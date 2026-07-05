"""Self-killing CPU-pod campaign: generate the FULL Analyzer arm family in PARALLEL on one big CPU pod.

Why a pod: one 1500-hand seed-55 export runs HOURS locally (cold turn-solve cache after any lever changes a
line); the ladder needs FIVE arms (fresh v3 anchor + v3.2/v3.3/v3.4/v3.5) and, since the all-in-HH exporter
fix, every pairing must come from ONE exporter + ONE platform anyway (torch CPU float bits differ across
platforms -> arms are only byte-comparable within a platform). On a 64-vCPU cpu5c all five run concurrently
(8 solver threads each) and SHARE one solve cache (identical seed-55 deals -> heavy cross-arm cache hits).

Cost guard: prints $/hr at launch and ABORTS if > MAX_HOURLY; HARD_WALL_H backstop; every exit path kills
the pod (finally + atexit — the user's #1 cost rule). Results -> data/gtow_upload/pod/hu_<arm>_1500.txt.

Run:  python -m infra.export_pod [vcpu=64] [wall_h=10]
Then ALWAYS verify: python -m infra.runpod_run --status   (no tracked pods)
"""
from __future__ import annotations

import atexit
import json
import os
import sys
import tarfile
import time

from infra import runpod_run as R
from infra.cfv_pod_campaign import CODE_TGZ, SOLVER_URL, _scp_down, _ssh, launch_pod, setup_pod, ssh_endpoint
from pokerbot import config

MAX_HOURLY = 2.60                 # $/hr abort threshold (budget ~$30 -> ~10h at worst)
N_HANDS = 1500
SEED = 55
# (name, extra env, idbase, dayoffset) — the id ledger continues 302/34 = the local v3.2 run
ARMS = [
    ("v3fresh", {},                                   303, 35),
    ("v32",     {"POKERB_RIVER_THIN_SEL": "0.40"},    304, 36),
    ("v33",     {"POKERB_RAISE_NARROW": "1"},         305, 37),
    ("v34",     {"POKERB_AUDIT_FIX": "1"},            306, 38),
    ("v35",     {"POKERB_ADVISOR_ROLE_POS": "1"},     307, 39),
]
BASE_ENV = "POKERB_PRINCE=1 PYTHONUTF8=1 PYTHONPATH=/root/pokerb TEXASSOLVER_DIR=/root/tsolver"


def build_tarball() -> None:
    """Code + the runtime data the export path needs (advisor .pt nets, census tree, blueprint ranges)."""
    with tarfile.open(CODE_TGZ, "w:gz") as t:
        t.add("pokerbot")
        t.add("research")
        t.add("infra")
        t.add("knowledge_base")                      # 29M: advisor nets + ranges + formulas (blueprint deps)
        t.add("data/census/gtow_tree.json")
    print(f"code tarball: {os.path.getsize(CODE_TGZ) / 1e6:.1f} MB", flush=True)


def arm_cmd(name: str, extra: dict, idbase: int, dayoffset: int) -> str:
    env = " ".join([BASE_ENV] + [f"{k}={v}" for k, v in extra.items()])
    return (f"cd /root/pokerb && nohup env {env} python3 -m research.pokerstars_export "
            f"--n {N_HANDS} --seed {SEED} --fast --resolver off "
            f"--idbase {idbase} --dayoffset {dayoffset} "
            f"--out /root/pokerb/hu_{name}_1500.txt < /dev/null > /root/arm_{name}.log 2>&1 & echo LAUNCHED_{name}")


def main() -> None:
    a = sys.argv[1:]
    vcpu = int(a[0]) if len(a) > 0 else 64
    wall_h = float(a[1]) if len(a) > 1 else 10.0
    out_dir = config.DATA_DIR.parent / "data" / "gtow_upload" / "pod"
    out_dir.mkdir(parents=True, exist_ok=True)
    build_tarball()

    def _killall() -> None:
        print(">>> finally/atexit: terminating ALL tracked pods <<<", flush=True)
        try:
            R.kill()
        except Exception as e:  # noqa: BLE001
            print(f"kill error (run `python -m infra.runpod_run --kill` MANUALLY): {e}", flush=True)
    atexit.register(_killall)

    t0 = time.time()
    try:
        pid = launch_pod(vcpu)
        if not pid:
            return
        _code, resp = R._req("GET", f"/pods/{pid}")
        rate = float(resp.get("costPerHr") or 0)
        print(f"pod {pid}: ${rate}/hr", flush=True)
        if rate > MAX_HOURLY:
            print(f"ABORT: ${rate}/hr > ${MAX_HOURLY} budget guard", flush=True)
            return
        ip, port = ssh_endpoint(pid)
        if not ip:
            print("no ssh endpoint; aborting", flush=True)
            return
        if not setup_pod(ip, port):
            return
        # torch CPU for the advisor nets (pod_setup.sh installs only treys/numpy)
        r = _ssh(ip, port, "pip install -q --break-system-packages torch --index-url https://download.pytorch.org/whl/cpu "
                           "&& python3 -c 'import torch; print(\"TORCH\", torch.__version__)'", timeout=900)
        if "TORCH" not in (r.stdout or ""):
            print(f"torch install FAILED: {((r.stderr or '') + (r.stdout or ''))[-200:]}", flush=True)
            return
        # advisor availability sanity BEFORE burning hours
        chk = _ssh(ip, port, f"cd /root/pokerb && {BASE_ENV} python3 -c "
                             "'from pokerbot.strategy import advisor as A; "
                             "print(\"ADV\", A.available(\"flop\"), A.available(\"river\"), A.defense_available())'",
                   timeout=120)
        print(f"advisors: {(chk.stdout or chk.stderr or '').strip()[:80]}", flush=True)
        if "ADV True True True" not in (chk.stdout or ""):
            print("advisor nets not available on pod; aborting", flush=True)
            return

        for name, extra, idbase, dayoffset in ARMS:
            r = _ssh(ip, port, arm_cmd(name, extra, idbase, dayoffset), timeout=60)
            print(f"  {name}: {(r.stdout or '').strip()}", flush=True)

        # poll until all five outputs exist (the export writes its .txt at the very end) or the wall cap
        done: set = set()
        while time.time() - t0 < wall_h * 3600:
            time.sleep(300)
            ls = _ssh(ip, port, "ls /root/pokerb/hu_*_1500.txt 2>/dev/null; echo ---; "
                                "tail -c 300 /root/arm_*.log | tr '\\n' ' '", timeout=60)
            files = [ln for ln in (ls.stdout or "").splitlines() if ln.endswith("_1500.txt")]
            for f in files:
                nm = f.split("hu_")[-1].replace("_1500.txt", "")
                if nm not in done:
                    done.add(nm)
                    print(f"  ARM DONE: {nm} ({len(done)}/{len(ARMS)}) at {(time.time()-t0)/3600:.1f}h", flush=True)
            if len(done) >= len(ARMS):
                break
            print(f"  [{(time.time()-t0)/3600:.1f}h] {len(done)}/{len(ARMS)} arms done | "
                  f"{(ls.stdout or '').split('---')[-1].strip()[:180]}", flush=True)

        # pull whatever finished (+ logs for the post-mortem of anything that didn't)
        for name, *_ in ARMS:
            res = _scp_down(ip, port, f"/root/pokerb/hu_{name}_1500.txt", str(out_dir / f"hu_{name}_1500.txt"))
            print(f"  pull hu_{name}_1500.txt: {'OK' if res.returncode == 0 else 'MISSING'}", flush=True)
            _scp_down(ip, port, f"/root/arm_{name}.log", str(out_dir / f"arm_{name}.log"))
        print(f"DONE in {(time.time()-t0)/3600:.2f}h -> {out_dir}", flush=True)
    finally:
        _killall()


if __name__ == "__main__":
    main()
