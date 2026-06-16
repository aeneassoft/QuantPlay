"""Short-deck (6+) hand evaluator — SELF-CONTAINED, separate from the 52-card treys path (NO NLHE risk; nothing
here is imported by the 52-card engine). Uses TexasSolver's bundled rank dict
(tools/.../card5_dic_sorted_shortdeck.txt, C(36,5)=376,992 rows). Verified 2026-06-15:
  LOWER value = better hand; variant = flush > full house, A-6-7-8-9 wheel, and **TRIPS > STRAIGHT**
  (the rarity-adjusted short-deck rule — confirm vs the target room before any COMPETITIVE use; fine for the demo).
7-card hand = best (lowest) over the C(7,5)=21 five-card subsets. 6-A ranks only — a 2-5 card raises KeyError
(the no-2-5-leakage guard)."""
from __future__ import annotations

import itertools
from functools import lru_cache

from pokerbot import config

SD_RANKS = "6789TJQKA"          # 9 ranks (deck)
SD_SUITS = "cdhs"
SD_DECK = [r + s for r in SD_RANKS for s in SD_SUITS]   # 36 cards
# dict CANONICAL KEY = the 5 cards sorted as PLAIN ASCII STRINGS — verified empirically: the flush
# {6c,8c,Tc,Qc,Ac} is keyed '6c-8c-Ac-Qc-Tc' (ASCII '6'<'8'<'A'<'Q'<'T', NOT poker-rank order; 'T'=84 is the
# highest ASCII among rank chars). Hand STRENGTH (incl. the ace-low A-6-7-8-9 wheel) lives in the dict VALUE.
_DICT: dict | None = None
_PATH = (config.ROOT / "tools" / "TexasSolver-v0.2.0-Windows" / "resources" / "compairer"
         / "card5_dic_sorted_shortdeck.txt")


def _load() -> dict:
    global _DICT
    if _DICT is None:
        d = {}
        with open(_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                cards, val = line.split(",")
                d[cards] = int(val)
        _DICT = d
    return _DICT


def available() -> bool:
    return _PATH.exists()


def _key5(cards5) -> str:
    """Canonical dict key: the 5 cards sorted as plain strings (ASCII), '-'-joined (matches the dict exactly)."""
    return "-".join(sorted(cards5))


@lru_cache(maxsize=200000)
def rank5(cards5_tuple) -> int:
    """Short-deck rank of a 5-card hand (LOWER = better). cards5_tuple = a tuple of 5 two-char cards."""
    return _load()[_key5(list(cards5_tuple))]


def rank7(cards7) -> int:
    """Best (lowest) short-deck rank over the 21 five-card subsets of a 5-7 card hand."""
    cards7 = list(cards7)
    if len(cards7) == 5:
        return rank5(tuple(cards7))
    return min(rank5(c) for c in itertools.combinations(cards7, 5))


def best_hand_rank(hole, board) -> int:
    """Short-deck rank of hero's best 5-card hand from hole+board (LOWER = better)."""
    return rank7(list(hole) + list(board))


def normalized_strength(hole, board) -> float:
    """0..1 strength (1 = best), for advisor features — analogous to the 52-card `1 - rank/7462`."""
    n = len(_load())
    return 1.0 - best_hand_rank(hole, board) / n
