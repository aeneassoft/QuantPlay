# PokerB — Repository Index (navigation map)

> **Start here.** North star + conventions = [`CLAUDE.md`](CLAUDE.md); live state = [`docs/STATE.md`](docs/STATE.md);
> current frontier = the **6-max GTO Qwen brain** ([`docs/QWEN_6MAX_PLAN.md`](docs/QWEN_6MAX_PLAN.md) +
> [`docs/DATASET_SPEC.md`](docs/DATASET_SPEC.md) + plan `.claude/plans/gut-dann-sind-wir-toasty-forest.md`).
> **Goal = PLAY GTO / ACHIEVE TRUE GTO in 6-max** via a fine-tuned Qwen that drives our engine (program-of-thought).

## Top-level map (post-reorg, 2026-06-17)
| Dir / file | Purpose |
|---|---|
| `pokerbot/` | the engine + strategy + the LLM-brain interface |
| `pokerbot/engine/` | cards, treys eval, MC `equity.py`, **`table.py` = the 6-max RL ENV** (start/legal/act/obs/result), HU `game.py` |
| `pokerbot/strategy/` | engine PRIMITIVES the brain calls: `preflop_blueprint`, `range_tracker`, `advisor`, `opp_model`, `postflop`, `bot.py` |
| `pokerbot/brain/` | **NEW — the LLM-brain interface:** `api.py` (engine-as-API), `format_spot.py` (canonical spot), `executor.py` (program-of-thought sandbox) |
| `pokerbot/arena/` | `sixmax.py` — the opponent LEAGUE (TAG/LAG/nit/station/maniac) |
| `pokerbot/{web,benchmark,coach,analysis}/` | apps; benchmarks (`slumbot`,`gtowizard`,`lbr`,`duplicate`); coaching; analysis |
| `dataset/` | **NEW — THE GOLD:** `build/` (KB→DSL JSONL converters) + the self-growing dataset shards |
| `training/` | **NEW — Qwen:** `qwen_sft.py` (SFT, 8B QLoRA), `qwen_grpo.py` (RL self-play, to build), `qwen_eval.py` |
| `pipeline/` | **NEW — the PC-hub program:** frontier-loop + EV-truth filter + monitor + scp-orchestration (to build) |
| `research/` | the one-off mining/consult/solve scripts (ex-`extraction/`, 91 files). Reusable: `llm.py` (OpenAI/Claude helpers), `mass_solve.py`, `preflop_*`, `cfv_*` |
| `infra/` | `runpod_run.py` (pod lifecycle) + `cfv_pod_campaign.py` + `pod_setup.sh` (scp-tarball, self-killing) |
| `knowledge_base/` | extracted theory = the dataset SOURCE (`math/`,`concepts/`,`theory/`,`exploit/`,`ranges/`,`postflop/`,`hand_histories/`). **Hard-referenced by config+strategy — do not move.** |
| `books/poker/` | the **6 poker books** (Mathematics of Poker, Beyond GTO, Exploitative Poker, Modern Poker Theory, NLHE T&P, Theory of Poker) · `books/papers/` (CFR, Pluribus, Supremus, PokerBench-LLM, Nash-robustness) |
| `docs/` | live: `STATE.md`, `QWEN_6MAX_PLAN.md`, `DATASET_SPEC.md`, `qwen_train_*.md`, `NEXT_RUN_TODO.md`, `README.md`. `docs/archive/` = 57 historical consults/plans/reviews |
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
