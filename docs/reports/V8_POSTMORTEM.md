# V8 POSTMORTEM — why the play stage brought no measurable advantage

**Date:** 2026-09-01 · **Decision:** v8 (r9_v8 = solver PLAY + stackoff_bremse on the v5 chain)
is NOT christened; `auslese-v5` (FINAL_STACK = r8_stack) remains the state. User decision after
presentation of the interim verdicts; this report is the requested root-cause analysis.

## 1. The measurement situation (all runs 12 workers, A/A-secured, paired decks)

| Comparison | n decks | bb/100 | 95% CI | Verdict |
|---|---|---|---|---|
| r9_play vs r8_stack (v5) | 30,000 | **+1.14 ± 2.78** | [−4.1; +6.3] | NEUTRAL |
| r9_v8 A/A | 576 | exactly 0.0 | — | measurement clean |
| r9_v8 vs r8_stack, run 1 | 30,000 | **+3.91 ± 2.85** | [−1.9; +9.5] | NEUTRAL |
| r9_v8 vs r8_stack, run 2 | 14,976 | **−1.23 ± 4.36** | [−9.9; +7.0] | NEUTRAL |
| pooled (inverse-variance) | ~45k | **≈ +2.3 ± 2.4** | — | null to weakly positive |

(Run 3 + ladder vs v4/basis aborted at the drop decision. Run storage:
`data/runs/20260831_*_pargate_r9_*` + `data/runs/v8_kette_rest_*.log`.)

For contrast, the GTOW-axis evidence of the same play component (replay on the real
night-2 hands, `research/v8_replay_gegentest.py`): 32 interventions/3904 decisions,
fold counterfactual **net +278.6bb**, repeatedly AIVAT-convergent (#2991749 AIVAT −52.2 →
solver check; #2993037 AIVAT −33.1 → solver raise). Both measurements are consistent —
they measure different axes.

## 2. Why no advantage in the gate channel — four causes

**(a) Channel saturation: the surgery had already brought in the mirror harvest.**
The v5 jump (+27.6 ± 1.8 vs v4) came from the rare, expensive clear cases — big-pot disasters
with ~17bb per divergence deck. Play differs from the surgery ONLY between the
thresholds (0.10 < p_basis < 0.70): fine size corrections, marginal mixing decisions.
Exactly there, however, the solver is (almost) indifferent — both sides of the mix carry similar
EV. The mirror can only price clear errors, and those had already been cleared away with v5.
Measurable: v8 divergences had nz_median **1.9bb** versus **11.6bb** for the v5 surgery —
ten times smaller corrections.

**(b) The self-play ecology does not punish fine precision.**
Value raise instead of call, halved mis-size, rescued overfolds — these gains exist
against an opponent who exploits or pays for the finer policy. The mirror opponent
(v5 family) is not a re-solver: it exploits neither size patterns nor mix errors. This is
the same two-axis lesson as with r6_ecall (mirror −4.15, GTOW-relevant) and r7_bill
(mirror exactly 0) — this time on the bet side.

**(c) The sample arithmetic of rare edge cases.**
Play interventions beyond the surgery: <1% of decisions; in the gym ~3% divergence
decks with ~2bb medians. A small effect × neutral mirror expectation is statistically
invisible at 45k decks (SE ~2.4); a confirmation of +2 would need >150k decks — for
an effect that is structurally small in this channel. The measurement budget then no longer
belongs in this channel.

**(d) Complexity and latency costs at a tie.**
v8 = v5 in the only channel that decided here — but with more code in the hot path,
more GPU latency per river spot and an additional (measured once crashed,
then gated) action branch. At a tie the simpler version wins (Occam,
and the repo's clean-code discipline).

## 3. Honest residual uncertainty

It remains POSSIBLE that v8 would be genuinely better against GTOW — the replay evidence points that way,
and the mirror cannot answer this question in principle. It is unproven as long as
no anchor runs. If ever desired: the cheapest proof would be a GTOW A/B **v5 vs
v5+play** (~2500 hands each, protocol ready in `data/runs/gtow_v8_protokoll_2026-08-31.json`,
arm configuration only to be extended by POKERB_AUSLESE_STACK=r9_play). Until then the
conservative conclusion of the drop stands.

## 4. What the round nevertheless contributed (stays in the repo)

- **Confirmation of v5:** three more A/A-exactly-0 proofs and ~45k decks in which v5 was not
  beaten by a more aggressive variant.
- **Instruments:** `research/v8_replay_gegentest.py` (parametric guard counter-test on
  real GTOW hands), `research/gpu_river_audit.py`, the GTOW v8 protocol.
- **Default-OFF arms** (built, registered, not christened): `r9_play` (incl. legality
  gate), `r9_turn` (TurnCFR surgery), `stackoff_bremse`; re-testable at any time.
- **Negative results with explanation:** no_limp (−11.42: the basis limps ~39% strategically —
  limp-pot *defense* would be the right candidate, not limp removal); turn_gpu
  (3/3904 interventions = too quiet for evidence); play (channel saturation, this report).
- **Process lessons:** a bash-chain stop kills only the active link (kill the process family);
  solver actions need legality gates against all-in opponents; expectation bands into the
  journal before every run.

## 5. State after the drop

`auslese-v5` remains FINAL_STACK (tag ec11fde): mirror ladder +27.6 ± 1.8 vs v4, +30.6 ± 5.0
vs basis, GPU surgery live-smoke green. The prepared GTOW anchor (arm B1 = v5) awaits
the user's command.
