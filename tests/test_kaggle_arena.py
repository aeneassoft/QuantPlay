"""Kaggle-Arena-Bruecke: Parser, Legalitaet, A/A-Nulltest.
Run: python -m tests.test_kaggle_arena   (braucht open_spiel + kaggle-environments)"""
import warnings

warnings.filterwarnings("ignore")

from pokerbot.benchmark import kaggle_arena as KA  # noqa: E402

ROH = ("Player: 1\n||Current Street: 1\n||Next Player to act: 1\n||Pot(s): [] \n||Bets: [0, 0]\n"
       "||Board Cards: [[8d], [Qs], [Td]]\n||Player's Private Hole Cards: [6c, 7s]\n"
       "||Per-player Hole Cards (public view): [[??, ??], [??, ??]]\n"
       "||Per-player Starting Stacks: (200, 200)\n||Per-player Current Stacks: [194, 194]")


def test_parser():
    b = KA.parse_beobachtung(ROH)
    assert b["board"] == ["8d", "Qs", "Td"], b["board"]     # der Wrapper klammert je Strasse
    assert b["hole"] == ["6c", "7s"], b["hole"]
    assert b["bets"] == [0, 0] and b["stacks"] == [194, 194]
    assert b["pot_gesamt"] == 12, "Pot = Startstacks minus aktuelle Stacks"
    print("  Parser: Board/Hole/Pot korrekt aus der observation_string")


def test_spielkonfiguration():
    """Die Kaggle-Konfiguration ist 100 bb tief — nicht 200, wie aelteres ACPC-Material nahelegt."""
    from kaggle_environments.envs.open_spiel_env.open_spiel_env import (
        DEFAULT_REPEATED_POKERKIT_GAME_STRING as S,
    )
    assert "blinds=1 2" in S and "stack_sizes=200 200" in S and "reset_stacks=True" in S, S
    assert "max_num_hands=100" in S, S
    g = KA.spiel()
    assert g.num_players() == 2
    print("  Konfiguration: HU, Blinds 1/2, Stacks 200 Einheiten = 100 bb, Reset je Hand")


def test_legalitaet():
    """spiel_aktion darf NIE eine illegale Aktion liefern — auch nicht bei unmoeglichem Wunsch."""
    import random

    g = KA.spiel()
    s = g.new_initial_state()
    rng = random.Random(4)
    while s.is_chance_node():
        s.apply_action(rng.choice([a for a, _ in s.chance_outcomes()]))
    p = s.current_player()
    legale = set(s.legal_actions(p))
    for wunsch in ({"action": "fold", "amount": None}, {"action": "check", "amount": None},
                   {"action": "call", "amount": None}, {"action": "allin", "amount": None},
                   {"action": "raise", "amount": 10 ** 9}, {"action": "raise", "amount": 1}):
        a = KA.spiel_aktion(wunsch, s, p)
        assert a in legale, f"{wunsch} -> {a} nicht legal"
    print(f"  Legalitaet: 6 Wuensche, alle auf legale Aktionen abgebildet ({len(legale)} legale)")


def test_aa_null():
    """MESS-DOKTRIN: derselbe Agent auf beiden Seiten muss EXAKT 0 ergeben."""
    st = KA.duell(KA.PrinceAgent, KA.PrinceAgent, decks=4, seed0=90000)
    assert st["bb100"] == 0.0 and st["nonzero"] == 0, st
    print(f"  A/A: exakt {st['bb100']} bb/100 ueber {st['n_decks']} gepaarte Decks")


def run():
    test_parser()
    test_spielkonfiguration()
    test_legalitaet()
    test_aa_null()
    print("KAGGLE-ARENA: alle 4 Tests bestanden")


if __name__ == "__main__":
    run()
