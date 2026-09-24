# QuantPlay — a No-Limit Hold'em trainer that runs in your browser, and the bot lab behind it

**Play it now: [quantplay.io](https://quantplay.io)** — no account, no server, nothing to install.
The whole engine (Python, ~1.5 MB) is downloaded once and runs on *your* machine via WebAssembly.
Your hands never leave your browser.

QuantPlay grew out of a three-month attempt to build a heads-up bot that could rank in the top 5 of the
GTO Wizard AI leaderboard. That goal was **not** reached (the honest balance sheet is
[`!_PROJEKT_BILANZ_2026-09-10.md`](!_PROJEKT_BILANZ_2026-09-10.md)). What came out of it, and what this
repository is about, is a 6-max trainer you cannot buy anywhere, a bot with every number measured and
sourced, and a measurement discipline that refuted more ideas than it confirmed.

---

## The trainer

Six modes, all against a league of profiled bots (TAG, LAG, nit, station, maniac, whale …) whose play was
tuned in paired self-play and gated against regressions:

| Mode | What it trains |
|---|---|
| **GTO** | The bots play their baseline straight. Every decision you make is graded against the engine's own line within the hand, with a written explanation. |
| **Exploit** | The bots learn *you* live and attack your leaks. You experience your own exploitability. |
| **Arena** | Rotating, adaptive opponent types across all stack depths. A stress test for staying disciplined. |
| **Punishment** | Five hunters, each built from a leak that was actually measured in human play (sheriff, iso-hammer, value press, trap nit, blind fighter). |
| **Tournament** | A 60-player MTT (6 tables × 10) with rising blinds, antes, table balancing, a final table and a top-9 payout. ICM hints appear once the bubble factor bites. Exact Malmuth-Harville ICM, tested against independent enumeration. |
| **Match** | Same opponents, no coaching, no distractions. Everything is recorded and graded for review afterwards. |

Plus: pre-fold while others still act (the hand is played out in the background and chips move correctly),
hand replay with per-decision grades, an opponent panel showing what the bots have learned about you, a
session analysis after ~100 hands, and a 61-entry poker glossary whose formulas are the audited ones in
[`knowledge_base/math/formulas.py`](knowledge_base/math/formulas.py). The UI is in German.

### Run it locally

```bash
pip install -r requirements.txt
python -m pokerbot.web.six_server --open --trainer
```

Windows / PowerShell, Python 3.12, run from the repo root. The trainer is at `http://127.0.0.1:8000/training`.
Bot decisions are local, instant and free; no LLM is involved in play.

### How the browser version works

[`web/`](web/) turns the *same* trainer into a static site. [`web/build.py`](web/build.py) zips the Python
package plus the knowledge files it reads at runtime; [`web/src/worker.js`](web/src/worker.js) boots
[Pyodide](https://pyodide.org) in a Web Worker, installs five pure-Python wheels and imports the trainer;
[`web/src/bridge.js`](web/src/bridge.js) replaces `fetch('/api/…')` so the unchanged front-end talks to
the worker instead of a server. The route dispatcher is
[`pokerbot/web/browser_bridge.py`](pokerbot/web/browser_bridge.py), which calls the FastAPI endpoints
directly (Pyodide has no threads for the ASGI threadpool). Tested under CPython in
[`tests/test_browser_bridge.py`](tests/test_browser_bridge.py). Measured in Node + Pyodide: import 0.9 s,
five full hands with grading in 0.32 s, slowest single request 0.11 s (tournament mode 0.35 s).

```bash
python web/build.py                          # -> web/dist (deterministic, content-hashed)
python -m http.server 8765 --directory web/dist
```

The site is deployed from `web/` to Vercel. Prince (the heads-up bot) does not take over heads-up pots in
the trainer: measured in 2,992 paired decks it *lost* against the league core, so it is off by default and
the browser build ships without its neural advisors.

---

## The bot, honestly

A heuristic engine (preflop blueprint from CFR push/fold + solver-distilled tables, postflop equity /
pot odds / MDF with solver-frequency advisors) wrapped in a chain of measured guards, a bounded exploit
overlay, and optional real-time re-solving (TexasSolver) at river/turn nodes. Every number below has a
source in [`docs/MESSKATALOG.md`](docs/MESSKATALOG.md); the channel decides what a number means.

| Measurement | Result | Channel / n | Meaning |
|---|---|---|---|
| Heads-up vs **GTO Wizard AI** (the only true GTO anchor) | **−21.1 ± 9.4 bb/100** (v4, AIVAT) | live API, n = 979 | 95 % band ≈ [−39.5, −2.7]. Leaderboard top: private bots at −3.1; best frontier LLM −9.2. The current champion (v5) was never anchored. |
| v5 vs its own base | +30.6 bb/100 | paired self-play mirror | A non-regression bound, **not** strength. Individual guard gains (~+53) did not add up. |
| Tournament risk premium (proportional bubble factor) | **+10.0 ± 5.0 pp ROI** | paired SNG arena, n = 1,500 | The full bubble factor was refuted (−8 pp); the proportional one validated. |
| vs **PokerSnowie** via the screen bridge | +3.2 bb/100 [−37, +44] | 3,114 clean hands of 3,651 | Break-even; the automation errors, not the bot, cost the account. |
| Kaggle Game Arena heads-up (LLM field, 100 bb) | −0.7 ± 2.5 bb/100 vs champion | paired, 150 decks | A cheap volume channel, not a GTO anchor. |
| Opponents who are not GTO | +300 … +700 bb/100 | local benchmark bots | The exploit layer works against exploitable play. |

What was learned the hard way is in the balance sheet: guards around a heuristic engine hit an asymptote
(≈ −10 predicted, never reached); self-play gains do not transfer to a re-solver; the per-hand standard
deviation is 294 bb, so a ±4 bb/100 answer costs ~5,400 hands; and a well-prompted frontier LLM plays
heads-up better than this bot. Ideas that were **refuted** by measurement are listed explicitly in
[`docs/MODULKATALOG.md`](docs/MODULKATALOG.md) — for anyone rebuilding, that is the most valuable part.

---

## Repository map

| Path | What |
|---|---|
| [`pokerbot/engine/`](pokerbot/engine/) | cards, evaluator (treys), Monte-Carlo equity, the N-player table (2–10 seats, side pots) |
| [`pokerbot/strategy/`](pokerbot/strategy/) | preflop blueprint, range tracker, postflop math, advisors, exploit model, ICM, tournament doctrine, the guard chain (`auslese.py`) |
| [`pokerbot/arena/`](pokerbot/arena/) | the opponent league (`sixmax.py`), MTT director, tournament arena |
| [`pokerbot/web/`](pokerbot/web/) | the trainer server (`six_server.py`), the UI (`static/training.html`), the browser bridge |
| [`pokerbot/coach/`](pokerbot/coach/) | decision capture, grading oracle, feedback templates, replay, opponent panel, glossary |
| [`pokerbot/autogym/`](pokerbot/autogym/) | the self-improving loop: math oracle, paired gyms, gates, journal |
| [`pokerbot/benchmark/`](pokerbot/benchmark/) | GTO Wizard, Slumbot, Kaggle Game Arena harnesses, duplicate/paired evaluation |
| [`pokerbot/vision/`](pokerbot/vision/) | the PokerSnowie screen bridge (template matching, state gates, marathon guard) |
| [`knowledge_base/`](knowledge_base/) | extracted, structured knowledge: audited formulas, ranges, concepts, exploit playbook |
| [`docs/`](docs/) | [`STATE.md`](docs/STATE.md) (live state), [`MODULKATALOG.md`](docs/MODULKATALOG.md) (272 modules), [`MESSKATALOG.md`](docs/MESSKATALOG.md) (every measurement), plans and consults |
| [`web/`](web/) | the static browser build of the trainer (quantplay.io) |
| [`tests/`](tests/) | `python -m tests.test_table`, `test_bot`, `test_icm`, `test_tournament`, `test_prefold`, `test_browser_bridge` … |

`CLAUDE.md` holds the working conventions for AI-assisted sessions, including the measurement doctrine
(paired decks, A/A null test must be exactly 0, pre-registered expectations, three-run rule).

## License

**[PolyForm Noncommercial 1.0.0](LICENSE.md).** You may use, copy, modify and share everything here for
noncommercial purposes: personal study, research, teaching, hobby projects, and use by noncommercial
organizations. **Any commercial use — selling, running as a paid service, using the bot, trainer, ranges,
knowledge base or measurements inside a commercial product or to make money at the tables for a business —
requires written permission.** Ask via a GitHub issue or the contact on the organization page. Keep the
[`NOTICE`](NOTICE) file (the `Required Notice:` line) with every copy.

## Status

Closed on 2026-09-10, reopened only to publish. Large artifacts (solver caches, trained nets, LLM
checkpoints, hand histories) are not in the repository. The books the knowledge base was extracted from are
not included either.
