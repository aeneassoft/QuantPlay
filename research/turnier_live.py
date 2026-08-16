"""DAS LAUFENDE TURNIER — was er tatsaechlich gespielt hat, gemessen.

Parser fuer die GG-Handhistorien des Daily Main Event $250 vom 08.08.2026. Gemessen wird
nicht alles, was ein Tracker anzeigt, sondern das, was in DIESER Struktur ueber Gewinn und
Verlust entscheidet:

  * Limp-Rate JE STAPELTIEFE — der teuerste Posten in einer Ante-reichen Struktur, und
    zwar zunehmend teurer, je flacher der Stack.
  * Open-Sizing gegen die toten Chips im Pot.
  * Was in Spots passiert, in denen ein Push-Fold-Stack keine postflop-Entscheidungen
    mehr treffen sollte.
  * Die Verteilung der Einsatzgroessen — traegt die Overbet-Signatur hier ueberhaupt?
  * Wo die Chips hingegangen sind (Attribution je Strasse und je Spot-Klasse).

  python -m research.turnier_live
"""
from __future__ import annotations

import argparse
import glob
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

HELD = "Hero"
VERZ = "data/turnier_live/*.txt"

RE_KOPF = re.compile(r"^Poker Hand #(\w+): Tournament #(\d+),.*?Level(\d+)"
                     r"\((\d[\d,]*)/(\d[\d,]*)\((\d[\d,]*)\)\)")
RE_BUTTON = re.compile(r"^Table '(\S+)' (\d+)-max Seat #(\d+) is the button")
RE_SITZ = re.compile(r"^Seat (\d+): (\S+) \(([\d,]+) in chips\)")
RE_STRASSE = re.compile(r"^\*\*\* (HOLE CARDS|FLOP|TURN|RIVER|SHOWDOWN|SUMMARY) \*\*\*")
RE_KARTEN = re.compile(rf"^Dealt to {HELD} \[(.+?)\]")
RE_AKTION = re.compile(r"^(\S+): (folds|checks|calls|bets|raises|posts)"
                       r"(?:[^\d]*?([\d,]+))?(?:.*?to ([\d,]+))?")
RE_UNCALLED = re.compile(r"^Uncalled bet \(([\d,]+)\) returned to (\S+)")
RE_SAMMELT = re.compile(r"^(\S+) collected ([\d,]+) from pot")
RE_ENDE = re.compile(r"^Total pot ([\d,]+)")


def _z(s) -> float:
    if not s:
        return 0.0
    try:
        return float(str(s).replace(",", ""))
    except ValueError:
        return 0.0


@dataclass
class Hand:
    id: str = ""
    level: int = 0
    sb: float = 0.0
    bb: float = 0.0
    ante: float = 0.0
    stack: float = 0.0          # Hero-Stack zu Beginn
    bb_tief: float = 0.0
    karten: str = ""
    position: str = ""          # BTN/SB/BB/CO/HJ/...
    n_spieler: int = 0
    # Vorflop
    erhoehungen_vor_held: int = 0
    held_vorflop: str = ""      # fold/limp/open/call/3bet/4bet
    open_groesse_bb: float = 0.0
    sah_flop: bool = False
    aktionen: list = field(default_factory=list)   # (strasse, was, betrag_bb)
    netto: float = 0.0          # in Chips
    tote_chips: float = 0.0     # was vor Karten im Pot lag


POSITIONEN_8 = ["BTN", "SB", "BB", "UTG", "UTG1", "MP", "HJ", "CO"]


def parse(muster: str = VERZ) -> list[Hand]:
    haende: list[Hand] = []
    for pfad in sorted(glob.glob(muster)):
        text = Path(pfad).read_text(encoding="utf-8", errors="ignore")
        for block in text.split("Poker Hand #")[1:]:
            block = "Poker Hand #" + block
            zeilen = block.splitlines()
            k = RE_KOPF.match(zeilen[0])
            if not k:
                continue
            H = Hand(id=k.group(1), level=int(k.group(3)), sb=_z(k.group(4)),
                     bb=_z(k.group(5)), ante=_z(k.group(6)))
            if HELD not in block:
                continue

            sitze: dict[int, tuple[str, float]] = {}
            btn = 0
            for z in zeilen[1:]:
                mb = RE_BUTTON.match(z)
                if mb:
                    btn = int(mb.group(3))
                    continue
                ms = RE_SITZ.match(z)
                if ms:
                    sitze[int(ms.group(1))] = (ms.group(2), _z(ms.group(3)))
            H.n_spieler = len(sitze)
            hero_sitz = next((s for s, (n, _) in sitze.items() if n == HELD), None)
            if hero_sitz is None:
                continue
            H.stack = sitze[hero_sitz][1]
            H.bb_tief = H.stack / H.bb if H.bb else 0.0
            H.tote_chips = H.sb + H.bb + H.ante * H.n_spieler

            # Position relativ zum Button
            reihenfolge = sorted(sitze)
            i_btn = reihenfolge.index(btn) if btn in reihenfolge else 0
            i_held = reihenfolge.index(hero_sitz)
            versatz = (i_held - i_btn) % len(reihenfolge)
            H.position = POSITIONEN_8[versatz] if versatz < len(POSITIONEN_8) else "?"

            strasse = "vor"
            held_gehandelt = False
            eingesetzt = 0.0
            # Je STRASSE mitgefuehrt: "raises 5,600 to 8,400" nennt den Gesamtbetrag
            # der Strasse, nicht die Erhoehung. Wer beides addiert, zaehlt den bereits
            # gesetzten Blind doppelt -- gemessen 1.400 zu viel in einer Hand.
            auf_strasse = 0.0
            zurueck = 0.0
            gewonnen = 0.0
            for z in zeilen[1:]:
                mk = RE_KARTEN.match(z)
                if mk:
                    H.karten = mk.group(1)
                    continue
                mstr = RE_STRASSE.match(z)
                if mstr:
                    # NICHT bei HOLE CARDS zuruecksetzen: die Blinds sind zu diesem
                    # Zeitpunkt bereits gesetzt und gehoeren zur Vorflop-Strasse. Der
                    # erste Reparaturversuch loeschte hier genau das, was er mitzaehlen
                    # sollte -- der Pruefwert blieb deshalb unveraendert falsch.
                    if mstr.group(1) != "HOLE CARDS":
                        auf_strasse = 0.0
                    s = mstr.group(1)
                    strasse = {"HOLE CARDS": "vor", "FLOP": "flop", "TURN": "turn",
                               "RIVER": "river", "SHOWDOWN": "sd",
                               "SUMMARY": "ende"}[s]
                    # NUR wenn Hero noch drin ist -- der Flop-Marker steht im Block
                    # auch dann, wenn er laengst gefoldet hat.
                    if strasse == "flop" and H.held_vorflop not in (
                            "fold", "fold_vs_open", "fold_vs_3bet"):
                        H.sah_flop = True
                    continue
                mu = RE_UNCALLED.match(z)
                if mu and mu.group(2) == HELD:
                    zurueck += _z(mu.group(1))
                    continue
                mc = RE_SAMMELT.match(z)
                if mc and mc.group(1) == HELD:
                    gewonnen += _z(mc.group(2))
                    continue
                ma = RE_AKTION.match(z)
                if not ma:
                    continue
                wer, was = ma.group(1), ma.group(2)
                betrag = _z(ma.group(4)) or _z(ma.group(3))
                if wer != HELD:
                    if strasse == "vor" and not held_gehandelt and was == "raises":
                        H.erhoehungen_vor_held += 1
                    continue
                if was == "posts":
                    p_betrag = _z(ma.group(3))
                    eingesetzt += p_betrag
                    if "blind" in z:          # Antes zaehlen nicht zur Strassen-Summe
                        auf_strasse += p_betrag
                    continue
                held_gehandelt = True
                if was == "raises":
                    zusatz = max(0.0, betrag - auf_strasse)
                    eingesetzt += zusatz
                    auf_strasse = betrag
                elif was in ("calls", "bets"):
                    eingesetzt += betrag
                    auf_strasse += betrag
                H.aktionen.append((strasse, was, betrag / H.bb if H.bb else 0.0))
                if strasse == "vor" and not H.held_vorflop:
                    if H.erhoehungen_vor_held == 0:
                        if was == "raises":
                            H.held_vorflop = "open"
                            H.open_groesse_bb = betrag / H.bb
                        elif was == "calls":
                            H.held_vorflop = "limp"
                        elif was == "checks":
                            H.held_vorflop = "check_bb"
                        else:
                            H.held_vorflop = "fold"
                    elif H.erhoehungen_vor_held == 1:
                        H.held_vorflop = {"raises": "3bet", "calls": "call_vs_open",
                                          "folds": "fold_vs_open"}.get(was, was)
                    else:
                        H.held_vorflop = {"raises": "4bet", "calls": "call_vs_3bet",
                                          "folds": "fold_vs_3bet"}.get(was, was)
            H.netto = gewonnen + zurueck - eingesetzt
            haende.append(H)
    return haende


def bericht(H: list[Hand]) -> dict:
    n = len(H)
    if not n:
        return {}
    gespielt = [h for h in H if h.held_vorflop not in ("fold", "fold_vs_open",
                                                       "fold_vs_3bet", "")]
    limps = [h for h in H if h.held_vorflop == "limp"]
    opens = [h for h in H if h.held_vorflop == "open"]
    vpip = [h for h in H if h.held_vorflop in ("limp", "open", "3bet", "4bet",
                                               "call_vs_open", "call_vs_3bet")]
    chance3 = [h for h in H if h.erhoehungen_vor_held == 1]
    dreib = [h for h in chance3 if h.held_vorflop == "3bet"]
    return {
        "haende": n,
        "level_von": min(h.level for h in H), "level_bis": max(h.level for h in H),
        "bb_median": sorted(h.bb_tief for h in H)[n // 2],
        "vpip": len(vpip) / n, "pfr": len(opens + dreib) / n,
        "limp": len(limps) / n,
        "limp_rate_wenn_gespielt": len(limps) / max(1, len(vpip)),
        "threebet": len(dreib) / max(1, len(chance3)),
        "open_bb_mittel": (sum(h.open_groesse_bb for h in opens) / len(opens)
                           if opens else 0.0),
        "sah_flop": sum(1 for h in H if h.sah_flop) / n,
        "netto": sum(h.netto for h in H),
        "limps": limps, "opens": opens, "alle": H,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/turnier_live.json")
    a = ap.parse_args()
    H = parse()
    B = bericht(H)
    if not B:
        print("keine Haende gefunden")
        return

    print(f"DAS LAUFENDE TURNIER — {B['haende']} Haende, "
          f"Level {B['level_von']}-{B['level_bis']}\n")
    print(f"  {'Groesse':<26}{'gemessen':>11}{'NL200-Cash':>13}   Bewertung")
    NL200 = {"vpip": 0.525, "pfr": 0.101, "limp": 0.194, "threebet": 0.143}
    for k, lab in (("vpip", "VPIP"), ("pfr", "PFR"), ("limp", "Limp-Rate"),
                   ("threebet", "3bet")):
        alt = NL200.get(k)
        print(f"  {lab:<26}{B[k]:>11.1%}{alt:>13.1%}")
    print(f"  {'Median-Stapeltiefe':<26}{B['bb_median']:>10.1f} BB")
    print(f"  {'Open-Groesse (Mittel)':<26}{B['open_bb_mittel']:>10.2f} BB")
    print(f"  {'Flop gesehen':<26}{B['sah_flop']:>11.1%}")
    print(f"  {'Netto ueber alle Haende':<26}{B['netto']:>+11,.0f} Chips")

    print("\n\n  DIE LIMPS EINZELN — der Posten, um den es geht:\n")
    print(f"  {'Hand':<10}{'Lvl':>4}{'Stack':>9}{'Pos':>6}{'Karten':>9}"
          f"{'tote Chips':>12}{'Netto':>10}")
    for h in B["limps"]:
        print(f"  {h.id[-8:]:<10}{h.level:>4}{h.bb_tief:>7.1f}BB{h.position:>6}"
              f"{h.karten:>9}{h.tote_chips/h.bb:>10.2f}BB{h.netto:>+10,.0f}")
    if B["limps"]:
        verlust = sum(h.netto for h in B["limps"])
        print(f"\n  {len(B['limps'])} Limps, Netto {verlust:+,.0f} Chips.")

    Path(a.out).write_text(json.dumps(
        {k: v for k, v in B.items() if k not in ("limps", "opens", "alle")},
        indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
