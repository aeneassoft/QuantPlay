# RL consult — OpenAI (RL knowledge)

> **About this document.** Verbatim transcript of an RL-methodology consultation with an OpenAI model (not named in the transcript; June 2026, committed 2026-07-05) on the GRPO lift of the GLM-Z1-9B program-of-thought brain: reward design, dynamic sampling and variance, entropy collapse and KL, GLM-specific issues, the SFT→RL handoff and the most likely failure mode. It answers a briefing that described the training code (`training/qwen_grpo.py`, R_BAD/R_FMT/GROUND_B0 shaping, K_ROLL rollouts with CRN).
> **English transcript, kept verbatim; what was adopted is recorded in docs/STATE.md and ../catalogs/MEASUREMENT_CATALOG.md.**
> Main conclusions:
> - Make EV dominate the reward variance: shrink R_FMT (2.0 → 1.0) and GROUND_B0 (1.0 → 0.5, GROUND_DECAY=100); choose K_ROLL from measured EV std (target ≈ 5–10 bb per action) and use REWARD_WORKERS instead of a larger k.
> - The most likely failure is a policy that looks healthy on internal metrics but does not lift bb/100 (a local optimum on league quirks); the single highest-leverage fix is a periodically rebuilt state buffer paired with intermediate bb/100 evaluations against the frozen SFT baseline.
> - Entropy bands [0.5·H0, 1.0·H0] as tripwires; KL (BETA 0.02–0.04) only on collapse; a short GLM-specific DSL SFT/prompt-adaptation phase before RL if frac_bad or EV are worse than the Qwen SFT.


## reward_design
Key points specific to this setup that actually move bb/100:

1) Make sure EV really dominates the gradient (R_BAD and shaping tuned around *your* EV scale)
- You already fixed the -30→-3 bug; still sanity-check with a 0-cost experiment:
  - On a small subset of states (e.g., 200 prompts), log per-completion: {EV, clipped_EV, final_reward, is_bad, is_grounded}.
  - Compute over groups (G=8):
    - Var(EV | legal)
    - Contribution of format + grounding vs EV to reward variance.
  - You want: for legal completions within a group, var_from_EV >> var_from(R_FMT, grounding).
- If grounding + format still contribute more than ~30–40% of within-group variance, shrink them:
  - R_FMT: consider 1.0 instead of 2.0.
  - GROUND_B0: consider 0.5 instead of 1.0, and/or faster decay (e.g., GROUND_DECAY=100).
- The failure mode you *must* avoid: model mostly optimizes “be valid + call api.*” while EV gradients are low SNR.

2) Verify R_CLIP scale vs real EV distribution
- Today: R_CLIP=25, bb unit = 1/100 big blind, rollouts k=16.
- Empirical check (same small subset as above): hist of raw EV from rollout_action_ev, per action.
  - If p(|EV| > 25) is non-trivial (>5–10%), clipping is cutting off real signal from big pots.
  - If p(|EV| > 25) ≈ 0, you can lower R_CLIP to ~15 to reduce heavy-tail noise without losing info.
- For 6-max cash, using CRN with k=16, a reasonable target is EV_std per completion ≈ 5–10 bb; much higher and updates get too noisy; much lower and you’re under-exploring high-impact spots.

3) Tune K_ROLL against variance, not guesswork
- K_ROLL=16 is expensive; use the GPU you have by increasing parallel rollout workers instead of blindly increasing k.
- Concrete plan:
  - Choose a representative sample of ~200 (snap,spot) and candidate actions.
  - For each action, estimate EV with different ks using extra offline scripts: 4, 8, 16, 32.
  - Plot std(EV_hat_k) vs k. Pick smallest k where std is in your 5–10 bb band above.
  - If k=8 already gives ~6–8 bb std, you can cut K_ROLL to 8 and double batch size / steps for same wall-clock.
- Very likely win: run with K_ROLL=8 and REWARD_WORKERS>1 (see dynamic_sampling_and_variance section) – more steps, more stable training, and still low variance thanks to CRN.

4) Penalize hangs and long programs explicitly (don’t rely just on truncation)
- You already have REWARD_TIMEOUT_S=2.0 inside run_program; verify that timed-out programs are marked res['ok']==False and thus get R_BAD.
- Add a small explicit length penalty for extremely long programs that still pass grammar:
  - After extract_program, compute token_count or char_count; if > L_cutoff (e.g., 512 chars or equivalent tokens), subtract 1–2 bb from reward.
  - This discourages pathological giant DSL programs that just happen to be valid, without confusing EV.
- This matters because your max_completion_length=384 was chosen to avoid <think>-ramble; there’s still room for pathological but valid DSL chains.

5) Keep shaping genuinely “small and decaying” in practice
- Shaping term is ±b with b = GROUND_B0 * (1 - step/GROUND_DECAY)_+.
- Two risks:
  1) If early steps are noisy, model may learn a local optimum around "always api.*" or "never api.*" that persists long after shaping decays.
  2) Different states may structurally prefer grounding differently; a global ±b may bias action mixes in weird ways.
- Mitigation:
  - Instrument per-step: avg_R_EV, avg_R_FMT, avg_R_grounding_abs.
  - Hard rule: |avg_R_grounding| < 0.2 * |avg_R_EV| after step 50. If not, either shorten GROUND_DECAY or cut GROUND_B0 by half.
  - If you see rapid increase in engine_grounded_rate to >0.9 combined with flat EV reward, you’re reward-hacking; immediately shrink GROUND_B0 to 0.25 and GROUND_DECAY to 50.

6) Watch for reward skew by illegal-rate differences between strategies
- Even with R_BAD=-3, strategies that propose more hard-to-evaluate actions (close to illegal) may be under-rewarded just because they trip edge cases more often.
- Manual check: sample 50–100 completions from the SFT init vs a mid-RL checkpoint for the same prompt set, and compute:
  - frac_bad(SFT), frac_bad(RL), mean EV(SFT legal), mean EV(RL legal).
- If RL policy has higher frac_bad but also clearly higher EV on legal ones, you may be underestimating its true strength; consider a small *relative* format reward that scales with (1 - frac_bad_in_group) rather than a flat R_BAD (more complex, probably not needed if you keep frac_bad under control).

7) Preserve stationarity of the reward distribution across training
- Don’t quietly change TRAIN_LEAGUE or the rollout parameters mid-run unless you log a hard phase boundary and reset expectations.
- If you do change profiles or their mix, expect a bump in reward_std and a transient dip in mean reward; don’t misinterpret that as collapse.
- If you want curriculum on opponent strength, do it in coarse phases (e.g., first N steps vs weaker league, then lock league and train to convergence). Don’t smoothly anneal profiles every few steps; you’ll wash out signal.


## dynamic_sampling_and_variance
Main lever: your state buffer proxy for DAPO dynamic sampling must be *alive*, not frozen.

1) Rebuild the state buffer periodically
- Current main() builds state buffer once at start: states = build_state_buffer(n_states, seed=seed).
- That bakes in the initial policy’s action-value landscape. As RL changes the policy, the set of high-spread states under *league_policy(tag)* may not be the high-information ones for the RL policy.
- Concrete fix:
  - Introduce a periodic rebuild every N_RL_STEPS (env knob). Example: every 200–500 steps.
  - Implementation: extend _callbacks with a callback that, on_step_end, if step % REBUILD_EVERY == 0 and step > 0:
    - Recompute states = build_state_buffer(n_states, seed=seed+step),
    - Rebuild ds, snapshots,
    - Assign trainer.train_dataset = new_ds and swap reward = make_ev_reward(new_snapshots).
  - This is a bit intrusive, but even a coarse 1–2 re-builds per full run is better than static buffer.
- At minimum: for the first run on GLM-Z1-9B, do *two* phases manually:
  1) Run N1 steps on initial buffer, save ckpt.
  2) Stop, rebuild buffer (same code), restart RL from ckpt with new buffer.

2) Actually monitor frac_reward_zero_std and act on it
- You’re already logging frac_reward_zero_std.
- Put concrete thresholds and actions into practice:
  - If frac_reward_zero_std > 0.6 for 3+ consecutive logging windows:
    - Increase spread_eps by +0.2 (e.g., 0.5 → 0.7), rebuild state buffer.
    - If that shrinks state count too much (<0.5*n_states), instead increase k_screen or oversample.
- Also log n_effective_states = number of states surviving the spread filter after build_state_buffer; if it trends downward over runs or rebuilds, your TRAIN_LEAGUE / rank_state parameters might be producing overly easy decisions.

3) Upgrade rank_state/k_screen for better prefiltering
- build_state_buffer uses rank_state(…, k=k_screen=8) to estimate candidate EV spread.
- Two cheap improvements:
  - Increase k_screen to 12–16: better approximation of max-min EV across candidate actions → more accurate spread.
  - Use multiple seeds for screening: for each (snap,spot), compute spread under base_seed, base_seed+1, then take mean spread; this smooths CRN noise in screening.
- If CPU is the bottleneck here, do this once offline and cache a state-buffer file. The important thing is: the states you train on really do have multi-action EV spreads of ≥0.5 bb in practice.

4) Use REWARD_WORKERS aggressively on the RTX PRO 6000 box
- Your bottleneck is CPU rollouts. Right now REWARD_WORKERS defaults to 0 (sequential). That will *starve* the GPU and limit you to very few steps.
- On the local Blackwell machine, pick REWARD_WORKERS = max(2, cpu_count - 2). Example: if 16 logical cores, use 12–14 workers.
- Then tune GEN_BATCH and K_ROLL together to target:
  - GPU utilization > 60%.
  - wall-clock step_time < 5–10 seconds for a reasonably sized GEN_BATCH (e.g., 64–96).
- Direct outcome: more gradient steps for same time budget → higher probability to see an actual bb/100 lift.

5) Control EV estimator variance *within GRPO groups*
- You already do CRN via base_seed per prompt, which is correct.
- Failure mode: if K_ROLL is too small and opponents are too swingy, you get high variance *within* the group, which makes DAPO clip out almost everything.
- Diagnostic:
  - During training, log (maybe offline) the empirical distribution of (R_i - mean(R_group)) per group, and the clip ratios for low and high sides separately.
  - If almost all advantages get clipped regularly (e.g., clip_ratio/region_mean close to clipping boundaries, or massive mass on ±epsilon), then variance is too high or epsilon too low.
- Fix options:
  - Lower K_ROLL variance by increasing k a bit (if CPU allows), or
  - Increase epsilon to 0.25 / epsilon_high=0.35 for more aggressive policy updates on noisy rewards, at risk of some instability. Given CRN, I’d first try K_ROLL adjustment before messing with epsilon.

6) Avoid dataset-spot overfitting: shuffle_dataset=True is good but ensure spots are diverse
- build_state_buffer(n_states) – choose n_states large enough that you are not seeing the same spot many times per epoch.
- For a 9B with real EV reward, I’d try n_states at least 5k–10k if you can afford the build; otherwise, ensure oversample>1.5 and seed randomization across runs so you don’t just memorize a tiny handful of states.

7) Consider simple per-step resampling rather than a static dataset
- TRL’s GRPOTrainer can work with an IterableDataset; if you’re comfortable, wrap gen_decision_states+state-buffer filtering into an IterableDataset that yields fresh states every step.
- That’s ideal but more code. For now, at least:
  - Set shuffle_dataset=True (you already do).
  - For longer runs, when you see reward flattening and frac_reward_zero_std creeping up, explicitly rebuild the dataset.


## entropy_collapse_and_kl
Your main anti-collapse tools: high epsilon_high, no KL at start, grammar constraints, shaping, and EV clipping. You need concrete tripwires.

1) Define clear entropy health bands
- Monitor the logged "entropy" metric (token-level).
- Empirical target bands for this task:
  - Initial SFT entropy (measured on the RL dataset prompts) = H0.
  - Healthy RL band: [0.5*H0, 1.0*H0].
  - Collapse alarm: entropy < 0.4*H0 sustained for >50 steps.
  - Noise/exploration alarm: entropy > 1.2*H0 sustained (often corresponds to babbling / off-policy degenerate outputs, but grammar constraints should limit that).
- Before RL, run a short dry pass to estimate H0 on the RL dataset: do a forward pass with SFT adapter-only policy, no RL, and compute entropy.

2) When to turn on KL (BETA) and how
- Start with BETA=0.0 as planned.
- If collapse alarm triggers (entropy < 0.4*H0, plus any sign of reward-hacking from GATE-5):
  - Turn on KL with small coefficient:
    - BETA=0.02 initially.
    - If still collapsing, increase to 0.04.
- Critical: the ref model should be the frozen SFT adapter+base.
  - Ensure you have enough VRAM: 96GB Blackwell should handle 9B base + 9B ref in 4bit easily.
- Don’t start with BETA>0.04; that would strongly tether the policy to SFT and may prevent surpassing it.

3) Mechanical check: is DAPO actually using the reference when beta>0?
- TRL + loss_type="dapo" + beta>0: confirm from TRL version docs / quick code dive that it indeed uses ref logits to compute KL.
- Simple test:
  - Run 1–2 iterations with a tiny training set and BETA>0.
  - Perturb model weights slightly pre-run and verify KL loss is non-zero and gradients flow.
- You don’t want to flip BETA in later runs and discover your installed TRL ignored it due to API drift.

4) Avoid implicit KL through grammar + grounding + R_BAD
- You already constrain to DSL grammar via vllm_structured_outputs_regex; that implicitly acts like a hard prior: you only explore within the grammar.
- Combined with R_BAD=-3 and R_FMT=+2, there is an anti-entropy bias even without KL:
  - Once the model finds a small family of always-valid, always-grounded programs with decent EV, it can shrink entropy by sticking to those.
- To counteract that without KL:
  - Keep temperature=1.0 and top_p=1.0 during RL (you do).
  - If you see collapse *and* don’t want to pay for KL, temporarily increase temperature to 1.2 and see if that recovers diversity without destroying EV.

5) Clip-Higher + DAPO can still over-update on noisy advantages
- epsilon=0.2 / epsilon_high=0.28 is sane, but with high-variance advantage estimates, you can get spiky updates that drive policy towards a brittle high-EV-for-panel niche.
- Diagnostics:
  - Monitor clip_ratio/region_mean and maybe region-specific clipping logs.
  - If you see a very high fraction of tokens in the high-clip region, your epsilon_high might be too small for the reward noise.
- Fix:
  - If you must, widen epsilon_high to 0.32 once you are confident variance is low (after tuning K_ROLL and opponent league).
  - But do this only if EV clearly becomes stable yet policy remains too close to SFT (high action-match vs teacher but small EV gain).

6) Explicit early-stop if signs of reward-hack with entropy drop
- Combine GATE-5 with entropy monitoring:
  - Sample ~50 completions periodically and inspect for patterns like "always fold", "always min-raise" or crazy-big constant bet sizing that yields good panel EV due to league quirks.
  - If you see one-liner patterns and entropy falling, assume reward-hack rather than genuine strategic improvement.
- Response pathway:
  1) Shrink or zero out GROUND_B0 to stop the hack vector.
  2) Adjust TRAIN_LEAGUE to include opponents that punish that pattern.
  3) Only if needed, add a modest KL (BETA>0) to tether away from that degenerate solution.

7) Don’t let beta interact silently with 4bit/LoRA finetuning weirdness
- With 4bit base + LoRA, KL regularization will mostly act on the LoRA head but can be affected by quantization noise.
- Make sure you’re not accidentally training both base and LoRA; load_policy_model uses prepare_model_for_kbit_training and then PeftModel.from_pretrained(..., is_trainable=True), which is correct (train only LoRA).
- If you later add a ref model, keep it 4bit + LoRA as well to keep KL geometry consistent; don’t compare 4bit-quantized policy vs full-float ref if you can avoid it.


## glm_z1_reasoning_model_rl_specifics
GLM-Z1-9B is a reasoning-tuned model with explicit thinking traces. You’ve already disabled thinking in build_dataset; you need to be careful about several GLM-specific behaviors.

1) Ensure no hidden thinking channel during RL
- In build_dataset, you do apply_chat_template(..., enable_thinking=False). Confirm GLM’s tokenizer/template actually respects this flag:
  - Quick sanity: run the RL policy on a few prompts and inspect raw text; you should *never* see GLM’s internal reasoning markers (e.g., <think> or similar) before the DSL program.
- If they still appear:
  - Patch the tokenizer/template: either strip the thinking tokens from generated outputs inside the processing function, or use a plain causal template instead of the chat template.
- If thinking tokens leak in, they will often fill max_completion_length and either cause truncation or move the program far to the right, both of which will spike frac_bad.

2) Harmonize GLM’s DSL style with Qwen/Claude teacher style
- Your SFT spine mixes PokerBench + solver/self-play + Claude teacher. GLM-Z1 may natively prefer different formatting / phrasing around the DSL program.
- Pre-RL check: on a validation set of spots, compare:
  - Qwen SFT completions (or Claude completions) vs GLM-Z1 SFT completions in DSL-only mode.
  - Compute frac_bad and EV for both.
- If GLM-Z1’s SFT policy has much higher frac_bad (e.g., >15%) or just weird program shapes, you should add a short, targeted SFT phase *just on the DSL format* before RL:
  - Fine-tune GLM-Z1-9B on a small curated set (e.g., 30–50k) of high-quality DSL-only demonstration data (no extra thinking, only valid programs with high EV) until frac_bad on that set is <5%.
  - Only then run RL.
- If you skip this and GLM-Z1 fights the DSL format during RL, most gradient will go into "produce a legal program" rather than "improve EV".

3) Cap complexity of program-of-thought seen during RL
- GLM-Z1 will happily produce complex DSL sequences with multiple api.* calls.
- For RL, long sequences may:
  - Increase rollout latency (more engine work per decision),
  - Increase the surface for subtle bugs (time-outs, unsupported API combos),
  - Inflate variance (small errors earlier in multi-step reasoning causing large EV swings).
- To manage this:
  - Add a soft complexity constraint to the DSL environment: e.g., limit the maximum number of api.* calls per program to 3.
  - If extract_program sees more than that, either hard-fail to R_BAD or assign a -1 bb complexity penalty.
- This keeps training focused on strategically relevant calculations (e.g., equities / pot odds / simple simulations) rather than esoteric chains.

4) Make sure grammar constraints + GLM’s tokenization play well with vLLM
- You rely on vllm_structured_outputs_regex = dsl_grammar.vllm_regex().
- Test matrix:
  - Run vLLM generation with GLM-Z1-9B + grammar on a random sample of prompts.
  - Track: generation latency, frac_bad, and any systematic failure modes (e.g., early EOS, repeated fragments).
- If GLM-Z1 under vLLM+regex shows higher frac_bad than under standard transformers-gen+regex, consider *starting* RL with USE_VLLM=0 locally to de-risk:
  - Use transformers-generation with logit processors that enforce the regex (or a simpler bracket/keyword-based constraint).
  - Once the policy stabilizes and frac_bad is low, you can reintroduce vLLM for throughput.

5) Account for GLM’s calibration vs EV signal strength
- Reasoning models often produce more calibrated probabilities; this can interact with PG in two ways:
  1) They are conservative: slow to move away from prior, smaller advantages → slower RL.
  2) They put high prob mass on a single favorite action → lower entropy, quicker collapse if reward signal is spiky.
- Mitigation:
  - At the start, keep LR=1e-6 but consider a slightly longer warmup_ratio (e.g., 0.05 instead of 0.03) to avoid large early updates.
  - If you see *very* slow movement in action distributions (no EV lift, but healthy entropy and reward_std>0), you can cautiously bump LR to 2e-6.
  - Expect GLM-Z1 to need more gradient steps than Qwen-8B for the same delta in behavior; budget accordingly.

6) Inspect GLM’s "reasoning" as latent prior even without explicit <think>
- Even with enable_thinking=False, GLM-Z1’s internal priors still differ from a plain decoder: it may encode preferences like "avoid thin value bets" or "play nitty in marginal spots".
- This can show up as:
  - Consistent under-betting in high-variance spots.
  - Overfolding to aggression.
- RL *can* fix this if EV signal is strong enough and TRAIN_LEAGUE punishes these biases.
- Concretely:
  - After some RL steps, analyze bet-size distributions and fold frequencies in typical spots for SFT vs RL vs a known baseline (e.g., your Qwen policy or solver approximations).
  - If RL amplifies GLM-Z1’s conservative bias instead of correcting it, you need more diverse and aggressive opponents in TRAIN_LEAGUE to create EV gradient pressure against overfolding.

7) Ensure LoRA adaptation fits GLM-Z1’s intrinsic scale
- load_policy_model assumes Qwen 4bit + LoRA. Switching to GLM-Z1 means LoRA rank, scaling, and init might not be ideal.
- If your SFT adapter for GLM-Z1 is already working (71.7% PokerBench etc.), then continuing RL on that adapter is fine.
- If you have to freshly create a LoRA layer for GLM-Z1, ensure:
  - LoRA rank is not too small (at least 16–32 for a 9B),
  - alpha matches what you used in SFT,
  - Target modules (e.g., attention and MLP projections) match SFT training; don’t change LoRA topology between SFT and RL.
- Misaligned LoRA configs can cause RL updates to be too weak to move policy, leading to apparent "non-learning" despite healthy reward signal.


## sft_to_rl_handoff
The handoff is where most projects silently fail. You need explicit gates between SFT sanity and meaningful RL signal.

1) Confirm SFT on GLM-Z1-9B is truly at least as good as Qwen SFT
- You cited 71.7% action accuracy on PokerBench for Qwen. Before RL on GLM-Z1, check:
  - PokerBench action-accuracy for GLM-Z1 SFT on the same evaluation protocol.
  - Realized EV vs the same frozen panel used for Qwen.
- If GLM-Z1 SFT is substantially weaker on EV (even if similar on accuracy), RL will first spend time just catching up to Qwen-style strategy; you may misinterpret initial improvements as "RL lift" from GLM-Z1 rather than from SFT baseline.
- Decide which SFT you want as the baseline for GATE 2 and stick to it. If GLM-Z1 SFT is worse, consider:
  - A two-stage process: distill Qwen→GLM-Z1 to parity, then RL on GLM-Z1.

2) Step-0 RL smoke test (you partially have this, but make it formal)
- Before any serious Blackwell run:
  - Use a tiny model (1.7B) or a small GLM-Z1 variant if available.
  - Run 10–20 RL steps locally with USE_VLLM=0, K_ROLL small (e.g., 4), and N_STATES=200.
  - Look only at *within-group* reward variance and frac_bad trends.
- Acceptable outcomes for going to full run:
  - frac_bad starts maybe high but drops below 0.3 within ~10 steps.
  - reward_std > 0.
  - No immediate entropy collapse.
- This step verifies that your updated R_BAD=-3 reward, grammar regex, and GLM-Z1 outputs are consistently wired.

3) Align the SFT prompt format and RL prompt format exactly
- build_dataset formats spots via build_messages and apply_chat_template with enable_thinking=False.
- Verify SFT training used the *same* prompt format, including role labels and any system messages.
- If SFT used thinking or slightly different instructions, GLM-Z1 will initially be off-distribution under RL prompts, causing a spike in frac_bad that may dominate the gradient.
- If there is a mismatch, add a short post-SFT "prompt-adaptation" fine-tune before RL where you train on the RL-style prompts but with the same target outputs as SFT.

4) Freeze evaluation protocols before the run
- Predefine the following for both SFT-init and RL checkpoints:
  - Opponent league for evaluation (likely the same as TRAIN_LEAGUE or a superset).
  - Number of hands per opponent for measuring bb/100 (e.g., 100k+ to shrink variance).
  - Seeds and CRN settings.
- Run the full evaluation pipeline on the SFT-init *before* starting RL, record:
  - bb/100 mean and 95% CI vs each panel member,
  - aggregate bb/100.
- This ensures that when you later say "RL beat SFT-init by +5 bb/100", you know it’s statistically meaningful and not due to eval drift.

5) Ensure trainer actually continues the SFT adapter, not resets it
- load_policy_model loads base + SFT LoRA with is_trainable=True, which is correct.
- Triple-check that OUT is different from ADAPTER, so you’re not overwriting the SFT adapter during RL training.
- Also, verify that GRPOTrainer does not accidentally reinit the model. Quick test:
  - Before trainer.train(), eval on a small validation set and save logits.
  - After 0 steps (or after calling trainer._prepare_model()), eval again; logits on same prompts must be bitwise identical (modulo dropout disabled).

6) Early-run guardrail: frac_bad and legality gating
- You have GATE 1: legality ≥99% after ~200 steps.
- Implement a hard kill: if after 20–30 RL steps frac_bad > 0.5, abort the run; do not continue hoping it will fix itself.
- Typical root causes and fixes:
  - Prompt mismatch → fix prompt templates, re-SFT on RL prompts.
  - Grammar mismatch between GLM-Z1 tokenization and regex → adjust grammar or use a looser but still safe constraint.

7) Transition from RunPod to local Blackwell: re-validate environment determinism
- _ensure_hashseed and _get_pool are designed to be deterministic.
- After moving to local, verify that:
  - Two short RL runs with same seed, same environment, and same code produce the same metrics.jsonl up to float noise.
- If they don’t, there’s a hidden nondeterminism: likely in multiprocessing, external libs, or random seeds in vLLM. Fix this before trusting RL results, or at least know the level of stochasticity in training.

8) Don’t change too many knobs between runs when diagnosing “no lift”
- You’ve already changed R_BAD and infra. Keep the next run as close as possible to the config that "almost worked" but died to timeouts, except for:
  - R_BAD fixed,
  - REWARD_WORKERS tuned,
  - GLM-Z1-specific fixes (prompt, thinking, grammar).
- If bb/100 still doesn’t lift, *then* iterate on bigger design choices (league composition, K_ROLL, n_states).

9) Measure lift vs SFT as soon as metrics suggest a plateau
- Don’t wait for thousands of RL steps before doing an eval.
- As soon as reward stabilizes for ~100 steps and frac_bad is low, take current checkpoint and run a reduced-size eval (e.g., 30k hands vs panel).
- If you already see +3 to +5 bb/100 over SFT with overlapping confidence intervals, it’s promising; then scale evaluation up.
- If no improvement or negative, stop early → debug reward variance / dataset / league before burning more compute.


## most_likely_failure_and_fix
Most likely failure: RL converges to a policy that **looks healthy on internal metrics (low frac_bad, stable reward, non-zero entropy)** but **does not improve bb/100 vs SFT**, or even slightly worsens it. In other words, you get a local optimum exploiting quirks of TRAIN_LEAGUE + shaping, not genuine strategic improvement.

Mechanism chain:
1) Static state buffer built under a tag-continuation policy and fixed TRAIN_LEAGUE yields a pre-filter of “interesting” spots that remains constant across RL.
2) GLM-Z1 SFT prior + grammar constraints push the model towards a few structurally safe DSL patterns that are always valid and often involve api.* (to exploit R_FMT + grounding).
3) In those fixed states, realized EV differences between actions *against TRAIN_LEAGUE* are either small or idiosyncratic (panel-specific quirks).
4) DAPO with CRN learns to exploit these idiosyncrasies (e.g., betting too big or folding slightly more than SFT in marginal spots) without improving generalized strategy.
5) On live evaluation vs a broader or different panel, these learned biases are neutral or negative → measured bb/100 vs frozen SFT-initial policy does not improve.

Why this is more likely than pure collapse or reward-hacking:
- You’ve already fixed the biggest structural bug (R_BAD=-30), and you have CRN + clipping + grammar constraints. That makes "system obviously broken" less likely.
- But nothing in the current pipeline refreshes the state buffer or the league adaptively, and shaping + format rewards still create mild non-EV objectives.

Concrete fix bundle (minimum set that directly targets this failure):

1) **Periodic state-buffer rebuild tied to RL progress**
- Choose REBUILD_EVERY (e.g., 300 steps).
- At each rebuild:
  - Stop trainer.
  - Recompute states = build_state_buffer(n_states, seed += 1) with up-to-date TRAIN_LEAGUE.
  - Rebuild ds, snapshots, reward = make_ev_reward(snapshots).
  - Resume trainer from same checkpoint on new dataset.
- Rationale: keeps training focused on currently high-signal states under the evolving policy and league, rather than overfitting to the initial buffer.

2) **Harden TRAIN_LEAGUE to punish league-specific exploits**
- Ensure the training league includes:
  - Variants of your own SFT policy (nitty, aggressive, slightly perturbed bet sizes).
  - At least one opponent with over-aggression and one with over-calling to counter over-folding / over-bluffing local optima.
- Every time you detect a strong pattern in RL policy during GATE-5 inspection (e.g., always c-bets small), check whether any league member is punishing it; if not, add one.

3) **Tighten shaping and format rewards so EV dominates**
- Halve R_FMT (2.0 → 1.0) and GROUND_B0 (1.0 → 0.5) for GLM-Z1 runs, with GROUND_DECAY=100.
- Monitor avg_R_EV vs auxiliary rewards; enforce a rule: sum(|auxiliary rewards|) < 0.2 * |R_EV| in logs.
- If GATE-5 shows api.* spam or uniform patterns not obviously EV-driven, further shrink shaping or zero it.

4) **Intermediate bb/100 evals vs the *frozen SFT* panel, not just internal reward**
- Every time reward plateaus for >100 steps, run a mid-run evaluation (even with fewer hands) vs the frozen SFT policy.
- If mid-run eval shows no clear improvement, don’t just continue training; adjust:
  - K_ROLL, TRAIN_LEAGUE, or spread_eps and rebuild state buffer before continuing.

5) **GLM-specific DSL SFT polish before RL**
- If initial GLM-Z1 SFT policy has higher frac_bad or lower EV than Qwen SFT, do a short alignment SFT over your DSL gold data first until:
  - frac_bad < 10% on RL prompts,
  - EV vs a simple opponent is at least not worse than Qwen SFT.
- Starting RL from a misaligned SFT will mix “fix formatting” and “improve strategy” in the same gradient, often saturating capacity with the former.

If you implement **only one major change** to maximize P(lift): make the state buffer **dynamic** (periodic rebuild or on-demand when frac_reward_zero_std is high) and pair it with periodic bb/100 evaluations against a frozen SFT baseline. That is the highest-leverage move to convert noisy local improvements in a fixed dataset into global strategic gains that show up in bb/100.


## top_5_actions
- Before the next full run, run a small diagnostic job that logs per-completion EV components (EV, R_FMT, grounding) and verify that variance from EV dominates (>60–70% of within-group reward variance); shrink R_FMT and GROUND_B0 if needed.
- Enable and tune REWARD_WORKERS on the local RTX PRO 6000 box, and empirically choose K_ROLL (likely 8–16) based on measured EV variance, targeting ~5–10 bb std per action.
- Implement at least *one* periodic rebuild of the state buffer (build_state_buffer + build_dataset + make_ev_reward) mid-run, and resume training on the new dataset to avoid overfitting to initial states.
- Add a short GLM-Z1-specific SFT or prompt-adaptation phase (if frac_bad or EV are worse than Qwen SFT) so that GLM-Z1 reliably emits valid DSL programs under the **same** prompts you’ll use in RL.
- Define and adhere to an evaluation protocol: run an initial bb/100 vs frozen-SFT baseline, then repeat after the first RL plateau; if no improvement, adjust league/opponents and state-buffer settings before investing in a long run.
