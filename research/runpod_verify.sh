#!/usr/bin/env bash
# End-to-end validation on the pod: imports OK + a short turn-coverage test solve actually produces cache files.
pkill -f console_solver 2>/dev/null; sleep 1
cd ~/PokerB || exit 1
TS_DIR=$(dirname "$(find ~/texassolver -iname 'console_solver*' | head -1)")
echo "TS_DIR=$TS_DIR"
PYTHONPATH=. python3 -c "from pokerbot import config; from pokerbot.strategy import gto_oracle; from pokerbot.benchmark.gto_benchmark import _IP,_OOP; from pokerbot.strategy.distill import CARDS, SMALL_BETS; print('IMPORTS_OK cards=%d bets=%s'%(len(CARDS), SMALL_BETS))" || { echo IMPORT_FAIL; exit 2; }
echo "--- 1.5-min test solve (DUMP=2 turn, 4 workers) ---"
env TEXASSOLVER_DIR="$TS_DIR" PYTHONPATH=. STACKS=100 DUMP=2 python3 -m extraction.mass_solve 1.5 4 2 2>&1 | tail -6
echo "--- cache files after test ---"; ls ~/PokerB/data/_gto_bench_cache 2>/dev/null | wc -l
