# NOTES — in-repo notes & deferred-precision log

A running, in-repo log of OPEN QUESTIONS, DEFERRED PRECISION items, and "good-enough-now, compute-exactly-later"
decisions. Distinct from the cross-session auto-memory (`C:\Users\hampe\.claude\projects\...\memory\`). Add an
entry whenever we ship a heuristic/approximation that should later be replaced by an exact/measured value.
Referenced from `CLAUDE.md`.

## ★ TRAINER: DU-Zeile soll bewusste Slowplay-Fallen erkennen (User, 2026-08-02 — NUR Trainer-Text, NICHT der HU-GTO-Bot)
- **[deferred] `pokerbot/coach/range_story.py::_du_line`**: bei passiver Linie + Monster sagt die DU-Zeile "mehr
  Blatt als Geschichte — hier bleibt Value liegen". Wenn die Hand aber mit einem River-Check-RAISE/Jam endet
  (Hand #80: check-call/check/check → All-in über seine Bet, alle 7 Entscheidungen ok), war die Unterrepräsentation
  der KÖDER — der Grader erkennt das bereits (Linie = ok im Plan), nur der Erzähltext nicht. Fix-Idee: wenn die
  LETZTE Hero-Aktion raise/allin NACH einer passiven Linie ist und die Hand stark → "Falle zugeschnappt: deine
  stille Linie hat ihn zum Bluffen eingeladen" statt "Value bleibt liegen". Reine templates/range_story-Sache;
  der HU-GTO-Bot (Prince) bleibt unangetastet — sein Seesaw/Slowplay-Mixing ist bereits gemessen geshippt.

## ★★★ ENGINE→GTOW: the −47 is stale (−20 real), GTOW-MODE built + UNMEASURED (2026-07-04)
- **CORRECTION (measured): the engine is −20.09 AIVAT, NOT −47.** Fresh HEAD-default GTOW run (n=974): AIVAT
  −20.09 ± 7.18, body −8…−11 (trim), 0 catastrophes. The −47.18 was a STALE account aggregate over dead code eras.
  Cross-checked: GTOW-Analyzer HU per-decision EV-loss 19.3 ≈ AIVAT −20. **Purge/annotate every "−47" in the repo.**
- **[BUILT, UNMEASURED — the #1 next test] `POKERB_GTO_MODE` (`pokerbot/strategy/gto_mode.py`).** Flips exploit OFF +
  GTOW-tree census sizes (S1–S5). The HU exploit engine grades 53.4% GTO-score / Freq-Diff 54.6% (deviates by design);
  6-max tag-core grades 85.9%. HYPOTHESIS: exploit-OFF lifts HU GTO-score toward 85% + shrinks Freq-Diff. TEST $0
  DETERMINISTICALLY: `POKERB_GTO_MODE=1 python -m research.pokerstars_export --n 1500 ...` → GTOW-Analyzer grade vs the
  53.4% HEAD. Only then a paired AIVAT run (S6, gated vs −20.09, NOT −47). Sub-levers still `in_progress`: S2
  weighted_ranges fix (verify via `research/check_range_l1.py` + `resolver_probe.py`), S5 resolver-on-census-tree.
- **[measured, deferred-precision] `--resolver off` only kills the RIVER resolver; the TURN resolver needs
  `POKERB_TURN_RESOLVER=0` separately** (the HU-export hang: turn-resolver ~6s/turn-decision). `hero_decider` should
  disable both for fast gradable exports; the shipped bot keeps both ON.
- **[finding] EV-loss is CONCENTRATED (fat tail), both HU + 6-max**: of 54 6-max "blunders" only 2 cost ≥8bb (a 3bet
  −8.25 + a 4bet −34.23 stack-off); the rest are ~0-EV mini-pot blunders. → the lever is BIG-POT stack-off discipline
  (the `postflop_corset`/commit-cap territory), not chasing the blunder COUNT. Mirror of [[gtow-tail-body-vs-spew]].
- **[built] `research/gtow_tree_census.py` → `data/census/gtow_tree.json`** = GTOW's empirical bet tree from 12,483
  logged hands (open 2.25 / 3bet 4x / river 0.65-0.35-1.0-1.5 …). Reusable to re-calibrate any tree constant.
- **[built] `pokerbot/vision/screen_reader.py`** = universal VLM poker-table reader (any site, dHash change-gate,
  watch mode). Grading exporters: `research/sixmax_export.py` (6-max), `research/pokerstars_export.py` (HU).

## ★ Understanding layer + river over-sizing + the personal coaching path (2026-06-29 #2)
Built the consolidated UNDERSTANDING layer (`pokerbot/brain/understanding.py::strategic_read`) so the brain reasons on
UNSOLVED spots, measured the brain's river over-sizing, and wrote the forward plan `docs/ROADMAP.md`. Deferred / open:
- **[BUILT, gated, EV-UNMEASURED — the #1 next measurement] the understanding layer.** Fuses SPR/position/pot-odds/MDF
  + texture + made-hand + the measured GTO heuristics into one engine-computed frame, appended in `format_spot` gated
  `POKERB_UNDERSTANDING` (default OFF). Locally verified (OFF byte-identical, ON-numbers exact). Its REALIZED-EV benefit
  is UNPROVEN → A/B it: deterministic GTOW per-decision (`research/claude_export.py`) FIRST (no variance), then a paired
  AIVAT run only if promising. Honest precedent: perception fixes helped (made-hand +40), strategy nudges didn't
  (solver_freq neutral) — the layer is mostly perception, so cautiously optimistic, but measure before believing.
- **[BUILT, gated, EV-UNMEASURED] the river-sizing rule** (`claude_brain.py`, `POKERB_CLAUDE_RIVERSIZE`, default OFF).
  MEASURED: the brain bets ~0.60× river vs the solver's median ~0.33× (checks 58%) → over-sizes ~2×. The rule nudges it
  smaller; validate deterministically (does the bet-size distribution move toward 0.33× at one seed?). **The cleaner fix
  (proposed, not built): render the solver's preferred SIZE in the prompt** — the size analog of `api.solver_freq` — so
  the brain sizes like the solver instead of being snapped post-hoc (`POKERB_BRAIN_ONTREE` snap is only a partial
  band-aid: 0.6→0.5/0.75 is still > 0.33×).
- **[PROPOSED — a new product direction] the personal Claude coaching path** (`docs/ROADMAP.md` §B). Review the user's
  OWN CoinPoker/PokerStars hands, engine-grounded + GTO-anchored, personalized to the user's tracked leaks. Most
  machinery exists (`pokerbot/coach/coach.py`, `research/study_grade.py` reconstruction, `research/llm.py`, the new
  `understanding.py`); the one genuinely new piece is a **CoinPoker HH parser**. Phased MVP = a `review_session.py` CLI
  (PokerStars first). Guardrails: Claude = PC-hub only, hands stay local, cite the engine's exact numbers (no hollow
  praise), and per-session bb/100 is noise — the value is per-decision grading + the cross-session leak trend.

## ★ Wiring-hint A/B + the perception-vs-strategy lesson + the noise floor (2026-06-21 night)
The `solver_freq` hint (the advisor's P(bet) shown in the prompt) was A/B'd **NEUTRAL** (paired n=500: ON −49.21 ≈ OFF
−49.52). The OFF arm also revealed the **"−28.36" baseline was a lucky draw** (same config re-measured −49.52; true ≈ −37
± 8, being pinned with n=1500). Insights + deferred:
- **[HYPOTHESIS — perception vs strategy] the model ACTS on corrected PERCEPTIONS but IGNORES strategy ADVICE.** The
  made-hand line (a PERCEPTION fix — the model mis-read its own hand) helped +40; `solver_freq` (a STRATEGY nudge — "GTO
  bets X%") was neutral. Couldn't fully ground it (the A/B harness pulls only ONE arm's per-hand log → the ON-arm log was
  lost; same pull-gap as the SFT). If true → future wiring leverage = MORE perception fixes, NOT strategy nudges.
- **[DEFERRED — the motivated next lever] a DRAW-perception hint.** The model UNDER-bets DRAWS on the turn (the one real
  leak from the 264-decision study); the made-hand line says "High Card" for a flush draw → UNDER-states it. A line like
  "Draw: flush draw, 9 outs ≈ 35% (2-card)" (`api.outs_equity` + a draw classifier) is a PERCEPTION fix (like made-hand)
  hitting the exact leak → the best-motivated next hint. Build + local-verify via the `format_spot` env-gated pattern
  (default OFF), THEN A/B. NOT done now (budget + the noise floor below).
- **[BLOCKER — the noise floor] n=500 AIVAT swings ±~20 session-to-session for this 9B** → it only detects BIG effects
  (made-hand +40 = 2.1σ; to_call +12 and solver_freq ≈0 were below it). The draw-hint (likely a few bb) needs a BIGGER-n
  A/B (≥1500/arm) or a duplicate/paired-hands harness to be measurable. **Do NOT A/B small hints at n=500 — you measure
  noise, not the effect.** This is the real constraint on cheap wiring optimization now.

## ★ RL/re-SFT post-mortem + deferred (2026-06-21)
The made-hand-NATIVE re-SFT→GRPO REGRESSED (−28.36 baseline → −90 GRPO vs GTOW; postflop/river spew). The session's wins
were INFERENCE-WIRING (to_call +12, made-hand +40 OOD), NOT weights; baking a serve-hint into training backfired. Open/deferred:
- **[OPERATIONAL — fix before ANY next campaign] `runpod_rl_campaign` pulls ONLY the GRPO** (`qwen_poker_grpo.tgz`) → it
  LOST today's SFT base (never pulled) → the clean SFT-vs-GRPO isolation was impossible (I had to A/B a stale older SFT).
  Add an SFT pull (slim `/root/qwen_poker_lora` → e.g. `sft_new.tgz`) at the end of the SFT stage.
- **[OPEN — the real RL lever] the self-play sixmax league is too weak/≠ GTOW** → RL optimizes league-beating aggression
  that SPEWS vs GTOW (river −211 in the −90 run). The deeper lever = a BETTER REWARD (GTOW-anchored eval-in-the-loop, or a
  much stronger opponent league), NOT more SFT/GRPO steps on the current reward. This is the hard, deferred RL work.
- **[REFUTED $0 — the cheap version of the above: a LEAGUE RESHUFFLE won't work] (2026-06-21 #3).** Plan was "drop the
  exploitable maniac/station from `TRAIN_LEAGUE` so the reward stops rewarding over-paying-off/over-bluffing". 3 grounded
  rollout tests killed it: call-EV maniac-vs-tag = +0.0 (a call CLOSES the action → CRN cards → style-irrelevant);
  maniac-gen vs tag-gen facing-bet call-EV = +0.3 bb; bluff-EV nit-vs-tag = +0.0. ROOT CAUSE: the `PROFILES` differ mainly
  PREFLOP; **POSTFLOP all 5 share ONE `_decide` engine (68% identical decisions; the 32% diffs are EV-low-leverage).** So
  the league can't change the POSTFLOP reward (where the tail is). The wall is the **OPPONENT CEILING** (RL trains vs a
  ~−47 engine; no GTOW-level postflop opponent for the loop — solve_node ~76s too slow, SolverSlumbotBot ~engine-level).
  → the ONLY real RL lever = build a **solver-distilled strong postflop opponent NET** (extend the advisor to full
  action+sizing), realistic ceiling **~−45 = engine-level** (the solver IS ~the −47 oracle → can't exceed it), NOT the
  leaderboard. Beating −45 needs a better-than-solver signal we don't have (GTOW in-loop infeasible). See [[gtow-tail-body-vs-spew]].
- **[DEFERRED — diagnostic, likely not worth it] isolate the regression cause** (made-hand-native gold vs claude_study vs
  the GRPO step): a controlled re-SFT (made-hand-native, NO claude_study) with BOTH SFT+GRPO pulled + A/B'd. The postflop
  spew is NOT uniquely tied to made-hand-native (an older made-hand-OFF SFT also spewed) → cause unconfirmed.
- **[HARD RULE] serve-time prompt hints (made-hand, to_call, the new `solver_freq`) stay OFF in the dataset builders** —
  NEVER bake into training. They are env-gated serve-time only; the re-SFT regression is exactly why.

## ★ Tail-robust eval + the anti-spew gate REFUTED (2026-06-21 #3)
Built `research/gtow_tail.py` (tail-robust metrics + a cross-session body table + a $0 gate counterfactual). Findings:
- **[FINDING] the BODY is ~−17; the raw −40/−68 is ALL TAIL.** The 5%-trimmed AIVAT clusters at ~−15…−19 across EVERY
  baseline session (incl. the "−28 lucky" AND the "−90 regression") while the raw swings −28↔−90. The model's
  non-catastrophic skill ≈ −17 (near the leaderboard); the raw is tail-variance. → at n≤1500 report the TRIMMED body + the
  tail separately, NOT the raw mean (the noise floor, restated harder: even the "−90 regression" is body-indistinguishable).
- **[REFUTED] the anti-spew CALL gate does not work.** Counterfactual replay over the 1500-hand log: ORACLE (perfect-info,
  eq vs villain's actual hand) fires 2/1500 (+16.7 bb/100); LIVE (eq vs a committing range = serve-computable) fires
  0/1500 (+0.0); aggressive settings → cost ≈ saved, net ≤0. Only 27 big-calls exist in 1500 hands. NOT built/shipped.
- **[WHY] the tail is hero's -EV BETTING, not call-offs** (the −208bb hand = `HERO:b1000 … HERO:b2710 gtow:b8134 HERO:f`).
  A serve-gate can't reach it — a bet→check change isn't cleanly offline-counterfactual'able (fold-equity is unknowable);
  it's RL's job. **[CONCLUSION] cheap serve levers are EXHAUSTED** (made-hand +40 robust, to_call noise, solver_freq
  neutral, retraining regressed, anti-spew gate refuted) → the only remaining real lever = a BETTER RL REWARD (the hard,
  deferred one above). See [[gtow-tail-body-vs-spew]].

## ★ Math-formula fixes + stale-duplicate cleanup (2026-06-20 Feinschliff)
The OpenAI math audit's 3 `knowledge_base/math/formulas.py` bugs are FIXED + grounded-verified (deterministic algebra +
an EV-zeroing numeric check): `required_fold_equity` denominator `P`→`P+R`; `required_future_winnings_for_implied_odds`
`C/p−P`→`C*(1/p−1)−P` (the audit JSON's own `C*(1/p−2)−P` was itself wrong — it double-counts the call); 
`bluff_to_value_and_frequencies` ratio `(P+B)/B`→`B/P`. HONEST: all three were **DORMANT** — the brain sandbox exposes
only `api.*`, and `api.py` wraps only 4 of formulas.py's functions (none of these three); the LIVE math comes from the
parallel, engine-verified `postflop_formulas.py`/`strategy_formulas.py`. So this is **KB correctness, NOT a bb/100 play
gain** (gate: deterministic, no noisy A/B). Jam-discipline + sizing were also checked: NO groundable engine-vs-blueprint
deviation (the blueprint IS the jam authority in both the brain path and `bot.py`).
- **[DEFERRED — structural] `formulas.py` is a stale, shadowed DUPLICATE of `postflop_formulas.py`.** The clean permanent
  fix = delete/redirect the dormant formulas.py functions to their verified postflop_formulas equivalents (kill the
  divergence) — but FIRST confirm the 4 live `api.py` wrappers + any other importer still resolve. Not done now (risk).

## ★ GTOW optimization pass (2026-06-20) — the preflop switch + deferred items
The GLM vs GTOW = −43.30 (n=100), diagnosed as ~90% a **PREFLOP** leak → the **preflop switch** (the engine blueprint plays
preflop, the GLM keeps postflop) is being measured. DEFERRED (flagged so the re-run measures ONE change at a time):
- **[DEFERRED — needs re-SFT] `format_spot` navigation enrichment** (the user's "add references/options" idea: show the
  LLM the IP/OOP role, effective stack/SPR, pot-odds/required-equity/MDF, explicit options). frac_bad is 0.009 → the GLM
  is NOT format-confused (the leak is preflop STRATEGY), and `format_spot` is what the GLM was SFT/GRPO-trained on
  byte-identically → changing it at serve time is OOD vs the weights (frac_bad-spike risk on the postflop spots we now
  depend on). The data IS already reachable via `api.spr`/`api.pot_odds`/`api.mdf`/`api.required_equity`. Correct path:
  re-SFT/GRPO on the enriched format (train + serve the SAME new bytes), gated on the re-run's postflop AIVAT.
- **[UNMEASURED — exposed by the switch] the GLM's POSTFLOP play.** Only ~6 hands reached postflop in the −43.30 run (the
  GLM over-folded preflop); the switch routes far more hands postflop → the postflop AIVAT is the new headline unknown.
  Measure in the re-run; if weak, lean on the advisor/solver postflop or re-SFT.
- **[DEFERRED] install TexasSolver on the GTOW pod** (live `api.solve_node`): the GLM postflop uses the trained advisor
  `api.solver_freq` (works on the pod); the pure live-solver spewed (−276 noisy). Add only if the re-run shows weak
  postflop AND the advisor is the cause — as its OWN measured change (do not confound the switch).

## ★ GLM-Z1-9B RL bring-up (2026-06-19 PM) — open questions + deferred items from Phase C
The GLM-Z1 SFT WARM-START is solved (loss 0.087, token-acc 97.5% on the H100 SXM); the bring-up chain + status is in
`docs/STATE.md`'s top CURRENT section. OPEN / DEFERRED:
- **[THE open question — UNMEASURED] does the RL LIFT above the engine?** We have only the (imitation-capped) warm-start;
  NO GRPO step's frac_bad/reward has been measured yet (round 10's GRPO died to the concurrency bug pre-step-1; round 11
  re-runs it clean). Everything downstream (GATE 2, the leaderboard number) waits on this.
- **[DEFERRED — path B, the real value of a reasoning model] explicit inference-time CoT is OFF.** We strip the GLM
  template's forced `<think>` so the prompt is byte-aligned with the program-only SFT (the frac_bad fix). That uses the
  reasoning-tuned WEIGHTS (adapted, not wasted) but drops the EXPLICIT test-time CoT that gave Claude −9. To capture it:
  (a) Claude-teacher-distilled CoT gold (reasoning + program, EV-gated), (b) a template/render that does NOT strip the
  think from SFT content, (c) a non-pathological structured approach (see next). Decide AFTER the RL-lift question.
- **[WORKAROUND, deferred] `STRUCTURED=0` for GLM.** vLLM's xgrammar HANGS on the bounded-think regex
  `[\s\S]{0,1500}</think>...` (state explosion); we disabled structured decoding for GLM and rely on the SFT (97.5%) to
  emit valid programs. A non-pathological grammar (the pure-DSL program regex, `think_cap_chars=None`, OR a bounded-think
  form that doesn't state-explode) would RESTORE the format guarantee + drop frac_bad to ~0. Test once the RL path is green.
- **[INVESTIGATE] recurring `AttributeError: 'NoneType' object has no attribute 'util'`** in the probe + GRPO (non-fatal —
  probe ok=True, GRPO starts; appears with a ProcessGroupNCCL teardown warning + a `concurrent.futures` weakref_cb) →
  likely a reward-ProcessPool / distributed TEARDOWN error, not in the hot path. Resolve to keep the logs clean.
- **[RULE, hardening deferred] serialize campaigns.** Two `runpod_rl_campaign` runs share ONE session file → the finisher's
  atexit kills the other's pod (this killed round 10 mid-GRPO). RULE: one campaign at a time; verify 0 pods before launch.
  Hardening (per-launch session file / a lock) is deferred — discipline suffices for the autonomous run.
- **[in progress, frac_bad-SAFE] turn/river gold skew.** The DSL gold is flop-heavy (flop 28421 / turn 575 / river 373).
  A `research.mass_solve STREET=4` (turn) runs on the idle PC CPU → TexasSolver CACHE (not gold → zero risk to the running
  RL). Convert via `from_solver` + VERIFY the format (byte-identical `format_spot` + reasoning-loop DSL only) BEFORE folding
  into a NEXT run. Adding raw-text / PokerBench-prose / decorative completions = the frac_bad killer → never.
- **[deferred] the SYSTEM_PROMPT is 1142 tokens** (the loss=0 truncation cause). A leaner system prompt frees token budget +
  shrinks the truncation surface; MAX_LEN=2048 + the new guard cover it for now, but a trim is cheap future headroom.

## ★ Compute modes + math integration (2026-06-17) — the accuracy↔time trade-off, made explicit
`pokerbot/brain/modes.py`: FAST(~1.5s)/STANDARD(~5s, live target)/DEEP(180s, R&D exact+sympy+trace)/TRAIN(RL
throughput). Every accuracy knob is mode-set (MC `equity_iters`, EV `rollout_k`, gen `max_new_tokens`, decision
wall-clock, `exact_threshold`/`sympy_verify`/`analysis`); wired into `api.equity` / `rl_env.rollout_action_ev` /
`policy.QwenPolicy`. The paradox it resolves: computing "too exactly" starves the reasoning within a hand's time frame
→ accuracy is BUDGETED, not maximized.
- **TUNING IS PROVISIONAL:** the per-mode numbers (eq_iters 300/1000/8000, k 8/16/96, tokens 160/320/2048, budgets
  1.5/5/180s) are first-cut guesses, NOT measured against real GPU latency. The STANDARD mode must actually land in
  1–5s on the deployed model — MEASURE in Stage-1/the pod and re-tune. DEEP's 180s is an R&D ceiling, not a promise.
- **66 engine-verified formulas** now callable as `api.<fn>` (34 post-flop + 32 strategy, both GPT-5.5-generated +
  gated). Same SELF-CONSISTENCY caveat as below — `verify_expr==verify_value` proves the function matches its own
  check, not canonical-GTO correctness; sympy-symbolic + RL-realized-EV are the strengthening. `pipeline/math_loop.py:
  grow_math` grows this toolkit on demand (PC-hub only; pod never calls a frontier API).

## ★ LLM curriculum + frac_bad fix (2026-06-17) — completion-only masking + ordered staged shards (`docs/llm_curriculum.md`)
The local SFT emitted invalid DSL (frac_bad=1.0). Root causes FIXED: (1) `qwen_sft.py` trained full-sequence with
`packing=True`, no masking → now `assistant_only_loss=True` + `packing=False` (TRL auto-swaps in `qwen3_training.jinja`
for the `{% generation %}` mask — verified the native Qwen3 template lacks the marker; the patched template renders
byte-identically for our system+user+plain-assistant case → NO train/inference mismatch). (2) ZERO `decide()` data in
the SFT mix → NEW `dataset/build/curriculum.py` writes 4 ordered shards (a_contract / b_ground / c_decide / d_exploit)
loaded in order via `CURRICULUM=1` + a `_OrderedSFT` SequentialSampler + 15% replay. GRPO got a binary format reward
(`R_FMT`) + the `R_BAD` floor fix (was −10 > min-EV −25, so garbage could beat a valid-but-bad action — a latent bug).
DEFERRED-PRECISION / heuristics shipped:
- **[ship-now] difficulty = engine-oracle EV-spread** (`from_selfplay` meta `spread`, `pilot.rank_state`). A_FRAC=0.35
  splits clearest→contract vs harder→c_decide. It's a PROXY for decision difficulty (best-vs-worst candidate EV gap),
  not a calibrated curriculum scale; fine for staging, re-tune if the pod shows ordering matters more.
- **[ship-now] one-epoch sequential ordering + replay.** True easy→hard is approximated by SequentialSampler over the
  staged dataset for 1 epoch with a 15% prior-phase replay slice. Multi-epoch would re-shuffle the curriculum benefit;
  a phase-by-phase resume (SFT-on-A → continue-on-B …) is the stricter version if needed (deferred).
- **[ship-now, local] c_decide self-play only (no PokerBench).** Local proof uses self-play decisions for both A and C
  (`--pb 0`); PokerBench (the decision-quality bulk) is added on the POD (`--pb -1`) where the HF download + scale fit.
- **[DEFERRED to v2 — the Factorio insight, scoped] persistent multi-street read + plan.** The public betting `line`
  (preflop→river) is ALREADY in `format_spot.Spot` (the brain is not myopic on public actions). MISSING, deferred:
  (a) a DERIVED 6-max villain-range READ as an `api.*` primitive — `range_tracker.py` is HU-only (seats 0/1,
  `state["button"]`), there is NO 6-max range model wired; (b) a persistent hero PLAN/intention carried across streets
  (e.g. "barreling as a bluff") — decisions are currently re-derived per spot from the present line. Both are a v2
  enhancement (a Factorio-agent-style observe→diagnose→adapt loop), NOT part of the frac_bad proof.

## ★ Post-flop formula toolkit (2026-06-17) — GPT-5.5-generated, engine-self-verified (`postflop_formulas.py`)
34 post-flop NLHE calculations (alpha, value:bluff ratios, semi-bluff EV, MDF-by-size, implied/reverse odds, SPR
stack-off, geometric sizing, equity-realization, combinatorics, EV-decisions, draws) generated by GPT-5.5
(`research/postflop_calc_consult`), gated 34/34 by `research/postflop_calc_gate` (each spec's `verify_expr ==
verify_value`), materialized + together-verified (`postflop_calc_materialize`), exposed as `api.<fn>`.
- **CAVEAT (the honest limit of the gate):** `verify_expr == verify_value` confirms the function matches ITS OWN stated
  numeric self-check — i.e. internal consistency + no runtime error — NOT that the formula is the canonically-correct
  GTO identity. A self-consistent but subtly-wrong formula could pass. STRENGTHENING (math_accuracy_strategy layers 2-3):
  (a) sympy SYMBOLIC verification of each closed form, (b) cross-check key fns against independently-known values
  (alpha=bet/(bet+pot), MDF=1−alpha, pot-odds), (c) the EV-truth filter / RL realized-EV is the ultimate arbiter when
  the brain USES them. Until then, treat as a strong PRIOR (frontier-generated, self-checked), not proven ground truth.

## ★ Phase-4 de-risk pilot (2026-06-17) — harness built + methodology verified; GATE-2 NOT yet demonstrated
`training/pilot.py` ranks candidate actions per state by rollout-EV (`training/rl_env.rollout_action_ev`) vs the league.
Methodology shipped + verified: **Common Random Numbers** (all candidates share run-out seeds -> card luck + opponent
mixing cancel) + a **fresh-seed HOLDOUT** re-eval of the selected action (removes the optimizer's-curse / argmax-of-
noisy-estimates upward bias). Fold-floor invariant holds (oracle EV >= 0 where fold is legal). The RL env itself is
verified zero-sum (chips conserved every hand) and the rollout reseed is proven (12/12 distinct showdown run-outs).
- **SMOKE (n=6, k=12): gap −1.67 vs tag** — but this was NOISE/optimizer's-curse, NOT a real absence of signal (see next).
- **FAIR PILOT (CRN+holdout+SEM, n=50, k=24), oracle vs {random, maniac, tag}:** gap **vs random = +4.62 ± 1.92
  (SIGNIFICANT, >2·SEM)**; vs maniac +2.29 ± 1.49; vs tag +2.06 ± 1.63 (positive but ~1.3·SEM, not yet significant).
  -> The realized-EV ranking carries a **real, learnable signal** (significant vs a weak baseline); the lift over a
  STRONG heuristic (tag ≈ a decent SFT-init) is DIRECTIONALLY positive but needs larger n to confirm. The smoke→fair
  flip (−1.67 → +2.06 vs tag) shows denoising (k, n, CRN, holdout, SEM) is essential — small samples lie.
- **CONFIRM LANDED (n=200, k=24): PASS.** gap vs random **+11.03±3.31**, maniac **+5.21±1.77**, tag **+5.62±1.81** —
  ALL significant (>2·SEM). The tag-lift GREW with scale (+2.06→+5.62) = signal, not noise. The #1 pre-spend risk
  (does realized-EV move the needle?) is RETIRED. Caveat: the oracle has rollout FORESIGHT (= the ceiling a learned
  policy approximates) + a tag continuation + the TRAINING league (not held-out) — it proves the reward carries
  learnable signal, NOT that Qwen captures it (that's the real GATE 2, the pod test).
- **HELD-OUT ROBUSTNESS re-confirm (n=50, k=24, league = rock/whale/shark = untrained types):** gap vs random
  **+3.93±1.56**, maniac **+3.27±1.46**, tag **+3.52±1.39** — ALL significant. The EV signal GENERALIZES to opponent
  types it wasn't tuned against = the cross-distribution robustness the theory demands. The pilot's train-league caveat
  is CLOSED. (Closes the only open $0 pre-spend validation except Stage-1, which needs `trl` = pod/venv.)
- **For a STRONG GATE-2 (lift over a good init):** the real lift must come from the LEARNED policy proposing
  better-than-coarse sizings (not enumeration), + AIVAT, + a held-out league. **DO NOT spend on RunPod until the
  tag-lift is significant OR the learned-policy test (GPU) is justified by this $0 evidence.** The pilot did its job.

## ★ Phase-3 EV-truth filter (2026-06-17) — conservative gate heuristics (`pipeline/filter.py`)
The hub's anti-hallucination gate ships three deliberate approximations (all error toward NOT rejecting, so a real
frontier example is rarely lost — we'd rather admit a borderline one than drop it, since RL re-judges by realized EV):
- **[ship-now] call-EV check uses a GENEROUS random range.** G6 rejects a `call` only if hero equity vs a UNIFORM
  random hand + 0.15 margin is still below the pot-odds break-even. Vs a real betting range hero's equity is LOWER, so
  this only ever flags a CLEAR blunder; it does NOT catch SUBTLE -EV calls (hero beats random but loses to villain's
  actual range). By design (false-reject-averse) → the filter is a BLUNDER-catcher, not a fine GTO-judge. EXACT GTO
  comes from RL/self-play realized EV, not the filter. Later: gate vs the range-tracker's posterior range, not random.
- **[ship-now] bet/raise get legality only, no EV check.** Sizing/bluffing judgment is deferred to RL (the filter
  can't price fold-equity without a solved tree). Later: a depth-limited-solve EV cross-check on bet sizings.
- **[ship-now] frontier loop has token-tracking but NO budget cap / cache reuse yet.** One Claude call ≈ 613/135 tok
  (~$0.02 Opus). Before any large `frontier_loop.run`, wire a cost cap + the `llm.Checkpoint` cache (per the plan).
- Lean pod bundle (`orchestrate.BUNDLE`) excludes `knowledge_base/hand_histories` + `books/` — if the trainer/RL env
  ever imports them, add the member (it errors clearly).

## ★ CFV value-net data-gen (2026-06-16) — pilot `k_rivers` approximation + the zero-samples root cause
The CFV-net training data (`extraction/cfv_data.py`) maps (turn board + both ranges + pot) → per-class turn-boundary
CFVs; each sample's label is the mean over the 48 river run-outs of the river-subgame CFV (each river SOLVED by
TexasSolver + extracted via the B1-validated `cfv_eval`). That is **48 solves per sample = ATOMIC + slow** (~12–16 min/
sample on an oversubscribed cpu5c) → the multi-pod RunPod campaign produced **ZERO** samples (no sample completed
inside the post-setup gen window; root-caused 2026-06-16 — `gen()` DOES write incrementally, so the cause was upstream:
the sample never finished). HEURISTIC shipped:
- **[ship-now, pilot] `k_rivers` knob (default 48 = exact).** `turn_boundary_cfv(..., k_rivers=K)` solves K sampled
  rivers instead of all 48 → a sample costs ~K/48 and actually COMPLETES in a short window. The pilot uses **K=12
  LOCAL** (free, no pod contention/setup, ~3 samples/min on 24 cores, incremental writes). TRADE-OFF: with K<48 the
  per-combo averaging count varies slightly → the river-level zero-sum is only APPROXIMATELY preserved (EXACT at K=48
  by the constant-n=46 argument). Fine for the pilot (validate pipeline + first learning signal); a deployable net
  needs K=48 (or large K) on a long run. The pilot net is NOT deployment-grade (tiny n → held-out MAE high, GATE B2
  not met); it proves the end-to-end data→train→save pipeline and gives the first learning signal.
- **NEXT (scale):** deploy needs thousands of K=48 samples. The atomic-sample cost makes SHORT pod windows fail; either
  (a) long single-pod runs that start gen as each pod is ready (no setup barrier — the campaign's `ex.map` barrier idles
  fast pods), or (b) the faster single-turn-solve `dump_rounds=2` + backward-pass path (1 solve/sample, not 48).
- **[VETTED 2026-06-16, o3 + gpt-5.5 — `docs/consults/nextrun_*`] the 48-river-average is the WRONG target, not just
  slow.** It computes "river EV after a forced turn CHECK-CHECK" → OMITS turn betting (Δ up to 10-20 bb on coordinated
  turns; turn-bet-fold nodes are invisible) and isn't even a consistent joint strategy. The CORRECT target = ONE
  `dump_rounds=2` turn+river solve + a single backward-induction pass (the river backward-pass + a river CHANCE node,
  card-removal). Both CORRECT and ~10-40× cheaper → it REPLACES the k_rivers approximation for production labels
  (`k_rivers` stays a pilot-only debugging knob). `train_cfv_net.py` got a target-standardization fix (raw CFVs ±2600
  chips → MSE in the millions; normalize → the net finally FITS; held-out still data-limited).
- **[OPEN RISK, gpt-5.5] 169-class range input may be SUIT-ALIASED.** Two states with identical 169-class weights but
  different combo-level suit distributions (e.g. KhQh vs KsQs on a heart board) can have meaningfully different CFVs —
  and MORE DATA CANNOT FIX missing input information. GATE before any big net run: an aliasing test (same-board /
  same-169 states, different suit-combos → direct-solve → if weighted-CFV-L1 > ~0.75 bb, switch to combo-level /
  board-relative suit-blocker features). Logged so the next-run build can't skip it.

## ★ Preflop blueprint (2026-06-16) — the current #1 fix (deferred-precision items)
The X-ray (`extraction/gtow_xray.py`) localized the −72 vs GTOW to PREFLOP (87%: −50 strategy + −15 all-in spew). We
built a near-Nash **200bb preflop blueprint** (`extraction/preflop_solve.py` — EXACT CFR+ over a real size menu +
a precomputed 169×169 all-in equity matrix) and wired it into `bot.py:_preflop` (loader `strategy/preflop_blueprint.py`,
depth-gated ≥140bb, toggle `use_blueprint` / harness env `POKERB_BLUEPRINT`). The neural fcpa net is SHELVED (measured
**−212** vs GTOW — fcpa is hopeless for preflop, both Nash consults predicted it). HEURISTICS shipped (replace each with
the high-quality real-postflop-continuation version = the GCP scale-up):
- **[ship-now] checkdown see-flop continuation.** Non-all-in showdowns are scored as a checkdown run-out (w·pot−inv) —
  NO postflop play. EXACT for all-in nodes (run-it-out → the all-in discipline is right), under-models OOP realization.
- **[ship-now] κ=0.05 IP-realization premium.** A zero-sum bump (peaks at marginal hands, SB is IP postflop) on
  see-flop leaves — corrects the checkdown's OOP over-defense (72o-vs-open call 0.38→fold 0.98 with κ). Heuristic;
  A/B-able via `--realize-kappa`; real value needs a postflop solve.
- **[ship-now] value-only jam clamp (`bp_jam_min_pct=0.90`).** The checkdown is BLOCKER-BLIND → 5bet/jam-bluffs the
  wrong hands (76s jam 0.59 = a 200bb spew). The bot clamps jam/5bet to top-10% at 4BET/5BET. The real GTO 5bet-bluffs
  (A5s-type blockers) need a blocker-aware solve to recover the (small) bluff EV.
- **[robustness] facing-a-shove detection** = `villain.all_in OR (owe>0 and cannot raise)` — the adapter can hide an
  all-in stack (`gtow_to_state` coerces 0→start); without this a 200bb jam mis-maps to 5BET (not JAMSB) and QQ CALLS
  it = the spew re-introduced. CAUGHT by a synthetic unit test (Fable-5).
- **[200bb-only] depth gate.** Solved at 200bb; gated to eff_bb≥140 (GTOW = 200bb). 100bb apps fall through to the
  heuristic → a 100bb blueprint is a later add.
- **GATE:** the GTOW AIVAT A/B (`use_blueprint` ON vs OFF, n≥2500) decides whether it ships. DEFERRED (GTOW resting).

## ★ Range-tracker keystone (2026-06-16) — turn/river defense → a SHARP resolver
The resolver (`resolver.py`) was measured NEUTRAL because `range_tracker._p_call` reweighted villain's range on a CALL
only on the FLOP → turn/river calls fell to legality-only → ranges too wide → un-sharp solve. Fixed: a multi-street
turn-defense advisor (`defense_advisor.pt`, retrained on flop+turn+river, GATE A2 +46% turn vs strength-only) + a
1-line widen of `_p_call` to ALL streets. GATE A3 (`extraction/check_range_l1.py`, Solver=truth, held-out): the update
HALVES the range-L1 (turn +60%, reaches flop sharpness) → grounded per the o3 bound (exploitability ≤ (pot/2)·L1).
HEURISTICS shipped:
- **[ship-now, MEASURED-safe] fixed `size_faced=0.66` on the call-update.** `_p_call` queries the defense advisor at a
  typical-c-bet size, NOT the ACTUAL bet faced (the live tracker doesn't thread the pot/bet magnitude into the call
  reweight). At a too-SMALL queried size the range only errs WIDE (o3-safe = conservative); the danger direction
  (a tiny real bet → over-narrow) is bounded + rare. River is the loosest (A3 river-L1 0.525 vs flop 0.399) because
  river sizes vary most (0.75–10× pot) → thread the real `size_faced` into `_update_action`'s call branch IF a
  river-only A3/eval shows it matters. Cheap, deferred until measured-needed.
- **[ship-now] uniform-prior A3 metric.** `check_range_l1` measures the call-UPDATE operator with a uniform prior (to
  isolate it); the live prior is the preflop-narrowed range. The DELTA (advisor vs do-nothing) is a fair operator
  measure; the absolute L1 is not the real-game range error (which also carries the prior's own error).
- **[2026-06-16 DONE+grounded] the FLOOR is now wired to the tracker (the keystone's second half).** The resolver got
  the tracker earlier this session (above); the FLOOR — which plays the MAJORITY of hands — still used
  `_villain_range`+`_narrow` (keep top-X%-by-board-strength, every bluff/draw DROPPED) → it fed `equity_vs_range` an
  artificially-strong range → systematic OVER-FOLDING facing bets (CLAUDE.md's "poisons the floor's facing-bet/
  bluffcatch math"). GATE A3-FLOOR (`extraction/check_floor_range.py`, held-out by board, Solver=truth): `_narrow`
  L1 **0.756 ≈ uniform-random 0.995** (near-worthless); the tracker is **0.437 = +42% closer to truth** (flop +51 /
  turn +44 / river +30). Wired in `bot.py` (`use_range_tracker`, `_tracked_villain_range`, new
  `equity.equity_vs_weighted_range`); `_narrow` kept as the `<CONF_THRESHOLD` fallback (o3-safe). EV A/B
  (`pokerbot/benchmark/range_tracker_ab.py`, duplicate, n=250): head-to-head ON>OFF **+50.5 ±40.7** (~1.2σ, fixes the
  over-fold leak); vs GTOBaseline paired **−31.4 ±58** (within noise, NO significant regression). DECISION: KEEP ON —
  the grounded range-L1 is the trusted gate (the bb/100 vs the analytic GTOBaseline is the noisy regression-catcher,
  and GTOBaseline isn't a solver so a solver-grounded range model is benignly mismatched to it). DEFINITIVE EV decider
  = the GTOW AIVAT A/B (`POKERB_RANGE_TRACKER=1` vs `0`, wired into `gtowizard.py`, fires when the server recovers).
- **[OPEN, deferred] the resolver EMIT is still 169-CLASS (suit-aliasing).** `range_tracker.emit` aggregates the
  per-combo range to class-level (TexasSolver v0.2.0 can't usably take per-combo strings) → KhQh/KsQs collapse on
  monotone/flush boards. NOTE: the FLOOR path just wired uses the per-combo weights DIRECTLY (no emit → NO aliasing),
  so this affects ONLY the resolver. gpt-5.5's 169-aliasing test (the CFV-section item above) is the gate for whether
  the resolver emit needs combo-level / board-relative suit-blocker features; not yet built.

## ★ Solver-grafted preflop (2026-06-16) — the checkdown leaf was CIRCULAR; grafting real-play leaves + re-solve PASSES the non-circular gate
The blueprint scored every see-flop leaf with a pure-equity CHECKDOWN (`w = e + κ·4e(1−e)`, κ=0.05 a GUESS) that
OMITS all postflop betting. We replaced it with REAL TexasSolver postflop-continuation values, then re-solved. Pipeline:
`preflop_ranges.py` (reach-weighted ranges per see-flop node) → `preflop_calibrate.py` (200bb flop solves + MC rollout
of the solved strategies → measured realization `w_node`; lean 1-size tree) → `preflop_leaves.py` (re-level κ PER NODE
to match w_node; `leaf_w` default = byte-identical checkdown) → `preflop_solve.py --leaf-table` re-solves →
`preflop_blueprint_solvergraft.json`. NON-CIRCULAR metric (`preflop_exploit.py --leaf-table`, o3's recommended gauge):
in-model checkdown expl **3.31** but independent-leaf expl of the SAME blueprint **6.12** (checkdown UNDER-stated the
gap ~2× — o3's "equilibrium of the wrong game"); re-solved-for-grafted-leaves **2.03** → **GATE PASS (−4.09)**.
`w_node(OPEN)=0.556` over 16 flops (spread 0.507–0.624; dry boards realize more). HEURISTICS / DEFERRED-PRECISION:
- **[ship-now, MEASURED-caveat] κ_OPEN ≈ 0** (vs the 0.05 guess) from a LEAN 1-size solve tree. The lean tree likely
  UNDER-realizes → κ_OPEN≈0 is a LOWER bound. **A full RICH tree (2 bets + raise) at 200bb is INTRACTABLE locally**
  (verified: 3 concurrent rich solves OOM/timeout before dumping — the raise sub-tree is the deep-stack branching
  killer). A MIDDLE tree (2 bets, no raise) is the tractable richness check (`--mid`; running). So the κ MAGNITUDE
  carries an irreducible-at-200bb lean-tree caveat; the STRUCTURAL finding (checkdown optimistic; graft+re-solve lowers
  non-circular expl) is robust to it.
- **[OPEN-only so far] only the OPEN (SRP) see-flop node is grafted; the other 5 (LIMP/ISO/3BET/4BET/5BET) still use the
  checkdown κ=0.05.** Next: calibrate 3BET/4BET (the other common see-flop pots). The shallow nodes (4BET/5BET, low SPR)
  solve fast; LIMP/ISO are rare (low reach) → low priority.
- **[proxy, not the arbiter] independent-leaf exploitability is a NON-CIRCULAR LOCAL proxy** (simplified preflop game +
  solver leaves), NOT the GTOW bb/100. The −30 verdict = the GTOW AIVAT A/B comparing `preflop_blueprint_solvergraft`
  vs the checkdown blueprint (wire behind an env toggle; GTOW server-blocked). Plan: `.claude/plans/gut-dann-sind-wir-toasty-forest.md`.
- **[rollout MC] `flop_realized_ev`** samples the solved strategies (1 runout/sample → bimodal per-sample, averages to
  the realized fraction). Zero-sum is automatic (single net/sample). Fidelity L1 = flop betting + a turn/river CHECKDOWN
  (captures flop fold-equity; omits turn/river betting). L2 (flop+turn betting, dump_rounds=2) is the deepen if needed.

## ★ Neural self-play GTO core (2026-06-16) — SHELVED (measured −212 vs GTOW; needs a real bet-size abstraction)
We PIVOTED to a from-scratch neural **Deep CFR self-play** net (`strategy/deep_cfr.py` Leduc, `deep_cfr_hunl.py` HUNL,
`deepcfr_adapter.py` net→bot) because the solver-imitation floor is a MEASURED ceiling (~−72 vs GTO Wizard, broad
postflop, run-to-run noise ±8). Pure self-play, no imitation (AlphaGo-Zero logic). DEFERRED-PRECISION items to fix
(scoped in `docs/NEXT_RUN_TODO.md`, vetted vs 4 sources incl. Supremus + the AAAI-26 DCFR+ paper):
- **[ship-now, fix next run] fcpa betting abstraction** (fold/call/POT/all-in) is "structurally impoverished" (can't
  express geometric sizing / overbet / merge-bets). Next: `0.33/0.5/0.75/1/1.25/2/allin`. THE Rank-1 lever.
- **[ship-now, fix next run] 20-dim strength-bucket features** collapse exactly what GTO needs (range-polarity,
  blockers, SPR, texture). Next: card-occupancy + hand-class/draw/texture flags, ideally the OpenSpiel
  universal_poker information-state tensor. NOT WEVA (vetted low-ROI for full HUNL).
- **[done on Leduc, port to HUNL] DCFR+** (discount+clip+bootstrap of cumulative ADVANTAGES) — took the neural Leduc
  run 445→338 mbb (LinearCFR plateaued ~445); the HUNL trainer is still LinearCFR → port it.
- **[deferred] variance-reduction baseline net** (DREAM/PDCFR component 3) — real but secondary for EXTERNAL sampling;
  add only after validating the abstraction direction + on Leduc exploitability first (an unvalidated ES baseline biases).
- **[deferred — the eventual ceiling] CFV value net + depth-limited continual resolving** (Supremus/DeepStack). Policy-
  net-only likely plateaus below GTOW parity; resolving is the path to near-0. A full architecture, not a patch.
- **VALIDATION GATES (math theory):** (1) Leduc EXACT exploitability (the correctness gate); (2) the clairvoyance
  toy-game — the net must bluff at α=s/(1+2s) (=1/3 at pot) + defend at MDF=1/(1+s) (=1/2 at pot), ±0.05, RIVER ONLY
  (river-MDF does NOT hold on flop/turn — semi-bluffs). See `docs/math_theory_net_connection.md`.
- **CONTAMINATION BOUNDARY (hard rule):** the pure self-play core is NEVER trained on imitation data. Books/papers →
  validation+design; PokerBench → a real-HUNL GTO-match validation set; Pluribus → eval-distribution + exploit overlay;
  OpenSpiel → feature representation + the fast-traverse pod path; the LLM → exploit overlay. None are training labels.
- **Compute reality:** the bottleneck is the Python MCCFR traverse (CPU), NOT the net → a B200 does NOT help the
  current code (measured slower for tiny nets). The pod helps ONLY via OpenSpiel's C++ traverse (`deep_cfr_nlhe.py`)
  or a vectorized rewrite. Cheap first win: multiprocess the traverse locally.

## Deferred precision (compute exactly later)
- **[2026-06-15 ✅ table + OOP wired] GTO donk + c-bet frequencies by texture.** EXTRACTED to
  `knowledge_base/postflop/texture_freqs.json` (`extraction/texture_freqs.py`, 1340 boards). OOP donk now wired
  PER-TEXTURE in `bot.py` (`_texture_freq`): monotone 12%≈GTO 14%, ALL 22%≈21% on the floor map. REMAINING:
  (a) the IP c-bet is still ~87% vs GTO 74% (value-always-bets); (b) the per-texture donk/c-bet HAND-SELECTION
  (which hands, not just the frequency) + SPR/position split. Both handled holistically by the supervised
  advisor (#36–41), which learns frequency AND selection from the same caches.
- **[2026-06-15 ⏳ solving] Turn advisor (#41) full coverage.** `turn_advisor.pt` is PRELIMINARY (turn nodes of
  only 46 flop files; +23% vs freq baseline, held out over 2189 turn boards). A robust 8h RunPod turn-coverage
  solve (DUMP=2, pod szx1z9in3g1rve, ~350 boards/h) is running. WHEN DONE: rerun `extraction.build_turn_data`
  then `extraction.train_turn_advisor` on the pod, pull `turn_advisor.pt`, then `runpod_run --kill`. See the
  auto-memory `active-runpod-turn-solve`.
- **[2026-06-15 ✅ river advisor wired (WS2)] River blocker nudges (#40).** `bot.py:_river_blocker_signal` biases
  river bluff SELECTION + nudges the bluffcatch threshold ±6%. The river-subgame solve (`_gto_river_cache`, 1308
  boards) now exists → a solver-grounded RIVER advisor (`river_advisor.pt`, +51% vs the freq baseline) SUPERSEDES
  the #40 bluff-SELECTION heuristic on the betting node (per-hand solver P(bet), OOP-lead/IP-after-check). The #40
  BLUFFCATCH nudge (facing a bet) stays active (disjoint node). The 3500 "value" rank bar etc. now only matter on
  the rarely-hit no-advisor fallback. Net: the river is solver-grounded, not heuristic.

## Open questions
- **[2026-06-15 ✅ RESOLVED — the −13 was a small-sample mirage] MVP#2 river resolver vs GTO Wizard = decision-grade
  −72.06 ±6.70 (n=2498), NOT −12.9.** Real-time TexasSolver re-solve of the river public state (`strategy/resolver.py`
  + `range_tracker.py`, `bot.use_resolver`). The 2500-hand confirmation gave **−72 ±6.7** (tight); the −12.9 ±69.6
  (n=150, RAW +200) was a LUCKY sample (−13 lay inside its own ±70 CI of −72). **−72 < Always-Fold (−64.6)** ⇒ fed the
  preflop-line-only (too-wide) ranges, the resolver confidently plays the WRONG equilibrium in big pots and SPEWS —
  the empirical confirmation that the **Bayesian action-consistent postflop range tracker is a PREREQUISITE**, not a
  refinement (without correct ranges the resolver HURTS). MVP#1 floor −33 was n=30 (unreliable); floor baseline at
  n=2500 pending. LESSON (again): small AIVAT samples (n≤150) lie — only n≥2500 is decision-grade. NOTE: GTO Wizard Benchmark paper
  (arXiv 2603.23660) VALIDATES MVP#2 — GTO Wizard AI = real-time-solving + value-net + balanced ranges, beat
  Slumbot +19.4/150k; the LLM failure mode = FREQUENCY/MIXING mistakes (exactly what the resolver fixes).
  Leaderboard: GPT-5.3 −16, Opus 4.6 −20.4, Opus 4.5 −22.3, Gemini −30.8, Grok −60. Bench = HUNL 200bb, 5000
  hands/agent. Next per the GTO-gap: turn resolver (P2) + a $140 RunPod multi-CPU mass-solve for a richer
  public-state blueprint (P3) / CFV value net (P4).
- **[2026-06-15] Run 2 duplicate watch.** The OOP-donk cap (`oop_donk_freq`) improved the solver-gap (the
  primary gate) but the duplicate-vs-GTOBaseline point moved −1.4 → −34 ±105 bb/100 (within noise, no disaster).
  Verify at scale (≥600 decks), AND check whether checking-more-OOP exposes a DOWNSTREAM leak vs the aggressor's
  c-bet (the flop-only solver-gap can't see that) — i.e. is our facing-c-bet defense after checking OOP sound?
  Knob: `PokerBot.oop_donk_freq` (currently 0.5 → ~25% donk; lower to approach GTO 20%).
- **[2026-06-15 ✅ RESOLVED] WS1 floor-bleed ablation (the −102 vs Slumbot).** `pokerbot/benchmark/floor_ablate.py`
  (600 decks, paired/duplicate, deterministic, vs GTOBaseline; 4 A/B toggles on `PokerBot`). full_floor = **−25.3
  ±40.6 bb/100** (NOT significantly losing — ~0.6σ from break-even). Paired Δ vs full_floor: #40 river-blocker **+0.0
  ±0.0** (zero effect), #41 turn-advisor **+8.3 ±20.0** (sub-1σ), fe-sizing −3.4 ±4.1 (mildly HELPS), mdf-shade +0.0
  (inactive on the floor: conf=0 ⇒ shade=0). **Verdict (c): the −102.5 ±44 vs Slumbot @2000h is variance /
  Slumbot-specific — NOT a reproducible floor leak nor a #40/#41 regression vs near-GTO.** Decision: do NOT gate
  #40/#41 off; do NOT pre-fix (this also closes the "Run 2 duplicate watch" above — verified at ≥600 decks). WATCH
  (don't fix, sub-2σ): #41 turn-advisor may cost ~8 bb/100 vs near-GTO. Caveat: duplicate-vs-GTOBaseline bb/100 has
  ±40 residual variance at 600 decks (the two strategies diverge into high-variance lines) → the per-spot multi-street
  GTO-gap (WS4, extending `floor_map`) is the sharper floor-quality instrument; also confirm with one large-N Slumbot run.
- **[2026-06-15 ✅ WS2 river advisor + a WS3 hand-off].** Built `extraction/build_river_data.py` +
  `train_river_advisor.py` from `_gto_river_cache` (293k rows / 1308 boards). The MLP beats the freq baseline by
  **+51%** (MSE 0.098→0.048) → `river_advisor.pt` saved + wired (`advisor.py` river file; `bot.py` river branch
  after `_river_exploit`). PAIRED floor effect: **river-advisor ON vs OFF = +38.6 ±15.6 bb/100 (~2.5σ)** vs
  GTOBaseline — a real river-leak fix (NOTES leak #4). Also made the exploit engine safe vs the now-strong floor:
  `_river_exploit` baseline is now the floor's ACTUAL action (`_river_floor_kind`), not a bare check, so it can't
  override a good floor bet with a worse one. **WS3 hand-off (from `exploit_proof`, −24 vs the over-folder):** the
  river engine fires **0×** vs the folder — a cold-start OFF-TREE EXPLORATION deadlock (can't learn a size's fold
  rate without betting it; the floor only ever bets GTO sizes, never the overbet cliff). The −24 is the OLD
  conf-driven overlay (`bluff_base`/MDF-shade via `self.opp`) betting non-cliff sizes, NOT the river engine. BOTH
  are exactly what WS3 fixes: merge the `ProbeController` (off-tree size-sweep → breaks the deadlock, re-enables the
  proven +28 cliff edge ON TOP of the strong floor) + replace the crude conf-overlay with the LCB-gated engine.

- **[2026-06-15 ✅ WS3 unify (one MVP)].** `PokerBot(exploit=True)` is now THE single MVP = solver-grounded floor
  (flop/turn/river advisors) + the exploit-primary river EV-engine + the conf-overlay + a NEW bounded,
  PREDICTION-GATED off-tree size **probe** (`_river_probe`): when the floor gives up an air hand AND an over-fold is
  already observed at a sampled river size, it occasionally bets an under-sampled LARGER size to map the fold-curve
  (discover a size-cliff), budget-capped (worst-case reserved vs a 120bb session budget → can't run away). This is
  the AdaptiveExploiter's probing idea ported in; the Dirichlet per-node model IS the calibration (it observes real
  fold rates per node). The standalone `AdaptiveExploiter` is kept as a labelled REFERENCE (interface differs; the
  scorecard measures `PokerBot` via `--hero mvp`). exploit_proof vs the synthetic cliff-only over-folder:
  **−7 ±24** (was −24; the probe explores + wins vs the over-folder, lifting exploit-primary to ≈floor — within
  noise, no regression). Honest: vs a pathological cliff-only folder (calls normal bets) principled play can't beat
  the strong floor without risky blind overbets the prediction gate correctly avoids; the exploit's real edge shows
  vs opponents that over-fold at NORMAL sizes (Slumbot folds 54% to 0.66) → measured in WS4. Fast-follow if WS4
  shows the flop/turn exploit needs it: port the TwoModelGate cross-confirm + the explicit Calibrator.

- **[2026-06-15 ✅ WS5 GTO Wizard harness ready-to-fire + ⚠ KEY MAY BE PRESENT].** Built `benchmark/gtowizard.py`
  = the pure, OFFLINE-UNIT-TESTED adapter (GameServiceResponse↔ActRequest: board parse, legal-dict, action+
  raise_range clamp, `PokerBotAgent`) + `config.GTOWIZARD_API_KEY` (read from `Secret keys\GTO Wizard API Key!.txt`,
  env override, never committed; `tools/` already gitignored). Self-test passes (preflop AKs→raise, flop QQ→check,
  river→call, all legal). **The key file now reads a 32-char no-space string (looks like a REAL key)** despite the
  user earlier saying it was empty → the requested key may have ARRIVED. Per "assume it never comes" + outward-facing
  /quota, NO live run was started. CONFIRM-ON-CLONE items before going live (need a real GameState): action_history
  verb format, hero-seat index, to_call derivation. To go live: clone `gtowizard-ai/researcher-api-client` under
  `tools/gtow_client/` (Python 3.13/uv), subclass `PokerBotAgent`, run `--num-hands 200` to validate, then ≥2500 for
  the AIVAT bb/100 + leaderboard = the DEFINITIVE measurement vs the true opponent.

- **[2026-06-15 UPDATE to the WS5 entry above] WENT LIVE -> `401 Unauthorized`.** The 32-char string in the key
  file is REJECTED by the API (placeholder / not-yet-granted; the user's "it's empty" was essentially right).
  Verified UP TO AUTH: client cloned + `uv sync` (Python 3.13 + deps); `gtowizard.py` REBUILT against the REAL
  schema (hero = the seat whose hole_cards is non-null, to_call = total_pot-common_pot, action_history `bX`/`_`
  parsing, SB=button, a legality guard so we never emit an illegal action, AIVAT+winnings per hand); secure runner
  `tools/gtow_run.py` (key from config, never logged) CONNECTS -> the clean 401 proves the wiring is correct.
  **Blocked only on a VALID key.** Then: `uv pip install treys torch numpy` into the client venv + register a
  `pokerbot` agent + `python tools/gtow_run.py --agent_type pokerbot --num_hands 2500` = the definitive AIVAT bb/100
  + leaderboard. Until a valid key exists, the KEY-FREE `scorecard.py` is the definitive measurement.

- **[2026-06-15 ✅ TexasSolver benchmark — gap + head-to-head].** Two "vs TexasSolver" measures (the local
  near-GTO stand-in while GTO Wizard is 401-blocked):
  (A) **Deterministic GTO-gap** (`floor_map` extended flop+turn+river): the MVP floor's action-kind divergence from
  the solver, 250 boards. **FLOP 31% gap** (frequencies MATCH: our-bet 47% vs GTO 47%, IP 75/74, OOP 22/22);
  **RIVER 29%** (our-bet 30% vs GTO 31%, OOP 18/18). Honest read: the FREQUENCIES match tightly (the GTO property);
  the ~30% per-hand gap is largely the solver's OWN mixing/indifference (a 50%-bet hand contributes 0.5 gap
  regardless), NOT a leak. TURN not locally measurable (local `_gto_bench_cache` is DUMP=1 flop-only; the DUMP=2
  turn subtrees were on the now-killed pod) — but the turn floor is advisor-grounded (+20% on the pod).
  (B) **Head-to-head bb/100** (`benchmark/gto_oracle_match.py`): MVP postflop vs a TexasSolver-DRIVEN oracle
  (PokerBot GTO preflop + live per-spot solves postflop; 40bb/SPR~7 + lean bet tree for speed; range-consistent SRP
  dealing). The oracle is genuinely solver-driven (0 floor-fallbacks in the smoke). Live solves → small NOISY
  samples (±~100+ bb/100) — a directional least-loss sanity (off-tree edge invisible, as vs GTO Wizard), NOT a
  precise number; the GTO-gap (A) is the precise measure. **Result: +184.6 ±132.9 bb/100 (n=50, oracle 134 decisions
  solver-driven, 0 fallbacks).** HONEST read: +184 vs *true* GTO is impossible — the oracle is APPROXIMATE GTO (full
  SRP ranges with NO continuation-narrowing → on turn/river it solves with too-wide ranges = mis-calibrated; + lean
  tree + iters=40 + 40bb), so our exploit-primary bot is EXPLOITING those approximations (the wrong turn/river
  ranges), not beating GTO; and ±133 = only ~1.4sigma (noise in play). So: "we crush an approximate-solver bot"
  (consistent with the thesis), NOT "we beat GTO". A truer head-to-head needs continuation-range propagation +
  richer solves (deferred, the hard part) → the number would regress toward break-even. The frequency-faithful
  GTO-gap (A) is the trustworthy "how close to GTO" signal.

- **[2026-06-15 ✅ DEFINITIVE TexasSolver head-to-head (PAIRED) — the MVP LOSES to solver play].** The n=50 UNPAIRED
  head-to-head (+184) was CARD VARIANCE. The PAIRED run (`gto_oracle_match.py`, 80 decks = 160 hands, card luck
  cancelled = the gate we trust) FLIPS THE SIGN: **MVP −160 +/- 75 bb/100** vs the solver-oracle (400 decisions
  solver-driven, 0 fallbacks). So the MVP LOSES to solver-grade play (~2sigma). HONEST: our floor matches solver
  FREQUENCIES (the GTO-gap 31%/29%) but loses full-hand bb/100 — the gap measures only bet-vs-check at the lead/cbet
  nodes; it does NOT capture SIZING / facing-bet DEFENSE / turn-river LINES, where the real EV leak sits. This
  reconciles WS1 (≈break-even vs the WEAK analytic GTOBaseline) with losing to the STRONGER actual solver + near-GTO
  Slumbot (−102): the floor's gap to true GTO is REAL + bigger than the analytic proxy showed. The edge is vs the
  EXPLOITABLE field (we crush); vs solver-grade play we LOSE → least-loss NOT yet achieved. Caveats: ±75 (~2sigma,
  loose magnitude); the lean-tree/40bb oracle is approximate (allin-heavy → may hit our allin-defense specifically →
  some inflation) BUT a weaker-than-true-GTO oracle means the true-GTO loss is >= this. NEXT high-leverage: close the
  facing-bet-defense / sizing / turn-river-line gap (the gap-match alone is not enough). Lesson re-confirmed: PAIR
  everything; the unpaired +184 was noise.

## Suspected leaks to review (ASSUMED, not yet measured — from the 2026-06-15 GTO-frontier consult)
These are hypothesized real leaks the consult (gpt-5.5 + o3, Claude-vetted) flagged. They are ASSUMED, not
measured — review each via the reach-weighted SOLVER EV-GAP once Move A makes the LBR trustworthy (Move B = the
EV-gap audit, Move C = river calibration, Move E = sizing/MDF audit). Do NOT fix on assumption; measure first.
1. **History-free floor averages incompatible info-sets** — the advisor conditions on board+hand features only,
   not line / SPR / position / range-asymmetry (K72r in BTN-vs-BB SRP ≠ in a 3-bet pot). Structural; the FIX
   (range/line-conditioned model) is the "add complexity" trap → MEASURE the cost (Move B), don't rebuild now.
2. **"Fold-equity-optimal sizing" ≠ EV-optimal** — max(folds) ≠ max(EV). Audit per-size solver-EV (Move E).
3. **MDF-shading may not be EV-grounded** — MDF is the wrong model vs underbluffers; is our bluffiness-shade
   EV-justified or a hand-wave? Verify, don't assume.
4. **River is heuristic, not solver-calibrated** (#40) — the most exactly-solvable street; calibrate (Move C).
5. **Advisor trained on P(bet)/action-match, not EV-gap** — can match frequency while bleeding on rare
   high-EV-gap nodes; the gate should be reach-weighted EV-gap, not MSE (Move B).
6. **Confidence-gated blend not provably globally safe** — local confidence ⇏ global low exploitability.
7. **Preflop 88.6% action-match** — the missing 11.4% could be low-EV indifference OR high-EV blunders; EV-gap
   audit needed (Move B).
8. **6-max independent-seat** — structural vs Pluribus-style joint reasoning; PARKED (not HU; consolidation phase).

## Exploit-primary crush-test #1 (2026-06-15) — right direction, NOT yet proven
First Slumbot crush-test of the exploit-primary river engine (`--exploit-primary`, seeded from slumbot_fold.json,
500 hands each, NO live-learning yet): **FLOOR −41.6 ±75.5 vs EXPLOIT-PRIMARY −26.4 ±79.4 bb/100, delta +15.2**
(in the predicted +8–15 corridor) — the engine fires + loses 15 bb/100 LESS than the floor. BUT: (a) both still
LOSE absolutely (Slumbot is near-GTO → ceiling ~break-even, no "crush"); (b) NOT significant — the unpaired delta
is ±~109 over 500 hands, and the floor alone swung −14.6 → −41.6 across runs (pure ±~80 variance). Encouraging,
unproven. Mechanism validated (safe-by-construction, fires correctly); the EDGE needs data. NEXT to make it
conclusive + grow it: (1) wire **live-learning** (`observe_hand_end` from the full hand history → the Dirichlet
model sharpens per-node during play instead of clinging to the thin n=8–39 seed); (2) run **2000–5000 hands** to
beat the ±noise. Re-probing Slumbot for a sharper fold-curve would also strengthen the seed.

## Exploit-primary LOUD proof (2026-06-15) — the engine's edge is per-SIZE / off-tree structure (PROVEN)
`pokerbot/benchmark/exploit_proof.py` (hero vs a parametric river over-folder, PAIRED decks, 1500 hands):
- vs a **FLAT** 70% over-folder: exploit-primary **+9 ±13** over the floor (NOT significant) — the heuristic floor
  already handles a flat leak.
- vs a **SIZE-CLIFF** folder (folds 20% to 0.5pot but 82% to overbets): exploit-primary **+28 ±11 (~2.5σ)**. The
  floor bets a FIXED heuristic size and cannot target the cliff; the engine LEARNS the per-size fold-curve and
  picks the max-fold (overbet) size.
**=> The engine's UNIQUE value is exploiting SIZE-STRUCTURE / off-tree mis-defense the floor's fixed-size heuristic
misses = the "killer cutoff" attack.** Slumbot's seed-curve already shows a rough cliff (0.66→54.5%, 2.0→62.5% vs
1.0→37.5%) = its abstraction artifacts → the engine should capture similar structure live. NEXT systematic step:
an ACTIVE off-tree size-sweep probe to map Slumbot's per-size cliffs finer than the 6-point seed, then hammer.

## Move A result (LBR falsification, 2026-06-15) — v1 eval unreliable; the paired A/B is the usable win
`pokerbot/benchmark/lbr_falsify.py` (300 hands, paired/duplicate) PROVED the v1 LBR is NOT a trustworthy
ABSOLUTE exploitability gate:
- **Range-blind** (uniform card re-sampling): injected c-bet-air / river-overbluff → paired-delta +123 / −31
  bb/100 (~0) despite firing 99/95 of 300 — the LBR can't see the corrupted RANGE.
- **Under-exploits** (passive-after-move): even an EXTREME over-folder is only +289 ±175 (fold-any-bet) /
  +323 ±175 (overfold-50) — directionally right (fold-response > range) but NOT 3σ at 300 hands.
- clean LBR +141 ±298 (was −487 pre-reseed; still within noise).
**Usable byproduct:** `lbr_bb100` now reseeds `g.rng` + the rollout RNG PER HAND → a PAIRED/DUPLICATE A/B
harness (same decks across bot versions → leak-free hands cancel) = a low-variance gate for a change's EFFECT.
**Use this as the change-gate now.** LBR v2 (Bayesian action-consistent range + multi-street best-response) is
the real ABSOLUTE-exploitability fix — DEFER until a change needs an absolute number (on consolidation phase,
don't build speculatively).

## Raise-facing-bet is UNMODELED in the range tracker (v3.3 candidate, mechanism-proven 2026-07-05)
`range_tracker.update` (:215) treats villain's raise/all-in FACING A BET as legality-only — the single most
range-defining action narrows nothing. Reproduced 30/30: PRINCE calls a turn check-raise-JAM in a 4bet pot with
K2o second pair ("37% >= MDF 21%") because the 37% is MC equity vs the un-narrowed range; a jam range there is
nutted (RANK4 cell: 7 hands x -13.8bb = ~-4 bb/100). Fix sketch: on raise-facing-bet, filter villain to the
top-R% by board strength + a census-calibrated bluff share (R from GTOW's revealed raise frequency at that node
class, data/freq_targets/gtow_frequencies.json); secondary root = the flat 50% bluffiness shading on jam nodes.
Gate ladder as usual; ONE lever at a time (v3.2 thin-value is in flight first).

### v3.3 calibration (mined 2026-07-05, $0, from data/freq_targets/gtow_frequencies.json = 13.5k hands)
GTOW raise-range composition P(class|raise), all postflop facing-bet nodes (check-raises included):
- FLOP: raises 8.9% of facing-bet nodes; composition air 49% / pair 17% / two-pair+ 17% / top-pair 15% / monster 2%
- TURN: raises 6.1%; two-pair+ 32% / air 31% / pair 18% / top-pair 11% / monster 8%
- RIVER: raises 12.2%; two-pair+ 38% / monster 18% / air 16% / pair 16% / top-pair 12%
=> the raise range is POLARIZED, not uniformly nutted, and the polarity tightens by street. DESIGN CONSEQUENCE:
the raise-facing-bet narrowing must be SIZE-AWARE (a normal raise keeps a large bluff share; a raise-ALL-IN in a
3bet+/4bet pot is the nutted case that killed K2o). Build step: extend freq_mine with a raise-size split (jam vs
normal) before wiring the filter — the 62-76 raise counts per street are too thin to split from the book alone,
mine the raw logs (both holes are always logged).

## Audit 2026-07-05 — deferred confirmed finds (fix when convenient; full ledger data/audit/audit_result.json)
- slumbot.py bridge emits no 'deal' history rows -> the range tracker walks nothing postflop yet reports
  confidence ~1.0 (resolver fires line-blind) — Slumbot is background-validation only, fix before the next
  Slumbot campaign.
- tools/gtow_client main.py act-loop never presents the terminal state -> observe_hand_end/live-learning is
  dead code in live runs (irrelevant under exploit-OFF profiles; matters if an exploit arm ever runs live).
- gto_oracle _cache_key omits allin_threshold — DELIBERATELY deferred: adding it invalidates the warm solve
  cache (hours of re-solves); include it only when != default at the next planned cache flush.
- classify_board 'twotone' (maxsuit==2) is true on ~every 5-card board -> tex['dynamic'] vacuous on rivers.
- v3.2 thin_to can be clamped up by raise_min in sub-3bb pots (unreachable in practice; noted for completeness).

## 'Big RAM CFR' = Johanson-Thesis 2007 — RAM-Hebel-Karte (agent-gelesen 2026-07-05; Maschine real: 15.7GB)
- GEBAUT: **ISO-Cache** (POKERB_ISO_CACHE, default OFF) — suit-kanonischer Solve-Cache-Key + Hole-Map am
  Lookup; BEWIESEN end-to-end (permutiertes Board -> Cache-Kollaps 5.0s->0.0s, identische Strategie). Bis 24x
  Hit-Rate auf dem 12GB-Cache -> weniger Live-Floor-Fallbacks. Exakt, weil Ranges KLASSEN-level sind.
- QUEUE #1 (der grosse): **kanonische FLOP-Solve-BIBLIOTHEK** (GS2-Praezedenz: 135k vorgeloeste Abstraktionen)
  — Praecomputation umgeht das doppelt bestaetigte Flop-Live-NO-GO komplett; ~200 Top-Flops x Census-Lines als
  Hintergrund-CPU-Job (1-2 Tage) oder Pod; zielt auf die Flop-Bleed −6.4…−8.3. POKERB_RSV_FLOP, volle Leiter.
- QUEUE #2: 7-card-LUT-Evaluator (~124MB RAM, verhaltenserhaltend) + EXAKTE Turn-Enumeration statt MC
  (Qualitaet: entfernt die ~0.9pp MC-SE aus Grenzentscheidungen; aendert Entscheidungen -> eigener Arm).
- KORREKTUR einer stalen Memory: River-Equity ENUMERIERT bereits exakt (equity.py:49-102) — der alte
  'river should enumerate'-Notiz-Punkt ist LAENGST implementiert.
- RNR (Kap. 5) = die Formalisierung unseres Nordstern-'bounded exploit overlay' (Theorem 6: Best Response
  unter Exploitability-Budget); via DBR-2009 (p pro Node nach Beobachtungs-Konfidenz = unser tracker.confidence).
  Bewusst DEPRIORISIERT vs GTOW (Harvest ~0, Dossier) — bauen, wenn Pools/Menschen die Mission sind.
- Mr.-Orange-Trick (Kap. 7): Equilibrium im PERTURBIERTEN Spiel (+7% Sieger-Utility) = aggressiv aber nur
  35mb/g exploitierbar — Kandidat fuer den River-Aggressions-Leak, braucht eigenen Mini-CFR (numpy, Hebel E).
- Lokales DIVAT fuer nicht-GTOW-Messungen (Slumbot/Coaching) notiert; UCB1-Team-Coach nur bei nicht-stationaeren
  Gegnern relevant. Volle Analyse: Agent-Report (Task a33db0cea418f96e9).

## 'Compact CFR' (Eric Jackson, AAAI-Workshop 2016 — inline gelesen 2026-07-05): die RAM-Achse von UNTEN
Kern: 16 Bytes/Aktion -> **1 Byte** via (1) Follow-the-Leader statt Regret-Matching (nur argmax zaehlt ->
Regrets als nicht-negative OFFSETS vom besten), (2) 1-Byte-Quantisierung (fixed-size fuer External-Sampling-
Random-Access; kostet etwas Konvergenzzeit), (3) Current-Strategy-only statt Average (FTL -> automatisch PURE
= 1 Bit/Aktion), (4) Checkpoint-MIXTURES retten die Exploitability teilweise (51 Blends: 21.7 vs 10.14 mbb/g).
EHRLICHE Warnungen aus dem Paper selbst: FTL verliert die No-Regret-GARANTIE; Current-only = schlechte
Exploitability (nur head-to-head ok) — fuer unsere Anti-GTOW-Mission ist Exploitability der Massstab, also
Average/Mixtures behalten, die OFFSET+1-Byte-Regrets sind der sichere Teil.
**DER RAM-ADAPTIVITAETS-DIAL (User-Wunsch, Design-Prinzip):** Johanson 2007 skaliert Qualitaet mit RAM nach
OBEN (mehr Aufloesung = staerker), Jackson 2016 nach UNTEN (16x Kompression) — ein Kern, ein Regler:
float32-Regrets (viel RAM) -> uint8-Offsets -> purified 1-Bit (wenig RAM). Einbauorte:
- **flop_library (Queue #1):** Dumps als uint8-quantisierte Strategien (256 Stufen << Solver-Rauschen) statt
  JSON-floats -> ~8-20x kleiner -> die 1755-Flop-Bibliothek passt in die realen 15.7GB RAM.
- **v4-CFR-Kern:** Regret-Tabellen mit waehlbarer Praezision (der Dial als Konstruktor-Parameter).
- Optional: der 12GB-Solve-Cache als npz/uint8 fuer RAM-Preload (Disk ist billig — nur bei Bedarf).
Kein Live-Nutzen HEUTE (TexasSolver-Subgames sind zeit-, nicht RAM-gebunden). PDF: books/papers/CFR/.

## Turnier-Modus (2026-08-04) — bewusste Naeherungen
- **OPEN_FRAC-"UTG"-Fund**: "UTG" fehlt im 6-max-OPEN_FRAC (faellt auf 0.20 statt EP-0.16). ABSICHTLICH
  nicht gefixt (Anker-Schutz des vermessenen tag-Kerns); gegateter Re-Test-Arm, wenn der Kern neu vermessen wird.
- **Dead-Button-Regel**: der Turnier-Direktor laesst den Button einfach zum naechsten Ueberlebenden wandern
  (statt Dead-Button/Dead-SB). Exakt spaeter, falls Empirie-Abgleich es verlangt.
- **ICM = Malmuth-Harville**: kein Future-Game-Simulation-Korrektiv (Blind-Positionen). Drehbarer Modell-Knopf.
- **BF mit Start-of-Hand-Stacks**: die Bubble-Faktor-Naeherung nutzt die Stacks bei Handbeginn (stabil, cachebar);
  nur der exakte All-in-Call rechnet mit Behind-Stacks im Entscheidungsmoment.
