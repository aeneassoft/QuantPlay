"""POLICY-ORACLE — die Verteilung der AUSGEFUEHRTEN v5-Politik (Arm A, Stack r8_stack) je Hero-Combo an einem
River-Knoten (v10 K3, docs/plans/V10_BUILD_CARD.md K3 'Politiken' + E3; Fakten docs/reports/V10_FACTS.md A3/A5/B7).

Ergebnis je Knoten: contracts.PolicyTable [angefragte board-kompatible Combos x ActionKey] + Meta.

GEBATCHTES DESIGN (Fix-Runde 2026-09-07). Der r8_stack ist pargate.py:100-108 exakt
    river_gpu_guard( river_wert_bremse( r6_button-Kette ) )  =  river_gpu_guard( r7_wert )
und river_gpu_guard (improver.py:477-533) ist eine PURE Regel ueber (Basis-Aktion, Solver-Ergebnis des Spots).
Der Oracle zerlegt deshalb exakt:
  (a) BASIS-AKTION je Combo = decide() der Kette OHNE den aeusseren GPU-Guard (pargate._baue_fabrik('r7_wert',
      seed) im Gym-Kanal; ~20 ms je Aufruf), ueber S Seeds mit FRISCHER Instanz je Seed (bot.rng = Random(seed));
  (b) CHIRURGIE-EFFEKT je Combo = die river_gpu_guard-Regel (Trigger st['pot'] >= 3000, p_basis < 0,10 &
      p_alt > 0,70 -> Ueberschreiben; Bet-Size int(0,75*pot)) als Funktion `chirurgie(...)` — mit dem Solver-
      Ergebnis aus EINEM gpu_resolver.solve_spots-Aufruf fuer ALLE Combos des Knotens (eine RiverSpot je Combo
      mit hero_hole=combo; die HERO_MIN_GEWICHT-Injektion passiert in solve_spots genau wie im Guard);
  (c) Kanal 'live' (PRINCE, exploit OFF, TexasSolver ON): die Resolver-VERTEILUNG (resolver.river_strategy, E3)
      je Combo; jedes Label mit p > 0 wird als ERZWUNGENES Resolver-Ergebnis durch die r7_wert-Kette geschickt
      (wert_bremse greift NACH dem Resolver, V10_FAKTEN A3 letzter Satz), dann Chirurgie wie (b); Floor-Faelle
      (Resolver-Gate bot.py:1039-1052 faellt) wie (a) ueber Seeds.
Identitaet: tests/test_river_br_pruefstand.py::test_oracle_identitaet_gegen_r8_stack vergleicht den gebatchten
Oracle mit dem DIREKTEN decide() der vollen r8_stack-Kette (B=1-Solve im Guard) je (Combo, Seed).

WARUM NICHT 'SEKUNDEN' (gemessen 2026-09-07, RTX 3080 Ti, Root 2990016 pot 3060, 150 Iter fp32): solve_spots
kostet 209 ms/Spot bei max_batch=192 und 215 ms/Spot bei 64 — bandbreiten-bound (W/M [B,1326,1326] je Spot,
gpu_cfr.RiverCFRBatch), die Batch-Groesse bringt nichts. Jede Combo hat durch die 2 %-Injektion eine EIGENE
Hero-Range -> ein eigener Solve; 1081 Combos = ~226 s je GPU-Knoten. Der Gewinn des Batchings liegt im Wegfall
der GPU-Kontention (6 Worker x B=16 -> 364-370 s im alten Pilot) und darin, dass der Pruefstand NUR Combos mit
Hero-Reach > 0 am Knoten anfragt (exakt fuer w/E_H/R: Reach-0-Zeilen tragen 0) — `tabelle(..., combos=)`.

GPU-Guard-Batching vs B=1: Batch-bmm kann in den letzten Bits vom B=1-Solve des Guards differieren (gpu_cfr
Selbsttest max|dSigma| ~1e-7); ein Schwellen-Umschlag an exakt p=0,10/0,70 ist theoretisch moeglich. Der
Identitaetstest zaehlt Abweichungen (Meta 'gpu_batch_max'); GPU_BATCH_MAX=64 (2,7 GB Peak statt 5,3 GB bei 192).

Prozesse: ein CPU-Pool (Worker mit Kanal-Env VOR dem bot-Import: Import-Zeit-Konstanten, V10_FAKTEN A3) fuer die
Basis-decide()s und EIN GPU-Prozess (Pool(1)) fuer die Solves — die GPU wird nie von mehreren Prozessen geteilt
(Pilot 2026-09-07: 12 Worker liefen in CUDA-OOM, vom Guard still geschluckt). Solve-Fehler werden GEZAEHLT: eine
Tabelle mit Fehlern ist ungueltig (nicht gecacht, Pruefstand -> UNSUPPORTED).

Cache je (root_hash, knoten_hash, kanal, S, stack, CODE-FINGERPRINT) unter data/runs/v10/policy_oracle_cache/;
Zeilen werden je Combo ergaenzt (Union), der Fingerprint (sha256 der beteiligten Module + Konstanten) verhindert,
dass eine alte v5-Politik nach Code-Aenderungen still weiterverwendet wird (Review MITTEL 2026-09-07).

Run (Pilot, Kosten je Knoten): python -m research.policy_oracle --split entwicklung --roots 2 --seeds 2 --kanal gym --workers 4
"""
from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing as mp
import os
import sys
import time
from pathlib import Path

from pokerbot.strategy.contracts import ActionKey, PolicyTable, combo_index, combo_kanonisch, kanonisiere

ORACLE_VERSION = "policy-oracle-2"          # gebatchtes Design (Fix-Runde 2026-09-07)
STACK_ARM_A = "r8_stack"                    # Arm A = v5 (auslese.FINAL_STACK); Build-Karte 'Arme'
BASIS_STACK = "r7_wert"                     # pargate.py:100-108: r8_stack == river_gpu_guard(r7_wert)
KANAELE = ("live", "gym")
GYM_EQUITY_ITERS = 120                      # duplicate.py:103 (Gate-Kanal)
# river_gpu_guard-Parameter (improver.py:477-478, pargate.py:104-108 nutzt die Defaults)
GPU_GUARD_MIN_POT = 3000
GPU_GUARD_ITERS = 150
GPU_GUARD_P_MAX_BASIS = 0.10
GPU_GUARD_P_MIN_ALT = 0.70
GPU_GUARD_BET_FRAC = 0.75                   # improver.py:527: int(0.75 * st['pot'])
GPU_BATCH_MAX = 64                          # gemessen 215 ms/Spot (192: 209 ms) — bandbreiten-bound; 2,7 GB Peak
CPU_WORKERS_DEFAULT = 4
CACHE_DIR = Path("data/runs/v10/policy_oracle_cache")
REPO = Path(__file__).resolve().parents[1]
FINGERPRINT_DATEIEN = ("pokerbot/strategy/bot.py", "pokerbot/strategy/postflop.py", "pokerbot/strategy/advisor.py",
                       "pokerbot/strategy/range_tracker.py", "pokerbot/strategy/resolver.py",
                       "pokerbot/strategy/gpu_resolver.py", "pokerbot/strategy/gpu_cfr.py",
                       "pokerbot/engine/equity.py", "pokerbot/autogym/improver.py", "pokerbot/autogym/pargate.py",
                       "pokerbot/benchmark/duplicate.py")
BB = 100

_RANKS = "23456789TJQKA"
_SUITS = "shdc"
_DECK = [r + s for r in _RANKS for s in _SUITS]


# ================================================================ Combos
def lebende_combos(board: list[str]) -> list[tuple[str, str]]:
    """Alle board-kompatiblen Combos in kanonischer Reihenfolge (1081 bei 5 Board-Karten)."""
    frei = [c for c in _DECK if c not in set(board)]
    out = []
    for i in range(len(frei)):
        for j in range(i + 1, len(frei)):
            out.append(combo_kanonisch(frei[i], frei[j]))
    return out


COMBO_VON_INDEX: dict[int, tuple[str, str]] = {combo_index(*c): c for c in lebende_combos([])}
assert len(COMBO_VON_INDEX) == 1326


def combos_mit_masse(vektor) -> list[tuple[str, str]]:
    """Combos mit Gewicht > 0 in einem [1326]-Vektor (gpu_cfr-Indizierung) — die Anfrage-Menge des Pruefstands."""
    return [COMBO_VON_INDEX[i] for i in range(len(vektor)) if float(vektor[i]) > 0.0]


def combo_str(c: tuple[str, str]) -> str:
    return c[0] + c[1]


# ================================================================ Zustand am Knoten (Engine-Regeln, game.py)
def legal_fuer(st: dict, seat: int, min_raise: int) -> dict:
    """legal_actions() der Engine (game.py:97-128) fuer den Sitz `seat` auf einem Adapter-/Engine-State."""
    p, opp = st["players"][seat], st["players"][1 - seat]
    to_call = int(st["current_bet"]) - int(p["committed_street"])
    can_raise = p["stack"] > to_call and not opp.get("all_in", False)
    is_bet = int(st["current_bet"]) == 0
    raise_min = raise_max = None
    if can_raise:
        raise_max = int(p["committed_street"]) + int(p["stack"])
        raise_min = (min(int(p["committed_street"]) + int(st["bb"]), raise_max) if is_bet
                     else min(int(st["current_bet"]) + int(min_raise), raise_max))
    return {"to_act": seat, "to_call": to_call, "can_fold": to_call > 0, "can_check": to_call == 0,
            "can_call": to_call > 0, "call_amount": min(to_call, int(p["stack"])), "can_raise": bool(can_raise),
            "is_bet": is_bet, "raise_min": raise_min, "raise_max": raise_max, "pot": int(st["pot"])}


def zustand_nach_pfad(root_state: dict, pfad: list[dict], hero_seat: int) -> dict:
    """Engine-State am Knoten nach den River-Aktionen `pfad` = [{player, action, to?}] ab River-Beginn.
    Chip-Buchhaltung wie game.act (game.py:141-181): Betrag = Raise-TO-Level der Strasse; call zahlt die
    Differenz; min_raise = groesstes Inkrement der Strasse (Start bb, game.py:212). Hero (to_act) = hero_seat."""
    st = json.loads(json.dumps(root_state))            # tiefe Kopie (Dicts/Listen)
    st["history"] = list(st.get("history") or [])
    min_raise = int(st["bb"])
    for a in pfad:
        s, art = int(a["player"]), a["action"]
        me = st["players"][s]
        if art == "check":
            st["history"].append({"player": s, "action": "check", "street": "river"})
        elif art == "call":
            diff = int(st["current_bet"]) - int(me["committed_street"])
            diff = min(diff, int(me["stack"]))
            _zahle(st, me, diff)
            st["history"].append({"player": s, "action": "call", "street": "river"})
        elif art in ("bet", "raise"):
            level = int(a["to"])
            inkrement = level - int(st["current_bet"])
            label = "bet" if int(st["current_bet"]) == 0 else "raise"
            _zahle(st, me, level - int(me["committed_street"]))
            st["current_bet"] = level
            if inkrement >= min_raise:
                min_raise = inkrement
            st["history"].append({"player": s, "action": label, "street": "river", "to": level})
        else:
            raise ValueError(f"Pfad-Aktion {art!r} baut keinen Entscheidungszustand")
    st["to_act"] = hero_seat
    st["legal"] = legal_fuer(st, hero_seat, min_raise)
    st["_min_raise"] = min_raise
    return st


def _zahle(st: dict, me: dict, chips: int) -> None:
    me["stack"] = int(me["stack"]) - chips
    me["committed_street"] = int(me["committed_street"]) + chips
    me["committed_total"] = int(me.get("committed_total", 0)) + chips
    me["all_in"] = me["stack"] <= 0
    st["pot"] = int(st["pot"]) + chips


def mit_hole(st: dict, hero_seat: int, combo: tuple[str, str]) -> dict:
    """Kopie des Zustands mit hypothetischer Hero-Combo; Villain bleibt '??' (kein Informationsleck)."""
    st2 = dict(st)
    st2["players"] = [dict(p) for p in st["players"]]
    st2["players"][hero_seat]["hole"] = list(combo)
    st2["players"][1 - hero_seat]["hole"] = ["??", "??"]
    return st2


def knoten_hash(st: dict) -> str:
    """Schluessel des oeffentlichen Knotens (ohne Hole-Karten): Board, Pot, Einsaetze, History-Aktionen."""
    hist = [(h.get("player"), h.get("action"), h.get("street"), h.get("to")) for h in st.get("history", [])]
    blob = json.dumps([st["board"], st["pot"], st["current_bet"], st["button"], st["to_act"],
                       [(p["stack"], p["committed_street"]) for p in st["players"]], hist], default=str)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]


def erster_hero_knoten(root: dict) -> dict:
    """Zustand von Heros ERSTER River-Entscheidung: OOP-Hero = Root; IP-Hero = nach Villain-Check."""
    hs = root["hero_seat"]
    pfad = [] if root["hero_oop"] else [{"player": 1 - hs, "action": "check"}]
    return zustand_nach_pfad(root["root_state"], pfad, hs)


def code_fingerprint() -> str:
    """sha256 der Module, die die Arm-A-Politik bestimmen, + der Oracle-Konstanten (Cache-Schluessel-Baustein)."""
    h = hashlib.sha256()
    for rel in FINGERPRINT_DATEIEN:
        h.update(rel.encode("utf-8"))
        h.update((REPO / rel).read_bytes())
    h.update(json.dumps({"oracle": ORACLE_VERSION, "basis_stack": BASIS_STACK, "gpu_batch_max": GPU_BATCH_MAX,
                         "gpu_guard_iters": GPU_GUARD_ITERS, "gym_equity_iters": GYM_EQUITY_ITERS},
                        sort_keys=True).encode("utf-8"))
    return h.hexdigest()[:12]


# ================================================================ Die Chirurgie-Regel (river_gpu_guard, pur)
def chirurgie(a: str, amt, st: dict, res: dict | None, p_max_basis: float = GPU_GUARD_P_MAX_BASIS,
              p_min_alt: float = GPU_GUARD_P_MIN_ALT, min_pot_chips: int = GPU_GUARD_MIN_POT):
    """improver.river_gpu_guard.d (improver.py:496-531) als Funktion von (Basis-Aktion, Solver-Ergebnis `res`
    des Spots dieser Combo). `res` None = Spot nicht rekonstruierbar oder Navigation gescheitert -> Basis bleibt
    (wie `gebaut is None` / `res is None` im Guard). Jede Ausnahme -> Basis (der Guard faengt `except Exception`)."""
    from pokerbot.autogym.improver import _frage_kind
    me = st["players"][st["to_act"]]
    to_call = max(0, st["current_bet"] - me["committed_street"])
    if st["street"] != "river" or st["pot"] < min_pot_chips:
        return a, amt
    try:
        frage = _frage_kind(a, to_call)
        if res is None:
            return a, amt
        acts, sig = res["acts"], res["sigma"]
        if frage in ("bet", "raise"):
            kand = [i for i, x in enumerate(acts) if x.startswith(("bet", "raise"))]
            p_basis = max((sig[i] for i in kand), default=0.0)
        elif frage in acts:
            p_basis = sig[acts.index(frage)]
        else:
            return a, amt
        best = max(range(len(sig)), key=lambda i: sig[i])
        if p_basis < p_max_basis and sig[best] > p_min_alt:
            alt = acts[best]
            if alt == "fold" and to_call > 0:
                return "fold", None
            if alt == "call" and to_call > 0:
                return "call", None
            if alt == "check" and to_call == 0:
                return "check", None
            if alt.startswith("bet") and to_call == 0:
                return "bet", int(GPU_GUARD_BET_FRAC * st["pot"])
    except Exception:  # noqa: BLE001
        pass            # defensiv wie der Guard: im Zweifel bleibt die Basis-Aktion
    return a, amt


# ================================================================ Worker (eigener Prozess je Kanal)
_W: dict = {}          # Worker-Zustand: kanal, seeds, Module, Resolver-Steuerung


def _setze_kanal_env(kanal: str) -> None:
    """Env VOR dem ersten pokerbot.strategy-Import (Import-Zeit-Konstanten, V10_FAKTEN A3)."""
    for v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ[v] = "1"                     # pargate._worker:155 (OpenBLAS-Init-Tod)
    for k in [k for k in os.environ if k.startswith("POKERB_")]:
        os.environ.pop(k, None)
    if kanal == "live":
        os.environ["POKERB_PRINCE"] = "1"       # gtowizard.py:23-27 -> gto_mode.apply() vor dem Bot-Import
        from pokerbot.strategy import gto_mode
        gto_mode.apply()
        from pokerbot.strategy import auslese
        auslese.setze_env(resolver_on=True)     # AUSLESE_ENV ohne RAISE_NARROW (resolver-ON kontraindiziert)


def _init_worker(kanal: str, seeds: int) -> None:
    _setze_kanal_env(kanal)
    try:
        import torch
        torch.set_num_threads(1)
    except Exception:  # noqa: BLE001
        pass
    import pokerbot.strategy.bot as botmod
    from pokerbot.strategy import resolver
    if kanal == "gym":
        botmod.EQUITY_ITERS = GYM_EQUITY_ITERS
    _W.update(kanal=kanal, seeds=seeds, botmod=botmod, resolver=resolver,
              modus={"art": "durchreichen", "label": None})
    # bot._river_resolve ruft resolver.river_resolve am Modul (bot.py:1054) -> im Worker steuerbar (Kanal 'live').
    _W["river_resolve_orig"] = resolver.river_resolve
    resolver.river_resolve = _river_resolve_gesteuert


def _river_resolve_gesteuert(state, hole, board, pot, eff_stack, oop_str, ip_str, la, rng, **kw):
    """'erzwingen' liefert das Label der Verteilung deterministisch (die Kette darunter sieht exakt die Aktion,
    die der Sampler bei diesem Label produziert haette); 'durchreichen' = Original (Floor-Faelle, Seeds)."""
    modus = _W["modus"]
    if modus["art"] == "erzwingen":
        return _W["resolver"]._label_to_action(modus["label"], la)
    return _W["river_resolve_orig"](state, hole, board, pot, eff_stack, oop_str, ip_str, la, rng, **kw)


def _live_fabrik(seed: int):
    """Live-Basis (gtowizard.py:183-196): PokerBot exploit=False, River+Turn-Resolver AN; _hand_u je Seed aus
    eigenem Random (LINE_U-Marginalisierung, V10_FAKTEN B7). duplicate.pokerbot-Vertrag make(seat)->d(st)."""
    import random
    PokerBot = _W["botmod"].PokerBot

    def make(seat):
        pb = PokerBot(seat, seed=seed, exploit=False)
        pb.use_resolver = True
        pb.use_turn_resolver = True
        pb._hand_u = random.Random(seed ^ 0x5EED).random()

        def d(st):
            pb.hero_idx = seat
            r = pb.decide(st)
            return r["action"], r["amount"]
        return d
    return make


def _kette(stack: str, seed: int, seat: int):
    """Die benannte Kette um decide (pargate._wickle = DIE EINE Quelle der Stack-Komposition). Gym-Kanal: exakt
    pargate._baue_fabrik (duplicate.pokerbot exploit=ON); live: _wickle um die Live-Basis."""
    from pokerbot.autogym.pargate import _baue_fabrik, _wickle
    if _W["kanal"] == "gym":
        return _baue_fabrik(stack, seed)(seat)
    return _wickle(stack, _live_fabrik(seed))(seat)


def _resolver_verteilung(st: dict, hero_seat: int) -> dict | None:
    """Repliziert das Gate von PokerBot._river_resolve (bot.py:1037-1054) und liefert die Resolver-VERTEILUNG
    (resolver.river_strategy) oder None (= Floor). Nur im Kanal 'live' sinnvoll."""
    from pokerbot.strategy.range_tracker import CONF_THRESHOLD, weighted_ranges
    la = st["legal"]
    if not la.get("can_raise") and not (la.get("to_call", 0) > 0 and la.get("can_call")):
        return None
    hero, vill = st["players"][hero_seat], st["players"][1 - hero_seat]
    hero_stack = hero["stack"]
    h_cs = hero.get("committed_street", 0) or 0
    v_cs = vill.get("committed_street", 0) or 0
    start_pot = max(2.0, st["pot"] - h_cs - v_cs)
    eff = min(hero_stack + h_cs, (vill.get("stack", hero_stack) or hero_stack) + v_cs)
    oop_str, ip_str, rconf = weighted_ranges(st)
    if rconf < CONF_THRESHOLD or not oop_str or not ip_str:
        return None
    strat = _W["resolver"].river_strategy(st, hero["hole"], st["board"], start_pot, eff, oop_str, ip_str, la)
    if not strat:
        return None
    probs = {lbl: max(0.0, p) for lbl, p in strat.items()}
    if sum(probs.values()) <= 0:
        return None
    return probs


def _basis_aktionen(st_h: dict, hero_seat: int) -> list[tuple[str, object, float, str, object]]:
    """Basis-Aktionen der r7_wert-Kette fuer EINE Combo: [(action, amount, masse, herkunft, kennung)].
    live + Resolver-Verteilung: kennung = Label, masse = p (herkunft 'oracle_exakt');
    sonst: kennung = Seed 1..S, masse = 1/S (herkunft 'oracle_seeds')."""
    modus = _W["modus"]
    if _W["kanal"] == "live":
        probs = _resolver_verteilung(st_h, hero_seat)
        if probs is not None:
            out = []
            tot = sum(probs.values())
            for lbl, p in probs.items():
                if p <= 0:
                    continue
                modus.update(art="erzwingen", label=lbl)
                a, amt = _kette(BASIS_STACK, 0, hero_seat)(st_h)     # Kette deterministisch -> Seed irrelevant
                out.append((a, amt, p / tot, "oracle_exakt", lbl))
            modus.update(art="durchreichen", label=None)
            return out
    modus.update(art="durchreichen", label=None)
    S = _W["seeds"]
    return [(*_kette(BASIS_STACK, seed, hero_seat)(st_h), 1.0 / S, "oracle_seeds", seed) for seed in range(1, S + 1)]


def _key_str(a: str, amt, st: dict) -> str:
    k = kanonisiere(a, amt, st)
    return k.kind if k.chips is None else f"raise_to:{k.chips}"


def _key_aus_str(s: str) -> ActionKey:
    if s.startswith("raise_to:"):
        return ActionKey.raise_to(int(s.split(":")[1]))
    return ActionKey(s)


def _gpu_stage(args: tuple) -> tuple[list, int, str | None]:
    """EIN solve_spots-Aufruf fuer alle Combos des Knotens (GPU-Prozess). Rueckgabe ([(combo, res|None)], Zahl
    gescheiterter Solves, Fehlertext). res = {'acts', 'sigma'} exakt wie der Guard es liest (improver.py:509)."""
    st, hero_seat, combos = args
    from pokerbot.autogym.improver import _river_spot_und_frage
    from pokerbot.strategy.gpu_resolver import solve_spots
    combos = [tuple(c) for c in combos]
    spots, idx = [], []
    for i, c in enumerate(combos):
        gebaut = _river_spot_und_frage(mit_hole(st, hero_seat, c), "check")     # Frage-Label geht nicht in den Solve ein
        if gebaut is not None:
            spots.append(gebaut[0]); idx.append(i)
    out: list = [(c, None) for c in combos]
    if not spots:
        return out, 0, None
    try:
        res = solve_spots(spots, iters=GPU_GUARD_ITERS, max_batch=GPU_BATCH_MAX)
    except Exception as e:  # noqa: BLE001
        return out, len(spots), f"{type(e).__name__}: {str(e)[:160]}"
    for i, r in zip(idx, res):
        if r is not None:
            out[i] = (combos[i], {"acts": list(r["acts"]), "sigma": [float(x) for x in r["sigma"]]})
    return out, 0, None


def _cpu_chunk(args: tuple) -> list[tuple]:
    """[(combo, {key: p}, herkunft, roh)] fuer einen Chunk; roh = [(kennung, key_final, key_basis)] je Basis-Zweig
    (Identitaetstest; key_final != key_basis <=> die Chirurgie hat ueberschrieben)."""
    st, hero_seat, paare = args
    out = []
    for combo, res in paare:
        combo = tuple(combo)
        st_h = mit_hole(st, hero_seat, combo)
        try:
            vert, roh, herk = {}, [], set()
            for a, amt, masse, herkunft, kennung in _basis_aktionen(st_h, hero_seat):
                a2, amt2 = chirurgie(a, amt, st_h, res)
                key = _key_str(a2, amt2, st_h)
                vert[key] = vert.get(key, 0.0) + masse
                roh.append((kennung, key, _key_str(a, amt, st_h)))
                herk.add(herkunft)
            out.append((combo, vert, "oracle_exakt" if herk == {"oracle_exakt"} else "oracle_seeds", roh))
        except Exception as e:  # noqa: BLE001
            out.append((combo, {}, f"fehler:{type(e).__name__}", []))
    return out


def _direkt_chunk(args: tuple) -> list[tuple]:
    """Referenz fuer den Identitaetstest: die VOLLE r8_stack-Kette (inkl. river_gpu_guard mit eigenem B=1-Solve)
    je (Combo, Seed) -> [(combo, seed, key)]. Laeuft im GPU-Prozess (der Guard loest selbst)."""
    st, hero_seat, combos, seeds = args
    out = []
    for c in combos:
        c = tuple(c)
        st_h = mit_hole(st, hero_seat, c)
        for seed in seeds:
            a, amt = _kette(STACK_ARM_A, seed, hero_seat)(st_h)
            out.append((c, seed, _key_str(a, amt, st_h)))
    return out


# ================================================================ Oracle (Hauptprozess)
class PolicyOracle:
    """Verteilung der Arm-A-Politik je angefragter Hero-Combo an einem River-Knoten, gecacht (Union je Knoten)."""

    def __init__(self, kanal: str = "gym", seeds: int = 4, workers: int = CPU_WORKERS_DEFAULT,
                 stack: str = STACK_ARM_A, cache_dir: Path = CACHE_DIR):
        if kanal not in KANAELE:
            raise ValueError(f"kanal muss in {KANAELE} liegen")
        if stack != STACK_ARM_A:
            raise ValueError(f"die Zerlegung Basis+Chirurgie gilt fuer {STACK_ARM_A} (= river_gpu_guard({BASIS_STACK}))")
        self.kanal, self.seeds, self.workers, self.stack = kanal, seeds, max(1, workers), stack
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.fingerprint = code_fingerprint()
        self._cpu_pool = self._gpu_pool = None
        self.statistik = {"knoten": 0, "cache_treffer_zeilen": 0, "berechnete_zeilen": 0, "gpu_solves": 0,
                          "gpu_solve_fehler": 0, "sekunden": 0.0, "sekunden_gpu": 0.0}

    # ---- Prozesse
    def _pool(self, art: str):
        ctx = mp.get_context("spawn")
        if art == "gpu":
            if self._gpu_pool is None:
                self._gpu_pool = ctx.Pool(1, initializer=_init_worker, initargs=(self.kanal, self.seeds))
            return self._gpu_pool
        if self._cpu_pool is None:
            self._cpu_pool = ctx.Pool(self.workers, initializer=_init_worker, initargs=(self.kanal, self.seeds))
        return self._cpu_pool

    def schliessen(self) -> None:
        for p in (self._cpu_pool, self._gpu_pool):
            if p is not None:
                p.close(); p.join()
        self._cpu_pool = self._gpu_pool = None

    # ---- Cache
    def _cache_pfad(self, root_hash: str, kh: str) -> Path:
        return self.cache_dir / f"{root_hash}__{kh}__{self.kanal}__S{self.seeds}__{self.stack}__fp{self.fingerprint}.json"

    def _cache_laden(self, pfad: Path, kh: str, root_hash: str) -> dict:
        if pfad.exists():
            d = json.loads(pfad.read_text(encoding="utf-8"))
            if d.get("fingerprint") == self.fingerprint:
                return d
        return {"knoten_hash": kh, "root_hash": root_hash, "kanal": self.kanal, "seeds": self.seeds,
                "stack": self.stack, "fingerprint": self.fingerprint, "oracle_version": ORACLE_VERSION,
                "gpu_batch_max": GPU_BATCH_MAX, "zeilen": {}, "herkunft": {}, "roh": {}, "fehler": {}, "laeufe": []}

    # ---- Berechnung
    def tabelle(self, root_hash: str, st: dict, hero_seat: int, combos=None) -> tuple[PolicyTable, dict]:
        """PolicyTable fuer die angefragten Combos (Default: alle lebenden) am Knoten `st` (Hero am Zug) + Meta.
        Nur noch nicht gecachte Combos werden gerechnet; die Cache-Datei traegt die Union aller Anfragen."""
        t0 = time.perf_counter()
        kh = knoten_hash(st)
        pfad = self._cache_pfad(root_hash, kh)
        cache = self._cache_laden(pfad, kh, root_hash)
        gefragt = list(dict.fromkeys(combo_kanonisch(*c) for c in (combos if combos is not None
                                                                    else lebende_combos(st["board"]))))   # dedupliziert
        offen = [c for c in gefragt if combo_str(c) not in cache["zeilen"] and combo_str(c) not in cache["fehler"]]
        gpu_aktiv = st["street"] == "river" and st["pot"] >= GPU_GUARD_MIN_POT
        solve_fehler, fehler_text, t_gpu = 0, None, 0.0
        if offen:
            res_map = {c: None for c in offen}
            if gpu_aktiv:
                t1 = time.perf_counter()
                paare, solve_fehler, fehler_text = self._pool("gpu").apply(_gpu_stage, ((st, hero_seat, offen),))
                t_gpu = time.perf_counter() - t1
                res_map.update({tuple(c): r for c, r in paare})
                self.statistik["gpu_solves"] += len(offen) - solve_fehler
            n_chunks = max(1, min(len(offen), self.workers * 3))
            chunks = [[(c, res_map[c]) for c in offen[i::n_chunks]] for i in range(n_chunks)]
            for teil in self._pool("cpu").imap_unordered(_cpu_chunk, [(st, hero_seat, ch) for ch in chunks if ch]):
                for combo, vert, herk, roh in teil:
                    cs = combo_str(combo)
                    if vert:
                        cache["zeilen"][cs] = vert
                        cache["herkunft"][cs] = herk
                        cache["roh"][cs] = [[str(k), key, basis] for k, key, basis in roh]
                    else:
                        cache["fehler"][cs] = herk
            cache["laeufe"].append({"n": len(offen), "gpu": gpu_aktiv, "sekunden": round(time.perf_counter() - t0, 2),
                                    "sekunden_gpu": round(t_gpu, 2), "gpu_solve_fehler": solve_fehler,
                                    "erzeugt": time.strftime("%Y-%m-%d %H:%M:%S")})
            if solve_fehler == 0:
                pfad.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")   # nur gueltige Tabellen cachen
        dt = time.perf_counter() - t0
        self.statistik["knoten"] += 1
        self.statistik["cache_treffer_zeilen"] += len(gefragt) - len(offen)
        self.statistik["berechnete_zeilen"] += len(offen)
        self.statistik["gpu_solve_fehler"] += solve_fehler
        self.statistik["sekunden"] += dt
        self.statistik["sekunden_gpu"] += t_gpu
        print(f"  [oracle] Knoten {kh} pot={st['pot']} combos={len(gefragt)} neu={len(offen)} "
              f"gpu={'ja' if gpu_aktiv else 'nein'}{f' ({t_gpu:.1f}s)' if t_gpu else ''} "
              f"solve_fehler={solve_fehler} {dt:.1f}s", flush=True)
        return self._tabelle_fuer(cache, gefragt), self._meta(cache, gefragt, gpu_aktiv, solve_fehler, fehler_text, dt, t_gpu)

    def direkt(self, st: dict, hero_seat: int, combos, seeds) -> dict[tuple, str]:
        """Referenz-Aktionen der VOLLEN r8_stack-Kette je (Combo, Seed) — fuer den Identitaetstest (GPU-Prozess)."""
        out = self._pool("gpu").apply(_direkt_chunk, ((st, hero_seat, [tuple(c) for c in combos], list(seeds)),))
        return {(combo_kanonisch(*c), seed): key for c, seed, key in out}

    def roh(self, root_hash: str, st: dict, combos) -> dict[tuple, list]:
        """{combo: [(kennung, key_final, key_basis)]} aus dem Cache des Knotens (nach tabelle()) — je Seed/Label die
        finale Aktion und die Basis-Aktion davor (Chirurgie sichtbar)."""
        cache = self._cache_laden(self._cache_pfad(root_hash, knoten_hash(st)), "", root_hash)
        return {combo_kanonisch(*c): [tuple(e) for e in cache["roh"].get(combo_str(combo_kanonisch(*c)), [])]
                for c in combos}

    @staticmethod
    def _tabelle_fuer(cache: dict, gefragt: list) -> PolicyTable:
        zeilen_d = cache["zeilen"]
        keys = sorted({k for c in gefragt for k in zeilen_d.get(combo_str(c), {})},
                      key=lambda s: (s.startswith("raise_to"), s))
        if not keys:
            keys = ["check"]                                     # leere Tabelle (alle Combos fehlerhaft) bleibt vertragsgueltig
        zeilen = tuple((c, tuple(float(zeilen_d[combo_str(c)].get(k, 0.0)) for k in keys))
                       for c in gefragt if combo_str(c) in zeilen_d)
        undefiniert = frozenset(c for c in gefragt if combo_str(c) not in zeilen_d)
        herk = {cache["herkunft"].get(combo_str(c)) for c in gefragt if combo_str(c) in zeilen_d}
        return PolicyTable(tuple(_key_aus_str(k) for k in keys), zeilen, undefiniert=undefiniert,
                           herkunft="oracle_exakt" if herk == {"oracle_exakt"} else "oracle_seeds")

    def _meta(self, cache: dict, gefragt: list, gpu_aktiv: bool, solve_fehler: int, fehler_text, dt: float, t_gpu: float) -> dict:
        herk: dict = {}
        for c in gefragt:
            h = cache["herkunft"].get(combo_str(c))
            if h:
                herk[h] = herk.get(h, 0) + 1
        fehler = [[list(c), cache["fehler"][combo_str(c)]] for c in gefragt if combo_str(c) in cache["fehler"]]
        return {"knoten_hash": cache["knoten_hash"], "root_hash": cache["root_hash"], "kanal": self.kanal,
                "seeds": self.seeds, "stack": self.stack, "fingerprint": self.fingerprint,
                "quantisierung": None if self.kanal == "live" else f"1/{self.seeds}",
                "sekunden": round(dt, 2), "sekunden_gpu": round(t_gpu, 2), "n_combos": len(gefragt),
                "herkunft": herk, "fehler": fehler, "gpu_guard_aktiv": gpu_aktiv, "gpu_guard_batched": gpu_aktiv,
                "gpu_batch_max": GPU_BATCH_MAX, "gpu_solve_fehler": solve_fehler, "gpu_fehler_text": fehler_text,
                "gueltig": solve_fehler == 0}


# ================================================================ Pilot-CLI
def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="entwicklung")
    ap.add_argument("--roots", type=int, default=2)
    ap.add_argument("--seeds", type=int, default=2)
    ap.add_argument("--kanal", default="gym", choices=KANAELE)
    ap.add_argument("--workers", type=int, default=CPU_WORKERS_DEFAULT)
    ap.add_argument("--min-pot", type=float, default=1500.0)
    ap.add_argument("--combos", type=int, default=0, help="nur die ersten N lebenden Combos (0 = alle)")
    args = ap.parse_args()
    from research.k3_roots import lade_roots
    _, roots = lade_roots(args.split, min_pot=args.min_pot)
    # Pilot-Auswahl: ein Root unter und einer ueber der GPU-Guard-Schwelle (beide Pfade werden ausgeuebt)
    klein = [r for r in roots if r["pot_river"] < GPU_GUARD_MIN_POT]
    gross = [r for r in roots if r["pot_river"] >= GPU_GUARD_MIN_POT]
    auswahl = (klein[:1] + gross[:1] + roots)[:args.roots]
    oracle = PolicyOracle(args.kanal, args.seeds, args.workers)
    print(f"[oracle] fingerprint {oracle.fingerprint}, kanal {args.kanal}, S={args.seeds}, workers {oracle.workers}", flush=True)
    bericht = []
    try:
        for r in auswahl:
            st = erster_hero_knoten(r)
            combos = lebende_combos(st["board"])
            if args.combos:
                combos = combos[:args.combos]
            t0 = time.perf_counter()
            tab, meta = oracle.tabelle(r["root_hash"], st, r["hero_seat"], combos=combos)
            dt = time.perf_counter() - t0
            masse = {k.kind if k.chips is None else f"raise_to:{k.chips}":
                     round(sum(p[i] for _, p in tab.zeilen) / max(1, len(tab.zeilen)), 3)
                     for i, k in enumerate(tab.aktionen)}
            bericht.append({"hand_id": r["hand_id"], "pot_river": r["pot_river"], "eff": r["eff"],
                            "hero_oop": r["hero_oop"], "sekunden": round(dt, 1), "sekunden_gpu": meta["sekunden_gpu"],
                            "n_combos": len(tab.zeilen), "aktionen_mittel": masse, "herkunft": meta["herkunft"],
                            "fehler": len(meta["fehler"]), "gpu_solve_fehler": meta["gpu_solve_fehler"],
                            "gueltig": meta["gueltig"], "workers": oracle.workers})
            print(json.dumps(bericht[-1], ensure_ascii=False), flush=True)
    finally:
        oracle.schliessen()
    out = Path("data/runs/v10") / f"policy_oracle_pilot_{args.kanal}_S{args.seeds}.json"
    out.write_text(json.dumps({"args": vars(args), "fingerprint": oracle.fingerprint, "roots": bericht,
                               "statistik": oracle.statistik}, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"-> {out}")


if __name__ == "__main__":
    main()
