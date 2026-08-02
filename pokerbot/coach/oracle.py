"""P0-3 Oracle-Diff: the trainer's grading reference — PRINCE v2.2 as a SAFE per-spot HU oracle plus the
neutral arena-'tag' core for multiway spots (TRAINER_PLAN.md P0-3; fairness doctrine TRAINER_DESIGN.md §1).

WHY two oracles: PokerBot (PRINCE) is HU-ONLY — villain is hardcoded as 1-hero_idx (bot.py:316/1260) and
state['players'] must be exactly 2 — so HU spots (n_active==2) are graded by a dedicated PRINCE instance on a
gtow_to_state-style adapter (benchmark/gtowizard.py:85-147, the production-proven precedent), while multiway
spots fall to the arena league's neutral 'tag' core (arena/sixmax.py::_decide, injected per-spot rng).
PokerBot verdicts for a 6-max hand collapsed to HU are an APPROXIMATION (Anhang A) — P0-4 labels them
'Bot-Einschätzung', never 'Mathe'.

SAFETY (binding): the oracle PokerBot is NEVER shared with a game bot, never placed in Session.bots, and this
module never calls the bot's learning entry points observe_opponent / observe_hand_end (bot.py:1248-1276) —
grading must not feed any opponent model. exploit stays False in BOTH trainer modes: the human is graded
against the GTO baseline, not against a Dirichlet read of themselves (recon gotcha 'exploit clobber').

REPRODUCIBILITY: decide() advances the bot's Mersenne stream, so two grade passes over the same record would
otherwise differ. Before every oracle call the rng is replaced by random.Random(rec['spot_fp']) — the crc32
spot fingerprint (decision_log.spot_fingerprint, NEVER Python hash()) — so the same record always grades the
same. The per-spot reseed is deliberate HERE: the sixmax.py:96-97 'fake mixing' warning applies to PLAY
(deterministic frequencies = a readable bot); a grader WANTS a deterministic reference sample.

Output contracts (consumed by grader.grade_decision P0-2 and the bands P0-4):
  oracle_decision(rec) -> {'source': 'prince_hu'|'sixmax_tag', 'action', 'amount', 'rationale'}
  oracle_diff(rec)     -> {'match': bool, 'oracle_action': str, 'size_diff_frac': float|None, 'oracle': dict}
Amounts are commit-TO street totals in chips (recon gotcha #5); 'allin' resolves to legal['raise_max'].

Run:  python -m pokerbot.coach.oracle      (offline self-test, synthetic records — no server, no new modules)
"""
from __future__ import annotations

import os
import random
from types import SimpleNamespace

# PRINCE v2.2 = the trainer's grading anchor (TRAINER_PLAN.md Basis-Bot). Expand the profile BEFORE any
# pokerbot.strategy import — postflop.py/advisor.py read their flags at IMPORT time (gto_mode.py:6). The
# post-v2.2 default-OFF levers (PAIR_DEFENSE/RIVER_DEFENSE/PURIFY/...) are NOT set here (excluded, v2.2 anchor).
os.environ.setdefault("POKERB_PRINCE", "1")
from pokerbot.strategy.gto_mode import apply as _apply_gto_mode  # noqa: E402

_apply_gto_mode()

# NOTE: import ONLY what we need from arena.sixmax — its OppModel name collides with strategy/opp_model.py
# (recon gotcha); we never touch either. _decide is the module-level core with the injectable rng (sixmax.py:84).
from pokerbot.arena.sixmax import PROFILES as SIXMAX_PROFILES  # noqa: E402
from pokerbot.arena.sixmax import _decide as _sixmax_decide  # noqa: E402
from pokerbot.brain import api  # noqa: E402  (imports pokerbot.strategy -> must come after apply())

ORACLE_SEED = 7            # fixed constructor seed (the gtowizard.py PokerBotAgent precedent); the real
                           # repeatability comes from the per-spot rng reseed in decide()
MULTIWAY_PROFILE = "tag"   # neutral reference profile for multiway spots (PROFILES['tag'], sixmax.py:50)

_STREETS = ("preflop", "flop", "turn", "river")
_STREET_IDX = {s: i for i, s in enumerate(_STREETS)}
# Table act order (engine/table.py POS_LABELS): preflop UTG..BTN then SB, BB; postflop SB first, BTN last.
_PREFLOP_ORDER = ("UTG", "MP", "HJ", "CO", "BTN", "SB", "BB")
_POSTFLOP_ORDER = ("SB", "BB", "UTG", "MP", "HJ", "CO", "BTN")


# ================================================================== HU-state adapter (gtow_to_state model)
def _hu_button(spot: dict, vill_pos: str) -> int:
    """HU button index (0 = hero) for the collapsed 6-max spot — per-record, street-aware.

    Preflop records map the EARLIER-to-act seat to the HU button (the HU button acts FIRST preflop), so the
    bot's SB/BB preflop role branches fire correctly; postflop records map the LATER-to-act (in position)
    seat to the button (HU non-button acts first postflop). The rules disagree only for SB-vs-BB — the 6-max
    blind battle has no exact HU image (the 6-max SB acts first on EVERY street) — and each record is graded
    standalone, so per-street role fidelity beats cross-street consistency (documented approximation).
    """
    order = _PREFLOP_ORDER if spot["street"] == "preflop" else _POSTFLOP_ORDER
    try:
        hero_i, vill_i = order.index(spot["hero_pos"]), order.index(vill_pos)
    except ValueError:                          # unknown label -> neutral fallback: villain gets the button
        return 1
    if spot["street"] == "preflop":
        return 0 if hero_i < vill_i else 1
    return 0 if hero_i > vill_i else 1


def _hu_history(rec: dict, hero_seat: int, vill_seat: int) -> list[dict]:
    """Stored 6-max player entries -> HU history (players 0/1 + 'deal' street markers).

    Remap: hero -> 0. Preflop entries: ALL other seats -> 1 (keeps the raise count = pot type and the
    last-raiser initiative read intact; fold entries are ignored by the RangeTracker, range_tracker.py:327).
    Postflop entries: ONLY the villain seat -> 1, third-seat entries DROPPED — _villain_barrels (bot.py:498)
    parses HU actor ALTERNATION by per-street index parity, which a third actor breaks; between the two live
    seats the relative order survives the drop. Deal markers are re-inserted at every street boundary up to
    the record's street: both bot parsers key on them (_has_initiative stops at the first 'deal', bot.py:921;
    _villain_barrels resets its parity counter there, bot.py:505).
    """
    cur_idx = _STREET_IDX.get(rec.get("street") or rec["spot"]["street"], 0)
    out: list[dict] = []
    si = 0
    for h in rec.get("history", []) or []:
        seat = h.get("player")
        if seat is None:
            continue
        st = _STREET_IDX.get(h.get("street"), 0)
        if st > 0 and seat not in (hero_seat, vill_seat):
            continue
        while si < st:                          # street boundary -> deal marker (gtow_to_state idiom)
            si += 1
            out.append({"action": "deal", "street": _STREETS[si]})
        e = dict(h)
        e["player"] = 0 if seat == hero_seat else 1
        out.append(e)
    while si < cur_idx:                         # hero first to act on a fresh street -> marker still needed
        si += 1
        out.append({"action": "deal", "street": _STREETS[si]})
    return out


def record_to_hu_state(rec: dict) -> dict:
    """trainer.decision.v1 record -> the HU game.state() shape PokerBot.decide consumes (hero forced to 0).

    Modeled 1:1 on gtow_to_state (benchmark/gtowizard.py:85-147): villain hole hidden ['??','??'], players =
    EXACTLY 2 dicts, committed-delta to_call convention (c_v = c_h + to_call), and a STABLE state['hand_id'] —
    PRINCE ships POKERB_LINE_U=1, so omitting hand_id would hit the scalar _hand_u fallback (bot.py:137-141).
    """
    spot, obs, legal = rec["spot"], rec["obs"], rec["legal"]
    hero_seat = spot["hero_seat"]
    live = [s for s in spot["seats"] if not s["folded"] and s["seat"] != hero_seat]
    if len(live) != 1:
        raise ValueError(f"HU-Adapter braucht genau 2 aktive Spieler, fand {1 + len(live)}")
    vill = live[0]
    hero = next(s for s in spot["seats"] if s["seat"] == hero_seat)
    to_call = int(legal["to_call"])
    c_h = int(obs.get("my_committed_street", 0) or 0)
    c_v = c_h + to_call                          # HU: the unmatched delta IS the to_call (gtow convention)
    button = _hu_button(spot, vill["pos"])
    legal_hu = dict(legal)
    legal_hu["to_act"] = 0                       # hero is index 0 by construction
    return {
        "street": rec.get("street") or spot["street"], "board": list(spot["board"]),
        "pot": int(legal.get("pot", spot["pot"])), "bb": int(spot["bb"]),
        "current_bet": int(obs.get("cur_bet", c_v) or 0), "button": button,
        "hand_id": rec.get("hand_id"),           # the LINE_U trap: stable per-hand id, never omitted
        "hand_no": 0, "history": _hu_history(rec, hero_seat, vill["seat"]),
        "to_act": 0, "hand_over": False,
        "players": [
            {"idx": 0, "hole": list(spot["hero_hole"]), "stack": int(obs["my_stack"]),
             "committed_street": c_h, "committed_total": int(hero["committed_total"]),
             "folded": False, "all_in": bool(hero.get("all_in")), "is_button": button == 0},
            {"idx": 1, "hole": ["??", "??"], "stack": int(vill["stack"]),
             "committed_street": c_v, "committed_total": int(vill["committed_total"]),
             "folded": False, "all_in": bool(vill.get("all_in")), "is_button": button == 1},
        ],
        "legal": legal_hu,
    }


# ================================================================== oracles
def _legalized(rec: dict, action: str, amount) -> tuple[str, int | None]:
    """Validate/clamp a synthesized action through api.legalize (api.py:469 — the engine = truth).

    Keeps the oracle's bet/raise verb when only the size was clamped; an illegal request falls back to
    legalize's safe verb (check > call > fold). Cheap legality assert per P0-3 step 7.
    """
    spot = SimpleNamespace(**rec["spot"])        # legalize duck-types .legal/.bb/.street/.to_call/.pot
    size_bb = (amount / spot.bb) if amount is not None else None
    la, lamt = api.legalize(spot, action, size_bb)
    if la == "raise" and action in ("bet", "raise"):
        return action, lamt
    return la, lamt


class PrinceOracle:
    """A DEDICATED PRINCE v2.2 PokerBot for grading HU spots (never a game bot, never in Session.bots).

    The proven pattern: web/server.py:30-31 runs a separate play-bot + advisor-oracle in production.
    exploit=False in BOTH trainer modes (bot.py:143 can only force OFF, so a trainer-set POKERB_EXPLOIT=1
    for the Exploit-Modus game bots cannot flip this instance ON). use_resolver stays False in P0: a cold-
    cache river solve costs seconds, and the sparse resolver rationale lacks the equity/mdf keys P1 renders.
    """

    def __init__(self, seed: int = ORACLE_SEED):
        from pokerbot.strategy.bot import PokerBot   # lazy: torch-free module import until an oracle exists
        self.bot = PokerBot(0, seed=seed, exploit=False)
        self.bot.use_resolver = False
        self.bot.use_turn_resolver = False

    def decide(self, rec: dict) -> dict:
        state = record_to_hu_state(rec)
        self.bot.hero_idx = 0                        # re-pin (gtowizard.py:208 idiom); cheap, explicit
        self.bot.rng = random.Random(rec["spot_fp"])  # fresh per-spot rng -> repeatable grading
        dec = self.bot.decide(state)
        action, amount = _legalized(rec, dec["action"], dec["amount"])
        # rationale families the P1 renderer must branch on: preflop / postflop / sparse-resolver / deepcfr
        # (bot.py:1242 _mk always adds 'reasoning'; equity/required_equity/mdf/defense_advisor/advisor_pbet*
        # are path-dependent free explanation data).
        return {"source": "prince_hu", "action": action, "amount": amount,
                "rationale": dec.get("rationale", {})}


class SixMaxOracle:
    """The neutral arena reference for multiway spots (n_active > 2) — PokerBot cannot represent them.

    Calls the module-level _decide (sixmax.py:84) on the stored table.obs_for dict with an injected
    per-spot rng and an initiative flag derived from the stored history; no exploit read ({}).
    """

    def __init__(self, profile: str = MULTIWAY_PROFILE):
        self.knobs = SIXMAX_PROFILES[profile]

    def decide(self, rec: dict) -> dict:
        obs = rec["obs"]
        aggressor = _preflop_aggressor(rec) if obs.get("board") else None
        dec = _sixmax_decide(obs, self.knobs, {}, aggressor=aggressor,
                             rng=random.Random(rec["spot_fp"]))
        action, amount = _legalized(rec, dec["action"], dec["amount"])
        return {"source": f"sixmax_{self.knobs.name}", "action": action, "amount": amount,
                "rationale": dec.get("rationale", {})}


def _preflop_aggressor(rec: dict) -> bool | None:
    """True/False = hero holds/lacks the preflop initiative; None = limped pot (mirrors SixMaxBot.decide)."""
    hero_seat = rec.get("spot", {}).get("hero_seat", 0)
    last = None
    for h in rec.get("history", []) or []:
        if h.get("street") == "preflop" and h.get("action") in ("bet", "raise", "allin"):
            last = h.get("player")
    return None if last is None else last == hero_seat


# ================================================================== routing + diff
_PRINCE: PrinceOracle | None = None
_SIXMAX: SixMaxOracle | None = None


def oracle_decision(rec: dict) -> dict:
    """Route one decision record to the right oracle: n_active==2 -> PRINCE HU, else the sixmax 'tag' core.

    Module-level singletons are safe here BECAUSE every call reseeds its own per-spot rng and the instances
    never learn (no observe hooks) — per-Session instances (plan wording) would grade byte-identically.
    """
    global _PRINCE, _SIXMAX
    n_active = int(rec.get("obs", {}).get("n_active") or rec.get("spot", {}).get("n_active") or 0)
    if n_active == 2:
        if _PRINCE is None:
            _PRINCE = PrinceOracle()
        return _PRINCE.decide(rec)
    if _SIXMAX is None:
        _SIXMAX = SixMaxOracle()
    return _SIXMAX.decide(rec)


def _canon_verb(action: str | None, legal: dict) -> str | None:
    """Normalize the aggressive verbs via legal['is_bet'] (P0-3 step 6): bet/raise/allin -> the node's verb."""
    if action in ("bet", "raise", "allin"):
        return "bet" if legal.get("is_bet") else "raise"
    return action


def _aggro_to(action: str | None, amount, legal: dict) -> int | None:
    """Effective commit-TO street total of an aggressive action; 'allin' -> raise_max (recon gotcha #5)."""
    if action == "allin" or amount is None:
        return legal.get("raise_max")
    return int(amount)


def oracle_diff(rec: dict, oracle: dict | None = None) -> dict:
    """Human vs oracle: verb match (bet/raise normalized) + sizing distance on both-aggressive.

    size_diff_frac = |human_to - oracle_to| / pot-as-faced — commit-TO totals, NEVER chips-added (recon
    gotcha), in pot fractions so P0-4's 0.25 OK-band reads as 'within a quarter pot'. None unless both
    sides are aggressive. The full oracle result rides along under 'oracle' (P1 explanation data).
    """
    if oracle is None:
        oracle = oracle_decision(rec)
    legal = rec.get("legal", {}) or {}
    human = rec.get("human_action", {}) or {}
    h_verb = _canon_verb(human.get("action"), legal)
    o_verb = _canon_verb(oracle.get("action"), legal)
    size_diff_frac = None
    if h_verb in ("bet", "raise") and o_verb in ("bet", "raise"):
        pot = legal.get("pot") or rec.get("spot", {}).get("pot") or 0
        h_to = _aggro_to(human.get("action"), human.get("amount"), legal)
        o_to = _aggro_to(oracle.get("action"), oracle.get("amount"), legal)
        if pot > 0 and h_to is not None and o_to is not None:
            size_diff_frac = round(abs(h_to - o_to) / pot, 4)
    return {"match": h_verb == o_verb, "oracle_action": oracle.get("action"),
            "size_diff_frac": size_diff_frac, "oracle": oracle}


# ================================================================== offline self-test (synthetic records)
def _mk_seats(hero_pos: str, spec: list[tuple[int, str, int, int, bool]]) -> list[dict]:
    return [{"seat": s, "pos": p, "stack": st, "committed_total": ct, "folded": f, "all_in": False}
            for s, p, st, ct, f in spec]


def _hu_flop_record() -> dict:
    """SB opens, hero (BB) calls, flop: SB bets 250 into 500 (0.5x pot) — the P0-3 acceptance spot."""
    seats = _mk_seats("BB", [(0, "BB", 9750, 250, False), (1, "UTG", 10000, 0, True),
                             (2, "HJ", 10000, 0, True), (3, "CO", 10000, 0, True),
                             (4, "BTN", 10000, 0, True), (5, "SB", 9500, 500, False)])
    history = [{"player": 1, "action": "fold", "street": "preflop"},
               {"player": 2, "action": "fold", "street": "preflop"},
               {"player": 3, "action": "fold", "street": "preflop"},
               {"player": 4, "action": "fold", "street": "preflop"},
               {"player": 5, "action": "raise", "to": 250, "street": "preflop"},
               {"player": 0, "action": "call", "amount": 150, "street": "preflop"},
               {"player": 5, "action": "bet", "to": 250, "street": "flop"}]
    legal = {"to_act": 0, "to_call": 250, "can_fold": True, "can_check": False, "can_call": True,
             "call_amount": 250, "can_raise": True, "is_bet": False, "raise_min": 500,
             "raise_max": 9750, "pot": 750}
    obs = {"hole": ["Ah", "7h"], "board": ["Kd", "8h", "2c"], "to_call": 250, "pot": 750,
           "my_stack": 9750, "bb": 100, "n_active": 2, "position": "BB", "preflop_raises": 1,
           "cur_bet": 250, "my_committed_street": 0, "street": "flop", "can_check": False,
           "can_call": True, "can_raise": True, "raise_min": 500, "raise_max": 9750}
    spot = {"street": "flop", "board": ["Kd", "8h", "2c"], "bb": 100, "hero_seat": 0, "hero_pos": "BB",
            "hero_hole": ["Ah", "7h"], "pot": 750, "to_call": 250, "n_active": 2, "seats": seats,
            "legal": {"can_fold": True, "can_check": False, "can_call": True, "can_raise": True,
                      "raise_min": 500, "raise_max": 9750},
            "line": [], "villain_fold": 0.5, "villain_aggro": 0.5}
    return {"schema": "trainer.decision.v1", "session_id": "selftest", "hand_id": "selftest-1",
            "ts": 0, "mode": "gto", "street": "flop", "spot": spot, "obs": obs, "legal": legal,
            "history": history, "human_action": {"action": "call", "amount": None}, "spot_fp": 3141592653}


def _hu_preflop_record() -> dict:
    """Folds to hero in the SB, first-in vs the BB — exercises the preflop button rule + the LINE_U draw."""
    seats = _mk_seats("SB", [(0, "SB", 9950, 50, False), (1, "BB", 9900, 100, False),
                             (2, "UTG", 10000, 0, True), (3, "HJ", 10000, 0, True),
                             (4, "CO", 10000, 0, True), (5, "BTN", 10000, 0, True)])
    history = [{"player": s, "action": "fold", "street": "preflop"} for s in (2, 3, 4, 5)]
    legal = {"to_act": 0, "to_call": 50, "can_fold": True, "can_check": False, "can_call": True,
             "call_amount": 50, "can_raise": True, "is_bet": False, "raise_min": 200,
             "raise_max": 10000, "pot": 150}
    obs = {"hole": ["Kd", "9d"], "board": [], "to_call": 50, "pot": 150, "my_stack": 9950, "bb": 100,
           "n_active": 2, "position": "SB", "preflop_raises": 0, "cur_bet": 100,
           "my_committed_street": 50, "street": "preflop", "can_check": False, "can_call": True,
           "can_raise": True, "raise_min": 200, "raise_max": 10000}
    spot = {"street": "preflop", "board": [], "bb": 100, "hero_seat": 0, "hero_pos": "SB",
            "hero_hole": ["Kd", "9d"], "pot": 150, "to_call": 50, "n_active": 2, "seats": seats,
            "legal": {"can_fold": True, "can_check": False, "can_call": True, "can_raise": True,
                      "raise_min": 200, "raise_max": 10000},
            "line": [], "villain_fold": 0.5, "villain_aggro": 0.5}
    return {"schema": "trainer.decision.v1", "session_id": "selftest", "hand_id": "selftest-2",
            "ts": 0, "mode": "gto", "street": "preflop", "spot": spot, "obs": obs, "legal": legal,
            "history": history, "human_action": {"action": "raise", "amount": 250}, "spot_fp": 271828182}


def _multiway_record() -> dict:
    """HJ opens, CO + BTN call, hero (BB) to act — 4 active preflop, must route to the sixmax oracle."""
    seats = _mk_seats("BB", [(0, "BB", 9900, 100, False), (1, "UTG", 10000, 0, True),
                             (2, "HJ", 9750, 250, False), (3, "CO", 9750, 250, False),
                             (4, "BTN", 9750, 250, False), (5, "SB", 9950, 50, True)])
    history = [{"player": 1, "action": "fold", "street": "preflop"},
               {"player": 2, "action": "raise", "to": 250, "street": "preflop"},
               {"player": 3, "action": "call", "amount": 250, "street": "preflop"},
               {"player": 4, "action": "call", "amount": 250, "street": "preflop"},
               {"player": 5, "action": "fold", "street": "preflop"}]
    legal = {"to_act": 0, "to_call": 150, "can_fold": True, "can_check": False, "can_call": True,
             "call_amount": 150, "can_raise": True, "is_bet": False, "raise_min": 400,
             "raise_max": 10000, "pot": 900}
    obs = {"hole": ["Qs", "Js"], "board": [], "to_call": 150, "pot": 900, "my_stack": 9900, "bb": 100,
           "n_active": 4, "position": "BB", "preflop_raises": 1, "cur_bet": 250,
           "my_committed_street": 100, "street": "preflop", "can_check": False, "can_call": True,
           "can_raise": True, "raise_min": 400, "raise_max": 10000}
    spot = {"street": "preflop", "board": [], "bb": 100, "hero_seat": 0, "hero_pos": "BB",
            "hero_hole": ["Qs", "Js"], "pot": 900, "to_call": 150, "n_active": 4, "seats": seats,
            "legal": {"can_fold": True, "can_check": False, "can_call": True, "can_raise": True,
                      "raise_min": 400, "raise_max": 10000},
            "line": [], "villain_fold": 0.5, "villain_aggro": 0.5}
    return {"schema": "trainer.decision.v1", "session_id": "selftest", "hand_id": "selftest-3",
            "ts": 0, "mode": "gto", "street": "preflop", "spot": spot, "obs": obs, "legal": legal,
            "history": history, "human_action": {"action": "call", "amount": None}, "spot_fp": 161803398}


def _assert_legal(rec: dict, res: dict) -> None:
    la = rec["legal"]
    a, amt = res["action"], res["amount"]
    if a in ("bet", "raise"):
        assert la["can_raise"] and la["raise_min"] <= amt <= la["raise_max"], (a, amt)
    elif a == "allin":
        assert la["can_raise"], a
    else:
        assert {"fold": la["can_fold"], "check": la["can_check"], "call": la["can_call"]}[a], a


def _selftest() -> None:
    import json
    import time

    import pokerbot.arena.sixmax as sixmax_mod
    import pokerbot.strategy.bot as botmod
    botmod.EQUITY_ITERS = 60          # the gtowizard._selftest speedup idiom (decide MC equity)
    sixmax_mod.EQ_ITERS = 60

    # ---- adapter shape (the gtowizard._selftest locked-asserts style) ----
    rec = _hu_flop_record()
    frozen = json.dumps(rec, sort_keys=True)
    st = record_to_hu_state(rec)
    assert len(st["players"]) == 2 and st["legal"]["to_act"] == 0
    assert st["players"][0]["hole"] == ["Ah", "7h"], "hero must be forced to index 0"
    assert st["players"][1]["hole"] == ["??", "??"], "villain hole must be hidden"
    assert st["hand_id"] == "selftest-1", "stable hand_id is mandatory (the LINE_U trap)"
    delta = st["players"][1]["committed_street"] - st["players"][0]["committed_street"]
    assert st["legal"]["to_call"] == delta == 250, "to_call must equal the committed delta"
    assert st["button"] == 0, "BB is IP vs SB postflop -> hero holds the HU button"
    assert {"action": "deal", "street": "flop"} in st["history"], "street deal marker missing"
    assert all(h.get("player") in (0, 1) for h in st["history"] if "player" in h)
    assert st["pot"] == 750 and st["current_bet"] == 250 and st["street"] == "flop"

    pre = _hu_preflop_record()
    st2 = record_to_hu_state(pre)
    assert st2["button"] == 0, "SB acts first preflop -> hero holds the HU button on a preflop record"
    assert st2["legal"]["to_call"] == 50 and st2["players"][1]["committed_street"] == 100
    assert not any(h.get("action") == "deal" for h in st2["history"])

    # ---- multiway rejects the HU adapter ----
    try:
        record_to_hu_state(_multiway_record())
        raise AssertionError("multiway record must not build a HU state")
    except ValueError:
        pass

    # ---- oracle decisions: legality + reproducibility (two passes byte-identical) ----
    prince = PrinceOracle()
    t0 = time.perf_counter()
    r1 = prince.decide(rec)
    cold_ms = (time.perf_counter() - t0) * 1000.0    # includes the one-time advisor/torch load
    t0 = time.perf_counter()
    r2 = prince.decide(rec)                       # SAME instance: the per-spot reseed beats stream advance
    warm_ms = (time.perf_counter() - t0) * 1000.0    # the per-decision cost P0-5 budgets against
    assert (r1["action"], r1["amount"]) == (r2["action"], r2["amount"]), "grading not reproducible"
    assert r1["source"] == "prince_hu" and "reasoning" in r1["rationale"]
    _assert_legal(rec, r1)
    p1 = prince.decide(pre)
    assert (p1["action"], p1["amount"]) == (prince.decide(pre)["action"], prince.decide(pre)["amount"])
    _assert_legal(pre, p1)
    assert json.dumps(rec, sort_keys=True) == frozen, "grading must never mutate the record"

    # ---- routing: HU -> prince, multiway -> sixmax and NEVER through the HU adapter ----
    assert oracle_decision(rec)["source"] == "prince_hu"
    mw = _multiway_record()
    g = globals()
    orig = g["record_to_hu_state"]

    def _boom(_rec):
        raise AssertionError("multiway routing constructed a PokerBot HU state")
    g["record_to_hu_state"] = _boom
    try:
        m1 = oracle_decision(mw)
    finally:
        g["record_to_hu_state"] = orig
    assert m1["source"] == "sixmax_tag"
    _assert_legal(mw, m1)
    m2 = oracle_decision(mw)
    assert (m1["action"], m1["amount"]) == (m2["action"], m2["amount"])

    # ---- diff semantics: verb normalization + commit-TO sizing in pot fractions ----
    d1 = oracle_diff(rec)
    assert set(d1) == {"match", "oracle_action", "size_diff_frac", "oracle"}
    assert d1 == oracle_diff(rec), "diff not deterministic"
    d2 = oracle_diff(rec, oracle={"source": "x", "action": "raise", "amount": 750, "rationale": {}})
    assert d2["match"] is False and d2["size_diff_frac"] is None      # human called vs oracle raise
    agg = dict(rec, human_action={"action": "raise", "amount": 500})
    d3 = oracle_diff(agg, oracle={"source": "x", "action": "bet", "amount": 750, "rationale": {}})
    assert d3["match"] is True, "bet vs raise must normalize via legal['is_bet']"
    assert d3["size_diff_frac"] == round(250 / 750, 4)
    jam = dict(rec, human_action={"action": "allin", "amount": None})
    d4 = oracle_diff(jam, oracle={"source": "x", "action": "raise", "amount": 9750, "rationale": {}})
    assert d4["match"] is True and d4["size_diff_frac"] == 0.0        # allin == raise-to raise_max

    # ---- safety: this module never touches the bot's learning entry points (source-level assert) ----
    import pathlib
    src = pathlib.Path(__file__).read_text(encoding="utf-8")
    needle = ".ob" + "serve_"                     # split so the check never matches itself
    assert needle not in src, "oracle module must never call the learning hooks"

    print(f"OK - oracle: HU adapter locked (button/deal/to_call), prince+sixmax reproducible, "
          f"routing + diff verified; prince decide cold {cold_ms:.0f} ms / warm {warm_ms:.0f} ms "
          f"(spot {rec['spot_fp']}) -> {r1['action']} {r1['amount']}")


if __name__ == "__main__":
    _selftest()
