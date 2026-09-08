"""Spot-level leak analysis of a per-hand GTO Wizard log (data/sessions/gtow_hands_*.jsonl, written by the
patched tools/gtow_client/src/main.py). Answers: WHERE does the bot lose AIVAT vs GTO Wizard? Buckets by final
street, flop texture, gtow-folded, line shape; + the worst-loss hands. This turns an aggregate run into an
actionable diagnostic (test specific spots -> fix the part that bleeds). Run: python -m extraction.analyze_gtow_hands [path]
"""
from __future__ import annotations

import glob
import json
import statistics
import sys
from collections import defaultdict

from pokerbot import config

BB = 100.0  # GTO Wizard HUNL: blinds=[100,50] (API GameModel.blinds, BB zuerst; gtowizard.py _gsr-Fixture) -> bb=100.
            # WHY: der alte Wert 50 war die SB -> alle bb/100 hier um Faktor 2 ueberhoeht (V10_FAKTEN A8/E10, 2026-09-07).


def _newest():
    fs = sorted(glob.glob(str(config.DATA_DIR / "sessions" / "gtow_hands_*.jsonl")))
    return fs[-1] if fs else None


def _texture(board: str | None) -> str:
    cards = [board[i:i + 2] for i in range(0, len(board or ""), 2)]
    if len(cards) < 3:
        return "no-flop"
    ranks, suits = [c[0] for c in cards[:3]], [c[1] for c in cards[:3]]
    if len(set(ranks)) < 3:
        return "paired"
    if len(set(suits)) == 1:
        return "monotone"
    if len(set(suits)) == 2:
        return "twotone"
    return "rainbow"


def _bbm(xs):
    m = sum(xs) / len(xs) / BB * 100.0
    se = (statistics.pstdev(xs) / len(xs) ** 0.5 / BB * 100.0) if len(xs) > 1 else 0.0
    return m, se


def _bucket(rows, keyfn, label):
    d = defaultdict(list)
    for r in rows:
        if r.get("aivat") is not None:
            d[keyfn(r)].append(r["aivat"])
    print(f"\nby {label} (AIVAT bb/100, sorted worst->best):")
    for k, xs in sorted(d.items(), key=lambda kv: sum(kv[1]) / len(kv[1])):
        m, _ = _bbm(xs)
        print(f"  {str(k):14s}: {m:+7.1f}  (n={len(xs)}, {100*len(xs)/max(1,len(rows)):.0f}%)")


def main() -> None:
    p = sys.argv[1] if len(sys.argv) > 1 else _newest()
    if not p:
        print("no gtow_hands log found (run a logged GTO Wizard test first)")
        return
    rows = [json.loads(x) for x in open(p, encoding="utf-8").read().splitlines() if x.strip()]
    av = [r["aivat"] for r in rows if r.get("aivat") is not None]
    print(f"=== {p} : {len(rows)} hands ({len(av)} w/ aivat) ===")
    if av:
        m, se = _bbm(av)
        print(f"OVERALL AIVAT: {m:+.1f} +/- {se:.1f} bb/100")
    _bucket(rows, lambda r: r.get("street"), "final street reached")
    _bucket(rows, lambda r: _texture(r.get("board")), "flop texture")
    _bucket(rows, lambda r: "gtow_FOLDED" if r.get("gtow_folded") else "contested", "GTO Wizard folded?")
    # line shape: # of betting rounds with action (rough), via '_' separators in the history
    _bucket(rows, lambda r: f"{sum(1 for a in (r.get('history') or []) if a == '_')}_rounds", "rounds w/ betting")
    worst = sorted([r for r in rows if r.get("aivat") is not None], key=lambda r: r["aivat"])[:12]
    print("\nworst-AIVAT hands (board | history | hole(s) | aivat):")
    for r in worst:
        holes = "/".join(str(pl.get("hole")) for pl in (r.get("players") or []))
        print(f"  {str(r.get('board')):12s} | {str(r.get('history'))[:38]:38s} | {holes:14s} | {r['aivat']:.0f}")


if __name__ == "__main__":
    main()
