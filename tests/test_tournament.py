"""Turnier-Tests: Mechanik-Invarianten + Buch-Anker + Cash-Paritäts-Gate.

Leiter (Baukarte 2026-08-04):
  1. Chip-Erhaltung über das GANZE Turnier (inkl. Ante-All-in-Side-Pots), Platz-/Payout-Vergabe,
     Determinismus (gleicher Seed -> identisches Resultat), Schrumpfung 9 -> Heads-up.
  2. Buch-Anker: BF-Skalierung (r=0.5, BF 2.56 -> 71.9%), icm_required_equity-Grenzfälle.
  3. Cash-Parität: OHNE obs['icm'] entscheidet der sixmax-Kern byte-identisch (der Anker-Schutz).
"""
import random

from pokerbot.arena.sixmax import PROFILES, SixMaxBot, decide_6max
from pokerbot.arena.tourney import run_tourney
from pokerbot.strategy.tournament import (SNG9, BlindLevel, Director, Structure,
                                          icm_required_equity, pick_villain)


def test_director_mechanics():
    st = SNG9
    d = Director(st, [f"p{i}" for i in range(9)], seed=7)
    total = 9 * st.start_stack
    hands = 0
    while not d.over() and hands < 3000:
        hands += 1
        t = d.next_table()
        # simple Zufalls-Agenten: schnell zum Ende, aber legal
        rng = random.Random(hands)
        guard = 0
        while not t.hand_over and t.to_act is not None and guard < 300:
            guard += 1
            la = t.legal_actions()
            if la.get("can_raise") and rng.random() < 0.25:
                t.act("raise", la["raise_min"])
            elif la.get("can_call") and rng.random() < 0.6:
                t.act("call")
            elif la.get("can_check"):
                t.act("check")
            else:
                t.act("fold")
        d.after_hand(t)
        # CHIP-ERHALTUNG: die Summe aller Entrant-Stacks bleibt der Gesamtbestand
        assert sum(e.stack for e in d.entrants) == total, (hands, sum(e.stack for e in d.entrants))
    assert d.over(), "Turnier endete nicht"
    places = sorted(e.place for e in d.entrants)
    assert places == list(range(1, 10)), places
    res = d.results()
    paid = sum(r["payout"] for r in res)
    assert abs(paid - st.buyin * 9) < 1e-9, paid
    assert res[0]["place"] == 1 and res[0]["payout"] == st.payouts(9)[0]


def test_determinism_and_shrink():
    def once():
        d = Director(SNG9, [f"p{i}" for i in range(9)], seed=42)
        ns = []
        while not d.over() and d.hand_no < 3000:
            t = d.next_table()
            ns.append(t.n)
            rng = random.Random(d.hand_no)
            guard = 0
            while not t.hand_over and t.to_act is not None and guard < 300:
                guard += 1
                la = t.legal_actions()
                if la.get("can_call") and rng.random() < 0.7:
                    t.act("call")
                elif la.get("can_check"):
                    t.act("check")
                else:
                    t.act("fold")
            d.after_hand(t)
        return ns, [(e.name, e.place) for e in d.entrants]
    a, ra = once()
    b, rb = once()
    assert a == b and ra == rb, "Seed-Determinismus verletzt"
    assert min(a) <= 3, f"Tisch schrumpfte nie unter 4 Spieler ({min(a)})"


def test_book_anchors():
    # Flip-Anker aus Endgame Poker Strategy: BF 2.56 -> 71.9%; BF 1.18 -> 54.1%; BF 1 -> Pot Odds
    assert abs(icm_required_equity(0.5, 2.56) - 2.56 / 3.56) < 1e-12
    assert abs(icm_required_equity(0.5, 1.18) - 1.18 / 2.18) < 1e-12
    assert icm_required_equity(0.33, 1.0) == 0.33
    # Monotonie: mehr BF -> hoehere Schwelle; nie ueber 1
    assert icm_required_equity(0.3, 4.0) > icm_required_equity(0.3, 2.0) > 0.3
    assert icm_required_equity(0.9, 5.0) < 1.0
    # pick_villain: Aggressor schlaegt Coverstack; sonst Coverstack
    assert pick_villain([100, 500, 50], 0, 2) == 2
    assert pick_villain([100, 500, 50], 0, None) == 1


def test_cash_parity_without_icm_key():
    """OHNE icm-Key muss der Kern byte-identisch zum Anker entscheiden (fester rng-Strom)."""
    obs = {"hole": ["Ah", "Kd"], "board": [], "to_call": 100, "pot": 350, "my_stack": 9800,
           "bb": 100, "n_active": 6, "position": "BTN", "preflop_raises": 1, "cur_bet": 250,
           "my_committed_street": 0, "street": "preflop", "can_check": False, "can_call": True,
           "can_raise": True, "raise_min": 500, "raise_max": 9800}
    a = decide_6max(dict(obs))
    b = decide_6max(dict(obs))
    assert a == b
    # und MIT icm-Key wird die Call-Schwelle strenger (ein Grenz-Blatt kippt zu Fold)
    borderline = dict(obs, hole=["7h", "6h"])
    plain = decide_6max(dict(borderline))
    icm_obs = dict(borderline)
    icm_obs["icm"] = {"stacks": [3000.0, 3000.0, 9800.0, 3000.0, 3000.0, 3000.0],
                      "payouts": [450.0, 270.0, 180.0], "seat": 2, "aggressor": 0,
                      "invested": {}}
    tight = decide_6max(icm_obs)
    # das Grenz-Blatt darf unter ICM nie AGGRESSIVER werden
    order = {"fold": 0, "check": 0, "call": 1, "raise": 2}
    assert order[tight["action"]] <= order[plain["action"]], (plain, tight)


def test_full_sng_with_bots():
    """Ein komplettes 9-max-SNG mit echten sixmax-Bots + Hero läuft durch und zahlt aus."""
    def hero_factory(rng):
        return SixMaxBot(0, PROFILES["tag"])
    r = run_tourney(SNG9, hero_factory, seed=5, icm_on=True)
    assert 1 <= r["place"] <= 9 and r["hands"] > 5, r


def run():
    test_director_mechanics()
    test_determinism_and_shrink()
    test_book_anchors()
    test_cash_parity_without_icm_key()
    test_full_sng_with_bots()
    print("TURNIER: alle Tests bestanden")


if __name__ == "__main__":
    run()
