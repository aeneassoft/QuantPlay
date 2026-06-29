"""The decision engine: a Heads-Up NLHE bot blending a GTO baseline with exploits.

decide(state) -> {action, amount, rationale}. The rationale is a structured explanation
(spot, hand strength, equity, pot odds, MDF, opponent read, reasoning) that powers both
the transparency panel and the Claude-backed coach.
"""
from __future__ import annotations

import os
import random

from pokerbot.engine.cards import hand_class
from pokerbot.engine.equity import equity_vs_range, equity_vs_weighted_range
from pokerbot.engine.evaluator import best_five_name, evaluate
from pokerbot.strategy import blueprint
from pokerbot.strategy import preflop_blueprint as pbp
from pokerbot.strategy import postflop as pf
from pokerbot.strategy import advisor as pf_advisor
from pokerbot.strategy import exploit_engine as pf_ee
from pokerbot.strategy.opp_model import OppModel, node_key
from pokerbot.strategy import preflop_strength as ps
from pokerbot.strategy import ranges as R
from pokerbot.strategy.opponent import OpponentModel
from pokerbot.strategy.postflop import LearnedFoldModel, PriorFoldModel
import json
from pokerbot import config

EQUITY_ITERS = 1500

_TEX_FREQS = None


def _texture_freq(board, role):
    """Per-texture GTO bet frequency from the solver cache (knowledge_base/postflop/texture_freqs.json,
    built by extraction/texture_freqs.py). role = 'OOP' (donk node) or 'IP' (c-bet node)."""
    global _TEX_FREQS
    if _TEX_FREQS is None:
        try:
            _TEX_FREQS = json.loads(
                (config.KNOWLEDGE_DIR / "postflop" / "texture_freqs.json").read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            _TEX_FREQS = {}
    t = pf.classify_board(board)
    order = "23456789TJQKA"
    if t.get("paired"):
        tex = "paired"
    elif t.get("monotone"):
        tex = "monotone"
    elif t.get("connected"):
        tex = "connected"
    elif board and max(order.index(c[0]) for c in board) >= order.index("T"):
        tex = "high"
    else:
        tex = "low"
    d = _TEX_FREQS.get(role, {})
    return d.get(tex, d.get("ALL", 0.22 if role == "OOP" else 0.74))


class PokerBot:
    def __init__(self, hero_idx: int, seed: int | None = None, exploit: bool = True):
        self.hero_idx = hero_idx
        self.rng = random.Random(seed)
        self.exploit = exploit
        self.opp = OpponentModel()
        self.fold_model = None   # set to a LearnedFoldModel to enable fold-equity-optimal sizing
        self.value_raise_eq = 0.72   # facing-bet value-raise threshold (A/B-able via the duplicate gate)
        self.range_cbet = True       # flop-c-bet medium hands at the solver-calibrated texture freq (A/B hook)
        self.oop_donk_freq = 0.5     # OOP-caller donk-frequency cap (was over-donking 52% vs GTO ~20%; A/B hook, NOTES.md)
        self.opp_model = OppModel()  # EXPLOIT-PRIMARY (#49): Dirichlet per-node villain response model
        self._river_keys: list = []  # river-bet node keys this hand (recorded for post-hand observation)
        # ---- floor-ablation A/B toggles (default True = current behavior; flipped only by floor_ablate.py) ----
        self.use_turn_advisor = True   # gate the #41 turn advisor (regression suspect vs near-GTO)
        self.use_river_blocker = True  # gate the #40 river-blocker nudge (bluffcatch + bluff-selection)
        self.use_fe_sizing = True      # fold-model value sizing (False -> fixed 0.66-pot; isolates NOTES leak #2)
        self.use_mdf_shade = True      # MDF bluffiness shade (False -> call_thresh = pot-odds req; NOTES leak #3)
        self.use_river_advisor = True  # WS2 river advisor (False -> #40 river heuristic; ablation/A-B hook)
        self.use_commit_cap = os.environ.get("POKERB_COMMIT_CAP", "0") == "1"   # anti-spew: FOLD a big stack commitment with a weak made hand (env-gated, default OFF = baseline byte-identical)
        self.commit_frac = 0.45        # "big commitment" = call > this fraction of the effective stack
        self.commit_eq = float(os.environ.get("POKERB_COMMIT_EQ", "0.70"))   # below this equity, a big commitment is a light stack-off -> fold (env-tunable)
        self.deep_jam_pct = 0.985      # preflop deep (>14bb) jam/stack-off threshold. Was 0.94 (top 6%) = the
                                       # -385/-527 all-in spew. The Nash consult (gpt-5.5) is explicit: at 200bb fold
                                       # QQ/AK to a full jam (QQ vs KK+ ~18% eq, needs 44% -> -103bb) -> stack off ~AA/KK
                                       # only (top ~1.5%). A/B-able; measured in the next GTOW run.
        self.use_deepcfr = False       # use the from-scratch HUNL Deep CFR policy net as the decision core
        self._deepcfr_policy = None    # lazy-loaded LoadedPolicy
        # WS3 unify: bounded, PREDICTION-GATED off-tree size probing (port of the AdaptiveExploiter idea). Maps
        # under-sampled larger river sizes ONLY when an over-fold is already observed at a sampled size, so it
        # never blind-probes a non-folder. Worst-case cost reserved vs a session budget -> can never run away.
        self.use_probe = True
        self._probe_budget_bb = 120.0
        self._probe_spent_bb = 0.0
        self._probe_freq = 0.15
        self.use_resolver = False    # MVP#2 P1: real-time RIVER re-solving (opt-in; the GTO Wizard A/B enables it)
        self.use_turn_resolver = False  # MVP#2 P2: real-time TURN re-solving (turn->river to terminal; opt-in)
        self.use_defense_advisor = True  # MVP C2: facing-bet DEFENSE advisor (the #1-leak fix; flop coverage, gated)
        # ---- KEYSTONE: the action-consistent per-combo range tracker as the FLOOR's villain-range source ----
        # The floor's equity_vs_range used _villain_range/_narrow (top-X%-by-board-strength, bluffs/draws DROPPED)
        # = barely better than uniform at predicting the solver's true range (GATE A3-FLOOR: L1 0.756 vs 0.995
        # noop). The Bayesian tracker is +42% closer to solver truth (L1 0.437) -> use it for the floor's villain
        # equity when its confidence clears CONF_THRESHOLD, else fall back to _narrow (o3-safe). A/B-able.
        self.use_range_tracker = True
        # ---- near-Nash PREFLOP BLUEPRINT (extraction/preflop_solve.py; the X-ray's #1 fix: preflop = 87% of -72) ----
        self.use_blueprint = True      # replace the "standard-dumb" preflop heuristic with the solved GTO mix
        self.bp_deep_min_bb = 140.0    # blueprint is solved at 200bb -> only fire when genuinely deep (GTOW = 200bb)
        self.bp_jam_min_pct = 0.90     # value-only clamp: don't 5bet/jam-bluff below top-10% (checkdown is blocker-blind)

    # ====================================================================== API
    def decide(self, state: dict) -> dict:
        la = state["legal"]
        if la.get("to_act") != self.hero_idx:
            raise ValueError("Not the bot's turn.")
        hero = state["players"][self.hero_idx]
        hole = hero["hole"]
        self._cur_street = state["street"]            # for _raise_to's POKERB_ONTREE postflop size-snap
        if self.use_deepcfr:                          # our from-scratch HUNL Deep CFR net IS the strategy
            return self._deepcfr(state, hole)
        if state["street"] == "preflop":
            self._river_keys = []                    # new hand -> reset the river-bet log
            return self._preflop(state, hole)
        return self._postflop(state, hole)

    def _deepcfr(self, state: dict, hole: list[str]) -> dict:
        """Decide via the from-scratch HUNL Deep CFR policy net (deep_cfr_hunl) — the self-play GTO core.
        Reconstructs the trainer's infoset features (verified identical) -> samples the net's mixed fcpa
        strategy -> maps to the engine's (action, amount)."""
        from pokerbot.strategy import deepcfr_adapter as dca
        if self._deepcfr_policy is None:
            from pokerbot import config
            self._deepcfr_policy = dca.LoadedPolicy(
                str(config.KNOWLEDGE_DIR / "postflop" / "deepcfr_hunl.pt"), device="cpu")
        la = state["legal"]
        feat, _p = dca.live_features(state, self.hero_idx)
        legal = dca.legal_fcpa(la)
        probs = self._deepcfr_policy.strategy(feat, legal)
        acts = list(probs)
        a = self.rng.choices(acts, weights=[probs[x] for x in acts])[0]      # sample the mixed GTO strategy
        to_call = la.get("to_call", 0)
        r = {"phase": "deepcfr", "hand": " ".join(hole), "street": state["street"],
             "probs": {dca.dc._ANAME[k]: round(v, 3) for k, v in probs.items()}}
        if a == dca.dc.FOLD:
            return self._mk("fold", None, r, f"Deep-CFR net: fold ({r['probs']}).")
        if a == dca.dc.CALL:
            if la.get("can_check"):
                return self._mk("check", None, r, f"Deep-CFR net: check ({r['probs']}).")
            return self._mk("call", None, r, f"Deep-CFR net: call ({r['probs']}).")
        if a == dca.dc.ALLIN:
            return self._mk("raise", self._raise_to(la, 10 ** 9), r, f"Deep-CFR net: all-in ({r['probs']}).")
        target = state.get("current_bet", 0) + state["pot"] + to_call       # POT = pot-size bet/raise
        return self._mk("raise" if to_call > 0 else "bet", self._raise_to(la, target), r,
                        f"Deep-CFR net: pot-bet ({r['probs']}).")

    # ====================================================================== preflop
    def _preflop(self, state: dict, hole: list[str]) -> dict:
        la = state["legal"]
        bb = state["bb"]
        hc = hand_class(*hole)
        pct = ps.percentile(hc)
        eff_bb = self._eff_stack(state) / bb
        is_sb = self.hero_idx == state["button"]
        raises = self._preflop_raises(state)
        to_call = la["to_call"]
        r = {"phase": "preflop", "hand": " ".join(hole), "hand_class": hc,
             "percentile": round(pct, 2), "eff_stack_bb": round(eff_bb, 1),
             "position": "SB/BTN" if is_sb else "BB"}

        # ---- short-stack push/fold ----
        if eff_bb <= 14:
            return self._pushfold(state, hole, hc, pct, eff_bb, is_sb, raises, r)

        # ---- near-Nash preflop blueprint (deep/200bb; the solved GTO mix replaces the heuristic cascade) ----
        if self.use_blueprint:
            bp = self._preflop_blueprint(state, hole, hc, pct, eff_bb, is_sb, raises, r)
            if bp is not None:
                return bp

        # ---- SB first-in (unopened) ----
        if is_sb and raises == 0 and to_call <= bb:
            if pct >= (1 - R.SB_OPEN_FRAC):
                size = self._raise_to(la, round(2.5 * bb))
                return self._mk("raise" if not la["is_bet"] else "raise", size, r,
                                f"Open-raise: {hc} is in the SB opening range (top "
                                f"{int(R.SB_OPEN_FRAC*100)}%). Standard 2.5bb open.")
            return self._mk("fold", None, r,
                            f"Fold: {hc} is below the SB opening threshold even HU.")

        # ---- BB option after SB limp ----
        if (not is_sb) and raises == 0 and la["can_check"]:
            if pct >= 0.80:
                size = self._raise_to(la, round(4.0 * bb))
                return self._mk("raise", size, r,
                                f"Raise the limp: {hc} is strong enough to isolate and build a pot in position-disadvantaged BB.")
            if pct >= 0.55 and self.rng.random() < 0.4:
                size = self._raise_to(la, round(3.5 * bb))
                return self._mk("raise", size, r, f"Raise the limp as a semi-bluff with {hc}.")
            return self._mk("check", None, r, "Check the option and see a flop.")

        # ---- BB facing SB open ----
        if (not is_sb) and raises == 1 and to_call > 0:
            return self._bb_vs_open(state, hole, hc, pct, r)

        # ---- SB facing BB 3bet ----
        if is_sb and raises == 2 and to_call > 0:
            return self._vs_3bet(state, hole, hc, pct, r)

        # ---- deeper re-raise war: value-or-fold ----
        return self._deep_reraise(state, hole, hc, pct, r)

    def _preflop_blueprint(self, state, hole, hc, pct, eff_bb, is_sb, raises, r):
        """Solved GTO preflop action from the 200bb blueprint (extraction/preflop_solve.py), or None to fall
        through to the heuristic. Gated to deep stacks; a value-only jam clamp guards the checkdown solve's
        blocker-blind bluff-jams (it would 5bet/jam 76s for 200bb = spew). See NOTES.md."""
        if eff_bb < self.bp_deep_min_bb or not pbp.available():
            return None
        la = state["legal"]
        bb = state["bb"]
        # robust "facing a shove" detection: a villain's all-in stack can read 0 (and some adapters coerce 0->start),
        # so also treat "owe chips but cannot raise" as all-in. Else a 200bb jam mis-maps to 5BET (not JAMSB) and QQ
        # CALLS it instead of folding = the -15 spew. Only affects the raises==4 (5BET vs JAMSB) branch.
        villain_allin = (state["players"][1 - self.hero_idx]["all_in"]
                         or (la.get("to_call", 0) > 0 and not la.get("can_raise", False)))
        node = pbp.node_for_state(is_sb, raises, la.get("can_check", False), villain_allin)
        if node is None:
            return None
        picked = pbp.pick(node, hc, self.rng)
        if picked is None:
            return None
        action, dist = picked
        if action in ("jam", "5bet") and node in ("4BET", "5BET") and pct < self.bp_jam_min_pct:
            safe = {a: p for a, p in dist.items() if a not in ("jam", "5bet")}     # value-only: drop the bluff-jam
            tot = sum(safe.values())
            action = self.rng.choices(list(safe), weights=list(safe.values()))[0] if tot > 1e-9 else "fold"
            r["blueprint_clamp"] = True
        r["blueprint"] = {"node": node, "picked": action, "pct": round(pct, 3),
                          "dist": {k: round(v, 3) for k, v in dist.items()}}
        to_call = la["to_call"]
        desc = f"Preflop blueprint [{node}] {hc}: {action} (GTO mix {r['blueprint']['dist']})."
        if action == "fold":
            if to_call <= 0 and la.get("can_check"):
                return self._mk("check", None, r, desc)
            return self._mk("fold", None, r, desc)
        if action == "check":
            return self._mk("check", None, r, desc)
        if action in ("limp", "call"):
            if to_call <= 0 and la.get("can_check"):
                return self._mk("check", None, r, desc)
            return self._mk("call", None, r, desc)
        if action == "jam":
            return self._mk("allin", None, r, desc)
        size_bb = pbp.SIZES_BB.get(action)                  # sized raise: open/iso/3bet/4bet/5bet
        if size_bb is None or not la.get("can_raise"):
            if to_call <= 0 and la.get("can_check"):
                return self._mk("check", None, r, desc + " [raise unavailable]")
            return self._mk("call", None, r, desc + " [raise unavailable]")
        return self._mk("raise", self._raise_to(la, round(size_bb * bb)), r, desc)

    def _pushfold(self, state, hole, hc, pct, eff_bb, is_sb, raises, r):
        la = state["legal"]
        r["mode"] = "push/fold"
        bp = blueprint.pushfold(eff_bb, hc) if blueprint.available() else None
        villain_allin = state["players"][1 - self.hero_idx]["all_in"]

        # facing an all-in -> call or fold
        if villain_allin or (raises >= 1 and la["to_call"] > 0 and not la["can_raise"]):
            if bp is not None and villain_allin:
                r["cfr"] = bp
                if self.rng.random() < bp["call"]:
                    return self._mk("call", None, r, f"Call the shove: CFR push/fold blueprint calls "
                                    f"{hc} {bp['call']:.0%} at {eff_bb:.0f}bb.")
                return self._mk("fold", None, r, f"Fold to the shove: CFR calls {hc} only "
                                f"{bp['call']:.0%} at {eff_bb:.0f}bb.")
            shove_range = ps.range_top(R.push_fraction(eff_bb))
            combos = R.combos_for_classes(shove_range, hole + state["board"])
            eq = equity_vs_range(hole, combos, state["board"], iters=EQUITY_ITERS, rng=self.rng)
            req = la["to_call"] / (state["pot"] + la["to_call"])
            r.update({"equity_vs_shove": round(eq, 3), "required_equity": round(req, 3)})
            if eq >= req:
                return self._mk("call", None, r, f"Call the shove: {eq:.0%} equity beats the "
                                f"{req:.0%} the pot lays.")
            return self._mk("fold", None, r, f"Fold: {eq:.0%} equity < {req:.0%} needed.")

        # SB first-in -> jam or fold
        if is_sb and raises == 0:
            if bp is not None:
                r["cfr"] = bp
                if self.rng.random() < bp["jam"]:
                    return self._mk("allin", None, r, f"Open-shove {hc} ({eff_bb:.0f}bb): CFR push/fold "
                                    f"blueprint jams this {bp['jam']:.0%}.")
                return self._mk("fold", None, r, f"Fold {hc}: CFR push/fold jams only {bp['jam']:.0%} "
                                f"at {eff_bb:.0f}bb.")
            if pct >= (1 - R.push_fraction(eff_bb)):
                return self._mk("allin", None, r, f"Open-shove {hc} ({eff_bb:.0f}bb): in the push range.")
            return self._mk("fold", None, r, f"Fold {hc}: below the {eff_bb:.0f}bb shove threshold.")

        # BB facing a non-all-in raise at short depth -> jam strong, else fold
        if pct >= (1 - R.call_shove_fraction(eff_bb)):
            if la["can_raise"]:
                return self._mk("allin", None, r, f"Re-jam {hc}: strong enough to get it in {eff_bb:.0f}bb deep.")
            return self._mk("call", None, r, f"Call off {hc} at {eff_bb:.0f}bb.")
        return self._mk("fold", None, r, f"Fold {hc} at {eff_bb:.0f}bb.")

    def _bb_vs_open(self, state, hole, hc, pct, r):
        la = state["legal"]
        bb = state["bb"]
        sb_open_combos = R.combos_for_classes(R.sb_open(), hole + state["board"])
        eq = equity_vs_range(hole, sb_open_combos, [], iters=EQUITY_ITERS, rng=self.rng)
        req = la["to_call"] / (state["pot"] + la["to_call"])
        realize = 0.82  # BB is OOP postflop
        r.update({"vs_range": "SB open", "equity": round(eq, 3),
                  "required_equity": round(req, 3), "realization": realize})
        fold_to_bet = self.opp.fold_to_bet_freq()
        conf = self.opp.confidence() if self.exploit else 0.0

        # value 3bet
        if pct >= (1 - R.BB_3BET_VALUE_FRAC):
            size = self._raise_to(la, round(state["current_bet"] * 3.2))
            return self._mk("raise", size, r, f"3-bet for value: {hc} is in the top "
                            f"{int(R.BB_3BET_VALUE_FRAC*100)}% — re-raise to punish the wide SB open.")
        # polarized 3bet bluff (more if villain folds a lot; aggregate fold-to-bet is our best proxy
        # here — we don't track a separate fold-to-3bet stat, so this slightly under-bluffs vs a folder)
        bluff_p = 0.30 + conf * (fold_to_bet - 0.5)
        if hc in R.bluff_band() and self.rng.random() < max(0.0, bluff_p):
            size = self._raise_to(la, round(state["current_bet"] * 3.2))
            return self._mk("raise", size, r, f"3-bet bluff with {hc}: polarized re-raise; "
                            f"villain folds to bets ~{fold_to_bet:.0%}.")
        # call by pot odds / equity realization
        if eq * realize >= req or pct >= (1 - R.BB_DEFEND_FRAC):
            return self._mk("call", None, r, f"Call: {eq:.0%} equity (×{realize} realization OOP) "
                            f"defends vs the {req:.0%} the pot lays. BB defends wide vs a small open.")
        return self._mk("fold", None, r, f"Fold {hc}: too weak to continue OOP vs the open.")

    def _vs_3bet(self, state, hole, hc, pct, r):
        la = state["legal"]
        tb_combos = R.combos_for_classes(ps.range_top(0.18), hole + state["board"])
        eq = equity_vs_range(hole, tb_combos, [], iters=EQUITY_ITERS, rng=self.rng)
        req = la["to_call"] / (state["pot"] + la["to_call"])
        r.update({"vs_range": "BB 3bet", "equity": round(eq, 3), "required_equity": round(req, 3)})
        if pct >= (1 - R.SB_4BET_VALUE_FRAC):
            size = self._raise_to(la, round(state["current_bet"] * 2.3))
            return self._mk("raise", size, r, f"4-bet for value with {hc} (top "
                            f"{int(R.SB_4BET_VALUE_FRAC*100)}%).")
        if hc in R.bluff_band() and self.rng.random() < 0.22:
            size = self._raise_to(la, round(state["current_bet"] * 2.3))
            return self._mk("raise", size, r, f"4-bet bluff with {hc} (blocker-driven).")
        if eq * 0.95 >= req or pct >= (1 - R.SB_CALL_3BET_FRAC):
            return self._mk("call", None, r, f"Call the 3-bet: {eq:.0%} equity in position justifies "
                            f"continuing vs the {req:.0%} needed.")
        return self._mk("fold", None, r, f"Fold {hc} vs the 3-bet.")

    def _deep_reraise(self, state, hole, hc, pct, r):
        la = state["legal"]
        if pct >= self.deep_jam_pct:   # deep-stack discipline: only stack off 100bb+ at 200bb with a true premium
            if la["can_raise"]:
                return self._mk("allin", None, r, f"Get it in: {hc} is a premium (top "
                                f"{int((1-self.deep_jam_pct)*100)}%) in a re-raised pot.")
            return self._mk("call", None, r, f"Call off with {hc} (premium).")
        if la["can_check"]:
            return self._mk("check", None, r, "Check.")
        return self._mk("fold", None, r, f"Fold {hc} in an escalating re-raise war.")

    # ====================================================================== postflop
    def _postflop(self, state: dict, hole: list[str]) -> dict:
        la = state["legal"]
        board = state["board"]
        pot = state["pot"]
        to_call = la["to_call"]
        hero = state["players"][self.hero_idx]
        hero_ip = self.hero_idx == state["button"]
        hero_committed = hero["committed_street"]
        hero_stack = hero["stack"]
        made = best_five_name(board, hole)
        street = state["street"]

        if street == "river" and self.use_resolver:        # MVP#2 P1: real-time river re-solve (situation-specific GTO)
            rr = self._river_resolve(state, hole, board, pot, la, hero, hero_stack)
            if rr is not None:
                return rr
        if street == "turn" and self.use_turn_resolver:     # MVP#2 P2: real-time turn re-solve (turn->river terminal)
            tr = self._turn_resolve(state, hole, board, pot, la, hero, hero_stack)
            if tr is not None:
                return tr

        vrange = self._villain_range(state)
        aggression = self._villain_postflop_aggression(state)
        kept = self._narrow(vrange, board, hole, aggression)
        # KEYSTONE: prefer the action-consistent per-combo TRACKED villain range (GATE A3-FLOOR: +42% closer to
        # the solver's true range than _narrow, which strips bluffs/draws); fall back to _narrow when the tracker's
        # confidence is below CONF_THRESHOLD (o3-safe: never trust a collapsed/mostly-legality-only reconstruction).
        vw = self._tracked_villain_range(state, board, hole) if self.use_range_tracker else None
        if vw:
            eq = equity_vs_weighted_range(hole, vw, board, iters=EQUITY_ITERS, rng=self.rng)
            n_villain = len(vw)
        else:
            eq = equity_vs_range(hole, kept, board, iters=EQUITY_ITERS, rng=self.rng)
            n_villain = len(kept)
        tex = pf.classify_board(board)

        fold_to_bet = self.opp.fold_to_bet_freq()
        conf = self.opp.confidence() if self.exploit else 0.0
        learned = isinstance(self.fold_model, LearnedFoldModel)
        fm = self.fold_model or PriorFoldModel(fold_to_bet, conf)
        bluff_base = max(0.0, min(0.85, 0.18 + conf * (fold_to_bet - 0.5) * 1.2))
        r = {"phase": "postflop", "street": street, "hand": " ".join(hole),
             "made_hand": made, "board": " ".join(board), "equity": round(eq, 3),
             "villain_combos": n_villain, "position": "IP" if hero_ip else "OOP",
             "texture": [k for k, v in tex.items() if v],
             "fold_model": "learned" if learned else "prior",
             "opponent": self.opp.summary() if self.exploit else None}

        if to_call > 0:  # ---- facing a bet/raise ----
            req = to_call / (pot + to_call)
            # ---- DEFENSE ADVISOR (MVP C2): solver (fold/call/raise) per hand = the #1-leak fix. Gated to its
            # coverage (flop, where it was trained); samples the GTO mix; raise keeps the anti-spew commitment cap.
            if self.use_defense_advisor and street == "flop" and pf_advisor.defense_available():  # flop-only: river defense MEASURED -14 vs GTO Wizard (reverted)
                size_faced = to_call / max(1.0, pot - to_call)        # bet as a fraction of the pot it hit
                pd = pf_advisor.p_defense(hole, board, "IP" if hero_ip else "OOP", size_faced, street=street)
                if pd is not None:
                    pf_, pc_, pr_ = pd
                    r.update({"defense_advisor": [round(pf_, 2), round(pc_, 2), round(pr_, 2)],
                              "size_faced": round(size_faced, 2), "required_equity": round(req, 3)})
                    u = self.rng.random()
                    if u < pf_ and eq < 0.80:     # follow the GTO fold — but NEVER fold a near-nut hand (advisor over-fold safety)
                        return self._mk("fold", None, r, f"Defense advisor: GTO fold {pf_:.0%} vs {size_faced:.0%}-pot. {made}.")
                    if u >= pf_ + pc_ and la["can_raise"]:            # raise (value / semi-bluff); anti-spew cap
                        eff_d = min(hero_stack, state["players"][1 - self.hero_idx].get("stack", hero_stack))
                        vr = self._raise_to(la, state["current_bet"] + round(0.8 * (pot + to_call)))
                        if eq >= 0.82 or (vr - hero_committed) <= 0.5 * eff_d:
                            return self._mk("raise", vr, r, f"Defense advisor: GTO raise {pr_:.0%} ({made}).")
                        # would over-commit a weak hand -> downgrade to call (safe-by-construction)
                    return self._mk("call", None, r, f"Defense advisor: GTO call {pc_:.0%} vs {size_faced:.0%}-pot. {made}.")
            mdf = 1 - req
            # MDF-driven defense: call threshold = pot-odds equilibrium SHADED by villain bluffiness
            # (rho_bluff proxy = bet/raise frequency): under-bluffer -> fold more; bluffy -> defend wider.
            aggr_v = self.opp.aggression_freq()
            shade = max(-0.12, min(0.12, (0.5 - aggr_v) * conf * 0.5)) if self.use_mdf_shade else 0.0
            call_thresh = max(0.0, req + shade)
            if street == "river" and self.use_river_blocker:  # blocker-aware bluffcatch (#40): block value -> call wider
                rblk = self._river_blocker_signal(hole, board, vrange)
                call_thresh = max(0.0, call_thresh - 0.06 * rblk)
                r["river_blocker"] = round(rblk, 2)
            r.update({"required_equity": round(req, 3), "mdf": round(mdf, 2), "facing_bet": to_call,
                      "call_threshold": round(call_thresh, 3), "villain_aggr": round(aggr_v, 2)})
            eff = min(hero_stack, state["players"][1 - self.hero_idx].get("stack", hero_stack))
            # Value-raise, but DON'T stack off (commit >half the effective stack) on merely-good equity vs
            # a betting = strong range: that is the dominated-top-pair spew. Need near-nut eq to commit deep.
            if eq >= self.value_raise_eq and la["can_raise"]:
                vr = self._raise_to(la, state["current_bet"] + round(0.8 * (pot + to_call)))
                if eq >= 0.82 or (vr - hero_committed) <= 0.5 * eff:
                    return self._mk("raise", vr, r, f"Raise for value: {eq:.0%} equity vs "
                                    f"{len(kept)} combos — build the pot with {made}.")
                # strong-ish but not near-nut and a big commitment -> just call, keep the pot controlled
            # ANTI-SPEW calling commit-cap: the CALL path (unlike the raise path above) had NO commitment guard,
            # so it called off any amount once eq >= the MDF threshold. But eq is computed vs the history-free
            # range, which over-rates a bare made hand facing a big bet -> the big-pot light stack-off (the gtow
            # river -130 bb / -100bb spew). Don't commit a big chunk of stack without a strong hand; fold instead.
            if self.use_commit_cap and to_call > self.commit_frac * eff and eq < self.commit_eq:
                return self._mk("fold", None, r, f"Anti-spew commit-cap: won't call {to_call} (>{self.commit_frac:.0%} "
                                f"eff stack) at {eq:.0%} equity — light stack-off vs a big bet. {made}.")
            if eq >= call_thresh:
                return self._mk("call", None, r, f"Call: {eq:.0%} >= MDF-defense threshold {call_thresh:.0%} "
                                f"(pot odds {req:.0%}, shaded for villain bluffiness {aggr_v:.0%}, MDF {mdf:.0%}). {made}.")
            # A bluff-RAISE is a pure gamble that villain folds. The FLOOR (no confident read) NEVER does it
            # — that unbounded raise-bluff was the -900 bb/100 stack-off leak. Fire ONLY with a confident
            # over-fold read (learned model + conf) AND a non-committing size.
            if la["can_raise"] and eq < 0.33 and learned and conf >= 0.5:
                sfrac = 0.6                                   # raise-bluff sized at 60% of the post-call pot
                s = round(sfrac * (pot + to_call))            # chips; risk/pot-won = s/(pot+to_call) = sfrac
                br = self._raise_to(la, state["current_bet"] + s)
                Fr = fm.fold(street, sfrac)
                if pf.ev_bluff(sfrac, Fr) > 0.10 and (br - hero_committed) <= 0.35 * eff:
                    return self._mk("raise", br, r, f"Bluff-raise: confident over-fold read "
                                    f"(F={Fr:.0%}, conf {conf:.0%}), non-committing size.")
            return self._mk("fold", None, r, f"Fold: {eq:.0%} < threshold {call_thresh:.0%} "
                            f"(floor: no stack-off raise-bluff without a read).")

        # ---- we can bet (checked to / first to act) ----
        if not la["can_raise"]:
            return self._mk("check", None, r, "Check (cannot bet).")

        cb_s = pf.cbet_policy(board, hero_ip)[1] if street == "flop" else None  # texture c-bet size (flop)

        # EXPLOIT-PRIMARY river (#49): when the opponent model has CONFIDENT data at this node, play the max-EV
        # river action gated by an LCB (safe-exploit). Cold-start / thin data -> None -> falls through to the floor.
        if street == "river" and self.exploit:
            ex = self._river_exploit(state, hole, board, eq, pot, la, hero_committed, hero_stack, fm, r)
            if ex is not None:
                return ex

        # GTO-floor ADVISOR (#39): on the FLOP, the trained solver-advisor picks bet-vs-check PER HAND (frequency
        # AND selection, from blocker/potential features) -> matches the solver's per-hand mix. Size from the
        # heuristic. Falls back to the heuristic floor below for turn/river or if the advisor is unavailable.
        # The bounded exploit overlay still applies on top of this floor.
        if street == "flop" and pf_advisor.available():
            role = "IP" if self._has_initiative(state) else "OOP"
            pb = pf_advisor.p_bet(hole, board, role)
            if pb is not None:
                r["advisor_pbet"] = round(pb, 2)
                if self.rng.random() < pb:
                    if eq >= pf.VALUE_EQ:
                        to, _ = self._value_to(pot, fm, street, hero_committed, hero_stack, eq)
                        size = self._raise_to(la, to or la["raise_min"])
                    else:
                        size = self._raise_to(la, hero_committed + round((cb_s or 0.5) * pot) or la["raise_min"])
                    return self._mk("bet" if la["is_bet"] else "raise", size, r,
                                    f"Floor advisor bet ({pb:.0%} GTO, {role}, {eq:.0%}). {made}.")
                return self._mk("check", None, r, f"Floor advisor check ({pb:.0%} GTO, {role}). {made}.")

        # GTO-floor ADVISOR TURN (#41): same per-hand bet-vs-check on the TURN (barrel if IP / lead if OOP),
        # from the turn-trained solver-advisor. Bluff size = 75% pot (the solver's turn size); value via the
        # heuristic value-sizer. Falls through to the heuristic for the river or if the turn advisor is absent.
        if street == "turn" and self.use_turn_advisor and pf_advisor.available("turn"):
            role = "IP" if self._has_initiative(state) else "OOP"
            pb = pf_advisor.p_bet(hole, board, role, "turn")
            if pb is not None:
                r["advisor_pbet_turn"] = round(pb, 2)
                if self.rng.random() < pb:
                    if eq >= pf.VALUE_EQ:
                        to, _ = self._value_to(pot, fm, street, hero_committed, hero_stack, eq)
                        size = self._raise_to(la, to or la["raise_min"])
                    else:
                        size = self._raise_to(la, hero_committed + round(0.75 * pot) or la["raise_min"])
                    return self._mk("bet" if la["is_bet"] else "raise", size, r,
                                    f"Turn advisor bet ({pb:.0%} GTO, {role}, {eq:.0%}). {made}.")
                return self._mk("check", None, r, f"Turn advisor check ({pb:.0%} GTO, {role}). {made}.")

        # GTO-floor ADVISOR RIVER (WS2): per-hand bet-vs-check on the RIVER from the river-trained solver advisor
        # (+51% vs the freq baseline). OOP=lead / IP=bet-after-check. Bluff size 66% pot (value via the fe-sizer).
        # Runs AFTER the exploit-primary river engine (so the exploit fires first) and supersedes the #40 bluff-
        # SELECTION heuristic when present; the #40 bluffcatch (facing a bet) is a disjoint node and stays active.
        if street == "river" and self.use_river_advisor and pf_advisor.available("river"):
            role = "IP" if self._has_initiative(state) else "OOP"
            pb = pf_advisor.p_bet(hole, board, role, "river", pot_type=self._pot_type(state))  # line-aware (POKERB_RIVER_LA)
            if pb is not None:
                if eq >= pf.RIVER_VALUE_FLOOR_EQ:          # value-floor: a clearly-strong final-card hand bets for
                    pb = max(pb, pf.RIVER_VALUE_BET_FREQ)  # value (no protection concern) -> don't under-bet it
                r["advisor_pbet_river"] = round(pb, 2)
                if self.rng.random() < pb:
                    if eq >= pf.VALUE_EQ:
                        to, _ = self._value_to(pot, fm, street, hero_committed, hero_stack, eq)
                        size = self._raise_to(la, to or la["raise_min"])
                    else:
                        size = self._raise_to(la, hero_committed + round(0.66 * pot) or la["raise_min"])
                    return self._mk("bet" if la["is_bet"] else "raise", size, r,
                                    f"River advisor bet ({pb:.0%} GTO, {role}, {eq:.0%}). {made}.")
                return self._mk("check", None, r, f"River advisor check ({pb:.0%} GTO, {role}). {made}.")

        # OOP as the caller (no initiative): GTO mostly CHECKS to the aggressor (check-raise/check-call) and
        # donks only the strong part of range, capped. We were OVER-DONKING (52% vs GTO ~20%) by value-betting
        # every strong hand here. Donk only value, frequency-capped; everything else checks (no air spew-donk).
        # Exact per-texture donk frequencies are a deferred refinement (NOTES.md).
        if street == "flop" and not self._has_initiative(state):
            donk_rate = min(1.0, self.oop_donk_freq * 4.0 * _texture_freq(board, "OOP"))  # per-texture GTO donk freq
            if eq >= pf.VALUE_EQ and self.rng.random() < donk_rate:
                to, _ = self._value_to(pot, fm, street, hero_committed, hero_stack, eq)
                return self._mk("bet" if la["is_bet"] else "raise", self._raise_to(la, to or la["raise_min"]),
                                r, f"Donk for value OOP ({eq:.0%}), capped frequency. {made}.")
            return self._mk("check", None, r, f"Check to the aggressor OOP ({eq:.0%}, {made}).")

        if eq >= pf.VALUE_EQ:   # value: size to get paid the most (e_call-aware)
            to, sf = self._value_to(pot, fm, street, hero_committed, hero_stack, eq)
            size = self._raise_to(la, to or la["raise_min"])
            return self._mk("bet" if la["is_bet"] else "raise", size, r,
                            f"Value bet {sf:.0%} pot ({eq:.0%} equity): size maximizes chips paid off. {made}.")

        if eq <= pf.BLUFF_EQ:   # bluff
            if learned:         # THE EDGE: pick the fold-equity-optimal size from real data
                to, ev, sf = pf.pick_bluff_size(pot, fm, street, hero_committed, hero_stack)
                if ev > 0.03 and to is not None:
                    Fs = fm.fold(street, min(sf, 3.0))
                    size = self._raise_to(la, to)
                    return self._mk("bet" if la["is_bet"] else "raise", size, r,
                                    f"Bluff {sf:.0%} pot: learned F={Fs:.0%} > breakeven "
                                    f"{sf/(1+sf):.0%} → +EV (edge). ({eq:.0%}, {made}).")
                return self._mk("check", None, r, f"Check: no +EV bluff size in the data ({eq:.0%}).")
            # FLOOR (no learned read): on the flop WITH initiative, range-c-bet air at the calibrated
            # texture frequency + the SMALL cbet_policy size -- a cheap GTO range-bet (first to act, NOT a
            # facing-bet raise), so it closes the under-c-bet gap without the stack-off spew the anti-spew fix killed.
            if self.range_cbet and street == "flop" and self._has_initiative(state):
                f_cbet, size_frac = pf.cbet_policy(board, hero_ip)
                if self.rng.random() < f_cbet:
                    size = self._raise_to(la, hero_committed + round(size_frac * pot) or la["raise_min"])
                    return self._mk("bet" if la["is_bet"] else "raise", size, r,
                                    f"Range c-bet air ({int(f_cbet*100)}% texture freq, small size, {eq:.0%}). {made}.")
                return self._mk("check", None, r, f"Check back air ({eq:.0%}, {made}).")
            # turn/river or no initiative: controlled-frequency bluff at a modest size (no spew). On the RIVER,
            # bias the SELECTION toward blockers (#40) at ~constant frequency: bluff hands that remove villain's
            # value/continues -> strictly better fold equity, no extra spew.
            bf = bluff_base
            if street == "river" and self.use_river_blocker:
                rblk = self._river_blocker_signal(hole, board, vrange)
                bf = max(0.0, min(0.95, bluff_base * (1.0 + 0.6 * rblk)))
            if self.rng.random() < bf:
                size = self._raise_to(la, round((cb_s or 0.6) * pot) or la["raise_min"])
                return self._mk("bet" if la["is_bet"] else "raise", size, r,
                                f"Bluff ~60% pot ({eq:.0%}): controlled frequency"
                                f"{', blocker-selected' if street == 'river' else ''}, fold equity present.")
            return self._mk("check", None, r, f"Check: give up ({eq:.0%}, {made}).")

        # medium equity: on the FLOP with initiative, range-c-bet at the solver-CALIBRATED texture frequency
        # (the f_cbet that sixmax + GTOBaseline already use). The live bot previously only borrowed the c-bet
        # SIZE and range-bet medium hands via a crude "IP + dynamic + 50%" rule -> it under-c-bet vs solver GTO.
        if self.range_cbet and street == "flop" and self._has_initiative(state):
            f_cbet, size_frac = pf.cbet_policy(board, hero_ip)
            if self.rng.random() < f_cbet:
                size = self._raise_to(la, hero_committed + round(size_frac * pot) or la["raise_min"])
                return self._mk("bet" if la["is_bet"] else "raise", size, r,
                                f"Range c-bet ({int(f_cbet*100)}% texture freq, {eq:.0%}) — solver-calibrated. {made}.")
            return self._mk("check", None, r, f"Check back this share ({eq:.0%}, {made}).")
        # turn/river or no initiative: thin value IP on dynamic boards, else pot control
        if hero_ip and tex["dynamic"] and self.rng.random() < 0.5:
            size = self._raise_to(la, hero_committed + round((cb_s or 0.5) * pot) or la["raise_min"])
            return self._mk("bet" if la["is_bet"] else "raise", size, r,
                            f"Thin bet/protection IP ({eq:.0%}) on a "
                            f"{','.join(r['texture']) or 'dry'} board.")
        return self._mk("check", None, r, f"Check for pot control ({eq:.0%}, {made}).")

    def _has_initiative(self, state: dict) -> bool:
        """True if hero was the last preflop raiser (holds postflop c-bet initiative). Mirrors the
        gto_baseline / sixmax initiative derivation from public history (pre-flop actions before the deal)."""
        pre = []
        for h in state.get("history", []):
            if h.get("action") == "deal":
                break
            pre.append(h)
        pfr = [h["player"] for h in pre if h.get("action") in ("raise", "bet", "allin")]
        return bool(pfr) and pfr[-1] == self.hero_idx

    # ====================================================================== range estimation
    def _villain_range(self, state: dict) -> set[str]:
        v = 1 - self.hero_idx
        villain_is_sb = v == state["button"]
        raises = self._preflop_raises(state)
        if raises >= 3:
            return ps.range_top(0.10)
        if raises == 2:
            return ps.range_top(0.20)            # someone 3-bet
        if raises == 1:
            return R.sb_open() if villain_is_sb else R.bb_defend()
        return ps.range_top(0.85)                # limped pot: wide

    def _villain_postflop_aggression(self, state: dict) -> int:
        v = 1 - self.hero_idx
        agg = 0
        for h in state["history"]:
            if h.get("street") in ("flop", "turn", "river") and h.get("player") == v \
                    and h.get("action") in ("bet", "raise"):
                agg += 1
        return agg

    def _narrow(self, classes: set[str], board, hole, aggression: int):
        dead = list(hole) + list(board)
        combos = R.combos_for_classes(classes, dead)
        if len(board) < 3 or not combos:
            return combos
        keep_frac = {0: 0.92, 1: 0.60, 2: 0.38}.get(aggression, 0.30)
        ranked = sorted(combos, key=lambda c: evaluate(board, list(c)))  # lower=better
        n = max(1, int(len(ranked) * keep_frac))
        return ranked[:n]

    def _tracked_villain_range(self, state, board, hole):
        """KEYSTONE: the action-consistent per-combo Bayesian tracked villain range as {combo: weight} for the
        floor's equity calc, or None when the tracker's confidence < CONF_THRESHOLD (-> caller falls back to the
        _narrow heuristic, o3-safe: never trust a collapsed / mostly-legality-only reconstruction). Board+hole
        dead-card-filtered. Any malformed state -> None so the floor is never worse than before."""
        if len(board) < 3:
            return None
        try:
            from pokerbot.strategy.range_tracker import RangeTracker, CONF_THRESHOLD
            v = 1 - self.hero_idx
            t = RangeTracker().build(state)
            if t.confidence(v) < CONF_THRESHOLD:
                return None
            dead = set(hole) | set(board)
            vw = {c: w for c, w in t.range.get(v, {}).items() if w > 0 and not (set(c) & dead)}
            return vw or None
        except Exception:  # noqa: BLE001
            return None

    def _river_blocker_signal(self, hole, board, vrange) -> float:
        """River blocker signal in [-1,1]: how much MORE hero's two cards block villain's VALUE combos than
        villain's WEAK combos. + => hero removes value -> good to BLUFF (fewer continues) and to BLUFFCATCH
        (villain's bets skew bluffier). Grounded in blocker theory; magnitudes deliberately small and the bluff
        side is frequency-preserving (biases selection, not amount). River-solver calibration deferred (NOTES.md)."""
        combos = R.combos_for_classes(vrange, list(board))   # exclude board only -> hero-blocking is measurable
        if not combos:
            return 0.0
        hole_s = set(hole)
        val_t = val_b = air_t = air_b = 0
        for c in combos:
            strong = evaluate(board, list(c)) <= 3500        # ~two-pair+ / strong top pair = value-bet range
            blocked = bool(hole_s & set(c))
            if strong:
                val_t += 1; val_b += int(blocked)
            else:
                air_t += 1; air_b += int(blocked)
        vf = (val_b / val_t) if val_t else 0.0
        af = (air_b / air_t) if air_t else 0.0
        return max(-1.0, min(1.0, vf - af))

    def _river_resolve(self, state, hole, board, pot, la, hero, hero_stack):
        """MVP#2 P1: solve the ACTUAL river public state (line-aware tracked ranges) + sample our GTO action;
        returns a _mk action or None (-> caller plays the floor). Situation-specific GTO for the river leak."""
        if not la.get("can_raise") and not (la.get("to_call", 0) > 0 and la.get("can_call")):
            return None
        from pokerbot.strategy import resolver as _rsv
        from pokerbot.strategy.range_tracker import weighted_ranges, CONF_THRESHOLD
        vill = state["players"][1 - self.hero_idx]
        h_cs = hero.get("committed_street", 0) or 0
        v_cs = vill.get("committed_street", 0) or 0
        start_pot = max(2.0, pot - h_cs - v_cs)                 # pot at the START of the river (pre river-betting)
        eff = min(hero_stack + h_cs, (vill.get("stack", hero_stack) or hero_stack) + v_cs)
        # P0 v2: line-aware per-combo TRACKED ranges (not the preflop-only stub). CONFIDENCE GATE (consult):
        # a low-confidence reconstruction is distrusted -> return None -> the floor plays (never a bad solve).
        oop_str, ip_str, rconf = weighted_ranges(state)
        if rconf < CONF_THRESHOLD or not oop_str or not ip_str:
            return None
        res = _rsv.river_resolve(state, hole, board, start_pot, eff, oop_str, ip_str, la, self.rng)
        if res is None:
            return None
        action, amount = res
        if action in ("bet", "raise") and amount is not None:
            amount = self._raise_to(la, amount, snap=False)   # resolver's GTO size is exact -> never re-snap (#3)
        r = {"phase": "postflop", "street": "river", "hand": " ".join(hole), "range_conf": round(rconf, 2),
             "made_hand": best_five_name(board, hole), "board": " ".join(board), "resolver": True}
        return self._mk(action, amount, r, "MVP#2 river resolver: real-time GTO re-solve of the public state.")

    def _turn_resolve(self, state, hole, board, pot, la, hero, hero_stack):
        """MVP#2 P2: solve the ACTUAL turn public state (turn->river to terminal, line-aware tracked ranges) +
        sample our GTO turn action; returns a _mk action or None (-> caller plays the floor). Situation-specific
        GTO for the turn barrel/check + check-raise + facing-bet leak (the #2 EV bleed per the consults)."""
        if not la.get("can_raise") and not (la.get("to_call", 0) > 0 and la.get("can_call")):
            return None
        from pokerbot.strategy import resolver as _rsv
        from pokerbot.strategy.range_tracker import weighted_ranges, CONF_THRESHOLD
        vill = state["players"][1 - self.hero_idx]
        h_cs = hero.get("committed_street", 0) or 0
        v_cs = vill.get("committed_street", 0) or 0
        start_pot = max(2.0, pot - h_cs - v_cs)                 # pot at the START of the turn (pre turn-betting)
        eff = min(hero_stack + h_cs, (vill.get("stack", hero_stack) or hero_stack) + v_cs)
        # P0 v2: line-aware per-combo TRACKED ranges + the same confidence gate as the river resolver.
        oop_str, ip_str, rconf = weighted_ranges(state)
        if rconf < CONF_THRESHOLD or not oop_str or not ip_str:
            return None
        res = _rsv.turn_resolve(state, hole, board, start_pot, eff, oop_str, ip_str, la, self.rng)
        if res is None:
            return None
        action, amount = res
        if action in ("bet", "raise") and amount is not None:
            amount = self._raise_to(la, amount, snap=False)   # resolver's GTO size is exact -> never re-snap (#3)
        r = {"phase": "postflop", "street": "turn", "hand": " ".join(hole), "range_conf": round(rconf, 2),
             "made_hand": best_five_name(board, hole), "board": " ".join(board), "resolver": True}
        return self._mk(action, amount, r, "MVP#2 turn resolver: real-time GTO re-solve (turn->river) of the public state.")

    def _board_class(self, board) -> str:
        t = pf.classify_board(board)
        if t.get("paired"):
            return "paired"
        if t.get("monotone"):
            return "mono"
        if t.get("connected") or t.get("flush_draw"):
            return "wet"
        return "dry"

    def _river_floor_kind(self, hole, board, eq, role, fm, pot, hero_committed, hero_stack):
        """The floor's intended river action (kind, size_frac) = the exploit engine's BASELINE. Advisor-driven
        (modal bet-vs-check at the value/bluff size) when available, else the heuristic; a CHECK baseline for
        marginal/air so the exploit can still ADD fold-equity bets where the floor gives up (without ever
        overriding a good floor bet with a worse size -- safe-by-construction)."""
        if eq >= pf.RIVER_VALUE_FLOOR_EQ:                  # value-floor: a clearly-strong final-card hand is a value
            _, sf = self._value_to(pot, fm, "river", hero_committed, hero_stack, eq)   # bet (exploit may upsize on top)
            return "bet", (sf or 0.66)
        if self.use_river_advisor and pf_advisor.available("river"):
            pb = pf_advisor.p_bet(hole, board, role, "river")
            if pb is None or pb < 0.5:
                return "check", 0.0
            if eq >= pf.VALUE_EQ:
                _, sf = self._value_to(pot, fm, "river", hero_committed, hero_stack, eq)
                return "bet", (sf or 0.66)
            return "bet", 0.66
        if eq >= pf.VALUE_EQ:                              # heuristic floor: value bets; marginal/air baseline = check
            _, sf = self._value_to(pot, fm, "river", hero_committed, hero_stack, eq)
            return "bet", (sf or 0.66)
        return "check", 0.0

    def _river_exploit(self, state, hole, board, eq, pot, la, hero_committed, hero_stack, fm, r):
        """EXPLOIT-PRIMARY river (#49): consider DEVIATING from the floor's river action to a higher-EV size vs
        the Dirichlet opponent model, LCB-gated. The BASELINE is the floor's OWN action (advisor bet at its size,
        or check) -- NOT a bare check -- so the exploit can never override a good floor bet with a worse one. It
        still upsizes (e.g. the overbet cliff) when that beats the floor action vs a confident over-folder, and
        adds bets where the floor checks. Cold-start / thin data -> wide LCB -> None -> floor. Returns a _mk bet
        or None."""
        if not la.get("can_raise"):
            return None
        role = "IP" if self.hero_idx == state["button"] else "OOP"
        bclass = self._board_class(board)
        fkind, fsf = self._river_floor_kind(hole, board, eq, role, fm, pot, hero_committed, hero_stack)
        if fkind == "bet":                                 # baseline candidate = the floor's bet at its own size
            kf = node_key("river", role, "all", bclass, fsf)
            respf, nf = self.opp_model.posterior(kf)
            cands, keys = [("bet", fsf, respf, nf)], [kf]
        else:                                              # baseline = check (the floor checks this hand)
            cands, keys = [("check", 0.0, None, 1e9)], [None]
        for sf in (0.5, 0.66, 1.0, 2.0):                   # candidate deviation sizes (incl. the overbet cliff)
            if fkind == "bet" and abs(sf - fsf) < 0.02:
                continue                                   # the floor size is already the baseline candidate
            k = node_key("river", role, "all", bclass, sf)
            resp, n = self.opp_model.posterior(k)
            cands.append(("bet", sf, resp, n))
            keys.append(k)
        idx, mode, lam, evs = pf_ee.choose_river(cands, 0, eq, pot)
        if mode != "floor" and idx != 0 and self.rng.random() < lam:
            sf = cands[idx][1]
            self._river_keys.append(keys[idx])
            r["exploit_river"] = {"size": sf, "mode": mode, "lam": round(lam, 2), "vs_floor": fkind,
                                  "model_n": round(cands[idx][3]), "ev": round(evs[idx], 1)}
            size = self._raise_to(la, hero_committed + round(sf * pot) or la["raise_min"])
            return self._mk("bet" if la["is_bet"] else "raise", size, r,
                            f"Exploit-primary river bet {sf:.0%} pot vs floor-{fkind} "
                            f"(lam {lam:.2f}, model n={cands[idx][3]:.0f}, eq {eq:.0%}).")
        # the LCB gate declined -> consider a bounded, prediction-gated off-tree probe (map the fold-curve further out)
        return self._river_probe(fkind, eq, role, bclass, pot, la, hero_committed, state, r)

    def _river_probe(self, fkind, eq, role, bclass, pot, la, hero_committed, state, r):
        """Bounded, PREDICTION-GATED off-tree probe (WS3 unify): when the floor gives up an air hand AND the
        opponent model ALREADY shows an over-fold at a sampled size, occasionally bet an UNDER-SAMPLED LARGER size
        to map the fold-curve further out (discover a size-cliff the LCB gate would otherwise never explore --
        the cold-start deadlock: can't learn a size without betting it). Three safety rails: prediction gate (never
        blind-probes a non-folder) + size cap + a session risk budget (worst-case cost reserved up front -> can
        never run away). The probe's response is fed back via observe_hand_end so the model sharpens."""
        if not self.use_probe or fkind != "check" or eq > pf.BLUFF_EQ:
            return None
        if self.rng.random() >= self._probe_freq:
            return None
        # PREDICTION GATE: require an observed over-fold (fold prob > pot-odds breakeven) at some SAMPLED size,
        # so we never blind-probe a non-folder.
        overfold_seen = False
        for ssf in (0.5, 0.66, 1.0):
            resp, n = self.opp_model.posterior(node_key("river", role, "all", bclass, ssf))
            if n >= 3 and resp[0] > ssf / (1.0 + ssf) + 0.05:
                overfold_seen = True
                break
        if not overfold_seen:
            return None
        bb = state.get("bb", 100) or 100
        pot_bb = pot / bb
        for psf in (2.0, 1.0):                                  # map further-out sizes (incl. the overbet cliff)
            k = node_key("river", role, "all", bclass, psf)
            _, n = self.opp_model.posterior(k)
            if n >= 6:                                          # already sampled enough -> nothing to learn
                continue
            cost_bb = psf * max(0.0, pot_bb)                    # worst case: lose the whole probe bet
            if cost_bb > max(0.0, self._probe_budget_bb - self._probe_spent_bb):
                continue
            self._probe_spent_bb += cost_bb
            self._river_keys.append(k)
            r["river_probe"] = {"size": psf, "n": round(n), "spent_bb": round(self._probe_spent_bb)}
            return self._mk("bet" if la["is_bet"] else "raise",
                            self._raise_to(la, hero_committed + round(psf * pot) or la["raise_min"]), r,
                            f"Off-tree river probe {psf:.0%} pot (over-fold predicted; map the cliff; n={n:.0f}).")
        return None

    # ====================================================================== helpers
    def _eff_stack(self, state: dict) -> int:
        return min(p["stack"] + p["committed_total"] for p in state["players"])

    def _preflop_raises(self, state: dict) -> int:
        return sum(1 for h in state["history"]
                   if h.get("street") == "preflop" and h.get("action") in ("bet", "raise"))

    def _pot_type(self, state: dict) -> str | None:
        """Pot type from the preflop raise count (SRP=1, 3bet=2, 4bet=3); None for limped/5bet+ -> advisor floor.
        Feeds the line-aware river advisor (pf_advisor.p_bet pot_type=...) so it value-bets per the correct range."""
        return {1: "srp", 2: "3bet", 3: "4bet"}.get(self._preflop_raises(state))

    def _raise_to(self, la: dict, desired: int, snap: bool = True) -> int:
        lo, hi = la["raise_min"], la["raise_max"]
        if lo is None:
            return hi
        # GTO-mode (POKERB_ONTREE): snap a postflop BET onto GTOW's discrete size tree (off-tree exploit-sizing
        # was ~the SRP UNSOLVED driver). Bets only (is_bet), never preflop (_cur_street). NEVER a jam/huge overbet:
        # the desired<=2*pot guard fixes the PROVEN bug where a 24x-pot jam (desired<hi because the resolver's eff
        # != raise_max) got snapped to 1.25x pot. snap=False lets a caller (the GTO resolver) keep its exact size.
        if (snap and pf.ONTREE and getattr(self, "_cur_street", "preflop") in ("flop", "turn", "river")
                and la.get("is_bet") and la.get("pot", 0) > 0 and int(desired) < hi
                and int(desired) <= 2.0 * la["pot"]):
            desired = pf.snap_to_tree(int(desired), la["pot"])
        return max(lo, min(int(desired), hi))

    def _value_to(self, pot, fm, street, hero_committed, hero_stack, eq):
        """Value-bet target (chips) + size_frac. fe-sizing = e_call-aware pick_value_size, unless toggled
        off (floor-ablate) -> fixed 0.66-pot. Isolates whether the adaptive value sizing is a leak vs near-GTO."""
        if self.use_fe_sizing:
            to, _, sf = pf.pick_value_size(pot, fm, street, hero_committed, hero_stack, eq)
            return to, sf
        return hero_committed + round(0.66 * pot), 0.66

    def _mk(self, action: str, amount, rationale: dict, reasoning: str) -> dict:
        rationale = dict(rationale)
        rationale["reasoning"] = reasoning
        return {"action": action, "amount": amount, "rationale": rationale}

    # ====================================================================== learning
    def observe_opponent(self, street: str, action: str, facing_bet: bool) -> None:
        self.opp.record(street, action, facing_bet)

    def observe_hand_end(self, final_state=None) -> None:
        self.opp.end_hand()
        # LIVE-LEARNING (#49): feed villain's response to each of OUR river bets into the Dirichlet model so it
        # sharpens per-node during play (vs clinging to the thin seed). Defensive: any mismatch -> skip (the
        # mismatch-count guard + try/except mean a parse error can never corrupt the model).
        if final_state is None or not self._river_keys:
            return
        try:
            hist = final_state.get("history", []) or []
            v = 1 - self.hero_idx
            responses = []
            for i, h in enumerate(hist):
                if h.get("street") == "river" and h.get("player") == self.hero_idx and h.get("action") in ("bet", "raise"):
                    resp = None
                    for hj in hist[i + 1:]:
                        if hj.get("player") == v:
                            a = hj.get("action")
                            resp = "fold" if a == "fold" else ("raise" if a == "raise" else "call")
                            break
                    responses.append(resp)
            if len(responses) == len(self._river_keys):       # only pair when counts match (avoid mispairing)
                for key, resp in zip(self._river_keys, responses):
                    if key and resp:
                        self.opp_model.observe(key, resp)
        except Exception:  # noqa: BLE001
            pass
