"""Mine Pluribus's EXPLOITABLE leaks from the 10,000 hand histories.

Goal is not GTO-similarity — it is MONEY. Since all hole cards are revealed, we can measure
exactly how Pluribus *responds* (it is non-adaptive, so any leak is a permanent, safe edge):

  * Fold-to-bet by bet-size x street x (heads-up vs multiway), compared to the maximum
    unexploitable fold frequency alpha = to_call/pot  (MDF complement). fold% >> alpha =>
    Pluribus OVER-folds there => bluff it. fold% << alpha => it's sticky => value-bet, don't bluff.
  * Its own bet-size footprint (the action-abstraction fingerprint + off-tree gaps to attack).
  * River calling-range strength (does it bluff-catch light or tight?).

Writes knowledge_base/exploit/pluribus_leaks.json (consumed by the exploiter) + prints a report.
Run:  python -m pokerbot.benchmark.pluribus_leaks
"""
from __future__ import annotations

import glob
import json
from collections import Counter, defaultdict

from pokerbot import config
from pokerbot.benchmark.pluribus_bench import SRC, replay
from pokerbot.engine.evaluator import best_five_name

BUCKETS = [(0.0, 0.4, "tiny<=.4p"), (0.4, 0.7, "small.4-.7p"), (0.7, 1.1, "pot.7-1.1p"),
           (1.1, 2.0, "overbet1.1-2p"), (2.0, 99.0, "huge>2p")]
OUT = config.KNOWLEDGE_DIR / "exploit" / "pluribus_leaks.json"


def bucket(s: float) -> str:
    for lo, hi, name in BUCKETS:
        if lo <= s < hi:
            return name
    return "huge>2p"


def main() -> None:
    files = sorted(glob.glob(str(SRC / "**" / "*.phh"), recursive=True))
    fold = defaultdict(lambda: [0, 0, 0.0])      # (street,bucket,mw) -> [folds, n, sum_alpha]
    call_river = Counter()                       # made-hand class when Pluribus calls a river bet
    bet_sizes = defaultdict(list)                # street -> [bet/pot] when Pluribus bets (to_call==0)
    raise_n = defaultdict(lambda: [0, 0])        # (street,bucket) -> [raises, n] facing a bet
    n_dec = 0

    for fp in files:
        try:
            for obs, verb, amount, seat, name in replay(fp):
                if name != "Pluribus":
                    continue
                n_dec += 1
                st, pot, tc = obs["street"], obs["pot"], obs["to_call"]
                mw = obs["n_active"] > 2
                if tc > 0:                                   # Pluribus FACES a bet/raise
                    s = tc / max(1, pot - tc)
                    alpha = tc / pot
                    b = bucket(s)
                    fs = fold[(st, b, mw)]
                    fs[1] += 1
                    fs[2] += alpha
                    rs = raise_n[(st, b)]
                    rs[1] += 1
                    if verb == "f":
                        fs[0] += 1
                    elif verb == "cbr":
                        rs[0] += 1
                    elif verb == "cc" and st == "river" and obs["board"]:
                        call_river[best_five_name(obs["board"], obs["hole"])] += 1
                elif verb == "cbr" and amount and pot > 0 and obs["board"]:  # Pluribus BETS
                    bet_sizes[st].append(amount / pot)
        except Exception:  # noqa: BLE001
            continue

    # ---- assemble exploit map ----
    leaks = []
    for (st, b, mw), (f, n, sa) in fold.items():
        if n < 40:
            continue
        fold_pct = 100 * f / n
        alpha_pct = 100 * sa / n
        gap = fold_pct - alpha_pct
        leaks.append({"street": st, "size": b, "multiway": mw, "n": n,
                      "fold_pct": round(fold_pct, 1), "alpha_pct": round(alpha_pct, 1),
                      "gap": round(gap, 1)})
    leaks.sort(key=lambda d: -abs(d["gap"]))
    bet_dist = {st: {"n": len(v), "mean_pot": round(sum(v) / len(v), 2),
                     "p_overbet": round(100 * sum(1 for x in v if x > 1.0) / len(v), 1)}
                for st, v in bet_sizes.items() if v}
    out = {"decisions": n_dec, "leaks": leaks, "bet_size_footprint": bet_dist,
           "river_call_strength": dict(call_river.most_common())}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")

    # ---- report ----
    print(f"Pluribus decisions analysed: {n_dec}  -> {OUT}")
    print("\n=== FOLD-TO-BET vs alpha (max unexploitable fold) — biggest gaps ===")
    print(f"{'street':8s} {'size':14s} {'mw':3s} {'n':>5s} {'fold%':>6s} {'alpha%':>7s} {'gap':>6s}  exploit")
    for d in leaks[:18]:
        tag = "BLUFF (overfolds)" if d["gap"] > 6 else ("VALUE (sticky)" if d["gap"] < -6 else "~balanced")
        print(f"{d['street']:8s} {d['size']:14s} {('mw' if d['multiway'] else 'hu'):3s} "
              f"{d['n']:5d} {d['fold_pct']:6.1f} {d['alpha_pct']:7.1f} {d['gap']:+6.1f}  {tag}")
    print("\n=== Pluribus bet-size footprint (when it bets) ===")
    for st in ("flop", "turn", "river"):
        if st in bet_dist:
            x = bet_dist[st]
            print(f"  {st:6s}: mean {x['mean_pot']:.2f}x pot, overbets {x['p_overbet']:.0f}%  (n={x['n']})")
    print("\n=== River calling-range strength (hands Pluribus calls a river bet with) ===")
    tot = sum(call_river.values()) or 1
    for k, v in call_river.most_common():
        print(f"  {k:16s}: {100*v/tot:5.1f}%  (n={v})")


if __name__ == "__main__":
    main()
