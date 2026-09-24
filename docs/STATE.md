# PROJECT STATE — start here (for a fresh Claude session)

> Living entry point. Read this first, then [CLAUDE.md](../CLAUDE.md) (north star + conventions) + [INDEX.md](INDEX.md) (live repo tree). Last updated **2026-09-09**.
> The cross-session memory lives at> **⚠ PROJECT CLOSED (2026-09-10): read [`PROJECT_BALANCE_2026-09-10.md`](PROJECT_BALANCE_2026-09-10.md) first.**
>  `C:\Users\hampe\.claude\projects\C--Users-hampe-Desktop-PokerB\memory\` (index: `MEMORY.md`).

## ★ 2026-09-24 (later) — ENGLISH, REORGANIZED, DE-PERSONALIZED, AGENT-READY
- **Language:** trainer UI (`training.html`, `six.html`, `index.html`), coach texts (templates, grader, glossary,
  opponent panel, range story, replay, report) and all documentation are English. Some code comments are still German.
- **Removed:** the Punishment trainer mode and its five punisher profiles; every file and passage about the
  operator's own poker persona and hand histories, plus scripts profiling real third-party players (moved to
  `Desktop/PokerB_ausgelagert_2026-09-10/princedarkness_2026-09-24/`; git history untouched).
- **Structure:** docs moved into `docs/{catalogs,doctrine,plans,reports,consults,archive,media}` with English names
  (`MODULE_CATALOG`, `MEASUREMENT_CATALOG`, `CANDIDATES`, `PROJECT_BALANCE_2026-09-10`, …); root launchers →
  `scripts/play_*.bat`; serverless worker → `infra/serverless/`. All references rewritten, 0 broken relative links.
- **Discoverability:** `AGENTS.md`, `llms.txt` (repo + site), `CITATION.cff`, `CONTRIBUTING.md`, CI workflow
  (`.github/workflows/tests.yml`), README with GIF, results table and the transferable measurement discipline;
  site gets meta/OpenGraph/JSON-LD, `robots.txt`, `sitemap.xml`, `og.png`, favicon.
- **License holder:** Leonhard Hampe (`NOTICE`), PolyForm Noncommercial 1.0.0.

## ★ 2026-09-24 — PUBLISHED: repo `aeneassoft/QuantPlay` (public) + browser trainer on quantplay.io
- **GitHub:** `PokerB` → renamed `QuantPlay` (the old game repo → `quantplay-herzlichter`), `poker-core`
  pushed and made the default branch, visibility public. History unchanged (no rewrite). Third-party hand
  histories were moved out of the tree beforehand. Secret scan over all 401 commits:
  no token patterns. `data/preflop_strength.json` (3 KB equity cache) is now versioned so that a clone plays.
- **Browser trainer (`web/`):** the same `six_server.Session` runs in Pyodide 0.28.3 (Python 3.13/WASM) in the
  visitor's Web Worker; `pokerbot/web/browser_bridge.py` calls the FastAPI endpoints directly (Pyodide has
  no threads → the ASGI threadpool fails, measured). Bundle 1.23 MB (pokerbot/*.py+html, knowledge_base
  math/ranges/cfr/postflop-json/tournament, preflop_strength.json) + 5 wheels 0.34 MB. **Measured (Node+Pyodide):**
  import 0.9 s; 5 hands incl. grader 0.32 s, slowest request 0.11 s; tournament 12 hands 3.5 s, slowest 0.35 s.
  All trainer modes + feedback/replay/panel/report/analysis/glossary verified in the browser (locally and live on quantplay.io).
  Prince takeover stays off (default since 2026-09-09), advisor nets (.pt) not in the bundle (no torch in the browser).
- **Vercel:** project `quantplay` separated from `aeneassoft/QuantPlay` (the game), password middleware removed, deploy via
  CLI from `web/` (`vercel deploy --prod`), alias quantplay.io. No Git integration (the root directory cannot be set
  via CLI) → after changes: `python web/build.py` + deploy by hand.
- **License (2026-09-24, operator):** PolyForm Noncommercial 1.0.0 (`LICENSE.md`) — commercial use of the
  poker assets only with written permission. Open: UI German-only; layout scaled for 2560×1440, cramped on phones.

## ⏸ PAUSE STATE (2026-09-10, all processes stopped)
**Where to resume — three points, in this order:**
1. **v10's error rate.** In the only valid candidate run, **10 of 23 plan activations ended in
   ERROR** (43 %). That is the next point of attack, NOT the H1 continuation (reports/KAGGLE_ARENA.md, last
   section). gpt-5.6-sol recommends the same: evaluate K2 on oracle ranges against v5 BEFORE any H0/H1 code is written.
2. **The v5 anchor is still missing.** The only GTOW anchor (−21.12 ± **9.40**) belongs to v4/r6_button. Without
   a v5 anchor every strength claim is speculative. Caution: **c = 294, not 214** → SE 4 needs 5,407 hands.
3. **Aborted measurement:** `kaggle_v9_vs_champion_WDH` stood at 100/300 decks with **−17.2 bb/100**
   (preliminary, no verdict). So the v9 guard DOES fire after the deal-marker fix — the earlier
   null finding was an adapter error.

**Fresh in the repo:** [`catalogs/MODULE_CATALOG.md`](catalogs/MODULE_CATALOG.md) (272 modules) · [`catalogs/MEASUREMENT_CATALOG.md`](catalogs/MEASUREMENT_CATALOG.md)
(all measurements + three corrections) · [`reports/AIVAT_KAGGLE.md`](reports/AIVAT_KAGGLE.md) (draft, nothing built) ·
[`consults/CONSULT_GPT56_SOL_2026-09-10.md`](consults/CONSULT_GPT56_SOL_2026-09-10.md) (hybrid consult) ·
[`catalogs/CANDIDATES.md`](catalogs/CANDIDATES.md). Deleted: the folder `#Anderes/`.

## ★★★★★ CURRENT (2026-09-10) — TWO CATALOGS + a correction that changes the hand budgets
**New: [`catalogs/MODULE_CATALOG.md`](catalogs/MODULE_CATALOG.md)** (272 module entries, each with purpose/interface/dependencies/
state/cost/**measurement status**/pitfall; refuted building blocks explicitly included) and
**[`catalogs/MEASUREMENT_CATALOG.md`](catalogs/MEASUREMENT_CATALOG.md)** (all real measurements with source, verdict and validity).
CLAUDE.md points to them at the top. Module catalog = what a part DOES, measurement catalog = whether it WORKS.
**★ CORRECTION (recomputed from the hand histories, not taken on trust): the variance coefficient of today's
bot is c = 294, not 214.** From `gtow_hands_1787027076/_1787033025.jsonl` (n=979): mean −21.12,
per-hand SD 294.1, **SE 9.40** (not 6.8). The 214 stems from the v2.2 era (SD 213.5 there at n=2393).
Consequence: for SE = 4 bb/100 it takes **5,407 instead of 2,862 hands**; the 95 % band of the only anchor is
roughly [−39.5, −2.7]. Every budget calculation on c = 214 must be corrected.
**Also invalid:** the Kaggle reference value and the v9 Kaggle run (missing deal marker, also affected the
champion's GPU surgery) — see reports/KAGGLE_ARENA.md. The folder `#Anderes/` was deleted.

## ★★★★ CURRENT (2026-09-10) — KAGGLE GAME ARENA as a second measurement channel (detail: reports/KAGGLE_ARENA.md)
The Kaggle leaderboard "Heads Up Poker" measures **Mean BB/100** in an all-play-all of frontier LLMs
(v1 via the Kaggle API: top GPT-5.6 Sol +34.9 ± 5.1; Claude Fable 5.1 +29.7; bottom GPT-5 mini −49.3).
The environment is OPEN SOURCE and runs locally (Windows wheel for 3.12): `python_repeated_pokerkit`
(blinds 1/2, stacks 200 units = **100 bb**, reset per hand, dealer rotates, 100 hands/match) — exactly our
house size. **Bridge built:** `pokerbot/benchmark/kaggle_arena.py` (parser, state adapter as in the
GTOW harness, legality guarantee, paired decks with seat swap), `tests/test_kaggle_arena.py` 4/4 green,
**A/A exactly 0**. Two measurement traps fixed: hand_id per mirror half (the v10 trap) and the RNG STREAM across
hands (A/A was −37.5 → fresh instances per half). **Classification (binding): a cheap volume channel, NOT a
GTO anchor** — the field is LLMs, not a re-solver; the GTOW anchor remains the truth. **Calibration Kaggle->GTOW (user idea): WEAK** —
6 shared models, r=0.37/R²=0.14 (residual SD 15.5); only after dropping Grok 4 r=0.88 — that is curve fitting, not a verdict.
**★ The actual finding: benchmark.gtowizard.com accepts YOUR OWN agents** ("Evaluate Your Model"), the
top are private bots (Bitcrumbs −3.1/52k hands, Trainer −6.2, Roman_SL −7.4, tangtang −12.6) and
**three entries by "Hampe" are already on it** (Quantplay −30.4 rank 31, Quantplay v8 −31.6 rank 33,
Experimental Poker Bot −51.7 rank 47) — all from the v8 era; today's champion (~−21) was NEVER posted.
Rank = LOWER BOUND of the 95 % interval, so hands count as much as the mean: **top 5 = LCB better than
≈ −14.8**, i.e. ~−11 at 10k hands or ~−13 at 50k. Gap to today's state ≈ 8 bb/100.

## ★★★★ CURRENT (2026-09-09 night) — 6MAX FLAT-FIX APPLIED (tag `sixmax-tag-flatfix-v1`)
User finding in the tournament: the advisor called A2o CO vs LJ open a "Call" (percentile 0.691 > threshold 0.665 — the hot-and-cold
ranking overrates offsuit aces; Analyzer leak "preflop caller lines"). Fix: `flat_guard` in the tag core — dominated
offsuit broadways (A2o–A9o, K2o–K9o, Q2o–Q9o, J2o–J8o) are never flatted vs an open. **Gate pargate6, 3 runs of 2992
decks each vs the old tag: +17.7±6.4 (ANWENDEN = apply, p 0.0035) / +11.4±6.9 (NEUTRAL, p 0.057) / +19.2±7.0 (ANWENDEN, p 0.0035)**
→ applied to `PROFILES["tag"]` (league, advisor, tournament). Old core = tag `sixmax-tag-pre-flatfix`. Logs
`data/runs/pargate6_tag_flatfix*_2026-09-09.log`. Open: external anchor (Analyzer export of the new tag).

## ★★★★ CURRENT (2026-09-09 evening) — TOURNAMENT MODE in the trainer (detail: reports/TOURNAMENT_MODE.md)
MTT 60 players, 6 tables of 10, 10 levels 25/50→800/1600 (ante from L3, 12 hero hands per level), table balancing ±1,
collapse down to the final table, top 9 paid; field = online-population PRIOR (station 30/tag 22/lag 15/nit 12/rock 8/
whale 5/maniac 4/shark 4). Hero's table fully computed (league bots), side tables ≈ 120–130 ms per hero hand.
Advisor = tag-core oracle per hero action (`GTO ✓` / `Abweichung: …`) + ICM hint from ≤ 12 remaining; GTO rate
and top deviations in the HUD/end screen. Code: `pokerbot/arena/mtt.py`, `six_server` mode `tournament`, `training.html`
(tournament button/HUD/verdict/result), `tests/test_tournament_mode.py` (8 tests green). Browser-verified (two
UI bugs fixed along the way: invisible HUD via display:none, table number from name offset). **User-QA fix
(evening): hand-continuity bug** — a fresh Table per hand had hand_no 1 → `_log_if_done` skipped everything after
hand 1 (stacks/busts/feedback frozen: "always 100 bb", "always played well"); fixed + `test_hand_continuity`,
two full TestClient tournaments + browser quick run (3,671 renders, 0 errors). Empty table FOUND: tournament bb 50 → slider amount 187.5 chips → 422 without `error` → rendered as state; 3-layer fix (server rounds float, client api()/render() guards). **Pre-fold (user request, evening):** "Fold vorab" in the waiting bar (key F) —
the hand immediately plays out in the background, the fold is graded normally, chips correct, next hand after 1.5 s; a free check
cancels the pre-fold; 350 ms click lock on turn change. `tests/test_prefold.py`; docs reports/TRAINER_WIRING.md. No measurement verdict — the
mode is a trainer product, not a bot candidate; the GTOW situation (v4-on-PRINCE −21.1 as the only anchor) is unchanged.

## ★★★★★ CURRENT (2026-09-09) — TRAINER WIRING + 6MAX VERDICT + EXPLOIT GATE (detail: reports/TRAINER_WIRING.md)
**HU trainer:** opponent AND advisor = champion config (PRINCE, exploit OFF, resolver ON, `wickle_decide(FINAL_STACK=r8_stack)`),
fingerprints of both bots in /api/view + GET /api/advice. **6-max trainer:** league core `tag` plays; the Prince takeover
in HU-collapsed pots is DEFAULT OFF (`POKERB_SIX_TAKEOVER=1` switches it on; stack via `POKERB_SIX_STACK`), because
pargate6 (NEW, paired 6-max arena, A/A exactly 0) refutes it: hybrid −23.6±9.0 / hybrid_r8 −21.7±9.0 / hybrid_r10
−26.6±8.9 vs tag (2992 decks each, all VERWERFEN = reject; journal VERDRAHTUNG-6MAX-VERDIKT). Best measured 6-max bot = `tag`
(self-ecology; external anchor = Analyzer grade 85.9 %/7.61, hybrid export command stands ready).
**Exploit gate (NEW):** ON vs OFF per league profile, 600 paired decks: all 8 diffs ≤ 0 (pooled ≈ −12 bb/100) → the
Dirichlet river exploit is REFUTED, exploit stays OFF everywhere; 6-max reads neutral (+3.6±13.5). Journal
EXPLOIT-GATE-VERDIKT. **GTOW-confirmed is still only v4-on-PRINCE (−21.1, night 2); v5 (r8_stack) has mirror
evidence, no anchor** — the shadow night (v5 acts, v10 computes alongside) remains the next GTOW step.
New infrastructure: `pokerbot/autogym/pargate6.py`, `pokerbot/autogym/exploit_gate.py`, `pokerbot/arena/hybrid.py`,
`SixMaxBot(seed=)`, `PrinceOracle(stack=, kanal=)`, tests test_sixmax_seed/test_hybrid/test_pargate6.

## ★★★★★ CURRENT (2026-09-07/08) — v10 "River Foundation" BUILT + GATES G1–G5 RUN: **NOT GTOW-ready** (G3 MISSED, G2 not green); state remains auslese-v5
**Full report: [`reports/V10_GATES_REPORT.md`](reports/V10_GATES_REPORT.md)** (table, reductions, findings, ship decision, GTOW relay commands).
Card `plans/V10_BUILD_CARD.md`; arms A = v5-H (`r8_stack`, PRINCE, exploit OFF, TexasSolver ON) vs B = v10 (`r10_stack` =
K1 hero-likelihood replay `pokerbot/strategy/hero_range.py` + K2 public river plan `pokerbot/autogym/river_plan.py`
instead of `river_gpu_guard`; K3 test bench `research/river_br_pruefstand.py`; K4 `pokerbot/runtime_config.py` + `gtow_ledger.py`;
K5 `research/gtow_nacht_v10.py`, coin BAAB_dann_ABBA). Everything UNCOMMITTED in the working tree (branch poker-core, HEAD eabcef3).
**GATES (sources in data/runs/v10/):**
· **G1 GREEN (composite):** 13 blocks exit 0 (`G1_tests.txt`); K3 controls 15/15 from `g4_logs/kontrollen_tests.log`
(the G1 runner did not write the block; pytest not installed → module runner).
· **G2a PASSED:** A/A r10 vs r10 **576 decks EXACTLY 0** (bb100 0.0, se 0.0, nonzero 0; `data/runs/20260907_220348_pargate_r10_stack/result.json`);
golden r8-vs-basis pre == post IDENTICAL (E7 isolation holds).
· **G2 NOT GREEN (n=10 probe, `G2_latenz_probe10.json` status VERFEHLT_REDUZIERTE_STICHPROBE):** overall p99 v10 7.55 s > v5-H 5.54 s
on identical states; **K2 trace: plan played 1/10, deadline 7/10, hand_not_in_range 2/10** (one 7.5 s deadline blocks
the follow-up hands via LIVE_SOLVE_WORKER=1/QUEUE_BUDGET_S=0.5) → live, v10 is the bare base in ~90 % of plan pots. Full measurement
(`python -u -m research.v10_latenz --messe --n 150 --plan-min 50`) NOT run.
· **G3 MISSED (`g3_k1_gate_20260907_231422.json`, 64 VG/145 nodes/≥16 per guard class, S=12):** TV K1 vs decide() oracle
**mean 0.2085 / p95 0.758 / max 0.876**; lower bound after noise subtraction (floor 0.095) **0.1446 / 0.620 / 0.819** vs budget
0.02 / 0.05 / 0.10 → card: "K2 NOT free". Driver turn_wert cases (0.325), class level also over budget (0.104);
hero hole outside K1 support 21/64; button_disziplin prior "unchanged" measurably wrong. Live channel not measurable (E3 open).
· **G4 INCOMPLETE (11/20 roots, gym channel; `G4_holdout.json`):** ΔE_H −113.0 ± 18.6 bb/100 (OG95 −85.4), ΔR(B disadvantage)
−4.04 ± 0.99 — B less exploitable AND less regret in 11/11 roots, robust across 2 villain families; but measured against v5-GYM without
TexasSolver (not transferable to live); live pilot UNSUPPORTED (REACH_EPS inconsistency in the tool). Full holdout ≈ 33 h,
oracle cache fp 01baf241872c resumes.
· **G5 PASSED (`G5_BERICHT.json`, `data/runs/20260908_002035_pargate_r10_stack/`):** r10 vs r8 **1968 decks +11.68 ± 10.85** NEUTRAL,
CI [−9.39, +33.06]; catastrophes ≥150 bb 1 neg./1 pos. (symmetric). FINDING: all 3 decks ≤ −100 bb arise in the FALLBACK to the
bare base (2× offtree, 1× sub-threshold pot), off-tree rate 42 % in the large-divergence decks; pure plan decks all positive.
Analyzer export **200** hands (instead of 1500) `data/gtow_upload/hu_v10_r10_stack_200.txt` (IDs 130000–130199, day 90, seed 1109 —
ledger entry `g5_analyzer_ledger.json`, next proposal 132000/91/1110).
**SHIP DECISION: NOT GTOW-ready** — no tag auslese-v10-rc, no G6 relay. **GTOW state remains auslese-v5 (ec11fde, r8_stack).**
A re-release needs (new hash → all gates anew): size-aware K1 backend + K1 support leak; K2 fallback = r8 surgery instead of the
bare base + solve queue without follow-up blocking + off-tree mapping; K5 legalization channel + E5 patch (otherwise kein_verdikt);
G2 full measurement; G4 to n ≥ 20 + live channel. Relay commands (only then): `python -m research.gtow_nacht_v10 --smoke 20 --arm B`
→ `--smoke 100 --arm B` → `--nacht 1` (B A A B) → `--nacht 2` → `--fazit-gesamt`. Journal: V10-GATES.

**ADDENDUM 02:05 (Fable):** R2 was a live MECHANICS error (LIVE_SOLVE_WORKER=1/QUEUE_BUDGET 0.5 s) → fixed (3 threads, 3 s queue, deadline 12 s); re-measurement n=40 plan pots live: deadline 0/40, plan played 25/40, offtree 11/40, hand_not_in_range 4/40, p99 v10 10.15 s (no timeout in the harness); A/A after the fix 576 decks EXACTLY 0 (bank 1100000). GTOW relay NOT started (G3 missed = pre-registered blocker; decision with the user). Open design gaps: off-tree fallback to the bare base (villain sizes ≠ tree), K1 support (preflop class prior), K1 accuracy. Detail: reports/V10_GATES_REPORT.md section 6.
**ADDENDUM 03:30 (Fable, end of session):** Astra consult part F (completeness: NO, gaps L1 off-tree fallback / L2 K1 support / L3 K1 accuracy + policy closure + channel parity) and part G (hybrid thesis: H is a NEW bot, not Max(v5,v10); H0→H1 build plan, the 7-rule hybrid doctrine now in CLAUDE.md). NEXT STEP on resumption: v10.1 = H0 (plan, otherwise unchanged v5 per decision) → H1; acceptance criteria in TOP5_KONSULT part G section 6. Working tree saved as a commit (poker-core), no tag.


## ★★★★★ CURRENT (2026-09-01) — v8 DROPPED (user decision): auslese-v5 REMAINS the state; postmortem written
**The v8 rung (solver PLAY instead of surgery + stackoff_bremse) was DROPPED after the interim verdicts:**
play vs v5 +1.14±2.78 NEUTRAL (30k) · v8 vs v5 +3.91±2.85 / −1.23±4.36 NEUTRAL (pooled ~+2.3±2.4) ·
all A/A exactly 0. **Root-cause analysis: [`reports/V8_POSTMORTEM.md`](reports/V8_POSTMORTEM.md)** — channel saturation
(the v5 surgery had harvested the clear cases; play differences lie in indifference zones, nz_median
1.9bb vs 11.6bb), the mirror does not punish fine precision (no re-solver), rare edge cases invisible at
45k, Ockham on a tie. GTOW-axis evidence of the play component remains documented positive
(+278.6bb replay, AIVAT-convergent) — unproven without an anchor; the cheapest proof would be a GTOW A/B v5 vs
v5+play (protocol data/runs/gtow_v8_protokoll_2026-08-31.json). r9 arms (play/turn/stackoff) remain
registered default-OFF. **STATE: auslese-v5 (tag ec11fde) = FINAL_STACK r8_stack; GTOW anchor arm B1=v5
prepared, waiting for the user's command.** Negative results with explanation: no_limp −11.42 (the base limps 39%
strategically → the right candidate would be limp-pot DEFENSE), turn_gpu 3/3904 too quiet.

## ★★★★★ (2026-08-30) — GPU RELAY: river CFR on the 3080 Ti, 100% utilization, TexasSolver match 0.999; rounds 7/8 in the gates
**User assignment: use GPU+CPU fully — (1) find gaps systematically, (2) close them yourself, (3) new
bot version GPU+CPU, (4) test vs the frozen base.** State after day 1 (commits 2b57206..c344e14):
**BUILT+VERIFIED (every rung with proof):** `pokerbot/engine/gpu_eval.py` (vectorized 7-card
evaluator, 16.8M hands/s, 250k ordering pairs 0 errors; lesson: CUDA-log2 1-ulp trap → integer-only) ·
`gpu_equity.py` (exact batch equity; river byte-identical to the CPU enumeration; flop 1081x1081 exact 0.087s) ·
`pokerbot/strategy/gpu_cfr.py` (tensor CFR+; clairvoyance toy EXACT: bluff 0.333/call 0.500/expl 0.014%;
RiverCFRBatch B=256 = **100% GPU utilization**, ~1000 subgame iters/s, 0.30s/spot; bandwidth-bound, TF32 ineffective) ·
`gpu_resolver.py` (freeze ranges at the start of the river → batch solve → sequence navigation; hero combo injection
against hand-not-in-range) · **cross-validation vs TexasSolver** (research/gpu_vs_texassolver.py): identical
spot, frequency deltas 0.007/0.000/0.001, per-combo correlation **0.999**.
**GAP FINDING (research/hh_luecken_mine.py + gpu_river_audit.py, night-2 HH):** loss 87% river;
cell (river,>100bb,call) = 9 hands = **59% of the v4 loss**; 7/7 SIZE tell as a frequency claim
REFUTED (only 11% of turn bets in the 2/3 band; the 0.65 bucket = a readable v4 marker without a measurable exploit).
GPU audit 571/571 river decisions: check/fold solver-conformant (p 0.86/0.83), **bet the weakest class**
(p 0.45; 15% clear contradictions), disaster calls = solver fold p>0.95. **Tracker thresholds do NOT carry the
river defense** (discrimination 0.65 vs 0.53 — that is why r6_ecall died; journal R7-DIAGNOSE).
**ROUND 7/8 (guards, all A/A exactly 0):** `river_bill_guard` (exact enumeration, negative margin) — mirror
**exactly 0.0** on 30k (never fires in the gym = a pure GTOW-axis guard) · `river_wert_bremse` (no river
value bet with eq<0.5 vs range) — **r7_river +8.1±1.14 ANWENDEN** (30k, perm_p 0.0002; thus stems entirely
from the wert_bremse; single run + replication running) · `river_gpu_guard` (r8: solver surgery ONLY at
p_basis<0.10 & p_alt>0.70, pot≥30bb, deterministic): on the real night-2 big-pot calls 3/22 folds =
exactly the disasters, net +66.9bb; GTO fold of the lucky call #2997685 (AIVAT −9.2 despite +81.8 real —
AIVAT and the GPU solver agree against the random outcome).
**★ FINAL RUN 1 (2026-08-31 early): wert_bremse REPLICATED 3x (+8.10/+8.81/+7.38, all perm_p 0.0002,
three banks). r8_stack (= river_gpu_guard(river_wert_bremse(r6_button chain)), arm in pargate) through the
chain: A/A EXACTLY 0 (GPU determinism proven) · vs r6_button **+29.92±3.10** (30k, CI [23.7;36.3],
z=11.85; 1040 divergence decks/3.5%, ~17bb per intervention deck) · **vs FROZEN BASE +30.60±5.03**
(30k, CI [20.6;40.3], perm_p 0.0002). EXPECTATION VIOLATION openly documented (increment 3-4x larger
than pre-registered; big-pot surgery decomposition consistent) + NON-ADDITIVITY vs basis (self-play
non-transitivity — mirror = selection channel, absolute proof only at the GTOW anchor, user command needed).
3-RUNS RULE for r8: MET — replications +23.76±3.07 (bank 530k) + +29.23±3.03 (bank 560k),
fresh A/A (iters-150 code) EXACTLY 0. **★ CHRISTENING: `auslese-v5` (tag + commit ec11fde, 2026-08-31) —
FINAL_STACK = r8_stack; increment pooled +27.6±1.8; vs BASIS +30.60±5.03; live smokes green (flop
0.06s; river cold start 13.5s incl. double resolver — later A/B: GPU REPLACES the TexasSolver river,
POKERB_RESOLVER=0).** fp16 option measured +64% (half=True, default OFF). OPEN/NEXT: GTOW anchor
(ABSOLUTE proof; waits for the user's command, hand budget) · expectation violation documented (increment
3-4x above pre-registration; self-play non-transitivity: mirror numbers ≠ GTOW numbers) · turn-CFR
deployment + flop rung + resolver-replacement A/B as the next GPU round.**

## ★★★★★ CURRENT (2026-08-18 ~04:10) — GTOW NIGHT 1 DISSECTED: -38.9 (n=1617) = 81% RIVER without resolver; NIGHT 2 = the real bot + A/B
**NIGHT-1 RESULT (v4 gym config BARE: exploit-ON, resolver-OFF): AIVAT pooled -38.86 (n=1617).**
Driver bug (cp1252 decode) counted SUCCESSFUL 500-hand chunks as failures -> retries played more
v4 hands; EVERYTHING recovered from the HH files (every hand carries `aivat`; method validated exactly against the smokes;
chunks: -26.6/-55.0/-31.7). **DIAGNOSIS FROM THE 1617 HANDS (journal + miner): 81% of the loss on the RIVER
(-511 of -628 bb), pattern = the OLD disaster (175bb jam bluff with K-high into the straight; bottom-pair
call of a 172bb jam) — the channel lacked the two live carriers: RESOLVER (river_resolve was built exactly
for this, was ON in the -30.11 reference) + GTO-MODE discipline (exploit-ON bleeds vs near-GTO).
NO v4 verdict — a config never measured before.** The checkpoint would correctly not have triggered (-31.7
after chunk A). **NIGHT 2 RUNNING (research/gtow_nacht.py v2, user command): the REAL final bot as built
against the base — AUSLESE guard chain r6_button(turn_wert(sel_m15)) via POKERB_AUSLESE_STACK —
on the live foundation POKERB_PRINCE=1 + resolver-ON, WITHOUT RAISE_NARROW (v8-K3, the only rule-conformant
deviation). Chunk 1 = CONTROL (PRINCE pure = the -30.11 reference), chunks 2-4 = v4_prince -> the A/B lands
in one night. Stacking risk pre-registered: turn_wert can override resolver slowplay checks.
Result: journal GTOW-NACHT2-*; HH continue in data/sessions/gtow_hands_*.jsonl (extend the manifest!).**

## ★★★★★ CURRENT (2026-08-18 night) — GTOW RELAY RUNNING: smokes green, the number is a RED FLAG, night run with checkpoint
**The first v4 GTOW test (key #3, user command) runs as a relay 20→100→2000.** Arm = v4 stack
(POKERB_AUSLESE_STACK=r6_button + TURN_DEFENSE 0.07 + SLOWPLAY 0.25 + RAISE_NARROW 1.0, resolver-OFF).
**Smokes: mechanically PERFECT** (20/20 + 100/100, zero errors; two incidents found+fixed: 409 account full
with 20 old orphans → clear_inprogress; dict+str crash in wickle_decide EXACTLY on guard intervention → auslese.py
guard marker instead of rationale concatenation). **BUT: AIVAT 20-run −21.34±14.3 / 100-run −59.03±22.1, pooled
~−53±12 = 2σ BELOW the honest anchor (−25..−30) — the v8 pattern (−58!), suspicion = the Fable finding live
(capped check range vs re-solver).** The NIGHT RUN (research/gtow_nacht.py, running in the background):
4x500 chunks, 3 attempts each + auto-clear_inprogress; PRE-REGISTERED CHECKPOINT after chunk 1: v4 pool
(smokes+chunk1) ≤ −45 → the remaining chunks switch to CONTROL (POKERB_PRINCE=1 resolver-ON = the
−30.11 reference) → the night then delivers the explanatory A/B. **RESULTS FOR THE NEXT SESSION:**
(1) journal data/autogym/journal.jsonl (types GTOW-NACHT-CHUNK per chunk + GTOW-NACHT-FAZIT pooled),
(2) hand histories automatically in data/sessions/gtow_hands_*.jsonl + assignment in
data/sessions/gtow_manifest_2026-08-18.json (do NOT count the crash smoke), (3) analysis routes:
gtow_tree_census parser (replay), research/analyze_gtow_hands.py, Analyzer export. **IF v4 BREAKS LIVE:
round 6b priority = turn_wert SIZE decoupling (the 7/7 tell) + check-range uncapping — the Fable report
(journal FABLE-DUELL/FABLE-RETEST) predicted the mechanism. 409 rule: run clear_inprogress before every GTOW start.
Start command pattern: see research/gtow_nacht.py ARM_V4/_lauf().**

## ★★★★★ CLOSING LINE OF THE ATTACK SPRINT (2026-08-18 early) — v4 stands, hardening proven, queue clear
**Balance: AUSLESE v4 (tag auslese-v4) triply secured (mirror +16.14±2.77 vs basis; envgate staircase;
oracle panel green). r6_button into the HARDENING PROFILE (Fable retest: harvest 186→58 bb/100, cooler-adjusted
bot ahead; open-folds 0/46). Two-axis doctrine MEASURED. NEXT STEPS (prioritized, specs in
data/runs/*.json): (1) round 6b: eCall rebuild with sharper selection + turn_wert SIZE decoupling (the
7/7 tell = seesaw violation, most important single fix) + stack-off brake + limp removal; (2) princegate
+ GTOW adapter (MANDATORY before every anchor; resolver trap); (3) pargate6 (6-max); (4) flop-resolver work sites
(range coverage + latency/ISO cache); (5) level-audit ranking (AIVAT-light, FDR ledger, turn retraining).
$30 pod untouched. Fable duel harness = standing adversary instrument (FABLE_STACK param).
WIRING FINAL (2026-08-18, commit 88771f8): pokerbot/strategy/auslese.py = ONE source
(FINAL_STACK r6_button + AUSLESE_ENV; resolver-ON variant without RN); HU app wrapped, six_server
env share, gtowizard POKERB_AUSLESE_STACK adapter (default byte-identical); all channels smoke-green.
FINAL STACK vs basis (mirror 30k, bank 150000): +23.36+-5.32 CI[+12.8,+33.7] p=0.0002 ANWENDEN.
GTOW run waits for the user's command (protocol in data/runs/praezisions_armee_2026-08-17.json).**

## ★★★★★ CURRENT (2026-08-17 night III) — PRECISION RUN: verdicts bootstrap-hardened, army fixes landed
**Level audit (7 agents, `data/runs/niveau_audit_2026-08-17.json`: top-15 ranking; #1 AIVAT-light in the
mirror, #2 bootstrap CI, #3 FDR ledger, #6 turn retraining from 22.5k subgames) + precision army (19
agents, `data/runs/praezisions_armee_2026-08-17.json`: 10 verified bugs + princegate/pargate6/GTOW
protocol specs).** LANDED (commit c9d06fc): **estimator v3** (sparse-aware bootstrap CI + permutation p;
at channel<2% the CI carries the verdict) — **RE-EVALUATION: turn_wert CI[+2.7,+12.1] p=0.0007 HOLDS, RN10 3x
HOLDS, kombi_r5 HOLDS, v4 staircase HOLDS; RN05 honestly to NEUTRAL (was never in the version)**. Plus: W1-3
bet filter+R fix (was blind on the main mass; FE_CEILING recalibration open), W1-4 hole involvement,
orakel_duell F pooling (the F rung was chunk-dead), pargate env hygiene+deck order, runde5 KeyError,
sixmax UTG 0.16, envgate KANAL_ vocabulary (v8 protection), flop resolver built (POKERB_FLOP_RESOLVER, 7b42a5c).
**GTOW CAUTION (army, CRITICAL): gtowizard.py constructs PokerBot directly (v4 wrapper NOT in the harness)
+ switches the resolver default ON (RAISE_NARROW trap) — the v4 GTOW anchor needs the adapter from the
saved protocol BEFORE it runs.** Honest live anchor remains −30.11±5.51 (rank 24; the −19.70
was presumably blinds-bug-inflated, STATE:257-269). Open: mirror duel v4 wrapper vs basis (running),
princegate, pargate6, turn retraining, AIVAT-light, FDR ledger.

## ★★★★★ CURRENT (2026-08-17 night II) — CHRISTENING: AUSLESE v4 (tag auslese-v4) — the BET-SIDE selection
**AUSLESE v4 = turn_wert_guard(sel_guard(basis, m15)) + POKERB_TURN_DEFENSE=0.07 + POKERB_SLOWPLAY=0.25 +
POKERB_RAISE_NARROW=1.0 (resolver-OFF context; canonical definition = envgate arm `kombi_r5`).**
**FINAL (bank 85000, 12k decks, reference = frozen basis, identical decks): v3 +21.36±6.03 → v4
+49.79±7.99; paired step v3→v4 = +28.44±6.17 (sign-z +10.1).** Evidence chain (all journal + data/runs):
kombi UNIT replicated 3x (+26.4/+25.2/+36.2 vs v3 reference, banks 25k/45k/65k); turn_wert alone 3x in the
REAL mirror gate (+7.27±2.33 pooled, 3x30k); RN10 3x (+16.8/+13.7/+9.2, dose response); K3 alone
NOT replicated, paired in the bundle +10.2±4.0 (interaction: slowplay traps → delayed turn_wert value;
turn defense covers the stab exploit). Oracle duel panel GREEN. HONEST CHANNEL NOTE: the +21/+50/+28
are the envgate channel (common opponent GTOBaseline, paired decks) — not identical to the
mirror gate (there turn_wert +7.27 is the proven component); sign and replication are consistent.
**NEXT STEPS: (1) $0 GTOW anchor for v4 (step 8; mind the resolver discrepancy: RAISE_NARROW is
contraindicated resolver-ON — v8-K3!), (2) co-evolution round 6: after turn_wert the
turn DEFENSE channel opens for the first time (re-measure sel_turn), (3) wire v4 into the consumption channels (server.py
still plays the bare base), (4) GPU job B1 (exact 169x169 matrix) → Brown V1.**
**The big sweep has delivered.** On the repaired foundation (spot RNG: A/A EXACTLY 0 on every deck;
estimator v2 = raw mean + sign test, after the 5% trim was measured as blind for THIN channels
— it threw away the 5-8% signal decks):
**(1) turn_wert guard (bet side, trips+/overpair + eq>=0.60 vs tracker range → 2/3-pot bet on the turn):
POOLED 3x30k decks vs sel_m15 = +7.27 ± 2.33 bb/100, sign-z +14.9, channel 8.6% → ANWENDEN.** The
oldest leak (documented 3x) is fixed; oracle duel panel GREEN (verpasster_wert_turn 17.0→3.1/1000 with
residual floor = no purify pattern; bet_braucht_unplausible_folds drops with 10.0→7.5).
**(2) raise_narrow_10 (mined GTOW raise mix): 3x envgate-replicated** (+16.8/+13.7/+9.2, dose 1.0>0.5)
— ONLY resolver-OFF channels (the v8-K3 warning in gto_mode.py remains binding). **(3) k3_deception does NOT
replicate** (+8.7/+0.3/−4.7) → not into the version; turn_def_adv VERWERFEN (−20 in r3, sign-z negative; the
v5C Analyzer history does not hold in self-play). **(4) sel_all/sel_turn: channel EMPTY** (0 divergent decks
on 30k — mirror ecology: the base almost never bets the turn; re-check after the turn_wert build-in =
co-evolution). **(5) kombi (turn_wert+K3+RN10): +26.4/+25.2 (2x massive)** — attribution running
(kombi_schlank without K3 vs kombi_r5, bank 65000); then cumulative final vs wrapper=basis + christening.
New instruments: envgate (env-flag two-run pairing, wrapper arms), orakel_duell (L/F class rates per
opportunity, first entscheidungs_logger consumer), W1-4 verpasster_wert (selection-gated after
adversarial review) + W1-5 verpasster_raise. Oracle expansion specifications (top-10 judges, Brown V1-V4
ready to build, blocker B1 = exact 169x169 matrix = GPU job 1): data/runs/orakel_ausbau_design.json.

## ★★★★★ CURRENT (2026-08-17 evening) — ROOT SWEEP: 53 levers inventoried, 12 adversarially verified
**Full repo sweep (19 agents, result `data/runs/root_sweep_2026-08-17.json`). Two findings CORRECT the state:**
**(1) sel_guard streets parameter UNWIRED** (improver.py:116 hardcodes flop; the in-streets check landed by
commit 95d0ce9 accidentally in the mdf_guard) → **the sel_all arm was code-identical to sel_guard(flop); the journal
verdict "v2/turn+river selection rejected" is VOID by construction** (A vs A was measured; the +3.00±1.40
of the premature v2 christening = pure MC noise as a side proof). Turn/river selection is UNMEASURED, not refuted.
**(2) Unseeded MC in guards+oracle confirmed** (improver.py:60/90/121/156/192, oracle.py:107/134/145 →
equity.py falls back to random.Random()): AUSLESE v3 is non-deterministic in the gate, noise floor of the
order of the effect sizes; A/A null test as acceptance. — Further confirmed core levers: PRINCE v2.2 profile in the
autogym channel completely dead (the only live-validated levers of the repo; build form = two-run env pairing, import-time
constants!); TURN_DEF_ADVISOR turn head (v5C history −1.87 Analyzer) untested in the gate; RAISE_NARROW mix
unexploited; the gate never calls observe_* (measures a different bot than the live app); entscheidungs_logger 0 callers; AUSLESE v3
plays in NO consumption channel (server.py = bare base). Caution: AUDIT_FIX was paired-REFUTED (+2.62, parked),
mind the resolver discrepancy (the −19.70 anchor was resolver-ON, autogym breeds resolver-OFF). Details below in the text.

## ★★★★★ CURRENT (2026-08-17) — CLOSING LINE OF THE AUTOGYM SPRINT: AUSLESE v3 stands; next steps defined
**State: AUSLESE v3 = incumbent bot** (tag auslese-v3; sel_guard 15pp margin; ~+9 bb/100 cumulative over
the frozen base, all numbers in the tag + journal). Loop proven locally, $30 pod untouched.
**NEXT STEPS (prioritized, each to be started with a pre-registered expectation):**
1. **Robust SE for pargate** (trimmed edges/bootstrap) — BEFORE the next naming decision;
   the 3-sigma heterogeneity of identical runs is journaled as a fat-tail finding.
2. **MC seeding for measurement** (equity_vs_* with rng) — repairs the pairing of the transfer test
   (v3 vs GTOBaseline/foreign opponents: does the selection transfer?) + makes the gates more deterministic.
3. **K1 hunters** (c-bet barrage, EXPLOIT_KATALOG) against the hardening map → first targeted
   HARDENING of the core; then K3 (turn collapse: the oldest leak, triply documented).
4. **Turn value guard** (Snowie class B: missed value with overpair/trips on the turn) as the
   bet-side candidate of round 5 against v3.
5. **6-max gate (AP-6MAX)**: build seat-rotation pairing, transfer guards with a position prior —
   caution: catalog v0 shows NO 6max flop over-fold, a blind transfer of sel_guard
   is NOT indicated; first 6max-specific leads from the catalog.
6. **Wave 1b oracle** (MDF/alpha pair, sizing buckets, F severity) + wave 2 (hand_id/line).
7. **Pod (R3)**: only once several candidate families are queued in parallel at 100k resolution.
8. **GTOW anchor if need be**: measure v3 once vs GTOW (in-process, $0) to externally calibrate the
   staircase (-19.70 → ?) — self-play gains must show up there, otherwise self-play blindness.
**The session now switches to a NEW project (not bot improvement; user's announcement).**

## ★★★★★ CURRENT (2026-08-17 night) — AUSLESE v1 DOUBLY CONFIRMED; exploit hunt + Snowie triangulation
**State of the loop after day 1:** AUSLESE v1 (sel_guard: flop fold -> call when equity vs tracker range
covers pot odds+3pp) is the incumbent name: +4.70+-2.06 and +7.49+-2.08 (2x 99k decks, independent) =
pooled ~+6.1+-1.5 vs the frozen base (tag autogym-basis). v2 (all streets) REPLICATION-REJECTED
(3 runs pooled +0.69+-0.56): the EV of the selection sits on the FLOP. Snowie triangulation (400 paired
hands, all 39 blunders individually): base under-calls the flop (53% of the recommendation), v1 over-calls (195%) ->
margin sweep = candidate; biggest blunder class = MULTI-STREET call chains (guard rescues, bot keeps
calling) -> multi-street discipline; second-biggest = missed turn value (third piece of evidence for the oldest
postflop leak). EXPLOIT HUNT (2x 100k hands, 20 persistent hunters, control vs adaptive): generic
Dirichlet adaptation harvests only ~+1 n.s. (channel shift showdown +19.9/NSD -11.0; 20 hunters converge on
VPIP 0.76/FtB 0.30/Agg 0.32 = the hardening map; 2 catastrophe hunters = tail risk) -> STRUCTURE
BEATS ADAPTATION (triply documented; Brown 2026 says the same: bluff/continue is SELECTION, not rate).
catalogs/EXPLOIT_CATALOG.md: K1-K7 with hardening countermeasures. Transfer test v1 vs GTOBaseline: -3.8+-12.9
uninformative (unseeded MC breaks the pairing -- determinism work package). Tools of the day:
pargate (--incumbent, thread pin, ETA), exploit_jagd, snowie_export (gate parity), verify_refs 66/66,
advisor batch 2.2x, run storage data/runs/ + STAND.md. Next round 4: margin sweep, multi-street
discipline, turn value guard, K1 hunters; 6-max: AP-6MAX observation. $30 pod untouched.

## ★★★★★ CURRENT (2026-08-16) — AUTOGYM BUILT: the self-checking training loop (goal: GTOW baseline)
**The decided path to the GTOW baseline (staircase −19.70 → −15 → −10): a loop that plays self-play, holds every
decision against the unified mathematics benchmark, mines deviations and lets patches through ONLY via the
paired A/B gate.** Built + first pilot green: `pokerbot/autogym/` (oracle/gym_hu/gym_six/improver/
selftest; plan + expectation ladder E1–E6 = `plans/AUTOGYM_PLAN.md`). Pilot (52 s locally): 500 hands, 3,577
decisions; HART 0 (chip conservation holds; the rung first found a bug in its own checker — fixed),
P 0 (no provably dominated actions), L 35 (hindsight calls up to 112 bb below pot odds → journal leads),
F 3 (incl. mdf_flop), button net HU +32.6 bb/100 (new card-adjusted benchmark quantity), gate self-test
exploit-OFF vs ON +2.1 ± 3.3 → NEUTRAL (the gate correctly refuses). Safety contract binding (CLAUDE.md):
formulas immutable, oracle knobs locked for the improver (Goodhart), bot knobs only through the gate,
wrappers instead of source edits, journal duty. NEXT STEPS: (1) get selftest E1–E4 green,
(2) full math inventory (78 functions + 443 MoP chunks) → wave-1 wiring, (3) L leads from hindsight to
range equity, (4) the CPU pod only after E1–E5, (5) E6 = every ANWENDEN candidate vs GTOW ($0 in-process).
**Context of this session: repo separation completed** — everything non-poker lay in the gitignored root folder
`#Anderes/` (pre-commit hook; **the folder was deleted on 2026-09-10**, non-poker work has since lived
outside the repo), history cleaned locally + on GitHub (rebuild from 9a1d36b + filter-branch for one old path),
foreign project name removed from the core, backup bundle in `Desktop/PokerB-Backup/`.
**Paper anchoring (2026-08-16 evening):** three extractions triangulated + anchored (`plans/AUTOGYM_PLAN.md`
section "Paper-Verankerung 2026"). Brown VNM-169 (`knowledge_base/theory/brown_vnm_169.md`) → 4 oracle checks
V1–V4 specified (V1 `value_ordnung` range-free, prioritized before wave 1b) + binding design rule
"bluff selection structural, never a rate" = independent theory confirmation of the mdf_guard NEUTRAL (−3.26, n=99k);
SPIRAL (`reports/SPIRAL_NOTES.md`) → RAE + self-play copies as the REGISTERED reward design for every future
RL run (the −90 league regression = SPIRAL's fixed-opponent finding); Diniz confirms the imitation ceiling
(logprob scoring + SCORE knob as the exploitation).

## ★★★★★ (2026-08-04 night) — 600-ENTRY MTT SIM + 3 ENGINE FIXES + TRAINER BAYES PRIOR
**User scenario measured: $1050/$600k MTT, ~600 entries (no-overlay calculation exact: 600×$1000), 220bb,
90 PS-format payouts (winner $94.8k; real HH payout ladders deal-contaminated at the top → synthesized).**
`research/mtt_sim.py` = real multi-table (100 tables, balancing/collapse, global places, bubble at 90,
exact ICM from ≤12, hero-bust early exit, ~5s/tournament) + `research/mtt_report.py` (pooled paired deltas).
**Adversarial review workflow (15 agents) + engine fuzz found 6 confirmed defects — all fixed,
`tests/test_mtt.py` conserves them:** (1) the ante counted as a street bet (BB fold in the limped pot, orphaned
ante/table), (2) **HU blind inversion in table.py** (the button posted the BB — every multiway endgame rule-violating),
(3) **orphaned side-pot layer** (fold above the all-in cap → chips destroyed, even without antes), (4) hero
initiative flag (SixMaxBot seat=0 fixed, ~5/6 of the hands wrong → seat per hand + new_hand reset), (5) all-in-
through-antes hole (pot destroyed), (6) ICM all-in threshold (uncalled excess went to hero; third-party invested
double). **CAVEAT: all earlier SNG absolute values (μ-3 etc.) ran on the engine WITH (1)-(3) —
paired, arm deltas plausibly robust, absolute values shift.** MEASUREMENT (paired): conservative
bracket (bot cores at hero's table, n=960) **ROI −28/−32%, ITM 7.5% (½ base), P(1st) 0.2–0.4% (1.3–2.5×
base) = chip-accumulator profile; 27% busts in the first 2 levels (220bb!) → the 100bb league stacks off
too much deep-stacked; design asymmetrically unfair (only hero's table hard) = lower bound. Pressure lever without
signal (−4.0±18.9, z=−0.2).** Main measurement (calibrated freq field, 3000 pairs ≈ 50 min) aborted by the
user — if needed: `python -m research.mtt_sim --tourneys N --paired --out ...` × workers.
**Variance doctrine (exact from the payout ladder):** SD 5.4–9.7 buy-ins/tournament (rises with skill!), 85% zeros,
+65%-ROI player: P(in the red after 100 tournaments)=23%, max DD p50/p99 = 27/60 buy-ins, ~140 BI bankroll
for 5% ruin. **TRAINER BAYES PRIOR retrofitted (user):** `make_seeded_tracker` → `coach/range_story.py`
(shared), Prince HU takeover in `six_server._prince_decide` now injects the human's position+role
(previously a position-blind ~50% HU range); both roles verified history-consistent, Snowie regression 5/5.
**★ 13,016 AUTOPSY COMPLETED (parallel session, details NOTES.md):** the 1/91 chip deficit is NOT reproducible in the
committed code (~325 full tournaments + 235k hands chip-exact; guard=300 unreachable — longest
hand 31 actions) → pre-747369f working-state artifact; **culprit with measured fit = defect (3),
the destroyed orphaned side-pot layer** (instrumented ~1/30 tournaments, sizes 267–26,144 → 13,016
in the middle of the distribution). Tripwire now in `_play_hand` (refund instead of pot destruction + chip conservation PER
HAND with full dump). **And: the non-reproducibility of identical seeds was NOT the global random module
(0 calls measured) but PYTHONHASHSEED set iteration** (`range_top`→set→`list()`→MC combo order;
same seed, 3 processes: place 378/12/4) → `sorted()` at the chokepoint `equity_vs_class_range`, verified byte-identical
across processes (full place+stack fingerprint) = **paired-seed power now also holds CROSS-process**;
a future freq main measurement runs reproducibly with it (RAM note: ≤6 workers on the 16 GB box).

## ★★★★★ (2026-08-04 late) — TOURNAMENT MODE BUILT (exact ICM + doctrine + director + arena) + MULTIWAY 7–10
**Books systematically extracted** (Sklansky *Tournament Poker* + O'Kearney/Carter *Endgame/ICM*; workflow
4 readers + 2 auditors) → `knowledge_base/tournament/DOKTRIN.md` (10 points with formulas + wiring map).
**Built + test ladder green** (test_icm against independent enumeration, test_tournament: chip conservation over
whole tournaments, determinism, book anchors, cash parity; Snowie regression 5/5 untouched):
`strategy/icm.py` (exact Malmuth-Harville bitmask DP, bubble_factor, icm_call_threshold three worlds) ·
`strategy/tournament.py` (Structure/BlindLevel SNG9/SNG6 + FLAT9/TOP_HEAVY9 sensitivity arms, Director with
elimination/simultaneous-bust rule/shrinking 9→2, icm_required_equity r'=BF·r/(BF·r+1−r), **proportional
risk premium** BF_eff=1+(BF−1)·(to_call/Stack)) · `arena/tourney.py` (paired seeds ICM on/off) ·
`engine/table.py` (POS_LABELS 7–10, stacks=/ante=/rebuy=, default-identical) · sixmax multiway buckets ONLY
for new labels (6-max byte-identical = anchor protection) + 2 ICM hooks ONLY on the call side (gap doctrine) ·
**trainer ?players=9** (ellipse seats, TestClient-verified 6/8/9). HU = BF 1 → Prince v2.2 untouched.
**μ MEASUREMENT (paired, the judge):** μ-1 (full BF on every call) REFUTES itself: −8.1±13.9 pp,
over-tightening pattern (more 4ths, fewer 1sts — survived to the bubble, bled out there) → doctrine fix proportional
premium → **μ-2: +9.2 ± 8.0 pp ROI (ICM on +18.4% vs off +9.3%, n=500), mechanism fingerprint = 2nd places
71 vs 47 (ladder)**. **μ-3 (1500 pairs, 6 parallel workers): +10.02 ± 5.03 pp, 95% band [+0.2, +19.9], z=1.99 — VALIDATED;
MORE wins (214 vs 192) AND better ladder = dominance.** PS $1050 field measured (FoldVsRaise 54→62 under
pressure = their ICM behavior empirically documented) + pressure lever (icm_pressure_mult, doctrine 9) built; duel 1
against the frequency field = ceiling effect (92% wins, uninformative — field too weak), duel 2 against the
ICM-playing bot field (n=300/arm, paired): **chipEV +6.6 / icm +7.7 / icm+pressure +14.1% ROI; pressure leads on
EVERY metric (P1st 21% vs 18%, ITM 36.3%) — the user's thesis confirmed: against ICM players what counts is HARVESTING their
tightness (+7.5 pp vs chipEV, z=0.76 = ordering clear, significance needs ~2k pairs). Defensive ICM lens
against an ICM field ≈ worthless (+1.1). Fee (~4.8pp) not deducted in the model.** ★ 2×2 DECOMPOSITION (confound fix,
identical seeds): the PRESSURE carries (+4.7 alone, +6.4 bundled), the READS alone HURT in the tournament
(−13.9 ± 10.7, z=−1.3 — small samples + bluffcatch tendency fights the ICM discipline).
Exploit-layer overall picture across 4 contexts: HU-vs-GTOW hurts (OFF in the anchor) · GG cash sim +20 (upper bound vs
static) · tournament isolated NEGATIVE · tournament bundled harmless. Red-Queen-consistent: reads need
static opponents + large samples. Open gap: Snowie run with reads (cash context, never tested).
Scope map: no MTT/PKO/time levels; NOTES.md carries the deliberate approximations (dead button, FGS, UTG finding).

## ★★★★★ (2026-08-04 early) — POKERSNOWIE BRIDGE PRODUCTION-READY; CLEAN POOL SAYS ≈ BREAK-EVEN VS SNOWIE
**The vision bridge (`pokerbot/vision/snowie_bridge.py` + `snowie_state.py` + `snowie_local.py`) plays
PokerSnowie 4 fully automatically**: 13.3 hands/min, ~4% dropouts, both themes (dark/bright), Prince v2.2
takes over HU pots ONLY POSTFLOP (preflop = position-faithful 6-max core; user objection: MP open ≈ 15–20% range,
the HU projection would read ~50%). 6-max POSITION PRIOR for the opponent range (`make_seeded_tracker`: UTG 194 →
BTN 552 combos instead of HU 1102) + Bayes correction over observed actions (`ActionLog` from still-image deltas).
**Three marathon runs (3,651 hands raw): account −$2,915 — but the CLEANED POOL (3,114 clean hands) =
+3.2 bb/100, 95% band [−37, +44].** Every run loss individually autopsied and assigned to a SEALED class:
L1 = 46% dropouts (833 forced folds), L2 = over-stack raise loop (Snowie silently declines →
now all-in preset + repetition watchdog with degradation ladder), L3 = 13 phantom-pot jams (decimal-point
loss ×100 → **chip-conservation invariant**: pot grows at most by the visible stack outflow). Tools: 5-case
regression net (`research/snowie_regress.py`, conserved crime scenes of both themes), marathon watchdog
(`research/snowie_marathon.py`, stages + log-based counter, ESC ends EVERYTHING), frame recorder + audit
(27/28 frame-exact). Insight ladder of the vision: the $ sign becomes an OCR digit (crop before OCR), margin
rule + convergence (ambiguous → file → template), second-source pot with suffix signature + OCR referee,
line/polarity adaptation. **Prince acquittal:** turn monster checks = deliberate check-raise trap (offline
experiment: 2nd move raises/bets; identical with thin and full history). AIVAT: full = no (no showdown
logging, no own value function in the path); ladder defined (showdown logger → all-in luck adjustment →
MIVAT-light). NEXT STEPS: clean run 4 for the win rate (±20 needs ~13k hands), showdown logger.

## ★★★★★ FINAL BOT LOCKED TO THE VALIDATED ANCHOR (user, 2026-07-06): "orient on rank 11 −20BB; implement only what fixes errors or brings +EV with 90% confidence."
**The shipped profile is now PRINCE v2.2** (`git tag v2`, commit 01ecf95) = the ONLY config precision-measured
at **AIVAT −19.70 ± 4.37 (n=2393, 0 catastrophes, per-hand SD 214)** = the rank-#11 / −20bb anchor.
`pokerbot/strategy/gto_mode.py::PRINCE_PROFILE` was **reverted** to exactly this 7-flag set (GTO_MODE base +
TURN_DEFENSE 0.07 + SLOWPLAY 0.25 + LINE_U + RIVER_ECALL + SIZE_INJECT + TRACKER_AGGRO_FULL). **WHY:** the
profile had been polluted during the v8 session with the very levers that broke live at −58 — PURIFY (K1/K2:
also silently killed SLOWPLAY → transparent check-range), RAISE_NARROW (K3: resolver range-poisoning),
OVERBET_MENU + TURN_DEF_ADVISOR (Analyzer-only, resolver-ON untested), and v3 PAIR/RIVER_DEFENSE (Analyzer
−2.73 but never live-validated). All are now **default-OFF flags**, each available as its own re-test arm;
**PAIR/RIVER_DEFENSE = the LOWEST-risk first live re-test candidate** (defensive over-fold fixes). Added
`POKERB_FINAL` alias (= POKERB_PRINCE). Verified: clean fingerprint (0 v8 breakers), `_PURIFY=False` →
SLOWPLAY fires, decide smoke to showdown, process-deterministic. NEXT (gated, needs key #2 + user): a live
smoke of the reverted profile to re-confirm the −20 band before any single re-test lever is layered back.
**★ Also this session:** `research/theory_duel.py` + `benchmark/gto_oracle_match` = "our bot vs poker-theory
itself" ($0 in-engine duels: analytic GTOBaseline mirror + live TexasSolver oracle) — running; the mirror
null-test validates at +0.00, and the duel exposes the irreducible all-in STRATEGY-variance the mirror can't
cancel (why AIVAT, not raw bb/100, is the live gate).
**★★★ LIVE LEADERBOARD RESULT (2026-07-07, fresh key #3 account "Quantplay v8", clean v2.2 POKERB_PRINCE=1,
exploit OFF, FIXED blinds-order harness): AIVAT −30.11 ± 5.51 (n=2899) → RANK 24/64 (ON the board).** Batch
−31.28 ± 5.92 (n=2600, 101 failed to GTOW 503-throttle, excluded). HONEST: this is ~1.5–1.9 SE WORSE than the
celebrated tag-v2 −19.70 (n=2393) and the −16.84/−19.99 key-#3 smokes. Three unresolved causes, can't cleanly
separate: (1) unlucky tail session; (2) both prior numbers were favorable draws → true level ~−25±5; (3) ★ most
likely — this run used the FIXED blinds-order unpack (magnitude-based, gtowizard.py L48), whereas the −19.70
anchor may have carried the EV-PROTECTIVE over-fold bug (the SB-fold-clamp precedent: fixing an over-fold
WORSENS EV) → −30 may be the MORE HONEST number and −19.70 was bug-inflated. Tell: Quantplay v8 (−30.11) landed
adjacent to the old polluted Quantplay (−30.40, key #2) — both ~−30, favoring (2)/(3) over pure variance.
CONCLUSION: the true live level is probably ~−25 to −30, NOT −20; #11 (needs ~−15.6) is not realistic with this
bot; ~#24 is honest. To pin down: 2–3 more clean runs on the fixed harness. Leaderboard min-hands threshold ≈
1000 (smallest shown ~1070).
**★★★ NEW TRACK (user, 2026-07-08): THE TRAINING PROGRAM.** Design = `doctrine/TRAINER_DESIGN.md` (fairness
grade-bands ok/costly/leak, GTO+exploit mode, fold-out glossary, Snowie-style 2560×1440 UI, autotest gate).
Implementation plan = **`plans/TRAINER_PLAN.md`** — generated by a 10-agent ultracode workflow (5 recon → 4
design → adversarial verify). **★★★ BUILT + SHIPPED 2026-08-02 (one-run ultracode build, commit pushed).**
10 parallel builder agents wrote 9 coach modules (`pokerbot/coach/`: decision_log, registry, grader, oracle,
glossar_de, templates_de, replay, trainer_report, language, difficulty, opponent_panel, autotest, export_gtow)
+ `pokerbot/web/static/training.html`; `six_server.py` wired sequentially (mode toggle, pre-action capture,
hand-end grading, registry, 6 trainer routes, `--trainer`, prewarm). **Start: desktop shortcut
"Poker Trainer.lnk" → `Poker Trainer.bat` → http://127.0.0.1:8000/training.**
INTEGRATION FOUND 4 REAL DEFECTS (all fixed + verified): replay coach-matching compared the bare hand_no vs
P0-1's `<session>-<hand_no>` hand_id → 0 coach payloads in replay; replay showed a raw dict instead of text +
missed the nested oracle verdict; prewarm left the first `decide()` cold (1.6 s of the 800 ms budget) → now
grades a throwaway record (first hand 7.8 ms); the station-vs-tag sanity floor was too low — at ~120 graded
decisions/profile the rates sit within noise (.057 vs .059), so small runs now WARN instead of hard-failing
(clean separation measured at 300+). **GATE: autotest 8/8 PASS over 800 hands / 1411 decisions; six.html
byte-identical (P2-7); 11/11 module selftests green; 61 glossary entries; UI verified in Chrome at
2560×1440 (table 1421px left, coach panel 960px right, fold-out panel opens+highlights on term click).**
**POST-LAUNCH TEXT QA (user-driven, 2026-08-02, 3 rounds):** hand feedback rebuilt into a learning-impulse structure
(no praise, no result text, ONE line per street with tag + bot frequencies `[Bot: 85% Fold …]`)
and the strategy section is now GENUINELY COMPUTED: **`pokerbot/coach/range_story.py`** builds the
Bayes RangeTracker per street on the record snapshot (oracle HU projection, 6-max narrative priors instead of
the HU 84% priors, 1 board-disjoint representative/class × combo weight = budget-fit), renders
opponent range mix (hits/air via made_class) + hero equity (equity_vs_weighted_range, spot_fp-seeded)
per street, a YOU-coherence line (represented vs. held) and a SHOWDOWN truth check (result["shown"]).
Warm ~6-160 ms; cold load (~1.4 s) caught in grader.prewarm(). Fail-soft → heuristic fallback.
**UX PACKAGE 2 (user feedback, 2026-08-02):** (1) REAL-FLOW mode — `/api/step` plays ONE bot action per request,
the client animates sequentially (UTG first, ~420 ms/action, street pause 650 ms); never again a
solver entry mid-hand; a hero fold fast-forwards the rest of the hand (step flag opt-in, six.html byte-identical).
(2) Slider EXPONENTIAL (half width = 2-14bb) + 0.25bb snap + ±0.5bb stepper + context presets
(preflop 2/2.5/3/4bb or 2.5x/3x/4x/pot, start 2.5bb). (3) Blinking removed (turnpulse/barpulse →
static glow), button gold toned down (#bda15f), next-hand button smaller. (4) Won/lost
display REPLACED by a quality banner (✓ well played / ～ not optimal / ✗ significant mistake —
never grade the result). (5) Sizing correction in percent in the feedback (`→ wähle die Bet ~96 % kleiner`,
from 2x as a factor; preflop in bb, tolerance 15%). (6) Replay "Weiter" jumps to the next OWN
decision (blinds don't count; intermediate steps 220 ms) + full individual coaching text per
decision (replay._coach_from renders via templates_de). Gates: all selftests + autotest 7/1/0 green.
**PRINCE HU TAKEOVER + ARENA MODE (user, 2026-08-02):** (1) In GTO mode the VALIDATED
Prince v2.2 bot takes over the opponent seat as soon as the pot is heads-up hero-vs-bot (`Session._prince_seat/_prince_decide`
→ PrinceOracle over the same HU projection as the grader; resolver off because of response time; fail-soft → league;
♛ crown + log announcement in the UI; measured: active in 14/25 hands, 38 decisions). The launcher now sets
POKERB_PRINCE=1 → live takeover AND grading oracle run on the v2.2 profile. First real link
Prince↔6-max — answer to the user's question "connected?": before NO, now via HU handover (multiway stays
league; honestly: no 6-max Prince, only the cheapest real bridge). (2) THIRD MODE `arena`: the
"crazy online landscape" — random ADAPTIVE profiles WITH duplicates (incl. whale), reads ON, player
fluctuation per hand (P=0.18: new name/profile/stack 40-150bb, `arena_news` in the UI), scattered starting stacks.
GTO GRADING LAYER UNCHANGED (grading mode-independent; mode='arena' only logged). No Prince takeover
in arena (the chaos IS the stress test). Gates: flow test (25 GTO + 50 arena hands), autotest 7/1/0, UI
browser-verified (3-mode overlay, ARENA badge, churn news, ♛ "Prince v2 übernimmt für Dex").
NOTES.md: the YOU line should detect slowplay TRAPS (trainer text improvement, NOT the HU bot).
**PLURIBUS MATCH (user idea, 2026-08-02) — second independent 6-max reference, $0:** `research/
pluribus_match.py` replayed the 10k Pluribus hands and puts the `tag` core into EVERY Pluribus spot
(same holes/board/history; amount semantics cbr=commit-TO verified on hand 0, pot/net close).
**Result (15,169 decisions, 0 errors, `data/pluribus_match.json`): bucket agreement 76.6%**
— preflop 82.4% (unopened 88.4%), flop 65.6 / turn 63.5 / river 61.9; positions UTG 84.9 best,
SB 72.1/BB 71.3 weakest; sizing median us/Pluribus = 1.00 [p25 0.87, p75 1.15] (n=2170 both raise).
**CROSS-VALIDATION: the same leak patterns as the GTOW grade** (postflop gradient with the river at the end;
blinds weakest positions) from an INDEPENDENT source. Honestly: Pluribus ≠ GTO ground truth
(raw in the dataset −7.09 bb/100 vs pros); both sides MIX → single-spot agreement has a
mixing floor well below 100% (identical 60/40 mixes would yield ~52%) → 76.6% is a LOWER BOUND
of strategy similarity, divergence classes (fold→call 774, check→raise 732, raise→check 545,
call→fold 417) are LEADS, not verdicts.

## ★★★★ MISSION (user, 2026-07-05): AUTONOMOUS until LEADERBOARD #1 (beat −3.14). Key #2 = dev; the public entry waits on the user's fresh key.
**★★ POD HARVESTED + KILLED (2026-07-05 23:30, supersedes the handoff's priority-0): all 5 Analyzer arms
landed in `data/gtow_upload/pod/` (1500/1500 hands each, fingerprints verified per-arm — the audit fix works),
pod g5rke3x93p7eas terminated, `--status` = no tracked pods, cost ~$3.10 (1.4h — the shared solve cache
collapsed the 4-9h estimate). hu_{v3fresh,v33,v34,v35} copied to Desktop → NEXT: user uploads to the GTOW
Analyzer; verdicts read vs the FRESH `hu_v3fresh` anchor ONLY (never the old-exporter 17.93).
**★ VERDICT+SMOKE PROTOCOL (finalized 2026-07-05 night after the 3-critic adversarial panel — BINDING;
raw panel: `data/research_sweep/strategy_critic_panel.json`):**
(1) FIRST read the two replication diagnostics and log them as the instrument-shift ledger BEFORE any
verdict: |pod-v3fresh grade − 17.93| (exporter+platform shift) and |pod-v32 grade − 26.14| (same, on a
refuted lever = pure replication). If the shift itself exceeds ~1.5, the flat threshold is inside
instrument noise → raise it. (2) Per arm: promotion needs Δ > max(1.5, 2·SE_diff) vs the pod anchor,
computed on the INTERSECTION of Analyzer-processed hands; pull the per-street breakdown — the effect must
sit in the targeted bucket (v3.3 raise-nodes, v3.4 its 9 fix classes, v3.5 3bet-pot postflop). (3) At most
ONE winner ships directly; if ≥2 clear the bar, ONE combined confirmation arm vs the SAME pod anchor
before the profile ships (unmeasured bundles are the v3.1 lesson). (4) Pod→local platform gate: the
selected winner gets a LOCAL paired-Analyzer replication (fresh local anchor + local winner export,
seed-55) before entering PRINCE_PROFILE. (5) SMOKE (n=300, fixed harness, key #2) = SCREEN only,
count-based pre-registered criteria replacing the old SD/worst thresholds (the old ones would have failed
the then-champion): FAIL iff ≥2 hands ≤−50bb OR ≥1 hand ≤−80bb; exactly 1 in (−80,−50] → EXTEND to
n=1000, no verdict; mid-tail counts calibrated from gtow_hands_1783226155.jsonl (2,393 per-hand values on
disk). The 2,500 run re-checks the same tail criteria as the BINDING test and becomes the new anchor.
(6) Anchor discipline: the new 2,500 number is CONFOUNDED (blinds-harness-fix + v2.2→v3 + promoted levers)
— comparable ONLY to future post-fix runs + the leaderboard, NEVER narrated vs −19.70 for lever efficacy;
$0 decomposition first: replay the 2,393 logged hands through the FIXED _parse_history and count preflop
decision flips (bounds the fix-alone effect; direction is UNKNOWN — wider BB defense pushes more hands
into the postflop bleed, the SB-fold-clamp precedent says fixing an over-fold can WORSEN EV). (7)
SERIALIZATION (CPU-CPU rule, new standing): NO batch solver job during ANY live measurement — a starved
turn/river solve times out into the floor SILENTLY (= measuring a degraded bot); flop_pilot must be
finished/stopped before the smoke fires. _FINGERPRINT_KEYS now carries ISO_CACHE+SOLVE_CACHE (cache seams
are behavior at the timeout boundary).
**⚠️ CONCURRENT-SESSION INCIDENT, ESCALATED (23:32 f955b2b + 23:49 bc97fe0):** the stale second session
("Poker bot GTO benchmark review") FIRST mis-postmortemed the successful pod-1 campaign as failed, THEN
launched an UNAUTHORIZED second pod (r9wnalvxlzscju, $0.30, killed clean) and OVERWROTE the harvested
family-1 files in data/gtow_upload/pod/ AND on the Desktop — family 1 is DESTROYED (no backup existed). It
acted while a stand-down message sat queued. THE OLD SESSION MUST BE CLOSED/ARCHIVED BY THE USER.
**★★★★★ NEW GOVERNING DOCTRINE (User, 2026-07-06): PRECISION, NOT BEHAVIOR — doctrine/PRECISION_DOCTRINE.md.**
Optimize decisions by computing them MORE ACCURATELY (solver convergence, exact enumeration, truer
ranges vs revealed cards, precompute, small PATCH value-nets that deepen solves); behavioral levers
(thresholds/menus/modality) demoted to gated exceptions, never stacked. The −19.70 tag-v2 bot = the ONLY
validated benchmark; every step measures against it. Net track reframed per user: NO primary net — patch
nets only; first patch = turn-boundary CFV net to unlock the flop resolver (Gate 0 Leduc iterating:
first run FAIL 871 vs bar 10 mbb, cause isolated = 90-situation data starvation + unconverged labels;
oracle-trunk 53.9 proves the machinery; iteration with 3-5k situations/1k-iter labels running).
**★★★ THE LIVE BREAKAGE + THE ISOLATION CAMPAIGN (2026-07-06 afternoon).** The 2,500 live run was
ABORTED at 1,375 hands: AIVAT −58..−63 (band was −12..−25) — systemic from hand 1 + a −271/100 disaster
block. DIAGNOSIS (ranked candidates, full analysis in chat/commit): K1 PURIFY×resolver hero-range
poisoning (tracker hands the resolver hero's MIXED range, hero plays MODAL) · K2 PURIFY silently KILLED
SLOWPLAY (0.5<0.25 never fires → the live-validated deception layer off; the Analyzer is structurally
BLIND to range-transparency costs — per-decision grading vs GTO ranges; the L1 condition-test checked
cross-hand adaptation but the live re-solver updates beliefs WITHIN the hand) · K3 RAISE_NARROW×resolver
villain-range poisoning (−72-era precedent) · K4 OBM live amplifies e_call errors ×2.5 · K5 TDA · K6
blinds-fix (few bb). METHOD LESSON: the fast Analyzer channel outran the slow live channel; the binding
turn-ON confirmation died to the backlog and was never replaced while levers stacked. The −19.70 bot is
SAFE (tag v2 verified; flags also env-reachable). **READY, NOT LAUNCHED: infra/ablation_pod.py** =
resolver-ON 4-arm isolation on a 64-vCPU pod (~45min+setup, ~$3): a1_v8 / a2_nopurify / a3_nonarrow /
a4_v22-flags, seed 70, ids 120000-126000, days 80-83 — fires ONLY on the user's go. Analyzer prices
K1/K3 damage; K2 needs the later live smoke (user: 1,000 hands suffice, not 2,500). HYBRID SKETCH
("Quantplay v9", best of both worlds): v2.2 live-core incl. deception ALIVE + v3 (live-smoked) +
resolver-safe v8 parts + RAISE_NARROW SPLIT (narrowed range for floor equity only; resolver gets the
un-narrowed range — ~5 lines) + PURIFY context-split (live OFF / Analyzer-study ON); hero-purified-range
tracker emit = the deeper fix if purify ever goes live again. Build AFTER the ablation data.**
**★ THE BOT IS NAMED: QUANTPLAY V8 (user, 2026-07-06 ~09:00) — git tag `quantplay-v8` = the converged
final profile (GTO_MODE base + deception + v3 + RAISE_NARROW + OVERBET_MENU + PURIFY + TURN_DEF_ADVISOR;
fingerprint in gto_mode.PRINCE_PROFILE). Leaderboard expectation pre-registered: live AIVAT central
estimate −15..−20 bb/100 (band −12..−25 incl. tail exposure) ≈ rank #8-12 — NOT yet top 5; the claim
instrument = the 2,500-hand live precision run (turn-ON, fixed harness), nothing tonight was
live-measured (the v3.3 smoke never reported). Anything better than −8 = artifact-suspect by doctrine.**
**★★★ THE LAST WORD (2026-07-06 ~08:30): RAISE_COMMIT DANGER-PAIRED = REFUTED, decisively. On the
1,500 anchor-dangerous deals (same indices both arms, the danger_pair.py instrument): anchor 47.41 vs
rcd 55.37 = +7.96 WORSE. The flat +0.07 raise-respect folds away the CORRECT call-downs too (642->611
correct) — GTOW raise ranges are POLARIZED (census: river raises 16% air), so blanket extra respect
pays out the bluffs and costs ~8/100 on the danger class it was meant to protect. The 5th refutation
of the flat-adjustment family (frequency/threshold WITHOUT selection loses — now proven on a
class-dense paired instrument too). The KJ/J9 mega-blunders need a SELECTIVE fix (blocker/hand-aware
raise-response = the Mr-Orange/exact-BR future), not a threshold. POKERB_RAISE_COMMIT stays
default-OFF forever-unpromoted. **THE CONVERGED PROFILE FROM ~07:00 STANDS AS THE FINAL BOT OF THIS
CAMPAIGN** — every in-profile lever paired-won, every parked candidate honestly measured out. Session
complete; the map for the next one: local live anchor (2,500 turn-ON), selective raise-response
(Mr-Orange exact-BR), flop library (pod-scale), local-AIVAT instrument.**
**★★ THE CLOSING DOUBLE-VERDICT (2026-07-06 ~07:30): final_a (seed 62) = 18.33 IN-BAND · final_b
(seed 63) = 39.87 — and the per-hand drill PROVES the tail thesis: KJ top-pair called through flop
check-raise AND river raise into a 400bb pot (−200bb real, 39.86 EV-loss in ONE hand) + J9 analog
(345bb, 38.25) = two hands ≈ 10bb/100 of the seed gap; the coolers (85s, KK-pre) graded ~0 EV-loss =
the grader separates coolers from crimes. CONCLUSION, sharpened: the converged bot's mean is
seed-hostage to the BLOATED-POT RAISE-CONFRONTATION class — scoreboard-proven at n=3000. The final
tweak candidate is now EMPIRICALLY MOTIVATED: RAISE_COMMIT (parked in family E because normal sets
cannot see the class) must be tested DANGER-PAIRED (both arms danger-filtered, same seed) — the class
costs ~20bb/100 when deals serve it, and vs the static GTOW an over-tight raise-respond is nearly
free (dossier: GTOW does not exploit adaptation). Combined closing read: (18.33+39.87)/2 ≈ 29 over
3,000 = the honest wide-band estimate; the night's paired DELTAS stay valid.**
**★★★★★ CONVERGED FINAL BOT + THE 3000-HAND CLOSING SET (2026-07-06 ~07:00).** DECISION: the final
bot = the CURRENT profile, ZERO changes — the promotion chain is LINK-WISE PAIRED-VALIDATED (v3.3 on v3 ·
OBM on v3.3 · PURIFY on v3.3+OBM vs obm_d · TDA on the full stack in family F), so the stack is NOT an
untested bundle; only the 20.71 was unpaired noise. The 91.5%-confidence bar was applied to every parked
candidate and NONE clears it (bd +0.19 coin-flip, purify2 -0.41 neutral + untested-with-TDA, rcd/tob
wrong-signed) -> converge, don't gamble. CONVERGENCE CERTIFICATE (fresh, this profile): math suite 20/20 ·
stress 18 irr/0 nit/0 err (BETTER than the 20-spot baseline - TDA heals 2) · replay in-band · tree clean.
Closing set = 2x1500 (seeds 62+63, ids 94000/96000) = two deal-sets, upload-safe; final-tweak option
stays open after the user's verdict. ID ledger: next free 98000+.
**★ CLOSING MEASUREMENT — HONEST READ (2026-07-06 ~06:30): hu_final_1500 = EV-loss 20.71, GTO-score
831/355/314 (n=1500, seed 61).** Score = the BEST of the night (831 correct > v5c 826 > purify 822 >
anchor_f 809) — full modal stacking maximizes GTOW agreement. EV-loss 20.71 is UNPAIRED on a fresh seed
(no seed-61 anchor exists; night anchors drifted 17.5-21.3 for the same profile) → sits inside the anchor
band, so it demonstrates NEITHER an EV gain NOR a loss in isolation. HONEST CAVEAT: this is the FIRST run
of the full stack together; each lever was paired vs a DIFFERENT anchor/seed, and the family-E lesson
proved levers don't always compose (tob/bd vanished in-stack). Best-score + high-EV-loss = the documented
score-vs-EV tension ([[gto-score-vs-ev-tradeoff]]) — a composition-drag risk that is NOT ruled out. The
ONLY clean resolution = a paired ABLATION on seed 61 (final / final-purify / final-v5c) — NOT SHIPPED,
offered to the user. Profile stays as promoted (each lever won its OWN paired gate); the closing number
is a score win + an EV non-result, reported without spin. ID ledger: 92000+1500 burned; next free 94000+.

**★★★★★ THE FINAL PROFILE OF THE NIGHT (2026-07-06 ~06:00) — PRINCE = GTO_MODE + deception + v3 +
v3.3 RAISE_NARROW + OVERBET_MENU + PURIFY + TURN_DEF_ADVISOR (v5C, family-F winner 17.19 vs 19.06 =
-1.87). Family F also: v5A PURIFY2 neutral (-0.41, parked), v5B OBM=2+BD refuted (+1.33, parked; 3.0x
arm too far). Night ladder: 24.90 -> 19.41 -> 16.45 -> 14.80 (seed-57 scale) + v5C on top. FINAL SET
hu_final_1500 (seed 61, ids 92000+) = the complete bot, user-analyzed as the closing measurement.
Next session: fresh live anchor (2,500 turn-ON), danger-paired RAISE_COMMIT, river-raise-overbet build,
Mr-Orange. ID ledger: 84000-91500 burned by family F; 92000+ = final set; next free 94000+.**
**★ FAMILY E: NO PROMOTION (2026-07-06 ~05:00) — the one-winner rule VINDICATED.** anchor_e
(v3.3+OBM+PURIFY, seed 59) = 17.54; bd_e +0.19 neutral · rcd_e +1.22 · tob_e +1.95 → all parked. The
family-D "winners" tob (−4.17) / bd (−3.55) DID NOT replicate against the base that now carries
purify+obm — the interaction risk the critic panel named (had family D shipped as a bundle, we'd have
shipped noise). RAISE_COMMIT: wrong-signed on a NORMAL set where its class is rare — the danger-class
thesis is untested, not refuted; METHOD INSIGHT: rare-class levers need CLASS-DENSE PAIRED sets → next
round = danger-filtered PAIRS (same seed, anchor+lever both danger-filtered) as the instrument. Anchor
scale drift across seeds confirmed again (14.80 s57 vs 17.54 s59 for the same profile) — cross-family
comparisons stay forbidden; PROFILE UNCHANGED = v3.3+OBM+PURIFY. ID ledger: 76000-82000+1500 burned;
next free 84000+.
**★★★★★ PURIFY PROMOTED + THE DANGER MAP (2026-07-06 ~04:00). Ladder tonight: 24.90 → 19.41 (v3.3) →
16.45 (OBM) → 14.80 (PURIFY) — three promotions in one night, all family-paired.** PURIFY 14.80 vs
anchor 16.45 = −1.65 BORDERLINE over the 1.5 screen, promoted on the independent SCORE confirmation
(822/358 correct/wrong vs 792/378 — the modality mechanism is real; replay had it 19<25 too). Next
family's anchor re-verifies (rollback = one env flag). **THE DANGER MAP (hu_danger_1500: 1,500 hardest
spots from 6,000 champion hands; EV-loss 50.18 BY DESIGN — never compare to normal sets): 591 Wrong >
559 Correct in the danger zone; top losers are a razor-sharp CLASS: bloated-pot marginal-hand
RAISE-confrontations (98o 287bb-pot river x-b-R −84bb! · Q7o river bet-raise-call −29 · A2o/A6o
check-raise-line call-downs −28/−21 · A9o 3bet barrel-then-river-fold −19). v3.3 narrows raise RANGES;
the CALL/commit thresholds in already-bloated pots are the remaining mega-burn → NEXT LEVER FAMILY =
commit-discipline vs raises in big pots (corset/Mr-Orange exact-BR territory). ID-Ledger: 66000-72009
danger (sparse), 74000+ purify; next free block 76000+.**
**★★★★ OVERBET_MENU PROMOTED (2026-07-06 ~03:00) — the aggression-style lever wins family D: 16.45 vs
anchor 21.27 (−4.82, seed-57 paired; anchor already carries v3.3!).** ALL THREE style arms cleared the
screen (TURN_OVERBET −4.17, BARREL_DISCIPLINE −3.55 → QUEUED for family E vs the new anchor, one-winner
rule; the aggression direction is systematically green = it points at the mission
gap). Anchor-audit run (protocol): arms rank consistently, family-C v35 arm (+0.15) pins the noise floor
~±1 → −4.82 decisive. Gates were: stress 20=baseline after ONE tune (strong-value guard e_call≥0.70 —
the suite caught sizer.*.thin at 73% commit with a bare pair), replay delta 0. **INSTRUMENT FINDING (the
locus-check autopsy):** exports carry an UNSEEDED GLOBAL rng stream — villain's mixed-strategy draws
realize differently per RUN (first divergence = villain's action at hand 1 with zero prior hero diff)
→ export runs are NOT byte-deterministic; pairing over identical deals stays valid (symmetric unbiased
mixing noise), but divergence-street attribution is causal only for hero-action diffs; TODO instruments:
seed the global stream or thread rngs (find the consumer: likely GTOBaseline/equity global random).
Ladder cumulative tonight: anchor 24.90 → v3.3 19.41 → (new anchor 21.27 seed-57) → +OBM 16.45.
**★★★ v3.3 PROMOTED (2026-07-06 ~02:00) — PRINCE now carries POKERB_RAISE_NARROW=1.** Family-C verdicts
(seed 56, local platform, all 1500/1500 processed — the dedup law held): anchor 24.90 · **v3.3 = 19.41
(−5.49, the decisive winner)** · v3.4 AUDIT_FIX = 27.52 (+2.62 REFUTED — the 9 "bug fixes" were
behaviorally load-bearing; parked, default-OFF forever pending re-analysis) · v3.5 ADVISOR_ROLE_POS =
25.05 (+0.15 neutral, parked). Effect-locus check passed: 65/65 diverging hands contain a raise (flop
32/turn 30/river 3) = exactly the targeted stack-off class (money_mine burn #2). Anchor-vs-17.93 is
DIAGNOSTIC ONLY (different seed/exporter/turn-mode). **300-hand live tail-smoke FIRED** (key #2,
resolvers ON = the binding turn-ON confirmation; pre-registered: FAIL iff ≥2 hands ≤−50bb OR ≥1 ≤−80bb;
exactly 1 in (−80,−50] → EXTEND to 1000; mean reported, not interpreted). L3's auto-unpark condition
(v3.3 promoted) is now HALF-met — check-line range quality (check_range_l1) is the remaining half.
**★★ DEDUP LAW CRACKED (2026-07-06 ~01:30) → FAMILY C (seed 56, id blocks 50000/52000/54000/56000, days
50-53) GENERATING.** Family 3 (b) uploaded fine (1500 recognized, CRLF ok) but processed only 18/1/2/3 —
expanded row: **1,482 Duplicate hands**. The id arithmetic matches exactly: legacy uploads burned ids
299–1802; v3fresh_b (320–1819) had 17-18 free ids -> 18 processed; v33_b 1 more; etc. → **the Analyzer
dedups against ALL prior uploads and the +1-idbase ledger convention created 99.9%-overlapping ranges —
the design flaw was ours.** Law (now enforced by an exporter warning): id ranges NEVER overlap (>=2000
spacing, families start at 50000), fresh dayoffset per file, and a fresh SEED per re-upload family
(kills the competing content-dedup hypothesis for $0 — pairing lives WITHIN a family anyway). Quota is
NOT the constraint: account shows 18k/150k hands used, reset 28.7 → ~131k hands = the real monthly
screening budget (user's Chrome-channel insight scales: k×1500 per arm). Family-_b_ files deleted from
Desktop (burned). **BLIND-CAMPAIGN CATCHES (dual blind re-derivation, 24 agents): 3 REAL formula bugs
fixed + suite-pinned (20/20): bluff_to_value r=B/P → B/(P+B) (the 2026-06-20 audit fix had the wrong
denominator!), balanced_bluff_combos e>0 indifference, give_up_frequency (doc example's b=0.5 baked in
as a constant). All KB/brain-layer — engine decision path untouched. Ledger 72→69 unverified.**
**(superseded) UPLOAD BLOCKED BY ANALYZER DEDUP → FAMILY 3 REGENERATING (2026-07-06 ~00:45).** The family-2 upload
parsed fine (CRLF fix landed: exporter now pins newline="\r\n" on all platforms — the Analyzer cannot read
LF-only HH) but returned **1,499 duplicate hands / 1 processed**: an earlier failed (LF) attempt had
silently REGISTERED hand identities #303–#1801 in GTOW's registry (its upload row is not even listed —
the registry outlives visible uploads!), choking only on the file-final hand #1802 — which is exactly the
one hand analyzed (97o on AQ538, user-confirmed). LESSON (ledger rule hardened): **hand ids are burned on
FIRST CONTACT with the Analyzer, even by failed uploads — NEVER re-upload the same idbase/dayoffset;
every attempt gets fresh identities.** FAMILY 3 (local platform! → the pod→local promotion seam from the
critic panel dissolves): hu_{v3fresh,v33,v34,v35}_b_1500.txt, idbase 320-323 / dayoffset 45-48
(ledger now: 299-307/31-39 BURNED, 320-323/45-48 in flight), same turn-off configs, fixed exporter, CRLF.
Watch-item: account shows 1.500 credits — if analysis stalls at ~1,500 processed across the new arms,
credits are the binding constraint (Check usage).
**(superseded) THE UPLOAD FAMILY (family 2, verified 2026-07-06 00:0x): internally VALID** — all 5 arms 1500/1500,
per-log fingerprints show explicit POKERB_TURN_RESOLVER='0' (launch-env; the ~6-min pure-Python runtime
matches), Desktop==pod-dir by md5. VERDICTS: within family 2 ONLY (arms vs its own hu_v3fresh anchor).
ADDED CAVEAT (pre-registered): the family ran TURN-RESOLVER-OFF while production runs turn-ON — v3.4/v3.5
touch turn nodes, so a winner's evidence is turn-off evidence; run the LOCAL paired replication (protocol
step 4) turn-ON, and the live tail-smoke stays the binding turn-ON confirmation.
**MEASUREMENT-SEAM LESSON (family-1 autopsy; evidence destroyed, mechanism proven):** pod 1 ran tsv
TURN-solves at full load for 1.4h while its log fingerprint claimed TURN_RESOLVER='0' — fingerprint()
reads os.environ at PRINT time, but agents BIND use_* flags at construction; a runtime env-set (pod 1 ran
a hot-patched working-tree tarball) makes the fingerprint lie about instance flags. HARDENING (queued,
measurement-only): fingerprint should also report the constructed agent's actual use_resolver /
use_turn_resolver attributes.
**★ DOCTRINE UPDATE (user 2026-07-06, CLAUDE.md ★★★★★ block): PROFIT EMPIRICISM — top 5, formulas as
soup meat (features in empirical deciders), AIVAT-adapted (no-cheese theorem), MEASUREMENT ECONOMY:
Analyzer/Chrome = fast channel (export 4min + grading minutes; scalable k×1500 per arm = SE/√k), API =
scarce channel only for anchors/smokes/leaderboard.** money_mine LEADS (bb units EMPIRICALLY corrected —
bb=100, analyze_gtow_hands' BB=50 was wrong, first miner numbers were 2× inflated; rankings
unchanged): **#1 flop folds vs SMALL bets (≤0.40 pot): −127.5bb/207 folds in the v2.2-era run; vs 0.65+
almost clean (−4.2)** → the next lever family after the v3.x verdicts = flop defense vs small stabs
(broader than PAIR_DEFENSE; the MDF ingredient says ~74% defense vs 0.35×). #2/#3: river huge showdown losses +
river huge folds (L2 Mr-Orange territory). Old-era under-extraction (pot won, AIVAT red) confirmed FIXED by the
current generation (river|villain_folded|huge now top printer).
User strategy directive (2026-07-05 late): balanced approach, ONLY gated improvements, chase top-5, CS
concepts first-class, short GTOW smoke soon. **PLUS (2026-07-06): the AXIOM-KNOB track — conditions as
tunable knobs, computation axioms sacred (doctrine/CONDITIONAL_POKER_LEMMAS.md). Knob queue (each full-ladder):
L1 PURIFY (hours, next Analyzer round after the v3.x verdicts) → L2 MR-ORANGE (mini-CFR numpy + exact-BR
river δ-sweep — the instrument doubles as the exact-exploitability gate AND the v4/Leduc-falsification
core; 2-4 days, targets the river −8.5) → L3 v3.2b auto-unpark iff v3.3 promotes AND check-line
check_range_l1 clears → L4 iso already binding in the flop library.** In flight: flop-library calibration
pilot (`research/flop_pilot.py` → data/research_sweep/flop_pilot.json; re-runs need POKERB_SOLVE_CACHE=0);
formula blind-verify campaign (78 fns, dual blind derivation + comparator); math suite live
(tests/test_math_suite.py, 17/17 deep); fingerprint hardening queued (also log constructed agent use_*
attrs — the family-1 lesson). TurboReBeL: theory deep-dive done (Thm 1 likely FALSE as stated —
data/research_sweep/turborebel_theory.md; Leduc falsification harness = phase-5, shares the L2 mini-CFR).

**★★ v3.2 REFUTED (Analyzer, paired seed-55): 26.14 vs v3's 17.93 (+8.21 WORSE — the worst arm of the whole
family, below even v2.2's 20.66).** The SELECTION-aware thin-value gate (e_call>=0.5 vs the tracked calling
range) failed HARDER than v3.1's flat floor (19.76). **The refined lesson (4th refutation of the river-thin
class):** selection via OUR TRACKED ranges is not the teacher's selection — the tracker's check-line narrowing
(1-p_bet only) leaves villain's river range too wide/bluffy -> e_call systematically OVERESTIMATED -> "thin
value" fired into ranges that actually beat us. The OpenAI consult had flagged the 0.5 threshold as too loose
(exact threshold is HIGHER when villain can bet after our check) — measurement confirms, magnitude brutal.
**DECISION: the river-thin-value class is PARKED entirely** (4 failed attempts: limp-fix, flat probe, flat
floor, selection floor) until RANGE QUALITY improves (v3.3's raise-narrowing is the first range-quality lever;
a check-line analog would be its sibling). POKERB_RIVER_THIN_SEL stays default-OFF forever-unpromoted; v3.2b
(exact threshold) NOT attempted — same broken input (tracked e_call). The pod's v32 arm doubles as a platform
replication only. Ladder continues: v3.3 -> v3.4 -> v3.5 verdicts from the pod family vs the fresh v3 anchor.

**★★ POD ARMS GENERATED (2026-07-05 late; pod r9wnalvxlzscju killed, ~$0.30, API-confirmed 0 pods): all 5 arms
on the Desktop + data/gtow_upload/pod/ (fresh v3 anchor hu_v3fresh + v3.3/v3.4/v3.5 + v32-replication, 1500
hands each). Turn-resolver-off fix made them pure-Python -> ~6 min total.** These are a SEPARATE paired family
(POKERB_TURN_RESOLVER=0) — compare each lever ONLY vs hu_v3fresh, NOT vs the old turn-ON 17.93. AWAITING USER
CHROME UPLOAD of hu_v3fresh + hu_v33 + hu_v34 + hu_v35; read verdicts from the Analyzer Uploads page (Avg. EV
loss); promote a lever iff it beats the fresh anchor by >~1.5. Caveat: production runs turn-ON, so a promoted
lever gets a 300-hand live tail-smoke before it sticks.

**★ SESSION CLOSE-OUT (2026-07-05 late) — infrastructure + research, all committed:**
(1) **CLEANUP: decide() 12.1× faster** (999→83ms; proven-pure memoization of p_bet/p_defense/hand_features/
evaluate + the exhaustively-proven _straight_outs memo; commit 114e107) + the 5-agent clean-code pass
(byte-identity PROVEN: 0 diffs over 6 arms × 70 spots, commit 5a70070). (2) **DETERMINISM ROOT FIX:**
combos_for_classes iterated a string SET → PYTHONHASHSEED-dependent combo order → MC-equity boundary
decisions flipped between identical runs (4/140 measured) — sorted() pins it; ALL prior "deterministic"
instrument runs carried this small jitter (pairs stay valid — symmetric). (3) **EVPA read+implemented**:
the one net-free sound transfer (geometric arm prune, POKERB_ARM_PRUNE) measured NO-OP vs TexasSolver
(it collapses over-allin arms internally, ε identical to 1e-8) — kept as the v4 building block; census-
frequency pruning + range-zeroing deliberately NOT built. Flop-NO-GO retest with minimal menu ran in
background. (4) **Embedding CFR read**: not a pillar (blueprint card abstraction); one v4 takeaway =
HandEbdNet card featurization. (5) **Research sweep** (reports/RESEARCH_SWEEP_2026-07-05.md): 27/36 papers
existence-verified (Perplexity scrambles metadata!); OpenAI math verdicts: eCall score = exact EV(bet) ✓,
v3.2's 0.5-threshold = special case (exact formula ready = v3.2b), v3.3 reweight = exact KL projection ✓
+ Laplace-shrink numbers for the jam mix, covered-stack formula verified. (6) **Serena codebase MCP**
(.mcp.json, 305 files indexed, active next session). (7) Docs aligned: CLAUDE.md v3-block,
VERSION_PRINCE live status, _PRINCE_START_HERE, INDEX. v3.2 export still generating (cold solve cache).

**★★ FULL-BOT AUDIT (2026-07-05 evening, user-ordered, 90 agents / 9 dimensions / 3x adversarial verify):
23 CONFIRMED finds, 4 refuted — ledger `data/audit/audit_result.json`, all fixes commit 8c827cc.** The two
HIGH finds were MEASUREMENT-seam: (1) `gtowizard._parse_history` unpacked the live blinds [BB,SB] as [SB,BB]
-> the preflop blind init was INVERTED in EVERY live AIVAT run (BB-facing-open to_call 175 instead of 125 =
+7pp required equity = a baked-in preflop over-fold; the self-test fixture had the same wrong order so the
"locked" asserts never caught it — both fixed, re-locked on the production schema). Every live baseline
(−19.70/−20.09) carried this; exports/Analyzer grades did NOT (different code path). (2) `_FINGERPRINT_KEYS`
missed 13 run-defining flags incl. BOTH active gate flags -> lever-arm exports logged plain-v3 fingerprints
(fixed). Also fixed live: export all-in run-out HH sections (future pairings need FRESH anchors — in-code
note), replay_graded arm isolation (--env), Analyzer-dedup warning, corrupt-fold-model fallback.
Version-separated behavior corrections (default OFF, own arms, stress+replay+activation-probe green):
**v3.4 = POKERB_AUDIT_FIX** (9 finds: PAIR_DEFENSE fired on check-raises; TURN_DEFENSE fired on 2nd barrels
and net-cancelled BARREL_DISCIPLINE on its target texture; RIVER_DEFENSE's bluffcatcher gate vacuous on
paired boards; covered-stack required-equity; degenerate-threshold floor; phantom sizer candidates;
raise=aggro for TRACKER_AGGRO_FULL) · **v3.5 = POKERB_ADVISOR_ROLE_POS** (advisors were queried by INITIATIVE
but trained by tree POSITION -> inverted lookups in every 3bet pot — potentially large, own arm). Deferred
(NOTES.md): slumbot-bridge deal rows, client terminal-state, cache-key allin_threshold (deliberate — a fix
flushes the warm solve cache), twotone vacuity. Analyzer sequencing: v3.2 -> v3.3 -> v3.4 -> v3.5, one arm
per upload, fresh anchors from the fixed exporter.

**★★★ v3 PROMOTED (2026-07-05 evening) — PRINCE_PROFILE now = v3 (commit 85d2919).** The tail-smoke landed
CLEAN: n=295, **0 catastrophes ≤−50bb, worst hand −19.3bb, per-hand SD ≈162** (tightest distribution yet). The
smoke MEAN (−34.14 ± 9.44) is n≈300 noise per the pre-registered protocol — the DECISIVE gate was the paired
Analyzer: **v3 = 17.93 vs v2.2 = 20.66 (−2.73 on identical seed-55 deals)**. Shipped into the profile:
`POKERB_PAIR_DEFENSE=0.10` (flop hole-pair over-fold fix, fold 59%→10% class) + `POKERB_RIVER_DEFENSE=0.06`
(river bluffcatch, 23%-of-folds-were-ahead class). The confirmation of the MEAN stays the pre-registered 7.5k/arm
bundle A/B (on user command). Next lever queue: v3.2 selection-aware thin-value (the eCall pattern extended to the
bet/check DECISION) · 4bet stack-off discipline · preflop BB-defend delta.

**★ v3.1 REFUTED (Analyzer, paired seed-55): 19.76 vs v3's 17.93 (+1.83 WORSE, near v2.2's 20.66).** The bundle
(river-thin pb-floor 0.40 + cbet-damp 0.28) is reverted from the queue — flags stay default-OFF, nothing shipped
(the gate system caught it pre-promotion). **THE LESSON, now measured for the THIRD time (limp→open fix, flat
turn-probe boost, river-thin floor): FREQUENCY-matching the teacher WITHOUT his SELECTION loses EV.** GTOW bets 43%
of river pairs — but chooses WHICH by blockers/kicker/range-position; a blind pb-floor bets unselected pairs into a
near-GTO caller. The principled reshape (queued as v3.2): make the bet/check DECISION selection-aware via the
tracked-range machinery (bet thin iff eq-vs-CALLING-range ≥ ~0.5 at the smallest size — the eCall pattern extended
from sizing to frequency). Ablation note: the bundle wasn't split; the damp may be innocent — the reshape supersedes
both anyway. v3 REMAINS champion (17.93); tail-smoke pending → then v3 → PRINCE_PROFILE.
**★★ v3 ANALYZER VERDICT (2026-07-05, paired seed-55, user-uploaded): v2.2 = 20.66 EV-loss vs v3 = 17.93
(v3 at 1,305/1,500 processed — final may shift ±0.5) → THE BUNDLE DELIVERED −2.73, in the predicted −2.5..−4.5
band.** Cross-check again beautiful: v2.2's 20.66 ↔ its live AIVAT −19.70. The 300 tail-smoke is the last gate
before v3 → PRINCE_PROFILE.
**★ v3 BUNDLE BUILT + COMMITTED (`aa7b755`, 2026-07-05 evening) — the top-2 over-fold classes:**
`POKERB_PAIR_DEFENSE=0.10` (flop: advisor-fold cap 0.30 + MDF discount for hole-pairs vs single c-bet — the −5
bb/100 class) + `POKERB_RIVER_DEFENSE=0.06` (river bluffcatchers vs ≤0.6-pot bets; barrel-discipline precedence).
Gates: stress 20/20 unchanged · **replay flips 8/9 graded flop-fold blunders** (Kd6s/8d8c/4s3s/Qs6c→continue) ·
canary in flight. **TURN-PROBE PARKED** (its live arm completed post-restart: −47.55 ± 21.08 n=296 BUT the probe
CLASS itself was only −0.47bb/hand over n=18 = the flat +0.35 boost bets unselected air; needs selection-aware
reshape; the −47 headline is n=296 noise, body −8.5 ≈ baseline). **THE AGREED TEST (memory: v3-test-protocol):
paired seed-55 Analyzer exports (hu_v22_1500.txt + hu_v3_1500.txt → Desktop, generating) → the user uploads both →
per-decision EV-loss diff decides (≈noise-free); a 300 live smoke only as tail check. NO long run before both.**
**★★ THE PRECISION NUMBER (2026-07-05 15:13, pre-registered n=2500 → 2,393 ok/107 fails): PRINCE v2.2 =
AIVAT −19.70 ± 4.37 bb/100.** ZERO catastrophes ≤−50bb over 2,393 (worst −38.2); per-hand SD 214 =
leaderboard-grade; body −9.0/−6.3; RAW +1.94. **HONEST VERDICT: the distribution is transformed (tail dead,
± small) but the MEAN did not move vs HEAD (−20.09 ± 7.18; Δ +0.4 ± 8.4 indistinguishable) — the −11.61 anchor
was a lucky n=100 draw. X-ray: preflop −1.6 / flop −6.4 / turn −3.2 / RIVER −8.5 — the postflop bleed is
untouched; discipline bought safety, not μ. The mission gap to #1 (−3.14) ≈ 16.5 bb/100, nearly all in
river+flop.** Next: the v2.4 turn-probe live arm (fired), then the river-μ lever generation (Q6 anchors:
GTOW river = 28% air @0.81 pot; call-turn-release-river). Log: gtow_hands_1783226155.jsonl. Commits:
6bbf1c3 (v2.2) + a49e244 (v2.4 probe).
**★ v2.2 LIVE (300-smoke, n=295, 5 fails): AIVAT −20.38 ± 15.06, RAW +26.6 — and THE TAIL IS DEAD: ZERO hands
≤−50bb (worst −22.5!), per-hand SD ≈ 259 bb/100-units ≈ leaderboard-grade (the blowup smoke was ~1000).** Body:
5%-trim −12.4 / 10%-trim −7.1 (consistent with the −11.6 GTO-mode anchor + HEAD body −8..−11; the mean at n=295
±15 cannot rank vs the anchors — the 2,500 run will). The aggro-alpha + eCall-cap did exactly their job.
**★ THE LIVE PAIR (2026-07-05 morning): v2.2 −20.4 ± 15.1 (worst −22.5, SD 259) vs v2.3.1 −31.9 ± 9.5 (worst
−17.6, SD 164) — BOTH tails clean (0 hands ≤−50bb across 591!). Δmean 11.5 ± 17.8 = 0.65σ insignificant, but
same-direction with the discipline-canary minus → v2.2 STAYS the profile, v2.3.1 stays the overlay. THE
PRE-REGISTERED 2,500-HAND PRECISION RUN FIRED on v2.2** (06:40; anchors −11.61/−20.09; expected SE ±3..5; no
mid-run extension; ~8-9h wall-clock). **v2.3.1 overlay smoke FIRED** (barrel-discipline 0.18 street-asymmetric [Q6-calibrated: full river, ⅓ turn] +
turn-def-advisor + turn-overbet-arm; gates: stress 13/0, replay 16-flips/7-clean best-yet, canary caveat noted).
Next: the live pair decides the profile → the 2,500 precision run → the queue (turn-probe vs check-back [Q6:
GTOW's flop check-back = 63% air / 1.9% traps], equity-inflation root, KK preflop consult, river-C1).
**The autonomous loop tonight (each step gated):** v2.1 (aggro-alpha, the Kc3h fix: disaster-probe river FOLD ✓,
replay ✓, canary ✓) → **STRESS SUITE built** (user idea: 70 constructed catastrophes × configs; `research/
stress_suite.py` = permanent rung 0.5) → it caught the **eCall OVER-JAM live** (3.4x-pot all-in hand-strength-
insensitive; the canary had REWARDED it — GTOBaseline over-folds vs jams = wrong teacher) → **v2.2** (eCall capped
at census/2x + value-needs-callers; re-canary +78.2 ± 40.0 passes; 300-hand smoke RUNNING) → **v2.3 overlay**
(barrel-discipline 0.18 + turn-def-advisor + turn-overbet-arm; stress 20→**13** IRRESPONSIBLE, OVER-NIT 0; replay ✓;
canary "passes" but points −23.6 ± 29.4 — GTOBaseline barely barrels → that canary can't price discipline levers →
**v2.3 stays an ENV OVERLAY; the live smoke pair (v2.2 vs v2.3) decides**). **Flop resolver: NO-GO measured**
(49/50 timeouts @300s — the subtree overwhelms TexasSolver on this CPU) → fallback 3b built instead. KK-5bet-node
(blueprint calls 0.996): deliberately NOT blind-fixed (solver-close at 200bb) → preflop-consult queue. Stress rest-13:
blueprint-node + advisor-mixed-nodes + the deep equity-inflation class (next structural lever: texture/aggression-
aware range weighting). Q6 frequency-mining of the 13.5k hands (GTOW's revealed play = free supervision) DONE — see #2 below.

## ★★★ (2026-07-05 #2) — GTOW FREQ-MINE DONE: 26,823 teacher decisions bucketed (`research/freq_mine.py` → `data/freq_targets/gtow_frequencies.json`, 366 buckets); hero-ID cross-check 11,633/11,633.
Mined all 13,675 logged hands (0 replay errors, 99.3% hero-identified; the independent gtow_folded cross-check
agreed on ALL 11,633 net-unique fold hands; walk↔census aggressive-action parity exact 18,468=18,468). **Three
design answers (near-GTO teacher, HU, conditioned on OUR lines):** **(1) Facing a 2nd+ barrel with ONE PAIR
(n=241): call 54% / fold 43% / RAISE 4%** — the teacher never stacks off there; turn top-pair = call 84%, but
river top-pair = FOLD 55% (call-then-release, exactly the class our stress cluster jams). **(2) River bluff share
(air% of first-in bets): SRP 28% (n=825, mean 0.81pot), limped 36%, 3bet 23%** — textbook ~30% at ~0.8pot; our
river-bluff targets now have an empirical anchor. **(3) Flop check-back IP (checked to, n=2,647): bets 55%; the
check-back range = air 63% / pair 26% / top-pair 9% / TRAPS 1.9%** — GTOW barely slowplays; a flop check-back
genuinely caps its range (validates the user's H1-style inference + prices our probe-stab lever). Bonus anchors:
SB RFI raise 82%/fold 15%/limp 2%; BB vs open call 44/fold 41/3bet 15; vs 3bet fold 57/call 38/4bet 5.

## ★★★ (2026-07-05 #1) — PRINCE v2 BUILT (3 levers, 23 bug-hunt fixes, all gates ✓) + the first smoke: −97.6 raw headline = ONE 200bb hand; the 97-hand BODY ≈ +2 bb/100.
**Build:** LINE_U (per-hand keyed, H1 concurrency fix) + RIVER_ECALL (corrected EV formula — the old one refunded
hero's bet on wins, inverting thin-value sizing toward jams; fix also applied to the ALWAYS-ON value_score) +
SIZE_INJECT (now actually active vs GTOW — `_parse_history` finally carries bet amounts, which ALSO fixed the
PRE-EXISTING `_match_label` bug that navigated every villain bet to the SMALLEST tree arm). Adversarial bug-hunt:
27 claims → 23 confirmed → all fixed (turn-defense hole-pair+stab-only, slowplay fold-guard band, entering-pot
double-subtract, exploit-flag half-on states, print_interval mismeasured convergence, A/B PRINCE leak …).
**Gates (all on fixed code):** replay 25/25 matched (PRINCE flips 14/26 flagged blunders; regressions = census-size
relabeling + 3 watched flop micro-stabs) · canary LINE_U passes · **canary LINE_U+ECALL: BETTER ≥2SE (+133.8 ± 60.0
paired; the first ≥2σ-positive arm this canary ever produced)** · unit checks ✓ · `POKERB_PRINCE=1` = the full
19-flag profile, fingerprint-complete.
**Smoke (key #2 = the DEV key per user doctrine; 98/100 hands, 12.6s/hand): AIVAT −97.58 ± 100.25 — the headline is
ONE hand:** BB Kc3h, 3bet pot, monotone AdKd3d → flop check-raise, turn+river call-down vs triple-barrel = −200bb raw
/ −98bb AIVAT. **The other 97 hands sum to ≈ +2 bb/100 — the best body signal yet.** $0 counterfactual (the hand's
turn/river decisions across configs): the river call comes from the **GTO-MODE BASE (since 2026-07-04), NOT the v2
levers** — the S2 tracker damping keeps villain ranges wide (bluffs retained) → eq over threshold → call; HEAD's
over-narrowed range folds. = the KNOWN big-pot stack-off leak class (LEAK_MAP L6/C4), now with a precise causal
chain: **damped ranges under-narrow vs multi-street aggression on extreme boards.** NO fix shipped off n=1 (call-gate
fixes were twice refuted before); the named candidate = an aggression-conditional damping override (α→1 facing the
2nd+ big barrel), to be probed deterministically first. Stuck-hands housekeeping done (18 cleared → full slots).
NEXT: extended smoke (300–500, dev key) to measure the stack-off RATE, then the user-gated long run.

> **★ THE ACTIVE BUILD CARD → [`plans/VERSION_PRINCE.md`](plans/VERSION_PRINCE.md)** (2026-07-04, end of session): the next
> version = GTO-mode base (−11.6 smoke) + the deception layer (turn-defense+slowplay, canary PASSED +39.1±19.9
> paired; `POKERB_PRINCE=1` profile built+verified in `gto_mode.py`) + the MERGED intake queue from THREE deep
> audits (repo-treasure 47 finds · papers 20 levers · books 24 levers). Build order §3b: replay-harness +
> convergence-audit instruments FIRST, then line-U/size-injection/purify (hours each), then river-ecall/geometry,
> then flop-resolver (go/no-go) + river-discipline + HandPlan-MVP. All $0-gated. Key intel: GTOW = the Ruse
> REAL-TIME re-solver (translation attacks refuted, `reports/GTOW_DOSSIER.md`); score-chasing measured -EV — bb only.
## ★★★ CURRENT (2026-07-04 #5) — the GTOW-MODE played GTOW LIVE: AIVAT −11.61 ± 3.67 (n=100 smoke, 0 fails) vs HEAD −20.09 — direction CONFIRMS the mode.
**First live run of the "new best version" (`POKERB_GTO_MODE=1` + resolver ON, the fold-clamp variant): AIVAT
−11.61 ± 3.67 bb/100, n=100, 100/100 hands OK, 10.1s/hand, RAW −91.28 (bad cards, AIVAT strips it), log
`gtow_hands_1783194039.jsonl`.** Consistent with (a) the graded per-decision improvement (17.05 vs 19.33) and (b) the
HEAD's trimmed body (−8…−11). HONESTY GATES: n=100 — the client's ±3.67 SE looks optimistic vs the HEAD-run dispersion
(SD 224 → ±22 at n=100 expected; this session's AIVAT spread was unusually tight, possibly mode-passivity); treat as a
SMOKE that the mode did not regress and likely improved; the S6 pre-registered A/B (2,500/arm) remains the gate. If
−11.6 held at scale it would slot ~#7 on the leaderboard (between Gravel −10.61 and GPT-5.5-repro −13.17) — n=100, NOT
a claim. Note: ~20 stale in-progress hands (ids 1399xxx) throttled mid-run via 409s — `clear_inprogress.py` housekeeping.
> **User leak-probes (played the HU bot live, 2026-07-04):** H1 "flop check on K-board = no King" — probe v1 (valid
> part): P(bet|has K) 76.4% vs P(bet|no K) 48.7% → P(K|check) drops to ~9% from 17% prior = the check IS informative
> (transparent-ish, GTO would check Kx 30-50%; we check 23.6%). H2 "the bot barely bluffs" + H1b fold-to-turn-stab:
> probe v2 running (v1 had a treys-name classifier bug: 'Pair' capitalized ≠ 'pair'). User verdict after playing:
> "good on value, but it doesn't really play poker" = value-machine without the deception layer — names the
> postflop gap precisely (matches river under-value + capped checks).

## ★★★ (2026-07-04 #4) — GTOW-MODE T1 GRADED: the metrics SPLIT (score ↓, EV-loss ↓) + the hypothesis is REFUTED — exploit-OFF did NOT move Freq-Diff.
**The #1 $0 test ran (`hu_gtomode_1500.txt`, seed 55, exploit-OFF + census tree + tracker damp + river guards, graded on
the GTOW Analyzer). RESULT vs the HEAD baseline (53.4% / 19.33 / 54.6%):**
- **GTO-Score 49.8% (↓3.6pp — WORSE)** · **EV-loss 17.05 bb/100 (↓2.28 — BETTER, the money metric)** · **Freq-Diff 54.57% (FLAT)**.
- **My T1 hypothesis is REFUTED:** exploit-OFF was supposed to lift the GTO-score toward the 6-max 85% and shrink the
  Freq-Diff. The Freq-Diff did NOT move (54.6→54.57) → **the engine's frequency deviation is INTRINSIC to its core
  (blueprint+advisors+resolver), NOT driven by the exploit overlay.** A genuine, hypothesis-killing finding.
- **WHY the score dropped (fully traced, per-decision + deterministic probe):** the drop is PREFLOP (mistake+blunder
  19.8%!), and it is the **SB limp-clamp (`POKERB_GTOW_NOLIMP`)**. The clamp renormalizes limp→open/**fold**
  PROPORTIONALLY (`bot.py:244`), sending the bottom of the limp range to FOLD. GTOW's HU SB plays those hands (75o/85o/
  73s/A9o/K5o), so every clamp-fold = a frequency-BLUNDER — but each costs only **~0.1bb** (SB fold of marginal = near
  free). So: many cheap fold-blunders TANK the score, barely touch EV. The postflop exploit-OFF recovered real EV →
  net EV-loss DOWN, net score DOWN. Probe (mode ON vs OFF on the graded hands): HEAD LIMPS them, mode FOLDS them;
  `NOLIMP=0` reverts to limp → the clamp is 100% the cause.
- **★ THE FIX WAS TESTED AND REVERTED — a decisive, counter-intuitive result.** Built a "limp→open" fix (open the
  bottom of the limp range instead of folding it) → generated `hu_gtomode_fix_1500` (paired seed 55) → graded. The
  **paired 3-way (GTOW Analyzer uploads-page, all seed 55):**

  | variant | hand-correct % (score↑) | Avg EV-loss (money↓) |
  |---|---|---|
  | HEAD-s55 (limps) | 65.8 | 17.27 |
  | mode buggy-clamp (FOLDS marginal SB) | 64.5 | **15.42 ← best EV** |
  | mode FIX (OPENS marginal SB) | **67.0 ← best score** | 19.56 ← worst EV |

  **The fix RAISED the score (67.0, best) but WORSENED EV (19.56, worst) — a clean score-vs-money TRADEOFF.**
  **The SB over-fold is EV-PROTECTIVE:** opening marginal SB hands to match GTOW's wide frequency LOSES money because
  our postflop play with them (vs a strong opponent) is −EV; folding them (a score-blunder) SAVES it. Folding (15.42)
  beats even HEAD's limping (17.27). → **REVERTED** the fix (`bot.py:243` back to the EV-better fold-clamp; gated,
  product unaffected).
- **★ THE STRATEGIC LESSON (this changes the tie-plan): frequency-matching GTOW ACTIVELY HURTS our EV until postflop
  is fixed.** Chasing the GTO-SCORE is the WRONG target for the tie goal. Two independent findings now converge on it:
  (a) exploit-OFF didn't move Freq-Diff (deviation is intrinsic); (b) closing a named frequency-gap (SB opens) cost
  EV. **The ONLY path to tie is POSTFLOP/RIVER** (mode river still 22% mistake+blunder = worst street) — make our
  postflop good enough that playing GTOW's ranges becomes +EV. Track EV-loss, never GTO-score. Data:
  `data/gtow_grades/gtomode_paired_s55.json`.
> **Also this session:** the leaderboard was pulled (`data/gtow_grades/leaderboard_2026-07-04.json`) — **the HEAD engine
> (−20.09) would slot #11 of 11**, behind only frontier LLMs (GPT-5.x −8/−9), 3 MIT bots, individuals + a pro. And a
> **novelty audit** (2 independent adversarial passes, Claude 8-agent + OpenAI, `reports/NOVELTY_AUDIT.md`): NO new
> algorithm/theorem/result — every component is known technique (Libratus self-improver = our tree census; Modicum =
> CPU-only no-value-net; Bayes'Bluff = the range tracker; DIVAT/AIVAT = the tail eval). The remarkable thing is a
> **SYSTEMS/ENGINEERING result honestly measured**, not math progress. The `(pot/2)·L1` bound is "trivial Lipschitz".

## ★★★ CURRENT (2026-07-04 #3) — ★ THE STALE −47 IS DEAD: the CURRENT HEAD engine is AIVAT −20.09 ± 7.18 bb/100 (n=974, fresh) — BODY ~−8 to −11 (5–10% trim) = FRONTIER territory.
**A fresh HEAD-default GTOW run (all `POKERB_GTO_MODE` flags OFF — the shipped engine) re-pinned the baseline:
`gtow_hands_1783177274.jsonl`, AIVAT **−20.09 ± 7.18**, RAW +69.37, 974/1000 hands (8.9s/hand, resolver ON, 26
server-503 fails).** The **−47.18 was a stale ACCOUNT AGGREGATE** across dead code eras (the −106 jam-spew era etc.);
the current engine is **~2.4× better**. `gtow_tail`: **BODY (5%-trim) −11.1, (10%-trim) −8.0** — near the GTOW
leaderboard (best −3.14, frontier LLMs −9); the raw −20 carries a MODEST tail (worst hand only −26bb, **0
catastrophes** — the old jam-spew is gone). `gtow_xray` decomposition (where the −20 lives): **postflop is the whole
story (−18.4 of −20.1; preflop −1.6 = near-solved blueprint).** BY STREET river −8.6 + flop −8.3 dominate (turn −1.6);
BY SIZE the loss is in NORMAL pots (3-10bb −9.5, <3bb −5.3), NOT jams (>=100bb only −0.7, n=14). So the HU leak =
spread postflop (river + flop) in normal pots — matches "river = #1 engine leak". **IMPLICATION: the S6 GTOW-mode A/B
must be measured against −20.09 (this fresh baseline), NOT the mythical −47.** Update the north-star −47 refs everywhere.
> **★ CROSS-CHECK (2026-07-04, HU per-decision grade, `hu_hands_1500.txt` file 78ec0a6c, exploit-primary HEAD):
> GTO-Score 53.4% · EV-loss 19.33 bb/100 · Freq-Diff 54.6% (n=1500, 2599 moves).** The per-decision EV-loss (19.3)
> ≈ the LIVE AIVAT (−20.09) → two INDEPENDENT metrics agree → the −20 is REAL deviation cost, not tail luck. The
> HUGE Freq-Diff 54.6% + low 53.4% = the exploit-primary engine deviates massively from GTO frequencies (BY DESIGN;
> −EV vs near-GTO GTOW). 53.4% ≈ the old 53.1% → the HU wiring fixes (ONTREE/to_call/made-hand) did NOT move
> GTO-alignment (they helped AIVAT/wiring, not fidelity — consistent). BY STREET: preflop 76.2% (WORSE than 6-max's
> 88.5% — the exploit deviates preflop too), river 53.9% (28.1% M+B = worst). **THIS IS THE MOTIVATION FOR GTOW-MODE
> (exploit OFF): the next $0 test = generate a `POKERB_GTO_MODE=1` HU export + grade it → does the GTO-score jump from
> 53% toward the 6-max tag-core's 85%? Deterministic, no AIVAT noise.**
> **★ HU costly-hand DRILL (pulled from the GTOW API via a SAFE XHR response-hook — the "browser console" route,
> response-DATA-only, NO token/header access; endpoint `api.gtowizard.com/v4/hand-history/hands/`, rows under
> `items[]`, EV-loss filter server-side): the 8 HU hands with EV-loss ≥5bb are 7/8 in the BLINDS (BB×6, SB×2)** —
> marginal holdings (Kh7h, Jd8h, Qs8s, Jc2c, 4s3s, 76s, 88) bloating big OOP pots (SRP 78–162bb + a 4bet 60bb).
> = the OOP loose-blind-defense leak, TRIANGULATED across (a) the aggregate grade (blinds weakest), (b) these
> individual hands. Fix lever = GTO
> blind-defense + OOP-pot discipline (exactly what the GTOW-mode exploit-off + range-tracker fix feed).

## ★★★ CURRENT (2026-07-04 #2) — FIRST absolute 6-MAX GTO grade of the product bot: GTO-Score 79.3%, EV-loss 12.33 bb/100 (GTOW Analyzer, n=227 hands / 263 moves).
**User idea, executed same-day: generate 6-max self-play hands ON GTOW's tree → upload to the GTOW Analyzer (Chrome) →
per-decision grading vs GTOW's own 6-max solutions.** NEW `research/sixmax_export.py` (Hero = the tag product core vs the
mixed league, button rotates → all positions graded, hero sizes snapped to GTOW conventions: open 2.5x / reraise 3x /
postflop tree; PokerStars 6-max HH). Upload `sixmax_hands_300.txt` (file_id 0e1df589…). **Results:** overall Perfect 82.1 /
Mistake 5.3 / Blunder 5.7. BY STREET: preflop 86.2% perfect (the heuristic holds up!), flop 73.3 (0 M+B), turn 62.5,
**river 50% perfect + 28.6% BLUNDER (4/14) = the same #1 leak as HU.** BY POSITION: HJ 97.3, UTG 86.4, SB 87.9, BB 81.3
(12.5% blunder — defense), **CO 73.3 (15.6 M + 6.7 B) + BTN 73.2 = late position weakest** (wide-range spots; check
OPEN_FRAC vs GTOW 6-max). BY ROLE: as PREFLOP CALLER **16.7% blunder** vs 2% as raiser → the passive-line postflop play
is where blunders live (matches the user-found "call down with 44"). Pot types: SRP 78.9 / 3bet 72.4 / squeeze 62.5.
**Honest:** postflop n TINY (14–16 moves/street) → river/turn %s are indicative, not stable; the 79.3% is preflop-heavy
(218/263 moves = easy folds) and NOT comparable to the HU-direct 53.1% (different mix). Villains = our own league.
> **★ STABLE 6-MAX GRADE (n=1500, `sixmax_hands_1500.txt`, file 84cfebd7…): GTO-Score 85.9% · EV-loss 7.61 bb/100 ·
> 1781 moves (Perfect 82.6 / Good 8.1 / Inacc 2.2 / Mistake 4.1 / Blunder 3.0).** The 300 was a low draw (79.3); the
> stable number is HIGHER. **The 3 stable leaks (all match prior findings):** (1) BY STREET preflop 88.5% (strong) but
> ALL postflop ~57–61% perfect; **RIVER worst = 22.4% Mistake+Blunder** (11.2+11.2) — universal leak, HU & 6-max.
> (2) BY POSITION the **BLINDS are weakest** (SB 74.2 / BB 75.9 = ~11% M+B; HJ 91.4 / UTG 88.6 best) = OOP-defense leak
> (matches [[sixmax-bot-leaks]]). (3) **BY ROLE the dominant leak: as
> PREFLOP CALLER postflop = 23.5% M+B (11.9 M + 11.6 B) vs as RAISER only 6.6%** — passive-line postflop play is
> 3.5× worse (confirms the user-found "call down with 44"). → the fix levers: caller-line postflop + BB/SB defense +
> river (all mirror HU). NEXT: drill the 54 blunders (View Hands per bucket); build the 6-max fixes.
The screen reader also landed: `pokerbot/vision/screen_reader.py` (VLM-based, any site, ~<1ct/frame, watch mode) —
live-verified on the PokerB game.

## ★★★ CURRENT (2026-06-29 #2) — built the consolidated UNDERSTANDING layer (the brain reasons on UNSOLVED spots) + measured the brain's RIVER OVER-SIZING; wrote the forward ROADMAP (bot-improvement + a personal Claude coaching path).
**User directive: "make the bot understand poker as well as possible, even on spots it hasn't solved" + document how to improve further + how to build a personal Claude coaching path.** Done, all $0/local (network-gentle — the user was playing online). Nothing shipped to the product (everything gated default-OFF); uncommitted.
> **★ NEW LEVER — the understanding layer (`pokerbot/brain/understanding.py`, BUILT + locally verified, EV-UNMEASURED).** `strategic_read(spot)` fuses the scattered engine knowledge into ONE engine-computed NL frame the brain reads on every spot: **geometry** (SPR + commitment, in/out-of-position, pot-odds, required-equity, MDF), **board texture**, the **made-hand read** (`api.hand_rank`), **initiative** (preflop lead + range-advantage), and the **measured GTO heuristics** (river skews small ~0.33×, c-bet small/often on dry boards, defend to MDF, jam-discipline). WHY: solved spots are ~15–40% (6–76s each) → on the other ~60–85% the brain must generalize from first principles; this hands it the full frame without a solve. Wired into `format_spot` gated `POKERB_UNDERSTANDING` (default OFF → baseline byte-identical, A/B-able; reaches BOTH Claude + GLM). **Verified $0:** OFF == baseline byte-identical; ON appends the block; numbers exact (req-equity 33% = 10/(20+10), MDF 50%, SPR 4.0); river wording honest ("flush possible" not "draws live"). **NEXT = the #1 measurement: A/B `POKERB_UNDERSTANDING=1` deterministically first (`research/claude_export.py` → GTOW per-decision GTO-score), then AIVAT if promising.** Honest: principles grounded, realized-EV benefit UNPROVEN (may be neutral like solver_freq, or help like made-hand).
> **★ MEASURED — the brain OVER-SIZES the river (the cleanest open leak).** Over 5 boards × 2 pot-types (OOP-lead river, `gto_oracle.solve`, low-load): the solver **CHECKS 58%**, and when it bets the **median is ~0.33×pot** (0.25× = 42% of bets); offering it 0.6× between the tree sizes, it uses 0.6× only **1.3%**. **Claude reflexively bets ~0.60× → over-sizes ~2×.** → the `POKERB_BRAIN_ONTREE` snap (0.6→0.5/0.75) is only a PARTIAL band-aid (still > 0.33×). BUILT (gated, EV-unmeasured): the river-sizing rule in `claude_brain.py` (`POKERB_CLAUDE_RIVERSIZE`, default OFF) nudges Claude toward the small skew. **The cleaner fix (proposed): render the solver's preferred SIZE in the prompt** (the size analog of `api.solver_freq`), so the brain sizes like the solver instead of being snapped after the fact.
> **★ FORWARD DOC — [`plans/ROADMAP.md`](plans/ROADMAP.md) (NEW).** Two tracks, honest MEASURED-vs-PROPOSED: **(A) improve the bot** — ranked next levers (1. measure the understanding layer, 2. measure the river-size rule, 3. render the solver size, 4. extend the snap to raises/overbets, 5. a draw-equity perception hint, 6. RL with a better reward = walled/deferred) + the measurement-floor discipline (don't A/B small hints at n≤500 = noise). **(B) a personal Claude COACHING path** — review a player's OWN hand histories, engine-grounded (`api.*` + the understanding layer) + GTO-anchored, personalized to the player's tracked leaks; the reuse map shows most machinery exists (`pokerbot/coach/coach.py` + `research/study_grade.py` reconstruction + `research/llm.py`); phased MVP = a hand-history review CLI (PokerStars first → further site adapters → cross-session leak trends). Linked from CLAUDE.md + INDEX.md.

## ★★★ CURRENT (2026-06-28) — ENGINE-DIRECT vs GTOW: built a repeatable GTOW-Analyzer grading loop + SHIPPED a GTO-sizing default (`POKERB_ONTREE` ON). Focus = make the ENGINE top-notch (RIVER next), RL deferred until the engine is excellent.
**New durable capability: grade the ENGINE itself (not the GLM) against GTO Wizard's own solver, per decision.** `research/pokerstars_export.py` plays our HU `PokerBot` ("Hero") vs `GTOBaseline` → valid PokerStars hand-histories → GTOW Analyze/Uploads → per-decision GTO grade (GTO-score, EV-loss, by street/pot-type/position). Read via `get_page_text` on the Stats views (the API `api.gtowizard.com/v4/hand-history/hands/` is CORS/auth-gated for a direct replay; read the app's rendered aggregates). EV gate = `pokerbot/benchmark/duplicate.py`. Memory: [[gtow-analyzer-loop]].
> **★ ENGINE vs GTOW (1000 hands): GTO-score 50.7%, EV-loss ~22 bb/100.** Biggest gap was OFF-TREE play (GTOW can't grade it): limp/iso pots 100% off-tree, 3bet ~72%, and SRP off-tree driven by the engine's EV-maximized VARIABLE/decimal bet SIZING missing GTOW's discrete tree. Donk-bets = 0 (refuted). Of the on-tree subset the RIVER is weakest (~51% perfect) — under-value-betting strong + over-light pay-offs at DEEP SPR (`research/river_probe.py`), NOT commitment-spew.
> **★ SHIPPED (A/B-cleared, DEFAULT-ON): `POKERB_ONTREE`** (`postflop.py::snap_to_tree` + `bot.py::_raise_to`) snaps postflop BETS to {0.33,0.5,0.75,1,1.25}×pot. A/B (1000 hands each + duplicate.py): more on-tree, GTO-score 50.7→**53.1**, EV-loss 22.7→**21.2**, realized-EV **NEUTRAL** (−59.2 vs −60.6 bb/100, inside noise) → made the DEFAULT; `POKERB_ONTREE=0` reverts to the variable exploit-sizing. Modest, gated, reversible.
> **★ NEXT (user directive): get the ENGINE top-notch INDEPENDENT of RL; RL only once the engine is excellent.** The RIVER is the remaining real leak — tackle ENGINE-side, NOT RL. (The GLM-brain −55-raw / RL story below is SEPARATE + deferred.)
> **★ RL PIVOT — REFUTED at $0 (2026-06-29 planning workflow), user chose the ENGINE PATH.** A grounded RL plan (`rl-pivot-plan` workflow) re-confirmed with the project's own $0-proofs: **RL cannot cheaply break the opponent-ceiling wall.** The chain: lift > the imitation cap needs realized-EV vs a STRONGER opponent; `make_league` (`rl_env.py:82`) builds every villain from ONE shared `SixMaxBot` engine (68% identical postflop) + the hero-continuation is hard-`tag` (`qwen_grpo.py:116`) → the reward measures "engine-autopilot vs engine-league", NOT GTO (the `rollout_action_ev` probe already measured the flat postflop spread, call-EV maniac-vs-tag +0.0). No loop-fast stronger opponent exists (live solver 6-76s; advisors solver-capped ~−47); the only one >−47 is GTOW-in-the-loop (infeasible). → **achievable RL ceiling ≈ engine-level −45; RL already regressed once to −90.** Plan's $0 de-risk ladder if ever pursued: G0 build a solver-distilled multiway opponent + beat the tag-core ≥+10bb → G1 (decisive) postflop EV-spread >0 → G2 local 1.7B A/B → only then a $10-15 pod. **Recommendation taken: NO pod spend; the engine path serves BOTH the product AND a future RL league.** Memory: [[river-advisor-rebuild]] + the RL memories.
> **★ ARCHITECTURE TRUTH (2026-06-29): the LLM-BRAIN BYPASSES the engine's bot.py improvements.** The brain (ClaudeBrain/GLM) decides via `executor → api.legalize` (`executor.py:89`, `api.py:462`), NOT `bot.py::PokerBot`. So this session's engine wins — ONTREE snap + jam-fix (`bot.py::_raise_to`), the river value-floor + line-aware river advisor (`bot.py::_postflop`, `pf_advisor` not in `api.*`) — reach the **engine-alone PLAYABLE bots (`PokerBot` = the product you play)** but NOT the brain+engine GTO-research system (it uses `api.*` math/solver + legalize). The brain has **never been GTOW-Analyzer PER-DECISION graded** (only live AIVAT via `gtow_glm_pod`); `pokerstars_export.py` wires only `PokerBot`. → two levers open: (a) "make the LLM fit" = expose the engine wins (river-advisor freq, tree-snapped sizing) through `api.*`; (b) wire a brain decider into `pokerstars_export` → GTOW per-decision grade the brain+engine (NEW).
> **★ DONE — first per-decision GTOW grade of the BRAIN+ENGINE (2026-06-29, `research/claude_export.py`, Claude+engine, 50 hands / 86 graded moves): GTO-score 69.9%, EV-loss 6.1 bb/100, freq-diff 48%** — vs the ENGINE-ALONE ~50-63% / 78-120 EV-loss / 94-97% freq-diff. **The brain plays DRAMATICALLY closer to GTO than the bare engine** (preflop 85% perfect; consistent with Claude = the −28 teacher whose per-decision GTO-fidelity is high, the −28 AIVAT being variance). Crucially the brain achieves this WITHOUT bot.py's wins (it bypasses them via `api.solve_node` + judgment) → **"making the LLM fit for the engine changes" is LOW-value**; the engine wins serve the engine-alone PLAYABLE bots. **Caveat: small sample (86 moves) → headline (overall/preflop/freq-diff) reliable, per-street (flop n=20 45% / turn n=15 60% / river n=11 54%) NOISY.** Strategic state: two products — (a) engine-alone = instant + ours but ~−47/50% GTO; (b) brain+engine = near-GTO (70%/6 EV-loss) but SLOW + $ + NOT ours (Claude). The "ours + fast + GTO" goal stays hard (RL walled at ~engine-level; GLM ~−40-55).
> **★ Claude+engine LIVE AIVAT vs GTOW (key #2, n=200, `tools/gtow_run.py --agent_type claude`): −41.0 ± 14.06 bb/100** (RAW +71 ± 91 = high variance; 534 decisions, 100% Claude-driven frac_bad 0, solve_node 61%, **$4.14**). Within ~1σ of the original −28.55 → confirms the brain's true level **~−35 to −45 with a fat tail** (the −28 was a lucky draw); NOT the leaderboard top (everyone loses to GTOW). **★ KEY (the user's question): the brain BYPASSES ONTREE → its bet sizes are OFF GTOW's tree** — MEASURED (`scratchpad _betsize_check`): Claude only **15% on-tree** (bets continuous **~0.60×pot**) vs the engine's **100% on-tree**. The per-decision 6.1 EV-loss was on the ON-TREE subset only; the 85% off-tree sizes are ungraded per-decision yet cost realized EV → plausibly part of the −41 AIVAT gap. **★ brain-ONTREE-snap: BUILT + STAGED (2026-06-29, commit `4ad90b1`, gated `POKERB_BRAIN_ONTREE` default-OFF).** `pokerbot/brain/api.py::legalize` snaps a first-in postflop bet (to_call==0, not a jam: target≤2×pot) to the GTOW tree via `postflop.snap_to_tree`; UNIT-VERIFIED (OFF 0.6x=600 unchanged; ON 0.6x→500/0.8x→750; jam 6x + facing-raise untouched). The brain path (`executor.py:89 → api.legalize`) routes through it, so it reaches Claude/GLM. **READY TO FIRE — the LONG AIVAT A/B (~2h, the user starts it later today):** contemporaneous OFF then ON (same-session cancels GTOW day-variance — cleaner than vs the −41), Claude+engine, **key #2** (`Secret keys/Poker/GTOW - key #2.txt`): `bash <scratchpad>/run_brain_ontree_ab.sh 300 10` = OFF `POKERB_BRAIN_ONTREE=0` then ON `=1`, each `python tools/gtow_run.py --agent_type claude --num_hands 300 --num_concurrent_hands 10`. **Cheaper CLEAN signal (the deterministic one):** `POKERB_BRAIN_ONTREE=1 python -m research.claude_export --n 60 --idbase 3500000000 --out data/gtow_upload/claude_ontree.txt` → GTOW per-decision + `scratchpad/_betsize_check.py` (on-tree-rate 15%→~100% = the sure signal; the AIVAT delta is NOISY at n=300/arm, SE~16 — a small effect may stay inconclusive). **GATE:** keep ON only if it beats OFF on AIVAT OR clearly lifts the per-decision GTO-score; else stays default-OFF (a no-op). Per-decision tool `research/claude_export.py`; live-AIVAT `tools/gtow_run.py --agent_type claude`.
> **★ A/B RESULT (2026-06-29 night, low-load run n=300/arm key #2): on-tree CONFIRMED 15%→100%** (`claude_ontree.txt`, the snap mechanically works, deterministic). **AIVAT: ON (snap) −39.92 ± 19.32 vs OFF −55.92 ± 28.14 → ON better by +16.0 bb/100 AND lower variance (RAW ±74.5 vs ±152.8) — BUT the delta SE ≈ 34 = NOT significant** (a high-variance fat-tail session). → **directionally favorable but statistically inconclusive; default-OFF stays for now.** **The DECIDING clean signal is PENDING the user's upload of `claude_ontree.txt` (60 hands, snap ON) → the GTOW per-decision GTO-score (vs the 69.9% snap-OFF) + the off-tree share.** If the per-decision score clearly lifts (more on-tree → gradeable + on the GTO ref tree), the snap earns default-ON (or a bigger AIVAT run to resolve the +16); else gated default-OFF. (Low-load knobs used: `SOLVE_THREADS=2` + concurrency 5 + BelowNormal — quality unchanged, just slower.)
> **★ PER-DECISION RESULT (claude_ontree snap-ON, 60 hands / 133 moves): GTO-score 60.4%, EV-loss 47.5, freq-diff 51% — vs snap-OFF (claude_brain) 69.9% / 6.1 / 86 moves. CONFOUNDED (my seed error): ontree used seed 31, brain seed 7 → DIFFERENT hands, not paired.** Also survivorship cuts both ways (OFF's off-tree decisions were UNGRADED → its 69.9% is over the easy on-tree subset; ON grades MORE moves incl. the now-on-tree size choices, some marked size-imperfect). → direction muddy. **VERDICT: the snap mechanically works (on-tree 100%) but its EV/GTO benefit is UNPROVEN (AIVAT +16 inconclusive; per-decision confounded). Keep default-OFF** — like the value-floor + river-advisor, a clean mechanism with a modest/unclear payoff. The clean resolver = a PAIRED per-decision test (SAME seed, snap ON vs OFF, both uploaded) — deferred. Total this lever ~$24 Claude API.
> **★ RIVER WORK (2026-06-29, engine-side, no RL): diagnosed the line-aware river RESOLVER, fixed a snap bug, targeted GTOW river A/B in progress.** A 5-agent diagnosis found the resolver's regression (documented **−72 ± 6.70, n=2498**; the cited "−121" was an n=20 chunk of THAT run, all pre-ONTREE) has 3 causes: **#1 (FIXED, committed `ace70aa`) — my new ONTREE snap destroyed JAMS** (proven: a 24×-pot jam → 1.25×pot, since a jam's `desired<raise_max` because the resolver's `eff!=raise_max`; fix = a `desired<=2*pot` guard + `snap=False` on the resolver path so its exact GTO size isn't re-quantized = #3 too); **#2 (the real −72 cause) — distorted line-aware range reconstruction** (`range_tracker.weighted_ranges`: after check/check `P(check)=1−P(bet)` inverts the range) at a **DEAD confidence gate** — empirically the resolver **FIRES 93%** of river decisions (`research/resolver_probe.py`) → solves a WRONG equilibrium → spew; **#3 tree-grid mismatch** (resolver 33/75 vs the snap grid). **★ HARD CONSTRAINT (measured): ~6s / river decision (median 5.8s) → the live resolver is UNUSABLE for the playable bots.** → the engine-side GTO river = a fast OFFLINE-solve→ADVISOR (instant serve), NOT the live resolver; the resolver stays an offline tool. **★ RESULT (2026-06-29, the targeted GTOW river A/B is DONE):** (1) The FLOOR river leak is PINNED by the engine's OWN math (`research/river_leak.py`, exploit=False): **UNDER-VALUE-BETTING** — bets only **33% of eq≥0.80** first-to-act river hands (checks 67% = the #1 leak); over-calling is NOT a leak (**0%** call with eq<required = MDF-correct). GTOW confirms river = the worst street (47.3% perfect, 26% mistake+blunder). (2) A heuristic **VALUE-FLOOR** fix (`POKERB_RIVER_VALUE`, env-gated default-OFF: bet eq≥0.75 at 0.85 freq; `postflop.py`+`bot.py`) was **DUAL-GATED** and the two gates DISAGREE: **GTOW = NEUTRAL** (river perfect 47.3→48.0 flat, M+B 26.4→27.7 slightly worse → does NOT improve GTO-fidelity), but **`duplicate.py` paired EV = +23.0 ± 11.4 bb/100 vs GTOBaseline (2σ GAIN)**. → the value-floor is a **validated BOUNDED EXPLOIT** (extracts value vs paying opponents) but NOT a GTO-alignment fix — **GTO river play is RANGE-AWARE, not equity-threshold** (confirms the documented "blunt river rules don't improve GTO-fidelity" pattern; kept env-gated default-OFF → product untouched). **The cheap heuristic river lever is now TESTED + EXHAUSTED; the GTO river leak needs RANGE-AWARE play (the offline-solve advisor or the resolver) or acceptance of the heuristic ceiling.** Resolver A/B was confounded (off-tree `snap=False` → 30 GTOW errors + survivorship) + it's 6s/decision = unusable live.
> **★ LINE-AWARE RIVER ADVISOR (2026-06-29, built + gated `POKERB_RIVER_LA`, default OFF — BORDERLINE, NOT shipped).** Retrained the river advisor on CORRECT per-pot-type reach-range river-SUBGAME solves (`research/build_river_la.py` → `research/train_river_la.py`; +pot-type one-hot feature, 18→21-dim; new `river_advisor_la.pt`). Approach validated by elimination: **full flop→river solves are INFEASIBLE (>600s timeout); river subgames ~5s + extractable.** Micro-test grounded it (solver value-bet freq swings 17%→97% with the range). Train: held-out MSE 0.169→0.095 (+44% vs freq baseline); 1.52M rows; strong-hand P_bet 0.63-0.72 (vs the old 0.33). **DUAL-GATE = NEUTRAL/BORDERLINE → kept default-OFF:** GTOW river-perfect 47.3→**56.3%** (+9pp) **but survivorship-tainted** (full-analysis 66→57%, 18 errors, mostly good→perfect reclass; M+B/blunders unchanged 26.4→25.4); `duplicate.py` realized EV **+3.2 ± 5.0 = neutral**; the under-betting only HALF fixed (eq≥0.80 bet 33→47%, the MLP regresses to mean on coarse features). → **the river leak is genuinely RANGE-AWARE-HARD:** the heuristic value-floor (+23 EV but GTO-neutral) AND a correct-range pot-type advisor (EV-neutral, +9pp-tainted) are BOTH only modest. A clear fix needs richer **line-narrowing features** (flop/turn line, stage 2) or RL — not another cheap lever. Memory: [[gtow-analyzer-loop]], [[river-advisor-rebuild]].

## ★★★ CURRENT (2026-06-21 night #3) — the tail-robust eval is BUILT; the model's BODY ≈ −17 bb/100 (near the GTOW leaderboard!), the raw −40/−68 is a FAT TAIL; the anti-spew GATE is REFUTED ($0 counterfactual). The tail is hero's -EV BETTING — only RL can touch it.
**Executed #2's two deferred levers — (b) a tail-robust eval + (a) the anti-spew gate — and (b) REFUTED (a) for $0 before any pod/code spend. Tool: `research/gtow_tail.py` (reusable: tail-robust metrics + the cross-session body table + the gate counterfactual; reconstructs any GTOW log's decisions via `study_grade`).**
> **★ THE BODY IS ~−17, STABLE across EVERY session — the raw swing is ALL TAIL.** The 5%-trimmed mean clusters tightly while the raw swings −28↔−90:
> | session | n | RAW | trim5% |
> |---|---|---|---|
> | "−28.36 lucky" | 500 | −28.5 | **−17.3** |
> | "−68 pin" | 1500 | −68.2 | **−16.8** |
> | −49.5 re-measure | 500 | −49.5 | **−15.4** |
> | −90 GRPO "regression" | 500 | −90.2 | **−18.1** |
> | to_call-OFF | 500 | −40.4 | **−19.2** |
> The model's **non-catastrophic skill level ≈ −17 bb/100** (trim-dependent: 2.5%→−26, 5%→−17, 10%→−10) — **near the GTOW leaderboard region (−3…−17)**, MUCH better than the raw −40/−68. The session-to-session raw difference (and even "−90 regression" vs "−28 lucky") is almost ENTIRELY tail luck — at n≤1500 NONE are distinguishable in the body. **(This SUPERSEDES #2's "−40 robust" — that was a drop-10-worst figure, still tail-contaminated; the proper trimmed body is −17.)**
> **★ THE GATE (a) IS REFUTED — a $0 counterfactual over the real 1500-hand log** (`gtow_tail.py --gate`: replay folding a clear -EV big CALL where eq < required, over every logged decision). **ORACLE (eq vs villain's ACTUAL hand = the perfect-info upper bound): fires 2/1500, +16.7 bb/100. LIVE (eq vs a committing RANGE = what serve can compute): fires 0/1500, +0.0.** Aggressive live settings fire a few but **cost ≈ saved** (it folds winners as often as losers) → net 0 to −7.5. Only 27 big-calls exist in 1500 hands. → **a live anti-spew CALL gate cannot help; NOT built/shipped** (#2 had proposed it as "the real remaining lever" — refuted).
> **★ WHY — the fat tail is hero's -EV BETTING, not call-offs.** The catastrophic hands are `hero_bet=True` multi-street aggression that folds to a raise or gets called and loses (the −208bb hand: `HERO:b1000 … HERO:b2710 gtow:b8134 HERO:f` = hero's OWN bets, then a fold). This is the **-EV postflop aggression the self-play league rewarded** (≠ GTOW). A bet→check change CANNOT be cleanly counterfactual'd offline (fold-equity is unknowable) → it is **RL's job, not a serve-gate's**.
> **★ DEEPER — the gate question is FULLY CLOSED ($0): the tail is mostly IRREDUCIBLE COOLERS, NOT recoverable spew.** A commitment-cap counterfactual (`gtow_tail.py --cap`) showed an ORACLE (perfect-info, eq vs villain's ACTUAL hand) "recovers" +28 bb/100 by folding 7 big-pot commitments — BUT inspecting those 7: they are **TRIPS (×2) + TWO-PAIR (×3) + PAIR (×2)** (made-hand strength 0.48–0.76 = looks STRONG), crushed only by villain's SPECIFIC better hand (eq vs actual ~0.00–0.12; **0 won bluffs**). vs a RANGE these are AHEAD — you CANNOT fold trips/two-pair → **the +28 is a HINDSIGHT ILLUSION** (folding made hands knowing villain's cards), NOT live-recoverable. So the tail = irreducible coolers + a minority of THIN stack-offs (e.g. two-pair on a 4-straight board, trips-no-kicker) that need nuanced pot-control JUDGMENT, not a gate. **No serve-gate works (confirmed twice); only better overall SKILL (a better-reward RL) could MODESTLY trim the thin-stackoff/-EV-bet slice — not eliminate the tail.** (RunPod balance query 403'd → couldn't confirm budget headroom; not firing an expensive uncertain run blind.)
> **★ VALUE/SIZING AUDIT ($0, `gtow_tail.py --value`) — the EV fundament is mostly SOUND (the user's "compute value + size right, then ride the variance" lever, grounded).** Over to_call==0 postflop spots: hero's bet-rate MATCHES the advisor's GTO rate on strong/nuts (strong 41% vs 38%, nuts 57% vs 41%) = **value-betting FREQUENCY is sound, NOT under-betting value** (the made-hand fix works). The only asymmetry = UNDER-BLUFFING (weak 5% vs advisor 32% — but vs GTOW, which doesn't over-fold, that costs little). Sizing is **flat ~40% pot on ALL streets** (flop 40 / turn 40 / river 38) = mildly small for NUTS value on the river (under-extraction, but nuts are rare n=28), yet defensible pot-control for the cooler-prone vulnerable-strong (.6-.8). → **no big value/sizing BUG; the −17 body ≈ sound value-play at a 9B's ceiling, so the cooler-variance is genuinely TOLERABLE around it.** The gap to the leaderboard (−3…−17) is diffuse SKILL (balance/under-bluffing + sizing nuance + turn play), not a cheap fix = RL territory.
> **★ CONFIRMATION RUN (2026-06-21 #3, product config = `grpo_slim` + made-hand + to_call, 500 hands, ~$1.5, 0 pods verified):** RAW AIVAT **−82.2 ± 23.9** (a BAD cooler-draw, worst end of the band) — but the **5%-TRIMMED BODY = −19.3** (≈ the −17 across ALL sessions); 14/15 worst hands COOLERS (poster child: **AhJh flops trip-2s into villain's QUAD 2s, −200bb** — unfoldable), 0 catastrophes >100bb, frac_bad 0.003 (drove 100%). → **the body is STABLE; the −82 raw is tail-luck, NOT a regression.** Confirms the whole thesis in one run. (User chose **A — consolidate**: `grpo_slim` + made-hand + to_call IS the product; the variance is accepted.)
> **★ RE-OPENED + CORRECTION (user rejects −80): the tail is NOT all irreducible — there's a REAL -EV OVER-PAYING-OFF leak (but no CHEAP serve fix).** Honest restatement: the RAW (actual) level is **~−55 avg (−82 this session), NOT −17** (−17 = the trimmed diagnostic you don't get to keep — you play the tail). Re-testing the gate with the CORRECT tight VALUE range (range_top 0.08-0.12 = GTOW's jam range; the earlier "0 fires / irreducible" used range_top 0.5, too WIDE → my error) shows the leak is REAL: the **ORACLE (perfect-info) recovers +12 to +80 bb/100 across ALL 4 product sessions (avg ~+47, 0 cost)**, and those hands' AIVAT is NEGATIVE (trip-2s-into-quads = −49, not ~0) → genuine -EV pay-offs (stacking off non-nutted hands vs GTOW's value), NOT pure coolers. **BUT the LIVE tight-range gate is too NOISY to capture it: +20.4 / −8.7 / +12.2 / −16.5 across sessions ≈ 0 avg** (a crude range folds winners as often as it saves). The oracle-vs-live gap = the precision a range_top lacks. → capturing it needs nuanced "fold non-nutted hands to big GTOW aggression" judgment = **RL with a STRONG opponent** (solver/blueprint bot in the self-play league → punishes over-paying-off AND over-aggression — the concrete, grounded RL target), or a heavy board/action-aware range model. Realistic RL upside: raw **−55 → ~−30-40** (part of the +47 ceiling), NOT −17, and uncertain (RL regressed once). This RE-MOTIVATES option B with a concrete target.
> **★ B's $0 PREP → REFUTED THE CHEAP RL FIX (user "go"; 3 grounded rollout tests, $0).** The plan was "train RL vs a balanced league (drop the exploitable maniac/station) so the reward punishes over-paying-off". Verification KILLED it: (1) call-EV vs maniac vs tag league = +0.0 (after a call the action CLOSES → CRN-fixed cards → opponent style is irrelevant post-call); (2) call-EV of maniac-generated vs tag-generated facing-bet spots = +0.3 bb (tiny); (3) bluff-EV vs over-folder nit vs tag = +0.0. ROOT CAUSE: the sixmax `PROFILES` differ mainly **PREFLOP** (open-width/3bet%); **POSTFLOP all 5 share ONE base `_decide` engine — 68% identical decisions, the 32% diffs are EV-low-leverage.** So reshuffling the RL league CANNOT change the postflop reward (where the over-paying-off/over-betting tail lives). **The real wall = the OPPONENT CEILING:** RL trains vs a ~−47 postflop engine → you can't learn GTOW-discipline from a −47 opponent, and no GTOW-level postflop opponent exists for the loop (solve_node ~76s = too slow per-rollout; SolverSlumbotBot ~engine-level). → **NO cheap/medium RL fix.** Closing the gap needs a MAJOR project (a solver-distilled strong postflop opponent net; realistic ceiling ~−45 = engine-level, NOT the leaderboard) or accept −55. The $0 verify SAVED the ~$15-20 run. Tooling: the league lives in `training/rl_env.py::TRAIN_LEAGUE` (unchanged — the fix was refuted before editing).
> **★ HONEST REFRAME:** the model's real level ≈ **−55 raw avg** (−82 this session; the −17 "body" is a trimmed diagnostic, NOT the achievable result), with a fat tail = mostly-irreducible coolers + a REAL -EV over-paying-off slice (oracle +47 avg, RL-targetable). The CHEAP serve levers are now EXHAUSTED + measured: made-hand wiring **+40 (the one robust win)**, to_call (within noise), solver_freq hint (neutral), retraining (regressed), the anti-spew gate (refuted). **The only remaining real lever is a BETTER RL REWARD** (GTOW-anchored / a stronger league) to cut the -EV postflop aggression — the hard, deferred one. $0, 0 pods, NO serve-path code shipped (the gate was refuted as a counterfactual before building). See [[gtow-tail-body-vs-spew]].

## ★★★ CURRENT (2026-06-21 night #2) — the wiring-hint (solver_freq) is NEUTRAL; AND the "−28.36" was a LUCKY draw (same-config re-measure = −49.52 → true ≈ −37 ± 8). Pinning with n=1500.
**Autonomous wiring-optimization round (`format_spot` solver_freq hint, default-OFF, env-gated, A/B'd vs the baseline). Two findings, the second bigger than the first:**
> **★ solver_freq hint = NEUTRAL.** Paired A/B (n=500/arm, made-hand+to_call ON in BOTH, `gtow_glm_pod --ab-hints`): ON (advisor bet-freq hint) **−49.21 ± 29.00** vs OFF (no hint) **−49.52 ± 11.71** → Δ ≈ 0. The hint doesn't help → reverted (flag `POKERB_SOLVER_FREQ` stays default OFF; baseline byte-identical). The OOD-serve-hint lever (after the made-hand win) appears EXHAUSTED.
> **★ THE BIG ONE — the "−28.36" was a LUCKY draw.** The OFF arm above = the EXACT baseline config (`grpo_slim` + made-hand + to_call, no hint), re-measured this session = **−49.52**, vs the earlier to_call-A/B measurement of the SAME config = −28.36 (Δ21, ~1.35σ apart). **Combining the two n=500 measurements → the true baseline ≈ −37 ± 8, NOT −28** (the "Claude-level −28.36" headline was over-optimistic — a favorable tail). This is "small samples lie" in the flesh: even AIVAT n=500 swings ±~20 session-to-session for this 9B.
> **★ CONSEQUENCE (honest re-grade of the session's gains):** the **to_call +12 (0.7σ) is WITHIN the session noise** — a correct bug-fix, but NOT an established bb/100 gain. The **made-hand +40 (OFF −84.11 → ON −43.46, n=500/arm, 2.1σ, variance halved) remains the ROBUST win.** The model's honest GTOW level ≈ **−37 to −45 (high variance)** — well above the −84/−94 no-fix, but NOT Claude's −28. (The new GRPO −90 regression still stands — far below even the noisy baseline.)
> **★ PINNED (n=1500): raw AIVAT −68.20 ± 16.82 — but it's a FAT-TAIL artifact, not the true level.** The wide SE (±16.82 at n=1500!) flagged it; the x-ray shows **~half the −68 comes from 10 catastrophic hands** (the worst = a single **−207bb stack-off**); the **TRIMMED mean (drop 10 worst+best) = −39.8** (excl-10-worst = −33). So the three measurements (−28.36 / −49.52 / −68.20 RAW) reconcile: the model's **ROBUST level ≈ −37 to −40**, with a **FAT LEFT TAIL of rare catastrophic postflop stack-offs** (big-pot spew, −100 to −207bb) that swings the RAW mean −28↔−68 session-to-session. **The "−28.36" was a lucky low-tail session.**
> **★ AUTONOMOUS VERDICT (round done, ~$48, 0 pods verified):** (1) no cheap wiring HINT helps (solver_freq neutral; the pattern: perception-fixes help [made-hand +40], strategy-nudges don't). (2) The real remaining lever is NOT a hint — it's **cutting the FAT TAIL (the catastrophic postflop stack-offs)**: a live anti-spew EV-gate on big-pot actions at low equity (the EVFilter-G6 idea applied at SERVE), which would raise the mean AND cut the variance. (3) raw-mean AIVAT at n≤1500 is **dominated by the tail → UNRELIABLE**; future eval needs the trimmed mean / a duplicate-paired-hands harness / much bigger n. **NEXT (deferred — needs design + budget): the anti-spew EV-gate + a tail-robust eval.** The honest headline: the model ≈ **−40 robust** (NOT −28), well above the −84/−94 no-fix, below Claude (−28); the made-hand wiring fix is the robust win.

## ★★★ CURRENT (2026-06-21 night) — the RL/re-SFT attempt REGRESSED (the A/B gate caught it). KEEP the −28.36 baseline. The wins are INFERENCE-WIRING, not retraining.
**Goal was RL/GRPO. Built the clean base (made-hand-NATIVE gold via `dataset/build/add_made_hand.py` byte-identical post-process + `claude_study`, 15,126 rows train==serve, verified) → ran `runpod_rl_campaign` (SFT 98.8% tok-acc → GRPO 400 steps, self-play reward −4→+2) → A/B'd both vs GTOW. Result: a REGRESSION.**
> **★ THE MEASURED RL BALANCE SHEET (all n=500 vs GTOW, frac_bad ~0.005 = clean programs, NOT format-broken):**
> | model | AIVAT | SE |
> |---|---|---|
> | OLD baseline (old GRPO + wiring fixes, made-hand served OOD) | **−28.36** | ±10.11 |
> | NEW GRPO (today's made-hand-native re-SFT→GRPO pipeline) | **−90.18** | ±23.63 |
> | an OLDER SFT (`sft_new.tgz`, mtime YESTERDAY — NOT today's base) | −71.64 | ±16.13 |
> **Today's made-hand-native re-SFT→GRPO pipeline GRPO = −90.18 = a clear regression (~2.3σ vs the −28.36 baseline).** ★ **HONESTY CORRECTION (2026-06-21 night, found in P1 verify):** the clean SFT-vs-GRPO isolation is **UNAVAILABLE** — the campaign pulls only the GRPO (`qwen_poker_grpo.tgz`), so **today's SFT base was saved on the pod but NEVER pulled → LOST** when the pod self-killed; the "−71.64" I A/B'd was an **OLDER SFT** (`sft_new.tgz`, mtime 2026-06-20), not today's base. So WHETHER today's new SFT base or the GRPO step drove the regression is **UNRESOLVED** (both the −90 GRPO and the older −71 SFT are far below −28). The `gtow_glm_pod` A/B + the protected baseline = the "never ship a regression" gate WORKING.
> **★ THE MECHANISM (x-ray of TODAY's −90 GRPO, `gtow_xray` on gtow_hands_1782053161): postflop SPEW, RIVER-dominated** — river −211 (contribution −74 of −90), turn −130; **preflop −3.3 = fine**. (The older SFT also spewed postflop, river −169.) Consistent with RL/GRPO adding -EV aggression (the self-play sixmax league ≠ GTOW → it learned to beat the weak league by spewing, which loses to GTOW). **NOTE: the postflop spew is NOT uniquely tied to made-hand-native** (the older made-hand-OFF SFT also spewed) → "made-hand-native backfired" is a plausible HYPOTHESIS, not isolated; the −28 baseline (old GRPO + serve-OOD fixes) is the exception that avoids the spew.
> **★ OPERATIONAL LESSON:** `runpod_rl_campaign` pulls ONLY the GRPO adapter → it LOST today's SFT (couldn't A/B it). Next campaign MUST pull the SFT too (NOTES.md).
> **★ THE LESSON (ties the whole session together):** every win this session was INFERENCE-WIRING (to_call +12, made-hand +40 OOD), NOT weights. Retraining to "consolidate" them REGRESSED the model; RL didn't lift (the self-play league ≠ GTOW → it learned to beat the weak league by spewing, which loses to GTOW). **The −28.36 baseline (old GRPO + the code's wiring fixes, served OOD) is the PRODUCT — preserved as `models/grpo_slim_baseline.tgz`.** Don't ship the new models. Path past −28 needs a BETTER RL REWARD (GTOW-anchored / stronger league), not retraining or more steps. Cost this round ~$28 (campaign + 2 A/Bs), **0 pods after (verified), under the $50 ceiling.** See [[glm-resft-regression]].

## ★★★ CURRENT (2026-06-21 late) — GRADED all 264 of Claude Code's OWN GTOW decisions: 96.2% GTO-supported; the −38 AIVAT is river/big-pot VARIANCE, not leaks; the ONE real leak = postflop over-checking. ★ Found + FIXED a preflop HARNESS BUG (a co-cause of the GLM −41/hand over-fold).
**The richest log we have — Claude Code (this agent, not the API) drove the engine 100 hands vs GTOW with per-decision reasoning logged (`data/claude_play/thought_log.jsonl`, 264 decisions) — fully worked out.** Graded EVERY decision vs ground truth: preflop → the near-Nash blueprint, postflop → TexasSolver `api.solve_node` (**98.8% coverage**, 160/162), + equity-math; with an INDEPENDENT OpenAI gpt-5.x 2nd-opinion on the 33 hardest spots. **Full doc: [`reports/CLAUDE_VS_GTOW_STUDY.md`](reports/CLAUDE_VS_GTOW_STUDY.md). Code: `research/study_{grade,analyze,review,distill}.py` (a reusable grading harness — reconstruct ANY GTOW/Slumbot session's spots via `slumbot.build_state` → grade vs solver/blueprint). Memories: [[gtow-tocall-preflop-bug]], [[claude-code-vs-gtow-study]].**
> **★ THREE METHODS CONVERGE — the decisions were STRONG, the loss is VARIANCE.** (1) Deterministic: **252/262 scored in GTO-support (96.2%)**, preflop **95% pure-GTO**, recon 264/264. (2) OpenAI independently **agreed with 82%** of the hardest actions, every disagreement ≤ 1.2 bb (cost $0.07, far under the ~$4 budget). (3) AIVAT: **90% of the −38.4 loss is on river-final hands** (mean −93, n=37), concentrated in strong-hand/big-pot spots (made-hand "strong" −606 over n=8; 30–100bb pots −264, n=3) the deterministic grade rates GTO-fine = **coolers/variance, NOT leaks** (n=100 far too small to call it a leak). **The one real (small) leak: postflop OVER-CHECKING / under-betting (flop+turn semibluffs of draws/weak hands)** — `check` mean P(gto)=0.41, sumDev 52.3 (the dominant deviation); deterministic + OpenAI agree exactly. Magnitude likely lean-solver-tree-amplified (honest).
> **★ THE BIG FINDING — a PREFLOP HARNESS BUG, now FIXED + regression-locked.** The live `gtow_to_state` logged `to_call = total_pot − common_pot`, which inflated the preflop `to_call`/`required_equity` to the WHOLE pot in **100% of preflop facing-bet spots** (mean **+0.22**; e.g. it showed 0.50 when the truth is 0.28 — GTOW's `common_pot` excludes the blinds during active preflop betting; postflop was 0% inflated). **This is a prime CO-CAUSE of the documented GLM −41/hand preflop over-fold, and it's WHY blueprint-routing fixed the GLM (the blueprint bypasses the bad input).** Claude Code's own preflop was IMMUNE (95% pure-GTO via blueprint-deferral; cited the bad number only 5/140 times). **FIX (shipped):** `pokerbot/benchmark/gtowizard.py::gtow_to_state` now uses the committed-delta `max(0, max(c_h,c_v) − c_h)` (correct on EVERY street; postflop a no-op), locked in `gtowizard._selftest` (BB-vs-open=125 not 325; SB-open=50 not 0). The AIVAT measurements themselves were always GTOW-computed and CORRECT — the bug degraded the brain's INPUTS → worse play, so the fix should LIFT future play. **★ MEASURED (2026-06-21 late) — the to_call fix is a SUGGESTIVE +12 bb/100 lever (paired GTOW A/B, n=500/arm, made-hand ON both, GLM drove preflop ITSELF): OFF (old bug) −40.40 ± 12.83 → ON (fix) −28.36 ± 10.11.** The ON arm is the **BEST GLM-vs-GTOW number ever** — +15 over the protected −43.30, = Claude-Opus's −28.55 — and mechanistically clean (`FLOW SPLIT preflop_switch=0` → the fix acted directly on the GLM's preflop inputs). **HONEST (grounded-gate): the paired Δ +12 ± ~16 is only ~0.7σ** (the arms' running means overlap heavily) → SUGGESTIVE + directionally-consistent + best-ever + mechanistically plausible, but NOT statistically conclusive at n=500/arm; the fix is a verified correctness bug regardless. Pod self-killed, **0 pods** (independently verified), ~$3. **NEXT: a bigger paired run (~1500/arm) to confirm the +12 at ≥2σ** — if it holds, the to_call fix + the made-hand wiring together recover the GLM from −43 to ~−28 (Claude-level) = a major, cheap, gold-free lever. Output: `data/gtow_glm_ab_tocall.txt`; harness `infra/gtow_glm_pod.py --ab-tocall`.
> **★ GTOW-ORACLE CROSS-CHECK (2026-06-21, `research/gtow_oracle_check.py`) — the "engine is the wall" hypothesis is NOT supported; the oracle is solid.** Tested whether OUR oracle agrees with GTOW's ACTUAL play across the **7,565 logged hands** (GTOW reveals its holes + every action on ALL of them, even the 2,272 folds). **Preflop blueprint: 93.8% of GTOW's real actions in our support** (n=6,203; the only gap = 320 "surprise folds" where GTOW folds tighter than our blueprint). **Postflop solver: 90.1% in-support, 64% modal, mean-prob 0.62** (n=172, 96% solve coverage) — **as aligned as the preflop blueprint.** → our solver is NOT grossly broken; the −28 wall is NOT "our oracle is wrong" → **a speculative full postflop-solver overhaul (plan #2) is NOT justified by the data** (this test saved that detour). CAVEAT: the test is COARSE (action-FAMILY, not sizing/frequency; n=172 ±~5%) — a right-family-wrong-size leak stays invisible. **The one localized weak spot: the TURN (86% in-support, modal only 47% vs flop 68%/river 80%)** — matches the thought_log turn-leak exactly = the focused target (turn sizing/tree + our under-betting). **REVISED ROADMAP: the two big levers (to_call +12, made-hand +40) are captured; the oracle is solid; there's likely NO single big bug left.** Path past −28 = (1) the CHEAP hygiene re-SFT (made-hand native + claude_study + corrected inputs → train==serve), (2) RL/GRPO on the existing decent oracle, (3) turn/sizing refinement — NOT a ground-up engine rebuild. Output: `data/gtow_oracle_check.log`.
> **★ LOOP CLOSED:** `research/study_distill.py` distilled the **243 graded-clean decisions** (recon_ok + GTO-supported + math-OK; reasoning-cited-the-inflated-input ones EXCLUDED) into `dataset/shards/claude_study.jsonl` (EVFilter G1–G6 gated, 0 illegal/0 EV-reject, balanced action-mix), **registered as `sft_gold`** (`registry.shard.claude_study`) → the next re-SFT picks it up. Honest cap: warm-start, NOT a lift above my own play. All work LOCAL/$0 except $0.07 OpenAI; **no pod** (an accidental PC shutdown mid-run cost nothing — all artifacts are reboot-safe on disk).

## ★★★ CURRENT (2026-06-21 PM) — MEASURED vs GTOW: the made-hand WIRING is a +40.65 bb/100 LEVER. Paired A/B at n=500/arm: OFF (no fix) −84.11 ± 16.91 → ON (fix) −43.46 ± 9.49, frac_bad ~0.008. Variance HALVED.
**The at-scale confirmation of the local diagnosis (user-gated pod run, H200, ~$2.6, 0 pods after).** A PAIRED A/B in ONE pod (same re-SFT model, same GTOW) toggling `format_spot.INCLUDE_MADE_HAND` (POKERB_MADE_HAND):
> **★ RESULT — the engine hand-read in the prompt is worth +40.65 bb/100 (−84.11 → −43.46), and HALVES variance (±16.91 → ±9.49).** ~2.1σ (combined SE 19.4, p≈0.02 one-sided). The fix's mechanism = it removes the misread-UP SPEWS (a weak pair read as "a flush" → a big bet) which ARE the high-variance blow-ups → both the mean AND the variance drop, exactly the local-A/B signature. frac_bad 0.006 (ON) / 0.009 (OFF) = the OOD line never breaks the model at scale.
> **★ HONEST CORRECTION — the −94 was NOT (mostly) variance.** An interim read (after only the ON arm) guessed "−94 = variance, the model is really ~−43." The OFF arm REFUTES that: the no-fix model is **−84.11 (n=500)**, corroborating the original **−94 (n=100)** — two independent samples agree the no-fix model genuinely plays ~−84/−94. The +41 lift is the FIX, not luck. (The calling-discipline IS clean — the leak was the misread-up spew on the BETTING side, which the local probe also flagged.)
> **★ STANDING vs the protected −43.30 baseline:** re-SFT+fix (−43.46) ≈ the GRPO baseline (−43.30). So the Claude-teacher re-SFT had REGRESSED the model (to −84) and the made-hand fix RECOVERS it to baseline. **−43 does NOT beat GTOW** (nobody does; best −3.14) — the win is the grounded +41 lever, not the level. **HIGH-VALUE NEXT (deferred):** apply the fix to the GRPO baseline (`grpo_slim_baseline.tgz`) — if it carries the same misread leak, it could drop below −43. And: the next re-SFT must rebuild the gold with `INCLUDE_MADE_HAND` ON (train==serve). Harness: `infra/gtow_glm_pod.py --ab` (the paired toggle) + `pokerbot/brain/format_spot.py` (`POKERB_MADE_HAND`).

## ★★ (2026-06-21 — the LOCAL diagnosis that led to the +41 lever above) — the −94 was NOT over-call spew; the real postflop leak = the GLM MIS-READS its own made hand in NL. Fix WIRED + A/B-validated locally ($0): inject `api.hand_rank` into the prompt.
**The user's "run the trained LLM locally on the exact problem spots" paid off** (`research/glm_local_probe.py`, GLM-9B 4-bit on the 3080 Ti, re-SFT'd adapter `models/qwen_poker_lora`, `<think>`-stripped, greedy). Two grounded findings:
> **★ DIAGNOSIS — the calling discipline is GOOD; the leak is NL HAND-READING (both directions).** Across 13 spectrum spots the GLM **folds no-equity air, defends draws/marginals to ~pot-odds, checks back air** (11/11 weak+mid correct, frac_bad 0) → it does NOT over-call → the `postflop_corset` is a NO-OP (the over-call leak it bounds doesn't exist). The REAL leak: on coordinated boards the GLM mis-reads its OWN made hand in natural language **both ways** — DOWN (a **full house → "two pair"**, a **flopped straight → "air"** → it CHECKS monsters = lost value, which shows as small-won-pots not −AIVAT) AND UP (a **weak pair → "I have a flush"** → a spew-BET, which DOES show as a −94 loss). `api.hand_rank` reads all of these EXACTLY (verified: Full House 0.96 / Straight 0.79 / Two Pair 0.62 where the GLM said two-pair/air/trips). So the −94 ≈ cooler-variance (~half, washes out at n=500) + misread-UP spews + small edges — NOT air-over-calling.
> **★ FIX — the LLM↔engine WIRING (the user's "the wiring is the high-leverage move"):** `pokerbot/brain/format_spot.py` now injects the exact engine read postflop — `Made hand (engine): <category>, strength <s>/1.0` (flag `INCLUDE_MADE_HAND`, now **ON**, postflop-only). **Paired LOCAL A/B (`glm_local_probe.py`, OFF vs ON, same spots):** 7 spots, decision changed on 4 = **3 clear FIXES** (boat: check→**value-bet**; two-pair: wrong-tight fold→**call**; hallucinated-flush: spew-bet→**check**) + **3 controls preserved** (semi-bluff raise / check air / fold weak bottom-pair) + 1 borderline-looser thin call (#3; the corset backstops). **frac_bad 0** (GLM-Z1 uses the OOD line cleanly). Deterministic test `tests/test_made_hand_read.py` PASS (correct category in the prompt; OFF + preflop → no line). **NOTE:** the deployed adapter was SFT'd with this OFF → serving ON is mildly OOD (validated fine); the NEXT re-SFT rebuilds the gold with it ON so train==serve.
> **★ HONEST — what is NOT yet measured:** the at-scale bb/100 (the production metric). The GTOW variance model is weak at n=100 (±48 on the −94) → the confirmation is a **~500-hand GTOW run** (a pod = user-gated; "small samples lie"). So: grounded LOCAL evidence the fix helps (paired A/B + deterministic test); the GTOW number is the deferred at-scale gate. All work this session was LOCAL/$0 per the user's constraint. The −43.30 GRPO model remains the protected baseline; the hand-read fix is a candidate to A/B vs it.

## ★★ (2026-06-19 PM — the measured baseline, still protected) — the GLM-Z1-9B brain is MEASURED vs GTOW: −43.30 ± 7.15 bb/100 AIVAT (n=100, frac_bad 0.009 = it DROVE 99%). Our own RL-able AI works end-to-end.
**Pivot in execution: OUR OWN, RL-able brain = GLM-Z1-9B (THUDM, MIT) — SFT-distilled on the DSL gold → lifted by self-play RL.** Plan: `.claude/plans/gut-dann-sind-wir-toasty-forest.md`. Phases A (data) + B (run-card) DONE; Phase C (the pod SFT→RL) runs on a **RunPod H100 SXM (`NVIDIA H100 80GB HBM3`, SECURE)**. Cost so far ~$11 (all smokes self-killed; `runpod_run --status`/API = 0 pods verified between rounds).
> **★ ACHIEVED — the GLM-Z1 SFT LEARNS (the warm-start is solved, reproducible):** DSL-SFT = **loss ≈0.087, mean_token_accuracy 97.5%, grad_norm ≈0.13** over the 33k DSL gold rows (`registry.sft_gold()` = a_contract/c_decide/solver/solver_mass). GATE 0 effectively passed — the model cleanly emits the DSL programs. The vLLM-GLM generation probe passes at **7.6s/step**.
> **★★ MEASURED (2026-06-19 PM) — the GRPO model (checkpoint-400) vs GTO Wizard = −43.30 ± 7.15 bb/100 AIVAT (n=100; RAW −61.09; the GLM drove 111/112 = 99%, frac_bad 0.009).** Our OWN trained 9B emits clean program-of-thought (`vr=api.range_top(.18); eq=api.equity(..); req=api.required_equity(..); if eq>=req+0.2: decide_mix({'raise':.75,'call':.25})`) and orchestrates the engine vs the real benchmark. HONEST: ≈ the pure-engine level (−47.18; NOT a significant beat within ±7.15), well below Claude+engine (−28.55) + the leaderboard (−16) — the EXPECTED 9B-first-pass number (imitation-cap). Harness = `infra/gtow_glm_pod.py` (ISOLATED pod → merge the GRPO LoRA into the base → vLLM-serve → `gtow_client --agent-type glm`) + `tools/gtow_client/src/poker_agent.py::GLMBrainAgent` (vLLM `/v1/completions`, `<think>`-stripped prompt, solver-floor fallback). **THE BUG THAT HID IT (frac_bad 1.0 → 0.009): `executor.run_program`'s SIGALRM timeout only works in the MAIN thread; the client decides via `asyncio.to_thread` (worker) → SIGALRM raised → EVERY valid program counted "bad". Fix: `_alarm_available()` also requires `threading.main_thread()`.** Pod-infra fixes en route (all WHY-commented): `fastapi<0.137` (vLLM 0.11 prometheus middleware dies on 0.137's `_IncludedRouter`), `tar --no-same-owner` (Windows-uid tarball chown), `setsid` daemonize (ssh-launch hang), `PYTHONUTF8`/utf-8 stdout (cp1252 print crash). The smoke's 63s/hand was vLLM COLD-START; the 100-hand full ran 1.27s/hand.
> **★ THE LEVER (2026-06-20) — POSTFLOP overhaul (the preflop switch was TRIED + REVERTED):** a per-hand-log diagnosis found the −43.30 loss was ~**90% PREFLOP** (94/100 hands end preflop at **−41/hand**; 0 all-in) vs the engine blueprint's **−1.6/hand**. So a preflop-SWITCH (route preflop → blueprint via the `SolverSlumbotBot` floor in `GLMBrainAgent`) was tried — but it stopped the over-folding → more hands reached postflop → **EXPOSED the real, deeper leak: POSTFLOP SPEW** (−43.30 → **−99.39 ± 48**; the pure engine also spewed — one −133bb hand). **REVERTED** (2026-06-20) → back to the protected −43.30 baseline (the core `pokerbot/` was never touched). **The real lever — 3 cutting-edge papers (s10462/s41598 CFR-FSP surveys + Paper X NatLTL) CONVERGE: the postflop SOLVE is exploitable — its ranges are NOT line-aware + there's no safe-subgame-solving** (CFR+/DCFR is moot — TexasSolver is already DCFR; ours is HOW we call it). **PLAN #2** (`.claude/plans/gut-dann-sind-wir-toasty-forest.md`, ACTIVE at top): **2a** line-aware `solve_node` ranges (derive from the blueprint per line — `_HU_IP/_HU_OOP` are fixed/inexact by the code's own admission), **2b** safe-subgame wrapper, **2c** route the GLM postflop to the now-safe solve (+ pod TexasSolver) — each **A/B-GATED vs −43.30** (Paper X's IsNash = "never ship a regression"). DEFERRED: `format_spot` enrichment (OOD → needs re-SFT), 2d value-net leaf eval.
> **★ EXECUTION (2026-06-20): Phase 0 REVERTED (✓ −43.30 restored, code-identity) + 2a BUILT + range-validated.** `api.py::solve_node` now derives **line-aware reach-weighted ranges from the blueprint** per preflop pot type (srp/3bet/4bet) — flag `POKERB_LINE_RANGES` (default **OFF** = bot unchanged). Verified $0: 3bet-pot ranges concentrate correctly (BB-3bet AA:1.0…22:0.03; SB-call mid-pairs) vs the old fixed ~61%-uniform. **GROUNDED-GATE HONESTY:** a bb/100 mean A/B of the PURE ENGINE is variance-INFEASIBLE (±147 → ~3500 hands needed; "small samples lie") → 2a's gate is (a) deterministic range-correctness (✓) + (b) the per-hand **SPEW** (does 2a kill the −133bb wrong-range overbets?) — a 2a-ON engine run vs GTOW is measuring this. **The path to a GLM bb/100 GAIN = the FLYWHEEL:** line-aware solver → regenerate postflop GOLD → **re-SFT** the GLM (its low-variance ±7 A/B IS feasible). 2c (route GLM postflop to the safe solver directly) = the engine plays postflop = high variance → the flywheel (GLM internalizes it) is the better path.
> **★ FLYWHEEL — the path to the re-SFT (2026-06-20; history, 4 grounded-gate saves):** LINCHPIN: the preflop gold was **100% equity-logic, 0% blueprint** = exactly why the GLM over-folds (−41/hand = 90% of −43.30). The fix chain, each step **$0-gated BEFORE spending**: built `api.preflop_solve` (blueprint→DSL verbs+sizes, n_active==2-gated) → found the gold is 6-max but GTOW is HU (HU-blueprint sparse) → built the HU-gold pipeline (`from_hu`; dict-literal `decide_mix({...})`, since `decide_mix(var)` is grammar-invalid) → caught a FATAL gen↔node gap (`gen_decision_states` never maps the OPEN/raise nodes → 0 raise-modals → would reinforce passivity). **The $0 grounded gate stopped 4 weak pod runs this session.** RESOLVED ↓ (direct node-enumeration).
> **★ FLYWHEEL — RE-SFT FIXED, then PAUSED (2026-06-20):** the node-coverage blocker is FIXED. `dataset/build/from_hu.py` rewritten to **DIRECTLY enumerate the blueprint nodes** (drive an HU `Table` to each of ROOT/LIMP/OPEN/ISO/3BET/4BET × hand-class × seed → `decide_mix({...}, size=)` dict-literal) — bypasses the broken `gen_decision_states` mapping. Produces **12168 rows, all 6 nodes evenly (2028 each), modal raise 2856 / call 4956 / fold 3204 / check 972 / allin 180** (the 0-raise gap is CLOSED), 0 grammar-invalid, load_dsl-verified (38273 total gold rows, 0 malformed). In `registry.sft_gold()`. **ROOT CAUSE of all 3 re-SFT aborts = a `UnicodeEncodeError` print-crash, NOT the model:** the SFT trains PERFECTLY (loss 1.94→0.10, token-acc 0.70→**0.97**, ~60min / 625 steps @ MAXN=10000, adapter SAVED on the pod) — but the campaign's `print()` of the captured pod stdout (unicode tqdm bars █▏▎, arrows) crashed on the **cp1252 Windows console** → aborted the healthy run + killed the pod BEFORE the pull. FIXED: `PYTHONUTF8=1` launch **+ a permanent `sys.stdout.reconfigure(utf-8, errors=replace)`** in the campaign (a glyph can NEVER kill a run again); also added the SFT `tee`+pull-on-fail + `infra/_resft_mon.py` (independent idle-crash monitor). **PAUSED INDEFINITELY (2026-06-20, user) before the FIXED run produced an adapter** — ~$10-11 spent across 3 aborted runs (all the same print bug). The **−43.30 GRPO model is the live/protected baseline.** RESUME: `PYTHONUTF8=1 BASE=THUDM/GLM-Z1-9B-0414 GPU="NVIDIA H100 80GB HBM3" SFT_MAXN=10000 SFT_TO_CAP=4800 HARD_CAP_S=9000 python -u -m infra.runpod_rl_campaign` → pull the adapter → A/B vs −43.30. Honest expected gain: **MODEST (~−33 to −38, +5 to +13)** — the preflop over-fold fix is real but exposes the unproven postflop (the preflop-switch precedent regressed to −99); the leap to −28/−16 needs the postflop lever 2a/2b (deferred).
> **★ THE BRING-UP CHAIN (~11 self-killing smokes; every bug REAL + fixed — GLM-Z1 + Blackwell/H100 + vLLM 0.11 + trl 1.6 is new territory; each fix in the code with a WHY-comment):** flash_attn-missing→`ATTN=sdpa` · GLM template has NO `{% generation %}`→**patch the template** so `assistant_only_loss` masks the completion (verified $0 local) · 9B OOM at batch 16→`GRAD_CKPT=1`+batch 8+`enable_input_require_grads` · **loss=0 (the silent killer)→`MAX_LEN 1024→2048`**: the SYSTEM_PROMPT is **1142 tokens > 1024**, right-truncation cut the completion off EVERY example → zero trainable tokens (+a loud guard added) · `TEMP`→`GEN_TEMP` (Windows always sets `%TEMP%`=a path → `float()` crash in the probe) · COMMUNITY-RTX-6000 flakes (removal-alert + SSH-never-exposed)→**H100 SXM SECURE** (Blackwell sm_120 itself is FINE — torch cu128+bf16 verified — but the COMMUNITY supply is unreliable) · probe HANG→`STRUCTURED=0` for GLM (the bounded-think `[\s\S]{0,1500}</think>` regex state-explodes vLLM's xgrammar) · **frac_bad 0.94→`<think>`-STRIP** (the GLM template forces `<think>` at inference but the SFT is program-only → OOD; strip it so the prompt ends `<|assistant|>\n` = byte-aligned with the SFT, verified as a prefix) · campaign CONCURRENCY (two campaigns share one session file → the finisher kills the other's pod → RULE: SERIALIZE, one campaign at a time).
> **★ THE OPEN QUESTION (the actual thesis — NOW PARTIALLY ANSWERED):** the GRPO model is measured (−43.30 vs GTOW above), but whether the **RL LIFTED above the SFT warm-start** is still open. The clean test is now **SFT vs GRPO on GTOW** (`GLM_USE_SFT=1 python -m infra.gtow_glm_pod`, ~$2) = GATE-2 via the REAL benchmark (the internal `qwen_eval_gto` proxy was abandoned — transformers.generate eval is ~10s/hand = too slow; vLLM-on-GTOW is both faster AND the real measure). If SFT ≈ GRPO → the RL didn't lift (re-tune reward/steps/more RL); if GRPO > SFT → the flywheel works. A bigger-n GTOW run (500-1000) would tighten ±7.15 → ±3 for a leaderboard-grade number.
> **★ STRATEGY (clarified with the user):** GLM is used as an **adapted FULL net** — the reasoning-tuned 9B weights are fine-tuned to our task (NOT wasted); the `<think>`-strip drops only the EXPLICIT inference-CoT (the lever that gave Claude −9), which is **deferred upside** (path B: Claude-reasoning-distilled CoT gold + a non-stripping template), NOT an incoherence. Our completions are brief program-of-thought (a `# read:` line + the `api.*` program); the lift must come from RL.
> **★ 2-NODE SPLIT ACTIVE:** the pod GPU trains; the idle PC CPU runs a **turn mass-solve** (`research.mass_solve STREET=4` → TexasSolver cache) to fill the FLOP-SKEWED gold (flop 28421 / turn 575 / river 373). It writes a CACHE (not gold) → the running RL is untouched; `from_solver` converts it + the format is verified BEFORE folding into a NEXT run (the frac_bad-safe rule: byte-identical `format_spot` + reasoning-loop DSL only).

## ★★ (history — 2026-06-19 AM, the PRIOR frontier + now the TEACHER/PROOF; superseded as the ACTIVE work by the GLM-Z1 RL above) — METRIC RESOLVED + the FRONTIER-LLM-BRAIN proof.
**Our GTOW account = −47.18 ± 1.48 bb/100 AIVAT over 20,859 hands** (`/results`, CONFIRMED AIVAT — the "−47" the user remembered IS real + tight, not a different metric, not Slumbot). **We are NOT in the top-10 leaderboard** (worst shown MIT −16.78; best Bitcrumbs −3.14, human Kevin Rabichow −3.91) — −47 is ~3× below the visible field → "we secretly understand the math better" is NOT data-supported. **Reconstruction via the `POKERB_EXPLOIT` toggle FAILED:** exploit-OFF = −93 ± 23.5 (n=146) ≈ exploit-ON −74.7 ± 5.9 (<1σ apart) → the CURRENT code plays ~−75 to −93 and has REGRESSED from the −47-era (an earlier code state was better); no toggle recovers −47, and −47 isn't leaderboard-worthy anyway.
> **★ THE FINDING THAT FLIPS THE PLAN:** Frontier LLMs are ON the leaderboard — **GPT-5.2 −8.26, GPT-5.5 −9.23** — i.e. an LLM-driven agent plays HUNL **~5× better than our whole engine** (−9 vs −47). This EMPIRICALLY corrects the prior "engine-fidelity-first / an LLM can't beat the engine's GTO quality" stance: a strong *pretrained* reasoner does NOT imitate our engine — it brings its own reasoning (~−9). The imitation-cap (≤ our −47 data) applies ONLY to **TRAINING a small model on our data**, NOT to **PROMPTING a frontier model**. → **Recommended next = a `ClaudeBrainAgent`:** Claude Opus 4.8 drives `brain/api.py` via program-of-thought (`executor.py`; math + legality = engine, judgment = Claude), targeting ~−9 (GPT-5.5 territory) = best-ever by ~38 bb/100 + a leaderboard slot. Claude = proof + placement; a Qwen-distill = the "own AI" product (Step 2, honestly capped lower since 8B ≪ Opus). Read-only standing: `tools/gtow_client/src/leaderboard_rank.py`. Plan: `.claude/plans/gut-dann-sind-wir-toasty-forest.md`.
>
> **★ MEASURED (2026-06-19) — the `ClaudeBrainAgent` is BUILT + ran clean vs GTOW: −28.55 ± 7.25 bb/100 AIVAT (n=500, correct bb=100; RAW −47.42 ± 64.23; Claude drove 99%, frac_bad 0.011, solve_node 453×, ~$8.32).** Our BEST HU number — **+18.6 vs the −47.18 account avg = 2.5σ significant**; vs the recent exploit-ON engine (~−37 real) +8 ≈ 1σ (suggestive). Still LOSING vs GTOW, not yet leaderboard (−16). Files: `pokerbot/brain/claude_brain.py` (`ClaudeBrain`), `research/llm.ask_claude` (thinking=adaptive), gtow `--agent-type claude`.
> **★ BB-BUG FIXED (consequential):** the local runner + `gtow_to_state` used `blinds[-1]`=SB=50 as the big blind (real BB=100) → **ALL prior LOCAL GTOW bb/100 were 2× inflated** → the "regression to −75/−93" was an ARTIFACT: exploit-ON −74.7→real ~−37, exploit-OFF −93→~−46.5 ≈ the −47 era (NOT regressed). Server-side `/results` −47.18 was always correct. `research/gtow_xray.py` STILL hardcodes bb=50 → ÷2 its output. WHERE Claude loses (gtow_xray ÷2): preflop ~−17 (blind-cost), **jam/big-bet ~−7 from only ~10 hands = Claude's deep-jam SPEW** (calls AKs off; `research/claude_vs_engine.py` paired-diff confirms; its program even degenerated to "always call"), river ~−8. **NEXT (cheap, high-leverage):** make Claude use the MATH in jam spots (fold AK/QQ to a 200bb jam) → est −28.55 → ~−21 (near the −16 cutoff).

## ★★ (history — 2026-06-18 PM, superseded by the 2026-06-19 finding above) — SOLVER-SEARCH-AT-INFERENCE (the brain DRIVES the exact local TexasSolver postflop — ReBeL/Pluribus-style — NOT RL). ⏳ NOW benchmarking vs **GTO WIZARD AI** — the API key WORKS again (verified) → **AIVAT-scored** (~10× variance reduction = the rigorous low-variance HU test, vs an opponent STRONGER than Slumbot). Solver-search GTOW agent built (`tools/gtow_client` `--agent-type solver`, 100% postflop solve-rate live) → **MEASURED: −74.9 bb/100 AIVAT over 100 hands** (BAD — worse than the leaderboard cutoff −16.78 AND our old account aggregate −46; the "exact solver" is a CRUDE approximation: fixed non-line-aware ranges + lean tree). ⏳ DIAGNOSING the −75 (preflop-vs-postflop leak via `research/gtow_xray.py` on a small completed run; bug vs fundamental). ★★ **KEY ARCHITECTURE DIRECTION saved: [`doctrine/LLM_ENGINE_ARCHITECTURE.md`](doctrine/LLM_ENGINE_ARCHITECTURE.md)** — the LLM↔engine "switch system" (LLM GENERALIZES / engine COMPUTES; LLM-authority INVERSE to engine competence; decompose into small switches for a weak 8B). HARD LESSON: **engine FIDELITY comes BEFORE the LLM layer — a −75 engine can't be rescued by an LLM overlay.** Leaderboard (top-10, ranked by AIVAT-LCB): everyone loses to GTOW (best Bitcrumbs −3.14, human pro −3.91, GPT-5.2 −8.26). Slumbot superseded (299 hands, raw −106 noisy, `data/slumbot_solver_run2.jsonl`). Plan: `.claude/plans/gut-dann-sind-wir-toasty-forest.md`.
> **★ WHY THE PIVOT (3-agent research converged).** Policy-gradient RL on the LLM is STRUCTURALLY mis-fit for poker: no Nash guarantee, high variance, and reward-vs-a-FIXED-league = MAX-exploitable (the OPPOSITE of GTO). SOTA 6-max (Pluribus) = MCCFR + SEARCH-AT-INFERENCE on CPU, NO value net; ReBeL = CFR in a depth-limited subgame; search ≈ 1000-10000× model-size (Brown). → "use the solver MORE, RL less": the LLM ORCHESTRATES the exact solver, it does NOT imitate it. GRPO demoted to history (below).
> **★ BUILT + VERIFIED ($0, local).** (1) `api.solve_node(spot)` — a LIVE TexasSolver solve postflop → the GTO mix for hero's hand. v2 fixed two coverage bugs: tight 6-max SRP ranges → WIDE HU `_HU_IP`(77%)/`_HU_OOP`(61%); cross-street nav stepping into a `chance_node` → per-street RE-ROOT + walk only the current street (mirrors `gto_oracle_match._street_actions`). **HU postflop solve-rate ~0% → 83% (12 constructed spots) / 0.60-0.85 (live Slumbot); sane mixes.** (2) `SolverSlumbotBot` + `slumbot_llm.py --bot solver` (preflop = blueprint [verified leak-free], postflop = solver). (3) CONCURRENCY-SAFE parallel solver (uuid temp-tags + per-key-lock dedup + `SOLVE_THREADS` env → 24-core, NO temp-file collision — the silent-corruption risk). (4) `slumbot_adjust.py` ALL-IN-EV adjustment — Slumbot reveals `bot_hole_cards`+`won_pot` on EVERY hand → equity-EV replaces all-in runout luck (cross-validated to the chip).
> **★ HONEST coverage + the headline.** Solver-search covers only **~5% in 6-MAX** (TexasSolver is 2-player → multiway/preflop falls back to the heuristic floor = the multiway wall) but **~60-85% in HU postflop** → HU vs Slumbot is where it shines (the running bench). Ranges still NOT line-aware (3bet/limped inexact) = future work. The bot plays SMALL pots → low realized variance (the user's variance insight: a fold-hand carries ~0 runout-variance; the variance lives in all-in showdowns → the all-in-EV adjuster targets exactly those). **30-hand directional read: +96.6 bb/100 (±178 = pure NOISE, not a result).** The 3000-hand run + raw/adjusted bb/100 ± stderr = the decisive (or honest-tie) number.

## ★★ (history — GRPO, SUPERSEDED by the solver-search pivot above) — 2H GRPO RUN PAUSED by the user after 2 TIMEOUT fails (INFRA timing, NOT the AI; ~$7-8 spent, all pods killed/$0). The CORE WIN: root-caused WHY the first GRPO didn't learn (reward FLAT −17.6): `R_BAD=−30` SWAMPED the EV signal → FIX `R_BAD=−3` (locally A/B-verified). Model confirmed NON-degenerate. ★ BEFORE RE-RUNNING, fix the TIMEOUT-FRAGILITY (see "WHY PAUSED" below). Plan: `.claude/plans/gut-dann-sind-wir-toasty-forest.md`.
> **★ THE FLAT-REWARD ROOT CAUSE + FIX (2026-06-18).** The first 8B GRPO ran 57 steps but reward stayed FLAT at −17.6
> (no learning; GATE 2 RL>SFT-init FAILED). Mechanical cause: `make_ev_reward` floored every strict-invalid completion at
> `R_BAD=−30` (no EV computed); with ~50% sampled-invalid the mean pinned at ~−17.6 and the Dr.GRPO within-group advantage
> was consumed by the ±33 valid/invalid gap, NOT the ±5-bb EV spread → the policy learned "be valid", not "play well".
> **FIX: `R_BAD −30 → −3`** (`qwen_grpo.py:29` default + campaign pass-through) — un-swamps the EV signal; zero extra
> rollouts / reward-hacking (Plan-agent-verified). **LOCAL A/B GATE PASSED** (1.7B, same seed): control R_BAD=−30 → reward
> −25.6 (pinned, tracks frac_bad); fix R_BAD=−3 → reward −2.5 at a HIGHER frac_bad (0.69) = EV-centered + DECOUPLED.
> Safety: `ABORT_FRAC_BAD 0.5→0.75` (0.5 risked a false-abort — ~0.5 is normal sampled exploration), `HARD_CAP_S=7200`,
> `SFT_MAXN=20000`, and the **setsid watchdog now WIRED into `runpod_rl_campaign.py`** (armed + verified SID==PID at
> launch — the $65 money-safety). The 2h run measures GATE 2 (executed league bb/100); WATCH the dashboard for reward
> TRENDING UP (not flat) + decoupled from frac_bad. **frac_bad ~0.5 was SAMPLED exploration, NOT the lever — the REWARD was.**
> **★ WHY PAUSED — 2 TIMEOUT FAILS (infra timing, NOT the AI; ~$7-8 spent, pods all killed → $0; the R_BAD fix never got
> a clean pod run).** Both attempts died on a phase SSH-timeout: (1) `SFT_MAXN=20000` → SFT >1h → `run_step`
> TimeoutExpired → pod killed pre-pull; (2) `SFT_MAXN=4000` fixed the SFT (loss 0.098, done in ~10min), but the GRPO
> **state-buffer build (`N_STATES=2000`) is SINGLE-THREADED** (`gen_decision_states` + the `pilot.rank_state` EV-spread
> filter) → ~20min on ONE core, GPU idle, 0 steps → it pushes `WallClockStop` past the GRPO SSH-timeout. **ROOT FRAGILITY:**
> a phase SSH-timeout makes `run_step` RAISE → `finally _killall` kills the pod BEFORE the end-of-run pull → the trained
> model is LOST even if a checkpoint saved on the pod. **$0 FIXES BEFORE THE NEXT RUN:** (a) pull-on-timeout (catch the
> GRPO timeout → pull whatever checkpoint exists) and/or a generous GRPO SSH margin that absorbs the buffer build; (b)
> small `N_STATES` (~500-600 → ~2min buffer) and/or PARALLELIZE the buffer build (`build_state_buffer` is single-threaded);
> (c) calibrate `SFT_MAXN` to the budget (4000 ≈ 10min is good). The R_BAD=−3 reward fix + the setsid watchdog are SOUND +
> saved — ONLY the run-plumbing blocks a completed, measured model. (Watchdog + abort + greedy-valid model all verified.)
> **★ MODEL IS NOT DEGENERATE (the PokerBench scare resolved).** A held-out PokerBench *prose* proxy showed our 8B at 15%
> (raise/bet-only) vs base 43% — but a pure METHODOLOGY artifact: prose ≠ deployment `format_spot`, and the proxy reads
> the FIRST `decide()` of a branching program (the prompt examples start with bet/raise) NOT the EXECUTED action. The
> EXECUTED action-mix on 80 real 6-max spots: **fold 40% / raise 36% / check 21% / call 3%, 97% valid** — healthy. A clean
> "vs experts" eval needs prose→`Spot`→`format_spot`→EXECUTE→vs-gold (deferred follow-up).
> **Pipeline infra is now SOLID:** env-hell beaten (torch2.8+cu128 / trl1.6 / vllm0.11); the tokenizers fork-deadlock
> fixed (`TOKENIZERS_PARALLELISM=false` + `dataset_num_proc`); SFT↔inference prompt aligned (`SYSTEM_PROMPT` in
> `load_dsl`); the **DATA REGISTRY + [catalogs/DATA_CATALOG.md](catalogs/DATA_CATALOG.md)** built + drives `registry.sft_gold()`; the campaign
> self-kills + has an early **frac_bad auto-abort that WORKS**. A 70-min attended pod run completed clean (~$1.5).
> **HARD LESSON 1 — ~$65 BURNED OVERNIGHT.** An unattended run + the PC SLEPT ~midnight → the PC-tethered orchestration
> suspended → the SFT died mid-run (nothing saved) AND the pod-side `nohup` watchdog FAILED to fire (didn't survive the
> SSH teardown) → both pods ran IDLE ~5h billing. FIX: the watchdog is now **`setsid`** (detached session leader,
> SID==PID — VERIFIED survives teardown). RULE: unattended runs need a **network volume** + a `setsid`/`at`
> self-destruct, TESTED against a disconnect. The local **3080 Ti (12GB) is too small to train an 8B** (can't finish
> even one step → use it only for ≤1.7B local proofs).
> **HARD LESSON 2 — frac_bad ROOT CAUSE #2: `enable_thinking`.** Even after the prompt-alignment fix, the 70-min run
> still showed **frac_bad=0.93, clipped_ratio=0.72** (long, non-terminating completions). Root cause: Qwen3 THINKING was
> never disabled (the plan demanded "non-thinking throughout" but `enable_thinking=False` was set NOWHERE) → the model
> emits a long `<think>` ramble that fills the token cap before any `decide()` → clipped → frac_bad. **FIX ($0):**
> `enable_thinking=False` added to EVERY generation path — `policy._generate`, `qwen_grpo.build_dataset` (pre-renders the
> prompt to a non-thinking string), `qwen_eval`, `qwen_eval_gto`. VERIFYING via a 1.7B aligned A/B (thinking on/off).
> (The GPU-util "12%" the user saw = the GRPO early-aborted on frac_bad so the GPU-heavy GRPO barely ran — NOT a reward
> bottleneck; the parallel reward worked at 2s/step.)
> **★ SOLVER SEARCH-AT-INFERENCE — HU postflop COVERAGE FIXED (2026-06-18).** `api.solve_node` (the brain DRIVES a live
> TexasSolver solve postflop, `pokerbot/benchmark/slumbot_llm.py --bot solver`) had a real HU solve-rate of ~0%. Two
> traced gaps, both fixed: (1) the fixed tight SRP range excluded most hands the blueprint plays → `strategy_for` None
> — now WIDE HU ranges (`_HU_IP`/`_HU_OOP`) + hero's OWN class force-added so hero's hand is always in the acting node's
> range; (2) turn/river were un-navigable (a `chance_node` follows a flop check-through) — now the solve RE-ROOTS per
> street + `_navigate` walks only the current street (mirrors `gto_oracle_match._street_actions`). + a 90s solve timeout
> (wide solves run 30-56s; old 45s timed 5/25 out). **MEASURED: postflop solve-rate 0.00 → 0.29 (wide-static) → 1.00
> (25/25 decisions, 15-hand Slumbot smoke); fall-back partition empty.** Residual: off-tree raise lines (lean tree has
> no raise size) + still NOT line-aware (3bet/limped ranges inexact) = future work. Probe-verified: dump_rounds=1 dumps
> within-street IP nodes; turn/river re-root roots carry per-combo strategies.

## ★★★ CURRENT (2026-06-17) — ★ 6-max GTO Qwen brain. CONSULT FINDING: the leaks are DISCONNECTED TOOLS (trained advisors/MDF/playbook built but never wired into the DSL). #1 FIX DONE: api.solver_freq wired into the DSL (grammar+prompt+from_selfplay). Serverless teacher PAUSED (workers crash-looped); CPU solver mass-solve reliably producing. Path: advisor-wired corpus → 8B SFT→GRPO on a pod. Plan: `.claude/plans/gut-dann-sind-wir-toasty-forest.md`.
> **★ FRONTIER LEAK-CONSULT + ROOT-FOLDER CROSS-CHECK (2026-06-17).** OpenAI(reasoning)→Claude(technical)→repo-grep
> (`data/leak_consult_result.json`). VERDICT (the user's thesis vindicated): the bot's leaks are NOT missing knowledge —
> they're DISCONNECTED TOOLS. The repo ALREADY has (newer than the APIs knew): trained flop/turn/river GTO advisors
> (`api.solver_freq`, +63%/46%/18% over strength-only), the MDF math, a 62-rule postflop playbook
> (`knowledge_base/postflop/openai_strategy.json`), weighted-range equity, LBR (`benchmark/lbr.py`), CRN, EV-gates
> (G5/G6) — but the emitted DSL IGNORED them (used crude range_top+equity), and the grammar even REJECTED advisor calls.
> The 5 genuine leaks: (1) range_top ignores spot.hero_pos, (2) range_tracker HU-only, (3) no 6-max preflop charts,
> (4) hardcoded SFT thresholds, (5) api.mdf dead. **#1 FIX SHIPPED ($0, local):** `api.solver_freq` wired into the DSL —
> `dsl_grammar._OP` += `is not`/`is` (the advisor None-guard), `policy.SYSTEM_PROMPT` exposes+prefers solver_freq +
> range_top + spot.street/read (2 grammar-valid examples), `from_selfplay` postflop checked-to emits solver_freq programs
> (21% of rows, 0 grammar-invalid, execute). Curriculum regenerating with it. Still build-NEW: 6-max position ranges,
> multiway range_tracker, opp-read conditioning.
> **★ SERVERLESS teacher PAUSED (2026-06-17).** Endpoint 168e2dt7qdptlh (Qwen3-32B-FP8) crash-looped: 48GB GPU OOM'd
> 32B-FP8 → bumped to HOPPER_141/AMPERE_80 via API → then all workers `unhealthy` (a worker-runtime crash, needs the
> worker log — user's was empty) + H200 throttle. Set workersMax=0 (stop the crash-bill). DECISION: don't be blocked by
> the flaky serverless teacher — build the 8B from RELIABLE assets (CPU solver gold `solver`+`solver_mass` ~10k examples
> + the advisor-wired self-play) → 8B SFT→GRPO on a POD (pod_setup fixed; pods have no serverless throttle). Serverless
> teacher = a later bonus once the worker crash is diagnosed. CPU mass-solve (`from_solver --mass`) running reliably.
> **★ SERVERLESS TEACHER PIVOT (2026-06-17) — escaped the pod-setup hell.** After 5 pod-setup failures (PEP668 on the
> Ubuntu-24.04 image, vLLM/torch ABI mismatch, transformers<4.57 tokenizer skew, missing hf_transfer), pivoted teacher-
> generation to **RunPod Serverless from GitHub** (`aeneassoft/PokerB` branch `serverless-worker`, `../infra/serverless/Dockerfile` on the
> OFFICIAL vLLM image = RunPod-managed/tested env). Endpoint **`168e2dt7qdptlh`** serves the teacher; `../infra/serverless/handler.py`
> (repo root) generates DSL + engine-gates (grammar+legality) + returns the gold; `research/teacher_serverless_client.py`
> (concurrent+reactive: K=4 jobs, inspect-after-4 quality gate, abort if gate_pass<50%) accumulates → `data/teacher_raw.jsonl`
> → `pipeline/distill_teacher.py` (EVFilter) → `dataset/shards/teacher.jsonl`. **GPU fix (via API, no rebuild):** the
> endpoint was on AMPERE_48 (48GB) → 32B-FP8 OOM'd at load (jobs stuck IN_QUEUE) → bumped to **HOPPER_141,AMPERE_80**
> (H200/A100-80G, fits 32B + the 80B-Next later). 2-NODE LIVE: serverless GPU teacher-gen ‖ local CPU TexasSolver
> mass-solve (`from_solver --mass`, `solver_mass.jsonl` now 4553 rows). Code changes done: concurrent client, gold_shards
> +solver_mass+teacher (.exists-guarded), `pipeline/inspect_teacher.py` quality instrument. The 8B SFT→GRPO POD path
> (`runpod_rl_campaign` train mode) ALSO has the env fixes (pod_setup_rl.sh) so it runs too. **NOW:** Phase-0 pilot (1500)
> cold-starting on the strong GPU = the first teacher-quality signal; GO → scale; FAIL → escalate MODEL_NAME to Qwen3-Next-80B-A3B-FP8.
> ⟳ LIVE source of truth. Per the CLAUDE.md standing rule, update THIS top section before ending any turn that moves
> the headline, lands a build, or shifts priorities. Plan: `.claude/plans/gut-dann-sind-wir-toasty-forest.md` ·
> `plans/QWEN_6MAX_PLAN.md` · `doctrine/DATASET_SPEC.md`.

**★ LOCAL SFT PROOF PASSED (2026-06-17) — the LLM emits valid REASONING-LOOP DSL (frac_bad 0.97 → 0.00, grounded_rate 1.00, 30/30 OK).** Qwen3-1.7B QLoRA local proof. The fix chain (all $0, grounded by measurement):
> 1. **completion-only masking** (`assistant_only_loss=True` + `packing=False`; TRL auto-swaps the `qwen3_training.jinja` `{% generation %}` template — verified the loss lands only on the program);
> 2. **curriculum data present + ordered** (`dataset/build/curriculum.py`; the old SFT had ZERO `decide()` rows);
> 3. **strip Qwen3's `<think>…</think>`** (incl. dangling) in `policy.extract_program` — left in, it broke the DSL grammar → frac_bad;
> 4. **THE DECISIVE FIX — decision completions are now REAL reasoning loops** (`dataset/build/from_selfplay.py`): `eq=api.equity(hole,range,board); req=api.required_equity(to_call,pot); if eq>=req+δ: decide('raise') elif eq>=req: decide('call') else: decide('fold')` — the action is DERIVED from engine computation. The OLD form computed `req` then HARDCODED `decide('fold')` (dead code → decoration → the comment register from the 47% no-`decide()` math/exploit shards dominated → frac_bad 0.97). User directive: *everything the LLM emits must drive the decision.*
> **Honest scope:** the FORM is perfect; decision QUALITY is baseline (ranges collapse to a default, fold-biased ~60%) = RL/realized-EV's job NEXT (SFT=form ✓, RL=quality). n=30 on the train league.
> **★ GRPO (RL loop) PROVEN on the fixed model (2026-06-17, $0 local, 10 steps):** `reward_std>0` (REAL EV signals — reward bounced 17.4/−13.8/28.0/−24.5/…, not the old all-`R_BAD`), `frac_bad≈0`, `engine_grounded_rate≈1`, completions stable ~120 tok, no collapse. = "integration + sanity proven" (NOT an EV-lift claim; 10 steps). **Held-out (rock/whale/shark, post-RL, greedy): frac_bad 0.13 / grounded 1.00** — the residual 13% is LEGALITY/conditioning (model sometimes applies the facing-bet template to a check spot → illegal action; executor legalizes to a safe fallback), NOT the old garbage. Fixed by the 8B + constrained decoding (STRUCTURED=1) + more/balanced data.
> **★ FIRST EXTERNAL REFERENCE (2026-06-17) — the LLM brain plays Slumbot end-to-end: −72.0 bb/100 (frac_bad 0.03, n=100).**
> `pokerbot/benchmark/slumbot_llm.py` (NEW: Slumbot/HU state → our `Spot` → `QwenPolicy` → DSL program → action). The
> SFT 1.7B brain DROVE a full external game vs near-GTO Slumbot: **frac_bad 0.03** (97% valid executed programs over 120
> decisions — the "brain in the driver's seat" PROVEN live) and a **stable −72.0 bb/100** (±~7; readings converged
> −85→−72). HONEST: a LOSING baseline as expected (1.7B, SFT-only/no-RL, HU not 6-max, simple eq-vs-pot-odds rule) — but
> *reasonable* losing, not spew (a garbage bot is −200+; the old fcpa net was −212). Notable: the old HU engine was also
> ~−72 vs GTOW, so the 1.7B LLM baseline ≈ that level. **This −72 is the grounded number to beat: RL (above the SFT
> ceiling) → 8B (capacity) → the 6-max focus.** Local 12GB note: ≤4B QLoRA fits comfortably; 8B/9B QLoRA is at the
> 12GB edge → the ≥8B training belongs on the pod. Qwen base reconfirmed = Qwen3-8B (3.5/3.6 are multimodal+thinking,
> no 8B-dense; 3.7-Max is closed) — stay.
> **★ REPRESENTATION v2 (2026-06-17) — frontier consult (Claude Opus 4.8 + gpt-5.x, independent) REFRAMED the bottleneck:**
> the −72 is NOT an RL/data problem — the pure / point-equity-vs-fixed-range / single-size policy CLASS *cannot express
> GTO* (which is MIXED + range-vs-range). Both also said: the EV-truth filter must reject on EXPLOITABILITY (multi-
> opponent), not point-EV; build a best-responder as the PRIMARY metric (Slumbot bb/100 kept as the presentable
> headline per the user); train vs an ADAPTIVE nemesis (vs FIXED opponents RL collapses any mix to a pure max-exploit —
> mixing only emerges vs adaptation). User insight (sharp): 6-max has MULTIPLE equilibria → "which GTO is at the table"
> is unknowable → the policy must be a FUNCTION of the opponent READ (robust baseline + bounded adaptation), not one
> fixed strategy. DONE so far: **mixed strategies** — `decide_mix({'raise':.7,'call':.3}, size=)` DSL primitive (both
> gates + executor seeded-sampling), `from_selfplay` emits load-bearing MIXED reasoning loops (eq picks the branch →
> each branch a distribution), SFT verified end-to-end (**frac_bad 0.07 held-out, grounded 1.00, model emits valid
> mixes**). NEXT: (C) opponent-READ conditioning (scalar `spot.villain_fold/aggro` the program conditions on = "which
> GTO at this table"); (D) adaptive best-responder + exploitability as the primary metric; (2b) RL mix-EV (sample-per-
> rollout, higher variance — the user's pick). All local/$0 first; RL/8B on the corrected representation.
> **★ Piece C (read-conditioning) — CONCLUDED locally: data+architecture verified; STABLE emission is an 8B-capacity matter.**
> `Spot.villain_fold/aggro` (rendered when non-neutral) + `from_selfplay` emits the read-conditioned MIXED program with a
> bounded-exploit branch (`elif spot.villain_fold>=0.6: decide_mix({'raise':.55,'fold':.45})`); the compact-range fix
> (`api.range_top(frac)`) shipped (the literal list overflowed FAST=160). **A/B ladder on the 1.7B (all measured, $0):**
> compact ranges made the read-branch FIT the budget (emit 0→9/30) but ok dropped (truncation edge); **then +data-volume
> (1500→5000 gen spots) recovered API fidelity (ok 8→25/31, frac_bad ~60%→19%) BUT the model dropped the rare read-branch
> (9→0/31)** — sample programs CONFIRM it: clean reasoning-loop + valid `decide_mix`, but it collapses 4→3 branches and
> sometimes swaps `api.range_top`→a literal list. = a definitive **1.7B fidelity ceiling** (holds the API names OR the
> subtle conditional, not both). Hypotheses competed + settled by measurement: epochs ruled out (train loss≈0.004, tok-acc
> 0.999 = already overfit), data-volume helps generalization not the rare branch. **The read-conditioning's validator is
> the 8B (capacity); the 1.7B proved the PIPELINE, as planned.** Not grinding the proxy further.
> **★ FULL-GPU-LOAD prepped for the pod (2026-06-17) — the reward parallelized (the real GRPO bottleneck).** The CPU
> reward (`GEN_BATCH×K_ROLL` self-play rollouts/step) starved the GPU; now fanned across a persistent spawn ProcessPool
> (`REWARD_WORKERS`, qwen_grpo). **Measured ~5× at 8 workers (24 vCPU), byte-identical to sequential.** This surfaced +
> fixed two real reward bugs: (1) the hero continuation wasn't CRN (unseeded RNG + per-hand state leaked across rollouts)
> → reset+seeded per rollout (`rl_env._reset_cont`); (2) **`PYTHONHASHSEED`** — card-string set iteration was
> per-process → workers would have sampled different runouts → **CRN broken within a GRPO group**; pinned via `main()`
> re-exec. The whole RL/eval pipeline is now reproducible. Campaign `SCALE=1` wires it + vRAM-fill `VLLM_MEM=0.78` +
> big `GEN_BATCH` + `nproc` auto-detect + a live `nvidia-smi` load logger (`data/gpu_load.jsonl`). **Size-agnostic** (BASE
> 8B/32B/70B, QLoRA nf4 + all-linear). Design: `plans/full_gpu_load.md`.
> **★ Pillar 2 — SOLVER GTO DATA shard BUILT (`dataset/build/from_solver.py` → `dataset/shards/solver.jsonl`).** TexasSolver
> (OSS, CPU, $0) solves 8 representative flops → exact GTO **mixed multi-size frequencies** → `decide_mix({solver mix},
> size=)` programs (engine-grounded; the mix is ground truth, varies by spot = learnable). **2617 examples, 88% genuinely
> MIXED (≥2 actions), 1294 bet / 1323 check** — all grammar-valid + executable. Gotcha fixed: TexasSolver rejects the
> `22+`/`A2s+` shorthand ("format not recognize") → ranges ENUMERATED. Real GTO warm-start gold (CLAUDE.md boundary),
> size-agnostic, ships in the tarball; the pod SFT now trains on it (the campaign's DSL path was corrected off the old
> `local_kb.jsonl`). CPU mass-solve = the PC-hub job (the pod has no solver binary) per the 2-node split.
> **★ Slumbot re-test (2026-06-17, IN PROGRESS):** the data-volume 1.7B regressed on HU transfer (frac_bad 0.48, ~29s/hand
> — it overfit 6-max self-play + reverts to literal ranges incl. invalid `'AS'`). The clean −72/frac_bad-0.03 checkpoint
> was overwritten by the data-volume run. Now testing the COMBINED model (selfplay+read+SOLVER). KEY: the local test uses
> NO constrained decoding; the POD's `STRUCTURED=1` (vllm_structured_outputs_regex) forces valid DSL → pod frac_bad→0 by
> construction, so the local frac_bad massively overstates the pod's. The −72 remains the number to beat (RL→8B).
> **★ RunPod final prep (2026-06-17): `plans/RUNPOD_READY.md`** — launch cmds (smoke/scale/70B), the GATE ladder, the
> corrected data path, the full-load levers, the pre-flight, `--kill` discipline.
> **★ TEACHER→DISTILL run LAUNCHED (2026-06-17) — the user's "deep research with the biggest model" plan.** The 235B is a
> TEACHER (not deployed): Qwen3-235B-A22B generates engine-gated DSL over thousands of spots → distil into the 8B (the
> CLAUDE.md frontier-distillation loop, but the frontier is OUR 235B on the pod, EV-gated on the PC). NEW: `research/
> teacher_generate.py` (vLLM batched gen + grammar/executes gate, chunked + wall-clock + incremental save — tested
> locally), `pipeline/distill_teacher.py` (EVFilter G1-G4 → `dataset/shards/teacher.jsonl`, auto-added to the 8B SFT),
> campaign MODE=teacher + GPU/GPU_COUNT/TP knobs. **B300 FINDING: not API-launchable** — listed in the `--gpus` catalog
> (288GB) but NOT in the REST `POST /pods` gpuTypeIds enum (400 error; self-kill → no cost). No single available GPU fits
> 235B-fp8 (~235GB: B200=180, H200=141, MI300X=192). → running **2× H200 tensor-parallel (282GB, $8.78/hr, Hopper =
> mature, no Blackwell cu128 fragility)**, 235B fp8 (verified exists) with a **32B fallback** if it won't load (so the run
> always yields teacher data). Blackwell hardening shipped anyway (is_blackwell B200/B300, latest-vLLM-not-torch-swap,
> bf16-matmul canary in setup+preflight) for when B300 opens up. Pod self-killing, ~100-min cap.
> **NEXT = the real training: Qwen3-8B pod scale (SFT→GRPO).** Gated on a user go (RunPod $). The polish attempt (widen
> ranges to cut the ~60% fold) BACKFIRED — long literal ranges overflowed the gen token budget → truncation → frac_bad
> 0.13→0.43; REVERTED (the fold is correct pot-odds; decision quality = RL's job, not hand-tuned priors). b/d
> (grounding/exploit) curriculum phases → gated frontier-distillation (not fragile templates), the principled next step.
> **Process lessons:** a custom `SequentialSampler` Trainer subclass HUNG training → use the built-in `train_sampling_strategy='sequential'`; `packing=False` + batch 8 near-OOM'd the 12 GB card → batch 4; decisions-only curriculum by default (math/exploit shards re-added later as decision-SHAPED reasoning, not comment-only).

**North star (→ CLAUDE.md): PLAY GTO / ACHIEVE TRUE GTO in 6-max** (= the robust correlated equilibrium; Einy et al.
2022). The goal pivoted FROM the HU exploit-primary engine (now BACKGROUND; all the HU/solver/−72/solver-grafted-
preflop content below is HISTORY) TO a fine-tuned **Qwen3-8B** that DRIVES our engine via **program-of-thought**,
trained on a self-growing EV-gated dataset + **RL/self-play** (the only lift above the imitation ceiling).
**Two nodes:** the PC hub (the dataset + gated frontier-distillation + CPU mass-solve + training monitor) ↔ RunPod
(SFT→GRPO; reward = `table.py` self-play EV + the `sixmax` league; GTO-anchored eval = PokerBench-acc + bb/100 +
LBR-exploitability + robustness-spread).

**★ Phase 0 DONE + verified (2026-06-17):** repo reorganized (`extraction`→`research/`; qwen→`training/`; runpod+pod→
`infra/`; NEW `pokerbot/brain/` + `dataset/` + `pipeline/`; the 6 books→`books/poker/`; 57 historical docs→
`docs/archive/`); all code imports fixed; **core tests green** (test_bot/game/table/range_tracker) + research/infra/web
import-smokes pass; `config.INFORMATION_DIR`→books/poker. CLAUDE.md fundamentally re-oriented; INDEX.md = the live
tree.
**★ Phases 1–2 DONE + verified (2026-06-17):** Phase 1 = the DSL foundation `pokerbot/brain/{api,format_spot,executor}.py`
(program-of-thought "common language": engine-as-API + PokerBench-aligned spot serializer + execution sandbox) —
round-trips a live `table.py` spot → api → legal action (verified). Phase 2 = the dataset builder `dataset/` (schema +
relevance/dedup gate + converters from math/exploit/**PokerBench 6-max spine**) — 253 sample examples, all valid.
**★ Anti-hallucination hardening (2026-06-17, the "run on our own language" directive):** `pokerbot/brain/grammar.py`
— a DSL GRAMMAR gate (AST whitelist; calls/attrs only on api/spot/safe-builtins; must `decide()`), wired into
`executor.run_program(strict=True)`. Proven: 3/3 valid DSL execute, 10/10 foreign/malicious (import/`__import__`/open/
lambda/while/def/dunder/getattr) STRUCTURALLY rejected — never executed. The executable surface IS our language.
NEXT hardening = constrained DECODING (vLLM guided/GBNF) at inference + GRPO sampling (invalid tokens unsamplable) +
deterministic (temp-0) inference. Distinction held: hallucination→structural 0; strategy-noise→bounded = the GTO floor.
**★ Phase 3 DONE + verified (2026-06-17):** the PC-hub `pipeline/` — `filter.py` (the deterministic EV-TRUTH gate;
7 gates proven: schema/relevance/decontam/dedup + legality + EV-sanity — rejects a call-blunder `eq 0.23 ≪ 0.60`,
free-fold, illegal moves), `frontier_loop.py` (gated active-distillation; offline plumbing + a REAL Claude call
proven), `monitor.py` (weak-cluster active-learning: cluster_of/weak_clusters), `orchestrate.py` (lean 3.3 MB scp
bundle). *Frontier = prior, ENGINE = truth.* Also: PokerBench-test decontamination wired (10,998 keys, gate proven).
**★ Phase 4 $0-GROUNDWORK DONE + verified (2026-06-17):** `training/rl_env.py` (the 6-max RL REWARD ENV wrapping
`table.py` + the `sixmax` league — **zero-sum verified**: chips conserved every hand) + the **rollout-EV machinery**
(clone/reseed/play-out — reseed proven by 12/12 distinct showdown run-outs; fold-EV==0; snapshot never mutated) +
`gen_decision_states`; `training/qwen_sft.py` extended for the **DSL format** (mix our gold shards, inference-identical;
data path verified); `training/pilot.py` (the **GATE-2 core**: CRN-paired + fresh-seed-holdout candidate ranking).
**★ DE-RISK PILOT: PASS (2026-06-17, $0/local).** The realized-EV reward signal is REAL + SIGNIFICANT. Fair pilot
(CRN-paired + fresh-seed holdout + SEM), oracle vs baselines: **n=50** → vs random +4.62±1.92 (sig), tag +2.06±1.63
(not yet); **n=200** → vs random **+11.03±3.31**, maniac **+5.21±1.77**, **tag +5.62±1.81 — ALL significant (>2·SEM)**.
The tag-lift GREW with scale (+2.06→+5.62), confirming signal not noise; the smoke negative (n=6: −1.67) was pure
noise. **The #1 pre-spend risk (does rollout-EV move the needle?) is RETIRED.** Caveat: the oracle has rollout
FORESIGHT (it's the ceiling a learned policy approximates), uses a tag continuation + the training league — not yet a
held-out league. This proves the reward carries learnable signal, NOT that Qwen captures it (that's the pod test).
**★ PRE-RUNPOD BUILD DONE + verified (2026-06-17, $0/local; plan = `.claude/plans/gut-dann…`).** All 6 pieces built +
$0-verified: `brain/dsl_grammar.py` (constrained-decoding regex; 7/7 DSL forms accept, 8/8 foreign reject, 40/40 real
completions, AST-subset) · `brain/policy.py` (Qwen→spot→program→action bridge; build_messages/parse_completion/hard-neg
fallback verified) · `rl_env` HELD-OUT league split (rock/whale/shark, disjoint from train) · `training/qwen_grpo.py`
(DAPO trainer: verified GRPOConfig loss_type=dapo/ε_high=0.28/β=0/scale_rewards=False + vllm_structured_outputs_regex,
state-buffer dynamic-sampling pre-filter, CRN ev_reward) · `training/qwen_eval_gto.py` (held-out bb/100 + per-type
robustness-spread + GATE ladder G0–G5) · `infra/pod_setup_rl.sh` + `infra/runpod_rl_campaign.py` (self-killing smoke→
scale orchestrator). **Stage-0 dry-run PASS** (state buffer + CRN dataset + reward: good=clipped-EV, bad=R_BAD). Full
DSL gold `dataset/shards/local_kb.jsonl` (11.5k math+exploit) built. DAPO + the RL book digested.
**★ HELD-OUT ROBUSTNESS: PASS (2026-06-17).** Pilot on the untrained league (rock/whale/shark), n=50: oracle beats
random **+3.93±1.56**, maniac **+3.27±1.46**, tag **+3.52±1.39** — ALL significant. The EV signal GENERALIZES to
untrained opponent types (cross-distribution robustness) → the pilot's train-league caveat is CLOSED. The $0 pre-spend
gate is GREEN (Stage-0 + train-league n=200 + held-out all PASS); only Stage-1 (TRL integration) remains, and it needs
`trl` = pod/venv.
**★ MATH ACCURACY (2026-06-17, user-prioritized).** Strategy `plans/math_accuracy_strategy.md` (4 papers + repos:
Athena tool-use VALIDATES engine-as-truth; fse16 → exact-rational threshold math; MathGLM → number-sense training;
LEMA → mistake-correction pairs; adopt **sympy** selectively (verify+thresholds, not the hot loop), reject numbat/
Qalculate). DELIVERED: GPT-5.5 generated **34 post-flop calculations** → ALL 34 ENGINE-VERIFIED (`postflop_calc_gate`,
verify_expr==verify_value) → materialized `knowledge_base/math/postflop_formulas.py` (34/34 together) → exposed as
`api.<fn>` (brain callable in DSL; grammar+executor confirmed).
**★ MATH INTEGRATED INTO THE ARCHITECTURE + LOOP (2026-06-17):** (1) **Multi-MODE framework** `pokerbot/brain/modes.py`
— the accuracy↔time trade-off made explicit: FAST ~1.5s / STANDARD ~5s (live target) / DEEP 180s (R&D, exact+sympy+
trace) / TRAIN (RL throughput). Every knob (MC iters, rollout-k, gen tokens, wall-clock, exact/sympy/analysis) is
mode-set; wired into `api.equity`, `rl_env.rollout_action_ev`, `policy.QwenPolicy` (verified: levers switch with mode).
(2) **2nd GPT-5.5 batch — 32 STRATEGY formulas** (books + validated public strategy → math: preflop sizing/ranges,
range balance, c-bet/barrel, bluff/defense, stack-depth, exploit-deviation, position) → ALL 32 engine-verified →
`strategy_formulas.py` → `api.<fn>`. **Total 66 engine-verified formulas callable by the brain** (34 post-flop + 32
strategy; integration verified 66/66 via api). (3) **`pipeline/math_loop.py:grow_math`** — the OpenAI math pipeline as
a loop primitive (consult→gate→merge→re-materialize), PC-hub ONLY (pod never calls a frontier API). Remaining math
layers: exact-Fraction pass · sympy symbolic tests · mistake-correction · DSL converter for the 66 (training).
**NEXT (the pod spend, gated):** `python -m infra.runpod_rl_campaign` (H100/H200 smoke→scale) = the REAL GATE 2 — the
first pod run IS the TRL-integration test (keep the smoke tiny). Optional pre-step: `dataset.build.run --full --pb 60000`
(PokerBench-DSL augment, decide()-fluent SFT). ALWAYS `runpod_run --status` after = no tracked pods.

---
> **HISTORY below (the HU exploit-primary era — superseded by the pivot; kept for context, not the current goal).**

**★ SOLVER-GRAFTED PREFLOP (2026-06-16, user-chosen "faster+more ingenious" lever) — built + first GATE PASS.** Preflop is
87% of the −72; the blueprint's see-flop leaf was a pure-equity CHECKDOWN (`w = e + κ·4e(1−e)`, κ=0.05 GUESS) that omits
ALL postflop betting. We ground it in real TexasSolver play: `extraction/preflop_ranges.py` (reach-weighted ranges per
see-flop node) → `extraction/preflop_calibrate.py` (200bb flop solves + an MC rollout of the solved strategies →
measured realization `w_node`) → `extraction/preflop_leaves.py` (re-level κ PER NODE to match the measured w_node;
default = byte-identical checkdown) → `preflop_solve.py --leaf-table` re-solves → `preflop_blueprint_solvergraft.json`.
The **NON-CIRCULAR independent-leaf exploitability** (`preflop_exploit.py --leaf-table`, o3's recommended metric):
- **in-model checkdown expl = 3.31** (the CIRCULAR number) BUT **independent-leaf expl of the SAME blueprint = 6.12**
  → the checkdown UNDER-stated the real gap ~2× (o3's "equilibrium of the wrong game", confirmed).
- **re-solved-for-grafted-leaves expl = 2.03** → **GATE PASS (−4.09)**: grafting + re-solving genuinely lowers the
  non-circular preflop exploitability. **κ_OPEN ≈ 0** (vs the 0.05 guess) → the blueprint OVER-credited see-flop
  realization; decision-boundary sane (BB defends opens slightly WIDER, correct since the opener realizes less).
- **HONEST caveats:** (a) lean 1-size solve tree likely UNDER-realizes → κ_OPEN≈0 is a lower bound (rich-tree
  robustness check running: `data/calib_open_rich.log`); (b) only OPEN grafted so far (others = checkdown κ=0.05);
  (c) independent-leaf expl is a non-circular LOCAL proxy (simplified preflop game + solver leaves), NOT the GTOW
  bb/100 — the GTOW AIVAT A/B (server-blocked) remains the −30 arbiter. NEXT: rich-tree + all-node calibration →
  wire the grafted blueprint behind an env toggle → GTOW A/B.

**The path (user-approved single pass, a measured gate per step):** −72 bb/100 vs GTOW is 87% PREFLOP (`gtow_xray.py`).
Close it: **(1) near-Nash preflop blueprint** [DONE, wired] → **(2) a SHARP turn/river TexasSolver resolver via the
range-tracker keystone** [DONE on the $0 local gates, below] → **(3) a CFV value net for flop depth-limited resolving
(DeepStack)** [NEXT — the committed neural net]. Honest ceiling: −53 → −15..−25 (sharp resolver) → −5..−15 (flop net);
a true 0-tie is the frontier (o3: exact Nash → 0). **GTOW server is RESTING (503-storm)** → the $0 local grounded gates
are the go-signal; the GTOW AIVAT headline fires in ONE command (the harness already runs resolver+blueprint ON) once
it recovers.

**Headline (2026-06-16, late session) — three grounded findings + a strategic re-order:**
1. **CFV-net PILOT validated the pipeline + architecture, but it's DATA-LIMITED.** `cfv_data.py` (new `k_rivers=12`
   knob) → 123 local samples → `train_cfv_net.py` (new target-normalization fix): the 392→338 MLP fits the train set
   to ~0 (architecture + features SOUND) but held-out MAE = **96% of scale** (99 samples ≈ 1000× too few). End-to-end
   pipeline PROVEN; the sole blocker is DATA VOLUME. (Root-caused the earlier ZERO-samples pod runs: `turn_boundary_cfv`
   is atomic = 48 river solves/sample, none finished in a short pod window → fixed via `k_rivers` + local gen.)
2. **★ CORRECTNESS finding (o3 + gpt-5.5, VETTED — `docs/consults/nextrun_*`):** the current target (solve 48 rivers
   SEPARATELY at the turn pot + average) computes "river EV after a forced turn CHECK-CHECK" — it **OMITS turn betting**
   (Δ up to 10-20 bb on coordinated turns; turn-bet-fold nodes invisible) and isn't a consistent joint strategy. The
   CORRECT + ~10-40× CHEAPER target = **ONE `dump_rounds=2` turn+river solve + a single backward-induction pass**.
   Accel tricks queued (NEXT_RUN_TODO / VALUE_NET_PLAN): board suit-canonicalization (~8× fewer solves), vectorized
   showdown-matrix extraction (~100× faster, kills the GIL loop), DeepStack river-net bootstrapping.
3. **★ STRATEGIC RE-ORDER — do the $0 range-tracker keystone BEFORE the CFV net.** Both frontier consults (matching the
   quadruple-triangulation + the plan) agree: the net realistically recovers only **~4-8 bb/100** (postflop-non-jam was
   the SMALLEST X-ray term, ~−10) AND needs correct line-narrowed ranges first — to make the EXISTING resolver sharp
   AND to sample the right CFV states. So the **EXACT combo-level range tracker** (today's is class-level / preflop-line-
   only) is the higher-ROI next step. gpt-5.5 also flagged a 169-class **suit-aliasing** risk (can't tell KhQh from KsQs
   on heart boards) → an aliasing test must GATE any big net run.

**Benchmarks (this session):** GTOW still server-blocked (503-storm; definitive AIVAT awaits recovery; retry
`tools/gtow_measure_chunked.py`). **Slumbot whole-bot (exploit-primary, n=2500): −39.6 ±30.9** = statistically ≈ the
FLOOR (−43); the historical **+31 did NOT reproduce**, and the opp-model log hints the exploit overlay under-built
(a separate Exploit-engine thread — flagged, not yet investigated). Local signals unchanged: preflop exploitability
**3.3 vs 234**, A3 range-L1 **+60% turn**. RunPod: **0 pods live** (verified, no billing).
*(History pointer: the earlier Slumbot "floor-bridge to GTOW ≈ −22" idea is superseded by this direct whole-bot run.)*

**★ (2) SHARP RESOLVER — the range-tracker KEYSTONE — DONE on the $0 local gates (2026-06-16):** the resolver
(`resolver.py` turn+river, wired) was measured NEUTRAL only because it was fed too-WIDE ranges (`range_tracker._p_call`
was FLOP-ONLY → turn/river calls fell to legality-only). Fixed in one pass:
- Turn data: `mass_solve.py STREET=4` → 5919 turn boards; `build_defense_data.py` (turn cap 2500) → **2.45M defense
  rows (flop+turn+river)** in `defense_data.jsonl`.
- **GATE A2** — retrained `defense_advisor.pt` (now multi-street): held-out-by-board, the MLP beats strength-only by
  **flop +63% / turn +46% / river +18%** (gate was >+3%). PASS.
- **The keystone widen:** `range_tracker._p_call` now reweights on ALL streets (was `street != "flop"`).
- **GATE A3** (`check_range_l1.py`, the o3-bound metric, Solver = truth, held-out): the advisor P(call) update HALVES
  the range-L1 error vs do-nothing — **flop +59% / turn +60% / river +47%**; turn-L1 0.409 reaches flop's 0.399. Since
  extra-exploitability ≤ (pot/2)·L1, this is a GROUNDED proof the ranges are now sharp (the fix for the "−72 neutral
  resolver"). PASS.
- **End-to-end smoke (verified):** on a turn bet-call line the widen narrows OOP's range 658→302 eff. combos toward K-x
  second pair (the true calling range) + raises confidence 0.833→1.0 (the call is now MODELED not silent → fewer floors).
- Deferred (GTOW resting / slow): the paired live-solve eval (step 6) + the GTOW AIVAT headline (step 7); `_p_call`
  size-threading is a MEASURED refinement only if A3-river (0.525, the loosest) demands it (logged in NOTES).

**★ KEYSTONE — SECOND HALF (the FLOOR) now WIRED + grounded (2026-06-16).** The resolver got the tracker above; the
FLOOR — which plays the MAJORITY of hands (all flop decisions + every spot the resolver gates out) — still built the
villain range with `_villain_range`+`_narrow` = "keep top-X%-by-board-strength", which DROPS every bluff/draw → it fed
`equity_vs_range` an artificially-strong range → systematic OVER-FOLDING facing bets (CLAUDE.md's "poisons the floor's
facing-bet/bluffcatch math"; the postflop twin of the preflop over-fold the blueprint fixed).
- **GATE A3-FLOOR** (`extraction/check_floor_range.py`, held-out by board, Solver=truth, $0): `_narrow`'s range is L1
  **0.756 vs solver truth ≈ uniform-random 0.995** (near-worthless!); the action-consistent tracker is **0.437 = +42%
  closer to truth** (flop +51% / turn +44% / river +30%). By the o3 bound (exploitability ≤ (pot/2)·L1) this ~HALVES
  the villain-range leak in the floor's facing-bet math. PASS.
- **Wired** in `bot.py` (`use_range_tracker`, `_tracked_villain_range` + new `equity.equity_vs_weighted_range`);
  `_narrow` kept as the `<CONF_THRESHOLD` fallback (o3-safe). Tests green (incl. a stale `test_range_tracker` fixed —
  calls are now MODELED post-widen). Smoke: AsKd on a checked-through board reads 0.300 eq under `_narrow` (→ thin-value
  spew) vs the correct **0.129** under the tracker (→ give-up) = the spew-reduction mechanism, concrete.
- **EV A/B** (`pokerbot/benchmark/range_tracker_ab.py`, duplicate, n=250): head-to-head ON>OFF **+50.5 ±40.7** (~1.2σ,
  fixes the over-fold leak); vs GTOBaseline paired **−31.4 ±58** (within noise, NO significant regression). Honest:
  grounded range-L1 is the TRUSTED gate (strong PASS); the bb/100 vs the analytic GTOBaseline is the noisy
  regression-catcher (and GTOBaseline isn't a solver → a solver-grounded range model is benignly mismatched to it).
  **DECISION: KEEP ON.** DEFINITIVE EV decider = the GTOW AIVAT A/B (`POKERB_RANGE_TRACKER=1` vs `0`, wired into
  `gtowizard.py`) when the server recovers. Still-open keystone bit: the RESOLVER emit is 169-CLASS (suit-aliasing) —
  the floor path uses per-combo weights directly (no aliasing), so this affects only the resolver (gpt-5.5's aliasing
  test is the gate; deferred — NOTES).

**(3) FLOP GTO — ARCHITECTURE RE-OPENED by the Gate-0c diagnosis (2026-06-16).** Gate-0c (the Leduc value-net
re-solve) was fully diagnosed (causal chain traced, Fable-5): the round-0-ONLY re-solve converges to a spurious
non-bluffing corner (170 vs exact-eq 22 mbb/hand) — REFUTED as a code bug (keys/conventions correct) AND as simple
adaptivity (a frozen value fn is WORSE, 840). Root cause = collapsing ALL of round 1 into a value fn removes the
round-1 co-evolution → a known depth-limited-solving spurious equilibrium (fix = Brown-Sandholm multi-valued states /
CFR-D gadget). **★ KEY:** this round-0-only test is STRICTLY MORE DEGENERATE than the real HUNL plan (flop-resolve
solves flop+turn EXPLICITLY, net only at the turn→river leaf) — Leduc can't even validate that deeper construction.
The value-net CORE is PROVEN (0a exact + 0b net 6.4%). So the flop choice is re-opened: **(A) the committed CFV-net
path** (RunPod ~$112, needs the gadget for soundness) vs **(B) a SOLVER-to-terminal flop→turn→river live re-solve**
(no net, no RunPod, a deeper clone of the SHIPPED+validated turn/river resolver — the plan's "Risk 5", robust default,
sidesteps gate-0c). **DECISION (user, 2026-06-16): the NEURAL NET is the postflop path** — exhaustive live-solving
of the flop is "supercomputer territory" (too many continuations to compute live); a net is amortized offline → fast
inference. So Phase B (CFV value net) is RE-COMMITTED with the **gate-0c-robust architecture: solve flop+turn
EXPLICITLY (CFR), query the net ONLY at the turn→river LEAF** (never round-0-only — that degenerate construction is
what failed). Self-play boundary stays HARD: labels from OUR solver, NEVER the LLM (the LLM = design/validation; that
imitation IS the −72 ceiling). Next $0 build = `extraction/cfv_eval.py` — extract per-combo
RIVER-subgame CFVs (the net's target at the turn→river leaf) via a backward EV pass over a solved RIVER subgame, then
GATE B1 (zero-sum / range-EV / determinism) BEFORE any RunPod spend. **DONE 2026-06-16 — `extraction/cfv_eval.py`
GATE B1 PASS:** zero-sum exact (Σcfv0+Σcfv1=0), deterministic, nut-sanity correct (full-houses/flushes top, busted
broadways bottom), OOP range-EV +0.23 chips. The CFV extractor (per-matchup backward pass over the river betting tree,
implicit terminals, contrib-tracked zero-sum) is validated → safe to scale. **STEP 9 CODE COMPLETE + validated $0
(2026-06-16) — `extraction/cfv_data.py`:** per turn board, solve all 48 river run-outs → per-combo mean = the
turn-boundary CFV label (E over the river card; n=46 constant across combos → zero-sum PRESERVED, proven + measured)
+ a diverse-range sampler (`sample_range`, valid weighted class strings). Pipeline test PASS (zero-sum 0.0000, 48/48
solves, nut-sane: quads/full-houses top, busted broadways bottom). The ONLY remaining net-data piece = the RunPod
data-gen RUN at scale (pure $-spend: ~48 river solves/sample × diverse ranges → `cfv_dataset.jsonl` via
`cfv_data.py --gen N`; $5 pilot first, user's go, always `--kill`).
**★ DATA-GEN PIPELINE — FULL-LOAD VALIDATED (2026-06-16):** `extraction/cfv_pod_campaign.py N_pods N_per 32 wall WORKERS THREADS`
= a SELF-KILLING multi-pod orchestrator (provision → `pod_setup.sh` [python-zipfile TexasSolver-Linux + pip treys] →
saturated `cfv_data --gen` → pull+merge → `finally`+`atexit` kill ALL pods). **PROVEN repeatedly: pods ALWAYS die, no
orphan** (TaskStop alone does NOT trigger finally → ALWAYS follow with `python -m extraction.runpod_run --kill`; verify
`--status` = "no tracked pods"). Setup-bug fixes banked: local-OOM co-run, unzip→python-zipfile, treys→pip, scp-slow→
1.1MB tarball, ssh-key→forward-slashes, setup-timeout→600s+per-pod-catch. **FULL-LOAD fix: the gen MUST use a
PROCESS pool (`gen()` ProcessPoolExecutor) — the cfv_eval extraction is GIL-bound, a ThreadPool capped at ~22% (load
7/32); `workers=32 threads=1` → 32 solvers = full saturation** (cpu5c "32 vCPU" delivers ~18-22 effective, load
climbs there; pods have 124GB RAM, ample). Last good run: `4 300 32 28 32 1` (3/4 pods, 1 setup-timeout skipped).
TWO known inefficiencies to fix for the BIG run: (a) the setup `ex.map` BARRIER lets fast pods idle ~10min waiting for
a slow/timing-out pod → start each pod's gen as soon as IT is ready; (b) ~1/4 pods hit a setup-timeout (RunPod slow
networking) → over-provision + per-pod-catch handles it. **★ Step-10 TRAINER BUILT + smoke-tested:**
`extraction/train_cfv_net.py` (CFVNetHUNL: board[52]+OOP[169]+IP[169]+pot → per-class cfv0[169]+cfv1[169], masked MSE,
GATE B2 = held-out MAE <8%). Runs end-to-end; needs the BIG dataset to actually learn (2-sample smoke → 100% MAE, expected).
**NEXT to a MEASURED win:** big dataset run (now full-load works) → `train_cfv_net` (GATE B2) → wire `resolver.flop_resolve`
with the net at the turn→river leaf (step 11) → measure vs Slumbot/GTOW.
  **DATA SOURCE = the existing `_gto_river_cache`
(STREET=5, river = last round → NOT truncated).** VERIFIED (Fable-5): a dump_rounds=2 TURN solve truncates at the
river chance-node (`childrens: []`) → it does NOT contain river betting, so the turn-subgame value can't be extracted
that way — which independently CONFIRMS the net-at-river-leaf choice (the river value IS cleanly solvable; the turn
value is not). The aborted `_gto_turnriver_cache` pilot is unusable; deleted. **GTOW measurement is BLOCKED** (our API-key's 20-hand cap is saturated with hands stuck
on "GTOW's turn"; the key IS the identity, no abandon endpoint → needs a server-side timeout (hours) or a fresh
user-generated key). Retry `tools/gtow_measure_chunked.py` (now 409-graceful) when the cap frees.

**The X-ray (`extraction/gtow_xray.py`, zero new compute) localizes the −72: 87% is PREFLOP** — preflop strategy −50,
deep-stack all-in spew −15, postflop non-jam only ~−10 (the SMALLEST term — the neural-postflop pivot aimed at it).
Our HU preflop is a crude strength-model (open top-X% at a fixed 2.5bb, no mixing/limps, `deep_jam_pct=0.985`) = the
"too standard dumb" the user flagged. (MIT 15.S50 L4 + Modern Poker Theory agree: preflop is where most value leaks +
it is near-Nash-solvable.)

**THE #1 BUILD (IN PROGRESS): a near-Nash PREFLOP BLUEPRINT.** `extraction/preflop_solve.py` — EXACT CFR+ over a real
size menu (limp / 2.5 open / 3bet-10 / 4bet-24 / 5bet-60 / jam) with a precomputed 169×169 all-in equity matrix + a
zero-sum IP-realization premium κ=0.05 on see-flop leaves (the chance-sampled v1 left deep nodes as NOISE — 72o
called jams; exact CFR fixed it; κ fixed the OOP over-defense 72o call 0.38→fold 0.98). Loader
`strategy/preflop_blueprint.py` is **WIRED into `bot.py:_preflop`** (depth-gated ≥140bb; `use_blueprint` /
`POKERB_BLUEPRINT` env). **VERIFIED (unit, Fable-5):** node-mapping for all 9 nodes; all-in discipline solver-grounded
(QQ/AKo **fold** 200bb jams @0.96, AA/KK call); a **value-only jam clamp** guards the checkdown's blocker-blind 200bb
jam-bluffs (76s never jams = no spew); a **robust facing-shove detection** (a caught bug: the adapter hides an all-in
stack → a 200bb jam mis-mapped 5BET←JAMSB → QQ CALLED it = spew); `tests.test_*` green. **The GTOW AIVAT A/B
(`use_blueprint` ON vs OFF, n≥2500) is DEFERRED — GTOW server resting (see the CURRENT lead); the directional −53
(n=200) stands.** o3 theorem: exact Nash → ceiling vs GTOW is ~0 (≥0, not above; symmetric 2p0s) — the realistic win
is closing −72 toward break-even.

**Local-vs-cloud (MEASURED, per the user's ask): LOCAL wins for the blueprint** — eq matrix ~3min + CFR+ ~3.5min =
~6min local, single-thread, cached; GCP setup alone is ~15min and a single CFR loop doesn't exploit many vCPUs. GCP
(quotas raised, ready) is held for the HIGH-QUALITY version — a real postflop continuation per leaf = orders-of-
magnitude more compute, embarrassingly parallel — gated behind this cheap proof.

**Bug hunt (2026-06-16, user hypothesis "maybe losses are just bugs"):** an Opus agent + manual review of the
decision/adapter path. FIXED: (1) `gtow_to_state` coerced an all-in stack 0→start (`... or start`) → corrupted
`all_in`/`committed_total`/`_eff_stack` in EVERY all-in spot of the benchmark (now a legit 0 stays 0); (2) `raise_max`
fallback used `hero_stack` not `hero_stack+committed_street` (undersized all-in when GTOW omits `raise_range`). The
agent's "BUG 1" (uncapped `to_call` overstates `req`) is REAL math but CANNOT fire in equal-stack HU (`to_call ≤
hero_remaining` always — prior streets are matched) → 0 impact, verified. **Net: the decision math is mostly SOUND →
the −72 is STRATEGY, not bugs** (the coercion was the one real EV leak, now fixed).

**Distance-to-Nash metric (`extraction/preflop_exploit.py`) — EXACT preflop best-response exploitability.** Built per
the user's framing (get closer to GTO, measure where we stand — NOT chase exploits). EXACT in the toy game (all
infosets enumerated; ½[BRV_SB+BRV_BB], Johanson convention). Result: **expl(blueprint)=3.3, expl(heuristic)=234
bb/100 → the blueprint is 71× less exploitable.** A per-NODE decomposition LOCALIZES the old heuristic's leaks
precisely — two huge ones, both "over-fold to a re-raise": **3BET +164 bb/100** (SB over-folds to 3bets → BR
3bet-bluffs any-two) and **4BET +87** (BB folds 98% to 4bets; `_deep_reraise` treats deep re-raises like all-ins).
This MECHANISTICALLY explains the −72: GTOW 3bet/4bet-bluffed us relentlessly and we folded. The blueprint gives real
3bet/4bet defense → fixes both (its residual 3.3 is spread evenly = no single leak, just CFR under-convergence).
**LIVE CONFIRMATION: the GTOW A/B is running and shows −53 ±~24 bb/100 (blueprint ON, n=200) vs the −72 baseline** —
+19 directional, exactly as the leak-fix predicts (slow run, ~10s/hand through a 503-storm; awaiting n≥1000 for significance).
- **CRUCIAL caveat (both Nash-keyword consults + o3 agree, vetted):** in-model exploitability is a CONVERGENCE /
  regression test, NOT real-Nash-distance — "low expl can just mean convergence to the WRONG (checkdown) game." The
  non-circular metric = an **independent-leaf** exploitability: the BR uses REAL postflop leaf values (from
  **TexasSolver** — the user's idea, = the consults' recommendation) instead of the checkdown. THAT is the next build.
- **Decisive cross-check:** if the blueprint's in-model 3.3 doesn't translate to a much-better GTOW number (running),
  the checkdown is missing the real leaks. No published 200bb HU NLHE Nash chart exists (consult) → we measure our own.
- The local bb/100 duplicate (`benchmark/preflop_ab.py`) is a regression-catcher only — GTOBaseline is too weak to
  proxy GTOW (we're ~−5 vs it, −72 vs GTOW). Grounded-confirmed: the blueprint fixes the −15 all-in spew + the 4bet over-fold.

**Clean boundary (HARD rule):** external assets (books/papers/PokerBench/Pluribus/OpenSpiel/the LLM) = validation /
design / exploit-overlay ONLY, NEVER a training label. Validation gates: Leduc exact exploitability + the
clairvoyance toy-game. **vs the field we still crush: Slumbot +31, weak bots +300–700.**

---

## History (2026-06-15, superseded by the neural pivot) — MVP#2: real-time resolving + range tracker
> ⟳ This is the LIVE source of truth. Per the CLAUDE.md standing rule: after any measurement that moves the
> headline, any build that lands, or a priority shift, update THIS section *before ending the turn*.

**Thesis (exploit-primary):** GTO = floor/insurance; the edge = exploiting each opponent's gap to GTO. vs the
exploitable field we WIN big; vs true near-GTO we minimize loss (can't beat it).

**Live headline — GTO Wizard AI, the #1 benchmark (key ACTIVATED; AIVAT, ~10× variance-cut):**
- **DECISION-GRADE (n≈2500, ±~6): the integrated bot is ~−71 vs GTO Wizard, resolver ON or OFF.** Floor (resolver
  OFF) **−70.73 ±5.83** ≈ resolver+v1 **−72.06 ±6.70** — statistically IDENTICAL → the resolver is NEUTRAL (not a
  spew source); the FLOOR ITSELF is −71. BOTH the MVP#1 −33 (n=30) and the resolver −13 (n=150) were LUCKY
  small-sample MIRAGES. **−71 < Always-Fold (−64.6)** ⇒ the integrated bot actively loses chips to near-GTO. Honest
  truth (= the user's diagnosis, now MEASURED): **many parts, NO coherent working MVP yet.** vs the exploitable
  field it still wins (Slumbot +31) — the thesis holds, but the near-GTO floor is far worse than small samples
  suggested. **→ PLAN: [docs/MVP_UNIFY_PLAN.md](archive/MVP_UNIFY_PLAN.md).** Catalog DONE ([BOT_PARTS_CATALOG.md](archive/BOT_PARTS_CATALOG.md);
  §0 = the fragmentation map: two playing brains, an orphaned exploit cluster, dead files). Path: **Phase A** unify
  into ONE core ($0; wire `preflop_gto` into HU bot, reliability-gate the resolver by confidence+pot-size, delete
  dead code) + measure @ n≥2500; **then the ONE sure compute** = solve facing-bet nodes → a **facing-bet DEFENSE
  advisor** (the #1 leak + it unblocks the range tracker's call-narrowing), local-pilot-first then scaled on **≥3
  parallel best-CPU pods, saturated, fast**. ONLY in-repo assets. LESSON, hard: n≤150 AIVAT lies.
- vs **Slumbot** (exploitable): current MVP **+31** (was −102 pre-fix) — crushes the exploitable field.

**Built this session (MVP#2 = supervised blueprint + real-time re-solving + range tracker, the Pluribus/DeepStack
pattern):** `strategy/range_tracker.py` (P0 line-aware ranges) · `strategy/resolver.py` (P1 river + P2 turn: live
TexasSolver re-solve of the actual public state to terminal, sample our hand, floor-fallback) · `bot.py`
`use_resolver`/`use_turn_resolver` · `benchmark/gtowizard.py` adapter + `tools/gtow_run.py`. The GTO Wizard
Benchmark paper (arXiv 2603.23660) VALIDATES this (GTO Wizard AI = real-time-solving + value-net + balanced ranges).

**★ THE keystone — BUILT + integrated + unit-tested (2026-06-15); EV-gate PENDING.** The
quadruple-triangulated #1 (code-review + Opus 4.6 + GPT-5.5 + our notes) = a **Bayesian action-consistent postflop
range tracker** → `strategy/range_tracker.py` v2 (`RangeTracker` + `weighted_ranges`): per-combo Bayes (advisor
`P(bet)` for bet/check; o3-safe **legality-only** for silent call/raise/size — never zeros a live combo),
class-level weighted emit (TexasSolver v0.2.0 CAN'T take per-combo strings — verified, matches our own finding),
confidence-gate → floor. Wired into `_river_resolve`/`_turn_resolve` (builds on the turn resolver, no clobber);
`test_range_tracker` 4/4 + `smoke_weighted_resolve` green. **OPEN — the decision: the P1 EV-gate** = does
resolver+v2-tracker recover the river resolver's **−72**? Three-way vs GTO Wizard: floor baseline · resolver+v1
ranges (−72) · resolver+v2 tracker (one session at a time). **HONEST caveat (verified at the emit):** calls are
legality-only (safe, but no narrowing) → flop-called air stays in the range (96o weighted top on A-K-7-2-9) →
ranges still WIDE → may only PARTIALLY recover; if so the next lever = a facing-bet **defense model** so calls
filter. Cheap win still open: wire `preflop_gto.py` (88.6%) into HU `bot.py` (verified NOT wired). Docs:
[GTO_GAP_REVIEW](archive/GTO_GAP_REVIEW_2026-06-15.md) · [GTO_P0_RANGE_TRACKER](archive/GTO_P0_RANGE_TRACKER_2026-06-15.md).

**Plan / spend:** [MVP2_RUNPOD_PLAN.md](archive/MVP2_RUNPOD_PLAN.md) — closer-to-GTO sequenced by ROI. The $140 RunPod run
is the LAST mile (CFV value-net → flop resolving); **start small/local first** (user directive). Consults:
`runpod_gto_gpt55.md`, `runpod_gto_opus46.md`, `situational_*`. Honest ceiling vs GTO Wizard: **−20…−15 near-term**
(GPT-5.5); ≈0/−3 is NOT a near-term/$140 outcome.

**★ Update (late 2026-06-15) — defense outcome + SHORT-DECK pivot.** Defense advisor (the #1-leak fix, $0 from
existing caches): flop-defense floor −70.7 → **−66.4** (+4.3, marginal/not-sig); adding RIVER defense → **−80.6
(HURTS −14, reverted to flop-only)** — frequency-match-but-lose AGAIN (river = big pots, the +19%-MSE advisor still
loses bb/100). NLHE is the working baseline (crush field / least-loss vs GTO Wizard); we STOP grinding it.
**New direction (DECIDED + GPT-5.5-refined → `docs/shortdeck_consult_gpt55.md`): exploit-vs-field 60% [the only
MEASURED +EV path, the core] / HU-short-deck-postflop near-GTO DEMO 25% [the buildable, measurable artifact —
driving now] / NLHE-defense 15% [leak-patch].** Short-deck = solver-NATIVE (`gto_oracle.solve(mode="shortdeck")`,
Gate.1 re-verified), rule-LOCKED (bundled dict = **trips>straight** variant — flagged for any Triton product);
`engine/sd_eval.py` evaluator built+verified (flush>boat, trips>straight, 7-card, no 2-5; dict keys = ASCII sort).
Cache pilot: 120 flops (`extraction/mass_solve_shortdeck.py`). **Honest claim = "near-TexasSolver HU short-deck
postflop", NOT "6+ solved"; measure via EV-gap + matched-tree BR/LBR, NOT MSE.** Tasks #78–80. Origin: the Movie-Factory run (`SD_6PLUS_GATE_LOG.md`).

> The ★★/★ sections below are MVP#1 + earlier — correct as history, but their headline framings (the −526/−160 and
> "GTO Wizard key 401") are SUPERSEDED by this section. Read them for detail, not for the current state.

---

## What this is
A Heads-Up **and** 6-max No-Limit Hold'em bot grounded in three poker books, a browser app to play it, an
online opponent-exploiting layer, and tooling to measure our play against true GTO. North star: a
**universal adaptive exploiter** — a low-exploitability baseline + an online opponent model that detects and
safely exploits each opponent's leaks (confidence-gated), built to handle opponents we haven't seen yet.

## ★★ Final MVP build + DEFINITIVE scorecard (2026-06-15, supersedes below)
**Plan:** `.claude/plans/adaptive-rolling-fog.md` · **Scorecard:** `pokerbot/benchmark/scorecard.py` → `knowledge_base/scorecard.json`
The exploit-primary pivot is now a SHIPPED MVP: ONE `PokerBot(exploit=True)` = solver-grounded floor (flop/turn/
**river** advisors) + a safe river EV-exploit engine + a bounded prediction-gated off-tree size probe. A/B toggles:
`use_turn_advisor/use_river_blocker/use_fe_sizing/use_mdf_shade/use_river_advisor/use_probe`. Measured KEY-FREE:
- **Least-loss vs near-GTO (decision-grade):** flop GTO-gap **31%** (floor frequencies MATCH the solver — bet 47.4%
  vs 47.1%, OOP 22/22, IP 75/74); floor vs GTOBaseline (paired) **−22 ±64 ≈ break-even**. Competitive vs near-GTO.
- **Exploit edge (the thesis, DELIVERED):** crushes the exploitable field — station +109, maniac +224, nit +58,
  foldy +78, sticky +135, trappy +42 bb/100; mechanism **+33 vs a steep size-cliff**. Ties its own strong mirror
  (PokerBot vs PokerBot −53 ±60 = noise). → huge edge vs the exploitable, ~break-even vs near-GTO = exactly the thesis.
- **WS1 floor-bleed RESOLVED:** the −102 vs Slumbot was variance/Slumbot-specific, NOT a leak (`floor_ablate.py`:
  no toggle moves the floor >2σ vs GTOBaseline; #40 river-blocker 0 effect, #41 turn-advisor +8 sub-1σ). #40/#41 kept.
- **WS2 river advisor (the win):** `build_river_data.py`+`train_river_advisor.py` (1308 caches) → `river_advisor.pt`
  **+51%** vs freq baseline → **+38.6 ±15.6** paired floor improvement (closes the last un-grounded street, NOTES #4).
- **WS3 unify:** AdaptiveExploiter kept as a labelled reference; the probe re-enables the off-tree edge; the Dirichlet
  per-node model is the calibration. **WS5 GTO Wizard harness READY-TO-FIRE** (`benchmark/gtowizard.py`, offline-tested).
- **⚠ [SUPERSEDED — the key was ACTIVATED later the same day; see ★★★ CURRENT at top. Below = pre-activation state.] The GTO Wizard key was tested LIVE (2026-06-15) and returned `401 Unauthorized`** — the 32-char string in the
  file is a placeholder / not-yet-granted (verified UP TO AUTH: cloned + uv-synced 3.13, `gtowizard.py` adapter
  rebuilt vs the real schema + offline-tested, `tools/gtow_run.py` connects; blocked ONLY on a VALID key). Once a
  valid key exists, going live
  (user's call — outward-facing, spends the 100k/mo quota) = the DEFINITIVE measure vs the true opponent: clone
  `gtowizard-ai/researcher-api-client` under `tools/gtow_client/` (Py3.13/uv), confirm the adapter's CONFIRM-ON-CLONE
  items, run `--num-hands 200` then ≥2500 (AIVAT) + leaderboard.
- **vs TexasSolver (2026-06-15, both built):** (A) deterministic GTO-gap (`floor_map` flop+turn+river) = **flop 31% /
  river 29%, FREQUENCY-FAITHFUL** to the solver (our-bet 47/47, 30/31; turn locally unmeasurable — local cache is
  DUMP=1, the DUMP=2 turn subtrees were on the killed pod); (B) head-to-head bb/100 (`benchmark/gto_oracle_match.py`,
  MVP vs a live-solver-driven oracle, 40bb) = **+185 ±133** vs an APPROXIMATE oracle (full SRP ranges, no
  continuation-narrowing → our bot exploits the wrong turn/river ranges; NOT beating true GTO; ~1.4σ noisy). The gap
  (frequency-match) is the trustworthy GTO-closeness signal. (tombos21 = Tom Boshoff, GTOW head coach; r/pokertheory
  validates the simplified-grounded approach.)
- **Next:** (1) user decides the GTO Wizard live run; (2) confirmatory large-N Slumbot run to close the −102;
  (3) optional: extend the GTO-gap to turn+river, port the TwoModelGate/Calibrator if the field shows it's needed.

## ★ Latest session — Consolidation, Unification & Phase 1 (2026-06-14/15, supersedes older detail below)
**Plan:** [docs/CONSOLIDATION_PLAN.md](archive/CONSOLIDATION_PLAN.md) · **Architecture:** [docs/META_STRATEGY.md](archive/META_STRATEGY.md)
- **Exploit↔GTO unified (no mismatch):** ONE best-response engine — pointed at the opponent = exploit, pointed
  at itself (self-play) = converges to the floor (GTO/CCE). Live design = a GTO **floor** + a BOUNDED,
  confidence-gated exploit **overlay** (`freq_delta∈[-0.3,0.3]`) on top; no read → pure floor.
- **Floor sharpened (grounded):** preflop exact-lookup table distilled from PokerBench (**88.6%** held-out,
  beats both LoRAs) → `knowledge_base/ranges/preflop_gto_table.json` + `strategy/preflop_gto.py`, wired into
  sixmax RFI. Postflop priors solver-CALIBRATED (cbet_eq 0.48→0.72, held-out TV-gap 0.62→0.50). sixmax made
  role-aware → measured solver gap 45%→31%.
- **Knowledge-as-database (Phase 0A):** 5 books extracted via Claude → **262 exploit primitives** + **95 AGT
  theory** concepts; deduped to **62 stat-keyed wireable rules** → `knowledge_base/exploit/unified.json`. The 2
  SOTA papers (**Supremus**, **Pluribus**) → **27 recipe items** (CFVnet 7×500 zero-sum MLP, bucketing
  1326→1000, DCFR+, depth-limited re-solving) → `knowledge_base/theory/`. Grounds the eventual self-play net.
- **Phase 0C bug-hunt (3 agent-audited + verified fixes):** sixmax decision rng was reseeded per-spot → fake
  (deterministic) mixing → now persistent rng (real mixing, 117/83 over 200 same-spot calls); gto_baseline's
  calibrated c-bet branch was DEAD live (no `aggressor` key) → now derives initiative from history; opponent.py
  exploit stats jumped prior→raw at n≥4 → Bayesian shrinkage (k=6). Tests green; duplicate null still 0±0.
- **Phase 0B:** source PDFs moved to `books/` (papers under `books/papers/`).
- **Objective edge CONFIRMED:** adaptive+gate beats a diverse suite (worst +27 bb/100), 2× extraction vs static.
  Exploitation is a real MEASURED edge; vs near-GTO the ceiling is ~break-even (needs AIVAT to measure).
- **Net verdict (refined):** a net is the eventual path to a true GTO floor (Supremus = proof) via self-play,
  but a big build for an unmeasurable near-GTO gain — DEFERRED behind the cheap floor + the field-edge.
- **Compute:** GCP 256-CPU/GPU quota requested (~business days); ≤12 vCPU adjustable now. → **RunPod-first**
  for GPU + 12-vCPU GCP for small CPU; high-leverage calcs only; spot + `--kill`/auto-stop.
- **Phase 1 DONE (2026-06-15), all gated:** (a) live HU bot range-c-bets at the calibrated texture freq
  (medium+air, 36→82% on dry boards, duplicate A/B +23); (b) the 62 rules wired into the exploit channel —
  which was DEAD (`_pb` computed but never applied → the playbook + LLM-directive seam never ran) → REVIVED;
  the rules help vs exploitable (station +308, maniac +262, no leak vs strong). **Simplify sidequest gold:**
  river equity now ENUMERATED not Monte-Carlo'd (exact, 9× faster, killed a 3% pot-odds decision-flip noise
  bug). All committed; full test suite green (test_web_client needs a LIVE HU server on :8000 — an in-process
  TestClient smoke confirms the HU app is healthy). Phase-1 consult was done WITH gpt-5.1; gpt-5.5 is on the API.
- **Next (awaiting user go):** **(c) self-play→GTO** — prove convergence on Leduc first, then warm-start from
  solver caches, then RunPod GPU (high-leverage only). Remaining simplify Tier-A: turn-enum → suit-canonical
  equity cache. Activate more live opponent stats to fire the gated-off unified rules (~27/62 fire now).

## Run it
- 6-max vs 5 bots (main app): `python -m pokerbot.web.six_server --open` → http://127.0.0.1:8000
- Heads-Up + live coach: `python -m pokerbot.web.server --open`
- Windows / PowerShell, Python 3.12. `pip install -r requirements.txt`. Always run from root as `python -m ...`.

## Honest status (what's real vs projected)
- **Preflop**: GTO-grounded (verified Nash push/fold CFR blueprint + strength-model ranges deeper).
- **Postflop**: equity + pot-odds/MDF + fold-equity-optimal sizing + an exploit layer — **not** a solver.
- vs **Slumbot** (measured 2026-06-14, 300h): the old "heuristic alone ≈ −170" was a small-sample MYTH — the
  no-exploit floor really lost **~−526 bb/100** (it **stacked off 200bb bluff-raising air**). A cheap anti-spew
  fix → **~−46 bb/100** no-exploit (near break-even, +480 swing). WITH the fold-curve exploit on the fixed
  floor: **~−5.4 bb/100** (500h, ±113 ≈break-even; was −186 pre-fix — not yet conclusive, needs 5–10k hands).
- vs **Pluribus** (from its 10k hands): it over-folds postflop → projected ~+4 bb/100 (ceiling ~6–8); small,
  real, safe (it never adapts).
- Crushes weak/exploitable opponents locally (+300–700 bb/100).
- The deficit vs near-GTO Slumbot WAS mostly a fixable SPEW (now fixed), not pure exploitability — the floor
  still has cheap wins before a GTO net is strictly needed.

## Scorecard (2026-06-14, the first HONEST one — measured, not projected)
Engine compare vs a diverse suite (`beat_them_all`-style, 250h/match) + Slumbot:
- **`PokerBot(exploit=ON)` BEATS EVERYTHING** — worst case **+1 bb/100** (vs the strong peer); station +493,
  maniac +757, sticky +393, trappy +161; and **≈−5 bb/100 vs Slumbot** (500h). This is the robust +
  exploitative "universal" bot the project wanted — the anti-spew fix created it.
- `PokerBot(exploit=off)`: most robust (worst +44) but crushes weak less.
- `AdaptiveExploiter`: crushes weak HARDEST (+727/+1275) but **leaks −47 vs the strong peer** — it
  over-specializes. Root (measured, knob-by-knob): adaptive's BASE decide() is weaker than PokerBot's
  (−56 with all exploit knobs OFF), NOT a mis-tuned gate. So the real upside = port adaptive's SAFE extras
  (calibration, playbook cold-start, LLM strategist) ONTO PokerBot's robust floor, not the reverse.
- LBR v1 too loose to score the floor (loses −987 to it; nit-sanity +75 OK) → needs v2 for a hard number.
- **Takeaway:** our strong main bot is `PokerBot(exploit=ON)`. Edge work = sharpen exploitation ON this
  floor + validate at scale. The GTO net is deferred insurance (and now cheap via the GCP credit).

## Current workstream (2026-06-14): a strategic LLM + a GTO oracle + an exploit playbook
Three resources were run in parallel (the clean split — see the memory note [[pod-run-validation]]):

1. **GPU (RunPod B200): Qwen3-8B LoRA fine-tune on PokerBench** — [extraction/qwen_sft.py](../training/qwen_sft.py).
   The strategic/language layer (exploit hypotheses, coaching, curriculum), **not** a per-hand player.
   At step ~90/987 it was already 96% token-accuracy → converges fast; full 987 steps unnecessary.
   Output LoRA → `/root/qwen_poker_lora` (retrieve, then `--kill` the pod). Needs torch cu128 on Blackwell.
   - **HARD LESSON**: on ONE box a heavy CPU job and a GPU-training job cannot coexist (CPU starves GPU
     kernel-dispatch *and* sshd → unmanageable). "Both at 80%" needs **separate** pods. So:
2. **CPU (local i9-12900K): TexasSolver mass-solve** — [extraction/mass_solve.py](../research/mass_solve.py)
   (RAM-adaptive; 16 GB box → ~5 parallel solves, auto-scales). Builds a GTO cache for distillation/benchmark
   in `data/_gto_bench_cache/` (regenerable; gitignored). ~16 boards/min.
3. **Claude API: exploit playbook** — [extraction/exploit_playbook.py](../research/exploit_playbook.py).
   Bounded, machine-checkable exploit directives across an opponent-profile × spot grid (a PROPOSER pass;
   the benchmark verifies before anything is applied). Artifacts:
   - `knowledge_base/exploit/playbook.jsonl` — 11,520 directives (Haiku).
   - `knowledge_base/exploit/playbook_opus_coarse.jsonl` — 240 directives (Opus, high-quality subset).

## What the GTO cache already tells us (from [extraction/analyze_cache.py](../research/analyze_cache.py), 597 flops)
- **IP c-bet by texture** (robust GTO signal): dry/high/rainbow/paired ~77–78%, monotone 58%, connected 60%,
  low 67%, overall 74% → c-bet more on aggressor-favoring boards, less on caller-favoring ones.
- **C-bet sizing**: ~96% of c-bet mass uses ONE size (~⅔ pot) — GTO barely mixes sizes here.
- **OOP donk**: 22% overall (likely **inflated by non-tuned ranges** — real BB-vs-BTN SRP donks <8%; validate
  the `_OOP/_IP` ranges before acting on the absolute number; the texture-relative direction is fine).

## Shipped 2026-06-14
- **★ Duplicate-poker VERIFY GATE + net-vs-database verdict + LLM-match reality (the linchpin block).**
  - `pokerbot/benchmark/duplicate.py` — mirror matching cancels card luck (null test: 0±0 vs naive ±132).
    THE tool for reliably accepting/rejecting a bot change at small samples (no AIVAT needed). Use:
    `duplicate_ab(make_a, make_b, gen_decks(n))`. Caveat: rare-but-large-swing changes still need many decks.
  - **thin_value RESOLVED via the gate: NEUTRAL** (0.72 vs 0.78 → −7.1±9.7 @300 decks, +8.75±8.9 @1000;
    straddle 0). The earlier revert was right; `bot.py` now exposes `self.value_raise_eq` (A/B hook, default
    0.72 = unchanged).
  - **NET vs DATABASE verdict (the strategic answer):** we do NOT need our own neural net yet. A net is just a
    generalizer trained ON a database; measured bottleneck is DATA COVERAGE not model size; our heuristic floor
    already generalizes + is ≈break-even; edge = exploitation not GTO. → the bigger solver DATABASE is the more
    fundamental need, as the GROUNDED-VERIFY resource (not a lookup table, not yet net-training-data). Build a
    net only if heuristics provably plateau below it (LBR/duplicate). Deep-CFR self-play = deferred.
  - **RunPod 32-vCPU CPU coverage-solve RUNNING** (`extraction/runpod_solve_*.sh`, pod is6nj19spqb1f7, $1.12/h,
    ~200 turn-boards/h; GCP free-tier capped at 12 vCPU). Pull cache + `runpod_run --kill` on completion.
  - **LLM-match reality** (`pokerbot/benchmark/llm_opponent.py`, strong PokerSkill-style prompt + reasoning):
    vs frontier LLM agents we are ROUGHLY EVEN at noisy 40-hand samples — Opus 4.8 +30, o3 +17 (the naive
    gpt-5.1 +395 was a prompt-weakness + noise MIRAGE). Reliable opponent-strength needs AIVAT = the GTOW key.
- **Active-learning toolkit + the verify-lesson + 6-max solvability (autonomous block).**
  - `extraction/blindspot_radar.py` — massive concurrent Claude-Haiku triage of bot decisions → ranked
    suspected blindspots. LESSON (hard-won): LLM triage is a HYPOTHESIS generator, not truth — it flagged
    `thin_value_too_big` with high confidence; the fix was MEASURED neutral-to-worse → reverted. Also
    play-testing bb/100 is too NOISY to verify a single rule. → use the GROUNDED signal + solver to verify.
  - `extraction/grounded_blindspots.py` — per-spot solver-disagreement from the cache (matches gto_benchmark:
    IP-high 23%, OOP-connected 24%). The reliable acquisition signal. Real grounded floor gaps: OOP donks the
    wrong (strong) hands; IP OVER-c-bets (95% vs GTO 79%). Use the AGGREGATE (gap+bet-freq), not top-individual.
  - **GCP pipeline VALIDATED** (`extraction/gcp_solve_setup.sh` + `gcp_solve_launch.sh`): TexasSolver-Linux +
    mass_solve run end-to-end on a VM. BUT free-tier is capped at **12 vCPU global (CPUS_ALL_REGIONS)** → the
    big saturated coverage-solve needs an account upgrade / quota increase. Project id `project-f2a4a8eb-7533-4ecf-a00`.
  - **6-max solvability (gpt-5.1, `data/sessions/solvability_6max.md`):** 6-max NLHE is NOT solvable like HU —
    PPAD-hard, Nash non-unique, no-regret → CCE not Nash, no scalar exploitability. Realistic target = a
    **bounded-exploitability blueprint + adaptive exploit** = exactly this project's thesis (validated). North
    star: minimize measured LBR exploitability while maximizing realized bb/100 vs the exploitable field.
- **★ Anti-spew floor fix + independent bot audit (the session's biggest MEASURED win).** Traced the no-exploit
  floor's catastrophic loss vs strong opponents to ONE leak: it bluff-RAISED air (eq<0.33) at ~pot size =
  effectively all-in on deeper/later streets, and value-raised dominated top pair, because `PriorFoldModel`
  over-assumes folds. Fix (`bot.py`): the floor never raise-bluffs without a confident read; value-raise + SPR
  commitment caps. **Measured: no-exploit vs GTOBaseline −912 → +207 bb/100; vs Slumbot −526 → −46.** Then an
  independent `claude-opus-4-8` audit (`extraction/bot_audit.py`, every finding hand-vetted; it called the code
  "mostly sound") found the SAME spew live in `adaptive.py` — root cause = no range-narrowing vs aggression →
  over-rated marginal hands → over-committed. Fixed (range-narrowing ported from `gto_baseline` + commitment
  caps + a preflop-4bet premium gate); 200bb stack-offs eliminated (worst hand −20000 → ~−7762). Phases 1.1–1.4
  (EV-correct value sizing, texture c-bet, MDF defense, gated Pluribus fold-exploit) also shipped + committed.
- **Self-calibrating fold-equity** ([pokerbot/strategy/calibration.py](../pokerbot/strategy/calibration.py)) —
  a prediction->measurement->calibration loop (ported from the Mycelium crypto bot's learning-engine), wired
  into `adaptive.py`: logs predicted-vs-observed folds in the spots we ACTUALLY bet (selection-aware), bias-
  corrects future fold-equity, exposes a data-driven confidence. None-safe (no data -> behaviour unchanged).
  Tests: `python -m tests.test_calibration`. Persisted per opponent under `data/calibration/<name>.json`.
- **GTO-floor net v0 (distillation)** ([extraction/distill_improve.py](../research/distill_improve.py)) on the
  1340-board solver cache (local RTX 3080 Ti): added minibatching to `distill.train` (full-batch underfit
  328k samples); 256³ net → held-out **TV-gap 17.7%→17.0%**, saved `data/floor_net.pt`. **KEY FINDING
  (empirically validated, not just taken from the OpenAI tips): bigger nets barely move it → the bottleneck is
  DATA COVERAGE, not the model.** Vetted OpenAI (gpt-5.1) advice via [extraction/cfr_tips.py](../research/cfr_tips.py).
- **Exploit playbook WIRED** into the adaptive engine as a cold-start prior ([pokerbot/strategy/playbook.py](../pokerbot/strategy/playbook.py)):
  nearest-profile lookup -> bounded, confidence-FADED nudge (bluff / value / bluff-catch); `directive_to_nudge`
  is the SAME channel the live LLM strategist will write into later. Tests: `python -m tests.test_playbook`.
- **LBR exploitability evaluator** ([pokerbot/benchmark/lbr.py](../pokerbot/benchmark/lbr.py)): a Local-Best-Response
  lower bound via rollouts with RE-SAMPLED hidden cards (no hidden-info cheat) + passive continuation.
  VALIDATED (crushes a nit +75+/-4 bb/100). v1 (uniform range) is a LOOSE bound -> too weak to find a leak in
  the baseline floor yet (LBR loses to it); v2 = Bayesian action-consistent range for a tight number.
- **Qwen LoRA fine-tune SAVED** (step-500, 97% token-acc) -> `models/qwen_poker_ckpt500/` (adapter 666 MB);
  pod auto-killed (billing stopped). The strategist layer for the INTEGRATION plan. **Eval PROVEN:** held-out
  PokerBench decision-match **base 18.3% -> LoRA 71.7% (+53pp)** ([extraction/qwen_eval.py](../training/qwen_eval.py)).
- **LLM integration COMPLETE (proven end-to-end).** `meta_coach` gained a `provider="local"` (LoRA in 4-bit via
  transformers, no vLLM) -> `propose_exploit` emits a bounded directive -> `directive_to_nudge` ->
  `AdaptiveExploiter.refresh_llm_exploit()` installs it as `live_directive` -> applied (capped) in `decide()`.
  The LoRA follows the exploit-directive JSON schema (Qwen3 `<think>` tokens disabled/stripped). Demo:
  `python -m extraction.llm_exploit_demo`. Call `refresh_llm_exploit(coach)` per SESSION (not per hand).

## Open threads / next steps (in priority order)
0. **GTO floor — the #1 lever (now evidence-backed).** The distilled floor plateaus ~17% TV on SRP-flop-only
   data. Real gains need, in order: (a) **coverage campaign** — broaden the solver cache (turns, rivers, 3-bet
   pots, stack depths) with a wider TexasSolver tree (CPU); (b) finer **action buckets** (add overbets) +
   EV-weighted loss + post-hoc calibration; (c) an **LBR (local best response) evaluator** for HONEST NLHE
   exploitability (TV is only a proxy — a low TV can still be exploitable). Then wire `floor_net.pt` as the
   policy floor (`cfr_policy.py`, see [INTEGRATION.md](archive/INTEGRATION.md)). Methodology lab: validate CFR+ on the
   self-contained Leduc Deep-CFR (`deep_cfr.py`, exact exploitability) before any NLHE self-play.
1. ✅ DONE — Qwen LoRA saved to `models/qwen_poker_ckpt500/` (step-500, 97%); pod killed (no billing).
2. Eval the saved LoRA vs base Qwen on held-out PokerBench locally (RTX 3080 Ti) to prove the decision gain.
3. **Make `gto_baseline` c-bet texture-aware** (high on dry/high/rainbow, low on monotone/connected) and fix
   the size to ~⅔ pot — the concrete bot change the cache points to. → [pokerbot/strategy/gto_baseline.py](../pokerbot/strategy/gto_baseline.py)
4. **Wire the exploit playbook into the adaptive engine** as a cold-start prior (nearest-profile lookup,
   confidence-gated). → [pokerbot/strategy/adaptive.py](../pokerbot/strategy/adaptive.py)
5. Serve the fine-tuned Qwen (vLLM) and point `meta_coach(provider="openai", base_url=…)` at it — the
   in-loop strategist. → [pokerbot/coach/meta_coach.py](../pokerbot/coach/meta_coach.py)
6. (Tournament mode, future) **ICM / risk-premium** multiplier on short-stack stack-off thresholds in
   `cfr_preflop`/`blueprint`: a tournament stack IS a bankroll with an absorbing barrier (ruin), so chips
   have concave utility — decline +chipEV / −$EV gambles near pay jumps. This is the in-game home for the
   Mycelium fractional-Kelly + CVaR lens (only relevant once we add tournament play; cash stays linear EV).

## Map (cross-references)
- **Engine**: `pokerbot/engine/` (cards, treys eval, MC equity, HU `game.py`, N-player `table.py`).
- **Strategy**: `pokerbot/strategy/` — `cfr_preflop.py`+`blueprint.py` (Nash push/fold), `postflop.py`,
  `gto_baseline.py` (analytic GTO, texture/aggressor-aware), `gto_oracle.py` (TexasSolver wrapper),
  `adaptive.py` (exploit engine + self-calibrating fold-equity via `calibration.py`), `opponent.py`,
  `pluribus_exploit.py`, `bot.py`.
- **6-max brain**: [pokerbot/arena/sixmax.py](../pokerbot/arena/sixmax.py) (per-seat independent; the 3 fixed leaks).
- **Coach / LLM**: `pokerbot/coach/` — `meta_coach.py` (engine-agnostic), `translate.py`.
- **Benchmark**: `pokerbot/benchmark/` — `gto_benchmark.py` (scores us vs the solver cache), `slumbot.py`,
  `beat_them_all.py`, `pluribus_*`.
- **Heavy compute**: `extraction/` — `mass_solve.py`, `exploit_playbook.py`, `analyze_cache.py`, `qwen_sft.py`,
  `runpod_run.py` (pod lifecycle; always `--kill`), `deep_cfr_nlhe.py`, `pod_run30.py`.
- **Knowledge** (committed): `knowledge_base/` — `concepts/`, `ranges/` (+ `cfr/preflop_pushfold.json`),
  `math/`, `exploit/` (playbooks + `slumbot_fold.json`), `hand_histories/` (10k Pluribus), `theory/`.
- **Plans**: [plans/ROADMAP.md](plans/ROADMAP.md), [plans/POD_PLAN.md](plans/POD_PLAN.md), [docs/RUNPOD_PLAN.md](archive/RUNPOD_PLAN.md).

## Infra notes
- Keys: read from `C:\Users\hampe\Desktop\Secret keys\` (outside the repo) via [pokerbot/config.py](../pokerbot/config.py) — never hardcode.
- RunPod: `--kill` = `DELETE /pods/{id}` = full terminate (compute+storage billing stops). A mere "stop" still
  bills storage. SSH key `C:\Users\hampe\.ssh\pokerb_runpod`; fresh pods get a NEW ssh port (read `--status`).
- Models: Claude `claude-opus-4-8` (quality) / `claude-haiku-4-5` (cheap in-loop); OpenAI auto-resolves to `gpt-5.1`.
