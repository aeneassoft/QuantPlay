"""PREFLOP-PROBE — 30 konstruierte Spots gegen den tag-Kern, Vorhersage vs. Messung.

User-Auftrag (2026-08-06): 30 verschiedene Preflop-Spots bauen, VORHER Annahmen notieren,
dann den Bot spielen lassen und die Annahmen pruefen. Vorhersagen (PRED) wurden VOR dem
ersten Lauf eingetragen und danach nicht angefasst — der Treffer-Report ist das Urteil.

Mechanik: echte Table-Staende (Button fix Seat 0: BTN=0, SB=1, BB=2, UTG=3, HJ=4, CO=5),
Hero-Karten nach dem Deal ueberschrieben (preflop irrelevant fuer Kollisionen — der Kern
liest nur die eigene Handklasse), Gegner-Aktionen geskriptet, dann 200 rng-Seeds fuer die
Mixing-Verteilung des Bots.

  python -m research.preflop_probe
"""
from __future__ import annotations

import random
from collections import Counter

from pokerbot.arena.sixmax import PROFILES, SixMaxBot
from pokerbot.engine.table import Table

SEAT = {"BTN": 0, "SB": 1, "BB": 2, "UTG": 3, "HJ": 4, "CO": 5}
ORDER = ["UTG", "HJ", "CO", "BTN", "SB", "BB"]
BB_CHIPS = 100
SEEDS = 200

# (Name, Hero-Pos, Hero-Karten, Stack_bb, Skript [(Pos, Aktion, Betrag_bb)], PRED, Begruendung)
SPOTS = [
    # ---- RFI (alle folden bis Hero)
    ("01 UTG A9o RFI", "UTG", ["Ah", "9c"], 100, [], "fold", "UTG-Range ~15%, A9o draussen"),
    ("02 UTG 77 RFI", "UTG", ["7h", "7c"], 100, [], "raise", "Paare gehoeren in jede UTG-Range"),
    ("03 HJ KQo RFI", "HJ", ["Kh", "Qc"], 100, [], "raise", "KQo klar in ~19%"),
    ("04 HJ A2s RFI", "HJ", ["Ah", "2h"], 100, [], "fold", "A2s knapp unter HJ-Schwelle"),
    ("05 CO A5s RFI", "CO", ["Ah", "5h"], 100, [], "raise", "Suited Ace in ~26%"),
    ("06 CO K8o RFI", "CO", ["Kh", "8c"], 100, [], "fold", "K8o zu schwach fuer CO"),
    ("07 BTN T7s RFI", "BTN", ["Th", "7h"], 100, [], "raise", "BTN ~42% nimmt T7s mit"),
    ("08 BTN 63o RFI", "BTN", ["6h", "3c"], 100, [], "fold", "63o unter jeder BTN-Range"),
    ("09 SB K9o RFI", "SB", ["Kh", "9c"], 100, [], "raise", "SB raise-or-fold, K9o in ~36%"),
    ("10 BB 84o n. 3 Limpern", "BB", ["8h", "4c"], 100,
     [("UTG", "call", 1), ("HJ", "call", 1), ("CO", "call", 1), ("BTN", "fold", None),
      ("SB", "fold", None)], "check", "Gratis-Flop, nie raisen"),
    # ---- vs Single-Open (2.5bb)
    ("11 BB Q9s vs BTN-Open", "BB", ["Qh", "9h"], 100,
     [("UTG", "fold", None), ("HJ", "fold", None), ("CO", "fold", None),
      ("BTN", "raise", 2.5), ("SB", "fold", None)], "call", "Standard-Defend IP-Preis"),
    ("12 BB 72o vs BTN-Open", "BB", ["7h", "2c"], 100,
     [("UTG", "fold", None), ("HJ", "fold", None), ("CO", "fold", None),
      ("BTN", "raise", 2.5), ("SB", "fold", None)], "fold", "Boden jeder Defend-Range"),
    ("13 BB AQo vs BTN-Open", "BB", ["Ah", "Qc"], 100,
     [("UTG", "fold", None), ("HJ", "fold", None), ("CO", "fold", None),
      ("BTN", "raise", 2.5), ("SB", "fold", None)], "raise", "3bet-Value vs BTN"),
    ("14 CO 88 vs UTG-Open", "CO", ["8h", "8c"], 100,
     [("UTG", "raise", 2.5), ("HJ", "fold", None)], "call", "Set-Mine/Flat vs frueher Range"),
    ("15 BTN AKs vs CO-Open", "BTN", ["Ah", "Kh"], 100,
     [("UTG", "fold", None), ("HJ", "fold", None), ("CO", "raise", 2.5)], "raise", "3bet immer"),
    ("16 SB KJo vs CO-Open", "SB", ["Kh", "Jc"], 100,
     [("UTG", "fold", None), ("HJ", "fold", None), ("CO", "raise", 2.5),
      ("BTN", "fold", None)], "fold", "OOP dominiert-anfaellig, kein Preis"),
    ("17 BB 55 vs UTG-Open", "BB", ["5h", "5c"], 100,
     [("UTG", "raise", 2.5), ("HJ", "fold", None), ("CO", "fold", None),
      ("BTN", "fold", None), ("SB", "fold", None)], "call", "Set-Mine-Preis stimmt"),
    ("18 BTN A4s vs HJ-Open", "BTN", ["Ah", "4h"], 100,
     [("UTG", "fold", None), ("HJ", "raise", 2.5), ("CO", "fold", None)], "call",
     "Flat-Mix; 3bet-Bluff moeglich, primaer Call"),
    # ---- Hero hat geoeffnet, bekommt 3bet
    ("19 CO AKo vs BTN-3bet", "CO", ["Ah", "Kc"], 100,
     [("UTG", "fold", None), ("HJ", "fold", None), ("CO", "raise", 2.5),
      ("BTN", "raise", 8), ("SB", "fold", None), ("BB", "fold", None)], "raise", "4bet-Value"),
    ("20 CO QQ vs BTN-3bet", "CO", ["Qh", "Qc"], 100,
     [("UTG", "fold", None), ("HJ", "fold", None), ("CO", "raise", 2.5),
      ("BTN", "raise", 8), ("SB", "fold", None), ("BB", "fold", None)], "raise", "4bet-Value"),
    ("21 BTN A5s vs SB-3bet", "BTN", ["Ah", "5h"], 100,
     [("UTG", "fold", None), ("HJ", "fold", None), ("CO", "fold", None),
      ("BTN", "raise", 2.5), ("SB", "raise", 9), ("BB", "fold", None)], "fold",
     "Unter der Cont-Schwelle vs 3bet"),
    ("22 HJ KQo vs CO-3bet", "HJ", ["Kh", "Qc"], 100,
     [("UTG", "fold", None), ("HJ", "raise", 2.5), ("CO", "raise", 8),
      ("BTN", "fold", None), ("SB", "fold", None), ("BB", "fold", None)], "fold",
     "Dominierte Broadways folden vs 3bet"),
    ("23 BTN 76s vs BB-3bet", "BTN", ["7h", "6h"], 100,
     [("UTG", "fold", None), ("HJ", "fold", None), ("CO", "fold", None),
      ("BTN", "raise", 2.5), ("SB", "fold", None), ("BB", "raise", 9)], "fold",
     "Niedrige Perzentile, cont-Schwelle verfehlt"),
    # ---- Hero hat ge-3bettet, bekommt 4bet
    ("24 BTN KK, CO 4bettet", "BTN", ["Kh", "Kc"], 100,
     [("UTG", "fold", None), ("HJ", "fold", None), ("CO", "raise", 2.5),
      ("BTN", "raise", 8), ("SB", "fold", None), ("BB", "fold", None),
      ("CO", "raise", 22)], "raise", "5bet/Stack rein"),
    ("25 BTN AQo, CO 4bettet", "BTN", ["Ah", "Qc"], 100,
     [("UTG", "fold", None), ("HJ", "fold", None), ("CO", "raise", 2.5),
      ("BTN", "raise", 8), ("SB", "fold", None), ("BB", "fold", None),
      ("CO", "raise", 22)], "fold", "AQo ist unter der 4bet-Cont-Schwelle"),
    # ---- Kurzstack (eff <= 12bb: Open-Shove-Logik)
    ("26 UTG 10bb A7o", "UTG", ["Ah", "7c"], 10, [], "fold",
     "Jam-Fenster UTG = Spitze (~12%), A7o draussen"),
    ("27 BTN 10bb K9s", "BTN", ["Kh", "9h"], 10, [], "raise",
     "BTN-Jam-Fenster breit, K9s drin (Erwartung: All-in-Sizing)"),
    ("28 BB 12bb 77 vs BTN-Jam", "BB", ["7h", "7c"], 12,
     [("UTG", "fold", None), ("HJ", "fold", None), ("CO", "fold", None),
      ("BTN", "raise", 10), ("SB", "fold", None)], "call", "77 callt Jams bei 12bb"),
    ("29 BB 12bb A2o vs BTN-Jam", "BB", ["Ah", "2c"], 12,
     [("UTG", "fold", None), ("HJ", "fold", None), ("CO", "fold", None),
      ("BTN", "raise", 10), ("SB", "fold", None)], "fold", "A2o unter der Call-Schwelle"),
    # ---- Iso ueber Limper
    ("30 BTN A8o ueber 2 Limper", "BTN", ["Ah", "8c"], 100,
     [("UTG", "call", 1), ("HJ", "fold", None), ("CO", "call", 1)], "raise",
     "Unopened-Pfad: A8o in BTN-~42% -> Iso-Raise"),
]


def build_table(hero_pos: str, hero_cards, stack_bb: int, script) -> Table | None:
    names = [f"p{i}" for i in range(6)]
    t = Table(names, starting_stack=stack_bb * BB_CHIPS, sb=BB_CHIPS // 2, bb=BB_CHIPS,
              seed=1, stacks=[stack_bb * BB_CHIPS] * 6, ante=0, rebuy=False)
    t.button = -1
    t.start_hand()
    hero_seat = SEAT[hero_pos]
    t.seats[hero_seat].hole = list(hero_cards)
    for pos, action, amt_bb in script:
        seat = SEAT[pos]
        assert t.to_act == seat, f"Skript-Fehler: to_act={t.to_act}, erwartet {seat} ({pos})"
        if action == "raise":
            t.act("raise", int(amt_bb * BB_CHIPS))
        elif action == "call":
            t.act("call")
        else:
            t.act(action)
    while t.to_act != hero_seat:                 # RFI-Spots: alle vor Hero folden automatisch
        t.act("fold")
    return t


def main() -> None:
    hits = 0
    print(f"{'Spot':26s} {'PRED':6s} -> Messung (200 Seeds)")
    for name, pos, cards, stack, script, pred, why in SPOTS:
        t = build_table(pos, cards, stack, script)
        obs = t.obs_for(SEAT[pos])
        dist = Counter()
        for s in range(SEEDS):
            bot = SixMaxBot(0, PROFILES["tag"])
            bot._read = lambda o: {}
            bot.rng = random.Random(1000 + s)
            bot.seat = SEAT[pos]
            bot.new_hand(list(range(6)))
            try:
                dec = bot.decide(obs)
                act = dec["action"] if isinstance(dec, dict) else dec[0]
            except Exception as e:  # noqa: BLE001
                act = f"FEHLER:{type(e).__name__}"
            dist[act] += 1
        primary = dist.most_common(1)[0][0]
        ok = primary == pred
        hits += ok
        mix = " ".join(f"{a}:{100*c//SEEDS}%" for a, c in dist.most_common())
        print(f"{name:26s} {pred:6s} -> {mix:34s} {'TREFFER' if ok else 'DANEBEN'}  ({why})")
    print(f"\nTrefferquote der Annahmen: {hits}/{len(SPOTS)}")


if __name__ == "__main__":
    main()
