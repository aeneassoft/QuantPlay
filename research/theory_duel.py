"""OUR BOT vs POKER-THEORY ITSELF — the in-engine, $0, variance-cancelled duel (2026-07-06).

"Poker theory itself" has two in-engine embodiments, run here side by side:
  * ANALYTIC theory = GTOBaseline (Chen/MDF/balanced-bluff near-GTO, instant) -> tight CI at high N.
  * SOLVER theory   = the TexasSolver oracle (live per-board solves) -> run separately via
    `python -m pokerbot.benchmark.gto_oracle_match` (slow, small n, the RIGOROUS arm).

This driver runs the ANALYTIC duel through the duplicate (mirror) gate so card luck cancels and the
SKILL edge is what remains. Three arms:
  (0) NULL   GTOBaseline vs GTOBaseline  -> must be ~0 +/- tiny (validates the instrument).
  (1) EXPLOIT  our shipped exploit-primary engine vs theory -> does the overlay BEAT or BLEED vs theory?
  (2) FLOOR    our engine with exploit OFF vs theory -> the pure-GTO-floor reference (shared DNA -> ~0).

Honest read: a POSITIVE exploit number = our engine out-exploits the ANALYTIC baseline's rigidities
(it is not true GTO); it is NOT a claim of beating the equilibrium. The floor arm is the control: our
GTO floor vs the analytic baseline should hover near 0 (both are near-GTO), so any exploit-arm edge is
the overlay's contribution, priced against a fixed, non-adaptive theory opponent.

Run:  python -m research.theory_duel [--decks 2000] [--seed 7]
"""
from __future__ import annotations

import argparse

from pokerbot.benchmark.duplicate import duplicate_ab, gen_decks, gto, pokerbot


def _fmt(name: str, bb100: float, se: float) -> str:
    ci = 1.96 * se
    return f"  {name:<34} {bb100:+7.2f} +/- {se:4.2f} bb/100   (95% CI {bb100 - ci:+.1f} .. {bb100 + ci:+.1f})"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--decks", type=int, default=2000)   # 2 hands/deck -> 2*decks hands
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--start", type=int, default=10000)  # native 100bb (200bb inflates all-in variance)
    args = ap.parse_args()
    decks = gen_decks(args.decks, seed=args.seed)
    st = args.start
    print(f"=== OUR BOT vs POKER-THEORY (analytic GTOBaseline), duplicate/mirror, "
          f"{args.decks} decks = {2 * args.decks} hands, {st // 100}bb stacks ===\n", flush=True)

    n0, s0 = duplicate_ab(gto(1), gto(1), decks, start=st)
    print(_fmt("(0) NULL  theory vs theory", n0, s0), flush=True)

    n2, s2 = duplicate_ab(pokerbot(exploit=False), gto(1), decks, start=st)
    print(_fmt("(2) FLOOR our GTO-floor vs theory", n2, s2), flush=True)

    n1, s1 = duplicate_ab(pokerbot(exploit=True), gto(1), decks, start=st)
    print(_fmt("(1) EXPLOIT our engine vs theory", n1, s1), flush=True)

    print("\nRead: (0) ~0 validates the mirror instrument. (2) is the near-GTO control (shared DNA -> ~0).")
    print("(1) - (2) = the exploit overlay's edge vs a fixed analytic theory opponent (positive = it out-")
    print("exploits the baseline's rigidity; NOT a claim of beating the true equilibrium).")


if __name__ == "__main__":
    main()
