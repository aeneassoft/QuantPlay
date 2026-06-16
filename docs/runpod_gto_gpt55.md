# $140 RunPod multi-CPU run -> closer to GTO (gpt-5.5)

## Bottom line

With $140, I would **not** do a blind “more strategy-frequency cache” run. Your measured result, **-32.6 ± 11 bb/100 despite matching solver frequencies**, says the leak is not lack of generic flop/turn/river frequencies. It is **public-state/range/SPR/line collapse**.

The highest-leverage $140 plan is:

1. **Patch/extend `mass_solve.py` to dump CFVs and action EVs, not just strategies.**
2. Spend most CPU on **turn-to-river solved public states** because:
   - river real-time resolver already exists,
   - turn resolver is next,
   - turn CFVs become the training target for a **flop depth-limited resolver/value net**.
3. Also solve a smaller but targeted set of flop and river states for a richer public-state blueprint.
4. Reserve a small amount for a short GPU training run.

Expected output from the $140 run:

- **~600k solved root public states**
  - ~50k flop roots
  - ~300k turn roots
  - ~250k river roots
- **2M–5M usable decision-node training rows** after extracting internal nodes.
- **Root CFVs for both players / all private combos** for every solved state.
- Realistic EV gain:
  - richer blueprint alone: **+4 to +8 bb/100**
  - + live river + turn resolving: **+10 to +18 bb/100 total**
  - + CFV-net-assisted flop resolving: **+13 to +23 bb/100 total**
- Expected near-term result if integration is solid: from **-33** to roughly **-20 to -15 bb/100**. Beating Opus 4.6’s **-20.4** point estimate is plausible; getting near **-3** is not a $140 outcome.

---

# 1. What to solve

## Core principle

Every solved item must be a **public state**, not just a board.

A useful training row needs:

- board
- street
- pot
- effective stack / SPR
- player to act
- IP/OOP
- full action history
- current bet faced, if any
- legal bet sizes
- both players’ ranges at that node
- solver strategy per combo
- root CFVs / hand EVs
- ideally action EVs per combo

If a solve does not include the line/ranges/SPR/facing-size context, it risks reproducing MVP#1’s failure mode.

---

## Preflop range-pair coverage

Use the actual ranges from your preflop/range tracker. Do not invent symmetric generic ranges.

Target mix:

| Preflop line / range pair | Weight | Reason |
|---|---:|---|
| SB/BTN opens, BB calls: SRP, BTN IP PFR | 45% | Highest-volume HU postflop spot |
| SB limp, BB check | 10% | If your bot limps; otherwise reallocate to SRP |
| SB limp, BB iso-raises, SB calls | 5% | Probe/donk/delayed-cbet context |
| SB opens, BB 3-bets, SB calls: 3BP, BB OOP PFR | 30% | Lower SPR, large EV mistakes |
| SB opens, BB 3-bets, SB 4-bets, BB calls | 10% | Low-SPR high-leverage pots |

If your actual strategy has no limp branch, do:

- SRP: 55%
- 3BP: 35%
- 4BP: 10%

Do **not** spend meaningful compute on stack depths or preflop lines that do not occur in the GTO Wizard benchmark or your actual bot.

---

## Board/runout sampling

Use a hybrid sampler:

### Flop boards

Use all **1,755 canonical isomorphic flops** at least once for the main SRP range pair, then oversample by texture and match frequency.

Texture-balanced buckets:

- paired / unpaired
- monotone / two-tone / rainbow
- A-high / K-high / broadway / middling / low
- connected / semi-connected / disconnected
- straight-heavy vs dry
- high-card advantage boards
- low-board BB advantage boards

Allocation:

- 60% natural-deal weighted
- 40% texture-uniform

Reason: natural weighting gives EV realism; texture-uniform prevents the net from being blind on rare but strategically distinct boards.

### Turn and river runouts

Sample from actual flop public states and stratify by:

- overcard turn
- board-pairing turn
- flush-completing turn
- straight-completing turn
- total brick
- river flush complete / brick
- river straight complete / brick
- paired-board river
- four-liner rivers

Do not just sample random turn/river cards. You need runouts that change range/nut advantage.

---

## SPR / stack grid

Primary stack should be the benchmark stack. If GTO Wizard is fixed-stack, do **80%+ at that exact stack**.

Postflop SPR variation should mostly come from line/pot geometry:

| Spot | Typical SPR bins to cover |
|---|---|
| Limped/SRP flop | 15–25 |
| SRP turn after small cbet-call | 8–18 |
| SRP turn after large cbet-call / raise-call | 3–10 |
| 3BP flop | 3–7 |
| 3BP turn | 1–4 |
| 4BP flop/turn | 0.5–2 |
| River | 0.25–5 |

Only add separate starting-stack samples if the match format actually has varying stacks. If needed, use:

- 80% benchmark stack
- 10% 75bb
- 10% 150bb

A broad 20bb–300bb grid is overkill and will not move EV for the benchmark.

---

## Bet-size abstraction

Do not solve with 6 sizes on every street. That is overkill for $140 and creates noisy sparse labels.

Use compact trees that match your runtime resolver abstraction.

### Flop

For SRP:

- IP/OOP open bet sizes: **33%, 75%**
- raises: **3x**, plus **jam if SPR ≤ 3**
- max raises: 2

For 3BP:

- open bet sizes: **25%, 50%**
- raises: **2.5x**, jam if SPR ≤ 3
- max raises: 2

For 4BP:

- open bet sizes: **25%, 50%, all-in**
- max raises: 1 or jam-only after raise

### Turn

- open bet sizes: **50%, 100%**
- add **150%** only when SPR > 3 and board/nut-advantage texture supports overbetting
- raises: **2.5x**, all-in
- max raises: 2

### River

- open bet sizes: **33%, 75%, 125%**
- all-in if jam ≤ 200% pot
- facing bet: fold/call plus raise **3x** or all-in
- max raises: 1 or 2

### Facing-bet defense per size

This is important because MVP#1 is blind to size-faced context.

Explicitly generate/extract nodes facing:

- 25%
- 33%
- 50%
- 75%
- 100%
- 150%
- all-in / geometric jam

Important: do **not** train defense against a bet using villain’s unconditional pre-bet range. Either:

1. solve the parent node with that bet size available and extract the child after villain bets, or  
2. use your range tracker’s conditional range after the observed bet.

The input range pair must reflect the line and the size faced.

---

## Street priority

Because MVP#2 already has a river resolver, do not blow the whole budget on river.

Recommended CPU allocation by importance:

| Street solve type | CPU priority | Why |
|---|---:|---|
| Turn-to-terminal solves with CFVs | Highest | Feeds turn resolver and CFV net |
| Compact flop solves | Medium | Fixes OOP XR/cbet/probe blueprint leaks |
| River solves | Medium-low | Useful for blueprint/fallback, but live resolver supersedes cache |

Concrete target:

| Solve type | Target root solves | Purpose |
|---|---:|---|
| Flop roots | 50k | Blueprint, OOP XR, cbet, probe, low-SPR 3BP/4BP |
| Turn roots | 300k | Turn resolver training, CFV net labels |
| River roots | 250k | Facing-size defense, value/bluff sizing, fallback blueprint |

---

## Node-type sampling

### Flop nodes

Within the 50k flop roots:

| Node type | Share |
|---|---:|
| SRP flop root, BTN IP PFR vs BB caller | 40% |
| BB/OOP facing IP cbet | 20% |
| OOP check-raise opportunity after IP cbet | 15% |
| 3BP flop root / facing cbet | 20% |
| 4BP / very low SPR | 5% |

You should extract internal nodes from these solves, especially:

- OOP check/call/check-raise facing 33% and 75%
- IP response to check-raise
- OOP probe opportunities after flop checks through
- delayed cbet nodes

### Turn nodes

Within the 300k turn roots:

| Turn public-state class | Share |
|---|---:|
| SRP flop cbet-call → turn barrel/check node | 25% |
| Flop check-check → turn probe/delayed cbet | 20% |
| Flop bet-raise-call → turn low-SPR node | 15% |
| 3BP flop cbet-call/check-check → turn | 25% |
| Facing turn bet-size challenge nodes | 15% |

Prioritize turns where the previous action changed ranges significantly:

- flop cbet-call
- flop x/r-call
- flop check-check
- 3BP cbet-call
- delayed/probe lines

### River nodes

Within the 250k river roots:

| River state class | Share |
|---|---:|
| Facing bet defense by size | 45% |
| Checked-to value/bluff sizing | 30% |
| River after turn barrel-call | 15% |
| Raise-over-bet / bluff-raise nodes | 10% |

River solves are fast and useful, but do not exceed this unless the CPU run finishes early. The live river resolver should handle the real high-leverage river spots.

---

# 2. What to dump

## Strategy frequencies alone are not enough

Your current cache stores strategy frequencies only. That is insufficient for the next step.

For a richer blueprint, strategies are needed.

For a CFV/value net, **CFVs are mandatory**.

For regret-aware policy training, action EVs are highly useful.

---

## Required dump schema

Use compressed Parquet, HDF5, or zstd JSONL. Avoid raw giant JSON if possible.

### Per solved public state

```json
{
  "state_id": "...",
  "street": "turn",
  "board": ["As", "7d", "3d", "Tc"],
  "button_player": "IP",
  "player_to_act": "OOP",
  "pot_bb": 14.5,
  "eff_stack_bb": 86.0,
  "spr": 5.93,
  "action_history": [
    {"street": "preflop", "action": "SB_open", "size_bb": 2.5},
    {"street": "preflop", "action": "BB_call"},
    {"street": "flop", "action": "BB_check"},
    {"street": "flop", "action": "SB_bet", "size_pot": 0.33},
    {"street": "flop", "action": "BB_call"}
  ],
  "range_pair_id": "srp_btn_open_bb_call_cbet33_call",
  "oop_range_1326": "...",
  "ip_range_1326": "...",
  "legal_actions": ["check", "bet_50", "bet_100"],
  "bet_abstraction": "...",
  "solver": {
    "iterations": 1200,
    "target_gap": 0.01,
    "wall_time_sec": 47.2,
    "exploitability_est": 0.008,
    "seed": 123
  }
}
```

### Per decision node extracted from the solve

```json
{
  "state_id": "...",
  "node_path": "turn_root/check/bet_75",
  "street": "turn",
  "player_to_act": "IP",
  "pot_bb": 14.5,
  "eff_stack_bb": 86.0,
  "facing_bet_bb": 7.25,
  "range_oop_1326": "...",
  "range_ip_1326": "...",
  "reach_prob": 0.031,
  "legal_actions": ["fold", "call", "raise_2.5x", "allin"],
  "strategy_1326xA": "...",
  "action_ev_1326xA": "... optional but recommended",
  "cfv_oop_1326": "...",
  "cfv_ip_1326": "..."
}
```

For storage, use:

- `float16` for strategies and CFVs if normalized by pot
- `float32` for validation/high-accuracy holdout
- zstd compression
- masks for impossible combos

Expected data size:

- root-only CFVs: small, roughly 5–10 KB/state compressed
- strategy + action EV internal nodes: larger
- total expected: **50–150 GB compressed**

Do not dump regrets or per-iteration solver internals.

---

## CFV definition to dump

For player `i` and hand combo `h`:

\[
V_i(h, s) =
E_{h_{-i} \sim r_{-i} \mid board,h}
[u_i \mid s,h,h_{-i},\bar{\sigma}]
\]

Important properties:

- conditional on player `i` holding combo `h`
- opponent range is card-removal normalized
- not multiplied by hero’s own reach probability
- units should be bb or pot-normalized bb
- dump both players’ CFVs
- invalid combos get mask = 0

Also dump range EV sanity checks:

\[
EV_i(s) = \sum_h r_i(h) V_i(h,s)
\]

For zero-sum consistency, weighted EVs should be approximately opposite after rake/rounding assumptions.

---

## Does TexasSolver dump CFVs?

Treat the answer as: **your current harness does not, so you must add it.**

TexasSolver necessarily has enough information after solving:

- average strategy
- game tree
- ranges
- terminal evaluator

If the public API/CLI exposes per-hand EVs, serialize them.

If not, add a post-solve evaluator:

1. take the solved average strategy tree,
2. recursively evaluate each node,
3. for each player/combo, compute conditional hand EV,
4. for each legal action, evaluate child action EV,
5. serialize root CFVs and selected node CFVs/action EVs.

Do not try to infer CFVs from aggregate strategy frequencies. That does not work.

If your old cache contains full tree per-combo strategies, you can compute CFVs offline from it. If it only stores root or aggregate frequencies, it is insufficient.

---

# 3. RunPod box and budget

## Recommended instance

Use CPU, not GPU, for solving.

Preferred:

- **64 vCPU**
- **256 GB RAM**
- local NVMe
- AMD EPYC community/spot CPU pod
- price cap: **$0.75–$0.90/hr**

If only 128 GB RAM is available, reduce concurrency.

Run config:

- one TexasSolver process per worker
- `OMP_NUM_THREADS=1`
- `RAYON_NUM_THREADS=1`
- use **48 workers** on 64 vCPU
- leave remaining CPU for OS, compression, queue, logging
- RAM-adaptive worker cap in `mass_solve.py`

Do not run one huge multithreaded solver job. You want many independent one-thread solves.

---

## Budget plan

Assuming **64 vCPU / 256 GB @ $0.80/hr**:

| Item | Cost |
|---|---:|
| CPU pilot + production: 150 hr × $0.80/hr | $120 |
| Short GPU training run: RTX 4090/A5000/A4000, 20–30 hr | $8–$15 |
| Storage / retry buffer | $5–$10 |
| Total | $133–$145 |

If the CPU pod costs $1.00/hr, reduce CPU runtime to ~120 hr and scale target counts down by ~20%.

---

## Expected solve scale

Assume:

- 48 active solver workers
- compact trees
- conservative median solve times:
  - flop: 75 sec
  - turn: 55 sec
  - river: 10 sec

Target production mix:

| Street | Root solves | Median sec/solve | Worker-hours |
|---|---:|---:|---:|
| Flop | 50,000 | 75 | 1,042 |
| Turn | 300,000 | 55 | 4,583 |
| River | 250,000 | 10 | 694 |
| Failed/retry/validation overhead | — | — | 400 |
| **Total** | **600,000** | — | **6,719 worker-hr** |

With 48 workers:

\[
6719 / 48 \approx 140 \text{ wall hours}
\]

At $0.80/hr:

\[
140 \times 0.80 = \$112
\]

Plus pilot and training brings you near the full $140.

If your measured median solve times are faster, do **not** just create millions of river states. Spend extra on:

1. more turn CFV states, up to 500k–600k,
2. more flop states, up to 80k,
3. higher-quality holdout solves.

If solve times are slower, cut in this order:

1. river count,
2. flop count,
3. then turn count last.

Minimum useful run:

- 30k flop
- 150k turn
- 100k river

Below that, the value net will be thin.

---

# 4. Model/data pipeline

## Blueprint policy model

The new blueprint must be public-state-conditioned.

Do **not** train another street-only frequency advisor.

### Inputs

For each decision:

- hero private hand
- board cards
- street
- IP/OOP
- player to act
- pot
- stack
- SPR
- action history encoded as pot fractions/check/call/raise tokens
- facing bet size
- legal action mask
- both ranges:
  - full 1326 combo vectors, or
  - compressed range representation plus equity/nut/blocker features

Useful derived features:

- hand equity vs opponent range
- hand class: pair, two pair, draw, blocker, nut blocker, showdown value
- range equity
- nut advantage
- range polarity estimate
- pot odds if facing bet
- MDF target as analytic feature, not final policy

### Outputs

Distribution over legal action buckets:

- fold
- check/call
- bet/raise size 1
- bet/raise size 2
- jam

Train per combo, not only aggregate action frequency.

### Loss

Primary:

\[
L_{\text{policy}} = KL(\sigma_{\text{solver}} || \sigma_{\text{model}})
\]

Weight by:

- public-state reach
- combo reach
- pot size
- street leverage

If action EVs are dumped, add EV-aware regret loss:

\[
L_{\text{EV}} =
\sum_a \pi_{\text{model}}(a)
\left[
\max_{a'} Q(a') - Q(a)
\right]
\]

This matters because exact frequency matching on indifferent actions is less important than avoiding large-EV mistakes.

---

## CFV/value net

This is the main reason to do the run.

### Input

At a public state:

- board
- street
- pot
- stack
- SPR
- player to act
- IP/OOP
- action history
- both 1326-combo ranges
- legal action abstraction, if relevant

### Output

Two vectors:

- `cfv_oop_1326`
- `cfv_ip_1326`

Normalize target values by pot:

\[
\hat{V} = V / \max(pot, 1bb)
\]

Use masks for impossible combos.

### Loss

Use Huber or L1:

\[
L_{\text{CFV}} =
\sum_h w_h \cdot
\left|
V_{\text{model}}(h) - V_{\text{solver}}(h)
\right|
\]

Weights:

- combo reach
- public-state reach
- pot leverage
- extra weight on hands near decision boundaries

Also track:

- per-combo L1 in pot units
- range EV error
- top/bottom percentile hand EV error
- zero-sum consistency

A decent initial target:

- turn CFV L1: **≤ 0.03–0.05 pot**
- range EV error: **≤ 0.01–0.02 pot**

If you cannot hit that, do not trust flop depth-limited resolving yet.

---

## Training run

Reserve a short GPU run.

Recommended:

- RTX 4090 / A5000 / A4000 class
- 20–30 hours
- expected cost: **$8–$15**

Training split:

- split by board/runout and preflop line, not random rows
- keep 5–10% high-accuracy holdout
- include suit canonicalization or suit augmentation carefully
- never leak same public state family into train and test

Training order:

1. Train CFV net on turn roots first.
2. Train river/fallback blueprint.
3. Train full public-state blueprint.
4. Validate offline EV-regret against solver action EVs.
5. Only then integrate with resolver.

---

# 5. Realistic bb/100 impact

Starting point:

- current measured vs GTO Wizard AI: **-32.6 ± 11 bb/100**
- point estimate behind Opus 4.6: **-20.4**
- gap to Opus point estimate: about **12 bb/100**

Because n=30 and CI is large, do not overinterpret small changes. But these are reasonable expectations:

| Upgrade | Expected gain | Expected new level |
|---|---:|---:|
| Richer public-state blueprint only | +4 to +8 bb/100 | -29 to -25 |
| + live river resolver | additional +3 to +6 | -26 to -20 |
| + turn resolver using exact river subtree | additional +5 to +10 | -21 to -14 |
| + CFV-net-assisted flop resolving | additional +3 to +7 | -18 to -10 |

Near-term likely outcome if implementation is solid:

- **-20 to -15 bb/100**

That is materially closer to GTO and plausibly beats Opus’s point estimate.

Unrealistic for $140:

- reaching **-3 bb/100**
- building a GTO Wizard-scale equilibrium + deep RL system
- self-play over hundreds of millions of hands

---

# 6. Is a big mass-solve the right use of $140?

## Yes, but only if CFV-enabled and public-state-targeted

A big solve run is correct if it produces:

- solved public states,
- exact range-conditioned labels,
- CFVs,
- action EVs,
- node context.

A big solve run is wrong if it produces:

- board-only strategy frequencies,
- street-only averages,
- no action history,
- no ranges,
- no CFVs.

Given your measured -33, strategy-frequency-only mass solving is likely to improve KL while barely moving bb/100.

The single highest-leverage $140 plan is:

> **Targeted turn-heavy CFV solve set + richer blueprint labels + short GPU training + integration into MVP#2 turn/flop resolving.**

Not generic self-play. Not river-only solving. Not huge action trees.

---

# 7. Concrete launch recipe

## Step 0: patch CFV dump before spending the money

Add to `mass_solve.py` / TexasSolver wrapper:

Required flags:

```bash
--dump-strategy
--dump-root-cfv
--dump-node-cfv
--dump-action-ev
--dump-ranges
--dump-action-history
--dump-solver-metadata
--min-node-reach 1e-5
--compress zstd
```

If `--dump-root-cfv` is not working, stop. Do not launch the full run.

---

## Step 1: pilot run

Run 1,000–2,000 solves first.

Example:

```bash
python extraction/mass_solve.py \
  --config configs/hunl_public_state_140.yaml \
  --targets flop=200 turn=1200 river=600 \
  --workers 48 \
  --solver-threads 1 \
  --ram-adaptive \
  --dump-strategy \
  --dump-root-cfv \
  --dump-node-cfv \
  --dump-action-ev \
  --min-node-reach 1e-5 \
  --out /workspace/solves/pilot \
  --compress zstd
```

Validate:

- CFVs exist
- action EVs exist
- impossible combos masked
- range EV sanity checks pass
- zero-sum sanity checks pass
- median wall times match expectation
- memory per worker is safe
- file sizes are acceptable

Only then launch production.

---

## Step 2: production run

Example:

```bash
export OMP_NUM_THREADS=1
export RAYON_NUM_THREADS=1
export MKL_NUM_THREADS=1

python extraction/mass_solve.py \
  --config configs/hunl_public_state_140.yaml \
  --targets flop=50000 turn=300000 river=250000 \
  --workers 48 \
  --solver-threads 1 \
  --ram-adaptive \
  --max-rss-gb-per-worker 4.0 \
  --checkpoint-every 1 \
  --retry-failed 2 \
  --dump-strategy \
  --dump-root-cfv \
  --dump-node-cfv \
  --dump-action-ev \
  --dump-ranges \
  --dump-action-history \
  --min-node-reach 1e-5 \
  --holdout-frac 0.08 \
  --out /workspace/solves/hunl_140_run \
  --compress zstd
```

Suggested config skeleton:

```yaml
game:
  blinds: [0.5, 1.0]
  benchmark_stack_bb: 100
  use_actual_benchmark_stack: true

range_pairs:
  srp_btn_open_bb_call: 0.45
  limp_check: 0.10
  limp_iso_call: 0.05
  threebet_pot_bb_3b_sb_call: 0.30
  fourbet_pot: 0.10

board_sampler:
  flop:
    mode: hybrid
    natural_weight: 0.60
    texture_uniform_weight: 0.40
    cover_all_1755: true
  turn:
    stratify:
      overcard: true
      flush_complete: true
      straight_complete: true
      board_pair: true
      brick: true
  river:
    stratify:
      flush_complete: true
      straight_complete: true
      board_pair: true
      brick: true

street_targets:
  flop: 50000
  turn: 300000
  river: 250000

bet_abstraction:
  flop_srp:
    bet_sizes_pot: [0.33, 0.75]
    raise_sizes: ["3x", "jam_if_spr_le_3"]
    max_raises: 2
  flop_3bp:
    bet_sizes_pot: [0.25, 0.50]
    raise_sizes: ["2.5x", "jam_if_spr_le_3"]
    max_raises: 2
  turn:
    bet_sizes_pot: [0.50, 1.00]
    overbet_size_pot: 1.50
    overbet_condition: "spr_gt_3_and_texture_enabled"
    raise_sizes: ["2.5x", "allin"]
    max_raises: 2
  river:
    bet_sizes_pot: [0.33, 0.75, 1.25]
    jam_condition: "jam_le_2x_pot"
    raise_sizes: ["3x", "allin"]
    max_raises: 1

facing_bet_challenge_sizes:
  pot_fracs: [0.25, 0.33, 0.50, 0.75, 1.00, 1.50]
  include_allin: true

solver_quality:
  flop:
    max_iter: 800
    target_gap_pot_frac: 0.015
    time_cap_sec: 180
  turn:
    max_iter: 1200
    target_gap_pot_frac: 0.010
    time_cap_sec: 120
  river:
    max_iter: 2500
    target_gap_pot_frac: 0.005
    time_cap_sec: 30

dump:
  strategy: true
  root_cfv: true
  node_cfv: true
  action_ev: true
  min_node_reach: 1.0e-5
  dtype: float16
  validation_dtype: float32
  compression: zstd
```

Tune iteration counts based on the pilot. Do not chase ultra-low exploitability on every solve; abstraction and model error dominate here.

---

# 8. Do NOT do this

1. **Do not spend $140 on board-only flop solves.**  
   That repeats MVP#1’s context-collapse failure.

2. **Do not dump only aggregate frequencies.**  
   You need per-combo strategies, ranges, action histories, and CFVs.

3. **Do not over-invest in river mass solving.**  
   You already have a live river resolver. River cache is fallback/training, not the main EV unlock.

4. **Do not use huge bet trees.**  
   Five or six bet sizes per street will burn CPU/RAM and create sparse labels. Use compact trees matching runtime.

5. **Do not train self-play RL from scratch with $140.**  
   GTO Wizard-scale self-play is hundreds of millions of hands plus strong infra. $140 will not get you there.

6. **Do not solve irrelevant stack depths.**  
   If benchmark is fixed 100bb, 200bb/300bb solves mostly waste EV budget.

7. **Do not deploy a CFV net without validation.**  
   Bad CFVs are worse than no CFVs because they poison resolving.

8. **Do not compare after another n=30 sample and declare victory.**  
   Your current ±11 bb/100 error bar is large. Use larger AIVAT samples before claiming you beat Opus.

---

## Final recommendation

Spend the $140 on a **turn-heavy, CFV-enabled public-state solve run**:

- **64 vCPU / 256 GB CPU pod**
- **48 parallel TexasSolver workers**
- **~150 CPU wall hours**
- **~600k root public-state solves**
- **CFVs + action EVs dumped**
- **short GPU training run for CFV net + public-state blueprint**

This is the most direct compute use tied to your measured leak and MVP#2 architecture. Strategy-only mass solving is cheap-looking but likely low EV. The money should buy you the labels needed for turn resolving and flop depth-limited resolving, not another pile of context-collapsed frequencies.
