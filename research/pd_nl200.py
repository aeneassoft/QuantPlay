"""DAS A-GAME AUF NL200 — gemessen, nicht uebernommen.

Korrektur des Nutzers: das A-Game liegt auf NL200 ($1/$2), nicht auf NL2. Das ist keine
Kleinigkeit — das NL2-Profil (research/prince_ecology.PD: VPIP .549 / PFR .153 / Limp .387)
beschreibt das Spiel gegen eine Freizeit-Population. Auf NL200 spielt derselbe Spieler
gegen regulars, und ein Profil, das dort funktioniert, muss anders aussehen.

Gemessen werden die Groessen, die fuer die STRATEGISCHE Uebersetzung zaehlen — also nicht
alles, was ein Tracker anzeigt, sondern die Groessen, aus denen sich eine Strategie
tatsaechlich bauen laesst:
    VPIP / PFR / Limp     -> wie breit und wie teuer wird eingestiegen
    3bet / Fold-vs-3bet   -> Verhalten gegen Widerstand
    AF postflop           -> wann Druck kommt
    Overbet-Anteil        -> ob Gewalt verhaeltnismaessig dosiert wird
    WTSD / W$SD           -> ob breit ausgezahlt wird (die Provokations-Anfaelligkeit)
    Aggression je Strasse -> frueh oder spaet

  python -m research.pd_nl200
"""
from __future__ import annotations

import argparse
import glob
import json
import re
from collections import defaultdict
from pathlib import Path

HELD = "Princedarkness"
VERZ = ("hand histories/Historisch/princedarkness/CoinPoker/NLH-Holdem/1-2/*.txt")

RE_HAND = re.compile(r"^CoinPoker Hand #(\d+):.*?\(\D*([\d.]+)/\D*([\d.]+)")
RE_STRASSE = re.compile(r"^\*\*\* (HOLE CARDS|FLOP|TURN|RIVER|SHOW DOWN|SUMMARY) \*\*\*")
RE_AKTION = re.compile(r"^([^:]+): (folds|checks|calls|bets|raises|posts)"
                       r"(?:.*?to \D*([\d.]+)|\D*([\d.]+))?")
RE_POT = re.compile(r"^Total pot \D*([\d.]+)")
RE_ZEIGT = re.compile(rf"^{re.escape(HELD)}: (shows|mucks)")
RE_SAMMELT = re.compile(rf"^{re.escape(HELD)} collected \D*([\d.]+)")


def _f(*g):
    for x in g:
        if x:
            try:
                return float(x)
            except ValueError:
                pass
    return 0.0


def messe(muster: str = VERZ) -> dict:
    dateien = sorted(glob.glob(muster))
    Z = defaultdict(float)
    haende = 0

    for pfad in dateien:
        text = Path(pfad).read_text(encoding="utf-8", errors="ignore")
        for block in text.split("CoinPoker Hand #")[1:]:
            block = "CoinPoker Hand #" + block
            zeilen = block.splitlines()
            kopf = RE_HAND.match(zeilen[0])
            if not kopf:
                continue
            bb = _f(kopf.group(3)) or 2.0
            if HELD not in block:
                continue
            haende += 1

            strasse = "vor"
            # Vorflop-Merkmale
            pf_erhoeht = 0          # Erhoehungen VOR der Held-Aktion
            held_hat_gehandelt = False
            vpip = pfr = limp = dreibet = 0
            konfrontiert_erhoehung = fold_vs_3bet = chance_3bet = 0
            # Postflop
            aggr = passiv = 0
            aggr_strasse = defaultdict(int)
            overbets = wetten = 0
            pot = 0.0
            sah_flop = showdown = gewann_sd = 0
            gesamtpot = 0.0

            for z in zeilen[1:]:
                m = RE_STRASSE.match(z)
                if m:
                    s = m.group(1)
                    strasse = {"HOLE CARDS": "vor", "FLOP": "flop", "TURN": "turn",
                               "RIVER": "river", "SHOW DOWN": "sd",
                               "SUMMARY": "ende"}[s]
                    if strasse in ("flop",):
                        sah_flop = 1
                    if strasse == "sd" and HELD in block:
                        showdown = 1
                    continue
                mp = RE_POT.match(z)
                if mp:
                    gesamtpot = _f(mp.group(1))
                    continue
                if RE_SAMMELT.match(z):
                    if showdown:
                        gewann_sd = 1
                    continue

                ma = RE_AKTION.match(z)
                if not ma:
                    continue
                wer, was = ma.group(1).strip(), ma.group(2)
                betrag = _f(ma.group(3), ma.group(4))
                if was == "posts":
                    if "blind" in z:
                        pot += betrag
                    continue

                if strasse == "vor":
                    if wer != HELD:
                        if not held_hat_gehandelt and was == "raises":
                            pf_erhoeht += 1
                    else:
                        held_hat_gehandelt = True
                        if pf_erhoeht == 0:
                            if was == "raises":
                                vpip += 1; pfr += 1
                            elif was == "calls":
                                vpip += 1; limp += 1
                        elif pf_erhoeht == 1:
                            chance_3bet = 1
                            if was == "raises":
                                vpip += 1; dreibet += 1
                            elif was == "calls":
                                vpip += 1
                        else:
                            konfrontiert_erhoehung = 1
                            if was == "folds":
                                fold_vs_3bet = 1
                            elif was in ("calls", "raises"):
                                vpip += 1
                    if was in ("calls", "raises", "bets"):
                        pot += betrag
                else:
                    if wer == HELD and strasse in ("flop", "turn", "river"):
                        if was in ("bets", "raises"):
                            aggr += 1
                            aggr_strasse[strasse] += 1
                            wetten += 1
                            # Overbet = mehr als der Pot vor der Wette
                            if pot > 0 and betrag > pot:
                                overbets += 1
                        elif was == "calls":
                            passiv += 1
                    if was in ("calls", "raises", "bets"):
                        pot += betrag

            Z["vpip"] += min(1, vpip)
            Z["pfr"] += min(1, pfr)
            Z["limp"] += min(1, limp)
            Z["dreibet"] += min(1, dreibet)
            Z["chance_3bet"] += chance_3bet
            Z["konfront"] += konfrontiert_erhoehung
            Z["fold_vs_3bet"] += fold_vs_3bet
            Z["aggr"] += aggr
            Z["passiv"] += passiv
            Z["overbets"] += overbets
            Z["wetten"] += wetten
            Z["sah_flop"] += sah_flop
            Z["showdown"] += showdown
            Z["gewann_sd"] += gewann_sd
            Z["pot_bb"] += gesamtpot / bb if bb else 0.0
            for s in ("flop", "turn", "river"):
                Z[f"aggr_{s}"] += aggr_strasse[s]

    n = max(1, haende)
    return {
        "dateien": len(dateien), "haende": haende,
        "vpip": Z["vpip"] / n, "pfr": Z["pfr"] / n, "limp": Z["limp"] / n,
        "threebet": Z["dreibet"] / max(1, Z["chance_3bet"]),
        "fold_vs_3bet": Z["fold_vs_3bet"] / max(1, Z["konfront"]),
        "af": Z["aggr"] / max(1, Z["passiv"]),
        "overbet_share": Z["overbets"] / max(1, Z["wetten"]),
        "wtsd": Z["showdown"] / max(1, Z["sah_flop"]),
        "wsd": Z["gewann_sd"] / max(1, Z["showdown"]),
        "pot_bb": Z["pot_bb"] / n,
        "aggr_flop": Z["aggr_flop"] / max(1.0, Z["aggr"]),
        "aggr_turn": Z["aggr_turn"] / max(1.0, Z["aggr"]),
        "aggr_river": Z["aggr_river"] / max(1.0, Z["aggr"]),
    }


# Zum Vergleich: das NL2-Profil, das ich faelschlich genommen haette.
NL2 = {"vpip": 0.549, "pfr": 0.153, "limp": 0.387, "threebet": 0.108,
       "af": 2.32, "overbet_share": 0.28, "wtsd": 0.295, "wsd": 0.386}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/pd_nl200.json")
    a = ap.parse_args()
    M = messe()
    print(f"DAS A-GAME AUF NL200 — {M['haende']} Haende aus {M['dateien']} Dateien\n")
    print(f"  {'Groesse':<20}{'NL200':>10}{'NL2':>10}   strategische Bedeutung")
    zeilen = [
        ("vpip", "wie breit eingestiegen wird"),
        ("pfr", "wie viel davon mit Initiative"),
        ("limp", "billiger Einstieg ohne Festlegung"),
        ("threebet", "Gegendruck bei Widerstand"),
        ("af", "Aggression nach der Eroeffnung"),
        ("overbet_share", "Unverhaeltnismaessigkeit der Gewalt"),
        ("wtsd", "wie oft es bis zur Abrechnung geht"),
        ("wsd", "ob breit ausgezahlt wird"),
    ]
    for k, bed in zeilen:
        alt = NL2.get(k)
        s_alt = f"{alt:>10.3f}" if alt is not None else f"{'—':>10}"
        print(f"  {k:<20}{M[k]:>10.3f}{s_alt}   {bed}")
    print(f"\n  Aggression je Strasse: Flop {M['aggr_flop']:.0%} · "
          f"Turn {M['aggr_turn']:.0%} · River {M['aggr_river']:.0%}")
    print(f"  Mittlerer Pot: {M['pot_bb']:.1f} bb")
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(M, indent=1), encoding="utf-8")
    print(f"\n  geschrieben: {a.out}")


if __name__ == "__main__":
    main()
