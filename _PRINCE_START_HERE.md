# ★★★ ROOT MARKER — READ THIS FIRST (updated 2026-07-05 evening) ★★★

> **UPDATE 2026-07-05:** the shipped bot = **PRINCE v3** (v2.2 + pair-defense + river-bluffcatch-defense;
> paired-Analyzer 17.93 vs 20.66, tag `v2` = the restore point before it). Four gated levers await their
> Analyzer arms (v3.2 thin-sel / v3.3 raise-narrow / v3.4 audit-fix / v3.5 advisor-role). decide() is 12.1×
> faster and the instruments are process-deterministic now. The live-AIVAT blinds-inversion bug is FIXED
> (every pre-fix live number carried a preflop over-fold). v4 = depth-limited CFR + neural leaves (the path
> below −8): `docs/RESEARCH_SWEEP_2026-07-05.md`. Everything below = the 2026-07-04 founding context.

**THE MISSION: build VERSION "PRINCE" and WIN bb vs GTO Wizard.** Doctrine (user, measured, non-negotiable):
**the GTO-score is DEAD as a target — ONLY bb count** (frequency-matching GTOW measured -EV; chasing score cost money).

## Where we stand (all measured 2026-07-04)
- Engine HEAD: AIVAT **−20.09 ± 7.18** (n=974) = #11 of the public leaderboard (behind only frontier LLMs, MIT, a pro).
- **GTO-mode: −11.61 ± 3.67 (n=100 smoke)** — the best measured config → would slot ~#7.
- **The deception layer SHIPPED** (`POKERB_TURN_DEFENSE=0.07` + `POKERB_SLOWPLAY=0.25`): canary +39.1 ± 19.9 paired ✓,
  mechanics ✓ (the user's "check=no King" read is DEAD: P(K|check) 9→17.3% ≈ prior; fold-to-stab 44→37.6%).
  Live in the HU app launcher; `POKERB_PRINCE=1` = GTO-mode + deception (gto_mode.py, fingerprint-complete).
- The bleed = POSTFLOP: river −8.6 + flop −8.3 bb/100. Opponent intel: GTOW = the Ruse REAL-TIME re-solver —
  translation/bet-size attacks REFUTED ($0, 13.5k hands): `docs/GTOW_DOSSIER.md`.

## THE ACTIVE BUILD CARD → `docs/VERSION_PRINCE.md` (§3b = the merged build order from 3 deep audits)

## ★ PRE-STAGED for the NEXT COMMAND ("identify the 3 biggest levers, implement, test vs GTOW"):
The queue analysis (91 audit finds + 44 paper/book levers, ranked by bb ÷ effort ÷ risk) pre-selects:
1. **FLOP→TERMINAL RESOLVER** (`POKERB_FLOP_RESOLVER`) — the biggest single unaddressed bleed (flop −8.3 has NO
   re-solve; entry ranges are the cleanest). Papers + books converged independently. **Go/no-go FIRST**: solve-time/
   timeout on ~50 logged flop spots (half a day, $0) — a flop subtree ≈ 50× the turn tree.
2. **RIVER VALUE = equity vs the CALLING range** (`POKERB_RIVER_ECALL`) — replace the magic surrogate
   (postflop.py:140) with re-equity vs call-worthy combos; size UP to the largest census arm keeping eq≥0.55.
   The highest-confidence content fix (two books name the exact rule); makes the +98bb-jam line legal.
3. **LINE COHERENCE: correlated per-hand sampling** (`POKERB_LINE_U`, ~20 lines) — ONE uniform per hand at the three
   advisor gates → monotone barrel/give-up lines. The degenerate line-planner; its result gates the full HandPlan.
   (+ Q1 exact villain-size injection into the resolver as the free rider — hours, floor-0 risk.)
**BUILD INSTRUMENTS FIRST (rung 0, hours):** the deterministic REPLAY HARNESS over the 34 graded disaster hands
(`data/gtow_grades/*.json` — zero consumers today!) + the solve-CONVERGENCE audit (TexasSolver prints exploitability;
`gto_oracle.py:107` discards it). Every lever then rungs: harness → canary (`research/duplicate_mode_ab.py` pattern)
→ graded export (seed-paired) → 100-hand live smoke (`tools/gtow_client`, key #2, ~17 min) → the pre-registered A/B.

## ★ TONIGHT'S CONTINUATION (2026-07-05, autonomous #1-mission; execute in order)
1. **Read the v2.2 300-smoke** (task bwawy6w39; log lands in data/sessions/): AIVAT ± SE + count hands ≤−100bb
   (the stack-off rate) + 5%-trim body via `gtow_tail`.
2. **Fire the v2.3.1 OVERLAY smoke** (same 300, dev key #2): env `POKERB_PRINCE=1 POKERB_BARREL_DISCIPLINE=0.18
   POKERB_TURN_DEF_ADVISOR=1 POKERB_TURN_OVERBET=1` + `tools/gtow_client/src/main.py --agent_type=pokerbot
   --num_hands=300 --num_concurrent_hands=10` (clear_inprogress first if 409s). v2.3.1 gates ALL GREEN:
   stress 13/0 · replay 16-flips/7-clean · canary passes-with-caveat (GTOBaseline can't price discipline).
3. **Compare the live pair** (v2.2 vs v2.3.1: AIVAT, tail-rate, ±) → winner becomes the PRINCE profile
   (add the 3 overlay flags to PRINCE_PROFILE in gto_mode.py if v2.3.1 wins).
4. **The 2,500-hand precision run** (dev key, overnight ~9h, pre-registered: vs GTO-mode −11.61 anchor,
   claim needs delta > 2·SE; report raw ± SE + trimmed body + x-ray + fingerprint).
5. Queue next (each gated): TURN-PROBE vs flop check-back (Q6 fang: GTOW's check-back = 63% air, 1.9% traps —
   attack it) · the equity-inflation root (texture/aggression-aware range weighting) · KK-node preflop consult ·
   river-discipline C1 (spec + 66 formulas on disk). Q6 anchors: `data/freq_targets/gtow_frequencies.json`.
**Mission: leaderboard #1 (beat −3.14). Honesty gates NEVER bend: pre-registered n, no mid-run extension,
"+" = artifact until the body agrees, ship at gate-tested values only.**

## KEY DOCTRINE (user decision 2026-07-05)
- **Key #2 ("Quantplay"/Hampe) = the DEV/TEST environment** — all smokes/gates run here; the aggregate is written
  off (−32.7 over 2.5k hands, polluted, NOT deletable — the API has no DELETE by design, anti-cherry-picking).
- **The public leaderboard entry** (gtowizard.com/benchmark) = a FRESH key the user registers via the
  benchmark.gtowizard.com form (their action, not ours) — that key sees ONLY final gated versions, ever.
- In-progress hands throttle concurrency (409s): `tools/gtow_client/src/clear_inprogress.py` before big runs.

## Standing rules (hard-won today)
- n=100 AIVAT = smoke, never a claim; a "+" vs GTOW = artifact until the trimmed body agrees; pre-register n.
- Ship at the EXACT gate-tested values (no silent retuning after a passed canary).
- One lever at a time through the $0 rungs; bundle only in the final A/B profile.
- Key files: `docs/VERSION_PRINCE.md` (build card) · `docs/STATE.md` (live truth) · `docs/GTOW_DOSSIER.md` (opponent)
  · `docs/TIE_GTOW.md` (ledger) · `data/gtow_grades/LEAK_MAP.md` (per-decision leaks) · `INDEX.md` (map).
