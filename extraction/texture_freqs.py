"""Task #35: extract the EXACT per-texture GTO bet frequencies (OOP-donk node + IP-c-bet node) from the
1340-board TexasSolver cache -> knowledge_base/postflop/texture_freqs.json. Replaces the heuristic donk/c-bet
constants (the NOTES.md deferred-precision item). Same unweighted-over-combos convention as floor_map's GTO-bet.
Run: python -m extraction.texture_freqs
"""
from __future__ import annotations

import json
from collections import defaultdict

from pokerbot import config
from pokerbot.benchmark.gto_benchmark import _CACHE, texture


def solver_bet_freq(node) -> float | None:
    s = node.get("strategy", {})
    actions, strat = s.get("actions", []), s.get("strategy", {})
    if not actions or not strat:
        return None
    bet_idx = [i for i, a in enumerate(actions) if a.split()[0] in ("BET", "RAISE", "ALLIN")]
    n = 0
    tot = 0.0
    for _combo, probs in strat.items():
        tot += sum(probs[i] for i in bet_idx)
        n += 1
    return tot / n if n else None


def main() -> None:
    agg: dict = defaultdict(lambda: [0, 0.0])     # (role, texture) -> [n_boards, sum_freq]
    files = sorted(_CACHE.glob("*.json"))
    for cf in files:
        try:
            node = json.loads(cf.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        st = cf.stem
        if len(st) < 6:
            continue
        tex = texture([st[0:2], st[2:4], st[4:6]])
        ip = next((v for k, v in (node.get("childrens") or {}).items() if k.split()[0] == "CHECK"), None)
        for role, nd in (("OOP", node), ("IP", ip)):
            if nd is None:
                continue
            f = solver_bet_freq(nd)
            if f is None:
                continue
            for key in ((role, tex), (role, "ALL")):
                agg[key][0] += 1
                agg[key][1] += f
    table: dict = {"OOP": {}, "IP": {}}
    for (role, tex), (n, sm) in agg.items():
        table[role][tex] = round(sm / n, 3)
    out = config.KNOWLEDGE_DIR / "postflop" / "texture_freqs.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(table, indent=1, sort_keys=True), encoding="utf-8")
    print(f"per-texture GTO bet frequencies ({len(files)} boards):")
    print(json.dumps(table, indent=1, sort_keys=True))
    print("saved", out)


if __name__ == "__main__":
    main()
