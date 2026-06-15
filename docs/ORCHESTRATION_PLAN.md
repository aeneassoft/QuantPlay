# ORCHESTRATION PLAN — iterative floor improvement (gpt-5.5-vetted, $70, CPU-first)

Source: `docs/orchestrate_gpt55.md` (gpt-5.5, grounded in our measured numbers), vetted by Claude. Supersedes
"(c) = train a GTO net from scratch": the highest-ROI path is an **eval-gap-driven iterative floor improvement**
with the net inserted ONLY as a small supervised **advisor** (glue over EXISTING data), not a from-scratch solve.

## The substrate decision (GPU vs CPU)
Measured: NLHE Deep-CFR is **CPU/traversal-bound** (GPU peak 0.2 GB / 143, ~47 traversals/s).
- **GPU** — pro: batched supervised training (the advisor). con: idle for traversal/CFR; **H200/B200 = pure waste here.**
- **CPU** — pro: matches the bottleneck (traversal), inspectable (regret tables, freq drift), cheap. con: full NLHE still huge; fcpa is lossy.
→ **CPU-first** for any CFR/self-play (smoke/analysis ONLY). **Cheap GPU (~$0.33/hr) only to train the small advisor.** Never rent H200/B200 for this. $70 is plenty (we'll use a fraction); it is NOT enough for from-scratch NLHE self-play (nor the right substrate).

## The net = "connecting interface logic" (the user's idea, made concrete)
A small supervised **GTO-floor advisor** that INTERPOLATES our existing assets — NOT a from-scratch GTO solve:
- **Ingests:** state (street/pos/pot/SPR/to-call/action-history/legal-mask) + hero+board cards/texture + **our existing bot's own features** (current heuristic action, MC/exact-river equity, pot-odds, MDF, fold-equity, hand class). It is GLUE, so it sees what the bot already computes.
- **Outputs:** action prior over our EXISTING action set + sizing prior over our EXISTING sizes + a **confidence/OOD score**.
- **Plugs in:** POSTFLOP FLOOR only, before the exploit overlay: `if conf high & in-domain: floor = blend(heuristic, advisor, α=0.25) else heuristic` → then the bounded overlay (unchanged, still last + capped).
- **Trained on:** TexasSolver caches (primary) + PokerBench 563k (broad), holding out whole flop/turn classes.
- **NET IS NOT WORTH IT for:** the preflop table (have 88.6%), exact river equity (keep enumeration), pot-odds/MDF (exact formulas), the exploit overlay (bounded rules are right), Leduc (CFR+ already exact). Keep those.

## The gate (one signal): held-out SOLVER EV-gap
NOT raw bb/100 (Slumbot ±110 = too noisy for small runs). For each held-out solver spot: bot action vs solver
mix → **EV loss / pot**, broken down by street / position / SPR / pot / action-class. A change is KEPT iff:
targeted EV-gap ↓ (≈5–10%+) AND no global regression AND action-diffs land in the hypothesized area AND
guardrails hold (preflop acc, river enum, overlay caps, legality). Slumbot/duplicate = secondary disaster-check only.

## The loop (hypothesis → small run → inspect → adjust)
0. **Freeze** baseline (bot version, tables, datasets, seeds, action mapping) — paired comparison.
1. **One narrow hypothesis** (falsifiable by one short run).
2. **Smallest test** (rule/table patch → nearest-neighbor solver lookup → tiny model; NOT "train a big net").
3. **Run short** (10–90 min eval/rule; 1–3 h CPU MCCFR smoke; never 24 h+).
4. **Inspect 3 reports:** (a) solver EV-gap by street/pos/SPR/pot/action; (b) action-diff vs old bot; (c) guardrails.
5. **Keep / revert** by the gate above.
6. **Opponents last** (Slumbot/duplicate) — catch disasters, not prove subtle gains.

## Starting hypotheses (ranked)
- **H1 (priority): the postflop HEURISTIC FLOOR is the main near-GTO leak** (our floor ≈ −97 vs Slumbot; postflop is heuristic except river). Test: solver-cache evaluator → heuristic vs nearest-neighbor solver-policy vs advisor vs blend.
- **H2: turn is the weak street** (river now exact). Test: turn-only EV-gap by SPR/texture/draws → a turn calibrator.
- **H3: sizing mismatch** (wrong size, not bet-vs-check). Test: sizing confusion matrix vs solver → a "sizing selector" over existing sizes.
- **H4: the 11.4% preflop-table gap** poisons later ranges. Test: complete the missing/low-conf entries from PokerBench (table/rule, no net).
- **H5: overlay too active vs near-GTO** (low-conf spots). Test: overlay diagnostics + a stricter confidence gate; keep field winrate, cut near-GTO EV-gap. (Do NOT optimize first — the floor is the bigger problem.)

## First 3 runs (mostly LOCAL + cheap)
- **Run 1 — solver-EV-gap evaluator + floor error map** (LOCAL, ~free). The keep/revert dashboard + "where does the floor lose most EV vs solver?" → pick the top-2 leak buckets. *Success = stable paired metrics, reproducible, interpretable action-diffs.*
- **Run 2 — cheapest patch for the biggest bucket** (LOCAL/cheap): table/rule/sizing-calibrator or nearest-neighbor solver-cache lookup. *Keep iff targeted EV-gap ↓, no global regression.*
- **Run 3 — minimal supervised advisor** (cheap GPU/CPU, ~$1–5): solver caches + PokerBench; MUST beat nearest-neighbor + LightGBM + table baselines; conf-gated blend α=0.25 into the postflop floor. *Keep iff held-out EV-gap ↓ 5–10% + beats the non-net baselines.*
- (Later) CPU MCCFR on fcpa = analysis/coarse-blueprint tool ONLY if it reduces solver-gap (target ≥10× the 47 trav/s first).

## Cost
Mostly LOCAL (eval harness + patches = ~free). RunPod only for the tiny advisor (cheap GPU, ~$1–5). $70 = plenty; B200/H200 = no.
