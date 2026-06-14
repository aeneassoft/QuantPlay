"""Validate the decision engine: bot-vs-bot legality + chip conservation, and spot checks."""
from __future__ import annotations

import random

import pokerbot.strategy.bot as botmod
from pokerbot.engine.game import HeadsUpGame
from pokerbot.strategy.bot import PokerBot

botmod.EQUITY_ITERS = 500  # faster for the test


def _legal_state(hole, button=0, to_act=0):
    return {
        "street": "preflop", "button": button, "bb": 100, "sb": 50, "pot": 150,
        "current_bet": 100, "board": [], "to_act": to_act, "history": [],
        "players": [
            {"idx": 0, "name": "Bot", "stack": 9950, "hole": hole,
             "committed_total": 50, "committed_street": 50, "all_in": False,
             "folded": False, "is_button": True},
            {"idx": 1, "name": "You", "stack": 9900, "hole": ["??", "??"],
             "committed_total": 100, "committed_street": 100, "all_in": False,
             "folded": False, "is_button": False},
        ],
        "legal": {"to_act": 0, "to_call": 50, "can_fold": True, "can_check": False,
                  "can_call": True, "call_amount": 50, "can_raise": True, "is_bet": False,
                  "raise_min": 200, "raise_max": 9950, "pot": 150},
    }


def spot_checks():
    bot = PokerBot(0, seed=1)
    aa = bot.decide(_legal_state(["As", "Ad"]))
    trash = bot.decide(_legal_state(["7d", "2c"]))
    print(f"  SB first-in AA  -> {aa['action']}  ({aa['rationale']['reasoning']})")
    print(f"  SB first-in 72o -> {trash['action']}  ({trash['rationale']['reasoning']})")
    assert aa["action"] in ("raise", "allin"), "AA should raise"
    assert trash["action"] == "fold", "72o should fold"


def bot_vs_bot(n=60):
    rng = random.Random(3)
    start = 10000
    total = 2 * start
    g = HeadsUpGame(names=("BotA", "BotB"), seed=11)
    bots = [PokerBot(0, seed=21), PokerBot(1, seed=22)]
    samples = []
    for _ in range(n):
        g.players[0].stack = g.players[1].stack = start
        g.start_hand()
        guard = 0
        while not g.hand_over:
            st = g.state()
            actor = st["to_act"]
            la = st["legal"]
            facing = la["to_call"] > 0
            dec = bots[actor].decide(st)
            bots[1 - actor].observe_opponent(st["street"], dec["action"], facing)
            if len(samples) < 6 and st["street"] != "preflop":
                samples.append((st["street"], dec["action"], dec["rationale"].get("reasoning", "")))
            g.act(dec["action"], dec["amount"])  # raises if illegal -> test fails
            guard += 1
            assert guard < 2000, "runaway hand"
        for b in bots:
            b.observe_hand_end()
        s0, s1 = g.players[0].stack, g.players[1].stack
        assert s0 + s1 == total, f"chip leak: {s0}+{s1}"
    print(f"  bot-vs-bot: {n} hands, all decisions legal, chips conserved.")
    print("  sample postflop decisions:")
    for street, action, why in samples:
        print(f"    [{street}] {action}: {why}")
    print("  opponent model (BotA's read of BotB):", bots[0].opp.summary())


if __name__ == "__main__":
    print("Spot checks:")
    spot_checks()
    print("Integration:")
    bot_vs_bot()
    print("OK")
