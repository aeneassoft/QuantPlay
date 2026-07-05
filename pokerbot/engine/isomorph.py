"""Suit isomorphism (Johanson 2007 §2.5.1, lossless): two boards differing only by a suit relabeling define
IDENTICAL games — up to 24 solve-cache entries per strategic situation collapse into one canonical entry.

Scope of validity in OUR pipeline (why this is exact, not approximate): the resolver hands TexasSolver
CLASS-level range strings (AKs/AKo/AA — suit-invariant by construction, see range_tracker.emit) and navigates
by bet-size labels (suit-free). The ONLY suit-bearing inputs are the board and hero's hole cards at the final
strategy lookup — both are mapped through the same permutation here. Gated POKERB_ISO_CACHE (default OFF).

Canonical form: of all 24 suit permutations, the one whose permuted board (order preserved — streets matter)
is lexicographically minimal. Deterministic, involution-free, O(24·|board|).
"""
from __future__ import annotations

from itertools import permutations

SUITS = "shdc"
_ALL_PERMS = [dict(zip(SUITS, p)) for p in permutations(SUITS)]


def canonical_board(board: list[str]) -> tuple[list[str], dict]:
    """(canonical board, the suit map used). The map applies to ANY card via apply_map (hero's hole)."""
    best_board, best_map = None, None
    for m in _ALL_PERMS:
        cand = [c[0] + m[c[1]] for c in board]
        key = "".join(cand)
        if best_board is None or key < "".join(best_board):
            best_board, best_map = cand, m
    return best_board, best_map


def apply_map(card: str, suit_map: dict) -> str:
    return card[0] + suit_map[card[1]]


def main() -> None:
    """Self-test: canonicalization is (a) idempotent, (b) constant across all 24 relabelings of a board."""
    import random
    rng = random.Random(7)
    deck = [r + s for r in "23456789TJQKA" for s in SUITS]
    for _ in range(500):
        board = rng.sample(deck, rng.choice([3, 4, 5]))
        canon, m = canonical_board(board)
        canon2, _ = canonical_board(canon)
        assert canon2 == canon, ("not idempotent", board)
        for perm in _ALL_PERMS:                        # every relabeling must reach the SAME canonical form
            relabeled = [c[0] + perm[c[1]] for c in board]
            c3, _ = canonical_board(relabeled)
            assert c3 == canon, ("not invariant", board, relabeled)
    print("isomorph self-test: 500 boards x 24 relabelings -> canonical form idempotent + invariant. OK")


if __name__ == "__main__":
    main()
