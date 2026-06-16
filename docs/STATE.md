# PROJECT STATE — start here (for a fresh Claude session)

> Living entry point. Read this first, then [CLAUDE.md](../CLAUDE.md) for conventions. Last updated **2026-06-16**.
> The cross-session memory lives at `C:\Users\hampe\.claude\projects\C--Users-hampe-Desktop-PokerB\memory\` (index: `MEMORY.md`).

## ★★★ CURRENT (2026-06-16) — NEURAL SELF-PLAY GTO CORE. SUPERSEDES every number below.
> ⟳ LIVE source of truth. Per the CLAUDE.md standing rule, update THIS top section before ending any turn that
> moves the headline, lands a build, or shifts priorities.

**The pivot:** the solver-IMITATION floor is a MEASURED ceiling — decision-grade **~−72 bb/100 vs GTO Wizard AIVAT**
(n≥2500; BROAD postflop loss, not a fixable leak; run-to-run noise ±8). The river resolver fed too-wide ranges also
HURTS (−72…−76 < Always-Fold −64.6); the range-tracker keystone did NOT recover it. So we are building our OWN
**from-scratch neural Deep CFR self-play GTO core** — pure self-play, NO imitation (AlphaGo-Zero logic).

**Built + proven this session:**
- `strategy/deep_cfr.py` — from-scratch Deep CFR on Leduc with EXACT exploitability + a `vanilla_cfr` ground truth
  (converges to Nash). **DCFR+ added + validated: neural Leduc 445→338 mbb (LinearCFR plateaued ~445), still falling.**
- `strategy/deep_cfr_hunl.py` — self-contained cloneable HUNL game (fcpa, treys showdown; self-test passes) +
  external-sampling MCCFR + dual nets (advantage + policy). The first HUNL net BEATS call-station/always-fold/random.
- `strategy/deepcfr_adapter.py` + `bot.py:use_deepcfr` + `gtowizard.py:POKERB_DEEPCFR` — net→bot wired, feature
  reconstruction VERIFIED (0 mismatches). **GTOW baseline of the first fcpa net PENDING.**

**Next run — [NEXT_RUN_TODO.md](NEXT_RUN_TODO.md)** (4 sources converge — MoP theory, the AAAI-26 DCFR+ paper, GPT-5.5,
Supremus): finer bet abstraction (`0.33/0.5/0.75/1/1.25/2/allin`) + richer features (card occupancy + hand-class/draw/
texture, ideally OpenSpiel's info-state tensor) + the DCFR+ port, gated by a paired GTOW A/B. Honest plateau priors:
fcpa −50…−80 · fine-abstraction −20…−45 · value-net+resolving −15…−30 · mature Supremus −5…−15. Policy-net-only
plausibly beats −72; *matching* GTOW likely needs real-time resolving.

**Clean boundary (HARD rule):** external assets (books/papers/PokerBench/Pluribus/OpenSpiel/the LLM) = validation /
design / exploit-overlay ONLY, NEVER a training label (imitation IS the −72 ceiling). Validation gates: Leduc exact
exploitability + the clairvoyance toy-game (α=1/3, MDF=1/2 at pot, river-only — `docs/math_theory_net_connection.md`).
Compute: the Python MCCFR traverse is the bottleneck (NOT the GPU) → no B200 until a GPU-native job (OpenSpiel C++
traverse / the value-net pipeline). **vs the field we still crush: Slumbot +31, weak bots +300–700.**

---

## History (2026-06-15, superseded by the neural pivot) — MVP#2: real-time resolving + range tracker
> ⟳ This is the LIVE source of truth. Per the CLAUDE.md standing rule: after any measurement that moves the
> headline, any build that lands, or a priority shift, update THIS section *before ending the turn*.

**Thesis (exploit-primary):** GTO = floor/insurance; the edge = exploiting each opponent's gap to GTO. vs the
exploitable field we WIN big; vs true near-GTO we minimize loss (can't beat it).

**Live headline — GTO Wizard AI, the #1 benchmark (key ACTIVATED; AIVAT, ~10× variance-cut):**
- **DECISION-GRADE (n≈2500, ±~6): the integrated bot is ~−71 vs GTO Wizard, resolver ON or OFF.** Floor (resolver
  OFF) **−70.73 ±5.83** ≈ resolver+v1 **−72.06 ±6.70** — statistically IDENTICAL → the resolver is NEUTRAL (not a
  spew source); the FLOOR ITSELF is −71. BOTH the MVP#1 −33 (n=30) and the resolver −13 (n=150) were LUCKY
  small-sample MIRAGES. **−71 < Always-Fold (−64.6)** ⇒ the integrated bot actively loses chips to near-GTO. Honest
  truth (= the user's diagnosis, now MEASURED): **many parts, NO coherent working MVP yet.** vs the exploitable
  field it still wins (Slumbot +31) — the thesis holds, but the near-GTO floor is far worse than small samples
  suggested. **→ PLAN: [docs/MVP_UNIFY_PLAN.md](MVP_UNIFY_PLAN.md).** Catalog DONE ([BOT_PARTS_CATALOG.md](BOT_PARTS_CATALOG.md);
  §0 = the fragmentation map: two playing brains, an orphaned exploit cluster, dead files). Path: **Phase A** unify
  into ONE core ($0; wire `preflop_gto` into HU bot, reliability-gate the resolver by confidence+pot-size, delete
  dead code) + measure @ n≥2500; **then the ONE sure compute** = solve facing-bet nodes → a **facing-bet DEFENSE
  advisor** (the #1 leak + it unblocks the range tracker's call-narrowing), local-pilot-first then scaled on **≥3
  parallel best-CPU pods, saturated, fast**. ONLY in-repo assets. LESSON, hard: n≤150 AIVAT lies.
- vs **Slumbot** (exploitable): current MVP **+31** (was −102 pre-fix) — crushes the exploitable field.

**Built this session (MVP#2 = supervised blueprint + real-time re-solving + range tracker, the Pluribus/DeepStack
pattern):** `strategy/range_tracker.py` (P0 line-aware ranges) · `strategy/resolver.py` (P1 river + P2 turn: live
TexasSolver re-solve of the actual public state to terminal, sample our hand, floor-fallback) · `bot.py`
`use_resolver`/`use_turn_resolver` · `benchmark/gtowizard.py` adapter + `tools/gtow_run.py`. The GTO Wizard
Benchmark paper (arXiv 2603.23660) VALIDATES this (GTO Wizard AI = real-time-solving + value-net + balanced ranges).

**★ THE keystone — BUILT + integrated + unit-tested (2026-06-15, "Goldbach" session); EV-gate PENDING.** The
quadruple-triangulated #1 (code-review + Opus 4.6 + GPT-5.5 + our notes) = a **Bayesian action-consistent postflop
range tracker** → `strategy/range_tracker.py` v2 (`RangeTracker` + `weighted_ranges`): per-combo Bayes (advisor
`P(bet)` for bet/check; o3-safe **legality-only** for silent call/raise/size — never zeros a live combo),
class-level weighted emit (TexasSolver v0.2.0 CAN'T take per-combo strings — verified, matches our own finding),
confidence-gate → floor. Wired into `_river_resolve`/`_turn_resolve` (builds on the turn resolver, no clobber);
`test_range_tracker` 4/4 + `smoke_weighted_resolve` green. **OPEN — the decision: the P1 EV-gate** = does
resolver+v2-tracker recover the river resolver's **−72**? Three-way vs GTO Wizard: floor baseline · resolver+v1
ranges (−72) · resolver+v2 tracker (one session at a time). **HONEST caveat (verified at the emit):** calls are
legality-only (safe, but no narrowing) → flop-called air stays in the range (96o weighted top on A-K-7-2-9) →
ranges still WIDE → may only PARTIALLY recover; if so the next lever = a facing-bet **defense model** so calls
filter. Cheap win still open: wire `preflop_gto.py` (88.6%) into HU `bot.py` (verified NOT wired). Docs:
[GTO_GAP_REVIEW](GTO_GAP_REVIEW_2026-06-15.md) · [GTO_P0_RANGE_TRACKER](GTO_P0_RANGE_TRACKER_2026-06-15.md).

**Plan / spend:** [MVP2_RUNPOD_PLAN.md](MVP2_RUNPOD_PLAN.md) — closer-to-GTO sequenced by ROI. The $140 RunPod run
is the LAST mile (CFV value-net → flop resolving); **start small/local first** (user directive). Consults:
`runpod_gto_gpt55.md`, `runpod_gto_opus46.md`, `situational_*`. Honest ceiling vs GTO Wizard: **−20…−15 near-term**
(GPT-5.5); ≈0/−3 is NOT a near-term/$140 outcome.

**★ Update (late 2026-06-15) — defense outcome + SHORT-DECK pivot.** Defense advisor (the #1-leak fix, $0 from
existing caches): flop-defense floor −70.7 → **−66.4** (+4.3, marginal/not-sig); adding RIVER defense → **−80.6
(HURTS −14, reverted to flop-only)** — frequency-match-but-lose AGAIN (river = big pots, the +19%-MSE advisor still
loses bb/100). NLHE is the working baseline (crush field / least-loss vs GTO Wizard); we STOP grinding it.
**New direction (DECIDED + GPT-5.5-refined → `docs/shortdeck_consult_gpt55.md`): exploit-vs-field 60% [the only
MEASURED +EV path, the core] / HU-short-deck-postflop near-GTO DEMO 25% [the buildable, measurable artifact —
driving now] / NLHE-defense 15% [leak-patch].** Short-deck = solver-NATIVE (`gto_oracle.solve(mode="shortdeck")`,
Gate.1 re-verified), rule-LOCKED (bundled dict = **trips>straight** variant — flagged for any Triton product);
`engine/sd_eval.py` evaluator built+verified (flush>boat, trips>straight, 7-card, no 2-5; dict keys = ASCII sort).
Cache pilot: 120 flops (`extraction/mass_solve_shortdeck.py`). **Honest claim = "near-TexasSolver HU short-deck
postflop", NOT "6+ solved"; measure via EV-gap + matched-tree BR/LBR, NOT MSE.** Tasks #78–80. Origin: the Goldbach
Movie-Factory run (`SD_6PLUS_GATE_LOG.md`).

> The ★★/★ sections below are MVP#1 + earlier — correct as history, but their headline framings (the −526/−160 and
> "GTO Wizard key 401") are SUPERSEDED by this section. Read them for detail, not for the current state.

---

## What this is
A Heads-Up **and** 6-max No-Limit Hold'em bot grounded in three poker books, a browser app to play it, an
online opponent-exploiting layer, and tooling to measure our play against true GTO. North star: a
**universal adaptive exploiter** — a low-exploitability baseline + an online opponent model that detects and
safely exploits each opponent's leaks (confidence-gated), built to handle opponents we haven't seen yet.

## ★★ Final MVP build + DEFINITIVE scorecard (2026-06-15, supersedes below)
**Plan:** `.claude/plans/adaptive-rolling-fog.md` · **Scorecard:** `pokerbot/benchmark/scorecard.py` → `knowledge_base/scorecard.json`
The exploit-primary pivot is now a SHIPPED MVP: ONE `PokerBot(exploit=True)` = solver-grounded floor (flop/turn/
**river** advisors) + a safe river EV-exploit engine + a bounded prediction-gated off-tree size probe. A/B toggles:
`use_turn_advisor/use_river_blocker/use_fe_sizing/use_mdf_shade/use_river_advisor/use_probe`. Measured KEY-FREE:
- **Least-loss vs near-GTO (decision-grade):** flop GTO-gap **31%** (floor frequencies MATCH the solver — bet 47.4%
  vs 47.1%, OOP 22/22, IP 75/74); floor vs GTOBaseline (paired) **−22 ±64 ≈ break-even**. Competitive vs near-GTO.
- **Exploit edge (the thesis, DELIVERED):** crushes the exploitable field — station +109, maniac +224, nit +58,
  foldy +78, sticky +135, trappy +42 bb/100; mechanism **+33 vs a steep size-cliff**. Ties its own strong mirror
  (PokerBot vs PokerBot −53 ±60 = noise). → huge edge vs the exploitable, ~break-even vs near-GTO = exactly the thesis.
- **WS1 floor-bleed RESOLVED:** the −102 vs Slumbot was variance/Slumbot-specific, NOT a leak (`floor_ablate.py`:
  no toggle moves the floor >2σ vs GTOBaseline; #40 river-blocker 0 effect, #41 turn-advisor +8 sub-1σ). #40/#41 kept.
- **WS2 river advisor (the win):** `build_river_data.py`+`train_river_advisor.py` (1308 caches) → `river_advisor.pt`
  **+51%** vs freq baseline → **+38.6 ±15.6** paired floor improvement (closes the last un-grounded street, NOTES #4).
- **WS3 unify:** AdaptiveExploiter kept as a labelled reference; the probe re-enables the off-tree edge; the Dirichlet
  per-node model is the calibration. **WS5 GTO Wizard harness READY-TO-FIRE** (`benchmark/gtowizard.py`, offline-tested).
- **⚠ [SUPERSEDED — the key was ACTIVATED later the same day; see ★★★ CURRENT at top. Below = pre-activation state.] The GTO Wizard key was tested LIVE (2026-06-15) and returned `401 Unauthorized`** — the 32-char string in the
  file is a placeholder / not-yet-granted (verified UP TO AUTH: cloned + uv-synced 3.13, `gtowizard.py` adapter
  rebuilt vs the real schema + offline-tested, `tools/gtow_run.py` connects; blocked ONLY on a VALID key). Once a
  valid key exists, going live
  (user's call — outward-facing, spends the 100k/mo quota) = the DEFINITIVE measure vs the true opponent: clone
  `gtowizard-ai/researcher-api-client` under `tools/gtow_client/` (Py3.13/uv), confirm the adapter's CONFIRM-ON-CLONE
  items, run `--num-hands 200` then ≥2500 (AIVAT) + leaderboard.
- **vs TexasSolver (2026-06-15, both built):** (A) deterministic GTO-gap (`floor_map` flop+turn+river) = **flop 31% /
  river 29%, FREQUENCY-FAITHFUL** to the solver (our-bet 47/47, 30/31; turn locally unmeasurable — local cache is
  DUMP=1, the DUMP=2 turn subtrees were on the killed pod); (B) head-to-head bb/100 (`benchmark/gto_oracle_match.py`,
  MVP vs a live-solver-driven oracle, 40bb) = **+185 ±133** vs an APPROXIMATE oracle (full SRP ranges, no
  continuation-narrowing → our bot exploits the wrong turn/river ranges; NOT beating true GTO; ~1.4σ noisy). The gap
  (frequency-match) is the trustworthy GTO-closeness signal. (tombos21 = Tom Boshoff, GTOW head coach; r/pokertheory
  validates the simplified-grounded approach.)
- **Next:** (1) user decides the GTO Wizard live run; (2) confirmatory large-N Slumbot run to close the −102;
  (3) optional: extend the GTO-gap to turn+river, port the TwoModelGate/Calibrator if the field shows it's needed.

## ★ Latest session — Consolidation, Unification & Phase 1 (2026-06-14/15, supersedes older detail below)
**Plan:** [docs/CONSOLIDATION_PLAN.md](CONSOLIDATION_PLAN.md) · **Architecture:** [docs/META_STRATEGY.md](META_STRATEGY.md)
- **Exploit↔GTO unified (no mismatch):** ONE best-response engine — pointed at the opponent = exploit, pointed
  at itself (self-play) = converges to the floor (GTO/CCE). Live design = a GTO **floor** + a BOUNDED,
  confidence-gated exploit **overlay** (`freq_delta∈[-0.3,0.3]`) on top; no read → pure floor.
- **Floor sharpened (grounded):** preflop exact-lookup table distilled from PokerBench (**88.6%** held-out,
  beats both LoRAs) → `knowledge_base/ranges/preflop_gto_table.json` + `strategy/preflop_gto.py`, wired into
  sixmax RFI. Postflop priors solver-CALIBRATED (cbet_eq 0.48→0.72, held-out TV-gap 0.62→0.50). sixmax made
  role-aware → measured solver gap 45%→31%.
- **Knowledge-as-database (Phase 0A):** 5 books extracted via Claude → **262 exploit primitives** + **95 AGT
  theory** concepts; deduped to **62 stat-keyed wireable rules** → `knowledge_base/exploit/unified.json`. The 2
  SOTA papers (**Supremus**, **Pluribus**) → **27 recipe items** (CFVnet 7×500 zero-sum MLP, bucketing
  1326→1000, DCFR+, depth-limited re-solving) → `knowledge_base/theory/`. Grounds the eventual self-play net.
- **Phase 0C bug-hunt (3 agent-audited + verified fixes):** sixmax decision rng was reseeded per-spot → fake
  (deterministic) mixing → now persistent rng (real mixing, 117/83 over 200 same-spot calls); gto_baseline's
  calibrated c-bet branch was DEAD live (no `aggressor` key) → now derives initiative from history; opponent.py
  exploit stats jumped prior→raw at n≥4 → Bayesian shrinkage (k=6). Tests green; duplicate null still 0±0.
- **Phase 0B:** source PDFs moved to `books/` (papers under `books/papers/`).
- **Objective edge CONFIRMED:** adaptive+gate beats a diverse suite (worst +27 bb/100), 2× extraction vs static.
  Exploitation is a real MEASURED edge; vs near-GTO the ceiling is ~break-even (needs AIVAT to measure).
- **Net verdict (refined):** a net is the eventual path to a true GTO floor (Supremus = proof) via self-play,
  but a big build for an unmeasurable near-GTO gain — DEFERRED behind the cheap floor + the field-edge.
- **Compute:** GCP 256-CPU/GPU quota requested (~business days); ≤12 vCPU adjustable now. → **RunPod-first**
  for GPU + 12-vCPU GCP for small CPU; high-leverage calcs only; spot + `--kill`/auto-stop.
- **Phase 1 DONE (2026-06-15), all gated:** (a) live HU bot range-c-bets at the calibrated texture freq
  (medium+air, 36→82% on dry boards, duplicate A/B +23); (b) the 62 rules wired into the exploit channel —
  which was DEAD (`_pb` computed but never applied → the playbook + LLM-directive seam never ran) → REVIVED;
  the rules help vs exploitable (station +308, maniac +262, no leak vs strong). **Simplify sidequest gold:**
  river equity now ENUMERATED not Monte-Carlo'd (exact, 9× faster, killed a 3% pot-odds decision-flip noise
  bug). All committed; full test suite green (test_web_client needs a LIVE HU server on :8000 — an in-process
  TestClient smoke confirms the HU app is healthy). Phase-1 consult was done WITH gpt-5.1; gpt-5.5 is on the API.
- **Next (awaiting user go):** **(c) self-play→GTO** — prove convergence on Leduc first, then warm-start from
  solver caches, then RunPod GPU (high-leverage only). Remaining simplify Tier-A: turn-enum → suit-canonical
  equity cache. Activate more live opponent stats to fire the gated-off unified rules (~27/62 fire now).

## Run it
- 6-max vs 5 bots (main app): `python -m pokerbot.web.six_server --open` → http://127.0.0.1:8000
- Heads-Up + live coach: `python -m pokerbot.web.server --open`
- Windows / PowerShell, Python 3.12. `pip install -r requirements.txt`. Always run from root as `python -m ...`.

## Honest status (what's real vs projected)
- **Preflop**: GTO-grounded (verified Nash push/fold CFR blueprint + strength-model ranges deeper).
- **Postflop**: equity + pot-odds/MDF + fold-equity-optimal sizing + an exploit layer — **not** a solver.
- vs **Slumbot** (measured 2026-06-14, 300h): the old "heuristic alone ≈ −170" was a small-sample MYTH — the
  no-exploit floor really lost **~−526 bb/100** (it **stacked off 200bb bluff-raising air**). A cheap anti-spew
  fix → **~−46 bb/100** no-exploit (near break-even, +480 swing). WITH the fold-curve exploit on the fixed
  floor: **~−5.4 bb/100** (500h, ±113 ≈break-even; was −186 pre-fix — not yet conclusive, needs 5–10k hands).
- vs **Pluribus** (from its 10k hands): it over-folds postflop → projected ~+4 bb/100 (ceiling ~6–8); small,
  real, safe (it never adapts).
- Crushes weak/exploitable opponents locally (+300–700 bb/100).
- The deficit vs near-GTO Slumbot WAS mostly a fixable SPEW (now fixed), not pure exploitability — the floor
  still has cheap wins before a GTO net is strictly needed.

## Scorecard (2026-06-14, the first HONEST one — measured, not projected)
Engine compare vs a diverse suite (`beat_them_all`-style, 250h/match) + Slumbot:
- **`PokerBot(exploit=ON)` BEATS EVERYTHING** — worst case **+1 bb/100** (vs the strong peer); station +493,
  maniac +757, sticky +393, trappy +161; and **≈−5 bb/100 vs Slumbot** (500h). This is the robust +
  exploitative "universal" bot the project wanted — the anti-spew fix created it.
- `PokerBot(exploit=off)`: most robust (worst +44) but crushes weak less.
- `AdaptiveExploiter`: crushes weak HARDEST (+727/+1275) but **leaks −47 vs the strong peer** — it
  over-specializes. Root (measured, knob-by-knob): adaptive's BASE decide() is weaker than PokerBot's
  (−56 with all exploit knobs OFF), NOT a mis-tuned gate. So the real upside = port adaptive's SAFE extras
  (calibration, playbook cold-start, LLM strategist) ONTO PokerBot's robust floor, not the reverse.
- LBR v1 too loose to score the floor (loses −987 to it; nit-sanity +75 OK) → needs v2 for a hard number.
- **Takeaway:** our strong main bot is `PokerBot(exploit=ON)`. Edge work = sharpen exploitation ON this
  floor + validate at scale. The GTO net is deferred insurance (and now cheap via the GCP credit).

## Current workstream (2026-06-14): a strategic LLM + a GTO oracle + an exploit playbook
Three resources were run in parallel (the clean split — see the memory note [[pod-run-validation]]):

1. **GPU (RunPod B200): Qwen3-8B LoRA fine-tune on PokerBench** — [extraction/qwen_sft.py](../extraction/qwen_sft.py).
   The strategic/language layer (exploit hypotheses, coaching, curriculum), **not** a per-hand player.
   At step ~90/987 it was already 96% token-accuracy → converges fast; full 987 steps unnecessary.
   Output LoRA → `/root/qwen_poker_lora` (retrieve, then `--kill` the pod). Needs torch cu128 on Blackwell.
   - **HARD LESSON**: on ONE box a heavy CPU job and a GPU-training job cannot coexist (CPU starves GPU
     kernel-dispatch *and* sshd → unmanageable). "Both at 80%" needs **separate** pods. So:
2. **CPU (local i9-12900K): TexasSolver mass-solve** — [extraction/mass_solve.py](../extraction/mass_solve.py)
   (RAM-adaptive; 16 GB box → ~5 parallel solves, auto-scales). Builds a GTO cache for distillation/benchmark
   in `data/_gto_bench_cache/` (regenerable; gitignored). ~16 boards/min.
3. **Claude API: exploit playbook** — [extraction/exploit_playbook.py](../extraction/exploit_playbook.py).
   Bounded, machine-checkable exploit directives across an opponent-profile × spot grid (a PROPOSER pass;
   the benchmark verifies before anything is applied). Artifacts:
   - `knowledge_base/exploit/playbook.jsonl` — 11,520 directives (Haiku).
   - `knowledge_base/exploit/playbook_opus_coarse.jsonl` — 240 directives (Opus, high-quality subset).

## What the GTO cache already tells us (from [extraction/analyze_cache.py](../extraction/analyze_cache.py), 597 flops)
- **IP c-bet by texture** (robust GTO signal): dry/high/rainbow/paired ~77–78%, monotone 58%, connected 60%,
  low 67%, overall 74% → c-bet more on aggressor-favoring boards, less on caller-favoring ones.
- **C-bet sizing**: ~96% of c-bet mass uses ONE size (~⅔ pot) — GTO barely mixes sizes here.
- **OOP donk**: 22% overall (likely **inflated by non-tuned ranges** — real BB-vs-BTN SRP donks <8%; validate
  the `_OOP/_IP` ranges before acting on the absolute number; the texture-relative direction is fine).

## Shipped 2026-06-14
- **★ Duplicate-poker VERIFY GATE + net-vs-database verdict + LLM-match reality (the linchpin block).**
  - `pokerbot/benchmark/duplicate.py` — mirror matching cancels card luck (null test: 0±0 vs naive ±132).
    THE tool for reliably accepting/rejecting a bot change at small samples (no AIVAT needed). Use:
    `duplicate_ab(make_a, make_b, gen_decks(n))`. Caveat: rare-but-large-swing changes still need many decks.
  - **thin_value RESOLVED via the gate: NEUTRAL** (0.72 vs 0.78 → −7.1±9.7 @300 decks, +8.75±8.9 @1000;
    straddle 0). The earlier revert was right; `bot.py` now exposes `self.value_raise_eq` (A/B hook, default
    0.72 = unchanged).
  - **NET vs DATABASE verdict (the strategic answer):** we do NOT need our own neural net yet. A net is just a
    generalizer trained ON a database; measured bottleneck is DATA COVERAGE not model size; our heuristic floor
    already generalizes + is ≈break-even; edge = exploitation not GTO. → the bigger solver DATABASE is the more
    fundamental need, as the GROUNDED-VERIFY resource (not a lookup table, not yet net-training-data). Build a
    net only if heuristics provably plateau below it (LBR/duplicate). Deep-CFR self-play = deferred.
  - **RunPod 32-vCPU CPU coverage-solve RUNNING** (`extraction/runpod_solve_*.sh`, pod is6nj19spqb1f7, $1.12/h,
    ~200 turn-boards/h; GCP free-tier capped at 12 vCPU). Pull cache + `runpod_run --kill` on completion.
  - **LLM-match reality** (`pokerbot/benchmark/llm_opponent.py`, strong PokerSkill-style prompt + reasoning):
    vs frontier LLM agents we are ROUGHLY EVEN at noisy 40-hand samples — Opus 4.8 +30, o3 +17 (the naive
    gpt-5.1 +395 was a prompt-weakness + noise MIRAGE). Reliable opponent-strength needs AIVAT = the GTOW key.
- **Active-learning toolkit + the verify-lesson + 6-max solvability (autonomous block).**
  - `extraction/blindspot_radar.py` — massive concurrent Claude-Haiku triage of bot decisions → ranked
    suspected blindspots. LESSON (hard-won): LLM triage is a HYPOTHESIS generator, not truth — it flagged
    `thin_value_too_big` with high confidence; the fix was MEASURED neutral-to-worse → reverted. Also
    play-testing bb/100 is too NOISY to verify a single rule. → use the GROUNDED signal + solver to verify.
  - `extraction/grounded_blindspots.py` — per-spot solver-disagreement from the cache (matches gto_benchmark:
    IP-high 23%, OOP-connected 24%). The reliable acquisition signal. Real grounded floor gaps: OOP donks the
    wrong (strong) hands; IP OVER-c-bets (95% vs GTO 79%). Use the AGGREGATE (gap+bet-freq), not top-individual.
  - **GCP pipeline VALIDATED** (`extraction/gcp_solve_setup.sh` + `gcp_solve_launch.sh`): TexasSolver-Linux +
    mass_solve run end-to-end on a VM. BUT free-tier is capped at **12 vCPU global (CPUS_ALL_REGIONS)** → the
    big saturated coverage-solve needs an account upgrade / quota increase. Project id `project-f2a4a8eb-7533-4ecf-a00`.
  - **6-max solvability (gpt-5.1, `data/sessions/solvability_6max.md`):** 6-max NLHE is NOT solvable like HU —
    PPAD-hard, Nash non-unique, no-regret → CCE not Nash, no scalar exploitability. Realistic target = a
    **bounded-exploitability blueprint + adaptive exploit** = exactly this project's thesis (validated). North
    star: minimize measured LBR exploitability while maximizing realized bb/100 vs the exploitable field.
- **★ Anti-spew floor fix + independent bot audit (the session's biggest MEASURED win).** Traced the no-exploit
  floor's catastrophic loss vs strong opponents to ONE leak: it bluff-RAISED air (eq<0.33) at ~pot size =
  effectively all-in on deeper/later streets, and value-raised dominated top pair, because `PriorFoldModel`
  over-assumes folds. Fix (`bot.py`): the floor never raise-bluffs without a confident read; value-raise + SPR
  commitment caps. **Measured: no-exploit vs GTOBaseline −912 → +207 bb/100; vs Slumbot −526 → −46.** Then an
  independent `claude-opus-4-8` audit (`extraction/bot_audit.py`, every finding hand-vetted; it called the code
  "mostly sound") found the SAME spew live in `adaptive.py` — root cause = no range-narrowing vs aggression →
  over-rated marginal hands → over-committed. Fixed (range-narrowing ported from `gto_baseline` + commitment
  caps + a preflop-4bet premium gate); 200bb stack-offs eliminated (worst hand −20000 → ~−7762). Phases 1.1–1.4
  (EV-correct value sizing, texture c-bet, MDF defense, gated Pluribus fold-exploit) also shipped + committed.
- **Self-calibrating fold-equity** ([pokerbot/strategy/calibration.py](../pokerbot/strategy/calibration.py)) —
  a prediction->measurement->calibration loop (ported from the Mycelium crypto bot's learning-engine), wired
  into `adaptive.py`: logs predicted-vs-observed folds in the spots we ACTUALLY bet (selection-aware), bias-
  corrects future fold-equity, exposes a data-driven confidence. None-safe (no data -> behaviour unchanged).
  Tests: `python -m tests.test_calibration`. Persisted per opponent under `data/calibration/<name>.json`.
- **GTO-floor net v0 (distillation)** ([extraction/distill_improve.py](../extraction/distill_improve.py)) on the
  1340-board solver cache (local RTX 3080 Ti): added minibatching to `distill.train` (full-batch underfit
  328k samples); 256³ net → held-out **TV-gap 17.7%→17.0%**, saved `data/floor_net.pt`. **KEY FINDING
  (empirically validated, not just taken from the OpenAI tips): bigger nets barely move it → the bottleneck is
  DATA COVERAGE, not the model.** Vetted OpenAI (gpt-5.1) advice via [extraction/cfr_tips.py](../extraction/cfr_tips.py).
- **Exploit playbook WIRED** into the adaptive engine as a cold-start prior ([pokerbot/strategy/playbook.py](../pokerbot/strategy/playbook.py)):
  nearest-profile lookup -> bounded, confidence-FADED nudge (bluff / value / bluff-catch); `directive_to_nudge`
  is the SAME channel the live LLM strategist will write into later. Tests: `python -m tests.test_playbook`.
- **LBR exploitability evaluator** ([pokerbot/benchmark/lbr.py](../pokerbot/benchmark/lbr.py)): a Local-Best-Response
  lower bound via rollouts with RE-SAMPLED hidden cards (no hidden-info cheat) + passive continuation.
  VALIDATED (crushes a nit +75+/-4 bb/100). v1 (uniform range) is a LOOSE bound -> too weak to find a leak in
  the baseline floor yet (LBR loses to it); v2 = Bayesian action-consistent range for a tight number.
- **Qwen LoRA fine-tune SAVED** (step-500, 97% token-acc) -> `models/qwen_poker_ckpt500/` (adapter 666 MB);
  pod auto-killed (billing stopped). The strategist layer for the INTEGRATION plan. **Eval PROVEN:** held-out
  PokerBench decision-match **base 18.3% -> LoRA 71.7% (+53pp)** ([extraction/qwen_eval.py](../extraction/qwen_eval.py)).
- **LLM integration COMPLETE (proven end-to-end).** `meta_coach` gained a `provider="local"` (LoRA in 4-bit via
  transformers, no vLLM) -> `propose_exploit` emits a bounded directive -> `directive_to_nudge` ->
  `AdaptiveExploiter.refresh_llm_exploit()` installs it as `live_directive` -> applied (capped) in `decide()`.
  The LoRA follows the exploit-directive JSON schema (Qwen3 `<think>` tokens disabled/stripped). Demo:
  `python -m extraction.llm_exploit_demo`. Call `refresh_llm_exploit(coach)` per SESSION (not per hand).

## Open threads / next steps (in priority order)
0. **GTO floor — the #1 lever (now evidence-backed).** The distilled floor plateaus ~17% TV on SRP-flop-only
   data. Real gains need, in order: (a) **coverage campaign** — broaden the solver cache (turns, rivers, 3-bet
   pots, stack depths) with a wider TexasSolver tree (CPU); (b) finer **action buckets** (add overbets) +
   EV-weighted loss + post-hoc calibration; (c) an **LBR (local best response) evaluator** for HONEST NLHE
   exploitability (TV is only a proxy — a low TV can still be exploitable). Then wire `floor_net.pt` as the
   policy floor (`cfr_policy.py`, see [INTEGRATION.md](INTEGRATION.md)). Methodology lab: validate CFR+ on the
   self-contained Leduc Deep-CFR (`deep_cfr.py`, exact exploitability) before any NLHE self-play.
1. ✅ DONE — Qwen LoRA saved to `models/qwen_poker_ckpt500/` (step-500, 97%); pod killed (no billing).
2. Eval the saved LoRA vs base Qwen on held-out PokerBench locally (RTX 3080 Ti) to prove the decision gain.
3. **Make `gto_baseline` c-bet texture-aware** (high on dry/high/rainbow, low on monotone/connected) and fix
   the size to ~⅔ pot — the concrete bot change the cache points to. → [pokerbot/strategy/gto_baseline.py](../pokerbot/strategy/gto_baseline.py)
4. **Wire the exploit playbook into the adaptive engine** as a cold-start prior (nearest-profile lookup,
   confidence-gated). → [pokerbot/strategy/adaptive.py](../pokerbot/strategy/adaptive.py)
5. Serve the fine-tuned Qwen (vLLM) and point `meta_coach(provider="openai", base_url=…)` at it — the
   in-loop strategist. → [pokerbot/coach/meta_coach.py](../pokerbot/coach/meta_coach.py)
6. (Tournament mode, future) **ICM / risk-premium** multiplier on short-stack stack-off thresholds in
   `cfr_preflop`/`blueprint`: a tournament stack IS a bankroll with an absorbing barrier (ruin), so chips
   have concave utility — decline +chipEV / −$EV gambles near pay jumps. This is the in-game home for the
   Mycelium fractional-Kelly + CVaR lens (only relevant once we add tournament play; cash stays linear EV).

## Map (cross-references)
- **Engine**: `pokerbot/engine/` (cards, treys eval, MC equity, HU `game.py`, N-player `table.py`).
- **Strategy**: `pokerbot/strategy/` — `cfr_preflop.py`+`blueprint.py` (Nash push/fold), `postflop.py`,
  `gto_baseline.py` (analytic GTO, texture/aggressor-aware), `gto_oracle.py` (TexasSolver wrapper),
  `adaptive.py` (exploit engine + self-calibrating fold-equity via `calibration.py`), `opponent.py`,
  `pluribus_exploit.py`, `bot.py`.
- **6-max brain**: [pokerbot/arena/sixmax.py](../pokerbot/arena/sixmax.py) (per-seat independent; the 3 fixed leaks).
- **Coach / LLM**: `pokerbot/coach/` — `meta_coach.py` (engine-agnostic), `translate.py`.
- **Benchmark**: `pokerbot/benchmark/` — `gto_benchmark.py` (scores us vs the solver cache), `slumbot.py`,
  `beat_them_all.py`, `pluribus_*`.
- **Heavy compute**: `extraction/` — `mass_solve.py`, `exploit_playbook.py`, `analyze_cache.py`, `qwen_sft.py`,
  `runpod_run.py` (pod lifecycle; always `--kill`), `deep_cfr_nlhe.py`, `pod_run30.py`.
- **Knowledge** (committed): `knowledge_base/` — `concepts/`, `ranges/` (+ `cfr/preflop_pushfold.json`),
  `math/`, `exploit/` (playbooks + `slumbot_fold.json`), `hand_histories/` (10k Pluribus), `theory/`.
- **Plans**: [docs/ROADMAP.md](ROADMAP.md), [docs/POD_PLAN.md](POD_PLAN.md), [docs/RUNPOD_PLAN.md](RUNPOD_PLAN.md).

## Infra notes
- Keys: read from `C:\Users\hampe\Desktop\Secret keys\` (outside the repo) via [pokerbot/config.py](../pokerbot/config.py) — never hardcode.
- RunPod: `--kill` = `DELETE /pods/{id}` = full terminate (compute+storage billing stops). A mere "stop" still
  bills storage. SSH key `C:\Users\hampe\.ssh\pokerb_runpod`; fresh pods get a NEW ssh port (read `--status`).
- Models: Claude `claude-opus-4-8` (quality) / `claude-haiku-4-5` (cheap in-loop); OpenAI auto-resolves to `gpt-5.1`.
