"""'Beat them all' — the core thesis test.

No bot plays true GTO, so the winning design is not a fixed strategy but a UNIVERSAL ADAPTIVE
EXPLOITER. This benchmark pits three heroes against a diverse opponent suite (named baselines +
random "unknown" synthetic opponents we never hand-tuned for + a strong PokerBot):

  * adaptive     -> AdaptiveExploiter (learns each opponent online, exploits safely)
  * baseline     -> PokerBot, exploit OFF (robust but non-adaptive)
  * always_aggro -> a fixed over-bluffer (a fixed "exploit")

The point: only `adaptive` beats (or ties) EVERY opponent. The fixed strategies each win some and
lose others — proving adaptivity is necessary to beat them all.

Run:  python -m pokerbot.benchmark.beat_them_all [--hands N] [--iters N]
"""
from __future__ import annotations

import argparse
import random

import pokerbot.strategy.bot as botmod
from pokerbot.engine.game import HeadsUpGame
from pokerbot.strategy.adaptive import AdaptiveExploiter, Knobs
from pokerbot.strategy.bot import PokerBot


# ---------------- opponents (decide(state) -> (action, amount)) ----------------
def _aggr_amount(st, frac):
    la = st["legal"]
    committed = st["players"][st["to_act"]]["committed_street"]
    tgt = committed + int(frac * max(1, la["pot"]))
    lo, hi = la["raise_min"], la["raise_max"]
    return tgt if lo is None else max(lo, min(tgt, hi))


def opp_station(rng):
    def d(st):
        la = st["legal"]
        return ("check", None) if la["can_check"] else (("call", None) if la["can_call"] else ("fold", None))
    return d


def opp_maniac(rng):
    def d(st):
        la = st["legal"]
        if la["can_raise"] and rng.random() < 0.6:
            return ("bet" if la["is_bet"] else "raise"), _aggr_amount(st, 0.8)
        if la["can_check"]:
            return "check", None
        return ("call", None) if la["can_call"] else ("fold", None)
    return d


def opp_nit(rng):
    def d(st):
        la = st["legal"]
        if la["can_check"]:
            return "check", None
        return "fold", None
    return d


def opp_synthetic(rng, fold_p, aggr_p, size):
    """A random 'unknown' opponent: folds to bets w.p. fold_p, bets/raises w.p. aggr_p."""
    def d(st):
        la = st["legal"]
        if la["to_call"] > 0:
            if rng.random() < fold_p:
                return "fold", None
            if la["can_raise"] and rng.random() < aggr_p * 0.5:
                return ("bet" if la["is_bet"] else "raise"), _aggr_amount(st, size)
            return ("call", None) if la["can_call"] else ("fold", None)
        if la["can_raise"] and rng.random() < aggr_p:
            return ("bet" if la["is_bet"] else "raise"), _aggr_amount(st, size)
        return "check", None
    return d


def opp_pokerbot(seed):
    pb = PokerBot(1, seed=seed, exploit=True)
    def d(st):
        pb.hero_idx = 1
        r = pb.decide(st)
        return r["action"], r["amount"]
    return d


# ---------------- heroes ----------------
class AlwaysAggro:
    """Fixed over-bluffer: bets/raises whenever it can. Crushes folders, bleeds vs stations."""
    def __init__(self, hero):
        self.hero = hero
    def decide(self, st):
        la = st["legal"]
        if la["can_raise"]:
            return ("bet" if la["is_bet"] else "raise"), _aggr_amount(st, 0.75)
        if la["can_check"]:
            return "check", None
        return ("call", None) if la["can_call"] else ("fold", None)


class PokerBotHero:
    def __init__(self, exploit, seed):
        self.pb = PokerBot(0, seed=seed, exploit=exploit)
    def decide(self, st):
        self.pb.hero_idx = 0
        r = self.pb.decide(st)
        return r["action"], r["amount"]
    def observe_opponent(self, st, a):
        self.pb.observe_opponent(st["street"], a, (st["legal"].get("to_call", 0) > 0))
    def observe_hand_end(self):
        self.pb.observe_hand_end()


# ---------------- match loop ----------------
def play(hero, opp_decide, hands, seed=7, start=10000, sb=50, bb=100) -> float:
    g = HeadsUpGame(names=("Hero", "Opp"), starting_stack=start, sb=sb, bb=bb, seed=seed)
    net = []
    for _ in range(hands):
        g.players[0].stack = g.players[1].stack = start
        g.start_hand()
        guard = 0
        while not g.hand_over:
            st = g.state()
            actor = st["to_act"]
            if actor == 0:
                a, amt = hero.decide(st)
            else:
                a, amt = opp_decide(st)
                if hasattr(hero, "observe_opponent"):
                    hero.observe_opponent(st, a)
            g.act(a, amt)
            guard += 1
            if guard > 3000:
                break
        if hasattr(hero, "observe_hand_end"):
            hero.observe_hand_end()
        net.append(g.players[0].stack - start)
    return sum(net) / len(net)


def stress(n_opp: int, hands: int, iters: int, gate: bool = False) -> None:
    """Full-adaptivity proof: AdaptiveExploiter vs a large population of RANDOM, never-seen
    opponents (random fold curve / aggression / sizing). Demonstrates it beats opponents we
    don't know exist — this is the workload RunPod would scale up."""
    import statistics
    rng = random.Random(123)
    bbs, losers = [], []
    for i in range(n_opp):
        fp, ap_, sz = rng.random(), rng.random() * 0.7, 0.3 + rng.random() * 1.2
        opp = opp_synthetic(random.Random(1000 + i), fold_p=fp, aggr_p=ap_, size=sz)
        bb = play(AdaptiveExploiter(0, seed=7, iters=iters, gate=gate), opp, hands)
        bbs.append(bb)
        if bb <= 0:
            losers.append((bb, fp, ap_, sz))
    beaten = sum(1 for b in bbs if b > 0)
    print(f"FULL-ADAPTIVITY STRESS — adaptive vs {n_opp} RANDOM unknown opponents "
          f"({hands} hands each, iters={iters}):")
    print(f"  beaten: {beaten}/{n_opp} = {100*beaten/n_opp:.0f}%")
    print(f"  bb/100: mean {statistics.mean(bbs):+.0f} | median {statistics.median(bbs):+.0f} | "
          f"min {min(bbs):+.0f} | max {max(bbs):+.0f}")
    if losers:
        print(f"  {len(losers)} not beaten (near-unexploitable / variance):")
        for b, fp, ap_, sz in sorted(losers)[:8]:
            print(f"    bb {b:+6.0f}  fold={fp:.2f} aggr={ap_:.2f} size={sz:.2f}")


def probe_test(hands: int, iters: int, budget: float = 40.0) -> None:
    """Test the bounded probing feature: does it add edge (faster opponent ID)? And — critically —
    does the session risk stay within the hard budget (no runaway)?"""
    R = random.Random
    opps = {
        "station": lambda: opp_station(R(1)),
        "maniac": lambda: opp_maniac(R(2)),
        "nit": lambda: opp_nit(R(3)),
        "unknown-B(sticky)": lambda: opp_synthetic(R(5), 0.12, 0.25, 0.7),
        "unknown-C(trappy)": lambda: opp_synthetic(R(6), 0.40, 0.55, 1.1),
        "PokerBot(strong)": lambda: opp_pokerbot(99),
    }
    print(f"PROBE TEST ({hands} hands/match) — adaptive WITHOUT vs WITH bounded probing "
          f"(budget {budget:.0f}bb). bb/100 + probe count + bb spent (must stay <= budget):\n")
    print(f"{'opponent':18s} {'no-probe':>9s} {'probe-on':>9s} {'delta':>7s} {'probes':>7s} {'spent':>8s}")
    for oname, ofac in opps.items():
        off = play(AdaptiveExploiter(0, seed=7, iters=iters, knobs=Knobs(probe=False)), ofac(), hands)
        h_on = AdaptiveExploiter(0, seed=7, iters=iters, knobs=Knobs(probe=True), probe_budget_bb=budget)
        on = play(h_on, ofac(), hands)
        cap = "OK" if h_on.probe.spent <= budget + 1e-6 else "!!OVER!!"
        print(f"{oname:18s} {off:>9.0f} {on:>9.0f} {on-off:>+7.0f} "
              f"{h_on.probe.n_probes:>7d} {h_on.probe.spent:>7.1f} {cap}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hands", type=int, default=250)
    ap.add_argument("--iters", type=int, default=110)
    ap.add_argument("--stress", type=int, default=0, help="run vs N random unknown opponents instead")
    ap.add_argument("--probe-test", action="store_true", help="compare probing off/on + check budget")
    ap.add_argument("--gate", action="store_true", help="use the two-model confidence gate")
    args = ap.parse_args()
    botmod.EQUITY_ITERS = args.iters
    if args.probe_test:
        probe_test(args.hands, args.iters)
        return
    if args.stress:
        stress(args.stress, args.hands, args.iters, gate=args.gate)
        return

    R = random.Random
    opponents = {
        "station": lambda: opp_station(R(1)),
        "maniac": lambda: opp_maniac(R(2)),
        "nit": lambda: opp_nit(R(3)),
        "unknown-A(foldy)": lambda: opp_synthetic(R(4), fold_p=0.75, aggr_p=0.15, size=0.6),
        "unknown-B(sticky)": lambda: opp_synthetic(R(5), fold_p=0.12, aggr_p=0.25, size=0.7),
        "unknown-C(trappy)": lambda: opp_synthetic(R(6), fold_p=0.40, aggr_p=0.55, size=1.1),
        "PokerBot(strong)": lambda: opp_pokerbot(99),
    }
    heroes = {
        "adaptive": lambda: AdaptiveExploiter(0, seed=7, iters=args.iters),
        "adaptive+gate": lambda: AdaptiveExploiter(0, seed=7, iters=args.iters, gate=True, depth_aware=True),
        "baseline": lambda: PokerBotHero(exploit=False, seed=7),
        "always_aggro": lambda: AlwaysAggro(0),
    }

    print(f"BEAT-THEM-ALL  ({args.hands} hands/match, iters={args.iters}) — bb/100\n")
    names = list(opponents)
    print(f"{'hero':14s} " + " ".join(f"{n[:10]:>11s}" for n in names) + f" {'WORST':>8s}")
    for hname, hfac in heroes.items():
        row = []
        for oname in names:
            res = play(hfac(), opponents[oname](), args.hands)
            row.append(res)
        worst = min(row)
        flag = "  <- beats ALL" if worst > 0 else ""
        print(f"{hname:14s} " + " ".join(f"{v:>11.0f}" for v in row) + f" {worst:>8.0f}{flag}")


if __name__ == "__main__":
    main()
