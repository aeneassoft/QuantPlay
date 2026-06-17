# GTO leak ladder + one-go engine-fit plan (2026-06-15)

**Frame (the user's standing goal): make the conceived ENGINE run coherently — bring the existing parts into
dynamic harmony. So leaks are split into MISFITS (parts exist but don't yet mesh → cheap to fit, close now) vs
MISSING (parts don't exist → rebuilds, DEFER; adding them = the complexity we avoid).**

## Honest measurement caveat (read first)
- We can quantify HU vs solver; **6-max "vs 100% GTO" is undefined** (proven: PPAD-hard, non-unique, no scalar
  exploitability — `docs/solvability_proof_gpt55.md`).
- Our **LBR is vacuous** (Move A) → no trustworthy absolute exploitability number. The **paired/duplicate A/B**
  (built in Move A) is the working change-gate; **frequency-gap** (floor_map) + **held-out MSE** + **Slumbot
  bb/100** are our measured anchors.
- The local cache has **NO per-action EVs** → exact EV-gap must be DERIVED (not a free lookup). So the bb/100
  figures below are **MEAS** (measured anchor) or **EST** (consult expert magnitude, `docs/frontier_*`), labeled.
  EST values are independent expert priors — **they do NOT simply sum**, and they are vs a true best-response,
  not vs Slumbot. The only hard aggregate is Slumbot floor **−14.6 ±82 bb/100 (≈break-even)**; since Slumbot is
  not a BR, true HU-floor exploitability is **≥** that (consult budget: "several to 10+ bb/100").

## The ladder (HU first — Slumbot is HU — ranked by EV-cost × confidence / effort)

| # | Leak | Scope | Mismatch | Conf | Type | Fit |
|---|------|-------|----------|------|------|-----|
| **L1** | "Fold-equity-optimal" sizing ≠ EV-optimal (max folds ≠ max EV) | HU | **EST 3–8 bb/100** | Med | MISFIT | pick EV-optimal over discrete sizes (fold-curve × equity), drop FE-only |
| **L2** | River still heuristic, not solver-calibrated (#40 magnitudes) | HU | **EST 3–8 bb/100** | Med | MISFIT* (needs river data) | calibrate blocker nudges vs solver river sub-strategies |
| **L3** | MDF-shading not EV-grounded (torches EV vs under-bluffers) | HU | **EST 2–5 bb/100** | Med | MISFIT | bluffcatch = pot-odds/EV vs the bot's existing villain-range estimate |
| **L4** | Advisor trained on P(bet)/action-match, not EV-gap | HU | MEAS MSE good (+43% flop/+20% turn); residual **EST 1–4 bb/100** (high-EV-gap tail) | Med | MISFIT | reach×EV-gap-weighted retrain |
| **L5** | Preflop 88.6% action-match → 11.4% could hide high-EV blunders | HU | **MEAS 11.4% miss**; EV **EST 1–3 bb/100** | Low-Med | MISFIT | preflop EV-gap audit, patch the blunder buckets |
| **L6** | Monte-Carlo equity noise flips close flop/turn decisions | HU | **EST 0.5–2 bb/100** | Low | MISFIT | exact turn enumeration where the CI crosses a decision threshold (river already exact) |
| **L7** | Confidence-gated blend not provably globally safe (local conf ⇏ global) | HU | **EST 0–2 bb/100** (floor) | Low | caveat | LCB-gated safe-exploit framing (post-eval) |
| **L8** | IP flop c-bet over-frequency (was 87%) | HU | **MEAS +13pp → ~0** after advisor (75%≈GTO) | High | **MESHED ✓** (#39) | done — just verify it holds |
| **—** | **Eval blindness: LBR vacuous** | meta | Move A: cannot bound | High | MISSING (mitigated) | LBR v2 deferred; paired A/B is the gate |
| **L9** | 6-max independent-seat (no joint public belief) | 6max | undefined vs GTO; "very high" vs competent bots, ~0 vs current field | — | MISSING | card-consistent joint-belief — **DEFER** |
| **L10** | Exploit overlay externality-blind ("who captures the leak?") | 6max | **EST** moderate multiway | Low | MISSING | externality-aware exploit — **DEFER** |

\* L2 is conceptually a mesh, but the local turn/river solver data is gone (pod killed) → needs a small targeted
river solve to calibrate exactly; until then it stays safe-by-construction (the #40 nudge can't spew).

## The one-go ENGINE-FIT plan (mesh the MISFITS, DEFER the MISSING)
**Reality check (honest):** "close ALL vs 100% GTO in one go" is NOT achievable — L9/L10 are rebuilds, 6-max GTO
is undefined, L2 needs absent river data, exact EV-gap needs EV-derivation. What IS achievable in one batch =
**mesh the HU misfits (L1, L3, L4, L5, L6) into dynamic harmony, each GATED, then the Slumbot run.** That is the
engine running coherently — the actual goal.

- **Phase 0 — the gate (so every fix is measured, not guessed):** use the **paired/duplicate A/B** (done) +
  **floor_map frequency-gap** as the gate. Derive per-action EV only where essential (L1 sizing). Discipline:
  keep a fix ONLY if the gate shows improvement; **revert otherwise** (the thin-value / draw-c-bet lesson).
- **Phase 1 — mesh the misfits (one batch, priority L1→L6, each gated):**
  1. **L1 sizing** → EV-optimal discrete size from the fold-curve × equity (replace FE-only).
  2. **L3 MDF** → pot-odds/EV bluffcatch against the existing villain-range estimate (mesh `_villain_range`).
  3. **L4 advisor** → reach×EV-gap-weighted retrain (needs EV-derivation; else keep + flag).
  4. **L5 preflop** → EV-gap audit of the table; patch the high-gap buckets.
  5. **L6 MC** → exact turn enumeration where a decision is CI-marginal.
  6. **L2 river** → calibrate the blocker nudges IF a small targeted river solve is run; else leave safe.
- **Phase 2 — validate:** the final **Slumbot run** (floor + exploit) on the meshed engine + a floor_map refresh
  + the paired-eval delta. This is the "letzter Run gegen Slumbot."
- **DEFER (the MISSING parts — adding them is the forbidden complexity, not now):** L9 joint-belief 6-max,
  L10 externality-exploit, LBR v2, the range/line/SPR-conditioned floor, the river-solve cache.

## Bottom line
The engine's **HU floor parts already exist** — the leaks are mostly **misfits** (FE-sizing not meshed with EV,
MDF not meshed with the range estimate, the advisor not meshed with EV-gap). Fitting those is the "one-go"
batch. The **missing** parts (joint belief, externality exploit, real LBR) are genuine rebuilds — deferred by
design, not closeable in one go without the complexity we're avoiding.
