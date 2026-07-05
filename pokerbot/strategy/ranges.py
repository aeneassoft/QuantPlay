"""Heads-Up preflop ranges + opponent-range estimation.

Ranges are defined as combo-weighted percentile bands on the preflop-strength model
(tuned to reasonable HU GTO frequencies for a ~100bb raise-or-fold game), and refined by
the GTO grids extracted from Modern Poker Theory where a confident match exists.
"""
from __future__ import annotations

import json

from pokerbot import config
from pokerbot.engine.cards import all_hand_classes, expand_class, normalize_class
from pokerbot.strategy import preflop_strength as ps

# --- HU spot ranges (fraction of all hands), ~100bb -------------------------
SB_OPEN_FRAC = 0.84          # BTN/SB open-raises the strongest 84%
BB_3BET_VALUE_FRAC = 0.13    # BB value-3bets the top 13%
BB_DEFEND_FRAC = 0.66        # BB continues (call+3bet) ~66% vs a small open
SB_4BET_VALUE_FRAC = 0.075
SB_CALL_3BET_FRAC = 0.34
BB_CALL_4BET_FRAC = 0.06
BLUFF_BAND = (0.40, 0.60)    # middling hands used as polarized 3bet/4bet bluffs


def sb_open() -> set[str]:
    return ps.range_top(SB_OPEN_FRAC)


def bb_3bet_value() -> set[str]:
    return ps.range_top(BB_3BET_VALUE_FRAC)


def bb_defend() -> set[str]:
    return ps.range_top(BB_DEFEND_FRAC)


def bb_call_open() -> set[str]:
    return bb_defend() - bb_3bet_value()


def sb_4bet_value() -> set[str]:
    return ps.range_top(SB_4BET_VALUE_FRAC)


def sb_call_3bet() -> set[str]:
    return ps.range_top(SB_CALL_3BET_FRAC) - sb_4bet_value()


def bb_call_4bet() -> set[str]:
    return ps.range_top(BB_CALL_4BET_FRAC)


def bluff_band() -> set[str]:
    lo, hi = BLUFF_BAND
    return {hc for hc in all_hand_classes() if lo <= ps.percentile(hc) < hi}


def push_fraction(eff_bb: float) -> float:
    """Heads-up SB open-shove width by effective stack (push/fold zone)."""
    if eff_bb <= 6:
        return 0.70
    if eff_bb <= 8:
        return 0.55
    if eff_bb <= 10:
        return 0.45
    if eff_bb <= 12:
        return 0.38
    return 0.30


def call_shove_fraction(eff_bb: float) -> float:
    """How wide BB calls an SB open-shove (tighter than the shove)."""
    return max(0.18, push_fraction(eff_bb) * 0.62)


def combos_for_classes(classes, dead) -> list[tuple[str, str]]:
    """DETERMINISM FIX (2026-07-05, measured): `classes` is usually a SET of class strings (range_top) —
    iterating it directly made the combo-list order PYTHONHASHSEED-dependent, so MC equity paired the same
    rng draws with different villain combos per process -> mixed-strategy boundary decisions flipped between
    otherwise-identical runs (caught by a run-to-run stress diff: 4/140 actions; PYTHONHASHSEED=0 -> 0 diffs).
    sorted() pins ONE canonical order for every consumer (tracker priors, equity ranges, exports, live)."""
    dead_cards = set(dead)
    out: list[tuple[str, str]] = []
    for hc in sorted(classes):
        for combo in expand_class(hc):
            if not (set(combo) & dead_cards):
                out.append(combo)
    return out


# --- Extracted GTO grids from Modern Poker Theory (optional refinement) -----
_extracted: list[dict] | None = None


def extracted_ranges() -> list[dict]:
    global _extracted
    if _extracted is None:
        p = config.RANGES_DIR / "ranges_grids.json"
        _extracted = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
    return _extracted


def match_grid(keywords: list[str], stack_bb: float | None = None) -> dict | None:
    """Best-effort match of an extracted grid to a spot by label keywords + stack."""
    best, best_score = None, 0
    for g in extracted_ranges():
        label = (g.get("label", "") + " " + g.get("villain_action", "")).lower()
        score = sum(1 for k in keywords if k.lower() in label)
        if stack_bb and g.get("stack_bb"):
            if abs(g["stack_bb"] - stack_bb) <= 5:
                score += 1
        if score > best_score:
            best, best_score = g, score
    return best if best_score >= 2 else None


def grid_action(grid: dict, hand_class: str) -> tuple[str, float] | None:
    """Look up a hand's action in an extracted grid (pure first, then mixed)."""
    hc = normalize_class(hand_class)
    for h in grid.get("pure", []):
        if normalize_class(h["hand"]) == hc:
            return h["action"], 100.0
    for h in grid.get("mixed", []):
        if normalize_class(h["hand"]) == hc:
            acts = sorted(h.get("actions", []), key=lambda a: -a.get("freq", 0))
            if acts:
                return acts[0]["action"], acts[0].get("freq", 0)
    return None  # not present => fold in these charts
