"""Universal adaptive exploiter (heads-up) + bounded exploratory probing + boolean control knobs.

No bot plays true GTO, so every opponent is an exploitable approximation. This engine starts from a
robust baseline (equity + pot-odds) and applies a SAFE online exploit overlay driven by what it
observes — adapting to ANY opponent, including unseen ones. With no reads it plays the baseline
(break-even-safe); the more it learns, the harder it exploits. Everything is confidence-gated/capped.

Two additions:
  * ProbeController — occasional UNORTHODOX "test moves" to learn the opponent faster. Inspired by the
    an earlier research project's *blind-prediction* method: only probe when a weakness is ALREADY PREDICTED, the
    move is small, and a hard SESSION RISK BUDGET (worst-case reserved per probe) is not exhausted.
    This is the most dangerous feature, so risk is bounded three ways: prediction-gate + size cap +
    budget stop-loss. It can never run away.
  * Knobs — boolean (0/1) "control buttons" for each exploit dimension, so an external pilot (e.g.
    Claude Haiku) can steer the bot by toggling flags.
"""
from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass

from pokerbot import config
from pokerbot.engine.cards import hand_class
from pokerbot.engine.equity import equity_vs_class_range
from pokerbot.strategy import preflop_strength as ps
from pokerbot.strategy.calibration import Calibrator
from pokerbot.strategy.playbook import directive_to_nudge, shared as _shared_playbook
from pokerbot.strategy import unified_exploit

BUCKETS = [(0.0, 0.45, "small"), (0.45, 0.8, "med"), (0.8, 1.3, "pot"), (1.3, 9.0, "over")]


def _bucket(s: float) -> str:
    for lo, hi, name in BUCKETS:
        if lo <= s < hi:
            return name
    return "over"


def _shrink(made: float, n: int, prior: float, k: float = 6.0) -> float:
    return (made + prior * k) / (n + k)


class OpponentProfile:
    """Online, opponent-agnostic model — learns a size-bucketed fold curve + aggression + VPIP."""

    def __init__(self) -> None:
        self.fold = defaultdict(lambda: [0, 0])
        self.faced = 0
        self.folds = 0
        self.could_bet = 0
        self.did_bet = 0
        self.pf = 0
        self.pf_vpip = 0
        self.hands = 0

    def see_decision(self, street: str, la: dict, action: str) -> None:
        to_call, pot = la.get("to_call", 0), la.get("pot", 0)
        if to_call > 0:
            self.faced += 1
            b = _bucket(to_call / max(1, pot - to_call))
            self.fold[b][1] += 1
            if action == "fold":
                self.folds += 1
                self.fold[b][0] += 1
        else:
            self.could_bet += 1
            if action in ("bet", "raise", "allin"):
                self.did_bet += 1
        if street == "preflop":
            self.pf += 1
            if action in ("call", "bet", "raise", "allin"):
                self.pf_vpip += 1

    def end_hand(self) -> None:
        self.hands += 1

    def fold_at(self, s: float) -> float:
        g = _shrink(self.folds, self.faced, 0.5)
        f, n = self.fold[_bucket(s)]
        return _shrink(f, n, g)

    def aggression(self) -> float:
        return _shrink(self.did_bet, self.could_bet, 0.4)

    def vpip(self) -> float:
        return _shrink(self.pf_vpip, self.pf, 0.6)

    def confidence(self) -> float:
        return min(1.0, self.faced / 15.0 + self.could_bet / 15.0)

    def summary(self) -> dict:
        return {"hands": self.hands, "vpip": round(self.vpip(), 2),
                "fold_to_bet": round(_shrink(self.folds, self.faced, 0.5), 2),
                "aggr": round(self.aggression(), 2), "conf": round(self.confidence(), 2)}


@dataclass
class Knobs:
    """Boolean control buttons (0/1). An external pilot can toggle these to steer the bot."""
    exploit_bluff: bool = True       # bluff more when the opponent over-folds
    exploit_value: bool = True       # size value bets up vs sticky opponents
    exploit_bluffcatch: bool = True  # call lighter vs over-bluffers
    probe: bool = True               # allow bounded exploratory test moves


class ProbeController:
    """Bounded, prediction-gated exploratory probing. Three independent safety rails guarantee it
    cannot run away: (1) only fires when a weakness is already PREDICTED, (2) the move is SMALL
    (size cap), (3) a session RISK BUDGET reserves each probe's worst-case loss up front and shuts
    probing off once exhausted — so total probe risk <= budget, period."""

    def __init__(self, budget_bb: float = 40.0, max_frac: float = 0.4, freq: float = 0.12,
                 max_n: int = 12, min_obs: int = 3, seed: int = 0) -> None:
        self.budget = budget_bb
        self.spent = 0.0
        self.max_frac = max_frac
        self.freq = freq
        self.max_n = max_n        # stop probing a size once it has this many samples (learned enough)
        self.min_obs = min_obs    # need a minimal read of the opponent before probing at all
        self.rng = random.Random(seed)
        self.n_probes = 0

    def remaining(self) -> float:
        return max(0.0, self.budget - self.spent)

    def consider(self, pot_bb: float, prof: "OpponentProfile"):
        """Fire only to CONFIRM an already-predicted, UNDER-SAMPLED weakness. Returns a probe bet
        size (fraction of pot) or None; reserves worst-case cost against the budget on fire."""
        if prof.faced + prof.could_bet < self.min_obs:   # need some prior read of the opponent
            return None
        if self.rng.random() >= self.freq:               # measured frequency
            return None
        s = min(self.max_frac, 0.4)                       # small probe bet
        _, n = prof.fold[_bucket(s)]
        if n >= self.max_n:                               # already well-sampled -> nothing to learn
            return None
        pred, alpha = prof.fold_at(s), s / (1 + s)
        if pred <= alpha + 0.05:                          # PREDICTION GATE: must predict an over-fold
            return None
        cost = s * max(0.0, pot_bb)                       # worst case: lose the whole probe bet
        if cost > self.remaining():                       # hard budget stop-loss
            return None
        self.spent += cost
        self.n_probes += 1
        return s


class TwoModelGate:
    """Predator-prey convergence as a confidence gate (method transfer from earlier research): two INDEPENDENT reads —
    Model A from how the opponent RESPONDS to bets (fold curve), Model B from how it takes INITIATIVE
    (aggression / VPIP). An exploit is armed ONLY when both models agree; if they diverge or data is
    thin, that knob stays OFF (robust baseline). Probing is armed to RESOLVE disagreement. This makes
    exploitation fire on real, cross-confirmed structure — not on noise (and is safer vs strong foes)."""

    def __init__(self, conf_min: float = 0.25) -> None:
        self.conf_min = conf_min

    def knobs(self, prof: "OpponentProfile") -> Knobs:
        conf = prof.confidence()
        if conf < self.conf_min:                       # too little data -> baseline + probe to learn
            return Knobs(False, False, False, True)
        fold_small, fold_big = prof.fold_at(0.5), prof.fold_at(0.9)
        aggr, vpip = prof.aggression(), prof.vpip()
        a_small = 0.5 / 1.5
        A_overfold, B_passive = fold_small > a_small + 0.05, aggr < 0.45
        A_sticky, B_loose = fold_big < 0.40, vpip > 0.55
        bluff = A_overfold and B_passive               # both agree: over-folds & won't fight back
        value = A_sticky and B_loose                   # both agree: calls big & enters wide
        bcatch = (fold_small < 0.40) and (aggr > 0.55)  # not foldy & aggressive -> over-bluffs
        disagree = (A_overfold != B_passive) or (A_sticky != B_loose)
        return Knobs(bluff, value, bcatch, probe=disagree or conf < 0.5)


class AdaptiveExploiter:
    VALUE_EQ = 0.62
    BLUFF_EQ = 0.42

    def __init__(self, hero: int, seed: int = 0, iters: int = 300, knobs: Knobs | None = None,
                 probe_budget_bb: float = 40.0, gate: bool = False, depth_aware: bool = False,
                 calibrate: bool = True, calib_name: str = "default", use_playbook: bool = True,
                 use_rules: bool = True) -> None:
        self.hero = hero
        self.rng = random.Random(seed)
        self.iters = iters
        self.prof = OpponentProfile()
        self.knobs = knobs or Knobs()
        self.probe = ProbeController(budget_bb=probe_budget_bb, seed=seed + 1)
        self.gate = gate
        self._gate = TwoModelGate()
        # prediction -> measurement -> calibration loop (self-correcting fold-equity). None-safe: with no
        # data adjust() returns raw, so default behaviour is unchanged. Pass calibrate=False in hot loops.
        self.calib = Calibrator(calib_name) if calibrate else None
        self._pending = None     # (key, predicted_fold) awaiting the opponent's response to OUR bet
        self.playbook = _shared_playbook() if use_playbook else None   # LLM cold-start exploit prior
        self.use_rules = use_rules                                     # unified book-exploit overlay (Phase 1)
        self.live_directive = None      # live LLM strategist proposal (set per session via refresh_llm_exploit)
        self._depth_params = None
        if depth_aware:                          # load RunPod/local stack-depth-tuned parameters
            try:
                import json as _json
                fp = config.KNOWLEDGE_DIR / "exploit" / "stack_depth_params.json"
                self._depth_params = {int(k): v for k, v in
                                      _json.loads(fp.read_text(encoding="utf-8")).get("by_depth", {}).items()}
            except Exception:  # noqa: BLE001
                self._depth_params = None

    def observe_opponent(self, opp_state: dict, action: str) -> None:
        la = opp_state.get("legal") or {}
        self.prof.see_decision(opp_state.get("street", "preflop"), la, action)
        # resolve a pending fold-equity prediction: opponent is now responding to OUR bet
        if self.calib and self._pending and la.get("to_call", 0) > 0:
            key, pred = self._pending
            self.calib.record(key, pred, action == "fold")
            self._pending = None

    def observe_hand_end(self) -> None:
        self.prof.end_hand()
        self._pending = None     # drop any unresolved prediction at the hand boundary

    def set_live_directive(self, directive: dict | None) -> None:
        """Install a live LLM exploit directive (bounded; applied via directive_to_nudge in decide)."""
        self.live_directive = directive if (directive and directive.get("adjust")) else None

    def refresh_llm_exploit(self, coach, context: dict | None = None):
        """Ask the LLM strategist for a fresh exploit directive from the CURRENT reads. Call per SESSION
        (not per hand) — the LLM proposes; bounded directive_to_nudge + caps keep it safe. (INTEGRATION.md)"""
        if not coach or not getattr(coach, "available", False):
            return None
        aggr = self.prof.aggression()
        opp = {"vpip": round(self.prof.vpip() * 100, 1),
               "fold_to_cbet": round(_shrink(self.prof.folds, self.prof.faced, 0.5), 2),
               "af": round(min(4.5, aggr / max(0.05, 1.0 - aggr)), 2), "hands": self.prof.hands}
        d = coach.propose_exploit(opp, context or {})
        self.set_live_directive(d if isinstance(d, dict) else None)
        return self.live_directive

    def decide(self, state: dict):
        la = state["legal"]
        me = state["players"][self.hero]
        hole, board = me["hole"], state["board"]
        pot, to_call = la["pot"], la["to_call"]
        can_check, can_raise, is_bet = la["can_check"], la["can_raise"], la["is_bet"]
        committed, stack = me["committed_street"], me["stack"]
        bb = state["bb"]
        conf = self.prof.confidence()
        if self.gate:                                    # two-model convergence sets the knobs
            self.knobs = self._gate.knobs(self.prof)
        if self._depth_params and bb:                    # stack-depth-tuned params (from training)
            eff = stack / bb
            dp = self._depth_params[min(self._depth_params, key=lambda d: abs(d - eff))]
            self.VALUE_EQ, self.BLUFF_EQ = dp["value_eq"], dp["bluff_eq"]
        agg_label = "bet" if is_bet else "raise"

        # cold-start exploit prior from the LLM playbook: bounded, postflop-only, FADED by live confidence
        # (w_pb -> 0 as reads accumulate). Same channel the live LLM strategist later writes into (INTEGRATION.md).
        pb_nudge, w_pb = {}, max(0.0, 1.0 - conf)
        if self.live_directive:                          # live LLM strategist proposal (data-driven) wins
            pb_nudge, w_pb = directive_to_nudge(self.live_directive), 1.0
        elif self.playbook and conf < 0.6 and board:
            street = {3: "flop", 4: "turn", 5: "river"}.get(len(board))
            if street:
                aggr = self.prof.aggression()
                opp = {"vpip": self.prof.vpip() * 100.0,
                       "fold_to_cbet": _shrink(self.prof.folds, self.prof.faced, 0.5),
                       "af": min(4.5, aggr / max(0.05, 1.0 - aggr))}
                pb_nudge = directive_to_nudge(self.playbook.lookup(
                    opp, street, "bet" if to_call > 0 else "check",
                    stack_bb=(stack / bb if bb else None)))

        # unified book-exploit rules (stat-keyed) -> the SAME channel, weighted by LIVE confidence: they fire
        # on MEASURED stats, so they GROW as the cold-start playbook fades (w_pb = 1 - conf). Bounded + clamped.
        _foldr = _shrink(self.prof.folds, self.prof.faced, 0.5)
        ru_nudge = unified_exploit.nudge(
            {"vpip": self.prof.vpip(), "aggression_freq": self.prof.aggression(),
             "fold_to_bet": _foldr, "fold_to_cbet": _foldr},
            postflop=bool(board)) if self.use_rules else {}

        def _pb(ch, cap=0.15):
            return max(-cap, min(cap, w_pb * pb_nudge.get(ch, 0.0) + conf * ru_nudge.get(ch, 0.0)))

        def raise_to(chips_total):
            lo, hi = la["raise_min"], la["raise_max"]
            if lo is None:
                return hi
            return max(lo, min(int(chips_total), hi))

        base = max(0.12, min(0.92, conf * self.prof.vpip() + (1 - conf) * 0.5))
        if to_call > 0 and pot > to_call:                     # villain put money in -> TIGHTEN his range
            rr = to_call / max(1.0, pot - to_call)            # (anti-spew: don't over-rate eq vs aggression,
            sf = {"flop": 0.9, "turn": 0.78, "river": 0.62}.get(state["street"], 0.85)  # the root over-commit leak)
            base = max(0.07, base * sf * (1 - 0.7 * min(1.5, rr)))
        if board:
            eq = equity_vs_class_range(hole, list(ps.range_top(base)), board, iters=self.iters, rng=self.rng)
        else:
            eq = ps.percentile(hand_class(*hole))

        # ---------- facing a bet ----------
        if to_call > 0:
            req = to_call / (pot + to_call)
            agg = self.prof.aggression()
            delta = max(-0.15, min(0.15, (0.45 - agg) * conf)) if self.knobs.exploit_bluffcatch else 0.0
            # PREFLOP a 4-bet+ means villain's range is premium: raw percentile over-rates marginal hands
            # (it 5-bet/stacked-off 55 as if top-20% = ahead). Need a real premium to re-raise into that.
            big_reraise = (not board) and to_call > 5 * bb
            if eq >= 0.80 and can_raise and not (big_reraise and eq < 0.92):
                eff = min(stack, state["players"][1 - self.hero].get("stack", stack))
                vr = raise_to(committed + to_call + int(0.9 * (pot + to_call)))
                if eq >= 0.88 or (vr - committed) <= 0.5 * eff:   # don't stack off a dominated made hand
                    return agg_label, vr
                # strong-ish but not near-nut + big commitment -> fall through to call (pot control)
            if eq >= req + delta - _pb("foldcatch"):     # overlay: +foldcatch = call wider, -foldcatch = fold more
                return "call", None
            return ("check" if can_check else "fold"), None

        # ---------- we may bet or check ----------
        if not can_raise:
            return "check", None

        if eq >= self.VALUE_EQ - _pb("value"):                  # value (overlay: +value = thinner/more value)
            eff = min(stack, state["players"][1 - self.hero].get("stack", stack))
            raw_fold = self.prof.fold_at(0.8)
            foldiness = self.calib.adjust("fe_value", raw_fold) if self.calib else raw_fold
            s = (0.45 + 0.7 * (1 - foldiness)) if self.knobs.exploit_value else 0.66
            if eq < 0.78:                                        # thin value: no overbet/stack-off (reverse implied odds)
                s = min(s, 0.66)
            amt = raise_to(committed + int(s * pot))
            if eq < 0.78 and (amt - committed) > 0.55 * eff:     # cap thin-value commitment, keep the pot controlled
                amt = raise_to(committed + int(0.55 * eff))
            if self.calib:
                self._pending = ("fe_value", foldiness)
            return agg_label, amt

        if self.knobs.exploit_bluff:                             # bluff (exploit fold curve)
            best_s, best_edge, best_fold = 0.6, -1.0, 0.5
            for s in (0.33, 0.5, 0.75, 1.1):
                raw_fold = self.prof.fold_at(s)
                fold = self.calib.adjust("fe_bluff", raw_fold) if self.calib else raw_fold
                edge = fold - s / (1 + s)
                if edge > best_edge:
                    best_edge, best_s, best_fold = edge, s, fold
            expl_freq = max(0.0, min(0.92, 0.33 + 1.6 * best_edge))
            p_bluff = (1 - conf) * 0.33 + conf * expl_freq
        else:
            best_s, best_fold, p_bluff = 0.6, 0.5, 0.33          # baseline (non-exploit) bluff rate
        if eq <= self.BLUFF_EQ and self.rng.random() < max(0.0, min(0.95, p_bluff + _pb("bluff"))):
            if self.calib:
                self._pending = ("fe_bluff", best_fold)
            return agg_label, raise_to(committed + int(best_s * pot))

        # ---------- bounded exploratory probe (replaces a give-up check) ----------
        if self.knobs.probe and bb:
            ps_frac = self.probe.consider(pot / bb, self.prof)
            if ps_frac:
                return agg_label, raise_to(committed + int(ps_frac * pot))
        return "check", None
