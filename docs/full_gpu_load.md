# Full-GPU-load — saturating a mega GPU during GRPO (size-agnostic)

**Goal (user, 2026-06-17):** when we rent a mega GPU we must FULLY load it — compute *and* vRAM — and do "stuff that
only works with a mega GPU." Training must be **size-agnostic** (prefer Qwen3-8B; fall back to 32B / 70B). This doc is
the plan + the knobs (all env-driven; one `infra/runpod_rl_campaign.py` serves smoke + scale via `SCALE=1`).

## The honest bottleneck: it is NOT the GPU
During GRPO the step is `generate (vLLM, GPU, fast) → reward (CPU self-play rollouts) → optimize (GPU)`. The reward is
`GEN_BATCH × K_ROLL` hand simulations **per step**. Done sequentially on one core it **starves the GPU** — the GPU
sawtooths to ~0% while the CPU computes the reward. So the FIRST lever for GPU utilization is not a GPU knob at all.

## The three levers

### Lever 1 — parallelize the reward (the prerequisite) · `REWARD_WORKERS`
The reward is embarrassingly parallel (each completion's EV is independent). `training/qwen_grpo.py` now fans the heavy
rollout pass across a persistent **spawn** process pool (`REWARD_WORKERS` = pod `nproc − 2`). Workers are lean (re-import
pulls **no torch** — torch is imported only inside the GPU fns) and pure-CPU (no CUDA-fork hazard).
- **Measured locally (24 vCPU):** sequential 10.4s/step-reward → **2.1s at 8 workers (~5×)**; scales with cores. A
  64-core pod ⇒ the reward stops being the wall.
- **Correctness:** the parallel reward is **byte-identical** to sequential — verified. This required two real fixes that
  also harden the pipeline:
  1. **CRN the hero continuation.** The cont-bot's mixing RNG was *unseeded* and its per-hand state *leaked* across
     rollouts (it never got `new_hand`). `rollout_action_ev` now resets + deterministically seeds it per rollout →
     each rollout is an independent fresh hand and the reward is reproducible.
  2. **`PYTHONHASHSEED=0`.** Card-string `set`/`dict` iteration order is per-process randomized; the equity sampler
     drew different runouts under different hash seeds. Unfixed, **different reward workers would disagree → a GRPO
     group's completions (split across workers) would not be CRN-comparable.** `main()` re-execs once to pin it; the
     pool also pins it for workers. (This made the *whole* RL/eval pipeline non-reproducible run-to-run before — now fixed.)

### Lever 2 — fill vRAM with the vLLM KV cache · `VLLM_MEM`
vLLM expands its KV cache to `vllm_gpu_memory_utilization` of the card. Higher ⇒ more concurrent sequences ⇒ higher gen
throughput ⇒ more vRAM used. Scale default `VLLM_MEM=0.78` (smoke 0.45). The probe (stage C2) runs at the real
`VLLM_MEM` so colocate-OOM surfaces on 12 states, not mid-run. Bigger `GEN_BATCH` (scale=256) is what actually *fills*
that KV cache.

### Lever 3 — fill compute: model size + batch · `BASE`, `GEN_BATCH`, `PD_BATCH`, `NUM_GEN`
An 8B QLoRA **underutilizes** an 80GB H100/H200's compute. Two ways to load it:
- **Bigger batch / group** (`GEN_BATCH`, `PD_BATCH`, `NUM_GEN`) — more sequences in flight, more matmul per step. Cheap,
  keeps 8B. This is how we fill the 8B's spare capacity.
- **Bigger model** (`BASE=Qwen/Qwen3-32B` or `-70B`) — QLoRA nf4 + `target_modules="all-linear"` is already
  size-agnostic, so the *only* change is the env var. 70B-QLoRA genuinely fills an 80GB card's compute + vRAM.
  **Preference: 8B** (cheaper, faster thesis iteration); the size knob is ready when a bigger model is justified.

## Size-agnostic — what makes it true
- **Model:** `BASE` env + QLoRA (nf4, double-quant) + `target_modules="all-linear"` (no per-size module list) in BOTH
  `qwen_sft.py` and `qwen_grpo.py`. 8B / 32B / 70B differ by one env var.
- **Reward/env:** pure CPU, model-independent — identical at any size (and it's the part that scales with the pod's cores,
  not the GPU).
- **Throughput knobs** (`GEN_BATCH`, `PD_BATCH`, `VLLM_MEM`) are env-driven, tuned per (GPU, size). Rule of thumb: bigger
  model ⇒ less KV room ⇒ **lower** `VLLM_MEM` (e.g. 8B→0.78, 32B→0.6, 70B→0.4) and smaller `PD_BATCH`; the C2 probe is
  the empirical OOM check before the long run.

## How to run
```
# smoke (default, ~40-60 min, 8B): python -m infra.runpod_rl_campaign
# full mega-GPU load (8B, big batch + parallel reward + vRAM-fill):
SCALE=1 BASE=Qwen/Qwen3-8B python -m infra.runpod_rl_campaign
# 70B to truly saturate compute (lower VLLM_MEM/PD_BATCH):
SCALE=1 BASE=Qwen/Qwen3-70B VLLM_MEM=0.4 PD_BATCH=4 GEN_BATCH=128 python -m infra.runpod_rl_campaign
```
`SCALE=1` flips: `HARD_CAP_S` 1h→6h, `VLLM_MEM` 0.45→0.78, `N_STATES` 120→2000, `K_ROLL` 6→16 (affordable now the reward
is parallel), `GEN_BATCH` 32→256, `PD_BATCH` 8→16, `MAX_STEPS` →uncapped (WallClockStop is the guard), `EVAL_HANDS`
300→1000. All individually overridable.

## Verification (empirical, not assumed)
- **`data/gpu_load.jsonl`** — the `_sample_gpu_load` daemon polls `nvidia-smi` every ~10s (util% + vRAM frac). Full load
  = `util` stays high (not sawtoothing to 0 between steps) and `mem_frac` near `VLLM_MEM`+model. This file is the proof.
- **C2 probe** prints `STEP_TIME_S` at the real settings and canaries colocate-OOM before the long run.
- The dashboard (`pokerbot/web/train_dashboard.py`) streams reward/frac_bad/grounded-rate/step_time live.

## Gates before spending (unchanged discipline)
A green LOCAL delta (mixed+read+solver data improves Slumbot/exploitability vs the −72 baseline) + the user's $-go gate
the pod scale run. The 8B is the real model; the 1.7B local run de-risks the pipeline. `--kill` always after (atexit+finally).
```
```
