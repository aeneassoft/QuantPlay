# -*- coding: utf-8 -*-
"""Profiliert Heros (PokerBot) RIVER-Verhalten auf denselben 1000 Händen wie der GTOW-Upload:
Aktion x Hand-Stärke x SPR (Commitment). Zeigt, OB das River-Leck Over-Bluff / Over-Pay-Off /
Mis-Sizing ist und WIE stark Commitment (niedriger SPR) hineinspielt — der Kontext, den GTOW
nicht direkt liefert.

  python -m research.river_probe
"""
from __future__ import annotations
from collections import Counter, defaultdict

from pokerbot.engine.game import HeadsUpGame
from pokerbot.engine.evaluator import best_five_name

import pokerbot.strategy.bot as botmod
botmod.EQUITY_ITERS = 120
from pokerbot.strategy.bot import PokerBot
from pokerbot.strategy.gto_baseline import GTOBaseline

SB, BB, STACK, HERO, N = 50, 100, 20000, 0, 1000


def hero_decider(seat, seed):
    pb = PokerBot(seat, seed=seed, exploit=False); pb.value_raise_eq = 0.72
    def d(st):
        pb.hero_idx = seat; r = pb.decide(st); return r["action"], r["amount"]
    return d


def villain_decider(seat, seed):
    b = GTOBaseline(seat, seed=seed, iters=120)
    def d(st):
        b.hero = seat; return b.decide(st)
    return d


# made-hand -> strength bucket (river showdown value); AIR/PAIR split = pure-bluff vs legit-bluffcatch
STRONG = {"Two Pair", "Three of a Kind", "Straight", "Flush", "Full House",
          "Four of a Kind", "Straight Flush"}
BUCKETS = [("AIR (high card)", {"High Card"}),
           ("PAIR (one pair)", {"Pair", "One Pair"}),
           ("STRONG (2pair+)", STRONG)]


def spr_bucket(spr):
    if spr < 0.5:  return "0  committed (<0.5)"
    if spr < 1.0:  return "1  low (0.5-1)"
    if spr < 2.0:  return "2  mid (1-2)"
    return "3  deep (2+)"


def main():
    rows = []
    g = HeadsUpGame(names=("P0", "P1"), starting_stack=STACK, sb=SB, bb=BB, seed=7)
    for i in range(N):
        g.players[0].stack = g.players[1].stack = STACK
        g.start_hand()
        dec = {HERO: hero_decider(HERO, 100 + i), 1 - HERO: villain_decider(1 - HERO, 200 + i)}
        guard = 0
        while not g.hand_over and guard < 400:
            st = g.state(); a = st["to_act"]; guard += 1
            if st["street"] == "river" and a == HERO:
                la = st["legal"]; pot = st["pot"]
                eff = min(st["players"][0]["stack"], st["players"][1]["stack"])
                spr = eff / pot if pot > 0 else 0.0
                to_call = la["to_call"]; facing = to_call > 0
                made = best_five_name(g.board, g.players[HERO].hole)
                act, amt = dec[a](st)
                put = 0
                if act in ("bet", "raise", "allin") and amt:
                    put = amt - st["players"][HERO]["committed_street"]
                size_pct = (put / pot) if (pot > 0 and put > 0) else None
                rows.append(dict(facing=facing, act=act, made=made, spr=spr,
                                 size_pct=size_pct, to_call_bb=to_call / BB, pot_bb=pot / BB))
                g.act(act, amt)
            else:
                act, amt = dec[a](st); g.act(act, amt)

    print(f"=== RIVER DECISIONS: {len(rows)} (over {N} hands) ===\n")

    # 1) action split
    facing = [r for r in rows if r["facing"]]
    free = [r for r in rows if not r["facing"]]
    print(f"FACING A BET: {len(facing)}   |   FREE (can check/bet): {len(free)}\n")

    def pct(n, d): return f"{100*n/d:.0f}%" if d else "-"

    # 2) facing a bet -> pay-off pattern by strength
    print("--- FACING A RIVER BET (call/fold/raise) by hand strength ---")
    for label, st in BUCKETS:
        sub = [r for r in facing if r["made"] in st]
        c = Counter(r["act"] for r in sub); n = len(sub)
        print(f"  {label:18} n={n:3}  call {pct(c['call'],n)}  fold {pct(c['fold'],n)}  raise {pct(c.get('raise',0)+c.get('allin',0),n)}")
    air_calls = [r for r in facing if r["made"] == "High Card" and r["act"] == "call"]
    print(f"  -> AIR river CALLS (pure pay-offs): {len(air_calls)}  "
          f"avg facing {sum(r['to_call_bb'] for r in air_calls)/max(1,len(air_calls)):.1f}bb\n")

    # 3) free -> bluff pattern by strength
    print("--- FREE (no bet to us): check vs bet by hand strength ---")
    for label, st in BUCKETS:
        sub = [r for r in free if r["made"] in st]
        c = Counter(r["act"] for r in sub); n = len(sub)
        bet = c.get("bet", 0) + c.get("raise", 0) + c.get("allin", 0)
        print(f"  {label:18} n={n:3}  check {pct(c.get('check',0),n)}  bet {pct(bet,n)}")
    air_bets = [r for r in free if r["made"] == "High Card" and r["act"] in ("bet", "raise", "allin")]
    sizes = [r["size_pct"] for r in air_bets if r["size_pct"]]
    print(f"  -> AIR river BETS (pure bluffs): {len(air_bets)}  "
          f"avg size {100*sum(sizes)/max(1,len(sizes)):.0f}% pot\n")

    # 4) commitment: SPR distribution + action mix
    print("--- SPR at river (commitment) x action mix ---")
    by_spr = defaultdict(list)
    for r in rows:
        by_spr[spr_bucket(r["spr"])].append(r)
    for b in sorted(by_spr):
        sub = by_spr[b]; n = len(sub); c = Counter(r["act"] for r in sub)
        bet = c.get("bet", 0) + c.get("raise", 0) + c.get("allin", 0)
        print(f"  SPR {b:20} n={n:3}  bet/raise {pct(bet,n)}  call {pct(c.get('call',0),n)}  "
              f"check {pct(c.get('check',0),n)}  fold {pct(c.get('fold',0),n)}")

    # 5) overall made-hand distribution on the river (sanity)
    print("\n--- made-hand at river (all decisions) ---")
    mc = Counter(r["made"] for r in rows)
    for k, v in mc.most_common():
        print(f"  {k:18} {v}")


if __name__ == "__main__":
    main()
