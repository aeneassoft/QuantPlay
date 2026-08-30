"""HH-Luecken-Mining der GTOW-Nacht-2-Laeufe (2026-08-18): WO verliert der Bot sein AIVAT?

Datenbasis (gtow_manifest_2026-08-18.json + Journal GTOW-NACHT2-CHUNK, per mtime zugeordnet):
  kontrolle  = gtow_hands_1787019130.jsonl (PRINCE, Resolver-ON; n=488, AIVAT -31,34)
  v4_prince  = gtow_hands_1787027076.jsonl + gtow_hands_1787033025.jsonl (AUSLESE+PRINCE+Resolver-ON; n=979, -21,12)
Crash-Smoke/Nacht-1-Dateien werden NICHT geladen.

Fragen: (a) Verlust River vs Turn vs Flop; (b) 7/7-SIZE-Tell (turn_wert immer 2/3 Pot -> River-Exploit?);
(c) Check-Range-Capping (Turn-Check -> River-Bet/Call systematisch teuer?).
Replay-Semantik + Hero-Identifikation werden aus research.gtow_tree_census wiederverwendet (validiert:
BB=100 Chips reproduziert exakt die Journal-AIVATs -31,34 / -21,12).

Nur-Lese-Analyse, deterministisch, $0. Run: python -m research.hh_luecken_mine
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from research.gtow_tree_census import BB, SB, _STREETS, hero_seat_of, replay

SESS = Path("data/sessions")
ARME = {
    "kontrolle": ["gtow_hands_1787019130.jsonl"],
    "v4_prince": ["gtow_hands_1787027076.jsonl", "gtow_hands_1787033025.jsonl"],
}
# 2/3-Pot-Band fuer den turn_wert-Guard (Ziel-Fraction 0.667; eng, damit die on-tree 3/4-Pot-Bets
# [Bucket 0.75, PRINCE-Grid] NICHT hineinfallen — sonst vermischt sich der Guard-Fingerabdruck)
DRITTEL2_LO, DRITTEL2_HI = 0.60, 0.72
POT_KLASSEN = [(5, "<=5bb"), (15, "5-15bb"), (40, "15-40bb"), (100, "40-100bb"), (float("inf"), ">100bb")]
WETTEN = ("bet", "raise", "call")               # Aktionen, die Chips einsetzen ("Einsatz")


def replay_voll(hand: dict):
    """Wie census.replay, aber liefert ALLE Aktionen (auch check/call/fold) + den End-Pot.
    Gleiche Token-Semantik: 'bX' kumulativ pro Runde, '_' beendet die Runde, preflop beginnt der Button/SB."""
    players = hand["players"]
    btn = 0 if str(players[0].get("position", "")).upper() in ("SB", "BTN", "BU", "D") else 1
    round_c = {0: 0.0, 1: 0.0}
    round_c[btn], round_c[1 - btn] = SB, BB
    carry = 0.0
    si, actor = 0, btn
    bet_made = True                              # preflop: der BB-Post ist die lebende Bet
    acts = []
    for tok in hand.get("history") or []:
        if tok == "_":
            carry += round_c[0] + round_c[1]
            round_c = {0: 0.0, 1: 0.0}
            si += 1
            actor = 1 - btn
            bet_made = False
            continue
        st = _STREETS[min(si, 3)]
        pot_before = carry + round_c[0] + round_c[1]
        cur = max(round_c.values())
        rec = {"street": st, "seat": actor, "pot_before": pot_before, "to_call": cur - round_c[actor]}
        if tok == "f":
            rec["kind"] = "fold"
            acts.append(rec)
            break
        if tok == "c":
            round_c[actor] = cur
            rec["kind"] = "call"
            acts.append(rec)
        elif tok == "k":
            rec["kind"] = "check"
            acts.append(rec)
        elif tok and tok[0] == "b":
            try:
                to = float(tok[1:])
            except ValueError:
                actor = 1 - actor
                continue
            kind = "raise" if (bet_made or si == 0) else "bet"
            # bet: to/pot; raise: Inkrement ueber den Call relativ zum Post-Call-Pot (wie census._frac)
            frac = to / pot_before if (kind == "bet" and pot_before) else (to - cur) / max(pot_before + cur, 1)
            rec.update(kind=kind, to=to, frac=frac)
            acts.append(rec)
            round_c[actor] = to
            bet_made = True
        actor = 1 - actor
    return acts, carry + round_c[0] + round_c[1]


def pot_klasse(pot_chips: float) -> str:
    pot_bb = pot_chips / BB
    for grenze, name in POT_KLASSEN:
        if pot_bb <= grenze:
            return name
    return POT_KLASSEN[-1][1]


def lade_arm(dateien: list[str]) -> list[dict]:
    """Laedt einen Arm zu je-Hand-Analysezeilen: aivat_bb, Hero-Aktionsliste, Ableitungen."""
    zeilen = []
    unbekannt = 0
    for name in dateien:
        for line in open(SESS / name, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            hand = json.loads(line)
            if hand.get("aivat") is None:
                continue
            _, net, folder, _ = replay(hand)          # validierte Netto-/Folder-Logik
            hs = hero_seat_of(hand, net, folder)
            if hs is None:
                unbekannt += 1
                continue
            acts, endpot = replay_voll(hand)
            hero_acts = [a for a in acts if a["seat"] == hs]
            vill_acts = [a for a in acts if a["seat"] != hs]
            wetten = [a for a in hero_acts if a["kind"] in WETTEN]
            letzte = wetten[-1] if wetten else None
            zeilen.append({
                "id": hand["hand_id"],
                "aivat_bb": hand["aivat"] / BB,
                "final_street": hand.get("street"),
                "pot_kl": pot_klasse(endpot),
                "einsatz_street": letzte["street"] if letzte else "keine",
                "einsatz_kind": letzte["kind"] if letzte else (hero_acts[-1]["kind"] if hero_acts else "keine"),
                "hero_acts": hero_acts,
                "vill_acts": vill_acts,
                "hero_pos": hand["players"][hs]["position"],
            })
    return zeilen, unbekannt


def stat(rows: list[dict]):
    """(Summe bb, n, Mittel bb/100) einer Zeilenmenge."""
    s = sum(r["aivat_bb"] for r in rows)
    n = len(rows)
    return s, n, (s / n * 100.0 if n else 0.0)


def beispiele(rows: list[dict], k: int = 3) -> str:
    worst = sorted(rows, key=lambda r: r["aivat_bb"])[:k]
    return ", ".join(f"#{r['id']}({r['aivat_bb']:+.0f}bb)" for r in worst)


def drucke_topzellen(zeilen: list[dict], arm: str) -> None:
    zellen = defaultdict(list)
    for r in zeilen:
        zellen[(r["einsatz_street"], r["pot_kl"], r["einsatz_kind"])].append(r)
    print(f"\n--- TOP-10 VERLUST-ZELLEN {arm} (letzte-Einsatz-Strasse | Pot-Klasse | Aktionstyp) ---")
    rangliste = sorted(zellen.items(), key=lambda kv: sum(r["aivat_bb"] for r in kv[1]))
    for (st, pk, kind), rows in rangliste[:10]:
        s, n, m = stat(rows)
        print(f"  {st:7s} {pk:9s} {kind:6s}: Summe {s:+8.1f}bb  n={n:3d}  {m:+7.1f} bb/100  | worst: {beispiele(rows)}")


def drucke_strassen(zeilen: list[dict], arm: str) -> None:
    print(f"\n--- (a) STRASSEN-ATTRIBUTION {arm} (AIVAT-Summe bb) ---")
    gesamt, n_ges, m_ges = stat(zeilen)
    print(f"  gesamt: {gesamt:+.1f}bb  n={n_ges}  ({m_ges:+.2f} bb/100)")
    for label, key in (("final erreichte Strasse", "final_street"), ("Strasse des letzten Hero-Einsatzes", "einsatz_street")):
        gruppen = defaultdict(list)
        for r in zeilen:
            gruppen[r[key]].append(r)
        print(f"  nach {label}:")
        for st in ("preflop", "flop", "turn", "river", "keine"):
            if st in gruppen:
                s, n, m = stat(gruppen[st])
                anteil = 100 * s / gesamt if gesamt else 0.0
                print(f"    {st:8s}: {s:+8.1f}bb  ({anteil:5.1f}% des Netto)  n={n:3d}  {m:+7.1f} bb/100  | worst: {beispiele(gruppen[st])}")


def turnbet_zeilen(zeilen: list[dict]):
    """Haende mit einer Hero-Turn-Bet (kind==bet, keine Raise); liefert (rows, frac der ersten Turn-Bet)."""
    out = []
    for r in zeilen:
        tb = [a for a in r["hero_acts"] if a["street"] == "turn" and a["kind"] == "bet"]
        if tb:
            out.append((r, tb[0]["frac"]))
    return out


def drucke_size_tell(zeilen: list[dict], arm: str) -> None:
    tb = turnbet_zeilen(zeilen)
    print(f"\n--- (b) TURN-BET-SIZE {arm} (Hero-Bets am Turn, n={len(tb)}) ---")
    if not tb:
        print("  keine Hero-Turn-Bets")
        return
    verteilung = Counter(round(f * 20) / 20 for _, f in tb)
    top = sorted(verteilung.items(), key=lambda kv: -kv[1])[:6]
    print("  Fraction-Verteilung (0.05-Buckets): " + ", ".join(f"{b:.2f}x{c}" for b, c in top))
    band = [(r, f) for r, f in tb if DRITTEL2_LO <= f <= DRITTEL2_HI]
    print(f"  im 2/3-Pot-Band [{DRITTEL2_LO},{DRITTEL2_HI}]: {len(band)}/{len(tb)} = {100*len(band)/len(tb):.0f}%")
    for name, teil in (("2/3-Band", [r for r, _ in band]), ("andere Size", [r for r, f in tb if not DRITTEL2_LO <= f <= DRITTEL2_HI])):
        if not teil:
            print(f"  {name}: n=0")
            continue
        s, n, m = stat(teil)
        river = [r for r in teil if r["final_street"] == "river"]
        vill_riv_aggr = sum(1 for r in river if any(a["street"] == "river" and a["kind"] in ("bet", "raise") for a in r["vill_acts"]))
        s_r, n_r, m_r = stat(river)
        print(f"  {name}: n={n}  Summe {s:+.1f}bb  {m:+.1f} bb/100 | davon River erreicht n={n_r}: "
              f"{s_r:+.1f}bb ({m_r:+.1f} bb/100), Villain-River-Bet/Raise in {vill_riv_aggr} Haenden | worst: {beispiele(teil)}")
        # Feinschnitt River-Fortsetzung: wie endet die Hand am River nach dieser Turn-Size?
        riv_gruppen = defaultdict(list)
        for r in river:
            riv = [a for a in r["hero_acts"] if a["street"] == "river"]
            label = ("bet/raise" if any(a["kind"] in ("bet", "raise") for a in riv)
                     else "call" if any(a["kind"] == "call" for a in riv)
                     else "fold" if any(a["kind"] == "fold" for a in riv) else "check")
            riv_gruppen[label].append(r)
        for label in sorted(riv_gruppen, key=lambda g: sum(r["aivat_bb"] for r in riv_gruppen[g])):
            rs = riv_gruppen[label]
            s2, n2, m2 = stat(rs)
            print(f"      Hero-River {label:9s}: n={n2:3d}  {s2:+7.1f}bb  {m2:+8.1f} bb/100  | worst: {beispiele(rs, 2)}")


def drucke_capping(zeilen: list[dict], arm: str) -> None:
    print(f"\n--- (c) CHECK-RANGE-CAPPING {arm} (Hero checkt Turn, Hand erreicht River) ---")
    cap = [r for r in zeilen
           if any(a["street"] == "turn" and a["kind"] == "check" for a in r["hero_acts"])
           and r["final_street"] == "river"]
    betl = [r for r in zeilen
            if any(a["street"] == "turn" and a["kind"] in ("bet", "raise") for a in r["hero_acts"])
            and r["final_street"] == "river"]
    for name, rows in (("Turn-CHECK-Linien", cap), ("Turn-BET/RAISE-Linien (Vergleich)", betl)):
        s, n, m = stat(rows)
        print(f"  {name}: n={n}  Summe {s:+.1f}bb  {m:+.1f} bb/100")
    if not cap:
        return
    # Feinschnitt: was tut Hero am River nach dem Turn-Check?
    gruppen = defaultdict(list)
    for r in cap:
        riv = [a for a in r["hero_acts"] if a["street"] == "river"]
        kinds = "-".join(a["kind"] for a in riv) or "keine"
        # gefragte Teilmenge: Hero bettet ODER called am River
        label = ("river-bet" if any(a["kind"] in ("bet", "raise") for a in riv)
                 else "river-call" if any(a["kind"] == "call" for a in riv)
                 else "river-" + ("fold" if any(a["kind"] == "fold" for a in riv) else "check/keine"))
        gruppen[label].append(r)
        r["_riv_line"] = kinds
    for label in sorted(gruppen, key=lambda g: sum(r["aivat_bb"] for r in gruppen[g])):
        rows = gruppen[label]
        s, n, m = stat(rows)
        print(f"    {label:18s}: n={n:3d}  Summe {s:+8.1f}bb  {m:+7.1f} bb/100  | worst: {beispiele(rows)}")
    probe = sum(1 for r in cap for a in r["vill_acts"] if a["street"] == "river" and a["kind"] in ("bet", "raise"))
    print(f"    Villain bettet/raist den River in {probe}/{len(cap)} Turn-Check-Haenden "
          f"({100*probe/len(cap):.0f}% = Druck auf die gecappte Range)")


def main() -> None:
    print("=== HH-LUECKEN-MINING GTOW NACHT 2 (BB=100 Chips; AIVAT aus Hero-Sicht) ===")
    for arm, dateien in ARME.items():
        zeilen, unbekannt = lade_arm(dateien)
        s, n, m = stat(zeilen)
        print(f"\n{'='*20} ARM {arm} {'='*20}")
        print(f"geladen n={n} (hero_unbekannt ausgeschlossen: {unbekannt}); AIVAT {m:+.2f} bb/100, Summe {s:+.1f}bb")
        drucke_strassen(zeilen, arm)
        drucke_topzellen(zeilen, arm)
        drucke_size_tell(zeilen, arm)
        drucke_capping(zeilen, arm)


if __name__ == "__main__":
    main()
