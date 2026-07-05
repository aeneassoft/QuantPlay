"""Deterministic POSTFLOP CORSET — the coupled flop->turn->river commitment discipline, WIRED from theory already in the
repo (api.equity [draw-aware], api.required_equity, range_top). NOT new theory and NOT a river-only alarm: the streets
are ONE coupled decision (a bloated flop with a weak hand IS the bad river), so the same equity-vs-price bound spans all
three. The -94 vs GTOW was committing big pots with low-equity hands ACROSS streets; the big COOLERS (a full house
losing to a bigger one) are HIGH-equity and are therefore correctly UNTOUCHED.

Why ONE gate works on every street: `api.equity` is DRAW-AWARE (it runs the board out), so on the flop/turn a real draw
KEEPS its equity (never folded) while a no-equity high card is cut; on the river equity == made-hand strength. The
defense math `required_equity = B/(P+2B)` is the engine truth. Applied AFTER the brain decides, in GLMBrainAgent._decide.
$0, deterministic. (Plan A / 2a: a line-aware solver range will sharpen the `range_top` estimate below.)
"""
from __future__ import annotations

from pokerbot.brain import api

GATE_BET_FRAC = 0.70             # gate ONLY a call vs a bet >= 70% of the PRE-bet pot (the spew zone); small -> defend wide
CALL_MARGIN = 0.03              # keep indifferent bluff-catchers in (anti-over-fold; a prior, RL/solver tunes)
_EQ_ITERS = 600                 # MC-equity precision (cheap; deterministic via the api's fixed seed)
_POSTFLOP = ("flop", "turn", "river")


def _value_frac(bet: float, p_pre: float) -> float:
    """Value-heavy continuing-range estimate (top fraction of hands), TIGHTER vs bigger bets (more polarized). A prior;
    plan A's line-aware solver range will replace this estimate."""
    x = bet / max(p_pre, 1.0)
    return min(0.50, max(0.12, 0.50 - 0.15 * x))


def apply(spot, decision: dict) -> dict:
    """Bound the brain's POSTFLOP action: vs a LARGE bet, fold a call whose DRAW-AWARE equity vs a value range is below
    the required equity. No-op for small bets / preflop / non-call -> draws and value are never over-folded."""
    if getattr(spot, "street", None) not in _POSTFLOP or not isinstance(decision, dict):
        return decision
    if decision.get("action") != "call":                       # the over-call is the spew we bound (a bet-cap is a later add)
        return decision
    B = float(getattr(spot, "to_call", 0) or 0)
    P = float(getattr(spot, "pot", 0) or 0)                    # spot.pot INCLUDES the villain's bet (brain convention)
    p_pre = P - B
    if B <= 0 or p_pre <= 0 or B < GATE_BET_FRAC * p_pre:      # no bet / small bet -> MDF defends wide -> trust the brain
        return decision
    req = api.required_equity(B, P)                            # = B/(p_pre+2B), engine truth
    eq = float(api.equity(spot.hero_hole, api.range_top(_value_frac(B, p_pre)), spot.board, iters=_EQ_ITERS))
    if eq < req - CALL_MARGIN:                                 # too little equity to call a big bet -> FOLD the spew
        return {"action": "fold", "amount": 0}
    return decision
