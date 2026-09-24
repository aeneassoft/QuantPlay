# PokerB — What you got & how to get started

> ⚠️ **Historical onboarding (first version).** Current state: [README.md](../../README.md) + [docs/STATE.md](../STATE.md).
> The bot has advanced far since — exploit MVP, 6-max, GTO Wizard benchmark, and now a **home-built
> neural self-play net** (Deep CFR). The numbers below (−170 vs Slumbot etc.) are OUTDATED. Below = how it
> was originally delivered, for reference.

## 🎮 Play right away
**Double-click `PokerB spielen.bat`** (on the Desktop). The server starts and the
browser opens automatically at http://127.0.0.1:8000 — then click "New game".
On the right is the **coach panel**: "Explain the bot's move", "Grade my move", or ask freely.

## What is inside
**Your 3 books — evaluated automatically:**
- **813 strategy concepts** (Claude Opus 4.8, structured with actionable rules)
- **348 range captions** + **66 heads-up GTO grids** from the 13×13 charts (Claude Vision)
- **13 math formulas** (OpenAI gpt-5.1), of which **12 verified by code execution**

**The bot:**
- **Engine**: cards, hand evaluator, Monte Carlo equity, full HU NLHE logic (300-hand stress test passed)
- **Decision engine**: preflop ranges + postflop (opponent range → equity → pot odds/MDF/EV) + **exploit layer** (learns your tendencies)
- **CFR solver** (`cfr_preflop.py`) — **Pluribus' core algorithm (MCCFR)**: solves the push/fold game to a **true Nash equilibrium** (verified against known charts) and drives the short-stack play
- **Coach** (Claude): explains/grades/coaches in German, **with quotes from your books**

## How good is it? (honestly)
- **Preflop**: GTO-founded — push/fold is **true CFR Nash**; deep stacks equity-grounded.
- **Postflop**: strongly **heuristic** (equity + pot odds + MDF + exploit) — *not* a full solver. Plays by principle, but is no superhuman bot postflop.
- **Against weak opponents** (local benchmark, 300 hands): calling station **+469 bb/100**, maniac **+524 bb/100**, nit **+58 bb/100** — the exploit layer clearly beats exploitable players.
- **Slumbot benchmark** (strong, near-GTO HU bot, 200bb, 400 hands): **−170 bb/100 (±81)** — we lose clearly against a top bot. Expected: 200bb deep + purely heuristic postflop is the hardest test. This is exactly where the future postflop CFR comes in. (High variance; true rate roughly −150…−200.)
- **Coach**: excellent for learning — this is where your book knowledge speaks most directly.

## Your questions — answered briefly
- **Pluribus**: researched & applied. We use its core (MCCFR) for the solvable/verifiable piece (push/fold). Details: `docs/pluribus_and_benchmarking.md`.
- **Pro hand DBs**: useful as an exploit *population* prior, not for GTO. Our live opponent model adapts anyway. Open datasets (ACPC, Pluribus hands) as a future addition.
- **Benchmark against an established bot**: ✅ done via the **Slumbot API** (`pokerbot/benchmark/slumbot.py`).
- **RunPod ($50)**: **deliberately not spent** — everything buildable right now runs locally. RunPod pays off for a *days-long* postflop CFR blueprint training (the next big step).
- **Role of non-LLM AI**: CFR/solver = true GTO; equity/combinatorics/ICM = math core; LLMs = reading books + coaching. Combined exactly like that.

## Next steps (optional, if you want to go on)
1. **Postflop CFR blueprint** (abstracted, trained offline — this is where RunPod comes in) + real-time subgame solving → true GTO postflop too.
2. **6-max** (engine/strategy are prepared for it).
3. **Hand-DB exploit prior** from open datasets.

## Check for yourself
```powershell
python -m tests.test_game                 # engine: 300 hands, all invariants
python -m tests.test_bot                  # bot: legality + spot checks
python -m pokerbot.strategy.cfr_preflop --quick   # CFR push/fold sanity
python -m pokerbot.benchmark.slumbot --hands 500  # benchmark against Slumbot
```
