#!/usr/bin/env bash
# Launch the mass_solve coverage run detached on the VM (turn + 3 stack depths), then tar the cache when done.
cd ~/PokerB
nohup bash -c 'env TEXASSOLVER_DIR=$HOME/texassolver/TexasSolver-v0.2.0-Linux PYTHONPATH=. \
  STACKS=50,100,200 DUMP=2 python3 -m extraction.mass_solve 180 4 2 > $HOME/solve.log 2>&1; \
  tar czf $HOME/cache.tgz -C $HOME/PokerB/data _gto_bench_cache' >/dev/null 2>&1 &
sleep 4
echo "LAUNCHED pid in background; solve.log so far:"
head -4 ~/solve.log 2>/dev/null || echo "(log not ready yet)"
