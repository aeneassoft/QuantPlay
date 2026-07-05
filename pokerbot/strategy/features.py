"""Task #36: blocker + potential-aware hand features for the GTO-floor advisor (#37+) and the hardest-spot
hand-selection (#40/#41). Makes "55% equity" hands no longer fungible: a nut-flush-blocker bluffcatcher, a
vulnerable top pair, and a combo draw are strategically different. Cheap, pure-card logic (treys for the made
hand + manual draw/blocker detection). Run: python -m pokerbot.strategy.features  (self-test)
"""
from __future__ import annotations

from pokerbot.engine.evaluator import best_five_name

RANKS = "23456789TJQKA"


def _ri(c: str) -> int:
    return RANKS.index(c[0])


def _suit_counts(cards) -> dict:
    d: dict = {}
    for c in cards:
        d[c[1]] = d.get(c[1], 0) + 1
    return d


def _straight_outs_compute(rs: frozenset) -> int:
    """The original straight-outs logic over a canonical rank-set (ace-low already added by the caller)."""
    cnt = 0
    for r in set(range(-1, 13)) - rs:
        for lo in range(r - 4, r + 1):
            win = set(range(lo, lo + 5))
            if r in win and all(-1 <= x <= 12 for x in win) and (win - {r}) <= rs:
                cnt += 1
                break
    return cnt


_STRAIGHT_MEMO: dict = {}         # frozenset(ranks) -> outs; domain <= 2^13 entries, exact + tiny


def _straight_outs(rank_idxs) -> int:
    """Number of distinct ranks that complete a 5-straight from the given ranks (8+ outs -> OESD, 4 -> gutshot).
    CLEANUP 2026-07-05 (profiled: 30% of decide() runtime, 10M generator calls): memoized over the canonical
    rank-set — the domain is all subsets of 13 ranks, so the cache is exact and bounded by construction."""
    rs = set(rank_idxs)
    if 12 in rs:                      # ace plays low too
        rs.add(-1)
    key = frozenset(rs)
    hit = _STRAIGHT_MEMO.get(key)
    if hit is None:
        hit = _STRAIGHT_MEMO[key] = _straight_outs_compute(key)
    return hit


_FEATURES_MEMO: dict = {}
_FEATURES_MEMO_MAX = 60_000       # bounded: per-combo-per-board entries; cleared wholesale when full


def hand_features(hole, board) -> dict:
    """Feature dict for (hole, board). Postflop only (board >= 3). Memoized (pure function of the cards;
    profiled at 241k calls / 70 decisions via the range tracker's per-combo advisor queries). Returns a
    fresh shallow copy so a caller mutating the dict can never corrupt the cache."""
    key = (tuple(hole), tuple(board))
    hit = _FEATURES_MEMO.get(key)
    if hit is not None:
        return dict(hit)
    if len(_FEATURES_MEMO) >= _FEATURES_MEMO_MAX:
        _FEATURES_MEMO.clear()
    result = _hand_features_compute(hole, board)
    _FEATURES_MEMO[key] = result
    return dict(result)


def _hand_features_compute(hole, board) -> dict:
    cards = list(hole) + list(board)
    made = best_five_name(board, hole)
    sc_all = _suit_counts(cards)
    sc_board = _suit_counts(board)
    flush_suit = max(sc_all, key=sc_all.get) if sc_all else None
    made_flush = bool(flush_suit) and sc_all.get(flush_suit, 0) >= 5
    flush_draw = (not made_flush) and any(v == 4 for v in sc_all.values())
    backdoor_flush = (not made_flush) and (not flush_draw) and any(v == 3 for v in sc_all.values())
    # nut-flush blocker: hold the Ace of a suit that is live on the board (>=2) -> blocks villain nut flush/draw
    nut_flush_blocker = (not made_flush) and any(_ri(c) == 12 and sc_board.get(c[1], 0) >= 2 for c in hole)
    so = _straight_outs([_ri(c) for c in cards])
    made_straight = "Straight" in made
    oesd = (not made_straight) and so >= 2
    gutshot = (not made_straight) and so == 1
    top_board = max((_ri(c) for c in board), default=-1)
    overcards = sum(1 for c in hole if _ri(c) > top_board)
    # coarse made tier (for selection): nut-ish / strong / medium / weak-pair / air
    m = made.lower()
    if any(k in m for k in ("quad", "full", "flush", "straight", "three")):
        tier = "strong"
    elif "two pair" in m:
        tier = "strong"
    elif "pair" in m:
        tier = "medium"          # one pair (refine by top/over below if needed)
    else:
        tier = "air"
    return {
        "made": made, "tier": tier,
        "made_flush": made_flush, "flush_draw": flush_draw, "backdoor_flush": backdoor_flush,
        "nut_flush_blocker": nut_flush_blocker,
        "made_straight": made_straight, "oesd": oesd, "gutshot": gutshot,
        "overcards": overcards,
        "has_draw": flush_draw or oesd or gutshot,
    }


def main() -> None:
    tests = [
        (["As", "Ks"], ["Qs", "7s", "2d"]),   # nut flush draw + nut-flush blocker (As) + overcards
        (["9h", "8h"], ["7c", "6d", "2s"]),   # OESD
        (["Jd", "Td"], ["9c", "2h", "5s"]),   # gutshot + 2 overcards
        (["Ac", "Ad"], ["Ks", "7h", "2c"]),   # overpair (strong-ish)
        (["Kh", "Qh"], ["Kd", "7s", "2c"]),   # top pair
        (["5c", "4c"], ["Ah", "Kd", "9s"]),   # air
    ]
    for hole, board in tests:
        print(f"{hole} {board} -> {hand_features(hole, board)}")


if __name__ == "__main__":
    main()
