"""AUSLESE — die EINE Quelle des finalen HU-Stacks fuer alle Konsum-Kanaele.

Definition (Taufe auslese-v5, 2026-08-31, GPU-Staffel):
  FINAL_STACK = river_gpu_guard(river_wert_bremse(r6_button(turn_wert(sel_m15))))
  + AUSLESE_ENV                                                  [Import-Zeit-Flags]

Evidenz v5 (Journal R7-REPLIKATION + R8-FINALE): wert_bremse 3x repliziert
(+8,10/+8,81/+7,38, drei Baenke, perm_p 0,0002); r8_stack-Inkrement vs
r6_button 3x30k: +29,92/+23,76/+29,23 (gepoolt +27,6+-1,8, alle p=0,0002);
vs eingefrorene BASIS +30,60+-5,03; A/A exakt 0 (GPU-Pfad deterministisch).
Der river_gpu_guard loest Big-Pot-River-Subgames auf der GPU (RiverCFRBatch,
TexasSolver-kreuzvalidiert r=0,999) und ueberschreibt die Basis NUR bei klarem
Solver-Widerspruch (p_basis<0,10 & p_alt>0,70) — Chirurgie, kein Purify.

Historie v4 (Tag auslese-v4): FINAL_STACK war r6_button; Mirror 3x30k vs basis
+16,14+-2,77. BINDEND bleibt: RAISE_NARROW ist resolver-ON KONTRAINDIZIERT
(v8-K3) -> setze_env(resolver_on=True) laesst RN weg. Die Guards sind HU-ONLY
(2-Spieler-State-Ausdruecke) — NIE in den Multiway-Kern verdrahten.

v10-RELEASE-KANDIDAT (docs/plans/V10_BUILD_CARD.md, 2026-09-07): RC_STACK = r10_stack
= dieselbe Kette darunter (r6_button + wert_bremse), aber der hand-abhaengige
river_gpu_guard ist durch den OEFFENTLICHEN River-Plan (K2, pokerbot/autogym/
river_plan.py: ein Solve je Hand am River-Beginn, K1-Hero-Range ohne Injektion,
private Randomisierung) ersetzt. FINAL_STACK bleibt r8_stack, bis die Gates
G1-G6 gruen sind und der RC getauft wird (Tag auslese-v10-rc); der GTOW-Pilot
(K5) faehrt beide Arme ueber POKERB_AUSLESE_STACK. Live-Kanaele wickeln mit
kanal='live' (7,5-s-Deadline, os.urandom-Seed), das Gate bleibt Gym.

Dieses Modul haelt seine Imports LAZY: setze_env() muss VOR dem Import von
pokerbot.strategy.bot laufen (Import-Zeit-Konstanten).
"""
from __future__ import annotations

FINAL_STACK = "r8_stack"
RC_STACK = "r10_stack"          # Release-Kandidat v10; wird erst mit der Taufe FINAL_STACK
AUSLESE_ENV = {"POKERB_TURN_DEFENSE": "0.07", "POKERB_SLOWPLAY": "0.25"}
AUSLESE_ENV_RESOLVER_OFF = {**AUSLESE_ENV, "POKERB_RAISE_NARROW": "1.0"}


def setze_env(resolver_on: bool = False) -> None:
    """Setzt die v4-Env-Flags (setdefault: explizite Launcher-Flags gewinnen).
    VOR dem bot-Import aufrufen — die Flags werden bei IMPORT gelesen."""
    import os
    env = AUSLESE_ENV if resolver_on else AUSLESE_ENV_RESOLVER_OFF
    for k, v in env.items():
        os.environ.setdefault(k, v)


def wickle_decide(pb, stack: str | None = None, kanal: str = "live"):
    """Legt den FINAL_STACK dict-erhaltend um PokerBot.decide (HU-Kanaele:
    Web-App, GTOW-Harness). Der Guard-Eingriff wird im rationale markiert.
    kanal 'live' (Default, unveraendert) = Deadline + os.urandom-Seed fuer K2-Arme;
    'gym' = deterministisch (gepaarte Gates wie pargate6 brauchen A/A exakt 0)."""
    from pokerbot.autogym.pargate import _wickle
    merker: dict = {}

    def fabrik(seat):
        def basis(st):
            dec = pb.decide(st)
            merker["dec"] = dec
            return dec["action"], dec["amount"]
        return basis

    stack_fabrik = _wickle(stack or FINAL_STACK, fabrik, kanal=kanal)
    kette = stack_fabrik(0)
    # K4-Fingerprint (runtime_config.private_seed_quelle liest bot.private_seed_quelle):
    # nur der K2-Plan-Wrapper traegt eine Seed-Herkunft; andere Stacks bleiben 'keine'.
    quelle = getattr(stack_fabrik, "private_seed_quelle", None)
    if quelle is not None:
        pb.private_seed_quelle = quelle

    def decide(st):
        a, amt = kette(st)
        dec = merker["dec"]
        if (a, amt) != (dec["action"], dec["amount"]):
            # rationale ist beim PokerBot ein DICT — nie String-konkatenieren
            # (Smoke-20-Fund 2026-08-18: dict+str-Crash exakt bei Guard-Eingriff).
            dec = {**dec, "action": a, "amount": amt, "auslese_guard": True}
        return dec
    return decide
