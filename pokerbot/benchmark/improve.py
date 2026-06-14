"""CPU dry-run of the pod self-improvement loop: tune the baseline's analytic PRIORS (Chen/MDF
thresholds) against the cached GTO-benchmark SELECTOR — propose -> evaluate(GTO-gap) -> accept if lower.

This is the SAME propose->eval->accept loop the pod will run, only with a neural policy + DCFR/self-play
in place of grid search. It proves the loop lowers the gap on cheap CPU before we spend GPU time.
Run (after the benchmark has cached the boards): python -m pokerbot.benchmark.improve
"""
from __future__ import annotations

from pokerbot.benchmark.gto_benchmark import evaluate
from pokerbot.strategy.gto_baseline import GTOBaseline


def _eval(params):
    return evaluate(GTOBaseline(0, seed=1, iters=120, params=params))


def _line(tag, e):
    return (f"{tag:11} gap {e['ALL']['gap']:.1%}  match {e['ALL']['match']:.0%}  | "
            f"OOP-bet {e['OOP']['bbet']:.0%} (GTO {e['OOP']['gbet']:.0%})  "
            f"IP-bet {e['IP']['bbet']:.0%} (GTO {e['IP']['gbet']:.0%})")


def main():
    base = _eval({})
    if base is None:
        print("cache empty — run `python -m pokerbot.benchmark.gto_benchmark 14` first")
        return
    print(_line("baseline", base))
    # coordinate search over the postflop priors; SELECTOR (GTO-gap) decides acceptance
    cur, best = {}, base["ALL"]["gap"]
    grid = {"cbet_eq": [0.40, 0.44, 0.48, 0.52], "cbet_bluff": [0.4, 0.6, 0.8, 1.0],
            "donk_eq": [0.75, 0.85, 0.95], "donk_freq": [0.0, 0.1, 0.2]}
    for knob, vals in grid.items():
        trials = sorted((( _eval({**cur, knob: v})["ALL"]["gap"], v) for v in vals), key=lambda x: x[0])
        g, v = trials[0]
        if g < best - 1e-4:
            cur[knob], best = v, g
            print(f"  accept {knob}={v}  -> gap {g:.1%}")
        else:
            print(f"  {knob}: no improvement (best {best:.1%})")
    print("\n" + _line("tuned", _eval(cur)))
    print(f"tuned priors θ = {cur}")


if __name__ == "__main__":
    main()
