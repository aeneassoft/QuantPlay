# THE RIVER SYSTEM — the focal point of the final architecture (2026-07-06)

> User thesis (confirmed + refined): the river is the decisive street. OpenAI consult
> (`data/research_sweep/openai_river_consult.json`) + web search + our own empirics. Compact CFR (Jackson 2016)
> is the RAM axis of this system.

## The thesis, honestly refined
The river is **terminal** (no more cards → EV purely via showdown/fold) → errors are irrecoverable,
correctness is maximally leveraged, and it is the street where a resource-limited builder gets close to
GTO the CHEAPEST (smallest state space, exact enumeration, solver in seconds). BUT **no magic eraser:**
NOT repairable by river play are (1) over-fold/over-call/stack-off BEFORE the river (hands that never
see the river), (2) pot size (you cannot retroactively grow the pot — SPR mismanagement),
(3) structural range damage (missing combos), (4) line incoherence that the opponent exploits BEFORE the
river. → River = best ROI per engineering hour, not absolution.

## THE BOTTLENECK (OpenAI, ranked — third independent confirmation)
1. **Range/belief quality that feeds the solve** — THE bottleneck (as in both prior consults).
2. **Coverage** (river boards × arrival lines × ranges — immense).
3. Exact-solve vs value-net tradeoff.
4. Per-solve latency — the LEAST important (river solves are fast). → NOT speed is the
   problem, but WHAT ranges we give the fast solver.

## The architecture (OpenAI recommendation = matches our roadmap)
**Short term (best EV/week): KEEP TexasSolver as the river engine + harden ranges + uint8 cache.**
NO pivot to exact LP or a pure river library now.
- **Range hardening** (Phase 1, highest lever): calibrate the tracker against GTOW river reveals (KL/cosine
  distance tight), both ranges line-conditioned.
- **River state cache**: key = (canonical board, line summary, coarse range hash), strategies stored **uint8-
  quantized** (Compact CFR: 16 bytes→1 byte; 256 levels ≪ solver noise). Reuse
  on repetition/similarity → latency limited to rare fresh nodes.
- **Medium term**: a small river CFV net ONLY as fallback for low-importance/time-critical nodes —
  NEVER the primary engine (Gate-0 proof + consult).

## THE POLARIZATION FIX (concrete precision lever, ~a few bb/100)
FINDING: our heuristic river bluffs exploit-driven (`bluff_p = 0.30 + conf·(fold_to_bet−0.5)` = opponent
fold rate), NOT polarized (bluff quantity coupled to value quantity via B/(P+B)). Vs the STATIC GTOW this is
a STRUCTURAL LEAK: we over-bluff where GTOW folds less, under-bluff where it folds more. OpenAI magnitude:
30-50% wrong bluff count ≈ 0.1-0.3 bb/hand per line cluster → aggregated a few bb/100 of our −20.
**FIX (pure precision, no behavioral lever):** in GTO mode do NOT overwrite the resolver output with the fold-rate
heuristic — the polarized frequency emerges correctly from CFR, IF ranges+utility are right.
Where we approximate (floor): anchor the bluff count explicitly to B/(P+B)·value quantity, then only a ±20% exploit tweak.
The `bluff_to_value_and_frequencies` formula (night fix B/(P+B)) is the bridge — it is DORMANT, wire it up.

## THE RIVER DIAGNOSTIC SCORE (your retrospective score, now specified)
Per river aggressor node: from the solve σ* mark the value quantity (EV_bet≥EV_check) and bluff quantity →
target frequencies V*_s, B*_s. Our policy π → observed V_s, B_s. Metrics per size: **miss_value**
(missed thin value), **over_value**, **ratio_error** (|B_s/V_s − B*_s/V*_s| = polarization deviation).
Defender side: overfold_rate / overcall_rate vs the indifference threshold h*. Aggregated by board class ×
line × position × size, weighted by pot/initial pot (EV impact). → Heatmap: WHERE we bleed (missed
value / mis-polarization / mis-bluffcatch). $0, deterministic, feeds corpus B.

## Verified techniques (citations checked; uncertain ones marked)
- **Sequence-form LP** — Koller/Megiddo/von Stengel, GEB 1996 (VERIFIED). Exact river solve + exact
  best-response gate (river small enough for exact LP → the exact exploitability gate that CLAUDE.md demands).
- **HULHE is Solved** — Bowling/Burch/Johanson/Tammelin, Science 2015 (VERIFIED). Endgame resolving.
- **Compact CFR** — Jackson 2016 AAAI workshop (WE OWN it; OpenAI wrongly advised "2021"). uint8 = the
  RAM axis of the river cache/library.
- Blocker/card removal exact — Johanson thesis 2013 (VERIFY sections; we already enumerate the river exactly).
- Accelerating Best-Response — Johanson/Waugh/Bowling/Zinkevich, IJCAI 2011 (VERIFY).

## Into the plan (roadmap placement)
Phase 1 (range truth) IS the river-bottleneck fix. NEWLY queued: polarization fix (precision, GTO mode,
buildable immediately) + river diagnostic score (measurement before every river lever) + uint8 river cache (Compact CFR).
The river CFV net is the FIRST patch-net candidate (Supremus river-first), but subordinate — after
range truth, as a narrow fallback, not as the engine.

## PARAMETRIC RANGE WAVE — the concrete method for range calibration (User + Brokos, 2026-07-06)
Source: Brokos "Play Optimal Poker 2: Range Construction" (p.4): river ranges are polarized/condensed
(clean 1D waves over strength); BEFORE the river ranges evolve with the future card ("hands change
value") = NO static wave → the mathematical reason for the street doctrine.
**METHOD (Phase 1, river first):** Represent the river range as a SMOOTH POLARIZED FUNCTION
(axes: strength × blocker dimension, polarization degree, value/bluff/medium masses) instead of 1326 free
weights → a SMOOTHNESS PRIOR regularizes the reconstruction (can no longer become overconfidently jagged
= attacks the "confident-wrong" source) → calibrate against GTOW reveals → optimize JOINTLY with the
bet-frequency wave ("harmony" = polarization consistency = the B/(P+B) fix as wave co-optimization).
**LIMITS (honestly):** (a) 1D strength loses blocker info → at least 2 axes (strength+blocker), otherwise
suit aliasing; (b) TURN/FLOP: the range evolves with the card → a static wave is incomplete, would need the
range wave as a function of the future card (harder). (c) Smoothness gain vs blocker loss = EMPIRICAL,
measurable via reveal data. Strongest on the river (Brokos: clean waves there) = exactly the focus.
