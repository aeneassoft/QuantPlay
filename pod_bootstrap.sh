#!/bin/bash
set -e
cd /workspace/PokerB
pip install -q -r requirements.txt
python -m pokerbot.benchmark.runpod_train --pop 300 --hands 300 --iters 200 --workers $(nproc)
echo DONE: knowledge_base/exploit/stack_depth_params.json
