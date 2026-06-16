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
from collections import deque

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
MEM_CAP = 400_000        # advantage-memory reservoir per player (Deep CFR spec: bounded, recency via t-weight)


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
    def __init__(self, device="cpu", seed=0, tabular=False, dcfrplus=False):
        self.dev = torch.device(device)
        self.dcfrplus = dcfrplus             # DCFR+ (discount+clip+bootstrap advantages); else old LinearCFR fit
        self.alpha = 2.0                     # DCFR+ regret-discount exponent (paper: alpha=2)
        self.gamma = 2.0 if dcfrplus else 1.0  # avg-strategy weight t**gamma (DCFR gamma=2 vs LinearCFR t^1)
        self.adv = [Net().to(self.dev), Net().to(self.dev)]
        # advantage memory per player: (feat, regrets, t). Bounded reservoir (deque) -> keeps the most recent
        # samples, which the t=linear weighting already favours, and keeps train_adv tractable as trav scales up.
        self.mem = [deque(maxlen=MEM_CAP), deque(maxlen=MEM_CAP)]
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
            rec[1] += (t ** self.gamma) * reach * strat   # reach-weighted avg strategy (DCFR gamma weighting)
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

    def train_adv(self, p: int, t: int, epochs=20, bs=1024):
        if not self.mem[p]:
            return
        X = torch.tensor(np.array([m[0] for m in self.mem[p]]), device=self.dev)
        Y = torch.tensor(np.array([m[1] for m in self.mem[p]]), device=self.dev)   # advantages
        if self.dcfrplus:
            # DCFR+ bootstrap (AAAI-26 VR-DeepDCFR+): R_t = max(R_{t-1},0)*disc(t) + advantage. Warm-start the
            # SAME net (it IS the running cumulative-advantage estimate); the buffer holds only this iter's samples.
            with torch.no_grad():
                prev = torch.clamp(self.adv[p](X), min=0.0)
            disc = ((t - 1) ** self.alpha) / ((t - 1) ** self.alpha + 1.0) if t > 1 else 0.0
            target = prev * disc + Y
            opt = torch.optim.Adam(self.adv[p].parameters(), lr=1e-3)
            n = X.shape[0]
            for _ in range(epochs):
                idx = torch.randperm(n, device=self.dev)
                for i in range(0, n, bs):
                    b = idx[i:i + bs]
                    opt.zero_grad()
                    loss = ((self.adv[p](X[b]) - target[b]) ** 2).mean()
                    loss.backward()
                    opt.step()
            return
        # ---- LinearCFR (original): reinit + fit ALL retained samples weighted by t ----
        self.adv[p] = Net().to(self.dev)
        W = torch.tensor(np.array([m[2] for m in self.mem[p]], dtype=np.float32),
                         device=self.dev).unsqueeze(1)
        opt = torch.optim.Adam(self.adv[p].parameters(), lr=1e-3)
        n = X.shape[0]
        for _ in range(epochs):
            idx = torch.randperm(n, device=self.dev)
            for i in range(0, n, bs):
                b = idx[i:i + bs]
                opt.zero_grad()
                loss = (W[b] * (self.adv[p](X[b]) - Y[b]) ** 2).mean()
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


def _br_value(pol: dict, br: int, sweeps: int = 14) -> float:
    """EXACT, INFOSET-CORRECT best-response utility for player `br` vs `pol`. (The old br_value did
    `if p==br: max(...)` per fully-known-cards state = a CLAIRVOYANT BR that sees the opponent's card ->
    it massively overstated exploitability and stayed ~constant, so NO CFR mode looked like it converged.)
    Here: policy iteration — evaluate under the current BR policy, then set each br INFOSET's action to the
    one maximizing its opponent-counterfactual-reach-weighted value; repeat to a fixed point. Leduc is tiny."""
    brp: dict = {}
    sign = 1.0 if br == 0 else -1.0
    acc: dict = {}

    def rec(s: State, cfr: float) -> float:           # player-0 EV under (opp=pol, br=brp); fills `acc`
        if s.done:
            return s.util0()
        if s.need_public:                             # chance: average over public, fold pc into opp reach
            used = [s.cards[0], s.cards[1]]
            deck = [c for c in DECK]
            for c in used:
                deck.remove(c)
            tot, ev = len(deck), 0.0
            for c in set(deck):
                pc = deck.count(c) / tot
                ev += pc * rec(_with_public(s, c), cfr * pc)
            return ev
        p = s.to_act
        legal = s.legal()
        k = key(s, p)
        if p == br:                                   # aggregate action values ACROSS the infoset (not per state)
            qs = {a: rec(s.apply(a), cfr) for a in legal}
            iset = acc.setdefault(k, {a: 0.0 for a in legal})
            for a in legal:
                iset[a] += cfr * qs[a]
            return qs[brp.get(k, legal[0])]
        pr = pol.get(k, {a: 1.0 / len(legal) for a in legal})   # opponent plays the fixed avg policy
        return sum(pr.get(a, 0.0) * rec(s.apply(a), cfr * pr.get(a, 0.0)) for a in legal)

    for _ in range(sweeps):
        acc = {}
        for s, w in root_states():
            rec(s, w)                                 # fills acc (opp+chance+deal-reach-weighted q per infoset)
        for k, av in acc.items():
            brp[k] = max(av, key=lambda a: sign * av[a])
    acc = {}
    val = sum(w * rec(s, w) for s, w in root_states())   # final value under the converged BR policy
    return sign * val


def exploitability(pol) -> float:
    """mbb/hand: total best-response gain over the game value (0 in symmetric Leduc). Infoset-correct BR."""
    return 1000.0 * (_br_value(pol, 0) + _br_value(pol, 1)) / 2.0


def _with_public(s: State, c: int) -> State:
    ss = s.clone()
    ss.public = c; ss.need_public = False; ss.rnd = 1
    ss.bet_open = False; ss.raises = 0; ss.checks = 0; ss.to_act = 0
    return ss


def vanilla_cfr(s: State, t: int, r0: float, r1: float, rc: float, regret: dict, strat_sum: dict) -> float:
    """Exact full-tree CFR (NO sampling) -> the rigorous self-play->Nash proof; Leduc is small enough to walk
    the whole tree. Returns player-0 EV. rc = chance reach (private deal x public card). Regret is weighted by
    (opponent reach x chance reach) = pi_{-i}; the average strategy by own reach pi_i (Zinkevich et al. 2007).
    The committed `traverse` MCCFR plateaued ~1500 mbb -> this is the correct, deterministic check instead."""
    if s.done:
        return s.util0()
    if s.need_public:                                    # chance node: average over public cards
        used = [s.cards[0], s.cards[1]]
        deck = [c for c in DECK]
        for c in used:
            deck.remove(c)
        tot, ev = len(deck), 0.0
        for c in set(deck):
            pc = deck.count(c) / tot
            ev += pc * vanilla_cfr(_with_public(s, c), t, r0, r1, rc * pc, regret, strat_sum)
        return ev
    p = s.to_act
    legal = s.legal()
    k = key(s, p)
    rs = regret.setdefault(k, np.zeros(NACT))
    strat = regret_match(rs, legal)
    own = r0 if p == 0 else r1
    ssum = strat_sum.setdefault(k, [legal, np.zeros(NACT)])
    for a in legal:
        ssum[1][a] += t * own * strat[a]                 # avg strategy weighted by OWN reach (x t = linear CFR)
    util = np.zeros(NACT)
    node = 0.0
    for a in legal:
        if p == 0:
            u = vanilla_cfr(s.apply(a), t, r0 * strat[a], r1, rc, regret, strat_sum)
        else:
            u = vanilla_cfr(s.apply(a), t, r0, r1 * strat[a], rc, regret, strat_sum)
        util[a] = u
        node += strat[a] * u
    opp = (r1 if p == 0 else r0) * rc                    # pi_{-i} = opponent reach x chance reach
    sign = 1.0 if p == 0 else -1.0                       # util[] is player-0 EV -> flip for player 1
    for a in legal:
        rs[a] += opp * sign * (util[a] - node)
    np.maximum(rs, 0.0, out=rs)                          # CFR+: clamp cumulative regret >=0 (faster, monotone)
    return node


def _avg(strat_sum: dict) -> dict:
    pol = {}
    for k, (legal, ssum) in strat_sum.items():
        tot = sum(ssum[a] for a in legal)
        pol[k] = {a: (ssum[a] / tot if tot > 1e-9 else 1.0 / len(legal)) for a in legal}
    return pol


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iters", type=int, default=150)
    ap.add_argument("--trav", type=int, default=120, help="traversals per player per iteration")
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--tabular", action="store_true", help="tabular CFR sanity check (no net)")
    ap.add_argument("--dcfrplus", action="store_true", help="DCFR+ (discount+clip+bootstrap advantages; AAAI-26)")
    ap.add_argument("--vanilla", action="store_true", help="exact full-tree CFR (clean convergence proof)")
    args = ap.parse_args()
    if args.vanilla:
        print(f"Vanilla full-tree CFR on Leduc | {args.iters} iters (exact, no sampling)")
        regret, strat_sum = {}, {}
        for t in range(1, args.iters + 1):
            for s, w in root_states():
                vanilla_cfr(s, t, 1.0, 1.0, w, regret, strat_sum)
            if t % 250 == 0 or t == args.iters:
                print(f"  iter {t:5d} | exploitability {exploitability(_avg(strat_sum)):8.2f} mbb/hand")
        return
    mode = "TABULAR sanity" if args.tabular else f"NEURAL {'DCFR+' if args.dcfrplus else 'Linear'} device={args.device}"
    print(f"Deep CFR on Leduc | {mode} | {args.iters} iters x {args.trav} trav")
    cfr = DeepCFR(device=args.device, tabular=args.tabular, dcfrplus=args.dcfrplus)
    for t in range(1, args.iters + 1):
        for trav in (0, 1):
            if cfr.dcfrplus:
                cfr.mem[trav].clear()        # DCFR+: buffer holds only the current iteration's advantages
            for _ in range(args.trav):
                s = State()
                cards = random.sample(range(len(DECK)), 2)
                s.cards = [DECK[cards[0]], DECK[cards[1]]]
                cfr.traverse(s, trav, t)
            if not args.tabular:
                cfr.train_adv(trav, t)
        if t % 25 == 0 or t == args.iters:
            expl = exploitability(cfr.avg_policy())
            print(f"  iter {t:4d} | exploitability {expl:8.1f} mbb/hand")


if __name__ == "__main__":
    main()
