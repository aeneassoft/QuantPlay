"""Phase 1: a position-aware, Chen-balanced near-GTO BASELINE.

Replaces the loose, self-exploitable baseline that lost -207 bb/100 to Slumbot. Built to be HARD to
exploit (balanced bluff/value, MDF defense, anti-spew) rather than to exploit — it is the GTO anchor
the adaptive regime switch (Phase 2) deviates FROM only when a leak is statistically proven.

Grounding (our books):
  * Bill Chen / *Mathematics of Poker*: bluff frequency alpha = s/(1+s); MDF = P/(P+B); polarised
    value/bluff betting; indifference.
  * *Modern Poker Theory* (Acevedo): position-aware preflop widths, standard sizings.

Reusable: GTOBaseline.decide(state) -> (action, amount). Live test vs Slumbot built in.
Run: python -m pokerbot.strategy.gto_baseline --hands 300
"""
from __future__ import annotations

import random

from pokerbot.engine.cards import hand_class
from pokerbot.engine.equity import equity_vs_class_range
from pokerbot.engine.evaluator import best_five_name
from pokerbot.strategy import preflop_strength as ps
from pokerbot.strategy.postflop import cbet_policy, classify_board


class GTOBaseline:
    VALUE_EQ = 0.62
    BLUFF_EQ = 0.38

    # Analytic thresholds as PRIORS — an optimiser may tune them against the GTO benchmark.
    PARAMS = {"cbet_eq": 0.48, "cbet_bluff": 0.6, "cbet_size": 0.5,
              "donk_eq": 0.80, "donk_freq": 0.25}

    def __init__(self, hero: int = 0, seed: int = 0, iters: int = 300, params: dict | None = None) -> None:
        self.hero = hero
        self.rng = random.Random(seed)
        self.iters = iters
        self.p = dict(self.PARAMS)
        self.p.update(params or {})

    # no-op hooks so it can drop into adaptive/Slumbot hero loops unchanged
    def observe_opponent(self, *a, **k) -> None: ...
    def observe_hand_end(self, *a, **k) -> None: ...

    def decide(self, state: dict):
        la = state["legal"]
        me = state["players"][self.hero]
        hole, board = me["hole"], state["board"]
        pot, to_call = la["pot"], la["to_call"]
        can_check, can_raise, is_bet = la["can_check"], la["can_raise"], la["is_bet"]
        committed = me["committed_street"]
        bb = state["bb"]
        cur = state.get("current_bet", to_call + committed)
        agg = "bet" if is_bet else "raise"

        def rto(chips):
            lo, hi = la["raise_min"], la["raise_max"]
            return hi if lo is None else max(lo, min(int(chips), hi))

        # ---- equity (postflop: narrow villain range on a bet -> anti-spew) ----
        made = scare = None
        if board:
            base = 0.55
            if to_call > 0:
                r = to_call / max(1.0, pot - to_call)
                sf = {"flop": 0.9, "turn": 0.78, "river": 0.62}.get(state["street"], 1.0)
                base = max(0.07, base * sf * (1 - 0.7 * min(1.5, r)))
            eq = equity_vs_class_range(hole, list(ps.range_top(base)), board, iters=self.iters, rng=self.rng)
            made = best_five_name(board, hole)
            tex = classify_board(board)
            scare = tex["monotone"] or (tex["connected"] and len(board) >= 4)
        else:
            eq = ps.percentile(hand_class(*hole))

        # ---------- facing a bet ----------
        if to_call > 0:
            req = to_call / (pot + to_call)
            if board:
                thresh = req + (0.10 if scare else 0.0)
                if made == "High Card":
                    thresh = max(thresh, req + 0.12)          # never stack off air
                if eq >= 0.80 and can_raise and not scare:    # value-raise: strong, capped (no overbet spew)
                    return agg, rto(committed + to_call + int(0.7 * (pot + to_call)))
                if eq >= thresh:
                    return "call", None
                return ("check" if can_check else "fold"), None
            # preflop facing a bet
            if cur <= bb * 1.5:                               # open spot (only blinds out)
                if eq >= 0.18 and can_raise:                  # open ~top 82% (HU button is wide)
                    return agg, rto(committed + int(2.5 * bb))
                return ("check" if can_check else "fold"), None
            if eq >= 0.90 and can_raise:                      # 3-bet for value
                return agg, rto(cur + int(1.0 * (pot + to_call)))
            defend = max(0.30, min(0.80, 1.10 - 1.5 * req))   # defend by pot-odds (wide vs small raises)
            if eq >= 1 - defend:
                return "call", None
            return ("check" if can_check else "fold"), None

        # ---------- betting / check ----------
        if not can_raise:
            return "check", None
        if board:
            aggr = state.get("aggressor")     # True = I had initiative this hand; False = I'm the caller
            if aggr is False:                 # caller w/o initiative: check to the raiser; donk rarely
                if eq >= self.p["donk_eq"] and self.rng.random() < self.p["donk_freq"]:
                    return agg, rto(committed + int(self.p["cbet_size"] * pot))
                return "check", None
            if aggr is True:                  # aggressor: texture-conditioned c-bet (openai_strategy table)
                if len(board) == 3:           # flop: frequency + size by board class (range-bet)
                    f_cbet, size = cbet_policy(board, ip=(self.hero == state["button"]))
                    if eq >= self.p["cbet_eq"] or self.rng.random() < f_cbet:
                        return agg, rto(committed + int(size * pot))
                    return "check", None
                # turn/river: merged c-bet (texture-aware barreling is a later step)
                if eq >= self.p["cbet_eq"] or (eq <= self.BLUFF_EQ and self.rng.random() < self.p["cbet_bluff"]):
                    return agg, rto(committed + int(self.p["cbet_size"] * pot))
                return "check", None
            if eq >= self.VALUE_EQ:           # unknown role: original equity-threshold behaviour
                return agg, rto(committed + int(0.7 * pot))
            if eq <= self.BLUFF_EQ and self.rng.random() < 0.42:
                return agg, rto(committed + int(0.7 * pot))
            return "check", None
        if eq >= 0.55:                                        # preflop BB option: raise strong, else check
            return agg, rto(committed + int(3 * bb))
        return "check", None


def main() -> None:
    import argparse
    import math

    import pokerbot.benchmark.slumbot as S

    ap = argparse.ArgumentParser()
    ap.add_argument("--hands", type=int, default=300)
    ap.add_argument("--iters", type=int, default=250)
    args = ap.parse_args()
    hero = GTOBaseline(0, seed=7, iters=args.iters)
    token, win = None, []
    for h in range(args.hands):
        resp = S._post("/api/new_hand", {"token": token} if token else {})
        token = resp.get("token", token)
        first = resp.get("action", "")
        button = resp.get("client_pos", 0) if first == "" else 1 - resp.get("client_pos", 0)
        w, guard = 0, 0
        while True:
            if resp.get("error_msg") or resp.get("winnings") is not None:
                w = resp.get("winnings") or 0
                break
            st = S.build_state(resp["hole_cards"], resp.get("board", []), resp.get("action", ""),
                               resp["client_pos"], button)
            if st is None:
                w = resp.get("winnings") or 0
                break
            hero.hero = resp["client_pos"]
            a, amt = hero.decide(st)
            resp = S._post("/api/act", {"token": token, "incr": S.decision_to_incr({"action": a, "amount": amt}, st)})
            token = resp.get("token", token)
            guard += 1
            if guard > 60:
                w = resp.get("winnings") or 0
                break
        win.append(w)
        if (h + 1) % 25 == 0:
            print(f"  {h+1:4d} hands | {sum(win)/len(win):+.1f} bb/100", flush=True)
    n = len(win)
    bb100 = sum(win) / n
    std = (sum((x - bb100) ** 2 for x in win) / n) ** 0.5 / S.BB
    print(f"\n=== GTO baseline vs Slumbot ===\nhands={n} | {bb100:+.1f} bb/100 (±{std/math.sqrt(n)*100:.1f} stderr)")


if __name__ == "__main__":
    main()
