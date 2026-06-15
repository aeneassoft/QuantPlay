# Orchestration consult — OpenAI gpt-5.5

## Bottom line

Your measured facts point to one conclusion: **do not spend the $70 on big GPUs for NLHE Deep-CFR.** Your current NLHE Deep-CFR is **Python traversal-bound**, not neural-net-bound: ~47 traversals/sec, GPU memory ~0.2 GB / 143 GB, GPU idle. H200/B200 would mostly buy you a more expensive idle device.

Use the budget for:

1. **CPU-first, parallel, inspectable experiments** for CFR/self-play / abstractions.
2. **Solver-cache evaluation harness** as the main keep/revert gate.
3. A **small supervised “GTO-floor advisor” net** only as glue/interpolation over your existing solver caches + PokerBench labels.
4. Keep exact/tabular/heuristic methods where they are already better: preflop table, exact river equity, pot-odds/MDF math, exploit overlay caps.

$70 is **plenty** for this small iterative loop. It is **not** enough, and not the right substrate, for serious from-scratch NLHE Deep-CFR training.

---

# Q1. GPU vs CPU for your CFR/self-play

## Measured facts that matter

You measured:

- Leduc CFR+ exact full-tree: exploitability drops **1300 → 16 mbb/hand monotonically** after fixing the clairvoyant BR bug.  
  **Signal:** your CFR implementation can converge when the game/tree is tractable and exact.
- NLHE OpenSpiel Deep-CFR on `universal_poker`, `fcpa` abstraction runs and learns vs check-call station: **-519 → +1136 chips/hand after 40 iters**.  
  **Signal:** the pipeline is not broken.
- But it is CPU/Python traversal-bound:
  - ~**47 traversals/sec**
  - GPU memory **0.2 GB / 143 GB**
  - GPU idle
  - single-threaded Python traversal bottleneck

That means the GPU is not your limiting resource.

---

## GPU option

### Pros

- Useful for **batched neural network training**, especially supervised learning from PokerBench / solver caches.
- Useful if you later have a traversal system that can generate large replay buffers fast enough.
- Cheap GPU at ~$0.33/hr is okay for small MLP training.

### Cons

- For your current Deep-CFR, the GPU is mostly idle.
- H200/B200 are actively wasteful here:
  - H200: $4.39/hr
  - B200: $5.98/hr
  - Your current workload uses almost none of the GPU.
- GPU does not fix Python game-tree traversal.
- The check-call-station improvement is not a GTO-floor signal. It proves learning against a weak fixed opponent, not reduced exploitability or better near-GTO play.

### Signal that GPU would be worth it

GPU becomes worth it only if you see:

- GPU utilization meaningfully high during training, e.g. sustained nontrivial utilization / memory use.
- Traversal throughput no longer dominates wall-clock.
- Larger batches reduce loss and improve held-out solver EV-gap.

You currently have the opposite signal.

---

## CPU / C++ / parallel MCCFR option

### Pros

- Matches your actual bottleneck: game traversal.
- Parallel external-sampling MCCFR can scale across CPU cores/processes much more naturally than the current single-threaded Python loop.
- More inspectable than Deep-CFR:
  - regret tables
  - average strategy snapshots
  - action-frequency drift
  - per-information-set regret
- Better for small iterative experiments.
- Lets you cheaply test whether the `fcpa` abstraction produces anything useful before involving neural nets.

### Cons

- Full NLHE is still huge. Even `fcpa` is a very lossy abstraction.
- Tabular strategies can explode if you do not aggressively abstract or sample.
- A coarse `fold/call/pot/allin` blueprint will not magically become a strong NLHE floor.
- OpenSpiel C++ integration may require engineering time.
- MCCFR self-play in a crude abstraction may improve consistency but may also teach your bot bad sizing habits relative to your actual solver-calibrated action space.

### Signal that CPU MCCFR is working

Use these signals, in order:

1. **Traversal/sec per dollar improves massively** over 47 traversals/sec.  
   I would want at least **10x**, preferably **50x+**, before trusting it as an iteration substrate.

2. On toy games / Leduc regression:
   - exploitability still falls monotonically or near-monotonically.
   - no return of the clairvoyant best-response issue.

3. In NLHE `fcpa`:
   - strategy stabilizes over iterations;
   - against fixed weak opponents, exploit improves;
   - more importantly, when mapped back to your real bot action abstraction, it **reduces held-out solver EV-gap** versus your current heuristic floor.

If it does not reduce solver EV-gap, it is not improving the floor you care about.

---

## Should you keep Python Deep-CFR?

### Brutal answer

Keep it only as a **smoke-test / reference prototype**. Do **not** use it as your main improvement substrate.

It already proved:

- the OpenSpiel setup runs;
- learning can occur;
- your environment wiring is not totally broken.

But the measured bottleneck makes it a bad place to spend $70.

---

## One recommendation

**Switch the CFR/self-play substrate to CPU-first parallel external-sampling MCCFR / C++ OpenSpiel / custom tabular-regret experiments on the small `fcpa` abstraction.**

Use Python Deep-CFR only for sanity checks. Do not rent H200/B200. If you rent anything, rent the cheapest CPU-rich pod available, or the cheapest GPU pod only if it happens to be the cheapest way to get enough CPU.

**Primary success signal:**  
`held-out solver EV-gap improves versus current floor after mapping the learned strategy back into your actual bot decision interface.`

**Secondary infrastructure signal:**  
`traversals/sec improves by at least 10x over the current ~47/sec.`

---

# Q2. Orchestrating the iterative loop

## Q2a. Single most reliable signal after each small run

For NLHE bot improvement, the best keep/revert signal is:

> **Held-out solver-cache EV-gap / action-regret gap on solved spots.**

Not raw bb/100.

Your Slumbot samples are too noisy:

- floor exploit-off: **-97 ± 110 bb/100**
- with overlay: **+49 ± 69 bb/100**

Those intervals are too wide for small-run gating.

Exact Leduc exploitability is excellent, but only for validating CFR machinery. It does not prove NLHE improvement.

PokerBench held-out accuracy is useful, but label agreement is less important than EV impact.

Duplicate poker helps reduce variance, but still requires enough volume and opponent choice.

So the main gate should be:

### Primary signal

For each held-out TexasSolver spot, compute:

- bot action;
- solver strategy;
- if available, solver action EVs;
- EV loss of bot action relative to solver mix / best response action.

Then track:

```text
mean EV loss / pot
street-specific EV loss
large-pot EV loss
fold/call/value/bluff decision EV loss
solver policy TV distance or cross-entropy as secondary
```

If you only have solver policies but not action EVs, use:

```text
held-out solver policy TV gap / cross-entropy
```

But EV-weighted gap is better because not all label disagreements matter.

### Signal that proves a patch worked

A patch worked if, on a frozen held-out solver set:

- EV-gap decreases, ideally by **5–10%+** on the targeted subset;
- no major regression on other streets/spots;
- improvement survives bootstrap over flops/hands;
- action diff report shows changes in the hypothesized failure area, not random global drift.

---

## Q2b. Loop structure

Use this structure every time.

### Step 0 — Freeze baseline

For each experiment, freeze:

- current bot version;
- current preflop table;
- current postflop heuristic;
- current exploit overlay;
- evaluation datasets;
- random seeds;
- legal action mapping.

You need paired comparisons.

---

### Step 1 — State one hypothesis

Example:

> “Our turn probe sizing is too aggressive on low-equity OOP turns, causing high solver EV-gap.”

Must be narrow enough that one short run can falsify it.

---

### Step 2 — Pick the smallest test

Do not start with “train a big net.”

Start with one of:

- rule patch;
- table patch;
- nearest-neighbor lookup from solver caches;
- small supervised model;
- 30–90 minute CPU MCCFR smoke run;
- river / turn subset evaluation.

---

### Step 3 — Run short

Target short runs:

- 10–30 min for eval-only / rule tests;
- 30–120 min for small supervised models;
- 1–3 hr for CPU MCCFR smoke tests;
- never start with 24+ hr training.

---

### Step 4 — Inspect three reports

For each run, inspect:

1. **Primary held-out solver EV-gap report**
   - total;
   - by street;
   - by position;
   - by SPR;
   - by pot size;
   - by action class.

2. **Action diff report**
   - where did the new bot disagree with old bot?
   - are changes concentrated in hypothesized spots?

3. **Guardrail report**
   - preflop accuracy does not regress;
   - exact river equity path unchanged unless intentionally modified;
   - exploit overlay still capped;
   - no illegal action / sizing mapping failures.

---

### Step 5 — Keep / revert

Keep only if:

```text
targeted held-out solver EV-gap improves
AND global EV-gap does not materially regress
AND action diffs make strategic sense
AND cheap duplicate-poker / fixed-opponent checks do not show obvious breakage
```

Otherwise revert.

---

### Step 6 — Only then test versus opponents

Use Slumbot / duplicate poker as secondary validation, not the first gate.

Small bb/100 samples are too noisy. Use them to catch disasters, not to prove subtle improvement.

---

## Q2c. Starting hypotheses and cheap tests

### Hypothesis 1 — The postflop heuristic floor is the main near-GTO leak

Your own measurement says:

- exploit overlay is healthy;
- floor is weak vs near-GTO;
- postflop is heuristic except exact river equity.

So this is likely.

### Cheap experiment

Build a solver-cache evaluator over your TexasSolver spots.

Compare:

1. current heuristic;
2. nearest-neighbor solver-cache policy;
3. simple learned advisor from solver/PokerBench;
4. blend of current heuristic + advisor.

### Signal

Patch works if:

```text
held-out postflop solver EV-gap decreases
especially on flop/turn
without increasing river or preflop errors
```

This should be your first real improvement target.

---

### Hypothesis 2 — Turn play is worse than river because river now has exact enumeration

You improved river with exact enumeration. Turn is likely now the weak link because it still needs equity realization, fold equity, implied odds, and future street modeling.

### Cheap experiment

On held-out solved turn spots:

- bucket by SPR, position, board texture, draw density, and action history;
- compute current bot’s EV-gap;
- add a small turn-only calibrator:
  - adjust bluff/value frequency;
  - adjust continue/fold thresholds;
  - adjust pot/all-in aggression.

Start with a non-net calibrator or tiny supervised model.

### Signal

Patch works if:

```text
turn-specific solver EV-gap drops
AND river EV-gap does not increase from bad turn range construction
```

If you cannot show turn held-out improvement, do not trust it.

---

### Hypothesis 3 — Your sizing abstraction does not match solver-preferred sizes

Your bot uses heuristic sizing with fold-equity logic. Solver caches likely contain spots where the main error is not “bet vs check” but “wrong size.”

### Cheap experiment

From solver caches, build a sizing confusion matrix:

```text
bot size chosen vs solver dominant size
by street / SPR / board texture / position
```

Then test a small “sizing selector”:

- input: current bot’s chosen action class, pot, SPR, board texture, position;
- output: choose among your existing legal sizes;
- no new fancy betting tree needed.

### Signal

Patch works if:

```text
solver EV-gap on bet/raise spots drops
AND frequency of catastrophic overbet / underbet mistakes decreases
```

Policy TV alone is not enough; use action EV loss if available.

---

### Hypothesis 4 — The 11.4% preflop gap in the lookup table causes avoidable downstream problems

You have an **88.6% preflop table**. That is good, but missing/misaligned preflop decisions can poison ranges for all later streets.

### Cheap experiment

Audit only the missing / low-confidence 11.4%.

Use:

- PokerBench preflop labels;
- solver charts if available;
- nearest-position/action-history mapping;
- hard-coded sanity filters.

Do not train a net for this first.

### Signal

Patch works if:

```text
held-out PokerBench preflop accuracy improves
AND high-EV preflop blunders decrease
AND postflop solver-gap does not worsen due to range distortion
```

Preflop is mostly table/rule work, not neural-net work.

---

### Hypothesis 5 — The exploit overlay may be too active against near-GTO opponents

You measured:

- floor exploit-off: about **-97 ± 110 bb/100**
- overlay on: about **+49 ± 69 bb/100**
- overlay crushes exploitable field **+300 to +1100**

So the overlay is likely useful. But it may still be unsafe in low-confidence spots.

### Cheap experiment

Add overlay diagnostics:

```text
where overlay changes action
confidence level
stat key
nudge size
solver EV-gap before/after on near-GTO-like held-out spots
```

Try a more conservative gate:

- require more hands/stat confidence;
- reduce caps in low-confidence nodes;
- disable some rules vs near-GTO profile.

### Signal

Patch works if:

```text
exploit overlay maintains winrate against exploitable test bots
AND reduces solver EV-gap / action-regret when opponent stats are near-GTO or low-confidence
```

Do not optimize this first. Your measured data says the floor is the bigger problem.

---

# Q3. “Net as connecting interface logic”

## Where a neural net genuinely makes sense

A neural net is useful where you need **generalization/interpolation** across many similar but not identical poker states.

Good candidates:

### 1. Solver-cache interpolator

You have TexasSolver caches:

- many flops;
- some turns.

A small net can learn:

```text
state features -> solver-like action prior / sizing preference / EV residual
```

This is a valid “glue” use. You are not training GTO from scratch; you are interpolating between solved spots.

### 2. PokerBench decision prior

You have **563k PokerBench labeled GTO decisions**.

A small supervised model can learn:

```text
state -> GTO-like action distribution
```

Then your existing exact/heuristic system can use it only where confident.

### 3. Leaf-value evaluator for depth-limited re-solving

This is theoretically a good use of a net:

```text
subgame leaf state + ranges -> approximate continuation value
```

But be careful: a real leaf-value model needs high-quality range-conditioned data. If your caches do not provide enough range/CFV information, this becomes research-scale fast.

For $70, I would not start here unless your solver cache includes usable action EVs / CFVs.

### 4. Blueprint prior that local search refines

A net can provide a prior for local re-solving:

```text
net gives rough policy
small local search refines
```

But local resolving infrastructure is more engineering. Good later, not first.

---

## Where a neural net is not worth it

Do **not** use a net for these:

### Preflop table

You already have an **88.6% solver-calibrated lookup table**.

Better tools:

- table completion;
- rule patches;
- chart interpolation;
- position/action-history-specific lookups.

Signal for improvement is PokerBench/solver preflop accuracy, not model sophistication.

---

### Exact river equity

You now have exact river equity by enumeration.

A neural net would be worse:

- approximate;
- harder to debug;
- can make illegal/unstable errors;
- unnecessary.

Keep enumeration.

---

### Pot odds / MDF arithmetic

These are exact formulas. Do not replace them with a net.

You may calibrate thresholds around them, but the core calculation should stay exact.

---

### Exploit overlay rules

Your overlay is already measured strong:

- +300 to +1100 vs exploitable field;
- apparent improvement vs Slumbot sample, though noisy.

A neural net opponent model might eventually help, but your current rule system is:

- bounded;
- interpretable;
- confidence-weighted;
- capped.

That is exactly what you want for exploit logic. Improve diagnostics/calibration first.

---

### Leduc / small exact games

Your Leduc CFR+ now converges:

- **1300 → 16 mbb/hand monotonically**

Do not add a net to something exact/tabular already solves.

---

## Minimal net-as-glue proposal

Build a small supervised **GTO-floor advisor**.

It does **not** replace the bot. It only advises the floor before the exploit overlay.

Decision path:

```text
state
 -> preflop lookup if preflop
 -> postflop floor:
      exact components:
        - pot odds
        - MDF
        - MC/equity
        - exact river enumeration when river
      solver-cache / net advisor:
        - action prior
        - sizing prior
        - confidence/OOD score
      blend/gate
 -> bounded exploit overlay
 -> final action
```

The exploit overlay remains last and capped.

---

## What the net ingests

Keep input minimal and aligned with data you actually have.

### Core state features

- street: preflop/flop/turn/river;
- position:
  - IP/OOP;
  - blinds/button;
  - 6-max position if applicable;
- number of players remaining;
- pot size;
- effective stack;
- SPR;
- amount to call;
- previous action sequence compressed into:
  - open/3bet/4bet flags;
  - c-bet flag;
  - check-raise flag;
  - bet sizes as pot fractions;
- legal action mask.

### Card features

Use one of:

- 52-card binary encoding for hero hand + board;
- rank/suit embeddings;
- board texture features:
  - paired board;
  - monotone/two-tone/rainbow;
  - straight connectivity;
  - high-card structure;
  - flush draw present;
  - straight draw present.

### Existing bot features

This is important because the net is glue, not standalone GTO:

- current heuristic action;
- current heuristic bet size;
- MC equity estimate;
- exact river equity when river;
- pot odds;
- MDF threshold;
- fold-equity estimate;
- hand category:
  - made hand strength;
  - draw type;
  - blockers;
  - nut potential.

### Optional range features

If your bot has range tracking, include coarse summaries:

- hero range percentile;
- opponent range percentile estimate;
- equity vs estimated range;
- nut advantage proxy;
- range advantage proxy.

Do not block the first version on perfect range features.

---

## What the net outputs

Use outputs that plug directly into your existing system.

### Output 1 — action prior

Over your existing legal action abstraction:

```text
fold/check
call
bet small
bet medium
bet large/pot
all-in
raise buckets if applicable
```

Do not invent new sizes in v1.

### Output 2 — sizing prior

If action is bet/raise:

```text
probability over existing bot sizes
```

Again, no new sizing tree yet.

### Output 3 — confidence / OOD score

Examples:

- entropy of predicted distribution;
- distance to nearest solver-cache cluster;
- ensemble disagreement;
- calibration score.

If confidence is low, the bot should fall back to current exact/heuristic logic.

### Optional Output 4 — EV residual

Predict:

```text
EV(action) - EV(current heuristic action)
```

This can help decide whether to override or only blend.

But do not require it for v1 unless you have reliable action EV labels.

---

## Where it plugs in

Postflop floor only.

Not preflop first. Not river equity. Not exploit overlay.

Concrete blend:

```text
if advisor_confidence high and state is in-domain:
    floor_policy = blend(current_heuristic_policy, advisor_policy, alpha)
else:
    floor_policy = current_heuristic_policy

final_policy = bounded_exploit_overlay(floor_policy, opponent_stats)
```

Start with conservative alpha:

```text
alpha = 0.25 or 0.5
```

Only increase if held-out solver EV-gap improves.

---

## Validation against non-net version

You need to beat three baselines:

1. current heuristic floor;
2. nearest-neighbor solver-cache lookup;
3. simple non-net model, e.g. logistic regression / LightGBM / table bucket model.

If the neural net does not beat those, do not use it.

### Primary validation signal

On held-out solver-cache spots:

```text
EV_gap(current floor) - EV_gap(net-advised floor) > 0
```

Preferably:

```text
5–10%+ reduction in EV-gap on targeted postflop spots
```

with no major street regression.

### Secondary validation

- held-out PokerBench cross-entropy / top-k action accuracy improves;
- action frequency by bucket resembles solver;
- duplicate-poker test does not show obvious disaster;
- Slumbot sample only after solver-cache metrics improve.

---

# Q4. Concrete $70 orchestration plan

## Substrate

Use:

```text
CPU-first parallel external-sampling MCCFR / C++ OpenSpiel / custom tabular-regret for small fcpa experiments
```

Use cheap GPU only for:

```text
small supervised GTO-floor advisor training
```

Do not use:

```text
H200/B200 Deep-CFR training
```

Given your measured GPU idleness, those are waste.

---

## Budget reality

$70 is enough for:

- many short CPU/GPU smoke runs;
- supervised model training;
- evaluation harness runs;
- duplicate-poker sanity checks.

$70 is not enough for:

- serious from-scratch NLHE Deep-CFR;
- robust near-GTO self-play blueprint training;
- large leaf-value network training;
- massive Slumbot confidence intervals.

---

# First 3 small runs

## Run 1 — Evaluation harness and baseline error map

### Goal

Before training anything, build the keep/revert dashboard.

### Work

Freeze datasets:

1. held-out TexasSolver cache spots;
2. held-out PokerBench split;
3. small fixed-opponent / duplicate-poker suite;
4. Leduc CFR regression test.

Evaluate current bot:

- exploit overlay off;
- exploit overlay on;
- by street;
- by position;
- by pot size;
- by SPR;
- by action type.

### Primary output

A report like:

```text
Current floor EV-gap:
  flop: X
  turn: Y
  river: Z
  IP: ...
  OOP: ...
  bet/check spots: ...
  call/fold spots: ...
  sizing spots: ...

Current solver TV/cross-entropy:
  ...

Overlay action changes:
  ...
```

### Success criteria

This run succeeds if you can answer:

```text
Where is the current floor losing the most EV vs solver?
```

and reproduce the result with fixed seeds.

### Signal that proves it worked

- Stable paired baseline metrics.
- Action diff reports are interpretable.
- Leduc CFR exploitability regression still shows convergence.
- No dependence on noisy bb/100.

### Rough cost

Likely <$1–$3 if using cheap compute. Mostly engineering/time, not compute.

---

## Run 2 — CPU MCCFR substrate smoke test on `fcpa`

### Goal

Decide whether CPU MCCFR is worth using as an iterative substrate.

### Work

Implement or run:

- C++ OpenSpiel external-sampling MCCFR, or
- custom parallel ES-MCCFR for your small abstraction.

Compare to current Python Deep-CFR:

```text
current: ~47 traversals/sec
target: >500 traversals/sec minimum
better: >2000 traversals/sec
```

Run short:

- 30 minutes;
- 1 hour;
- 3 hours max.

Evaluate the average strategy by mapping it into your bot’s action interface where possible.

### Success criteria

Keep this substrate only if:

1. traversal speed improves at least **10x** over Python;
2. no Leduc regression;
3. `fcpa` average strategy either:
   - improves versus fixed weak opponents, and/or
   - reduces held-out solver EV-gap on matching action spots.

### Signal that proves it worked

```text
traversals/sec per dollar increases
AND held-out solver EV-gap does not worsen
AND some targeted fcpa-compatible spots improve
```

If it only beats a check-call station but worsens solver-gap, it is not useful for your floor.

### Rough cost

If using CPU-rich cheap pod: probably <$5 for smoke testing.  
Do not use H200/B200.

---

## Run 3 — Minimal supervised GTO-floor advisor

### Goal

Test the “net as glue” idea in the cheapest valid way.

### Data

Use:

- TexasSolver caches for primary labels;
- PokerBench 563k GTO decisions for broader supervised signal;
- hold out entire flops/turn classes, not random individual rows only, to test generalization.

### Model

Start tiny:

- MLP or small transformer/card-embedding model;
- also train a non-net baseline:
  - nearest-neighbor;
  - logistic regression;
  - LightGBM / gradient boosted trees if convenient.

Do not train a large poker foundation model.

### Inputs

- street;
- position;
- pot;
- SPR;
- amount to call;
- action history summary;
- legal action mask;
- hero cards;
- board cards;
- board texture;
- current heuristic action;
- current equity/pot-odds/MDF/exact river equity features.

### Outputs

- action prior over existing bot actions;
- sizing prior over existing sizes;
- confidence/OOD score.

### Integration

First evaluate offline only.

Then test blend:

```text
advisor_alpha = 0.25
```

Only in high-confidence postflop spots.

Exploit overlay stays disabled during floor validation.

Then test overlay enabled as guardrail.

### Success criteria

Keep the advisor only if:

```text
held-out solver EV-gap improves by 5–10%+ on targeted postflop spots
AND global EV-gap does not regress materially
AND it beats nearest-neighbor/table baseline
AND PokerBench held-out CE/top-k improves or at least does not conflict
```

If the net does not beat nearest-neighbor / LightGBM / table buckets, do not ship it.

### Signal that proves it worked

The decisive signal is:

```text
paired EV loss per held-out solver spot:
  baseline floor EV loss - net-advised floor EV loss > 0
```

with bootstrap confidence by flop/turn group.

### Rough cost

Small model training: probably <$1–$5 on a cheap GPU/CPU pod.  
No need for H200/B200.

---

# Suggested order of operations

## Week/iteration 1

1. Build held-out solver EV-gap evaluator.
2. Produce floor error map.
3. Identify top 2 leak buckets.

No net yet.

---

## Week/iteration 2

1. Try the cheapest patch for the biggest bucket:
   - table/rule/sizing calibrator;
   - nearest-neighbor solver-cache lookup.
2. Keep only if solver EV-gap improves.

Still no big net.

---

## Week/iteration 3

1. Train minimal supervised advisor.
2. Compare against:
   - current heuristic;
   - nearest-neighbor;
   - simple non-net model.
3. Integrate only via conservative blend and confidence gate.

---

## Week/iteration 4

1. CPU MCCFR `fcpa` smoke if still useful.
2. Use it as an analysis tool or coarse blueprint only if it reduces solver-gap.
3. Otherwise abandon it for now and focus on solver-cache supervised interpolation.

---

# Final recommendation

Your best $70 plan is:

```text
Do not buy big GPU time.
Do not continue Python Deep-CFR as the main loop.
Use CPU-first parallel MCCFR only as a cheap smoke-test / coarse abstraction tool.
Make held-out solver EV-gap the primary keep/revert signal.
Build a minimal supervised postflop GTO-floor advisor as glue over solver caches + PokerBench.
Keep exact/table/rule systems where they already win.
```

The highest-probability improvement path is not “train GTO from scratch.”

It is:

```text
solver-cache error map
 -> identify biggest postflop floor leaks
 -> patch with table/heuristic/nearest-neighbor first
 -> train tiny advisor only where interpolation helps
 -> validate by paired solver EV-gap
 -> then test with duplicate poker / Slumbot as secondary
```

That fits the budget and the measured reality of your system.
