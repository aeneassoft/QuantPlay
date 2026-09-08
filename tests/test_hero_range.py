"""G1-Invarianten fuer K1 (pokerbot/strategy/hero_range.py; Karte docs/V10_BUILD_CARD.md K1-Abnahme):
Σ=1 (1e-6) · Board-Combos exakt 0 · Invarianz gegen Heros echte Hand · Guard-Transformation vs explizite
Enumeration (≤1e-6) · Massenerhaltung · C(h) BITGENAU gegen den echten improver-Guard (E6) · beide Kanaele
(Engine-History UND gtow_to_state-Form) · Replay-Buchhaltung == Engine · Tracker-Paritaet · p_defense_batch-
Identitaet (E11). Run: python -m pytest tests/test_hero_range.py -q   oder   python -m tests.test_hero_range
"""
from __future__ import annotations

import random
import sys

from pokerbot.autogym.improver import sel_guard, turn_wert_guard
from pokerbot.engine.game import HeadsUpGame
from pokerbot.strategy import advisor
from pokerbot.strategy import hero_range as hr
from pokerbot.strategy.contracts import ActionKey, PolicyTable, RangeState, combo_kanonisch
from pokerbot.strategy.range_tracker import WEIGHT_FLOOR, RangeTracker, _board_at

START, SB, BB = 20000, 50, 100
TOL = 1e-6


# ---------------------------------------------------------------- Fixtures: eine Linie, zwei Kanaele
def _engine_hand(hole0=("Ah", "Kd"), hole1=("9c", "9d"), board=("8c", "Ac", "2h", "As", "Kc")):
    """Engine-Kanal: BTN(0) opent 300, BB(1) callt; Flop BB check / BTN bet 400 / BB call; Turn BB check /
    BTN bet int(0.66*pot) = b* (der turn_wert-Zielbetrag) / BB call; River-Deal. Liefert (st0 am River-Beginn,
    alle Engine-States vor jeder Aktion)."""
    g = HeadsUpGame(starting_stack=START, sb=SB, bb=BB, seed=3)
    g.start_hand()
    g.players[0].hole, g.players[1].hole = list(hole0), list(hole1)
    g.deck.cards = list(reversed(list(board)))
    states = []
    for a, amt in (("raise", 300), ("call", None), ("check", None), ("bet", 400), ("call", None),
                   ("check", None), ("bet", None), ("call", None)):
        st = g.state()
        states.append(st)
        if a == "bet" and amt is None:
            amt = int(hr.TURN_WERT_FRAC * st["pot"])
        g.act(a, amt)
    st0 = g.state()
    assert st0["street"] == "river"
    return st0, states


def _adapter_hand(hole0=("Ah", "Kd"), board=("8c", "Ac", "2h", "As", "Kc")):
    """Adapter-Kanal (gtow_to_state-Form, V10_FAKTEN A2): dieselbe Linie — call OHNE amount, deal OHNE board,
    `to` als float, hand_id, Villain '??'."""
    pot_turn = 1400
    b_star = float(int(hr.TURN_WERT_FRAC * pot_turn))
    hist = [
        {"player": 0, "action": "raise", "street": "preflop", "to": 300.0}, {"player": 1, "action": "call", "street": "preflop"},
        {"action": "deal", "street": "flop"},
        {"player": 1, "action": "check", "street": "flop"}, {"player": 0, "action": "bet", "street": "flop", "to": 400.0},
        {"player": 1, "action": "call", "street": "flop"},
        {"action": "deal", "street": "turn"},
        {"player": 1, "action": "check", "street": "turn"}, {"player": 0, "action": "bet", "street": "turn", "to": b_star},
        {"player": 1, "action": "call", "street": "turn"},
        {"action": "deal", "street": "river"},
    ]
    ct = 700 + int(b_star)
    return {
        "street": "river", "board": list(board), "pot": 2 * ct, "bb": BB, "current_bet": 0, "button": 0,
        "hand_id": 4711, "hand_no": 0, "to_act": 1, "hand_over": False, "history": hist,
        "players": [
            {"idx": 0, "hole": list(hole0), "stack": START - ct, "committed_street": 0, "committed_total": ct,
             "folded": False, "all_in": False, "is_button": True},
            {"idx": 1, "hole": ["??", "??"], "stack": START - ct, "committed_street": 0, "committed_total": ct,
             "folded": False, "all_in": False, "is_button": False},
        ],
        "legal": {"to_act": 1, "to_call": 0, "pot": 2 * ct, "can_fold": False, "can_check": True, "can_call": False,
                  "call_amount": 0, "can_raise": True, "is_bet": True, "raise_min": 100, "raise_max": START - ct},
    }


def _tv(a: dict, b: dict) -> float:
    return 0.5 * sum(abs(a.get(c, 0.0) - b.get(c, 0.0)) for c in set(a) | set(b))


def _maxdiff(a: dict, b: dict) -> float:
    return max(abs(a.get(c, 0.0) - b.get(c, 0.0)) for c in set(a) | set(b))


# ---------------------------------------------------------------- 1. Σ=1, Board 0, Status, RangeState
def test_summe_board_status_engine():
    st0, _ = _engine_hand()
    for hero in (0, 1):
        rek = hr.rekonstruiere(st0, hero=hero)
        assert rek.status == hr.STATUS_OK, rek.grund
        assert abs(sum(rek.hero_range.values()) - 1.0) <= TOL
        board = set(st0["board"])
        assert all(c[0] not in board and c[1] not in board for c in rek.hero_range), "Board-Combo mit Gewicht"
        assert all(w > 0 for w in rek.hero_range.values())
        assert all(c == combo_kanonisch(*c) for c in rek.hero_range), "Schluessel nicht kanonisch"
        assert rek.pot_river == 2 * (700 + int(hr.TURN_WERT_FRAC * 1400))
        rs = rek.range_state(st0["board"])                       # contracts validiert Σ=1 + Board=0 hart
        assert isinstance(rs, RangeState) and rs.herkunft == "k1_likelihood" and not rs.hero_injiziert
        assert rs.hero_rolle == "initiative"
    # Hero 1 (BB) hat einen sel_m15-Knoten (Flop-Call facing Bet) UND einen turn_wert-Knoten (Turn-Check)
    rek1 = hr.rekonstruiere(st0, hero=1)
    guards = [k.guard for k in rek1.knoten]
    assert hr.GUARD_SEL_FLOP in guards and hr.GUARD_TURN_WERT in guards
    # Hero 0 (BTN) bettet am Turn EXAKT b* -> Groessenvergleich ueber Chips trifft
    rek0 = hr.rekonstruiere(st0, hero=0)
    turn = [k for k in rek0.knoten if k.guard == hr.GUARD_TURN_WERT]
    assert len(turn) == 1 and turn[0].ziel_getroffen is True and turn[0].guard_ziel == "raise_to(924)"


def test_kein_river_deal_ist_fehlgeschlagen_und_fremde_guards_werfen():
    st0, states = _engine_hand()
    rek = hr.rekonstruiere(states[-1], hero=1)                   # Turn-State: kein River-Deal
    assert rek.status == hr.STATUS_FEHLGESCHLAGEN and rek.hero_range == {}
    assert hr.hero_range_river_start(states[-1], hero=1) == {}
    try:
        hr.rekonstruiere(st0, guards=("river_gpu",), hero=1)
    except ValueError:
        pass
    else:
        raise AssertionError("unbekannter Guard muss ValueError werfen")


# ---------------------------------------------------------------- 2. Invarianz gegen Heros echte Hand
def test_invarianz_gegen_hero_hole():
    st_a, _ = _engine_hand(hole0=("Ah", "Kd"), hole1=("9c", "9d"))
    st_b, _ = _engine_hand(hole0=("7d", "3s"), hole1=("Qh", "Jd"))
    for hero in (0, 1):
        ra = hr.rekonstruiere(st_a, hero=hero)
        rb = hr.rekonstruiere(st_b, hero=hero)
        assert ra.hero_range and _maxdiff(ra.hero_range, rb.hero_range) <= TOL
        assert _maxdiff(ra.villain_range, rb.villain_range) <= TOL
    # kein Knoten-Zustand traegt eine Hole-Karte
    for k in hr.knoten_liste(st_a, 1):
        assert all(p["hole"] == ["??", "??"] for p in k.zustand["players"])


# ---------------------------------------------------------------- 3. Beide Kanaele identisch
def test_engine_und_adapter_kanal_identisch():
    st_e, _ = _engine_hand()
    st_a = _adapter_hand()
    assert st_e["pot"] == st_a["pot"]
    for hero in (0, 1):
        re_ = hr.rekonstruiere(st_e, hero=hero)
        ra = hr.rekonstruiere(st_a, hero=hero)
        assert re_.status == ra.status == hr.STATUS_OK
        assert _maxdiff(re_.hero_range, ra.hero_range) <= TOL
        assert _maxdiff(re_.villain_range, ra.villain_range) <= TOL
        assert [k.beobachtet for k in re_.knoten] == [k.beobachtet for k in ra.knoten]
    assert hr.knoten_liste(st_a, 1)[0].zustand["hand_id"] == 4711


# ---------------------------------------------------------------- 4. Replay-Buchhaltung == Engine
def test_replay_zustaende_gleichen_engine_states():
    st0, states = _engine_hand()
    oeffentlich = ("street", "board", "pot", "current_bet", "to_act", "button")
    for hero in (0, 1):
        for k in hr.knoten_liste(st0, hero):
            eng = next(s for s in states if len(s["history"]) == k.index)
            assert eng["to_act"] == hero
            for f in oeffentlich:
                assert k.zustand[f] == eng[f], f
            for s in (0, 1):
                for f in ("stack", "committed_street", "committed_total", "all_in"):
                    assert k.zustand["players"][s][f] == eng["players"][s][f], (s, f)
            for f in ("to_call", "can_check", "can_call", "can_raise", "is_bet", "raise_min", "raise_max"):
                assert k.zustand["legal"][f] == eng["legal"][f], f
            assert k.beobachtet == hr.kanonisiere_history_eintrag(st0["history"][k.index])


# ---------------------------------------------------------------- 5. Tracker-Paritaet (guards=(), Tracker-Konvention)
def test_tracker_paritaet_ohne_guards():
    st0, _ = _engine_hand()
    t = RangeTracker().build(hr.schneide_am_river(st0))
    for hero in (0, 1):
        par = hr.rekonstruiere(st0, guards=(), hero=hero, konvention=hr.TRACKER_PARITAET)
        tr = {combo_kanonisch(*c): w for c, w in t.range[hero].items()}
        assert _maxdiff(par.hero_range, tr) <= 1e-12, "K1 ohne Guards muss die Tracker-Hero-Range reproduzieren"
        vill = hr.villain_range_river_start(st0, hero=hero)
        assert vill == t.range[1 - hero]


# ---------------------------------------------------------------- 6. C(h) BITGENAU gegen den echten Guard (E6)
def _dummy(aktion):
    return lambda seat: (lambda st: (aktion, None))


def test_bedingung_turn_wert_bitgenau_gegen_improver_guard():
    st0, _ = _engine_hand()
    k = next(k for k in hr.knoten_liste(st0, 1) if k.street == "turn")      # BB checkt den Turn
    vill = hr._villain_range_am_knoten(k.zustand, 1, None)
    guard = turn_wert_guard(_dummy("check"))(1)
    rng = random.Random(11)
    combos = rng.sample(hr.lebende_combos(k.zustand["board"]), 80)
    combos += [("Ad", "Ah"), ("8d", "8h"), ("Kd", "Kh"), ("Ad", "8h"), ("Ad", "2d")]  # Trips/Sets/Two Pair
    n_feuer = 0
    for c in combos:
        erwartet = guard(hr._mit_hole(k.zustand, c))
        feuert = erwartet == ("bet", int(hr.TURN_WERT_FRAC * k.zustand["pot"]))
        assert feuert == hr.bedingung_turn_wert(k.zustand, c, vill), c
        n_feuer += feuert
    assert n_feuer >= 3, "Fixture muss den Guard mehrfach zuenden (Trips/Two-Pair-Combos)"


def test_bedingung_sel_bitgenau_gegen_improver_guard():
    st0, _ = _engine_hand()
    k = next(k for k in hr.knoten_liste(st0, 1) if k.street == "flop" and k.facing)   # BB callt die Flop-Bet
    vill = hr._villain_range_am_knoten(k.zustand, 1, None)
    guard = sel_guard(_dummy("fold"), margin=hr.SEL_M15_MARGE)(1)
    rng = random.Random(12)
    combos = rng.sample(hr.lebende_combos(k.zustand["board"]), 80)
    feuer = [guard(hr._mit_hole(k.zustand, c)) == ("call", None) for c in combos]
    assert feuer == [hr.bedingung_sel(k.zustand, c, vill) for c in combos]
    assert 0 < sum(feuer) < len(feuer), "Fixture muss beide Faelle enthalten"


# ---------------------------------------------------------------- 7. Guard-Transformation vs explizite Enumeration
class _FakeAdvisor:
    """Deterministischer Advisor-Ersatz (Combo-Hash -> p in [0.1, 0.9]); Batch == Einzel per Konstruktion."""

    def available(self, street="flop"):
        return True

    def defense_available(self):
        return True

    def _p(self, hole, salz):
        h = hash((combo_kanonisch(hole[0], hole[1]), salz)) % 1000
        return 0.1 + 0.8 * h / 999.0

    def p_bet(self, hole, board, role, street="flop", pot_type=None):
        return self._p(hole, ("bet", street, role))

    def p_bet_batch(self, combos, board, role, street="flop", pot_type=None):
        return {tuple(c): self.p_bet(list(c), board, role, street) for c in combos}

    def p_defense(self, hole, board, role, size_faced, street="flop"):
        a, b = self._p(hole, ("f", street)), self._p(hole, ("c", street))
        s = a + b + 0.3
        return (a / s, b / s, 0.3 / s)

    def p_defense_batch(self, combos, board, role, size_faced, street="flop"):
        return {tuple(c): self.p_defense(list(c), board, role, size_faced, street) for c in combos}


def _normalize_wie_tracker(d: dict) -> dict:
    s = sum(d.values())
    d = {c: w / s for c, w in d.items() if w / s >= WEIGHT_FLOOR}
    s2 = sum(d.values())
    return {c: w / s2 for c, w in d.items()}


class _Patch:
    """Minimaler monkeypatch-Ersatz (Tests laufen auch ohne pytest: python -m tests.test_hero_range)."""

    def __init__(self):
        self._alt = []

    def setattr(self, obj, name, wert):
        self._alt.append((obj, name, getattr(obj, name)))
        setattr(obj, name, wert)

    def undo(self):
        for obj, name, alt in reversed(self._alt):
            setattr(obj, name, alt)


def test_guard_transformation_gegen_explizite_enumeration(monkeypatch=None):
    monkeypatch = monkeypatch or _Patch()
    """C(h) wird durch eine explizite Regel ersetzt (Paar in der Hand), damit die Enumeration unabhaengig vom
    MC-Pfad ist; die Transformationsformeln der Karte werden Combo fuer Combo nachgerechnet."""
    ist_paar = lambda z, c, v, *a: c[0][0] == c[1][0]  # noqa: E731
    monkeypatch.setattr(hr, "bedingung_turn_wert", ist_paar)
    monkeypatch.setattr(hr, "bedingung_sel", ist_paar)
    fake = _FakeAdvisor()
    st0, _ = _engine_hand()
    st = hr.schneide_am_river(st0)
    for hero in (0, 1):
        rek = hr.rekonstruiere(st0, hero=hero, advisor=fake)
        assert rek.status == hr.STATUS_OK
        # --- explizite Enumeration
        d = hr.prior_range(st, hero, advisor=fake)
        d = _normalize_wie_tracker(d)
        for art, wert in hr.ereignisse(st, hero)[0]:
            if art == "deal":
                tot = set(_board_at(st["board"], wert))
                d = _normalize_wie_tracker({c: w for c, w in d.items() if c[0] not in tot and c[1] not in tot})
                continue
            k = wert
            z, key = k.zustand, k.beobachtet
            for c in list(d):
                C = ist_paar(z, c, None)
                if not k.facing:
                    p = fake.p_bet(list(c), z["board"], hr.rolle_bet(z, hero, hr.K1_KONVENTION), k.street)
                    guard = hr.turn_wert_anwendbar(z)
                    ziel = hr.turn_wert_ziel(z) if guard else None
                    if key.kind == "check":
                        lik = (1 - p) * (0.0 if (guard and C) else 1.0)
                    else:
                        lik = p + ((1 - p) if (guard and C and key.chips == ziel.chips) else 0.0)
                else:
                    pf, pc, pr = fake.p_defense(list(c), z["board"], "IP" if hero == z["button"] else "OOP",
                                                hr._size_faced(z, hero, hr.K1_KONVENTION), k.street)
                    guard = hr.sel_anwendbar(z)
                    if key.kind == "call":
                        lik = pc + (pf if (guard and C) else 0.0)
                    elif key.kind == "fold":
                        lik = 0.0 if (guard and C) else pf
                    else:
                        lik = 1.0                                     # legality-only (Tracker-Paritaet)
                d[c] *= lik
            d = _normalize_wie_tracker(d)
        erwartet = {combo_kanonisch(*c): w for c, w in d.items()}
        assert _maxdiff(rek.hero_range, erwartet) <= TOL
        assert _tv(rek.hero_range, erwartet) <= TOL


def test_massenerhaltung_und_verschiebung_am_knoten(monkeypatch=None):
    monkeypatch = monkeypatch or _Patch()
    """Je Combo Σ_a π_exec = Σ_a π_vor = 1; die verschobene Check-Masse landet exakt in der b*-Spalte."""
    ist_paar = lambda z, c, v, *a: c[0][0] == c[1][0]  # noqa: E731
    monkeypatch.setattr(hr, "bedingung_turn_wert", ist_paar)
    monkeypatch.setattr(hr, "bedingung_sel", ist_paar)
    fake = _FakeAdvisor()
    st0, _ = _engine_hand()
    for k in hr.knoten_liste(st0, 1):
        m = hr.knoten_modell(k.zustand, 1, advisor=fake)
        assert isinstance(m.tabelle, PolicyTable)                    # Zeilen Σ=1 hart validiert
        for c, basis in m.basis.items():
            v = m.tabelle.verteilung(c)
            assert abs(sum(v.values()) - 1.0) <= TOL
            C = ist_paar(None, c, None)
            if m.guard == hr.GUARD_TURN_WERT:
                p_check, p_bet = basis
                assert abs(v[ActionKey.check()] - (0.0 if C else p_check)) <= TOL
                assert abs(v[m.guard_ziel] - (p_bet + (p_check if C else 0.0))) <= TOL
                assert m.likelihood(c, ActionKey.raise_to(m.guard_ziel.chips + 1)) == p_bet   # x ≠ b*: nur Basis
            elif m.guard == hr.GUARD_SEL_FLOP:
                pf, pc, pr = basis
                assert abs(v[ActionKey.fold()] - (0.0 if C else pf)) <= 1e-6
                assert abs(v[ActionKey.call()] - (pc + (pf if C else 0.0))) <= 1e-6
                assert abs(m.tabelle.p(c, m.tabelle.aktionen[2]) - pr) <= 1e-6   # Raise-Anteil bleibt
        if m.guard is not None:
            assert m.c_maske and len(m.c_maske) < len(m.basis)


def test_ohne_guards_keine_verschiebung():
    st0, _ = _engine_hand()
    k = next(k for k in hr.knoten_liste(st0, 1) if k.street == "turn")
    m = hr.knoten_modell(k.zustand, 1, guards=())
    assert m.guard is None and not m.c_maske and m.guard_ziel is None
    assert hr.action_likelihoods(k.zustand, 1, guards=()).aktionen[0] == ActionKey.check()


# ---------------------------------------------------------------- 8. p_defense_batch-Identitaet (E11)
def test_p_defense_batch_identitaet():
    if not advisor.defense_available():
        print("SKIP p_defense_batch: defense_advisor.pt / torch nicht verfuegbar")
        return
    rng = random.Random(3)
    worst = 0.0
    for street, board in (("flop", ["Ah", "7d", "2c"]), ("turn", ["Ah", "7d", "2c", "Td"]),
                          ("river", ["Ah", "7d", "2c", "Td", "3s"])):
        deck = [r + s for r in "23456789TJQKA" for s in "shdc" if r + s not in board]
        combos = [tuple(rng.sample(deck, 2)) for _ in range(150)]
        for role in ("IP", "OOP"):                                    # korrekte Gross-Schreibung (V10_FAKTEN A4)
            for size in (0.33, 0.66, 1.25):
                einzel = {c: advisor.p_defense(list(c), board, role, size, street) for c in combos}
                advisor._PDEF_MEMO.clear()
                batch = advisor.p_defense_batch(combos, board, role, size, street)
                worst = max(worst, max(abs(a - b) for c in combos for a, b in zip(einzel[c], batch[c])))
                assert all(abs(sum(batch[c]) - 1.0) <= 1e-5 for c in combos)
    assert worst < 1e-6, worst


# ---------------------------------------------------------------- K1-Orakel (research/k1_oracle.py, G3-Instrument)
# Reviewer-Befund 2026-09-07 (HOCH): geteilter Bot-Seed je Combo -> identisches Gatter-u -> P̂ war eine
# Treppenfunktion von p_bet (11/12 Combos mit identischem 8-Seed-Muster am Turn-Knoten dieser Fixture).
# Die Tests unten wuerden unter dem alten Design ROT: unabhaengige Stroeme je Combo, Fake-Backend-Exaktheit,
# Rauschboden aus Seed-Haelften, Urteil nur mit Karten-Stichprobe.
ORAKEL_COMBOS_TURN = [("Qh", "Jd"), ("Jh", "Td"), ("Th", "9d"), ("9h", "8d"), ("7h", "6d"), ("Qs", "Th"),
                      ("Js", "9h"), ("Ts", "8h"), ("5h", "4d"), ("6h", "5d"), ("Kh", "Qd")]
ORAKEL_SEEDS_TEST = list(range(1, 9))


def _turn_knoten_fixture():
    """Der Hero-0-Turn-Knoten der Engine-Fixture (BB check, BTN am Zug; das b*-Gatter ist gemischt)."""
    st0, states = _engine_hand()
    turn = states[6]
    assert turn["street"] == "turn" and turn["to_act"] == 0
    return st0, turn


def test_orakel_seed_unabhaengig_je_combo_und_knoten():
    from research import k1_oracle as ko
    adresse = (2, 0, 5)
    seeds = {ko.orakel_seed(1, adresse, c) for c in ORAKEL_COMBOS_TURN}
    assert len(seeds) == len(ORAKEL_COMBOS_TURN), "Combos muessen verschiedene RNG-Stroeme bekommen"
    assert ko.orakel_seed(1, adresse, ("Qh", "Jd")) == ko.orakel_seed(1, adresse, ["Qh", "Jd"])   # deterministisch
    assert ko.orakel_seed(1, (2, 0, 8), ("Qh", "Jd")) != ko.orakel_seed(1, adresse, ("Qh", "Jd"))  # Knoten trennt
    assert ko.orakel_seed(2, adresse, ("Qh", "Jd")) != ko.orakel_seed(1, adresse, ("Qh", "Jd"))     # Seed trennt
    assert ko.knoten_adresse(2, 0, {"history": [0] * 5}) == adresse


def test_orakel_stratifiziert_trifft_advisor_pbet_am_realen_stack():
    """Realer r6_button-Stack am Turn-Knoten: mit stratifiziertem Gatter-u ist das Treffermuster je Combo eine
    MONOTONE Treppe in k (check genau fuer u_k >= p_bet) und P̂(bet) trifft den Advisor-p_bet des Bots bis
    1/(2S) (+ Rundung der Rationale). Alt (geteilter Seed): nicht-monotone, ueber Combos identische Muster
    ['check','r1050','r1050','check',...] = P̂ 0,5 fuer p_bet 0,30..0,33."""
    import pokerbot.strategy.bot as botmod
    from pokerbot.strategy.bot import PokerBot
    from research import k1_oracle as ko
    _, turn = _turn_knoten_fixture()
    adresse = ko.knoten_adresse(0, 0, turn)
    beobachtet = ("check", None)                              # contracts.ActionKey: check traegt keinen Betrag
    n_strata = len(ORAKEL_SEEDS_TEST)
    _, _, treffer, hist = ko._orakel_paket((0, 0, adresse, turn, 0, beobachtet, ORAKEL_COMBOS_TURN,
                                            ORAKEL_SEEDS_TEST, "r6_button"))
    assert sum(hist.values()) == len(ORAKEL_COMBOS_TURN) * n_strata
    botmod.EQUITY_ITERS = ko.DUPLICATE_EQUITY_ITERS
    geprueft = 0
    for c in ORAKEL_COMBOS_TURN:
        muster = treffer[c][ko.EBENE_EXAKT]
        assert len(muster) == n_strata and list(muster) == sorted(muster), (c, muster)   # Treppe: bet unten, check oben
        bot = PokerBot(0, seed=1, exploit=True)
        bot.value_raise_eq = ko.DUPLICATE_VALUE_RAISE_EQ
        r = bot.decide(ko._mit_combo(turn, 0, c))["rationale"]
        pb = r.get("advisor_pbet_turn", r.get("advisor_pbet"))    # bot.py:811 (Turn) / :782 (Flop)
        if pb is None:
            continue                                          # anderer Pfad (Value-Size/Guard): nur Monotonie prueft
        p_bet_hat = 1.0 - ko.p_hat(muster)
        assert abs(p_bet_hat - pb) <= 0.5 / n_strata + 0.005, (c, p_bet_hat, pb)
        geprueft += 1
    assert geprueft >= 5, geprueft


def test_orakel_schaetzer_gegen_fake_backend(monkeypatch=None):
    """Fake-Stack mit Schwellen-Gatter `rng.random() < p(combo)` (wie bot.py:783) hinter einer MC-Equity-
    Attrappe (choices/sample auf dem Orakel-RNG): der stratifizierte Schaetzer trifft p EXAKT bis 1/(2S) —
    das alte Design (geteiltes u) lieferte fuer alle Combos gleicher Treppenstufe dasselbe P̂."""
    from research import k1_oracle as ko
    monkeypatch = monkeypatch or _Patch()
    st0, turn = _turn_knoten_fixture()
    b_star = int(hr.TURN_WERT_FRAC * turn["pot"])
    p_von = {c: 0.30 + 0.01 * i for i, c in enumerate(ORAKEL_COMBOS_TURN[:5])} | {c: 0.75 for c in ORAKEL_COMBOS_TURN[5:]}

    def fake_fabrik(stack, seed_eff, hero, stratum=None):
        rng = ko.orakel_rng(seed_eff, stratum)

        def entscheide(st):
            rng.choices([1, 2, 3], k=1); rng.sample(range(40), 5)          # MC-Equity-Attrappe (innerer Strom)
            combo = tuple(st["players"][hero]["hole"])
            return ("bet", b_star) if rng.random() < p_von[combo] else ("check", None)
        return entscheide
    monkeypatch.setattr(ko, "fabrik_fuer", fake_fabrik)
    n_strata = 400
    seeds = list(range(n_strata))
    adresse = ko.knoten_adresse(0, 0, turn)
    _, _, treffer, _ = ko._orakel_paket((0, 0, adresse, turn, 0, ("raise_to", b_star), ORAKEL_COMBOS_TURN, seeds, "egal"))
    for c, p in p_von.items():
        assert abs(ko.p_hat(treffer[c][ko.EBENE_EXAKT]) - p) <= 0.5 / n_strata + 1e-12, (c, ko.p_hat(treffer[c][0]), p)
    nahe_p = sorted(ko.p_hat(treffer[c][ko.EBENE_EXAKT]) for c in ORAKEL_COMBOS_TURN[:5])
    assert len(set(nahe_p)) == 5, ("p 0,30..0,34 muessen aufgeloest werden (alt: eine Treppenstufe)", nahe_p)
    if isinstance(monkeypatch, _Patch):
        monkeypatch.undo()


def test_stratifizierter_rng_delegiert_und_gitter():
    from research import k1_oracle as ko
    assert [ko.gitterpunkt(k, 4) for k in range(4)] == [0.125, 0.375, 0.625, 0.875]
    rng, ref = ko.orakel_rng(77, (1, 4)), random.Random(77)
    assert rng.random() == 0.375                                  # erster Aufruf = Gitterpunkt
    assert rng.random() == ref.random()                           # danach der innere Strom
    assert rng.choices([1, 2, 3], weights=[1, 2, 3], k=5) == ref.choices([1, 2, 3], weights=[1, 2, 3], k=5)
    assert rng.sample(range(50), 7) == ref.sample(range(50), 7)   # MC-Equity-Methoden delegieren
    plain = ko.orakel_rng(77, None)
    assert isinstance(plain, random.Random) and plain.random() == random.Random(77).random()


def test_stack_fabrik_identisch_mit_baue_fabrik():
    """Die Spiegelung von duplicate.pokerbot in k1_oracle.stack_fabrik (noetig fuer den RNG-Tausch) muss
    entscheidungs-identisch zu pargate._baue_fabrik bleiben — sonst misst das Orakel einen anderen Stack."""
    from pokerbot.autogym.pargate import _baue_fabrik
    from research import k1_oracle as ko
    _, states = _engine_hand()
    knoten = [(states[3], 0), (states[6], 0), (states[4], 1)]        # BTN Flop-Bet, BTN Turn-Bet, BB facing Flop-Bet
    combos = ORAKEL_COMBOS_TURN[:4] + [("Ad", "Ah")]
    n = 0
    for seed in (1, 2, 3):
        for st, hero in knoten:
            for c in combos:
                st_c = ko._mit_combo(st, hero, c)
                assert _baue_fabrik("r6_button", seed)(hero)(st_c) == ko.stack_fabrik("r6_button", seed, hero)(st_c), (seed, hero, c)
                n += 1
    assert n == 45


def test_orakel_rauschboden_aus_seed_haelften():
    """Seed-Haelften: identische Haelften -> Floor 0; eine leere Haelfte -> None; p_hat mit Maske korrekt."""
    from research import k1_oracle as ko
    st0, turn = _turn_knoten_fixture()
    vg = {"st0": st0, "hero": 0}
    prior = hr.prior_range(st0, 0)
    tot = set(turn["board"])
    combos = [c for c in prior if c[0] not in tot and c[1] not in tot]
    knoten = hr.knoten_liste(st0, 0)
    assert len(knoten) == 2                                   # Flop-Bet + Turn-Bet des BTN
    gleich = {c: ((1, 1, 0, 0), (1, 1, 1, 1)) for c in combos}   # A={0,2}->(1,0), B={1,3}->(1,0): Haelften gleich
    treffer = {0: gleich, 1: gleich}
    assert ko.seed_haelften(4) == ((0, 2), (1, 3))
    assert ko.p_hat((1, 1, 0, 0)) == 0.5 and ko.p_hat((1, 1, 0, 0), (0, 2)) == 0.5 and ko.p_hat((1, 1, 0, 0), (0, 1)) == 1.0
    assert ko.tv_floor(vg, treffer, 4) == 0.0
    schief = {c: ((1, 0, 1, 0), (1, 1, 1, 1)) for c in combos}   # B-Haelfte ohne Masse -> nicht messbar
    assert ko.tv_floor(vg, {0: schief, 1: schief}, 4) is None
    assert ko.tv_floor(vg, treffer, 1) is None
    voll = ko.oracle_range(vg, treffer, ko.EBENE_EXAKT)
    assert abs(sum(voll.values()) - 1.0) <= TOL and all(c[0] not in set(st0["board"]) for c in voll)


def test_orakel_urteil_nur_mit_stichprobe_und_aufloesung():
    from research import k1_oracle as ko
    im_budget = {"n": 6, "mittel": 0.01, "p95": 0.02, "max": 0.03}
    verfehlt = {"n": 6, "mittel": 0.26, "p95": 0.84, "max": 0.84}
    pilot = ko.stichprobe_pruefen(6, 14, {"button_disziplin": 1, "sel_m15": 2})
    assert not pilot["ausreichend"] and len(pilot["gruende"]) == 5, pilot["gruende"]
    assert ko._budget_urteil(verfehlt, 0.001, pilot) == "unterpowert"      # das Pilot-Verdikt ist KEIN K1-Verdikt
    assert ko._budget_urteil(im_budget, 0.001, pilot) == "unterpowert"
    voll = ko.stichprobe_pruefen(64, 128, {"sel_m15": 16, "turn_wert": 16, "button_disziplin": 16})
    assert voll["ausreichend"]
    assert ko._budget_urteil(verfehlt, 0.011, voll) == "orakel_zu_grob"    # Floor > 0,5 * 0,02
    assert ko._budget_urteil(verfehlt, None, voll) == "orakel_zu_grob"
    assert ko._budget_urteil(verfehlt, 0.009, voll) == "verfehlt"
    assert ko._budget_urteil(im_budget, 0.009, voll) == "im_budget"
    assert ko._budget_urteil({"n": 0}, 0.0, voll) == "leer"
    assert ko._urteil_roh(verfehlt) == "verfehlt" and ko._urteil_roh(im_budget) == "im_budget"


def _alle_tests() -> int:
    """Standalone-Runner (Repo-Konvention `python -m tests.<modul>`); pytest sammelt dieselben Funktionen."""
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in tests:
        patch = _Patch()
        try:
            fn(patch) if "monkeypatch" in fn.__code__.co_varnames else fn()
        finally:
            patch.undo()
        print(f"OK {fn.__name__}")
    print(f"{len(tests)} Tests gruen")
    return len(tests)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    _alle_tests()
