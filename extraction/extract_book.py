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


def _chunks(pages, n=12):
    for i in range(0, len(pages), n):
        txt = "\n".join(pages[i:i + n]).strip()
        if len(txt) >= 200:
            yield i, txt[:45000]


def extract(pdf, out, focus, model):
    from anthropic import Anthropic
    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and out.stat().st_size > 50:
        print(f"skip {out.name} (already extracted)", flush=True)
        return
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
            r = client.messages.create(model=model, max_tokens=8000,
                                       messages=[{"role": "user", "content": prompt}])
            t = "".join(b.text for b in r.content if getattr(b, "type", None) == "text")
            m = re.search(r"\[.*\]", t, re.S)
            try:
                got = json.loads(m.group(0)) if m else []
            except json.JSONDecodeError:          # truncated array -> salvage complete objects
                got = [json.loads(o) for o in re.findall(r"\{[^{}]*\}", m.group(0))] if m else []
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


EXPLO_FOCUS = (
    "This book teaches EXPLOITATION via planned betting lines, organized by opponent TYPE (calling station, "
    "weak-tight, LAG, maniac, nit, showdown-monkey, TAG, etc.). The text is largely NARRATIVE -- DISTILL "
    "the concrete exploit rule from the prose; do NOT skip a chapter just because it is explanatory (that "
    "IS the content). Extract GENEROUSLY: every distinct line/adjustment per opponent type. For each return "
    "{opponent_type, trigger (read/stat), spot (street/position/node), line (planned multi-street betting "
    "sequence, e.g. 'flop bet 75%, turn check, river overbet'), adjustment (deviation from GTO + WHY it "
    "exploits), confidence (0..1)}. Return [] ONLY for truly contentless pages (cover/title/diagram-only)."
)


SOTA_FOCUS = (
    "Extract from this poker-AI RESEARCH PAPER the architecture + techniques relevant to building our "
    "self-play->GTO + exploit bot. For each return {component, description (1-3 sentences), application (how "
    "it informs our build)}. Capture: value/policy network design (CFVnet / CFR value net); training method "
    "(CFR/MCCFR/CFR+/DCFR+/Deep-CFR self-play); depth-limited solving / subgame re-solving / search; "
    "abstraction (card + action); blueprint strategy; exploitability/results (bb/100, mbb/g); and any lesson "
    "about exploitation vs static GTO play. Skip pure proofs / unrelated background."
)


def main():
    books = config.ROOT / "books"     # all source PDFs live here (papers under books/papers/)
    extract(books / "algorithmic-game-theory.pdf",
            config.KNOWLEDGE_DIR / "theory" / "algorithmic_game_theory.json", AGT_FOCUS,
            config.CLAUDE_HAIKU_MODEL)
    extract(books / "Beyond GTO_ Poker Exploits Simplified (The Poker Solved Series).pdf",
            config.KNOWLEDGE_DIR / "exploit" / "beyond_gto.json", BGTO_FOCUS,
            config.CLAUDE_MODEL)
    extract(books / "Exploitative Poker_ Learn to Play the Player_ Using Planned Betting Lines.pdf",
            config.KNOWLEDGE_DIR / "exploit" / "exploitative_poker.json", EXPLO_FOCUS,
            config.CLAUDE_MODEL)
    for paper in ("Supremus.pdf", "Pluribus.pdf"):
        extract(books / "papers" / paper,
                config.KNOWLEDGE_DIR / "theory" / (paper.replace(".pdf", "_paper.json").lower()),
                SOTA_FOCUS, config.CLAUDE_MODEL)


if __name__ == "__main__":
    main()
