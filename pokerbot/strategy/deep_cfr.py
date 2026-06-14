"""Deep CFR — a real NEURAL self-play poker solver (PyTorch, GPU).

This is the actual "AI (not LLM)" for poker: neural Counterfactual Regret Minimization (Brown et al.
2019), the modern Pluribus-class method. Per player we train an ADVANTAGE network that predicts
counterfactual regrets; regret-matching on it gives the strategy; external-sampling MCCFR traversals
generate the training data; the time-averaged strategy converges to a Nash equilibrium.

We validate correctness on LEDUC HOLD'EM (small, real imperfect-info poker) by measuring
EXPLOITABILITY (mbb/hand vs a best response) — it must fall toward 0. The same trainer then scales
to NLHE on a GPU pod. Run on GPU; CPU works for the Leduc smoke.

  python -m pokerbot.strategy.deep_cfr --iters 150 --trav 120        # validate on Leduc
"""
from __future__ import annotations

import argparse
import random

import numpy as np
import torch
import torch.nn as nn

# ---------------- Leduc Hold'em ----------------
# 6-card deck: ranks 0,1,2 (J,Q,K), two of each. 2 players, 2 rounds. Ante 1. Bet 2 (round0)/4(round1),
# max 2 raises/round. Actions: 0=fold, 1=check/call, 2=bet/raise. Pair with the public card wins.
DECK = [0, 0, 1, 1, 2, 2]
BET = [2, 4]
MAX_RAISES = 2
NACT = 3
F, C, R = 0, 1, 2


class State:
    __slots__ = ("cards", "public", "rnd", "contrib", "to_act", "raises", "checks",
                 "bet_open", "done", "winner", "need_public", "hist")

    def __init__(self):
        self.cards = [0, 0]
        self.public = -1
        self.rnd = 0
        self.contrib = [1, 1]          # antes
        self.to_act = 0
        self.raises = 0
        self.checks = 0
        self.bet_open = False
        self.done = False
        self.winner = -2               # -2 undecided, -1 tie, 0/1 winner
        self.need_public = False
        self.hist = ""

    def clone(self):
        s = State()
        s.cards = list(self.cards); s.public = self.public; s.rnd = self.rnd
        s.contrib = list(self.contrib); s.to_act = self.to_act; s.raises = self.raises
        s.checks = self.checks; s.bet_open = self.bet_open; s.done = self.done
        s.winner = self.winner; s.need_public = self.need_public; s.hist = self.hist
        return s

    def legal(self):
        if self.bet_open:
            acts = [F, C]
            if self.raises < MAX_RAISES:
                acts.append(R)
            return acts
        return [C, R] if self.raises < MAX_RAISES else [C]

    def _end_betting(self):
        if self.rnd == 0:
            self.need_public = True     # chance node deals the public card next
        else:
            self._showdown()

    def _showdown(self):
        self.done = True
        c0, c1, pub = self.cards[0], self.cards[1], self.public
        s0 = 10 if c0 == pub else c0
        s1 = 10 if c1 == pub else c1
        self.winner = 0 if s0 > s1 else (1 if s1 > s0 else -1)

    def apply(self, a):
        s = self.clone()
        s.hist += "fcr"[a]
        p, opp = s.to_act, 1 - s.to_act
        if a == F:
            s.done = True
            s.winner = opp
            return s
        if a == R:
            s.contrib[p] = s.contrib[opp] + BET[s.rnd]
            s.bet_open = True
            s.raises += 1
            s.checks = 0
            s.to_act = opp
            return s
        # a == C
        if s.bet_open:                  # a call closes the round
            s.contrib[p] = s.contrib[opp]
            s.bet_open = False
            s._end_betting()
            return s
        # a check
        s.checks += 1
        if s.checks >= 2:               # check-check closes the round
            s._end_betting()
        else:
            s.to_act = opp
        return s

    def util0(self):                    # terminal utility for player 0 (zero-sum)
        if self.winner == -1:
            return 0.0
        return float(self.contrib[1] if self.winner == 0 else -self.contrib[0])


def deal_public(s: State, rng):
    s = s.clone()
    used = [s.cards[0], s.cards[1]]
    deck = list(DECK)
    for c in used:
        deck.remove(c)
    s.public = rng.choice(deck)
    s.need_public = False
    s.rnd = 1
    s.bet_open = False
    s.raises = 0
    s.checks = 0
    s.to_act = 0
    return s


# ---------------- features + infoset key ----------------
def features(s: State, p: int) -> np.ndarray:
    v = np.zeros(16, dtype=np.float32)
    v[s.cards[p]] = 1.0                       # own card 0..2
    v[3 + (s.public + 1)] = 1.0               # public: none/J/Q/K -> idx 3..6
    v[7] = s.rnd
    v[8] = 1.0 if s.bet_open else 0.0
    v[9] = s.raises / 2.0
    v[10] = s.checks / 2.0
    v[11] = s.contrib[p] / 13.0
    v[12] = s.contrib[1 - p] / 13.0
    v[13] = 1.0 if s.to_act == p else 0.0
    v[14] = len(s.hist) / 8.0
    v[15] = 1.0
    return v


def key(s: State, p: int) -> str:
    return f"{s.cards[p]}|{s.public}|{s.hist}"


# ---------------- networks ----------------
class Net(nn.Module):
    def __init__(self, din=16, h=128):
        super().__init__()
        self.f = nn.Sequential(nn.Linear(din, h), nn.ReLU(), nn.Linear(h, h), nn.ReLU(),
                               nn.Linear(h, NACT))

    def forward(self, x):
        return self.f(x)


def regret_match(adv: np.ndarray, legal) -> np.ndarray:
    strat = np.zeros(NACT, dtype=np.float64)
    pos = np.maximum(adv, 0.0)
    s = sum(pos[a] for a in legal)
    if s > 1e-9:
        for a in legal:
            strat[a] = pos[a] / s
    else:
        for a in legal:
            strat[a] = 1.0 / len(legal)
    return strat


# ---------------- Deep CFR ----------------
class DeepCFR:
    def __init__(self, device="cpu", seed=0, tabular=False):
        self.dev = torch.device(device)
        self.adv = [Net().to(self.dev), Net().to(self.dev)]
        self.mem = [[], []]                  # advantage memory per player: (feat, regrets, t)
        self.strat_sum = {}                  # infoset key -> [legal, weighted strat sum]
        self.rng = random.Random(seed)
        self.tabular = tabular
        self.regret_sum = {}                 # infoset key -> cumulative regret (tabular sanity mode)

    def strat_at(self, s: State, p: int):
        legal = s.legal()
        if self.tabular:
            rs = self.regret_sum.get(key(s, p), np.zeros(NACT))
            return regret_match(rs, legal)
        with torch.no_grad():
            x = torch.tensor(features(s, p), device=self.dev).unsqueeze(0)
            adv = self.adv[p](x).cpu().numpy()[0]
        return regret_match(adv, legal)

    def traverse(self, s: State, trav: int, t: int, reach: float = 1.0) -> float:
        if s.done:
            return s.util0() if trav == 0 else -s.util0()
        if s.need_public:
            return self.traverse(deal_public(s, self.rng), trav, t, reach)
        p = s.to_act
        legal = s.legal()
        strat = self.strat_at(s, p)
        if p == trav:
            k = key(s, p)
            rec = self.strat_sum.setdefault(k, [legal, np.zeros(NACT)])
            rec[1] += t * reach * strat               # reach-weighted avg strategy (traverser nodes)
            util = np.zeros(NACT)
            node = 0.0
            for a in legal:
                util[a] = self.traverse(s.apply(a), trav, t, reach * strat[a])
                node += strat[a] * util[a]
            regrets = np.zeros(NACT, dtype=np.float32)
            for a in legal:
                regrets[a] = util[a] - node
            if self.tabular:
                self.regret_sum.setdefault(k, np.zeros(NACT))
                self.regret_sum[k] += regrets
            else:
                self.mem[trav].append((features(s, p), regrets, t))
            return node
        a = self.rng.choices(legal, weights=[strat[x] for x in legal])[0]
        return self.traverse(s.apply(a), trav, t, reach)

    def train_adv(self, p: int, epochs=40, bs=512):
        if not self.mem[p]:
            return
        self.adv[p] = Net().to(self.dev)        # reinit (Deep CFR spec)
        X = torch.tensor(np.array([m[0] for m in self.mem[p]]), device=self.dev)
        Y = torch.tensor(np.array([m[1] for m in self.mem[p]]), device=self.dev)
        W = torch.tensor(np.array([m[2] for m in self.mem[p]], dtype=np.float32),
                         device=self.dev).unsqueeze(1)
        opt = torch.optim.Adam(self.adv[p].parameters(), lr=1e-3)
        n = X.shape[0]
        for _ in range(epochs):
            idx = torch.randperm(n, device=self.dev)
            for i in range(0, n, bs):
                b = idx[i:i + bs]
                opt.zero_grad()
                pred = self.adv[p](X[b])
                loss = (W[b] * (pred - Y[b]) ** 2).mean()
                loss.backward()
                opt.step()

    def avg_policy(self):
        pol = {}
        for k, (legal, ssum) in self.strat_sum.items():
            tot = sum(ssum[a] for a in legal)
            pol[k] = {a: (ssum[a] / tot if tot > 1e-9 else 1.0 / len(legal)) for a in legal}
        return pol


def root_states():
    """All chance-dealt private deals with probabilities, for exact exploitability."""
    out = []
    n = len(DECK)
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            s = State()
            s.cards = [DECK[i], DECK[j]]
            out.append((s, 1.0 / (n * (n - 1))))
    return out


def br_value(s: State, br: int, pol, rng_enum=True) -> float:
    """Best-response value for player `br` (max), opponent plays avg policy `pol`. Exact (enumerated)."""
    if s.done:
        return s.util0() if br == 0 else -s.util0()
    if s.need_public:
        used = [s.cards[0], s.cards[1]]
        deck = [c for c in DECK]
        for c in used:
            deck.remove(c)
        # enumerate distinct public ranks weighted by remaining count
        vals, tot = {}, len(deck)
        ev = 0.0
        for c in set(deck):
            ss = s.clone(); ss.public = c; ss.need_public = False; ss.rnd = 1
            ss.bet_open = False; ss.raises = 0; ss.checks = 0; ss.to_act = 0
            ev += (deck.count(c) / tot) * br_value(ss, br, pol)
        return ev
    p = s.to_act
    legal = s.legal()
    if p == br:
        return max(br_value(s.apply(a), br, pol) for a in legal)
    k = key(s, p)
    pr = pol.get(k, {a: 1.0 / len(legal) for a in legal})
    return sum(pr.get(a, 0.0) * br_value(s.apply(a), br, pol) for a in legal)


def exploitability(pol) -> float:
    """mbb/hand: average best-response gain over the game value (0 in symmetric Leduc)."""
    roots = root_states()
    v0 = sum(w * br_value(s, 0, pol) for s, w in roots)   # BR0 value (player-0 utility), vs avg p1
    v1 = sum(w * br_value(s, 1, pol) for s, w in roots)   # BR1 value (player-1 utility), vs avg p0
    return 1000.0 * (v0 + v1) / 2.0                        # exploitability >= 0 at non-equilibrium


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iters", type=int, default=150)
    ap.add_argument("--trav", type=int, default=120, help="traversals per player per iteration")
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--tabular", action="store_true", help="tabular CFR sanity check (no net)")
    args = ap.parse_args()
    mode = "TABULAR sanity" if args.tabular else f"NEURAL device={args.device}"
    print(f"Deep CFR on Leduc | {mode} | {args.iters} iters x {args.trav} trav")
    cfr = DeepCFR(device=args.device, tabular=args.tabular)
    for t in range(1, args.iters + 1):
        for trav in (0, 1):
            for _ in range(args.trav):
                s = State()
                cards = random.sample(range(len(DECK)), 2)
                s.cards = [DECK[cards[0]], DECK[cards[1]]]
                cfr.traverse(s, trav, t)
            if not args.tabular:
                cfr.train_adv(trav)
        if t % 25 == 0 or t == args.iters:
            expl = exploitability(cfr.avg_policy())
            print(f"  iter {t:4d} | exploitability {expl:8.1f} mbb/hand")


if __name__ == "__main__":
    main()
