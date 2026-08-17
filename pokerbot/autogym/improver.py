"""AUTOGYM-IMPROVER — die Verbesserungs-Schleife: minen -> patchen -> Gate -> Urteil.

Autonomie mit Leitplanken (die Gate-Doktrin des Repos, hier als Code):
  * Nur P-Befunde (beweisbar dominierte Aktionen) duerfen einen AUTONOMEN Patch
    ausloesen — und der Patch ist ein WRAPPER (Guard-Regel um decide()), nie ein
    Quelltext-Edit.
  * JEDER Patch, auch der beweisbare, muss das gepaarte A/B-Gate passieren
    (duplicate-Decks, Karten herausgekuerzt), bevor er als 'ANWENDEN' gebucht wird.
    Bestehensgrenze vorregistriert: Kandidat nicht schlechter als -1 bb/100 und
    |Effekt| > 2*SE fuer eine POSITIVE Buchung.
  * L/F-Befunde erzeugen nur EXPERIMENT-VORSCHLAEGE ins Journal — ein Mensch
    (oder eine spaetere, selbst gegatete Stufe) waehlt aus.

Journal: data/autogym/journal.jsonl — jede Runde ein Eintrag, nichts wird still.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from pokerbot.benchmark.duplicate import duplicate_ab, gen_decks, pokerbot

from .oracle import OracleReport

JOURNAL = Path("data/autogym/journal.jsonl")

# Whitelist der Guard-Regeln, die ein P-Befund scharfschalten darf.
# name -> (beschreibung, patch_fn(action, amount, state) -> (action, amount))
GUARDS = {
    "free_fold": ("fold bei to_call=0 wird zu check",
                  lambda a, amt, st: (("check", None) if a == "fold" else (a, amt))),
}


def podds_guard(make_strat, margin: float = 0.02, iters: int = 120):
    """Der erste aus dem Journal MOTIVIERTE Bot-Kandidat (L: call_unter_pot_odds):
    River-Call nur, wenn die Equity vs eine UNIFORME Gegner-Range die Pot-Odds
    deckt. Nutzt NUR legale Information (eigene Karten, Board, Pot) -- die
    Rueckschau-Gegnerhand des Orakels beruehrt er nie. Ob die uniforme Range zu
    pessimistisch ist (Value-Folds!), entscheidet allein das gepaarte Gate."""
    import random as _random

    from knowledge_base.math.formulas import equity_needed_to_call
    from pokerbot.engine.cards import make_deck
    from pokerbot.engine.equity import equity_vs_range

    def make(seat):
        base = make_strat(seat)
        rng = _random.Random(97 + seat)

        def d(st):
            a, amt = base(st)
            me = st["players"][st["to_act"]]
            to_call = max(0, st["current_bet"] - me["committed_street"])
            if a == "call" and to_call > 0 and st["street"] == "river":
                dead = set(me["hole"]) | set(st["board"])
                deck = [c for c in make_deck() if c not in dead]
                combos = [tuple(rng.sample(deck, 2)) for _ in range(40)]
                eq = equity_vs_range(me["hole"], combos, st["board"], iters=iters)
                if eq + margin < equity_needed_to_call(st["pot"], to_call):
                    return "fold", None
            return a, amt
        return d
    return make


def mdf_guard(make_strat, margin: float = 0.0, iters: int = 120):
    """Kandidat aus dem F-Befund mdf_flop (OVER-FOLD 0,61 vs erlaubt 0,32):
    ein Flop-Fold gegen einen Einsatz wird zum Call, wenn die Equity vs eine
    uniforme Range die Pot-Odds deckt. Nur legale Information. Die Doktrin
    kennt das Risiko (Frequenz-Matching 3x widerlegt) -- das Gate urteilt."""
    import random as _random
    from knowledge_base.math.formulas import equity_needed_to_call
    from pokerbot.engine.cards import make_deck
    from pokerbot.engine.equity import equity_vs_range

    def make(seat):
        base = make_strat(seat)
        rng = _random.Random(53 + seat)

        def d(st):
            a, amt = base(st)
            me = st["players"][st["to_act"]]
            to_call = max(0, st["current_bet"] - me["committed_street"])
            if a == "fold" and to_call > 0 and st["street"] in streets:
                dead = set(me["hole"]) | set(st["board"])
                deck = [c for c in make_deck() if c not in dead]
                combos = [tuple(rng.sample(deck, 2)) for _ in range(40)]
                eq = equity_vs_range(me["hole"], combos, st["board"], iters=iters)
                if eq >= equity_needed_to_call(st["pot"], to_call) + margin:
                    return "call", None
            return a, amt
        return d
    return make


def sel_guard(make_strat, margin: float = 0.03, iters: int = 160,
              streets: tuple = ("flop",)):
    """Kandidat 3 -- SELEKTION statt Frequenz (die Lehre aus Runde 1): ein
    Flop-Fold gegen einen Einsatz wird NUR dann zum Call, wenn die Equity vs
    die TRACKER-Range des Gegners (Bayes ueber die gespielte Linie, History
    steht im State) die Pot-Odds plus Marge deckt. Trash foldet weiter --
    genau die Selektion, die mdf_guard fehlte. Nur legale Information."""
    from knowledge_base.math.formulas import equity_needed_to_call
    from pokerbot.engine.equity import equity_vs_weighted_range
    from pokerbot.strategy.range_tracker import RangeTracker

    def make(seat):
        base = make_strat(seat)

        def d(st):
            a, amt = base(st)
            me = st["players"][st["to_act"]]
            to_call = max(0, st["current_bet"] - me["committed_street"])
            if a == "fold" and to_call > 0 and st["street"] == "flop":
                try:
                    t = RangeTracker().build(st)
                    cw = t.range.get(1 - st["to_act"], {})
                    if cw:
                        eq = equity_vs_weighted_range(me["hole"], cw, st["board"], iters=iters)
                        if eq == eq and eq >= equity_needed_to_call(st["pot"], to_call) + margin:
                            return "call", None
                except Exception:
                    pass                    # defensiv: im Zweifel bleibt der Basis-Fold
            return a, amt
        return d
    return make


def lizenz_guard(make_strat, junk_eq: float = 0.20, iters: int = 160):
    """Kandidat Runde 3 -- die Brown-Anpassung, Bet-Seite: Bluffs brauchen eine
    LIZENZ. Browns pure Bluffs leben im Equity-Band 0,36-0,50 (Zyklus-Region),
    NICHT am Boden der Verteilung. Dieser Guard unterdrueckt lizenzlosen Spew:
    Bettet/raist die Basis am Flop/Turn mit Equity vs Tracker-Range unter
    junk_eq (reiner Junk, keine Zyklus-Zugehoerigkeit), wird daraus Check bzw.
    Fold. Value und lizenzierte Bluffs bleiben unangetastet. Nur legale Info."""
    from pokerbot.engine.equity import equity_vs_weighted_range
    from pokerbot.strategy.range_tracker import RangeTracker

    def make(seat):
        base = make_strat(seat)

        def d(st):
            a, amt = base(st)
            me = st["players"][st["to_act"]]
            to_call = max(0, st["current_bet"] - me["committed_street"])
            # 'bet' MUSS dabei sein: die Eroeffnungs-Bet heisst in der Engine 'bet',
            # nicht 'raise' -- ohne sie sah der Guard nur 3 Knoten in 300 Haenden
            # (Diagnose 2026-08-16, toter Wrapper statt leerer Kanal).
            if a in ("bet", "raise", "allin") and st["street"] in ("flop", "turn"):
                try:
                    t = RangeTracker().build(st)
                    cw = t.range.get(1 - st["to_act"], {})
                    if cw:
                        eq = equity_vs_weighted_range(me["hole"], cw, st["board"], iters=iters)
                        if eq == eq and eq < junk_eq:
                            return ("check", None) if to_call == 0 else ("fold", None)
                except Exception:  # noqa: BLE001
                    pass            # defensiv: im Zweifel bleibt die Basis-Aktion
            return a, amt
        return d
    return make


def einmal_guard(make_strat, margin: float = 0.03, iters: int = 160):
    """Runde-4-Kandidat MEHRSTRASSEN-DISZIPLIN (Snowie-Befund: die groesste
    Blunder-Klasse waren Call-KETTEN -- der Guard rettet am Flop, danach callt
    die Basis Turn und River hinterher). Regel: die Selektion darf eine Hand
    nur EINMAL retten; ab der zweiten Rettungs-Gelegenheit derselben Hand gilt
    die Basis-Entscheidung."""
    from knowledge_base.math.formulas import equity_needed_to_call
    from pokerbot.engine.equity import equity_vs_weighted_range
    from pokerbot.strategy.range_tracker import RangeTracker

    def make(seat):
        base = make_strat(seat)
        zustand = {"hand": None, "gerettet": False}

        def d(st):
            if st.get("hand_no") != zustand["hand"]:
                zustand["hand"], zustand["gerettet"] = st.get("hand_no"), False
            a, amt = base(st)
            me = st["players"][st["to_act"]]
            to_call = max(0, st["current_bet"] - me["committed_street"])
            if (a == "fold" and to_call > 0 and st["street"] == "flop"
                    and not zustand["gerettet"]):
                try:
                    t = RangeTracker().build(st)
                    cw = t.range.get(1 - st["to_act"], {})
                    if cw:
                        eq = equity_vs_weighted_range(me["hole"], cw, st["board"], iters=iters)
                        if eq == eq and eq >= equity_needed_to_call(st["pot"], to_call) + margin:
                            zustand["gerettet"] = True
                            return "call", None
                except Exception:  # noqa: BLE001
                    pass
            return a, amt
        return d
    return make


def guarded(make_strat, guard_names: list[str]):
    """Wrapper-Fabrik: legt die Guard-Regeln um eine bestehende Strategie-Fabrik."""
    def make(seat):
        base = make_strat(seat)
        def d(st):
            a, amt = base(st)
            me = st["players"][st["to_act"]]
            to_call = max(0, st["current_bet"] - me["committed_street"])
            if to_call == 0:
                for g in guard_names:
                    a, amt = GUARDS[g][1](a, amt, st)
            return a, amt
        return d
    return make


def _journal(entry: dict) -> None:
    JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    entry["ts"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with JOURNAL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def gate_ab(make_candidate, make_incumbent, n_decks: int, seed: int) -> dict:
    """Das gepaarte A/B-Gate. Positiv nur bei |Effekt| > 2*SE; ANWENDEN nur, wenn
    der Kandidat zusaetzlich nicht unter -1 bb/100 liegt (Nichtverschlechterung)."""
    decks = gen_decks(n_decks, seed=seed)
    bb100, se = duplicate_ab(make_candidate, make_incumbent, decks)
    if bb100 - 2 * se > 0:
        verdict = "ANWENDEN"            # signifikant besser
    elif bb100 + 2 * se < -1.0:
        verdict = "VERWERFEN"           # signifikant schlechter als die Toleranz
    else:
        verdict = "NEUTRAL"             # kein Effekt nachweisbar -> Status quo behalten
    return {"bb100": round(bb100, 2), "se": round(se, 2), "n_decks": n_decks,
            "verdict": verdict}


def improve_round(hu_report: OracleReport, n_decks: int = 150, seed: int = 11,
                  exploit: bool = True) -> list[dict]:
    """Eine Runde der Schleife ueber die HU-Befunde. Gibt die Journal-Eintraege zurueck."""
    out = []

    # 1) P-Befunde -> autonome Guard-Patches, jeder einzeln durchs Gate.
    fired = {v.rule for v in hu_report.provable if v.rule in GUARDS}
    for rule in sorted(fired):
        res = gate_ab(guarded(pokerbot(exploit=exploit), [rule]),
                      pokerbot(exploit=exploit), n_decks, seed)
        entry = {"typ": "P-AUTOPATCH", "regel": rule,
                 "beschreibung": GUARDS[rule][0], **res}
        _journal(entry)
        out.append(entry)

    # 2) L/F-Befunde -> Vorschlaege ins Journal (keine autonome Anwendung).
    for v in hu_report.freq:
        entry = {"typ": "F-VORSCHLAG", "regel": v.rule, "befund": v.proof,
                 "verdict": "EXPERIMENT-KANDIDAT"}
        _journal(entry)
        out.append(entry)
    top_leads = sorted(hu_report.leads, key=lambda v: -v.severity_bb)[:3]
    for v in top_leads:
        entry = {"typ": "L-VORSCHLAG", "regel": v.rule,
                 "severity_bb": round(v.severity_bb, 2), "befund": v.proof,
                 "verdict": "EXPERIMENT-KANDIDAT"}
        _journal(entry)
        out.append(entry)
    return out
