"""Play the GAME engine (the strategy `PokerBot`, GTO base = exploit OFF) vs Slumbot and LOG every hand richly
(hero hole + board + full action string + winnings + won_pot + Slumbot's showdown cards) to a jsonl — the input for
`slumbot_adjust` (variance-adjusted bb/100) + per-decision mistake-grading.

WHY this exists: `slumbot_llm.py --bot solver` logs the SLOW solver-search variant (`SolverSlumbotBot`, ≈ −74…−374),
which is NOT the engine the app ships. This logs the actual `PokerBot` (≈ −46 vs Slumbot, matching −47 vs GTOW).

Run:  python -m research.slumbot_collect [hands=500] [out=data/slumbot_pokerbot.jsonl]
"""
from __future__ import annotations

import json
import math
import sys
import time

import pokerbot.strategy.bot as botmod
from pokerbot.benchmark.slumbot import BB, play_hand_verbose
from pokerbot.strategy.bot import PokerBot


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    out = sys.argv[2] if len(sys.argv) > 2 else "data/slumbot_pokerbot.jsonl"
    botmod.EQUITY_ITERS = 600
    bot = PokerBot(0, seed=7, exploit=False)            # GTO base = the −47 engine (NOT the exploit overlay)
    token = None
    wins: list[int] = []
    open(out, "w", encoding="utf-8").close()             # truncate any stale log
    t0 = time.time()
    for h in range(n):
        try:
            w, token, rec = play_hand_verbose(bot, token)
        except Exception as e:                           # noqa: BLE001 — never lose the run on one bad hand
            print(f"  hand {h} error: {e}", flush=True)
            continue
        wins.append(w)
        rec["net_bb"] = w / 100.0                         # so slumbot_adjust can read it directly
        with open(out, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        if (h + 1) % 20 == 0:
            bb100 = sum(wins) / len(wins)
            print(f"  {h+1:4d}/{n} | {bb100:+.1f} bb/100 | {(time.time()-t0)/(h+1)*1000:.0f} ms/hand", flush=True)

    tot, m = sum(wins), len(wins)
    bb100 = tot / m
    std = (sum((w - bb100) ** 2 for w in wins) / m) ** 0.5 / BB
    print(f"\n=== PokerBot (GTO base) vs Slumbot ===")
    print(f"hands={m} | total={tot:+d} chips | {bb100:+.1f} bb/100 (±{std/math.sqrt(m)*100:.1f} stderr)", flush=True)
    print(f"log -> {out}", flush=True)


if __name__ == "__main__":
    main()
