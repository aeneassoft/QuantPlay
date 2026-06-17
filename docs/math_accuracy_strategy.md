# Math-Accuracy Strategy — getting the engine + brain to TRUE-GTO-grade exactness

**Why this matters (user, 2026-06-17):** to get *very* close to GTO, the math must be exact. Poker decisions hinge on
**threshold comparisons** (equity vs pot-odds; the indifference/alpha point; SPR stack-off) where a tiny error FLIPS a
call into a fold. So "math accuracy" is a first-class correctness concern, not a nicety. Sources analysed (by Claude
Opus 4.8): 4 papers in `books/papers/Math Accuracy/` + 3 GitHub repos.

## What the sources say
- **2507.08034 — "Integrating External Tools with LLMs" (Athena, 2025):** tool-integrated LLM hits 83% math / 88%
  science, crushing internal-math GPT-4o (the best baseline 67%/79%). → **VALIDATES our core design**: the LLM must
  NOT do the arithmetic; it orchestrates a tool. Our engine-API + program-of-thought IS this, with the engine as the
  guaranteed-exact calculator. Keep going.
- **fse16 — "Detecting/Fixing Precision-Specific Operations" (Peking U, FSE'16):** floating-point representation error
  is real and can be catastrophic (the Patriot-missile example). → Our engine uses **float** for pot-odds / MDF / EV
  comparisons; at a decision threshold a float error can flip the action. → adopt **exact rational arithmetic** for the
  decision-critical threshold math.
- **2309.03241 — "GPT Can Solve Math Without a Calculator" (MathGLM, 2023):** a 2B model trained on arithmetic reaches
  ~100% multi-digit accuracy (vs GPT-4's 4.3% on >8-digit mult). → Counterpoint: training gives **number-sense**, but
  it's still probabilistic, NOT guaranteed-exact. → use arithmetic/number-sense training to make Qwen PROPOSE correct
  programs (fewer garbage proposals → lower frac_bad), but **the engine stays truth.**
- **2310.20689 — "Learning From Mistakes" (LEMA, 2023):** fine-tuning on mistake→correction pairs (a corrector marks
  the wrong step, explains, fixes) beats CoT-only fine-tuning. → our executor ALREADY flags mistakes (grammar-reject /
  illegal / −EV, `ok=False`); turn those into **correction pairs** for SFT/RL = free error-driven learning.

## Repos — verdict
- **sympy** (pure-Python, pip, exact `Rational` + symbolic): **ADOPT — selectively.** It is slow (orders of magnitude
  vs float) → NEVER in the equity Monte-Carlo hot loop. Use it for (a) a ONE-TIME symbolic **verification** of every
  formula (prove pot_odds/MDF/alpha/EV are algebraically correct), (b) exact-rational evaluation of the cheap
  decision-threshold comparisons, (c) gating the GPT-5.5-generated post-flop calcs.
- **numbat** (Rust CLI, units-first): **REJECT** — not a Python library, units aren't our problem.
- **Qalculate / libqalculate** (C++ desktop calc, no Python bindings): **REJECT** — not embeddable; we already own the
  engine.

## The strategy — 5 layers (most are $0)
1. **Engine = truth (DONE).** Program-of-thought: the LLM emits a program, the engine computes. Validated by Athena.
   Reinforced by the grammar gate (`dsl_grammar`) + `run_program(strict)` + the EV-truth filter.
2. **Exactness upgrade (NEW — fse16 + sympy).** A targeted pass: the DECISION-CRITICAL threshold functions
   (`required_equity`, `pot_odds`, `mdf`, alpha, EV-comparisons, indifference, SPR stack-off) use `fractions.Fraction`
   (exact, stdlib, fast enough for single comparisons) so a float epsilon never flips a call/fold. **Float STAYS** for
   the MC equity estimate (it's a sampled probability, not a threshold — exactness there is meaningless). Margin-aware
   comparisons (already in the EV-filter) further guard the boundary.
3. **Symbolic verification (NEW — sympy).** A `tests/test_formulas_symbolic.py`: for each formula, assert sympy proves
   the closed form (e.g. `mdf = 1 - bet/(bet+pot)` simplifies to the implementation; alpha + MDF = 1). One-time, offline,
   catches a wrong formula before it ever ships.
4. **Number-sense training (MathGLM).** Keep expanding the **verified-CoT** math examples in the DSL dataset (math.json
   + the GPT-5.5 `postflop_calc.json`) so Qwen proposes arithmetically-sane programs. Secondary lever; the engine is
   primary.
5. **Mistake-correction pairs (LEMA).** Extend `pipeline/frontier_loop.py`: when `run_program` returns `ok=False`
   (grammar/illegal/−EV), emit a `(bad_program, engine_diagnosis, corrected_program)` triple (Claude writes the fix,
   the engine verifies it) → an SFT/RL correction-data stream. Error-driven learning, gated by the engine.

**Binding rule (the gate):** every generated or learned calculation enters the dataset ONLY after an engine/sympy
verification passes (`verify_expr == verify_value`). This is the EV-truth filter extended to pure math — frontier =
prior, engine = truth.

## Concrete next actions (priority order; all $0 except noted)
- **A.** Gate + integrate the GPT-5.5 `postflop_calc.json` (running): run each `verify_expr` against its `python_function`;
  sympy-double-check the algebra; keep only the passers → `knowledge_base/math/` + thin wrappers in `brain/api.py` + the
  DSL dataset (`from_math`-style). This deepens the brain's post-flop tooling.
- **B.** Exactness pass (layer 2) on the threshold functions in `api.py` / `formulas.py` (Fraction).
- **C.** `tests/test_formulas_symbolic.py` (layer 3, sympy).
- **D.** Mistake-correction generation in `frontier_loop` (layer 5).
- **E.** Add `sympy` to `requirements.txt` (pure-Python, safe); keep it OUT of the equity hot path.

## Caveats
- sympy is SLOW → verification/threshold-only, never per-MC-sample. Float is correct for sampled probabilities.
- Exactness only changes outcomes AT a threshold; elsewhere it's cosmetic. Target the pass, don't rewrite the engine.
- MathGLM-style arithmetic training is a *secondary* lever (helps proposals, not guarantees) — do not let it tempt us
  back toward "the LLM does the math" (that's the −10/−30 ceiling).
