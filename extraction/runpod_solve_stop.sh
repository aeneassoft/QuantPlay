#!/usr/bin/env bash
# Cleanly stop a running solve (loop + mass_solve driver + console_solver workers). MUST run from a FILE so the
# runner's own command line ("bash runpod_solve_stop.sh") does NOT contain the kill patterns -> no self-kill
# (the bug: `ssh ... "pkill -f 'EXIT rc'"` matched its own remote shell). pkill already excludes its own PID.
[ -f ~/solve.pid ] && kill -9 "$(cat ~/solve.pid)" 2>/dev/null   # the restart loop (new script writes a PID file)
pkill -9 -f 'EXIT rc' 2>/dev/null                                # old-style loop bash (pre-PID-file)
pkill -9 -f extraction.mass_solve 2>/dev/null                    # the python driver (has its own 55-min timer)
pkill -9 -f console_solver 2>/dev/null                           # the TexasSolver workers
sleep 3
echo "stopped. remaining: loops=$(pgrep -fc 'EXIT rc') drivers=$(pgrep -fc extraction.mass_solve) solvers=$(pgrep -fc console_solver)"
echo "cache=$(ls ~/PokerB/data/_gto_bench_cache 2>/dev/null | wc -l)"
