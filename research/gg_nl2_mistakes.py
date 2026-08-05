"""NL2-FEHLER-ZENSUS (User, 2026-08-05): Wie oft macht der Pool KLARE strategische Fehler?

Vier harte, karten-/linien-basierte Fehlerklassen (bewusst NUR eindeutige Verstoesse —
keine Ergebnis-Orientierung, keine Solver-Graubereiche):
  F1 OPEN-LIMP        : erster freiwilliger Einsatz = Limp (6-max: dominierte Klasse)
  F2 LIMP-CALL        : limpen und dann einen Raise callen (der Compound-Fehler)
  F3 VERPASSTE VALUE  : River checkt durch, Showdown zeigt Two-Pair+ (Bet war Pflicht)
  F4 HOFFNUNGSLOSER CALL: River-Bet gecallt und AIR gezeigt (made_class 'air' — schlaegt
                        keine einzige Value-Hand; Ace-high-Bluffcatcher zaehlen NICHT als air)
F3/F4 nur auf Showdown-Haenden messbar (~5-6% der Haende zeigen Karten) — je GELEGENHEIT
normiert. Kohorten-Split ueber die echten Winrates (data/gg_nl2_pop.json, >=2000 Haende).

  python -m research.gg_nl2_mistakes
"""
from __future__ import annotations

import json
import re
from collections import defaultdict

from pokerbot.engine.evaluator import made_class
from research.gg_nl2_pop import _iter_all

_SHOW = re.compile(r"^(.+?): shows \[(\w\w) (\w\w)\]", re.M)
_BOARD = re.compile(r"^Board \[([^\]]+)\]", re.M)
_ACT = re.compile(r"^(.+?): (folds|checks|calls|bets|raises)", re.M)


def _river_section(hand: str) -> str | None:
    i = hand.find("*** RIVER ***")
    if i < 0:
        return None
    j = hand.find("*** SHOW DOWN ***", i)
    return hand[i:j if j > 0 else len(hand)]


def main() -> None:
    C = defaultdict(lambda: defaultdict(int))       # C[spieler][zaehler]
    pool = defaultdict(int)
    for hand in _iter_all():
        pre = hand.split("*** FLOP ***")[0]
        raises_seen = 0
        limped: set[str] = set()
        acted: set[str] = set()
        for m in _ACT.finditer(pre):
            who, verb = m.group(1), m.group(2)
            if verb in ("calls", "bets", "raises"):
                if verb == "raises":
                    if who in limped:
                        pass
                    raises_seen += 1
                elif verb == "calls":
                    if raises_seen == 0 and who not in acted:
                        C[who]["f1_limp"] += 1
                        pool["f1_limp"] += 1
                        limped.add(who)
                    elif raises_seen >= 1 and who in limped:
                        C[who]["f2_limpcall"] += 1
                        pool["f2_limpcall"] += 1
            if who not in acted and verb in ("folds", "calls", "bets", "raises"):
                if raises_seen == 0 or who in acted:
                    pool["first_in_opp"] += 1
                    C[who]["first_in_opp"] += 1
                acted.add(who)
        pool["hands"] += 1
        # Showdown-Klassen
        shows = _SHOW.findall(hand)
        bm = _BOARD.search(hand)
        if not shows or not bm:
            continue
        board = bm.group(1).split()
        if len(board) < 5:
            continue
        rs = _river_section(hand)
        if rs is None:
            continue
        r_acts = [(m.group(1), m.group(2)) for m in _ACT.finditer(rs)]
        any_bet = any(v in ("bets", "raises") for _, v in r_acts)
        checked_through = (not any_bet) and any(v == "checks" for _, v in r_acts)
        callers = {who for who, v in r_acts if v == "calls"} if any_bet else set()
        for who, c1, c2 in shows:
            cls = made_class(board, [c1, c2])
            if checked_through:
                pool["f3_opp"] += 1
                C[who]["f3_opp"] += 1
                if cls in ("two-pair+", "monster"):
                    pool["f3_missed"] += 1
                    C[who]["f3_missed"] += 1
            if who in callers:
                pool["f4_opp"] += 1
                C[who]["f4_opp"] += 1
                if cls == "air":
                    hi = max("23456789TJQKA".index(c[0]) for c in (c1, c2))
                    if hi < "23456789TJQKA".index("A"):      # Ace-high = legitimer Bluffcatcher
                        pool["f4_hopeless"] += 1
                        C[who]["f4_hopeless"] += 1
    n = pool["hands"]
    print(f"POOL GESAMT ({n} Haende):")
    print(f"  F1 Open-Limp        : {pool['f1_limp']:7d}  = {100*pool['f1_limp']/max(1,pool['first_in_opp']):5.1f}% der First-in-Gelegenheiten")
    print(f"  F2 Limp-Call        : {pool['f2_limpcall']:7d}  = {100*pool['f2_limpcall']/max(1,pool['f1_limp']):5.1f}% der Limps callen dann einen Raise")
    print(f"  F3 Verpasste Value  : {pool['f3_missed']:7d}  = {100*pool['f3_missed']/max(1,pool['f3_opp']):5.1f}% der durchgecheckten River-Showdowns hielten Two-Pair+")
    print(f"  F4 Hoffnungslose Calls: {pool['f4_hopeless']:5d}  = {100*pool['f4_hopeless']/max(1,pool['f4_opp']):5.1f}% der River-Calls am Showdown zeigten pure Air (<A-high)")
    per100 = 100 * (pool['f1_limp'] + pool['f2_limpcall'] + pool['f3_missed'] + pool['f4_hopeless']) / n
    print(f"  -> KLARE Fehler je 100 Haende (nur diese 4 Klassen, Showdown-Sichtfenster): {per100:.1f}")
    # Kohorten
    try:
        pop = json.load(open("data/gg_nl2_pop.json", encoding="utf-8"))["players"]
        BB = 0.02
        coh = {"GEWINNER": set(), "VERLIERER": set()}
        for nm, s in pop.items():
            if s["hands"] >= 2000:
                wr = s["net"] / BB / s["hands"] * 100
                if wr > 5:
                    coh["GEWINNER"].add(nm)
                elif wr < -5:
                    coh["VERLIERER"].add(nm)
        print("KOHORTEN (echte Winrates, >=2000 Haende):")
        for label, names in coh.items():
            agg = defaultdict(int)
            for nm in names:
                for k, v in C[nm].items():
                    agg[k] += v
            print(f"  {label:9s}: Limp {100*agg['f1_limp']/max(1,agg['first_in_opp']):4.1f}% | "
                  f"Limp-Call {100*agg['f2_limpcall']/max(1,agg['f1_limp']):4.0f}% | "
                  f"Verpasste Value {100*agg['f3_missed']/max(1,agg['f3_opp']):4.1f}% "
                  f"(n={agg['f3_opp']}) | Hoffnungslose Calls {100*agg['f4_hopeless']/max(1,agg['f4_opp']):4.1f}% (n={agg['f4_opp']})")
    except FileNotFoundError:
        pass


if __name__ == "__main__":
    main()
