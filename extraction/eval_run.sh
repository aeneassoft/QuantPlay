#!/usr/bin/env bash
# Run the held-out LoRA eval detached to a log (survives ssh drops), wait on the pod for EVAL_DONE.
pkill -9 -f eval_lora.py 2>/dev/null || true
sleep 2
cd ~
nohup env BASE=Qwen/Qwen3-32B EVALN=60 PYTHONPATH=. python -u eval_lora.py > eval.log 2>&1 &
for i in $(seq 1 44); do
  grep -q EVAL_DONE eval.log 2>/dev/null && break
  grep -qE "Traceback|No module|CUDA out of memory|AssertionError" eval.log 2>/dev/null && break
  sleep 15
done
echo "==== eval.log tail ===="
tail -8 eval.log | tr -d '\r'
