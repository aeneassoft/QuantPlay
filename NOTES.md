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

## Open questions
- **[2026-06-15] Run 2 duplicate watch.** The OOP-donk cap (`oop_donk_freq`) improved the solver-gap (the
  primary gate) but the duplicate-vs-GTOBaseline point moved −1.4 → −34 ±105 bb/100 (within noise, no disaster).
  Verify at scale (≥600 decks), AND check whether checking-more-OOP exposes a DOWNSTREAM leak vs the aggressor's
  c-bet (the flop-only solver-gap can't see that) — i.e. is our facing-c-bet defense after checking OOP sound?
  Knob: `PokerBot.oop_donk_freq` (currently 0.5 → ~25% donk; lower to approach GTO 20%).
