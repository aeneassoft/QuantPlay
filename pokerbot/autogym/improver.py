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
