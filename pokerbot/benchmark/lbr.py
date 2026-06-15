"""LBR (Local Best Response): an HONEST lower bound on our bot's exploitability.

Exact best-response is intractable in NLHE, so we estimate exploitability by letting an LBR opponent
best-respond LOCALLY. At each LBR decision it picks the action with the highest EV, where EV is estimated
by Monte-Carlo ROLLOUTS in which:
  (a) the bot's hidden cards are RE-SAMPLED uniformly each rollout (LBR never sees them -> no hidden-info cheat),
  (b) the bot plays its REAL policy, and
  (c) LBR plays passively (check/call) after its move.
LBR's win-rate (bb/100) is then a valid LOWER BOUND on exploitability: a true best response can only do
better. A robust 'floor' keeps this small; a big number localizes a leak (which street/line LBR farms).

v1 caveat: uniform card sampling -> a LOOSE bound (a Bayesian action-consistent range would tighten it).
Run: python -m pokerbot.benchmark.lbr [--hands N] [--rollouts K] [--exploit]
"""
from __future__ import annotations

import argparse
import copy
import random
import statistics

import pokerbot.strategy.bot as botmod
from pokerbot.engine.cards import make_deck
from pokerbot.engine.game import HeadsUpGame
from pokerbot.strategy.bot import PokerBot


class _NitBot:
    """Sanity target: always checks, folds to any bet. An over-folder LBR MUST crush (validates mechanics)."""

    def __init__(self, seat, **_kw):
        self.hero_idx = seat

    def decide(self, st):
        la = st.get("legal", {})
        return {"action": "check", "amount": None} if la.get("can_check") else {"action": "fold", "amount": None}

    def observe_hand_end(self):
        pass


def _passive(la):
    if la.get("can_check"):
        return "check", None
    if la.get("can_call"):
        return "call", None
    return "fold", None


def _legalize(la, action, amount):
    """Coerce a bot action to the nearest legal one (robust e.g. when it wants to raise facing an all-in)."""
    action = (action or "").lower()
    if action in ("bet", "raise", "allin"):
        if la.get("can_raise"):
            return action, amount
        return ("call", None) if la.get("can_call") else ("check", None)
    if action == "call" and not la.get("can_call"):
        return ("check", None)
    if action == "check" and not la.get("can_check"):
        return ("call", None) if la.get("can_call") else ("fold", None)
    if action == "fold" and not la.get("can_call"):       # cannot fold when checking is free
        return ("check", None)
    return action, amount


def _candidates(game, la):
    """LBR's local action set with concrete amounts (check/call/fold + ~2/3-pot + all-in)."""
    p = game.players[game.to_act]
    out = []
    if la.get("can_check"):
        out.append(("check", None))
    if la.get("can_call"):
        out += [("call", None), ("fold", None)]
    if la.get("can_raise"):
        lab = "bet" if la["is_bet"] else "raise"
        rmin, rmax = la["raise_min"], la["raise_max"]
        tt = max(rmin, min(p.committed_street + int(0.66 * la["pot"]), rmax))
        out.append((lab, tt))
        if rmax > tt:
            out.append((lab, rmax))            # all-in (distinct from the 2/3-pot bet)
    return out


def _rollout_ev(game, lbr_idx, action, amount, rollout_bot, K, rng):
    """Mean future chip change for LBR after `action`, over K rollouts with re-sampled bot cards."""
    bot_idx = 1 - lbr_idx
    fixed = set(game.players[lbr_idx].hole) | set(game.board)
    pool = [c for c in make_deck() if c not in fixed]
    base = game.players[lbr_idx].stack
    total = 0.0
    for _ in range(K):
        clone = copy.deepcopy(game)
        rng.shuffle(pool)
        clone.players[bot_idx].hole = list(pool[:2])      # re-sampled hidden cards (uniform range)
        rest = list(pool[2:])
        rng.shuffle(rest)
        clone.deck.cards = rest                            # fresh runout
        try:
            clone.act(action, amount)
            guard = 0
            while not clone.hand_over and guard < 400:
                guard += 1
                la = clone.legal_actions()
                actor = la.get("to_act")
                if actor is None:
                    break
                if actor == bot_idx:
                    rollout_bot.hero_idx = bot_idx
                    d = rollout_bot.decide(clone.state())
                    a, amt = _legalize(la, d["action"], d.get("amount"))
                    clone.act(a, amt)
                else:
                    a, amt = _passive(la)
                    clone.act(a, amt)
        except Exception:  # noqa: BLE001  (a malformed line just contributes 0)
            continue
        total += clone.players[lbr_idx].stack - base
    return total / max(1, K)


def lbr_bb100(make_bot, hands=120, K=8, start=10000, sb=50, bb=100, seed=7, iters=80):
    botmod.EQUITY_ITERS = iters
    g = HeadsUpGame(names=("Bot", "LBR"), starting_stack=start, sb=sb, bb=bb, seed=seed)
    measured = make_bot(0)              # the bot under test (seat 0); stationary -> not fed LBR reads
    rollout_bot = make_bot(0)           # reused across rollouts (same stationary policy)
    net = []
    for _hi in range(hands):
        # Per-hand reseed -> PAIRED / duplicate eval: hand index _hi deals identical cards and uses identical
        # rollout randomness across runs, regardless of decisions, so leak-free hands cancel in an A/B delta.
        g.rng = random.Random(f"deck-{seed}-{_hi}")
        rng = random.Random(f"roll-{seed}-{_hi}")
        g.players[0].stack = g.players[1].stack = start
        g.start_hand()
        guard = 0
        while not g.hand_over and guard < 400:
            guard += 1
            st = g.state()
            la = st["legal"]
            actor = la.get("to_act")
            if actor is None:
                break
            if actor == 0:
                measured.hero_idx = 0
                d = measured.decide(st)
                a, amt = _legalize(la, d["action"], d.get("amount"))
                g.act(a, amt)
            else:                          # LBR best-responds locally
                best, bev = ("fold", None), -1e18
                for a, amt in _candidates(g, la):
                    ev = 0.0 if a == "fold" else _rollout_ev(g, 1, a, amt, rollout_bot, K, rng)
                    if ev > bev:
                        bev, best = ev, (a, amt)
                g.act(best[0], best[1])
        if hasattr(measured, "observe_hand_end"):
            measured.observe_hand_end()
        net.append(g.players[1].stack - start)     # LBR's winnings = exploitability (in chips; bb=100)
    mean = sum(net) / len(net)
    se = statistics.pstdev(net) / (len(net) ** 0.5) if len(net) > 1 else 0.0
    return mean, se, net


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hands", type=int, default=120)
    ap.add_argument("--rollouts", type=int, default=8)
    ap.add_argument("--exploit", action="store_true", help="measure the exploit-ON bot (default: baseline floor)")
    ap.add_argument("--target", choices=["bot", "nit"], default="bot", help="nit = mechanics sanity check")
    ap.add_argument("--iters", type=int, default=80)
    args = ap.parse_args()

    if args.target == "nit":
        def make_bot(seat):
            return _NitBot(seat)
        label = "NIT sanity (LBR must crush)"
    else:
        def make_bot(seat):
            return PokerBot(seat, seed=0, exploit=args.exploit)
        label = "exploit-ON" if args.exploit else "baseline floor"
    print(f"LBR exploitability ({label}) | {args.hands} hands x {args.rollouts} rollouts ...", flush=True)
    mean, se, _ = lbr_bb100(make_bot, hands=args.hands, K=args.rollouts, iters=args.iters)
    print(f"  LBR wins {mean:+.0f} +/- {se:.0f} bb/100  (lower bound on exploitability; lower=more robust)")


if __name__ == "__main__":
    main()
