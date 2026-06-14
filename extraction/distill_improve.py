"""Improve the distillation GTO-floor net on the local GPU (RTX 3080 Ti). The full-batch baseline
underfits ~328k samples (only `epochs` gradient steps total); minibatching + a bigger net should cut the
held-out GTO-gap (TV). Informed by (vetted) OpenAI tips. Saves the best net to data/floor_net.pt.
Run: python -m extraction.distill_improve
"""
from __future__ import annotations

import time

from pokerbot import config
from pokerbot.strategy import distill as D


def main():
    X, Y, _M = D.build_dataset()
    n = len(X)
    k = int(n * 0.85)
    Xtr, Ytr, Xte, Yte = X[:k], Y[:k], X[k:], Y[k:]
    print(f"dataset: {n} hero-decisions | train {k} / test {n - k}\n", flush=True)
    configs = [
        ("baseline 128x128 full-batch e300", dict(hidden=(128, 128), epochs=300, bs=0)),
        ("256x256 minibatch(8192) e40", dict(hidden=(256, 256), epochs=40, bs=8192)),
        ("256x256x256 minibatch(8192) e80", dict(hidden=(256, 256, 256), epochs=80, bs=8192)),
    ]
    best = None
    import torch
    for name, cfg in configs:
        t = time.time()
        net, loss = D.train(Xtr, Ytr, lr=1e-3, **cfg)
        gap = D.eval_gap(net, Xte, Yte)
        print(f"{name:34} | loss {loss:.3f} | held-out TV-gap {gap:.1%} | {time.time() - t:.0f}s", flush=True)
        if best is None or gap < best[0]:
            best = (gap, name, net)
    out = config.DATA_DIR / "floor_net.pt"
    torch.save(best[2].state_dict(), out)
    print(f"\nBEST: {best[1]} -> TV-gap {best[0]:.1%} | saved {out}")


if __name__ == "__main__":
    main()
