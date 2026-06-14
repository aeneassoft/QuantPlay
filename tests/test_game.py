"""Stress-test the HU NLHE engine: play many random-but-legal hands, assert invariants."""
from __future__ import annotations

import random

from pokerbot.engine.game import HeadsUpGame


def random_action(la: dict, rng: random.Random):
    opts = []
    if la.get("can_check"):
        opts += ["check", "check"]
    if la.get("can_call"):
        opts += ["call", "call"]
    if la.get("can_fold"):
        opts.append("fold")
    if la.get("can_raise"):
        opts.append("raise")
    action = rng.choice(opts)
    amount = None
    if action == "raise":
        lo, hi = la["raise_min"], la["raise_max"]
        # mostly small raises so hands reach later streets; occasionally shove
        amount = lo if rng.random() < 0.6 else rng.randint(lo, hi)
    return action, amount


def main() -> None:
    rng = random.Random(7)
    start = 10000
    total = 2 * start
    g = HeadsUpGame(starting_stack=start, sb=50, bb=100, seed=7)

    hands = 0
    showdowns = folds = allins = 0
    by_street = {0: 0, 3: 0, 4: 0, 5: 0}
    while hands < 300:
        g.players[0].stack = g.players[1].stack = start  # independent hands
        g.start_hand()
        guard = 0
        while not g.hand_over:
            la = g.legal_actions()
            action, amount = random_action(la, rng)
            g.act(action, amount)
            guard += 1
            assert guard < 2000, "runaway hand"
        # chip conservation must hold every hand
        s0, s1 = g.players[0].stack, g.players[1].stack
        assert s0 + s1 == total, f"chip leak hand {hands}: {s0}+{s1}={s0+s1} != {total}"
        assert s0 >= 0 and s1 >= 0, f"negative stack hand {hands}"
        if g.result["reason"] == "showdown":
            showdowns += 1
        else:
            folds += 1
        if any(p.all_in for p in g.players):
            allins += 1
        by_street[len(g.result["board"])] += 1
        hands += 1

    print(f"OK: played {hands} hands | showdowns={showdowns} folds={folds} allin_hands={allins}")
    print(f"ended on: preflop={by_street[0]} flop={by_street[3]} turn={by_street[4]} river/showdown={by_street[5]}")
    print("All chip-conservation & legality invariants held across every hand.")


if __name__ == "__main__":
    main()
