# NOTES — in-repo notes & deferred-precision log

A running, in-repo log of OPEN QUESTIONS, DEFERRED PRECISION items, and "good-enough-now, compute-exactly-later"
decisions. Distinct from the cross-session auto-memory (`C:\Users\hampe\.claude\projects\...\memory\`). Add an
entry whenever we ship a heuristic/approximation that should later be replaced by an exact/measured value.
Referenced from `CLAUDE.md`.

## Deferred precision (compute exactly later)
- **[2026-06-15] Exact GTO donk + c-bet FREQUENCIES by texture (and SPR / position).** Run 2 caps the OOP donk
  with a single `PokerBot.oop_donk_freq` constant (to pull the over-donk 52% → ~GTO 20%) and the IP c-bet uses
  `postflop.cbet_policy`'s coarse texture frequency. These are APPROXIMATIONS. LATER: compute the EXACT
  per-texture (and per-SPR/position) donk + c-bet frequencies from the TexasSolver caches
  (`extraction/analyze_cache.py` over `data/_gto_bench_cache`) and wire them as a small lookup table, instead of
  the single heuristic constants. Gate/verify with `pokerbot/benchmark/floor_map.py` (the floor error map).

## Open questions
- **[2026-06-15] Run 2 duplicate watch.** The OOP-donk cap (`oop_donk_freq`) improved the solver-gap (the
  primary gate) but the duplicate-vs-GTOBaseline point moved −1.4 → −34 ±105 bb/100 (within noise, no disaster).
  Verify at scale (≥600 decks), AND check whether checking-more-OOP exposes a DOWNSTREAM leak vs the aggressor's
  c-bet (the flop-only solver-gap can't see that) — i.e. is our facing-c-bet defense after checking OOP sound?
  Knob: `PokerBot.oop_donk_freq` (currently 0.5 → ~25% donk; lower to approach GTO 20%).
