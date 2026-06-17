"""Sidequest: how to conceptually SIMPLIFY poker's expensive computations. gpt-5.5 (the best poker reasoner,
per the user) proposes non-obvious CS/math/ML simplifications + reviews our logic + tackles multiplayer/
positions; then Claude VETS which are real and how to integrate them into OUR engine. GOAL = LESS compute and
LESS conceptual complexity, never more. Run: python -m extraction.simplify_consult
"""
from __future__ import annotations

from pokerbot import config

GPT_MODEL = "gpt-5.5"

SYSTEM = (
    "You are a world-class poker-AI researcher who is ALSO a CS/math/ML theorist (abstraction, sufficient "
    "statistics, function approximation, game theory, numerical methods) and a brutally honest engineer. The "
    "user's GOAL is SIMPLIFICATION: reduce the COMPUTE and the conceptual complexity of the bot, NOT add "
    "sophistication. Every idea must (1) measurably REDUCE calculation burden or state complexity, (2) fit a "
    "modest Python engine, (3) be VERIFIABLE. Prefer established, under-used-in-poker tools over novelty. "
    "Flag anything that is hype or that would ADD complexity. Be concrete enough to implement."
)

BRIEF = """\
OUR BOT (the relevant compute + complexity):
- Per-decision MONTE-CARLO equity (equity_vs_range / equity_vs_class_range, ~120-1500 sims each) is the main
  runtime cost. Hand strength = treys 7-card eval. Ranges = hand-class percentiles (ps.range_top).
- Postflop = equity + pot-odds/MDF + fold-equity-optimal sizing + a bounded exploit overlay (bluff/value/
  foldcatch nudges from a stat-keyed rule set). Preflop = CFR push/fold (short) + a solver-distilled GTO
  lookup table (PokerBench, 88.6%).
- GTO ground truth = TexasSolver caches (flops/turns). A self-play->GTO net (Deep-CFR, Supremus CFVnet recipe)
  is the planned floor upgrade.
- 6-MAX = each of 6 seats decides INDEPENDENTLY from its own cards (no joint/opponent-coupled model);
  positions handled by per-position open/defend ranges.

THE QUESTION (find the GOLD): poker is astronomically complex if attacked by brute force. Which ESTABLISHED
systems from CS / mathematics / modern ML -- ones NOT obvious to ordinary poker theorists -- let us
CONCEPTUALLY SIMPLIFY the expensive thinking tasks so our bot AND its calculations get SIMPLER? Concepts poker
already uses (pot odds, ranges, MDF) are the spirit; we want the next layer.

Answer concretely, each item: {name; the CS/math/ML idea in 1-2 sentences; what expensive poker computation it
REPLACES/COMPRESSES; the COMPLEXITY/COMPUTE reduction (e.g. MC -> closed form, 1326 combos -> k buckets, tree
-> sufficient statistic); how it fits our engine; a VERIFICATION; any ACCURACY cost}. Cover at least:
- replacing per-decision Monte-Carlo equity with something cheaper + as accurate (closed form / precomputed /
  amortized-net / low-dimensional features).
- compressing the hand/range/board space (abstraction, suit isomorphism, clustering, sufficient statistics).
- representing strategy compactly (low-rank / few features) instead of huge tables.
- MOST IMPORTANT: how to understand MULTIPLE PLAYERS and POSITION with this simplifying mindset (e.g.
  mean-field / population game theory, potential games, position as a low-dimensional parameter) so 6-max does
  not blow up combinatorially.

ALSO: flag any CORRECTNESS errors or conceptual mistakes in the bot's approach above.

HARD CONSTRAINTS: do NOT make the model more complicated than it is; do NOT go off course (it must serve THIS
bot). Rank your ideas by (simplification gained / effort). Be brutally honest about which are real GOLD vs
nice-to-have vs hype.
"""


def ask_gpt() -> str:
    from openai import OpenAI
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": BRIEF}]
    # gpt-5.5 is a REASONING model: max_completion_tokens caps reasoning + output together, so give plenty of
    # headroom and a moderate effort, else the visible answer returns empty (reasoning ate the whole budget).
    for kw in ({"reasoning_effort": "medium", "max_completion_tokens": 32000},
               {"max_completion_tokens": 32000}, {}):
        try:
            r = client.chat.completions.create(model=GPT_MODEL, messages=msgs, **kw)
            txt = r.choices[0].message.content or ""
            if txt.strip():
                return txt
            print(f"(empty content, finish={r.choices[0].finish_reason}, kw={list(kw)})", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"(gpt err kw={list(kw)}: {type(e).__name__}: {str(e)[:90]})", flush=True)
    return ""


def ask_claude(gpt_text: str) -> str:
    from anthropic import Anthropic
    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    prompt = ("A frontier model (gpt-5.5) proposed these SIMPLIFYING concepts for our poker bot. Your job: "
              "(1) VET each -- which are genuinely real + applicable to OUR engine vs hype / over-complex; "
              "(2) for the real ones, give the CONCRETE integration into our modules (which file/function "
              "changes), SMALLEST-first, each with its grounded verification; (3) flag any that would ADD "
              "complexity (the user forbids that) or go off course. Be brutally honest; end with the single "
              f"highest-ROI simplification to do first.\n\nOUR BOT:\n{BRIEF}\n\nGPT-5.5 PROPOSAL:\n{gpt_text}")
    r = client.messages.create(model=config.CLAUDE_MODEL, max_tokens=8000, system=SYSTEM,
                               messages=[{"role": "user", "content": prompt}])
    return "".join(b.text for b in r.content if getattr(b, "type", None) == "text")


def main() -> None:
    out = config.ROOT / "docs"
    print("=== gpt-5.5 (simplification concepts + logic review) ...", flush=True)
    g = ask_gpt()
    (out / "simplify_gpt55.md").write_text(f"# Simplification consult — OpenAI {GPT_MODEL}\n\n{g}\n",
                                           encoding="utf-8")
    print(f"  saved docs/simplify_gpt55.md ({len(g)} chars)", flush=True)
    if not g.strip():
        print("  gpt-5.5 returned EMPTY -- aborting Claude vet (fix the call first)", flush=True)
        return
    print("=== Claude Opus (vet + integration) ...", flush=True)
    c = ask_claude(g)
    (out / "simplify_claude.md").write_text(
        f"# Simplification vet + integration — Claude {config.CLAUDE_MODEL}\n\n{c}\n", encoding="utf-8")
    print(f"  saved docs/simplify_claude.md ({len(c)} chars)", flush=True)


if __name__ == "__main__":
    main()
