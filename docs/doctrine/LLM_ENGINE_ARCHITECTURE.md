# LLM ↔ Engine — The Switch System (PRIMARY embedding direction)

> **Design direction (2026-06-18).** How the LLM-brain should be embedded in the engine. Distilled from a design
> discussion (the user's insight). This **supersedes the monolithic program-of-thought as the *primary* embedding for a
> small/weak LLM** — keep it prominent: every future LLM-integration decision should be checked against this.

## The core principle

The LLM and the engine have **opposite strengths**:
- **LLM** = reduce / **generalize** fuzzy, high-dimensional data → a *small* choice. (The user's words: *"able to
  simplify and generalize a lot of data."*) It is NOT good at exact computation.
- **Engine** = exact math, legality, GTO solving, a portfolio of verifiable functions. It cannot do fuzzy judgment.

> **The LLM never computes. The engine never guesses.** The LLM condenses uncertainty into a small choice; the engine
> turns that choice into an exact action. The final decisions are always **(action, bet-size)**.

## Why a "switch system" — the 8B constraint

We use an **8B model first**: low context budget, degrades with too much context, weak vs human intelligence — but a
**functioning neural net if adapted for our narrow tasks**. So we do NOT ask it for a full decision over the whole spot
(that is the hardest possible task — and exactly why the monolithic program-of-thought hit **frac_bad ~0.5**). Instead:

**Decompose the decision into many small switches.** The **engine reduces the data INTO each switch** (curated, minimal
context); the **LLM generalizes WITHIN it**. The 8B never sees the complete overview — it operates competent small
switches, each leveraging its generalization on a digestible slice. Two compression levels: engine condenses *for* the
LLM, LLM condenses *inside* the switch.

## The 4 principles

1. **Division by strength.** A switch belongs to the LLM *only if* generalization beats a heuristic. Otherwise use the
   rule — it saves latency and risk.
2. **Authority = INVERSE to engine competence (per spot, not global).** This answers *"how far do we constrain the AI?"*
   - Where the engine computes exactly (HU postflop, solver) → the LLM only **advises** (abstraction / read); the engine
     **decides**. Tightly constrained.
   - Where the engine *cannot* (multiway 6-max, no solver) → the LLM **decides**, because its generalization is the best
     available. Loosely constrained.
   → The constraint level is automatic, per-spot. The LLM gets authority exactly where we otherwise have nothing better.
3. **Decomposition for the 8B.** As above — engine reduces in, LLM generalizes within. Keeps every LLM call inside the
   8B's competence window.
4. **Training tractability.** Small switches = narrow, **engine-labelable, individually verifiable** tasks → far more
   trainable than full valid+good programs. This **explains why the monolithic PoT training failed** (frac_bad 0.5 — we
   gave the 8B the whole exam) and is the path forward (per-switch labels, denser/scoped reward — likely also the way to
   make RL grip).

## The switch system (a decision = a short pipeline; signals flow BOTH ways)

| Switch | Engine curates IN | LLM signal OUT | Owner | Why |
|---|---|---|---|---|
| 1 · Spot-type / plan | texture tags, SPR, street, hand-class, line summary | value / bluff / pot-control / give-up | **LLM** | generalize the gestalt |
| 2 · Read | villain last actions + 2-3 stats + pos/n_active | {fold-lean, aggro-lean, confidence} | **LLM** | read from *few* samples (8B strength) |
| 3 · **Abstraction** | spot-type + texture | which 2-3 bet-sizes / lines to solve | **LLM** | generalize "what is relevant here" |
| 4 · Solve | board + ranges + the LLM's abstraction | exact GTO mix | **Engine** | exact math |
| 5 · Commit / deviation | GTO mix + read | final (action, size): follow GTO *or* bounded deviation | **LLM↔Engine** (principle 2) | inverse to coverage |
| 6 · Legalize | (action, size) | legal (action, chips) | **Engine** | legality = truth |

Switches 1-3 (+ sometimes 5) = LLM generalization; 4 + 6 = engine exactness. **Keep the loop short** (1-2 LLM calls per
decision — latency, see caveats).

## Flagship switch: the LLM picks the solver's abstraction (#3)

The highest-value LLM job and the cleanest realization of "LLM generalizes → engine computes":
- The solver's biggest cost *and* quality lever is the **bet-size abstraction** (which sizes the tree contains; currently
  fixed/lean).
- The LLM generalizes the spot → picks the 2-3 sizes that matter *here* → the engine solves a **small, tailored** tree →
  faster AND better (relevant sizes) than any fixed abstraction.
- Tiny LLM output (2-3 categories) = perfect for the 8B; label = the sizes the full solve actually uses.

## Caveats (honest)

- **Latency:** each LLM switch is an 8B call (~seconds). Only 1-2 *high-value* switches go to the LLM; the rest are
  engine rules. Not everything to the LLM.
- **Each switch must earn its place** (beat the engine-rule baseline empirically; else it is just latency + risk).
- **Glue complexity** is real — build switches incrementally, gate each one.
- The 8B stays weak: this architecture **maximizes value per IQ-point**, it does not conjure intelligence.

## Status / relation to the codebase (2026-06-18)

- `pokerbot/strategy/opp_model.py` + `api.opponent_read` + `spot.villain_fold/aggro` = a first **switch #2 (read)** already built.
- `api.solve_node` (the solver-search) = the **engine compute (switch #4)** — but currently **CRUDE**: measured
  **−74.9 bb/100 AIVAT vs GTO Wizard (100 hands)** with fixed non-line-aware ranges + a lean tree. **The engine scaffold
  needs fidelity (line-aware ranges = real subgame solving) BEFORE the LLM layer pays off** — a −75 engine cannot be
  rescued by an LLM overlay.
- Current `QwenPolicy` (program-of-thought) = the monolithic embedding (frac_bad 0.5) — **to be superseded by switches**.
- **Path:** (1) diagnose the solver's −75 (preflop vs postflop leak; bug vs fundamental), (2) fix engine fidelity,
  (3) THEN build switches incrementally — start with #3 (abstraction) or #2 (read), gate each empirically.

See also: [`STATE.md`](../STATE.md), the pro/con matrix of the 6 embedding architectures (session transcript 2026-06-18),
and `pokerbot/brain/{api,policy,executor,format_spot}.py`.
