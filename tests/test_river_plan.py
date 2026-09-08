"""Tests K2 — pokerbot/autogym/river_plan.py (v10 Build-Karte K2 + E1/E4/E5/E7 + Review-Fixes 2026-09-07).

Fixtures = echte HeadsUpGame-States (20000/50/100, Hand 1 -> Button 0 = IP; Sitz 1 = OOP handelt postflop
zuerst; game.py:68-72, 227-228). Der Basis-Mock ZAEHLT seine Aufrufe (E1: in Plan-Pots nie gerufen).
Seeds (Sonde 2026-09-07, K1-Range am River-Beginn): SEED_HERO_IM_SUPPORT=4 -> Heros echte Hand liegt in BEIDEN
Rollen in der oeffentlichen Hero-Range; SEED_HERO_OOP_AUSSERHALB=3 -> Sitz 1 (OOP) haelt Td4s AUSSERHALB.

  python -m tests.test_river_plan                       # alle Tests + kleine Latenz-Messung (10 Aufrufe)
  python -m tests.test_river_plan --latenz 500 --ausgabe data/runs/v10/latenz_k2.json [--deadline 7.5]
                                                        # Karten-Abnahme: >=500 geschichtete Aufrufe, LEERE GPU!
"""
from __future__ import annotations

import copy
import json
from collections import Counter
import math
import os
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import replace

from pokerbot.engine.game import HeadsUpGame
from pokerbot.strategy.contracts import ActionKey, EntscheidungsTrace, PolicyTable
from pokerbot.autogym import river_plan as rp

STACK, SB, BB = 20000, 50, 100
SEED_HERO_IM_SUPPORT = 4          # Hero-Hand in der K1-Range: OOP 3dKd, IP 5c6c (Sonde)
SEED_HERO_OOP_AUSSERHALB = 3      # Hero Sitz 1 haelt Td4s, Gewicht 0 in der K1-Range (559 Combos)
SCHNELL_ITERS = 20                # Mechanik-Tests brauchen keine 150 Iterationen (Solve-Zeit ~ linear in iters)


# ---------------------------------------------------------------- Fixtures
class BasisMock:
    """Fabrik-Vertrag make(seat) -> d(st); zaehlt Aufrufe, antwortet immer legal-passiv."""

    def __init__(self):
        self.aufrufe = 0

    def __call__(self, seat):
        def d(st):
            self.aufrufe += 1
            to_call = st["current_bet"] - st["players"][st["to_act"]]["committed_street"]
            return ("call", None) if to_call > 0 else ("check", None)
        return d


def spiel_bis_river(flop_bet: int = 700, seed: int = SEED_HERO_IM_SUPPORT, turn_bet: int | None = None) -> HeadsUpGame:
    """SRP zum River: BTN(0) raise 300 / call; Flop bet/call; Turn check/check (oder bet/call).
    pot_river = 600 + 2*flop_bet (+ 2*turn_bet)."""
    g = HeadsUpGame(starting_stack=STACK, sb=SB, bb=BB, seed=seed)
    g.start_hand()
    assert g.button == 0
    g.act("raise", 300); g.act("call")
    g.act("bet", flop_bet); g.act("call")
    if turn_bet:
        g.act("bet", turn_bet); g.act("call")
    else:
        g.act("check"); g.act("check")
    assert g.street == "river" and g.to_act == 1
    return g


def fabrik(basis: BasisMock, **kw) -> rp.RiverPlanFabrik:
    return rp.river_plan_guard(basis, **kw)


def _pruefe_legal_und_spiele(g: HeadsUpGame, aktion):
    a, amt = aktion
    g.act(a, amt)        # wirft bei Illegalitaet


def _plan_und_trace(fab, seat):
    return fab.letzter_plan(seat), fab.letzter_trace(seat)


_PLAN_CACHE: dict[str, rp.GeloesterPlan] = {}


def plan_oop_facing_bet(seed: int = SEED_HERO_IM_SUPPORT, iters: int = SCHNELL_ITERS) -> tuple[dict, rp.GeloesterPlan]:
    """Einmal je Prozess geloester Plan (Hero Sitz 1, check -> Villain bet 0,75) fuer die Mock-basierten Tests."""
    g = spiel_bis_river(seed=seed); g.act("check"); g.act("bet", 1500)
    st = g.state()
    key = f"{seed}/{iters}"
    if key not in _PLAN_CACHE:
        _PLAN_CACHE[key] = rp.loese_plan(st, hero_seat=1, hand_adresse="fixture", iters=iters)
    return st, _PLAN_CACHE[key]


# ---------------------------------------------------------------- Aktivierung
def test_aktivierung_oeffentlich_und_hole_unabhaengig():
    g = spiel_bis_river(flop_bet=450)                # pot_river == 1500 == Schwelle (inklusiv)
    st = g.state()
    aktiv, pot_river = rp.ist_aktiviert(st)
    assert (aktiv, pot_river) == (True, 1500)
    st2 = json.loads(json.dumps(st))
    st2["players"][1]["hole"] = ["2c", "3d"] if "2c" not in st["board"] and "3d" not in st["board"] else ["2d", "3c"]
    assert rp.ist_aktiviert(st2) == (True, 1500), "Aktivierung darf nicht von Hole-Karten abhaengen"
    g_klein = spiel_bis_river(flop_bet=400)          # 1400 < 1500
    assert rp.ist_aktiviert(g_klein.state()) == (False, 1400)
    assert rp.ist_aktiviert({"street": "turn"}) == (False, 0)


def test_pot_river_formel_gleich_improver_formel():
    """pot − Σ committed_street == pot − Σ River-Einsaetze (improver._river_spot_und_frage, V10_FAKTEN A5)."""
    g = spiel_bis_river()
    g.act("bet", 700); g.act("raise", 1890)
    st = g.state()
    river_einsaetze = 700 + 1890
    assert rp.pot_river_aus_state(st) == st["pot"] - river_einsaetze == 2000


def test_unter_schwelle_und_andere_strassen_rufen_basis_unveraendert():
    basis = BasisMock()
    d = fabrik(basis)(1)
    g = spiel_bis_river(flop_bet=400)
    assert d(g.state()) == ("check", None) and basis.aufrufe == 1
    g2 = HeadsUpGame(starting_stack=STACK, sb=SB, bb=BB, seed=3); g2.start_hand()
    g2.act("raise", 300); g2.act("call")
    assert d(g2.state()) == ("check", None) and basis.aufrufe == 2
    assert fabrik(basis).statistik(1) == {} and d.zustand.zaehler["plan_pot_entscheidungen"] == 0


# ---------------------------------------------------------------- Fixtures der Karte (Check-Bet-Raise-Call, Jam, Off-Tree)
def test_fixture_hero_oop_checkt_villain_bettet_075():
    basis = BasisMock()
    fab = fabrik(basis)
    d = fab(1)
    g = spiel_bis_river()                            # pot_river 2000
    g.act("check")                                    # Hero (OOP) checkt (on-tree)
    g.act("bet", 1500)                                # Villain 0.75 * 2000 = Arm bet0.75
    st = g.state()
    aktion = d(st)
    assert basis.aufrufe == 0, "E1: base(st) darf im Plan-Pot nicht laufen"
    gp, tr = _plan_und_trace(fab, 1)
    assert tr["fallback_status"] == "keiner" and tr["pfad"] == [{"kind": "check", "chips": None},
                                                                 {"kind": "raise_to", "chips": 1500}]
    kinds = {k for k, _c, _p in tr["plan_verteilung"]}
    assert kinds == {"fold", "call", "raise_to"}
    assert abs(sum(p for _k, _c, p in tr["plan_verteilung"]) - 1.0) < 1e-6
    _pruefe_legal_und_spiele(g, aktion)
    assert gp.pot_river == 2000 and gp.eff == 19000 and gp.hero_rolle == rp.ROLLE_OOP
    assert "latenz_ms" not in tr and "zeiten_ms" not in tr, "Gym-Trace bleibt zeitfrei (deterministisch)"


def test_fixture_hero_ip_nach_villain_check():
    basis = BasisMock()
    fab = fabrik(basis)
    d = fab(0)
    g = spiel_bis_river()
    g.act("check")                                    # Villain (OOP) checkt
    st = g.state()
    assert st["to_act"] == 0
    aktion = d(st)
    assert basis.aufrufe == 0
    tr = fab.letzter_trace(0)
    assert tr["fallback_status"] == "keiner" and tr["pfad"] == [{"kind": "check", "chips": None}]
    # Arme: check + bet0.35 (700) + bet0.75 (1500) + bet1.5 (3000) + jam (19000)
    chips = sorted(c for k, c, _p in tr["plan_verteilung"] if k == "raise_to")
    assert chips == [700, 1500, 3000, 19000], chips
    _pruefe_legal_und_spiele(g, aktion)


def test_fixture_raise_linie_ohne_range_reset():
    basis = BasisMock()
    fab = fabrik(basis)
    d = fab(1)
    g = spiel_bis_river()
    g.act("bet", 700)                                 # Hero OOP bet0.35 = 700
    g.act("raise", 1890)                              # Villain raise2.7: Zusatz 2.7*700 = 1890 -> TO 1890
    st = g.state()
    assert st["legal"]["to_call"] == 1190
    aktion = d(st)
    assert basis.aufrufe == 0
    gp, tr = _plan_und_trace(fab, 1)
    assert tr["fallback_status"] == "keiner"
    assert tr["pfad"] == [{"kind": "raise_to", "chips": 700}, {"kind": "raise_to", "chips": 1890}]
    assert tr["root_hash"] == gp.root_hash and tr["pot_river"] == 2000
    # Hero-Re-Raise-Arm: Zusatz 2.7 * 1190 = 3213 -> TO-Level 700 + 3213 = 3913
    chips = sorted(c for k, c, _p in tr["plan_verteilung"] if k == "raise_to")
    assert chips == [3913, 19000], chips
    _pruefe_legal_und_spiele(g, aktion)
    # ZWEITE Entscheidung derselben Hand (wenn die Hand weiterlaeuft) nutzt denselben Plan (ein Solve)
    if not g.hand_over and g.to_act == 1:
        d(g.state())
        assert fab.letzter_plan(1) is gp


def test_fixture_villain_all_in_nur_passiver_zweig():
    basis = BasisMock()
    fab = fabrik(basis)
    d = fab(1)
    g = spiel_bis_river()
    g.act("check")
    g.act("allin")                                    # Villain jam: TO 19000 == eff -> Arm jam
    st = g.state()
    assert st["players"][0]["all_in"] and st["legal"]["can_raise"] is False
    aktion = d(st)
    assert basis.aufrufe == 0
    tr = fab.letzter_trace(1)
    assert tr["fallback_status"] == "keiner"
    assert tr["pfad"] == [{"kind": "check", "chips": None}, {"kind": "raise_to", "chips": 19000}]
    assert {k for k, _c, _p in tr["plan_verteilung"]} == {"fold", "call"}
    assert aktion in (("fold", None), ("call", None))
    _pruefe_legal_und_spiele(g, aktion)
    assert g.hand_over


def test_villain_jam_ueber_eff_wird_auf_jam_arm_geclippt():
    """Deckender Villain setzt mehr als eff: fuer Hero identisch mit Jam -> Arm jam, kein offtree."""
    from pokerbot.strategy.gpu_cfr import build_river_tree
    root = build_river_tree(2000.0, 19000.0, **rp.BAUM_KW)
    ip_node = root.kids[root.acts.index("check")]
    i = rp.arm_index_fuer(ip_node, ActionKey.raise_to(25000), eff=19000)
    assert i is not None and ip_node.acts[i].endswith("jam")       # Baum-Label 'betjam' (gpu_cfr.py:147)
    assert rp.arm_index_fuer(ip_node, ActionKey.raise_to(1000), eff=19000) is None      # 0.5 Pot: off-tree
    assert rp.arm_index_fuer(ip_node, ActionKey.raise_to(1501), eff=19000) is not None  # ±1 Chip Toleranz
    assert rp.arm_index_fuer(ip_node, ActionKey.raise_to(1502), eff=19000) is None


def test_fixture_offtree_size_faellt_auf_basis_mit_log():
    basis = BasisMock()
    fab = fabrik(basis)
    d = fab(1)
    g = spiel_bis_river()
    g.act("check")
    g.act("bet", 1000)                                # 0.5 Pot: kein Arm (0.35=700, 0.75=1500)
    aktion = d(g.state())
    assert aktion == ("call", None) and basis.aufrufe == 1, "Off-Tree -> genau EIN Basis-Aufruf"
    tr = fab.letzter_trace(1)
    assert tr["fallback_status"] == "offtree" and tr["offtree"] is True
    assert tr["plan_verteilung"] is None and tr["basis"] == {"kind": "call", "chips": None}
    assert any(f.startswith("nav:raise_to:1000") for f in tr["flags"])
    assert fab.letzter_plan(1) is not None, "der Plan wurde geloest (ein Solve), nur die Navigation scheiterte"
    assert fab.statistik(1) == {"plan_pot_entscheidungen": 1, "offtree": 1}


# ---------------------------------------------------------------- Verteilung / Σ=1 / Support
def test_summe_eins_je_knoten_und_policytable_vertrag():
    st, gp = plan_oop_facing_bet()
    assert len(gp.knoten) >= 5
    for pfad, node in gp.knoten.items():
        sig = gp.cfr.avg_sigma(node)[0]
        summen = sig.sum(dim=1)
        assert float((summen - 1.0).abs().max()) < 1e-4, f"Σ≠1 am Knoten {pfad}"
    tab = gp.tabelle(())
    assert isinstance(tab, PolicyTable) and tab.herkunft == "gpu_cfr_avg"
    assert len(tab.zeilen) == len([c for c, w in gp.hero_gewichte.items() if w > 0])
    assert len(tab.zeilen) + len(tab.undefiniert) == 1326
    # Verteilung ist OHNE RNG abrufbar (K3); Heros echte Hand liegt im Support (Fixture-Voraussetzung seed 4)
    hole = list(st["players"][1]["hole"])
    assert gp.im_support(hole)
    keys, probs, flags = gp.verteilung((ActionKey.check(), ActionKey.raise_to(1500)), hole)
    assert flags == [] and abs(sum(probs) - 1.0) < 1e-9 and len(keys) == len(probs)


def test_plan_ist_oeffentlich_gleicher_root_hash_bei_anderer_hero_hand():
    g = spiel_bis_river()
    g.act("check"); g.act("bet", 1500)
    st = g.state()
    gp1 = rp.loese_plan(st, hero_seat=1, hand_adresse="h", iters=SCHNELL_ITERS)
    st2 = json.loads(json.dumps(st))
    frei = [r + s for r in "23456789TJQKA" for s in "shdc" if r + s not in st["board"]
            and r + s not in st["players"][0]["hole"]]
    st2["players"][1]["hole"] = frei[:2]
    gp2 = rp.loese_plan(st2, hero_seat=1, hand_adresse="h", iters=SCHNELL_ITERS)
    assert gp1.root_hash == gp2.root_hash, "K2-Plan haengt nur von der oeffentlichen Historie ab"
    assert gp1.plan.ranges.hero_injiziert is False


def test_verteilung_liefert_keine_zeile_fuer_reach0_combos():
    """Vertrag contracts.PolicyTable: die Reach-0-Uniform von avg_sigma darf NIE als Strategie gelesen werden
    (V10_FAKTEN B10). verteilung() und tabelle().undefiniert muessen dieselbe Menge meinen — fuer ALLE 1326 Combos."""
    _st, gp = plan_oop_facing_bet()
    pfad = (ActionKey.check(), ActionKey.raise_to(1500))
    tab = gp.tabelle(pfad)
    n_undef = 0
    for k in range(1326):
        combo = list(rp._combo_str(k))
        keys, probs, flags = gp.verteilung(pfad, combo)
        if tuple(combo) in tab.undefiniert or rp.combo_kanonisch(*combo) in tab.undefiniert:
            n_undef += 1
            assert probs is None and flags == [rp.FLAG_HERO_AUSSERHALB_RANGE], combo
        else:
            assert probs is not None and flags == [] and abs(sum(probs) - 1.0) < 1e-9, combo
            assert tab.p(tuple(combo), keys[0]) is not None
    assert n_undef == len(tab.undefiniert) > 0


def test_hero_ausserhalb_range_faellt_auf_basis_hand_not_in_range():
    """Review-Befund 1: Fixture seed 3, Hero Sitz 1 (Td4s) liegt AUSSERHALB der oeffentlichen Range. Frueher wurde
    dort die uniforme Solver-Zeile gespielt (25 % Jam) — jetzt IMMER Basis mit Vertrags-Status hand_not_in_range,
    genau EIN Basis-Aufruf, keine Verteilung im Trace, kein Knopf."""
    g = spiel_bis_river(seed=SEED_HERO_OOP_AUSSERHALB); g.act("check"); g.act("bet", 1500)
    st = g.state()
    basis = BasisMock(); fab = fabrik(basis, iters=SCHNELL_ITERS)
    d = fab(1)
    assert d(st) == ("call", None) and basis.aufrufe == 1
    gp, tr = _plan_und_trace(fab, 1)
    assert not gp.im_support(list(st["players"][1]["hole"])), "Fixture-Voraussetzung (Sonde 2026-09-07)"
    assert tr["fallback_status"] == "hand_not_in_range" and tr["plan_verteilung"] is None and tr["offtree"] is False
    assert tr["sample_u"] is None and tr["gewaehlter_arm"] is None
    assert rp.FLAG_HERO_AUSSERHALB_RANGE in tr["flags"] and tr["basis"] == {"kind": "call", "chips": None}
    assert fab.statistik(1) == {"plan_pot_entscheidungen": 1, "hand_not_in_range": 1}
    try:
        rp.river_plan_guard(basis, bei_hero_ausserhalb="spielen")
    except TypeError:
        pass
    else:
        raise AssertionError("der Knopf 'spielen' (Reach-0-Uniform spielen) darf nicht mehr existieren")


def test_plan_pot_spielt_nie_eine_reach0_zeile():
    """Ueber mehrere Haende beider Support-Lagen: Flag hero_ausserhalb_range <=> Status hand_not_in_range;
    eine Plan-Verteilung im Trace existiert NUR fuer Combos im Support."""
    faelle = [(SEED_HERO_OOP_AUSSERHALB, 1), (6, 1), (SEED_HERO_IM_SUPPORT, 1), (SEED_HERO_IM_SUPPORT, 0)]
    gesehen = set()
    for seed, seat in faelle:
        g = spiel_bis_river(seed=seed)
        if seat == 1:
            g.act("check"); g.act("bet", 1500)
        else:
            g.act("check")
        st = g.state()
        basis = BasisMock(); fab = fabrik(basis, iters=SCHNELL_ITERS)
        fab(seat)(st)
        gp, tr = _plan_und_trace(fab, seat)
        drin = gp.im_support(list(st["players"][seat]["hole"]))
        gesehen.add(drin)
        if drin:
            assert tr["fallback_status"] == "keiner" and tr["plan_verteilung"] is not None and basis.aufrufe == 0
            assert rp.FLAG_HERO_AUSSERHALB_RANGE not in tr["flags"]
        else:
            assert tr["fallback_status"] == "hand_not_in_range" and tr["plan_verteilung"] is None and basis.aufrufe == 1
            assert rp.FLAG_HERO_AUSSERHALB_RANGE in tr["flags"]
    assert gesehen == {True, False}, "beide Lagen muessen vorkommen (Sonde: seed 3/6 OOP ausserhalb, seed 4 innerhalb)"


def test_k1_wird_genutzt_wenn_vorhanden_sonst_tracker_fallback_geflaggt():
    _st, gp = plan_oop_facing_bet()
    try:
        import pokerbot.strategy.hero_range  # noqa: F401
        k1_da = True
    except ImportError:
        k1_da = False
    if k1_da:
        assert gp.plan.ranges.herkunft == "k1_likelihood" and not any(f.startswith(rp.FLAG_K1_FALLBACK) for f in gp.flags)
        assert gp.plan.ranges.hero_rolle in ("position", "initiative")
    else:
        assert gp.plan.ranges.herkunft == "tracker" and any(f.startswith(rp.FLAG_K1_FALLBACK) for f in gp.flags)
    assert gp.plan.ranges.hero_injiziert is False and gp.plan.aktiviert and gp.plan.schwelle_chips == 1500


def test_zeiten_werden_getrennt_erfasst():
    """Review-Befund 2: K1-/Range-Zeit und Solve-Zeit getrennt am Plan (immer) — die Attribution haengt nicht mehr
    an Scratch-Skripten."""
    _st, gp = plan_oop_facing_bet()
    z = gp.zeiten
    assert z is not None and z.ranges_s > 0 and z.solve_s > 0 and z.gesamt_s >= z.ranges_s + z.solve_s
    ms = z.als_ms()
    assert set(ms) == {"ranges", "solve", "gesamt"} and ms["gesamt"] >= ms["solve"]


# ---------------------------------------------------------------- Sampling / private Randomisierung
def test_sampling_10000_seeds_je_verteilung():
    verteilungen = [[0.3, 0.7], [0.1, 0.2, 0.7], [0.0, 1.0], [1.0, 0.0, 0.0], [0.5, 0.0, 0.5], [0.05, 0.95]]
    n = 10_000
    for probs in verteilungen:
        zaehler = [0] * len(probs)
        for i in range(n):
            seed = i.to_bytes(4, "big")
            u = None if rp.ist_degeneriert(probs) else rp.private_u(seed, "hand", "river/9")
            zaehler[rp.sample_aus_verteilung(probs, u)] += 1
        for k, p in enumerate(probs):
            if p in (0.0, 1.0):
                assert zaehler[k] == (n if p == 1.0 else 0), f"p∈{{0,1}} muss exakt sein: {probs} -> {zaehler}"
            else:
                se = math.sqrt(n * p * (1 - p))
                assert abs(zaehler[k] - n * p) <= 5 * se, f"{probs}: Arm {k} {zaehler[k]} vs {n*p} (SE {se:.1f})"


def test_private_u_in_intervall_und_key_abhaengig():
    u1 = rp.private_u(b"a" * 16, "h1", "river/9")
    assert 0.0 <= u1 < 1.0
    assert u1 == rp.private_u(b"a" * 16, "h1", "river/9")
    assert u1 != rp.private_u(b"b" * 16, "h1", "river/9")
    assert u1 != rp.private_u(b"a" * 16, "h1", "river/11")
    assert rp.privater_seed_gym("h1", 0) != rp.privater_seed_gym("h1", 1)


def test_determinismus_gleiche_inputs_gleiche_aktion():
    ergebnisse = []
    for _ in range(2):
        basis = BasisMock()
        fab = fabrik(basis, iters=SCHNELL_ITERS)
        d = fab(1)
        g = spiel_bis_river()
        g.act("check"); g.act("bet", 1500)
        ergebnisse.append((d(g.state()), fab.letzter_trace(1)["sample_u"], fab.letzter_trace(1)["plan_verteilung"]))
    assert ergebnisse[0] == ergebnisse[1] and ergebnisse[0][2] is not None
    # expliziter privater Seed -> Quelle test_seed; anderer Seed darf die Aktion aendern, muss aber deterministisch sein
    basis = BasisMock()
    fab = fabrik(basis, privater_seed=b"\x01" * 16)
    assert fab.private_seed_quelle == "test_seed" and fab.private_seed_hex == "01" * 16
    fab_gym = fabrik(BasisMock())
    assert fab_gym.private_seed_quelle == "deck_hand_id_sitz" and fab_gym.private_seed_hex is None
    fab_live = fabrik(BasisMock(), modus="live", aufwaermen=False)
    assert fab_live.private_seed_quelle == "os_urandom" and len(fab_live.private_seed_hex) == 32


def test_hand_id_wird_als_adresse_genutzt_sonst_kartenhash_mit_flag():
    g = spiel_bis_river()
    st = g.state()
    adr, flags = rp.hand_adresse_aus(st)
    assert adr.startswith("karten:") and flags == [rp.FLAG_CACHE_KEY_OHNE_HAND_ID]
    st2 = dict(st); st2["hand_id"] = 4711
    assert rp.hand_adresse_aus(st2) == ("4711", [])


# ---------------------------------------------------------------- Trace / Vertrag
def test_trace_jsonl_deterministisch_ohne_zeitstempel():
    with tempfile.TemporaryDirectory() as tmp:
        pfad = os.path.join(tmp, "k2_trace.jsonl")
        basis = BasisMock()
        fab = fabrik(basis, trace_pfad=pfad, iters=SCHNELL_ITERS)
        d = fab(1)
        g = spiel_bis_river()
        g.act("check"); g.act("bet", 1500)
        d(g.state())
        g2 = spiel_bis_river(); g2.act("check"); g2.act("bet", 1000)
        d(g2.state())
        zeilen = [json.loads(z) for z in open(pfad, encoding="utf-8")]
    assert len(zeilen) == 2
    for z in zeilen:
        assert "ts" not in z and "latenz_ms" not in z and "zeiten_ms" not in z and z["version"] == rp.PLAN_VERSION
        assert z["deadline_status"] == "iterations_deadline" and z["private_seed_quelle"] == "deck_hand_id_sitz"
    assert zeilen[0]["basis"] is None and zeilen[0]["fallback_status"] == "keiner"
    assert zeilen[1]["fallback_status"] == "offtree" and zeilen[1]["basis"] is not None


def test_entscheidungstrace_vertrag_akzeptiert_plan_und_fallback():
    EntscheidungsTrace(basis=None, final=ActionKey.call(), plan_verteilung=((ActionKey.fold(), 0.4), (ActionKey.call(), 0.6)),
                       legalitaet=ActionKey.call(), sample_u=0.5)
    EntscheidungsTrace(basis=ActionKey.call(), final=ActionKey.call(), fallback_status="offtree", offtree=True)
    EntscheidungsTrace(basis=ActionKey.call(), final=ActionKey.call(), fallback_status="hand_not_in_range")


def test_legalisiere_exakt_wie_improver():
    st = {"to_act": 1, "current_bet": 1500, "players": [{"stack": 17500, "committed_street": 1500, "all_in": False},
                                                          {"stack": 19000, "committed_street": 0, "all_in": False}]}
    assert rp.legalisiere(ActionKey.fold(), st) == ("fold", None)
    assert rp.legalisiere(ActionKey.call(), st) == ("call", None)
    assert rp.legalisiere(ActionKey.raise_to(5550), st) == ("raise", 5550)
    assert rp.legalisiere(ActionKey.raise_to(19000), st) == ("allin", None)         # betrag >= stack-1
    st0 = {**st, "current_bet": 0, "players": [{"stack": 19000, "committed_street": 0, "all_in": False},
                                                {"stack": 19000, "committed_street": 0, "all_in": False}]}
    assert rp.legalisiere(ActionKey.fold(), st0) == ("check", None)
    assert rp.legalisiere(ActionKey.raise_to(700), st0) == ("bet", 700)
    st_ai = {**st, "players": [{"stack": 0, "committed_street": 19000, "all_in": True},
                               {"stack": 19000, "committed_street": 0, "all_in": False}], "current_bet": 19000}
    assert rp.legalisiere(ActionKey.raise_to(19000), st_ai) == ("call", None)       # Gegner all-in -> passiv


# ---------------------------------------------------------------- Live: Deadline, Parallelitaet, geteilte Solves (E5, Review-Befund 3)
class _SolveMock:
    """Ersetzt rp.loese_plan: schlaeft `dauer_s`, liefert eine KOPIE des Fixture-Plans (verspaetet-Flag je Test
    frisch); zaehlt Aufrufe thread-sicher. Ohne GPU -> die Parallel-Mechanik ist deterministisch testbar."""

    def __init__(self, plan: rp.GeloesterPlan, dauer_s: float):
        self.plan, self.dauer_s, self.aufrufe = plan, dauer_s, 0
        self._lock = threading.Lock()

    def __call__(self, st, hero_seat, hand_adresse, **kw):
        with self._lock:
            self.aufrufe += 1
        time.sleep(self.dauer_s)
        return replace(self.plan, hand_adresse=hand_adresse, verspaetet=False)


class _gemockter_solve:
    def __init__(self, mock: _SolveMock):
        self.mock = mock

    def __enter__(self):
        self._orig = rp.loese_plan
        rp.loese_plan = self.mock
        return self.mock

    def __exit__(self, *exc):
        rp.loese_plan = self._orig


def _staaten_mit_hand_ids(st: dict, n: int) -> list[dict]:
    out = []
    for i in range(n):
        s = copy.deepcopy(st); s["hand_id"] = f"parallel-{i}"
        out.append(s)
    return out


def _parallel(d, staaten: list[dict], versatz_s: float = 0.0) -> list[dict]:
    """Ruft d(st) fuer alle Staaten gleichzeitig (Threads) auf und sammelt je Aufruf den Trace-Umschlag."""
    traces: list[dict | None] = [None] * len(staaten)
    z = d.zustand

    def lauf(i, s):
        if versatz_s:
            time.sleep(versatz_s * i)
        d(s)
        traces[i] = dict(z.letzter_trace) if z.letzter_trace and z.letzter_trace["hand_adresse"] == s["hand_id"] else None

    threads = [threading.Thread(target=lauf, args=(i, s)) for i, s in enumerate(staaten)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return traces


def _traces_aus_datei(pfad: str) -> dict[str, dict]:
    return {z["hand_adresse"]: z for z in (json.loads(l) for l in open(pfad, encoding="utf-8"))}


def test_live_8_parallele_haende_queue_budget_und_worker_knopf():
    """Review-Befund 3 (gemessen statt angenommen): 8 gleichzeitige Haende, jeder Solve 0,4 s (Mock), Deadline 1,5 s.
    DEFAULT (1 Worker, Queue-Budget 0,5 s): die Haende hinter dem laufenden Solve fallen nach ~0,5 s auf die Basis
    (Flag deadline_in_queue, latenz << deadline) statt 1,5 s zu warten; >= 1 Hand spielt den Plan; kein Solve wird
    doppelt gestartet. KNOPF solve_worker=8: alle 8 Solves starten sofort (queue < 400 ms) -> 0 Deadlines."""
    st, plan = plan_oop_facing_bet()
    staaten = _staaten_mit_hand_ids(st, 8)
    with tempfile.TemporaryDirectory() as tmp:
        pfad = os.path.join(tmp, "live.jsonl")
        basis = BasisMock()
        fab = fabrik(basis, modus="live", deadline_s=1.5, trace_pfad=pfad, aufwaermen=False)
        assert fab.solve_worker == rp.LIVE_SOLVE_WORKER == 1 and fab.queue_budget_s == rp.QUEUE_BUDGET_S == 0.5
        with _gemockter_solve(_SolveMock(plan, dauer_s=0.4)) as mock:
            _parallel(fab(1), staaten)
            fab._executor.shutdown(wait=True)             # Waisen laufen INNERHALB des Mocks aus (kein echter GPU-Solve)
        traces = _traces_aus_datei(pfad)
    assert len(traces) == 8 and mock.aufrufe == 8, "jede Hand wird genau einmal geloest (auch verspaetet), nie doppelt"
    plaene = [t for t in traces.values() if t["fallback_status"] == "keiner"]
    deadlines = [t for t in traces.values() if t["fallback_status"] == "deadline"]
    assert len(plaene) >= 1 and len(plaene) + len(deadlines) == 8 and basis.aufrufe == len(deadlines)
    assert all(rp.FLAG_DEADLINE_IN_QUEUE in t["flags"] for t in deadlines), \
        "kein Solve dauert 1,5 s: jede Deadline ist eine QUEUE-Deadline und muss so geflaggt sein"
    assert all(t["latenz_ms"] < 1000.0 for t in deadlines), \
        "Queue-Budget 0,5 s: der Fallback kommt SOFORT, nicht erst nach der 1,5-s-Deadline"
    assert all(t["deadline_status"] == "verletzt" for t in deadlines)
    for t in traces.values():
        assert set(t["zeiten_ms"]) == {"queue", "ranges", "solve", "gesamt"}
    # KNOPF: 8 Worker -> alle Solves starten sofort (Mock-Solves sind echt parallel; echte Solves serialisieren sich, Doku)
    with tempfile.TemporaryDirectory() as tmp:
        pfad = os.path.join(tmp, "live8.jsonl")
        basis8 = BasisMock()
        fab8 = fabrik(basis8, modus="live", deadline_s=1.5, solve_worker=8, trace_pfad=pfad, aufwaermen=False)
        with _gemockter_solve(_SolveMock(plan, dauer_s=0.4)) as mock8:
            _parallel(fab8(1), staaten)
            fab8._executor.shutdown(wait=True)
        traces8 = _traces_aus_datei(pfad)
    assert mock8.aufrufe == 8 and basis8.aufrufe == 0
    assert all(t["fallback_status"] == "keiner" for t in traces8.values()), \
        {k: t["fallback_status"] for k, t in traces8.items()}
    assert all(t["zeiten_ms"]["queue"] is not None and t["zeiten_ms"]["queue"] < 400.0 for t in traces8.values())


def test_live_folgeentscheidung_teilt_laufenden_solve():
    """Folge-Entscheidung derselben Hand waehrend der Solve laeuft: wartet auf DIESELBE Future (Flag solve_geteilt),
    genau EIN Solve, beide spielen den Plan."""
    st, plan = plan_oop_facing_bet()
    s = copy.deepcopy(st); s["hand_id"] = "geteilt"
    with tempfile.TemporaryDirectory() as tmp:
        pfad = os.path.join(tmp, "live.jsonl")
        basis = BasisMock()
        fab = fabrik(basis, modus="live", deadline_s=3.0, trace_pfad=pfad, aufwaermen=False)
        with _gemockter_solve(_SolveMock(plan, dauer_s=0.6)) as mock:
            _parallel(fab(1), [s, copy.deepcopy(s)], versatz_s=0.15)
            fab._executor.shutdown(wait=True)
        zeilen = [json.loads(l) for l in open(pfad, encoding="utf-8")]
    assert mock.aufrufe == 1 and basis.aufrufe == 0
    assert [z["fallback_status"] for z in zeilen] == ["keiner", "keiner"]
    assert sum(rp.FLAG_SOLVE_GETEILT in z["flags"] for z in zeilen) == 1


def test_live_verspaeteter_solve_wird_gecacht_nicht_neu_geloest():
    """Deadline verpasst -> Basis (Status deadline, Ergebnis fuer DIESE Entscheidung verworfen); der fertige Plan
    landet trotzdem im Cache: die naechste Entscheidung derselben Hand spielt ihn (Flag plan_verspaetet_genutzt)
    statt einen zweiten Solve zu starten (Kaskaden-Schutz)."""
    st, plan = plan_oop_facing_bet()
    s = copy.deepcopy(st); s["hand_id"] = "verspaetet"
    basis = BasisMock()
    fab = fabrik(basis, modus="live", deadline_s=0.1, aufwaermen=False)
    d = fab(1)
    with _gemockter_solve(_SolveMock(plan, dauer_s=0.5)) as mock:
        assert d(s) == ("call", None) and basis.aufrufe == 1
        tr1 = dict(fab.letzter_trace(1))
        assert tr1["fallback_status"] == "deadline" and rp.FLAG_DEADLINE_IN_QUEUE not in tr1["flags"]
        assert fab.letzter_plan(1) is None, "beim Fallback lag noch kein Plan vor"
        time.sleep(0.8)                                   # der Waisen-Solve wird fertig -> Cache (verspaetet)
        assert fab.letzter_plan(1) is not None and fab.letzter_plan(1).verspaetet is True
        d(s)
        tr2 = fab.letzter_trace(1)
        fab._executor.shutdown(wait=True)
    assert mock.aufrufe == 1, "kein zweiter Solve derselben Hand"
    assert tr2["fallback_status"] == "keiner" and rp.FLAG_PLAN_VERSPAETET_GENUTZT in tr2["flags"]
    assert basis.aufrufe == 1
    assert fab.statistik(1) == {"plan_pot_entscheidungen": 2, "deadline": 1, "keiner": 1}


def test_deadline_live_faellt_auf_basis_und_verwirft_ergebnis():
    """Echter GPU-Solve mit Deadline 1e-6 s: Basis, Status deadline, latenz_ms + zeiten_ms im Trace."""
    basis = BasisMock()
    fab = fabrik(basis, modus="live", deadline_s=1e-6, iters=SCHNELL_ITERS)
    assert fab.aufwaerm_s is not None and fab.aufwaerm_s > 0, "live waermt den CUDA-Kaltstart vor der ersten Hand ab"
    d = fab(1)
    g = spiel_bis_river()
    g.act("check"); g.act("bet", 1500)
    aktion = d(g.state())
    assert aktion == ("call", None) and basis.aufrufe == 1
    tr = fab.letzter_trace(1)
    assert tr["fallback_status"] == "deadline" and tr["deadline_status"] == "verletzt"
    assert "latenz_ms" in tr and set(tr["zeiten_ms"]) == {"queue", "ranges", "solve", "gesamt"}
    assert fab.letzter_plan(1) is None, "verspaetetes Ergebnis wird fuer diese Entscheidung verworfen"
    fab._executor.shutdown(wait=True)                    # der Waisen-Solve darf den Prozess nicht ueberleben


# ---------------------------------------------------------------- Latenz-Instrument (Karte K2 / E10; Gate-Laeufer G2)
def _bau_oop_facing_bet(seed):
    g = spiel_bis_river(seed=seed); g.act("check"); g.act("bet", 1500); return 1, g.state()


def _bau_ip_nach_check(seed):
    g = spiel_bis_river(seed=seed); g.act("check"); return 0, g.state()


def _bau_schwelle_1500(seed):
    g = spiel_bis_river(seed=seed, flop_bet=450); g.act("check"); g.act("bet", 1125); return 1, g.state()


def _bau_raise_linie(seed):
    g = spiel_bis_river(seed=seed); g.act("bet", 700); g.act("raise", 1890); return 1, g.state()


def _bau_jam(seed):
    g = spiel_bis_river(seed=seed); g.act("check"); g.act("allin"); return 1, g.state()


SCHICHTEN = (("oop_facing_bet", _bau_oop_facing_bet), ("ip_nach_check", _bau_ip_nach_check),
             ("schwelle_1500", _bau_schwelle_1500), ("raise_linie", _bau_raise_linie), ("jam", _bau_jam))
LATENZ_GATE_P99_S, LATENZ_GATE_MAX_S, LATENZ_HARTGRENZE_S = 8.0, 9.0, 30.0    # Karte K2:61-62 + E10


def _quantil(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(math.ceil(q * len(xs))) - 1)]


def _gpu_lage() -> dict:
    """nvidia-smi-Schnappschuss: Auslastung + fremde Compute-Prozesse (eine Latenz-Zahl ohne diese Angabe ist
    nicht interpretierbar — Review 2026-09-07)."""
    try:
        aus = subprocess.run(["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used", "--format=csv,noheader"],
                             capture_output=True, text=True, encoding="utf-8", timeout=10).stdout.strip()
        apps = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,process_name", "--format=csv,noheader"],
                              capture_output=True, text=True, encoding="utf-8", timeout=10).stdout.strip()
        python_procs = [l for l in apps.splitlines() if "python" in l.lower()]
        return {"gpu": aus, "fremde_python_gpu_prozesse": max(0, len(python_procs) - 1), "pid": os.getpid()}
    except Exception as e:  # noqa: BLE001
        return {"gpu": f"nicht_lesbar ({type(e).__name__})"}


def messe_latenz_geschichtet(n_aufrufe: int = 10, iters: int = rp.DEFAULT_ITERS, deadline_s: float | None = None,
                             fortschritt: bool = False) -> dict:
    """END-TO-END d(st) ueber n geschichtete Plan-Pot-Aufrufe (5 Schichten zyklisch: beide Rollen, Schwelle, Raise,
    Jam; jede Hand neu -> ein Solve je Aufruf; Aufruf 0 = kalt). Misst je Aufruf Wand-Latenz + ranges/solve
    (K1-Attribution) + Status. Gate-Zahlen: p99 < 8 s, max < 9 s (Karte), Hartgrenze 30 s (E10)."""
    basis = BasisMock()
    fab = fabrik(basis, iters=iters, **({"modus": "live", "deadline_s": deadline_s} if deadline_s else {}))
    d = {seat: fab(seat) for seat in (0, 1)}
    aufrufe = []
    for i in range(n_aufrufe):
        name, bau = SCHICHTEN[i % len(SCHICHTEN)]
        seed = 1000 + i
        seat, st = bau(seed)
        st["hand_id"] = f"lat-{i}"
        t0 = time.perf_counter()
        d[seat](st)
        wand = time.perf_counter() - t0
        tr = fab.letzter_trace(seat) or {}
        gp = d[seat].zustand.cache.get(f"lat-{i}")
        z = gp.zeiten if gp is not None and gp.zeiten is not None else None
        aufrufe.append({"i": i, "schicht": name, "seed": seed, "kalt": i == 0, "status": tr.get("fallback_status"),
                        "gesamt_s": round(wand, 3), "ranges_s": None if z is None else round(z.ranges_s, 3),
                        "solve_s": None if z is None else round(z.solve_s, 3)})
        if fortschritt:
            print(f"  [{i + 1}/{n_aufrufe}] {name:15s} {tr.get('fallback_status')!s:18s} {wand:6.2f}s"
                  + ("" if z is None else f"  ranges {z.ranges_s:5.2f}  solve {z.solve_s:5.2f}"), flush=True)
    if fab._executor is not None:
        fab._executor.shutdown(wait=True)

    def zusammenfassung(rows):
        g = [r["gesamt_s"] for r in rows]
        rs = [r["ranges_s"] for r in rows if r["ranges_s"] is not None]
        so = [r["solve_s"] for r in rows if r["solve_s"] is not None]
        out = {"n": len(rows), "gesamt_p50_s": round(statistics.median(g), 3), "gesamt_p99_s": round(_quantil(g, 0.99), 3),
               "gesamt_max_s": round(max(g), 3), "status": dict(sorted(Counter(r["status"] for r in rows).items()))}
        if rs:
            out.update(ranges_p50_s=round(statistics.median(rs), 3), ranges_max_s=round(max(rs), 3),
                       solve_p50_s=round(statistics.median(so), 3), solve_p99_s=round(_quantil(so, 0.99), 3),
                       solve_max_s=round(max(so), 3))
        return out

    warm = [r for r in aufrufe if not r["kalt"]]
    gesamt = zusammenfassung(aufrufe)
    return {"kommando": " ".join(["python", "-m", "tests.test_river_plan", "--latenz", str(n_aufrufe)]
                                 + (["--deadline", str(deadline_s)] if deadline_s else [])),
            "iters": iters, "deadline_s": deadline_s, "gpu_lage_vorher": _gpu_lage(), "gesamt": gesamt,
            "kalt": aufrufe[0], "warm": zusammenfassung(warm) if warm else None,
            "je_schicht": {name: zusammenfassung([r for r in aufrufe if r["schicht"] == name])
                           for name, _ in SCHICHTEN if any(r["schicht"] == name for r in aufrufe)},
            "gate": {"p99_unter_8s": gesamt["gesamt_p99_s"] < LATENZ_GATE_P99_S,
                     "max_unter_9s": gesamt["gesamt_max_s"] < LATENZ_GATE_MAX_S,
                     "max_unter_30s": gesamt["gesamt_max_s"] < LATENZ_HARTGRENZE_S,
                     "n_mindestens_500": n_aufrufe >= 500},
            "aufrufe": aufrufe}


def test_latenz_hartgrenze_30s():
    """E10: kein Aufruf >= 30 s (harte Grenze). Die Karten-Gates (p99 < 8 s, max < 9 s, n >= 500) sind KEIN Unit-Test:
    sie brauchen eine leere GPU und den frischen Prozess des Gate-Laeufers (--latenz 500). Bei FREMDER GPU-Last ist
    die Zahl nicht interpretierbar (gemessen 2026-09-07: Solve 2,4 s frei vs 33-45 s bei 7 fremden GPU-Prozessen)
    -> UEBERSPRUNGEN mit Befund statt falsch rot."""
    import unittest
    lage = _gpu_lage()
    if lage.get("fremde_python_gpu_prozesse", 0) > 0:
        raise unittest.SkipTest(f"GPU belegt: {lage}")
    m = messe_latenz_geschichtet(n_aufrufe=5, iters=rp.DEFAULT_ITERS)
    assert m["gate"]["max_unter_30s"], m["gesamt"]
    assert set(m["je_schicht"]) == {n for n, _ in SCHICHTEN}


def _latenz_cli(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="K2-Latenz-Abnahme (Karte K2 / E10): geschichtete End-to-End-Aufrufe")
    ap.add_argument("--latenz", type=int, required=True, help="Anzahl Aufrufe (Karte: >= 500)")
    ap.add_argument("--ausgabe", default=None, help="JSON-Pfad, z.B. data/runs/v10/latenz_k2.json")
    ap.add_argument("--iters", type=int, default=rp.DEFAULT_ITERS)
    ap.add_argument("--deadline", type=float, default=None, help="Live-Modus mit Zeit-Deadline (Karte: 7,5)")
    a = ap.parse_args(argv)
    print("GPU-Lage vorher:", json.dumps(_gpu_lage()), flush=True)
    m = messe_latenz_geschichtet(a.latenz, iters=a.iters, deadline_s=a.deadline, fortschritt=True)
    m["gpu_lage_nachher"] = _gpu_lage()
    kurz = {k: v for k, v in m.items() if k != "aufrufe"}
    print(json.dumps(kurz, indent=1, ensure_ascii=False))
    if a.ausgabe:
        os.makedirs(os.path.dirname(os.path.abspath(a.ausgabe)), exist_ok=True)
        with open(a.ausgabe, "w", encoding="utf-8") as f:
            json.dump(m, f, indent=1, ensure_ascii=False)
        print("geschrieben:", a.ausgabe)
    return 0 if all(m["gate"].values()) else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--latenz" in sys.argv:
        sys.exit(_latenz_cli(sys.argv[1:]))
    import unittest
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    rot = uebersprungen = 0
    for name, fn in tests:
        t0 = time.perf_counter()
        try:
            fn()
            print(f"  OK   {name} ({time.perf_counter() - t0:.2f}s)", flush=True)
        except unittest.SkipTest as e:
            uebersprungen += 1
            print(f"  UEBERSPRUNGEN {name}: {e}", flush=True)
        except Exception as e:  # noqa: BLE001
            rot += 1
            print(f"  ROT  {name}: {type(e).__name__}: {e}", flush=True)
    print(f"{len(tests) - rot - uebersprungen}/{len(tests)} gruen, {uebersprungen} uebersprungen, {rot} rot")
    m = messe_latenz_geschichtet(10, rp.DEFAULT_ITERS)
    print("Latenz (10 geschichtete End-to-End-Aufrufe, 150 Iter):", json.dumps({k: m[k] for k in ("gesamt", "kalt", "gpu_lage_vorher", "gate")}))
    sys.exit(1 if rot else 0)
