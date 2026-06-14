"""PHASE 1 of the synthesis plan: ask BOTH frontier models (Claude Opus 4.8 + OpenAI gpt-5.1), INDEPENDENTLY,
the same comprehensive brief: given EXACTLY our assets, what's the best bot we can build NOW, how to synthesize
all the data, and what to do with our own trained LLM's knowledge. Responses saved for hand-synthesis. The
brief carries our HARD-WON LESSONS so the models can't hand us hype we've already measured to be false.

Run:  python -m extraction.synthesis_consult
"""
from __future__ import annotations

from pokerbot import config

SYSTEM = (
    "You are a world-class poker-AI architect and ML researcher (CFR/MCCFR, Deep-CFR, solver distillation, "
    "LLM fine-tuning, exploitative play and opponent modeling) who is ALSO a rigorous, brutally honest "
    "engineer. Reason concretely and grounded in the specific assets provided. Do NOT overclaim and do NOT "
    "give unfalsifiable advice: EVERY recommendation must state how to VERIFY it with the assets at hand "
    "(a solver gap, a held-out metric, a variance-reduced A/B, an exploitability bound). Prefer correctness "
    "over optimism. Distinguish heads-up (2p zero-sum, solvable to epsilon) from 6-max (general-sum, "
    "PPAD-hard, non-unique Nash). Be specific enough that an engineer can implement your answer this week."
)

BRIEF = """\
PROJECT — a Heads-Up AND 6-max No-Limit Hold'em bot (Python). North star: a UNIVERSAL ADAPTIVE EXPLOITER =
a low-exploitability GTO "floor" + an online opponent-modeling exploit layer that is confidence-gated, built
to beat opponents we have not seen. We are NOT trying to imitate any one bot (each is an exploitable GTO
approximation; imitating one is a ceiling).

IMMEDIATE GOAL: the BEST bot we can build RIGHT NOW by SYNTHESIZING ALL the data/assets below. "Right now"
means: no waiting on a months-long from-scratch neural net; use what we already have. Tell us the highest-EV
synthesis.

================ ASSETS WE ALREADY HAVE (use ALL of them) ================
A. LABELED GTO DECISIONS — RZ412/PokerBench: 563,200 6-max spots, templated natural-language state ->
   GTO action (e.g. "fold" / "call" / "raise 35" / "bet 23"), 100bb. Parses 100% into structured spots.
B. SOLVER GROUND-TRUTH (TexasSolver) caches we computed: ~1340 solved flops @100bb (_gto_bench_cache);
   ~143 broad boards across 3 stack depths (_gto_cover_cache); +184 freshly-solved turn boards (GCP);
   a 209MB HU-turn solve cache. These are EXACT GTO at the solved nodes.
C. HAND HISTORIES — 10k Pluribus hands (+ mined stats and exploitable-leak tables); a Slumbot fold-vs-bet-
   size curve we probed.
D. BOOK KNOWLEDGE — 5 poker books. Extracted to JSON: (1) Modern Poker Theory [Acevedo, GTO ranges/
   principles], (2) No Limit Hold'em: Theory & Practice [Sklansky/Miller], (3) The Theory of Poker
   [Sklansky], (4) The Mathematics of Poker [Chen & Ankenman]. NOT yet extracted (PDF only): (5) "Beyond
   GTO: Poker Exploits Simplified" — an EXPLOITATION-focused book, directly relevant to our edge.
E. EXPLOIT ARTIFACTS — a pre-generated exploit "playbook": 11,500 Claude-Haiku bounded exploit directives +
   240 Claude-Opus coarse ones (target spot, action, freq_delta in [-0.3,0.3], confidence), intended as a
   cold-start prior via nearest-opponent-profile lookup.
F. OUR OWN TRAINED LLMs — Qwen LoRA fine-tunes on PokerBench: an 8B (decision-match 18.3% base -> 71.7%
   after LoRA on ~100k rows) and a 32B bf16 (only ~25k rows due to a budget cap; held-out action-match ~62%
   on a stricter eval, and it skews PASSIVE — checks instead of betting, folds instead of raising). The two
   numbers are NOT directly comparable (different eval harness/data size).
G. THE EXISTING BOT (heuristic, fast, no LLM in play) — analytic GTO baseline (texture- and aggressor-aware
   c-bet), a CFR push/fold blueprint (verified Nash for short stacks), postflop = Monte-Carlo equity +
   pot-odds/MDF + fold-equity-optimal bet sizing + blockers, an online opponent model, an adaptive exploit
   engine with a calibration loop, and per-opponent exploit models. A dormant numeric postflop spec
   (knowledge_base/postflop/openai_strategy.json) the code does not yet fully read.

================ MEASURED, HONEST STATUS ================
- Our true weakness: we are a strong EXPLOITER WITHOUT a real GTO floor. vs near-GTO Slumbot, the fixed
  heuristic floor loses ~ -46 bb/100 (no exploit) and ~ -5.4 bb/100 (with the fold-curve exploit; ~break-even
  but not yet conclusive). That -deficit IS our own exploitability. We CRUSH weak/exploitable opponents
  (+300..+700 bb/100). vs near-GTO the realistic ceiling is ~break-even (you cannot beat GTO, only minimize
  loss); vs the field the edge is large.
- 6-max NLHE is provably NOT "solvable" like HU (PPAD-hard, non-unique Nash, CFR only reaches a CCE). So the
  sound target is a bounded-exploitability blueprint + a verified adaptive exploit, judged by MEASURED
  exploitability (LBR) and realized bb/100 — never a "solve".

================ HARD-WON LESSONS (do NOT contradict these; we measured them) ================
1. LLM triage = HYPOTHESES ONLY. An LLM audit once flagged its own top "leak" which measurement then refuted.
2. Small-sample raw bb/100 is NOISE. Two plausible single-rule fixes (thin-value, draw-c-bet) looked good and
   were REVERTED after grounded measurement disproved them.
3. ONLY a grounded signal gates a change: solver TV-gap, a held-out metric, AIVAT/duplicate-poker variance
   reduction, or an exploitability (LBR) bound. "Language proposes, math disposes."
4. Exploitation is the edge, not GTO imitation. The floor is insurance (stop bleeding to near-GTO); the
   money is in exploiting each opponent's deviation, safely + bounded.
5. For PRECISION, exact data (solver labels, PokerBench labels) BEATS our LLM's generated outputs (62-72%).

================ QUESTIONS — answer EACH concretely, each with a VERIFICATION method ================
Q1. ARCHITECTURE NOW: Given EXACTLY assets A-G, what is the single best bot we can assemble in ~1-2 weeks
    (no from-scratch net)? Be concrete about the floor (how to build it from solver caches + PokerBench +
    books WITHOUT deploying the LLM in play) and the exploit overlay. Give the data flow.
Q2. DATA SYNTHESIS: How should we weight/combine A-G? Which sources build the floor, which seed exploitation,
    which inform reasoning? Where do they conflict and who wins? How to turn 563k PokerBench rows + the solver
    caches into fast, queryable bot parameters/tables (distillation/lookup/calibration)?
Q3. OUR LLM's KNOWLEDGE: We suspect the 32B/8B LoRA should NOT be deployed in play (slow, ~62-72%). Is that
    right? Concretely, what is the best use of its KNOWLEDGE as SECOND-HAND data/insight — e.g. generate GTO
    references for spots the solver/PokerBench do not cover, then distill into the heuristic bot? a curriculum
    director? an async per-session exploit proposer? Or is it not worth it given exact data exists? Decide.
Q4. THE EXPLOIT BOOK: Should we extract "Beyond GTO: Poker Exploits Simplified" (book 5), and exactly how
    would its content plug into the exploit overlay / opponent model? What concrete exploit primitives to mine.
Q5. RANKED PLAN: Give the highest-EV concrete steps, ranked, each with (a) which assets it uses, (b) the
    grounded gate that proves it worked, (c) rough effort. Flag anything you are UNSURE about as a hypothesis.

Be specific and honest. If something we have is low-value, say so. If we are missing something cheap and
high-impact, say that too.
"""


def ask_claude() -> str:
    from anthropic import Anthropic
    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    r = client.messages.create(model=config.CLAUDE_MODEL, max_tokens=8000,
                               system=SYSTEM, messages=[{"role": "user", "content": BRIEF}])
    return "".join(b.text for b in r.content if getattr(b, "type", None) == "text")


def ask_openai() -> tuple[str, str]:
    from openai import OpenAI
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    try:
        ids = {m.id for m in client.models.list().data}
    except Exception:  # noqa: BLE001
        ids = set()
    model = next((m for m in (([config.OPENAI_MODEL] if config.OPENAI_MODEL else []) +
                              config.OPENAI_MODEL_PREFERENCE) if m and (not ids or m in ids)), "gpt-4o")
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": BRIEF}]
    try:
        r = client.chat.completions.create(model=model, messages=msgs, max_completion_tokens=8000)
    except Exception as e:  # noqa: BLE001
        print(f"(openai retry minimal: {type(e).__name__})", flush=True)
        r = client.chat.completions.create(model=model, messages=msgs)
    return model, r.choices[0].message.content


def main() -> None:
    out = config.ROOT / "docs"
    out.mkdir(exist_ok=True)
    print("=== querying Claude Opus 4.8 ...", flush=True)
    try:
        ctext = ask_claude()
        (out / "synthesis_claude.md").write_text(f"# Synthesis consult — Claude {config.CLAUDE_MODEL}\n\n{ctext}\n", encoding="utf-8")
        print(f"  saved docs/synthesis_claude.md ({len(ctext)} chars)", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"  CLAUDE FAILED: {type(e).__name__}: {e}", flush=True)
    print("=== querying OpenAI gpt-5.1 ...", flush=True)
    try:
        model, otext = ask_openai()
        (out / "synthesis_openai.md").write_text(f"# Synthesis consult — OpenAI {model}\n\n{otext}\n", encoding="utf-8")
        print(f"  saved docs/synthesis_openai.md ({len(otext)} chars, model={model})", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"  OPENAI FAILED: {type(e).__name__}: {e}", flush=True)


if __name__ == "__main__":
    main()
