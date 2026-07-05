"""Self-killing MULTI-POD CFV data-gen campaign. Provisions N CPU pods, sets each up (TexasSolver-Linux + the repo
code + deps), runs the SATURATED sharded parallel gen (extraction/cfv_data --gen), pulls + merges the shards, and
ALWAYS terminates EVERY tracked pod in a `finally` AND via `atexit` — so no pod is ever orphaned (the user's #1
cost rule). A hard wall-clock cap is the backstop. Designed to run as a BACKGROUND process; the kill is tied to the
run finishing/erroring, not a fragile timer.

Run:  python -m infra.cfv_pod_campaign [n_pods=2] [n_per_pod=4] [vcpu=32] [wall_min=25] [workers=16] [threads=2]
ALWAYS verify afterwards: python -m infra.runpod_run --status   (should show no tracked pods)
"""
from __future__ import annotations

import atexit
import json
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor

from infra import runpod_run as R
from pokerbot import config

KEY = r"C:\Users\hampe\.ssh\pokerb_runpod"
SOLVER_URL = "https://github.com/bupticybee/TexasSolver/releases/download/v0.2.0/TexasSolver-v0.2.0-Linux.zip"
CODE_TGZ = str(config.DATA_DIR / "podcode.tgz")     # the repo code as ONE tarball -> one fast scp (vs scp -r of 100s of small files)
SSH = ["-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", "-o", "ConnectTimeout=20"]


def _ssh(ip, port, cmd, timeout=None):
    # decode the pod's stdout as UTF-8 (it prints → / — / bb symbols); errors="replace" so a stray byte never crashes
    # the local reader. Windows defaults to cp1252 -> a mid-stream UnicodeDecodeError once buried a real SFT result.
    return subprocess.run(["ssh", "-i", KEY, "-p", str(port), *SSH, f"root@{ip}", cmd],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)


def _scp_up(ip, port, locals_, remote):
    return subprocess.run(["scp", "-i", KEY, "-P", str(port), *SSH, "-r", *locals_, f"root@{ip}:{remote}"],
                          capture_output=True, text=True, timeout=300)


def _scp_down(ip, port, remote, local):
    return subprocess.run(["scp", "-i", KEY, "-P", str(port), *SSH, f"root@{ip}:{remote}", local],
                          capture_output=True, text=True, timeout=180)


def launch_pod(vcpu):
    pub = open(R.PUBKEY_FILE, encoding="utf-8").read().strip()
    body = {"name": "pokerb-cfv", "imageName": R.IMAGE, "computeType": "CPU", "cpuFlavorIds": ["cpu5c"],
            "vcpuCount": vcpu, "containerDiskInGb": 30, "volumeInGb": 0, "ports": ["22/tcp"],
            "env": {"PUBLIC_KEY": pub}}
    code, resp = R._req("POST", "/pods", body)
    if code not in (200, 201):
        print(f"  launch FAILED {code}: {json.dumps(resp)[:200]}", flush=True)
        return None
    pid = resp.get("id")
    R._track(pid)                                   # multi-pod-safe tracking -> --kill / finally gets it
    print(f"  launched pod {pid} ({vcpu}vCPU, ${resp.get('costPerHr')}/hr)", flush=True)
    return pid


def ssh_endpoint(pid, wait_s=300):
    """Poll the pod until its public SSH ip:port is live; return (ip, port) or (None, None)."""
    t0 = time.time()
    shown = False
    while time.time() - t0 < wait_s:
        _code, resp = R._req("GET", f"/pods/{pid}")
        ip = resp.get("publicIp") or None
        port = None
        rt = resp.get("runtime") or {}
        for p in (rt.get("ports") or []):
            if str(p.get("privatePort")) == "22" and p.get("publicPort"):
                ip = ip or p.get("ip")
                port = p.get("publicPort")
        if not port:
            pm = resp.get("portMappings")
            if isinstance(pm, dict):
                port = pm.get("22/tcp") or pm.get("22")
        if ip and port:
            return ip, int(port)
        if not shown and time.time() - t0 > 40:     # one-time structure dump to debug parsing if it stalls
            print(f"  [{pid}] not-ready resp: {json.dumps(resp)[:400]}", flush=True)
            shown = True
        time.sleep(8)
    return None, None


def setup_pod(ip, port):
    """Upload the repo code, then install TexasSolver-Linux + deps via pod_setup.sh (quote-safe, python-zipfile
    extract, real success-check). Returns True ONLY if the solver is actually available (AVAIL True)."""
    try:
        up = subprocess.run(["scp", "-i", KEY, "-P", str(port), *SSH, CODE_TGZ, f"root@{ip}:/root/code.tgz"],
                            capture_output=True, text=True, timeout=180)
        if up.returncode != 0:
            print(f"  [{ip}:{port}] code upload FAILED: {(up.stderr or '')[:200]}", flush=True)
            return False
        _ssh(ip, port, "mkdir -p /root/pokerb && tar xzf /root/code.tgz -C /root/pokerb", timeout=120)
        r = _ssh(ip, port, f"bash /root/pokerb/infra/pod_setup.sh {SOLVER_URL}", timeout=600)  # pip can be slow
        if "SETUP_OK" not in (r.stdout or ""):
            print(f"  [{ip}:{port}] solver/deps setup FAILED: {((r.stderr or '') + (r.stdout or ''))[-300:]}", flush=True)
            return False
        chk = _ssh(ip, port, "cd /root/pokerb && PYTHONPATH=/root/pokerb TEXASSOLVER_DIR=/root/tsolver "
                             "python3 -c 'from pokerbot.strategy import gto_oracle as O; print(\"AVAIL\", O.available())'", timeout=90)
        ok = "AVAIL True" in (chk.stdout or "")
        print(f"  [{ip}:{port}] setup {'OK' if ok else 'FAILED'} | avail: {(chk.stdout or chk.stderr or '').strip()[:50]}", flush=True)
        return ok
    except Exception as e:  # noqa: BLE001  -- a slow/failed pod is SKIPPED, never aborts the whole campaign
        print(f"  [{ip}:{port}] setup EXCEPTION (skipping this pod): {type(e).__name__}: {str(e)[:110]}", flush=True)
        return False


def run_gen(ip, port, seed, n, workers, threads, wall_min):
    """Run the saturated gen on the pod (blocking ssh). Writes /root/pokerb/shard_<seed>.jsonl."""
    cmd = (f"cd /root/pokerb && PYTHONPATH=/root/pokerb TEXASSOLVER_DIR=/root/tsolver OMP_NUM_THREADS={threads} "
           f"python3 -m research.cfv_data --gen {n} --workers {workers} --threads {threads} --seed {seed} "
           f"--out /root/pokerb/shard_{seed}.jsonl")
    r = _ssh(ip, port, cmd, timeout=wall_min * 60)
    tail = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()[-2:]
    print(f"  [seed {seed}] gen done: {' | '.join(tail)[:160]}", flush=True)


def main():
    import sys
    a = sys.argv[1:]
    n_pods = int(a[0]) if len(a) > 0 else 2
    n_per = int(a[1]) if len(a) > 1 else 4
    vcpu = int(a[2]) if len(a) > 2 else 32
    wall_min = int(a[3]) if len(a) > 3 else 25
    workers = int(a[4]) if len(a) > 4 else 16
    threads = int(a[5]) if len(a) > 5 else 2
    out_dir = config.DATA_DIR / "cfv_shards"
    out_dir.mkdir(parents=True, exist_ok=True)
    import tarfile                                    # bundle the code ONCE -> one fast scp (scp -r of 100s of files stalls)
    with tarfile.open(CODE_TGZ, "w:gz") as _t:
        _t.add("pokerbot")
        _t.add("research")
        _t.add("training")
        _t.add("infra")
    print(f"  code tarball: {os.path.getsize(CODE_TGZ) / 1e6:.1f} MB", flush=True)
    t0 = time.time()

    def _killall():
        print("  >>> finally/atexit: terminating ALL tracked pods <<<", flush=True)
        try:
            R.kill()
        except Exception as e:  # noqa: BLE001
            print(f"  kill error (run `python -m infra.runpod_run --kill` MANUALLY): {e}", flush=True)
    atexit.register(_killall)

    print(f"CAMPAIGN: {n_pods} pods x {vcpu}vCPU, {n_per} samples/pod (workers={workers} threads={threads}), "
          f"wall {wall_min}min. Pods self-terminate in finally+atexit.", flush=True)
    try:
        pods = [p for p in (launch_pod(vcpu) for _ in range(n_pods)) if p]
        if not pods:
            print("no pods launched; aborting.", flush=True)
            return
        eps = {}

        def _prep(pid):                              # set up ALL pods CONCURRENTLY (sequential setup wasted the run's time budget)
            ip, port = ssh_endpoint(pid)
            return (pid, (ip, port)) if (ip and port and setup_pod(ip, port)) else (pid, None)
        with ThreadPoolExecutor(max_workers=len(pods)) as ex:
            for pid, ep in ex.map(_prep, pods):
                if ep:
                    eps[pid] = ep
                else:
                    print(f"  pod {pid} setup failed -> skipping (it will still be killed)", flush=True)
        if not eps:
            print("no pods set up; aborting (pods will be killed).", flush=True)
            return
        print(f"  {len(eps)} pod(s) ready; running saturated gen in parallel...", flush=True)
        with ThreadPoolExecutor(max_workers=len(eps)) as ex:
            futs = []
            for i, (pid, (ip, port)) in enumerate(eps.items()):
                futs.append(ex.submit(run_gen, ip, port, i, n_per, workers, threads,
                                      max(5, wall_min - int((time.time() - t0) / 60) - 2)))
            for f in futs:
                try:
                    f.result()
                except Exception as e:  # noqa: BLE001
                    print(f"  a gen errored: {e}", flush=True)
        # pull + merge
        merged = out_dir / "cfv_dataset.jsonl"
        total = 0
        with open(merged, "a", encoding="utf-8") as mf:
            for i, (pid, (ip, port)) in enumerate(eps.items()):
                local = str(out_dir / f"shard_{i}.jsonl")
                d = _scp_down(ip, port, f"/root/pokerb/shard_{i}.jsonl", local)
                if d.returncode == 0 and os.path.exists(local):
                    rows = [ln for ln in open(local, encoding="utf-8") if ln.strip()]
                    mf.writelines(rows if all(r.endswith("\n") for r in rows) else [r + "\n" for r in rows])
                    total += len(rows)
                    print(f"  pulled shard {i}: {len(rows)} samples", flush=True)
        print(f"CAMPAIGN DONE: {total} samples merged -> {merged}", flush=True)
    finally:
        _killall()


if __name__ == "__main__":
    main()
