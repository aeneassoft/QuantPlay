#!/bin/bash
# v8-Messkette (2026-08-31, vorregistriert im Journal V8-VORREGISTRIERUNG-MESSPLAN):
# play-A/A -> play-Mirror 30k -> CHECKPOINT (VERWERFEN => Stopp) ->
# v8-A/A -> v8 vs v5 30k -> 2x15k Replikation -> Treppe vs v4/basis je 15k.
# 12 Worker (VRAM 3,7/12,3GB gemessen); Baenke disjunkt ab 720000.
set -u
cd "C:/Users/hampe/Desktop/PokerB"
LOG=data/runs/v8_kette_$(date +%Y%m%d_%H%M%S).log

lauf() {
  echo "=== LAUF: $* ===" | tee -a "$LOG"
  python -m pokerbot.autogym.pargate "$@" 2>&1 | tee -a "$LOG" | tail -2
}

lauf --kandidat r9_play --incumbent r9_play --decks 600 --workers 12 --seed 1 --deck-seed0 720000
if ! grep -q "'kandidat': 'r9_play', 'incumbent': 'r9_play'.*'bb100': 0.0, 'se': 0.0" "$LOG"; then
  echo "ABBRUCH: play-A/A nicht exakt 0" | tee -a "$LOG"; exit 1
fi
lauf --kandidat r9_play --incumbent r8_stack --decks 30000 --workers 12 --seed 1 --deck-seed0 750000
if grep -q "'incumbent': 'r8_stack'.*'verdict': 'VERWERFEN'" "$LOG"; then
  echo "CHECKPOINT: play-Mirror VERWERFEN - Kette gestoppt, v8 neu denken" | tee -a "$LOG"; exit 2
fi
lauf --kandidat r9_v8 --incumbent r9_v8 --decks 600 --workers 12 --seed 1 --deck-seed0 780000
lauf --kandidat r9_v8 --incumbent r8_stack --decks 30000 --workers 12 --seed 1 --deck-seed0 810000
lauf --kandidat r9_v8 --incumbent r8_stack --decks 15000 --workers 12 --seed 1 --deck-seed0 840000
lauf --kandidat r9_v8 --incumbent r8_stack --decks 15000 --workers 12 --seed 1 --deck-seed0 870000
lauf --kandidat r9_v8 --incumbent r6_button --decks 15000 --workers 12 --seed 1 --deck-seed0 900000
lauf --kandidat r9_v8 --incumbent basis --decks 15000 --workers 12 --seed 1 --deck-seed0 930000
echo "KETTE KOMPLETT" | tee -a "$LOG"
