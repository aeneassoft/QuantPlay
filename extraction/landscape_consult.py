"""Consult gpt-5.5: which DATA / METHODS / ALGORITHMS from open-source GTO bots & solvers can we ADAPT for our
bot (NOT 1:1 copy, NOT limiting our adaptive-exploit edge), where are our GAPS + which OS project fills each,
how to BENCHMARK beyond noisy Slumbot, and the HARDEST NLHE spots we must master. Grounded in our bot. Output
-> docs/landscape_gpt55.md. Run: python -m extraction.landscape_consult
"""
from __future__ import annotations

from pokerbot import config

GPT_MODEL = "gpt-5.5"

SYSTEM = (
    "You are a world-class poker-AI researcher AND engineer who knows the open-source poker-AI landscape "
    "(solvers, CFR/Deep-CFR frameworks, hand-history datasets, abstraction, variance reduction) deeply and is "
    "brutally honest. The user's goal is to be the BEST bot = a robust GTO floor + an ADAPTIVE EXPLOITER. So: "
    "adapt others' methods/data WITHOUT copying any one bot 1:1 and WITHOUT limiting the exploit edge (pure-GTO "
    "bots do NOT exploit -- that is THEIR ceiling, not a thing to copy). Ground every suggestion in the user's "
    "actual assets, name the concrete win, and flag what is NOT worth adapting (adds complexity / limits us / "
    "won't help). Be specific enough to act on."
)

BRIEF = """\
OUR BOT (consolidation/pruning phase):
- FLOOR: solver-calibrated preflop lookup table (88.6%), heuristic postflop (MC equity + pot-odds/MDF +
  fold-equity sizing), EXACT river equity by enumeration, a freq-capped OOP donk (just fixed an over-donk).
- EXPLOIT OVERLAY: bounded stat-keyed rules -> bluff/value/foldcatch frequency nudges, confidence-gated, capped.
  This is our EDGE: +49 bb/100 vs Slumbot with overlay, crushes the exploitable field (+300..+1100).
- ASSETS: TexasSolver GTO caches (many flops + some turns), PokerBench 563k labeled GTO decisions, 10k Pluribus
  hands, the Slumbot fold-curve. CFR+ VALIDATED on Leduc (exploitability 1300->16 mbb monotone, after we fixed
  a clairvoyant best-response bug). OpenSpiel Deep-CFR on NLHE (fcpa) runs+learns but is CPU/traversal-bound;
  deferred. Planned: a small SUPERVISED 'GTO-floor advisor' that interpolates our caches+PokerBench (glue, not
  a from-scratch solve), conf-gated blend into the postflop floor.
- MEASURED WEAKNESS: the FLOOR loses to near-GTO (Slumbot floor ~ -50..-100 bb/100, noisy +/-110); the exploit
  edge is the money. Our eval is TOO NOISY (Slumbot 400 hands = +/-70..110 bb/100).

ANSWER EACH, grounded + honest:
Q1. ADAPT FROM OPEN SOURCE: name the open-source bots / solvers / CFR frameworks / DATASETS whose DATA,
    METHODS, or ALGORITHMS we should ADAPT (not 1:1 copy). For each: project, what exactly to take, how it
    plugs into OUR engine, the concrete win. Cover at least: solvers (TexasSolver + others / public solver
    outputs), CFR-family (CFR+/Linear/Discounted-CFR/MCCFR/Deep-CFR/ReBeL/NFSP -- and which we already have),
    card+action ABSTRACTION (potential-aware clustering), VARIANCE REDUCTION (AIVAT) for evaluation, continual
    re-solving / depth-limited subgame solving, and hand-history DATASETS (PHH, IRC db, others).
Q2. OUR GAPS vs the strongest bots -- where are our holes, and which OS project already FILLS each (so we adapt
    instead of reinventing)? Rank by impact-on-strength.
Q3. BENCHMARKING: beyond Slumbot, what should we measure against and HOW? Our eval is too noisy -- what is the
    cheapest fix (AIVAT? OpenSpiel exploitability/best-response? LBR? duplicate at scale?) and how do we wire it?
Q4. HARDEST SPOTS: the NLHE situations we MUST master -- where GTO bots win and our heuristic floor most likely
    fails. Rank them, and for each give how to attack it with our assets (solver caches, advisor, exploit overlay).

Be specific. If a famous method would LIMIT our exploitation edge or just add complexity, say so plainly.
"""


def ask_gpt() -> str:
    from openai import OpenAI
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": BRIEF}]
    for kw in ({"reasoning_effort": "medium", "max_completion_tokens": 32000},
               {"max_completion_tokens": 32000}, {}):
        try:
            r = client.chat.completions.create(model=GPT_MODEL, messages=msgs, **kw)
            txt = r.choices[0].message.content or ""
            if txt.strip():
                return txt
            print(f"(empty, finish={r.choices[0].finish_reason}, kw={list(kw)})", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"(gpt err kw={list(kw)}: {type(e).__name__}: {str(e)[:90]})", flush=True)
    return ""


def main() -> None:
    print(f"=== querying {GPT_MODEL} (open-source landscape + gaps + hardest spots) ...", flush=True)
    g = ask_gpt()
    out = config.ROOT / "docs" / "landscape_gpt55.md"
    out.write_text(f"# Open-source landscape / gaps / hardest spots — {GPT_MODEL}\n\n{g}\n", encoding="utf-8")
    print(f"saved {out} ({len(g)} chars)", flush=True)


if __name__ == "__main__":
    main()
