# Phase-5 math double-check (OpenAI gpt-5.1)

I go through it point by point and separate clearly where the theory is "clean" and where you are poking around in the fog.

---

## 1) Deep CFR on abstracted HUNL: mathematical correctness & convergence

### 1.1. Theoretical basis

- **External-sampling MCCFR** is *convergent* for finite extensive-form games with perfect recall to an NE strategy of the *abstracted* game, provided that:
  - regrets are computed correctly,
  - the sampling distribution is correct (importance weights),
  - all infosets are hit infinitely often,
  - no systematic bias arises in the training of the approximators.

- **Deep CFR (Brown & Sandholm 2019)** replaces the tabular regret table with:
  - a neural network for the *advantage* (regrets) per infoset,
  - memory (reservoir/replay) for samples of the counterfactual values,
  - periodic reinit of the networks or consistent online approximation of the regrets.

Mathematical convergence guarantees are strict *only* for:
- tabular CFR / MCCFR,
- linear or "special" approximators with exact regression.

Deep CFR with deep nets is **heuristic**, but empirically strong (Leduc, Flop Hold’em, HUNL).

### 1.2. In your setting (abstracted HU-NLHE)

- The game is finite (discrete bet sizes, bounded stack, finite cards):
  - ⇒ CFR convergence on *this* abstraction game is given in principle.
- **Abstraction** (e.g. {fold, call, 0.5p, 1p, all-in}) reduces the game massively:
  - The *theoretical* solution is then only an NE of the abbreviated game.
  - Exploitability in the *full* HUNLHE = ε_abstraction + ε_solver.

Formally:
- Let \(G\) be the real game, \(\tilde G\) the abstracted one.
- Your Deep CFR yields a strategy \(\tilde\sigma\) with
  \[
  \epsilon_\text{CFR} := \text{exploitability}_{\tilde G}(\tilde\sigma).
  \]
- Induced strategy in G: \(\sigma^\uparrow\) (natural "lift" mapping).
- Total exploitability in G:
  \[
  \text{exploitability}_G(\sigma^\uparrow) \le \epsilon_\text{abstraction} + C \cdot \epsilon_\text{CFR},
  \]
  with a problem-dependent factor \(C\) (typically O(1), but not trivial to know exactly).

**Leduc result (2.33→0.33 nash_conv)** guarantees only:
- your *pipeline code* (sampling, backprop, buffers) is correct in principle,
- but says *almost nothing* about the size of ε_abstraction in HU-NLHE.
  - Leduc is tiny, has no street structure like NLHE, hardly any bet-sizing problems.
  - Transfer: "the algorithm works" yes; "derive exploitability in HUNL from Leduc values" no.

### 1.3. Realistic exploitability / abstraction error

**Without massive domain expertise** in bet/state abstraction:

- ε_abstraction in full HUNL with only 3 bet sizes is typically **huge**:
  - In older ACPC bots with sophisticated abstraction and solving (CFR+), HU-NL was more in the range of:
    - 10–50 bb/100 exploitability vs. "perfect" GTO, depending on the model.
  - With a very coarse action abstraction (no splitting of stack regions, hardly any street specifics):
    - **>50 bb/100 exploitability** relative to theoretical GTO is easily conceivable,
    - but in practice that is *perfectly okay*, as long as you beat Slumbot etc.

**ε_CFR** in the abstract game:
- Deep CFR on HUNL with 3–4 bet sizes, 200bb and without card abstraction is far more brutal than Leduc:
  - the state space explodes because of:
    - the 52-card deck, many boards,
    - many more actions per street,
    - long game trees 200bb deep.
- With a reasonable setup (large GPU pod):
  - an abstract exploitability in the range of **1–5 bb/100** is *theoretically* achievable, but only with very good engineering (network architecture, replay, LR schedule, stabilization).
- I would conservatively assume:
  - ε_CFR in the abstracted game: **5–20 bb/100**, unless you fine-tune for months.
  - ε_abstraction: **20–50+ bb/100** relative to real GTO.
  
Crucial: **Slumbot is itself abstracted and finite**; you do *not* need "real GTO", but "better than Slumbot and the population".

### 1.4. Important correctness pitfalls with external sampling + NN

1. **Regret targets:**
   - Deep CFR learns the *advantage*:
     \[
     A(I,a) = v(I,a) - v(I),
     \]
     with counterfactual reach.
   - Make sure that
     - \(v(I)\) is computed correctly over the strategy of your own and the opponent's policy,
     - the counterfactual reach corrections are right (importance weights).

2. **Reservoir buffers / replay:**
   - Brown 2019: advantage samples are stored with reservoir sampling in order to approximate a *uniformly distributed* set over all iterations.
   - Source of error:
     - over-representing "fresh" iterations,
     - bias toward the latest policies ⇒ can ruin convergence.
   - Recommendation:
     - a real reservoir sampler per iteration or globally,
     - a limit on buffer size (e.g. 1–5 million samples) + uniform drawing during training.

3. **Reinit vs. continual training:**
   - Deep CFR original: *reinit of the advantage nets per iteration* (to avoid distortions when approximating the cumulative regrets).
   - Many implementations (including some OpenSpiel variants) deviate from this.
   - If you do **not** reinitialize, you have:
     - a "working, but no longer strictly justifiable" heuristic.
   - Decision:
     - for "mathematical cleanliness", stay as close as possible to the Brown setup,
     - in practice you can also do `no_reinit + target_network`, but then you have to watch empirical stability.

4. **Averaging strategy:**
   - Deep CFR additionally uses a **separate average-policy net** that approximates the (reach-weighted) average strategy.
   - Fatal mistake:
     - evaluating the "online policy" instead of the "average".
   - You should:
     - strictly use the *average* policy for evaluation (nash_conv, matches),
     - not the "last iteration".

---

## 2) Warm start via behavioural cloning (BC) from bot histories

### 2.1. Does BC break CFR convergence?

The CFR guarantee states: from an *arbitrary starting regret*, CFR converges to an NE (tabular).
- If you use BC only as an **initialization of the network weights**, you change:
  - the initial approximator parameters, not the mathematical structure of the update.
- CFR only "sees" the subsequent regret updates via MCCFR traversals.

**Conclusion:**  
- Purely mathematically: **NO**, a BC initialization does *not* break CFR convergence in the abstract game, as long as:
  - all further updates are *on-policy CFR*,
  - you keep accumulating the regrets cleanly,
  - you do not try to keep mixing in the BC loss during CFR (that would then no longer be pure CFR).

Only **simultaneous** objectives would be dangerous:
- Loss = α·MSE(regret targets) + β·cross-entropy to the bot policy,
- then you are *no longer* optimizing pure regrets ⇒ no CFR guarantee.

Therefore:

### 2.2. Warm-starting "correctly"

Recommendation:

1. **Pure BC pre-training:**
   - Train a policy net with supervised BC on bot hands (ACPC, Pluribus),
   - optionally an advantage net with pseudo-targets (but harder; I would skip it).
2. **Transfer to Deep CFR:**
   - Initialize
     - the policy/average net with the BC weights,
     - the advantage net e.g. randomly or with a rough heuristic derived from the policy.
   - Then:
     - **from now on use only the CFR loss** (advantage MSE, possibly the policy-average fit).
3. **Optional:** warm start of the average policy via replay sampling of past BC states:
   - In principle: treat the BC data like "iteration -1" for the average buffers,
   - but this is heuristic – a clean CFR guarantee only exists from the start of the MCCFR traversals.

### 2.3. Off-policy concerns

- BC on bot histories is **purely supervised**, not a CFR update.
- ESR/MCCFR updates afterwards are **on-policy** with respect to your ongoing strategies.
- You must **not** try to turn bot histories into *CFR advantage* targets without exact knowledge of the strategies played at the time & the counterfactual reach corrections:
  - otherwise off-policy bias in the regret estimates,
  - breaks the convergence properties.

**Safe scheme:**
- BC = pure policy prior.
- All regret/value estimates only from self-sampled CFR episodes.

---

## 3) "ONE net: near-GTO + maximum exploit" – is that possible?

### 3.1. The mathematical conflict

You have two objectives:

1. **GTO robustness:**  
   Minimize exploitability:
   \[
   \min_\sigma \max_{\tau} u(\sigma,\tau).
   \]
2. **Best response to a fixed opponent \(\pi^\text{opp}\):**  
   Maximize:
   \[
   \max_\sigma u(\sigma,\pi^\text{opp}).
   \]

If you fix \(\pi^\text{opp}\) and train only a BR against it, you get a strategy \(\sigma^\text{BR}\) that typically:
- is highly exploitable by other opponents,
- can be very far from an NE.

**Combination** via a convex combination:
\[
\sigma^\text{mix} = (1-\lambda) \sigma^\text{GTO} + \lambda \sigma^\text{BR}
\]
is completely **clean**:

- The expected value against an arbitrary opponent \(\tau\) is:
  \[
  u(\sigma^\text{mix},\tau) = (1-\lambda)u(\sigma^\text{GTO},\tau) + \lambda u(\sigma^\text{BR},\tau).
  \]
- Exploitability:
  \[
  \text{exploit}(\sigma^\text{mix}) \le (1-\lambda)\,\text{exploit}(\sigma^\text{GTO}) + \lambda\,\Delta,
  \]
  where \(\Delta\) is bounded by the difference between the worst-case payoff and the BR payoff against the opponent's best responder. An upper bound can be roughly estimated from the payoff range (in HUNL bounded by the stack size).

You can define an **exploitability budget**:
- Choose \(\lambda\) such that \(\text{exploit}(\sigma^\text{mix}) \le \epsilon_\text{max}\).

### 3.2. In ONE net vs separate policies

Two variants:

1. **One policy net parametrized by a "regime" input:**
   - Input feature e.g. `mode ∈ {GTO, exploit}` or a continuous λ.
   - The net learns \(\pi_\theta(a|s,\lambda)\), such that:
     - for \(\lambda=0\): close to GTO,
     - for \(\lambda=1\): close to BR.
   - Training:
     - CFR update on \(\lambda=0\),
     - BR-RL/SL update on \(\lambda=1\),
     - possibly interpolation for intermediate λ.

   Problem:
   - the training objectives **conflict locally** in parameter space,
   - there is no guarantee that \(\pi_\theta(\cdot|s,0)\) actually remains the CFR solution,
   - you can destroy the convergence of the GTO policy.

2. **Two separate nets + an external mixer:**
   - \(\pi^\text{GTO}_\theta\) via Deep CFR,
   - \(\pi^\text{BR}_\phi\) via RL / supervised BR search against the population/Slumbot,
   - runtime mixer:
     - selects an action from \(\pi^\text{GTO}\) with probability \((1-\lambda)\),
     - from \(\pi^\text{BR}\) with probability \(\lambda\),
     - or mixes at the action-probability level.

   Mathematical advantages:
   - the CFR convergence of \(\pi^\text{GTO}_\theta\) remains untouched,
   - the BR policy can be tuned completely independently on the population,
   - the exploitability of \(\pi^\text{GTO}_\theta\) is analyzable; then you mix deliberately.

### 3.3. Recommendation

For *mathematical clarity* and *engineering safety*:

- **Yes**, the goal "near-GTO + exploit" is coherent.
- **Recommendation:**  
  - Train **separately**:
    - the Deep CFR net (GTO head),
    - the exploit net (BR head) against the population/Slumbot.
  - Afterwards use an **explicit mixer** with a controlled \(\lambda\).

If you absolutely want "one net":
- Better as "shared body + two heads":
  - a jointly shared feature-extractor backbone,
  - two separate output heads (GTO policy, exploit policy),
  - the CFR update acts *only* on the GTO head (and the backbone),
  - the BR-RL update acts *only* on the exploit head (and the backbone),
  - possibly gradient surgery to protect GTO stability.

---

## 4) Evaluation: nash_conv & AIVAT

### 4.1. Abstracted nash_conv as a proxy

- Nash-Conv in \(\tilde G\) measures:
  \[
  \text{nash\_conv}(\sigma) = u(\text{BR}_1(\sigma_2),\sigma_2) + u(\sigma_1,\text{BR}_2(\sigma_1)) - 2 u(\sigma_1,\sigma_2).
  \]
- For symmetric 2-player zero-sum games this is twice the exploitability (depending on the convention).
- Problem:  
  - It says nothing directly about exploitability in the real G,
  - but: a low nash_conv in \(\tilde G\) means "a good solution *within the abstraction*",
  - together with head-to-head vs Slumbot + population this is an **acceptable practical proxy**.

Empirical heuristic:
- If your nash_conv in \(\tilde G\) is < **1–2 bb/100**, and the abstraction is okay, **you can realistically** expect:
  - solid performance vs Slumbot,
  - robust performance against a normal population.

### 4.2. Lightweight AIVAT scheme

AIVAT = Action-Informed Value Approximation Tool:
- Idea:
  - use a baseline value model \(b(s)\) to reduce the variance due to luck (cards, random actions),
  - the observed payoff \(R\) is replaced by:
    \[
    \hat R = b(s_0) + \sum_{t} \left( r_t - \mathbb{E}[r_t | s_t] \right),
    \]
    where \(r_t\) are the incremental rewards and \(\mathbb{E}[r_t | s_t]\) is approximated by \(b\).

A practicable minimal version for HU-NL:

1. **Baseline value function \(b(s)\):**
   - Train a net \(b_\psi(s)\) that, from
     - public cards,
     - position,
     - pot size, stacks,
     - your own leaked hole cards during training,
     approximates the *expected EV (in bb)*.
   - To do so:
     - use your own policy (e.g. the GTO net),
     - simulate many self-play episodes,
     - train \(b_\psi\) with MSE on the realized return.

2. **Variance reduction in the match vs Slumbot/population:**
   - During evaluation:
     - For each decision point \(t\) with state \(s_t\), compute \(b_\psi(s_t)\).
     - Either:
       - use a simple "one-step" AIVAT:
         \[
         \hat R = R - (b_\psi(s_K)-b_\psi(s_0)),
         \]
         i.e. subtract the change in the value estimator,
       - or (minimally more complex):
         - at every chance node (card deal) you subtract the baseline expectation and add it back as a constant.

3. **Lightweight implementation (simplified):**
   - Even simpler, but usable:
     - Train \(b_\psi\) only on the *start state* (preflop):
       - \(b_\psi\)(ButtonStack, Blinds, HoleCards) = expected return with your policy over random boards & opponents.
     - For each hand:
       \[
       \hat R = R - (b_\psi^\text{hero}(s_0) - b_\psi^\text{villain}(s_0)),
       \]
       or analogously symmetric.
   - This mainly reduces card variance (preflop equity differences).

This is not a "full" AIVAT, but:
- very easy to implement,
- reduces variance significantly compared to pure ROI,
- requires only a value net + logging.

---

## 5) Concrete config & compute estimate

**Warning:** Everything that follows is necessarily rough; HUNL is big. I am giving you a *realistic sketch*, not a guarantee.

### 5.1. Action abstraction

To stay close to Slumbot (200bb, fc + sizes):

- Preflop/flop:
  - actions: fold, call, bet/raise {0.33p, 1.0p, all-in}
- Turn/river:
  - fold, call, bet/raise {0.5p, 1.0p, all-in}

That gives:
- max ~4 actions per decision (incl. fold/call),
- somewhat finer preflop/flop, to capture preflop dynamics.

If compute is scarce, you can also:
- use a uniform {0.5p, 1p, all-in}.

### 5.2. Information-state features

Per player infoset (input to the net):

- **Card encoding:**
  - one-hot: 52 cards,
  - hero hole cards: 2×52 ("card-present"),
  - board: up to 5×52,
  - mask, so that undealt cards stay 0.
  - Optional: a more compact 52-bit mask for "absent/present".

- **Betting state:**
  - pot size (normalized to the starting stack),
  - effective stack (in pot multiples),
  - current street (0=Preflop,1=Flop,2=Turn,3=River),
  - last bet size (in pot multiples),
  - number of raises on this street,
  - position (BTN/BB),
  - who is to act.

- **History features (compact):**
  - Binning:
    - #bets / #calls / #folds per street,
    - binary flags: "villain the aggressor so far?", "hero capped?" etc.

A total feature dimension in the range of 300–500 is feasible.

### 5.3. Network architecture

**Advantage net:**

- Input: ~400-dim vector,
- 3–4 dense layers with 512–1024 units, ReLU or SiLU,
- Output: |A|-dimensional advantage estimate (4 actions).

Example:
- FC(400→1024) → ReLU
- FC(1024→1024) → ReLU
- FC(1024→512) → ReLU
- FC(512→|A|)

**Average-policy net:**
- same architecture, but softmax output (policy logits).

Parameter count:
- on the order of 5–15 million parameters, fits well on 1 GPU.

### 5.4. Deep CFR hyperparameters (for first serious runs)

- **Num iterations**: 200–500 (CFR iterations).
- **Traversals per iteration**:
  - Guideline: 10k–100k MCCFR traversals per player.
  - Since HU is symmetric: you can play both roles for one agent.

Concretely, the minimum for "useful":
- 200 iterations × 20k traversals ≈ 4 million visited infosets.

- **Train_steps per iteration (advantage net)**:
  - 1–2 "epochs" over reservoir samples (max 1M–2M samples).
  - In practice in the code: e.g. 5k–10k mini-batches of 512.

- **LR**:
  - start 1e-3,
  - cosine decay or step decay (e.g. 1e-3 → 3e-4 → 1e-4).

- **Memory / replay:**
  - Advantage buffer: 1–3 million samples (infoset features + target advantages).
  - Average-policy buffer: 1–3 million samples.

### 5.5. Compute estimate

Assume:
- 1 GPU at roughly the TFLOP level of a V100/A100 (or a pod with several of them),
- forward+backward per sample (batch 512, network ~10M param) about 1–2 ms / batch.

Rough calculation:

- Per iteration:
  - 20k traversals (HUNL, 200bb) are expensive, let's say:
    - about 0.5–1 sec per 1k traversals on a GPU-accelerated Python/Cpp mix ⇒ 10–20 sec per iteration.
  - Training:
    - 10k batches × 2ms = 20s per iteration.

→ 1 iteration ≈ 30–40s.

- 200 iterations:
  - 200 × 40s ≈ 8000s ≈ ~2.2 hours on *one* well-utilized GPU.

That is **optimistic**; with Python overhead/OSS implementation, I/O, debugging:

- Realistic: 5–10 GPU hours for a **"mid-quality" run**,
- 20–50 GPU hours for a **better, fine-tuned run**.

Whether you beat Slumbot **clearly** with that is uncertain; but:
- a chance of "competitive" performance is realistic in 20–50 GPU hours,
- for clearly > GTO-Wizard level against Slumbot this is rather *undersized* (there one typically talks about many 100 GPU hours plus a lot of domain knowledge).

---

## 6) Potential FATAL flaws & highest risk factor

Possible serious stumbling blocks:

1. **Faulty MCCFR implementation** (sampling, reach weights, action probs):
   - You have validated Leduc – good.
   - But make sure that:
     - the same fixes are used in HU-NLHE,
     - there are no hidden bugs (e.g. in the abstracted action_probabilities).

2. **Advantage-net training bias:**
   - unclean reservoir samples,
   - too strong a correlation between samples,
   - wrong targets (e.g. normalized regrets vs. raw advantages mixed).

3. **Average policy represented / used incorrectly:**
   - If you accidentally play the last iteration instead of the averaged policy, exploitability can be very high.

4. **Abstraction too coarse or inconsistent:**
   - E.g. an all-in button in spots where it never makes strategic sense,
   - or no option for a "smallish" bet on the river → massively exploitable.

5. **Meta-coach (LLM) changes hyperparameters / objective during a run**:
   - If the meta-loop changes objectives in the middle of the CFR optimization (e.g. mixes BC / RL loss into the CFR loss), any serious CFR theory goes out the window.
   - Let the meta-coach only:
     - *end* runs and start new runs with *new, fixed hyperparameters*,
     - not redefine the live objective during a Deep CFR run.

**Single highest-risk assumption error (from my point of view):**

> **"Deep CFR with relatively few iterations/traversals on heavily abstracted HU-NLHE *automatically* yields a near-GTO strategy that clearly beats Slumbot."**

- That is **un
