"""Extract & formalize the deeper math from 'The Mathematics of Poker' via OpenAI (gpt-5.1).

Pulls the key game-theory results (toy games like [0,1] and AKQ, indifference, optimal
bluffing/calling frequencies, bet-sizing, jam/fold equilibria) into structured, implementable
items with Python where applicable.

Output: knowledge_base/math/mathematics_of_poker.json (+ .md)
Run:    python -m extraction.mathematics_of_poker [--analyze]
"""
from __future__ import annotations

import argparse
import json

import fitz

from pokerbot import config
from extraction.llm import openai_json

PDF = config.ROOT / "The_Mathematics_of_Poker.pdf"
TXT = config.TEXT_DIR / "mathematics_of_poker.txt"

SYSTEM = (
    "You are a game theorist specializing in poker mathematics (Chen & Ankenman style). From the "
    "given excerpt of 'The Mathematics of Poker', extract the key mathematical MODELS and RESULTS "
    "that a poker bot could use or learn from: toy games ([0,1], AKQ), indifference principles, "
    "optimal bluffing/calling/bet-sizing frequencies, the alpha/MDF relationships, jam-or-fold "
    "equilibria, and EV formulas. For each, give a clear concept, the formula (plain text), a "
    "self-contained Python function when it is computable (else empty string), and a concrete "
    "takeaway for a NLHE bot. Be precise; skip prose/history."
)

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {"items": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "properties": {"name": {"type": "string"}, "concept": {"type": "string"},
                       "formula": {"type": "string"}, "python": {"type": "string"},
                       "bot_takeaway": {"type": "string"}},
        "required": ["name", "concept", "formula", "python", "bot_takeaway"]}}},
    "required": ["items"],
}


def extract_text() -> str:
    doc = fitz.open(PDF)
    text = "\n".join(doc[i].get_text("text") for i in range(doc.page_count))
    doc.close()
    TXT.write_text(text, encoding="utf-8")
    return text


def _chunks(text: str, size: int = 22000):
    for i in range(0, len(text), size):
        yield text[i:i + size]


def analyze(text: str):
    all_items, tin, tout = [], 0, 0
    chunks = list(_chunks(text))
    for i, ch in enumerate(chunks, 1):
        if len(ch.strip()) < 400:
            continue
        try:
            data, (pin, pout) = openai_json(SYSTEM, f"Excerpt {i}/{len(chunks)}:\n\n{ch}",
                                             SCHEMA, "mop_math", max_tokens=16000)
        except Exception as e:  # noqa: BLE001
            print(f"  chunk {i} error: {e}")
            continue
        items = data.get("items", [])
        all_items += items
        tin += pin; tout += pout
        print(f"  chunk {i}/{len(chunks)}: {len(items)} items (in={pin} out={pout})")
    out = config.MATH_DIR / "mathematics_of_poker.json"
    out.write_text(json.dumps(all_items, ensure_ascii=False, indent=2), encoding="utf-8")
    md = ["# The Mathematics of Poker — extracted models\n"]
    for it in all_items:
        md.append(f"## {it['name']}\n{it['concept']}\n\n**Formel:** {it['formula']}\n\n"
                  f"**Für den Bot:** {it['bot_takeaway']}\n")
    (config.MATH_DIR / "mathematics_of_poker.md").write_text("\n".join(md), encoding="utf-8")
    print(f"\nMerged {len(all_items)} items -> mathematics_of_poker.json (in={tin} out={tout})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--analyze", action="store_true")
    args = ap.parse_args()
    text = extract_text()
    chars = len(text)
    print(f"Extracted {chars:,} chars from {PDF.name}")
    print("Sample:", " ".join(text[:400].split()))
    if args.analyze:
        analyze(text)


if __name__ == "__main__":
    main()
