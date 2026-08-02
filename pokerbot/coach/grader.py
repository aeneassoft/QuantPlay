"""Deterministic decision grader for the 6-max trainer — math checks + grade bands (TRAINER_PLAN.md P0-2/P0-4/P0-5).

WHY: the trainer grades every HUMAN decision captured by decision_log (schema trainer.decision.v1) against
engine truth. Four cheap deterministic checks (pot odds / MDF / sizing geometry / advisor frequency) plus the
P0-3 oracle diff feed assemble_grade(), which implements the BINDING fairness doctrine (TRAINER_DESIGN.md §1):

  - Nie Ergebnisse graden, nur Entscheidungen.
  - ✗ leak NUR bei mathematisch harten Verstößen (Pot-Odds klar verletzt, grobe MDF-Verletzung,
    Sizing-Geometrie-Fehler) — NIEMALS, weil eine Referenz fehlte.
  - ✓ ok bei gemischtem Support (Advisor-Frequenz >= 15%) ODER Oracle-Match ODER nahem Sizing; Mixing wird
    GESAGT ("GTO mischt hier ...").
  - ～ teuer für den Rest — warm formuliert ("teurer Kauf"), jede Kritik trägt Alternative + Ein-Satz-Grund.
  - Range-Toleranz (§1.4, MODULE RULE): kein Check vergleicht den Menschen mit der exakten Tracker-Range.
    Die Pot-Odds-Schranke nutzt per Konstruktion die ANY-TWO-Optimistik (alle 169 Klassen) — verletzt ist
    nur, wer selbst gegen jede Hand den Preis nicht hat.
  - Unsicherheits-Hierarchie (§1.3): Mathe-Checks = "Mathe (unanfechtbar)"; Advisor-Frequenz =
    "Solver-Frequenz (HU-trainiert, Näherung)" (weiches 10-20%-Band, nie hartes richtig/falsch);
    Oracle-Diff = "Bot-Einschätzung". Preflop 6-max hat keinen Advisor (api.preflop_mix -> None) und der
    River hat in P0 keinen Resolver -> beide landen ehrlich bei "Bot-Einschätzung".

POT CONVENTIONS (der #1 Footgun, understanding.py:76-81 ist die auditierte Referenz):
  required_equity(to_call, pot) mit pot AS-FACED (Villains Bet ist schon drin);
  mdf(bet, pot) mit pot = PRE-bet pot = spot.pot - spot.to_call.

Run: python -m pokerbot.coach.grader     (self-test: synthetic fixtures only — no server, no oracle module)
"""
from __future__ import annotations

import dataclasses
import math
import os
import random
import time

# PRINCE v2.2 anchor BEFORE any strategy import — postflop.py/advisor.py read their flags at IMPORT time
# (gto_mode.py:6). setdefault: an explicitly-set env always wins. NEVER set the excluded v3+ default-OFF
# flags here (PAIR_DEFENSE/RIVER_DEFENSE/PURIFY/RAISE_NARROW/OVERBET_MENU/TURN_DEF_ADVISOR).
os.environ.setdefault("POKERB_PRINCE", "1")
from pokerbot.strategy import gto_mode  # noqa: E402 — sanctioned early import (lazy env reads)

gto_mode.apply()

from pokerbot.brain import api  # noqa: E402
from pokerbot.brain import understanding  # noqa: E402
from pokerbot.brain.format_spot import Spot  # noqa: E402
from pokerbot.strategy import advisor  # noqa: E402
from pokerbot.strategy.postflop import snap_raise_to_tree, snap_to_tree  # noqa: E402

# ---------------------------------------------------------------- tunable grade thresholds (doctrine-bound)
EQUITY_ITERS = 600          # explicit MC iters for the optimistic bound — NEVER rely on modes.current() (P0-2)
POT_ODDS_TOLERANCE = 0.05   # equity slack before a call is "Pot-Odds klar verletzt" (benefit of the doubt)
MDF_SMALL_BET_X = 0.5       # folding a STRONG made hand to <= this pot-fraction = grobe MDF-Verletzung
SIZING_ERR_HARD = 0.5       # |human - tree| pot-fraction beyond which geometry is a hard violation
MIX_SUPPORT = 0.15          # advisor frequency that counts as mixed-strategy support (doctrine §1.2)
OK_SIZE_DIFF = 0.25         # both-aggressive: sizing within this fraction of the oracle's = ok

GRADE_OK, GRADE_TEUER, GRADE_LEAK = "ok", "teuer", "leak"

CONF_MATH = "Mathe (unanfechtbar)"
CONF_ADVISOR = "Solver-Frequenz (HU-trainiert, Näherung)"
CONF_ORACLE = "Bot-Einschätzung"
_CONFIDENCE = {"pot_odds": CONF_MATH, "mdf": CONF_MATH, "sizing": CONF_MATH,
               "advisor_freq": CONF_ADVISOR, "oracle_diff": CONF_ORACLE}

# German display names for action verbs inside erklaerung_kurz (verbs themselves are common poker German).
_DE = {"fold": "Fold", "check": "Check", "call": "Call", "raise": "Raise", "bet": "Bet", "allin": "All-in"}

# human verb -> advisor-dist key, per node type ('defense' = facing a bet, 'bet' = free to bet/check)
_ADVISOR_KEY = {"defense": {"fold": "fold", "call": "call", "raise": "raise", "allin": "raise"},
                "bet": {"check": "check", "bet": "bet", "raise": "bet", "allin": "bet"}}


def _all_169_classes() -> tuple:
    """All 169 starting-hand classes (13 pairs + 78 suited + 78 offsuit) — generated locally: the plan's
    BINDING fix, no ALL_169_CLASSES exists anywhere in the repo to import."""
    ranks = "AKQJT98765432"
    classes = [r + r for r in ranks]
    for i in range(13):
        for j in range(i + 1, 13):
            classes.append(ranks[i] + ranks[j] + "s")
            classes.append(ranks[i] + ranks[j] + "o")
    return tuple(classes)


ALL_169_CLASSES = _all_169_classes()

_SPOT_FIELDS = {f.name for f in dataclasses.fields(Spot)}


def _spot_obj(spot_dict: dict) -> Spot:
    """Rebuild the Spot dataclass from its asdict record form (understanding helpers need attribute access)."""
    return Spot(**{k: v for k, v in spot_dict.items() if k in _SPOT_FIELDS})


_NOT_APPLICABLE = {"available": False, "violated": False}


# ---------------------------------------------------------------- P0-2: the four deterministic checks
def check_pot_odds(rec: dict) -> dict:
    """Hard pot-odds check: human CALLED without the price even vs ANY TWO (the §1.4 optimistic bound)."""
    spot = rec["spot"]
    to_call = spot.get("to_call") or 0
    if to_call <= 0:                                   # no bet faced -> formulas would raise at C=0; skip
        return dict(_NOT_APPLICABLE)
    req = api.required_equity(to_call, spot["pot"])    # spot.pot AS-FACED (villain's bet already in it)
    eq_max = api.equity(spot["hero_hole"], list(ALL_169_CLASSES), spot.get("board") or None,
                        iters=EQUITY_ITERS, seed=0)
    if math.isnan(eq_max):                             # dead range (equity.py returns NaN) -> no reference
        return {"available": False, "req": round(req, 4), "violated": False}
    called = (rec.get("human_action") or {}).get("action") == "call"
    violated = bool(called and eq_max + POT_ODDS_TOLERANCE < req)
    return {"req": round(req, 4), "eq_max": round(eq_max, 4), "violated": violated}


def check_mdf(rec: dict) -> dict:
    """Hard MDF proxy: human FOLDED a strong made hand (strength >= STRONG_MADE) to a small bet (<= 0.5x pot)."""
    spot = rec["spot"]
    to_call = spot.get("to_call") or 0
    pot_pre = (spot.get("pot") or 0) - to_call         # MDF is vs the bet into the PRE-bet pot
    if to_call <= 0 or pot_pre <= 0:
        return dict(_NOT_APPLICABLE)
    mdf_val = api.mdf(to_call, pot_pre)                # argument order (bet, pot) — understanding.py:79-81
    size_faced = to_call / pot_pre
    board = spot.get("board") or []
    strength = api.hand_rank(spot["hero_hole"], board)[1] if len(board) >= 3 else None
    folded = (rec.get("human_action") or {}).get("action") == "fold"
    violated = bool(folded and strength is not None
                    and strength >= understanding.STRONG_MADE and size_faced <= MDF_SMALL_BET_X)
    return {"mdf": round(mdf_val, 4), "size_faced": round(size_faced, 4),
            "strength": strength, "violated": violated}


def check_sizing(rec: dict) -> dict:
    """Sizing geometry vs the GTOW tree (snap_to_tree / snap_raise_to_tree). Pure arithmetic, zero latency.
    Hard violation only for err > 0.5 pot-fractions (min-click where the floor is 0.75x, >2.5x-pot spew)."""
    action = (rec.get("human_action") or {}).get("action")
    if action not in ("bet", "raise", "allin"):
        return dict(_NOT_APPLICABLE)
    spot, legal, obs = rec["spot"], rec.get("legal") or {}, rec.get("obs") or {}
    pot, street = spot.get("pot") or 0, spot.get("street")
    amount = (rec.get("human_action") or {}).get("amount")
    if amount is None:                                 # 'allin' carries amount=None -> reconstruct (P0-1 step 6)
        amount = legal.get("raise_max")
    if not amount or pot <= 0:
        return dict(_NOT_APPLICABLE)
    if legal.get("is_bet"):
        bet_chips = amount - (obs.get("my_committed_street") or 0)
        if bet_chips <= 0:
            return dict(_NOT_APPLICABLE)
        human_frac = bet_chips / pot
        snapped_frac = snap_to_tree(int(bet_chips), int(pot), street) / pot
    else:                                              # raise: increment over call / POST-call pot (commit-TO totals)
        cur_bet = obs.get("cur_bet") or 0
        to_call = spot.get("to_call") or 0
        pot_after_call, incr = pot + to_call, amount - cur_bet
        if pot_after_call <= 0 or incr <= 0:
            return dict(_NOT_APPLICABLE)
        human_frac = incr / pot_after_call
        snapped_to = snap_raise_to_tree(int(amount), int(cur_bet), int(pot), int(to_call), street)
        snapped_frac = (snapped_to - cur_bet) / pot_after_call
    err = abs(human_frac - snapped_frac)
    return {"human_frac": round(human_frac, 4), "snapped_frac": round(snapped_frac, 4),
            "err": round(err, 4), "violated": bool(err > SIZING_ERR_HARD)}


def check_advisor(rec: dict) -> dict:
    """Advisor action distribution at the human's node — the P0-4 mixed-support input. Postflop only;
    None/unavailable => {available: False} and the frequency criterion is simply ABSENT (never treated as 0)."""
    spot = rec["spot"]
    street = spot.get("street")
    if street == "preflop":                            # api.preflop_mix returns None on 6-max (api.py:130)
        return {"available": False, "reason": "kein 6-max Preflop-Advisor"}
    to_call = spot.get("to_call") or 0
    hole, board = spot["hero_hole"], spot.get("board") or []
    role = "IP" if understanding._in_position(_spot_obj(spot)) else "OOP"
    if to_call > 0:                                    # facing-bet node -> (P_fold, P_call, P_raise)
        pot_pre = (spot.get("pot") or 0) - to_call
        if not advisor.defense_available() or pot_pre <= 0:
            return {"available": False}
        trip = advisor.p_defense(hole, board, role, to_call / pot_pre, street)
        if trip is None:
            return {"available": False}
        dist, node = {"fold": trip[0], "call": trip[1], "raise": trip[2]}, "defense"
    else:                                              # bet/check node -> P(bet) split
        if not advisor.available(street):
            return {"available": False}
        pb = advisor.p_bet(hole, board, role, street)
        if pb is None:
            return {"available": False}
        dist, node = {"bet": pb, "check": 1.0 - pb}, "bet"
    action = (rec.get("human_action") or {}).get("action")
    chosen = _ADVISOR_KEY[node].get(action)
    p_chosen = dist.get(chosen) if chosen else None
    return {"available": True, "node": node, "role": role,
            "dist": {k: round(v, 4) for k, v in dist.items()},
            "chosen": chosen, "p_chosen": round(p_chosen, 4) if p_chosen is not None else None}


# ---------------------------------------------------------------- P0-4: grade bands (fairness doctrine §1.2)
def _hard_violation(checks: dict) -> dict | None:
    """✗ leak ONLY here — a hard math violation, named + numbered, warm ('teurer Kauf'), with the alternative."""
    po = checks.get("pot_odds") or {}
    if po.get("violated"):
        text = (f"Call brauchte {po.get('req', 0) * 100:.0f}% Equity, selbst gegen jede Hand nur "
                f"{po.get('eq_max', 0) * 100:.0f}% — teurer Kauf, Fold spart auf Dauer.")
        return {"grade": GRADE_LEAK, "grade_typ": "pot_odds", "confidence": CONF_MATH, "erklaerung_kurz": text}
    md = checks.get("mdf") or {}
    if md.get("violated"):
        text = (f"Starke Hand ({md.get('strength') or 0:.2f}) gegen nur {md.get('size_faced', 0):.1f}x Pot "
                f"gefoldet — MDF sagt: mindestens {md.get('mdf', 0) * 100:.0f}% verteidigen, Call war der "
                f"bessere Kauf.")
        return {"grade": GRADE_LEAK, "grade_typ": "mdf", "confidence": CONF_MATH, "erklaerung_kurz": text}
    sz = checks.get("sizing") or {}
    if sz.get("violated"):
        text = (f"Sizing {sz.get('human_frac', 0):.2f}x Pot statt ~{sz.get('snapped_frac', 0):.2f}x vom "
                f"Baum — Geometrie-Fehler, die Standardgröße macht denselben Job billiger.")
        return {"grade": GRADE_LEAK, "grade_typ": "sizing", "confidence": CONF_MATH, "erklaerung_kurz": text}
    return None


def _support_ok(checks: dict, o: dict) -> dict | None:
    """✓ ok: advisor mixed support >= 15% (mixing is SAID out loud), oracle match, or near-oracle sizing."""
    adv = checks.get("advisor") or {}
    p = adv.get("p_chosen") if adv.get("available") else None
    if p is not None and p >= MIX_SUPPORT:
        dist = adv.get("dist") or {}
        support = sorted(((k, v) for k, v in dist.items() if v >= MIX_SUPPORT), key=lambda kv: (-kv[1], kv[0]))
        if len(support) >= 2:
            mix = " / ".join(f"{v * 100:.0f}% {_DE.get(k, k)}" for k, v in support)
            tail = "beides gut" if len(support) == 2 else "alles spielbar"
            text = f"GTO mischt hier: {mix} — {tail}."
        else:
            text = f"Sauber: der Solver spielt {_DE.get(adv.get('chosen'), 'das')} hier in {p * 100:.0f}% der Fälle."
        return {"grade": GRADE_OK, "grade_typ": "advisor_freq", "confidence": CONF_ADVISOR, "erklaerung_kurz": text}
    if o.get("match"):
        act = _DE.get(o.get("oracle_action"), o.get("oracle_action") or "dieselbe Aktion")
        return {"grade": GRADE_OK, "grade_typ": "oracle_diff", "confidence": CONF_ORACLE,
                "erklaerung_kurz": f"Sauber: der Referenz-Bot spielt hier genauso ({act})."}
    sd = o.get("size_diff_frac")
    if sd is not None and sd <= OK_SIZE_DIFF:
        return {"grade": GRADE_OK, "grade_typ": "oracle_diff", "confidence": CONF_ORACLE,
                "erklaerung_kurz": f"Gleiche Linie wie der Referenz-Bot, Sizing nur {sd * 100:.0f}% Pot "
                                   f"daneben — gut."}
    return None


def _teuer_or_no_reference(checks: dict, o: dict) -> dict:
    """～ teuer — but ONLY when a reference actually disagrees. With NO reference at all the grade stays ok
    ('keine Beanstandung'): never a worse grade because a reference was missing (doctrine, P0-4 step 4)."""
    adv = checks.get("advisor") or {}
    p = adv.get("p_chosen") if adv.get("available") else None
    if p is not None:                                  # advisor has an opinion and it is < MIX_SUPPORT
        dist = adv.get("dist") or {}
        alt = o.get("oracle_action") or (max(dist, key=dist.get) if dist else None)
        alt_de = _DE.get(alt, alt or "die Standardlinie")
        chosen_de = _DE.get(adv.get("chosen"), "diese Linie")
        text = (f"Teurer Kauf: der Solver wählt {chosen_de} hier nur in {p * 100:.0f}% der Fälle — "
                f"{alt_de} ist meist der bessere Kauf.")
        return {"grade": GRADE_TEUER, "grade_typ": "advisor_freq", "confidence": CONF_ADVISOR,
                "erklaerung_kurz": text}
    if o.get("oracle_action"):                         # oracle disagreed (no match, sizing not close)
        act = _DE.get(o["oracle_action"], o["oracle_action"])
        return {"grade": GRADE_TEUER, "grade_typ": "oracle_diff", "confidence": CONF_ORACLE,
                "erklaerung_kurz": f"Teurer Kauf: der Referenz-Bot spielt hier {act} — auf Dauer die "
                                   f"günstigere Linie."}
    return {"grade": GRADE_OK, "grade_typ": "oracle_diff", "confidence": CONF_ORACLE,
            "erklaerung_kurz": "Keine Referenz für diesen Spot verfügbar — Mathe sauber, keine Beanstandung."}


def assemble_grade(checks: dict, oracle_diff: dict, street: str, n_active) -> dict:
    """Grade bands per TRAINER_DESIGN.md §1.2 EXACTLY: leak ONLY on hard math violations; ok on mixed
    support / oracle match / near sizing; else teuer. Confidence labels are honest to what P0 has:
    preflop 6-max and the river both resolve to 'Bot-Einschätzung' via the map (no preflop advisor, no
    resolver yet — the trainer that names its limits is more credible, §1.3). `street`/`n_active` are part
    of the stable signature for the post-P0 resolver upgrade; the P0 map does not branch on them."""
    o = oracle_diff or {}
    verdict = _hard_violation(checks) or _support_ok(checks, o) or _teuer_or_no_reference(checks, o)
    assert verdict["confidence"] == _CONFIDENCE[verdict["grade_typ"]]   # map + texts must never drift apart
    return verdict


# ---------------------------------------------------------------- grading entry point + prewarm (P0-5)
_CHECKS = (("pot_odds", check_pot_odds), ("mdf", check_mdf), ("sizing", check_sizing), ("advisor", check_advisor))


def _oracle_diff(rec: dict) -> dict:
    """P0-3 oracle diff (parallel build) — soft dependency: absent module or a failing call degrades to
    {source: 'none'}; a runtime error stays VISIBLE in the record (swallow-trap rule), never silent."""
    try:
        from pokerbot.coach import oracle as _oracle
    except ImportError:
        return {"source": "none"}
    # The P0-3 module ships `oracle_diff`; the plan text called it `diff`. Accept BOTH — a name mismatch
    # between two parallel builders silently disabled every oracle recommendation ("Empfohlen: –" in replay).
    fn = getattr(_oracle, "oracle_diff", None) or getattr(_oracle, "diff", None)
    if fn is None:
        return {"source": "none", "error": "oracle module exposes neither oracle_diff nor diff"}
    try:
        d = fn(rec)
        return d if isinstance(d, dict) else {"source": "none"}
    except Exception as e:  # noqa: BLE001 — a grader bug must never break play, but must be visible
        return {"source": "none", "error": repr(e)}


def grade_decision(rec: dict) -> dict:
    """Grade ONE captured decision record in place: checks + oracle diff + grade band + grade_ms.
    Every check is individually guarded — a failing check becomes {'error': repr(e)} in the record
    (visible, never silent, never a crashed hand)."""
    t0 = time.perf_counter()
    checks: dict = {}
    for name, fn in _CHECKS:
        try:
            checks[name] = fn(rec)
        except Exception as e:  # noqa: BLE001
            checks[name] = {"error": repr(e), "violated": False}
    odiff = _oracle_diff(rec)
    try:
        verdict = assemble_grade(checks, odiff, rec.get("street") or rec.get("spot", {}).get("street"),
                                 rec.get("spot", {}).get("n_active"))
    except Exception as e:  # noqa: BLE001 — never a worse grade because the grader itself broke
        verdict = {"grade": GRADE_OK, "grade_typ": "oracle_diff", "confidence": CONF_ORACLE,
                   "erklaerung_kurz": "Bewertung fehlgeschlagen — keine Beanstandung.", "grade_error": repr(e)}
    rec["checks"] = checks
    rec["oracle"] = odiff
    rec.update(verdict)
    rec["grade_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
    return rec


def prewarm() -> dict:
    """One-time warm-up at SERVER start, not per session (P0-5 step 3): the advisor torch nets (~1-2 s
    first load) + one throwaway PokerBot construction (module-level MLP/blueprint caches are shared
    read-only). Returns the availability map for the startup log."""
    ready = {f"advisor_{st}": advisor.available(st) for st in ("flop", "turn", "river")}
    ready["advisor_defense"] = advisor.defense_available()
    try:
        from pokerbot.strategy.bot import PokerBot
        PokerBot(hero_idx=0, seed=0, exploit=False)
        ready["oracle_bot"] = True
    except Exception:  # noqa: BLE001 — prewarm must never block server start
        ready["oracle_bot"] = False
    try:
        # A throwaway GRADE — construction alone leaves the first decide() cold (~1.6 s measured), which
        # would spend most of the first hand's 800 ms budget. Grading one synthetic record warms the whole
        # path (equity tables, advisor nets, oracle decide) so hand 1 is as fast as hand 50.
        grade_decision(_fixture_record("flop", ["Ah", "7d", "2c"], ["Kc", "Qd"], 300, 100, "call"))
        ready["grade_path"] = True
    except Exception:  # noqa: BLE001
        ready["grade_path"] = False
    try:
        # Turn/River-Netze mitwärmen: die Range-Story (templates_de -> range_story) baut den Tracker pro
        # Straße — der ERSTE Turn/River-Load kostete sonst ~1.4 s in der Feedback-Phase von Hand 1 (gemessen).
        for street, board in (("turn", ["Ah", "7d", "2c", "5s"]), ("river", ["Ah", "7d", "2c", "5s", "Jh"])):
            advisor.p_bet(["Kc", "Qd"], board, "IP", street)
            advisor.p_defense(["Kc", "Qd"], board, "OOP", 0.66, street)
    except Exception:  # noqa: BLE001 — nur Vorwärmen; fehlende Netze meldet die ready-Map oben
        pass
    return ready


# ---------------------------------------------------------------- self-test (synthetic fixtures, hermetic)
def _fixture_record(street: str, board: list, hole: list, pot: int, to_call: int, action: str,
                    amount: int | None = None, *, hero_pos: str = "BTN", is_bet: bool = False,
                    cur_bet: int = 0, my_committed: int = 0) -> dict:
    """A minimal trainer.decision.v1 record (P0-1 schema shape) — enough for every grader check."""
    seats = [{"seat": 0, "pos": hero_pos, "stack": 10000, "committed_total": 0, "folded": False, "all_in": False},
             {"seat": 1, "pos": "BB" if hero_pos != "BB" else "SB", "stack": 10000, "committed_total": 0,
              "folded": False, "all_in": False}]
    legal = {"to_act": 0, "to_call": to_call, "can_fold": True, "can_check": to_call == 0,
             "can_call": to_call > 0, "call_amount": to_call, "can_raise": True, "is_bet": is_bet,
             "raise_min": max(200, 2 * to_call), "raise_max": 10000, "pot": pot}
    spot = {"street": street, "board": board, "bb": 100, "hero_seat": 0, "hero_pos": hero_pos,
            "hero_hole": hole, "pot": pot, "to_call": to_call, "n_active": 2, "seats": seats,
            "legal": {k: legal.get(k) for k in ("can_fold", "can_check", "can_call", "can_raise",
                                                "raise_min", "raise_max")},
            "line": [], "villain_fold": 0.5, "villain_aggro": 0.5}
    obs = {"hole": hole, "board": board, "to_call": to_call, "pot": pot, "my_stack": 10000, "bb": 100,
           "n_active": 2, "position": hero_pos, "preflop_raises": 0, "cur_bet": cur_bet,
           "my_committed_street": my_committed, "street": street}
    return {"schema": "trainer.decision.v1", "session_id": "selftest", "hand_id": "selftest-1", "ts": 0,
            "mode": "gto", "street": street, "spot": spot, "obs": obs, "legal": legal, "history": [],
            "human_action": {"action": action, "amount": amount}, "spot_fp": 12345}


class _StubOracle:
    """sys-attribute stub: `from pokerbot.coach import oracle` resolves the package ATTRIBUTE first, so the
    selftest controls the diff result without the (parallel-built) oracle module existing."""
    result: dict = {"source": "none"}

    @staticmethod
    def diff(rec):  # noqa: ARG004 — record-independent by design (fixture control)
        return dict(_StubOracle.result)


def _graded_subset(rec: dict) -> str:
    """The deterministic slice of a graded record (grade_ms is wall time and excluded by design)."""
    import json
    return json.dumps({k: rec[k] for k in ("checks", "oracle", "grade", "grade_typ", "confidence",
                                           "erklaerung_kurz")}, sort_keys=True)


def _selftest() -> None:                               # noqa: C901 — one linear acceptance script (repo idiom)
    import copy

    import pokerbot.coach as _coach_pkg
    from knowledge_base.math import formulas as F

    # -- environment pin: PRINCE v2.2 active, exploit OFF, excluded v3+ flags untouched
    assert gto_mode.prince_enabled() and os.environ.get("POKERB_EXPLOIT") == "0"
    for f in ("POKERB_PAIR_DEFENSE", "POKERB_RIVER_DEFENSE", "POKERB_PURIFY", "POKERB_RAISE_NARROW",
              "POKERB_OVERBET_MENU", "POKERB_TURN_DEF_ADVISOR"):
        assert os.environ.get(f) is None, f"excluded flag {f} must not be set"

    # -- math conventions locked (the #1 pot-convention footgun)
    assert api.required_equity(50, 150) == 0.25
    for b, p in ((50, 100), (75, 100), (200, 300)):
        assert abs(api.mdf(b, p) - F.minimum_defense_frequency(p, b)) < 1e-12, (b, p)
    assert len(ALL_169_CLASSES) == 169 and len(set(ALL_169_CLASSES)) == 169
    assert sum(1 for c in ALL_169_CLASSES if len(c) == 2) == 13
    assert sum(1 for c in ALL_169_CLASSES if c.endswith("s")) == 78
    print("  math conventions      : required_equity/mdf/169-classes locked")

    _coach_pkg.oracle = _StubOracle                    # hermetic oracle for every grade below
    saved = {n: getattr(advisor, n) for n in ("available", "defense_available", "p_bet", "p_defense")}
    try:
        # -- (1) constructed leak spot: river 72o unimproved, call a pot-size bet -> leak/pot_odds
        _StubOracle.result = {"source": "none"}
        rec = _fixture_record("river", ["As", "Kd", "Qh", "Jc", "9s"], ["7h", "2c"], 2000, 1000, "call")
        grade_decision(rec)
        assert rec["checks"]["pot_odds"]["violated"] is True, rec["checks"]["pot_odds"]
        assert rec["grade"] == GRADE_LEAK and rec["grade_typ"] == "pot_odds", (rec["grade"], rec["grade_typ"])
        assert "Mathe" in rec["confidence"]
        assert rec["grade_ms"] >= 0
        print(f"  leak fixture pot_odds : req={rec['checks']['pot_odds']['req']:.3f} "
              f"eq_max={rec['checks']['pot_odds']['eq_max']:.3f} -> {rec['erklaerung_kurz']}")

        # -- to_call=0 spot: no formulas call, no ValueError
        rec0 = _fixture_record("flop", ["Ah", "7d", "2c"], ["Kd", "Qs"], 300, 0, "check")
        assert check_pot_odds(rec0) == _NOT_APPLICABLE and check_mdf(rec0) == _NOT_APPLICABLE

        # -- NaN range guard: dead range -> available/violated False, no exception
        real_equity = api.equity
        api.equity = lambda *a, **k: float("nan")
        try:
            nan_check = check_pot_odds(_fixture_record("flop", ["Ah", "7d", "2c"], ["Kd", "Qs"], 300, 100, "call"))
        finally:
            api.equity = real_equity
        assert nan_check["available"] is False and nan_check["violated"] is False, nan_check
        print("  guards                : to_call=0 skip + NaN fallback ok")

        # -- (2) advisor mixing support: p_bet=0.60, human checked (0.40 support) -> ok + both percentages
        advisor.available = lambda street="flop": True
        advisor.p_bet = lambda *a, **k: 0.60
        rec2 = _fixture_record("flop", ["Ah", "7d", "2c"], ["Kd", "Qs"], 300, 0, "check")
        grade_decision(rec2)
        assert rec2["grade"] == GRADE_OK and rec2["grade_typ"] == "advisor_freq", rec2["erklaerung_kurz"]
        assert "60" in rec2["erklaerung_kurz"] and "40" in rec2["erklaerung_kurz"], rec2["erklaerung_kurz"]
        assert rec2["confidence"] == CONF_ADVISOR
        print(f"  ok fixture mixing     : {rec2['erklaerung_kurz']}")

        # -- (3) advisor None + oracle mismatch + no math violation -> teuer / Bot-Einschätzung
        advisor.available = lambda *a, **k: False
        advisor.defense_available = lambda: False
        _StubOracle.result = {"source": "prince_hu", "match": False, "oracle_action": "raise",
                              "size_diff_frac": None}
        rec3 = _fixture_record("flop", ["Ah", "7d", "2c"], ["Ad", "Kh"], 600, 200, "call")
        grade_decision(rec3)
        assert rec3["checks"]["advisor"] == {"available": False}, rec3["checks"]["advisor"]
        assert rec3["grade"] == GRADE_TEUER and rec3["grade_typ"] == "oracle_diff", rec3["grade"]
        assert rec3["confidence"] == "Bot-Einschätzung"
        print(f"  teuer fixture         : {rec3['erklaerung_kurz']}")

        # -- (4) fold of a strong made hand vs 0.4x-pot bet -> leak/mdf
        _StubOracle.result = {"source": "none"}
        rec4 = _fixture_record("flop", ["Ah", "Kd", "7c"], ["As", "Ad"], 1400, 400, "fold")
        grade_decision(rec4)
        assert rec4["checks"]["mdf"]["violated"] is True, rec4["checks"]["mdf"]
        assert rec4["grade"] == GRADE_LEAK and rec4["grade_typ"] == "mdf" and "Mathe" in rec4["confidence"]
        print(f"  leak fixture mdf      : strength={rec4['checks']['mdf']['strength']:.2f} "
              f"-> {rec4['erklaerung_kurz']}")

        # -- advisor-None fallback on a graded record: grade still computes from math + oracle
        recf = _fixture_record("turn", ["Ah", "7d", "2c", "Ts"], ["Kd", "Qs"], 900, 300, "call")
        grade_decision(recf)
        assert recf["checks"]["advisor"] == {"available": False}
        assert recf["grade"] in (GRADE_OK, GRADE_TEUER, GRADE_LEAK)
        # a check that RAISES becomes a visible error dict, grade still assigned (never a crashed hand)
        advisor.available = lambda *a, **k: True
        advisor.p_bet = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("kaputt"))
        rece = _fixture_record("flop", ["Ah", "7d", "2c"], ["Kd", "Qs"], 300, 0, "check")
        grade_decision(rece)
        assert "error" in rece["checks"]["advisor"] and rece["grade"] in (GRADE_OK, GRADE_TEUER, GRADE_LEAK)
        print("  robustness            : advisor None + raising check degrade gracefully")

        # -- determinism: grade twice on the same captured record -> byte-identical deterministic slice
        advisor.available = saved["available"]; advisor.defense_available = saved["defense_available"]
        advisor.p_bet = saved["p_bet"]; advisor.p_defense = saved["p_defense"]
        base = _fixture_record("flop", ["Ah", "7d", "2c"], ["Kd", "Qs"], 600, 200, "call")
        a, b = grade_decision(copy.deepcopy(base)), grade_decision(copy.deepcopy(base))
        assert _graded_subset(a) == _graded_subset(b), "grade_decision must be deterministic"
        print("  determinism           : two passes byte-identical (equity seed=0, iters explicit)")

        # -- never-leak-without-math fuzz (200, seed 42): all violated=False -> zero leaks + 4 fields non-empty
        rng = random.Random(42)
        for i in range(200):
            pb = rng.random()
            checks = {
                "pot_odds": {"req": rng.random(), "eq_max": rng.random(), "violated": False},
                "mdf": {"mdf": rng.random(), "size_faced": rng.random() * 2, "strength": rng.random(),
                        "violated": False},
                "sizing": {"human_frac": rng.random() * 3, "snapped_frac": rng.random(), "err": rng.random() * 2,
                           "violated": False},
                "advisor": rng.choice([
                    {"available": False},
                    {"available": True, "node": "bet", "role": "IP", "dist": {"bet": pb, "check": 1 - pb},
                     "chosen": rng.choice(["bet", "check"]), "p_chosen": rng.random()},
                ]),
            }
            o = rng.choice([{"source": "none"},
                            {"source": "prince_hu", "match": rng.random() < 0.5,
                             "oracle_action": rng.choice(["fold", "call", "raise"]),
                             "size_diff_frac": rng.random()}])
            g = assemble_grade(checks, o, rng.choice(["preflop", "flop", "turn", "river"]), rng.choice([2, 3, 4]))
            assert g["grade"] != GRADE_LEAK, (i, g)
            assert all(g[k] for k in ("grade", "grade_typ", "confidence", "erklaerung_kurz")), (i, g)
        print("  fuzz 200 (seed 42)    : zero leaks without a hard math violation; all 4 fields non-empty")
    finally:
        for n, fn in saved.items():
            setattr(advisor, n, fn)

    # -- prewarm: availability map + throwaway PokerBot construction (shared read-only caches)
    ready = prewarm()
    assert set(ready) == {"advisor_flop", "advisor_turn", "advisor_river", "advisor_defense",
                          "oracle_bot", "grade_path"}
    print(f"  prewarm               : {ready}")
    print("OK — grader P0-2/P0-4 acceptance fixtures all pass (fingerprint: PRINCE v2.2, exploit OFF)")


if __name__ == "__main__":
    _selftest()
