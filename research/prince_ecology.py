"""PRINCEDARKNESS-PROTOKOLL — Abschnitt 4: Ökologie-Simulation B / C / D (2026-07-07).

P_D = frequency profile fitted to the MEASURED cash stats (VPIP .55 / PFR .15 / limp .39 / 3bet .11 /
AF 2.3 / cbet .52 / WTSD .30 / W$SD .39 / overbet-share .28). Archetypes LP, TAG, GTOapx are heuristic
agents on the same interface. Engine = pokerbot.engine.table (6-max, side pots, real showdowns).

HONEST LIMITS (documented, not hidden):
 * The spec asks for >=1,000,000 hands per ecology. That is not feasible in-session; N is a CLI arg and
   every result carries its n + SE. Default 40k/ecology.
 * P_D is a BEHAVIOURAL CLONE fitted to aggregate frequencies, not a node-exact strategy: it reproduces
   the measured tendencies (loose-passive-limpy preflop, overbet-heavy postflop, calls down light) and is
   NOT the real player. Every simulated number is therefore [SIMULATION], never [MESSUNG].
 * Bayes smoothing: frequencies are used directly (n>=400 for the big ones); thin nodes (cbet n=54,
   4bet n=66) are shrunk toward the pool prior with k=25 pseudo-counts -> documented as SMOOTH_K.

Run:  python -m research.prince_ecology [hands_per_eco=40000] [seed=11]
"""
from __future__ import annotations

import json
import math
import random
import sys
from collections import defaultdict

from pokerbot.engine.cards import hand_class
from pokerbot.engine.equity import equity_vs_class_range
from pokerbot.engine.table import Table
from pokerbot.strategy import preflop_strength as ps

_ALL_CLASSES = None

SMOOTH_K = 25          # pseudo-counts for thin-node shrinkage toward the pool prior
EQ_ITERS = 60          # MC iterations for the equity estimate inside the agents (speed/precision trade)

# ---- measured Princedarkness cash frequencies (from research/prince_protocol.py, n=923) ----
PD = {
    "vpip": 0.549, "pfr": 0.153, "limp": 0.387, "threebet": 0.108, "fourbet": 0.061,
    "af": 2.32, "cbet_flop": 0.517, "wtsd": 0.295, "wsd": 0.386,
    "overbet_share": 0.28, "blind_fold_vs_raise": 0.268, "blind_3bet": 0.146,
}
POOL_PRIOR = {"cbet_flop": 0.60, "fourbet": 0.05}


def smooth(val, n, key):
    p = POOL_PRIOR.get(key)
    return val if p is None else (val * n + p * SMOOTH_K) / (n + SMOOTH_K)


PD["cbet_flop"] = smooth(PD["cbet_flop"], 54, "cbet_flop")
PD["fourbet"] = smooth(PD["fourbet"], 66, "fourbet")


# ---------------------------------------------------------------- agents
class Agent:
    """decide(obs) -> (action, amount).  obs = Table.obs_for(seat)."""
    def __init__(self, rng):
        self.rng = rng

    def eq(self, obs):
        """equity vs a random single opponent (class-range = all classes), scaled for multiway."""
        global _ALL_CLASSES
        if _ALL_CLASSES is None:
            from pokerbot.engine.cards import all_hand_classes
            _ALL_CLASSES = all_hand_classes()
        try:
            e = equity_vs_class_range(obs["hole"], _ALL_CLASSES, obs["board"], iters=EQ_ITERS)
            opp = max(1, obs["n_active"] - 1)
            return e ** opp if opp > 1 else e          # crude multiway scaling (documented approximation)
        except Exception:
            return 0.5

    def _raise_to(self, obs, frac_pot):
        lo, hi = obs["raise_min"], obs["raise_max"]
        if lo is None:
            return None
        target = obs["cur_bet"] + max(obs["bb"], int(frac_pot * obs["pot"]))
        return max(lo, min(int(target), hi))


class PrinceClone(Agent):
    """P_D: loose-passive-limpy preflop (VPIP .55 / PFR .15 / limp .39), aggressive+overbet-heavy postflop
    (AF 2.3, 28% of bets are overbets), calls down light (W$SD .39 = pays off wide)."""
    def decide(self, obs):
        st, r = obs["street"], self.rng
        if st == "preflop":
            s = ps.strength(_hc(obs["hole"]))
            faced = obs["preflop_raises"] > 0
            if not faced:
                if r.random() < PD["vpip"]:
                    if r.random() < PD["pfr"] / PD["vpip"]:
                        return ("raise", self._raise_to(obs, 1.0)) if obs["can_raise"] else ("call", None)
                    return ("call", None) if obs["can_call"] else ("check", None)
                return ("check", None) if obs["can_check"] else ("fold", None)
            # facing a raise
            if r.random() < PD["threebet"] and s > 0.45 and obs["can_raise"]:
                return ("raise", self._raise_to(obs, 1.2))
            if r.random() < (1 - PD["blind_fold_vs_raise"]) and s > 0.28:
                return ("call", None) if obs["can_call"] else ("check", None)
            return ("fold", None) if obs["to_call"] > 0 else ("check", None)
        # postflop
        e = self.eq(obs)
        if obs["to_call"] == 0:
            if r.random() < (PD["cbet_flop"] if st == "flop" else 0.45) and obs["can_raise"]:
                frac = 1.9 if r.random() < PD["overbet_share"] else r.choice([0.33, 0.5, 0.75])
                return ("bet", self._raise_to(obs, frac))
            return ("check", None)
        pot_odds = obs["to_call"] / max(1, obs["pot"] + obs["to_call"])
        if e > 0.72 and obs["can_raise"] and r.random() < 0.45:
            frac = 1.9 if r.random() < PD["overbet_share"] else 0.8
            return ("raise", self._raise_to(obs, frac))
        # calls down light: measured W$SD .39 -> call threshold clearly BELOW pot odds
        if e > pot_odds * 0.62:
            return ("call", None)
        return ("fold", None)


class LP(Agent):
    """loose-passive recreational: VPIP ~.60, PFR ~.08, almost never folds postflop with any piece."""
    def decide(self, obs):
        r = self.rng
        if obs["street"] == "preflop":
            if r.random() < 0.60:
                if r.random() < 0.13 and obs["can_raise"]:
                    return ("raise", self._raise_to(obs, 0.9))
                return ("call", None) if obs["can_call"] else ("check", None)
            return ("check", None) if obs["can_check"] else ("fold", None)
        e = self.eq(obs)
        if obs["to_call"] == 0:
            return ("bet", self._raise_to(obs, 0.4)) if (e > 0.62 and obs["can_raise"] and r.random() < 0.35) else ("check", None)
        return ("call", None) if e > 0.22 else ("fold", None)


class TAG(Agent):
    """tight-aggressive reg: VPIP ~.24, PFR ~.19, cbets, folds to pressure without equity."""
    def decide(self, obs):
        r = self.rng
        if obs["street"] == "preflop":
            s = ps.strength(_hc(obs["hole"]))
            thr = 0.55 if obs["position"] in ("UTG", "EP", "MP") else 0.42
            if obs["preflop_raises"] > 0:
                if s > 0.72 and obs["can_raise"]:
                    return ("raise", self._raise_to(obs, 1.1))
                return ("call", None) if (s > thr + 0.1 and obs["can_call"]) else (("fold", None) if obs["to_call"] > 0 else ("check", None))
            if s > thr and obs["can_raise"]:
                return ("raise", self._raise_to(obs, 1.0))
            return ("check", None) if obs["can_check"] else ("fold", None)
        e = self.eq(obs)
        if obs["to_call"] == 0:
            return ("bet", self._raise_to(obs, 0.6)) if (obs["can_raise"] and (e > 0.58 or r.random() < 0.28)) else ("check", None)
        pot_odds = obs["to_call"] / max(1, obs["pot"] + obs["to_call"])
        if e > 0.78 and obs["can_raise"] and r.random() < 0.4:
            return ("raise", self._raise_to(obs, 0.85))
        return ("call", None) if e > pot_odds * 1.05 else ("fold", None)


class GTOapx(Agent):
    """equilibrium APPROXIMATION: pot-odds-disciplined, balanced sizings, mixed frequencies.
    NOT a solver — an honest stand-in (see limits)."""
    def decide(self, obs):
        r = self.rng
        if obs["street"] == "preflop":
            s = ps.strength(_hc(obs["hole"]))
            open_thr = {"UTG": 0.62, "EP": 0.60, "MP": 0.55, "CO": 0.47, "BTN": 0.40, "SB": 0.45, "BB": 0.40}.get(obs["position"], 0.5)
            if obs["preflop_raises"] > 0:
                if s > 0.76 and obs["can_raise"] and r.random() < 0.75:
                    return ("raise", self._raise_to(obs, 1.15))
                if s > open_thr + 0.08 and obs["can_call"]:
                    return ("call", None)
                return ("fold", None) if obs["to_call"] > 0 else ("check", None)
            if s > open_thr and obs["can_raise"]:
                return ("raise", self._raise_to(obs, 0.75))
            return ("check", None) if obs["can_check"] else ("fold", None)
        e = self.eq(obs)
        if obs["to_call"] == 0:
            if obs["can_raise"] and (e > 0.62 or r.random() < 0.30):
                return ("bet", self._raise_to(obs, r.choice([0.33, 0.5, 0.75])))
            return ("check", None)
        pot_odds = obs["to_call"] / max(1, obs["pot"] + obs["to_call"])
        if e > 0.80 and obs["can_raise"] and r.random() < 0.35:
            return ("raise", self._raise_to(obs, 0.75))
        return ("call", None) if e >= pot_odds else ("fold", None)


class PrinceReset(PrinceClone):
    """P_D' = the INVERSE OPERATOR: after an H4 trigger (lost >=20bb showdown or lost all-in), a forced
    reset for Y hands — baseline range only (tight), and a hard block on hero payoffs (no light calldowns)."""
    RESET_HANDS = 20

    def __init__(self, rng):
        super().__init__(rng)
        self.lock = 0

    def notify_hand_end(self, net_bb, was_showdown, was_allin):
        if (net_bb <= -20 and was_showdown) or (was_allin and net_bb < 0):
            self.lock = self.RESET_HANDS
        elif self.lock > 0:
            self.lock -= 1

    def decide(self, obs):
        if self.lock <= 0:
            return super().decide(obs)
        r = self.rng
        if obs["street"] == "preflop":                       # baseline range only
            s = ps.strength(_hc(obs["hole"]))
            if s > 0.60 and obs["can_raise"]:
                return ("raise", self._raise_to(obs, 1.0))
            if s > 0.52 and obs["can_call"] and obs["to_call"] <= 3 * obs["bb"]:
                return ("call", None)
            return ("check", None) if obs["can_check"] else ("fold", None)
        e = self.eq(obs)
        if obs["to_call"] == 0:
            return ("bet", self._raise_to(obs, 0.6)) if (e > 0.62 and obs["can_raise"]) else ("check", None)
        pot_odds = obs["to_call"] / max(1, obs["pot"] + obs["to_call"])
        return ("call", None) if e > pot_odds * 1.15 else ("fold", None)   # payoff block


def _hc(hole):
    """['As','Kd'] -> 'AKo' class string for preflop_strength.strength"""
    try:
        return hand_class(hole[0], hole[1])
    except Exception:
        return "72o"


# ---------------------------------------------------------------- simulation
def run_eco(hero_cls, mix, hands, seed, label):
    """mix = (n_LP, n_TAG, n_GTO) filling the other 5 seats. Returns bb/100 + SD + drawdown."""
    rng = random.Random(seed)
    hero = hero_cls(random.Random(seed + 1))
    villains = []
    for cls, k in ((LP, mix[0]), (TAG, mix[1]), (GTOapx, mix[2])):
        villains += [cls(random.Random(seed + 100 + len(villains) + i)) for i in range(k)]
    agents = [hero] + villains
    n = len(agents)
    t = Table([f"p{i}" for i in range(n)], starting_stack=10000, sb=50, bb=100, seed=seed)
    nets, guard_fail = [], 0
    for _ in range(hands):
        t.start_hand()
        start_stack = t.seats[0].stack
        was_allin = False
        g = 0
        while not t.hand_over and g < 400:
            g += 1
            la = t.legal_actions()
            i = la.get("to_act")
            if i is None:
                break
            obs = t.obs_for(i)
            try:
                a, amt = agents[i].decide(obs)
            except Exception:
                a, amt = ("check", None) if obs["can_check"] else ("fold", None)
            if a in ("bet", "raise") and (amt is None or not obs["can_raise"]):
                a, amt = ("call", None) if obs["can_call"] else ("check", None)
            if a == "check" and not obs["can_check"]:
                a = "call" if obs["can_call"] else "fold"
            if a == "fold" and obs["to_call"] == 0:
                a = "check"
            try:
                t.act(a, amt)
            except Exception:
                guard_fail += 1
                try:
                    t.act("fold" if la.get("to_call", 0) > 0 else "check", None)
                except Exception:
                    break
            if i == 0 and t.seats[0].stack == 0:
                was_allin = True
        net_bb = (t.seats[0].stack - start_stack) / t.bb
        nets.append(net_bb)
        if hasattr(hero, "notify_hand_end"):
            shown = bool((t.result or {}).get("shown"))
            hero.notify_hand_end(net_bb, shown, was_allin)
    m = sum(nets) / len(nets)
    sd = (sum((x - m) ** 2 for x in nets) / max(1, len(nets) - 1)) ** 0.5
    # drawdown
    cum, peak, mdd = 0.0, 0.0, 0.0
    for x in nets:
        cum += x
        peak = max(peak, cum)
        mdd = min(mdd, cum - peak)
    bb100 = m * 100
    se = sd / math.sqrt(len(nets)) * 100
    out = {"label": label, "n_hands": len(nets), "bb100": round(bb100, 1), "se": round(se, 1),
           "sd_per_hand_bb": round(sd, 2), "max_drawdown_bb": round(mdd, 1), "engine_guard_fixups": guard_fail}
    # risk of ruin (Kelly-style approx for a winning/losing player; exact for the loser: RoR=1)
    for bi in (30, 50, 100):
        bank = bi * 100.0     # buy-in = 100bb
        if bb100 <= 0:
            out[f"ror_{bi}bi"] = 1.0
        else:
            wr, s = bb100 / 100.0, sd
            out[f"ror_{bi}bi"] = round(math.exp(-2 * wr * bank / (s ** 2)), 4) if s > 0 else 0.0
    out["kelly_fraction"] = round((bb100 / 100.0) / (sd ** 2), 5) if sd > 0 else None
    return out


ECOS = {"Ö1 (70LP/20TAG/10GTO)": (4, 1, 0), "Ö2 (20LP/60TAG/20GTO)": (1, 3, 1), "Ö3 (0LP/30TAG/70GTO)": (0, 2, 3)}


def main():
    hands = int(sys.argv[1]) if len(sys.argv) > 1 else 40000
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 11
    res = {"config": {"hands_per_eco": hands, "seed": seed, "smooth_k": SMOOTH_K, "eq_iters": EQ_ITERS,
                      "spec_asked_hands": 1000000, "note": "N reduced for feasibility; SE reported"},
           "pd_profile": PD, "B": {}, "C": {}, "D": {}}
    print(f"=== B: ecology test ({hands} hands each) ===", flush=True)
    for name, mix in ECOS.items():
        r = run_eco(PrinceClone, mix, hands, seed, name)
        res["B"][name] = r
        print(f"  P_D  {name}: {r['bb100']:+.1f} +/- {r['se']:.1f} bb/100 | SD {r['sd_per_hand_bb']} | MDD {r['max_drawdown_bb']}", flush=True)
    print("=== C: inverse operator (forced reset after trigger) ===", flush=True)
    for name, mix in ECOS.items():
        r = run_eco(PrinceReset, mix, hands, seed, name)
        res["C"][name] = r
        d = r["bb100"] - res["B"][name]["bb100"]
        res["C"][name]["delta_vs_PD"] = round(d, 1)
        print(f"  P_D' {name}: {r['bb100']:+.1f} +/- {r['se']:.1f} | delta {d:+.1f} bb/100 | MDD {r['max_drawdown_bb']}", flush=True)
    print("=== D: niche map + counter ===", flush=True)
    grid = {}
    for mix, lbl in (((5, 0, 0), "100LP"), ((3, 2, 0), "60LP/40TAG"), ((0, 5, 0), "100TAG"),
                     ((0, 0, 5), "100GTOapx"), ((2, 2, 1), "40LP/40TAG/20GTO")):
        r = run_eco(PrinceClone, mix, max(8000, hands // 4), seed, lbl)
        grid[lbl] = {"bb100": r["bb100"], "se": r["se"], "n": r["n_hands"]}
        print(f"  {lbl}: {r['bb100']:+.1f} +/- {r['se']:.1f}", flush=True)
    res["D"]["niche_grid"] = grid
    json.dump(res, open(r"C:\Users\hampe\Desktop\PokerB\data\research_sweep\prince_ecology.json", "w", encoding="utf-8"), indent=1)
    print("saved -> data/research_sweep/prince_ecology.json")


if __name__ == "__main__":
    main()


def calibrate(hero_cls, mix, hands, seed):
    """HONESTY GATE: does the clone actually reproduce the measured profile? Measure the clone's own
    VPIP/PFR/WTSD/AF/overbet-share in simulation and compare to the PD targets."""
    rng = random.Random(seed)
    hero = hero_cls(random.Random(seed + 1))
    villains = []
    for cls, k in ((LP, mix[0]), (TAG, mix[1]), (GTOapx, mix[2])):
        villains += [cls(random.Random(seed + 200 + i)) for i in range(k)]
    agents = [hero] + villains
    t = Table([f"p{i}" for i in range(len(agents))], starting_stack=10000, sb=50, bb=100, seed=seed)
    st = {"hands": 0, "vpip": 0, "pfr": 0, "sd": 0, "sawflop": 0, "bets": 0, "calls": 0, "ob": 0, "bet_tot": 0}
    for _ in range(hands):
        t.start_hand(); st["hands"] += 1
        vp = pf = sawf = False
        g = 0
        while not t.hand_over and g < 400:
            g += 1
            la = t.legal_actions(); i = la.get("to_act")
            if i is None: break
            obs = t.obs_for(i)
            try: a, amt = agents[i].decide(obs)
            except Exception: a, amt = ("check", None) if obs["can_check"] else ("fold", None)
            if a in ("bet", "raise") and (amt is None or not obs["can_raise"]):
                a, amt = ("call", None) if obs["can_call"] else ("check", None)
            if a == "check" and not obs["can_check"]: a = "call" if obs["can_call"] else "fold"
            if a == "fold" and obs["to_call"] == 0: a = "check"
            if i == 0:
                if obs["street"] == "preflop":
                    if a in ("call", "bet", "raise"): vp = True
                    if a in ("bet", "raise"): pf = True
                else:
                    sawf = True
                    if a in ("bet", "raise"):
                        st["bets"] += 1; st["bet_tot"] += 1
                        if amt and obs["pot"] > 0 and (amt - obs["cur_bet"]) > 1.5 * obs["pot"]: st["ob"] += 1
                    elif a == "call": st["calls"] += 1
            try: t.act(a, amt)
            except Exception:
                try: t.act("fold" if la.get("to_call", 0) > 0 else "check", None)
                except Exception: break
        if vp: st["vpip"] += 1
        if pf: st["pfr"] += 1
        if sawf: st["sawflop"] += 1
        if (t.result or {}).get("shown") and 0 in ((t.result or {}).get("shown") or {}): st["sd"] += 1
    return {"n": st["hands"], "vpip": round(st["vpip"] / st["hands"], 3), "pfr": round(st["pfr"] / st["hands"], 3),
            "wtsd": round(st["sd"] / max(1, st["sawflop"]), 3),
            "af": round(st["bets"] / max(1, st["calls"]), 2),
            "overbet_share": round(st["ob"] / max(1, st["bet_tot"]), 3),
            "targets": {"vpip": PD["vpip"], "pfr": PD["pfr"], "wtsd": PD["wtsd"], "af": PD["af"], "overbet_share": PD["overbet_share"]}}
