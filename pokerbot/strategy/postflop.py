"""Postflop engine: board texture, fold-equity-optimal bet sizing, and the fold model.

The edge: pick the bet size s (fraction of pot) that maximizes EV against the opponent's
fold-frequency-vs-size curve F(s).
  - Bluff EV (per pot):   ev_bluff(s)  = F(s) - s*(1 - F(s))      [win 1 pot on fold, lose s when called]
  - Value EV (per pot):   value_score(s) = F + (1-F)*(e_call*(1+2s) - (1-e_call)*s)   [exact: fold-win + showdown]
Against a GTO opponent F(s) = s/(1+s) and every bluff size is break-even. Profit only comes from
an opponent who deviates — so a *learned* per-size fold model (e.g. from probing Slumbot) is what
turns this into an edge.
"""
from __future__ import annotations

import json

# candidate bet sizes as a fraction of the pot (overbets included to probe/exploit big-size folds)
CANDIDATE_SIZES = [0.33, 0.5, 0.66, 1.0, 1.5, 2.0]

VALUE_EQ = 0.58      # bet for value at/above this equity vs the continuing range
BLUFF_EQ = 0.38      # only bluff below this equity
THIN_BAND = (0.45, 0.58)


def classify_board(board: list[str]) -> dict:
    if len(board) < 3:
        return {"paired": False, "monotone": False, "twotone": False,
                "connected": False, "high": False, "dynamic": False}
    from pokerbot.engine.cards import RANK_ORDER
    ranks = sorted((RANK_ORDER[c[0]] for c in board), reverse=True)
    suits = [c[1] for c in board]
    suit_counts = {s: suits.count(s) for s in set(suits)}
    maxsuit = max(suit_counts.values())
    uniq = sorted(set(ranks))
    spread = max(uniq) - min(uniq) if len(uniq) > 1 else 0
    paired = len(set(ranks)) < len(ranks)
    monotone = maxsuit >= 3
    twotone = maxsuit == 2
    connected = spread <= 4 and len(uniq) >= 2
    high = ranks[0] >= RANK_ORDER["T"]
    dynamic = monotone or twotone or connected            # wet/drawy -> protect, charge draws
    return {"paired": paired, "monotone": monotone, "twotone": twotone,
            "connected": connected, "high": high, "dynamic": dynamic}


def ev_bluff(s: float, F: float) -> float:
    return F - s * (1.0 - F)


def value_score(s: float, F: float, eq: float) -> float:
    """Exact value-bet EV vs size (pot units, P=1): win the pot on a fold, else showdown for P+2sP.
    Replaces the old surrogate (1-F)*s*(2e-1), which dropped the fold-win term F*P and the (1+2s) pot
    geometry -> it under-bet thin value and mis-ranked sizes. (openai_strategy.json fold_equity.ev_value)"""
    e_call = max(0.10, eq - 0.25 * s)        # equity vs the (tightening) calling range; may drop below 0.5
    return F + (1.0 - F) * (e_call * (1.0 + 2.0 * s) - (1.0 - e_call) * s)


class PriorFoldModel:
    """Default opponent fold curve: GTO indifference s/(1+s), nudged by the live read."""

    def __init__(self, fold_to_bet: float = 0.5, confidence: float = 0.0):
        self.ftb = fold_to_bet
        self.conf = confidence

    def fold(self, street: str, s: float) -> float:
        base = s / (1.0 + s)
        base += (self.ftb - 0.5) * 0.5 * self.conf      # exploit the aggregate read
        base += 0.04 * (1.0 - self.conf)                # mild default over-fold assumption
        return max(0.02, min(0.96, base))


class LearnedFoldModel:
    """Per-(street, size) fold frequencies learned from observed responses (e.g. Slumbot)."""

    def __init__(self, table: dict, min_n: int = 6):
        self.table = table              # {street: [[size, fold_rate, n], ...]}
        self.min_n = min_n
        self.prior = PriorFoldModel()

    @classmethod
    def load(cls, path) -> "LearnedFoldModel | None":
        try:
            with open(path, encoding="utf-8") as f:
                return cls(json.load(f))
        except OSError:
            return None

    def fold(self, street: str, s: float) -> float:
        rows = self.table.get(street) or self.table.get("all") or []
        best = None
        for size, fr, n in rows:
            if n >= self.min_n and (best is None or abs(size - s) < abs(best[0] - s)):
                best = (size, fr)
        if best is not None:
            return max(0.02, min(0.98, best[1]))
        return self.prior.fold(street, s)


def _to_amount_for_size(s: float, pot: int, hero_committed: int, hero_stack: int) -> int:
    """Bet sizing when first in / leading (current_bet == 0): bet s*pot, capped at all-in."""
    bet = min(round(s * pot), hero_stack)
    return hero_committed + bet


def pick_bluff_size(pot: int, model, street: str, hero_committed: int, hero_stack: int):
    """Return (to_amount, best_ev, size_frac). best_ev<=0 means no profitable bluff."""
    best = (None, -1e9, 0.0)
    sizes = CANDIDATE_SIZES + [hero_stack / pot] if pot else CANDIDATE_SIZES
    for s in sizes:
        if s <= 0 or s * pot < 1:
            continue
        F = model.fold(street, min(s, 3.0))
        ev = ev_bluff(s, F)
        if ev > best[1]:
            best = (_to_amount_for_size(s, pot, hero_committed, hero_stack), ev, s)
    return best


def pick_value_size(pot: int, model, street: str, hero_committed: int, hero_stack: int, eq: float):
    """Return (to_amount, score, size_frac) maximizing (1-F)*s*(2*e_call-1)."""
    best = (None, -1e9, 0.0)
    sizes = CANDIDATE_SIZES + [hero_stack / pot] if pot else CANDIDATE_SIZES
    for s in sizes:
        if s <= 0 or s * pot < 1:
            continue
        F = model.fold(street, min(s, 3.0))
        sc = value_score(s, F, eq)
        if sc > best[1]:
            best = (_to_amount_for_size(s, pot, hero_committed, hero_stack), sc, s)
    return best
