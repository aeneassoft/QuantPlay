# GLM-Z1-9B runbook — RunPod RTX PRO 6000 (Blackwell, 96 GB)

The GLM-Z1 SFT→RL run. **COMPUTE (corrected 2026-06-19):** the RTX PRO 6000 is a **RunPod pod** (96 GB) — the local PC is
an RTX 3080 Ti (12 GB), used for **$0 proofs only** (≤1.7B; the reward A/B). So the 9B run is ON THE POD → the pod
hardening (setsid watchdog + self-kill + EarlyAbort + pull-on-timeout) IS in force (the infra-fragility is real; my
earlier "local = no fragility" was on a wrong assumption). WHY + config + gates = `docs/RL_RUNCARD.md`; this is the HOW.

## ★ LAUNCH — one self-killing command (launch-ready; NO idle billing)
```bash
# provision RTX-PRO-6000 pod -> cu128 setup -> GLM download -> SFT(GATE 0) -> probe -> GRPO(GATE 2) -> eval -> SELF-KILL
GPU="<RunPod gpuTypeId for RTX PRO 6000>"      # from the RunPod console; "" -> the H100/H200 FAST-chain fallback
BASE=THUDM/GLM-Z1-9B-0414 GPU="$GPU" SCALE=1 python -u -m infra.runpod_rl_campaign
python -m infra.runpod_run --status            # MUST show NO pods after (self-kill verify)
```
`_train_env` auto-sets **bf16 (QLORA/QUANT4=0) + THINK_CAP_CHARS=1500 + TEMP=0.8 + flash_attn2** when `BASE` is GLM. The
campaign trains on the **DSL gold** (`registry.sft_gold()`; `c_decide` already holds PokerBench decisions in DSL form —
`SKIP_PB=1` avoids raw PokerBench, which re-spikes frac_bad). **First provision VERIFIES the Blackwell/GLM env** via
`pod_setup_rl.sh`'s bf16-matmul canary + `RL_SETUP_OK` (a bad cu128/sm_120-vLLM/GLM-transformers env → SETUP_FAILED →
self-kill, ~$1-2, not a silent burn). Honest: that env can't be pre-verified without provisioning — the canary is the gate.

## (reference) the manual steps the campaign automates — also the de-risk ladder if you ever train on local hardware

## 0. Environment (once) — Blackwell needs cu128
Blackwell (sm_120) has NO cubin in older torch/bnb/vLLM wheels → use cu128 builds (the B200 lesson). bf16 LoRA (NOT nf4)
on 96 GB → bnb-on-Blackwell is avoided entirely (`QLORA` unset).
```bash
pip install torch --index-url https://download.pytorch.org/whl/cu128
pip install -U "transformers>=4.51" "trl>=0.15" peft datasets accelerate hf_transfer
pip install flash-attn --no-build-isolation        # then export ATTN=flash_attention_2 (else default sdpa works)
# vLLM: MUST be a cu128 / sm_120 build. VERIFY a 1-prompt gen BEFORE training (the torch path is the only real risk):
python -c "import vllm, torch; print(torch.__version__, torch.cuda.get_device_name(0))"
```

## 1. Download GLM-Z1-9B
```bash
HF_HUB_ENABLE_HF_TRANSFER=1 huggingface-cli download THUDM/GLM-Z1-9B-0414
```

## 2. ★ LOAD-BEARING GLM-template checks (do BEFORE training — these are the frac_bad=0.93 / garbage-SFT traps)
```python
from transformers import AutoTokenizer
from pokerbot.brain.policy import build_messages          # our canonical [system,user] prompt
tok = AutoTokenizer.from_pretrained("THUDM/GLM-Z1-9B-0414", trust_remote_code=True)
# (a) does add_generation_prompt open <think>?  build_dataset appends it if not — confirm which path you're on:
s = tok.apply_chat_template([{"role":"user","content":"hi"}], tokenize=False, add_generation_prompt=True)
print("ends with <think>:", s.rstrip().endswith("<think>"))
# (b) does the template carry the {% generation %} block that assistant_only_loss needs?  If NOT, SFT masks NOTHING ->
#     loss on the prompt -> garbage SFT. Check for the marker; if absent, set ASSIST_ONLY=0 and add a GLM
#     DataCollatorForCompletionOnlyLM(response_template="<|assistant|>") fallback in qwen_sft.
print("has generation block:", "{% generation %}" in (tok.chat_template or ""))
```
If (a) is False → already handled (`build_dataset` appends `<think>`). If (b) is False → wire the GLM response-template
fallback before SFT (else GATE 0 will look fine on loss but the model learns nothing useful).

## 3. SFT (GATE 0) — bf16 LoRA, PokerBench spine + our gold
```bash
BASE=THUDM/GLM-Z1-9B-0414 QUANT4=0 ATTN=flash_attention_2 \
DSL=dataset/shards/a_contract.jsonl,dataset/shards/c_decide.jsonl,dataset/shards/solver.jsonl,dataset/shards/solver_mass.jsonl \
OUT=./glm_poker_lora EPOCHS=2 BATCH=16 MAX_LEN=2048 \
python -u -m training.qwen_sft
```
(Default mode mixes PokerBench 560k + DSL; `SKIP_PB=1` for DSL-only/faster.) **GATE 0:** PokerBench-acc ≥70% (our Qwen hit
71.7% → feasible) + frac_bad <10% on the local test fold (`dataset/shards/streets/test_holdout.jsonl`).
**SFT-target note:** GLM reasons at inference; consider teaching a BOUNDED `<think>` in the targets (≤~400 tok) if frac_bad
is high — RL won't fix a model SFT'd to ramble.

## 4. The 20-step GRPO SMOKE ($0, minutes) — the spend-gate replacement (Claude de-risk Step 3)
```bash
PYTHONHASHSEED=0 BASE=THUDM/GLM-Z1-9B-0414 QLORA=0 ATTN=flash_attention_2 \
ADAPTER=./glm_poker_lora OUT=./glm_poker_grpo_smoke \
USE_VLLM=1 STRUCTURED=1 THINK_CAP_CHARS=1500 TEMP=0.8 \
R_BAD=-3 BETA=0.0 MAX_STEPS=20 N_STATES=200 NUM_GEN=8 K_ROLL=8 \
REWARD_WORKERS=$(($(nproc)-2)) METRICS_PATH=./smoke.jsonl WALLCLOCK_S=0 \
python -u -m training.qwen_grpo
```
**Smoke GATES (all must hold to proceed):** `frac_bad < 0.1` · `reward_std > 0` · completions show `</think>` then a valid
program (eyeball a few) · entropy not collapsing · `EarlyAbort` did NOT fire. If `completions/clipped_ratio` is high →
lower `THINK_CAP_CHARS`, not `MAX_COMP`.

## 5. The full RL run (GATE 2) — bigger group + the DYNAMIC buffer (the #1 lift lever)
Same env as §4 but: `NUM_GEN=16 GEN_BATCH=128 PD_BATCH=16 MAX_COMP=768 VLLM_MEM=0.45 N_STATES=4000 MAX_STEPS=-1`.
- **DYNAMIC buffer (OpenAI's #1 lever — static buffer = "looks healthy but no lift"):** run in **2 phases** — N steps →
  stop → re-run from the ckpt (rebuilds `build_state_buffer` with a fresh seed) → resume. Monitor `frac_reward_zero_std`;
  if >0.6 sustained, raise `spread_eps` (in `build_state_buffer`) and rebuild.
- **Mid-run bb/100 vs the FROZEN SFT**, not just internal reward: when reward plateaus ~100 steps, eval the ckpt vs the
  league (`qwen_eval_gto`). **GATE 2 = RL > SFT-init in bb/100.** No lift → debug (reward variance / league / buffer)
  BEFORE more steps.
- **EV must dominate:** if shaping/format > ~30% of within-group reward variance, `R_FMT 2→1`, `GROUND_B0 1→0.5`.

## 6. Local de-risk (replaces SSH/scp/watchdog)
| pod | local |
|---|---|
| SSH launch | `tmux new -s grpo` → run → detach (survives disconnect) |
| setsid watchdog / pull-on-timeout / network volume | **drop** — `OUT`/`METRICS_PATH` are local NVMe; nothing to lose |
| `WallClockStop` | `WALLCLOCK_S=0` (free local; the gate is your time, + `EarlyAbort` on) |
| dashboard | `tail -f ./*.jsonl` → the existing `pokerbot.web.train_dashboard` pointed at the local path |

## 7. Measure → leaderboard
Eval the lifted adapter vs the held-out league + vs GTOW under the fresh **"Nutzz"** key (you register it on GTOW). Report
bb/100 ± SE. Track −28.55 (Claude) as the bar a 9B can't be expected to match out-of-box — the value is OURS + RL-able.
```bash
ADAPTER=./glm_poker_grpo  python -m pokerbot.benchmark.slumbot_llm --hands 1000 --base THUDM/GLM-Z1-9B-0414 --adapter ...
# + the gtow_client --agent-type qwen path with the GLM base/adapter (wire the GLM base into slumbot_llm._load).
```
