# scripts/ — Windows launchers

Double-click from anywhere (they `cd` to the repo root themselves). Requires Python 3.12 on PATH and
`pip install -r requirements.txt` once.

| Launcher | What it starts | URL |
|---|---|---|
| `play_trainer.bat` | the 6-max trainer with coaching (GTO / Exploit / Arena / Tournament / Match) | http://127.0.0.1:8000/training |
| `play_6max.bat` | the plain 6-max table vs 5 bots, 2–10 seats via `?players=N` | http://127.0.0.1:8000 |
| `play_headsup.bat` | heads-up vs the strongest bot (Prince, AUSLESE chain, resolver on) with an engine advisor | http://127.0.0.1:8001 |

No install at all: the trainer also runs at **https://quantplay.io** (same code, in your browser).
