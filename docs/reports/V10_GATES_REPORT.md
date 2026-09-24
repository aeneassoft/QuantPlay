# V10 GATES REPORT — synthesis of the gate runners G1–G5 (2026-09-07/08)

**Purpose:** one page that carries the ship decision for v10 ("river foundation", `../plans/V10_BUILD_CARD.md`).
Every number carries its source (file + command). No strategy code was changed by the gate runners;
no git commits. Measurement window: 2026-09-07 22:00 → 2026-09-08 01:41.

**Arms:** A = v5-H (`r8_stack`, PRINCE, exploit OFF, TexasSolver ON) · B = v10 (`r10_stack` = K1 hero range +
K2 public river plan instead of `river_gpu_guard`). Channel vocabulary (card E2): **Gym** = pargate channel
(exploit ON, no PRINCE, resolver OFF) = integrity/non-regression bound, NEVER ship evidence;
**Live** = PRINCE + resolver ON = the GTOW channel.

---

## 1. Gate table

| Gate | Status | Metric (measured) | Threshold (card) | Source (file · command) |
|---|---|---|---|---|
| **G1** Invariants/tests | **GREEN (evidence composed)** | 13 test/smoke blocks, all exit 0: hero_range 19/19 (Σ=1 ≤1e-6, invariance, guard transformation vs enumeration ≤1e-6), river_plan 27/28 (1 skipped: latency hard limit due to foreign GPU load), runtime_config 19 OK (1 skip "E5 NICHT LIVE"), gtow_nacht_v10 31/31, river_strategy_identity 20/20, integration_v10 4/4, contracts 250 green, game/bot/range_tracker/math_suite 20/20 OK; HU app smoke v5-H green + misconfiguration gate v10-on-r8 aborts correctly (exit 1); golden set r8 vs basis pre == post (IDENTICAL). **K3 controls** (matching pennies / card fixture ≤1e-6 / A/A exactly 0 / oracle identity 60/60) **15/15 green** | all green; pytest command executable | `data/runs/v10/G1_tests.txt` (blocks `### …`) · `python -u -m research.g1_gate_runner`; K3 controls from `data/runs/v10/g4_logs/kontrollen_tests.log` (22:15:13) · `python -u -m tests.test_river_br_pruefstand`. **Gap:** the G1 runner did NOT write the block `test_river_br_pruefstand` (log ends at test_river_plan 22:14:36; `G1_summary.json` missing) — the evidence comes from the G4 run of the same code version. `python -m pytest …` → exit 1 "No module named pytest" (substitute: module runner, identical test scope) |
| **G2a** A/A + golden after code change | **PASSED** | pargate A/A r10 vs r10, **576 decks: bb100 0.0, se 0.0, nonzero 0/576** (bank 1090000, 212.9 s); golden A/A 40 decks nonzero 0; r8-vs-basis pre == post_g2a IDENTICAL; trace: k1_fallback 0/4, k1_likelihood 4/4 | A/A EXACTLY 0; golden identical | `data/runs/20260907_220348_pargate_r10_stack/{result,config,edges}.json` · `python -u -m pokerbot.autogym.pargate --kandidat r10_stack --incumbent r10_stack --decks 600 --workers 12 --seed 1 --deck-seed0 1090000`; `data/runs/v10/golden_r10_AA_v2.json`, `golden_r8_vs_basis_post_g2a.json`, `G2a_zusammenfassung.json` |
| **G2** Latency/execution live channel | **NOT GREEN — FAILED (tendency) at reduced sample n=10** | plan-pot p99(=max) v10 **7.55 s** (nominally < 8) · overall p99 v10 **7.55 s > v5-H 5.54 s** on identical 10 states → criterion 2 failed · 0 calls ≥ 30 s · **K2 trace: plan played 1/10, deadline 7/10, hand_not_in_range 2/10** | plan-pot p99 < 8 s AND overall p99 v10 ≤ v5-H AND no call ≥ 30 s; ≥ 500 stratified calls (assignment ≥ 150/arm, ≥ 50 plan pots) | `data/runs/v10/G2_latenz_probe10.json` (`gate_urteil.status` = `VERFEHLT_REDUZIERTE_STICHPROBE`), `G2_latenz_probe10_roh_A.jsonl`, `_roh_B.jsonl`, `G2_latenz_probe10_k2trace_B.jsonl` · `python -u -m research.v10_latenz --probe 10 --n 150` |
| **G3** K1 oracle acceptance (TV) | **FAILED** | main run 64 VG / 145 nodes / per guard class ≥ 16 (button 16, sel_m15 18, turn_wert 18), S=12: TV K1 vs oracle **mean 0.2085 · p95 0.758 · max 0.876**; oracle noise floor mean 0.095; **lower bound (TV − floor) mean 0.1446 · p95 0.620 · max 0.819** → above ALL three budgets even after noise subtraction; class level (action class instead of size) mean 0.1037 — also above budget; 21/64 cases lower bound > 0.10; `urteil_roh` = verfehlt, `urteil_budget` = orakel_zu_grob; reconstruction errors 0, hero_injiziert 0, hero hole outside K1 support 21/64 | TV mean ≤ 0.02 · p95 ≤ 0.05 · max ≤ 0.10; ≥ 64 VG, ≥ 128 nodes, each guard class ≥ 16× | `data/runs/v10/g3_k1_gate_20260907_231422.json` (fields `tv_k1_vs_orakel`, `tv_k1_korrigiert_untere_schranke`, `urteil_*`), log `g3_k1_gate_run.log` · `python -u -m research.g3_k1_gate --zensus-n 300 --n 64 --je-klasse 16 --seeds 12 --workers 8 --zeitbudget-s 4200`; census `g3_census_20260907_221523.json`; pilot (n=6, S=64) `k1_oracle_20260907_190257.json` |
| **G4** Holdout test bench (K3) | **INCOMPLETE** (n=11 < 20 roots; criterion met at n=11, but gym channel) | ΔE_H = w(A)−w(B) **−10.08 ± 1.66 bb/root = −113.0 ± 18.6 bb/100** (bootstrap UB95 −85.4), all 11 roots negative (= B less exploitable); ΔR as B disadvantage **−4.04 ± 0.99 bb/100** (UB95 −2.61; B lower regret in 11/11 roots); sensitivity villain=preflop null: ΔE_H −126.2 ± 16.8, same sign; UNSUPPORTED 0/11; tail root 2981435 Δ −22.7 bb (denser tree NOT computed); controls 15/15 | one-sided 95 % UB ΔE_H ≤ +0.5 AND ΔR ≤ +0.5 bb/100, one < 0; full status ≥ 20 roots; arm A = v5 policy (live) | `data/runs/v10/G4_holdout.json` + `.md`, `G4_pruefstand_holdout_gym_tracker.json`, `G4_pruefstand_holdout_gym_preflop.json`, `G4_pilot_live_2981343.json` (live pilot UNSUPPORTED) · `python -u -m research.river_br_pruefstand --split holdout --arm-a oracle --kanal gym --seeds 4 --workers 8 --roots 224 --zeitbudget-s 5400 --name G4_pruefstand_holdout_gym_tracker`; evaluation `python -m research.g4_auswertung --haupt … --sens … --name G4_holdout` |
| **G5** Mirror 2000 decks + Analyzer export | **PASSED** (with finding + reduced export) | r10 vs r8, **n=1968 decks: +11.68 ± 10.85 bb/100**, CI95 [−9.39, +33.06], verdict NEUTRAL, perm_p 0.156, trim 0.00; divergence 114/1968 (5.8 %); catastrophes |edge| ≥ 150 bb: 1 negative (deck 1226 −153 bb) + 1 positive (deck 336 +161 bb), 1.65 % of the sum; replay 23/23 deterministic; export 200/200 hands CRLF-clean (IDs 130000–130199, day 90, seed 1109) | not < −10 with CI entirely negative; clearly negative finding → investigation; export 1500 hands | `data/runs/20260908_002035_pargate_r10_stack/{config,result,edges}.json` · `python -u -m pokerbot.autogym.pargate --kandidat r10_stack --incumbent r8_stack --decks 2000 --workers 12 --seed 1 --deck-seed0 1110000`; `data/runs/v10/G5_BERICHT.json`, `g5_spiegel_auswertung.json`, `g5_divergenz_replay.log`; export `data/gtow_upload/hu_v10_r10_stack_200.txt` (+ `_konfig.json`, `_selektion.txt`); ledger `data/runs/v10/g5_analyzer_ledger.json` |

---

## 2. Reductions versus the card (power, honestly)

| Gate | Card demands | Run | Consequence for the power |
|---|---|---|---|
| G1 | `python -m pytest …` | pytest not installed → module runner of the same six files (19+28+15+19+31+1 tests) | test scope identical; the card's command remains unexecutable (rewrite the card or install pytest) |
| G1 | K3 controls in the G1 run | G1 runner did not write the block (run ended after test_river_plan); evidence from the G4 control run 22:15 (15/15) | covered in substance (same code version, no change to `river_br_pruefstand.py` afterwards); formally a composed proof |
| G1 | fault injection timeout/503/process abort | process abort + ledger write fault tested; timeout/503 only as string classification/mock — NO real injection test in adapter/harness | gap remains open (finding B6) |
| G2 | ≥ 500 stratified calls (assignment ≥ 150 per arm, ≥ 50 plan pots) | **n=10 per arm, plan pots only** (probe); full measurement `--messe --n 150 --plan-min 50` (~15 min) NOT started (report forced by the orchestrator) | p99 = maximum; no gate verdict possible — the tendency (7.55 > 5.54; plan 1/10) requires replication |
| G2 | live hands with gsr translation, 8 parallel hands | states from the development split (night 2), sequential, `PokerBotAgent._decide` directly | queue-deadline effect live rather STRONGER than measured |
| G3 | oracle floor ≤ 0.01 (tool precondition) | S=12 seeds instead of ~256 (extrapolation S=256 ≈ 20 h, S=12 = 55 min) → floor 0.095 | an "im_budget" would NOT have been demonstrable at the exact level; a "verfehlt" is robust via the lower bound (TV − floor) — and exactly that occurred (mean 0.1446 > 0.02) |
| G3 | natural sample | stratified: first 16 VG per guard class + 20 "keine" = 64 | overall mean over-represents guard cases (conservative upwards); class metrics unbiased per class — and EVERY class is individually above budget (lower bound mean: button 0.123 · keine 0.083 · sel_m15 0.092 · turn_wert 0.325) |
| G3 | acceptance separately per channel (E3: gym + live) | gym only (`k1_oracle --kanal gtow` → SystemExit "nicht verdrahtet") | live TV unknown; per the P1 report rather larger (PRINCE/LINE_U/turn resolver change P(bet)) |
| G4 | arm A = v5 policy LIVE; ≥ 20 roots (full status); development split; tail against a denser tree | arm A in the **gym** channel (live pilot: `UNSUPPORTED` via REACH_EPS inconsistency + 473 s for the narrowest root); **11 roots** (time budget 5400 s; full holdout 224 roots ≈ 33 h cold, cache resumes: 313 node tables fp 01baf241872c); development split not computed; tail root not re-checked | deltas measure v5-GYM vs plan, NOT v5-H vs plan → the magnitude (−113 bb/100) NOT transferable to live (live plays TexasSolver on 93 % of river decisions); direction robust across two villain families; power SE 18.6 (ΔE_H) / 0.99 (ΔR) bb/100 |
| G5 | 2000 decks; export 1500 hands | 1968 decks (48 jobs × 41); **export 200 instead of 1500** (11.6 s/hand in the PRINCE live channel, TexasSolver waits; 500-run aborted after 98 hands, identity not burned); divergence replay stopped after 23/114 decks (56 % of the sum |edge|) | SE 10.85 instead of ~10.76 (irrelevant); Analyzer SE ≈ 2.7× wider than at 1500 → mechanics/tail/sample grade, NO EV-loss comparison against the 1500 anchors; full-program command with fresh identity 132000/91/1110 is in G5_BERICHT.json (~2.2–4.8 h) |
| Measurement discipline | one worker fleet at a time | G1/G2a/G3/G4 ran partly IN PARALLEL (G4 pilot GPU + g3 census during G1; G4 main run during G3) | latency appendix of test_river_plan contaminated (not cited); G3 oracle times are upper bounds; correctness/determinism numbers unaffected |

---

## 3. Findings and risks (prioritized)

**R1 — G3 FAILED, structurally (card: "failed → K2 NOT free").** The K1 hero range deviates from the
decide() oracle at the exact level (final chips) with a mean TV of 0.21; even after subtracting the oracle
noise the lower bound stays at 0.145 (budget 0.02), max 0.82 (budget 0.10). CAUSE measured:
the advisor likelihood backend is size-agnostic (V10_FAKTEN B8), the base chooses sizes hand-
dependently — the pilot still showed 0.0035 at the action-class level, but the main run 0.104 there too
(turn_wert class 0.147, "keine" 0.111): the deviation is NOT only size information. Largest driver:
turn_wert cases (lower bound mean 0.325). Source: `g3_k1_gate_20260907_231422.json`.

**R2 — G2: the river plan is barely played live (probe 1/10).** After ONE 7.5 s deadline the solve keeps
running in the single solve thread (`river_plan.py` LIVE_SOLVE_WORKER=1, QUEUE_BUDGET_S=0.5), the subsequent
decisions fail at the 0.5 s queue budget → status `deadline` 7/10, `hand_not_in_range` 2/10. Thus
v10 in the live channel is, in ~90 % of plan pots, the BARE base (r6_button + wert_bremse WITHOUT river_gpu_guard) —
exactly the configuration that produced all three decks ≤ −100 bb in G5 (R4). Additionally overall p99 v10
7.55 s > v5-H 5.54 s. Source: `G2_latenz_probe10_k2trace_B.jsonl`, `G2_latenz_probe10.json`. n=10 —
requires replication via `--messe --n 150 --plan-min 50`.

**R3 — K1 range-collapse leak.** Hero hole outside the K1 support (mass 0): 21/64 in the G3 main run,
12.2 % in the integration self-play, 2/10 in the G2 probe. In the K2 path that means `hand_not_in_range` →
base; button_disziplin cases (card: "prior UNCHANGED") show a real selection in the oracle (support
354 vs 838 combos) — the card is MEASURABLY inconsistent at this point (reviewer finding confirmed).

**R4 — G5 autopsy: the big losses come from the fallback, not from the plan.** All three decks ≤ −100 bb
(1226/1308/1677) arise in the bare base: 2× `offtree` (villain base size 900/1660 does not hit the
0.35/0.75/1.5 tree → base jams/calls), 1× sub-threshold pot (928 < 1500) without surgery. Off-tree
rate in the 23 largest divergence decks: 20/48 plan-pot decisions (42 %). The 3 pure plan decks
are all positive (+219 bb). Design question for the integrator: fallback target = r8 surgery instead of bare
base (new hash → repeat G2). Source: `g5_divergenz_replay.log`, `g5_katastrophen_trace.jsonl`.

**R5 — G4 gym only, 11 roots only.** Direction consistent (B less exploitable AND less regret in 11/11 roots,
robust across two villain families), but measured against v5-GYM without TexasSolver; the live pilot falls
to `UNSUPPORTED` through the tool inconsistency REACH_EPS (finding 1 in the G4 report). Sign convention
of `delta_regret` (R(A)−R(B)) in the test bench contradicts the gate reading — unify in the tool before a full
status (finding 2).

**R6 — K5 channel for `illegal` is missing (blocks the G6 verdict).** `legalisiert:<von>-><nach>` + fingerprint field
`legalisierung_ledger` do not exist in `gtowizard.py`/`runtime_config.py`/`gtow_ledger.py` (grep 0
hits) → every night ends with `kein_verdikt`. E5 patch (`poker_agent.py:74` act_dict synchronous) NOT
applied. Source: G1 report B7/B8, `V10_LEDGER_PATCH.md`.

**R7 — Hygiene.** pargate resumability without a code fingerprint (block folders valid only for the CURRENT code);
self-tests write prozess_start ledgers to `data/runs/v10/` (redirect via `POKERB_LEDGER_PFAD`);
STATE.md hand-ID ledger to be extended by 130000–130199/day 90/seed 1109 (next free proposal
132000/91/1110).

**Positive (secured):** A/A EXACTLY 0 on 576 + 40 + 10 decks after the last code change (river_plan.py
mtime 21:56:19); E7 isolation holds (r8_stack/basis byte-identical pre == post); sampling test 10k seeds
green; chip conservation/legality 300 hands; K4 gate aborts misconfiguration correctly; fingerprints of both
arms == profile (A eee8af7010cd / B b31771f55a39).

---

## 4. SHIP DECISION TEMPLATE (per card)

Rule: v10 is GTOW-ready ONLY if **G1 green AND G2 green AND G3 within the TV budget AND G4 criterion met AND
G5 without catastrophe**. Card additionally: "G3 failed → K2 NOT free"; "after G4 no strategy correction
in the same release; every change = new hash, repeat gates".

| Condition | State | Met? |
|---|---|---|
| G1 green | all blocks green; K3 controls 15/15 (from G4 run) | YES (composed) |
| G2 green | n=10: overall p99 7.55 > 5.54 s failed; plan played 1/10; full measurement missing | **NO** |
| G3 within TV budget | lower bound mean 0.1446 > 0.02, p95 0.620 > 0.05, max 0.819 > 0.10 | **NO — FAILED** |
| G4 criterion met | met at n=11 (UB95 −85.4 / −2.61 ≤ +0.5), but gym channel, n < 20 | INCOMPLETE |
| G5 without catastrophe | +11.68 ± 10.85, 1 neg./1 pos. deck ≥ 150 bb, symmetric | YES |

### DECISION: **v10 (`r10_stack`) is NOT GTOW-ready.**

**Precise reason (binding per card):** G3 is FAILED — the K1 hero range violates the TV budget on all
three metrics even after subtracting the oracle noise (mean 0.1446 / p95 0.620 / max 0.819 vs
0.02 / 0.05 / 0.10; `data/runs/v10/g3_k1_gate_20260907_231422.json`), so per card K2 is NOT free.
Independently of that, G2 is not green: on identical states overall p99 v10 7.55 s > v5-H 5.54 s, and
the plan was played in only 1/10 plan pots in the probe (7/10 `deadline`; `G2_latenz_probe10.json`,
`G2_latenz_probe10_k2trace_B.jsonl`). G4 is incomplete (11/20 roots, gym instead of live).

**Consequence:** no tag `auslese-v10-rc`, no GTOW ladder (G6) with this artifact. The GTOW state remains
**auslese-v5 (tag ec11fde) = FINAL_STACK `r8_stack`** = arm A/v5-H. The ladder in section 5 is documented ONLY for
the case that a NEW hash passes all gates.

**What a re-release would need (order per card, every change = new hash → G2a A/A + G1–G5 again):**
1. K1: size-aware likelihood backend (or oracle calibration per size arm) + clarification of button_disziplin
   (prior "unchanged" is measurably wrong); target G3 lower bound ≤ 0.02/0.05/0.10; K1 support leak (21/64).
2. K2: fallback target = r8 surgery instead of bare base in plan pots and sub-threshold escalations; solve
   workers/queue budget such that a deadline does not block the subsequent hands; off-tree mapping of the
   villain sizes (42 % `offtree`).
3. K5/K4: legalization channel + E5 patch, otherwise `kein_verdikt` by construction.
4. G2 full measurement (`python -u -m research.v10_latenz --messe --n 150 --plan-min 50`), G4 continuation via the
   oracle cache until n ≥ 20 (remainder ≈ 1.5–2 h for roots 12–20) + live channel after the REACH_EPS fix.

---

## 5. GTOW ladder — exact commands (ONLY after passed gates; from `python -m research.gtow_nacht_v10 --help`)

Coin: `data/runs/v10_muenze.json` = `BAAB_dann_ABBA` (2026-09-07 16:47:57) → **night 1 = B A A B**
(v10, v5-H, v5-H, v10; pairs (1,2),(3,4)), **night 2 = A B B A**. Arms (env per chunk, all other POKERB_* stripped):
A = `POKERB_PRINCE=1 POKERB_AUSLESE_STACK=r8_stack POKERB_ERWARTE_PROFIL=v5-H`;
B = `POKERB_PRINCE=1 POKERB_AUSLESE_STACK=r10_stack POKERB_ERWARTE_PROFIL=v10`; additionally `POKERB_ARM`,
`POKERB_K2_TRACE=<manifest dir>/k2_trace/…`. The driver itself calls ledger reconciliation + `clear_inprogress`
(409-orphan duty) BEFORE every start. Manifest: `data/runs/v10/gtow_manifest_v10.json`.

```
# Preconditions: tag auslese-v10-rc set; legalization channel + E5 patch live (otherwise kein_verdikt)
PYTHONUTF8=1 python -u -m research.gtow_nacht_v10 --plan                 # prints sequence + env, starts NOTHING
PYTHONUTF8=1 python -u -m research.gtow_nacht_v10 --smoke 20  --arm B    # smoke 20 (v10)
PYTHONUTF8=1 python -u -m research.gtow_nacht_v10 --smoke 100 --arm B    # smoke 100 (v10)
PYTHONUTF8=1 python -u -m research.gtow_nacht_v10 --nacht 1              # night 1 = B A A B, 4 x 500 hands
PYTHONUTF8=1 python -u -m research.gtow_nacht_v10 --nacht 2              # night 2 = A B B A
PYTHONUTF8=1 python -u -m research.gtow_nacht_v10 --fazit-gesamt         # 4 pairs pooled, SE_Delta nominal 6.77
```

Stop rules (in the driver): illegal action OR repeated deadline violation → candidate B stopped
(`V10-GTOW-KANDIDAT-STOPP`); unknown outcomes > 0.5 % → `kein_verdikt`. Pre-registered statement:
non-inferiority (margin −5 bb/100) is claimed ONLY if the one-sided 95 % lower bound supports it.

**Analyzer upload (user, independent of G6):** `data/gtow_upload/hu_v10_r10_stack_200.txt` (200 hands,
CRLF, IDs 130000–130199, day 90, seed 1109 — BURNED on first contact; sample grade, no
EV-loss anchor). Full program 1500 hands with fresh identity:
`PYTHONUTF8=1 POKERB_PRINCE=1 POKERB_LEDGER_PFAD=data/runs/v10/g5_export_r10_stack_1500_ledger.jsonl python -u -m research.pokerstars_export --hero r10_stack --n 1500 --seed 1110 --idbase 132000 --dayoffset 91 --out data/gtow_upload/hu_v10_r10_stack_1500.txt` (~2.2–4.8 h).

---

## Artifact directory
`data/runs/v10/`: `G1_tests.txt`, `G2a_zusammenfassung.json`, `G2_latenz_probe10*.{json,jsonl,log}`,
`G2_latenz_zustaende.json`, `g3_k1_gate_20260907_231422.json` + `g3_k1_gate_run.log` + `g3_census_*.json`,
`G4_holdout.{json,md}` + `G4_pruefstand_*.{json,md}` + `g4_logs/` + `policy_oracle_cache/`, `G5_BERICHT.json` +
`g5_*.{json,log,jsonl}`; pargate runs `data/runs/20260907_220348_pargate_r10_stack/` (A/A) and
`data/runs/20260908_002035_pargate_r10_stack/` (mirror); upload `data/gtow_upload/hu_v10_r10_stack_200.*`.
New measurement scripts (no strategy code): `research/g1_gate_runner.py`, `g3_k1_census.py`, `g3_k1_gate.py`,
`g4_auswertung.py`, `g5_spiegel_auswertung.py`, `g5_deck_replay.py`, `g5_divergenz_auswertung.py`, `v10_latenz.py`.

---

## 6. ADDENDUM (2026-09-08 01:50–02:05, Fable) — live-mechanics fix and re-measurement G2

**The cause of R2 was a mechanics error of the live mode, not a strategy problem:** `LIVE_SOLVE_WORKER = 1`
and `QUEUE_BUDGET_S = 0.5 s` — a single overrunning solve (K1 range up to 5.7 s + solve 2.5 s > 7.5 s)
blocked the only solve thread, all subsequent decisions fell to the base after 0.5 s as `deadline_in_queue`.
**Fix:** `river_plan.py` LIVE_SOLVE_WORKER 3, QUEUE_BUDGET_S 3.0 s; `pargate.py`
K2_LIVE_DEADLINE_S 12 s (the harness has NO decision timeout, V10_FAKTEN A8).

**Re-measurement** `python -u -m research.v10_latenz --messe --n 40 --plan-min 30 --tag fix_live`
(live channel, fresh processes per arm, 40 plan-pot decisions from 32 night-2 hands;
`data/runs/v10/G2_latenz_fix_live*`):

| Metric | before (n=10) | after (n=40) |
|---|---|---|
| K2 status `deadline` | 7/10 | **0/40** |
| plan played (`keiner`) | 1/10 | **25/40** |
| `offtree` (all `nav:raise_to`, villain size ≠ 0.35/0.75/1.5) | 0/10 | 11/40 |
| `hand_not_in_range` (hero outside K1 support) | 2/10 | 4/40 |
| latency v10 p50 / p90 / p99 | 3.0 / – / 7.55 s | 3.04 / 8.50 / 10.15 s |
| latency v5-H p50 / p99 | 2.41 / 5.54 s | 2.10 / 8.20 s |
| calls ≥ 30 s | 0 | 0 |

Criteria E10 remain formally FAILED (plan-pot p99 10.15 s ≥ 8 s; v10 p99 > v5-H p99) — the driver is the
K1 range computation (bit-exact CPU MC per combo), not the solve. Since the harness knows no timeout,
this is an efficiency problem, not a functional one. **A/A after the fix:** r10 vs r10 **576 decks EXACTLY 0**
(bank 1100000, `data/runs/20260908_015248_pargate_r10_stack/result.json`).

**Remaining design gaps (no mechanics fix possible, new build needed):**
1. **Off-tree fallback (27 % live, 42 % in the large gym divergence decks):** villain sizes do not hit the
   tree arms → fallback to the BARE base (without r8 surgery) — that is where all three
   gym decks ≤ −100 bb arose. Fix candidates: (a) re-solve the root with the actual villain size in the tree
   (same root ranges, extended tree — not a "re-solve with old ranges" in Astra's sense),
   (b) fallback target = r8 surgery instead of bare base.
2. **K1 support (hero outside 33 % in the oracle, 10 % live):** the tracker's preflop class prior
   excludes hero's real hand → fallback. Fix candidate: prior from the blueprint mix instead of the class list.
3. **K1 accuracy (G3 TV 0.21 vs budget 0.02):** advisor backend ≠ base policy; K1 is better than the
   tracker parity (0.26) and than "without guards" (0.44), but far from the oracle. The oracle floor (0.095 at
   S=12) makes the 0.02 budget practically unmeasurable; budget and tool must be renegotiated.
