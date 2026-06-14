#!/usr/bin/env bash
# Provision a GCP VM to run TexasSolver coverage-solves: deps + fetch the Linux solver release + smoke test.
set -e
echo "=== installing deps ==="
sudo apt-get update -qq
sudo apt-get install -y -qq python3-pip python3-venv unzip wget jq libgomp1 file >/dev/null 2>&1
pip3 install -q treys numpy >/dev/null 2>&1 || true
echo "deps ok; cores=$(nproc) ram=$(free -g | awk '/Mem/{print $2}')GB"

cd ~
echo "=== locating TexasSolver Linux release asset ==="
ASSETS=$(curl -s https://api.github.com/repos/bupticybee/TexasSolver/releases/latest)
URL=$(echo "$ASSETS" | jq -r '.assets[].browser_download_url' | grep -iE 'linux|ubuntu' | head -1)
if [ -z "$URL" ]; then
  echo "NO obvious linux asset; all assets:"; echo "$ASSETS" | jq -r '.assets[].name'; exit 2
fi
echo "asset: $URL"
wget -q "$URL" -O solver.pkg
echo "downloaded $(stat -c%s solver.pkg) bytes"
mkdir -p texassolver
case "$URL" in
  *.zip)            unzip -o -q solver.pkg -d texassolver ;;
  *.tar.gz|*.tgz)   tar xzf solver.pkg -C texassolver ;;
  *)                echo "unknown archive type"; file solver.pkg ;;
esac
BIN=$(find texassolver -type f -iname 'console_solver*' | head -1)
echo "solver bin: ${BIN:-NONE}"
if [ -n "$BIN" ]; then
  chmod +x "$BIN"
  echo "=== file type ==="; file "$BIN"
  echo "=== smoke run (no-arg; expect usage/exit) ==="; "$BIN" 2>&1 | head -4 || echo "(exited non-zero, expected without input)"
  echo "SOLVER_OK $BIN"
else
  echo "SOLVER_MISSING — tree:"; find texassolver -maxdepth 2 -type f | head -20
fi
