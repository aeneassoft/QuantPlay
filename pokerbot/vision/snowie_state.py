"""VOLLSTÄNDIGER lokaler Tisch-Zustand für PokerSnowie 4 — keine API, kein Raten (User, 2026-08-03).

Ersetzt die VLM-Lesung der Brücke. Die zwei Fehler des ersten 32-Hand-Laufs waren BEIDE Folgen davon,
dass ein Sprachmodell strukturelle Fragen beantworten sollte:
  (1) 17 Gratis-Checks als Fold weggeworfen — das VLM meldete 'can_fold ja, can_check nein, can_call nein',
      ein logisch unmöglicher Zustand.  -> Hier wird NICHTS an Buttons abgelesen: aus den EINSÄTZEN folgt
      deterministisch, ob Check geht (kein Einsatz größer als meiner) und was ein Call kostet.
  (2) Position systematisch falsch (26/57 'SB') — das VLM lieferte eine Sitzreihenfolge, die nicht beim
      Dealer-Button begann.  -> Die Sitzreihenfolge ist durch das feste Layout BEKANNT (SEAT_ORDER,
      live verifiziert an zwei Händen); gesucht wird nur noch die weiße 'D'-Scheibe.

Alles Weitere ist Pixel-Arbeit mit derselben Technik wie die Karten (snowie_local): Ziffern per
Template-Matching, Sitz-Status per Helligkeit. Erkennungslücke -> None -> der Aufrufer PAUSIERT.

  python -m pokerbot.vision.snowie_state --read      # kompletter Zustand, lokal
  python -m pokerbot.vision.snowie_state --learn     # unbekannte Ziffern zum Labeln ablegen
"""
from __future__ import annotations

import argparse
import os

import numpy as np
from PIL import Image

from pokerbot.vision import snowie_local as SL

W, H = SL.W, SL.H

# Sitz-Boxen (native px, live vermessen) und die ACTION-Reihenfolge im Uhrzeigersinn des Spiels.
# Verifiziert an zwei Händen: D bei snowie2 -> hero=SB/snowie3=BB; D bei hero -> snowie3=SB/snowie4=BB.
SEAT_BOX = {
    "snowie5": (930, 430, 1160, 510), "snowie1": (1316, 430, 1546, 510),
    "snowie4": (574, 770, 810, 845),  "snowie2": (1670, 750, 1900, 824),
    "snowie3": (930, 1056, 1160, 1136), "hero": (1310, 1056, 1550, 1136),
}
SEAT_ORDER = ["snowie2", "hero", "snowie3", "snowie4", "snowie5", "snowie1"]
POS_AFTER_BTN = ["BTN", "SB", "BB", "UTG", "HJ", "CO"]

POT_BOX = (1178, 518, 1302, 562)              # die '$3'-Zeile unter 'TOTAL POT'
BAR_BOX = (600, 1235, 1270, 1320)             # die drei Aktions-Buttons (nur Anwesenheit zählt)
STACK_FRAC = (0.0, 0.45, 1.0, 1.0)            # untere Hälfte einer Sitz-Box = der Stack-Text
NAME_FRAC = (0.0, 0.0, 1.0, 0.45)
# Einsatz-Text je Sitz: liegt zwischen Sitz und Tischmitte (live vermessen, +-15px Toleranz durch Trim)
BET_BOX = {
    "hero": (1310, 895, 1520, 965), "snowie3": (960, 895, 1170, 965),
    "snowie4": (770, 715, 960, 785), "snowie2": (1540, 695, 1740, 765),
    "snowie5": (960, 555, 1170, 625), "snowie1": (1310, 555, 1520, 625),
}
DEALER_SEARCH = (560, 400, 1920, 1150)        # Suchbereich fuer die weisse 'D'-Scheibe
DEALER_MIN_WHITE = 0.55                       # Anteil sehr heller Pixel im Fundfenster
LIVE_MAX_BRIGHT = 200                         # aktiv = reinweisser Text (255); gefoldet nur ~160 (gemessen)


def _px(box):
    return (box[0] / W, box[1] / H, box[2] / W, box[3] / H)


def _sub(img, box):
    return SL.crop_frac(img, _px(box))


# ---------------------------------------------------------------- Ziffern
# POLARITAET: Karten sind dunkle Glyphen auf Weiss, die TISCH-ZAHLEN aber HELLE Schrift auf Dunkel
# (gemessen: der dunkel-Binarisierer fand in '$200' keine einzige Tintenspalte).
INK_BRIGHT = 165


def _ink(arr: np.ndarray, ratio: float = 0.70) -> np.ndarray:
    """ADAPTIV statt fester Schwelle: Snowie rendert aktive Sitze hell, gefoldete gedimmt — eine feste
    Schwelle fand bei gedimmten Sitzen NULL Tinte und liess '$200' zu einem Klumpen verschmelzen.
    Wir nehmen 70% zwischen Hintergrund (Median) und hellstem Pixel: trennt die Zeichen sauber."""
    if arr.size == 0:
        return np.zeros_like(arr, dtype=bool)
    lo, hi = float(np.median(arr)), float(arr.max())
    if hi - lo < 25:                      # kein Kontrast -> kein Text
        return np.zeros_like(arr, dtype=bool)
    return arr > (lo + ratio * (hi - lo))


def _binary_bright(img: Image.Image, size=(24, 30), ratio: float = 0.70) -> np.ndarray:
    """Helles Zeichen -> normiertes 0/1-Raster (auf die Tinte getrimmt, wie SL._binary, nur invertiert)."""
    g = np.asarray(img.convert("L"))
    ink = _ink(g, ratio)
    if not ink.any():
        return np.zeros(size[::-1], dtype=np.float32)
    ys, xs = np.where(ink)
    m = ink[ys.min():ys.max() + 1, xs.min():xs.max() + 1].astype(np.uint8) * 255
    r = np.asarray(Image.fromarray(m).resize(size, Image.BILINEAR))
    return (r > 127).astype(np.float32)


_DCACHE: dict[float, list[tuple[str, np.ndarray]]] = {}


def _digit_templates(ratio: float = 0.70):
    if ratio not in _DCACHE:
        d = os.path.join(SL.TPL_DIR, "digit")
        os.makedirs(d, exist_ok=True)
        _DCACHE[ratio] = [(os.path.splitext(f)[0],
                           _binary_bright(Image.open(os.path.join(d, f)), ratio=ratio))
                          for f in sorted(os.listdir(d)) if f.endswith(".png")]
    return _DCACHE[ratio]


def match_digit(img: Image.Image, ratio: float = 0.70) -> tuple[str | None, float]:
    b = _binary_bright(img, ratio=ratio)
    best, best_s = None, -1.0
    for label, tpl in _digit_templates(ratio):
        s = SL._score(b, tpl)
        if s > best_s:
            best, best_s = label, s
    return (best, best_s) if best_s >= SL.MATCH_MIN else (None, best_s)


MIN_SEG_W, MIN_INK_FRAC, MIN_SEG_H = 5, 0.12, 0.35
DOLLAR_W = 11      # Breite des Waehrungszeichens in diesem Font (live vermessen)


def _digit_boxes(arr: np.ndarray, ratio: float = 0.70) -> list[tuple[int, int]]:
    """Spalten mit Tinte -> zusammenhaengende Segmente = einzelne Zeichen.
    FILTER (2026-08-04): der erste Sammellauf lieferte 63 Kandidaten fuer 11 mogliche Zeichen — es
    rutschten Rahmenkanten und 1px-Splitter durch. Ein Zeichen muss BREIT genug, HOCH genug und
    dicht genug mit Tinte sein; alles andere ist Dekoration."""
    ink_mask = _ink(arr, ratio)
    ink = ink_mask.any(axis=0)
    out, start = [], None
    for i, v in enumerate(ink):
        if v and start is None:
            start = i
        elif not v and start is not None:
            if _ok_seg(ink_mask, start, i):
                out.append((start, i))
            start = None
    if start is not None and _ok_seg(ink_mask, start, len(ink)):
        out.append((start, len(ink)))
    return out


def _ok_seg(mask: np.ndarray, a: int, b: int) -> bool:
    if b - a < MIN_SEG_W:
        return False
    seg = mask[:, a:b]
    if seg.mean() < MIN_INK_FRAC:
        return False
    rows = seg.any(axis=1)
    return float(rows.sum()) / max(1, mask.shape[0]) >= MIN_SEG_H


def read_number(img: Image.Image, box, learn: bool = False) -> float | None:
    """'$199' -> 199.0. Probiert beide Tinten-Schwellen (Pot-Feld und Sitz-Box brauchen
    verschiedene) und nimmt das erste VOLLSTAENDIGE Ergebnis; sonst None (nie raten)."""
    for r in (0.70, 0.50, 0.60, 0.40, 0.80, 0.30):
        v = _read_number_at(img, box, learn, r)
        if v is not None:
            return v
    return None


def _read_number_at(img, box, learn, ratio) -> float | None:
    crop = _sub(img, box)
    g = np.asarray(crop.convert("L"))
    if _ink(g, ratio).sum() < 12:                             # praktisch keine Tinte -> kein Text
        return 0.0
    digits = ""
    boxes = _digit_boxes(g, ratio)
    for idx, (x0, x1) in enumerate(boxes):
        ch = crop.crop((x0, 0, x1, crop.height))
        label, score = match_digit(ch, ratio)
        if label is None and idx == 0:
            # Das '$' verschmilzt oft mit einer folgenden schmalen '1' zu EINEM Segment ('$1').
            # Das ganze Segment zu verwerfen kostete die fuehrende Ziffer (gemessen: 179 -> 79).
            # Also nur die Waehrungszeichen-Breite abschneiden und den Rest erneut lesen.
            w = x1 - x0
            for cut in list(range(6, 20)) + [w // 2]:
                if w - cut < 4:
                    continue
                rest = crop.crop((x0 + cut, 0, x1, crop.height))
                lab2, sc2 = match_digit(rest, ratio)
                if lab2 is not None:
                    label = lab2
                    break
            if label is None and len(boxes) > 1:
                continue                                   # reines '$' ohne Ziffer -> verwerfen
        if label is None:
            if learn:
                d = os.path.join(SL.DUMP_DIR, "digit")
                os.makedirs(d, exist_ok=True)
                ch.save(os.path.join(d, f"d_{abs(hash(ch.tobytes())) % 10**8}.png"))
            return None
        if label != "dollar":                          # das '$'-Zeichen wird gelernt, aber verworfen
            digits += "." if label == "dot" else label
    try:
        return float(digits) if digits else 0.0
    except ValueError:
        return None


# ---------------------------------------------------------------- Sitze / Dealer / Zug
def seat_live(img: Image.Image, seat: str) -> bool:
    """Aktiv (nicht gefoldet)? Gefoldete Sitze rendert Snowie deutlich dunkler/ausgegraut."""
    g = np.asarray(_sub(img, SEAT_BOX[seat]).convert("L"))
    return int(g.max()) >= LIVE_MAX_BRIGHT


def dealer_seat(img: Image.Image) -> str | None:
    """Die weisse 'D'-Scheibe suchen und dem NAECHSTEN Sitz zuordnen (Layout-unabhaengig)."""
    x0, y0, x1, y1 = DEALER_SEARCH
    g = np.asarray(_sub(img, DEALER_SEARCH).convert("L"))
    white = g > 225
    best, best_frac = None, 0.0
    step, win = 12, 44
    for yy in range(0, g.shape[0] - win, step):
        for xx in range(0, g.shape[1] - win, step):
            f = float(white[yy:yy + win, xx:xx + win].mean())
            if f > best_frac:
                best_frac, best = f, (x0 + xx + win // 2, y0 + yy + win // 2)
    if best is None or best_frac < DEALER_MIN_WHITE:
        return None
    cx, cy = best
    return min(SEAT_BOX, key=lambda s: (cx - (SEAT_BOX[s][0] + SEAT_BOX[s][2]) / 2) ** 2
               + (cy - (SEAT_BOX[s][1] + SEAT_BOX[s][3]) / 2) ** 2)


def hero_turn(img: Image.Image) -> bool:
    """Sind die Aktions-Buttons da? (Nur Anwesenheit — die LOGIK kommt aus den Einsaetzen.)"""
    g = np.asarray(_sub(img, BAR_BOX).convert("L"))
    return float((g > 110).mean()) > 0.06


def position_of(dealer: str) -> dict[str, str]:
    i = SEAT_ORDER.index(dealer)
    return {SEAT_ORDER[(i + k) % 6]: POS_AFTER_BTN[k] for k in range(6)}


# ---------------------------------------------------------------- Gesamt-Zustand
NUM_INSET = 14        # Innenabstand der Zahlen-Crops: Heros WEISSER Auswahlrahmen liegt am Boxrand und
                      # zog die adaptive Schwelle ueber die Text-Helligkeit -> Stack las sich als 'leer'.


def number_fields() -> dict[str, tuple]:
    """DIE eine Quelle fuer alle Zahlenfelder — read_state UND der Glyphen-Sammler lesen exakt
    dieselben Crops (die Doppelpflege mit verschiedenen Raendern war die Fehlerquelle #1)."""
    out = {"pot": POT_BOX}
    for s, b in SEAT_BOX.items():
        y_split = int(b[1] + (b[3] - b[1]) * STACK_FRAC[1])
        out[f"stack_{s}"] = (b[0] + NUM_INSET, y_split + 4, b[2] - NUM_INSET, b[3] - 6)
    for s, b in BET_BOX.items():
        out[f"bet_{s}"] = b
    return out


def read_state(img: Image.Image | None = None, learn: bool = False) -> dict:
    img = img or SL.grab()
    cards = SL.read_cards(img, learn=learn)
    d = dealer_seat(img)
    live = {s: seat_live(img, s) for s in SEAT_BOX}
    F = number_fields()
    bets = {s: read_number(img, F[f"bet_{s}"], learn) for s in SEAT_BOX}
    stacks = {s: read_number(img, F[f"stack_{s}"], learn) for s in SEAT_BOX}
    pot = read_number(img, F["pot"], learn)
    mine = bets.get("hero")
    live_bets = [v for s, v in bets.items() if live.get(s) and v is not None]
    mx = max(live_bets) if live_bets else 0.0
    return {
        "hero_turn": hero_turn(img), "hero_cards": cards["hero"], "board": cards["board"],
        "dealer": d, "positions": position_of(d) if d else {},
        "hero_position": position_of(d).get("hero") if d else None,
        "live": live, "bets": bets, "stacks": stacks, "pot": pot,
        "hero_bet": mine, "max_bet": mx,
        # DETERMINISTISCH aus den Einsaetzen — kein Button wird abgelesen:
        "can_check": (mine is not None and abs(mx - mine) < 1e-9),
        "call_amount": (None if mine is None else round(mx - mine, 2)),
        "players_in_hand": sum(1 for s, v in live.items() if v),
    }


def gate(s: dict) -> str | None:
    """None = brauchbar. Sonst der Grund zu PAUSIEREN (jede Luecke ist ein Grund)."""
    if not s["hero_turn"]:
        return "nicht am Zug"
    if len([c for c in s["hero_cards"] if c]) != 2:
        return f"Hole Cards unlesbar ({s['hero_cards']})"
    if s["hero_position"] is None:
        return "Dealer-Button nicht gefunden"
    if s["pot"] is None or s["hero_bet"] is None or s["stacks"].get("hero") is None:
        return "Zahl unlesbar (Pot/Einsatz/Stack)"
    if not s["pot"] or s["pot"] <= 0:
        return "Pot = 0 — bei laufender Hand unmoeglich (stiller Lesefehler)"
    if not s["stacks"].get("hero"):
        return "Hero-Stack = 0 — unplausibel"
    if s["players_in_hand"] < 2:
        return f"Spielerzahl unplausibel ({s['players_in_hand']})"
    # Die Unmoeglichkeit aus Lauf 1 kann hier strukturell nicht mehr auftreten, wird aber geprueft:
    if not s["can_check"] and (s["call_amount"] or 0) <= 0:
        return "Widerspruch: kein Check moeglich, aber nichts zu callen"
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--learn", action="store_true")
    ap.parse_args()
    import json
    s = read_state(learn=True)
    print(json.dumps({k: v for k, v in s.items() if k != "live"}, indent=1, ensure_ascii=False))
    print("live:", s["live"])
    print("GATTER:", gate(s) or "OK")


if __name__ == "__main__":
    main()
