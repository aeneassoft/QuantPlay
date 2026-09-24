# Surfing Uncertainty (Andy Clark) → poker-bot math/CS — the GPT-5.5 consult (2026-07-07)

Extracted 11 grounded predictive-processing (PP) concepts from the book (ch1–8 + appendices), asked GPT-5.5 which
translate to concrete higher-level math/CS for our −20 bb/100 engine. Tool: `research/surfing_consult.py`
(full result: `data/research_sweep/surfing_consult.json`).

## The honest verdict
**Predictive Processing is mostly an elegant vocabulary for things poker/RL already know** — Bayesian filtering,
uncertainty weighting, model selection, amortized/variational inference, bounded rational metareasoning,
model-based/model-free arbitration. **It gives NO new poker objective** (poker is chip-EV / exploitability, not
prediction-error minimization — treating them as equal is a category error). Most mappings are re-descriptions or
incremental cleanups.

**BUT** three concepts converge on ONE genuinely high-leverage, implementable idea for our exact bottleneck.

## The 3 HIGH-leverage concepts (they unify)
| PP concept | math/CS |
|---|---|
| **Precision-weighting** (Ch2) | inverse-variance weighting; calibrated predictive uncertainty across all controllers |
| **Productive laziness / ecological balance** (Ch8.2–3) | rational metareasoning: choose computation `c` to max `E[EV after c] − cost(c)`; anytime/multi-fidelity/value-of-computation |
| **Model-based ↔ model-free arbitration** (Ch8.6) | mixture-of-experts `π(a|s)=Σ_k g_k(s)π_k(a|s)`, gates `g_k` ∝ estimated reliability |

→ Together = **precision-weighted value-of-computation (VoC) control**.

## TOP RECOMMENDATION — a postflop VoC arbiter
Spend expensive CFR/resolver budget ONLY where the fast cached policy is likely wrong or the EV gap between
candidate actions is small AND high-value. Concrete first experiment:
1. Collect postflop decision states; per state record cheap features: advisor MLP policy + entropy, `range_tracker`
   confidence/entropy, pot/street/SPR, top-2 EV margin, cache-hit age, board texture, opponent **line-surprise**
   (`−log P(a_t | state, range)`), cheap rollout estimate.
2. Offline label each with `ΔEV = EV(resolved action) − EV(fast action)` (resolver / GTOW).
3. Train a **calibrated quantile regressor** predicting `ΔEV` + its uncertainty.
4. Online rule: invoke the resolver iff `E[ΔEV | features] − λ_ms · solve_ms > threshold`, with hard triggers for
   river all-ins + low top-2 EV margin.

This is the highest-leverage PP translation and **directly attacks the −20 postflop leak** (river+flop) — it aligns
with our own `PRECISION_DOCTRINE` (spend accuracy where it changes the decision), now with a principled trigger
instead of hand-coded thresholds.

## The LOW ones (honest)
- **Active inference / "doing without cost functions"** → category error for poker; = max-entropy/KL-regularized RL;
  keep EV as the primitive, PP-as-prior adds little.
- **Controlled hallucination / mental simulation** → already the high-grade version in our resolver (CFR/rollouts).

## MEDIUM (useful cleanups, not new leverage)
Hierarchical PP (residual-as-compute-signal), affordance competition (parallel candidate-action racing / progressive
widening), model-evidence Occam penalty (abstraction selection), approx generative model (already = advisor MLPs +
census tree), empirical Bayes hierarchical opponent priors (helps vs real pools, not vs GTOW), free-energy = ELBO
(range_tracker as amortized variational inference).
