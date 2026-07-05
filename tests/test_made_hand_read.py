"""$0 deterministic test of the LLM<->engine made-hand WIRING (format_spot.INCLUDE_MADE_HAND).

The grounded trigger (research/glm_local_probe.py A/B): the GLM mis-reads its own made hand in NL on coordinated boards
(a full house -> "two pair", a flopped straight -> "air", a weak pair -> "a flush"). format_spot now injects the EXACT
engine read (api.hand_rank) postflop. This test locks: (1) ON -> the prompt carries the correct engine category on the
3 spots the GLM actually mis-read; (2) OFF and preflop -> NO line (byte-identical fallback). Run: python -m tests.test_made_hand_read
"""
from __future__ import annotations

from pokerbot.brain import format_spot as fs
from pokerbot.brain.format_spot import Spot


def _spot(street, board, hole, to_call=0):
    return Spot(street=street, board=board, bb=100, hero_seat=0, hero_pos="BTN", hero_hole=hole,
                pot=1160, to_call=to_call, n_active=2)


# (hole, board, the category the engine must surface == the one the GLM mis-read away)
_MISREADS = [
    (["7d", "2d"], ["7c", "7s", "6h", "3c", "3d"], "Full House"),   # GLM read "two pair" -> checked the boat
    (["4d", "8c"], ["5c", "7c", "6h"], "Straight"),                 # GLM read "air" -> checked a flopped straight
    (["7h", "Qd"], ["7c", "Jc", "Jd", "2c"], "Two Pair"),          # GLM read "trip 7s" -> wrong-tight fold
]


def main():
    ok = True
    fs.INCLUDE_MADE_HAND = True
    for hole, board, cat in _MISREADS:
        text = fs.format_spot(_spot("river" if len(board) == 5 else "flop", board, hole))
        present = f"Made hand (engine): {cat}" in text
        print(f"ON  {hole} {board} -> expect '{cat}' in prompt: {present}")
        ok &= present

    fs.INCLUDE_MADE_HAND = False                                    # control: OFF -> byte-identical (no line)
    off = "Made hand (engine)" not in fs.format_spot(_spot("river", _MISREADS[0][1], _MISREADS[0][0]))
    print(f"OFF -> no made-hand line: {off}"); ok &= off

    fs.INCLUDE_MADE_HAND = True                                     # control: preflop has no board -> no line even ON
    pre = "Made hand (engine)" not in fs.format_spot(_spot("preflop", [], ["As", "Kd"]))
    print(f"ON preflop -> no made-hand line: {pre}"); ok &= pre
    fs.INCLUDE_MADE_HAND = True                                     # leave at the production default

    print(f"\n=== MADE-HAND WIRING TEST: {'PASS' if ok else 'FAIL'} ===")


if __name__ == "__main__":
    main()
