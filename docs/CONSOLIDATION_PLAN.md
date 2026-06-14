# CONSOLIDATION & UNIFICATION PLAN (2026-06-14)

The point: we've accumulated a LOT (knowledge + code + measured results). Before more big builds, get the
house in order, treat the bot as a DATABASE, eradicate errors, and make the exploit↔GTO design coherent.
Perfect to do NOW while the GCP 256-CPU/GPU quota pends (~business days).

## Constraints / compute reality
- **GCP big runs BLOCKED ~days** (256 quota requested; can self-adjust to ≤12 vCPU now, no GPU). → **Don't wait.**
- **RunPod-first for GPU** (validated this session: H200/Hopper, spot, `--kill`). **12-vCPU GCP** only for a small
  CPU chunk. **OPTIMIZE: only high-leverage calcs** — spot, cost-capped, curriculum-directed, killed when done.
- SOTA references provided: **Supremus** (DeepStack lineage: CFVnet value-net + DCFR+ + depth-limited re-solving,
  0.3 bb/100 exploitable) + **Pluribus** (blueprint MCCFR + depth-limited search; near-static, minimal adaptation).

## PHASE 0 — Get the house in order (NOW; no big compute)
- **0A — Knowledge as a database.** Inventory all of `knowledge_base/` (concepts, ranges, math, exploit
  [262 book primitives + 11.5k+240 playbook], theory [95 AGT], caches). **Claude consolidates the EXPLOIT
  knowledge into ONE deduped, schema-normalized DB** keyed `opponent_stat → spot → bounded adjustment` →
  `knowledge_base/exploit/unified.json` + an index. (The 262+playbook overlap heavily → dedup is the win.)
- **0B — Repo + bot refactor.** Move PDFs → `books/`; group scattered scripts; clean module layout; update
  `CLAUDE.md`/`STATE.md`. A documented, navigable root (currently PDFs + one-off scripts litter it).
- **0C — Audit & STATISTICAL bug-hunt.** Actively hunt errors + statistical problems and eradicate:
  the dead `GTOBaseline` aggressor-branch in LIVE play; the exploit-gate edge cases (unknown-C underperformed);
  equity-MC variance / seeds; any residual spew; the `pick_value_size`/sizing paths. Every fix grounded-gated
  (solver TV-gap / held-out / duplicate). Reuse `bot_audit.py` + add explicit statistical checks.
- **0D — Extract Supremus + Pluribus papers** → `knowledge_base/theory/` (CFVnet, DCFR+, depth-limited
  re-solving, blueprint MCCFR, abstraction, search; + the "Pluribus barely adapts" lesson = our edge). Grounds
  the net path.

## PHASE 1 — Unify exploit + GTO (NO mismatch) — the architecture
The unification, made concrete so there is no exploit-vs-GTO mismatch:
- **FLOOR** = the GTO anchor (calibrated tables now; the self-play net later). It is the strategy you play
  when you have no read.
- **OVERLAY** = a BOUNDED best-response deviation (exploit), `freq_delta ∈ [-0.3,0.3]`, confidence-gated,
  applied ON TOP of the floor's frequencies. Capped → worst case ≈ floor + probe budget.
- **No mismatch because:** (1) the overlay is a *delta on the floor*, not a separate strategy; (2) the SAME
  best-response engine yields both — point it at the opponent = exploit, point it at itself (self-play) =
  converges to the floor (GTO/CCE); (3) the gate ensures the overlay only fires on a verified read, else pure
  floor. Document this in `INTEGRATION.md`. Then wire the unified exploit DB (0A) as the overlay (Build A).

## PHASE 2 — Compute-optimized builds (RunPod-first; high-leverage only)
- **Build A (CPU/local, no big compute):** unified-exploit overlay wired + objective re-test (vs the suite +
  a near-GTO opponent), duplicate-gated. → the measured edge.
- **Self-play→GTO net (Deep-CFR, RunPod GPU):** the Supremus/Pluribus recipe (value net + CFR self-play +
  depth-limited), warm-started by solver data. The beat-GTO-bots path. Spot + `--kill` + cost-capped.
- **Solver data:** 12-vCPU GCP now (curriculum-directed at the worst-TV-gap spots) → scale on GCP when the 256
  quota clears, or RunPod CPU. High-leverage only.

## Next logical step (prepped)
After 0+1: the **self-play→GTO net on RunPod** — grounded by the extracted papers + the unified architecture +
the curriculum solver data. That is how we stop losing to near-GTO; the overlay keeps the field-edge.

## Running rules
High-leverage compute only (no wasteful runs); spot + cost-cap + `--kill`/auto-stop; only a grounded gate
(solver TV-gap / held-out / duplicate / LBR) accepts a change; honest measurement, never hype.
