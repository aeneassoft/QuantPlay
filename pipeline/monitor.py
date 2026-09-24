"""The training MONITOR — closes the PC-hub active-learning loop (Phase 3). It reads the pod's GTO-anchored eval
report, identifies Qwen's WEAK CLUSTERS (street × position × SPR × texture), and emits targets so
pipeline/frontier_loop.py grows the dataset exactly where the model is weakest. The cluster taxonomy is SHARED with
eval-time tagging via `cluster_of(spot)`, so the pod's report and the PC's targeting speak the same language.
Per docs/plans/QWEN_6MAX_PLAN.md.
"""
from __future__ import annotations

from pokerbot.brain import api
from pokerbot.brain.format_spot import Spot


def _spr_bucket(spot: Spot) -> str:
    eff = min((s["stack"] for s in spot.seats if not s["folded"]), default=spot.bb)
    s = api.spr(eff, spot.pot or spot.bb)
    return "spr_low" if s < 3 else ("spr_mid" if s <= 7 else "spr_high")


def _texture_tag(board: list) -> str:
    if not board:
        return "preflop"
    t = api.board_texture(board)
    if t.get("paired"):
        return "paired"
    if t.get("monotone"):
        return "monotone"
    if t.get("twotone") or t.get("connected") or t.get("dynamic"):
        return "wet"
    return "dry"


def cluster_of(spot: Spot) -> tuple:
    """The canonical weak-cluster key for a spot — used BOTH at eval-tagging (pod) and frontier-targeting (PC)."""
    return (spot.street, spot.hero_pos, _spr_bucket(spot), _texture_tag(spot.board))


def weak_clusters(records, k: int = 10, min_n: int = 20):
    """records = [{'cluster': key, 'score': float, 'n': int}] — score = bb/100 or accuracy (higher = better).
    Aggregate by cluster, return the k WEAKEST (lowest mean score) clusters with >= min_n samples:
    [(cluster_key, mean_score, n), ...]."""
    agg: dict = {}
    for r in records:
        c = r.get("cluster")
        key = tuple(c) if isinstance(c, (list, tuple)) else c
        tot, n = agg.get(key, (0.0, 0))
        cnt = r.get("n", 1)
        agg[key] = (tot + r["score"] * cnt, n + cnt)
    ranked = sorted(((key, tot / n, n) for key, (tot, n) in agg.items() if n >= min_n), key=lambda x: x[1])
    return ranked[:k]


def spots_in_clusters(spot_pool, target_clusters):
    """Yield spots from `spot_pool` whose cluster_of falls in `target_clusters` — the frontier_loop's input feed."""
    targets = {tuple(c) for c in target_clusters}
    for spot in spot_pool:
        if cluster_of(spot) in targets:
            yield spot
