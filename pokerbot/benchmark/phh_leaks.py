"""Cross-check the fold-to-bet leak across MULTIPLE PHH sources (uoftcprg/phh-dataset):
  * pluribus  — superhuman bot (Pluribus seats, and all seats)
  * wsop      — 2023 WSOP $50k PPC final table (elite human pros)
  * famous    — iconic televised high-stakes hands (Ivey/Dwan/Antonius/…)
  * handhq    — anonymised online cash population (sample, 1000NL)

Question: is "over-folds to small/pot bets postflop heads-up" (the Pluribus leak) SPECIFIC to
Pluribus, or a GENERAL human/bot weakness we can exploit? Fold-to-bet only needs actions+sizes, so
it works even when hole cards are hidden ("????"). alpha = to_call/pot is the max unexploitable
fold frequency (HU postflop); fold% > alpha => exploitable over-fold.

Run:  python -m pokerbot.benchmark.phh_leaks
"""
from __future__ import annotations

import glob
import tomllib
from collections import defaultdict

from pokerbot import config

REPO = config.ROOT / "data" / "_phh_repo" / "data"
BUCKETS = [(0.0, 0.45, "small"), (0.45, 0.8, "med"), (0.8, 1.3, "pot"), (1.3, 9.0, "over")]
STREETS = {0: "preflop", 3: "flop", 4: "turn", 5: "river"}
POSTFLOP = ("flop", "turn", "river")


def bucket(s: float) -> str:
    for lo, hi, name in BUCKETS:
        if lo <= s < hi:
            return name
    return "over"


def parse_file(path: str):
    with open(path, "rb") as f:
        d = tomllib.load(f)
    if "actions" in d:                      # single-hand .phh
        yield d
    else:                                   # multi-hand .phhs: {"1":{...}, "2":{...}}
        for v in d.values():
            if isinstance(v, dict) and "actions" in v:
                yield v


def replay_hand(d: dict):
    players = d.get("players", [])
    n = len(players)
    blinds = d.get("blinds_or_straddles", [])
    antes = d.get("antes", [])
    if n < 2 or not blinds:
        return
    street_commit = [0.0] * n
    total_commit = [0.0] * n
    folded = [False] * n
    for i in range(n):
        a = antes[i] if i < len(antes) else 0          # antes = dead money (pot only)
        b = blinds[i] if i < len(blinds) else 0
        total_commit[i] = float(a) + float(b)
        street_commit[i] = float(b)
    board: list[str] = []
    street = "preflop"
    for raw in d.get("actions", []):
        tok = raw.split()
        if tok[0] == "d":
            if tok[1] == "db":
                cards = tok[2]
                board += [cards[i:i + 2] for i in range(0, len(cards), 2)]
                street = STREETS.get(len(board), street)
                street_commit = [0.0] * n
            continue
        if tok[1] == "sm":
            continue
        seat = int(tok[0][1:]) - 1
        verb = tok[1]
        if seat >= n:
            continue
        cur = max(street_commit)
        to_call = cur - street_commit[seat]
        pot = sum(total_commit)
        nact = sum(1 for x in folded if not x)
        name = players[seat] if seat < len(players) else "?"
        yield street, to_call, pot, nact, verb, name
        if verb == "f":
            folded[seat] = True
        elif verb == "cbr" and len(tok) > 2:
            amt = float(tok[2])
            total_commit[seat] += amt - street_commit[seat]
            street_commit[seat] = amt
        elif verb == "cc":
            add = cur - street_commit[seat]
            if add > 0:
                total_commit[seat] += add
                street_commit[seat] = cur


def collect(paths, target=None):
    stats = defaultdict(lambda: [0, 0, 0.0])     # (street, hu, bucket) -> [folds, n, sum_alpha]
    hands = dec = 0
    for p in paths:
        try:
            for d in parse_file(p):
                hands += 1
                for street, to_call, pot, nact, verb, name in replay_hand(d):
                    if target and name != target:
                        continue
                    dec += 1
                    if to_call > 0 and pot > to_call:
                        alpha = to_call / pot
                        b = bucket(to_call / (pot - to_call))
                        st = stats[(street, nact == 2, b)]
                        st[1] += 1
                        st[2] += alpha
                        if verb == "f":
                            st[0] += 1
        except Exception:  # noqa: BLE001
            continue
    return hands, dec, stats


def agg(stats, hu, streets, buckets):
    f = n = sa = 0
    for (street, is_hu, b), (ff, nn, ss) in stats.items():
        if is_hu == hu and street in streets and b in buckets:
            f += ff
            n += nn
            sa += ss
    if not n:
        return None
    return 100 * f / n, 100 * sa / n, n


def report(label, hands, dec, stats):
    print(f"\n### {label}  ({hands} hands, {dec} target decisions)")
    hu = agg(stats, True, POSTFLOP, ("small", "med", "pot"))
    mw = agg(stats, False, POSTFLOP, ("small", "med", "pot"))
    if hu:
        fp, ap, n = hu
        print(f"  POSTFLOP HU  small+pot bets: fold {fp:5.1f}%  vs alpha {ap:5.1f}%  "
              f"gap {fp-ap:+5.1f}  (n={n})  {'<-- over-folds' if fp-ap>5 else ''}")
    else:
        print("  POSTFLOP HU: (no samples)")
    if mw:
        fp, ap, n = mw
        print(f"  POSTFLOP MW  small+pot bets: fold {fp:5.1f}%  vs alpha {ap:5.1f}%  "
              f"gap {fp-ap:+5.1f}  (n={n})  [MW: high fold is tight-correct, not an alpha-leak]")
    for st in POSTFLOP:                       # per-street HU detail
        a = agg(stats, True, (st,), ("small", "med", "pot"))
        if a and a[2] >= 20:
            print(f"    {st:5s} HU: fold {a[0]:5.1f}% vs alpha {a[1]:5.1f}% gap {a[0]-a[1]:+5.1f} (n={a[2]})")


def main() -> None:
    sources = {
        "PLURIBUS (Pluribus seats)": (sorted(glob.glob(str(REPO / "pluribus" / "**" / "*.phh"), recursive=True)), "Pluribus"),
        "PLURIBUS (all seats incl pros)": (sorted(glob.glob(str(REPO / "pluribus" / "**" / "*.phh"), recursive=True)), None),
        "WSOP 2023 final table (pros)": (sorted(glob.glob(str(REPO / "wsop" / "**" / "*.phh"), recursive=True)), None),
        "Famous high-stakes hands": (sorted(glob.glob(str(REPO / "*.phh"))), None),
        "HandHQ online cash 1000NL (sample)": (sorted(glob.glob(str(REPO / "handhq" / "**" / "*.phhs"), recursive=True)), None),
    }
    print("FOLD-TO-BET LEAK ACROSS SOURCES — does 'over-fold to small/pot bets' generalise?")
    for label, (paths, target) in sources.items():
        h, dec, stats = collect(paths, target)
        report(label, h, dec, stats)


if __name__ == "__main__":
    main()
