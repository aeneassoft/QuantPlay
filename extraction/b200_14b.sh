#!/usr/bin/env bash
# 32B did not fit the 60GB container disk -> Qwen3-14B (fits, still big, completes within the 1h cap).
pkill -9 -f qwen_sft 2>/dev/null || true
sleep 2
rm -rf ~/.cache/huggingface
echo CACHE_CLEARED
df -h / | tail -1
cd ~
nohup env HF_HUB_ENABLE_HF_TRANSFER=1 BASE=Qwen/Qwen3-14B BATCH=16 SAVE_STEPS=150 MAXN=60000 EPOCHS=1 python -u qwen_sft.py > ~/train.log 2>&1 &
echo "RELAUNCHED_14B pid=$!"
sleep 7
tail -3 ~/train.log | tr -d '\r'
