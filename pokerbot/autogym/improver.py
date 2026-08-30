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
import random
import time
import zlib
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

# Kartenrang-Ordnung fuer Made-Hand-Checks ('As' -> 'A'); treys-kompatibel.
_RANK_ORD = {r: i for i, r in enumerate("23456789TJQKA")}


def _spot_rng(st: dict) -> random.Random:
    """Deterministischer, SPOT-gebundener RNG fuer alle Guard-Equity-Aufrufe
    (Messfundament 2026-08-17): gleiche Karten/Strasse/Pot-Lage => gleiche
    MC-Schaetzung, in JEDEM Arm des Gates und in jedem Prozess. Ersetzt
    (a) ungeseedetes random.Random() (brach die Deck-Paarung: Transfer-Test
    SE 12,9 trotz identischer Decks) und (b) pro-Seat-Sequenzen (die
    Aufruf-REIHENFOLGE desynct die Arme, sobald eine Entscheidung abweicht)."""
    me = st["players"][st["to_act"]]
    key = "|".join((",".join(sorted(me["hole"])), ",".join(st["board"]),
                    str(st["street"]), str(st["pot"]), str(st["current_bet"]),
                    str(me["committed_street"]),
                    str(len(st.get("history", [])))))   # Kollisions-Schutz: gleiche Lage, andere Line
    return random.Random(zlib.crc32(key.encode()))


def podds_guard(make_strat, margin: float = 0.02, iters: int = 120):
    """Der erste aus dem Journal MOTIVIERTE Bot-Kandidat (L: call_unter_pot_odds):
    River-Call nur, wenn die Equity vs eine UNIFORME Gegner-Range die Pot-Odds
    deckt. Nutzt NUR legale Information (eigene Karten, Board, Pot) -- die
    Rueckschau-Gegnerhand des Orakels beruehrt er nie. Ob die uniforme Range zu
    pessimistisch ist (Value-Folds!), entscheidet allein das gepaarte Gate."""
    from knowledge_base.math.formulas import equity_needed_to_call
    from pokerbot.engine.cards import make_deck
    from pokerbot.engine.equity import equity_vs_range

    def make(seat):
        base = make_strat(seat)

        def d(st):
            a, amt = base(st)
            me = st["players"][st["to_act"]]
            to_call = max(0, st["current_bet"] - me["committed_street"])
            if a == "call" and to_call > 0 and st["street"] == "river":
                rng = _spot_rng(st)
                dead = set(me["hole"]) | set(st["board"])
                deck = [c for c in make_deck() if c not in dead]
                combos = [tuple(rng.sample(deck, 2)) for _ in range(40)]
                eq = equity_vs_range(me["hole"], combos, st["board"], iters=iters, rng=rng)
                if eq + margin < equity_needed_to_call(st["pot"], to_call):
                    return "fold", None
            return a, amt
        return d
    return make


def mdf_guard(make_strat, margin: float = 0.0, iters: int = 120,
              streets: tuple = ("flop",)):
    """Kandidat aus dem F-Befund mdf_flop (OVER-FOLD 0,61 vs erlaubt 0,32):
    ein Flop-Fold gegen einen Einsatz wird zum Call, wenn die Equity vs eine
    uniforme Range die Pot-Odds deckt. Nur legale Information. Die Doktrin
    kennt das Risiko (Frequenz-Matching 3x widerlegt) -- das Gate urteilt.
    FIX 2026-08-17: der streets-Check aus Commit 95d0ce9 landete hier statt in
    sel_guard UND referenzierte einen nie definierten Namen (NameError bei jedem
    Facing-Bet-Fold) -- jetzt echter Parameter."""
    from knowledge_base.math.formulas import equity_needed_to_call
    from pokerbot.engine.cards import make_deck
    from pokerbot.engine.equity import equity_vs_range

    def make(seat):
        base = make_strat(seat)

        def d(st):
            a, amt = base(st)
            me = st["players"][st["to_act"]]
            to_call = max(0, st["current_bet"] - me["committed_street"])
            if a == "fold" and to_call > 0 and st["street"] in streets:
                rng = _spot_rng(st)
                dead = set(me["hole"]) | set(st["board"])
                deck = [c for c in make_deck() if c not in dead]
                combos = [tuple(rng.sample(deck, 2)) for _ in range(40)]
                eq = equity_vs_range(me["hole"], combos, st["board"], iters=iters, rng=rng)
                if eq >= equity_needed_to_call(st["pot"], to_call) + margin:
                    return "call", None
            return a, amt
        return d
    return make


def sel_guard(make_strat, margin: float = 0.03, iters: int = 160,
              streets: tuple = ("flop",)):
    """Kandidat 3 -- SELEKTION statt Frequenz (die Lehre aus Runde 1): ein
    Fold gegen einen Einsatz wird NUR dann zum Call, wenn die Equity vs
    die TRACKER-Range des Gegners (Bayes ueber die gespielte Linie, History
    steht im State) die Pot-Odds plus Marge deckt. Trash foldet weiter --
    genau die Selektion, die mdf_guard fehlte. Nur legale Information.
    FIX 2026-08-17: streets war seit Commit 95d0ce9 unverdrahtet (Body
    hardcodete flop) -- sel_all wurde damals als A-vs-A gemessen; das
    Journal-Verdikt 'Turn/River-Selektion abgelehnt' ist NICHTIG."""
    from knowledge_base.math.formulas import equity_needed_to_call
    from pokerbot.engine.equity import equity_vs_weighted_range
    from pokerbot.strategy.range_tracker import RangeTracker

    def make(seat):
        base = make_strat(seat)

        def d(st):
            a, amt = base(st)
            me = st["players"][st["to_act"]]
            to_call = max(0, st["current_bet"] - me["committed_street"])
            if a == "fold" and to_call > 0 and st["street"] in streets:
                try:
                    t = RangeTracker().build(st)
                    cw = t.range.get(1 - st["to_act"], {})
                    if cw:
                        eq = equity_vs_weighted_range(me["hole"], cw, st["board"],
                                                      iters=iters, rng=_spot_rng(st))
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
                        eq = equity_vs_weighted_range(me["hole"], cw, st["board"],
                                                      iters=iters, rng=_spot_rng(st))
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
                        eq = equity_vs_weighted_range(me["hole"], cw, st["board"],
                                                      iters=iters, rng=_spot_rng(st))
                        if eq == eq and eq >= equity_needed_to_call(st["pot"], to_call) + margin:
                            zustand["gerettet"] = True
                            return "call", None
                except Exception:  # noqa: BLE001
                    pass
            return a, amt
        return d
    return make


def turn_wert_guard(make_strat, frac: float = 0.66, min_eq: float = 0.60, iters: int = 160):
    """Runde-5-Kandidat TURN-WERT -- der aelteste, 3x belegte Leak (Snowie-Klasse B:
    Turn-Check mit Ueberpaar/Trips+; Turn-Betting bei 0-19% der Empfehlung; die
    GTOW-Zerlegung nennt denselben Knoten). SELEKTIONS-Regel auf der BET-Seite:
    checkt die Basis am Turn ohne Einsatz vor sich, wird daraus eine ~2/3-Pot-
    Value-Bet, wenn (a) die Made Hand STARK ist (Trips+ ODER Two Pair/Ueberpaar
    mit Hole-Beteiligung) UND (b) die Equity vs die Tracker-Range min_eq deckt.
    Beides ist AUSWAHL, keine Frequenz (Doktrin: Selektion schlaegt Frequenz).
    Nur legale Information; die Engine clampt den Betrag auf [raise_min, raise_max]."""
    from pokerbot.engine.equity import equity_vs_weighted_range
    from pokerbot.engine.evaluator import evaluate
    from pokerbot.strategy.range_tracker import RangeTracker
    try:
        from treys import Evaluator as _TreysEval
        _klasse = _TreysEval().get_rank_class          # 1=SF .. 6=Trips, 7=Two Pair, 8=Pair, 9=High
    except Exception:  # noqa: BLE001
        _klasse = None

    def make(seat):
        base = make_strat(seat)

        def d(st):
            a, amt = base(st)
            me = st["players"][st["to_act"]]
            opp = st["players"][1 - st["to_act"]]
            to_call = max(0, st["current_bet"] - me["committed_street"])
            if (a == "check" and to_call == 0 and st["street"] == "turn"
                    and _klasse is not None and me["stack"] > 0 and opp["stack"] > 0):
                try:
                    board = st["board"]
                    kl = _klasse(evaluate(board, me["hole"]))
                    hole_pair = me["hole"][0][0] == me["hole"][1][0]
                    board_ranks = [b[0] for b in board]
                    beteiligt = hole_pair or any(hc[0] in board_ranks for hc in me["hole"])
                    ueberpaar = (hole_pair and kl == 8
                                 and _RANK_ORD[me["hole"][0][0]] > max(_RANK_ORD[r] for r in board_ranks))
                    if kl <= 6 or (kl == 7 and beteiligt) or ueberpaar:
                        t = RangeTracker().build(st)
                        cw = t.range.get(1 - st["to_act"], {})
                        if cw:
                            eq = equity_vs_weighted_range(me["hole"], cw, board,
                                                          iters=iters, rng=_spot_rng(st))
                            if eq == eq and eq >= min_eq:
                                return "bet", int(frac * st["pot"])
                except Exception:  # noqa: BLE001
                    pass            # defensiv: im Zweifel bleibt der Basis-Check
            return a, amt
        return d
    return make



def river_ecall_guard(make_strat, marge: float = 0.05, iters: int = 200):
    """Runde-6-Kandidat aus dem Fable-Duell (River-Station: 4/5 grosse Calls mit
    Verlierern, ~90bb): River-CALL auf Bets >= 60% Pot nur, wenn die Equity vs
    die Tracker-Range die Pot-Odds + Marge deckt (River = exakte Enumeration,
    varianzfrei). SELEKTION auf der Call-Seite, K4-Haertung."""
    from knowledge_base.math.formulas import equity_needed_to_call
    from pokerbot.engine.equity import equity_vs_weighted_range
    from pokerbot.strategy.range_tracker import RangeTracker

    def make(seat):
        base = make_strat(seat)

        def d(st):
            a, amt = base(st)
            me = st["players"][st["to_act"]]
            to_call = max(0, st["current_bet"] - me["committed_street"])
            if (a == "call" and st["street"] == "river"
                    and to_call >= 0.6 * max(1, st["pot"] - to_call)):
                try:
                    t = RangeTracker().build(st)
                    cw = t.range.get(1 - st["to_act"], {})
                    if cw:
                        eq = equity_vs_weighted_range(me["hole"], cw, st["board"],
                                                      iters=iters, rng=_spot_rng(st))
                        if eq == eq and eq < equity_needed_to_call(st["pot"], to_call) + marge:
                            return "fold", None
                except Exception:  # noqa: BLE001
                    pass
            return a, amt
        return d
    return make


def _river_eq_exakt(hole, cw: dict, board) -> float:
    """Exakte Equity vs eine gewichtete Range am River (5 Board-Karten):
    reine Enumeration ueber alle Combos, KEIN RNG — paarungssicher und
    rauschfrei (die MC-Variante mit iters=200 traegt ~3,5pp SE; genau das
    Rauschen, an dem r6_ecall im Mirror scheiterte)."""
    from pokerbot.engine.evaluator import evaluate
    tot = set(hole) | set(board)
    hero_s = evaluate(board, list(hole))
    besser = schlechter = gleich = 0.0
    for (c1, c2), gew in cw.items():
        if gew <= 0 or c1 in tot or c2 in tot:
            continue
        s = evaluate(board, [c1, c2])          # treys: KLEINER = besser
        if s < hero_s:
            besser += gew
        elif s > hero_s:
            schlechter += gew
        else:
            gleich += gew
    masse = besser + schlechter + gleich
    return (schlechter + 0.5 * gleich) / masse if masse > 0 else float("nan")


def river_bill_guard(make_strat, marge: float = 0.04, overbet_marge: float = 0.02,
                     min_frac: float = 0.6, min_pot_chips: int = 3000):
    """Runde-7-Kandidat BIG-POT-RIVER-DEFENSE — der GEMESSEN groesste Leak der
    GTOW-Nacht 2 (hh_luecken_mine: 9 River-Riesenpot-Calls = -121bb = 59% des
    v4-Nettoverlusts; die Kontrolle blutet in derselben Zelle). Neubau nach der
    r6_ecall-Obduktion (Mirror -4,15 = Value-Folds): (1) EXAKTE Enumeration
    statt MC-200 (rauschfrei, RNG-frei), (2) Marge NEGATIV — gefoldet wird nur
    ein klar -EV-Call (eq < Pot-Odds MINUS marge), nie der Grenz-Call,
    (3) enger Trigger: nur grosse River-Bets (>= min_frac Pot) in grossen
    Toepfen (>= min_pot_chips final). Overbets/Jams (Bet >= Pot) sind
    polarisiert-value-lastig -> dort greift die engere overbet_marge."""
    from knowledge_base.math.formulas import equity_needed_to_call
    from pokerbot.strategy.range_tracker import RangeTracker

    def make(seat):
        base = make_strat(seat)

        def d(st):
            a, amt = base(st)
            me = st["players"][st["to_act"]]
            to_call = max(0, st["current_bet"] - me["committed_street"])
            pot_vor = max(1, st["pot"] - to_call)
            if (a == "call" and st["street"] == "river"
                    and to_call >= min_frac * pot_vor
                    and st["pot"] + to_call >= min_pot_chips):
                try:
                    t = RangeTracker().build(st)
                    cw = t.range.get(1 - st["to_act"], {})
                    if cw:
                        eq = _river_eq_exakt(me["hole"], cw, st["board"])
                        m_eff = overbet_marge if to_call >= pot_vor else marge
                        if eq == eq and eq < equity_needed_to_call(st["pot"], to_call) - m_eff:
                            return "fold", None
                except Exception:  # noqa: BLE001
                    pass            # defensiv: im Zweifel bleibt der Basis-Call
            return a, amt
        return d
    return make


def river_wert_bremse(make_strat, min_eq: float = 0.50):
    """Runde-7-Kandidat RIVER-WERT-BREMSE — zweitgroesster Nacht-2-Block
    (hh_luecken_mine: River-BETS in bessere Haende, ~-59bb; Typusfall #3001968
    Trips bettet 34bb in den offensichtlichen Nut-Flush). Regel: eine RIVER-Bet
    mit STARKER Made Hand (Two Pair+) ist eine Value-Bet — sie braucht eq >=
    min_eq vs die Tracker-Range, sonst ist die Hand auf diesem Board ein
    Bluffcatcher und der Check dominiert (Showdown-Value statt Bet in bessere).
    Bluffs/schwache Haende bleiben UNANGETASTET (Seesaw: die Bluff-Seite der
    Bet-Range wird nicht purifiziert). Nur der to_call==0-Knoten (bet->check);
    der Raise-Knoten bleibt bewusst v2 (ein Mechanismus pro Guard)."""
    from pokerbot.engine.evaluator import evaluate
    from pokerbot.strategy.range_tracker import RangeTracker
    try:
        from treys import Evaluator as _TreysEval
        _klasse = _TreysEval().get_rank_class          # 1=SF .. 7=Two Pair, 8=Pair
    except Exception:  # noqa: BLE001
        _klasse = None

    def make(seat):
        base = make_strat(seat)

        def d(st):
            a, amt = base(st)
            me = st["players"][st["to_act"]]
            to_call = max(0, st["current_bet"] - me["committed_street"])
            if (a == "bet" and to_call == 0 and st["street"] == "river"
                    and _klasse is not None):
                try:
                    kl = _klasse(evaluate(st["board"], me["hole"]))
                    if kl <= 7:                        # nur die Value-Absicht bremsen
                        t = RangeTracker().build(st)
                        cw = t.range.get(1 - st["to_act"], {})
                        if cw:
                            eq = _river_eq_exakt(me["hole"], cw, st["board"])
                            if eq == eq and eq < min_eq:
                                return "check", None
                except Exception:  # noqa: BLE001
                    pass            # defensiv: im Zweifel bleibt die Basis-Bet
            return a, amt
        return d
    return make


def button_disziplin_guard(make_strat):
    """Runde-6-Kandidat aus dem Fable-Duell (Button-Open-Fold ~29% = geschenkte
    0,5bb-Rente): der Button open-foldet in HU NIE — aus fold bei to_call=50
    preflop wird ein Open auf 250 (2,5x). Jede Hand realisiert mehr als den
    halben Blind zu diesem Preis (Fable-Zaehlung + HU-Basiswissen)."""
    def make(seat):
        base = make_strat(seat)

        def d(st):
            a, amt = base(st)
            me = st["players"][st["to_act"]]
            to_call = max(0, st["current_bet"] - me["committed_street"])
            if (a == "fold" and st["street"] == "preflop" and to_call == 50
                    and me["committed_street"] == 50):
                return "raise", 250
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
