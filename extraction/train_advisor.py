"""Task #38: train the GTO-floor advisor (predict solver P_bet from blocker/potential features) and compare to
the FREQUENCY-ONLY baseline (per role x texture mean = the texture_freqs table). Held out BY BOARD (tests
generalization to unseen boards). If the feature model does NOT beat the baseline, we ship the table, not a net
(gpt-5.5's rule). Run: python -m extraction.train_advisor
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


def feat(r: dict) -> list:
    v = [1.0 if r["tier"] == t else 0.0 for t in TIERS]
    v += [1.0 if r["tex"] == t else 0.0 for t in TEX]
    v.append(1.0 if r["role"] == "IP" else 0.0)
    v += [1.0 if r[k] else 0.0 for k in BOOLS]
    v.append(r["overcards"] / 2.0)
    v.append(float(r["strength"]))
    return v


def main() -> None:
    rows = [json.loads(x) for x in (config.DATA_DIR / "advisor_data.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    boards = sorted({r["board"] for r in rows})
    rng = random.Random(7)
    rng.shuffle(boards)
    held = set(boards[:len(boards) // 5])

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
    base_mse = float(np.mean([(base.get((r["role"], r["tex"]), 0.4) - r["y_bet"]) ** 2 for r in rte]))

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

    print(f"held-out-by-board P_bet MSE:  freq-baseline {base_mse:.4f}  |  MLP {mlp_mse:.4f}  "
          f"({100*(base_mse-mlp_mse)/base_mse:+.0f}% vs baseline)")
    if mlp_mse < base_mse * 0.97:
        torch.save({"state": net.state_dict(), "dims": Xtr_t.shape[1]},
                   config.KNOWLEDGE_DIR / "postflop" / "advisor.pt")
        print("MLP beats the baseline -> saved data/advisor.pt (wire in #39)")
    else:
        print("MLP does NOT clearly beat the baseline -> SHIP THE TABLE, skip the net (per gpt-5.5)")


if __name__ == "__main__":
    main()
