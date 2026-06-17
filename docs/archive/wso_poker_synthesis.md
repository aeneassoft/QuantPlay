# WSO → poker: synthesis + verdict (vetted 2026-06-16; GPT-5.5 + o3 + my own paper read all agree)

Both LLMs (fed the paper text) CONVERGE and are HONEST — both proactively state WSO is **not** a game/Nash solver and
warn where it would mislead. Cross-checked against the paper's own equations (§III–IV): the characterization matches.
So this verdict is well-grounded, not an LLM hallucination. (Clean boundary: design intel to vet, never a training label.)

## What WSO actually is
A war-THEMED population metaheuristic for **single-objective, continuous, box-constrained global optimization**
(a PSO/GA/GWO cousin): "soldiers" = candidate vectors x∈ℝᵈ move toward the **King** (best) + **Commander** (2nd best)
via a weighted update `x ← x + rand·W(K−x) + rand·(C−x)` (attack=exploit) / a peer-randomized variant (defense=explore);
rank+weight rise on improvement (elitist snap-back otherwise); the worst "weak soldier" is relocated/replaced.
**It is NOT a poker / game / Nash / imperfect-information / regret solver.** Its "war strategy" is a NAMING metaphor —
NOT military game theory.

## The ONE rigorous use for us: an OFFLINE black-box TUNER of the exploit-layer dials
- **Decision vector** (≤~30–60 dim, box-constrained): LCB-gate params (z, N_min, decay); Dirichlet opponent-model
  priors (α by street/action); safe-exploit blend cap / max-GTO-deviation; bet-size grids (log-scaled).
- **Objective (ROBUST, not the raw mean):** `bb/100 vs a FROZEN opponent model/pool − λ·max(0, LBR−ε)² −
  μ·deviation-from-GTO-floor`, scored on a LOWER bound (mean − c·SE) because bb/100 is high-variance.
- **Eval:** duplicate deals / common random numbers; racing (more hands to the top candidates); **re-sample
  King/Commander each generation** (else it crowns variance winners); held-out unseen-opponent + LBR validation.
- The floor (CFR / resolver / CFV-net) and the safe-exploit GUARDRAILS stay OUTSIDE WSO (frozen) — WSO only turns dials.

## Honest priority (the bottom line)
1. **WSO does NOT advance the theory-of-mind / exploitation EDGE** (the user's vision). Reasoning about a hidden-info,
   *adapting* adversary needs the OPPONENT-MODELING + CFR machinery (see `EXPLOIT_VISION.md`: Bayesian opponent
   typing, recursive belief, level-k, safe-gated) — a continuous optimizer cannot do it.
2. **Even as a tuner it is not the best choice** — o3's sharp point: CMA-ES / Bayesian Optimization typically beat WSO
   on noisy low-dim objectives. So WSO is not even optimal for its one niche.
3. **A poker strategy is a product of info-set simplexes over a 10⁵–10⁶-node tree** — WSO searches ℝᵈ boxes; evolving
   the strategy directly breaks normalization/card-removal/dimension. CFR is provably convergent + orders faster.
4. **Noise danger:** without the variance-reduction above, WSO overfits luck → can make the bot MORE exploitable.

⇒ **LOW priority.** Worth keeping as a clean offline tuner *if* we later auto-optimize the exploit-layer dials (after
the floor net + the ToM exploit layer exist). It is NOT the "military-strategy AI" the title suggests — the genuine
military/game-theory edge (Stackelberg/commitment, Bayesian games, safe opponent exploitation) lives in the
OPPONENT-MODELING layer, not in this optimizer. Full per-model detail: `docs/wso_poker_gpt55.md`, `docs/wso_poker_o3.md`.
