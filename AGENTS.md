# AGENTS.md — how AI agents should work in this repository

QuantPlay is a 6-max No-Limit Hold'em trainer (runs in the browser at https://quantplay.io) and the measured
poker-bot laboratory behind it. This file is the short, tool-neutral entry point for coding agents; `CLAUDE.md`
holds the full working conventions and the project's doctrine; `llms.txt` is the machine-readable map.

## Read in this order
1. `README.md` — what exists, the honest results table, the repository map.
2. `docs/PROJECT_BALANCE_2026-09-10.md` — why the original goal (GTO Wizard top 5) was missed and what has value.
3. `docs/STATE.md` — the living state, newest block first.
4. `docs/catalogs/MODULE_CATALOG.md` — every module (272) with purpose, interface, dependencies, measurement
   status and pitfall, including modules that were REFUTED by measurement.
5. `docs/catalogs/MEASUREMENT_CATALOG.md` — every real measurement with channel, n, verdict and source.
6. `CLAUDE.md` — doctrine, forbidden zones, measurement discipline, escalation rules.

## Run and test
```bash
pip install -r requirements.txt
python -m pokerbot.web.six_server --trainer          # local trainer at http://127.0.0.1:8000/training
python -m tests.test_browser_bridge                  # the serverless dispatcher used by the browser build
python -m tests.test_prefold; python -m tests.test_tournament_mode; python -m tests.test_table; python -m tests.test_icm
python web/build.py                                  # rebuild the static site (web/dist) after trainer changes
```
Windows / Python 3.12; always run from the repo root as `python -m <module>`.

## Drive the trainer without HTTP
`pokerbot.web.browser_bridge.dispatch(method, path, body_json)` returns `{"status", "body"}` for every route of
`pokerbot/web/six_server.py` (`/api/new_session`, `/api/action`, `/api/step`, `/api/feedback/last`,
`/api/replay/last`, `/api/opponent_panel`, `/api/report`, `/api/analyze`, `/api/glossary`). This is what the
browser build and the tests use; it needs no server and no threads.

## Rules that are not negotiable
- **Numbers only with a source** (`file:line` in the catalogues). The measurement channel decides what a number
  means: a self-play mirror result is a non-regression bound, not strength; only the GTO Wizard AIVAT anchor is
  strength. Per-hand SD is 294 bb, so a ±4 bb/100 answer needs ~5,400 hands.
- **Strategy code** (`pokerbot/strategy/*`) changes only as guard wrappers plus a paired A/B gate (A/A null test
  must be exactly 0). Formulas in `knowledge_base/math/` are immutable.
- **Never commit** API keys, third-party hand histories, or files about real persons. Keys live outside the
  repo; `pokerbot/config.py` reads them from the environment or the operator's key directory.
- **Do not rewrite git history.** Do not push, publish or deploy without the operator's explicit go.
- The trainer's user-facing text is English; code comments may still be German in places.

## Where things are
| Path | What |
|---|---|
| `pokerbot/engine`, `strategy`, `arena`, `coach`, `web`, `autogym`, `benchmark`, `brain`, `vision` | the Python package (see README map) |
| `knowledge_base/` | audited formulas, ranges, concepts, exploit playbook (structured, extracted from books) |
| `web/` | static browser build: `build.py`, `src/bridge.js`, `src/worker.js`, `wheels/`, `site/`, committed `dist/` |
| `docs/catalogs`, `docs/doctrine`, `docs/plans`, `docs/reports`, `docs/consults`, `docs/archive` | catalogues, doctrine, plans, reports, LLM consult transcripts, history |
| `research/` | one-off measurement and mining scripts (`python -m research.<name>`) |
| `tests/` | `python -m tests.<name>` |
| `scripts/` | Windows launchers |

License: PolyForm Noncommercial 1.0.0 (`LICENSE.md`, `NOTICE`). Commercial use needs written permission from
Leonhard Hampe.
