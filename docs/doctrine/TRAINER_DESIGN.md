# TRAINER_DESIGN.md — The training program (design blueprint, 2026-07-08)

**Product:** 6-max NLHE training program on the existing platform (`six_server` + engine).
**Base bot:** PRINCE v2.2 (`POKERB_PRINCE=1`) — the most-measured version (Quantplay v8: AIVAT −30.11 ± 5.51,
n=2,899, rank 24/64; history −19.70 n=2,393 on the old harness). More than strong enough for human opponents;
the engine limit is honestly stated in the grading.
**Guiding principle:** engine = truth · templates = explanation · small LLM = voice · Claude (Code, in-session) =
development coach. Simple and efficient — NOT overloaded.

---

## 1. Fairness doctrine of the grading (BINDING)

Poker is a game of incomplete information with mixed strategies. The grading MUST reflect that:

1. **Never grade results, only decisions.** A won hand ≠ a good hand; a lost one ≠ a mistake.
   (Anti-results-orientation is itself lesson content no. 1.)
2. **Grade bands instead of binary:**
   - ✓ **OK** — the action lies in the mixed support (advisor frequency ≥ ~15 %) OR within a small
     EV tolerance of the best line. Several actions can be OK at the same time — and that is SAID
     ("GTO mixes here: 60 % bet / 40 % check — both good").
   - ～ **Costly** — clearly inferior line, moderate EV loss.
   - ✗ **Leak** — only on mathematically hard violations (pot odds clearly violated, gross MDF violation,
     sizing-geometry error) or a large EV loss.
3. **State the uncertainty hierarchy:** preflop (near-Nash blueprint) and river (resolver) = hard verdicts;
   math checks = incontestable; flop/turn strategy = "bot assessment", labeled as such. The trainer that names its
   limits is more credible.
4. **Range tolerance:** The human constructs ranges approximately. What is graded is the DECISION LOGIC
   ("was the action defensible against a reasonable range?"), not the match with the exact
   tracker range.
5. **Tone: warm, concrete, never ice-cold.** Good moves are EXPLICITLY celebrated (not only mistakes marked).
   Leaks are called an "expensive purchase", not a "mistake". Every criticism carries the alternative + the one-sentence reason.
   Engagement via content (hand of the session, best decision, progress since the last session) —
   NO gamification bloat (no points/badges/levels).

## 2. Two modes

| | GTO mode | Exploit mode |
|---|---|---|
| Bot config | `POKERB_PRINCE=1`, exploit OFF (= the measured basis) | the same basis + `exploit=True` |
| Behavior | plays its GTO approximation, ignores player tendencies | GTO baseline + **bounded, LCB-gated deviations** (opp_model/Dirichlet learns the trainee live) — realistic, no cartoon |
| Training purpose | learn the baseline, feel balance | hold up under pressure; EXPERIENCE one's own exploitability |
| ★ Killer feature | — | **"What the bot has learned about you"** panel: the trainee's learned Dirichlet tendencies in plain text ("it noticed: you fold 68 % to river bets → it bluffs you more often"). Exploit layer = leak detector. |

## 3. Language layer — interface first, backend replaceable (protection against getting sidetracked)

- **Contract:** structured JSON in (grades, numbers, rationale, strategic_read) → short text out.
  The language layer DECIDES NOTHING and COMPUTES NOTHING (LLM authority inverse to engine competence).
- **Phase now:** deterministic **templates** (P1) + **Claude Code in-session as development coach**
  (free, best quality): we play, I coach live, the best formulations get distilled into the
  template library. LEARN from the optimization process — that is the user's plan.
- **Phase later (P3):** ONE measured latency/quality test: Ollama (Qwen3-8B-Instruct GGUF) vs our own
  serving (GLM experience). Criterion: < 2 s response, no hallucinating of numbers (numbers come ONLY from
  the JSON). The simpler system wins. Our GLM lessons (template discipline, validity gates,
  frac_bad measurement) transfer to both.
- **Claude API:** NOT for now (no credit). Premium deep reviews run as Claude Code sessions.

## 4. Data layer

- `data/sessions/` JSONL exists (per hand). NEW: one record **per DECISION**:
  `{hand_id, ts, street, spot_fp, state_kompakt, human_action, oracle_action, advisor_dist,
   equity, pot_odds, mdf, grade, grade_typ, erklärung_kurz, mode}`
- Append-only + session registry. The 1000-hand analysis runs on our own logs (format controlled →
  no parser needed).
- Quality control of the trainer itself: export of the human hands in PokerStars format
  (`research/pokerstars_export.py` path) → GTOW Analyzer as an external second opinion on our grades.

## 5. Learning maximization

- **Error-rate band 10–20 %** (85% rule, Wilson et al. 2019 — honestly: a HYPOTHESIS for poker, implemented as
  an adaptive band, not as dogma). Regulator = opponent league (`arena/sixmax.py`: nit/tag/lag/station/
  maniac + bot ± exploit) is adjusted per session.
- **Instant feedback light** in play (✓/～/✗ icon, NO wall of text — flow!) + **deep review after the hand**.
- **Leak drilling:** the weakest spot category of the last sessions is generated more often (spaced repetition
  over spots). **Interleaving:** positions/stack depths mixed.

## 6. UI specification (2560×1440, Snowie-oriented)

- **Layout:** left ~60 % compact table, right ~40 % coaching panel. Table deliberately NOT large.
- **Tempo:** maximum hands/hour — animations < 300 ms, bot decisions instant (the engine is fast),
  hotkeys (F/C/R + sizing shortcuts), auto-deal after feedback dismiss or timeout.
- **Visibility:** actor highlight, bet amounts LARGE at the chip, pot permanently visible, short flowing
  info line ("CO bets 12 → BTN calls"). See visually what happens.
- **Flow:** hand by hand. After EVERY hand: 3–5-line feedback on the right.
- **Replay button:** animated replay of the hand, step by step; at every hero spot: played vs
  recommended action + one-sentence strategy (from `strategic_read` + rationale) → "this is how you play the hand".
  Fully deterministically reconstructable from the decision log.
- **DO NOT build:** accounts, 3D, sound design, mobile, gamification, multi-table. Simple + efficient.

## 7. Autotest before human use (binding)

League bots play the "human" seat through the COMPLETE stack (logger → grader → renderer → replay →
language layer): N hands automatically. Check criteria: 0 crashes · latency budgets met · grade distribution
plausible (station is graded worse than tag — sanity!) · every rationale path renders text
(template coverage) · session report builds.

## 8. Build phases

| Phase | Content | Status basis |
|---|---|---|
| **P0** | decision logger + math grades (pot odds/MDF/sizing) + oracle diff | session_log exists; decide() rationale exists |
| **P1** | explanation renderer (templates on rationale + strategic_read) + after-hand feedback + session report | understanding.py exists |
| **P2** | UI rebuild (layout/tempo/replay) + adaptive difficulty regulator + leak drills | six_server/six.html exists |
| **P3** | language-layer backend test (Ollama vs own) + "what the bot has learned" panel | opp_model exists |
| **P4** | autotest harness + polish | league exists |
