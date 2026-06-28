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

from pokerbot.engine.game import HeadsUpGame

import pokerbot.strategy.bot as botmod
botmod.EQUITY_ITERS = 120          # match duplicate.py: fast-but-stable equity
from pokerbot.strategy.bot import PokerBot
from pokerbot.strategy.gto_baseline import GTOBaseline

SB, BB, STACK = 50, 100, 20000     # 0.5/1, 200bb — the gtow benchmark stakes
BASE_ID = 2600000000
BASE_DT = datetime.datetime(2026, 6, 27, 18, 0, 0)


def money(chips: int) -> str:
    """Chips -> PokerStars dollar string (bb=100 chips = $1). Integers without decimals."""
    v = chips / 100.0
    return f"${int(v)}" if v == int(v) else f"${v:.2f}"


# ---- bot deciders (uniform (action, amount) interface) ----
def hero_decider(seat: int, seed: int):
    pb = PokerBot(seat, seed=seed, exploit=False)
    pb.value_raise_eq = 0.72
    def d(st):
        pb.hero_idx = seat
        r = pb.decide(st)
        return r["action"], r["amount"]
    return d


def villain_decider(seat: int, seed: int):
    b = GTOBaseline(seat, seed=seed, iters=120)
    def d(st):
        b.hero = seat
        return b.decide(st)
    return d


def play_hand(g: HeadsUpGame, hero_seat: int, idx: int):
    """Drive one hand to completion; return (holes, history, result, button)."""
    g.players[0].stack = g.players[1].stack = STACK     # cash-game reset to 200bb
    g.start_hand()
    holes = [list(g.players[0].hole), list(g.players[1].hole)]
    button = g.button
    deciders = {hero_seat: hero_decider(hero_seat, seed=100 + idx),
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
    for ev in history:
        act = ev["action"]
        if act == "deal":
            board = ev["board"]
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
    ap.add_argument("--out", default="data/gtow_upload/bot_hands.txt")
    args = ap.parse_args()

    g = HeadsUpGame(names=("P0", "P1"), starting_stack=STACK, sb=SB, bb=BB, seed=args.seed)
    blocks = []
    for i in range(args.n):
        # Hero is ALWAYS seat 0; the button alternates by hand -> Hero plays SB and BB equally
        # (i%2 would track the button in lockstep -> Hero stuck as SB; seat 0 fixed covers both).
        hero_seat = 0
        names = ["Hero" if k == hero_seat else "Villain" for k in (0, 1)]
        holes, history, result, button = play_hand(g, hero_seat, i)
        dt = BASE_DT + datetime.timedelta(days=args.dayoffset, minutes=3 * i)
        blocks.append(format_hand(args.idbase + i, dt, names, button, holes, history, result, hero_seat))

    text = "\n\n".join(blocks) + "\n"
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"WROTE {args.n} hands -> {args.out}  ({len(text)} chars)")
    print("\n===== FIRST HAND PREVIEW =====\n")
    print(blocks[0])


if __name__ == "__main__":
    main()
