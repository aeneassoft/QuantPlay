# Short-deck (6+) strategy consult (gpt-5.5)

## Bottom line

Short-deck is **not** a magic path to “a bot we can win with.” Near-GTO still does not beat near-GTO. The value of short-deck is narrower:

1. **Good value:** a cheap, measurable **HU short-deck postflop near-GTO demonstration**.
2. **Possible value:** a niche **short-deck planning/training product**, if rules + market are real.
3. **Bad claim / trap:** “we solved 6+” or “we have a 6-max Triton ante near-GTO bot.”

My ranked allocation:

1. **Exploit-vs-field edge: 60%**
2. **HU short-deck near-GTO demo: 25%**, time-boxed and measurement-gated
3. **NLHE defense advisor completion: 15%**, only as leak patching, not as the main path

Do **not** fully pivot from NLHE to short-deck unless the goal is explicitly a **bounded HU postflop proof/product**, not “winning poker” in general.

---

# 1. Strategic value of short-deck

## Checkable facts you have

- NLHE vs GTO Wizard AI: roughly **-66 to -71 bb/100**, worse than always-fold **-64.6 bb/100**.
- Solver-grounded facing-bet defense advisor improved floor **-70.7 → -66.4**, only **+4.3 bb/100**, not significant.
- Real measured positive result: **+31 bb/100 vs Slumbot**, i.e. exploitability of weaker field.
- TexasSolver v0.2.0 supports short-deck natively via `--mode shortdeck`.
- Your short-deck solve worked: parsed strategy dump, 6-A ranks only, ~0.5% exploitability in ~5s.
- Short-deck card game is materially smaller:
  - Preflop combos: **630 vs 1326**, about **47.5%** of NLHE.
  - Hand classes: **81 vs 169**, about **47.9%**.
  - Flops: `C(36,3)=7,140` vs `C(52,3)=22,100`, about **32.3%**.
  - Full boards: `C(36,5)=376,992` vs `C(52,5)=2,598,960`, about **14.5%**.

These facts support: **short-deck HU postflop is cheaper to solve and easier to build a measured demonstration around.**

They do **not** support: “we can now win with GTO short-deck” or “we solved short-deck poker.”

---

## Is short-deck a smarter path to near-GTO?

### For HU postflop near-GTO: yes, conditionally

Short-deck is a better place to prove the architecture because:

- 2-player HU postflop is zero-sum.
- TexasSolver already solves it.
- Card space is smaller.
- Your parser already works.
- Your `gto_oracle.solve(mode="shortdeck")` is wired.
- A fixed postflop subgame has a clean solver-gap/exploitability notion.

So if the target claim is:

> “For fixed HU short-deck postflop subgames, under locked rules/ranges/sizings, our resolver/advisor approximates TexasSolver within measured EV/exploitability tolerances.”

That is credible and checkable.

### For a full bot you can win with: no, not by itself

A near-GTO bot wins only against opponents making mistakes. Short-deck being smaller does not create EV versus strong opponents. It only lowers approximation cost.

Winning requires:

- exploitable opponents,
- good opponent modeling,
- game selection,
- rake awareness,
- correct preflop/ante format,
- and likely multiway handling if targeting popular short-deck formats.

You have measured +EV evidence in the exploitable field path, not in short-deck.

---

## Where exactly short-deck has value

### 1. HU postflop near-GTO demonstration — real value

This is the cleanest use case.

Claim you can honestly make:

> “We can build a HU short-deck postflop bot/resolver whose decisions are measured against solved TexasSolver subgames.”

This is much stronger than the current NLHE story, where the external GTO Wizard AI gate says the bot is worse than always-fold.

### 2. Smaller-game pipeline proof — real value

Short-deck is a good proving ground for:

- deck-agnostic card/range code,
- parser robustness,
- solver-cache generation,
- advisor retraining,
- EV-gap evaluation,
- resolver latency.

Because the game is smaller, failures surface faster.

### 3. Sellable short-deck product — possible but unproven

There may be product value because GTO Wizard has short-deck planning only, not an AI benchmark. But this cuts both ways:

- Less competition / possible niche.
- Less external validation.
- Smaller player market.
- Rule forks create support burden.
- Popular formats are often ante/multiway, not clean HU postflop.

A plausible product is **short-deck planning/training/resolving for locked HU/postflop spots**, assuming legal/ToS-compliant use.

A bad product claim is **“6-max Triton short-deck solved.”**

### 4. “We solved 6+” — marketing trap

You have **not** solved 6+.

What you have:

- a working short-deck evaluator/dict,
- native TexasSolver mode,
- one verified postflop solve,
- parser compatibility,
- and a plausible port path.

That is valuable, but it is not a full-game solution.

---

# 2. Measurement problem: how to measure HU short-deck near-GTO

There is no GTO Wizard AI equivalent, so you need an internal but rigorous measurement stack.

The key is to be explicit:

> You are measuring **conformance to solved HU short-deck postflop subgames**, not universal game-theoretic optimality.

## What is actually checkable

### A. Evaluator/rule correctness

Before strategy measurement, lock and test rules.

Check:

- deck = 36 cards, ranks `6789TJQKA`;
- no 2-5 leakage anywhere;
- `C(36,5)=376,992` rank rows;
- flush/full-house ordering matches target rule;
- A-6-7-8-9 wheel is handled;
- trips-vs-straight ordering matches target room;
- 7-card best-hand evaluation matches 5-card rank dict;
- TexasSolver `--mode shortdeck` ranking agrees with your dict.

This is binary. If wrong, all strategy data is poisoned.

---

### B. Oracle solve quality

For each fixed HU postflop subgame:

- locked rules,
- locked stack depth,
- locked pot,
- locked ranges,
- locked action tree,
- locked bet sizes,

record TexasSolver exploitability/gap.

Your current measured example: ~0.5% exploitability in ~5s.

Decision-grade cache gate:

- solve training spots to around **≤0.5% pot exploitability**, if feasible;
- solve heldout evaluation spots tighter, e.g. rerun some at **≤0.25% pot** or more iterations;
- verify strategy EV stability when iterations are doubled.

Caveat: this validates against TexasSolver, not against an independent external oracle.

---

### C. Agent action EV gap

Do not use MSE as the primary metric. Your NLHE experience already shows that solver-imitation MSE does not necessarily translate into large bb/100 gain.

Use EV gap:

\[
\text{gap}(s) = \max_a Q_{\text{solver}}(s,a) - \sum_a \pi_{\text{agent}}(a|s)Q_{\text{solver}}(s,a)
\]

Report:

- reach-weighted mean action EV gap;
- p95 action EV gap;
- max action EV gap;
- street breakdown: flop / turn / river;
- spot-type breakdown: facing bet, checked-to, all-in, low SPR, draw-heavy boards, paired boards.

Suggested decision gate for a demo:

- mean action EV gap: **≤0.5% pot**;
- p95 action EV gap: **≤2-3% pot**;
- no catastrophic action classes with large systematic losses.

If this fails, the advisor is not near-GTO even if its policy MSE looks good.

---

### D. Best response / LBR exploitability

For HU postflop, you can freeze the bot policy and compute exploitability in the same discrete tree.

Two levels:

1. **Matched-tree best response**
   - Same action abstraction as solver/advisor.
   - Gives the cleanest internal scalar.
   - This is closest to “exploitability” for your implementation.

2. **Local Best Response with extra bet sizes**
   - More adversarial.
   - Tests if the bot is brittle outside the trained tree.
   - Not exact full-game exploitability, but useful.

Suggested pass/fail gate:

- matched-tree exploitability: target **single-digit bb/100 equivalent**, ideally **≤2-5 bb/100** over the defined spot distribution;
- LBR with extra sizes: should not explode; if it is **>10-15 bb/100**, do not call it near-GTO.

The exact threshold should be predeclared before training.

---

### E. Self-play convergence

Useful for bug detection only.

Self-play convergence does **not** prove near-GTO. Two broken agents can converge against each other.

Use self-play to catch:

- evaluator bugs,
- impossible card deals,
- illegal actions,
- range normalization errors,
- regression vs previous versions.

Do not use it as the main GTO metric.

---

### F. Match winrate against bots/humans

This measures exploitative strength, not near-GTO.

Good for product/field EV.

Bad for GTO certification.

---

## Without an external gate, do you repeat the same problem?

Partly, yes.

The absence of GTO Wizard AI means you lose the clean external falsifier. So the honest claim must be narrower:

- **Strong claim:** “Measured near-TexasSolver in fixed HU short-deck postflop abstractions.”
- **Weak/invalid claim:** “Near-GTO short-deck bot.”

To reduce circularity:

- exhaustively test evaluator/rules independently;
- use heldout boards/ranges/action trees;
- rerun a sample of spots at tighter solver settings;
- measure EV gap, not just policy similarity;
- compute BR/LBR against the frozen bot;
- keep train/test split by board/range/tree, not random node split.

---

# 3. Minimal execution path for HU short-deck postflop bot

Ranked lean path:

## Step 1 — Rule-lock the variant

Highest priority.

Decide exact target:

- flush > full house? Your current dict says yes.
- trips > straight or straight > trips?
- A-6-7-8-9 wheel?
- ante/blind format if preflop is included?
- HU only or 6-max/multiway?

If TexasSolver’s `--mode shortdeck` ranking differs from your target room, stop. Do not generate caches until this is resolved.

---

## Step 2 — Hard test card/evaluator/range plumbing

Implement/configure:

- `cards.py RANKS = "6789TJQKA"`;
- 36-card deck generation;
- 630 preflop combos;
- 81 hand classes;
- no 2-5 leakage;
- board parser rejects illegal ranks;
- blocker logic works;
- range normalization works with 630 combos;
- 5-card and 7-card hand-rank tests pass.

This is not glamorous, but it prevents silent poisoning.

---

## Step 3 — Re-derive short-deck equity/texture features

Do not reuse NLHE equity bands.

Short-deck equities are different:

- fewer ranks;
- more connected boards;
- stronger average made hands;
- different flush/full-house/trips/straight order;
- different draw values;
- all-in equities run closer.

Recompute:

- preflop hand class equities;
- board texture buckets;
- draw features;
- nut advantage features;
- equity percentile bands;
- facing-bet defense thresholds.

This should be generated from the short-deck evaluator, not edited manually.

---

## Step 4 — Define a narrow HU postflop scope

For the first measured demo, avoid pretending you solved preflop.

Define:

- HU only;
- fixed stack depth(s), e.g. one or two SPR buckets;
- fixed preflop ranges;
- fixed action tree;
- fixed bet sizes;
- flop/turn/river postflop only.

The preflop ranges can be imperfect, but then the claim is conditional:

> “Near-GTO postflop conditional on these ranges.”

That is acceptable for a demo. It is not a full-game bot.

---

## Step 5 — Generate short-deck TexasSolver cache

Use `gto_oracle.solve(mode="shortdeck")`.

Compute expectation:

- all concrete short-deck flops: **7,140**;
- measured solve time: **~5s/flop** at ~0.5% exploitability;
- one canonical range/tree full-flop cache:  
  `7,140 * 5s = 35,700s ≈ 9.9 CPU-hours`.

Parallelized:

- 16 cores: roughly **40-90 minutes** with overhead;
- 32 cores: roughly **20-60 minutes** with overhead.

For multiple ranges/SPR/action trees, multiply linearly.

Example:

- 10 range/tree buckets ≈ **99 CPU-hours**;
- on 32 cores: roughly **3-5 wall-clock hours** plus IO/failures.

Card-state cost versus NLHE is materially smaller:

- flops: **32.3%** of NLHE;
- flop private combos per player after board: `C(33,2)=528` vs `C(49,2)=1176`, about **44.9%**;
- pairwise private-hand matrix roughly **20%** of NLHE for a single flop;
- all-flop card-state workload can be around **6-15%** of NLHE for the same abstraction.

Do not overpromise exact speedup. Solver cost also depends on tree size, iterations, bet sizes, convergence behavior.

---

## Step 6 — Retrain the short-deck advisor

Train on short-deck caches only.

Use:

- EV-weighted loss, not pure action MSE;
- heldout split by board/range/tree;
- separate metrics for facing-bet defense, probe, c-bet, check-raise, river bluffcatch;
- calibration by pot odds/equity class.

Primary validation:

- action EV gap to solver;
- matched-tree BR exploitability;
- LBR robustness.

Secondary validation:

- KL/cross-entropy/MSE.

---

## Step 7 — Integrate HU resolver

The resolver is probably the cleanest path to a strong demo.

Use:

- live `mode="shortdeck"` solving where latency permits;
- advisor fallback when online solve is too slow;
- same locked action abstraction as measurement;
- no NLHE regression: default `holdem` must remain unchanged.

Latency target depends on product mode:

- offline trainer/planner: seconds are fine;
- real-time bot: ~5s flop solve may be too slow without caching/fallback;
- turn/river may be faster, but measure it.

---

## Step 8 — Produce one decision-grade report

For the demo, report:

- exact rules;
- exact ranges;
- exact action tree;
- number of solved spots;
- oracle exploitability distribution;
- heldout action EV gap;
- matched-tree exploitability/LBR;
- resolver latency;
- advisor vs heuristic comparison;
- failure cases.

If you cannot produce this report, you do not have a near-GTO demonstration.

---

# Biggest pitfalls

## 1. Trips-vs-straight rule fork

This is the biggest technical poison risk.

If the target room says trips beats straight but your solver/dict uses straight beats trips, every cache is wrong for that room.

Rule-lock before mass-solving.

---

## 2. TexasSolver mode may not match your target variant

You verified `--mode shortdeck` works. You still need to verify its exact ranking convention against your intended product.

Native support is not enough.

---

## 3. Popular short-deck is often ante/multiway

HU postflop is clean.

6-max Triton-style ante games are not:

- multiway;
- not two-player zero-sum;
- no clean exploitability scalar;
- CCE is not Nash;
- preflop format dominates range construction;
- your current blueprint does not cover it.

Do not let a HU postflop success become a 6-max marketing claim.

---

## 4. Preflop is not solved by this pivot

A postflop resolver needs ranges. If preflop ranges are wrong, the bot may be bad in real games even if postflop decisions are strong conditional on those ranges.

For the first demo, explicitly scope out full preflop.

For a product, preflop becomes a separate project.

---

## 5. Same-solver circularity

“TexasSolver says we match TexasSolver” is useful but not equivalent to an external benchmark.

Mitigate with:

- evaluator unit tests;
- tighter heldout solves;
- BR/LBR;
- adversarial off-policy states;
- independent equity calculations.

But be honest: it is still not GTO Wizard AIVAT.

---

# 4. Honest recommendation

## Ranked call

### 1. Exploit-vs-field edge — 60%

This is the only path with measured positive EV evidence: **+31 vs Slumbot**.

Prioritize:

- opponent modeling;
- exploit selection;
- population leaks;
- game-type targeting;
- safety fallback;
- regression tests against known exploitable bots.

This is the path to “we can win,” not near-GTO purity.

---

### 2. HU short-deck near-GTO demo — 25%

Do this as a bounded sprint because it is cheap and strategically useful.

Goal:

> Prove the architecture can produce a measured near-solver HU postflop bot in short-deck.

Time-box it. Predeclare pass/fail metrics.

Worth doing if you can produce:

- locked short-deck rules;
- valid 36-card evaluator;
- all-flop or broad sampled cache;
- heldout EV-gap report;
- matched-tree BR/LBR report;
- resolver/advisor integration;
- no NLHE regression.

This gives you a credible technical artifact.

---

### 3. NLHE defense advisor — 15%

Continue only as leak reduction.

The measured result so far is weak:

- +4.3 bb/100;
- not significant;
- still around always-fold territory;
- GTO Wizard remains a hard external falsifier.

Do not make this the main bet unless new modules show statistically significant movement, e.g. a large improvement over always-fold and current bot across a fresh AIVAT sample.

---

# What makes short-deck clearly worth it?

Short-deck becomes clearly worth more effort if all of the following happen:

1. Rules are locked and match TexasSolver/evaluator.
2. Cache generation is cheap as expected.
3. Advisor/resolver achieves low heldout EV gap.
4. Matched-tree BR/LBR does not find large exploits.
5. The demo works across flop/turn/river, not just one cherry-picked flop.
6. There is a real target user/product/pool for HU/postflop short-deck.
7. You keep the claim narrow: HU postflop, fixed abstraction, measured against solver.

Then increase allocation from 25% to maybe 35-40%.

---

# What makes short-deck clearly a distraction?

Short-deck is a distraction if:

1. The claim drifts to “solved 6+” or “6-max near-GTO.”
2. You cannot lock trips-vs-straight / room rules.
3. You need Triton-style ante/multiway preflop immediately.
4. Measurement is only self-play or policy MSE.
5. BR/LBR finds large exploits.
6. There is no product/user/game target.
7. It consumes effort from the exploit-vs-field path, where you already have measured +EV.

---

## Final answer

Short-deck is a **smart bounded side-pivot** for a measurable HU postflop near-GTO demonstration. It is **not** the main path to a winning poker bot.

Keep the main effort on exploit-vs-field. Use short-deck to prove the pipeline cheaply and honestly. Keep NLHE GTO Wizard work on a short leash until it produces significant movement beyond the current least-loss plateau.
