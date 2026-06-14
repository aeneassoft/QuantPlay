"""7-card hand evaluation via treys. Lower score = stronger hand."""
from __future__ import annotations

from treys import Card, Evaluator

_EV = Evaluator()


def _t(cards: list[str]) -> list[int]:
    return [Card.new(c) for c in cards]


def evaluate(board: list[str], hole: list[str]) -> int:
    """Score a hand. board+hole must total >= 5 cards. Lower is better (1 = royal flush)."""
    return _EV.evaluate(_t(board), _t(hole))


def hand_rank_name(score: int) -> str:
    return _EV.class_to_string(_EV.get_rank_class(score))


def best_five_name(board: list[str], hole: list[str]) -> str:
    return hand_rank_name(evaluate(board, hole))
