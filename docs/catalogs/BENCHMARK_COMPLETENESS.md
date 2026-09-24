# BENCHMARK_COMPLETENESS.md — Reconciliation of inventory vs. repo sources (2026-08-16)

**Question:** The user says 95% of the necessary mathematics already lies in the repo and only needs to be
ASSEMBLED. Is that true — and what does the benchmark (`pokerbot/autogym/oracle.py`) lack
for COMPLETENESS?

**Short verdict:** For the DECISION mathematics (cash, HU + 6-max) the 95% thesis holds:
the inventory (AUTOGYM_INVENTORY.md, 77 functions) covers the three formula files completely,
and the `*_verified.json` even provide ready-made `verify_expr`/`verify_value`
pairs for every function = practically bundled E1 references. BUT: the inventory has **never
inventoried three whole repo domains** that belong to a COMPLETE benchmark and are mountable —
**(A) ICM/tournament** (`pokerbot/strategy/icm.py` + `tournament.py` + `arena/tourney.py`),
**(B) measurement/variance statistics** (`mathematics_of_poker.json`: 443 entries, many with Python),
**(C) the MoP corpus itself** (toy-game/limit anchors as cross-checks). Genuinely missing (not
in the repo) are only 5 points, see section 5.

---

## 1. Source reconciliation (what the inventory covers — and what not)

| Source | Scope | In the inventory? | Finding |
|---|---|---|---|
| `knowledge_base/math/formulas.py` | 12 functions | ✓ complete | 7 of them wired/mirrored (v0+W1-1..3) |
| `knowledge_base/math/postflop_formulas.py` | 34 functions | ✓ complete | wave 1/2 planned |
| `knowledge_base/math/strategy_formulas.py` | 32 functions | ✓ complete | wave 1/2 planned |
| `knowledge_base/math/math.json` | 13 entries, `verified` flags | ✓ (identical to formulas.py) | `reverse_implied_odds` verified:false, code defective — correctly listed as NOT |
| `knowledge_base/math/postflop_calc_verified.json` | 34 calculations | ⚠ only indirectly | carries `verify_expr` + `verify_value` per function = **ready-made E1 references, unused** |
| `knowledge_base/math/strategy_calc_verified.json` | 32 calculations | ⚠ only indirectly | ditto |
| `knowledge_base/math/mathematics_of_poker.json` | **443 entries** (name/concept/formula/python) | **✗ NOT inventoried** | variance, CI, risk of ruin, Kelly, tournament variance k, Malmuth-Harville/Weitzman, jam-or-fold thresholds, alpha/MDF toy-game anchors — much of it with executable Python |
| `knowledge_base/concepts/concepts.json` | 813 concepts (qualitative) | ✗ (rightly) | no formulas; correctly excluded as a benchmark source |
| `tests/test_math_suite.py` | 17 deep checks, Fraction culture | ⚠ partially | ALREADY contains Fraction references for W1 candidates (alpha/MDF `_alpha_mdf`, bluff ratio `_bluff_ratio`, RFE `_rfe`, convention checks `_observed_fracs_conventions`) — the oracle does not duplicate them so far, it should IMPORT them |
| `pokerbot/strategy/icm.py` | exact Malmuth-Harville, bubble_factor, icm_call_threshold (tested: `tests/test_icm`) | **✗ NOT inventoried** | complete ICM check family mountable |
| `pokerbot/strategy/tournament.py` | icm_required_equity, proportional risk premium (validated +10.0 ± 5.0 pp ROI), bf_matrix, Director | **✗ NOT inventoried** | tournament-gym connection mountable (`arena/tourney.py` exists) |
| `pokerbot/engine/equity.py` | equity_vs_hand / equity_vs_range | ✓ (as hindsight engine) | multiway hindsight (all holes) still missing, small rebuild |

**Count:** 12+34+32 = 78 definitions, 77 unique (1 duplicate `bluff_catcher_breakeven_equity`
≡ `equity_needed_to_call` family) — the inventory statistics are correct. Wired today: 7 checks.

---

## 2. MOUNTABLE from the repo — block A: ICM / tournament

The gym for it already exists (`pokerbot/arena/tourney.py`, paired SNG arena) — it is just
not connected to the oracle. Proposal: `gym_tourney.py` analogous to `gym_hu.py`, records extended by
`stacks_all`, `payouts`, `bf`.

| Building block | Source | Category | Rule sketch | Fraction reference |
|---|---|---|---|---|
| ICM sum invariant | `strategy/icm.py:22` (`icm_equities`) | **HART** | Σ ICM equities = Σ payouts, exact, every hand | winner-take-all: `icm_equities([200,100,100],[1,0])` = exactly `[1/2, 1/4, 1/4]` (stack proportion per Fraction) |
| ICM monotonicity | `strategy/icm.py` | **HART** | larger stack ⇒ ≥ ICM equity (permutation check) | equal stacks ⇒ exactly equal equity by symmetry |
| Malmuth-Harville vs. enumeration | `strategy/icm.py` + `tests/test_icm.py` | E1 self-test | adopt the independent enumeration (already in the test) as oracle reference | 3 players, rational stacks: recompute the MH product formula per Fraction |
| `bubble_factor` HU limit case | `strategy/icm.py:101` | E1 self-test | HU winner-take-all ⇒ BF exactly 1 (CLAUDE.md anchor: Prince plays endgames untouched) | `bubble_factor(HU, [1,0])` == 1 exactly |
| `icm_call_ohne_odds` | `icm.py:126` (`icm_call_threshold`) + `tournament.py:71` (`icm_required_equity`) | **L** | hindsight call below the ICM threshold (chip req · BF_eff), margin like LEAD_MARGIN | identity `icm_required_equity(req, 1)` == req (BF=1 collapses to cash) per Fraction |
| Proportional risk premium | `tournament.py` (BF_eff = 1+(BF−1)·(to_call/Stack)) | **Knob** | scalar validated (paired, +10.0 ± 5.0 pp); bounds: proportional formula fixed, no full BF (REFUTED −8pp) | to_call=Stack ⇒ BF_eff = BF exactly; to_call=0 ⇒ 1 |
| `icm_pressure_mult` | `tournament.py:136` | **Knob** | pressure lever doctrine 9; bounds from DOKTRIN.md | limit case: no ICM tension ⇒ mult 1 |
| Tournament variance k | `mathematics_of_poker.json` ("Tournament variance multiple k") | **Context** | payout structure ⇒ variance multiple; weights tournament gate SE | k for winner-take-all structure closed per Fraction |

## 3. MOUNTABLE from the repo — block B: measurement/variance statistics (the benchmark of the benchmark)

The gate doctrine (ANWENDEN > 2·SE) stands and falls with the SE computation — but NOTHING checks
the statistics of the gate itself today. `mathematics_of_poker.json` carries the necessary formulas
with Python: variance additivity, SD/Var relation, CI of the win rate, SE scaling with n,
sample size for precision. Proposal: **new level "MESS"** (self-test of the harness,
runs in `selftest.py`, never in improver territory):

| Building block | Source (MoP entry) | Category | Fraction reference |
|---|---|---|---|
| SE of the paired gate | "Scaling variance with sample size" | MESS (E level) | constructed pair series with rational values ⇒ SE closed per Fraction, against `duplicate_ab` SE |
| Variance additivity | "Additivity of variance across poker hands" | MESS | Var(X+Y) = Var(X)+Var(Y) for independent rational series, exact |
| CI / sample size | "Approximate confidence interval …", "Sample size needed …" | MESS | n = (z·σ/ε)² at rational σ,ε; z fixed |
| Bernoulli variance | "Variance of Bernoulli outcome" | MESS | p(1−p) per Fraction, maximum exactly at p=1/2 |

## 4. MOUNTABLE from the repo — block C: multiway + MoP anchors + self-test imports

| Building block | Source | Category | Rule sketch | Fraction reference |
|---|---|---|---|---|
| Multiway equity requirement | `postflop_formulas.py:403` (`multiway_independent_equity_need`) | **L** (6-max!) | gym_six already logs `n_opponents`; call that closes the action, req equity vs field: per-opponent requirement = target^(1/n) exceeds draw upper bound ⇒ lead. Honestly declare the independence assumption as an approximation (../NOTES.md entry) | target 1/4, n=2 ⇒ exactly 1/2 |
| Multiway hindsight | `engine/equity.py` + gym_six | rebuild (small) | gym_six logs `villain_hole=None` — instead log ALL active holes ⇒ L level (pot-odds hindsight) also runs 6-max; needs `equity_vs_hands` (multi-opponent MC, ~20 lines around `equity_vs_hand`) | all-in cases exactly enumerable (remaining board cards) like `_river_equity_exact` in test_math_suite |
| Geometric sizing | `postflop_formulas.py:208/218` | **Context** | severity weighting + sizing-bucket reference line (W1-4/5) | SPR 4, 1 street ⇒ f = 4 (pot factor) exactly; `(1+2f)^streets = 1+2·spr` as Fraction identity |
| SPR family cross-check | `postflop_formulas.py:188/198` + `strategy_formulas.py:263` | E1 self-test | triple identity `stackoff_equity_threshold_from_spr(spr)` == zero of `commitment_margin_by_spr` == `equity_needed_to_call(P+S, S)` | spr = S/P rational ⇒ spr/(1+2·spr) per Fraction (inventory W1-9 already names it — here as mutual self-test of all three) |
| Combo counting | `formulas.py:473` + `postflop_formulas.py:291/321` | E1 self-test | blocker combinatorics against brute-force enumeration (52 cards) | AKs without blocker = 4, AA = 6, with one ace dead: AA = 3 — exactly |
| Import test_math_suite references | `tests/test_math_suite.py` (`_alpha_mdf`, `_bluff_ratio`, `_rfe`, `_observed_fracs_conventions`) | E1 | do NOT re-derive the W1-4/5/7 checks: the Fraction references exist, the oracle self-test module should call them (checker separate from the checked stays preserved — the suite is the independent checker) | present (17/17 deep) |
| MoP toy-game anchors | `mathematics_of_poker.json` ("Golden mean r=√2−1", AKQ-α, clairvoyance calling) | E1 self-test | limit anchors for the F family: α(s) curve, MDF complement, P=1 bluff cutoff | α = s/(1+s) at rational s per Fraction; MDF+α = 1 identity (matches inventory W1-5) |
| Jam-or-fold model | `mathematics_of_poker.json` (jam-or-fold game #1/#2, thresholds with Python) | **F** (later) | reference curve for `short_stack_open_shove_fraction` (inventory W2) — COMPUTE from the MoP model instead of searching for an external Nash table | [0,1]-game thresholds closed, recomputable per Fraction |

---

## 5. GENUINELY MISSING (not mountable from the repo) — with completion sketch

1. **Bankroll/RoR/Kelly as a checked module.** The formulas exist as Python STRINGS in
   `mathematics_of_poker.json` (R(b)=e^(−2μb/σ²), Kelly f=2p−1, RoRU, half-bankroll rule), but
   nowhere as an importable, tested module — CLAUDE.md itself calls the bankroll/variance axis
   "un-formalized". *Sketch:* `knowledge_base/math/bankroll_formulas.py` (~8 functions
   from the MoP entries), Fraction/closed-form references (Kelly p=3/5 ⇒ f=1/5 exactly; RoR
   exponent at rational μ,σ²,b algebraically), connection to test_math_suite. Category: context/
   MESS (evaluates sessions, never individual decisions). Effort ~1 session.
2. **`reverse_implied_odds` is defective** (math.json verified:false, dataclass decorator without `@`
   ⇒ TypeError). No new knowledge needed, only a code fix + verification — until then the
   building block rightly stays out.
3. **Multi-opponent hindsight equity** (`equity_vs_hands`): the engine building block for the 6-max
   L level does not exist (only vs ONE hand / ONE range). *Sketch:* MC extension of
   `equity_vs_hand` to a list of known holes (in self-play ALL holes are known);
   exact enumeration branch for river/all-in as reference (pattern `_river_equity_exact`).
4. **Nash push/fold reference data** (external validated table à la HoldemResources) for
   `short_stack_open_shove_fraction`: not in the repo. *Sketch:* do NOT procure externally, but
   compute once from the MoP jam-or-fold model ourselves (`research/jam_or_fold_solve.py`,
   CPU minutes) and freeze as `data/jam_or_fold_reference.json`; sanity-check against the published
   limit cases (S→0 ⇒ any-two).
5. **Rake realism:** the gym is rake-free (knob rake=0, deliberately). For a benchmark that ever
   targets real sites, a rake model per site is missing (structure + cap as data).
   *Sketch:* small `data/rake_models.json` + the already existing knob
   `pot_odds_required_equity_with_rake`; only relevant once a live target is pending — deliberately
   documented gap, no blocker.

**Not missing but deliberately excluded (confirmed):** the 17 range-based functions
(NICHT_VERDRAHTBAR — the gym delivers hands, not ranges), `effective_multi_street_required_equity`
(needs the planned commitment plan), concepts.json (qualitative). The exclusion is honest and
remains correct.

---

## 6. Knob register additions (in addition to the inventory table)

| Knob | Source | Default | Bounds |
|---|---|---|---|
| BF_eff proportional formula | `tournament.py` | proportional (validated) | form fixed; full BF forbidden (refuted) |
| ICM_LEAD_MARGIN | new (block A) | 0.15 like LEAD_MARGIN | [0.10, 0.25]; oracle knob ⇒ improver-locked |
| icm_pressure_mult strength | `tournament.py:136` | doctrine-9 value | from DOKTRIN.md; only with condition test |
| MULTIWAY_INDEP_ANNAHME | new (block C) | independence | NO knob — declared approximation, ../NOTES.md entry |
| RAKE_MODELL | genuinely missing no. 5 | rake=0 | measurement config, never improver |

## 7. Recommended order

1. **Immediately, $0:** import the test_math_suite references into the oracle self-test module (section 4)
   + run the `verify_expr` pairs of the `*_verified.json` as a machine E1 net over ALL 66
   calculations (a ~30-line runner; covers the complete wave 1/2 in advance).
2. **Wave 1 as planned** (inventory 1→3, 4+5, 6→8, 9+10) — this reconciliation changes nothing about it.
3. **Block B (MESS level)** before the next gate run — the gate SE is the most expensive unchecked
   number of the system.
4. **Block A (ICM/tournament gym)** as its own discipline — arena exists, connection effort small,
   opens up the validated tournament stack for the loop.
5. **Genuinely-missing no. 3 (equity_vs_hands)** together with wave 2 (hand_id/line) — makes the
   L level 6-max-capable, the biggest lever for the 6-max benchmark.
6. No. 1 (bankroll module) and no. 4 (jam-or-fold reference) opportunistically; no. 5 (rake) only
   with a live target.
