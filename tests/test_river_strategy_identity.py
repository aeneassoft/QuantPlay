"""v10 K3/E3 — Byte-Identitaets-Wache fuer die Aufspaltung river_resolve = river_strategy + rng.choices.

BEWEIS-IDEE: die URSPRUENGLICHE river_resolve (Stand eabcef3, hier WOERTLICH als Referenz eingefroren) und die
neue Fassung muessen fuer identische Eingaben und identischen rng-Zustand (a) dieselbe (action, amount) liefern und
(b) denselben rng-FOLGEZUSTAND hinterlassen (genau ein rng.choices-Aufruf mit denselben Labels/Gewichten). Beide
laufen gegen DENSELBEN gefaelschten Solver (gto_oracle.solve/strategy_for gepatcht), damit der Test $0 kostet,
deterministisch ist und OHNE TexasSolver-Binary laeuft — geprueft wird der Code-Pfad (Navigation, Suit-Map,
Sampling, Legalitaetsabbildung), nicht der Solver. 20 zufaellige River-Spots (Karte: 'fuer 20 Spots identisch').

Zusaetzlich: river_strategy verbraucht KEINE Zufallszahl (rng-Zustand unveraendert) und liefert das rohe strat.

Run: python -m tests.test_river_strategy_identity   (oder pytest -q tests/test_river_strategy_identity.py)
"""
from __future__ import annotations

import random
import sys
import zlib

from pokerbot.strategy import gto_oracle as O
from pokerbot.strategy import resolver as R

N_SPOTS = 20
_RANKS = "23456789TJQKA"
_SUITS = "shdc"
_DECK = [r + s for r in _RANKS for s in _SUITS]


# ---------------------------------------------------------------- Referenz: river_resolve VOR der Aufspaltung
def _river_resolve_referenz(state, hole, board, pot, eff_stack, oop_str, ip_str, la, rng,
                            acc: float = R._RIVER_ACC, iters: int = R._RIVER_ITERS,
                            timeout: int = R._RIVER_TIMEOUT):
    """WOERTLICHE Kopie von resolver.river_resolve @ eabcef3 (nur Modul-Praefixe R./O. ergaenzt)."""
    if not oop_str or not ip_str:
        return None
    try:
        bets = R._inject_observed_sizes(state, "river", pot, R._RIVER_BETS)
        bets = R._prune_degenerate_arms(bets, "river", pot, eff_stack)
        root = O.solve(board, oop_str, ip_str, pot=max(R._MIN_SOLVE_CHIPS, pot),
                       eff_stack=max(R._MIN_SOLVE_CHIPS, eff_stack),
                       bets=bets, accuracy=acc, max_iter=iters, dump_rounds=1, threads=R._SOLVE_THREADS,
                       timeout=timeout, tag="rsv" + "".join(board))
    except Exception:  # noqa: BLE001
        return None
    node = root
    for h in R._river_actions(state):
        lbl = R._match_label(h.get("action"), h.get("to") or h.get("amount"), node)
        ch = (node.get("childrens") or {}).get(lbl) if lbl else None
        if not ch or ch.get("node_type") == "chance_node":
            return None
        node = ch
    sm = root.get("_suit_map")
    h0, h1 = (hole[0][0] + sm[hole[0][1]], hole[1][0] + sm[hole[1][1]]) if sm else (hole[0], hole[1])
    strat = O.strategy_for(node, h0, h1)
    if not strat:
        return None
    labels = list(strat.keys())
    probs = [max(0.0, p) for p in strat.values()]
    if sum(probs) <= 0:
        return None
    lbl = rng.choices(labels, weights=probs)[0]
    return R._label_to_action(lbl, la)


# ---------------------------------------------------------------- gefaelschter Solver (deterministisch je Board)
def _fake_knoten(seed: int, pot: float, tiefe: int, hero_hole: list[str], zu_act_hero: bool) -> dict:
    """Baum-Knoten im TexasSolver-Dump-Format: strategy.actions + strategy.strategy {combo: [p...]} + childrens.
    Gewollt 'schmutzig': gelegentlich ein negatives p (max(0,p)-Pfad) und eine Combo-Reihenfolge wie im Dump."""
    rnd = random.Random(seed)
    if tiefe >= 3:
        return {"node_type": "chance_node"}
    facing = tiefe % 2 == 1
    acts = (["FOLD", "CALL", f"RAISE {int(pot * 2.5)}", "ALLIN"] if facing
            else ["CHECK", f"BET {int(pot * 0.33)}", f"BET {int(pot * 0.75)}", "ALLIN"])
    probs = [rnd.random() for _ in acts]
    if rnd.random() < 0.2:
        probs[0] = -0.05                      # der max(0, p)-Zweig wird mitgeprueft
    s = sum(max(0.0, p) for p in probs) or 1.0
    probs = [p / s for p in probs]
    combo_key = hero_hole[0] + hero_hole[1] if rnd.random() < 0.5 else hero_hole[1] + hero_hole[0]
    strat = {combo_key: probs, "2c3d": [0.25] * len(acts)}
    kids = {a: _fake_knoten(seed * 31 + i + 1, pot * 1.5, tiefe + 1, hero_hole, not zu_act_hero)
            for i, a in enumerate(acts)}
    return {"node_type": "action_node", "strategy": {"actions": acts, "strategy": strat}, "childrens": kids}


class _FakeSolver:
    """Ersetzt O.solve/O.strategy_for: gleiches Board -> gleicher Baum (wie der Disk-Cache). strategy_for bleibt
    das ECHTE gto_oracle.strategy_for (es liest das Dump-Format), nur solve wird gefaelscht."""

    def __init__(self, hero_hole: list[str]):
        self.hero_hole = hero_hole
        self.aufrufe = 0

    def solve(self, board, oop, ip, **kw):
        self.aufrufe += 1
        seed = zlib.crc32("".join(board).encode()) & 0xFFFF   # prozessunabhaengig (Review NIEDRIG: hash() haengt an PYTHONHASHSEED)
        root = _fake_knoten(seed, kw.get("pot", 100.0), 0, self.hero_hole, False)
        if seed % 3 == 0:                      # ISO_CACHE-Pfad: Suit-Map mitpruefen (Identitaets-Permutation)
            root["_suit_map"] = {s: s for s in _SUITS}
        return root


def _zufaelliger_spot(rnd: random.Random) -> tuple:
    karten = rnd.sample(_DECK, 7)
    board, hole = karten[:5], karten[5:]
    pot = float(rnd.choice([600, 1400, 3000, 5200]))
    n_akt = rnd.choice([0, 0, 1, 1, 2])
    hist = [{"action": "deal", "street": "river", "board": board}]
    lvl = 0
    for i in range(n_akt):
        if i == 0:
            if rnd.random() < 0.5:
                hist.append({"player": 1, "action": "check", "street": "river"})
            else:
                lvl = int(pot * rnd.choice([0.33, 0.75]))
                hist.append({"player": 1, "action": "bet", "street": "river", "to": lvl})
        else:
            if lvl == 0:
                lvl = int(pot * 0.75)
                hist.append({"player": 0, "action": "bet", "street": "river", "to": lvl})
            else:
                hist.append({"player": 0, "action": "call", "street": "river", "amount": lvl})
    to_call = lvl if n_akt == 1 and lvl > 0 else 0
    la = {"to_call": to_call, "can_raise": True, "is_bet": to_call == 0,
          "raise_min": max(100, to_call * 2), "raise_max": 20000, "pot": pot + lvl}
    state = {"street": "river", "board": board, "pot": pot + lvl, "history": hist, "button": 0,
             "players": [{"committed_street": 0}, {"committed_street": lvl}]}
    return state, hole, board, pot, 20000.0 - rnd.choice([0, 500, 3000]), la


def test_identitaet_river_resolve_vs_referenz():
    rnd = random.Random(20260907)
    orig_solve = O.solve
    treffer = 0
    try:
        for k in range(N_SPOTS):
            state, hole, board, pot, eff, la = _zufaelliger_spot(rnd)
            fake = _FakeSolver(hole)
            O.solve = fake.solve
            rng_a, rng_b = random.Random(1000 + k), random.Random(1000 + k)
            assert rng_a.getstate() == rng_b.getstate()
            ref = _river_resolve_referenz(state, hole, board, pot, eff, "AA,KK", "QQ,JJ", la, rng_a)
            neu = R.river_resolve(state, hole, board, pot, eff, "AA,KK", "QQ,JJ", la, rng_b)
            assert ref == neu, f"Spot {k}: Referenz {ref} != neu {neu}"
            assert rng_a.getstate() == rng_b.getstate(), f"Spot {k}: rng-Folgezustand divergiert"
            treffer += ref is not None
            # river_strategy: Verteilung ohne Zufallsverbrauch, identische Labels wie der Sampler sieht
            rng_c = random.Random(5)
            vorher = rng_c.getstate()
            strat = R.river_strategy(state, hole, board, pot, eff, "AA,KK", "QQ,JJ", la)
            assert rng_c.getstate() == vorher
            assert (strat is None) == (ref is None) or (strat is not None and sum(max(0.0, p) for p in strat.values()) <= 0), \
                f"Spot {k}: strat/None-Faelle divergieren"
            if strat is not None:
                assert abs(sum(max(0.0, p) for p in strat.values()) - 1.0) < 1e-9 or sum(max(0.0, p) for p in strat.values()) <= 0
    finally:
        O.solve = orig_solve
    # Leere Ranges -> beide None, kein Solver-Aufruf
    assert R.river_strategy({}, ["As", "Kd"], [], 100, 100, "", "AA", {}) is None
    assert treffer >= 5, f"Fixture zu schwach: nur {treffer}/{N_SPOTS} Spots mit Strategie"
    return treffer


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    n = test_identitaet_river_resolve_vs_referenz()
    print(f"river_strategy-Identitaet: {N_SPOTS}/{N_SPOTS} Spots identisch (action, amount) + rng-Folgezustand; "
          f"{n} Spots mit Strategie, Rest None-Pfade. OK")
