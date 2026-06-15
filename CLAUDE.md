# CLAUDE.md — PokerB

A Heads-Up **and** 6-max No-Limit Hold'em bot grounded in five poker books, with a browser app
to play against it, an opponent-exploiting layer, and tooling to analyze your own play. Built
across several sessions — see the user memory for the full history.

> **New Claude session? Start with [`docs/STATE.md`](docs/STATE.md)** — live state, current workstream,
> artifacts, and next steps with cross-references. This file = stable conventions; `STATE.md` = what's happening now.
>
> **Current phase (2026-06-15): CONSOLIDATION & PRUNING.** Not adding features — we MESH/fit the EXISTING parts
> so the engine runs cleanly, ERADICATE dead code + statistical leaks, and improve the floor via a grounded
> iterative loop (held-out solver EV-gap gate; see [`docs/ORCHESTRATION_PLAN.md`](docs/ORCHESTRATION_PLAN.md)).
> A neural net enters ONLY as a confidence-gated supervised *advisor* (glue over existing data), never a
> from-scratch build. Bias toward deleting/unifying over adding (see [`docs/CONSOLIDATION_PLAN.md`](docs/CONSOLIDATION_PLAN.md)).

## Run / play
- **6-max vs 5 bots (the main app):** `python -m pokerbot.web.six_server --open` → http://127.0.0.1:8000
  Desktop launcher: **`PokerB 6max spielen.bat`**. Fast (bots decide locally, no LLM in-play); logs
  every hand to `data/sessions/session_*.jsonl`; "Analyse" button = end-of-session breakdown.
- **Heads-Up + live coach:** `python -m pokerbot.web.server --open`. Desktop: **`PokerB spielen.bat`**.
- Always run from the project root as `python -m <module>` (the `pokerbot`/`extraction` packages need
  the root on `sys.path`). Windows / PowerShell, Python 3.12. Install: `pip install -r requirements.txt`.

## Architecture
- `pokerbot/engine/` — cards, treys evaluator, Monte-Carlo equity, HU `game.py`, N-player `table.py` (side pots).
- `pokerbot/strategy/` — preflop strength model, ranges, **CFR push/fold blueprint** (`cfr_preflop.py` +
  `blueprint.py`), **postflop + fold-equity sizing** (`postflop.py`), the **analytic GTO baseline**
  (`gto_baseline.py`, texture/aggressor-aware) measured against the **TexasSolver GTO oracle** (`gto_oracle.py`),
  online `opponent.py` model, the **adaptive exploitation engine** (`adaptive.py`), per-opponent exploit models
  (`pluribus_exploit.py`, the Slumbot `LearnedFoldModel`), the HU `bot.py`.
- `pokerbot/arena/` — `sixmax.py` (6-max decision brain), `openpoker.py` (Open Poker WebSocket client).
- `pokerbot/coach/` — Claude-backed coaching (HU app); `meta_coach.py` (engine-agnostic in-loop meta-coach /
  exploit-hypothesis / run-director — Anthropic or an OpenAI-compatible vLLM endpoint), `translate.py`
  (engine spot ↔ poker prose, directive → clamped param delta).
- `pokerbot/analysis/` — `session_analysis.py` (stats + Claude narrative), `session_deep.py` (meta-pattern /
  better-vs-bot / tilt), `pluribus_catalog.py`.
- `pokerbot/web/` — FastAPI servers + `static/*.html` single-page UIs (`six.html` = 6-max, `index.html` = HU).
- `pokerbot/benchmark/` — `slumbot.py` (play Slumbot's API, `--exploit`), `probe.py` (learn its fold curve),
  `internal.py` (local baselines), `pluribus_bench.py` (decision-alignment vs Pluribus) + `pluribus_leaks.py`
  (mine its exploitable fold-curve), `beat_them_all.py` (adaptive vs a diverse suite), `lbr.py` (LBR
  exploitability lower bound), `llm_opponent.py` (our bot vs a frontier-LLM agent, GTO-Wizard-leaderboard-style).
- `extraction/` — book-mining pipeline (PDF→text→Claude concepts/ranges + OpenAI math; `mathematics_of_poker.py`)
  PLUS heavy-compute: `mass_solve.py` (RAM-adaptive parallel TexasSolver → GTO cache), `analyze_cache.py`
  (cache → GTO patterns by texture), `exploit_playbook.py` (concurrent Claude → bounded exploit-directive grid),
  `qwen_sft.py` (Qwen LoRA fine-tune on PokerBench), `runpod_run.py` (pod lifecycle), `deep_cfr_nlhe.py`, `pod_run30.py`.
  **Active learning (2026-06-14):** `grounded_blindspots.py` (solver-disagreement per spot = the RELIABLE
  acquisition signal) + `blindspot_radar.py` (Claude-Haiku triage = cheap hypotheses, MUST be solver-verified);
  `solvability_query.py` (OpenAI); `gcp_solve_setup.sh`/`gcp_solve_launch.sh` (GCP coverage-solve — free-tier
  capped at 12 vCPU global, big run needs an account upgrade).
- `knowledge_base/` — extracted artifacts: `concepts/`, `ranges/` (+ `cfr/preflop_pushfold.json`), `math/`
  (incl. `mathematics_of_poker.json`), `hand_histories/` (10k Pluribus hands), `exploit/` (`slumbot_fold.json`
  + `playbook.jsonl` = 11.5k Haiku exploit directives + `playbook_opus_coarse.jsonl` = 240 Opus).
- `docs/` — `STATE.md` (session entry point) + ROADMAP / POD_PLAN / RUNPOD_PLAN etc.
- `tests/` — engine stress tests + bot/web smoke tests. `data/` — intermediate + session logs (gitignored).

## Config / keys
- `pokerbot/config.py`: paths, models, API keys. Keys are read from `C:\Users\hampe\Desktop\Secret keys\`
  (Claude + OpenAI under `AI\`, RunPod) with env-var override — **never hardcode keys in source**.
- Models: Claude **`claude-opus-4-8`**; OpenAI auto-resolves to **`gpt-5.1`** (see `OPENAI_MODEL_PREFERENCE`).

## Conventions / gotchas
- Cards are 2-char strings (`'As'`, `'Td'`) — treys-compatible. `bb = 100` chips in the apps; UIs show bb.
- `six_server.index()` reads `six.html` fresh per request (browser refresh shows UI edits). The other
  servers cache HTML at import → restart to pick up changes.
- `TaskStop` on a backgrounded server can leave the Python child alive holding the port. If a port is
  "in use": `Get-NetTCPConnection -LocalPort <p>` → `Stop-Process -Id <pid> -Force`.
- The Claude-Preview screenshot tool hangs in this environment — verify UIs via the API or
  `fastapi.testclient.TestClient` (in-process), not screenshots.
- 6-max UI: chip colours are deliberately outside the teal/cyan/gold theme; only winners reveal cards
  (mucking); only the human's own net is shown; next hand auto-advances (~2.4 s).

## Heavy compute / pod (RunPod)
- `extraction/runpod_run.py` provisions/kills a GPU pod (B200 via `--fast`). **ALWAYS `--kill` when done** — it
  does `DELETE /pods/{id}` = full terminate (compute+storage billing stops); a mere "stop" still bills storage.
- B200 = Blackwell (sm_100): the stock `pytorch:2.4` image's torch fails "no kernel image" → on the pod
  `pip install -U torch --index-url https://download.pytorch.org/whl/cu128` (+ drop torchvision/torchaudio). Verify
  FOREGROUND that `torch.__version__` ends `+cu128` (a quiet `-q` install can silently no-op).
- **CPU and GPU heavy jobs do NOT coexist on one box**: a TexasSolver mass-solve starves the GPU trainer's
  kernel-dispatch *and* saturates sshd (SSH 255s, unmanageable). Run the GPU job on the pod and the CPU
  mass-solve LOCALLY (separate boxes). SSH key `C:\Users\hampe\.ssh\pokerb_runpod`; fresh pods get a NEW ssh port.

## Honest status (what's real)
- **Preflop** is GTO-grounded: CFR push/fold = verified Nash; deeper stacks use a strength-model range system.
- **Postflop** is equity + pot-odds/MDF + **fold-equity-optimal bet sizing** + an exploit layer — *not* a solver.
- vs **Slumbot** (measured 2026-06-14, 300h samples): the old "heuristic alone ≈ −170" was a small-sample
  MYTH. The no-exploit floor actually lost **~−526 bb/100** because it **stacked off 200bb bluff-raising air**
  (`PriorFoldModel` assumed a ~60% fold a near-GTO opponent never gives → `ev_bluff` looked +EV). A cheap
  **anti-spew floor fix** (the floor never raise-bluffs without a confident read; value-raise/SPR commitment
  caps) took the no-exploit floor to **~−46 bb/100** (near break-even, +480 bb/100 swing). With the fold-curve
  exploit on the fixed floor: **~−5.4 bb/100** (500h, ±113 — statistically ≈break-even; was −186 pre-fix, so
  NOT yet conclusively break-even, needs 5–10k hands). LESSON: the heuristic floor still hides cheap, huge wins.
- vs **Pluribus** (from its 10k hands): it over-folds postflop heads-up to small/pot bets → exploit projects
  ~**+4 bb/100** (ceiling ~6–8); small but real & safe (it never adapts). See `knowledge_base/exploit/`.
- Crushes weak/exploitable opponents locally (+300–700 bb/100).
- **Bot cleanup (2026-06-14):** an independent `claude-opus-4-8` audit (`extraction/bot_audit.py`, hand-vetted)
  found the SAME stack-off spew live in `adaptive.py`; root cause = it never tightened villain's range vs
  aggression. Fixed (range-narrowing + commitment caps + preflop-4bet premium gate); 200bb stack-offs eliminated.
- **Benchmarks & the verify-everything lesson (2026-06-14):** the rigorous HU target is the **GTO Wizard
  Benchmark** (`benchmark.gtowizard.com` — public API + leaderboard, HUNL 200bb, scored vs GTOW AI with
  **AIVAT** variance reduction → 10× less data; request a key via their form, client = `gtowizard-ai/
  researcher-api-client`, Python, `PokerAgent.act(GameServiceResponse)->ActRequest{f/k/c/b}`). On that board
  EVERY LLM/agent LOSES (best ~−3 bb/100): you can't beat near-GTO, only minimize the loss. HARD LESSON:
  candidate fixes from LLM triage AND single-rule raw-bb/100 A/B are too unreliable/noisy — only a GROUNDED
  signal (solver TV-gap / AIVAT) or a deterministic check should gate a change (two plausible fixes — thin-value
  and draw-c-bet — were REVERTED after measurement refuted them).
- **GTO oracle says** (597 solved flops, `analyze_cache.py`): IP c-bet should be texture-conditioned (~77% on
  dry/high/rainbow vs ~58–60% monotone/connected) at a single ~⅔-pot size — the next `gto_baseline` change. An
  **exploit playbook** (Claude, bounded + benchmark-verifiable) seeds cold-start exploits for the adaptive engine.

## Direction (not a rulebook — current thinking, expected to evolve)
No bot plays **true GTO** yet, so every opponent (Pluribus, Slumbot, GTO Wizard, humans) is an exploitable
approximation. Imitating any one of them is a ceiling. The goal is a **universal adaptive exploiter**: a
robust low-exploitability baseline + an online opponent-model that detects each opponent's leaks and
exploits them safely, with a confidence-gated fallback — built to handle opponents *we haven't seen yet*.
"Beat them all" requires adaptivity (the exploit that beats one bot loses to another). RunPod/Deep-CFR is
an *optional* lever for a stronger baseline, not the edge. Stay honest about what's measured vs projected.
**Solvability validation (gpt-5.1, 2026-06-14, `data/sessions/solvability_6max.md`):** 6-max NLHE is provably
NOT "solvable" like heads-up — multiplayer general-sum ⇒ computing Nash is PPAD-hard & non-unique, no-regret
(CFR) only reaches a CCE not Nash, and exploitability isn't a clean scalar. So this design *is* the only sound
north star: a bounded-exploitability blueprint (floor) + an adaptive exploiter, judged by MEASURED
exploitability (LBR/AIVAT) + realized bb/100 — never a "solve". The edge = exploiting each opponent's gap to
GTO; vs near-GTO (GTO Wizard) the ceiling is ~break-even, vs the field it's huge.

## Tests
`python -m tests.test_game` · `python -m tests.test_table` · `python -m tests.test_bot` ·
`python -m pokerbot.strategy.cfr_preflop --quick`
