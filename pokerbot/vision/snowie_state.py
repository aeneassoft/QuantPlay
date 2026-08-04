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
from PIL import Image, ImageOps

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
    # POLARITAET automatisch (Bright Mode 2026-08-04): aktive Sitzboxen sind jetzt WEISS mit
    # dunkler Schrift — liegt der Median naeher am Maximum als am Minimum, ist die Tinte DUNKEL
    # und wir arbeiten auf dem Negativ. Dunkelmodus-Felder bleiben unveraendert (Regression 3x).
    med = float(np.median(arr))
    if med - float(arr.min()) > float(arr.max()) - med:
        arr = 255 - arr
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
        _DCACHE[ratio] = [(os.path.splitext(f)[0].split("_")[0],
                           _binary_bright(Image.open(os.path.join(d, f)), ratio=ratio))
                          for f in sorted(os.listdir(d)) if f.endswith(".png")]
    return _DCACHE[ratio]


NARROW_W, NARROW_MIN = 15, 0.55     # ein SCHMALES Segment kann nur EINE Ziffer sein


def match_digit(img: Image.Image, ratio: float = 0.70) -> tuple[str | None, float]:
    """Breitenabhaengige Schwelle: gemessen liegen korrekte Treffer bei 0.72-1.0, falsche bei
    0.15-0.45, und VERSCHMOLZENE Doppelziffern bei 0.45-0.60 — die sind aber immer BREIT.
    Bei schmalen Segmenten ist eine Verwechslung daher unmoeglich-genug, um milder zu werten;
    breite Segmente muessen weiter durch die strenge Schwelle (bzw. die Trennung)."""
    b = _binary_bright(img, ratio=ratio)
    best, best_s, second = None, -1.0, -1.0
    for label, tpl in _digit_templates(ratio):
        s = SL._score(b, tpl)
        if s > best_s:
            if label != best:
                second = best_s
            best, best_s = label, s
        elif label != best and s > second:
            second = s
    # Margin wie beim Rang-Matcher: zweideutig -> unlesbar. Ohne sie wurde ein 10px-Fragment des
    # Pots '$13' ueber die Schmal-Milde als '8' akzeptiert (Bright-Mode-Fund) und das Gatter
    # bekam einen falschen, aber plausiblen Pot praesentiert.
    if best_s < SL.MATCH_MIN or best_s - second < SL.MATCH_MARGIN:
        return None, best_s
    return best, best_s


MIN_SEG_W, MIN_INK_FRAC, MIN_SEG_H = 5, 0.12, 0.35
DOLLAR_W = 11      # Breite des Waehrungszeichens in diesem Font (live vermessen)


COL_INK_MIN = 0.05        # so viel einer Spalte muss Tinte sein, damit sie zu einem Zeichen zaehlt


def _digit_boxes(arr: np.ndarray, ratio: float = 0.70) -> list[tuple[int, int]]:
    """Spalten mit Tinte -> zusammenhaengende Segmente = einzelne Zeichen.
    FILTER (2026-08-04): der erste Sammellauf lieferte 63 Kandidaten fuer 11 mogliche Zeichen — es
    rutschten Rahmenkanten und 1px-Splitter durch. Ein Zeichen muss BREIT genug, HOCH genug und
    dicht genug mit Tinte sein; alles andere ist Dekoration."""
    ink_mask = _ink(arr, ratio)
    # ANTEIL statt any() (2026-08-04): mit any() gilt eine Spalte schon bei EINEM Tintenpixel als
    # belegt -> Rauschen fuellt die Luecken zwischen den Zeichen, das Segment wird unfoermig und
    # faellt durch _ok_seg. Gemessener Fall: Pot "$239" ergab statt vier Zeichen ein 10px-Bruchstueck.
    ink = ink_mask.mean(axis=0) > COL_INK_MIN
    out, start = [], None
    for i, v in enumerate(ink):
        if v and start is None:
            start = i
        elif not v and start is not None:
            if _ok_seg(ink_mask, start, i) or _is_dot(ink_mask, start, i):
                out.append((start, i))
            start = None
    if start is not None and _ok_seg(ink_mask, start, len(ink)):
        out.append((start, len(ink)))
    return out


def _is_dot(mask: np.ndarray, a: int, b: int) -> bool:
    """DEZIMALPUNKT: 2-4px schmal, Tinte NUR im unteren Drittel. Der Mindestbreite-Filter warf ihn
    weg — aus '337.5' wurde '3375', das Gatter blockierte jeden Dezimalstack (Befund run_v9)."""
    if not (2 <= b - a < MIN_SEG_W):
        return False
    seg = mask[:, a:b]
    rows = np.where(seg.any(axis=1))[0]
    return rows.size > 0 and rows.min() >= int(mask.shape[0] * 0.55)


def _ok_seg(mask: np.ndarray, a: int, b: int) -> bool:
    if b - a < MIN_SEG_W:
        return False
    seg = mask[:, a:b]
    if seg.mean() < MIN_INK_FRAC:
        return False
    rows = seg.any(axis=1)
    return float(rows.sum()) / max(1, mask.shape[0]) >= MIN_SEG_H


TESS_EXE = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
OCR_SCALE = 3                 # Hochskalieren: Tesseract braucht deutlich groessere Glyphen als 17px
OCR_CFG = "--psm 7 -c tessedit_char_whitelist=0123456789.$"
_TESS = None                  # None = noch nicht geprueft, False = nicht verfuegbar


def _tesseract():
    """Tesseract einmalig anbinden. False, wenn nicht installiert — dann greifen die Templates."""
    global _TESS
    if _TESS is None:
        try:
            import pytesseract
            pytesseract.pytesseract.tesseract_cmd = TESS_EXE
            pytesseract.get_tesseract_version()
            _TESS = pytesseract
        except Exception:  # noqa: BLE001 — fehlendes OCR ist kein Fehler, nur ein Verzicht
            _TESS = False
    return _TESS


def _ocr_number(img: Image.Image, box) -> float | None:
    """Zahl per OCR lesen. None = nichts Verwertbares (dann entscheidet der Aufrufer weiter).

    Die Tischzahlen sind HELL auf DUNKEL, Tesseract erwartet das Gegenteil -> invertieren. Ohne
    Hochskalieren liefert es bei 17px-Ziffern nichts. Der Weissliste-Filter haelt Waehrungszeichen
    und Buchstaben heraus, die sonst als Ziffern halluziniert werden.
    """
    tess = _tesseract()
    if not tess:
        return None
    try:
        crop = _sub(img, box).convert("L")
        crop = ImageOps.invert(crop).resize((crop.width * OCR_SCALE, crop.height * OCR_SCALE),
                                            Image.LANCZOS)
        # "$" MUSS in der Weissliste stehen: fehlt es, presst Tesseract das Zeichen in eine
        # Ziffer (gemessen: Pot "$4" -> "34"). Erlauben und danach abschneiden.
        txt = tess.image_to_string(crop, config=OCR_CFG).strip().lstrip("$").strip(".")
        v = float(txt) if txt and txt.replace(".", "", 1).isdigit() else None
        # verliert die OCR den Dezimalpunkt, entsteht das Zehnfache — jenseits der Tischgrenze
        # ist es sicher ein Lesefehler (gemessen: 337.5 -> 3375)
        return None if v is not None and v > OCR_MAX_CHIPS else v
    except Exception:  # noqa: BLE001 — OCR darf den Lauf nie stoppen
        return None


def read_number(img: Image.Image, box, learn: bool = False) -> float | None:
    """'$199' -> 199.0. Probiert beide Tinten-Schwellen (Pot-Feld und Sitz-Box brauchen
    verschiedene) und nimmt das erste VOLLSTAENDIGE Ergebnis; sonst None (nie raten)."""
    # TEMPLATES ZUERST, OCR als Rueckfall — aber im KONSENS ueber die Schwellen, nicht erstbestes:
    # bei 0.70 zerbrach '$13' zu einem 8px-Fragment ('8'), waehrend 0.40 sauber '13' las; die alte
    # Erstbestes-Regel gab die 8 zurueck. Jetzt gewinnt der Wert, den die meisten Schwellen sehen;
    # bei Gleichstand der mit den meisten gelesenen Zeichen (laengerer Text schlaegt Fragment).
    votes: dict[float, int] = {}
    for r in (0.70, 0.50, 0.60, 0.40, 0.80, 0.30):
        v = _read_number_at(img, box, learn, r)
        if v is not None:
            votes[v] = votes.get(v, 0) + 1
    if votes:
        return max(votes.items(), key=lambda kv: (kv[1], len(f"{kv[0]:g}")))[0]
    return _ocr_number(img, box)


WIDE_SEG = 16          # breiter als eine Einzelziffer -> Verdacht auf verschmolzene Zeichen


def _split_wide(crop, g, x0, x1, ratio):
    """Zwei verschmolzene Ziffern ('24' als EIN Segment) an der tintenaermsten Spalte trennen.
    Gemessen: der Pot lieferte ein 21px-Segment, das gegen jedes Einzelziffern-Template scheiterte."""
    seg = _ink(g[:, x0:x1], ratio)
    if x1 - x0 < WIDE_SEG or seg.size == 0:
        return None
    # ALLE plausiblen Trennstellen probieren, nach Tintenarmut sortiert (die wahrscheinlichste zuerst),
    # und die erste nehmen, bei der BEIDE Haelften erkannt werden. Eine einzige geratene Schnittstelle
    # traf oft daneben (gemessen: 17px-Segment, Minimum-Spalte lieferte zwei unerkannte Haelften).
    cols = seg.sum(axis=0)
    w = x1 - x0
    lo, hi = max(4, w // 4), min(w - 4, 3 * w // 4)
    if hi <= lo:
        return None
    for off in sorted(range(lo, hi), key=lambda i: cols[i]):
        cut = x0 + off
        parts = []
        for a, b in ((x0, cut), (cut, x1)):
            lab, _ = match_digit(crop.crop((a, 0, b, crop.height)), ratio)
            if lab is None or lab == "dollar":
                parts = []
                break
            parts.append(lab)
        if parts:
            return "".join(parts)
    return None


LINE_INK_MIN = 0.02        # Zeilen-Tinte: so viel einer Bildzeile muss hell sein, damit dort Text steht
LINE_MIN_H = 5             # duennere "Zeilen" sind Rahmenkanten, kein Text


def _text_lines(g: np.ndarray) -> list[tuple[int, int]]:
    """Waagerechte Textzeilen eines Ausschnitts als (oben, unten)-Paare."""
    med = float(np.median(g))
    lit = (np.abs(g.astype(np.int16) - med) > 60).mean(axis=1) > LINE_INK_MIN
    out, start = [], None
    for y, v in enumerate(lit):
        if v and start is None:
            start = y
        elif not v and start is not None:
            if y - start >= LINE_MIN_H:
                out.append((start, y))
            start = None
    if start is not None and len(lit) - start >= LINE_MIN_H:
        out.append((start, len(lit)))
    return out


def read_button_amount(img: Image.Image, box, learn: bool = False,
                       batch_val: float | None = None) -> float | None:
    """Betrag auf einem Aktions-Button. 0.0 = Button ohne Betrag (reines Wort).

    Ein Aktions-Button traegt sein Wort ueber dem Betrag ('CALL' / '$95'). Spaltenweise ueber BEIDE
    Zeilen gelesen verschmieren die Buchstaben mit den Ziffern und nichts wird erkannt (gemessener
    Fall: CALL $95 -> None -> das Gatter blockierte, obwohl der Betrag gross dastand). Also erst die
    Zeilen trennen, dann NUR die untere lesen. Der Innenabstand schneidet den gelben Auswahlrahmen
    weg, der sonst jede Bildzeile mit Tinte fuellt und die Trennung unmoeglich macht.
    """
    n = NUM_INSET
    inner = (box[0] + n, box[1] + n, box[2] - n, box[3] - n)
    lines = _text_lines(np.asarray(_sub(img, inner).convert("L")))
    if not lines:
        return None                                     # leerer Button (Layout ohne diese Aktion)
    if len(lines) == 1:
        return 0.0                                      # nur ein Wort ('CHECK') -> kein Betrag
    top, bot = lines[-1]
    val = batch_val if batch_val is not None else         read_number(img, (inner[0], inner[1] + top, inner[2], inner[1] + bot), learn)
    if val is None:
        _dump_unknown_amount(_sub(img, (inner[0], inner[1] + top, inner[2], inner[1] + bot)))
    return val


def _dump_unknown_amount(line: Image.Image) -> None:
    """Unlesbare Betragszeile ablegen, damit die fehlende Ziffer NACHTRAEGLICH gelabelt werden kann.

    Button-Ziffern sind eine eigene Groessenklasse (fetter als die Tischzahlen) und matchen nicht
    gegen deren Vorlagen. Ohne diese Ablage kostet jede noch unbekannte Ziffer eine eigene
    Haenger-Runde; so sammeln sie sich waehrend des Laufs von selbst an.
    """
    try:
        d = os.path.join(SL.DUMP_DIR, "btn_amount")
        os.makedirs(d, exist_ok=True)
        if len(os.listdir(d)) < DUMP_CAP:
            line.save(os.path.join(d, f"amt_{len(os.listdir(d)):03d}.png"))
    except Exception:  # noqa: BLE001 — Diagnose darf den Lauf nie stoppen
        pass


DUMP_CAP = 60         # genug Belege zum Labeln, ohne die Platte zuzumuellen


def _read_number_at(img, box, learn, ratio) -> float | None:
    crop = _sub(img, box)
    g = np.asarray(crop.convert("L"))
    if _ink(g, ratio).sum() < 12:                             # praktisch keine Tinte -> kein Text
        return 0.0
    digits = ""
    boxes = _digit_boxes(g, ratio)
    for idx, (x0, x1) in enumerate(boxes):
        if x1 - x0 < MIN_SEG_W:                        # nur _is_dot laesst so schmale Segmente durch
            digits += "."
            continue
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
        if label is None:                              # letzter Versuch: verschmolzene Doppelziffer
            merged = _split_wide(crop, g, x0, x1, ratio)
            if merged:
                digits += merged
                continue
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
LIVE_WHITE_BOX = 200      # Bright Mode: aktive Box ist reinweiss (median 255), gefoldete grau (123)
GREY_BAND = (100, 160)    # das Grau gefoldeter Boxen — in KEINEM Modus ist ein aktiver Sitz so mittig


def seat_live(img: Image.Image, seat: str) -> bool:
    """Aktiv (nicht gefoldet)? Beide Themes (gemessen 2026-08-04):
    dunkel: aktiv = reinweisser Text (max 255), gefoldet nur ~160 -> max-Schwelle.
    bright: gefoldet = GRAUE Box (median 123, max bis 234!) -> die max-Schwelle allein luegt;
    aktiv ist entweder die weisse Box (median>=200) oder Heros dunkle Box mit hellem Text."""
    g = np.asarray(_sub(img, SEAT_BOX[seat]).convert("L"))
    med = float(np.median(g))
    if GREY_BAND[0] <= med <= GREY_BAND[1]:
        return False
    return med >= LIVE_WHITE_BOX or int(g.max()) >= LIVE_MAX_BRIGHT


# Die D-Scheibe ist ein GEFUELLTER weisser Kreis (~40px) mit dunklem 'D' darin. Ein Kreis fuellt
# sein Quadratfenster zu hoechstens pi/4 ~ 0.785 — reinweisse Flaechen (Boardkarten!) liegen DARUEBER,
# duenne weisse Raender (Heros Zug-Markierung) und Textzeilen weit DARUNTER. Das Band + der dunkle
# Kern trennen die Scheibe von allem anderen Weiss am Tisch.
SEAT_EXCL_PAD = 24        # gerenderte Bright-Box ragt ueber das Sitz-Rechteck hinaus
DISC_WIN = 44
DISC_WHITE = (0.36, 0.86)         # Kreis-Band; Untergrenze 0.36: JPEG-Aufnahmen (q70) weichen das
                                  # Reinweiss der Scheibe auf 0.41 auf (live-PNG ~0.50). Gefahrlos,
                                  # weil bei >248 nur Scheibe/Boxen/Karten weiss sind - letztere gesperrt.
DISC_DARK = (0.02, 0.48)          # 'D' + dunkler Tischrand ums Rund (gemessen 0.357 an der echten Scheibe)
BOARD_RECT = (960, 680, 1510, 850)      # Boardkarten: weiss + dunkle Glyphen = falsche Kandidaten
HERO_CARDS_RECT = (1330, 955, 1530, 1065)  # Heros offene Karten: dieselbe Falle


def dealer_seat(img: Image.Image) -> str | None:
    """Die weisse 'D'-Scheibe suchen und dem NAECHSTEN Sitz zuordnen.

    WARUM nicht mehr "weissestes Fenster" (Befund 2026-08-04): Boardkarten sind WEISSER als die
    Scheibe, und Heros Zug-Markierung ist weiss — der alte Detektor fand daher postflop das Board
    (-> Position des naechstgelegenen Sitzes) und preflop Hero (-> immer "BTN"). Der Positions-Log
    zeigte BTN in 20 von 22 Entscheidungen; JEDE davon rechnete mit erfundener Position.
    """
    x0, y0, _, _ = DEALER_SEARCH
    g = np.asarray(_sub(img, DEALER_SEARCH).convert("L"))
    # 248 statt 225 (Bright Mode): der helle App-Hintergrund (234) zaehlte sonst als "weiss" und
    # die Suche ertrank in Weissflaechen. Die echte Scheibe ist reinweiss (255) in BEIDEN Themes.
    white = (g > 248).astype(np.float32)
    dark = (g < 120).astype(np.float32)
    # Integralbilder: alle Fenstermittel in einem Rutsch statt Python-Doppelschleife
    def _win_mean(m):
        c = np.cumsum(np.cumsum(m, 0), 1)
        c = np.pad(c, ((1, 0), (1, 0)))
        w = DISC_WIN
        return (c[w:, w:] - c[:-w, w:] - c[w:, :-w] + c[:-w, :-w]) / float(w * w)
    wf, df = _win_mean(white), _win_mean(dark)
    ok = (wf >= DISC_WHITE[0]) & (wf <= DISC_WHITE[1]) & (df >= DISC_DARK[0]) & (df <= DISC_DARK[1])
    best, best_frac = None, 0.0
    ys, xs = np.where(ok)
    for yy, xx in zip(ys.tolist(), xs.tolist()):
        cx, cy = x0 + xx + DISC_WIN // 2, y0 + yy + DISC_WIN // 2
        if BOARD_RECT[0] <= cx <= BOARD_RECT[2] and BOARD_RECT[1] <= cy <= BOARD_RECT[3]:
            continue
        if HERO_CARDS_RECT[0] <= cx <= HERO_CARDS_RECT[2] and HERO_CARDS_RECT[1] <= cy <= HERO_CARDS_RECT[3]:
            continue
        # Bright Mode: aktive Sitzboxen sind WEISS mit dunkler Schrift = scheibenartig — und die
        # GERENDERTE Box ist GROESSER als unser Rechteck: Kandidaten auf dem ueberstehenden weissen
        # Rand schlugen die echte Scheibe im Weiss-Anteil (Frame-Beweis run_v16 [1]: D bei snowie2,
        # gefunden snowie3 -> Hero 'CO' statt SB). Darum gepolsterte Sperrzone; die Scheibe selbst
        # liegt >=30px neben jeder Box und ueberlebt das Polster.
        if any(b[0] - SEAT_EXCL_PAD <= cx <= b[2] + SEAT_EXCL_PAD
               and b[1] - SEAT_EXCL_PAD <= cy <= b[3] + SEAT_EXCL_PAD for b in SEAT_BOX.values()):
            continue
        if float(wf[yy, xx]) > best_frac:
            best_frac, best = float(wf[yy, xx]), (cx, cy)
    if best is None:
        return None
    cx, cy = best
    return min(SEAT_BOX, key=lambda s: (cx - (SEAT_BOX[s][0] + SEAT_BOX[s][2]) / 2) ** 2
               + (cy - (SEAT_BOX[s][1] + SEAT_BOX[s][3]) / 2) ** 2)


def hero_turn(img: Image.Image) -> bool:
    """Sind die Aktions-Buttons da? (Nur Anwesenheit — die LOGIK kommt aus den Einsaetzen.)

    NICHT ueber die Gesamttinte der Leiste (Fund 2026-08-04): ist der Gegner All-in, blendet Snowie
    den RAISE-Button aus; ein Drittel weniger Tinte drueckte die Leiste auf 0.0576 gegen die Schwelle
    0.06 -> hero_turn=False, obwohl FOLD und CALL leuchteten. Die Hand wartete auf uns, wir auf sie:
    Deadlock am River, wo All-ins sich haeufen. FOLD und CHECK/CALL gibt es dagegen IMMER, wenn wir
    am Zug sind — also zaehlen wir diese beiden Felder EINZELN.
    """
    g = np.asarray(img.convert("L"))
    def _lit(box: tuple[int, int, int, int]) -> bool:
        # STREUUNG statt Tintenanteil (Bright Mode): die orangen Buttons (median 146) UND die leere
        # helle Flaeche (median 234) liegen beide ueber jeder festen Helligkeitsschwelle — aber nur
        # ein Button mit Text streut (std 20-24 vs 0 leer; dunkler Modus: 40+ vs ~3).
        return float(g[box[1]:box[3], box[0]:box[2]].std()) >= BTN_STD_MIN
    return _lit(BTN_FOLD_BOX) and _lit(BTN_MID_BOX)


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
        # +16px unter die Boxkante (Bright Mode): die weisse Sitzbox ist HOEHER als die dunkle,
        # der Stack-Text sitzt tiefer — der alte Crop schnitt '195' horizontal durch.
        out[f"stack_{s}"] = (b[0] + NUM_INSET, y_split + 4, b[2] - NUM_INSET, b[3] + 16)
    for s, b in BET_BOX.items():
        out[f"bet_{s}"] = b
    return out


# Der EINSATZ-Betrag steht immer direkt unter einem gruenen Chip-Symbol — und der Chip ist farblich
# unverwechselbar. Ihn als ANKER zu nehmen ist robuster als feste Koordinaten: Snowie verschiebt den
# Betrag je nach Laenge ('$2' vs '$12.50'), und pro Sitz sitzt er woanders am Tischrand.
CHIP_MIN_PIX = 40             # Mindestzahl gruener Pixel, damit es als Chip zaehlt
CHIP_BOX_DY = (16, 46)        # Betrag liegt so weit UNTER der Chip-Mitte (live vermessen)
CHIP_BOX_DX = 55              # halbe Breite des Betrags-Fensters


TABLE_Y = (380, 1180)         # nur der Filz: darueber Menue, darunter die Aktionsleiste (gruener Button!)


def _green_chips(img: Image.Image) -> list[tuple[int, int]]:
    """Mittelpunkte aller gruenen Chip-Symbole auf dem Tisch (Bildkoordinaten)."""
    a = np.asarray(img.convert("RGB")).astype(int)
    a = a.copy()
    a[:TABLE_Y[0], :, :] = 0
    a[TABLE_Y[1]:, :, :] = 0
    g = (a[:, :, 1] - a[:, :, 0] > 45) & (a[:, :, 1] - a[:, :, 2] > 45) & (a[:, :, 1] > 110)
    ys, xs = np.where(g)
    if len(xs) < CHIP_MIN_PIX:
        return []
    pts, used = [], np.zeros(len(xs), bool)
    order = np.argsort(xs)
    for i in order:                                   # simple Clusterung: alles binnen 60px = ein Chip
        if used[i]:
            continue
        near = (np.abs(xs - xs[i]) < 60) & (np.abs(ys - ys[i]) < 60) & (~used)
        if near.sum() >= CHIP_MIN_PIX:
            mx_, my_ = int(xs[near].mean()), int(ys[near].mean())
            core = np.asarray(img.convert("L"))[max(0, my_ - 8):my_ + 8, max(0, mx_ - 8):mx_ + 8]
            if core.size and (core > 200).mean() >= 0.10:      # weisse Speichen -> echter Chip
                pts.append((mx_, my_))
        used |= near
    return pts


def read_bets(img: Image.Image, learn: bool = False,
              batch: dict | None = None) -> dict[str, float | None]:
    """Einsaetze ueber die Chip-Anker lesen und dem naechsten Sitz zuordnen.
    Ein Chip NAHE einem Sitz, dessen Betrag unlesbar ist, setzt den Sitz auf None (-> Gatter),
    statt ihn als 0 auszugeben: 'kein Einsatz' und 'Einsatz nicht lesbar' duerfen nie dasselbe sein."""
    out: dict[str, float | None] = {s: 0.0 for s in SEAT_BOX}
    for cx, cy in _green_chips(img):
        seat0 = min(SEAT_BOX, key=lambda s: (cx - (SEAT_BOX[s][0] + SEAT_BOX[s][2]) / 2) ** 2
                    + (cy - (SEAT_BOX[s][1] + SEAT_BOX[s][3]) / 2) ** 2)
        b = SEAT_BOX[seat0]
        d2 = (cx - (b[0] + b[2]) / 2) ** 2 + (cy - (b[1] + b[3]) / 2) ** 2
        if d2 > 300 ** 2:                              # weit weg von jedem Sitz = Logo/Deko, kein Einsatz
            continue
        box = (cx - CHIP_BOX_DX, cy + CHIP_BOX_DY[0], cx + CHIP_BOX_DX, cy + CHIP_BOX_DY[1])
        val = (batch or {}).get(f"bet_{seat0}")
        if val is None:
            val = read_number(img, box, learn)
        if not val:
            out[seat0] = None                          # Chip da, Betrag unklar -> ehrlich unbekannt
            continue
        out[seat0] = val if out[seat0] is None else max(out[seat0] or 0.0, val)
    return out


# AKTIONSLEISTE (native px, live vermessen): FOLD | CALL-oder-CHECK | RAISE-oder-BET.
# Der Betrag AUF dem Button ist die zuverlaessigste Zahl am ganzen Tisch — gross, fett, konstanter
# Hintergrund. Der Einsatz VOR dem Sitz ist die kleinste (eigener Font, matcht die Templates nicht).
# Fuer die Entscheidung brauchen wir aber genau zwei Dinge: darf ich checken, und was kostet ein Call.
# Beides steht auf dem mittleren Button — Ziffern vorhanden = CALL mit Betrag, keine Ziffern = CHECK.
BTN_FOLD_BOX = (604, 1235, 814, 1318)         # FOLD steht immer links — auch im Zwei-Button-Layout
BTN_STD_MIN = 12.0                            # gemessen: Button mit Text std 20-58, leere Flaeche 0-5
BTN_MID_BOX = (830, 1235, 1040, 1318)
BTN_RIGHT_BOX = (1056, 1235, 1266, 1318)


def read_buttons(img: Image.Image, learn: bool = False, batch: dict | None = None) -> dict:
    """-> {'active': bool, 'call_amount': float|None, 'can_check': bool, 'raise_min': float|None}.
    active=False heisst: wir sind nicht am Zug (keine Buttons sichtbar)."""
    if not hero_turn(img):
        return {"active": False, "call_amount": None, "can_check": False, "raise_min": None}
    mid = read_button_amount(img, BTN_MID_BOX, learn, (batch or {}).get("btn_mid"))
    rgt = read_button_amount(img, BTN_RIGHT_BOX, learn, (batch or {}).get("btn_right"))
    # read_number liefert 0.0, wenn im Feld gar keine Tinte/Zahl steckt -> das ist der CHECK-Fall.
    can_check = (mid == 0.0)
    return {"active": True, "call_amount": (None if can_check else mid),
            "can_check": can_check, "raise_min": (rgt or None)}


NUM_LINE_MIN_H = 9        # Ziffernzeilen sind ~17px; Rahmenkanten 4-6px, Textsplitter <8px
SOLID_BLOCK_FRAC = 0.70   # mehr "Tinte" als das ist ein Farbblock, kein Text


def bottom_line_box(img: Image.Image, box) -> tuple:
    """Ein Zahlenfeld auf seine UNTERSTE Textzeile eindampfen (mit Luft), Rueckfall = ganze Box.

    Zwei gemessene Bright-Mode-Faelle erzwingen das: der Pot-Crop enthaelt oben einen Streifen
    'TOTAL POT', dessen Fragmente die Segmentierung vergiften (eine 0.30-Schwelle las das Chaos
    als '8', der Tisch zeigte 13); und Sitz-Namen ragen von oben in die Stack-Crops.
    """
    g = np.asarray(_sub(img, box).convert("L"))
    # nur ZIFFERN-hohe Zeilen (>=9px; Ziffern sind ~17px): Heros weisse Rahmen-Unterkante (4-6px)
    # und der 'TOTAL POT'-Streifen (Teilzeile) qualifizierten sonst als "unterste Zeile" und die
    # Lesung lief auf leeren Pixeln (hero-Stack 0.0 in BEIDEN Regressionsfaellen - vom Netz gefangen).
    med = float(np.median(g))
    def _text_like(a, b):
        # echte Textzeilen sind 10-40% Tinte; ein VOLLBLOCK (~100%) ist der helle Hintergrund, der
        # unter einer dunklen Box in den erweiterten Crop ragt — keine Zeile, eine Flaeche.
        frac = float((np.abs(g[a:b].astype(np.int16) - med) > 60).mean())
        return frac <= SOLID_BLOCK_FRAC
    lines = [ln for ln in _text_lines(g) if ln[1] - ln[0] >= NUM_LINE_MIN_H and _text_like(*ln)]
    if not lines:
        return box
    top, bot = lines[-1]
    return (box[0], box[1] + max(0, top - 2), box[2], box[1] + min(g.shape[0], bot + 2))


def read_state(img: Image.Image | None = None, learn: bool = False) -> dict:
    img = img or SL.grab()
    cards = SL.read_cards(img, learn=learn)
    d = dealer_seat(img)
    live = {s: seat_live(img, s) for s in SEAT_BOX}
    F = number_fields()
    n_inset = NUM_INSET
    batch_boxes = {"pot": bottom_line_box(img, F["pot"]),
                   **{f"stack_{s}": bottom_line_box(img, F[f"stack_{s}"]) for s in SEAT_BOX},
                   **{f"bet_{s}": BET_BOX[s] for s in SEAT_BOX},
                   "btn_mid": (BTN_MID_BOX[0] + n_inset, BTN_MID_BOX[1] + n_inset,
                               BTN_MID_BOX[2] - n_inset, BTN_MID_BOX[3] - n_inset),
                   "btn_right": (BTN_RIGHT_BOX[0] + n_inset, BTN_RIGHT_BOX[1] + n_inset,
                                 BTN_RIGHT_BOX[2] - n_inset, BTN_RIGHT_BOX[3] - n_inset)}
    batch = read_numbers_batched(img, batch_boxes)
    # Plausibilitaet gilt fuer JEDEN Batch-Wert (Tesseract haengt gelegentlich Ziffern an)
    batch = {k: (v if v is not None and 0 <= v <= OCR_MAX_CHIPS else None) for k, v in batch.items()}
    bets = read_bets(img, learn, batch)
    # EIN OCR-Durchgang fuer Pot + alle Stacks (131ms statt 557ms Templates); was er nicht liefert,
    # holen die Vorlagen nach. Beides zusammen deckt mehr ab als jedes allein.
    def _n(key):
        v = batch.get(key)
        return v if v is not None else read_number(img, batch_boxes[key], learn)

    stacks = {s: _n(f"stack_{s}") for s in SEAT_BOX}
    pot = _n("pot")
    btn = read_buttons(img, learn, batch)
    mine = bets.get("hero")
    unknown_bet = any(v is None for s, v in bets.items() if live.get(s))
    live_bets = [v for s, v in bets.items() if live.get(s) and v is not None]
    mx = max(live_bets) if live_bets else 0.0
    return {
        "hero_turn": hero_turn(img), "hero_cards": cards["hero"], "board": cards["board"],
        "cards_unreadable": cards.get("unreadable", 0),
        "dealer": d, "positions": position_of(d) if d else {},
        "hero_position": position_of(d).get("hero") if d else None,
        "live": live, "bets": bets, "stacks": stacks, "pot": pot,
        "hero_bet": mine, "max_bet": mx,
        # PRIMAER vom Button (grosse, zuverlaessige Schrift); die Einsaetze vor den Sitzen sind
        # nur noch Kontext. Die Button-LOGIK wird dabei nicht interpretiert, nur die ZAHL gelesen —
        # der alte Fehlschlag kam von einem Sprachmodell, das die Legalitaet erfand.
        "buttons": btn,
        "can_check": btn["can_check"],
        "call_amount": btn["call_amount"],
        "raise_min_dollars": btn["raise_min"],
        "players_in_hand": sum(1 for s, v in live.items() if v),
        "unknown_bet": unknown_bet,
    }


# PLAUSIBILITAET (User-Auftrag "pruefe, dass wir nicht falsch spielen", 2026-08-04). Das Gatter prueft
# bisher nur, ob ein Wert LESBAR ist — nicht, ob er SINN ergibt. Gemessen: ein Stack wurde als 14104
# gelesen (statt ~180), der Bot hielt sich fuer 3500bb tief und raiste 206 Dollar in einen 9-Dollar-Pot.
# Eine Zahl, die gegen die Tisch-Geometrie verstoesst, ist ein Lesefehler — egal wie sauber sie aussieht.
BB_DOLLARS = 2.0                 # Tisch-Blinds; bestimmt die plausiblen Groessenordnungen
STACK_MAX_BB, POT_MAX_BB = 400, 1200


def duplicate_cards(s: dict) -> str | None:
    """Jede Karte gibt es GENAU EINMAL — ein Duplikat ist der Beweis eines Lesefehlers.
    Live gefangen (2026-08-04): Board las '6s Ks 2h Jd 6s'. Das Gatter prueft nur Lesbarkeit, also
    lief es durch, und der Evaluator haette stumm eine falsche Handstaerke berechnet — die
    gefaehrlichste Sorte Fehler, weil nichts abstuerzt und nichts warnt."""
    cards = [c for c in (s.get("hero_cards") or []) if c] + list(s.get("board") or [])
    seen = set()
    for c in cards:
        if c in seen:
            return f"Karte {c} doppelt gelesen ({' '.join(cards)}) — unmoeglich"
        seen.add(c)
    return None


def implausible(s: dict) -> str | None:
    st = (s.get("stacks") or {}).get("hero")
    pot = s.get("pot")
    if st is not None and not (BB_DOLLARS <= st <= STACK_MAX_BB * BB_DOLLARS):
        return f"Hero-Stack {st} ausserhalb plausibler Grenzen (Lesefehler)"
    if pot is not None and not (BB_DOLLARS * 0.5 <= pot <= POT_MAX_BB * BB_DOLLARS):
        return f"Pot {pot} ausserhalb plausibler Grenzen (Lesefehler)"
    if pot is not None and st is not None and pot > 12 * st + 200:
        return f"Pot {pot} passt nicht zum Stack {st}"
    for name, v in (s.get("stacks") or {}).items():
        if v is not None and v > STACK_MAX_BB * BB_DOLLARS:
            return f"Stack {name}={v} unmoeglich (Lesefehler)"
    return None


def gate(s: dict) -> str | None:
    """None = brauchbar. Sonst der Grund zu PAUSIEREN (jede Luecke ist ein Grund)."""
    if not s["hero_turn"]:
        return "nicht am Zug"
    if len([c for c in s["hero_cards"] if c]) != 2:
        return f"Hole Cards unlesbar ({s['hero_cards']})"
    if s.get("cards_unreadable"):
        return f"{s['cards_unreadable']} belegte Kartenplaetze unlesbar — Board waere verkuerzt"
    if len(s["board"]) not in (0, 3, 4, 5):
        return f"Board-Laenge {len(s['board'])} unmoeglich"
    if s["hero_position"] is None:
        return "Dealer-Button nicht gefunden"
    if s["pot"] is None or s["stacks"].get("hero") is None:
        return "Zahl unlesbar (Pot/Stack)"
    if not (s.get("buttons") or {}).get("active"):
        return "Aktions-Buttons nicht lesbar"
    if not s["can_check"] and s["call_amount"] is None:
        return "Weder Check moeglich noch Call-Betrag lesbar"
    bad = duplicate_cards(s) or implausible(s)
    if bad:
        return bad
    if not s["pot"] or s["pot"] <= 0:
        return "Pot = 0 — bei laufender Hand unmoeglich (stiller Lesefehler)"
    if not s["stacks"].get("hero"):
        return "Hero-Stack = 0 — unplausibel"
    if s["players_in_hand"] < 2:
        return f"Spielerzahl unplausibel ({s['players_in_hand']})"
    # Die Unmoeglichkeit aus Lauf 1 kann hier strukturell nicht mehr auftreten, wird aber geprueft:
    if not s["can_check"] and (s["call_amount"] or 0) <= 0:
        return "Widerspruch: kein Check moeglich, aber nichts zu callen"
    # POT ENTHAELT JEDES EINSATZNIVEAU (run_v15: to_call 250 bei Pot 150 lief ungehindert durch,
    # AA bekam einen unmoeglichen Preis praesentiert): Snowies TOTAL POT schliesst die liegenden
    # Einsaetze ein - ein Einsatzniveau ueber dem Pot ist immer ein Lesefehler.
    bets_l = s.get("bets") or {}
    live_l = s.get("live") or {}
    lv = [v for k, v in bets_l.items() if live_l.get(k) and v is not None]
    if lv and s.get("pot") is not None and max(lv) > s["pot"] + 0.01:
        return f"Einsatzniveau {max(lv):g} > Pot {s['pot']:g} - unmoeglich (Lesefehler)"
    # KREUZPROBE Button vs Einsaetze (nach dem '$8'->'38'-Fund): was ein Call kostet, folgt auch
    # aus den Chips auf dem Tisch. Widersprechen sich beide Quellen, ist eine davon falsch gelesen
    # -> pausieren. Ausnahme: der Call ist durch Heros Stack gedeckelt (All-in-Call).
    if s["call_amount"] is not None:
        bets, live = s.get("bets") or {}, s.get("live") or {}
        vals = [v for k, v in bets.items() if live.get(k)]
        if vals and all(v is not None for v in vals):
            expected = max(vals) - (bets.get("hero") or 0.0)
            hero_stack = s["stacks"].get("hero") or 0.0
            if expected > 0 and abs(s["call_amount"] - expected) > 0.01                     and abs(s["call_amount"] - hero_stack) > 0.01:
                return (f"Call-Betrag {s['call_amount']} widerspricht den Einsaetzen "
                        f"(erwartet {expected:g}) — eine Quelle luegt")
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


# ---------------------------------------------------------------- Zahlen in EINEM OCR-Durchgang
SLOT_PAD = 12             # Luft zwischen den Feld-Streifen, damit Tesseract sie als Zeilen trennt
OCR_MAX_CHIPS = 800       # = 400bb Stack-Maximum in Dollar. Verliert die OCR einen Dezimalpunkt,
                          # entsteht das Zehnfache ('185.5' -> 1855): unter 2000 passierte das den
                          # Filter und rannte 77x ins Gatter (run_v15). Alles darueber geht an den
                          # Vorlagen-Pfad, der den Punkt beherrscht - der liest 185.5 korrekt.
OCR_CFG_BLOCK = "--psm 6 -c tessedit_char_whitelist=0123456789.$"


def read_numbers_batched(img: Image.Image, boxes: dict) -> dict:
    """ALLE Zahlenfelder mit EINEM Tesseract-Aufruf lesen. -> {schluessel: float|None}.

    Ein OCR-Aufruf startet einen Prozess (~80ms). Zehn Felder einzeln zu lesen kostete darum mehr
    als die Vorlagen. Hier werden alle Felder untereinander in EIN Bild gestapelt, jedes in ein
    eigenes Fach fester Hoehe; ein Durchgang liest den Stapel, und jedes erkannte Wort wird ueber
    seine y-Position dem Fach zugeordnet. Das bleibt richtig, wenn ein Feld leer ist — anders als
    ein Zeilenzaehler, der dann alles verschieben wuerde.
    """
    tess = _tesseract()
    if not tess:
        return {k: None for k in boxes}
    keys = list(boxes)
    strips, width = [], 0
    for k in keys:
        # JEDES Feld EINZELN binarisieren: Snowie rendert aktive Sitze hell, gefoldete gedimmt. Ein
        # gemeinsames Invertieren laesst die dunklen Felder kontrastarm und Tesseract uebersieht sie
        # (gemessen: nur 3 von 13 Feldern gelesen). _ink findet die Schwelle pro Feld selbst.
        raw = np.asarray(_sub(img, boxes[k]).convert("L"))
        mask = _ink(raw, 0.55)
        c = Image.fromarray(np.where(mask, 0, 255).astype(np.uint8))    # Text schwarz auf weiss
        c = c.resize((c.width * OCR_SCALE, c.height * OCR_SCALE), Image.LANCZOS)
        strips.append(c)
        width = max(width, c.width)
    # Das Fach muss MINDESTENS so hoch sein wie der hoechste Streifen — ein festes Mass schnitt
    # die Ziffern ab (gemessen: Pot 239 wurde als 7 gelesen).
    slot_h = max(c.height for c in strips) + SLOT_PAD
    sheet = Image.new("L", (width, slot_h * len(keys)), 255)
    for i, c in enumerate(strips):
        sheet.paste(c, (0, i * slot_h))
    out = {k: None for k in keys}
    try:
        data = tess.image_to_data(sheet, config=OCR_CFG_BLOCK, output_type=tess.Output.DICT)
    except Exception:  # noqa: BLE001 — OCR darf den Lauf nie stoppen
        return out
    # Pro Fach das UNTERSTE Zahlwort: bei einzeiligen Feldern egal, bei Aktions-Buttons steht das
    # Wort OBEN und der Betrag UNTEN — genau der zaehlt.
    best_top = {}
    for txt, top, conf in zip(data["text"], data["top"], data["conf"]):
        txt = (txt or "").strip().lstrip("$").strip(".")
        if not txt or float(conf) < 0 or not txt.replace(".", "", 1).isdigit():
            continue
        slot = min(len(keys) - 1, max(0, top // slot_h))
        if top >= best_top.get(slot, -1):
            best_top[slot] = top
            out[keys[slot]] = float(txt)
    return out
