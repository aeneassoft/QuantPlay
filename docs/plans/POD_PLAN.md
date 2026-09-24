# POD_PLAN.md — Overall plan of the next operations (synthesis, 2026-08-16)

**State at time of writing:** loop proven locally (self-test 4/4; E1 9/9 Fraction references).
Basis frozen (tag `autogym-basis`). Measurement doctrine = mathematics benchmark (oracle) +
self-play gates + paired A/B new-vs-old bot — **no GTOW in this phase**. First
candidate `podds_guard` (uniform range) NEUTRAL (n=800, +0.31 ± 0.31). Wired: 7 checks.
Open: wave 1b + wave 2 (see [`../catalogs/AUTOGYM_INVENTORY.md`](../catalogs/AUTOGYM_INVENTORY.md)).

Order of the plan: **1. complete the benchmark → 2. local mandatory gates → 3. pod deployment**,
carried by the work packages (4.), under the versioning rule (5.), with an open eye
on the tipping risks (6.).

---

## 1. COMPLETE THE BENCHMARK

Result of the completeness check: [`../catalogs/BENCHMARK_COMPLETENESS.md`](../catalogs/BENCHMARK_COMPLETENESS.md).
The ten findings, here as a working basis:

1. **95% thesis CONFIRMED for decision mathematics:** the inventory covers all 78
   definitions (77 unique) of the three formula files exactly; the count is correct.
2. **Biggest find:** `postflop/strategy_calc_verified.json` carries ready-made
   `verify_expr`/`verify_value` pairs per function = **66 unused E1 references** — a ~30-line runner
   immediately turns them into a machine verification net (→ AP7).
3. **Three repo domains not inventoried, but mountable:** (A) ICM/tournament
   (`strategy/icm.py` + `tournament.py` + `arena/tourney.py` — HART Σ-ICM invariant,
   L `icm_call_ohne_odds`, knob BF_eff), (B) measurement/variance statistics from
   `mathematics_of_poker.json` (443 entries, many with Python — never mentioned in the inventory),
   (C) MoP toy-game anchors + multiway.
4. **Proposal for a new level "MESS":** check the gate SE itself against a Fraction closed form —
   the most expensive currently unchecked number of the system (ANWENDEN > 2·SE hangs on it) (→ AP8).
5. **Multiway L level is achievable:** `gym_six` logs `villain_hole=None`, although ALL holes
   are known; missing building block = `equity_vs_hands` (multi-opponent MC, ~20 lines) (→ AP10).
6. `tests/test_math_suite.py` already contains Fraction references for W1-4/5/7 (`_alpha_mdf`,
   `_bluff_ratio`, `_rfe`) — **import instead of re-deriving**.
7. **Genuinely missing (5 points):** bankroll/RoR/Kelly module (only JSON strings, un-formalized),
   `reverse_implied_odds` code fix (verified:false), `equity_vs_hands`,
   jam-or-fold reference data (computable from the MoP model itself), rake model (deliberately,
   only with a live target).
8. **Deliberate exclusions confirmed correct:** 17 range-based functions,
   `effective_multi_street_required_equity`, concepts.json (813 entries, qualitative).
9. **Knob additions documented** (ICM_LEAD_MARGIN, BF_eff form fixed, icm_pressure_mult);
   multiway independence = declared approximation, no knob.
10. **Order:** verify_expr runner immediately ($0) → wave 1 unchanged → MESS level before the
    next gate → ICM gym → `equity_vs_hands` with wave 2.

---

## 2. LOCAL MANDATORY GATES before the pod

Each stage with a **pre-registered expectation** (do not adjust after seeing the numbers). The
instruments are the loop itself (`python -m pokerbot.autogym.selftest`) and the improver;
everything here is $0 and local. The pod only starts once G1–G7 are green.

| Gate | Check | Pre-registered expectation |
|---|---|---|
| **G1** | Self-test after EVERY new wiring wave (E1 grows with it: every new check gets its Fraction reference) | E1 exact (tolerance 1e-12), E2–E4 PASS; a FAIL stops the wave |
| **G2** | verify_expr runner (AP7) over `strategy_calc_verified.json` | 66/66 PASS or a documented exclusion reason per exception (like `reverse_implied_odds` verified:false) |
| **G3** | MESS level (AP8): the `duplicate_ab` SE against the Fraction closed form of the paired sample variance, on constructed data | agreement < 1e-12; additionally SE(n) ~ 1/√n over n = 100/400/1600 |
| **G4** | AP1 `tracker_podds_guard` through the gate (n=800 decks) | ANWENDEN (bb100 − 2·SE > 0) OR second NEUTRAL ⇒ family "river-call guard" exhausted, journal entry, continue with F leads |
| **G5** | E5 pre-stage LOCALLY: multiprocessing scaling on the local cores (workers = physical cores) | ≥ 0.7× linear scaling per core (today only 580 hands/min single-process are proven) — if that fails, the pod calculation is moot BEFORE money flows |
| **G6** | Determinism: two runs with the same seed ⇒ identical oracle counts + identical gate number | byte-identical (PYTHONHASHSEED lesson; set iteration is the known trap) |
| **G7** | Journal hygiene: dedupe of the top-L proposals from mirrored passes (known open; visible in the journal: 112.12 duplicated) | after fix: identical hand ⇒ exactly ONE lead entry |

Additional observation under G1: the pair drift was positive twice in a row (+294 ± 195, then
+106.8 ± 70.3 — 1.5 SE each). Formally PASS, but a third positive run in a row is a
pre-registered investigation trigger (seat asymmetry? OppModel persistence?) — clarify BEFORE the pod,
otherwise all gate SEs stand on an ununderstood asymmetry.

---

## 3. THE POD DEPLOYMENT ($140, RunPod Secure Cloud, CPU maxcore)

### 3.1 Price situation (researched 2026-08, list prices; verify in the console before deploy — prices fluctuate)

| Instance | Cores | $/h | $/vCPU-h | $140 buys | Hands (@E5 scaling ~156/min/core) |
|---|---|---|---|---|---|
| CPU compute-opt. (cpu3c/cpu5c) | 2/4/8 vCPU per pod ($0.06/0.12/0.24 per h) | $0.24 @8vCPU | **~$0.030** | 583 h @8vCPU | ~44 million @64 cores (8 pods in parallel) |
| CPU 64 cores aggregated (8×8 OR 1 large one, if the console offers >8) | 64 | ~$1.92 | $0.030 | **~73 h** | ≥10,000/min (E5 target) → ~44 million |
| H100 PCIe | 16 vCPU | $2.89 | $0.181 | 48 h | ~7 million |
| H100 SXM | 20 vCPU | $3.29 | $0.165 | 42 h | ~8 million |
| H200 | 12–24 vCPU | $4.39–4.59 | ~$0.19 | ~31 h | ~5–9 million |
| B200 | 26–28 vCPU | $6.79 | $0.24 | 20 h | ~8 million (CPU side) |

**Scenarios ($140):**
- **A — CPU-only maxcore: ~73 h at 64 cores.** At E5 target (≥10k hands/min) ≈ 44 million hands. One
  gate experiment at 2×50k paired hands ≈ 10 min → **~400 gate experiments**. Clear winner:
  5–6× more core-hours per dollar than any GPU pod.
- **B — GPU pod as CPU source (H100 SXM, 20 vCPU): 42 h ≈ 8 million hands / ~75 experiments.**
  Only sensible if the same session ALSO needs GPU — currently not (no GPU training;
  AUTOGYM is pure CPU load).
- **C — mixed: $115 CPU (≈60 h maxcore, ~36 million hands) + $25 reserve** (≈7 h H100 SXM) for
  a later GPU need (e.g. leaf net of the v4 path).

**Recommendation: scenario C.** "Most powerful pod" means for OUR load (CFR/self-play)
cores/dollar, not GPU — B200 would be 8× more expensive per core, and CLAUDE.md warns against
sm_100 anyway. Beware the instance cap: the docs show CPU pods up to 8 vCPU → 64 cores = 8 parallel
pods (price identical); `infra/runpod_run.py` then needs multi-pod handling + per pod
tarball-in/results-out. If the console lists larger CPU instances, take those (less
orchestration).

### 3.2 Budget split: the numbered runs

Rules above all runs: **ALWAYS `--kill`** (8 pods = 8 kills, atexit+finally), one
scp tarball per direction, 2-node doctrine (no CPU/GPU mix on one box), avoid Community Cloud
(preemption destroys paired runs), **scp results + journal back BEFORE the kill**
(lesson from the GRPO pull loss), long sessions instead of many short ones (setup tax).

| Run | Goal | Duration | Cost | Abort criterion | Pre-registered expectation |
|---|---|---|---|---|---|
| **R1 PILOT** | Measure the E5 gate: hands/min on 8 vCPU + orchestration smoke on 2 pods (tarball in, journal out, both kills clean) | 1 h | ~$2 | < 60% of target (< ~94 hands/min/core) → kill, optimize locally, re-pilot | ≥ 130 hands/min/core (≈ 156 · 0.85), extrapolated ≥ 8,300/min on 64 cores; HART = 0 |
| **R2 CALIBRATION BLOCK** | Large-n reference of the basis (HU ≥ 50k pairs → reference SE), 6-max position ledger at n ≥ 1,000/position, validate wave-1b checks (AP2–AP6) at large n | 15 h at 64 cores | ~$29 | HART > 0 or E4 violation on the pod (loop broken) → immediate kill + local debugging | reference SE of the basis < 1 bb/100; mdf_flop finding decomposes per sizing bucket without vanishing (sum consistency) |
| **R3 CANDIDATE LADDER** | All locally surviving candidates (AP1, later guards) paired vs `autogym-basis` at n = 5,000–50,000 decks; only > 2·SE winners get names | 20 h | ~$38 | 3 families NEUTRAL in a row → STOP; do not throw hours after it, rethink the measurement channel instead (section 6, point 2) | ≥ 1 candidate ANWENDEN with effect > 2·SE; every verdict in the journal |
| **R4 WAVE-2 / MULTIWAY** | Wave-2-instrumented long runs (hand_id/hand_result/line aggregations), multiway L via `equity_vs_hands`, ICM gym first run if the AP state allows it | 20 h | ~$38 | Wave-2 instrumentation not locally G1-green → run does NOT start (no "finish building on the pod") | implied-odds family delivers first quantified L leads; multiway lead rate comparable to the HU order of magnitude (plausibility anchor) |
| **RESERVE** | $25 GPU (≈7 h H100 SXM, only with a concrete GPU need, e.g. v4 leaf net) + ~$8 CPU buffer for re-pilots/re-measurements | — | ~$33 | is NOT touched without a concrete, pre-registered need | — |

Sum: ~$107 planned + ~$33 reserve = $140.

---

## 4. THE WORK PACKAGES (backlog, 10 packages)

Derived from `journal.jsonl`, `../catalogs/AUTOGYM_INVENTORY.md` (W1b/W2), the podds_guard NEUTRAL and
the completeness check (section 1).

**Preliminary finding on the core question (tracker range): no new plumbing needed.**
`HeadsUpGame.state()` returns `"history"` (pokerbot/engine/game.py:304), and
`RangeTracker(advisor=None).build(state)` (pokerbot/strategy/range_tracker.py:279)
reconstructs the range **statelessly per decision** from exactly this state dict. The
wrapper `d(st)` in the improver already receives the full state — so:
`t = RangeTracker().build(st)`; villain combos with weights lie in
`t.range[1 - st["to_act"]]` (dict {(c1,c2): w}); equity via `equity_vs_weighted_range`
(pokerbot/engine/equity.py:79 — **exact weighted enumeration on the river, zero variance**,
better than the 40-combo MC sample of the old guard); confidence gate via
`t.confidence(villain)` (0.2–1.0, inverse-Herfindahl collapse protection).

**AP1 — podds_guard v2 (tracker range) [highest priority]**
Goal: attack journal leads `call_unter_pot_odds` (top severity 112/99/96/92 bb, all river, eq 0.00
vs needed 0.23–0.31) with legal information; the uniform range was too coarse
(NEUTRAL +0.31 ± 0.31, n=800).
Files: `pokerbot/autogym/improver.py` (new factory `tracker_podds_guard`); read-only:
`range_tracker.py`, `equity.py`.
Mechanics: only river + `to_call>0` + `confidence ≥ 0.5` (otherwise no override); fold if
`eq_weighted + margin < equity_needed_to_call(pot, to_call)`; keep margin 0.02.
Expectation (pre-registered): ANWENDEN = bb100 − 2·SE > 0 at n=800 decks. Second NEUTRAL ⇒
family "river-call guard" exhausted, journal entry, continue with F leads (mdf_flop
OVER-FOLD 0.61 vs 0.32 is the larger documented finding).
Runtime: locally ~3–5 min (1,600 hands; tracker build only at river-call nodes); pod: <1 min.
Deps: none.

**AP2 — MDF/alpha pair per sizing bucket (W1-4+5)**
Goal: refine `facing_bets` from per-street to per-(street × bucket [0.33, 0.66, 1.0, 1.5, ∞])
+ alpha check from the bettor side (mutual verification).
Files: `oracle.py` (`finalize_frequencies`; extend `facing_bets` by the bettor row),
import Fraction anchors from `tests/test_math_suite.py` (finding 6, section 1).
Expectation: identity alpha + MDF = 1 exact per Fraction (self-test PASS); the existing
mdf_flop finding must decompose per bucket without vanishing (sum consistency);
N_MIN 30 per bucket.
Runtime: +0 s (pure aggregation); validation run 900 hands ≈ 75 s locally.
Deps: none.

**AP3 — Quantify F severity (W1-11)**
Goal: `fold_frequency_exploit_ev` / `exploit_fold_deviation_ev` fill `severity_bb` of the
F verdicts (today hard 0.0) — makes F leads prioritizable against L leads.
Files: `oracle.py`.
Expectation: zero exactly at f = alpha (Fraction); anchor 0.7·100 − 0.3·50 = 55; on the
reference run mdf_flop gets severity_bb > 0.
Runtime: +0 s. Deps: AP2 (same data basis, sensible together).

**AP4 — Raise-node alpha/MDF (W1-6)**
Goal: own band for `node_typ='raise'` — the wired MDF band covers only bets; raises
have their own alpha geometry (`required_fold_fraction_for_raise`,
postflop_formulas.py:82).
Files: `oracle.py` + record field `node_typ` at both call sites (HU from
history/current_bet, 6-max from obs — wave-1 field, no engine rebuild).
Expectation: 300/(300+150) = 2/3 exact per Fraction; identity with
`breakeven_fold_equity_pure_bluff`; own RAISE_N_MIN 30 (raise nodes are more thinly populated
— below n=30 no judgment).
Runtime: +0 s. Deps: AP2 (bucket machinery is shared).

**AP5 — River ratio + pool bluff fraction (W1-7+8)**
Goal: classify every hero river bet in hindsight via villain_hole as value (eq>0.5) / bluff;
aggregated ratio per sizing bucket vs B/(P+B); mirror-wise the
bluff fraction of the BETTOR vs q* = B/(P+2B) (`bluff_catcher_call_ev`) → over-fold/
over-call proposals for the defender side. HU-only.
Files: `oracle.py`.
Expectation: B=P ⇒ bluff share 1/3 (docstring anchor); chain q=B/(P+2B), r=B/(P+B) per
Fraction (pinned in test_math_suite, import); RATIO_BAND 0.15, Q_BAND 0.10, N_MIN 30,
VALUE_EQ_SCHWELLE 0.5 fixed (no tuning knob).
Runtime: +a few s (equity only at river-bet nodes). Deps: AP2 (buckets).

**AP6 — Commitment + setmine (W1-9+10)**
Goal: `commitment_margin_by_spr` (fold despite eq ≥ spr/(1+2spr)+margin; stack-off far
below) + `set_mining_implied_odds_margin` (pocket-pair call preflop with eff/call <
threshold — runs HU AND 6-max, no villain_hole needed).
Files: `oracle.py`; the field `effective_stack` is already logged at BOTH call sites
(gym_hu.py:48, gym_six.py:50) — pure oracle work.
Expectation: Fraction identity S/(P+2S) = spr/(1+2spr) = equity_needed_to_call(P+S, S);
setmine anchor call 2 / eff 30 / sf 0.8 ⇒ exactly 0 on the threshold; SETMINE_FAKTOR 12
[10, 15].
Runtime: +0 s. Deps: none.

**AP7 — verify_expr runner ($0, immediately)**
Goal: execute the 66 ready-made `verify_expr`/`verify_value` pairs from
`knowledge_base/postflop/strategy_calc_verified.json` by machine — the largest
unused verification net of the repo (section 1, finding 2).
Files: new `pokerbot/autogym/verify_runner.py` (~30 lines) + call in the self-test (E1 extension).
Expectation: 66/66 PASS or a documented reason per exception; `reverse_implied_odds`
(verified:false, defective dataclass decorator) stays excluded until the code fix.
Runtime: seconds. Deps: none — **executable before everything else.**

**AP8 — MESS level: check the gate SE itself**
Goal: secure the most expensive unchecked number of the system — ANWENDEN > 2·SE hangs on the
SE computation of `duplicate_ab`. Closed form of the paired sample variance per Fraction
on constructed data + SE(n) ~ 1/√n over n = 100/400/1600; prospectively connect the
variance statistics from `mathematics_of_poker.json` (443 entries).
Files: `selftest.py` (new expectation E7/MESS), read-only `pokerbot/benchmark/duplicate.py`.
Expectation: agreement < 1e-12; a FAIL here devalues ALL previous gate verdicts →
hence BEFORE the next gate (G3).
Runtime: seconds. Deps: none.

**AP9 — Wave 2: hand_id / hand_result / line history**
Goal: extend the record schema by `hand_id`+`decision_idx` (linkage), `hand_result` (net bb,
showdown, winner) and `line` (action sequence per street) → implied-odds family
(`implied_odds_extra_needed`, `call_ev_with_implied_gain`, `reverse_implied_odds` as
aggregate), empirical `equity_realization` (knob calibration instead of prior),
check-raise family; plus the dedupe fix in the improver (mirrored passes, G7).
Files: `gym_hu.py`, `gym_six.py` (call sites), `oracle.py`, `improver.py`.
Expectation: G1 green with extended schema; first quantified implied-odds lead on the
reference run; journal without duplicates.
Runtime: schema +0 s; new aggregations a few s. Deps: AP2–AP6 (aggregation machinery).

**AP10 — equity_vs_hands + multiway L (+ ICM gym as follow-on)**
Goal: `gym_six` today logs `villain_hole=None` (gym_six.py:48), although the table knows ALL holes
— with `equity_vs_hands` (multi-opponent MC, ~20 lines in `pokerbot/engine/equity.py`)
the complete L level becomes multiway-capable. Then ICM gym (section 1, finding 3A:
Σ-ICM invariant as HART, `icm_call_ohne_odds` as L) on `arena/tourney.py`.
Files: `equity.py`, `gym_six.py`, `oracle.py`; ICM: new `pokerbot/autogym/gym_icm.py`.
Expectation: multiway lead rate in the order of magnitude of the HU rate (plausibility anchor);
ICM-HART = 0 on the paired SNG arena.
Runtime: MC cost ~n_opponents-fold at L nodes; pod run R4. Deps: AP9 sensibly beforehand.

---

## 5. VERSIONING

1. **Basis-tag rule:** before EVERY change, freeze (currently tag `autogym-basis`).
   Every candidate with a local ANWENDEN is measured PAIRED against the frozen basis bot
   (E6) — never against a moving state.
2. **Naming only on ANWENDEN:** a changed bot gets a name (git tag)
   exclusively if the paired gate vs basis says ANWENDEN (effect > 2·SE AND not
   below −1 bb/100). NEUTRAL/VERWERFEN produce journal entries, no names. The named
   bot carries its paired number in the tag/journal text.
3. **Journal obligation:** nothing happens silently — every round, every proposal, every verdict →
   `data/autogym/journal.jsonl`. Pod runs write their journal on the pod and it is scp'd back BEFORE
   the kill. Every gate entry carries the config fingerprint (git commit +
   knob values + flags — lesson: the old fingerprint missed 13 flags).
4. Oracle knobs remain measurement configuration (locked for the improver); every manual turn
   needs justification + journal entry (Goodhart protection, safety contract point 2).

---

## 6. WHAT CAN TIP THE PLAN (honestly)

1. **E5 scaling fails.** Proven are 580 hands/min single-process; the ≥10,000/min on
   64 cores are an ASSUMPTION (multiprocessing scaling). If G5 fails locally or R1 on the
   pod (< 60% of target), the whole pod calculation is moot — then optimize locally
   (process pool, EQ_ITERS budget, tracker memoization), do not throw budget after it. Loss
   then: ~$2 pilot.
2. **The measurement channel is too insensitive for rare nodes.** podds_guard fires only at
   river-call nodes — rare events × small effect = effect < SE despite real
   improvement. A second NEUTRAL at AP1 can therefore also mean "channel too coarse", not only
   "family empty". Countermeasure (then retrofit pre-registered): measure the fire rate first;
   paired evaluation ONLY over hands in which the guard fires (variance reduction on the
   treatment nodes).
3. **Self-play blindness.** All gates measure new-vs-old bot in self-play. A guard
   can be self-play-NEUTRAL and still win/lose vs GTOW — the doctrine
   deliberately defers GTOW, but the final truth about the staircase
   (−19.70 → −15 → −10) comes only from the GTOW measurement. The risk is priced in, not gone.
4. **Hindsight bias + seesaw danger.** L leads compare against the ONE actual
   opponent hand; guards that force folds too aggressively from that make the bot more readable
   (v8 lesson: flattening the mixing broke live to −58). Every guard therefore needs the
   gate AND the question: does it reduce unpredictability?
5. **Pair-drift anomaly.** Positive drift twice in a row (1.5 SE each) — still PASS. If a
   real seat asymmetry is confirmed, the SE assumptions of the gates are violated; pre-registered
   trigger: third positive run ⇒ investigation BEFORE further pod consumption.
6. **Orchestration risk 8 pods.** Multi-pod handling in `infra/runpod_run.py` is
   unbuilt; an error there (hanging pod, lost journal) eats budget. Countermeasure:
   R1 contains the orchestration smoke; results BEFORE kill; atexit+finally kills; check the console
   for larger CPU instances (1 pod beats 8).
7. **Price/availability drift.** The table is as of 2026-08 (list prices); verify in the console before every
   deploy. Secure Cloud may be sold out; Community Cloud
   stays taboo regardless (preemption destroys paired runs).
8. **Formula foundation.** If the verify_expr runner (AP7) or the MESS level (AP8) fails,
   part of the previous verdicts is in question — hence both run BEFORE the next gate and
   BEFORE the pod. That is the cheapest point of the plan at which it may tip.

Sources (prices): [RunPod Pricing](https://www.runpod.io/pricing) ·
[getdeploying RunPod](https://getdeploying.com/runpod) ·
[RunPod CPU types (docs)](https://docs.runpod.io/flash/configuration/cpu-types) ·
[Flexprice RunPod Guide](https://flexprice.io/blog/runprod-pricing-guide-with-gpu-costs) ·
[Spheron H100 2026](https://www.spheron.network/blog/runpod-h100-pricing-2026/)
