#!/usr/bin/env bash
# Fix: transformers/peft 5.x need torch>=2.5 (set_submodule); the pod image ships torch 2.4.1. Upgrade torch.
pkill -9 -f qwen_sft 2>/dev/null || true
pip install -q -U torch --index-url https://download.pytorch.org/whl/cu124 >~/torch.log 2>&1
python -c "import torch; print('torch', torch.__version__, 'cuda', torch.cuda.is_available(), 'set_submodule', hasattr(torch.nn.Module,'set_submodule'))"
cd ~
nohup env QUANT4=1 BATCH=2 MAXN=60000 EPOCHS=1 python -u qwen_sft.py > ~/train.log 2>&1 &
sleep 8
echo "RELAUNCHED pid=$!"
