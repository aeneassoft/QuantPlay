# BOT PARTS CATALOG — every part, its status, its compute (2026-06-15)

*Complete inventory of ALL parts (cataloged by 4 parallel agents, grepped for real import/usage — not guessed).
Purpose: the project has accreted MANY parts but has **no coherent working MVP** (measured: the integrated bot is
−71 bb/100 vs GTO Wizard, ON or OFF the resolver — worse than always-fold). This catalog is the basis for the NEXT
step: decide how to bring the best parts together into one functioning MVP (the ensemble/router idea). Status legend:
**LIVE** = on a real playing/serving path · **TOOL** = run manually · **TRAIN/COMPUTE** = offline build · **DEAD** =
not imported anywhere / superseded. Compute: **CPU-LIVE** (heavy per-decision) · **CPU-MASSOLVE** (offline parallel
TexasSolver — the "strong-CPU" kind) · **GPU** · **NET** (external API) · **LIGHT**.*

---

## ★ §0 THE FRAGMENTATION MAP — why there's no MVP yet (read this first)

The single most important finding of the catalog: **the parts don't converge on one bot.**

1. **TWO separate playing brains, no shared decision core:**
   - **HU:** `strategy/bot.py` (`PokerBot`) — served by `web/server.py`, used by all HU benchmarks.
   - **6-max:** `arena/sixmax.py` (`SixMaxBot`) — served by `web/six_server.py` (THE main app). Totally separate decision logic; only shares the engine + `postflop.py`.
2. **A whole EXPLOIT CLUSTER is built but ORPHANED** — reachable only through `adaptive.py` (`AdaptiveExploiter`), which **no app/live path uses** (only benchmarks + `arena/haiku_pilot` + `slumbot_adaptive`). So these are effectively dead to the playing bot:
   - `adaptive.py` (the "universal exploiter" + ProbeController + TwoModelGate + Knobs)
   - `unified_exploit.py` (the **62 book rules** → nudges)
   - `playbook.py` (the 11.5k-directive LLM playbook / cold-start prior)
   - `calibration.py` (predict→measure→calibrate fold-equity)
   - The live `bot.py` has its OWN, DIFFERENT exploit path (`opp_model` + `exploit_engine` river EV + a probe). **The WS3 "unify" was only half-done:** bot.py got the river exploit engine; the rest of adaptive's machinery was never ported in.
3. **Dead / superseded files** (built, now unused): `strategy/pluribus_exploit.py` (Pluribus fold model never wired), `coach/translate.py` (directive→param pipeline never wired), `benchmark/gto_check.py` + `benchmark/improve.py` (superseded by `gto_benchmark`/`floor_map` + `calibrate`).
4. **The "GTO floor" the bot actually plays is the HEURISTIC + advisors**, not `gto_baseline.py` — `gto_baseline.py` (`GTOBaseline`) is a benchmark *reference opponent*, NOT the player. And `preflop_gto.py` (the 88.6% table) is wired into 6-max RFI only, **NOT** into the HU `bot.py` (it uses the weaker strength-heuristic).
5. **The real-time GTO path (resolver + range_tracker) is wired but default-OFF** and (measured) neutral-to-harmful until ranges are correct.

→ **Unification target:** ONE decision core, with the best parts routed in by reliability (the ensemble/router), the orphaned cluster either ported-in-gated or deleted, the dead files removed.

---

## §1 THE LIVE PLAYING PATH (what actually plays today)

**HU `PokerBot.decide` (`strategy/bot.py`)** calls, in order:
- Preflop: `cfr_preflop`/`blueprint` (push-fold ≤14bb, verified Nash) + `ranges.py` + `preflop_strength.py` (deeper, heuristic). *(NOT `preflop_gto.py`.)*
- Postflop floor: `advisor.py` (flop/turn/river solver-imitation MLPs + `features.py`) → per-hand P(bet); else `postflop.py` heuristic (texture c-bet, fold-equity sizing, `PriorFoldModel`/`LearnedFoldModel`); MDF/pot-odds defense.
- Exploit-primary river: `opp_model.py` (Dirichlet per-node) + `exploit_engine.py` (LCB-gated max-EV) + the off-tree probe; `opponent.py` (aggregate read).
- Real-time GTO (opt-in, default OFF): `resolver.py` (river/turn) + `range_tracker.py` (+ `gto_oracle.py` → live TexasSolver).
- Per decision: `engine/equity.py` Monte-Carlo equity (the dominant per-decision cost).

**6-max `SixMaxBot` (`arena/sixmax.py`)**: position-aware TAG + per-seat opponent profiles + bounded online exploiter; uses `engine/table.py`, `postflop.py`, `preflop_gto.py` (RFI). Served by `web/six_server.py` + `web/session_log.py` (+ `analysis/session_analysis.py` on the analyze button).

---

## §2 THE BOT PROPER — `pokerbot/`

### engine/
| Part | Role | Status | Compute |
|---|---|---|---|
| `engine/cards.py` | 2-char cards, Deck, 169 classes, combos | LIVE | LIGHT |
| `engine/evaluator.py` | treys 7-card scoring | LIVE | LIGHT |
| `engine/equity.py` | MC equity (river ENUMERATES; flop/turn sample) | LIVE | **CPU-LIVE** |
| `engine/game.py` | HU state machine | LIVE | LIGHT |
| `engine/table.py` | N-player table + side pots (6-max) | LIVE | LIGHT |

### strategy/ — preflop
| Part | Role | Status | Compute |
|---|---|---|---|
| `preflop_strength.py` | 169-class strength + `range_top` (cached) | LIVE | CPU-MASSOLVE (1× build) |
| `ranges.py` | percentile range bands | LIVE | LIGHT |
| `cfr_preflop.py` | push/fold CFR solver → blueprint | TRAIN | **CPU-MASSOLVE** |
| `blueprint.py` | serves push/fold Nash | LIVE | LIGHT |
| `preflop_gto.py` | 88.6% PokerBench table | LIVE **(6-max RFI only — NOT in HU bot)** | LIGHT |

### strategy/ — postflop floor + advisors
| Part | Role | Status | Compute |
|---|---|---|---|
| `postflop.py` | texture, fold-equity sizing, `PriorFoldModel`/`LearnedFoldModel` | LIVE | LIGHT |
| `advisor.py` | flop/turn/river solver-imitation MLPs → P(bet) | LIVE | LIGHT (tiny MLP) |
| `features.py` | blocker/draw/tier features | LIVE | LIGHT |
| `gto_baseline.py` | analytic near-GTO baseline | **TOOL (benchmark reference, NOT the player)** | CPU-LIVE |

### strategy/ — real-time GTO (MVP#2)
| Part | Role | Status | Compute |
|---|---|---|---|
| `gto_oracle.py` | drives TexasSolver `console_solver.exe` | LIVE (via resolver, opt-in) | **CPU-LIVE** |
| `resolver.py` | live river/turn re-solve → GTO action | LIVE (opt-in, default OFF; measured neutral w/ wide ranges) | **CPU-LIVE** |
| `range_tracker.py` | v2 Bayesian per-combo range recon + conf gate | LIVE (feeds resolver) | LIGHT |

### strategy/ — exploit + opponent models
| Part | Role | Status | Compute |
|---|---|---|---|
| `opponent.py` | aggregate VPIP/fold/aggr read (shrinkage) | LIVE | LIGHT |
| `opp_model.py` | Dirichlet per-node fold/call/raise | LIVE (river exploit) | LIGHT |
| `exploit_engine.py` | LCB-gated max-EV river | LIVE (`_river_exploit`) | LIGHT |
| `adaptive.py` | "universal exploiter" + probe + gate + knobs | **TOOL (ORPHANED — not in any app)** | CPU-LIVE |
| `unified_exploit.py` | 62 book rules → nudges | **via adaptive only → effectively DEAD to the bot** | LIGHT |
| `playbook.py` | LLM playbook cold-start prior | **via adaptive only → DEAD to the bot** | LIGHT |
| `calibration.py` | predict→measure→calibrate | **via adaptive only → DEAD to the bot** | LIGHT |
| `pluribus_exploit.py` | Pluribus fold model | **DEAD-UNUSED** | LIGHT |

### strategy/ — offline / neural
| Part | Role | Status | Compute |
|---|---|---|---|
| `distill.py` | solver→policy distillation (+ `solve_focus_spots`) | TRAIN | **GPU** (train) / **CPU-MASSOLVE** (solve) |
| `deep_cfr.py` | Leduc Deep-CFR + exact exploitability | TRAIN/TOOL (not imported) | GPU |
| `bot.py` | **the HU decision engine** (`PokerBot`) | **LIVE (canonical HU player)** | **CPU-LIVE** |

### arena / coach / web / analysis / config
| Part | Role | Status | Compute |
|---|---|---|---|
| `arena/sixmax.py` | **6-max decision brain** (`SixMaxBot`) | **LIVE (main app)** | CPU-LIVE |
| `arena/openpoker.py` | Open Poker WS client | TOOL | NET (WS) |
| `arena/haiku_pilot.py` | Haiku flips adaptive knobs (experiment) | TOOL | NET |
| `coach/coach.py` | HU in-app Claude coach | LIVE (HU app) | NET |
| `coach/meta_coach.py` | run-director / exploit-hypothesis LLM | TOOL (optional injection) | NET |
| `coach/translate.py` | spot→prose, directive→param | **DEAD-UNUSED** | LIGHT |
| `web/six_server.py` | **6-max app (THE main app)** | LIVE | CPU-LIVE |
| `web/server.py` | HU app + live coach | LIVE (secondary) | CPU-LIVE + NET |
| `web/session_log.py` | per-hand JSONL logger | LIVE (6-max) | LIGHT |
| `analysis/session_analysis.py` | session stats + Claude narrative | LIVE (6-max analyze) | NET |
| `analysis/{session_deep,harvest_play,luck_vs_skill,pluribus_catalog,_dig}.py` | session/Pluribus analysis | TOOL | LIGHT (luck_vs_skill = CPU-LIVE) |
| `config.py` | paths, models, keys (Secret keys/) | CONFIG (imported everywhere) | LIGHT |

---

## §3 MEASUREMENT / BENCHMARK — `pokerbot/benchmark/`

**Active gates (trusted accept/reject):** `duplicate.py` (paired/duplicate, the linchpin) + its derivatives `floor_ablate.py`, `exploit_proof.py`; `floor_map.py` (multi-street GTO-gap); `gto_oracle_match.py` (paired vs live-solver oracle); `gto_benchmark.py` (cache/selector, imported widely); `scorecard.py` (the aggregator). `lbr.py`+`lbr_falsify.py` = exploitability (LBR proven vacuous → needs range-aware v2).
**External-opponent tools:** `slumbot.py` (+`probe.py`, `slumbot_adaptive.py`) [NET], `gtowizard.py` (+`tools/gtow_run.py`) [NET, the definitive AIVAT gate], `llm_opponent.py` [NET].
**Internal/field tools:** `internal.py`, `beat_them_all.py`, `weaponize.py` [CPU-MASSOLVE-class, parallel], `runpod_train.py` [**CPU-MASSOLVE** — the designated RunPod CPU sweep].
**Pluribus/PHH leak-mining (data producers):** `pluribus_bench.py` [CPU-LIVE], `pluribus_leaks.py`, `phh_leaks.py`.
**DEAD/superseded:** `gto_check.py`, `improve.py`. **CPU-LIVE (live solves/MC):** `gto_benchmark`(first run), `gto_oracle_match`, `lbr`, `lbr_falsify`, `pluribus_bench`, `scorecard --full`.

---

## §4 TOOLING / COMPUTE — `extraction/` (~70 files)

**COMPUTE-JOBS (heavy):**
- `mass_solve.py` — **THE CPU mass-solve** (RAM-adaptive parallel TexasSolver → GTO cache). **CPU-MASSOLVE.**
- `deep_cfr_nlhe.py` — OpenSpiel Deep-CFR on HU-NLHE (B200-sized). **GPU.**
- `qwen_sft.py` — Qwen3-8B LoRA SFT on PokerBench. **GPU.**
- `pod_run30.py` — distill orchestrator (solve + train + LLM director). **CPU-MASSOLVE + GPU + NET.**
- `distill_improve.py` — local floor-net MLP trainer. **GPU (local).**
- `openspiel_leduc.py` — Leduc Deep-CFR convergence proof. GPU (small).

**DATA-BUILD (from caches → training data/tables, mostly LIGHT):** `build_{advisor,turn,river}_data.py`, `train_{advisor,turn,river}_advisor.py`, `texture_freqs.py`, `preflop_table.py`, `consolidate_exploit.py`, `grounded_blindspots.py` [CPU-LIVE], `blindspot_radar.py` [NET+CPU-LIVE], `exploit_playbook.py` [NET].
**POD/VM LIFECYCLE:** `runpod_run.py` (the manager — `--launch`/`--cpu`/`--kill`), `runpod_{launch,check,recon,cpu_probe}.py`, `_pod_diag.py`, the `*.sh` bootstrap scripts, `gcp_solve_setup.sh`. **NET.** *(ALWAYS `--kill`.)*
**BOOK-EXTRACT pipeline (grouped):** `extract_text/chunk/extract_concepts/parse_ranges/extract_ranges_vision/extract_math/mathematics_of_poker/extract_book` + `llm.py` + `pdf_peek.py` → `knowledge_base/{concepts,ranges,math}`. **NET.**
**LLM-CONSULT one-offs (grouped, ~25, NET):** `theory_qa, exploit_synthesis, grand_synthesis, gto_hybrid, gto_shortcut, exploit_gto_bridge, poker_for_compute, phase5_math_check, solvability_query, solvability_proof_consult, gto_frontier_consult, alpha_consult, situational_consult, synthesis_consult, phase1_consult, simplify_consult, orchestrate_consult, landscape_consult, runpod_gto_consult, range_tracker_consult, postflop_openai, cfr_tips, perplexity_search, bot_audit` + model probes `probe_apis/_models/venice_models`.
**MISC:** `llm_exploit_demo, llm_probe` [CPU-LIVE, local LoRA], `pokerbench_grounded, peek_pb, inspect_node` [LIGHT], `smoke_weighted_resolve.py` [CPU-LIVE, the resolver smoke].

---

## §5 ⚡ COMPUTE MAP — what needs a strong CPU / GPU (the flag you asked for)

**CPU-MASSOLVE — heavy offline parallel CPU (the "strong-CPU / RunPod-CPU" jobs):**
- `extraction/mass_solve.py` — TexasSolver mass-solve → GTO cache (the data engine; wants MANY cores + RAM; RAM is the binding constraint, auto-throttles). **This is the box the $140-RunPod plan is about.**
- `strategy/cfr_preflop.py` — 120k-iter push/fold CFR (one-time blueprint build).
- `strategy/distill.py → solve_focus_spots` + `extraction/pod_run30.py` — parallel curriculum solves.
- `benchmark/runpod_train.py` — embarrassingly-parallel stack×param sweep (the designated RunPod CPU bench).
- `preflop_strength.py` — 1× MC build of the strength table (LIGHT once cached).

**CPU-LIVE — heavy CPU at DECISION time (latency-bound; matters for live play):**
- `engine/equity.py` — MC equity, called EVERY postflop decision (the dominant cost; `EQUITY_ITERS=1500`).
- `strategy/resolver.py` + `gto_oracle.py` — live TexasSolver solve per decision (~seconds; river ~1.8s, turn ~7.5s) — **why the resolver can't be "always on" for real-time play**.
- `gto_baseline.py`, `adaptive.py`, `benchmark/{gto_oracle_match,lbr,lbr_falsify,pluribus_bench}.py` (bench paths).

**GPU — needs a real CUDA GPU (RunPod, separate box from any CPU mass-solve):**
- `extraction/deep_cfr_nlhe.py`, `extraction/qwen_sft.py`, `extraction/eval_lora.py`/`qwen_eval.py`, `extraction/distill_improve.py` (local 3080 Ti), `strategy/distill.py → train`, `strategy/deep_cfr.py`. *(B200/sm_100 needs torch cu128.)*

**NET — external API:** Anthropic (`coach`, `meta_coach`, `session_analysis`, `haiku_pilot`, the consults), OpenAI (math consults), GTO Wizard (`gtowizard`+`gtow_run`), Slumbot (`slumbot`/`probe`), WebSocket (`openpoker`).

*Note (CLAUDE.md): a CPU mass-solve and a GPU train must NOT share one box (the solver starves GPU dispatch + sshd). Mass-solve LOCAL or its own CPU pod; GPU on a separate GPU pod.*

---

## §6 NEXT STEP (not done here — the catalog's purpose)
With every part now mapped, the unification question becomes concrete: pick ONE decision core; decide for each part — **route-in-gated** (the best parts, reliability-weighted — engine, advisors, exploit-river, resolver-when-confident), **port-then-gate** (the orphaned cluster: 62 rules, playbook, calibration, probe — if they earn their keep), or **delete** (dead files: pluribus_exploit, translate, gto_check, improve). Then validate the unified MVP at n≥2500 (the only decision-grade bar). That design is the next session's work.
