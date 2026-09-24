# Fundamental GTO step: P0 range tracker built, tested, wired — and a false consensus caught

*2026-06-15. Session deliverable. I (Claude) worked on the bot myself in a grounded way, not merely consulted.
This documents what was built/verified, the decisive verify-everything find, and — importantly — what is
**not yet measured** (the Skinner discipline demands this separation).*

---

## 0. What was requested

"Bring the poker bot significantly closer toward GTO, fundamentally too. Spin up all APIs + our program.
Go deeper into the newest files." → I went into the *newest* files first (the GTO consults
gpt-5.5/o3 + the `MVP2_RESOLVER_PLAN`), then fired the APIs **in a grounded way** (at the one open sub-problem, not
at "how GTO?" — that was already answered), and then **implemented + tested myself**.

---

## 1. The convergent diagnosis (three independent sources, the same finding)

The −160 bb/100 vs TexasSolver are **abstraction error**, not a frequency problem. Three sources, independent:

- **My own GTO review** ([GTO_GAP_REVIEW_2026-06-15.md](GTO_GAP_REVIEW_2026-06-15.md)) → keystone =
  Bayes range tracker, then resolver.
- **o3** (`situational_reason_o3.md`): CFR decomposition — matching bucket-marginal frequencies leaves
  `Σ π·δ·v` unbounded precisely at sizing/SPR/range asymmetry.
- **gpt-5.5** (`situational_poker_gpt55.md`): hybrid = blueprint + targeted resolving, **river-first**,
  driven by a range tracker.

The `MVP2_RESOLVER_PLAN` turns that into the plan; **P0 (the range tracker) is the linchpin** and until today
was only a preflop stub. The plan warns explicitly: *"a bad range reconstruction makes the resolver WORSE than the
floor."* → Building P0 correctly is the fundamental prerequisite for *any* postflop GTO progress.

> Three-source convergence is a Pidgeon signal. But here it rests on o3's CFR proof + measured numbers,
> not on enthusiasm. The honest consequence: do **not** fire the APIs at "how GTO?" again (waste)
> — but at the *open* sub-problem the plan skips.

---

## 2. The grounded consult (the open P0 sub-problem)

`extraction/range_tracker_consult.py` → 4 APIs in parallel on the precise gap: **how do you build the Bayes range
update when the blueprint only delivers P(bet)** (nothing for facing-bet call/fold/raise or bet size)?
Answers in `docs/range_tracker_consult_{o3,claude,perplexity,venice}.md`. Convergent synthesis:

- **o3 (safety theorem):** reweight only where a model exists (bet/check via advisor); for the
  *silent* actions **legality-only** (multiply by 1, never by 0 except when logically impossible). Then
  `‖tracked − true‖₁` can only decrease → injected exploitability ≤ (CapPot/2)·L1, **bounded**. A badly
  narrowed range (zeroing a live combo) is **unboundedly** worse. "Do nothing unless certain."
- **Fidelity budget:** villain range ≫ own range (o3 bound: own error often = 0 for the actually
  held hand on the river).
- **Confidence gate:** on an uncertain reconstruction fall back to the floor (Claude).
- **Venice (red team):** the cheap upfront test — does P(bet) correlate with optimal play at all? (Yes: the advisor
  is solver-trained, the floor matches solver frequencies.)

---

## 3. What I built

### `pokerbot/strategy/range_tracker.py` — the v2 RangeTracker (the keystone)
Per-combo Bayes tracker, o3's provably-safe v0:
- **bet/check** → reweight per advisor `P(bet)` (the only real model).
- **call/raise/bet size (silent)** → legality-only (weight unchanged), counts against confidence.
- **fold** → ends the hand (does not occur in a live line).
- exact per-combo dead-card removal per street; normalization; weight floor 1e-6.
- **Confidence** = `1 − 0.5·heuristic_ratio`, capped only on *real* collapse (effective combos < 10, via
  inverse Herfindahl — **not** via an absolute weight threshold; a wide range has tiny per-combo
  weights ~1/N and would otherwise be falsely flagged as collapsed — I caught + fixed this bug).

### Wiring: `pokerbot/strategy/bot.py`
`_river_resolve` + `_turn_resolve` now use `weighted_ranges(state)` (line-aware tracked ranges)
instead of the preflop stub, with a **confidence gate**: `conf < 0.5 → return None → floor` (safe by construction).
Everything behind the existing `use_resolver` (OFF by default) → no influence on live play / existing tests.

---

## 4. ⚠ The decisive verify-everything find (the Pidgeon discipline in action)

**All four APIs claimed in agreement: "per-combo weighted ranges (`AsKh:0.62`) are standard and
work with TexasSolver."** o3 even said "~20 ms overhead, zero approximation error."

**That is FALSE for our TexasSolver v0.2.0 build.** My end-to-end test against the real binary showed:
- class-level ranges → 58 strategy keys, `strategy_for` works ✓
- per-combo ranges → the solver produces **no output at all** (crashes) or an **empty** per-combo
  strategy dump (`num strategy keys: 0`) → the resolver cannot read our action ✗

Four models, confidently convergent, **wrong**. Had I not tested it against the real build, I would
have shipped a tracker that silently feeds the solver empty strategies. **That is exactly the lesson
../NOTES.md documents again and again** ("verify everything", "the unpaired +184 was noise").

**Fix:** the tracker stays per-combo internally (advisor P(bet) + exact dead-card removal), **but aggregates on
emit to class-level weighted strings** (`AQs:0.62,KQo:0.31,...`). TexasSolver expands internally + keys the
dump per combo → `strategy_for(node, hero_c1, hero_c2)` works again. Cost: within-class weight
variation is lost (a real solver constraint, not a choice); the solver still does card removal.

### Side finding + fix: `gto_oracle.py` null crash
Deep nodes / failed solves have `"strategy": null`. `_key`/`strategy_for` crashed on that
(`AttributeError`) instead of cleanly returning `None`. Made null-safe (`(x or {})`) → the resolver floors
gracefully instead of crashing live when it is switched on. (Found via the end-to-end smoke.)

---

## 5. Verification (what actually runs)

**Unit tests** `tests/test_range_tracker.py` (4/4 green) — the P0 gate checks from the consult:
- mass conservation (sum→1) + dead-card exclusion
- monotone shrinkage down the line (support never grows)
- confidence ≥ gate on a normal SRP river line (0.83) + class weights are non-uniform (the advisor
  really reweights, spread 0.42..1.0)
- safety: a call-heavy line **never** zeroes a live combo (o3's theorem)

**End-to-end smoke** `extraction/smoke_weighted_resolve.py` (green, against the real TexasSolver):
- [1] class-level tracked ranges solve → **709 per-combo strategy keys** (non-empty dump)
- [2] resolver fires on the OOP-first node → `('bet', 330)`
- [3] resolver fires on the IP-after-check node → `('check', None)`

→ **The complete P0→P1 pipeline runs mechanically end-to-end:** tracked ranges → TexasSolver → readable
per-combo strategy → sampled GTO action for our hand, on both river node types.

**Regression:** `test_game` (300 hands, all invariants), `test_bot`, `test_range_tracker` — all green. The
resolver is off by default → live play unchanged.

---

## 6. HONEST STATUS — what is NOT shown (Skinner discipline)

I built and verified the **mechanism**: the keystone (P0) is built, tested, wired; the
pipeline runs end-to-end; it is safe by construction (gate → floor). **I have NOT measured that the bot
thereby plays closer to GTO.** Concretely not shown:

- **No EV recovery measured.** Whether the resolver with tracked ranges reduces the −160 bb/100 vs TexasSolver
  is **open**. That demands the P1 gate: **paired/duplicate ≥1000 hands vs TexasSolver** (hours
  of live solve compute) **+ a fresh GTO Wizard AIVAT run**. Neither ran in this session.
- **Range tracker fidelity unmeasured.** The tests show consistency (sum, shrink, safety), **not** that the
  reconstructed ranges are close to the *true* ranges. The consult's validation path (solver cross-check on
  canonical spots) is not built yet.
- **Class-level loses within-class fidelity.** A forced compromise (solver constraint) — effect on
  resolve quality unmeasured.
- **Only the river is smoke-tested end-to-end.** The turn resolver is wired but not validated end-to-end.

> Plain language: I **built the blocking keystone and proved that it feeds the solver correctly** —
> that is real fundamental progress on the GTO path. I have **not** proved that the bot now
> loses less. "The resolver fires" ≠ "the bot is closer to GTO". This separation is the whole point.

---

## 7. Concrete next steps (in order)

1. **P1 gate (the measurement that decides everything):** `use_resolver=True`, paired/duplicate ≥1000 hands
   floor vs floor+river resolver vs TexasSolver. Does it recover >2σ (target +30 bb/100, gpt-5.5's corridor)?
   → keep. If <15 → range tracker/abstraction/integration wrong, or diagnosis incomplete.
2. **Range tracker validation:** solver cross-check on 10-20 canonical spots (consult §4) — catches a
   bad reconstruction *before* it silently degrades the resolver.
3. **Facing-bet nodes:** the biggest measured bleed (~55 bb/100, gpt-5.5). Currently the river smoke covers
   first-to-act + after-check; facing-a-bet (call/fold/raise) needs its own resolve-rooting validation.
4. **Turn resolver** end-to-end (analogous to the river smoke), then its own P1 gate.
5. **GTO Wizard key** (401-blocked) → AIVAT is the definitive external number.

---

## 8. Changed / new files

**New:** `pokerbot/strategy/range_tracker.py` (v2 tracker — complete), `tests/test_range_tracker.py`,
`extraction/range_tracker_consult.py`, `extraction/smoke_weighted_resolve.py`,
`docs/range_tracker_consult_{o3,claude,perplexity,venice}.md`, this file.
**Changed:** `pokerbot/strategy/bot.py` (`_river_resolve`/`_turn_resolve` → tracked ranges + confidence gate),
`pokerbot/strategy/gto_oracle.py` (null safety in `_key`/`strategy_for`).

---

## 9. Conclusion

The **fundamental block** (P0 range tracker) is built, tested, wired — and the per-combo→class-level
solver constraint that a fourfold API consensus had falsely denied is caught. The GTO pipeline now runs
mechanically end-to-end. **The next step is no longer code — it is the measurement** (P1 gate), and until
that runs, "closer to GTO" is a justified expectation, not a result.

*— Built + verified against the real TexasSolver v0.2.0 build. Consults: o3 + gpt-5.5/5.1 + Claude +
Perplexity + Venice. Tests + smoke green; EV gate open.*
