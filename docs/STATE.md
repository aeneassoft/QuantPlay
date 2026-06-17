# PROJECT STATE — start here (for a fresh Claude session)

> Living entry point. Read this first, then [CLAUDE.md](../CLAUDE.md) (north star + conventions) + [INDEX.md](../INDEX.md) (live repo tree). Last updated **2026-06-17**.
> The cross-session memory lives at `C:\Users\hampe\.claude\projects\C--Users-hampe-Desktop-PokerB\memory\` (index: `MEMORY.md`).

## ★★★ CURRENT (2026-06-17) — ★ 6-max GTO Qwen brain. SFT proof PASSED (reasoning-loop DSL, frac_bad→0); REWARD PARALLELIZED for full-GPU-load (~5×, byte-identical); Pillar-2 SOLVER DATA pipeline live; Qwen3-8B pod scale prepped (SCALE=1, size-agnostic), gated on a $-go.
> ⟳ LIVE source of truth. Per the CLAUDE.md standing rule, update THIS top section before ending any turn that moves
> the headline, lands a build, or shifts priorities. Plan: `.claude/plans/gut-dann-sind-wir-toasty-forest.md` ·
> `docs/QWEN_6MAX_PLAN.md` · `docs/DATASET_SPEC.md`.

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
> 8B/32B/70B, QLoRA nf4 + all-linear). Design: `docs/full_gpu_load.md`.
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
> **★ RunPod final prep (2026-06-17): `docs/RUNPOD_READY.md`** — launch cmds (smoke/scale/70B), the GATE ladder, the
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
**★ MATH ACCURACY (2026-06-17, user-prioritized).** Strategy `docs/math_accuracy_strategy.md` (4 papers + repos:
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

**★ SOLVER-GRAFTED PREFLOP (2026-06-16, user-chosen "schneller+genialer" lever) — built + first GATE PASS.** Preflop is
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
**3.3 vs 234**, A3 range-L1 **+60% turn**. Pro-hands (`extraction/pro_hands_profile.py`) catalogued = NLHE 7-max PKO
MTT (NOT cash) → exploit ARCHETYPE only (29/20, 9.5% 3bet, AF 2.26). RunPod: **0 pods live** (verified, no billing).
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
  suggested. **→ PLAN: [docs/MVP_UNIFY_PLAN.md](MVP_UNIFY_PLAN.md).** Catalog DONE ([BOT_PARTS_CATALOG.md](BOT_PARTS_CATALOG.md);
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

**★ THE keystone — BUILT + integrated + unit-tested (2026-06-15, "Goldbach" session); EV-gate PENDING.** The
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
[GTO_GAP_REVIEW](GTO_GAP_REVIEW_2026-06-15.md) · [GTO_P0_RANGE_TRACKER](GTO_P0_RANGE_TRACKER_2026-06-15.md).

**Plan / spend:** [MVP2_RUNPOD_PLAN.md](MVP2_RUNPOD_PLAN.md) — closer-to-GTO sequenced by ROI. The $140 RunPod run
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
postflop", NOT "6+ solved"; measure via EV-gap + matched-tree BR/LBR, NOT MSE.** Tasks #78–80. Origin: the Goldbach
Movie-Factory run (`SD_6PLUS_GATE_LOG.md`).

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
**Plan:** [docs/CONSOLIDATION_PLAN.md](CONSOLIDATION_PLAN.md) · **Architecture:** [docs/META_STRATEGY.md](META_STRATEGY.md)
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

1. **GPU (RunPod B200): Qwen3-8B LoRA fine-tune on PokerBench** — [extraction/qwen_sft.py](../extraction/qwen_sft.py).
   The strategic/language layer (exploit hypotheses, coaching, curriculum), **not** a per-hand player.
   At step ~90/987 it was already 96% token-accuracy → converges fast; full 987 steps unnecessary.
   Output LoRA → `/root/qwen_poker_lora` (retrieve, then `--kill` the pod). Needs torch cu128 on Blackwell.
   - **HARD LESSON**: on ONE box a heavy CPU job and a GPU-training job cannot coexist (CPU starves GPU
     kernel-dispatch *and* sshd → unmanageable). "Both at 80%" needs **separate** pods. So:
2. **CPU (local i9-12900K): TexasSolver mass-solve** — [extraction/mass_solve.py](../extraction/mass_solve.py)
   (RAM-adaptive; 16 GB box → ~5 parallel solves, auto-scales). Builds a GTO cache for distillation/benchmark
   in `data/_gto_bench_cache/` (regenerable; gitignored). ~16 boards/min.
3. **Claude API: exploit playbook** — [extraction/exploit_playbook.py](../extraction/exploit_playbook.py).
   Bounded, machine-checkable exploit directives across an opponent-profile × spot grid (a PROPOSER pass;
   the benchmark verifies before anything is applied). Artifacts:
   - `knowledge_base/exploit/playbook.jsonl` — 11,520 directives (Haiku).
   - `knowledge_base/exploit/playbook_opus_coarse.jsonl` — 240 directives (Opus, high-quality subset).

## What the GTO cache already tells us (from [extraction/analyze_cache.py](../extraction/analyze_cache.py), 597 flops)
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
- **GTO-floor net v0 (distillation)** ([extraction/distill_improve.py](../extraction/distill_improve.py)) on the
  1340-board solver cache (local RTX 3080 Ti): added minibatching to `distill.train` (full-batch underfit
  328k samples); 256³ net → held-out **TV-gap 17.7%→17.0%**, saved `data/floor_net.pt`. **KEY FINDING
  (empirically validated, not just taken from the OpenAI tips): bigger nets barely move it → the bottleneck is
  DATA COVERAGE, not the model.** Vetted OpenAI (gpt-5.1) advice via [extraction/cfr_tips.py](../extraction/cfr_tips.py).
- **Exploit playbook WIRED** into the adaptive engine as a cold-start prior ([pokerbot/strategy/playbook.py](../pokerbot/strategy/playbook.py)):
  nearest-profile lookup -> bounded, confidence-FADED nudge (bluff / value / bluff-catch); `directive_to_nudge`
  is the SAME channel the live LLM strategist will write into later. Tests: `python -m tests.test_playbook`.
- **LBR exploitability evaluator** ([pokerbot/benchmark/lbr.py](../pokerbot/benchmark/lbr.py)): a Local-Best-Response
  lower bound via rollouts with RE-SAMPLED hidden cards (no hidden-info cheat) + passive continuation.
  VALIDATED (crushes a nit +75+/-4 bb/100). v1 (uniform range) is a LOOSE bound -> too weak to find a leak in
  the baseline floor yet (LBR loses to it); v2 = Bayesian action-consistent range for a tight number.
- **Qwen LoRA fine-tune SAVED** (step-500, 97% token-acc) -> `models/qwen_poker_ckpt500/` (adapter 666 MB);
  pod auto-killed (billing stopped). The strategist layer for the INTEGRATION plan. **Eval PROVEN:** held-out
  PokerBench decision-match **base 18.3% -> LoRA 71.7% (+53pp)** ([extraction/qwen_eval.py](../extraction/qwen_eval.py)).
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
   policy floor (`cfr_policy.py`, see [INTEGRATION.md](INTEGRATION.md)). Methodology lab: validate CFR+ on the
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
- **Plans**: [docs/ROADMAP.md](ROADMAP.md), [docs/POD_PLAN.md](POD_PLAN.md), [docs/RUNPOD_PLAN.md](RUNPOD_PLAN.md).

## Infra notes
- Keys: read from `C:\Users\hampe\Desktop\Secret keys\` (outside the repo) via [pokerbot/config.py](../pokerbot/config.py) — never hardcode.
- RunPod: `--kill` = `DELETE /pods/{id}` = full terminate (compute+storage billing stops). A mere "stop" still
  bills storage. SSH key `C:\Users\hampe\.ssh\pokerb_runpod`; fresh pods get a NEW ssh port (read `--status`).
- Models: Claude `claude-opus-4-8` (quality) / `claude-haiku-4-5` (cheap in-loop); OpenAI auto-resolves to `gpt-5.1`.
