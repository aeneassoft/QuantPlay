"""Convert the PokerBench 6-max SPINE (HF `RZ412/PokerBench`, instruction→optimal-action) into DSL decision examples.
PokerBench is already in BB units (SB 0.5 / BB 1) → `output` amounts ARE big-blinds → map straight to decide(a, size_bb).

These are the SFT WARM-START bulk (solver-optimal 6-max decisions). Completions are thin (decide() + a marker) — the
program-of-thought DEPTH (api-calls + reasoning) comes from the structured sources + the Phase-3 frontier rationales +
Phase-4 self-play (where spots are fully structured). Format note: PokerBench prose ≠ our `format_spot`, but a strong
LLM generalizes across phrasings of the same spot, and self-play trains on `format_spot` directly (no hard skew).
"""
from __future__ import annotations

import re

from dataset.schema import make_example

_OUT = re.compile(r"(fold|check|call|bet|raise|all[\s-]?in)\s*([0-9]*\.?[0-9]+)?", re.IGNORECASE)


def parse_output(out: str) -> dict | None:
    m = _OUT.search(out or "")
    if not m:
        return None
    a = m.group(1).lower().replace("all in", "allin").replace("all-in", "allin")
    sz = float(m.group(2)) if m.group(2) else None
    return {"action": a, "size_bb": sz}


def build(limit: int | None = None, streaming: bool = True):
    from datasets import load_dataset
    ds = load_dataset("RZ412/PokerBench", split="train", streaming=streaming)
    n = 0
    for r in ds:
        act = parse_output(r.get("output"))
        spot = (r.get("instruction") or "").strip()
        if not act or not spot:
            continue
        size = f", {act['size_bb']}" if act["size_bb"] is not None else ""
        comp = f"# Solver-optimal 6-max decision (PokerBench).\ndecide({act['action']!r}{size})"
        yield make_example("pokerbench", spot, comp, action=act, type_="decision",
                           meta={"raw_output": r.get("output")})
        n += 1
        if limit and n >= limit:
            break
