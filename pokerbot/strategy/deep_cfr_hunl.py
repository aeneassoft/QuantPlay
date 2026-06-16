"""Deep CFR for HEADS-UP NLHE — our own from-scratch neural self-play GTO core (the HUNL scale-up of the
Leduc-proven deep_cfr.py). Self-contained, cloneable, CFR-traversable game (NOT the live game.py, which is built
for play, not tree traversal). Betting abstraction = fcpa (fold / call|check / pot-raise / all-in), capped raises
-> a bounded tree. treys showdown. Two nets (Deep CFR proper, since HUNL has too many infosets for a tabular
average strategy): an ADVANTAGE net per player (regrets) + a POLICY net (the time-averaged Nash strategy).

Built + validated in stages: (1) the GAME (self-test: random rollouts conserve chips + terminal/showdown sane),
(2) the Deep CFR trainer, (3) head-to-head validation vs check-call/always-fold (no exact exploitability on HUNL),
(4) export the policy net for the bot adapter.

Chip model: `committed[p]` = total chips p has put in THIS hand (cumulative, the only contribution var); `to_match`
= the committed-level the current street's action must reach. owe = to_match - committed[p]; remaining =
stack0 - committed[p]. A street closes when both players have voluntarily acted since the last raise and committed
levels are equal (with the special preflop big-blind option). The pot = sum(committed); util uses committed.

Run the game self-test:  python -m pokerbot.strategy.deep_cfr_hunl --selftest
"""
from __future__ import annotations

import argparse
import random
from collections import deque

import numpy as np
import torch
import torch.nn as nn
from treys import Card, Evaluator

_EVAL = Evaluator()
_RANKS = "23456789TJQKA"
_SUITS = "shdc"
DECK = [r + s for r in _RANKS for s in _SUITS]      # 52 two-char cards ('As','Td',...)

FOLD, CALL, POT, ALLIN = 0, 1, 2, 3                 # fcpa betting abstraction
NACT = 4
_ANAME = {FOLD: "f", CALL: "c", POT: "p", ALLIN: "a"}

SB, BB = 50, 100
START_STACK = 20000        # 200bb
MAX_RAISES = 4             # per-street raise cap (bounds the tree; all-in still always available)


class HState:
    __slots__ = ("hole", "board", "deck", "street", "committed", "stack0", "to_act", "to_match",
                 "raises", "acted", "done", "fold_winner", "hist")

    def __init__(self):
        self.hole = [[], []]
        self.board = []
        self.deck = []
        self.street = 0
        self.committed = [SB, BB]         # blinds; player0 = SB/button (acts first preflop, HU rule)
        self.stack0 = START_STACK
        self.to_act = 0
        self.to_match = BB                # preflop level to match = the big blind
        self.raises = 0
        self.acted = [False, False]       # voluntarily acted since the last raise / street start
        self.done = False
        self.fold_winner = -1
        self.hist = ""

    def clone(self):
        s = HState.__new__(HState)
        s.hole = [list(self.hole[0]), list(self.hole[1])]
        s.board = list(self.board)
        s.deck = list(self.deck)
        s.street = self.street
        s.committed = list(self.committed)
        s.stack0 = self.stack0
        s.to_act = self.to_act
        s.to_match = self.to_match
        s.raises = self.raises
        s.acted = list(self.acted)
        s.done = self.done
        s.fold_winner = self.fold_winner
        s.hist = self.hist
        return s

    def legal(self):
        if self.done:
            return []
        p = self.to_act
        owe = self.to_match - self.committed[p]
        rem = self.stack0 - self.committed[p]
        acts = []
        if owe > 0:
            acts.append(FOLD)                       # facing a bet -> can fold
        acts.append(CALL)                           # call (owe>0) or check (owe==0)
        call_cost = min(owe, rem)
        if self.raises < MAX_RAISES and rem > call_cost:      # there is money beyond the call -> can raise
            pot_after_call = sum(self.committed) + owe
            raise_to = self.to_match + pot_after_call
            if raise_to - self.committed[p] < rem:  # a pot-raise is a distinct, non-all-in amount
                acts.append(POT)
            acts.append(ALLIN)
        return acts

    def apply(self, a):
        s = self.clone()
        s.hist += _ANAME[a]
        p = s.to_act
        opp = 1 - p
        owe = s.to_match - s.committed[p]
        rem = s.stack0 - s.committed[p]
        if a == FOLD:
            s.done = True
            s.fold_winner = opp
            return s
        if a == CALL:
            s.committed[p] += min(owe, rem)
            s.acted[p] = True
            if s.acted[opp]:                        # opponent already had a turn this street -> calling closes it
                s._end_street()
            else:                                   # e.g. SB limp -> BB still has the option; or check to opp
                s.to_act = opp
            return s
        # POT or ALLIN -> a raise
        if a == ALLIN:
            s.committed[p] = s.stack0
        else:
            pot_after_call = sum(s.committed) + owe
            s.committed[p] = min(s.to_match + pot_after_call, s.stack0)
        s.to_match = max(s.to_match, s.committed[p])
        s.raises += 1
        s.acted = [False, False]
        s.acted[p] = True
        s.to_act = opp
        return s

    def _end_street(self):
        allin = any((self.stack0 - self.committed[i]) == 0 for i in (0, 1))
        if self.street >= 3:
            self.done = True
            return
        if allin:                                   # bets matched + someone all-in -> run out the board
            while len(self.board) < 5:
                self.board.append(self.deck.pop())
            self.street = 3
            self.done = True
            return
        self._advance_street()

    def _advance_street(self):
        self.street += 1
        n = {1: 3, 2: 4, 3: 5}[self.street]
        while len(self.board) < n:
            self.board.append(self.deck.pop())
        self.to_match = max(self.committed)         # committed are equal here (street ended matched)
        self.raises = 0
        self.acted = [False, False]
        self.to_act = 1                             # postflop: BB (player1, OOP) acts first in HU

    def util0(self):
        """Terminal chips for player 0 (zero-sum: player1 = -util0)."""
        if self.fold_winner == 0:
            return float(self.committed[1])
        if self.fold_winner == 1:
            return float(-self.committed[0])
        b = [Card.new(c) for c in self.board]       # showdown (treys: lower rank = better)
        r0 = _EVAL.evaluate(b, [Card.new(c) for c in self.hole[0]])
        r1 = _EVAL.evaluate(b, [Card.new(c) for c in self.hole[1]])
        if r0 < r1:
            return float(self.committed[1])
        if r1 < r0:
            return float(-self.committed[0])
        return 0.0


def new_hand(rng: random.Random) -> HState:
    s = HState()
    s.deck = list(DECK)
    rng.shuffle(s.deck)
    s.hole = [[s.deck.pop(), s.deck.pop()], [s.deck.pop(), s.deck.pop()]]
    return s


def _selftest(n=20000):
    rng = random.Random(0)
    chips_ok = True
    terminals = {"fold": 0, "showdown": 0}
    pots, u0s = [], []
    for _ in range(n):
        s = new_hand(rng)
        depth = 0
        while not s.done and depth < 300:
            la = s.legal()
            assert la, f"no legal actions at non-terminal! hist={s.hist}"
            s = s.apply(rng.choice(la))
            depth += 1
        assert s.done, f"not terminal after {depth}: {s.hist}"
        terminals["fold" if s.fold_winner >= 0 else "showdown"] += 1
        u0 = s.util0()
        u0s.append(u0)
        if abs(u0) > START_STACK or sum(s.committed) < SB + BB:
            chips_ok = False
        pots.append(sum(s.committed))
    print(f"self-test {n} random hands: {'CHIPS OK' if chips_ok else 'CHIP LEAK!'}")
    print(f"  terminals: {terminals}")
    print(f"  pot: min {min(pots)}  mean {sum(pots)/len(pots):.0f}  max {max(pots)}  (2*stack={2*START_STACK})")
    print(f"  util0: mean {sum(u0s)/len(u0s):+.1f}  (should be ~0 by symmetry over many hands)")
    print(f"  sample lines: " + ", ".join(_play_random(random.Random(i)) for i in range(4)))


def _play_random(rng):
    s = new_hand(rng)
    while not s.done:
        s = s.apply(rng.choice(s.legal()))
    return s.hist or "-"


# ========================= Deep CFR (dual-net: advantage + policy) =========================
SCALE = float(START_STACK)        # normalize utilities -> net targets ~[-1,1]
FEATD = 20


def _pf_strength(hole):
    r = sorted((_RANKS.index(c[0]) for c in hole), reverse=True)
    pair, suited = r[0] == r[1], hole[0][1] == hole[1][1]
    s = (r[0] + r[1]) / 24.0
    if pair:
        s = 0.55 + r[0] / 30.0
    if suited:
        s += 0.05
    if not pair and (r[0] - r[1]) <= 2:
        s += 0.03
    return min(1.0, s)


def features(s: HState, p: int) -> np.ndarray:
    v = np.zeros(FEATD, dtype=np.float32)
    v[s.street] = 1.0                                   # 0..3 street one-hot
    v[4] = 1.0 if p == 0 else 0.0                       # button (player0)?
    v[5] = sum(s.committed) / (2 * SCALE)
    v[6] = (s.to_match - s.committed[p]) / SCALE        # owe
    v[7] = (START_STACK - s.committed[p]) / SCALE       # remaining
    v[8] = s.raises / MAX_RAISES
    hole, board = s.hole[p], s.board
    if board:
        v[9] = 1.0 - _EVAL.evaluate([Card.new(c) for c in board], [Card.new(c) for c in hole]) / 7462.0
    else:
        v[9] = _pf_strength(hole)
    rk = sorted((_RANKS.index(c[0]) for c in hole), reverse=True)
    v[10] = rk[0] / 12.0
    v[11] = rk[1] / 12.0
    v[12] = 1.0 if hole[0][0] == hole[1][0] else 0.0    # pocket pair
    v[13] = 1.0 if hole[0][1] == hole[1][1] else 0.0    # suited
    v[14] = (rk[0] - rk[1]) / 12.0                      # gap
    if board:
        bs = [c[1] for c in board]
        br = [c[0] for c in board]
        v[15] = max(bs.count(x) for x in set(bs)) / 5.0                       # max suit count (flush-ness)
        v[16] = (len(board) - len(set(br))) / 5.0                            # paired-ness
        alls = bs + [c[1] for c in hole]
        v[17] = 1.0 if max(alls.count(x) for x in set(alls)) >= 4 else 0.0   # flush draw/made
    v[18] = len(board) / 5.0
    v[19] = 1.0                                          # bias
    return v


class Net(nn.Module):
    def __init__(self, h=256):
        super().__init__()
        self.f = nn.Sequential(nn.Linear(FEATD, h), nn.ReLU(), nn.Linear(h, h), nn.ReLU(),
                               nn.Linear(h, h), nn.ReLU(), nn.Linear(h, NACT))

    def forward(self, x):
        return self.f(x)


def _rm(adv, legal):
    pos = np.maximum(adv, 0.0)
    ssum = sum(pos[a] for a in legal)
    if ssum > 1e-9:
        return {a: pos[a] / ssum for a in legal}
    return {a: 1.0 / len(legal) for a in legal}


class DeepCFRHUNL:
    def __init__(self, device="cpu", seed=0):
        self.dev = torch.device(device)
        self.adv = [Net().to(self.dev), Net().to(self.dev)]
        self.policy = Net().to(self.dev)
        self.adv_mem = [deque(maxlen=600_000), deque(maxlen=600_000)]
        self.pol_mem = deque(maxlen=1_500_000)
        self.rng = random.Random(seed)

    def _adv_strat(self, s, p):
        legal = s.legal()
        with torch.no_grad():
            x = torch.tensor(features(s, p), device=self.dev).unsqueeze(0)
            a = self.adv[p](x).cpu().numpy()[0]
        return _rm(a, legal)

    def traverse(self, s: HState, trav: int, t: int) -> float:
        if s.done:
            return (s.util0() if trav == 0 else -s.util0()) / SCALE
        p = s.to_act
        legal = s.legal()
        strat = self._adv_strat(s, p)
        if p == trav:
            f = features(s, p)
            sv = np.zeros(NACT, dtype=np.float32)
            for a in legal:
                sv[a] = strat[a]
            self.pol_mem.append((f, sv, float(t)))
            util = np.zeros(NACT, dtype=np.float32)
            node = 0.0
            for a in legal:
                util[a] = self.traverse(s.apply(a), trav, t)
                node += strat[a] * util[a]
            reg = np.zeros(NACT, dtype=np.float32)
            for a in legal:
                reg[a] = util[a] - node
            self.adv_mem[trav].append((f, reg, float(t)))
            return node
        a = self.rng.choices(legal, weights=[strat[x] for x in legal])[0]
        return self.traverse(s.apply(a), trav, t)

    def _fit(self, net, mem, epochs, softmax_out, bs=4096, lr=1e-3):
        X = torch.tensor(np.array([m[0] for m in mem]), device=self.dev)
        Y = torch.tensor(np.array([m[1] for m in mem]), device=self.dev)
        W = torch.tensor(np.array([m[2] for m in mem], dtype=np.float32), device=self.dev).unsqueeze(1)
        opt = torch.optim.Adam(net.parameters(), lr=lr)
        n = X.shape[0]
        bs = min(bs, n)
        for _ in range(epochs):
            idx = torch.randperm(n, device=self.dev)
            for i in range(0, n, bs):
                b = idx[i:i + bs]
                opt.zero_grad()
                out = net(X[b])
                if softmax_out:
                    out = torch.softmax(out, dim=1)
                loss = (W[b] * (out - Y[b]) ** 2).mean()
                loss.backward()
                opt.step()

    def train_adv(self, p, epochs=12):
        if len(self.adv_mem[p]) >= 64:
            self.adv[p] = Net().to(self.dev)             # Deep CFR: reinit advantage net each iter
            self._fit(self.adv[p], self.adv_mem[p], epochs, softmax_out=False)

    def train_policy(self, epochs=20):
        if len(self.pol_mem) >= 64:
            self.policy = Net().to(self.dev)
            self._fit(self.policy, self.pol_mem, epochs, softmax_out=True)

    def policy_strategy(self, s, p):
        legal = s.legal()
        with torch.no_grad():
            x = torch.tensor(features(s, p), device=self.dev).unsqueeze(0)
            pr = torch.softmax(self.policy(x), dim=1).cpu().numpy()[0]
        z = {a: max(float(pr[a]), 1e-9) for a in legal}
        tot = sum(z.values())
        return {a: z[a] / tot for a in legal}


# ---- baselines + head-to-head rollout (no exact exploitability on HUNL) ----
def _cc(s, p):
    la = s.legal()
    return {CALL: 1.0} if CALL in la else {la[0]: 1.0}


def _fold(s, p):
    la = s.legal()
    return {FOLD: 1.0} if FOLD in la else {CALL: 1.0}


def _rand(s, p):
    la = s.legal()
    return {a: 1.0 / len(la) for a in la}


def rollout(polf, oppf, n, seed=99):
    """policy (polf) vs opponent (oppf), seats alternated to cancel position; returns the policy's bb/100."""
    rng = random.Random(seed)
    tot = 0.0
    for i in range(n):
        s = new_hand(rng)
        pol_seat = i % 2
        while not s.done:
            p = s.to_act
            pr = (polf if p == pol_seat else oppf)(s, p)
            acts = list(pr)
            a = rng.choices(acts, weights=[pr[x] for x in acts])[0]
            s = s.apply(a)
        u0 = s.util0()
        tot += u0 if pol_seat == 0 else -u0
    return tot / n / BB * 100.0


def evaluate(cfr, n=3000):
    pol = cfr.policy_strategy
    return (f"vs call-station {rollout(pol, _cc, n):+7.1f} | vs always-fold {rollout(pol, _fold, n):+7.1f} | "
            f"vs random {rollout(pol, _rand, n):+7.1f}  bb/100")


def train(iters, trav, device, seed=0, evalint=10, out=None):
    print(f"Deep CFR on HUNL (fcpa) | device={device} | {iters} iters x {trav} trav | feat={FEATD}", flush=True)
    cfr = DeepCFRHUNL(device=device, seed=seed)
    rng = random.Random(seed + 1)
    import time
    t0 = time.time()
    for t in range(1, iters + 1):
        for tr in (0, 1):
            for _ in range(trav):
                cfr.traverse(new_hand(rng), tr, t)
            cfr.train_adv(tr)
        if t % evalint == 0 or t == iters:
            cfr.train_policy()
            print(f"  iter {t:4d} | {evaluate(cfr)} | {time.time()-t0:.0f}s "
                  f"| advmem {len(cfr.adv_mem[0])} polmem {len(cfr.pol_mem)}", flush=True)
    if out:
        torch.save({"policy": cfr.policy.state_dict(), "featd": FEATD, "scale": SCALE,
                    "iters": iters, "trav": trav}, out)
        print(f"saved policy net -> {out}", flush=True)
    return cfr


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--train", action="store_true")
    ap.add_argument("--iters", type=int, default=100)
    ap.add_argument("--trav", type=int, default=300)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    if args.selftest:
        _selftest()
    elif args.train:
        train(args.iters, args.trav, args.device, out=args.out)
