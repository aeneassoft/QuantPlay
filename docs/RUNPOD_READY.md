# RunPod job — final readiness checklist (2026-06-17)

The one self-killing pod run: **DSL-SFT (on the corrected gold) → DAPO-GRPO → GTO-anchored eval → pull best adapter →
`--kill`.** Size-agnostic, full-GPU-load. Gated on a user $-go. Orchestrator: `infra/runpod_rl_campaign.py`.

## Launch commands
```
# smoke (de-risk the whole pipeline on the pod, ~40-60 min, 8B, ~$15-30):
python -m infra.runpod_rl_campaign
# full mega-GPU-load scale run (8B, parallel reward + vRAM-fill + big batch; only after a green smoke):
SCALE=1 BASE=Qwen/Qwen3-8B python -m infra.runpod_rl_campaign
# 70B to truly saturate compute (size-agnostic; lower vRAM-util/micro-batch):
SCALE=1 BASE=Qwen/Qwen3-70B VLLM_MEM=0.4 PD_BATCH=4 GEN_BATCH=128 python -m infra.runpod_rl_campaign
# watch live:  python -m pokerbot.web.train_dashboard --open
# AFTER (mandatory): python -m infra.runpod_run --status   # MUST show NO tracked pods
```

## What ships (the tarball — `pipeline/orchestrate.build_tarball`)
`pokerbot/` + `dataset/` (incl. the GOLD shards: `a_contract.jsonl`, `c_decide.jsonl`, **`solver.jsonl`** = the local
TexasSolver mixes — the pod has no solver binary; CPU mass-solve is the PC-hub job per the 2-node split) + `training/`
+ `infra/` + the `knowledge_base` subset. Verify before firing: `python -c "from pipeline.orchestrate import build_tarball; print(build_tarball())"`.

## ✅ Done + verified (this session, $0 local)
- **frac_bad fix** (completion-only masking + reasoning-loop completions): the LLM emits valid DSL (0.97→0.00 local).
- **CORRECTED DATA PATH (critical):** the pod SFT now trains on the reasoning-loop + read + **solver** gold shards, NOT
  the old `local_kb.jsonl` (11.5k comment-only exploit/math = the original frac_bad cause). PokerBench (spine) auto-loaded, MAXN-capped.
- **Full-GPU-load:** reward parallelized (`REWARD_WORKERS`, ~5× @ 8 workers, byte-identical) — the prerequisite so the
  GPU isn't starved by the CPU reward; `PYTHONHASHSEED` pinned (CRN across workers) + hero-continuation CRN'd.
- **Size-agnostic:** `BASE` env + QLoRA nf4 + `target_modules="all-linear"` (SFT + GRPO). 8B/32B/70B = one env var.
- **Pillar-2 solver data:** `dataset/build/from_solver.py` → real GTO mixed-frequency DSL, grammar-valid + executable.
- **Campaign hardening (prior):** time-boxed stages + grep success-markers + WallClockStop + `--kill` (atexit+finally);
  C1 preflight (imports/CUDA/GRPOConfig/1-state-reward) + C2 probe (STEP_TIME_S + colocate-OOM canary at the real VLLM_MEM).
- **Live proof:** `data/gpu_load.jsonl` (nvidia-smi util%+vRAM, the full-load record) + the dashboard stream.

## The GATE ladder (go/no-go, in `training/qwen_eval_gto.gate_ladder`)
- **G0** PokerBench-acc ≥70% + DSL-emit ≥99%   · **G1** legality ≥99% (frac_bad low)
- **G2** RL mixed bb/100 > its SFT-init  = THE thesis test   · **G3** worst-case vs each held-out type ≥0 (robustness)
- **G4** LBR not worse (advisory)   · **G5** trace audit (manual: no degenerate collapse)
Eval is size-agnostic + reproducible (BASE + PYTHONHASHSEED via the train-env).

## Pre-flight (run on THIS box before spending)
1. `python -c "import infra.runpod_rl_campaign"` — imports clean ✅
2. `python -c "from pipeline.orchestrate import build_tarball; build_tarball()"` — tarball builds (incl. solver.jsonl)
3. RunPod API key present (`C:\Users\hampe\Desktop\Secret keys\`), SSH key `C:\Users\hampe\.ssh\pokerb_runpod`
4. `dataset/shards/{a_contract,c_decide,solver}.jsonl` exist (the gold) — they ship in the tarball
5. Fire smoke first; only scale on a green delta vs SFT-init.

## Honest caveats
- 8B on one H100/H200 underutilizes COMPUTE; we fill it via big batch + KV cache (vRAM) — true compute saturation = 32B/70B (size knob ready).
- The 1.7B local runs proved the PIPELINE; the 8B is the capacity (read-conditioning + API fidelity) + EV-lift validator.
- Prefer H100/H200 (B200 sm_100 kernels immature, ~10× slower unless verified +cu128).
