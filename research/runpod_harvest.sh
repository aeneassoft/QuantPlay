#!/usr/bin/env bash
# Harvest the overnight solve: stop it, rebuild turn-advisor training data + retrain on the FULL cache.
# Run from a FILE (no inline-quoting/paren pitfalls). Then pull knowledge_base/postflop/turn_advisor.pt + --kill.
set -e
bash ~/PokerB/extraction/runpod_solve_stop.sh
cd ~/PokerB
echo "=== build_turn_data on the full cache ==="
PYTHONPATH=. python3 -m extraction.build_turn_data
echo "=== train_turn_advisor on the full cache ==="
PYTHONPATH=. OMP_NUM_THREADS=8 python3 -m extraction.train_turn_advisor
echo "=== turn_advisor.pt ==="
ls -la ~/PokerB/knowledge_base/postflop/turn_advisor.pt
