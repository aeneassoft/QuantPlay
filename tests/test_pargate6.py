"""pargate6 A/A-Nulltest in-process: Kandidat == Incumbent muss auf 6 Decks EXAKT 0 sein (tag-Held + HU-Arena
n=2 mit dem exploit_gate-Helden), Chip-Erhaltung je Hand, Rotation deckt alle Sitze. Run: python -m tests.test_pargate6"""
from __future__ import annotations

import os

os.environ.update({"POKERB_PRINCE": "0", "POKERB_GTO_MODE": "0", "POKERB_EXPLOIT": "1"})

from pokerbot.arena.sixmax import PROFILES, SixMaxBot  # noqa: E402
from pokerbot.autogym import exploit_gate as eg  # noqa: E402
from pokerbot.autogym import pargate6 as pg  # noqa: E402
from pokerbot.engine.table import Table  # noqa: E402

N_DECKS = 6


def test_aa_tag_exakt_null():
    decks = pg.gen_decks6(N_DECKS, seed=42)
    a = pg.spiele_block(pg.held_fabrik("tag"), decks, 0)["chips"]
    b = pg.spiele_block(pg.held_fabrik("tag"), decks, 0)["chips"]
    assert len(a) == N_DECKS and a == b, f"A/A nicht exakt 0: {[x - y for x, y in zip(a, b)]}"


def test_aa_hu_exploit_held_exakt_null():
    decks = pg.gen_decks6(N_DECKS, seed=5, n_seats=2)
    a = pg.spiele_block(eg.held_fabrik("exploit_on"), decks, 0, n_seats=2, liga=("station",))
    b = pg.spiele_block(eg.held_fabrik("exploit_on"), decks, 0, n_seats=2, liga=("station",))
    assert a["chips"] == b["chips"] and a["illegal_fallbacks"] == 0
    assert a["fingerprint"]["exploit"] is True and a["fingerprint"]["prince"] is False


def test_chip_erhaltung_und_deck_treue():
    holes, board = pg.gen_decks6(1, seed=1)[0]
    t = Table([f"S{i}" for i in range(6)], human_seat=-1, seed=1)
    pg._setze_deck(t, holes, board)
    assert t.button == 0 and [s.hole for s in t.seats] == holes
    bots = {s: SixMaxBot(s, PROFILES["station"], seed=s) for s in range(6)}   # Stations -> Showdown wahrscheinlich
    pg._spiele_hand(t, bots, 0, bots[0], "x")
    assert sum(s.stack for s in t.seats) == 6 * pg.START_STACK, "Chip-Erhaltung verletzt"
    assert t.hand_over and all(c in board for c in t.board), "Board weicht vom festen Deck ab"


def test_villain_profile_rotation():
    """Jeder Sitz traegt ueber die 6 Rotationen jedes Liga-Profil genau einmal (+ einmal den Helden)."""
    for s in range(6):
        profile = sorted(pg.LIGA[(s - rot - 1) % 6] for rot in range(6) if rot != s)
        assert profile == sorted(pg.LIGA), profile


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"  ok {name}")
    print("test_pargate6: alle gruen")
