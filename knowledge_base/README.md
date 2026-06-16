# knowledge_base/ — extracted artifacts

OUTPUT of the `extraction/` pipelines: what the bot is grounded in. See the root
[README](../README.md). Large nets (`*.pt`) are gitignored (regenerable); the JSON artifacts are committed.

| Dir | What |
|---|---|
| `concepts/` | strategy concepts/heuristics mined from the books (Claude) |
| `ranges/` | preflop range grids + captions (text + chart vision); `cfr/preflop_pushfold.json` = Nash blueprint |
| `math/` | verified poker math (`mathematics_of_poker.json`, `formulas.py`) — incl. the toy-game GTO |
| `postflop/` | solver-imitation advisor nets (`*.pt`, gitignored) + texture frequencies + the playbook |
| `theory/` | distilled research papers (Supremus, Deep DCFR+, WEVA, Sequential-Equilibrium, …) — the algorithm/architecture source |
| `exploit/` | learned opponent leaks (Slumbot fold curve, the exploit playbook) |
| `hand_histories/` | 10k Pluribus hands (evaluation distribution + exploit-model data) |
