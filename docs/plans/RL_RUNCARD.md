# RL RUN-CARD — the single source of truth for a GRPO/DAPO run (poker brain)

Consolidates the RL book + the DAPO paper + the converged consults (`../consults/qwen_train_claude.md`, `../consults/qwen_train_gpt55.md`,
`QWEN_6MAX_PLAN.md`, `llm_curriculum.md`, `first_rl_run_expectations.md`) into ONE recipe + gates + alarms + de-risk
ladder. Verified against the actual `training/qwen_grpo.py`. Applies to Qwen3-8B AND the GLM-Z1-9B pivot (model-agnostic).

## The thesis (why RL at all)
SFT/distill = **warm-start only** — it caps at the teacher. PokerBench (2501.08328) confirmed it empirically ("simple
SFT has limitations → more advanced methods needed"); our own Qwen-on-PokerBench plateaued at ~71.7% action-accuracy.
**Only RL with a realized-EV reward lifts ABOVE the teacher.** `GATE 2` (RL > SFT-init in bb/100) IS the test of the
whole approach. RL is empirical — there is NO guarantee; we maximize P(lift), fail cheap, and gate on measured bb/100.

## The config — VERIFIED in `training/qwen_grpo.py` `make_config` (DAPO, native TRL)
| knob | value | why (source) |
|---|---|---|
| `loss_type` | `"dapo"` | token-level PG loss (DAPO) |
| `epsilon` / `epsilon_high` | 0.2 / **0.28** | **Clip-Higher** — decoupled clip preserves entropy / anti-collapse (DAPO) |
| `scale_rewards` | **False** | Dr.GRPO — no length bias (poker ≠ verbosity) |
| `beta` (KL) | **0.0** (env `BETA`) | DAPO: no ref model, RL diverges from the teacher. RAISE to ~0.04 only if collapse (see Tensions) |
| `mask_truncated_completions` | True | drop truncated rollouts from the loss |
| `num_generations` (G) | 8 (16 if throughput allows) | group-relative advantage; the variance-reduction structure |
| `learning_rate` | 1e-6, constant+warmup | RL lr is ~100× below SFT — non-negotiable |
| `temperature`/`top_p` | 1.0 / 1.0 | exploration in rollouts |
| `max_completion_length` | 384 | cap CoT; long rambles waste compute (+ frac_bad) |
| vLLM gen + `vllm_structured_outputs_regex` | on | only grammar-valid DSL programs are sampleable (`brain/dsl_grammar`) |

## The reward — engine realized-EV (VERIFIABLE → no reward model → no reward-hacking surface)
Per completion (`make_ev_reward`): parse → `run_program(strict)` → action.
- **bad** (grammar/illegal/no-decide) → `R_BAD=-3`. NOT −30: with ~50% bad, −30 swamped the EV signal (Dr.GRPO advantage
  = `R_i − mean(R)` → the ±33 valid/invalid gap dominated the ±5-bb EV spread → reward FLAT −17.6, the first-run failure).
  −3 (just below typical bad-EV) lets the **EV spread drive the advantage** — the load-bearing fix.
- **legal** → `clip(realized_EV, ±R_CLIP=25)` from `rollout_action_ev` + `R_FMT=2` (binary format edge) + a **decaying**
  engine-grounded shaping (`GROUND_B0=1` bb, → 0 over `GROUND_DECAY=200` steps, so realized-EV stays dominant + the truth).
- **CRN**: every completion of a prompt shares that prompt's `base_seed` → group-relative advantage isolates the ACTION,
  not card luck. The load-bearing correctness invariant (also: `PYTHONHASHSEED=0` across main + pool workers).
- **Opponent panel** = the `arena/sixmax` league (TAG/LAG/nit/station/maniac + frozen-SFT + earlier-RL ckpts). Diversity
  = robustness: 6-max has no Nash, a narrow panel → beats-panel-loses-world.

## Dynamic sampling (DAPO's biggest single win) — ours is a STATE-BUFFER proxy
DAPO: drop groups where all G rollouts get identical reward (zero advantage = wasted gradient) + oversample + refill.
Ours (`build_state_buffer`): keep only spots whose candidate-action EV-**spread** ≥ `spread_eps=0.5` (a learnable
decision), `oversample=1.5`, decontam vs the PokerBench test set. A PROXY done BEFORE rollout (TRL has no in-loop
post-rollout knob). **Monitor `frac_reward_zero_std`**; if it stays high, raise `spread_eps` (more-learnable states).

## GATE ladder (go/no-go)
- **GATE 0 — SFT sanity:** PokerBench-acc ≥70% (we hit 71.7%) ∧ frac_bad <10%. If RL doesn't START ≥70%, fix SFT first.
- **GATE 1 — RL not broken:** legality ≥99% after ~200 steps; frac_bad low + stable.
- **GATE 2 — RL LIFTING (THE CORE TEST):** bb/100 vs the frozen-SFT panel **> SFT-init** (+5 and rising). If RL can't
  beat its own SFT init, the thesis is failing → STOP + debug (reward variance? beta? stale state buffer?).
- **GATE 3 — robustness:** positive bb/100 vs EACH panel member (negative vs one = an exploitable hole).
- **GATE 4 — no leak:** LBR exploitability not catastrophically worse than the SFT init.
- **GATE 5 — no reward-hack:** read ~50 traces — coherent reasoning, NOT action-spam / folds-everything.
Select the checkpoint on **bb/100-vs-panel**, NOT PokerBench-acc (selecting on acc re-caps you at the imitation ceiling).

## Live alarms (the dashboard / `JsonlMetrics` keys)
| metric | healthy | ALARM → action |
|---|---|---|
| `reward` (± `reward_std`) | trends UP, not flat | flat/collapsing → R_BAD swamp / collapse |
| `reward_std` | >0 (learnable) | ≈0 everywhere → no signal |
| `frac_reward_zero_std` | 0.1–0.5 | →1 → dynamic-sampling failing → raise `spread_eps` |
| `frac_bad` | <10%, stable/↓ | >20% → broken generation |
| `entropy` | not collapsing | →0 → collapse → raise `BETA` |
| `engine_grounded_rate` | rises | api-spam → reward-hacking the shaping (shrink GROUND_B0) |
| `completions/clipped_ratio` | low | high → thinking ramble fills the cap → frac_bad |

## De-risk ladder (fail cheap — the part that historically broke)
1. **$0 local A/B** (1.7B, `USE_VLLM=0`, ~20 steps) = the SPEND GATE: the fix's `reward` is EV-centered + DECOUPLED from
   `frac_bad` (control `R_BAD=-30` tracks frac_bad; fix `R_BAD=-3` doesn't). Green → the pod.
2. **Early-abort:** after ~5 GRPO steps, if `frac_bad>0.5` → kill (a broken run dies for ~$3, not 8h).
3. **`WallClockStop`** (HARD_CAP_S) + **setsid pod-side watchdog** (survives PC death — the ~$65-burn lesson) +
   **pull-on-timeout** (a phase SSH-timeout must not lose the trained model).
4. **Network volume** for any unattended/overnight run.

## Open tensions (decide per run)
- **`beta` 0 vs ~0.04:** 0 = DAPO (diverge from teacher, cheaper, no ref model); ~0.04 = the poker-noise anti-collapse
  hedge (`../consults/qwen_train_claude.md`). Start 0 (we have other anti-collapse: R_CLIP, CRN, format reward, decaying shaping,
  GATE-5); raise via `BETA` if entropy→0 / GATE-5 shows reward-hacking.
- **Dynamic sampling = state-buffer proxy**, not true post-rollout — acceptable; monitor `frac_reward_zero_std`.
- **GLM-Z1 bounded thinking:** GLM-Z1 reasons → then emits the DSL program (`extract_program` strips `<think>`). CAP the
  think so it doesn't fill `max_completion_length` before the program (the Qwen3 frac_bad=0.93 lesson).

## ★ Consult synthesis (2026-06-19, OpenAI RL-knowledge + Claude technical → `docs/rl_consult_*.md`)
Two frontier models, CONVERGENT on the lift-critical actions. A GATED PRIOR — verify each (the math-audit showed
frontier "fixes" can be wrong); these are mostly verifiable-by-construction + both models independently agree.

**THE #1 lift lever (OpenAI):** the state buffer must be DYNAMIC, not static — a static buffer → RL overfits the initial
spots → "looks healthy (low frac_bad, reward_std>0, entropy ok) but NO bb/100 lift" = THE most-likely failure. FIX:
rebuild `build_state_buffer` every ~300 steps (or ≥2 manual phases) AND measure bb/100 vs the FROZEN SFT *mid-run*, not
just internal reward. [Phase C — needs an in-loop rebuild callback OR a 2-phase run.]

**GLM-Z1 wiring — the must-fix-before-it-runs (Claude; Phase C):**
1. `enable_thinking=False` is **Qwen3-ONLY** → GLM ignores it → always `<think>` → frac_bad=0.93. BOUND, don't disable.
2. `dsl_grammar.vllm_regex(think_cap_chars=1500)` → `(?s).{0,N}</think>\s*{prog}` enforces `</think>` within a char
   budget at the sampler = the structural defense. [Phase C — needs the dsl_grammar internals.]
3. `extract_program` → take after the LAST `</think>` (GLM completion = `reasoning</think>program`). **[APPLIED + back-compat.]**
4. `load_policy_model` → **bf16 LoRA** + `trust_remote_code` + flash_attn2; DROP nf4/bnb (Blackwell sm_120 bnb needs cu128;
   96 GB has room). Keep a `QLORA=1` fallback for the pod. [Phase C.]
5. SFT completion-only mask on GLM's `<|assistant|>` (NOT Qwen's `<|im_start|>assistant` — else NO masking → garbage SFT).
   SFT targets teach BOUNDED think (≤~400-tok rationale + program) = GATE-0 insurance. [Phase C — qwen_sft.]
6. temperature **0.8** (not 1.0; reasoning model), `MAX_COMP=768`, `VLLM_MEM=0.45`, `NUM_GEN=16`, `BASE=THUDM/GLM-Z1-9B-0414`.

**Reward (OpenAI):** verify EV dominates within-group variance (>60–70%); if not, `R_FMT` 2→1, `GROUND_B0` 1→0.5 / decay
100. Check `R_CLIP=25` vs the real EV histogram. Tune `K_ROLL` (8–16) to ~5–10 bb std. `REWARD_WORKERS=nproc-2` is the
throughput lever (else the GPU starves → too few steps → no lift). `EarlyAbort` callback **[APPLIED, env `ABORT_FRAC_BAD`].**

**Local de-risk (Claude):** `tmux` (not SSH/setsid); `OUT` local (DROP pull-on-timeout/scp/network-volume); `WALLCLOCK_S=0`
(free local — the cost gate is now YOUR time); a real **20-step GLM smoke** (free) = the spend-gate replacement; FREEZE the
eval protocol + measure SFT-init bb/100 BEFORE RL.

**Convergent must-dos:** R_BAD=−3 (never export −30) · bounded-think · NUM_GEN=16 · DYNAMIC buffer + mid-run bb/100 eval ·
a GLM-SFT-quality gate (frac_bad<10% on the RL prompts) BEFORE RL.

## Sources
- **RL book:** `books/papers/Reinforcement learning/Reinforcement Learning for Data Scientists_ From Intuition to LLMs.pdf`
- **DAPO:** `books/papers/Reinforcement learning/Dapo RL System.pdf` (Clip-Higher · Dynamic Sampling · Token-Level Loss · Overlong Reward Shaping)
- **Recipe/gates:** `../consults/qwen_train_claude.md` · **thesis:** `../consults/qwen_train_gpt55.md` · **spine:** `QWEN_6MAX_PLAN.md` · **SFT staging:** `llm_curriculum.md` · **alarms:** `first_rl_run_expectations.md`
- **Validation:** PokerBench [2501.08328](https://arxiv.org/abs/2501.08328) — SFT ceiling → RL needed.
