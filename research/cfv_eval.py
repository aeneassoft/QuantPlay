"""Phase B step 8 (gate-0c-robust architecture): extract per-combo RIVER-subgame counterfactual values (CFVs) from a
SOLVED river subgame (TexasSolver dump). These are the training labels for the CFV value net, which the flop resolver
will query at the turn->river LEAF (flop+turn solved EXPLICITLY; the net only stands in for the river subgame — the
construction gate-0c showed is robust, unlike collapsing a whole round into the net).

TexasSolver dumps the per-combo STRATEGY (action probabilities) at every action node of the dumped round, but NO EV/CFV
field and the terminals are IMPLICIT (an action with no child node = a terminal: FOLD, or a CHECK/CALL that closes the
betting -> showdown). The river is the LAST round (no chance after it) so the dump is COMPLETE (not truncated, unlike a
dump_rounds=2 turn solve). So we reconstruct the CFVs ourselves with a per-matchup backward pass over the betting tree.

Convention (zero-sum): river_value0(c0,c1) = winnings0 - total_contrib0, where total_contrib starts at pot/2 per player
(the sunk pot, split as the neutral baseline) + each player's river-street contribution; winnings0 = final pot if OOP
wins the showdown (pot/2 on a tie, 0 on a loss/own-fold). Then value0 + value1 == 0 exactly. CFV0(c0) = sum over the
OPPONENT's compatible combos c1 of river_value0 (card-removal handled by skipping overlapping (c0,c1)).

GATE B1 ($0, before any RunPod spend): zero-sum, determinism, nut/trash sanity, a finite reasonable range-EV.
Run: python -m extraction.cfv_eval [river_cache_file]
"""
from __future__ import annotations

import glob
import json
import sys

from pokerbot import config
from pokerbot.engine.evaluator import evaluate

POT = 20.0          # mass_solve solves the river cache at pot=20 (eff_stack is the _NN suffix in the filename)


def _combos_at(node, want_player):
    """The per-combo strategy keys at the first node belonging to `want_player` (= that player's range, board-removed)."""
    if node is None:
        return None
    if node.get("player") == want_player:
        strat = (node.get("strategy") or {}).get("strategy") or {}
        if strat:
            return list(strat.keys())
    for ch in (node.get("childrens") or {}).values():
        r = _combos_at(ch, want_player)
        if r:
            return r
    return None


def _probs(node, combo):
    """action-label -> prob for `combo` at `node`, or None if the combo isn't in this node's range."""
    s = node.get("strategy") or {}
    actions = s.get("actions") or []
    pr = (s.get("strategy") or {}).get(combo)
    if pr is None:
        return None
    return dict(zip(actions, pr))


def _overlap(c0, c1):
    return c0[:2] == c1[:2] or c0[:2] == c1[2:4] or c0[2:4] == c1[:2] or c0[2:4] == c1[2:4]


def _matchup_v0(node, c0, c1, sc0, sc1, board, start_pot):
    """Expected river_value0 for the (c0,c1) matchup from `node` under BOTH players' dumped strategies."""
    p = node.get("player")
    combo = c0 if p == 0 else c1
    pr = _probs(node, combo)
    if pr is None:                                  # combo not represented here -> no contribution (defensive)
        return 0.0
    kids = node.get("childrens") or {}
    val = 0.0
    for a, prob in pr.items():
        if prob <= 0:
            continue
        parts = a.split()
        kind = parts[0]
        amt = float(parts[1]) if len(parts) > 1 else None
        nsc0, nsc1 = sc0, sc1
        if kind in ("BET", "RAISE", "ALLIN"):       # the label number is the actor's river-street TOTAL ("to")
            if p == 0:
                nsc0 = amt
            else:
                nsc1 = amt
        elif kind == "CALL":
            if p == 0:
                nsc0 = sc1
            else:
                nsc1 = sc0
        child = kids.get(a)
        if child is not None and kind not in ("FOLD",):
            val += prob * _matchup_v0(child, c0, c1, nsc0, nsc1, board, start_pot)
        else:                                        # IMPLICIT terminal
            val += prob * _terminal_v0(kind, c0, c1, nsc0, nsc1, p, board, start_pot)
    return val


def _terminal_v0(kind, c0, c1, sc0, sc1, p, board, start_pot):
    tc0 = start_pot / 2 + sc0                         # OOP total contribution (sunk pot/2 + river street)
    pot = start_pot + sc0 + sc1
    if kind == "FOLD":
        return (0.0 - tc0) if p == 0 else (pot - tc0)   # OOP folds -> loses its contrib; IP folds -> OOP wins pot
    r0 = evaluate(board, [c0[:2], c0[2:4]])           # treys rank: LOWER = better
    r1 = evaluate(board, [c1[:2], c1[2:4]])
    w0 = pot if r0 < r1 else (0.0 if r0 > r1 else pot / 2)
    return w0 - tc0


def compute_river_cfv(root, board, start_pot: float = POT):
    """-> (cfv0{combo:cfv}, cfv1{combo:cfv}, oop_combos, ip_combos, stats). reach = 1 per combo (unweighted ranges).
    start_pot = pot at the START of river betting (the data-gen passes the actual sampled turn-boundary pot)."""
    oop = _combos_at(root, 0) or []
    ip = _combos_at(root, 1) or []
    cfv0 = {c: 0.0 for c in oop}
    cfv1 = {c: 0.0 for c in ip}
    total = 0.0
    n = 0
    for c0 in oop:
        for c1 in ip:
            if _overlap(c0, c1):
                continue
            mv = _matchup_v0(root, c0, c1, 0.0, 0.0, board, start_pot)
            cfv0[c0] += mv
            cfv1[c1] += -mv
            total += mv
            n += 1
    stats = {"n_matchups": n, "total_v0": total, "oop_range_ev_chips": (total / n if n else 0.0)}
    return cfv0, cfv1, oop, ip, stats


def _board_from_name(path):
    stem = path.split("\\")[-1].split("/")[-1].split("_")[0].replace(".json", "")
    return [stem[i:i + 2] for i in range(0, 10, 2)]


def main():
    files = sys.argv[1:] or sorted(glob.glob(str(config.DATA_DIR / "_gto_river_cache" / "*.json")))[:1]
    if not files:
        print("no river-cache files found")
        return
    f = files[0]
    root = json.loads(open(f, encoding="utf-8").read())
    board = _board_from_name(f)
    cfv0, cfv1, oop, ip, st = compute_river_cfv(root, board)
    cfv0b, _, _, _, _ = compute_river_cfv(json.loads(open(f, encoding="utf-8").read()), board)  # determinism re-run

    s0 = sum(cfv0.values())
    s1 = sum(cfv1.values())
    n1 = {c0: sum(1 for c1 in ip if not _overlap(c0, c1)) for c0 in oop}
    per0 = {c0: cfv0[c0] / n1[c0] for c0 in oop if n1[c0]}        # per-combo OOP EV (chips), normalized by opp reach
    top = sorted(per0, key=lambda c: -per0[c])[:5]
    bot = sorted(per0, key=lambda c: per0[c])[:5]

    print(f"=== B1 self-test: river CFV extractor on {f.split(chr(92))[-1].split('/')[-1]}  board={board} ===")
    print(f"  OOP combos {len(oop)} | IP combos {len(ip)} | matchups {st['n_matchups']} | pot {POT}")
    print(f"  range EV (OOP, chips) = {st['oop_range_ev_chips']:+.3f}  (|EV| < pot={POT} expected; balanced SRP ~small)")
    print(f"  ZERO-SUM: sum cfv0 {s0:+.3f}  + sum cfv1 {s1:+.3f}  = {s0 + s1:+.6f}  -> {'PASS' if abs(s0 + s1) < 1e-6 else 'FAIL'}")
    det = all(abs(cfv0[c] - cfv0b[c]) < 1e-9 for c in cfv0)
    print(f"  DETERMINISM: re-run identical -> {'PASS' if det else 'FAIL'}")
    print("  NUT-SANITY (top-5 OOP per-combo EV should be STRONG hands, bottom-5 WEAK):")
    for c in top:
        print(f"    +{per0[c]:+.2f}  {c}  (treys rank {evaluate(board, [c[:2], c[2:4]])})")
    for c in bot:
        print(f"    {per0[c]:+.2f}  {c}  (treys rank {evaluate(board, [c[:2], c[2:4]])})")
    nut_ok = (sum(evaluate(board, [c[:2], c[2:4]]) for c in top) / 5) < (sum(evaluate(board, [c[:2], c[2:4]]) for c in bot) / 5)
    print(f"  -> nut-sanity (mean top rank < mean bottom rank, lower=better): {'PASS' if nut_ok else 'FAIL'}")
    ok = abs(s0 + s1) < 1e-6 and det and nut_ok and abs(st["oop_range_ev_chips"]) < POT
    print(f"\n  GATE B1: {'PASS - CFV extractor validated; safe to scale the data-gen' if ok else 'FAIL - fix before any RunPod spend'}")


if __name__ == "__main__":
    main()
