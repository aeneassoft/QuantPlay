"""v10 — eingefrorene VERTRAEGE (G0, Build-Karte docs/V10_BUILD_CARD.md; Fakten docs/V10_FAKTEN.md).

Reine Datentypen (frozen dataclasses) + Validierung + Kanonisierungs-Helfer. KEINE Strategie, KEIN Sampling,
KEIN Solver. Alles hier ist so gebaut, dass es mit BEIDEN echten Zustandsformaten arbeitet:

  * Engine-State  (HeadsUpGame.state(), pokerbot/engine/game.py:290-307): history-Eintraege
    fold/check {player,action,street} · call {player,action,amount,street} · bet/raise {player,action,to,street}
    · deal {action:'deal',street,board}. KEIN hand_id. Beide Hole-Karten sichtbar.
  * Adapter-State (gtow_to_state, pokerbot/benchmark/gtowizard.py:126-148): call OHNE amount, deal OHNE board,
    `to` als FLOAT, hand_id vorhanden, Villain-Hole '??'.

Die Vertraege nutzen deshalb NUR die Schnittmenge: player/action/street/to (bet/raise) + deal.street; das Board
kommt aus state['board']; Call-Increments werden NICHT aus 'amount' gelesen (V10_FAKTEN A2/B16).

Kanonisierung folgt der ENGINE-Regel (game.py:161-181): Betrag = Raise-TO-Level der Strasse, int()-Truncation,
stiller Clamp auf [raise_min, raise_max]; 'bet'/'raise'/'allin' sind semantisch dieselbe finale Aktion
raise_to(chips). Die Engine emittiert NIE das Label 'allin'.

Combo-Konvention = pokerbot/strategy/gpu_cfr.py:37-44 / gpu_eval.py:200-201: Karte = rank*4+suit (rank 0='2'..
12='A', suits 'shdc'), Combo-Index lexikographisch ueber itertools.combinations(range(52), 2). Hier ohne torch
nachgebaut; der Selbsttest vergleicht gegen gpu_cfr.combo_index, wenn torch verfuegbar ist.
"""
from __future__ import annotations

import hashlib
import itertools
import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

KONTRAKT_VERSION = "v10-contracts-1"

STREETS = ("preflop", "flop", "turn", "river")
BOARD_LEN = {"preflop": 0, "flop": 3, "turn": 4, "river": 5}
SUMMEN_TOLERANZ = 1e-6                 # Karte: Σ=1 (1e-6) fuer Ranges und Politik-Zeilen

ACTION_KINDS = ("fold", "check", "call", "raise_to")
FALLBACK_STATUS = ("keiner", "offtree", "deadline", "fehler", "hand_not_in_range", "nicht_aktiviert")
DEADLINE_STATUS = ("eingehalten", "verletzt", "nicht_gemessen", "iterations_deadline")
REKONSTRUKTIONS_STATUS = ("ok", "teilweise", "fehlgeschlagen")
RANGE_KONVENTION = ("unnormiert_skaleninvariant", "normiert_summe_1")
RANGE_HERKUNFT = ("tracker", "k1_likelihood", "gtow_census", "fixture", "unbekannt")
PRIVATE_SEED_QUELLE = ("deck_hand_id_sitz", "os_urandom", "test_seed", "keine")
OFFTREE_REGELN = ("fallback_basis_log",)     # Karte K2: definierter Fallback (Basis) + Log, kein stilles Neulösen

# ---------------------------------------------------------------- Karten / Combos (Konvention gpu_cfr)
_RANKS = "23456789TJQKA"
_SUITS = "shdc"
_COMBOS = tuple(itertools.combinations(range(52), 2))
_COMBO_IDX = {c: k for k, c in enumerate(_COMBOS)}
N_COMBOS = len(_COMBOS)                # 1326


def karte_int(card: str) -> int:
    """'As' -> 51 (rank*4+suit; identisch zu gpu_eval.encode)."""
    if not isinstance(card, str) or len(card) != 2 or card[0] not in _RANKS or card[1] not in _SUITS:
        raise ValueError(f"Keine gueltige Karte: {card!r}")
    return _RANKS.index(card[0]) * 4 + _SUITS.index(card[1])


def combo_index(c1: str, c2: str) -> int:
    """Kanonischer Combo-Index 0..1325 (Eingabereihenfolge egal) — identisch zu gpu_cfr.combo_index."""
    a, b = sorted((karte_int(c1), karte_int(c2)))
    if a == b:
        raise ValueError(f"Combo mit doppelter Karte: {c1} {c2}")
    return _COMBO_IDX[(a, b)]


def combo_kanonisch(c1: str, c2: str) -> tuple[str, str]:
    """Combo als sortiertes Karten-Paar (nach karte_int), damit dict-Schluessel eindeutig sind."""
    a, b = sorted((c1, c2), key=karte_int)
    return (a, b)


def konfig_hash_aus(konfig: Mapping[str, Any]) -> str:
    """sha256 ueber die sortierte JSON-Form einer Konfiguration (Fingerprint-Baustein K4)."""
    return hashlib.sha256(json.dumps(dict(konfig), sort_keys=True, default=str).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- ActionKey
@dataclass(frozen=True)
class ActionKey:
    """Semantisch finale Aktion: fold | check | call | raise_to(chips).

    'bet', 'raise' und 'allin' der Engine/des Adapters fallen auf raise_to zusammen — unterschieden wird NUR
    ueber den finalen ganzzahligen Raise-TO-Betrag der Strasse (Engine-Clamp, game.py:170), nie ueber Labels
    (Karte K1: 'Groessenvergleich ueber finale ganzzahlige Chipbetraege')."""
    kind: str
    chips: int | None = None

    def __post_init__(self) -> None:
        if self.kind not in ACTION_KINDS:
            raise ValueError(f"ActionKey.kind muss in {ACTION_KINDS} liegen: {self.kind!r}")
        if self.kind == "raise_to":
            if not isinstance(self.chips, int) or isinstance(self.chips, bool) or self.chips <= 0:
                raise ValueError(f"raise_to braucht chips als positives int: {self.chips!r}")
        elif self.chips is not None:
            raise ValueError(f"{self.kind} traegt keinen Betrag: {self.chips!r}")

    @staticmethod
    def fold() -> "ActionKey":
        return ActionKey("fold")

    @staticmethod
    def check() -> "ActionKey":
        return ActionKey("check")

    @staticmethod
    def call() -> "ActionKey":
        return ActionKey("call")

    @staticmethod
    def raise_to(chips: int) -> "ActionKey":
        return ActionKey("raise_to", int(chips))

    def als_engine_aktion(self, legal: Mapping[str, Any] | None = None) -> tuple[str, int | None]:
        """Rueckabbildung auf (action, amount) fuer game.act / den Guard-Vertrag. Label 'bet' iff legal.is_bet."""
        if self.kind != "raise_to":
            return self.kind, None
        label = "bet" if (legal and legal.get("is_bet")) else "raise"
        return label, self.chips


def kanonisiere(action: str, amount: Any, state: Mapping[str, Any]) -> ActionKey:
    """(action, amount) einer Strategie -> ActionKey, exakt nach der Engine-Regel (game.py:141-181):
    bet/raise: int(amount) (Truncation), dann Clamp auf [legal.raise_min, legal.raise_max]; 'allin' = raise_max.
    fold/check/call werden gegen state['legal'] geprueft (fold bei to_call==0 ist engine-legal, bleibt erlaubt)."""
    a = str(action).lower()
    legal = state.get("legal") or {}
    if a == "fold":
        return ActionKey.fold()
    if a == "check":
        if legal and not legal.get("can_check", True):
            raise ValueError("check ist nicht legal (legal.can_check False)")
        return ActionKey.check()
    if a == "call":
        if legal and not legal.get("can_call", True):
            raise ValueError("call ist nicht legal (legal.can_call False)")
        return ActionKey.call()
    if a in ("bet", "raise", "allin"):
        if legal and not legal.get("can_raise", True):
            raise ValueError("bet/raise ist nicht legal (legal.can_raise False)")
        rmin, rmax = legal.get("raise_min"), legal.get("raise_max")
        if a == "allin":
            if rmax is None:
                raise ValueError("allin ohne legal.raise_max nicht kanonisierbar")
            return ActionKey.raise_to(int(rmax))
        if amount is None:
            raise ValueError("bet/raise braucht einen Betrag (Engine wirft ebenfalls)")
        target = int(amount)                                    # Engine: int(amount) = Truncation
        if rmin is not None and rmax is not None:
            target = max(int(rmin), min(target, int(rmax)))     # Engine: stiller Clamp
        return ActionKey.raise_to(target)
    raise ValueError(f"Unbekannte Aktion: {action!r}")


def kanonisiere_history_eintrag(h: Mapping[str, Any]) -> ActionKey | None:
    """History-Zeile (Engine ODER Adapter) -> ActionKey; deal-Zeilen -> None.
    Nutzt nur die Kanal-Schnittmenge: 'to' (bet/raise, ggf. float) — 'amount' bei call wird NICHT benoetigt."""
    a = str(h.get("action", "")).lower()
    if a == "deal":
        return None
    if a in ("fold", "check", "call"):
        return ActionKey(a)
    if a in ("bet", "raise", "allin"):
        to = h.get("to")
        if to is None:
            to = h.get("amount")            # defensiv (Legacy-Fixtures); die Engine setzt 'to'
        if to is None:
            raise ValueError(f"bet/raise-Zeile ohne 'to': {dict(h)!r}")
        return ActionKey.raise_to(int(round(float(to))))   # Adapter liefert float-Level, Engine int
    raise ValueError(f"Unbekannte History-Aktion: {dict(h)!r}")


# ---------------------------------------------------------------- HistorienSchritt + PolicySnapshot
@dataclass(frozen=True)
class HistorienSchritt:
    """Eine Spieler-Aktion der oeffentlichen Historie. Deal-Events sind KEINE Schritte (die Strasse steht am
    Schritt; das Board kommt aus PolicySnapshot.board). Adapter- und Engine-Historie ergeben dieselben Schritte."""
    street: str
    spieler: int
    key: ActionKey

    def __post_init__(self) -> None:
        if self.street not in STREETS:
            raise ValueError(f"street {self.street!r} nicht in {STREETS}")
        if self.spieler not in (0, 1):
            raise ValueError(f"spieler muss 0|1 sein (HU): {self.spieler!r}")


@dataclass(frozen=True)
class PolicySnapshot:
    """OEFFENTLICHER Zustand unmittelbar vor einer Aktion — ohne jede Hole-Karte (K1-Invarianz: gleiche
    oeffentliche Historie, andere Hero-Hand -> identischer Snapshot). Chips-Einheiten wie die Engine
    (bb=100 in allen Messkanaelen, Stacks 20000; V10_FAKTEN A1).

    hand_adresse: Adapter liefert state['hand_id']; der Engine-State hat KEINS (game.py:301) und hand_no ist im
    Spiegel nicht eindeutig (duplicate.py:32-40) -> dort None, bis der Integrator eine Adresse injiziert (E4)."""
    board: tuple[str, ...]
    street: str
    pot: int
    current_bet: int
    committed_street: tuple[int, int]
    committed_total: tuple[int, int]
    stacks: tuple[int, int]
    button: int
    to_act: int
    historie: tuple[HistorienSchritt, ...]
    bb: int
    policy_id: str
    konfig_hash: str
    hand_adresse: str | None = None
    to_call: int = 0
    raise_min: int | None = None
    raise_max: int | None = None
    can_raise: bool = False

    def __post_init__(self) -> None:
        if self.street not in STREETS:
            raise ValueError(f"street {self.street!r}")
        if len(self.board) != BOARD_LEN[self.street]:
            raise ValueError(f"Board-Laenge {len(self.board)} passt nicht zu {self.street}")
        for c in self.board:
            karte_int(c)
        if len(set(self.board)) != len(self.board):
            raise ValueError("Board enthaelt doppelte Karten")
        if self.button not in (0, 1) or self.to_act not in (0, 1):
            raise ValueError("button/to_act muessen 0|1 sein (HU)")
        if self.pot < 0 or self.current_bet < 0 or self.bb <= 0:
            raise ValueError("pot/current_bet >= 0, bb > 0 verletzt")
        for cs, ct, st in zip(self.committed_street, self.committed_total, self.stacks):
            if cs < 0 or ct < 0 or st < 0 or cs > ct:
                raise ValueError("committed_street <= committed_total, alles >= 0 verletzt")
        if self.current_bet != max(self.committed_street) and self.current_bet != 0:
            raise ValueError("current_bet muss max(committed_street) oder 0 sein")
        if self.to_call != self.current_bet - self.committed_street[self.to_act] and self.current_bet != 0:
            raise ValueError("to_call inkonsistent zu current_bet/committed_street")
        if self.can_raise and (self.raise_min is None or self.raise_max is None or self.raise_min > self.raise_max):
            raise ValueError("can_raise verlangt raise_min <= raise_max")
        for s in self.historie:
            if STREETS.index(s.street) > STREETS.index(self.street):
                raise ValueError(f"Historie enthaelt spaetere Strasse {s.street} als {self.street}")
        if not self.policy_id or not self.konfig_hash:
            raise ValueError("policy_id und konfig_hash sind Pflicht")

    def pot_konsistent(self) -> bool:
        """Engine: pot == Σ committed_total (game.py:51-52). Adapter: total_pot vs start-stack — kann abweichen,
        deshalb nur eine Pruef-Methode, kein harter Fehler."""
        return self.pot == sum(self.committed_total)

    def pot_bei_strassenbeginn(self) -> int:
        """Exakte Formel pot_river = pot − Σ committed_street (verifiziert 1400 == 1400, V10_FAKTEN A5)."""
        return self.pot - sum(self.committed_street)

    def legale_keys(self) -> tuple[ActionKey, ...]:
        """Legale ActionKeys (raise_to nur als Intervall-Grenzen, da der Betrag frei ist)."""
        keys: list[ActionKey] = []
        if self.to_call > 0:
            keys += [ActionKey.fold(), ActionKey.call()]
        else:
            keys.append(ActionKey.check())
        if self.can_raise and self.raise_min is not None and self.raise_max is not None:
            keys.append(ActionKey.raise_to(self.raise_min))
            if self.raise_max != self.raise_min:
                keys.append(ActionKey.raise_to(self.raise_max))
        return tuple(keys)

    @staticmethod
    def aus_state(state: Mapping[str, Any], policy_id: str, konfig_hash: str) -> "PolicySnapshot":
        """Baut den Snapshot aus einem Engine- ODER Adapter-State. Liest KEINE Hole-Karten.
        Fuer Adapter-States wird 'amount' bei call nicht benoetigt und deal.board ignoriert."""
        pl = state["players"]
        legal = state.get("legal") or {}
        schritte = tuple(
            HistorienSchritt(str(h["street"]), int(h["player"]), k)
            for h in state["history"]
            for k in (kanonisiere_history_eintrag(h),) if k is not None
        )
        hid = state.get("hand_id")
        return PolicySnapshot(
            board=tuple(state["board"]), street=str(state["street"]), pot=int(state["pot"]),
            current_bet=int(state.get("current_bet", 0)),
            committed_street=(int(pl[0]["committed_street"]), int(pl[1]["committed_street"])),
            committed_total=(int(pl[0]["committed_total"]), int(pl[1]["committed_total"])),
            stacks=(int(pl[0]["stack"]), int(pl[1]["stack"])),
            button=int(state["button"]), to_act=int(state["to_act"]), historie=schritte,
            bb=int(state["bb"]), policy_id=policy_id, konfig_hash=konfig_hash,
            hand_adresse=None if hid is None else str(hid),
            to_call=int(legal.get("to_call", 0) or 0),
            raise_min=None if legal.get("raise_min") is None else int(legal["raise_min"]),
            raise_max=None if legal.get("raise_max") is None else int(legal["raise_max"]),
            can_raise=bool(legal.get("can_raise", False)),
        )


# ---------------------------------------------------------------- RangeState
Combo = tuple[str, str]


def _range_items(r: Any) -> tuple[tuple[Combo, float], ...]:
    """dict{combo->w} ODER Sequenz der Laenge 1326 (numpy/list) -> sortierte, kanonische Item-Tupel."""
    if isinstance(r, Mapping):
        items = [(combo_kanonisch(*c), float(w)) for c, w in r.items()]
    else:
        seq = list(r)
        if len(seq) != N_COMBOS:
            raise ValueError(f"Range-Vektor muss Laenge {N_COMBOS} haben: {len(seq)}")
        items = [(_combo_str(k), float(w)) for k, w in enumerate(seq) if float(w) != 0.0]
    items.sort(key=lambda kv: combo_index(*kv[0]))
    return tuple(items)


def _combo_str(k: int) -> Combo:
    a, b = _COMBOS[k]
    return (_RANKS[a // 4] + _SUITS[a % 4], _RANKS[b // 4] + _SUITS[b % 4])


@dataclass(frozen=True)
class RangeState:
    """Zwei Range-Vektoren (Hero, Villain) + Board-Maske + Herkunft/Konvention.

    hero/villain: sortierte ((c1,c2), w)-Tupel (Konstruktion aus dict ODER 1326-Vektor via RangeState.aus).
    konvention: 'unnormiert_skaleninvariant' (gpu_cfr.range_vector normiert NICHT; RM+/avg/expl sind
    skaleninvariant) oder 'normiert_summe_1' (Σ=1 ± 1e-6 wird geprueft).
    hero_injiziert: True nur im Legacy-Pfad (gpu_resolver._injiziere, HERO_MIN_GEWICHT 0.02); im K1/K2-Pfad
    (herkunft 'k1_likelihood') MUSS es False sein (Karte K1 'Keine Hero-Hand-Injektion').
    Board-Combos sind EXAKT 0 (Karte-Abnahme) — hart validiert."""
    hero: tuple[tuple[Combo, float], ...]
    villain: tuple[tuple[Combo, float], ...]
    board: tuple[str, ...]
    herkunft: str
    konvention: str
    rekonstruktions_status: str
    versions_hash: str
    hero_injiziert: bool = False
    hero_rolle: str = "position"          # 'position' (Tracker) | 'initiative' (decide) — V10_FAKTEN B9

    def __post_init__(self) -> None:
        if self.herkunft not in RANGE_HERKUNFT:
            raise ValueError(f"herkunft {self.herkunft!r}")
        if self.konvention not in RANGE_KONVENTION:
            raise ValueError(f"konvention {self.konvention!r}")
        if self.rekonstruktions_status not in REKONSTRUKTIONS_STATUS:
            raise ValueError(f"rekonstruktions_status {self.rekonstruktions_status!r}")
        if self.hero_rolle not in ("position", "initiative"):
            raise ValueError("hero_rolle muss position|initiative sein")
        if self.herkunft == "k1_likelihood" and self.hero_injiziert:
            raise ValueError("K1-Range darf keine Hero-Injektion tragen")
        board_ints = {karte_int(c) for c in self.board}
        for name, rng in (("hero", self.hero), ("villain", self.villain)):
            gesehen = set()
            for (c1, c2), w in rng:
                if w < 0:
                    raise ValueError(f"{name}: negatives Gewicht {w} fuer {c1}{c2}")
                k = combo_index(c1, c2)
                if k in gesehen:
                    raise ValueError(f"{name}: Combo {c1}{c2} doppelt")
                gesehen.add(k)
                if w != 0.0 and (karte_int(c1) in board_ints or karte_int(c2) in board_ints):
                    raise ValueError(f"{name}: Board-Combo {c1}{c2} traegt Gewicht {w} (muss exakt 0 sein)")
            if self.konvention == "normiert_summe_1":
                s = sum(w for _, w in rng)
                if abs(s - 1.0) > SUMMEN_TOLERANZ:
                    raise ValueError(f"{name}: Σ={s} ≠ 1 (Toleranz {SUMMEN_TOLERANZ})")
        if not self.versions_hash:
            raise ValueError("versions_hash ist Pflicht")

    @staticmethod
    def aus(hero: Any, villain: Any, board: Sequence[str], herkunft: str, konvention: str,
            rekonstruktions_status: str, versions_hash: str, hero_injiziert: bool = False,
            hero_rolle: str = "position") -> "RangeState":
        return RangeState(_range_items(hero), _range_items(villain), tuple(board), herkunft, konvention,
                          rekonstruktions_status, versions_hash, hero_injiziert, hero_rolle)

    def hero_dict(self) -> dict[Combo, float]:
        return dict(self.hero)

    def villain_dict(self) -> dict[Combo, float]:
        return dict(self.villain)

    def support(self, seite: str = "hero") -> frozenset[Combo]:
        rng = self.hero if seite == "hero" else self.villain
        return frozenset(c for c, w in rng if w > 0)


# ---------------------------------------------------------------- PolicyTable
@dataclass(frozen=True)
class PolicyTable:
    """Verteilung [combo][ActionKey] -> p ueber die LEGALEN Aktionen eines Knotens. KEINE Samples.

    zeilen: ((combo, (p_0, ..., p_{n-1})), ...) in der Reihenfolge von `aktionen`; jede Zeile Σ=1 ± 1e-6.
    undefiniert: Combos, fuer die keine Verteilung definiert ist (z.B. eigene Reach 0 im Solve — gpu_cfr.avg_sigma
    liefert dort uniform 1/n, das darf NIE als Strategie gelesen werden; V10_FAKTEN B10). Eine Combo ist entweder
    Zeile ODER undefiniert, nie beides."""
    aktionen: tuple[ActionKey, ...]
    zeilen: tuple[tuple[Combo, tuple[float, ...]], ...]
    undefiniert: frozenset[Combo] = frozenset()
    herkunft: str = "unbekannt"     # 'gpu_cfr_avg' | 'texassolver_strat' | 'advisor' | 'oracle_seeds' | ...

    def __post_init__(self) -> None:
        if not self.aktionen or len(set(self.aktionen)) != len(self.aktionen):
            raise ValueError("aktionen muessen nicht-leer und eindeutig sein")
        # Combos kanonisieren (frozen -> object.__setattr__), damit Lookups reihenfolge-unabhaengig treffen.
        object.__setattr__(self, "zeilen", tuple((combo_kanonisch(*c), tuple(float(p) for p in probs))
                                                 for c, probs in self.zeilen))
        object.__setattr__(self, "undefiniert", frozenset(combo_kanonisch(*c) for c in self.undefiniert))
        n = len(self.aktionen)
        gesehen: set[int] = set()
        for combo, probs in self.zeilen:
            k = combo_index(*combo)
            if k in gesehen:
                raise ValueError(f"Combo {combo} doppelt")
            gesehen.add(k)
            if len(probs) != n:
                raise ValueError(f"Zeile {combo}: {len(probs)} Werte fuer {n} Aktionen")
            if any(p < -SUMMEN_TOLERANZ or p > 1 + SUMMEN_TOLERANZ for p in probs):
                raise ValueError(f"Zeile {combo}: p ausserhalb [0,1]: {probs}")
            s = sum(probs)
            if abs(s - 1.0) > SUMMEN_TOLERANZ:
                raise ValueError(f"Zeile {combo}: Σ={s} ≠ 1 (Toleranz {SUMMEN_TOLERANZ})")
        for combo in self.undefiniert:
            if combo_index(*combo) in gesehen:
                raise ValueError(f"Combo {combo} ist Zeile UND undefiniert")

    def p(self, combo: Combo, key: ActionKey) -> float | None:
        """None, wenn die Combo undefiniert/unbekannt ist — der Aufrufer darf das nicht als 0 lesen."""
        ck = combo_kanonisch(*combo)
        if key not in self.aktionen:
            raise KeyError(f"{key} nicht in aktionen")
        for c, probs in self.zeilen:
            if c == ck:
                return probs[self.aktionen.index(key)]
        return None

    def verteilung(self, combo: Combo) -> dict[ActionKey, float] | None:
        ck = combo_kanonisch(*combo)
        for c, probs in self.zeilen:
            if c == ck:
                return dict(zip(self.aktionen, probs))
        return None


# ---------------------------------------------------------------- RiverPlan
@dataclass(frozen=True)
class RiverPlan:
    """Der EINE River-Plan je Hand (Karte K2): Root = River-Beginn, gemittelte Strategien je Knoten, Navigation
    entlang der gespielten Sequenz. Aktivierung ist eine Funktion NUR von pot_river (oeffentlich): pot_river >=
    schwelle_chips (Karte: 1500 = 15 bb). Kein Hochsetzen nach Ergebnisansicht.

    knoten: ((knotenpfad, PolicyTable | 'tensor:<ref>'), ...) — knotenpfad = ActionKeys ab Root (OOP handelt
    zuerst, gpu_cfr.py:153). aktueller_pfad muss ein bekannter Knotenpfad sein (oder leer = Root)."""
    root: PolicySnapshot
    ranges: RangeState
    baum_hash: str
    konfig_hash: str
    knoten: tuple[tuple[tuple[ActionKey, ...], PolicyTable | str], ...]
    aktueller_pfad: tuple[ActionKey, ...]
    pot_river: int
    schwelle_chips: int = 1500
    aktiviert: bool = False
    offtree_regel: str = "fallback_basis_log"
    fallback_status: str = "keiner"
    deadline_status: str = "nicht_gemessen"
    private_seed_quelle: str = "keine"
    iterationen: int = 150
    praezision: str = "fp32"

    def __post_init__(self) -> None:
        if self.root.street != "river":
            raise ValueError("RiverPlan.root muss ein River-Snapshot sein")
        if tuple(self.ranges.board) != tuple(self.root.board):
            raise ValueError("RangeState.board ≠ root.board")
        if self.pot_river < 0 or self.schwelle_chips <= 0:
            raise ValueError("pot_river >= 0, schwelle_chips > 0 verletzt")
        if self.aktiviert != (self.pot_river >= self.schwelle_chips):
            raise ValueError("aktiviert muss EXAKT (pot_river >= schwelle_chips) sein — oeffentliches Gating")
        if not self.aktiviert and self.fallback_status not in ("keiner", "nicht_aktiviert"):
            raise ValueError("nicht aktivierter Plan traegt keinen Solver-Fallback-Status")
        if self.offtree_regel not in OFFTREE_REGELN:
            raise ValueError(f"offtree_regel {self.offtree_regel!r}")
        if self.fallback_status not in FALLBACK_STATUS:
            raise ValueError(f"fallback_status {self.fallback_status!r}")
        if self.deadline_status not in DEADLINE_STATUS:
            raise ValueError(f"deadline_status {self.deadline_status!r}")
        if self.private_seed_quelle not in PRIVATE_SEED_QUELLE:
            raise ValueError(f"private_seed_quelle {self.private_seed_quelle!r}")
        if self.ranges.herkunft == "k1_likelihood" and self.ranges.hero_injiziert:
            raise ValueError("K2-Plan mit injizierter Hero-Range verboten")
        pfade = [p for p, _ in self.knoten]
        if len(set(pfade)) != len(pfade):
            raise ValueError("Knotenpfade doppelt")
        for p, tab in self.knoten:
            if isinstance(tab, str) and not tab.startswith("tensor:"):
                raise ValueError(f"Tensor-Referenz muss 'tensor:<ref>' sein: {tab!r}")
        if self.aktiviert and self.knoten and self.aktueller_pfad not in pfade:
            raise ValueError("aktueller_pfad ist kein bekannter Knotenpfad (offtree -> fallback_status setzen)")
        if not self.baum_hash or not self.konfig_hash:
            raise ValueError("baum_hash und konfig_hash sind Pflicht")
        if self.iterationen <= 0 or self.praezision not in ("fp32", "fp16"):
            raise ValueError("iterationen > 0, praezision fp32|fp16")

    def tabelle(self, pfad: tuple[ActionKey, ...] | None = None) -> PolicyTable | str | None:
        p = self.aktueller_pfad if pfad is None else pfad
        for kp, tab in self.knoten:
            if kp == p:
                return tab
        return None


# ---------------------------------------------------------------- EntscheidungsTrace
@dataclass(frozen=True)
class EntscheidungsTrace:
    """Trace je Hero-Entscheidung (Karte K2): basis -> texassolver -> guards -> plan_verteilung -> legalitaet ->
    sample_u -> final. Jede Aenderung NACH der Plan-Entscheidung ist reine Legalitaetsabbildung.

    basis: Aktion des Floors (bot.decide ohne Resolver). texassolver: die Resolver-Aktion, wenn er gefeuert hat —
    sie ERSETZT die Basis (bot.py:545-547), ist kein Eingriff; None = nicht gefeuert/Fallback.
    guards: ((name, ActionKey_nach_guard), ...) in Wrapper-Reihenfolge (innen -> aussen).
    plan_verteilung: ((ActionKey, p), ...) Σ=1, None wenn der Plan nicht aktiv war.
    legalitaet: die legalisierte Plan-Aktion (vor dem Sample bei degenerierter Verteilung, sonst nach dem Sample).
    sample_u: Zufallszahl in [0,1) aus der privaten Randomisierung; Pflicht, wenn eine echte Mischung gesampelt
    wurde; None erlaubt bei p in {0,1} exakt (Karte: 'p∈{0,1} exakt')."""
    basis: ActionKey
    final: ActionKey
    texassolver: ActionKey | None = None
    guards: tuple[tuple[str, ActionKey], ...] = ()
    plan_verteilung: tuple[tuple[ActionKey, float], ...] | None = None
    legalitaet: ActionKey | None = None
    sample_u: float | None = None
    fallback_status: str = "keiner"
    offtree: bool = False
    deadline_status: str = "nicht_gemessen"
    hand_adresse: str | None = None
    decision_addr: str | None = None

    def __post_init__(self) -> None:
        if self.fallback_status not in FALLBACK_STATUS:
            raise ValueError(f"fallback_status {self.fallback_status!r}")
        if self.deadline_status not in DEADLINE_STATUS:
            raise ValueError(f"deadline_status {self.deadline_status!r}")
        if self.sample_u is not None and not (0.0 <= self.sample_u < 1.0):
            raise ValueError(f"sample_u muss in [0,1) liegen: {self.sample_u}")
        if self.offtree and self.fallback_status != "offtree":
            raise ValueError("offtree=True verlangt fallback_status 'offtree'")
        if self.plan_verteilung is not None:
            keys = [k for k, _ in self.plan_verteilung]
            if len(set(keys)) != len(keys):
                raise ValueError("plan_verteilung: ActionKey doppelt")
            ps = [p for _, p in self.plan_verteilung]
            if any(p < -SUMMEN_TOLERANZ or p > 1 + SUMMEN_TOLERANZ for p in ps):
                raise ValueError("plan_verteilung: p ausserhalb [0,1]")
            if abs(sum(ps) - 1.0) > SUMMEN_TOLERANZ:
                raise ValueError(f"plan_verteilung: Σ={sum(ps)} ≠ 1")
            degeneriert = any(abs(p - 1.0) <= SUMMEN_TOLERANZ for p in ps)
            if not degeneriert and self.sample_u is None:
                raise ValueError("echte Mischung ohne sample_u — Sampling muss protokolliert sein")
            if self.legalitaet is None:
                raise ValueError("Plan-Entscheidung ohne Legalitaets-Abbildung")
        if self.legalitaet is not None and self.final != self.legalitaet:
            raise ValueError("final ≠ legalitaet: nach der Legalitaetsabbildung darf nichts mehr aendern")
        if self.plan_verteilung is None and self.legalitaet is None:
            erwartet = self.guards[-1][1] if self.guards else (self.texassolver or self.basis)
            if self.final != erwartet:
                raise ValueError("final ohne Plan muss die letzte Guard-/Resolver-/Basis-Aktion sein")


# ================================================================ Selbsttest
def _selbsttest() -> int:
    import random
    n = 0

    def ok(bed: bool, was: str) -> None:
        nonlocal n
        if not bed:
            raise AssertionError(was)
        n += 1

    def wirft(fn, was: str) -> None:
        nonlocal n
        try:
            fn()
        except (ValueError, AssertionError, KeyError):
            n += 1
            return
        raise AssertionError(f"haette werfen muessen: {was}")

    # --- 1. Engine-State (echte HeadsUpGame) -> PolicySnapshot, ohne Hole-Karten
    from pokerbot.engine.game import HeadsUpGame
    g = HeadsUpGame(starting_stack=20000, sb=50, bb=100, seed=3)
    g.start_hand()
    g.act("raise", 300); g.act("call")                                      # preflop (game.py:131 act(action, amount))
    g.act("bet", 400); g.act("call")                                        # flop
    g.act("check"); g.act("check")                                          # turn
    g.act("bet", 600); g.act("raise", 1800)                                 # river
    st = g.state()
    ok(st["street"] == "river" and "hand_id" not in st, "Engine-State ohne hand_id am River")
    snap = PolicySnapshot.aus_state(st, "v5_r8_stack", konfig_hash_aus({"prince": 1}))
    ok(snap.pot == 3800 and snap.pot_bei_strassenbeginn() == 1400, f"pot_river 1400 erwartet: {snap.pot_bei_strassenbeginn()}")
    ok(snap.pot_konsistent(), "Engine: pot == Σ committed_total")
    ok(len(snap.historie) == 8 and all(isinstance(s.key, ActionKey) for s in snap.historie), "8 Schritte, deal-Events ignoriert")
    ok(snap.historie[0].key == ActionKey.raise_to(300) and snap.historie[-1].key == ActionKey.raise_to(1800), "raise-TO-Level")
    ok(snap.hand_adresse is None, "Gym: keine Hand-Adresse")
    ok(snap.to_call == 1200 and ActionKey.call() in snap.legale_keys(), "to_call 1200 am River facing raise")
    ok("hole" not in json.dumps(snap.__dict__, default=str), "Snapshot traegt keine Hole-Karten")
    ok(hash(snap) == hash(PolicySnapshot.aus_state(st, "v5_r8_stack", konfig_hash_aus({"prince": 1}))), "frozen + hashbar + deterministisch")

    # --- 2. Kanonisierung folgt der Engine (Truncation + Clamp + allin)
    la = st["legal"]
    ok(kanonisiere("raise", 1, st) == ActionKey.raise_to(la["raise_min"]), "raise 1 -> raise_min (Clamp)")
    ok(kanonisiere("raise", 1e9, st) == ActionKey.raise_to(la["raise_max"]), "raise 1e9 -> raise_max")
    ok(kanonisiere("allin", None, st) == ActionKey.raise_to(la["raise_max"]), "allin -> raise_max")
    mid = (la["raise_min"] + la["raise_max"]) // 2 + 0.7
    ok(kanonisiere("bet", mid, st) == ActionKey.raise_to(int(mid)), "float wird trunkiert wie int(amount)")
    ok(kanonisiere("bet", mid, st) == kanonisiere("raise", mid, st), "bet/raise = dieselbe finale Aktion")
    wirft(lambda: kanonisiere("raise", None, st), "raise ohne Betrag")
    wirft(lambda: kanonisiere("check", None, st), "check facing bet illegal")
    ok(kanonisiere("fold", None, st) == ActionKey.fold(), "fold")
    wirft(lambda: ActionKey("raise_to", 0), "raise_to 0")
    wirft(lambda: ActionKey("call", 5), "call mit Betrag")
    ok(ActionKey.raise_to(500).als_engine_aktion({"is_bet": True}) == ("bet", 500), "Rueckabbildung bet")

    # --- 3. Adapter-State (gtow_to_state-Form): call ohne amount, deal ohne board, to als float, hand_id
    ad = {
        "street": "river", "board": ["8c", "Ac", "2h", "As", "Kc"], "pot": 3800, "bb": 100, "current_bet": 1800,
        "button": 0, "hand_id": 3012345, "hand_no": 0, "to_act": 0, "hand_over": False,
        "history": [
            {"player": 0, "action": "raise", "street": "preflop", "to": 300.0}, {"player": 1, "action": "call", "street": "preflop"},
            {"action": "deal", "street": "flop"},
            {"player": 1, "action": "bet", "street": "flop", "to": 400.0}, {"player": 0, "action": "call", "street": "flop"},
            {"action": "deal", "street": "turn"},
            {"player": 1, "action": "check", "street": "turn"}, {"player": 0, "action": "check", "street": "turn"},
            {"action": "deal", "street": "river"},
            {"player": 1, "action": "bet", "street": "river", "to": 600.0}, {"player": 0, "action": "raise", "street": "river", "to": 1800.0},
        ],
        "players": [
            {"idx": 0, "hole": ["Ah", "Kd"], "stack": 17500, "committed_street": 1800, "committed_total": 2500, "folded": False, "all_in": False, "is_button": True},
            {"idx": 1, "hole": ["??", "??"], "stack": 18700, "committed_street": 600, "committed_total": 1300, "folded": False, "all_in": False, "is_button": False},
        ],
        "legal": {"to_act": 0, "to_call": 0, "pot": 3800, "can_fold": False, "can_check": True, "can_call": False,
                  "call_amount": 0, "can_raise": False, "is_bet": False, "raise_min": None, "raise_max": 19300},
    }
    ad_snap = PolicySnapshot.aus_state(ad, "v5_r8_stack", "k")
    ok(ad_snap.hand_adresse == "3012345", "Adapter: hand_id als Adresse")
    ok([s.key for s in ad_snap.historie] == [s.key for s in snap.historie], "Adapter- und Engine-Historie ergeben identische ActionKeys")
    ok(ad_snap.pot_bei_strassenbeginn() == 1400, "pot_river-Formel auch im Adapter-Kanal")

    # --- 4. Combo-Konvention + RangeState
    ok(combo_index("2s", "2h") == 0 and combo_index("Ac", "Ad") == N_COMBOS - 1, "Index-Raender")
    ok(combo_index("As", "Kd") == combo_index("Kd", "As"), "Reihenfolge egal")
    try:
        from pokerbot.strategy.gpu_cfr import combo_index as gpu_ci
        rnd = random.Random(7)
        deck = [r + s for r in _RANKS for s in _SUITS]
        for _ in range(200):
            a, b = rnd.sample(deck, 2)
            ok(combo_index(a, b) == gpu_ci(a, b), f"combo_index ≠ gpu_cfr fuer {a}{b}")
        gpu_check = "gpu_cfr.combo_index 200/200 identisch"
    except Exception as e:  # torch fehlt o.ae. -> ehrlich melden, nicht still bestehen
        gpu_check = f"gpu_cfr-Vergleich uebersprungen ({type(e).__name__})"
    board = ("8c", "Ac", "2h", "As", "Kc")
    hero = {("Ah", "Kd"): 0.5, ("Qs", "Qh"): 0.5}
    vill = {("Jd", "Td"): 1.0, ("7s", "7h"): 3.0}            # Σ=4: nur unnormiert-skaleninvariant zulaessig
    vill_n = {("Jd", "Td"): 0.25, ("7s", "7h"): 0.75}
    wirft(lambda: RangeState.aus(hero, vill, board, "k1_likelihood", "normiert_summe_1", "ok", "h0"), "Villain Σ=4 unter normiert")
    rs = RangeState.aus(hero, vill_n, board, "k1_likelihood", "normiert_summe_1", "ok", "h1")
    ok(rs.support("hero") == frozenset({("Kd", "Ah"), ("Qs", "Qh")}), "Support kanonisch sortiert (rank*4+suit: Qs=40 < Qh=41)")
    RangeState.aus(hero, vill, board, "tracker", "unnormiert_skaleninvariant", "ok", "h2")   # Σ=4 erlaubt
    wirft(lambda: RangeState.aus(hero, {**vill, ("Ac", "2d"): 0.1}, board, "tracker", "unnormiert_skaleninvariant", "ok", "h3"),
          "Board-Combo mit Gewicht")
    wirft(lambda: RangeState.aus({("Ah", "Kd"): 0.5, ("Qs", "Qh"): 0.5 + 1e-5}, vill_n, board, "tracker", "normiert_summe_1", "ok", "h4"),
          "Σ ≠ 1 bei normiert")
    wirft(lambda: RangeState.aus(hero, vill_n, board, "k1_likelihood", "normiert_summe_1", "ok", "h5", hero_injiziert=True),
          "K1 mit Injektion")
    vec = [0.0] * N_COMBOS
    vec[combo_index("Ah", "Kd")] = 1.0
    rs_vec = RangeState.aus(vec, vill_n, board, "fixture", "normiert_summe_1", "ok", "h6")
    ok(rs_vec.hero == ((("Kd", "Ah"), 1.0),), "1326-Vektor -> Items")

    # --- 5. PolicyTable
    akt = (ActionKey.check(), ActionKey.raise_to(2400), ActionKey.raise_to(19300))
    pt = PolicyTable(akt, ((("Kd", "Ah"), (0.2, 0.5, 0.3)), (("Qh", "Qs"), (1.0, 0.0, 0.0))),
                     undefiniert=frozenset({("2d", "3d")}), herkunft="gpu_cfr_avg")
    ok(pt.p(("Ah", "Kd"), ActionKey.raise_to(2400)) == 0.5, "p-Lookup mit unkanonischer Combo-Reihenfolge")
    ok(pt.p(("2d", "3d"), ActionKey.check()) is None, "undefiniert -> None, nie 0")
    wirft(lambda: PolicyTable(akt, ((("Kd", "Ah"), (0.2, 0.5, 0.3 + 1e-5)),)), "Zeile Σ≠1")
    PolicyTable(akt, ((("Kd", "Ah"), (0.2, 0.5, 0.3 + 1e-7)),))                       # innerhalb 1e-6
    wirft(lambda: PolicyTable(akt, ((("Kd", "Ah"), (0.2, 0.5, 0.3)),), undefiniert=frozenset({("Ah", "Kd")})),
          "Zeile UND undefiniert")
    wirft(lambda: PolicyTable((ActionKey.check(), ActionKey.check()), ()), "aktionen doppelt")

    # --- 6. RiverPlan: oeffentliches Gating, Pfade, Status-Vokabular
    root_st = dict(st); root_st["history"] = st["history"][:9]   # bis inkl. river-deal (Engine: 6 Aktionen + 3 deals)
    root_pl = [dict(p, committed_street=0) for p in st["players"]]
    root_st.update(players=root_pl, pot=1400, current_bet=0,
                   legal={"to_act": 1, "to_call": 0, "can_check": True, "can_call": False, "can_raise": True,
                          "is_bet": True, "raise_min": 100, "raise_max": 19300, "pot": 1400}, to_act=1)
    root = PolicySnapshot.aus_state(root_st, "v10_r10_stack", "k")
    ok(root.pot_bei_strassenbeginn() == 1400 and len(root.historie) == 6, "Root = River-Beginn")
    frei = [r + su for r in _RANKS for su in _SUITS if r + su not in root.board]     # das echte Board ist geseedet
    hero6 = {(frei[0], frei[1]): 0.5, (frei[2], frei[3]): 0.5}
    vill6 = {(frei[4], frei[5]): 0.25, (frei[6], frei[7]): 0.75}
    rs_root = RangeState.aus(hero6, vill6, root.board, "k1_likelihood", "normiert_summe_1", "ok", "h7")
    plan = RiverPlan(root, rs_root, "baum", "konf", (((), pt), ((ActionKey.check(),), "tensor:0")), (),
                     pot_river=1400, schwelle_chips=1500, aktiviert=False, fallback_status="nicht_aktiviert")
    ok(plan.tabelle() is pt, "Root-Tabelle")
    plan_on = RiverPlan(root, rs_root, "baum", "konf", (((), pt),), (), pot_river=1500, aktiviert=True,
                        private_seed_quelle="test_seed", deadline_status="iterations_deadline")
    ok(plan_on.aktiviert, "Schwelle inklusiv (>= 1500)")
    wirft(lambda: RiverPlan(root, rs_root, "b", "k", (((), pt),), (), pot_river=1400, aktiviert=True), "aktiviert trotz pot_river < Schwelle")
    wirft(lambda: RiverPlan(root, rs_root, "b", "k", (((), pt),), (ActionKey.call(),), pot_river=2000, aktiviert=True), "unbekannter Pfad")
    RiverPlan(snap, rs_root, "b", "k", (), (), pot_river=2000, aktiviert=True)         # positiv: jeder River-Snapshot ist ein legaler Root
    wirft(lambda: RiverPlan(root, rs_root, "b", "k", (), (), pot_river=2000, aktiviert=True, fallback_status="egal"), "Status-Vokabular")
    fremd = tuple(frei[8:13])                                                       # ein anderes 5er-Board
    rs_fremd = RangeState.aus(hero6, vill6, fremd, "tracker", "unnormiert_skaleninvariant", "ok", "h8")
    wirft(lambda: RiverPlan(root, rs_fremd, "b", "k", (), (), pot_river=2000, aktiviert=True), "ranges.board ≠ root.board")

    # --- 7. EntscheidungsTrace
    tr = EntscheidungsTrace(basis=ActionKey.check(), texassolver=ActionKey.raise_to(900),
                            guards=(("wert_bremse", ActionKey.check()),),
                            plan_verteilung=((ActionKey.check(), 0.4), (ActionKey.raise_to(1050), 0.6)),
                            legalitaet=ActionKey.raise_to(1050), sample_u=0.73, final=ActionKey.raise_to(1050),
                            hand_adresse="3012345", decision_addr="river/0")
    ok(tr.final.chips == 1050, "Trace ok")
    wirft(lambda: EntscheidungsTrace(basis=ActionKey.check(), final=ActionKey.check(),
                                     plan_verteilung=((ActionKey.check(), 0.4), (ActionKey.raise_to(1050), 0.6)),
                                     legalitaet=ActionKey.check()), "Mischung ohne sample_u")
    EntscheidungsTrace(basis=ActionKey.check(), final=ActionKey.check(),
                       plan_verteilung=((ActionKey.check(), 1.0), (ActionKey.raise_to(1050), 0.0)),
                       legalitaet=ActionKey.check())                                     # p∈{0,1}: kein Sample noetig
    wirft(lambda: EntscheidungsTrace(basis=ActionKey.check(), final=ActionKey.call(),
                                     plan_verteilung=((ActionKey.check(), 1.0),), legalitaet=ActionKey.check()),
          "final ≠ legalitaet")
    wirft(lambda: EntscheidungsTrace(basis=ActionKey.check(), final=ActionKey.call()), "final ohne Plan ≠ Basis")
    ok(EntscheidungsTrace(basis=ActionKey.check(), texassolver=ActionKey.raise_to(900), final=ActionKey.raise_to(900)).final.chips == 900,
       "TexasSolver ERSETZT die Basis")
    wirft(lambda: EntscheidungsTrace(basis=ActionKey.check(), final=ActionKey.check(), offtree=True), "offtree ohne Status")
    wirft(lambda: EntscheidungsTrace(basis=ActionKey.check(), final=ActionKey.check(), sample_u=1.0), "sample_u=1.0")

    print(f"contracts {KONTRAKT_VERSION}: {n} Pruefungen gruen | {gpu_check} | Engine-History {len(st['history'])} "
          f"Eintraege -> {len(snap.historie)} Schritte | pot_river {snap.pot_bei_strassenbeginn()}")
    return n


if __name__ == "__main__":
    _selbsttest()
