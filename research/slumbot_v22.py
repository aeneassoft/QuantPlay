"""v2.2 (the shipped anchor) vs Slumbot, WITH the Slumbot-specific exploit ON — the exploit-target run (2026-07-06).

Rationale: v2.2 ships as a GTO-mode profile (POKERB_EXPLOIT=0) tuned for the near-GTO GTOW. Slumbot is a strong but
EXPLOITABLE opponent, so here we run the v2.2 POSTFLOP TUNING (LINE_U / RIVER_ECALL / SIZE_INJECT / TRACKER_AGGRO_FULL /
SLOWPLAY / TURN_DEFENSE via POKERB_PRINCE=1) with the exploit layer forced back ON (POKERB_EXPLOIT=1) plus the
Slumbot-specific exploit (#49): the learned Slumbot fold model + Dirichlet opp-model seeded from its fold curve.

Variance reduction ("our own AIVAT"): full AIVAT needs Slumbot's ranges (unavailable), so we use the feasible substitute
`pokerbot.benchmark.slumbot_adjust` — the ALL-IN-EV adjustment (when both hands are known at an all-in, replace the
realized net with equity*pot - invested). It kills the biggest variance source (all-in coolers) unbiasedly. Rich per-hand
rows (incl. Slumbot's showdown cards) are logged for it.

Rate limiter (user warning): Slumbot throttles if hammered -> single-threaded + an inter-hand pace, and an abort if a run
of hands returns errors. Run:
  POKERB_PRINCE=1 POKERB_EXPLOIT=1 python -m research.slumbot_v22 --hands 1000 [--pace 0.3] [--out data/slumbot_v22.jsonl]
"""
from __future__ import annotations

import argparse
import json
import math
import time

import pokerbot.strategy.bot as botmod
from pokerbot import config
from pokerbot.benchmark.slumbot import BB, play_hand_verbose
from pokerbot.strategy.bot import PokerBot
from pokerbot.strategy.gto_mode import apply as apply_profile, fingerprint


def build_bot(iters: int) -> PokerBot:
    """v2.2 tuning + exploit ON + the Slumbot fold model/seed (mirrors slumbot.py --exploit-primary)."""
    botmod.EQUITY_ITERS = iters
    bot = PokerBot(0, seed=7, exploit=True)          # exploit ON; POKERB_EXPLOIT=1 keeps bot.py from forcing it off
    from pokerbot.strategy.opp_model import seed_from_fold_curve
    from pokerbot.strategy.postflop import LearnedFoldModel
    fm = LearnedFoldModel.load(config.KNOWLEDGE_DIR / "exploit" / "slumbot_fold.json")
    if fm:
        bot.fold_model = fm
        print("Loaded Slumbot fold model -> fold-equity-optimal sizing ON", flush=True)
    n_seed = seed_from_fold_curve(bot.opp_model)
    print(f"EXPLOIT-PRIMARY: seeded {n_seed} river buckets from slumbot_fold.json -> river EV engine ON", flush=True)
    return bot


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hands", type=int, default=1000)
    ap.add_argument("--pace", type=float, default=0.3, help="inter-hand sleep (s) to respect Slumbot's rate limit")
    ap.add_argument("--iters", type=int, default=600)
    ap.add_argument("--out", default="data/slumbot_v22.jsonl")
    args = ap.parse_args()

    # Materialize the FULL v2.2 profile into os.environ (setdefault -> our explicit POKERB_EXPLOIT=1 wins). Without
    # this, modules that read raw os.environ (not the prince-aware _gto_flag) get "half-on states" (bot.py L141 note).
    apply_profile()
    fp = fingerprint()
    print(f"CONFIG | exploit={fp.get('POKERB_EXPLOIT')} PRINCE={fp.get('POKERB_PRINCE')} "
          f"SLOWPLAY={fp.get('POKERB_SLOWPLAY')} RIVER_ECALL={fp.get('POKERB_RIVER_ECALL')} "
          f"LINE_U={fp.get('POKERB_LINE_U')} TRACKER_AGGRO_FULL={fp.get('POKERB_TRACKER_AGGRO_FULL')}", flush=True)
    bot = build_bot(args.iters)

    token = None
    wins: list[int] = []
    errs = 0                                          # consecutive-error guard (rate-limit / API trouble)
    open(args.out, "w", encoding="utf-8").close()     # truncate any stale log
    t0 = time.time()
    for h in range(args.hands):
        try:
            w, token, rec = play_hand_verbose(bot, token)
        except Exception as e:  # noqa: BLE001 — never lose the whole run on one bad hand
            errs += 1
            print(f"  hand {h} error: {e} (consecutive={errs})", flush=True)
            if errs >= 10:
                print("  ABORT: 10 consecutive errors — likely rate-limited/blocked. Stopping.", flush=True)
                break
            time.sleep(2.0 * errs)                     # back off hard on trouble
            continue
        errs = 0
        wins.append(w)
        rec["net_bb"] = w / 100.0                       # so slumbot_adjust reads it directly
        with open(args.out, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        if (h + 1) % 20 == 0:
            bb100 = sum(wins) / len(wins)
            print(f"  {h+1:4d}/{args.hands} | {bb100:+.1f} bb/100 raw | {(time.time()-t0)/(h+1)*1000:.0f} ms/hand", flush=True)
        if args.pace:
            time.sleep(args.pace)

    m = len(wins)
    if m == 0:
        print("no hands completed", flush=True)
        return
    tot = sum(wins)
    bb100 = tot / m
    std = (sum((w - bb100) ** 2 for w in wins) / m) ** 0.5 / BB
    print(f"\n=== v2.2 + Slumbot-exploit vs Slumbot (RAW) ===", flush=True)
    print(f"hands={m} | total={tot:+d} chips | {bb100:+.2f} bb/100 (+/-{std/math.sqrt(m)*100:.2f} stderr)", flush=True)
    obs = sum(sum(c) for c in bot.opp_model.counts.values())
    print(f"opp_model: {obs:.0f} counts across {len(bot.opp_model.counts)} buckets (live-learning grew the seed)", flush=True)
    print(f"log -> {args.out}  (run: python -m pokerbot.benchmark.slumbot_adjust {args.out} for the all-in-EV-adjusted bb/100)", flush=True)


if __name__ == "__main__":
    main()
