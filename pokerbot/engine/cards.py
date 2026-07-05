"""Card primitives and 169-hand-class notation.

Cards are 2-char strings: rank in '23456789TJQKA', suit in 'shdc'  (e.g. 'As', 'Td', '2c').
This matches the format the treys evaluator expects, so no conversion table is needed.
"""
from __future__ import annotations

import random

RANKS = "23456789TJQKA"
SUITS = "shdc"
RANK_ORDER = {r: i for i, r in enumerate(RANKS)}  # 2->0 .. A->12


def rank_value(rank: str) -> int:
    return RANK_ORDER[rank]


def make_deck() -> list[str]:
    return [r + s for r in RANKS for s in SUITS]


class Deck:
    """A shuffled deck that can exclude already-known cards."""

    def __init__(self, exclude: list[str] | None = None, rng: random.Random | None = None):
        self.rng = rng or random.Random()
        ex = set(exclude or [])
        self.cards = [c for c in make_deck() if c not in ex]
        self.rng.shuffle(self.cards)

    def deal(self, n: int = 1) -> list[str]:
        return [self.cards.pop() for _ in range(n)]


def hand_class(c1: str, c2: str) -> str:
    """Map two cards to canonical class notation: 'AA', 'AKs', 'AKo' (high card first)."""
    r1, s1 = c1[0], c1[1]
    r2, s2 = c2[0], c2[1]
    if RANK_ORDER[r1] < RANK_ORDER[r2]:
        r1, r2, s1, s2 = r2, r1, s2, s1
    if r1 == r2:
        return r1 + r2
    return r1 + r2 + ("s" if s1 == s2 else "o")


def normalize_class(hc: str) -> str:
    """Normalize loose notation like 'kqs', 'AKo', 'TT' to canonical form."""
    hc = hc.strip()
    if len(hc) == 2:  # pair
        a, b = hc[0].upper(), hc[1].upper()
        return a + b
    a, b, suit = hc[0].upper(), hc[1].upper(), hc[2].lower()
    if RANK_ORDER[a] < RANK_ORDER[b]:
        a, b = b, a
    return a + b + suit


def all_hand_classes() -> list[str]:
    """All 169 starting-hand classes."""
    classes: list[str] = []
    rl = list(RANKS)[::-1]  # A..2
    for i, hi in enumerate(rl):
        for j, lo in enumerate(rl):
            if i == j:
                classes.append(hi + lo)            # pair
            elif i < j:
                classes.append(hi + lo + "s")      # suited
            else:
                classes.append(lo + hi + "o")      # offsuit (high first)
    # de-dup while preserving order
    seen: set[str] = set()
    out = []
    for c in classes:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def expand_class(hc: str) -> list[tuple[str, str]]:
    """Expand a hand class into its concrete 2-card combos."""
    hc = normalize_class(hc)
    if len(hc) == 2:  # pair -> 6 combos
        r = hc[0]
        return [(r + SUITS[i], r + SUITS[j])
                for i in range(4) for j in range(i + 1, 4)]
    hi, lo, suit = hc[0], hc[1], hc[2]
    if suit == "s":  # 4 suited combos
        return [(hi + s, lo + s) for s in SUITS]
    # offsuit -> 12 combos
    return [(hi + s1, lo + s2) for s1 in SUITS for s2 in SUITS if s1 != s2]
