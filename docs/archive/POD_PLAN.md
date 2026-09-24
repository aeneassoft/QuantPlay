# Pod-Launch Plan — the foundation before we spend GPU

**Core principle (both OpenAI + Claude converged on it):** in any self-improvement system the
**SELECTOR** (the fitness function) decides the outcome; everything else — neural policy, DCFR,
self-play, Haiku/MiMo, prior-tuning — is just a **PROPOSER**. A strong proposer with a weak/slow
selector optimises confidently in the *wrong* direction. **So: harden the selector first, validate the
loop on CPU, only then switch on GPU.**

## STATUS — B200 pipeline VALIDATED (2026-06-14), pod killed; building the measured run
**Validation success:** a RunPod **B200** ran the full stack — required `pip install -U torch
--index-url .../cu128` (→ torch 2.11+cu128; the image's torch 2.4 is too old for Blackwell sm_100,
CUDA ops fail otherwise) + `dm-tree` + `open_spiel`. `deep_cfr_nlhe.py` ran universal_poker fcpa
Deep-CFR self-play on CUDA, **~18 s/iter @1000 traversals** → a meaningful run = 1–5 h. Killed after
(~$2.5; $5.89/h).
**Honest gap → don't train blind:** the on-pod eval (vs check-call) is too noisy to measure GTO quality.
Before a multi-hour run, build the MEASURED-run pieces, then relaunch:
1. **Distillation driver** (net imitates TexasSolver GTO — the compute-efficient path) +
2. **TexasSolver-Linux + the GTO-benchmark scoring the net ON the pod** (the selector; fast on the
   pod's 192 CPU cores).
Relaunch is ~2 min: `runpod_run --launch --fast` + the torch-cu128/dm-tree/open_spiel install (`../../infra/serverless/pod_bootstrap.sh`).

### 30-min measured run — BUILT + VALIDATED locally (awaiting GO)
Fast path for 30 min = **distillation** (not blind self-play), Claude-Opus actively directing:
- `strategy/distill.py` — features + 5-bucket GTO targets + small policy net + **warm-start** training +
  distributional **TV-gap selector** (not gameable) + `solve_focus_spots` = live curriculum (solve more
  boards in the director's focus classes, parallel on the 192 cores).
- `coach/meta_coach.py::direct_run` — **Claude-Opus** reads gap-by-spot-class each round → focus + lr/epochs.
- `extraction/pod_run30.py` — the time-boxed orchestrator. Local 2-min smoke: gap fell **17.3% → 16.8%**
  under live Opus direction (plateau = only 14 local boards; the pod's curriculum + thousands of solves go
  lower). `translate.py` = engine↔language bridge for the LLM.
**Deploy (on GO):** `runpod_run --launch --fast` (B200) → on pod: `pip install -U torch --index-url
https://download.pytorch.org/whl/cu128; pip install dm-tree open_spiel treys`; scp `pokerbot/ extraction/
data/_gto_bench_cache/` + TexasSolver-**Linux** (set `TEXASSOLVER_DIR`); export `ANTHROPIC_API_KEY`
(Opus director); `python -m extraction.pod_run30 30 16 64`; then `runpod_run --kill`. (~35 min ≈ ~$4.)

### Pre-validation status (still valid):
- **(a) CPU dry-run loop WORKS** (Tier-1 mechanism validated): propose→eval→accept lowered the GTO-gap
  **19.8% → 14.8%**, match 87% → 94%. BUT it **gamed the proxy** (drove to donk 0% / c-bet 99% =
  exploitable extremes). Two lessons, empirically confirmed: (1) the modal bet/check selector is
  GAMEABLE → the real selector needs **distributional frequency-matching (TV/KL to GTO) + an
  exploitability gate** (the distributional part is cheap from the cached solves; the true-BR gate needs
  a BR tool — postflop-solver/custom). (2) A **deterministic** baseline tops out ~15% (it can't match
  GTO *mixing*) → the **stochastic neural policy is the only way below that = the pod's job.**
- **(b) `meta_coach.propose_exploit` built** — the in-loop recursive-ToM hypothesis generator
  (engine-agnostic; emits a JSON node-lock directive; solver/benchmark verifies before use). On-pod LLM
  = a **small 7-14B** (one GPU) or API Haiku — NOT MiMo-V2-Flash (**309B/15B-MoE → ~8 GPUs**) or Kimi (1T).
- **GPU spec (strongest available):** **B200** 180GB **$5.98/hr** (B300 288GB not self-serve-priced yet);
  **H200** 141GB **$3.59/hr** = ample + cheaper. A **single** GPU + high vCPU fits net + small-LLM +
  TexasSolver(CPU); we do NOT need a multi-GPU node. Launch: `python -m extraction.runpod_run --launch --fast`.
- **Pre-GO hardening (the one real blocker the dry-run exposed):** upgrade the selector to
  distributional + add the exploitability gate, so the pod net can't game the proxy.

## The engine (what the pod actually runs)
**Self-play mutual exploitation → GTO.** Theory: in 2-player zero-sum the time-average of mutual
no-regret/best-response play converges to Nash (Robinson 1951; CFR/NFSP). So our *exploitation strength
becomes the GTO-solving mechanism*. Discipline that makes it converge (not cycle): best-respond to and
**output the AVERAGE** strategy, regularised/smoothed (NFSP/DCFR), never the raw last iterate.
- Seeded by **distillation** from the TexasSolver GTO-oracle (cheap, fast GTO-gap reduction) +
  **analytic priors** (Chen/MDF) as initialisation + KL-soft-regulariser with **constraint-annealing**
  ("engine warming up": start theory-bound, loosen as the benchmark earns it).
- Exploit head = small RL layer, **KL-bound to the GTO policy = the exploitability budget**.
- **AI on the pod** = the π_θ policy+value net (this engine) + **Haiku/MiMo as meta-coach** (proposes
  hyperparams / curriculum / node-lock targets *between* runs only — never mid-run objective changes).

## Substrate
**OpenSpiel = the "Qiskit for game theory"** — use it for algorithm reference + Leduc/Kuhn validation
(we already validated Deep CFR there). But our **TexasSolver + abstraction + evaluator IS the real
NLHE engine**; build a thin OpenSpiel-inspired NLHE interface on top, not from scratch.

## Launch checklist — Tier 0 → 1 → 2
**Tier 0 — eval integrity (BLOCKER, no launch without it):**
- [x] Selector API: `gto_benchmark.evaluate(policy) -> {gap, per-role bet-freqs}` — deterministic, cached, sub-second.
- [x] Baseline params exposed as tunable priors (`GTOBaseline(params=...)`).
- [ ] Exploitability gate (v1 = GTO-gap as the proxy; v2 = true best-response value — needs a BR tool: postflop-solver/custom BR).
- [ ] Spot-set fixed + versioned (currently 14 seed-7 flops @ SPR 5; expand + add a Haiku-mined "hard-spot set").

**Tier 1 — validate the loop on CPU (before GPU):**
- [x] `benchmark/improve.py` = the propose→eval→accept dry-run (grid/coordinate search over priors).
- [ ] **Prove it lowers the GTO-gap** end-to-end on the baseline. (Runs the moment the cache is full.)
- [ ] Freeze the state-encoding (public obs + card bits + suit pattern + blocker counts).

**Tier 2 — pod-specific (the new thing):**
- [ ] Small on-pod π_θ net (policy+value), same encoding, scored by the SAME selector.
- [ ] DCFR / self-play update loop over subgame-resolved CFVs; value-net bootstraps the subgame leaves
      (the proven shortcut: re-solve + abstraction + value-fn + SPR + DCFR).
- [ ] Haiku/MiMo meta-coach hook (same interface as the CPU loop).
- [ ] Pod spec: GPU (net) **+ many vCPUs** (TexasSolver is CPU-bound) + cost-cap + auto-kill + checkpoints.

## Parked (deliberately, to not split focus)
- Full ReBeL belief-search; DeepNash/R-NaD model-free branch; LLM-ToM as a *loss* signal; 6-max/multiway
  (do clean 2p zero-sum first — only there does the no-regret→Nash guarantee hold).
- Recursive-ToM-on-hand-histories = **offline hard-spot miner only** (Haiku marks tough nodes → solver
  verifies CFV-sensitivity → weighted into the spot-set). Feeds the benchmark, not the hot loop.

## Honest status
Foundation is ~Tier-0/1 complete in code; the gate is *proving the CPU loop drops the gap* + populating
the cache. The −100 vs Slumbot is the missing floor; this pipeline is exactly the cure (a measurable,
selector-driven floor + a bounded exploit head).
