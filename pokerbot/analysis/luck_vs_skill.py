"""Luck-vs-skill decomposition of a 6-max session — answers "was the heater variance or repeatable?".

Splits the human's net into:
  * NON-showdown net  — pots won/lost without showdown (fold equity = aggression/skill, low variance),
  * SHOWDOWN net      — high variance; for these we compute the human's EXACT flop equity vs the live
    opponents' actual hands and compare expected vs actual => a "luck" (run-good) estimate.
Also reports VPIP / PFR / postflop aggression so we can see if play was tighter/more structured.

Honest caveats: one session is a small sample; equity is taken at the flop as a single proxy for
"got-it-in" quality. Run: python -m pokerbot.analysis.luck_vs_skill [n_sessions]
"""
from __future__ import annotations

import glob
import itertools
import os
import sys
import json

from pokerbot import config
from pokerbot.engine.evaluator import evaluate

CARDS = [r + s for r in "23456789TJQKA" for s in "shdc"]


def flop_equity(hole, opp_holes, flop):
    used = set(hole) | set(flop)
    for oh in opp_holes:
        used |= set(oh)
    deck = [c for c in CARDS if c not in used]
    win = tie = tot = 0
    for t, r in itertools.combinations(deck, 2):
        b = flop + [t, r]
        hs = evaluate(b, hole)
        best_opp = min(evaluate(b, oh) for oh in opp_holes)
        tot += 1
        if hs < best_opp:
            win += 1
        elif hs == best_opp:
            tie += 1
    return (win + 0.5 * tie) / tot if tot else 0.0


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    files = sorted(glob.glob(str(config.DATA_DIR / "sessions" / "session_*.jsonl")),
                   key=os.path.getmtime)[-n:]
    hands = []
    for f in files:
        for ln in open(f, encoding="utf-8"):
            if ln.strip():
                hands.append(json.loads(ln))
    print(f"Analyzing {len(hands)} hands from: {[os.path.basename(f) for f in files]}\n")
    if not hands:
        return
    H = str(hands[0]["human_seat"])
    Hi = hands[0]["human_seat"]

    total = sd_net = nsd_net = 0
    vpip = pfr = won_nosd = 0
    agg = agg_opp = 0
    sd_rows = []   # (hand_no, equity, won, exp_net, act_net)
    for h in hands:
        net = h.get("net", {}).get(H, 0)
        total += net
        acts = h["actions"]
        folded = {a["seat"] for a in acts if a["action"] == "fold"}
        pre = [a for a in acts if a["street"] == "preflop" and a["seat"] == Hi]
        if any(a["action"] in ("call", "raise") for a in pre):
            vpip += 1
        if any(a["action"] == "raise" for a in pre):
            pfr += 1
        for a in acts:
            if a["seat"] == Hi and a["street"] != "preflop":
                agg_opp += 1
                if a["action"] in ("bet", "raise"):
                    agg += 1
        reason = h.get("result", {}).get("reason")
        winners = {w["seat"] for w in h.get("result", {}).get("winners", [])}
        human_in_sd = reason == "showdown" and Hi not in folded
        if not human_in_sd:
            nsd_net += net
            if net > 0 and reason == "fold":
                won_nosd += 1
            continue
        sd_net += net
        board = h["board"]
        opps = [s for s in h["hole"] if int(s) not in folded and s != H]
        if len(board) >= 3 and opps and len(h["hole"][H]) == 2:
            eq = flop_equity(h["hole"][H], [h["hole"][s] for s in opps], board[:3])
            pot = h["result"].get("pot", 0)
            won = h["result"].get("pot", 0) if Hi in winners else 0
            invested = won - net                       # net = won - invested
            exp_net = eq * pot - invested
            sd_rows.append((h["hand_no"], eq, Hi in winners, exp_net, net))

    nh = len(hands)
    print(f"HUMAN net total: {total:+d} chips ({total/100:+.1f} bb)\n")
    print(f"  non-showdown net: {nsd_net:+d}  (fold-equity / aggression — repeatable)")
    print(f"  showdown net:     {sd_net:+d}  (high variance)\n")
    print(f"  VPIP {vpip}/{nh} ({vpip/nh:.0%}) | PFR {pfr}/{nh} ({pfr/nh:.0%}) | "
          f"postflop aggression {agg}/{agg_opp} ({(agg/agg_opp if agg_opp else 0):.0%}) | "
          f"pots won w/o showdown: {won_nosd}")
    if sd_rows:
        exp = sum(r[3] for r in sd_rows)
        act = sum(r[4] for r in sd_rows)
        avg_eq = sum(r[1] for r in sd_rows) / len(sd_rows)
        won_ct = sum(1 for r in sd_rows if r[2])
        print(f"\n  SHOWDOWNS: {len(sd_rows)} (won {won_ct}). Avg flop-equity when reaching showdown: "
              f"{avg_eq:.0%}")
        print(f"  Expected showdown net (equity-weighted): {exp:+.0f}  |  actual: {act:+.0f}")
        print(f"  => run-good (luck) ≈ {act-exp:+.0f} chips ({(act-exp)/100:+.1f} bb)")
        print("\n  per showdown (hand, flop-eq, won, exp_net, act_net):")
        for hn, eq, won, en, an in sd_rows:
            print(f"    h{hn:<3} eq {eq:.0%}  {'WON ' if won else 'lost'}  exp {en:+7.0f}  act {an:+7.0f}")


if __name__ == "__main__":
    main()
