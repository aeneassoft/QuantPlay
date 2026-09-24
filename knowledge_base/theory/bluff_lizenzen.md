# BLUFF LICENSES — the structural preconditions of bluffing, mathematically
(Program document, 2026-08-16; occasion: Brown 2026 + the AUSLESE v1 gate — selection, not quota)

**Thesis:** A bluff is never "a weak hand with frequency f", but a hand with a
**license** — a computable structural property that makes the bluff profitable.
Brown measures: ZERO hands are pure bluffs in all four model variants; the 27 real
bluff hands split according to WHICH dropped simplification licenses them.
Our task: find the licenses, categorize them, express them as formulas, then measure.

All quantities below are computable from LEGAL information: own cards h, board B,
bet size b, pot P, and the opponent's Bayes-tracker range W = {combo c -> weight w(c)}
(from the line played). Continue range C(W,b) = the combos with which W continues
against size b (defense advisor / MDF core of the strongest combos).

## L1 — BLOCKER LICENSE (card removal on the continue side)
    Block(h) = 1 − [ Σ_{c∈C, c∩h≠∅} w(c) ] / [ Σ_{c∈C} w(c) ]  … relative weight loss
    more precisely as a score:  Block(h) = Σ_{c∈C} w(c)·1[c∩h≠∅] / Σ_{c∈C} w(c)
Hero holds cards that physically reduce the opponent's CONTINUE combos (nut flush
blockers etc.). License if Block(h) ≥ β. Source: Brown (card removal = the 169x169
non-scalarity); count_hand_combos_with_blockers sits unwired in formulas.py.

## L2 — UNBLOCKER LICENSE (don't touch the fold side)
    Unblock(h) = 1 − Σ_{c∈F} w(c)·1[c∩h≠∅] / Σ_{c∈F} w(c),   F = W \ C (the fold range)
Hero holds NO cards of the opponent's FOLD range — every blocked fold combo lowers the realized
fold frequency below the MDF calculation. Full license strength = the Block(h)·Unblock(h) pair.

## L3 — EQUITY BACKUP (semi-bluff license)
    E_called(h) = Equity(h | C(W,b), B)     … equity AGAINST THE CALLING range
    License if  FE_required(P, b, E_called) = (b − E_called·(P+2b)) / (P + b − E_called·(P+2b))
    lies below the realistic fold estimate (required_fold_equity, wired, E1-checked).
Outs make the bluff profitable in two stages. Source: semi_bluff_ev (formula collection), Brown
(the non-determinism variant licenses its own bluff hands).

## L4 — CAP LICENSE (range asymmetry)
    Cap(W,B) = Σ_{c∈W} w(c)·1[strength(c,B) ≥ nut threshold] / Σ w(c)   … the opponent's nut share
    License if Cap(W,B) ≤ κ  (the opponent CAN hardly be strong — his line has capped him).
Source: nut_fraction/capped_range_penalty (collection, so far NICHT_VERDRAHTBAR for lack of a range —
the tracker range now makes them computable!). This is the sel_guard trick on the bet side.

## L5 — GEOMETRY LICENSE (sizing/SPR)
    b*(P, s) from geometric_bet_fraction_to_all_in; license for overbet polarization only if
    one's own range at the node owns the nut side (L4 mirrored onto hero) and the SPR carries the
    pressure (stackoff_equity_threshold_from_spr). Source: Brown (bet-size axis).

## The measurement program (pre-registered)
1. **Catalog:** score all bluff instances from decisions.jsonl.gz + the GTOW raise mining
   (488 raises: flop 53% air) + Brown's 27 hands per license -> which licenses occur
   in reality, individually or in bundles?
2. **Oracle checks:** L check `bluff_ohne_lizenz` (hero bet with low equity AND
   Block·Unblock·Cap all below threshold = structural spew) + F check license rates.
3. **Candidate (round 3, against AUSLESE v1):** the bet-side selection guard — bluffs only
   with a license score above threshold, value untouched. Expectation pre-registered BEFORE the build.
4. **Honesty:** thresholds (β, κ, …) are knobs with bounds; the license DEFINITIONS
   are formulas and immutable. Catalog (descriptive) first, then check (normative) —
   never the other way round, otherwise we build dogma instead of measurement.
