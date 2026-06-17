# Synthesis consult — Claude claude-opus-4-8

# The Brutal Summary First

Your north star is correct, but your self-diagnosis buries the lede: **you don't have a floor problem with the exploit layer — you have a floor problem, period.** Losing -46 bb/100 to Slumbot with no exploit means your "GTO baseline" is roughly a 4.5 BB/100 *leak machine* against near-GTO. No exploit overlay survives contact with a good opponent if the floor bleeds that fast, because a competent opponent's "deviation" is small and your floor's error dwarfs it.

So the highest-EV work right now is **not glamorous exploitation — it's converting your exact solver/PokerBench data into a measurably-lower-exploitability floor**, then bolting the (already-good) exploit engine on top with confidence gates. The exploit book and LLM are secondary.

Let me answer each question concretely.

---

## Q1 — ARCHITECTURE NOW (1–2 weeks, no from-scratch net)

**The bot is a fast tabular/heuristic policy with a learned-from-data postflop core, plus a confidence-gated exploit delta. The LLM never runs in play.**

### The floor (this is where the 2 weeks goes)

Three layers, by street, in priority of how exact your data is:

1. **Preflop (HU + 6-max): pure lookup table.**
   - HU short-stack: keep your CFR push/fold blueprint (it's verified Nash — don't touch it).
   - 100bb preflop: distill PokerBench (asset A) into a preflop action table keyed by `(position, action-history-bucket, hand-class-169 or cluster)`. PokerBench is exact GTO labels — 563k rows is *enormous* for preflop, which has a tiny state space after bucketing. This alone should be near-GTO preflop.
   - **Verify:** action-match vs held-out PokerBench preflop rows (target >95% — preflop is easy and you have abundant labels); then LBR-probe preflop-only exploitability.

2. **Flop: solver-cache nearest-neighbor + interpolation.**
   - You have ~1340 solved flops @100bb (B). Build a flop-strategy retriever: key on `(board-texture features, range vs range from preflop node, pot/stack)`. For an unsolved flop, retrieve the k-nearest solved flops by a texture-isomorphism metric (suit-isomorphism + rank-bucket + connectivity/pairing features) and blend their strategies.
   - **This replaces your analytic c-bet heuristic** for spots within retrieval distance. That heuristic is almost certainly the source of much of the -46.
   - **Verify:** held-out: solve ~50 *new* flops you don't put in the cache, measure TV-gap (total variation between retrieved policy and true solve) per node. Gate the retriever on TV-gap thresholds — fall back to heuristic only where gap is large.

3. **Turn/river: your turn solve caches (209MB HU + 184 GCP boards) + MDF/pot-odds + blockers as the principled fallback.**
   - Turn/river state space is too big for full lookup, so: where you have a cache hit (esp. HU turn — that 209MB is gold for the HU bot), use it. Otherwise the analytic core (equity + MDF + fold-equity sizing + blockers) — but **re-tune its parameters against solver river/turn nodes** (see Q2).

### The exploit overlay (already mostly built — asset G)

- Keep the architecture: online opponent model → exploit engine → calibration loop.
- **Make every exploit a bounded delta on the floor's action frequencies**, with `freq_delta` clamped (your playbook E already uses [-0.3, 0.3] — adopt that bound universally).
- **Confidence gate:** an exploit fires only when (a) sample count for that opponent×spot-bucket exceeds a threshold, and (b) the observed deviation exceeds a noise band estimated from the opponent's own sample variance. Below threshold → play the floor.
- Cold start from playbook E via nearest-opponent-profile lookup; as real observations accumulate, the empirical model overrides the prior (Bayesian shrinkage toward the prior, not a hard switch).

### Data flow (per decision, in play)

```
State → parse to structured spot
  → Preflop? → preflop lookup table → floor_policy
  → Flop?    → solver-cache retriever (if TV-gap < τ) else analytic → floor_policy
  → Turn/Riv?→ cache hit? use it : analytic core → floor_policy
floor_policy → opponent_model.lookup(opponent_id, spot_bucket)
  → if confidence ≥ gate: apply bounded freq_delta → exploit_policy
  → else: floor_policy
→ sample action
(async, offline) all hands → opponent_model update → calibration loop
```

**Verification of the whole thing:** the only number that matters is **LBR exploitability + AIVAT/duplicate bb/100 vs Slumbot with exploit OFF**. If the new floor gets you from -46 to something like -5 to -15 bb/100 *with no exploit*, the rebuild worked. Then turn exploit ON and re-measure; the exploit should not *hurt* vs near-GTO (gate is working) and should crush the weak field as before.

---

## Q2 — DATA SYNTHESIS: weighting, conflicts, distillation

**Precision hierarchy (who wins conflicts):**

```
Solver caches (B)  >  PokerBench labels (A)  >  Books (D)  >  Our LLM outputs (F)  >  Playbook priors (E)
   [exact at node]    [exact GTO, templated]    [principles]   [62-72%, biased]      [hypotheses]
```

- **Floor = B + A.** B is exact at solved nodes; A covers the breadth (563k spots) with exact labels. Where they overlap, B wins (it's the ground truth A was approximating). A fills everything B doesn't cover.
- **Seed exploitation = E + C + book 5.** Playbook E is cold-start prior; Pluribus leak tables and the Slumbot fold-curve (C) are *measured* opponent deviations → these are stronger than E for the specific opponents they describe.
- **Inform reasoning / fill gaps = D + F.** Books give principled fallbacks and feature ideas; F generates references only where A and B are silent (see Q3).

**Conflict resolution rule:** if the solver cache and a book disagree on a spot, **solver wins, always** — but log the disagreement. A cluster of solver-vs-heuristic disagreements is a map of your floor's leaks; prioritize re-solving those textures.

**Turning 563k rows + caches into fast queryable parameters:**

1. **Preflop → exact lookup table.** Bucket the action history (open/3bet/4bet, positions), key by 169 hand classes or learned clusters. ~minutes to build, near-perfect.

2. **Flop → solver-cache k-NN retriever** keyed on texture-isomorphism features (see Q1). Precompute a feature vector per cached flop; at query time, nearest-neighbor + suit/rank isomorphism mapping back to the actual cards.

3. **Postflop heuristic parameter recalibration.** Your analytic core has knobs (c-bet freq by texture, bet sizes, MDF thresholds, fold-equity targets). **Fit those knobs to minimize TV-gap against the solver caches** — this is a small regression/grid-search, not training. This is probably your single highest-leverage cheap win: you already have the machinery and the ground truth; you just haven't tuned the machinery *to* the ground truth.

4. **The dormant `openai_strategy.json` numeric postflop spec:** wire it in *as a candidate parameter set* and A/B it against the solver-tuned knobs via TV-gap. Don't trust it blind — it's untested. Cheap to evaluate, so test it; keep it only if it lowers TV-gap.

---

## Q3 — OUR LoRA LLMs: deploy or not?

**Decision: Do NOT deploy either in play. Correct call. Use the 8B narrowly, offline, as a gap-filler — and only behind a verification gate. The 32B is near-worthless for your purposes; mothball it.**

Reasoning:

- **In-play:** too slow, and 62–72% action-match means it's *less accurate than your distilled tables* on exactly the spots the tables cover. The 32B's passive skew (checks > bets, folds > raises) is a systematic, EV-bleeding bias — deploying it would re-introduce a leak you can measure. Hard no.
- **As a GTO reference generator for uncovered spots:** **only marginally useful, and only the 8B.** Here's the honest math: the LLM was *trained on PokerBench*, so its "knowledge" is a lossy 71.7%-accurate compression of asset A. Asking it for references in spots A doesn't cover = extrapolation by a model that's already lossy and biased. **Don't use LLM output where you can cheaply run TexasSolver instead** — you have the solver and GCP. A fresh solve is exact; the LLM is a guess. The LLM's only legitimate niche is spots that are *expensive to solve AND outside PokerBench* — and even there, every LLM-generated label should be spot-checked against a solve before entering the floor.
- **As a curriculum director (which boards/spots to solve next):** **this is its best use.** Have the 8B *propose* under-covered or high-frequency spot families; then you allocate solver compute there. The LLM's failure mode here is benign — a bad suggestion just wastes a little solve time, and the solve itself is the ground truth. This respects Lesson 1 (LLM = hypotheses only).
- **As an async per-session exploit proposer:** *maybe*, low priority. It could read a session's hand histories and propose exploit hypotheses (freq_deltas) — but these are strictly hypotheses that must pass the confidence gate and calibration loop before firing. This is redundant with your existing exploit engine + book 5; only pursue if the engine is starved for hypotheses.

**Verify the gap-filler use:** for any batch of LLM-generated references, solve a 10% random sample exactly and measure action-match. If <90%, discard the batch and just solve everything.

**Bottom line:** the LLM is a worse copy of data you already have exactly. Its one defensible job is *suggesting where to point the solver*. Don't sink time here.

---

## Q4 — THE EXPLOIT BOOK ("Beyond GTO")

**Yes, extract it — it's cheap and it's the only asset directly targeting your actual edge (exploitation), and unlike the other books it isn't redundant with your solver data.** But extract it for **primitives and trigger→adjustment rules**, not prose.

**What to mine (concrete exploit primitives):**

- **Population/opponent tendency → adjustment mappings**, in the same schema as playbook E: `(opponent_tendency_signal, spot_class, action, freq_delta, confidence)`. E.g. "villain folds too much to turn barrels → increase turn-barrel freq by δ in spot X."
- **Observable triggers**, mapped to stats your online model already tracks: fold-to-cbet, fold-to-3bet, aggression frequency, fold-to-river-bet by size, limp frequency, etc. The Slumbot fold-vs-bet-size curve (C) is exactly this kind of trigger — the book should give you a *taxonomy* of such curves and the correct response to each.
- **Exploit magnitude/bounds** — the book should inform how *far* to deviate per tendency strength, which feeds your `freq_delta` clamp.
- **Counter-exploit awareness** — when villain might be adjusting back (relevant if you replay the same opponent).

**How it plugs in:**
1. Extract to JSON in playbook-E schema → **merge into the exploit prior store**, tagged by source (book vs Haiku vs Opus vs measured).
2. Map each primitive's trigger to your opponent model's existing stat fields.
3. **Crucially: book directives are priors, not facts** (Lesson 1, and your refuted thin-value/draw-cbet experiences). They enter at the *prior* end of the Bayesian shrinkage, get overridden by real observations, and must clear the confidence gate before firing.

**Verify:** run the bot with book-primitives ON vs OFF against your exploitable-bot suite (the +300..+700 opponents) using AIVAT/duplicate variance reduction. The book layer should *increase* exploit EV vs weak opponents and *not decrease* it vs near-GTO (gate holds). If a specific primitive shows up as net-negative in held-out duplicate matches, kill that primitive — don't trust the book over the measurement.

Effort: ~1–2 days extraction + schema mapping. High ROI relative to cost.

---

## Q5 — RANKED PLAN (highest EV first)

**1. Recalibrate the postflop analytic core against solver caches (TV-gap fitting).**
- Assets: B (solver caches) + existing G core.
- Gate: mean/median TV-gap between core policy and held-out solved nodes drops; then LBR exploitability of floor-only drops; then floor-only bb/100 vs Slumbot improves from -46.
- Effort: 2–4 days. **This is the biggest expected EV — it directly attacks the -46.**

**2. Build the preflop exact-lookup table from PokerBench.**
- Assets: A (+ existing HU push/fold from G untouched).
- Gate: held-out preflop action-match >95%; preflop-only LBR low.
- Effort: 1–2 days. High EV, low risk — preflop is where exact labels are most decisive.

**3. Build the flop solver-cache k-NN retriever with TV-gap fallback gate.**
- Assets: B (1340 flops + cover cache).
- Gate: on 50 *held-out freshly-solved* flops, retrieved-policy TV-gap below threshold for >X% of nodes; floor-only bb/100 improves.
- Effort: 3–5 days. High EV but more engineering; the held-out solve is the honest test.

**4. Extract Book 5 → exploit primitives, merge into prior store behind the gate.**
- Assets: D(5) + E + C + G exploit engine.
- Gate: exploit-ON vs exploit-OFF in duplicate/AIVAT matches — up vs weak field, not-down vs near-GTO.
- Effort: 1–2 days. Good EV on your actual edge, cheap.

**5. Tighten the confidence gate + Bayesian shrinkage on the exploit overlay.**
- Assets: C, E, G.
- Gate: vs Slumbot with exploit ON, bb/100 should be ≥ floor-only (gate prevents harm); vs weak field, exploit ON >> OFF.
- Effort: 2–3 days. Protects the floor gains from #1–3 being eaten by overzealous exploits.

**6. (Conditional / low priority) Use 8B LoRA as curriculum director to point the solver at uncovered high-frequency spot families.**
- Assets: F (8B) + B (solve them) + GCP.
- Gate: 10% of generated references solved exactly to verify; only keep solver outputs, never raw LLM labels.
- Effort: 1–2 days. Marginal EV; do only after 1–5.

**Mothball:** 32B LoRA (passive bias, no use); don't deploy any LLM in play.

---

### Flags / honesty caveats

- **The -5.4 bb/100 "with fold-curve exploit" is, by your own admission, not conclusive.** Before celebrating any floor improvement, fix your measurement: AIVAT or duplicate poker, and enough hands that the confidence interval excludes zero. **Hypothesis: a chunk of your current "break-even vs Slumbot" is variance, not skill.** Verify before building on it.
- **Hypothesis (must test):** that the analytic c-bet/sizing heuristic is the dominant source of the -46. Likely, but confirm by measuring TV-gap per street — if turn/river gaps dominate, reprioritize toward the turn caches.
- **k-NN flop retrieval correctness is the riskiest engineering claim here.** Texture isomorphism + range-dependence means a "near" flop by texture can still differ a lot in strategy if the preflop ranges differ. **Gate hard on held-out TV-gap; do not assume the retriever generalizes.**
- **Cheap thing you may be under-using:** you have GCP solve capacity. Solving 200–500 more targeted flops/turns (directed by where your TV-gap is worst) is probably cheaper and more reliable than any LLM or clever interpolation. Brute-force ground truth where it hurts most.

Build the floor first. The exploiter is only as good as the floor it deviates from.
