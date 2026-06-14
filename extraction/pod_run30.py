"""30-minute pod-run orchestrator: distill the policy net toward the GTO oracle, with Claude-Opus
ACTIVELY directing the curriculum each round (your active role in the run). Time-boxed; the SELECTOR
(held-out GTO-gap, TV — distributional => not gameable) gates progress. On the pod the director's focus
classes get MORE solved spots (192 cores) appended to the dataset between rounds.
Run: python -m extraction.pod_run30 [minutes]
"""
from __future__ import annotations

import json
import sys
import time

from pokerbot import config
from pokerbot.coach.meta_coach import MetaCoach
from pokerbot.strategy import distill


def _bucket_gaps(net, Xh, Yh, Mh):
    out = {"overall": round(distill.eval_gap(net, Xh, Yh), 4)}
    for key in ("role", "tex"):
        groups = {}
        for x, y, m in zip(Xh, Yh, Mh):
            groups.setdefault(m[key], ([], []))
            groups[m[key]][0].append(x)
            groups[m[key]][1].append(y)
        for g, (xs, ys) in groups.items():
            if xs:
                out[f"{key}:{g}"] = round(distill.eval_gap(net, xs, ys), 4)
    return out


def main():
    minutes = float(sys.argv[1]) if len(sys.argv) > 1 else 30.0
    expand = int(sys.argv[2]) if len(sys.argv) > 2 else 0       # boards solved per round (pod: 12-24)
    workers = int(sys.argv[3]) if len(sys.argv) > 3 else 8       # parallel solves (pod: 32-64 on 192 cores)
    X, Y, M = distill.build_dataset()
    if not X:
        print("cache empty — run `python -m pokerbot.benchmark.gto_benchmark 14` first")
        return
    k = int(len(X) * 0.8)
    Xtr, Ytr = X[:k], Y[:k]
    Xh, Yh, Mh = X[k:], Y[k:], M[k:]
    director = MetaCoach(provider="anthropic", model=config.CLAUDE_MODEL)    # Opus = the active director
    print(f"directing with {director.model} | {len(Xtr)} train / {len(Xh)} held-out | budget {minutes} min")
    import copy
    t0, rnd, lr, epochs, best, best_state, net = time.time(), 0, 1e-3, 250, 1.0, None, None
    while (time.time() - t0) / 60 < minutes - 1:
        rnd += 1
        net, _loss = distill.train(Xtr, Ytr, epochs=epochs, lr=lr, net=net)   # warm-start across rounds
        gaps = _bucket_gaps(net, Xh, Yh, Mh)
        if gaps["overall"] < best:
            best, best_state = gaps["overall"], copy.deepcopy(net.state_dict())
        left = minutes - (time.time() - t0) / 60
        print(f"round {rnd}: gap {gaps['overall']:.1%} (best {best:.1%}) lr={lr} ep={epochs} | {left:.1f}min left")
        d = director.direct_run({"round": rnd, "minutes_left": round(left, 1), "gaps": gaps,
                                 "lr": lr, "epochs": epochs})
        print("  Claude-director:", json.dumps(d, ensure_ascii=False)[:280])
        if isinstance(d, dict) and "error" not in d:
            lr = float(d.get("lr") or lr)
            epochs = int(d.get("epochs_next") or epochs)
            if d.get("continue") is False:
                break
            if expand:                                          # LIVE CURRICULUM (Claude-directed)
                nx, ny, _nm = distill.solve_focus_spots(d.get("focus"), n=expand, workers=workers)
                Xtr += nx
                Ytr += ny
                print(f"  +{len(nx)} samples solved in focus classes (train now {len(Xtr)})")
    print(f"\nFINAL best GTO-gap {best:.1%} after {rnd} rounds, {(time.time()-t0)/60:.1f} min "
          f"(directed by {director.model}).")
    if best_state is not None:
        try:
            import torch
            torch.save(best_state, str(config.DATA_DIR / "distilled_policy.pt"))
            print("saved -> data/distilled_policy.pt")
        except Exception as e:  # noqa: BLE001
            print("save skipped:", e)


if __name__ == "__main__":
    main()
