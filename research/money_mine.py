"""MONEY MINE — degenerate P&L attribution over every logged GTOW hand: what PRINTS, what BURNS.

No solver, no theory, no EV-loss-vs-GTO: raw money flow (AIVAT-weighted = variance-reduced dollars,
raw winnings alongside) grouped by coarse patterns (final street x hero position x terminal shape x
hero hand-class x pot bucket). The output is a CANDIDATE GENERATOR: the fattest burns become lever
candidates, gated downstream by the Analyzer/ladder like everything else (a degenerate still needs an
honest scoreboard, or he cannot know what prints).

CAVEAT baked into the output: sessions span CONFIG ERAS (dead-code eras included) — the per-era block
for the newest big file is the cleaner read; the all-files block is the wide net.

AIVAT-ATTRIBUTION CAVEAT (paper-grounded, arXiv:1612.06915 read 2026-07-06): AIVAT is unbiased over ALL
hands regardless of baseline quality (Thm 1), but the paper does NOT license unbiasedness for sums over
CONDITIONED subsets (our buckets condition on terminal shape/street!) — bucket sums mix true EV with
baseline residue correlated with the conditioning. Treat rankings as LEAD GENERATION, magnitudes as
soft; every lead still passes the normal gate ladder before anything ships.

Usage: python -m research.money_mine        -> data/research_sweep/money_mine.json + printed top tables
"""
from __future__ import annotations

import glob
import json
from collections import defaultdict
from pathlib import Path

from treys import Card, Evaluator

from research.freq_mine import hand_class  # reuse the mined-era hand classifier (board+hole -> class)

OUT = Path("data/research_sweep/money_mine.json")
# bb is detected EMPIRICALLY per file: min |nonzero winnings| = the open-fold SB loss => bb = 2x that.
# (analyze_gtow_hands.py hardcodes BB=50 — measured WRONG for the current era: smallest loss 50 => bb=100.
# The 2026-07-06 first-run numbers were 2x inflated; rankings unaffected, magnitudes halved.)
BB_FALLBACK = 100.0
POT_BUCKETS = ((2.0, "limp/mini"), (8.0, "small"), (25.0, "mid"), (80.0, "big"), (1e9, "huge"))
_EV = Evaluator()


def _hero_hole(h: dict) -> list[str] | None:
    """Hero's hole, or None when not provable. The players list order does NOT identify hero (measured:
    hero index splits 344/307 over showdowns) — so hero is recovered ONLY where the board+winnings sign
    prove it: full-board showdowns, winner's rank vs the winnings sign. Fold-ended hands return None."""
    b, w, ps = h.get("board") or "", h.get("winnings") or 0, h.get("players") or []
    if len(b) != 10 or w == 0 or len(ps) != 2:
        return None
    if h.get("gtow_folded") or (h.get("history") or ["x"])[-1] == "f":
        return None
    board = [Card.new(b[i:i + 2]) for i in range(0, 10, 2)]
    try:
        r0 = _EV.evaluate(board, [Card.new(ps[0]["hole"][:2]), Card.new(ps[0]["hole"][2:])])
        r1 = _EV.evaluate(board, [Card.new(ps[1]["hole"][:2]), Card.new(ps[1]["hole"][2:])])
    except Exception:  # noqa: BLE001
        return None
    if r0 == r1:
        return None
    hero = (0 if r0 < r1 else 1) if w > 0 else (1 if r0 < r1 else 0)
    hole = ps[hero]["hole"]
    return [hole[:2], hole[2:]]


def _terminal_shape(h: dict) -> str:
    """How the hand ENDED, hero-centric — the degenerate cares who blinked and who paid."""
    hist = h.get("history") or []
    last = next((t for t in reversed(hist) if t != "_"), "")
    folded_by_gtow = bool(h.get("gtow_folded"))
    if folded_by_gtow:
        return "villain_folded"
    if last == "f":
        return "hero_folded"
    return "showdown_win" if (h.get("winnings") or 0) > 0 else ("showdown_push" if (h.get("winnings") or 0) == 0 else "showdown_loss")


def _pot_bucket(h: dict, bb: float) -> str:
    pot_bb = abs(h.get("winnings") or 0.0) / bb * 2  # crude: |result| ~ half the contested pot
    return next(lbl for cap, lbl in POT_BUCKETS if pot_bb <= cap)


def _rows(files: list[str]):
    for f in files:
        for line in open(f, encoding="utf-8"):
            try:
                h = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            ps = h.get("players") or []
            if len(ps) != 2 or "hole" not in ps[0]:
                continue
            yield f, h


def _bb_of(path: str) -> float:
    """Empirical bb: the smallest nonzero |winnings| is the open-fold SB loss => bb = 2x."""
    lo = None
    for line in open(path, encoding="utf-8"):
        try:
            w = abs(json.loads(line).get("winnings") or 0.0)
        except Exception:  # noqa: BLE001
            continue
        if w and (lo is None or w < lo):
            lo = w
    return 2.0 * lo if lo else BB_FALLBACK


def mine(files: list[str]) -> dict:
    agg = defaultdict(lambda: [0.0, 0.0, 0])           # key -> [sum_aivat_bb, sum_win_bb, n]
    bbs = {f: _bb_of(f) for f in files}
    for _f, h in _rows(files):
        bb = bbs[_f]
        board = [h["board"][i:i + 2] for i in range(0, len(h.get("board") or ""), 2)]
        hole = _hero_hole(h)                            # exact or None — never a coin-flip guess
        cls = hand_class(board, hole) if (hole and board) else ("preflop" if not board else "n/a")
        key = "|".join([h.get("street") or "?", _terminal_shape(h), cls, _pot_bucket(h, bb)])
        a = agg[key]
        a[0] += (h.get("aivat") or 0.0) / bb
        a[1] += (h.get("winnings") or 0.0) / bb
        a[2] += 1
    return {k: {"aivat_bb": round(v[0], 1), "win_bb": round(v[1], 1), "n": v[2]} for k, v in agg.items()}


def report(tag: str, table: dict, top: int = 15) -> None:
    print(f"\n===== {tag}: TOP BURNS (AIVAT-bb, variance-reduced money) =====")
    for k, v in sorted(table.items(), key=lambda x: x[1]["aivat_bb"])[:top]:
        print(f"{v['aivat_bb']:9.1f} bb  (raw {v['win_bb']:9.1f}, n={v['n']:5d})  {k}")
    print(f"===== {tag}: TOP PRINTERS =====")
    for k, v in sorted(table.items(), key=lambda x: -x[1]["aivat_bb"])[:top]:
        print(f"{v['aivat_bb']:9.1f} bb  (raw {v['win_bb']:9.1f}, n={v['n']:5d})  {k}")


def main() -> None:
    files = sorted(glob.glob("data/sessions/gtow_hands_*.jsonl"))
    if not files:
        print("no session logs found")
        return
    all_t = mine(files)
    biggest = max(files, key=lambda f: Path(f).stat().st_size)
    era_t = mine([biggest])
    report(f"ALL FILES ({len(files)} files, era-mixed wide net)", all_t)
    report(f"NEWEST BIG FILE ({Path(biggest).name} — cleanest single era)", era_t)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"all_files": all_t, "single_era": era_t, "era_file": biggest},
                              indent=1), encoding="utf-8")
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
