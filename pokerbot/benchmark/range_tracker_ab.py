"""EV gate for the range-tracker KEYSTONE floor wiring: does `use_range_tracker` (the action-consistent per-combo
villain range — GATE A3-FLOOR: +42% closer to solver truth than _narrow) actually improve the floor's bb/100,
card-luck-cancelled (duplicate poker)? The river-defense-advisor lesson is explicit: a better range MODEL is NOT
automatically +EV (it was +19% MSE but -14 bb/100 on the river), so this MUST be measured before claiming a win.

Two reads on the SAME fixed decks:
  (1) head-to-head: tracker-ON floor vs tracker-OFF floor (most sensitive to the change).
  (2) paired vs GTOBaseline: tracker-ON-vs-GTO minus tracker-OFF-vs-GTO, paired per deck (a regression catcher;
      GTOBaseline is too weak to PROVE a GTOW gain, but a local regression would show up here).
Run: python -m pokerbot.benchmark.range_tracker_ab --decks 300
"""
from __future__ import annotations

import argparse

from pokerbot.benchmark.duplicate import duplicate_ab, gen_decks, gto, pokerbot


def _verdict(bb: float, se: float) -> str:
    if bb > se:
        return "ON better"
    if bb < -se:
        return "ON worse"
    return "neutral (within 1 stderr)"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--decks", type=int, default=300)
    args = ap.parse_args()
    decks = gen_decks(args.decks, seed=7)

    print(f"=== Range-tracker floor EV gate ({args.decks} decks, card-luck-cancelled, exploit=OFF) ===\n")

    print("(1) head-to-head: tracker-ON floor vs tracker-OFF floor")
    bb, se = duplicate_ab(pokerbot(exploit=False, use_range_tracker=True),
                          pokerbot(exploit=False, use_range_tracker=False), decks)
    print(f"    ON over OFF: {bb:+.1f} +/- {se:.1f} bb/100   ({_verdict(bb, se)})\n")

    print("(2) paired vs GTOBaseline (same decks):")
    bb_on, se_on, e_on = duplicate_ab(pokerbot(exploit=False, use_range_tracker=True), gto(1), decks, return_edges=True)
    bb_off, se_off, e_off = duplicate_ab(pokerbot(exploit=False, use_range_tracker=False), gto(1), decks, return_edges=True)
    d = [a - b for a, b in zip(e_on, e_off)]            # paired per-deck delta (ON edge - OFF edge vs the same GTO)
    n = len(d)
    md = sum(d) / n
    var = sum((x - md) ** 2 for x in d) / max(1, n - 1)
    dbb = md / 2 / 100 * 100                            # 2 hands/deck, bb=100
    dse = (var ** 0.5 / n ** 0.5) / 2 / 100 * 100
    print(f"    tracker-ON  vs GTOBaseline: {bb_on:+.1f} +/- {se_on:.1f}")
    print(f"    tracker-OFF vs GTOBaseline: {bb_off:+.1f} +/- {se_off:.1f}")
    print(f"    PAIRED delta (ON - OFF):    {dbb:+.1f} +/- {dse:.1f} bb/100   ({_verdict(dbb, dse)})")
    print("\nVERDICT: delta positive or neutral (>= -1 stderr) -> KEEP tracker ON; clearly negative -> revert.")


if __name__ == "__main__":
    main()
