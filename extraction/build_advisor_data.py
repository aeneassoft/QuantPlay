"""Task #37: build the GTO-floor advisor's training data from the TexasSolver cache. For each (board, role,
combo): X = blocker/potential features (features.py) + made strength + texture + role; y = the solver's bet
probability (P_bet) at that combo. -> data/advisor_data.jsonl for #38 (train). Cheap (no MC; treys rank only).
Run: python -m extraction.build_advisor_data
"""
from __future__ import annotations

import json
import statistics

from pokerbot import config
from pokerbot.benchmark.gto_benchmark import _CACHE, texture
from pokerbot.engine.evaluator import evaluate
from pokerbot.strategy.features import hand_features

FEAT = ["tier", "flush_draw", "backdoor_flush", "nut_flush_blocker", "made_straight",
        "oesd", "gutshot", "overcards", "has_draw"]


def main() -> None:
    rows = []
    for cf in sorted(_CACHE.glob("*.json")):
        try:
            node = json.loads(cf.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        st = cf.stem
        if len(st) < 6:
            continue
        board = [st[0:2], st[2:4], st[4:6]]
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
    out = config.DATA_DIR / "advisor_data.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    oop = [r["y_bet"] for r in rows if r["role"] == "OOP"]
    ipv = [r["y_bet"] for r in rows if r["role"] == "IP"]
    print(f"{len(rows)} rows -> {out}")
    print(f"OOP P_bet mean {statistics.mean(oop):.3f} (n={len(oop)}) | IP {statistics.mean(ipv):.3f} (n={len(ipv)})")


if __name__ == "__main__":
    main()
