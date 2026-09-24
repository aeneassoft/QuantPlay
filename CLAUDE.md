# CLAUDE.md — QuantPlay (PokerB until 2026-09-24)

> **⚠ PROJECT CLOSED (2026-09-10). READ FIRST [`docs/PROJECT_BALANCE_2026-09-10.md`](docs/PROJECT_BALANCE_2026-09-10.md)**
> — the critical balance sheet: goal missed, why, what has value, and in which order to continue.
> The doctrine blocks below are history, not a mandate.
>
> **★ PUBLISHED (2026-09-24).** The repo is now called **`aeneassoft/QuantPlay`** (public; the earlier
> game lives under `aeneassoft/quantplay-herzlichter`), default branch `poker-core`. The trainer runs as a
> **static browser version at https://quantplay.io** — the same `six_server` session in Pyodide (Python/WASM)
> in the visitor's Web Worker, no server: `web/build.py` builds `web/dist/`, `web/src/{bridge,worker}.js` route
> `fetch('/api/…')` to `pokerbot/web/browser_bridge.py` (calls the FastAPI endpoints directly, Pyodide has no
> threads). Deploy: `python web/build.py && cd web && vercel deploy --prod` (project `quantplay`, Git integration
> deliberately disconnected). **Rules for a public repo:** no third-party hand histories, no keys, no
> personal files (the hand-history files were moved to `Desktop/PokerB_ausgelagert_2026-09-10/` on 2026-09-24;
> they remain in the git history — history is not rewritten). **License:
> PolyForm Noncommercial 1.0.0** (`LICENSE.md`, operator decision 2026-09-24; rights holder per `NOTICE`: Leonhard Hampe): free for non-commercial use, any
> commercial use only with written permission; the `Required Notice:` line (`NOTICE`) must stay with every copy.
> Test: `python -m tests.test_browser_bridge`.

**Goal: a world-class 6-max No-Limit Hold'em AI that PLAYS GTO — i.e. approaches TRUE GTO.** The AI is three
assets ("the gold"): a **self-growing, EV-grounded dataset**, a **fine-tuned Qwen "brain"**, and **our engine as the
scaffold** the brain drives. Built across many sessions — see the user memory + `docs/STATE.md` for history.

> **★★★★★ POKER IN A NUTSHELL — THE FUNDAMENTAL LINE (user sketch, 2026-07-06; docs/doctrine/POKER_NUTSHELL.md).**
> Poker = the UNPREDICTABLE WAVE (over/underbet) around hand strength, framed by two computable anchors
> (preflop = pure statistics; river = "The Bill", where everything is settled). The wave (flop/turn = game theory)
> serves two purposes: FOLD EQUITY (bet more → folds) + EXTRACTION/milking (bet less → milk the opponent).
> The whole thing MUST be a SEESAW (always switching up → unpredictable + noise) — stop rocking and
> you become readable. **THIS MODEL IS PREDICTIVE:** it explains the v8 live break (Purify flattened the seesaw →
> check range transparent → −20 to −58), the value/bluff polarization (weight per branch at the Bill), the street
> doctrine (preflop/river compute, flop/turn = wave, fold-equity job) and river primacy. **BINDING: the bot
> is a seesaw, not a fixed point — NEVER flatten the mixing/deception. Balance = non-negotiable; the
> rocking ITSELF is the edge; against adaptive opponents the switching over time (Red Queen) becomes the exploit.
> Bankroll/variance (more bluffing = more variance) = a still un-formalized axis.** OBFUSCATION extension
> (user): cryptographic unpredictability of the REALIZATION (CSPRNG instead of Mersenne Twister) for maximum
> opacity — relevant vs ADAPTIVE opponents (humans), irrelevant vs the static GTOW (which exploits the RANGE,
> not the RNG sequence); second order ABOVE balance (obfuscation ≠ balance). Determinism
> tension: seeded RNG for MEASURING, CSPRNG for LIVE play vs humans (context split, like Purify).
>
> **★★★★★ OPERATING DOCTRINE (user, 2026-07-06) — PROFIT EMPIRICISM. GOAL: GTOW LEADERBOARD TOP 5.**
> We are first of all a **statistical pattern-recognition machine over millions of hands**: the only thing that
> counts is what prints bb („nur bb zählen" — "only bb count", now radicalized). **Formulas are SOUP MEAT** (stock, not
> the dish) — MDF/pot odds/e_call/blockers swim as features/priors INSIDE the empirically seasoned deciders
> (the advisor MLPs are the pattern), never as dogma above them. Mathematically elegant + doesn't print = bin
> (measured: frequency-matching 3× refuted). Mathematically "wrong" + prints = shipped (measured: SB-fold-clamp).
> **Axioms as knobs:** MODEL assumptions/equilibrium notions/precision budgets/game perturbations are
> freely turnable with an explicit condition test (`docs/doctrine/CONDITIONAL_POKER_LEMMAS.md`: L1 Purify, L2 Mr-Orange,
> L3 v3.2b, L4 Iso). NOT turnable (not out of dogma — it is the scoreboard itself): chip conservation,
> Σp=1, EV linearity (`tests/test_math_suite.py` guards; 17/17 deep). Lead generator: `research/money_mine.py`
> (AIVAT-weighted P&L attribution; buckets = leads, not proofs — conditioned subsets are not
> unbiased). The only taste test remains the gate ladder — a degenerate without an honest
> scoreboard doesn't know what prints.
> **AIVAT-ADAPTED (paper arXiv:1612.06915 read, ledger):** the mean is by theorem NOT gameable
> ("cannot appear to do better by changing play") → metric-gaming ideas are artifacts by construction.
> Legitimate adaptation: (1) pure EV, (2) low-variance style = tighter SE = cheaper truth (per-hand SD
> 1000→214 measured), (3) on-tree sizings = better baseline fit = less measurement noise.
> **MEASUREMENT ECONOMICS (user observation 2026-07-06, hard):** the **Chrome/Analyzer channel is orders of magnitude
> faster than the API** — export of 1500 hands ≈ 4 min locally (post-memoization), the Analyzer grades them in
> minutes; the live API needs ~8-9h for 2500. → **Analyzer-first**: μ comparisons/arm verdicts run via
> paired seed exports + Chrome upload (scalable: several 1500-blocks per arm = SE/√k); the API is the
> scarce channel ONLY for live anchors, tail smokes and leaderboard entries. Upload rules: CRLF mandatory,
> hand IDs burn on FIRST contact (also on failed uploads — never repeat idbase/dayoffset;
> ledger in STATE).

> **★ NORTH STAR (2026-06-17) — PLAY GTO / ACHIEVE TRUE GTO, in 6-max NLHE.**
> Rigorous target = the **robust correlated equilibrium**. (Einy–Haimanko–Lagziel, *Economic Theory* 2022,
> `books/papers/Springer - Nash + Incomplete Information.pdf`: a Nash eq is *strongly robust to incomplete
> information* **iff** it is the UNIQUE correlated equilibrium; a 2-player zero-sum game with a unique NE has a unique
> CE.) → that is WHY heads-up is the solver/SOTA domain (unique NE → unique CE → strongly robust) and WHY **6-max is
> fundamentally harder** (multiplayer general-sum → no unique-CE guarantee → **strong robustness is NOT free**). So
> "true GTO" here = **lowest achievable exploitability + solver-match + cross-opponent-distribution robustness**,
> enforced EMPIRICALLY. **Exploitation = a BOUNDED, GTO-EVALUATED overlay** (a deviation justified by EV gain vs its
> exploitability cost) — never the goal in itself.
>
> **The approach:** an **LLM brain** — a fine-tuned **Qwen3** (8B first, size-agnostic pipeline → 32B later) — that
> DRIVES our engine via **program-of-thought**: it emits Python calling our engine-API (`pokerbot/brain/api.py`),
> which EXECUTES → an exact, verifiable action. The LLM does NOT *be* a solver; it *orchestrates* one (math by code =
> no LLM-arithmetic errors; legality by the engine; judgment by NL). SOTA value-nets (DeepStack/Supremus) are HU-only;
> a from-scratch 6-max net is DEPRIORITIZED (no clean GTO benchmark + extreme complexity). Plan:
> `.claude/plans/gut-dann-sind-wir-toasty-forest.md` · `docs/plans/QWEN_6MAX_PLAN.md` · `docs/doctrine/DATASET_SPEC.md`.
>
> **★★★ CURRENT TRUTH + VEHICLE (2026-07-04) — THE "−47 ENGINE" IS DEAD; the ENGINE-ALONE is the vehicle toward GTOW,
> and it is FAR better than every number in this repo claimed.** Two things flipped this session:
> **(1) The engine is NOT −47.** A fresh HEAD-default GTOW run (all flags OFF = the shipped `pokerbot/strategy/bot.py`)
> measured **AIVAT −20.09 ± 7.18 bb/100 (n=974)**, BODY **−8 to −11** (5–10% trim), **0 catastrophes**. The −47.18 was
> a STALE ACCOUNT AGGREGATE over dead code eras (the −106 jam-spew era etc.). The body is near the GTOW leaderboard
> (best −3.14, frontier LLMs −9). CROSS-CHECKED: the GTOW-Analyzer per-decision HU EV-loss (**19.3 bb/100**) ≈ the live
> AIVAT (−20) → two independent metrics agree → the loss is REAL deviation cost, not tail luck. The −20 lives entirely
> POSTFLOP (river −8.6 + flop −8.3; preflop −1.6 = near-solved blueprint), in NORMAL pots (not jams).
> **(2) Both disciplines are now ABSOLUTELY GTO-GRADED** (GTOW Analyzer, the repeatable Chrome loop; `research/
> pokerstars_export.py` HU + `research/sixmax_export.py` 6-max): **HU 53.4% GTO-score / Freq-Diff 54.6%** (the shipped
> EXPLOIT-PRIMARY engine deviates from GTO by design → −EV vs near-GTO GTOW) vs **6-max 85.9% / EV-loss 7.61** (the
> `tag` core, far more GTO-aligned). The user chose the **ENGINE-ALONE path** (fast, $0/hand, fully ours); **the goal
> (explicit, 2026-07-04): TIE GTOW (0 bb/100)** — staged via −10; the full ledger + path = `docs/plans/TIE_GTOW.md`
> (the 19.33 bb/100 gap decomposes into a spread exploit-frequency deviation ≈10.7 + named concentrated leaks ≈8.6:
> BB-flop-over-fold 2.9, river-aggression 1.6, cbet-fold 1.3, river-value 1.0 …). **The active lever = `POKERB_GTO_MODE` (built this session, `pokerbot/strategy/gto_mode.py`, default
> OFF): flip exploit OFF + play GTOW's MEASURED tree** (the 12.5k-hand census `data/census/gtow_tree.json` →
> `research/gtow_tree_census.py`; sub-fixes S1–S5 in the plan: exploit-off, range-tracker fix, off-tree snap, river
> guards, resolver-on-census-tree). Hypothesis (the next $0 deterministic test): exploit-OFF lifts the HU GTO-score
> from 53% toward the 6-max 85% and shrinks the Freq-Diff. NOTE (measurement): engine GTOW runs are **effectively FREE**
> (in-process from the PC, `--agent-type pokerbot`, no pod); the "$10 budget" is a statistical-honesty constraint, not
> money. **Every "−47" reference below/elsewhere is STALE — read it as −20 raw / −8…−11 body.** Live detail + the S6
> GTOW-mode A/B (must be gated vs −20.09, not −47): `docs/STATE.md`. Also built: `pokerbot/vision/screen_reader.py`
> (universal VLM poker-table reader, any site).
> **The BRAIN track (Claude/GLM below) is a PROVEN, still-valid asset — but SECONDARY now**: it BYPASSES the engine's
> `bot.py` wins (drives `api.legalize` directly, [[brain-engine-two-products]]), and the engine-alone is the cheaper,
> faster, fully-ours bet the user picked. Keep the brain for research + the teacher-gold loop; the engine is the product.
>
> **★ CURRENT BRAIN (2026-06-19, SECONDARY now — see the 2026-07-04 block above) — CLAUDE OPUS 4.8 is the brain; Claude-ONLY first, Qwen is Step 2 (decide later).**
> Measured truth (GTOW leaderboard, read-only API): frontier LLMs with high reasoning play HUNL at ~−9 bb/100 AIVAT
> (GPT-5.2 −8.26, GPT-5.5 −9.23) — ~5× better than the STALE −47 engine aggregate (the CURRENT engine is −20 raw /
> −8…−11 body, see the 2026-07-04 block — the gap to the frontier is now small). So the brain is now a **frontier LLM prompted via program-of-thought**, NOT the (warm-start)
> Qwen-8B: `pokerbot/brain/claude_brain.py` `ClaudeBrain` → emits a DSL program calling `api.*` (exact math / equity /
> the live solver) → `executor.run_program` → an exact LEGAL action (gtow `--agent-type claude`; `research/llm.ask_claude`,
> thinking=adaptive = the leaderboard's "extra-high reasoning"). **Judgment by Claude, math + legality by the engine; we
> steer it in natural language → fast iteration.** ORDER: **Claude-only first DID prove the recipe** (−28.55 AIVAT —
> the teacher + proof); **Step 2 — our own RL-able AI — is NOW IN EXECUTION = GLM-Z1-9B (THUDM, MIT; not Qwen) SFT→RL**
> on a RunPod H100 SXM. Live status: `docs/STATE.md` (the SFT warm-start WORKS at 97.5% token-acc; the RL-lift is the
> open question). Honestly capped LOWER (9B ≪ Opus). Imitation-cap (still true): TRAINING a small model on our data ≤ our −47; PROMPTING a
> frontier model is NOT so capped (its own reasoning ~−9). Frontier API = PC-hub ONLY (never the pod). Honest ceiling:
> nobody beats GTOW (best −3.14) — a too-good number (e.g. a "+" vs GTOW) is an ARTIFACT to debug, never a win.
> **★ MEASURED (2026-06-21) — the GLM-Z1-9B brain (engine+brain) vs GTOW ≈ −17 bb/100 in the BODY (5%-trimmed, NEAR the leaderboard −3…−17) but a FAT TAIL of -EV postflop BETTING + coolers drags the RAW to −40/−68 (high variance; the anti-spew gate was REFUTED by a $0 counterfactual — STATE.md #3), via
> INFERENCE-WIRING fixes, NOT weights.** The arc: pure engine −47 → GLM-GRPO −43.30 → two SERVE-TIME wiring fixes (the
> `gtow_to_state` preflop `to_call` bug [inflated required_equity → over-fold] + the `format_spot` made-hand read [the GLM
> mis-read its own hand], both OOD, NO retraining) → a **body ~−17** (5%-trimmed, near the leaderboard; the RAW is −40/−68 = a fat tail of -EV betting/coolers; the once-cited −28.36 was a LUCKY low-tail session — raw swings −28↔−90 at n≤1500, all tail).** ★ **THE RL-LIFT QUESTION IS NOW
> ANSWERED (negatively, for this setup):** a re-SFT on made-hand-NATIVE gold + a fresh GRPO REGRESSED to −90.18 (postflop/
> river spew; the self-play sixmax league ≠ GTOW → RL learned league-beating aggression that loses to GTOW). The
> `gtow_glm_pod` A/B + the protected baseline = the "never ship a regression" gate. **THE LESSON: the wins are the WIRING
> (what the engine feeds the LLM at serve time), not the weights; baking a serve-hint into TRAINING backfires.** A
> separate cross-check found our solver/blueprint ORACLE is ~90% aligned with GTOW (NOT grossly broken) → the speculative
> postflop-solver overhaul (the old "PLAN #2") is NOT justified by the data. The baseline (`models/grpo_slim.tgz`, ≈ −40 robust,
> served `POKERB_MADE_HAND=1`+`POKERB_TOCALL_FIX=1`) is the PRODUCT. **NEXT (gated):** modest serve-time hints (the advisor
> bet-frequency, A/B'd OFF/ON default-OFF) for the one remaining real leak (postflop turn UNDER-betting); the deeper RL
> lever needs a BETTER REWARD (GTOW-anchored / stronger league), not more steps. Live detail: `docs/STATE.md`; harness
> `infra/gtow_glm_pod.py`. (The SIGALRM-in-worker-thread bug that first hid the GLM as frac_bad=1.0 is fixed in
> `executor._alarm_available`.)
>
> **Two-node system:** (1) **the PC (hub)** = the self-growing EV-gated dataset + a frontier-distillation loop
> (OpenAI/Claude → a HARD-CODED deterministic EV-TRUTH filter → dataset) + CPU mass-solving + the training monitor +
> scp-orchestration; (2) **RunPod** = Qwen SFT→GRPO (reward = 6-max self-play EV via `table.py` + the `sixmax`
> opponent league; GTO-anchored eval = PokerBench-acc + bb/100 + LBR-exploitability + robustness-spread). Frontier
> APIs feed ONLY the PC, never the pod; **the engine is TRUTH, the frontier a GATED PRIOR.**
>
> **CLEAN BOUNDARY (hard rule):** SFT/distillation = WARM-START only; the imitation ceiling is real (a HU policy net
> hit −212, a solver-imitation floor plateaued ~−72). **Only RL/self-play with realized-EV reward lifts above the
> teacher.** External assets (the 6 books, CFR/Pluribus/Supremus papers, PokerBench, Pluribus hands, frontier LLMs)
> seed / validate / distill-UNDER-GATE — never an ungated training label.

> **★★★★★ MILESTONE `v2` (git tag, 2026-07-05) — PRINCE v2.2 (SUPERSEDED by v3, block below) — PRECISION-MEASURED at
> AIVAT −19.70 ± 4.37 bb/100 vs GTO Wizard (n=2,393, pre-registered; ZERO catastrophes ≤−50bb, per-hand SD 214 =
> leaderboard-grade, body −6..−9).** This is the first bot the team versioned as a restore point (`git checkout v2`;
> commits `6bbf1c3`+`a49e244`). Config = `POKERB_PRINCE=1` (20-flag profile, `pokerbot/strategy/gto_mode.py`). The
> honest read: the DISTRIBUTION was transformed vs the old HEAD (tail eliminated, ± small) but the MEAN did not move
> (HEAD was −20.09 ± 7.18; the −11.61 was a lucky n=100 draw) — discipline bought SAFETY, not μ. The remaining loss
> is postflop (river −8.5 + flop −6.4, x-ray); mission = leaderboard #1 (beat −3.14), gap ≈ 16.5 bb/100 almost all
> river+flop. Instruments built this generation (all reusable, all $0): `research/stress_suite.py` (constructed-
> catastrophe gate), `research/replay_graded.py` (graded-hand regression gate), `research/freq_mine.py` (GTOW's
> revealed per-node frequencies from 13.5k hands = free teacher). NEXT = μ-levers on the river (Q6 anchors:
> `data/freq_targets/gtow_frequencies.json`), each gated stress→replay→canary→live. **The −20 in every block BELOW
> is the SAME engine measured; v2 is that engine with the deception+eCall+line-U+size-inject layer, tail-fixed.**
>
> **⟵ SUPERSEDED (2026-07-06): the shipped profile was REVERTED to PRINCE v2.2 — the validated −19.70/rank-#11
> anchor. v3 (PAIR/RIVER_DEFENSE) and every later lever (RAISE_NARROW/OVERBET_MENU/PURIFY/TURN_DEF_ADVISOR) are
> Analyzer-only and/or the v8 live-breakers (−58); by the user's 90%-confidence rule they are EXCLUDED from the
> final bot and demoted to default-OFF re-test arms. See STATE.md's top block. The v3 record below is history.**
> **★★★★★ PRINCE v3 SHIPPED + THE LEVER PIPELINE + THE INFRASTRUCTURE LEAP (2026-07-05 evening).** The shipped
> bot is now **PRINCE v3** (commit 85d2919): the v2.2 profile + PAIR_DEFENSE 0.10 + RIVER_DEFENSE 0.06 — gated by
> the agreed v3-test-protocol (**paired Analyzer 17.93 vs v2.2's 20.66 on identical seed-55 deals** = the decisive
> $0 gate; tail-smoke 0 catastrophes, worst −19.3bb). v3.1 (flat thin-floor) was Analyzer-REFUTED (19.76) = the
> THIRD measured proof that **frequency-matching without the teacher's SELECTION loses**. IN THE PIPELINE (built,
> all gates green, default-OFF, ONE Analyzer arm each): **v3.2** RIVER_THIN_SEL (selection-aware thin value via
> eCall), **v3.3** RAISE_NARROW (raise-facing-bet range narrowing toward the MINED GTOW raise mix —
> `research/raise_mine.py`, 488 raises: jams ~62% nutted, flop raises 53% air), **v3.4** AUDIT_FIX (9 finds of the
> 90-agent audit: PAIR_DEFENSE fired on check-raises, TURN_DEFENSE cancelled BARREL_DISCIPLINE, vacuous river
> bluffcatcher gate, covered-stack pot odds, threshold floor, phantom sizer arms, raise=aggro), **v3.5**
> ADVISOR_ROLE_POS (advisors were queried by INITIATIVE but trained by POSITION → inverted in 3bet pots).
> **MEASUREMENT-SEAM FIXES (live now):** the live blinds order [BB,SB] was unpacked as [SB,BB] → EVERY live AIVAT
> run carried a baked-in preflop over-fold (+7pp required equity BB-vs-open; exports unaffected); the config
> fingerprint missed 13 flags; export all-in run-outs lacked HH board sections (**future pairings need FRESH
> anchors**). **INFRASTRUCTURE: decide() is 12.1× faster** (999→83ms, proven-pure memoization, commit 114e107) and
> the instruments are now TRULY process-deterministic (set-iteration/PYTHONHASHSEED root fix in
> `ranges.combos_for_classes` — every prior "deterministic" run carried boundary-spot jitter). Clean-code
> discipline = standing rule (memory `clean-code-discipline`; the byte-identity harness is THE refactor gate).
> **THE v4 PATH (post-lever-ladder, decided):** real-time depth-limited CFR + neural leaves per Li&Huang
> (`books/papers/CFR/2605.19928v1.pdf`) + EVPA (ICLR25, read: ensemble pruning needs the nets; the geometric
> transfer measured NO-OP vs TexasSolver — it prunes internally) + TurboReBeL (leaf training) — ladder ≈ −10
> asymptote, v4 = the way below −8. Research ledger: `docs/reports/RESEARCH_SWEEP_2026-07-05.md` (27/36 papers
> existence-verified; Perplexity scrambles metadata — NEVER cite unverified). Codebase MCP: Serena (`.mcp.json`,
> LSP symbol navigation, active from the next session). Analyzer sequencing: v3.2 → v3.3 → v3.4 → v3.5, one arm
> per user upload, fresh anchors from the fixed exporter.
>
> **★ FUTURE BUILD CANDIDATE (user-flagged 2026-07-07, deferred) — the VALUE-OF-COMPUTATION ARBITER**
> ([`docs/consults/SURFING_CONSULT.md`](docs/consults/SURFING_CONSULT.md), memory [[value-of-computation-arbiter]]). From extracting
> Andy Clark's *Surfing Uncertainty* (predictive processing) + a GPT-5.5 math/CS translation: PP is mostly an
> elegant re-description of RL/solver methods (NO new poker objective — poker stays chip-EV, not prediction-error
> min), BUT 3 concepts converge on ONE buildable high-leverage lever = **precision-weighted value-of-computation
> control**: spend resolver/CFR budget ONLY where the fast cached policy is likely wrong or the top-2 EV gap is
> small AND the pot is large. Build: a calibrated **ΔEV = EV(resolved) − EV(fast)** quantile regressor over cheap
> features (advisor policy+entropy, range-confidence, pot/SPR, top-2 margin, cache age, board texture, opponent
> line-surprise) → invoke the resolver iff `E[ΔEV] − λ·solve_ms > threshold` (+ river-all-in triggers). This is the
> IMPLEMENTABLE core of the v4 path (it decides WHERE the real-time CFR runs) and attacks the −20 postflop leak
> directly; aligns with `docs/doctrine/PRECISION_DOCTRINE.md`. The transferable book-insight: the brain rivals machines at
> poker via metareasoning EFFICIENCY (optimal scarce-compute allocation), not raw compute or a better objective.
>
> **★★★★★ 2026-08-04 — THREE NEW PILLARS (detail: STATE.md): SNOWIE BRIDGE, TOURNAMENT MODE, MULTIWAY.**
> **(1) PokerSnowie bridge production-ready** (`pokerbot/vision/snowie_*`): plays PokerSnowie 4 fully automatically
> (13.3 hands/min, ~4% dropouts, both themes). Hardening doctrine derived from it: NEVER compute with wrong numbers
> (gate → escalation only with clean core fields → honest exclusion), chip conservation as a gate,
> mandatory second source for the pot, click/action verification, 5-case regression net (`research/
> snowie_regress.py`) + marathon watchdog. **Measurement (3 runs, 3,651 hands): account −$2,915, but the CLEANED
> pool (3,114 clean hands) = +3.2 bb/100 [−37,+44] — the bot was ≈ break-even vs Snowie, the automation
> tax ate the account** (every class autopsied individually + sealed). Prince-HU in the bridge ONLY postflop
> (user objection correct: MP open ≈ 15–20% range, the HU projection would read ~50%); 6-max POSITION PRIOR for the
> opponent range + Bayes correction over observed actions (`make_seeded_tracker`/`ActionLog`).
> **(2) TOURNAMENT MODE BUILT + VALIDATED** (Sklansky + endgame/ICM systematically extracted →
> `knowledge_base/tournament/DOKTRIN.md`): exact Malmuth-Harville (`strategy/icm.py`, tested against an independent
> enumeration), doctrine layer (`strategy/tournament.py`: BF scaling of the call side ONLY =
> gap doctrine; **proportional risk premium** BF_eff = 1+(BF−1)·(to_call/stack) — the full BF was REFUTED by the
> paired experiment (−8pp, bubble bleed-out), the proportional one VALIDATED: **μ-3 n=1500 paired:
> +10.0 ± 5.0 pp ROI, 95% band [+0.2, +19.9], MORE wins AND a better ladder**), director (levels/antes/
> elimination/shrinkage), arena with paired seeds (`arena/tourney.py`). HU = BF 1 → Prince v2.2 plays
> tournament endgames UNTOUCHED. Pressure lever (doctrine 9, `icm_pressure_mult`): the covering stack harvests the
> forced tightness of ICM-playing opponents — the PS-$1050 survey documents this tightening empirically
> (FoldVsRaise 54→62%, jam 1.1→13.1%; `research/ps_tourney_field.py` + `ps_tourney_duel.py`).
> **(3) MULTIWAY 7–10**: engine labels up to 10-max, sixmax buckets ONLY for new labels (6-max byte-identical =
> anchor protection), trainer `?players=9`. AIVAT vs Snowie: not fully possible (no showdown logging); ladder defined
> (showdown logger → all-in luck adjustment → MIVAT-light).
>
> **★★★★ HISTORY (2026-07-04) — `docs/archive/PRINCE_START_HERE_2026-07.md` is NO LONGER the entry point.** The root marker names
> "PRINCE v3" as shipped; that is outdated (revert to v2.2, then the AUSLESE chain up to v5). **No longer
> to be used as the situation picture** — that is what [`docs/STATE.md`](docs/STATE.md) is for. Two things from it
> remain permanently valid: the doctrine **only bb count** (frequency matching against GTOW cost EV, measured 3x) and the
> opponent dossier [`docs/reports/GTOW_DOSSIER.md`](docs/reports/GTOW_DOSSIER.md) (GTOW = ruse re-solver; sizing and
> translation attacks refuted, 13.5k hands, $0).
>
> **New Claude session? Start with [`docs/STATE.md`](docs/STATE.md)** — the LIVE source of truth.
> Building blocks = [`docs/catalogs/MODULE_CATALOG.md`](docs/catalogs/MODULE_CATALOG.md) · numbers = [`docs/catalogs/MEASUREMENT_CATALOG.md`](docs/catalogs/MEASUREMENT_CATALOG.md)
> · repo tree = [`docs/INDEX.md`](docs/INDEX.md). This file = stable conventions + the north star; `STATE.md` = now.
>
> **★ YOU WANT TO BUILD A NEW BOT VERSION FROM SCRATCH? → [`docs/catalogs/MODULE_CATALOG.md`](docs/catalogs/MODULE_CATALOG.md)**
> (2026-09-10). Every building block of this project described INDIVIDUALLY — purpose, interface with signature,
> input/output format, dependencies (hard or replaceable), state, cost, **measurement status** and the one
> pitfall. Meant for someone who does NOT know the bot and wants to decide per module: take it or build it
> yourself. **REFUTED building blocks are explicitly included** — what we have measurably disproved is the most
> valuable information for a rebuild. Alongside it belongs [`docs/catalogs/MEASUREMENT_CATALOG.md`](docs/catalogs/MEASUREMENT_CATALOG.md): what was
> ACTUALLY measured on each part, with source, verdict and the question whether the number still holds today.
> The module catalog says what a part DOES; the measurement catalog says whether it WORKS. Candidates never
> measured at the anchor, with their pre-registered expectations: [`docs/catalogs/CANDIDATES.md`](docs/catalogs/CANDIDATES.md).
>
> **⟳ KEEP STATE.md CURRENT — standing rule.** After any turn that moves a headline number (a measurement), lands a
> build, or shifts priorities, UPDATE STATE.md's top CURRENT section *before ending the turn* — lead with the current
> frontier, demote superseded numbers to a one-line "history" pointer. A fresh context must start from the truth.
>
> **Deferred-precision / open questions:** [`docs/NOTES.md`](docs/NOTES.md) — approximations we ship now + should compute
> exactly later. Add an entry when you ship a heuristic.
>
> **★ FORWARD PLAN — how to improve the bot + the personal coaching path:** [`docs/plans/ROADMAP.md`](docs/plans/ROADMAP.md). Two
> tracks. **(A) Make the bot UNDERSTAND poker as well as possible** — the live lever is the consolidated
> **understanding layer** (`pokerbot/brain/understanding.py::strategic_read` = SPR/position/pot-odds/MDF + board
> texture + the made-hand read + the MEASURED GTO heuristics fused into ONE engine-computed frame, gated
> `POKERB_UNDERSTANDING`, default OFF), so the brain reasons from first principles even on the ~60–85% of spots the
> solver never covers; next = measure it (deterministic GTOW per-decision first), the river over-size fix, render the
> solver's preferred SIZE. **(B) A Claude-API COACHING path for a human player** — review a player's own
> hand histories, engine-grounded (`api.*` + the understanding layer) + GTO-anchored, personalized to their
> tracked leaks; most machinery exists (`pokerbot/coach/coach.py` + `research/study_grade.py`). Honest: the
> understanding layer is BUILT but EV-UNMEASURED; the coaching path is PROPOSED. Details + the reuse map in docs/plans/ROADMAP.md.

## Working discipline — Fable-5 verified mode (embedded from `github.com/fivetaku/fablize`)
How to work on THIS project. Transfers PROCEDURE, not capability — *make the work reach its own ceiling, don't fake it.*
- **Verification grounding:** run + observe the artifact — a measured run, a paired/duplicate A/B, exact
  exploitability, a `test_*`, a UI via TestClient — BEFORE any "done". A claim without its cited evidence is not done.
- **Multi-story gate:** decompose; refuse a groundless "done". Per objective, state truly-evidenced vs merely-declared.
- **Investigation protocol:** for any loss/failure, reproduce it, COMPETE the hypotheses, trace the COMPLETE causal
  chain — never stop at the first plausible cause.
- **No promising-without-doing:** "I'll do X" / "should help" are NOT results. Hard-separate DONE+measured from planned/hoped.
- **Grounded gate (hard-won):** only a GROUNDED signal (solver-gap / AIVAT / exact exploitability / a deterministic
  check) gates a change. Single-rule raw-bb/100 A/B is too noisy (plausible fixes were REVERTED after measurement);
  small samples lie (n≤150 AIVAT lied as −13 vs the real −72). Paired/duplicate eval cancels card luck.

## Style & communication standard (DEFAULT — `books/papers` / `aiStyle.pdf`, Stanford *Art of Elegant Coding*)
How I write code AND talk about it — the standing default, every turn.
- **Elegant code — 4 pillars.** (1) **Names** meaningful + accurate; a name must NEVER mislead about the type/content
  it holds (`weight_str` holding a float is a leak). Descriptive, not over-verbose. (2) **Constants, not magic numbers**
  — name them (UPPERCASE module-level) so intent + tunability are explicit (matches our `# a prior; RL tunes` idiom).
  (3) **Comments** explain the WHY + the non-obvious (why `0.378`), never restate the code; one honest line beats three
  hollow ones. (4) **Decomposition** — small single-purpose functions; split a function >~15 lines; extract a repeated
  >~4-line block into a helper.
- **Communication — be TIMELY, SPECIFIC, HONEST, CONSISTENT.** TIMELY: surface issues inline as I work, not deferred.
  SPECIFIC: exact `file:line` + a concrete alternative + a one-line WHY. **HONEST: NO hollow praise / hallucinated
  approval** — never call code good when it isn't, never claim a comment/test/result that isn't there (the paper's #1
  LLM failure mode; this IS the Verification-grounding gate restated). CONSISTENT: uniform format; write code that reads
  like the surrounding code (match its naming, comment density, idiom).

> **★★★★★ ACTIVE PLAN (2026-08-16) — AUTOGYM: the self-checking training loop. GOAL = approach the
> GTOW BASELINE** (reference −19.70 ± 4.37; staircase −15 → −10 → leaderboard band, each step measured vs GTOW,
> $0 in-process). Built: `pokerbot/autogym/` — `oracle.py` (the UNIFIED math benchmark:
> the 78 formula functions from `knowledge_base/math/` are wired step by step into verdicts over real
> self-play decisions; tiers HART/P/L/F), `gym_hu.py` + `gym_six.py` (separate self-play gyms
> with bookkeeping; HU on paired decks with button swap → pair drift as a symmetry check, button net as
> card-adjusted position value), `improver.py` (mine → patch → paired A/B gate → journal),
> `selftest.py` (the local proof E1–E4). **Safety contract (binding): formulas immutable +
> Fraction reference mandatory; oracle knobs = measurement config, LOCKED for the improver (Goodhart); bot knobs
> tunable within bounds, applied ONLY through the gate; P patches as wrappers, never source code; everything into the journal.**
> Doctrine: PRE-REGISTERED expectations everywhere; the loop must be proven LOCALLY (expectation ladder
> E1–E6, `docs/plans/AUTOGYM_PLAN.md`), only then the pod (CPU cores, no GPU — CFR/self-play computation).
> First pilot: 500 hands + 3,577 graded decisions in 52 s locally; HART 0, P 0, L 35, F 3.
> **★ RESULT AFTER 2 DAYS (2026-08-17): THE LOOP WORKS. Version chain basis → AUSLESE v1
> (+6.1±1.5, replicated 2x99k) → AUSLESE v3 (~+9 cumulative; 15pp margin; 3 direct runs pooled +3.9±0.95
> vs v1 + 183k anchor +8.68±1.28 vs basis) → AUSLESE v4 (tag auslese-v4, night of 2026-08-17: the BET side —
> turn_wert_guard [trips+/overpair + eq>=0.60 → 2/3-pot turn bet; the oldest leak, replicated 3x in the mirror
> +7.27±2.33] + TURN_DEFENSE 0.07 + SLOWPLAY 0.25 + RAISE_NARROW 1.0 [ONLY resolver-OFF]; final on
> identical decks vs basis: v3 +21.4 → v4 +49.8, paired step +28.4±6.2, envgate channel; new instruments:
> envgate/orakel_duell/W1-4+W1-5; estimator v2 = raw mean + sign test, the trim was blind for
> thin channels; A/A null test exactly 0 after spot-RNG seeding).**
> **★ ROUND 5/6 ADDENDUM (early 2026-08-18): v4 core in the MIRROR vs basis = +16.14±2.77 (3x30k, CI[+10.7,+21.6],
> p=0.0002) — exactly in the pre-registered band. NEW INSTRUMENT: the Fable LLM adversary (`research/fable_duell.py`,
> file-based, replay-deterministic): 62 hands vs v4 = +115bb with COUNTED patterns (river station,
> button open-fold 29%, check-raise without follow-through, capped check range = the v8 Purify mechanism observed LIVE
> on v4). MEASURED TWO-AXIS DOCTRINE (binding): hardening guards against ADAPTIVE opponents are
> invisible to negative in the mirror (r6_ecall REJECT −4.15 = value folds in the self-play ecology; r6_button
> NEUTRAL despite exploit prevention) → mirror = NON-REGRESSION bound, adversary (Fable retest/
> exploit_jagd) = proof of effect. Bug harvest of the agent armies (all data/runs/*_2026-08-17.json): OpenBLAS caps in
> all workers (proven cause of hangs), W1-3 bet filter+R fix, _wickle = ONE stack source (export parity),
> flop resolver built but first flight 0/3 (latency 75-121s + hand-not-in-range of the 35-class hero range —
> tier-2 construction site). GTOW HONESTY: live anchor ~−25..−30 (the −19.70 was inflated by the blinds bug);
> gtowizard.py needs the v4 ADAPTER (wrapper missing in the harness, resolver default ON = RAISE_NARROW trap)
> BEFORE an anchor runs. QUEUE: Fable retest vs hardened stack, follow-through/seesaw-mixing guards
> (stateful), princegate, pargate6, GTOW adapter (specs ready in data/runs/).**
> **★ GTOW FIRST CONTACT v4 (night of 2026-08-18, RUNNING — live status in STATE.md!): final bot wired
> (pokerbot/strategy/auslese.py = ONE source: FINAL_STACK — THEN r6_button, TODAY `r8_stack`
> (auslese.py:34; release candidate RC_STACK = r10_stack) + AUSLESE_ENV; HU app/six_server/
> gtowizard adapter, all smoke-green; final stack vs basis mirror +23.36±5.32 APPLY). GTOW batch
> key #3: smokes 20/100 mechanically error-free (2 bugs found+fixed: 409 orphans→clear_inprogress mandatory
> before every start; dict+str in wickle_decide), but AIVAT pooled ~−53±12 = RED FLAG (v8 pattern; suspicion:
> Fable finding live — capped check range vs re-solver). Night run 4x500 with pre-registered checkpoint
> (v4 pool ≤ −45 after chunk 1 → control arm PRINCE-resolver-ON). Hand histories of all runs:
> data/sessions/gtow_hands_*.jsonl + gtow_manifest_2026-08-18.json. Result: journal GTOW-NACHT-*.
> NIGHT-1 FINDING (~04:10): gym config bare = −38.86 (n=1617, recovered from HH files after the cp1252
> driver bug — every hand carries `aivat`, recovery validated exactly); 81% of the loss on the RIVER in the old
> jam-spew/station pattern = the arm lacked resolver + GTO discipline, NO v4 verdict. NIGHT 2 (running):
> the real final bot (AUSLESE chain + PRINCE + resolver-ON, without RN) with a control chunk as A/B —
> journal GTOW-NACHT2-*. LESSONS (binding): subprocess ALWAYS encoding="utf-8" (cp1252 trap);
> HH logging is the insurance of every run; live arms need the live foundation (the gym config
> does NOT transplant bare).** Core doctrine MEASURED (3x + Brown 2026 theory): SELECTION
> beats frequency/adaptation — which hands, never how often. Rejected (replication mandatory!): v2/sel_all,
> einmal_guard, mdf/podds/lizenz_guard. Measurement lessons (binding): no name without 3 runs (2x premature
> naming prevented); per-deck edges are FAT-TAILED → 2SE intervals too optimistic (robust SE = open
> item); quiet channel (candidate vs candidate) >> loud (vs basis); measure the channel BEFORE the build (AP8);
> unseeded MC breaks pairings; one worker fleet at a time (RAM). Tools: pargate (--incumbent,
> thread pin, ETA), exploit_jagd (20 persistent hunters; hardening map VPIP 0.76/FtB 0.30/Agg 0.32),
> snowie_export (gate parity!), verify_refs (66/66), advisor batch (2.2x), runde4 campaign pattern,
> data/runs/+STAND.md. 6-max catalog v0 (30k hands): flop overfold is HU-SPECIFIC (6max folds 0.216
> where 0.30 is allowed). Papers anchored: Brown (27 bluffs structural, band 0.36-0.50) + SPIRAL-RAE
> (reward design for future RL). Detail: docs/plans/AUTOGYM_PLAN.md + docs/catalogs/EXPLOIT_CATALOG.md + journal.
> **VERSIONING RULE (user, 2026-08-16, binding): BEFORE every bot change the state is
> frozen (git tag; current basis = tag `autogym-basis`); a changed bot receives a NAME at the END
> and is versioned as a tag. MEASUREMENT DOCTRINE: do NOT measure vs GTOW — the three instruments are
> (1) the math benchmark (oracle), (2) self-play gates (paired decks), (3) the paired
> A/B anchor NEW BOT vs OLD BASIS (`duplicate_ab` on identical decks). GTOW only as a last resort.**

> **★★★★★ v10 "RIVER FOUNDATION" (2026-09-07/08) — BUILT, GATED, NOT GTOW-READY; CHAMPION REMAINS auslese-v5.**
> **Re-entry in 4 files:** `docs/reports/V10_GATES_REPORT.md` (gate table + addendum 6 = ship decision),
> `docs/plans/V10_BUILD_CARD.md` (card + decisions E1–E11 + addendum), `docs/reports/V10_FACTS.md` (code facts with
> file:line), `docs/consults/TOP5_CONSULT_GPT6_2026-09-07.md` (gpt-6-astra consult parts A–G: top-5 strategy, net
> architecture R1/R2/R3, v10 critique, completeness, hybrid doctrine). Journal types V10-*/KONSULT-GPT6-*.
> **What exists (branch poker-core):** K1 `pokerbot/strategy/hero_range.py` (hero-likelihood replay), K2
> `pokerbot/autogym/river_plan.py` (public river plan, private randomization, trace), K3
> `research/{policy_oracle,river_br_pruefstand,k3_roots}.py` (exact BR against a fixed hero policy, batched
> arm-A oracle), K4 `pokerbot/runtime_config.py` + `pokerbot/benchmark/gtow_ledger.py` (fingerprint, misconfig
> gate, ledger; HU app D1 fixed), K5 `research/gtow_nacht_v10.py` (coin BAAB then ABBA), contracts
> `pokerbot/strategy/contracts.py`, `research/golden_set.py`, stack `r10_stack` in pargate, `auslese.RC_STACK`.
> **Measurement status:** A/A 576 decks EXACTLY 0 (3 banks; bug hand_id-per-half found+fixed), G5 mirror r10 vs v5
> +11.7 ± 10.9 (1968 decks, gym channel), G4 plan less exploitable in 11/11 holdout roots (gym arm, n=11),
> **G3 MISSED** (K1-TV 0.21 vs 0.02; hero outside K1 support 21/64), G2 live: plan 25/40, offtree 11/40.
> **Catastrophe source = off-tree fallback onto the BARE basis without the v5 surgery** (all gym decks ≤ −100 bb).
> **NEXT BUILD v10.1 = closed hybrid (Astra part G, steps 1–6):** H0 = plan, otherwise
> UNCHANGED productive v5 per decision (including sub-threshold escalation) → H1 = plan + range-consistent
> continuation from the ACTUALLY executed hybrid policy (`v5_continuation`); K1 prior from the played
> preflop policy (support exactly 0 violations, NO epsilon for the real hand); state machine (no
> silent re-entry into an old plan; never execute stale thread results); forced seam tests instead of
> random decks; test bench with the executed HYBRID POLICY against PRODUCTIVE v5 (H0 vs bare, H1 vs H0,
> H1 vs P); then shadow night (v5 acts, v10 computes alongside = at the same time the missing v5 GTOW anchor).
> **HYBRID DOCTRINE (binding, 7 rules):** (1) the executed overall policy is evaluated, never components;
> (2) public gating is the standard, hand-dependent selection only as a fully modeled strategy;
> (3) ranges follow the actually executed action probabilities, private cards repair no
> public range; (4) every switch has a closed continuation; (5) no invisible degraded
> fallback; (6) compare EVs only with the same meaning (no max over solver EVs of different games);
> (7) release checks seams and selection, not only the parents. **MEASUREMENT LESSONS:** oracles batched over solver
> guards (injection = one solve per combo, 0.2 s); live K2 ≥3 solve threads/3 s queue/12 s deadline; a 40-deck A/A
> is not enough for K2 (576); pargate bank fresh per code state (1080000–1110000 used up); agent runs >10 min
> only with extrapolation + stdout progress. **Fable as live orchestrator:** shadow diagnosis only on
> logged states; proof only with the engine (SE ≈ 214/√n bb/100; ±4 band ≈ 11k hands).

## ★ FALLBACK PROTOCOL (2026-08-18) — BINDING for EVERY model below Fable 5 (e.g. Opus 5)
If you are not Fable 5: work DEFENSIVELY by these rules. The project is precisely measured —
a well-meant intervention without a gate destroys more than it helps.
**1. ENTRY (always in this order):** read the top CURRENT block of docs/STATE.md → BEFORE every number
docs/catalogs/MEASUREMENT_CATALOG.md (channel + validity; the variance coefficient is c=294, NOT 214) → BEFORE every new build
docs/catalogs/MODULE_CATALOG.md + docs/catalogs/CANDIDATES.md (the chance is high that it already exists or is refuted) → data/runs/STAND.md
→ for GTOW questions the journal: `python -c "import json; [print(l.strip()) for l in open('data/autogym/journal.jsonl', encoding='utf-8').readlines()[-30:]]"`.
**2. SAFE STANDARD ACTIONS (allowed without asking):** read and CITE journal/result.json/STAND;
execute ready-made commands FROM THE DOCS verbatim (pargate/envgate/orakel_duell/gtow_nacht — patterns are
in STATE.md and the module docstrings); before every GTOW start `clear_inprogress.py` (409 orphans); report results
WITH source (file+line). Any number without a source is forbidden — NEVER numbers from memory.
**3. NO-GO ZONES (only with an explicit user mandate AND through the gate):** knowledge_base/math/* (formulas
immutable), oracle thresholds/knobs in oracle.py (measurement config, Goodhart lock), pokerbot/strategy/*
(strategy code — changes ONLY as guard wrappers + paired gate), frozen tags (autogym-basis,
auslese-v1..v4, v2), running background jobs (never kill without diagnosis), git history (no rebase/reset).
**4. MEASUREMENT DISCIPLINE (non-negotiable):** BEFORE every measurement series an A/A null test (candidate==incumbent must
be EXACTLY 0 — otherwise STOP and report the finding, do not repair); one worker fleet at a time; mp drivers
never as a heredoc (use `python -m` modules); verdicts only via stats.verdikt (bootstrap for thin channels);
3-runs rule before every naming; envgate results are called KANAL_* and are NEVER ship evidence.
**5. ESCALATION:** On inconsistent numbers, a broken A/A, unclear diffs in the working tree or ANY
suspicion of a second session (memory: one-session-per-repo): STOP, report the finding with sources to the user,
fix NOTHING on your own. An honest "I don't know, here is the state" is always right;
a plausible invention is always wrong.
**6. WHAT YOU SHOULD NOT DO, EVEN IF IT SEEMS OBVIOUS:** large refactors, "cleaning up" code you
have not measured, agent armies without a clear mandate, GTOW runs beyond the documented batch
(hand budget!), changing CLAUDE.md doctrine blocks. When in doubt: read, report, ask.

## Boundary — what does NOT belong in this repo (standing rule, 2026-08-16)
The core is **poker bot, poker trainer, poker understanding** — nothing else. Everything else (personal
files, relationship/chat analyses, geopolitics, number theory, reports about real persons) belongs
**outside this repository**, in its own folders next to `PokerB` — not in a subfolder.
Until 2026-09-10 the gitignored root folder `#Anderes/` existed for this; it is **deleted**, its content
pulled out. A local `pre-commit` hook continues to block the old paths, even against `git add -f`.
The repo anchors exclusively **poker bot + poker trainer**.
If a genuine poker finding falls out of such work, it moves DEPERSONALIZED into the core
(as happened: the 66-bb/100 flattening in `docs/doctrine/POKER_NUTSHELL.md`, the entropy bias in `docs/NOTES.md`) —
the raw data and the person stay outside.

## Run / play
- **6-max vs 5 bots (the app):** `python -m pokerbot.web.six_server --open` → http://127.0.0.1:8000 (launcher
  `PokerB 6max spielen.bat`). Logs each hand to `data/sessions/`; "Analyse" = end-of-session breakdown.
  Multiway: `http://127.0.0.1:8000?players=9` (2–10 seats). Tournament arena (sim): `python -m pokerbot.arena.tourney`.
- **Play PokerSnowie automatically:** open PokerSnowie 4 (cash table) → `python -m pokerbot.vision.snowie_bridge
  --hands 20 --loose`; long runs via `python -m research.snowie_marathon --hands 2000` (ESC ends EVERYTHING).
- HU app (background/validation only now): `python -m pokerbot.web.server --open`.
- Always run from the project root as `python -m <module>`. Windows / PowerShell, Python 3.12. `pip install -r requirements.txt`.

## Architecture (logical; module by module = [`docs/catalogs/MODULE_CATALOG.md`](docs/catalogs/MODULE_CATALOG.md))
- `pokerbot/engine/` — cards, treys evaluator, MC equity (`equity.py`), the **N-player `table.py` = the 6-max RL
  ENVIRONMENT** (start_hand / legal_actions / act / obs_for / result, side pots), HU `game.py`.
- `pokerbot/strategy/` — the engine PRIMITIVES the brain calls: `preflop_blueprint.py`, `range_tracker.py`,
  `advisor.py` (solver-frequency MLPs), `opp_model.py` (Dirichlet exploit), `postflop.py` (sizing/texture), `bot.py`.
- `pokerbot/brain/` — **the LLM-brain interface (NEW):** `api.py` (typed engine-API = the DSL vocabulary),
  `format_spot.py` (canonical 6-max spot, PokerBench-aligned), `executor.py` (program-of-thought sandbox),
  `understanding.py` (**the consolidated strategic read** — SPR/position/pot-odds/MDF + texture + made-hand +
  measured GTO heuristics in one engine-computed frame, gated `POKERB_UNDERSTANDING`; lets the brain reason on
  UNSOLVED spots), `claude_brain.py` (Claude-as-brain), `policy.py` (the shared SYSTEM_PROMPT + DSL).
- `pokerbot/arena/` — `sixmax.py` (the opponent LEAGUE: TAG/LAG/nit/station/maniac profiles).
- `pokerbot/{web,benchmark,coach,analysis}/` — apps; benchmarks (`slumbot.py`, `gtowizard.py`, `lbr.py`,
  `duplicate.py`); coaching; session analysis. Trainer multiway: `six_server` + `six.html` up to 10-max (`?players=9`).
- `pokerbot/vision/` — **the PokerSnowie bridge (NEW 2026-08-04):** `snowie_local.py` (cards/glyphs,
  template matching with margin rule), `snowie_state.py` (complete table state, second-source pot,
  gate chain), `snowie_bridge.py` (game loop, Prince-HU postflop, ActionLog, watchdog). Regression net
  `research/snowie_regress.py` (preserved crime scenes), marathon `research/snowie_marathon.py`.
- **Tournament (NEW 2026-08-04):** `pokerbot/strategy/icm.py` (exact Malmuth-Harville + bubble_factor +
  icm_call_threshold), `pokerbot/strategy/tournament.py` (Structure/Director/proportional risk premium/
  pressure lever), `pokerbot/arena/tourney.py` (paired SNG arena). Doctrine: `knowledge_base/tournament/DOKTRIN.md`.
- `dataset/` — **the GOLD (NEW):** `build/` (KB→DSL JSONL converters) + the self-growing dataset shards + **`registry.py`**
  = the single source of truth for ALL data (every asset's role/schema/provenance; the training pipeline reads gold by
  ROLE via `registry.sft_gold()`) → **[`docs/catalogs/DATA_CATALOG.md`](docs/catalogs/DATA_CATALOG.md)** the generated data map (`python -m dataset.build_manifest`).
- `training/` — **Qwen (NEW):** `qwen_sft.py` (SFT, Qwen3-8B QLoRA on the DSL data), `qwen_grpo.py` (RL self-play),
  `qwen_eval.py` (PokerBench-acc + bb/100 + LBR).
- `pipeline/` — **the PC-hub program (NEW):** `frontier_loop.py` (gated active distillation), `filter.py` (the
  deterministic EV-truth/relevance filter), `monitor.py`, `orchestrate.py` (scp to/from the pod).
- `research/` — the one-off mining/consult/solve scripts (the historical `extraction/`; reusable: `llm.py` = the
  OpenAI/Claude call helpers, `mass_solve.py`, `preflop_*`, `cfv_*`).
- `infra/` — `runpod_run.py` (pod lifecycle) + the pod campaign/setup.
- `knowledge_base/` — extracted theory = the dataset's SOURCE: `math/` (Mathematics of Poker → `formulas.py`),
  `concepts/`, `theory/` (CFR/Pluribus/Supremus/AGT), `exploit/` (11.5k directives), `ranges/`, `postflop/`,
  `hand_histories/` (10k Pluribus). **Hard-referenced by `config.py` + strategy — do not move without updating both.**
- `books/` — the 6 poker books (`poker/`: Mathematics of Poker, Beyond GTO, Exploitative Poker, Modern Poker Theory,
  NLHE Theory & Practice, Theory of Poker) + `papers/` (CFR, Pluribus, Supremus, the PokerBench-LLM + Nash-robustness PDFs).
- `docs/` (`STATE.md` entry point + `docs/plans/ROADMAP.md` forward plan + plans/consults) · `tests/` · `data/` (gitignored) · `models/` (`qwen_poker_ckpt500`) · `tools/` (TexasSolver + GTOW client).

## The common language (DSL) — see [`docs/doctrine/DATASET_SPEC.md`](docs/doctrine/DATASET_SPEC.md)
Math (`knowledge_base/math/formulas.py`) ↔ Code (the `brain/api.py` engine-API) ↔ Language (concepts/prompt). A
training example = a canonical spot → a **decision-program** (Python calling the API + brief NL) → the executed action.
Same `format_spot()` byte-identical across SFT / RL / inference / eval. Qwen-native (code), exact (math by code),
verifiable (run it → exact RL reward).

## Config / keys
- `pokerbot/config.py`: paths, models, API keys read from `C:\Users\hampe\Desktop\Secret keys\` (Claude+OpenAI under
  `AI\`, RunPod) with env-var override — **never hardcode keys**. The OpenAI/Claude call helpers live in
  `research/llm.py` (`ask_openai`/`ask_claude`/`claude_json`/`openai_json`).
- Models: Claude `claude-opus-4-8`; OpenAI auto-resolves (`OPENAI_MODEL_PREFERENCE`, gpt-5.1/gpt-5.5/o3). Base LLM = **Qwen3-8B**.

## Conventions / gotchas
- Cards are 2-char strings (`'As'`, `'Td'`) — treys-compatible. `bb = 100` chips; UIs show bb.
- `six_server.index()` reads `six.html` fresh per request; other servers cache HTML at import → restart for UI edits.
- A backgrounded server killed via TaskStop can hold its port: `Get-NetTCPConnection -LocalPort <p>` → `Stop-Process -Id <pid> -Force`.
- Verify UIs via `fastapi.testclient.TestClient`, not the (hanging) screenshot tool.

## Heavy compute / pod (RunPod)
- `infra/runpod_run.py` provisions/kills a GPU pod. **ALWAYS `--kill` when done** (`DELETE /pods/{id}` = full
  terminate; a "stop" still bills storage). Verify `--status` = no tracked pods.
- **Prefer H100/H200 for Qwen.** B200 = Blackwell sm_100: training kernels are immature (torch SDPA math-fallback,
  ~10× slower observed) → only with `pip install -U torch --index-url …/cu128` AND verified `+cu128` throughput.
- **CPU and GPU heavy jobs do NOT coexist on one box** (mass-solve starves the GPU trainer + saturates sshd). The
  GPU job runs on the pod, the CPU mass-solve LOCALLY (the 2-node split). SSH key `C:\Users\hampe\.ssh\pokerb_runpod`.
- Data moves PC↔pod via a single **scp tarball** (`pokerbot/`+`research/`+`dataset/`) + scp results back; the campaign
  pattern is self-killing (`atexit`+`finally`).

## History (superseded — context only; the live state is STATE.md)
The project was a HU exploit-primary engine measured **−72 bb/100 vs GTO Wizard** (87% preflop; AIVAT n=2498); the
solver-imitation floor + the fcpa policy net (−212) showed the imitation ceiling; a near-Nash preflop blueprint +
range-tracker keystone + a solver-grafted-preflop pass were built (grounded but flat in bb/100 vs near-GTO). Those
are now **background/validation** — the goal pivoted to the 6-max GTO-achieving Qwen brain above.

## Tests
`python -m tests.test_game` · `python -m tests.test_table` · `python -m tests.test_bot` · `python -m tests.test_range_tracker`
· `python -m tests.test_icm` · `python -m tests.test_tournament` · Snowie vision: `python -m research.snowie_regress --run`
