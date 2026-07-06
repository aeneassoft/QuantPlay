"""RESOLVER-ON ablation campaign (the Quantplay-v8 live-breakage isolation, 2026-07-06).

WHY: the −58 live run exposed that every night-lever was validated resolver-OFF while live play is
resolver-dominated. This campaign runs the 2x2 isolation WITH RESOLVERS ON on one big CPU pod:
  a1_v8        POKERB_PRINCE=1                        (the broken live config = breakage baseline)
  a2_nopurify  PRINCE + POKERB_PURIFY=0               (isolates K1/K2: purify x resolver / deception-kill)
  a3_nonarrow  PRINCE + POKERB_RAISE_NARROW=0         (isolates K3: narrowed villain range x resolver)
  a4_v22       the exact tag-v2 FLAG SET on current code (the −19.70 reference level, flag-isolated)
All 4 arms share seed 70 -> paired deals; verdicts are read pairwise on the Analyzer as always.
HONEST LIMIT: the Analyzer prices resolver-poisoning damage (bad solves -> graded EV-loss) but stays
BLIND to range-transparency costs (K2) — that dimension needs the later live smoke (1,000 hands).

Budget: 4 arms x 1,000 hands, turn+river resolvers ON, 64 vCPU, shared solve cache. Family-1 precedent
(5x1500 turn-solving) ran 1.4h -> this is ~half the work => ~45 min + ~10 min setup. Hard wall 2.5h.

Run (ONLY on the user's go):  python -m infra.ablation_pod [vcpu=64] [wall_h=2.5]
Then ALWAYS verify: python -m infra.runpod_run --status   (no tracked pods)
"""
from __future__ import annotations

import atexit
import os
import sys
import tarfile
import time

from infra import runpod_run as R
from infra.cfv_pod_campaign import CODE_TGZ, _scp_down, _ssh, launch_pod, setup_pod, ssh_endpoint
from pokerbot import config

MAX_HOURLY = 2.60
N_HANDS = 1000
SEED = 70
# id ledger (STATE): 120000+ is the next free block; 2000 spacing; fresh dayoffsets 80-83
ARMS = [
    ("a1_v8",       {},                             120000, 80),
    ("a2_nopurify", {"POKERB_PURIFY": "0"},         122000, 81),
    ("a3_nonarrow", {"POKERB_RAISE_NARROW": "0"},   124000, 82),
    # tag-v2 flag set, explicit (NOT via PRINCE — PRINCE now implies the whole v8 stack):
    ("a4_v22", {"POKERB_PRINCE": "", "POKERB_GTO_MODE": "1", "POKERB_TURN_DEFENSE": "0.07",
                "POKERB_SLOWPLAY": "0.25", "POKERB_LINE_U": "1", "POKERB_RIVER_ECALL": "1",
                "POKERB_SIZE_INJECT": "1", "POKERB_TRACKER_AGGRO_FULL": "1"}, 126000, 83),
]
# NO --resolver off, NO POKERB_TURN_RESOLVER=0: resolvers stay at their live defaults (ON) — the point.
BASE_ENV = "POKERB_PRINCE=1 PYTHONUTF8=1 PYTHONPATH=/root/pokerb TEXASSOLVER_DIR=/root/tsolver"


def build_tarball() -> None:
    with tarfile.open(CODE_TGZ, "w:gz") as t:
        t.add("pokerbot")
        t.add("research")
        t.add("infra")
        t.add("knowledge_base")
        t.add("data/census/gtow_tree.json")
    print(f"code tarball: {os.path.getsize(CODE_TGZ) / 1e6:.1f} MB", flush=True)


def arm_cmd(name: str, extra: dict, idbase: int, dayoffset: int) -> str:
    env = " ".join([BASE_ENV] + [f"{k}={v}" for k, v in extra.items() if v != ""])
    unset = " ".join(f"-u {k}" for k, v in extra.items() if v == "")     # a4: PRINCE must be UNSET, not "0"-ish
    return (f"cd /root/pokerb && ( nohup env {unset} {env} python3 -m research.pokerstars_export "
            f"--n {N_HANDS} --seed {SEED} --fast "
            f"--idbase {idbase} --dayoffset {dayoffset} "
            f"--out /root/pokerb/hu_{name}_{N_HANDS}.txt < /dev/null > /root/arm_{name}.log 2>&1 & ) "
            f"&& echo LAUNCHED_{name}")


def main() -> None:
    a = sys.argv[1:]
    vcpu = int(a[0]) if len(a) > 0 else 64
    wall_h = float(a[1]) if len(a) > 1 else 2.5
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
            print(f"ABORT: ${rate}/hr > ${MAX_HOURLY}", flush=True)
            return
        ip, port = ssh_endpoint(pid)
        if not ip or not setup_pod(ip, port):
            return
        r = _ssh(ip, port, "pip install -q --break-system-packages torch --index-url https://download.pytorch.org/whl/cpu "
                           "&& python3 -c 'import torch; print(\"TORCH\", torch.__version__)'", timeout=900)
        if "TORCH" not in (r.stdout or ""):
            print(f"torch install FAILED: {((r.stderr or '') + (r.stdout or ''))[-200:]}", flush=True)
            return
        for name, extra, idbase, dayoffset in ARMS:
            r = _ssh(ip, port, arm_cmd(name, extra, idbase, dayoffset), timeout=60)
            print(f"  {name}: {(r.stdout or '').strip()}", flush=True)
        time.sleep(20)
        alive = _ssh(ip, port, "pgrep -fc pokerstars_export", timeout=30)
        print(f"  arms alive: {(alive.stdout or '').strip()}/{len(ARMS)}", flush=True)

        done: set = set()
        while time.time() - t0 < wall_h * 3600:
            time.sleep(180)
            ls = _ssh(ip, port, f"ls /root/pokerb/hu_*_{N_HANDS}.txt 2>/dev/null", timeout=60)
            for f in (ls.stdout or "").splitlines():
                nm = f.split("hu_")[-1].replace(f"_{N_HANDS}.txt", "")
                if nm and nm not in done:
                    done.add(nm)
                    print(f"  ARM DONE: {nm} ({len(done)}/{len(ARMS)}) at {(time.time()-t0)/60:.0f}min", flush=True)
            if len(done) >= len(ARMS):
                break
        for name, *_ in ARMS:
            res = _scp_down(ip, port, f"/root/pokerb/hu_{name}_{N_HANDS}.txt", str(out_dir / f"hu_{name}_{N_HANDS}.txt"))
            print(f"  pull hu_{name}_{N_HANDS}.txt: {'OK' if res.returncode == 0 else 'MISSING'}", flush=True)
            _scp_down(ip, port, f"/root/arm_{name}.log", str(out_dir / f"arm_{name}.log"))
        print(f"DONE in {(time.time()-t0)/60:.0f} min -> {out_dir}", flush=True)
    finally:
        _killall()


if __name__ == "__main__":
    main()
