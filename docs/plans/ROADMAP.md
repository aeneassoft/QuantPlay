# ROADMAP — how to improve the bot, and the personal Claude coaching path

> Forward-looking companion to [`docs/STATE.md`](../STATE.md) (what's true NOW) and [`CLAUDE.md`](../../CLAUDE.md) (the
> north star). STATE.md is the measured present; this file is the **grounded plan for what's next**. Two tracks:
> **(A) make the bot understand poker as well as possible**, and **(B) build a Claude-API coaching path for a
> human player**. Honest throughout: MEASURED vs PROPOSED is marked explicitly. Last updated **2026-06-29**.

---

## §0 — The starting point (one paragraph, from STATE.md)

There are **two products**: (1) **engine-alone `PokerBot`** — instant + ours, ~−47 AIVAT / ~50% GTOW per-decision =
the playable browser game; (2) **brain+engine** — Claude (or the GLM) drives the engine via program-of-thought,
**near-GTO per-decision (69.9% GTO-score / 6.1 EV-loss)** but ~−40 to −55 AIVAT (a fat cooler tail), slow, $, not ours.
**The brain BYPASSES `bot.py`** (it decides via `executor → api.legalize`), so the engine's `bot.py` heuristics don't
reach it — the brain's quality comes from `api.*` (math/equity/solver) + **what it UNDERSTANDS about the spot**. The
cheap serve/engine levers are largely **exhausted** (made-hand wiring **+40 = the one robust win**; to_call within
noise; solver_freq neutral; value-floor GTO-neutral; river-advisor borderline; ONTREE-snap unproven; anti-spew refuted;
retraining regressed). **RL is walled** at ~engine-level (the opponent-ceiling). So the live frontier is **poker
UNDERSTANDING** — the lever this session opened.

---

## §A — How to improve the BOT further

### A0 — The new lever (BUILT 2026-06-29, EV-UNMEASURED): the consolidated understanding layer
[`pokerbot/brain/understanding.py`](../../pokerbot/brain/understanding.py) — `strategic_read(spot)` fuses the scattered
engine knowledge into ONE coherent, engine-computed NL frame the brain reads on EVERY spot: **geometry** (SPR,
in/out-of-position, pot-odds, required-equity, MDF), **board texture**, the **made-hand read** (`api.hand_rank`),
**initiative** (who has the preflop lead + the range-advantage read), and the **measured GTO heuristics** (river bets
skew small ~0.33×, c-bet small-and-often on dry boards, defend to MDF, jam-discipline). Why it matters: solved spots
are rare (~15–40% solver coverage, 6–76 s each) — on the **other ~60–85% the brain must generalize from first
principles**, and this gives it the full strategic frame without a solve. Gated `POKERB_UNDERSTANDING` (default OFF →
baseline byte-identical, A/B-able); appended in `format_spot`, it reaches **both** brains (Claude + GLM).
- **NEXT (the #1 measurement to run):** A/B `POKERB_UNDERSTANDING=1` vs OFF. Cheap deterministic gate first
  (`research/claude_export.py` → GTOW per-decision GTO-score; does the brain's score rise?), then — if promising —
  a paired AIVAT run (`tools/gtow_run.py --agent_type claude`). **Honest:** the principles are grounded, but the
  *realized-EV* benefit is unproven until measured; it may be neutral (like solver_freq) or help (like made-hand).

### A1 — The measured river leak: the brain OVER-SIZES (the cleanest open finding)
MEASURED 2026-06-29: Claude reflexively bets ~**0.60×pot** on the river; the solver's OOP river bets skew **small**
(over 5 boards × 2 pot-types: **CHECK 58%**, and when it bets the **median is ~0.33×**, 0.25× is the most common).
So ~0.6× is a measured over-size leak vs GTOW's tree.
- **BUILT (gated, EV-unmeasured):** the river-sizing rule in [`claude_brain.py`](../../pokerbot/brain/claude_brain.py)
  (`POKERB_CLAUDE_RIVERSIZE`, default OFF) nudges Claude toward the solver's small skew.
- **The cleaner fix (PROPOSED):** render the **solver's preferred SIZE** in the prompt (the size analog of
  `api.solver_freq`), so the brain sizes like the solver instead of being snapped after the fact. The `POKERB_BRAIN_ONTREE`
  snap (`api.legalize`) is only a *partial* band-aid — it snaps 0.6× → 0.5/0.75×, still bigger than the solver's 0.33×.
- **Validation is cheap + deterministic ($0):** generate with the rule ON vs OFF at one seed → does the bet-size
  distribution move toward ~0.33×? No noisy AIVAT needed for the size-match check.

### A2 — Finish the sizing alignment (the #1 scaffold-gap)
The off-tree/over-size pattern is the biggest measured slice of the −40-vs-−9 gap.
- Extend the ONTREE snap (`api.legalize`) beyond first-in bets ≤2×pot to **raises / 3-bets / overbets** = the full
  sizing fix (currently only flop/turn/river first-in bets are snapped).
- Decide the snap gate from evidence: keep gated-OFF unless a clean signal (per-decision GTO-score lift OR a
  significant AIVAT delta) earns it default-ON. The +16 AIVAT seen once was inconclusive (delta SE ≈ 34).

### A3 — More perception hints (the pattern that works)
The measured pattern: **perception fixes help** (made-hand +40), **strategy nudges don't** (solver_freq neutral). The
understanding layer is mostly perception (SPR, texture, made-hand, MDF) → consistent with the winning pattern. The one
explicit perception hint still worth its own A/B (../NOTES.md): a **draw note** — "flush draw, 9 outs ≈ 35% (2-card)"
(`api.outs_equity` + a draw classifier) — to fix the measured turn under-betting of draws. `understanding._draw_note`
already flags *that* a draw is live; quantifying the outs/equity is the next increment.

### A4 — The measurement floor (the real constraint on cheap levers)
AIVAT at n≤1500 swings ±~20 session-to-session → it only detects BIG effects (made-hand +40 was 2.1σ; +12 and ~0
were below it). **Do NOT A/B small hints at n=500 — you measure noise.** Prefer: (a) the **deterministic** GTOW
per-decision GTO-score (`claude_export.py`, $0, no variance), (b) a **paired/duplicate** harness, or (c) bigger n.
This is why the understanding layer should be graded deterministically first.

### A5 — RL (walled; the major project, deferred)
Lift above the imitation cap needs realized-EV vs a **stronger** in-loop opponent. The self-play league is one shared
~−47 engine (68% identical postflop) and the reward's hero-continuation is hard-`tag` → the reward measures
engine-vs-engine, not GTO; RL already regressed once to −90. The only real RL lever = a **better reward** (a
solver-distilled strong postflop opponent net, or a GTOW-anchored signal) — realistic ceiling ~−45 = engine-level,
NOT the leaderboard. Deferred until the engine/understanding levers are exhausted and the reward problem is solved.

### A6 — Honest ranking of the next moves
1. **Measure the understanding layer** (A0) — deterministic GTOW per-decision first. *The "understand poker maximally" lever; do this next.*
2. **Measure the river-size rule** (A1) — deterministic size-match.
3. **Render the solver's preferred SIZE** in the prompt (A1) — the cleaner sizing fix.
4. **Extend the snap** to raises/overbets (A2).
5. **Draw-equity perception hint** (A3).
6. RL with a better reward (A5) — major, deferred.

---

## §B — The personal Claude coaching path (for a human player)

> **Goal:** Claude reviews a PLAYER's OWN real hands (PokerStars hand-history exports), grounded in our engine (exact
> equity/solver/blueprint + the new understanding layer), and produces honest, personalized, GTO-anchored coaching —
> tuned to the player's known tendencies. This is a NEW product direction; most of the machinery already exists.

### B0 — Why this is buildable now (the reuse map)
Nearly every piece exists; the path is assembly, not new research:
| Need | Reuse |
|---|---|
| Claude API call helpers | `research/llm.py` (`ask_claude` / `claude_json`) |
| A Claude coach (explain move, review vs GTO, free-form Q&A; book-grounded) | `pokerbot/coach/coach.py` + `meta_coach.py` |
| Reconstruct a hand-history into per-decision `Spot`s | `research/study_grade.py` (`build_state` → `spot_from_slumbot` seam) |
| Grade a decision vs ground truth (blueprint / `api.solve_node` / equity-math) | `research/study_grade.py`, `study_analyze.py` |
| The strategic frame for each spot (SPR, MDF, texture, made-hand, principles) | **NEW** `pokerbot/brain/understanding.py::strategic_read` |
| Engine math the coach cites exactly | `pokerbot/brain/api.py` (`equity`, `required_equity`, `solve_node`, `preflop_mix`) |
| Per-decision EV-loss vs GTO (existing loop) | the GTOW Analyzer loop (memory `gtow-analyzer-loop`) + `research/gtow_xray.py` |

### B1 — The architecture (per-session, then cross-session)
1. **Ingest** the player's hands: a hand-history export (PokerStars format is already in the loop; another site's
   format would need one new parser — map its HH to the same internal state the reconstruction seam expects).
2. **Reconstruct** each hero decision → a canonical `Spot` (`study_grade` reconstruction; checksum the pot/to_call so a
   bad parse never silently mis-grades).
3. **Ground each decision:** attach `strategic_read(spot)` (the understanding frame) + the oracle grade (blueprint /
   `solve_node` / equity-math) → the exact GTO action-mix + the user's deviation + the honest EV-loss proxy.
4. **Coach with Claude:** feed `format_spot(spot)` + the strategic read + the oracle mix + the user's action to
   `ask_claude` → a per-decision verdict: *what GTO does here and why, what you did, the EV cost, and the one concrete
   lesson* — phrased in the two-gear (exploit/GTO) vocabulary, in the player's language.
5. **Aggregate** into a session report: the biggest leaks ranked by summed EV-loss, the strongest plays, and the
   street/spot-type pattern (reuse the `study_analyze` leak/edge aggregation).
6. **Personalize across sessions:** track the player's recurring leaks over time (update the record as new sessions
   confirm/retire a leak) so coaching focuses on THE player's patterns, not generic advice.

### B2 — Phased build (smallest valuable first)
- **B2.1 — MVP ($0 infra, a few $ Claude):** a CLI under `pokerbot/coach/` that takes ONE PokerStars HH
  file → reconstructs → grounds → Claude per-decision review → a Markdown report. Reuses `study_grade` + `coach.py` +
  `understanding.py`; no new parser (PokerStars first). Verify on one exported session.
- **B2.2 — Personalization + trend tracking:** persist per-leak EV-loss across sessions → a "your leaks this week"
  rollup; feed the tracked leaks back into the coach prompt.
- **B2.3 — A nicer surface (optional):** a small local web view (mirror `pokerbot/web`) for browsing graded hands +
  the coaching notes, instead of a Markdown file.

### B3 — Honest scope / guardrails
- **Cost + privacy:** Claude API = PC-hub only (CLAUDE.md hard rule); the player's hands stay local; keys read from
  `Secret keys/`, never logged. One per-decision review ≈ a few cents → a session is ~$1–3 (gate batch size).
- **Grounding gate:** the coach must cite the ENGINE's exact numbers (equity/required-equity/the oracle mix), never
  hand-wave — the EV-loss is the honest proxy `study_grade` already computes (real-bb only for call/fold; solver has
  no per-action EV). No hollow praise: a fine decision is called fine, a leak is quantified.
- **Variance honesty:** a single session's results are noise (the whole project's lesson — small samples lie). The
  coaching value is the **per-decision GTO-grading + the cross-session leak trend**, NOT any session's bb/100.
- **It is coaching, not autopilot:** this reviews the player's OWN play to make the PLAYER better; it is separate from the
  bot that plays. The two share the engine + the understanding layer.

---

## Pointers
- Live measured state: [`docs/STATE.md`](../STATE.md) · north star + conventions: [`CLAUDE.md`](../../CLAUDE.md) · repo tree:
  [`../INDEX.md`](../INDEX.md) · deferred-precision log: [`../NOTES.md`](../NOTES.md).
- The understanding layer: [`pokerbot/brain/understanding.py`](../../pokerbot/brain/understanding.py).
- The grading harness the coach reuses: `research/study_grade.py` + `research/study_analyze.py`.
- The existing Claude coach: `pokerbot/coach/coach.py` + `pokerbot/coach/meta_coach.py`.
