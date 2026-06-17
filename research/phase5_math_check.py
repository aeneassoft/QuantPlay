"""Double-check the Phase-5 (neural self-play) MATH with OpenAI gpt-5.1 BEFORE spending pod time.
Run: python -m extraction.phase5_math_check  -> saves knowledge_base/theory/phase5_math_check.md
"""
from __future__ import annotations

from openai import OpenAI

from pokerbot import config

client = OpenAI(api_key=config.OPENAI_API_KEY)
OUT = config.KNOWLEDGE_DIR / "theory" / "phase5_math_check.md"

PLAN = """
PHASE-5 PLAN TO VERIFY (a neural self-play poker net trained on a GPU pod):

A) CORE: Deep CFR (neural CFR, Brown 2019) self-play on ABSTRACTED Heads-Up NLHE via OpenSpiel
   universal_poker. Action abstraction = a few bet sizes (e.g. fold/call + {0.5p, 1p, all-in} or fcpa).
   Cards fed as features to the net (no card bucketing). 200bb, 50/100 blinds (to match Slumbot).
   We VALIDATED the exact OpenSpiel PyTorch Deep CFR pipeline on Leduc: nash_conv fell 2.33 -> 0.33
   (device='cuda', advantage_network_train_steps~750, lr 1e-3; we patched an OpenSpiel cuda bug in
   action_probabilities; print_nash_convs works).

B) WARM-START: initialise/pre-train from near-GTO BOT hand histories (ACPC HU-NL ~278M hands +
   Pluribus 10k, hole cards known) via behavioural cloning, then continue with Deep CFR self-play.

C) CRUSH POPULATION: also train a best-response/exploit head against calibrated EXPLOITABLE opponents
   derived from real data (e.g. an online-cash population profile we already beat +182 bb/100), so ONE
   net is both near-GTO-robust AND crushes the exploitable field. Combine via a regime/blend.

D) EVALUATION: nash_conv on the abstracted game; head-to-head vs Slumbot (live API, AIVAT variance
   reduction); vs the calibrated population. Our analytic GTO baseline currently does -100 bb/100 vs
   Slumbot (±113, 350 hands); GTO Wizard beats Slumbot by ~19.4 bb/100 (so Slumbot break-even ≈ 19
   below SOTA).

E) CLAUDE META-COACH: at each checkpoint, an LLM reviews win-rates + sample losing hands + frequency-
   vs-GTO and suggests curriculum/reward/hyperparameter changes (meta-level, not per-hand).
"""

QUESTION = """
Rigorously DOUBLE-CHECK the mathematics/soundness, in German, concise but precise:

1) Is the Deep CFR self-play on this abstracted NLHE mathematically sound and CONVERGENT? What
   exploitability is realistic, and how big is the abstraction error (ε_abstraction) — does the
   Leduc result transfer? Any correctness pitfalls in external-sampling MCCFR + neural advantage nets
   we must respect (regret targets, reservoir buffers, reinit, averaging)?
2) WARM-START by behavioural cloning from bot hand histories then Deep CFR: is this a valid prior, or
   does it BIAS/break CFR's convergence guarantees? How to do it correctly (or is pure self-play
   safer)? Off-policy concerns?
3) CRUSH-POPULATION: is "train ONE net to be near-GTO AND max-exploit a fixed opponent" mathematically
   coherent? Best-response to a fixed opponent vs an equilibrium objective conflict — how to combine
   without breaking GTO-robustness (the (1-λ)GTO + λ·exploit blend, exploitability budget)? Is a
   SEPARATE exploit policy + a regime switch cleaner than one mixed net?
4) EVALUATION: we cannot compute exact nash_conv on full NLHE. Is abstracted-game nash_conv + live
   head-to-head (Slumbot, AIVAT) a valid GTO-quality proxy? Give a correct, LIGHTWEIGHT AIVAT we can
   actually implement (what baseline value function, what residual).
5) Give a CONCRETE, sane config for the pod run: action abstraction, info-state features, net sizes,
   num_iterations, num_traversals, train_steps, lr, memory, and a rough COMPUTE estimate (GPU-hours)
   to reach a useful (Slumbot-competitive) net — or honestly say if that's infeasible in hours.
6) Any FATAL flaw that would waste the pod run? What is the single highest-risk assumption?
"""


def main() -> None:
    om = config.OPENAI_MODEL or "gpt-5.1"
    print(f"=== OpenAI {om} — Phase-5 math double-check ===\n")
    r = client.chat.completions.create(
        model=om, max_completion_tokens=6000,
        messages=[{"role": "system", "content": "You are a rigorous game-theory + deep-RL "
                   "mathematician (CFR, Deep CFR, best response, exploitability, AIVAT). Be precise, "
                   "flag errors bluntly, give concrete numbers. Answer in German."},
                  {"role": "user", "content": PLAN + "\n" + QUESTION}])
    out = (r.choices[0].message.content or "").strip()
    print(out)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(f"# Phase-5 math double-check (OpenAI {om})\n\n{out}\n", encoding="utf-8")
    print(f"\n\nSaved -> {OUT}")


if __name__ == "__main__":
    main()
