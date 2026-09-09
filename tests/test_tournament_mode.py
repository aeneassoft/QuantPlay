"""Turnier-Modus des Trainers (docs/TURNIER_MODUS.md): MTT-Direktor + Server-Smoke.

  python -m tests.test_tournament_mode
"""
from __future__ import annotations

import time

from pokerbot.arena.mtt import (FIELD_MIX, MTT, N_PLAYERS, PAYOUT_PCT_TOP9, SEATS_PER_TABLE,
                                START_STACK, field_counts, make_league_bot)

SIDE_BUDGET_MS = 300          # Laufzeit-Ziel: 5 Nebentische je Hero-Hand zusammen (Product-Owner)
SMOKE_ACTIONS = 30


def _hero_bot(seed: int = 99):
    return make_league_bot("tag", seed)


def test_field_and_payouts():
    counts = field_counts(N_PLAYERS - 1)
    assert sum(counts.values()) == N_PLAYERS - 1 and set(counts) == set(FIELD_MIX)
    assert abs(sum(PAYOUT_PCT_TOP9) - 1.0) < 1e-9
    m = MTT(seed=1)
    pays = m.payouts()
    assert len(pays) == 9 and abs(sum(pays) - m.prize_pool()) < 1e-9, pays
    assert pays == sorted(pays, reverse=True)
    assert len(m.tables) == N_PLAYERS // SEATS_PER_TABLE and all(len(h.names) == SEATS_PER_TABLE for h in m.tables)
    profs = [e.profile for e in m.entrants.values()]
    assert profs.count("hero") == 1 and profs.count("station") == counts["station"]


def test_levels():
    m = MTT(seed=2, hands_per_level=4)
    assert (m.level().sb, m.level().bb, m.level().ante) == (25, 50, 0) and m.hands_to_level() == 4
    m.round_no = 4
    assert m.level_index() == 1 and m.level().bb == 100
    m.round_no = 8
    assert m.level().ante == 15, "Ante ab Level 3"
    m.round_no = 4 * 12
    assert m.level().bb > 1600, "nach Level 10 waechst der BB weiter (Terminierung)"


def test_full_mtt_bots_only_invariants():
    """60 Spieler bis zum Sieger; Chip-Erhaltung + Balance-Invarianten nach JEDER Runde (audit=True)."""
    m = MTT(seed=7, hero_bot=_hero_bot())
    t0 = time.perf_counter()
    r = m.run_bots_only(audit=True)
    sec = time.perf_counter() - t0
    assert m.over() and r["winner"] is not None
    assert m.total_chips() == N_PLAYERS * START_STACK
    places = sorted(p for p in r["places"].values() if p)
    assert places == list(range(1, N_PLAYERS + 1)), "jeder Platz genau einmal"
    assert m.entrants[r["winner"]].place == 1
    print(f"  MTT bots-only: Sieger {r['winner']}, {r['rounds']} Runden, {sec:.1f}s")


def test_determinism():
    a = MTT(seed=11, hero_bot=_hero_bot(), hands_per_level=6).run_bots_only()
    b = MTT(seed=11, hero_bot=_hero_bot(), hands_per_level=6).run_bots_only()
    assert a == b, "gleicher Seed -> gleiches Turnier"
    c = MTT(seed=12, hero_bot=_hero_bot(), hands_per_level=6).run_bots_only()
    assert c != a, "anderer Seed -> anderes Turnier"


def test_rebalance_rules():
    """Ausgleich erst ab Differenz >= 2; kein Tisch < 2 ausser dem Final Table; Hero-Umzug wird gemeldet."""
    m = MTT(seed=3)
    hero = m.hero_host()
    other = next(h for h in m.tables if h is not hero)
    for nm in other.names[:3]:                 # drei Busts am Nachbartisch: 7 vs 10 -> Balance auf 8/9
        m.entrants[nm].stack = 0
    m._apply_busts([(nm, START_STACK) for nm in other.names[:3]])
    m._rebalance()
    sizes = sorted(len(h.names) for h in m.tables)
    assert max(sizes) - min(sizes) <= 1 and sum(sizes) == 57, sizes
    # Kollaps: auf 11 Spieler schrumpfen -> 2 Tische 6/5; auf 10 -> Final Table
    for nm in list(m.alive):
        if nm != m.hero_name and len(m.alive) > 11:
            m.entrants[nm].stack = 0
            m._apply_busts([(nm, START_STACK)])
    m._rebalance()
    assert sorted(len(h.names) for h in m.tables) == [5, 6]
    m.table_change = None
    nm = next(n for n in m.alive if n != m.hero_name)
    m.entrants[nm].stack = 0
    m._apply_busts([(nm, START_STACK)])
    m._rebalance()
    assert m.is_final_table() and len(m.tables[0].names) == 10 and m.final_table_reached
    assert m.hero_name in m.tables[0].names


def test_side_table_runtime():
    m = MTT(seed=5)
    ms = []
    for _ in range(20):
        m.advance_round([])
        ms.append(m.last_side_ms)
    mean = sum(ms) / len(ms)
    print(f"  Nebentische: mean {mean:.0f} ms, max {max(ms):.0f} ms je Hero-Hand (5 Tische)")
    assert mean < SIDE_BUDGET_MS, f"Nebentische zu langsam: {mean:.0f} ms (Fallback side_tables_every=2)"
    assert m.total_chips() == N_PLAYERS * START_STACK


def test_server_smoke():
    """new_session tournament -> view.tournament -> 30 Hero-Aktionen (Fold/Call) -> Berater-Urteil vorhanden."""
    from fastapi.testclient import TestClient

    from pokerbot.web import six_server as S
    c = TestClient(S.app)
    v = c.post("/api/new_session", json={"mode": "tournament", "seed": 42, "step": True}).json()
    assert "error" not in v and len(v["seats"]) == 10
    t = v["tournament"]
    for k in ("level", "players_left", "rank", "hero_stack_bb", "avg_stack_bb", "next_payout",
              "hands_to_level", "advisor", "finished", "avatars"):
        assert k in t, k
    assert t["players_left"] == N_PLAYERS and t["level"] == 1
    acts = 0
    while acts < SMOKE_ACTIONS:
        if v["hand_over"]:
            v = c.post("/api/hand", json={"step": True}).json()
            if v["tournament"]["finished"]:
                break
            continue
        if v["to_act"] == v["human_seat"]:
            L = v["legal"]
            a = "call" if L.get("can_call") else ("check" if L.get("can_check") else "fold")
            v = c.post("/api/action", json={"action": a, "step": True}).json()
            assert "error" not in v, v.get("error")
            acts += 1
            last = v["tournament"]["advisor"]["last"]
            assert last and last["text"] and (last["text"] == "GTO ✓" or last["text"].startswith("Abweichung"))
        else:
            v = c.post("/api/step", json={}).json()
    st = v["tournament"]["advisor"]["stats"]
    assert st["decisions"] == acts and st["gto_quote"] is not None
    assert S.SESSION.mtt.total_chips() == N_PLAYERS * START_STACK   # Entrant-Stacks nur zwischen Haenden
    print(f"  Server-Smoke: {acts} Aktionen, GTO-Quote {st['gto_quote']}, "
          f"Nebentische {v['tournament']['side_ms']} ms, Spieler {v['tournament']['players_left']}")


def run():
    test_field_and_payouts()
    test_levels()
    test_rebalance_rules()
    test_side_table_runtime()
    test_determinism()
    test_full_mtt_bots_only_invariants()
    test_server_smoke()
    print("TURNIER-MODUS: alle 7 Tests bestanden")


if __name__ == "__main__":
    run()
