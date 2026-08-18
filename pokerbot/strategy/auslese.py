"""AUSLESE — die EINE Quelle des finalen HU-Stacks fuer alle Konsum-Kanaele (2026-08-18).

Definition (Taufe auslese-v4 + Runde-6-Haertung, Journal):
  FINAL_STACK = r6_button(turn_wert(sel_guard(basis, m15)))     [Wrapper-Kette]
  + AUSLESE_ENV                                                  [Import-Zeit-Flags]

Evidenz: Mirror 3x30k vs basis +16,14+-2,77 (p=0,0002); r6_button Haertung im
Fable-Retest bewiesen (Ernte 186->58 bb/100). BINDEND: RAISE_NARROW ist
resolver-ON KONTRAINDIZIERT (v8-K3) -> setze_env(resolver_on=True) laesst RN
weg. Die Guards sind HU-ONLY (2-Spieler-State-Ausdruecke) — NIE in den
Multiway-Kern verdrahten (Armee-Befund 2026-08-17).

Dieses Modul haelt seine Imports LAZY: setze_env() muss VOR dem Import von
pokerbot.strategy.bot laufen (Import-Zeit-Konstanten).
"""
from __future__ import annotations

FINAL_STACK = "r6_button"
AUSLESE_ENV = {"POKERB_TURN_DEFENSE": "0.07", "POKERB_SLOWPLAY": "0.25"}
AUSLESE_ENV_RESOLVER_OFF = {**AUSLESE_ENV, "POKERB_RAISE_NARROW": "1.0"}


def setze_env(resolver_on: bool = False) -> None:
    """Setzt die v4-Env-Flags (setdefault: explizite Launcher-Flags gewinnen).
    VOR dem bot-Import aufrufen — die Flags werden bei IMPORT gelesen."""
    import os
    env = AUSLESE_ENV if resolver_on else AUSLESE_ENV_RESOLVER_OFF
    for k, v in env.items():
        os.environ.setdefault(k, v)


def wickle_decide(pb, stack: str | None = None):
    """Legt den FINAL_STACK dict-erhaltend um PokerBot.decide (HU-Kanaele:
    Web-App, GTOW-Harness). Der Guard-Eingriff wird im rationale markiert."""
    from pokerbot.autogym.pargate import _wickle
    merker: dict = {}

    def fabrik(seat):
        def basis(st):
            dec = pb.decide(st)
            merker["dec"] = dec
            return dec["action"], dec["amount"]
        return basis

    kette = _wickle(stack or FINAL_STACK, fabrik)(0)

    def decide(st):
        a, amt = kette(st)
        dec = merker["dec"]
        if (a, amt) != (dec["action"], dec["amount"]):
            # rationale ist beim PokerBot ein DICT — nie String-konkatenieren
            # (Smoke-20-Fund 2026-08-18: dict+str-Crash exakt bei Guard-Eingriff).
            dec = {**dec, "action": a, "amount": amt, "auslese_guard": True}
        return dec
    return decide
