#!/usr/bin/env bash
# Train the Qwen LoRA on PokerBench (4-bit QLoRA) on a 24GB GPU pod. Deps then detached training + log.
pip install -q transformers trl peft bitsandbytes datasets accelerate >~/pip.log 2>&1
echo "deps: $(python -c 'import transformers,trl,peft,bitsandbytes,datasets; print("tf",transformers.__version__,"trl",trl.__version__,"bnb",bitsandbytes.__version__)' 2>&1 | tail -1)"
cd ~
nohup env QUANT4=1 BATCH=2 MAXN=60000 EPOCHS=1 python -u qwen_sft.py > ~/train.log 2>&1 &
sleep 8
echo "LAUNCHED pid=$!"
tail -6 ~/train.log 2>/dev/null || echo "(log not ready)"
