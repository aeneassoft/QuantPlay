"""#41: build the TURN advisor's training data from the DUMP=2 cache. The classic turn-barrel spot:
flop CHECK (oop) -> BET (ip c-bet) -> CALL (oop) -> turn. For each turn card we extract the OOP turn-lead node
and the IP turn-barrel node (after OOP turn check): X = features(hole, flop+turn) + made strength + tex(4) +
role; y = the solver's P_bet. Runs ON THE POD (the cache is ~8 MB/file, too big to pull); writes a compact
data/turn_data.jsonl for #41 (train). Run: PYTHONPATH=. python3 -m extraction.build_turn_data
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


def _smallest_bet(children: dict):
    """The non-allin c-bet = smallest BET size among the children (allin is the largest)."""
    bets = [(float(k.split()[1]), k) for k in children if k.split()[0] == "BET"]
    return min(bets)[1] if bets else None


def _extract(node, role, board4, tex, rows) -> None:
    s = node.get("strategy", {}) or {}
    actions, strat = s.get("actions", []), s.get("strategy", {}) or {}
    bet_idx = [i for i, a in enumerate(actions) if a.split()[0] in ("BET", "RAISE", "ALLIN")]
    if not actions or not strat or not bet_idx:
        return
    bstr = "".join(board4)
    for combo, probs in strat.items():
        hole = [combo[:2], combo[2:4]]
        if hole[0] in board4 or hole[1] in board4:
            continue                                # solver dumps now-impossible combos with the dealt card
        f = hand_features(hole, board4)
        row = {"board": bstr, "role": role, "tex": tex,
               "y_bet": round(sum(probs[i] for i in bet_idx), 4),
               "strength": round(1.0 - evaluate(board4, hole) / 7462.0, 4)}
        for k in FEAT:
            row[k] = f[k]
        rows.append(row)


def main() -> None:
    rows, nfiles, nturn = [], 0, 0
    for cf in sorted(_CACHE.glob("*.json")):
        st = cf.stem.split("_")[0]          # strip the _<stack> suffix if present
        if len(st) != 6:
            continue
        flop = [st[0:2], st[2:4], st[4:6]]
        try:
            root = json.loads(cf.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        # walk the line: OOP CHECK -> IP BET (c-bet) -> OOP CALL -> turn chance node
        ipn = (root.get("childrens") or {}).get("CHECK")
        if not ipn:
            continue
        bkey = _smallest_bet(ipn.get("childrens") or {})
        if not bkey:
            continue
        oop_face = (ipn.get("childrens") or {}).get(bkey)
        chance = (oop_face.get("childrens") or {}).get("CALL") if oop_face else None
        if not chance or chance.get("node_type") != "chance_node":
            continue
        nfiles += 1
        for tcard, turn_oop in (chance.get("dealcards") or {}).items():
            if not isinstance(turn_oop, dict) or tcard in flop:
                continue
            board4 = flop + [tcard]
            tex = texture(board4)
            _extract(turn_oop, "OOP", board4, tex, rows)               # OOP turn lead
            turn_ip = (turn_oop.get("childrens") or {}).get("CHECK")
            if turn_ip:
                _extract(turn_ip, "IP", board4, tex, rows)             # IP turn barrel (after OOP check)
            nturn += 1
    if len(rows) > 4_000_000:                      # keep the jsonl compact (train subsamples to 2M anyway)
        import random as _rng
        rows = _rng.Random(7).sample(rows, 4_000_000)
        print("subsampled to 4,000,000 rows for a compact jsonl")
    out = config.DATA_DIR / "turn_data.jsonl"
    out.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    oop = [r["y_bet"] for r in rows if r["role"] == "OOP"]
    ipv = [r["y_bet"] for r in rows if r["role"] == "IP"]
    print(f"{len(rows)} rows from {nfiles} flop files / {nturn} turn nodes -> {out}")
    if oop:
        print(f"OOP turn-lead   P_bet mean {statistics.mean(oop):.3f} (n={len(oop)})")
    if ipv:
        print(f"IP  turn-barrel P_bet mean {statistics.mean(ipv):.3f} (n={len(ipv)})")


if __name__ == "__main__":
    main()
