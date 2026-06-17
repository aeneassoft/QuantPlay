"""SD advisor data: extract the SHORT-DECK solver's bet-vs-check strategy per (flop, role, combo) from the
short-deck cache -> data/sd_advisor_data.jsonl. Mirrors build_advisor_data.py but short-deck: strength via
engine/sd_eval (the verified 6-A evaluator), a generic short-deck texture (works on any 3 cards). For the SD
near-GTO demo (the advisor's training data). Run: python -m extraction.build_sd_advisor_data
"""
from __future__ import annotations

import json
import statistics

from pokerbot import config
from pokerbot.engine import sd_eval as SD

CACHE = config.DATA_DIR / "_gto_shortdeck_cache"
_RIDX = {r: i for i, r in enumerate(SD.SD_RANKS)}   # 6=0 .. A=8 (ace high)


def sd_texture(board) -> str:
    ranks = [c[0] for c in board]
    suits = [c[1] for c in board]
    if len(set(ranks)) < len(ranks):
        return "paired"
    if len(set(suits)) == 1:
        return "mono"
    idx = sorted(_RIDX[r] for r in ranks)
    if idx[-1] - idx[0] <= 2:        # tight rank span -> connected (short-deck boards connect a lot)
        return "connected"
    if len(set(suits)) == 2:
        return "twotone"
    return "dry"


def main() -> None:
    rows = []
    flops = sorted(CACHE.glob("*.json"))
    for cf in flops:
        try:
            node = json.loads(cf.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        st = cf.stem.split("_")[0]
        if len(st) < 6:
            continue
        board = [st[0:2], st[2:4], st[4:6]]
        tex = sd_texture(board)
        ip = next((v for k, v in (node.get("childrens") or {}).items() if k.split()[0] == "CHECK"), None)
        for role, nd in (("OOP", node), ("IP", ip)):
            if nd is None:
                continue
            s = nd.get("strategy") or {}
            actions, strat = s.get("actions", []), s.get("strategy") or {}
            if not actions or not strat:
                continue
            bet_idx = [i for i, a in enumerate(actions) if a.split()[0] in ("BET", "RAISE", "ALLIN")]
            for combo, probs in strat.items():
                if combo[0] not in SD.SD_RANKS or combo[2] not in SD.SD_RANKS:
                    continue                      # defensive: skip any stray non-short-deck combo
                hole = [combo[:2], combo[2:4]]
                rows.append({"board": st, "role": role, "tex": tex,
                             "y_bet": round(sum(probs[i] for i in bet_idx), 4),
                             "strength": round(SD.normalized_strength(hole, board), 4)})
    out = config.DATA_DIR / "sd_advisor_data.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    print(f"{len(rows)} SD advisor rows from {len(flops)} flops -> {out}")
    for role in ("OOP", "IP"):
        rr = [r["y_bet"] for r in rows if r["role"] == role]
        if rr:
            print(f"  {role}: mean P_bet {statistics.mean(rr):.3f} (n={len(rr)})")
    from collections import Counter
    print("  textures:", dict(Counter(r["tex"] for r in rows)))


if __name__ == "__main__":
    main()
