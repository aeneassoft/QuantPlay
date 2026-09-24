"""Flop-LIBRARY calibration pilot: what does ONE flop->terminal solve really cost to convergence?

The 2026-07-05 feasibility gate (research/flop_feasibility.py) capped at 300s and got 49/50 TIMEOUTS —
so the true per-solve cost is UNKNOWN, and the library budget (1755 canonical flops x lines, docs/NOTES.md
Queue #1) cannot be planned. This pilot removes the cap (30 min/solve), runs 4 texture-representative
canonical flops through TWO trees:
  MINIMAL  - 1 bet size/street (the EVPA-minimal-menu retest whose bwfga5qs2 result died with its session)
  LEAN     - the feasibility gate's census 3-street tree (flop 33/75, river 65/100)
and PERSISTS everything to data/research_sweep/flop_pilot.json (never again a result that lives only
in a task log). MINIMAL runs first across all boards: if even that blows the cap, LEAN is hopeless and
the early verdict is 'library needs pod-scale compute or a depth-limited tree'.

Run:  python -m research.flop_pilot          (local, idle CPU, ~10 min .. 4 h depending on the answer)
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from pokerbot.brain.api import _HU_IP as IP, _HU_OOP as OOP
from pokerbot.strategy import gto_oracle as O

OUT = Path("data/research_sweep/flop_pilot.json")
PER_SOLVE_TIMEOUT_S = 1800            # 30 min: generous enough to measure, bounded enough to finish tonight
ACC, ITERS = 0.5, 150                 # identical to the feasibility gate -> numbers stay comparable
POT, EFF = 450.0, 19775.0             # canonical SRP entry at census sizes: SB 2.25x open, BB call (bb=100)

# texture spread — convergence cost varies by board class, the library must budget for the worst
BOARDS = [
    (["As", "7h", "2d"], "dry_Ahigh_rainbow"),
    (["9h", "8h", "7s"], "wet_connected_twotone"),
    (["Kh", "9h", "4h"], "monotone"),
    (["Qs", "Qd", "6c"], "paired"),
]

LEAN_BETS = [
    "set_bet_sizes oop,flop,bet,33,75", "set_bet_sizes oop,flop,raise,50", "set_bet_sizes oop,flop,allin",
    "set_bet_sizes ip,flop,bet,33,75", "set_bet_sizes ip,flop,raise,50", "set_bet_sizes ip,flop,allin",
    "set_bet_sizes oop,turn,bet,75", "set_bet_sizes oop,turn,raise,75", "set_bet_sizes oop,turn,allin",
    "set_bet_sizes ip,turn,bet,75", "set_bet_sizes ip,turn,raise,75", "set_bet_sizes ip,turn,allin",
    "set_bet_sizes oop,river,bet,65,100", "set_bet_sizes oop,river,raise,60", "set_bet_sizes oop,river,allin",
    "set_bet_sizes ip,river,bet,65,100", "set_bet_sizes ip,river,raise,60", "set_bet_sizes ip,river,allin",
]
# census modal size only (flop 35 / turn 75 / river 65) -> bet nodes lose their 2nd arm vs LEAN
MINIMAL_BETS = [
    "set_bet_sizes oop,flop,bet,35", "set_bet_sizes oop,flop,raise,50", "set_bet_sizes oop,flop,allin",
    "set_bet_sizes ip,flop,bet,35", "set_bet_sizes ip,flop,raise,50", "set_bet_sizes ip,flop,allin",
    "set_bet_sizes oop,turn,bet,75", "set_bet_sizes oop,turn,raise,75", "set_bet_sizes oop,turn,allin",
    "set_bet_sizes ip,turn,bet,75", "set_bet_sizes ip,turn,raise,75", "set_bet_sizes ip,turn,allin",
    "set_bet_sizes oop,river,bet,65", "set_bet_sizes oop,river,raise,60", "set_bet_sizes oop,river,allin",
    "set_bet_sizes ip,river,bet,65", "set_bet_sizes ip,river,raise,60", "set_bet_sizes ip,river,allin",
]
ARMS = [("minimal", MINIMAL_BETS), ("lean", LEAN_BETS)]


def main() -> None:
    results: list[dict] = []
    OUT.parent.mkdir(parents=True, exist_ok=True)
    for arm_name, bets in ARMS:
        for board, tex in BOARDS:
            t0 = time.time()
            row: dict = {"arm": arm_name, "board": "".join(board), "texture": tex,
                         "pot": POT, "eff": EFF, "acc": ACC, "iters": ITERS}
            try:
                r = O.solve(board, OOP, IP, pot=POT, eff_stack=EFF, bets=bets,
                            accuracy=ACC, max_iter=ITERS, dump_rounds=1, threads=8,
                            timeout=PER_SOLVE_TIMEOUT_S, tag=f"fpilot_{arm_name}_{tex}")
                row["seconds"] = round(time.time() - t0, 1)
                row["exploitability_pct"] = r.get("_exploitability_pct")
                row["solve_iters"] = r.get("_solve_iters")
            except Exception as ex:  # noqa: BLE001
                row["seconds"] = round(time.time() - t0, 1)
                row["error"] = f"{type(ex).__name__}: {ex}"[:200]
            results.append(row)
            OUT.write_text(json.dumps({"results": results}, indent=1), encoding="utf-8")  # persist after EVERY solve
            print(f"[{arm_name}] {''.join(board):8s} {tex:24s} {row['seconds']:8.1f}s "
                  f"expl={row.get('exploitability_pct')} err={row.get('error', '-')}", flush=True)
        arm_rows = [x for x in results if x["arm"] == arm_name and "error" not in x]
        if not arm_rows:
            print(f"ARM '{arm_name}': 0/{len(BOARDS)} converged inside {PER_SOLVE_TIMEOUT_S}s "
                  f"-> heavier trees are pointless; stopping early", flush=True)
            break
    print(f"done -> {OUT}", flush=True)


if __name__ == "__main__":
    main()
