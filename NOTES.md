# NOTES — in-repo notes & deferred-precision log

A running, in-repo log of OPEN QUESTIONS, DEFERRED PRECISION items, and "good-enough-now, compute-exactly-later"
decisions. Distinct from the cross-session auto-memory (`C:\Users\hampe\.claude\projects\...\memory\`). Add an
entry whenever we ship a heuristic/approximation that should later be replaced by an exact/measured value.
Referenced from `CLAUDE.md`.

## ★ Neural self-play GTO core (2026-06-16) — the current frontier (deferred-precision + gates)
We PIVOTED to a from-scratch neural **Deep CFR self-play** net (`strategy/deep_cfr.py` Leduc, `deep_cfr_hunl.py` HUNL,
`deepcfr_adapter.py` net→bot) because the solver-imitation floor is a MEASURED ceiling (~−72 vs GTO Wizard, broad
postflop, run-to-run noise ±8). Pure self-play, no imitation (AlphaGo-Zero logic). DEFERRED-PRECISION items to fix
(scoped in `docs/NEXT_RUN_TODO.md`, vetted vs 4 sources incl. Supremus + the AAAI-26 DCFR+ paper):
- **[ship-now, fix next run] fcpa betting abstraction** (fold/call/POT/all-in) is "structurally impoverished" (can't
  express geometric sizing / overbet / merge-bets). Next: `0.33/0.5/0.75/1/1.25/2/allin`. THE Rank-1 lever.
- **[ship-now, fix next run] 20-dim strength-bucket features** collapse exactly what GTO needs (range-polarity,
  blockers, SPR, texture). Next: card-occupancy + hand-class/draw/texture flags, ideally the OpenSpiel
  universal_poker information-state tensor. NOT WEVA (vetted low-ROI for full HUNL).
- **[done on Leduc, port to HUNL] DCFR+** (discount+clip+bootstrap of cumulative ADVANTAGES) — took the neural Leduc
  run 445→338 mbb (LinearCFR plateaued ~445); the HUNL trainer is still LinearCFR → port it.
- **[deferred] variance-reduction baseline net** (DREAM/PDCFR component 3) — real but secondary for EXTERNAL sampling;
  add only after validating the abstraction direction + on Leduc exploitability first (an unvalidated ES baseline biases).
- **[deferred — the eventual ceiling] CFV value net + depth-limited continual resolving** (Supremus/DeepStack). Policy-
  net-only likely plateaus below GTOW parity; resolving is the path to near-0. A full architecture, not a patch.
- **VALIDATION GATES (math theory):** (1) Leduc EXACT exploitability (the correctness gate); (2) the clairvoyance
  toy-game — the net must bluff at α=s/(1+2s) (=1/3 at pot) + defend at MDF=1/(1+s) (=1/2 at pot), ±0.05, RIVER ONLY
  (river-MDF does NOT hold on flop/turn — semi-bluffs). See `docs/math_theory_net_connection.md`.
- **CONTAMINATION BOUNDARY (hard rule):** the pure self-play core is NEVER trained on imitation data. Books/papers →
  validation+design; PokerBench → a real-HUNL GTO-match validation set; Pluribus → eval-distribution + exploit overlay;
  OpenSpiel → feature representation + the fast-traverse pod path; the LLM → exploit overlay. None are training labels.
- **Compute reality:** the bottleneck is the Python MCCFR traverse (CPU), NOT the net → a B200 does NOT help the
  current code (measured slower for tiny nets). The pod helps ONLY via OpenSpiel's C++ traverse (`deep_cfr_nlhe.py`)
  or a vectorized rewrite. Cheap first win: multiprocess the traverse locally.

## Deferred precision (compute exactly later)
- **[2026-06-15 ✅ table + OOP wired] GTO donk + c-bet frequencies by texture.** EXTRACTED to
  `knowledge_base/postflop/texture_freqs.json` (`extraction/texture_freqs.py`, 1340 boards). OOP donk now wired
  PER-TEXTURE in `bot.py` (`_texture_freq`): monotone 12%≈GTO 14%, ALL 22%≈21% on the floor map. REMAINING:
  (a) the IP c-bet is still ~87% vs GTO 74% (value-always-bets); (b) the per-texture donk/c-bet HAND-SELECTION
  (which hands, not just the frequency) + SPR/position split. Both handled holistically by the supervised
  advisor (#36–41), which learns frequency AND selection from the same caches.
- **[2026-06-15 ⏳ solving] Turn advisor (#41) full coverage.** `turn_advisor.pt` is PRELIMINARY (turn nodes of
  only 46 flop files; +23% vs freq baseline, held out over 2189 turn boards). A robust 8h RunPod turn-coverage
  solve (DUMP=2, pod szx1z9in3g1rve, ~350 boards/h) is running. WHEN DONE: rerun `extraction.build_turn_data`
  then `extraction.train_turn_advisor` on the pod, pull `turn_advisor.pt`, then `runpod_run --kill`. See the
  auto-memory `active-runpod-turn-solve`.
- **[2026-06-15 ✅ river advisor wired (WS2)] River blocker nudges (#40).** `bot.py:_river_blocker_signal` biases
  river bluff SELECTION + nudges the bluffcatch threshold ±6%. The river-subgame solve (`_gto_river_cache`, 1308
  boards) now exists → a solver-grounded RIVER advisor (`river_advisor.pt`, +51% vs the freq baseline) SUPERSEDES
  the #40 bluff-SELECTION heuristic on the betting node (per-hand solver P(bet), OOP-lead/IP-after-check). The #40
  BLUFFCATCH nudge (facing a bet) stays active (disjoint node). The 3500 "value" rank bar etc. now only matter on
  the rarely-hit no-advisor fallback. Net: the river is solver-grounded, not heuristic.

## Open questions
- **[2026-06-15 ✅ RESOLVED — the −13 was a small-sample mirage] MVP#2 river resolver vs GTO Wizard = decision-grade
  −72.06 ±6.70 (n=2498), NOT −12.9.** Real-time TexasSolver re-solve of the river public state (`strategy/resolver.py`
  + `range_tracker.py`, `bot.use_resolver`). The 2500-hand confirmation gave **−72 ±6.7** (tight); the −12.9 ±69.6
  (n=150, RAW +200) was a LUCKY sample (−13 lay inside its own ±70 CI of −72). **−72 < Always-Fold (−64.6)** ⇒ fed the
  preflop-line-only (too-wide) ranges, the resolver confidently plays the WRONG equilibrium in big pots and SPEWS —
  the empirical confirmation that the **Bayesian action-consistent postflop range tracker is a PREREQUISITE**, not a
  refinement (without correct ranges the resolver HURTS). MVP#1 floor −33 was n=30 (unreliable); floor baseline at
  n=2500 pending. LESSON (again): small AIVAT samples (n≤150) lie — only n≥2500 is decision-grade. NOTE: GTO Wizard Benchmark paper
  (arXiv 2603.23660) VALIDATES MVP#2 — GTO Wizard AI = real-time-solving + value-net + balanced ranges, beat
  Slumbot +19.4/150k; the LLM failure mode = FREQUENCY/MIXING mistakes (exactly what the resolver fixes).
  Leaderboard: GPT-5.3 −16, Opus 4.6 −20.4, Opus 4.5 −22.3, Gemini −30.8, Grok −60. Bench = HUNL 200bb, 5000
  hands/agent. Next per the GTO-gap: turn resolver (P2) + a $140 RunPod multi-CPU mass-solve for a richer
  public-state blueprint (P3) / CFV value net (P4).
- **[2026-06-15] Run 2 duplicate watch.** The OOP-donk cap (`oop_donk_freq`) improved the solver-gap (the
  primary gate) but the duplicate-vs-GTOBaseline point moved −1.4 → −34 ±105 bb/100 (within noise, no disaster).
  Verify at scale (≥600 decks), AND check whether checking-more-OOP exposes a DOWNSTREAM leak vs the aggressor's
  c-bet (the flop-only solver-gap can't see that) — i.e. is our facing-c-bet defense after checking OOP sound?
  Knob: `PokerBot.oop_donk_freq` (currently 0.5 → ~25% donk; lower to approach GTO 20%).
- **[2026-06-15 ✅ RESOLVED] WS1 floor-bleed ablation (the −102 vs Slumbot).** `pokerbot/benchmark/floor_ablate.py`
  (600 decks, paired/duplicate, deterministic, vs GTOBaseline; 4 A/B toggles on `PokerBot`). full_floor = **−25.3
  ±40.6 bb/100** (NOT significantly losing — ~0.6σ from break-even). Paired Δ vs full_floor: #40 river-blocker **+0.0
  ±0.0** (zero effect), #41 turn-advisor **+8.3 ±20.0** (sub-1σ), fe-sizing −3.4 ±4.1 (mildly HELPS), mdf-shade +0.0
  (inactive on the floor: conf=0 ⇒ shade=0). **Verdict (c): the −102.5 ±44 vs Slumbot @2000h is variance /
  Slumbot-specific — NOT a reproducible floor leak nor a #40/#41 regression vs near-GTO.** Decision: do NOT gate
  #40/#41 off; do NOT pre-fix (this also closes the "Run 2 duplicate watch" above — verified at ≥600 decks). WATCH
  (don't fix, sub-2σ): #41 turn-advisor may cost ~8 bb/100 vs near-GTO. Caveat: duplicate-vs-GTOBaseline bb/100 has
  ±40 residual variance at 600 decks (the two strategies diverge into high-variance lines) → the per-spot multi-street
  GTO-gap (WS4, extending `floor_map`) is the sharper floor-quality instrument; also confirm with one large-N Slumbot run.
- **[2026-06-15 ✅ WS2 river advisor + a WS3 hand-off].** Built `extraction/build_river_data.py` +
  `train_river_advisor.py` from `_gto_river_cache` (293k rows / 1308 boards). The MLP beats the freq baseline by
  **+51%** (MSE 0.098→0.048) → `river_advisor.pt` saved + wired (`advisor.py` river file; `bot.py` river branch
  after `_river_exploit`). PAIRED floor effect: **river-advisor ON vs OFF = +38.6 ±15.6 bb/100 (~2.5σ)** vs
  GTOBaseline — a real river-leak fix (NOTES leak #4). Also made the exploit engine safe vs the now-strong floor:
  `_river_exploit` baseline is now the floor's ACTUAL action (`_river_floor_kind`), not a bare check, so it can't
  override a good floor bet with a worse one. **WS3 hand-off (from `exploit_proof`, −24 vs the over-folder):** the
  river engine fires **0×** vs the folder — a cold-start OFF-TREE EXPLORATION deadlock (can't learn a size's fold
  rate without betting it; the floor only ever bets GTO sizes, never the overbet cliff). The −24 is the OLD
  conf-driven overlay (`bluff_base`/MDF-shade via `self.opp`) betting non-cliff sizes, NOT the river engine. BOTH
  are exactly what WS3 fixes: merge the `ProbeController` (off-tree size-sweep → breaks the deadlock, re-enables the
  proven +28 cliff edge ON TOP of the strong floor) + replace the crude conf-overlay with the LCB-gated engine.

- **[2026-06-15 ✅ WS3 unify (one MVP)].** `PokerBot(exploit=True)` is now THE single MVP = solver-grounded floor
  (flop/turn/river advisors) + the exploit-primary river EV-engine + the conf-overlay + a NEW bounded,
  PREDICTION-GATED off-tree size **probe** (`_river_probe`): when the floor gives up an air hand AND an over-fold is
  already observed at a sampled river size, it occasionally bets an under-sampled LARGER size to map the fold-curve
  (discover a size-cliff), budget-capped (worst-case reserved vs a 120bb session budget → can't run away). This is
  the AdaptiveExploiter's probing idea ported in; the Dirichlet per-node model IS the calibration (it observes real
  fold rates per node). The standalone `AdaptiveExploiter` is kept as a labelled REFERENCE (interface differs; the
  scorecard measures `PokerBot` via `--hero mvp`). exploit_proof vs the synthetic cliff-only over-folder:
  **−7 ±24** (was −24; the probe explores + wins vs the over-folder, lifting exploit-primary to ≈floor — within
  noise, no regression). Honest: vs a pathological cliff-only folder (calls normal bets) principled play can't beat
  the strong floor without risky blind overbets the prediction gate correctly avoids; the exploit's real edge shows
  vs opponents that over-fold at NORMAL sizes (Slumbot folds 54% to 0.66) → measured in WS4. Fast-follow if WS4
  shows the flop/turn exploit needs it: port the TwoModelGate cross-confirm + the explicit Calibrator.

- **[2026-06-15 ✅ WS5 GTO Wizard harness ready-to-fire + ⚠ KEY MAY BE PRESENT].** Built `benchmark/gtowizard.py`
  = the pure, OFFLINE-UNIT-TESTED adapter (GameServiceResponse↔ActRequest: board parse, legal-dict, action+
  raise_range clamp, `PokerBotAgent`) + `config.GTOWIZARD_API_KEY` (read from `Secret keys\GTO Wizard API Key!.txt`,
  env override, never committed; `tools/` already gitignored). Self-test passes (preflop AKs→raise, flop QQ→check,
  river→call, all legal). **The key file now reads a 32-char no-space string (looks like a REAL key)** despite the
  user earlier saying it was empty → the requested key may have ARRIVED. Per "assume it never comes" + outward-facing
  /quota, NO live run was started. CONFIRM-ON-CLONE items before going live (need a real GameState): action_history
  verb format, hero-seat index, to_call derivation. To go live: clone `gtowizard-ai/researcher-api-client` under
  `tools/gtow_client/` (Python 3.13/uv), subclass `PokerBotAgent`, run `--num-hands 200` to validate, then ≥2500 for
  the AIVAT bb/100 + leaderboard = the DEFINITIVE measurement vs the true opponent.

- **[2026-06-15 UPDATE to the WS5 entry above] WENT LIVE -> `401 Unauthorized`.** The 32-char string in the key
  file is REJECTED by the API (placeholder / not-yet-granted; the user's "it's empty" was essentially right).
  Verified UP TO AUTH: client cloned + `uv sync` (Python 3.13 + deps); `gtowizard.py` REBUILT against the REAL
  schema (hero = the seat whose hole_cards is non-null, to_call = total_pot-common_pot, action_history `bX`/`_`
  parsing, SB=button, a legality guard so we never emit an illegal action, AIVAT+winnings per hand); secure runner
  `tools/gtow_run.py` (key from config, never logged) CONNECTS -> the clean 401 proves the wiring is correct.
  **Blocked only on a VALID key.** Then: `uv pip install treys torch numpy` into the client venv + register a
  `pokerbot` agent + `python tools/gtow_run.py --agent_type pokerbot --num_hands 2500` = the definitive AIVAT bb/100
  + leaderboard. Until a valid key exists, the KEY-FREE `scorecard.py` is the definitive measurement.

- **[2026-06-15 ✅ TexasSolver benchmark — gap + head-to-head].** Two "vs TexasSolver" measures (the local
  near-GTO stand-in while GTO Wizard is 401-blocked):
  (A) **Deterministic GTO-gap** (`floor_map` extended flop+turn+river): the MVP floor's action-kind divergence from
  the solver, 250 boards. **FLOP 31% gap** (frequencies MATCH: our-bet 47% vs GTO 47%, IP 75/74, OOP 22/22);
  **RIVER 29%** (our-bet 30% vs GTO 31%, OOP 18/18). Honest read: the FREQUENCIES match tightly (the GTO property);
  the ~30% per-hand gap is largely the solver's OWN mixing/indifference (a 50%-bet hand contributes 0.5 gap
  regardless), NOT a leak. TURN not locally measurable (local `_gto_bench_cache` is DUMP=1 flop-only; the DUMP=2
  turn subtrees were on the now-killed pod) — but the turn floor is advisor-grounded (+20% on the pod).
  (B) **Head-to-head bb/100** (`benchmark/gto_oracle_match.py`): MVP postflop vs a TexasSolver-DRIVEN oracle
  (PokerBot GTO preflop + live per-spot solves postflop; 40bb/SPR~7 + lean bet tree for speed; range-consistent SRP
  dealing). The oracle is genuinely solver-driven (0 floor-fallbacks in the smoke). Live solves → small NOISY
  samples (±~100+ bb/100) — a directional least-loss sanity (off-tree edge invisible, as vs GTO Wizard), NOT a
  precise number; the GTO-gap (A) is the precise measure. **Result: +184.6 ±132.9 bb/100 (n=50, oracle 134 decisions
  solver-driven, 0 fallbacks).** HONEST read: +184 vs *true* GTO is impossible — the oracle is APPROXIMATE GTO (full
  SRP ranges with NO continuation-narrowing → on turn/river it solves with too-wide ranges = mis-calibrated; + lean
  tree + iters=40 + 40bb), so our exploit-primary bot is EXPLOITING those approximations (the wrong turn/river
  ranges), not beating GTO; and ±133 = only ~1.4sigma (noise in play). So: "we crush an approximate-solver bot"
  (consistent with the thesis), NOT "we beat GTO". A truer head-to-head needs continuation-range propagation +
  richer solves (deferred, the hard part) → the number would regress toward break-even. The frequency-faithful
  GTO-gap (A) is the trustworthy "how close to GTO" signal.

- **[2026-06-15 ✅ DEFINITIVE TexasSolver head-to-head (PAIRED) — the MVP LOSES to solver play].** The n=50 UNPAIRED
  head-to-head (+184) was CARD VARIANCE. The PAIRED run (`gto_oracle_match.py`, 80 decks = 160 hands, card luck
  cancelled = the gate we trust) FLIPS THE SIGN: **MVP −160 +/- 75 bb/100** vs the solver-oracle (400 decisions
  solver-driven, 0 fallbacks). So the MVP LOSES to solver-grade play (~2sigma). HONEST: our floor matches solver
  FREQUENCIES (the GTO-gap 31%/29%) but loses full-hand bb/100 — the gap measures only bet-vs-check at the lead/cbet
  nodes; it does NOT capture SIZING / facing-bet DEFENSE / turn-river LINES, where the real EV leak sits. This
  reconciles WS1 (≈break-even vs the WEAK analytic GTOBaseline) with losing to the STRONGER actual solver + near-GTO
  Slumbot (−102): the floor's gap to true GTO is REAL + bigger than the analytic proxy showed. The edge is vs the
  EXPLOITABLE field (we crush); vs solver-grade play we LOSE → least-loss NOT yet achieved. Caveats: ±75 (~2sigma,
  loose magnitude); the lean-tree/40bb oracle is approximate (allin-heavy → may hit our allin-defense specifically →
  some inflation) BUT a weaker-than-true-GTO oracle means the true-GTO loss is >= this. NEXT high-leverage: close the
  facing-bet-defense / sizing / turn-river-line gap (the gap-match alone is not enough). Lesson re-confirmed: PAIR
  everything; the unpaired +184 was noise.

## Suspected leaks to review (ASSUMED, not yet measured — from the 2026-06-15 GTO-frontier consult)
These are hypothesized real leaks the consult (gpt-5.5 + o3, Claude-vetted) flagged. They are ASSUMED, not
measured — review each via the reach-weighted SOLVER EV-GAP once Move A makes the LBR trustworthy (Move B = the
EV-gap audit, Move C = river calibration, Move E = sizing/MDF audit). Do NOT fix on assumption; measure first.
1. **History-free floor averages incompatible info-sets** — the advisor conditions on board+hand features only,
   not line / SPR / position / range-asymmetry (K72r in BTN-vs-BB SRP ≠ in a 3-bet pot). Structural; the FIX
   (range/line-conditioned model) is the "add complexity" trap → MEASURE the cost (Move B), don't rebuild now.
2. **"Fold-equity-optimal sizing" ≠ EV-optimal** — max(folds) ≠ max(EV). Audit per-size solver-EV (Move E).
3. **MDF-shading may not be EV-grounded** — MDF is the wrong model vs underbluffers; is our bluffiness-shade
   EV-justified or a hand-wave? Verify, don't assume.
4. **River is heuristic, not solver-calibrated** (#40) — the most exactly-solvable street; calibrate (Move C).
5. **Advisor trained on P(bet)/action-match, not EV-gap** — can match frequency while bleeding on rare
   high-EV-gap nodes; the gate should be reach-weighted EV-gap, not MSE (Move B).
6. **Confidence-gated blend not provably globally safe** — local confidence ⇏ global low exploitability.
7. **Preflop 88.6% action-match** — the missing 11.4% could be low-EV indifference OR high-EV blunders; EV-gap
   audit needed (Move B).
8. **6-max independent-seat** — structural vs Pluribus-style joint reasoning; PARKED (not HU; consolidation phase).

## Exploit-primary crush-test #1 (2026-06-15) — right direction, NOT yet proven
First Slumbot crush-test of the exploit-primary river engine (`--exploit-primary`, seeded from slumbot_fold.json,
500 hands each, NO live-learning yet): **FLOOR −41.6 ±75.5 vs EXPLOIT-PRIMARY −26.4 ±79.4 bb/100, delta +15.2**
(in the predicted +8–15 corridor) — the engine fires + loses 15 bb/100 LESS than the floor. BUT: (a) both still
LOSE absolutely (Slumbot is near-GTO → ceiling ~break-even, no "crush"); (b) NOT significant — the unpaired delta
is ±~109 over 500 hands, and the floor alone swung −14.6 → −41.6 across runs (pure ±~80 variance). Encouraging,
unproven. Mechanism validated (safe-by-construction, fires correctly); the EDGE needs data. NEXT to make it
conclusive + grow it: (1) wire **live-learning** (`observe_hand_end` from the full hand history → the Dirichlet
model sharpens per-node during play instead of clinging to the thin n=8–39 seed); (2) run **2000–5000 hands** to
beat the ±noise. Re-probing Slumbot for a sharper fold-curve would also strengthen the seed.

## Exploit-primary LOUD proof (2026-06-15) — the engine's edge is per-SIZE / off-tree structure (PROVEN)
`pokerbot/benchmark/exploit_proof.py` (hero vs a parametric river over-folder, PAIRED decks, 1500 hands):
- vs a **FLAT** 70% over-folder: exploit-primary **+9 ±13** over the floor (NOT significant) — the heuristic floor
  already handles a flat leak.
- vs a **SIZE-CLIFF** folder (folds 20% to 0.5pot but 82% to overbets): exploit-primary **+28 ±11 (~2.5σ)**. The
  floor bets a FIXED heuristic size and cannot target the cliff; the engine LEARNS the per-size fold-curve and
  picks the max-fold (overbet) size.
**=> The engine's UNIQUE value is exploiting SIZE-STRUCTURE / off-tree mis-defense the floor's fixed-size heuristic
misses = the "killer cutoff" attack.** Slumbot's seed-curve already shows a rough cliff (0.66→54.5%, 2.0→62.5% vs
1.0→37.5%) = its abstraction artifacts → the engine should capture similar structure live. NEXT systematic step:
an ACTIVE off-tree size-sweep probe to map Slumbot's per-size cliffs finer than the 6-point seed, then hammer.

## Move A result (LBR falsification, 2026-06-15) — v1 eval unreliable; the paired A/B is the usable win
`pokerbot/benchmark/lbr_falsify.py` (300 hands, paired/duplicate) PROVED the v1 LBR is NOT a trustworthy
ABSOLUTE exploitability gate:
- **Range-blind** (uniform card re-sampling): injected c-bet-air / river-overbluff → paired-delta +123 / −31
  bb/100 (~0) despite firing 99/95 of 300 — the LBR can't see the corrupted RANGE.
- **Under-exploits** (passive-after-move): even an EXTREME over-folder is only +289 ±175 (fold-any-bet) /
  +323 ±175 (overfold-50) — directionally right (fold-response > range) but NOT 3σ at 300 hands.
- clean LBR +141 ±298 (was −487 pre-reseed; still within noise).
**Usable byproduct:** `lbr_bb100` now reseeds `g.rng` + the rollout RNG PER HAND → a PAIRED/DUPLICATE A/B
harness (same decks across bot versions → leak-free hands cancel) = a low-variance gate for a change's EFFECT.
**Use this as the change-gate now.** LBR v2 (Bayesian action-consistent range + multi-street best-response) is
the real ABSOLUTE-exploitability fix — DEFER until a change needs an absolute number (on consolidation phase,
don't build speculatively).
