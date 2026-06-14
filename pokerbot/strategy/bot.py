"""The decision engine: a Heads-Up NLHE bot blending a GTO baseline with exploits.

decide(state) -> {action, amount, rationale}. The rationale is a structured explanation
(spot, hand strength, equity, pot odds, MDF, opponent read, reasoning) that powers both
the transparency panel and the Claude-backed coach.
"""
from __future__ import annotations

import random

from pokerbot.engine.cards import hand_class
from pokerbot.engine.equity import equity_vs_range
from pokerbot.engine.evaluator import best_five_name, evaluate
from pokerbot.strategy import blueprint
from pokerbot.strategy import postflop as pf
from pokerbot.strategy import preflop_strength as ps
from pokerbot.strategy import ranges as R
from pokerbot.strategy.opponent import OpponentModel
from pokerbot.strategy.postflop import LearnedFoldModel, PriorFoldModel

EQUITY_ITERS = 1500


class PokerBot:
    def __init__(self, hero_idx: int, seed: int | None = None, exploit: bool = True):
        self.hero_idx = hero_idx
        self.rng = random.Random(seed)
        self.exploit = exploit
        self.opp = OpponentModel()
        self.fold_model = None   # set to a LearnedFoldModel to enable fold-equity-optimal sizing

    # ====================================================================== API
    def decide(self, state: dict) -> dict:
        la = state["legal"]
        if la.get("to_act") != self.hero_idx:
            raise ValueError("Not the bot's turn.")
        hero = state["players"][self.hero_idx]
        hole = hero["hole"]
        if state["street"] == "preflop":
            return self._preflop(state, hole)
        return self._postflop(state, hole)

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
        fold_to_3bet = self.opp.fold_to_bet_freq()
        conf = self.opp.confidence() if self.exploit else 0.0

        # value 3bet
        if pct >= (1 - R.BB_3BET_VALUE_FRAC):
            size = self._raise_to(la, round(state["current_bet"] * 3.2))
            return self._mk("raise", size, r, f"3-bet for value: {hc} is in the top "
                            f"{int(R.BB_3BET_VALUE_FRAC*100)}% — re-raise to punish the wide SB open.")
        # polarized 3bet bluff (more if villain folds to 3bets a lot)
        bluff_p = 0.30 + conf * (fold_to_3bet - 0.5)
        if hc in R.bluff_band() and self.rng.random() < max(0.0, bluff_p):
            size = self._raise_to(la, round(state["current_bet"] * 3.2))
            return self._mk("raise", size, r, f"3-bet bluff with {hc}: polarized re-raise; "
                            f"villain folds to bets ~{fold_to_3bet:.0%}.")
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
        if pct >= 0.94:
            if la["can_raise"]:
                return self._mk("allin", None, r, f"Get it in: {hc} is a premium in a re-raised pot.")
            return self._mk("call", None, r, f"Call off with {hc}.")
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

        vrange = self._villain_range(state)
        aggression = self._villain_postflop_aggression(state)
        kept = self._narrow(vrange, board, hole, aggression)
        eq = equity_vs_range(hole, kept, board, iters=EQUITY_ITERS, rng=self.rng)
        tex = pf.classify_board(board)

        fold_to_bet = self.opp.fold_to_bet_freq()
        conf = self.opp.confidence() if self.exploit else 0.0
        learned = isinstance(self.fold_model, LearnedFoldModel)
        fm = self.fold_model or PriorFoldModel(fold_to_bet, conf)
        bluff_base = max(0.0, min(0.85, 0.18 + conf * (fold_to_bet - 0.5) * 1.2))
        r = {"phase": "postflop", "street": street, "hand": " ".join(hole),
             "made_hand": made, "board": " ".join(board), "equity": round(eq, 3),
             "villain_combos": len(kept), "position": "IP" if hero_ip else "OOP",
             "texture": [k for k, v in tex.items() if v],
             "fold_model": "learned" if learned else "prior",
             "opponent": self.opp.summary() if self.exploit else None}

        if to_call > 0:  # ---- facing a bet/raise ----
            req = to_call / (pot + to_call)
            mdf = 1 - req
            # MDF-driven defense: call threshold = pot-odds equilibrium SHADED by villain bluffiness
            # (rho_bluff proxy = bet/raise frequency): under-bluffer -> fold more; bluffy -> defend wider.
            aggr_v = self.opp.aggression_freq()
            shade = max(-0.12, min(0.12, (0.5 - aggr_v) * conf * 0.5))
            call_thresh = max(0.0, req + shade)
            r.update({"required_equity": round(req, 3), "mdf": round(mdf, 2), "facing_bet": to_call,
                      "call_threshold": round(call_thresh, 3), "villain_aggr": round(aggr_v, 2)})
            if eq >= 0.72 and la["can_raise"]:
                size = self._raise_to(la, state["current_bet"] + round(0.8 * (pot + to_call)))
                return self._mk("raise", size, r, f"Raise for value: {eq:.0%} equity vs "
                                f"{len(kept)} combos — build the pot with {made}.")
            if eq >= call_thresh:
                return self._mk("call", None, r, f"Call: {eq:.0%} >= MDF-defense threshold {call_thresh:.0%} "
                                f"(pot odds {req:.0%}, shaded for villain bluffiness {aggr_v:.0%}, MDF {mdf:.0%}). {made}.")
            if la["can_raise"] and eq < 0.33:   # bluff-raise only if the fold model makes it +EV
                s = round(0.9 * (pot + to_call))
                Fr = fm.fold(street, s / max(pot, 1))
                if pf.ev_bluff(s / max(pot, 1), Fr) > 0.06:
                    size = self._raise_to(la, state["current_bet"] + s)
                    return self._mk("raise", size, r, f"Bluff-raise: fold model F={Fr:.0%} at this "
                                    f"size beats breakeven → +EV semi-bluff.")
            return self._mk("fold", None, r, f"Fold: {eq:.0%} < MDF-defense threshold {call_thresh:.0%}.")

        # ---- we can bet (checked to / first to act) ----
        if not la["can_raise"]:
            return self._mk("check", None, r, "Check (cannot bet).")

        cb_s = pf.cbet_policy(board, hero_ip)[1] if street == "flop" else None  # texture c-bet size (flop)

        if eq >= pf.VALUE_EQ:   # value: size to get paid the most (e_call-aware)
            to, _, sf = pf.pick_value_size(pot, fm, street, hero_committed, hero_stack, eq)
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
            # unknown opponent: controlled-frequency bluff at a modest size (no spew)
            if self.rng.random() < bluff_base:
                size = self._raise_to(la, round((cb_s or 0.6) * pot) or la["raise_min"])
                return self._mk("bet" if la["is_bet"] else "raise", size, r,
                                f"Bluff ~60% pot ({eq:.0%}): controlled frequency, fold equity present.")
            return self._mk("check", None, r, f"Check: give up ({eq:.0%}, {made}).")

        # medium equity -> thin value IP on dynamic boards, else pot control
        if hero_ip and tex["dynamic"] and self.rng.random() < 0.5:
            size = self._raise_to(la, hero_committed + round((cb_s or 0.5) * pot) or la["raise_min"])
            return self._mk("bet" if la["is_bet"] else "raise", size, r,
                            f"Thin bet/protection IP ({eq:.0%}) on a "
                            f"{','.join(r['texture']) or 'dry'} board.")
        return self._mk("check", None, r, f"Check for pot control ({eq:.0%}, {made}).")

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

    # ====================================================================== helpers
    def _eff_stack(self, state: dict) -> int:
        return min(p["stack"] + p["committed_total"] for p in state["players"])

    def _preflop_raises(self, state: dict) -> int:
        return sum(1 for h in state["history"]
                   if h.get("street") == "preflop" and h.get("action") in ("bet", "raise"))

    def _raise_to(self, la: dict, desired: int) -> int:
        lo, hi = la["raise_min"], la["raise_max"]
        if lo is None:
            return hi
        return max(lo, min(int(desired), hi))

    def _mk(self, action: str, amount, rationale: dict, reasoning: str) -> dict:
        rationale = dict(rationale)
        rationale["reasoning"] = reasoning
        return {"action": action, "amount": amount, "rationale": rationale}

    # ====================================================================== learning
    def observe_opponent(self, street: str, action: str, facing_bet: bool) -> None:
        self.opp.record(street, action, facing_bet)

    def observe_hand_end(self) -> None:
        self.opp.end_hand()
