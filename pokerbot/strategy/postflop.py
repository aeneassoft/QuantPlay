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
import os

# candidate bet sizes as a fraction of the pot (overbets included to probe/exploit big-size folds)
CANDIDATE_SIZES = [0.33, 0.5, 0.66, 1.0, 1.5, 2.0]

# GTO-mode (POKERB_ONTREE, DEFAULT ON since the A/B): snap postflop BETS to GTOW's discrete size tree so the spot
# stays on GTOW's solution (off-tree variable sizing was the main SRP "UNSOLVED" driver). A/B (1000 hands each +
# duplicate.py): more on-tree + GTO-score 50.7->53.1 + EV-loss-vs-GTO 22.7->21.2, at NO realized-EV cost
# (-59.2 vs -60.6 bb/100, inside the noise) -> SHIPPED as default. Set POKERB_ONTREE=0 to restore the variable
# exploit-sizing (the edge vs very leaky fields; trades GTO-alignment for exploitation).
ONTREE = os.environ.get("POKERB_ONTREE", "1") == "1"
TREE_SIZES = (0.33, 0.5, 0.75, 1.0, 1.25)            # standard GTOW tree fractions (drops 0.66/1.5/2.0)


def snap_to_tree(bet_chips: int, pot: int) -> int:
    """Round a bet (chips) to the nearest GTOW-tree pot-fraction; returns the input if pot/bet non-positive."""
    if pot <= 0 or bet_chips <= 0:
        return bet_chips
    frac = bet_chips / pot
    best = min(TREE_SIZES, key=lambda s: abs(s - frac))
    return max(1, round(best * pot))

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


# Flop c-bet (frequency, primary size as pot fraction) by board class, hero IN POSITION as the PFR.
# From knowledge_base/postflop/openai_strategy.json ("Flop c-bet frequency & size"). Frequencies match our
# solver cache (~80% dry/high vs ~55% monotone); sizes are small range-bets on dry, bigger on dynamic.
FLOP_CBET = {
    "High_dry":     (0.80, 0.33),
    "Low_dry":      (0.65, 0.33),
    "High_dynamic": (0.70, 0.50),
    "Low_dynamic":  (0.55, 0.50),
    "Paired":       (0.75, 0.33),
    "Monotone":     (0.55, 0.50),
}


def flop_class(tex: dict) -> str:
    """Map classify_board() flags to one of the 6 openai_strategy flop categories."""
    if tex["monotone"]:
        return "Monotone"
    if tex["paired"]:
        return "Paired"
    drawy = tex["twotone"] or tex["connected"]
    if drawy:
        return "High_dynamic" if tex["high"] else "Low_dynamic"
    return "High_dry" if tex["high"] else "Low_dry"


def cbet_policy(board: list[str], ip: bool = True) -> tuple[float, float]:
    """Texture-conditioned flop c-bet (frequency, size as pot fraction). OOP: ~15% less often, sized up.
    Turn/river boards still classify, but callers should prefer street-specific logic there."""
    f, s = FLOP_CBET[flop_class(classify_board(board))]
    if not ip:
        f = max(0.35, min(0.85, f - 0.15))
        s = max(s, 0.50)
    return f, s


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
    """Per-(street, size) fold frequencies learned from observed responses (e.g. Slumbot).

    With `max_dist` set, a learned rate is used ONLY when the queried size is within that distance of a
    measured spot — otherwise it falls back to the GTO prior. This makes a SPARSE, spot-specific table
    (e.g. the few significant Pluribus over-fold points) deviate from GTO *only where a leak was actually
    measured* and play the indifference curve everywhere else, so the exploit is confined to proven spots
    rather than generalized blindly. (A dense curve like Slumbot's leaves max_dist=None = nearest-always.)"""

    def __init__(self, table: dict, min_n: int = 6, max_dist: float | None = None):
        self.table = table              # {street: [[size, fold_rate, n], ...]}
        self.min_n = min_n
        self.max_dist = max_dist
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
        if best is not None and (self.max_dist is None or abs(best[0] - s) <= self.max_dist):
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
    """Return (to_amount, score, size_frac) maximizing the exact value_score(s) (fold-win + showdown)."""
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
