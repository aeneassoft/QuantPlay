# tests/

Engine stress tests + bot/web smoke tests. Run from the project root. See the root [README](../README.md).

```powershell
python -m tests.test_game        # HU engine: random hands, chip-conservation + legality invariants
python -m tests.test_table       # N-player engine: side pots
python -m tests.test_bot         # bot-vs-bot legality + AA/72o spot checks
python -m tests.test_range_tracker   # the postflop range tracker
```

Self-contained sanity checks also live next to the code they test, e.g.:
```powershell
python -m pokerbot.strategy.cfr_preflop --quick          # CFR push/fold Nash sanity
python -m pokerbot.strategy.deep_cfr --vanilla --iters 1500   # Leduc CFR exact-exploitability convergence
python -m pokerbot.strategy.deep_cfr_hunl --selftest      # the HUNL game: chip-conservation + showdown
python -m pokerbot.strategy.deepcfr_adapter               # net→bot feature reconstruction self-check
```
