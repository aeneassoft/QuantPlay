#!/usr/bin/env bash
# Robust H200 setup + launch for Qwen3-32B on PokerBench. set -e gates EVERY step: if torch/cuda/imports
# fail, it aborts BEFORE launching the long run. Hopper (sm_90) => torch's SDPA uses the fast flash kernel
# (no cu128 / no flash-attn compile needed). Picks bf16 (>=130GB VRAM) else 4-bit QLoRA.
set -e
echo "=== drop torchvision/torchaudio + deps ==="
pip uninstall -y torchvision torchaudio >/dev/null 2>&1 || true
pip install -q transformers trl peft bitsandbytes datasets accelerate hf_transfer >~/pip.log 2>&1
echo "=== torch (>=2.5 for set_submodule) on cu124 -- Hopper sm_90, fast SDPA ==="
pip install -q -U torch --index-url https://download.pytorch.org/whl/cu124 >~/torch.log 2>&1
pip uninstall -y torchvision torchaudio >/dev/null 2>&1 || true
echo "=== VERIFY (set -e aborts if any assert fails) ==="
QUANT=$(python - <<'PY'
import torch, sys
assert "cu12" in torch.__version__, "torch not cuda12: " + torch.__version__
assert hasattr(torch.nn.Module, "set_submodule"), "torch too old (no set_submodule): " + torch.__version__
assert torch.cuda.is_available(), "cuda not available"
from transformers import AutoModelForCausalLM
from peft import LoraConfig
from trl import SFTTrainer
mem = torch.cuda.get_device_properties(0).total_memory / 1e9
sys.stderr.write(f"torch {torch.__version__} | GPU {torch.cuda.get_device_name(0)} | VRAM {mem:.0f}GB | IMPORTS_OK\n")
print("0" if mem >= 130 else "1")   # bf16 on big VRAM, else 4-bit QLoRA
PY
)
echo "QUANT4=$QUANT (0=bf16 full quality, 1=4-bit)"
echo "=== launch Qwen3-32B (sdpa, QUANT4=$QUANT) ==="
cd ~
nohup env HF_HUB_ENABLE_HF_TRANSFER=1 ATTN=sdpa QUANT4=$QUANT BASE=Qwen/Qwen3-32B BATCH=8 SAVE_STEPS=200 MAXN=100000 EPOCHS=1 python -u qwen_sft.py > ~/train.log 2>&1 &
echo "LAUNCHED pid=$!"
sleep 8
tail -3 ~/train.log 2>/dev/null || echo "(log not ready yet)"
