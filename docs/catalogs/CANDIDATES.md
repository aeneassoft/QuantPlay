# KANDIDATEN — what was built/planned but never measured at the anchor (as of 2026-09-10)

Short note so the list does not have to be pieced together from ten files again.
**Caution: the numbers sit on DIFFERENT axes** (GTOW-AIVAT, gym mirror, Analyzer EV-loss) and
are not directly comparable. The only real GTOW anchor remains **v4-on-PRINCE −21.1** (night 2).
Target yardstick: Top 5 on benchmark.gtowizard.com = **lower bound better than ≈ −14.8** → ~8 bb/100 are missing.

## With a pre-registered number

| # | Candidate | Status | Recorded expectation | Source |
|---|---|---|---|---|
| 1 | **v9 / `r10_ernte`** (river-raise harvest + size precision, trigger 15 bb, fp16) | built, A/A exactly 0 (576 decks), champion run aborted at ~13/48 blocks | **+3.6 to +5.4 bb/100 on the GTOW axis**; mirror pre-registered "NEUTRAL to +8" | `data/autogym/journal.jsonl:100` |
| 2 | **v4 path** (depth-limited CFR + neural leaves, EVPA, TurboReBeL) | only planned, never started | "ladder ≈ **−10 asymptote**, v4 = the way below −8" | `CLAUDE.md:169` |
| 3 | **Canonical flop/turn solve library** (1755 suit-ISO flops) | only planned | targets the **flop bleed −6.4…−8.3** | `../NOTES.md:647`, `../plans/TIE_GTOW.md:19` |
| 4 | **v10 / `r10_stack`** (K1 hero likelihood + K2 river plan) | gated, **no GTOW anchor**, G3 missed | mirror **+11.7 ± 10.9 NEUTRAL** (CI includes 0) | `docs/STATE.md:84` |
| 5 | **v8 play component** (`river_play_guard`) as a GTOW A/B | built, never at the anchor | "+278.6 bb replay, AIVAT-convergent" — explicitly unproven | `docs/STATE.md:105` |
| 6 | **A7 `stackoff_bremse`** | built, silent in self-play (1 trigger/400) | GTOW class D, **−13.8 bb per cell** | `HU_OPTIMAL_MAP.md:51` |

External assessment of #1 (Astra): "The registered +3.6 to +5.4 bb/100 are a **hypothesis**. Even at the
upper end, A1 alone would not suffice for −8 if the actual v5 value is below −13.4."
(`../consults/TOP5_CONSULT_GPT6_2026-09-07.md:813`)

## Marked as a lever, without a number

* **Value-of-computation arbiter** — resolver budget only where it flips the decision; noted as "ONE
  buildable high-leverage lever" and "implementable core of the v4 path" (`CLAUDE.md:175`).
* **v10.1 = closed hybrid H0 → H1** (Astra Part G). Warning in the journal: "H is a NEW bot with
  its own seams, **not Max(v5,v10)**" (`data/autogym/journal.jsonl:111`).
* **R1 CFV net** (river CFV for turn search) — "first substantial new net"; R3 only if needed.
* **Re-solver proxy opponent in the gym (E1)** — "the only $0 channel that can price A1/A2/C3".
* **`turn_wert` SIZE decoupling** (the 7/7 tell) — "most important single fix" against the seesaw violation.
* **Turn/river selection** (`sel_turn`/`sel_all`) — the old rejection verdict is VOID by construction;
  the matter is **unmeasured, not refuted** (`docs/STATE.md:255`).

## Only "open / queue"

GTOW anchor for v5 (shadow night) · C1 A/B "GPU replaces TexasSolver river" · limp-pot DEFENSE ·
bluff follow-through and seesaw-mixing guards · B1 range-structure round · v10 re-release (K2 fallback onto
the r8 surgery instead of the naked base, off-tree mapping, K1 support) · external Analyzer anchor for the new
6max `tag` after the flat fix.

## External consult gpt-5.6-sol (2026-09-10)

Full answer in the root: [`../consults/CONSULT_GPT56_SOL_2026-09-10.md`](../consults/CONSULT_GPT56_SOL_2026-09-10.md)
(briefing 37,655 characters incl. our own fact check; answer 59,696 characters, effort high).
The main question was the **hybrid ("Zwitter")**. Short verdict: a bot that simply picks the best module per
decision is a game-theoretic fallacy; the only viable form is **v5 as a closed baseline + exactly ONE
coherent river expert + complete v5 continuation + conservative public selector**.
**Correction confirmed against the code:** the GTOW competition runs at **200 bb** (`gtowizard.py:98`), our
blueprint only fires from 140 bb (`bot.py:200`) — the Kaggle channel (100 bb) measures a DIFFERENT bot.

## Next step (user, 2026-09-10)

**Measure v9 (`r10_ernte`) in the Kaggle channel** — the first reference value is being produced right now.
Protocol + results: [`../reports/KAGGLE_ARENA.md`](../reports/KAGGLE_ARENA.md).
