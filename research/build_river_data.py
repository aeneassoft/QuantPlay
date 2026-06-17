"""WS2: build the RIVER advisor's training data from the river-subgame TexasSolver cache
(data/_gto_river_cache, produced by extraction.mass_solve with STREET=5). Mirrors build_advisor_data.py (the
FLOP builder), NOT build_turn_data: the river cache root IS the OOP first-to-act river node and its CHECK child
is the IP node -> no line-walk. For each (board5, role, combo): X = blocker/potential + made-strength + texture
+ role features; y = the solver's P(bet). -> data/river_data.jsonl for train_river_advisor.py.
Run: python -m extraction.build_river_data
"""
from __future__ import annotations

import json
import statistics

from pokerbot import config
from pokerbot.benchmark.gto_benchmark import texture      # max over ALL board cards -> valid on a 5-card board
from pokerbot.engine.evaluator import evaluate
from pokerbot.strategy.features import hand_features

RCACHE = config.DATA_DIR / "_gto_river_cache"
FEAT = ["tier", "flush_draw", "backdoor_flush", "nut_flush_blocker", "made_straight",
        "oesd", "gutshot", "overcards", "has_draw"]


def main() -> None:
    rows = []
    for cf in sorted(RCACHE.glob("*.json")):
        try:
            node = json.loads(cf.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        st = cf.stem
        bs = st.split("_")[0]                 # strip the _<stack> suffix -> 10 hex chars = 5 board cards
        if len(bs) < 10:
            continue
        board = [bs[0:2], bs[2:4], bs[4:6], bs[6:8], bs[8:10]]
        tex = texture(board)
        ip = next((v for k, v in (node.get("childrens") or {}).items() if k.split()[0] == "CHECK"), None)
        for role, nd in (("OOP", node), ("IP", ip)):
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
                row = {"board": st, "role": role, "tex": tex,
                       "y_bet": round(sum(probs[i] for i in bet_idx), 4),
                       "strength": round(1.0 - evaluate(board, hole) / 7462.0, 4)}
                for k in FEAT:
                    row[k] = f[k]
                rows.append(row)
    out = config.DATA_DIR / "river_data.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    oop = [r["y_bet"] for r in rows if r["role"] == "OOP"]
    ipv = [r["y_bet"] for r in rows if r["role"] == "IP"]
    print(f"{len(rows)} rows -> {out}")
    if oop:
        print(f"OOP P_bet mean {statistics.mean(oop):.3f} (n={len(oop)})")
    if ipv:
        print(f"IP  P_bet mean {statistics.mean(ipv):.3f} (n={len(ipv)})")


if __name__ == "__main__":
    main()
