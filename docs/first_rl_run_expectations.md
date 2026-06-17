# First RL run — what it should SHOW us (expectations + live mid-check)

**Run:** `python -m infra.runpod_rl_campaign` (self-killing, ~40–60 min, H100/H200). **Watch:**
`python -m pokerbot.web.train_dashboard --open`.

**The ONE question this first job answers:** does the WHOLE pipeline run end-to-end on the pod (provision → setup →
preflight → SFT → GRPO → eval → pull → kill) WITHOUT crashing, and are the GRPO metrics SANE? It is an **integration +
sanity proof**, NOT a finished model or a bb/100 win (that needs the later scale run). Costs ~$15–30.

## Per-stage expectations vs alarms
| stage | EXPECT (healthy) | ALARM (distrust / investigate) |
|---|---|---|
| **provision/setup** (A,B) | `launched … H200/H100`; bundle ~3 MB; `RL_SETUP_OK` (torch/trl/vllm import) within ~15 min | no GPU available; `pip` errors; setup > 15 min |
| **C1 preflight** | `PREFLIGHT1_OK`; GPU named; `GRPOConfig(loss_type=dapo…)` constructs; 1-state `ev_reward` a finite bb | `PREFLIGHT1_FAIL: …`; `TypeError` on GRPOConfig (trl API drift → re-pin trl); CUDA missing |
| **SFT (short, MAXN=1500)** | loss trends ↓; **PokerBench-acc ~50–68%** — LOWER than the 71.7% full-ckpt is EXPECTED (1500 ≪ 60000 rows); DSL-emit high | loss flat/NaN; acc < 40% |
| **C2 probe** | `STEP_TIME_S=…` printed; `SAVED GRPO adapter`; no vLLM OOM | OOM (lower `VLLM_MEM`); probe crashes (GRPO integration bug) |
| **GRPO (core, dashboard)** | `reward` slightly ↑ / stable-positive (NO big jump in ~tens of steps); **`frac_bad` < 0.1** + stable/↓; `frac_reward_zero_std` 0.1–0.5; `reward_std` > 0 (groups have learnable variance); `completions/mean_length` stable; `entropy` not → 0; `step_time` fits the budget | `reward` collapsing toward −10; `frac_bad` > 0.2; `reward_std` ≈ 0 everywhere; length exploding; `entropy` → 0 |
| **prior-suppression** | **`engine_grounded_rate` RISES** over steps (deriving via `api.*`, not gut); `frac_bad` stays low = math/code intact | api-call-count exploding (reward-hacking the shaping); grounded-rate↑ but `reward`↓ (gaming); `frac_bad`↑ = math/code forgetting |
| **eval** | bb/100 vs held-out league (NOISY at 300 hands → wide CI); **Δ vs SFT-init ≈ 0 to slightly ±** (tens of steps won't lift it — the THESIS lift needs the scale run); G0 may FAIL (short SFT), **G1 legality PASS** | Δ strongly negative (big regression); legality < 90% |

## Concrete numeric priors (so we can tell signal from noise)
- **Step time:** likely 5–20 s/step (reward = 32 completions × 6 rollouts × a full hand-sim, CPU-bound). The WallClockStop
  guarantees the budget regardless; expect ~tens of GRPO steps (NOT hundreds) in this first run.
- **Reward scale:** per-decision EV in bb, clipped ±25; the engine-grounded shaping adds ≤ ±1 bb (decaying). Group means
  typically single-digit bb; `R_BAD = −10` for malformed output.
- **frac_bad at start:** should be LOW (SFT warm-start emits `decide(...)`); if STRUCTURED stayed on, ~0.
- **Δ vs SFT-init:** treat |Δ| < ~5 bb/100 at 300 hands as NOISE (SEM is large); direction matters more than magnitude.

## PASS criterion for THIS job
**All stages COMPLETE without crashing + `frac_bad` low + `reward_std` > 0 + no reward collapse + a gate-ladder JSON
produced.** = the pipeline + reward signal are proven on real hardware. A bb/100 win is NOT the bar here — it is the goal
of the subsequent, longer scale run (more SFT, more GRPO steps, the held-out gate ladder at full `EVAL_HANDS`).

## The ~3-min alive-check
By T+3 min the orchestrator stdout should show, in order: `launched … H200` → `bundle … MB -> pod` → setup running /
`RL_SETUP_OK` → `PREFLIGHT1_OK`. The dashboard's `data/training_metrics.jsonl` starts filling at GRPO step ~5 (the live
heartbeat). If stdout is silent past ~3 min or a stage prints a FAIL marker → `python -m infra.runpod_run --status` then
`--kill` (the run also self-kills via finally+atexit).
