"""Loader for the CFR-computed push/fold blueprint (true GTO short-stack ranges)."""
from __future__ import annotations

import json

from pokerbot import config
from pokerbot.engine.cards import normalize_class

_pf: dict | None = None


def _load() -> dict:
    global _pf
    if _pf is None:
        p = config.KNOWLEDGE_DIR / "cfr" / "preflop_pushfold.json"
        _pf = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    return _pf


def available() -> bool:
    return bool(_load())


def pushfold(stack_bb: float, hand_class: str) -> dict | None:
    """Return {'jam': p, 'call': p} for the nearest solved stack, or None if unavailable."""
    pf = _load()
    if not pf:
        return None
    stacks = sorted(int(k) for k in pf)
    nearest = min(stacks, key=lambda x: abs(x - stack_bb))
    return pf[str(nearest)].get(normalize_class(hand_class))
