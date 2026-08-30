"""RIVER-BILL-REPLAY — Konfusionsmatrix des river_bill_guard auf den ECHTEN GTOW-Nacht-2-Haenden.

Frage (Wirkungs-Beweis, $0, deterministisch): Haette der neue Guard die gemessenen
Riesenpot-River-Call-Desaster (hh_luecken_mine: 9 Haende = -121bb = 59% des
v4-Verlusts) gefoldet — und wie viele GEWONNENE Big-Pot-Calls haette er gekostet?

Methodik:
  * Beide Arme (kontrolle + v4_prince) geladen; Hero via validierter
    hero_seat_of-Logik; jede Hand hat maximal EINEN Hero-River-Call (HU).
  * Der State am Call-Spot wird LIVE-TREU rekonstruiert: history via
    gtowizard._parse_history (der validierte Token-Uebersetzer), Villain-Karten
    bleiben '??' (kein Information-Leak in den Tracker).
  * Geprueft wird der ECHTE Guard-Codepfad: river_bill_guard um eine
    Dummy-Basis gewickelt, die immer ('call', None) liefert.
  * Kontrafaktik: fold_net = -committed_total_hero_vor_call; delta =
    fold_net - winnings (positiv = der Fold haette gerettet).
  * Konsistenz-Gatter: der rekonstruierte Pot am Spot muss dem
    replay_voll-pot_before entsprechen (sonst wird die Hand ausgeschlossen
    und gezaehlt — NIE mit falschen Zahlen rechnen, Snowie-Doktrin).

EHRLICHKEIT: Das ist eine Rueckschau-Konfusionsmatrix auf out-of-sample-GTOW-
Verhalten — ein Wirkungs-NACHWEIS-Proxy fuer den Gate-Entscheid, KEIN
bb/100-Schaetzer (der Fold aendert kuenftige Villain-Anpassung nicht mit).

Run: python -m research.river_bill_replay
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from pokerbot.benchmark.gtowizard import _parse_history, parse_cards
from research.gtow_tree_census import BB, hero_seat_of, replay
from research.hh_luecken_mine import ARME, SESS, replay_voll

START_STACK = 20000
BLINDS = [100, 50]
# Trigger-Parameter — MUESSEN mit river_bill_guard-Defaults uebereinstimmen
MIN_FRAC, MIN_POT = 0.6, 3000


def spot_state(hand: dict, hero_seat: int, spot_idx: int, acts: list[dict]) -> dict | None:
    """Engine-State am Aktions-Index spot_idx (VOR der Aktion), live-treu."""
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
    pot = spot["pot_before"]
    board_str = hand.get("board") or ""
    board = parse_cards(board_str)
    hole = parse_cards(players[hero_seat]["hole"])
    if len(board) != 5 or len(hole) != 2:
        return None
    cur_bet = max(committed_street.values())
    st = {
        "street": "river", "board": board, "pot": int(pot), "bb": int(BB),
        "current_bet": int(cur_bet), "button": btn, "hand_no": 0,
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
    pot_eigen = total[0] + total[1]
    if abs(pot_eigen - pot) > 1.0:
        return None
    st["_committed_total_hero"] = total[hero_seat]
    return st


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from pokerbot.autogym.improver import river_bill_guard
    dummy = lambda seat: (lambda st: ("call", None))  # noqa: E731

    print("=== RIVER-BILL-REPLAY (Guard-Konfusionsmatrix, GTOW Nacht 2) ===")
    for arm, dateien in ARME.items():
        d = river_bill_guard(dummy)(0)
        n_spots = n_fold = n_ausgeschlossen = 0
        gerettet, gekostet = [], []
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
                for i, a in enumerate(acts):
                    if not (a["seat"] == hs and a["street"] == "river" and a["kind"] == "call"):
                        continue
                    pot_vor = max(1, a["pot_before"] - a["to_call"])
                    if not (a["to_call"] >= MIN_FRAC * pot_vor
                            and a["pot_before"] + a["to_call"] >= MIN_POT):
                        continue
                    st = spot_state(hand, hs, i, acts)
                    if st is None:
                        n_ausgeschlossen += 1
                        continue
                    n_spots += 1
                    aktion, _amt = d(st)
                    win = float(hand.get("winnings") or 0.0)
                    if aktion == "fold":
                        n_fold += 1
                        fold_net = -st["_committed_total_hero"]
                        delta_bb = (fold_net - win) / BB
                        ziel = gerettet if delta_bb > 0 else gekostet
                        ziel.append((hand["hand_id"], win / BB, delta_bb))
                    break
        print(f"\n--- ARM {arm} ---")
        print(f"Trigger-Spots (River-Call >= {MIN_FRAC}x Pot, Endpot >= {MIN_POT/BB:.0f}bb): "
              f"{n_spots}  (ausgeschlossen wg. Rekonstruktion: {n_ausgeschlossen})")
        print(f"Guard foldet: {n_fold}/{n_spots}")
        s_plus = sum(x[2] for x in gerettet)
        s_minus = sum(x[2] for x in gekostet)
        print(f"  GERETTET (Fold besser): {len(gerettet)} Haende, {s_plus:+.1f}bb")
        for hid, w, dbb in sorted(gerettet, key=lambda x: -x[2])[:8]:
            print(f"    #{hid}: real {w:+.1f}bb -> Fold-Delta {dbb:+.1f}bb")
        print(f"  GEKOSTET (Fold schlechter): {len(gekostet)} Haende, {s_minus:+.1f}bb")
        for hid, w, dbb in sorted(gekostet, key=lambda x: x[2])[:8]:
            print(f"    #{hid}: real {w:+.1f}bb -> Fold-Delta {dbb:+.1f}bb")
        print(f"  NETTO-Kontrafaktik: {s_plus + s_minus:+.1f}bb ueber den Arm")


if __name__ == "__main__":
    main()
