"""Measure the river/turn GTO RESOLVER's per-decision latency + fire-rate.

The line-aware resolver (`bot._river_resolve` via `resolver.py` + `range_tracker.weighted_ranges`,
confidence-gated) is OFF by default. This probe turns it ON and times Hero's RIVER decisions while
counting how often it actually FIRES (rationale["resolver"] is True) vs falls back to the floor.

Why it matters: a ~6s/decision resolver is unusable for the live playable bots (instant needed), and a
near-100% fire-rate means the confidence gate is effectively dead (it solves even on distorted ranges).

Run:  PYTHONUTF8=1 PYTHONPATH=. python -m research.resolver_probe [N_HANDS]
"""
import statistics
import sys
import time

from pokerbot.engine.game import HeadsUpGame
import pokerbot.strategy.bot as bot_module
from pokerbot.strategy.bot import PokerBot
from pokerbot.strategy.gto_baseline import GTOBaseline

bot_module.EQUITY_ITERS = 120
STACK, SB, BB = 20000, 50, 100


def main(n_hands: int = 120) -> None:
    g = HeadsUpGame(starting_stack=STACK, sb=SB, bb=BB, seed=11)
    river_times, fires, river_decisions = [], 0, 0
    for _ in range(n_hands):
        g.players[0].stack = g.players[1].stack = STACK
        g.start_hand()
        pb = PokerBot(0, seed=1)
        pb.use_resolver = pb.use_turn_resolver = True
        pb.value_raise_eq = 0.72
        villain = GTOBaseline(1, seed=2, iters=120)
        guard = 0
        while not g.hand_over and guard < 400:
            st = g.state(); guard += 1
            if st["to_act"] == 0:
                pb.hero_idx = 0
                t0 = time.perf_counter(); r = pb.decide(st); dt = time.perf_counter() - t0
                if st["street"] == "river":
                    river_decisions += 1; river_times.append(dt)
                    if isinstance(r.get("rationale"), dict) and r["rationale"].get("resolver"):
                        fires += 1
                act, amt = r["action"], r["amount"]
            else:
                villain.hero = 1; act, amt = villain.decide(st)
            g.act(act, amt)

    if not river_times:
        print("no river decisions reached"); return
    print(f"river_decisions={river_decisions}  resolver_FIRED={fires} "
          f"({100 * fires / river_decisions:.0f}%)  "
          f"avg_river_decide={1000 * statistics.mean(river_times):.0f}ms  "
          f"median={1000 * statistics.median(river_times):.0f}ms  "
          f"max={1000 * max(river_times):.0f}ms")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 120)
