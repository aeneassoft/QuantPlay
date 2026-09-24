# NEXT RUN — evidence-grounded TO-DO (re-scoped 2026-06-16 after the CFV pilot + 2× frontier consult)

## ★ READ FIRST — the priority ORDER (grounded this session)
The X-ray (`extraction/gtow_xray.py`, $0) localized −72 vs GTOW: **PREFLOP −50 (67%)** + **jam spew −15** +
**postflop-non-jam ~−10 (the SMALLEST term)**. Preflop is largely addressed (near-Nash blueprint, wired). So the
remaining gap is postflop — but BOTH frontier consults (o3 + gpt-5.5, `docs/consults/nextrun_*`), the quadruple-
triangulation, and the plan AGREE on the order:

1. **★ #1 — do FIRST, $0: the EXACT combo-level range-tracker keystone.** Today's tracker is class-level / preflop-
   line-only → it feeds the EXISTING (shipped) turn/river resolver too-WIDE ranges (the "−72 neutral resolver") AND
   can't sample the right CFV states. Fixing it (a) makes the resolver sharp NOW, (b) is the PREREQUISITE for any CFV
   net data. Both consults rank it ABOVE the net: ~3-8 bb/100 at **$0**, vs the net's ~4-8 bb/100 at high cost + risk.
2. **#2 — re-X-ray after the keystone** (`gtow_xray`, $0): is postflop still material? Only scale the net if yes.
   (gpt-5.5: "do not assume the net recovers 50 bb/100 without measurement".)
3. **#3 — the CFV value net, only if #2 greenlights it** — with the CORRECTED calc + accel tricks below.

---

## The CFV net — CORRECTED calculation + acceleration tricks (ready for when #2 greenlights it)
The pilot (this session) PROVED the pipeline + architecture (the 392→338 MLP fits train to ~0 once targets are
normalized) but is DATA-LIMITED (99 samples → held-out 96% of scale). Before scaling, two things changed (o3 +
gpt-5.5, VETTED — `docs/consults/nextrun_calc_o3.md`, `nextrun_design_gpt55.md`):

### (a) FIX the target — the current one is WRONG (omits turn betting)
`turn_boundary_cfv` solves the 48 rivers SEPARATELY at the turn pot + averages = "river EV after a forced turn
CHECK-CHECK" → it OMITS all turn-betting EV (Δ up to 10-20 bb on coordinated turns; turn-bet-fold nodes invisible)
and is not a consistent joint strategy. CORRECT target = **ONE `dump_rounds=2` turn+river solve + a single backward-
induction pass** (turn betting → river CHANCE node (card-removal) → river betting → showdown/fold). Build
`cfv_eval.compute_turn_cfv` = the river backward-pass + a river chance node. ~10-40× cheaper AND correct.

### (b) ACCELERATION tricks — the binding constraint is SOLVE COUNT, so ELIMINATE solves first
- **Board suit-canonicalization** (~8× fewer distinct solves; the net never re-learns suit permutations). [o3]
- **`dump_rounds=2` single solve** replaces 48 river solves (= also (a)). [o3]
- **Vectorized showdown-matrix extraction** — replace the O(169²) per-matchup Python loop with a precomputed per-board
  win/tie/lose matrix + numpy → ~100× faster extraction (kills the GIL loop that forced the ProcessPool). [Claude]
- **DeepStack river-net bootstrapping** — train a cheap RIVER net first, then use it as the turn-solve's river-leaf
  evaluator → near-free turn data. [Claude, follow-on]
- Cheaper per solve: shallow iters (label noise averages out), minimal bet menu, range pruning (drop ~0 combos).

### (c) GATES before any big run (gpt-5.5, non-negotiable)
- **169-aliasing test FIRST:** same-board / same-169-range states with different suit-combo distributions → direct-
  solve both → if weighted-CFV-L1 > ~0.75 bb (1.5 bb in big pots), the 169-class input is ALIASED (can't tell KhQh
  from KsQs on heart boards) → need combo-level or board-relative suit/blocker features. *More data cannot fix missing
  information.*
- **Coverage = real line-narrowed ranges** (the keystone's output: SRP/3BP/4BP × c-bet/check/raise/call leaves), NOT
  uniform-random; stratified oversample of rare high-EV-error textures (monotone, flush-completing, paired,
  four-straight, low-SPR); pot/SPR bins; oversample big pots (a 10 bb error in a 120 bb pot is fatal).
- **Bet abstraction (compact, faithful):** turn `33 / 75 (or geometric) / 150 / all-in when SPR≤2.5-3`; river
  `33 / 75 / 150 / all-in when SPR≤2-2.5`; one non-all-in raise + jam, cap one raise. (Everything-at-every-node = overkill.)
- **Sample schedule:** 5k (learning-curve + aliasing) → 20k (does held-out fall?) → 100k (first serious). If held-out
  plateaus > ~3 bb at 20k, the blocker is NOT volume.
- **Deploy-safety gates** (before the net touches a real decision): held-out ≥5-10k split by board/line/pot;
  weighted-L1 ≤0.75 bb mean / ≤1.5 bb p95; range-EV bias ≤0.15 bb; zero-sum residual ≤0.05 bb; nut/blocker sanity;
  **ROOT-DECISION REGRET ≤0.25 bb mean / no >3 bb in big pots**; an OOD detector + solver fallback. (Full list:
  `docs/consults/nextrun_design_gpt55.md` §4.)

### Realistic ROI (gpt-5.5, honest)
A good CFV net recovers **~4-8 bb/100** (optimistic 8-12), NOT a −72 fix (preflop was the big term). The net is the
right LONG-TERM architecture but lower-ROI than the keystone — which is why it is #3, not #1.

---

## Discipline gates (keep — Fable-5)
- Only a GROUNDED signal gates a change (solver-gap / AIVAT / exact exploitability / a deterministic check). A single-
  rule raw-bb/100 A/B is too noisy (plausible fixes were REVERTED after measurement). Slumbot whole-bot is variance-
  limited (±~30-46 even at n=2500 — this session: −39.6 ±30.9).
- Pre-register KILL gates before any big build; a GTOW number inside noise is NULL, not success.
- Hard-separate DONE+measured from planned/hoped in every report.

## Compute / cost reality
- #1 (keystone) + the corrected calc + the vectorized extraction are **$0 local**. The CFV data-gen, with the tricks,
  is feasible local + a modest pod — NOT the o3 "1000 VMs × 4 days" estimate (that assumed 1500-iter full convergence;
  our label regime is ~50× cheaper). ALWAYS `--kill` pods (verified **0 live** now; the atomic 48-solve sample is why
  short pod windows produced 0 — fixed via `k_rivers` + the dump_rounds=2 plan).

## SUPERSEDED (history pointer — do NOT re-do without re-deciding)
- The prior content of this file (the **fine bet-abstraction self-play POLICY-net run**: fcpa → 0.33/0.5/0.75/1/1.25/2/
  all-in + richer features + DCFR+ port + clairvoyance gate) is SUPERSEDED by the DeepStack CFV-VALUE-net path — a
  policy net IS the −72 imitation ceiling (measured −212 for fcpa). The fine-abstraction + clairvoyance-gate ideas stay
  valid IF the pure self-play policy core is ever revived; the CFV value net (re-solved strategy, not a copied policy)
  is the committed postflop path. (Old text recoverable from git history pre-2026-06-16.)
