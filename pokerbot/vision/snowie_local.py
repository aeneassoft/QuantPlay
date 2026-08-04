"""LOKALE Bilderkennung für PokerSnowie 4 — ohne API, ohne Kosten (User-Vorgabe 2026-08-03).

WARUM: ein VLM-Call pro Entscheidung wäre bei ~4 Calls/Hand und Tausenden Händen sowohl teuer als auch
langsam. PokerSnowie rendert seine Sprites PIXEL-IDENTISCH (Qt, feste Layout-Geometrie) — damit ist
Template-Matching exakt richtig: einmal gelernt, danach gratis und in Millisekunden.

ARCHITEKTUR
  * REGIONS: alle Elemente als BRUCHTEILE des Fensters (überlebt Fenstergrößen, live vermessen).
  * Templates liegen als PNG unter data/vision/snowie/tpl/<art>/<label>.png. Gematcht wird über die
    normalisierte Kreuzkorrelation auf binarisierten Crops (numpy, kein OpenCV nötig).
  * `--learn` legt JEDEN unbekannten Glyph als PNG ab -> per Auge labeln -> ab dann erkannt.
    Der Deck-Aufbau ist damit eine EINMALIGE Investition, kein laufender Posten.
  * Unsicher (bester Score unter MATCH_MIN) -> None. Der Aufrufer PAUSIERT dann (nie raten).

  python -m pokerbot.vision.snowie_local --dump     # Crops als Montage zum Vermessen/Labeln
  python -m pokerbot.vision.snowie_local --read     # aktueller Tischzustand, rein lokal
"""
from __future__ import annotations

import argparse
import ctypes
import os

import numpy as np
from PIL import Image, ImageGrab

ctypes.windll.user32.SetProcessDPIAware()          # sonst logische statt physischer Pixel (hier 175%)

from pokerbot.vision.screen_reader import pick_window          # noqa: E402

TPL_DIR = os.path.join("data", "vision", "snowie", "tpl")
DUMP_DIR = os.path.join("data", "vision", "snowie", "dump")
MATCH_MIN = 0.72          # darunter gilt ein Glyph als UNERKANNT (lieber pausieren als raten)
MATCH_MARGIN = 0.05       # das beste Label muss das zweitbeste FREMDE Label klar schlagen. Gemessen
                          # (2026-08-04): Nachbar-Raenge scoren bis 0.79 GEGENEINANDER (5-6: 0.790,
                          # A-4: 0.758, 8-6: 0.753, J-3: 0.743, 7-2: 0.740) — alle UEBER der Schwelle.
                          # Folge war eine systematisch verbogene Rangverteilung in 890 Karten
                          # (3: 4x statt ~68, 2: 131x): der Bot spielte GERATENE Haende ('34o
                          # geraised', User-Fund). Zweideutig heisst ab jetzt: unlesbar.
BIN_THRESH = 140          # Graustufen-Schwelle: Sprites sind dunkle Glyphen auf Weiß

# --- live vermessene Geometrie (Fenster 1953x1442, PokerSnowie 4 Cash-Training) -------------------
# Board: 5 Slots, Breite 97, Abstand 101, oben y=700
_BOARD_X0, _BOARD_W, _BOARD_DX, _BOARD_Y0, _BOARD_H = 988, 97, 101, 700, 138
# Hero: zwei kleinere Karten unten rechts
_HERO = [(1360, 975, 68, 80), (1435, 975, 68, 80)]
W, H = 1953.0, 1442.0


def _frac(x, y, w, h):
    return (x / W, y / H, (x + w) / W, (y + h) / H)


REGIONS = {
    **{f"board{i}": _frac(_BOARD_X0 + _BOARD_DX * i, _BOARD_Y0, _BOARD_W, _BOARD_H) for i in range(5)},
    **{f"hero{i}": _frac(*_HERO[i]) for i in range(2)},
}
# Innerhalb einer Karte: wo sitzen Rang- und Farb-Glyph? (Board-Karten: Rang links, Farbe rechts oben;
# Hero-Karten: Rang oben, Farbe darunter — daher zwei Sätze.)
GLYPH_BOARD = {"rank": (0.03, 0.03, 0.44, 0.36), "suit": (0.45, 0.04, 0.95, 0.34)}
GLYPH_HERO = {"rank": (0.05, 0.03, 0.92, 0.50), "suit": (0.10, 0.48, 0.85, 0.98)}


def window_bbox():
    w = pick_window("PokerSnowie")
    if not w:
        raise RuntimeError("PokerSnowie-Fenster nicht gefunden")
    return w["bbox"]


def grab():
    return ImageGrab.grab(bbox=window_bbox(), all_screens=True)


def crop_frac(img: Image.Image, box) -> Image.Image:
    x0, y0, x1, y1 = box
    return img.crop((int(x0 * img.width), int(y0 * img.height),
                     int(x1 * img.width), int(y1 * img.height)))


def _card_ink(g: np.ndarray) -> np.ndarray:
    """ADAPTIV statt fester Schwelle (4-Farben-Deck, 2026-08-04): gruene Tinte misst ~148 Grauwert und
    fiel durch die feste 140er-Schwelle. Das PAPIER ist immer das Hellste -> Schwelle relativ dazu,
    damit jede Tintenfarbe (schwarz/rot/blau/gruen) gleich sicher erkannt wird."""
    paper = float(np.percentile(g, 90))
    return g < max(60.0, 0.78 * paper)


def _binary(img: Image.Image, size=(28, 34)) -> np.ndarray:
    """Glyph -> normiertes 0/1-Raster. Trimmt zuerst auf die Tinte (macht das Matching lage-robust)."""
    g = np.asarray(img.convert("L"))
    ink = _card_ink(g)
    if not ink.any():
        return np.zeros(size[::-1], dtype=np.float32)
    ys, xs = np.where(ink)
    g = g[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    small = np.asarray(Image.fromarray(g).resize(size, Image.BILINEAR))
    return _card_ink(small).astype(np.float32)


def _score(a: np.ndarray, b: np.ndarray) -> float:
    """Normalisierte Kreuzkorrelation zweier 0/1-Raster (1.0 = identisch)."""
    if a.std() < 1e-6 or b.std() < 1e-6:
        return 0.0
    return float(((a - a.mean()) * (b - b.mean())).mean() / (a.std() * b.std()))


_CACHE: dict[str, list[tuple[str, np.ndarray]]] = {}


def templates(kind: str):
    if kind not in _CACHE:
        d = os.path.join(TPL_DIR, kind)
        os.makedirs(d, exist_ok=True)
        _CACHE[kind] = [(os.path.splitext(f)[0].split("_")[0], _binary(Image.open(os.path.join(d, f))))
                        for f in sorted(os.listdir(d)) if f.endswith(".png")]
    return _CACHE[kind]


def match(glyph: Image.Image, kind: str) -> tuple[str | None, float]:
    b = _binary(glyph)
    best, best_s, second = None, -1.0, -1.0
    for label, tpl in templates(kind):
        s = _score(b, tpl)
        if s > best_s:
            if label != best:
                second = best_s               # bisheriger Sieger wird zweitbestes FREMDES Label
            best, best_s = label, s
        elif label != best and s > second:
            second = s
    if best_s < MATCH_MIN or best_s - second < MATCH_MARGIN:
        return None, best_s                   # zweideutig -> unlesbar -> Gatter statt geratener Hand
    return best, best_s


# FARBE als Schluessel (User-Idee 2026-08-04): bei einem 4-FARBEN-Deck ist die Farbe EINDEUTIG
# (Pik schwarz / Herz rot / Karo blau / Kreuz gruen) -> kein Formvergleich noetig, praktisch fehlerfrei.
# Beim 2-Farben-Deck halbiert sie immerhin den Suchraum (rot: h/d, schwarz: s/c). Ein verwechseltes
# Herz/Karo waere der teuerste Lesefehler ueberhaupt (erfundener Flush-Draw).
# Vom User bestaetigtes 4-Farben-Schema (2026-08-04) + live gemessene Farbtoene:
#   Herz ROT (gemessen 3 Grad) · Kreuz GRUEN (138) · Karo BLAU · Pik SCHWARZ (entsaettigt)
# Damit ist die Farbe fuer JEDE Karte eindeutig -> Formvergleich fuer Farben entfaellt komplett.
FOUR_COLOR = True
SUIT_BY_HUE = {"h": (0, 25), "d": (185, 260), "c": (80, 170), "s": None}    # HSV-Hue-Fenster in Grad


def suit_by_colour(glyph: Image.Image) -> list[str]:
    """Kandidaten-Farben nach Pixelfarbe. Leere Liste = keine Aussage (dann entscheidet die Form)."""
    import colorsys
    a = np.asarray(glyph.convert("RGB")).reshape(-1, 3) / 255.0
    lum = a.sum(axis=1)
    dark = lum < max(0.9, 0.78 * float(np.percentile(lum, 90)))                      # nur die Glyphen-Pixel, nicht das weisse Papier
    if dark.sum() < 8:
        return []
    r, g, b = a[dark].mean(axis=0)
    h, sat, v = colorsys.rgb_to_hsv(r, g, b)
    if sat < 0.25:                                  # entsaettigt = schwarz
        return ["s"] if FOUR_COLOR else ["s", "c"]   # 4-Farben: schwarz ist EINDEUTIG Pik
    deg = h * 360.0
    out = [k for k, win in SUIT_BY_HUE.items() if win and (win[0] <= deg <= win[1])]
    return out or []


def read_card(img: Image.Image, key: str, learn: bool = False):
    """Eine Kartenposition -> 'As' | None (leer/unerkannt). Board- und Hero-Karten haben andere Layouts."""
    card = crop_frac(img, REGIONS[key])
    g = np.asarray(card.convert("L"))
    if (g > 200).mean() < 0.25:                   # kaum Weiß -> leerer Slot / verdeckte Karte
        return None
    # GETRENNTE Bibliotheken (User-Hypothese 2026-08-04, bestaetigt): Hero-Karten (68px) und
    # Board-Karten (97px) rendern denselben Rang sichtbar anders (Fontgewicht/Antialiasing) —
    # eine gemischte Bibliothek matcht beide schlechter als zwei sortenreine.
    hero_card = key.startswith("hero")
    layout = GLYPH_HERO if hero_card else GLYPH_BOARD
    out = {}
    for part, box in layout.items():
        x0, y0, x1, y1 = box
        sub = card.crop((int(x0 * card.width), int(y0 * card.height),
                         int(x1 * card.width), int(y1 * card.height)))
        kind = (part + ("_h" if hero_card else "_b")) if part == "rank" else part
        label, score = match(sub, kind)
        if part == "suit":
            cand = suit_by_colour(sub)
            if len(cand) == 1:                      # 4-Farben-Deck: Farbe entscheidet allein
                label = cand[0]
            elif cand and label not in cand:        # 2-Farben-Deck: Form darf der Farbe nicht widersprechen
                label = None
        if label is None and learn:
            os.makedirs(os.path.join(DUMP_DIR, kind), exist_ok=True)
            sub.save(os.path.join(DUMP_DIR, kind, f"{key}_{abs(hash(sub.tobytes())) % 10**8}.png"))
        out[part] = label
    if not out.get("rank") or not out.get("suit"):
        return None
    return f"{out['rank']}{out['suit']}"


def slot_occupied(img: Image.Image, key: str) -> bool:
    """Liegt an dieser Position UEBERHAUPT eine offene Karte? (weisses Papier = ja)"""
    g = np.asarray(crop_frac(img, REGIONS[key]).convert("L"))
    return bool((g > 200).mean() >= 0.25)


def read_cards(img: Image.Image | None = None, learn: bool = False) -> dict:
    img = img or grab()
    board = [read_card(img, f"board{i}", learn) for i in range(5)]
    hero = [read_card(img, f"hero{i}", learn) for i in range(2)]
    unread = sum(1 for i in range(5) if board[i] is None and slot_occupied(img, f"board{i}"))
    unread += sum(1 for i in range(2) if hero[i] is None and slot_occupied(img, f"hero{i}"))
    return {"board": [c for c in board if c], "board_raw": board, "hero": hero,
            "unreadable": unread}


def dump(img: Image.Image | None = None) -> str:
    """Alle Kartenpositionen + ihre Glyph-Ausschnitte als EINE Montage — zum Vermessen und Labeln."""
    img = img or grab()
    os.makedirs(DUMP_DIR, exist_ok=True)
    keys = [f"board{i}" for i in range(5)] + [f"hero{i}" for i in range(2)]
    cards = [crop_frac(img, REGIONS[k]) for k in keys]
    cw, ch = max(c.width for c in cards), max(c.height for c in cards)
    sheet = Image.new("RGB", (cw * len(cards), ch * 3 + 20), "white")
    for i, (k, c) in enumerate(zip(keys, cards)):
        sheet.paste(c, (i * cw, 0))
        layout = GLYPH_HERO if k.startswith("hero") else GLYPH_BOARD
        for j, part in enumerate(("rank", "suit")):
            x0, y0, x1, y1 = layout[part]
            sub = c.crop((int(x0 * c.width), int(y0 * c.height), int(x1 * c.width), int(y1 * c.height)))
            sheet.paste(sub.resize((min(cw, sub.width * 2), min(ch, sub.height * 2))), (i * cw, ch * (j + 1) + 10))
    path = os.path.join(DUMP_DIR, "montage.png")
    sheet.save(path)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", action="store_true")
    ap.add_argument("--read", action="store_true")
    ap.add_argument("--learn", action="store_true", help="unerkannte Glyphen zum Labeln ablegen")
    a = ap.parse_args()
    if a.dump:
        print("Montage ->", dump())
        return
    r = read_cards(learn=a.learn)
    print("BOARD:", r["board"], " HERO:", r["hero"])


if __name__ == "__main__":
    main()
