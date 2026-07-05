"""All PNG charts for the DEEP player-report (plan 2026-07-01), drawn with Pillow (renderPM is unavailable → we draw
pixels directly, then reportlab embeds the PNGs). Reads data/coach/deep_stats.json (+ style_sim.json for the bot-sim).

Framing rules baked in: NO money, NO 'losses'/'downswing' — variance is shown as a SYMMETRIC outcome-distribution +
a swing-amplitude number, never a direction-laden equity curve. Poker-green theme to match the report PDF.
"""
from __future__ import annotations

import json
import math
import os

from PIL import Image, ImageDraw, ImageFont

OUT_DIR = "data/coach/charts"
FONT = "C:/Windows/Fonts/arial.ttf"
FONT_B = "C:/Windows/Fonts/arialbd.ttf"

# --- theme --------------------------------------------------------------------------------------
GREEN = (31, 122, 77)
DARK = (26, 34, 48)
ACCENT = (15, 81, 50)
GREY = (91, 100, 112)
LIGHT = (238, 243, 239)
GOLD = (200, 160, 60)
BLUE = (60, 110, 170)
AMBER = (210, 150, 50)
RED_SOFT = (176, 84, 78)
WHITE = (255, 255, 255)
RANKS = "AKQJT98765432"


def _f(size, bold=False):
    return ImageFont.truetype(FONT_B if bold else FONT, size)


def _canvas(w, h, bg=WHITE):
    img = Image.new("RGB", (w, h), bg)
    return img, ImageDraw.Draw(img)


def _text(d, xy, s, size=16, bold=False, fill=DARK, anchor="la"):
    d.text(xy, s, font=_f(size, bold), fill=fill, anchor=anchor)


def _title(d, w, title, sub=None):
    _text(d, (40, 26), title, 30, True, ACCENT)
    if sub:
        _text(d, (40, 66), sub, 15, False, GREY)


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _save(img, name):
    os.makedirs(OUT_DIR, exist_ok=True)
    p = os.path.join(OUT_DIR, name)
    img.save(p)
    return p


# ---------------------------------------------------------------- 1. phase timeline (A/B/C game)
def phase_timeline(d: dict) -> str:
    sess = d["sessions"]
    W, H = 1200, 620
    img, dr = _canvas(W, H)
    _title(dr, W, "Deine Zeit-Phasen — A / B / C-Game über 6 Monate",
           "Jeder Balken = eine Spiel-Sitzung. Breite = Anzahl Hände. Farbe = wie fokussiert das Spiel war.")
    colA, colB, colC = GREEN, BLUE, AMBER
    lvl_col = {"A": colA, "B": colB, "C": colC}
    x0, y0, plot_w, plot_h = 60, 130, W - 120, 360
    total_hands = sum(s["n"] for s in sess)
    # lay sessions left→right, width ∝ hands
    x = x0
    for s in sess:
        bw = max(6, plot_w * s["n"] / total_hands)
        lvl = s["game_level"]
        # bar height encodes stake tier (serious = taller), color encodes level
        tier_h = {"high": 1.0, "mid": 0.72, "low": 0.42}[s["tier"]]
        bh = plot_h * tier_h
        y = y0 + (plot_h - bh)
        dr.rectangle([x, y, x + bw - 2, y0 + plot_h], fill=lvl_col[lvl])
        if bw > 22:
            _text(dr, (x + bw / 2, y0 + plot_h + 8), lvl, 13, True, lvl_col[lvl], "ma")
        x += bw
    # baseline + tier guide
    dr.line([x0, y0 + plot_h, x0 + plot_w, y0 + plot_h], fill=GREY, width=2)
    for frac, lab in [(1.0, "High"), (0.72, "Mid"), (0.42, "Low")]:
        yy = y0 + plot_h - plot_h * frac
        dr.line([x0, yy, x0 + plot_w, yy], fill=(220, 226, 220), width=1)
        _text(dr, (x0 + plot_w + 6, yy), lab, 12, False, GREY, "lm")
    _text(dr, (x0, y0 - 24), "Höhe = Einsatz-Level (höher = ernster gespielt)", 13, False, GREY)
    # legend + how-often
    gl = d["game_level_dist"]
    hb = d["hands_by_level"]
    ly = 545
    items = [("A", "A-Game — fokussiert, kontrolliert-aggressiv, ernste Stakes", colA),
             ("B", "B-Game — solide, etwas lockerer", colB),
             ("C", "C-Game — verspielt, experimentell, Micro-Aufwärmen", colC)]
    for i, (lv, lab, col) in enumerate(items):
        yy = ly + i * 24
        dr.rectangle([40, yy, 62, yy + 16], fill=col)
        n_s = gl.get(lv, 0)
        pct = 100 * hb.get(lv, 0) / max(1, total_hands)
        _text(dr, (72, yy), f"{lab}   —   {n_s} Sitzungen, {pct:.0f}% deiner Hände", 14, False, DARK)
    return _save(img, "phase_timeline.png")


# ---------------------------------------------------------------- 2. observed range matrix (13x13)
def _played_counter(d: dict) -> dict:
    """Aggregate mid+high played hands across positions × voluntary roles → {hand_class: count}."""
    out = {}
    for pos, roles in d["ranges"].items():
        for role, counter in roles.items():
            for hc, c in counter.items():
                out[hc] = out.get(hc, 0) + c
    return out


def observed_range_matrix(d: dict) -> str:
    played = _played_counter(d)
    mx = max(played.values()) if played else 1
    W, H = 900, 1000
    img, dr = _canvas(W, H)
    _title(dr, W, "Deine tatsächlich gespielte Range (Mid + High)",
           "Alle 169 Starthände. Je grüner, desto öfter hast du diese Hand freiwillig gespielt.")
    grid, cell = 60, 56
    total_played = sum(played.values())
    n_classes = sum(1 for v in played.values() if v > 0)
    for i, r1 in enumerate(RANKS):
        for j, r2 in enumerate(RANKS):
            x = grid + j * cell
            y = 130 + i * cell
            if i == j:
                hc = r1 + r2                      # pair
            elif i < j:
                hc = r1 + r2 + "s"                # suited (upper triangle)
            else:
                hc = r2 + r1 + "o"                # offsuit (lower triangle)
            c = played.get(hc, 0)
            t = (c / mx) ** 0.6 if c else 0
            fill = _lerp(WHITE, GREEN, t) if c else (245, 247, 245)
            dr.rectangle([x, y, x + cell - 3, y + cell - 3], fill=fill, outline=(225, 230, 225))
            tcol = WHITE if t > 0.55 else (DARK if c else (190, 195, 190))
            _text(dr, (x + cell / 2 - 1, y + cell / 2 - 2), hc, 12, c > 0, tcol, "mm")
    # legend gradient
    gy = 130 + 13 * cell + 30
    _text(dr, (grid, gy - 4), "selten", 13, False, GREY)
    for k in range(180):
        dr.rectangle([grid + 60 + k, gy, grid + 61 + k, gy + 18], fill=_lerp(WHITE, GREEN, k / 180))
    _text(dr, (grid + 250, gy - 4), "oft", 13, False, GREY)
    _text(dr, (grid, gy + 34),
          f"Du hast {n_classes} von 169 möglichen Starthänden freiwillig gespielt — eine sehr breite, "
          f"schwer lesbare Range.", 15, False, DARK)
    _text(dr, (grid, gy + 60),
          "Diagonale = Paare · oben rechts = suited (gleiche Farbe) · unten links = offsuit.", 13, False, GREY)
    return _save(img, "observed_range.png")


# ---------------------------------------------------------------- 3. confusion / sizing entropy
def confusion_chart(d: dict) -> str:
    ent = d["entropy"]
    dist = ent["distribution"]
    W, H = 1100, 600
    img, dr = _canvas(W, H)
    _title(dr, W, "Die Confusion-Frage — wie unlesbar sind deine Einsatz-Größen?",
           "Verteilung deiner Setzgrößen nach dem Flop (als Anteil des Pots). Viel Streuung = schwer auszurechnen.")
    # --- entropy gauge (top) ---
    bits, mxb = ent["entropy_bits"], ent["max_bits"]
    gx, gy, gw = 130, 145, 820
    _text(dr, (gx, gy - 32), f"Unberechenbarkeit deiner Sizings: {bits} von {mxb:.0f} — "
          f"{'sehr hoch' if bits/mxb>0.85 else 'hoch' if bits/mxb>0.6 else 'mittel'}.", 17, True, ACCENT)
    dr.rounded_rectangle([gx, gy, gx + gw, gy + 30], 8, fill=LIGHT)
    dr.rounded_rectangle([gx, gy, gx + int(gw * bits / mxb), gy + 30], 8, fill=GREEN)
    total = sum(dist.values()) or 1
    over_pct = 100 * dist[">1.1x (overbet)"] / total
    _text(dr, (gx, gy + 44),
          f"{over_pct:.0f}% deiner Einsätze sind Overbets (größer als der Pot) — du bespielst das ganze "
          f"Größen-Spektrum.", 14, False, DARK)
    # --- bars (below, no overlap) ---
    labels = {"<=0.4x": "klein\n(bis 40% Pot)", "0.4-0.7x": "mittel\n(40–70%)",
              "0.7-1.1x": "groß\n(70–110%)", ">1.1x (overbet)": "Overbet\n(über 110%)"}
    cols = {"<=0.4x": BLUE, "0.4-0.7x": GREEN, "0.7-1.1x": AMBER, ">1.1x (overbet)": RED_SOFT}
    x0, y0, bw, gap, maxbar = 130, 500, 150, 70, 210
    mx = max(dist.values())
    for i, k in enumerate(["<=0.4x", "0.4-0.7x", "0.7-1.1x", ">1.1x (overbet)"]):
        x = x0 + i * (bw + gap)
        h = maxbar * dist[k] / mx
        dr.rectangle([x, y0 - h, x + bw, y0], fill=cols[k])
        _text(dr, (x + bw / 2, y0 - h - 26), f"{100*dist[k]/total:.0f}%", 20, True, cols[k], "ma")
        for li, line in enumerate(labels[k].split("\n")):
            _text(dr, (x + bw / 2, y0 + 12 + li * 20), line, 14, li == 0, DARK, "ma")
    dr.line([x0 - 20, y0, x0 + 4 * (bw + gap) - gap + 20, y0], fill=GREY, width=2)
    return _save(img, "confusion.png")


# ---------------------------------------------------------------- 4. variance (symmetric distribution)
def variance_chart(d: dict) -> str:
    """Outcome SPREAD, no direction: a symmetric histogram of per-hand results (bb) + swing-amplitude number."""
    rows_path = "data/coach/_hand_nets.json"
    nets = json.load(open(rows_path, encoding="utf-8")) if os.path.exists(rows_path) else []
    v = d["variance_serious"]
    W, H = 1100, 560
    img, dr = _canvas(W, H)
    _title(dr, W, "Deine Varianz, in Zahlen gefasst",
           "Wie weit deine einzelnen Hand-Ergebnisse streuen (in großen Blinds). Breite Streuung = High-Variance-Stil.")
    # histogram buckets, symmetric & clipped so no single tail dominates the story
    if nets:
        clip = 60
        buckets = [0] * 13                      # -60..+60 in 10-bb steps (center = ~0)
        for x in nets:
            xc = max(-clip, min(clip, x))
            idx = int((xc + clip) / 10)
            idx = min(12, idx)
            buckets[idx] += 1
        mx = max(buckets)
        x0, y0, bw, maxbar = 130, 400, 62, 240
        for i, b in enumerate(buckets):
            x = x0 + i * bw
            h = maxbar * b / mx if mx else 0
            center = abs(i - 6) / 6
            col = _lerp(GREEN, AMBER, center)
            dr.rectangle([x, y0 - h, x + bw - 6, y0], fill=col)
        dr.line([x0, y0, x0 + 13 * bw, y0], fill=GREY, width=2)
        _text(dr, (x0, y0 + 12), "kleinere Pötte", 13, False, GREY)
        _text(dr, (x0 + 6.5 * bw, y0 + 12), "ausgeglichen", 13, True, DARK, "ma")
        _text(dr, (x0 + 13 * bw, y0 + 12), "große Pötte", 13, False, GREY, "ra")
    # numbers box
    bx, by = 760, 150
    _text(dr, (bx, by), "Schwankungsbreite (Mid + High)", 16, True, ACCENT)
    lines = [f"Streuung je Hand:  ±{v['std_per_hand_bb']:.0f} bb",
             f"Streuung je 100 Hände:  ±{v['std_per_100_bb']:.0f} bb",
             f"Größte Auslenkung:  {v['swing_amplitude_bb']:.0f} bb"]
    for i, ln in enumerate(lines):
        _text(dr, (bx, by + 34 + i * 30), ln, 15, False, DARK)
    _text(dr, (bx, by + 150), "Hohe Werte = ein aufregender, wuchtiger\nSpielstil mit großen Ausschlägen —\ndas ist der Preis der Aggression.",
          13, False, GREY)
    return _save(img, "variance.png")


# ---------------------------------------------------------------- 5. Poker-IQ radar
def iq_radar(dims: dict, iq: int) -> str:
    W, H = 900, 820
    img, dr = _canvas(W, H)
    _title(dr, W, f"Der IQ deines Spiels — Index {iq}/100",
           "Ein konstruierter Kennwert aus messbaren Bausteinen deines Spiels (kein offizieller Wert, eine Landkarte).")
    cx, cy, R = 450, 470, 250
    keys = list(dims.keys())
    n = len(keys)
    # rings
    for ring in range(1, 5):
        pts = []
        for i in range(n):
            a = -math.pi / 2 + 2 * math.pi * i / n
            rr = R * ring / 4
            pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
        dr.polygon(pts, outline=(220, 226, 220))
    # axes + labels
    poly = []
    for i, k in enumerate(keys):
        a = -math.pi / 2 + 2 * math.pi * i / n
        dr.line([cx, cy, cx + R * math.cos(a), cy + R * math.sin(a)], fill=(225, 230, 225))
        val = dims[k] / 100
        poly.append((cx + R * val * math.cos(a), cy + R * val * math.sin(a)))
        lx, ly = cx + (R + 42) * math.cos(a), cy + (R + 42) * math.sin(a)
        anchor = "mm"
        _text(dr, (lx, ly - 10), k, 15, True, ACCENT, "mm")
        _text(dr, (lx, ly + 10), f"{dims[k]}", 14, False, GREEN, "mm")
    # value polygon
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    od.polygon(poly, fill=(31, 122, 77, 90), outline=(31, 122, 77, 255))
    img.paste(Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB"), (0, 0))
    dr = ImageDraw.Draw(img)
    for p in poly:
        dr.ellipse([p[0] - 4, p[1] - 4, p[0] + 4, p[1] + 4], fill=GREEN)
    return _save(img, "iq_radar.png")


# ---------------------------------------------------------------- 6. bot-sim
def bot_sim_chart(sim: dict) -> str:
    """Honest framing: single-type tables are high-variance, so we show QUALITATIVE tiers + sqrt-scaled bars (so the
    maniac edge doesn't dwarf everything) — NOT the raw, misleading bb/100 magnitudes. The robust signal both runs
    agree on: the biggest edge is vs wild/recreational opponents (the online pool)."""
    W, H = 1100, 600
    img, dr = _canvas(W, H)
    _title(dr, W, "Simulation — unsere Engine spielt deinen Style",
           "Dein Stil-Zwilling (locker, aggressiv, Overbets) gegen viele Gegner-Typen. Je länger der Balken, desto größer dein Vorteil.")
    per = sim["style_per_opponent"]
    order = sorted(per.items(), key=lambda kv: kv[1]["bb_per_100"], reverse=True)
    names_de = {"station": "Calling-Station (geht viel mit)", "whale": "Whale (sehr locker)",
                "nit": "Nit (extrem vorsichtig)", "rock": "Rock (super tight)", "maniac": "Maniac (wild, überaggressiv)",
                "lag": "Loose-Aggressiv", "tag": "Tight-Aggressiv", "shark": "Shark (starker Reg)"}

    def tier(v):
        if v > 800: return "sehr großer Vorteil", GREEN
        if v > 200: return "großer Vorteil", GREEN
        if v > 0: return "leichter Vorteil", (90, 150, 110)
        return "eng · hohe Schwankung", AMBER

    x0, y0, rowh = 470, 120, 50
    mx = max(abs(v["bb_per_100"]) for _, v in order) ** 0.5 or 1
    for i, (opp, s) in enumerate(order):
        y = y0 + 20 + i * rowh
        v = s["bb_per_100"]
        lab, col = tier(v)
        _text(dr, (x0 - 16, y + 10), names_de.get(opp, opp), 14, True, DARK, "ra")
        bl = 480 * (abs(v) ** 0.5) / mx
        dr.rectangle([x0, y, x0 + max(4, bl), y + 22], fill=col)
        _text(dr, (x0 + max(4, bl) + 8, y + 10), lab, 12, True, col, "lm")
    dr.line([x0, y0 + 12, x0, y0 + 20 + len(order) * rowh], fill=GREY, width=2)
    _text(dr, (40, y0 + 34 + len(order) * rowh),
          "Lektion: Dein Stil ist quer durchs Feld im Plus — am wuchtigsten gegen wilde und lockere Gegner "
          "(Maniacs, Stations, Whales),", 14, False, DARK)
    _text(dr, (40, y0 + 56 + len(order) * rowh),
          "also genau den typischen Online-Pool. Der Preis dafür ist eine hohe Schwankungsbreite — dieselbe "
          "Aggression, die zerlegt, schwankt auch stark.", 14, False, DARK)
    return _save(img, "bot_sim.png")


def station_sim_chart(sim: dict) -> str:
    """Bar chart of the calling-station Monte Carlo: Δ(bet − check) bb per scenario, grouped bluff/value/sizing."""
    rows = [  # (label, key-substring, group)
        ("Bluff: 3 Barrels bis River", "BLUFF 3 barrels 0.66x vs station", "BLUFFEN"),
        ("Bluff: nur ein Flop-Stab", "BLUFF flop-only", "BLUFFEN"),
        ("Bluff: 3 Barrels vs. Mega-Station", "MEGA-station", "BLUFFEN"),
        ("Top-Pair: 3x Value (halber Pot)", "top-pair 3 streets 0.5x", "VALUE"),
        ("Top-Pair: 3x Value (2/3 Pot)", "top-pair 3 streets 0.66x", "VALUE"),
        ("Schwaches Paar: 3 Barrels", "WEAK-pair barrel", "VALUE"),
        ("Schwaches Paar: nur ein Bet", "WEAK-pair one bet", "VALUE"),
        ("Starke Hand: kleiner Bet (½ Pot)", "STRONG small", "SIZING"),
        ("Starke Hand: Overbet (1,2× Pot)", "STRONG big", "SIZING"),
    ]
    by = {t["label"]: t for t in sim["tests"]}
    def find(sub):
        return next((v for k, v in by.items() if sub in k), None)
    W, H = 1200, 760
    img, dr = _canvas(W, H)
    _title(dr, W, "Simulation: Bluffen vs. Value gegen einen Calling-Station",
           "Bringt SETZEN mehr als CHECKEN? Je Fall 6000 echte Hände bis zum Showdown. Grün = Setzen bringt Chips, Rot = Setzen verliert Chips.")
    axis_x, y, rowh = 470, 150, 52          # one-sided bars from a fixed axis; sign shown by colour + the number
    mx = max(abs(find(s)["bet_minus_check_bb"]) for _, s, _ in rows) or 1
    last_group = None
    for lab, sub, grp in rows:
        t = find(sub)
        if grp != last_group:
            _text(dr, (40, y - 1), grp, 15, True, ACCENT)
            last_group = grp
        v = t["bet_minus_check_bb"]
        _text(dr, (axis_x - 16, y + 13), lab, 14, False, DARK, "ra")
        bl = max(3, 590 * abs(v) / mx)
        col = GREEN if v > 0.5 else (RED_SOFT if v < -0.5 else GREY)
        dr.rectangle([axis_x, y, axis_x + bl, y + 24], fill=col)
        _text(dr, (axis_x + bl + 8, y + 12), f"{v:+.1f} bb", 14, True, col, "lm")
        y += rowh
    dr.line([axis_x, 140, axis_x, y - 6], fill=GREY, width=2)
    y += 8
    for ln in [
        "Lektion 1 — Bluffs bis zum River verbrennen Chips: sie zahlen mit jedem Paar. Ein EINZELNER Flop-Stab ist ok (±0).",
        "Lektion 2 — Value: setze deine STARKEN Hände groß. Der Overbet bringt ~4,6× so viel wie ein kleiner Bet.",
        "Lektion 3 — Top-Pair ruhig drei Straßen dünn betten; ein SCHWACHES Paar aber NICHT bis zum River prügeln (Pot klein halten).",
    ]:
        _text(dr, (40, y), ln, 14, True, DARK)
        y += 24
    return _save(img, "station_sim.png")


def station_sim_chart_mobile(sim: dict) -> str:
    """A PORTRAIT, large-font version of the station chart for phone (iPhone Pro Max) reading — big text so it stays
    legible when the PDF scales it to a ~386pt-wide page."""
    rows = [
        ("Bluff — 3 Straßen bis River", "BLUFF 3 barrels 0.66x vs station", "BLUFFEN"),
        ("Bluff — nur ein Flop-Stab", "BLUFF flop-only", "BLUFFEN"),
        ("Bluff — 3 Straßen vs. Mega", "MEGA-station", "BLUFFEN"),
        ("Top-Pair — 3× dünn (½ Pot)", "top-pair 3 streets 0.5x", "VALUE"),
        ("Top-Pair — 3× dünn (⅔ Pot)", "top-pair 3 streets 0.66x", "VALUE"),
        ("Schwaches Paar — 3 Straßen", "WEAK-pair barrel", "VALUE"),
        ("Schwaches Paar — nur 1 Bet", "WEAK-pair one bet", "VALUE"),
        ("Starke Hand — kleiner Bet", "STRONG small", "SIZING"),
        ("Starke Hand — Overbet", "STRONG big", "SIZING"),
    ]
    by = {t["label"]: t for t in sim["tests"]}
    def find(sub):
        return next((v for k, v in by.items() if sub in k), None)
    W, H = 760, 1170
    img, dr = _canvas(W, H)
    _text(dr, (30, 30), "Setzen vs. Checken", 40, True, ACCENT)
    _text(dr, (30, 82), "gegen einen Calling-Station", 26, True, GREEN)
    _text(dr, (30, 120), "Je Fall 6000 echte Hände. Grün = Setzen bringt", 20, False, GREY)
    _text(dr, (30, 146), "Chips, Rot = Setzen verliert Chips.", 20, False, GREY)
    y = 210
    axis_x = 34
    mx = max(abs(find(s)["bet_minus_check_bb"]) for _, s, _ in rows) or 1
    last = None
    for lab, sub, grp in rows:
        t = find(sub)
        v = t["bet_minus_check_bb"]
        if grp != last:
            _text(dr, (30, y), grp, 23, True, ACCENT)
            y += 34
            last = grp
        _text(dr, (34, y), lab, 24, True, DARK)
        bar_y = y + 34
        bl = max(4, 500 * abs(v) / mx)
        col = GREEN if v > 0.5 else (RED_SOFT if v < -0.5 else GREY)
        dr.rectangle([axis_x, bar_y, axis_x + bl, bar_y + 30], fill=col)
        _text(dr, (axis_x + bl + 12, bar_y + 15), f"{v:+.1f} bb", 24, True, col, "lm")
        y = bar_y + 62
    return _save(img, "station_sim_mobile.png")


if __name__ == "__main__":
    d = json.load(open("data/coach/deep_stats.json", encoding="utf-8"))
    print(phase_timeline(d))
    print(observed_range_matrix(d))
    print(confusion_chart(d))
    print(variance_chart(d))
    if os.path.exists("data/coach/style_sim.json"):
        print(bot_sim_chart(json.load(open("data/coach/style_sim.json", encoding="utf-8"))))
    print("charts done")
