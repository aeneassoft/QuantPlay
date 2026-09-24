"""Gate 0 — Leduc CFV value net + depth-limited continual re-solving (docs/plans/VALUE_NET_PLAN.md).

The DeepStack machinery proven on Leduc, where `exploitability()` is EXACT (mbb/hand vs a true
best response). Phases, each persisted to data/research_sweep/gate0_leduc.json as it completes:

  1. LABELS  — solve round-1 subgames exactly with `vanilla_cfr` over sampled situations
               (public card, pot size, both players' Dirichlet belief vectors over the 3 ranks)
               and record per-rank counterfactual values for both players.
  2. NET     — tiny MLP: (public one-hot, pot, r0, r1) -> pot-normalized per-rank CFVs for both
               players, with the DeepStack zero-sum output correction baked into forward().
               Huber loss, train/holdout split, holdout MAE in pot fractions.
  3. RESOLVE — vector-form trunk CFR on round 0 that never descends into round 1: at the round
               boundary it maps the current reach vectors to beliefs and queries the net for leaf
               CFVs. SAFETY (iteration 3): the whole construction runs through DeepStack's CFR-D
               re-solving GADGET (supplementary p.24/p.28-29). (a) TWO trunks, one per re-solving
               player; in each, the OPPONENT's boundary leaf value is max(follow-CFV, constraint)
               — the T/F gadget choice — with the constraint = the t-weighted running average of
               that opponent's own leaf evaluations there (the trunk solve's own evaluations, in
               per-rank normalized units). (b) Round-1 infosets are filled by GADGET re-solves:
               per boundary x public x player, the opponent is dealt each rank and regret-matches
               terminate-for-constraint vs follow-into-the-subgame against hero's fixed range —
               no opponent range enters (the unsafe range-re-solve fill was iteration 2's ~38 mbb
               composition cost, plus the spurious-equilibrium trunk cost the gadget removes).
  4. GATE    — exact exploitability: full vanilla_cfr solve (baseline) vs the net-resolved policy.
               PASS bar (pre-registered, NOT tuned after seeing numbers): resolved exploitability
               within GATE_PASS_DELTA_MBB of the full solve. Units: milli-antes/hand (ante = 1,
               initial pot = 2 antes -> pot fraction = mbb / 2000).

CFV convention (must match between labels and the trunk leaf, or the resolve is silently wrong):
  CFV0[a] = sum_b r1[b] * mult(a,b|pub) * u0*(a,b) / Z,   Z = sum_{a,b} r0[a] r1[b] mult(a,b|pub)
so r0 . CFV0 = E_joint[u0] and the zero-sum identity is simply r0 . CFV0 + r1 . CFV1 = 0.
`mult` is the card-removal deal count (2 copies per rank, one copy of the public card gone).

Run:  python -m pokerbot.valuenet.gate0_leduc            # full gate (< 30 min CPU, labels parallel)
      python -m pokerbot.valuenet.gate0_leduc --quick    # smoke run (~1 min, tiny everything)
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

from pokerbot.strategy.deep_cfr import (
    NACT,
    State,
    _avg,
    exploitability,
    key,
    regret_match,
    root_states,
    vanilla_cfr,
)

SEED = 7
RANKS = 3
POT_HALVES = (1, 3, 5)        # the only per-player contribs a finished Leduc round 0 can end on
BELIEF_FLOOR = 0.01           # NET queries/training only: zero-reach ranks still drive trunk regrets
                              # -> the net needs labels there, so its input domain is floored
FILL_BELIEF_FLOOR = 1e-6      # EXACT fill re-solves must NOT inherit the net floor: 0.01 injects ~2%
                              # phantom opponent mass into every subgame (a measured composition cost)
N_SITUATIONS = 4500           # "a few thousand" solved subgames (VALUE_NET_SPECS: label scale matters)
LABEL_CFR_ITERS = 1000        # Supremus lesson: converged labels beat everything (DeepStack used 1000 CFR+)
LABEL_WORKERS = 12            # label solves are independent -> process pool (24 logical cores on this box)
STABILITY_PROBE_N = 5         # label-convergence check: CFV diff between 500- and 1000-iter solves
HOLDOUT_FRAC = 0.1
NET_HIDDEN = 128
NET_EPOCHS = 300
NET_BATCH = 256
NET_LR = 1e-3
HUBER_BETA = 0.5              # targets are O(1) pot units; a sub-pot beta keeps the loss quadratic near 0
BASELINE_ITERS = 8000         # this repo's vanilla_cfr is SIMULTANEOUS CFR+ -> ~T^-0.5; measured:
                              # 2000 it = 19.2, 4000 it = 13.9, 8000 it = 10.0 mbb (its practical floor)
TRUNK_ITERS = 4000
FILL_CFR_ITERS = 3000         # exact re-solve per reachable (boundary hist, public) subgame; the subgame
                              # trees are tiny, so converged fills are cheap composition insurance
ORACLE_TRUNK_ITERS = 800      # diagnostic mode: exact subgame solves instead of the net at the leaf
ORACLE_LEAF_ITERS = 200
ORACLE_QUANT = 0.02           # belief quantization for the oracle-leaf cache
GATE_PASS_DELTA_MBB = 10.0    # pre-registered: "a few mbb/hand" above the full solve; never tuned post-hoc
BOOTSTRAP_QUERY_FRAC = 0.5    # iteration 4 (ReBeL warning, VALUE_NET_SPECS §B): half the labels are drawn
                              # from the TRUNK-INDUCED query beliefs, not pure Dirichlet -> the net is
                              # trained where the depth-limited re-solve actually evaluates it
BOOTSTRAP_JITTER = 0.03       # Dirichlet concentration around each harvested belief: the trunk visits a
                              # FINITE set of beliefs, so we smear them slightly for input-domain coverage
RESULTS_PATH = Path("data/research_sweep/gate0_leduc.json")
LABELS_CACHE = Path("data/research_sweep/gate0_leduc_labels.npz")          # hand-off between run stages
LABELS_BOOT_CACHE = Path("data/research_sweep/gate0_leduc_labels_boot.npz")  # iter-4 query-belief labels

# P(deal a to P0, b to P1) over the 6-card deck (2 copies per rank): (2 - [a==b]) / 15.
M2 = np.array([[(2 - (a == b)) / 15.0 for b in range(RANKS)] for a in range(RANKS)])
# mult(a,b|pub): ways to deal (a,b) from the deck minus one copy of pub. M3[a,b,pub] = mult/60.
MULT = np.array([[[(2 - (a == pub)) * (2 - (b == pub) - (a == b)) for b in range(RANKS)]
                  for a in range(RANKS)] for pub in range(RANKS)], dtype=np.float64)


# ---------------- subgame solving (labels + round-1 fill-in) ----------------
def _subgame_root(a: int, b: int, pub: int, pot_half: int, hist: str = "") -> State:
    """A round-1 State: public dealt, both players at `pot_half` chips, betting fresh."""
    s = State()
    s.cards = [a, b]
    s.public = pub
    s.rnd = 1
    s.contrib = [pot_half, pot_half]
    s.hist = hist                 # full-game hist prefix so keys match key(s, p) of the whole game
    return s


def solve_subgame(pub: int, pot_half: int, r0, r1, iters: int, hist: str = ""):
    """Exact CFR on one round-1 subgame, root deals weighted by r0[a]*r1[b]*mult (card removal).

    Returns (avg policy, Z) where Z is the raw belief-mass normalizer of the CFV convention."""
    raw = (np.outer(r0, r1) * MULT[pub])
    z = raw.sum()
    joint = raw / z
    roots = [(_subgame_root(a, b, pub, pot_half, hist), joint[a, b])
             for a in range(RANKS) for b in range(RANKS) if joint[a, b] > 0.0]
    regret: dict = {}
    ssum: dict = {}
    for t in range(1, iters + 1):
        for s, w in roots:
            vanilla_cfr(s, t, 1.0, 1.0, w, regret, ssum)
    return _avg(ssum), z


def _policy_ev0(s: State, pol: dict) -> float:
    """Player-0 EV of a (chance-free) subgame state under an average policy."""
    if s.done:
        return s.util0()
    legal = s.legal()
    pr = pol.get(key(s, s.to_act), {a: 1.0 / len(legal) for a in legal})
    return sum(pr.get(a, 0.0) * _policy_ev0(s.apply(a), pol) for a in legal)


def subgame_cfvs(pub: int, pot_half: int, r0, r1, iters: int):
    """Solve one subgame exactly and return pot-normalized per-rank CFVs for both players."""
    pol, z = solve_subgame(pub, pot_half, r0, r1, iters)
    pot = 2.0 * pot_half
    u0 = np.zeros((RANKS, RANKS))
    for a in range(RANKS):
        for b in range(RANKS):
            if MULT[pub][a, b] > 0.0:
                u0[a, b] = _policy_ev0(_subgame_root(a, b, pub, pot_half), pol)
    cfv0 = (MULT[pub] * u0) @ r1 / z            # cfv0[a] = sum_b r1[b] mult u0 / Z
    cfv1 = -(MULT[pub] * u0).T @ r0 / z         # u1 = -u0 (zero-sum)
    return cfv0 / pot, cfv1 / pot


# ---------------- phase 1: labels ----------------
def _sample_belief(rng: np.random.Generator) -> np.ndarray:
    """Uniform / mild / skewed / near-pure mixture, floored so every rank keeps some mass."""
    kind = int(rng.integers(0, 4))
    if kind == 0:
        v = np.full(RANKS, 1.0 / RANKS)
    elif kind == 1:
        v = rng.dirichlet([5.0] * RANKS)        # mild skew around uniform
    elif kind == 2:
        v = rng.dirichlet([0.7] * RANKS)        # clearly skewed
    else:
        v = rng.dirichlet([0.15] * RANKS)       # near-pure (one rank dominates)
    v = np.maximum(v, BELIEF_FLOOR)
    return v / v.sum()


def _features(pub: int, pot_half: float, r0, r1) -> np.ndarray:
    x = np.zeros(10, dtype=np.float32)
    x[pub] = 1.0
    x[3] = pot_half / float(max(POT_HALVES))
    x[4:7] = r0
    x[7:10] = r1
    return x


def _situation(idx: int):
    """Deterministic situation for index idx: (public, pot) cycles the 9 cells, beliefs per-index RNG.

    Seeding by (SEED, idx) makes labels reproducible regardless of worker scheduling."""
    cells = [(pub, ph) for pub in range(RANKS) for ph in POT_HALVES]
    rng = np.random.default_rng([SEED, idx])
    pub, ph = cells[idx % len(cells)]
    return pub, ph, _sample_belief(rng), _sample_belief(rng)


def _label_one(args):
    """Worker: solve one subgame exactly and return (features, targets, zero-sum error)."""
    idx, label_iters = args
    pub, ph, r0, r1 = _situation(idx)
    cfv0, cfv1 = subgame_cfvs(pub, ph, r0, r1, label_iters)
    zs_err = abs(float(r0 @ cfv0 + r1 @ cfv1))
    return (_features(pub, ph, r0, r1),
            np.concatenate([cfv0, cfv1]).astype(np.float32), zs_err)


def generate_labels(n_situations: int, label_iters: int, workers: int):
    """Solve n independent subgames in a process pool; order (and thus the dataset) is deterministic."""
    from concurrent.futures import ProcessPoolExecutor

    xs, ys = [], []
    max_zero_sum_err = 0.0
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        jobs = ((i, label_iters) for i in range(n_situations))
        for i, (x, y, zs_err) in enumerate(pool.map(_label_one, jobs, chunksize=32)):
            xs.append(x)
            ys.append(y)
            max_zero_sum_err = max(max_zero_sum_err, zs_err)
            if (i + 1) % 900 == 0:
                rate = (i + 1) / (time.time() - t0)
                print(f"  labels {i + 1}/{n_situations} ({rate:.1f}/s)")
    return np.stack(xs), np.stack(ys), max_zero_sum_err


def label_stability_probe(n_probe: int, iters_lo: int = 500, iters_hi: int = 1000) -> dict:
    """Label-convergence check: max-abs CFV difference between a 500- and a 1000-iter exact solve.

    The residual difference is dominated by equilibrium-selection ambiguity on near-zero-belief
    ranks (their CFVs are not unique across subgame equilibria), not by iteration count."""
    diffs = []
    for i in range(n_probe):
        pub, ph, r0, r1 = _situation(10_000_000 + i)      # offset: fresh situations, never trained on
        lo0, lo1 = subgame_cfvs(pub, ph, r0, r1, iters_lo)
        hi0, hi1 = subgame_cfvs(pub, ph, r0, r1, iters_hi)
        diffs.append(float(max(np.abs(lo0 - hi0).max(), np.abs(lo1 - hi1).max())))
    return {"n": n_probe, "iters": [iters_lo, iters_hi],
            "max_abs_cfv_diff_pot": max(diffs), "mean_abs_cfv_diff_pot": float(np.mean(diffs))}


# ---------------- phase 2: net ----------------
class CFVNet(nn.Module):
    """(public one-hot, pot, r0, r1) -> 6 pot-normalized CFVs (3 per player).

    forward() applies the DeepStack zero-sum correction: the belief-weighted error
    err = r0.f0 + r1.f1 is split in half and subtracted from every component of each side
    (beliefs sum to 1, so r0.(f0 - err/2) + r1.(f1 - err/2) == 0 exactly). Differentiable,
    so training already optimizes the corrected output."""

    def __init__(self, h: int = NET_HIDDEN):
        super().__init__()
        self.f = nn.Sequential(nn.Linear(10, h), nn.ReLU(), nn.Linear(h, h), nn.ReLU(),
                               nn.Linear(h, 2 * RANKS))

    def forward(self, x):
        out = self.f(x)
        r0, r1 = x[:, 4:7], x[:, 7:10]
        f0, f1 = out[:, :RANKS], out[:, RANKS:]
        err = (r0 * f0).sum(1, keepdim=True) + (r1 * f1).sum(1, keepdim=True)
        return torch.cat([f0 - err / 2.0, f1 - err / 2.0], dim=1)


def train_net(x: np.ndarray, y: np.ndarray):
    net = CFVNet()
    n = x.shape[0]
    perm = torch.randperm(n)                    # torch RNG -> covered by torch.manual_seed
    n_hold = max(1, int(n * HOLDOUT_FRAC))
    hold, tr = perm[:n_hold], perm[n_hold:]
    xt, yt = torch.from_numpy(x)[tr], torch.from_numpy(y)[tr]
    xh, yh = torch.from_numpy(x)[hold], torch.from_numpy(y)[hold]
    opt = torch.optim.Adam(net.parameters(), lr=NET_LR)
    loss_fn = nn.SmoothL1Loss(beta=HUBER_BETA)
    for _ in range(NET_EPOCHS):
        idx = torch.randperm(xt.shape[0])
        for i in range(0, xt.shape[0], NET_BATCH):
            b = idx[i:i + NET_BATCH]
            opt.zero_grad()
            loss = loss_fn(net(xt[b]), yt[b])
            loss.backward()
            opt.step()
    net.eval()
    with torch.no_grad():
        mae_train = float((net(xt) - yt).abs().mean())
        mae_hold = float((net(xh) - yh).abs().mean())
    return net, mae_train, mae_hold


# ---------------- phase 3: depth-limited trunk resolve ----------------
def _floor_norm(reach: np.ndarray, floor: float = BELIEF_FLOOR) -> np.ndarray:
    """Reach vector -> belief vector. NET consumers keep the training floor (the net never saw exact
    0); EXACT fill re-solves pass FILL_BELIEF_FLOOR so no phantom opponent mass distorts them."""
    total = reach.sum()
    if total <= 0.0:
        return np.full(RANKS, 1.0 / RANKS)
    r = np.maximum(reach / total, floor)
    return r / r.sum()


def _net_leaf_fn(net: CFVNet):
    """leaf(pot_half, r0, r1) -> (cfv0, cfv1) arrays of shape (RANKS pubs, RANKS), pot units."""
    def leaf(pot_half, r0, r1):
        x = np.stack([_features(pub, pot_half, r0, r1) for pub in range(RANKS)])
        with torch.no_grad():
            out = net(torch.from_numpy(x)).numpy()
        return out[:, :RANKS], out[:, RANKS:]
    return leaf


def _oracle_leaf_fn(leaf_iters: int):
    """Diagnostic leaf: exact subgame solves instead of the net, cached on quantized beliefs.

    Separates net-approximation error from the depth-limit abstraction error (the gate-0c
    spurious-equilibrium question) — if oracle-trunk fails too, the net is not the problem."""
    cache: dict = {}

    def leaf(pot_half, r0, r1):
        q0 = np.maximum(np.round(r0 / ORACLE_QUANT) * ORACLE_QUANT, BELIEF_FLOOR)
        q1 = np.maximum(np.round(r1 / ORACLE_QUANT) * ORACLE_QUANT, BELIEF_FLOOR)
        q0, q1 = q0 / q0.sum(), q1 / q1.sum()
        k = (pot_half, tuple(np.round(q0, 4)), tuple(np.round(q1, 4)))
        if k not in cache:
            c0 = np.zeros((RANKS, RANKS))
            c1 = np.zeros((RANKS, RANKS))
            for pub in range(RANKS):
                c0[pub], c1[pub] = subgame_cfvs(pub, pot_half, q0, q1, leaf_iters)
            cache[k] = (c0, c1)
        return cache[k]
    return leaf


class TrunkResolver:
    """Vector-form linear CFR+ on Leduc round 0 only; the round boundary is a value-net leaf.

    Reach vectors s0/s1 carry per-rank STRATEGY reach (the uniform deal prior and card removal
    live in M2/MULT), exactly the quantities a real re-solver would map to belief vectors.

    `hero` selects the re-solving player (DeepStack: each player runs their own re-solver): the
    OPPONENT's boundary values then pass through the CFR-D gadget choice max(follow-CFV,
    terminate-for-constraint), so hero's trunk strategy is solved against an opponent who can
    always bank their bound — the safety that kills the spurious-equilibrium channel. hero=None
    keeps the iteration-2 unconstrained trunk (both players take raw leaf values)."""

    def __init__(self, leaf_fn, hero: int | None = None):
        self.leaf_fn = leaf_fn
        self.hero = hero
        self.regret: dict = {}    # (player, hist) -> (RANKS, NACT) cumulative regrets
        self.ssum: dict = {}      # (player, hist) -> [legal, (RANKS, NACT) weighted strat sum]
        self._constraint: dict = {}   # (hist, pub) -> [t-weighted sum of opp per-rank CFVs, weight]

    def opponent_constraints(self) -> dict:
        """(hist, pub) -> the opponent's constraint CFVs (per-rank normalized chips) — the
        continual-re-solving state this trunk carries forward into the round-1 gadget fills."""
        return {k: wsum / wt for k, (wsum, wt) in self._constraint.items()}

    def run(self, iters: int):
        for t in range(1, iters + 1):
            self._walk(State(), np.ones(RANKS), np.ones(RANKS), t)

    def _walk(self, s: State, s0: np.ndarray, s1: np.ndarray, t: int):
        """Returns per-rank counterfactual value vectors (v0, v1), opponent+chance reach included."""
        if s.done:                                   # a fold: utility is rank-independent
            u0 = s.util0()
            return u0 * (M2 @ s1), -u0 * (M2 @ s0)
        if s.need_public:
            return self._boundary(s, s0, s1, t)
        p = s.to_act
        legal = s.legal()
        k = (p, s.hist)
        reg = self.regret.setdefault(k, np.zeros((RANKS, NACT)))
        strat = np.stack([regret_match(reg[a], legal) for a in range(RANKS)])
        rec = self.ssum.setdefault(k, [legal, np.zeros((RANKS, NACT))])
        own = s0 if p == 0 else s1
        rec[1] += t * own[:, None] * strat           # linear-CFR averaging, own-reach weighted
        v0 = np.zeros(RANKS)
        v1 = np.zeros(RANKS)
        child: dict = {}
        for a in legal:
            if p == 0:
                c0, c1 = self._walk(s.apply(a), s0 * strat[:, a], s1, t)
                v0 += strat[:, a] * c0
                v1 += c1
            else:
                c0, c1 = self._walk(s.apply(a), s0, s1 * strat[:, a], t)
                v0 += c0
                v1 += strat[:, a] * c1
            child[a] = (c0, c1)
        mine = v0 if p == 0 else v1
        for a in legal:
            reg[:, a] += child[a][p] - mine          # child[a][p]: c0 for P0 nodes, c1 for P1 nodes
        np.maximum(reg, 0.0, out=reg)                # CFR+ clamp, same as vanilla_cfr
        return v0, v1

    def _boundary(self, s: State, s0: np.ndarray, s1: np.ndarray, t: int):
        """Round-0 betting done -> map reaches to beliefs, query the leaf for all 3 public cards.

        De-normalization: cfv0[a] = sum_b r1[b] mult u0* / Z (pot units), so the true
        counterfactual leaf value is sum_b M3 * s1[b] * u0* = (S1 * Z / 60) * cfv0[a] * pot.
        With a hero set, the opponent's side is gadget-clipped in per-rank NORMALIZED units
        (chips given the rank, hero playing their belief) so the T/F comparison is independent
        of the trunk's reach magnitudes, then de-normalized back into the value stream."""
        pot_half = float(s.contrib[0])
        pot = 2.0 * pot_half
        sum0, sum1 = s0.sum(), s1.sum()
        r0, r1 = _floor_norm(s0), _floor_norm(s1)
        cfv0_all, cfv1_all = self.leaf_fn(pot_half, r0, r1)
        v0 = np.zeros(RANKS)
        v1 = np.zeros(RANKS)
        for pub in range(RANKS):
            z = float(r0 @ MULT[pub] @ r1)
            f0 = (sum1 * z / 60.0) * cfv0_all[pub] * pot
            f1 = (sum0 * z / 60.0) * cfv1_all[pub] * pot
            if self.hero == 0:      # opponent = P1; d1[b] = sum_a r0[a] mult(a,b|pub)
                f1 = (sum0 / 60.0) * self._gadget_clip(
                    s.hist, pub, z * pot * cfv1_all[pub], r0 @ MULT[pub], t)
            elif self.hero == 1:    # opponent = P0; d0[a] = sum_b r1[b] mult(a,b|pub)
                f0 = (sum1 / 60.0) * self._gadget_clip(
                    s.hist, pub, z * pot * cfv0_all[pub], MULT[pub] @ r1, t)
            v0 += f0
            v1 += f1
        return v0, v1

    def _gadget_clip(self, hist: str, pub: int, raw_cfv: np.ndarray, d: np.ndarray, t: int):
        """CFR-D gadget at the boundary: the opponent may TERMINATE for their constraint CFV
        (t-weighted running average of their own leaf evaluations here, matching the trunk's
        linear averaging) instead of following into the subgame -> per-rank max(follow, w).

        Returns d * max(n, w) where n = raw_cfv / d is the normalized follow value; the caller
        multiplies by hero_reach_sum / 60 to restore the counterfactual value stream."""
        n = np.where(d > 0.0, raw_cfv / np.maximum(d, 1e-12), 0.0)
        rec = self._constraint.setdefault((hist, pub), [np.zeros(RANKS), 0.0])
        clipped = n if rec[1] <= 0.0 else np.maximum(n, rec[0] / rec[1])
        rec[0] += t * n              # constraint tracks the RAW follow values (no ratchet)
        rec[1] += t
        return d * clipped

    def policy(self) -> dict:
        """Average round-0 policy in full-game key format ('{rank}|-1|{hist}')."""
        pol = {}
        for (_, hist), (legal, w) in self.ssum.items():
            for rank in range(RANKS):
                tot = sum(w[rank][a] for a in legal)
                pol[f"{rank}|-1|{hist}"] = {
                    a: (w[rank][a] / tot if tot > 1e-12 else 1.0 / len(legal)) for a in legal}
        return pol


def _boundaries(pol0: dict):
    """All round-boundary histories with the per-rank strategy reach the trunk policy induces."""
    out = []

    def rec(s: State, s0: np.ndarray, s1: np.ndarray):
        if s.done:
            return
        if s.need_public:
            out.append((s.hist, int(s.contrib[0]), s0.copy(), s1.copy()))
            return
        p = s.to_act
        for a in s.legal():
            probs = np.array([pol0[f"{r}|-1|{s.hist}"].get(a, 0.0) for r in range(RANKS)])
            rec(s.apply(a), s0 * probs if p == 0 else s0, s1 * probs if p == 1 else s1)

    rec(State(), np.ones(RANKS), np.ones(RANKS))
    return out


def harvest_query_beliefs(trunk_pols: list) -> list:
    """The (pot_half, r0, r1) beliefs the gadget trunk ACTUALLY queries the net at.

    `_boundary` maps each boundary's reach vectors through `_floor_norm` (the NET floor) before
    the leaf call, so replaying `_boundaries` under each trunk's average policy reconstructs the
    exact query distribution — this is the REAL PBS distribution the ReBeL warning is about."""
    seen, queries = set(), []
    for pol0 in trunk_pols:
        for hist, pot_half, s0, s1 in _boundaries(pol0):
            r0, r1 = _floor_norm(s0), _floor_norm(s1)     # same floor `_boundary` uses at query time
            k = (pot_half, tuple(np.round(r0, 4)), tuple(np.round(r1, 4)))
            if k not in seen:                             # dedupe: the finite query set, not a histogram
                seen.add(k)
                queries.append((pot_half, r0, r1))
    return queries


def _boot_situation(idx: int, queries: list):
    """Iteration-4 situation: BOOTSTRAP_QUERY_FRAC drawn near a harvested query belief (Dirichlet
    jitter for domain coverage), the rest pure Dirichlet as before. Same (SEED, idx) reproducibility.

    The public card of a query belief is unconstrained (the trunk's leaf call fans over all 3 pubs),
    so we still cycle the (pub, pot) cells; only the BELIEF vectors come from the query set."""
    rng = np.random.default_rng([SEED, 4, idx])           # tag 4: fresh stream, disjoint from labels
    cells = [(pub, ph) for pub in range(RANKS) for ph in POT_HALVES]
    pub, ph = cells[idx % len(cells)]
    if queries and rng.random() < BOOTSTRAP_QUERY_FRAC:
        _, qr0, qr1 = queries[int(rng.integers(0, len(queries)))]
        r0 = rng.dirichlet(np.maximum(qr0, 1e-3) / BOOTSTRAP_JITTER)   # concentrate around the query belief
        r1 = rng.dirichlet(np.maximum(qr1, 1e-3) / BOOTSTRAP_JITTER)
        r0 = np.maximum(r0, BELIEF_FLOOR); r1 = np.maximum(r1, BELIEF_FLOOR)
        return pub, ph, r0 / r0.sum(), r1 / r1.sum()
    return pub, ph, _sample_belief(rng), _sample_belief(rng)


def _boot_label_one(args):
    """Worker: solve one bootstrap situation exactly (identical CFV convention to `_label_one`)."""
    idx, label_iters, queries = args
    pub, ph, r0, r1 = _boot_situation(idx, queries)
    cfv0, cfv1 = subgame_cfvs(pub, ph, r0, r1, label_iters)
    zs_err = abs(float(r0 @ cfv0 + r1 @ cfv1))
    return (_features(pub, ph, r0, r1),
            np.concatenate([cfv0, cfv1]).astype(np.float32), zs_err)


def generate_boot_labels(n_situations: int, label_iters: int, workers: int, queries: list):
    """Solve n query-biased subgames in a process pool; deterministic order (same as generate_labels)."""
    from concurrent.futures import ProcessPoolExecutor

    xs, ys, max_zs = [], [], 0.0
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        jobs = ((i, label_iters, queries) for i in range(n_situations))
        for i, (x, y, zs) in enumerate(pool.map(_boot_label_one, jobs, chunksize=32)):
            xs.append(x); ys.append(y); max_zs = max(max_zs, zs)
            if (i + 1) % 900 == 0:
                print(f"  boot-labels {i + 1}/{n_situations} ({(i + 1) / (time.time() - t0):.1f}/s)")
    return np.stack(xs), np.stack(ys), max_zs


GADGET_T, GADGET_F = 0, 1        # opponent's gadget actions: terminate / follow


def resolve_subgame_gadget(hero: int, pub: int, pot_half: int, r_hero: np.ndarray,
                           w_opp: np.ndarray, iters: int, hist: str) -> dict:
    """DeepStack's CFR-D re-solving gadget for ONE round-1 subgame (supplementary p.24, p.28-29).

    The opponent is dealt each rank (uniform gadget deal = the conservative option, guarantees
    kept) and regret-matches between TERMINATE — banking that rank's constraint CFV `w_opp`
    carried from hero's trunk — and FOLLOW into the subgame against hero's FIXED range `r_hero`.
    T/F values are compared in per-rank normalized chips (u per rank given hero plays r_hero),
    the same units the trunk stored. Hero's average strategy is then safe by construction
    (Lemma 3: each opponent rank is held to <= max(w, BV)); no opponent range enters at all.
    Returns ONLY hero's round-1 policy — the opponent's gadget strategy is a solving device."""
    opp = 1 - hero
    regret: dict = {}
    ssum: dict = {}
    gadget_regret = np.zeros((RANKS, 2))
    # opponent counterfactual reach per rank (hero range x card removal) -> the F-value normalizer
    denom = r_hero @ MULT[pub] if opp == 1 else MULT[pub] @ r_hero
    for t in range(1, iters + 1):
        pos = np.maximum(gadget_regret, 0.0)
        tot = pos.sum(axis=1)
        q_follow = np.where(tot > 1e-12, pos[:, GADGET_F] / np.maximum(tot, 1e-12), 0.5)
        follow_raw = np.zeros(RANKS)
        for a in range(RANKS):
            for b in range(RANKS):
                if MULT[pub][a, b] <= 0.0:
                    continue
                hero_rank, opp_rank = (a, b) if hero == 0 else (b, a)
                rc = r_hero[hero_rank] * MULT[pub][a, b] / 60.0
                reach0 = 1.0 if hero == 0 else q_follow[a]      # opponent's F prob is their
                reach1 = q_follow[b] if hero == 0 else 1.0      # strategy reach into the subgame
                u0 = vanilla_cfr(_subgame_root(a, b, pub, pot_half, hist), t,
                                 reach0, reach1, rc, regret, ssum)
                follow_raw[opp_rank] += r_hero[hero_rank] * MULT[pub][a, b] * (u0 if opp == 0 else -u0)
        follow = np.where(denom > 0.0, follow_raw / np.maximum(denom, 1e-12), w_opp)
        node = q_follow * follow + (1.0 - q_follow) * w_opp
        gadget_regret[:, GADGET_F] += follow - node
        gadget_regret[:, GADGET_T] += w_opp - node
        np.maximum(gadget_regret, 0.0, out=gadget_regret)      # CFR+ clamp, same as vanilla_cfr
    pol = _avg(ssum)
    # round-1 actor alternates from P0: hero's infosets are those at hero's parity in the suffix
    return {k: v for k, v in pol.items()
            if (len(k.split("|")[2]) - len(hist)) % 2 == hero}


def gadget_fill(pol0: dict, constraints_by_hero: dict, fill_iters: int) -> dict:
    """SAFE round-1 completion: per boundary x public x player, a gadget re-solve on that
    player's OWN trunk range with the opponent constraint CFVs their trunk carried forward.
    Replaces the unsafe range-re-solve fill (iteration 2's measured ~38 mbb composition cost)."""
    pol = dict(pol0)
    for hist, pot_half, s0, s1 in _boundaries(pol0):
        for hero in (0, 1):
            r_hero = _floor_norm(s0 if hero == 0 else s1, FILL_BELIEF_FLOOR)
            for pub in range(RANKS):
                w_opp = constraints_by_hero[hero][(hist, pub)]
                pol.update(resolve_subgame_gadget(hero, pub, pot_half, r_hero, w_opp,
                                                  fill_iters, hist))
    return pol


def _compose_round0(pol_a: dict, pol_b: dict) -> dict:
    """Each player's round-0 strategy from THEIR OWN re-solving trunk (hero=0 -> pol_a)."""
    out = {}
    for k in sorted(set(pol_a) | set(pol_b)):    # sorted: no set-iteration order in outputs
        actor = len(k.split("|")[2]) % 2
        out[k] = (pol_a if actor == 0 else pol_b)[k]
    return out


def exact_constraints(pol_full: dict) -> dict:
    """Gadget constraints for the full-solve ablation: each opponent's per-rank normalized CFVs
    under the full policy's OWN round-1 play — the exact analogue of the trunk's leaf
    evaluations. Full trunk + gadget fill on these isolates the fill construction alone."""
    pol0 = _round0_only(pol_full)
    out: dict = {0: {}, 1: {}}
    for hist, pot_half, s0, s1 in _boundaries(pol0):
        r0 = _floor_norm(s0, FILL_BELIEF_FLOOR)
        r1 = _floor_norm(s1, FILL_BELIEF_FLOOR)
        for pub in range(RANKS):
            u0 = np.zeros((RANKS, RANKS))
            for a in range(RANKS):
                for b in range(RANKS):
                    if MULT[pub][a, b] > 0.0:
                        u0[a, b] = _policy_ev0(_subgame_root(a, b, pub, pot_half, hist), pol_full)
            wu = MULT[pub] * u0
            d1, d0 = r0 @ MULT[pub], MULT[pub] @ r1
            out[0][(hist, pub)] = np.where(d1 > 0.0, -(r0 @ wu) / np.maximum(d1, 1e-12), 0.0)
            out[1][(hist, pub)] = np.where(d0 > 0.0, (wu @ r1) / np.maximum(d0, 1e-12), 0.0)
    return out


def gadget_resolve(leaf_fn, trunk_iters: int, fill_iters: int):
    """The full iteration-3 construction: two gadget trunks (one per re-solving player),
    composed round-0 policy, and gadget fills on each trunk's carried constraints.

    Returns (full policy, composed round-0 policy, [per-hero trunk round-0 policies])."""
    trunks = {}
    for hero in (0, 1):
        trunks[hero] = TrunkResolver(leaf_fn, hero=hero)
        trunks[hero].run(trunk_iters)
    trunk_pols = [trunks[0].policy(), trunks[1].policy()]
    pol0 = _compose_round0(trunk_pols[0], trunk_pols[1])
    constraints = {hero: trunks[hero].opponent_constraints() for hero in (0, 1)}
    return gadget_fill(pol0, constraints, fill_iters), pol0, trunk_pols


# ---------------- phase 4: baseline + gate ----------------
def full_solve(iters: int) -> dict:
    """Ground truth: full-tree linear CFR+ over the whole game (the deep_cfr --vanilla path)."""
    regret: dict = {}
    ssum: dict = {}
    for t in range(1, iters + 1):
        for s, w in root_states():
            vanilla_cfr(s, t, 1.0, 1.0, w, regret, ssum)
    return _avg(ssum)


def _round0_only(pol: dict) -> dict:
    return {k: v for k, v in pol.items() if k.split("|")[1] == "-1"}


def _policy_table(pol_a: dict, pol_b: dict) -> dict:
    """Round-0 side-by-side action probs (resolved vs full) for the gate diagnostics."""
    table = {}
    for k in sorted(_round0_only(pol_a)):
        row_a = {str(a): round(p, 4) for a, p in pol_a[k].items()}
        row_b = {str(a): round(p, 4) for a, p in pol_b.get(k, {}).items()}
        table[k] = {"resolved": row_a, "full": row_b}
    return table


def _persist(results: dict):
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")


def _load_results() -> dict:
    """Staged runs (--stage gate/oracle) continue the JSON the labels stage persisted."""
    if RESULTS_PATH.exists():
        return json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    return {}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--quick", action="store_true", help="tiny smoke run (~1 min)")
    ap.add_argument("--situations", type=int, default=N_SITUATIONS)
    ap.add_argument("--label-iters", type=int, default=LABEL_CFR_ITERS)
    ap.add_argument("--baseline-iters", type=int, default=BASELINE_ITERS)
    ap.add_argument("--trunk-iters", type=int, default=TRUNK_ITERS)
    ap.add_argument("--fill-iters", type=int, default=FILL_CFR_ITERS)
    ap.add_argument("--workers", type=int, default=LABEL_WORKERS)
    ap.add_argument("--oracle-trunk", action="store_true",
                    help="diagnostic: exact-solve leaf instead of the net (isolates net error)")
    ap.add_argument("--stage", choices=("all", "labels", "gate", "oracle"), default="all",
                    help="split the run so each call stays synchronous: labels -> gate -> oracle")
    args = ap.parse_args()
    if args.quick:
        args.situations, args.label_iters = 90, 60
        args.baseline_iters, args.trunk_iters, args.fill_iters = 150, 200, 100

    np.random.seed(SEED)
    torch.manual_seed(SEED)
    torch.set_num_threads(1)                     # determinism > speed for a net this small

    # sanity: the 3-card deal tensor must be a probability distribution (mult/60 over a,b,pub)
    assert abs(MULT.sum() / 60.0 - 1.0) < 1e-12 and abs(M2.sum() - 1.0) < 1e-12

    if args.stage in ("gate", "oracle"):
        results = _load_results()               # continue the labels stage's JSON
    else:
        results = {"seed": SEED, "config": {
            "situations": args.situations, "label_iters": args.label_iters,
            "baseline_iters": args.baseline_iters, "trunk_iters": args.trunk_iters,
            "fill_iters": args.fill_iters, "belief_floor": BELIEF_FLOOR,
            "fill_belief_floor": FILL_BELIEF_FLOOR, "workers": args.workers,
            "gate_pass_delta_mbb": GATE_PASS_DELTA_MBB, "quick": args.quick,
        }}

    if args.stage == "oracle":
        t0 = time.time()
        print(f"[oracle] 2x gadget trunk {ORACLE_TRUNK_ITERS} iters, exact {ORACLE_LEAF_ITERS}-iter leaf ...")
        pol_o, _ = gadget_resolve(_oracle_leaf_fn(ORACLE_LEAF_ITERS),   # one shared leaf cache
                                  ORACLE_TRUNK_ITERS, args.fill_iters)
        expl_oracle = exploitability(pol_o)
        results.setdefault("resolve", {})["exploitability_oracle_trunk_gadget_mbb"] = expl_oracle
        _persist(results)
        print(f"      oracle+gadget exploitability {expl_oracle:.2f} mbb/hand "
              f"({time.time() - t0:.0f}s) | results -> {RESULTS_PATH}")
        return

    # ---- phase 1: labels (exact vanilla_cfr subgame solves) ----
    if args.stage in ("all", "labels"):
        print(f"[1/4] label stability probe: {STABILITY_PROBE_N} subgames, 500 vs 1000 iters ...")
        stability = label_stability_probe(STABILITY_PROBE_N)
        results["label_stability"] = stability
        print(f"      max abs CFV diff {stability['max_abs_cfv_diff_pot']:.4f} pot "
              f"| mean {stability['mean_abs_cfv_diff_pot']:.4f} pot")
        t0 = time.time()
        print(f"[1/4] labels: {args.situations} subgames x {args.label_iters} exact CFR iters "
              f"({args.workers} workers) ...")
        x, y, zs_err = generate_labels(args.situations, args.label_iters, args.workers)
        results["labels"] = {"n": int(x.shape[0]), "max_zero_sum_err": zs_err,
                             "cfv_abs_mean_pot": float(np.abs(y).mean()),
                             "seconds": round(time.time() - t0, 1)}
        print(f"      done in {results['labels']['seconds']}s | max zero-sum err {zs_err:.2e}")
        LABELS_CACHE.parent.mkdir(parents=True, exist_ok=True)
        np.savez(LABELS_CACHE, x=x, y=y)
        _persist(results)
        if args.stage == "labels":
            print(f"      labels cached -> {LABELS_CACHE}")
            return
    else:                                        # stage == "gate": reuse the cached labels
        cached = np.load(LABELS_CACHE)
        x, y = cached["x"], cached["y"]
        print(f"[1/4] labels: loaded {x.shape[0]} cached situations from {LABELS_CACHE}")

    # ---- phase 2: net ----
    t0 = time.time()
    print("[2/4] net: train CFVNet (Huber, zero-sum-corrected outputs) ...")
    net, mae_train, mae_hold = train_net(x, y)
    results["net"] = {"mae_train_pot": mae_train, "mae_holdout_pot": mae_hold,
                      "seconds": round(time.time() - t0, 1)}
    print(f"      train MAE {mae_train:.4f} pot | HOLDOUT MAE {mae_hold:.4f} pot "
          f"| {results['net']['seconds']}s")
    _persist(results)

    # ---- phase 3: baseline full solve + depth-limited net resolve + round-1 fill ----
    t0 = time.time()
    print(f"[3/4] baseline: full vanilla_cfr solve, {args.baseline_iters} iters ...")
    pol_full = full_solve(args.baseline_iters)
    expl_full = exploitability(pol_full)
    print(f"      baseline exploitability {expl_full:.2f} mbb/hand ({time.time() - t0:.0f}s)")

    t0 = time.time()
    print(f"[3/4] resolve: 2x gadget trunk CFR ({args.trunk_iters} iters, net leaf) + gadget fill ...")
    pol_resolved, pol0_net = gadget_resolve(_net_leaf_fn(net), args.trunk_iters, args.fill_iters)
    expl_resolved = exploitability(pol_resolved)
    print(f"      net+gadget exploitability {expl_resolved:.2f} mbb/hand ({time.time() - t0:.0f}s)")

    # ablation: gadget fill under the full solve's trunk with EXACT constraints -> isolates the
    # fill construction alone (should sit at the baseline if the gadget composition is safe).
    pol_ablation = gadget_fill(_round0_only(pol_full), exact_constraints(pol_full), args.fill_iters)
    expl_ablation = exploitability(pol_ablation)
    print(f"      ablation (full trunk + gadget fill) {expl_ablation:.2f} mbb/hand")

    expl_oracle = None
    if args.oracle_trunk:
        t0 = time.time()
        print(f"[3/4] oracle+gadget trunk (diagnostic): {ORACLE_TRUNK_ITERS} iters, exact leaf ...")
        pol_o, _ = gadget_resolve(_oracle_leaf_fn(ORACLE_LEAF_ITERS),
                                  ORACLE_TRUNK_ITERS, args.fill_iters)
        expl_oracle = exploitability(pol_o)
        print(f"      oracle+gadget exploitability {expl_oracle:.2f} mbb/hand "
              f"({time.time() - t0:.0f}s)")

    prev = results.get("resolve", {})            # iteration-2 (no-gadget) numbers, kept as contrast
    no_gadget = prev.get("no_gadget_iteration2") or {
        "resolved": prev.get("exploitability_resolved_mbb"),
        "ablation_unsafe_fill": prev.get("exploitability_ablation_fulltrunk_fill_mbb"),
        "oracle_trunk": prev.get("exploitability_oracle_trunk_mbb"),
    }
    results["iteration"] = 3
    results["resolve"] = {
        "exploitability_full_mbb": expl_full,
        "exploitability_resolved_mbb": expl_resolved,
        "exploitability_ablation_fulltrunk_gadget_fill_mbb": expl_ablation,
        "exploitability_oracle_trunk_gadget_mbb": expl_oracle,
        "no_gadget_iteration2": no_gadget,
    }
    _persist(results)

    # ---- phase 4: gate ----
    delta = expl_resolved - expl_full
    passed = delta <= GATE_PASS_DELTA_MBB
    results["gate"] = {
        "pass": bool(passed),
        "bar": f"resolved - full <= {GATE_PASS_DELTA_MBB} mbb/hand (pre-registered)",
        "delta_mbb": delta,
        "full_solve_mbb_per_hand": expl_full,
        "net_resolved_mbb_per_hand": expl_resolved,
        "full_solve_pot_fraction": expl_full / 2000.0,        # initial pot = 2 antes
        "net_resolved_pot_fraction": expl_resolved / 2000.0,
        "holdout_cfv_mae_pot_fraction": mae_hold,
        "trunk_policy_table": _policy_table(pol0_net, pol_full),
    }
    _persist(results)
    print(f"\n[4/4] GATE {'PASS' if passed else 'FAIL'}: full {expl_full:.2f} vs "
          f"net-resolved {expl_resolved:.2f} mbb/hand (delta {delta:+.2f}, bar "
          f"{GATE_PASS_DELTA_MBB}) | holdout CFV MAE {mae_hold:.4f} pot")
    print(f"      results -> {RESULTS_PATH}")


if __name__ == "__main__":
    main()
