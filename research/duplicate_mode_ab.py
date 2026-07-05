"""The FAST local canary (user ask 2026-07-04): HEAD vs GTOW-mode on MIRRORED decks vs GTOBaseline — $0, no
network, card luck cancelled twice (duplicate seats within each arm + the SAME decks across arms -> paired deltas).

Because the mode profile is applied at IMPORT time (postflop/advisor flags), each arm runs as a SUBPROCESS; the
per-deck edges land in JSON and the parent computes the paired MODE-HEAD delta. The resolver is OFF in both arms
(speed; it has its own probes) -> this canary gates the NON-resolver levers: exploit-off, fold-prior, river
floor/LA, tracker damping, census sizes/snaps, limp clamp.

HONEST LIMIT (the value-floor lesson): duplicate measures EV vs GTOBaseline, NOT vs GTOW — a lever can win here
and be GTOW-neutral. This is the SPEW CANARY (a big negative = something broke); the GTOW-side truth stays the
Analyzer grade + the AIVAT A/B.

Usage: python -m research.duplicate_mode_ab [--decks 500]     (child mode: --arm head|mode --decks N --out f.json)
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import subprocess
import sys

OUT_DIR = os.path.join("data", "census")


def _arm(decks: int, out: str) -> None:
    """Child process: play PokerBot(LIVE env config, resolver OFF) vs GTOBaseline on gen_decks(seed=7)."""
    from pokerbot.strategy.gto_mode import apply, fingerprint
    apply()
    import pokerbot.strategy.bot as botmod
    botmod.EQUITY_ITERS = 120                     # equal in both arms -> cancels in the paired delta
    from pokerbot.strategy.bot import PokerBot
    from pokerbot.benchmark.duplicate import duplicate_ab, gen_decks, gto

    def make(seat):
        pb = PokerBot(seat, seed=1, exploit=os.environ.get("POKERB_EXPLOIT", "1") != "0")
        pb.use_resolver = pb.use_turn_resolver = False        # speed: the resolver has its own probes
        if os.environ.get("POKERB_GTO_MODE", "0") == "1":
            pb.use_probe = False
        def d(st):
            pb.hero_idx = seat
            r = pb.decide(st)
            return r["action"], r["amount"]
        return d

    decks_l = gen_decks(decks, seed=7)
    bb100, se, edges = duplicate_ab(make, gto(1), decks_l, return_edges=True)
    json.dump({"bb100": bb100, "se": se, "edges": edges, "fingerprint": fingerprint()},
              open(out, "w", encoding="utf-8"))
    print(f"arm done: {bb100:+.1f} +/- {se:.1f} bb/100 (n_decks={decks})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--decks", type=int, default=500)
    ap.add_argument("--arm", choices=["head", "mode"])
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    if args.arm:                                   # child invocation
        _arm(args.decks, args.out)
        return
    os.makedirs(OUT_DIR, exist_ok=True)
    outs = {}
    for arm in ("head", "mode"):
        out = os.path.join(OUT_DIR, f"dup_{arm}.json")
        env = dict(os.environ, PYTHONUTF8="1")
        env.pop("POKERB_GTO_MODE", None)
        env.pop("POKERB_PRINCE", None)   # bug-hunt fix: PRINCE implies the base profile — must not leak into arms
        if arm == "mode":
            env["POKERB_GTO_MODE"] = "1"
        print(f"[{arm}] {args.decks} mirrored decks vs GTOBaseline ...", flush=True)
        subprocess.run([sys.executable, "-m", "research.duplicate_mode_ab",
                        "--arm", arm, "--decks", str(args.decks), "--out", out], env=env, check=True)
        outs[arm] = json.load(open(out, encoding="utf-8"))
    h, m = outs["head"], outs["mode"]
    # paired per-deck delta (same decks in both arms -> deck luck cancels across arms too)
    deltas = [(bm - bh) / 100.0 for bh, bm in zip(h["edges"], m["edges"])]   # chips -> bb per deck(2 hands)
    n = len(deltas)
    mean_delta_bb100 = sum(deltas) / n / 2.0 * 100.0
    se = statistics.pstdev(deltas) / math.sqrt(n) / 2.0 * 100.0
    print(f"\nHEAD : {h['bb100']:+.1f} +/- {h['se']:.1f} bb/100")
    print(f"MODE : {m['bb100']:+.1f} +/- {m['se']:.1f} bb/100")
    print(f"PAIRED delta (MODE - HEAD): {mean_delta_bb100:+.1f} +/- {se:.1f} bb/100  (n={n} decks)")
    print("verdict:", "MODE better (>=2SE)" if mean_delta_bb100 > 2 * se
          else ("MODE WORSE (<= -2SE) — investigate before any GTOW spend" if mean_delta_bb100 < -2 * se
                else "inside noise (canary passes: no spew regression)"))


if __name__ == "__main__":
    main()
