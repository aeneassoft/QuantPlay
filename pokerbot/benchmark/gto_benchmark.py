"""Scalable GTO benchmark: score our gto_baseline against the TexasSolver oracle over MANY flops — the
floor's exploitability measuring stick (any engine, even a future model-free net, gets scored here).

Per spot we score TWO decisions: the OOP first-action (donk) node and the IP c-bet-after-check node.
Metric per acting hand: GTO-implausibility = 1 - p_GTO(our action-kind), where action-kind is bet vs
check (our baseline is deterministic). Aggregates a single GTO-gap + per-texture/position breakdown.
Run: python -m pokerbot.benchmark.gto_benchmark [n_boards]
"""
from __future__ import annotations

import json
import random
import sys
import time
from collections import defaultdict

from pokerbot import config
from pokerbot.strategy import gto_oracle as O
from pokerbot.strategy.gto_baseline import GTOBaseline
from pokerbot.strategy.postflop import classify_board

# Realistic single-raised-pot ranges: BB (OOP) defends vs BTN (IP) open, ~100bb (medium SPR for speed).
_OOP = "QQ,JJ,TT,99,88,77,66,55,AQs,AJs,ATs,KQs,KJs,KTs,QJs,QTs,JTs,T9s,98s,87s,76s,65s,54s,AQo,KQo,A5s,A4s,A3s"
_IP = "AA,KK,QQ,JJ,TT,99,88,77,AKs,AQs,AJs,ATs,KQs,KJs,QJs,JTs,T9s,98s,AKo,AQo,KQo,A5s,A4s"
CARDS = [r + s for r in "23456789TJQKA" for s in "shdc"]
_ORDER = "23456789TJQKA"
_CACHE = config.DATA_DIR / "_gto_bench_cache"


def _solve_cached(board, k):
    """Solve once, cache the dumped node. The GTO reference is independent of our baseline, so re-runs
    (after tuning the baseline) re-score from cache in seconds instead of re-solving."""
    _CACHE.mkdir(parents=True, exist_ok=True)
    cf = _CACHE / ("".join(board) + ".json")
    if cf.exists():
        return json.loads(cf.read_text(encoding="utf-8"))
    node = O.solve(board, _OOP, _IP, pot=20, eff_stack=100, accuracy=0.5, max_iter=100,
                   dump_rounds=1, tag=f"bm{k}")
    cf.write_text(json.dumps(node), encoding="utf-8")
    return node


def make_state(hole, board, role, pot=600, stack=10000):
    return {"legal": {"pot": pot, "to_call": 0, "can_check": True, "can_raise": True,
                      "is_bet": True, "raise_min": 1, "raise_max": stack},
            "players": [{"hole": list(hole), "committed_street": 0}],
            "board": list(board), "street": "flop", "bb": 100, "current_bet": 0,
            "aggressor": (role == "IP")}


def texture(board):
    t = classify_board(board)
    if t.get("paired"):
        return "paired"
    if t.get("monotone"):
        return "monotone"
    if t.get("connected"):
        return "connected"
    return "high" if max(_ORDER.index(c[0]) for c in board) >= _ORDER.index("T") else "low"


def score_node(node, board, hero, role):
    s = node.get("strategy", {})
    actions, strat = s.get("actions", []), s.get("strategy", {})
    if not actions or not strat:
        return None
    bet_idx = [i for i, a in enumerate(actions) if a.split()[0] in ("BET", "RAISE", "ALLIN")]
    check_idx = next((i for i, a in enumerate(actions) if a.split()[0] == "CHECK"), None)
    n = match = 0
    div = gbet = bbet = 0.0
    for combo, probs in strat.items():
        a, _ = hero.decide(make_state((combo[:2], combo[2:4]), board, role))
        our_bet = a in ("bet", "raise")
        g_bet = sum(probs[i] for i in bet_idx)
        p_ourkind = g_bet if our_bet else (probs[check_idx] if check_idx is not None else 0.0)
        div += 1 - p_ourkind
        gbet += g_bet
        bbet += 1.0 if our_bet else 0.0
        match += 1 if ((g_bet >= 0.5) == our_bet) else 0
        n += 1
    return n, div, match, gbet, bbet


def boards(nb=14):
    rng = random.Random(7)
    return [rng.sample(CARDS, 3) for _ in range(nb)]


def evaluate(hero, nb=14):
    """The SELECTOR: re-score `hero` against the CACHED solves only (no solving) — fast + deterministic.
    Returns overall + per-role (OOP/IP) GTO-gap & bet-frequencies. None if the cache is empty."""
    agg = defaultdict(lambda: [0, 0.0, 0, 0.0, 0.0])
    for board in boards(nb):
        cf = _CACHE / ("".join(board) + ".json")
        if not cf.exists():
            continue
        node = json.loads(cf.read_text(encoding="utf-8"))
        ip = next((v for k, v in (node.get("childrens") or {}).items() if k.split()[0] == "CHECK"), None)
        for role, nd in (("OOP", node), ("IP", ip)):
            if nd is None:
                continue
            r = score_node(nd, board, hero, role)
            if r:
                for j in range(5):
                    agg[role][j] += r[j]
                    agg["ALL"][j] += r[j]
    if agg["ALL"][0] == 0:
        return None

    def stat(a):
        n = a[0]
        return {"n": n, "gap": a[1] / n, "match": a[2] / n, "gbet": a[3] / n, "bbet": a[4] / n}
    return {k: stat(agg[k]) for k in ("ALL", "OOP", "IP") if agg[k][0]}


def main():
    if not O.available():
        print(f"solver missing at {O.EXE}")
        return
    nb = int(sys.argv[1]) if len(sys.argv) > 1 else 14
    hero = GTOBaseline(0, seed=1, iters=200)
    rng = random.Random(7)
    agg = defaultdict(lambda: [0, 0.0, 0, 0.0, 0.0])   # bucket -> [hands, div, match, gbet, bbet]
    t0 = time.time()
    for k in range(nb):
        board = rng.sample(CARDS, 3)
        tex = texture(board)
        try:
            node = _solve_cached(board, k)
        except Exception as e:  # noqa: BLE001
            print(f"  [{k}] {''.join(board)} solve failed: {e}", flush=True)
            continue
        ip_node = next((v for key, v in (node.get("childrens") or {}).items()
                        if key.split()[0] == "CHECK"), None)
        for label, nd in (("OOP", node), ("IP", ip_node)):
            if nd is None:
                continue
            r = score_node(nd, board, hero, label)
            if r is None:
                continue
            for key in (f"{label}:{tex}", f"{label}:ALL", "ALL"):
                a = agg[key]
                for j in range(5):
                    a[j] += r[j]
        print(f"  [{k+1}/{nb}] {''.join(board)} {tex:9} ({time.time()-t0:.0f}s)", flush=True)

    print(f"\n=== GTO benchmark ({nb} boards, {time.time()-t0:.0f}s) ===")
    print(f"{'bucket':15} {'hands':>6} {'GTO-gap':>8} {'match':>6} {'GTO-bet':>8} {'base-bet':>9}")
    for key in sorted(agg):
        n, div, match, gbet, bbet = agg[key]
        if n:
            print(f"{key:15} {n:>6} {div/n:>8.0%} {match/n:>6.0%} {gbet/n:>8.0%} {bbet/n:>9.0%}")
    print("\nGTO-gap = mean(1 - p_GTO(our action-kind)); 0 = GTO-plausible, 1 = always off.")
    print("OOP = our donk decision (GTO mostly checks); IP = our c-bet-after-check decision.")


if __name__ == "__main__":
    main()
