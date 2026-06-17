"""The engine-as-API — the typed primitive library the LLM brain calls in a program-of-thought (docs/DATASET_SPEC.md).
THIN wrappers over existing, tested engine code (no logic duplication): equity, the Mathematics-of-Poker formulas,
board texture, hand strength, and a legal-action coercer. The brain emits Python calling THESE; `executor.py` runs it.

Design: math is done by code (no LLM-arithmetic errors), legality by the engine (truth). Everything is deterministic
given a seed. Strategy lookups (preflop blueprint / solver-freq advisor / exploit model) are exposed best-effort and
return None where 6-max coverage is not yet built — the brain must handle None.
"""
from __future__ import annotations

import random

from pokerbot.engine.equity import equity_vs_range, equity_vs_weighted_range, equity_vs_class_range
from pokerbot.engine.evaluator import evaluate, best_five_name
from pokerbot.engine.cards import hand_class
from pokerbot.strategy.postflop import classify_board
from knowledge_base.math import formulas as F
from knowledge_base.math.postflop_formulas import *  # noqa: F401,F403 — engine-verified post-flop toolkit, callable as api.<fn>
try:                                                  # engine-verified STRATEGY formulas (optional until generated)
    import knowledge_base.math.strategy_formulas as _strategy_formulas
    globals().update({_n: getattr(_strategy_formulas, _n) for _n in getattr(_strategy_formulas, "__all__", [])})
except Exception:  # noqa: BLE001
    pass

# ---------------------------------------------------------------- equity
def equity(hero: list, villain, board: list | None = None, iters: int | None = None,
           seed: int | None = 0) -> float:
    """Hero equity (0..1) vs a villain range. `villain` may be a list of class strings (['AA','AKs']), a list of
    combo tuples ([('As','Ks')]), or a weighted dict ({('As','Ks'): 0.6}). Board = community cards (or None preflop).
    `iters` defaults to the ACTIVE compute mode's equity_iters (the accuracy<->time lever; brain/modes.py)."""
    if iters is None:
        from pokerbot.brain import modes
        iters = modes.current().equity_iters
    rng = random.Random(seed)
    if isinstance(villain, dict):
        return equity_vs_weighted_range(hero, villain, board, iters=iters, rng=rng)
    if villain and isinstance(villain[0], (tuple, list)):
        return equity_vs_range(hero, [tuple(v) for v in villain], board, iters=iters, rng=rng)
    return equity_vs_class_range(hero, list(villain), board, iters=iters, rng=rng)


def range_top(frac: float) -> list:
    """Top-`frac` of starting hands as 169-class strings — a COMPACT continuing-range prior so the brain emits
    `api.range_top(0.2)` instead of a long literal list (a much shorter program = it fits the RL token budget, and the
    downstream read-branch stays salient). Wraps `preflop_strength.range_top`; safe fallback if unavailable."""
    frac = max(0.02, min(1.0, float(frac)))
    try:
        from pokerbot.strategy import preflop_strength as ps
        r = sorted(ps.range_top(frac))
        if r:
            return r
    except Exception:  # noqa: BLE001
        pass
    base = ["AA", "KK", "QQ", "JJ", "TT", "99", "88", "77", "66", "55", "44", "33", "22", "AKs", "AQs", "AJs", "ATs",
            "KQs", "KJs", "QJs", "JTs", "AKo", "AQo", "KQo"]
    return base[:max(3, round(len(base) * frac / 0.4))]


# ---------------------------------------------------------------- Mathematics of Poker (formulas.py)
def required_equity(to_call: float, pot: float) -> float:
    """Pot-odds break-even equity to call: to_call / (pot + to_call)."""
    if to_call <= 0:
        return 0.0
    return to_call / (pot + to_call)


def pot_odds(to_call: float, pot: float):
    """(ratio, required_equity) via formulas.compute_pot_odds (pot=P already in the middle, bet faced=to_call)."""
    return F.compute_pot_odds(pot, to_call, to_call)


def mdf(bet: float, pot: float) -> float:
    """Minimum defense frequency vs a bet of `bet` into `pot`."""
    return F.minimum_defense_frequency(pot, bet)


def spr(effective_stack: float, pot: float) -> float:
    return F.compute_spr(effective_stack, pot)


def outs_equity(outs: int, cards_to_come: int = 2) -> float:
    return F.outs_to_equity_rule_2_and_4(outs, cards_to_come)


# ---------------------------------------------------------------- texture + made hand
def board_texture(board: list) -> dict:
    """{'paired','monotone','twotone','connected','high','dynamic'} bools."""
    return classify_board(board) if board else {}


def hand_rank(hole: list, board: list):
    """(made_hand_name, strength) where strength in (0,1], higher=better (1 - treys/7462)."""
    if not board:
        return ("preflop", None)
    r = evaluate(board, list(hole))
    return (best_five_name(board, list(hole)), round(1.0 - r / 7462.0, 4))


def hand_class_of(hole: list) -> str:
    return hand_class(hole[0], hole[1])


# ---------------------------------------------------------------- strategy lookups (best-effort; None if uncovered)
def preflop_mix(spot) -> dict | None:
    """The solved preflop GTO action-mix for hero's class at this node, or None if outside the (200bb HU) blueprint.
    NOTE: 6-max preflop coverage is dataset-driven; this is best-effort until the 6-max ranges are wired."""
    try:
        from pokerbot.strategy import preflop_blueprint as pbp
        if not pbp.available():
            return None
        raises = sum(1 for a in spot.line if a["action"] in ("bet", "raise"))
        node = pbp.node_for_state(spot.hero_pos in ("BTN", "SB"), raises,
                                  spot.legal.get("can_check", False), False)
        return pbp.actions(node, hand_class_of(spot.hero_hole)) if node else None
    except Exception:  # noqa: BLE001
        return None


def solver_freq(hole: list, board: list, role: str, street: str) -> float | None:
    """Advisor P(bet) for this hand/board, or None if the advisor is unavailable for that street."""
    try:
        from pokerbot.strategy import advisor as A
        return A.p_bet(hole, board, role, street) if A.available(street) else None
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------- legality (the engine = truth)
def legalize(spot, action: str, size_bb: float | None = None):
    """Coerce (action, size_bb) to a LEGAL (action, amount_chips) for `spot`. amount = total bet in CHIPS for
    bet/raise; None for fold/check/call/all-in. Falls back safely (check>call>fold) for an illegal request."""
    a = (action or "").lower()
    L = spot.legal
    if a in ("bet", "raise", "allin", "all-in"):
        if not L.get("can_raise"):
            return ("check", None) if L.get("can_check") else (("call", None) if L.get("can_call") else ("fold", None))
        if a in ("allin", "all-in") or size_bb is None:
            return ("allin", None)
        target = int(round(size_bb * spot.bb))
        target = max(L.get("raise_min") or target, min(target, L.get("raise_max") or target))
        return ("raise", target)
    if a == "fold":
        return ("fold", None) if L.get("can_fold") else ("check", None)
    if a == "call":
        return ("call", None) if L.get("can_call") else ("check", None)
    if a == "check":
        return ("check", None) if L.get("can_check") else (("call", None) if L.get("can_call") else ("fold", None))
    return ("check", None) if L.get("can_check") else (("call", None) if L.get("can_call") else ("fold", None))
