"""DAPO-style GRPO trainer — lift the Qwen DSL policy ABOVE its SFT init via REALIZED-EV reward (the core thesis, GATE 2).

DAPO (verified native in TRL): `loss_type="dapo"` (token-level PG loss), `epsilon=0.2`/`epsilon_high=0.28` (clip-higher),
`beta=0.0` (no KL — RL is meant to diverge from the SFT teacher), `scale_rewards=False` (Dr.GRPO), and
`mask_truncated_completions=True`. Dynamic sampling (DAPO's biggest single win) is done as a $0 STATE-BUFFER pre-filter
here (drop spots whose candidate-EV spread ≈ 0 → no learnable signal) + oversampling, since TRL has no in-loop knob.
Generation is grammar-CONSTRAINED to our DSL via `vllm_structured_outputs_regex` (brain/dsl_grammar). Reward = engine
realized EV (verifiable, no learned reward model → no reward hacking).

Layering for $0 testability: `build_state_buffer`, `make_ev_reward`, `build_dataset` import NO torch/trl — Stage-0 dry-run
(training/ tests) exercises them on CPU. torch/trl load only inside `load_policy_model` / `make_config` / `main` (pod GPU).
Run on the pod: PYTHONPATH=/root/pokerb python -u -m training.qwen_grpo
"""
from __future__ import annotations

import json
import os
import time

from pokerbot.arena.sixmax import PROFILES, SixMaxBot
from pokerbot.brain import dsl_grammar
from pokerbot.brain.executor import run_program
from pokerbot.brain.format_spot import format_spot, spot_from_table
from pokerbot.brain.policy import build_messages, extract_program
from training.pilot import rank_state
from training.rl_env import TRAIN_LEAGUE, gen_decision_states, league_policy, rollout_action_ev

HERO_SEAT = 0
R_BAD = float(os.environ.get("R_BAD", "-30"))      # grammar-reject/illegal/no-decide: a TRUE floor BELOW -(R_CLIP+R_FMT+GROUND_B0)
R_CLIP = float(os.environ.get("R_CLIP", "25"))     # clip EV (scale_rewards=False -> an all-in cooler must not swamp a group)
R_FMT = float(os.environ.get("R_FMT", "2.0"))      # binary FORMAT reward: +R_FMT for a parsed+grammar+decide() program. With
#                                                    R_BAD a true floor, a valid-but-bad action ALWAYS beats garbage -> format is
#                                                    never the EV-wrong choice (R_BAD=-10 > min EV -25 was a latent bug). Fast-converging.
K_ROLL = int(os.environ.get("K_ROLL", "16"))       # rollouts per completion (reward variance vs cost)
# Aggressive pretrained-PRIOR suppression (user directive): a SMALL, DECAYING shaping term that rewards engine-grounded
# programs (an api.* call before decide) over gut decides -> suppresses poker-folklore reliance while realized-EV stays
# dominant + the truth. b decays to 0 so it never permanently distorts the EV signal. |b| <= GROUND_B0 (~1 bb << R_CLIP).
GROUND_B0 = float(os.environ.get("GROUND_B0", "1.0"))        # initial shaping weight (bb)
GROUND_DECAY = float(os.environ.get("GROUND_DECAY", "200"))  # steps over which the shaping decays to 0
REWARD_TIMEOUT_S = float(os.environ.get("REWARD_TIMEOUT_S", "2.0"))  # per-program wall-clock cap (anti-hang; POSIX)
# FULL-GPU-LOAD lever: the reward = GEN_BATCH*K_ROLL self-play rollouts/step is the CPU bottleneck that STARVES the GPU
# during GRPO (vLLM gen is fast; the GPU then idles waiting on sequential CPU rollouts). REWARD_WORKERS>1 fans the
# (embarrassingly-parallel, independent-per-completion) rollout pass across a persistent process pool so generation isn't
# blocked. 0/1 = sequential (the $0 local/Stage-0 path; behaviour-identical). The pod sets it to ~cpu_count-2.
REWARD_WORKERS = int(os.environ.get("REWARD_WORKERS", "0"))
_POOL = None


def _get_pool(workers: int):
    """Lazy, PERSISTENT process pool (spawn) reused across steps — pay worker-startup once, not per step. Spawn (not
    fork) → workers re-import this module which pulls NO torch (torch is imported only inside the GPU fns) → lean CPU
    workers + no CUDA-fork hazard (the reward is pure-CPU poker sim)."""
    global _POOL
    if _POOL is None and workers > 1:
        import multiprocessing as mp
        from concurrent.futures import ProcessPoolExecutor
        os.environ["PYTHONHASHSEED"] = "0"           # spawned workers inherit env at startup -> all workers share ONE hash
        #                                              seed -> set/dict (card-string) iteration is identical across workers
        #                                              -> a GRPO group's completions stay CRN-comparable even split across them.
        _POOL = ProcessPoolExecutor(max_workers=workers, mp_context=mp.get_context("spawn"))
    return _POOL


def _rollout_worker(args):
    """Module-level (→ picklable) rollout task: rebuild the tag continuation IN-PROCESS (the cont-bot gets only decide()
    in rollouts, never observe()/new_hand() → stateless → a fresh bot is behaviour-identical to a shared one), then run
    the k CRN rollouts. Returns the mean hero net (bb). All heavy work (k deepcopy+play-outs) happens off the main proc."""
    snap, hero_seat, action, amount, profiles, k, bseed, bb = args
    from pokerbot.arena.sixmax import PROFILES, SixMaxBot
    from training.rl_env import league_policy, rollout_action_ev
    cont = league_policy(SixMaxBot(hero_seat, PROFILES["tag"]))
    return rollout_action_ev(snap, hero_seat, action, amount, cont,
                             profiles=profiles, k=k, base_seed=bseed, bb=bb)


# ---------------------------------------------------------------- state buffer (dynamic-sampling pre-filter)
def build_state_buffer(n: int, oversample: float = 1.5, spread_eps: float = 0.5, k_screen: int = 8,
                       profiles=TRAIN_LEAGUE, hero_seat: int = HERO_SEAT, seed: int = 0,
                       decontam: bool = True) -> list:
    """gen_decision_states + the DAPO DYNAMIC-SAMPLING pre-filter: keep only spots whose discrete candidate actions have
    an EV SPREAD >= spread_eps (a learnable decision), oversample to refill, decontam vs the PokerBench test set.
    Returns the top-spread `n` (snapshot, spot) pairs. CPU/$0."""
    cont = league_policy(SixMaxBot(hero_seat, PROFILES["tag"]))
    keys = set()
    if decontam:
        try:
            from dataset.decontam import pokerbench_test_keys
            keys = pokerbench_test_keys()
        except Exception:  # noqa: BLE001
            keys = set()
    from dataset.schema import spot_key
    scored = []
    for i, (snap, spot) in enumerate(gen_decision_states(profiles=profiles, hero_seat=hero_seat,
                                                         n_states=int(n * oversample), seed=seed)):
        if keys and spot_key(format_spot(spot)) in keys:
            continue
        cands = rank_state(snap, hero_seat, cont, k=k_screen, profiles=profiles, base_seed=seed + i)
        spread = cands[0]["ev_bb"] - cands[-1]["ev_bb"]
        if spread >= spread_eps:
            scored.append((spread, snap, spot))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [(snap, spot) for _, snap, spot in scored[:n]]


# ---------------------------------------------------------------- reward (engine realized EV, CRN-paired)
def make_ev_reward(snapshots: list, hero_seat: int = HERO_SEAT, profiles=TRAIN_LEAGUE, k: int = K_ROLL, bb: int = 100):
    """Return a TRL reward_func(completions, sid, base_seed, **kw) -> list[float]. CRN: every completion of a prompt
    shares that prompt's base_seed (passed through as a dataset column) so group-relative advantage isolates the ACTION,
    not card luck. Bad output -> R_BAD; legal -> clipped realized EV from rollout_action_ev (tag continuation)."""
    cont = league_policy(SixMaxBot(hero_seat, PROFILES["tag"]))

    def _finalize(ev, is_grounded, b):
        """Identical reward math whether the EV came from the pool or the sequential path: clip → +format → ±grounding."""
        return max(-R_CLIP, min(R_CLIP, float(ev))) + R_FMT + (b if is_grounded else -b)

    def ev_reward(completions, sid, base_seed, trainer_state=None, prompts=None, log_metric=None, **kwargs):
        step = getattr(trainer_state, "global_step", 0) or 0
        b = GROUND_B0 * max(0.0, 1.0 - step / GROUND_DECAY)            # decaying engine-grounded shaping weight
        n = len(completions)
        out = [None] * n
        bad = grounded = 0
        work = []                                                     # (idx, snap, action, amount, bseed, is_grounded)
        # PASS 1 (fast, sequential): parse + run_program → action or R_BAD. Light CPU; gathers the heavy rollout work.
        for j, (comp, i, bseed) in enumerate(zip(completions, sid, base_seed)):
            text = comp if isinstance(comp, str) else comp[-1]["content"]   # standard vs conversational
            snap = snapshots[int(i)]
            spot = spot_from_table(snap, hero_seat)
            prog = extract_program(text)
            res = run_program(prog, spot, timeout_s=REWARD_TIMEOUT_S, strict=True)   # anti-hang cap
            if not res["ok"]:
                out[j] = R_BAD
                bad += 1
                continue
            is_grounded = "api." in prog                              # derives via the engine (vs a gut decide)
            grounded += int(is_grounded)
            work.append((j, snap, res["action"], res["amount"], int(bseed), is_grounded))
        # PASS 2 (heavy): the k self-play rollouts per legal completion — fanned across the pool (REWARD_WORKERS>1) so the
        # GPU isn't starved, else sequential. CRN is per-completion (bseed), so parallelism is reward-identical.
        pool = _get_pool(REWARD_WORKERS)
        if pool is not None and work:
            futs = {pool.submit(_rollout_worker, (snap, hero_seat, action, amount, profiles, k, bseed, bb)):
                    (j, is_grounded) for (j, snap, action, amount, bseed, is_grounded) in work}
            for fut in futs:
                j, is_grounded = futs[fut]
                out[j] = _finalize(fut.result(), is_grounded, b)
        else:
            for (j, snap, action, amount, bseed, is_grounded) in work:
                ev = rollout_action_ev(snap, hero_seat, action, amount, cont,
                                       profiles=profiles, k=k, base_seed=bseed, bb=bb)
                out[j] = _finalize(ev, is_grounded, b)
        if log_metric:
            log_metric("frac_bad", bad / max(1, n))
            log_metric("engine_grounded_rate", grounded / max(1, n))   # the prior-suppression headline metric
        return out

    return ev_reward


def build_dataset(states: list, seed: int = 0):
    """(Dataset with 'prompt'+'sid'+'base_seed', snapshots side-table). 'prompt' is conversational (build_messages)."""
    from datasets import Dataset
    rows = [{"prompt": build_messages(spot), "sid": i, "base_seed": seed + i}
            for i, (snap, spot) in enumerate(states)]
    snapshots = [snap for snap, _ in states]
    return Dataset.from_list(rows), snapshots


# ---------------------------------------------------------------- trainer (pod GPU: torch/trl/peft)
def make_config(out_dir: str):
    """Build GRPOConfig DEFENSIVELY — filter to the params the INSTALLED trl actually accepts (TRL's API drifts; an
    unknown kwarg would otherwise raise TypeError and abort the run). Drops + logs anything the version lacks."""
    import inspect
    from trl import GRPOConfig
    want = dict(
        output_dir=out_dir,
        loss_type="dapo", epsilon=0.2, epsilon_high=0.28, beta=0.0,
        scale_rewards=False, mask_truncated_completions=True, num_iterations=1,
        num_generations=int(os.environ.get("NUM_GEN", "8")),
        generation_batch_size=int(os.environ.get("GEN_BATCH", "64")),
        max_completion_length=int(os.environ.get("MAX_COMP", "384")),
        temperature=1.0, top_p=1.0,
        learning_rate=1e-6, lr_scheduler_type="constant_with_warmup", warmup_ratio=0.03,
        per_device_train_batch_size=int(os.environ.get("PD_BATCH", "8")),
        gradient_accumulation_steps=1, gradient_checkpointing=True, bf16=True, max_grad_norm=1.0,
        logging_steps=int(os.environ.get("LOG_STEPS", "1")),   # every step -> the dashboard fills frequently (was 5)
        save_steps=int(os.environ.get("SAVE_STEPS", "100")),
        max_steps=int(os.environ.get("MAX_STEPS", "-1")),
        report_to="none", shuffle_dataset=True,
    )
    _lc = os.environ.get("LOG_COMPLETIONS", "0") == "1"   # OFF by default: TRL's completion printer crashes on Windows cp1252
    want["log_completions"] = _lc
    want["num_completions_to_print"] = 4 if _lc else 0
    if os.environ.get("USE_VLLM", "1") == "1":       # vLLM generation (pod); local uses transformers-gen (USE_VLLM=0)
        want["use_vllm"] = True
        want["vllm_gpu_memory_utilization"] = float(os.environ.get("VLLM_MEM", "0.3"))
        if os.environ.get("STRUCTURED", "1") == "1":
            want["vllm_structured_outputs_regex"] = dsl_grammar.vllm_regex()
    else:
        want["use_vllm"] = False
    valid = set(inspect.signature(GRPOConfig).parameters)
    dropped = sorted(k for k in want if k not in valid)
    if dropped:
        print(f"  (make_config: installed trl lacks {dropped} -> dropped; using defaults for those)", flush=True)
    return GRPOConfig(**{k: v for k, v in want.items() if k in valid})


def load_policy_model(base: str, adapter: str):
    """nf4 base + the SFT LoRA loaded is_trainable (CONTINUE the adapter — RL lifts the SFT init)."""
    import torch
    from peft import PeftModel, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    tok = AutoTokenizer.from_pretrained(base)
    tok.padding_side = "left"
    qc = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                            bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(base, quantization_config=qc, device_map="cuda")
    model = prepare_model_for_kbit_training(model)
    model = PeftModel.from_pretrained(model, adapter, is_trainable=True)
    return model, tok


def _callbacks(wallclock_s: float, metrics_path: str):
    """WallClockStop (hard budget deadline → save+stop) + JsonlMetrics (per-log JSONL for the live dashboard)."""
    from transformers import TrainerCallback

    class WallClockStop(TrainerCallback):
        def __init__(self, max_seconds, min_steps=8):
            self.deadline = time.time() + max_seconds
            self.min_steps = min_steps

        def on_step_end(self, args, state, control, **kw):
            if state.global_step >= self.min_steps and time.time() >= self.deadline:
                control.should_save = True
                control.should_training_stop = True
            return control

    class JsonlMetrics(TrainerCallback):
        KEYS = ("reward", "reward_std", "frac_reward_zero_std", "completions/mean_length",
                "completions/clipped_ratio", "entropy", "step_time", "clip_ratio/region_mean",
                "reward/ev_reward/mean", "frac_bad", "engine_grounded_rate", "loss")

        def __init__(self, path):
            self.path = path

        def on_log(self, args, state, control, logs=None, **kw):
            if not logs:
                return
            rec = {"step": state.global_step, "t": time.time()}
            rec.update({k: logs[k] for k in self.KEYS if k in logs})
            try:
                with open(self.path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(rec) + "\n")
            except Exception:  # noqa: BLE001 — never let logging crash training
                pass

    cbs = []
    if wallclock_s and wallclock_s > 0:
        cbs.append(WallClockStop(wallclock_s))
    if metrics_path:
        cbs.append(JsonlMetrics(metrics_path))
    return cbs


def _ensure_hashseed():
    """Re-exec ONCE with PYTHONHASHSEED=0 so card-string set/dict iteration is reproducible. Without a fixed hash seed the
    reward is non-reproducible run-to-run AND (critically) parallel reward workers disagree with each other -> a GRPO
    group's completions split across workers aren't CRN-comparable. os.execv keeps the same PID (campaign tracking intact)."""
    if os.environ.get("PYTHONHASHSEED") == "0":
        return
    import sys
    os.environ["PYTHONHASHSEED"] = "0"
    spec = getattr(sys.modules.get("__main__"), "__spec__", None)   # preserve `python -m pkg.mod` (the pod launch form)
    if spec is not None and spec.name:
        os.execv(sys.executable, [sys.executable, "-m", spec.name] + sys.argv[1:])
    os.execv(sys.executable, [sys.executable] + sys.argv)


def main():
    _ensure_hashseed()                                              # FIRST: deterministic hashing across main + pool workers
    from trl import GRPOTrainer
    from pokerbot.brain import modes
    modes.set_mode("train")                                          # RL throughput knobs (api.equity iters in the reward)
    base = os.environ.get("BASE", "Qwen/Qwen3-8B")
    adapter = os.environ.get("ADAPTER", "/root/qwen_poker_lora")
    out = os.environ.get("OUT", "/root/qwen_poker_grpo")
    n_states = int(os.environ.get("N_STATES", "2000"))
    seed = int(os.environ.get("SEED", "0"))
    wallclock_s = float(os.environ.get("WALLCLOCK_S", "0"))         # >0 -> hard deadline (the 40-60min budget guarantee)
    metrics_path = os.environ.get("METRICS_PATH", "/root/grpo_metrics.jsonl")
    print(f"building state buffer (n={n_states}) ...", flush=True)
    states = build_state_buffer(n_states, seed=seed)
    ds, snapshots = build_dataset(states, seed=seed)
    print(f"state buffer: {len(states)} learnable spots | dataset rows: {len(ds)}", flush=True)
    model, tok = load_policy_model(base, adapter)
    reward = make_ev_reward(snapshots)
    trainer = GRPOTrainer(model=model, reward_funcs=[reward], args=make_config(out),
                          train_dataset=ds, processing_class=tok,
                          callbacks=_callbacks(wallclock_s, metrics_path))
    trainer.train()
    trainer.save_model(out)
    sts = [h["step_time"] for h in trainer.state.log_history if "step_time" in h]
    if sts:
        print(f"STEP_TIME_S={sum(sts) / len(sts):.2f}", flush=True)   # the C2 probe's signal for dynamic MAX_STEPS
    print(f"SAVED GRPO adapter -> {out}", flush=True)


if __name__ == "__main__":
    main()
