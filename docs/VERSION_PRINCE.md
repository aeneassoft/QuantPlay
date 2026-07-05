# VERSION "PRINCE" — the next best bot (concept + pre-registered build card, 2026-07-04)

> **★ LIVE STATUS (2026-07-05 evening — supersedes the queue below where they conflict):**
> **SHIPPED = PRINCE v3** (commit 85d2919; profile += PAIR_DEFENSE 0.10, RIVER_DEFENSE 0.06; paired Analyzer
> **17.93** vs v2.2's 20.66; live anchor −19.70 ± 4.37 n=2,393 = tag `v2`).
> **REFUTED:** v3.1 (flat RIVER_THIN + CBET_DAMP, 19.76) · flat turn-probe (parked) · limp→open (reverted) —
> the "frequency without selection" family, 3/3 measured.
> **THE ANALYZER QUEUE (built, gates green, default-OFF, one arm per user upload, FRESH anchors — the exporter
> gained all-in run-out sections):**
> 1. **v3.2 `POKERB_RIVER_THIN_SEL=0.40`** — selection-aware thin value (eCall probe gates the bet DECISION);
>    export in flight. Follow-up if graded good: v3.2b = the EXACT threshold (OpenAI-derived, sweep doc §1.1).
> 2. **v3.3 `POKERB_RAISE_NARROW=1`** — raise-facing-bet narrowing toward the mined GTOW raise mix
>    (`research/raise_mine.py`; RANK4 stack-off fix; K2o probe 37%→24%). Pre-gate TODO: Laplace-shrink the
>    n=29 jam mix (sweep doc §1.2).
> 3. **v3.4 `POKERB_AUDIT_FIX=1`** — the 9-find audit bundle (scope guards + covered-stack req + floor +
>    phantom sizer arms + raise=aggro).
> 4. **v3.5 `POKERB_ADVISOR_ROLE_POS=1`** — advisor role by tree POSITION (training convention; inverts 3bet-pot
>    lookups; potentially the largest single lever left).
> Ledger: audit `data/audit/audit_result.json` · research `docs/RESEARCH_SWEEP_2026-07-05.md` · error budget
> `data/gtow_grades/error_prognosis.json`. After the ladder: the v4 decision (depth-limited CFR + neural leaves).


**The name is the thesis:** the cross-coaching result (bot-vs-Prince replay, 2,332 decisions) said the perfect player
of that sample plays *the bot's discipline + the user's pressure*. This version fuses them. **Doctrine: ONLY bb count**
(GTO-score is dead as a target — measured: chasing it COST EV). Every ingredient below carries its evidence status;
nothing ships on hope. Full evidence trail: `docs/STATE.md` #4/#5, `docs/GTOW_DOSSIER.md`, `data/gtow_grades/LEAK_MAP.md`.

## 1. The base (LOCKED — best measured config)
`POKERB_GTO_MODE=1` + live resolvers = **AIVAT −11.61 ± 3.67 (n=100 smoke, 0 fails)** vs HEAD −20.09 (n=974).
Components: exploit-OFF (17.05 vs 19.33 EV-loss, graded paired) · census tree + raise-snap · tracker damping ·
river guards · the EV-protective SB fold-clamp (15.42 vs 19.56 — the counter-intuitive winner) · solve cache.

## 2. New in PRINCE — the deception layer (built today, gated)
| Flag | What | Evidence status |
|---|---|---|
| `POKERB_TURN_DEFENSE=0.07` | MDF-calibrated turn defense (pairs defend vs ≤0.8-pot stabs) | ✅ canary PASSED (paired +39.1 ± 19.9) · ✅ mechanics PASSED |
| `POKERB_SLOWPLAY=0.25` | trap 25% of strong flop hands → uncap the check range | ✅ same canary · ✅ mechanics PASSED |

**Gates PASSED (2026-07-04, probe n=1800):** P(check|has K) 23.6→**49.1%** (top of the GTO 30-50 band);
**P(K|check) 9.2→17.3% ≈ the 18.2% prior — the check is now uninformative (the user's read is dead)**; fold-to-stab
44.0→**37.6%** (at the ~36 tilde-gate; the stabber's profit −60%: +0.16→+0.06 pot; weak pairs fold 33.9→22.3%; TP+
raises the stab 39.9%). Shipped at the EXACT canary-tested values (no silent post-gate retuning). LIVE: the HU app
launcher + the running server now carry both flags (exploit stays ON vs humans — intentional); the GTOW ladder gets
them via `POKERB_PRINCE=1`. Optional later tuning (0.07→0.09 to close the last 4.6pp to MDF) re-opens the canary.

## 3. Candidate modules (build order; each = its own gated flag, ONE at a time)
**C1 — River value/pressure uplift (the biggest bleed: −8.6 bb/100).** The user's proven line (thin max-value,
overbet vs capped ranges — the +98.5bb jam the bot never takes) as a river module: when villain's line caps his range
(checked twice / called passively) and we hold TP+ → size UP (census 1.0–1.5× arms), plus a planned bluff quota on
scare rivers. Feeds from: LEAK_MAP river classes + the books-wave river chapters (PENDING slot).
**C2 — The line planner (the "er spielt nicht wirklich Poker" fix).** Minimal viable version: ONE plan enum chosen at
the flop decision (`VALUE_LINE / PRESSURE_LINE / POT_CONTROL / TRAP`), persisted on the PokerBot instance per hand,
biasing subsequent street decisions (a pressure-line turn barrels what a street-local decision would check). Sketch
arrives from the Planned-Betting-Lines deep-read (PENDING slot). Start minimal; the full version only if the MVP measures.
**C3 — Safe-subgame-solving wrapper (the never-built 2b).** Wrap `resolver.py` solves: reject/floor a re-solve whose
value vs the tracked range falls below the blueprint/advisor baseline (anti-spew with a guarantee flavor). Spec from
the purchased-papers re-read (PENDING slot).
**C4 — 6-max: squeeze-pot preflop coverage + stack-off discipline** (the −34bb 4bet hand; 4/9 six-max leaks) — for the
6-max product, not the GTOW ladder.
**INTAKE (landed 2026-07-04; merged queue, ranked by bb ÷ effort ÷ risk):**
- **Q1 (hours, floor-0 risk): exact villain bet-size INJECTION into the re-solve tree** (papers #1) — `resolver.py`
  `_match_label` snaps GTOW's observed 1.35–1.75× turn overbets onto our 0.75 arm → hero defends at wrong pot odds.
  We solve AFTER seeing the size → inserting it exactly is free + strictly better. Pure correctness fix.
- **Q2 (hours): the deterministic REPLAY HARNESS on the graded disaster spots** (audit #2) — replay the 34 graded
  hands (Kd6s check-fold, AsQh stack-off…) through `bot.decide` per config = the $0 regression gate every module
  rungs through BEFORE any AIVAT. Becomes measurement-ladder rung 0.
- **Q3 (hours): solve-CONVERGENCE audit** (papers #3) — TexasSolver prints its achieved exploitability; `gto_oracle.py:107`
  DISCARDS it. Parse + log + histogram per street; raise iters (80→500+) only where measured-unconverged. Supremus's
  central lesson; also hardens every other gate.
- **Q4 (hours): STRATEGY PURIFICATION vs the static GTOW** (papers #2, licensed by GTOW's own benchmark paper §4.3.1:
  it never adapts → mixing buys zero protection) — `POKERB_PURIFY`: round mixes ≥0.5 → 1.0. Targets the ~10.7 spread
  slice. GTOW-ladder ONLY (vs humans, mixing stays!). Risk where the modal action is wrong → Q2-gated.
- **Q5 (hours): the product plays the WRONG config** (audit #3) — the HU/6-max apps run exploit-primary HEAD without
  the mode; the user leak-hunts against the un-fixed bot. Launcher/env wiring once PRINCE passes mechanics.
- **Q6 (day): mine the 13.5k logged hands for per-node action FREQUENCIES** (audit #5, the "near-jewel") — GTOW's
  revealed hole cards = free near-solver supervision; our-mix vs GTOW's-mix tables per (street, node, hand-class).
- **Q7 (hours): turn overbet arm (1.5×) in the resolver tree** (papers #5) + **turn defense-advisor head enable**
  (audit #6 — trained, hard-gated to flop) — both feed the turn.
- **Q8 (days): flop→terminal resolver** (papers #4) — the biggest single upside (+2…+4; flop −8.3 has NO re-solve
  today); flop-entry ranges are the cleanest (straight off the blueprint). `POKERB_FLOP_RESOLVER`, Q3-instrumented.
- **Q9 (hours): tracker `size_faced=0.66` hardcode** (audit #7) — thread the real bet fraction; river L1 0.525 is the
  tracker's loosest street. Existing $0 gate (`check_range_l1.py`).
- **Q10 (days): advisor retrain on the census tree** (audit #8) — the default-path MLPs learned a size menu that
  can't represent GTOW's river 0.65; overnight local CPU re-solve + retrain.
- C1 (river discipline) is UPGRADED by audit #4: the spec (`docs/river_corset_consult.md` Guards 1–3) + 66
  engine-verified bluff formulas + MoP blocker primitives ALL exist with zero call-sites — wiring, not invention.
- **Books-wave intake (landed):**
  - **B1 (hours, ★ the elegant find): correlated per-hand street sampling (`POKERB_LINE_U`)** — persist ONE uniform
    draw per hand, reuse it at the three advisor bet/check gates (bot.py:541/559/580) → which hands barrel vs give up
    becomes MONOTONE across streets (flop⊃turn⊃river continuation) instead of independent coin flips. ~20 lines.
    **This IS the degenerate line planner** — it delivers line-coherence with zero architecture; its measurement
    GATES the full planner (if barrel-node Freq-Diff doesn't move, incoherence wasn't the binding leak).
  - **B2 (1–2d, highest-confidence content fix): river value gate = equity vs the CALLING range (`POKERB_RIVER_ECALL`)**
    — replace the magic surrogate `e_call = max(0.10, eq − 0.25·s)` (postflop.py:140) with real re-equity vs the
    tracker range filtered to call-worthy combos; pick the LARGEST census size keeping eq-vs-callers ≥ ~0.55 (ToP
    pp.86-87). The only lever that makes the user's +98bb overbet-jam a GTO-legal line.
  - **B3 (1d): geometric sizing + credible-river-threat gate (`POKERB_LINE_GEOM`)** — stateless multi-street geometry
    (MPT pp.309-315): size value so the river stays jammable; launch turn bluffs only if stack geometry leaves a
    credible ≥⅔-pot river barrel (NLHE T&P pp.37-39). Kills never-follow-through stabs.
  - **B4 = Q8 (flop resolver — papers + books converged independently).** Go/no-go FIRST: solve-time/timeout rate on
    ~50 logged flop spots (a flop subtree is ~50× the turn tree) — half a day decides it for $0.
  - **B5 (2–3d, LAST): the HandPlan MVP (`POKERB_LINE_PLAN`)** — the persisted plan enum {value-ladder, pressure,
    pot-control, trap, delayed-cbet} chosen at the first flop decision, ±0.15–0.25 pb bias vs the SHARED hand-u,
    book-sourced invalidation (villain raise → abandon). Build ONLY if B1 measures green — B1 is its cheap test.
  - Delivery-failure fact (audit-confirmed): **163 multi-street line rules from Beyond GTO were extracted but
    FLATTENED into single-decision nudges** (consolidate_exploit.py → the dead AdaptiveExploiter branch); 813 concepts
    feed only the coach. Gap #1 was never-WIRED, not never-known.
  - Instrument purchase (later): the AGT sequence-form LP = exact river solve + exact best-response → manufactures
    the exact-exploitability gate CLAUDE.md demands. After the content levers.

## 3b. THE BUILD ORDER (final, all three intakes merged)
Rung-0 instruments (hours, build FIRST): **Q2 replay-harness + Q3 convergence-audit** → then the hours-level content
in one measured batch each: **B1 line-U → Q1 size-injection → Q4 purify → Q7 turn-overbet-arm** → day-level:
**B2 river-ecall → B3 geometry → Q6 frequency-mining** → days-level (each gated by what preceded): **B4/Q8 flop
resolver (go/no-go first) → C1 river discipline → B5 HandPlan (iff B1 green)**. Every rung through the ladder in §4.

## 4. The measurement ladder (pre-registered; every rung $0 until the last)
1. **Mechanics probe** (1.8k sims, ~20 min): does the intended behavior move? (per module)
2. **Paired deck canary** (800 mirrored decks): no regression; ship-gate = "not ≤ −2SE".
3. **Graded export** (seed-paired 1500 hands → Analyzer): EV-loss/100 must not rise; river/flop street EV specifically.
4. **Live smoke** (100 hands GTOW, ~17 min): sanity + direction; NEVER a claim (SE ±22 honest).
5. **The pre-registered A/B** (S6): PRINCE vs GTO-mode base, interleaved 250-blocks, **2,500 hands/arm**, key #2,
   thresholds written BEFORE the run. Claim ladder: "better than −20" needs the delta > 2·SE_pair; "−10 or better at
   scale" needs n≈5k; a TIE claim (0 ± 2σ) needs n≈12k (free, ~30h wall-clock).
6. **Honesty gates (unchanged, non-negotiable):** any "+" vs GTOW = artifact until body agrees + the effect sits in
   the targeted bucket; never extend a running session; every run logs the config fingerprint (`gto_mode.fingerprint()`).

## 5. Ship rules
- One module at a time through rungs 1–3; bundle only for rung 5 (the A/B measures the PROFILE, ablation arms resolve
  ambiguity). A module that fails any rung is tuned once, then parked (no zombie retries).
- The PRINCE profile = a new expansion in `gto_mode.py` (`POKERB_PRINCE=1` → GTO_MODE + the passed modules), default
  OFF; the product (`bot.py` defaults) stays byte-identical until the S6 A/B verdict.
- Rollback is trivial by construction: every module is one env flag.

## 6. Definition of done
PRINCE ships when: mechanics ✓ on all included modules · canary ✓ · graded EV-loss ≤ base's 17.05 · live A/B at
2,500/arm beats the base by > 2·SE or matches it with the deception layer live (strictly better vs humans). Target
corridor after C1+C2 (honest): **AIVAT −4 … −9** — leaderboard top-5 territory; tie remains the North Star via the
T3 loop, not a promise.
