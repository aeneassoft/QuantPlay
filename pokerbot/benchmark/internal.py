"""Local benchmark: our bot vs simple baseline opponents (fast, no network).

Complements the Slumbot benchmark — shows the bot crushes weak/exploitable opponents
(which a strong exploitative bot must), while Slumbot measures it vs a near-GTO peer.

Run:  python -m pokerbot.benchmark.internal [--hands N]
"""
from __future__ import annotations

import argparse
import random
import statistics

import pokerbot.strategy.bot as botmod
from pokerbot.engine.game import HeadsUpGame
from pokerbot.strategy.bot import PokerBot


def station(la, rng):
    """Calling station: never folds, never raises."""
    if la["can_check"]:
        return "check", None
    if la["can_call"]:
        return "call", None
    return "fold", None


def maniac(la, rng):
    """Hyper-aggressive: raises minimum often, otherwise calls."""
    if la["can_raise"] and rng.random() < 0.55:
        return ("bet" if la["is_bet"] else "raise"), la["raise_min"]
    if la["can_check"]:
        return "check", None
    if la["can_call"]:
        return "call", None
    return "fold", None


def nit(la, rng):
    """Over-folder: folds to any bet, never bets/raises."""
    if la["can_check"]:
        return "check", None
    return "fold", None


POLICIES = {"station": station, "maniac": maniac, "nit": nit}


def run(opp: str, hands: int, start=10000, sb=50, bb=100, seed=1) -> float:
    rng = random.Random(seed)
    g = HeadsUpGame(names=("Bot", opp), starting_stack=start, sb=sb, bb=bb, seed=seed)
    bot = PokerBot(0, seed=seed, exploit=True)
    pol = POLICIES[opp]
    net = []
    for _ in range(hands):
        g.players[0].stack = g.players[1].stack = start
        g.start_hand()
        guard = 0
        while not g.hand_over:
            st = g.state()
            actor = st["to_act"]
            la = st["legal"]
            if actor == 0:
                bot.hero_idx = 0
                d = bot.decide(st)
                a, amt = d["action"], d["amount"]
            else:
                a, amt = pol(la, rng)
                bot.observe_opponent(st["street"], a, la["to_call"] > 0)
            g.act(a, amt)
            guard += 1
            assert guard < 2000
        bot.observe_hand_end()
        net.append(g.players[0].stack - start)
    bb100 = sum(net) / len(net)   # bb/100 (bb=100 chips)
    se = statistics.pstdev(net) / (len(net) ** 0.5) if len(net) > 1 else 0.0   # same bb/100 units (bb=100)
    print(f"  vs {opp:8s}: {hands} hands | bot net {sum(net):+d} chips | {bb100:+.0f} +/- {se:.0f} bb/100 "
          f"| read={bot.opp.summary()}")
    return bb100, se, net


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hands", type=int, default=400)
    ap.add_argument("--iters", type=int, default=400)
    args = ap.parse_args()
    botmod.EQUITY_ITERS = args.iters
    print("Local benchmark (our bot, exploit ON, vs baselines):")
    for opp in ("station", "maniac", "nit"):
        run(opp, args.hands)


if __name__ == "__main__":
    main()
