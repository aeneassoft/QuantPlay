"""GATE 0 of the value-net plan (docs/plans/VALUE_NET_PLAN.md): DeepStack-style CFV value net + continual re-solving on
LEDUC, validated against EXACT exploitability. This proves the value-net+resolving MACHINERY is correct for ~$0
BEFORE any HUNL/GPU compute (the discipline that would have caught the fcpa −212).

Pieces (built + tested incrementally):
  0a round-1 CFV ORACLE   — exact per-hand counterfactual values at the start of round 1, given (public, ranges).
                            Reuses deep_cfr.vanilla_cfr per (h0,h1) combo with exact Leduc card-removal weights.
  0b value NET            — (public, range0, range1, pot) -> per-hand round-1 CFVs; train on 0a; PASS = net~oracle.
  0c round-0 RESOLVER     — belief-state CFR over round 0, value net at the round-1 depth limit.
  0d continual RE-SOLVE   — play by re-solving; deep_cfr.exploitability() must be ~0 = the GATE.

Leduc: ranks 0,1,2 = J,Q,K (two each). A private that PAIRS the public wins; else higher private; equal = tie.
Run:  python -m pokerbot.strategy.deepstack_leduc            # 0a oracle self-test (sane CFVs)
"""
from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn

from pokerbot.strategy.deep_cfr import State, _avg, key, vanilla_cfr

CONTRIBS = (1.0, 3.0, 5.0)        # reachable round-1 pot states (ante 1 + round-0 bets of 2, max 2 raises)


def _round1_root(h0: int, h1: int, public: int, contrib) -> State:
    s = State()
    s.cards = [h0, h1]
    s.public = public
    s.rnd = 1
    s.contrib = [contrib[0], contrib[1]]
    s.to_act = 0
    s.bet_open = False
    s.raises = 0
    s.checks = 0
    s.done = False
    s.need_public = False
    s.winner = -2
    s.hist = ""
    return s


def _cr(h0: int, h1: int, public: int):
    """Leduc card-removal multiplicities: 2 of each rank, the public uses one. Returns (cnt0, cnt1) ways."""
    cnt0 = 2 - (1 if h0 == public else 0)
    cnt1 = 2 - (1 if h1 == public else 0) - (1 if h1 == h0 else 0)
    return cnt0, cnt1


def _combos(public, r0, r1):
    """{(h0,h1): joint weight} with card-removal; weight = r0[h0]*r1[h1]*cnt0*cnt1 (unnormalized)."""
    out = {}
    for h0 in range(3):
        for h1 in range(3):
            cnt0, cnt1 = _cr(h0, h1, public)
            if cnt0 <= 0 or cnt1 <= 0:
                continue
            w = r0[h0] * r1[h1] * cnt0 * cnt1
            if w > 0:
                out[(h0, h1)] = w
    return out


def _eval_v(s: State, pol: dict) -> float:
    """Player-0 EV of the round-1 matchup under the fixed average policy pol (no chance in round 1)."""
    if s.done:
        return s.util0()
    p = s.to_act
    legal = s.legal()
    pr = pol.get(key(s, p), None)
    n = len(legal)
    if pr is None:
        pr = {a: 1.0 / n for a in legal}
    return sum(pr.get(a, 0.0) * _eval_v(s.apply(a), pol) for a in legal)


def solve_round1(public: int, r0, r1, contrib=(1.0, 1.0), iters: int = 400, return_v: bool = False):
    """0a — exact round-1 CFV oracle. r0,r1 = belief vectors over ranks {J,Q,K}. Returns (cfv0[3], cfv1[3]) =
    each hand's expected value vs the (card-removal-adjusted, normalized) opponent range under the round-1
    equilibrium. cfv0 is player-0-relative (+ = good for hero); cfv1 is player-1-relative."""
    r0 = np.asarray(r0, float)
    r1 = np.asarray(r1, float)
    combos = _combos(public, r0, r1)
    regret, strat_sum = {}, {}
    for t in range(1, iters + 1):
        for (h0, h1), w in combos.items():
            vanilla_cfr(_round1_root(h0, h1, public, contrib), t, 1.0, 1.0, w, regret, strat_sum)
    pol = _avg(strat_sum)
    v = {}                                                # V for ALL valid card-removal pairs (out-of-range too)
    for h0 in range(3):
        for h1 in range(3):
            cnt0, cnt1 = _cr(h0, h1, public)
            if cnt0 > 0 and cnt1 > 0:
                v[(h0, h1)] = _eval_v(_round1_root(h0, h1, public, contrib), pol)
    cfv0 = np.zeros(3)
    cfv1 = np.zeros(3)
    for h0 in range(3):                                   # CFV0(h0) = E over opp range (card-removal) of V(h0,h1)
        num = den = 0.0
        for h1 in range(3):
            cnt0, cnt1 = _cr(h0, h1, public)
            if cnt0 <= 0 or cnt1 <= 0:
                continue
            wt = r1[h1] * cnt1
            num += wt * v[(h0, h1)]
            den += wt
        cfv0[h0] = num / den if den > 1e-12 else 0.0
    for h1 in range(3):                                   # CFV1(h1) = E over opp range of (−V) = player-1 value
        num = den = 0.0
        for h0 in range(3):
            cnt0, cnt1 = _cr(h0, h1, public)
            if cnt0 <= 0 or cnt1 <= 0:
                continue
            wt = r0[h0] * cnt0
            num += wt * (-v[(h0, h1)])
            den += wt
        cfv1[h1] = num / den if den > 1e-12 else 0.0
    if return_v:
        return cfv0, cfv1, v                              # v[(h0,h1)] = player-0 round-1 value per matchup
    return cfv0, cfv1


# ----------------------------------------------------------------- 0b: the CFV value net
class CFVNet(nn.Module):
    """(public one-hot[3], range0[3], range1[3], contrib/5[1]) -> (cfv0[3], cfv1[3]) round-1 counterfactual values."""

    def __init__(self, h: int = 128):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(10, h), nn.ReLU(), nn.Linear(h, h), nn.ReLU(),
                                 nn.Linear(h, h), nn.ReLU(), nn.Linear(h, 6))

    def forward(self, x):
        return self.net(x)


def _feat(public, r0, r1, contrib):
    pub = [0.0, 0.0, 0.0]
    pub[public] = 1.0
    return np.array(pub + list(r0) + list(r1) + [contrib / 5.0], dtype=np.float32)


def gen_data(n: int, seed: int, iters: int = 250):
    rng = np.random.RandomState(seed)
    X, Y = [], []
    for _ in range(n):
        public = int(rng.randint(3))
        r0 = rng.dirichlet([0.8, 0.8, 0.8])               # full-support ranges (alpha<1 -> some near-polar)
        r1 = rng.dirichlet([0.8, 0.8, 0.8])
        contrib = float(rng.choice(CONTRIBS))
        cfv0, cfv1 = solve_round1(public, r0, r1, contrib=(contrib, contrib), iters=iters)
        X.append(_feat(public, r0, r1, contrib))
        Y.append(np.concatenate([cfv0, cfv1]).astype(np.float32))
    return np.array(X), np.array(Y, dtype=np.float32)


def train_net(ntrain=6000, nval=800, epochs=2500, lr=2e-3, verbose=True, save=None):
    """0b — train + validate the value net. PASS = val MAE small vs the CFV scale (the net learned the value fn)."""
    if verbose:
        print(f"  generating {ntrain}+{nval} oracle-labelled samples ...", flush=True)
    Xtr, Ytr = gen_data(ntrain, 1)
    Xv, Yv = gen_data(nval, 2)
    Xt, Yt = torch.tensor(Xtr), torch.tensor(Ytr)
    Xvt, Yvt = torch.tensor(Xv), torch.tensor(Yv)
    net = CFVNet()
    opt = torch.optim.Adam(net.parameters(), lr=lr, weight_decay=1e-5)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, epochs)
    bs = 512
    n = Xt.shape[0]
    for ep in range(epochs):
        perm = torch.randperm(n)
        for i in range(0, n, bs):
            idx = perm[i:i + bs]
            opt.zero_grad()
            loss = ((net(Xt[idx]) - Yt[idx]) ** 2).mean()
            loss.backward()
            opt.step()
        sched.step()
        if verbose and (ep + 1) % 250 == 0:
            with torch.no_grad():
                vmae = (net(Xvt) - Yvt).abs().mean().item()
            print(f"    ep{ep+1:4d} train_mse={loss.item():.4f} val_mae={vmae:.4f}", flush=True)
    with torch.no_grad():
        vmae = (net(Xvt) - Yvt).abs().mean().item()
        scale = Yvt.abs().mean().item()
    pct = 100 * vmae / scale
    print(f"  0b RESULT: val MAE {vmae:.3f} vs CFV scale {scale:.3f}  = {pct:.1f}% of scale  "
          f"-> {'PASS' if pct < 8 else 'FAIL'} (the net learned the round-1 value function)", flush=True)
    if save:
        torch.save(net.state_dict(), save)
        print(f"  saved -> {save}", flush=True)
    return net


# ----------------------------------------------------------------- 0c: belief-state round-0 resolver
from pokerbot.strategy.deep_cfr import State, exploitability, root_states, vanilla_cfr  # noqa: E402,F811
from pokerbot.strategy.deep_cfr import NACT, F, C, R  # noqa: E402

NACT = 3


def _rm_vec(rs, legal):
    pos = np.maximum(rs, 0.0)
    sl = pos[legal].sum()
    out = np.zeros(NACT)
    out[legal] = pos[legal] / sl if sl > 1e-12 else 1.0 / len(legal)
    return out


def boundary_oracle(r0, r1, contrib, iters=60):
    """Pre-public round-0->round-1 boundary: counterfactual round-1 value per hand (opponent reach x privates
    card-removal x public deal). EXACT (re-solves round 1 per public via the oracle's per-matchup V)."""
    cfv0 = np.zeros(3)
    cfv1 = np.zeros(3)
    Vc = {c: solve_round1(c, r0, r1, contrib=tuple(contrib), iters=iters, return_v=True)[2] for c in range(3)}
    for h0 in range(3):
        for h1 in range(3):
            opp = (2 - (h0 == h1))                              # privates card-removal coupling
            for c in range(3):
                pc = max(0, 2 - (c == h0) - (c == h1)) / 4.0    # P(public=c | h0,h1)
                if pc > 0 and (h0, h1) in Vc[c]:
                    cfv0[h0] += r1[h1] * opp * pc * Vc[c][(h0, h1)]
                    cfv1[h1] += r0[h0] * opp * pc * (-Vc[c][(h0, h1)])
    return cfv0, cfv1


def _net_value_fn(net):
    """Boundary value fn from the trained CFV net (fast forward pass; the DeepStack depth-limit estimator)."""
    def fn(r0, r1, contrib):
        cfv0 = np.zeros(3)
        cfv1 = np.zeros(3)
        for c in range(3):
            x = torch.tensor(_feat(c, r0, r1, contrib[0]), dtype=torch.float32)
            with torch.no_grad():
                out = net(x).numpy()
            n0, n1 = out[:3], out[3:]
            for h0 in range(3):
                for h1 in range(3):
                    opp = (2 - (h0 == h1))
                    pc = max(0, 2 - (c == h0) - (c == h1)) / 4.0
                    if pc > 0:
                        cfv0[h0] += r1[h1] * opp * pc * n0[h0] / max(1e-9, _den0(h0, r1))
                        cfv1[h1] += r0[h0] * opp * pc * n1[h1] / max(1e-9, _den1(h1, r0))
        return cfv0, cfv1
    return fn


def _den0(h0, r1):
    return sum(r1[h1] * (2 - (h0 == h1)) for h1 in range(3))


def _den1(h1, r0):
    return sum(r0[h0] * (2 - (h0 == h1)) for h0 in range(3))


def cfr0(s, r0, r1, value_fn, regret, strat_sum, t):
    """Belief-state CFR over round 0. r0,r1: reach-per-hand[3]. Returns (cfv0[3], cfv1[3]) counterfactual values."""
    if s.done:                                                  # fold (no round-0 showdown): card-independent util0
        u0 = s.util0()
        cfv0 = np.array([u0 * sum(r1[j] * (2 - (i == j)) for j in range(3)) for i in range(3)])
        cfv1 = np.array([-u0 * sum(r0[i] * (2 - (i == j)) for i in range(3)) for j in range(3)])
        return cfv0, cfv1
    if s.need_public:
        return value_fn(r0, r1, s.contrib)
    p = s.to_act
    legal = s.legal()
    sig = np.zeros((3, NACT))
    for h in range(3):
        k = f"{h}|-1|{s.hist}"
        sig[h] = _rm_vec(regret.setdefault(k, np.zeros(NACT)), legal)
    av0, av1 = {}, {}
    for a in legal:
        if p == 0:
            av0[a], av1[a] = cfr0(s.apply(a), r0 * sig[:, a], r1, value_fn, regret, strat_sum, t)
        else:
            av0[a], av1[a] = cfr0(s.apply(a), r0, r1 * sig[:, a], value_fn, regret, strat_sum, t)
    cfv0 = np.zeros(3)
    cfv1 = np.zeros(3)
    for h in range(3):
        cfv0[h] = (sum(sig[h][a] * av0[a][h] for a in legal) if p == 0 else sum(av0[a][h] for a in legal))
        cfv1[h] = (sum(sig[h][a] * av1[a][h] for a in legal) if p == 1 else sum(av1[a][h] for a in legal))
    for h in range(3):                                          # regret + avg-strategy update for the acting player
        k = f"{h}|-1|{s.hist}"
        rs = regret[k]
        node = cfv0[h] if p == 0 else cfv1[h]
        for a in legal:
            rs[a] += (av0[a][h] if p == 0 else av1[a][h]) - node
        np.maximum(rs, 0.0, out=rs)
        ss = strat_sum.setdefault(k, [legal, np.zeros(NACT)])
        own = r0[h] if p == 0 else r1[h]
        for a in legal:
            ss[1][a] += t * own * sig[h][a]
    return cfv0, cfv1


def resolve_round0(value_fn, iters=120):
    """Continual re-solve of round 0 with value_fn at the depth limit -> the round-0 strategy {key: {a: prob}}."""
    regret, strat_sum = {}, {}
    prior = np.array([1 / 3, 1 / 3, 1 / 3])
    for t in range(1, iters + 1):
        cfr0(State(), prior.copy(), prior.copy(), value_fn, regret, strat_sum, t)
    return _avg(strat_sum)


_POL_EXACT = None


def _exact_pol(iters=1500):
    global _POL_EXACT
    if _POL_EXACT is None:
        reg, ss = {}, {}
        for t in range(1, iters + 1):
            for s, w in root_states():
                vanilla_cfr(s.clone(), t, 1.0, 1.0, w, reg, ss)
        _POL_EXACT = _avg(ss)
    return _POL_EXACT


def gate0d(value_fn, label, r0iters=300):
    """0d — swap the resolver's round-0 strategy into the exact equilibrium (exact round-1) -> exploitability."""
    pol_exact = _exact_pol()
    pol_res = dict(pol_exact)
    for k, v in resolve_round0(value_fn, r0iters).items():
        pol_res[k] = v
    e_exact = exploitability(pol_exact)
    e_res = exploitability(pol_res)
    print(f"  {label:22s}: exact-eq {e_exact:6.1f}  |  resolver-round0 {e_res:6.1f} mbb/hand", flush=True)
    return e_res, e_exact


def _selftest():
    rng = np.random.RandomState(0)
    uni = np.array([1.0, 1.0, 1.0]) / 3
    print("=== 0a round-1 CFV oracle self-test (Leduc; ranks J,Q,K = 0,1,2) ===")
    for public in range(3):
        cfv0, cfv1 = solve_round1(public, uni, uni, contrib=(3.0, 3.0))
        pub = "JQK"[public]
        print(f"  public={pub}: CFV0(J,Q,K)={np.round(cfv0,3)}  CFV1(J,Q,K)={np.round(cfv1,3)}")
    print("  sanity: the hand that PAIRS the public should have the highest CFV; the unpaired ranking is by height.")
    # asymmetric range: hero (P0) range-capped to J -> should be exploitable (low CFV)
    capped = np.array([1.0, 0.0, 0.0])
    cfv0, cfv1 = solve_round1(2, capped, uni, contrib=(3.0, 3.0))
    print(f"  public=K, P0 range=only J: CFV0={np.round(cfv0,3)} (J only is bad OOP) CFV1={np.round(cfv1,3)}")


if __name__ == "__main__":
    import os
    import sys
    if "--train" in sys.argv:
        print("=== 0b: train + validate the Leduc CFV value net (net ~ oracle) ===")
        train_net(save="data/leduc_cfv_net.pt")
    elif "--resolve" in sys.argv:
        print("=== 0c/0d: belief-state round-0 resolver -> EXACT exploitability (mbb/hand; ~0 = near-Nash) ===")
        print("  (the exact equilibrium itself reads ~0; the resolver's round-0 strategy + exact round-1 is the test)")
        gate0d(boundary_oracle, "ORACLE boundary")     # validates the resolver LOGIC (exact value fn -> ~0)
        if os.path.exists("data/leduc_cfv_net.pt"):
            net = CFVNet()
            net.load_state_dict(torch.load("data/leduc_cfv_net.pt"))
            net.eval()
            gate0d(_net_value_fn(net), "NET boundary")  # the value-net resolver (the real DeepStack machinery)
    else:
        _selftest()
