# THE MVP PLAN — from −71 + fragmented → ONE measured, working bot (2026-06-15)

*Supersedes the "CFV-net" framing of `MVP2_RUNPOD_PLAN.md`. Constraints (user, 2026-06-15): (1) be 100% SURE what
we compute + why — no blind pod runs; (2) RunPod, when used = **≥3 of the best CPU pods in PARALLEL, fully
saturated, FAST** (no hours of waiting); (3) work ONLY with what's already in the repo/root — no new books, data,
deps, or external services. Ground truth: the integrated bot is **−71 bb/100 vs GTO Wizard** (decision-grade,
resolver ON or OFF — worse than always-fold) and **fragmented** (`docs/BOT_PARTS_CATALOG.md` §0): two playing
brains, an orphaned exploit cluster, dead files. Goal = ONE coherent decision core, the best parts gated in by
reliability, validated at n≥2500.*

---

## §1 BE SURE FIRST — exactly WHAT we compute, and WHY (the precondition)

The honest read of every decision-grade measurement:
- The floor (advisors + heuristic) MATCHES solver bet/check FREQUENCIES but loses −71 → the leak is NOT missing
  bet-frequencies.
- The resolver (actual live GTO solves) with the current (too-wide) ranges is ALSO −71 → live solving doesn't help
  when the **input ranges are wrong**.
- The range tracker v2 can't fix the ranges because it does **legality-only on calls** (o3-safe, but no narrowing)
  — and it CAN'T narrow on calls because **we have no model of facing-bet defense**.
- The floor's facing-bet defense is **pure heuristic** (`call_thresh = req + MDF-shade`) — the advisors only model
  P(bet) (leading/c-betting), never call/fold/raise. Opus 4.6 ranks facing-bet defense the **#1 EV bleed**.

⇒ **The ONE computation we are SURE about** (it attacks the measured leak AND unblocks the resolver, with a
concrete mechanism, using only in-repo tools):

> **Solve a diverse set of public states whose bet-trees create FACING-BET nodes (per size, across SRP + 3-bet
> pots + an SPR grid + turn/river lines), then train a FACING-BET DEFENSE advisor** (per-combo P(fold/call/raise |
> facing a bet of size s) — the missing floor piece), **plus broaden the existing bet-advisors' coverage** (3-bet
> pots, more SPRs) from the same solves.

Why this and not "more frequency cache" or "a CFV net":
- It fixes the **#1 measured leak** (facing-bet defense — today pure heuristic).
- The defense model is exactly what the **range tracker needs to narrow on calls** → correct ranges → the resolver
  can finally help (turns the −72/−71 path live). One compute, two unlocks.
- It uses ONLY what's in the repo: `extraction/mass_solve.py` (TexasSolver → cache) + the advisor data/train
  pipeline (`build_advisor_data.py` / `train_advisor.py`). No new data, no CFV-net build, no new deps.
- Honest ceiling: vs GTO Wizard the goal is **least-loss** — move −71 toward the LLM tier (−16…−30) / beat
  always-fold (−64.6), NOT beat GTO Wizard. The big +EV stays vs the exploitable field. We do NOT over-promise.

We do not provision a pod until a **local pilot proves this pipeline pays** (start-small discipline).

---

## §2 PHASE A — UNIFY (local, $0, no compute) → the real MVP baseline

One canonical decision core = the HU `PokerBot` (`strategy/bot.py`) — it already has the most (floor + advisors +
exploit-river + resolver). Make it coherent using ONLY in-repo assets:
- **A1 Wire `preflop_gto.py` (the 88.6% PokerBench table) into the HU `bot.py` preflop** — it exists, is better
  than the current strength-heuristic, and the catalog found it's wired into 6-max RFI ONLY. Free win. Gate behind
  a flag; A/B with `duplicate.py`.
- **A2 Reliability-ROUTER (the ensemble, the user's ML-101 point):** the bot = {preflop, floor-advisor, heuristic,
  exploit-river, resolver} each gated by a RELIABILITY signal. Concretely: gate the resolver by **range-confidence
  AND pot-size/commitment** (the −72 harm source = big pots) — not a global on/off. Floor = safe default.
- **A3 Decide the orphaned cluster** (`adaptive.py` + `unified_exploit.py` 62 rules + `playbook.py` +
  `calibration.py`): either PORT-then-gate into `bot.py` (only if a paired A/B shows they help) or SHELVE. **Delete
  dead files** (`pluribus_exploit.py`, `coach/translate.py`, `benchmark/gto_check.py`, `benchmark/improve.py`).
- **A4 MEASURE the unified MVP vs GTO Wizard @ n≥2500** (the only decision-grade bar). This is the real baseline —
  is unifying + the free preflop-table already better than −71? Also re-run the floor baseline numbers.

Phase A needs no pod and no new data. It may already move the number; it definitely de-fragments the bot.

---

## §3 PHASE B — THE COMPUTE (precisely specified, in-repo, parallel-FAST)

**B1 Extend `extraction/mass_solve.py` → a diverse PUBLIC-STATE sampler** (in-repo edit): SRP + 3-bet pots, an SPR
grid, bet-trees that include the facing-bet sizes (25/33/50/75/100/150/jam), flop+turn+river. Output = the same
per-board JSON cache format (atomic writes, resumable — already built).

**B2 Extend `extraction/build_advisor_data.py` → extract FACING-BET DEFENSE nodes** (per-combo fold/call/raise vs a
bet of size s), alongside the existing bet-vs-check nodes. New dataset `data/defense_data.jsonl`.

**B3 LOCAL PILOT first ($0, the start-small gate):** run B1 on the LOCAL CPU for a SMALL set (~1–2 k solves,
~30–60 min), build B2's data, train a defense advisor (`train_advisor.py` recipe), and check it **beats the
heuristic defense on a held-out split**. If it doesn't → STOP, rethink (don't spend pod time). If it does → scale.

**B4 SCALE on RunPod — ≥3 best CPU pods, PARALLEL, SATURATED, FAST:**
- Provision **≥3** of the highest-vCPU community/spot CPU pods (target the biggest available, e.g. 3× ~64–96 vCPU)
  via `extraction/runpod_run.py --cpu`. Each runs `mass_solve.py` SATURATED (RAM-adaptive, ~1 solver process per
  core).
- **Partition the board/public-state space across the pods** (disjoint seed/prefix ranges → no overlap), then
  merge the per-board caches. 3×+ boxes × full saturation → the whole diverse cache in **~1–2 hours wall, not
  many** (the explicit "I'm not waiting hours" requirement).
- Cost ≈ 3 pods × ~$0.6–1/hr × ~2 h ≈ **$4–6** (trivial vs the $140 — parallel-fast is ALSO cheap; honors
  start-small). **ALWAYS `runpod_run.py --kill` every pod when done.** (CPU mass-solve only — no GPU box; the
  advisor train is LIGHT/local.)

---

## §4 PHASE C — TRAIN + INTEGRATE + MEASURE

- **C1** Train the **facing-bet defense advisor** + the broadened **bet-advisors** on the merged cache (in-repo
  `train_advisor.py` recipe; ship only if each beats its baseline by the >3% gate). LIGHT compute (tiny MLPs, local).
- **C2** Wire the defense advisor into the floor's facing-bet path (replace the pure-heuristic `call_thresh`) AND
  into the **range tracker** so calls finally NARROW the range → correct ranges → re-enable the resolver as a
  reliability-gated expert.
- **C3** MEASURE the full MVP vs GTO Wizard @ n≥2500. Decision-grade. Keep only what beats the Phase-A baseline.

---

## §5 TO-DO (ordered)
- [ ] **A1** Wire `preflop_gto.py` into HU `bot.py` (flag + `duplicate.py` A/B).
- [ ] **A2** Reliability-router: gate the resolver by confidence + pot-size (not global on/off); floor = default.
- [ ] **A3** Delete dead files; decide (A/B) the orphaned exploit cluster → port-gated or shelve.
- [ ] **A4** Measure the unified MVP vs GTO Wizard @ n≥2500 → the real baseline.
- [ ] **B1** Extend `mass_solve.py`: diverse public-state + facing-bet-tree sampler (in-repo).
- [ ] **B2** Extend `build_advisor_data.py`: extract facing-bet DEFENSE nodes → `defense_data.jsonl`.
- [ ] **B3** LOCAL pilot ($0): small solve → train defense advisor → beats heuristic on held-out? (go/no-go gate).
- [ ] **B4** If go: ≥3 best CPU pods, parallel + saturated, partitioned, ~1–2 h, merge cache. `--kill` all.
- [ ] **C1** Train defense + broadened bet advisors (>3% gate).
- [ ] **C2** Wire defense advisor → floor facing-bet path + range-tracker call-narrowing → re-gate resolver.
- [ ] **C3** Measure full MVP @ n≥2500; keep only what beats the Phase-A baseline.

**Sequencing logic:** A is $0 and de-fragments + may already help (do it regardless). B3 is the $0 go/no-go that
makes us SURE before any pod. B4 is the only pod step — parallel, fast, cheap. Nothing here adds anything not
already in the repo.
