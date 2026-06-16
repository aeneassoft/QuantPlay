"""Train the SHORT-DECK bet-vs-check advisor on data/sd_advisor_data.jsonl, held out BY BOARD, vs the
(role, texture) frequency baseline. This is a SANITY (does a generalizing SD advisor learn the solver's flop
strategy beyond the texture+role bucket mean?) — a policy-match check, NOT the near-GTO proof. The HONEST near-GTO
metric is EV-gap + matched-tree BR/LBR (the next build; best on SD RIVER subgames where it's terminal+computable,
since these flop dumps have no turn/river continuation). Run: python -m extraction.train_sd_advisor
"""
from __future__ import annotations

import json
import random
from collections import defaultdict

import numpy as np
import torch
import torch.nn as nn

from pokerbot import config

TEX = ["twotone", "paired", "connected", "mono", "dry"]


def feat(r: dict) -> list:
    v = [float(r["strength"]), 1.0 if r["role"] == "IP" else 0.0]
    v += [1.0 if r["tex"] == t else 0.0 for t in TEX]
    return v


def main() -> None:
    rows = [json.loads(x) for x in (config.DATA_DIR / "sd_advisor_data.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    boards = sorted({r["board"] for r in rows})
    rng = random.Random(7)
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
    base_mse = float(np.mean([(base.get((r["role"], r["tex"]), 0.4) - r["y_bet"]) ** 2 for r in rte]))

    Xtr_t = torch.tensor(Xtr, dtype=torch.float32)
    ytr_t = torch.tensor(ytr, dtype=torch.float32).unsqueeze(1)
    Xte_t = torch.tensor(Xte, dtype=torch.float32)
    yte_t = torch.tensor(yte, dtype=torch.float32).unsqueeze(1)
    net = nn.Sequential(nn.Linear(Xtr_t.shape[1], 64), nn.ReLU(), nn.Linear(64, 64), nn.ReLU(),
                        nn.Linear(64, 1), nn.Sigmoid())
    opt = torch.optim.Adam(net.parameters(), lr=1e-3)
    for _ep in range(80):
        idx = torch.randperm(len(Xtr_t))
        for i in range(0, len(Xtr_t), 4096):
            b = idx[i:i + 4096]
            opt.zero_grad()
            loss = ((net(Xtr_t[b]) - ytr_t[b]) ** 2).mean()
            loss.backward()
            opt.step()
    with torch.no_grad():
        mlp_mse = float(((net(Xte_t) - yte_t) ** 2).mean().item())

    print(f"held-out-by-board P_bet MSE: freq-baseline {base_mse:.4f} | MLP {mlp_mse:.4f} "
          f"({100*(base_mse-mlp_mse)/base_mse:+.0f}% vs baseline)  [{len(held)} held / {len(boards)} flops]")
    if mlp_mse < base_mse * 0.97:
        torch.save({"state": net.state_dict(), "dims": Xtr_t.shape[1]},
                   config.KNOWLEDGE_DIR / "postflop" / "sd_advisor.pt")
        print("-> SD advisor learns beyond the bucket -> sd_advisor.pt SAVED (policy-match sanity PASS)")
    else:
        print("-> does NOT beat the bucket (texture+role already capture it)")


if __name__ == "__main__":
    main()
