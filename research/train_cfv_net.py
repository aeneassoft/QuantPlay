"""Phase B step 10: train the CFV value net (HUNL). Maps (4-card turn board + OOP range + IP range + pot) -> per-
HAND-CLASS counterfactual values (cfv0[169], cfv1[169]), learned from the cfv_data dataset (cfv_dataset.jsonl, the
RunPod campaign output). This is the DeepStack value function our flop resolver will query at the turn->river leaf —
trained ONLY on our own solver-generated CFVs (self-play boundary; NOT an external policy → escapes the imitation
ceiling). Per-class (169) granularity matches the class-level ranges range_tracker emits + keeps the net small.

Target = per-class MEAN of the per-combo CFVs in the dataset row (masked: only classes present in that row's range
are scored). GATE B2: held-out-by-board MAE small vs the CFV scale. Run: python -m extraction.train_cfv_net [jsonl]
"""
from __future__ import annotations

import json
import sys

import numpy as np
import torch
import torch.nn as nn

from pokerbot import config
from pokerbot.engine.cards import hand_class
from research.cfv_data import _all_classes

CLASSES = _all_classes()                       # 169 ordered hand classes (AA, AKs, AKo, ..., 22)
CIDX = {c: i for i, c in enumerate(CLASSES)}
RANKS = "23456789TJQKA"
SUITS = "cdhs"
DECK = [r + s for r in RANKS for s in SUITS]   # 52 cards
DIDX = {c: i for i, c in enumerate(DECK)}


def _range_vec(range_str):
    """'AKs:0.8,QQ:1,...' -> 169-dim weighted class vector."""
    v = np.zeros(len(CLASSES), dtype=np.float32)
    for tok in (range_str or "").split(","):
        if ":" in tok:
            c, w = tok.split(":")
            if c in CIDX:
                v[CIDX[c]] = float(w)
    return v


def _board_vec(board4):
    v = np.zeros(52, dtype=np.float32)
    for c in board4:
        if c in DIDX:
            v[DIDX[c]] = 1.0
    return v


def _class_targets(cfv_dict):
    """per-combo {combo:cfv} -> (per-class mean[169], mask[169])."""
    acc = np.zeros(len(CLASSES), dtype=np.float32)
    cnt = np.zeros(len(CLASSES), dtype=np.float32)
    for combo, val in cfv_dict.items():
        cls = hand_class(combo[:2], combo[2:4])
        if cls in CIDX:
            acc[CIDX[cls]] += val
            cnt[CIDX[cls]] += 1
    mask = (cnt > 0).astype(np.float32)
    mean = np.divide(acc, cnt, out=np.zeros_like(acc), where=cnt > 0)
    return mean, mask


def _featurize(rows):
    X, Y, M = [], [], []
    for r in rows:
        x = np.concatenate([_board_vec(r["board"]), _range_vec(r["oop"]), _range_vec(r["ip"]),
                            np.array([r["pot"] / 100.0, r.get("eff", 50) / 100.0], dtype=np.float32)])
        y0, m0 = _class_targets(r["cfv0"])
        y1, m1 = _class_targets(r["cfv1"])
        X.append(x); Y.append(np.concatenate([y0, y1])); M.append(np.concatenate([m0, m1]))
    return np.array(X), np.array(Y), np.array(M)


class CFVNetHUNL(nn.Module):
    def __init__(self, din, dout, h=512):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(din, h), nn.ReLU(), nn.Linear(h, h), nn.ReLU(),
                                 nn.Linear(h, h), nn.ReLU(), nn.Linear(h, dout))

    def forward(self, x):
        return self.net(x)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else str(config.DATA_DIR / "cfv_shards" / "cfv_dataset.jsonl")
    rows = [json.loads(x) for x in open(path, encoding="utf-8") if x.strip()]
    if len(rows) < 8:
        print(f"only {len(rows)} samples in {path} — this is a SMOKE TEST (confirms the trainer runs); the real "
              f"train needs the big RunPod dataset. Proceeding on what's here.", flush=True)
    boards = sorted({"".join(r["board"]) for r in rows})
    import random as _r
    _r.Random(7).shuffle(boards)
    held = set(boards[:max(1, len(boards) // 5)])
    tr = [r for r in rows if "".join(r["board"]) not in held]
    te = [r for r in rows if "".join(r["board"]) in held]
    if not tr or not te:
        tr = te = rows                                          # tiny smoke set: don't split to empty
    Xtr, Ytr, Mtr = _featurize(tr)
    Xte, Yte, Mte = _featurize(te)
    din, dout = Xtr.shape[1], Ytr.shape[1]
    # STANDARDIZE targets: raw CFVs are ~±thousands of chips -> MSE in the millions + unstable grads (the net
    # could not even FIT the train set). Normalize to ~unit scale for training; de-normalize at inference via the
    # stored (mu, sigma). Computed on the TRAIN masked targets only (no test leakage).
    mtr = Mtr > 0
    mu = float(Ytr[mtr].mean()) if mtr.any() else 0.0
    sigma = float(Ytr[mtr].std()) or 1.0
    Ytr_n, Yte_n = (Ytr - mu) / sigma, (Yte - mu) / sigma
    net = CFVNetHUNL(din, dout)
    opt = torch.optim.Adam(net.parameters(), lr=1e-3, weight_decay=1e-5)
    Xt, Yt, Mt = torch.tensor(Xtr), torch.tensor(Ytr_n), torch.tensor(Mtr)
    Xv, Mv = torch.tensor(Xte), torch.tensor(Mte)
    Yte_r, Mte_r = torch.tensor(Yte), torch.tensor(Mte)            # REAL-unit held-out targets for the final report
    print(f"train {len(tr)} / held-out {len(te)} | features {din} -> {dout} classes(x2) | "
          f"targets standardized (mu={mu:.1f} sigma={sigma:.1f}) | masked MSE", flush=True)
    for ep in range(600):
        opt.zero_grad()
        pred = net(Xt)
        loss = (((pred - Yt) ** 2) * Mt).sum() / Mt.sum().clamp(min=1)
        loss.backward()
        opt.step()
        if (ep + 1) % 150 == 0:
            with torch.no_grad():
                pv_real = net(Xv) * sigma + mu                     # de-normalize -> chips
                vmae = ((pv_real - Yte_r).abs() * Mv).sum() / Mv.sum().clamp(min=1)
            print(f"  ep{ep+1} train_mse(norm)={loss.item():.4f} heldout_MAE(chips)={vmae.item():.1f}", flush=True)
    with torch.no_grad():
        pv_real = net(Xv) * sigma + mu
        vmae = (((pv_real - Yte_r).abs() * Mv).sum() / Mv.sum().clamp(min=1)).item()
        scale = ((Yte_r.abs() * Mte_r).sum() / Mte_r.sum().clamp(min=1)).item()
    pct = 100 * vmae / scale if scale else float("nan")
    print(f"\n  RESULT: held-out MAE {vmae:.1f} vs CFV scale {scale:.1f} = {pct:.0f}% "
          f"-> {'PASS (<8%)' if pct < 8 else 'needs more data / tuning'} (GATE B2)", flush=True)
    torch.save({"state": net.state_dict(), "din": din, "dout": dout, "classes": CLASSES, "mu": mu, "sigma": sigma},
               config.DATA_DIR / "hunl_cfv_net.pt")
    print(f"  saved -> {config.DATA_DIR / 'hunl_cfv_net.pt'} (gitignored)", flush=True)


if __name__ == "__main__":
    main()
