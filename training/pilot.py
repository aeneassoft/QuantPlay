"""The DE-RISK PILOT (GATE-2 core) — proves, CHEAPLY and LOCALLY, that realized-EV ranking carries signal BEFORE any
RunPod spend (both consults' #1 advice). For each generated 6-max decision state it rolls out a small CANDIDATE set
(fold / check / call / raise sizings / all-in) via rl_env.rollout_action_ev and ranks by realized EV vs the league.

Output per state = the EV-ranked candidates + an EV-GAP between the rollout-BEST action and a BASELINE policy's action.
A positive mean gap = there IS exploitable signal a learner could capture (the local GATE-2 evidence). This harness is
the $0 half; the Qwen-policy + AWR/DPO adapter + the on-GPU run are the pod half (training/qwen_grpo.py). The output
(spot, best_action, gap) is also the AWR/preference training data. Per docs/plans/QWEN_6MAX_PLAN.md + the plan's pilot.

HARD INVARIANT (tested): when fold is legal it is a candidate with EV exactly 0, so the oracle EV is always >= 0 —
the learner can never be forced into a -EV spot it could have folded.
"""
from __future__ import annotations

from statistics import mean, pstdev

from pokerbot.arena.sixmax import PROFILES, SixMaxBot
from training.rl_env import gen_decision_states, league_policy, rollout_action_ev

DEFAULT_LEAGUE = ("tag", "lag", "nit", "station", "maniac")


def candidate_actions(snapshot) -> list:
    """Sensible discrete candidates from the legal set: (action, amount_chips, label)."""
    la = snapshot.legal_actions()
    out = []
    if la.get("can_check"):
        out.append(("check", None, "check"))
    if la.get("can_call"):
        out.append(("call", None, "call"))
    if la.get("can_fold"):
        out.append(("fold", None, "fold"))
    if la.get("can_raise"):
        rmin, rmax = la.get("raise_min"), la.get("raise_max")
        out.append(("raise", rmin, "raise_min"))
        mid = rmin + (rmax - rmin) // 3
        if rmin < mid < rmax:
            out.append(("raise", mid, "raise_mid"))
        out.append(("allin", None, "allin"))
    return out


def rank_state(snapshot, hero_seat, cont_policy, k: int = 16, profiles=DEFAULT_LEAGUE, base_seed: int = 0) -> list:
    """Rollout each candidate -> EV(bb); return candidates sorted best-first."""
    scored = []
    for a, amt, label in candidate_actions(snapshot):
        ev = rollout_action_ev(snapshot, hero_seat, a, amt, cont_policy, profiles=profiles, k=k,
                               base_seed=base_seed)               # SAME base_seed for all candidates = CRN-paired
        scored.append({"action": a, "amount": amt, "label": label, "ev_bb": round(ev, 2)})
    scored.sort(key=lambda x: x["ev_bb"], reverse=True)
    return scored


def baseline_profile(profile: str, hero_seat: int = 0):
    """A baseline policy = a SixMaxBot of `profile` (its decide() action at the spot)."""
    bot = SixMaxBot(hero_seat, PROFILES[profile])

    def _fn(snapshot, seat):
        d = bot.decide(snapshot.obs_for(seat))
        return d["action"], d.get("amount")
    return _fn


def baseline_random(seed: int = 0):
    """The weakest baseline: a uniform pick over legal actions (raise -> min). The floor a learner must clear."""
    import random as _r
    rng = _r.Random(seed)

    def _fn(snapshot, seat):
        la = snapshot.legal_actions()
        opts = []
        if la.get("can_check"):
            opts.append(("check", None))
        if la.get("can_call"):
            opts.append(("call", None))
        if la.get("can_fold"):
            opts.append(("fold", None))
        if la.get("can_raise"):
            opts.append(("raise", la.get("raise_min")))
        return rng.choice(opts) if opts else ("fold", None)
    return _fn


def run_pilot(n_states: int = 8, k: int = 16, seed: int = 0, profiles=DEFAULT_LEAGUE, hero_seat: int = 0,
              baselines=None) -> dict:
    """Generate states, rank candidates by rollout-EV (the oracle), and compare the oracle vs EACH baseline on FRESH,
    PAIRED holdout seeds (unbiased). Multiple baselines share the oracle rollouts (cheap). Returns per-baseline mean
    gaps = the GATE-2 thesis map: a STRONG positive gap vs a weak/mediocre baseline => realized-EV ranking carries a
    learnable signal; a ~0 gap vs a strong baseline => the coarse candidate set (not the EV signal) is the ceiling."""
    cont = league_policy(SixMaxBot(hero_seat, PROFILES["tag"]))   # hero continuation = a tag policy
    if baselines is None:
        baselines = {"random": baseline_random(seed), "maniac": baseline_profile("maniac", hero_seat),
                     "tag": baseline_profile("tag", hero_seat)}
    names = list(baselines.keys())
    rows = []
    for idx, (snap, spot) in enumerate(gen_decision_states(profiles=profiles, hero_seat=hero_seat,
                                                           n_states=n_states, seed=seed)):
        sel_seed = seed + idx
        scored = rank_state(snap, hero_seat, cont, k=k, profiles=profiles, base_seed=sel_seed)
        oracle = scored[0]
        fold_avail = any(c["label"] == "fold" for c in scored)
        hold = sel_seed + 777777                                  # fresh seeds -> unbiased; shared by oracle+baselines
        o_ev = rollout_action_ev(snap, hero_seat, oracle["action"], oracle["amount"], cont,
                                 profiles=profiles, k=k, base_seed=hold)
        gaps = {}
        for nm, fn in baselines.items():
            a, amt = fn(snap, hero_seat)
            b_ev = rollout_action_ev(snap, hero_seat, a, amt, cont, profiles=profiles, k=k, base_seed=hold)
            gaps[nm] = round(o_ev - b_ev, 2)
        rows.append({"spot": f"{spot.street}/{spot.hero_pos}", "hand": " ".join(spot.hero_hole),
                     "oracle_label": oracle["label"], "sel_oracle_ev": oracle["ev_bb"],
                     "oracle_ev": round(o_ev, 2), "gaps": gaps, "fold_avail": fold_avail})
    fold_sel = [r["sel_oracle_ev"] for r in rows if r["fold_avail"]]
    n = len(rows)

    def _stat(nm):
        xs = [r["gaps"][nm] for r in rows]
        m = mean(xs)
        sem = pstdev(xs) / (n ** 0.5) if n > 1 else 0.0
        return {"gap": round(m, 2), "sem": round(sem, 2), "sig_2sem": bool(m > 2 * sem and m > 0)}
    return {"n": n,
            "mean_oracle_ev": round(mean(r["oracle_ev"] for r in rows), 2),
            "gap_vs": {nm: _stat(nm) for nm in names},      # per-baseline {gap, sem, significant at 2*SEM}
            "fold_floor_min_sel_oracle_ev": round(min(fold_sel), 2) if fold_sel else None,
            "rows": rows}


if __name__ == "__main__":
    import json
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    kk = int(sys.argv[2]) if len(sys.argv) > 2 else 24
    res = run_pilot(n_states=n, k=kk, seed=1)
    print(json.dumps({k_: v for k_, v in res.items() if k_ != "rows"}, indent=2))
    g = res["gap_vs"]
    print(f"\nGATE-2 thesis map (oracle - baseline, bb/decision): "
          + ", ".join(f"{nm} {g[nm]['gap']:+.2f}±{g[nm]['sem']:.2f}{'*' if g[nm]['sig_2sem'] else ''}" for nm in g))
    sig = [nm for nm in g if g[nm]["sig_2sem"]]
    print(f"-> significant (>2*SEM) positive gap vs: {sig or 'NONE'} "
          f"({'signal is real + learnable' if sig else 'directional only — need larger n'})")
