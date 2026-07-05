#!/usr/bin/env bash
# Pod stack for the Qwen runs. TEACHER=1 -> LEAN (vLLM generation only: vllm+transformers+engine); else the full
# SFT/GRPO training stack (+trl/peft/bitsandbytes/datasets/accelerate). Prints RL_SETUP_OK on success (orchestrator
# greps it); on ANY error the ERR trap dumps the pip logs so the real cause is visible (not masked by an ssh warning).
set -e
cd /root
# Ubuntu 24.04 marks the system python as PEP-668 "externally-managed" -> `pip install` REFUSES without this (the
# real cause of the line-11 setup failure once we moved to the ubuntu2404 image). Set globally so every pip respects it.
export PIP_BREAK_SYSTEM_PACKAGES=1
PIP="python3 -m pip"                                                       # the python that HAS torch (a bare `pip` may point elsewhere)
trap 'echo "SETUP_FAILED (line $LINENO)"; for L in pip_engine pip_vllm pip_rl; do echo "--- $L.log ---"; tail -30 ~/$L.log 2>/dev/null; done' ERR

echo "  python: $(python3 --version 2>&1) | torch: $(python3 -c 'import torch;print(torch.__version__)' 2>&1)"
$PIP install -q treys numpy >~/pip_engine.log 2>&1                          # engine deps (table / equity / rl_env)

# Pin the IMAGE's torch so pip resolves a COMPATIBLE vLLM instead of dragging in a mismatched torch (cu124/torch2.4 ->
# ABI undefined-symbol; cu130 -> missing libnvJitLink). "2.8.0+cu128" satisfies "==2.8.0", so the image torch is KEPT.
TORCH_PIN=$(python3 -c "import torch; print('torch=='+torch.__version__.split('+')[0])" 2>/dev/null || echo "")
echo "  image torch pin: ${TORCH_PIN:-<none>}"
# vLLM 0.11.0 only requires transformers>=4.55.2 (open upper bound) -> pip would grab the LATEST (4.57+), whose slow
# Qwen2Tokenizer dropped `all_special_tokens_extended` that vLLM 0.11.0 accesses -> crash at model load. Pin to vLLM's
# era (4.55.2..4.56.x) so the tokenizer API matches. (vLLM = xgrammar backend + tokenizer = all the TEACHER needs.)
$PIP install -q ${TORCH_PIN} vllm "transformers>=4.55.2,<4.57" hf_transfer >~/pip_vllm.log 2>&1   # hf_transfer: the ENV sets HF_HUB_ENABLE_HF_TRANSFER=1 -> fast model download (REQUIRED, else the load errors out)

if [ "${TEACHER:-0}" != "1" ]; then                                        # full training stack (NOT needed for teacher generation)
  $PIP install -q --upgrade-strategy only-if-needed ${TORCH_PIN} "trl>=0.22" peft bitsandbytes datasets accelerate hf_transfer >~/pip_rl.log 2>&1
fi

# Fallback: image had NO torch AND Blackwell -> force a cu128 torch (sm_100/103 needs CUDA >= 12.8).
if [ -z "$TORCH_PIN" ] && [ "${B200:-0}" = "1" ]; then
  echo "  no image torch -> forcing cu128 for Blackwell"
  $PIP uninstall -y torchvision torchaudio >/dev/null 2>&1 || true
  $PIP install -q -U torch --index-url https://download.pytorch.org/whl/cu128 >~/torch_cu128.log 2>&1
fi

# Verify: imports + a REAL bf16 GPU matmul (the kernel canary; is_available() passes even when sm kernels are missing).
if [ "${TEACHER:-0}" = "1" ]; then
  python3 -c "import torch,transformers,vllm; cap=torch.cuda.get_device_capability(0); x=torch.randn(2048,2048,device='cuda',dtype=torch.bfloat16); assert torch.isfinite((x@x).float().sum()), 'matmul NaN'; print(f'TEACHER deps OK | torch {torch.__version__} | cuda {torch.version.cuda} | sm_{cap[0]}{cap[1]} | {torch.cuda.get_device_name(0)} | vllm {vllm.__version__} | transformers {transformers.__version__} | bf16 OK')"
else
  python3 -c "import torch,transformers,trl,peft,datasets,vllm,importlib.util; cap=torch.cuda.get_device_capability(0); x=torch.randn(2048,2048,device='cuda',dtype=torch.bfloat16); assert torch.isfinite((x@x).float().sum()), 'matmul NaN'; bnb=importlib.util.find_spec('bitsandbytes') is not None; print(f'RL deps OK | torch {torch.__version__} | cuda {torch.version.cuda} | sm_{cap[0]}{cap[1]} | {torch.cuda.get_device_name(0)} | trl {trl.__version__} | vllm {vllm.__version__} | bnb_available={bnb} (bf16/QLORA=0 needs none) | bf16 OK')"
fi
echo "RL_SETUP_OK"
