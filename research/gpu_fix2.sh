#!/usr/bin/env bash
# Root cause: torch was upgraded to 2.6 but torchvision stayed at 2.4 -> torchvision::nms missing -> cascades
# into transformers' lazy import. qwen_sft is text-only -> just remove torchvision/torchaudio (memory lesson).
pkill -9 -f qwen_sft 2>/dev/null || true
pip uninstall -y torchvision torchaudio >~/uninstall.log 2>&1
python -c "from transformers import AutoModelForCausalLM; from peft import LoraConfig; from trl import SFTTrainer; print('IMPORTS_OK')"
cd ~
nohup env QUANT4=1 BATCH=2 MAXN=60000 EPOCHS=1 python -u qwen_sft.py > ~/train.log 2>&1 &
sleep 8
echo "RELAUNCHED pid=$!"
tail -4 ~/train.log
