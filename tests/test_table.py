"""Stress-test the 6-max engine: random multiway hands w/ many all-ins -> chip conservation + side pots."""
from __future__ import annotations

import random

from pokerbot.engine.table import Table


def policy(la, rng):
    opts = []
    if la.get("can_check"):
        opts.append("check")
    if la.get("can_call"):
        opts += ["call", "call"]
    if la.get("can_fold"):
        opts.append("fold")
    if la.get("can_raise"):
        opts += ["raise", "allin"]          # bias toward all-ins to exercise side pots
    a = rng.choice(opts)
    amt = None
    if a == "raise":
        lo, hi = la["raise_min"], la["raise_max"]
        amt = lo if rng.random() < 0.5 else rng.randint(lo, hi)
    return a, amt


def main() -> None:
    rng = random.Random(1)
    N, start = 6, 10000
    total = N * start
    t = Table([f"P{i}" for i in range(N)], starting_stack=start, sb=50, bb=100, seed=1)
    showdowns = folds = allin_hands = sidepot_hands = 0
    for h in range(500):
        for s in t.seats:
            s.stack = start                  # reset for a clean conservation check
        t.start_hand()
        guard = 0
        while not t.hand_over:
            a, amt = policy(t.legal_actions(), rng)
            t.act(a, amt)
            guard += 1
            assert guard < 5000, "runaway"
        ssum = sum(s.stack for s in t.seats)
        assert ssum == total, f"chip leak hand {h}: {ssum} != {total}"
        assert all(s.stack >= 0 for s in t.seats), f"negative stack hand {h}"
        if t.result["reason"] == "showdown":
            showdowns += 1
        else:
            folds += 1
        if any(s.all_in for s in t.seats):
            allin_hands += 1
        if t.result.get("pots") and len(t.result["pots"]) > 1:
            sidepot_hands += 1
    print(f"OK: 500 six-max hands | showdowns={showdowns} folds={folds} "
          f"allin_hands={allin_hands} side-pot_hands={sidepot_hands}")
    print("Chip conservation & non-negative stacks held every hand (incl. side pots).")


if __name__ == "__main__":
    main()
