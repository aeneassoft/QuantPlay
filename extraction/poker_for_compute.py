"""Foundation question (dual-API): how to optimize/adapt poker THEORY for ML + computation, so an hour
of compute beats years of a pro's book-theory. OpenAI=math/CS, Claude=theory/synthesis into our build.
Saves knowledge_base/theory/poker_for_compute.md. Run: python -m extraction.poker_for_compute
"""
from __future__ import annotations

from anthropic import Anthropic
from openai import OpenAI

from pokerbot import config

OUT = config.KNOWLEDGE_DIR / "theory" / "poker_for_compute.md"

CONTEXT = """OUR BOT (PokerB), current foundation:
- Local TexasSolver postflop GTO oracle (fast, exact-in-abstraction) + a scalable GTO-benchmark that
  scores any strategy's 'GTO-gap' over many solved spots (cached, so re-tests are seconds).
- An analytic Chen/MDF baseline, now made initiative/range-aware (caller checks-to-raiser, aggressor
  c-bets wide) — i.e. hand-coded poker theory with tunable thresholds.
- A per-seat online OppModel (public-info-only) + a regime blend sigma=(1-λ)·GTO + λ·exploit with an
  exploitability budget. Exploit↔GTO bridge = node-locking (planned).
- Established findings: the practical shortcut to GTO = continual subgame re-solving + abstraction + a
  (learned) value function + SPR decomposition + DCFR; infinite MUTUAL no-regret exploitation → GTO
  (time-average, 2p zero-sum only); ReBeL/DeepStack = chess-style search over BELIEF states; DeepNash
  (R-NaD) = model-free self-play to Nash WITHOUT explicit ranges. Hardware: 1 GPU pod + many CPU cores.
GOAL: prepare the foundation to launch a pod run (fast self-improvement vs the OSS GTO benchmark, with a
small on-pod model + Claude Haiku as meta-coach)."""

MATH_Q = """Answer rigorously + honestly, in German, concrete:
1) What is the RIGHT COMPUTATIONAL REPRESENTATION of poker so that compute beats human book-theory? Map
   human concepts (ranges, polarisation, MDF, blockers, equity) onto primitives a machine optimises well
   (counterfactual values over belief states, regret/no-regret, self-play, function approximation,
   gradient descent). Where does 1 hour of compute genuinely beat 3 years of a pro (finding exact mixed
   frequencies / leak-curves humans can't), and where does it NOT (priors that save compute)?
2) The user's key idea: in ML we don't need the math functions EXACTLY — we approximate them
   statistically; and conversely, if an analytic formula (Chen, MDF, alpha=s/(1+s)) is too rigid, we
   should RELAX it so the whole system of functions co-fits ('an engine warming up'). Is there a
   PRINCIPLED framework for this? (analytic formulas as priors / initialisation / soft regularisers /
   constraint-annealing in a learned model; Lagrangian relaxation; curriculum). How do we get analytic
   theory + learned approximation to reinforce rather than fight each other?
3) Is there an OPEN-SOURCE 'computation substrate' for game theory analogous to Qiskit for quantum
   (OpenSpiel? others?) — i.e. the right framework/'hardware-sim' for imperfect-info game solving? What
   exactly should we stand on? Is bespoke tooling justified anywhere?
4) Concrete: given our assets, what is the most compute-efficient training objective + representation to
   put on the pod so an hour of compute maximally improves measured GTO-gap AND exploit bb/100?"""

STRAT_Q = """In German, synthesise into our concrete pod foundation — buildable, prioritised:
1) The user's idea: take a famous hand history and have an LLM reason recursive Theory-of-Mind for ALL
   players ('what does he think I think…', how does the decision tree shift). Is this a VALUABLE method
   — to mine concepts, generate training/eval signal, or stress-test our bot — or just a nice essay?
   If valuable, how do we operationalise it (and could it feed the pod run)?
2) Apply the 'relax rigid formulas' idea to OUR baseline: treat the analytic Chen/MDF thresholds as
   PRIORS that an optimiser (search / Haiku-proposed / gradient) tunes against the GTO-benchmark. Sketch
   the self-improvement loop (propose params → benchmark → accept if GTO-gap drops) that we should build.
3) Given all of the above: what EXACTLY should we build/finish to have the foundation 'complete' before
   launching the pod, and in what order? Be concrete (components, not vibes).
4) The single highest-leverage thing to put on the pod first."""


def main() -> None:
    oc = OpenAI(api_key=config.OPENAI_API_KEY)
    ac = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    om = config.OPENAI_MODEL or "gpt-5.1"
    base = CONTEXT + "\n\n"

    print(f"=== OpenAI {om} — MATH/CS ===\n")
    r = oc.chat.completions.create(
        model=om, max_completion_tokens=6000,
        messages=[{"role": "system", "content": "Rigorous ML + computational game-theory researcher "
                   "(CFR/Deep CFR, ReBeL, function approximation, optimisation, OpenSpiel). Precise, "
                   "honest about what compute can and cannot do, cite concrete methods."},
                  {"role": "user", "content": base + MATH_Q}])
    math = (r.choices[0].message.content or "").strip()
    print(math)

    print(f"\n\n=== Claude {config.CLAUDE_MODEL} — STRATEGY ===\n")
    m = ac.messages.create(
        model=config.CLAUDE_MODEL, max_tokens=4500,
        system=("Pragmatic ML systems architect for game-playing AI. Turn theory into a concrete, "
                "ordered build plan. Ruthlessly prioritise; flag what's a distraction."),
        messages=[{"role": "user", "content": base + "OpenAI's take:\n" + math[:4000] + "\n\n" + STRAT_Q}])
    strat = "".join(b.text for b in m.content if getattr(b, "type", None) == "text").strip()
    print(strat)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(f"# Optimising poker theory for ML/computation\n\n## OpenAI {om}\n\n{math}\n\n"
                   f"## Claude {config.CLAUDE_MODEL}\n\n{strat}\n", encoding="utf-8")
    print(f"\n\nSaved -> {OUT}")


if __name__ == "__main__":
    main()
