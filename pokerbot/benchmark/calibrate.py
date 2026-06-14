"""SYNTHESIS Step 3: calibrate gto_baseline's postflop priors to MATCH the solver's c-bet/donk FREQUENCIES
(not just the gameable action-gap, which over-c-betting can lower while drifting AWAY from GTO's 79% IP freq),
over the FULL _gto_bench_cache, with a held-out train/test split (guards overfitting -- Claude's flag).

loss = ALL.gap + |IP.bbet-IP.gbet| + |OOP.bbet-OOP.gbet|   (frequency-match is the honest objective)

Run:  python -m pokerbot.benchmark.calibrate
"""
from __future__ import annotations

import json
import os
import random
from collections import defaultdict

from pokerbot.benchmark.gto_benchmark import _CACHE, score_node
from pokerbot.strategy.gto_baseline import GTOBaseline

CARDS = [r + s for r in "23456789TJQKA" for s in "shdc"]
ITERS = int(os.environ.get("ITERS", "80"))
NTRAIN = int(os.environ.get("NTRAIN", "400"))
NTEST = int(os.environ.get("NTEST", "300"))


def all_boards():
    """List the ACTUAL cached flop solves (filenames != our boards(seed) sequence) and parse the board
    from each 6-char stem, e.g. 'AsKd7c' -> ['As','Kd','7c']. Deterministic shuffle for a stable split."""
    out = []
    for f in sorted(_CACHE.glob("*.json")):
        s = f.stem
        if len(s) == 6:                      # flop = 3 cards
            out.append([s[0:2], s[2:4], s[4:6]])
    random.Random(13).shuffle(out)
    return out


def eval_boards(params, boards):
    hero = GTOBaseline(0, seed=1, iters=ITERS, params=params)
    agg = defaultdict(lambda: [0, 0.0, 0, 0.0, 0.0])
    for board in boards:
        node = json.loads((_CACHE / ("".join(board) + ".json")).read_text(encoding="utf-8"))
        ip = next((v for k, v in (node.get("childrens") or {}).items() if k.split()[0] == "CHECK"), None)
        for role, nd in (("OOP", node), ("IP", ip)):
            if nd is None:
                continue
            r = score_node(nd, board, hero, role)
            if r:
                for j in range(5):
                    agg[role][j] += r[j]
                    agg["ALL"][j] += r[j]

    def stat(a):
        n = a[0]
        return {"n": n, "gap": a[1] / n, "match": a[2] / n, "gbet": a[3] / n, "bbet": a[4] / n}
    return {k: stat(agg[k]) for k in ("ALL", "OOP", "IP") if agg[k][0]}


def loss(e):
    return e["ALL"]["gap"] + abs(e["IP"]["bbet"] - e["IP"]["gbet"]) + abs(e["OOP"]["bbet"] - e["OOP"]["gbet"])


def line(tag, e):
    return (f"{tag:10} loss {loss(e):.3f} | gap {e['ALL']['gap']:.1%} match {e['ALL']['match']:.0%} | "
            f"IP-bet {e['IP']['bbet']:.0%} (GTO {e['IP']['gbet']:.0%}) | "
            f"OOP-bet {e['OOP']['bbet']:.0%} (GTO {e['OOP']['gbet']:.0%})")


def main():
    allb = all_boards()
    tr = allb[:NTRAIN]
    te = allb[NTRAIN:NTRAIN + NTEST]
    print(f"boards: total={len(allb)} train={len(tr)} test={len(te)} | iters={ITERS}", flush=True)
    base_tr = eval_boards({}, tr)
    print(line("BASE/tr", base_tr), flush=True)

    grid = {"cbet_eq": [0.40, 0.48, 0.56, 0.64, 0.72],
            "cbet_bluff": [0.2, 0.4, 0.6, 0.8],
            "donk_eq": [0.75, 0.85, 0.95],
            "donk_freq": [0.0, 0.05, 0.1, 0.2]}
    cur = {}
    best = loss(base_tr)
    for knob, vals in grid.items():
        trials = sorted(((loss(eval_boards({**cur, knob: v}, tr)), v) for v in vals), key=lambda x: x[0])
        g, v = trials[0]
        if g < best - 1e-4:
            cur[knob], best = v, g
            print(f"  accept {knob}={v} -> train loss {g:.3f}", flush=True)
        else:
            print(f"  {knob}: no improvement (best {best:.3f})", flush=True)

    print("\n--- HELD-OUT (test) verification ---", flush=True)
    print(line("BASE/te", eval_boards({}, te)), flush=True)
    print(line("TUNED/te", eval_boards(cur, te)), flush=True)
    print(f"\ntuned params = {cur}", flush=True)
    out = config_path()
    out.write_text(json.dumps(cur, indent=2), encoding="utf-8")
    print(f"saved -> {out}", flush=True)


def config_path():
    from pokerbot import config
    return config.KNOWLEDGE_DIR / "postflop" / "calibrated_priors.json"


if __name__ == "__main__":
    main()
