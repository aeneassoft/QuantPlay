# QuantPlay (formerly PokerB) — Repository Index (navigation map)

> **2026-09-24 — public.** Repo `aeneassoft/QuantPlay`, default branch `poker-core`. The trainer runs in the
> browser at **https://quantplay.io** from [`web/`](../web/) (`build.py` → `dist/`; `src/bridge.js` + `src/worker.js`
> = Pyodide worker; server-less dispatcher [`pokerbot/web/browser_bridge.py`](../pokerbot/web/browser_bridge.py),
> test `tests/test_browser_bridge.py`). Public overview: [`README.md`](../README.md); agent entry: [`AGENTS.md`](../AGENTS.md). Closure note:
> [`PROJECT_BALANCE_2026-09-10.md`](PROJECT_BALANCE_2026-09-10.md).

> **Start here (2026-09-24).** ① [`../README.md`](../README.md) → ② [`PROJECT_BALANCE_2026-09-10.md`](PROJECT_BALANCE_2026-09-10.md)
> (why the goal was missed) → ③ [`STATE.md`](STATE.md) (living log, newest first) → ④ the catalogues
> [`catalogs/MODULE_CATALOG.md`](catalogs/MODULE_CATALOG.md) (what each module does) and
> [`catalogs/MEASUREMENT_CATALOG.md`](catalogs/MEASUREMENT_CATALOG.md) (whether it works). Conventions: [`../CLAUDE.md`](../CLAUDE.md).
> Everything below this line is the historical navigation map (2026-06 to 2026-08) and names states that were later superseded.
>
> **Where is which DATA ("the gold")?** → [`catalogs/DATA_CATALOG.md`](catalogs/DATA_CATALOG.md) — the generated map of every asset (shards /
> advisors / models / KB) with role, size, schema, provenance. Built from [`dataset/registry.py`](../dataset/registry.py),
> the single source of truth the **training pipeline reads gold by ROLE** from (`registry.sft_gold()`). Refresh:
> `python -m dataset.build_manifest`.
>
> **Where are we GOING?** → [`plans/ROADMAP.md`](plans/ROADMAP.md) — the forward plan: **(A)** how to make the bot
> understand poker maximally (the new `understanding.py` strategic-read layer + the sizing fixes + the measurement
> discipline) and **(B)** a **personal Claude-API coaching path** (engine-grounded review of a player's own hand histories).

## Top-level map (post-reorg, 2026-06-17)
| Dir / file | Purpose |
|---|---|
| `pokerbot/` | the engine + strategy + the LLM-brain interface |
| `pokerbot/engine/` | cards, treys eval, MC `equity.py`, **`table.py` = the 6-max RL ENV** (start/legal/act/obs/result), HU `game.py` |
| `pokerbot/strategy/` | engine PRIMITIVES the brain calls: `preflop_blueprint`, `range_tracker`, `advisor`, `opp_model`, `postflop`, `bot.py`, **`gto_mode.py` (NEW — `POKERB_GTO_MODE` = exploit-OFF + GTOW-tree profile for min-exploitability vs GTOW), `resolver.py`, `gto_oracle.py` (TexasSolver wrapper + disk cache)** |
| `pokerbot/brain/` | **the LLM-brain interface (SECONDARY now):** `api.py` (engine-as-API), `format_spot.py` (canonical spot), `executor.py` (program-of-thought sandbox), `understanding.py` (consolidated strategic read for UNSOLVED spots, gated `POKERB_UNDERSTANDING`), `claude_brain.py`, `policy.py` |
| `pokerbot/arena/` | `sixmax.py` — the opponent LEAGUE (TAG/LAG/nit/station/maniac) |
| `pokerbot/vision/` | **NEW — `screen_reader.py` = universal VLM poker-table reader** (any site/skin, dHash change-gate, `--watch`) |
| `pokerbot/{web,benchmark,coach,analysis}/` | apps; benchmarks (`slumbot`,`gtowizard`,`lbr`,`duplicate`); coaching; analysis. **`web/browser_bridge.py` (2026-09-24)** = the trainer's routes without HTTP, for the browser build |
| `web/` | **the static browser trainer (quantplay.io, 2026-09-24):** `build.py` (bundle + hash → `dist/`), `src/bridge.js` (fetch shim + boot overlay), `src/worker.js` (Pyodide 0.28.3 from jsDelivr, vendored `wheels/`), `vercel.json`. Committed `dist/` is what Vercel serves |
| `dataset/` | **NEW — THE GOLD:** `build/` (KB→DSL JSONL converters) + the self-growing dataset shards |
| `training/` | **NEW — Qwen:** `qwen_sft.py` (SFT, 8B QLoRA), `qwen_grpo.py` (RL self-play, to build), `qwen_eval.py` |
| `pipeline/` | **NEW — the PC-hub program:** frontier-loop + EV-truth filter + monitor + scp-orchestration (to build) |
| `research/` | the one-off mining/consult/solve scripts. Reusable: `llm.py` (OpenAI/Claude helpers, +vision), `mass_solve.py`, `preflop_*`, `cfv_*`. **GTOW loop (NEW): `pokerstars_export.py` (HU) + `sixmax_export.py` (6-max) → GTOW-Analyzer per-decision grade; `gtow_xray.py`/`gtow_tail.py` (log decomposition); `gtow_tree_census.py` (GTOW's tree from logs); `gtow_ab.py` (interleaved AIVAT A/B); `duplicate_mode_ab.py` (local canary); `resolver_probe.py`/`check_range_l1.py` (S2 gates)** |
| `infra/` | `runpod_run.py` (pod lifecycle) + `cfv_pod_campaign.py` + `pod_setup.sh` (scp-tarball, self-killing) |
| `knowledge_base/` | extracted theory = the dataset SOURCE (`math/`,`concepts/`,`theory/`,`exploit/`,`ranges/`,`postflop/`,`hand_histories/`). **Hard-referenced by config+strategy — do not move.** |
| `books/poker/` | the **6 poker books** (Mathematics of Poker, Beyond GTO, Exploitative Poker, Modern Poker Theory, NLHE T&P, Theory of Poker) · `books/papers/` (CFR, Pluribus, Supremus, PokerBench-LLM, Nash-robustness) |
| `docs/` | live: `STATE.md` (present), **`plans/ROADMAP.md` (forward plan: bot-improvement tracks + the personal coaching path)**, `plans/QWEN_6MAX_PLAN.md`, `doctrine/DATASET_SPEC.md`, `qwen_train_*.md`, `README.md`. `docs/archive/` = historical consults/plans/reviews |
| `tests/` · `data/` (gitignored) · `models/` (`qwen_poker_ckpt500`) · `tools/` (TexasSolver + GTOW client) |
| `CLAUDE.md` · `NOTES.md` · `README.md` · `archive/START_HERE_2026-06.md` | north star/conventions · deferred-precision log · overview · historical quickstart (first delivery) |

## The Qwen 6-max pipeline (current frontier) — read in order
1. [`CLAUDE.md`](../CLAUDE.md) NORTH STAR block — the GTO goal + robust-CE foundation + the 2-node architecture.
2. The plan `.claude/plans/gut-dann-sind-wir-toasty-forest.md` — phased build (0 reorg ✓ → 1 DSL → 2 dataset → 3 PC-hub → 4 RunPod).
3. [`plans/QWEN_6MAX_PLAN.md`](plans/QWEN_6MAX_PLAN.md) + [`doctrine/DATASET_SPEC.md`](doctrine/DATASET_SPEC.md) — the staged recipe + the "common language" (program-of-thought + engine-as-API).
4. Consults: [`consults/qwen_train_gpt55.md`](consults/qwen_train_gpt55.md) (conceptual+RL) · [`consults/qwen_train_claude.md`](consults/qwen_train_claude.md) (technical).

## Key entry points (run)
- 6-max app: `python -m pokerbot.web.six_server --open`
- Slumbot bench: `python -m pokerbot.benchmark.slumbot --hands N --exploit-primary`
- Qwen train: `python -m training.qwen_sft` · eval: `python -m training.qwen_eval`
- Solver cache (CPU): `python -m research.mass_solve` · RunPod: `python -m infra.runpod_run`

## Not in the repo

Everything non-poker lives OUTSIDE this repository, in its own folders next to `PokerB`.
Until 2026-09-10 there was the git-ignored root folder `#Anderes/` for that; it is deleted,
its content was pulled out. A local pre-commit hook continues to block the old paths.

## pokerbot/autogym/ (AUTOGYM loop, 2026-08-16/17)
- oracle.py (math benchmark HART/P/L/F, W1-1..W1-5) · improver.py (guard wrapper + gate + journal)
- pargate.py (parallel mirror gate, _wickle = ONE stack source) · envgate.py (env-flag two-run pairing)
- orakel_duell.py (oracle as second instrument) · stats.py (estimator v3: bootstrap/permutation)
- gym_hu.py/gym_six.py (self-play with grading) · runs.py (run storage) · runde5.py/runde5b.py (campaigns)
- exploit_jagd.py (adaptive hunters) · selftest.py/verify_refs.py · research/fable_duell.py (LLM adversary)
