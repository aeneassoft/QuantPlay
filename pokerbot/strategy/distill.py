"""Distillation: train a small stochastic policy net to IMITATE the TexasSolver GTO oracle — the
compute-efficient path to a low GTO-gap (supervised, sample-efficient → fits a 30-min pod run).

Targets come from solved spots (cached by gto_benchmark, or freshly solved on the pod's 192 cores). For
each hero hand at a decision node we record compact, fast features + the GTO action distribution bucketed
into 5 canonical actions. A small MLP learns features -> action-distribution (so it can MIX like GTO —
the deterministic baseline could not, which is why it topped out ~15% gap). The selector = mean TV/KL
between the net's distribution and the GTO target on held-out spots (distributional => not gameable).

Torch is imported lazily (only the trainer needs it) so dataset-building runs anywhere.
"""
from __future__ import annotations

import glob
import json
import os

from pokerbot import config
from pokerbot.engine.evaluator import evaluate
from pokerbot.strategy.postflop import classify_board

ACTIONS = ["fold_check", "call", "aggr_small", "aggr_big", "allin"]   # 5 canonical buckets
_ORDER = "23456789TJQKA"
CARDS = [r + s for r in _ORDER for s in "shdc"]
_CACHE = config.DATA_DIR / "_gto_bench_cache"
# small bet tree (one size + all-in per street) -> fast solves for the time-boxed pod curriculum
SMALL_BETS = [
    "set_bet_sizes oop,flop,bet,66", "set_bet_sizes oop,flop,allin",
    "set_bet_sizes ip,flop,bet,66", "set_bet_sizes ip,flop,allin",
    "set_bet_sizes oop,turn,bet,75", "set_bet_sizes oop,turn,allin",
    "set_bet_sizes ip,turn,bet,75", "set_bet_sizes ip,turn,allin",
    "set_bet_sizes oop,river,bet,75", "set_bet_sizes oop,river,allin",
    "set_bet_sizes ip,river,bet,75", "set_bet_sizes ip,river,allin",
]


def _tier(hole, board, made):
    if made in ("Two Pair", "Three of a Kind", "Straight", "Flush", "Full House",
                "Four of a Kind", "Straight Flush"):
        return 2                                   # strong
    if made == "Pair" and board:
        top = max(_ORDER.index(c[0]) for c in board)
        if hole[0][0] == hole[1][0]:
            return 1 if _ORDER.index(hole[0][0]) >= top else 0
        pr = [_ORDER.index(c[0]) for c in hole if any(c[0] == b[0] for b in board)]
        return 1 if pr and max(pr) >= top else 0
    return 0                                        # weak / air


def _bucket(action: str, pot: float) -> int:
    a = action.split()
    head = a[0]
    if head in ("CHECK", "FOLD"):
        return 0
    if head == "CALL":
        return 1
    if head == "ALLIN":
        return 4
    size = float(a[1]) if len(a) > 1 else pot       # BET/RAISE <size>
    return 2 if size < 0.66 * max(1.0, pot) else 3


def features(hole, board, role_ip: bool, pot: float, stack: float) -> list[float]:
    """Compact, FAST (no Monte-Carlo) feature vector: made-hand strength + tier + texture + role + SPR."""
    from pokerbot.engine.evaluator import best_five_name
    made = best_five_name(board, hole)
    strength = 1.0 - evaluate(board, hole) / 7462.0          # treys: 1=best..7462=worst -> 0..1 (higher=better)
    tier = _tier(hole, board, made)
    tex = classify_board(board)
    spr = min((stack / max(1.0, pot)) / 20.0, 1.0)
    street = {3: 0, 4: 1, 5: 2}.get(len(board), 0)
    return [
        strength,
        1.0 if tier == 0 else 0.0, 1.0 if tier == 1 else 0.0, 1.0 if tier == 2 else 0.0,
        float(bool(tex.get("paired"))), float(bool(tex.get("monotone"))),
        float(bool(tex.get("two_tone"))), float(bool(tex.get("connected"))),
        1.0 if role_ip else 0.0,
        spr,
        1.0 if street == 0 else 0.0, 1.0 if street == 1 else 0.0, 1.0 if street == 2 else 0.0,
    ]


N_FEAT = 13


def _target(node, pot):
    """{frozenset(hole): [5-bucket GTO dist]} for the acting player at this node."""
    s = node.get("strategy", {})
    acts, strat = s.get("actions", []), s.get("strategy", {})
    out = {}
    for combo, probs in strat.items():
        dist = [0.0] * 5
        for a, p in zip(acts, probs):
            dist[_bucket(a, pot)] += p
        out[(combo[:2], combo[2:4])] = dist
    return out


def build_dataset(pot: float = 20.0, stack: float = 100.0):
    """Build (X, Y, M) from the cached GTO solves. X=features, Y=5-bucket GTO targets, M=spot-class
    labels (role, texture) per sample so the director can target the worst spot-classes."""
    X, Y, M = [], [], []
    for f in sorted(glob.glob(str(_CACHE / "*.json"))):
        board = [os.path.basename(f)[i:i + 2] for i in range(0, 6, 2)]
        node = json.loads(open(f, encoding="utf-8").read())
        tex = classify_board(board)
        tlab = ("paired" if tex.get("paired") else "monotone" if tex.get("monotone")
                else "connected" if tex.get("connected")
                else "high" if max(_ORDER.index(c[0]) for c in board) >= _ORDER.index("T") else "low")
        ip = next((v for k, v in (node.get("childrens") or {}).items()
                   if k.split()[0] == "CHECK"), None)
        for role_ip, nd in ((False, node), (True, ip)):
            if nd is None:
                continue
            for (c1, c2), dist in _target(nd, pot).items():
                X.append(features([c1, c2], board, role_ip, pot, stack))
                Y.append(dist)
                M.append({"role": "IP" if role_ip else "OOP", "tex": tlab})
    return X, Y, M


# ----------------------------------------------------------------- net + train (torch, pod-side)
def train(X, Y, epochs=300, lr=1e-3, hidden=(128, 128), device=None, seed=0, net=None):
    """Distill toward the GTO targets. Pass `net` to WARM-START (continue training across rounds)."""
    import numpy as np
    import torch
    import torch.nn as nn
    dev = device or ("cuda" if torch.cuda.is_available() else "cpu")
    Xt = torch.tensor(np.array(X), dtype=torch.float32, device=dev)
    Yt = torch.tensor(np.array(Y), dtype=torch.float32, device=dev)
    Yt = Yt / Yt.sum(1, keepdim=True).clamp_min(1e-9)
    if net is None:
        torch.manual_seed(seed)
        layers, d = [], N_FEAT
        for h in hidden:
            layers += [nn.Linear(d, h), nn.ReLU()]
            d = h
        layers += [nn.Linear(d, 5)]
        net = nn.Sequential(*layers)
    net = net.to(dev)
    opt = torch.optim.Adam(net.parameters(), lr=lr)
    for _ in range(epochs):
        opt.zero_grad()
        loss = -(Yt * torch.log_softmax(net(Xt), dim=1)).sum(1).mean()   # cross-entropy / KL to GTO
        loss.backward()
        opt.step()
    return net, float(loss.item())


def eval_gap(net, X, Y):
    """SELECTOR: mean total-variation distance between net dist and GTO target (0=perfect, 1=worst)."""
    import numpy as np
    import torch
    dev = next(net.parameters()).device
    with torch.no_grad():
        p = torch.softmax(net(torch.tensor(np.array(X), dtype=torch.float32, device=dev)), dim=1).cpu().numpy()
    y = np.array(Y)
    y = y / y.sum(1, keepdims=True).clip(1e-9)
    return float(np.abs(p - y).sum(1).mean() / 2.0)       # mean TV


def _tex_label(board):
    tex = classify_board(board)
    return ("paired" if tex.get("paired") else "monotone" if tex.get("monotone")
            else "connected" if tex.get("connected")
            else "high" if max(_ORDER.index(c[0]) for c in board) >= _ORDER.index("T") else "low")


def solve_focus_spots(focus, n=8, pot=20.0, stack=100.0, workers=8, threads=16, max_iter=30, seed=None):
    """LIVE CURRICULUM: solve n fresh boards biased to the director's focus texture(s) -> (X, Y, M).
    Parallel (on the pod set workers high to use the 192 cores). Uses gto_oracle (TexasSolver)."""
    import random
    import uuid
    from concurrent.futures import ThreadPoolExecutor

    from pokerbot.benchmark.gto_benchmark import _IP, _OOP   # reuse the SRP ranges
    from pokerbot.strategy import gto_oracle as O

    rng = random.Random(seed)
    want = [f.split(":", 1)[1] for f in (focus or []) if f.startswith("tex:")]
    boards, tries = [], 0
    while len(boards) < n and tries < n * 12:
        tries += 1
        b = rng.sample(CARDS, 3)
        if want and _tex_label(b) not in want and rng.random() < 0.8:
            continue                                          # bias sampling toward the focus texture
        boards.append(b)

    def _solve(b):
        try:
            return b, O.solve(b, _OOP, _IP, pot=pot, eff_stack=stack, accuracy=0.5, max_iter=max_iter,
                              threads=threads, bets=SMALL_BETS, dump_rounds=1, timeout=300,
                              tag="fx" + uuid.uuid4().hex[:8])
        except Exception:  # noqa: BLE001
            return b, None

    X, Y, M = [], [], []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for b, node in ex.map(_solve, boards):
            if node is None:
                continue
            tlab = _tex_label(b)
            ip = next((v for k, v in (node.get("childrens") or {}).items()
                       if k.split()[0] == "CHECK"), None)
            for role_ip, nd in ((False, node), (True, ip)):
                if nd is None:
                    continue
                for (c1, c2), dist in _target(nd, pot).items():
                    X.append(features([c1, c2], b, role_ip, pot, stack))
                    Y.append(dist)
                    M.append({"role": "IP" if role_ip else "OOP", "tex": tlab})
    return X, Y, M


def main():
    X, Y, _M = build_dataset()
    print(f"dataset: {len(X)} hero-decisions, {N_FEAT} features, 5 action-buckets")
    if not X:
        print("cache empty — run `python -m pokerbot.benchmark.gto_benchmark 14` first")
        return
    try:
        import torch  # noqa: F401
    except ImportError:
        print("(torch not installed locally — dataset build OK; train on the pod)")
        return
    k = int(len(X) * 0.8)
    net, loss = train(X[:k], Y[:k])
    print(f"trained (loss {loss:.3f}); held-out GTO-gap (TV) = {eval_gap(net, X[k:], Y[k:]):.1%}")


if __name__ == "__main__":
    main()
