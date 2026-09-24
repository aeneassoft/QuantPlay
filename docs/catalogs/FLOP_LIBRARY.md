# FLOP SOLVE LIBRARY — Design (2026-07-05 night; ../NOTES.md queue #1, after the v3.x ladder)

> Goal: attack the flop bleed (−6.4…−8.3 bb/100, X-ray) that the doubly confirmed live NO-GO
> (49/50 timeouts @300s, `research/flop_feasibility.py`) denies the live resolver — through
> PRECOMPUTATION of canonical flops. Subsystem map: 6-agent workflow 2026-07-05 (this doc = distillate).
> Status: **design + calibration pilot** (`research/flop_pilot.py` → `data/research_sweep/flop_pilot.json`).
> NOTHING of this is shipped; `POKERB_RSV_FLOP` does not yet exist as code.

## Architecture decisions (derived from the map)
1. **The library IS the (ISO) solve cache, pre-warmed.** `gto_oracle.solve()` checks the cache before
   every solve; a precompute whose SHA1 key is byte-identical with the live call turns the
   live flop resolve into a ~0s lookup. No new storage system, no new lookup path.
2. **THE critical seam = key match.** The key hashes board|oop|ip|pot|eff|bets|acc|iters|dump|mode.
   The precompute MUST therefore generate through the LIVE path: play the preflop line through the
   `RangeTracker` → use the `emit()` strings (do not build "equivalent" ranges by hand). Flop entry ranges
   are pure functions of the preflop line (blueprint percentile bands: SRP=(0.66,0.84), 3bet=(0.06,0.34),
   limped=(0.85,0.85)) → finitely enumerable. Census preflop sizes (GTOW_SIZES) fix pot/eff per line
   (SRP: pot=450, eff=19775).
3. **ISO keying on:** `isomorph.canonical_board()` (lex-min over 24 suit permutations) → 1755 canonical
   flops instead of 22,100; the consumer remaps hero hole cards via suit_map (pattern exists: resolver.py:233/271).
4. **dump_rounds=1** (only the flop-street strategy in the dump): the turn/river decisions are taken over by the
   existing turn/river resolver; the dump stays small (~MB instead of ~100MB), the SOLVE still computes internally
   flop→terminal.
5. **Prioritization by frequency:** freq_targets (26.8k decisions): top-15 buckets = 42.4%, top-~50 =
   85% coverage. Order: SRP entry first (dominant, 1335 obs), then 3bet; limped/4bet+ the rest.
   Off-library spots → unchanged floor fallback (today's behavior, no regression risk).
6. **Menu:** census modal arms (flop 35, secondary 75; turn 75; river 65) — the 1.6x+ tails are n<5 noise
   and only bloat the tree (census agent). Minimal vs. lean tree is decided by the pilot.
7. **uint8 quantization (Compact CFR) = stage 2**, only if RAM preload becomes necessary — disk JSON first
   (the cache is disk-backed today and time-, not RAM-bound).

## The pilot (running) — the one missing number
`flop_pilot.py`: 4 texture representatives × {minimal, lean} tree, 30 min/solve cap, acc/iters identical
to the feasibility gate. It answers: **What does ONE converged flop→terminal solve cost at 200bb?**
From that: library budget = cost × target coverage → locally-over-nights vs. CPU pod ($2.24/h class).
(The bwfga5qs2 minimal-menu retest of the old session never persisted its result — the pilot replaces it.)

## ★ Critic panel conditions (2026-07-05 night, 3-agent adversarial review — BINDING for the design)
Raw data: `data/research_sweep/strategy_critic_panel.json`. The architecture-relevant verdicts:
1. **Staleness detection is mandatory (BLOCKER):** otherwise a miss is indistinguishable from "uncovered" →
   silent floor fallback → the Analyzer arm "refutes" a library that never fired. Fix:
   (a) **Manifest** `data/flop_library/manifest.json` = key set + build fingerprint (emit code version,
   blueprint bands, GTOW_SIZES pot/eff, menu, ISO status, allin_threshold, acc/iters); (b) the consumer
   validates the fingerprint at startup and fails LOUDLY; (c) hit/miss counters in the run log, expected hit rate
   PRE-REGISTERED — a shortfall aborts the arm as a broken measurement, not as a refuted lever.
2. **Order (BLOCKER):** P1 promotions (v3.3 changes `range_tracker.update`, v3.5 the advisor query)
   change the emit() strings → invalidate EVERY precomputed key. **First freeze the profile, THEN build through
   the frozen emit path** (profile fingerprint into the manifest). If computation must happen earlier:
   only pull forward solver dumps (board × line), recompute keys cheaply after the freeze.
3. **Query-side canonicalization:** the consumer uses the FIXED census menu and SNAPS observed
   size/pot/eff onto the library arms BEFORE the key computation (S3 snap concept) — otherwise every
   off-census size produces a unique SHA1 and precompute is impossible by construction.
4. **ISO coupling:** library keys are canonical, live `POKERB_ISO_CACHE` is default-OFF → without a fix
   only ~1/24 of the boards hit. The consumer enforces canonical keying for flop lookups independently of the
   global flag. CAUTION: ISO_CACHE=1 globally is itself a live behavior change (re-keys turn/river →
   100% miss on the warm cache → cold-solve behavior) → the Analyzer arm runs with the FULL
   consumption environment; both flags are in `_FINGERPRINT_KEYS` as of today.
5. **Lookup-only API:** on a miss NEVER into the solve path (the NO-GO costs seconds–minutes of wall clock) —
   key existence against the manifest set in RAM (plain `set`, NO Bloom filter — key count ≤ tens of thousands),
   floor fallback in ~0ms.
6. **Versioned key, own directory:** `data/flop_library/` with KEY_VERSION + allin_threshold in the
   key blob (the 12GB warm cache stays untouched = the deferral rationale survives). Precompute driver:
   idempotent + checkpointed (skip-if-key-exists; the persist-after-every-solve pattern of the pilot).
7. **GO gate before every arm ($0, deterministic):** offline replay of the 13.5k logged GTOW hands through the
   frozen emit path → EXACT expected hit rate (the 85% are bucket-, not key-level!) + the
   round-trip test (permuted board → cache HIT; the ISO proof pattern).
8. **Serialization (BLOCKER, generalized):** NO batch solve job during ANY live measurement
   (CPU-CPU version of the CLAUDE.md rule; timeout→floor fallback turns contention into a silent
   policy change). Finish pilot/precompute before smoke/anchor. Run the anchor arm first (warms the
   shared cache → determinism ally for the follow-up arms).
9. **Pilot self-contamination:** re-runs of the pilot only with `POKERB_SOLVE_CACHE=0` (otherwise timings
   are ~0s cache hits and the library budget rests on garbage). Tonight's run is cold=valid.
10. **Cross-street seam (dump_rounds=1) = accepted, second-order:** the seam already exists today
   (floor flop + turn resolver); condition: internal turn/river menus of the library == live resolver menus
   (align `_TURN_BETS`/`_RIVER_BETS` before the build). Deliberately NOT built: Bloom filter, uint8 before
   RAM shortage — refraining from overengineering is part of the design.

## Gate ladder (as always, before every ship)
Flag `POKERB_RSV_FLOP` default-OFF → byte-identical OFF (harness) → stress 70 spots → replay_graded →
coverage GO gate (#7) → own Analyzer arm with FULL consumption env (fresh anchor!) → if applicable live tail smoke.
One lever, one arm.

## Synergies (take along, do not build now)
- **EVPA corpus:** every library solve yields (spot, hand, line)→strategy/value labels; dumps carry
  `_exploitability_pct`/`_solve_iters`; CFV derivation via backward pass (cfv_eval machinery, B1-validated).
- **TurboReBeL ideas** (verified, rejected — ledger): iso augmentation uses the same `isomorph.py`;
  SSMIG only in our own v4 CFR core (TexasSolver exposes no per-iteration dumps).
- **Allin-threshold debt:** `_cache_key` does NOT carry `allin_threshold` (0.67 hardcoded) — include at the next
  planned cache flush (NOTES/audit), NOT now (invalidates the 12GB warm cache).
