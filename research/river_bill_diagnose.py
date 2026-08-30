"""RIVER-BILL-DIAGNOSE — Trennschaerfe der Tracker-Equity auf den 20 Trigger-Spots.

Fuer jeden Big-Pot-River-Call-Spot der Nacht 2: eq_exakt vs Tracker-Range,
Pot-Odds, Guard-Entscheid, tatsaechlicher Showdown-Ausgang (Villain-Karten im
HH bekannt) und die WAHRE Equity (0/0.5/1 am River). Frage: korreliert die
Tracker-eq mit dem Ausgang — oder ist der Mechanismus blind?

Run: python -m research.river_bill_diagnose
"""
from __future__ import annotations

import json
import sys

from knowledge_base.math.formulas import equity_needed_to_call
from pokerbot.autogym.improver import _river_eq_exakt
from pokerbot.benchmark.gtowizard import parse_cards
from pokerbot.strategy.range_tracker import RangeTracker
from pokerbot.engine.evaluator import evaluate
from research.gtow_tree_census import BB, hero_seat_of, replay
from research.hh_luecken_mine import ARME, SESS, replay_voll
from research.river_bill_replay import MIN_FRAC, MIN_POT, spot_state


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("=== TRENNSCHAERFE: Tracker-eq vs Wahrheit auf den Trigger-Spots ===")
    print(f"{'arm':10s} {'hand':9s} {'hero':6s} {'board':11s} {'toC/pot':>8s} "
          f"{'podds':>6s} {'eq_trk':>7s} {'wahr':>5s} {'real_bb':>8s}  urteil")
    zeilen = []
    for arm, dateien in ARME.items():
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
                for i, a in enumerate(acts):
                    if not (a["seat"] == hs and a["street"] == "river" and a["kind"] == "call"):
                        continue
                    pot_vor = max(1, a["pot_before"] - a["to_call"])
                    if not (a["to_call"] >= MIN_FRAC * pot_vor
                            and a["pot_before"] + a["to_call"] >= MIN_POT):
                        continue
                    st = spot_state(hand, hs, i, acts)
                    if st is None:
                        continue
                    t = RangeTracker().build(st)
                    cw = t.range.get(1 - hs, {})
                    hole = st["players"][hs]["hole"]
                    board = st["board"]
                    eq = _river_eq_exakt(hole, cw, board) if cw else float("nan")
                    podds = equity_needed_to_call(st["pot"], a["to_call"])
                    vhole = parse_cards(hand["players"][1 - hs]["hole"])
                    sh, sv = evaluate(board, hole), evaluate(board, vhole)
                    wahr = 1.0 if sh < sv else (0.5 if sh == sv else 0.0)
                    win = float(hand.get("winnings") or 0.0) / BB
                    zeilen.append((arm, hand["hand_id"], "".join(hole), hand.get("board", ""),
                                   a["to_call"] / pot_vor, podds, eq, wahr, win, len(cw)))
                    break
    for arm, hid, hole, board, frac, podds, eq, wahr, win, ncw in sorted(
            zeilen, key=lambda z: z[6]):
        guard = "FOLD" if eq == eq and eq < podds - (0.02 if frac >= 1 else 0.04) else "call"
        gut = ("RICHTIG" if (guard == "FOLD") == (wahr == 0.0) else "falsch")
        print(f"{arm:10s} #{hid:<8d} {hole:6s} {board:11s} {frac:8.2f} "
              f"{podds:6.3f} {eq:7.3f} {wahr:5.1f} {win:+8.1f}  {guard}->{gut}  (range n={ncw})")
    # Trennschaerfe-Kennzahl: mittlere Tracker-eq der Gewinner vs Verlierer
    gew = [z[6] for z in zeilen if z[7] >= 0.5 and z[6] == z[6]]
    ver = [z[6] for z in zeilen if z[7] < 0.5 and z[6] == z[6]]
    if gew and ver:
        print(f"\nTracker-eq Mittel: Gewinner {sum(gew)/len(gew):.3f} (n={len(gew)})  "
              f"vs Verlierer {sum(ver)/len(ver):.3f} (n={len(ver)})")
        print("-> Signal vorhanden, wenn Gewinner-eq deutlich > Verlierer-eq.")


if __name__ == "__main__":
    main()
