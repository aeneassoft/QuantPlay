#!/usr/bin/env bash
# Provision a RunPod CPU pod (root container, no sudo) for TexasSolver coverage-solves: deps + Linux solver.
set -e
echo "=== deps ==="
apt-get update -qq >/dev/null 2>&1 || true
apt-get install -y -qq unzip wget jq libgomp1 file curl >/dev/null 2>&1 || true
pip3 install -q treys numpy >/dev/null 2>&1 || true
echo "deps ok; cores=$(nproc) ram=$(free -g | awk '/Mem/{print $2}')GB"

cd ~
echo "=== fetch TexasSolver Linux release ==="
ASSETS=$(curl -s https://api.github.com/repos/bupticybee/TexasSolver/releases/latest)
URL=$(echo "$ASSETS" | jq -r '.assets[].browser_download_url' | grep -iE 'linux|ubuntu' | head -1)
if [ -z "$URL" ]; then echo "NO linux asset:"; echo "$ASSETS" | jq -r '.assets[].name'; exit 2; fi
echo "asset: $URL"
wget -q "$URL" -O solver.pkg
echo "downloaded $(stat -c%s solver.pkg) bytes"
mkdir -p texassolver
case "$URL" in
  *.zip)          unzip -o -q solver.pkg -d texassolver ;;
  *.tar.gz|*.tgz) tar xzf solver.pkg -C texassolver ;;
  *)              echo "unknown archive"; file solver.pkg ;;
esac
BIN=$(find texassolver -type f -iname 'console_solver*' | head -1)
if [ -n "$BIN" ]; then
  chmod +x "$BIN"
  echo "=== smoke (no-arg; expect usage) ==="; "$BIN" 2>&1 | head -3 || echo "(non-zero, expected)"
  echo "SOLVER_OK $BIN"
else
  echo "SOLVER_MISSING"; find texassolver -maxdepth 2 -type f | head -20
fi
