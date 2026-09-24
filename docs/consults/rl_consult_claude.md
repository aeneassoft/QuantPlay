# RL consult — Claude (technical implementation in our build)

> **About this document.** Verbatim transcript (truncated at the end) of a technical consultation with Claude (June 2026, committed 2026-07-05) on implementing the GLM-Z1-9B RL lift in this codebase on a local RTX PRO 6000 (Blackwell sm_120, 96 GB, cu128 torch) instead of a RunPod pod. It reviews `training/qwen_grpo.py`, `brain/policy.py`, `brain/dsl_grammar.py` and `training/qwen_sft.py` and gives exact configs.
> **English transcript, kept verbatim; what was adopted is recorded in docs/STATE.md and ../catalogs/MEASUREMENT_CATALOG.md.**
> Main conclusions:
> - `enable_thinking=False` is a Qwen3-only template kwarg; GLM-Z1 always opens `<think>`, so thinking must be BOUNDED, not disabled: a grammar-level think cap (THINK_CAP_CHARS=1500 inside MAX_COMP=768) and `extract_program` taking everything after the last `</think>`.
> - Drop QLoRA/bitsandbytes on sm_120 and use bf16 LoRA; the SFT completion-only loss must mask on GLM's `<|assistant|>` marker, not Qwen's.
> - Replace the pod mechanics with a local de-risk ladder (tmux, an EarlyAbort callback on frac_bad, a free 20-step smoke run); the R_BAD=-3 fix must survive, group size NUM_GEN=16 and REWARD_WORKERS are the throughput/variance levers.


Below is the concrete lift plan against the files you showed. I flag every place the current code will silently or loudly break on GLM-Z1 + Blackwell.

---

## 0. Things in the shown code that WILL break the GLM lift (fix before anything)

1. **`build_dataset(..., enable_thinking=False)` and `main()`'s `_tok.apply_chat_template(..., enable_thinking=False)`** — `enable_thinking` is a **Qwen3-only** jinja kwarg. GLM-Z1's chat template doesn't read it, so the kwarg is **silently ignored**. GLM-Z1 is reasoning-tuned and *always* opens `<think>`. Result: the exact failure your runcard warns about (Qwen3 `frac_bad=0.93`) but guaranteed, because you can't turn GLM thinking off. **You must BOUND, not disable.**
2. **`vllm_structured_outputs_regex = dsl_grammar.vllm_regex()`** constrains the *entire* completion to pure DSL. With GLM forced to reason first, a program-only regex makes `<think>` ungrammatical → either degenerate output or you've thrown away GLM-Z1's whole reason for existing. The regex must allow a bounded think prefix.
3. **`load_policy_model` uses nf4 + bitsandbytes.** On Blackwell sm_120 the bnb kernels need a very recent bnb built against cu128; older bnb has no sm_120 cubin → import/runtime crash. With 96 GB you don't need QLoRA for a 9B anyway. **Drop QLoRA, go bf16 LoRA.**
4. **`VLLM_MEM=0.3` / `MAX_COMP=384`** are tuned for a 24 GB pod and non-thinking Qwen. Both are wrong for GLM bounded-think on 96 GB (cap too short for think+program; mem util needlessly low).
5. **`temperature=1.0`** with a reasoning model inflates `frac_bad`; GLM-Z1's recommended sampling is ~0.6. Use 0.8 for RL exploration.
6. **vLLM/torch wheels**: TRL colocate needs a vLLM built against **cu128** with sm_120. CPU-side reward code is fine; the torch path is the risk.

---

## 1. GLM-Z1-9B wiring

### 1a. `brain/policy.py` — `extract_program` (not shown, but contract is load-bearing)
GLM-Z1's template opens `<think>` in the *prompt*, so the **completion** looks like:
```
<reasoning text></think>\n<dsl program>
```
i.e. the opening `<think>` is NOT in the completion. `extract_program` must:
```python
def extract_program(text: str) -> str:
    # GLM-Z1: prompt opens <think>; completion = reasoning </think> program
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[1]
    # back-compat: also strip a leading <think>...</think> if both present (SFT/teacher data)
    text = re.sub(r"(?s)^.*?</think>", "", text, count=1) if "</think>" in text else text
    return text.strip()
```
Take everything **after the last `</think>`**. If `</think>` never appears (think overran the cap), return `""` → `run_program` rejects → `R_BAD`. That's the desired pressure.

### 1b. `brain/dsl_grammar.py` — `vllm_regex()` must wrap a bounded think
Add a think-prefix wrapper so the grammar *enforces* `</think>` within a char budget — this is the bounded-thinking enforcement at the sampler level (cleanest place to do it):
```python
def vllm_regex(think_cap_chars: int | None = None) -> str:
    prog = _program_regex()  # your existing pure-DSL regex
    if think_cap_chars is None:
        return prog
    # completion: <reasoning up to N chars></think> whitespace <program>
    return rf"(?s).{{0,{think_cap_chars}}}</think>\s*{prog}"
```
With `(?s)` so `.` spans newlines. The `{0,N}` is the hard bound: vLLM literally cannot sample past N think chars without emitting `</think>`, so the program always gets room inside `max_completion_length`. This is your structural defense against the frac_bad=0.93 failure — stronger than relying on a soft prompt.

### 1c. `training/qwen_grpo.py` — `build_dataset`
Replace the Qwen thinking branch with a GLM-aware render:
```python
def build_dataset(states, tok=None, seed=0):
    from datasets import Dataset
    def _prompt(spot):
        msgs = build_messages(spot)
        if tok is None:
            return msgs
        # GLM-Z1: DO NOT pass enable_thinking. Let the template open <think>.
        return tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    rows = [{"prompt": _prompt(spot), "sid": i, "base_seed": seed + i}
            for i, (snap, spot) in enumerate(states)]
    return Dataset.from_list(rows), [snap for snap, _ in states]
```
**Verify** GLM-Z1's template actually auto-appends `<think>` after `add_generation_prompt=True` (some 0414 templates don't). If it does NOT, append it yourself: `return rendered + "<think>"`. Test once: `print(tok.apply_chat_template(build_messages(spot), tokenize=False, add_generation_prompt=True))` and confirm it ends in `<think>`.

### 1d. `make_config` — bounded-think regex + sampling
```python
want["temperature"] = float(os.environ.get("TEMP", "0.8"))
...
if os.environ.get("STRUCTURED", "1") == "1":
    cap = int(os.environ.get("THINK_CAP_CHARS", "1500"))
    want["vllm_structured_outputs_regex"] = dsl_grammar.vllm_regex(think_cap_chars=cap)
```
1500 chars ≈ ~450 think tokens, leaving ~300 for the program inside MAX_COMP=768. Add a `completions/clipped_ratio` watch: if it climbs, lower THINK_CAP_CHARS, not MAX_COMP.

### 1e. `load_policy_model` — bf16 LoRA (drop bnb)
```python
def load_policy_model(base, adapter):
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(base, trust_remote_code=True)
    tok.padding_side = "left"
    model = AutoModelForCausalLM.from_pretrained(
        base, torch_dtype=torch.bfloat16, device_map="cuda",
        trust_remote_code=True, attn_implementation="flash_attention_2")
    model = PeftModel.from_pretrained(model, adapter, is_trainable=True)
    return model, tok
```
`trust_remote_code=True` (GLM-4/Z1 ship custom modeling). Keep a `QLORA=1` env fallback that re-adds the BitsAndBytesConfig path only if you ever need the $50 pod. On the 6000, bf16.

### 1f. `main()` — base default + tokenizer
```python
base = os.environ.get("BASE", "THUDM/GLM-Z1-9B-0414")
...
_tok = AutoTokenizer.from_pretrained(base, trust_remote_code=True)
```

---

## 2. Exact LOCAL config — RTX PRO 6000 (sm_120, 96 GB, cu128 torch)

**Environment (once):**
```bash
pip install torch --index-url https://download.pytorch.org/whl/cu128
pip install -U "transformers>=4.51" "trl>=0.15" peft datasets accelerate
pip install flash-attn --no-build-isolation
# vLLM: must be a cu128/sm_120 build; verify import + a 1-prompt gen before training
```

### 2a. SFT — `training/qwen_sft.py` (GLM, bf16 LoRA)
GLM-Z1-9B bf16 ≈ 18 GB; LoRA params + Adam states tiny; activations at seq 2048 with checkpointing ~ a few GB. 96 GB is wildly comfortable.

| knob | value | note |
|---|---|---|
| base | `THUDM/GLM-Z1-9B-0414` | `trust_remote_code=True` |
| precision | **bf16 LoRA** (no nf4) | bnb on sm_120 is the risk; you have the VRAM |
| LoRA | r=32, alpha=64, dropout=0.05, target=q/k/v/o + gate/up/down | |
| seq_len | 2048 (packing on) | think+program targets fit |
| lr | **1e-4** cosine, warmup 0.03 | SFT lr (100× the RL lr) |
| per_device_batch | 16, grad_accum 2 (eff 32) | room for 32–48 if activations allow |
| epochs | 1–2 over the mixed spine | |
| chat template | GLM; **completion-only loss masked on `<|assistant|>`** | see below |
| attn | flash_attention_2 | |

**Critical SFT-side break to fix:** the `DataCollatorForCompletionOnlyLM` response template must be GLM's assistant marker, not Qwen's `<|im_start|>assistant`. For GLM-4/Z1 it's the `<|assistant|>` token sequence. If you leave a Qwen template, *no tokens get masked* → loss on the prompt → garbage SFT. In `qwen_sft.py` wherever you set `response_template=`, switch to the GLM one and assert the collator finds it (TRL warns "could not find response template" — treat that warning as fatal).

**SFT targets must teach bounded think**: gold rows = `<think>{≤~400-token rationale}</think>\n{dsl program}`. Truncate teacher/solver rationales at build time so the model *learns* to keep think short — RL alone won't fix a model SFT'd to ramble. This is GATE 0 insurance.

### 2b. GRPO — exact env for the run
```bash
PYTHONHASHSEED=0 \
BASE=THUDM/GLM-Z1-9B-0414 \
ADAPTER=./glm_poker_lora \
OUT=./glm_poker_grpo \
USE_VLLM=1 STRUCTURED=1 \
VLLM_MEM=0.45 \
NUM_GEN=16 \
GEN_BATCH=128 \
PD_BATCH=16 \
MAX_COMP=768 \
THINK_CAP_CHARS=1500 \
TEMP=0.8 \
BETA=0.0 \
R_BAD=-3 R_CLIP=25 R_FMT=2 \
K_ROLL=16 \
GROUND_B0=1.0 GROUND_DECAY=200 \
REWARD_WORKERS=$(($(nproc)-2)) \
N_STATES=4000 \
METRICS_PATH=./grpo_metrics.jsonl \
WALLCLOCK_S=0 \
python -u -m training.qwen_grpo
```

Memory math (colocate): GLM bf16 policy 18 GB + LoRA/optimizer/grads ~3 GB + activations (PD_BATCH=16 × 768 tok, checkpointed) ~10–15 GB + vLLM at `VLLM_MEM=0.45` ≈ 43 GB (weights copy + KV cache for G=16). Total ~75–80 GB on 96 — headroom for the long-completion KV spikes. If you see vLLM OOM, drop `VLLM_MEM` to 0.40 before touching batch.

Notes:
- `NUM_GEN=16` (your runcard's "if throughput allows") — the 6000 + REWARD_WORKERS pool makes it affordable; bigger G = lower-variance group advantage = the single best lift lever after the R_BAD fix.
- `REWARD_WORKERS` is the load-bearing throughput knob: vLLM gen is fast, the GEN_BATCH×K_ROLL=128×16=2048 CRN rollouts/step are the CPU bottleneck. Fan them. Confirm spawn workers re-import cleanly with `trust_remote_code` not pulling torch (they don't — reward path imports no torch; good).
- Keep `gradient_checkpointing=True`, `bf16=True` — already correct in `make_config`.

---

## 3. De-risk ladder, LOCAL (replace SSH/scp/watchdog)

| pod mechanism | local replacement |
|---|---|
| `$50 RunPod`, SSH launch | `tmux new -s grpo` then run; detach. Survives terminal/SSH death without setsid. |
| `setsid` watchdog (PC-death) | unneeded — model writes to local disk continuously; nothing to lose to a dropped connection. For UPS-grade safety use `systemd-run --user --scope` so a logout doesn't SIGHUP it. |
| `pull-on-timeout` / scp the model back | **delete** — `OUT=./glm_poker_grpo` is already local. Drop the whole pull-on-timeout phase. |
| network volume | local NVMe; just ensure `OUT` and `METRICS_PATH` are on the fast disk, not a network mount. |
| `WallClockStop` | keep but **set `WALLCLOCK_S=0`** locally — you're not renting by the hour. Cost gate is now *your time*, not dollars. |
| dashboard over SSH tail | `tail -f ./grpo_metrics.jsonl` + your existing JSONL dashboard pointed at the local path. |

**Step 1 ($0 A/B = SPEND→TIME gate):** the A/B that matters is *reward-shape*, and it's model-agnostic and torch-free. Run `build_state_buffer` + `make_ev_reward` on synthetic completions (mix of valid/invalid) with `R_BAD=-30` vs `R_BAD=-3`, assert: control reward correlates with `frac_bad`, fixed reward is EV-centered and *decoupled* from `frac_bad`. This needs no GLM and no GPU — keep it exactly as the runcard describes. Green → proceed.

**Step 2 (early-abort):** the runcard wants it; the code doesn't have it. **Add this callback** in `_callbacks`:
```python
class EarlyAbort(TrainerCallback):
    def __init__(self, check_step=5, frac_bad_max=0.5):
        self.cs, self.fbm = check_step, frac_bad_max
    def on_log(self, args, state, control, logs=None, **kw):
        if logs and state.global_step >= self.cs and logs.get("frac_bad", 0) > self.fbm:
            print(f"EARLY ABORT: frac_bad={logs['frac_bad']:.2f} > {self.fbm} @ step {state.global_step}", flush=True)
            control.should_training_stop = True
        return control
```
and append `cbs.append(EarlyAbort())`. Locally a broken run dies in minutes of *your* time instead of $3.

**Step 3 (spend gate is now free):** because the 6000 runs the real 9B locally for free, do a real **20-step smoke run** of GLM-Z1 at `MAX_STEPS=20 N_STATES=200` and read: `frac_bad < 0.1`, `reward_std > 0`, completions show `</think>` before the program. That replaces the "is the fix EV-centered" pod test with the actual model — strictly better and costs nothing.

---

## 4. Precise changes that make RL actually LIFT

These are the deltas beyond wiring that move GATE 2.

1. **The R_BAD=-3 fix is already in** — verify it survives: `R_BAD` env unset in your launch so it defaults to -3. Do **not** export the old -30 anywhere in your shell profile. This is the #1 reason the lift never worked.

2. **Bounded think is the second load-bearing fix.** With GLM you *cannot* set thinking off, so the grammar-level `THINK_CAP_CHARS` in 1b/1d is what prevents the `frac_bad=0.93` reward collapse. Without it, advantage is dominated by clip-truncation noise, not EV → flat reward → no lift. Treat `completions/clipped_ratio` as a GATE-1 blocker.

3. **Raise group size to 16** (`NUM_GEN=16`). The ±5 bb EV spread is small; group-relative
