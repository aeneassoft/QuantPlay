"""EXPERIMENT 10 — inszenierte Trainer-Session (User, 2026-08-06).

Startet den normalen 6-max-Trainer (six_server) auf Port 8010, aber die ersten 10 Hände
sind INSZENIERT: Heros Karten, gezielte Bot-Karten (Steering ueber die fixen Sitz-Profile
Seat1=tag/2=lag/3=nit/4=station/5=maniac) und der komplette Board-Runout sind vorgegeben.
Der Mensch spielt sie blind — die versiegelten Vorhersagen liegen in
research/experiment10_predictions.md (NICHT vorher lesen; Commit-Hash = Vorregistrierung).
Nach Hand 10 spielt der Trainer normal weiter. Alles landet wie immer in data/sessions/.

  python -m research.experiment10        # Server auf http://127.0.0.1:8010
"""
from __future__ import annotations

import webbrowser

from pokerbot.engine.table import Table

# btn: Button-Seat (Hero=Seat 0). Positionen: SB=btn+1, BB=btn+2, UTG=btn+3, HJ=btn+4, CO=btn+5.
# force: Seat -> Karten (Steering). board: [F1,F2,F3,Turn,River].
SCENARIOS = [
    {"btn": 0, "hero": ["Ah", "8c"], "force": {},
     "board": ["Ad", "7s", "2c", "Kh", "3d"]},                                  # 1 BTN A8o RFI
    {"btn": 3, "hero": ["Kh", "Kc"], "force": {2: ["Qh", "Qs"]},
     "board": ["Ts", "7h", "2d", "6c", "3h"]},                                  # 2 UTG KK vs lag-QQ-3bet
    {"btn": 4, "hero": ["Td", "7d"], "force": {4: ["Ad", "Qd"]},
     "board": ["Kd", "2d", "9c", "8c", "Jd"]},                                  # 3 BB Flush-Drama
    {"btn": 1, "hero": ["8h", "8c"], "force": {5: ["Ac", "Kc"]},
     "board": ["Js", "4d", "9h", "2s", "8d"]},                                  # 4 CO 88 vs maniac-AK
    {"btn": 5, "hero": ["Ah", "6c"], "force": {},
     "board": ["As", "Kd", "2s", "9c", "4h"]},                                  # 5 SB A6o RFI
    {"btn": 0, "hero": ["6h", "5h"], "force": {2: ["Ac", "Ad"]},
     "board": ["Kh", "9d", "4c", "Qd", "2h"]},                                  # 6 BTN 65s vs lag-AA-3bet
    {"btn": 2, "hero": ["Qc", "Qd"], "force": {4: ["Kd", "Qs"]},
     "board": ["Kc", "7h", "2s", "4d", "8h"]},                                  # 7 HJ QQ auf K-hoch vs station
    {"btn": 4, "hero": ["Ac", "Jc"], "force": {3: ["Ah", "Qh"]},
     "board": ["As", "8d", "3c", "Qc", "6s"]},                                  # 8 BB AJo Call-down-Test
    {"btn": 0, "hero": ["Th", "9h"], "force": {3: ["Ah", "Kc"]},
     "board": ["Qh", "8c", "4d", "7s", "2c"]},                                  # 9 BTN T9s Float/Bluff-Test
    {"btn": 3, "hero": ["Ac", "Ad"], "force": {1: ["Ks", "Qs"]},
     "board": ["Qc", "Jd", "Th", "8h", "2d"]},                                  # 10 UTG AA Monsterpot-Test
]

_queue = list(SCENARIOS)
_orig_start = Table.start_hand


def _scripted_start(self) -> None:
    scen = _queue.pop(0) if _queue and self.n == 6 else None
    if scen is not None:
        self.button = (scen["btn"] - 1) % self.n
        for s in self.seats:
            s.stack = 10_000                      # jede Szene startet 100bb tief
    _orig_start(self)
    if scen is None:
        return
    used = set(scen["hero"]) | set(scen["board"])
    for cards in scen["force"].values():
        used |= set(cards)
    self.seats[0].hole = list(scen["hero"])
    for seat, cards in scen["force"].items():
        self.seats[seat].hole = list(cards)
    # Kollisionen in nicht-gesteuerten Haenden bereinigen (Ersatz aus dem Deck)
    self.deck.cards = [c for c in self.deck.cards if c not in used]
    for i, s in enumerate(self.seats):
        if i == 0 or i in scen["force"]:
            continue
        s.hole = [c if c not in used else self.deck.cards.pop(0) for c in s.hole]
        used |= set(s.hole)
    self.deck.cards = [c for c in self.deck.cards if c not in used]
    b = scen["board"]
    # Deck poppt vom ENDE: [.., River, Turn, F3, F2, F1] -> Flop=F1,F2,F3, dann Turn, River
    self.deck.cards += [b[4], b[3], b[2], b[1], b[0]]


Table.start_hand = _scripted_start


def main() -> None:
    import uvicorn

    from pokerbot.web.six_server import app
    url = "http://127.0.0.1:8010"
    print(f"EXPERIMENT 10 laeuft: {url}  (die ersten 10 Haende sind inszeniert; danach normal)")
    try:
        webbrowser.open(url)
    except Exception:  # noqa: BLE001
        pass
    uvicorn.run(app, host="127.0.0.1", port=8010, log_level="warning")


if __name__ == "__main__":
    main()
