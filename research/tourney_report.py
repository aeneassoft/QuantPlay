"""Princedarkness tournament player-report -> premium white-background magazine PDF (DE + EN, 2026-07-07).
Canvas-drawn: editorial white layout, bronze/slate accents, dual-scale chip chart, drawn cards, game-theory
page, insights grid, plain-language glossary, verdict. Content enriched via a 5-agent workflow + verify pass
(all verify corrections applied: no "coinflip" mislabels, ICM fold not framed as a foreseen exploit, hand
notation glossed). Run:  python -m research.tourney_report
"""
from __future__ import annotations

import re

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

HH = (r"C:\Users\hampe\Documents\1# Personal Poker Hand Histories + reports"
      r"\GG20260706-2110 - Speed Racer Bounty 108 [10 BB].txt")
OUTDIR = r"C:\Users\hampe\Documents\1# Personal Poker Hand Histories + reports"

# ---- palette: editorial white, bronze + slate accents ----
WHITE  = (1.000, 1.000, 1.000)
INK    = (0.100, 0.100, 0.100)   # warm charcoal main text
GREY   = (0.430, 0.430, 0.430)   # secondary/labels
HAIR   = (0.860, 0.850, 0.820)   # hairline rules
PANEL  = (0.957, 0.949, 0.933)   # pale warm panel
BRONZE = (0.690, 0.480, 0.180)   # accent 1 (trophy / wins / focal)
BRONZET= (0.953, 0.914, 0.847)   # bronze pale tint (area fill)
SLATE  = (0.243, 0.431, 0.447)   # accent 2 (illusion line / ICM)
LOSS   = (0.600, 0.600, 0.600)   # loss/neutral marker
REDC   = (0.698, 0.227, 0.227)   # hearts/diamonds on cards
W, H = A4


# ---------------------------------------------------------------- parse
def parse():
    txt = open(HH, encoding="utf-8").read()
    hands = [h for h in re.split(r"(?=Poker Hand #)", txt) if h.strip().startswith("Poker Hand")][::-1]
    arc = []
    for i, h in enumerate(hands, 1):
        bb = int(re.search(r"Level\d+\([\d,]+/([\d,]+)", h).group(1).replace(",", ""))
        m = re.search(r"Seat \d+: Hero \(([\d,]+) in chips\)", h)
        chips = int(m.group(1).replace(",", "")) if m else 0
        arc.append((i, chips, round(chips / bb, 1)))
    return arc


def numfmt(n, lang):
    s = f"{n:,}"
    return s.replace(",", ".") if lang == "de" else s


# ---------------------------------------------------------------- draw helpers
def bg(c):
    c.setFillColorRGB(*WHITE); c.rect(0, 0, W, H, fill=1, stroke=0)


def text(c, x, y, s, size, col=INK, font="Helvetica", center=False, right=False, track=0.0):
    c.setFillColorRGB(*col); c.setFont(font, size)
    if track:  # manual letter-spacing (this reportlab lacks setCharSpace) — only used for short eyebrow labels
        if right: s2 = s; x -= sum(c.stringWidth(ch, font, size) + track for ch in s2) - track
        cx = x
        for ch in s:
            c.drawString(cx, y, ch); cx += c.stringWidth(ch, font, size) + track
        return
    if center: c.drawCentredString(x, y, s)
    elif right: c.drawRightString(x, y, s)
    else: c.drawString(x, y, s)


def eyebrow(c, x, y, s, col=GREY, size=8, right=False):
    text(c, x, y, s.upper(), size, col, "Helvetica-Bold", track=1.5, right=right)


def hair(c, x1, y, x2, col=HAIR, wpt=0.6):
    c.setStrokeColorRGB(*col); c.setLineWidth(wpt); c.setDash()
    c.line(x1, y, x2, y)


def shadow_panel(c, x, y, w, h, fill=PANEL, radius=5, toprule=None):
    """Soft-lift panel: faint offset copy + fill; optional accent hairline on top edge (magazine card)."""
    c.setFillColorRGB(*HAIR); c.roundRect(x + 1.2, y - 1.2, w, h, radius, fill=1, stroke=0)
    c.setFillColorRGB(*fill); c.roundRect(x, y, w, h, radius, fill=1, stroke=0)
    if toprule:
        c.setStrokeColorRGB(*toprule); c.setLineWidth(1.4); c.line(x + 4, y + h, x + w - 4, y + h)


def wrap(c, x, y, w, s, size, col, lead=None, font="Helvetica"):
    lead = lead or size + 4
    c.setFillColorRGB(*col); c.setFont(font, size)
    line = ""
    for wd in s.split():
        if c.stringWidth(line + " " + wd, font, size) < w:
            line = (line + " " + wd).strip()
        else:
            c.drawString(x, y, line); y -= lead; line = wd
    if line: c.drawString(x, y, line)
    return y - lead


def card(c, x, y, rank, suit, w=15 * mm, h=21 * mm):
    c.setFillColorRGB(*WHITE); c.setStrokeColorRGB(*HAIR); c.setLineWidth(0.8)
    c.roundRect(x, y, w, h, 2.5, fill=1, stroke=1)
    col = REDC if suit in "hd" else INK
    sym = {"h": "♥", "d": "♦", "s": "♠", "c": "♣"}[suit]
    r = {"T": "10"}.get(rank, rank)
    c.setFillColorRGB(*col)
    c.setFont("Helvetica-Bold", 11); c.drawString(x + 2.5, y + h - 11, r)
    c.setFont("Helvetica", 14); c.drawCentredString(x + w / 2, y + h / 2 - 5, sym)
    c.setFont("Helvetica-Bold", 7.5); c.drawRightString(x + w - 2.5, y + 3.5, r)


def hand_cards(c, x, y, cards, scale=1.0):
    for k, p in enumerate(cards.split()):
        card(c, x + k * 17 * mm * scale, y, p[0], p[1], 15 * mm * scale, 21 * mm * scale)


def peak_dot(c, cx, cy, col=BRONZE):
    c.setStrokeColorRGB(*col); c.setLineWidth(1.3); c.setFillColorRGB(*WHITE)
    c.circle(cx, cy, 2.2 * mm, fill=1, stroke=1)
    c.setFillColorRGB(*col); c.circle(cx, cy, 1.0 * mm, fill=1, stroke=0)


def footer(c, lang, pg):
    hair(c, 22 * mm, 13 * mm, W - 22 * mm, HAIR, 0.4)
    rid = "PRINCEDARKNESS · SPIELER-REPORT" if lang == "de" else "PRINCEDARKNESS · PLAYER REPORT"
    text(c, 22 * mm, 9 * mm, rid, 7, GREY, track=1.2)
    text(c, W - 22 * mm, 9 * mm, f"{pg} / 6", 7, GREY, right=True, track=1.0)


# ---------------------------------------------------------------- pages
def cover(c, arc, L, lang, pg):
    bg(c)
    eyebrow(c, 26 * mm, H - 30 * mm, L["eyebrow_report"], GREY, 8.5)
    hair(c, 26 * mm, H - 34 * mm, W - 26 * mm)
    text(c, 26 * mm, H - 58 * mm, "PRINCEDARKNESS", 44, INK, "Helvetica-Bold")
    text(c, 26 * mm, H - 68 * mm, L["cover_sub"], 12.5, GREY)
    # focal podium '3'
    cx, cy = 62 * mm, H - 132 * mm
    c.setStrokeColorRGB(*BRONZE); c.setLineWidth(2.2); c.circle(cx, cy, 30 * mm, fill=0, stroke=1)
    text(c, cx, cy - 14 * mm, "3", 96, BRONZE, "Helvetica-Bold", center=True)
    eyebrow(c, cx, cy + 18 * mm, L["place"], BRONZE, 9)
    # monospace-feel readout
    rx = W - 26 * mm; ry = H - 118 * mm
    for lab, val in L["readout"]:
        eyebrow(c, rx, ry + 5, lab, GREY, 7.5, right=True)
        text(c, rx, ry - 6 * mm, val, 15, INK, "Helvetica-Bold", right=True)
        ry -= 18 * mm
    text(c, 26 * mm, 24 * mm, L["cover_tag"], 12, SLATE, "Helvetica-Oblique")
    footer(c, lang, pg); c.showPage()


def climb_page(c, arc, L, lang, pg):
    bg(c)
    eyebrow(c, 22 * mm, H - 24 * mm, L["eyebrow_report"], GREY, 7.5)
    text(c, 22 * mm, H - 34 * mm, L["climb_h"], 27, INK, "Helvetica-Bold")
    wrap(c, 22 * mm, H - 42 * mm, W - 44 * mm, L["climb_deck"], 12, GREY, 16)
    gx, gy, gw, gh = 24 * mm, H - 150 * mm, W - 48 * mm, 92 * mm
    xs = [a[0] for a in arc]; ys = [a[1] for a in arc]; bbs = [a[2] for a in arc]
    xmax, ymax, bbmax = max(xs), max(ys), max(bbs)
    def px(i): return gx + (i - 1) / (xmax - 1) * gw
    def pyc(v): return gy + v / ymax * (gh - 6 * mm)
    def pyb(v): return gy + v / bbmax * (gh - 6 * mm)
    # gridlines
    for frac in (0.25, 0.5, 0.75, 1.0):
        yy = gy + frac * (gh - 6 * mm); hair(c, gx, yy, gx + gw, HAIR, 0.4)
        text(c, gx - 2 * mm, yy - 2, f"{int(ymax*frac/1000)}k", 6.5, GREY, right=True)
    # chip area (bronze tint)
    p = c.beginPath(); p.moveTo(px(1), gy)
    for i, v in zip(xs, ys): p.lineTo(px(i), pyc(v))
    p.lineTo(px(xs[-1]), gy); p.close()
    c.setFillColorRGB(*BRONZET); c.drawPath(p, fill=1, stroke=0)
    c.setStrokeColorRGB(*BRONZE); c.setLineWidth(2.0)
    pc = c.beginPath(); pc.moveTo(px(1), pyc(ys[0]))
    for i, v in zip(xs, ys): pc.lineTo(px(i), pyc(v))
    c.drawPath(pc, stroke=1, fill=0)
    # big-blind line (slate, own scale -> visually falls)
    c.setStrokeColorRGB(*SLATE); c.setLineWidth(1.2); c.setDash(3, 2)
    pb = c.beginPath(); pb.moveTo(px(1), pyb(bbs[0]))
    for i, v in zip(xs, bbs): pb.lineTo(px(i), pyb(v))
    c.drawPath(pb, stroke=1, fill=0); c.setDash()
    # peak + events
    peak = max(arc, key=lambda a: a[1])
    peak_dot(c, px(peak[0]), pyc(peak[1]))
    text(c, px(peak[0]) - 2 * mm, pyc(peak[1]) + 6 * mm, L["peak_call"], 8, BRONZE, "Helvetica-Bold", right=True)
    for hx, lab, col in ((71, L["flag71"], BRONZE), (75, L["flag75"], LOSS)):
        c.setStrokeColorRGB(*col); c.setLineWidth(0.6); c.setDash(1, 2)
        c.line(px(hx), gy, px(hx), pyc(ys[hx - 1]) if hx <= len(ys) else gy); c.setDash()
        c.setFillColorRGB(*col); c.circle(px(hx), gy, 1.1 * mm, fill=1, stroke=0)
    # series legend
    text(c, gx + 3 * mm, gy + gh - 1 * mm, L["series_chips"], 8, BRONZE, "Helvetica-Bold")
    text(c, gx + 3 * mm, gy + gh - 6 * mm, L["series_bb"], 8, SLATE, "Helvetica-Bold")
    text(c, gx + gw / 2, gy - 6 * mm, L["run_axis"], 8, GREY, center=True)
    # blind ramp strip
    ry = gy - 24 * mm
    text(c, gx, ry + 6 * mm, L["ramp_cap"], 8, GREY)
    for k in range(21):
        bx = gx + k * (gw / 21); bh = 2 * mm + (k / 20) * 10 * mm
        c.setFillColorRGB(*(BRONZE if k >= 18 else HAIR)); c.rect(bx, ry, gw / 21 - 1.2, bh, fill=1, stroke=0)
    # illusion callout — in the open space below the chart (decluttered from the plot)
    iy = ry - 40 * mm
    hair(c, 22 * mm, iy + 16 * mm, W - 22 * mm, SLATE, 0.8)
    eyebrow(c, 22 * mm, iy + 10 * mm, L["illusion_eyebrow"], SLATE, 8.5)
    wrap(c, 22 * mm, iy + 2 * mm, W - 44 * mm, L["illusion"], 11.5, INK, 16)
    footer(c, lang, pg); c.showPage()


def gametheory_page(c, L, lang, pg):
    bg(c)
    eyebrow(c, 22 * mm, H - 24 * mm, L["eyebrow_report"], GREY, 7.5)
    text(c, 22 * mm, H - 34 * mm, L["gt_h"], 26, INK, "Helvetica-Bold")
    wrap(c, 22 * mm, H - 42 * mm, W - 44 * mm, L["gt_deck"], 12, GREY, 16)
    y = H - 54 * mm
    for name, plain, applies, tag in L["gt_dims"]:
        hair(c, 22 * mm, y, W - 22 * mm, HAIR, 0.5)
        text(c, 22 * mm, y - 7 * mm, name, 12.5, INK, "Helvetica-Bold")
        eyebrow(c, W - 22 * mm, y - 6.5 * mm, tag, BRONZE, 7.5, right=True)
        yy = wrap(c, 22 * mm, y - 13 * mm, W - 44 * mm, plain, 9.3, GREY, 12, "Helvetica-Oblique")
        wrap(c, 22 * mm, yy + 1 * mm, W - 44 * mm, applies, 9.3, INK, 12)
        y -= 37.5 * mm
    footer(c, lang, pg); c.showPage()


def hands_page(c, L, lang, pg):
    bg(c)
    eyebrow(c, 22 * mm, H - 24 * mm, L["eyebrow_report"], GREY, 7.5)
    text(c, 22 * mm, H - 34 * mm, L["hands_h"], 26, INK, "Helvetica-Bold")
    wrap(c, 22 * mm, H - 42 * mm, W - 44 * mm, L["hands_deck"], 12, GREY, 16)
    # panel 1: the fold that paid
    y1 = H - 128 * mm
    shadow_panel(c, 22 * mm, y1, W - 44 * mm, 74 * mm, PANEL, 6, SLATE)
    text(c, 30 * mm, y1 + 64 * mm, L["fold_h"], 13, SLATE, "Helvetica-Bold")
    text(c, 30 * mm, y1 + 56 * mm, L["fold_sub"], 9.5, INK, "Helvetica-Bold")
    hand_cards(c, 30 * mm, y1 + 26 * mm, "Ac 7d", 0.85)
    text(c, 30 * mm, y1 + 20 * mm, L["fold_folds"], 8, GREY)
    wrap(c, 74 * mm, y1 + 48 * mm, W - 74 * mm - 26 * mm, L["fold_body"], 9.3, INK, 12.5)
    text(c, 30 * mm, y1 + 9 * mm, L["fold_result"], 12, BRONZE, "Helvetica-Bold")
    # panel 2: the favorite that lost
    y2 = y1 - 84 * mm
    shadow_panel(c, 22 * mm, y2, W - 44 * mm, 76 * mm, PANEL, 6, BRONZE)
    text(c, 30 * mm, y2 + 66 * mm, L["fav_h"], 13, BRONZE, "Helvetica-Bold")
    text(c, 30 * mm, y2 + 59 * mm, L["fav_sub"], 9.5, INK, "Helvetica-Bold")
    # probability split bar 70/30
    bx, by, bw, bh = 30 * mm, y2 + 40 * mm, W - 60 * mm, 9 * mm
    c.setFillColorRGB(*BRONZE); c.roundRect(bx, by, bw * 0.70, bh, 2, fill=1, stroke=0)
    c.setFillColorRGB(*LOSS); c.roundRect(bx + bw * 0.70, by, bw * 0.30, bh, 2, fill=1, stroke=0)
    text(c, bx + 3 * mm, by + 2.6 * mm, L["fav_you"], 8.5, WHITE, "Helvetica-Bold")
    text(c, bx + bw - 3 * mm, by + 2.6 * mm, L["fav_vill"], 8.5, WHITE, "Helvetica-Bold", right=True)
    # hole cards + board
    text(c, 30 * mm, y2 + 32 * mm, L["board"], 8.5, GREY)
    hand_cards(c, 47 * mm, y2 + 22 * mm, "7s 5h Tc 5s 9h", 0.58)
    text(c, 30 * mm, y2 + 8 * mm, L["fav_result"], 10.5, INK, "Helvetica-Bold")
    footer(c, lang, pg); c.showPage()


def insights_page(c, L, lang, pg):
    bg(c)
    eyebrow(c, 22 * mm, H - 24 * mm, L["eyebrow_report"], GREY, 7.5)
    text(c, 22 * mm, H - 34 * mm, L["ins_h"], 26, INK, "Helvetica-Bold")
    # 2x3 stat cards
    cw, ch = (W - 44 * mm - 12 * mm) / 3, 40 * mm
    x0, y0 = 22 * mm, H - 96 * mm
    for k, (lab, fig, line, accent) in enumerate(L["ins_cards"]):
        cx = x0 + (k % 3) * (cw + 6 * mm); cy = y0 - (k // 3) * (ch + 8 * mm)
        c.setStrokeColorRGB(*(BRONZE if accent else HAIR)); c.setLineWidth(1.4 if accent else 0.6)
        c.line(cx, cy + ch, cx + cw, cy + ch)
        eyebrow(c, cx, cy + ch - 8 * mm, lab, GREY, 7.5)
        text(c, cx, cy + ch - 22 * mm, fig, 34, BRONZE if accent else INK, "Helvetica-Bold")
        wrap(c, cx, cy + ch - 28 * mm, cw - 2 * mm, line, 8.6, GREY, 11)
    # all-in ledger motif
    ly = y0 - (ch + 8 * mm) - 18 * mm
    eyebrow(c, 22 * mm, ly + 8 * mm, L["ledger_cap"], GREY, 7.5)
    seq = ["w"] * 12 + ["l"] * 3 + ["o"] * 2
    for k, s in enumerate(seq):
        sx = 22 * mm + k * 8.5 * mm
        if s == "w": c.setFillColorRGB(*BRONZE); c.roundRect(sx, ly, 6.2 * mm, 6.2 * mm, 1, fill=1, stroke=0)
        elif s == "l": c.setFillColorRGB(*LOSS); c.roundRect(sx, ly, 6.2 * mm, 6.2 * mm, 1, fill=1, stroke=0)
        else:
            c.setStrokeColorRGB(*HAIR); c.setLineWidth(0.8); c.roundRect(sx, ly, 6.2 * mm, 6.2 * mm, 1, fill=0, stroke=1)
    footer(c, lang, pg); c.showPage()


def glossary_verdict_page(c, L, lang, pg):
    bg(c)
    eyebrow(c, 22 * mm, H - 24 * mm, L["eyebrow_report"], GREY, 7.5)
    text(c, 22 * mm, H - 34 * mm, L["glo_h"], 24, INK, "Helvetica-Bold")
    text(c, 22 * mm, H - 41 * mm, L["glo_deck"], 11, GREY)
    # glossary two-column panel
    gy = H - 135 * mm
    shadow_panel(c, 22 * mm, gy, W - 44 * mm, 90 * mm, PANEL, 6)
    col_w = (W - 44 * mm - 16 * mm) / 2
    half = (len(L["glossary"]) + 1) // 2
    for ci, group in enumerate((L["glossary"][:half], L["glossary"][half:])):
        gx = 30 * mm + ci * (col_w + 8 * mm); yy = gy + 82 * mm
        for term, dfn in group:
            text(c, gx, yy, term, 9.2, INK, "Helvetica-Bold")
            yy = wrap(c, gx, yy - 5 * mm, col_w, dfn, 8.2, GREY, 10)
            yy -= 2.5 * mm
    # verdict
    vy = gy - 12 * mm
    eyebrow(c, 22 * mm, vy, L["verd_eyebrow"], BRONZE, 8.5)
    yq = wrap(c, 22 * mm, vy - 9 * mm, W - 44 * mm, L["pullquote"], 19, INK, 24, "Helvetica-Bold")
    yb = wrap(c, 22 * mm, yq - 3 * mm, W - 44 * mm, L["verd_body"], 10.2, INK, 14.5)
    hair(c, 22 * mm, yb + 2 * mm, W - 22 * mm)
    text(c, 22 * mm, yb - 6 * mm, L["signature"], 12, BRONZE, "Helvetica-Oblique")
    footer(c, lang, pg); c.showPage()


def build(lang):
    L = LANG[lang]; arc = parse()
    out = OUTDIR + "\\" + L["file"]
    c = canvas.Canvas(out, pagesize=A4); c.setTitle(L["title"])
    cover(c, arc, L, lang, 1)
    climb_page(c, arc, L, lang, 2)
    gametheory_page(c, L, lang, 3)
    hands_page(c, L, lang, 4)
    insights_page(c, L, lang, 5)
    glossary_verdict_page(c, L, lang, 6)
    c.save(); print("PDF ->", out)


def main():
    for lang in ("de", "en"):
        build(lang)


# ================================================================ CONTENT (DE + EN)
LANG = {
"de": {
    "file": "Princedarkness_Spieler-Report_DE.pdf", "title": "Princedarkness — Spieler-Report",
    "eyebrow_report": "Turnier-Spielerbericht",
    "cover_sub": "GG Poker — Speed Racer Bounty — $108 Hyper-Turbo — 2026-07-07",
    "place": "Platz", "cover_tag": "Ein starker Deep-Run — entschieden durch eine unglückliche Hand, nicht durch einen Fehler.",
    "readout": [("Platzierung", "3. im Feld"), ("Preisgeld", "~$1.200"), ("Chip-Wachstum", "47×"), ("All-in-Bilanz", "12–3")],
    "climb_h": "Der Aufstieg",
    "climb_deck": "Von 10.000 auf 470.592 Chips — ein 47-facher Aufstieg — bis die Blinds den Tisch verschluckten.",
    "peak_call": "470.592 · Chip-Leader",
    "series_chips": "— echte Chips (steigend)", "series_bb": "- - Big Blinds (fallend)",
    "illusion_eyebrow": "Die Big-Blind-Illusion",
    "illusion": "In „Big Blinds\" gemessen sieht es aus wie ein Absturz (64 → 5). Das ist eine Illusion: die Blinds (die erzwungenen Einsätze) stiegen schneller, als jeder Chips sammeln konnte — in echten Chips bist du fast durchgehend gestiegen.",
    "run_axis": "Hand 1  →  Hand 75",
    "flag71": "Hand 71 — das Ass-König", "flag75": "Hand 75 — raus",
    "ramp_cap": "Blind-Level 1 → 21 · die Zwangseinsätze steigen alle paar Minuten",
    "gt_h": "Dein Spiel — spieltheoretisch",
    "gt_deck": "Sechs Blickwinkel darauf, WIE du gespielt hast — jeder Fachbegriff in Klartext erklärt.",
    "gt_dims": [
        ("Erwartungswert", "Das Durchschnittsergebnis, wenn man eine Entscheidung tausendmal wiederholen könnte — gute Spieler wählen den besten Langzeit-Schnitt, auch wenn ein einzelner Versuch schiefgehen kann.",
         "Du bist mit starken Händen all-in gegangen (Paare und große Ass/König-Hände — z.B. TT = ein Paar Zehnen, KhQh = König-Dame derselben Farbe) statt mit Schrott — solide, vernünftige Hände bei diesen kurzen Stacks.", "Hervorragend"),
        ("Varianz (das Glück)", "Selbst eine perfekte Entscheidung verliert manchmal — Varianz ist die Lücke zwischen dem, was du im Schnitt verdienst, und dem, was dieses eine Mal passiert.",
         "Alles hing an Hand 71: all-in mit Ass-König (~70% Gewinnchance), gecallt von König-Zehn, das Board machte den Gegner zu zwei Paar. Ein DOMINIERENDER Favorit, der verlor — kein Coinflip, sondern schlicht Pech.", "Ehrlich erkannt"),
        ("Das Geldmodell (ICM)", "Chips sind kein Bargeld — weil höhere Platzierungen mehr zahlen, kann Überleben mehr wert sein als um mehr Chips zu zocken.",
         "Hand 70: du foldest Ass-Sieben am Button. Dann gingen die zwei anderen gegeneinander all-in, einer bustete — du bist eine Auszahlungsstufe hochgeklettert, ohne eigenes Risiko. Genau das Turnier-Geld-Kalkül.", "Klug"),
        ("Short-Stack: All-in oder Fold", "Bei winzigem Stack (wenige Big Blinds) schrumpft das Spiel auf zwei Optionen — alles reinschieben oder folden — mit einer mathematisch standardisierten Liste, welche Hände man shovt.",
         "Der ganze Finaltisch lag bei ~4–10 Big Blinds — die klassische Push/Fold-Zone. Dein Profil (viele All-ins, kaum unklare Mini-Pots) passt exakt: du warst im richtigen „Gang\".", "Richtiger Gang"),
        ("Überleben (Ruin-Risiko)", "„Ruin-Risiko\" ist die Gefahr, alles zu verlieren — die Balance zwischen Chips sammeln und nicht dein ganzes Turnier auf einen dünnen Vorteil zu setzen.",
         "Aggressiv genug, um von 10.000 auf 470.592 Chips (Chip-Leader) zu wachsen, aber selektiv genug, um Platz 3 zu erreichen. Selbst der K3s-Verlust (König-Drei derselben Farbe) war ein mathematisch korrekter Call zum gebotenen Preis.", "Gut austariert"),
        ("Ausbalanciert vs anpassend", "„Ausbalanciert\" heißt eine Lehrbuch-Basis, die schwer auszunutzen ist; „anpassend\" heißt, sie zu beugen, um die konkreten Fehler der Gegner zu bestrafen.",
         "Short-stacked gibt es wenig Spielraum zum Ausmanövrieren — du lagst nahe der gelösten „All-in oder Fold\"-Basis (ICM und mehrere Spieler machen einen Finaltisch komplexer als eine saubere Lösung). Mehr Edge bräuchte langsamere, tiefere Strukturen.", "Solide"),
    ],
    "hands_h": "Die zwei Hände, die es entschieden",
    "hands_deck": "Spät im Turnier verlieren Chips ihren Nennwert. Manchmal bringt Folden mehr Geld als den Pot zu gewinnen.",
    "fold_h": "Der Fold, der sich auszahlte", "fold_sub": "Hand 70 · du foldest Ass-Sieben am Button (~4,7 BB)",
    "fold_folds": "du foldest",
    "fold_body": "Danach gingen die zwei anderen Spieler gegeneinander all-in (Neun-Vier vs König-Bube) und einer schied aus. Indem du beiseite tratst und die Gegner aufeinander losgehen ließt, bist du eine Auszahlungsstufe hochgeklettert — ohne eigenes Risiko.",
    "fold_result": "= +$200 (Platz 3 statt 4)",
    "fav_h": "Der Favorit, der verlor", "fav_sub": "Hand 71 · all-in mit Ass-König als Chip-Leader",
    "fav_you": "A♦K♣ — 70% Gewinnchance", "fav_vill": "K♠10♦ überholt — 30%",
    "board": "Board:", "fav_result": "Ein 70%-Favorit — und verloren. Reine Varianz (Pech), kein Fehler.",
    "ins_h": "Was die Zahlen zeigen",
    "ins_cards": [
        ("All-in-Duelle", "12–3", "Chips vorne reingebracht — vier von fünf gewonnen.", True),
        ("Freiwillig gespielt", "38%", "Selektiv, nicht wild — er hat seine Spots gewählt.", False),
        ("Chip-Wachstum", "47×", "Vom 10-Big-Blind-Short-Stack zum Chip-Leader.", False),
        ("Entscheidende Marge", "1 Hand", "Platz 3 vs Sieg hing an einem verlorenen 70/30-Favoriten.", True),
        ("Double-ups", "6+", "Überlebt mit 66, TT, KhQh, QJs, ATo, A7s (Verdoppeln des Stacks).", False),
        ("Disziplin", "✓", "Selbst der K3s-Verlust war ein mathematisch korrekter Call.", False),
    ],
    "ledger_cap": "All-in-Bilanz — 12 gewonnen · 3 verloren · 2 gefoldet",
    "glo_h": "In Klartext", "glo_deck": "Die paar Poker-Begriffe aus diesem Bericht — in Alltagssprache.",
    "glossary": [
        ("Big Blind", "Der größere der zwei Zwangseinsätze vor dem Austeilen; zugleich die Maßeinheit für Stackgröße."),
        ("Ante", "Ein kleiner Zwangsbeitrag von jedem Spieler pro Hand, der den Pot vergrößert und das Spiel beschleunigt."),
        ("All-in", "Alle Chips auf eine Hand setzen; man kann nicht mehr rausgedrängt werden, aber bei Verlust ausscheiden."),
        ("All-in oder Fold", "Ein Endspiel mit so kurzen Stacks, dass nur zwei Optionen bleiben: alles rein oder aufgeben."),
        ("Bounty", "Eine Bargeldprämie fürs Ausschalten eines bestimmten Spielers."),
        ("Hyper-Turbo", "Ein sehr schnelles Turnierformat, in dem die Zwangseinsätze alle paar Minuten steigen."),
        ("ICM (Geldmodell)", "Die Mathematik, wie Turnier-Chips zu echtem Geld werden; höher platzieren zahlt mehr, also lohnt Überleben."),
        ("Coinflip", "Ein All-in, bei dem beide Hände etwa 50/50 stehen — reines Glück entscheidet."),
        ("Favorit", "Die Hand mit der höheren Gewinnchance; ein 70%-Favorit verliert dennoch etwa 3 von 10 Mal."),
        ("Dominiert", "Eine Hand, die eine Karte mit einer stärkeren teilt und klar hinten liegt — wie König-Zehn gegen Ass-König."),
    ],
    "verd_eyebrow": "Das Fazit",
    "pullquote": "Platz 3 — entschieden durch eine unglückliche Hand, nicht durch einen einzigen Fehler.",
    "verd_body": "Stark und selektiv gespielt: 12 von 15 erzwungenen All-in-Duellen gewonnen, weil du deine Chips vorne reinbrachtest. Der Ass-König-Verlust als 70%-Favorit ist Varianz, die jeder starke Spieler akzeptiert. Ehrlich: ein Hyper-Turbo ist am Finaltisch bauartbedingt eine Lotterie — dein Instinkt, für den Auszahlungssprung zu folden (Hand 70), zeigt echtes Turnier-Geld-Können. Für mehr Skill-Edge geben langsamere Strukturen mehr Raum.",
    "signature": "„Platz 3 statt 4 hat mir $200 eingebracht.\"",
},
"en": {
    "file": "Princedarkness_Player-Report_EN.pdf", "title": "Princedarkness — Player Report",
    "eyebrow_report": "Tournament Player Report",
    "cover_sub": "GG Poker — Speed Racer Bounty — $108 Hyper-Turbo — 2026-07-07",
    "place": "Place", "cover_tag": "A strong deep run — decided by one unlucky hand, not by a single mistake.",
    "readout": [("Finish", "3rd of field"), ("Prize", "~$1,200"), ("Chip growth", "47×"), ("All-in record", "12–3")],
    "climb_h": "The Climb",
    "climb_deck": "From 10,000 to 470,592 chips — a 47× climb — until the blinds swallowed the room.",
    "peak_call": "470,592 · chip leader",
    "series_chips": "— real chips (rising)", "series_bb": "- - big blinds (falling)",
    "illusion_eyebrow": "The big-blind illusion",
    "illusion": "Measured in \"big blinds\" it looks like a fall (64 → 5). That is an illusion: the blinds (the forced bets) rose faster than anyone could accumulate chips — in real chips you climbed almost the whole way.",
    "run_axis": "Hand 1  →  Hand 75",
    "flag71": "Hand 71 — the Ace-King", "flag75": "Hand 75 — out",
    "ramp_cap": "Blind levels 1 → 21 · the forced bets rise every few minutes",
    "gt_h": "Your Game, in Game-Theory Terms",
    "gt_deck": "Six lenses on HOW you played — every technical term explained in plain words.",
    "gt_dims": [
        ("Expected value", "The average result if you could replay a decision a thousand times — good players chase the best long-run average, even when a single try can go badly.",
         "You committed with strong hands (pairs and big ace/king holdings — e.g. TT = a pair of tens, KhQh = King-Queen of the same suit), not trash — strong, reasonable hands to commit at these short stacks.", "Excellent"),
        ("Variance (the luck)", "Even a perfect decision loses sometimes — variance is the gap between what you deserve on average and what happens this one time.",
         "It all turned on hand 71: all-in with Ace-King (~70% to win), called by King-Ten, and the board made the opponent two pair. A DOMINATING favorite that lost — not a coinflip, just bad luck.", "Read honestly"),
        ("The money model (ICM)", "Chips aren't cash — because higher finishes pay more, surviving can be worth more than gambling for more chips.",
         "Hand 70: you folded Ace-Seven on the button. The other two then went all-in against each other and one busted — you climbed a pay jump at no risk to yourself. Exactly the tournament-money logic.", "Sophisticated"),
        ("Short-stack shove-or-fold", "With a tiny stack (a few big blinds) the game shrinks to two choices — push everything in or fold — with a mathematically standard list of which hands to shove.",
         "The whole final table sat at ~4–10 big blinds — the classic push/fold zone. Your profile (many all-ins, few messy small pots) fits exactly: you were in the right \"gear\".", "Correct gear"),
        ("Survival (risk of ruin)", "\"Risk of ruin\" is the chance you go broke — the balance between grabbing chips and not staking your whole tournament on a thin edge.",
         "Aggressive enough to grow from 10,000 to 470,592 chips (chip leader), yet selective enough to reach 3rd. Even the K3s loss (King-Three of the same suit) was a mathematically correct call at the price offered.", "Well-calibrated"),
        ("Balanced vs adaptive", "\"Balanced\" means a textbook baseline that is hard to exploit; \"adaptive\" means bending it to punish opponents' specific mistakes.",
         "Short-stacked, there's little room to out-maneuver — you sat near the solved \"shove-or-fold\" baseline (ICM and multiple players make a final table more complex than a clean solution). More edge would need slower, deeper structures.", "Solid"),
    ],
    "hands_h": "The Two Hands That Decided It",
    "hands_deck": "Late in a tournament, chips stop being worth their face value. Sometimes folding earns more money than winning the pot.",
    "fold_h": "The fold that paid", "fold_sub": "Hand 70 · you fold Ace-Seven on the button (~4.7 BB)",
    "fold_folds": "you fold",
    "fold_body": "Then the other two players went all-in against each other (Nine-Four vs King-Jack) and one was eliminated. By stepping aside and letting your rivals clash, you climbed a pay jump — at no risk to yourself.",
    "fold_result": "= +$200 (3rd over 4th)",
    "fav_h": "The favorite that lost", "fav_sub": "Hand 71 · all-in with Ace-King as chip leader",
    "fav_you": "A♦K♣ — 70% to win", "fav_vill": "K♠10♦ catches up — 30%",
    "board": "Board:", "fav_result": "A 70% favorite — and lost. Pure variance (bad luck), not a mistake.",
    "ins_h": "What the Numbers Show",
    "ins_cards": [
        ("All-in showdowns", "12–3", "Got the chips in ahead — won four of every five.", True),
        ("Hands played by choice", "38%", "Selective, not reckless — he picked his spots.", False),
        ("Chip growth", "47×", "From a 10-big-blind short stack to chip leader.", False),
        ("Deciding margin", "1 hand", "3rd vs the win came down to one lost 70/30 favorite.", True),
        ("Double-ups", "6+", "Survived with 66, TT, KhQh, QJs, ATo, A7s (doubling the stack).", False),
        ("Discipline", "✓", "Even the K3s loss was a mathematically correct call.", False),
    ],
    "ledger_cap": "All-in ledger — 12 won · 3 lost · 2 folded",
    "glo_h": "In Plain Words", "glo_deck": "The handful of poker terms in this report — in everyday language.",
    "glossary": [
        ("Big blind", "The larger of two forced bets posted before the deal; also the standard unit for measuring stack size."),
        ("Ante", "A small forced payment from every player each hand that grows the pot and speeds up the action."),
        ("All-in", "Betting every chip on one hand; you can't be pushed off it, but you can be knocked out if you lose."),
        ("Shove-or-fold", "An endgame with such short stacks that the only sensible choices are all-in or give up the hand."),
        ("Bounty", "A cash reward for knocking a specific player out of the tournament."),
        ("Hyper-turbo", "A very fast tournament format where the forced bets rise every few minutes."),
        ("ICM (payout model)", "The math of how tournament chips turn into real money; finishing higher pays more, so survival has value."),
        ("Coinflip", "An all-in where both hands are close to 50/50, so the outcome is basically luck."),
        ("Favorite", "The hand more likely to win; a 70% favorite still loses about 3 times in 10."),
        ("Dominated", "A hand that shares a card with a stronger one and is a big underdog — like King-Ten against Ace-King."),
    ],
    "verd_eyebrow": "The Verdict",
    "pullquote": "Third place — decided by one unlucky hand, not by a single mistake.",
    "verd_body": "Played strongly and selectively: won 12 of 15 forced all-ins because you got your chips in ahead. The Ace-King loss as a 70% favorite is variance every strong player accepts. Honestly: a hyper-turbo is a lottery at the final table by design — your instinct to fold for the pay jump (hand 70) shows genuine tournament-money skill. To express more edge, slower structures give more room.",
    "signature": "“Coming 3rd instead of 4th earned me $200.”",
},
}


if __name__ == "__main__":
    main()
