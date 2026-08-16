# -*- coding: utf-8 -*-
"""Snowie-Export: Haende in EXAKT der Konfiguration, die im Gate gemessen wurde.

Der Unterschied zu pokerstars_export: Hero ist die duplicate_ab-Fabrik
(PokerBot direkt, KEIN PokerBotAgent, kein Resolver, keine Solver-Aufrufe) --
also genau die Version, die AUSLESE v1 mit +6,1 bb/100 belegt hat. Beide Arme
laufen auf denselben Deals; die Unterschiede sitzen dort, wo die Selektion griff.

  python -m research.snowie_export --hero auslese --n 400 --out <pfad>
"""
from __future__ import annotations

import argparse
import datetime
import os
import sys

import pokerbot.strategy.bot as botmod
from pokerbot.autogym.improver import sel_guard
from pokerbot.benchmark.duplicate import pokerbot
from pokerbot.engine.game import HeadsUpGame
from research.pokerstars_export import BASE_DT, BB, SB, STACK, format_hand

GEFEUERT: list = []


def _hero(variante: str, idx: int):
    basis = pokerbot(exploit=True, seed=1)
    if variante == "basis":
        return basis(0)
    inner = sel_guard(basis)(0)

    def d(st):                       # protokolliert die Eingriffe fuer den Index
        vor = st["street"], st["pot"]
        a, amt = inner(st)
        me = st["players"][st["to_act"]]
        if a == "call" and basis(0)(st)[0] == "fold":
            GEFEUERT.append((idx, vor[0], vor[1]))
        return a, amt
    return d


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--hero", choices=("basis", "auslese"), default="auslese")
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
    if GEFEUERT:
        ip = os.path.splitext(args.out)[0] + "_selektion.txt"
        z = ["Haende, in denen die AUSLESE-Selektion eingriff (Fold -> Call)", ""]
        z += [f"Hand #{args.idbase + h}  {s}  Pot {p}" for h, s, p in GEFEUERT]
        with open(ip, "w", encoding="utf-8", newline=chr(13) + chr(10)) as f:
            f.write(chr(10).join(z) + chr(10))
        print(f"SELEKTION: {len(GEFEUERT)} Eingriffe -> {ip}")


if __name__ == "__main__":
    main()
