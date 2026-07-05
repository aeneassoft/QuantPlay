"""$0-ish local SPEND-GATE for the Claude brain (`pokerbot/brain/claude_brain.ClaudeBrain`): drive a HU 200bb table to
a handful of decision points across streets, ask Claude (Opus 4.8, extra-high reasoning) for a DSL program at each, and
print its program + the executed LEGAL action + the ok-flag + token cost.

Verifies BEFORE any GTOW spend: Claude emits VALID engine-grounded DSL (low frac_bad), the actions are sane + legal,
it orchestrates the live solver postflop, and the latency/cost per decision is acceptable. A few Claude calls (~cents).

Run:  python -m research.claude_brain_smoke
"""
from __future__ import annotations

import random

from pokerbot.brain.claude_brain import ClaudeBrain
from pokerbot.brain.format_spot import format_spot, spot_from_table
from pokerbot.engine.table import Table


def hu_spots(n_spots: int = 5, seed: int = 7) -> list:
    """Drive HU 200bb hands with a simple call/check-down-ish line (with occasional small raises) to reach a spread of
    decision points across streets; collect Spots until we have `n_spots`."""
    rng = random.Random(seed)
    spots: list = []
    hand = 0
    while len(spots) < n_spots and hand < 60:
        hand += 1
        t = Table(["Hero", "Villain"], starting_stack=20000, sb=50, bb=100, seed=seed + hand)
        t.start_hand()
        while not t.hand_over and t.to_act is not None:
            spot = spot_from_table(t, t.to_act)
            if spot.street in ("flop", "turn", "river") or (spot.street == "preflop" and rng.random() < 0.35):
                spots.append(spot)
                if len(spots) >= n_spots:
                    break
            la = t.legal_actions()
            if la.get("can_raise") and rng.random() < 0.25:          # some bet/raise lines -> facing-bet spots
                a, amt = "raise", la["raise_min"]
            elif la.get("can_check"):
                a, amt = "check", None
            elif la.get("can_call"):
                a, amt = "call", None                                # keep hands alive to reach later streets
            else:
                a, amt = "fold", None
            t.act(a, amt)
    return spots[:n_spots]


def main() -> None:
    brain = ClaudeBrain(thinking=True, strict=True)
    spots = hu_spots()
    print(f"=== Claude-brain smoke: {len(spots)} HU spots (Opus 4.8, thinking=on, strict DSL) ===\n")
    for idx, spot in enumerate(spots, 1):
        print(f"--- Spot {idx} ({spot.street}) ---")
        print(format_spot(spot))
        res = brain.decide_spot(spot)
        print("\nPROGRAM:\n" + (res.get("program") or "(none)"))
        print(f"\n-> action={res['action']} amount={res['amount']} ok={res['ok']} err={res.get('error')}")
        if res.get("mix"):
            print(f"   mix={res['mix']}")
        print()
    r = brain.report()
    print("=== SUMMARY ===")
    print(f"decisions={r['decisions']} valid={r['valid']} frac_bad={r['frac_bad']} "
          f"called_solve_node={r['called_solve_node']} errors={r['errors']}")
    print(f"tokens in={r['in_tok']} out={r['out_tok']} cache_read={r['cache_tok']}")


if __name__ == "__main__":
    main()
