"""Reach-weighted preflop ranges at each see-flop node of the blueprint TREE — the input a postflop solver needs
to ground the see-flop continuation value (Step 1 of the solver-grafted-preflop plan).

For a see-flop leaf (kind "sd") reached by a path ROOT -> ... -> node, each hand class's REACH for a player is the
product of that player's blueprint action-probabilities along the path. The class-reach IS the correct relative
range weight: TexasSolver expands a class-weighted string ("AA:1.0,AKs:0.5") to its combos and applies the weight
per combo, so combo multiplicity (6 for pairs, etc.) is handled by the solver — we pass the per-class action-reach.

HU mapping (fixed): BB = OOP postflop, SB (button) = IP postflop.
Run:  python -m extraction.preflop_ranges   # prints the 6 see-flop nodes' (pot, eff) + top of each range
"""
from __future__ import annotations

import json

from pokerbot import config
from research.preflop_solve import TREE, CLASSES, N

START_STACK_BB = 200.0     # the blueprint is solved at 200bb (TREE jam = 200,200)
EMIT_FLOOR = 1e-3          # drop classes below this RELATIVE (to max) reach weight from the emitted string


def sd_leaves() -> dict:
    """DFS the TREE -> {node: (action, n_sb, n_bb, path)} for every see-flop ('sd') leaf, where path is the list of
    (node, action) from ROOT to that leaf (the leaf's own (node, action) included). Each see-flop parent has one 'sd'."""
    out: dict = {}

    def walk(node, path):
        _to_act, _si, _bi, acts = TREE[node]
        for (a, kind, n_sb, n_bb, nxt) in acts:
            if kind == "sd":
                out[node] = (a, n_sb, n_bb, path + [(node, a)])
            elif kind == "node":
                walk(nxt, path + [(node, a)])
            # foldSB / foldBB / sd_allin -> terminal, no see-flop continuation

    walk("ROOT", [])
    return out


def _range_str(reach: list[float]) -> str:
    """Per-class reach -> a TexasSolver class-weighted range string, normalised to max=1, near-zero classes dropped."""
    mx = max(reach) if reach else 0.0
    if mx <= 0:
        return ""
    entries = [(CLASSES[i], reach[i] / mx) for i in range(N) if reach[i] / mx >= EMIT_FLOOR]
    return ",".join(f"{c}:{w:.4f}" for c, w in sorted(entries, key=lambda x: -x[1]))


def reach_weights(node: str, blueprint: dict) -> tuple[list, list, float, float]:
    """-> (oop_reach[N], ip_reach[N], pot_bb, eff_stack_bb): the per-class reach (product of blueprint action-probs
    along the path) for OOP=BB and IP=SB at the see-flop leaf `node`. Raw (un-normalised) weights."""
    leaves = sd_leaves()
    if node not in leaves:
        raise KeyError(f"{node} has no see-flop leaf")
    _action, n_sb, n_bb, path = leaves[node]
    sb_reach = [1.0] * N
    bb_reach = [1.0] * N
    for (nd, a) in path:
        to_act = TREE[nd][0]
        bp_nd = blueprint.get(nd, {})
        for ci, cls in enumerate(CLASSES):
            p = bp_nd.get(cls, {}).get(a, 0.0)
            if to_act == 0:
                sb_reach[ci] *= p
            else:
                bb_reach[ci] *= p
    pot = float(n_sb + n_bb)
    eff = START_STACK_BB - float(max(n_sb, n_bb))      # symmetric at a call/check leaf
    return bb_reach, sb_reach, pot, eff


def reaching_ranges(node: str, blueprint: dict) -> tuple[str, str, float, float]:
    """-> (oop_str, ip_str, pot_bb, eff_stack_bb): TexasSolver class-weighted range strings (oop=BB, ip=SB)."""
    bb_reach, sb_reach, pot, eff = reach_weights(node, blueprint)
    return _range_str(bb_reach), _range_str(sb_reach), pot, eff


def load_blueprint() -> dict:
    return json.loads((config.KNOWLEDGE_DIR / "ranges" / "preflop_blueprint.json").read_text(encoding="utf-8"))


def main() -> None:
    bp = load_blueprint()
    print("See-flop nodes (BB=OOP, SB=IP), reach-weighted ranges from the current blueprint:\n")
    for node in sd_leaves():
        oop, ip, pot, eff = reaching_ranges(node, bp)
        spr = eff / pot if pot else float("inf")
        print(f"=== {node}  pot={pot:g}bb  eff={eff:g}bb  SPR={spr:.1f} ===")
        print(f"  IP (SB) [{len(ip.split(',')) if ip else 0} classes]: {ip[:140]}")
        print(f"  OOP(BB) [{len(oop.split(',')) if oop else 0} classes]: {oop[:140]}\n")


if __name__ == "__main__":
    main()
