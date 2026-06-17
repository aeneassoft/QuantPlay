#!/usr/bin/env bash
# Robust MULTI-HOUR turn-coverage solve on a RunPod CPU pod. Must NOT abort during the hours:
#   - nohup            -> survives SSH disconnect
#   - restart loop     -> a crashed/OOM chunk auto-resumes (mass_solve skips already-cached boards atomically)
#   - per-board atomic  -> a kill mid-write never corrupts the cache
# Turn coverage = STACKS=50,100,200 + DUMP=2 (flop+turn). Run ON the pod:  HOURS=6 bash runpod_solve_robust.sh
cd ~/PokerB || { echo "no ~/PokerB"; exit 1; }
HOURS=${HOURS:-6}
STREET=${STREET:-3}                                  # 3=flop coverage (default), 5=river-subgame coverage
TS_BIN=$(find ~/texassolver -type f -iname 'console_solver*' 2>/dev/null | head -1)
TS_DIR=$(dirname "$TS_BIN")
if [ -z "$TS_BIN" ]; then echo "TexasSolver console_solver NOT found under ~/texassolver"; exit 2; fi
echo "TEXASSOLVER_DIR=$TS_DIR | HOURS=$HOURS | cores=$(nproc)"

nohup bash -c '
  cd ~/PokerB
  echo $$ > ~/solve.pid
  END=$(( $(date +%s) + '"$HOURS"' * 3600 ))
  i=0
  while [ $(date +%s) -lt $END ]; do
    i=$((i+1))
    USED=$(df -BG --output=used ~/PokerB/data | tail -1 | tr -dc 0-9)
    if [ "${USED:-0}" -ge 28 ]; then echo "[disk guard: ${USED}G used >= 28G -> stop cleanly]" >> ~/solve.log; break; fi
    echo "[chunk $i START $(date -u)] cache=$(ls data/_gto_bench_cache 2>/dev/null | wc -l)" >> ~/solve.log
    env TEXASSOLVER_DIR="'"$TS_DIR"'" PYTHONPATH=. STACKS=50,100,200 DUMP=2 STREET='"$STREET"' \
        python3 -m extraction.mass_solve 55 14 2 >> ~/solve.log 2>&1
    echo "[chunk $i EXIT rc=$? $(date -u)] cache=$(ls data/_gto_bench_cache 2>/dev/null | wc -l)" >> ~/solve.log
    sleep 3
  done
  tar czf ~/cache.tgz -C ~/PokerB/data _gto_bench_cache 2>/dev/null
  echo "[ALL DONE $(date -u)] cache=$(ls data/_gto_bench_cache 2>/dev/null | wc -l)" >> ~/solve.log
' >/dev/null 2>&1 &

sleep 6
echo "=== LAUNCHED robust ${HOURS}h solve (PID $!). solve.log tail: ==="
tail -6 ~/solve.log 2>/dev/null || echo "(log not ready yet)"
