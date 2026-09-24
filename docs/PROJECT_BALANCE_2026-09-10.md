# ⚠ PROJECT POST-MORTEM PokerB — critical (closure 2026-09-10, HIGH PRIORITY)

> Read this first before you continue working here or start over. State at closure: branch `poker-core`,
> working tree clean, no running processes. All numbers are documented in `catalogs/MEASUREMENT_CATALOG.md`.

## The hard truth
1. **The goal was not reached.** GTOW Top 5 requires a 95 % lower bound better than ≈ −14.8 bb/100.
   With this architecture that was never within reach.
2. **The only valid GTOW anchor belongs to an old version.** v4 on PRINCE: −21.1 ± 9.4 bb/100 (n=979).
   The current champion v5 was **never** measured against GTO Wizard.
3. **A well-operated frontier LLM plays better than our bot** (GPT-5.5 XHigh −9.2). The top spots, however, are
   held by specialised private bots (−3.1), not LLMs. Our own Claude brain sat at −28.6.
4. **Roughly 237 hours over three months** (13.06.–10.09.2026, 399 commits). A large share went into measuring and
   into correcting measurement errors, not into playing strength.
5. **What retained value is above all what does not compete with specialists:** the trainer.

## What went wrong — causes, not symptoms
- **Wrong architecture for the goal.** Guards around a heuristic engine patch symptoms. The gains do not add
  up (individual measurements ~+53, combined +30.6), every seam costs. Our own documentation predicted the asymptote
  at ≈ −10. The only documented way below it, real-time search with learned value functions
  (DeepStack/ReBeL line), was never started.
- **Measured against the wrong opponent.** Self-play gains (v5 +30.6 against the base in the mirror) demonstrably
  do not transfer to GTOW. Months of gates proved non-regression, not strength.
- **Measurement was more expensive than planned and often wrong.** The real variance coefficient is c = 294, not
  the 214 quoted everywhere → hand budgets almost twice as high. On the last day alone: wrong stack depth (100 instead
  of 200 bb), missing deal marker (rendered two Kaggle measurements worthless), wrong base-rate counter. Each of
  these would have passed as a finding without re-checking.
- **Too many changes of direction.** Qwen brain → Claude brain → GLM SFT/GRPO (regressed to −90) → engine-alone
  → 6-max, tournament, Snowie bridge, trainer, Kaggle. Many strands, few carried through to the anchor.
- **Documentation sprawl.** Four competing entry points (README, START_HIER, _PRINCE_START_HERE, INDEX). CLAUDE.md
  still names a "6-max GTO Qwen brain" as the goal, the product was a HU engine bot. Many "CURRENT" blocks
  are outdated.

## What has real value
- **The trainer**: 6-max, tournament mode with ICM, pre-fold.
  You cannot buy that anywhere.
- **The measurement discipline** (paired decks, A/A null test, pre-registration, 3-runs rule) and the list of
  REFUTED ideas. The most honest part of the project.
- **The two catalogues:** `catalogs/MODULE_CATALOG.md` (what each part does) and `catalogs/MEASUREMENT_CATALOG.md` (whether it works).

## The strategic lesson
A free frontier LLM is today a strong and rising bar. A home-built bot is only worth it if it measurably
beats that bar, and knowing that costs more than building. AI accelerates building far more than
knowing. For a non-specialist the leverage lies where one's own knowledge makes the difference, not in
racing specialists on a benchmark.

## If someone continues — only in this order
1. **Anchor v5 against GTOW**, with a verified fingerprint and ≥ 5,400 hands for SE ≈ 4. Without this number, every
   further step is speculation.
2. **Before every build, check whether it can beat a frontier LLM against GTOW.** If not, do not build it.
3. **If playing strength is the goal:** the known architecture (real-time search + learned values), no further guards.

Open individual items are in the pause state of `docs/STATE.md` (among others v10: 43 % errors on plan activations).

## Backup — state at closure
- **Addendum 2026-09-24:** The repo was **published as `aeneassoft/QuantPlay`** (default branch
  `poker-core`, previously local only). Since then the trainer runs without a server in the visitor's browser at
  **https://quantplay.io** (`web/`, Pyodide). Third-party hand histories were removed from the tree beforehand
  (`Desktop/PokerB_ausgelagert_2026-09-10/knowledge_base_hand_histories/`); the Git history still contains them.
- ~~**The branch `poker-core` does NOT exist on GitHub.**~~ (until 2026-09-24) GitHub (`aeneassoft/PokerB`) had
  only `master` (as of 16.06.2026) and `serverless-worker`. Three months of work existed only locally and on the USB stick.
- **Folder size 62 GB:** `data/` 45 GB (of which 37 GB `data/_solve_cache`), `models/` 17 GB (LLM track, parked).
  Code plus Git history are only around 20 MB. No single file over 4 GB.
- **Not in the folder:** the API keys (`Desktop/Secret keys`) as well as the Claude session logs and the
  memory (`~/.claude/projects/C--Users-hampe-Desktop-PokerB`, around 730 MB).
