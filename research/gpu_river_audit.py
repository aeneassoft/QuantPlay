"""GPU-RIVER-AUDIT — jede River-Entscheidung der GTOW-Nacht 2 gegen den GPU-Solver.

Fuer jede Hero-River-Aktion beider Arme: das River-Subgame wird mit den am
River-Beginn eingefrorenen Tracker-Ranges (PRINCE-Konfiguration, live-treu)
auf der GPU geloest (RiverCFRBatch, geometrie-gebatcht) und Heros gespielte
Aktion gegen die Solver-Politik seiner konkreten Combo gegradet.

Ausgabe: (1) p(gespielte Aktion)-Verteilung, (2) die klaren Abweichungen
(p_gespielt < 0.10 bei einer Alternativ-Aktion > 0.70) mit Hand-IDs und
realem Ausgang, (3) der Spezial-Blick auf die 9 Riesenpot-Call-Desaster.

$0, deterministisch, GPU-gesaettigt. Run:
  POKERB_TRACKER_ALPHA=0.5 POKERB_TRACKER_CONF_SLOPE=0.7 python -m research.gpu_river_audit
"""
from __future__ import annotations

import json
import sys

from pokerbot.strategy.gpu_resolver import RiverSpot, solve_spots
from pokerbot.strategy.range_tracker import RangeTracker
from research.gtow_tree_census import BB, hero_seat_of, replay
from research.hh_luecken_mine import ARME, SESS, replay_voll
from research.river_bill_replay import START_STACK, spot_state


def extrahiere_spots(arm: str, dateien: list[str]) -> list[RiverSpot]:
    spots = []
    for name in dateien:
        for line in open(SESS / name, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            hand = json.loads(line)
            if hand.get("aivat") is None:
                continue
            _, net, folder, _ = replay(hand)
            hs = hero_seat_of(hand, net, folder)
            if hs is None:
                continue
            acts, _ = replay_voll(hand)
            riv = [(i, a) for i, a in enumerate(acts) if a["street"] == "river"]
            if not riv:
                continue
            i0 = riv[0][0]
            st0 = spot_state(hand, hs, i0, acts)      # State am River-Beginn
            if st0 is None:
                continue
            t = RangeTracker().build(st0)
            hero_w = t.range.get(hs, {})
            vill_w = t.range.get(1 - hs, {})
            if not hero_w or not vill_w:
                continue
            pot_river = st0["pot"]
            eff = min(p["stack"] for p in st0["players"])
            if eff <= 0:
                continue
            btn = st0["button"]
            hero_hole = tuple(st0["players"][hs]["hole"])
            # River-Sequenz mit ZUSATZ-Betraegen (Level-Differenz je Aktor)
            lvl = {0: 0.0, 1: 0.0}
            seq_alle = []
            for _i, a in riv:
                s = a["seat"]
                wer = "hero" if s == hs else "vill"
                if a["kind"] in ("bet", "raise"):
                    zusatz = a["to"] - lvl[s]
                    lvl[s] = a["to"]
                    seq_alle.append((wer, a["kind"], zusatz))
                elif a["kind"] == "call":
                    need = max(lvl.values()) - lvl[s]
                    lvl[s] = max(lvl.values())
                    seq_alle.append((wer, "call", need))
                else:
                    seq_alle.append((wer, a["kind"], 0.0))
            # ein Spot je HERO-Aktion (Frage-Entscheidung = letzte der Teilsequenz)
            for k, (wer, kind, zusatz) in enumerate(seq_alle):
                if wer != "hero":
                    continue
                spots.append(RiverSpot(
                    st0["board"], hero_w, vill_w, pot_river, eff,
                    hero_oop=(hs != btn), seq=seq_alle[:k + 1], hero_hole=hero_hole,
                    tag={"arm": arm, "hand": hand["hand_id"], "kind": kind,
                         "win_bb": float(hand.get("winnings") or 0.0) / BB,
                         "aivat_bb": hand["aivat"] / BB,
                         "pot_bb": pot_river / BB, "zusatz_bb": zusatz / BB}))
    return spots


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("=== GPU-RIVER-AUDIT (Nacht 2; Solver = RiverCFRBatch, Tracker-Ranges PRINCE) ===")
    alle = []
    for arm, dateien in ARME.items():
        alle += extrahiere_spots(arm, dateien)
    print(f"extrahierte Hero-River-Entscheidungen: {len(alle)}")
    res = solve_spots(alle, iters=300)
    n_ok = sum(1 for r in res if r is not None)
    print(f"geloest+navigiert: {n_ok}/{len(alle)}")

    KLAR_P, KLAR_ALT = 0.10, 0.70
    abweichungen = []
    p_summe = {"call": [], "bet": [], "raise": [], "check": [], "fold": []}
    for r in res:
        if r is None:
            continue
        tag = r["tag"]
        gespielt = tag["kind"]
        # gespielte Aktion auf Baum-Vokabular mappen
        if gespielt in ("bet", "raise"):
            kand = [i for i, a in enumerate(r["acts"]) if a.startswith(("bet", "raise"))]
            p_gespielt = max((r["sigma"][i] for i in kand), default=0.0)
        elif gespielt in r["acts"]:
            p_gespielt = r["sigma"][r["acts"].index(gespielt)]
        else:
            continue
        p_summe.setdefault(gespielt, []).append(p_gespielt)
        best_i = max(range(len(r["sigma"])), key=lambda i: r["sigma"][i])
        if p_gespielt < KLAR_P and r["sigma"][best_i] > KLAR_ALT:
            abweichungen.append((tag, gespielt, p_gespielt, r["acts"][best_i],
                                 r["sigma"][best_i], r["expl"]))

    print("\n--- p(gespielte Aktion) laut Solver, je Aktionstyp ---")
    for kind, ps in p_summe.items():
        if ps:
            print(f"  {kind:6s}: n={len(ps):4d}  Mittel p={sum(ps)/len(ps):.3f}  "
                  f"Anteil p<0.10: {sum(1 for p in ps if p < 0.10)/len(ps):.0%}")

    abweichungen.sort(key=lambda x: x[0]["aivat_bb"])
    print(f"\n--- KLARE ABWEICHUNGEN (p_gespielt<{KLAR_P}, Alternative>{KLAR_ALT}): "
          f"{len(abweichungen)} ---")
    for tag, gespielt, pg, alt, palt, expl in abweichungen[:25]:
        print(f"  {tag['arm']:9s} #{tag['hand']:<8d} {gespielt:5s}(p={pg:.2f}) -> Solver {alt:9s}"
              f"(p={palt:.2f})  Pot {tag['pot_bb']:5.1f}bb  real {tag['win_bb']:+7.1f}bb  "
              f"aivat {tag['aivat_bb']:+6.1f}bb  expl {expl:.1f}%")
    verlust_abw = sum(t[0]["aivat_bb"] for t in abweichungen)
    print(f"\nAIVAT-Summe der Abweichungs-Haende: {verlust_abw:+.1f}bb")


if __name__ == "__main__":
    main()
