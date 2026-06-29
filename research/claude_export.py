# -*- coding: utf-8 -*-
"""Spiele die CLAUDE-BRAIN ('Hero') vs GTOBaseline und exportiere PokerStars-Hand-Histories,
damit GTO Wizards Analyzer JEDE Hero-Entscheidung vs GTO benoten kann.

WIE sich das von `research/pokerstars_export.py` unterscheidet: dort ist Hero der ENGINE-Bot (`PokerBot.decide`);
HIER ist Hero die LLM-BRAIN-Strecke — `ClaudeBrain.decide_spot(spot)` (Claude Opus 4.8 emittiert ein DSL-Programm,
das `api.*` aufruft, der Executor führt es zu einer EXAKTEN, LEGALEN Aktion aus). Das ist die CLAUDE.md
program-of-thought-These mit dem Frontier-Brain. Alle HH-Maschinerie (`format_hand`, `money`, SB/BB/STACK, die
Hand-Schleife) wird aus `pokerstars_export` WIEDERVERWENDET, damit die Uploads byte-strukturell vergleichbar sind.

Spot-Bridge (Variante b — siehe Kopf-Kommentar in `main`): wir spielen auf der KORREKTEN HU-Engine
`HeadsUpGame` (Button = SB, agiert zuerst preflop — genau wie pokerstars_export) und bauen am Hero-Knoten den
kanonischen `Spot` über einen kleinen `_spot_from_hu_state`-Adapter (gespiegelt aus
`pokerbot/benchmark/slumbot_llm.spot_from_slumbot`). Das N-Player-`Table`-Pendant `spot_from_table` ist NICHT
benutzbar, weil `Table` bei N=2 das generische Ring-Blind-Schema fährt (Button postet den BB, SB agiert zuerst,
Positionslabels BTN/BB statt SB/BB) — ein FALSCHER Spot für HU.

  SMOKE (kostet ein paar Cent Claude-API):  python -m research.claude_export --n 2 --out data/gtow_upload/claude_smoke.txt
  BATCH:  python -m research.claude_export --n 120 --seed 7 --idbase 3400000000 --out data/gtow_upload/claude_river.txt
"""
from __future__ import annotations

import argparse
import datetime
import os

from pokerbot.brain.claude_brain import ClaudeBrain
from pokerbot.brain.format_spot import Spot
from pokerbot.engine.game import HeadsUpGame
from pokerbot.strategy.gto_baseline import GTOBaseline

# Reuse pokerstars_export's HH machinery + stakes verbatim (same upload structure -> comparable GTOW batches).
from research.pokerstars_export import BASE_DT, BASE_ID, SB, BB, STACK, format_hand, money  # noqa: F401


def _pos_hu(seat: int, button: int) -> str:
    """HU position label for the canonical Spot: the button IS the small blind (acts first preflop)."""
    return "SB" if seat == button else "BB"


def _spot_from_hu_state(st: dict, hero_seat: int) -> Spot:
    """HeadsUpGame.state() dict -> our canonical Spot at `hero_seat`'s decision point.

    Mirrors `slumbot_llm.spot_from_slumbot` (the proven HU adapter), but reads HeadsUpGame's `state()` shape:
    the button is the SB, `players[k]` carries committed_total/folded/all_in, and `history` carries `deal` events
    WITHOUT a 'player' key (those are skipped so the public line is actions-only, like format_spot._line_from_history)."""
    button, bb = st["button"], st["bb"]
    players, L = st["players"], st["legal"]
    seats = [{"seat": k, "pos": _pos_hu(k, button), "stack": p["stack"],
              "committed_total": p["committed_total"], "folded": p["folded"], "all_in": p["all_in"]}
             for k, p in enumerate(players)]
    line = [{"street": h["street"], "pos": _pos_hu(h["player"], button), "action": h["action"],
             "amount_bb": (round(h.get("to", h.get("amount")) / bb, 2) if h.get("to", h.get("amount")) else None),
             "hero": h["player"] == hero_seat}
            for h in st["history"] if "player" in h]          # skip deal/blinds events (no actor)
    return Spot(street=st["street"], board=list(st["board"]), bb=bb, hero_seat=hero_seat,
                hero_pos=_pos_hu(hero_seat, button), hero_hole=list(players[hero_seat]["hole"]),
                pot=st["pot"], to_call=L["to_call"], n_active=2, seats=seats,
                legal={k: L.get(k) for k in ("can_fold", "can_check", "can_call", "can_raise",
                                             "raise_min", "raise_max")},
                line=line)


def hero_decider(brain: ClaudeBrain, hero_seat: int):
    """Hero = the Claude brain. Builds the canonical Spot at each hero node, asks Claude for a DSL program, returns
    the executed LEGAL (action, amount_chips). `res['ok']` (valid program) + `res['action']` are what the brain emits;
    the engine then applies it, so the HH records Claude's REAL decision (or a salvaged legal action if a program failed)."""
    def d(st):
        spot = _spot_from_hu_state(st, hero_seat)
        res = brain.decide_spot(spot)
        return res["action"], res["amount"]
    return d


def villain_decider(seat: int, seed: int):
    """Villain = GTOBaseline (same as pokerstars_export, for batch comparability)."""
    b = GTOBaseline(seat, seed=seed, iters=120)
    def d(st):
        b.hero = seat
        return b.decide(st)
    return d


def play_hand(g: HeadsUpGame, brain: ClaudeBrain, hero_seat: int, idx: int):
    """Drive one hand to completion; return (holes, history, result, button). Same structure as pokerstars_export.play_hand."""
    g.players[0].stack = g.players[1].stack = STACK     # cash-game reset to 200bb
    g.start_hand()
    holes = [list(g.players[0].hole), list(g.players[1].hole)]
    button = g.button
    deciders = {hero_seat: hero_decider(brain, hero_seat),
                1 - hero_seat: villain_decider(1 - hero_seat, seed=200 + idx)}
    guard = 0
    while not g.hand_over:
        st = g.state()
        i = st["to_act"]
        action, amount = deciders[i](st)
        g.act(action, amount)
        guard += 1
        if guard > 400:
            break
    return holes, list(g.history), g.result, button


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=2)               # SMOKE default = 2 (Claude API costs money)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--idbase", type=int, default=BASE_ID)    # offset so GTOW doesn't DEDUP vs a prior upload
    ap.add_argument("--dayoffset", type=int, default=0)       # shift timestamps too (unique hand identity)
    ap.add_argument("--river-only", action="store_true")      # emit only hands that reached the river (river-dense)
    ap.add_argument("--out", default="data/gtow_upload/claude_hands.txt")
    args = ap.parse_args()

    brain = ClaudeBrain(thinking=True, strict=True)           # built once; thread-safe (a stateless HTTP call)
    g = HeadsUpGame(names=("P0", "P1"), starting_stack=STACK, sb=SB, bb=BB, seed=args.seed)
    blocks = []
    for i in range(args.n):
        # Hero is ALWAYS seat 0; the button alternates by hand -> Hero plays SB and BB equally (same as pokerstars_export).
        hero_seat = 0
        names = ["Hero" if k == hero_seat else "Villain" for k in (0, 1)]
        holes, history, result, button = play_hand(g, brain, hero_seat, i)
        if args.river_only and len(result["board"]) < 5:
            continue                                          # not a river hand -> skip (keep the upload river-dense)
        dt = BASE_DT + datetime.timedelta(days=args.dayoffset, minutes=3 * i)
        blocks.append(format_hand(args.idbase + i, dt, names, button, holes, history, result, hero_seat))

    text = "\n\n".join(blocks) + "\n"
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"WROTE {len(blocks)} of {args.n} played hands -> {args.out}  ({len(text)} chars)")

    r = brain.report()                                        # honest brain summary (decisions, frac_bad, tokens)
    print(f"\n=== ClaudeBrain.report() ===\n{r}")
    if blocks:
        print("\n===== HANDS =====\n")
        print("\n\n".join(blocks))


if __name__ == "__main__":
    main()
