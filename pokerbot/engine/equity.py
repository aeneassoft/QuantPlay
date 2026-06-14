"""Monte-Carlo equity: hand vs hand, hand vs combo-range, hand vs class-range."""
from __future__ import annotations

import random

from pokerbot.engine.cards import expand_class, make_deck
from pokerbot.engine.evaluator import evaluate

_FULL = make_deck()


def equity_vs_hand(hero: list[str], villain: list[str],
                   board: list[str] | None = None, iters: int = 3000,
                   rng: random.Random | None = None) -> float:
    rng = rng or random.Random()
    board = list(board or [])
    dead = set(hero) | set(villain) | set(board)
    deck = [c for c in _FULL if c not in dead]
    need = 5 - len(board)
    if need == 0:                       # river: one exact comparison, not `iters` identical samples
        hs, vs = evaluate(board, hero), evaluate(board, villain)
        return 1.0 if hs < vs else (0.5 if hs == vs else 0.0)
    win = tie = 0
    for _ in range(iters):
        draw = rng.sample(deck, need)
        full = board + draw
        hs, vs = evaluate(full, hero), evaluate(full, villain)
        if hs < vs:
            win += 1
        elif hs == vs:
            tie += 1
    return (win + tie / 2) / iters


def equity_vs_range(hero: list[str], villain_combos: list[tuple[str, str]],
                    board: list[str] | None = None, iters: int = 3000,
                    rng: random.Random | None = None) -> float:
    rng = rng or random.Random()
    board = list(board or [])
    base_dead = set(hero) | set(board)
    vc = [v for v in villain_combos if not (set(v) & base_dead)]
    if not vc:
        return float("nan")
    need = 5 - len(board)
    win = tie = 0
    # RIVER: the board is complete -> ENUMERATE the villain range EXACTLY. Zero variance, no sampling noise,
    # and cheaper when len(vc) < iters. (MC here sampled a finite combo set WITH replacement = pure waste and
    # flipped pot-odds decisions on noise.) Hero's 7-card rank is fixed across villain combos -> eval it once.
    if need == 0:
        hs = evaluate(board, hero)
        for v in vc:
            vs = evaluate(board, list(v))
            if hs < vs:
                win += 1
            elif hs == vs:
                tie += 1
        return (win + tie / 2) / len(vc)
    # turn/flop: Monte-Carlo over (villain combo, run-out). Hoist the base deck out of the loop (was rebuilt
    # from all 52 every iteration); per-combo we only drop the 2 villain cards.
    base_deck = [c for c in _FULL if c not in base_dead]
    n = 0
    for _ in range(iters):
        v = rng.choice(vc)
        deck = [c for c in base_deck if c not in v]
        draw = rng.sample(deck, need)
        full = board + draw
        hs, vs = evaluate(full, hero), evaluate(full, list(v))
        if hs < vs:
            win += 1
        elif hs == vs:
            tie += 1
        n += 1
    return (win + tie / 2) / n


def equity_vs_class_range(hero: list[str], classes: list[str],
                          board: list[str] | None = None, iters: int = 3000,
                          rng: random.Random | None = None) -> float:
    combos: list[tuple[str, str]] = []
    for hc in classes:
        combos.extend(expand_class(hc))
    return equity_vs_range(hero, combos, board, iters, rng)
