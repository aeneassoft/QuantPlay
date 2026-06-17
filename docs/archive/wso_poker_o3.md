# WSO (War Strategy Optimization) -> poker (o3, 2026-06-16)

1. What WSO actually is  
WSO is a population-based, single-objective, continuous meta-heuristic—conceptually a cousin of PSO or GA, not an equilibrium or game solver.  
• Each particle (“soldier”) has a position x∈ℝᵈ. At every iteration it is re-positioned by one of two fixed update rules.  
  – Attack rule: xᵢ ← xᵢ + rand·Wᵢ·(K − xᵢ) + rand·(C − xᵢ) where K = best position (the “King”) and C = 2nd best (“Commander”).  
  – Defence rule: xᵢ ← xᵢ + rand·Wᵢ·(K − xrand) + rand·(xrand − xᵢ) (adds a random peer to enlarge exploration).  
• Each soldier has a rank and an exponential weight Wᵢ=α^{rank}. Rank ↑ only if the new position improved fitness; otherwise the soldier snaps back to the previous position (elitist selection).  
• The worst-fitness soldier is either replaced by a random point or “relocated” near the population median (weak-soldier relocation).  
That’s the entire algorithm: no gradients, no game-theoretic reasoning, no concept of mixed strategies—just a stochastic optimiser of a scalar objective.

2. Defensible black-box uses inside our poker stack  
WSO can tune numeric hyper-parameters that sit outside the equilibrium solver itself. Typical decision vectors are ≤30 dims, continuous, unconstrained or box-constrained—exactly WSO’s comfort zone.

Recipe A – Safe-exploitation hyper-parameters  
Decision vector (dim≈8):  
α_dirichlet (4 streets), LCB_confidence, ε_mix (floor/exploit blend), learning-rate, decay.  
Objective: Mean bb/100 in 30 000 simulated hands versus a fixed library of opponent models (each model sampled with common random numbers to cut variance).  
Evaluation: For every candidate vector run N=5 seeds × 30 k hands, average result; reuse RNG streams across candidates; fitness = mean_bb − λ·stdev_bb (risk penalty).  
WSO tweaks vectors, weak-soldier replacement explores new regions; stop after 300 fitness calls.  
Adaptations for noise:  
• Use mini-batch resampling—re-evaluate the incumbent King every ten iterations to avoid luck-lock-in.  
• Increase population size modestly (e.g., 60) to stabilise the rank-based weight update.

Recipe B – Bet-size grid design  
Decision vector: 3 bet sizes flop + 3 turn + 2 river (log-scaled real values).  
Objective: minimise computed exploitability (LBR) of the blueprint strategy that uses that grid.  
Evaluation: run TexasSolver once per grid, then run a fixed LBR for 1 M hands. Deterministic, but very expensive, so cache results and set population size small (e.g., 12).  
WSO’s elitist snap-back keeps only strictly better grids, useful when each call is hours long.

Recipe C – Prior weights for opponent model  
Decision vector: 1326-card-class priors compressed with 10 PCA coefficients.  
Objective: log-likelihood on last 500 observed hands + regulariser. Same noise-handling tricks as recipe A apply.

3. Metaphorical mapping (inspiration only)  
• Attack update ≈ shifting strategy mass toward an exploit line once we have identified villain’s leak.  
• Defence update ≈ retract frequencies toward the GTO floor while still shadowing a promising peer line—mirrors “don’t over-exploit” safe-exploit logic.  
• King = best-performing parameter set (highest EV); Commander = runner-up guiding diversity.  
• Weak-soldier relocation = decap frequency from clearly –EV lines and recycle that probability mass near solid core ranges.  
These analogies may help intuition but carry no formal guarantee.

4. Honest limits / where WSO does NOT fit  
• Poker strategies are probability simplices over a combinatorial game tree; WSO searches ℝᵈ boxes. Directly evolving an entire NLHE strategy would break because constraints (sum to 1, no negative probs) and dimension (10⁵–10⁶) violate WSO’s assumptions.  
• Imperfect-information and opponent adaptation are absent in WSO’s model; iterating WSO inside a live match would ignore feedback loops and can be counter-exploited.  
• For solving subgames or computing counterfactual values, CFR-type dynamic programming is orders-of-magnitude faster and provably convergent; swapping it for WSO would be strictly worse.  
• High outcome variance (bb/100) inflates noise; if variance-reduction tricks are skipped, WSO will chase luck and overfit—CMA-ES or Bayesian Opt often cope better.  
• No equilibrium awareness: WSO may find brittle, easily counter-exploitable settings if the opponent class shifts. Safe-exploit guardrails must therefore be outside, not inside, WSO.  
Bottom line: treat WSO as one more hyper-parameter tuner in the engineering toolbox—useful, but not a replacement for CFR, depth-limited solving, or principled game-theoretic reasoning.
