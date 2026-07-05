"""S6 (plan 2026-07-04): the interleaved GTOW AIVAT A/B — A = HEAD default vs B = GTOW-mode (POKERB_GTO_MODE=1).

Paired dealing vs GTOW is impossible (the server deals; no seed in NewHandRequest), so the best variance control is
INTERLEAVED blocks (A,B,A,B,...) + AIVAT: opponent/server drift cancels across arms. Each block runs the client
in-process from the PC (free; --agent-type pokerbot needs no pod) as a SUBPROCESS so the arm's env profile applies
cleanly at import time. Per-block per-hand logs are tagged in a manifest; the report follows the plan's Phase-4
standard: raw +/- SE, 5%-trim body, catastrophe share, config fingerprint.

Usage:  python -m research.gtow_ab --blocks 5 --block-hands 250 --conc 8
        (5 blocks/arm x 250 = 1250 hands/arm; ~2-3h wall-clock)
Requires env GTOWIZARD_API_KEY (use key #2 — keeps the main account aggregate clean).
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import statistics
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENT = os.path.join(REPO, "tools", "gtow_client", "src")
MANIFEST = os.path.join(REPO, "data", "census", "ab_manifest.json")
BB = 100.0


def _newest_log(after: float) -> str | None:
    logs = [(os.path.getmtime(p), p) for p in glob.glob(os.path.join(REPO, "data", "sessions", "gtow_hands_*.jsonl"))]
    logs = [(m, p) for m, p in logs if m >= after - 5]
    return max(logs)[1] if logs else None


def run_block(arm: str, hands: int, conc: int) -> dict:
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env.pop("POKERB_GTO_MODE", None)
    env.pop("POKERB_PRINCE", None)   # bug-hunt fix: PRINCE implies the base profile — must not leak into arms
    if arm == "B":
        env["POKERB_GTO_MODE"] = "1"
    t0 = time.time()
    r = subprocess.run([sys.executable, "-m", "main", f"--agent_type=pokerbot",
                        f"--num_hands={hands}", f"--num_concurrent_hands={conc}"],
                       cwd=CLIENT, env=env, capture_output=True, text=True, timeout=hands * 60)
    log = _newest_log(t0)
    tail = "\n".join((r.stdout + r.stderr).splitlines()[-12:])
    aivat_line = next((ln for ln in tail.splitlines() if "AIVAT" in ln), "")
    return {"arm": arm, "hands": hands, "log": log, "aivat_line": aivat_line.strip(),
            "wall_s": round(time.time() - t0, 1), "rc": r.returncode}


def _stats(files: list[str]) -> dict:
    xs = []
    for f in files:
        if not f:
            continue
        for line in open(f, encoding="utf-8"):
            try:
                a = json.loads(line).get("aivat")
            except json.JSONDecodeError:
                continue
            if a is not None:
                xs.append(a / BB * 100.0)          # per-hand AIVAT in bb/100 units
    if not xs:
        return {"n": 0}
    n = len(xs)
    mean = sum(xs) / n
    se = statistics.pstdev(xs) / math.sqrt(n)
    k = max(1, int(0.05 * n))
    body = statistics.mean(sorted(xs)[k:-k]) if n > 2 * k else mean
    catastrophes = sum(1 for x in xs if x < -100 * 100 / 100)   # < -100bb on the hand
    return {"n": n, "raw": round(mean, 2), "se": round(se, 2), "body_trim5": round(body, 2),
            "catastrophes": catastrophes, "cat_share_pct": round(100 * catastrophes / n, 2)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--blocks", type=int, default=5, help="blocks PER ARM")
    ap.add_argument("--block-hands", type=int, default=250)
    ap.add_argument("--conc", type=int, default=8)
    args = ap.parse_args()
    if not os.environ.get("GTOWIZARD_API_KEY"):
        sys.exit("set GTOWIZARD_API_KEY (key #2) first")
    from pokerbot.strategy.gto_mode import PROFILE
    manifest = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "profile_B": PROFILE, "blocks": []}
    for i in range(args.blocks):
        for arm in ("A", "B"):
            print(f"[block {i+1}/{args.blocks} arm {arm}] {args.block_hands} hands ...", flush=True)
            b = run_block(arm, args.block_hands, args.conc)
            print(f"   -> {b['aivat_line']}  ({b['wall_s']}s, log={os.path.basename(b['log'] or '?')})", flush=True)
            manifest["blocks"].append(b)
            json.dump(manifest, open(MANIFEST, "w", encoding="utf-8"), indent=1)
    for arm in ("A", "B"):
        files = [b["log"] for b in manifest["blocks"] if b["arm"] == arm]
        s = _stats(files)
        label = "HEAD default" if arm == "A" else "GTOW-mode"
        print(f"\n=== ARM {arm} ({label}) ===\n  {s}")
    print(f"\nmanifest -> {MANIFEST}")


if __name__ == "__main__":
    main()
