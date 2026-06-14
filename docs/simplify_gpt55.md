# Simplification consult — OpenAI gpt-5.5

## Brutal summary: the real GOLD

Ranked by **simplification gained / effort** for your current bot:

1. **Canonicalized exact/cached equity oracle** — replace per-decision MC with deterministic lookup / exact enumeration on cache miss. This is the biggest win.
2. **Bitset/vector range algebra** — replace Python combo loops and `range_top` recomputation with masks/weights/blocker operations.
3. **Suit isomorphism canonicalization** — collapse board/hand states massively; makes equity caching practical.
4. **Equity-distribution / bucket abstraction** — compress hand/range/board thinking into 16–64 buckets + a few board features.
5. **Mean-field / population model for 6-max** — do not model 5 opponents jointly; model aggregate opponent pressure and active-count/position statistics.
6. **Position as low-dimensional features** — replace per-seat strategy explosion with `{players behind, IP/OOP, blind tax, opener distance, SPR}`.
7. **Low-rank / GAM strategy distillation** — compress solver tables into small parametric policies; avoid Deep-CFR unless absolutely necessary.

The biggest warning: **Deep-CFR / CFV nets are probably not your next simplification.** They may improve strength, but they add training complexity, debugging burden, distribution-shift risk, and infra cost. For this bot, the next layer should be **deterministic amortization + abstraction**, not more learning machinery.

---

# 1. Canonicalized exact/cached equity oracle

### Name

**Amortized exact equity via canonical state lookup**

### CS/math/ML idea

Memoization + quotienting by symmetry: many poker states are equivalent up to suit relabeling and range discretization. Compute equity once for a canonical representative, then reuse it.

### Replaces/compresses

Your current bottleneck:

```text
per-decision Monte Carlo equity_vs_range / equity_vs_class_range
~120–1500 treys 7-card eval sims per decision
```

Replace with:

```text
equity = EquityCache[street, canonical_board, canonical_hero_hand, range_id]
```

or exact enumeration on cache miss.

### Complexity / compute reduction

Runtime:

```text
MC:      O(num_sims * hand_eval)
lookup:  O(1)
miss:    exact enumeration, then cached forever
```

Board suit-isomorphism counts:

```text
raw flops:  C(52,3)  = 22,100      canonical flops:  1,755
raw turns:  C(52,4)  = 270,725     canonical turns:  ~16,432
raw rivers: C(52,5)  = 2,598,960   canonical rivers: ~134,459
```

This is exactly the kind of compression you want: not smarter poker, just fewer distinct states.

### Fits your engine

Define a small fixed set of range IDs:

```text
R0 = top 5%
R1 = top 10%
R2 = top 15%
...
or your existing ps.range_top classes
```

Then build:

```python
key = (
    street,
    canonicalize(board, hero_hand),
    hero_hand_canonical_id,
    villain_range_id,
)
equity = equity_cache.get(key)

if equity is None:
    equity = exact_equity_vs_range(hero_hand, board, villain_range_mask)
    equity_cache[key] = equity
```

Use SQLite / LMDB / disk-backed numpy arrays. Do not over-engineer.

For river, exact equity is cheap:

```text
iterate villain combos only
```

For turn:

```text
iterate villain combos × remaining rivers
```

For flop:

```text
iterate villain combos × C(remaining_cards, 2)
```

Flop exact can be expensive, but you only pay once per canonical state/range.

### Verification

For random states:

1. Compare cache/exact result to your current MC with a huge sample, e.g. 100k sims.
2. Track:

```text
mean absolute error
max absolute error
sign agreement around pot-odds thresholds
```

3. Your expected result:

```text
exact/cache error: 0 except range discretization
MC error: noisy, especially at 120 sims
```

### Accuracy cost

None if the range is the same combo-weighted range.

Accuracy loss only comes from:

```text
range abstraction / percentile bucket
interpolation between range IDs
ignoring action-history-specific range shape
```

But those costs already exist in your bot.

### Verdict

**GOLD.** This should be priority #1.

---

# 2. Street-specific exact equity instead of MC

### Name

**Deterministic street enumeration**

### CS/math/ML idea

Use exact finite enumeration when the remaining uncertainty is small. This is not “closed form” symbolically, but it is deterministic, low-variance, and often cheaper than MC once vectorized.

### Replaces/compresses

Replaces:

```text
random rollout sampling
```

with:

```text
exact enumeration of remaining cards
```

### Complexity / compute reduction

River:

```text
O(villain_combos)
```

Turn:

```text
O(villain_combos × ~44 rivers)
```

Flop:

```text
O(villain_combos × ~990 turn-river pairs)
```

For river and turn this is usually cheap enough in Python if you use vectorized arrays / precomputed ranks / bitsets.

### Fits your engine

Implement three functions:

```python
equity_river_exact(hero, board5, villain_mask)
equity_turn_exact(hero, board4, villain_mask)
equity_flop_cached(hero, board3, villain_mask)
```

Policy:

```text
river: always exact
turn: exact or cached exact
flop: cached exact; fallback to low-discrepancy sample if cache miss
```

For flop cache misses, if exact enumeration is too slow, use deterministic quasi-MC instead of random MC:

```text
fixed deck ordering
Sobol / stratified turn-river samples
same samples per canonical state
```

This gives reproducible errors and much lower variance.

### Verification

Compare:

```text
river exact vs brute force
turn exact vs brute force
flop cached exact vs high-sample MC
```

Track decision flips near thresholds.

### Accuracy cost

None for exact.

Small controlled cost if using deterministic subsampling on flop cache misses.

### Verdict

**GOLD for river/turn. Very good for flop when combined with caching.**

---

# 3. Bitset/vector range algebra

### Name

**Range masks and blocker algebra**

### CS/math/ML idea

Represent sets of hands as bitsets / boolean masks over the 1,326 possible combos. Updating a range after blockers becomes a fast mask operation.

### Replaces/compresses

Replaces repeated Python-level combo filtering:

```python
for combo in all_combos:
    if combo in range and not blocked:
        ...
```

with:

```python
legal = range_mask & ~blocked_mask
weights = range_weights * legal
```

### Complexity / compute reduction

Conceptual compression:

```text
1326 combo objects -> fixed 1326-bit/float vector
range_top recomputation -> precomputed mask lookup
blocker removal -> bitwise AND
```

Runtime reduction is often huge in Python because you eliminate object loops.

### Fits your engine

Precompute:

```python
combo_to_cards[1326, 2]
combo_class[1326]          # AA, AKs, AKo, etc.
preflop_strength_rank[1326]
range_masks[range_id, 1326]
```

At decision time:

```python
blocked = cards_to_blocker_mask(hero_cards + board)
villain_mask = range_masks[range_id] & ~blocked
```

If using weighted ranges:

```python
villain_weights = base_range_weights[range_id].copy()
villain_weights[blocked] = 0
villain_weights /= villain_weights.sum()
```

### Verification

For every range ID:

```text
old combo list == new mask-derived combo list
```

For random blocker sets:

```text
old filtered combos == new masked combos
```

Equity should match exactly.

### Accuracy cost

None.

### Verdict

**GOLD. Easy, boring, high-value.**

---

# 4. Suit isomorphism canonicalization

### Name

**Group-action quotienting / suit canonicalization**

### CS/math/ML idea

Poker suits are symmetric except for flush structure. Two states that differ only by renaming suits have identical equities and strategically identical properties.

### Replaces/compresses

Replaces raw state identity:

```text
Ah Kh on Qh 7h 2c
```

and equivalent suit-renamings with one canonical representative.

### Complexity / compute reduction

Board states:

```text
22,100 flops  -> 1,755 canonical flops
270,725 turns -> ~16,432 canonical turns
2.6M rivers   -> ~134,459 canonical rivers
```

This makes caching and precomputation feasible.

### Fits your engine

Implement:

```python
canonical_board, suit_map = canonicalize_cards(board)
canonical_hero = apply_suit_map(hero_hand)
key = canonical_board + canonical_hero
```

Do not make this fancy. A brute-force canonicalizer over 24 suit permutations is fine:

```python
best = min(encode(apply_perm(cards, perm)) for perm in all_24_suit_perms)
```

For 5–7 cards, 24 permutations is cheap compared to equity MC.

### Verification

Property tests:

```python
equity(state) == equity(any_suit_permutation(state))
canonicalize(state) == canonicalize(any_suit_permutation(state))
```

### Accuracy cost

None.

### Verdict

**GOLD. Required for good equity caching.**

---

# 5. Equity-distribution buckets instead of raw combo/range reasoning

### Name

**Information abstraction by equity histograms**

### CS/math/ML idea

Replace detailed hand identity with a low-dimensional summary of its behavior: current equity, draw potential, nut potential, and equity distribution over future cards.

This is an established abstraction idea from poker AI, but it is still underused in ordinary bot engineering.

### Replaces/compresses

Replaces:

```text
1326 combos
large board-specific rule keys
hand-class percentiles only
```

with something like:

```text
16–64 hand buckets per street
board texture bucket
range bucket histogram
```

### Complexity / compute reduction

Example:

```text
1326 combos -> 32 buckets
22,100 flops -> maybe 50–200 board texture buckets for rule overlay
full range vector -> histogram over 32 buckets
```

For each hand on a board, store:

```text
EHS       = current equity
PPOT      = positive potential / improvement chance
NPOT      = negative potential / vulnerability
NutScore  = probability of making/top retaining nutted hand
Blockers  = blocker score to nuts / draws
```

Then cluster into buckets.

### Fits your engine

You can use this for:

```text
exploit overlay
sizing choice
value/bluff/foldcatch nudges
multiway approximations
strategy distillation features
```

Do **not** necessarily use it as the only equity source if exact cached equity is available.

A simple feature vector:

```python
features = [
    equity_vs_range,
    equity_percentile_in_hero_range,
    villain_range_nut_advantage,
    hero_hand_bucket,
    board_pairness,
    flush_possible,
    flush_draw_possible,
    straightiness,
    high_card_rank,
    spr,
    position_ip,
]
```

### Verification

Take TexasSolver cache states and test whether buckets preserve decisions:

```text
bucket-level predicted action vs solver action
EV loss per abstraction bucket
```

Important diagnostic:

```text
within-bucket EV variance
```

If a bucket contains hands with very different solver EVs, split it.

### Accuracy cost

Moderate.

Equity buckets lose blocker nuance and suit-specific strategic effects. Mitigate by keeping a few explicit blocker features:

```text
blocks nut flush
blocks top straight
has nut flush draw
has pair+draw
```

### Verdict

**Very good.** Use for strategy/rules, not as a replacement for exact equity everywhere.

---

# 6. Range moments as sufficient-ish statistics

### Name

**Moment compression of ranges**

### CS/math/ML idea

For many decisions, you do not need the full opponent range; you need a few range-level statistics: mean equity, nut density, air density, draw density, and fold/call elasticity.

This is not perfectly sufficient in the mathematical sense, but it is a useful engineering approximation.

### Replaces/compresses

Replaces full range reasoning:

```text
villain has weighted distribution over 1326 combos
```

with:

```text
villain_range_summary = {
    mean_strength,
    top_5_density,
    top_15_density,
    weak_showdown_density,
    draw_density,
    nut_advantage,
    blocker_sensitive_fold_rate,
}
```

### Complexity / compute reduction

```text
1326 weighted combos -> 6–12 scalar features
```

This is especially useful for your bounded exploit overlay.

### Fits your engine

At each street, after forming villain’s range mask:

```python
summary = summarize_range(villain_weights, board)
```

Precompute per combo/board bucket:

```text
hand_strength_bucket
draw_bucket
nut_bucket
blocker bucket
```

Then range summary is just weighted sums.

Example:

```python
nut_density = weights[nut_bucket].sum()
draw_density = weights[flush_draw | oesd | combo_draw].sum()
air_density = weights[no_pair_no_draw].sum()
```

### Verification

Compare decisions using full range vs moments on a held-out set:

```text
action agreement
EV difference
sizing difference
fold/call threshold flips
```

### Accuracy cost

Medium.

Moments can miss important composition differences:

```text
same equity but different blockers
same nut density but different redraws
same mean but different polarization
```

Use moments for overlays and sizing, not for final all-in equity unless calibrated.

### Verdict

**Good. Especially for simplifying the exploit rule set.**

---

# 7. Compact strategy via low-rank / GAM distillation

### Name

**Low-rank or additive strategy distillation**

### CS/math/ML idea

Large strategy tables are often approximately low-dimensional. Fit action probabilities as a simple function of a few features instead of storing enormous tables.

Prefer:

```text
logistic regression
isotonic thresholds
small GAM
low-rank matrix factorization
```

Avoid:

```text
big neural nets
Deep-CFR unless necessary
transformers/GNNs
```

### Replaces/compresses

Replaces:

```text
huge GTO lookup tables
many hand/board/position-specific rules
```

with:

```text
π(action | features)
```

Example model:

```python
logit_raise = (
    b0
    + f1(equity)
    + f2(range_percentile)
    + f3(nut_advantage)
    + f4(spr)
    + f5(position_ip)
    + f6(board_texture)
)
```

### Complexity / compute reduction

Instead of:

```text
millions of table entries
```

you may get:

```text
50–500 parameters
```

or:

```text
rank-4 / rank-8 factors
```

for action matrices.

### Fits your engine

Take your TexasSolver cache and PokerBench lookup.

Train a simple model to predict:

```text
fold/call/raise/check/bet size bucket
```

Use features you already compute:

```text
equity
pot odds
SPR
position
board texture
range percentile
nut advantage
draw density
blocker flags
```

You can implement with sklearn:

```python
LogisticRegression
HistGradientBoostingClassifier with shallow depth
IsotonicRegression for threshold curves
```

But the cleanest version is often:

```text
per-street threshold model:
if equity > T_value(features): value bet
elif blocker_score > T_bluff(features): bluff
elif equity > T_call(features): call
else fold
```

### Verification

Do not use raw action accuracy alone. Track:

```text
cross-entropy vs solver strategy
EV loss when plugged into solver state
threshold flip rate near indifference
exploitability proxy if available
```

### Accuracy cost

Low to medium.

The model will miss mixed-strategy fine structure and rare board-specific effects. That is acceptable if EV loss is small.

### Verdict

**GOLD if you distill into simple models. HYPE if you replace this with Deep-CFR before exhausting table compression.**

---

# 8. Multi-player simplification: mean-field / population model

### Name

**Mean-field opponent aggregation**

### CS/math/ML idea

Instead of modeling every opponent jointly, approximate the other players as samples from position-conditioned population distributions. Track aggregate pressure, not the full joint state.

This is common in population games and mean-field game approximations.

### Replaces/compresses

The impossible object:

```text
joint range over 5 opponents
~1326^5 combo combinations
```

becomes:

```text
active_count
position classes
per-opponent range summaries
aggregate call/fold pressure
aggregate nut pressure
```

### Complexity / compute reduction

From exponential:

```text
O(1326^N)
```

to roughly linear:

```text
O(N × K)
```

where:

```text
N = number of opponents
K = number of buckets/range moments
```

### Fits your engine

For each opponent `i`, maintain:

```python
opp_i = {
    position,
    range_id,
    fold_prob_to_size,
    call_prob_to_size,
    raise_prob_to_size,
    hand_bucket_histogram,
    nut_density,
    draw_density,
}
```

Aggregate:

```python
p_all_fold = product_i(p_fold_i)

p_at_least_one_call = 1 - product_i(p_fold_i)

p_someone_strong = 1 - product_i(1 - nut_density_i)

effective_opposition = sum_i(call_prob_i * range_strength_i)
```

For betting EV:

```python
EV_bet =
    p_all_fold * pot
    + sum_over_call_scenarios_approx(...)
```

Simplified version:

```python
p_called = 1 - Π_i p_fold_i
equity_when_called = weighted_average_equity_against_calling_ranges
EV = p_all_fold * pot + p_called * (equity_when_called * final_pot - bet)
```

This is not exact, but it is massively simpler.

### Verification

Use high-sample exact/MC multiway equity as a test harness:

```text
random 3-way, 4-way, 5-way states
compare mean-field equity to sampled multiway equity
calibrate correction curves by active_count/street/board_texture
```

Track:

```text
MAE by number of opponents
decision flip rate
overbluffing frequency multiway
```

### Accuracy cost

Medium to high in multiway pots.

Mean-field misses:

```text
card removal between villains
squeeze dynamics
one villain's action changing another's range
multiway nut-peddling effects
```

But it is much better than pretending 6 seats act independently without aggregate coupling.

### Verdict

**GOLD conceptually for 6-max simplification.** Not exact, but the right kind of wrong.

---

# 9. Multiway equity via “hazard” / survival approximation

### Name

**Survival probability approximation**

### CS/math/ML idea

For multiway showdown, approximate hero’s chance of surviving all opponents as a product of per-opponent survival probabilities.

Mathematically:

```text
P(hero beats everyone) ≈ Π_i P(hero beats opponent i)
```

or with loss probabilities:

```text
P(hero loses to someone) ≈ 1 - Π_i (1 - q_i)
```

where `q_i` is opponent `i`’s probability of beating hero.

### Replaces/compresses

Replaces:

```text
joint multi-opponent equity enumeration
```

with:

```text
several heads-up equity/rank-CDF lookups
```

### Complexity / compute reduction

```text
multiway exact: O(product of opponent combo counts)
approx:        O(number of opponents × bucket lookup)
```

### Fits your engine

If you already have heads-up equity/cache:

```python
q_i = loss_probability(hero, board, opp_i_range)
p_win_multiway = product(1 - q_i for i in opponents)
```

Better than raw heads-up equity:

precompute opponent range CDF over hand strength buckets:

```python
opp_cdf_i = hand_strength_cdf(opp_i_range, board)
hero_rank = hand_rank_bucket(hero, board)
p_i_worse = opp_cdf_i[hero_rank - 1]
p_win = product_i(p_i_worse)
```

For turn/flop, use expected future rank bucket transitions.

### Verification

Compare against sampled true multiway equity:

```text
2 opponents exact
3–5 opponents high-sample MC
```

Calibrate:

```python
p_win_calibrated = isotonic_regression(p_win_raw, true_win)
```

by:

```text
street
active_count
board_texture
```

### Accuracy cost

Medium.

It ignores dependence from blockers and villain-villain card conflicts. Usually it over/underestimates in dense ranges unless calibrated.

### Verdict

**Good practical simplifier.** Use calibration.

---

# 10. Position as low-dimensional parameters, not six independent worlds

### Name

**Positional feature factorization**

### CS/math/ML idea

Position is not a categorical magic label; most of its strategic effect comes from a few variables:

```text
players behind
blind obligation
relative position postflop
initiative
SPR
opener distance
```

Use those as features instead of separate independent policies per seat.

### Replaces/compresses

Replaces:

```text
per-position open/defend tables
6 independent seat policies
```

with:

```text
shared policy + positional features
```

### Complexity / compute reduction

Instead of:

```text
6 separate policies/tables
```

use one policy conditioned on:

```python
features = {
    players_behind,
    is_button,
    is_blind,
    posted_blind_amount,
    has_position_postflop,
    relative_position_index,
    opener_position_index,
    callers_between,
    spr,
}
```

Preflop examples:

```text
UTG: players_behind = 5
CO:  players_behind = 2
BTN: players_behind = 0, has position advantage
SB:  blind_tax high, OOP postflop
BB:  closing_action_discount, already invested blind
```

Postflop examples:

```text
HU: IP/OOP mostly enough
multiway: relative action order + players left to act
```

### Verification

Fit/distill from existing per-position tables and measure:

```text
open frequency by position
defend frequency by position
action KL divergence
EV loss
```

A successful factorized model should reproduce the table with far fewer parameters.

### Accuracy cost

Low to medium.

Some position-specific quirks remain, especially blind-vs-blind and BTN dynamics. Add small residual corrections only where needed.

### Verdict

**GOLD for conceptual simplification.**

---

# 11. Counterfactual-value compression, but not full Deep-CFR

### Name

**Small CFV regressor / value cache**

### CS/math/ML idea

Approximate continuation value as a function of compressed state features. This is value-function approximation, but you should use it as a cache/distillation tool, not as a whole new learning system.

### Replaces/compresses

Replaces:

```text
large solver cache lookups
some expensive subgame solving / tree reasoning
```

with:

```text
V(features)
```

### Complexity / compute reduction

```text
subgame/tree/cache lookup -> small regression call
```

### Fits your engine

Train on TexasSolver cached states:

```python
X = [
    equity,
    pot_odds,
    spr,
    position_ip,
    board_texture,
    range_nut_advantage,
    hero_bucket,
    villain_bucket_histogram,
]
y = solver_CFV_or_action_EV
```

Use:

```text
ridge regression
small gradient boosted trees
GAM
tiny MLP only if necessary
```

Avoid full Deep-CFR unless you have a clear evaluation harness.

### Verification

Holdout by board class, not random state only.

Track:

```text
CFV MAE
decision EV regret
generalization to unseen flops/turns
```

### Accuracy cost

Medium.

Value nets can hallucinate off-distribution. Keep them bounded and fallback to cache/exact rules.

### Verdict

**Nice-to-have. Do not make this the next big project before equity amortization.**

---

# 12. Board texture grammar for rules

### Name

**Finite board-texture automaton**

### CS/math/ML idea

Turn raw cards into a small symbolic state: pairedness, monotone/two-tone/rainbow, straight connectivity, high-card class, draw completion.

This is a handcrafted sufficient-statistic approximation for rule logic.

### Replaces/compresses

Replaces:

```text
large stat-keyed rule set with many board-specific cases
```

with:

```text
small board descriptor
```

Example:

```python
BoardTexture(
    paired=False,
    trips=False,
    monotone=False,
    two_tone=True,
    flush_completed=False,
    straight_possible=True,
    straight_draw_dense=True,
    broadway_heavy=True,
    low_connected=False,
    ace_high=True,
)
```

### Complexity / compute reduction

```text
22,100 raw flops -> maybe 30–100 texture types
```

### Fits your engine

Use this to gate:

```text
c-bet sizing
bluff permission
foldcatch nudge
overbet permission
multiway caution
```

### Verification

For each texture bucket:

```text
solver average bet frequency
solver average size
your bot frequency/size
EV deviation
```

### Accuracy cost

Medium.

Texture alone is insufficient; pair with equity/nut advantage.

### Verdict

**Good. Especially for simplifying exploit overlay.**

---

# Correctness / conceptual issues in the current approach

## 1. Per-decision MC equity is the wrong runtime architecture

120–1500 sims is noisy near thresholds. You may be making fold/call/bet decisions on sampling noise.

Better:

```text
exact river/turn
cached/canonicalized flop
deterministic fallback samples
```

## 2. MDF is not a general decision rule

MDF is valid mainly as a heads-up equilibrium defense concept against polarized betting. It is not automatically correct:

```text
multiway
against non-polar ranges
against population exploits
with rake
with range asymmetry
with equity realization differences
```

Use MDF as a sanity bound, not as a primary postflop rule.

## 3. “Fold-equity-optimal sizing” can be conceptually wrong

You should maximize EV, not fold equity.

A size with higher fold equity can be worse if:

```text
it risks too much
gets called by stronger range
folds out worse hands
destroys value
causes bad range construction
```

Simplified EV sizing is okay:

```python
EV(size) =
    p_fold(size) * pot
    + p_call(size) * (equity_when_called * final_pot - cost)
```

But optimizing fold equity alone is dangerous.

## 4. Hand-class percentile ranges are too crude postflop

`top x%` preflop-style ranges do not represent postflop action well.

Postflop ranges are shaped by:

```text
board interaction
draws
blockers
slowplays
polarization
cappedness
```

Simpler fix:

```text
range = histogram over strength/draw/nut buckets
```

rather than only `top percentile`.

## 5. Independent 6-max seat decisions are not coherent poker

If each seat decides from its own cards without coupled range/deck/opponent modeling, you lose:

```text
card removal
blockers
action-conditioning
multiway pressure
positional interaction
```

You do not need a full joint model, but you need at least:

```text
shared deck state
position-conditioned population ranges
aggregate opponent pressure
active_count
relative position
```

## 6. HU TexasSolver caches are not true 6-max ground truth

TexasSolver postflop caches are likely heads-up or simplified subgames. They are useful after a pot becomes HU, but multiway pots have different incentives:

```text
less bluffing
stronger continuing ranges
more checking
nut advantage matters more
equity realization lower
```

Do not blindly apply HU solver outputs to 3–6 way pots.

## 7. “88.6% action accuracy” may not mean much

Action accuracy can be misleading because solver mixes and many actions are near-indifferent.

Better metrics:

```text
EV loss
regret
KL divergence to solver strategy
threshold flip rate
performance in rollouts
```

## 8. Deep-CFR / Supremus CFVnet plan is likely complexity creep

It may improve the bot eventually, but it does not simplify your current system.

Before doing that, exhaust:

```text
equity cache
canonicalization
range bitsets
low-rank strategy distillation
simple CFV regression
```

---

# Recommended implementation order

## Phase 1 — kill MC runtime

Implement:

```text
range masks
blocker masks
suit canonicalization
river exact
turn exact/cache
flop canonical equity cache
```

Expected result:

```text
main runtime bottleneck mostly disappears
decisions become deterministic
debugging becomes easier
```

## Phase 2 — compress postflop state

Implement:

```text
board texture descriptor
hand bucket ID
range bucket histogram
nut/draw/air density summaries
```

Use these for:

```text
exploit overlay
sizing
multiway caution
```

## Phase 3 — fix 6-max conceptually without explosion

Implement:

```text
population ranges by position
active_count
relative position
mean-field fold/call aggregation
survival approximation for multiway equity
```

This gives you a coherent 6-max approximation without full joint solving.

## Phase 4 — distill strategy compactly

Replace large lookup/rule complexity with:

```text
few-feature threshold models
low-rank tables
GAM/logistic models
small value regressors
```

Only after that consider neural CFR machinery.

---

# Final ranking

| Rank | Idea | Gold? | Effort | Simplification |
|---:|---|---|---:|---:|
| 1 | Canonicalized equity cache | **GOLD** | Medium | Very high |
| 2 | Bitset/vector range algebra | **GOLD** | Low | High |
| 3 | River/turn exact enumeration | **GOLD** | Low-medium | High |
| 4 | Suit isomorphism | **GOLD** | Medium | High |
| 5 | Position as features | **GOLD** | Low-medium | High |
| 6 | Mean-field 6-max model | **GOLD-ish** | Medium | Very high conceptually |
| 7 | Equity/range buckets | Very good | Medium | High |
| 8 | Board texture grammar | Good | Low | Medium |
| 9 | Low-rank/GAM strategy distillation | Very good | Medium | High |
| 10 | Small CFV regressor | Nice-to-have | Medium-high | Medium |
| 11 | Full Deep-CFR / CFVnet | Not for simplification | High | Low/negative initially |
| 12 | Exact multiplayer Nash / large multiway CFR | Avoid | Very high | Negative |

The central simplifying move is:

```text
Stop thinking per decision.
Think per canonical state, per range bucket, per population summary.
Compute once, reuse forever.
```
