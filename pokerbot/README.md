# pokerbot/ — the bot

The decision engine, game engines, neural CFR core, coach, web apps, and benchmarks. See the root
[README](../README.md) for the overview and [docs/STATE.md](../docs/STATE.md) for the live state.

| Subpackage | What |
|---|---|
| `engine/` | cards, treys evaluator, Monte-Carlo equity, HU `game.py`, N-player `table.py` (side pots), `sd_eval.py` (short-deck) |
| `strategy/` | the bot brain + all strategy. See below. |
| `arena/` | `sixmax.py` (6-max decision brain), `openpoker.py` (WebSocket client) |
| `coach/` | Claude-backed coach + `meta_coach.py` (engine-agnostic in-loop meta-coach) |
| `analysis/` | session stats + Claude narrative, meta-pattern / tilt analysis |
| `web/` | FastAPI servers + `static/*.html` single-page UIs (`six.html` = 6-max, `index.html` = HU) |
| `benchmark/` | `slumbot.py`, `internal.py`, `beat_them_all.py`, `gtowizard.py` (the #1 benchmark adapter), `floor_ablate.py`, `scorecard.py` |
| `config.py` | paths, models, API keys (read from outside the repo) |

### `strategy/` — the three layers
- **Floor (least-loss vs near-GTO):** `cfr_preflop.py`+`blueprint.py` (Nash push/fold), `preflop_gto.py`
  (PokerBench table), `postflop.py`, `gto_baseline.py`, `advisor.py` (flop/turn/river solver-imitation MLPs),
  `gto_oracle.py` (TexasSolver ground truth).
- **Real-time GTO:** `resolver.py` (live river/turn re-solve) + `range_tracker.py` (line-aware ranges).
- **Exploit overlay:** `opponent.py`, `adaptive.py`, `opp_model.py` (Dirichlet), `exploit_engine.py` (LCB gate).
- **★ Neural self-play GTO core (current frontier):** `deep_cfr.py` (from-scratch Deep CFR + DCFR+, Leduc
  exact-exploitability proof), `deep_cfr_hunl.py` (the HUNL trainer + game), `deepcfr_adapter.py` (net → bot).
- `bot.py` — the HU bot that meshes all of the above (toggles: `use_resolver`, `use_deepcfr`, …).
