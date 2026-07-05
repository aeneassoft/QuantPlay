# Novelty audit — is there substantial math progress / a novel CS approach? (2026-07-04)

The user asked, after the engine landed #11 on GTO Wizard's public leaderboard: *"Es scheint mir als hätten wir
mathematische Fortschritte gemacht die erheblich sein könnten. Oder zumindest einen neuartigen Weg im Programm und
in der Informatik aufgebaut."* — Prüfe das.

**Two INDEPENDENT adversarial audits** (Claude: an 8-agent prior-art workflow, each component checked against the
literature; OpenAI: a separate reviewer prompt, NOT shown the Claude result). Both were told the owner wants the
truth, not encouragement.

## The verdict — they converge

| Component | Claude verdict | OpenAI verdict |
|---|---|---|
| 1. CPU-only hybrid (blueprint + advisors + terminal re-solve, no value net) | KNOWN_TECHNIQUE | KNOWN_TECHNIQUE |
| 2. Damped Bayesian range tracker (tempered exponent + confidence gate) | KNOWN_BUT_NOVEL_APPLICATION | KNOWN_BUT_NOVEL_APPLICATION |
| 3. **Tree census** (mine GTOW's size grid, snap our tree onto it) | **KNOWN_TECHNIQUE** (Libratus self-improver) | **PLAUSIBLY_NOVEL_METHOD** ("most novel thing") |
| 4. Oracle-in-the-loop dev (Analyzer as free per-decision grader) | KNOWN_BUT_NOVEL_APPLICATION | KNOWN_BUT_NOVEL_APPLICATION |
| 5. Trimmed-body vs fat-tail eval | KNOWN_TECHNIQUE (DIVAT/AIVAT) | KNOWN_BUT_NOVEL_APPLICATION |
| 6. The tie-ledger (gap decomposition) | KNOWN_TECHNIQUE | KNOWN_TECHNIQUE |
| **WHOLE PROJECT** | all known / known-application | **KNOWN_BUT_NOVEL_APPLICATION** |

**Neither auditor found a new algorithm, a new theorem, or a field-surprising empirical result.** The claimed
`(pot/2)·L1` value-error bound is, per OpenAI, "mathematically trivial under standard Lipschitz arguments" — the same
belief-error→value-error relationship used throughout the CFR/DeepStack literature. Every ingredient has nameable
prior art:
- Hybrid CPU player, no value net → **Tartanian7** (Ganzfried-Sandholm, AAMAS 2015, terminal endgame solving on CPU),
  **Libratus** (Brown-Sandholm, Science 2017, blueprint + nested subgame solve, explicitly no value net),
  **Modicum** (Brown-Sandholm-Amos, NeurIPS 2018, near-superhuman HUNL on a 4-core laptop). The CPU-only, value-net-free
  point is not new — it is a *regression* from DeepStack/ReBeL, chosen for our hardware, not a frontier advance.
- Tempered per-combo Bayes tracker → **Bayes' Bluff** (Southey et al., UAI 2005) + **power/fractional posteriors**
  (Grünwald SafeBayes 2012, Bissiri-Holmes-Walker 2016).
- Tree census → **Libratus's "self-improver" module** (mines opponents' played bet-sizes from logs nightly, adds the
  off-tree sizes to its own abstraction, re-solves). Mechanically the same idea, published + deployed 2017.
- Oracle-in-the-loop → chess engine-grading loops (Stockfish ACPL, Regan's IPR, Maia), PokerBench solver-label grading,
  and GTO Wizard's *own advertised human workflow* (upload HHs → per-decision EV-loss → fix → re-grade).
- Trimmed-body / spew-vs-cooler → **DIVAT** (Billings-Kan 2006), **MIVAT** (White-Bowling 2009), **AIVAT**
  (Burch et al. 2018), + classical trimmed means (Tukey).

## The one honest disagreement — the tree census

Claude called it **refuted** (= Libratus self-improver). OpenAI called it the **single most novel thing**
("PLAUSIBLY_NOVEL_METHOD"). The resolution is in the PURPOSE, not the mechanism:
- **Same mechanism** (mine a black-box solver's bet-size distribution from logs, reshape your own action tree). That
  mechanism is Libratus's — Claude is right it is not new.
- **Different purpose.** Libratus mined sizes to *reduce its own exploitability* to sizes it hadn't anticipated. We
  mine GTOW's grid to *snap our abstraction onto the grader's tree so our self-play hands become per-decision gradable
  by that black-box solver* — an evaluation-alignment trick, not a strategy-improvement one. Neither auditor can name a
  publication that does exactly this. So it sits between the two verdicts: a **known mechanism repurposed for a new
  (unpublished) end** — at most a short methods note, IF written up with measured before/after AIVAT. Not a theorem,
  not a breakthrough.

## The honest bottom line

**The remarkable thing here is NOT mathematical progress and NOT a new algorithm. It is a SYSTEMS / ENGINEERING
result, honestly measured.** Both auditors say this in their own words. Specifically what is genuinely creditable:

1. **A consumer-CPU, value-net-free, classical-architecture (2015–2018-era) engine reaches #11 on a 2026 leaderboard**
   whose top-10 is otherwise frontier LLMs (GPT-5.x), two MIT bots, individuals, and a poker pro. It *loses* to the
   benchmark (−20 AIVAT is a losing mid-table number), but reaching that region on a home PC with no GPU is a real
   engineering feat of integration and tuning.
2. **The measurement discipline is the actual quality signal** — AIVAT + trimmed-body + paired/interleaved A/B +
   pre-registered n + the $0 counterfactual that *refuted our own* anti-spew gate. That is good science hygiene (not a
   publishable result, but the thing that makes every number above trustworthy).
3. **The evaluation-alignment pipeline** (tree census + oracle-in-the-loop) is a clever, cheap, reproducible
   build-measure-fix loop against a commercial solver — an engineering shortcut worth a blog post / systems write-up,
   with the tree-census twist the one part that could stretch to a short methods note.

**What it is NOT:** substantial mathematical progress, a new GTO algorithm, or a novel CS paradigm. Pitched as
"new GTO math," reviewers would (correctly) push back — and so should we, per our own honesty gates. Pitched as
"how far classical tools + a commercial oracle + one abstraction-alignment trick get you on a consumer CPU, measured
rigorously," it is a solid, honest engineering study.

Artifacts: `data/gtow_grades/openai_novelty.json` (OpenAI) · the Claude workflow result (8 agents, in the session
transcript) · `data/gtow_grades/leaderboard_2026-07-04.json` (the #11 standing).
