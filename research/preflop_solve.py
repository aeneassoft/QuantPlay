"""A near-Nash HU 200bb PREFLOP blueprint via EXACT CFR+ over a real bet-size tree (the gpt-5.5/o3 Nash consult's
menu: limp / 2.5bb open / 3bet 10 / 4bet 24 / 5bet 60 / jam). The X-ray localized our -72 vs GTO Wizard to PREFLOP
(-50 strategy + -15 all-in spew = 87% of the loss); both consults say "compute a preflop blueprint SEPARATELY". This
is the cheap, LOCAL, highest-ROI fix.

WHY EXACT (not chance-sampled): a first chance-sampled version (one Bernoulli board/iter) left the DEEP, low-reach
nodes (4bet/5bet/jam) as pure noise — 72o called 200bb jams. So we PRECOMPUTE a 169x169 all-in equity matrix once
(cached), then run noise-free CFR+: every node converges on the clean equity signal regardless of reach.

CONTINUATION caveat (honest): non-all-in showdowns are scored as a CHECKDOWN run-out (w*pot - invested), i.e. NO
postflop play. This cleanly captures the ALL-IN DISCIPLINE (200bb pot-odds make QQ/AK -EV vs KK+) and gross range
construction, but UNDER-models postflop playability/realization (suited/connected). That residual = the high-quality
version (real postflop continuation per leaf) = the GCP scale-up, gated behind this cheap proof.

Run:  python -m extraction.preflop_solve [--iters N] [--sims S] [--rebuild-eq]
Output: knowledge_base/ranges/preflop_blueprint.json  { node: { class: {action: prob} } }
"""
from __future__ import annotations

import argparse
import json
import random
import time

from pokerbot import config
from pokerbot.engine.cards import all_hand_classes, expand_class, make_deck
from pokerbot.engine.evaluator import evaluate
from research.preflop_leaves import leaf_w

# Node: (to_act, sb_inv, bb_inv, [(action, kind, n_sb, n_bb, next)]). to_act 0=SB(button), 1=BB.
# kind: foldSB (SB net -sb_inv) / foldBB (SB net +bb_inv) / sd (showdown w*pot - n_sb) / node.
TREE = {
    "ROOT":  (0, 0.5, 1.0, [("fold", "foldSB", 0, 0, None), ("limp", "node", 1.0, 1.0, "LIMP"),
                            ("open", "node", 2.5, 1.0, "OPEN")]),
    "LIMP":  (1, 1.0, 1.0, [("check", "sd", 1.0, 1.0, None), ("iso", "node", 1.0, 4.5, "ISO")]),
    "ISO":   (0, 1.0, 4.5, [("fold", "foldSB", 0, 0, None), ("call", "sd", 4.5, 4.5, None)]),
    "OPEN":  (1, 2.5, 1.0, [("fold", "foldBB", 0, 0, None), ("call", "sd", 2.5, 2.5, None),
                            ("3bet", "node", 2.5, 10.0, "3BET")]),
    "3BET":  (0, 2.5, 10.0, [("fold", "foldSB", 0, 0, None), ("call", "sd", 10.0, 10.0, None),
                             ("4bet", "node", 24.0, 10.0, "4BET")]),
    "4BET":  (1, 24.0, 10.0, [("fold", "foldBB", 0, 0, None), ("call", "sd", 24.0, 24.0, None),
                              ("5bet", "node", 24.0, 60.0, "5BET"), ("jam", "node", 24.0, 200.0, "JAMSB")]),
    "5BET":  (0, 24.0, 60.0, [("fold", "foldSB", 0, 0, None), ("call", "sd", 60.0, 60.0, None),
                              ("jam", "node", 200.0, 60.0, "JAMBB")]),
    "JAMSB": (0, 24.0, 200.0, [("fold", "foldSB", 0, 0, None), ("call", "sd_allin", 200.0, 200.0, None)]),
    "JAMBB": (1, 200.0, 60.0, [("fold", "foldBB", 0, 0, None), ("call", "sd_allin", 200.0, 200.0, None)]),
}
CLASSES = all_hand_classes()                 # 169, fixed order
IDX = {c: i for i, c in enumerate(CLASSES)}
N = len(CLASSES)
KAPPA = 0.0                                   # IP (button=SB) postflop realization premium on see-flop leaves
LEAF_KMAP = None                              # {node: kappa_node} from a calibration leaf-table (--leaf-table); None = global-kappa checkdown
EQ_CACHE = config.KNOWLEDGE_DIR / "ranges" / "preflop_eqmatrix.json"


def build_eqmatrix(sims: int, rng: random.Random) -> list[list[float]]:
    """169x169 all-in equity: EQ[i][j] = P(class_i beats class_j) over random combos+board (card-removal exact per
    sample). Upper triangle by MC, lower by 1-symmetry, diagonal 0.5."""
    combos = [expand_class(c) for c in CLASSES]
    deck = make_deck()
    EQ = [[0.5] * N for _ in range(N)]
    t0 = time.time()
    for i in range(N):
        ci = combos[i]
        for j in range(i + 1, N):
            cj = combos[j]
            wins = cnt = 0.0
            for _ in range(sims):
                h1 = rng.choice(ci)
                h2 = rng.choice(cj)
                if h1[0] in h2 or h1[1] in h2:
                    continue                                   # shared card -> impossible matchup combo
                used = (h1[0], h1[1], h2[0], h2[1])
                board = rng.sample(deck, 5)
                if any(b in used for b in board):
                    board = [c for c in rng.sample(deck, 9) if c not in used][:5]
                s1, s2 = evaluate(board, list(h1)), evaluate(board, list(h2))
                wins += 1.0 if s1 < s2 else (0.5 if s1 == s2 else 0.0)
                cnt += 1
            e = wins / cnt if cnt else 0.5
            EQ[i][j] = e
            EQ[j][i] = 1.0 - e
        if (i + 1) % 30 == 0:
            print(f"  eq row {i+1}/{N} | {time.time()-t0:.0f}s", flush=True)
    return EQ


def load_eqmatrix(sims: int, rebuild: bool) -> list[list[float]]:
    if EQ_CACHE.exists() and not rebuild:
        d = json.loads(EQ_CACHE.read_text())
        if d.get("n") == N and d.get("sims", 0) >= sims:
            print(f"  eq matrix cached (sims={d['sims']})", flush=True)
            return d["eq"]
    print(f"  building eq matrix ({sims} sims/pair, {N*(N-1)//2} pairs) ...", flush=True)
    EQ = build_eqmatrix(sims, random.Random(11))
    EQ_CACHE.write_text(json.dumps({"n": N, "sims": sims, "eq": EQ}))
    return EQ


def traverse(node, i, j, EQ, r_sb, r_bb, regret, strat):
    """SB's counterfactual value at `node`; i=SB class idx, j=BB class idx. Exact (EQ[i][j] = SB equity)."""
    to_act, _si, _bi, acts = TREE[node]
    cls = i if to_act == 0 else j
    key = (node, cls)
    reg = regret.setdefault(key, [0.0] * len(acts))
    pos = [x if x > 0 else 0.0 for x in reg]
    s = sum(pos)
    sigma = [x / s for x in pos] if s > 1e-12 else [1.0 / len(acts)] * len(acts)
    util = [0.0] * len(acts)
    node_val = 0.0
    for k, (_a, kind, n_sb, n_bb, nxt) in enumerate(acts):
        if kind == "foldSB":
            u = -_si
        elif kind == "foldBB":
            u = _bi
        elif kind == "sd_allin":
            u = EQ[i][j] * (n_sb + n_bb) - n_sb            # all-in run-out: exact equity, no realization
        elif kind == "sd":
            w = leaf_w(node, EQ[i][j], LEAF_KMAP, KAPPA)    # calibrated per-node realization, else global-kappa checkdown
            u = w * (n_sb + n_bb) - n_sb
        else:
            nr_sb = r_sb * (sigma[k] if to_act == 0 else 1.0)
            nr_bb = r_bb * (sigma[k] if to_act == 1 else 1.0)
            u = traverse(nxt, i, j, EQ, nr_sb, nr_bb, regret, strat)
        util[k] = u
        node_val += sigma[k] * u
    rch = r_bb if to_act == 0 else r_sb
    own = r_sb if to_act == 0 else r_bb
    sign = 1.0 if to_act == 0 else -1.0          # util is SB-relative; BB minimizes it
    st = strat.setdefault(key, [0.0] * len(acts))
    for k in range(len(acts)):
        reg[k] += rch * sign * (util[k] - node_val)
        if reg[k] < 0.0:
            reg[k] = 0.0                          # CFR+ : floor regrets at 0
        st[k] += own * sigma[k]
    return node_val


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iters", type=int, default=400)
    ap.add_argument("--sims", type=int, default=600)
    ap.add_argument("--realize-kappa", type=float, default=0.05,
                    help="IP postflop realization premium on see-flop leaves (0=pure checkdown). Heuristic; see NOTES.")
    ap.add_argument("--rebuild-eq", action="store_true")
    ap.add_argument("--leaf-table", default=None,
                    help="calibration leaf-table JSON -> graft per-node realization (extraction.preflop_calibrate)")
    args = ap.parse_args()
    global KAPPA, LEAF_KMAP
    KAPPA = args.realize_kappa
    t0 = time.time()
    EQ = load_eqmatrix(args.sims, args.rebuild_eq)
    out_name = "preflop_blueprint.json"
    if args.leaf_table:
        from research.preflop_leaves import load_leaf_table, build_kappa_map
        from research.preflop_ranges import load_blueprint as _load_bp
        LEAF_KMAP = build_kappa_map(load_leaf_table(args.leaf_table), _load_bp(), EQ)
        out_name = "preflop_blueprint_solvergraft.json"
        print("  GRAFT per-node kappa: " + ", ".join(f"{k}={v:+.3f}" for k, v in LEAF_KMAP.items()), flush=True)
    cw = [len(expand_class(c)) for c in CLASSES]          # combo weights = deal reach
    regret, strat = {}, {}
    print(f"  CFR+ : {args.iters} iters x {N*N} pairs ...", flush=True)
    for t in range(1, args.iters + 1):
        for i in range(N):
            ri = cw[i]
            for j in range(N):
                traverse("ROOT", i, j, EQ, ri, cw[j], regret, strat)
        if t % 50 == 0:
            print(f"  iter {t}/{args.iters} | {time.time()-t0:.0f}s", flush=True)
    out = {}
    for (node, cls), s in strat.items():
        tot = sum(s)
        acts = [a[0] for a in TREE[node][3]]
        name = CLASSES[cls]
        out.setdefault(node, {})[name] = {acts[k]: round(s[k] / tot, 4) for k in range(len(acts))} if tot > 1e-9 \
            else {a: round(1.0 / len(acts), 4) for a in acts}
    p = config.KNOWLEDGE_DIR / "ranges" / out_name
    p.write_text(json.dumps(out, indent=0), encoding="utf-8")
    print(f"DONE {args.iters} iters, kappa={KAPPA}, graft={'on' if LEAF_KMAP else 'off'} in {time.time()-t0:.0f}s -> {p}", flush=True)
    for node in ("ROOT", "OPEN", "4BET", "JAMSB"):
        for cls in ("AA", "QQ", "AKo", "76s", "72o"):
            if node in out and cls in out[node]:
                pr = {k: v for k, v in out[node][cls].items() if v > 0.02}
                print(f"  {node:5s} {cls}: {pr}", flush=True)


if __name__ == "__main__":
    main()
