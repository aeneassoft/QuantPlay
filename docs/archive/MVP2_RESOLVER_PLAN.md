# MVP#2 — the big step toward GTO: hybrid blueprint + targeted real-time re-solving

> Grounded in MEASURED gaps (2026-06-15): MVP vs **GTO Wizard AI −32.6 ±11 bb/100 (AIVAT, n=30 prelim)**;
> vs **TexasSolver −160 ±75 bb/100 (paired)**; vs **Slumbot ~−102**. Frontier consult (gpt-5.5 + o3, vetted) =
> `docs/situational_poker_gpt55.md` + `situational_reason_o3.md`.

## Context — why MVP#1 plateaus, and the proven direction
MVP#1 (the floor) MATCHES the solver's bet/check **frequencies** (GTO-gap flop 31% / river 29%, freqs aligned)
yet LOSES big in bb/100. Both frontier models + the theory agree on WHY: the floor is **context-collapsed**. It maps
`(board+hand features, role) → one P(bet)`, averaging over distinct info-sets that differ by **line, SPR, ranges,
and bet-size faced**. o3's CFR decomposition makes it exact:

  `u(σ̂,σ*) − u(σ*,σ*) = Σ_I π₋ᵢ(I) Σ_a (σ̂−σ*)(I,a)·v(I,a)`

Matching bucket-**marginal** frequencies leaves this sum unconstrained whenever `v` (counterfactual value) is
heterogeneous inside a bucket — exactly at sizing / SPR / range-asymmetry. So **the fix is not better frequencies;
it is a strategy specific to the public state that actually occurs.** That is the user's intuition, confirmed.

**Vetted architecture (both models agree): a HYBRID** — a supervised blueprint (fast fallback + range prior) +
**targeted real-time sub-game re-solving** (TexasSolver, which we already run locally) at the high-leverage nodes,
driven by a **range tracker**. River-first (solves to TERMINAL → no value net). The Pluribus/DeepStack pattern.
Theory guarantee (Brown & Sandholm CFR-D AAAI-17/18; DeepStack, Moravčík et al. Science-17, citations verified):
re-solved exploitability ≤ 2·(leaf-value error); river/turn-to-terminal ⇒ leaf error ≈ 0.

**Vet corrections to o3 (it was over-optimistic, as in prior consults):**
- **Speed:** o3's "20–30 ms/solve, build 0.40" is wrong — we run TexasSolver **v0.2.0**; our REAL solves are
  **~seconds** (head-to-head evidence). So real-time resolving is fine for ANALYSIS/benchmark + a strong-but-slow
  bot; snappy LIVE play needs later caching / action-abstraction / a value net. Plan for seconds, not ms.
- **Leaf values:** o3's "leaf = cache CFVs" does NOT work — our cache stores **frequencies only, no CFVs**, and
  with the wrong (fixed-SRP) ranges. gpt-5.5 is right: **solve river/turn to TERMINAL** (no value net) first.
- **EV claims:** o3's "+120–150, wipes out −160" is hype. Use gpt-5.5's honest ranges (below). We will NOT beat
  GTO Wizard — the target is LEAST-LOSS (leaderboard-best ≈ −3 bb/100): move −33 toward single-digit-negative.

The −160 decomposition (engineering prior, NOT measured — Phase 1 measures it): facing-bet defense ~55 /
turn-river line-context ~45 / sizing ~35 / OOP check-raise+probe ~25 bb/100. Biggest bleed = **facing-bet defense**.

## Architecture (target)
```
Preflop:    CFR push/fold + GTO lookup (keep)
Blueprint:  the supervised advisor (keep as fallback + range prior; later: richer, public-state-conditioned)
RangeTracker: both players' 1326-combo public ranges, Bayesian-updated through the actual line via the blueprint policy
Resolver:   at high-leverage nodes, build the sub-game from the tracked ranges + a compact action abstraction,
            solve with TexasSolver (river/turn = terminal; flop later w/ a CFV net), use the solver strategy for OUR
            hand, SAMPLE (not argmax), fall back to the floor on timeout
Exploit:    OFF vs near-GTO (defers); ON vs the exploitable field (the existing engine)
```
Reuses the head-to-head's live-solve machinery (`gto_oracle_match.py` / `gto_oracle.solve`) — the difference is
TRACKED ranges (the real public state) instead of fixed SRP ranges, wired into OUR bot at the high-leverage nodes.

## Phases — river-first, every step PROOF-GATED (measure, don't assume)
**Gate for every phase:** paired/duplicate vs TexasSolver (1000+ hands; the variance gate we trust) AND a fresh
**GTO Wizard AIVAT** run (the north-star number, AIVAT-sharp). Keep a phase only if it RECOVERS EV at >2σ.

- **P0 — Range tracker** (`strategy/range_tracker.py`). Maintain both players' 1326-combo ranges through the line:
  `range_next(h) ∝ range_prev(h)·policy(action|state,h)`, policy from the advisor/blueprint (villain) + our own
  prior-node policy (us). The prerequisite for solving the public STATE (not just our hand). Verify: ranges sum→1,
  shrink sanely down a betting line, exclude board/known cards.
- **P1 — RIVER resolver** (`strategy/resolver.py` + wire `bot.py` river path, behind `use_resolver`). At a river
  decision: build the river sub-game (board, pot, SPR, tracked ranges) + compact action abstraction (facing a bet →
  fold/call/raise-or-jam; first-to-act → check / bet 33 / bet 75 / overbet-or-jam); `gto_oracle.solve` to terminal;
  look up OUR hand's strategy; sample; floor-fallback on timeout. Highest signal (facing-bet defense + sizing),
  solves to terminal → no value net. **Gate: paired floor vs floor+river-resolver vs TexasSolver ≥1000h → recover
  30+ bb/100? + GTO Wizard AIVAT improves.** If <15 → range-tracking/abstraction/integration wrong, or diagnosis off.
- **P1b — Intervention ablations** (empirical −160 decomposition, cheap): variants {solver-sizing-only,
  solver-facing-defense-only, solver-river-line-only}, each paired vs TexasSolver 1k+ → which leak is biggest.
  Because the cache has no per-action EVs, outcome-based paired ablation is the honest decomposition.
- **P2 — TURN resolver** (if P1 proves out). Turn sub-game, compact action abstraction, solve **turn→river to
  terminal** (slower, ~seconds, still no value net). Attacks turn/river line-context + turn defense. Gate as P1.
- **P3 — Richer supervised blueprint** (the fallback + range-tracker policy; necessary, NOT sufficient). A
  multi-action net `(public state + hand + range summaries) → full action distribution`, trained on MORE solved
  NODE TYPES (facing-bet per size, x/r, probes, delayed cbet, river block/overbet) — not just lead/cbet. Needs a
  bigger, public-state solve set. Plateaus ~−40..−80 alone → it's the blueprint, the resolver is the edge.
- **P4 — CFV value net + flop resolving** (LATER; only if speed/flop is the bottleneck). RE-EXTRACT CFVs from
  TexasSolver (the cache lacks them; modify `mass_solve` to dump per-range CFVs) → train a small CFV net (L1 on
  CFVs, NOT frequencies) on the RunPod GPU → depth-limited flop resolving with the net as the leaf oracle
  (DeepStack/Supremus). The biggest build; deferred until river/turn prove the direction + flop-speed matters.

## Honest expectation (no hype)
We will NOT beat GTO Wizard (least-loss; the leaderboard ceiling for an excellent agent is ≈ −3 bb/100). Realistic
recovery from the current −33 (GTO Wizard) / −160 (TexasSolver), per gpt-5.5's honest ranges: **river-only**
~+30–60 (TexasSolver scale); **river+turn** ~+70–120; **+key flop x/r** ~+90–140. On the GTO Wizard AIVAT scale,
the goal is to move **−33 → single-digit-negative** (toward the −3..−10 leaderboard-competitive band) over P1→P2,
and closer with P3/P4. Every claim re-measured (paired + AIVAT); a phase that doesn't recover EV at >2σ is reverted.

## Files
**CREATE:** `pokerbot/strategy/range_tracker.py`, `pokerbot/strategy/resolver.py`, `pokerbot/benchmark/resolver_ablation.py`.
**MODIFY:** `pokerbot/strategy/bot.py` (river/turn resolver branch behind `use_resolver`, floor fallback),
`pokerbot/strategy/gto_oracle.py` (custom weighted-range solve helper if needed), `extraction/mass_solve.py` (P4: CFV dump).
**REUSE:** `gto_oracle.solve` + the `gto_oracle_match.py` live-solve/adapter machinery; the paired `duplicate.py` +
`gto_oracle_match.py` (paired) + `gtow_run.py` (AIVAT) gates.

## Verification
P0: range-tracker unit tests (sums, line-shrink, dead cards). P1/P2: paired vs TexasSolver ≥1000h recover >2σ +
GTO Wizard AIVAT improves; `tests.test_bot` green; resolver timeout→floor fallback never errors. P1b: ablation
table decomposes the −160. P3: held-out multi-action MSE + the blueprint doesn't regress the resolver. P4: CFV-net
L1 error → the 2ε exploitability bound; flop-resolve speed.

## Risks
1. **Speed** (the real one): seconds/solve → fine for analysis/benchmark + a strong slow bot; live snappiness needs
   P4 (value net) / caching / tighter action abstraction. Don't promise snappy live play from P1/P2.
2. **Range-tracker fidelity** = the linchpin; a bad range reconstruction makes the resolver worse than the floor.
   Gate P1 hard; if it doesn't recover EV, suspect the tracker first.
3. **Off-tree / action-abstraction mismatch:** our bot's own off-tree sizes vs the solver's discrete tree; map
   carefully (reuse the head-to-head's snapping). Residual cost remains (as vs GTO Wizard's own abstraction).
4. **Complexity vs the consolidation ethos:** this DOES add a real capability — but it's JUSTIFIED by a measured
   −160/−33, not speculative. Each phase is proof-gated; revert what doesn't pay.
5. **6-max:** real-time resolving is PPAD-hard / no safe bound in multiplayer (o3 + our solvability memo). HU-only
   for MVP#2; 6-max stays the heuristic brain.
