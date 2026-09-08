"""K1-ORAKEL v2 (Gate G3, Karte docs/V10_BUILD_CARD.md K1-Abnahme): misst, wie gut die K1-Likelihood-Rekonstruktion
(pokerbot/strategy/hero_range.py) die TATSAECHLICH AUSGEFUEHRTE Politik des Stacks trifft.

Orakel = offline decide() je hypothetischer Hero-Combo: an jedem Hero-Knoten vor dem River wird der Stack
(pargate._baue_fabrik(stack, seed) — nur aufgerufen) mit AUSGETAUSCHTEN Hole-Cards ueber S Seeds befragt.
P(beobachtet | combo) = Anteil der Seeds, deren kanonisierte Aktion (contracts.kanonisiere = Engine-Clamp) der
beobachteten gleicht. Oracle-Range ∝ Prior · Π_t P(a_t | combo) mit demselben Prior/derselben Board-Maske wie K1
(RangeTracker-Internals). Kennzahl: TV-Distanz zur K1-Range.

v2 — WARUM ein UNABHAENGIGER RNG-Strom je (Seed, Knoten, Combo) (Reviewer-Befund 2026-09-07, reproduziert):
`duplicate.pokerbot` baut `PokerBot(seat, seed=seed)` (duplicate.py:107), und die MC-Equity konsumiert denselben
`self.rng` mit combo-UNABHAENGIGER Ziehungszahl (bot.py:566/569; Deck-Groesse und `choices(k=1)` haengen nicht
von Heros Hand ab). Ein geteilter Seed liefert also an JEDEM Gatter dasselbe u fuer alle Combos → P̂(a|combo) war
eine Treppenfunktion von p_bet mit S gemeinsamen Schwellen (Repro: 11/12 Combos mit identischem 8-Seed-Muster),
keine empirische Verteilung. Jetzt: seed_eff = keyed_hash(seed, Knoten-Adresse, combo) (Praezedenz Per-Spot-
Reseeding: coach/oracle.py:185-188) → je Combo ein unabhaengiger Bernoulli-Schaetzer (SE = √(p(1−p)/S)), Fehler
ueber Combos unkorreliert. ZUSAETZLICH wird das Gatter-u STRATIFIZIERT (StratifizierterRNG: der erste
random()-Aufruf des Bots = Gitterpunkt (k+½)/S, der Rest = innerer Random(seed_eff)): reines MC hatte im Pilot
(S=8) einen Rauschboden von 0,20 — so gross wie die K1-Distanz selbst — und skaliert nur mit 1/√S (Floor 0,01
haette S≈3000 verlangt); das Gitter macht ein Schwellen-Gatter exakt bis 1/(2S). Die Treffer werden JE SEED
gespeichert, damit der RAUSCHBODEN des Orakels messbar ist: TV(Orakel[gerade k], Orakel[ungerade k]) je
Vorgeschichte (zwei versetzte Gitter halber Aufloesung = konservativ). Das Budget-Urteil wird NUR vergeben, wenn
(a) die Karten-Stichprobe steht (>=64 Vorgeschichten, >=128 Knoten, jede Guard-Klasse >=16x) und (b) der
Rauschboden hoechstens die Haelfte des Mittel-Budgets betraegt (Dreiecksungleichung: sonst ist ein 'verfehlt'
nicht K1 zuzuschreiben) — andernfalls 'unterpowert' bzw. 'orakel_zu_grob'.

Vorgeschichten (Kanal 'gym'): Gym-Decks (duplicate.gen_decks) im Self-Play des Stacks (beide Sitze derselbe
Stack, exploit ON, PRINCE aus, Resolver AUS = der pargate-Kanal, E2/E3) -> Haende mit River; jede (Hand, Hero-Sitz)
ist eine Vorgeschichte. Die Engine-States vor jeder Hero-Entscheidung werden MITGESCHNITTEN (kein Replay noetig;
die K1-Replay-Buchhaltung wird in tests/test_hero_range.py gegen dieselben Engine-States geprueft). Welche
Guards REAL feuerten, wird beim Spielen protokolliert (Basis-Aktion vs Stack-Aktion je Knoten).

Kanal 'gtow' (GTOW-HH via research/river_bill_replay.spot_state) ist als Schalter vorgesehen, aber NICHT
verdrahtet — G3 laeuft laut E3 zuerst auf dem Gym-Kanal; der Live-Kanal braucht den Live-Stack (PRINCE +
Resolver ON) und die K4-Konfig, die hier nicht existiert. Der Aufruf endet mit einer klaren Meldung.

Report: data/runs/v10/k1_oracle_<ts>.json (mittel/p95/max TV; Rauschboden; je Guard-Klasse; Stichproben-Pruefung;
je Knoten P(beobachtet | echte Hero-Hand) als Mechanik-Kontrolle). Multiprocessing spawn-sicher (alles unter
__main__; OPENBLAS/OMP=1 + POKERB_*-Strip + torch 1 Thread wie pargate._worker).

  Pilot:  python -m research.k1_oracle --n 6 --seeds 8 --workers 4
  G3:     python -m research.k1_oracle --n 64 --seeds 64 --workers 12
          GEMESSEN (n=6, 14 Knoten, 12 Worker, Reports data/runs/v10/k1_oracle_20260907_18*/19*.json):
          S=8 → Floor 0,122 | S=32 → 0,050 (600 s) | S=64 → 0,033 (1124 s) ≈ 1/√S (der Rest-MC-Anteil der
          Equity dominiert das Gitter). → 64 Vorgeschichten bei S=64 ≈ 3,3 h; fuer Floor <= 0,010 (Urteils-
          Vorbedingung) waere S≈256 (~13 h) noetig. Die Klassen-Ebene ist schon bei S=64 auf 0,0035 konvergiert.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import random
import sys
import time
import zlib
from pathlib import Path

REPORT_DIR = Path("data/runs/v10")
ORAKEL_VERSION = "k1-orakel-2"        # v1 = geteilter Seed je Combo (Treppenfunktion, Reviewer-Befund); v2 = unabhaengig + stratifiziert
STACK_STANDARD = "r6_button"          # sel_m15 + turn_wert + button_disziplin, OHNE River-Guards (Karte K1)
COMBO_CHUNK = 48                      # Combos je Arbeitspaket (Balance: Pool-Overhead vs Granularitaet)
MAX_DECKS = 2000                      # Deck-Bank je --deck-seed; ~50 % der Haende erreichen den River
KANAL_GYM = "gym_engine"
# TV-Budget der Karte (K1-Abnahme): mittel <= 0,02, p95 <= 0,05, kein Fall > 0,10
TV_BUDGET = {"mittel": 0.02, "p95": 0.05, "max": 0.10}
# Stichproben-Vorbedingungen der Karte (K1-Abnahme, Zeile 'Oracle-Stichprobe')
MIN_VORGESCHICHTEN = 64
MIN_KNOTEN = 128
MIN_JE_GUARD_KLASSE = 16
# Der Rauschboden (TV der beiden Seed-Haelften) darf hoechstens diesen Anteil des Mittel-Budgets betragen —
# sonst kann das Orakel ein 'verfehlt' gar nicht aufloesen (Dreiecksungleichung: TV(K1,wahr) >= TV(K1,Orakel) −
# TV(Orakel,wahr); der Haelften-Abstand schaetzt das Orakel-Rauschen bei halber Seed-Zahl, also konservativ).
FLOOR_ANTEIL_BUDGET = 0.5
EBENE_EXAKT, EBENE_KLASSE = 0, 1      # Treffer ueber finale Chips (das Urteil) vs ueber die Aktionsklasse (Diagnose)


# ================================================================ Phase 1: Vorgeschichten spielen (Hauptprozess)
def _basis_protokolliert(seed: int, protokoll: list):
    """duplicate.pokerbot(exploit=True, seed) mit Mitschrift der Basis-Aktion — entscheidungs-identisch zur
    Fabrik in pargate._baue_fabrik (der Wrapper ist transparent); nur so ist 'Guard feuerte' exakt ablesbar."""
    from pokerbot.benchmark.duplicate import pokerbot
    innen = pokerbot(exploit=True, seed=seed)

    def make(seat):
        d0 = innen(seat)

        def d(st):
            a, amt = d0(st)
            protokoll.append((a, amt))
            return a, amt
        return d
    return make


def _guard_klasse(street: str, basis: tuple, final: tuple) -> str | None:
    """Welcher Guard der r6_button-Kette hat die Basis ueberschrieben? (Trigger laut improver.py)"""
    if (basis[0], basis[1]) == (final[0], final[1]):
        return None
    if street == "flop" and basis[0] == "fold" and final[0] == "call":
        return "sel_m15"
    if street == "turn" and basis[0] == "check" and final[0] == "bet":
        return "turn_wert"
    if street == "preflop" and basis[0] == "fold" and final[0] == "raise":
        return "button_disziplin"
    return "unbekannt"


def knoten_adresse(deck_idx: int, hero: int, state: dict) -> tuple[int, int, int]:
    """Oeffentliche, n-unabhaengige Adresse eines Hero-Knotens (Deck-Index der Bank, Sitz, History-Laenge) —
    der Schluessel des Orakel-Seeds; unabhaengig von --n, damit Teil-Laeufe reproduzierbar bleiben."""
    return (deck_idx, hero, len(state["history"]))


def spiele_vorgeschichten(n: int, deck_seed: int, seed: int, stack: str) -> list[dict]:
    """Self-Play des Stacks auf Gym-Decks; liefert n Vorgeschichten (Hand, Hero-Sitz) mit River und >= 1
    Hero-Knoten auf Flop/Turn. Jede traegt st0 (River-Beginn), die Engine-States je Hero-Knoten und die
    real gefeuerten Guards."""
    from pokerbot.autogym.pargate import _wickle
    from pokerbot.benchmark.duplicate import _setup_fixed, gen_decks
    from pokerbot.engine.game import HeadsUpGame
    from pokerbot.strategy import hero_range as hr
    out: list[dict] = []
    g = HeadsUpGame(names=("S0", "S1"), starting_stack=20000, sb=50, bb=100, seed=0)
    decks = gen_decks(MAX_DECKS, seed=deck_seed)       # feste Bank: Deck-Index = reproduzierbare Adresse
    deck_idx = 0
    while len(out) < n and deck_idx < len(decks):
        h0, h1, board = decks[deck_idx]
        _setup_fixed(g, h0, h1, board, 0, 20000)
        protokoll: list = []
        fab = _wickle(stack, _basis_protokolliert(seed, protokoll))
        d = (fab(0), fab(1))
        zuege: list[dict] = []                    # (seat, street, state, basis, final)
        schutz = 0
        while not g.hand_over and schutz < 500:
            st = g.state()
            a, amt = d[st["to_act"]](st)
            zuege.append({"seat": st["to_act"], "street": st["street"], "state": st,
                          "basis": protokoll[-1], "final": (a, amt)})
            g.act(a, amt)
            schutz += 1
        river = [z["state"] for z in zuege if z["street"] == "river"]
        deck_idx += 1
        if not river:
            continue
        st0 = hr.schneide_am_river(river[0])
        for hero in (0, 1):
            knoten = hr.knoten_liste(st0, hero)
            if not knoten or len(out) >= n:
                continue
            states = {len(z["state"]["history"]): z["state"] for z in zuege if z["seat"] == hero}
            guards_real = sorted({gk for z in zuege if z["seat"] == hero
                                  for gk in (_guard_klasse(z["street"], z["basis"], z["final"]),) if gk})
            out.append({"deck_idx": deck_idx - 1, "hero": hero, "st0": st0,
                        "knoten_states": [states[k.index] for k in knoten],
                        "beobachtet": [(k.beobachtet.kind, k.beobachtet.chips) for k in knoten],
                        "guards_real": guards_real,
                        "hero_hole": list(river[0]["players"][hero]["hole"])})
    return out


# ================================================================ Phase 2: Orakel-Arbeitspakete (Worker)
def _worker_env() -> None:
    """Identisch zu pargate._worker: OpenBLAS/OMP 1 Thread, POKERB_*-Strip, torch 1 Thread."""
    for v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ[v] = "1"
    for k in [k for k in os.environ if k.startswith("POKERB_")]:
        os.environ.pop(k, None)
    try:
        import torch
        torch.set_num_threads(1)
    except Exception:  # noqa: BLE001
        pass


def _mit_combo(state: dict, hero: int, combo) -> dict:
    """Engine-State mit ausgetauschter Hero-Hand; Villain-Hole maskiert ('??' wie im Live-Kanal —
    der Bot darf die Gegnerkarten ohnehin nicht lesen)."""
    st = dict(state)
    spieler = [dict(p) for p in st["players"]]
    spieler[hero]["hole"] = list(combo)
    spieler[1 - hero]["hole"] = ["??", "??"]
    st["players"] = spieler
    return st


def orakel_seed(seed: int, adresse: tuple, combo) -> int:
    """Der effektive Bot-Seed einer Orakel-Befragung: keyed Hash aus (Basis-Seed, Knoten-Adresse, Combo).
    Ein unabhaengiger RNG-Strom je Combo ist die Korrektur des v1-Defekts (Modul-Docstring): mit geteiltem Seed
    zog jede Combo dasselbe Gatter-u. Der Knoten in der Adresse verhindert zudem, dass Flop- und Turn-Befragung
    derselben Combo denselben Strom sehen (die Produktformel nimmt Unabhaengigkeit an)."""
    return zlib.crc32(f"{seed}|{adresse}|{tuple(combo)}".encode())


class StratifizierterRNG:
    """Bot-RNG-Ersatz fuer das Orakel: der ERSTE random()-Aufruf liefert den Gitterpunkt u_k, alles andere
    (weitere random(), choices, sample, ...) den inneren Random(seed_innen).
    WARUM: die Postflop-Gatter ziehen `self.rng.random()` DIREKT (bot.py:621/783/812/851/897/909/921), die
    MC-Equity davor nur `rng.choices`/`rng.sample` (equity.py:65-68/107-110, auf dem inneren Random). So trifft
    das Gitter genau das Gatter-u: fuer ein Schwellen-Gatter ist P̂ = #{k: u_k < p}/S exakt bis 1/(2S), statt
    Bernoulli-Rauschen 1/√S (Pilot S=8: Rauschboden 0,20 = so gross wie die K1-Distanz selbst). Der innere
    Strom variiert mit k, also bleibt die MC-Equity-Streuung mitintegriert (Stratifikation aendert den
    Erwartungswert nicht, senkt nur die Varianz). Preflop-Gatter ueber `rng.choices` (bot.py:247/342/356)
    bleiben unstratifiziert = reines MC (dokumentierte Restunschaerfe)."""

    def __init__(self, u_erst: float, seed_innen: int):
        self._u_erst = u_erst
        self._innen = random.Random(seed_innen)
        self._erst_offen = True

    def random(self) -> float:
        if self._erst_offen:
            self._erst_offen = False
            return self._u_erst
        return self._innen.random()

    def __getattr__(self, name):
        return getattr(self._innen, name)


def gitterpunkt(k: int, n_strata: int) -> float:
    """Mittelpunkt des k-ten von n gleich breiten Strata in [0,1) — die stratifizierte Gatter-Schwelle."""
    return (k + 0.5) / n_strata


def orakel_rng(seed_eff: int, stratum: tuple[int, int] | None):
    """Der RNG einer Orakel-Befragung: stratifiziert (k, S) oder — ohne Stratum — der plain Random(seed_eff)."""
    if stratum is None:
        return random.Random(seed_eff)
    return StratifizierterRNG(gitterpunkt(*stratum), seed_eff)


DUPLICATE_VALUE_RAISE_EQ = 0.72       # duplicate.pokerbot-Default (duplicate.py:101) — Spiegelung, s. stack_fabrik
DUPLICATE_EQUITY_ITERS = 120          # duplicate.pokerbot setzt bot.EQUITY_ITERS = 120 (duplicate.py:103)


def stack_fabrik(stack: str, seed: int, hero: int, rng=None):
    """Entscheidungsfunktion des benannten Stacks um eine PokerBot-Basis — SPIEGELT duplicate.pokerbot
    (duplicate.py:101-116) Zeile fuer Zeile, weil dessen Closure die Bot-Instanz verbirgt und das Orakel
    `bot.rng` austauschen muss (Praezedenz coach/oracle.py:185-188). rng=None => Random(seed) wie das Original.
    Identitaet mit pargate._baue_fabrik wird in tests/test_hero_range.py bewacht (Drift-Schutz der Kopie)."""
    import pokerbot.strategy.bot as botmod
    from pokerbot.autogym.pargate import _wickle
    from pokerbot.strategy.bot import PokerBot
    botmod.EQUITY_ITERS = DUPLICATE_EQUITY_ITERS

    def make(seat):
        pb = PokerBot(seat, seed=seed, exploit=True)
        pb.value_raise_eq = DUPLICATE_VALUE_RAISE_EQ
        if rng is not None:
            pb.rng = rng

        def d(st):
            pb.hero_idx = seat
            r = pb.decide(st)
            return r["action"], r["amount"]
        return d
    return _wickle(stack, make)(hero)


def fabrik_fuer(stack: str, seed_eff: int, hero: int, stratum: tuple[int, int] | None = None):
    """Die Entscheidungsfunktion einer FRISCHEN Stack-Instanz mit dem Orakel-RNG (stratifiziert, wenn ein
    Stratum (k, S) gegeben ist). Modul-Hook, damit Tests ein Fake-Backend mit bekannter P(a|combo) einsetzen."""
    return stack_fabrik(stack, seed_eff, hero, rng=orakel_rng(seed_eff, stratum))


def _orakel_paket(args: tuple) -> tuple:
    """(vg_idx, knoten_idx, adresse, state, hero, beobachtet, combos, seeds, stack)
    -> (vg_idx, knoten_idx, {combo: (treffer_exakt je Seed, treffer_klasse je Seed)}, histogramm).
    Seed-Index k = Stratum k von S (Gatter-u = Gitterpunkt), Seed-Wert = innerer MC-Strom je (Seed, Knoten,
    Combo). Treffer werden JE SEED gehalten (0/1-Tupel in Seed-Reihenfolge), damit Teilmengen (Seed-Haelften
    fuer den Rauschboden) ohne Neu-Rechnung ausgewertet werden koennen."""
    vg_idx, k_idx, adresse, state, hero, beobachtet, combos, seeds, stack = args
    _worker_env()
    from pokerbot.strategy.contracts import ActionKey, kanonisiere
    ziel = ActionKey(beobachtet[0], beobachtet[1])
    treffer: dict = {}
    histogramm: dict = {}
    for combo in combos:
        exakt, klasse = [], []
        for k, seed in enumerate(seeds):
            entscheide = fabrik_fuer(stack, orakel_seed(seed, adresse, combo), hero, (k, len(seeds)))
            a, amt = entscheide(_mit_combo(state, hero, combo))
            key = kanonisiere(a, amt, state)
            exakt.append(int(key == ziel))                     # finale Chips (Karte: Groessenvergleich)
            klasse.append(int(key.kind == ziel.kind))          # Aktionsklasse (was der Advisor modellieren kann)
            label = key.kind if key.kind != "raise_to" else f"raise_to({key.chips})"
            histogramm[label] = histogramm.get(label, 0) + 1
        treffer[tuple(combo)] = (tuple(exakt), tuple(klasse))
    return vg_idx, k_idx, treffer, histogramm


def _pakete(vorgeschichten: list[dict], seeds: list[int], stack: str) -> list[tuple]:
    """Ein Paket je (Vorgeschichte, Knoten, Combo-Block); Combos = Prior-Support minus Board am Knoten
    (jede Combo, die im Oracle-Produkt Masse tragen KANN)."""
    from pokerbot.strategy import hero_range as hr
    pakete = []
    for vi, vg in enumerate(vorgeschichten):
        prior = hr.prior_range(vg["st0"], vg["hero"])
        for ki, state in enumerate(vg["knoten_states"]):
            tot = set(state["board"])
            combos = sorted(c for c in prior if c[0] not in tot and c[1] not in tot)
            adresse = knoten_adresse(vg["deck_idx"], vg["hero"], state)
            for s in range(0, len(combos), COMBO_CHUNK):
                pakete.append((vi, ki, adresse, state, vg["hero"], vg["beobachtet"][ki],
                               combos[s:s + COMBO_CHUNK], seeds, stack))
    return pakete


# ================================================================ Phase 3: Auswertung
def _tv(a: dict, b: dict) -> float:
    return 0.5 * sum(abs(a.get(c, 0.0) - b.get(c, 0.0)) for c in set(a) | set(b))


def _kanonisch(d: dict) -> dict:
    from pokerbot.strategy.contracts import combo_kanonisch
    return {combo_kanonisch(*c): w for c, w in d.items()}


def p_hat(treffer: tuple, seed_maske: tuple[int, ...] | None = None) -> float:
    """Trefferquote ueber alle Seeds oder ueber die Seed-Indizes in `seed_maske`."""
    idx = range(len(treffer)) if seed_maske is None else seed_maske
    return sum(treffer[i] for i in idx) / len(idx)


def seed_haelften(n_seeds: int) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Disjunkte Seed-Index-Haelften (gerade/ungerade) fuer den Rauschboden Orakel-vs-Orakel."""
    return tuple(range(0, n_seeds, 2)), tuple(range(1, n_seeds, 2))


def oracle_range(vg: dict, treffer_je_knoten: dict[int, dict], ebene: int = EBENE_EXAKT,
                 seed_maske: tuple[int, ...] | None = None) -> dict:
    """Prior · Board-Maske · Π P̂ — mit denselben Tracker-Internals (Prior, _remove_dead, _normalize) wie K1.
    ebene EXAKT = P̂ ueber finale Chips (das ehrliche Ziel), KLASSE = P̂ ueber Aktionsklasse (isoliert die
    Groessen-Information, die dem groessenagnostischen Advisor-Backend fehlt). seed_maske = Seed-Teilmenge."""
    from pokerbot.strategy import hero_range as hr
    from pokerbot.strategy.range_tracker import RangeTracker, _board_at
    st0, hero = vg["st0"], vg["hero"]
    t = RangeTracker()
    t._init_preflop(st0)
    ki = 0
    for art, wert in hr.ereignisse(st0, hero)[0]:
        if art == "deal":
            t._remove_dead(_board_at(st0["board"], wert))
            continue
        d = t.range[hero]
        tk = treffer_je_knoten.get(ki, {})
        for c in list(d):
            tr = tk.get(tuple(c))
            d[c] *= p_hat(tr[ebene], seed_maske) if tr is not None else 0.0
        t._normalize(hero)
        ki += 1
    d = t.range.get(hero, {})
    s = sum(d.values())
    return _kanonisch({c: w / s for c, w in d.items()}) if s > 0 else {}


def tv_floor(vg: dict, treffer_je_knoten: dict[int, dict], n_seeds: int) -> float | None:
    """Rauschboden des Orakels fuer eine Vorgeschichte: TV der Oracle-Ranges aus den beiden Seed-Haelften.
    None, wenn eine Haelfte leer ist (n_seeds < 2) oder eine Haelfte keine Masse traegt."""
    a, b = seed_haelften(n_seeds)
    if not a or not b:
        return None
    ra = oracle_range(vg, treffer_je_knoten, EBENE_EXAKT, a)
    rb = oracle_range(vg, treffer_je_knoten, EBENE_EXAKT, b)
    return _tv(ra, rb) if ra and rb else None


def _quantil(xs: list[float], q: float) -> float:
    if not xs:
        return float("nan")
    xs = sorted(xs)
    k = min(len(xs) - 1, int(round(q * (len(xs) - 1))))
    return xs[k]


def _zusammenfassung(tvs: list[float]) -> dict:
    return {"n": len(tvs), "mittel": sum(tvs) / len(tvs) if tvs else float("nan"),
            "p95": _quantil(tvs, 0.95), "max": max(tvs) if tvs else float("nan")}


def stichprobe_pruefen(n_vorgeschichten: int, n_knoten: int, klassen_zaehler: dict[str, int],
                       guards: tuple[str, ...] | None = None) -> dict:
    """Karten-Vorbedingungen der K1-Abnahme: >=64 Vorgeschichten, >=128 Knoten, jede Guard-Klasse des Stacks
    >=16x REAL gefeuert. Liefert {'ausreichend': bool, 'gruende': [...]} — die Gruende sind der Bericht."""
    if guards is None:
        from pokerbot.strategy import hero_range as hr
        guards = hr.STANDARD_GUARDS
    gruende = []
    if n_vorgeschichten < MIN_VORGESCHICHTEN:
        gruende.append(f"Vorgeschichten {n_vorgeschichten} < {MIN_VORGESCHICHTEN}")
    if n_knoten < MIN_KNOTEN:
        gruende.append(f"Knoten {n_knoten} < {MIN_KNOTEN}")
    for g in guards:
        if klassen_zaehler.get(g, 0) < MIN_JE_GUARD_KLASSE:
            gruende.append(f"Guard-Klasse {g} {klassen_zaehler.get(g, 0)}x < {MIN_JE_GUARD_KLASSE}x")
    return {"ausreichend": not gruende, "gruende": gruende,
            "minima": {"vorgeschichten": MIN_VORGESCHICHTEN, "knoten": MIN_KNOTEN, "je_guard_klasse": MIN_JE_GUARD_KLASSE}}


def _urteil_roh(z: dict) -> str:
    """Nur der Zahlenvergleich gegen das TV-Budget — ohne Vorbedingungen (Diagnose, nie Abnahme)."""
    if z["n"] == 0:
        return "leer"
    ok = z["mittel"] <= TV_BUDGET["mittel"] and z["p95"] <= TV_BUDGET["p95"] and z["max"] <= TV_BUDGET["max"]
    return "im_budget" if ok else "verfehlt"


def _budget_urteil(z: dict, floor_mittel: float | None, stichprobe: dict) -> str:
    """Das Abnahme-Urteil: 'unterpowert' (Karten-Stichprobe fehlt), 'orakel_zu_grob' (Rauschboden > Haelfte des
    Mittel-Budgets oder nicht messbar), sonst der Zahlenvergleich. Reihenfolge = Beweiskraft: ohne Stichprobe
    und Aufloesung ist weder ein 'im_budget' noch ein 'verfehlt' K1 zuzuschreiben."""
    if z["n"] == 0:
        return "leer"
    if not stichprobe["ausreichend"]:
        return "unterpowert"
    if floor_mittel is None or floor_mittel > FLOOR_ANTEIL_BUDGET * TV_BUDGET["mittel"]:
        return "orakel_zu_grob"
    return _urteil_roh(z)


def _zaehle_guard_klassen(vgs: list[dict]) -> dict[str, int]:
    zaehler: dict[str, int] = {}
    for vg in vgs:
        for kl in vg["guards_real"]:
            zaehler[kl] = zaehler.get(kl, 0) + 1
    return zaehler


def _fall(vi: int, vg: dict, k1, k1_par, ohne_guards, treffer_v: dict, histo: dict, n_seeds: int) -> dict:
    """Die Auswertung einer Vorgeschichte: TV-Kennzahlen (exakt/Klasse/Vergleichsarme), Rauschboden,
    Mechanik-Kontrolle (P(beobachtet | echte Hand)) und die K1-Knotenprotokolle."""
    orakel = oracle_range(vg, treffer_v, EBENE_EXAKT)
    orakel_kl = oracle_range(vg, treffer_v, EBENE_KLASSE)
    floor = tv_floor(vg, treffer_v, n_seeds)
    tv_exakt = _tv(k1.hero_range, orakel) if orakel else None
    hole = tuple(vg["hero_hole"])
    p_echt = []
    for ki in sorted(treffer_v):
        tr = treffer_v[ki].get(hole, treffer_v[ki].get((hole[1], hole[0])))
        p_echt.append(p_hat(tr[EBENE_EXAKT]) if tr is not None else None)
    return {
        "deck_idx": vg["deck_idx"], "hero": vg["hero"], "hero_hole": list(hole),
        "n_knoten": len(vg["knoten_states"]), "guards_real": vg["guards_real"],
        "guards_k1": sorted({k.guard for k in k1.knoten if k.guard and k.n_c > 0}),
        "k1_status": k1.status, "pot_river": k1.pot_river,
        "tv_k1_vs_orakel": tv_exakt,
        "tv_floor_orakel_ab": floor,
        # untere Schranke von TV(K1, wahre Politik) per Dreiecksungleichung — Diagnose, nicht das Urteil
        "tv_k1_korrigiert_untere_schranke": (max(0.0, tv_exakt - floor) if tv_exakt is not None and floor is not None else None),
        "tv_k1_vs_orakel_klasse": _tv(k1.hero_range, orakel_kl) if orakel_kl else None,
        "tv_paritaet_vs_orakel": _tv(k1_par.hero_range, orakel) if orakel else None,
        "tv_ohne_guards_vs_orakel": _tv(ohne_guards.hero_range, orakel) if orakel else None,
        "tv_k1_vs_ohne_guards": _tv(k1.hero_range, ohne_guards.hero_range),
        "orakel_support": len(orakel), "k1_support": len(k1.hero_range),
        "p_beobachtet_echte_hand": p_echt,
        "orakel_histogramm": {str(ki): histo[(vi, ki)] for ki in sorted(treffer_v)},
        "knoten": [k.__dict__ for k in k1.knoten],
    }


def _sammle(faelle: list[dict], feld: str) -> list[float]:
    return [f[feld] for f in faelle if f.get(feld) is not None]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--n", type=int, default=6, help="Vorgeschichten (Hand x Hero-Sitz) mit River")
    ap.add_argument("--seeds", type=int, default=8, help="S Seeds je (Combo, Knoten); Rauschboden ~ 1/sqrt(S)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--deck-seed", type=int, default=5)
    ap.add_argument("--seed", type=int, default=1, help="Bot-Seed des gespielten Stacks (wie pargate --seed)")
    ap.add_argument("--stack", default=STACK_STANDARD)
    ap.add_argument("--kanal", choices=("gym", "gtow"), default="gym")
    args = ap.parse_args()
    if args.kanal == "gtow":
        sys.exit("Kanal 'gtow' ist noch NICHT verdrahtet (E3: G3 zuerst auf dem Gym-Kanal; der Live-Kanal braucht "
                 "den Live-Stack PRINCE+Resolver-ON aus K4). Bitte --kanal gym.")
    _worker_env()
    from pokerbot.strategy import hero_range as hr
    from pokerbot.strategy import range_tracker as rt

    t0 = time.time()
    vgs = spiele_vorgeschichten(args.n, args.deck_seed, args.seed, args.stack)
    t_spiel = time.time() - t0
    n_knoten = sum(len(v["knoten_states"]) for v in vgs)
    print(f"Vorgeschichten: {len(vgs)} | Hero-Knoten: {n_knoten} | gespielt in {t_spiel:.1f}s", flush=True)

    # K1 je Vorgeschichte (Standard-Konvention + Tracker-Paritaet + Tracker-Hero-Range als Referenz)
    t1 = time.time()
    k1 = [hr.rekonstruiere(v["st0"], hero=v["hero"]) for v in vgs]
    k1_par = [hr.rekonstruiere(v["st0"], hero=v["hero"], konvention=hr.TRACKER_PARITAET) for v in vgs]
    ohne_guards = [hr.rekonstruiere(v["st0"], guards=(), hero=v["hero"]) for v in vgs]
    t_k1 = time.time() - t1
    print(f"K1 gerechnet: {t_k1:.1f}s ({t_k1 / max(1, len(vgs)):.1f}s je Vorgeschichte)", flush=True)

    seeds = list(range(args.seed, args.seed + args.seeds))
    pakete = _pakete(vgs, seeds, args.stack)
    print(f"Orakel: {len(pakete)} Pakete x {COMBO_CHUNK} Combos x {len(seeds)} Seeds auf {args.workers} Workern "
          f"(Seed-Konvention: unabhaengig je Combo+Knoten, {ORAKEL_VERSION})", flush=True)
    t2 = time.time()
    treffer: dict[tuple, dict] = {}
    histo: dict[tuple, dict] = {}
    with mp.Pool(args.workers) as pool:
        for k, (vi, ki, tr, hist) in enumerate(pool.imap_unordered(_orakel_paket, pakete), 1):
            treffer.setdefault((vi, ki), {}).update(tr)
            h = histo.setdefault((vi, ki), {})
            for lab, n in hist.items():
                h[lab] = h.get(lab, 0) + n
            if k % 10 == 0 or k == len(pakete):
                el = time.time() - t2
                print(f"  [{k}/{len(pakete)}] {el / 60:.1f} min | ETA {el / k * (len(pakete) - k) / 60:.1f} min", flush=True)
    t_orakel = time.time() - t2

    faelle = []
    for vi, vg in enumerate(vgs):
        treffer_v = {ki: treffer[(vi, ki)] for ki in range(len(vg["knoten_states"])) if (vi, ki) in treffer}
        faelle.append(_fall(vi, vg, k1[vi], k1_par[vi], ohne_guards[vi], treffer_v, histo, len(seeds)))
    klassen: dict[str, list] = {}
    for f in faelle:
        for kl in (f["guards_real"] or ["keine"]):
            if f["tv_k1_vs_orakel"] is not None:
                klassen.setdefault(kl, []).append(f["tv_k1_vs_orakel"])
    gesamt = _zusammenfassung(_sammle(faelle, "tv_k1_vs_orakel"))
    floor = _zusammenfassung(_sammle(faelle, "tv_floor_orakel_ab"))
    stichprobe = stichprobe_pruefen(len(vgs), n_knoten, _zaehle_guard_klassen(vgs))
    floor_mittel = floor["mittel"] if floor["n"] > 0 else None
    report = {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"), "kanal": KANAL_GYM, "orakel_version": ORAKEL_VERSION,
        "seed_konvention": "seed_eff = crc32(f'{seed}|{(deck_idx, hero, len(history))}|{combo}') je Befragung; "
                           "Gatter-u stratifiziert: erster rng.random() = (k+0.5)/S, Rest = Random(seed_eff)",
        "kanal_flags": {"exploit": True, "prince": False, "resolver": False, "equity_iters": 120,
                        "tracker_alpha": rt.TRACKER_ALPHA, "aggro_full": rt.TRACKER_AGGRO_FULL,
                        "raise_narrow": rt.RAISE_NARROW, "audit_fix": rt.AUDIT_FIX},
        "k1_version": hr.K1_VERSION, "k1_versions_hash": hr.versions_hash(),
        "konfig": vars(args), "seeds": seeds, "stack": args.stack,
        "n_vorgeschichten": len(vgs), "n_knoten": n_knoten, "n_pakete": len(pakete),
        "zeit_s": {"spiel": round(t_spiel, 1), "k1": round(t_k1, 1), "orakel": round(t_orakel, 1)},
        "tv_budget": TV_BUDGET, "floor_anteil_budget": FLOOR_ANTEIL_BUDGET,
        "stichprobe": stichprobe, "guard_klassen_real": _zaehle_guard_klassen(vgs),
        "tv_k1_vs_orakel": gesamt,
        "tv_floor_orakel_ab": floor,
        "tv_k1_korrigiert_untere_schranke": _zusammenfassung(_sammle(faelle, "tv_k1_korrigiert_untere_schranke")),
        "urteil_roh": _urteil_roh(gesamt),
        "urteil_budget": _budget_urteil(gesamt, floor_mittel, stichprobe),
        "tv_k1_vs_orakel_klasse": _zusammenfassung(_sammle(faelle, "tv_k1_vs_orakel_klasse")),
        "tv_paritaet_vs_orakel": _zusammenfassung(_sammle(faelle, "tv_paritaet_vs_orakel")),
        "tv_ohne_guards_vs_orakel": _zusammenfassung(_sammle(faelle, "tv_ohne_guards_vs_orakel")),
        "je_guard_klasse_real": {k: _zusammenfassung(v) for k, v in sorted(klassen.items())},
        "je_kanal_flag": {KANAL_GYM: gesamt},
        "faelle": faelle,
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    pfad = REPORT_DIR / f"k1_oracle_{time.strftime('%Y%m%d_%H%M%S')}.json"
    pfad.write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    _drucke(report, faelle, pfad)


def _drucke(report: dict, faelle: list[dict], pfad: Path) -> None:
    gesamt, floor = report["tv_k1_vs_orakel"], report["tv_floor_orakel_ab"]
    print(f"\nTV K1 vs Orakel: mittel {gesamt['mittel']:.4f} | p95 {gesamt['p95']:.4f} | max {gesamt['max']:.4f} "
          f"(n={gesamt['n']}) -> roh {report['urteil_roh']} | ABNAHME: {report['urteil_budget']}")
    print(f"Rauschboden Orakel A/B (Seed-Haelften): mittel {floor['mittel']:.4f} | p95 {floor['p95']:.4f} | "
          f"max {floor['max']:.4f} (zulaessig fuer ein Urteil: mittel <= {FLOOR_ANTEIL_BUDGET * TV_BUDGET['mittel']:.3f})")
    if not report["stichprobe"]["ausreichend"]:
        print("Stichprobe unzureichend: " + "; ".join(report["stichprobe"]["gruende"]))
    kl = report["tv_k1_vs_orakel_klasse"]
    print(f"TV K1 vs Orakel (Aktionsklasse statt Chips): mittel {kl['mittel']:.4f} | p95 {kl['p95']:.4f} | max {kl['max']:.4f}")
    print(f"TV Paritaet(Tracker-Konv.) vs Orakel: mittel {report['tv_paritaet_vs_orakel']['mittel']:.4f} | "
          f"ohne Guards vs Orakel: mittel {report['tv_ohne_guards_vs_orakel']['mittel']:.4f}")
    for k, z in report["je_guard_klasse_real"].items():
        print(f"  Guard-Klasse {k}: n={z['n']} mittel {z['mittel']:.4f} max {z['max']:.4f}")
    for f in faelle:
        fl = f["tv_floor_orakel_ab"]
        print(f"  deck {f['deck_idx']} hero {f['hero']} {''.join(f['hero_hole'])}: TV {f['tv_k1_vs_orakel']:.4f} "
              f"(Klasse {f['tv_k1_vs_orakel_klasse']:.4f}, Floor {fl if fl is None else round(fl, 4)}) | "
              f"guards real {f['guards_real']} k1 {f['guards_k1']} | P(beob|echt) {f['p_beobachtet_echte_hand']}")
    print(f"Report: {pfad}")


if __name__ == "__main__":
    main()
