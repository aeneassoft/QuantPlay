"""EMPIRICAL test of the calling-station advice (2026-07-01, "auf Nummer sicher") — a decision-level Monte Carlo.

The engine's 6-max league is the WRONG instrument here: its bots barely bluff in multiway pots and its "station" profile
still folds ~58% (a weak-tier penalty overrides the loose call_delta). So we model the opponent the USER described —
"calls down with just a pair or a draw, wants to see cards" — EXPLICITLY and transparently, then play REAL hands
(real cards, real showdowns via the treys evaluator) to measure realized chips.

The station's rule (stated openly, no hidden fitting): facing a bet it CALLS if it holds a made pair-or-better OR a draw
(flush draw / open-or-gutshot straight draw); it folds only pure air. "mega" also calls ace-high / two overcards.
We compare, over thousands of random deals, the hero's realized bb from BETTING vs CHECKING, split by the hero's flop
strength (air = bluff / one pair = thin value / two-pair+ = strong) — a paired A/B on identical deals (CRN). Pure-local.
"""
from __future__ import annotations

import json
import random
import statistics

from pokerbot.engine.evaluator import best_five_name, evaluate

_RANKS = "23456789TJQKA"
_SUITS = "cdhs"
_DECK = [r + s for r in _RANKS for s in _SUITS]
_RVAL = {r: i for i, r in enumerate(_RANKS, start=2)}          # '2'->2 ... 'A'->14

PRE_POT = 6.0            # a single-raised-pot starting point (bb), symmetric dead money
STACK = 100.0           # realistic 100bb effective — so a 3-street overbet stacks off, not an inflated fantasy pot
MADE = ("Pair", "Two Pair", "Three of a Kind", "Straight", "Flush", "Full House",
        "Four of a Kind", "Straight Flush")


def _flush_draw(cards: list) -> bool:
    """Exactly four to a flush (five = a made flush, already caught by pair-or-better)."""
    for s in _SUITS:
        if sum(1 for c in cards if c[1] == s) == 4:
            return True
    return False


def _straight_draw(cards: list) -> bool:
    """A one-card straight draw (gutshot or open-ended) that is NOT already a made straight."""
    ranks = {_RVAL[c[0]] for c in cards}
    if 14 in ranks:
        ranks = ranks | {1}                                    # wheel: treat the ace as low too
    for x in range(1, 15):
        if x in ranks:
            continue
        test = ranks | {x}
        for lo in range(1, 11):
            if all(lo + i in test for i in range(5)):
                return True
    return False


def _has_pair_plus(hole: list, board: list) -> bool:
    return best_five_name(board, hole) in MADE


def _station_calls(hole: list, board: list, mega: bool) -> bool:
    """The transparent station rule: call with a made hand, or a draw (only pre-river a draw is live)."""
    if _has_pair_plus(hole, board):
        return True
    seven = hole + board
    if len(board) < 5 and (_flush_draw(seven) or _straight_draw(seven)):
        return True
    if mega:                                                   # even stickier: ace-high / two overcards "wants to see"
        bh = max(_RVAL[c[0]] for c in board)
        if any(_RVAL[c[0]] == 14 for c in hole) or sum(_RVAL[c[0]] > bh for c in hole) == 2:
            return True
    return False


def _hero_scenario(hole: list, flop: list) -> str:
    name = best_five_name(flop, hole)
    if name == "High Card":
        return "air" if not (_flush_draw(hole + flop) or _straight_draw(hole + flop)) else "draw"
    if name == "Pair":                                        # split by kicker/rank: top pair+ vs a weak/second pair
        top = max(_RVAL[c[0]] for c in flop)
        if hole[0][0] == hole[1][0]:                          # pocket pair: over- vs under-pair to the board
            return "top_pair" if _RVAL[hole[0][0]] >= top else "weak_pair"
        paired = [_RVAL[c[0]] for c in hole if any(c[0] == b[0] for b in flop)]
        return "top_pair" if paired and max(paired) >= top else "weak_pair"
    return "strong"                                            # two pair or better


def _play(hole, villain, board5, bet_line: bool, size: float, barrels: int, mega: bool) -> float:
    """Play one hand out; return the hero's realized bb (chips won − chips put in). CHECK line = check to showdown.
    BET line = hero fires `size`x-pot on up to `barrels` streets; the station calls per its rule or folds."""
    hero_stack = STACK
    pot = PRE_POT                                              # dead money already in the middle (symmetric)
    hero_stack -= PRE_POT / 2                                  # hero's share of the preflop pot
    streets = [board5[:3], board5[:4], board5[:5]]
    vill_stack = STACK - PRE_POT / 2
    folded = False
    if bet_line:
        for i, bd in enumerate(streets):
            if i >= barrels or hero_stack <= 0:
                break
            b = min(size * pot, hero_stack)                    # cap at stack = all-in
            hero_stack -= b
            pot += b
            if _station_calls(villain, bd, mega):
                c = min(b, vill_stack)                         # villain matches up to its stack
                vill_stack -= c
                pot += c
            else:
                folded = True
                break
    if folded:
        hero_stack += pot                                      # uncontested
    else:
        hs, vs = evaluate(board5, hole), evaluate(board5, villain)   # treys: lower = better
        hero_stack += pot if hs < vs else (pot / 2 if hs == vs else 0.0)
    return hero_stack - STACK


def _deal(rng):
    d = _DECK[:]
    rng.shuffle(d)
    return d[:2], d[2:4], d[4:9]                               # hero, villain, board5


def compare(scenario: str, size: float, barrels: int, mega: bool, n: int, seed: int) -> dict:
    """Over n random deals whose hero-flop matches `scenario`, the paired mean realized bb of BET vs CHECK (same deal)."""
    rng = random.Random(seed)
    bet, chk, fold_flop, fold_any = [], [], 0, 0
    tries = 0
    while len(bet) < n and tries < n * 60:
        tries += 1
        hole, vill, board5 = _deal(rng)
        if _hero_scenario(hole, board5[:3]) != scenario:
            continue
        bet.append(_play(hole, vill, board5, True, size, barrels, mega))
        chk.append(_play(hole, vill, board5, False, size, barrels, mega))
        if not _station_calls(vill, board5[:3], mega):
            fold_flop += 1
        if not all(_station_calls(vill, board5[:s], mega) for s in (3, 4, 5)):
            fold_any += 1
    m = len(bet) or 1
    return {"scenario": scenario, "size_x_pot": size, "barrels": barrels, "n": len(bet),
            "bet_bb": round(sum(bet) / m, 2), "check_bb": round(sum(chk) / m, 2),
            "bet_minus_check_bb": round((sum(bet) - sum(chk)) / m, 2),
            "villain_folds_flop_pct": round(100 * fold_flop / m, 1),
            "villain_folds_by_river_pct": round(100 * fold_any / m, 1)}


def run(n=6000) -> dict:
    S = "station (calls any pair/draw)"
    out = {"model": {"station": "calls facing a bet iff it has a made pair-or-better OR a live draw; folds pure air",
                     "mega": "station + also calls ace-high / two overcards"}}
    tests = []
    # 1) THE BLUFF CLAIM — hero has AIR and barrels all 3 streets ("zwanghaft zu Ende bluffen"): bet should LOSE vs check
    tests.append(("BLUFF 3 barrels 0.66x vs station", compare("air", 0.66, 3, False, n, 1)))
    tests.append(("BLUFF flop-only 0.66x vs station", compare("air", 0.66, 1, False, n, 1)))     # one-and-done nuance
    tests.append(("BLUFF 3 barrels 0.66x vs MEGA-station", compare("air", 0.66, 3, True, n, 1)))
    # 2) THIN VALUE — split the pair: TOP pair should value-bet +EV; a WEAK pair betting 3 streets should NOT (pot-control)
    tests.append(("VALUE top-pair 3 streets 0.5x vs station", compare("top_pair", 0.5, 3, False, n, 2)))
    tests.append(("VALUE top-pair 3 streets 0.66x vs station", compare("top_pair", 0.66, 3, False, n, 2)))
    tests.append(("WEAK-pair barrel 3 streets 0.66x vs station", compare("weak_pair", 0.66, 3, False, n, 2)))
    tests.append(("WEAK-pair one bet (flop) 0.5x vs station", compare("weak_pair", 0.5, 1, False, n, 2)))
    # 3) SIZING — hero STRONG (2pair+): overbet vs small bet (inelastic caller -> size up wins more)
    tests.append(("STRONG small 0.5x vs station", compare("strong", 0.5, 3, False, n, 3)))
    tests.append(("STRONG big 1.2x overbet vs station", compare("strong", 1.2, 3, False, n, 3)))
    out["tests"] = [{"label": lab, **res} for lab, res in tests]
    json.dump(out, open("data/coach/station_sim.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for lab, r in tests:
        print(f"  {lab:<42} bet {r['bet_bb']:>7}  check {r['check_bb']:>7}  Δ(bet-check) {r['bet_minus_check_bb']:>7}"
              f"  | vill folds flop {r['villain_folds_flop_pct']}% / by river {r['villain_folds_by_river_pct']}%  (n={r['n']})")
    print("saved data/coach/station_sim.json")
    return out


if __name__ == "__main__":
    run()
