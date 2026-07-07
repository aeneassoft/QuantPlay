"""Princedarkness tournament player-report -> a cool poker-felt PDF (2026-07-07).
Canvas-drawn (no matplotlib): felt background, gold accents, the chip-arc as a scaled polyline, drawn cards.
Run:  python -m research.tourney_report
"""
from __future__ import annotations

import re

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

HH = (r"C:\Users\hampe\Documents\1# Personal Poker Hand Histories + reports"
      r"\GG20260706-2110 - Speed Racer Bounty 108 [10 BB].txt")
OUT = (r"C:\Users\hampe\Documents\1# Personal Poker Hand Histories + reports"
       r"\Princedarkness_Spieler-Report.pdf")

# ---- palette (poker felt) ----
FELT   = (0.043, 0.239, 0.180)   # deep green
FELT2  = (0.055, 0.290, 0.220)
GOLD   = (0.831, 0.686, 0.216)
CREAM  = (0.961, 0.941, 0.882)
REDC   = (0.855, 0.267, 0.216)   # hearts/diamonds
DARK   = (0.06, 0.15, 0.11)
MUTE   = (0.62, 0.72, 0.66)
TEAL   = (0.10, 0.74, 0.61)

W, H = A4


# ---------------------------------------------------------------- parse
def parse():
    txt = open(HH, encoding="utf-8").read()
    hands = [h for h in re.split(r"(?=Poker Hand #)", txt) if h.strip().startswith("Poker Hand")][::-1]
    arc, rows = [], []
    for i, h in enumerate(hands, 1):
        lvl = int(re.search(r"Level(\d+)", h).group(1))
        bb = int(re.search(r"Level\d+\([\d,]+/([\d,]+)", h).group(1).replace(",", ""))
        m = re.search(r"Seat \d+: Hero \(([\d,]+) in chips\)", h)
        chips = int(m.group(1).replace(",", "")) if m else 0
        cards = re.search(r"Dealt to Hero \[([^\]]+)\]", h)
        cards = cards.group(1) if cards else "??"
        allin = bool(re.search(r"Hero:.*all-in", h)) or "and is all-in" in h and "Hero" in h
        res = "won" if re.search(r"Hero.*(won|collected)", h) else ("lost" if "Hero" in h and "lost" in h else "fold")
        arc.append((i, lvl, chips, round(chips / bb, 1)))
        rows.append(dict(i=i, lvl=lvl, chips=chips, bb=round(chips / bb, 1), cards=cards, res=res, allin=allin))
    return arc, rows


# ---------------------------------------------------------------- helpers
def bg(c):
    c.setFillColorRGB(*FELT); c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColorRGB(*FELT2)
    c.setStrokeColorRGB(*FELT2)


def text(c, x, y, s, size, col=CREAM, font="Helvetica", center=False, right=False):
    c.setFillColorRGB(*col); c.setFont(font, size)
    if center: c.drawCentredString(x, y, s)
    elif right: c.drawRightString(x, y, s)
    else: c.drawString(x, y, s)


def panel(c, x, y, w, h, fill=DARK, radius=6, alpha=1.0):
    c.saveState(); c.setFillAlpha(alpha)
    c.setFillColorRGB(*fill); c.roundRect(x, y, w, h, radius, fill=1, stroke=0)
    c.restoreState()


def card(c, x, y, rank, suit, w=15 * mm, h=21 * mm):
    """Draw a playing card."""
    c.setFillColorRGB(*CREAM); c.roundRect(x, y, w, h, 2.5, fill=1, stroke=0)
    red = suit in "hd"
    col = REDC if red else (0.10, 0.10, 0.12)
    sym = {"h": "♥", "d": "♦", "s": "♠", "c": "♣"}[suit]
    r = {"T": "10"}.get(rank, rank)
    c.setFillColorRGB(*col)
    c.setFont("Helvetica-Bold", 12); c.drawString(x + 2, y + h - 12, r)
    c.setFont("Helvetica", 15); c.drawCentredString(x + w / 2, y + h / 2 - 6, sym)
    c.setFont("Helvetica-Bold", 8); c.drawRightString(x + w - 2, y + 4, r)


def hand_cards(c, x, y, cards, scale=1.0):
    parts = cards.split()
    for k, p in enumerate(parts):
        card(c, x + k * 17 * mm * scale, y, p[0], p[1], 15 * mm * scale, 21 * mm * scale)


def chip(c, cx, cy, r, col=GOLD):
    c.setFillColorRGB(*col); c.circle(cx, cy, r, fill=1, stroke=0)
    c.setStrokeColorRGB(*CREAM); c.setLineWidth(1); c.setDash(2, 2)
    c.circle(cx, cy, r * 0.72, fill=0, stroke=1); c.setDash()


# ---------------------------------------------------------------- pages
def cover(c, arc, rows):
    bg(c)
    # top gold rule
    c.setFillColorRGB(*GOLD); c.rect(0, H - 8, W, 8, fill=1, stroke=0)
    # chips motif
    for k, xx in enumerate((28, 40, 52)):
        chip(c, xx * mm, H - 32 * mm, 9 * mm - k * 0.4 * mm, GOLD if k != 1 else TEAL)
    text(c, W / 2, H - 55 * mm, "SPIELER-REPORT", 15, GOLD, "Helvetica-Bold", center=True)
    text(c, W / 2, H - 72 * mm, "PRINCEDARKNESS", 42, CREAM, "Helvetica-Bold", center=True)
    text(c, W / 2, H - 83 * mm, "Speed Racer Bounty  $108  ·  7-max Hyper-Turbo  ·  2026-07-07", 11, MUTE, center=True)

    # hero medallion
    cx, cy = W / 2, H - 120 * mm
    c.setFillColorRGB(*GOLD); c.circle(cx, cy, 26 * mm, fill=1, stroke=0)
    c.setFillColorRGB(*FELT); c.circle(cx, cy, 22 * mm, fill=1, stroke=0)
    text(c, cx, cy + 4 * mm, "PLATZ", 12, GOLD, "Helvetica-Bold", center=True)
    text(c, cx, cy - 12 * mm, "3", 46, CREAM, "Helvetica-Bold", center=True)

    # money panels
    py = 60 * mm
    for x0, big, small in ((28 * mm, "$108", "Buy-in"),
                           (W / 2 - 22 * mm, "~$1.200", "Gewonnen"),
                           (W - 72 * mm, "+$200", "ICM: Platz 3 statt 4")):
        panel(c, x0, py, 44 * mm, 22 * mm, DARK, 6)
        text(c, x0 + 22 * mm, py + 13 * mm, big, 18, GOLD, "Helvetica-Bold", center=True)
        text(c, x0 + 22 * mm, py + 5 * mm, small, 8, MUTE, center=True)

    peak = max(arc, key=lambda a: a[2])
    text(c, W / 2, 42 * mm, f"10.000  →  {peak[2]:,} Chips  (47×)  ·  75 Hände  ·  Chip-Leader am Finaltisch".replace(",", "."),
         10, CREAM, center=True)
    text(c, W / 2, 20 * mm, "Ein starker Deep-Run — entschieden von einem einzigen Flip.", 11, TEAL, "Helvetica-Oblique", center=True)
    c.setFillColorRGB(*GOLD); c.rect(0, 0, W, 6, fill=1, stroke=0)
    c.showPage()


def run_page(c, arc, rows):
    bg(c)
    text(c, 22 * mm, H - 22 * mm, "DER RUN", 22, GOLD, "Helvetica-Bold")
    text(c, 22 * mm, H - 30 * mm, "Chip-Verlauf über 75 Hände — in ECHTEN Chips (nicht BB) gestiegen bis zum Peak.", 10, MUTE)

    # chip arc polyline
    gx, gy, gw, gh = 22 * mm, H - 130 * mm, W - 44 * mm, 88 * mm
    panel(c, gx, gy, gw, gh, DARK, 8)
    xs = [a[0] for a in arc]; ys = [a[2] for a in arc]
    xmin, xmax, ymax = min(xs), max(xs), max(ys)
    def px(i): return gx + 8 * mm + (i - xmin) / (xmax - xmin) * (gw - 16 * mm)
    def py(v): return gy + 8 * mm + v / ymax * (gh - 16 * mm)
    # gridlines
    c.setStrokeColorRGB(*FELT2); c.setLineWidth(0.5)
    for frac in (0.25, 0.5, 0.75, 1.0):
        yy = gy + 8 * mm + frac * (gh - 16 * mm)
        c.line(gx + 8 * mm, yy, gx + gw - 8 * mm, yy)
        text(c, gx + 6 * mm, yy - 2, f"{int(ymax*frac/1000)}k", 6, MUTE, right=True)
    # area under curve
    p = c.beginPath(); p.moveTo(px(xs[0]), py(0))
    for i, v in zip(xs, ys): p.lineTo(px(i), py(v))
    p.lineTo(px(xs[-1]), py(0)); p.close()
    c.setFillColorRGB(*FELT2); c.setFillAlpha(0.6); c.drawPath(p, fill=1, stroke=0); c.setFillAlpha(1)
    # line
    c.setStrokeColorRGB(*GOLD); c.setLineWidth(2.2)
    p2 = c.beginPath(); p2.moveTo(px(xs[0]), py(ys[0]))
    for i, v in zip(xs, ys): p2.lineTo(px(i), py(v))
    c.drawPath(p2, stroke=1, fill=0)
    # peak marker
    peak = max(arc, key=lambda a: a[2])
    chip(c, px(peak[0]), py(peak[2]), 3.2 * mm, TEAL)
    text(c, px(peak[0]), py(peak[2]) + 6 * mm, f"PEAK {peak[2]//1000}k", 8, TEAL, "Helvetica-Bold", center=True)
    # bust marker
    chip(c, px(xs[-1]), py(ys[-1]), 3 * mm, REDC)
    text(c, px(xs[-1]) - 5 * mm, py(ys[-1]) + 9 * mm, "BUST", 8, REDC, "Helvetica-Bold", right=True)
    text(c, gx + gw / 2, gy - 5 * mm, "Hand 1  →  Hand 75   (die Blinds explodierten schneller als jeder akkumulieren konnte — der 'BB-Verfall' war eine Hyper-Illusion)", 8, MUTE, center=True)

    # narrative panels
    ny = gy - 62 * mm
    blurbs = [
        ("AKKUMULATION", "Von 10 BB auf ~470k — fast monoton gestiegen. Aggressives Early-Game (JhTh, KsJs, JsAs), 6× in Level 1.", TEAL),
        ("DER HYPER-DRUCK", "Level 1 → 21: Blinds bis 60k/120k + 18k Ante. Am Finaltisch hatte JEDER nur 4–10 BB — Shove/Fold-Territorium.", GOLD),
        ("DIE LEITER", "Als Short Stack diszipliniert gelaufen: Double-ups mit 66, TT, KhQh, QdJs — von ~8 BB durch 40 Hände bis Platz 3.", CREAM),
    ]
    bw = (gw - 8 * mm) / 3
    for k, (t, b, col) in enumerate(blurbs):
        x0 = gx + k * (bw + 4 * mm)
        panel(c, x0, ny, bw, 46 * mm, DARK, 6)
        c.setFillColorRGB(*col); c.rect(x0, ny + 46 * mm - 3, bw, 3, fill=1, stroke=0)
        text(c, x0 + 5 * mm, ny + 37 * mm, t, 10, col, "Helvetica-Bold")
        _wrap(c, x0 + 5 * mm, ny + 30 * mm, bw - 10 * mm, b, 8.5, CREAM)
    c.setFillColorRGB(*GOLD); c.rect(0, 0, W, 5, fill=1, stroke=0)
    c.showPage()


def _wrap(c, x, y, w, s, size, col, lead=None):
    lead = lead or size + 2.5
    c.setFillColorRGB(*col); c.setFont("Helvetica", size)
    words, line = s.split(), ""
    for wd in words:
        if c.stringWidth(line + " " + wd, "Helvetica", size) < w:
            line = (line + " " + wd).strip()
        else:
            c.drawString(x, y, line); y -= lead; line = wd
    if line: c.drawString(x, y, line)
    return y


def pivotal_page(c):
    bg(c)
    text(c, 22 * mm, H - 22 * mm, "WARUM PLATZ 3 — EIN FLIP", 22, GOLD, "Helvetica-Bold")
    text(c, 22 * mm, H - 30 * mm, "Am Shove/Fold-Finaltisch (alle ~5 BB) entscheidet ein Coinflip über Platz 1 vs 3.", 10, MUTE)

    # pivotal hand panel
    y = H - 110 * mm
    panel(c, 22 * mm, y, W - 44 * mm, 72 * mm, DARK, 8)
    text(c, 30 * mm, y + 62 * mm, "DIE SCHLÜSSELHAND  ·  Hand 71  ·  Level 20  ·  ~4,6 BB", 11, GOLD, "Helvetica-Bold")
    # hero
    text(c, 30 * mm, y + 50 * mm, "DU (all-in)", 9, TEAL, "Helvetica-Bold")
    hand_cards(c, 30 * mm, y + 26 * mm, "Ad Kc")
    text(c, 30 * mm, y + 20 * mm, "Dominierend: ~70% Equity", 8, MUTE)
    # vs
    text(c, W / 2, y + 40 * mm, "VS", 16, CREAM, "Helvetica-Bold", center=True)
    # villain
    text(c, W - 78 * mm, y + 50 * mm, "CALLER", 9, REDC, "Helvetica-Bold")
    hand_cards(c, W - 78 * mm, y + 26 * mm, "Ks Td")
    text(c, W - 78 * mm, y + 20 * mm, "~30% — aber floppt Paar", 8, MUTE)
    # board
    text(c, 30 * mm, y + 12 * mm, "Board:", 9, MUTE)
    hand_cards(c, 48 * mm, y + 2 * mm, "7s 5h Tc 5s 9h", 0.62)
    text(c, W - 78 * mm, y + 8 * mm, "→ Villain: two pair", 9, REDC, "Helvetica-Bold")
    text(c, W - 78 * mm, y + 2 * mm, "AK verliert.", 10, REDC, "Helvetica-Bold")

    # ICM mastery
    y2 = y - 66 * mm
    panel(c, 22 * mm, y2, (W - 48 * mm) / 2, 58 * mm, DARK, 6)
    text(c, 28 * mm, y2 + 50 * mm, "ICM-MEISTERSCHAFT", 11, TEAL, "Helvetica-Bold")
    text(c, 28 * mm, y2 + 42 * mm, "Hand 70 · du foldest A7o am Button (4,7 BB)", 9, CREAM, "Helvetica-Bold")
    _wrap(c, 28 * mm, y2 + 35 * mm, (W - 48 * mm) / 2 - 12 * mm,
          "Danach clashen SB (94s) und BB (KJo) all-in — einer bustet. Du lässt die anderen aufeinander los und LADDERST. Genau die Bounty/ICM-Logik.", 8.5, CREAM)
    text(c, 28 * mm, y2 + 8 * mm, "= +$200 (Platz 3 statt 4)", 11, GOLD, "Helvetica-Bold")

    xr = 22 * mm + (W - 48 * mm) / 2 + 4 * mm
    panel(c, xr, y2, (W - 48 * mm) / 2, 58 * mm, DARK, 6)
    text(c, xr + 6 * mm, y2 + 50 * mm, "DEINE EIGENE ERKENNTNIS", 11, GOLD, "Helvetica-Bold")
    _wrap(c, xr + 6 * mm, y2 + 42 * mm, (W - 48 * mm) / 2 - 12 * mm,
          "„Hätte ich um Platz 1 gezockt, hätte ich vielleicht einen niedrigeren Platz gemacht.“", 9.5, CREAM)
    _wrap(c, xr + 6 * mm, y2 + 24 * mm, (W - 48 * mm) / 2 - 12 * mm,
          "Exakt richtig. Im Bounty/ICM ist gesichertes Laddern mehr wert als ein Gamble um den Sieg mit Bust-Risiko. Chip-EV ≠ $-EV.", 8.5, TEAL)
    c.setFillColorRGB(*GOLD); c.rect(0, 0, W, 5, fill=1, stroke=0)
    c.showPage()


def verdict_page(c, rows):
    bg(c)
    text(c, 22 * mm, H - 22 * mm, "VERDIKT & PROFIL", 22, GOLD, "Helvetica-Bold")

    # style-by-depth table
    y = H - 40 * mm
    text(c, 22 * mm, y, "PLAYSTYLE NACH STACK-TIEFE", 12, TEAL, "Helvetica-Bold")
    rowsd = [
        ("Tief (>25 BB)", "Aggressiv, viele Pots, Steal-Raises — 6× in Level 1", "STARK"),
        ("Mittel (12–25 BB)", "Steals + korrekte Pot-Odds-Calls (K3s→Call vs ATo = math. richtig)", "SOLIDE"),
        ("Kurz (5–12 BB)", "Sauberes Push/Fold, Double-ups mit Premiums, Laddering", "STARK"),
        ("Ultra (<3 BB)", "Forced, ausgeblindet mit Trash bei Level-21-Blinds", "UNVERMEIDBAR"),
    ]
    yy = y - 8 * mm
    for label, desc, tag in rowsd:
        panel(c, 22 * mm, yy - 11 * mm, W - 44 * mm, 12 * mm, DARK, 4)
        text(c, 27 * mm, yy - 7 * mm, label, 9.5, GOLD, "Helvetica-Bold")
        text(c, 68 * mm, yy - 7 * mm, desc, 8.5, CREAM)
        tcol = TEAL if tag in ("STARK", "SOLIDE") else MUTE
        text(c, W - 27 * mm, yy - 7 * mm, tag, 8.5, tcol, "Helvetica-Bold", right=True)
        yy -= 14 * mm

    # poker-IQ portrait
    py = yy - 8 * mm
    panel(c, 22 * mm, py - 44 * mm, W - 44 * mm, 44 * mm, FELT2, 8)
    text(c, 30 * mm, py - 10 * mm, "PROFIL: DER GEDULDIGE AKKUMULATOR", 13, GOLD, "Helvetica-Bold")
    _wrap(c, 30 * mm, py - 18 * mm, W - 64 * mm,
          "Du kombinierst aggressives Early-Game-Chip-Accumulation mit disziplinierter, ICM-bewusster Short-Stack-Leiter — ein Turnier-Profil, das TIEF läuft. Deine Push/Fold-Mathematik ist sauber, deine Laddering-Instinkte (A7o-Fold) sind Finaltisch-reif.", 9.5, CREAM)

    # verdict
    vy = py - 60 * mm
    panel(c, 22 * mm, vy - 30 * mm, W - 44 * mm, 30 * mm, DARK, 8)
    c.setFillColorRGB(*GOLD); c.rect(22 * mm, vy - 3, W - 44 * mm, 3, fill=1, stroke=0)
    text(c, 30 * mm, vy - 10 * mm, "EHRLICHES VERDIKT", 11, GOLD, "Helvetica-Bold")
    _wrap(c, 30 * mm, vy - 17 * mm, W - 64 * mm,
          "Stark gespielt. Platz 3 war VARIANZ, kein Fehler — der pivotale AK-vs-KT-Flip verloren, sonst Heads-up. Echte Leaks: keine gefunden. Im Hyper-Turbo ist der Finaltisch by-design eine Lotterie; willst du mehr Skill-Edge → langsamere Strukturen.", 9, CREAM)

    text(c, W / 2, 12 * mm, "Generiert aus 75 Händen · GG Speed Racer Bounty $108 · Princedarkness", 8, MUTE, center=True)
    c.setFillColorRGB(*GOLD); c.rect(0, 0, W, 5, fill=1, stroke=0)
    c.showPage()


def main():
    arc, rows = parse()
    c = canvas.Canvas(OUT, pagesize=A4)
    c.setTitle("Princedarkness — Spieler-Report")
    cover(c, arc, rows)
    run_page(c, arc, rows)
    pivotal_page(c)
    verdict_page(c, rows)
    c.save()
    print("PDF ->", OUT)


if __name__ == "__main__":
    main()
