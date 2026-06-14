"""Extract structured knowledge from a PDF book via Claude: chunk the text, pull focus-relevant items,
save JSON. (1) algorithmic-game-theory.pdf (775p Nisan/Roughgarden textbook -> self-play/CFR/equilibrium
THEORY; Haiku filters the mostly-irrelevant chapters cheaply). (2) Beyond GTO (206p -> EXPLOIT PRIMITIVES;
Opus for quality). Chunks return [] when nothing relevant, so the textbook's irrelevant pages cost little.
Run:  python -m extraction.extract_book
"""
from __future__ import annotations

import json
import re

from pokerbot import config


def _pdf_pages(path):
    try:
        from pypdf import PdfReader
    except ImportError:
        from PyPDF2 import PdfReader  # noqa
    return [(p.extract_text() or "") for p in PdfReader(str(path)).pages]


def _chunks(pages, n=20):
    for i in range(0, len(pages), n):
        txt = "\n".join(pages[i:i + n]).strip()
        if len(txt) >= 200:
            yield i, txt[:60000]


def extract(pdf, out, focus, model):
    from anthropic import Anthropic
    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        pages = _pdf_pages(pdf)
    except Exception as e:  # noqa: BLE001
        print(f"PDF read FAILED {pdf.name}: {type(e).__name__}: {e}", flush=True)
        return
    print(f"=== {pdf.name}: {len(pages)} pages | model={model} ===", flush=True)
    items = []
    for start, txt in _chunks(pages):
        prompt = (f"{focus}\n\nReturn ONLY a JSON array of objects (no prose, no markdown fences). "
                  f"If nothing relevant on these pages, return []. \n\nBOOK TEXT (from page ~{start}):\n{txt}")
        try:
            r = client.messages.create(model=model, max_tokens=3000,
                                       messages=[{"role": "user", "content": prompt}])
            t = "".join(b.text for b in r.content if getattr(b, "type", None) == "text")
            m = re.search(r"\[.*\]", t, re.S)
            got = json.loads(m.group(0)) if m else []
            items.extend(got)
            if got:
                print(f"  page ~{start}: +{len(got)} (total {len(items)})", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"  page ~{start}: ERR {type(e).__name__}", flush=True)
    out.write_text(json.dumps(items, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"SAVED {len(items)} items -> {out}", flush=True)


AGT_FOCUS = (
    "You are extracting from an algorithmic game-theory textbook ONLY the concepts relevant to building a "
    "No-Limit Hold'em AI that (a) reaches equilibrium/GTO via SELF-PLAY + no-regret learning and (b) "
    "exploits opponents. For each return {name, concept (1-3 sentences), application (how it informs our "
    "self-play->GTO + exploit bot)}. ONLY: Nash equilibrium; correlated & coarse-correlated equilibrium "
    "(CCE); no-regret / regret-minimization + convergence guarantees; fictitious play; counterfactual "
    "regret (CFR); exploitability; PPAD-hardness of Nash; 2p-zero-sum vs multiplayer general-sum; "
    "best-response dynamics. If the pages are about auctions/mechanism-design/routing/unrelated, return []."
)

BGTO_FOCUS = (
    "You are extracting concrete EXPLOIT PRIMITIVES from a poker exploitation book. For each exploit rule "
    "return {tendency (observable opponent leak), stat (a measurable statistic that detects it, e.g. "
    "fold_to_cbet, wtsd, 3bet_pct, aggression, fold_to_3bet), spot (street/position/node), adjustment (the "
    "action change), direction (e.g. bluff more / value-bet thinner / fold more / call wider), magnitude "
    "(small|medium|large), confidence (0..1)}. Focus on trigger->adjustment rules wireable into an online "
    "opponent-modeling exploit engine. Skip generic prose / history / hand-reading narration."
)


def main():
    extract(config.ROOT / "algorithmic-game-theory.pdf",
            config.KNOWLEDGE_DIR / "theory" / "algorithmic_game_theory.json", AGT_FOCUS,
            config.CLAUDE_HAIKU_MODEL)
    extract(config.ROOT / "Beyond GTO_ Poker Exploits Simplified (The Poker Solved Series).pdf",
            config.KNOWLEDGE_DIR / "exploit" / "beyond_gto.json", BGTO_FOCUS,
            config.CLAUDE_MODEL)


if __name__ == "__main__":
    main()
