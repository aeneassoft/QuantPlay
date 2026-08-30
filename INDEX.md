# PokerB — Repository Index (navigation map)

> **Start here.** ① [`_PRINCE_START_HERE.md`](_PRINCE_START_HERE.md) (the ROOT MARKER — the current mission in one
> page) → ② [`docs/STATE.md`](docs/STATE.md) (live state) → ③ [`docs/VERSION_PRINCE.md`](docs/VERSION_PRINCE.md)
> (**the ACTIVE BUILD CARD**: the next engine version + the merged lever queue + the pre-registered measurement
> ladder). North star + conventions = [`CLAUDE.md`](CLAUDE.md).
> **Current frontier (2026-08-04):** Snowie-Brücke produktionsreif (bereinigter Pool ≈ break-even vs Snowie);
> **Turnier-Modus validiert** (+10,0 ± 5,0 pp ROI gepaart, `strategy/icm.py` + `strategy/tournament.py` +
> `arena/tourney.py`); Multiway 7–10 (Trainer `?players=9`). Shipped-Profil bleibt PRINCE v2.2 (Anker −19,70).
> Historisch (2026-07-05): PRINCE v3 shipped (paired-Analyzer 17.93 vs v2.2's 20.66; live anchor −19.70 ± 4.37 n=2,393, tag `v2`); 4 gated levers in the Analyzer queue (v3.2–v3.5) — AIVAT −11.6 (GTO-mode smoke) / −20.09
> (HEAD, n=974) = #11 of the public leaderboard; **goal: WIN bb** (doctrine: the GTO-score is DEAD as a target —
> measured; only bb count). Key intel: [`docs/GTOW_DOSSIER.md`](docs/GTOW_DOSSIER.md) (the opponent),
> [`docs/TIE_GTOW.md`](docs/TIE_GTOW.md) (the gap ledger), [`data/gtow_grades/LEAK_MAP.md`](data/gtow_grades/LEAK_MAP.md)
> (per-decision leaks incl. the user-found + FIXED turn-defense/slowplay pair). The 6-max Qwen/GLM brain track is
> SECONDARY/parked (`docs/QWEN_6MAX_PLAN.md`, baselines protected).
>
> **Where is which DATA ("the gold")?** → [`CATALOG.md`](CATALOG.md) — the generated map of every asset (shards /
> advisors / models / KB) with role, size, schema, provenance. Built from [`dataset/registry.py`](dataset/registry.py),
> the single source of truth the **training pipeline reads gold by ROLE** from (`registry.sft_gold()`). Refresh:
> `python -m dataset.build_manifest`.
>
> **Where are we GOING?** → [`docs/ROADMAP.md`](docs/ROADMAP.md) — the forward plan: **(A)** how to make the bot
> understand poker maximally (the new `understanding.py` strategic-read layer + the sizing fixes + the measurement
> discipline) and **(B)** a **personal Claude-API coaching path** (review the user's own CoinPoker/PokerStars hands).

## Top-level map (post-reorg, 2026-06-17)
| Dir / file | Purpose |
|---|---|
| `pokerbot/` | the engine + strategy + the LLM-brain interface |
| `pokerbot/engine/` | cards, treys eval, MC `equity.py`, **`table.py` = the 6-max RL ENV** (start/legal/act/obs/result), HU `game.py` |
| `pokerbot/strategy/` | engine PRIMITIVES the brain calls: `preflop_blueprint`, `range_tracker`, `advisor`, `opp_model`, `postflop`, `bot.py`, **`gto_mode.py` (NEW — `POKERB_GTO_MODE` = exploit-OFF + GTOW-tree profile for min-exploitability vs GTOW), `resolver.py`, `gto_oracle.py` (TexasSolver wrapper + disk cache)** |
| `pokerbot/brain/` | **the LLM-brain interface (SECONDARY now):** `api.py` (engine-as-API), `format_spot.py` (canonical spot), `executor.py` (program-of-thought sandbox), `understanding.py` (consolidated strategic read for UNSOLVED spots, gated `POKERB_UNDERSTANDING`), `claude_brain.py`, `policy.py` |
| `pokerbot/arena/` | `sixmax.py` — the opponent LEAGUE (TAG/LAG/nit/station/maniac) |
| `pokerbot/vision/` | **NEW — `screen_reader.py` = universal VLM poker-table reader** (any site/skin, dHash change-gate, `--watch`) |
| `pokerbot/{web,benchmark,coach,analysis}/` | apps; benchmarks (`slumbot`,`gtowizard`,`lbr`,`duplicate`); coaching; analysis |
| `dataset/` | **NEW — THE GOLD:** `build/` (KB→DSL JSONL converters) + the self-growing dataset shards |
| `training/` | **NEW — Qwen:** `qwen_sft.py` (SFT, 8B QLoRA), `qwen_grpo.py` (RL self-play, to build), `qwen_eval.py` |
| `pipeline/` | **NEW — the PC-hub program:** frontier-loop + EV-truth filter + monitor + scp-orchestration (to build) |
| `research/` | the one-off mining/consult/solve scripts. Reusable: `llm.py` (OpenAI/Claude helpers, +vision), `mass_solve.py`, `preflop_*`, `cfv_*`. **GTOW loop (NEW): `pokerstars_export.py` (HU) + `sixmax_export.py` (6-max) → GTOW-Analyzer per-decision grade; `gtow_xray.py`/`gtow_tail.py` (log decomposition); `gtow_tree_census.py` (GTOW's tree from logs); `gtow_ab.py` (interleaved AIVAT A/B); `duplicate_mode_ab.py` (local canary); `resolver_probe.py`/`check_range_l1.py` (S2 gates)** |
| `infra/` | `runpod_run.py` (pod lifecycle) + `cfv_pod_campaign.py` + `pod_setup.sh` (scp-tarball, self-killing) |
| `knowledge_base/` | extracted theory = the dataset SOURCE (`math/`,`concepts/`,`theory/`,`exploit/`,`ranges/`,`postflop/`,`hand_histories/`). **Hard-referenced by config+strategy — do not move.** |
| `books/poker/` | the **6 poker books** (Mathematics of Poker, Beyond GTO, Exploitative Poker, Modern Poker Theory, NLHE T&P, Theory of Poker) · `books/papers/` (CFR, Pluribus, Supremus, PokerBench-LLM, Nash-robustness) |
| `docs/` | live: `STATE.md` (present), **`ROADMAP.md` (forward plan: bot-improvement tracks + the personal coaching path)**, `QWEN_6MAX_PLAN.md`, `DATASET_SPEC.md`, `qwen_train_*.md`, `README.md`. `docs/archive/` = historical consults/plans/reviews |
| `tests/` · `data/` (gitignored) · `models/` (`qwen_poker_ckpt500`) · `tools/` (TexasSolver + GTOW client) |
| `CLAUDE.md` · `NOTES.md` · `README.md` · `START_HIER.md` | north star/conventions · deferred-precision log · overview · German quickstart |

## The Qwen 6-max pipeline (current frontier) — read in order
1. [`CLAUDE.md`](CLAUDE.md) NORTH STAR block — the GTO goal + robust-CE foundation + the 2-node architecture.
2. The plan `.claude/plans/gut-dann-sind-wir-toasty-forest.md` — phased build (0 reorg ✓ → 1 DSL → 2 dataset → 3 PC-hub → 4 RunPod).
3. [`docs/QWEN_6MAX_PLAN.md`](docs/QWEN_6MAX_PLAN.md) + [`docs/DATASET_SPEC.md`](docs/DATASET_SPEC.md) — the staged recipe + the "common language" (program-of-thought + engine-as-API).
4. Consults: [`docs/qwen_train_gpt55.md`](docs/qwen_train_gpt55.md) (conceptual+RL) · [`docs/qwen_train_claude.md`](docs/qwen_train_claude.md) (technical).

## Key entry points (run)
- 6-max app: `python -m pokerbot.web.six_server --open`
- Slumbot bench: `python -m pokerbot.benchmark.slumbot --hands N --exploit-primary`
- Qwen train: `python -m training.qwen_sft` · eval: `python -m training.qwen_eval`
- Solver cache (CPU): `python -m research.mass_solve` · RunPod: `python -m infra.runpod_run`

## Nicht im Repo

`#Anderes/` — alles Nicht-Poker (Lebens-Akte, Geopolitik, Zahlentheorie, Familie).
Gitignored, durch pre-commit-Hook geschuetzt, nie Teil des Repositories.
Beschreibung: `#Anderes/LIESMICH.md`.

## pokerbot/autogym/ (AUTOGYM-Schleife, 2026-08-16/17)
- oracle.py (Mathe-Benchmark HART/P/L/F, W1-1..W1-5) · improver.py (Guard-Wrapper + Gate + Journal)
- pargate.py (paralleles Mirror-Gate, _wickle = EINE Stack-Quelle) · envgate.py (Env-Flag-Zwei-Lauf-Paarung)
- orakel_duell.py (Orakel als Zweitinstrument) · stats.py (Estimator v3: Bootstrap/Permutation)
- gym_hu.py/gym_six.py (Self-Play mit Grading) · runs.py (Run-Ablage) · runde5.py/runde5b.py (Kampagnen)
- exploit_jagd.py (adaptive Jaeger) · selftest.py/verify_refs.py · research/fable_duell.py (LLM-Adversar)
