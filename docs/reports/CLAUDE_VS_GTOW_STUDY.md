# Claude-Code-vs-GTOW thought_log study — grading 264 decisions against ground truth

**Date:** 2026-06-21 · **Data:** `data/claude_play/thought_log.jsonl` (264 decisions / 91 hands) +
`data/sessions/gtow_hands_1781997096.jsonl` (100 hands). **Code:** `research/study_grade.py` (reconstruct + grade),
`research/study_analyze.py` (leaks/edges + AIVAT), `research/study_review.py` (OpenAI 2nd-opinion),
`research/study_distill.py` (close the loop). **Plan:** `.claude/plans/gut-dann-sind-wir-toasty-forest.md`.

---

## §0 — TL;DR (the verdict)

Claude Code drove the engine for 100 hands vs GTO Wizard (HU 200bb), scoring **AIVAT −38.41 ± 22.48 bb/100** (RAW
+16.93). Grading every decision against TexasSolver (postflop, 98.8% coverage) + the near-Nash blueprint (preflop) +
equity-math, with an independent OpenAI (gpt-5.x) 2nd-opinion on the 33 hardest spots, three independent methods CONVERGE:

1. **The decisions were strong.** 252/262 scored decisions were in GTO support (**96.2%**); preflop was **95% pure-GTO**;
   OpenAI independently agreed with **82%** of the hardest/most-disputed actions, and every disagreement it priced at
   **≤ 1.2 bb**. There is no large decision leak.
2. **The −38 headline is dominated by VARIANCE / coolers, not leaks.** 90% of the AIVAT loss is on hands that reached the
   river (mean −93 bb/100, n=37), concentrated in strong-hand / big-pot spots (made-hand "strong" hands averaged −606,
   n=8; 30–100bb pots −264, n=3) — i.e. losing big WITH good hands (getting coolered), which the deterministic grade rates
   GTO-fine. n=100 is far too small to call this a leak.
3. **The one real (small) leak: postflop OVER-CHECKING (under-betting), flop + turn.** My single most-frequent GTO
   deviation is the `check` action (mean P(gto)=0.41 — I check in spots GTO bets ~59% of the time), driven by
   under-semibluffing draws / weak hands on the flop (sumDev 35.0) and turn (28.1). The deterministic grade and OpenAI
   (its top EV-costs are exactly these flop/turn semibluff spots, +0.5..+1.2bb) **agree exactly**.

**The single highest-value finding is a HARNESS BUG, not a strategy leak:** the live `gtow_to_state` adapter logged the
preflop `to_call` (hence `required_equity`) as the WHOLE pot in **100% of preflop facing-bet spots** (mean +0.22 too
high; e.g. 0.50 shown when the truth was 0.28). This is a prime co-cause of the documented GLM preflop over-fold and
explains WHY blueprint-routing fixed it (the blueprint bypasses the bad input). **Fixed + regression-locked** in
`pokerbot/benchmark/gtowizard.py`; an A/B is recommended to measure the GLM lift.

---

## §1 — Method + honesty

- **Deterministic-first.** Each decision is graded against an OBJECTIVE oracle: preflop → the stored near-Nash blueprint
  (`features.preflop_blueprint`, free); postflop → `api.solve_node` (TexasSolver, line-aware ranges via
  `POKERB_LINE_RANGES=1` — strictly more correct offline) + an equity-math fallback when the solver returns None. This
  per-decision grade is the PRIMARY signal because it is noise-free.
- **GTOW cannot grade spots.** The GTOW API only plays hands; it gives no per-spot solver access. So AIVAT is a per-HAND,
  n=100 (±22.48) signal used ONLY to corroborate — never as the per-decision grade.
- **Independent 2nd-opinion = OpenAI**, not Claude: the log is Claude's own reasoning, so a Claude self-review is biased.
- **bb=100** throughout (`research/gtow_xray.py` convention; NOT the `analyze_gtow_hands.py` bb=50 2× bug).
- **Reconstruction is exact: 264/264 (100%)** rebuilt from the session betting line via `slumbot.build_state` →
  `spot_from_slumbot`, checksummed on pot + street (NOT on the logged to_call — see §1a).
- **Solver coverage (postflop): 160/162 = 98.8%** (flop 67/69, turn/river ~100%). The deep 3-street flop tree (~76s/solve)
  timed out under the first parallel pass; a targeted re-grade (`--stage regrade`, solve_threads=6) recovered 62/64. Only
  2 spots remain math_fallback-only.
- A per-bucket "+" vs GTOW is noise, never an edge (nobody beats GTOW; best public −3.14). The distilled gold (§6) is a
  warm-start, NOT a lift above my own play.

### §1a — The decision-time INPUT AUDIT (a load-bearing confound)
Because the live `gtow_to_state` path computed `to_call = total_pot − common_pot`, the math I SAW while playing could be
wrong. Auditing the logged vs the reconstructed-true values:

| street | facing-bet spots | required_equity INFLATED | mean gap |
|--------|------------------|--------------------------|----------|
| preflop | 102 | **102 (100%)** | **+0.221** |
| flop | 17 | 0 (0%) | +0.000 |
| turn | 10 | 0 (0%) | +0.000 |
| river | 11 | 3 (27%) | +0.034 |

The bug is **preflop-only** (GTOW's `common_pot` excludes the blinds during active preflop betting → `to_call` = whole
pot). 24 of 38 facing-bet folds were made on an inflated `required_equity` (all preflop). **But I rarely followed it:**
my reasoning cited the inflated number only 5/140 times — preflop I deferred to the blueprint, so my own play was
unharmed (preflop AIVAT −1.0, essentially break-even). A brain that reasons from `required_equity` (the untrained GLM)
would over-fold catastrophically — which is exactly the −41 bb/hand GLM preflop leak. **Fix in §5/§6.**

---

## §2 — Deterministic leak-ranking (the primary signal)

Grade buckets (264): **pure_gto 159, mixed_ok 93, minor_dev 9, blunder 1, unscored 2.** Of 262 scored:
**252 in-support (96.2%)**, 10 out-of-support deviations.

**By street (sumDev = summed deviation from GTO = where I deviate most):**

| street | n | scored | mean P(gto) | sumDev | out-of-support |
|--------|---|--------|-------------|--------|----------------|
| flop | 69 | 67 | **0.48** | **35.0** | 4 |
| turn | 51 | 51 | **0.45** | **28.1** | 5 |
| river | 42 | 42 | 0.70 | 12.6 | 0 |
| preflop | 102 | 102 | **0.89** | 10.8 | 1 |

**By action — the leak is the PASSIVE side:** `check` mean P(gto)=**0.41**, sumDev **52.3** (by far the biggest deviation;
6 out-of-support), vs `raise` 0.89, `fold` 0.84, `call` 0.79, `bet` 0.68. **I systematically over-check / under-bet
postflop.** By hand-strength the deviation concentrates on `weak` (P=0.39) and `air` (0.52) hands — i.e. the bluff/
semibluff side I decline to fire.

**The leak, concretely — under-betting draws & weak hands (check where the solver bets):**

| seq | street | spot | my hand | solver | my action |
|-----|--------|------|---------|--------|-----------|
| 147 | flop | 2d4d4s (paired) | 65o (gutshot+BDFD) | bet | check |
| 257 | flop | 9h4dKh | 42s (bottom pair) | bet | check |
| 139 | turn | 3sKcJcTd | 6c2c (club FD, ~26%) | bet 1.00 | check |
| 45 | turn | QhQc7cJd | Td9d (OESD, 8 outs) | bet 0.98 | check ("don't donk OOP") |

I realize draws cheaply / refuse to donk OOP; GTO bets them (value-denial + semibluff). The DIRECTION is real (too
passive); the MAGNITUDE (bet ~100%) is likely overstated by the lean 1–2-size solver tree — reported honestly.

**EDGES (where I'm solid):** preflop blueprint discipline (95% pure-GTO, immune to the §1a bug), 3bet/raise lines (0.89),
disciplined folds (0.84), value-calls (0.79). 159/262 scored decisions are pure-GTO (P≥0.70); 3bet/4bet pots are clean
(0.83/0.95, 0 out-of-support).

---

## §3 — AIVAT corroboration (hand-level, n=100, ±22.48 — corroboration only)

`research/gtow_xray.py`:

- **By final street:** river −93.4 (contribution **−34.6**, n=37), turn −27.2 (−2.4), flop −10.8 (−1.0), preflop −1.0
  (−0.4). **90% of the loss is on river-final hands.**
- **By preflop outcome:** postflop hands −69.0 (n=55, the whole loss); preflop WON/LOST ≈ 0 (preflop is break-even —
  corroborates §1a: the input bug did NOT hurt my play).
- **By largest bet:** the loss sits in the bigger pots (30–100bb: −264, n=3; 3–10bb: −151, n=17) — small-n, high-variance.

**Consistency check:** the biggest-DEVIATION streets (flop/turn over-checking) are NOT the biggest-LOSS street (river).
The river loss comes with strong hands graded GTO-fine (made-hand "strong" −606 over n=8) → **coolers/variance, not a
leak.** Conversely the flop/turn over-checking is a real GTO deviation that cost almost nothing in this sample (flop −1.0,
turn −2.4) — a leak the deterministic grade catches but AIVAT can't, at n=100. This is exactly why the deterministic grade
leads and AIVAT only corroborates.

---

## §4 — Independent OpenAI review (gpt-5.x, 33 hardest/disputed spots)

`research/study_review.py` (cost ~$0.07 — far under the ~$4 budget; gpt-5.x with a tight schema is cheap):

- **Agrees with my action: 27/33 (82%).** Every disagreement priced ≤ 1.2 bb. The top-EV disagreements are the SAME
  flop/turn under-betting spots §2 found → **two independent methods converge** on the one real leak.
- **Reasoning sound: 16/33 (48%).** ★ **11 spots: ACTION OK but REASONING UNSOUND** — the key blind-spot signal. Even
  when I picked the GTO action, my stated logic was sometimes off (dominant cause: `wrong_range_read` ×8). My
  DECISION-making is stronger than my VERBALIZED reasoning.
- The one preflop blunder (seq28): I overrode the blueprint's 97%-call citing "size-blind"; OpenAI confirms the solver
  already accounts for the 2.8× open and still defends → my override was wrong (a rare case of distrusting the blueprint).

---

## §5 — Root-cause taxonomy (my-error vs engine/harness-artifact)

| # | finding | EV | whose error | status |
|---|---------|----|----|--------|
| 1 | **Preflop `required_equity` inflation** (100% preflop facing-bet, +0.22) | large for equity-reasoning brains (GLM −41/hand); ~0 for me (blueprint-deferral) | **HARNESS bug** (`gtow_to_state`) | **FIXED + locked (§6)**; A/B recommended |
| 2 | Postflop over-checking / under-betting (flop+turn semibluffs) | small (≤1.2 bb/spot), the top deterministic + OpenAI leak | MY leak (too passive) | train/awareness; honestly lean-tree-amplified |
| 3 | Reasoning range-read imprecision (11 spots) | ~0 (action still GTO) | MY leak (verbalization) | distill keeps the right ACTION, gated |
| 4 | River / big-pot losses (the −38 headline) | the bulk of AIVAT | **VARIANCE / coolers** (n=37 river, n=3 big pots) | NOT a leak — n too small |
| 5 | Preflop blueprint override (seq28) | tiny (1 spot) | MY leak (over-rode a correct blueprint) | trust the blueprint on sizing |

---

## §6 — The closed loop (distilled gold + fixes + next A/Bs)

- **Distilled teacher gold:** `research/study_distill.py` takes every graded-clean decision (recon_ok + GTO-supported +
  math-OK; decisions whose reasoning cited the inflated `required_equity` are EXCLUDED), rebuilds the corrected spot, and
  emits it in the existing teacher format (`frontier_loop.to_example` → `# reasoning\ndecide(...)`), forcing each through
  the deterministic EV-truth gate (`EVFilter` G1–G6). Output: `dataset/shards/claude_study.jsonl` (**243 rows**; 245
  candidates, 2 dups, 0 illegal, 0 EV-rejected; action-mix check 34 / call 23 / raise 16 / bet 14 / fold 13, balanced
  across streets), registered as `sft_gold` (`registry.shard.claude_study`) so the next re-SFT picks it up. Honest cap:
  warm-start, not a lift.
- **Engine fix shipped (correctness, verified):** the `gtow_to_state` `to_call` now uses the committed-delta
  `max(0, max(c_h,c_v) − c_h)` (correct on every street; postflop a no-op). Regression-locked in the `gtowizard._selftest`
  (BB-vs-open=125 not 325; SB-open=50 not 0). The AIVAT measurements themselves were always GTOW-computed and correct;
  the bug degraded the brain's INPUTS (→ worse play), so the fix should LIFT future play.
- **Next grounded A/Bs:** (a) **DONE (2026-06-21) — the to_call fix paired A/B (n=500/arm, made-hand ON both, GLM drove
  preflop itself): OFF (bug) −40.40 ± 12.83 → ON (fix) −28.36 ± 10.11** = a suggestive **+12 bb/100**, and the ON arm is
  the **best GLM-vs-GTOW number ever** (+15 over the protected −43.30, = Claude's −28.55). Mechanistically clean, but the
  paired Δ is only ~0.7σ (arms overlap) → a **~1500/arm run is needed to confirm at ≥2σ**. (`infra/gtow_glm_pod.py
  --ab-tocall`; output `data/gtow_glm_ab_tocall.txt`.) (b) Re-SFT including `claude_study.jsonl` → paired GTOW A/B vs the
  protected −43.30. (c) Optional: a richer postflop solver bet-tree to test whether the flop/turn under-betting leak (§2)
  is real or lean-tree-amplified, before training it in.

---

## §7 — Open questions / deferred

- **n=100 is too small** to separate the river/big-pot loss (§3) from a subtle river leak; the deterministic grade says
  "fine," but a larger paired run (the duplicate harness) would settle it.
- The flop/turn under-betting leak's MAGNITUDE depends on the solver bet-tree richness — flagged, not yet trained in.
- The `gtow_to_state` fix's play-impact is UNMEASURED until the recommended A/B (it is a verified correctness fix, so
  shipping it is safe regardless).
- 2 postflop spots remain solver-uncovered (off-tree / hand-not-in-range) — graded by equity-math only; immaterial.
