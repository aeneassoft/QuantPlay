"""Surfing-Uncertainty -> poker-bot consult (2026-07-07): extract the predictive-processing concepts (grounded
from the book, Andy Clark 2016) and ask GPT-5.5 which translate to CONCRETE higher-level math/CS mechanisms for
our HUNL/6-max engine. Honest novelty demanded (is it already solver/RL standard, or genuine leverage?).

Run:  python -m research.surfing_consult
"""
from __future__ import annotations

import json

from research.llm import openai_json

# ---- the grounded concept inventory (extracted from the PDF: ch1-8 + appendices) ----
CONCEPTS = """
Grounded concepts from Andy Clark, "Surfing Uncertainty" (2016) — the Predictive Processing (PP) framework:

1. HIERARCHICAL PREDICTIVE PROCESSING / prediction-error minimization (Ch1). The brain is a multilevel
   generative model; each level predicts the activity of the level below; only the residual PREDICTION ERROR
   propagates upward; perception = the top-down hypothesis that best cancels incoming error.

2. PRECISION-WEIGHTING (Ch2, Ch5). Prediction errors are weighted by their estimated reliability (precision =
   inverse variance). "Attention" = transiently raising precision on selected error channels (gain control).
   Precision sculpts effective connectivity (transient circuits). Pathologies = mis-set precision (over/under-trust).

3. ACTIVE INFERENCE & "DOING WITHOUT COST FUNCTIONS" (Ch4.5, 4.8). Action minimizes prediction error: you act to
   make sensations match predictions. No separate reward/cost function — goals are encoded as strong priors
   (predictions) the system then fulfils by acting.

4. AFFORDANCE COMPETITION (Ch6.5, 8.5). The brain continuously computes MULTIPLE partially-specified action
   possibilities IN PARALLEL and selects among them; perception/planning/action intermingled; "pragmatic"
   representations tuned for control, not world-mirroring.

5. PRODUCTIVE LAZINESS / satisficing / bounded rationality / ECOLOGICAL BALANCE (Ch8.2-8.3). Good-enough
   heuristics that respect time/compute limits; match the agent's complexity to the task; distribute the
   problem-solving load; use cheap "sensing-for-coupling" instead of a rich inner model when possible.

6. MODEL-BASED <-> MODEL-FREE AS A CONTINUUM, ARBITRATED BY PRECISION (Ch8.6). Daw's Bayesian "principle of
   arbitration": estimate the RELIABILITY (uncertainty) of each competing controller; the least-uncertain one
   (in the current context) drives action; model-based (deep/slow/context-sensitive) can TRAIN model-free
   (fast/cached); the two are a hierarchical continuum, not separate systems.

7. BALANCING ACCURACY & COMPLEXITY = MODEL EVIDENCE (Ch8.7). Bayes-optimal agents maximize prediction accuracy
   AND minimize model complexity (an Occam factor). model_evidence = accuracy - complexity. Bayesian Model
   Averaging weights models by EVIDENCE, not raw accuracy. "The most efficient strategy is the active inference
   that minimizes overall complexity cost."

8. APPROXIMATE GENERATIVE MODEL TRADING PRECISION FOR SPEED (Ch8.8). The "intuitive physics engine": a
   probabilistic simulator using deliberate approximations, "good enough" for the task, robust+fast BECAUSE it
   is imprecise (trades veridicality for speed/generality).

9. EMPIRICAL BAYES / HIERARCHICAL PRIORS (App1). Priors estimated from data; each level's estimate serves as the
   prior for the level below; gradient-descent tuning. "All optimal inference is Bayesian, but not all Bayesian
   inference is optimal" — coarse/approximate generative models are legitimate and expected.

10. FREE-ENERGY PRINCIPLE / VARIATIONAL FREE ENERGY (App2). Minimize free energy = an upper bound on surprisal
    (negative log model-evidence); mathematically = variational inference (ELBO). Perception (update beliefs) and
    action (change the world) are two routes to reduce the SAME quantity.

11. CONTROLLED HALLUCINATION / MENTAL SIMULATION (Ch3, Ch6). Perception = the generative model's top-down best
    guess, merely constrained by data; imagination = running the same generative model without sensory clamping.
"""

BOT_CONTEXT = """
OUR SYSTEM (what to map onto): a HUNL + 6-max No-Limit Hold'em engine that currently loses ~-20 bb/100 vs GTO
(measured vs GTO Wizard; AIVAT). Components already built:
- preflop_blueprint: a near-Nash CACHED preflop policy (model-free-ish).
- advisor MLPs: neural nets trained on solver frequencies = a fast cached postflop policy (model-free).
- range_tracker: Bayesian, line-aware reconstruction of the opponent's range from observed actions; already has a
  CONFIDENCE gate (down-weights unreliable reconstructions).
- opp_model: Dirichlet opponent model for a bounded EXPLOIT overlay, gated by a lower-confidence-bound (LCB) EV test.
- resolver: real-time depth-limited CFR (model-based) — expensive, used sparingly; a persistent solve cache exists.
- census tree: a minimal bet-size grid measured from GTO Wizard's revealed frequencies (approximation to shrink
  the action space).
- CORE PROBLEM: compute-vs-accuracy. Full solves everywhere are unaffordable; the -20 loss lives POSTFLOP
  (river+flop). Preflop is near-solved. We need to spend expensive computation only where it changes the decision.
"""

SYSTEM = (
    "You are a rare triple expert: (a) computational game theory / poker solvers (CFR, depth-limited solving, "
    "abstraction, AIVAT), (b) machine learning (variational inference, RL, model-based/model-free, uncertainty "
    "estimation), and (c) predictive processing / active inference (Friston, Clark). You translate cognitive-science "
    "concepts into CONCRETE, implementable math/CS for a poker engine. You are RUTHLESSLY HONEST about novelty: if a "
    "PP concept is just a re-description of something poker solvers/RL already do, you say so plainly and rate its "
    "leverage LOW. You reserve HIGH leverage for genuinely non-obvious, implementable ideas that could move bb/100."
)

USER = f"""{CONCEPTS}
{BOT_CONTEXT}

TASK: For EACH of the 11 concepts, give:
- math_cs_construct: the precise higher-level mathematical/CS object it maps to (e.g. "variational free energy = ELBO",
  "precision = inverse-variance weighting in a Kalman/Bayesian update", "model evidence = marginal likelihood with an
  Occam penalty", "affordance competition = parallel partial-tree evaluation with a softmax over Q-values").
- poker_bot_mechanism: a CONCRETE mechanism we could build in OUR engine (name the component it touches).
- leverage: "high" | "medium" | "low" — be strict; most will be medium/low.
- novelty_vs_existing: is this already standard in solvers/RL (say which), or genuinely new leverage for a poker bot?
- honest_caveat: the main reason it might NOT help (or might be a re-description).

Then:
- top_recommendation: the SINGLE highest-leverage, implementable idea, with a concrete first experiment.
- overall_honest_assessment: does predictive processing offer REAL new leverage for a -20 poker bot, or is it mostly
  an elegant re-description of RL/variational methods we should implement directly instead? Be honest, not flattering.
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "translations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "concept": {"type": "string"},
                    "math_cs_construct": {"type": "string"},
                    "poker_bot_mechanism": {"type": "string"},
                    "leverage": {"type": "string", "enum": ["high", "medium", "low"]},
                    "novelty_vs_existing": {"type": "string"},
                    "honest_caveat": {"type": "string"},
                },
                "required": ["concept", "math_cs_construct", "poker_bot_mechanism",
                             "leverage", "novelty_vs_existing", "honest_caveat"],
                "additionalProperties": False,
            },
        },
        "top_recommendation": {"type": "string"},
        "overall_honest_assessment": {"type": "string"},
    },
    "required": ["translations", "top_recommendation", "overall_honest_assessment"],
    "additionalProperties": False,
}


def main() -> None:
    print("Consulting GPT-5.5 on Surfing-Uncertainty -> poker-bot math/CS translations...", flush=True)
    result, (pt, ct) = openai_json(SYSTEM, USER, SCHEMA, "surfing_translations",
                                   model="gpt-5.5", max_tokens=16000)
    out = "data/research_sweep/surfing_consult.json"
    import os
    os.makedirs("data/research_sweep", exist_ok=True)
    json.dump(result, open(out, "w", encoding="utf-8"), indent=2)
    print(f"tokens: in={pt} out={ct} -> saved {out}\n")
    for t in result["translations"]:
        print(f"[{t['leverage'].upper():6}] {t['concept'][:60]}")
        print(f"         math/CS: {t['math_cs_construct']}")
        print(f"         mechanism: {t['poker_bot_mechanism']}")
        print(f"         novelty: {t['novelty_vs_existing']}")
        print(f"         caveat: {t['honest_caveat']}\n")
    print("=== TOP RECOMMENDATION ===\n" + result["top_recommendation"])
    print("\n=== OVERALL HONEST ASSESSMENT ===\n" + result["overall_honest_assessment"])


if __name__ == "__main__":
    main()
