# QUANTPLAY — THE FUNDAMENTAL FINAL ARCHITECTURE (2026-07-06)

> Not "the perfect player" — the SKELETON on which everything further iterates. Triply founded:
> (1) the measured COMPETENCE MATRIX (`data/research_sweep/component_matrix.json`, every component vs
> TexasSolver oracle), (2) the OpenAI architecture consult (`data/research_sweep/openai_architecture_consult.json`),
> (3) our own night empirics (precision doctrine, Gate-0 Leduc, v8 live break). All three say the same.

## The edge (unchanged, now formalized)
No new algorithm. The edge is **the architecture + the cheapest honest measurement loop + the
GTOW vampirism** (superhuman teacher for cents: revealed cards, per-decision grades,
frequencies). Every organ sits where it is MEASURABLY the best; compute sits at the decision point,
not in an omniscience table.

## The organs at their measured places (competence matrix, 36 regions)
| Region | Best (measured) | GTO gap |
|---|---|---|
| Preflop (all) | **blueprint** (near-Nash CFR) | leads |
| Flop (8/9 regions) | **advisor_mlp** | 0.23–0.34 |
| Turn (10/12) | **advisor_mlp** | ~0.3 |
| River (9 value / 5 exploit) | **advisor_mlp** or **exploit_overlay** | ~0.3 |
| EVERYWHERE last place | **formula_floor** | 0.53–0.71 (fallback only now) |
CRITICAL MATRIX GAP: the LIVE RESOLVER was NEVER evaluated with 0 solves → its region wins are
unmeasured. That is the next measurement step (bounded resolver solves), NOT a design assumption.

## The 7 layers (order = call order per decision)
1. **Blueprint** — preflop, near-Nash. Stays. (Matrix: wins preflop.)
2. **Range tracker** — THE multiplier. Feeds ALL downstream organs; wrong ranges = confident
   wrong (v8 break, measured). → HIGHEST LEVER, see below.
3. **Importance-aware scheduler (NEW, architecture gap #1)** — decides per (pot, SPR, texture, line)
   WHICH organ + which bet menu. Replaces today's coarse "solve/no-solve @300s" cap. No more
   iteration budget on $1 pots.
4. **Off-tree translator (NEW, gap #2)** — maps arbitrary real villain actions (overbets, min-raises,
   delay lines) EV-impact-aware onto the small on-tree action set + adjusts ranges. A piece of −20→−10
   bleeds today through mishandled freak lines.
5. **Flop library (NEW, gap #3)** — offline pre-solved flop archetypes (board cluster × pot/SPR ×
   bet menu), online = table lookup. THAT is the flop-bleed fix — NOT a live net. (OpenAI + our
   NOTES queue #1 agree; live flop solve is measured NO-GO, 49/50 timeouts.)
6. **Live resolver (turn+river)** — where the scheduler calls it worthwhile; precision can be turned up
   (more iters, exact enumeration — costs only compute, changes no behavior).
7. **Advisor MLPs** — the measured strongest static layer; fallback where (5)/(6) do not apply.
   **exploit_overlay** regime-aware (gap #4), primarily river/turn, smooths back to the baseline.
Below that: **formula_floor** as a pure emergency fallback (matrix: never wins, but graceful degradation).

## WHERE the new NET is +EV (your core question — consult ranking, honestly)
- **NOT the central engine.** A global all-street net is −EV/dead end (Gate 0 proved: off-
  distribution error dominates, 70 vs 31 mbb). Replacing the advisor MLPs is not worthwhile (matrix: the tiny
  advisors already win).
- **+EV only at THREE narrow places, and ALL subordinate:** (a) a turn-boundary leaf net to ENABLE depth-limited
  FLOP resolving — structurally important, but only runnable after tree abstraction + gadget
  (Gate-0 line); (b) a river leaf net for SEARCH CUTTING in large trees (saving cost, not quality);
  (c) a range-residual net as DENOISER on the tracker — but only AFTER the structural range fixes.
- **Where precision beats the net:** everywhere the subgame is small enough to solve AND the inputs
  are right → more solver iters / exact enumeration beat any 125KB net. Nets reserved for
  NEW search regimes (flop) or cost cutting — never where 2–5× more iters fetch the same gain.

## The highest single lever: RANGE TRUTH (not a net)
Both sources: range quality multiplies EVERY organ; a 10–20% KL error costs more than any
0.5% solve tightening. The clean fix uses our 13.5k GTOW-REVEALED hands as ground truth —
statistical CALIBRATION, no net:
1. Key every decision node by abstract state (position, stack/pot bucket, line abstraction, texture cluster).
2. Compare tracker output R̂ vs empirical reveal frequency f_K per key (cross-entropy, calibration).
3. Learn the logit correction δ_K = logit(f_K) − logit(R̂), smooth over similar keys, fall back for keys with n<30.
4. Two-stage tracker online: Bayes → δ_K correction → renormalize. Evaluate on held-out keys.
5. Optional residual net only AFTER that (the only justified net deployment close to the core).

## The build order (precision doctrine, every step against anchor tag v2 = −19.70)
1. **Range calibration** (reveal data → δ_K) — highest lever, $0, deterministic.
2. **Flop library** (offline solves, board clusters) — the flop-bleed fix.
3. **Importance scheduler + off-tree translator** — coordination logic, no net.
4. **Resolver precision up** (iters/enumeration) where the matrix (after resolver grading) shows it.
5. **Patch nets** last, narrow: turn boundary (enable flop resolve) / river cut / range residual.
None of this CHANGES a decision; all of it computes it MORE PRECISELY. The final version is this skeleton
wired — it does not have to play perfectly, it has to BE the right architecture.

## STREET DOCTRINE (User, 2026-07-06) — where compute vs. game theory belongs
The streets differ fundamentally in their SOLVABILITY, and that determines the organ assignment:
- **Preflop = pure COMPUTATION.** Small, near-Nash, solved (blueprint). No theory of mind.
- **River = COMPUTATION (path already walked).** Terminal, arriving range defined, subgame small →
  solvable in seconds. The compute focus (RIVER_SYSTEM.md).
- **Flop/turn = GAME THEORY / strategy / theory of mind.** Here the tree explodes (48 turns × 44 rivers
  ahead), here live multi-street plans, range shaping and fold equity. NOT repairable by river play:
  over-fold/over-commit/range damage BEFORE the river (OpenAI consult Q1). → Flop/turn JOB = do not
  damage the range, do not overcommit, maximize FOLD EQUITY, arrive at a river that is not already lost.
CONSEQUENCE (= the measured architecture, now justified): blueprint preflop (compute), advisors flop/turn
(fast distilled heuristic = the "strategic" layer — one gets away CHEAPLY here without a perfect
solve), live solver river (compute). The compute budget belongs on the COMPUTABLE streets (preflop done,
river the focus); flop/turn is handled strategically/heuristically with a fold-equity goal, not solved perfectly.
DATA-DENSITY SEQUENCE (pod compute): QUALITY BEFORE DENSITY. Range calibration ($0, local) FIRST; only when the
river diagnostic score after calibration shows coverage as the residual bleed is pod mass solving (flop/river
library, uint8) justified — otherwise one builds expensive libraries on uncalibrated ranges that go stale.
