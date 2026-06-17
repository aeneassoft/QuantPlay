"""Loader + lookup for the near-Nash HU 200bb PREFLOP blueprint (built by extraction/preflop_solve.py).

Maps a LIVE preflop decision (is_sb, #raises, villain all-in?) to a blueprint node and samples the solved GTO action
for the hand class. Replaces bot.py's "open top-X% at a fixed 2.5bb / deep_jam_pct" heuristic cascade with a mixed,
size-aware equilibrium.

Trust profile (honest, see NOTES.md): the blueprint is solved at 200bb with a checkdown+IP-realization continuation.
It is MOST accurate for the ALL-IN-DISCIPLINE nodes (4bet/5bet/jam — run-it-out equity is exact) and for the open/
3bet STRUCTURE + mixing; the OOP flat-defense WIDTH carries a realization approximation (the high-quality version =
a real postflop continuation per leaf = the GCP scale-up). Calibrated to 200bb -> gate to deep stacks.
"""
from __future__ import annotations

import json
import os

from pokerbot import config

_BP: dict | None = None
# A/B: POKERB_GRAFT=1 -> the SOLVER-GRAFTED blueprint (real-play see-flop leaves; extraction.preflop_calibrate +
# preflop_solve --leaf-table). Default = the original checkdown blueprint. Grafted is OPEN-only + lean-tree so far,
# so it stays OPT-IN until the GTOW AIVAT A/B (grafted vs checkdown) confirms it (the project's "model gate is not
# enough, measure bb/100" rule).
_FILE = "preflop_blueprint_solvergraft.json" if os.environ.get("POKERB_GRAFT", "0") == "1" else "preflop_blueprint.json"
_PATH = config.KNOWLEDGE_DIR / "ranges" / _FILE

# blueprint action -> cumulative chips THIS player puts in, expressed in bb (None = not a sized raise)
SIZES_BB = {"limp": 1.0, "open": 2.5, "iso": 4.5, "3bet": 10.0, "4bet": 24.0, "5bet": 60.0}
RAISE_ACTIONS = set(SIZES_BB) | {"jam"}


def available() -> bool:
    global _BP
    if _BP is None:
        try:
            _BP = json.loads(_PATH.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001  - missing/corrupt blueprint -> caller falls back to heuristic
            _BP = {}
    return bool(_BP)


def node_for_state(is_sb: bool, raises: int, can_check: bool, villain_allin: bool) -> str | None:
    """Structural map of the live betting state to a blueprint node (None = outside the modeled tree)."""
    if is_sb and raises == 0:
        return "ROOT"                      # SB first-in (unopened)
    if not is_sb and raises == 0 and can_check:
        return "LIMP"                      # BB option after SB limp
    if not is_sb and raises == 1:
        return "OPEN"                      # BB faces SB open
    if is_sb and raises == 1:
        return "ISO"                       # SB faces BB iso-raise of its limp
    if is_sb and raises == 2:
        return "3BET"                      # SB faces BB 3bet
    if not is_sb and raises == 3:
        return "4BET"                      # BB faces SB 4bet
    if is_sb and raises == 4:
        return "JAMSB" if villain_allin else "5BET"   # SB faces BB jam (over 4bet) vs BB 5bet-to-60
    if not is_sb and raises >= 5:
        return "JAMBB"                     # BB faces SB jam (over its 5bet)
    return None


def actions(node: str, hc: str) -> dict | None:
    """The solved action->probability distribution for (node, hand class); None if absent."""
    if not available():
        return None
    return _BP.get(node, {}).get(hc)


def pick(node: str, hc: str, rng) -> tuple[str, dict] | None:
    """Sample a GTO action from the blueprint mixture. Returns (action, dist) or None if out-of-model."""
    dist = actions(node, hc)
    if not dist:
        return None
    acts = list(dist)
    a = rng.choices(acts, weights=[max(0.0, dist[x]) for x in acts])[0]
    return a, dist


if __name__ == "__main__":  # quick smoke
    print("available:", available())
    for nd in ("ROOT", "OPEN", "4BET", "JAMSB"):
        for h in ("AA", "QQ", "AKo", "72o"):
            print(nd, h, actions(nd, h))
