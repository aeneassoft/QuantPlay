# META-STRATEGY — winning the game-of-strategies (2026-06-14)

## 1. The core unification: exploitation and GTO are the SAME loop
Your recursive-exploit-loop intuition is mathematically correct and it dissolves the whole "GTO vs exploit"
tension. **Iterated best-response (fictitious play / CFR) converges to equilibrium:**
- Best-respond to a **real opponent** = **exploitation** (the edge vs the field).
- Best-respond to **yourself**, iterated and time-AVERAGED (self-play) = **converges to GTO** —
  Nash in heads-up (2p zero-sum), a CCE in 6-max (multiplayer is PPAD-hard, no-regret only reaches a CCE;
  see `sixmax-solvability`). So the recursive loop *does* arrive at GTO (HU) / a bounded-exploitability
  blueprint (6-max).
- **Same engine, two targets.** We never had to choose. ONE recursive best-response engine gives both the
  exploit edge (point it at opponents) and the GTO floor (point it at itself).
- **Where the NET comes in:** the loop needs a way to REPRESENT the converging strategy across the enormous
  state space. Tables/heuristics can't → they have a ceiling (our measured ~-22 bb/100 vs Slumbot, 31% c-bet
  gap). The function approximator that closes it = a neural value/policy net. That is exactly **Deep-CFR /
  NFSP**, and the SOTA **Supremus** (DeepStack lineage: CFVnets + DCFR+, millions of solver samples →
  0.3 bb/100 exploitability). So: **recursive exploit loop + net = the path to true GTO.**

## 2. Is GTO a gimmick, or do top pros play it?
**Not a gimmick.** Top HUNL pros play *very* close to GTO (the solver era trained everyone); 6-max pros
study it heavily. → At the TOP you cannot out-GTO them, only minimize loss + exploit small deviations.
vs the **FIELD** (everyone below perfect GTO = essentially everyone) exploitation is the edge.
**Conclusion:** to win the meta-game you need BOTH — a GTO floor (don't get crushed by the top) AND
exploitation (crush the field). Unified by the loop in §1. So **yes, eventually we must also build the net**
to compete in GTO arenas — but it is the *second* lever, not the first.

## 3. Are we better than Pluribus? (honest + how to test objectively)
- vs near-GTO opponents: **No** — Pluribus is research-grade GTO+search; our floor isn't there yet (the net
  closes this).
- vs the exploitable **field**: **plausibly yes** — Pluribus plays a near-static blueprint with little
  adaptation; we ADAPT/exploit. This is our thesis and must be MEASURED, not assumed.
- **Objective edge test (the gate for all exploit work):**
  1. our adaptive bot (exploit ON) vs the exploitable suite (`beat_them_all`) — bb/100, **duplicate-gated**.
  2. a STATIC near-GTO bot (GTOBaseline, exploit OFF) vs the SAME suite — the contrast. **adaptive ≫ static
     ⇒ exploitation is a real, objective edge.**
  3. vs Pluribus: decision-alignment (`pluribus_bench`) + exploit-projection (`pluribus_leaks`, ~+4 bb/100 on
     its over-folding) + duplicate vs a Pluribus-imitator.

## 4. Do we need a net to MAXIMIZE exploitation?
- To START exploiting: **No** — a heuristic baseline + opponent model already exploits the field NOW.
- To MAXIMIZE + to make the loop converge to GTO: **Yes** — the net is the generalizer, and exploiting
  relative to a *more accurate* GTO reference yields cleaner, larger, safer exploits.
- → **Phase it:** exploit now (heuristic floor, Build A); add the net (the self-play loop) when committing to
  GTO-tier. The net is not required for the edge; it is required for the ceiling.

## 5. Compute: fully load GCP at high leverage WITHOUT upgrading
- Free-tier hard cap = **12 vCPU global, no GPU**. Within that, the high-leverage use is a **continuous
  12-vCPU TexasSolver coverage campaign, CURRICULUM-DIRECTED** (the LLM's one good use: point the solver at
  the worst-TV-gap / uncovered spots — turn/river, 3bet pots).
- This generates the **GTO DATABASE** = the bottleneck-asset feeding (a) the floor tables (turn/river → kills
  the -22), (b) the future Deep-CFR net's targets / warm-start, (c) the exploit baseline.
- €260 ≈ ~5 weeks of continuous 12-vCPU solving (more on spot/preemptible). **No account upgrade.**
- GPU stays on RunPod (only when we build the net).

## 6. The meta-game-winning sequence
1. **Objective baseline (now):** measure our exploit edge vs the suite + vs a static bot + vs Pluribus
   (duplicate-gated). Know, objectively, whether exploitation is a real edge.
2. **Build A — the recursive exploit engine (now, CPU, no net):** opponent model → bounded exploit proposal →
   verify/gate → apply → observe → update (closed loop); + extract "Beyond GTO" + the playbook as the
   exploit-knowledge seed; + a self-play scaffold (bot vs bot, averaging) = the seed of the GTO convergence.
   Crush the field, MEASURED.
3. **GCP campaign (parallel):** curriculum-directed 12-vCPU solving → the GTO database (turn/river first).
4. **The net (when committing to GTO-tier):** Deep-CFR / NFSP on the GCP data → the self-play loop converges
   to a GTO floor that ALSO exploits. This is literally "arrive at GTO via the recursive loop" + the
   Supremus-tier path.

**Bottom line:** ONE engine — recursive best-response — wins the meta-game: exploitation vs the field now,
and (via self-play + a net) convergence to GTO vs the top later. The GCP campaign feeds it. Build the edge
first (A), the GTO floor when we commit (net). We do not pick a side; the loop is both.
