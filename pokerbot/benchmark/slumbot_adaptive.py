"""Play our WEAPONIZED bot (AdaptiveExploiter + gate + depth-aware) LIVE vs Slumbot, learning its
tendencies online. Reuses the slumbot.py client; adds an adapter + opponent-action observation so
the bot builds Slumbot's fold curve across hands and exploits it. This is the one real card-aware
head-to-head we can run for free.

Run:  python -m pokerbot.benchmark.slumbot_adaptive --hands 400 [--iters 300]
"""
from __future__ import annotations

import argparse
import math
import time

import pokerbot.benchmark.slumbot as S
from pokerbot.strategy.adaptive import AdaptiveExploiter


def walk_decisions(action: str, button: int):
    """Yield (street, to_call, pot, actor, label) for every token in Slumbot's action string,
    reconstructing pot/to_call exactly like build_state does — so we can feed opponent decisions."""
    other = 1 - button
    committed = [0, 0]
    sc = [0, 0]
    cur = 0
    actor = button
    sname = "preflop"
    for si, seg in enumerate(action.split("/")):
        if si == 0:
            sc = [0, 0]
            sc[button], sc[other] = S.SB, S.BB
            cur, actor, sname = S.BB, button, "preflop"
        else:
            committed[0] += sc[0]
            committed[1] += sc[1]
            sc = [0, 0]
            cur, actor, sname = 0, other, S.STREETS[si]
        for tok in S.parse_tokens(seg):
            to_call = cur - sc[actor]
            pot = committed[0] + committed[1] + sc[0] + sc[1]
            if tok == "f":
                yield sname, to_call, pot, actor, "fold"
            elif tok == "k":
                yield sname, to_call, pot, actor, "check"
            elif tok == "c":
                yield sname, to_call, pot, actor, "call"
                sc[actor] = min(cur, S.STACK - committed[actor])
            else:  # bet/raise
                to = int(tok[1:])
                yield sname, to_call, pot, actor, "raise"
                sc[actor], cur = to, to
            actor = 1 - actor


class AdaptiveHero:
    def __init__(self, iters: int):
        self.ex = AdaptiveExploiter(0, seed=7, iters=iters, gate=True, depth_aware=True)
        self.hero_idx = 0
        self._seen = 0

    def new_hand(self):
        self._seen = 0

    def observe(self, action: str, button: int):
        i = 0
        for sname, to_call, pot, actor, lbl in walk_decisions(action, button):
            i += 1
            if i <= self._seen or actor == self.hero_idx:
                continue
            self.ex.observe_opponent({"street": sname, "legal": {"to_call": to_call, "pot": pot}}, lbl)
        self._seen = i

    def decide(self, st: dict) -> dict:
        self.ex.hero = self.hero_idx
        a, amt = self.ex.decide(st)
        return {"action": a, "amount": amt}


def play_hand(hero: AdaptiveHero, token, verbose=False):
    resp = S._post("/api/new_hand", {"token": token} if token else {})
    token = resp.get("token", token)
    first = resp.get("action", "")
    button = resp.get("client_pos", 0) if first == "" else 1 - resp.get("client_pos", 0)
    hero.new_hand()
    guard = 0
    while True:
        if resp.get("error_msg"):
            return 0, token
        if resp.get("winnings") is not None:
            hero.hero_idx = resp.get("client_pos", hero.hero_idx)
            hero.observe(resp.get("action", ""), button)
            hero.ex.observe_hand_end()
            return resp["winnings"], token
        action = resp.get("action", "")
        hero.hero_idx = resp["client_pos"]
        hero.observe(action, button)
        st = S.build_state(resp["hole_cards"], resp.get("board", []), action, resp["client_pos"], button)
        if st is None:
            return (resp.get("winnings") or 0), token
        dec = hero.decide(st)
        if verbose:
            print(f"  [{st['street']}] {resp['hole_cards']} board {resp.get('board')} -> "
                  f"{dec['action']} {dec.get('amount') or ''}")
        resp = S._post("/api/act", {"token": token, "incr": S.decision_to_incr(dec, st)})
        token = resp.get("token", token)
        guard += 1
        if guard > 60:
            return resp.get("winnings") or 0, token


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hands", type=int, default=400)
    ap.add_argument("--iters", type=int, default=300)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    hero = AdaptiveHero(args.iters)
    token = None
    win = []
    t0 = time.time()
    for h in range(args.hands):
        w, token = play_hand(hero, token, verbose=args.verbose and h < 4)
        win.append(w)
        if (h + 1) % 25 == 0:
            tot = sum(win)
            print(f"  {h+1:4d} hands | total {tot:+d} | {tot/len(win):+.1f} bb/100 "
                  f"| read={hero.ex.prof.summary()} | {(time.time()-t0)/(h+1)*1000:.0f} ms/hand", flush=True)
    n = len(win)
    tot = sum(win)
    bb100 = tot / n
    std = (sum((w - bb100) ** 2 for w in win) / n) ** 0.5 / S.BB
    print(f"\n=== WEAPONIZED bot vs Slumbot ===\nhands={n} | total={tot:+d} chips | "
          f"{bb100:+.1f} bb/100 (±{std/math.sqrt(n)*100:.1f} stderr) | final read={hero.ex.prof.summary()}")


if __name__ == "__main__":
    main()
