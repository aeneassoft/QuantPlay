#!/usr/bin/env bash
# 32B bf16 runs ~15.5 s/it on the H200 (heavy model, ~20% MFU). 100k rows = ~8.5h -> too long/costly.
# Shrink to 25k rows so it finishes in ~2h / ~$9. Model already cached -> no re-download.
pkill -9 -f qwen_sft 2>/dev/null || true
sleep 3
cd ~
nohup env HF_HUB_ENABLE_HF_TRANSFER=1 ATTN=sdpa QUANT4=0 BASE=Qwen/Qwen3-32B BATCH=8 SAVE_STEPS=150 MAXN=25000 EPOCHS=1 python -u qwen_sft.py > ~/train.log 2>&1 &
echo "RELAUNCHED pid=$!"
sleep 8
tail -3 ~/train.log | tr -d '\r'
