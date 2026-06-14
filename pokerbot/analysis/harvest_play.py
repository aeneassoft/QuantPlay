"""Harvest the human's just-played 6-max session(s): verify the reads in his notes and measure the
bots' preflop tendencies (loose-open? fold-to-3bet?). Small sample => directional, but his specific
remembered hands are verifiable. Run: python -m pokerbot.analysis.harvest_play [n_sessions]
"""
from __future__ import annotations

import glob
import json
import os
import sys
from collections import defaultdict

from pokerbot import config


def load_recent(n: int):
    files = sorted(glob.glob(str(config.DATA_DIR / "sessions" / "session_*.jsonl")),
                   key=os.path.getmtime)[-n:]
    hands = []
    for f in files:
        for ln in open(f, encoding="utf-8"):
            ln = ln.strip()
            if ln:
                h = json.loads(ln)
                h["_file"] = os.path.basename(f)
                hands.append(h)
    return files, hands


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    files, hands = load_recent(n)
    print(f"{len(hands)} hands from {len(files)} session(s): {[os.path.basename(f) for f in files]}\n")
    if not hands:
        return
    human = hands[0]["human_seat"]
    st = defaultdict(lambda: {"dealt": 0, "vpip": 0, "pfr": 0, "open": 0, "f3b_faced": 0, "f3b_fold": 0})
    names = {}
    multiway, bb3b = [], []
    bigloss = None
    low_pair_calls = []

    for h in hands:
        pre = [a for a in h["actions"] if a["street"] == "preflop"]
        for s in h["hole"]:
            st[int(s)]["dealt"] += 1
        for w in h.get("result", {}).get("winners", []):
            names[w["seat"]] = w.get("name", "")
        vol, raised, order = set(), set(), []
        for a in pre:
            if a["action"] in ("call", "raise"):
                vol.add(a["seat"])
            if a["action"] == "raise":
                raised.add(a["seat"])
                order.append(a)
        for s in vol:
            st[s]["vpip"] += 1
        for s in raised:
            st[s]["pfr"] += 1
        if order:
            opener = order[0]["seat"]
            st[opener]["open"] += 1
            if len(order) >= 2:                       # a 3bet happened
                st[opener]["f3b_faced"] += 1
                opener_folded = any(a["seat"] == opener and a["action"] == "fold" for a in pre)
                if opener_folded:
                    st[opener]["f3b_fold"] += 1
                tb = order[1]                          # the 3bettor
                if tb["pos"] == "BB":
                    bb3b.append((h["hand_no"], tb["is_human"], order[0]["pos"], opener_folded))
        if order and len(vol) >= 3:
            multiway.append(h["hand_no"])
        nh = h.get("net", {}).get(str(human), 0)
        if bigloss is None or nh < bigloss[1]:
            bigloss = (h, nh)
        # low pocket pair (22-66) that voluntarily put money in
        for s, hole in h["hole"].items():
            si = int(s)
            if len(hole) == 2 and hole[0][0] == hole[1][0] and hole[0][0] in "23456":
                acted = [a["action"] for a in h["actions"] if a["seat"] == si]
                if any(x in ("call", "raise") for x in acted):
                    low_pair_calls.append((h["hand_no"], si, "".join(c[0] for c in hole),
                                           h.get("net", {}).get(s, 0)))

    print("=== BOT PREFLOP TENDENCIES (non-human seats; small sample) ===")
    print(f"{'seat':>4} {'dealt':>5} {'VPIP':>6} {'PFR':>6} {'opens':>6} {'fold-to-3bet':>13}")
    for s in sorted(st):
        if s == human:
            continue
        d = st[s]
        dl = max(1, d["dealt"])
        f3 = f"{d['f3b_fold']}/{d['f3b_faced']}"
        print(f"{s:>4} {d['dealt']:>5} {d['vpip']/dl:>6.0%} {d['pfr']/dl:>6.0%} {d['open']:>6} {f3:>13}")
    tf = sum(st[s]["f3b_faced"] for s in st if s != human)
    ff = sum(st[s]["f3b_fold"] for s in st if s != human)
    print(f"\nBots faced a 3bet {tf}x, folded {ff}x" + (f" ({ff/tf:.0%})" if tf else ""))
    print(f"Multiway raised pots (>=3 voluntary + a raise): {len(multiway)}  hands {multiway}")

    print("\n=== READ #3 — your BB-3bet vs late open ===")
    for hn, ishuman, opos, folded in bb3b:
        who = "YOU" if ishuman else "a bot"
        print(f"  hand {hn}: {who} 3bet from BB vs {opos}-open -> opener {'FOLDED' if folded else 'continued'}")
    if not bb3b:
        print("  (no BB-3bet spots in these hands)")

    print("\n=== READ #1 — low pocket pairs that called/raised ===")
    for hn, si, pr, net in low_pair_calls:
        print(f"  hand {hn}: seat {si} held {pr}{pr} and put money in (seat net {net})")
    if not low_pair_calls:
        print("  (no low-pair entries)")

    h, nh = bigloss
    print(f"\n=== YOUR BIGGEST LOSS: hand {h['hand_no']} ({h['_file']}), your net {nh} ===")
    print(f"  board {h['board']}  result {h['result'].get('reason')} pot {h['result'].get('pot')}")
    print(f"  YOUR hole: {h['hole'].get(str(human))}")
    for s, hole in h["hole"].items():
        if int(s) != human:
            print(f"  seat {s} ({h['positions'].get(s)}): {hole}")
    print("  actions:")
    for a in h["actions"]:
        tag = "YOU" if a["is_human"] else f"s{a['seat']}"
        print(f"    {a['street']:<8} {a['pos']:<4} {tag:<4} {a['action']}"
              + (f" {a['amount']}" if a["amount"] else ""))


if __name__ == "__main__":
    main()
