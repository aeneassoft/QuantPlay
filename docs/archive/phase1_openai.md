# Phase 1 integration consult — OpenAI gpt-5.1

Q1. Wiring the 62 exploit rules into the existing nudge channel
---------------------------------------------------------------

### 1.1 Data flow: from live stats → rules → `directive_to_nudge`

**Goal:** no new subsystem; rules just become another way to generate the *same* `{adjust, freq_delta, confidence}` directive object that already goes through `directive_to_nudge`.

**Existing pieces:**

- Live stats: `vpip, pfr, fold_to_bet, aggression_freq, confidence(n)`
- Nudge channel: `directive_to_nudge(directive)` → nudges `bluff / value / foldcatch` with clamped `freq_delta ∈ [-0.3,0.3]`
- Current cold-start: 11,520 Haiku + 240 Opus directives, looked up by `(vpip, fold_to_cbet, af)` profile, faded by `(1 - live_confidence)`

**New piece we’re allowed to use:** `unified.json` with 62 rules.

---

### 1.2 Step 1 – Rule triggering from live stats

Add a very small dispatcher, not a new system:

```python
def rules_for_opponent(opp_model, street, spot_tags):
    """
    opp_model: has .vpip, .pfr, .fold_to_bet, .aggression_freq, .confidence
    street: 'preflop'/'flop'/'turn'/'river'
    spot_tags: small set of booleans/labels we already have (e.g., 'facing_raise', 'ip_aggressor', 'river_bet_facing')
    """
    active_rules = []
    for rule in unified_rules:
        if not stat_available(rule.stat, opp_model):
            continue
        if not condition_holds(rule, opp_model):
            continue
        if not spot_matches(rule.spot, street, spot_tags):
            continue
        active_rules.append(rule)
    return active_rules
```

**Key simplification constraints:**

- **Only use stats we already measure live**: `vpip, pfr, fold_to_bet, aggression_freq`.  
  Rules depending on `call_down_freq, river_bet_freq, fold_to_cbet, fold_to_3bet, threebet_pct, wtsd, limp_freq` are *ignored for now* (hard-gated, not approximated). That avoids inventing phantom stats.

- **Spot matching is coarse and reuses existing info**:  
  Map a few obvious ones:
  - `"preflop BTN/CO/SB steal vs tight blinds"` → `street='preflop' and hero_position in {BTN,CO,SB} and spot_tags['vs_blinds']`
  - `"flop as aggressor c-betting into checker"` → `street='flop' and spot_tags['hero_last_raiser'] and spot_tags['villain_checked_to_hero']`
  - `"turn second barrel after flop call"` → `street='turn' and spot_tags['hero_last_raiser'] and spot_tags['villain_called_flop']`

  Don’t build a giant spot ontology. Implement the 10–15 most obviously mappable spots now; everything else just never fires. That’s fine for Phase 1.

---

### 1.3 Step 2 – Mapping rule `delta` to our three channels

Your nudge space is **only about action *frequencies***:

- `bluff` ≈ how often we choose bluffing lines
- `value` ≈ how often we choose value-bet lines
- `foldcatch` ≈ how often we choose call/hero-call vs fold

We force every rule `delta` into that 3D space:

| Rule `delta`      | Interpretation in our engine         | Channel + sign                           |
|-------------------|--------------------------------------|------------------------------------------|
| `more_bluffs`     | Bluff with higher frequency          | `bluff` +                                 |
| `fewer_bluffs`    | Bluff less                           | `bluff` −                                 |
| `more_value_bets` | Value-bet more often                 | `value` +                                 |
| `thinner_value`   | Value-bet thinner (more combos)      | `value` + (stronger magnitude)           |
| `fold_more`       | Fold more bluffcatchers/marginals    | `foldcatch` −                             |
| `call_wider`      | Call more bluffcatchers              | `foldcatch` +                             |
| `raise_more`      | Take aggressive line more often      | `bluff` + (because in your map raises=bluffs) |
| `check_more`      | Check-back/control more              | `value` − and `bluff` − (less betting)   |
| `overbet`         | Proxy: more polarized betting        | `bluff` + and `value` + (see below)      |
| `smaller_bet`     | Proxy: more medium / merged bets     | `bluff` − and `value` − (see below)      |

**Important:** This is *not* perfect semantics, but it keeps everything inside the existing 3-channel nudge system, which is your constraint.

Implementation sketch:

```python
DELTA_TO_CHANNEL = {
  'more_bluffs':      {'bluff': +1.0},
  'fewer_bluffs':     {'bluff': -1.0},
  'more_value_bets':  {'value': +1.0},
  'thinner_value':    {'value': +1.5},
  'fold_more':        {'foldcatch': -1.0},
  'call_wider':       {'foldcatch': +1.0},
  'raise_more':       {'bluff': +1.0},
  'check_more':       {'bluff': -0.7, 'value': -0.7},
  'overbet':          {'bluff': +0.7, 'value': +0.7},
  'smaller_bet':      {'bluff': -0.7, 'value': -0.7},
}
```

Those coefficients are just *relative* weights; they’ll be scaled by rule magnitude and clamped by your existing `freq_delta` caps, so they can be tuned by solver/TV-gap later.

---

### 1.4 Step 3 – Magnitude + confidence → `freq_delta`

Use the existing clamp of 0.3 as the outer bound, and convert rule `magnitude` & `confidence` into a scalar:

```python
MAGNITUDE_BASE = {
  'small':  0.10,
  'medium': 0.20,
  'large':  0.30,
}
```

For each active rule:

```python
def rule_to_directive(rule):
    # stat-confidence from opp_model, but we can also use rule.confidence
    base = MAGNITUDE_BASE[rule.magnitude]
    # multiply by rule.confidence so low-confidence rules are naturally weaker
    freq_delta = base * rule.confidence              # in [0, 0.30*0.9] ~ [0,0.27]
    # For each channel impacted:
    channel_weights = DELTA_TO_CHANNEL[rule.delta]   # e.g. {'bluff': +1.0, 'value': +0.7}
    directive = []
    for ch, sign in channel_weights.items():
        directive.append({
           'adjust': ch,      # we’ll map this to your internal action->channel mapping
           'freq_delta': sign * freq_delta,
           'confidence': rule.confidence,
        })
    return directive
```

You then combine **all rule-derived directives** for the state into one aggregate directive per channel:

```python
agg = {'bluff': 0.0, 'value': 0.0, 'foldcatch': 0.0}
tot_conf = {'bluff': 0.0, 'value': 0.0, 'foldcatch': 0.0}

for rule in active_rules:
    for d in rule_to_directive(rule):
        ch = channel_from_delta(rule.delta)  # or directly d['adjust'] if aligned
        agg[ch] += d['freq_delta']
        tot_conf[ch] += rule.confidence

# Optional shrink toward 0 if conflicting rules fire
for ch in agg:
    if tot_conf[ch] > 0:
        agg[ch] = clamp(agg[ch], -0.3, 0.3)  # respect existing global cap

rules_directive = {
  'adjust': 'composite',
  'freq_delta': agg,   # now a 3-vector
  'confidence': opp_model.confidence,  # or function of #hands
}
```

You can then pass `rules_directive` into `directive_to_nudge` by slightly generalizing it to accept a structure with per-channel freq_deltas instead of a single scalar, or by emitting **three** directives per decision (`bluff`, `value`, `foldcatch`) and letting existing mapping process them one by one.

---

### 1.5 Step 4 – Handling sizing deltas (a), and missing stats (b)

**(a) Sizing deltas (`check_more`, `overbet`, `smaller_bet`)**

You don’t have a separate sizing control path, and you’re not allowed to add one. So:

- **Interpret them as shifts in betting vs checking frequencies**:
  - `check_more`: use negative nudges on both `bluff` and `value` → more checks/pass
  - `overbet`: use positive nudges on both `bluff` and `value` → we pick the “aggressive” bet line more often within existing size abstractions
  - `smaller_bet`: negative nudges on both `bluff` and `value` → we favor more medium-passive lines over high-polarized ones

No new bet-size system, just reshaping the frequencies of whatever bet sizes your policy already supports.

**(b) Rules with stats we don’t track yet**

Do **not** synthesize pseudo-stats or guess from others. For Phase 1:

```python
def stat_available(stat, opp_model):
    return stat in ['vpip','pfr','fold_to_bet','aggression_freq']
```

So roughly half the rules are “off” until you choose to add those stats later. That’s exactly what “no new subsystems” looks like: we don’t pretend to have what we don’t measure.

---

### 1.6 Do the 62 rules replace the Haiku/Opus playbook?

For a Phase‑1 *simplification*, yes, and you should be ruthless here.

The existing cold-start is:

- 11,520 Haiku + 240 Opus directives via nearest-profile on `(vpip, fold_to_cbet, af)`, only when `confidence < 0.6`, faded by `(1 - live_confidence)`.

Problems:

- It’s opaque and hard to calibrate.
- It relies on stats (`fold_to_cbet`) you’re not currently measuring in the live model.
- It’s massive; tuning 11k directives is essentially impossible; you’ll never LBR them properly.

**Recommendation:**

1. **Phase 1: Run an A/B experiment where the playbook is completely disabled as a cold-start.**  
   - A: current system (playbook + live model nudges)
   - B: same but with playbook removed, leaving existing exploiter + GTO floor only

2. **Phase 2:** If you want a cold-start source, **replace** the playbook with the 62 rules (and only for the subset whose stats are available), wired exactly as above. The rules are stat-keyed and human-auditable.

So yes, rules should *replace* the playbook as a cold-start *once* they are proven not-worse. Until then, they run **alongside** the rest of the exploit channel with small caps.

---

### 1.7 Exact decision-time data flow

At each decision in `AdaptiveExploiter.decide`:

1. **Base floor policy** from GTO components:
   - Preflop: GTO table (6-max) or simple HU preflop default
   - Postflop: `gto_baseline.py`/`postflop.py` (whatever is currently wired)

2. **Live model readout**: `opp_model = opponent_tracker.get_model(villain_id)` with `confidence = f(#hands)`

3. **Derive exploit nudges:**

   - If `live_directive` (LLM) exists: keep current behavior (full weight).
   - Else:
     - Get **rule-based directive**: `rules_directive = rules_for_state(opp_model, street, spot_tags)`
     - (Optionally) keep current static playbook directive (until A/B shows it can be dropped).
     - Combine:
       ```python
       combined_nudge = zero_vector()  # bluff/value/foldcatch
       if rules_directive is not None:
           combined_nudge += rules_directive.freq_delta * opp_model.confidence
       if playbook_directive is not None:
           combined_nudge += playbook_directive.freq_delta * (1 - opp_model.confidence)
       # If live_directive exists, decide whether it overrides or adds; for now: override.
       if live_directive is not None:
           combined_nudge = live_directive.freq_delta
       combined_nudge = clamp_each(combined_nudge, -0.3, 0.3)
       ```
4. **Apply via existing channel**: call `directive_to_nudge(combined_directive)` and adjust action probabilities from the floor accordingly.

---

### 1.8 Grounded gate to keep this change

You keep rule-based integration *only if* it passes a **duplicate-poker A/B** against the current exploiter, with confirmatory LBR:

- **Setup:**
  - Two bots A and B play the same pool of opponents (or recorded hand histories) in duplicate format (same cards/positions).
  - A = current exploit system (playbook cold-start, no 62 rules)
  - B = same but with rules wired as above; either:
    - B1: playbook kept; rules capped at, say, ±0.15.
    - B2 (second phase): playbook removed; rules only.

- **Metrics:**
  - Primary: average **bb/100** vs exploitable field across ≥ 100k duplicate hands.
  - Secondary: **LBR exploitability** of A vs B using a simple look-ahead best-response bot (on smaller abstracted game tree if needed).

- **Gate condition:**
  - For B1: require **no statistically significant drop** in bb/100 vs field AND no increase in LBR exploitability by more than X% (e.g., 5%).
  - For B2 (rules replacing playbook): require *non-inferiority* vs A in bb/100 within confidence interval and equal or better LBR exploitability.

If it fails either metric, you revert to the old exploiter and revisit mapping constants (`DELTA_TO_CHANNEL`, magnitude mapping).

---

Q2. Integration gaps and minimal fixes (ranked by EV)
-----------------------------------------------------

### 2.1 Gap 1: GTO floor pieces are inconsistent / partially wired

**Symptoms:**

- HU bot uses `postflop.py` (equity thresholds) that may not match `gto_baseline.py` solver-calibrated textures.
- 6-max preflop GTO table is not used by HU; HU preflop probably ad-hoc.
- The 62-rule DB is not wired (we’re fixing that in Q1).

**Why high EV:** your exploit layer is a perturbation around the floor. If the floor is inconsistent, all calibrations (bluff:value ratios, foldcatch thresholds) are drifted. You get fragile exploitation that breaks vs stronger opponents.

**Minimal fix: make a single baseline policy object and force everything to use it.**

1. Define `BaselinePolicy`:
   ```python
   class BaselinePolicy:
       def __init__(self, preflop_table_6max, preflop_table_hu, postflop_solver):
           ...

       def get_action_distribution(self, state):
           if state.street == 'preflop':
               if state.num_players == 2:
                   return self._hu_preflop_policy(state)
               else:
                   return self._6max_preflop_policy(state)
           else:
               return self._postflop_policy(state)
   ```

2. Wire:
   - HU preflop to use HU GTO table; if missing, approximate by 6-max positions mapped to HU (e.g., BTN ≈ SB HU).
   - 6-max already uses its table.
   - Postflop: **choose one**: either `gto_baseline.py` or `postflop.py`, and **delete** the other for Phase 1, or make one a strict wrapper of the other (no divergence).

3. Ensure `AdaptiveExploiter.decide` *always* calls `BaselinePolicy.get_action_distribution` first, then applies nudges.

**Verification gate:**

- **Solver TV-gap / exploitability test** on a small set of canonical spots:
  - Pick ~20 boards and situations (BTN vs BB c-bet/call, 3-bet pot, etc.).
  - For each, compute:
    - `π_baseline` (current hacked wiring)
    - `π_unified` (new BaselinePolicy)
    - `π_solver` (offline solver from `gto_baseline.py`)
  - Compute **total variation distance** `TV(π_unified, π_solver)` and `TV(π_baseline, π_solver)`.

- **Gate:** keep the unified floor only if `mean TV(π_unified, π_solver) ≤ mean TV(π_baseline, π_solver)` and ideally improves by a clear margin. For HU, run a small **LBR** agent vs both floors and demand equal or *lower* exploitability with the unified floor.

---

### 2.2 Gap 2: Exploit layer uses stats differently than rules / playbooks

- Live model tracks `vpip, pfr, fold_to_bet, aggression_freq`.
- Old playbooks index on `(vpip, fold_to_cbet, af)` where `fold_to_cbet` isn’t currently measured live.
- 62 rules contain multiple stats not in the live model.

This creates diverging notions of “NIT”, “station”, etc.

**Minimal fix: single authoritative stat schema.**

- **Authoritative live stats** (Phase 1): `vpip, pfr, fold_to_bet, aggression_freq, hands_seen`.
- Any subsystem referencing anything else (playbook `fold_to_cbet`, rules needing `river_bet_freq`, etc.) **must either:**
  - be hard-disabled for now; or
  - get its own minimal estimator wired into opponent model (if you *choose* to add that later).

For Phase 1, pick option 1 to simplify.

**Verification gate:**

- **Held-out metric**: build a labeled synthetic test-set of profiles with given stats and run both:
  - current exploit decision logic
  - new consolidated-stat exploit logic
- For each profile, run a simple toy solver (or simple EV calculation) on a few canonical spots where the exploitation direction is known (e.g., vpip=0.7 & fold_to_bet=0.2 → value-heavy).
- **Gate:** require that the new logic’s decisions are at least as consistent with solver-suggested exploit directions as the old logic (≥ same agreement rate). This is cheap but sanity-preserving.

---

### 2.3 Gap 3: Static playbook is oversized and uncalibrated

- 11,520+240 directives, almost impossible to maintain or validate.
- It uses stats that are not live, and is faded with an arbitrary function of `live_confidence`.

**Minimal fix: shrink and/or delete.**

You have three near-term options, ranked by simplicity:

1. **Full deletion for live play** (my recommendation after A/B):
   - Remove playbook from the cold-start path.
   - Use:
     - Floor-only when `opp_model.confidence` below threshold.
     - Floor+62-rules when `confidence` high enough.

2. **Keep but cap**:
   - Hard-cap playbook freq_deltas at ±0.1.
   - Decrease weight with #hands much faster than now.

The highest EV *and* simplicity is **eventual deletion**, but do it with a gated experiment.

**Verification gate:** already covered under Q1: duplicate-poker A/B vs field; gate on **bb/100** and **LBR exploitability**.

---

### 2.4 Gap 4: HU preflop floor not using the existing GTO table

- 6-max GTO preflop table exists and is wired.
- HU bot doesn’t use it; preflop behavior may be wildly ad-hoc against strong players.

**Minimal fix: map HU positions into 6-max preflop table**

- HU BTN → 6-max BTN opening ranges.
- HU BB vs BTN open → 6-max BB vs BTN scenario (or SB vs BTN, depending on table semantics).
- Use simple position remapping until you have a dedicated HU preflop table.

**Verification gate:**

- **LBR vs HU floor** on a simplified HU game:
  - Run an LBR agent on a preflop+flop abstraction (e.g., 2-sizings tree).
  - Measure exploitability of:
    - old HU preflop
    - mapped HU-using-6max
- Gate: mapped version must be ≤ exploitability of old version; ideally strictly lower.

---

### 2.5 Which single fix most improves the floor “running perfectly”?

If I had to implement **one** fix this week:

> **Unify the floor into a single `BaselinePolicy` and delete/disable the redundant postflop logic paths.**

Reason:

- Every exploit and rule nudge is relative to that base. If the base is inconsistent (different for HU vs 6-max, or solver-calibrated here vs heuristic there), you get non-local effects when tuning exploit.
- It’s small, concrete, and testable with TV-gap and LBR on a small battery of spots.
- Once the floor is coherent, wiring the 62 rules (Q1) becomes much safer.

---

Q3. Self-play → improved history-free floor
-------------------------------------------

### 3.1 Is the logic sound?

Your framing (C2):

> “Exploitative play needs opponent history. If we build a loop where recursive exploitative play converges to GTO (self-play), couldn't that ALSO improve our pure GTO part?”

Yes, under normal game-theory conditions:

- Repeated self-play where each agent best-responds to the average of past policies is precisely **fictitious play**, which converges to a **Nash equilibrium** in 2p zero-sum games in the limit (for many games).
- Algorithms like **NFSP**, **Deep CFR**, and variants are scalable approximations that learn:
  - an average policy (approx-GTO floor)
  - a best-response policy (exploit head)

So logically: **if** you point your exploit machinery at **your own policy** in a self-play loop and update the floor toward the average over time, you *can* improve the floor toward GTO.

The constraints in your case:

- You already have partially-solved GTO caches (gto_baseline, preflop table).
- You must not add new architectural complexity, just upgrade parameters.

So we want the **minimal** self-play update that:

- Uses your existing policy representation (whatever function approximator or table you already use).
- Uses your existing solver caches as warm-start.
- Trains only limited parts (e.g., adjust bet frequencies on key textures).

---

### 3.2 Minimal algorithm sketch: tabular / small-network fictitious play

For Phase 1, full Deep CFR / NFSP is overkill. You can:

1. **Restrict to a small toy abstraction** first (e.g., Leduc or a small No-Limit subgame class):
   - Limited bet sizes (2-3 sizes).
   - Simplified board textures (bucketed).
   - That’s where you *prove* your loop works and converges.

2. **Algorithm (minimal fictitious play variant):**

   - Representation:
     - Let `πθ` be your current floor policy, parameterized by θ (e.g., logit weights per state-action).
   - Loop:
     1. Initialize `πθ` using your existing GTO caches (preflop table, postflop solver lookups).
     2. For iteration `k = 1..K`:
        - **Best-Response Step:** Compute an approximate best response `BR_k` to `πθ_k`:
          - Use a simple search/solver (the same as your gto_baseline code but with one side fixed to `πθ_k`) to maximize EV for the opponent against πθ_k.
        - **Average Policy Update:**
          - Maintain an **average policy** `π̄` over past iterates (or directly over `BR_k` and πθ_k).
          - Update θ toward the **regret-minimizing mix**:
            - In simple tabular form, set new θ_i proportional to log of action frequencies that appear often in higher-value branches of BR_k (CFR-style regret update).
     3. After K iterations, set your **floor** to `π̄`.

   This is essentially **tabular CFR / fictitious play** on your abstraction.

3. **How it fits your floor:**

   - Preflop:
     - You already have a table. You can treat it as initial `πθ_0` and then only allow **small deviations** discovered by best-response loops on the abstract preflop+flop game.
   - Postflop:
     - gto_baseline outputs approximate GTO strategies for certain classes of boards.
     - Use self-play only where you *don’t* have solver output, or to refine those outputs in your specific abstraction (e.g., limit bet sizes to the ones your engine actually uses).
   - Output of this procedure is just new **action-frequency tables or logit weights**, which can replace the current ones in `BaselinePolicy`.

We’re not adding a neural net unless you already have one; if you do, the update is just adjusting its output distribution on the training set of states.

---

### 3.3 Compute requirements (RunPod etc.)

On a **small game** like Leduc (or tiny no-limit abstraction):

- You can run CFR / fictitious play on CPU in hours, not days.
- If you insist on a neural-network representation (NFSP/Deep CFR):
  - A single modest GPU (A10 or T4 on RunPod) for ~8–24h is plenty for small games.

For **full no-limit**, I would *not* recommend full-blown Deep CFR given your current constraints. Limit the experiment to:

- Key decision classes (e.g., flop c-bet spots in single-raised pots).
- Use existing solver caches to generate initial policies and best-responses cheaply, so training is basically “calibration” / distillation, not from scratch.

---

### 3.4 Verification of convergence/improvement

**Step 1: Leduc testbed**

- Implement a Leduc Poker environment.
- Run fictitious play / CFR:
  - Initialize random-ish.
  - Run K iterations (e.g., 10k).
- Eval:
  - Compute exploitability using:
    - Either exact best response (Leduc small enough for enumeration)
    - Or a search-based approximate BR.
- **Gate for Leduc**: exploitability must monotonically decrease (or at least trend downward) and reach a known benchmark (comparable to published CFR results).

**Step 2: Small no-limit abstraction**

- Take a tiny subset of your real game tree (e.g., BTN vs BB single-raised pot, 2 bet sizes).
- Run the same scheme:
  - Use your own solver (gto_baseline) as a reference for the first iteration.
  - Run about K=100–500 updates of best-response + policy update.

- Eval:
  - Compare exploitability of:
    - Old floor policy (before self-play refinement).
    - New floor policy `π̄` after self-play.
  - Use **Limited Best Response (LBR)** to approximate exploitability for this subgame.
  - Also check TV-distance between π̄ and the original solver output; large deviations that don’t decrease exploitability are suspect.

**Step 3: Integration to the main bot**

- Only after the small-game experiments demonstrate **reduction in exploitability** do you even consider applying self-play-trained updates to the main floor.

---

### 3.5 Minimal “correct” algorithm by name

Given your constraints, the minimal correct options:

- **For toy games / learning sanity:** “Tabular CFR / tabular fictitious play”
- **For a slightly larger abstraction with your current representation:** “Regret-matching update on existing policy tables using approximate best responses from current solver”

I would **not** deploy full NFSP or Deep CFR in Phase 1. That’s too much scaffolding for your stated goal.

---

Q4. One grounded gate per question
-----------------------------------

Summarizing the single coercive gate for each change:

**Q1 – Wiring the 62 rules into the exploit channel**

> **Gate:** Duplicate-poker A/B + LBR  
> 
> - A: current exploiter (playbook, no 62 rules)  
> - B: exploiter + 62-rule integration (with playbook still on, then in second phase without playbook)  
> 
> Keep the 62-rule integration only if:
> - B’s bb/100 vs exploitable field is **not worse** than A, within statistical error; and  
> - LBR exploitability of B is **no higher** than A (within a tolerance, e.g., ≤ +5%).

If either metric degrades, revert the integration and re-tune the mapping / magnitudes.

---

**Q2 – Making the engine run smoothly (floor unification, etc.)**

> **Gate for unifying the floor (`BaselinePolicy`):** Solver TV-gap + small-game LBR  
> 
> On a curated set of 20–50 canonical spots:
> - Compare `TV(π_unified, π_solver)` vs `TV(π_old, π_solver)`. Require that unified floor’s TV-gap is **no larger** and preferably smaller.  
> 
> On a small HU/6-max abstraction:
> - Use LBR to estimate exploitability of old vs unified floor. Keep unified floor only if exploitability is **not worse**.

---

**Q3 – Self-play loop to improve the history-free floor**

> **Gate:** Toy-game exploitability reduction (Leduc or small no-limit abstraction)  
> 
> Implement your self-play / fictitious play algorithm in a toy game:
> - Start from some initial π.  
> - Run self-play until convergence (CFR / fictitious play iterations).  
> - Measure exploitability via exact or approximate BR.  
> 
> Only if exploitability **monotonically decreases** and reaches a low, stable level do you allow this procedure to update any part of the live floor. No update to the main engine until this is passed.

---

If you want a “do this this week” ordering:

1. **Unify the floor** (`BaselinePolicy`) and validate via TV-gap/LBR.  
2. **Wire in 62 rules** as described, initially with low caps; run duplicate A/B + LBR.  
3. Only once 1 & 2 are stable, start the **Leduc/self-play experiment** as a separate research branch to prove to yourself that self-play actually converges before touching the live engine.
