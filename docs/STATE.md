# PROJECT STATE — start here (for a fresh Claude session)

> Living entry point. Read this first, then [CLAUDE.md](../CLAUDE.md) for conventions. Last updated **2026-06-14**.
> The cross-session memory lives at `C:\Users\hampe\.claude\projects\C--Users-hampe-Desktop-PokerB\memory\` (index: `MEMORY.md`).

## What this is
A Heads-Up **and** 6-max No-Limit Hold'em bot grounded in three poker books, a browser app to play it, an
online opponent-exploiting layer, and tooling to measure our play against true GTO. North star: a
**universal adaptive exploiter** — a low-exploitability baseline + an online opponent model that detects and
safely exploits each opponent's leaks (confidence-gated), built to handle opponents we haven't seen yet.

## ★ Latest session — Consolidation & Unification (2026-06-14, supersedes older detail below)
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
- **Next:** Phase 1 — wire `unified.json` as the bounded overlay (Build A) + re-test the edge (duplicate-gated)
  → Phase 2 — the self-play→GTO net on RunPod (the Supremus/Pluribus recipe), warm-started by solver data.

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
