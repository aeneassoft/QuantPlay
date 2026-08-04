"""P_D-TAGES-REPORT — die eigene PokerCraft-Session obduzieren (User, taeglich nutzbar).

Input: ein Tagesordner mit entpackten GG-PokerCraft-Exports (Hero = 'Hero', Karten sichtbar).
  Cash:  exakte Netto-Buchhaltung je Hand (Einsaetze - Uncalled + Collected), Stats vs die
         5 Prep-Regeln (docs/PREP_GG_NL2.md), Value-Gate-Check ueber Heros ECHTE Karten
         (made_class bei River-Bets: Value oder Bluff?), Tilt-Fenster (20 Haende nach jedem
         20bb+-Showdown-Verlust — die H4-Trigger-Messung auf dem eigenen Tag).
  Spin:  Platz je Turnier aus den Bust-Verlaeufen rekonstruiert (Preise stehen nicht im Export;
         2x-Standard-Annahme fuer die $-Schaetzung, Tier aus dem Namen 'Spin&Gold #N').

  python -m research.pd_day --dir data/pd_day/0408
"""
from __future__ import annotations

import argparse
import glob
import re
from collections import defaultdict

from pokerbot.engine.evaluator import made_class

MONEY = r"\$?([0-9]+(?:\.[0-9]+)?)"
_HAND = re.compile(r"^Poker Hand #(\w+):.*?\((\$[\d.]+)/(\$[\d.]+)\).*?- (\d{4}/\d{2}/\d{2} "
                   r"\d{2}:\d{2}:\d{2})", re.M)
_TOUR = re.compile(r"^Poker Hand #(\w+): Tournament #(\d+),? (.+?) Hold'em.*?- Level(\d+)\("
                   r"(\d+)/(\d+)\).*?- (\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})", re.M)
_SEAT = re.compile(r"^Seat \d+: (.+?) \(" + MONEY + r" in chips\)", re.M)
_BLIND = re.compile(r"^Hero: posts (?:small blind|big blind) " + MONEY, re.M)
_ANTE = re.compile(r"^Hero: posts the ante " + MONEY, re.M)
_ACT = re.compile(r"^Hero: (bets|calls|raises) " + MONEY + r"(?: to " + MONEY + r")?", re.M)
_UNC = re.compile(r"Uncalled bet \(" + MONEY + r"\) returned to Hero")
_COLL = re.compile(r"^Hero collected " + MONEY + r" from pot", re.M)
_CARDS = re.compile(r"Dealt to Hero \[(\w\w) (\w\w)\]")
_BOARD = re.compile(r"\*\*\* RIVER \*\*\* \[([^\]]+)\] \[(\w\w)\]")


def _streets(hand: str) -> list[tuple[str, str]]:
    """[(street, text)] in Reihenfolge."""
    parts = re.split(r"\*\*\* (FLOP|TURN|RIVER|SHOWDOWN|SHOW DOWN) \*\*\*", hand)
    out = [("preflop", parts[0])]
    for i in range(1, len(parts) - 1, 2):
        out.append((parts[i].lower().replace(" ", ""), parts[i + 1]))
    return out


def hero_net(hand: str) -> float:
    """Exakte Hero-Buchhaltung. Semantik: 'bets/calls X' ADDIEREN zum Street-Commit;
    'raises X to Y' SETZT ihn auf Y (Y enthaelt bereits gepostete Blinds/fruehere Einsaetze
    der Street). invested = Summe der finalen Street-Commits + Antes − Uncalled."""
    invested = sum(float(m) for m in _ANTE.findall(hand))
    for street, text in _streets(hand):
        if street.startswith("show"):
            continue
        commit = sum(float(m) for m in _BLIND.findall(text)) if street == "preflop" else 0.0
        for m in _ACT.finditer(text):
            verb, amt, to = m.group(1), float(m.group(2)), m.group(3)
            if verb == "raises":
                commit = float(to)
            else:
                commit += amt
        invested += commit
    for m in _UNC.finditer(hand):
        invested -= float(m.group(1))
    collected = sum(float(m) for m in _COLL.findall(hand))
    return collected - invested


def cash_report(files: list[str]) -> None:
    hands = []
    for f in files:
        text = open(f, encoding="utf-8-sig", errors="replace").read().replace(",", "")
        heads = list(_HAND.finditer(text))
        for m, nxt in zip(heads, heads[1:] + [None]):
            hand = text[m.start(): nxt.start() if nxt else len(text)]
            bb = float(m.group(3).lstrip("$"))
            hands.append({"id": m.group(1), "bb": bb, "ts": m.group(4), "text": hand})
    hands.sort(key=lambda h: h["ts"])
    st = defaultdict(float)
    river_bets = {"value": 0, "bluff": 0, "bluff_ids": []}
    nets = []
    for h in hands:
        hand, bb = h["text"], h["bb"]
        net = hero_net(hand)
        h["net_bb"] = net / bb
        nets.append(net / bb)
        st["hands"] += 1
        pre = _streets(hand)[0][1]
        acts = [(m.group(1), m.group(2)) for m in _ACT.finditer(pre)]
        raised_before = re.search(r"^(?!Hero)(.+?): raises", pre, re.M)
        if acts:
            st["vpip"] += 1
            if any(a[0] == "raises" for a in acts):
                st["pfr"] += 1
            elif not raised_before:
                st["limp"] += 1
        if raised_before:
            st["fr_opp"] += 1
            hero_after = re.search(r"^Hero: (folds|calls|raises)", pre[raised_before.end():], re.M)
            if hero_after:
                st["fr_fold" if hero_after.group(1) == "folds" else "fr_cont"] += 1
                if hero_after.group(1) == "raises":
                    st["threebet"] += 1
        if "*** SHOWDOWN ***" in hand and "Hero: shows" in hand:
            st["wtsd"] += 1
            if net > 0:
                st["wsd"] += 1
        # VALUE-GATE-CHECK: Heros River-Bets nach echter Handstaerke klassifiziert
        cm = _CARDS.search(hand)
        bm = _BOARD.search(hand)
        if cm and bm:
            for street, text in _streets(hand):
                if street == "river" and re.search(r"^Hero: (bets|raises)", text, re.M):
                    board = bm.group(1).split() + [bm.group(2)]
                    cls = made_class(board, [cm.group(1), cm.group(2)])
                    key = "bluff" if cls in ("air", "pair") else "value"
                    river_bets[key] += 1
                    if key == "bluff":
                        river_bets["bluff_ids"].append(h["id"])
    n = int(st["hands"])
    total = sum(h["net_bb"] * h["bb"] for h in hands)
    print(f"CASH: {n} Haende | Netto ${total:+.2f} | "
          f"{100 * sum(nets) / max(1, n):+.1f} bb/100")
    print(f"  VPIP {100*st['vpip']/n:.0f} (Ziel ~22) | PFR {100*st['pfr']/n:.0f} | "
          f"Limp {100*st['limp']/n:.1f} (Ziel 0) | 3bet-Anteil {st['threebet']:.0f}x | "
          f"FvR {100*st['fr_fold']/max(1,st['fr_opp']+0):.0f} (Ziel ~75) | "
          f"WTSD {st['wtsd']:.0f} davon gewonnen {st['wsd']:.0f}")
    rb = river_bets
    print(f"  VALUE-GATE: {rb['value']} River-Value-Bets vs {rb['bluff']} River-Bluffs "
          f"{'(IDs: ' + ', '.join(rb['bluff_ids'][:4]) + ')' if rb['bluff_ids'] else ''}")
    big = sorted(hands, key=lambda h: h["net_bb"])
    print("  Groesste Verluste:", [(h["id"], f"{h['net_bb']:+.0f}bb", h["ts"][-8:]) for h in big[:3]])
    print("  Groesste Gewinne :", [(h["id"], f"{h['net_bb']:+.0f}bb", h["ts"][-8:]) for h in big[-3:]])
    # TILT-FENSTER: 20 Haende nach jedem 20bb+-Showdown-Verlust
    trig = [i for i, h in enumerate(hands)
            if h["net_bb"] <= -20 and "*** SHOWDOWN ***" in h["text"]]
    if trig:
        win_net, win_n, marked = 0.0, 0, set()
        for i in trig:
            for j in range(i + 1, min(i + 21, len(hands))):
                if j not in marked:
                    marked.add(j)
                    win_net += hands[j]["net_bb"]
                    win_n += 1
        base = (sum(nets) - win_net) / max(1, n - win_n)
        print(f"  TILT-FENSTER: {len(trig)} Trigger (20bb+-SD-Verlust) -> danach "
              f"{100*win_net/max(1,win_n):+.1f} bb/100 in {win_n} Haenden "
              f"(Baseline sonst {100*base:+.1f}) — Delta {100*(win_net/max(1,win_n)-base):+.1f}")
    else:
        print("  TILT-FENSTER: kein 20bb+-Showdown-Verlust heute")


def spin_report(files: list[str]) -> None:
    tours = defaultdict(list)
    tier_of = {}
    for f in files:
        text = open(f, encoding="utf-8-sig", errors="replace").read().replace(",", "")
        heads = list(_TOUR.finditer(text))
        for m, nxt in zip(heads, heads[1:] + [None]):
            hand = text[m.start(): nxt.start() if nxt else len(text)]
            tours[m.group(2)].append({"ts": m.group(7), "text": hand})
            tm = re.search(r"Spin&Gold #([\d.]+)", m.group(3))
            if tm:
                tier_of[m.group(2)] = float(tm.group(1))
    wins = losses = 0
    net_assumed = 0.0
    for tid, hs in sorted(tours.items(), key=lambda kv: kv[1][0]["ts"]):
        hs.sort(key=lambda h: h["ts"])
        last = hs[-1]["text"]
        seats = _SEAT.findall(last)
        hero_alive_last = any(nm == "Hero" for nm, _ in seats)
        won = hero_alive_last and bool(_COLL.search(last)) and \
            "Hero: folds" not in last.split("*** ")[-1]
        # Sieg = Hero sammelt den letzten Pot der letzten Hand des Turniers ein UND
        # danach existiert keine weitere Hand — robuste Naeherung: letzter Collector
        last_coll = re.findall(r"^(.+?) collected [\d.]+ from pot", last, re.M)
        won = bool(last_coll) and last_coll[-1] == "Hero"
        tier = tier_of.get(tid, 1.0)
        if won:
            wins += 1
            net_assumed += tier            # 2x-Multiplikator-Annahme: +1 Buy-in
        else:
            losses += 1
            net_assumed -= tier
        print(f"  Turnier {tid} (${tier:g}): {'SIEG' if won else 'verloren'} "
              f"({len(hs)} Haende, {hs[0]['ts'][-8:]}-{hs[-1]['ts'][-8:]})")
    n = wins + losses
    print(f"SPIN: {n} Spiele | {wins} Siege ({100*wins/max(1,n):.0f}%) | "
          f"$-Schaetzung (2x-Annahme): {net_assumed:+.2f} | Breakeven-P(Sieg) 35.8%")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="data/pd_day/0408")
    a = ap.parse_args()
    cash = sorted(glob.glob(a.dir + "/cash/*.txt"))
    spin = sorted(glob.glob(a.dir + "/spin/*.txt"))
    nl2 = [f for f in cash if "0.01 - 0.02" in f]
    other = [f for f in cash if f not in nl2]
    if nl2:
        print("== NL2 ==")
        cash_report(nl2)
    if other:
        print("== ANDERE STAKES (Shot?) ==")
        cash_report(other)
    if spin:
        print("== SPIN & GOLD ==")
        spin_report(spin)


if __name__ == "__main__":
    main()
