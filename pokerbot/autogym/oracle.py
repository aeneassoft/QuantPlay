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
        eq = equity_vs_hand(rec["hero_hole"], rec["villain_hole"], rec["board"], iters=EQ_ITERS)
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
    if (action in ("raise", "allin") and rec.get("amount")
            and rec.get("villain_hole") and rec["street"] != "preflop"):
        risk = max(0, rec["amount"] - to_call)
        if risk > 0:
            eq = equity_vs_hand(rec["hero_hole"], rec["villain_hole"], rec["board"], iters=EQ_ITERS)
            fe_req = required_fold_equity(pot, risk, risk, eq)
            if fe_req > FE_CEILING:
                rep.leads.append(Verdict(
                    "L", "bet_braucht_unplausible_folds", 0.0,
                    f"{rec['street']}: FE_req {fe_req:.2f} > {FE_CEILING} "
                    f"(eq {eq:.2f}, Risiko {risk}, Pot {pot})"))

    # L: Call deutlich unter der Pot-Odds-Schwelle, in Rueckschau-Equity.
    if action == "call" and to_call > 0 and rec.get("villain_hole"):
        req = equity_needed_to_call(pot, to_call)
        eq = equity_vs_hand(rec["hero_hole"], rec["villain_hole"], rec["board"], iters=EQ_ITERS)
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
        ],
        "offen": [
            "compute_pot_odds", "expected_value", "bluff_to_value_and_frequencies",
            "required_future_winnings_for_implied_odds", "required_fold_equity",
            "outs_to_equity_rule_2_and_4", "compute_spr",
            "count_hand_combos_with_blockers", "breakeven_bluff_percentage",
            "equity_realization",
            "34 Postflop-Formeln aus knowledge_base/math (DSL-Konvertierung, NOTES.md)",
        ],
    }
