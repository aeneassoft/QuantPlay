# Simplification vet + integration — Claude claude-opus-4-8

# Brutal Vet of the GPT-5.5 Proposal

Short version: the proposal is **mostly correct and unusually un-hyped for a frontier model**. It correctly identifies that your real enemy is per-decision MC, and that the answer is amortization + symmetry + abstraction, not more ML. But it has **three concrete errors/overclaims** I'll flag, and it **buries the single highest-ROI item under a medium-effort one**. Let me re-sort by *actual* simplification-per-effort for YOUR engine.

---

## The verdict on each item, regrouped

### TIER A — REAL GOLD, do these (smallest-first)

**A1. River exact enumeration (their #2, partial)**
- **Real.** River has *zero* remaining cards. MC on the river is indefensible — you're sampling when you could just iterate villain combos. This is `O(villain_combos)` ≈ a few hundred evals, *cheaper and exact* vs 120-1500 noisy sims.
- **Integration:** add `equity_river_exact(hero, board5, villain_mask)` next to `equity_vs_range`. Route river calls there. ~30 lines.
- **Verify:** for 1000 random river spots, `|exact - MC_100k| < 0.005`; assert exact has zero variance across reruns.
- **Effort: tiny. This is your true #1.** GPT ranked it #3.

**A2. Bitset/vector range algebra (their #3)**
- **Real and boring-good.** Your `range_top` + per-combo Python loops are pure overhead. Precompute `combo_to_cards[1326,2]`, `combo_class[1326]`, `range_masks[range_id]` once. Blocker removal becomes one `&`.
- **Integration:** new `range_algebra.py`; refactor `equity_vs_range` / `equity_vs_class_range` to consume a mask+weights instead of rebuilding combos. **This also makes A1/A4 trivial** — they all need the same mask representation. Do this *with* A1.
- **Verify:** old combo-list == new mask-derived combo-list for every range_id and 1000 random blocker sets. Exact equality, no tolerance.
- **Accuracy cost: none.** **Effort: low.**

**A3. Suit isomorphism canonicalization (their #4)**
- **Real, but only worth it as the *key function* for caching.** By itself it does nothing; it's the hash that makes A4 small enough.
- **Integration:** `canonicalize(board, hero)` via brute min over 24 suit perms (cheap vs one MC). Returns canonical key + suit_map.
- **Verify:** `equity(state) == equity(any_suit_perm(state))`; `canon(state)==canon(perm(state))`.
- **Effort: medium.** Do it *only as the prerequisite for the cache*, not standalone.

**A4. Canonicalized equity cache (their #1)**
- **Real, and the biggest steady-state win — but it depends on A1-A3.** GPT ranked it #1 by total value; correct on value, wrong on order. You cannot build it cleanly without masks (A2) and a canonical key (A3). Turn/flop are where caching pays (river you just enumerate live).
- **Integration:** disk-backed numpy/SQLite keyed by `(street, canon_board, canon_hero, range_id)`. Miss → exact enumerate (turn) or quasi-MC (flop) → store.
- **Verify:** cache hit == recomputed exact; track hit-rate in live play (this is the real ROI metric).
- **Accuracy cost:** only from your *existing* range discretization. **Effort: medium.**

**One correction to GPT's framing on A4:** it claims flop exact is "pay once." In 6-max your villain range varies by position *and* action history, so `range_id` cardinality is larger than it implies. Keep `range_id` to a SMALL fixed set (e.g. 6-10 percentile bands) or your cache won't hit. This is a real design trap.

---

### TIER B — Good, but DEFER (they serve strategy quality, not compute reduction)

**B1. Position as low-dimensional features (their #10)**
- **Real and right conceptually**, BUT: be honest — this is *strategy refactor*, not compute reduction. Your per-position tables are already cheap O(1) lookups. Replacing 6 tables with 1 feature-model **doesn't reduce runtime compute meaningfully**; it reduces *parameter/maintenance complexity*. Worth doing eventually, low ROI on the stated goal (cut calculation).

**B2. Board texture grammar (their #12)** — same: simplifies the *rule set*, not the hot path. Cheap, modest value.

**B3. Equity-distribution buckets (their #5)** and **B4. Range moments (their #6)** — useful for the exploit overlay, but **do NOT let them replace your equity source.** GPT correctly warns this. Risk: you'll trade an accurate-but-slow number for a fast-but-lossy one *when you've already solved speed via A1-A4*. So buckets become **redundant for equity** once caching exists. Keep them only as overlay features.

---

### TIER C — Real conceptually but the proposal OVERSELLS the simplicity

**C1. Mean-field / population 6-max (their #8) + survival approximation (their #9)**
- **This is the one place GPT's "GOLD" label is too generous.** The mean-field idea is correct (don't model 1326^5 jointly), but here's the brutal truth: **you don't currently model opponents jointly at all** — each seat decides independently from its own cards. So mean-field doesn't *simplify* anything you have; it **ADDS** an opponent-coupling layer you don't have today. That's complexity creep dressed as simplification.
- **The honest move:** the survival-product approximation (`P(win) ≈ Π P(beat_i)`) is a genuinely cheap multiway equity estimate IF you ever need multiway equity. But it requires *calibration curves by active_count/texture* — that's new infrastructure. **Net: this is a feature, not a simplification.** Defer unless multiway equity is actually wrong today.

**C2. Low-rank / GAM distillation (their #7)** — real, but again: your GTO table is already a fast lookup. Distilling it into 50-500 params reduces *storage*, not decision compute. Value is maintainability. Medium effort, medium-low ROI vs the stated goal.

**C3. Small CFV regressor (their #11)** — GPT correctly says "nice-to-have, not next." Agreed. Adds a training/eval harness = complexity.

---

### TIER D — Correctly flagged as NOT simplification

- **Deep-CFR / CFVnet (#11 full / your "planned floor upgrade"):** GPT is **right and brave to say this.** It adds training infra, distribution-shift risk, and debugging burden. It is a *strength* play, not a *simplification* play. Given your explicit goal, **shelve it.**
- **Exact multiway Nash (#12):** correctly says avoid.

---

## Correctness issues — which of GPT's flags are valid

| GPT's flag | My ruling |
|---|---|
| MC noisy near thresholds | **Valid, serious.** 120 sims → ~±4.5% std error on equity. You ARE flipping decisions on noise. |
| MDF not a general rule (multiway/rake/non-polar) | **Valid.** Use as bound, not primary. |
| "Fold-equity-optimal sizing" ⊂ EV-optimal | **Valid and important.** Maximize EV(size), not fold equity. Real bug risk. |
| Top-x% percentile ranges crude postflop | **Valid but lower priority** — fixing it adds the bucket machinery. Accept the crudeness for now. |
| Independent 6-max seats lose card removal/coupling | **Valid as a *strength* critique, but NOT a simplification target.** Fixing it adds complexity. Note it, don't chase it. |
| HU solver caches ≠ 6-max ground truth | **Valid and important.** Don't apply HU GTO blindly to 3+way pots. This is a *correctness* fix, costs ~nothing (just gate it on active_count). |
| 88.6% action accuracy misleading | **Valid.** Switch eval to EV-loss / threshold-flip rate. Cheap, do it. |

Two of these are free correctness wins worth folding in: **(a) gate HU solver outputs to HU pots**, **(b) change your eval metric to EV-loss/flip-rate.**

---

## The single highest-ROI simplification to do FIRST

**River exact enumeration, built on a minimal bitset range mask (A1 + the mask part of A2).**

Why this over GPT's #1 (the full cache):
- It's **tiny** (one function + one mask representation), needs no canonicalization, no disk store, no cache invalidation.
- It **eliminates MC entirely on the street where MC is most indefensible** (zero unknown cards → sampling is pure waste).
- It produces **exact, zero-variance, reproducible** numbers — instantly killing the "deciding on sampling noise" bug class on the river.
- It is the **foundation** every other Tier-A item reuses (turn enumeration, the cache, blocker algebra all consume the same mask).

**Concrete first commit:**
1. `range_algebra.py`: `combo_to_cards[1326,2]`, `combo_class[1326]`, `cards_to_blocker_mask()`, `range_to_mask(range_id)`.
2. `equity_river_exact(hero, board5, villain_mask)`: iterate unblocked villain combos, `treys` eval each, return win+½tie fraction.
3. Route street==river to it.
4. **Verify:** 1000 random rivers, `|exact − MC_100k| < 0.005`, variance==0 across reruns, and log decision-flip count vs old MC near pot-odds thresholds (this number is your proof of the noise bug).

Then expand mask → turn enumeration → canonicalize → flop cache, in that order.

**Do not** start the mean-field 6-max work, the buckets, or anything ML-flavored — those either add complexity or optimize storage you don't need optimized.
