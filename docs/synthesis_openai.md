# Synthesis consult — OpenAI gpt-5.1

Q1. ARCHITECTURE NOW (1–2 weeks, no new big net)

Target: a hybrid bot:

- Preflop: CFR/Nash-based ranges (you already have push/fold HU; extend to 100bb via static ranges).
- Postflop “floor”: a parametrized strategy engine that:
  - Uses your existing analytic baseline structure.
  - Replaces as many heuristics as possible with values calibrated to (A) PokerBench and (B) your solver caches (B), plus range templates from (D1).
- Exploit layer: your existing online opponent model + exploit engine (G) but:
  - Re-parameterized with empirical priors from (C) Pluribus + (E) exploit directives.
  - Confidence-gated more aggressively via AIVAT/duplicate poker.

No LLM in the online loop.

### 1.1 Concrete floor architecture (no LLM in play)

#### 1.1.1 Representation

Use a single shared feature representation for all postflop decisions (both HU and 6-max):

- Board features:
  - Board class: paired / monotone / 2-tone / rainbow / 3-suited.
  - High card, second high, third high (buckets: A,K,Q,J,T,9-7,6-4,3-2).
  - Connectivity: very wet / semi-wet / dry, defined by straight draws count.
- Pot/stack features:
  - SPR bucket: (0–1, 1–3, 3–6, 6+).
  - Pot size in bb (coarse buckets).
- Position/line features:
  - Nodes: preflop raiser or caller, OOP/IP, street, action history type (e.g. SRP IP cbet flop; SRP OOP x/c flop; 3bet pot IP).
  - Street: flop/turn/river.
- Hand class:
  - Made hand class: air / high card w/ blocker / weak pair / middle pair / top pair / overpair / 2p / set+.
  - Draw class: none / gutshot / OESD / flush draw / combo draw.
  - Nut rank: near-nuts / strong / medium / weak.
  - Again—bucket date: you don’t need precise equity here; coarse classes are enough.

You likely already have some of this in G; standardize it and ensure it is indexable.

#### 1.1.2 Floor = parametric policy tables

For each “node type” (e.g. SRP IP c-bet flop, SRP OOP x/c flop, turn probe vs missed cbet, river facing bet after x/x, etc.) define:

- Discrete sizing set: e.g. {check, 33%, 66%, 100%, overbet} for flop/turn; {check, 50%, 100%, 150%} for river.
- For each (node type, feature bucket, hand class):
  - Action set and frequencies.
  - Baseline bet sizes allowed.

These parameters will be stored as small tables / JSON / numpy arrays, not learned online. You can then:

- Lookup rule = f(node_type, feature_bucket, hand_class) → (allowed actions, recommended frequencies).
- Sampling: sample stochastically or deterministically (e.g. epsilon-randomization).

#### 1.1.3 How to fill & calibrate the parameters from A + B + D

1. **Initialize structure from book knowledge (D1 Acevedo + D2–D4):**
   - Extract generic patterns:
     - C-bet frequency & size by board class & range vs range (Acevedo).
     - Check-raise / barrel frequencies guidelines.
   - Convert these to initial heuristics: e.g.
     - In SRP IP vs BB, on high dry boards (Axx, Kxx): high small c-bet frequency.
     - On low connected boards (678, 456): more checking, polarizing bets when betting.
   - Store as prior frequencies (e.g. 70% c-bet small on A72r, 40% on T98ss, etc.).

2. **Override / calibrate with solver caches (B):**
   - Use your exact flop & turn solves to compute:
     - Average c-bet% per board class, role, and texture.
     - Average size distribution.
     - Typical x/r, x/c frequencies by hand class bucket.
   - Define mapping: solved board → your board feature bucket.
   - For each bucket:
     - Aggregate solver data (mean frequencies).
     - Fit simple param values: e.g. for (SRP IP, “high dry board”, SPR>3) set:
       - c-bet = 75% freq, 33% pot 90% of the time, 66% 10%.
   - For HU turn cache: calibrate barreling frequencies and probe frequencies.

   **Verification method**:  
   - Use a held-out subset of boards from your solve cache (B) not used in calibration.
   - For each node, simulate decisions using your parametrized policy vs exact solver strategy and compute:
     - Average action distribution KL divergence.
     - EV gap: plug in both strategies into TexasSolver (fixed ranges) and compute EV difference over those boards.
   - Gate: floor is acceptable if average EV gap per node is below X bb/100 (e.g. < -5bb/100 on those boards).

3. **Fill missing coverage using PokerBench (A):**
   - A is 6-max, solved GTO decisions at 100bb. You already parse natural language → structured (state→action).
   - Map each PokerBench row into your feature buckets (node_type, board class, etc.):
     - You know hero position, preflop line, board, stack, action so far, and GTO decision.
   - For each (node_type, feature bucket, hand class):
     - Tabulate frequencies from the 563k rows.
     - Where solver caches (B) exist: treat A as a “secondary” calibration check: ensure our parameters are consistent (qualitatively) but prefer exact solves (B) for HU; A dominates for 6-max spots not well-covered by HU solver caches.
     - Where B does not cover the node/texture: use A’s tabulated frequencies directly.

   **Verification method**:  
   - Hold out 10–20% of PokerBench spots by stratified sampling (by node type/board class).
   - Build your parameter tables on the remaining 80–90%, then:
     - Action-match rate on hold-out (how often floor chooses exact GTO action).
     - Calibrate vs existing baseline: run a small 6-max self-play or vs Slumbot, measuring bb/100 and LBR exploitability on a truncated tree (see 1.1.4).

4. **Refine bet sizing using existing heuristic formulas (G):**
   - Keep your existing bet sizing formulas but:
     - Use solver & PokerBench data to pick from a small discrete set rather than arbitrary.
     - Example: if solver shows for texture class X most EV is split between 33% and 100%, limit your allowed sizes to those.

   **Verification method**:  
   - For specific boards in B, compare EV of:
     - Full continuous sizing heuristic vs
     - Discrete solver-informed sizes with your hand selection.
   - Gate: new sizing set should not worsen EV vs solver by more than Y (e.g. 1–2bb/100) on those boards.

#### 1.1.4 Measuring floor exploitability (HU) with LBR

For HU specifically (you have a 209MB HU-turn cache):

- Build a reduced HU blueprint from the above method.
- Use Lower Bounding Rationality (LBR) on a subset of boards:
  - Opponent: uses best response on each decision from cached solves where available; where not available, approximate by local hand-equity + greediness.
- Measure exploitability:
  - Exploitability per hand / per 100 hands.
- Compare:
  - Existing heuristic floor vs new table-calibrated floor.
- Gate: accept if new floor’s exploitability is significantly lower with confidence (e.g. 95% CI via duplicate poker).

### 1.2 Exploit overlay

Use your existing engine (G) conceptually, but re-initialize priors and thresholds using (C) and (E):

1. **Opponent model:**
   - Stats: VPIP, PFR, 3-bet, fold-to-cbet by street/size, etc.
   - Maintain Bayesian posteriors for these stats, with conjugate priors seeded by:
     - Pluribus data (C): for “strong reg-like” players.
     - Exploit directives (E): to recognize named patterns (e.g. “overfolds to turn barrels”, “under-defends vs small flop bets”).
   - Confidence gating:
     - For each potential exploit adjustment, compute an approximate EV delta using:
       - Observed frequencies vs baseline GTO model (from A/B).
       - Pot size and number of times the pattern will occur.
       - Uncertainty from sample size (e.g. Beta posterior).
     - Only activate if lower-bound EV (mean – 2σ) is positive.

2. **Exploit action modifications:**
   - Input: base floor action distribution π_floor.
   - Opponent model proposes Δπ for specific contexts based on E (e.g. “overbet bluff 20% more on river vs this opponent profile”).
   - Final policy: π = (1-λ)*π_floor + λ*(π_floor + Δπ), renormalized, where λ is a function of confidence.

   **Verification method:**
   - A/B test:
     - Bot A: new floor only.
     - Bot B: new floor + exploit overlay.
   - Use duplicate matches against:
     - Slumbot (near-GTO).
     - Several weaker models (e.g. your own heuristic baseline).
   - Metrics:
     - vs Slumbot: ensure EV not worse than floor alone (> -X bb/100, same as floor within error bars).
     - vs weaker models: EV gain with significance (AIVAT/duplicate poker to reduce variance).

---

Q2. DATA SYNTHESIS: How to weight/combine A–G

### 2.1 Roles of each asset

- A (PokerBench GTO decisions):
  - Primary empirical source for 6-max postflop decision frequencies (floor).
  - Used for building lookup tables and validating heuristic parameters.
- B (solver caches, including HU turn cache):
  - Gold standard for HU blueprint and for calibrating general patterns (board class → action frequencies, sizes).
  - Used as local ground truth for EV gap testing.
- C (hand histories: Pluribus, Slumbot curve):
  - Pluribus: baseline “good human-ish bot” frequency priors for exploit modeling; sanity-check of our GTO floor (if floor suggests weird frequencies where Pluribus & solvers agree).
  - Slumbot fold-vs-size curve: exploited pattern used to test exploit engine; also a reference for “rational” behavior vs bet sizes.
- D (books):
  - Structural priors: range construction, qualitative strategy patterns; used only to initialize or interpret, not to override solver data.
- E (exploit directives):
  - Codified targets for exploit overlay (“if you see X stats, adjust Y this way by Z”).
  - Used as priors for which patterns to look for; but adjustments must be verified statistically in play.
- F (LLMs):
  - Not used in live play due to speed & sub-GTO accuracy.
  - Used offline for:
    - Fast annotation/classification of spots (e.g. mapping boards to bucket classes, summarizing book knowledge).
    - Generating candidate exploit heuristics or param sweeps, subject to later quant verification.
- G (existing bot):
  - Provides the framework: tree navigation, equity calc, opponent model, exploit engine.
  - Its heuristics are gradually overridden by table-driven values from A/B.

### 2.2 Conflict resolution hierarchy

When there is a discrepancy:

1. **Exact solver (B)** always dominates, but only in its domain:
   - If a board texture/stack/line is directly solved or very close in features: prefer B.
2. **PokerBench (A)** is next:
   - For 6-max lines not available in B, use A’s aggregated stats.
3. **Book priors (D)**:
   - Used when A/B coverage is thin or when needing to extrapolate; treat D as qualitative.
4. **LLM (F)**:
   - Only as hypothesis generator; never override A/B directly.
5. **Pluribus/Slumbot behaviors (C)**:
   - For exploit priors and sanity checks, not for floor building (since they’re approximate GTO approximations, not ground-truth).

### 2.3 Turning 563k PokerBench rows + solver caches into fast tables

Concrete pipeline:

1. **Parse & feature-map (A, B):**
   - Ensure all PokerBench rows and solver-cache nodes map to:
     - node_type, position, preflop pot type (SRP/3bet/4bet), board bucket, SPR bucket, hand class bucket, action label.
   - For B, you already have actions and frequencies; convert to same abstraction.

2. **Aggregate to tables:**
   - For each (node_type, board_bucket, SPR_bucket, hand_class_bucket):
     - Maintain:
       - Count of total examples.
       - Counts per action label (fold/call/bet-size-i/raise-size-j).
     - From B (solver), compute:
       - Average solver frequencies per action.
   - For HU vs 6-max, maintain separate tables.

3. **Smoothing & priority:**
   - Where solver (B) data exists:
     - Use B frequencies as the primary estimate.
     - Use A as a smoothing prior only if sample size from B is small.
   - Where only A exists:
     - Use A’s empirical frequency with Dirichlet smoothing (e.g. α=1 per action).

4. **Export tables:**
   - Serialize to binary (e.g. numpy arrays or small SQLite) keyed by (street, node_type, board_bucket, SPR_bucket, hand_class_bucket).
   - At runtime:
     - Compute feature bucket indices and do O(1) lookup into tables.
     - If bucket empty: fallback to parent bucket (e.g. more general board class) or heuristic default from D/G.

**Verification:**

- Offline:
  - Hold-out PokerBench subset, compute action-match rate using your floor policy (derived from tables).
  - For boards available in solver caches, compute EV gap vs GTO strategies.
- Online:
  - Run vs Slumbot and old heuristic floor; compare bb/100 with variance reduction.

---

Q3. Best use of the LoRA LLMs (F)

Your suspicion is correct: do not deploy them in live decision-making right now:

- Accuracy: 62–72% decision match on A, but:
  - That’s on PokerBench formats; real-game distribution differs.
  - They skew passive; that’s a very specific systemic leak.
- Latency: 8B/32B inference will be slow and variable, and margin over your calibrated tables is unclear.

Instead, treat them as tools for *offline engineering*, not as the policy.

### 3.1 High-value uses of the LLMs

1. **Automated annotation & bucketing:**
   - Use LLMs to automatically classify boards and lines into human-style descriptors:
     - “Wet low connected board favoring caller,” “ace-high dry board where PFR has significant range advantage,” etc.
   - Then convert those descriptors to your finite feature buckets.
   - This can speed the creation of your node_type/board_bucket taxonomy by generating large lists of (board, classification) that you then spot check.

   **Verification**:
   - Spot-check 100–200 samples per class vs your own definitions.
   - Measure inter-annotator agreement: are the LLM labels consistent with your designed bucket rules?
   - This is manual but bounded effort.

2. **Curriculum / diagnostic generator:**
   - Use LLM to:
     - Probe where the current floor deviates most from PokerBench/solver decisions.
     - For each misclassified region, ask LLM to explain qualitatively what pattern the GTO is following.
   - This helps you refine hand/board buckets without trusting LLM for final actions.

   **Verification**:
   - For each proposed “pattern” region, check PokerBench/solver data directly:
     - Does the claimed behavior actually hold numerically?
   - If yes, you can update bucket definitions or parameterization.

3. **Exploit heuristic ideation (offline only):**
   - Feed it your opponent model stats and ask:
     - “Given an opponent who folds X% vs flop c-bet but defends turn too wide, what exploit lines are likely good?”
   - Use outputs as candidate rules for E/G.
   - Then implement *only* after you derive explicit EV formulas and test via A/B.

   **Verification**:
   - Explicitly code the exploit rule.
   - A/B test vs synthetic opponents with that specific leak (can be built via solver modifications or scripted bots).

Given you have rich exact / labeled data (A, B), using the LLM to hallucinate new “GTO” data is low-value and dangerous; any such synthetic data will be worse than what you already have and hard to validate.

---

Q4. The exploit book (“Beyond GTO: Poker Exploits Simplified”)

Yes, extract it, but treat it as a structured exploit-primitive source feeding (G) and (E), not as gospel.

### 4.1 What to mine concretely

From the book, you want patterns of the form:

- Condition on opponent behavior:
  - “Overfolds flop vs large bets,” “Under-defends BB vs steals,” “Over-raises river with too many bluffs,” etc.
- Recommended exploit:
  - “Increase flop bluffing frequency in large sizing by Δ,” “3-bet lighter from BTN vs this villain,” etc.
- Sizing/line-specific advice:
  - Overbet polarizations in certain nodes.
  - Under-bluffing adjustments vs calling stations.

Turn each pattern into:

1. **Opponent-profile filters:**
   - For each exploit primitive, define measurable stats:
     - E.g. `fold_to_flop_cbet_large`, `river_raise_freq_IP`, `WTSD`, etc.
   - Map book thresholds (“if they fold too much”) to approximate numeric ranges (e.g. >70%).

2. **Action adjustments (Δπ):**
   - For each condition, specify:
     - Node(s) where you change behavior (e.g. river, OOP, facing missed c-bet).
     - How you adjust frequencies:
       - Increase bluffing proportion by α for given line.
       - Decrease thin value in some nodes.
   - Exactly the format your exploit directives (E) already use: (spot, action, freq_delta in [-0.3, 0.3], confidence).

3. **Initial confidence values:**
   - Assign low initial confidence (e.g. 0.1–0.3) to each pattern.
   - Let your opponent model update that confidence as it observes data (C, live play).

### 4.2 Integration into your exploit overlay

- Merge book-derived primitives with existing (E):
  - Tag each primitive with:
    - Source = book vs LLM vs earlier engineering.
    - Stats required.
  - In your opponent modeling loop:
    - For each primitive:
      - Check if the required stats are measured and consistent with the condition.
      - Compute approximate EV gain from applying the Δπ (as in 1.2).
- Apply the same confidence gating and A/B validation.

**Verification:**

- Offline:
  - Construct synthetic opponents that follow book-described leak patterns:
    - e.g. scripted bots that fold 80% vs pot-size flop bets, etc.
  - Simulate:
    - Baseline exploit engine (without new book primitives).
    - With book primitives.
  - Measure winrate difference with variance reduction.

- Online:
  - In real play (or vs population models from C), run:
    - Bot with exploit layer enabled vs disabled.
  - Look for consistent bb/100 improvement in leaks where book predictions apply (e.g. opponents flagged as overfolders).

---

Q5. Ranked plan (highest EV, concrete, with gates)

Here is a ranked, implementable plan for the next 1–2 weeks.

### Step 1: Build unified feature & node taxonomy  
- **Assets**: G (existing bot), D (books) for structuring.
- **Work** (1–2 days):
  - Enumerate the node types your bot commonly reaches (by preflop pot type, position, street, last aggressor).
  - Define coarse board buckets and SPR buckets.
  - Define hand classes (currently you use equity + some blockers; standardize into discrete classes).
  - Implement mapping functions from an actual game state to (node_type, board_bucket, SPR_bucket, hand_class_bucket).
- **Gate**:
  - Write tests: for a set of saved HHs, verify mapping is deterministic and consistent.
  - Manually inspect ~100 randomly chosen spots; confirm buckets make poker sense.

### Step 2: Aggregate A+B into param tables  
- **Assets**: A (PokerBench), B (caches).
- **Work** (3–4 days):
  - Parse A and B into structured features using Step 1 mappings.
  - Compute aggregated frequency tables per (node_type, board_bucket, SPR_bucket, hand_class_bucket).
  - Use B as primary, A as supplemental when B coverage low.
  - Serialize tables into a format your engine can query at runtime.
- **Gate**:
  - Hold-out eval on PokerBench:
    - Train on 80–90%, test on 10–20%.
    - Target: action-match > your previous heuristic baseline by a clear margin (e.g. +10–20% absolute) in relevant nodes.
  - For boards covered by B:
    - Simulate your table policy vs solver (static ranges).
    - Target: EV loss per state < small threshold (e.g. <1–2% of pot).

### Step 3: Integrate tables into bot as the floor  
- **Assets**: G (bot engine), tabulated policy from Step 2.
- **Work** (3–4 days):
  - Replace existing postflop heuristics in G with a table-driven decision:
    - compute buckets;
    - read recommended action distribution from table;
    - sample / pick highest-prob action.
  - Leave your equity-based logic only as tie-breaker or fallback.
- **Gate**:
  - Regression vs old bot:
    - No crashes; decision-time remains acceptable.
  - HU test vs Slumbot:
    - Run duplicate matches baseline vs new floor.
    - Target: new floor has clearly better bb/100 (closer to breakeven) with 95% CI including 0 but not including old -46bb/100 floor.
  - 6-max test vs Slumbot / strong bots:
    - Compare to your prior heuristic floor; you want reduced losses vs balanced opponents.

### Step 4: Measure HU exploitability via LBR on subsets  
- **Assets**: B (HU caches), new floor from Step 3.
- **Work** (2–3 days):
  - Implement a simple LBR opponent that:
    - When at a state found in B’s HU cache, plays best response action (or near-BR) given your public strategy.
  - Run enough hands on representative boards and lines.
- **Gate**:
  - Report exploitability of:
    - Old floor.
    - New floor.
  - Target: material reduction (e.g. >20–30% relative drop in exploitability).

*(This is measurement; if it reveals specific leak patterns, you can iterate bucket definitions and param values.)*

### Step 5: Re-tune exploit engine using E + C + book patterns  
- **Assets**: G (exploit engine), E (exploit directives), C (Pluribus/Slumbot), D5 (Beyond GTO, once extracted).
- **Work** (5–7 days, in parallel):
  - Extract “Beyond GTO” into machine-readable exploit rules (even basic regex/hand-tagging is fine initially).
  - Standardize all exploit primitives (from E and book) into:
    - Stats required.
    - Conditions on those stats.
    - Δπ (action frequency delta).
    - Initial confidence.
  - Seed opponent-model priors:
    - For “reg-like” profiles, use Pluribus stats as baseline priors.
  - Implement confidence-gated adjustment function (as described in 1.2).
- **Gate**:
  - Offline vs synthetic opponents:
    - Construct simple leaked bots (overfolders, stations, etc.).
    - Evaluate baseline vs new exploit overlay; require significant bb/100 gain, with very small or no loss vs simulated “GTO-ish” bot.
  - Online vs Slumbot:
    - Ensure EV does not get significantly *worse* than floor alone; exploit overlay should essentially turn off when leak not detected.

### Step 6: Use LLMs for analysis tools, not policy  
- **Assets**: F (LoRA LLMs), D (books), A/B as reference.
- **Work** (2–3 days, ongoing):
  - Build simple scripts that:
    - Use LLMs to annotate hands/boards with descriptive tags to accelerate bucket design evolution.
    - Ask LLMs to explain discrepancies between floor decisions and GTO (from A/B) in English so you can reason about better bucketing / paramization.
  - Use them to accelerate pattern discovery for exploit rules, but do NOT hard-wire unverified suggestions.
- **Gate**:
  - Qualitative: do you actually change buckets/params after verification based on LLM’s analyses?
  - Quantitative: whenever a LLM-inspired rule is implemented, it goes through the same EV-based A/B tests (never bypass this).

---

Things I’m explicitly unsure about (hypotheses):

- Whether PokerBench (A) covers enough 6-max turn/river lines to fully stabilize late-street behavior in rare configurations. You may find sparsity in some nodes; then you’ll need either:
  - more abstraction (coarser buckets), or
  - additional solves for those nodes.
- How well Pluribus (C) approximates population tendencies at your target stakes. Using it as a prior may slightly mis-bias exploits if your actual pool differs. That’s empirical and must be monitored.
- Exact bucket granularity vs EV: too fine gives sparsity from A/B; too coarse loses nuance. I recommend starting coarse, then refining buckets where EV-gap and action-mismatch metrics show consistent issues.

If you follow this plan, in 1–2 weeks you should have:

- A materially lower-exploitability HU/6-max floor, grounded in A+B.
- An exploit layer that is structurally richer (E+D5), but still mathematically gated and testable.
- A workflow where LLMs and books accelerate iteration but are never trusted without a solver/held-out gate.
