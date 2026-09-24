# Contributing

Thanks for looking. The project is closed as a race for the GTO Wizard leaderboard (read
`docs/PROJECT_BALANCE_2026-09-10.md` first), but the trainer is alive and the measurement discipline is worth
keeping. Issues and pull requests are welcome for:

- trainer bugs, UI/UX, translations, accessibility, mobile layout;
- new opponent profiles or trainer modes **with a paired self-play gate** (see `docs/plans/AUTOGYM_PLAN.md`);
- measurements against GTO Wizard AI, Slumbot or the Kaggle Game Arena — with channel, n and raw logs;
- documentation fixes (most docs were translated from German; wording fixes are appreciated).

Rules of the house (details in `CLAUDE.md` and `AGENTS.md`):
1. Every number needs a source. Add measurements to `docs/catalogs/MEASUREMENT_CATALOG.md`.
2. Strategy changes ship as guard wrappers behind a paired A/B gate; the A/A null test must be exactly 0.
3. No keys, no third-party hand histories, no files about real persons.
4. `python -m tests.test_browser_bridge`, `test_prefold`, `test_tournament_mode`, `test_table`, `test_icm` must pass;
   run `python web/build.py` if you touched anything the trainer imports (the built `web/dist` is committed).

Commercial use of any part of the repository needs written permission (PolyForm Noncommercial 1.0.0, see
`LICENSE.md` and `NOTICE`). By contributing you agree that your contribution is licensed the same way.
