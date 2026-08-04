"""MTT-Regressionsnetz — der 600-Spieler-Simulator (research/mtt_sim.py) + der Ante-Engine-Fix.

Konserviert die im Bau gefangenen Tatorte:
  * Ante als Street-Einsatz: BB bekam to_call<0 -> can_check False -> Fold im Limped-Pot;
    Caller zahlten bb-ante; eine Ante je betroffenem Tisch verwaiste bei der Auszahlung.
  * __init__-Zerschneidung (checkpoints nach einem Methodendef = unerreichbar).

  python -m tests.test_mtt
"""
from __future__ import annotations

from pokerbot.engine.table import Table
from research import mtt_sim


def test_payout_ladder() -> None:
    p = mtt_sim.PAYOUTS
    assert len(p) == 90
    assert abs(sum(p) - 600_000.0) < 0.01
    assert all(p[i] >= p[i + 1] for i in range(len(p) - 1))
    assert 1.8 * mtt_sim.BUYIN < p[-1] < 3 * mtt_sim.BUYIN          # Min-Cash ~2x Buy-in
    assert 0.14 < p[0] / 600_000.0 < 0.18                           # 1. Platz in PS-Form


def test_ante_is_dead_money() -> None:
    """Der Engine-Fix: Antes duerfen die Street-Abrechnung nicht beruehren."""
    t = Table([f"p{i}" for i in range(6)], starting_stack=55_000, sb=125, bb=250,
              seed=7, stacks=[55_000] * 6, ante=32, rebuy=False)
    t.button = -1
    t.start_hand()
    total_before = sum(s.stack + s.committed_total for s in t.seats)
    bb_seat = (t.button + 2) % 6
    # UTG callt, alle anderen folden -> der BB MUSS checken koennen (to_call exakt 0)
    order = []
    while not t.hand_over and t.to_act is not None and t.street == "preflop":
        la = t.legal_actions()
        if t.to_act == bb_seat:
            assert la["can_check"], f"BB kann nicht checken: to_call={la['to_call']}"
            assert la["to_call"] == 0
            t.act("check")
            break
        t.act("call" if not order else "fold")
        order.append(1)
    caller = t.seats[(t.button + 3) % 6]
    assert caller.committed_total == 32 + 250, caller.committed_total   # voller Call, Ante extra
    guard = 0
    while not t.hand_over and t.to_act is not None and guard < 50:
        guard += 1
        t.act("check" if t.legal_actions().get("can_check") else "fold")
    assert sum(s.stack for s in t.seats) == total_before                # keine verwaiste Ante


def test_full_tournament_audit() -> None:
    """Ein komplettes 600er-Turnier: Chip-Erhaltung je Runde + lueckenlose Platzvergabe."""
    m = mtt_sim.MTT(90_001, "chipEV")
    m.stop_on_hero_bust = False
    m.audit = True
    r = m.run()
    places = sorted(m.places.values())
    assert places in (list(range(2, 601)), list(range(1, 601)))
    assert 1 <= r["place"] <= 600
    assert r["rounds"] < mtt_sim.MAX_ROUNDS, "Turnier lief in den Guard"


def test_determinism_and_pairing() -> None:
    a = mtt_sim.run_one(91_001, "chipEV")
    assert a == mtt_sim.run_one(91_001, "chipEV")
    b = mtt_sim.run_one(91_001, "druck")
    assert b == mtt_sim.run_one(91_001, "druck")
    c = mtt_sim.run_one(91_001, "chipEV", "bots_local")
    assert c == mtt_sim.run_one(91_001, "chipEV", "bots_local")


def test_engine_fuzz_short_stacks() -> None:
    """Turnier-Formen-Fuzz: Mikro-Stacks, Riesen-Antes, HU — Chip-Erhaltung nach jeder Hand.
    Fand die verwaiste Side-Pot-Schicht (Fold ueber All-in-Cap -> eligible leer -> Chips weg)."""
    import random
    rng = random.Random(1234)
    for trial in range(4000):
        n = rng.randint(2, 6)
        bb = rng.choice([200, 2000, 20000, 100000])
        ante = int(round(bb * 0.13)) if rng.random() < 0.7 else 0
        stacks = [rng.choice([1, ante or 1, bb // 2, bb, 3 * bb, 10 * bb]) for _ in range(n)]
        if sum(1 for s in stacks if s > 0) < 2:
            continue
        t = Table([f"p{i}" for i in range(n)], starting_stack=bb * 100, sb=bb // 2, bb=bb,
                  seed=trial, stacks=stacks, ante=ante, rebuy=False)
        t.button = rng.randrange(n) - 1
        total = sum(stacks)
        t.start_hand()
        g = 0
        while not t.hand_over and t.to_act is not None and g < 60:
            g += 1
            la = t.legal_actions()
            opts = []
            if la.get("can_check"):
                opts.append(("check", None))
            if la.get("can_call"):
                opts.append(("call", None))
            if la.get("can_fold"):
                opts.append(("fold", None))
            if la.get("can_raise") and la.get("raise_min") is not None                and la["raise_min"] <= la["raise_max"]:
                opts.append(("raise", rng.choice([la["raise_min"], la["raise_max"]])))
            a, amt = rng.choice(opts) if opts else ("fold", None)
            t.act(a, amt)
        after = sum(s.stack for s in t.seats)
        assert after == total, f"Fuzz trial {trial}: {after} != {total} (stacks {stacks})"
        assert t.hand_over, f"Fuzz trial {trial}: Hand haengt (g={g})"


def main() -> None:
    test_payout_ladder()
    test_ante_is_dead_money()
    test_engine_fuzz_short_stacks()
    test_full_tournament_audit()
    test_determinism_and_pairing()
    print("MTT: alle Tests bestanden")


if __name__ == "__main__":
    main()
