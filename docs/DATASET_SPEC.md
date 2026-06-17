# The "Common Language" — Dataset & Reasoning Format for the Qwen 6-max Brain (2026-06-17)

> Answers the user's core idea: bridge **Mathematics → Programming language → human Poker-theory language** into ONE
> formal representation Qwen works with natively, so Qwen "thinks" compute-efficiently + EXACTLY + verifiably.
> Companion to [`QWEN_6MAX_PLAN.md`](QWEN_6MAX_PLAN.md). This is the spec the data pipeline must produce flawlessly.

## The key decision: Program-of-Thought, with OUR ENGINE as the typed primitive library

A poker decision is mostly **computation over well-defined primitives** (equity, pot-odds, MDF, ranges, frequencies,
blockers, legality) + a thin layer of **judgment** (reads, exploitation, multiway meta). So the right common language
is **Python "decision programs"**: Qwen emits code that calls our engine, the code EXECUTES, and the action is the
*result of running it* — not free-text arithmetic the LLM can get wrong.

Why this is the right bridge (and why it harmonizes with Qwen specifically):
- **Math layer** = `knowledge_base/math/formulas.py` + the Mathematics-of-Poker extraction → exact, unit-tested
  primitive functions (pot_odds, mdf, ev_call, combos, blocker_count, spr...). No LLM arithmetic = kills the #1 LLM
  poker weakness (frequency/EV mistakes).
- **Code layer** = our `pokerbot` engine exposed as a clean, typed API = the lingua franca Qwen reasons in. **This is
  literally "our bot as the scaffold"** — the bot becomes the standard library the LLM imports.
- **Language layer** = the spot description (natural language) + the concepts (as docstrings/comments) + the brief NL
  rationale around the code. Human poker theory stays, but anchored to executable primitives.
- **Qwen-native + fast:** Qwen (esp. Qwen-Coder lineage) is S-tier at code; "program-of-thought" is higher
  throughput-per-token + deterministic + **verifiable** (run it → exact reward, ideal for RL).

HONEST scope: **hybrid, not code-ONLY.** Code for the computable parts (EV/freq/legality/blockers); natural language
for genuine judgment (reads, exploit sizing, multiway). "Qwen works only in code" is too strong — the computable core
is code, the judgment is language, fused in one program.

## The engine-as-API (the primitive library Qwen calls)
A stable, typed facade `pokerbot/brain/api.py` (NEW, thin wrappers over existing code — no logic duplication):
```python
spot = parse_spot(prompt)                      # canonical spot -> typed Spot object
eq   = equity_vs_range(spot.hero, villain_range, spot.board)      # engine/equity.py
po   = pot_odds(spot.to_call, spot.pot)                            # math/formulas.py
mdf  = minimum_defense_frequency(spot.bet, spot.pot)               # math/formulas.py
bp   = blueprint_action(spot)                  # preflop_blueprint.py -> mixed strategy
vr   = tracked_range(spot)                      # range_tracker.py -> villain combo weights
freq = solver_frequency(spot)                   # postflop tables -> action distribution (CPU-extended!)
exp  = exploit_adjust(spot, villain_stats)      # exploit model -> bounded nudge
act  = decide(...)                              # compose -> {action, size_bb, freq}
```
Every function is deterministic + unit-tested → the "decision program" is **executable + checkable**.

## The training example schema (what the pipeline emits)
JSONL, one object per decision. The COMPLETION is a decision-program (PoT) + NL rationale + the executed action:
```json
{
  "source": "pokerbench|ranges|postflop|exploit|distill|selfplay",
  "spot": "<canonical format_spot string — byte-identical to live inference>",
  "completion": "# reasoning: BTN range-advantage on dry K72r; we hold a blocker.\neq = equity_vs_range(hero, bb_call_range, board)   # 0.61\npo = pot_odds(to_call=4, pot=6)                    # 0.40\n# eq > po and we deny equity -> value bet, solver-mixed\nfreq = solver_frequency(spot)                      # {bet_75:0.7, check:0.3}\nACTION: raise 4",
  "action": {"action": "raise", "size_bb": 4.0},
  "meta": {"executed_freq": {"bet_75":0.7,"check":0.3}, "ground_truth": "pokerbench", "ev_checked": true}
}
```
- **SFT** trains Qwen to PRODUCE such programs (`train_on_inputs=false`). **RL** rewards the EXECUTED program's
  realized EV (the engine runs it → exact, verifiable reward — the program-of-thought makes RL clean).
- Inference: Qwen emits the program → we EXECUTE it in a sandbox calling the real engine → the action. (Math is done
  by code, not the LLM → exact + fast.)

## Source → format mapping (the flawless pipeline)
| Source | becomes | how |
|---|---|---|
| `knowledge_base/math` + formulas.py | the PRIMITIVE LIBRARY + math-CoT examples | wrap as typed funcs; auto-checked tasks |
| PokerBench (6-max, 560k) | spot→decision-program→action | engine writes the program that reaches the known label |
| `knowledge_base/ranges` | preflop spot→`blueprint_action` program | sample hand from cell; program returns the table freq |
| `knowledge_base/postflop` | postflop spot→`solver_frequency` program | soft-label freqs; **CPU-extendable (see below)** |
| `knowledge_base/exploit` (11.5k) | (spot+villain_stats)→`exploit_adjust` program | conditional + anti-overexploit pairs |
| `knowledge_base/concepts` + 6 books | docstrings + NL rationale patterns + distill seeds | NOT raw SFT prose |
| `hand_histories` (10k Pluribus) | masked-future spot→analysis | eval + self-play opponents, low SFT weight |

## Local-CPU dataset extension WHILE RunPod trains (the user's parallelization)
The two heavy jobs run on SEPARATE boxes (per the project's hard CPU≠GPU-coexist lesson):
- **RunPod (1–2× B200, highest class, fully loaded):** Qwen SFT→GRPO. (B200=Blackwell sm_100 → `pip install -U torch
  --index-url .../cu128`, verify `+cu128`; always `--kill`.)
- **Local i9 (CPU):** `extraction/mass_solve.py` keeps generating **finely-calculated frequencies + bet-sizings** →
  these flow into `solver_frequency()` (richer postflop tables) → more `postflop`/`ranges` training examples + better
  RL ground-truth. This is exactly the user's "lokal den Datensatz durch CPU-Rechnungen erweitern" — the frequency/
  bet-sizing dataset that (with the fine-tuned LLM + the engine scaffold) the user named as the win condition.

## Does fine-tuning suffice? (the user's question)
YES, with the three pillars the user named, IF Stage-4 RL is included:
1. a fine-tuned Qwen that **orchestrates the engine via program-of-thought** (not a from-scratch solver),
2. **our bot as the scaffold** (= the engine-API the programs call — literal here),
3. a **dataset of finely-calculated frequencies + bet-sizings** (CPU-extended) the programs look up.
The LLM supplies reasoning/adaptation/exploitation; the engine supplies exact math/GTO/legality; RL/self-play lifts
the composition above the imitation ceiling. Fine-tuning is sufficient **because we are not asking the LLM to BE the
solver — we are asking it to DRIVE one.**

## Pipeline non-negotiables (flawless = these hold)
- ONE `format_spot()` + ONE `api.py`, imported everywhere (SFT == RL == inference == eval). Any drift = silent skew.
- Every emitted program must PARSE + EXECUTE + produce a LEGAL action, else it's a hard-negative.
- Dedup by canonical spot-key + DECONTAMINATE vs the PokerBench test set (log drops).
- Determinism: same spot+seed → same executed result (required for RL reward + eval).
