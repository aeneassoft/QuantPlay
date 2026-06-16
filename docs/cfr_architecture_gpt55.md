# Next-run architecture — GPT-5.5

## 0. Brutal verdict

**For the next HUNL run, the single highest-leverage upgrade is:  
move off `fcpa` to a finer betting abstraction.**

Not variance reduction. Not WEVA. Not more MLP width. Not just “run longer.”

Your current result, **~ -72 bb/100 vs GTO Wizard AI**, is exactly what I would expect from:

- pot-only / all-in postflop sizing,
- 20-dim strength-bucket features,
- no resolving,
- static policy-net inference.

DCFR+ helped Leduc because it improves CFR convergence. But HUNL vs GTO Wizard is now mainly an **abstraction / representation / resolving ceiling** problem, not just a convergence problem.

---

# 1. Ranked upgrades by EV / effort

## Rank 1 — **Finer bet abstraction**  
**Do next. Highest EV/effort for the target benchmark.**

Current `fcpa` gives the bot:

- fold,
- call/check,
- pot,
- all-in.

That is too crude for HUNL. Postflop equilibrium strategy uses many small/medium bets: 25–33%, 50%, 75%, pot, overbet, jams. If your only non-all-in aggression is pot, the policy is forced into wrong risk/reward geometry on almost every street.

### Expected effect

Not guaranteed, but realistic engineering prior:

| Setup | Likely plateau vs GTO Wizard |
|---|---:|
| Current `fcpa` policy-net | around **-50 to -80 bb/100** |
| Fine abstraction policy-net, no resolving | around **-20 to -45 bb/100** if trained enough |
| Fine abstraction + resolving/value net | potentially **-5 to -20 bb/100** for a good from-scratch build; closer to 0 only with serious SOTA-level work |

So yes: **finer betting is the first thing that can plausibly move the target by tens of bb/100.**

### Caveat

Full Supremus menu increases branch factor. Your traversal is Python/CPU-bound. Expect iteration time to roughly **1.8–2.8x** current `fcpa`, depending on action pruning and raise caps.

Still worth it.

---

## Rank 2 — **Richer features, but not WEVA**

Direct WEVA is low ROI for your build. The paper’s method needs tabular/warm-up CFR EVs over a game abstraction that does not fit full HUNL. It is not a drop-in fix for `deep_cfr_hunl.py`.

But your current **20-dim scalar strength-bucketed feature set is probably too compressed** for postflop NLHE.

Your net needs to distinguish:

- top pair good kicker vs weak kicker,
- nut blocker vs non-nut blocker,
- overpair vs underpair,
- flush draw vs nut flush draw,
- OESD/gutshot/backdoor,
- paired-board blocker effects,
- board connectivity,
- turn/river texture shifts.

The cheap version is not WEVA. It is:

> keep your current 20 features, add raw card occupancy + explicit hand/board interaction features.

This is low effort and should be bundled with the fine bet abstraction.

### Expected effect

Likely **+5 to +15 bb/100** if the current policy is making broad postflop category mistakes. It will not fix action abstraction by itself.

---

## Rank 3 — **Scale iterations/traversals, but only after changing abstraction**

Just scaling the current `fcpa` build is low ceiling.

You may get some improvement because your Leduc DCFR+ curve is still falling, but I would not expect scaling alone to close a **-72 bb/100** gap.

### Expected effect

| Scaling target | Expected value |
|---|---:|
| More iterations on current `fcpa` | maybe **+5 to +15 bb/100** |
| More iterations after fine bet + richer features | necessary and useful |
| RunPod GPU without fixing Python traversal | mostly self-deception |

Your bottleneck is the Python traversal, not the net. A bigger GPU does not magically help unless you parallelize/vectorize traversal or increase training batch work.

---

## Rank 4 — **Variance-reduction baseline net**

This is scientifically correct and worth doing, but **not the first target-benchmark lever**.

The AAAI-26/PDCFR paper’s DREAM-style baseline is more directly powerful for **outcome sampling**, where sampled-action variance is brutal. You use **external sampling**, where the updating player already enumerates all actions. Your variance comes mainly from opponent/chance sampling.

So the upside is real but more modest.

### Expected effect

- Better training stability.
- Possibly equivalent to **~1.2–2x effective traversal count**, if implemented correctly.
- Does **not** fix the `fcpa` ceiling.
- Does **not** directly reduce AIVAT evaluation noise for a fixed policy.

Also: do **not** copy the outcome-sampling formula verbatim. For ES, the baseline/control variate belongs at sampled opponent/chance nodes, not at the updating-player enumeration nodes.

A valid ES-style control variate at a sampled opponent node is conceptually:

\[
\hat V(h)
=
\sum_a \sigma(a|h)b(h,a)
+
\left(\hat V(ha_s)-b(h,a_s)\right),
\quad a_s \sim \sigma(\cdot|h)
\]

This remains unbiased because:

\[
E[\hat V(h)] = \sum_a \sigma(a|h)V(ha)
\]

But implementing this around chance nodes can be expensive if you have to sum baselines over many card outcomes. So start with opponent nodes only if you do it.

For the **next strong HUNL run**, I would leave VR off unless you have already validated it on Leduc exploitability.

---

## Rank 5 — **CFV value net + depth-limited resolving**

This is the biggest eventual ceiling upgrade, but not the next-run move.

Supremus/DeepStack-style strength comes from:

- public-state range tracking,
- counterfactual value nets,
- continual subgame resolving,
- fine abstraction,
- safe re-solving constraints.

That is a full architecture, not a patch.

### Expected effect

Potentially huge, but effort is also huge.

For your current build, trying to bolt resolving on top of:

- `fcpa`,
- 20-dim features,
- no value net,
- no validated subgame CFV targets,

would be self-deception.

Do it later. Fine abstraction first.

---

# 2. Exact next-run config for RTX 3080 Ti / few hours

## Goal

A decision-quality **directional run**, not a final bot.

You want to test:

> Does finer betting + richer features move the GTO Wizard bb/100 needle enough to justify bigger compute?

---

## Action abstraction

Use this postflop menu:

```text
fold
call/check
0.33 pot
0.50 pot
0.75 pot
1.00 pot
1.25 pot
2.00 pot
all-in
```

Prune illegal/duplicate sizes after rounding/min-raise/all-in logic.

Important details:

- `fold` only legal when `owe > 0`.
- `check/call` always legal.
- Remove duplicate raise sizes caused by stack caps.
- Keep the existing raise cap unchanged for this A/B test.
- Do not simultaneously change raise cap, stack depth, reward scaling, and action menu. You need interpretable results.

### Preflop

If your current action generator blindly uses pot fractions preflop, add a small preflop special case if feasible:

SB first action:

```text
fold
limp/call
raise to 2.0bb
raise to 2.5bb
raise to 3.0bb
all-in
```

Facing a raise:

```text
fold
call
raise 2.5x
raise 3.5x
pot
all-in
```

If this is too much implementation work for the immediate run, use the same pot-fraction menu everywhere, but be aware: **pot-only preflop sizing is also a leak.**

---

## Feature set

Do **not** implement WEVA.

Use:

### Keep current 20 features

Your current features are useful context:

- treys-normalized made strength,
- street one-hot,
- button,
- pot/owe/remaining ratios,
- raise count,
- hole high/low/pair/suited/gap,
- board suit-count/paired/flush-draw.

### Add raw card occupancy

Add:

```text
52-dim private card occupancy
52-dim board card occupancy
```

Total +104 dims.

This is cheap and gives the net access to exact blocker/rank/suit identity instead of forcing everything through a scalar strength bucket.

### Add explicit postflop interaction flags

Add roughly these, all normalized/binary:

```text
hand class one-hot:
  high card
  one pair
  two pair
  trips
  straight
  flush
  full house
  quads
  straight flush

pair interaction:
  overpair
  top pair
  middle pair
  bottom pair
  pocket pair below board
  ace high
  two overcards

draws:
  flush draw
  nut flush draw
  backdoor flush draw
  open-ended straight draw
  gutshot
  double gutter if easy
  straight blocker if easy

board texture:
  rainbow
  two-tone
  monotone
  paired
  trips on board
  four-straight texture
  three-straight texture
  A-high board
  K-high board
  connectedness score
```

Target input size: roughly **140–170 dims**.

This is still tiny. A 3080 Ti will not care.

---

## Target scaling

This is mandatory.

Your chip frame is:

```text
SB = 50
BB = 100
stack = 20000 = 200bb
```

Scale terminal utilities and advantage targets by stack:

\[
u_{\text{scaled}} = u / 20000
\]

So targets are approximately in:

```text
[-1, 1]
```

The PDCFR paper explicitly warns about unstable target magnitude. Do not make the net regress raw chip-scale cumulative advantages.

---

## DCFR+ details to verify before the run

You said DCFR+ is done, but double-check ordering.

Use the paper-consistent cumulative-advantage target:

\[
R_t^{target}
=
\max(R_{t-1},0)
\cdot
\frac{(t-1)^\alpha}{(t-1)^\alpha + 1}
+
\bar r_t
\]

with:

```text
alpha = 2
clip positive before discount/bootstrap
gamma = 2 for average strategy weighting
```

For policy samples, weight by normalized averaging weight:

\[
w_t = (t/T)^\gamma
\]

not raw unbounded \(t^\gamma\), unless you normalize batch weights equivalently.

Store clean strategy targets \(\sigma_t\), not importance-scaled junk.

---

## Network

Use the same architecture for both players unless there is a bug reason not to.

### Advantage nets

```text
input_dim ≈ 140–170
hidden: 256, 256, 256
activation: ReLU or SiLU
output_dim: number of abstract actions
optimizer: AdamW
lr: 1e-3
weight_decay: 1e-5
batch_size: 4096 or 8192
loss: masked MSE or Huber on legal actions
grad_clip: 5.0
dropout: 0.0
```

Do not waste time on NAS, exotic attention, or huge nets. Your issue is not MLP expressivity at 20 inputs; it is abstraction/representation/traversal.

### Policy net

```text
same body: 256, 256, 256
output: masked softmax over legal actions
loss: weighted CE/KL to stored average-strategy targets
batch_size: 4096 or 8192
weighting: (t/T)^2
```

Policy-net quality matters because inference samples directly from it.

---

## Iterations / traversals

Given your measured speed:

```text
current: ~1.9 s/iter @ 80 traversals on CPU
```

With full fine betting, expect:

```text
~3.5–5.5 s/iter
```

For a few-hour local run, use:

```text
iterations: 2500–3500
traversals/iter: 80 using your current convention
players: split evenly if your code supports it
```

Concretely:

```text
T = 3000 iterations
K = 80 traversals/iteration
action menu = fine
features = current 20 + card occupancy + interaction flags
VR baseline = no
DCFR+ = yes
target scaling = /20000
```

If it profiles faster than expected, extend to:

```text
T = 5000
K = 80
```

Do **not** reduce to tiny traversal counts just to hit more iterations. With larger action branching, your per-iteration samples become noisier.

---

## CPU vs GPU

Use:

```text
CPU: traversal/state machine/treys
GPU: minibatch training
```

Do **not** try to “GPU the traversal” unless you are actually vectorizing thousands of states. Calling PyTorch/GPU per recursive node will likely make things worse.

If you want a high-ROI engineering speedup later:

1. multiprocessing traversal workers,
2. cache feature/showdown computations,
3. batch network inference if currently doing per-node forward calls,
4. only then consider C++/Numba.

For the next run: keep traversal CPU.

---

## Variance reduction in this run?

For this next strong run:

```text
variance reduction: NO
```

Reason: an unvalidated ES baseline can silently bias your CFR targets. First prove the fine action abstraction direction.

Add VR after:

- Leduc exact exploitability still passes,
- ES control variate is validated,
- no target-scaling bugs,
- fine abstraction A/B shows value.

---

# 3. Is direct policy-net sampling enough to beat GTO Wizard?

## Short answer

**Probably not.**

Direct policy-net sampling can become a respectable static bot, but against GTO Wizard AI it likely plateaus below parity because:

1. action abstraction mismatch remains,
2. no real-time adaptation to actual bet sizes,
3. no subgame re-solving,
4. no CFV correction at river/turn frontiers,
5. policy net averages over training abstraction errors.

A static policy net is a good floor. It is not the Supremus/DeepStack ceiling.

---

## Plateau estimates

These are **not measured facts**. They are engineering priors grounded in your current -72 bb/100 result and known architecture gaps.

| Architecture | Expected plateau vs GTO Wizard AI |
|---|---:|
| `fcpa` static policy net | **-50 to -80 bb/100** |
| fine-abstraction static policy net | **-20 to -45 bb/100** |
| fine abstraction + richer features + much more traversal | **-15 to -35 bb/100** |
| value net + depth-limited resolving, first competent version | **-15 to -30 bb/100** |
| mature Supremus-style resolving stack | **-5 to -15 bb/100**, maybe near 0 only with serious scale/engineering |

If your goal is merely “better than -72,” policy-net-only can likely do it.

If your goal is “beat or match GTO Wizard AI,” then yes, you probably need real-time resolving or something functionally equivalent.

---

# 4. Cheapest experiment to prove/kill the next direction

## The cheapest useful experiment

Run a **paired A/B mini-training + paired GTO Wizard evaluation**.

You need to test whether fine betting improves the target benchmark before committing big compute.

---

## A/B arms

Train three small agents with identical wall-clock budgets.

### Arm A — current baseline

```text
action menu: fcpa
features: current 20
DCFR+: yes
T: same wall-clock as others
K: 80
```

### Arm B — fine betting only

```text
action menu: F/C/0.33/0.5/0.75/1/1.25/2/all-in
features: current 20
DCFR+: yes
T: same wall-clock
K: 80
```

### Arm C — fine betting + richer features

```text
action menu: same as B
features: current 20 + card occupancy + interaction flags
DCFR+: yes
T: same wall-clock
K: 80
```

Do **not** add variance reduction in this experiment. You want a clean test of abstraction/features.

---

## Mini-run size

Use:

```text
wall-clock: 45–90 minutes per arm
or
T ≈ 800–1200 iterations for fine-menu arms
K = 80
```

This is not final quality. It is a direction test.

---

## Evaluation

First run cheap sanity checks:

```text
vs always-fold
vs check-call
vs random
```

If the fine-menu agent fails these, you have action masking/training bugs.

Then run GTO Wizard AIVAT:

```text
n = 500 paired hands minimum
n = 1000 if cheap enough
same seeds/deals/seats across agents if possible
```

Your known noise:

```text
±8 bb/100 at n=2500
```

So approximate unpaired noise scales like:

```text
n=1000: ±13 bb/100
n=500:  ±18 bb/100
```

Paired deals should reduce comparison variance, but do not assume magic.

---

## Decision rule

At `n=500`, only believe large differences.

Continue with fine abstraction if:

```text
Arm B beats Arm A by ≥20–25 bb/100
or
Arm C beats Arm A by ≥20–25 bb/100
```

At `n=1000`, threshold can be closer to:

```text
≥15–20 bb/100
```

Interpretation:

| Result | Conclusion |
|---|---|
| B improves a lot over A | betting abstraction is the main next lever |
| B flat, C improves | representation/features were bottlenecking fine betting |
| B and C both worse | undertraining/branching/action mapping issue; do not scale blindly |
| B/C crush weak bots but not Wizard | abstraction helps basics, but resolving/value net likely needed |
| no clear result within noise | run longer or paired eval; do not declare victory |

---

## What would be fabricated?

These would be fabricated/self-deceptive claims:

- “Variance reduction will fix -72 bb/100.”  
  No. It improves sample efficiency, not action abstraction.

- “WEVA can be plugged into full HUNL Deep CFR.”  
  No. The paper’s actual method does not fit full HUNL.

- “A bigger MLP will solve broad postflop quality.”  
  No. With 20 compressed features and `fcpa`, architecture tuning is mostly noise.

- “RunPod GPU will fix traversal speed.”  
  No. Your bottleneck is Python traversal unless you parallelize/vectorize.

- “Policy-net-only can definitely beat GTO Wizard.”  
  No. Maybe it improves substantially, but near-parity likely needs resolving.

---

## Final recommendation

For the next run, do this exact package:

```text
1. Replace fcpa with fine betting:
   F/C/0.33/0.5/0.75/1/1.25/2/all-in

2. Add cheap richer features:
   current 20
   + 52 private-card occupancy
   + 52 board-card occupancy
   + explicit hand-class/draw/texture flags

3. Keep DCFR+:
   alpha = 2
   gamma = 2
   cumulative advantage bootstrap
   target scaling by /20000
   verify clip-before-discount ordering

4. No variance-reduction baseline yet.

5. Run:
   T ≈ 3000
   K = 80 traversals/iter
   CPU traversal
   GPU minibatch training

6. Evaluate with paired A/B:
   current fcpa vs fine vs fine+features
   n=500–1000 GTO Wizard hands first
```

If that does not move the needle by at least **~15–25 bb/100** in the cheap paired test, do **not** burn big compute. Then the next serious direction is not “more iterations”; it is **resolving/value-net architecture**.
