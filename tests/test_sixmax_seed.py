"""SixMaxBot-Seeding (pargate6-Voraussetzung): gleicher Seed -> identische Entscheidungsfolge; der Default
(seed=None) bleibt das bisherige nicht-deterministische Mixing. Run: python -m tests.test_sixmax_seed"""
from __future__ import annotations

import random

from pokerbot.arena import sixmax
from pokerbot.arena.sixmax import PROFILES, SixMaxBot, seed_modul_rng
from pokerbot.engine.table import Table

N_HAENDE = 40


def _folge(seed: int | None, deck_seed: int = 3) -> list:
    """Entscheidungsfolge eines geseedeten 'lag' auf Sitz 0 gegen geseedete tag-Villains, feste Decks."""
    bots = {s: SixMaxBot(s, PROFILES["lag" if s == 0 else "tag"], seed=(seed + s) if seed is not None else None)
            for s in range(6)}
    folge = []
    for h in range(N_HAENDE):
        t = Table([f"S{i}" for i in range(6)], seed=deck_seed * 1000 + h, human_seat=-1)
        t.start_hand()
        for b in bots.values():
            b.new_hand(list(range(6)))
        for _ in range(400):
            if t.hand_over:
                break
            i = t.to_act
            obs = t.obs_for(i)
            dec = bots[i].decide(obs)
            folge.append((h, i, dec["action"], dec.get("amount")))
            t.act(dec["action"], dec.get("amount"))
            for b in bots.values():
                b.observe(i, obs["street"], "raise" if dec["action"] == "allin" else dec["action"],
                          obs["to_call"], obs["preflop_raises"])
    return folge


def test_gleicher_seed_identisch():
    assert _folge(11) == _folge(11), "gleicher Seed muss dieselbe Entscheidungsfolge liefern"


def test_anderer_seed_weicht_ab():
    assert _folge(11) != _folge(12), "verschiedene Seeds sollten (bei 40 Haenden) irgendwo abweichen"


def test_default_bleibt_zufaellig():
    b = SixMaxBot(0, PROFILES["tag"])
    assert isinstance(b.rng, random.Random)
    zieh = [SixMaxBot(0, PROFILES["tag"]).rng.random() for _ in range(3)]
    assert len(set(zieh)) == 3, "Default seed=None darf keine feste Folge sein"


def test_modul_rng_seedbar():
    seed_modul_rng(5)
    a = sixmax._RNG.random()
    seed_modul_rng(5)
    assert sixmax._RNG.random() == a


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"  ok {name}")
    print("test_sixmax_seed: alle gruen")
