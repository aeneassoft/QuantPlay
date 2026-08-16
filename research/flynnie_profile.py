"""FLYNNIE-PROFIL — Auswertung der PokerStars-Handhistorien von 'flynnie4040'.

Zwei Fragen: (1) Passt das Profil zu dem Live-Bild des Ranglisten-Besten
("spielt nicht auf Platz eins, sondern um lange drin zu bleiben")? (2) Welches
Frequenzprofil ergibt sich fuer die Simulation gegen Princes Stil?

Nur NLH-Cash wird statistisch ausgewertet — die 5-Card-PLO-Turniere haben andere
Handregeln und gehen nur in die Metadaten (Format/Zeitraum/Waehrung) ein.

  python -m research.flynnie_profile
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter, defaultdict

ROOT = os.path.join("hand histories", "Roadhouse", "flynnie4040")
HERO = "flynnie4040"
OUT = "data/flynnie_profile.json"

RE_HAND = re.compile(r"^PokerStars Hand #(\d+):\s+(.+?) \((.+?)\) - (\d{4}/\d{2}/\d{2}) (\d+:\d+:\d+)")
RE_TABLE = re.compile(r"^Table '(.+?)' (\S+) Seat #(\d+) is the button")
RE_SEAT = re.compile(r"^Seat (\d+): (.+?) \((\S+) in chips\)")
RE_ACT = re.compile(r"^(.+?): (folds|checks|calls|bets|raises|posts)(.*)$")
RE_MONEY = re.compile(r"[\d.]+")


def money(tok: str) -> float:
    m = RE_MONEY.search(tok.replace(",", ""))
    return float(m.group()) if m else 0.0


def read(path: str) -> str:
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return open(path, encoding=enc).read()
        except UnicodeDecodeError:
            continue
    return open(path, encoding="utf-8", errors="replace").read()


def split_hands(text: str):
    blocks, cur = [], []
    for line in text.splitlines():
        if line.startswith("PokerStars Hand #"):
            if cur:
                blocks.append(cur)
            cur = [line]
        elif cur:
            cur.append(line)
    if cur:
        blocks.append(cur)
    return blocks


def parse_hand(lines: list[str]) -> dict | None:
    m = RE_HAND.match(lines[0])
    if not m:
        return None
    hid, game, stakes, date, tm = m.groups()
    h = {"id": hid, "game": game.strip(), "stakes": stakes.strip(), "date": date, "time": tm,
         "seats": {}, "street": "preflop", "acts": [], "hero_cards": None, "shown": {},
         "table": None, "size": None, "collected": defaultdict(float), "uncalled": (None, 0.0)}
    for ln in lines[1:]:
        mt = RE_TABLE.match(ln)
        if mt:
            h["table"], h["size"] = mt.group(1), mt.group(2)
            continue
        ms = RE_SEAT.match(ln)
        if ms and "*** SUMMARY ***" not in ln:
            h["seats"][ms.group(2)] = money(ms.group(3))
            continue
        if ln.startswith("*** HOLE CARDS"):
            h["street"] = "preflop"; continue
        if ln.startswith("*** FLOP"):
            h["street"] = "flop"; continue
        if ln.startswith("*** TURN"):
            h["street"] = "turn"; continue
        if ln.startswith("*** RIVER"):
            h["street"] = "river"; continue
        if ln.startswith("*** SHOW DOWN") or ln.startswith("*** SUMMARY"):
            h["street"] = "showdown"; continue
        if ln.startswith(f"Dealt to {HERO} "):
            c = re.search(r"\[(.+?)\]", ln)
            if c:
                h["hero_cards"] = c.group(1)
            continue
        mc = re.match(r"^(.+?) collected \S?([\d.,]+) from pot", ln)
        if mc:
            h["collected"][mc.group(1)] += money(mc.group(2)); continue
        mu = re.match(r"^Uncalled bet \(\S?([\d.,]+)\) returned to (.+)$", ln)
        if mu:
            h["uncalled"] = (mu.group(2), money(mu.group(1))); continue
        msh = re.match(r"^(.+?): shows \[(.+?)\]", ln)
        if msh:
            h["shown"][msh.group(1)] = msh.group(2); continue
        ma = RE_ACT.match(ln)
        if ma:
            who, verb, rest = ma.group(1), ma.group(2), ma.group(3)
            amt = money(rest) if rest.strip() else 0.0
            to = None
            mto = re.search(r"to ([\d.,]+)", rest)
            if mto:
                to = money(mto.group(1))
            h["acts"].append({"who": who, "verb": verb, "amt": amt, "to": to,
                              "street": h["street"], "raw": rest.strip()})
    return h


def analyse_nlh(hands: list[dict]) -> dict:
    n = vpip = pfr = tb = tb_opp = fold_tb = tb_faced = 0
    limps = opens = 0
    bets = raises = calls = checks = 0
    wtsd = wsd = 0
    net = 0.0
    invested_total = 0.0
    hero_hands_seen = 0
    positions = Counter()
    showdowns = []
    stakes_c = Counter()
    for h in hands:
        if HERO not in h["seats"]:
            continue
        n += 1
        stakes_c[h["stakes"]] += 1
        pre = [a for a in h["acts"] if a["street"] == "preflop" and a["verb"] != "posts"]
        blinds = sum(a["amt"] for a in h["acts"]
                     if a["who"] == HERO and a["verb"] == "posts")
        inv = blinds
        vol = aggr = False
        raises_before = 0
        for a in h["acts"]:
            if a["who"] != HERO:
                if a["street"] == "preflop" and a["verb"] == "raises":
                    raises_before += 1
                continue
            if a["street"] == "preflop":
                if a["verb"] == "calls":
                    vol = True
                    inv += a["amt"]
                    if raises_before == 0:
                        limps += 1
                elif a["verb"] == "raises":
                    vol = True; aggr = True
                    inv = max(inv, a["to"] or a["amt"])
                    if raises_before == 0:
                        opens += 1
                    elif raises_before == 1:
                        tb += 1
            else:
                if a["verb"] == "bets":
                    bets += 1; inv += a["amt"]
                elif a["verb"] == "raises":
                    raises += 1; inv = max(inv, a["to"] or a["amt"])
                elif a["verb"] == "calls":
                    calls += 1; inv += a["amt"]
                elif a["verb"] == "checks":
                    checks += 1
        # gegen eine 3bet konfrontiert?
        if raises_before >= 2 and any(a["who"] == HERO and a["street"] == "preflop"
                                      and a["verb"] == "raises" for a in h["acts"]):
            tb_faced += 1
        if vol:
            vpip += 1
        if aggr:
            pfr += 1
        if HERO in h["shown"]:
            wtsd += 1
            showdowns.append((h["id"], h["shown"][HERO], h["collected"].get(HERO, 0) > 0))
            if h["collected"].get(HERO, 0) > 0:
                wsd += 1
        won = h["collected"].get(HERO, 0.0)
        if h["uncalled"][0] == HERO:
            won += h["uncalled"][1]
            inv -= 0  # der ungematchte Teil steckt bereits in inv
        net += won - inv
        invested_total += inv
    return {"haende": n, "stakes": dict(stakes_c),
            "vpip": round(vpip / n, 3) if n else None,
            "pfr": round(pfr / n, 3) if n else None,
            "limp": round(limps / n, 3) if n else None,
            "opens": opens, "threebets": tb,
            "postflop_bets": bets, "postflop_raises": raises,
            "postflop_calls": calls, "postflop_checks": checks,
            "af": round((bets + raises) / calls, 2) if calls else None,
            "showdowns_gezeigt": wtsd,
            "wsd": round(wsd / wtsd, 3) if wtsd else None,
            "netto": round(net, 2),
            "gezeigte_haende": showdowns[:40]}


def main():
    files = []
    for dp, _, fns in os.walk(ROOT):
        for fn in fns:
            if fn.endswith(".txt"):
                files.append(os.path.join(dp, fn))
    files.sort()
    all_hands = []
    meta = defaultdict(list)
    for f in files:
        hs = [parse_hand(b) for b in split_hands(read(f))]
        hs = [h for h in hs if h]
        for h in hs:
            h["file"] = os.path.basename(f)
        all_hands += hs
        meta[os.path.basename(os.path.dirname(f))].append((os.path.basename(f), len(hs)))

    nlh = [h for h in all_hands if h["game"].startswith("Hold'em")]
    plo = [h for h in all_hands if "Omaha" in h["game"] or "5 Card" in h["game"]]
    out = {
        "dateien": {k: v for k, v in meta.items()},
        "haende_gesamt": len(all_hands),
        "nlh": len(nlh), "plo_omaha": len(plo),
        "spiele": dict(Counter(h["game"] for h in all_hands)),
        "waehrungen": dict(Counter(re.sub(r"[\d./ ]", "", h["stakes"]) for h in all_hands)),
        "stakes": dict(Counter(h["stakes"] for h in all_hands)),
        "tischgroessen": dict(Counter(h["size"] for h in all_hands)),
        "zeitraum": (min(h["date"] for h in all_hands), max(h["date"] for h in all_hands)),
        "tage": sorted({h["date"] for h in all_hands}),
        "uhrzeiten_ET": dict(Counter(h["time"][:2] for h in all_hands)),
        "tische": dict(Counter(h["table"] for h in all_hands).most_common(12)),
        "gegner_haeufig": dict(Counter(p for h in all_hands for p in h["seats"]
                                       if p != HERO).most_common(15)),
    }
    out["nlh_profil"] = analyse_nlh(nlh)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    show = {k: v for k, v in out.items() if k not in ("tage", "gegner_haeufig", "tische")}
    show["nlh_profil"] = {k: v for k, v in out["nlh_profil"].items() if k != "gezeigte_haende"}
    print(json.dumps(show, indent=1, ensure_ascii=False))
    print("->", OUT)


if __name__ == "__main__":
    main()
