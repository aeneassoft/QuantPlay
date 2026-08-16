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

from knowledge_base.math.formulas import equity_needed_to_call, minimum_defense_frequency
from pokerbot.engine.equity import equity_vs_hand

# L-Stufe: erst ab dieser Equity-Luecke wird ein Call als Lead gebucht. Die Marge
# frisst den Rueckschau-Bias (eine Hand ist nicht die Range) bewusst mit Reserve.
LEAD_MARGIN = 0.15
# MC-Praezision der Rueckschau-Equity; SE bei 200 Iterationen ~3.5pp << LEAD_MARGIN.
EQ_ITERS = 200
# F-Stufe: erlaubte Abweichung der Fold-Frequenz vom MDF-Ziel, bevor gemeldet wird.
MDF_BAND = 0.10


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


def grade_decision(rep: OracleReport, rec: dict, bb: int = 100) -> None:
    """Ein Entscheidungs-Datensatz aus dem Gym gegen die Benchmark.

    rec: street, pot, to_call, action, amount, hero_hole, board,
         villain_hole (None wenn multiway/unbekannt).
    """
    rep.decisions += 1
    action, to_call, pot = rec["action"], rec["to_call"], rec["pot"]

    # P: Fold, obwohl Checken frei war — dominiert, beweisbar, kein Kontext noetig.
    if action == "fold" and to_call <= 0:
        rep.provable.append(Verdict("P", "free_fold", pot / bb,
                                    f"fold bei to_call=0, Pot {pot} ({rec['street']})"))

    # F-Rohdaten: jede Entscheidung, die einem Einsatz gegenuebersteht.
    if to_call > 0 and action in ("fold", "call", "raise"):
        rep.facing_bets.append((rec["street"], pot, to_call, action == "fold"))

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


def grade_hand_conservation(rep: OracleReport, before: int, after: int, hand_no) -> None:
    """HART: die Chipsumme des Tischs muss jede Hand exakt erhalten bleiben."""
    if before != after:
        rep.hard.append(Verdict("HART", "chip_erhaltung", abs(after - before) / 100,
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
        if abs(observed - allowed) > MDF_BAND:
            rep.freq.append(Verdict(
                "F", f"mdf_{street}", 0.0,
                f"{street}: Fold-Frequenz {observed:.2f} vs MDF-erlaubt {allowed:.2f} "
                f"(n={len(rows)}, {'OVER-FOLD' if observed > allowed else 'UNDER-FOLD'})"))


def manifest() -> dict:
    """Der ehrliche Stand der Formalisierung: was verdrahtet ist, was noch nicht."""
    return {
        "verdrahtet_v0": [
            "equity_needed_to_call  (L: Pot-Odds-Rueckschau)",
            "minimum_defense_frequency  (F: MDF-Band je Strasse)",
            "Chip-Erhaltung  (HART)",
            "dominierte Aktion free_fold  (P)",
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
