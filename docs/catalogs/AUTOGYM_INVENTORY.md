# AUTOGYM_INVENTORY.md — full inventory of the mathematics assets (panel, 2026-08-16)

> 77 unique formula functions categorized (4 agents + synthesis; raw categories: {'CHECK_F': 21, 'NICHT_VERDRAHTBAR': 29, 'CHECK_L': 21, 'KONTEXT_FEATURE': 34, 'KNOB_PRIOR': 27, 'CHECK_P': 2}). Result = the wiring plan for the oracle.
> Wave 1 needs NO engine rebuild, only record extensions at the two gym call sites.

WIRING PLAN AUTOGYM ORACLE (pokerbot/autogym/oracle.py, stages HART/P/L/F)

Basis checked: `grade_decision` today receives ONLY {street, pot, to_call, action, amount, hero_hole, board, villain_hole} (gym_hu.py:42-47, gym_six.py:44-49); at BOTH call sites, however, stacks/all_in/position are already present in the state — fields from these are cheap record extensions (wave 1), genuinely new recording (hand linkage, result, line) is wave 2.

---

## 1. STATISTICS

77 unique functions (the inventory contains 14 duplicate entries; the last entry `equity_denial_value` is truncated). 4 category CONFLICTS between first and second entry, each resolved to the more conservative second verdict:
- `bluff_catcher_call_ev`: L→**F** (only robust in aggregate)
- `pot_odds_required_equity_with_rake`: L→**KNOB** (rake=0 collapses onto the already-wired `equity_needed_to_call`)
- `reverse_implied_odds_max_future_loss`: L→**KONTEXT**
- `effective_multi_street_required_equity`: L→**NICHT** (needs the PLANNED betting plan)

| Category | Count |
|---|---|
| CHECK_P | 1 |
| CHECK_F | 16 (of which 1 wired: `minimum_defense_frequency_by_bet_fraction`) |
| CHECK_L | 14 (of which 2 identical to wired ones: `bluff_catcher_breakeven_equity`, `compute_pot_odds` = cross-check only) |
| KONTEXT_FEATURE | 19 |
| KNOB_PRIOR | 10 |
| NICHT_VERDRAHTBAR | 17 |

---

## 2. WAVE 1 — next wiring (10 checks + 2 instrumentations; no engine rebuild, only record extension at the two call sites)

New record fields from existing state: `effective_stack` (min(my_stack, villain_stack)+committed logic), `call_closes_action` (opponent all_in or to_call ≥ my_stack), `node_typ` ('bet'|'raise', HU from history/cur_bet, 6-max from obs), `n_opponents` (obs['n_active']-1).

1. **expected_value** — `knowledge_base/math/formulas.py:104` — stage **L**, rule `fold_ueber_pot_odds` (mirror of the wired `call_unter_pot_odds`): fold at to_call>0 with hindsight eq ≥ req+margin. Fields: present (HU-only via villain_hole). Verification: EV = eq·(P+C) − C per Fraction; zero at eq = C/(P+C). Knob: LEAD_MARGIN 0.15 [0.10, 0.25].
2. **exact_two_card_draw_equity** + feeder **combined_draw_outs** — `postflop_formulas.py:413/426` — stage **P**, rule `allin_call_ohne_odds`: a call that closes the action all-in (no implied odds), and even the OPTIMISTIC out upper bound does not cover the pot odds ⇒ provably −EV, range-free, also runs 6-max. Fields: + `call_closes_action`. Verification: 1 − C(38,2)/C(47,2) = 378/1081 exactly; outs=0 ⇒ 0. Knob: OUTS_SAFETY (+2 outs safety margin) [0, 4].
3. **required_fold_equity** — `formulas.py:322` — stage **L**, rule `bet_ohne_gewinnweg`: a hero bet/raise with FE_req > 1 at hindsight E vs villain_hole cannot profit at any fold frequency. Fields: present (amount is logged). Verification: E=0 ⇒ FE = R/(P+R) = alpha (Fraction); denominator fix formulas.py:361 pinned in the suite. Knob: FE_MARGIN 0.10 [0.05, 0.20].
4. **minimum_defense_frequency_by_bet_fraction** (refinement) — `postflop_formulas.py:92` — stage **F**: refine the existing MDF band from per-street to per-(street × sizing bucket); `facing_bets` already carries pot+bet. Verification: Fraction(1, 1+f); half pot ⇒ 2/3. Knobs: SIZING_BUCKETS [0.33, 0.66, 1.0, 1.5, ∞], MDF_BAND 0.10 [0.05, 0.15], N_MIN 30.
5. **breakeven_bluff_percentage** — `formulas.py:594` — stage **F**, rule `pool_overfold_vs_alpha`: the same `facing_bets` tuples read from the BETTOR side — fold frequency > alpha+band ⇒ any-two bluff prints. Verification: exact identity alpha + MDF = 1 per Fraction (complement of check no. 4, mutual self-test). Knobs: as no. 4.
6. **required_fold_fraction_for_raise** — `postflop_formulas.py:82` — stage **F**, rule `mdf_am_raise_knoten`: alpha/MDF separately for node_typ='raise' (the wired band covers only bets). Fields: + `node_typ`. Verification: 300/(300+150)=2/3 per Fraction; identity with `breakeven_fold_equity_pure_bluff`. Knobs: own RAISE_N_MIN 30 (more thinly populated).
7. **river_bluff_to_value_ratio** + q target **bluff_to_value_and_frequencies** — `strategy_formulas.py index 18` / `formulas.py:183` — stage **F**, rule `river_ratio`: classify every hero river bet in hindsight via villain_hole as value (eq>0.5) / bluff, aggregated ratio per sizing bucket vs B/(P+B). HU-only. Verification: B=P ⇒ bluff share 1/3 (docstring anchor); chain q=B/(P+2B), r=B/(P+B) per Fraction; form 2026-07-06 pinned in tests/test_math_suite.py. Knobs: RATIO_BAND 0.15 [0.10, 0.25], N_MIN 30, VALUE_EQ_SCHWELLE 0.5 (fixed, not a tuning knob).
8. **bluff_catcher_call_ev** — `postflop_formulas.py:102` — stage **F**, rule `pool_bluff_fraktion`: at river bet nodes the bluff fraction of the BETTOR (in self-play its hole = the logged villain_hole) vs q* = B/(P+2B); deviation ⇒ over-fold/over-call proposal for the defender side. Fields: present. Verification: zero exactly at q* per Fraction; algebraically identical to `exploit_call_deviation_ev`. Knobs: Q_BAND 0.10 [0.05, 0.20], N_MIN 30.
9. **commitment_margin_by_spr** — `strategy_formulas.py index 26` — stage **L**, rule `committed_fold` / `stackoff_unter_schwelle`: fold despite eq ≥ spr/(1+2spr)+margin, or stack-off far below it. Fields: + `effective_stack` (HU-only for the eq side). Verification: Fraction identity S/(P+2S) = spr/(1+2spr) = equity_needed_to_call(P+S, S). Knob: LEAD_MARGIN shared with no. 1.
10. **set_mining_implied_odds_margin** — `strategy_formulas.py index 24` — stage **L**, rule `setmine_ohne_odds`: pocket-pair call preflop with eff/call < threshold — no villain_hole needed, runs HU AND 6-max. Fields: + `effective_stack`. Verification: call 2 / eff 30 / sf 0.8 ⇒ exactly 0 on the threshold. Knobs: SETMINE_FAKTOR 12 [10, 15], stack_factor clamp [0.6, 1.0].
11. *(Instrumentation)* **fold_frequency_exploit_ev** / **exploit_fold_deviation_ev** — `postflop_formulas.py:122` / `index 20` — KONTEXT: quantify severity_bb of the F verdicts (oracle.py:118 sets 0.0 today). Verification: zero exactly at f = alpha (identity `breakeven_bluff_percentage`); 0.7·100−0.3·50=55.
12. *(Self-test only)* **compute_pot_odds** — `formulas.py:7` — identity cross-check `compute_pot_odds(P,B,C)[1] == equity_needed_to_call(P+B,C)` in an `oracle._selftest` analog / test_math_suite — no new verdict.

Recommended order: 1→3 (L/P, per decision, immediate signal), then 4+5 (same data basis, mutual verification), then 6→8 (aggregation F), lastly 9+10 (need the effective_stack field).

---

## 3. WAVE 2 — needs a real gym extension (new recording fields)

New fields (record schema extension + partly aggregation machinery):
- **`hand_id` + `decision_idx`** (linkage of all records of a hand): → `implied_odds_extra_needed` (L), `call_ev_with_implied_gain` (L, realized future_gain from the subsequent records), `reverse_implied_odds_max_future_loss` as an aggregated detector.
- **`hand_result`** (net bb of the hand per seat, showdown yes/no, winner): → empirical `equity_realization` (knob calibration instead of prior), `realized_equity_by_position_spr` validation, money_mine connection.
- **`line`** (action sequence per street, at least hero: checked/bet/raised + marker check-then-face-bet): → `delayed_cbet_ev` (L; needs the check/give-up detection), `minimum_check_raise_defense_combos` (F; defense split check-call vs check-raise at the check node), `check_raise_vs_check_call_delta` (L).
- **Aggregated pool fold frequencies as two-pass input** (collect first, then grade — machinery, not a field): → `semi_bluff_ev` (L), `raise_ev_with_fold_equity` (L, missed raises), tightening of `required_fold_equity` (FE_req vs pool FE+margin).
- **`hero_pos` / `first_in` / `caller_count`** (gym_six already has position_label locally, not logged; HU: button role): → `preflop_calling_range_fraction` (F), `short_stack_open_shove_fraction` (F, comparison against published Nash push/fold tables), `suited_connector_implied_odds_margin` (L).
- **Hindsight classification aggregator per node class** (street × node_typ × sizing bucket × role): → `balanced_bluff_combos`, `target_bluff_combos_for_polar_bet`, `alpha_break_even_bluff_frequency`, `optimal_value_to_bluff_ratio`, `bluff_to_value_ratio_by_pot_fraction`, `breakeven_fold_equity_pure_bluff`, `calling_frequency_to_indifferent_bluffer` (all F — the same family as W1 no. 7/8, only keyed more finely; only meaningful once the node classes fill n≥30).
- **Context fields for severity** (`spr` via compute_spr, `initiative`, `n_opponents`): → `stackoff_equity_threshold_from_spr`, `commitment_spr_for_equity`, `multiway_independent_equity_need`, `initiative_value`, `in_position_ev_premium`, `realized_equity_by_position_spr`, `equity_denial_value`, `geometric_bet_fraction_to_all_in`, `per_street_geometric_bets`, `hand_class_combo_count`, `card_removal_fraction`, `outs_to_equity_rule_2_and_4` (all KONTEXT — they weight, never judge).

---

## 4. DO NOT WIRE (honestly)

All for the same reason: **the gym delivers hands, not ranges** — per decision no range object exists, and an empirical range aggregator (holdings per line over many hands) is a build project of its own, not a check:
`polarized_bet_ev`, `range_vs_range_ev`, `nut_advantage_index`, `nut_fraction`, `polarization_degree`, `mergedness_index`, `capped_range_penalty`, `range_morphology_selector`, `cbet_frequency`, `barrel_continuation_frequency`, `give_up_frequency`, `range_advantage_to_bet_frequency`, `reverse_implied_odds_discounted_equity`, `range_combo_count`, `count_hand_combos_with_blockers`.
Additionally:
- `effective_multi_street_required_equity` — needs the PLANNED multi-street plan, which no decision record contains; the realized variant is P&L attribution (money_mine), not a formula check.
- `reverse_implied_odds` (math.json:273-334) — verified:false, code broken (dataclass decorator without @ ⇒ TypeError); only assessable at all after a code fix.
- `cbet_frequency` explicitly NOT to be wired as a degraded prior check (neutral zeros for range_advantage/nut_advantage would be self-deception).

---

## 5. KNOB REGISTER (KNOB_PRIOR + check-internal constants)

| Knob | Source | Default | Bounds |
|---|---|---|---|
| R (equity_realization_ev) | postflop_formulas.py:239 | 1.0 | [0.5, 1.2] |
| R (equity_realization) | formulas.py:624 | 1.0 | [0.5, 1.05] (clamps as in realized_equity_by_position_spr) |
| dirty_out_weight | postflop_formulas.py:438 | 0.5 | [0, 1] |
| rake_fraction / rake_cap | postflop_formulas.py:132 | 0 (gym rake-free) | [0, 0.05] / ≥0 |
| preflop_open_raise_size_bb | strategy_formulas index 1 | 2.25/2.50/3.00 per pos. | [2.0, 3.5], 0.25 grid |
| preflop_threebet_size_bb | index 2 | IP 3x / OOP 4x | IP [2.5, 3.5], OOP [3.5, 4.5], cap ≤ effective_bb, IP<OOP |
| preflop_fourbet_size_bb | index 3 | IP 2.2x / OOP 2.5x | IP [2.0, 2.6], OOP [2.2, 3.0], lower bound 3bet+open, cap ≤ eff |
| preflop_squeeze_size_bb | index 4 | open·(3\|4 + callers) | base [2.5, 4.5], +1/caller [0.5, 1.5], monotone in callers, cap ≤ eff |
| bounded_read_deviation_ev | index 28 | sensitivity 2 | edge clip [−1, 1] hard; sensitivity [0, 3]; |EV| ≤ P+R by construction |
| stat_read_delta | index 29 | 0.5/0.3/0.2 | simplex Σ=1, each weight [0, 1]; output clip [−1, 1] |
| realization clamp (preflop_calling_range_fraction) | index 5 | — | [0.45, 0.90] (the constants are knobs at the same time) |
| LEAD_MARGIN | oracle.py:28 | 0.15 | [0.10, 0.25] |
| MDF_BAND | oracle.py:32 | 0.10 | [0.05, 0.15] |
| EQ_ITERS | oracle.py:30 | 200 | ≥200 (keep SE ≪ LEAD_MARGIN) |
| N_MIN (F stage) | oracle.py:110 | 30 | ≥30, never lower |
| SIZING_BUCKETS (new, W1-4/5/7) | — | [0.33, 0.66, 1.0, 1.5] | edges fixed per measurement series (otherwise bucket gaming) |
| RATIO_BAND / Q_BAND (new, W1-7/8) | — | 0.15 / 0.10 | [0.10, 0.25] / [0.05, 0.20] |
| FE_MARGIN (new, W1-3) | — | 0.10 | [0.05, 0.20] |
| OUTS_SAFETY (new, W1-2) | — | +2 outs | [0, 4] |
| SETMINE_FAKTOR / SC thresholds | index 24/25 | 12 / max(8, 20−3·IP−2·callers) | [10, 15] / lower bound 8 fixed |

Binding (improver doctrine, oracle.py header): HART is untouchable; only P may be patched autonomously (wrapper behind a paired A/B gate); L/F generate proposals, never auto-patches; every knob turn needs the explicit condition test (CONDITIONAL_POKER_LEMMAS pattern).
