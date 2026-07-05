"""Mobile (iPhone Pro Max) PDF for the calling-station strategy guide (2026-07-01). Page = 430x932 pt (one Pro-Max
screen aspect), large single-column type, the portrait sim-chart — reads without pinch-zoom. Content is grounded in the
engine Monte-Carlo (pokerbot/coach/station_sim.py) + the exploit KB + the user's own coached hands; every claim survived
an adversarial audit. Output: C:/Users/hampe/Desktop/Gegen_Calling_Stations.pdf
"""
from __future__ import annotations

import os
import re

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (CondPageBreak, HRFlowable, Image, ListFlowable, ListItem,
                                Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

from pokerbot.coach import report_charts as rc

OUT = r"C:\Users\hampe\Desktop\Gegen_Calling_Stations.pdf"
PAGE = (430, 932)                     # iPhone Pro Max logical points — each PDF page ~= one screen
CHART = "data/coach/charts/station_sim_mobile.png"

GREEN = colors.HexColor("#1f7a4d")
DARK = colors.HexColor("#16202e")
GREY = colors.HexColor("#5b6470")
LIGHT = colors.HexColor("#eef3ef")
ACCENT = colors.HexColor("#0f5132")
RED = colors.HexColor("#b0544e")
GOLD = colors.HexColor("#c8a03c")

ss = getSampleStyleSheet()
S = {
    "Title": ParagraphStyle("T", parent=ss["Title"], fontSize=27, textColor=ACCENT, leading=31, spaceAfter=2),
    "Sub": ParagraphStyle("Sub", parent=ss["Normal"], fontSize=14.5, textColor=GREEN, leading=19,
                          fontName="Helvetica-Bold", spaceAfter=6),
    "H1": ParagraphStyle("H1", parent=ss["Heading1"], fontSize=17, textColor=colors.white, backColor=GREEN,
                         borderPadding=(6, 8, 6, 8), spaceBefore=15, spaceAfter=9, leading=21),
    "Body": ParagraphStyle("B", parent=ss["Normal"], fontSize=14, leading=20, textColor=DARK, spaceAfter=8),
    "Bullet": ParagraphStyle("Bu", parent=ss["Normal"], fontSize=14, leading=19.5, textColor=DARK),
    "Cap": ParagraphStyle("Cap", parent=ss["Normal"], fontSize=11, leading=14, textColor=GREY,
                          fontName="Helvetica-Oblique", spaceBefore=2, spaceAfter=10),
    "Rule": ParagraphStyle("R", parent=ss["Normal"], fontSize=15, leading=21, textColor=DARK, fontName="Helvetica-Bold"),
}
_LATIN = {"→": "->", "—": " – ", "’": "'", "„": '"', "“": '"', "”": '"', "×": "x", "≈": "ca. ", "½": "1/2",
          "⅔": "2/3", "•": "-", "€": "EUR", "…": "..."}


def san(t: str) -> str:
    t = str(t)
    for k, v in _LATIN.items():
        t = t.replace(k, v)
    t = re.sub(r"\$\s?\d[\d.,]*", "", t)              # never money amounts
    t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # restore the inline markup we DO use (escaping above neutralised any stray real tags)
    for esc, tag in [("&lt;b&gt;", "<b>"), ("&lt;/b&gt;", "</b>"), ("&lt;br/&gt;", "<br/>")]:
        t = t.replace(esc, tag)
    return t


def P(story, t, sty="Body"):
    story.append(Paragraph(san(t), S[sty]))


def H1(story, t):
    story.append(CondPageBreak(70 * mm))
    story.append(Paragraph(san(t), S["H1"]))


def bullets(story, items):
    li = [ListItem(Paragraph(san(x), S["Bullet"]), leftIndent=10, value="square") for x in items]
    story.append(ListFlowable(li, bulletType="bullet", start="square", spaceBefore=2, spaceAfter=9))


def callout(story, t, tag="DIE GOLDENE REGEL", col=GREEN):
    inner = Paragraph(f'<b>{san(tag)}</b><br/><br/>{san(t)}', S["Rule"])
    tbl = Table([[inner]], colWidths=[PAGE[0] - 44 - 16])
    tbl.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), LIGHT), ("LEFTPADDING", (0, 0), (-1, -1), 12),
                             ("RIGHTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 10),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 10), ("LINEBEFORE", (0, 0), (0, -1), 4, col)]))
    story.append(tbl)
    story.append(Spacer(1, 10))


def img_full(story, path, caption=None):
    if not os.path.exists(path):
        return
    from PIL import Image as PILImage
    iw, ih = PILImage.open(path).size
    w = PAGE[0] - 44
    im = Image(path, width=w, height=w * ih / iw)        # explicit size = never overflow the narrow page
    im.hAlign = "CENTER"
    story.append(im)
    if caption:
        story.append(Paragraph(san(caption), S["Cap"]))
    else:
        story.append(Spacer(1, 8))


def build():
    story = []

    # cover
    story.append(Spacer(1, 8))
    P(story, "Gegen Calling-Stations", "Title")
    P(story, "Spieler, die „Karten sehen wollen“ und mit jedem Paar mitgehen", "Sub")
    P(story, "Kurz-Guide - engine-gemessen, für dein Spiel.", "Cap")

    callout(story, "Setze deine guten Hände GROSS auf Value und hör auf, sie zu bluffen. "
                   "Ein Station kann nicht folden – also gewinnst du sein Geld nicht mit Druck, sondern mit Value.")

    # why
    H1(story, "Warum das so ist")
    P(story, "Normales „ausbalanciertes“ Spiel funktioniert nur, weil dein Gegner ab und zu foldet. Ein Calling-Station "
             "foldet fast nie – damit fällt die ganze Grundlage für Bluffs weg: Ein Bluff gewinnt nur, wenn er eine "
             "bessere Hand zum Wegwerfen bringt. Bei jemandem, der nicht wegwirft, ist jeder Bluff verschenkt.")
    P(story, "Gleichzeitig wird Value viel breiter: Weil er mit jedem Paar, jedem Ass-Hoch und jedem Draw mitgeht, "
             "verdienst du schon mit mittelstarken Händen, die du gegen gute Gegner nur checken würdest.")

    # measured
    H1(story, "Wir haben es gemessen")
    P(story, "Unsere Engine hat je 6.000 echte Hände gegen einen Station ausgespielt und verglichen, wie viel dir "
             "SETZEN gegenüber CHECKEN bringt (in großen Blinds). Die Zahlen zeigen die RICHTUNG – nicht garantierte "
             "Beträge, aber der Trend ist über viele Läufe stabil:")
    img_full(story, CHART, "Grün = Setzen bringt Chips. Rot = Setzen verbrennt Chips.")
    bullets(story, [
        "<b>Bluffs bis zum River verbrennen Chips</b> (-9,7 bb). Ein einzelner Flop-Stab ist noch ok (±0).",
        "<b>Starke Hände GROSS setzen zahlt sich am meisten aus</b>: der Overbet bringt in der Simulation gut das "
        "4-Fache eines kleinen Bets (gegen einen maximal klebrigen Gegner bis zu ~40 bb).",
        "<b>Top-Pair ruhig drei Straßen dünn betten</b> (+3,9 bis +6,1 bb) – aber ein <b>schwaches Paar NICHT</b> bis "
        "zum River durchprügeln (-3,8 bb); der Fehler ist der dritte Barrel, nicht das Setzen an sich.",
    ])

    # the adjustments
    H1(story, "Deine Anpassungen")
    bullets(story, [
        "<b>Mehr Value, weniger Bluff.</b> Mach das Value-Betten zu deinem Hauptplan, nicht das Bluffen.",
        "<b>Größer machen.</b> Weil er jede Größe callt, setze deine starken Hände dick – bis zum Overbet. Er zahlt.",
        "<b>Dünn auf Value gehen.</b> Auch Top-Pair mit mittlerem Kicker ist hier ein Value-Bet über mehrere Straßen.",
        "<b>Schwache Hände kontrollieren.</b> Zweitpaar/Underpair: ein, zwei Bets für Value oder zum Schutz gegen "
        "Draws sind ok – aber keine drei Barrels; sonst zahlst DU die besseren Paare.",
        "<b>Preflop isolieren.</b> Erhöhe (statt zu limpen/callen), um heads-up und möglichst in Position mit ihm zu "
        "spielen – mit Händen, die gut Top-Pair treffen. Reine Bluff-Hände (lose Suited Connectors nur zum Klauen) "
        "brauchst du gegen ihn nicht.",
        "<b>Wenn er raist: glauben.</b> Ein passiver Spieler, der plötzlich selbst setzt/raist, hat fast immer eine "
        "starke Hand – dann kannst du dein eines Paar getrost weglegen.",
    ])

    # personalisation
    H1(story, "Das passt zu deinem Stil")
    P(story, "Der Station-Gegner ist wie gemacht für dich: Deine Stärke sind große Value-Bets und Overbets – genau die "
             "zahlt ein Station am liebsten. Deine Aggression wird hier zu barem Value, nicht zu Risiko.")
    P(story, "Zwei Dinge, auf die du bei DIR achten solltest (deine bekannten Muster):", "Body")
    bullets(story, [
        "Deine großen Overbets nur mit starker Hand oder starkem Draw – <b>nicht als reinen Bluff</b>. Gegen einen "
        "Station ist der Overbet-Bluff der teuerste Fehler.",
        "Wenn ein großer Bluff gecallt wird: <b>aufhören</b>, nicht „zu Ende bluffen“. Der Call zeigt eine klebrige "
        "Hand.",
        "Lose aus früher Position OOP nur mitgehen, wenn du triffst und hältst – gegen Stations werden dominierte "
        "Hände teuer.",
    ])

    # nuance
    H1(story, "Die Ausnahmen")
    P(story, "Damit du nicht komplett ausrechenbar wirst – kleine, gezielte Ausnahmen bleiben erlaubt:")
    bullets(story, [
        "<b>Ein Flop-Stab</b> ist ok (bricht die vielen Air-Hände weg). Nur nicht stur weiter-barreln.",
        "<b>Scare-Cards & Semi-Bluffs:</b> Wenn ein Draw ankommt oder du selbst noch einen Draw hast, darfst du Druck "
        "machen – das ist Value/Equity, kein reiner Bluff.",
        "<b>Manche „Stations“ folden doch den Turn/River:</b> Wer nur den Flop klebt, den kannst du mit einem zweiten/"
        "dritten Barrel doch noch wegdrücken – erst beobachten, dann anpassen.",
        "<b>Mehrere Gegner = enger.</b> Gegen zwei oder mehr Caller wird ihre Range stärker – dann dünnes Value UND "
        "Bluffs vorsichtiger, nur mit klaren Value-Händen in große Pötte.",
        "<b>Nasses Board:</b> Auf sehr Draw-lastigen Boards kann dein Top-Pair zum Bluffcatcher werden – dann kleiner "
        "halten; und schwache Paare dort ruhig mal setzen, um dem Draw Equity zu verweigern.",
    ])

    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", color=GOLD, thickness=1.2))
    P(story, "Kurz: Value groß, Bluff klein. Lass ihn zahlen, statt ihn wegdrücken zu wollen.", "Rule")
    return story


def main():
    import json
    sim = json.load(open("data/coach/station_sim.json", encoding="utf-8"))
    rc.station_sim_chart_mobile(sim)                  # (re)generate the portrait chart the PDF embeds
    doc = SimpleDocTemplate(OUT, pagesize=PAGE, topMargin=26, bottomMargin=24, leftMargin=22, rightMargin=22,
                            title="Gegen Calling-Stations")
    doc.build(build())
    print("PDF ->", OUT, "|", os.path.getsize(OUT), "bytes")


if __name__ == "__main__":
    main()
