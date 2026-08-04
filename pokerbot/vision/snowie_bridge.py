"""PokerSnowie-BRÜCKE (User, 2026-08-03): unser Produkt-Bot spielt AUTOMATISCH gegen PokerSnowie 4.

WARUM head-to-head statt Grader-Urteil: Snowies Error-Rate ist SEIN Modell-Urteil (und seine Skala
bestraft Frequenz-Abweichungen hart). Ein direktes Duell hängt von niemandes Meinung ab — es zählt nur,
wer die Chips hat (Profit-Empirismus, CLAUDE.md). Diese Brücke erzeugt genau dieses Duell.

SCHLEIFE:  Fenster capturen -> VLM liest den Tisch -> obs für unseren Bot -> ctypes-Klick zurück.
Held = derselbe Verbund wie im Trainer-GTO-Modus: tag-Kern multiway, Prince v2.2 sobald heads-up.

SICHERHEIT (bindend — ein geratener Zug verseucht die MESSUNG und kann einen Stack verschenken):
  * Jede Unklarheit (Tisch nicht gefunden / Karten unlesbar / Aktionsknöpfe uneindeutig) -> PAUSE,
    niemals raten. `--strict` (Default) bricht ab; ohne strict wird gewartet und neu gelesen.
  * Wir klicken NUR die drei Aktions-Buttons + das Betrags-Feld dieses einen Fensters.
  * Jede Entscheidung wird nach data/vision/snowie_session_*.jsonl geloggt (Nachrechnen möglich).

KOSTEN/TEMPO: ein VLM-Call pro EIGENER Entscheidung (~4/Hand). Der Karten-/Ziffern-Cache (Phase 2,
`--cache`) merkt sich erkannte Sprites per Bild-Hash und macht Folgeläufe gratis + schnell.

  python -m pokerbot.vision.snowie_bridge --probe            # EINE Lesung, nichts klicken
  python -m pokerbot.vision.snowie_bridge --hands 50         # 50 Hände spielen
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import time
from datetime import datetime

from PIL import ImageGrab

from pokerbot.vision.screen_reader import pick_window, to_b64

OUT_DIR = os.path.join("data", "vision")
WINDOW_PAT = "PokerSnowie"
SETTLE_S = 0.22         # Wartezeit nach einem Klick (Animationen aus -> kurz reicht)
POLL_S = 0.10           # Pause zwischen Lesungen, wenn wir nicht am Zug sind
MAX_STALE = 400        # grosszuegig: die Notausfahlt loest Deadlocks, nicht der Abbruch
BLOCK_GIVEUP = 12      # so viele Blockaden am STUECK -> diese Hand aufgeben (Fold) und weiter          # so viele erfolglose Lesungen hintereinander -> Abbruch (Snowie hängt/Hand vorbei)

# Layout als BRUCHTEILE des Fensters (PokerSnowie 4, aus der Live-Vermessung 2026-08-03). Bruchteile
# statt Pixel: überlebt Fenstergrößen-Änderungen, solange das Layout proportional skaliert.
FRAC = {
    "btn_fold":   (0.360, 0.892),
    "btn_mid":    (0.479, 0.892),      # CALL oder CHECK
    "btn_right":  (0.596, 0.892),      # RAISE oder BET
    "amount":     (0.939, 0.876),      # Betrags-Eingabefeld
    "pre_quarter": (0.710, 0.876), "pre_half": (0.764, 0.876),
    "pre_pot": (0.822, 0.876), "pre_allin": (0.878, 0.876),
}

_user32 = ctypes.windll.user32
try:
    _user32.SetProcessDPIAware()          # sonst weichen Klick- von Screenshot-Koordinaten ab (HiDPI)
except Exception:  # noqa: BLE001
    pass

_SYSTEM = (
    "You read a PokerSnowie 4 training table screenshot for a bot. Be literal and conservative: report "
    "ONLY what is visibly rendered. Hero is the seat whose two hole cards are FACE-UP (labelled 'hero'). "
    "Money is shown in dollars. The three big buttons at the bottom are hero's legal actions; read their "
    "labels AND amounts exactly (e.g. 'CALL $2', 'CHECK', 'RAISE $4', 'BET $2'). If no buttons are shown, "
    "it is not hero's turn. TRUST THE SUIT SYMBOL, not the colour."
)
_CARD = {"type": "string", "description": "rank+suit like 'As','Td','7h','2c'"}
SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["table_found", "hero_turn", "street", "hero_cards", "board", "pot", "hero_stack",
                 "seats_clockwise", "seats", "actions", "notes"],
    "properties": {
        "table_found": {"type": "boolean"},
        "hero_turn": {"type": "boolean", "description": "true only if the action buttons are visible/enabled"},
        "street": {"type": "string", "enum": ["preflop", "flop", "turn", "river", "between_hands", "unknown"]},
        "hero_cards": {"type": "array", "items": _CARD, "maxItems": 2},
        "board": {"type": "array", "items": _CARD, "maxItems": 5},
        "pot": {"type": ["number", "null"], "description": "TOTAL POT in dollars"},
        "hero_stack": {"type": ["number", "null"], "description": "hero's stack in dollars"},
        # ARCHITEKTUR (nach dem ersten Live-Probe-Lauf korrigiert): das VLM liefert nur SICHTBARE FAKTEN,
        # jede poker-logische ABLEITUNG passiert in Python. Gemessen: das Modell las Karten/Pot/Beträge
        # fehlerfrei, aber nannte den SB "BB", zählte gefoldete Sitze mit und erfand einen Raise.
        "seats_clockwise": {
            "type": "array",
            "description": "ALL seat labels in CLOCKWISE seating order, starting with the seat that has the "
                           "white dealer-button chip 'D'. Use the on-screen names ('hero', 'snowie3', ...). "
                           "This is a pure reading task: follow the seats around the oval.",
            "items": {"type": "string"}},
        "seats": {
            "type": "array",
            "description": "one entry per seat shown at the table",
            "items": {"type": "object", "additionalProperties": False,
                      "required": ["label", "bet_in_front", "folded"],
                      "properties": {
                          "label": {"type": "string", "description": "the on-screen name at that seat"},
                          "bet_in_front": {"type": "number",
                                           "description": "dollars in the chip stack in front of THIS seat "
                                                          "this street; 0 when nothing is in front"},
                          "folded": {"type": "boolean",
                                     "description": "true when the seat is greyed out / has no cards"}}}},
        "actions": {
            "type": "object", "additionalProperties": False,
            "required": ["can_fold", "can_check", "can_call", "call_amount", "can_raise",
                         "raise_label", "raise_min_amount"],
            "properties": {
                "can_fold": {"type": "boolean"},
                "can_check": {"type": "boolean"},
                "can_call": {"type": "boolean"},
                "call_amount": {"type": ["number", "null"], "description": "dollars shown on the CALL button"},
                "can_raise": {"type": "boolean"},
                "raise_label": {"type": "string", "description": "'RAISE', 'BET' or '' if absent"},
                "raise_min_amount": {"type": ["number", "null"],
                                     "description": "dollars shown on the RAISE/BET button"}}},
        "notes": {"type": "string", "description": "anything ambiguous; '' when the read is clean"},
    },
}


# ---------------------------------------------------------------- Fenster / Eingabe
VK_ESCAPE = 0x1B


_ESC_SEEN = False


def esc_pressed() -> bool:
    """True, sobald ESC gedrueckt WURDE — der Lauf endet sauber und gibt die Maus frei.

    Zwei Gruende, warum das vorher nicht zuverlaessig ansprach (User-Fund): 0x8000 meldet nur, ob
    die Taste GERADE gehalten wird, und eine Lesung dauert ~800ms — ein kurzer Druck fiel schlicht
    zwischen zwei Abfragen. Das niederwertige Bit meldet dagegen "seit der letzten Abfrage gedrueckt".
    Und einmal gesehen, bleibt der Wunsch gemerkt: abbrechen heisst abbrechen.
    """
    global _ESC_SEEN
    if _user32.GetAsyncKeyState(VK_ESCAPE) & 0x8001:
        _ESC_SEEN = True
    return _ESC_SEEN


def _sleep(seconds: float) -> None:
    """Warten, ohne ESC zu verschlafen: in kurzen Scheiben, jede mit einer Abfrage."""
    end = time.perf_counter() + seconds
    while time.perf_counter() < end:
        if esc_pressed():
            return
        time.sleep(min(0.05, max(0.0, end - time.perf_counter())))


def window_box() -> tuple[int, int, int, int]:
    w = pick_window(WINDOW_PAT)
    if not w:
        raise RuntimeError(f"Kein Fenster mit '{WINDOW_PAT}' gefunden — läuft PokerSnowie?")
    return w["bbox"]


def grab(bbox):
    return ImageGrab.grab(bbox=bbox, all_screens=True)


def _click_frac(bbox, key: str) -> None:
    l, t, r, b = bbox
    fx, fy = FRAC[key]
    x, y = int(l + (r - l) * fx), int(t + (b - t) * fy)
    _user32.SetCursorPos(x, y)
    time.sleep(0.05)
    _user32.mouse_event(0x0002, 0, 0, 0, 0)      # LEFTDOWN
    time.sleep(0.03)
    _user32.mouse_event(0x0004, 0, 0, 0, 0)      # LEFTUP


def _type_number(value: float) -> None:
    """Betrag ins fokussierte Feld tippen (Ctrl+A ersetzt den alten Wert). Nur Ziffern + Punkt."""
    _user32.keybd_event(0x11, 0, 0, 0)           # CTRL down
    _user32.keybd_event(0x41, 0, 0, 0)           # A
    _user32.keybd_event(0x41, 0, 2, 0)
    _user32.keybd_event(0x11, 0, 2, 0)
    time.sleep(0.05)
    txt = f"{value:.2f}".rstrip("0").rstrip(".")
    for ch in txt:
        vk = 0x30 + int(ch) if ch.isdigit() else 0xBE      # VK_OEM_PERIOD
        _user32.keybd_event(vk, 0, 0, 0)
        _user32.keybd_event(vk, 0, 2, 0)
        time.sleep(0.02)


# ---------------------------------------------------------------- Lesen + Übersetzen
def read_local(img=None) -> dict:
    """LOKALE Lesung (Standard seit 2026-08-04): keine API, ~0.1 s statt ~4 s, 0 statt ~4 ct pro Zug."""
    from pokerbot.vision import snowie_state as SS
    return SS.read_state(img, learn=True)


def to_obs_local(s: dict, bb_dollars: float = 2.0, committed: float = 0.0) -> dict:
    """Lokaler Zustand -> obs unserer Engine. Check/Call folgen aus den EINSAETZEN, nicht aus Buttons."""
    def chips(x):
        return int(round((x or 0) / bb_dollars * 100))
    board = list(s.get("board") or [])
    street = "preflop" if not board else {3: "flop", 4: "turn", 5: "river"}.get(len(board), "flop")
    to_call = chips(s.get("call_amount"))
    stack = chips((s.get("stacks") or {}).get("hero"))
    # mein Einsatz dieser Strasse: bevorzugt aus der Stack-Differenz (gross gesetzt, zuverlaessig),
    # ersatzweise aus dem gelesenen Einsatz-Text.
    mine = chips(committed) or chips(s.get("hero_bet") or 0)
    # RAUSCHBODEN 1bb (Audit run_v12): ein $1-Stack-Lesefehler wurde als Einsatz verbucht -> UTG
    # mit mine=50 und Phantom-raises=1, aus Open-Spots wurden "facing raise"-Folds. Wahrheit unter
    # 1bb sind die BLINDS der Position; das Stack-Delta zaehlt erst, wenn es KLAR darueber liegt
    # (jede echte Aktion kostet >= 1bb).
    blind = {"SB": 50, "BB": 100}.get(s.get("hero_position") or "", 0) if street == "preflop" else 0
    mine = mine if mine >= blind + 100 else blind
    pot_chips = chips(s.get("pot"))
    if pot_chips > 0:
        # INVARIANTE: der Pot enthaelt meinen Einsatz — mine > pot ist immer ein Verfolgungsfehler.
        mine = min(mine, pot_chips)
    mx = mine + to_call                            # IDENTITAET: Einsatzniveau = meins + zu callen
    raises = 0 if mx <= 100 else (1 if mx <= 400 else 2)      # bb = 100 Chips
    return {
        "hole": [c for c in (s.get("hero_cards") or []) if c], "board": board,
        "to_call": to_call, "pot": chips(s.get("pot")), "my_stack": stack, "bb": 100,
        "n_active": max(2, int(s.get("players_in_hand") or 2)),
        "position": s.get("hero_position") or "MP",
        "preflop_raises": raises if street == "preflop" else 0,
        "cur_bet": mx, "my_committed_street": mine, "street": street,
        "can_check": bool(s.get("can_check")), "can_call": to_call > 0,
        "can_raise": stack > to_call,
        # Der RAISE-Button traegt den SLIDER-VorSCHLAG, nicht das Minimum — und sein '$' wurde
        # einmal als '3' gelesen ('$8' -> '38'): die Engine squeezte ihr vermeintliches "Minimum"
        # von 19bb mit AJs/KQs/QQ (run_v14, Frame-Beweis chk_d03). Das Minimum wird darum
        # BERECHNET: 2*Einsatzniveau ist immer >= legal (der Raise-Zuwachs kann das Niveau nie
        # uebersteigen), und zu niedrige Eingaben korrigiert Snowie selbst nach oben.
        "raise_min": min(stack, max(2 * mx, 100)),
        "raise_max": stack + mine,
    }


def read(img) -> dict:
    from research.llm import openai_json
    state, _ = openai_json(_SYSTEM, "Read this PokerSnowie table.", SCHEMA, "snowie_table",
                           images=[to_b64(img)], max_tokens=2000)
    return state


_POS_BY_OFFSET = {0: "BTN", 1: "SB", 2: "BB", 3: "UTG", 4: "HJ", 5: "CO"}
HERO_LABEL = "hero"


def derive(s: dict, bb_dollars: float) -> dict:
    """Sichtbare Fakten -> Poker-Logik (Position, Spielerzahl, Raise-Zahl). Reines Python, kein VLM."""
    order = [str(x) for x in (s.get("seats_clockwise") or [])]
    seats = {str(x.get("label")): x for x in (s.get("seats") or [])}
    hero_key = next((k for k in seats if k.lower() == HERO_LABEL), None)
    hero_idx = next((i for i, k in enumerate(order) if k.lower() == HERO_LABEL), None)
    n_seats = len(order)
    pos = "unknown"
    if hero_idx is not None and 2 <= n_seats <= 6:
        # order[0] hat den Button. Bei weniger als 6 Sitzen fehlen die frühen Positionen von HINTEN,
        # nicht die Blinds -> Offset direkt abbilden ist korrekt für 6-max-Vollbesetzung.
        pos = _POS_BY_OFFSET.get(hero_idx, "unknown") if n_seats == 6 else (
            {0: "BTN", 1: "SB", 2: "BB"}.get(hero_idx, "CO"))
    live = [k for k, v in seats.items() if not v.get("folded")]
    bets = [float(v.get("bet_in_front") or 0) for v in seats.values()]
    mine = float((seats.get(hero_key) or {}).get("bet_in_front") or 0)
    mx = max(bets) if bets else 0.0
    # Raise-Zahl aus den Beträgen: solange der größte Einsatz == BB ist, hat NIEMAND erhöht.
    raises = 0 if mx <= bb_dollars + 1e-9 else (1 if mx <= 4 * bb_dollars else 2)
    return {"position": pos, "players_in_hand": max(2, len(live)),
            "hero_bet": mine, "max_bet": mx, "preflop_raises": raises}


def to_obs(s: dict, bb_dollars: float = 2.0) -> dict:
    """Snowie-Lesung -> obs-Dict unserer Engine (Chips: bb = 100)."""
    def chips(x):
        return int(round((x or 0) / bb_dollars * 100))
    a = s["actions"]
    to_call = chips(a.get("call_amount")) if a.get("can_call") else 0
    board = list(s.get("board") or [])
    street = s.get("street") if s.get("street") in ("preflop", "flop", "turn", "river") else (
        "preflop" if not board else {3: "flop", 4: "turn", 5: "river"}.get(len(board), "flop"))
    raise_min = chips(a.get("raise_min_amount")) if a.get("can_raise") else 0
    stack = chips(s.get("hero_stack"))
    d = derive(s, bb_dollars)
    mine = chips(d["hero_bet"])
    cur_bet = chips(d["max_bet"]) or (mine + to_call)
    return {
        "hole": list(s.get("hero_cards") or []), "board": board,
        "to_call": to_call, "pot": chips(s.get("pot")), "my_stack": stack, "bb": 100,
        "n_active": d["players_in_hand"], "position": d["position"],
        "preflop_raises": d["preflop_raises"] if street == "preflop" else 0,
        "cur_bet": cur_bet, "my_committed_street": mine, "street": street,
        "can_check": bool(a.get("can_check")), "can_call": bool(a.get("can_call")),
        "can_raise": bool(a.get("can_raise")),
        "raise_min": raise_min or 0, "raise_max": stack,
    }


def sane(s: dict, bb: float = 2.0) -> str | None:
    """None = Lesung brauchbar; sonst der GRUND, warum wir NICHT handeln (Sicherheitsgatter)."""
    if not s.get("table_found"):
        return "kein Tisch erkannt"
    if not s.get("hero_turn"):
        return "wir sind nicht am Zug"
    cards = s.get("hero_cards") or []
    if len(cards) != 2:
        return f"Hole Cards unlesbar ({cards})"
    a = s.get("actions") or {}
    if not (a.get("can_fold") or a.get("can_check") or a.get("can_call")):
        return "keine Aktionsknöpfe erkannt"
    if a.get("can_call") and not a.get("call_amount"):
        return "CALL ohne Betrag"
    if s.get("pot") in (None, 0):
        return "Pot unlesbar"
    # Position ist NICHT optional: ohne sie spielt der Kern jeden Spot als 'MP' und over-foldet
    # systematisch in den Blinds (live gemessen am ersten Probe-Lauf: A4o im SB gefoldet).
    d = derive(s, bb)
    if d["position"] not in ("UTG", "HJ", "CO", "BTN", "SB", "BB"):
        return f"Position nicht ableitbar (Sitzreihenfolge={s.get('seats_clockwise')})"
    if not (s.get("seats") or []):
        return "Sitzdaten fehlen"
    # Konsistenz-Kreuzcheck: der CALL-Button muss zum Einsatz-Delta passen (fängt Fehlablesungen)
    a = s["actions"]
    if a.get("can_call"):
        soll = d["max_bet"] - d["hero_bet"]
        ist = float(a.get("call_amount") or 0)
        if abs(soll - ist) > max(0.02, 0.25 * max(ist, 1e-9)):
            return f"Widerspruch: CALL {ist} vs Einsatz-Delta {soll:.2f}"
    return None


# ---------------------------------------------------------------- Spielen
def _check_is_free(s: dict) -> bool:
    """Ist Checken NACHWEISLICH gratis? Nur dann darf der Notausgang den mittleren Button druecken.

    can_check=False entsteht auch, wenn der Betrag auf dem Button UNLESBAR war — das heisst "ich
    weiss es nicht", nicht "Check ist unmoeglich". Der Notausgang las es als Zweites und foldete
    (User-Fund: "der Bot foldet jetzt alles"). Zweitzeuge sind darum die EINSAETZE: liegt Heros
    Einsatz bereits auf Hoehe des hoechsten, steht nichts zu callen an und Check ist gratis.
    """
    if (s.get("buttons") or {}).get("can_check"):
        return True
    bets = s.get("bets") or {}
    live = s.get("live") or {}
    mine = bets.get("hero")
    others = [v for seat, v in bets.items() if seat != "hero" and live.get(seat) and v is not None]
    if mine is None or any(v is None for seat, v in bets.items() if live.get(seat)):
        return False                      # ein Einsatz unlesbar -> kein Zweitzeuge -> nicht raten
    return mine + 1e-6 >= max(others, default=0.0)


MONEY_TOL = 30.0        # Toleranz der Chip-Erhaltung in Dollar: unlesbare Einzelstacks wackeln


class HandTracker:
    """Der ZUSTAND EINER HAND — die Klasse von Fehlern, die eine Einzelbild-Pruefung nie faengt.

    Gemessen (User-Auftrag "pruefe, dass wir nicht falsch spielen"): die Position sprang INNERHALB
    einer Hand von BTN (preflop) auf UTG (postflop) — unmoeglich, der Button bewegt sich nicht
    mitten in der Hand; und der Pot sank einmal von 4.5 auf 4.0, was es im Poker nicht gibt.
    Beides sind Widersprueche gegen den VERLAUF, nicht gegen ein einzelnes Bild.

    Darum: Position EINMAL pro Hand festnageln (der erste saubere Lesewert gilt bis zum Handende),
    und der Pot darf innerhalb einer Hand nie schrumpfen — tut er es, ist es ein Lesefehler.
    Handwechsel = Board wird wieder leer ODER der Stack springt nach oben (Pot gewonnen/Rebuy).
    """

    def __init__(self):
        self.reset()

    def reset(self):
        self.fresh = False
        self.position = None
        self.pot_max = 0.0
        self.last_board = None
        self.last_stack = None
        self.hole = None
        self.money_seen = None       # Summe der sichtbaren Stacks bei der letzten Lesung

    def observe(self, board_len: int, stack, pot, position, hole=None,
                stacks_sum: float | None = None) -> str | None:
        """-> Fehlermeldung bei Verlaufs-Widerspruch, sonst None. Nagelt Position/Pot fest."""
        # Handwechsel: das Board wird kuerzer, der Stack springt hoch (Pot gewonnen/Rebuy) — ODER
        # der Pot faellt bei LEEREM Board. Letzteres fehlte: endet eine Hand schon praeflop (alle
        # folden), war das Board nie belegt, wird also auch nicht kuerzer; der Waechter hielt die
        # neue Hand fuer die alte und ihre Blinds fuer einen Lesefehler ("Pot schrumpft 8 -> 3").
        # Praeflop waechst der Pot nur — faellt er dort, ist die Hand vorbei.
        pot_dropped = pot is not None and board_len == 0 and pot + 1e-6 < self.pot_max
        # DAS street-unabhaengige Signal (Befund run_v11): endete die letzte Hand auf dem Flop und
        # beginnt Heros naechster Zug wieder auf einem Flop, wird das Board nie kuerzer und der
        # Pot-Waechter blockierte endlos ("Pot schrumpft 18 -> 3"). Heros KARTEN wechseln dagegen
        # mit jeder Hand — gleiche zwei Karten zweimal in Folge sind 1:1080.
        hole_changed = bool(hole) and bool(self.hole) and tuple(hole) != tuple(self.hole)
        new_hand = (self.last_board is not None and board_len < self.last_board) or pot_dropped or                    hole_changed or                    (self.last_stack is not None and stack is not None and stack > self.last_stack + 0.01
                    and board_len == 0)
        if new_hand or self.position is None:
            self.reset()
            self.position = position
        if hole and all(hole):
            self.hole = tuple(hole)
        # NACH dem reset() setzen — reset() loescht das Flag (so wurde der Fix vom eigenen Test gefangen)
        self.fresh = bool(new_hand)
        self.last_board, self.last_stack = board_len, stack
        if pot is not None:
            if pot + 1e-6 < self.pot_max:
                return f"Pot schrumpft {self.pot_max} -> {pot} (im Poker unmoeglich = Lesefehler)"
            # CHIP-ERHALTUNG (Lauf-3-Obduktion, -1812 Dollar): verlorene Dezimalpunkte machten aus
            # 7.38-Dollar-Poetten 738-Dollar-Fantasien UNTER der Plausibilitaetsgrenze - Prince bekam
            # Traum-Pot-Odds und jammte 13x. Das Scoreboard-Axiom des Projekts gilt auch hier:
            # der Pot kann nur um das wachsen, was die sichtbaren Stacks verloren haben.
            if (self.pot_max > 0 and self.money_seen is not None and stacks_sum is not None):
                influx = max(0.0, self.money_seen - stacks_sum)
                if pot > self.pot_max + influx + MONEY_TOL:
                    return (f"Pot springt {self.pot_max:g} -> {pot:g}, aber die Stacks verloren nur "
                            f"{influx:g} - Chip-Erhaltung verletzt (Lesefehler)")
            self.pot_max = max(self.pot_max, pot)
        if stacks_sum is not None:
            self.money_seen = stacks_sum
        return None

    def fixed_position(self, fallback):
        return self.position or fallback


class StreetTracker:
    """Heros Einsatz DIESER Strasse aus der STACK-DIFFERENZ, nicht aus der winzigen Einsatz-Schrift.

    WARUM (User-Frage 2026-08-04): ohne das aktuelle Einsatzniveau wuesste der Bot nicht, ob er in
    einem Single-Raised-, 3-Bet- oder 4-Bet-Pot sitzt — in Multiway-Poets der teuerste Lesefehler,
    weil die ganze Range-Logik daran haengt; ausserdem verankern die Sizing-Formeln darauf.
    Der Stack ist GROSS gesetzt und wird zuverlaessig gelesen. Es gilt exakt:
        mein Einsatz auf dieser Strasse = Stack bei Strassenbeginn - aktueller Stack
        aktuelles Einsatzniveau        = mein Einsatz + was der Button zu callen verlangt
    Damit ist cur_bet eine IDENTITAET, keine Schaetzung — ganz ohne die kleine Schrift."""

    def __init__(self):
        self.reset()

    def reset(self):
        """Beim HANDWECHSEL rufen. Der eigene Strassen-Schluessel ist nur (board_len,) — endet eine
        Hand praeflop, faengt die naechste mit demselben Schluessel an und die Referenz bleibt stehen;
        der Stack SINKT zwischen Haenden (Blinds, verlorene Poette), die Differenz wurde als 'Einsatz'
        verbucht und wuchs ueber Haende an (gemessen: committed 250 in einem 150er-Pot, drei Haende
        in Folge -> Phantom-'raises', der Grund fuer wilde Preflop-Folds)."""
        self.street_key = None
        self.stack_at_street = None

    def update(self, board_len: int, stack: float | None) -> float:
        """-> Heros Einsatz auf der aktuellen Strasse (Dollar). 0.0, solange nichts bekannt ist."""
        key = (board_len,)
        if stack is None:
            return 0.0
        if key != self.street_key:                 # neue Strasse (Board waechst) -> Referenz neu setzen
            self.street_key = key
            self.stack_at_street = stack
        if stack > (self.stack_at_street or 0):    # Stack GEWACHSEN = neue Hand/Pot gewonnen -> Reset
            self.stack_at_street = stack
        return max(0.0, (self.stack_at_street or stack) - stack)


def make_hero():
    """Der Trainer-Verbund KOMPLETT: tag-Kern multiway, PRINCE v2.2 sobald der Pot heads-up ist.

    Bis 2026-08-04 stand das nur im Docstring — gebaut war allein der tag-Kern, und da fast jeder
    Snowie-Pot heads-up endet, spielte praktisch NIE der validierte Prince (User-Frage deckte es auf).
    """
    os.environ.setdefault("POKERB_PRINCE", "1")   # VOR dem Strategie-Import: expandiert das v2.2-Profil
    from pokerbot.arena.sixmax import PROFILES, SixMaxBot
    bot = SixMaxBot(0, PROFILES["tag"])
    bot._read = lambda obs: {}
    return bot


# 6-max-Open-Anteile nach Position (Standard-Solver-Groessenordnungen; Prior, der Bayes-Walk korrigiert)
OPEN_FRAC = {"UTG": 0.15, "HJ": 0.19, "CO": 0.26, "BTN": 0.42, "SB": 0.36, "BB": 0.25}


def make_seeded_tracker(villain_pos: str | None, villain_raised: bool | None):
    """Tracker-Fabrik: 6-max-POSITIONS-Prior fuer die Gegner-Range im kollabierten HU-Pot.

    Der User-Einwand (2026-08-04, korrekt): die HU-Projektion laese einen MP-Open als ~50%-HU-Range.
    Hier bekommt Seat 1 (der Gegner; Hero ist per Projektion Seat 0) stattdessen die 6-max-Range
    seiner ECHTEN Position als Startgewichte — Open ~15-42% je Sitz, Caller/3-Better ueber die
    Trainer-Prioren (range_story) positions-skaliert. Danach laeuft der unveraenderte Bayes-Walk
    des Trackers ueber die beobachtete History: jede Flop/Turn/River-Aktion korrigiert den Prior.
    """
    from pokerbot.coach.range_story import CALLER_FRAC, RAISER_FRAC
    from pokerbot.strategy import preflop_strength as PS
    from pokerbot.strategy import ranges as R
    from pokerbot.strategy.range_tracker import RangeTracker, _preflop_raises

    class SixMaxSeededTracker(RangeTracker):
        def _init_preflop(self, state) -> None:
            super()._init_preflop(state)                     # Hero-Seite + Fallback unveraendert
            if villain_pos not in OPEN_FRAC:
                return
            n = min(max(_preflop_raises(state), 0), 3)
            pos_mult = OPEN_FRAC[villain_pos] / 0.20         # 0.20 = der positionsblinde Trainer-Anker
            base = CALLER_FRAC.get(n, 0.28) if villain_raised is False else RAISER_FRAC.get(max(n, 1), 0.20)
            frac = min(0.85, max(0.03, base * pos_mult))
            combos = R.combos_for_classes(PS.range_top(frac), [])
            if combos:
                self.range[1] = {c: 1.0 for c in combos}
                self._normalize(1)

    return SixMaxSeededTracker


class ActionLog:
    """Beobachtete Aktionen einer Hand als Tracker-History (Seat 0 = Hero, 1 = der HU-Gegner).

    Die Bruecke sieht nur Standbilder — aber die DELTAS zwischen Lesungen verraten die Aktionen:
    steigt des Gegners Einsatzniveau, hat er gesetzt/erhoeht; zieht er auf Heros Niveau gleich,
    hat er gecallt; wechselt die Strasse ohne Einsaetze, wurde durchgecheckt. Nur EINDEUTIGE
    Beobachtungen werden geloggt — eine spaerliche History senkt beim Tracker bloss die Konfidenz
    (der Fallback greift), eine falsche wuerde ihn vergiften.
    """

    def __init__(self):
        self.reset()

    def reset(self):
        self.rows: list[dict] = []
        self.street = "preflop"
        self.v_level = 0.0
        self.h_level = 0.0

    def observe(self, street: str, hero_bet_chips: int, villain_bet_chips: int | None) -> None:
        if street != self.street and street in ("flop", "turn", "river"):
            # Strassenwechsel: wurde die alte Strasse ohne Einsatz beendet, hat der Gegner gecheckt
            if self.street in ("flop", "turn") and self.v_level <= 0 and self.h_level <= 0:
                self.rows.append({"street": self.street, "player": 1, "action": "check"})
            self.rows.append({"action": "deal", "street": street})
            self.street, self.v_level, self.h_level = street, 0.0, 0.0
        if villain_bet_chips is None:
            return
        if villain_bet_chips > self.v_level + 1:
            act = "raise" if self.h_level > 0 or (street == "preflop" and villain_bet_chips > 100) else "bet"
            self.rows.append({"street": street, "player": 1, "action": act, "to": villain_bet_chips})
            self.v_level = float(villain_bet_chips)
        elif 0 < self.h_level <= villain_bet_chips + 1 and self.v_level < self.h_level:
            self.rows.append({"street": street, "player": 1, "action": "call"})
            self.v_level = self.h_level

    def hero(self, street: str, action: str, to_chips: int | None) -> None:
        row = {"street": street, "player": 0, "action": action}
        if to_chips:
            row["to"] = to_chips
            self.h_level = float(to_chips)
        self.rows.append(row)


class PrinceHU:
    """PRINCE v2.2 fuer Heads-up-Poette der Bruecke — derselbe Oracle-Pfad wie Trainer und Grader.

    Fabriziert aus der Vision-Lesung das trainer.decision.v1-Rekord, das record_to_hu_state erwartet;
    PrinceOracle macht daraus HU-Projektion -> PokerBot.decide -> api.legalize. Kein History-Kanal:
    die Bruecke sieht nur Standbilder, rec['history'] bleibt leer (Linien-Features degradieren sanft).
    """

    def __init__(self):
        from pokerbot.coach.oracle import PrinceOracle
        self.oracle = PrinceOracle()

    def decide(self, obs: dict, s: dict, observed: list | None = None,
               hero_raised_pf: bool | None = None) -> dict:
        live = s.get("live") or {}
        vills = [k for k, v in live.items() if v and k != "hero"]
        if len(vills) != 1:
            raise ValueError("kein HU-Pot")
        v = vills[0]
        positions = s.get("positions") or {}
        # 6-max-Prior fuer die Gegner-Range (User-Vorschlag): Position + Rolle statt HU-Annahme.
        villain_raised = None if hero_raised_pf is None else (not hero_raised_pf)
        self.oracle.bot.tracker_cls = make_seeded_tracker(positions.get(v), villain_raised)
        bb_d = 2.0
        vstack = (s.get("stacks") or {}).get(v)
        vstack_chips = int(round((vstack or 0) / bb_d * 100)) or obs["my_stack"]
        mine, to_call = obs["my_committed_street"], obs["to_call"]
        seats = [
            {"seat": 0, "pos": obs["position"], "stack": obs["my_stack"], "folded": False,
             "committed_total": mine, "all_in": False},
            {"seat": 1, "pos": positions.get(v) or "BB", "stack": vstack_chips, "folded": False,
             "committed_total": mine + to_call, "all_in": vstack_chips <= 0},
        ]
        legal = {"to_call": to_call, "pot": obs["pot"], "can_fold": to_call > 0,
                 "can_check": obs["can_check"], "can_call": obs["can_call"],
                 "can_raise": obs["can_raise"], "call_amount": to_call,
                 "is_bet": obs["street"] != "preflop" and to_call == 0,
                 "raise_min": obs["raise_min"], "raise_max": obs["raise_max"], "to_act": 0}
        # legal/to_call gehoeren IN den Spot: api.legalize duck-typet spot.legal/.to_call/.pot/.bb/.street
        spot = {"hero_seat": 0, "hero_pos": obs["position"], "hero_hole": obs["hole"],
                "seats": seats, "board": obs["board"], "pot": obs["pot"], "bb": 100,
                "street": obs["street"], "n_active": 2, "legal": legal, "to_call": to_call}
        hand_id = "snowie-" + "".join(obs["hole"])
        # SYNTHETISCHE History aus dem, was die Vision sicher weiss. Ohne sie zaehlte der Bot
        # preflop_raises=0 und lief in einen falschen Ast (gemessen: A7o BB vs Open -> ALL-IN).
        # Raise-Zahl aus dem Einsatzniveau, deal-Marker aus dem Board, die aktuelle Bet als letzter
        # Eintrag - grob, aber dieselbe Naeherung, die obs["preflop_raises"] ohnehin traegt.
        hist = []
        for k in range(obs.get("preflop_raises") or 0):
            amt = obs["cur_bet"] if (obs["street"] == "preflop" and k == (obs["preflop_raises"] or 1) - 1) else None
            hist.append({"street": "preflop", "player": 1, "action": "raise", "amount": amt})
        for st in ("flop", "turn", "river")[:max(0, len(obs["board"]) - 2)]:
            hist.append({"action": "deal", "street": st})
        if observed:
            seen_deals = {r.get("street") for r in observed if r.get("action") == "deal"}
            hist = [r for r in hist if not (r.get("action") == "deal" and r.get("street") in seen_deals)]
            hist.extend(observed)
        elif obs["street"] != "preflop" and to_call > 0:
            hist.append({"street": obs["street"], "player": 1, "action": "bet", "amount": to_call})
        rec = {"spot": spot, "obs": obs, "legal": legal, "history": hist,
               "street": obs["street"], "hand_id": hand_id,
               "spot_fp": hash((hand_id, obs["street"], obs["pot"], to_call)) & 0x7FFFFFFF}
        return self.oracle.decide(rec)


def act(bbox, obs: dict, decision: dict, bb_dollars: float) -> str:
    """Entscheidung in Klicks übersetzen. Rückgabe = was wir getan haben (fürs Log)."""
    action, amount = decision["action"], decision.get("amount")
    if action == "fold":
        _click_frac(bbox, "btn_fold")
        return "fold"
    if action == "check":
        _click_frac(bbox, "btn_mid")
        return "check"
    if action == "call":
        _click_frac(bbox, "btn_mid")
        return "call"
    if action == "allin":
        _click_frac(bbox, "pre_allin")
        time.sleep(0.3)
        _click_frac(bbox, "btn_right")
        return "allin"
    # NIE unter das Tisch-Minimum tippen: Snowie nimmt einen zu kleinen Betrag nicht an und setzt
    # stattdessen seinen eigenen Mindest-Raise — von aussen sieht das aus, als koennte der Bot keine
    # eigenen Groessen eingeben (User-Fund). Gemessen: unsere 2.5bb = $5 gegen ein Minimum von $6.
    chips = max(amount or obs["raise_min"], obs["raise_min"])
    dollars = chips / 100.0 * bb_dollars
    # ALL-IN statt Tippen, wenn das Ziel den RESTSTACK erreicht (Hand-553-Wurzel: Prince wollte
    # auf 527 raisen, hero hatte 347 uebrig - Snowie lehnte die Eingabe STILL ab und die
    # Schleife tippte endlos). Der Preset-Knopf ist fuer diesen Fall gebaut und immer legal.
    stack_dollars = (obs.get("my_stack") or 0) / 100.0 * bb_dollars
    my_street_dollars = (obs.get("my_committed_street") or 0) / 100.0 * bb_dollars
    if stack_dollars > 0 and dollars >= stack_dollars + my_street_dollars - 0.01:
        _click_frac(bbox, "pre_allin")
        time.sleep(0.3)
        _click_frac(bbox, "btn_right")
        return f"allin (Ziel {dollars:.2f} >= Stack)"
    _click_frac(bbox, "amount")
    time.sleep(0.15)
    _type_number(dollars)
    time.sleep(0.15)
    _click_frac(bbox, "btn_right")
    return f"raise ${dollars:.2f}"


def run(n_hands: int, strict: bool, bb_dollars: float, probe: bool) -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    log_path = os.path.join(OUT_DIR, f"snowie_session_{datetime.now():%Y%m%d_%H%M%S}.jsonl")
    bbox = window_box()
    print(f"Fenster: {bbox}  |  Log: {log_path}")
    if probe:
        s = read_local()
        print(json.dumps(s, indent=1, ensure_ascii=False))
        from pokerbot.vision import snowie_state as SS2
        blocker = SS2.gate(s)
        print("GATTER:", blocker or "OK — Lesung brauchbar")
        if not blocker:
            obs = to_obs(s, bb_dollars)
            d = make_hero().decide(obs)
            print(f"UNSER BOT: {d['action']} {d.get('amount')} | {d['rationale']['reasoning']}")
        return

    from pokerbot.vision import snowie_state as SS
    hero, decisions, stale = make_hero(), 0, 0
    alog, hero_raised_pf = ActionLog(), False
    same_state, last_sig = 0, None
    prince = None
    try:
        prince = PrinceHU()
        print("PRINCE v2.2 aktiv fuer Heads-up-Poette", flush=True)
    except Exception as e:  # noqa: BLE001 — ohne Prince spielt der Kern weiter, aber sichtbar
        print(f"PRINCE nicht verfuegbar ({e}) — tag-Kern spielt auch HU", flush=True)
    tracker = StreetTracker()
    hand = HandTracker()
    blocked_streak, forced, skipped_hands = 0, 0, []
    while decisions < n_hands * 4 and stale < MAX_STALE:
        if esc_pressed():
            print("ESC — Lauf gestoppt, Maus/Tastatur wieder frei.", flush=True)
            break
        s = read_local()
        blocker = SS.gate(s)
        # ESKALATION statt Aufgabe: ein REINER Einsatz-Widerspruch, der sich 3x wiederholt, ist
        # ein stabil falsch gelesener Chip-Text (Animationsflug) - alles Entscheidungskritische
        # ist dann gepiegelt gueltig, also ohne die Einsatz-Gatter entscheiden.
        if blocker and blocked_streak >= 3 and any(
                blocker.startswith(pfx) for pfx in ("Einsatzniveau", "Raise auf", "Call-Betrag")):
            loose = SS.gate(s, strict_bets=False)
            if loose is None:
                print(f"EINSATZ-GATTER umgangen nach {blocked_streak} Blocks: {blocker}", flush=True)
                blocker = None
            elif blocked_streak == 3:
                print(f"ESKALATION VERWEIGERT: Kern selbst unklar -> {loose}", flush=True)
        if blocker:
            stale += 1
            # NOTAUSFAHRT gegen den Deadlock: das Gatter verbietet zu handeln -> die Hand laeuft nicht
            # weiter -> derselbe Zustand blockiert erneut, endlos. Nach genug Versuchen geben wir DIESE
            # HAND auf (Fold) und markieren sie als AUSGESCHLOSSEN. Ein Fold ist die einzige Aktion,
            # die keine Annahme ueber den Tisch trifft; und eine bewusst verworfene, protokollierte
            # Hand ist ehrlicher als eine geratene.
            if blocker != "nicht am Zug":
                blocked_streak += 1
                if blocked_streak >= BLOCK_GIVEUP and s.get("hero_turn"):
                    try:
                        shot = os.path.join(OUT_DIR, "fails")
                        os.makedirs(shot, exist_ok=True)
                        from pokerbot.vision import snowie_local as _SL
                        _SL.grab().save(os.path.join(shot, f"fail_{forced:03d}.png"))
                        with open(os.path.join(shot, "reasons.txt"), "a", encoding="utf-8") as fh:
                            fh.write("fail_{:03d}  {}\n".format(forced, blocker))
                    except Exception:  # noqa: BLE001 — Diagnose darf den Lauf nie stoppen
                        pass
                    # AUFGEBEN heisst NICHT blind folden (User-Fund: der Bot warf AA weg).
                    # Ist Check GRATIS moeglich, ist Folden immer die schlechtere Wahl — und ob
                    # Check geht, sagt uns der Button zuverlaessig, auch wenn das Board unlesbar ist.
                    # Nur wenn wir zahlen muessten UND den Tisch nicht lesen koennen, wird gefoldet.
                    # KLICK-VERIFIKATION (Marathon-Obduktion): ein einziger nicht gelandeter
                    # Aufgabe-Klick liess die Bruecke stumm auf die naechste Hand warten, bis
                    # MAX_STALE die Etappe beerdigte - drei Etappen starben so. Jetzt wird nach
                    # dem Klick nachgelesen; aendert sich NICHTS, wird erneut geklickt (3x).
                    free = _check_is_free(s)
                    how = "CHECK (gratis)" if free else "Fold"
                    before_sig = (tuple(s.get("hero_cards") or []), len(s.get("board") or []),
                                  s.get("pot"))
                    for attempt in range(3):
                        _click_frac(bbox, "btn_mid" if free else "btn_fold")
                        _sleep(1.0)
                        try:
                            s2 = read_local()
                            sig2 = (tuple(s2.get("hero_cards") or []), len(s2.get("board") or []),
                                    s2.get("pot"))
                            if sig2 != before_sig or not s2.get("hero_turn"):
                                break
                            print(f"Aufgabe-Klick griff nicht (Versuch {attempt + 1}) - erneut",
                                  flush=True)
                        except Exception:  # noqa: BLE001 — Nachlesen darf die Aufgabe nie stoppen
                            break
                    forced += 1
                    skipped_hands.append(blocker)
                    blocked_streak, stale = 0, 0
                    print(f"HAND UEBERSPRUNGEN (#{forced}): {blocker} — {how}, aus der Messung ausgeschlossen",
                          flush=True)
                    _sleep(SETTLE_S)
                    continue
            if blocker == "nicht am Zug":
                _sleep(POLL_S)
                continue
            print(f"PAUSE ({stale}/{MAX_STALE}): {blocker} | notes={s.get('notes','')}")
            if strict:
                print("STRICT: Abbruch — lieber keine Messung als eine verseuchte.")
                return
            _sleep(POLL_S)
            continue
        # VERLAUFS-PRUEFUNG vor der Entscheidung: ein Widerspruch zum bisherigen Handverlauf ist ein
        # Lesefehler, auch wenn das Einzelbild sauber aussieht.
        bl = len(s.get("board") or [])
        hstack = (s.get("stacks") or {}).get("hero")
        _ssum = sum(v for v in (s.get("stacks") or {}).values() if v is not None)
        conflict = hand.observe(bl, hstack, s.get("pot"), s.get("hero_position"),
                                s.get("hero_cards"), stacks_sum=_ssum)
        if hand.fresh:
            tracker.reset()                      # neue Hand -> Einsatz-Referenz dieser Strasse neu
            alog.reset()
            hero_raised_pf = False
        # jede Lesung fuettert das Aktions-Log (nur der EINE HU-Gegner ist eindeutig zuzuordnen)
        _street = "preflop" if bl == 0 else {3: "flop", 4: "turn", 5: "river"}.get(bl, "flop")
        _live_v = [k for k, v in (s.get("live") or {}).items() if v and k != "hero"]
        _vb = (s.get("bets") or {}).get(_live_v[0]) if len(_live_v) == 1 else None
        _hb = (s.get("bets") or {}).get("hero")
        alog.observe(_street, int(round((_hb or 0) / bb_dollars * 100)),
                     None if _vb is None else int(round(_vb / bb_dollars * 100)))
        if conflict:
            blocked_streak += 1
            stale += 1
            print(f"PAUSE (Verlauf): {conflict}", flush=True)
            if blocked_streak >= BLOCK_GIVEUP and s.get("hero_turn"):
                _click_frac(bbox, "btn_mid" if _check_is_free(s) else "btn_fold")
                forced += 1
                skipped_hands.append(conflict)
                blocked_streak, stale = 0, 0
                hand.reset()
            _sleep(POLL_S)
            continue
        stale = blocked_streak = 0
        committed = tracker.update(bl, hstack)
        obs = to_obs_local(s, bb_dollars, committed)
        obs["position"] = hand.fixed_position(obs["position"])   # Button wandert nicht mitten in der Hand
        # WIEDERHOLUNGS-WAECHTER (Hand-553-Bug): landet eine Aktion nicht (Snowie lehnt z.B. einen
        # zu grossen Raise still ab), bleibt der Zustand identisch, die Schleife entscheidet
        # identisch neu und die Maus springt endlos Betragsfeld<->Button - das Gatter ist dabei
        # SAUBER, kein Blockade-Zaehler greift. Degradations-Leiter: nach 3 identischen
        # Wiederholungen raise->call, nach 3 weiteren -> Hand ehrlich aufgeben.
        cur_sig = (tuple(s.get("hero_cards") or []), len(s.get("board") or []), s.get("pot"),
                   (s.get("buttons") or {}).get("call_amount"))
        if cur_sig == last_sig:
            same_state += 1
        else:
            same_state, last_sig = 0, cur_sig
        d = None
        # PRINCE NUR POSTFLOP (User-Einwand 2026-08-04, korrekt): ein kollabierter 6-max-Pot ist
        # KEIN echtes Heads-up — ein MP-Open ist eine ~15-20%-Range, der HU-Bot laese denselben
        # Raise als ~45-85%-HU-Range und verteidigte viel zu weit. Preflop entscheidet darum der
        # positionstreue 6-max-Kern; Prince uebernimmt postflop (Value/Disziplin = sein Gewinn;
        # der HU-Range-Prior bleibt dort eine dokumentierte Naeherung, wie im Trainer/Grader).
        if prince is not None and obs.get("n_active") == 2 and obs.get("street") != "preflop":
            try:
                d = prince.decide(obs, s, observed=list(alog.rows), hero_raised_pf=hero_raised_pf)
            except Exception:  # noqa: BLE001 — Prince-Problem -> der Kern uebernimmt still (Trainer-Idiom)
                d = None
        if d is None:
            d = hero.decide(obs)
        if same_state >= 3 and d.get("action") in ("raise", "allin", "bet"):
            print(f"AKTION GREIFT NICHT ({same_state}x identischer Zustand) - degradiere zu Call",
                  flush=True)
            d = {"action": "call" if obs.get("can_call") else "check", "amount": None,
                 "rationale": {"reasoning": "Degradation: Raise landete nicht (Hand-553-Waechter)"}}
        if same_state >= 6:
            print("AKTION GREIFT WEITER NICHT - Hand wird aufgegeben", flush=True)
            skipped_hands.append("Aktion landet nicht (Hand-553-Waechter)")
            _click_frac(bbox, "btn_fold" if not _check_is_free(s) else "btn_mid")
            _sleep(SETTLE_S)
            same_state = 0
            continue
        did = act(bbox, obs, d, bb_dollars)
        if obs["street"] == "preflop" and d.get("action") in ("raise", "allin"):
            hero_raised_pf = True
        alog.hero(obs["street"], d.get("action") or "check",
                  int(d["amount"]) if d.get("amount") else None)
        decisions += 1
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": datetime.now().isoformat(timespec="seconds"),
                                "state": s, "obs": obs, "decision": d, "did": did}, ensure_ascii=False) + "\n")
        print(f"[{decisions}] {obs['street']:8s} {''.join(obs['hole']):5s} -> {did}")
        for _ in range(int(SETTLE_S * 10)):        # in Scheiben schlafen, damit ESC sofort greift
            if esc_pressed():
                break
            time.sleep(0.1)
    print(f"FERTIG: {decisions} Entscheidungen geloggt -> {log_path}")
    if forced:
        from collections import Counter
        print(f"UEBERSPRUNGEN: {forced} Haende (aus jeder Auswertung ausgeschlossen)")
        for reason, n in Counter(skipped_hands).most_common():
            print(f"   {n}x {reason}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hands", type=int, default=10)
    ap.add_argument("--bb", type=float, default=2.0, help="Big Blind in Dollar (Snowie-Tisch)")
    ap.add_argument("--probe", action="store_true", help="EINE Lesung, nichts klicken")
    ap.add_argument("--loose", action="store_true", help="bei unklarer Lesung warten statt abbrechen")
    args = ap.parse_args()
    run(args.hands, strict=not args.loose, bb_dollars=args.bb, probe=args.probe)


if __name__ == "__main__":
    main()
