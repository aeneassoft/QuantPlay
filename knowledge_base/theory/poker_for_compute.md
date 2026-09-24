# Optimising poker theory for ML/computation

## OpenAI gpt-5.1

1) Representation: How to model poker so that compute is genuinely better than "book theory"
-------------------------------------------------------------------------------

The core: you want to cast **everything** into terms over which you can
- cleanly define expected values,
- compute belief states and counterfactual values,
- cleanly derive gradients / regrets / policy updates.

### a) Central mathematical objects

**Game model (for 2p NLHE, CGT-style):**

- State space: histories \(h = (a_1, a_2, ..., a_t)\).  
- Public information: board, pot, bet-size history, who is to act, effective stacks.  
- Private information: hole cards \(c_i\).  
- Information sets \(I\): set of histories that are **indistinguishable** for a player (same public info, own cards, but opponent cards unknown).  
- Strategies \(\sigma_i(I)\): probability distributions over actions \(a\in A(I)\).  
- Payoff: \(u_i(h)\) at the terminal state (showdown / fold).

**Computationally relevant quantities:**

- **Belief State**:  
  \(b(I)\) = distribution over all possible hidden cards / previous mixes, consistent with the public line.  
  In practice: "range distribution" over combos (often a factorized approx).

- **Counterfactual Value (CFV)**:  
  \(v_i^\sigma(I)\) = expected payoff of player \(i\), *conditional* on the game being in \(I\), weighted by the probability that the opponent & chance led to \(I\). Central in CFR, DeepStack, ReBeL.

- **Regret** \(r(I,a)\):  
  Advantage one would have had by always choosing action \(a\) in \(I\) instead of the current policy:
  \[
  r(I,a) = v_i^\sigma(I \text{ with } a) - v_i^\sigma(I)
  \]
  -> Regret matching / (D)CFR.

**Human concepts → machine primitives**

- **Ranges**:  
  Human: "He open-raises a 25% range, I 3-bet 10%"  
  Machine:  
  - distribution \(\rho_{\text{pre}}\) over hole cards,  
  - updated posterior distribution after actions: \(\rho_{\text{post}}(c_{\text{villain}} \mid h)\).  
  Implemented as:
  - tabular (abstraction),
  - or a parametrized model \(f_\theta(\text{public obs}) \to\) density over "bucketed" hand types / card bits.

- **Polarization**:  
  Human: strong hands + bluffs, no medium-strength hands.  
  Machine:
  - A policy that chooses the action "big bet" only at CFV extremes (very high / very low).  
  - Can be seen as structure in the Q-value: the action "pot bet" is preferred for hands with large \(|v - \text{EV-Fold}|\).  
  - In representations the model typically learns "monotonicities": the stronger/ weaker, the more likely big bets.

- **MDF (Minimum Defense Frequency)**:  
  Human: \(\text{MDF} = \frac{\text{Pot}}{\text{Pot}+\text{Bet}}\).  
  Machine:
  - The exact same expression appears when one solves a BR optimization (best call/fold mix) against a given bluff frequency.  
  - But compute does not need to "know" MDF: CFR/best-response iteration *induce* MDF, because any deviation from MDF leads to exploitable bluffs/folds.  
  - In practice: MDF is a **strong prior** / initializing heuristic for the policy (see Part 2).

- **Blockers**:  
  Human: "My A♣ blocks his nut flushes → better bluff bet."  
  Machine:
  - The CFV difference arises because certain card combos become thinner in the belief distribution when I hold this card.  
  - Feature-wise: an input encoding that cleanly represents individual card bits + suit patterns; the net learns how card symmetries shift CFVs.  
  - Explicitly, one can encode "blocker features" as additional inputs (e.g. counts of specific nut hands that my holding blocks).

- **Equity**:  
  Human: "equity vs range" = win probability in an all-in.  
  Machine:
  - Equity is only *one* component of the CFV, under the policy / betting strategy.  
  - Important: instead of isolated preflop/flop equity, compute optimizes the **total value** over the entire subgame.  
  - Technically: \(v_i^\sigma(I)\) integrates both – equity & expected folding/bluff selection.

### b) Where 1 hour of compute dominates 3 years of pro knowledge

**Compute is superior as soon as:**

1. **Exact mixing frequencies in complex SPOTs**  
   - E.g. 3-bet pot, SPR ~ 2, multi-street betting with many bet sizes.  
   - A local solver (TexasSolver) + cf-values over a board sampling can:
     - output exact frequencies for hundreds/ thousands of hands,  
     - deliver error curves (how bad is "always c-bet 60% pot") at high resolution.  
   - A human can understand qualitatively: "turn check-raise is polar", but not:
     - "Hand X bets 32% flop, 51% turn, 8% river, with which combo weighting, to punish IP check-back leaks."

2. **Quantifying leak curves / exploit strength**  
   - Example: "Villain folds flop vs c-bet 55% instead of GTO 35%" → compute can:
     - systematically search for the best response,  
     - calculate the exploitative line in bb/100, per board class / commitment level.  
   - These finely granular "leak-mapping heatmaps" are beyond what a pro can construct by intuition.

3. **Abstraction & subgame re-solving** in many spots  
   - Through **cached GTO benchmarks** you can in 1h:
     - score thousands of strategies across board classes against GTO ground truth,  
     - find optimal hyperparameters while varying parameters (aggression, c-bet frequency, sizing mix, etc.).  
   - The human can find rules, but **cannot** simulate 1000 variants and evaluate their GTO gap.

4. **Belief-state optimization > static heuristics**  
   - OppModel + node locking:  
     - Compute can automatically find (via no-regret/gradients) how far to deviate from GTO in order to maximally exploit a specific OppModel, under a fixed exploitability-budget constraint.  
   - Humans are qualitatively good here ("vs a nit I fold more"), but:
     - Compute can tune these adjustments very precisely in mixing frequencies/line selection, incl. complex multi-line exploits.

**Where compute does **NOT** simply replace 3 years of a pro:**

1. **Priors / abstractions / domain reduction**  
   - Which bet sizes to allow at all?  
   - Which states to merge (board clusters, SPR classes, positions)?  
   - Which human heuristics save 90% of the search space without killing 90% of the EV?  
   -> Here good "theory priors" are worth their weight in gold and reduce compute massively.

2. **Model specification**  
   - Architecture of the value/policy net, feature design, parametrization of ranges (e.g. bucketing, suit isomorphisms).  
   - A strong pro who also understands the compute pipeline can judge very well **which** details matter (e.g. deep river value traps vs. turn aggression patterns) and steer the net/focus accordingly.

3. **Meta-strategy / game selection / real population assumptions**  
   - Even perfect 2p zero-sum GTO does not solve:
     - multiway dynamics,  
     - rake/structure-specific adjustments,  
     - live tells, timing behavior, etc.  
   - Humans provide more robust high-level priors about which exploit-regime mode makes sense in which games/lineups.

4. **Interpretation & robustness**  
   - Compute can solve thousands of spots, but:
     - Pattern recognition at an abstracted level ("what does this range curvature *mean*?") remains a human strength.  
   - These insights help to detect abstraction errors / overfitting.

---

2) Analytical theory as a relaxed prior: principled frameworks
--------------------------------------------------------------------

Your intuition ("Chen, MDF, α=s/(1+s) as a *relaxable* structure") fits very well into several established frameworks:

### a) Analytical formulas as **priors / initialization**

**Bayesian prior / architecture prior:**

- Example: your initiative-/range-aware Chen/MDF heuristic provides:
  - for every spot a "hard-coded" policy \(\pi_{\text{theory}}(I)\),  
  - or target metrics (e.g. "c-bet 70% on a dry board").
- In the learning model:
  - Initialize the policy net \( \pi_\theta \approx \pi_{\text{theory}}\) (supervised init: MSE / CE on \(\pi_{\text{theory}}\)).  
  - Afterwards: self-play / CFR updates to improve *away* from this approximation.

Positive effect:
- The search space is in a reasonable regime from the start (e.g. no massive overbluffing on nut-heavy boards).
- Compute is used for fine-tuning, not for "elementary-school theory".

### b) Analytical theory as **soft regularization**

Formally:  
\[
\mathcal{L}(\theta) = \mathcal{L}_{\text{game}}(\theta) + \lambda \cdot \mathcal{R}(\theta)
\]
with e.g.
\[
\mathcal{R}(\theta) = \sum_I D_{\text{KL}}\left(\pi_\theta(\cdot\mid I) \;\|\; \pi_{\text{theory}}(\cdot\mid I)\right)
\]

Interpretation:
- \(\mathcal{L}_{\text{game}}\): exploitability approximation, BR loss, DCFR objective or self-play cross-entropy / advantage loss.  
- \(\mathcal{R}\): "Don't stray too far from the theory policy, unless it brings EV."

**Constraint annealing / homotopy:**

- Start with a high \(\lambda\) (strong theory binding),  
- reduce \(\lambda\) over time ("the engine warms up").  
- Result: the model starts in the theory-near regime, then breaks away when data (self-play / GTO benchmark) provide reasons.

This is exactly the idea of:
- **Lagrange multipliers / Lagrangian relaxation**:
  - implement theoretical constraints (e.g. MDF, pot control on certain boards) as soft constraints,  
  - the Lagrange multiplier \(\lambda\) is adjusted dynamically (or per schedule).

### c) Analytics as a **curriculum**

Curriculum learning approach:

1. Phase 1:  
   - Only simple spots with high analytical coverage (e.g. single-raised pots, CBET-only, few sizing options).  
   - Loss = distance to the analytical policy + a light self-play share.

2. Phase 2:  
   - More complex spots (3bet pots, turns, rivers, various sizings).  
   - More weight on explicit counterfactuals (CFV estimation, best-response loss).

3. Phase 3:  
   - Full self-play/exploitability optimization; analytical theory only as regularization for out-of-distribution states.

This way theory & learning reinforce each other instead of colliding:
- Theory defines the "starting space" and the "allowed tendencies".
- The learning component uses deviations from the theory only when they are **measurably EV-positive**.

### d) Concrete construction for you

**Example: α = s / (1 + s)** (control over the aggression level vs. the stack/pot ratio)

- Use α as a deterministic function of your features (SPR, position, initiative).  
- The policy net learns *residual parameters* \(\delta\alpha\):  
  \[
  \alpha_{\text{eff}} = \frac{s}{1+s} + f_\theta(\text{state})
  \]
  with regularization \(\|\delta\alpha\|^2\) or KL vs. the base α.  
- This preserves the global structure (higher s → higher aggression), but the net learns the subtleties (e.g. specifically Q-high boards vs K-high).

**MDF baseline**

- For every bet spot: analytical MDF \(\text{MDF}_{\text{theory}}\).  
- The net outputs \(\text{MDF}_\theta(I)\).  
- Regularization:
  \[
  \mathcal{R}(I) = (\text{MDF}_\theta(I) - \text{MDF}_{\text{theory}})^2
  \]
  unless the GTO benchmark clearly shows that deviating is better → then lower \(\lambda\) locally (adaptive regularisation).

---

3) "Computation substrate": what to build on?
---------------------------------------------

### a) OpenSpiel

**OpenSpiel (DeepMind, open source)** is currently the closest thing to "Qiskit for game theory":

- Framework for:
  - representation of **simultaneous and sequential games** with imperfect information,  
  - CFR, DCFR, XFP, PSRO, RL algorithms,  
  - various example games (incl. Leduc, Kuhn, Goofspiel, some poker variants).

- Strengths:
  - Very modular representation of games (infosets, actions, transitions).  
  - Clean implementations of classic algorithms (counterfactual regret minimization + variants, policy gradients, etc.).  
  - Integration with JAX / TensorFlow / PyTorch possible.

- Weaknesses:
  - For NLHE in full complexity only usable as a game template;  
  - no out-of-the-box, highly optimized NLHE solving modules like Pio/TexasSolver.  
  - Performance & abstractions are generic, not NLHE-optimized.

Nevertheless:  
**As a conceptual & experimental substrate, OpenSpiel makes absolute sense**, in particular to:
- first test new CFR variants, exploitability metrics, OppModel algorithms etc. in Leduc/Kuhn,  
- validate generic IIGS (Imperfect Information Game Solving) pipelines.

### b) Other relevant OSS building blocks

- **ACPC/annual computer poker competition code**  
  - Legacy, but good references for:  
    - game abstraction,  
    - best-response tools,  
    - evaluators.

- **DeepStack/Deep CFR/Pluribus open repos** (partly unofficial, partly reimplementations):  
  - e.g.:
    - open-source "Deep CFR" implementations (Python/C++/PyTorch)  
    - RLCard (more RL-oriented, poker & card games, but less game-theoretically rigorous)

- **Poker-specific projects**:
  - There are various GitHub repos for:
    - counterfactual regret minimization in Texas Hold’em,  
    - abstraction & bucketing.  
  - Quality varies, but some contain solid evaluators + CFR cores.

### c) When is bespoke tooling worth it?

With your setup:

- **You already have**:
  - TexasSolver (local postflop GTO oracle),
  - GTO benchmark (GTO gap scorer, cached),
  - OppModel.

What is missing here, which generic frameworks do not solve well:

1. **Seamless integration of NLHE specifics + high-performance solutions**
   - board equity evaluators,  
   - suit/isomorphism symmetrization,  
   - SPR stratification and subgame resolving.

2. **Custom training loops**:
   - online re-solving with GTO oracle calls,  
   - node locking based on OppModel estimates,  
   - exploitability budgeting (regime blend \(\sigma = (1-\lambda)\cdot \text{GTO} + \lambda\cdot \text{Exploit}\)).

This speaks **clearly for your own infrastructure**, but not "from scratch":
- Use OpenSpiel as a **reference for algorithms** (CFR variants, exploitability computation, PSRO ideas).  
- Your NLHE engine (TexasSolver + abstraction + evaluator) is the actual "hardware sim".  
- Build a thin, well-designed interface:
  - a `GameState` object with an API similar to OpenSpiel, but NLHE-optimized,  
  - adapters for self-play / DCFR / ReBeL-like search that integrate your solver calls.

---

4) Concrete training plan for the pod runs
--------------------------------------------

Goal: in 1 GPU hour, **maximum progress** regarding
- (a) the GTO gap on your benchmark,
- (b) exploit bb/100 vs. OppModel / realistic opponent profiles.

### a) Representation on the pod

**State features (input)**:
- Public information:
  - board (bitmap: 52-card one-hot or compressed rank/suit features + isomorphisms),
  - pot size, effective stacks, SPR,
  - position (IP/OOP), street, past bet sizes (as normalized sizes, e.g. pot fraction),
  - action-history embedding (LSTM/Transformer light or simply aggregated stats like "number of bets/raises", max-bet multiplier etc.).

- Private information:
  - own hole cards (one-hot or embed),
  - optional: bucket ID (if you use abstraction).

**Outputs** (policy/value):

- **Policy head**:  
  - probability distribution over discrete actions (fold, call, raise {x1/2, x2/3, pot, all-in, …}).  
  - Optional multi-head: a separate head for bluff/value classifiers, if you want to force polarized structures.

- **Value head**:  
  - CFV estimate under the current (or target) policy \(\hat{v}_\theta(I)\).  
  - Optional: value head per hand class (e.g. 169/1326 buckets), useful for node locking/range visualization.

### b) Training objective(s) in 1h: combination of 3 loss components

**1. Supervised + distillation from TexasSolver (GTO oracle):**

- Use cached GTO strategies as "ground truth" in many spots (already available through your benchmarking).  
- Loss components:
  - Policy distillation:  
    \[
    \mathcal{L}_{\text{policy}} = \mathbb{E}_I \left[ D_{\text{KL}}\big(\pi_\theta(\cdot\mid I) \|\; \pi_{\text{GTO}}(\cdot\mid I)\big) \right]
    \]
  - Value distillation:
    \[
    \mathcal{L}_{\text{value}} = \mathbb{E}_I \left[ \|\hat{v}_\theta(I) - v_{\text{GTO}}(I)\|^2 \right]
    \]

This is very compute-efficient:
- Oracle/benchmark data are cached.  
- In 1h you can push a great many batches through (pure feedforward + backprop).  
- Result: a small, quickly evaluable "approx-GTO net" that covers wide areas of the state space.

**2. Exploit learning vs OppModel (with exploitability budget)**

In parallel (or in a later phase of the same run):

- Collect self-play/off-policy data in which PokerB plays against:
  - a pure GTO-approx policy, and  
  - the OppModel policy (realistic opponents).

- Goal: learn an **exploit policy** \(\pi_\theta^{\text{exploit}}\), but with a soft constraint on GTO proximity.

Loss:

- EV metric vs OppModel:
  \[
  \mathcal{L}_{\text{exploit}} = -\mathbb{E}_{\text{episodes}}[ \text{bb/100 vs OppModel} ]
  \]
- plus regularization:
  \[
  \mathcal{R} = \mathbb{E}_I D_{\text{KL}}\big(\pi_\theta^{\text{exploit}}(\cdot\mid I) \|\; \pi_\theta^{\text{GTO-approx}}(\cdot\mid I)\big)
  \]
- Total:
  \[
  \mathcal{L}_{\text{total}} = \mathcal{L}_{\text{policy}} + \beta \mathcal{L}_{\text{value}} + \gamma \mathcal{L}_{\text{exploit}} + \lambda \mathcal{R}
  \]

with:
- \(\beta\): weighting of value distillation,
- \(\gamma\): focus on the exploit update in this pod session,
- \(\lambda\): exploitability-budget control (regime blending).

**Compute efficiency:**
- You can recycle many off-policy transitions from existing simulations (replay buffer).  
- New episodes against OppModel can run in parallel on many CPUs; the GPU only does training.  
- 1h is enough to make significant updates, as long as the net is lean (e.g. < 50M parameters).

**3. Direct optimization of the GTO gap via a DCFR-like objective (optional)**

If you can estimate exploitability (e.g. via an approximate best response or an existing benchmark), you could:

- define the GTO gap as the difference between:
  - the value under your policy,  
  - the value under the oracle GTO.  
- Minimize it via:
  - gradient-based policy optimization (deliberately simple policy gradient / advantage actor-critic),  
  - or CFR-like updates in which regrets are stored in a net (Deep CFR).

For 1h runs, however, **policy/value distillation + a light RL exploit component** is usually more efficient than full-fledged CFR training.

### c) Meta-coach (Claude Haiku) in the loop

Claude can be used sensibly to:

1. **Steer small-scale hyperparameter search**:
   - after each pod run:
     - GTO gap change,
     - exploit bb/100 change,
     - exploitability budget (effective KL distance from GTO).  
   - Claude evaluates which loss weightings (\(\beta, \gamma, \lambda\)) worked,  
   - proposes new configurations / curriculum steps.

2. **Curriculum design**:
   - Order of the spots that should be trained more heavily (e.g. river decisions with high EV impact first).  
   - Identification of board classes in which the GTO gap is particularly large → focused retraining.

3. **Node-locking policy**:
   - proposed node locks against OppModel (e.g. "Vs. this opponent: increase the check-raise frequency in the 3bet pot in spots X/Y"), which are then verified locally by TexasSolver and integrated into the training data.

---

Summary of the action plan:

1. **Fix the representation**: a compact policy+value net with rich but lightweight features (board, history, cards, SPR).  
2. **Analytical theory as a prior**: policy init on a Chen/MDF variant, soft regularization against this heuristic with annealing.  
3. **Exploit cached oracle data**: distillation of TexasSolver GTO in large-batch training → reduce the GTO gap quickly.  
4. **Exploit component**: a small RL layer on top that maximizes EV vs. OppModel but stays KL-bound to the GTO approx (exploitability budget).  
5. **Bespoke tooling**: your TexasSolver+abstraction is the "hardware", with a thin, OpenSpiel-inspired but NLHE-specific solver/training interface on top.  
6. **1h pod run**:  
   - ~70–80% of the time distillation / GTO-gap minimization,  
   - ~20–30% of the time exploit fine-tuning vs OppModel & replay,  
   - after the run: evaluate, adapt hyperparameters (meta-coach).

## Claude claude-opus-4-8

# Answer: Making the pod foundation concrete

## 1) Recursive-ToM LLM on hand histories — valuable or essay?

**Verdict: As a training signal, largely essay. As a concept miner and test generator valuable — but only in a strongly restricted form.**

The problem with "recursive ToM over all players" as a learning signal: it is not *grounded*. The LLM prose ("he thinks that I think…") produces no verifiable EVs. But you already have the GTO benchmark as ground truth — every LLM ToM argument must be measured against it, otherwise it is chatter. **Use the benchmark as a lie detector for the LLM reasoning.**

Where it has concrete value (by priority):

- **(a) Spot generator / stress-test miner — YES.** Haiku reads hand histories and proposes *node categories* in which blockers / polarization / range asymmetry are decisive ("here everything hinges on the nut blocker"). These are candidate spots that you then **verify with the solver**. Output: a curated, difficulty-weighted spot list for the benchmark — exactly where your bot likely has the largest GTO gap.
- **(b) Feature discovery — YES, limited.** If the LLM ToM consistently points to a quantity that is missing from your encoding (e.g. "number of nut combos my holding blocks"), that is a concrete feature proposal. This is cheap to test: feature in → GTO gap on the benchmark drops? keep.
- **(c) Direct policy signal — NO.** Distraction. Pouring LLM ToM text into loss functions is expensive, noisy and dominated by the solver.

**Operationalization (does NOT belong in the hot pod loop, but offline before it):**
```
HH → Haiku: "mark nodes where ToM/blockers/polarization tip the tree"
   → solver verifies every marked node (CFV sensitivity)
   → keep only nodes with high CFV variance → "hard-spot set"
   → feed the hard-spot set into the benchmark (weighting)
```
This **feeds** the pod run (better eval set), but runs asynchronously on CPU.

---

## 2) Chen/MDF thresholds as priors — the self-improvement loop

Exactly right and buildable immediately. Your hand-coded baseline is a *parametrized policy* π_θ with a small θ (open %, 3bet %, MDF fudge, c-bet sizes, polarization cutoffs). That is a low-dimensional, cheaply evaluable optimization problem — perfect for CPU + Haiku coach.

**The loop (CPU-only, no GPU needed):**
```
θ_0 = Chen/MDF defaults (good priors → fast start)
loop:
  1. PROPOSE θ':
       - Haiku proposes structured edits ("raise BTN open by 2%, polarize the turn bet")
       - IN PARALLEL: CMA-ES / Bayes-opt proposes numerical steps
  2. EVALUATE: GTO-Gap(π_θ') on the weighted spot set  (seconds, cached)
  3. ACCEPT if the gap drops (with the exploitability budget as a constraint)
  4. LOG (θ', gap, which proposer) → fed back to Haiku as context
```

**Important design decisions:**
- **Haiku is a proposer, not a referee.** Acceptance is *always* decided by the benchmark. Haiku only wins if it jumps into good regions faster than blind search — you measure that (accept rate per proposer).
- **θ per subgame class** (per SPR bucket × initiative × board texture), not global. Otherwise everything averages out.
- **Exploitability budget as a hard constraint**, not as a term in the loss — otherwise the loop optimizes itself into exploitable corners.

This loop is also your **dry run** for the pod infrastructure: the same propose→eval→accept loop, except that on the pod a neural π_θ and DCFR updates take over the role of CMA-ES.

---

## 3) What must be finished BEFORE the pod launch — in order

Principle: **The pod may only run once the reward/eval pipeline is watertight.** A GPU pod that optimizes against a wrong or slow benchmark burns money in the wrong direction.

**Tier 0 — eval integrity (blocker, no launch without it):**
1. **Benchmark as an API with a stable contract**: `gto_gap(policy, spot_set) → scalar + per-node breakdown`, deterministic, cached, < seconds. This is your reward signal — it must be rock-solid.
2. **Exploitability-budget check as a separate gate**: every policy gets `(gto_gap, exploitability)`. Acceptance only if both are ok.
3. **Spot set fixed + versioned** (incl. the hard-spot set from §1a, if finished — otherwise without it, not a blocker).

**Tier 1 — validate the loop mechanics on CPU (before GPU):**
4. **The §2 loop runs end-to-end** on the baseline and demonstrably lowers the gap. If this does not work on CPU, it will not work on the pod either — just more expensively.
5. **State encoding frozen**: public obs + card bits + suit pattern + blocker counts (the one feature from §1b, if verified). Encoding changes in the middle of a pod run = restart.

**Tier 2 — pod-specific (the actually new part):**
6. **Small on-pod π_θ net** (policy + value head) that consumes the same encoding and is measured on the same benchmark.
7. **DCFR update loop** over subgame-resolved CFVs, value net as a bootstrap at the subgame leaves (the established GTO shortcut: re-solve + abstraction + value-fn + SPR + DCFR).
8. **Haiku meta-coach hook**: same interface as in the CPU loop, now proposes hyperparameters / abstraction edits / node-lock targets.

**Deliberately NOT before the launch (distractions):**
- Full ReBeL belief search — too hard, later.
- DeepNash/R-NaD path — a different paradigm branch, right now it splits the attention. Park it.
- LLM ToM as a loss signal (§1c).
- 6-max / multiway — first clean 2p zero-sum (only there does your no-regret→Nash guarantee hold).

---

## 4) The ONE highest-leverage thing to put on the pod first

**The reward pipeline as a pod service: `gto_gap` + exploitability gate, as the shared, deterministic, fast fitness operator that both the CPU prior loop (§2) and the on-pod π_θ (§3-Tier2) dock onto.**

Rationale: everything else — Haiku coach, DCFR, prior tuning, neural policy — is only a *proposer*. The benchmark is the *selector*. In every self-improvement system, the quality and speed of the selector determine the quality of the end product; a strong proposer with a weak selector optimizes confidently in the wrong direction. You already have the selector (TexasSolver oracle + cached benchmark) — the highest leverage is to harden it into a **stable, deterministic, sub-second service** on which the CPU and GPU worlds hang interchangeably.

Concretely, "first" means: Tier 0 finished, then run the §2 CPU loop against it, verify *gap-demonstrably-drops* — **only then** switch on the GPU power.
