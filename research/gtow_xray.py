"""The Fable-5-audit X-RAY: turn the -72 vs GTO Wizard from a number into a MAP, with ZERO new compute, by
decomposing an existing per-hand GTOW log (data/sessions/gtow_hands_*.jsonl) into CONTRIBUTIONS (mean x share) by
street, by preflop won/lost, and by largest-bet-faced bucket. The audit's point: localize WHERE the loss is
generated before switching engines. Run: python -m extraction.gtow_xray [path]
"""
from __future__ import annotations

import glob
import json
import sys
from collections import defaultdict

from pokerbot import config

BB = 50.0  # GTO Wizard HUNL bb


def _newest():
    fs = sorted(glob.glob(str(config.DATA_DIR / "sessions" / "gtow_hands_*.jsonl")))
    return fs[-1] if fs else None


def _maxbet(hist):
    return max((int(t[1:]) for t in (hist or []) if t and t[0] == "b" and t[1:].isdigit()), default=0)


def _contrib(rows, keyfn, label):
    """For each bucket: mean aivat (bb/100), n, share, and CONTRIBUTION = mean*share (its slice of the total)."""
    d = defaultdict(list)
    tot = [r["aivat"] for r in rows if r.get("aivat") is not None]
    N = len(tot)
    overall = sum(tot) / N / BB * 100 if N else 0.0
    for r in rows:
        if r.get("aivat") is not None:
            d[keyfn(r)].append(r["aivat"])
    print(f"\n{label}  (overall {overall:+.1f} bb/100, n={N})")
    print(f"  {'bucket':18s}{'mean bb/100':>12s}{'n':>7s}{'share':>7s}{'CONTRIBUTION':>14s}")
    rowsout = []
    for k, xs in d.items():
        mean = sum(xs) / len(xs) / BB * 100
        share = len(xs) / N
        rowsout.append((mean * share, k, mean, len(xs), share))
    for contrib, k, mean, n, share in sorted(rowsout):   # most-negative contribution first
        print(f"  {str(k):18s}{mean:>+12.1f}{n:>7d}{share:>6.0%}{contrib:>+14.1f}")


def main():
    p = sys.argv[1] if len(sys.argv) > 1 else _newest()
    if not p:
        print("no gtow_hands log"); return
    rows = [json.loads(x) for x in open(p, encoding="utf-8").read().splitlines() if x.strip()]
    print(f"=== X-RAY of {p} ({len(rows)} hands) ===")
    print("CONTRIBUTION = mean(bb/100) x share = how much of the total loss this bucket GENERATES (they sum to overall).")

    _contrib(rows, lambda r: r.get("street") or "?", "by FINAL STREET")

    def pf_kind(r):
        if r.get("street") != "preflop":
            return "postflop"
        w = r.get("winnings") or 0
        h = r.get("history") or []
        if any(t == "a" or (t and t[0] == "b" and int(t[1:] or 0) >= 19000) for t in h):
            return "preflop allin"
        return "preflop WON" if w > 0 else ("preflop LOST" if w < 0 else "preflop chop")
    _contrib(rows, pf_kind, "by PREFLOP outcome (the dominant-volume bucket)")

    def size_bucket(r):
        mb = _maxbet(r.get("history"))
        if mb == 0:
            return "no bet (checked)"
        if mb < 300:
            return "<3bb"
        if mb < 1000:
            return "3-10bb"
        if mb < 3000:
            return "10-30bb"
        if mb < 10000:
            return "30-100bb"
        return ">=100bb (jam)"
    _contrib(rows, size_bucket, "by LARGEST BET in the hand (chips; stack=20000)")


if __name__ == "__main__":
    main()
