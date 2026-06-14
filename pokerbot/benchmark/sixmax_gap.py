"""Step 4c diagnostic: score the LIVE 6-max bot (sixmax._decide) against the solver cache with the SAME
metric as gto_benchmark (IP c-bet + OOP donk frequency vs GTO). The Step-3 calibration was on GTOBaseline,
but sixmax has its OWN postflop policy -> measure ITS gap before tuning. Adapter maps the benchmark state
to a sixmax obs (HU single-raised pot: IP=BTN aggressor, OOP=BB caller).
Run:  python -m pokerbot.benchmark.sixmax_gap
"""
from __future__ import annotations

import json
from collections import defaultdict

from pokerbot.arena import sixmax
from pokerbot.benchmark.calibrate import all_boards
from pokerbot.benchmark.gto_benchmark import _CACHE, score_node


def bench_obs(state: dict) -> dict:
    la, p0 = state["legal"], state["players"][0]
    aggr = bool(state.get("aggressor", True))
    return {"hole": p0["hole"], "board": state["board"], "bb": state["bb"],
            "to_call": la["to_call"], "pot": la["pot"], "can_check": la["can_check"],
            "can_raise": la["can_raise"], "can_call": la["to_call"] > 0,
            "position": "BTN" if aggr else "BB", "preflop_raises": 1,
            "raise_min": la["raise_min"], "raise_max": la["raise_max"],
            "cur_bet": state.get("current_bet", 0), "my_stack": la["raise_max"],
            "n_active": 2, "street": state["street"], "my_committed_street": p0.get("committed_street", 0)}


class _Hero:
    """Wrap sixmax._decide so gto_benchmark.score_node (which calls hero.decide(state)->(a,amt)) can score it."""
    def __init__(self, knobs):
        self.k = knobs
        self.hero = 0

    def decide(self, state):
        d = sixmax._decide(bench_obs(state), self.k, {}, aggressor=state.get("aggressor"))
        return d["action"], d["amount"]


def measure(knobs, n=400):
    hero = _Hero(knobs)
    agg = defaultdict(lambda: [0, 0.0, 0, 0.0, 0.0])
    for board in all_boards()[:n]:
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
    return agg


def main():
    sixmax.EQ_ITERS = 80          # faster equity for the diagnostic (vs the live 400)
    agg = measure(sixmax.PROFILES["tag"], n=300)
    print("=== LIVE 6-max bot (sixmax, tag) vs solver ===", flush=True)
    for role in ("ALL", "OOP", "IP"):
        a = agg[role]
        n = a[0]
        if n:
            print(f"  {role:3} n={n:5} gap={a[1]/n:.1%}  GTO-bet={a[3]/n:.0%}  sixmax-bet={a[4]/n:.0%}", flush=True)
    print("  (IP = c-bet after check; OOP = donk; compare sixmax-bet vs GTO-bet)", flush=True)


if __name__ == "__main__":
    main()
