# -*- coding: utf-8 -*-
"""Snowie-Export: Haende in EXAKT der Konfiguration, die im Gate gemessen wurde.

Der Unterschied zu pokerstars_export: Hero ist die duplicate_ab-Fabrik
(PokerBot direkt, KEIN PokerBotAgent, kein Resolver, keine Solver-Aufrufe).
GATE-PARITAET KONKRET (2026-08-17): --hero nimmt einen pargate-KANDIDATEN-Namen;
der Guard-Stack kommt aus der EINEN Quelle pargate._wickle (frueher: lokales
sel_guard(basis) = AUSLESE v1, obwohl der Docstring Gate-Paritaet versprach).
Default = 'turn_wert' (AUSLESE v4-Wrapper). Die v4-Env-Seite
(POKERB_TURN_DEFENSE=0.07 POKERB_SLOWPLAY=0.25 POKERB_RAISE_NARROW=1.0) setzt
die SHELL — bot.py liest bei IMPORT; der Lauf-Fingerprint landet im Sidecar.

  python -m research.snowie_export --hero turn_wert --n 400 --out <pfad>
"""
from __future__ import annotations

import argparse
import datetime
import os
import sys

import pokerbot.strategy.bot as botmod
from pokerbot.autogym.pargate import KANDIDATEN
from pokerbot.benchmark.duplicate import pokerbot
from pokerbot.engine.game import HeadsUpGame
import research.pokerstars_export as _pse
from research.pokerstars_export import BB, SB, STACK, format_hand, stack_mit_protokoll

# PokerStars schreibt Betraege IMMER mit zwei Nachkommastellen ($1.00, nie $1) --
# der Repo-Exporter kuerzt ganze Zahlen, was fremde Parser (PokerSnowie) mit
# "unsupported / not texas holdem" ablehnen. Hier ueberschrieben.
_pse.money = lambda chips: f"${chips / 100.0:.2f}"

# Datum MUSS in der Vergangenheit liegen; ein Zukunftsdatum lehnen Importer ab.
BASE_DT = datetime.datetime(2026, 7, 1, 18, 0, 0)

GEFEUERT: list = []


def _hero(variante: str, idx: int):
    """Hero = pargate-Stack (EINE Quelle) um die duplicate-Basis. Das Protokoll
    vergleicht Stack- vs Roh-Aktion ohne zweiten Basis-Aufruf (der alte Code
    baute pro Entscheidung einen FRISCHEN PokerBot nur fuers Logging)."""
    basis = pokerbot(exploit=True, seed=1)
    if variante == "basis":
        return basis(0)
    return stack_mit_protokoll(variante, basis(0), idx, GEFEUERT)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--hero", choices=KANDIDATEN, default="turn_wert",
                    help="pargate-KANDIDATEN-Name; 'turn_wert' = der AUSLESE-v4-Wrapper")
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--seed", type=int, default=4711)
    ap.add_argument("--idbase", type=int, default=700000)
    ap.add_argument("--dayoffset", type=int, default=60)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    botmod.EQUITY_ITERS = 120

    g = HeadsUpGame(names=("P0", "P1"), starting_stack=STACK, sb=SB, bb=BB, seed=args.seed)
    villain = pokerbot(exploit=True, seed=2)
    blocks = []
    for i in range(args.n):
        g.players[0].stack = g.players[1].stack = STACK
        g.start_hand()
        holes = [list(g.players[0].hole), list(g.players[1].hole)]
        button = g.button
        deciders = {0: _hero(args.hero, i), 1: villain(1)}
        guard = 0
        while not g.hand_over and guard < 400:
            st = g.state()
            a, amt = deciders[st["to_act"]](st)
            g.act(a, amt)
            guard += 1
        dt = BASE_DT + datetime.timedelta(days=args.dayoffset, minutes=3 * i)
        blocks.append(format_hand(args.idbase + i, dt, ["Hero", "Villain"], button,
                                  holes, list(g.history), g.result, 0))
        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{args.n} | {len(GEFEUERT)} Eingriffe", flush=True)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline=chr(13) + chr(10)) as f:
        f.write("\n\n".join(blocks) + "\n")
    print(f"WROTE {len(blocks)} Haende -> {args.out}")
    # Konfig-Sidecar IMMER: das graded Artefakt traegt den Env-Fingerprint
    # (inkl. TURN_DEFENSE/SLOWPLAY/RAISE_NARROW) + den Wrapper-Namen selbst.
    import json
    from pokerbot.strategy.gto_mode import fingerprint
    with open(os.path.splitext(args.out)[0] + "_konfig.json", "w", encoding="utf-8") as f:
        json.dump({"hero": args.hero, "fingerprint": fingerprint(),
                   "equity_iters": botmod.EQUITY_ITERS, "seed": args.seed,
                   "idbase": args.idbase, "dayoffset": args.dayoffset}, f, indent=1)
    print("config fingerprint:", {k: v for k, v in fingerprint().items() if v is not None})
    if GEFEUERT:
        ip = os.path.splitext(args.out)[0] + "_selektion.txt"
        z = ["Haende, in denen der Guard-Stack eingriff (Roh-Aktion -> Stack-Aktion)", ""]
        z += [f"Hand #{args.idbase + h}  {s}  {roh} -> {neu}" for h, s, roh, neu in GEFEUERT]
        with open(ip, "w", encoding="utf-8", newline=chr(13) + chr(10)) as f:
            f.write(chr(10).join(z) + chr(10))
        print(f"SELEKTION: {len(GEFEUERT)} Eingriffe -> {ip}")


if __name__ == "__main__":
    main()
