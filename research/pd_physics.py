"""P_D-PHYSIK — drei Gesetze an Princes EIGENEN Haenden (User, 2026-08-05).

Korpus: CoinPoker historisch (Hero 'Princedarkness', 9 Stake-Level 0.02bb..10bb, ~2.2k Haende,
Karten nur bei Showdown) + GG-Tage (Hero 'Hero', data/pd_day/*). Einheitlicher Licht-Parser.

GESETZ 1 — GEWICHTS-SKALIERUNG (lambda*dEV / Krokodil): Leistung als Funktion des
  Einsatzgewichts. 1a: bb/100 je Stake-Level (Vorhersage: steigt MIT den Stakes — gegen den
  normalen Gradienten haerterer Felder). 1b: E[Netto] je Pot-Groessen-Bin innerhalb der Haende
  (Vorhersage: blutet im Kleinpot-Poker, konkurrenzfaehig in grossen Poetten).
GESETZ 2 — ANGEREGTER ZUSTAND MIT RELAXATION (Tilt-Zerfall): nach einem 20bb+-Verlust
  Netto/VPIP als Funktion der Haende-seit-Trigger -> Zerfallskurve.
GESETZ 3 — SITZUNGS-ZERFALL: Netto/VPIP nach Sitzungs-Dritteln (Ermuedung/Langeweile).

  python -m research.pd_physics
"""
from __future__ import annotations

import glob
import re
from collections import defaultdict

CP_DIR = "hand histories/Historisch/princedarkness/CoinPoker/NLH-Holdem"
GG_DIRS = ["data/pd_day/0408/cash", "data/pd_day/0508/cash"]
MONEY = r"[₮$]([0-9]+(?:\.[0-9]+)?)"
_HEAD = re.compile(r"^(?:CoinPoker|Poker) Hand #\w+: Hold'em No Limit \([₮$]([\d.]+)/[₮$]([\d.]+)[^)]*\)"
                   r" - (\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})", re.M)
_POT = re.compile(r"Total pot " + MONEY)


def _hero_res(hand: str, hero: str) -> tuple[float, bool, bool]:
    """(netto, vpip, limp) — dieselbe validierte Buchhaltung wie pd_day.hero_net."""
    blind = re.compile(r"^" + re.escape(hero) + r": posts (?:small blind|big blind) " + MONEY, re.M)
    ante = re.compile(r"^" + re.escape(hero) + r": posts the ante " + MONEY, re.M)
    act = re.compile(r"^" + re.escape(hero) + r": (bets|calls|raises) " + MONEY
                     + r"(?: to " + MONEY + r")?", re.M)
    unc = re.compile(r"Uncalled bet \(" + MONEY + r"\) returned to " + re.escape(hero))
    coll = re.compile(r"^" + re.escape(hero) + r" collected " + MONEY + r" from", re.M)
    parts = re.split(r"\*\*\* (FLOP|TURN|RIVER|SHOWDOWN|SHOW DOWN) \*\*\*", hand)
    streets = [("preflop", parts[0])] + [(parts[i].lower(), parts[i + 1])
                                         for i in range(1, len(parts) - 1, 2)]
    invested = sum(float(m) for m in ante.findall(hand))
    vpip = limp = False
    for street, text in streets:
        if street.startswith("show"):
            continue
        commit = sum(float(m) for m in blind.findall(text)) if street == "preflop" else 0.0
        raised_before_hero = False
        for line_m in re.finditer(r"^(.+?): (folds|checks|calls|bets|raises)", text, re.M):
            if line_m.group(1) == hero and line_m.group(2) in ("calls", "bets", "raises"):
                vpip = True
                if street == "preflop" and line_m.group(2) == "calls" and not raised_before_hero:
                    limp = True
            if line_m.group(2) == "raises":
                raised_before_hero = True
        for m in act.finditer(text):
            verb, amt, to = m.group(1), float(m.group(2)), m.group(3)
            if verb == "raises":
                # bare 'raises X' (ohne 'to') = Kurzform fuer raise-TO X (selten, defensiv)
                commit = float(to) if to is not None else amt
            else:
                commit += amt
        invested += commit
    for m in unc.finditer(hand):
        invested -= float(m.group(1))
    collected = sum(float(m) for m in coll.findall(hand))
    return collected - invested, vpip, limp


def parse_all() -> list[dict]:
    hands = []
    sources = [(f, "Princedarkness") for f in
               sorted(glob.glob(CP_DIR + "/**/*.txt", recursive=True))]
    for d in GG_DIRS:
        sources += [(f, "Hero") for f in sorted(glob.glob(d + "/*.txt"))]
    for f, hero in sources:
        text = open(f, encoding="utf-8-sig", errors="replace").read().replace(",", "")
        heads = list(_HEAD.finditer(text))
        for m, nxt in zip(heads, heads[1:] + [None]):
            hand = text[m.start(): nxt.start() if nxt else len(text)]
            if hero + ":" not in hand and hero + " " not in hand:
                continue
            bb = float(m.group(2))
            net, vpip, limp = _hero_res(hand, hero)
            pm = _POT.search(hand)
            hands.append({"bb": bb, "net": net / bb, "vpip": vpip, "limp": limp,
                          "pot": (float(pm.group(1)) / bb) if pm else 0.0,
                          "ts": m.group(3), "file": f})
    return hands


def _stat(hs: list[dict]) -> str:
    n = len(hs)
    if n == 0:
        return "n=0"
    m = sum(h["net"] for h in hs) / n
    sd = (sum((h["net"] - m) ** 2 for h in hs) / max(1, n - 1)) ** 0.5
    se = sd / n ** 0.5
    vp = 100 * sum(h["vpip"] for h in hs) / n
    return f"{100 * m:+7.1f} ± {100 * se:5.1f} bb/100 | VPIP {vp:4.0f} | n={n}"


def main() -> None:
    H = parse_all()
    print(f"Korpus: {len(H)} Haende (CoinPoker historisch + GG-Tage)\n")

    print("== GESETZ 1a — Leistung je STAKE-GEWICHT (Vorhersage: steigt mit den Stakes) ==")
    buckets = [("micro (bb<=0.05)", lambda b: b <= 0.05), ("low (0.05<bb<=1)", lambda b: 0.05 < b <= 1.0),
               ("mid (1<bb<=2)", lambda b: 1.0 < b <= 2.0), ("high (bb>2)", lambda b: b > 2.0)]
    for label, cond in buckets:
        print(f"  {label:18s}: {_stat([h for h in H if cond(h['bb'])])}")

    print("\n== GESETZ 1b — Netto je POT-GEWICHT (nur bestrittene Haende; Vorhersage: Kleinpot blutet) ==")
    contested = [h for h in H if h["vpip"]]
    for label, lo, hi in [("Kleinpot <=10bb", 0, 10), ("Mittel 10-40bb", 10, 40),
                          ("Gross 40-100bb", 40, 100), ("Sehr gross >100bb", 100, 10 ** 9)]:
        grp = [h for h in contested if lo < h["pot"] <= hi]
        tot = sum(h["net"] for h in grp)
        print(f"  {label:18s}: {_stat(grp)} | Summe {tot:+7.0f} bb")

    print("\n== GESETZ 2 — RELAXATION nach 20bb+-Verlust (je Sitzung, Haende danach) ==")
    by_file = defaultdict(list)
    for h in H:
        by_file[h["file"]].append(h)
    windows = {"1-3": [], "4-10": [], "11-20": [], "baseline": []}
    for hs in by_file.values():
        hs.sort(key=lambda h: h["ts"])
        since = 10 ** 9
        for h in hs:
            if since <= 3:
                windows["1-3"].append(h)
            elif since <= 10:
                windows["4-10"].append(h)
            elif since <= 20:
                windows["11-20"].append(h)
            else:
                windows["baseline"].append(h)
            since = 0 if h["net"] <= -20 else since + 1
    for label in ("1-3", "4-10", "11-20", "baseline"):
        print(f"  {label:9s} Haende danach: {_stat(windows[label])}")

    print("\n== GESETZ 3 — SITZUNGS-DRITTEL (Ermuedung/Langeweile) ==")
    thirds = {"erstes": [], "mittleres": [], "letztes": []}
    for hs in by_file.values():
        hs.sort(key=lambda h: h["ts"])
        k = len(hs) // 3
        if k == 0:
            continue
        thirds["erstes"] += hs[:k]
        thirds["mittleres"] += hs[k:2 * k]
        thirds["letztes"] += hs[2 * k:]
    for label in ("erstes", "mittleres", "letztes"):
        print(f"  {label:9s} Drittel: {_stat(thirds[label])}")


if __name__ == "__main__":
    main()
