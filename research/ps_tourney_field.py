"""PS-TURNIERFELD-VERMESSUNG — die $530/$1050-6-max-MTTs, phasenweise (User, 2026-08-04).

Der Kern-Trick: die GEMESSENEN Frequenzen des Pools ENTHALTEN sein ICM-Verhalten bereits —
statt gegnerisches ICM zu simulieren, messen wir die Tightness je PHASE (effektive Stacktiefe
in bb) und geben den Feld-Agenten genau diese phasenbedingten Frequenzen. Tiefe = deep >40bb /
mid 15-40 / short <15 (die bb-Tiefe ist der dominante ICM-Treiber; Spieler-übrig ist über
Tische hinweg aus HHs nicht rekonstruierbar — bewusste Näherung).

  python -m research.ps_tourney_field            # parst + schreibt data/ps_tourney_field.json
"""
from __future__ import annotations

import glob
import json
import re
from collections import defaultdict

HH_GLOB = "data/ps_tourney/hh/**/*.txt"
OUT = "data/ps_tourney_field.json"

_HAND_RE = re.compile(r"^PokerStars Hand #\d+: Tournament #(\d+), \$([\d,]+)\+\$([\d,]+) USD.*?"
                      r"Level [IVXLC]+ \((\d+)/(\d+)\)", re.M)
_SEAT_RE = re.compile(r"^Seat \d+: (.+?) \((\d+) in chips\)", re.M)
_ANTE_RE = re.compile(r"^(.+?): posts the ante (\d+)", re.M)
_ACT_RE = re.compile(r"^(.+?): (folds|checks|calls|bets|raises)(?: (\d+))?(?: to (\d+))?", re.M)
_ALLIN_RE = re.compile(r"and is all-in")

PHASES = (("deep", 40, 10_000), ("mid", 15, 40), ("short", 0, 15))


def _phase(eff_bb: float) -> str:
    for name, lo, hi in PHASES:
        if lo <= eff_bb < hi:
            return name
    return "deep"


def parse() -> dict:
    stats = {ph: defaultdict(lambda: {"hands": 0, "vpip": 0, "pfr": 0, "tb_opp": 0, "tb": 0,
                                      "fr_opp": 0, "fr_fold": 0, "jam": 0})
             for ph, _, _ in PHASES}
    lvl_seen = {}
    buyins = set()
    n_hands = 0
    for f in sorted(glob.glob(HH_GLOB, recursive=True)):
        text = open(f, encoding="utf-8-sig", errors="replace").read()
        heads = list(_HAND_RE.finditer(text))
        for m, nxt in zip(heads, heads[1:] + [None]):
            hand = text[m.start(): nxt.start() if nxt else len(text)]
            n_hands += 1
            bb = float(m.group(5))
            buyins.add(m.group(2).replace(",", ""))
            lvl_seen.setdefault((float(m.group(4)), bb), 0)
            lvl_seen[(float(m.group(4)), bb)] += 1
            seats = {nm: float(ch) for nm, ch in _SEAT_RE.findall(hand)}
            if len(seats) < 2:
                continue
            # Phase JE SPIELER nach EIGENER Tiefe (erste Fassung nahm die Tisch-Tiefe: der
            # Short-Bucket blieb leer, weil Kurzstacks an tiefen Tischen im Deep-Topf landeten -
            # der ICM-Druck gehoert aber zum eigenen Stack)
            ph_of = {nm: _phase(ch / bb) for nm, ch in seats.items()}
            pre = hand.split("*** FLOP ***")[0]
            raises_seen = 0
            vpip_done, pfr_done = set(), set()
            for am in _ACT_RE.finditer(pre):
                who, verb = am.group(1), am.group(2)
                if who not in seats:
                    continue
                st = stats[ph_of[who]][who]
                if verb in ("calls", "bets", "raises"):
                    if who not in vpip_done:
                        st["vpip"] += 1
                        vpip_done.add(who)
                    if verb == "raises":
                        if raises_seen == 1:
                            st["tb"] += 1                   # 3-Bet ausgefuehrt
                        if who not in pfr_done:
                            st["pfr"] += 1
                            pfr_done.add(who)
                        if _ALLIN_RE.search(pre[am.start():am.end() + 40]):
                            st["jam"] += 1
                        raises_seen += 1
                if raises_seen >= 1 and verb in ("folds", "calls", "raises"):
                    st["fr_opp"] += 1
                    if verb == "folds":
                        st["fr_fold"] += 1
                if raises_seen == 1 and verb in ("folds", "calls"):
                    st["tb_opp"] += 1
            for who in seats:
                stats[ph_of[who]][who]["hands"] += 1
    # Aggregation je Phase (Pool-Mittel, gewichtete Spieler)
    pool = {}
    for ph in stats:
        agg = {"hands": 0, "vpip": 0, "pfr": 0, "tb": 0, "tb_opp": 0, "fr_fold": 0, "fr_opp": 0, "jam": 0}
        for st in stats[ph].values():
            for k in agg:
                agg[k] += st[k]
        h = max(1, agg["hands"])
        pool[ph] = {
            "hands": agg["hands"],
            "vpip": agg["vpip"] / h,
            "pfr": agg["pfr"] / h,
            "threebet": agg["tb"] / max(1, agg["tb_opp"]),
            "fold_vs_raise": agg["fr_fold"] / max(1, agg["fr_opp"]),
            "jam_rate": agg["jam"] / h,
        }
    levels = sorted(lvl_seen.items(), key=lambda kv: kv[0][1])
    return {"n_hands": n_hands, "buyins": sorted(buyins),
            "levels": [{"sb": sb, "bb": b, "hands": c} for (sb, b), c in levels],
            "phasen": pool}


def main() -> None:
    d = parse()
    open(OUT, "w", encoding="utf-8").write(json.dumps(d, indent=1))
    print(f"{d['n_hands']} Haende | Buy-ins: {d['buyins']}")
    print("Blind-Level (nach bb):", [(lv['sb'], lv['bb'], lv['hands']) for lv in d['levels'][:10]])
    for ph, st in d["phasen"].items():
        print(f"  {ph:5s} ({st['hands']:6d} Spieler-Haende): VPIP {st['vpip']*100:.0f} / "
              f"PFR {st['pfr']*100:.0f} / 3bet {st['threebet']*100:.0f} / "
              f"FoldVsRaise {st['fold_vs_raise']*100:.0f} / Jam {st['jam_rate']*100:.1f}")


if __name__ == "__main__":
    main()
