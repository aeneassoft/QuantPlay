"""Kontrollen des River-BR-Pruefstands (v10 K3, Karte 'Kontrollen'): A/A == 0 (1e-6); analytisch Matching Pennies
(Mischung -> Sicherheitsverlust 0, reine Strategie -> 1); kleine Karten-Fixture gegen UNABHAENGIGE Brute-Force-
Enumeration aller reinen Villain-Strategien (<= 1e-6; beweist, dass die BR Heros Karte NICHT sieht — die Villain-
Strategie ist je (Villain-Combo, Knoten) definiert); Purify-Kontrolle (weich) am Clairvoyance-Toy; Struktur-
Identitaet des rollen-spezifischen Baums mit gpu_cfr.build_river_tree; Zustandsaufbau vs Engine (game.act);
Review-Fixes 2026-09-07: 1-Chip-Arm-Zuordnung statt 8 %-Snapping (HOCH), exakte Zusatzarme je Knoten, Arm B per Label
auf den Evaluationsbaum abgebildet (BLOCKER: w_B exakt erhalten, Regret endlich, E2E-Status ok); Fix-Runde:
Chirurgie-Regel pur == river_gpu_guard, Reach-Maske, IDENTITAET gebatchter Oracle vs volle r8_stack-Kette
(braucht data/runs/v10/k3_roots_entwicklung.jsonl + GPU; ~2 min).

Run: python -m tests.test_river_br_pruefstand
"""
from __future__ import annotations

import itertools
import math
import random
import sys

import torch

from pokerbot.engine.evaluator import evaluate
from pokerbot.strategy.contracts import ActionKey, PolicyTable, combo_index
from pokerbot.strategy.gpu_cfr import DEVICE, N_COMBOS, Node, build_river_tree, range_vector
from research import river_br_pruefstand as P

TOL = 1e-6
_RANKS = "23456789TJQKA"
_SUITS = "shdc"
_DECK = [r + s for r in _RANKS for s in _SUITS]


# ---------------------------------------------------------------- 1. Matching Pennies (analytisch)
class _Blatt:
    """Terminal ohne Karten: Nutzen-Vektor je Villain-'Combo' als Funktion der Hero-Reach."""
    __slots__ = ("actor", "acts", "kids", "terminal", "invest", "pot", "sd_pot", "fold_von", "vill_aktion")

    def __init__(self, vill_aktion):
        self.actor, self.acts, self.kids, self.terminal, self.vill_aktion = -1, [], [], "mp", vill_aktion
        self.invest, self.pot, self.sd_pot, self.fold_von = (0.0, 0.0), 0.0, 0.0, None


class _MatchingPennies:
    """Hero 'Combos' = {Kopf, Zahl} (seine Mischung IST die Range); Villain hat 2 Slots (Masse nur im ersten).
    Villain gewinnt +1 bei Gleichheit. Hero = Rolle 0 (ohne Entscheidungsknoten), Villain = Rolle 1."""

    def __init__(self, p_kopf: float):
        self.n_combos = 2
        self.r = [torch.tensor([p_kopf, 1.0 - p_kopf], dtype=torch.float64),
                  torch.tensor([1.0, 0.0], dtype=torch.float64)]
        self.paare = 1.0
        self.root = Node(1, 0.0, (0.0, 0.0))
        self.root.acts = ["kopf", "zahl"]
        self.root.kids = [_Blatt("kopf"), _Blatt("zahl")]

    def terminal_nutzen(self, n, reach_opp, spieler):
        # Villain-Nutzen (spieler 1): +reach(gleich) - reach(ungleich); Hero-Nutzen = das Negative
        gleich = reach_opp[0] if n.vill_aktion == "kopf" else reach_opp[1]
        ungleich = reach_opp[1] if n.vill_aktion == "kopf" else reach_opp[0]
        vorzeichen = 1.0 if spieler == 1 else -1.0
        return vorzeichen * (gleich - ungleich) * torch.ones(2, dtype=torch.float64)


def test_matching_pennies() -> None:
    v_stern = 0.0                                              # Spielwert Matching Pennies
    for p, soll in ((0.5, 0.0), (1.0, 1.0), (0.0, 1.0), (0.75, 0.5)):
        spiel = _MatchingPennies(p)
        w = P.garantiewert(spiel, spiel.root, {}, hero_rolle=0)
        e_h = v_stern - w
        assert abs(e_h - soll) < TOL, f"Matching Pennies p={p}: E_H={e_h} soll {soll}"


# ---------------------------------------------------------------- 2. Karten-Fixture vs Brute Force
def _fixture(seed: int, hero_rolle: int):
    rnd = random.Random(seed)
    karten = rnd.sample(_DECK, 5 + 6 + 6)
    board = karten[:5]
    hero_c = [(karten[5 + 2 * i], karten[6 + 2 * i]) for i in range(3)]
    vill_c = [(karten[11 + 2 * i], karten[12 + 2 * i]) for i in range(3)]
    # Gewichte fp32-exakt (Vielfache von 1/64): range_vector ist float32, die Brute-Force rechnet float64 —
    # sonst misst der Vergleich die Rundung der Range statt der BR (beobachtet: 1e-6 bei glatten Gewichten)
    hero_w = {c: round(rnd.uniform(0.2, 1.0) * 64) / 64 for c in hero_c}
    vill_w = {c: round(rnd.uniform(0.2, 1.0) * 64) / 64 for c in vill_c}
    pot, eff = 100.0, 100.0                                     # eff == pot: genau EIN Bet-Arm (Jam), kein Raise
    r_h, r_v = range_vector(hero_w), range_vector(vill_w)
    r_oop, r_ip = (r_h, r_v) if hero_rolle == 0 else (r_v, r_h)
    spiel = P.RiverSpiel(board, pot, r_oop, r_ip)
    baum = P.baue_baum(pot, eff, ((), ()), ((), ()), max_raises=0)
    # zufaellige MISCHUNG an jedem Hero-Knoten (je Combo)
    sigma = {}
    for pfad, n in P.knoten_mit_pfad(baum):
        if n.actor == hero_rolle:
            s = torch.zeros(N_COMBOS, len(n.acts), device=DEVICE, dtype=torch.float64)
            for c in hero_c:
                zeile = torch.tensor([rnd.random() for _ in n.acts], dtype=torch.float64)
                s[combo_index(*c)] = (zeile / zeile.sum()).to(DEVICE)
            sigma[pfad] = s
    return board, hero_c, vill_c, hero_w, vill_w, spiel, baum, sigma


def _brute_force_br(board, hero_c, vill_c, hero_w, vill_w, baum, sigma, hero_rolle: int, pot0: float) -> float:
    """Unabhaengige Enumeration: max ueber ALLE reinen Villain-Strategien s: (villain_combo, knoten) -> aktion.
    Nutzen-Konvention wie gpu_cfr (zentriert um -pot0/2). Sieht Heros Karte NIE (Strategie haengt nur von der
    eigenen Combo + oeffentlichem Knoten ab)."""
    vill_rolle = 1 - hero_rolle
    vill_knoten = [(p, n) for p, n in P.knoten_mit_pfad(baum) if n.actor == vill_rolle]
    def kompatibel(h, v):
        return not (set(h) & set(v)) and not (set(h) | set(v)) & set(board)

    def nutzen_villain(n, h, v, s_v, pfad):
        if n.terminal == "showdown":
            sh, sv = evaluate(board, list(h)), evaluate(board, list(v))     # treys: kleiner = besser
            return (n.sd_pot / 2.0) * (1.0 if sv < sh else -1.0 if sh < sv else 0.0)
        if n.terminal == "fold":
            eigen = n.invest[vill_rolle]
            return -(pot0 / 2.0 + eigen) if n.fold_von == vill_rolle else n.pot - (pot0 / 2.0 + eigen)
        if n.actor == vill_rolle:
            a = s_v[(v, pfad)]
            return nutzen_villain(n.kids[a], h, v, s_v, pfad + (n.acts[a],))
        sig = sigma[pfad][combo_index(*h)]
        return sum(float(sig[a]) * nutzen_villain(k, h, v, s_v, pfad + (lbl,))
                   for a, (lbl, k) in enumerate(zip(n.acts, n.kids)) if float(sig[a]) > 0)

    paare = sum(hero_w[h] * vill_w[v] for h in hero_c for v in vill_c if kompatibel(h, v))
    schluessel = [(v, p) for v in vill_c for p, _ in vill_knoten]
    wahl = [range(len(n.acts)) for v in vill_c for _, n in vill_knoten]
    best = -float("inf")
    for komb in itertools.product(*wahl):
        s_v = dict(zip(schluessel, komb))
        u = sum(hero_w[h] * vill_w[v] * nutzen_villain(baum, h, v, s_v, ())
                for h in hero_c for v in vill_c if kompatibel(h, v)) / paare
        best = max(best, u)
    return best


def test_brute_force_fixture() -> None:
    for seed, hero_rolle in ((11, 0), (12, 1), (13, 0), (14, 1)):
        board, hero_c, vill_c, hero_w, vill_w, spiel, baum, sigma = _fixture(seed, hero_rolle)
        wert_tensor, _ = P.br_gegen_fest(spiel, baum, sigma, 1 - hero_rolle)
        wert_brute = _brute_force_br(board, hero_c, vill_c, hero_w, vill_w, baum, sigma, hero_rolle, spiel.pot0)
        assert abs(wert_tensor - wert_brute) <= TOL, f"seed {seed} rolle {hero_rolle}: {wert_tensor} vs {wert_brute}"
        # w(pi_H) = -BR_V ist exakt das Negative
        assert abs(P.garantiewert(spiel, baum, sigma, hero_rolle) + wert_brute) <= TOL


# ---------------------------------------------------------------- 3. A/A == 0
def test_aa_null() -> None:
    board, hero_c, vill_c, hero_w, vill_w, spiel, baum, sigma = _fixture(21, 0)
    w1 = P.garantiewert(spiel, baum, sigma, 0)
    w2 = P.garantiewert(spiel, baum, {p: s.clone() for p, s in sigma.items()}, 0)
    assert abs(w1 - w2) <= 1e-6 and w1 == w2
    # ueber den echten Solve-Pfad: identische Politik A==B -> Delta E_H == 0 UND Delta R == 0 exakt
    rnd = random.Random(5)
    karten = rnd.sample(_DECK, 5)
    rest = [c for c in _DECK if c not in karten]
    combos = list(itertools.combinations(rest, 2))
    root = {"hand_id": 0, "provenienz": "fixture", "split": "test", "board": karten, "pot_river": 2000.0,
            "eff": 6000.0, "hero_oop": True, "hero_seat": 1, "button": 0,
            "ranges": {"hero_tracker": {c: 1.0 for c in rnd.sample(combos, 120)},
                       "vill_tracker": {c: 1.0 for c in rnd.sample(combos, 120)}, "hero_k1": None},
            "root_state": {}}
    e = P.bewerte_root(root, None, arm_a="identisch")
    assert e["status"] == "ok" and e["delta_e_h_bb"] == 0.0 and e["delta_regret_bb"] == 0.0, e
    assert e["L_bb"] <= e["U_bb"] + 1e-9, "Spielwert-Klammer: L <= U"


# ---------------------------------------------------------------- 4. Purify-Kontrolle (weich) am Clairvoyance-Toy
def test_purify_kontrolle() -> None:
    """Nuts/Air (IP) vs Bluffcatcher (OOP), Pot 100, eine Bet-Size (gpu_cfr._toy_clairvoyance): das Gleichgewicht
    ist ECHT gemischt (Bluff-Anteil 1/3, Call 1/2) -> die modale Politik muss mehr Sicherheit verlieren."""
    board = ["2c", "7d", "9h", "Jd", "Ks"]
    oop = {("Ah", "9s"): 1.0}
    nuts = [("Kh", "Kd"), ("Kh", "Kc"), ("Kd", "Kc")]
    air = [(q + s, r + s) for q, r in (("Q", "3"), ("Q", "4"), ("Q", "5")) for s in "shdc"]
    ip = {c: 1.0 for c in nuts + air}
    pot, eff = 100.0, 100.0
    baum = P.baue_baum(pot, eff, ((1.0,), (1.0,)), ((), ()), max_raises=0)
    cfr = P.CFRAufBaum(board, range_vector(oop), range_vector(ip), pot, baum)
    cfr.solve(iters=800)
    spiel = P.RiverSpiel(board, pot, range_vector(oop), range_vector(ip))
    for hero_rolle in (1, 0):
        sigma = P.sigma_aus_cfr(cfr, baum, hero_rolle)
        w_mix = P.garantiewert(spiel, baum, sigma, hero_rolle)
        w_pur = P.garantiewert(spiel, baum, P.purifiziere(sigma), hero_rolle)
        assert w_mix > w_pur + 1e-3, f"Rolle {hero_rolle}: purify verliert nicht ({w_mix} vs {w_pur})"
    # Spielwert-Klammer schliesst sich beim Gleichgewicht: L (IP garantiert) ~ U (IP-BR vs OOP-Solver)
    sig_ip, sig_oop = P.sigma_aus_cfr(cfr, baum, 1), P.sigma_aus_cfr(cfr, baum, 0)
    L = P.garantiewert(spiel, baum, sig_ip, 1)
    U, _ = P.br_gegen_fest(spiel, baum, sig_oop, 1)
    assert -1e-9 <= U - L < 1.0, f"Klammer [L,U] = [{L},{U}] (Pot 100) zu weit fuer 800 Iter"


# ---------------------------------------------------------------- 5. Baum-Struktur == gpu_cfr.build_river_tree
def _struktur(root):
    return [(p, n.actor, n.terminal, round(n.pot, 6), tuple(round(x, 6) for x in n.invest), n.sd_pot, n.fold_von)
            for p, n in P.knoten_mit_pfad(root)]


def test_baum_identisch_mit_gpu_cfr() -> None:
    for pot, eff in ((1916, 19042), (3060, 18470), (1500, 3000), (6000, 14000), (1000, 1000)):
        a = _struktur(build_river_tree(pot, eff))
        b = _struktur(P.baue_baum(pot, eff, (P.K2_BET_SIZES, P.K2_BET_SIZES), (P.K2_RAISE_SIZES, P.K2_RAISE_SIZES)))
        assert a == b, f"Baumstruktur weicht ab bei pot {pot} eff {eff}"
    # rollen-spezifisch: Hero-Zusatzarm 0.66 erscheint NUR an Hero-Knoten
    baum = P.baue_baum(2000, 10000, ((0.35, 0.66, 0.75, 1.5), P.K2_BET_SIZES), (P.K2_RAISE_SIZES, P.K2_RAISE_SIZES))
    for _, n in P.knoten_mit_pfad(baum):
        if n.actor == 1:
            assert "bet0.66" not in n.acts
    assert "bet0.66" in baum.acts


# ---------------------------------------------------------------- 6. Zustandsaufbau == Engine (game.act)
def test_zustand_nach_pfad_gegen_engine() -> None:
    from pokerbot.engine.game import HeadsUpGame
    from research.policy_oracle import zustand_nach_pfad
    g = HeadsUpGame(starting_stack=20000, sb=50, bb=100, seed=3)
    g.start_hand()
    g.act("raise", 300); g.act("call")
    g.act("bet", 400); g.act("call")
    g.act("check"); g.act("check")
    root_state = g.state()
    assert root_state["street"] == "river"
    oop = root_state["to_act"]
    pfad = [{"player": oop, "action": "bet", "to": 700}, {"player": 1 - oop, "action": "raise", "to": 2100}]
    g.act("bet", 700); g.act("raise", 2100)
    soll = g.state()
    ist = zustand_nach_pfad(root_state, pfad, oop)
    assert ist["pot"] == soll["pot"] and ist["current_bet"] == soll["current_bet"]
    for i in (0, 1):
        for k in ("stack", "committed_street", "committed_total"):
            assert ist["players"][i][k] == soll["players"][i][k], (k, ist["players"][i][k], soll["players"][i][k])
    for k in ("to_call", "can_check", "can_call", "can_raise", "is_bet", "raise_min", "raise_max"):
        assert ist["legal"][k] == soll["legal"][k], (k, ist["legal"][k], soll["legal"][k])


# ---------------------------------------------------------------- 7. Arm-Zuordnung (exakt, 1-Chip-Fenster)
_FIXTURE_ROOT_STATE = {"street": "river", "board": ["2c", "7d", "9h", "Jd", "Ks"], "pot": 2000, "bb": 100,
                       "current_bet": 0, "button": 1, "history": [], "to_act": 0,
                       "players": [{"idx": 0, "hole": ["Ah", "9s"], "stack": 10000, "committed_street": 0,
                                    "committed_total": 1000, "folded": False, "all_in": False, "is_button": False},
                                   {"idx": 1, "hole": ["??", "??"], "stack": 10000, "committed_street": 0,
                                    "committed_total": 1000, "folded": False, "all_in": False, "is_button": True}]}


def _k2_baum(pot=2000, eff=10000, zusatz_exakt=None):
    return P.baue_baum(pot, eff, (P.K2_BET_SIZES, P.K2_BET_SIZES), (P.K2_RAISE_SIZES, P.K2_RAISE_SIZES),
                       zusatz_exakt=zusatz_exakt)


def test_key_zu_arm() -> None:
    """Review-Befund HOCH (2026-09-07): 8 % Pot-Toleranz projizierte 0,67-Pot-Bets auf den 0,75-Arm. Jetzt gilt
    das 1-Chip-Fenster (Engine-Truncation); alles andere ist ein EXAKTER Zusatzarm, auch in der Jam-Kollaps-Zone."""
    from research.policy_oracle import zustand_nach_pfad
    baum = _k2_baum()
    st = zustand_nach_pfad(_FIXTURE_ROOT_STATE, [], 0)

    def arm(chips):
        return P.key_zu_arm(ActionKey.raise_to(chips), baum, 0, st, 0)
    idx, neu = arm(1500)                                                    # 0.75 Pot exakt
    assert baum.acts[idx] == "bet0.75" and neu is None
    for chips in (1499, 1501):                                              # 1-Chip-Fenster (int-Truncation)
        idx, neu = arm(chips)
        assert baum.acts[idx] == "bet0.75" and neu is None, (chips, idx, neu)
    assert arm(1498) == (None, ("exakt", 1498)), "2 Chips Abstand sind KEIN Treffer"
    assert arm(1340) == (None, ("exakt", 1340)), "0,67 Pot darf NICHT auf 0,75 Pot gesnappt werden (alter 8 %-Bug)"
    assert arm(1320) == (None, ("exakt", 1320))                             # 0.66 Pot: eigener Arm, keine Fraktion
    assert arm(9000) == (None, ("exakt", 9000)), "0,9 Reststack ist exakt darstellbar, kein Jam-Kollaps"
    idx, neu = arm(10000)                                                   # Jam = raise_max
    assert baum.acts[idx] == "betjam" and neu is None
    idx, neu = arm(9999)                                                    # raise_max - 1 Chip = Jam
    assert baum.acts[idx] == "betjam" and neu is None
    idx, _ = P.key_zu_arm(ActionKey.check(), baum, 0, st, 0)
    assert baum.acts[idx] == "check"
    # facing: 'Raise' um <= 1 Chip ueber den Call ist der Call (Truncation-Fenster; Pilot-Fund 2988445), 2 Chips nicht
    pfad_f = ("check", "bet0.75")
    n_f = P.knoten_am_pfad(baum, pfad_f)
    st_f = zustand_nach_pfad(_FIXTURE_ROOT_STATE, P.pfad_zu_aktionen(baum, pfad_f, 1, _FIXTURE_ROOT_STATE), 0)
    to_call = st_f["legal"]["to_call"]
    assert n_f.acts[P.key_zu_arm(ActionKey.raise_to(to_call + 1), n_f, 0, st_f, 0)[0]] == "call"
    assert P.key_zu_arm(ActionKey.raise_to(to_call + 2), n_f, 0, st_f, 0) == (None, ("exakt", to_call + 2))
    # PolicyTable -> Sigma: undefinierte Combo mit Range-Gewicht -> Unsupported
    tab = PolicyTable((ActionKey.check(), ActionKey.raise_to(1500)), ((("Ah", "9s"), (0.4, 0.6)),),
                      undefiniert=frozenset({("Ad", "9d")}), herkunft="oracle_seeds")
    r_h = range_vector({("Ah", "9s"): 1.0})
    sig, fehlend = P.tabelle_zu_sigma(tab, baum, 0, st, 0, r_h)
    assert abs(float(sig[combo_index("Ah", "9s")].sum()) - 1.0) < 1e-9 and not fehlend
    # 0,67-Pot-Bet mit Masse -> fehlend = exakter Betrag (frueher: still auf bet0.75 verbucht)
    tab67 = PolicyTable((ActionKey.check(), ActionKey.raise_to(1340)), ((("Ah", "9s"), (0.4, 0.6)),))
    sig, fehlend = P.tabelle_zu_sigma(tab67, baum, 0, st, 0, r_h)
    assert fehlend == {("exakt", 1340)} and float(sig[combo_index("Ah", "9s"), baum.acts.index("bet0.75")]) == 0.0
    try:
        P.tabelle_zu_sigma(tab, baum, 0, st, 0, range_vector({("Ah", "9s"): 1.0, ("Ad", "9d"): 1.0}))
        raise AssertionError("undefinierte Combo mit Gewicht muss Unsupported werfen")
    except P.Unsupported:
        pass


# ---------------------------------------------------------------- 8. Baum mit exakten Zusatzarmen je Knoten
def test_baum_exakte_zusatzarme() -> None:
    pfad_facing = ("check", "bet0.75")
    baum = _k2_baum(zusatz_exakt={(): {1340, 9000, 20000}, pfad_facing: {3450, 1500}})
    assert baum.acts == ["check", "bet0.35", "bet0.75", "bet1.5", "bet@1340", "bet@9000", "betjam"], baum.acts
    k = baum.kids[baum.acts.index("bet@1340")]
    assert k.invest[0] - baum.invest[0] == 1340.0, "Baum-Arm byte-gleich dem Oracle-Betrag"
    assert "bet@9000" in baum.acts, "Kollaps-Zone (>= 85 % Rest) ist fuer exakte Arme erlaubt"
    assert "bet@20000" not in baum.acts, "Zusatz >= Reststack IST der Jam"
    n = P.knoten_am_pfad(baum, pfad_facing)
    assert "raise@3450" in n.acts and "raise@1500" not in n.acts, (n.acts, "Raise <= to_call ist illegal")
    assert n.kids[n.acts.index("raise@3450")].invest[0] - n.invest[0] == 3450.0
    # exakte Arme NUR am genannten Knoten, nie bei IP oder an anderen Hero-Knoten
    for p, m in P.knoten_mit_pfad(baum):
        if p not in ((), pfad_facing):
            assert not any("@" in a for a in m.acts), (p, m.acts)
    assert sorted(P.zusatzarme(baum)) == [("check/bet0.75", "raise@3450"), ("root", "bet@1340"), ("root", "bet@9000")]
    # ohne Zusatzarme: Struktur unveraendert (Test 5 deckt die Identitaet zu build_river_tree)
    assert _struktur(_k2_baum()) == _struktur(_k2_baum(zusatz_exakt={}))


# ---------------------------------------------------------------- 9. Schliessung mit Off-Tree-Raise (Pilot-Bug)
OFFTREE_RAISE_FAKTOR = 2.3          # nicht im K2-Menue (2.7) -> muss als exakter Zusatzarm geschlossen werden


class _FakeOrakel:
    """Deterministische Arm-A-Politik der Hero-Combo: frei -> check; erste Bet -> 50 % fold / 50 % Raise 2,3x
    (off-tree); spaeter facing -> fold. Zaehlt die Abfragen (Cache-/Reach-Verhalten sichtbar)."""

    def __init__(self, combo):
        self.combo, self.abfragen = combo, 0

    def tabelle(self, root_hash, st, hs, combos=None):
        self.abfragen += 1
        self.letzte_combos = None if combos is None else [tuple(c) for c in combos]
        la, hero = st["legal"], st["players"][hs]
        hero_raises = sum(1 for h in st["history"] if h.get("player") == hs and h.get("action") in ("bet", "raise"))
        if la["to_call"] == 0:
            akt, probs = (ActionKey.check(),), (1.0,)
        elif la["can_raise"] and hero_raises == 0:
            chips = min(la["raise_max"], int(hero["committed_street"]) + int(OFFTREE_RAISE_FAKTOR * la["to_call"]))
            akt, probs = (ActionKey.fold(), ActionKey.raise_to(chips)), (0.5, 0.5)
        else:
            akt, probs = (ActionKey.fold(),), (1.0,)
        return PolicyTable(akt, ((self.combo, probs),), herkunft="oracle_seeds"), {"gueltig": True, "herkunft": {}}


def _fixture_root_offtree():
    combo = ("Ah", "9s")
    rest = [c for c in _DECK if c not in _FIXTURE_ROOT_STATE["board"] and c not in combo]
    vill = {(rest[i], rest[i + 1]): 1.0 for i in range(0, 40, 2)}
    root = {"hand_id": 1, "provenienz": "fixture", "split": "test", "board": _FIXTURE_ROOT_STATE["board"],
            "pot_river": 2000.0, "eff": 10000.0, "hero_oop": True, "hero_seat": 0, "button": 1, "root_hash": "fixture",
            "ranges": {"hero_tracker": {combo: 1.0}, "vill_tracker": vill, "hero_k1": None},
            "root_state": _FIXTURE_ROOT_STATE}
    return combo, vill, root


def test_schliessung_offtree_raise() -> None:
    """Off-Tree-Betrag MIT Masse muss als SCHLIESSBAR gemeldet werden (nicht 'unmappbar' — der Pilot-Bug
    smoke_oracle_root1 brach dort mit UNSUPPORTED ab) und die Schliessungsschleife muss in Runde 2 mit EXAKTEN
    Zusatzarmen (Chips, keine Fraktion) konvergieren."""
    from research.policy_oracle import zustand_nach_pfad
    combo, vill, root = _fixture_root_offtree()
    root_state = root["root_state"]
    baum = _k2_baum()
    # (a) tabelle_zu_sigma: facing bet0.75 (Villain-Bet 1500), Raise auf 2,3 x 1500 = 3450 -> ('exakt', 3450)
    pfad = ("check", "bet0.75")
    n = P.knoten_am_pfad(baum, pfad)
    st = zustand_nach_pfad(root_state, P.pfad_zu_aktionen(baum, pfad, 1, root_state), 0)
    # Fixture-Betraege wie der Fake-Oracle sie rechnet: int(2.3 x to_call) = 3449 (2.3*1500 = 3449.99.. in float) —
    # die exakte Schliessung muss GENAU diesen Chip-Betrag tragen, keine Rundung auf 3450 oder eine Fraktion
    raise_75 = int(OFFTREE_RAISE_FAKTOR * 1500)
    assert raise_75 == 3449
    tab = PolicyTable((ActionKey.fold(), ActionKey.raise_to(raise_75)), ((combo, (0.5, 0.5)),))
    sig, fehlend = P.tabelle_zu_sigma(tab, n, 0, st, 0, range_vector({combo: 1.0}))
    assert fehlend == {("exakt", raise_75)}, fehlend
    assert float(sig[combo_index(*combo)].sum()) == 0.5, "nur die fold-Masse ist im K2-Baum darstellbar"
    # (b) Schliessungsschleife: Runde 2 traegt die exakten Raises (2,3 x 700 / 1500 / 3000) als Hero-Arme
    r_hero, r_vill = range_vector({combo: 1.0}), range_vector(vill)
    spiel = P.RiverSpiel(root_state["board"], 2000.0, r_hero, r_vill)
    orakel = _FakeOrakel(combo)
    baum_eval, sigma_a, meta = P.sigma_arm_a(orakel, root, spiel, r_hero, 0)
    assert meta["runden"] == 2, meta
    assert orakel.letzte_combos is not None and {combo_index(*c) for c in orakel.letzte_combos} == {combo_index(*combo)},         "der Pruefstand fragt den Oracle NUR fuer Combos mit Hero-Reach > 0 an"
    soll = {"check/bet0.35": [int(OFFTREE_RAISE_FAKTOR * 700)], "check/bet0.75": [raise_75],
            "check/bet1.5": [int(OFFTREE_RAISE_FAKTOR * 3000)]}
    assert meta["zusatz_exakt"] == soll, meta
    assert meta["n_zusatz_arme"] == 3
    n_eval = P.knoten_am_pfad(baum_eval, pfad)
    lbl = P.exakt_label("raise", raise_75)
    assert lbl in n_eval.acts
    assert n_eval.kids[n_eval.acts.index(lbl)].invest[0] - n_eval.invest[0] == float(raise_75)
    assert float(sigma_a[pfad][combo_index(*combo), n_eval.acts.index(lbl)]) == 0.5
    w = P.garantiewert(spiel, baum_eval, sigma_a, 0)
    assert math.isfinite(w) and orakel.abfragen > 0
    # Hero-Knoten nach dem Off-Tree-Raise (Villain re-raist) sind jetzt abgefragt und fold-1.0 belegt
    tiefe = [p for p in sigma_a if len(p) >= 3]
    assert tiefe, "nach der Schliessung muessen Hero-Knoten hinter dem exakten Raise existieren"


# ---------------------------------------------------------------- 10. Arm B auf dem Evaluationsbaum (BLOCKER)
def test_sigma_b_auf_evaluationsbaum() -> None:
    """Review-BLOCKER (2026-09-07): sigma_B (K2-Spalten) wurde ungemappt auf baum_eval (K2 + Zusatzarme) bewertet
    -> Spalten-Verschiebung, Unsupported in garantiewert, IndexError in lokaler_regret. Die Abbildung per Label
    muss den Wert EXAKT erhalten (ungenutzte Zusatzarme addieren 0) und der Regret endlich sein."""
    rnd = random.Random(5)
    karten = rnd.sample(_DECK, 5)
    rest = [c for c in _DECK if c not in karten]
    combos = list(itertools.combinations(rest, 2))
    r_h = range_vector({c: 1.0 for c in rnd.sample(combos, 120)})
    r_v = range_vector({c: 1.0 for c in rnd.sample(combos, 120)})
    pot, eff = 2000.0, 6000.0
    spiel = P.RiverSpiel(karten, pot, r_h, r_v)
    k2 = _k2_baum(pot, eff)
    cfr = P.CFRAufBaum(karten, r_h, r_v, pot, k2)
    cfr.solve(iters=50)
    sigma_b = P.sigma_aus_cfr(cfr, k2, 0)
    w_k2 = P.garantiewert(spiel, k2, sigma_b, 0)
    eval_baum = _k2_baum(pot, eff, zusatz_exakt={(): {1320}, ("check", "bet0.75"): {3450}})
    assert eval_baum.acts != k2.acts, "Fixture: der Evaluationsbaum hat einen Zusatzarm an der Wurzel"
    # Negativ-Kontrolle: ungemappt bricht es genau so, wie der Reviewer es gemessen hat
    try:
        P.garantiewert(spiel, eval_baum, sigma_b, 0)
        raise AssertionError("ungemapptes sigma_B auf baum_eval darf nicht still durchlaufen")
    except (P.Unsupported, IndexError):
        pass
    sigma_b_eval = P.sigma_auf_baum(sigma_b, k2, eval_baum, 0)
    assert set(sigma_b_eval) == {p for p, n in P.knoten_mit_pfad(eval_baum) if n.actor == 0}
    for p, n in P.knoten_mit_pfad(eval_baum):
        if n.actor == 0:
            assert sigma_b_eval[p].shape[1] == len(n.acts)
            for j, a in enumerate(n.acts):
                if "@" in a:
                    assert float(sigma_b_eval[p][:, j].abs().sum()) == 0.0, "Zusatzarme tragen Masse 0"
    w_eval = P.garantiewert(spiel, eval_baum, sigma_b_eval, 0)
    assert w_eval == w_k2, f"w_B muss exakt erhalten bleiben: {w_eval} vs {w_k2}"
    cfr_q = P.CFRAufBaum(karten, r_h, r_v, pot, eval_baum)
    cfr_q.solve(iters=20)
    r_b, _ = P.lokaler_regret(cfr_q, eval_baum, spiel, sigma_b_eval, 0)
    assert math.isfinite(r_b) and r_b >= -1e-9, r_b
    # Quellarme ohne Zielarm (Masse ginge verloren) -> Unsupported statt stiller Verlust
    schmal = P.baue_baum(pot, eff, ((0.75,), P.K2_BET_SIZES), (P.K2_RAISE_SIZES, P.K2_RAISE_SIZES))
    try:
        P.sigma_auf_baum(sigma_b, k2, schmal, 0)
        raise AssertionError("fehlende Zielarme muessen Unsupported werfen")
    except P.Unsupported:
        pass


def test_bewerte_root_oracle_mit_schliessung() -> None:
    """E2E durch bewerte_root (Arm A = Oracle mit Off-Tree-Raise, ergo Zusatzarme): Status ok, w_B(eval) == w_B(K2)
    exakt (Selbstkontrolle im Report), Regret B endlich. Vor dem Fix: UNSUPPORTED bzw. IndexError-Crash."""
    combo, vill, root = _fixture_root_offtree()
    e = P.bewerte_root(root, _FakeOrakel(combo), arm_a="oracle")
    assert e["status"] == "ok", e
    assert e["n_zusatz_arme"] == 3 and e["arm_a_meta"]["runden"] == 2, e["arm_a_meta"]
    assert e["w_b_bb"] == e["w_b_k2_bb"], (e["w_b_bb"], e["w_b_k2_bb"])
    for k in ("w_a_bb", "delta_e_h_bb", "regret_a_bb", "regret_b_bb", "delta_regret_bb"):
        assert math.isfinite(e[k]), (k, e[k])
    assert e["L_bb"] <= e["U_bb"] + 1e-9
    agg = P.aggregiere([e], n_haende=10, n_roots_ge_schwelle=1)
    assert agg["zusatz_arme_gesamt"] == 3 and agg["roots_mit_zusatzarmen"] == 1
    assert agg["max_abw_w_b_eval_vs_k2_bb"] == 0.0


# ---------------------------------------------------------------- 12. Policy-Oracle: Chirurgie-Regel pur == river_gpu_guard
def _echter_root(hand_id: int) -> dict:
    """Ein Entwicklungs-Root aus data/runs/v10/k3_roots_entwicklung.jsonl (lokales Artefakt; Fehlermeldung nennt
    das Kommando, das es erzeugt)."""
    from research.k3_roots import ausgabe_pfad, lade_roots
    assert ausgabe_pfad("entwicklung").exists(), "k3_roots fehlt: python -m research.k3_roots --split entwicklung"
    _, roots = lade_roots("entwicklung", min_pot=1500)
    return next(r for r in roots if r["hand_id"] == hand_id)


def test_chirurgie_pur_gleich_river_gpu_guard() -> None:
    """policy_oracle.chirurgie(basis, res) muss improver.river_gpu_guard byte-gleich nachbilden: derselbe Wrapper mit
    gepatchtem solve_spots (kanonisches Ergebnis) um eine Basis mit fester Aktion, an einem echten River-State mit
    pot >= 3000 (Guard aktiv) und < 3000 (inaktiv), fuer alle Ueberschreib-Zweige und den Mischfall."""
    from pokerbot.autogym import improver
    from pokerbot.strategy import gpu_resolver
    from research import policy_oracle as PO
    root = _echter_root(2990016)                                   # OOP, pot 3060 -> Guard am ersten Knoten aktiv
    hs = root["hero_seat"]
    st_frei = PO.mit_hole(PO.erster_hero_knoten(root), hs, ("5s", "8s"))
    st_facing = PO.mit_hole(PO.zustand_nach_pfad(root["root_state"], [
        {"player": hs, "action": "check"}, {"player": 1 - hs, "action": "bet", "to": 2295}], hs), hs, ("5s", "8s"))
    st_klein = dict(st_frei); st_klein["pot"] = 2999                 # unter der Schwelle: Guard darf nichts tun
    frei_acts, facing_acts = ["check", "bet0.35", "bet0.75", "bet1.5", "betjam"], ["fold", "call", "raise2.7", "raisejam"]
    faelle = [  # (state, basis, sigma) — Solver-Verdikt klar (p_basis < 0.10, p_alt > 0.70) oder gemischt
        (st_frei, ("bet", 2295), [0.95, 0.02, 0.02, 0.01, 0.0]),        # bet -> check
        (st_frei, ("check", None), [0.05, 0.05, 0.85, 0.05, 0.0]),      # check -> bet int(0.75*pot)
        (st_frei, ("check", None), [0.05, 0.05, 0.05, 0.05, 0.80]),     # check -> jam-Arm startet mit 'bet' -> bet 0.75 pot
        (st_frei, ("bet", 1010), [0.30, 0.30, 0.30, 0.10, 0.0]),        # gemischt -> Basis bleibt
        (st_frei, ("check", None), [0.60, 0.10, 0.30, 0.0, 0.0]),       # p_alt <= 0.70 -> Basis bleibt
        (st_facing, ("call", None), [0.96, 0.02, 0.02, 0.0]),           # call -> fold
        (st_facing, ("fold", None), [0.05, 0.90, 0.05, 0.0]),           # fold -> call
        (st_facing, ("raise", 6000), [0.05, 0.85, 0.05, 0.05]),         # raise -> call
        (st_facing, ("call", None), [0.09, 0.05, 0.86, 0.0]),           # call -> alt raise: kein Zweig -> Basis bleibt
        (st_klein, ("bet", 2295), [0.95, 0.02, 0.02, 0.01, 0.0]),       # pot < 3000: Basis bleibt
    ]
    orig = gpu_resolver.solve_spots
    try:
        for st, basis, sig in faelle:
            acts = frei_acts if st["current_bet"] == 0 else facing_acts
            res = {"acts": acts, "sigma": sig, "zusatz_norm": [0.0] * len(acts), "expl": 0.0, "gespielt": "x", "tag": None}
            gpu_resolver.solve_spots = lambda spots, iters=None, **kw: [res for _ in spots]
            guard = improver.river_gpu_guard(lambda seat: (lambda s: basis))(hs)
            soll = guard(st)
            ist = PO.chirurgie(basis[0], basis[1], st, res)
            assert soll == ist, (basis, sig, soll, ist)
    finally:
        gpu_resolver.solve_spots = orig
    # der Guard laesst die Basis unveraendert, wenn der Spot nicht baubar ist (res None)
    assert PO.chirurgie("bet", 2295, st_frei, None) == ("bet", 2295)
    assert PO.chirurgie("bet", 2295, st_frei, {"acts": frei_acts, "sigma": [0.95, 0.02, 0.02, 0.01, 0.0]}) == ("check", None)


def test_combo_index_inverse_und_reach_maske() -> None:
    from research import policy_oracle as PO
    for i, c in PO.COMBO_VON_INDEX.items():
        assert combo_index(*c) == i
    assert len(PO.COMBO_VON_INDEX) == 1326
    vec = range_vector({("Ah", "9s"): 0.4, ("2c", "3c"): 0.0, ("Kd", "Qd"): 1.0})
    assert {combo_index(*c) for c in PO.combos_mit_masse(vec)} == {combo_index("Ah", "9s"), combo_index("Kd", "Qd")}


# ---------------------------------------------------------------- 13. IDENTITAET: gebatchter Oracle == volle r8_stack-Kette
CHIRURGIE_COMBOS_2990016 = (("5s", "8s"), ("5s", "9h"), ("5h", "8d"), ("5s", "8c"), ("5h", "9c"), ("5s", "9d"))
"""Combos, bei denen der GPU-Guard am ersten Knoten von Root 2990016 die Basis-Bet (raise_to:1530) zu check
ueberschreibt (Vollknoten-Analyse 2026-09-07: 62 von 2162 (Combo,Seed)-Entscheidungen, alle bet->check)."""


def test_oracle_identitaet_gegen_r8_stack() -> None:
    """Pflichttest der Fix-Runde: fuer >= 12 zufaellige Combos x 2 Seeds an 2 Roots liefert der GEBATCHTE Oracle
    (Basis r7_wert + Chirurgie aus EINEM solve_spots-Batch) exakt dieselbe finale Aktion wie der DIREKTE decide()-
    Aufruf der vollen r8_stack-Kette (Guard mit eigenem B=1-Solve). Drei Knoten: Root 2990016 erster Knoten
    (pot 3060, Guard aktiv; 6 Chirurgie-Combos + 6 zufaellige), Root 2988445 erster Knoten (pot 1916, Guard inaktiv,
    12 zufaellige) und Root 2988445 nach Villain-Bet 0,75 Pot (pot 3353, Guard aktiv, 6 zufaellige). Frischer Cache
    (Temp), damit der Batch-Pfad wirklich laeuft. Laufzeit-Budget < 3 min (Direktkette: ~2,4 s je B=1-Solve)."""
    import tempfile
    import time
    from research import policy_oracle as PO
    t_start = time.perf_counter()
    r_a, r_b = _echter_root(2990016), _echter_root(2988445)
    hs_a, hs_b = r_a["hero_seat"], r_b["hero_seat"]
    st_a = PO.erster_hero_knoten(r_a)
    st_b1 = PO.erster_hero_knoten(r_b)
    st_b2 = PO.zustand_nach_pfad(r_b["root_state"], [{"player": 1 - hs_b, "action": "bet", "to": 1437}], hs_b)
    assert st_a["pot"] >= PO.GPU_GUARD_MIN_POT and st_b2["pot"] >= PO.GPU_GUARD_MIN_POT > st_b1["pot"]
    rnd = random.Random(11)
    frei_a = [c for c in PO.lebende_combos(st_a["board"])
              if combo_index(*c) not in {combo_index(*x) for x in CHIRURGIE_COMBOS_2990016}]
    knoten = [(r_a, st_a, hs_a, list(CHIRURGIE_COMBOS_2990016) + rnd.sample(frei_a, 6)),
              (r_b, st_b1, hs_b, rnd.sample(PO.lebende_combos(st_b1["board"]), 12)),
              (r_b, st_b2, hs_b, rnd.sample(PO.lebende_combos(st_b2["board"]), 6))]
    seeds = (1, 2)
    oracle = PO.PolicyOracle("gym", seeds=len(seeds), workers=4, cache_dir=tempfile.mkdtemp(prefix="oc_ident_"))
    treffer = n = chirurgie = 0
    try:
        for root, st, hs, combos in knoten:
            tab, meta = oracle.tabelle(root["root_hash"], st, hs, combos=combos)
            assert meta["gueltig"] and not meta["fehler"], meta
            roh = oracle.roh(root["root_hash"], st, combos)
            direkt = oracle.direkt(st, hs, combos, seeds)
            for c in combos:
                ck = PO.combo_kanonisch(*c)
                eintraege = roh[ck]
                assert len(eintraege) == len(seeds), (c, eintraege)
                for kennung, key, basis in eintraege:
                    n += 1
                    chirurgie += key != basis
                    if direkt[(ck, int(kennung))] == key:
                        treffer += 1
                    else:
                        print(f"  ABWEICHUNG {root['hand_id']} {c} seed {kennung}: oracle {key} (basis {basis}) "
                              f"direkt {direkt[(ck, int(kennung))]}")
                # die Tabelle ist exakt die Haeufigkeit der Roh-Entscheidungen
                vert = tab.verteilung(ck)
                for k in tab.aktionen:
                    kstr = k.kind if k.chips is None else f"raise_to:{k.chips}"
                    soll = sum(1 for _, key, _ in eintraege if key == kstr) / len(seeds)
                    assert abs(vert[k] - soll) < 1e-12, (c, k, vert[k], soll)
    finally:
        oracle.schliessen()
    dauer = time.perf_counter() - t_start
    print(f"  Identitaet gebatchter Oracle vs r8_stack: {treffer}/{n} (Combo,Seed) identisch, davon {chirurgie} mit "
          f"Chirurgie-Ueberschreibung; GPU-Batch {PO.GPU_BATCH_MAX}; {dauer:.0f}s")
    assert treffer == n, f"{n - treffer} Abweichungen"
    assert chirurgie >= 1, "der Test muss mindestens eine Chirurgie-Ueberschreibung enthalten (sonst prueft er den Guard nicht)"
    assert n >= 24


# ---------------------------------------------------------------- 14. Exakter Jam an raise-gekappten Knoten (Pilot-Fund)
def test_jam_an_raise_gekapptem_knoten() -> None:
    """Pilot pilot_oracle_gebatcht_S2 (2026-09-07): Root 2988445 UNSUPPORTED 'unmappbar raise_to 19042' — Arm A geht
    nach zwei Raises all-in, der K2-Baum (max_raises=2) bietet dort nur fold/call. Die Schliessung muss den exakten
    Jam-Arm einziehen (Villain danach nur fold/call), key_zu_arm ihn als ('exakt', Rest) melden und danach treffen."""
    from research.policy_oracle import zustand_nach_pfad
    pot, eff = 2000.0, 10000.0
    baum = _k2_baum(pot, eff)
    # Hero OOP: bet0.75 (1500) -> Villain raise2.7 (Zusatz 4050 -> to 5550) -> Hero raise2.7 -> Villain raise?
    # max_raises=2: nach zwei Raises ist der Knoten gekappt. Pfad: bet0.75 / raise2.7 / raise2.7 -> Villain-Knoten
    # (Rolle 1) gekappt; wir brauchen einen HERO-Knoten (Rolle 0) mit Kappung: check / bet0.75(V) / raise2.7(H) /
    # raise2.7(V) -> Hero facing, n_raises = 2 -> nur fold/call.
    pfad = ("check", "bet0.75", "raise2.7", "raise2.7")
    n = P.knoten_am_pfad(baum, pfad)
    assert n.actor == 0 and n.acts == ["fold", "call"], n.acts
    st = zustand_nach_pfad(_FIXTURE_ROOT_STATE, P.pfad_zu_aktionen(baum, pfad, 1, _FIXTURE_ROOT_STATE), 0)
    assert st["legal"]["can_raise"]
    jam_to = st["legal"]["raise_max"]
    idx, neu = P.key_zu_arm(ActionKey.raise_to(jam_to), n, 0, st, 0)
    rest = int(jam_to - st["players"][0]["committed_street"])
    assert idx is None and neu == ("exakt", rest), (idx, neu)
    baum2 = _k2_baum(pot, eff, zusatz_exakt={pfad: {rest}})
    n2 = P.knoten_am_pfad(baum2, pfad)
    assert n2.acts == ["fold", "call", P.JAM_EXAKT_LABEL], n2.acts
    kind = n2.kids[n2.acts.index(P.JAM_EXAKT_LABEL)]
    assert kind.actor == 1 and kind.acts == ["fold", "call"], "Villain nach dem Jam: nur fold/call (terminal)"
    assert abs((kind.invest[0] - n2.invest[0]) - rest) <= P.SIZE_TOL_CHIPS
    idx2, neu2 = P.key_zu_arm(ActionKey.raise_to(jam_to), n2, 0, st, 0)
    assert n2.acts[idx2] == P.JAM_EXAKT_LABEL and neu2 is None
    P._pruefe_zusatzarme(baum2, {pfad: {rest}}, 0)                  # der Jam-Zusatz gilt als vorhanden
    assert (("/".join(pfad), P.JAM_EXAKT_LABEL) in P.zusatzarme(baum2))
    # Arm B (K2-Baum) auf den erweiterten Baum: der Jam-Arm traegt Masse 0, Werte bleiben exakt
    rnd = random.Random(9)
    rest_deck = [c for c in _DECK if c not in _FIXTURE_ROOT_STATE["board"]]
    combos = list(itertools.combinations(rest_deck, 2))
    r_h, r_v = range_vector({c: 1.0 for c in rnd.sample(combos, 80)}), range_vector({c: 1.0 for c in rnd.sample(combos, 80)})
    spiel = P.RiverSpiel(_FIXTURE_ROOT_STATE["board"], pot, r_h, r_v)
    cfr = P.CFRAufBaum(_FIXTURE_ROOT_STATE["board"], r_h, r_v, pot, baum)
    cfr.solve(iters=30)
    sigma_b = P.sigma_aus_cfr(cfr, baum, 0)
    sigma_b2 = P.sigma_auf_baum(sigma_b, baum, baum2, 0)
    assert P.garantiewert(spiel, baum2, sigma_b2, 0) == P.garantiewert(spiel, baum, sigma_b, 0)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    tests = [test_matching_pennies, test_brute_force_fixture, test_aa_null, test_purify_kontrolle,
             test_baum_identisch_mit_gpu_cfr, test_zustand_nach_pfad_gegen_engine, test_key_zu_arm,
             test_baum_exakte_zusatzarme, test_schliessung_offtree_raise, test_sigma_b_auf_evaluationsbaum,
             test_bewerte_root_oracle_mit_schliessung, test_chirurgie_pur_gleich_river_gpu_guard,
             test_combo_index_inverse_und_reach_maske, test_jam_an_raise_gekapptem_knoten,
             test_oracle_identitaet_gegen_r8_stack]
    for t in tests:
        t()
        print(f"  {t.__name__}: OK")
    print(f"test_river_br_pruefstand: {len(tests)}/{len(tests)} gruen (Device {DEVICE})")
