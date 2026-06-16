# CLAUDE.md — PokerB

A Heads-Up **and** 6-max No-Limit Hold'em bot grounded in five poker books, with a browser app
to play against it, an opponent-exploiting layer, and tooling to analyze your own play. Built
across several sessions — see the user memory for the full history.

> **New Claude session? Start with [`docs/STATE.md`](docs/STATE.md)** — the LIVE source of truth: current state,
> headline number, workstream, next build. This file = stable conventions; `STATE.md` = what's happening now.
>
> **⟳ KEEP STATE.md CURRENT — standing rule (do this every session).** STATE.md must reflect the LIVE state, not
> history. After any turn that moves a headline number (a measurement), lands a build, or shifts priorities,
> UPDATE STATE.md's top CURRENT section *before ending the turn* — lead with the current frontier, demote
> superseded numbers to a one-line "history" pointer. A fresh context (a human OR Claude after a context summary)
> must start from the truth, never a stale framing. *(This rule exists because a stale doc once led a code-reviewer
> onto an outdated "it's just a heuristic / −160 bb/100" trail — don't let that recur. Same for THIS file's "Honest
> status" below.)*
>
> **Current phase (2026-06-16): NEURAL SELF-PLAY GTO CORE.** The solver-imitation floor is a MEASURED ceiling —
> decision-grade **~−72 bb/100 vs GTO Wizard AIVAT** (n≥2500; the loss is BROAD postflop quality, not a fixable leak;
> run-to-run noise ±8). The resolver fed too-wide ranges also hurts (−72…−76 < Always-Fold −64.6). So we PIVOTED to
> building our OWN **from-scratch neural Deep CFR self-play net** — pure self-play, NO imitation (AlphaGo-Zero logic):
> `strategy/deep_cfr.py` (Leduc-proven via EXACT exploitability), `deep_cfr_hunl.py` (the HUNL game + dual-net
> trainer), `deepcfr_adapter.py` (net→bot, features verified). DCFR+ is the convergence engine (validated: Leduc
> neural 445→338 mbb, still falling). Next run scoped in [`docs/NEXT_RUN_TODO.md`](docs/NEXT_RUN_TODO.md): finer bet
> abstraction + richer features, gated by a paired GTOW A/B. Every other asset (books, CFR papers, PokerBench/Pluribus,
> OpenSpiel, the LLM) connects at the **CLEAN BOUNDARY** — validation/design/exploit, NEVER a training label. vs the
> field we still crush (+31 Slumbot, +300–700 weak). (Resolver/range-tracker = HISTORY now; see STATE.md + NOTES.md.)
>
> **Deferred-precision / open questions:** [`NOTES.md`](NOTES.md) — in-repo log of approximations we ship now and
> should compute exactly later. Add an entry when you ship a heuristic. (NOT a primary onboarding doc — it's a
> caveat list; the live state is STATE.md.)

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
  **MVP#2 — real-time GTO:** `resolver.py` (live TexasSolver river/turn re-solve to terminal, the situation-specific
  GTO path) + `range_tracker.py` (line-aware ranges into the resolver) + `advisor.py` (flop/turn/river solver-
  imitation MLPs = the floor) + `exploit_engine.py`/`opp_model.py` (LCB-gated safe exploit + Dirichlet opponent
  model). The HU benchmark adapter is `benchmark/gtowizard.py` (+ `tools/gtow_run.py`).
  **★ Neural self-play GTO core (current frontier):** `deep_cfr.py` (from-scratch Deep CFR + DCFR+, with the
  `vanilla_cfr` Leduc EXACT-exploitability ground truth), `deep_cfr_hunl.py` (self-contained HUNL game + dual-net
  trainer), `deepcfr_adapter.py` (policy net → bot via `use_deepcfr` / `POKERB_DEEPCFR`).
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
*Lead with the LIVE numbers; older numbers are HISTORY (one-liners at the end). #1 benchmark = the GTO Wizard AIVAT board.*
- **★ CURRENT FRONTIER (2026-06-16) — from-scratch neural Deep CFR self-play GTO core** (`strategy/deep_cfr*.py`),
  built to ESCAPE the imitation ceiling (the floor below is what it replaces). Proven on Leduc (exact exploitability;
  DCFR+ took the neural run 445→338 mbb, still falling); the first HUNL net beats call-station/always-fold/random; the
  GTOW number is pending. PURE self-play — external knowledge (books/papers/PokerBench/Pluribus/OpenSpiel/the LLM) is
  validation/design/exploit ONLY, **never a training label** (that imitation IS the −72 ceiling). Plan: `docs/NEXT_RUN_TODO.md`.
- **What the bot IS:** an **exploit-primary** engine — a solver-grounded **floor** (flop/turn/river solver-imitation
  advisors + analytic defense/sizing) + **real-time TexasSolver re-solving** at high-leverage nodes (`resolver.py`:
  river built+measured, turn built) + a **range tracker** + an **LCB-gated exploit overlay** (fires only on a
  measured, safe leak → floor vs near-GTO). Honest: the floor MATCHES solver bet/check FREQUENCIES but is
  context-collapsed (heuristic + advisors, **not** a solver); the resolver is the path to situation-specific GTO.
- **vs GTO Wizard AI — the #1 benchmark (key ACTIVATED 2026-06-15; AIVAT ~10× variance-cut):** the river resolver,
  measured DECISION-GRADE, is **−72.06 ±6.70** (n=2498) — the earlier −12.9 (n=150) was a LUCKY small sample (the
  small-samples-lie lesson, again). −72 is worse than Always-Fold (−64.6): fed too-wide ranges, the resolver
  confidently plays the WRONG equilibrium in big pots. MVP#1 floor was −33 ±11 but only n=30 (also unreliable); a
  floor baseline at n=2500 is running. **Implication: the range-tracker keystone is a PREREQUISITE — without
  correct ranges the resolver HURTS, it doesn't help.** You can't beat near-GTO regardless; least-loss is the goal.
- **vs Slumbot (exploitable near-GTO):** current MVP **+31 ±46** (2000h) — the floor-fix + exploit + live-learning
  turned the old −102 into a crush. **The thesis in one line: vs the exploitable field we WIN big; vs true near-GTO
  we minimize loss.** The edge = exploiting each opponent's gap to GTO, not out-GTO-ing anyone. Crushes weak
  opponents locally (+300–700 bb/100).
- **★ THE keystone next build (quadruple-triangulated — an external code-review + Opus 4.6 + GPT-5.5 + our own
  notes ALL independently name it #1):** a **Bayesian action-consistent postflop range tracker**. Today's
  `_villain_range`/`_narrow` is "top X% by absolute board strength" (no bluffs/draws/lineage) → poisons the floor's
  facing-bet/bluffcatch math; and `range_tracker` is preflop-line-only → the resolver solves the right board with
  too-wide ranges. Fixing ranges fixes BOTH. Cheap win alongside: wire `preflop_gto.py` (the 88.6% PokerBench
  table) into the HU `bot.py` — verified NOT wired (only 6-max RFI uses it).
- **Measurement discipline (hard-won):** only a GROUNDED signal (solver gap / AIVAT) or a deterministic check
  gates a change — LLM triage + single-rule raw-bb/100 A/B are too noisy (plausible fixes were REVERTED after
  measurement). Paired/duplicate eval cancels card luck; the GTO Wizard board uses AIVAT.
- **History (superseded; context only):** the 2026-06-14 Slumbot **anti-spew saga** (no-exploit floor −526 → −46 →
  −5.4 with the fold-curve exploit) and the **−160 paired vs-TexasSolver-oracle** head-to-head are PRE-GTO-Wizard,
  PRE-resolver numbers (the −160 oracle shared an abstraction + used too-wide ranges → not true GTO). The live truth
  is the GTO Wizard AIVAT line above. Preflop push/fold ≤~10bb = verified Nash; deeper preflop is still heuristic.

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
