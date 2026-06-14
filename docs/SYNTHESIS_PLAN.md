# SYNTHESIS PLAN — best bot we can build NOW (Phase 1 output, 2026-06-14)

Synthesized from TWO independent frontier-model consults (`synthesis_claude.md` = Opus 4.8,
`synthesis_openai.md` = gpt-5.1), cross-checked against our own measured lessons. They **converged hard** —
high confidence in the direction below.

## The one-line reframe (both models, unprompted)
**We don't have an exploit problem — we have a FLOOR problem.** The −46 bb/100 vs Slumbot with exploit OFF
*is* our own exploitability. A bleeding floor means a good opponent's small deviation is dwarfed by our own
error → the exploit layer can't help vs strong players until the floor is fixed. **So: build the floor first,
from our exact data; bolt the (already-built) exploit engine on top, gated.** Exploitation stays the edge vs
the *field*; the floor is the insurance vs near-GTO.

## Precision hierarchy (who wins data conflicts — both models agree)
```
Solver caches (B, exact at node)  >  PokerBench labels (A, exact GTO)  >  Books (D, principles)
   >  our LoRA LLM outputs (F, 62–72%, biased)  >  playbook/Pluribus priors (E/C, hypotheses)
```
Rule: if a solver node and a book/heuristic disagree, **solver wins, always** — and log it; a cluster of
disagreements is a map of the floor's leaks → solve those textures next.

## The honest LLM verdict (the question we asked) — BOTH models + our own analysis converge
**Do NOT deploy the LoRA in play** (too slow; 62–72% is *less* accurate than the distilled tables on the
spots the tables cover; the 32B's passive skew is a measurable leak). The LLM's knowledge is a **lossy copy
of data we already have exactly** → for the floor, exact data beats it. Its only legitimate, second-hand uses:
1. **Curriculum director** — propose under-covered / high-frequency spot families → point the *solver* there
   (its failure mode is benign: a bad suggestion just wastes a little solve time; the solve is ground truth).
2. **Annotation / diagnostic** — auto-tag boards into buckets; explain *in English* where the floor deviates
   from GTO, so we refine buckets (never trust its actions).
3. (low priority) async exploit-hypothesis ideation — redundant with our engine + Book 5.
Claude is blunter: **mothball the 32B** for deployment; the LLM is "a worse copy of data you already have."
→ This is the deflating-but-honest answer: the LoRA is the *least* valuable asset for the floor. We use its
   *insights*, not the model.

## THE RANKED BUILD (merged, every step gated by a GROUNDED signal)

**Step 0 — Fix measurement FIRST (½–1 day).** Stand up AIVAT/duplicate-poker + an LBR probe; re-measure the
current floor vs Slumbot. *Claude's flag:* the −5.4 "with exploit" may be **variance, not skill** — verify
before building on it. Gate: a CI that excludes zero.

**Step 1 — Unified feature/node taxonomy (1–2 days).** Standardize `(node_type, board_bucket, SPR_bucket,
hand_class)` mappings from a live state (gpt-5.1's detailed schema). Foundation for all tables. Gate:
deterministic mapping + ~100 spots eyeballed as poker-sane.

**Step 2 — Preflop EXACT lookup table from PokerBench (1–2 days).** 563k exact labels → tiny bucketed state
space → near-GTO preflop. Keep the verified HU push/fold blueprint untouched. Gate: held-out preflop
action-match **>95%** + preflop-only LBR low.

**Step 3 — Postflop param-tables, calibrated to solver caches (3–5 days) — THE biggest EV.** Aggregate B
(primary) + A (coverage) into per-bucket action/size frequencies; **recalibrate the analytic knobs (c-bet
freq/size, MDF, fold-equity targets) to MINIMIZE TV-gap vs the solver caches** (a grid-search/regression, not
training — Claude's "single highest-leverage cheap win"). A/B the dormant `openai_strategy.json` here — keep
only if it lowers TV-gap. Gate: held-out TV/EV-gap vs freshly-solved nodes drops; per-street gap reveals where
the −46 lives.

**Step 4 — Wire tables as the floor + measure (3–4 days).** Replace postflop heuristics with table lookups
(equity logic = fallback/tie-break only). Gate: LBR exploitability ↓ AND floor-only bb/100 vs Slumbot moves
from −46 toward break-even, with variance-reduced CI.

**Step 5 — Extract "Beyond GTO" → exploit primitives + re-seed the overlay (2–4 days).** Mine
trigger→adjustment rules into the playbook schema `(stat-condition, spot, freq_delta∈[−0.3,0.3], confidence)`;
merge with E + Pluribus/Slumbot priors (C); confidence-gate + Bayesian shrinkage (prior → overridden by
observation). Gate: exploit-ON vs OFF in duplicate/AIVAT — **up vs the weak field, NOT-down vs near-GTO**.
Kill any primitive that's net-negative in held-out matches.

**Step 6 — LLM offline-only (1–2 days, low priority).** 8B as curriculum director → point GCP solving at the
worst-TV-gap / uncovered spots (Claude: **we're under-using GCP solve capacity** — brute-force ground truth
where it hurts most is cheaper + more reliable than any interpolation/LLM). Verify any generated reference by
solving a 10% sample; keep only solver outputs.

## Open risks / hypotheses to watch (their honesty flags)
- Hypothesis (test, don't assume): the analytic **c-bet/sizing heuristic is the dominant source of the −46** —
  confirm via per-street TV-gap; if turn/river dominate, reprioritize toward the turn caches.
- **k-NN flop retrieval** (Claude's variant of Step 3) is the riskiest engineering claim — gate hard on
  held-out TV-gap; range-dependence can make a "near" flop strategically different. (gpt-5.1's tabulation
  variant is the safer default.)
- PokerBench may be **sparse in rare 6-max turn/river nodes** → coarsen buckets or solve those nodes.
- Pluribus priors may mis-bias exploits if our pool differs → monitor, override with live observation.

## Bottom line
Both models, independently, told us to do the un-glamorous thing: **turn our exact solver+PokerBench data into
a measurably-lower-exploitability floor, gate everything, and use the LLM only to point the solver.** That is
the best bot we can build now — and it's squarely inside our verify-everything discipline.
