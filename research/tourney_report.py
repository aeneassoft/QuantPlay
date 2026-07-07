"""Princedarkness tournament player-report -> a white-on-black PDF with colored graphics (2026-07-07).
Canvas-drawn (no matplotlib): black background, white text, colored chip-arc + cards. DE + EN versions.
Run:  python -m research.tourney_report
"""
from __future__ import annotations

import re

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

HH = (r"C:\Users\hampe\Documents\1# Personal Poker Hand Histories + reports"
      r"\GG20260706-2110 - Speed Racer Bounty 108 [10 BB].txt")
OUTDIR = r"C:\Users\hampe\Documents\1# Personal Poker Hand Histories + reports"

# ---- palette: DARK ON WHITE, colored accents ----
BG         = (1.000, 1.000, 1.000)   # white background
INK        = (0.130, 0.140, 0.170)   # dark main text
CREAM      = INK                     # legacy alias: "main text" is dark ink on white
CARD       = (1.000, 1.000, 1.000)   # card face (bordered)
CARDBORDER = (0.780, 0.790, 0.820)
PANEL      = (0.960, 0.963, 0.972)   # very light gray panels
PANEL2     = (0.928, 0.933, 0.947)
GRID       = (0.860, 0.870, 0.890)
GOLD       = (0.820, 0.620, 0.120)
REDC       = (0.820, 0.240, 0.190)   # hearts/diamonds
MUTE       = (0.450, 0.460, 0.500)
TEAL       = (0.055, 0.560, 0.460)

W, H = A4

# ---------------------------------------------------------------- i18n
LANG = {
    "de": {
        "kicker": "SPIELER-REPORT",
        "subtitle": "Speed Racer Bounty  $108  ·  7-max Hyper-Turbo  ·  2026-07-07",
        "place": "PLATZ", "buyin": "Buy-in", "won": "Gewonnen", "icm_money": "ICM: Platz 3 statt 4",
        "cover_stat": "{a}  →  {b} Chips  (47×)  ·  75 Hände  ·  Chip-Leader am Finaltisch",
        "cover_tag": "Ein starker Deep-Run — entschieden von einem einzigen Flip.",
        "run_h": "DER RUN",
        "run_sub": "Chip-Verlauf über 75 Hände — in ECHTEN Chips (nicht BB) gestiegen bis zum Peak.",
        "peak": "PEAK", "bust": "BUST",
        "run_axis": "Hand 1  →  Hand 75   (die Blinds explodierten schneller als jeder akkumulieren konnte — der 'BB-Verfall' war eine Hyper-Illusion)",
        "b1_t": "AKKUMULATION", "b1_b": "Von 10 BB auf ~470k — fast monoton gestiegen. Aggressives Early-Game (JhTh, KsJs, JsAs), 6× in Level 1.",
        "b2_t": "DER HYPER-DRUCK", "b2_b": "Level 1 → 21: Blinds bis 60k/120k + 18k Ante. Am Finaltisch hatte JEDER nur 4–10 BB — Shove/Fold-Territorium.",
        "b3_t": "DIE LEITER", "b3_b": "Als Short Stack diszipliniert gelaufen: Double-ups mit 66, TT, KhQh, QdJs — von ~8 BB durch 40 Hände bis Platz 3.",
        "piv_h": "WARUM PLATZ 3 — EIN FLIP",
        "piv_sub": "Am Shove/Fold-Finaltisch (alle ~5 BB) entscheidet ein Coinflip über Platz 1 vs 3.",
        "keyhand": "DIE SCHLÜSSELHAND  ·  Hand 71  ·  Level 20  ·  ~4,6 BB",
        "you": "DU (all-in)", "you_eq": "Dominierend: ~70% Equity", "caller": "CALLER",
        "vill_eq": "~30% — aber floppt Paar", "board": "Board:",
        "vill_res": "→ Villain: two pair", "ak_lose": "AK verliert.",
        "icm_h": "ICM-MEISTERSCHAFT", "icm_hand": "Hand 70 · du foldest A7o am Button (4,7 BB)",
        "icm_body": "Danach clashen SB (94s) und BB (KJo) all-in — einer bustet. Du lässt die anderen aufeinander los und LADDERST. Genau die Bounty/ICM-Logik.",
        "icm_result": "= +$200 (Platz 3 statt 4)",
        "insight_h": "DEINE EIGENE ERKENNTNIS",
        "insight_q": "„Hätte ich um Platz 1 gezockt, hätte ich vielleicht einen niedrigeren Platz gemacht.“",
        "insight_b": "Exakt richtig. Im Bounty/ICM ist gesichertes Laddern mehr wert als ein Gamble um den Sieg mit Bust-Risiko. Chip-EV ≠ $-EV.",
        "ver_h": "VERDIKT & PROFIL", "depth_h": "PLAYSTYLE NACH STACK-TIEFE",
        "d1": ("Tief (>25 BB)", "Aggressiv, viele Pots, Steal-Raises — 6× in Level 1", "STARK"),
        "d2": ("Mittel (12–25 BB)", "Steals + korrekte Pot-Odds-Calls (K3s→Call vs ATo = math. richtig)", "SOLIDE"),
        "d3": ("Kurz (5–12 BB)", "Sauberes Push/Fold, Double-ups mit Premiums, Laddering", "STARK"),
        "d4": ("Ultra (<3 BB)", "Forced, ausgeblindet mit Trash bei Level-21-Blinds", "UNVERMEIDBAR"),
        "prof_h": "PROFIL: DER GEDULDIGE AKKUMULATOR",
        "prof_b": "Du kombinierst aggressives Early-Game-Chip-Accumulation mit disziplinierter, ICM-bewusster Short-Stack-Leiter — ein Turnier-Profil, das TIEF läuft. Deine Push/Fold-Mathematik ist sauber, deine Laddering-Instinkte (A7o-Fold) sind Finaltisch-reif.",
        "verd_h": "EHRLICHES VERDIKT",
        "verd_b": "Stark gespielt. Platz 3 war VARIANZ, kein Fehler — der pivotale AK-vs-KT-Flip verloren, sonst Heads-up. Echte Leaks: keine gefunden. Im Hyper-Turbo ist der Finaltisch by-design eine Lotterie; willst du mehr Skill-Edge → langsamere Strukturen.",
        "footer": "Generiert aus 75 Händen · GG Speed Racer Bounty $108 · Princedarkness",
        "file": "Princedarkness_Spieler-Report_DE.pdf", "title": "Princedarkness — Spieler-Report",
    },
    "en": {
        "kicker": "PLAYER REPORT",
        "subtitle": "Speed Racer Bounty  $108  ·  7-max Hyper-Turbo  ·  2026-07-07",
        "place": "PLACE", "buyin": "Buy-in", "won": "Won", "icm_money": "ICM: 3rd over 4th",
        "cover_stat": "{a}  →  {b} chips  (47×)  ·  75 hands  ·  chip leader at the final table",
        "cover_tag": "A strong deep run — decided by a single flip.",
        "run_h": "THE RUN",
        "run_sub": "Chip trajectory over 75 hands — climbing in REAL chips (not BB) up to the peak.",
        "peak": "PEAK", "bust": "BUST",
        "run_axis": "Hand 1  →  Hand 75   (blinds exploded faster than anyone could accumulate — the 'BB decline' was a hyper illusion)",
        "b1_t": "ACCUMULATION", "b1_b": "From 10 BB to ~470k — a nearly monotonic climb. Aggressive early game (JhTh, KsJs, JsAs), 6× in Level 1.",
        "b2_t": "THE HYPER PRESSURE", "b2_b": "Level 1 → 21: blinds up to 60k/120k + 18k ante. At the final table EVERYONE had only 4–10 BB — shove/fold territory.",
        "b3_t": "THE LADDER", "b3_b": "Disciplined short-stack play: double-ups with 66, TT, KhQh, QdJs — from ~8 BB through 40 hands to 3rd place.",
        "piv_h": "WHY 3RD — A SINGLE FLIP",
        "piv_sub": "At the shove/fold final table (all ~5 BB) one coinflip decides 1st vs 3rd.",
        "keyhand": "THE KEY HAND  ·  Hand 71  ·  Level 20  ·  ~4.6 BB",
        "you": "YOU (all-in)", "you_eq": "Dominating: ~70% equity", "caller": "CALLER",
        "vill_eq": "~30% — but flops a pair", "board": "Board:",
        "vill_res": "→ Villain: two pair", "ak_lose": "AK loses.",
        "icm_h": "ICM MASTERY", "icm_hand": "Hand 70 · you fold A7o on the button (4.7 BB)",
        "icm_body": "Then SB (94s) and BB (KJo) clash all-in — one busts. You let the others collide and LADDER up. Exactly the bounty/ICM logic.",
        "icm_result": "= +$200 (3rd over 4th)",
        "insight_h": "YOUR OWN INSIGHT",
        "insight_q": "“If I'd gambled for 1st, I might have finished lower.”",
        "insight_b": "Exactly right. In bounty/ICM, securing the ladder is worth more than gambling for the win with bust risk. Chip-EV ≠ $-EV.",
        "ver_h": "VERDICT & PROFILE", "depth_h": "PLAYSTYLE BY STACK DEPTH",
        "d1": ("Deep (>25 BB)", "Aggressive, many pots, steal-raises — 6× in Level 1", "STRONG"),
        "d2": ("Mid (12–25 BB)", "Steals + correct pot-odds calls (K3s→call vs ATo = mathematically right)", "SOLID"),
        "d3": ("Short (5–12 BB)", "Clean push/fold, double-ups with premiums, laddering", "STRONG"),
        "d4": ("Ultra (<3 BB)", "Forced, blinded out with trash at Level-21 blinds", "UNAVOIDABLE"),
        "prof_h": "PROFILE: THE PATIENT ACCUMULATOR",
        "prof_b": "You combine aggressive early-game chip accumulation with disciplined, ICM-aware short-stack laddering — a tournament profile that runs DEEP. Your push/fold math is clean; your laddering instincts (the A7o fold) are final-table caliber.",
        "verd_h": "HONEST VERDICT",
        "verd_b": "Well played. 3rd was VARIANCE, not a mistake — the pivotal AK-vs-KT flip lost, otherwise heads-up. Real leaks: none found. In a hyper-turbo the final table is a lottery by design; want more skill edge → slower structures.",
        "footer": "Generated from 75 hands · GG Speed Racer Bounty $108 · Princedarkness",
        "file": "Princedarkness_Player-Report_EN.pdf", "title": "Princedarkness — Player Report",
    },
}
POS_STRONG = {"STARK", "SOLIDE", "STRONG", "SOLID"}


def numfmt(n, lang):
    s = f"{n:,}"
    return s.replace(",", ".") if lang == "de" else s


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


# ---------------------------------------------------------------- draw helpers
def bg(c):
    c.setFillColorRGB(*BG); c.rect(0, 0, W, H, fill=1, stroke=0)


def text(c, x, y, s, size, col=CREAM, font="Helvetica", center=False, right=False):
    c.setFillColorRGB(*col); c.setFont(font, size)
    if center: c.drawCentredString(x, y, s)
    elif right: c.drawRightString(x, y, s)
    else: c.drawString(x, y, s)


def panel(c, x, y, w, h, fill=PANEL, radius=6):
    c.setFillColorRGB(*fill); c.setStrokeColorRGB(*GRID); c.setLineWidth(0.7)
    c.roundRect(x, y, w, h, radius, fill=1, stroke=1)


def card(c, x, y, rank, suit, w=15 * mm, h=21 * mm):
    c.setFillColorRGB(*CARD); c.setStrokeColorRGB(*CARDBORDER); c.setLineWidth(0.7)
    c.roundRect(x, y, w, h, 2.5, fill=1, stroke=1)
    col = REDC if suit in "hd" else (0.10, 0.10, 0.12)
    sym = {"h": "♥", "d": "♦", "s": "♠", "c": "♣"}[suit]
    r = {"T": "10"}.get(rank, rank)
    c.setFillColorRGB(*col)
    c.setFont("Helvetica-Bold", 12); c.drawString(x + 2, y + h - 12, r)
    c.setFont("Helvetica", 15); c.drawCentredString(x + w / 2, y + h / 2 - 6, sym)
    c.setFont("Helvetica-Bold", 8); c.drawRightString(x + w - 2, y + 4, r)


def hand_cards(c, x, y, cards, scale=1.0):
    for k, p in enumerate(cards.split()):
        card(c, x + k * 17 * mm * scale, y, p[0], p[1], 15 * mm * scale, 21 * mm * scale)


def chip(c, cx, cy, r, col=GOLD):
    c.setFillColorRGB(*col); c.circle(cx, cy, r, fill=1, stroke=0)
    c.setStrokeColorRGB(*CARD); c.setLineWidth(1); c.setDash(2, 2)
    c.circle(cx, cy, r * 0.72, fill=0, stroke=1); c.setDash()


def wrap(c, x, y, w, s, size, col, lead=None):
    lead = lead or size + 2.5
    c.setFillColorRGB(*col); c.setFont("Helvetica", size)
    line = ""
    for wd in s.split():
        if c.stringWidth(line + " " + wd, "Helvetica", size) < w:
            line = (line + " " + wd).strip()
        else:
            c.drawString(x, y, line); y -= lead; line = wd
    if line: c.drawString(x, y, line)


def footer_rule(c):
    c.setFillColorRGB(*GOLD); c.rect(0, 0, W, 4, fill=1, stroke=0)


# ---------------------------------------------------------------- pages
def cover(c, arc, L, lang):
    bg(c)
    c.setFillColorRGB(*GOLD); c.rect(0, H - 6, W, 6, fill=1, stroke=0)
    for k, xx in enumerate((28, 40, 52)):
        chip(c, xx * mm, H - 32 * mm, 9 * mm - k * 0.4 * mm, GOLD if k != 1 else TEAL)
    text(c, W / 2, H - 55 * mm, L["kicker"], 15, GOLD, "Helvetica-Bold", center=True)
    text(c, W / 2, H - 72 * mm, "PRINCEDARKNESS", 42, CREAM, "Helvetica-Bold", center=True)
    text(c, W / 2, H - 83 * mm, L["subtitle"], 11, MUTE, center=True)
    cx, cy = W / 2, H - 118 * mm
    c.setFillColorRGB(*GOLD); c.circle(cx, cy, 26 * mm, fill=1, stroke=0)
    c.setFillColorRGB(*BG); c.circle(cx, cy, 22 * mm, fill=1, stroke=0)
    text(c, cx, cy + 4 * mm, L["place"], 12, GOLD, "Helvetica-Bold", center=True)
    text(c, cx, cy - 12 * mm, "3", 46, CREAM, "Helvetica-Bold", center=True)
    py = 62 * mm
    for x0, big, small in ((28 * mm, "$108", L["buyin"]),
                           (W / 2 - 22 * mm, "~$1,200" if lang == "en" else "~$1.200", L["won"]),
                           (W - 72 * mm, "+$200", L["icm_money"])):
        panel(c, x0, py, 44 * mm, 22 * mm, PANEL, 6)
        text(c, x0 + 22 * mm, py + 13 * mm, big, 18, GOLD, "Helvetica-Bold", center=True)
        text(c, x0 + 22 * mm, py + 5 * mm, small, 8, MUTE, center=True)
    peak = max(arc, key=lambda a: a[1])
    text(c, W / 2, 42 * mm, L["cover_stat"].format(a=numfmt(10000, lang), b=numfmt(peak[1], lang)), 10, CREAM, center=True)
    text(c, W / 2, 20 * mm, L["cover_tag"], 11, TEAL, "Helvetica-Oblique", center=True)
    footer_rule(c); c.showPage()


def run_page(c, arc, L):
    bg(c)
    text(c, 22 * mm, H - 22 * mm, L["run_h"], 22, GOLD, "Helvetica-Bold")
    text(c, 22 * mm, H - 30 * mm, L["run_sub"], 10, MUTE)
    gx, gy, gw, gh = 22 * mm, H - 130 * mm, W - 44 * mm, 88 * mm
    panel(c, gx, gy, gw, gh, PANEL, 8)
    xs = [a[0] for a in arc]; ys = [a[1] for a in arc]
    xmin, xmax, ymax = min(xs), max(xs), max(ys)
    def px(i): return gx + 8 * mm + (i - xmin) / (xmax - xmin) * (gw - 16 * mm)
    def py(v): return gy + 8 * mm + v / ymax * (gh - 16 * mm)
    c.setStrokeColorRGB(*GRID); c.setLineWidth(0.5)
    for frac in (0.25, 0.5, 0.75, 1.0):
        yy = gy + 8 * mm + frac * (gh - 16 * mm)
        c.line(gx + 8 * mm, yy, gx + gw - 8 * mm, yy)
        text(c, gx + 6 * mm, yy - 2, f"{int(ymax*frac/1000)}k", 6, MUTE, right=True)
    p = c.beginPath(); p.moveTo(px(xs[0]), py(0))
    for i, v in zip(xs, ys): p.lineTo(px(i), py(v))
    p.lineTo(px(xs[-1]), py(0)); p.close()
    c.saveState(); c.setFillColorRGB(*GOLD); c.setFillAlpha(0.16); c.drawPath(p, fill=1, stroke=0); c.restoreState()
    c.setStrokeColorRGB(*GOLD); c.setLineWidth(2.2)
    p2 = c.beginPath(); p2.moveTo(px(xs[0]), py(ys[0]))
    for i, v in zip(xs, ys): p2.lineTo(px(i), py(v))
    c.drawPath(p2, stroke=1, fill=0)
    peak = max(arc, key=lambda a: a[1])
    chip(c, px(peak[0]), py(peak[1]), 3.2 * mm, TEAL)
    text(c, px(peak[0]), py(peak[1]) + 6 * mm, f"{L['peak']} {peak[1]//1000}k", 8, TEAL, "Helvetica-Bold", center=True)
    chip(c, px(xs[-1]), py(ys[-1]), 3 * mm, REDC)
    text(c, px(xs[-1]) - 5 * mm, py(ys[-1]) + 9 * mm, L["bust"], 8, REDC, "Helvetica-Bold", right=True)
    text(c, gx + gw / 2, gy - 5 * mm, L["run_axis"], 8, MUTE, center=True)
    ny = gy - 62 * mm
    bw = (gw - 8 * mm) / 3
    for k, (t, b, col) in enumerate([(L["b1_t"], L["b1_b"], TEAL), (L["b2_t"], L["b2_b"], GOLD), (L["b3_t"], L["b3_b"], CREAM)]):
        x0 = gx + k * (bw + 4 * mm)
        panel(c, x0, ny, bw, 46 * mm, PANEL, 6)
        c.setFillColorRGB(*col); c.rect(x0, ny + 46 * mm - 3, bw, 3, fill=1, stroke=0)
        text(c, x0 + 5 * mm, ny + 37 * mm, t, 10, col, "Helvetica-Bold")
        wrap(c, x0 + 5 * mm, ny + 30 * mm, bw - 10 * mm, b, 8.5, CREAM)
    footer_rule(c); c.showPage()


def pivotal_page(c, L):
    bg(c)
    text(c, 22 * mm, H - 22 * mm, L["piv_h"], 22, GOLD, "Helvetica-Bold")
    text(c, 22 * mm, H - 30 * mm, L["piv_sub"], 10, MUTE)
    y = H - 110 * mm
    panel(c, 22 * mm, y, W - 44 * mm, 72 * mm, PANEL, 8)
    text(c, 30 * mm, y + 62 * mm, L["keyhand"], 11, GOLD, "Helvetica-Bold")
    text(c, 30 * mm, y + 50 * mm, L["you"], 9, TEAL, "Helvetica-Bold")
    hand_cards(c, 30 * mm, y + 26 * mm, "Ad Kc")
    text(c, 30 * mm, y + 20 * mm, L["you_eq"], 8, MUTE)
    text(c, W / 2, y + 40 * mm, "VS", 16, CREAM, "Helvetica-Bold", center=True)
    text(c, W - 78 * mm, y + 50 * mm, L["caller"], 9, REDC, "Helvetica-Bold")
    hand_cards(c, W - 78 * mm, y + 26 * mm, "Ks Td")
    text(c, W - 78 * mm, y + 20 * mm, L["vill_eq"], 8, MUTE)
    text(c, 30 * mm, y + 12 * mm, L["board"], 9, MUTE)
    hand_cards(c, 48 * mm, y + 2 * mm, "7s 5h Tc 5s 9h", 0.62)
    text(c, W - 78 * mm, y + 8 * mm, L["vill_res"], 9, REDC, "Helvetica-Bold")
    text(c, W - 78 * mm, y + 2 * mm, L["ak_lose"], 10, REDC, "Helvetica-Bold")
    y2 = y - 66 * mm; halfw = (W - 48 * mm) / 2
    panel(c, 22 * mm, y2, halfw, 58 * mm, PANEL, 6)
    text(c, 28 * mm, y2 + 50 * mm, L["icm_h"], 11, TEAL, "Helvetica-Bold")
    text(c, 28 * mm, y2 + 42 * mm, L["icm_hand"], 9, CREAM, "Helvetica-Bold")
    wrap(c, 28 * mm, y2 + 35 * mm, halfw - 12 * mm, L["icm_body"], 8.5, CREAM)
    text(c, 28 * mm, y2 + 8 * mm, L["icm_result"], 11, GOLD, "Helvetica-Bold")
    xr = 22 * mm + halfw + 4 * mm
    panel(c, xr, y2, halfw, 58 * mm, PANEL, 6)
    text(c, xr + 6 * mm, y2 + 50 * mm, L["insight_h"], 11, GOLD, "Helvetica-Bold")
    wrap(c, xr + 6 * mm, y2 + 42 * mm, halfw - 12 * mm, L["insight_q"], 9.5, CREAM)
    wrap(c, xr + 6 * mm, y2 + 22 * mm, halfw - 12 * mm, L["insight_b"], 8.5, TEAL)
    footer_rule(c); c.showPage()


def verdict_page(c, L):
    bg(c)
    text(c, 22 * mm, H - 22 * mm, L["ver_h"], 22, GOLD, "Helvetica-Bold")
    y = H - 40 * mm
    text(c, 22 * mm, y, L["depth_h"], 12, TEAL, "Helvetica-Bold")
    yy = y - 8 * mm
    for key in ("d1", "d2", "d3", "d4"):
        label, desc, tag = L[key]
        panel(c, 22 * mm, yy - 11 * mm, W - 44 * mm, 12 * mm, PANEL, 4)
        text(c, 27 * mm, yy - 7 * mm, label, 9.5, GOLD, "Helvetica-Bold")
        text(c, 68 * mm, yy - 7 * mm, desc, 8.5, CREAM)
        text(c, W - 27 * mm, yy - 7 * mm, tag, 8.5, TEAL if tag in POS_STRONG else MUTE, "Helvetica-Bold", right=True)
        yy -= 14 * mm
    py = yy - 8 * mm
    panel(c, 22 * mm, py - 44 * mm, W - 44 * mm, 44 * mm, PANEL2, 8)
    text(c, 30 * mm, py - 10 * mm, L["prof_h"], 13, GOLD, "Helvetica-Bold")
    wrap(c, 30 * mm, py - 18 * mm, W - 64 * mm, L["prof_b"], 9.5, CREAM)
    vy = py - 60 * mm
    panel(c, 22 * mm, vy - 30 * mm, W - 44 * mm, 30 * mm, PANEL, 8)
    c.setFillColorRGB(*GOLD); c.rect(22 * mm, vy - 3, W - 44 * mm, 3, fill=1, stroke=0)
    text(c, 30 * mm, vy - 10 * mm, L["verd_h"], 11, GOLD, "Helvetica-Bold")
    wrap(c, 30 * mm, vy - 17 * mm, W - 64 * mm, L["verd_b"], 9, CREAM)
    text(c, W / 2, 12 * mm, L["footer"], 8, MUTE, center=True)
    footer_rule(c); c.showPage()


def build(lang):
    L = LANG[lang]; arc = parse()
    out = OUTDIR + "\\" + L["file"]
    c = canvas.Canvas(out, pagesize=A4)
    c.setTitle(L["title"])
    cover(c, arc, L, lang)
    run_page(c, arc, L)
    pivotal_page(c, L)
    verdict_page(c, L)
    c.save()
    print("PDF ->", out)


def main():
    for lang in ("de", "en"):
        build(lang)


if __name__ == "__main__":
    main()
