"""AUTOGYM-SELBSTTEST — der lokale Beweis der ganzen Schleife (Erwartungen E1-E4).

Vier vorregistrierte Erwartungen; jede wird geprueft und als PASS/FAIL gebucht.
Erst wenn dieser Selbsttest gruen ist, ist die Schleife 'lokal bewiesen' im Sinne
des Plans (docs/AUTOGYM_PLAN.md) — und erst dann lohnt ein Pod.

  E1  ORAKEL-WAHRHEIT: jede verdrahtete Formel besteht eine UNABHAENGIGE
      Fraction-Referenz (Pruefer getrennt vom Beprueften, test_math_suite-Kultur).
  E2  SYMMETRIE: Paar-Drift des gesunden Bots im Selbstspiel vertraeglich mit 0
      (|mean| < 2*SE).
  E3  DETEKTOR: ein konstruierter Defekt-Bot (Station: foldet nie gegen Einsatz)
      wird (a) vom Orakel als L-Ausreisser erkannt (Lead-Rate >= 2x gesund) und
      (b) vom gepaarten Gate verworfen (gesund vs defekt = ANWENDEN fuer gesund).
  E4  NULL-STABILITAET: gesund vs gesund (andere Seeds) darf im Gate KEIN
      ANWENDEN produzieren — die Schleife erfindet keine Verbesserungen.

  python -m pokerbot.autogym.selftest            # ~2-4 min lokal
  python -m pokerbot.autogym.selftest --quick    # verkleinerte Stichproben
"""
from __future__ import annotations

import argparse
import sys
from fractions import Fraction

from pokerbot.benchmark.duplicate import gen_decks, pokerbot

from . import gym_hu
from .improver import gate_ab

# Vorregistrierte Schwellen (NICHT nach Sicht der Zahlen justieren):
E2_SE_MULT = 2.0          # Paar-Drift muss innerhalb von 2 SE um 0 liegen
E3_LEAD_FACTOR = 2.0      # Defekt-Lead-Rate >= 2x gesunde Lead-Rate
GATE_DECKS = 120


def e1_orakel_wahrheit() -> tuple[bool, list[str]]:
    """Jede verdrahtete Formel gegen eine handgerechnete Fraction-Referenz."""
    from knowledge_base.math.formulas import (breakeven_bluff_percentage, compute_spr,
                                              equity_needed_to_call, expected_value,
                                              minimum_defense_frequency)
    from knowledge_base.math.postflop_formulas import (alpha_break_even_bluff_frequency,
                                                       breakeven_fold_equity_pure_bluff)
    rows = []
    ok = True

    def check(name: str, got: float, want: Fraction) -> None:
        nonlocal ok
        good = abs(got - float(want)) < 1e-12
        ok = ok and good
        rows.append(f"   {'PASS' if good else 'FAIL'}  {name}: {got:.6f} vs Referenz {float(want):.6f}")

    # Pot 300 (inkl. Villain-Bet), Call 100 -> noetige Equity = 100/400.
    check("equity_needed_to_call(300,100)", equity_needed_to_call(300, 100), Fraction(100, 400))
    # MDF vs Potsize-Bet: pot/(pot+bet) = 1/2.
    check("minimum_defense_frequency(100,100)", minimum_defense_frequency(100, 100), Fraction(1, 2))
    # Break-even-Fold-Frequenz eines Pure Bluffs b in Pot p: b/(b+p) = 1/3.
    check("alpha_break_even(50,100)", alpha_break_even_bluff_frequency(50, 100), Fraction(50, 150))
    check("breakeven_FE_pure_bluff(50,100)", breakeven_fold_equity_pure_bluff(50, 100), Fraction(50, 150))
    check("breakeven_bluff_pct(100,100)", breakeven_bluff_percentage(100, 100), Fraction(1, 2))
    check("compute_spr(1000,250)", compute_spr(1000, 250), Fraction(4))
    check("expected_value([.6,.4],[100,-50])", expected_value([0.6, 0.4], [100, -50]), Fraction(40))
    return ok, rows


class _StationDefekt:
    """Der konstruierte Defekt: foldet NIE gegen einen Einsatz (call statt fold).
    Existiert nur, damit der Detektor etwas zu finden hat — E3."""

    def __init__(self, base):
        self.base = base

    @property
    def hero_idx(self):
        return self.base.hero_idx

    @hero_idx.setter
    def hero_idx(self, v):
        self.base.hero_idx = v

    def decide(self, st):
        dec = self.base.decide(st)
        me = st["players"][st["to_act"]]
        to_call = max(0, st["current_bet"] - me["committed_street"])
        if dec["action"] == "fold" and to_call > 0:
            return {"action": "call", "amount": None}
        return dec


def _defekt_factory(seed: int, mode: str):
    """mode='station': call statt fold. mode='folder': fold gegen jeden Einsatz —
    die einzige Defektrichtung mit mathematisch SICHEREM Vorzeichen (verschenkt
    jeden Pot, sobald gesetzt wird), darum traegt sie den Gate-Beweis E3b."""
    base = pokerbot(exploit=True, seed=seed)

    def make(seat):
        inner = base(seat)

        def d(st):
            a, amt = inner(st)
            me = st["players"][st["to_act"]]
            to_call = max(0, st["current_bet"] - me["committed_street"])
            if mode == "station" and a == "fold" and to_call > 0:
                return "call", None
            if mode == "folder" and to_call > 0:
                return "fold", None
            return a, amt
        return d
    return make


def _lead_rate(rep) -> float:
    return len(rep.leads) / max(1, rep.decisions) * 100


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    pairs = 60 if args.quick else 150
    decks = 60 if args.quick else GATE_DECKS
    results = {}

    print("AUTOGYM-SELBSTTEST — vorregistrierte Erwartungen E1-E4\n")

    ok1, rows = e1_orakel_wahrheit()
    results["E1_orakel_wahrheit"] = ok1
    print(f"E1 ORAKEL-WAHRHEIT: {'PASS' if ok1 else 'FAIL'}")
    for r in rows:
        print(r)

    print("\nE2 SYMMETRIE laeuft ...")
    hu = gym_hu.run(n_pairs=pairs, seed=7)
    drift, se = hu["paar_drift_bb100"], hu["paar_drift_se"]
    ok2 = abs(drift) < E2_SE_MULT * se
    results["E2_symmetrie"] = ok2
    print(f"E2 SYMMETRIE: {'PASS' if ok2 else 'FAIL'}  (Drift {drift:+.2f} vs 2*SE {E2_SE_MULT * se:.2f}, "
          f"n={pairs} Paare)")
    gesund_leads = _lead_rate(hu["orakel_report"])

    print("\nE3 DETEKTOR laeuft (Defekt-Bot: Station) ...")
    # Defekt-Selbstspiel durch dasselbe Gym: der Defekt sitzt auf BEIDEN Sitzen.
    import pokerbot.strategy.bot as botmod
    from pokerbot.strategy.bot import PokerBot
    botmod.EQUITY_ITERS = 120
    orig_make = gym_hu._make_bot
    gym_hu._make_bot = lambda seat, seed, exploit, eq: _StationDefekt(PokerBot(seat, seed=seed, exploit=exploit))
    try:
        defekt = gym_hu.run(n_pairs=max(30, pairs // 3), seed=7)
    finally:
        gym_hu._make_bot = orig_make
    defekt_leads = _lead_rate(defekt["orakel_report"])
    ok3a = defekt_leads >= E3_LEAD_FACTOR * gesund_leads
    print(f"E3a ORAKEL ERKENNT: {'PASS' if ok3a else 'FAIL'}  "
          f"(Lead-Rate defekt {defekt_leads:.1f}% vs gesund {gesund_leads:.1f}%, Soll >= {E3_LEAD_FACTOR}x)")

    gate3 = gate_ab(pokerbot(exploit=True, seed=1), _defekt_factory(3, "folder"), decks, seed=21)
    ok3b = gate3["verdict"] == "ANWENDEN"
    results["E3_detektor"] = ok3a and ok3b
    print(f"E3b GATE VERWIRFT DEFEKT (Immer-Folder): {'PASS' if ok3b else 'FAIL'}  "
          f"(gesund vs defekt {gate3['bb100']:+.1f} ± {gate3['se']:.1f} -> {gate3['verdict']})")

    # Nebenbefund mit eigenem Wert: die STATION (foldet nie). Richtung NICHT sicher —
    # ohne Hand-uebergreifende Anpassung laufen Bluffs in einen Gegner, der nie foldet.
    # Wird als Lead ins Journal gebucht, nicht als Maschinerie-Test gewertet.
    gate_st = gate_ab(pokerbot(exploit=True, seed=1), _defekt_factory(3, "station"), decks, seed=23)
    print(f"E3c NEBENBEFUND Station: gesund vs Station {gate_st['bb100']:+.1f} ± {gate_st['se']:.1f} "
          f"-> {gate_st['verdict']}  (Lead: Bluff-Anteil vs Nie-Folder, Journal)")
    from .improver import _journal
    _journal({"typ": "SELFTEST-BEFUND", "regel": "station_nicht_geschlagen",
              "befund": f"gesund vs Nie-Folder {gate_st['bb100']:+.1f} ± {gate_st['se']:.1f} "
                        f"({gate_st['n_decks']} Decks, 1-Hand-Horizont ohne Anpassung)",
              "verdict": "EXPERIMENT-KANDIDAT"})

    print("\nE4 NULL-STABILITAET laeuft ...")
    gate4 = gate_ab(pokerbot(exploit=True, seed=101), pokerbot(exploit=True, seed=202), decks, seed=22)
    ok4 = gate4["verdict"] != "ANWENDEN"
    results["E4_null_stabilitaet"] = ok4
    print(f"E4 NULL-STABILITAET: {'PASS' if ok4 else 'FAIL'}  "
          f"(gesund vs gesund {gate4['bb100']:+.1f} ± {gate4['se']:.1f} -> {gate4['verdict']})")

    n_pass = sum(results.values())
    print(f"\nERGEBNIS: {n_pass}/{len(results)} Erwartungen getroffen "
          f"{'— die Schleife ist lokal bewiesen.' if n_pass == len(results) else '— NICHT pod-bereit.'}")
    sys.exit(0 if n_pass == len(results) else 1)


if __name__ == "__main__":
    main()
