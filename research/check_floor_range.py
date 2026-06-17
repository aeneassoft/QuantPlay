"""GATE A3-FLOOR (the keystone's second half): is the action-consistent tracker's per-combo P(call) closer to
the solver's TRUE post-call range than the FLOOR's current `_narrow` heuristic (`bot._narrow`: keep the top
keep_frac of combos by ABSOLUTE board strength, every bluff/draw DROPPED)?

Context: the Bayesian RangeTracker got wired into the RESOLVER this session (GATE A3, `check_range_l1.py`). But
the FLOOR (which plays the majority of hands) still builds the villain range with `_villain_range`+`_narrow` =
top-X%-by-made-strength → it feeds `equity_vs_range` an ARTIFICIALLY-STRONG range (no bluffs/draws) → hero
under-rates his equity → systematically OVER-FOLDS facing bets (the "poisons the floor's facing-bet/bluffcatch
math" leak in CLAUDE.md). This gate decides whether replacing `_narrow` with the tracker is GROUNDED.

Same held-out-by-board split + net + facing-bet nodes as `check_range_l1.py`. At each node we form FOUR
post-call distributions over the node's combos and score each by L1 vs the solver truth (y_call):
  true   ∝ y_call_solver                          (ground truth = the solver's real continuing range)
  adv    ∝ P_call_advisor                          (the Bayesian tracker's CALL operator — the candidate)
  narrow ∝ 1[combo in top-60% by `strength`] else 0 (the FLOOR's `_narrow`, facing one bet → keep_frac=0.60)
  noop   ∝ uniform                                 (do-nothing baseline, = the existing GATE A3 reference)
`strength` (= 1 − evaluate/7462) is the SAME made-hand rank `_narrow` sorts on, so the cut is faithful.

GATE: per street, mean L1(adv,true) < L1(narrow,true) → the tracker is a grounded improvement over the floor
heuristic → safe to wire it into bot.py's villain-equity path. o3 bound: extra exploitability ≤ (pot/2)·L1, so a
lower L1 is a strictly tighter exploit bound, not just a held-out-MSE win. $0, no live solve.
Run: python -m extraction.check_floor_range
"""
from __future__ import annotations

import json
import random
from collections import defaultdict

import numpy as np
import torch
import torch.nn as nn

from pokerbot import config
from research.train_defense_advisor import feat, STREETS

KEEP_FRAC_ONE_BET = 0.60     # bot._narrow's keep_frac for aggression==1 (facing a single bet)


def _norm(v: np.ndarray) -> np.ndarray:
    s = v.sum()
    return v / s if s > 0 else np.full_like(v, 1.0 / len(v))


def _narrow_post(rs: list[dict]) -> np.ndarray:
    """The floor's `_narrow` as a post-bet distribution over the node's combos: keep the top KEEP_FRAC by
    made-hand strength (higher `strength` = lower evaluate = better), uniform over the kept, 0 for the dropped."""
    strength = np.array([r["strength"] for r in rs])
    keep = max(1, int(len(rs) * KEEP_FRAC_ONE_BET))
    order = np.argsort(-strength)               # descending strength = _narrow's "lower evaluate first"
    w = np.zeros(len(rs))
    w[order[:keep]] = 1.0
    return _norm(w)


def main() -> None:
    rows = [json.loads(x) for x in (config.DATA_DIR / "defense_data.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    boards = sorted({r["board"] for r in rows})
    rng = random.Random(7)              # EXACT same split as train_defense_advisor / check_range_l1
    rng.shuffle(boards)
    held = set(boards[:len(boards) // 5])
    rte = [r for r in rows if r["board"] in held]

    ck = torch.load(config.KNOWLEDGE_DIR / "postflop" / "defense_advisor.pt", map_location="cpu")
    net = nn.Sequential(nn.Linear(ck["dims"], 64), nn.ReLU(), nn.Linear(64, 64), nn.ReLU(), nn.Linear(64, 3))
    net.load_state_dict(ck["state"])
    net.eval()
    X = torch.tensor([feat(r) for r in rte], dtype=torch.float32)
    with torch.no_grad():
        P = torch.softmax(net(X), dim=1).numpy()       # (N,3) = advisor (P_fold, P_call, P_raise)
    for r, p in zip(rte, P):
        r["_padv_call"] = float(p[1])

    nodes: dict = defaultdict(list)
    for r in rte:
        nodes[(r["street"], r["board"], r["role"], r["size_faced"])].append(r)

    # street -> [sum L1_adv, sum L1_narrow, sum L1_noop, n_nodes]
    per: dict = defaultdict(lambda: [0.0, 0.0, 0.0, 0])
    for (street, _b, _role, _sz), rs in nodes.items():
        if len(rs) < 4:
            continue
        ycall = np.array([r["y_call"] for r in rs])
        if ycall.sum() <= 0:
            continue
        true_post = _norm(ycall)
        adv_post = _norm(np.array([r["_padv_call"] for r in rs]))
        narrow_post = _narrow_post(rs)
        noop_post = np.full(len(rs), 1.0 / len(rs))
        per[street][0] += float(np.abs(adv_post - true_post).sum())
        per[street][1] += float(np.abs(narrow_post - true_post).sum())
        per[street][2] += float(np.abs(noop_post - true_post).sum())
        per[street][3] += 1

    print("GATE A3-FLOOR - post-call range L1 vs the solver TRUE range (held-out by board):")
    print("  the candidate (adv = Bayesian tracker) vs the FLOOR's _narrow (top-60%-by-strength) vs do-nothing\n")
    print("  street |  L1_adv   L1_narrow   L1_noop  |  adv vs narrow   nodes")
    ok = True
    tot = [0.0, 0.0, 0.0, 0]
    for street in STREETS:
        sa, sn, sno, n = per[street]
        if n == 0:
            continue
        a, nar, no = sa / n, sn / n, sno / n
        tot[0] += sa; tot[1] += sn; tot[2] += sno; tot[3] += n
        flag = "" if a < nar else "   <- NO-GO (tracker worse than _narrow)"
        if a >= nar:
            ok = False
        print(f"  {street:6s} |  {a:.4f}   {nar:.4f}    {no:.4f}  |    {100*(nar-a)/nar:+5.0f}%       {n}{flag}")
    if tot[3]:
        a, nar, no = tot[0] / tot[3], tot[1] / tot[3], tot[2] / tot[3]
        print(f"  {'ALL':6s} |  {a:.4f}   {nar:.4f}    {no:.4f}  |    {100*(nar-a)/nar:+5.0f}%       {tot[3]}")
    print("\nGATE: per-street L1_adv < L1_narrow -> the action-consistent tracker beats the floor's _narrow")
    print("heuristic at predicting the solver's continuing range -> wire the tracker into bot.py's villain-equity.")
    print(f"\nVERDICT: {'PASS - wire the tracker into the floor (replace _narrow)' if ok else 'MIXED - see per-street flags'}")


if __name__ == "__main__":
    main()
