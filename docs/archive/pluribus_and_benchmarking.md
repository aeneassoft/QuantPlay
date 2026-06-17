# Pluribus, CFR, and benchmarking — what we used and why

This documents the research you asked for: what Pluribus is, what's reusable, how non-LLM AI
fits, and how we measure our bot's real strength.

## Pluribus (Brown & Sandholm, 2019, *Science*)
First AI to beat elite professionals at **6-max** No-Limit Hold'em (the hard, multiplayer
game). Two-part design:
1. **Blueprint via MCCFR self-play** — Monte-Carlo Counterfactual Regret Minimization on an
   *abstracted* game (bucketed cards + a few discrete bet sizes). No human data. Trained for
   roughly **$150** of cloud compute.
2. **Real-time depth-limited search** — at decision time it re-solves the current subgame to a
   limited depth, evaluating leaves by letting each player pick among ~4 precomputed
   continuation strategies. Ran on **2 CPUs** at play time (no GPU).

Lessons: CFR + abstraction makes NLHE tractable; cheap blueprint + real-time search ≫ blueprint
alone; self-play beats imitating humans.

## Open-source "amateur Pluribus" projects
- **`fedden/poker_ai`** → mirrored as **`keithlee96/pluribus-poker-AI`** (GPL): MCCFR +
  clustering card abstraction + a poker engine. Research-grade, incomplete.
- **`zanussbaum/pluribus`**: equilibrium finding + depth-limited solving.
- **`conorarmstrong/pluribus`**.

Reality check: none is a turnkey superhuman bot — they're educational MCCFR scaffolds. The
**algorithms** are the valuable, reusable part, not a droppable artifact.

## What we actually applied (this is the important part)
- **MCCFR, implemented and verified** — `pokerbot/strategy/cfr_preflop.py`. Chance-sampled CFR
  solving the HU **push/fold** game for stacks 2–20bb. The output matches published **Nash
  push/fold** charts almost exactly (10bb: SB jam ≈55%, BB call ≈44%; AA/KQo ≈100%, 72o ≈0%).
  It **replaced our ad-hoc short-stack thresholds** with a true equilibrium →
  `knowledge_base/cfr/preflop_pushfold.json`. This is the same core algorithm Pluribus uses,
  applied to the slice of the game that is small enough to solve exactly *and verify*.
- **Pluribus-shaped architecture** — the CFR push/fold table is our "blueprint"; postflop we make
  **real-time decisions** from Monte-Carlo equity vs a board-narrowed range + pot-odds/MDF/EV.
  That real-time step is a lightweight stand-in for Pluribus's depth-limited subgame search.

## What's out of scope for one session (this is where RunPod's $50 would go)
A full **postflop CFR blueprint** (deep-stack, card + bet-size abstraction) is exactly the part
that takes hours-to-days of compute. Path: port abstraction + MCCFR to the full tree, train
offline (RunPod), then add real-time subgame solving. This is the documented next milestone — I
deliberately did **not** burn your RunPod credit, because everything achievable now runs locally.

## Role of non-LLM AI (your question)
- **CFR / solvers** → true GTO (we did push/fold; postflop is the future step).
- **Exact equity / combinatorics / ICM** → already in the engine (`engine/equity.py`, the
  verified `knowledge_base/math/formulas.py`).
- **A small opponent classifier** (statistical) → could sharpen the exploit layer.
- **LLMs (Claude/OpenAI)** are *not* for real-time GTO math; they shine at **reading the books**,
  **coaching**, and **explanation** — which is exactly how we used them.

## Hand-history databases
Open sets exist (ACPC competition logs; Pluribus's released hands). They're best for
**population/exploit priors**, *not* GTO calibration — pros aren't GTO; a solver is the yardstick.
Our **live opponent model** already adapts to a specific opponent, so we don't hard-depend on a
static DB. Mining one for a population prior is a clean future add.

## Benchmarking — measuring strength honestly
- **Slumbot public API** — `pokerbot/benchmark/slumbot.py`. Slumbot is a strong, near-GTO HU bot
  you can play over HTTP (200bb, 50/100). We reconstruct each decision from its action string,
  let our bot decide, and report **bb/100** over N hands.
- HU NLHE variance is enormous, so only multi-hundred-hand samples mean anything, and even those
  have wide error bars. **Measured: −170 bb/100 over 400 hands (±81 stderr) vs Slumbot** — a clear
  loss to a near-GTO bot (expected for heuristic deep-stack postflop), while the same bot beats
  weak/exploitable opponents by +400 to +500 bb/100 locally. The gap is the postflop solver gap.

Run it yourself:  `python -m pokerbot.benchmark.slumbot --hands 500`
