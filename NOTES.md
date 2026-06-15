# NOTES — in-repo notes & deferred-precision log

A running, in-repo log of OPEN QUESTIONS, DEFERRED PRECISION items, and "good-enough-now, compute-exactly-later"
decisions. Distinct from the cross-session auto-memory (`C:\Users\hampe\.claude\projects\...\memory\`). Add an
entry whenever we ship a heuristic/approximation that should later be replaced by an exact/measured value.
Referenced from `CLAUDE.md`.

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
- **[2026-06-15 ⚠ theory-only] River blocker nudges (#40).** `bot.py:_river_blocker_signal` biases river bluff
  SELECTION (frequency-preserving) + nudges the bluffcatch threshold ±6% by how much hero blocks villain's VALUE
  vs AIR combos. The DIRECTION is GTO-canonical (blocker theory) but the magnitudes (0.06 thresh, 0.6 freq factor,
  the 3500 "value" rank bar) are NOT solver-calibrated — there is no river (DUMP=3) cache yet. Calibrate against a
  targeted DUMP=3 river batch later; safe-by-construction until then (selection bias + tiny nudge can't spew).

## Open questions
- **[2026-06-15] Run 2 duplicate watch.** The OOP-donk cap (`oop_donk_freq`) improved the solver-gap (the
  primary gate) but the duplicate-vs-GTOBaseline point moved −1.4 → −34 ±105 bb/100 (within noise, no disaster).
  Verify at scale (≥600 decks), AND check whether checking-more-OOP exposes a DOWNSTREAM leak vs the aggressor's
  c-bet (the flop-only solver-gap can't see that) — i.e. is our facing-c-bet defense after checking OOP sound?
  Knob: `PokerBot.oop_donk_freq` (currently 0.5 → ~25% donk; lower to approach GTO 20%).

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
