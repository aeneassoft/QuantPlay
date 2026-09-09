"""HybridHero (pokerbot/arena/hybrid.py): mit/ohne Stack legale Aktionen am 6-max-Tisch; der Stack-Wrapper
greift im HU-Pot (die AUSLESE-Kette liegt um Prince.decide, kanal 'gym'). Setzt die Prince-Env VOR dem
bot-Import (Import-Zeit-Flags). Run: python -m tests.test_hybrid"""
from __future__ import annotations

import os

os.environ.setdefault("POKERB_PRINCE", "1")
for _k, _v in (("POKERB_TURN_DEFENSE", "0.07"), ("POKERB_SLOWPLAY", "0.25"), ("POKERB_RAISE_NARROW", "1.0")):
    os.environ.setdefault(_k, _v)

from pokerbot.arena.hybrid import HybridHero  # noqa: E402
from pokerbot.autogym import pargate6 as pg  # noqa: E402
from pokerbot.strategy.auslese import FINAL_STACK  # noqa: E402

N_DECKS = 4


def _spielt_legal(held) -> dict:
    decks = pg.gen_decks6(N_DECKS, seed=42)
    res = pg.spiele_block(held, decks, 0)
    assert res["illegal_fallbacks"] == 0, f"illegale Aktionen: {res['illegal_fallbacks']}"
    assert res["kern_fallbacks"] == 0, f"Prince fiel {res['kern_fallbacks']}x auf den Kern"
    assert res["prince_decisions"] > 0, "kein einziger HU-Pot in 24 Haenden? Takeover greift nicht"
    return res


def test_ohne_stack_legal():
    held = HybridHero(0, stack=None)
    assert held.prince.stack is None
    _spielt_legal(held)


def test_mit_stack_legal_und_wrapper_greift():
    held = HybridHero(0, stack=FINAL_STACK, kanal="gym")
    assert held.prince.stack == FINAL_STACK
    # Der Prince-Anteil entscheidet durch die AUSLESE-Kette (auslese.wickle_decide), nicht durch den nackten decide.
    assert held.prince._decide is not held.prince.bot.decide
    assert "wickle_decide" in held.prince._decide.__qualname__
    res = _spielt_legal(held)
    # Direkter HU-Spot durch die Kette: dict-erhaltend (action/amount/rationale bleiben die PokerBot-Form).
    dec = held.prince.decide(_hu_record(held))
    assert dec["source"] == "prince_hu" and dec["action"] in ("fold", "check", "call", "bet", "raise")
    assert res["prince_decisions"] > 0


def _hu_record(held) -> dict:
    """Ein HU-Pot aus einem gespielten Deck: der Tisch nach dem Preflop-Kollaps (5 Folds) am Flop."""
    from pokerbot.engine.table import Table
    holes, board = pg.gen_decks6(1, seed=99)[0]
    t = Table([f"S{i}" for i in range(6)], human_seat=-1, seed=1)
    pg._setze_deck(t, holes, board)
    for _ in range(3):                      # UTG, MP, HJ folden -> CO (Sitz 4) vs Blinds
        t.act("fold")
    t.act("raise", 250)                      # CO oeffnet
    t.act("fold")                            # SB
    t.act("call")                            # BB (Sitz 1) callt -> HU am Flop, BB zuerst am Zug
    held.setze_sitz(t.to_act)
    held.bind_table(t)
    return held._record()


def test_deterministisch_mit_stack():
    decks = pg.gen_decks6(3, seed=7)
    a = pg.spiele_block(HybridHero(0, stack=FINAL_STACK), decks, 0)["chips"]
    b = pg.spiele_block(HybridHero(0, stack=FINAL_STACK), decks, 0)["chips"]
    assert a == b, f"A/A nicht exakt: {a} vs {b}"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"  ok {name}")
    print("test_hybrid: alle gruen")
