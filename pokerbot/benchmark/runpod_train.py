"""HEAVY RunPod job — make the bot better via large-scale self-play hardening across STACK DEPTHS.

Rationale (user's point): stack depth / SPR changes optimal play even at fixed blinds, and tournaments
add rising blinds + ICM. So we don't tune one 100bb config — we sweep a grid of effective stack
depths and, for each, SEARCH the adaptive+gate engine's key parameters to maximise a ROBUST edge
(mean bb/100 vs a large random opponent population, penalising any opponent we lose to). Output:
per-stack-depth best parameters the engine can load, so it plays depth-aware.

Compute-hungry and embarrassingly parallel (multiprocessing over depth x param-combo) -> the RunPod
workload; it scales with vCPU cores. Scale with --pop/--hands/--workers.
  Local smoke:  python -m pokerbot.benchmark.runpod_train --quick
  Full (RunPod): python -m pokerbot.benchmark.runpod_train --pop 300 --hands 300 --iters 200 --workers 32

ICM/tournament hook: --icm wraps chip EV in an ICM-style concave (sqrt) utility — a placeholder for a
real ICM model once tournament structures (rising blinds, pay jumps) are added.
"""
from __future__ import annotations

import argparse
import json
import math
import multiprocessing as mp
import random
import statistics
from collections import defaultdict

import pokerbot.benchmark.beat_them_all as bta
from pokerbot import config
from pokerbot.strategy.adaptive import AdaptiveExploiter

DEPTHS = [20, 40, 75, 125, 200]          # effective stack in bb (SPR grid)
GRID = [(ve, be, pb) for ve in (0.58, 0.62, 0.66) for be in (0.38, 0.42) for pb in (20.0, 40.0, 60.0)]
OUT = config.KNOWLEDGE_DIR / "exploit" / "stack_depth_params.json"


def _edge(params, depth_bb, pop, hands, iters, icm, seed=0):
    rng = random.Random(seed)
    nets = []
    for i in range(pop):
        fp, ap_, sz = rng.random(), rng.random() * 0.7, 0.3 + rng.random() * 1.2
        opp = bta.opp_synthetic(random.Random(7000 + i), fold_p=fp, aggr_p=ap_, size=sz)
        ex = AdaptiveExploiter(0, seed=7, iters=iters, gate=True, probe_budget_bb=params[2])
        ex.VALUE_EQ, ex.BLUFF_EQ = params[0], params[1]
        bb100 = bta.play(ex, opp, hands, start=depth_bb * 100)
        nets.append(math.copysign(math.sqrt(abs(bb100)), bb100) if icm else bb100)
    return statistics.mean(nets), min(nets)


def _task(arg):
    depth, combo, pop, hands, iters, icm = arg
    m, mn = _edge(combo, depth, pop, hands, iters, icm)
    return depth, combo, m, mn


def _score(mean_v, min_v):
    """Robust objective: reward mean edge, heavily penalise losing to ANY opponent."""
    return mean_v + 3.0 * min(0.0, min_v)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pop", type=int, default=300)
    ap.add_argument("--hands", type=int, default=300)
    ap.add_argument("--iters", type=int, default=200)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--icm", action="store_true")
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    if args.quick:
        args.pop, args.hands, args.iters = 6, 50, 60
    grid = GRID[:2] if args.quick else GRID
    depths = DEPTHS[:2] if args.quick else DEPTHS

    tasks = [(d, c, args.pop, args.hands, args.iters, args.icm) for d in depths for c in grid]
    print(f"Stack-depth sweep: {len(depths)} depths x {len(grid)} param-combos = {len(tasks)} evals, "
          f"{args.pop} opponents x {args.hands} hands each, {args.workers} worker(s).")
    if args.workers > 1:
        with mp.Pool(args.workers) as pool:
            res = pool.map(_task, tasks)
    else:
        res = [_task(t) for t in tasks]

    by = defaultdict(list)
    for depth, combo, m, mn in res:
        by[depth].append((_score(m, mn), combo, m, mn))
    out = {}
    for d in depths:
        best = max(by[d], key=lambda x: x[0])
        _, combo, m, mn = best
        out[str(d)] = {"value_eq": combo[0], "bluff_eq": combo[1], "probe_budget_bb": combo[2],
                       "mean_bb100": round(m, 1), "worst_bb100": round(mn, 1)}
        print(f"  depth {d:3d}bb -> value_eq={combo[0]} bluff_eq={combo[1]} probe_budget={combo[2]} "
              f"| mean {m:+.0f} worst {mn:+.0f} bb/100")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"icm": args.icm, "pop": args.pop, "hands": args.hands,
                               "by_depth": out}, indent=2), encoding="utf-8")
    print(f"\nSaved per-stack-depth params -> {OUT}")


if __name__ == "__main__":
    main()
