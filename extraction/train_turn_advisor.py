"""#41: train the TURN advisor (predict solver P_bet on the turn from blocker/potential features) and compare
to the FREQUENCY-ONLY baseline (per role x texture mean). Held out BY BOARD (4-card) to test generalization.
Mirrors train_advisor.py (the flop one); subsamples to CAP rows so it trains fast on the CPU pod. Saves
knowledge_base/postflop/turn_advisor.pt only if the feature model beats the table by >3% (gpt-5.5's rule).
Run ON THE POD after the solve: PYTHONPATH=. python3 -m extraction.train_turn_advisor
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
BOOLS = ["flush_draw", "backdoor_flush", "nut_flush_blocker", "made_straight", "oesd", "gutshot", "has_draw"]
CAP = 2_000_000


def feat(r: dict) -> list:
    v = [1.0 if r["tier"] == t else 0.0 for t in TIERS]
    v += [1.0 if r["tex"] == t else 0.0 for t in TEX]
    v.append(1.0 if r["role"] == "IP" else 0.0)
    v += [1.0 if r[k] else 0.0 for k in BOOLS]
    v.append(r["overcards"] / 2.0)
    v.append(float(r["strength"]))
    return v


def main() -> None:
    rows = [json.loads(x) for x in (config.DATA_DIR / "turn_data.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    rng = random.Random(7)
    if len(rows) > CAP:
        rows = rng.sample(rows, CAP)
        print(f"subsampled to {CAP} rows")
    boards = sorted({r["board"] for r in rows})
    rng.shuffle(boards)
    held = set(boards[:max(1, len(boards) // 5)])

    Xtr, ytr, Xte, yte, rte = [], [], [], [], []
    acc = defaultdict(lambda: [0, 0.0])
    for r in rows:
        x, y = feat(r), r["y_bet"]
        if r["board"] in held:
            Xte.append(x); yte.append(y); rte.append(r)
        else:
            Xtr.append(x); ytr.append(y)
            acc[(r["role"], r["tex"])][0] += 1
            acc[(r["role"], r["tex"])][1] += y
    base = {k: s / n for k, (n, s) in acc.items()}
    base_mse = float(np.mean([(base.get((r["role"], r["tex"]), 0.3) - r["y_bet"]) ** 2 for r in rte]))

    Xtr_t = torch.tensor(Xtr, dtype=torch.float32)
    ytr_t = torch.tensor(ytr, dtype=torch.float32).unsqueeze(1)
    Xte_t = torch.tensor(Xte, dtype=torch.float32)
    yte_t = torch.tensor(yte, dtype=torch.float32).unsqueeze(1)
    net = nn.Sequential(nn.Linear(Xtr_t.shape[1], 64), nn.ReLU(), nn.Linear(64, 64), nn.ReLU(),
                        nn.Linear(64, 1), nn.Sigmoid())
    opt = torch.optim.Adam(net.parameters(), lr=1e-3)
    for _ep in range(60):
        idx = torch.randperm(len(Xtr_t))
        for i in range(0, len(Xtr_t), 4096):
            b = idx[i:i + 4096]
            opt.zero_grad()
            loss = ((net(Xtr_t[b]) - ytr_t[b]) ** 2).mean()
            loss.backward()
            opt.step()
    with torch.no_grad():
        mlp_mse = float(((net(Xte_t) - yte_t) ** 2).mean().item())

    print(f"held-out-by-board TURN P_bet MSE:  freq-baseline {base_mse:.4f}  |  MLP {mlp_mse:.4f}  "
          f"({100*(base_mse-mlp_mse)/base_mse:+.0f}% vs baseline)  | train={len(Xtr)} test={len(Xte)} boards={len(boards)}")
    if mlp_mse < base_mse * 0.97:
        (config.KNOWLEDGE_DIR / "postflop").mkdir(parents=True, exist_ok=True)
        torch.save({"state": net.state_dict(), "dims": Xtr_t.shape[1]},
                   config.KNOWLEDGE_DIR / "postflop" / "turn_advisor.pt")
        print("MLP beats the baseline -> saved turn_advisor.pt (wire into bot.py turn branch)")
    else:
        print("MLP does NOT clearly beat the baseline -> ship the turn freq table, skip the net")


if __name__ == "__main__":
    main()
