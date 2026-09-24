"""CONSTRUCTED-CATASTROPHE stress suite for the HU engine bot.

Hand-crafted danger spots where the tail could be gigantic; reports where each config still acts
IRRESPONSIBLY (commits >30% of the remaining stack with a hand below the spot's "responsible" bar)
or OVER-NIT (folds the trap/nuts spots -- the opposite failure).

Scenario taxonomy (70 decision spots, 200bb start, hero always idx 0):
  1 barrel  multi-barrel x extreme board (monotone A-high / 4-straight / double-paired) --
            TPWK / bottom-two / overpair-class facing 2nd+3rd barrels (0.5x/1x/1.5x/jam; SRP + 3bet pot)
  2 cfeit   counterfeit rivers: small two pair, river pairs the board / completes 4-flush / 4-straight
  3 xr      check-raised after c-bet: one pair c-bets a wet board, villain raises 3x / jams
  4 pre     preflop jam discipline: KK/QQ/JJ/AK/AQs/TT vs a 200bb 5bet-JAM (the KsKh spew, quantified);
            junk 3bettors (K3o class) facing a 4bet (MUST fold)
  5 sizer   river value-sizer sanity: nuts / second-nut / thin top pair FIRST-IN in a bloated 3bet pot
            (thin value betting >1.5x pot = irresponsible; checking the nuts = over-nit)
  6 trap    trap second act: hero checked a set / top two on the flop, villain barrels huge -- must NOT fold

Configs (one SUBPROCESS each -- env flags are read at pokerbot import time):
  head (no env) / gto (POKERB_GTO_MODE=1) / prince (POKERB_PRINCE=1) /
  prince_aggro (POKERB_PRINCE=1 + POKERB_TRACKER_AGGRO_FULL=1)
Every arm: POKERB_RESOLVER=0 POKERB_TURN_RESOLVER=0 (deterministic, no re-solve latency).
Determinism: a FRESH PokerBot(0, seed=42) per spot -- mixed-strategy nodes are sampled ONCE at that
seed (a single deterministic draw, not a frequency estimate).

Usage (repo root):  PYTHONUTF8=1 python -m research.stress_suite
Writes data/stress/stress_report.json (+ per-config _worker_<cfg>.json artifacts).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "stress"
REPORT_PATH = OUT_DIR / "stress_report.json"

BB = 100                     # chips per big blind (repo convention)
START_STACK = 20000          # 200bb
SEED = 42
STACKOFF_FRAC = 0.30         # committing more than this share of the remaining stack = a stack-off
SIZE_CAP_X_POT = 1.5         # thin value may never bet bigger than this multiple of the pot
WORKER_TIMEOUT_S = 780       # < the 15-min budget, per config

CONFIGS: dict[str, dict[str, str]] = {
    "head": {},
    "gto": {"POKERB_GTO_MODE": "1"},
    "prince": {"POKERB_PRINCE": "1"},
    "prince_aggro": {"POKERB_PRINCE": "1", "POKERB_TRACKER_AGGRO_FULL": "1"},
    # v2.2 gate arm: + the barrel discipline (the MDF-cluster fix candidate; the PRINCE profile carries aggro already)
    "prince_bd": {"POKERB_PRINCE": "1", "POKERB_BARREL_DISCIPLINE": "0.18"},
    "prince_v23": {"POKERB_PRINCE": "1", "POKERB_BARREL_DISCIPLINE": "0.18",
                   "POKERB_TURN_DEF_ADVISOR": "1", "POKERB_TURN_OVERBET": "1"},
    "prince_probe": {"POKERB_PRINCE": "1", "POKERB_TURN_PROBE": "0.35"},
    # v3 bundle = the top-2 over-fold classes (pair-defense flop + river bluffcatch defense); IN the profile
    # since commit 85d2919 -> "prince" now equals "prince_v3", kept as an explicit arm for older comparisons
    "prince_v3": {"POKERB_PRINCE": "1", "POKERB_PAIR_DEFENSE": "0.10", "POKERB_RIVER_DEFENSE": "0.06"},
    # v3.2 = the selection-aware thin-value rebuild (v3.1's flat RIVER_THIN floor was Analyzer-REFUTED 19.76)
    "prince_v32": {"POKERB_PRINCE": "1", "POKERB_RIVER_THIN_SEL": "0.40"},
    # v3.3 = raise-facing-bet range narrowing toward GTOW's mined raise mix (RANK4 stack-off fix)
    "prince_v33": {"POKERB_PRINCE": "1", "POKERB_RAISE_NARROW": "1"},
    # v3.4 = the 9-find AUDIT-FIX bundle (scope guards + covered-stack clamp + phantom sizers + raise-aggro)
    "prince_v34": {"POKERB_PRINCE": "1", "POKERB_AUDIT_FIX": "1"},
    # v3.5 = advisor role by tree position (the training convention; inverts 3bet-pot advisor lookups)
    "prince_v35": {"POKERB_PRINCE": "1", "POKERB_ADVISOR_ROLE_POS": "1"},
    # human-catalog overbet menu (2026-07-06): eCall value-size menu + 2.0x/2.5x arms (selection-aware chooser)
    "prince_obm": {"POKERB_PRINCE": "1", "POKERB_OVERBET_MENU": "1"},
    # L1 purify (2026-07-06): modal action at the 8 big mixing gates (score-experiment arm, GTOW-only)
    "prince_pur": {"POKERB_PRINCE": "1", "POKERB_PURIFY": "1"},
    # danger-map raise-commit discipline (2026-07-06)
    "prince_rcd": {"POKERB_PRINCE": "1", "POKERB_RAISE_COMMIT": "0.07"},
    # v5 candidates (2026-07-06 morning)
    "prince_v5a": {"POKERB_PRINCE": "1", "POKERB_PURIFY2": "1"},
    "prince_v5b": {"POKERB_PRINCE": "1", "POKERB_OVERBET_MENU": "2", "POKERB_BARREL_DISCIPLINE": "0.18"},
    "prince_v5c": {"POKERB_PRINCE": "1", "POKERB_TURN_DEF_ADVISOR": "1"},
}
BASE_ENV = {"POKERB_RESOLVER": "0", "POKERB_TURN_RESOLVER": "0"}
ACTS_CONTINUE = ("call", "bet", "raise", "allin")


# ====================================================================== state builder
class HU:
    """Builds a consistent HU engine state at hero's decision point (hero = idx 0).

    Mirrors pokerbot/engine/game.py semantics: history entries carry the street-cumulative
    bet-to; blinds are absorbed into commitments (no history rows, template-proven);
    raise_min/raise_max are target TOTAL street commitments; pot = all chips committed.
    """

    def __init__(self, hero_hole: list[str], button: int):
        self.hole = list(hero_hole)
        self.button = button                       # 0 = hero on BTN/SB, 1 = villain on BTN/SB
        self.board: list[str] = []
        self.street = "preflop"
        self.history: list[dict] = []
        self.ct = [0, 0]                           # committed_total by seat
        self.cs = [0, 0]                           # committed_street by seat
        self._put(button, BB // 2)                 # BTN posts SB in HU
        self._put(1 - button, BB)
        self.current_bet = BB
        self.min_raise = BB

    def _put(self, p: int, to: int) -> None:
        add = to - self.cs[p]
        assert add >= 0, f"negative commit for seat {p}: to={to} cs={self.cs[p]}"
        self.cs[p] += add
        self.ct[p] += add
        assert self.ct[p] <= START_STACK, f"seat {p} over-committed: {self.ct[p]}"

    def raise_to(self, p: int, to: int) -> "HU":
        label = "bet" if self.current_bet == 0 else "raise"
        self.history.append({"player": p, "action": label, "street": self.street, "to": float(to)})
        self.min_raise = to - self.current_bet
        self._put(p, to)
        self.current_bet = to
        return self

    def jam(self, p: int) -> "HU":
        return self.raise_to(p, self.cs[p] + (START_STACK - self.ct[p]))

    def call(self, p: int) -> "HU":
        self.history.append({"player": p, "action": "call", "street": self.street})
        self._put(p, min(self.current_bet, self.cs[p] + (START_STACK - self.ct[p])))
        return self

    def check(self, p: int) -> "HU":
        self.history.append({"player": p, "action": "check", "street": self.street})
        return self

    def deal(self, street: str, cards: list[str]) -> "HU":
        self.history.append({"action": "deal", "street": street})
        self.street, self.board = street, list(cards)
        self.cs = [0, 0]
        self.current_bet, self.min_raise = 0, BB
        return self

    def state(self, hand_id: str, hand_no: int) -> dict:
        stacks = [START_STACK - self.ct[0], START_STACK - self.ct[1]]
        to_call = self.current_bet - self.cs[0]
        assert to_call >= 0 and min(stacks) >= 0
        can_check = to_call == 0
        can_raise = (stacks[0] > to_call) and stacks[1] > 0     # game.py: opp all-in blocks raising
        is_bet = self.current_bet == 0
        raise_min = raise_max = None
        if can_raise:
            raise_max = self.cs[0] + stacks[0]
            raise_min = min((self.cs[0] + BB) if is_bet else (self.current_bet + self.min_raise), raise_max)
        players = []
        for i, hole in ((0, self.hole), (1, ["??", "??"])):
            players.append({"idx": i, "hole": hole, "stack": stacks[i],
                            "committed_street": self.cs[i], "committed_total": self.ct[i],
                            "folded": False, "all_in": stacks[i] == 0, "is_button": i == self.button})
        return {"street": self.street, "board": list(self.board), "pot": sum(self.ct), "bb": BB,
                "current_bet": int(self.current_bet), "button": self.button, "hand_no": hand_no,
                "to_act": 0, "hand_id": hand_id, "hand_over": False, "history": list(self.history),
                "players": players,
                "legal": {"to_act": 0, "to_call": int(to_call), "pot": sum(self.ct),
                          "can_fold": to_call > 0, "can_check": can_check, "can_call": to_call > 0,
                          "call_amount": int(min(to_call, stacks[0])), "can_raise": can_raise,
                          "is_bet": is_bet, "raise_min": raise_min, "raise_max": raise_max}}


# ====================================================================== scenario lines
def _srp_defend_flop(hole: list[str], flop: list[str]) -> HU:
    """SRP, hero BB defends a 2.5x open, check-calls a pot c-bet -> pot 1500 going to the turn."""
    h = HU(hole, button=1)
    h.raise_to(1, 250).call(0)
    h.deal("flop", flop).check(0).raise_to(1, 500).call(0)
    return h

def srp_turn_barrel(hole, flop, turn, bet_to: int | None) -> HU:
    """Decision: hero facing the 2nd barrel on the turn (bet_to=None -> villain open-jams)."""
    h = _srp_defend_flop(hole, flop).deal("turn", flop + [turn]).check(0)
    return h.jam(1) if bet_to is None else h.raise_to(1, bet_to)

def srp_river_barrel(hole, flop, turn, river, bet_to: int) -> HU:
    """Decision: hero called a 1x turn barrel, faces the 3rd barrel on the river (pot 4500)."""
    h = _srp_defend_flop(hole, flop)
    h.deal("turn", flop + [turn]).check(0).raise_to(1, 1500).call(0)
    return h.deal("river", flop + [turn, river]).check(0).raise_to(1, bet_to)

def threebet_river_jam(hole, flop, turn, river) -> HU:
    """3bet pot, hero the 3bettor check-calls 0.66-pot flop+turn barrels, faces the river JAM."""
    h = HU(hole, button=1)
    h.raise_to(1, 250).raise_to(0, 1100).call(1)
    h.deal("flop", flop).check(0).raise_to(1, 1450).call(0)
    h.deal("turn", flop + [turn]).check(0).raise_to(1, 3400).call(0)
    return h.deal("river", flop + [turn, river]).check(0).jam(1)

def counterfeit_river(hole, flop, turn, river, jam: bool) -> HU:
    """SRP, flop check-call, turn checks through, the river counterfeits/completes -- villain bets."""
    h = _srp_defend_flop(hole, flop)
    h.deal("turn", flop + [turn]).check(0).check(1)
    h.deal("river", flop + [turn, river]).check(0)
    return h.jam(1) if jam else h.raise_to(1, 1500)          # 1500 = 1x pot

def checkraise_after_cbet(hole, flop, raise_to: int | None) -> HU:
    """Hero PFR on the BTN c-bets 0.66 pot, villain check-raises 3x (990) or JAMS."""
    h = HU(hole, button=0)
    h.raise_to(0, 250).call(1)
    h.deal("flop", flop).check(1).raise_to(0, 330)
    return h.jam(1) if raise_to is None else h.raise_to(1, raise_to)

def five_bet_jam(hole) -> HU:
    """Hero BTN opens, 3bet, hero 4bets, villain 5bet-JAMS 200bb. Call = the whole stack."""
    return HU(hole, button=0).raise_to(0, 250).raise_to(1, 1100).raise_to(0, 2500).jam(1)

def junk_vs_4bet(hole) -> HU:
    """Hero BB 3bet a junk hand, villain 4bets to 27.5bb. The bar: MUST fold."""
    return HU(hole, button=1).raise_to(1, 250).raise_to(0, 1100).raise_to(1, 2750)

def river_first_in(hole, flop, turn, river) -> HU:
    """Bloated 3bet pot (5100), turn checked through, hero FIRST-IN on the river (sizer probe)."""
    h = HU(hole, button=1)
    h.raise_to(1, 250).raise_to(0, 1100).call(1)
    h.deal("flop", flop).raise_to(0, 1450).call(1)
    h.deal("turn", flop + [turn]).check(0).check(1)
    return h.deal("river", flop + [turn, river]).check(0)

def trap_line(hole, flop, turn, river=None) -> HU:
    """Hero checked a strong hand on the flop, check-called; villain barrels 1.25x turn / JAMS river."""
    h = HU(hole, button=1)
    h.raise_to(1, 250).call(0)
    h.deal("flop", flop).check(0).raise_to(1, 330).call(0)
    h.deal("turn", flop + [turn]).check(0).raise_to(1, 1450)
    if river is None:
        return h                                              # turn decision
    h.call(0)
    return h.deal("river", flop + [turn, river]).check(0).jam(1)


# ====================================================================== spot catalog
def build_spots() -> list[dict]:
    spots: list[dict] = []

    def add(sid, klass, hu, rule, bar, hand_label, facing):
        st = hu.state(sid, len(spots))
        spots.append({"id": sid, "klass": klass, "rule": rule, "bar": bar,
                      "hand_label": hand_label, "hole": hu.hole, "board": st["board"],
                      "street": st["street"], "facing": facing, "pot": st["pot"],
                      "to_call": st["legal"]["to_call"], "hero_stack": st["players"][0]["stack"],
                      "hero_cs": st["players"][0]["committed_street"], "state": st})

    # -- 1 barrel: 3 extreme boards x 3 danger hands ---------------------------------------------
    bar1 = "one-pair / weak-two-pair class never stacks off (> 30% stack) vs 2nd/3rd barrels here"
    boards1 = [
        ("mono", ["Ad", "8d", "3d"], "2c", "6s",
         [("tpwk", ["Ah", "4c"], "A4o top pair weak kicker, no diamond"),
          ("bot2", ["8c", "3h"], "83o bottom two pair, no diamond"),
          ("unpr", ["Jc", "Jh"], "JJ pocket under the A, no diamond")]),
        ("str8", ["6h", "7d", "8s"], "9c", "2h",
         [("tpwk", ["8c", "3c"], "83s top pair weak kicker"),
          ("bot2", ["7c", "6c"], "76s bottom two pair"),
          ("ovpr", ["Jd", "Jh"], "JJ overpair on the 4-straight")]),
        ("dpair", ["Js", "8h", "3c"], "3h", "8c",
         [("tpwk", ["Jd", "4d"], "J4s top pair weak kicker"),
          ("pkt9", ["9c", "9h"], "99 pocket below top pair"),
          ("ovpr", ["Qc", "Qh"], "QQ overpair on the double-paired board")]),
    ]
    for bname, flop, tc, rc, hands in boards1:
        for htag, hole, hlabel in hands:
            pre = f"barrel.{bname}.{htag}"
            add(f"{pre}.t100", "barrel", srp_turn_barrel(hole, flop, tc, 1500), "no_stackoff", bar1,
                hlabel, "SRP turn 2nd barrel 1.0x pot (1500 into 1500)")
            add(f"{pre}.r150", "barrel", srp_river_barrel(hole, flop, tc, rc, 6750), "no_stackoff", bar1,
                hlabel, "SRP river 3rd barrel 1.5x pot (6750 into 4500; call = 38% stack)")
            add(f"{pre}.3bjam", "barrel", threebet_river_jam(hole, flop, tc, rc), "no_stackoff", bar1,
                hlabel, "3bet pot river 3rd-barrel JAM (14050 into 11900; call = 100% stack)")
            if bname == "mono":                    # extra sizes on the scariest board
                add(f"{pre}.t50", "barrel", srp_turn_barrel(hole, flop, tc, 750), "no_stackoff", bar1,
                    hlabel, "SRP turn 2nd barrel 0.5x pot (750 into 1500)")
                add(f"{pre}.tjam", "barrel", srp_turn_barrel(hole, flop, tc, None), "no_stackoff", bar1,
                    hlabel, "SRP turn 2nd-barrel overbet JAM (19250 into 1500; call = 100% stack)")

    # -- 2 cfeit: small two pair, disaster river --------------------------------------------------
    bar2 = "counterfeited / overtaken small two pair never stacks off on this river"
    for bname, hole, hlabel, flop, tc, rc in [
        ("pairK", ["7h", "6h"], "76s two pair, river pairs the K (counterfeit)",
         ["7d", "6c", "Ks"], "2s", "Kd"),
        ("flush", ["9c", "8c"], "98s two pair, river completes the 4-flush",
         ["9h", "8d", "Qh"], "3h", "6h"),
        ("str8", ["9d", "8h"], "98o two pair, river completes the 4-straight",
         ["9s", "8c", "2d"], "Jc", "Th"),
    ]:
        for stag, jam in (("1x", False), ("jam", True)):
            facing = ("river overbet JAM 19250 into 1500 (call = 100% stack)" if jam
                      else "river 1x-pot bet (1500 into 1500)")
            add(f"cfeit.{bname}.{stag}", "cfeit", counterfeit_river(hole, flop, tc, rc, jam),
                "no_stackoff", bar2, hlabel, facing)

    # -- 3 xr: c-bet gets check-raised on wet boards ----------------------------------------------
    bar3 = "one pair (incl. overpair) never stacks off vs a flop check-raise 200bb deep"
    for bname, flop, hands in [
        ("jt9hh", ["Jh", "Th", "9h"], [("tp", ["As", "Jc"], "AJo top pair on monotone JT9"),
                                       ("ovpr", ["Qc", "Qd"], "QQ overpair on monotone JT9")]),
        ("987ss", ["9s", "8s", "7h"], [("tptk", ["Ad", "9d"], "A9s top pair top kicker on 987ss"),
                                       ("ovpr", ["Td", "Tc"], "TT overpair on 987ss")]),
    ]:
        for htag, hole, hlabel in hands:
            add(f"xr.{bname}.{htag}.3x", "xr", checkraise_after_cbet(hole, flop, 990), "no_stackoff",
                bar3, hlabel, "flop check-raise 3x the c-bet (990 over our 330)")
            add(f"xr.{bname}.{htag}.jam", "xr", checkraise_after_cbet(hole, flop, None), "no_stackoff",
                bar3, hlabel, "flop check-raise JAM (19750; call = 100% stack)")

    # -- 4 pre: 5bet-jam discipline + junk-3bet vs 4bet -------------------------------------------
    bar4a = "at 200bb only AA calls a 5bet-JAM; KK calling = the known KsKh replay-gate spew"
    for htag, hole in [("KK", ["Ks", "Kh"]), ("QQ", ["Qs", "Qh"]), ("JJ", ["Js", "Jh"]),
                       ("AKo", ["Ac", "Kd"]), ("AQs", ["Ah", "Qh"]), ("TT", ["Ts", "Th"])]:
        add(f"pre.5bj.{htag}", "pre", five_bet_jam(hole), "no_stackoff", bar4a, htag,
            "villain 5bet-JAMS 200bb over our 25bb 4bet (call 17500 = 100% stack)")
    bar4b = "a junk 3bet bluff (K3o class) MUST fold to the 4bet -- any continue is irresponsible"
    for htag, hole in [("K3o", ["Kc", "3h"]), ("Q5o", ["Qd", "5h"]), ("J4o", ["Jc", "4h"])]:
        add(f"pre.4b.{htag}", "pre", junk_vs_4bet(hole), "must_fold", bar4b, htag,
            "villain 4bets our junk 3bet to 27.5bb (call 1650 into 3850)")

    # -- 5 sizer: first-in river value sizing in a bloated 3bet pot -------------------------------
    for bname, flop, tc, rc, hands in [
        ("dry", ["Kd", "9c", "4s"], "7h", "2d",
         [("nuts", ["Kh", "Ks"], "KK top set = nuts", "must_bet"),
          ("2nd", ["9h", "9s"], "99 second set = 2nd nuts", "none"),
          ("thin", ["Kc", "Jc"], "KJs thin top pair", "size_cap")]),
        ("wet", ["Qh", "Jh", "7c"], "3d", "8h",
         [("nuts", ["Ah", "Kh"], "AKhh nut flush", "must_bet"),
          ("2nd", ["Kh", "9h"], "K9hh 2nd-nut flush", "none"),
          ("thin", ["Ac", "Qd"], "AQo thin top pair on the 3-flush", "size_cap")]),
    ]:
        for htag, hole, hlabel, rule in hands:
            bar5 = {"must_bet": "checking the nuts first-in in a 51bb pot = over-nit",
                    "none": "recorded only (2nd nuts: any size defensible)",
                    "size_cap": f"thin value never bets > {SIZE_CAP_X_POT}x pot (7650)"}[rule]
            add(f"sizer.{bname}.{htag}", "sizer", river_first_in(hole, flop, tc, rc), rule, bar5,
                hlabel, "FIRST-IN on the river, 3bet pot 5100, stack 17450 behind (jam = 3.4x pot)")

    # -- 6 trap: checked strong hand, villain barrels huge -- must not fold -----------------------
    bar6 = "a trapped set / top two MUST continue vs the barrel (fold = over-nit)"
    for bname, hole, hlabel, flop, tc, rc in [
        ("set7", ["7h", "7c"], "77 flopped set (trap)", ["7d", "2s", "Qc"], "3h", "9d"),
        ("top2q9", ["Qs", "9s"], "Q9s flopped top two (trap)", ["Qc", "9h", "4d"], "3c", "6h"),
        ("set9", ["9h", "9s"], "99 flopped set (trap)", ["9c", "6d", "2h"], "Kd", "4c"),
        ("top2jt", ["Js", "Td"], "JTo flopped top two (trap)", ["Jc", "Th", "3s"], "7d", "2c"),
    ]:
        add(f"trap.{bname}.turn", "trap", trap_line(hole, flop, tc), "must_continue", bar6, hlabel,
            "villain turn barrel 1.25x pot (1450 into 1160) after our flop check-call")
        add(f"trap.{bname}.river", "trap", trap_line(hole, flop, tc, rc), "must_continue", bar6, hlabel,
            "villain river overbet JAM (17970 into 4060) after barreling the turn")

    return spots


# ====================================================================== classification
def commit_of(action: str, amount, sp: dict) -> int:
    """Chips hero puts in NOW with this action (raise amounts are street-cumulative targets)."""
    stack, cs = sp["hero_stack"], sp["hero_cs"]
    if action == "call":
        return min(sp["to_call"], stack)
    if action == "allin":
        return stack
    if action in ("bet", "raise"):
        if amount is None:                      # no target = the engine would put us all-in
            return stack
        return max(0, min(int(amount) - cs, stack))
    return 0


def classify(sp: dict, action: str, amount) -> tuple[str | None, float]:
    commit = commit_of(action, amount, sp)
    frac = commit / sp["hero_stack"] if sp["hero_stack"] else 1.0
    rule = sp["rule"]
    if rule == "no_stackoff" and frac > STACKOFF_FRAC:
        return "IRRESPONSIBLE", frac
    if rule == "must_fold" and action in ACTS_CONTINUE:
        return "IRRESPONSIBLE", frac
    if rule == "size_cap" and action in ("bet", "raise", "allin") and commit > SIZE_CAP_X_POT * sp["pot"]:
        return "IRRESPONSIBLE", frac
    if rule == "must_continue" and action == "fold":
        return "OVER_NIT", frac
    if rule == "must_bet" and action == "check":
        return "OVER_NIT", frac
    return None, frac


# ====================================================================== worker
def run_worker(cfg: str, only: str | None) -> None:
    """Subprocess body: set the config env BEFORE importing pokerbot, decide every spot, dump JSON."""
    for k, v in CONFIGS[cfg].items():
        os.environ[k] = v
    for k, v in BASE_ENV.items():
        os.environ[k] = v
    from pokerbot.strategy.gto_mode import apply as gto_apply, fingerprint
    gto_apply()
    from pokerbot.strategy.bot import PokerBot

    results = {}
    for sp in build_spots():
        if only and only not in sp["id"]:
            continue
        t0 = time.time()
        try:
            r = PokerBot(0, seed=SEED).decide(sp["state"])    # fresh bot per spot: no state bleed
            action, amount = r["action"], r.get("amount")
            why = str(r.get("rationale", {}).get("reasoning", ""))[:160]
        except Exception as e:  # noqa: BLE001 -- a crash IS a finding; record and continue
            action, amount, why = "ERROR", None, f"{type(e).__name__}: {e}"
        flag, frac = (None, 0.0) if action == "ERROR" else classify(sp, action, amount)
        results[sp["id"]] = {"action": action, "amount": amount, "commit_frac": round(frac, 3),
                             "flag": flag, "why": why, "secs": round(time.time() - t0, 2)}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"config": cfg, "fingerprint": fingerprint(), "results": results}
    (OUT_DIR / f"_worker_{cfg}.json").write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"[worker {cfg}] done: {len(results)} spots")


# ====================================================================== orchestrator
def _cell(res: dict | None) -> str:
    if res is None:
        return "-"
    a, amt = res["action"], res.get("amount")
    txt = {"fold": "F", "check": "X", "call": "C", "allin": "ALLIN", "ERROR": "ERR"}.get(a)
    if txt is None:
        txt = ("B" if a == "bet" else "R") + (f"{amt / BB:g}" if amt is not None else "?")
    return txt + {"IRRESPONSIBLE": "!", "OVER_NIT": "~"}.get(res.get("flag") or "", "")


def _spawn(cfg: str, only: str | None) -> subprocess.Popen:
    env = {k: v for k, v in os.environ.items() if not k.startswith("POKERB_")}
    env["PYTHONUTF8"] = "1"
    cmd = [sys.executable, "-m", "research.stress_suite", "--worker", cfg]
    if only:
        cmd += ["--only", only]
    return subprocess.Popen(cmd, cwd=str(ROOT), env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

def run_orchestrator(configs: list[str], only: str | None) -> None:
    spots = [sp for sp in build_spots() if not only or only in sp["id"]]
    print(f"stress_suite: {len(spots)} spots x {len(configs)} configs "
          f"(seed {SEED}, resolver OFF, fresh bot per spot)")
    t0 = time.time()
    procs = {cfg: _spawn(cfg, only) for cfg in configs}
    data = {}
    for cfg, p in procs.items():
        try:
            out, _ = p.communicate(timeout=WORKER_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            p.kill()
            print(f"[{cfg}] TIMEOUT after {WORKER_TIMEOUT_S}s -- excluded")
            continue
        if p.returncode != 0:
            print(f"[{cfg}] worker FAILED (rc={p.returncode}):\n{out[-2000:]}")
            continue
        data[cfg] = json.loads((OUT_DIR / f"_worker_{cfg}.json").read_text(encoding="utf-8"))
    print(f"all workers done in {time.time() - t0:.0f}s\n")

    # ---- matrix ----
    cols = [c for c in configs if c in data]
    idw = max(len(sp["id"]) for sp in spots) + 1
    print("cell legend: F=fold X=check C=call B/R<bb>=bet/raise-to  '!'=IRRESPONSIBLE  '~'=OVER-NIT")
    header = "spot".ljust(idw) + "".join(c.rjust(14) for c in cols)
    cur_klass = None
    for sp in spots:
        if sp["klass"] != cur_klass:
            cur_klass = sp["klass"]
            print("\n" + header if cur_klass == "barrel" else header.replace("spot".ljust(idw), "".ljust(idw)))
        row = sp["id"].ljust(idw)
        for c in cols:
            row += _cell(data[c]["results"].get(sp["id"])).rjust(14)
        print(row)

    # ---- per-config counts + flagged spots ----
    summary = {}
    print("\n== per-config verdicts " + "=" * 60)
    for c in cols:
        res = data[c]["results"]
        irr = [(i, r) for i, r in res.items() if r["flag"] == "IRRESPONSIBLE"]
        nit = [(i, r) for i, r in res.items() if r["flag"] == "OVER_NIT"]
        err = [(i, r) for i, r in res.items() if r["action"] == "ERROR"]
        summary[c] = {"irresponsible": len(irr), "over_nit": len(nit), "errors": len(err),
                      "irresponsible_spots": [i for i, _ in irr], "over_nit_spots": [i for i, _ in nit],
                      "error_spots": [i for i, _ in err]}
        print(f"\n{c}: IRRESPONSIBLE={len(irr)}  OVER-NIT={len(nit)}  ERRORS={len(err)}")
        for i, r in irr:
            print(f"  ! {i:32s} {r['action']:6s} amt={r['amount']} commit={r['commit_frac']:.0%}  {r['why'][:70]}")
        for i, r in nit:
            print(f"  ~ {i:32s} {r['action']:6s} {r['why'][:80]}")
        for i, r in err:
            print(f"  E {i:32s} {r['why'][:90]}")

    # ---- report ----
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "meta": {"date": time.strftime("%Y-%m-%d %H:%M"), "seed": SEED, "bb": BB,
                 "start_stack": START_STACK, "n_spots": len(spots),
                 "stackoff_frac": STACKOFF_FRAC, "size_cap_x_pot": SIZE_CAP_X_POT,
                 "note": "POKERB_RESOLVER=0 POKERB_TURN_RESOLVER=0; fresh PokerBot(0, seed=42) per "
                         "spot; mixed nodes sampled once (deterministic draw, not a frequency)."},
        "fingerprints": {c: data[c]["fingerprint"] for c in cols},
        "summary": summary,
        "spots": [{k: sp[k] for k in ("id", "klass", "hand_label", "hole", "board", "street",
                                      "facing", "pot", "to_call", "hero_stack", "rule", "bar")}
                  for sp in spots],
        "matrix": {sp["id"]: {c: data[c]["results"].get(sp["id"]) for c in cols} for sp in spots},
    }
    REPORT_PATH.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(f"\nreport -> {REPORT_PATH}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--worker", choices=sorted(CONFIGS), help="internal: run one config in-process")
    ap.add_argument("--configs", default=",".join(CONFIGS), help="comma list of configs to run")
    ap.add_argument("--only", default=None, help="substring filter on spot ids (debug)")
    ap.add_argument("--list", action="store_true", help="print the spot catalog and exit")
    args = ap.parse_args()
    if args.list:
        for sp in build_spots():
            print(f"{sp['id']:32s} {sp['street']:7s} pot={sp['pot']:6d} to_call={sp['to_call']:6d} "
                  f"stack={sp['hero_stack']:6d} rule={sp['rule']:13s} {sp['hand_label']}")
        return
    if args.worker:
        run_worker(args.worker, args.only)
    else:
        run_orchestrator([c.strip() for c in args.configs.split(",") if c.strip()], args.only)


if __name__ == "__main__":
    main()
