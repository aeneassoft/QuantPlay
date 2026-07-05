"""HU blueprint GOLD via DIRECT node enumeration — the flywheel fix for the GTOW HU over-fold leak.

`gen_decision_states` never produced hero OPEN decisions (0/2463 examples had a raise-modal — it only mapped the
DEFEND nodes). This instead DRIVES an HU engine table to EACH blueprint node (ROOT/LIMP/OPEN/ISO/3BET/4BET), grabs
hero's spot template, then for every hand class with a blueprint mix emits (format_spot with that hand, a grammar-valid
`decide_mix({...}, size=)` dict-literal of the blueprint mix). So the gold COVERS every node × hand — including the
opens / 3bets / 4bets where the over-fold leak lives. A few table seeds add stack/position variety.

Run: python -m dataset.build.from_hu
"""
from __future__ import annotations

import json
from collections import Counter

from pokerbot import config
from pokerbot.brain.dsl_grammar import matches
from pokerbot.brain.format_spot import format_spot, spot_from_table
from pokerbot.engine.table import Table
from pokerbot.strategy import preflop_blueprint as pbp
from pokerbot.strategy.preflop_blueprint import SIZES_BB
from dataset.schema import make_example

_RANKS = "AKQJT98765432"
_SEEDS = [42, 7, 101, 2024, 9]                               # table seeds -> stack/pos variety (5 = balanced vs the postflop gold; plan #3)
# the preflop verb sequence (HU, SB acts first preflop) to reach each node where HERO is next to act:
_LINES = {
    "ROOT": [],                                              # SB first-in (open/limp/fold)
    "LIMP": [("call", None)],                                # BB option after SB limp
    "OPEN": [("raise", 2.5)],                                # BB faces the SB open
    "ISO":  [("call", None), ("raise", 4.5)],               # SB faces the BB iso of its limp
    "3BET": [("raise", 2.5), ("raise", 10.0)],              # SB faces the BB 3bet
    "4BET": [("raise", 2.5), ("raise", 10.0), ("raise", 24.0)],   # BB faces the SB 4bet
}


def _all_classes() -> list:
    return ([r + r for r in _RANKS]
            + [_RANKS[i] + _RANKS[j] + "s" for i in range(13) for j in range(i + 1, 13)]
            + [_RANKS[i] + _RANKS[j] + "o" for i in range(13) for j in range(i + 1, 13)])


def _cards_of(hc: str) -> list:
    """A representative 2-card combo for a class (AKs->As Ks, 99->9s 9d, T9o->Ts 9h)."""
    a, b = hc[0], hc[1]
    if a == b:
        return [a + "s", a + "d"]
    return [a + "s", b + ("s" if hc.endswith("s") else "h")]


def _verbs_from_mix(node: str, hc: str):
    """Blueprint label-mix at (node, hc) -> (DSL-verb mix, raise_size_bb) | (None, None). Mirrors api.preflop_solve."""
    m = pbp.actions(node, hc)
    if not m:
        return None, None
    verbs, rsize = {}, None
    for label, p in m.items():
        if not p or float(p) <= 0.01:
            continue
        if label in SIZES_BB:
            verb = "call" if label == "limp" else "raise"
            if verb == "raise":
                rsize = SIZES_BB[label]
        elif label == "jam":
            verb = "allin"
        elif label in ("call", "check", "fold"):
            verb = label
        else:
            continue
        verbs[verb] = verbs.get(verb, 0.0) + round(float(p), 3)
    return (verbs or None), rsize


def _template_spot(node: str, seed: int):
    """Drive an HU table to `node`; return (table, hero_seat) at hero's decision, or (None, None) if the line desyncs."""
    t = Table(["a", "b"], seed=seed, human_seat=-1)
    t.start_hand()
    for verb, size_bb in _LINES[node]:
        if t.to_act is None:
            return None, None
        t.act(verb, int(size_bb * t.bb) if size_bb else None)
    return (t, t.to_act) if t.to_act is not None else (None, None)


def build_enum():
    classes = _all_classes()
    for node in _LINES:
        for seed in _SEEDS:
            t, hero = _template_spot(node, seed)
            if hero is None:
                continue
            spot = spot_from_table(t, hero)
            if spot.street != "preflop" or spot.n_active != 2:
                continue
            for hc in classes:
                verbs, rsize = _verbs_from_mix(node, hc)
                if not verbs:
                    continue
                spot.hero_hole = _cards_of(hc)
                modal = max(verbs, key=verbs.get)
                size_arg = f", size={rsize}" if (rsize and any(a in verbs for a in ("raise", "bet", "allin"))) else ""
                mix_repr = "{" + ", ".join(f"'{k}': {v}" for k, v in verbs.items()) + "}"
                prog = ("# preflop: the EXACT near-Nash HU-200bb blueprint mix (api.preflop_solve), not equity-logic\n"
                        f"decide_mix({mix_repr}{size_arg})")
                if not matches(prog):
                    continue
                yield make_example("selfplay", format_spot(spot), prog,
                                   action={"action": modal, "size_bb": rsize if modal in ("raise", "bet", "allin") else None},
                                   type_="decision", meta={"hu": True, "blueprint": True, "node": node})


def main():
    rows = list(build_enum())
    out = config.ROOT / "dataset" / "shards" / "hu_blueprint.jsonl"
    with open(out, "w", encoding="utf-8") as f:
        for ex in rows:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} HU blueprint rows -> {out}")
    print("per-node:", dict(Counter(e["meta"]["node"] for e in rows)))
    print("modal mix:", dict(Counter(e["action"]["action"] for e in rows)))


if __name__ == "__main__":
    main()
