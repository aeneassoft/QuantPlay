"""$0 deterministic validation of the POSTFLOP CORSET (pokerbot/strategy/postflop_corset.py).

Part A (unit, hard asserts): vs a big bet the corset FOLDS air (low equity), KEEPS a strong made hand, and — the
draw-aware key — KEEPS a flush DRAW on the flop (it has equity); it is a strict NO-OP for small bets / preflop / non-call.
Part B (real data): on the -94 GTOW run's big-loss postflop hands facing a big bet, the corset must FOLD the air spews
(High Card) and KEEP the coolers (Full House / Flush). Run: python -m tests.test_postflop_corset
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from pokerbot import config
from pokerbot.brain import api
from pokerbot.strategy import postflop_corset as pc

_RIVER = ["Ah", "Kh", "Qh", "5d", "2c"]


def _spot(street, hole, board, pot, to_call):
    return SimpleNamespace(street=street, hero_hole=hole, board=board, pot=pot, to_call=to_call)


def part_a_unit():
    ok = True
    air = _spot("river", ["9s", "4d"], _RIVER, 8500, 5100)         # 9-high air vs a 1.5x overbet -> fold
    d = pc.apply(air, {"action": "call", "amount": 5100})
    print(f"A1 air vs overbet -> {d['action']} (expect fold)"); ok &= d["action"] == "fold"

    nut = _spot("river", ["Jh", "Th"], _RIVER, 8500, 5100)         # royal flush -> high equity -> call
    d = pc.apply(nut, {"action": "call", "amount": 5100})
    print(f"A2 nuts vs overbet -> {d['action']} (expect call)"); ok &= d["action"] == "call"

    # DRAW-AWARE KEY: a flush draw on the FLOP vs a pot bet must be KEPT (made-strength would wrongly fold it)
    draw = _spot("flop", ["Jc", "Tc"], ["Ac", "7c", "2d"], 2000, 1000)   # 2 clubs -> flush draw + overcards
    d = pc.apply(draw, {"action": "call", "amount": 1000})
    eqd = api.equity(["Jc", "Tc"], api.range_top(0.35), ["Ac", "7c", "2d"], iters=600)
    print(f"A3 flush DRAW (flop) vs pot bet -> {d['action']} (expect call; eq={eqd:.2f}, draw-aware kept)")
    ok &= d["action"] == "call"

    small = _spot("river", ["9s", "4d"], _RIVER, 3900, 500)        # 500 into 3400 = small -> defend wide, no over-fold
    d = pc.apply(small, {"action": "call", "amount": 500})
    print(f"A4 air vs SMALL bet -> {d['action']} (expect call, no over-fold)"); ok &= d["action"] == "call"

    bet = _spot("river", ["9s", "4d"], _RIVER, 3400, 0)            # our own bet, not a call -> no-op
    d = pc.apply(bet, {"action": "bet", "amount": 2000})
    print(f"A5 non-call (our bet) -> {d['action']} (expect bet, no-op)"); ok &= d["action"] == "bet"
    return ok


def _cards(s):
    return [s[i:i + 2] for i in range(0, len(s), 2)]


def _recon(history):
    """string history -> (to_call, pot_incl) at the hero's postflop call facing a bet, or None."""
    streets, cur = [], []
    for h in history:
        if h == "_":
            streets.append(cur); cur = []
        else:
            cur.append(h)
    streets.append(cur)
    if len(streets) < 2 or streets[-1][-1:] != ["c"]:             # must end on a CALL
        return None
    pot = 0
    for st in streets[:-1]:
        lv = [int(a[1:]) for a in st if a.startswith("b") and a[1:].isdigit()]
        if lv:
            pot += 2 * max(lv)
    last = [int(a[1:]) for a in streets[-1] if a.startswith("b") and a[1:].isdigit()]
    if not last:
        return None
    B = max(last)
    return B, pot + B


def part_b_realdata():
    p = config.ROOT / "data" / "sessions" / "gtow_hands_1781985733.jsonl"
    if not p.exists():
        print("B: log missing, skip"); return True
    rows = [json.loads(l) for l in open(p, encoding="utf-8")]
    big = [r for r in rows if r.get("aivat", 0) < -100 and r.get("street") in pc._POSTFLOP]
    air_fold = air_n = strong_keep = strong_n = 0
    for r in big:
        rc = _recon(r.get("history", []))
        pls = r.get("players", [])
        if not rc or len(pls) != 2:
            continue
        to_call, pot = rc
        board = _cards(r["board"]); ha, hb = _cards(pls[0]["hole"]), _cards(pls[1]["hole"])
        loser = ha if api.equity(ha, [hb], board, iters=1) < 0.5 else hb
        cat, _ = api.hand_rank(loser, board)
        d = pc.apply(_spot(r["street"], loser, board, pot, to_call), {"action": "call", "amount": to_call})
        print(f"  {r['street']:5} aivat {r['aivat']:7.0f} | loser {loser} {cat:11} | to_call {to_call} pot {pot} -> {d['action']}")
        if cat == "High Card":                                    # air committing a big pot = the genuine spew
            air_n += 1; air_fold += (d["action"] == "fold")
        elif cat in ("Full House", "Flush", "Four of a Kind", "Straight Flush"):  # a cooler -> must be kept (value)
            strong_n += 1; strong_keep += (d["action"] == "call")
    print(f"B: air spews folded {air_fold}/{air_n} | coolers kept {strong_keep}/{strong_n}")
    return air_fold == air_n and strong_keep == strong_n


def main():
    a = part_a_unit()
    print(f"\nPART A (unit): {'PASS' if a else 'FAIL'}\n")
    b = part_b_realdata()
    print(f"\nPART B (real data): {'PASS' if b else 'FAIL'}")
    print(f"\n=== POSTFLOP CORSET TEST: {'PASS' if (a and b) else 'FAIL'} ===")


if __name__ == "__main__":
    main()
