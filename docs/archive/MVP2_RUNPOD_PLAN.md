# MVP#2 — closer to GTO: the $140 RunPod run, sequenced by ROI

Synthesis of two vetted consults (`docs/runpod_gto_gpt55.md` = systems/architecture, `docs/runpod_gto_opus46.md`
= poker-strategy) + the empirical fact that **TexasSolver v0.2.0 dumps frequencies only, NO CFVs** (verified:
node keys = `actions/childrens/node_type/player/strategy`). Grounded in the measured **−33 bb/100 AIVAT vs GTO
Wizard** (behind Opus 4.6 −20.4) and the **river resolver result −12.9 (n=150, confirming at 2500)**.

## The convergent verdict (both models independently agree)
- **The leak is CONTEXT-COLLAPSE**, not missing frequencies. A bot that matches marginal bet/check frequencies
  but is blind to line/SPR/ranges/size-faced "bets the right amount with the wrong hands" — a near-GTO opponent
  extracts from every mis-assigned hand. So **more board-only frequency data would NOT move bb/100** (would repeat
  MVP#1's failure). The fix is **public-state-conditioned, situation-specific play** = real-time re-solving + a
  CFV value net + accurate range tracking.
- **The range tracker is the lynchpin** (Opus): a resolver given wrong input ranges produces wrong output. P0's
  line-aware ranges are v1; postflop Bayesian narrowing is the refinement that matters most.
- **Honest ceiling:** −3 is NOT a $140 outcome. Realistic: **−33 → −20…−15** (GPT-5.5), plausibly beating Opus 4.6.

## ★ The key sequencing insight (ROI-ordered) — the $140 run is the LAST mile, not the first step
Both consults' EV decomposition shows most of the gain is **$0 live-solving + heuristics**; the $140/CFV-net buys
the hardest last mile (flop resolving). So spend money LAST, after the free wins are measured:

| Phase | What | Cost | Expected (consult ranges) | Gate |
|---|---|---|---|---|
| **A** | River resolver = default on ALL rivers (built) + **TURN resolver (P2)** + blocker-aware hand selection | **$0** (live solves + heuristic) | −33 → **~−15…−10** | GTO Wizard AIVAT ≥2500h |
| **B** | **CFV evaluator** (post-solve tree-EV pass) + local pilot (1–2k solves, validate CFVs: zero-sum + range-EV) | **$0** | unblocks C | CFVs sane, deterministic |
| **C** | RunPod **MINI-pilot first** (~$2–5, 1–2 h) to validate on-pod → scale incrementally only if it pays; **NOT the full $140 up front** | **~$5, then incremental** | local pilot (B) passed |
| **D** | Train CFV value net + richer public-state blueprint (GPU) → integrate for **flop/turn depth-limited resolving** | (in C's $10) | −10 → **~−5…−3-ish** | CFV L1 ≤0.03–0.05 pot |

**Discipline (GPT-5.5, verbatim): build & pilot the CFV dump BEFORE spending the money — "if the CFV dump isn't
working, stop, do not launch."** Phases A+B are local/$0 and come first; the $140 (C) fires only after B validates.

## The $140 run design (GPT-5.5, corrected for our reality)
- **Box:** 64 vCPU / 256 GB RAM, AMD EPYC community/spot, **~$0.80/hr**. **48 parallel TexasSolver workers**,
  `OMP_NUM_THREADS=1` (many independent 1-thread solves, NOT one big multithreaded job). RAM-adaptive (mass_solve
  already does this). ~150 CPU wall-hours ≈ **$112** + **~$10** short GPU train (RTX 4090/A5000, 20–30h) + buffer.
- **What to solve (~600k root public states, TURN-HEAVY):** 50k flop / **300k turn** / 250k river. Turn-heavy
  because the river resolver already exists and turn CFVs are the training target for flop depth-limited resolving.
  Every item is a **public state** (board + street + pot + SPR + to-act + IP/OOP + **action history** + **both
  ranges from the range tracker** + size-faced), NOT a bare board.
  - **Range pairs (real, not generic symmetric):** SRP 45% / 3BP 30% / 4BP 10% / limp 15%.
  - **Boards:** cover all 1,755 canonical flops once + texture-uniform oversample (60% natural / 40% texture);
    turn/river runouts **stratified** by range-shifting cards (overcard, flush/straight-complete, board-pair, brick).
  - **SPR:** **≥80% at the benchmark depth = 200bb** (GPT-5.5's skeleton said 100bb — CORRECTED; the GTO Wizard
    bench is 200bb → deeper SPRs, overbets matter more). SPR variation comes from line/pot geometry, not stack grid.
  - **Bet trees:** COMPACT, matching the runtime resolver (flop 33/75 + 3x + jam; turn 50/100 (+150 if SPR>3) +
    2.5x + jam; river 33/75/125 + jam), max 2 raises. **Facing-bet defense per size** (25/33/50/75/100/150/jam) is
    the explicit MVP#1 blind-spot fix — extract the child AFTER villain bets (conditional range), never the
    unconditional pre-bet range.
- **What to dump:** strategy (per-combo) + **root CFVs** (both players, all combos, card-removal-normalized, pot-
  units, masked) + **action EVs** (for EV-regret-aware loss). zstd Parquet/JSONL, float16. ~50–150 GB.
- **CFV computation (the build, since the solver doesn't dump them):** post-solve recursive tree-EV pass over the
  solved average strategy + ranges → conditional hand EV per combo per node + per-action EV. Validate by zero-sum
  (Σ rᵢ·Vᵢ ≈ −Σ r₋ᵢ·V₋ᵢ) + range-EV sanity. Do NOT infer CFVs from aggregate frequencies (impossible).

## Poker priorities for the node-type sampling + a validation suite (Opus 4.6)
- **EV-leak ranking** (where to aim compute): #1 river facing bets/raises (~8–12 bb/100; blockers, over/under-fold
  by size, thin value) · #2 turn barrel/check + check-raise + delayed-cbet/donk (~6–10) · #3 facing-bet defense
  with correct COMPOSITION (~4–7) · #4 sizing by texture + overbets + small river bets (~3–5) · #5 check-raise
  construction (~2–4) · #6 polar-vs-merged (~2–3) · #7 range protection / checking strong (~1–3).
- **Re-solve priority:** T1 = all rivers facing ≥50% pot + river SIZING + facing overbets · T2 = turn barrel/check
  + OOP donk leads · T3 = flop check-raise + 3BP/4BP flop.
- **Balance to enforce:** river bluff:value by size (1x→50% bluffs, ⅓→20%, 2x→60%), blocker-selected bluffs; turn
  barrel/check hand lists; **c-bet sizing by texture** (dry/paired→25–33% hi-freq, wet→50–75% lo-freq, monotone→
  check-heavy/large, advantaged-turn→overbet 125–200%); defend vs 150%-overbet = MDF 40% with best blockers.
- **7 hard-check spots → a regression suite** (`tests`/bench): river 150%-overbet on bricked board (right HANDS,
  not just freq) · turn donk after flop checks-through · 3BP monotone flop (check ~70%) · river thin value vs
  check-back · SB open range/size (200bb ~70–85%) · raise vs small (25–33%) river bets · 4BP AA low flop (call, not
  raise). These make the context-collapse fix FALSIFIABLE per-spot.

## Do NOT (GPT-5.5)
Board-only freq solves · freq-only dumps · over-investing river mass-solve (live resolver supersedes it) · huge
6-size bet trees (sparse labels) · self-play-RL-from-scratch on $140 · irrelevant stack depths · deploying an
unvalidated CFV net (bad CFVs poison resolving, worse than none) · declaring victory on another n=30 sample.

## To-do
- [ ] **A1** Verify the river resolver fires on EVERY river decision in `bot.py` (not gated away); widen if needed.
- [ ] **A2** Build the **TURN resolver** (`resolver.py`: solve turn→river to terminal, navigate the turn line, sample) + wire `use_turn_resolver` in `bot.py`. Clone of `river_resolve`.
- [ ] **A3** Blocker-aware hand ordering in defense/bluff selection (cheap, no solve) — Opus rec #4.
- [ ] **A4** Encode Opus's 7 hard-check spots as a deterministic per-spot regression (right HANDS, not just freq).
- [ ] **A5** MEASURE Phase A vs GTO Wizard AIVAT (≥2500h). Decide if the $0 wins already hit ~−10.
- [ ] **B1** Build the **CFV evaluator** (post-solve tree-EV) in the solver wrapper + dump schema (CFVs + action EVs).
- [ ] **B2** Local pilot (1–2k solves): validate CFVs (zero-sum + range-EV), wall-times, file sizes.
- [ ] **C1** Provision the 64-vCPU RunPod box; extend `mass_solve.py` (public-state sampler + range pairs + CFV dump); pilot on-pod; **production ~600k solves**. **ALWAYS `--kill` when done.**
- [ ] **D1** Train CFV net (turn first) + richer blueprint (GPU); validate EV-regret; integrate into flop/turn resolving.

**Bottom line for the spend (user directive, 2026-06-15 — "starte erstmal kleiner"):** do NOT commit the $140 up
front. The next steps need NO RunPod at all — Phase A + B are **local/$0** (`mass_solve.py` is built to hammer the
LOCAL CPU; a small CFV solve-set + a tiny CFV net can be proven entirely locally for $0). RunPod enters ONLY as a
cheap pilot (~$2–5) AFTER (i) the local pipeline is proven AND (ii) Phase A's measurement shows we still need the
extra EV (the $0 wins may already capture most of it). Scale incrementally; never provision the full budget
speculatively. The $140 stays untouched until a small run has proven it pays.
