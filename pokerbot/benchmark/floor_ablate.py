"""WS1 floor-bleed ablation (GATING). Deterministic, no network: each config of the FLOOR (exploit=False) is
measured vs GTOBaseline via the duplicate (card-luck-cancelled) gate, plus a PAIRED delta vs the full floor on
the SAME decks (low variance). Decides whether the -102.5 bb/100 vs Slumbot @2000h is:
  (a) a #40/#41 regression vs near-GTO,   (b) a real floor leak,   (c) variance / Slumbot-specific.

The toggles live on PokerBot (default True = shipped floor). NOTE: use_mdf_shade is a no-op on the floor
(the MDF shade is gated by conf, which is 0 when exploit=False) -> it should show ~0 delta, confirming it is an
exploit-path knob, not a floor leak.

Run:  python -m pokerbot.benchmark.floor_ablate [--decks 600]
"""
from __future__ import annotations

import argparse

from pokerbot.benchmark.duplicate import duplicate_ab, gen_decks, gto, pokerbot

# config -> floor toggle overrides (anything not listed stays at its default True)
CONFIGS = {
    "full_floor":       {},
    "no_river_blocker": {"use_river_blocker": False},
    "no_turn_advisor":  {"use_turn_advisor": False},
    "no_40_no_41":      {"use_river_blocker": False, "use_turn_advisor": False},
    "no_fe_sizing":     {"use_fe_sizing": False},
    "no_mdf_shade":     {"use_mdf_shade": False},
    "no_river_advisor": {"use_river_advisor": False},
    "with_commit_cap":  {"use_commit_cap": True},   # NEW: anti-spew big-pot stack-off cap (paired test vs floor)
    "pre40_pre41":      {"use_river_blocker": False, "use_turn_advisor": False,
                         "use_fe_sizing": False, "use_mdf_shade": False},
}
BB = 100


def _paired_delta(edges_x, edges_f):
    """Per-deck (X - full_floor) paired delta -> (bb100, se). Same decks => card luck cancels => low variance."""
    n = len(edges_x)
    d = [edges_x[i] - edges_f[i] for i in range(n)]
    mean = sum(d) / n
    var = sum((x - mean) ** 2 for x in d) / max(1, n - 1)
    return mean / 2 / BB * 100, (var ** 0.5 / n ** 0.5) / 2 / BB * 100


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--decks", type=int, default=600)
    args = ap.parse_args()
    decks = gen_decks(args.decks, seed=7)
    print(f"=== FLOOR-BLEED ABLATION ({args.decks} decks, paired, vs GTOBaseline) ===\n")

    nbb, nse = duplicate_ab(pokerbot(False), pokerbot(False), decks)
    print(f"null  full_floor vs full_floor : {nbb:+6.1f} ± {nse:.1f} bb/100   (sanity: ~0)\n")

    results = {}
    for name, flags in CONFIGS.items():
        bb100, se, edges = duplicate_ab(pokerbot(False, **flags), gto(1), decks, return_edges=True)
        results[name] = (bb100, se, edges)
        print(f"  ...{name} done")

    base_edges = results["full_floor"][2]
    print(f"\n{'config':<18}{'vs GTOBaseline':>18}{'paired d vs full_floor':>30}")
    print("-" * 66)
    for name in CONFIGS:
        bb100, se, edges = results[name]
        if name == "full_floor":
            print(f"{name:<18}{bb100:>+11.1f} ±{se:<5.1f}{'(baseline)':>30}")
        else:
            dbb, dse = _paired_delta(edges, base_edges)
            sig = "  <-- SIG (>2sd)" if abs(dbb) > 2 * dse else ""
            print(f"{name:<18}{bb100:>+11.1f} ±{se:<5.1f}{dbb:>+18.1f} ±{dse:<5.1f}{sig}")

    # ---- automatic cause label (pre-registered) ----
    print("\n--- cause label (pre-registered criteria) ---")
    full_bb, full_se = results["full_floor"][0], results["full_floor"][1]
    d_4041, se_4041 = _paired_delta(results["no_40_no_41"][2], base_edges)
    pre_bb = results["pre40_pre41"][0]
    found = False
    if d_4041 > 2 * se_4041:
        found = True
        print(f"(a) REGRESSION vs near-GTO: removing #40/#41 gains {d_4041:+.1f} ± {se_4041:.1f} bb/100 "
              f"(paired vs full_floor) -> gate #40/#41 OFF by default on the floor.")
    for nm in ("no_fe_sizing", "no_mdf_shade"):
        dd, ss = _paired_delta(results[nm][2], base_edges)
        if dd > 2 * ss:
            found = True
            print(f"(b) LEAK: disabling {nm.replace('no_', '')} gains {dd:+.1f} ± {ss:.1f} bb/100 "
                  f"vs full_floor -> EV-suspect, fix the smallest change that recovers it.")
    if pre_bb < -10 and pre_bb < full_bb - 2 * results["pre40_pre41"][1]:
        print(f"    note: even pre40_pre41 still loses {pre_bb:+.1f} vs GTOBaseline -> residual floor gap "
              f"beyond these 4 toggles (deeper structural leak; see NOTES suspected-leaks).")
    if not found:
        print(f"(c) VARIANCE / no clear culprit: full_floor {full_bb:+.1f} +/- {full_se:.1f} vs GTOBaseline; "
              f"no config beats it by >2sd. The -102 vs Slumbot is then Slumbot-specific or noise -> confirm "
              f"with ONE large-N Slumbot run; do NOT pre-fix on assumption.")


if __name__ == "__main__":
    main()
