# PokerB — Heads-Up GTO + Exploitative Poker Bot

A No-Limit Hold'em bot (Heads-Up proof-of-concept, built to extend to 6-max) whose strategy is
grounded in three classic poker books. The books were mined automatically:

- **Claude (Opus 4.8)** read the books and extracted strategy **concepts/heuristics** and the
  **GTO preflop range grids** (vision on the 13×13 charts).
- **OpenAI (gpt-5.1)** formalized and **verified the poker math** (pot odds, EV, MDF, bluff/value
  ratios, implied odds, SPR, combinatorics, …) into runnable, tested Python.

You play against the bot in the browser and a **Claude-backed coach** explains the bot's moves,
reviews yours, and answers questions — all citing the principles pulled from your books.

---

## Quick start

**Easiest:** double-click **`PokerB spielen.bat`** on the Desktop — it starts the server and
opens the browser automatically.

Manual:
```powershell
# 1. (once) install deps
python -m pip install -r requirements.txt

# 2. play in the browser
python -m pokerbot.web.server --open
#   -> http://127.0.0.1:8000
```

Click **Neues Spiel**, then act with the Fold / Check / Call / Bet-Raise (slider + ½/¾/Pot quick
sizes) / All-in buttons. Use the **Coach** panel to get tips.

> The bot decisions are local, instant, and free. Only the **Coach** calls the Claude API
> (on demand). API keys are read from your existing key files under `…/Secret keys/AI/`.

---

## How strong is it / what is "GTO" here?

Honest framing:

- **Preflop** play is genuinely GTO-grounded: a combo-weighted hand-strength model (all-in equity
  vs a random hand for all 169 classes) drives position/spot ranges tuned to HU GTO frequencies,
  plus a Nash-style push/fold zone short-stacked. The book's actual grids are extracted and used by
  the coach as reference.
- **Postflop** play is **equity + math driven**, not a full solver: the bot estimates the
  opponent's range (from preflop action, then narrows it by board texture and aggression), computes
  its equity by Monte-Carlo, and decides via pot odds / MDF / EV with sensible bet-sizing — then
  layers **exploitative** adjustments from an opponent model (over-folders get bluffed more,
  calling stations get value-bet thinner, etc.). This plays strong, principled poker; it is not a
  GTO solver's exact equilibrium postflop.
- **Coaching** is where the books speak directly: the extracted principles + verified math are fed
  to Claude so explanations cite real concepts ("MDF", "polarized 3-bet", "equity realization", …).

**Measured strength:** vs weak/exploitable opponents the bot wins huge (calling station +469,
maniac +524, nit +58 bb/100 — `python -m pokerbot.benchmark.internal`). Vs **Slumbot** (near-GTO,
200bb) it loses about **−170 bb/100** over 400 hands (±81) — expected for heuristic deep-stack
postflop; the next milestone (postflop CFR) targets exactly this gap.

---

## Architecture / file map

```
Information/                     the 3 source PDFs
extraction/                      Phase 1 — mine the books
  extract_text.py                PDF -> per-page text + rendered range-chart images
  chunk.py                       token-bounded chunks
  extract_concepts.py            Claude Opus 4.8 -> strategy concepts (structured)
  parse_ranges.py                regex -> all 348 range captions (frequencies), free
  extract_ranges_vision.py       Claude vision -> the HU 13x13 grids (which hands do what)
  extract_math.py                OpenAI gpt-5.1 -> verified math formulas + Python
  llm.py                         shared Claude/OpenAI helpers (caching, retries, checkpoints)
knowledge_base/                  OUTPUT of Phase 1
  concepts/concepts.json         extracted strategy concepts/heuristics
  ranges/range_captions.json     all range captions (position/vs/stack/action-frequencies)
  ranges/ranges_grids.json       vision-parsed per-hand HU grids
  math/math.json + formulas.py   verified poker math
pokerbot/
  config.py                      paths, API keys, model ids
  engine/                        cards, treys evaluator, Monte-Carlo equity, HU NLHE game
  strategy/                      preflop strength, ranges, opponent model, the Bot brain
    cfr_preflop.py               MCCFR solver for HU push/fold (true Nash) — Pluribus's core algo
    blueprint.py                 loads the CFR push/fold blueprint into the bot
  coach/                         Claude-backed coach (grounded in knowledge_base)
  web/                           FastAPI server + single-page browser UI
  benchmark/slumbot.py           play vs Slumbot's API, measure strength in bb/100
knowledge_base/cfr/              CFR output (preflop_pushfold.json)
docs/pluribus_and_benchmarking.md   Pluribus research + what we reused + benchmarking notes
"PokerB spielen.bat"  (on Desktop)  double-click launcher
tests/                           engine stress test, bot integration, coach + web smoke tests
```

## Re-running the extraction

```powershell
python -m extraction.extract_text
python -m extraction.chunk
python -m extraction.parse_ranges
python -m extraction.extract_concepts          # Claude Opus 4.8  (~$6)
python -m extraction.extract_ranges_vision     # Claude vision    (~$8)
python -m extraction.extract_math              # OpenAI gpt-5.1
```
All are **checkpointed** — re-running resumes and skips finished items.

## Tests

```powershell
python -m tests.test_game        # 300 random hands: chip-conservation + legality
python -m tests.test_bot         # bot-vs-bot legality + AA/72o spot checks
python -m tests.test_coach       # live coach smoke test (calls Claude)
```

## Extending to 6-max (next step)

The engine's betting/showdown core and the range/equity/decision modules are written to generalize.
Going to 6-max mainly needs: multi-seat seating/blinds + side-pots in `engine/game.py`, the full
position set (already in the extracted MPT ranges), and per-position opening ranges in
`strategy/ranges.py`.
