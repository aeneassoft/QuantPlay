"""LINE-AWARE river training data: solve river SUBGAMES per POT-TYPE (SRP/3bet/4bet) with the CORRECT
blueprint REACH ranges (api._reach_range), not the wrong fixed ranges the old build_river_data used. The micro-test
proved the solver's value-bet frequency swings 17%->97% with the range, so the range (pot-type) MUST be a feature.
Each row carries `pot_type` -> train_river_la.py one-hot-encodes it (18->21 dims) -> river_advisor_la.pt.

Approach B (validated 2026-06-29): full flop->river solves time out (>600s); river subgames are ~5s + extractable.
HONEST LIMIT: uses the full pot-type reach range = the check-down river approximation (no flop/turn line-narrowing).

Run:  PYTHONUTF8=1 PYTHONPATH=. python -m research.build_river_la --n 1800 --workers 6
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import uuid
from concurrent.futures import ThreadPoolExecutor

from pokerbot import config
from pokerbot.benchmark.gto_benchmark import texture
from pokerbot.brain import api
from pokerbot.engine.cards import make_deck
from pokerbot.engine.evaluator import evaluate
from pokerbot.strategy import gto_oracle as O
from pokerbot.strategy.features import hand_features

FEAT = ["tier", "flush_draw", "backdoor_flush", "nut_flush_blocker", "made_straight",
        "oesd", "gutshot", "overcards", "has_draw"]
POT_TYPES = ["srp", "3bet", "4bet"]
STACKS = [40, 80, 120, 200]          # varied river SPR (pot fixed at 20bb), mirrors mass_solve


def _ranges(pt: str):
    """(oop_range, ip_range) reach-weighted from the blueprint for this pot type. SB=IP(button), BB=OOP."""
    sb_steps, bb_steps = api._LINE_STEPS[pt]
    return api._reach_range(bb_steps), api._reach_range(sb_steps)


def _rows_from_solve(root: dict, board: list, pt: str, stack: int) -> list:
    """Extract per-(role, combo) y_bet + features. Mirrors build_river_data: root=OOP, its CHECK child=IP."""
    ip_node = next((v for k, v in (root.get("childrens") or {}).items() if k.split()[0] == "CHECK"), None)
    bid = f"{''.join(board)}_{pt}_{stack}"
    out = []
    for role, nd in (("OOP", root), ("IP", ip_node)):
        if nd is None:
            continue
        s = nd.get("strategy", {})
        actions, strat = s.get("actions", []), s.get("strategy", {})
        if not actions or not strat:
            continue
        bet_idx = [i for i, a in enumerate(actions) if a.split()[0] in ("BET", "RAISE", "ALLIN")]
        for combo, probs in strat.items():
            hole = [combo[:2], combo[2:4]]
            f = hand_features(hole, board)
            row = {"board": bid, "role": role, "tex": texture(board), "pot_type": pt,
                   "y_bet": round(sum(probs[i] for i in bet_idx), 4),
                   "strength": round(1.0 - evaluate(board, hole) / 7462.0, 4)}
            for k in FEAT:
                row[k] = f[k]
            out.append(row)
    return out


def _solve_one(args) -> list:
    pt, seed, threads = args
    rng = random.Random(seed)
    board = rng.sample(make_deck(), 5)
    stack = rng.choice(STACKS)
    oop, ip = _ranges(pt)
    try:
        root = O.solve(board, oop, ip, pot=20, eff_stack=stack, bets=api._LEAN_BETS,
                       accuracy=0.5, max_iter=150, threads=threads, dump_rounds=1,
                       timeout=120, tag=uuid.uuid4().hex)
        return _rows_from_solve(root, board, pt, stack)
    except Exception:  # noqa: BLE001
        return []


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1800)          # total solves (cycled across pot types)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--solve-threads", type=int, default=3)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default=str(config.DATA_DIR / "river_data_la.jsonl"))
    args = ap.parse_args()

    jobs = [(POT_TYPES[i % len(POT_TYPES)], args.seed * 100000 + i, args.solve_threads) for i in range(args.n)]
    rows, done = [], 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for r in ex.map(_solve_one, jobs):
            rows.extend(r)
            done += 1
            if done % 50 == 0:
                print(f"  {done}/{args.n} solves, {len(rows)} rows")

    out = config.DATA_DIR / "river_data_la.jsonl" if args.out is None else __import__("pathlib").Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    print(f"\n{len(rows)} rows -> {out}  ({args.n} solves)")
    for pt in POT_TYPES:
        strong = [r["y_bet"] for r in rows if r["pot_type"] == pt and r["strength"] >= 0.85]
        if strong:
            print(f"  {pt:4s}: strong-hand (strength>=0.85) mean P_bet = {statistics.mean(strong):.2f} (n={len(strong)})")


if __name__ == "__main__":
    main()
