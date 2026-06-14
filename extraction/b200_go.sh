#!/usr/bin/env bash
# B200 (Blackwell sm_100): stock torch 2.4+cu124 fails "no kernel image" -> install torch cu128 + drop torchvision.
# Then train Qwen3-32B in bf16 (no quant -> saturates the B200, best quality) on PokerBench, 1h-capped run.
set -e
echo "=== deps ==="
pip uninstall -y torchvision torchaudio >/dev/null 2>&1 || true
pip install -q transformers trl peft bitsandbytes datasets accelerate hf_transfer >~/pip.log 2>&1
echo "=== torch cu128 LAST so it wins (B200 sm_100) ==="
pip install -q -U torch --index-url https://download.pytorch.org/whl/cu128 >~/torch.log 2>&1
pip uninstall -y torchvision torchaudio >/dev/null 2>&1 || true
python -c "import torch; print('torch', torch.__version__); assert 'cu128' in torch.__version__, 'NOT cu128!'; print('cuda', torch.cuda.is_available(), torch.cuda.get_device_name(0))"
python -c "from transformers import AutoModelForCausalLM; from peft import LoraConfig; from trl import SFTTrainer; print('IMPORTS_OK')"
echo "=== launch Qwen3-32B bf16 ==="
cd ~
nohup env HF_HUB_ENABLE_HF_TRANSFER=1 BASE=Qwen/Qwen3-32B BATCH=8 SAVE_STEPS=150 MAXN=60000 EPOCHS=1 python -u qwen_sft.py > ~/train.log 2>&1 &
echo "LAUNCHED pid=$!"
sleep 6
tail -4 ~/train.log 2>/dev/null || echo "(log not ready)"
