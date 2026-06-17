#!/usr/bin/env bash
# Fix: GitHub API was rate-limited on the pod IP -> install TexasSolver from the DIRECT release URL, relaunch.
pkill -9 -f mass_solve 2>/dev/null || true
pkill -9 -f console_solver 2>/dev/null || true
cd ~
rm -rf texassolver && mkdir texassolver
wget -q 'https://github.com/bupticybee/TexasSolver/releases/download/v0.2.0/TexasSolver-v0.2.0-Linux.zip' -O solver.zip
echo "downloaded $(stat -c%s solver.zip) bytes"
unzip -o -q solver.zip -d texassolver
BIN=$(find texassolver -name console_solver | head -1)
echo "bin: $BIN"
chmod +x "$BIN"
file "$BIN" | head -1
cd ~/PokerB && bash ~/runpod_solve_launch.sh
