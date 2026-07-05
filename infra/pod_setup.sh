#!/usr/bin/env bash
# Pod-side setup for the CFV data-gen campaign: install TexasSolver-Linux + the python deps.
# Quote-safe as a file (no nested-quoting hell from an inline ssh command). Arg $1 = the TexasSolver Linux zip URL.
# Echoes SETUP_OK only if EVERYTHING succeeded (the orchestrator gates on that). Robust to unzip being absent
# (uses python zipfile) and finds console_solver wherever the zip puts it.
set -e
cd /root
rm -rf tsolver TexasSolver* ts.zip
curl -sL "$1" -o ts.zip
python3 -c "import zipfile; zipfile.ZipFile('/root/ts.zip').extractall('/root')"
CS=$(find /root -iname console_solver -type f 2>/dev/null | head -1)
if [ -z "$CS" ]; then echo "NO_SOLVER_BINARY_FOUND"; ls -R /root | head -40; exit 1; fi
chmod +x "$CS"
ln -sfn "$(dirname "$CS")" /root/tsolver
pip install -q --break-system-packages treys numpy 2>/dev/null || pip install -q treys numpy
python3 -c "import treys, numpy"          # hard-fail if the deps did not actually install
echo "SETUP_OK CS=$CS"
