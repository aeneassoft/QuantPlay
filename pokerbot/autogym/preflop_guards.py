"""PREFLOP-GUARDS — zwei Wrapper-Kandidaten im improver-Stil (HU, bb=100 Chips).

(a) stackoff_bremse — GTOW-Desaster-Klasse D (Journal/STATE: KsKh 5bet-Jam 200bb,
    Js9d 4bet-Call; error_prognosis Klasse 4 = 4bet-Stackoff -13,8bb/Hand):
    grosse Preflop-Stackoffs (>= 100bb Gesamt-Einsatz nach der Aktion) nur noch
    mit Premium-Klassen; Mittel-Klassen bis unter 150bb. Opens/3bets/kleine
    Toepfe bleiben UNANGETASTET — nur der Stack-off-Knoten wird gebremst.
(b) no_limp_guard — Fable-Duell-Befund (Limp-Call -> Fold-vs-Cbet 5/7 = freie
    Kasse): der Button-Limp (SB-Complete) wird zum 2,5x-Open, wie es
    button_disziplin_guard in improver.py fuer die open-FOLDS tut.

Beides sind GUARD-WRAPPER um decide() (nie Quelltext-Edits) und laufen wie alle
Kandidaten NUR durchs gepaarte A/B-Gate (improver.gate_ab), bevor irgendetwas
als 'ANWENDEN' gebucht wird. Selbsttest: python -m pokerbot.autogym.preflop_guards
"""
from __future__ import annotations

# Kartenrang-Ordnung ('As' -> 'A'); identisch zu improver._RANK_ORD, lokal
# gehalten, damit der Guard-Modul-Import keine Gate-Maschinerie mitzieht.
_RANK_ORD = {r: i for i, r in enumerate("23456789TJQKA")}

# HU-Konventionen (bb = 100 Chips; SB 50): der Button-Limp ist das SB-Complete.
_SB_CHIPS = 50
_OPEN_RAISE_TO = 250            # 2,5x-Open, identisch zu button_disziplin_guard

# Schwellen der Stackoff-Bremse (Chips): 100bb weich, 150bb hart.
_GRENZE_WEICH = 10000
_GRENZE_HART = 15000


def _hand_klasse(hole) -> str:
    """['Ks','Kh'] -> 'KK'; ['Js','9d'] -> 'J9o'; ['As','Ks'] -> 'AKs'.
    Hoehere Karte zuerst, Paare im 'AA'-Format, sonst Rang1+Rang2+s/o."""
    r1, r2 = hole[0][0], hole[1][0]
    if r1 == r2:
        return r1 + r2
    if _RANK_ORD[r1] < _RANK_ORD[r2]:
        r1, r2 = r2, r1
    return r1 + r2 + ("s" if hole[0][1] == hole[1][1] else "o")


def stackoff_bremse(make_strat, premium: tuple = ("AA", "KK", "QQ", "AKs", "AKo"),
                    mittel: tuple = ("JJ", "TT", "AQs"),
                    grenze_hart: int = _GRENZE_HART, grenze_weich: int = _GRENZE_WEICH):
    """Preflop-Stackoff nur noch selektiv: spielt die Basis bei to_call>0
    call/raise/allin und laege der GESAMT-Einsatz nach der Aktion bei
    >= grenze_weich (100bb), dann bleibt die Aktion nur fuer premium-Klassen
    frei; mittel-Klassen duerfen bis unter grenze_hart (150bb); alles andere
    foldet. to_call==0 und kleine Toepfe werden NIE angefasst (Opens/3bets
    bleiben frei — gebremst wird ausschliesslich der Stack-off-Knoten)."""
    def make(seat):
        base = make_strat(seat)

        def d(st):
            a, amt = base(st)
            try:
                me = st["players"][st["to_act"]]
                to_call = max(0, st["current_bet"] - me["committed_street"])
                if (st["street"] != "preflop" or to_call <= 0
                        or a not in ("call", "raise", "allin")):
                    return a, amt
                # Gesamt-Einsatz NACH der Aktion (Engine-Semantik game.py:
                # raise-amount = Street-Ziel 'to'; allin committet den Stack).
                if a == "call":
                    gesamt = me["committed_total"] + min(to_call, me["stack"])
                elif a == "allin" or amt is None:
                    gesamt = me["committed_total"] + me["stack"]
                else:                           # raise mit Ziel-Betrag (to)
                    ziel = min(int(amt), me["committed_street"] + me["stack"])
                    gesamt = me["committed_total"] - me["committed_street"] + ziel
                if gesamt < grenze_weich:
                    return a, amt               # kleiner Topf: nie eingreifen
                klasse = _hand_klasse(me["hole"])
                if klasse in premium:
                    return a, amt
                if klasse in mittel and gesamt < grenze_hart:
                    return a, amt
                return "fold", None
            except Exception:  # noqa: BLE001
                return a, amt   # defensiv: im Zweifel bleibt die Basis-Aktion
        return d
    return make


def no_limp_guard(make_strat):
    """HU-Button-Limp streichen: complettiert der Button den SB (Basis 'call'
    bei to_call==SB und committed_street==SB preflop), wird daraus das
    2,5x-Open — das Fable-Duell zaehlte Limp-Call -> Fold-vs-Cbet 5/7 als
    freie Kasse; das Gegenstueck zu button_disziplin_guard (open-FOLDS)."""
    def make(seat):
        base = make_strat(seat)

        def d(st):
            a, amt = base(st)
            try:
                me = st["players"][st["to_act"]]
                to_call = max(0, st["current_bet"] - me["committed_street"])
                if (a == "call" and st["street"] == "preflop"
                        and to_call == _SB_CHIPS
                        and me["committed_street"] == _SB_CHIPS):
                    return "raise", _OPEN_RAISE_TO
            except Exception:  # noqa: BLE001
                pass            # defensiv: im Zweifel bleibt die Basis-Aktion
            return a, amt
        return d
    return make


# ---------------------------------------------------------------- Selbsttest
def _fixe_basis(action: str, amount=None):
    """Strategie-Fabrik, die immer dieselbe Basis-Entscheidung liefert."""
    def make_strat(seat):
        def d(st):
            return action, amount
        return d
    return make_strat


def _st(hole, stack: int, committed: int, current_bet: int, street: str = "preflop") -> dict:
    """Synthetischer HU-State (preflop: committed_total == committed_street)."""
    return {
        "street": street, "board": [] if street == "preflop" else ["2c", "7d", "Th"],
        "to_act": 0, "current_bet": current_bet, "button": 0, "history": [],
        "pot": committed + current_bet,
        "players": [
            {"idx": 0, "hole": hole, "stack": stack, "committed_street": committed,
             "committed_total": committed, "folded": False, "all_in": False,
             "is_button": True},
            {"idx": 1, "hole": ["??", "??"], "stack": 20000, "committed_street": current_bet,
             "committed_total": current_bet, "folded": False, "all_in": False,
             "is_button": False},
        ],
    }


def _selbsttest() -> int:
    faelle = [
        # (name, guard-fabrik, basis(aktion, amount), state, erwartet)
        ("premium AA-Stackoff bleibt (allin 200bb)",
         stackoff_bremse, ("allin", None),
         _st(["As", "Ad"], 18000, 2000, 6000), ("allin", None)),
        ("KsKh 5bet-Jam 200bb bleibt (raise-to all-in)",
         stackoff_bremse, ("raise", 20000),
         _st(["Ks", "Kh"], 14000, 6000, 14000), ("raise", 20000)),
        ("Js9d 4bet-Call 120bb wird gefoldet",
         stackoff_bremse, ("call", None),
         _st(["Js", "9d"], 17500, 2500, 12000), ("fold", None)),
        ("mittel JJ-Call 120bb bleibt (unter 150bb hart)",
         stackoff_bremse, ("call", None),
         _st(["Jc", "Jh"], 17500, 2500, 12000), ("call", None)),
        ("mittel TT-Call 160bb wird gefoldet (ueber 150bb hart)",
         stackoff_bremse, ("call", None),
         _st(["Ts", "Th"], 17500, 2500, 16000), ("fold", None)),
        ("kleiner Topf unberuehrt (72o callt 3bb)",
         stackoff_bremse, ("call", None),
         _st(["7s", "2d"], 19900, 100, 300), ("call", None)),
        ("to_call==0 nie eingreifen (BB-Option, raise-to all-in bleibt)",
         stackoff_bremse, ("raise", 20000),
         _st(["8s", "3d"], 19900, 100, 100), ("raise", 20000)),
        ("postflop unberuehrt (River-Call, grosser Topf)",
         stackoff_bremse, ("call", None),
         _st(["Js", "9d"], 8000, 12000, 4000, street="river"), ("call", None)),
        ("Button-Limp wird 2,5x-Open",
         no_limp_guard, ("call", None),
         _st(["7s", "2d"], 19950, 50, 100), ("raise", 250)),
        ("Nicht-Limp-Call unberuehrt (BB callt 3bet)",
         no_limp_guard, ("call", None),
         _st(["Ah", "Qd"], 19750, 250, 750), ("call", None)),
    ]
    fehler = 0
    for name, fabrik, (ba, bamt), st, erwartet in faelle:
        d = fabrik(_fixe_basis(ba, bamt))(0)
        ist = d(st)
        ok = ist == erwartet
        fehler += 0 if ok else 1
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: basis=({ba},{bamt}) -> {ist}"
              + ("" if ok else f" (erwartet {erwartet})"))
    print(f"\nSelbsttest: {len(faelle) - fehler}/{len(faelle)} gruen")
    return fehler


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(1 if _selbsttest() else 0)
