# TIE GTOW — the final analysis (2026-07-04)

**The goal (user, explicit): TIE GTO Wizard (0 bb/100 AIVAT) with OUR ENGINE — no LLM, no pod.**
Honest framing up front: nobody on the visible GTOW leaderboard ties (best −3.14; frontier LLMs −8/−9). Tie is
beyond published SOTA. But the ledger below shows the arithmetic is NOT absurd — the engine's body is already
−8…−11, and the gap decomposes into NAMED, individually-fixable pieces. We measure our way there; we don't promise it.

## 1. Where we actually stand (all measured 2026-07-04, all free/deterministic)

| Metric | Value | Source |
|---|---|---|
| Live AIVAT vs GTOW (HEAD default) | **−20.09 ± 7.18** (n=974) | fresh run, `gtow_hands_1783177274.jsonl` |
| Body (5% / 10% trim) | **−11.1 / −8.0** | `gtow_tail` — 0 catastrophes, worst hand −26bb |
| Per-decision EV-loss (Analyzer, HU n=1500) | **19.33 bb/100** | GTO-score 53.4%, Freq-Diff 54.6% |
| Cross-check | 19.33 ≈ 20.09 → **the gap is real deviation cost, not luck** | two independent methods |
| 6-max tag core (reference) | 85.9% GTO-score, 7.61 bb/100 EV-loss | the exploit-light core is far more GTO-true |

The stale −47.18 was an account aggregate over dead code eras. Preflop is near-solved (−1.6 of −20). The whole gap
is postflop: flop −8.3 + river −8.6 + turn −1.6 (xray contributions).

## 2. The gap, decomposed to the bb (the tie-ledger)

The 19.33 bb/100 per-decision loss splits into **concentrated** (25 hands with EV-loss ≥2bb = 8.60 bb/100, 45%)
and **spread** (≈10.7 bb/100, 55% — thousands of small frequency deviations = the Freq-Diff 54.6% = the
exploit-primary engine deviating from GTO frequencies BY DESIGN).

Concentrated, by leak class (from `data/gtow_grades/hu_leaks_ev2.json`, per-decision grades):

| # | Leak class | n | bb/100 | The fix (all engine-side) |
|---|---|---|---|---|
| L1 | **BB/SB flop over-fold vs c-bet** (folds TOP PAIR: Kd6s on KcTs5h!) | 9 | **2.91** | defense-advisor / MDF calibration facing c-bets — NOT yet in the GTOW-mode |
| L2 | **River over-aggression** (thin bets/raises: J2o bet, Qs8s raise) | 5 | **1.58** | exploit-OFF + river guards (IN the mode) |
| L3 | C-bet-then-fold (bet flop, fold to raise w/ equity) | 2 | 1.33 | facing-raise defense (same family as L1) |
| L4 | River under-bet (missed value: X:BLUNDER) | 3 | 0.98 | `POKERB_RIVER_VALUE` floor (IN the mode) |
| L5 | River other | 2 | 0.95 | mode river package |
| L6 | Preflop 4bet-call/jam | 2 | 0.53 | jam-discipline / corset |
| L7 | Turn + other | 2 | 0.31 | — |
| **Σ concentrated** | | 25 | **8.60** | |
| S | **Spread frequency deviation** (Freq-Diff 54.6%) | ~800 small | **≈10.7** | **`POKERB_GTO_MODE` exploit-OFF** — the wholesale lever |

(6-max for reference: only 9 costly hands = 4.64 of 7.61 bb/100; worst = AsQh 4bet −34bb turn stack-off; 4/9 =
squeeze-pot preflop — separate 6-max fix list, `LEAK_MAP.md`.)

## 3. The path to 0 (staged, each stage measured before the next)

- **T1 (DONE, $0): the GTOW-mode grade — RESULT: metrics SPLIT, hypothesis REFUTED.** `hu_gtomode_1500.txt` (seed 55,
  exploit OFF + census tree + tracker damp + river guards) graded → **GTO-Score 49.8% (↓3.6pp), EV-loss 17.05 bb/100
  (↓2.28 — BETTER), Freq-Diff 54.57% (FLAT)**. The gate ("score must jump toward 85%, Freq-Diff must fall") FAILED —
  **exploit-OFF did not move the frequency deviation → it is INTRINSIC to the engine core, not the exploit overlay**
  (the T1 diagnosis the plan asked for). The score DROP is fully traced to the **SB limp-clamp** folding hands GTOW
  plays (75o/85o/A9o…) at ~0.1bb each = cheap frequency-blunders that tank the score but not EV; meanwhile postflop
  exploit-OFF recovered real EV (net EV-loss ↓). **So the mode is a net EV improvement mis-read as a regression by the
  score metric.** Fix built (`bot.py:243` limp→open, not open/fold split); paired seed-55 re-grades staged. LESSON:
  **track EV-loss (money, cross-checks to AIVAT), not GTO-score (frequency-match, inflated by cheap SB folds).**
- **T2 ($0 + code): the L1 fix — BB flop defense.** The single biggest named leak (2.91 + the L3 family 1.33).
  Calibrate `advisor.p_defense`/the MDF-facing-cbet thresholds so top-pair+ NEVER folds to a single c-bet; verify
  on the 9 recorded hands (deterministic replay: same spots must now continue), then a fresh graded export.
- **T3 ($0): re-grade + iterate.** New export → Analyzer → new leak-map. Repeat T2-style targeted fixes on whatever
  the map names next (the loop: grade → fix the named leak → re-grade; each iteration is ~1h + free).
- **T4 (free, wall-clock): the AIVAT confirmations.** The mode vs HEAD interleaved A/B (`research/gtow_ab.py`,
  n=2500/arm, key #2) gated vs **−20.09**. Then the scale-up: a TIE CLAIM (0 within 2σ) needs SE≈2 → **n≈12,000
  hands** (free, ~10–20h wall-clock, pre-registered) — feasible, just patient.

**Arithmetic best case:** 19.3 − (S recovered, say 70% = 7.5) − (L1+L3 = 4.2) − (L2+L4+L5 via mode = 3.5) −
(L6 = 0.5) ≈ **3.6 bb/100 residual** → the leaderboard-top region, knocking on tie. Honest discount: exploit-OFF
won't recover 100% of S (the tag core still loses 7.61 per-decision — engine frequencies are imperfect even without
exploit), and per-decision EV-loss ≠ exactly realized AIVAT. **Central expectation after T1–T3: −5…−10 AIVAT;
tie requires the T3 loop to keep converging.** Every claim gets the honesty gates (no "+", body must move,
pre-registered n).

## 4. Standing instruments (all free, all repeatable)
- Generate: `research/pokerstars_export.py` (HU) / `research/sixmax_export.py` (6-max) — hero = the LIVE config
  (parity); `POKERB_GTO_MODE=1` env; both resolvers OFF for speed (`POKERB_RESOLVER=0 POKERB_TURN_RESOLVER=0`).
- Grade: GTOW Analyzer upload (Chrome) → Stats read via get_page_text → costly hands via the safe XHR
  response-capture (`items[]`, per-move `actions_with_correctness_*`) → `data/gtow_grades/*.json`.
- Live: `tools/gtow_client --agent-type pokerbot` from the PC (free) + `gtow_xray`/`gtow_tail` decomposition;
  A/B via `research/gtow_ab.py`.
