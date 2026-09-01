#!/bin/bash
# v9-Messkette (2026-09-01, Journal V9-VORREGISTRIERUNG):
# A/A (fp16-Determinismus MUSS exakt 0) -> vs r8_stack 30k (Champion v5)
# -> vs basis 15k (eingefroren) -> vs r6_button 15k (v4). 12 Worker.
# Stoppen heisst: bash + pargate-Main + alle Spawns killen (Prozessfamilien-Lehre).
set -u
cd "C:/Users/hampe/Desktop/PokerB"
LOG=data/runs/v9_kette_$(date +%Y%m%d_%H%M%S).log

lauf() {
  echo "=== LAUF: $* ===" | tee -a "$LOG"
  python -m pokerbot.autogym.pargate "$@" 2>&1 | tee -a "$LOG" | tail -2
}

lauf --kandidat r10_ernte --incumbent r10_ernte --decks 600 --workers 12 --seed 1 --deck-seed0 960000
if ! grep -q "'kandidat': 'r10_ernte', 'incumbent': 'r10_ernte'.*'bb100': 0.0, 'se': 0.0" "$LOG"; then
  echo "ABBRUCH: A/A nicht exakt 0 (fp16-Determinismus!)" | tee -a "$LOG"; exit 1
fi
lauf --kandidat r10_ernte --incumbent r8_stack --decks 30000 --workers 12 --seed 1 --deck-seed0 990000
if grep -q "'incumbent': 'r8_stack'.*'verdict': 'VERWERFEN'" "$LOG"; then
  echo "CHECKPOINT: vs Champion VERWERFEN - Treppe gestoppt" | tee -a "$LOG"; exit 2
fi
lauf --kandidat r10_ernte --incumbent basis --decks 15000 --workers 12 --seed 1 --deck-seed0 1020000
lauf --kandidat r10_ernte --incumbent r6_button --decks 15000 --workers 12 --seed 1 --deck-seed0 1050000
echo "KETTE KOMPLETT" | tee -a "$LOG"
