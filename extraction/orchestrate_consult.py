"""Consult gpt-5.5 (best poker reasoner) on HOW to orchestrate an iterative small-run improvement loop for our
bot, GPU vs CPU for our CFR, and the 'neural net as connecting INTERFACE logic' idea (insert the net only
where it's actually useful, not a from-scratch GTO train). Grounded in our MEASURED numbers. Output ->
docs/orchestrate_gpt55.md for the plan. Run: python -m extraction.orchestrate_consult
"""
from __future__ import annotations

from pokerbot import config

GPT_MODEL = "gpt-5.5"

SYSTEM = (
    "You are a world-class poker-AI researcher AND a pragmatic ML-systems engineer, brutally honest. Ground "
    "EVERY answer in the specific MEASURED facts given. The user has a $70 budget and wants a WORKING iterative "
    "improvement loop (hypothesis -> small short run -> inspect -> adjust in real time), NOT a research-scale "
    "mega-train. Distinguish sharply what GENUINELY needs a neural net from what exact/heuristic/tabular methods "
    "already do better+cheaper. Every recommendation states the concrete SIGNAL that proves it worked. No hype."
)

BRIEF = """\
OUR BOT (measured, real):
- HU + 6-max NLHE. A GTO FLOOR (solver-calibrated preflop lookup table 88.6%, heuristic postflop = MC equity +
  pot-odds/MDF + fold-equity sizing, now EXACT river equity by enumeration) + a BOUNDED exploit OVERLAY (62
  stat-keyed book rules -> bluff/value/foldcatch frequency nudges, confidence-weighted, capped).
- MEASURED vs Slumbot (near-GTO, ~400 hands each, noisy): floor exploit-OFF ~ -97 +/-110 bb/100; WITH the
  exploit overlay ~ +49 +/-69 bb/100. The exploit EDGE is healthy (crushes the exploitable field +300..+1100);
  the FLOOR is the weak part vs near-GTO (you cannot beat GTO, only minimize loss).
- DATA WE ALREADY HAVE: TexasSolver GTO caches (many flops + some turns), 563k PokerBench labeled GTO
  decisions, the 88.6% preflop table.

SELF-PLAY / CFR STATUS (just measured):
- Leduc Hold'em: our CFR+ (exact, full-tree) exploitability falls 1300 -> 16 mbb/hand MONOTONE = converges to
  Nash. (We just FIXED a clairvoyant best-response bug that had hidden all convergence.)
- NLHE: OpenSpiel Deep-CFR (universal_poker, fcpa abstraction = fold/call/pot/allin) RUNS + LEARNS on a GPU pod
  (vs a check-call station: -519 -> +1136 chips/hand after 40 iters). BUT it is CPU-BOUND: GPU peak memory was
  0.2 GB of 143 (idle), ~47 traversals/sec single-threaded Python. A strong GPU barely helps; the bottleneck is
  the Python game-tree traversal.
- Budget: ~$70 of RunPod credit. Cheap GPU ~$0.33/hr, H200 $4.39, B200 $5.98.

WHAT WE WANT TO DO (the user's framing):
1. An ITERATIVE loop: form HYPOTHESES about where the bot has gaps -> run SMALL SHORT experiments -> inspect the
   output -> adjust the model in REAL TIME. Be sure it works on small runs before any longer run.
2. End state: we mostly improve the EXISTING bot, and insert a neural net ONLY as "connecting INTERFACE logic"
   for the parts where a net is actually useful -- we do NOT necessarily train a full GTO net from scratch.

QUESTIONS (answer each concretely, each with the SIGNAL that proves it, grounded in the above):
Q1. GPU vs CPU for OUR CFR/self-play, given it is CPU-bound + the $70 budget + the small-iterative-run workflow.
    Pros/cons of each. Should we even keep Python Deep-CFR (GPU), or switch substrate (parallel CPU external-
    sampling MCCFR / OpenSpiel C++ solvers / tabular on the small fcpa abstraction)? Give ONE recommendation.
Q2. ORCHESTRATE the iterative loop. (a) The single most reliable SIGNAL to read after each small run to decide
    keep/revert (given small-sample bb/100 is noise, but we have exact Leduc exploitability, solver TV-gap,
    duplicate-poker variance reduction, held-out PokerBench match). (b) The loop structure. (c) 3-5 concrete
    starting HYPOTHESES about our biggest gaps + the cheap experiment that tests each.
Q3. The "NET AS CONNECTING INTERFACE LOGIC" idea -- be concrete. WHERE is a neural net genuinely the right tool
    (e.g. a leaf-value evaluator for depth-limited re-solving, an interpolator/generalizer over our solved-spot
    caches, a blueprint that local search refines) vs WHERE exact enumeration / tabular lookup / heuristics are
    already better+cheaper? Give the MINIMAL net-as-glue that connects our EXISTING parts (solver caches +
    lookup tables + exploit overlay) WITHOUT a research-scale train -- what exactly does it ingest, what does it
    output, where does it plug into the decision path, and how do we validate it beats the non-net version.
Q4. The concrete ORCHESTRATION PLAN that fits $70 and "validate small first": the substrate (Q1), the loop (Q2),
    the net-as-interface target (Q3), and the FIRST 2-3 small runs with explicit success criteria + rough cost.

Be specific and brutally honest. If the net is NOT worth it for some part, say so. If $70 is plenty (or not),
say which.
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
    print(f"=== querying {GPT_MODEL} (orchestration + net-as-interface) ...", flush=True)
    g = ask_gpt()
    out = config.ROOT / "docs" / "orchestrate_gpt55.md"
    out.write_text(f"# Orchestration consult — OpenAI {GPT_MODEL}\n\n{g}\n", encoding="utf-8")
    print(f"saved {out} ({len(g)} chars)", flush=True)


if __name__ == "__main__":
    main()
