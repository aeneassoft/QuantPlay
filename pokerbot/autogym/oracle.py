"""AUTOGYM-ORAKEL — die vereinheitlichte Mathematik-Benchmark (v0).

Formalisiert die Formelsammlung (knowledge_base/math/formulas.py) zu maschinell
pruefbaren Urteilen ueber echte Self-Play-Entscheidungen. Vier Stufen, getrennt,
weil sie verschieden belastbar sind:

  HART  nie verstellbare Invarianten (Chip-Erhaltung). Ein Verstoss ist ein BUG,
        kein Stil. Diese Stufe ist das Scoreboard selbst (CLAUDE.md) und darf
        von keinem Improver angefasst werden.
  P     pro Entscheidung BEWEISBARE Fehler (dominierte Aktionen, z.B. Fold bei
        to_call=0). Die einzige Klasse, die der Improver autonom patchen darf —
        und auch dann nur als Wrapper-Regel HINTER dem gepaarten A/B-Gate.
  L     Leads: Rueckschau-Equity vs. der TATSAECHLICHEN Gegnerhand mit grosser
        Marge. Einzeln verrauscht (der Gegner haette eine andere Hand halten
        koennen), aggregiert ein Leck-Detektor. Nie ein Beweis (money_mine-Logik).
  F     Frequenz-Abweichungen vs. Mathe-Ziel (MDF-Band). Nur ueber viele Haende
        definiert; erzeugt Vorschlaege, nie automatische Patches.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from knowledge_base.math.formulas import (equity_needed_to_call,
                                          minimum_defense_frequency,
                                          required_fold_equity)
from knowledge_base.math.postflop_formulas import exact_two_card_draw_equity
from pokerbot.engine.equity import equity_vs_hand

# L-Stufe: erst ab dieser Equity-Luecke wird ein Call als Lead gebucht. Die Marge
# frisst den Rueckschau-Bias (eine Hand ist nicht die Range) bewusst mit Reserve.
LEAD_MARGIN = 0.15
# MC-Praezision der Rueckschau-Equity; SE bei 200 Iterationen ~3.5pp << LEAD_MARGIN.
EQ_ITERS = 200
# F-Stufe: erlaubte Abweichung der Fold-Frequenz vom MDF-Ziel, bevor gemeldet wird.
MDF_BAND = 0.10
# W1-2 (HERABGESTUFT P->L, 2026-08-16): 'Call ohne Odds' ist NUR beweisbar, wenn
# Hero sicher hinten ist -- das weiss man ohne Gegnerhand nie (Value-Call moeglich).
# Darum Lead-Stufe, dafuer range-frei: die OPTIMISTISCHE Out-Obergrenze eines
# Draws im Holdem (Monster-Draw ~21 Outs) deckt die Pot-Odds nicht.
OUTS_CEILING = 21
# W1-3 (KORRIGIERT, 2026-08-16): die Inventur-Regel 'FE_req > 1' ist leer -- bei
# Fold-Frequenz 1 ist EV = Pot > 0, also ist FE_req IMMER < 1. Der echte Check:
# die noetige Fold-Frequenz uebersteigt eine plausible Obergrenze.
FE_CEILING = 0.75
# W1-1-ERSTKALIBRIERUNG (2026-08-16, VOR Validierung des Checks, journalfaehig):
# der Fold-Spiegel braucht eine STRENGERE Marge als der Call-Check — jeder Fold
# gegen einen geglueckten Bluff hat hohe Rueckschau-Equity (unvermeidbares
# Poker, kein Leak). 0.15 feuerte auf dem gesunden Bot mit 6,5% (gemessen);
# 0.30 verlangt einen krassen Ueberschuss. Keine Post-hoc-Justierung eines
# validierten Instruments, sondern die Erstkalibrierung eines neuen.
FOLD_LEAD_MARGIN = 0.30
# W1-4 (NEU 2026-08-17; Erstkalibrierung v2 nach adversarischem Design-Review,
# VOR Validierung, journalfaehig): die BETTOR-Seite, auf der das Orakel bisher
# strukturell blind war — der aelteste, 3x belegte Leak (Turn-Check mit
# Ueberpaar/Trips+; Snowie-Klasse B 11/39). Bedingungen (SELEKTION, nicht
# nackte eq-Schwelle — sonst Frequenz-Detektor, der 3x widerlegte Fehlertyp):
#   (1) Hero CHECKT turn/river ohne Einsatz vor sich,
#   (2) Made-Hand-Klassen-Gate wie der turn_wert_guard (Trips+ / Two Pair mit
#       Hole-Beteiligung / Ueberpaar),
#   (3) Rueckschau-eq >= WERT_MARGIN vs die tatsaechliche Gegnerhand,
#   (4) ZAHLUNGSFAEHIGKEIT: eq <= 0.90 ODER Villain haelt Paar+ — eliminiert
#       die Drawing-dead-Phantom-severity (Bet gegen geplatzte Haende foldet
#       alles Schlechtere; Check-Induce ist dort die bessere Linie).
# severity = (min(eq,0.95)-WERT_MARGIN) * min(pot, effective_stack) — Deckel
# gegen Ueberbepreisung. Slowplay/Trapping bleibt Seesaw-konform -> LEAD-
# Detektor im ARM-VERGLEICH je GELEGENHEIT, nie Einzelhand-Beweis; Klasse->0
# waere ein ROTES TUCH (Purify-Muster), kein Sieg.
WERT_MARGIN = 0.75
_RANK_ORD = {r: i for i, r in enumerate("23456789TJQKA")}


def _made_klasse(hole: list, board: list):
    """treys-Rangklasse (1=SF..9=High) der Made Hand; None wenn treys fehlt."""
    try:
        from treys import Evaluator
        from pokerbot.engine.evaluator import evaluate
        return Evaluator().get_rank_class(evaluate(board, hole))
    except Exception:  # noqa: BLE001
        return None


def _starke_made_hand(hole: list, board: list) -> bool:
    """Das Klassen-Gate des turn_wert_guard, orakel-seitig gespiegelt."""
    kl = _made_klasse(hole, board)
    if kl is None:
        return False
    hole_pair = hole[0][0] == hole[1][0]
    board_ranks = [b[0] for b in board]
    beteiligt = hole_pair or any(hc[0] in board_ranks for hc in hole)
    ueberpaar = (hole_pair and kl == 8
                 and _RANK_ORD[hole[0][0]] > max(_RANK_ORD[r] for r in board_ranks))
    return kl <= 6 or (kl == 7 and beteiligt) or ueberpaar


def _rec_rng(rec: dict):
    """Deterministischer REKORD-gebundener RNG fuer die Rueckschau-Equity
    (Messfundament 2026-08-17): dieselbe Entscheidung ergibt dasselbe Urteil,
    lauf- und prozessuebergreifend. Vorher lief jeder equity_vs_hand-Aufruf
    auf frischem random.Random() -> das Orakel war nicht-deterministisch."""
    import random
    import zlib
    key = "|".join((",".join(rec.get("hero_hole") or []),
                    ",".join(rec.get("villain_hole") or []),
                    ",".join(rec.get("board") or []),
                    str(rec.get("street")), str(rec.get("pot"))))
    return random.Random(zlib.crc32(key.encode()))


@dataclass
class Verdict:
    tier: str          # 'HART' | 'P' | 'L' | 'F'
    rule: str
    severity_bb: float  # geschaetzte EV-Kosten in bb (0 wenn nicht bezifferbar)
    proof: str


@dataclass
class OracleReport:
    decisions: int = 0
    hard: list[Verdict] = field(default_factory=list)
    provable: list[Verdict] = field(default_factory=list)
    leads: list[Verdict] = field(default_factory=list)
    freq: list[Verdict] = field(default_factory=list)
    # Rohdaten der F-Stufe: (street, pot, bet, folded)
    facing_bets: list[tuple] = field(default_factory=list)

    def counts(self) -> dict:
        return {"decisions": self.decisions, "HART": len(self.hard),
                "P": len(self.provable), "L": len(self.leads), "F": len(self.freq)}


def grade_decision(rep: OracleReport, rec: dict, bb: int = 100) -> bool:
    """Ein Entscheidungs-Datensatz aus dem Gym gegen die Benchmark.

    rec: street, pot, to_call, action, amount, hero_hole, board,
         villain_hole (None wenn multiway/unbekannt).
    """
    rep.decisions += 1
    vorher = len(rep.provable) + len(rep.leads)
    action, to_call, pot = rec["action"], rec["to_call"], rec["pot"]

    # P: Fold, obwohl Checken frei war — dominiert, beweisbar, kein Kontext noetig.
    if action == "fold" and to_call <= 0:
        rep.provable.append(Verdict("P", "free_fold", pot / bb,
                                    f"fold bei to_call=0, Pot {pot} ({rec['street']})"))

    # F-Rohdaten: jede POSTFLOP-Entscheidung gegen einen Einsatz. 'allin' zaehlt
    # als Continue (Review-Befund: sonst fehlen die aggressivsten Continues und
    # die Fold-Frequenz wird nach oben verzerrt). Preflop bleibt draussen —
    # Blind-Struktur/First-in macht die MDF-Logik dort schief.
    # KONVENTION: minimum_defense_frequency braucht den Pot VOR dem Einsatz,
    # st['pot'] ist aber einsatz-INKLUSIV -> pot - to_call speichern.
    # (equity_needed_to_call unten will dagegen den INKLUSIVEN Pot — die beiden
    # Formeln haben entgegengesetzte Pot-Konventionen.)
    if (to_call > 0 and rec["street"] != "preflop"
            and action in ("fold", "call", "raise", "allin")):
        rep.facing_bets.append((rec["street"], pot - to_call, to_call, action == "fold"))

    # W1-1 (L): Fold TROTZ ausreichender Equity -- der Spiegel des Call-Checks.
    if action == "fold" and to_call > 0 and rec.get("villain_hole"):
        req = equity_needed_to_call(pot, to_call)
        eq = equity_vs_hand(rec["hero_hole"], rec["villain_hole"], rec["board"],
                            iters=EQ_ITERS, rng=_rec_rng(rec))
        if eq - req > FOLD_LEAD_MARGIN:
            rep.leads.append(Verdict(
                "L", "fold_ueber_pot_odds", (eq - req) * (pot + to_call) / bb,
                f"{rec['street']}: eq {eq:.2f} vs noetig {req:.2f} "
                f"(Ueberschuss {eq - req:.2f}, to_call {to_call}, Pot {pot})"))

    # W1-2 (L, range-frei -> laeuft auch 6-max): Call, der die Action schliesst
    # (keine Implied Odds), obwohl selbst die OPTIMISTISCHE Draw-Obergrenze die
    # Pot-Odds nicht deckt. flop: 2 Karten kommen; turn: 1 Karte (outs/46).
    if (action == "call" and to_call > 0 and rec.get("call_closes_action")
            and rec["street"] in ("flop", "turn")):
        req = equity_needed_to_call(pot, to_call)
        ceiling = (exact_two_card_draw_equity(OUTS_CEILING) if rec["street"] == "flop"
                   else OUTS_CEILING / 46.0)
        if req > ceiling + 0.02:
            rep.leads.append(Verdict(
                "L", "allin_call_ohne_odds", (req - ceiling) * (pot + to_call) / bb,
                f"{rec['street']}: noetig {req:.2f} > Draw-Obergrenze {ceiling:.2f} "
                f"(to_call {to_call}, Pot {pot}, Action geschlossen)"))

    # W1-3 (L, korrigiert): Hero-Bet/Raise, dessen noetige Fold-Frequenz bei
    # Rueckschau-Equity eine plausible Obergrenze uebersteigt.
    # FIX 2026-08-17 (Armee, BESTAETIGT): (a) 'bet' fehlte im Filter — jede
    # Eroeffnungs-Bet (die Hauptmasse) war fuer W1-3 unsichtbar (dieselbe Falle
    # wie beim lizenz_guard); (b) risk war das Raise-INKREMENT, Heros echtes
    # Zusatz-Risiko ist R = risk + to_call (cs=0-Normalfall; bei bet identisch).
    # MESS-INSTRUMENT-AENDERUNG: L-Zaehlungen vor/nach diesem Fix sind nicht
    # vergleichbar; FE_CEILING ist danach neu zu kalibrieren (Journal-Pflicht).
    _w13_amount = rec.get("amount")
    if _w13_amount is None and action == "allin":
        _w13_amount = rec.get("effective_stack")      # approximativ, journalfaehig
    if (action in ("bet", "raise", "allin") and _w13_amount
            and rec.get("villain_hole") and rec["street"] != "preflop"):
        risk = max(0, _w13_amount - to_call)
        if risk > 0:
            eq = equity_vs_hand(rec["hero_hole"], rec["villain_hole"], rec["board"],
                                iters=EQ_ITERS, rng=_rec_rng(rec))
            fe_req = required_fold_equity(pot, risk + to_call, risk, eq)
            if fe_req > FE_CEILING:
                rep.leads.append(Verdict(
                    "L", "bet_braucht_unplausible_folds", 0.0,
                    f"{rec['street']}: FE_req {fe_req:.2f} > {FE_CEILING} "
                    f"(eq {eq:.2f}, Risiko {risk}, Pot {pot})"))

    # W1-4 (L): VERPASSTER WERT — selektions-gegatet, s. Kalibrierungs-Block oben.
    if (action == "check" and to_call <= 0 and rec.get("villain_hole")
            and rec["street"] in ("turn", "river")
            and _starke_made_hand(rec["hero_hole"], rec["board"])):
        eq = equity_vs_hand(rec["hero_hole"], rec["villain_hole"], rec["board"],
                            iters=EQ_ITERS, rng=_rec_rng(rec))
        v_kl = _made_klasse(rec["villain_hole"], rec["board"])
        # Praezisions-Fix (Armee): auf GEPAARTEN Boards ist die rohe treys-Klasse
        # immer 'Paar' — Zahlungsfaehigkeit verlangt HOLE-Beteiligung des Villains.
        v_h = rec["villain_hole"]
        v_beteiligt = (v_h[0][0] == v_h[1][0]
                       or any(hc[0] in [b[0] for b in rec["board"]] for hc in v_h))
        zahlungsfaehig = eq <= 0.90 or (v_kl is not None and v_kl <= 8 and v_beteiligt)
        if eq >= WERT_MARGIN and zahlungsfaehig:
            deckel = min(pot, rec.get("effective_stack", pot))
            rep.leads.append(Verdict(
                "L", f"verpasster_wert_{rec['street']}",
                (min(eq, 0.95) - WERT_MARGIN) * deckel / bb,
                f"{rec['street']}: check mit eq {eq:.2f} >= {WERT_MARGIN} "
                f"(Pot {pot}, Deckel {deckel})"))

    # W1-5 (L, NEU 2026-08-17, Erstkalibrierung VOR Validierung): VERPASSTER
    # RAISE — die K5-Seite (Raise-Armut 0-4% der Empfehlung): CALL am Turn/River
    # mit Monster-Rueckschau-eq, wo selbst der fold_equity-FREIE Min-Raise-EV
    # den Call-EV schlaegt (Fold-Equity kann den Raise nur verbessern).
    if (action == "call" and to_call > 0 and rec.get("villain_hole")
            and rec["street"] in ("turn", "river")
            and _starke_made_hand(rec["hero_hole"], rec["board"])):
        eq = equity_vs_hand(rec["hero_hole"], rec["villain_hole"], rec["board"],
                            iters=EQ_ITERS, rng=_rec_rng(rec))
        if eq >= WERT_MARGIN:
            risk = min(2 * to_call, rec.get("effective_stack", 2 * to_call))
            ev_call = eq * (pot + to_call) - to_call
            ev_raise = eq * (pot + to_call + 2 * (risk - to_call)) - risk
            if ev_raise > ev_call:
                rep.leads.append(Verdict(
                    "L", "verpasster_raise", (ev_raise - ev_call) / bb,
                    f"{rec['street']}: call mit eq {eq:.2f} (to_call {to_call}, "
                    f"Min-Raise-EV {ev_raise:.0f} > Call-EV {ev_call:.0f})"))

    # L: Call deutlich unter der Pot-Odds-Schwelle, in Rueckschau-Equity.
    if action == "call" and to_call > 0 and rec.get("villain_hole"):
        req = equity_needed_to_call(pot, to_call)
        eq = equity_vs_hand(rec["hero_hole"], rec["villain_hole"], rec["board"],
                            iters=EQ_ITERS, rng=_rec_rng(rec))
        gap = req - eq
        if gap > LEAD_MARGIN:
            rep.leads.append(Verdict(
                "L", "call_unter_pot_odds", gap * (pot + to_call) / bb,
                f"{rec['street']}: eq {eq:.2f} vs noetig {req:.2f} "
                f"(Luecke {gap:.2f}, to_call {to_call}, Pot {pot})"))


    return len(rep.provable) + len(rep.leads) > vorher


def grade_hand_conservation(rep: OracleReport, before: int, after: int, hand_no,
                            bb: int = 100) -> None:
    """HART: die Chipsumme des Tischs muss jede Hand exakt erhalten bleiben."""
    if before != after:
        rep.hard.append(Verdict("HART", "chip_erhaltung", abs(after - before) / bb,
                                f"Hand {hand_no}: Summe {before} -> {after}"))


def finalize_frequencies(rep: OracleReport) -> None:
    """F: beobachtete Fold-Frequenz je Strasse gegen das MDF-Ziel der Formelsammlung."""
    by_street: dict[str, list[tuple]] = {}
    for street, pot, bet, folded in rep.facing_bets:
        by_street.setdefault(street, []).append((pot, bet, folded))
    for street, rows in by_street.items():
        if len(rows) < 30:              # unter n=30 ist die Frequenz kein Signal
            continue
        # MDF = Anteil, der WEITERSPIELEN muss -> erlaubte Fold-Frequenz = 1 - MDF.
        allowed = sum(1.0 - minimum_defense_frequency(p, b) for p, b, _ in rows) / len(rows)
        observed = sum(1 for _, _, f in rows if f) / len(rows)
        # MDF ist eine OBERGRENZE fuers Folden, kein Sollwert: nur OVER-FOLD ist
        # ein Befund — weniger folden als erlaubt ist MDF-theoretisch kein Defekt.
        if observed - allowed > MDF_BAND:
            rep.freq.append(Verdict(
                "F", f"mdf_{street}", 0.0,
                f"{street}: Fold-Frequenz {observed:.2f} vs MDF-erlaubt {allowed:.2f} "
                f"(n={len(rows)}, OVER-FOLD)"))


def manifest() -> dict:
    """Der ehrliche Stand der Formalisierung: was verdrahtet ist, was noch nicht."""
    return {
        "verdrahtet_v0": [
            "equity_needed_to_call  (L: Pot-Odds-Rueckschau)",
            "minimum_defense_frequency  (F: MDF-Band je Strasse)",
            "Chip-Erhaltung  (HART)",
            "dominierte Aktion free_fold  (P)",
            "expected_value-Spiegel: fold_ueber_pot_odds  (L, W1-1)",
            "exact_two_card_draw_equity: allin_call_ohne_odds  (L, W1-2, P->L herabgestuft)",
            "required_fold_equity: bet_braucht_unplausible_folds  (L, W1-3, korrigiert)",
            "verpasster_wert_{turn,river}  (L, W1-4: Bettor-Seite, selektions-gegated)",
            "verpasster_raise  (L, W1-5: Raise-Seite, K5-Detektor)",
        ],
        "offen": [
            "compute_pot_odds", "expected_value", "bluff_to_value_and_frequencies",
            "required_future_winnings_for_implied_odds",
            "outs_to_equity_rule_2_and_4", "compute_spr",
            "count_hand_combos_with_blockers", "breakeven_bluff_percentage",
            "equity_realization",
            "34 Postflop-Formeln aus knowledge_base/math (DSL-Konvertierung, docs/NOTES.md)",
        ],
    }
