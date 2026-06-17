# PokerB — a Heads-Up & 6-max No-Limit Hold'em GTO + exploit bot

A No-Limit Hold'em bot grounded in five poker books and modern CFR research, with a browser app to play
against it, an opponent-exploiting layer, a Claude-backed coach, and a measurement harness against the
strongest public benchmarks (Slumbot, GTO Wizard AI). The current frontier is **finetune an Open Source LLM to be able to Play 6 Players NLH Poker.

> **New here? Read [`docs/STATE.md`](docs/STATE.md) first** — the LIVE source of truth (current frontier, the
> headline number, the next build). `CLAUDE.md` = stable conventions; this README = the durable overview;
> `STATE.md` = what's happening now. `NOTES.md` = the deferred-precision / open-questions log.

---

## Run it

| What | Command | Launcher |
|---|---|---|
| **6-max vs 5 bots** (the main app) | `python -m pokerbot.web.six_server --open` → http://127.0.0.1:8000 | `PokerB 6max spielen.bat` |
| **Heads-Up + live Claude coach** | `python -m pokerbot.web.server --open` | `PokerB spielen.bat` |

Windows / PowerShell, Python 3.12. `pip install -r requirements.txt`. Run from the project root as
`python -m <module>`. Bot decisions are local, instant, and free; only the **Coach** calls an LLM (on demand).

---

## What it is (honest)

An **exploit-primary** engine — the thesis: *no public bot plays true GTO, so the edge is exploiting each
opponent's gap to GTO, not out-GTO-ing anyone.*

- **The floor** (insurance/least-loss vs near-GTO): solver-imitation advisors (flop/turn/river MLPs that predict
  the solver's bet/check frequency) + analytic defense (pot-odds/MDF) + fold-equity sizing + a CFR push/fold
  blueprint (verified Nash ≤~10bb). Plus real-time **TexasSolver re-solving** at high-leverage river/turn nodes.
- **The exploit overlay**: a Dirichlet per-node opponent model + an LCB-gated safe-exploit engine that fires only
  on a *measured* leak (so it can't hurt vs near-GTO; it just falls back to the floor).
- **The new direction** (the real path to GTO): a **from-scratch neural Deep CFR self-play net** that learns the
  equilibrium with no external knowledge — the floor matches solver *frequencies* but is history-free
  (context-collapsed), which is why it plateaus; self-play is how we escape it.

### Measured strength (the honest numbers; see `STATE.md` for the live frontier)
- **vs the field — we crush:** weak bots **+300…+700 bb/100**; **Slumbot +31 ±46** (exploit-primary, after the
  floor-fix + live-learning turned an old −102 into a win).
- **vs GTO Wizard AI (the #1 benchmark, AIVAT, decision-grade n≥2500) — least-loss:** the floor/resolver is
  **~−72 bb/100**. You cannot beat near-GTO with a history-free imitation floor; minimizing loss is the goal,
  and the neural self-play net is the build aimed at actually closing this gap.
- **Neural core proof:** our from-scratch Deep CFR converges on Leduc (exact exploitability; DCFR+ took the
  neural run 445→338 mbb and still falling); the first HUNL net beats call-station/always-fold/random.

---

## The neural-net direction (current frontier)

Solver imitation is a ceiling (it re-learns the −72 floor). So we build a **pure self-play GTO core** —
Deep CFR (Brown 2019) + DCFR+ (the AAAI-26 convergence engine) — that derives superior strategy from regret
minimization, exactly like AlphaGo **Zero** beat the human-bootstrapped AlphaGo. External knowledge stays at the
clean boundary — **never a training label:**

- **Books / Mathematics of Poker** → a **validation suite** (the toy games have exact GTO the net must
  rediscover: clairvoyance α=1/3, MDF=1/2 at a pot bet) + design bounds. (`docs/math_theory_net_connection.md`)
- **CFR papers** (DCFR+, Supremus, WEVA, Sequential-Equilibrium) → the algorithm + abstraction.
  (`knowledge_base/theory/`, `docs/cfr_papers_digest.md`)
- **PokerBench / Pluribus data** → validation + the exploit overlay (not the GTO core).
- **OpenSpiel** → the information-state-tensor feature representation + the fast-traverse pod path.
- **The trained LLM (Qwen)** → the exploit overlay, not the GTO core.

The next run is scoped in [`docs/NEXT_RUN_TODO.md`](docs/NEXT_RUN_TODO.md): finer bet abstraction
(`0.33/0.5/0.75/1/1.25/2/allin`) + richer features, gated by a paired A/B vs GTO Wizard.

---

## Repository map

| Dir | What | README |
|---|---|---|
| `pokerbot/` | the bot: engine, strategy, neural CFR, coach, web apps, benchmarks, arena | [pokerbot/README.md](pokerbot/README.md) |
| `extraction/` | book-mining + heavy-compute + neural-net training + LLM/OpenAI consults | [extraction/README.md](extraction/README.md) |
| `knowledge_base/` | extracted artifacts: concepts, ranges, math, CFR, theory, postflop nets | [knowledge_base/README.md](knowledge_base/README.md) |
| `docs/` | `STATE.md` (live) + plans, consults, the next-run to-do | [docs/README.md](docs/README.md) |
| `tests/` | engine stress + bot/web smoke tests | [tests/README.md](tests/README.md) |
| `books/`, `Information/` | source PDFs (gitignored — copyrighted) | — |
| `tools/` | external clients (the GTO Wizard researcher client) — gitignored | — |

## Tests
```powershell
python -m tests.test_game        # engine: random hands, chip-conservation + legality
python -m tests.test_table       # N-player side pots
python -m tests.test_bot         # bot legality + spot checks
python -m pokerbot.strategy.cfr_preflop --quick   # CFR push/fold sanity
python -m pokerbot.strategy.deep_cfr --vanilla --iters 1500   # Leduc CFR convergence proof
```

## Config & security
- `pokerbot/config.py`: paths, models (`claude-opus-4-8`, OpenAI auto-resolves to `gpt-5.1`/`gpt-5.5`), API keys.
- **Keys live OUTSIDE the repo** in `C:\Users\hampe\Desktop\Secret keys\` (env-var override). **Never hardcode
  or commit keys.** The `.gitignore` keeps out secrets, `*.pt` nets, `*.pdf` books, `data/`, `tools/`, `models/`.
- Heavy compute (RunPod): `extraction/runpod_run.py` — **always `--kill` when done**.
