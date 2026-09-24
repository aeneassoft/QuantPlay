# CONDITIONAL POKER LEMMAS — effective mathematics with explicit condition knobs (2026-07-06)

> User directive: "Axioms as knobs, effective instead of dogmatic mathematics, conditional proofs for profit."
> The translation that works: **The computational axioms (probability, chip conservation, EV linearity)
> remain sacred — they ARE the profit measuring instrument (AIVAT/Analyzer compute through them).** The legitimate knobs
> sit one level higher: MODEL assumptions, equilibrium concepts, precision budgets, game perturbations.
> Every lemma here is a conditional statement: condition (the knob) → claim → condition TEST → profit link.
> The assumption pattern (adopted from an earlier research project): enforce the assumption, harvest the consequence,
> measure the condition — never loosen the arithmetic.

## L1 — Purification lemma (equilibrium axiom as knob) [= Q4, licensed]
**Condition:** The opponent is STATIC (never adapts to our frequencies).
**Claim:** Then rounding our mixed strategy to the modal action (mix ≥ 0.5 → 1.0) costs no
exploitable EV — mixing only protects against adaptation; against a static opponent it is pure variance.
**Condition test:** GTOW dossier ($0, 13.5k hands): GTOW is the ruse re-solver, does NOT adapt to us
(translation attack refuted, harvest ~0). GTOW's own benchmark paper §4.3.1 licenses it explicitly.
**Profit link:** the ~10.7 bb/100 spread slice of the error ledger; additionally variance reduction in every arm.
**Status:** buildable in hours (`POKERB_PURIFY`), GTOW ladder ONLY (vs humans, mixing stays!), Q2-gated.

## L2 — Perturbed-equilibrium lemma ("Mr. Orange", Johanson 2007 ch. 7) [game axiom as knob]
**Condition:** We deliberately solve the WRONG game: villain's utility scaled by +δ (winner's bonus).
**Claim:** The equilibrium of the perturbed game is, in the REAL game, an aggressive strategy with
BOUNDED exploitability (Johanson measured: +7% bonus → only 35 mbb/g exploitable) — aggression on a
proven leash instead of a felt one.
**Condition test:** exact best response on river subgames is locally computable → δ sweep: exploitability(δ)
+ Analyzer-EV(δ) curves; the knob δ is set empirically to the profit sweet spot.
**Profit link:** the river-aggression leak (−1.6 named, river total −8.5 = largest bleed) — exactly the
class where "GTO-faithful" is too passive against GTOW's real calling mixes.
**Status:** needs the mini-CFR (numpy, lever E from NOTES) — POST-ladder candidate; the only real
"axiom tweak for profit" with a proof anchor. THIS is the best embodiment of the user directive.

## L3 — Thin-value threshold lemma (v3.2b, OpenAI-verified) [model assumption as knob — MEASURABLY FAILED]
**Condition:** The tracked calling range == villain's true calling range at this node.
**Claim:** Then bet s is thin-profitable iff e_call ≥ exact threshold(s, line) (closed form in the
sweep doc §1.1; the 0.5 approximation was the special case).
**Condition test:** v3.2 refutation (26.14 vs 17.93!) = the CONDITION is false (tracker check-lines too
wide → e_call systematically overestimated), not the theorem. The lemma thereby LOCALIZES the work: range
quality (v3.3 family) is the blocker, not the threshold mathematics.
**Profit link:** river-thin stays parked UNTIL the condition test turns green — then the harvest is already
fully derived. Conditional proofs conserve work across refutations.

## L4 — Suit-isomorphism lemma (Johanson §2.5.1) [exactness FOR FREE from symmetry]
**Condition:** Ranges are CLASS-level (169-grid, suit-invariant) — which our emit() guarantees constructively.
**Claim:** Then the canonical solve under suit permutation is EXACT (no approximation error) → 24×
cache collapse without EV cost.
**Condition test:** proven end-to-end (permuted board → 5.0s→0.0s, identical strategy).
**Profit link:** the flop library + every warm-cache hit = fewer timeout→floor fallbacks.
**Status:** BUILT (POKERB_ISO_CACHE); the library enforces canonical keying (../catalogs/FLOP_LIBRARY.md §4).

## Precision knobs (not a lemma, but the same philosophy: exactness is a BUDGET)
MC-EQUITY_ITERS / k_rivers / uint8 quantization (256 levels << solver noise) / RAM dial float32→uint8→1bit
(Johanson up, Jackson down). Rule: every knob carries its error budget EXPLICITLY; the math suite
(tests/test_math_suite.py) pins WHERE exactness is mandatory (core identities) vs. where tolerance is legitimate
(documented conditioning, MC-SE). "Loosen" without a budget = destroying the measuring instrument; "loosen" with a budget =
engineering.

## Anti-lemma (the red line, written down once)
Chip conservation, probability coherence (Σp=1, p∈[0,1]), EV linearity and zero-sum are NOT
negotiable — not out of dogma, but because AIVAT/Analyzer/leaderboard define profit THROUGH them. A
"breakthrough" that violates them is an artifact by construction (CLAUDE.md honesty gate: a too-good
number is a bug, never a win).
