"""MVP B3 (+ river pull-forward): train the FACING-BET DEFENSE advisor (solver fold/call/raise mix per combo) on
the flop+river defense data, gated against TWO street-aware baselines, held out BY BOARD:
  (A) CONTEXT-COLLAPSED = mean mix per (street, role, texture, size-bucket)  -> ignores the hand (the enemy).
  (B) STRENGTH-ONLY     = mean mix per (street, size-bucket, strength-decile) -> ~the equity-threshold heuristic.
The MEANINGFUL bar: the net must beat (B) -> it captures defense beyond raw strength (blockers/draws/texture).
Street is a feature (flop/turn/river one-hot) so one advisor covers both streets + their distinct size ranges
(river overbets 2.5-10x). Beats (B) by >3% -> ships defense_advisor.pt. Run: python -m extraction.train_defense_advisor
"""
from __future__ import annotations

import json
import random
from collections import defaultdict

import numpy as np
import torch
import torch.nn as nn

from pokerbot import config

TIERS = ["air", "medium", "strong"]
TEX = ["high", "low", "connected", "monotone", "paired"]
STREETS = ["flop", "turn", "river"]
BOOLS = ["flush_draw", "backdoor_flush", "nut_flush_blocker", "made_straight", "oesd", "gutshot", "has_draw"]
SIZES = (0.35, 0.66, 0.75, 2.5, 5.0, 10.0)


def size_bucket(s: float) -> float:
    return min(SIZES, key=lambda b: abs(b - s))


def feat(r: dict) -> list:
    v = [1.0 if r["tier"] == t else 0.0 for t in TIERS]
    v += [1.0 if r["tex"] == t else 0.0 for t in TEX]
    v += [1.0 if r.get("street", "flop") == s else 0.0 for s in STREETS]
    v.append(1.0 if r["role"] == "IP" else 0.0)
    v += [1.0 if r[k] else 0.0 for k in BOOLS]
    v.append(r["overcards"] / 2.0)
    v.append(float(r["strength"]))
    v.append(float(r["size_faced"]))
    return v


def y3(r: dict) -> list:
    return [r["y_fold"], r["y_call"], r["y_raise"]]


def main() -> None:
    rows = [json.loads(x) for x in (config.DATA_DIR / "defense_data.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    boards = sorted({r["board"] for r in rows})
    rng = random.Random(7)
    rng.shuffle(boards)
    held = set(boards[:len(boards) // 5])

    Xtr, Ytr, Xte, Yte, rte = [], [], [], [], []
    collapsed = defaultdict(lambda: [0, np.zeros(3)])
    strength = defaultdict(lambda: [0, np.zeros(3)])
    for r in rows:
        yv = np.array(y3(r))
        st = r.get("street", "flop")
        if r["board"] in held:
            Xte.append(feat(r)); Yte.append(yv); rte.append(r)
        else:
            Xtr.append(feat(r)); Ytr.append(yv)
            collapsed[(st, r["role"], r["tex"], size_bucket(r["size_faced"]))][0] += 1
            collapsed[(st, r["role"], r["tex"], size_bucket(r["size_faced"]))][1] += yv
            sd = int(min(9, r["strength"] * 10))
            strength[(st, size_bucket(r["size_faced"]), sd)][0] += 1
            strength[(st, size_bucket(r["size_faced"]), sd)][1] += yv

    cbase = {k: s / n for k, (n, s) in collapsed.items()}
    sbase = {k: s / n for k, (n, s) in strength.items()}
    DEF = np.array([0.5, 0.35, 0.15])

    def cb_pred(r):
        return cbase.get((r.get("street", "flop"), r["role"], r["tex"], size_bucket(r["size_faced"])), DEF)

    def sb_pred(r):
        return sbase.get((r.get("street", "flop"), size_bucket(r["size_faced"]), int(min(9, r["strength"] * 10))), DEF)

    cbase_mse = float(np.mean([np.mean((cb_pred(r) - y3(r)) ** 2) for r in rte]))
    sbase_mse = float(np.mean([np.mean((sb_pred(r) - y3(r)) ** 2) for r in rte]))

    Xtr_t = torch.tensor(Xtr, dtype=torch.float32)
    Ytr_t = torch.tensor(np.array(Ytr), dtype=torch.float32)
    Xte_t = torch.tensor(Xte, dtype=torch.float32)
    Yte_t = torch.tensor(np.array(Yte), dtype=torch.float32)
    net = nn.Sequential(nn.Linear(Xtr_t.shape[1], 64), nn.ReLU(), nn.Linear(64, 64), nn.ReLU(), nn.Linear(64, 3))
    opt = torch.optim.Adam(net.parameters(), lr=1e-3)
    for _ep in range(60):
        idx = torch.randperm(len(Xtr_t))
        for i in range(0, len(Xtr_t), 4096):
            b = idx[i:i + 4096]
            opt.zero_grad()
            loss = ((torch.softmax(net(Xtr_t[b]), dim=1) - Ytr_t[b]) ** 2).mean()
            loss.backward()
            opt.step()
    with torch.no_grad():
        mlp_mse = float(((torch.softmax(net(Xte_t), dim=1) - Yte_t) ** 2).mean().item())
        # per-street held-out MSE (net vs strength baseline)
        per = {}
        for street in STREETS:
            sidx = [i for i, r in enumerate(rte) if r.get("street", "flop") == street]
            if sidx:
                p = torch.softmax(net(Xte_t[sidx]), dim=1)
                nm = float(((p - Yte_t[sidx]) ** 2).mean().item())
                bm = float(np.mean([np.mean((sb_pred(rte[i]) - y3(rte[i])) ** 2) for i in sidx]))
                per[street] = (bm, nm, len(sidx))

    print("held-out-by-board defense (fold/call/raise) MSE:")
    print(f"  (A) context-collapsed : {cbase_mse:.4f}")
    print(f"  (B) strength (~heur)  : {sbase_mse:.4f}   <- bar")
    print(f"  (C) defense MLP       : {mlp_mse:.4f}   ({100*(sbase_mse-mlp_mse)/sbase_mse:+.0f}% vs B)")
    for street, (bm, nm, n) in per.items():
        print(f"      [{street}] B {bm:.4f} -> MLP {nm:.4f} ({100*(bm-nm)/bm:+.0f}%, n={n})")
    if mlp_mse < sbase_mse * 0.97:
        torch.save({"state": net.state_dict(), "dims": Xtr_t.shape[1]},
                   config.KNOWLEDGE_DIR / "postflop" / "defense_advisor.pt")
        print("  -> beats the strength heuristic: defense_advisor.pt SAVED (flop+river)")
    else:
        print("  -> does NOT beat strength: NO-GO")


if __name__ == "__main__":
    main()
