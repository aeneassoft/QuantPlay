"""Assemble the long German PDF player-report (plan 2026-07-01, stage 8) from the structured synth.json + the PNG
charts. reportlab Platypus; poker-green theme. Bakes the hard rules by SANITISING every string (no '$', no 'Verlust'/
'loss'/'downswing') at write-time — a defensive net on top of the LLM prompt. Output: C:/Users/hampe/Desktop/Spieler_Report.pdf
"""
from __future__ import annotations

import json
import os
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (CondPageBreak, HRFlowable, Image, ListFlowable, ListItem, PageBreak,
                                Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

from pokerbot.coach import report_charts as rc

STATS = "data/coach/deep_stats.json"
SIM = "data/coach/style_sim.json"
SYNTH = "data/coach/synth.json"
OUT = r"C:\Users\hampe\Desktop\Spieler_Report.pdf"

GREEN = colors.HexColor("#1f7a4d")
DARK = colors.HexColor("#1a2230")
GREY = colors.HexColor("#5b6470")
LIGHT = colors.HexColor("#eef3ef")
ACCENT = colors.HexColor("#0f5132")
GOLD = colors.HexColor("#c8a03c")

ss = getSampleStyleSheet()
S = {
    "Title": ParagraphStyle("T", parent=ss["Title"], fontSize=32, textColor=ACCENT, spaceAfter=6, leading=36),
    "Tsub": ParagraphStyle("Ts", parent=ss["Normal"], fontSize=14, textColor=GREEN, alignment=TA_CENTER,
                           fontName="Helvetica-Bold", spaceAfter=4),
    "H1": ParagraphStyle("H1", parent=ss["Heading1"], fontSize=17, textColor=colors.white, backColor=GREEN,
                         borderPadding=(6, 8, 6, 8), spaceBefore=18, spaceAfter=11, leading=21),
    "H2": ParagraphStyle("H2", parent=ss["Heading2"], fontSize=13, textColor=ACCENT, spaceBefore=10,
                         spaceAfter=5, leading=17),
    "Body": ParagraphStyle("B", parent=ss["Normal"], fontSize=10.6, leading=16, textColor=DARK, spaceAfter=8),
    "Lead": ParagraphStyle("L", parent=ss["Normal"], fontSize=12, leading=17.5, textColor=DARK, spaceAfter=9,
                           fontName="Helvetica-Oblique"),
    "Bullet": ParagraphStyle("Bu", parent=ss["Normal"], fontSize=10.6, leading=15.5, textColor=DARK),
    "Cap": ParagraphStyle("Cap", parent=ss["Normal"], fontSize=9, leading=12, textColor=GREY,
                          alignment=TA_CENTER, spaceBefore=3, spaceAfter=10, fontName="Helvetica-Oblique"),
    "Big": ParagraphStyle("Big", parent=ss["Normal"], fontSize=46, textColor=GREEN, alignment=TA_CENTER,
                          fontName="Helvetica-Bold", leading=50),
}

# hard-rule guard: strip any accidental money/loss wording the LLM might have slipped in. The user was emphatic
# ("überhaupt gar nicht von Verlusten") → catch the word AND its compounds (e.g. "Mutverlust" = loss of nerve).
_BANNED = [(re.compile(r"\$\s?\d[\d.,]*"), ""), (re.compile(r"\bUSD\b", re.I), ""),
           (re.compile(r"\bMutverlust(e|en)?\b", re.I), "Schwäche"),
           (re.compile(r"\w*[Vv]erlust\w*\b", re.I), "Schwankung"),
           (re.compile(r"\bloss(es)?\b", re.I), "swing"),
           (re.compile(r"\bDownswing(s)?\b", re.I), "Schwankungsphase"), (re.compile(r"\bverloren\b", re.I), "geschwankt")]
_LATIN = {"→": "->", "—": " – ", "’": "'", "“": '"', "”": '"', "…": "…", "×": "x", "≈": "ca. ", "•": "-"}


def san(t: str) -> str:
    t = str(t)
    for k, v in _LATIN.items():
        t = t.replace(k, v)
    for pat, repl in _BANNED:
        t = pat.sub(repl, t)
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def P(story, text, style="Body"):
    story.append(Paragraph(san(text), S[style]))


def H1(story, text):
    """A section header that never orphans: forces a new page if <95mm remains, so it stays with its chart."""
    story.append(CondPageBreak(95 * mm))
    story.append(Paragraph(san(text), S["H1"]))


def bullets(story, items, fmt=lambda x: x):
    li = [ListItem(Paragraph(san(fmt(x)), S["Bullet"]), leftIndent=12, value="square") for x in items]
    story.append(ListFlowable(li, bulletType="bullet", start="square", spaceBefore=2, spaceAfter=10))


def img(story, path, w_mm, caption=None):
    if not os.path.exists(path):
        return
    im = Image(path)
    ratio = im.imageHeight / im.imageWidth
    im.drawWidth = w_mm * mm
    im.drawHeight = w_mm * mm * ratio
    im.hAlign = "CENTER"
    story.append(Spacer(1, 4))
    story.append(im)
    if caption:
        story.append(Paragraph(san(caption), S["Cap"]))
    else:
        story.append(Spacer(1, 8))


def _glossary_table(items):
    data = [[Paragraph("<b>Begriff</b>", S["Bullet"]), Paragraph("<b>Einfach erklärt</b>", S["Bullet"])]]
    for it in items:
        data.append([Paragraph(f"<b>{san(it['begriff'])}</b>", S["Bullet"]),
                     Paragraph(san(it["erklaerung"]), S["Bullet"])])
    t = Table(data, colWidths=[38 * mm, 128 * mm], hAlign="LEFT")
    sty = [("BACKGROUND", (0, 0), (-1, 0), GREEN), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
           ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
           ("LEFTPADDING", (0, 0), (-1, -1), 8), ("VALIGN", (0, 0), (-1, -1), "TOP"),
           ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cfd8d0"))]
    for r in range(1, len(data)):
        if r % 2 == 0:
            sty.append(("BACKGROUND", (0, r), (-1, r), LIGHT))
    t.setStyle(TableStyle(sty))
    return t


def build():
    stats = json.load(open(STATS, encoding="utf-8"))
    synth = json.load(open(SYNTH, encoding="utf-8"))
    sim = json.load(open(SIM, encoding="utf-8")) if os.path.exists(SIM) else None
    por, edge = synth["portrait"], synth["edge"]
    dims, iq = synth["dims"], synth["iq"]

    # ensure the two data-driven charts exist
    rc.iq_radar(dims, iq)
    if sim:
        rc.bot_sim_chart(sim)

    story = []
    C = "data/coach/charts"

    # 1 — title
    story.append(Spacer(1, 60))
    P(story, "Dein Spieler-Porträt", "Title")
    P(story, f"„{por['archetyp_name']}“", "Tsub")
    story.append(Spacer(1, 8))
    P(story, "Eine tiefe Analyse deiner Spielweise", "Tsub")
    story.append(Spacer(1, 20))
    P(story, f"{stats['n_hands']} Hände · {stats['n_sessions']} Sitzungen · 6 Monate · Low-, Mid- & High-Stakes",
      "Cap")
    story.append(Spacer(1, 30))
    img(story, f"{C}/observed_range.png", 120)
    story.append(PageBreak())

    # 2 — overview + method
    H1(story, "Worum es hier geht")
    P(story, "Dieser Bericht ist kein Fehler-Katalog. Er ist ein Porträt deines Spiels — wie du denkst, wann du "
             "gefährlich wirst, wie du dich über die Monate veränderst und was dich als Spieler einzigartig macht. "
             "Wir schauen auf alles zusammen: die Karten, die du spielst, wie groß du setzt, wie du die Gänge "
             "wechselst — und behandeln dabei Pre-Flop (vor den Gemeinschaftskarten) und Post-Flop (danach) als EIN "
             "einziges, fließendes Feld.", "Lead")
    P(story, "Grundlage sind deine echten Hände aus sechs Monaten. Die Zeitachse deckt alle Einsatz-Level ab; die "
             "tiefe Detail-Analyse (Ranges, Coaching) konzentriert sich auf deine ernsten Sitzungen im Mid- und "
             "High-Bereich. Ein paar Kennzahlen — der „Spiel-IQ“, das „A/B/C-Game“, die „Confusion“ — sind von uns "
             "konstruierte Landkarten, keine amtlichen Werte; sie sind ehrlich aus echten Zahlen gebaut, aber als "
             "Orientierung gedacht, nicht als Urteil.")

    # 3 — glossary
    H1(story, "Mini-Glossar — nur das Nötigste")
    P(story, "Damit alles verständlich bleibt, hier die wenigen Fachbegriffe, die im Bericht vorkommen — je in einem "
             "Satz erklärt.")
    story.append(_glossary_table(por["glossar"]))
    story.append(PageBreak())

    # 4 — portrait
    H1(story, "Dein Spieler-Porträt")
    for para in por["portrait"]:
        P(story, para)

    # 5 — phases
    H1(story, "Deine Zeit-Phasen: A-, B- und C-Game")
    img(story, f"{C}/phase_timeline.png", 168,
        "Deine Sitzungen über 6 Monate. Farbe = Fokus-Level, Höhe = Einsatz-Level, Breite = Anzahl Hände.")
    for para in por["phasen"]:
        P(story, para)
    story.append(PageBreak())

    # 6 — strategy / flowing field
    H1(story, "Deine Strategien im fließenden Feld")
    for para in por["strategie_fliessendes_feld"]:
        P(story, para)

    # 7 — confusion
    H1(story, "Die Confusion-Frage: Wie unlesbar bist du?")
    img(story, f"{C}/confusion.png", 165,
        "Verteilung deiner Setzgrößen nach dem Flop. Viel Streuung = für Gegner schwer auszurechnen.")
    for para in por["confusion_text"]:
        P(story, para)
    story.append(PageBreak())

    # 8 — ranges
    H1(story, "Deine tatsächlichen Ranges")
    img(story, f"{C}/observed_range.png", 150,
        "Jedes Feld = eine Starthand. Je grüner, desto öfter hast du sie freiwillig gespielt.")
    for para in por["ranges_text"]:
        P(story, para)
    story.append(PageBreak())

    # 9 — when dangerous
    H1(story, "Wann bist du am gefährlichsten?")
    P(story, "Aus der Analyse deiner Entscheidungen kristallisieren sich klare Situationen heraus, in denen dein "
             "Stil richtig zubeißt:")
    for it in edge["wann_gefaehrlich"]:
        P(story, f"<b>{san(it['situation'])}</b>", "H2")
        P(story, it["warum"])

    # 10 — variance
    H1(story, "Deine Varianz, in Zahlen")
    img(story, f"{C}/variance.png", 165,
        "Wie weit deine einzelnen Ergebnisse streuen (in großen Blinds). Breite Streuung = wuchtiger Stil.")
    for para in edge["varianz_text"]:
        P(story, para)
    story.append(PageBreak())

    # 11 — IQ
    H1(story, "Der IQ deines Spiels")
    P(story, f"{iq}", "Big")
    P(story, "Spiel-IQ-Index (konstruiert, aus echten Bausteinen)", "Cap")
    img(story, f"{C}/iq_radar.png", 130,
        "Die sechs Dimensionen deines Spiels. Je weiter außen, desto stärker ausgeprägt.")
    for para in edge["iq_text"]:
        P(story, para)
    story.append(PageBreak())

    # 12 — simulation
    H1(story, "Simulation: Unsere Engine spielt deinen Style")
    P(story, "Wir haben deine gemessenen Tendenzen — locker, aggressiv, viele Overbets, klebrig beim Mitgehen — in "
             "unsere eigene Poker-Engine übertragen und diesen „digitalen Zwilling“ gegen viele Gegner-Typen antreten "
             "lassen. Das zeigt, wo dein Stil von Natur aus dominiert und wo er gekontert wird.")
    img(story, f"{C}/bot_sim.png", 165, "Dein Stil-Zwilling gegen verschiedene Gegner-Typen.")
    bullets(story, edge["sim_lektionen"])
    story.append(PageBreak())

    # 13 — other players
    H1(story, "Wer spielt sonst so?")
    P(story, "Dein Stil ist eine seltene Mischung. Am nächsten kommen ihm diese bekannten Spieler-Typen:")
    for it in edge["andere_spieler"]:
        P(story, f"<b>{san(it['name'])}</b>", "H2")
        P(story, it["warum"])

    # 14 — conclusion
    H1(story, "Fazit: Deine Kern-Stärken")
    for para in edge["fazit"]:
        P(story, para, "Lead")
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", color=GOLD, thickness=1.2))
    P(story, "Erstellt aus deiner echten 6-Monats-Historie · alle konstruierten Kennwerte sind ehrlich als "
             "Orientierung gekennzeichnet.", "Cap")
    return story


def main():
    doc = SimpleDocTemplate(OUT, pagesize=A4, topMargin=18 * mm, bottomMargin=16 * mm,
                            leftMargin=20 * mm, rightMargin=20 * mm, title="Dein Spieler-Porträt")
    doc.build(build())
    print("PDF ->", OUT, "|", os.path.getsize(OUT), "bytes")


if __name__ == "__main__":
    main()
