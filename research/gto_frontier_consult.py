"""GTO-frontier strategic consult. The big questions: what does our bot understand about GTO that other GTO
bots (Slumbot/Pluribus/solvers) don't? where does true 100% GTO lie + how far are we? biggest high-leverage
move? the MATH; ML-process optimization; is LEAN/formalization worth it? Routing (per the user):
  - POKER/GTO  -> gpt-5.5   (strongest poker reasoner)
  - REASONING  -> o3        (math / ML-process / approximation theory / formal methods)
  - TECHNICAL  -> Claude    (vets BOTH, gives concrete codebase implementation)
Vet everything for hallucination before acting. Run: python -m extraction.gto_frontier_consult
"""
from __future__ import annotations

from pokerbot import config

GPT_POKER = "gpt-5.5"
O3 = "o3"

BRIEF = """\
OUR BOT (heads-up + 6-max NLHE; described honestly, measured not hyped):
- PREFLOP: CFR push/fold (verified Nash, short stacks) + strength-model ranges (deeper) + a PokerBench-
  distilled GTO lookup table (88.6% action match).
- POSTFLOP FLOOR (history-free, GTO-grounded): per-texture donk/c-bet frequencies extracted from a TexasSolver
  cache; a supervised "advisor" MLP that predicts the SOLVER's P(bet) per hand from blocker/potential features,
  confidence-gated into the bet decision -- FLOP (+43% vs the frequency-only baseline, held out by board) and
  TURN (+20% over 87k held-out turn boards, trained on a fresh 1825-board turn-coverage solve); RIVER is
  blocker-aware (frequency-preserving bluff SELECTION + a small bluffcatch-threshold nudge, theory-grounded,
  not yet solver-calibrated). Equity = Monte-Carlo, exact river enumeration. Defense = pot-odds/MDF shaded by
  villain bluffiness. Sizing = fold-equity-optimal.
- EXPLOIT LAYER (online): an adaptive exploiter + a 62-rule book overlay that nudges bluff/value/foldcatch
  ONLY from live-measured opponent stats (vpip, fold-to-bet, aggression-freq), with a confidence-gated fallback
  to the floor. Per-opponent models for Slumbot (learned fold curve) + Pluribus.
- GROUND TRUTH + GATES: TexasSolver caches (flops + the 1825-board turn solve). Changes are gated by the SOLVER
  EV-gap / frequency-match / held-out MSE / a deterministic check -- NOT by noisy realized bb/100 (Slumbot
  +-110 over 100h). Two plausible heuristic fixes were REVERTED after measurement refuted them.
- MEASURED: vs Slumbot (near-GTO) ~break-even (floor -14.6, exploit +2.2 bb/100 over 500h, both within noise);
  crushes weak/exploitable bots (+300-700). Our LBR exploitability tool is currently TOO WEAK to bound us
  (it loses to our bot -> vacuous lower bound).
- NOT a real-time solver: no continuous re-solving in play; the HU floor is supervised-over-solver-caches +
  analytic heuristics + an online exploit overlay, NOT a from-scratch CFR equilibrium. 6-max: each seat decides
  independently from its own cards (no joint/opponent-coupled model); positions via per-position ranges.

THESIS: no deployed bot plays TRUE GTO (all are approximations: Slumbot = HU CFR with card abstraction, no
real-time solving; Pluribus = blueprint + depth-limited search; commercial solvers = offline, abstraction-
bounded, single-spot). Our intended edge = a robust low-exploitability blueprint + an ONLINE universal adaptive
exploiter that detects + safely exploits each opponent's gap to GTO, with a confidence-gated fallback. Project
phase = CONSOLIDATION/PRUNING: mesh existing parts, eradicate leaks, do NOT add complexity for its own sake.
"""

POKER_SYSTEM = (
    "You are the world's strongest No-Limit Hold'em GTO reasoner AND a brutally honest game-theory analyst. "
    "Answer concretely and quantitatively where possible, ground every claim in real poker/game-theory facts, "
    "and explicitly flag where the bot is fooling itself. No hype, no generic advice -- it must serve THIS bot."
)

POKER_Q = BRIEF + """

ANSWER THESE (concretely, ranked by edge-gained / effort, brutally honest):
1. WHAT DOES OUR BOT UNDERSTAND / DO ABOUT GTO THAT OTHER GTO BOTS DON'T? Where are the STRUCTURAL blind spots
   of Slumbot, Pluribus, and raw solvers (card-abstraction error, NO real-time solving, STATIC blueprints, NO
   in-game adaptation, single-spot myopia)? Be specific about each one's residual gap to 100% GTO and how our
   design can convert that gap into EV.
2. WHERE DOES TRUE 100% GTO ACTUALLY LIE relative to these approximations, and how do we ESTIMATE the remaining
   gap in practice (AIVAT-reduced eval, a correctly-implemented LBR, solver tree-value gap)? Give the rough
   magnitudes you'd expect (mbb/100) for HU NLHE.
3. HOW DO WE CREDIBLY PULL AHEAD OF ALL OF THEM? Against near-GTO the HU ceiling is ~break-even; the field is
   huge. What is THE single biggest HIGH-LEVERAGE move for our specific architecture (floor vs edge vs eval)?
4. THE MATH -- go through the key mathematical questions of our approach and find what we get subtly WRONG or
   approximate in an EV-costing way: equity (MC variance vs exact vs closed-form), range/board ABSTRACTION
   error, MDF/indifference + when it's the wrong model, blocker/card-removal EXACTNESS, the BIAS of a
   supervised net imitating solver caches (mixing-strategy averaging, off-tree generalization), and whether
   our confidence-gated blend is theoretically sound. For each: the rigorous fix.
"""

O3_SYSTEM = (
    "You are a rigorous researcher in game theory, machine learning, numerical methods, and formal verification. "
    "Reason carefully and quantitatively, cite the actual theory (regret bounds, PPAD, epsilon-Nash, AIVAT, "
    "abstraction error), and give an HONEST cost/benefit. Distinguish high-leverage from intellectually-"
    "appealing-but-low-ROI. It must serve THIS specific bot, not be a generic literature review."
)

O3_Q = BRIEF + """

REASON RIGOROUSLY ABOUT:
1. ML-PROCESS / ALGORITHM OPTIMIZATION for THIS bot. Our floor = a supervised MLP imitating solver caches
   (the "advisor"); a self-play->GTO net (Deep-CFR / CFR+ / Supremus-style CFVnet) is the planned upgrade.
   What is the RIGHT learning objective (exploitability vs imitation/MSE loss vs realized EV), and how do we
   optimize quality-per-compute: card/range ABSTRACTION (potential-aware bucketing), data efficiency, CFR
   variant choice (LCFR/DCFR/MCCFR/Deep-CFR/ReBeL), distillation, VARIANCE REDUCTION (AIVAT / baselines),
   and ONLINE/continual learning for the exploiter? Where is our supervised-imitation approach
   theoretically WEAK vs an equilibrium-finding method, and is the gap worth closing?
2. WHERE 100% GTO LIES + BOUNDING OUR DISTANCE: approximation/abstraction-error theory, epsilon-Nash, the
   exploitability lower bound (LBR done right) vs computable upper bounds, and what is actually tractable for
   HU vs 6-max (multiplayer general-sum: PPAD-hardness, CCE vs Nash, why exploitability isn't a clean scalar).
   How should we MEASURE progress so the metric isn't noise?
3. LEAN / FORMAL METHODS: would formalizing the poker MATHEMATICS in LEAN (or another proof assistant)
   MEASURABLY increase the bot's quality/EV? Be specific about WHAT would be worth formally verifying (equity
   enumeration correctness; CFR/CFR+ convergence + regret bounds; MDF/indifference; side-pot accounting;
   the advisor's calibration) vs what is rigor-for-rigor that will NOT move EV. Give an honest cost/benefit,
   and if LEAN is overkill, the sharper alternative (property-based tests, exact-solver cross-checks, etc.).
RANK everything by (quality/EV gained per unit effort). Be honest about what is hype.
"""


def ask_openai(model: str, system: str, user: str, effort: str = "high", cap: int = 45000) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    for kw in ({"reasoning_effort": effort, "max_completion_tokens": cap},
               {"reasoning_effort": "medium", "max_completion_tokens": cap},
               {"max_completion_tokens": cap}, {}):
        try:
            r = client.chat.completions.create(model=model, messages=msgs, **kw)
            txt = r.choices[0].message.content or ""
            if txt.strip():
                return txt
            print(f"({model} empty, finish={r.choices[0].finish_reason}, kw={list(kw)})", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"({model} err kw={list(kw)}: {type(e).__name__}: {str(e)[:140]})", flush=True)
    return ""


def ask_claude(poker: str, reason: str) -> str:
    from anthropic import Anthropic
    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    system = ("You are a brutally honest senior engineer who knows THIS poker bot's codebase. Vet frontier-model "
              "analysis for hallucination, separate real high-leverage from hype, and translate the survivors into "
              "concrete, smallest-first changes in our actual modules with grounded (solver-EV-gap / held-out-MSE "
              "/ deterministic) verifications. The project is in a consolidation/pruning phase: no complexity for "
              "its own sake.")
    prompt = (f"OUR BOT:\n{BRIEF}\n\n=== gpt-5.5 (poker/GTO frontier) said ===\n{poker}\n\n"
              f"=== o3 (math / ML-process / formal methods) said ===\n{reason}\n\n"
              "YOUR JOB (technical implementation):\n"
              "1. VET both -- which specific claims are real AND applicable to our actual codebase vs generic / "
              "hype / over-complex / already-done? Call out any hallucinated facts.\n"
              "2. For the genuine high-leverage moves, give the CONCRETE implementation: which file/function, "
              "smallest-first, each with its grounded verification (our gate = solver EV-gap / held-out MSE / a "
              "deterministic check, NOT noisy bb/100).\n"
              "3. Deliver THE single biggest high-leverage move with a concrete step plan.\n"
              "4. Honest verdict on LEAN/formalization FOR US: worth it or not, and what (if anything) to verify.\n"
              "Brutally honest; flag anything that would add complexity or go off course.")
    r = client.messages.create(model=config.CLAUDE_MODEL, max_tokens=12000, system=system,
                               messages=[{"role": "user", "content": prompt}])
    return "".join(b.text for b in r.content if getattr(b, "type", None) == "text")


def main() -> None:
    out = config.ROOT / "docs"
    out.mkdir(exist_ok=True)
    print(f"=== {GPT_POKER} (poker / GTO frontier) ...", flush=True)
    poker = ask_openai(GPT_POKER, POKER_SYSTEM, POKER_Q)
    (out / "frontier_poker_gpt55.md").write_text(f"# GTO frontier — poker/GTO ({GPT_POKER})\n\n{poker}\n", encoding="utf-8")
    print(f"  saved docs/frontier_poker_gpt55.md ({len(poker)} chars)", flush=True)

    print(f"=== {O3} (math / ML-process / formal methods) ...", flush=True)
    reason = ask_openai(O3, O3_SYSTEM, O3_Q)
    (out / "frontier_reason_o3.md").write_text(f"# GTO frontier — reasoning/math/LEAN ({O3})\n\n{reason}\n", encoding="utf-8")
    print(f"  saved docs/frontier_reason_o3.md ({len(reason)} chars)", flush=True)

    if not (poker.strip() or reason.strip()):
        print("  both OpenAI calls EMPTY -- fix before the Claude vet", flush=True)
        return
    print(f"=== Claude {config.CLAUDE_MODEL} (vet + technical implementation) ...", flush=True)
    tech = ask_claude(poker, reason)
    (out / "frontier_tech_claude.md").write_text(f"# GTO frontier — vet + implementation (Claude {config.CLAUDE_MODEL})\n\n{tech}\n", encoding="utf-8")
    print(f"  saved docs/frontier_tech_claude.md ({len(tech)} chars)", flush=True)


if __name__ == "__main__":
    main()
