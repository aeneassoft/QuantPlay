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


def equity_vs_weighted_range(hero: list[str], combo_weights: dict, board: list[str] | None = None,
                             iters: int = 3000, rng: random.Random | None = None) -> float:
    """Hero equity vs a WEIGHTED villain range {combo(tuple of two card-strs): weight}. The weighted analogue of
    equity_vs_range, for the per-combo Bayesian range tracker (combos carry the tracker's action-consistent
    weight, not a flat 1). RIVER -> exact weighted enumeration (zero variance); pre-river -> MC with the villain
    combo SAMPLED proportional to weight. Dead-card-filtered (hero+board); NaN if the range is empty."""
    rng = rng or random.Random()
    board = list(board or [])
    base_dead = set(hero) | set(board)
    items = [(v, w) for v, w in combo_weights.items() if w > 0 and not (set(v) & base_dead)]
    if not items:
        return float("nan")
    need = 5 - len(board)
    if need == 0:                                   # river: exact weighted enumeration (hero rank fixed)
        hs = evaluate(board, hero)
        win = tie = tot = 0.0
        for v, w in items:
            vs = evaluate(board, list(v))
            if hs < vs:
                win += w
            elif hs == vs:
                tie += w
            tot += w
        return (win + tie / 2) / tot if tot > 0 else float("nan")
    combos = [v for v, _ in items]
    weights = [w for _, w in items]
    base_deck = [c for c in _FULL if c not in base_dead]
    win = tie = n = 0
    for _ in range(iters):
        v = rng.choices(combos, weights=weights, k=1)[0]   # weighted combo draw (vs uniform in equity_vs_range)
        deck = [c for c in base_deck if c not in v]
        full = board + rng.sample(deck, need)
        hs, vs = evaluate(full, hero), evaluate(full, list(v))
        if hs < vs:
            win += 1
        elif hs == vs:
            tie += 1
        n += 1
    return (win + tie / 2) / n if n else float("nan")


def equity_vs_class_range(hero: list[str], classes: list[str],
                          board: list[str] | None = None, iters: int = 3000,
                          rng: random.Random | None = None) -> float:
    combos: list[tuple[str, str]] = []
    for hc in classes:
        combos.extend(expand_class(hc))
    return equity_vs_range(hero, combos, board, iters, rng)
