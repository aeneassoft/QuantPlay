# -*- coding: utf-8 -*-
"""Spiele unseren HU-PokerBot ('Hero') vs GTOBaseline und exportiere PokerStars-Hand-Histories,
damit GTO Wizards Analyzer JEDE Hero-Entscheidung vs GTO benoten kann.

Hero-Sitz wechselt pro Hand -> der Produkt-Bot wird in BEIDEN Positionen (BTN/SB und BB) graded.
Cash-Game: jede Hand startet auf 200bb (Stacks werden zurückgesetzt).

  python -m research.pokerstars_export --n 15 --out data/gtow_upload/bot_hands.txt
"""
from __future__ import annotations

import argparse
import datetime
import os

from pokerbot.strategy.gto_mode import apply as _apply_gto_mode, fingerprint

# GTOW mode BEFORE any strategy import (flags are read at import time) — the export must grade the SAME
# config that plays AIVAT (S1 parity fix, plan 2026-07-04; the old hero was hard-coded exploit=False/iters=120,
# grading a config that never played live).
_apply_gto_mode()

from pokerbot.engine.game import HeadsUpGame

import pokerbot.strategy.bot as botmod
from pokerbot.strategy.gto_baseline import GTOBaseline

SB, BB, STACK = 50, 100, 20000     # 0.5/1, 200bb — the gtow benchmark stakes
BASE_ID = 2600000000
BASE_DT = datetime.datetime(2026, 6, 27, 18, 0, 0)


def money(chips: int) -> str:
    """Chips -> PokerStars dollar string (bb=100 chips = $1). Integers without decimals."""
    v = chips / 100.0
    return f"${int(v)}" if v == int(v) else f"${v:.2f}"


# ---- bot deciders (uniform (action, amount) interface) ----
def hero_decider(seat: int, seed: int, resolver: bool | None = None):
    """Hero = EXACTLY the live GTOW agent (PokerBotAgent, incl. every env toggle) — never a diverging copy.
    `resolver=None` keeps the live default (env POKERB_RESOLVER); True/False forces it for a targeted A/B."""
    from pokerbot.benchmark.gtowizard import PokerBotAgent
    assert seat == 0, "hero must sit at 0 (PokerBotAgent is seat-0 by construction)"
    agent = PokerBotAgent(seed=seed)
    if resolver is not None:
        agent.bot.use_resolver = resolver
    pb = agent.bot
    def d(st):
        pb.hero_idx = seat
        r = pb.decide(st)
        return r["action"], r["amount"]
    return d


# Welche Hero-Version exportiert wird: 'basis' oder ein pargate-KANDIDATEN-Name.
# Der Guard-Stack kommt aus der EINEN Quelle pargate._wickle — die alte lokale
# _auslese_um-Kopie (Marge 0.03 statt m15, UNGESEEDETE MC = Paarungs-Brecher,
# kein turn_wert) ist entfernt (2026-08-17). AUSLESE v4 = --hero turn_wert
# + Shell-Env POKERB_TURN_DEFENSE=0.07 POKERB_SLOWPLAY=0.25 POKERB_RAISE_NARROW=1.0.
from pokerbot.autogym.pargate import KANDIDATEN as HERO_VARIANTEN

GEFEUERT: list = []          # (hand_idx, street, roh_aktion, stack_aktion) je Eingriff


def stack_mit_protokoll(variante: str, roh_decider, hand_idx: int, protokoll: list):
    """v4-Stack aus der EINEN Quelle (pargate._wickle) um einen FERTIGEN Decider,
    mit Eingriffs-Protokoll: jede Abweichung Stack vs Roh (Call- UND Bet-Seite,
    turn_wert greift auf der Bet-Seite ein). Der Roh-Decider wird pro Spot genau
    EINMAL gerufen (merk) — kein doppelter RNG-Verbrauch, Paarung bleibt intakt."""
    from pokerbot.autogym.pargate import _wickle
    letzte: dict = {}

    def merk(st):
        r = roh_decider(st)
        letzte["r"] = r
        return r

    gewickelt = _wickle(variante, lambda seat: merk)(0)

    def w(st):
        a, amt = gewickelt(st)
        if (a, amt) != letzte.get("r"):
            protokoll.append((hand_idx, st["street"], letzte["r"][0], a))
        return a, amt
    return w


def villain_decider(seat: int, seed: int):
    b = GTOBaseline(seat, seed=seed, iters=120)
    def d(st):
        b.hero = seat
        return b.decide(st)
    return d


def play_hand(g: HeadsUpGame, hero_seat: int, idx: int, resolver: bool | None = None,
              hero_variante: str = "basis"):
    """Drive one hand to completion; return (holes, history, result, button)."""
    g.players[0].stack = g.players[1].stack = STACK     # cash-game reset to 200bb
    g.start_hand()
    holes = [list(g.players[0].hole), list(g.players[1].hole)]
    button = g.button
    hd = hero_decider(hero_seat, seed=100 + idx, resolver=resolver)
    if hero_variante != "basis":
        hd = stack_mit_protokoll(hero_variante, hd, idx, GEFEUERT)
    deciders = {hero_seat: hd,
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


def format_hand(hand_id, dt, names, button, holes, history, result, hero_seat) -> str:
    """One hand -> a PokerStars hand-history block."""
    sb_idx, bb_idx = button, 1 - button          # HU: button = small blind
    L = []
    L.append(f"PokerStars Hand #{hand_id}:  Hold'em No Limit ({money(SB)}/{money(BB)} USD) - "
             f"{dt.strftime('%Y/%m/%d %H:%M:%S')} ET")
    L.append(f"Table 'PokerB' 2-max Seat #{button + 1} is the button")
    L.append(f"Seat 1: {names[0]} ({money(STACK)} in chips)")
    L.append(f"Seat 2: {names[1]} ({money(STACK)} in chips)")
    L.append(f"{names[sb_idx]}: posts small blind {money(SB)}")
    L.append(f"{names[bb_idx]}: posts big blind {money(BB)}")
    L.append("*** HOLE CARDS ***")
    hn = names[hero_seat]
    L.append(f"Dealt to {hn} [{holes[hero_seat][0]} {holes[hero_seat][1]}]")

    street_commit = {0: 0, 1: 0}
    total_commit = {0: 0, 1: 0}
    street_commit[sb_idx] = SB; street_commit[bb_idx] = BB
    total_commit[sb_idx] = SB; total_commit[bb_idx] = BB
    cur_bet = BB
    fold_street = "preflop"

    HEADER = {"flop": "*** FLOP ***", "turn": "*** TURN ***", "river": "*** RIVER ***"}
    dealt_streets = set()
    for ev in history:
        act = ev["action"]
        if act == "deal":
            board = ev["board"]
            dealt_streets.add(ev["street"])
            if ev["street"] == "flop":
                L.append(f"{HEADER['flop']} [{' '.join(board[:3])}]")
            elif ev["street"] == "turn":
                L.append(f"{HEADER['turn']} [{' '.join(board[:3])}] [{board[3]}]")
            elif ev["street"] == "river":
                L.append(f"{HEADER['river']} [{' '.join(board[:4])}] [{board[4]}]")
            street_commit = {0: 0, 1: 0}
            cur_bet = 0
            continue
        p = ev["player"]; nm = names[p]
        if act == "fold":
            fold_street = ev["street"]
            L.append(f"{nm}: folds")
        elif act == "check":
            L.append(f"{nm}: checks")
        elif act == "call":
            amt = ev["amount"]
            street_commit[p] += amt; total_commit[p] += amt
            L.append(f"{nm}: calls {money(amt)}")
        elif act == "bet":
            to = ev["to"]; amt = to - street_commit[p]
            total_commit[p] += amt; street_commit[p] = to; cur_bet = to
            L.append(f"{nm}: bets {money(amt)}")
        elif act == "raise":
            to = ev["to"]; inc = to - cur_bet; amt = to - street_commit[p]
            total_commit[p] += amt; street_commit[p] = to; cur_bet = to
            L.append(f"{nm}: raises {money(inc)} to {money(to)}")

    # ---- end-of-hand accounting (uncalled refund + pot) ----
    hi = 0 if total_commit[0] >= total_commit[1] else 1
    lo = 1 - hi
    uncalled = total_commit[hi] - total_commit[lo]
    pot = 2 * total_commit[lo]
    if uncalled > 0:
        L.append(f"Uncalled bet ({money(uncalled)}) returned to {names[hi]}")

    winner = result["winner"]
    board = result["board"]
    # AUDIT FIX (2026-07-05): all-in RUN-OUT streets are dealt silent=True by the engine (no deal events) ->
    # the exported HH omitted *** FLOP/TURN/RIVER *** sections on exactly the stack-off hands. Emit the
    # missing sections here (after the uncalled-refund line, before SHOW DOWN — real PokerStars order).
    # NOTE (pairing): exports BEFORE this fix (hu_v22/v3/v31/v32) lack the sections consistently — comparable
    # among themselves; any NEW arm must be paired against a freshly regenerated anchor, not the old files.
    if result["reason"] == "showdown" and board:
        if len(board) >= 3 and "flop" not in dealt_streets:
            L.append(f"{HEADER['flop']} [{' '.join(board[:3])}]")
        if len(board) >= 4 and "turn" not in dealt_streets:
            L.append(f"{HEADER['turn']} [{' '.join(board[:3])}] [{board[3]}]")
        if len(board) >= 5 and "river" not in dealt_streets:
            L.append(f"{HEADER['river']} [{' '.join(board[:4])}] [{board[4]}]")
    if result["reason"] == "showdown":
        L.append("*** SHOW DOWN ***")
        for k in (hi, lo):
            L.append(f"{names[k]}: shows [{holes[k][0]} {holes[k][1]}] ({result['hands'][k]['rank']})")
        if winner is None:
            L.append(f"{names[0]} collected {money(pot // 2)} from pot")
            L.append(f"{names[1]} collected {money(pot - pot // 2)} from pot")
        else:
            L.append(f"{names[winner]} collected {money(pot)} from pot")
    else:
        L.append(f"{names[winner]} collected {money(pot)} from pot")

    # ---- summary ----
    L.append("*** SUMMARY ***")
    L.append(f"Total pot {money(pot)} | Rake $0")
    if board:
        L.append(f"Board [{' '.join(board)}]")
    fold_phrase = "folded before Flop" if fold_street == "preflop" else f"folded on the {fold_street.capitalize()}"
    for k in (0, 1):
        tags = " (button) (small blind)" if k == button else " (big blind)"
        if result["reason"] == "fold":
            out = f"collected ({money(pot)})" if k == winner else fold_phrase
        else:
            desc = result["hands"][k]["rank"]
            if winner is None:
                out = f"showed [{holes[k][0]} {holes[k][1]}] and won ({money(pot // 2)}) with {desc}"
            elif k == winner:
                out = f"showed [{holes[k][0]} {holes[k][1]}] and won ({money(pot)}) with {desc}"
            else:
                out = f"showed [{holes[k][0]} {holes[k][1]}] and lost with {desc}"
        L.append(f"Seat {k + 1}: {names[k]}{tags} {out}")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=15)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--idbase", type=int, default=BASE_ID)   # offset so GTOW doesn't DEDUP vs a prior upload
    ap.add_argument("--dayoffset", type=int, default=0)      # shift timestamps too (unique hand identity)
    ap.add_argument("--resolver", choices=["on", "off", "live"], default="live",
                    help="force Hero's river resolver on/off; 'live' = the env default (parity with AIVAT play)")
    ap.add_argument("--fast", action="store_true", help="EQUITY_ITERS=120 for quick iteration (default = live 1500)")
    ap.add_argument("--river-only", action="store_true")     # emit only hands that reached the river (river-dense)
    ap.add_argument("--hero", choices=HERO_VARIANTEN, default="basis",
                    help="welche Bot-Version exportiert wird")
    ap.add_argument("--out", default="data/gtow_upload/bot_hands.txt")
    args = ap.parse_args()
    if args.fast:
        botmod.EQUITY_ITERS = 120
    if args.idbase == BASE_ID and args.dayoffset == 0:
        # AUDIT FIX (2026-07-05): default identity constants -> two default exports carry IDENTICAL hand
        # ids/timestamps and the Analyzer silently DEDUPS the second upload against the first.
        print("WARNING: default --idbase/--dayoffset — a prior default upload will DEDUP this one on the "
              "Analyzer. Pass a unique --idbase N --dayoffset M per arm (ledger: 299/31=v22 300/32=v3 "
              "301/33=v31 302/34=v32).")
    # DEDUP LAW (measured 2026-07-06, the family-2/3 incident): the Analyzer burns hand IDENTITIES on
    # FIRST CONTACT (even failed uploads) and dedups across ALL prior uploads — id RANGES must never
    # overlap (idbase steps of +1 overlap 99.9% for n=1500; use >= 2000 spacing, ledger in STATE.md),
    # and identical seeds re-upload only with fresh id blocks + fresh dayoffsets (belt + suspenders:
    # a fresh SEED per re-upload family removes any content-keyed dedup risk too).
    if args.idbase < 40000:
        print(f"WARNING: idbase {args.idbase} is in the BURNED legacy range (299-1822+ used through "
              "2026-07-06). New families start at 50000 with >=2000 spacing per arm.")
    print("config fingerprint:", fingerprint(), "| EQUITY_ITERS:", botmod.EQUITY_ITERS)

    g = HeadsUpGame(names=("P0", "P1"), starting_stack=STACK, sb=SB, bb=BB, seed=args.seed)
    blocks = []
    for i in range(args.n):
        # Hero is ALWAYS seat 0; the button alternates by hand -> Hero plays SB and BB equally
        # (i%2 would track the button in lockstep -> Hero stuck as SB; seat 0 fixed covers both).
        hero_seat = 0
        names = ["Hero" if k == hero_seat else "Villain" for k in (0, 1)]
        holes, history, result, button = play_hand(
            g, hero_seat, i, resolver={"on": True, "off": False, "live": None}[args.resolver],
            hero_variante=args.hero)
        if args.river_only and len(result["board"]) < 5:
            continue                                         # not a river hand -> skip (keep the upload river-dense)
        if (i + 1) % 25 == 0:
            print(f"  {i + 1}/{args.n} Haende | {len(GEFEUERT)} Selektions-Eingriffe", flush=True)
        dt = BASE_DT + datetime.timedelta(days=args.dayoffset, minutes=3 * i)
        blocks.append(format_hand(args.idbase + i, dt, names, button, holes, history, result, hero_seat))

    text = "\n\n".join(blocks) + "\n"
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    # Konfig-Sidecar IMMER (Audit-Regel 2026-07-05 verallgemeinert: das graded
    # Artefakt selbst traegt den kompletten Env-Fingerprint des Laufs, inkl.
    # TURN_DEFENSE/SLOWPLAY/RAISE_NARROW — nie nur die Konsole).
    import json as _json
    with open(os.path.splitext(args.out)[0] + "_konfig.json", "w", encoding="utf-8") as f:
        _json.dump({"hero": args.hero, "fingerprint": fingerprint(),
                    "equity_iters": botmod.EQUITY_ITERS, "seed": args.seed,
                    "idbase": args.idbase, "dayoffset": args.dayoffset}, f, indent=1)
    # newline="\r\n": the GTOW Analyzer only parses CRLF hand histories (2026-07-06: the first pod/Linux-
    # generated upload produced LF-only files the Analyzer could not analyze; every prior local export was
    # CRLF only because Windows text mode translated it silently). Pin CRLF on every platform.
    with open(args.out, "w", encoding="utf-8", newline="\r\n") as f:
        f.write(text)
    print(f"WROTE {len(blocks)} of {args.n} played hands -> {args.out}  ({len(text)} chars)")
    if GEFEUERT:
        idx_pfad = os.path.splitext(args.out)[0] + "_selektion.txt"
        zeilen = ["Haende, in denen der Guard-Stack eingriff (Roh-Aktion -> Stack-Aktion)",
                  f"Hero-Variante: {args.hero} | Hand-ID-Basis: {args.idbase}", ""]
        zeilen += [f"Hand #{args.idbase + h}  {street}  {roh} -> {neu}"
                   for h, street, roh, neu in GEFEUERT]
        with open(idx_pfad, "w", encoding="utf-8", newline=chr(13) + chr(10)) as f:
            f.write(chr(10).join(zeilen) + chr(10))
        print(f"SELEKTION griff in {len(GEFEUERT)} Entscheidungen ein -> {idx_pfad}")
    if blocks:
        print("\n===== FIRST HAND PREVIEW =====\n")
        print(blocks[0])


if __name__ == "__main__":
    main()
