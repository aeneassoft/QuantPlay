"""FAST LOCAL preflop-blueprint A/B — the deterministic, card-luck-cancelled proxy for the slow/flaky GTO Wizard API.

The GTOW API is ~50 min/run and 503/409-prone; this is SECONDS and reproducible. It can't BE GTOW (their net is
proprietary, API-only), but it pins a near-GTO LOCAL opponent (the analytic GTOBaseline) + duplicate (mirror) poker
to collapse variance ~10-50x, so a preflop change's true effect is measurable WITHOUT the API. Use it as the fast
iteration gate; keep the GTOW AIVAT run as the occasional FINAL confirmation.

Honest scope: vs the GTOBaseline (not GTOW) this measures whether the blueprint is self-harmful / regressive and its
directional EV; it UNDER-states the exploitability-reduction a true best-responder (GTOW) would reward. The duplicate
runs at 200bb (HeadsUpGame 20000/50/100) so the blueprint's depth gate fires.

Run:  python -m pokerbot.benchmark.preflop_ab [--decks N]
"""
from __future__ import annotations

import argparse

from pokerbot.benchmark.duplicate import duplicate_ab, gen_decks, gto, pokerbot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--decks", type=int, default=600)
    ap.add_argument("--exploit", action="store_true", help="match the GTOW config (exploit overlay ON)")
    args = ap.parse_args()
    decks = gen_decks(args.decks, seed=7)
    ex = args.exploit
    N = 2 * args.decks
    print(f"=== Preflop-blueprint LOCAL A/B — duplicate poker @200bb, {args.decks} decks ({N} hands), "
          f"exploit={'ON' if ex else 'off'} ===", flush=True)

    # null sanity: identical bots -> ~0 (validates the harness)
    nb, nse = duplicate_ab(pokerbot(exploit=ex, use_blueprint=True), pokerbot(exploit=ex, use_blueprint=True), decks)
    print(f"  null (ON vs ON):                 {nb:+6.2f} ± {nse:4.2f} bb/100   (expect ~0)", flush=True)

    # THE direct A/B: new preflop vs old preflop, heads-up, card-luck-cancelled
    ab, abse = duplicate_ab(pokerbot(exploit=ex, use_blueprint=True), pokerbot(exploit=ex, use_blueprint=False), decks)
    print(f"  blueprint ON vs OFF (self-play): {ab:+6.2f} ± {abse:4.2f} bb/100   <-- the direct preflop edge", flush=True)

    # both vs the near-GTO GTOBaseline (same decks -> comparable)
    ong, onse = duplicate_ab(pokerbot(exploit=ex, use_blueprint=True), gto(1), decks)
    offg, offse = duplicate_ab(pokerbot(exploit=ex, use_blueprint=False), gto(1), decks)
    print(f"  ON  vs GTOBaseline:              {ong:+6.2f} ± {onse:4.2f} bb/100", flush=True)
    print(f"  OFF vs GTOBaseline:              {offg:+6.2f} ± {offse:4.2f} bb/100", flush=True)
    print(f"  -> blueprint delta vs near-GTO:  {ong - offg:+6.2f} bb/100   (>0 = blueprint helps vs near-GTO)", flush=True)
    print("\nVerdict: ship-worthy if ON-vs-OFF > 0 by >2 stderr AND ON-vs-GTOBaseline is not a regression.", flush=True)


if __name__ == "__main__":
    main()
