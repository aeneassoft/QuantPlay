"""V8-REPLAY-GEGENTEST — GTOW-Achsen-Gegentest fuer beliebige Guard-Staeple
auf den echten Nacht-2-Haenden (kontrolle + v4_prince).

Frage ($0, deterministisch, Nur-Lese): WO haette ein Guard-Stack in die
HISTORISCH GESPIELTEN Hero-Entscheidungen eingegriffen — und was haetten die
River-FOLD-Eingriffe kontrafaktisch gerettet/gekostet?

Methodik (Bausteine wiederverwendet, nichts editiert):
  * Beide Arme via hh_luecken_mine (ARME/SESS/replay_voll); Hero via der
    validierten gtow_tree_census-Logik (replay + hero_seat_of, BB=100).
  * Der State an JEDEM Hero-Aktions-Index wird live-treu rekonstruiert —
    spot_state_alle = river_bill_replay.spot_state, verallgemeinert auf ALLE
    Strassen (street/board aus dem Spot statt river-fest) + demselben
    Konsistenz-Gatter (eigener Pot == replay_voll-pot_before, sonst
    Ausschluss — NIE mit falschen Zahlen rechnen).
  * Die Dummy-Basis gibt je Spot die HISTORISCHE Aktion zurueck (bet/raise ->
    ('bet', to-Level-Differenz als int) mit dem Street-Level-Tracking wie in
    spot_state; call/check/fold -> (kind, None)). Der Guard-Stack wird darum
    gewickelt; jede Abweichung der Rueckgabe = EIN EINGRIFF.
  * Kontrafaktik NUR fuer River-FOLD-Eingriffe (der einzige saubere Fall:
    der Fold beendet die Hand): fold_net = -committed_total_hero am Spot;
    delta = fold_net - winnings (positiv = der Eingriff haette gerettet).
    Bet->Check-Eingriffe aendern die Zukunft der Hand — dort wird nur
    gezaehlt, nicht bilanziert.

EHRLICHKEIT: Rueckschau-Konfusionsmatrix auf out-of-sample-GTOW-Verhalten —
ein Wirkungs-NACHWEIS-Proxy, KEIN bb/100-Schaetzer (Villain-Anpassung und
Folgestrassen aendern sich nicht mit).

Wiederverwendbar: main(guards=[fabrik1, fabrik2, ...]) mit beliebigen
improver-Guard-Fabriken (Signatur fabrik(make_strat) -> make(seat) -> d(st)).
Default = [river_wert_bremse]; river_gpu_guard kommt NUR mit V8_MIT_GPU=1
dazu (GPU-Solve je Grosspot-Spot ist teuer).

Run: POKERB_TRACKER_ALPHA=0.5 POKERB_TRACKER_CONF_SLOPE=0.7 \
     python -m research.v8_replay_gegentest
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter

from pokerbot.benchmark.gtowizard import _parse_history, parse_cards
from research.gtow_tree_census import BB, hero_seat_of, replay
from research.hh_luecken_mine import ARME, SESS, replay_voll

START_STACK = 20000
BLINDS = [100, 50]
BOARD_KARTEN = {"preflop": 0, "flop": 3, "turn": 4, "river": 5}
TOP_K = 8                                          # Eingriffe je Liste im Report


def spot_state_alle(hand: dict, hero_seat: int, spot_idx: int, acts: list[dict]) -> dict | None:
    """Engine-State am Aktions-Index spot_idx (VOR der Aktion), live-treu —
    wie river_bill_replay.spot_state, aber fuer JEDE Strasse (street + Board-
    Schnitt aus dem Spot) und mit der historischen Aktion als st['_hist_aktion']."""
    players = hand["players"]
    btn = 0 if str(players[0].get("position", "")).upper() in ("SB", "BTN", "BU", "D") else 1
    tokens = [t for t in hand.get("history") or []]
    # Token-Index des Spots: acts zaehlt nur Nicht-'_'-Tokens -> zurueckuebersetzen
    tok_idx, seen = 0, 0
    for i, t in enumerate(tokens):
        if t == "_":
            continue
        if seen == spot_idx:
            tok_idx = i
            break
        seen += 1
    hist_eng, c0, c1, _si = _parse_history(tokens[:tok_idx], button_seat=btn, blinds=BLINDS)
    committed_street = {0: c0, 1: c1}
    # committed_total je Seat via acts-Kumulation (replay_voll-Semantik: Blinds
    # sind das preflop-Startlevel, Runden-Level resettet je Strasse)
    total = {0: float(min(BLINDS)) if btn == 0 else float(max(BLINDS)),
             1: float(min(BLINDS)) if btn == 1 else float(max(BLINDS))}
    lvl = dict(total)                              # laufende Runden-Level
    street_of = "preflop"
    for a in acts[:spot_idx]:
        if a["street"] != street_of:
            lvl = {0: 0.0, 1: 0.0}
            street_of = a["street"]
        s = a["seat"]
        if a["kind"] in ("bet", "raise"):
            total[s] += a["to"] - lvl[s]
            lvl[s] = a["to"]
        elif a["kind"] == "call":
            need = max(lvl.values()) - lvl[s]
            total[s] += need
            lvl[s] = max(lvl.values())
    spot = acts[spot_idx]
    if spot["street"] != street_of:                # der Spot eroeffnet eine neue Strasse
        lvl = {0: 0.0, 1: 0.0}
    n_brd = BOARD_KARTEN.get(spot["street"])
    board_voll = parse_cards(hand.get("board") or "")
    hole = parse_cards(players[hero_seat].get("hole") or "")
    if n_brd is None or len(board_voll) < n_brd or len(hole) != 2:
        return None
    pot = spot["pot_before"]
    cur_bet = max(committed_street.values())
    st = {
        "street": spot["street"], "board": board_voll[:n_brd], "pot": int(pot),
        "bb": int(BB), "current_bet": int(cur_bet), "button": btn, "hand_no": 0,
        "hand_id": hand.get("hand_id"), "history": hist_eng, "to_act": hero_seat,
        "players": [
            {"idx": i,
             "hole": hole if i == hero_seat else ["??", "??"],
             "stack": START_STACK - int(total[i]),
             "committed_street": int(committed_street[i]),
             "committed_total": int(total[i]),
             "folded": False, "all_in": START_STACK - int(total[i]) <= 0,
             "is_button": i == btn}
            for i in (0, 1)
        ],
    }
    # Konsistenz-Gatter: Pot aus eigener Kumulation == replay_voll-pot_before
    if abs(total[0] + total[1] - pot) > 1.0:
        return None
    st["_committed_total_hero"] = total[hero_seat]
    # Die historisch gespielte Aktion in Engine-Form (Basis-Rueckgabe des Dummys)
    if spot["kind"] in ("bet", "raise"):
        st["_hist_aktion"] = ("bet", int(round(spot["to"] - lvl[hero_seat])))
    else:
        st["_hist_aktion"] = (spot["kind"], None)
    return st


def _dummy_basis(seat):
    """Strategie-Fabrik, die je Spot die HISTORISCHE Aktion zurueckgibt (aus dem
    State gelesen, den spot_state_alle stiftet) — der Nullpunkt des Gegentests."""
    def d(st):
        return st["_hist_aktion"]
    return d


def baue_stack(guards):
    """Guard-Fabriken (innerste zuerst) um die Dummy-Basis wickeln -> decide(st)."""
    strat = _dummy_basis
    for fabrik in guards:
        strat = fabrik(strat)
    return strat(0)                                # seat-Argument ist fuer die Guards egal


def _drucke_arm(arm: str, n_spots: int, n_aus: int, eingriffe: list[dict]) -> None:
    print(f"\n--- ARM {arm} ---")
    print(f"Hero-Entscheidungen geprueft: {n_spots}  (ausgeschlossen wg. Rekonstruktion: {n_aus})")
    print(f"Eingriffe gesamt: {len(eingriffe)}")
    zaehler = Counter((e["street"], f"{e['hist'][0]}->{e['neu'][0]}") for e in eingriffe)
    for (street, wandel), c in sorted(zaehler.items()):
        print(f"  {street:7s} {wandel:12s}: {c:3d}")
    folds = [e for e in eingriffe if e["delta_bb"] is not None]
    gerettet = sum(e["delta_bb"] for e in folds if e["delta_bb"] > 0)
    gekostet = sum(e["delta_bb"] for e in folds if e["delta_bb"] <= 0)
    print(f"  Kontrafaktik River-FOLD-Eingriffe (n={len(folds)}): "
          f"gerettet {gerettet:+.1f}bb, gekostet {gekostet:+.1f}bb, NETTO {gerettet + gekostet:+.1f}bb")
    for e in sorted(folds, key=lambda e: -abs(e["delta_bb"]))[:TOP_K]:
        print(f"    #{e['hand_id']}: {e['hist'][0]}->fold  Pot {e['pot_bb']:6.1f}bb  "
              f"real {e['win_bb']:+7.1f}bb  Delta {e['delta_bb']:+7.1f}bb  (AIVAT {e['aivat_bb']:+.1f})")
    andere = [e for e in eingriffe if e["delta_bb"] is None]
    if andere:
        print(f"  Nicht bilanzierbare Eingriffe (n={len(andere)}, Top-{TOP_K} nach Pot):")
        for e in sorted(andere, key=lambda e: -e["pot_bb"])[:TOP_K]:
            print(f"    #{e['hand_id']}: {e['street']} {e['hist']}->{e['neu']}  "
                  f"Pot {e['pot_bb']:6.1f}bb  real {e['win_bb']:+7.1f}bb  (AIVAT {e['aivat_bb']:+.1f})")


def main(guards=None) -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if guards is None:
        from pokerbot.autogym.improver import river_wert_bremse
        guards = [river_wert_bremse]
        if os.environ.get("V8_MIT_GPU") == "1":    # GPU-Solve je Grosspot-Spot = teuer
            from pokerbot.autogym.improver import river_gpu_guard
            guards.append(river_gpu_guard)
    decide = baue_stack(guards)
    namen = " + ".join(getattr(g, "__name__", str(g)) for g in guards)
    print(f"=== V8-REPLAY-GEGENTEST (Guard-Stack: {namen}; GTOW Nacht 2) ===")
    for arm, dateien in ARME.items():
        n_spots = n_aus = 0
        eingriffe = []
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
                acts, _endpot = replay_voll(hand)
                win = float(hand.get("winnings") or 0.0)
                for i, a in enumerate(acts):
                    if a["seat"] != hs:
                        continue
                    st = spot_state_alle(hand, hs, i, acts)
                    if st is None:
                        n_aus += 1
                        continue
                    n_spots += 1
                    hist = st["_hist_aktion"]
                    neu = tuple(decide(st))
                    if neu == hist:
                        continue
                    e = {"hand_id": hand.get("hand_id"), "street": a["street"],
                         "hist": hist, "neu": neu, "pot_bb": st["pot"] / BB,
                         "win_bb": win / BB, "aivat_bb": hand["aivat"] / BB,
                         "delta_bb": None}
                    if neu[0] == "fold" and a["street"] == "river":
                        fold_net = -st["_committed_total_hero"]
                        e["delta_bb"] = (fold_net - win) / BB
                    eingriffe.append(e)
        _drucke_arm(arm, n_spots, n_aus, eingriffe)


if __name__ == "__main__":
    main()
