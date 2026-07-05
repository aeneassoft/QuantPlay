"""7-card hand evaluation via treys. Lower score = stronger hand."""
from __future__ import annotations

from collections import Counter

from treys import Card, Evaluator

_EV = Evaluator()

RANK_ORDER = "23456789TJQKA"


# CLEANUP 2026-07-05 (profiled: 645k evaluate calls / 70 decisions, 1.3M Card.new conversions): both are
# pure -> memoized. The card table is complete after 52 entries; the evaluate memo is bounded + cleared
# wholesale when full (combos repeat heavily within a decision's range walks).
_CARD_INTS: dict = {}
_EVAL_MEMO: dict = {}
_EVAL_MEMO_MAX = 120_000


def _t(cards: list[str]) -> list[int]:
    out = []
    for c in cards:
        i = _CARD_INTS.get(c)
        if i is None:
            i = _CARD_INTS[c] = Card.new(c)
        out.append(i)
    return out


def evaluate(board: list[str], hole: list[str]) -> int:
    """Score a hand. board+hole must total >= 5 cards. Lower is better (1 = royal flush)."""
    key = (tuple(board), tuple(hole))
    hit = _EVAL_MEMO.get(key)
    if hit is None:
        if len(_EVAL_MEMO) >= _EVAL_MEMO_MAX:
            _EVAL_MEMO.clear()
        hit = _EVAL_MEMO[key] = _EV.evaluate(_t(board), _t(hole))
    return hit


def hand_rank_name(score: int) -> str:
    return _EV.class_to_string(_EV.get_rank_class(score))


def best_five_name(board: list[str], hole: list[str]) -> str:
    return hand_rank_name(evaluate(board, hole))


def _one_pair_class(pair_rank: str, board_ranks: list[str]) -> str:
    """Top pair = pair rank at/above the highest board rank (includes overpairs)."""
    top_board = max(RANK_ORDER.index(r) for r in board_ranks)
    return "top-pair" if RANK_ORDER.index(pair_rank) >= top_board else "pair"


def made_class(board: list[str], hole: list[str]) -> str:
    """air / pair / top-pair / two-pair+ / monster at the board-so-far.

    The SINGLE taxonomy shared by the GTOW frequency/raise mining (research/freq_mine.py,
    research/raise_mine.py) and the range tracker's raise narrowing — the mined class mixes are only
    valid calibration if both sides classify identically. Built on treys best_five_name, DEMOTED when
    the board makes the hand for us (board pair counted as 'Pair', a double-paired board counted as
    'Two Pair', board trips, a 5-card board that plays alone): those are air/one-pair in the poker sense.
    """
    if len(board) < 3:
        return "preflop"
    name = best_five_name(board, hole)
    b_ranks = [c[0] for c in board]
    h_ranks = [c[0] for c in hole]
    board_count, total_count = Counter(b_ranks), Counter(b_ranks + h_ranks)
    if name == "High Card":
        return "air"
    if name == "Pair":
        pair_rank = next(r for r in total_count if total_count[r] >= 2)
        if pair_rank not in h_ranks:                       # the pair lives on the board
            return "air"
        return _one_pair_class(pair_rank, b_ranks)
    if name == "Two Pair":
        pairs = sorted((r for r in total_count if total_count[r] == 2),
                       key=RANK_ORDER.index, reverse=True)[:2]
        hero_made = [r for r in pairs if r in h_ranks]
        if not hero_made:                                  # double-paired board plays
            return "air"
        if len(hero_made) == 1:                            # e.g. Qx on KKQ72: really one pair
            return _one_pair_class(hero_made[0], b_ranks)
        return "two-pair+"
    if name == "Three of a Kind":
        trip_rank = next(r for r in total_count if total_count[r] >= 3)
        return "air" if board_count[trip_rank] >= 3 else "two-pair+"
    if name == "Four of a Kind":
        quad_rank = next(r for r in total_count if total_count[r] >= 4)
        if board_count[quad_rank] >= 4:            # board quads: everyone has them, hole = a kicker (also
            return "air"                           # covers 4-card boards where the 5-card check can't run)
    # Straight and better: on a complete board, demote to air when the board alone plays.
    if len(board) == 5 and evaluate(board, hole) == evaluate(board, []):
        return "air"
    return "two-pair+" if name == "Straight" else "monster"
