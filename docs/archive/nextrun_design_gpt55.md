# Next-run design — poker-practical (gpt-5.5)

## Brutal bottom line

- Your current CFV net is **hard no-go**: held-out MAE ≈ `0.96 × 2600 = 2496 chips ≈ 25 bb`. That is essentially random at the scale of the decisions. In a 20–60bb pot / 40–80bb effective turn state, a 25bb leaf error can make the flop resolver confidently choose catastrophic lines.
- **99 training samples is not “a little small”; it is a smoke test only.** For a useful HU 200bb flop resolver, you are in the **50k–250k solved turn-state** regime, with ~100k a realistic first serious target.
- However: **do not spend Phase B money before the $0 range-tracker keystone.** Your own X-ray says ~87% of −72bb/100 was preflop and postflop-non-jam was only ~−10bb/100. A mature CFV net cannot recover 50bb/100 unless the new X-ray says the error moved there. The range tracker is both higher ROI and a prerequisite for sampling the right CFV states.

Also, one important engineering warning: I do **not** fully accept “features are definitely sound” until you prove there is no 169-class suit-aliasing problem. Real flop lines create suit-specific combo distributions. A 169-class range often cannot distinguish `AhQh` from `AsQs` on heart boards. Data volume will not fix information that is absent from the input.

---

# 1. Coverage needed for a useful HU 200bb flop CFV net

A “training point” should be:

> One solved **turn boundary state**:  
> `turn board + exact line-narrowed OOP range + exact line-narrowed IP range + pot + effective stack`, with target CFVs from a Nash-ish **turn+river continuation solve**.

Not uniform random ranges. Not random 169 weights. The training distribution must look like the states your live flop resolver will actually query.

## The net must cover these axes

### A. Public board coverage

The turn input is a 4-card board, but practically you need coverage over:

#### Flop texture families

At minimum:

| Flop family | Examples | Why it matters |
|---|---:|---|
| Paired | `KK4`, `772`, `QQJ` | Polarization, trips/nut advantage |
| Monotone | `Ah9h3h` | Suit blockers dominate |
| Two-tone | `Ks8s4d` | FD interaction, turn flush completion |
| Rainbow | `A72r`, `JT4r` | Backdoor turns, delayed equity |
| Connected | `987`, `T98`, `J97` | Straights, pair+draw |
| Disconnected/static | `A72`, `K83` | Range advantage, thin value |
| High-card | `AKx`, `AQx`, `KQx` | Preflop range asymmetry |
| Low/mid | `764`, `953`, `T65` | BB/OOP equity density |
| Ace-high dry | `A72r` | C-bet/check strategy sensitive |
| Broadway-dynamic | `QJT`, `KJ9` | Nuts shift heavily by turn |

#### Turn-card families

For each flop family, you need turns that:

| Turn type | Examples |
|---|---|
| Complete flush | two-tone flop → third suit |
| Add flush draw | rainbow flop → two-tone turn |
| Pair board | top/middle/bottom pair |
| Complete straight | `T98` + `J/7`, `QJ9` + `T/K` |
| Add straight density | low/mid connector turns |
| Overcard | `K` on `T74`, `A` on `Q83` |
| Brick | offsuit low non-connector |
| Change nut advantage | A/K turns, flush turns, board-pairing turns |

There are ~16k suit-isomorphic 4-card turn boards. You do not need every canonical board crossed with every line, but if you only sample “random boards,” you will under-cover the rare but high-EV-error textures: monotone, paired, four-straight, flush-completing, low connected.

Recommended board sampling:

- **70% natural reach-weighted** from real preflop/flop lines.
- **30% stratified oversample** of rare/high-impact textures:
  - monotone flops,
  - flush-completing turns,
  - paired turns,
  - four-straight boards,
  - 4BP/low-SPR dynamic boards,
  - nut-changing overcards.

---

### B. Range-pair coverage

The ranges must come from your actual live range tracker / preflop blueprint / flop resolver.

You need at least these preflop buckets:

| Preflop pot type | Must include? | Notes |
|---|---:|---|
| SRP | Yes | BTN/SB open, BB call. This is most volume. |
| Limped pots, if your bot plays them | If applicable | Do not include if bot never queries them. |
| 3BP | Yes | Very important at 200bb because mistakes are larger. |
| 4BP | Yes | Lower frequency, high impact. |
| 5BP non-all-in | If exists | Usually rare, but if 200bb tree has it, include. |

Then within each preflop bucket, sample flop line leaves that can reach the turn:

#### SRP examples

- OOP check, IP check-back.
- OOP check, IP c-bet small, OOP call.
- OOP check, IP c-bet large, OOP call.
- OOP check, IP c-bet, OOP raise, IP call.
- OOP check, IP c-bet, OOP raise, IP 3bet non-all-in, OOP call.
- OOP donk lines, if your live abstraction allows donks.
- Delayed c-bet lines if the flop tree includes check-back.

#### 3BP examples

- OOP check, IP check.
- OOP check, IP small c-bet, OOP call.
- OOP check, IP large c-bet, OOP call.
- OOP check-raise, IP call.
- Bet/raise/call non-all-in lines.
- Low-SPR jam-adjacent lines.

#### 4BP examples

- Check/check.
- Small bet/call.
- Bet/jam terminal excluded.
- Bet/raise/call non-terminal if possible.
- SPR ≤ 2 turn states heavily represented.

Do **not** train mainly on terminal folds or all-ins. The CFV net is needed for **non-terminal turn-boundary leaves**.

---

### C. Pot / SPR coverage

For 200bb HU, you need more than the current pilot’s apparent `pot 20–60bb, eff 40–80bb` region.

Approximate bins:

| Pot type | Typical turn pot | Typical SPR | Importance |
|---|---:|---:|---|
| SRP passive | 4–12bb | 15–50 | High frequency, lower immediate EV swing |
| SRP bet/call | 8–25bb | 8–25 | Very common |
| SRP raised | 20–70bb | 2–10 | High error cost |
| 3BP passive | 18–35bb | 5–10 | Important |
| 3BP bet/call | 30–80bb | 2–6 | Very important |
| 4BP | 45–140bb | 0.5–4 | Low frequency, high impact |
| Jam-adjacent | 80bb+ | <1.5 | Must be right or avoid net |

For training, I would weight samples roughly by:

> `query_reach × pot_weight × exploration_floor`

where `pot_weight` should oversample big pots, e.g. `min(4, pot_bb / 20)`.

Reason: a 1bb CFV error in a 5bb pot is annoying. A 10bb CFV error in a 120bb 4BP is fatal.

---

## Sampling procedure that matches the live range tracker

Concrete generation loop:

1. Sample a real preflop line from the near-Nash blueprint:
   - SRP / 3BP / 4BP according to live frequency, with an exploration floor.
2. Sample a legal flop:
   - mostly natural deck frequency,
   - with stratified oversampling of rare textures.
3. Run your current flop resolver or blueprint strategy to generate flop action leaves.
4. Pick a non-terminal turn-boundary leaf:
   - probability proportional to reach,
   - but oversample raises, big pots, low SPR, and rare board classes.
5. Deal/sample the turn card.
6. Record:
   - board,
   - pot,
   - effective stack,
   - exact OOP combo range,
   - exact IP combo range,
   - 169 projection if you insist on 169 input.
7. Add modest perturbations:
   - 80–90% exact solver/live range states,
   - 10–20% perturbed opponent deviations / nearby sizes / slightly noisy ranges.
8. Solve turn+river continuation and store per-hand/per-class CFVs.

The perturbations matter because live opponent ranges and your resolver ranges will not be exactly blueprint-Nash.

---

## How many distinct training points?

For a **first useful HU 200bb flop CFV net**:

| Dataset size | Honest assessment |
|---:|---|
| 100–1k | Pipeline only. Not meaningful. Your 99 train samples are here. |
| 5k | Learning curve / feature-aliasing test. Still not deployable. |
| 10k–20k | Can tell whether features/labels are viable. Maybe useful for narrow SRP-only experiments. |
| 50k | Minimum plausible for common SRP/3BP lines if safety gates pass. |
| 100k–250k | Realistic first serious target for broad HU 200bb flop resolving. |
| 500k+ | Stronger, but likely overkill until X-ray proves postflop is worth that spend. |
| Millions | DeepStack-scale; not ROI-justified from your measured −10bb/100 postflop term yet. |

Given your own statement that 99 is ~1000x too few, the natural target is **~100k turn states**, not “a few thousand.”

But I would not jump straight to 100k. Next CFV run should be:

1. **5k full-quality samples**: prove labels, features, splits, learning curve.
2. **20k samples**: check whether held-out error falls materially.
3. Only then scale to **100k+**.

If held-out MAE plateaus above ~2–3bb even at 20k, the blocker is not just data volume.

---

## Critical feature warning: 169-class ranges may be aliased

Your planned input is:

> 4-card board + both players’ 169-class weighted ranges + pot/eff  
> output: 169-class CFVs for both players.

This is compact, but dangerous.

Real flop lines create suit-specific distributions. Example:

- Board: `Ah 9h 4c 2d`
- The class `KQs` includes different combos:
  - `KhQh`: nut-flush blocker/draw interaction.
  - `KsQs`: no heart blocker.
  - `KdQd`: different backdoor/blocker profile.

Two states can have identical 169-class weights but different combo-level suit weights. Solver CFVs can differ meaningfully. More data cannot recover hidden suit information.

Before the big run, do this aliasing test:

- Construct pairs of turn states with identical 169-class ranges/pot/board encoding but different legal combo suit distributions.
- Direct-solve both.
- Compare true CFVs.

If weighted CFV L1 differs by more than **0.75–1.0bb** in common states or **1.5bb+** in big pots, 169-only input is not safe. Then you need either:

- combo-level range features, or
- board-relative suit/blocker features, or
- board-aware hand buckets finer than 169.

---

# 2. Bet abstraction for turn+river data-gen

First: the current “solve all 48 rivers separately at the turn pot and average” is **not the correct target** for a flop→turn CFV leaf.

At the turn boundary, the continuation value should include:

> turn betting → river chance → river betting.

Averaging 48 river-only solves with pot fixed at the turn pot approximates a game where the turn betting round does not exist. That is not the Nash continuation your flop resolver needs.

For production labels, use a **turn+river solve** with chance inside the tree. Use `k_rivers` only for debugging/pipeline tests, not final labels.

---

## Minimum faithful menu

The minimum I would trust for data-gen is not massive. You need a compact abstraction with:

- small bet,
- geometric / medium bet,
- overbet,
- conditional all-in,
- limited raises.

### Recommended first-bet menu

For fixed sizing:

> **33%, 75%, 150%, conditional all-in**

That is better than `33/66/100/150/all-in` everywhere.

Why?

- 66% and 100% are often close substitutes.
- 150% captures polar overbet/nut-advantage lines.
- All-in is mandatory at low SPR.
- Adding every intermediate size explodes solve time without proportional CFV improvement.

If you can use dynamic sizing, use:

> **33%, geometric, 150%, conditional all-in**

where geometric means the size that sets up a natural river shove, clipped to a sane range.

For turn first bet:

`geo ≈ (SPR - 1) / 3` pot, clipped around `66%–125%`.

Examples:

| SPR | Geometric-ish turn bet |
|---:|---:|
| 2 | ~33% pot |
| 3 | ~66% pot |
| 4 | ~100% pot |
| 5 | ~133% pot |

So a fixed `75%` is an acceptable approximation for many 3BP/4BP states.

---

## Conditional all-in rule

Do not include absurd 20x-pot jams in high-SPR SRP turns. But do include jam when it is strategically real.

Recommended:

| Street | Include all-in when |
|---|---:|
| Turn | stack/pot ≤ 2.5–3.0 |
| River | stack/pot ≤ 2.0–2.5 |
| 4BP / jam-adjacent | almost always include |

If SPR is 0.7–2.0, omitting all-in is dangerous. That is exactly where a wrong abstraction can create confident but terrible values.

---

## Raise abstraction

You need raises, but not many.

Minimum:

### Facing a turn bet

Allow:

- fold,
- call,
- one non-all-in raise,
- all-in.

The non-all-in raise should be geometric/pot-like. Do not add 3 raise sizes unless doing a benchmark validation solve.

### Facing a river bet

Allow:

- fold,
- call,
- one polar raise, usually all-in or large raise.

River raises are rare and polar. One raise size is usually enough for CFV-label purposes.

### Cap

Use a raise cap:

- Turn: bet / raise / call or jam. Avoid multi-raise wars except in low-SPR spots.
- River: bet / raise / call. Usually one raise cap.

---

## What is overkill?

For your measured situation, overkill is:

- `25/33/50/66/75/100/125/150/200/all-in` at every node.
- Multiple raise sizes on both turn and river.
- Solving all 48 river-only subgames separately for a turn CFV target.
- Full-size abstraction on low-frequency lines before range tracker is fixed.

A good compact menu:

> Turn: `33 / 75 or geo / 150 / AI when SPR ≤ 2.5–3`  
> River: `33 / 75 / 150 / AI when SPR ≤ 2–2.5`  
> Raises: one non-all-in raise + jam, cap at one raise.

That is the minimum I would call value-faithful without exploding time.

---

# 3. ROI honesty

Your measured baseline:

- Bot: **−72bb/100** vs GTO Wizard AI.
- EV X-ray: **87% preflop**.
- Therefore preflop term ≈ `0.87 × 72 = 62.6bb/100`.
- Non-preflop remainder ≈ `9.4bb/100`.
- You also state postflop-non-jam was the smallest X-ray term, around **−10bb/100**.

So a flop CFV net is not a 72bb/100 fix.

## Realistic recovery from a good CFV net

Assuming preflop is truly near-Nash now and the residual is postflop:

| CFV net maturity | Expected recovery vs Wizard |
|---|---:|
| Current 99-sample net | Negative / unsafe |
| 5k–20k experimental net | 0–3bb/100 if lucky, not deployable without gates |
| 50k decent narrow net | 2–5bb/100 |
| 100k–250k good line-distribution net | 4–8bb/100 realistic |
| Excellent mature CFV + correct ranges + good abstraction | 8–12bb/100 optimistic ceiling |
| 20bb/100+ from CFV alone | Not supported by your X-ray unless new measurement changes |

If the bot is still around **−53bb/100** after the preflop blueprint, the CFV net is unlikely to explain that by itself. You need a new X-ray after the preflop wiring stabilizes. Either:

1. the −53 partial result is noisy / preflop not fully fixed, or  
2. the X-ray terms changed and postflop is now much larger, or  
3. there is another infrastructure bug.

Do not assume a CFV net recovers 50bb/100 without measurement.

---

## Range-tracker keystone ROI

The $0 range tracker is higher ROI than Phase B CFV right now.

Why?

1. Your existing turn/river TexasSolver resolver can only be sharp if given correct line-narrowed ranges.
2. Wrong ranges make a solver confidently solve the wrong game.
3. Correct line-narrowed ranges are also required to generate the CFV training distribution.
4. It directly attacks the measured postflop term without training risk.
5. It gives you better data for the next X-ray.

Expected value:

| Work item | Cost | Risk | Realistic gain |
|---|---:|---:|---:|
| Correct preflop blueprint | Already in progress | Low/medium | Largest: original ~63bb/100 term |
| Range-tracker keystone | $0 / engineering only | Low | 3–8bb/100 plausible, maybe most of postflop-non-jam |
| Existing turn/river resolver with correct ranges | Low once tracker works | Medium latency | 2–6bb/100 plausible |
| CFV Phase B | High: 50k–250k solves | High if bad net | 4–8bb/100 realistic, 8–12 optimistic |
| CFV before range tracker | High | Very high | Bad ROI / likely off-distribution |

Recommended order:

1. **Finish and verify preflop blueprint wiring.**
2. **Implement exact combo-level line-narrowed range tracker.**
3. Feed current turn/river TexasSolver with those ranges.
4. Re-run EV X-ray vs Wizard AI.
5. If postflop/flop-leaf error is still >5–8bb/100 and latency prevents direct solving, then scale CFV Phase B.
6. Only then do the 100k+ CFV run.

The CFV net is the right long-term architecture, but it is **lower ROI than the range tracker now**.

---

# 4. Deploy-safety gates

Current net:

- Held-out MAE ≈ 25bb.
- Train MSE → 0.
- Heldout only 24 samples.
- Random/noisy generalization.

That is an absolute no-go.

Before the net touches a real decision, I would require these gates.

---

## A. Data split gate

Heldout must not be random tiny holdout.

Require:

- At least **5k–10k heldout turn states**.
- Split by:
  - board family,
  - preflop pot type,
  - flop line family,
  - pot/SPR bin.
- Include at least **1k high-impact states**:
  - pot ≥ 40bb,
  - SPR ≤ 2.5,
  - 4BP,
  - raised SRP/3BP,
  - monotone/flush-completing/paired/four-straight turns.

No go if the test set is 24 states.

---

## B. Label quality gate

The target solve must be stable.

Require for target labels:

| Label metric | Threshold |
|---|---:|
| Turn+river solve, not river-only average | Mandatory |
| Solver convergence / Nash gap | ≤0.25bb or ≤1% pot, whichever larger |
| No timeout/partial labels | Mandatory |
| Same abstraction as deployment | Mandatory |
| Full chance treatment | Preferred; no K-river production labels |

If using `k_rivers` for pilot, fine. But not for production CFV unless you quantify label variance and it is below the model error target.

---

## C. Weighted CFV L1 / MAE gate

Do not use unweighted 169-class MAE alone. Weight by live combo reach.

Define for player `p`:

`WL1_p = Σ_h range_p(h) × |V_net_p(h) - V_solve_p(h)|`

in bb.

Required:

| Metric | Go threshold |
|---|---:|
| Mean weighted per-hand L1 | ≤0.75bb |
| Median weighted per-hand L1 | ≤0.50bb |
| 95th percentile state WL1 | ≤1.5bb |
| High-pot p95 WL1 | ≤1.5bb, preferably ≤1.0bb |
| Any high-reach catastrophic state | No state >3bb WL1 |

In chips, with `bb = 100 chips`:

| bb | chips |
|---:|---:|
| 0.5bb | 50 chips |
| 0.75bb | 75 chips |
| 1.5bb | 150 chips |
| 3bb | 300 chips |

Your current heldout MAE ≈ **2496 chips**, so you need roughly a **25x–50x error reduction** before live use.

---

## D. Range-EV error gate

The resolver mostly cares about range EVs and action ranking.

For each heldout state:

`EV_error_p = |Σ_h range_p(h) × (V_net_p(h) - V_solve_p(h))|`

Require:

| Metric | Go threshold |
|---|---:|
| Mean range-EV error | ≤0.25bb |
| 95th percentile range-EV error | ≤0.75bb |
| High-pot p95 | ≤1.0bb |
| Signed bias by player | ≤0.10–0.15bb |
| Signed bias by line/texture/SPR slice | ≤0.50bb |

A net with low average MAE but systematic +EV bias for IP in 3BP flush-completing turns is unsafe.

---

## E. Zero-sum gate

Under your label convention, the same invariant the solver labels satisfy must hold.

Usually:

`RangeEV_OOP + RangeEV_IP ≈ 0`

after accounting for whether values are defined as net chip EV from the current state.

Required:

| Metric | Threshold |
|---|---:|
| Mean zero-sum residual | ≤0.05bb |
| 99th percentile residual | ≤0.25bb |
| Systematic position bias | No |

Best solution: enforce this structurally or by post-processing. If the net outputs both players independently and violates zero-sum, that is asking for silent live errors.

---

## F. Nut / air / blocker sanity gates

These are not sufficient for deployment, but they catch bugs.

Require targeted tests on heldout and synthetic states:

| Test | Go threshold |
|---|---:|
| Nut hands not valued below pure air on same board/range state | Mandatory except tiny numerical tolerance |
| Clear dominated river hands monotonic | >99% pass |
| Violation magnitude | <0.5bb for non-strategic monotonic pairs |
| Flush blocker sanity on monotone/two-tone boards | No systematic inversion |
| Board-blocked impossible classes | Masked / zero-weighted correctly |

Be careful: turn CFVs are not strictly monotonic by raw equity because blockers and betting strategy matter. But if the nut flush is valued below no-pair no-draw air on the same board, the net is broken.

---

## G. Slice robustness gate

Report all metrics by slice:

- SRP / 3BP / 4BP.
- OOP/IP.
- Check-check / bet-call / raise-call.
- Pot bins.
- SPR bins.
- Board type:
  - paired,
  - monotone,
  - two-tone,
  - flush-completing,
  - four-straight,
  - overcard turn,
  - brick turn.

Go threshold:

- No important slice has mean WL1 > **1.5bb**.
- No important slice has mean range-EV bias > **0.5bb**.
- No high-pot slice has catastrophic outliers > **3bb**.

If the global average passes but 4BP monotone turns fail, no deployment.

---

## H. Root decision regret gate

This is the most important practical gate.

Take heldout flop roots. Compare:

1. Flop resolver using net CFV leaf.
2. Benchmark resolver using direct turn+river solve / much stronger depth.

For each real decision, compute regret of the action chosen by the net-backed resolver under benchmark values.

Require:

| Metric | Go threshold |
|---|---:|
| Mean root action regret | ≤0.25bb/decision |
| 95th percentile regret | ≤1.0bb |
| Any pot ≥30bb catastrophic regret | No action >3bb worse |
| Jam/call/fold boundary errors | Zero tolerance for obvious >2bb mistakes |

Action-frequency L1 is less important than regret. Strategies can differ in near-tie spots. What matters is not choosing actions that are materially worse.

---

## I. OOD gate and fallback

The net must know when not to answer.

Require an out-of-distribution detector using:

- pot,
- SPR,
- board family,
- range entropy,
- range L1 distance to training clusters,
- preflop/flop line ID,
- nearest-neighbor or embedding distance.

Rule:

> If a live query is outside the 99th percentile of training distribution distance, do not use the net. Fall back to direct TexasSolver or conservative baseline.

No OOD fallback = no deployment.

---

## J. 169-class aliasing gate

Before a 100k run, specifically test the 169 abstraction.

Construct same-board, same-169-range states with different suit-specific combo distributions. Direct solve both. Compare target CFVs.

Go threshold:

| Metric | Threshold |
|---|---:|
| Mean alias-induced WL1 | ≤0.5–0.75bb |
| High-pot alias WL1 | ≤1.0–1.5bb |
| Large alias failures | <1–2% of tested states |

If this fails, the architecture is missing information. More samples will not solve it.

---

# Recommended next run

Not Phase B full-scale yet.

## Next run I would actually do

1. **Implement range tracker first.**
   - Exact combo weights preferred.
   - 169 projection only as a derived feature, not the source of truth.

2. **Generate 5k line-distribution turn states**, not uniform random.
   - From SRP/3BP/4BP real lines.
   - Include stratified board/pot/SPR oversampling.
   - Use turn+river solves, not river-only averaging.

3. **Train learning curve checkpoints:**
   - 500,
   - 1k,
   - 2k,
   - 5k.

4. **Run aliasing test for 169-class input.**

5. If metrics improve cleanly, scale to:
   - 20k,
   - then 100k.

## Go/no-go after 5k

At 5k, I would not deploy, but I would expect clear movement.

If heldout error is still, say, >8–10bb, something is wrong beyond volume.

If it drops toward 3–5bb and learning curve is clean, scaling to 100k is plausible.

## Final honest priority

Order should be:

1. Preflop blueprint stabilization.
2. Range-tracker keystone.
3. Existing turn/river resolver fed correct ranges.
4. Re-run EV X-ray.
5. Only if postflop/flop-leaf remains material, scale CFV net.

A good CFV net is valuable, but from your measured numbers it is **not the highest-ROI next step**. The range tracker is.
