# NOTES — in-repo notes & deferred-precision log

A running, in-repo log of OPEN QUESTIONS, DEFERRED PRECISION items, and "good-enough-now, compute-exactly-later"
decisions. Distinct from the cross-session auto-memory (`C:\Users\hampe\.claude\projects\...\memory\`). Add an
entry whenever we ship a heuristic/approximation that should later be replaced by an exact/measured value.
Referenced from `CLAUDE.md`.

## Deferred precision (compute exactly later)
- **[2026-06-15 ✅ table + OOP wired] GTO donk + c-bet frequencies by texture.** EXTRACTED to
  `knowledge_base/postflop/texture_freqs.json` (`extraction/texture_freqs.py`, 1340 boards). OOP donk now wired
  PER-TEXTURE in `bot.py` (`_texture_freq`): monotone 12%≈GTO 14%, ALL 22%≈21% on the floor map. REMAINING:
  (a) the IP c-bet is still ~87% vs GTO 74% (value-always-bets); (b) the per-texture donk/c-bet HAND-SELECTION
  (which hands, not just the frequency) + SPR/position split. Both handled holistically by the supervised
  advisor (#36–41), which learns frequency AND selection from the same caches.
- **[2026-06-15 ⏳ solving] Turn advisor (#41) full coverage.** `turn_advisor.pt` is PRELIMINARY (turn nodes of
  only 46 flop files; +23% vs freq baseline, held out over 2189 turn boards). A robust 8h RunPod turn-coverage
  solve (DUMP=2, pod szx1z9in3g1rve, ~350 boards/h) is running. WHEN DONE: rerun `extraction.build_turn_data`
  then `extraction.train_turn_advisor` on the pod, pull `turn_advisor.pt`, then `runpod_run --kill`. See the
  auto-memory `active-runpod-turn-solve`.
- **[2026-06-15 ⚠ theory-only] River blocker nudges (#40).** `bot.py:_river_blocker_signal` biases river bluff
  SELECTION (frequency-preserving) + nudges the bluffcatch threshold ±6% by how much hero blocks villain's VALUE
  vs AIR combos. The DIRECTION is GTO-canonical (blocker theory) but the magnitudes (0.06 thresh, 0.6 freq factor,
  the 3500 "value" rank bar) are NOT solver-calibrated — there is no river (DUMP=3) cache yet. Calibrate against a
  targeted DUMP=3 river batch later; safe-by-construction until then (selection bias + tiny nudge can't spew).

## Open questions
- **[2026-06-15] Run 2 duplicate watch.** The OOP-donk cap (`oop_donk_freq`) improved the solver-gap (the
  primary gate) but the duplicate-vs-GTOBaseline point moved −1.4 → −34 ±105 bb/100 (within noise, no disaster).
  Verify at scale (≥600 decks), AND check whether checking-more-OOP exposes a DOWNSTREAM leak vs the aggressor's
  c-bet (the flop-only solver-gap can't see that) — i.e. is our facing-c-bet defense after checking OOP sound?
  Knob: `PokerBot.oop_donk_freq` (currently 0.5 → ~25% donk; lower to approach GTO 20%).
