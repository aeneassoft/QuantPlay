"""Move A (GTO-frontier keystone): FALSIFY our LBR. Inject KNOWN leaks into the frozen bot and check whether the
LBR detects them (strictly higher exploit vs the corrupted bot than vs clean, beyond noise). If a leak CLASS is
missed (delta ~ 0), the LBR is blind there -- almost certainly the v1 uniform-card-sampling caveat (it cannot see
the bot's RANGE, only its fold/bet RESPONSE) -> we need a Bayesian action-consistent range (LBR v2) before
trusting any "low-exploitability" claim. NIT = an always-fold bot the LBR MUST crush (mechanics sanity).

Prediction: fold-RESPONSE leaks (river overfold, fold-to-overbet) are CARD-INDEPENDENT -> caught; range-
COMPOSITION leaks (c-bet air, over-bluff) need the bot's range -> MISSED by uniform sampling.
Run: python -m pokerbot.benchmark.lbr_falsify [--hands N] [--rollouts K]
"""
from __future__ import annotations

import argparse
import random
import statistics

from pokerbot.benchmark.lbr import _NitBot, lbr_bb100
from pokerbot.strategy.bot import PokerBot


class LeakyBot:
    """Wrap a frozen PokerBot and inject ONE known corruption (a synthetic leak) into its decisions."""

    def __init__(self, seat, spec="clean", seed=0):
        self.inner = PokerBot(seat, seed=seed, exploit=False)
        self.hero_idx = seat
        self.spec = spec
        self.rng = random.Random(seed + 99)

    def _bet_to(self, st, la, frac):
        hero = st["players"][self.hero_idx]
        tt = hero.get("committed_street", 0) + int(frac * (la.get("pot", 0) or 0))
        tt = max(la["raise_min"], min(tt, la["raise_max"]))
        return {"action": "bet" if la.get("is_bet") else "raise", "amount": tt}

    def decide(self, st):
        self.inner.hero_idx = self.hero_idx
        d = self.inner.decide(st)
        spec = self.spec
        if spec == "clean":
            return d
        la = st.get("legal", {}) or {}
        street = st.get("street")
        to_call = la.get("to_call", 0) or 0
        pot = la.get("pot", 0) or 0
        a = d.get("action")
        post = street in ("flop", "turn", "river")
        # ---- fold-RESPONSE leaks (card-independent -> LBR should CATCH by betting more) ----
        if spec == "fold_any_bet" and post and to_call > 0 and a in ("call", "raise"):
            return {"action": "fold", "amount": None}                  # extreme over-fold (fires on every postflop bet faced)
        if spec == "overfold_50" and post and to_call > 0 and a == "call":
            if self.rng.random() < 0.5:
                return {"action": "fold", "amount": None}              # moderate over-fold
        # ---- range-COMPOSITION leaks (need the bot's range -> uniform-sampling LBR likely MISSES) ----
        if spec == "cbet_air" and street == "flop" and to_call == 0 and a == "check" and la.get("can_raise"):
            return self._bet_to(st, la, 0.66)                 # c-bet the WHOLE range incl. air
        if spec == "overbluff_river" and street == "river" and to_call == 0 and a == "check" and la.get("can_raise"):
            if self.rng.random() < 0.5:
                return self._bet_to(st, la, 1.0)              # turn half of give-ups into pot-size bluffs
        return d

    def observe_hand_end(self):
        if hasattr(self.inner, "observe_hand_end"):
            self.inner.observe_hand_end()


SPECS = [
    ("nit_ref", "sanity (must crush)"),
    ("clean", "baseline"),
    ("fold_any_bet", "fold-response/extreme"),
    ("overfold_50", "fold-response/moderate"),
    ("cbet_air", "range-composition"),
    ("overbluff_river", "range-composition"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hands", type=int, default=250)
    ap.add_argument("--rollouts", type=int, default=8)
    ap.add_argument("--iters", type=int, default=50)
    args = ap.parse_args()
    print(f"LBR FALSIFICATION (paired/duplicate) | {args.hands} hands x {args.rollouts} rollouts (iters={args.iters})\n", flush=True)
    clean_net = None
    for spec, kind in SPECS:
        def make_bot(seat, _spec=spec):
            return _NitBot(seat) if _spec == "nit_ref" else LeakyBot(seat, spec=_spec, seed=0)
        mean, se, net = lbr_bb100(make_bot, hands=args.hands, K=args.rollouts, iters=args.iters)
        if spec == "clean":
            clean_net = net
        if clean_net is not None and spec not in ("nit_ref", "clean") and len(net) == len(clean_net):
            diffs = [net[i] - clean_net[i] for i in range(len(net))]
            fired = sum(1 for d in diffs if abs(d) > 1e-9)
            dmean = sum(diffs) / len(diffs)
            dse = statistics.pstdev(diffs) / (len(diffs) ** 0.5) if len(diffs) > 1 else 0.0
            verdict = "DETECTED" if (dmean > 3 * dse and dmean > 20) else ("BLIND~0" if abs(dmean) < max(20.0, 2 * dse) else "?")
            print(f"  {spec:16s} [{kind:18s}] LBR {mean:+7.0f} | paired-delta {dmean:+7.1f} +/- {dse:4.1f} | fired {fired:3d}/{len(net)} -> {verdict}", flush=True)
        else:
            print(f"  {spec:16s} [{kind:18s}] LBR {mean:+7.0f} +/- {se:4.0f}", flush=True)
    print("\nGATE: nit_ref hugely positive (sanity). DETECTED = leak the LBR catches; BLIND~0 = leak it misses.")
    print("Expectation: fold-response DETECTED, range-composition BLIND -> the LBR needs Bayesian range tracking (v2).")


if __name__ == "__main__":
    main()
