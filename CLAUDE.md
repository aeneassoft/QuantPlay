# CLAUDE.md — PokerB

**Goal: a world-class 6-max No-Limit Hold'em AI that PLAYS GTO — i.e. approaches TRUE GTO.** The AI is three
assets ("the gold"): a **self-growing, EV-grounded dataset**, a **fine-tuned Qwen "brain"**, and **our engine as the
scaffold** the brain drives. Built across many sessions — see the user memory + `docs/STATE.md` for history.

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
> `.claude/plans/gut-dann-sind-wir-toasty-forest.md` · `docs/QWEN_6MAX_PLAN.md` · `docs/DATASET_SPEC.md`.
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

> **New Claude session? Start with [`docs/STATE.md`](docs/STATE.md)** — the LIVE source of truth. Live repo tree =
> [`INDEX.md`](INDEX.md). This file = stable conventions + the north star; `STATE.md` = what's happening now.
>
> **⟳ KEEP STATE.md CURRENT — standing rule.** After any turn that moves a headline number (a measurement), lands a
> build, or shifts priorities, UPDATE STATE.md's top CURRENT section *before ending the turn* — lead with the current
> frontier, demote superseded numbers to a one-line "history" pointer. A fresh context must start from the truth.
>
> **Deferred-precision / open questions:** [`NOTES.md`](NOTES.md) — approximations we ship now + should compute
> exactly later. Add an entry when you ship a heuristic.

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

## Run / play
- **6-max vs 5 bots (the app):** `python -m pokerbot.web.six_server --open` → http://127.0.0.1:8000 (launcher
  `PokerB 6max spielen.bat`). Logs each hand to `data/sessions/`; "Analyse" = end-of-session breakdown.
- HU app (background/validation only now): `python -m pokerbot.web.server --open`.
- Always run from the project root as `python -m <module>`. Windows / PowerShell, Python 3.12. `pip install -r requirements.txt`.

## Architecture (logical; the live tree is [`INDEX.md`](INDEX.md))
- `pokerbot/engine/` — cards, treys evaluator, MC equity (`equity.py`), the **N-player `table.py` = the 6-max RL
  ENVIRONMENT** (start_hand / legal_actions / act / obs_for / result, side pots), HU `game.py`.
- `pokerbot/strategy/` — the engine PRIMITIVES the brain calls: `preflop_blueprint.py`, `range_tracker.py`,
  `advisor.py` (solver-frequency MLPs), `opp_model.py` (Dirichlet exploit), `postflop.py` (sizing/texture), `bot.py`.
- `pokerbot/brain/` — **the LLM-brain interface (NEW):** `api.py` (typed engine-API = the DSL vocabulary),
  `format_spot.py` (canonical 6-max spot, PokerBench-aligned), `executor.py` (program-of-thought sandbox).
- `pokerbot/arena/` — `sixmax.py` (the opponent LEAGUE: TAG/LAG/nit/station/maniac profiles).
- `pokerbot/{web,benchmark,coach,analysis}/` — apps; benchmarks (`slumbot.py`, `gtowizard.py`, `lbr.py`,
  `duplicate.py`); coaching; session analysis.
- `dataset/` — **the GOLD (NEW):** `build/` (KB→DSL JSONL converters) + the self-growing dataset shards.
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
- `docs/` (`STATE.md` entry point + plans/consults) · `tests/` · `data/` (gitignored) · `models/` (`qwen_poker_ckpt500`) · `tools/` (TexasSolver + GTOW client).

## The common language (DSL) — see [`docs/DATASET_SPEC.md`](docs/DATASET_SPEC.md)
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
