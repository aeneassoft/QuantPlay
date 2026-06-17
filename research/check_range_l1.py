"""GATE A3 (range-tracker keystone): does the defense advisor's per-combo P(call), used as the range-update
operator on a CALL, move the tracked range CLOSER to the solver's TRUE post-call range than doing NOTHING
(legality-only)? The o3 safety theorem: the extra exploitability the tracker can inject is <= (pot/2)*L1, where
L1 is the villain-range error. So a LOWER L1 is a GROUNDED proof that the keystone widen (range_tracker._p_call
now reweights on ALL streets, not flop-only) actually helps — not just a held-out MSE win. Held out BY BOARD
(same seed=7 split as train_defense_advisor). $0, no live solve, reuses the SAME features + the SAME net.

For each held-out facing-bet node (street, board, role, size_faced) we form three post-call distributions over the
combos in that node, with a UNIFORM prior so we isolate the CALL-update operator's own contribution:
  true_post[c] ~ y_call_solver[c]   (the solver's true post-call range = the ground truth)
  adv_post[c]  ~ p_call_advisor[c]  (widen ON:  the tracker reweight  d[c] *= P_call(advisor))
  noop_post[c] ~ 1                  (widen OFF: legality-only = leave the prior untouched = "do nothing")
GATE: per street (esp. turn/river) mean L1(adv,true) < L1(noop,true). Run: python -m extraction.check_range_l1
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


def _norm(v: np.ndarray) -> np.ndarray:
    s = v.sum()
    return v / s if s > 0 else np.full_like(v, 1.0 / len(v))


def main() -> None:
    rows = [json.loads(x) for x in (config.DATA_DIR / "defense_data.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    boards = sorted({r["board"] for r in rows})
    rng = random.Random(7)              # EXACT same split as train_defense_advisor -> honest held-out
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

    per: dict = defaultdict(lambda: [0.0, 0.0, 0])     # street -> [sum L1_adv, sum L1_noop, n_nodes]
    for (street, _b, _role, _sz), rs in nodes.items():
        if len(rs) < 4:                                # need a few combos for a meaningful range distribution
            continue
        ycall = np.array([r["y_call"] for r in rs])
        if ycall.sum() <= 0:
            continue
        padv = np.array([r["_padv_call"] for r in rs])
        true_post = _norm(ycall)
        adv_post = _norm(padv)
        noop_post = np.full(len(rs), 1.0 / len(rs))    # uniform = the prior left untouched (legality-only)
        per[street][0] += float(np.abs(adv_post - true_post).sum())
        per[street][1] += float(np.abs(noop_post - true_post).sum())
        per[street][2] += 1

    print("GATE A3 - range-update L1 vs the solver's TRUE post-call range (held-out by board, uniform prior):")
    print("  street |  L1_adv (widen ON)   L1_noop (do-nothing)   improvement   nodes")
    ok = True
    for street in STREETS:
        sa, sn, n = per[street]
        if n == 0:
            continue
        a, no = sa / n, sn / n
        flag = "" if a < no else "   <- NO-GO (update hurts)"
        if street in ("turn", "river") and a >= no:
            ok = False
        print(f"  {street:6s} |      {a:.4f}              {no:.4f}          {100*(no-a)/no:+5.0f}%      {n}{flag}")
    print("GATE: turn/river L1_adv < L1_noop -> the advisor CALL-update sharpens the range toward the solver truth.")
    print("o3 bound: extra exploitability injected <= (pot/2)*L1, so a lower L1 = a strictly tighter exploit bound.")
    print(f"\nVERDICT: {'PASS - keep the all-streets widen' if ok else 'FAIL - revert turn/river to legality-only'}")


if __name__ == "__main__":
    main()
