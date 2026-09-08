"""K1 — HERO-LIKELIHOOD-REPLAY: Heros OEFFENTLICHE Range am River-Beginn (v10, Karte docs/V10_BUILD_CARD.md K1;
Entscheidungen E3/E6/E11; Fakten docs/V10_FAKTEN.md A4/A5/B8/B9).

    r_river(h)  ∝  r_0(h) · M_board(h) · Π_t π_exec(a_t | s_t, h)        ueber alle Hero-Aktionen VOR dem River.

Drei Schichten, jede fuer sich pruefbar:
  1. PRIOR + BOARD-MASKE = exakt der RangeTracker (range_tracker.py _init_preflop / _remove_dead / _normalize —
     Klassen-Prior nach Raise-Anzahl + Button, Preflop-Aktionen veraendern die Range nicht, V10_FAKTEN A4).
  2. BASIS-LIKELIHOOD (approximiert, GEKENNZEICHNET): das Advisor-Modell des Trackers — P(bet)/P(check) via
     p_bet_batch, P(fold/call/raise) via p_defense_batch — ohne Sampling, ohne Nebenwirkung auf RNG/Tracker.
     Rollen laut E11: Heros p_bet nach INITIATIVE (wie bot.decide, bot.py:771-776), p_defense nach POSITION mit
     der ECHTEN Bet-Groesse (bot.py:600-603). `TRACKER_PARITAET` schaltet auf die Tracker-Konvention (Position,
     size_faced 0.66) — dann ist das Ergebnis bei guards=() byte-gleich zur Tracker-Hero-Range (Test).
     Daempfung (TRACKER_ALPHA / TRACKER_AGGRO_FULL) und die legality-only-Regel fuer Raise-facing-Bet werden
     1:1 vom Tracker uebernommen (im Gym-Kanal ALPHA=1.0 -> keine Daempfung).
  3. GUARD-TRANSFORMATIONEN EXAKT als Verschiebung von Aktionsmasse je Hero-Combo (Karte K1):
       turn_wert:   π_exec(b*|h) = π_vor(bet|h) + 1_C(h)·π_vor(check|h);  π_exec(check|h) = (1−1_C(h))·π_vor(check|h)
       sel_m15:     π_exec(call|h) = π_vor(call|h) + 1_C(h)·π_vor(fold|h); Raise-Anteil bleibt
       button_disziplin: Prior UNVERAENDERT (Open 2,5x fuer JEDE Combo = keine Selektion)
     C(h) BITGENAU wie improver.turn_wert_guard / improver.sel_guard (E6): derselbe CPU-MC-Pfad
     (equity_vs_weighted_range, iters=160, improver._spot_rng mit der HYPOTHETISCHEN Combo als Hero-Hole), mit
     der DAMALIGEN Villain-Range (RangeTracker auf dem History-Schnitt VOR der Hero-Aktion; das Card-Removal je
     Combo macht equity_vs_weighted_range selbst). Groessenvergleich b* vs beobachtete Aktion ueber FINALE Chips
     (Engine-Clamp via contracts.kanonisiere), nie ueber Labels.

INVARIANZ (bindend): dieser Pfad liest NIE Heros echte Hole-Karten. Alle Knoten-Zustaende tragen '??' als Hole;
die hypothetische Combo wird nur fuer C(h) eingesetzt. Gleiche oeffentliche Historie, andere Hero-Hand -> identische
Range (Test). Keine Hero-Hand-Injektion (contracts.RangeState herkunft 'k1_likelihood', hero_injiziert False).

Kanaele: Engine-State (HeadsUpGame.state()) UND Adapter-State (gtow_to_state) — genutzt wird nur die Schnittmenge
player/action/street/to + deal.street (contracts-Docstring; V10_FAKTEN A2/B16). Der Call-Betrag kommt aus der
Level-Differenz, das Board aus state['board'].
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from knowledge_base.math.formulas import equity_needed_to_call
from pokerbot.autogym.improver import _RANK_ORD, _spot_rng      # DIE Referenz fuer bitgenaues C(h) (E6)
from pokerbot.engine.equity import equity_vs_weighted_range
from pokerbot.engine.evaluator import evaluate
from pokerbot.strategy import range_tracker as rt
from pokerbot.strategy.contracts import (ActionKey, PolicyTable, RangeState, combo_kanonisch, kanonisiere,
                                         kanonisiere_history_eintrag, konfig_hash_aus)
from pokerbot.strategy.range_tracker import RangeTracker, _board_at

K1_VERSION = "k1-hero-range-1"

# ---- Guard-Namen (= pargate-Registrierung der r6_button-Kette: sel_m15 -> turn_wert -> button_disziplin)
GUARD_SEL_FLOP = "sel_m15"
GUARD_TURN_WERT = "turn_wert"
GUARD_BUTTON = "button_disziplin"
STANDARD_GUARDS: tuple[str, ...] = (GUARD_SEL_FLOP, GUARD_TURN_WERT, GUARD_BUTTON)
BEKANNTE_GUARDS = frozenset(STANDARD_GUARDS)

# ---- Guard-Parameter: Spiegel von pargate._wickle ('sel_m15' = sel_guard(margin=0.15); 'turn_wert' =
# turn_wert_guard(frac=0.66, min_eq=0.60, iters=160)) und der improver-Defaults (sel_guard iters=160).
SEL_M15_MARGE = 0.15
TURN_WERT_FRAC = 0.66
TURN_WERT_MIN_EQ = 0.60
GUARD_EQUITY_ITERS = 160
# treys-Rangklassen (improver.turn_wert_guard: 1=SF .. 6=Trips, 7=Two Pair, 8=Pair, 9=High Card)
TREYS_TRIPS_ODER_BESSER = 6
TREYS_TWO_PAIR = 7
TREYS_PAIR = 8

# ---- Rollen-/Groessen-Konventionen (E11 / V10_FAKTEN B9)
ROLLE_INITIATIVE = "initiative"      # bot.decide: 'IP' iff Hero war letzter Preflop-Raiser
ROLLE_POSITION = "position"          # RangeTracker: 'IP' iff seat == button
SIZE_ECHT = "echt"                   # bot.decide: to_call / (pot - to_call)
SIZE_TRACKER = "tracker_066"         # RangeTracker._p_call: fest 0.66
TRACKER_SIZE_FACED = 0.66

STATUS_OK = "ok"                     # jeder Hero-Postflop-Knoten modelliert
STATUS_TEILWEISE = "teilweise"       # legality-only-Schritte (Advisor fehlt / Raise-facing-Bet)
STATUS_FEHLGESCHLAGEN = "fehlgeschlagen"

_ALLE_KARTEN = tuple(r + s for r in "23456789TJQKA" for s in "shdc")
try:
    from treys import Evaluator as _TreysEval
    _KLASSE = _TreysEval().get_rank_class
except Exception:  # noqa: BLE001 — improver: ohne treys feuert turn_wert nie
    _KLASSE = None


@dataclass(frozen=True)
class Konvention:
    """Wie die Basis-Likelihood befragt wird. K1-Standard = E11; TRACKER_PARITAET = Tracker-Konvention.
    raise_modelliert=False: eine Hero-Raise facing Bet ist legality-only (x1, heur) wie im Tracker (o3-safe);
    True: Advisor-P_raise wird als Likelihood benutzt (G3-Experimentarm)."""
    rolle_bet: str = ROLLE_INITIATIVE
    size_faced: str = SIZE_ECHT
    raise_modelliert: bool = False

    def __post_init__(self) -> None:
        if self.rolle_bet not in (ROLLE_INITIATIVE, ROLLE_POSITION):
            raise ValueError(f"rolle_bet {self.rolle_bet!r}")
        if self.size_faced not in (SIZE_ECHT, SIZE_TRACKER):
            raise ValueError(f"size_faced {self.size_faced!r}")


K1_KONVENTION = Konvention()
TRACKER_PARITAET = Konvention(ROLLE_POSITION, SIZE_TRACKER, False)


# ================================================================ Replay der oeffentlichen Historie
@dataclass(frozen=True)
class Knoten:
    """Ein Hero-Entscheidungsknoten VOR dem River: oeffentlicher Zustand vor der Aktion + die beobachtete Aktion.
    zustand ist Engine-foermig (players/legal/history-Prefix), Holes beider Sitze '??'."""
    index: int                  # Position der Aktion in st0['history'] (== len(zustand['history']))
    street: str
    seat: int
    zustand: dict
    beobachtet: ActionKey
    facing: bool
    size_cls: str               # 'jam' | 'normal' (Tracker-Jam-Read fuer RAISE_NARROW)


class _Replay:
    """Fuehrt die Engine-Buchhaltung (game.py:141-181, 207-215) ueber die oeffentliche Historie nach:
    Raise-TO-Level je Strasse, Call = Level-Differenz, min_raise-Regel, Blinds als Startlevel."""

    def __init__(self, st0: Mapping[str, Any]):
        pl = st0["players"]
        self.bb = int(st0.get("bb", 100))
        self.sb = int(st0.get("sb") or self.bb // 2)
        self.button = int(st0["button"])
        self.board_voll = list(st0["board"])
        self.hand_id = st0.get("hand_id")
        # Startstack = stack + committed_total (invariant ueber die Hand, solange kein Refund lief;
        # ein Refund setzt einen All-in voraus, nach dem es keinen Hero-Knoten mehr gibt)
        self.start = [int(pl[s]["stack"]) + int(pl[s]["committed_total"]) for s in (0, 1)]
        self.ct = [0, 0]
        self.cs = [0, 0]
        self.street = "preflop"
        self.current_bet = 0
        self.min_raise = self.bb
        self.to_act = self.button
        self._setze(self.button, self.sb)
        self._setze(1 - self.button, self.bb)
        self.current_bet = self.bb

    def _setze(self, seat: int, betrag: int) -> None:
        betrag = min(betrag, self.start[seat] - self.ct[seat])      # Engine: _commit kappt am Stack
        self.ct[seat] += betrag
        self.cs[seat] += betrag

    def stack(self, seat: int) -> int:
        return self.start[seat] - self.ct[seat]

    def all_in(self, seat: int) -> bool:
        return self.stack(seat) <= 0

    def pot(self) -> int:
        return self.ct[0] + self.ct[1]

    def board(self) -> list[str]:
        return _board_at(self.board_voll, self.street) if self.street != "preflop" else []

    def deal(self, street: str) -> None:
        self.street = street
        self.cs = [0, 0]
        self.current_bet = 0
        self.min_raise = self.bb
        self.to_act = 1 - self.button                                 # postflop: OOP zuerst

    def aktion(self, seat: int, key: ActionKey) -> None:
        if key.kind == "call":
            self._setze(seat, max(0, self.current_bet - self.cs[seat]))
        elif key.kind == "raise_to":
            self._setze(seat, max(0, key.chips - self.cs[seat]))
            zuwachs = self.cs[seat] - self.current_bet
            self.current_bet = self.cs[seat]
            if zuwachs >= self.min_raise:
                self.min_raise = zuwachs
        self.to_act = 1 - seat

    def legal(self, seat: int) -> dict:
        to_call = self.current_bet - self.cs[seat]
        stack = self.stack(seat)
        can_raise = stack > to_call and not self.all_in(1 - seat)
        is_bet = self.current_bet == 0
        raise_min = raise_max = None
        if can_raise:
            raise_max = self.cs[seat] + stack
            raise_min = min(self.cs[seat] + self.bb, raise_max) if is_bet else min(self.current_bet + self.min_raise, raise_max)
        return {"to_act": seat, "to_call": to_call, "can_fold": to_call > 0, "can_check": to_call == 0,
                "can_call": to_call > 0, "call_amount": min(to_call, stack), "can_raise": can_raise,
                "is_bet": is_bet, "raise_min": raise_min, "raise_max": raise_max, "pot": self.pot()}

    def zustand(self, seat: int, history_prefix: list) -> dict:
        """Oeffentlicher Engine-foermiger State VOR der Aktion von `seat` — OHNE Hole-Karten ('??')."""
        spieler = [{"idx": s, "name": f"S{s}", "stack": self.stack(s), "hole": ["??", "??"],
                    "folded": False, "all_in": self.all_in(s), "committed_street": self.cs[s],
                    "committed_total": self.ct[s], "is_button": s == self.button} for s in (0, 1)]
        st = {"hand_no": 0, "button": self.button, "street": self.street, "board": self.board(),
              "pot": self.pot(), "current_bet": self.current_bet, "to_act": seat, "hand_over": False,
              "result": None, "sb": self.sb, "bb": self.bb, "history": list(history_prefix),
              "players": spieler, "legal": self.legal(seat)}
        if self.hand_id is not None:
            st["hand_id"] = self.hand_id
        return st


def schneide_am_river(st0: Mapping[str, Any]) -> dict | None:
    """History-Schnitt am River-Deal inklusive (wie improver._river_spot_und_frage:428-436); None ohne River-Deal
    (Engine: stiller All-in-Run-out hat kein deal-Event)."""
    hist = st0.get("history", []) or []
    schnitt = next((i for i, h in enumerate(hist) if h.get("action") == "deal" and h.get("street") == "river"), None)
    if schnitt is None:
        return None
    st = dict(st0)
    st["history"] = list(hist[:schnitt + 1])
    return st


def ereignisse(st0: Mapping[str, Any], hero: int) -> tuple[list[tuple], int]:
    """Die K1-Ereignisfolge bis zum River-Deal: ('deal', street) und ('knoten', Knoten) fuer jeden Hero-Knoten
    auf Flop/Turn (Preflop-Aktionen veraendern die Range nicht — Tracker-Regel, button_disziplin = Prior
    unveraendert). Rueckgabe (ereignisse, pot_river). st0 muss am River-Deal geschnitten sein."""
    rp = _Replay(st0)
    hist = st0.get("history", []) or []
    out: list[tuple] = []
    for i, h in enumerate(hist):
        key = kanonisiere_history_eintrag(h)
        if key is None:                                                # deal
            street = str(h.get("street"))
            rp.deal(street)
            out.append(("deal", street))
            if street == "river":
                break
            continue
        seat = int(h["player"])
        if key.kind == "fold":
            break                                                      # Hand endet — kein River
        if seat == hero and rp.street in ("flop", "turn"):
            zustand = rp.zustand(seat, hist[:i])
            facing = rp.current_bet - rp.cs[seat] > 0
            size_cls = _size_cls(rp, seat, key)
            out.append(("knoten", Knoten(i, rp.street, seat, zustand, key, facing, size_cls)))
        rp.aktion(seat, key)
    return out, rp.pot()


def _size_cls(rp: _Replay, seat: int, key: ActionKey) -> str:
    """Tracker-Jam-Read (range_tracker.py:326-330): 'jam' iff committed + inc >= start - 1."""
    if key.kind != "raise_to":
        return "normal"
    inc = max(0, key.chips - rp.cs[seat])
    return "jam" if rp.ct[seat] + inc >= rp.start[seat] - 1 else "normal"


def knoten_liste(st0: Mapping[str, Any], hero: int) -> list[Knoten]:
    """Nur die Hero-Knoten (fuer das Orakel / Tests)."""
    return [k for art, k in ereignisse(st0, hero)[0] if art == "knoten"]


# ================================================================ Bitgenaue Guard-Bedingungen C(h)
def _mit_hole(zustand: Mapping[str, Any], combo: Sequence[str]) -> dict:
    """Kopie des Knoten-Zustands mit der HYPOTHETISCHEN Combo als Hero-Hole — nur fuer improver._spot_rng /
    equity (beide lesen players[to_act]['hole']). Der Original-Zustand bleibt hole-frei."""
    st = dict(zustand)
    seat = st["to_act"]
    spieler = [dict(p) for p in st["players"]]
    spieler[seat]["hole"] = list(combo)
    st["players"] = spieler
    return st


def _guard_equity(zustand: Mapping[str, Any], combo: Sequence[str], villain_range: Mapping) -> float:
    """Exakt der Guard-Aufruf: equity_vs_weighted_range(hole, tracker_range, board, iters=160, rng=_spot_rng(st))."""
    st_h = _mit_hole(zustand, combo)
    return equity_vs_weighted_range(list(combo), villain_range, st_h["board"], iters=GUARD_EQUITY_ITERS,
                                    rng=_spot_rng(st_h))


def bedingung_turn_wert(zustand: Mapping[str, Any], combo: Sequence[str], villain_range: Mapping) -> bool:
    """C(h) des turn_wert_guard (improver.py:256-272) fuer eine hypothetische Combo: starke Made Hand
    (Trips+ | Two Pair mit Hole-Beteiligung | Ueberpaar) UND MC-Equity vs Tracker-Range >= 0.60.
    Bitgenau: dieselbe treys-Klasse, derselbe MC-Pfad, derselbe spot-gebundene RNG."""
    if _KLASSE is None or not villain_range:
        return False
    try:
        board = zustand["board"]
        hole = list(combo)
        kl = _KLASSE(evaluate(board, hole))
        hole_pair = hole[0][0] == hole[1][0]
        board_ranks = [b[0] for b in board]
        beteiligt = hole_pair or any(hc[0] in board_ranks for hc in hole)
        ueberpaar = (hole_pair and kl == TREYS_PAIR
                     and _RANK_ORD[hole[0][0]] > max(_RANK_ORD[r] for r in board_ranks))
        if not (kl <= TREYS_TRIPS_ODER_BESSER or (kl == TREYS_TWO_PAIR and beteiligt) or ueberpaar):
            return False
        eq = _guard_equity(zustand, combo, villain_range)
        return eq == eq and eq >= TURN_WERT_MIN_EQ
    except Exception:  # noqa: BLE001 — der Guard schweigt bei Fehlern (improver.py:274-275)
        return False


def bedingung_sel(zustand: Mapping[str, Any], combo: Sequence[str], villain_range: Mapping,
                  marge: float = SEL_M15_MARGE) -> bool:
    """C(h) des sel_guard (improver.py:140-148): MC-Equity vs Tracker-Range >= Pot-Odds + Marge."""
    if not villain_range:
        return False
    try:
        me = zustand["players"][zustand["to_act"]]
        to_call = max(0, zustand["current_bet"] - me["committed_street"])
        if to_call <= 0:
            return False
        eq = _guard_equity(zustand, combo, villain_range)
        return eq == eq and eq >= equity_needed_to_call(zustand["pot"], to_call) + marge
    except Exception:  # noqa: BLE001
        return False


def turn_wert_anwendbar(zustand: Mapping[str, Any]) -> bool:
    """Trigger-Lage des turn_wert_guard (ohne die Basis-Aktion): Turn, to_call==0, beide Stacks > 0."""
    me = zustand["players"][zustand["to_act"]]
    opp = zustand["players"][1 - zustand["to_act"]]
    to_call = max(0, zustand["current_bet"] - me["committed_street"])
    return (zustand["street"] == "turn" and to_call == 0 and _KLASSE is not None
            and me["stack"] > 0 and opp["stack"] > 0)


def turn_wert_ziel(zustand: Mapping[str, Any]) -> ActionKey:
    """b* des Guards: ('bet', int(0.66*pot)) durch den Engine-Clamp (contracts.kanonisiere = game.py:170)."""
    return kanonisiere("bet", int(TURN_WERT_FRAC * zustand["pot"]), zustand)


def sel_anwendbar(zustand: Mapping[str, Any]) -> bool:
    """Trigger-Lage des sel_m15-Guards: Flop, facing Bet."""
    me = zustand["players"][zustand["to_act"]]
    return zustand["street"] == "flop" and zustand["current_bet"] - me["committed_street"] > 0


# ================================================================ Basis-Likelihood (Advisor, ohne Sampling)
def _hat_initiative(zustand: Mapping[str, Any], seat: int) -> bool:
    """bot.PokerBot._has_initiative (bot.py:934-943): letzter Preflop-Aggressor."""
    pfr = []
    for h in zustand.get("history", []) or []:
        if h.get("action") == "deal":
            break
        if h.get("action") in ("raise", "bet", "allin"):
            pfr.append(h.get("player"))
    return bool(pfr) and pfr[-1] == seat


def rolle_bet(zustand: Mapping[str, Any], seat: int, konvention: Konvention) -> str:
    if konvention.rolle_bet == ROLLE_INITIATIVE:
        return "IP" if _hat_initiative(zustand, seat) else "OOP"
    return "IP" if seat == zustand["button"] else "OOP"


def _rolle_position(zustand: Mapping[str, Any], seat: int) -> str:
    return "IP" if seat == zustand["button"] else "OOP"


def _size_faced(zustand: Mapping[str, Any], seat: int, konvention: Konvention) -> float:
    if konvention.size_faced == SIZE_TRACKER:
        return TRACKER_SIZE_FACED
    me = zustand["players"][seat]
    to_call = max(0, zustand["current_bet"] - me["committed_street"])
    return to_call / max(1.0, zustand["pot"] - to_call)            # bot.py:601: Bet relativ zum getroffenen Pot


def _advisor_modul(advisor):
    if advisor is not None:
        return advisor
    try:
        from pokerbot.strategy import advisor as _adv
        return _adv
    except Exception:  # noqa: BLE001
        return None


def _p_bet_alle(adv, combos, board, role, street) -> dict | None:
    """P(bet) je Combo; None = Advisor fuer diese Strasse nicht verfuegbar (-> legality-only wie im Tracker).
    Batch-Pfad wenn vorhanden, sonst Einzelaufrufe (Memo-identisch, research/advisor_batch_check.py)."""
    if adv is None or not adv.available(street):
        return None
    fn = getattr(adv, "p_bet_batch", None)
    try:
        if fn is not None:
            return {tuple(c): v for c, v in fn(list(combos), board, role, street).items()}
        return {tuple(c): adv.p_bet([c[0], c[1]], board, role, street) for c in combos}
    except Exception:  # noqa: BLE001
        return None


def _p_defense_alle(adv, combos, board, role, size_faced, street) -> dict | None:
    """(P_fold, P_call, P_raise) je Combo; None = Defense-Advisor nicht verfuegbar."""
    if street not in ("flop", "turn", "river") or adv is None:
        return None
    if not getattr(adv, "defense_available", lambda: False)():
        return None
    fn = getattr(adv, "p_defense_batch", None)
    try:
        if fn is not None:
            return {tuple(c): v for c, v in fn(list(combos), board, role, size_faced, street).items()}
        return {tuple(c): adv.p_defense([c[0], c[1]], board, role, size_faced, street) for c in combos}
    except Exception:  # noqa: BLE001
        return None


# ================================================================ Knoten-Modell = Bausteine von (a)
@dataclass(frozen=True)
class KnotenModell:
    """Die AUSGEFUEHRTE Politik an einem Hero-Knoten je Combo — Basis (Advisor) + exakte Guard-Verschiebung.

    tabelle: PolicyTable ueber die legalen Aktionsklassen. Die Basis ist GROESSEN-AGNOSTISCH (der Advisor kennt
    nur bet-vs-check), deshalb traegt die raise_to-Spalte die GESAMTE Bet-Masse; ihr Chip-Label ist b* (Guard-
    Ziel) bzw. — ohne Guard — die Referenzgroesse int(0.66*pot) nach Clamp / raise_min (facing). Die Likelihood
    einer BEOBACHTETEN Groesse x ≠ b* liefert `likelihood()` (Basis-Masse ohne Guard-Anteil).
    basis: rohe Advisor-Verteilung je Combo VOR der Verschiebung (bet/check: (p_check, p_bet); facing:
    (pf, pc, pr)); None = Advisor fehlt (legality-only).
    c_maske: Combos mit C(h)=True. guard: greifender Guard oder None. guard_ziel: b* (turn_wert) oder None."""
    tabelle: PolicyTable
    facing: bool
    guard: str | None
    guard_ziel: ActionKey | None
    c_maske: frozenset
    basis: dict
    kann_raisen: bool

    def likelihood(self, combo: Sequence[str], beobachtet: ActionKey) -> float | None:
        """π_exec(beobachtet | combo). None = nicht modelliert (Aufrufer: legality-only, x1)."""
        c = tuple(combo)
        in_c = combo_kanonisch(*c) in self.c_maske
        b = self.basis.get(c)
        if not self.facing:
            p_bet = None if b is None else b[1]
            if beobachtet.kind == "check":
                if in_c:
                    return 0.0                              # C(h): der Guard bettet SICHER — exakt, auch ohne Advisor
                return None if p_bet is None else 1.0 - p_bet
            if beobachtet.kind == "raise_to":
                trifft_ziel = self.guard_ziel is not None and beobachtet.chips == self.guard_ziel.chips
                if in_c and trifft_ziel:
                    return 1.0                              # Basis-Bet + verschobene Check-Masse = alles
                return p_bet                                # Basis-Groesse (auch x ≠ b*): nur die Basis-Masse
            return None                                     # fold bei to_call==0: vom Modell nicht erfasst
        if b is None:
            return None
        pf, pc, pr = b
        if beobachtet.kind == "fold":
            return 0.0 if in_c else pf
        if beobachtet.kind == "call":
            return pc + (pf if in_c else 0.0) + (0.0 if self.kann_raisen else pr)
        if beobachtet.kind == "raise_to":
            return pr if self.kann_raisen else None
        return None


def knoten_modell(zustand: Mapping[str, Any], seat: int, guards: Sequence[str] = STANDARD_GUARDS,
                  konvention: Konvention = K1_KONVENTION, combos: Sequence[tuple] | None = None,
                  advisor=None) -> KnotenModell:
    """Baut die ausgefuehrte Politik am Knoten (ohne Sampling, ohne Nebenwirkung auf RNG/Tracker).
    combos: die zu bewertenden Hero-Combos (Default: alle 1326 minus Board). Die Villain-Range fuer C(h) ist der
    Tracker auf GENAU diesem Zustand (History-Schnitt vor der Aktion) — wie der Guard sie damals sah."""
    _pruefe_guards(guards)
    adv = _advisor_modul(advisor)
    board = list(zustand["board"])
    street = zustand["street"]
    legal = zustand.get("legal") or {}
    me = zustand["players"][seat]
    to_call = max(0, int(zustand["current_bet"]) - int(me["committed_street"]))
    kann_raisen = bool(legal.get("can_raise", me["stack"] > to_call))
    if combos is None:
        combos = lebende_combos(board)
    combos = [tuple(c) for c in combos]
    if to_call == 0:
        return _modell_frei(zustand, seat, guards, konvention, combos, adv, board, street, kann_raisen)
    return _modell_facing(zustand, seat, guards, konvention, combos, adv, board, street, to_call, kann_raisen)


def _villain_range_am_knoten(zustand: Mapping[str, Any], seat: int, advisor) -> dict:
    """Die DAMALIGE Villain-Range: RangeTracker auf dem Knoten-Zustand (liest keine Hole-Karten, A3)."""
    return RangeTracker(advisor=advisor).build(zustand).range.get(1 - seat, {})


def _modell_frei(zustand, seat, guards, konvention, combos, adv, board, street, kann_raisen) -> KnotenModell:
    p = _p_bet_alle(adv, combos, board, rolle_bet(zustand, seat, konvention), street)
    guard = GUARD_TURN_WERT if (GUARD_TURN_WERT in guards and turn_wert_anwendbar(zustand)) else None
    c_maske: set = set()
    if guard is not None:
        vill = _villain_range_am_knoten(zustand, seat, adv)
        c_maske = {combo_kanonisch(*c) for c in combos if bedingung_turn_wert(zustand, c, vill)}
    ziel = turn_wert_ziel(zustand) if guard is not None else None
    spalten: list[ActionKey] = [ActionKey.check()]
    if kann_raisen:
        # Label der Bet-Spalte: b* — oder ohne Guard dieselbe Referenzgroesse (die Basis ist groessenagnostisch)
        spalten.append(ziel if ziel is not None else kanonisiere("bet", int(TURN_WERT_FRAC * zustand["pot"]), zustand))
    zeilen, undefiniert, basis = [], set(), {}
    for c in combos:
        pb = None if p is None else p.get(c)
        if pb is None:
            undefiniert.add(c)
            continue
        pb = max(0.0, min(1.0, pb))
        basis[c] = (1.0 - pb, pb)
        in_c = combo_kanonisch(*c) in c_maske
        if kann_raisen:
            zeilen.append((c, ((1.0 - pb) * (0.0 if in_c else 1.0), pb + ((1.0 - pb) if in_c else 0.0))))
        else:
            zeilen.append((c, (1.0,)))
    tab = PolicyTable(tuple(spalten), tuple(zeilen), frozenset(undefiniert), herkunft="advisor")
    return KnotenModell(tab, False, guard, ziel, frozenset(c_maske), basis, kann_raisen)


def _modell_facing(zustand, seat, guards, konvention, combos, adv, board, street, to_call, kann_raisen) -> KnotenModell:
    pd = _p_defense_alle(adv, combos, board, _rolle_position(zustand, seat),
                         _size_faced(zustand, seat, konvention), street)
    guard = GUARD_SEL_FLOP if (GUARD_SEL_FLOP in guards and sel_anwendbar(zustand)) else None
    c_maske: set = set()
    if guard is not None:
        vill = _villain_range_am_knoten(zustand, seat, adv)
        c_maske = {combo_kanonisch(*c) for c in combos if bedingung_sel(zustand, c, vill, SEL_M15_MARGE)}
    legal = zustand.get("legal") or {}
    spalten: list[ActionKey] = [ActionKey.fold(), ActionKey.call()]
    if kann_raisen and legal.get("raise_min") is not None:
        spalten.append(ActionKey.raise_to(int(legal["raise_min"])))    # Referenz-Label (Basis groessenagnostisch)
    raise_spalte = len(spalten) == 3
    zeilen, undefiniert, basis = [], set(), {}
    for c in combos:
        trip = None if pd is None else pd.get(c)
        if trip is None:
            undefiniert.add(c)
            continue
        pf, pc, pr = (max(0.0, min(1.0, x)) for x in trip)
        basis[c] = (pf, pc, pr)
        in_c = combo_kanonisch(*c) in c_maske
        f_exec = 0.0 if in_c else pf
        c_exec = pc + (pf if in_c else 0.0)
        if raise_spalte:
            zeilen.append((c, _normiert((f_exec, c_exec, pr))))
        else:
            zeilen.append((c, _normiert((f_exec, c_exec + pr))))      # decide(): Raise-Masse ohne can_raise -> call
    tab = PolicyTable(tuple(spalten), tuple(zeilen), frozenset(undefiniert), herkunft="advisor")
    return KnotenModell(tab, True, guard, None, frozenset(c_maske), basis, raise_spalte)


def _normiert(p: tuple[float, ...]) -> tuple[float, ...]:
    """Softmax-Tripel summieren in float32 auf 1±1e-7; PolicyTable verlangt 1e-6 — Renormierung ist hier nur
    Rundungs-Hygiene (Massenerhaltung wird im Test gegen die rohen Werte geprueft)."""
    s = sum(p)
    return tuple(x / s for x in p) if s > 0 else p


def lebende_combos(board: Sequence[str]) -> list[tuple[str, str]]:
    """Alle Combos ohne Board-Karte, kanonisch sortiert (contracts.combo_kanonisch)."""
    tot = set(board)
    return [combo_kanonisch(a, b) for a, b in itertools.combinations(_ALLE_KARTEN, 2) if a not in tot and b not in tot]


def action_likelihoods(st_vor_aktion: Mapping[str, Any], seat: int, guards: Sequence[str] = STANDARD_GUARDS,
                       konvention: Konvention = K1_KONVENTION, combos: Sequence[tuple] | None = None,
                       advisor=None) -> PolicyTable:
    """(c) PolicyTable-kompatible Verteilung [combo][ActionKey] am Knoten — die Bausteine von (a), einzeln testbar."""
    return knoten_modell(st_vor_aktion, seat, guards, konvention, combos, advisor).tabelle


# ================================================================ (a)/(b)/(d): die Rekonstruktion
@dataclass(frozen=True)
class KnotenProtokoll:
    index: int
    street: str
    beobachtet: str
    facing: bool
    guard: str | None
    guard_ziel: str | None
    n_combos: int
    n_c: int                    # Combos mit C(h)=True in Heros damaliger Range
    masse_c: float              # Range-Masse dieser Combos VOR dem Knoten (wie viel der Guard bewegen KONNTE)
    modelliert: bool            # Advisor-Likelihood vorhanden (sonst legality-only)
    ziel_getroffen: bool | None  # beobachtete Bet == b* (nur turn_wert-Knoten)


@dataclass(frozen=True)
class K1Rekonstruktion:
    hero: int
    hero_range: dict            # kanonische Combos -> Gewicht, Σ=1
    villain_range: dict         # Tracker-Villain-Range am River-Beginn (wie heute; Tracker-Combo-Reihenfolge)
    status: str
    grund: str
    pot_river: int
    guards: tuple
    konvention: Konvention
    knoten: tuple = field(default_factory=tuple)
    heur: int = 0               # legality-only-Schritte (Tracker-Zaehler-Semantik)
    total: int = 0
    k1_version: str = K1_VERSION

    def range_state(self, board: Sequence[str]) -> RangeState:
        return RangeState.aus(self.hero_range, self.villain_range, board, "k1_likelihood", "normiert_summe_1",
                              self.status, versions_hash(self.guards, self.konvention), hero_injiziert=False,
                              hero_rolle=self.konvention.rolle_bet)


def versions_hash(guards: Sequence[str] = STANDARD_GUARDS, konvention: Konvention = K1_KONVENTION) -> str:
    """Fingerprint-Baustein (K4): K1-Version + Guards + Konvention + die Tracker-Flags, die die Likelihood formen."""
    return konfig_hash_aus({"k1": K1_VERSION, "guards": list(guards), "konvention": konvention.__dict__,
                            "alpha": rt.TRACKER_ALPHA, "aggro_full": rt.TRACKER_AGGRO_FULL,
                            "raise_narrow": rt.RAISE_NARROW, "audit_fix": rt.AUDIT_FIX,
                            "iters": GUARD_EQUITY_ITERS, "turn_frac": TURN_WERT_FRAC, "turn_min_eq": TURN_WERT_MIN_EQ,
                            "sel_marge": SEL_M15_MARGE})


def _pruefe_guards(guards: Sequence[str]) -> None:
    fremd = set(guards) - BEKANNTE_GUARDS
    if fremd:
        raise ValueError(f"unbekannte Guards {sorted(fremd)}; bekannt: {sorted(BEKANNTE_GUARDS)}")


def prior_range(st0: Mapping[str, Any], hero: int, advisor=None) -> dict:
    """r_0: der Tracker-Preflop-Prior fuer Hero (ohne Board-Maske) — fuer das Orakel."""
    t = RangeTracker(advisor=advisor)
    t._init_preflop(st0)
    return dict(t.range[hero])


def rekonstruiere(st0: Mapping[str, Any], guards: Sequence[str] = STANDARD_GUARDS, hero: int | None = None,
                  konvention: Konvention = K1_KONVENTION, advisor=None) -> K1Rekonstruktion:
    """(a)+(b)+(d): Heros oeffentliche Range am River-Beginn, vorwaerts ab Prior; Villain-Range des Trackers;
    Status. hero default = st0['to_act'] (improver-Konvention: der am River handelnde Sitz)."""
    _pruefe_guards(guards)
    hero = int(st0["to_act"]) if hero is None else int(hero)
    st = schneide_am_river(st0)
    if st is None:
        return K1Rekonstruktion(hero, {}, {}, STATUS_FEHLGESCHLAGEN, "kein River-Deal in der History",
                                0, tuple(guards), konvention)
    evs, pot_river = ereignisse(st, hero)
    t = RangeTracker(advisor=advisor)
    t._init_preflop(st)
    aggro = heur = total = 0
    protokoll: list[KnotenProtokoll] = []
    for art, wert in evs:
        if art == "deal":
            t._remove_dead(_board_at(st["board"], wert))
            continue
        k: Knoten = wert
        d = t.range[hero]
        if not d:
            break
        modell = knoten_modell(k.zustand, hero, guards, konvention, list(d.keys()), t.adv)
        total += 1
        masse_c = sum(w for c, w in d.items() if combo_kanonisch(*c) in modell.c_maske)
        modelliert = _wende_an(t, hero, d, modell, k, konvention, aggro)
        if k.beobachtet.kind == "raise_to" and (not k.facing or rt.AUDIT_FIX or modelliert):
            aggro += 1                                   # Tracker: Bet zaehlt immer; Raise nur unter AUDIT_FIX/modelliert
        if not modelliert:
            heur += 1
        t._normalize(hero)
        protokoll.append(KnotenProtokoll(
            k.index, k.street, _key_str(k.beobachtet), k.facing, modell.guard,
            None if modell.guard_ziel is None else _key_str(modell.guard_ziel), len(d), len(modell.c_maske),
            masse_c, modelliert,
            None if modell.guard_ziel is None else (k.beobachtet.kind == "raise_to"
                                                    and k.beobachtet.chips == modell.guard_ziel.chips)))
    d = t.range.get(hero, {})
    s = sum(d.values())
    if not d or s <= 0:
        return K1Rekonstruktion(hero, {}, {}, STATUS_FEHLGESCHLAGEN, "Hero-Range kollabiert (Masse 0)",
                                pot_river, tuple(guards), konvention, tuple(protokoll), heur, total)
    hero_range = {combo_kanonisch(*c): w / s for c, w in d.items()}
    villain_range = _villain_range_river(st, hero, advisor)
    status = STATUS_OK if heur == 0 else STATUS_TEILWEISE
    grund = "" if heur == 0 else f"{heur}/{total} Hero-Knoten legality-only (Advisor fehlt / Raise facing Bet)"
    return K1Rekonstruktion(hero, hero_range, villain_range, status, grund, pot_river, tuple(guards), konvention,
                            tuple(protokoll), heur, total)


def _wende_an(t: RangeTracker, hero: int, d: dict, modell: KnotenModell, k: Knoten, konvention: Konvention,
              aggro: int) -> bool:
    """Multipliziert d mit π_exec(beobachtet|h)^alpha — Daempfung exakt nach range_tracker._update_action
    (Bet: alpha 1.0 ab der 2. Aggression unter AGGRO_FULL, sonst TRACKER_ALPHA; Check/Call: TRACKER_ALPHA).
    Raise facing Bet ohne raise_modelliert: RAISE_NARROW-Mix (Tracker-Code) oder legality-only. True iff modelliert."""
    key = k.beobachtet
    if k.facing and key.kind == "raise_to" and not konvention.raise_modelliert:
        if rt.RAISE_NARROW > 0 and k.street in rt.RAISE_MIX and t._narrow_raise(hero, k.zustand["board"], k.street, k.size_cls):
            return True
        return False
    if key.kind == "raise_to" and not k.facing:
        alpha = 1.0 if (rt.TRACKER_AGGRO_FULL and aggro >= 1) else rt.TRACKER_ALPHA
    else:
        alpha = rt.TRACKER_ALPHA
    modelliert = False
    for c in list(d.keys()):
        lik = modell.likelihood(c, key)
        if lik is None:
            continue
        d[c] *= max(0.0, min(1.0, lik)) ** alpha
        modelliert = True
    return modelliert


def _villain_range_river(st_geschnitten: Mapping[str, Any], hero: int, advisor) -> dict:
    return dict(RangeTracker(advisor=advisor).build(st_geschnitten).range.get(1 - hero, {}))


def _key_str(k: ActionKey) -> str:
    return k.kind if k.kind != "raise_to" else f"raise_to({k.chips})"


def hero_range_river_start(st0: Mapping[str, Any], guards: Sequence[str] = STANDARD_GUARDS,
                           hero: int | None = None, konvention: Konvention = K1_KONVENTION) -> dict:
    """(a) Heros oeffentliche Range am River-Beginn, normiert (Σ=1), kanonische Combo-Schluessel. Leer bei
    Status 'fehlgeschlagen' — Status/Protokoll liefert rekonstruiere()."""
    return rekonstruiere(st0, guards, hero, konvention).hero_range


def villain_range_river_start(st0: Mapping[str, Any], hero: int | None = None) -> dict:
    """(b) Tracker-Villain-Range am River-Beginn — wie heute (improver._river_spot_und_frage:436-438)."""
    hero = int(st0["to_act"]) if hero is None else int(hero)
    st = schneide_am_river(st0)
    if st is None:
        return {}
    return _villain_range_river(st, hero, None)


def range_state_river_start(st0: Mapping[str, Any], guards: Sequence[str] = STANDARD_GUARDS,
                            hero: int | None = None, konvention: Konvention = K1_KONVENTION) -> RangeState:
    """contracts.RangeState fuer K2 (herkunft 'k1_likelihood', Σ=1, Board-Combos exakt 0, keine Injektion)."""
    rek = rekonstruiere(st0, guards, hero, konvention)
    if rek.status == STATUS_FEHLGESCHLAGEN:
        raise ValueError(f"K1 fehlgeschlagen: {rek.grund}")
    return rek.range_state(list(st0["board"])[:5])
