"""TURNIER-DOKTRIN — die Schicht zwischen ICM-Mathematik (icm.py) und dem Cash-Kern.

Aus den zwei Turnier-Büchern destilliert (Sklansky *Tournament Poker for Advanced Players* +
O'Kearney/Carter *Endgame Poker Strategy*), Baukarte 2026-08-04:

  * $EV statt cEV ab Hand 1: der Bubble-Faktor BF = |ΔEq_verlieren| / ΔEq_gewinnen macht aus
    jeder Pot-Odds-Schwelle r die Turnier-Schwelle BF·r / (BF·r + (1−r)) — reduziert korrekt auf
    r bei BF=1 (Cash/Heads-up) und auf BF/(BF+1) beim Flip (Buch-Anker: 1.18→54%, 2.56→72%,
    3.98→80%-nur-AA).
  * Der Aufschlag trifft NUR die Call-Seite (Gap Concept / Aggressor-Bias): Jam- und Open-Ranges
    bleiben Chip-EV — Fold Equity ist unter ICM die geschützte Equity-Form.
  * Heads-up ist BF exakt 1 → der validierte Prince-v2.2-Kern spielt das Endspiel unverändert.
  * All-in-Calls rechnen EXAKT (icm_call_threshold, drei Welten), nicht über die BF-Näherung.

Der Direktor führt Struktur (Blind-Level je Hand, Antes, Payouts), Eliminierung (Simultan-Busts:
der größere Start-Stack platziert höher — Sklansky-Regel) und die Tisch-Schrumpfung 9→2.
Kein Multi-Table, kein PKO, keine Zeit-Level: Produkt = Single-Table-SNG (Scope-Karte).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from pokerbot.engine.table import Table
from pokerbot.strategy.icm import bubble_factor, icm_call_threshold


# ---------------------------------------------------------------- Struktur
@dataclass(frozen=True)
class BlindLevel:
    sb: int
    bb: int
    ante: int = 0
    hands: int = 10          # die Sim zählt Hände, nicht Minuten


@dataclass(frozen=True)
class Structure:
    name: str
    levels: tuple
    payouts_pct: tuple       # z.B. (0.5, 0.3, 0.2)
    start_stack: int = 10_000
    buyin: float = 100.0

    def level_at(self, hand_no: int) -> BlindLevel:
        h = 0
        for lv in self.levels:
            h += lv.hands
            if hand_no < h:
                return lv
        return self.levels[-1]          # die letzte Stufe wiederholt sich

    def payouts(self, n_entries: int) -> list[float]:
        pool = self.buyin * n_entries
        return [round(p * pool, 2) for p in self.payouts_pct]


_SNG_LEVELS = (
    BlindLevel(50, 100, 0, 10), BlindLevel(75, 150, 0, 10), BlindLevel(100, 200, 25, 10),
    BlindLevel(150, 300, 40, 10), BlindLevel(200, 400, 50, 10), BlindLevel(300, 600, 75, 10),
    BlindLevel(400, 800, 100, 10), BlindLevel(600, 1200, 150, 10), BlindLevel(800, 1600, 200, 10),
    BlindLevel(1000, 2000, 300, 10),
)
SNG9 = Structure("sng9", _SNG_LEVELS, (0.5, 0.3, 0.2))
SNG6 = Structure("sng6", _SNG_LEVELS, (0.65, 0.35))
# Payout-Sensitivitäts-Arme (Doktrin: flach -> BFs explodieren; top-lastig -> Richtung Chip-EV)
FLAT9 = Structure("flat9", _SNG_LEVELS, (0.25, 0.20, 0.15, 0.14, 0.13, 0.13))
TOP_HEAVY9 = Structure("topheavy9", _SNG_LEVELS, (0.8, 0.2))


# ---------------------------------------------------------------- Doktrin-Formeln
def icm_required_equity(req_chip: float, bf: float) -> float:
    """Pot-Odds-Schwelle unter ICM: verlorene Chips zählen BF-fach.

    r' = bf·r / (bf·r + (1−r)).  Prüfsteine: bf=1 → r; r=0.5 → bf/(bf+1) (der Flip-Anker der
    Bücher: BF 2.56 → 71.9%).
    """
    if bf <= 1.0 or req_chip <= 0.0:
        return req_chip
    return (bf * req_chip) / (bf * req_chip + (1.0 - req_chip))


def pick_villain(stacks: list[float], hero: int, aggressor: int | None) -> int:
    """Der BF-Gegenpart: der Aggressor, wenn bekannt — sonst der größte gegnerische Stack
    (konservativ: gegen den Coverstack ist das Risiko maximal)."""
    if aggressor is not None and aggressor != hero and 0 <= aggressor < len(stacks):
        return aggressor
    best, best_s = hero, -1.0
    for i, s in enumerate(stacks):
        if i != hero and s > best_s:
            best, best_s = i, s
    return best


def icm_scaled_req(req_chip: float, obs: dict, to_call: float, pot: float) -> float:
    """Der EINE Einstiegspunkt für den Cash-Kern (sixmax._decide ruft genau diese Funktion).

    obs['icm'] = {'stacks': Start-of-Hand-Chips je Sitz, 'payouts': Rest-Payouts, 'seat': hero,
    'aggressor': Sitz|None}. Fehlt der Key, fasst der Kern diese Funktion nie an (Byte-Identität).
    All-in-Calls (to_call >= Hero-Reststack) rechnen die EXAKTE Drei-Welten-Schwelle; alles
    andere über den Bubble-Faktor gegen den relevanten Gegner.
    """
    ctx = obs.get("icm") or {}
    stacks = ctx.get("stacks")
    payouts = ctx.get("payouts")
    hero = ctx.get("seat", 0)
    if not stacks or not payouts or len(stacks) < 2:
        return req_chip
    villain = pick_villain(stacks, hero, ctx.get("aggressor"))
    my_stack = obs.get("my_stack") or 0
    if to_call >= my_stack > 0:
        # Call = All-in: exakt rechnen. behind = Start-of-Hand − schon investiert, fuer JEDEN
        # Sitz (nur Hero+Villain abzuziehen liess Dritt-Einsaetze doppelt existieren — in den
        # behind-Stacks UND im Pot; MTT-Review-Fund, mit Antes feuert das an jeder FT).
        inv = ctx.get("invested") or {}
        behind = [max(0.0, s - inv.get(i, 0.0)) for i, s in enumerate(stacks)]
        tc_cap = min(to_call, behind[hero])
        # Uncalled-Exzess des Villain-Shoves geht in Wahrheit an ihn ZURUECK — ihn im Pot zu
        # lassen schenkte Hero in der Gewinn-Welt fremde Chips (zu lockere Cover-Calls).
        excess = max(0.0, to_call - tc_cap)
        behind[villain] += excess
        return icm_call_threshold(behind, payouts, hero, villain,
                                  to_call=tc_cap, pot_before=max(0.0, pot - excess))
    bf = bubble_factor(stacks, payouts, hero, villain)
    if bf == float("inf"):
        return 1.0            # ICM-Gewinn <= 0: kein Call kann richtig sein (NaN-Pfad-Waechter)
    # ANTEILIGES Risiko-Premium (μ-Experiment 1: voller BF auf jeden Kleinst-Call -> Ueberstraffung,
    # mehr 4.-Plaetze statt weniger — er ueberlebte zur Bubble und blindete aus). Die Buecher wenden
    # den BF auf ALL-IN-Risiko an; bei einem Teil-Call steht nur to_call/Stack im Feuer:
    #   BF_eff = 1 + (BF-1) * (to_call / Stack)
    # All-in -> voller BF (deckt sich mit der exakten Drei-Welten-Rechnung), 2bb von 30bb -> ~Cash.
    frac_at_risk = min(1.0, to_call / my_stack) if my_stack > 0 else 1.0
    bf_eff = 1.0 + (bf - 1.0) * frac_at_risk
    return icm_required_equity(req_chip, bf_eff)


def icm_pressure_mult(obs: dict, villains: list[int] | None = None) -> float:
    """Steal-Verbreiterung des Coverstacks (Doktrin 9 + User-These: die anderen SPIELEN ICM).

    Stehen die Gegner unter hohem Bubble-Faktor GEGEN UNS (wir covern sie), koennen sie kaum
    callen — ihre Zwangs-Tightness ist erntbare Fold Equity. Multiplikator auf die Open-Fraktion:
    1 + 0.5·(mittlerer BF der Gegner gegen uns − 1), gedeckelt bei 1.6. BF=1 ueberall -> 1.0
    (Cash byte-identisch; der Hook feuert ohnehin nur mit obs['icm']).
    """
    ctx = obs.get("icm") or {}
    if "pressure_mult" in ctx:
        # GROSSE Felder (MTT): der Sim rechnet den Multiplikator EINMAL pro Hand vor (exakte
        # BFs sind ab ~13 Spielern unbezahlbar pro Entscheidung); SNG-Pfad unveraendert.
        return float(ctx["pressure_mult"])
    stacks = ctx.get("stacks")
    payouts = ctx.get("payouts")
    hero = ctx.get("seat", 0)
    if not stacks or not payouts or len(stacks) < 3:
        return 1.0
    # villains: nur DIESE Gegner mitteln (MTT: die am eigenen Tisch — Off-Table-Stacks koennen
    # nicht auf unsere Opens folden und wuerden den Multiplikator verzerren); None = alle (SNG).
    cand = villains if villains is not None else range(len(stacks))
    bfs = [bubble_factor(stacks, payouts, v, hero)
           for v in cand if v != hero and stacks[v] > 0]
    bfs = [b for b in bfs if b != float("inf")]
    if not bfs:
        return 1.0
    avg = sum(bfs) / len(bfs)
    return min(1.6, 1.0 + 0.5 * (avg - 1.0))


def bf_matrix(stacks: list[float], payouts: list[float]) -> list[list[float]]:
    """Alle Paar-BFs (Diagnose/Reports; die Entscheidung selbst holt nur den einen Gegner)."""
    n = len(stacks)
    return [[1.0 if i == j else bubble_factor(stacks, payouts, i, j) for j in range(n)]
            for i in range(n)]


# ---------------------------------------------------------------- Direktor
@dataclass
class _Entrant:
    name: str
    stack: int
    alive: bool = True
    place: int | None = None


class Director:
    """Führt EIN Single-Table-Turnier: Level, Antes, Eliminierung, Schrumpfung, Payouts.

    Pro Hand liefert `next_table()` eine frische Table NUR der Überlebenden (rebuy=False) mit den
    aktuellen Blinds/Antes; der Button wandert im Uhrzeigersinn der Überlebenden (vereinfachte
    Regel statt Dead-Button — NOTES.md). `after_hand(table)` sammelt Stacks ein, vergibt Plätze
    (Simultan-Busts: größerer Start-Stack platziert höher) und meldet, ob es weitergeht.
    """

    def __init__(self, structure: Structure, names: list[str], seed: int | None = None):
        self.structure = structure
        self.entrants = [_Entrant(nm, structure.start_stack) for nm in names]
        self.n_entries = len(names)
        self.hand_no = 0
        self.seed = seed
        self._button_name: str | None = None
        self._next_place = len(names)          # der nächste zu vergebende (schlechteste) Platz
        self._start_stacks: dict[str, int] = {}

    # ---- Zustand
    def alive(self) -> list[_Entrant]:
        return [e for e in self.entrants if e.alive]

    def payouts_remaining(self) -> list[float]:
        """Die noch nicht ausgezahlten Preisgelder (für die ICM-Rechnung der Verbliebenen)."""
        pays = self.structure.payouts(self.n_entries)
        return pays[: len(self.alive())] if len(self.alive()) <= len(pays) else pays

    def over(self) -> bool:
        return len(self.alive()) <= 1

    # ---- Ablauf
    def next_table(self) -> Table:
        live = self.alive()
        lv = self.structure.level_at(self.hand_no)
        names = [e.name for e in live]
        stacks = [e.stack for e in live]
        # Button-Rotation über NAMEN (Sitze ändern sich mit jeder Eliminierung)
        if self._button_name in names:
            btn = (names.index(self._button_name) + 1) % len(names)
        else:
            btn = 0
        t = Table(names, starting_stack=self.structure.start_stack, sb=lv.sb, bb=lv.bb,
                  seed=None if self.seed is None else (self.seed * 100003 + self.hand_no),
                  stacks=stacks, ante=lv.ante, rebuy=False)
        t.button = btn - 1                      # start_hand rückt +1 vor
        t.start_hand()
        self._button_name = t.seats[t.button].name
        self._start_stacks = {s.name: s.stack + s.committed_total for s in t.seats}
        self.hand_no += 1
        return t

    def icm_ctx(self, table: Table, seat: int, aggressor: int | None) -> dict:
        """Der obs['icm']-Kontext für EINEN Entscheider (Start-of-Hand-Stacks, Rest-Payouts)."""
        return {
            "stacks": [float(self._start_stacks[s.name]) for s in table.seats],
            "payouts": self.payouts_remaining(),
            "seat": seat,
            "aggressor": aggressor,
            "invested": {i: float(s.committed_total) for i, s in enumerate(table.seats)},
        }

    def after_hand(self, table: Table) -> None:
        by_name = {e.name: e for e in self.entrants}
        busted = []
        for s in table.seats:
            e = by_name[s.name]
            e.stack = s.stack
            if s.stack <= 0:
                busted.append(e)
        # Simultan-Busts: der größere START-Stack platziert höher (bekommt die BESSERE Zahl)
        busted.sort(key=lambda e: self._start_stacks.get(e.name, 0))
        for e in busted:
            e.alive = False
            e.place = self._next_place
            self._next_place -= 1
        if len(self.alive()) == 1:
            self.alive()[0].place = 1
            self.alive()[0].alive = False       # Turnier vorbei; Zustand eingefroren

    def results(self) -> list[dict]:
        pays = self.structure.payouts(self.n_entries)
        out = []
        for e in sorted(self.entrants, key=lambda x: x.place or 999):
            payout = pays[e.place - 1] if e.place and e.place <= len(pays) else 0.0
            out.append({"name": e.name, "place": e.place, "payout": payout})
        return out
