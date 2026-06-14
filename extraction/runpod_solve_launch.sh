#!/usr/bin/env bash
# Launch the coverage mass_solve detached on a 32-vCPU RunPod CPU pod (turn + 3 stack depths), tar when done.
cd ~/PokerB
nohup bash -c 'env TEXASSOLVER_DIR=$HOME/texassolver/TexasSolver-v0.2.0-Linux PYTHONPATH=. \
  STACKS=50,100,200 DUMP=2 python3 -m extraction.mass_solve 240 14 2 > $HOME/solve.log 2>&1; \
  tar czf $HOME/cache.tgz -C $HOME/PokerB/data _gto_bench_cache' >/dev/null 2>&1 &
sleep 4
echo "LAUNCHED; solve.log:"; head -4 ~/solve.log 2>/dev/null || echo "(log not ready)"
