"""Preflop hand-strength model: all-in equity of each of the 169 classes vs a random hand.

Computed once via Monte Carlo and cached to data/preflop_strength.json. Provides a
combo-weighted percentile used to build position/spot ranges in a principled way.
"""
from __future__ import annotations

import json
import random

from pokerbot import config
from pokerbot.engine.cards import all_hand_classes, expand_class, normalize_class
from pokerbot.engine.equity import equity_vs_class_range

CACHE = config.DATA_DIR / "preflop_strength.json"
ALL_CLASSES = all_hand_classes()
COMBOS = {hc: len(expand_class(hc)) for hc in ALL_CLASSES}
TOTAL_COMBOS = sum(COMBOS.values())  # 1326

_strength: dict[str, float] | None = None
_percentile: dict[str, float] | None = None


def _compute(iters: int = 4000) -> dict[str, float]:
    rng = random.Random(0)
    out: dict[str, float] = {}
    for hc in ALL_CLASSES:
        combo = list(expand_class(hc)[0])
        out[hc] = round(equity_vs_class_range(combo, ALL_CLASSES, iters=iters, rng=rng), 4)
    return out


def _ensure() -> None:
    global _strength, _percentile
    if _strength is not None:
        return
    if CACHE.exists():
        _strength = json.loads(CACHE.read_text(encoding="utf-8"))
    else:
        _strength = _compute()
        CACHE.write_text(json.dumps(_strength, indent=2), encoding="utf-8")
    # combo-weighted percentile: fraction of all combos strictly weaker than this class
    _percentile = {}
    for hc, eq in _strength.items():
        weaker = sum(COMBOS[o] for o, v in _strength.items() if v < eq)
        _percentile[hc] = weaker / TOTAL_COMBOS


def strength(hc: str) -> float:
    _ensure()
    return _strength[normalize_class(hc)]


def percentile(hc: str) -> float:
    """0..1, higher = stronger (fraction of random hands this class beats)."""
    _ensure()
    return _percentile[normalize_class(hc)]


def range_top(fraction: float) -> set[str]:
    """The strongest `fraction` of all hands (combo-weighted), as a set of classes."""
    _ensure()
    cutoff = 1.0 - fraction
    return {hc for hc, pct in _percentile.items() if pct >= cutoff}


def ranked_classes() -> list[str]:
    _ensure()
    return sorted(ALL_CLASSES, key=lambda h: _strength[h], reverse=True)


if __name__ == "__main__":
    _ensure()
    ranked = ranked_classes()
    print(f"computed strength for {len(_strength)} classes -> {CACHE.name}")
    print("strongest:", [(h, _strength[h]) for h in ranked[:6]])
    print("weakest:  ", [(h, _strength[h]) for h in ranked[-6:]])
    for h in ("AA", "AKs", "QJs", "T9s", "A2o", "72o"):
        print(f"  {h}: equity={strength(h):.3f}  percentile={percentile(h):.2f}")
    print("top 15% size (classes):", len(range_top(0.15)))
