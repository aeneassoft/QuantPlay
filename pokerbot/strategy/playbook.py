"""Exploit playbook = a COLD-START prior for the adaptive engine.

The LLM pre-computed a bounded exploit directive for a grid of opponent profiles x spots
(knowledge_base/exploit/playbook*.jsonl). Against an opponent we have NOT profiled live yet, we look up the
nearest profile and apply its directive as a BOUNDED, confidence-gated nudge that FADES as live reads
accumulate (so it can never override solid live evidence, and worst case ~= the baseline).

This is also the LIVE channel for the future LLM strategist: a live LLM proposal uses the SAME directive
format -> the SAME `directive_to_nudge` -> the SAME bounded application path in adaptive.py. So wiring the
static playbook now also builds the seam the LLM plugs into later (see docs/INTEGRATION.md).
"""
from __future__ import annotations

import json

from pokerbot import config

_FILES = ["playbook_opus_coarse.jsonl", "playbook.jsonl"]   # opus first (higher quality), then the haiku grid
# normalization ranges for the nearest-profile distance (playbook units: vpip in %, others as in the grid)
_NORM = {"vpip": (10.0, 70.0), "fold_to_cbet": (0.2, 0.8), "af": (0.5, 4.5)}

# directive action -> (channel, call-more/bluff-more/value-wider sign). Shared by static playbook + live LLM.
_MAP = {
    "bluff_more":        ("bluff", +1),
    "value_bet_thinner": ("value", +1),
    "call_wider":        ("foldcatch", +1),   # facing a bet: call MORE
    "fold_more":         ("foldcatch", -1),   # facing a bet: call LESS (fold more)
    "raise_more":        ("bluff", +1),   # raise/aggress more -> the (wired) bluff/aggression channel
}


def _z(stat: str, v: float) -> float:
    lo, hi = _NORM[stat]
    return (float(v) - lo) / (hi - lo)


def directive_to_nudge(directive: dict | None) -> dict:
    """Map a bounded exploit directive -> small signed nudges per channel, scaled by its OWN confidence.
    Returns {} for an unknown/empty directive. Used by BOTH the static playbook and the live LLM."""
    if not directive:
        return {}
    adj = directive.get("adjust", {}) or {}
    ch = _MAP.get(adj.get("action"))
    if not ch:
        return {}
    delta = max(-0.3, min(0.3, float(adj.get("freq_delta", 0.0) or 0.0)))
    conf = max(0.0, min(1.0, float(directive.get("confidence", 0.5) or 0.5)))
    channel, sign = ch
    return {channel: sign * abs(delta) * conf}


class Playbook:
    def __init__(self, files: list[str] | None = None) -> None:
        self.by_spot: dict[tuple[str, str], list[dict]] = {}     # (street, facing) -> entries
        self._cache: dict[tuple, dict | None] = {}
        base = config.KNOWLEDGE_DIR / "exploit"
        for name in (files or _FILES):
            fp = base / name
            if not fp.exists():
                continue
            for line in fp.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except Exception:  # noqa: BLE001
                    continue
                ctx = e.get("ctx", {})
                self.by_spot.setdefault((ctx.get("street"), ctx.get("facing")), []).append(e)
        self.available = bool(self.by_spot)

    def lookup(self, opp_stats: dict, street: str, facing: str, position: str | None = None,
               stack_bb: float | None = None) -> dict | None:
        """Nearest-profile directive for this spot (opp_stats in PLAYBOOK units: vpip %, fold_to_cbet 0..1,
        af ratio). Hard-matches (street, facing); ranks profiles by normalized L2 distance. Cached."""
        bucket = self.by_spot.get((street, facing))
        if not bucket:
            return None
        ck = (street, facing, position,
              round(opp_stats.get("vpip", 35) / 5.0), round(opp_stats.get("fold_to_cbet", 0.5) * 10),
              round(opp_stats.get("af", 1.5) * 2), None if stack_bb is None else round(stack_bb / 40.0))
        if ck in self._cache:
            return self._cache[ck]
        best, bestd = None, 1e9
        for e in bucket:
            if position and e.get("ctx", {}).get("hero_position") not in (None, position):
                continue
            o = e.get("opp", {})
            d = 0.0
            for s in ("vpip", "fold_to_cbet", "af"):
                if s in o and s in opp_stats:
                    d += (_z(s, o[s]) - _z(s, opp_stats[s])) ** 2
            if stack_bb is not None and "stack_bb" in e.get("ctx", {}):
                d += ((e["ctx"]["stack_bb"] - stack_bb) / 160.0) ** 2
            if d < bestd:
                bestd, best = d, e
        out = best.get("directive") if best else None
        if len(self._cache) < 16384:
            self._cache[ck] = out
        return out


_SHARED: Playbook | None = None


def shared() -> Playbook:
    """Process-wide singleton so many AdaptiveExploiter instances share ONE parsed playbook (cheap)."""
    global _SHARED
    if _SHARED is None:
        _SHARED = Playbook()
    return _SHARED
