"""K2 — OEFFENTLICHER RIVER-PLAN (v10 Build-Karte docs/plans/V10_BUILD_CARD.md, Entscheidungen E1/E4/E5/E7).

WARUM: der v8/v9-`river_play_guard` (improver.py:535-604) gated JE ENTSCHEIDUNG am aktuellen Pot, loeste je
Entscheidung neu (B=1), snappte Off-Tree-Sizes stumm und hashte die HERO-HOLE in den Sampling-Schluessel
(V10_FAKTEN A5/B6/B10). Dieser Wrapper ersetzt ihn durch EINEN oeffentlichen Plan je Hand:

  * AKTIVIERUNG oeffentlich + strassenweit: pot_river (Pot beim River-Deal) >= min_pot_chips — unabhaengig von
    den Hole-Karten (PolicySnapshot.pot_bei_strassenbeginn: pot − Σ committed_street, V10_FAKTEN A5).
  * EIN Solve je River-Strasse (Root = River-Beginn, K1-Hero-Range wenn verfuegbar, sonst Tracker; Villain =
    Tracker), RiverCFRBatch DIREKT (E7: gpu_resolver.solve_spots/_injiziere werden NICHT benutzt → keine
    Hero-Injektion, r8_stack/r10_ernte bleiben byte-identisch), fp32, feste Iterationen (E5: kein Zeitabbruch
    im Gym), GEMITTELTE Strategie je Knoten.
  * NAVIGATION der gespielten River-Sequenz mit EXAKTEM Chip-Vergleich (±OFFTREE_TOLERANZ_CHIPS); Off-Tree →
    Fallback base(st) + Status 'offtree' (kein stilles Snapping, kein Neuloesen).
  * PRIVATE RANDOMISIERUNG u = blake2b(key=private_seed, hand_adresse|decision_addr) — Verteilung (fuer K3)
    und Sampling sind getrennte Funktionen; p∈{0,1} verbraucht keine Zufallszahl.
  * E1: in Plan-Pots wird base(st) NICHT aufgerufen (der TexasSolver-River-Resolver der Basis entfaellt dort);
    base(st) laeuft nur unterhalb der Schwelle, ausserhalb des Rivers und in den Fallback-Faellen
    (offtree/deadline/fehler/hand_not_in_range).
  * HERO AUSSERHALB DER OEFFENTLICHEN RANGE (Gewicht 0 in der K1-/Tracker-Hero-Range): dort hat der Solver KEINE
    Strategie — `avg_sigma` liefert bei Reach 0 uniform 1/n, und das darf NIE als Strategie gelesen werden
    (contracts.PolicyTable, V10_FAKTEN B10). `GeloesterPlan.verteilung` liefert fuer solche Combos KEINE Zeile
    (probs None + Flag), der Wrapper faellt auf base(st) mit Vertrags-Status 'hand_not_in_range' (v5-Praezedenz:
    TexasSolver-Resolver bei hand-not-in-range → Floor, resolver.py:257-259). Review-Fix 2026-09-07; die Rate
    dieser Faelle ist eine G3-Kennzahl (Support-Abdeckung der echten Hero-Hand; Zaehler `statistik(seat)`).

SIZE-KONVENTION (gpu_cfr.build_river_tree, gpu_cfr.py:95-150): ein Bet-Arm `bet{f}` investiert
min(rest, f · Pot-AM-KNOTEN) Chips (Pot inkl. aller bisherigen River-Einsaetze — NICHT f · pot_river); ein
Raise-Arm `raise2.7` investiert 2,7 · to_call ZUSAETZLICH; `jam` = Reststack; Arme >= 85 % des Rests fallen
mit dem Jam zusammen. Da die River-Investition bei Null startet, ist node.invest[actor] == committed_street
des Akteurs und der Engine-Raise-TO-Level eines Arms == round(kid.invest[actor]).
Chip-Betrag = round(kid.invest − node.invest); to_level = committed_street + Betrag (Engine-Konvention
amount = Raise-TO-Level, game.py:161-181). Jam-Regel + Legalitaetsgatter exakt wie improver.py:590-604.

LIVE-PARALLELITAET (E5, Review-Fix 2026-09-07): der GTOW-Harness spielt 5–8 Haende parallel mit EINER
Bot-Instanz (V10_FAKTEN A3:63-64). Darum (1) je Hand EIN laufender Solve (`_LaufenderSolve`): eine
Folge-Entscheidung derselben Hand wartet auf DIESELBE Future (Flag solve_geteilt) statt neu zu loesen, (2) die
Deadline zaehlt ab Solve-START — Queue-Wartezeit wird getrennt gemessen (zeiten_ms.queue) und hat ihr eigenes,
KURZES Budget (QUEUE_BUDGET_S; Ueberschreitung = sofortiger Basis-Fallback mit Flag deadline_in_queue), (3) ein
verspaetetes Ergebnis wird fuer DIE Entscheidung verworfen (Fallback Basis, Status deadline), aber der fertige
oeffentliche Plan wird gecacht: die naechste Entscheidung derselben Hand spielt ihn (Flag plan_verspaetet_genutzt)
statt einen zweiten Solve zu starten (Kaskaden-Schutz), (4) LIVE_SOLVE_WORKER = 1: mehr Worker helfen NICHT
(Messung: die Solves serialisieren sich am GIL, mit 8 Workern verpasst JEDE Hand die Deadline) — die Zahl ist ein
Knopf (`solve_worker`), (5) `aufwaermen()` traegt den CUDA-Kaltstart (2-3 s) vor der ersten Hand ab.

Trace: contracts.EntscheidungsTrace je Entscheidung; in Plan-Pots basis=None (E1, dokumentiert — das
Vertrags-Feld ist als ActionKey annotiert, zur Laufzeit ungeprueft; der Integrator kann die Annotation additiv
auf `ActionKey | None` weiten). Zusaetzliche Status-Flags ausserhalb des Vertrags-Vokabulars (k1_fallback,
hero_ausserhalb_range, cache_key_ohne_hand_id, ...) stehen im JSONL-Umschlag unter `flags`; die Zeit-Attribution
(zeiten_ms: queue/ranges/solve/gesamt) steht nur im Live-Modus im Umschlag (Gym-Trace bleibt byte-deterministisch),
ist aber immer ueber `GeloesterPlan.zeiten` abrufbar.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from collections import Counter, OrderedDict
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Mapping

from pokerbot.strategy.contracts import (ActionKey, EntscheidungsTrace, PolicySnapshot, PolicyTable, RangeState,
                                         RiverPlan, SUMMEN_TOLERANZ, combo_index, combo_kanonisch, kanonisiere,
                                         kanonisiere_history_eintrag, karte_int, konfig_hash_aus)

PLAN_VERSION = "k2-river-plan-2"      # -2: Reach-0-Zeilen nie gespielt, geteilte Live-Solves (Review-Fix 2026-09-07)
# Baum der Karte K2: 0,35/0,75/1,5 Pot + Raise 2,7x + Jam, max. 2 Raises (gpu_cfr.build_river_tree-Defaults).
BAUM_KW: dict[str, Any] = {"bet_sizes": (0.35, 0.75, 1.5), "raise_sizes": (2.7,), "max_raises": 2}
DEFAULT_MIN_POT_CHIPS = 1500          # Karte K2: 15 bb bei bb=100 (alle Messkanaele, V10_FAKTEN A1)
DEFAULT_ITERS = 150                   # Karte K2: fp32, 150 Iterationen, gemittelte Strategie
OFFTREE_TOLERANZ_CHIPS = 1            # Rundung float-Arm -> int-Chips (Engine int()-Truncation, game.py:170)
JAM_SCHWELLE_CHIPS = 1                # improver.py:597: betrag >= stack-1 -> allin
CACHE_GROESSE = 16                    # Plaene je Sitz (live laufen bis ~8 Haende parallel, V10_FAKTEN A3)
# Live-Solve-Threads: GEMESSEN 2026-09-07 (RTX 3080 Ti, freie GPU, 4 parallele echte Haende): die Solves
# SERIALISIEREN sich (Python-getriebene CFR-Traversierung + K1-MC teilen den GIL) — 8 Worker: solve 19,6 s je
# Hand, 0/4 Plaene rechtzeitig; 1 Worker: erste Hand 4,3 s (Plan), Rest Queue. => 1 Worker + kurzes Queue-Budget
# (Haende hinter einem laufenden Solve fallen SOFORT auf die Basis, statt 7,5 s zu warten). Paketbericht P2.
LIVE_SOLVE_WORKER = 3                 # G2-Befund 2026-09-08: mit EINEM Thread blockierte ein ueberlaufener Solve alle
                                      # Folge-Entscheidungen (7/10 'deadline_in_queue'); der Harness spielt 5 Haende parallel.
QUEUE_BUDGET_S = 3.0                  # Solve muss innerhalb 3 s BEGINNEN (G2: 0,5 s liess jede wartende Hand nach einem
                                      # langsamen Vorgaenger sofort auf die Basis fallen; der Harness hat KEINEN Entscheidungs-Timeout)
GYM_SALZ = b"pokerb-k2-gym-private-seed-v1"   # festes Salz fuer den deterministischen Gym-Seed (E4)
RANGE_QUANT_STELLEN = 6               # Range-Quantisierung fuer den Root-Hash
ROLLE_OOP, ROLLE_IP = 0, 1            # gpu_cfr: Spieler 0 = OOP handelt zuerst (gpu_cfr.py:150)

# Status-Flags des JSONL-Umschlags (ausserhalb des Vertrags-Vokabulars FALLBACK_STATUS).
FLAG_K1_FALLBACK = "k1_fallback"
FLAG_HERO_AUSSERHALB_RANGE = "hero_ausserhalb_range"     # echte Combo hat Gewicht 0 -> Status hand_not_in_range
FLAG_CACHE_KEY_OHNE_HAND_ID = "cache_key_ohne_hand_id"
FLAG_CACHE_ROOT_ABWEICHUNG = "cache_root_abweichung"
FLAG_JAM_GECLIPPT = "villain_jam_ueber_eff_geclippt"
FLAG_DEADLINE_IN_QUEUE = "deadline_in_queue"             # der Solve hat innerhalb deadline_s nicht einmal BEGONNEN
FLAG_SOLVE_GETEILT = "solve_geteilt"                     # Folge-Entscheidung wartete auf den laufenden Solve der Hand
FLAG_PLAN_VERSPAETET_GENUTZT = "plan_verspaetet_genutzt"  # Plan kam nach einer Deadline an, spaetere Entscheidung nutzt ihn

Combo = tuple[str, str]
StratFn = Callable[[dict], tuple[str, int | None]]


# ================================================================ oeffentliche Groessen (hole-frei)
def river_deal_index(history: list[dict]) -> int | None:
    """Index der River-Deal-Zeile (Kanal-Schnittmenge: action=='deal' & street=='river'); None = kein Deal
    (stiller Run-out, V10_FAKTEN A1 — dann gibt es keine River-Entscheidung)."""
    for i, h in enumerate(history):
        if h.get("action") == "deal" and h.get("street") == "river":
            return i
    return None


def pot_river_aus_state(st: Mapping[str, Any]) -> int:
    """Pot beim River-Deal = pot − Σ committed_street (exakt, verifiziert 1400 == 1400, V10_FAKTEN A5).
    Liest keine Hole-Karten, keine History."""
    return int(st["pot"]) - sum(int(p["committed_street"]) for p in st["players"])


def eff_stack_aus_state(st: Mapping[str, Any]) -> int:
    """Effektiver Stack am River-Beginn = min(stack + committed_street) — ueber die ganze Strasse invariant."""
    return int(min(int(p["stack"]) + int(p["committed_street"]) for p in st["players"]))


def ist_aktiviert(st: Mapping[str, Any], min_pot_chips: int = DEFAULT_MIN_POT_CHIPS) -> tuple[bool, int]:
    """(aktiv, pot_river): aktiv iff street=='river' und pot_river >= min_pot_chips. Oeffentlich, hole-frei."""
    if st.get("street") != "river":
        return False, 0
    pot_river = pot_river_aus_state(st)
    return pot_river >= min_pot_chips, pot_river


def rolle_von(seat: int, button: int) -> int:
    """HU postflop: der Button ist IP (handelt zuletzt, game.py:227-228) -> Baum-Rolle 1, sonst OOP = 0."""
    return ROLLE_IP if seat == button else ROLLE_OOP


def hand_adresse_aus(st: Mapping[str, Any]) -> tuple[str, list[str]]:
    """Adresse der Hand fuer Cache + private Randomisierung: state['hand_id'] (Adapter; im Gym injiziert der
    Integrator sie, E4). Fallback bis dahin: Karten-Hash sorted(hole)+board mit Flag — die Hole-Karten
    sind hier NUR Identitaet der Hand, nie Input der Aktivierung oder der Verteilung."""
    hid = st.get("hand_id")
    if hid is not None:
        return str(hid), []
    me = st["players"][st["to_act"]]
    roh = "|".join(sorted(me["hole"])) + "#" + ",".join(st["board"])
    return "karten:" + hashlib.sha256(roh.encode("utf-8")).hexdigest()[:24], [FLAG_CACHE_KEY_OHNE_HAND_ID]


def decision_addr_aus(st: Mapping[str, Any]) -> str:
    """Adresse der Entscheidung innerhalb der Hand: (street, len(history)) — Karte K2."""
    return f"{st['street']}/{len(st.get('history', []) or [])}"


# ================================================================ private Randomisierung
_PROZESS_SEED_LOCK = threading.Lock()
_PROZESS_SEED: bytes | None = None


def prozess_seed() -> bytes:
    """Live-Seed: os.urandom(16) EINMAL je Prozess (Karte K2: nie gegnerseitig ableitbar; via Fabrik loggbar)."""
    global _PROZESS_SEED
    with _PROZESS_SEED_LOCK:
        if _PROZESS_SEED is None:
            _PROZESS_SEED = os.urandom(16)
        return _PROZESS_SEED


def privater_seed_gym(hand_adresse: str, seat: int) -> bytes:
    """Gym-Seed deterministisch aus (hand_adresse, seat) mit festem Salz (E4): A/A bleibt exakt 0, beide Arme
    eines gepaarten Decks ziehen bei identischer Lage dieselbe Zahl."""
    return hashlib.blake2b(f"{hand_adresse}|{seat}".encode("utf-8"), key=GYM_SALZ, digest_size=32).digest()


def private_u(private_seed: bytes, hand_adresse: str, decision_addr: str) -> float:
    """u ∈ [0,1) = keyed blake2b(private_seed, hand_adresse|decision_addr) / 2^64."""
    h = hashlib.blake2b(f"{hand_adresse}|{decision_addr}".encode("utf-8"), key=private_seed, digest_size=8)
    return int.from_bytes(h.digest(), "big") / 2.0 ** 64


def ist_degeneriert(probs: list[float]) -> bool:
    """p∈{0,1} exakt (Vertrag: |p−1| <= 1e-6) -> kein Sample noetig, keine Zufallszahl verbraucht."""
    return any(abs(p - 1.0) <= SUMMEN_TOLERANZ for p in probs)


def sample_aus_verteilung(probs: list[float], u: float | None) -> int:
    """Index des gewaehlten Arms. Degeneriert -> argmax ohne u. Sonst inverse CDF ueber u; Arme mit p == 0
    werden NIE gewaehlt (exakt), Rest-Masse durch fp-Rundung faellt auf den letzten Arm mit p > 0."""
    if ist_degeneriert(probs):
        return max(range(len(probs)), key=lambda i: probs[i])
    if u is None:
        raise ValueError("echte Mischung braucht u")
    kum = 0.0
    letzter_positiver = max(i for i, p in enumerate(probs) if p > 0.0)
    for i, p in enumerate(probs):
        if p <= 0.0:
            continue
        kum += p
        if u < kum:
            return i
    return letzter_positiver


# ================================================================ Ranges am River-Beginn
def state_am_river_beginn(st: Mapping[str, Any]) -> dict | None:
    """Kopie des States mit History-Schnitt NACH dem River-Deal (wie improver._river_spot_und_frage) und den
    Chips auf River-Beginn zurueckgesetzt (committed_street 0, Stacks + committed_street, pot_river, OOP am Zug).
    None ohne River-Deal."""
    hist = st.get("history", []) or []
    schnitt = river_deal_index(hist)
    if schnitt is None:
        return None
    pot_river = pot_river_aus_state(st)
    button = int(st["button"])
    oop = 1 - button
    spieler = []
    for p in st["players"]:
        q = dict(p)
        q["stack"] = int(p["stack"]) + int(p["committed_street"])
        q["committed_total"] = int(p["committed_total"]) - int(p["committed_street"])
        q["committed_street"] = 0
        spieler.append(q)
    st0 = dict(st)
    st0.update(history=hist[:schnitt + 1], players=spieler, pot=pot_river, current_bet=0, to_act=oop,
               legal={"to_act": oop, "to_call": 0, "can_fold": False, "can_check": True, "can_call": False,
                      "call_amount": 0, "can_raise": spieler[oop]["stack"] > 0, "is_bet": True,
                      "raise_min": min(int(st.get("bb", 100)), spieler[oop]["stack"]),
                      "raise_max": spieler[oop]["stack"], "pot": pot_river})
    st0.setdefault("bb", 100)
    return st0


def _ohne_board_combos(w: Mapping[Combo, float], board: list[str]) -> dict[Combo, float]:
    """Board-Combos exakt 0 (Vertrags-Pflicht RangeState) — der Tracker entfernt sie bereits (_remove_dead)."""
    tot = {karte_int(c) for c in board}
    return {tuple(c): float(v) for c, v in w.items()
            if v > 0 and karte_int(c[0]) not in tot and karte_int(c[1]) not in tot}


K1_AKZEPTIERTE_STATUS = ("ok", "teilweise")
# WHY (Integrator-Entscheid 2026-09-07 nach dem Trace-Beispiel): "teilweise" heisst ein legality-only-
# Schritt (Raise-facing-Bet ohne Advisor-Modell) — genau das, was der Tracker dort ebenfalls tut. Ein
# Fallback auf die Tracker-Range verwirft dagegen ALLE Guard-Transformationen der uebrigen Knoten
# (Karte K2: Plan MIT K1-Range; contracts.REKONSTRUKTIONS_STATUS erlaubt "teilweise"). Nur
# "fehlgeschlagen" faellt zurueck. Aenderung = neuer Artefakt-Hash -> A/A 576 wiederholt (Gate G2a).


def _k1_hero_range(st0: dict, hero_seat: int) -> tuple[dict | None, str, str]:
    """LAZY: K1 (pokerbot/strategy/hero_range.py, Paket P1). Bevorzugt `rekonstruiere(st0, hero=)` (traegt
    Status + Rollen-Konvention), sonst `hero_range_river_start(st0, hero=)` (leer = fehlgeschlagen).
    Rueckgabe (range | None, status_grund, hero_rolle)."""
    try:
        from pokerbot.strategy import hero_range as k1     # noqa: WPS433 — bewusst lazy (Paket P1 parallel)
    except ImportError:
        return None, "k1_modul_fehlt", "position"
    rek_fn, plain_fn = getattr(k1, "rekonstruiere", None), getattr(k1, "hero_range_river_start", None)
    if rek_fn is None and plain_fn is None:
        return None, "k1_funktion_fehlt", "position"
    try:
        if rek_fn is not None:
            rek = rek_fn(st0, hero=hero_seat)
            rng, status = dict(rek.hero_range), str(rek.status)
            rolle = str(getattr(getattr(rek, "konvention", None), "rolle_bet", "initiative"))
        else:
            rng, rolle = dict(plain_fn(st0, hero=hero_seat)), "initiative"
            status = "ok" if rng else "fehlgeschlagen"
    except Exception as e:  # noqa: BLE001 — K1-Fehler darf den Plan nicht reissen, wird geflaggt
        return None, f"k1_fehler:{type(e).__name__}", "position"
    if status not in K1_AKZEPTIERTE_STATUS or not rng:
        return None, f"k1_status:{status}", rolle
    return rng, "ok", rolle


@dataclass(frozen=True)
class RiverRanges:
    hero: dict[Combo, float]
    villain: dict[Combo, float]
    herkunft: str                 # 'k1_likelihood' | 'tracker'
    hero_rolle: str
    flags: tuple[str, ...]


def ranges_am_river_beginn(st0: dict, hero_seat: int) -> RiverRanges | None:
    """Hero via K1 (Fallback Tracker, Flag k1_fallback), Villain via Tracker — beide am River-Beginn eingefroren
    (Tracker.build liest KEINE Hole-Karten, range_tracker.py:294-350 -> oeffentlich). None bei leerer Range."""
    from pokerbot.strategy.range_tracker import RangeTracker
    t = RangeTracker().build(st0)
    board = list(st0["board"])
    vill = _ohne_board_combos(t.range.get(1 - hero_seat, {}), board)
    hero_k1, status, rolle = _k1_hero_range(st0, hero_seat)
    flags: list[str] = []
    if hero_k1 is None:
        hero, herkunft, rolle = _ohne_board_combos(t.range.get(hero_seat, {}), board), "tracker", "position"
        flags.append(FLAG_K1_FALLBACK + ":" + status)
    else:
        hero, herkunft = _ohne_board_combos(hero_k1, board), "k1_likelihood"
    if not hero or not vill:
        return None
    return RiverRanges(hero, vill, herkunft, rolle, tuple(flags))


def _quantisiert(w: Mapping[Combo, float]) -> list[list]:
    """Normierte, auf RANGE_QUANT_STELLEN gerundete, kanonisch sortierte Items (Root-Hash-Baustein)."""
    s = sum(w.values()) or 1.0
    items = sorted(((combo_kanonisch(*c), round(v / s, RANGE_QUANT_STELLEN)) for c, v in w.items() if v > 0),
                   key=lambda kv: combo_index(*kv[0]))
    return [[c[0], c[1], q] for c, q in items if q > 0]


def root_hash_aus(board: list[str], rr: RiverRanges, pot_river: int, eff: int, hero_oop: bool,
                  iters: int, half: bool) -> str:
    return konfig_hash_aus({"board": list(board), "hero": _quantisiert(rr.hero), "villain": _quantisiert(rr.villain),
                            "pot_river": pot_river, "eff": eff, "hero_oop": hero_oop, "baum": BAUM_KW,
                            "iters": iters, "half": half, "version": PLAN_VERSION})


# ================================================================ Baum-Adressierung (Arme -> ActionKeys)
def arm_key(node: Any, kid: Any) -> ActionKey:
    """Arm eines Knotens als ActionKey: check/fold/call direkt; bet*/raise*/jam -> raise_to(TO-Level des
    Akteurs) = round(kid.invest[actor]) (River-Investition startet bei 0 => == committed_street nach dem Arm)."""
    label = node.acts[node.kids.index(kid)]
    if label in ("check", "fold", "call"):
        return ActionKey(label)
    return ActionKey.raise_to(int(round(kid.invest[node.actor])))


def arm_zusatz_chips(node: Any, kid: Any) -> int:
    """Zusatz-Einsatz des Akteurs fuer diesen Arm in Chips (gerundet)."""
    return int(round(kid.invest[node.actor] - node.invest[node.actor]))


def _passt_raise(key: ActionKey, node: Any, kid: Any, eff: int) -> bool:
    """Exakter Chip-Vergleich eines Raise-TO-Levels gegen einen Bet/Raise-Arm (±OFFTREE_TOLERANZ_CHIPS).
    Ein TO-Level >= eff wird auf eff geclippt: der deckende Villain kann mehr als eff setzen, fuer Hero ist
    jedes Level >= eff dasselbe Jam (Engine: Hero callt fuer weniger)."""
    ziel = min(int(key.chips), eff)
    return abs(ziel - int(round(kid.invest[node.actor]))) <= OFFTREE_TOLERANZ_CHIPS


def arm_index_fuer(node: Any, key: ActionKey, eff: int) -> int | None:
    """Index des Baum-Arms zu einem ActionKey oder None (= off-tree). Kein Nearest-Snapping."""
    for i, (label, kid) in enumerate(zip(node.acts, node.kids)):
        if key.kind in ("check", "fold", "call"):
            if label == key.kind:
                return i
        elif label.startswith(("bet", "raise")) and _passt_raise(key, node, kid, eff):
            return i
    return None


def alle_knoten_mit_pfad(root: Any) -> list[tuple[tuple[ActionKey, ...], Any]]:
    """Alle Entscheidungsknoten (actor >= 0) mit ihrem ActionKey-Pfad ab Root, Vorordnung."""
    out: list[tuple[tuple[ActionKey, ...], Any]] = []
    stapel = [((), root)]
    while stapel:
        pfad, n = stapel.pop()
        if n.actor < 0:
            continue
        out.append((pfad, n))
        for kid in n.kids:
            stapel.append((pfad + (arm_key(n, kid),), kid))
    return out


# ================================================================ der geloeste Plan
@dataclass(frozen=True)
class Zeiten:
    """Zeit-Attribution EINES Solves (immer gemessen, im Gym-Trace nicht geschrieben): ranges = Tracker + K1
    (CPU; dominiert bei Hero IP durch K1s turn_wert-MC, Paketbericht P2), solve = RiverCFRBatch Setup + solve +
    cuda.synchronize, gesamt = loese_plan end-to-end inkl. Kaltstart-Import (gesamt − ranges − solve = Rest)."""
    ranges_s: float
    solve_s: float
    gesamt_s: float

    def als_ms(self) -> dict[str, float]:
        return {"ranges": round(self.ranges_s * 1000.0, 1), "solve": round(self.solve_s * 1000.0, 1),
                "gesamt": round(self.gesamt_s * 1000.0, 1)}


@dataclass
class GeloesterPlan:
    """RiverPlan (Vertrag) + die Solver-Tensoren je Knoten. Die Verteilung ist OHNE RNG abrufbar (K3)."""
    plan: RiverPlan
    cfr: Any                                     # gpu_cfr.RiverCFRBatch (B=1)
    knoten: dict[tuple[ActionKey, ...], Any]     # Pfad -> Node
    hero_seat: int
    hero_rolle: int
    button: int
    pot_river: int
    eff: int
    root_hash: str
    hand_adresse: str
    hero_gewichte: dict[Combo, float]
    flags: tuple[str, ...] = ()
    zeiten: Zeiten | None = None
    verspaetet: bool = False                     # kam live NACH einer Deadline an (spaetere Nutzung wird geflaggt)

    def im_support(self, hole: list[str]) -> bool:
        """Hat Heros echte Combo Gewicht > 0 in der OEFFENTLICHEN Hero-Range? Nur dort ist die Solver-Zeile eine
        Strategie (Reach 0 -> avg_sigma uniform 1/n = Phantom, V10_FAKTEN B10)."""
        return self.hero_gewichte.get(combo_kanonisch(*hole), 0.0) > 0.0

    def verteilung(self, pfad: tuple[ActionKey, ...], hole: list[str]) -> tuple[tuple[ActionKey, ...], list[float] | None, list[str]]:
        """Hero-Verteilung am Knoten fuer die echte Combo aus der GEMITTELTEN Strategie (avg_sigma).
        Combo ausserhalb des Supports -> (keys, None, [hero_ausserhalb_range]): KEINE Zeile — die Reach-0-Uniform
        des Solvers ist keine Strategie (contracts.PolicyTable.undefiniert, V10_FAKTEN B10); KEINE Injektion (E7).
        Der Aufrufer entscheidet (Wrapper: Fallback Basis, Status hand_not_in_range)."""
        node = self.knoten[pfad]
        keys = tuple(arm_key(node, k) for k in node.kids)
        if not self.im_support(hole):
            return keys, None, [FLAG_HERO_AUSSERHALB_RANGE]
        zeile = self.cfr.avg_sigma(node)[0, combo_index(*hole)].double()
        return keys, (zeile / zeile.sum()).tolist(), []

    def tabelle(self, pfad: tuple[ActionKey, ...] = ()) -> PolicyTable:
        """PolicyTable des Knotens ueber den Hero-SUPPORT (Gewicht > 0 UND board-kompatibel); alle anderen
        Combos sind `undefiniert` (Reach-0-Uniform darf nie als Strategie gelesen werden, V10_FAKTEN B10)."""
        node = self.knoten[pfad]
        sig = self.cfr.avg_sigma(node)[0].double()
        zeilen_l = (sig / sig.sum(dim=1, keepdim=True)).tolist()      # float64-Renormierung: Σ=1 ± 1e-6
        keys = tuple(arm_key(node, k) for k in node.kids)
        zeilen, undefiniert = [], []
        for k, z in enumerate(zeilen_l):
            combo = _combo_str(k)
            if self.hero_gewichte.get(combo, 0.0) > 0.0:
                zeilen.append((combo, tuple(z)))
            else:
                undefiniert.append(combo)
        return PolicyTable(keys, tuple(zeilen), frozenset(undefiniert), herkunft="gpu_cfr_avg")

    def plan_mit_pfad(self, pfad: tuple[ActionKey, ...]) -> RiverPlan:
        return replace(self.plan, aktueller_pfad=pfad)


_RANKS, _SUITS = "23456789TJQKA", "shdc"
_COMBO_STRS: list[Combo] = []


def _combo_str(k: int) -> Combo:
    if not _COMBO_STRS:
        import itertools
        for a, b in itertools.combinations(range(52), 2):
            _COMBO_STRS.append((_RANKS[a // 4] + _SUITS[a % 4], _RANKS[b // 4] + _SUITS[b % 4]))
    return _COMBO_STRS[k]


def _gpu_fertig(cfr: Any) -> None:
    """Zeitmessung ehrlich machen: CUDA-Kernel laufen asynchron, erst synchronize() beendet den Solve."""
    if cfr.r[0].is_cuda:
        import torch
        torch.cuda.synchronize()


def loese_plan(st: Mapping[str, Any], hero_seat: int, hand_adresse: str, iters: int = DEFAULT_ITERS,
               half: bool = False, min_pot_chips: int = DEFAULT_MIN_POT_CHIPS,
               private_seed_quelle: str = "deck_hand_id_sitz",
               deadline_status: str = "iterations_deadline") -> GeloesterPlan | None:
    """Der EINE Solve je Hand: Root = River-Beginn, RiverCFRBatch (B=1) mit ECHTEM eff (kein SPR-Bucket) und
    pot_river in Chips (CFR+ ist skaleninvariant; Chips machen den Arm-Vergleich exakt). None, wenn der Root
    nicht rekonstruierbar ist (kein River-Deal, leere Range, eff <= 0). Zeiten (ranges/solve/gesamt) werden
    immer erfasst — perf_counter + synchronize aendern keine Werte, der Gym-Trace schreibt sie nicht."""
    t_gesamt = time.perf_counter()
    from pokerbot.strategy.gpu_cfr import RiverCFRBatch, range_vector      # Kaltstart (torch/CUDA) zaehlt zu gesamt
    st0 = state_am_river_beginn(st)
    if st0 is None:
        return None
    pot_river, eff, button = int(st0["pot"]), eff_stack_aus_state(st), int(st["button"])
    if pot_river <= 0 or eff <= 0:
        return None
    t_ranges = time.perf_counter()
    rr = ranges_am_river_beginn(st0, hero_seat)
    ranges_s = time.perf_counter() - t_ranges
    if rr is None:
        return None
    hero_rolle = rolle_von(hero_seat, button)
    board = list(st["board"])
    root_hash = root_hash_aus(board, rr, pot_river, eff, hero_rolle == ROLLE_OOP, iters, half)
    r_hero, r_vill = range_vector(rr.hero).unsqueeze(0), range_vector(rr.villain).unsqueeze(0)
    r_oop, r_ip = (r_hero, r_vill) if hero_rolle == ROLLE_OOP else (r_vill, r_hero)
    t_solve = time.perf_counter()
    cfr = RiverCFRBatch([board], r_oop, r_ip, pot=float(pot_river), eff_stack=float(eff), half=half, **BAUM_KW)
    cfr.solve(iters=iters)
    _gpu_fertig(cfr)
    solve_s = time.perf_counter() - t_solve
    knoten = dict(alle_knoten_mit_pfad(cfr.root))
    konfig = {"baum": BAUM_KW, "iters": iters, "half": half, "min_pot_chips": min_pot_chips, "version": PLAN_VERSION}
    root = PolicySnapshot.aus_state(st0, policy_id=PLAN_VERSION, konfig_hash=konfig_hash_aus(konfig))
    ranges = RangeState.aus(rr.hero, rr.villain, board, rr.herkunft, "unnormiert_skaleninvariant", "ok",
                            root_hash, hero_injiziert=False,
                            hero_rolle=rr.hero_rolle if rr.hero_rolle in ("position", "initiative") else "position")
    baum_hash = konfig_hash_aus({"pot_river": pot_river, "eff": eff, **BAUM_KW, "n_knoten": len(knoten)})
    plan = RiverPlan(root=root, ranges=ranges, baum_hash=baum_hash, konfig_hash=konfig_hash_aus(konfig),
                     knoten=tuple((p, f"tensor:{i}") for i, p in enumerate(knoten)), aktueller_pfad=(),
                     pot_river=pot_river, schwelle_chips=min_pot_chips, aktiviert=pot_river >= min_pot_chips,
                     deadline_status=deadline_status, private_seed_quelle=private_seed_quelle,
                     iterationen=iters, praezision="fp16" if half else "fp32")
    zeiten = Zeiten(ranges_s, solve_s, time.perf_counter() - t_gesamt)
    return GeloesterPlan(plan, cfr, knoten, hero_seat, hero_rolle, button, pot_river, eff, root_hash,
                         hand_adresse, {combo_kanonisch(*c): w for c, w in rr.hero.items()}, rr.flags, zeiten)


# ================================================================ Navigation
@dataclass(frozen=True)
class Navigation:
    pfad: tuple[ActionKey, ...] | None
    status: str                          # 'ok' | 'offtree' | 'fehler'
    grund: str = ""


def navigiere(gp: GeloesterPlan, st: Mapping[str, Any]) -> Navigation:
    """Laeuft die gespielten River-Schritte (nach dem River-Deal) durch den Baum: Akteur muss zur Baum-Rolle
    passen, jeder Schritt muss EXAKT (±1 Chip) auf einen Arm treffen; Ziel = Hero-Knoten am Zug."""
    hist = st.get("history", []) or []
    schnitt = river_deal_index(hist)
    if schnitt is None:
        return Navigation(None, "fehler", "kein_river_deal")
    pfad: tuple[ActionKey, ...] = ()
    node = gp.knoten[()]
    for h in hist[schnitt + 1:]:
        key = kanonisiere_history_eintrag(h)
        if key is None:
            continue
        spieler = h.get("player")
        if spieler not in (0, 1) or node.actor != rolle_von(int(spieler), gp.button):
            return Navigation(None, "fehler", "akteur_desync")
        i = arm_index_fuer(node, key, gp.eff)
        if i is None:
            return Navigation(None, "offtree", f"{key.kind}:{key.chips}")
        pfad = pfad + (arm_key(node, node.kids[i]),)
        node = node.kids[i]
        if node.actor < 0:
            return Navigation(None, "fehler", "terminal_erreicht")
    if node.actor != gp.hero_rolle:
        return Navigation(None, "fehler", "hero_nicht_am_zug")
    return Navigation(pfad, "ok")


# ================================================================ Legalitaet (exakt improver.py:590-604)
def legalisiere(key: ActionKey, st: Mapping[str, Any]) -> tuple[str, int | None]:
    """Plan-ActionKey -> (action, amount) fuer die Engine. fold/call bei to_call==0 -> check; check facing bet
    -> call (der passive Zweig; im korrekt navigierten Baum unerreichbar); bet/raise NUR wenn Gegner nicht
    all-in und stack > to_call (game.py:110 can_raise), sonst passiver Zweig; Jam-Regel betrag >= stack-1."""
    me = st["players"][st["to_act"]]
    opp = st["players"][1 - st["to_act"]]
    to_call = max(0, int(st["current_bet"]) - int(me["committed_street"]))
    passiv = ("call", None) if to_call > 0 else ("check", None)
    if key.kind == "fold":
        return ("fold", None) if to_call > 0 else ("check", None)
    if key.kind in ("call", "check"):
        return passiv
    kann_raisen = (not opp.get("all_in")) and int(me["stack"]) > to_call
    if not kann_raisen:
        return passiv
    betrag = int(key.chips) - int(me["committed_street"])
    if betrag >= int(me["stack"]) - JAM_SCHWELLE_CHIPS:
        return "allin", None
    return ("raise" if to_call > 0 else "bet"), int(me["committed_street"]) + betrag


def _key_oder_roh(action: str, amount: int | None, st: Mapping[str, Any]) -> ActionKey:
    """kanonisiere() mit Engine-Clamp; faellt bei fehlendem legal-Block auf den rohen Key zurueck."""
    try:
        return kanonisiere(action, amount, st)
    except (ValueError, KeyError):
        a = str(action).lower()
        if a in ("bet", "raise", "allin"):
            return ActionKey.raise_to(int(amount) if amount else int(st["players"][st["to_act"]]["stack"]))
        return ActionKey(a)


def _verteilung_gemerged(keys: tuple[ActionKey, ...], probs: list[float]) -> tuple[tuple[ActionKey, float], ...]:
    """Gleiche ActionKeys (theoretisch bei Rundungs-Kollision zweier Arme) werden addiert — Σ bleibt 1."""
    out: dict[ActionKey, float] = {}
    for k, p in zip(keys, probs):
        out[k] = out.get(k, 0.0) + p
    return tuple(out.items())


def _key_json(k: ActionKey | None) -> dict | None:
    return None if k is None else {"kind": k.kind, "chips": k.chips}


# ================================================================ Live-Solve-Verwaltung (E5)
@dataclass
class _LaufenderSolve:
    """Ein live laufender Solve einer Hand. `gestartet` trennt Queue-Wartezeit von Solve-Zeit (Deadline zaehlt ab
    t_start); `verworfen` merkt, dass ein Wartender in die Deadline lief — das fertige Ergebnis wird dann als
    'verspaetet' gecacht (spaetere Nutzung geflaggt), nie fuer die verpasste Entscheidung nachgereicht."""
    fut: Future
    gestartet: threading.Event = field(default_factory=threading.Event)
    t_submit: float = field(default_factory=time.perf_counter)
    t_start: float | None = None
    verworfen: bool = False

    def queue_s(self) -> float | None:
        return None if self.t_start is None else self.t_start - self.t_submit


@dataclass
class _SitzZustand:
    seat: int
    base: StratFn
    cache: "OrderedDict[str, GeloesterPlan]" = field(default_factory=OrderedDict)
    laufend: dict[str, _LaufenderSolve] = field(default_factory=dict)
    lock: threading.RLock = field(default_factory=threading.RLock)   # RLock: Done-Callback kann im Submitter laufen
    zaehler: Counter = field(default_factory=Counter)
    letzter_plan: GeloesterPlan | None = None
    letzter_trace: dict | None = None
    basis_aufrufe: int = 0


# ================================================================ die Wrapper-Fabrik
class RiverPlanFabrik:
    """make(seat) -> d(st) -> (action, amount) — Signatur-Muster wie improver.river_play_guard/pargate.
    Instanz statt Closure, damit private_seed-Herkunft/Prozess-Seed loggbar und Plaene testbar sind."""

    def __init__(self, make_strat, min_pot_chips: int = DEFAULT_MIN_POT_CHIPS, iters: int = DEFAULT_ITERS,
                 deadline_s: float | None = None, trace_pfad: str | None = None,
                 privater_seed: bytes | None = None, modus: str = "gym", half: bool = False,
                 solve_worker: int = LIVE_SOLVE_WORKER, queue_budget_s: float | None = None,
                 aufwaermen: bool = True):
        if modus not in ("gym", "live"):
            raise ValueError("modus muss 'gym' oder 'live' sein")
        if deadline_s is not None and solve_worker < 1:
            raise ValueError("solve_worker muss >= 1 sein")
        self.queue_budget_s = QUEUE_BUDGET_S if queue_budget_s is None else float(queue_budget_s)
        self.make_strat = make_strat
        self.min_pot_chips, self.iters, self.deadline_s = int(min_pot_chips), int(iters), deadline_s
        self.trace_pfad, self.modus, self.half = trace_pfad, modus, half
        self.solve_worker = int(solve_worker)
        self._privater_seed = privater_seed
        self._sitze: dict[int, _SitzZustand] = {}
        self._executor = (ThreadPoolExecutor(max_workers=self.solve_worker, thread_name_prefix="k2-solve")
                          if deadline_s else None)
        self._trace_lock = threading.Lock()
        self.aufwaerm_s: float | None = None
        if self.modus == "live" and aufwaermen:
            self.aufwaermen()

    def aufwaermen(self) -> float:
        """Kaltstart (torch-Import, CUDA-Kontext, Kernel-Compile) VOR der ersten Hand abtragen: gemessen kostet
        er 2-3 s und liess im frischen Prozess (K4: ein Prozess je Chunk) die ERSTE Plan-Entscheidung in die
        7,5-s-Deadline laufen (Sonde 2026-09-07: gesamt 5,6 s + Kaltstart > 7,5 s). Ein Mini-Solve auf einem
        festen Board, ohne Hand-Bezug; aendert keine Werte. Rueckgabe: Dauer in s."""
        from pokerbot.strategy.gpu_cfr import RiverCFRBatch, range_vector
        t0 = time.perf_counter()
        board = ["As", "Kd", "7c", "4h", "2s"]
        breit = {(a, b): 1.0 for a, b in (("Qh", "Qd"), ("Jh", "Jd"), ("Th", "9h"), ("8d", "8c"))}
        cfr = RiverCFRBatch([board], range_vector(breit).unsqueeze(0), range_vector(breit).unsqueeze(0),
                            pot=2000.0, eff_stack=19000.0, half=self.half, **BAUM_KW)
        cfr.solve(iters=2)
        _gpu_fertig(cfr)
        self.aufwaerm_s = time.perf_counter() - t0
        return self.aufwaerm_s

    # ---- Seed-Herkunft (Vertrag PRIVATE_SEED_QUELLE) -------------------------------------------------
    @property
    def private_seed_quelle(self) -> str:
        if self._privater_seed is not None:
            return "test_seed"
        return "os_urandom" if self.modus == "live" else "deck_hand_id_sitz"

    @property
    def private_seed_hex(self) -> str | None:
        """Zum Loggen (Fingerprint K4): explizit gesetzter Seed oder der Prozess-Seed (live); im Gym None
        (dort ist der Seed eine Funktion von hand_adresse+seat, nicht der Fabrik)."""
        if self._privater_seed is not None:
            return self._privater_seed.hex()
        return prozess_seed().hex() if self.modus == "live" else None

    def _seed_fuer(self, hand_adresse: str, seat: int) -> bytes:
        if self._privater_seed is not None:
            return self._privater_seed
        return prozess_seed() if self.modus == "live" else privater_seed_gym(hand_adresse, seat)

    # ---- Fabrik-Protokoll --------------------------------------------------------------------------
    def __call__(self, seat: int) -> StratFn:
        z = _SitzZustand(seat, self.make_strat(seat))
        self._sitze[seat] = z

        def d(st: dict) -> tuple[str, int | None]:
            return self._entscheide(z, st)
        d.zustand = z          # type: ignore[attr-defined] — Test-/Diagnose-Zugriff
        return d

    def letzter_plan(self, seat: int) -> GeloesterPlan | None:
        z = self._sitze.get(seat)
        return None if z is None else z.letzter_plan

    def letzter_trace(self, seat: int) -> dict | None:
        z = self._sitze.get(seat)
        return None if z is None else z.letzter_trace

    def basis_aufrufe(self, seat: int) -> int:
        z = self._sitze.get(seat)
        return 0 if z is None else z.basis_aufrufe

    def statistik(self, seat: int) -> dict[str, int]:
        """Zaehler je Sitz ueber alle Plan-Pot-Entscheidungen: fallback_status ('keiner' = Plan gespielt, offtree,
        deadline, fehler, hand_not_in_range) + 'plan_pot_entscheidungen'. hand_not_in_range / plan_pot_entscheidungen
        = Support-Abdeckung der echten Hero-Hand (G3-Kennzahl, Review-Fix)."""
        z = self._sitze.get(seat)
        return {} if z is None else dict(z.zaehler)

    # ---- Entscheidung ------------------------------------------------------------------------------
    def _basis(self, z: _SitzZustand, st: dict) -> tuple[str, int | None]:
        z.basis_aufrufe += 1
        return z.base(st)

    def _entscheide(self, z: _SitzZustand, st: dict) -> tuple[str, int | None]:
        aktiv, pot_river = ist_aktiviert(st, self.min_pot_chips)
        if not aktiv:
            return self._basis(z, st)                    # ausserhalb: Basis UNVERAENDERT, kein Trace
        t_start = time.perf_counter() if self.deadline_s else None
        hand_adresse, flags = hand_adresse_aus(st)
        gp, status, plan_flags, job = self._plan_fuer(z, st, hand_adresse)
        flags += plan_flags
        if gp is None:
            return self._fallback(z, st, status, hand_adresse, flags, t_start, job=job)
        nav = navigiere(gp, st)
        if nav.status != "ok":
            flags.append(f"nav:{nav.grund}")
            return self._fallback(z, st, nav.status, hand_adresse, flags, t_start, gp, job)
        return self._plan_entscheidung(z, st, gp, nav.pfad, hand_adresse, flags, t_start, job)

    def _plan_fuer(self, z: _SitzZustand, st: dict, hand_adresse: str
                   ) -> tuple[GeloesterPlan | None, str, list[str], _LaufenderSolve | None]:
        """Cache je Hand (Schluessel hand_adresse; Root-Kontrolle ueber pot_river/eff) -> sonst EIN Solve:
        Gym synchron; live ueber den laufenden Solve der Hand (geteilt, wenn er schon laeuft)."""
        flags: list[str] = []
        with z.lock:
            gp = z.cache.get(hand_adresse)
            if gp is not None and (gp.pot_river != pot_river_aus_state(st) or gp.eff != eff_stack_aus_state(st)
                                   or gp.button != int(st["button"])):
                flags.append(FLAG_CACHE_ROOT_ABWEICHUNG)
                gp = None
            if gp is not None:
                z.cache.move_to_end(hand_adresse)
                if gp.verspaetet:
                    flags.append(FLAG_PLAN_VERSPAETET_GENUTZT)
                return gp, "cache", flags, None
            if self._executor is not None:
                job = z.laufend.get(hand_adresse)
                if job is not None:
                    flags.append(FLAG_SOLVE_GETEILT)
                else:
                    job = self._starte_solve(z, st, hand_adresse)
        if self._executor is None:
            gp, status = self._loese_synchron(z, st, hand_adresse)
            job = None
        else:
            gp, status, wflags = self._warte_auf(z, job)
            flags += wflags
        if gp is None:
            return None, status, flags, job
        flags += list(gp.flags)
        with z.lock:
            self._cache_setze(z, hand_adresse, gp)
        return gp, "geloest", flags, job

    def _solve_kw(self) -> dict[str, Any]:
        return dict(iters=self.iters, half=self.half, min_pot_chips=self.min_pot_chips,
                    private_seed_quelle=self.private_seed_quelle,
                    deadline_status="iterations_deadline" if self.deadline_s is None else "eingehalten")

    def _cache_setze(self, z: _SitzZustand, hand_adresse: str, gp: GeloesterPlan) -> None:
        """Unter z.lock aufrufen. LRU je Sitz, CACHE_GROESSE Plaene."""
        z.cache[hand_adresse] = gp
        z.cache.move_to_end(hand_adresse)
        z.letzter_plan = gp
        while len(z.cache) > CACHE_GROESSE:
            z.cache.popitem(last=False)

    def _loese_synchron(self, z: _SitzZustand, st: dict, hand_adresse: str) -> tuple[GeloesterPlan | None, str]:
        """Gym: synchron, feste Iterationen (E5) — kein Zeitabbruch, deterministisch."""
        try:
            gp = loese_plan(st, z.seat, hand_adresse, **self._solve_kw())
        except Exception as e:  # noqa: BLE001 — ehrlicher Fallback mit Status statt Absturz im Spiel
            return None, f"fehler:{type(e).__name__}"
        return (gp, "geloest") if gp is not None else (None, "fehler:root_nicht_rekonstruierbar")

    def _starte_solve(self, z: _SitzZustand, st: dict, hand_adresse: str) -> _LaufenderSolve:
        """Unter z.lock aufrufen. Startet den EINEN Solve der Hand im Executor; das Ergebnis landet ueber den
        Done-Callback im Cache — auch wenn jeder Wartende in die Deadline lief (dann als 'verspaetet')."""
        job = _LaufenderSolve(fut=Future())
        job.fut = self._executor.submit(self._solve_job, job, st, z.seat, hand_adresse)
        z.laufend[hand_adresse] = job
        job.fut.add_done_callback(lambda fut, z=z, adr=hand_adresse, job=job: self._solve_fertig(z, adr, job, fut))
        return job

    def _solve_job(self, job: _LaufenderSolve, st: dict, seat: int, hand_adresse: str) -> GeloesterPlan | None:
        job.t_start = time.perf_counter()
        job.gestartet.set()
        return loese_plan(st, seat, hand_adresse, **self._solve_kw())

    def _solve_fertig(self, z: _SitzZustand, hand_adresse: str, job: _LaufenderSolve, fut: Future) -> None:
        with z.lock:
            z.laufend.pop(hand_adresse, None)
            try:
                gp = fut.result()
            except Exception:  # noqa: BLE001 — der Wartende meldet den Fehler-Status; Waisen bleiben still
                return
            if gp is None:
                return
            gp.verspaetet = job.verworfen
            self._cache_setze(z, hand_adresse, gp)

    def _warte_auf(self, z: _SitzZustand, job: _LaufenderSolve) -> tuple[GeloesterPlan | None, str, list[str]]:
        """Live-Warten mit Deadline AB SOLVE-START: erst bis zu queue_budget_s (Default QUEUE_BUDGET_S) auf den
        Start (Queue), dann die Rest-Deadline ab t_start. Ueberschreitung -> 'deadline' (+ Flag deadline_in_queue,
        wenn der Solve nicht einmal begann); das spaetere Ergebnis wird fuer diese Entscheidung verworfen."""
        if not job.gestartet.wait(timeout=self.queue_budget_s):
            self._markiere_verworfen(z, job)
            return None, "deadline", [FLAG_DEADLINE_IN_QUEUE]
        rest = self.deadline_s - (time.perf_counter() - job.t_start)
        try:
            gp = job.fut.result(timeout=max(0.0, rest))
        except FutureTimeout:
            self._markiere_verworfen(z, job)
            return None, "deadline", []
        except Exception as e:  # noqa: BLE001 — ehrlicher Fallback mit Status statt Absturz im Spiel
            return None, f"fehler:{type(e).__name__}", []
        return (gp, "geloest", []) if gp is not None else (None, "fehler:root_nicht_rekonstruierbar", [])

    @staticmethod
    def _markiere_verworfen(z: _SitzZustand, job: _LaufenderSolve) -> None:
        """Rennen Deadline vs. Fertigstellung: ist der Plan im selben Moment schon gecacht, wird er nachtraeglich
        als verspaetet markiert — die verpasste Entscheidung bleibt Basis."""
        with z.lock:
            job.verworfen = True
            if job.fut.done() and not job.fut.cancelled() and job.fut.exception() is None:
                gp = job.fut.result()
                if gp is not None:
                    gp.verspaetet = True

    def _fallback(self, z: _SitzZustand, st: dict, status: str, hand_adresse: str, flags: list[str],
                  t_start: float | None, gp: GeloesterPlan | None = None,
                  job: _LaufenderSolve | None = None) -> tuple[str, int | None]:
        a, amt = self._basis(z, st)
        key = _key_oder_roh(a, amt, st)
        vertrag = (status if status in ("offtree", "deadline", "hand_not_in_range") else "fehler")
        if status.startswith("fehler"):
            flags.append(status)
        trace = EntscheidungsTrace(basis=key, final=key, fallback_status=vertrag, offtree=(vertrag == "offtree"),
                                   deadline_status=self._deadline_status(t_start, vertrag == "deadline"),
                                   hand_adresse=hand_adresse, decision_addr=decision_addr_aus(st))
        self._schreibe_trace(z, trace, flags, gp, None, t_start, job=job)
        return a, amt

    def _plan_entscheidung(self, z: _SitzZustand, st: dict, gp: GeloesterPlan, pfad: tuple[ActionKey, ...],
                           hand_adresse: str, flags: list[str], t_start: float | None,
                           job: _LaufenderSolve | None) -> tuple[str, int | None]:
        hole = list(st["players"][st["to_act"]]["hole"])
        keys, probs, vflags = gp.verteilung(pfad, hole)
        flags += vflags
        if probs is None:
            # Heros echte Combo hat in der oeffentlichen Range Gewicht 0: der Solver hat dort KEINE Strategie
            # (Reach-0-Uniform, V10_FAKTEN B10) -> Basis, Vertrags-Status hand_not_in_range (Review-Fix).
            return self._fallback(z, st, "hand_not_in_range", hand_adresse, flags, t_start, gp, job)
        u = None if ist_degeneriert(probs) else private_u(self._seed_fuer(hand_adresse, z.seat), hand_adresse,
                                                          decision_addr_aus(st))
        wahl = sample_aus_verteilung(probs, u)
        a, amt = legalisiere(keys[wahl], st)
        final = _key_oder_roh(a, amt, st)
        trace = EntscheidungsTrace(basis=None, final=final, plan_verteilung=_verteilung_gemerged(keys, probs),
                                   legalitaet=final, sample_u=u, fallback_status="keiner",
                                   deadline_status=self._deadline_status(t_start, False),
                                   hand_adresse=hand_adresse, decision_addr=decision_addr_aus(st))
        self._schreibe_trace(z, trace, flags, gp, pfad, t_start, gewaehlt=keys[wahl], job=job)
        return a, amt

    def _deadline_status(self, t_start: float | None, verletzt: bool) -> str:
        if t_start is None:
            return "iterations_deadline"
        return "verletzt" if verletzt else "eingehalten"

    # ---- Trace -------------------------------------------------------------------------------------
    @staticmethod
    def _zeiten_ms(gp: GeloesterPlan | None, job: _LaufenderSolve | None) -> dict[str, float | None]:
        """Zeit-Attribution fuer den Live-Trace: queue (Submit -> Solve-Start), ranges/solve/gesamt des Plans."""
        out: dict[str, float | None] = {"queue": None, "ranges": None, "solve": None, "gesamt": None}
        if job is not None and job.queue_s() is not None:
            out["queue"] = round(job.queue_s() * 1000.0, 1)
        if gp is not None and gp.zeiten is not None:
            out.update(gp.zeiten.als_ms())
        return out

    def _schreibe_trace(self, z: _SitzZustand, trace: EntscheidungsTrace, flags: list[str],
                        gp: GeloesterPlan | None, pfad: tuple[ActionKey, ...] | None, t_start: float | None,
                        gewaehlt: ActionKey | None = None, job: _LaufenderSolve | None = None) -> None:
        """JSONL-Umschlag um den Vertrags-Trace: deterministischer Inhalt (KEINE Zeitstempel/Zeiten im Gym-Pfad;
        latenz_ms + zeiten_ms nur mit deadline_s)."""
        eintrag = {
            "version": PLAN_VERSION, "seat": z.seat, "hand_adresse": trace.hand_adresse,
            "decision_addr": trace.decision_addr, "fallback_status": trace.fallback_status, "offtree": trace.offtree,
            "deadline_status": trace.deadline_status, "flags": sorted(set(flags)),
            "basis": _key_json(trace.basis), "final": _key_json(trace.final), "legalitaet": _key_json(trace.legalitaet),
            "sample_u": trace.sample_u, "gewaehlter_arm": _key_json(gewaehlt),
            "plan_verteilung": None if trace.plan_verteilung is None else
            [[k.kind, k.chips, round(p, 9)] for k, p in trace.plan_verteilung],
            "pfad": None if pfad is None else [_key_json(k) for k in pfad],
            "root_hash": None if gp is None else gp.root_hash, "baum_hash": None if gp is None else gp.plan.baum_hash,
            "pot_river": None if gp is None else gp.pot_river, "eff": None if gp is None else gp.eff,
            "range_herkunft": None if gp is None else gp.plan.ranges.herkunft,
            "private_seed_quelle": self.private_seed_quelle,
        }
        if t_start is not None:
            eintrag["latenz_ms"] = round((time.perf_counter() - t_start) * 1000.0, 1)
            eintrag["zeiten_ms"] = self._zeiten_ms(gp, job)
        z.zaehler["plan_pot_entscheidungen"] += 1
        z.zaehler[trace.fallback_status] += 1
        z.letzter_trace = eintrag
        if self.trace_pfad:
            with self._trace_lock:
                os.makedirs(os.path.dirname(os.path.abspath(self.trace_pfad)), exist_ok=True)
                with open(self.trace_pfad, "a", encoding="utf-8") as f:
                    f.write(json.dumps(eintrag, sort_keys=True, ensure_ascii=False) + "\n")


def river_plan_guard(make_strat, min_pot_chips: int = DEFAULT_MIN_POT_CHIPS, iters: int = DEFAULT_ITERS,
                     deadline_s: float | None = None, trace_pfad: str | None = None,
                     privater_seed: bytes | None = None, modus: str = "gym",
                     solve_worker: int = LIVE_SOLVE_WORKER, queue_budget_s: float | None = None,
                     aufwaermen: bool = True) -> RiverPlanFabrik:
    """v10-K2 Wrapper-Fabrik (Signatur-Muster improver.river_play_guard): make(seat) -> d(st) -> (action, amount).

    modus 'gym' (Default): private_seed deterministisch aus (hand_adresse, seat) + festem Salz, feste
    Iterationen, kein Zeitabbruch. modus 'live': private_seed = os.urandom(16) je Prozess (Property
    private_seed_hex), deadline_s (Karte: 7,5 s) ab Solve-Start in `solve_worker` parallelen Solve-Threads
    (Default LIVE_SOLVE_WORKER = 1, gemessen: parallele Solves serialisieren sich); queue_budget_s = Wartezeit auf den
    Solve-START (Default QUEUE_BUDGET_S = 0,5 s, dann sofort Basis); aufwaermen (live, Default True) traegt den
    CUDA-Kaltstart vor der ersten Hand ab.
    privater_seed setzt beides ausser Kraft ('test_seed').
    Hero ausserhalb der oeffentlichen Range -> IMMER Basis mit Status hand_not_in_range (kein Knopf: die
    Reach-0-Uniform des Solvers ist keine Strategie, contracts.PolicyTable / V10_FAKTEN B10)."""
    return RiverPlanFabrik(make_strat, min_pot_chips, iters, deadline_s, trace_pfad, privater_seed, modus,
                           solve_worker=solve_worker, queue_budget_s=queue_budget_s, aufwaermen=aufwaermen)
