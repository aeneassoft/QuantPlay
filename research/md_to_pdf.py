# -*- coding: utf-8 -*-
"""Render a simple-Markdown report (#/##/### headings, paragraphs, '- ' bullets, **bold**) to a clean A4 PDF.
German-safe (Helvetica/WinAnsi covers ä ö ü ß, em-dash, curly quotes, bullet).

  python research/md_to_pdf.py <in.md> <out.pdf> ["Title"]
"""
import re
import sys

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable

INK = colors.HexColor("#1a1a2e")
GREY = colors.HexColor("#444444")

# replace chars outside CP1252 (would render as black boxes in built-in fonts)
SAN = {"→": "->", "↔": "<->", "⇒": "=>", "≈": "~", "≥": ">=",
       "≤": "<=", "×": "x", "…": "...", "-": "-", "₮": "",
       " ": " ", " ": " ", " ": " "}


def san(s: str) -> str:
    for k, v in SAN.items():
        s = s.replace(k, v)
    return s


def inline(s: str) -> str:
    s = san(s)
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)        # **bold** -> <b>
    return s


def main():
    md_path = sys.argv[1]
    out = sys.argv[2]
    text = open(md_path, encoding="utf-8").read()

    ss = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=ss["BodyText"], fontName="Helvetica", fontSize=10.5,
                          leading=15.2, alignment=TA_JUSTIFY, spaceAfter=7, textColor=colors.HexColor("#181818"))
    h1 = ParagraphStyle("h1", parent=ss["Title"], fontName="Helvetica-Bold", fontSize=19, leading=23,
                        spaceAfter=4, textColor=INK)
    h2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=14.5, leading=18, spaceBefore=15,
                        spaceAfter=5, textColor=INK)
    h3 = ParagraphStyle("h3", fontName="Helvetica-Bold", fontSize=11.5, leading=15, spaceBefore=9,
                        spaceAfter=3, textColor=GREY)
    bullet = ParagraphStyle("bullet", parent=body, leftIndent=16, firstLineIndent=-9, spaceAfter=3)

    doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=2.2 * cm, rightMargin=2.2 * cm,
                            topMargin=2.0 * cm, bottomMargin=2.0 * cm, title="Poker-Stil-Report")
    S = []
    para = []
    bullets = []

    def flush_para():
        if para:
            S.append(Paragraph(inline(" ".join(para)), body))
            para.clear()

    def flush_bullets():
        for b in bullets:
            S.append(Paragraph("-  " + inline(b), bullet))   # literal CP1252 bullet + nbsp
        bullets.clear()

    for raw in text.splitlines():
        st = raw.strip()
        if not st:
            flush_para(); flush_bullets(); continue
        if st.startswith("### "):
            flush_para(); flush_bullets(); S.append(Paragraph(inline(st[4:]), h3))
        elif st.startswith("## "):
            flush_para(); flush_bullets(); S.append(Paragraph(inline(st[3:]), h2))
        elif st.startswith("# "):
            flush_para(); flush_bullets()
            S.append(Paragraph(inline(st[2:]), h1))
            S.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#cccccc"),
                                spaceBefore=4, spaceAfter=9))
        elif st.startswith("- ") or st.startswith("* "):
            flush_para(); bullets.append(st[2:])
        else:
            flush_bullets(); para.append(st)
    flush_para(); flush_bullets()

    n = len(S)
    doc.build(S)
    print(f"WROTE {out}  ({n} flowables)")


if __name__ == "__main__":
    main()
