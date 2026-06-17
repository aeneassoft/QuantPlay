#!/usr/bin/env bash
# PokerB pod bootstrap — run ON the pod after SSH (image: runpod/pytorch:*-cuda*-devel; has sshd+python).
# Prepares the GTO self-play run. NOTE: an LLM in the loop must be SMALL (one GPU) — MiMo-V2-Flash (309B)
# and Kimi-K2.5 (1T) need ~8-GPU nodes, so they are NOT the on-pod model; use a 7-14B or API Haiku.
set -euo pipefail

echo "== deps =="
pip install -U numpy treys open_spiel anthropic openai >/dev/null
python -c "import torch; print('cuda:', torch.cuda.is_available(), torch.cuda.get_device_name(0))"

echo "== code =="
# code is transferred separately (scp/git). Expected layout: /root/PokerB/{pokerbot,extraction}
cd /root/PokerB

echo "== (optional) TexasSolver Linux for the GTO oracle / benchmark =="
# wget -q <TexasSolver-*-Linux.zip from github releases> -O ts.zip && unzip -q ts.zip -d tools/
# export TEXASSOLVER_DIR=/root/PokerB/tools/TexasSolver-*-Linux   (gto_oracle reads this env override)

echo "== (optional) small in-loop LLM via vLLM (7-14B, fits one GPU) =="
# pip install vllm && vllm serve Qwen/Qwen2.5-7B-Instruct --port 8001 &   # meta_coach(provider='openai', base_url=...)

echo "== GTO core (validated on Leduc; scale here) =="
echo "   python -u extraction/deep_cfr_nlhe.py <iters> <traversals>"
echo "   then: python -m pokerbot.benchmark.gto_benchmark   # selector / GTO-gap"
echo "bootstrap done — see POD_PLAN.md for the run sequence."
