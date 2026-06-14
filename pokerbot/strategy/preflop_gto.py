"""Serve the solver-distilled preflop GTO table (knowledge_base/ranges/preflop_gto_table.json, built by
extraction/preflop_table.py from 63k PokerBench preflop spots, 88.6% held-out action-match). Same key
scheme as the builder. Step 4a wires the RFI (unopened open/fold) lookup into the 6-max bot; vs-raise /
vs-3bet need the preflop action sequence in obs (Step 4b). Graceful: missing table -> None -> caller falls
back to its heuristic.
"""
from __future__ import annotations

import json
from functools import lru_cache

from pokerbot import config


@lru_cache(maxsize=1)
def _table() -> dict:
    p = config.KNOWLEDGE_DIR / "ranges" / "preflop_gto_table.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except OSError:
        return {}


def rfi(pos: str, hand: str, min_n: int = 3) -> dict | None:
    """RFI (unopened, no limpers) GTO record for (position, 169-hand-class), or None if unknown/too rare.
    Record = {action, n, mix, raise_bb?}. Key matches the builder: '{pos}|0|none|none|0|{hand}'."""
    rec = _table().get(f"{pos}|0|none|none|0|{hand}")
    if rec and rec.get("n", 0) >= min_n:
        return rec
    return None
