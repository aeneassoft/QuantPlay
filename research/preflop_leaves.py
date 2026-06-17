"""Step 4 of the solver-grafted-preflop plan: the injectable see-flop leaf-value seam.

The blueprint's checkdown values a see-flop leaf as `w = e + kappa*4*e*(1-e)` (e = all-in equity EQ[i][j], kappa a
single global guess = 0.05). The calibration (extraction.preflop_calibrate) MEASURES the range-average realized
fraction `w_node` per see-flop node from real TexasSolver play. We graft that by re-leveling kappa PER NODE: find
kappa_node so the reach-weighted average of `e + kappa_node*4*e*(1-e)` equals the measured w_node. This keeps the
per-(i,j) shape (a strong hand still gets a higher leaf value via its larger e) but grounds the LEVEL in real play.

  kappa_node = (w_node - E[e]) / (4 * E[e*(1-e)]),   E[] reach-weighted over IP(SB) class i, OOP(BB) class j.

leaf_w(node, e, kmap, default_kappa) is the single seam called by both preflop_solve.traverse and
preflop_exploit._leaf. kmap=None or node-absent -> the original checkdown (byte-identical default behavior).
"""
from __future__ import annotations

import json


def load_leaf_table(path) -> dict:
    return json.loads(open(path, encoding="utf-8").read())


def build_kappa_map(table: dict, blueprint: dict, EQ) -> dict:
    """{node: kappa_node} fitting each node's measured w_node to the checkdown's reach-weighted average.
    Uses the CURRENT blueprint's reach weights (the ranges the calibration solved) + the same EQ matrix."""
    from research.preflop_ranges import reach_weights
    from research.preflop_solve import N
    kmap = {}
    for node, rec in table.items():
        w_node = rec.get("w_node")
        if w_node is None:
            continue
        oop_w, ip_w, _pot, _eff = reach_weights(node, blueprint)
        s_ip, s_oop = sum(ip_w), sum(oop_w)
        if s_ip <= 0 or s_oop <= 0:
            continue
        e_mean = e1_mean = 0.0
        for i in range(N):
            wi = ip_w[i] / s_ip
            if wi <= 0:
                continue
            row = EQ[i]
            for j in range(N):
                wj = oop_w[j] / s_oop
                if wj <= 0:
                    continue
                e = row[j]                    # IP(SB) class i all-in equity vs OOP(BB) class j
                e_mean += wi * wj * e
                e1_mean += wi * wj * e * (1.0 - e)
        kmap[node] = (w_node - e_mean) / (4.0 * e1_mean) if e1_mean > 1e-9 else 0.0
    return kmap


def leaf_w(node: str, e: float, kmap: dict | None, default_kappa: float) -> float:
    """Realized see-flop fraction for all-in equity e at `node`: calibrated kappa_node if present, else the
    global checkdown kappa. Clipped to [0,1]."""
    k = kmap.get(node, default_kappa) if kmap else default_kappa
    w = e + k * 4.0 * e * (1.0 - e)
    return 1.0 if w > 1.0 else (0.0 if w < 0.0 else w)
