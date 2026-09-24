# AUTOGYM_PLAN.md — the self-checking training loop (decided 2026-08-16)

**Goal: approach the GTOW baseline.** Reference = the validated **−19.70 ± 4.37 bb/100**
(PRINCE v2.2, n=2,393). Staircase, pre-registered: −19.70 → **−15** → **−10** → leaderboard band.
Every step is measured vs GTOW (in-process, $0), never extrapolated from self-play.

**Doctrine: proven locally, then scaled.** Pre-registered expectations everywhere; met = ready.
The pod (RunPod, CPU-heavy — CFR/self-play needs cores, not GPU) comes only after E1–E5.

## Architecture (built, `pokerbot/autogym/`)

| Module | Role |
|---|---|
| `oracle.py` | the unified mathematics benchmark: formula collection → judgments (HART / P / L / F) |
| `gym_hu.py` | Prince HU self-play, paired decks with button swap (cards+position cancel out) |
| `gym_six.py` | 6-max self-play, fresh table per hand, position ledger |
| `improver.py` | mine → patch → paired gate → journal (`data/autogym/journal.jsonl`) |
| `selftest.py` | the local proof of the loop (E1–E4, one command) |

## The safety contract — "optimize mathematics automatically, without errors"

Modular here means: **every layer has a different mutability status**, and the loop
can only touch what its status allows.

1. **Formulas are immutable.** A formula (`knowledge_base/math/*.py`, 78 functions) is
   never edited automatically. It is only wired in once it passes an **independent
   Fraction reference** (E1; checker separate from the checked — test_math_suite culture).
2. **Oracle knobs are measurement configuration** (LEAD_MARGIN, MDF_BAND, EQ_ITERS): **locked**
   for the improver. A loop that may tune the tolerances of its own measuring instrument
   optimizes the instrument instead of the bot (Goodhart). Changes only by hand, with justification.
3. **Bot knobs are the tuning territory** (e.g. `value_raise_eq`, flag profiles), each with
   declared bounds. Proposal free — **application only through the paired A/B gate**.
4. **P patches are wrappers, never source edits** — and even the provable patch must pass the gate
   (pass thresholds pre-registered: ANWENDEN > 2·SE, VERWERFEN < −1 bb/100).
5. **Nothing happens silently.** Every round, every proposal, every judgment → journal.

## The expectation ladder (pre-registered; PASS = ready for the next stage)

| | Expectation | Threshold | Status |
|---|---|---|---|
| **E1** | Oracle truth: every wired formula vs independent Fraction reference | 7/7 exact | `selftest` |
| **E2** | Symmetry: pair drift of the healthy bot in self-play | \|drift\| < 2·SE | `selftest` |
| **E3** | Detector: constructed defect bot (station) is detected AND rejected in the gate | lead rate ≥ 2× healthy; gate = ANWENDEN for healthy | `selftest` |
| **E4** | Null stability: healthy vs healthy produces **no** ANWENDEN (no invented improvements) | 0 false patches | `selftest` |
| **E5** | Throughput locally: pilot measured 500 hands + 3,577 graded decisions in 52 s (~580 hands/min) | pod expectation ≥ 10,000 hands/min on 64 cores, otherwise it is not worth it | pilot ✓, pod open |
| **E6** | **BASIS anchor (user decision 2026-08-16):** every candidate with a local ANWENDEN is measured PAIRED against the frozen basis bot (tag `autogym-basis`) | candidate > basis with effect > 2·SE; GTOW only as a last resort | open |

E6 is the only stage that counts — E1–E5 exist so that E6 measurements never stand on a
broken loop. VERSIONING: freeze before every change (tag); a finished
changed bot gets a NAME (tag) and its paired number against the basis.

## Wiring backlog (the oracle manifest keeps live books)

v0 wired: `equity_needed_to_call` (L), `minimum_defense_frequency` (F), chip conservation
(HART), `free_fold` (P). **The full inventory is there: [`../catalogs/AUTOGYM_INVENTORY.md`](../catalogs/AUTOGYM_INVENTORY.md)**
— 77 unique functions categorized (1 P / 16 F / 14 L / 19 context / 10 knob / 17 honestly
not wirable, because the gym delivers hands, not ranges). **Wave 1 = 10 checks + 2
instrumentations without engine rebuild** (only record extensions: effective_stack,
call_closes_action, node_typ, n_opponents); recommended order 1→3 (per decision),
4+5 (mutually verifying MDF/alpha pair), 6→8 (aggregation F), 9+10. Wave 2 needs
hand_id/decision_idx, hand_result and the line history. The knob register (with bounds)
is in the inventory; binding remains: oracle knobs are measurement config, not improver territory.

## TWO DISCIPLINES — the 6-max parity (user reminder 2026-08-16, binding)

The candidate loop so far measures ONLY Prince HU (duplicate_ab). The 6-max core
(SixMaxBot ecology) is graded by the oracle but has NO gate. Work package
**AP-6MAX (before the basis rotation round 4):** a paired 6-max gate — same cards,
candidate rotates over the seats (6 rotations per deal = position and card cancellation),
rest of the table = frozen sixmax basis; then the same guards run (sel/lizenz —
both are range-free enough: the tracker range needs HU posts, 6-max uses the
position prior from the Snowie bridge make_seeded_tracker). Versioning separate:
own basis tags (autogym-basis-6max), own names. The disciplines share oracle,
journal, run storage and expectation ladder.

### AP-6MAX-OBSERVATION — structure catalog first, then mathematics (user design 2026-08-16)

Method as with the bluff-license catalog: DESCRIPTIVE before NORMATIVE. The 6-max bot plays against
itself; what is recorded is the CONVERSATION STRUCTURE of every hand (classroom analogy:
order of raising hands = position, speaking up = action, the conversation collapses to 2-3 voices):
  (1) Node taxonomy: open/call/3bet/squeeze/multiway pot per position x number of active
      players x street — WHICH decision types occur how often (the frequency map
      determines where mathematics has leverage at all, AP8 lesson);
  (2) Collapse dynamics: 6 -> n players per street, who carries the defense burden (MDF is
      NOT well-defined per player multiway — the burden is shared, that is new mathematics);
  (3) Equity thresholds multiway: required equity vs N callers (the formula collection has the building blocks);
  (4) Position range structure: the realized ranges per seat as an empirical prior
      (Snowie bridge lesson formalized).
Yield: the 6-max structure catalog -> from it the 6-max oracle checks (which HU checks
transfer, which must be redefined multiway) -> only then candidates.
Instrument: gym_six + entscheidungs_logger (built) + new structure fields (n_active per
street, aggressor position, node type).

### THE RELAY ARCHITECTURE (user design 2026-08-16): 6max -> 3max -> HU
The collapse gets a BOT RELAY: the 6-max bot plays the full round; if the
pot shrinks to 3 players, a dedicated 3-player bot takes over; in the final case the (Prince) HU bot.
The RANGE TRACKER is the baton: the ranges COLLAPSED at the collapse + the
order history are HANDED OVER to the next stage (the handover exists
in rudiments — Prince HU takeover in six_server + make_seeded_tracker — and is extended into the
load-bearing interface: range snapshot per player + position/aggressor
context as handover object). ROBUSTNESS OBLIGATION: no path may fail on obscure cases
(4-6 players to the river, side pots, all-in cascades) — the fallback is
ALWAYS the 6-max core, never an error; stress deals as their own gate before every relay ship.

## AUSLESE v3 NAMED (2026-08-17 afternoon) — the calibrated selection

**sel_m15 = sel_guard with 15pp margin.** Three direct runs vs v1 (+10.50±2.10 / +1.11±2.16 /
+2.63±1.22 on 90k) → pooled **+3.94±0.95**, conservatively without the high first run +2.13±1.06;
plus the 183k anchor **+8.68±1.28 vs basis**. Named according to the three-runs rule (the replication
heterogeneity — 3σ between run 1 and 2 — is journaled as a fat-tail finding; robust SE =
open tool package). Version chain: basis → v1 (+6.1) → **v3 (~+9 cumulative)**. v2/sel_all
and einmal_guard honestly rejected; m20 tips over (plateau edge reached).

## ROUND 4 — the 2h campaign (2026-08-17 noon): the dose-response curve of selection

**Margin sweep (25k decks each, quiet channel vs v1):** m06 +0.06±1.45 (NEUTRAL — indistinguishable
from 3pp) · **m10 +5.64±1.74 (ANWENDEN)** · **m15 +10.50±2.10 (ANWENDEN)** — monotone curve,
Snowie's "3pp too loose" confirmed three times and quantified. **Decisive m15 vs basis:
+8.68 ± 1.28 on 183,200 decks (366k hands) → ANWENDEN.** (Note: pairwise edges are
NOT additive in poker — m15-vs-v1 + v1-vs-basis ≠ m15-vs-basis; non-transitivity is normal.)
**einmal_guard +0.41±1.05 NEUTRAL:** the multi-street discipline brings nothing that the
stricter margin does not solve better — family to the archive.
**6-max catalog v0 (30k hands, 298k graded decisions):** position ledger for the first time
readable and plausibly ordered (BTN +33.5 · HJ +15.8 · UTG +6.8 · CO +2.4 · BB −28.9 · SB −29.6);
facing catalog: fold_freq flop 0.216 / turn 0.297 / river 0.337 at median bets 0.43/0.38/0.37
pot — flop fold BELOW the MDF allowance (0.30 at 0.43-pot bets), no over-fold flag: the
6-max ecology does not fold too much, the HU flop overfold is HU-specific.
**RUNNING:** m15 replication on fresh seeds (naming prerequisite) + m20 gradient probe
(does the curve end at 15pp?). Name only after passed replication.

## Candidate round 1 completed (2026-08-16 evening) — both families cleanly settled

**G5 PASSED:** 24 cores locally, pargate holds **2,459 decks/min over 40 min** (~4,900 hands/min;
scaling ~1.0x/core). For individual gates the pod is therefore unnecessary — the $30 stay for R3.
**podds_guard (river):** channel too rare (0.015 nodes/hand, ~24 nodes per 1,600 hands) — the
NEUTRAL judgments were "channel too coarse", not "no effect". Family paused until constructed decks.
**mdf_guard (flop):** measured three times, 400 → 1,200 → **99,000 decks: −3.26 ± 2.19 → NEUTRAL**
(95% band [−7.6, +1.1], ~1.5 SE below zero). Fourth data point of the doctrine: frequency matching without
SELECTION does not print. No name assigned, basis stays.
**Lesson for candidate round 2:** candidates must carry selection (WHICH hands continue
— tracker range/made-hand read), not frequency; and the measurement channel is measured BEFORE the build (AP8).

## First full run AFTER the review fixes (2026-08-16, local, 75 s) — the reference run

900 hands, 6,080 graded decisions. **HU (600, 4-fold crossed):** HART 0 · P 0 · L 62
(2.0% lead rate) · F 1 · button net **+33.4 bb/100** (pre-run +32.6 — the magnitude is stable) ·
pair drift +106.8 ± 70.3 (1.5 SE, PASS; second run in a row positive → observe).
**6-max (300, repaired ecology):** HART 0 · P 0 · F 1; position ledger at n=50/position
still noise (BB +122 implausible, SB −194 plausible — readable only from ~1,000 hands).
Gate self-test exploit-OFF +1.4 ± 2.2 → NEUTRAL (consistent over three runs).
Known minor issue: top-L proposals contain duplicates from mirrored passes
(dedupe in the improver open).

## First measurements (pilot 2026-08-16, local, 52 s)

HU 300 hands: HART 0 · P 0 · L 35 (hindsight calls up to 112 bb below pot odds) · F 1 ·
button net +32.6 bb/100 (card-adjusted position value = new benchmark quantity) ·
pair drift +294 ± 195 (1.5 SE, compatible with 0 — more pairs needed). 6-max 200 hands:
HART 0 · P 0 · F 2 (incl. mdf_flop). Gate self-test exploit-OFF vs ON: +2.1 ± 3.3 → NEUTRAL.

## Paper anchoring 2026 (2026-08-16 — three extractions triangulated)

Sources: Brown VNM-169 (`knowledge_base/theory/brown_vnm_169.md`, full extraction ssrn-6709840),
SPIRAL ICLR 2026 (`../reports/SPIRAL_NOTES.md`), Diniz PokerBench-SFT (PDFs in `books/papers/Poker Math 2026/`).

### 1. Brown checks into the wiring backlog (V1–V4, specified in brown_vnm_169.md §4)

| Check | Level | Core | Priority |
|---|---|---|---|
| **V1 `value_ordnung`** | F | Value bets per bucket = upper set of the equity ordering (Spearman anchor 0.98); Brown-27 bluff classes EXCLUDED | **★ range-free → queue BEFORE wave 1b** (after the running per-decision checks, before the remaining aggregation F) |
| **V2 `fold_ordnung`** | F | Defense mirror: continue set = top of the posterior ordering; covers the seesaw break class (v8) WITHOUT frequency prescription | with V1 (shares reference + fields) |
| **V3 `bluff_struktur`** | F | Bluffs from the cycle region (equity 0.36–0.50), junk share > band = finding | after wave 1 (needs hindsight/villain_hole) |
| **V4 `bluff_persistenz_hoch_b`** | L | Short persisters/junk bluffs at bet-to-pot ≥ 2 = individual lead | after V3 |

Fraction-reference obligation (E1) applies: reference ordering = **exactly enumerated** 169 equities
((2·wins+splits)/(2·1,712,304)) — the repo asset `knowledge_base/ranges/preflop_eqmatrix.json`
is MC sims=600 and NOT reference-grade; enumerate exactly once before V1 wiring.
Knob bounds (ORDNUNG_RHO_MIN [0.80; 0.98] start 0.90 among others) are in brown_vnm_169.md;
oracle knobs remain improver-locked. On the BLUFF side ordering fidelity is explicitly
NOT to be expected (persistence correlation −0.42) — an oracle that measures bluffs against the equity ordering
measures wrongly.

### 2. Binding candidate design rule: bluff selection STRUCTURALLY, never quota

Brown, independently of our measurement: **0 of 169 hands are bluffs in all four
matrix variants** — WHICH weak hand bluffs is pure matrix geometry (cycle position/
suitedness; in the multi-street game: blockers/board/sizing), never weakness and never a
frequency target number. That is the theoretical confirmation of the fourth measurement data point
(mdf_guard −3.26 ± 2.19 NEUTRAL at n=99k): **frequency without selection does not print.**
Binding for every candidate round from now on: a candidate that raises/lowers a frequency
without carrying the SELECTION (which hands/classes) is not built (sel_guard = the first
candidate of this type). In addition (Brown §5): roles are functions of the bet size, not of the
hand — static hand→role tables are wrong per Brown; mixing frequencies follow
predator-prey margins, not one's own hand strength (the formal reason for the seesaw / against
purify flattening).

### 3. SPIRAL-RAE = registered reward design for EVERY future RL run

The −90 league regression is structurally SPIRAL's fixed-opponent finding (Mistral opponent: win rate
0→62.5% with benchmarks BELOW basis = exploitation instead of learning). Registered (design in
../reports/SPIRAL_NOTES.md §5, NOT started, needs user go + measurement slot): (1) opponents = self-play copies
instead of sixmax league (league only eval from now on), (2) RAE instead of GRPO group normalization — position-
and format-conditioned EMA baselines `b ← 0.95·b + 0.05·R`, `A = R − b` (BB/BTN have
inherently different EVs = confounded), (3) reward = pure chip outcome terminal, without
shaping, (4) fully online, (5) thinking-collapse watchdog (trace length + grad norm).
Gate: paired Analyzer exports ($0) → AIVAT; win rate vs training opponent FORBIDDEN as a metric.
Honestly: HU theoretically clean (two-player zero-sum), 6-max without convergence guarantee;
expectation = elimination of the −90 class, no promise below −20.

### 4. Diniz (PokerBench-SFT) — no new lever, two uses

93.3/91.8% action acc via SFT = pure label agreement, no EV → confirms the
imitation-ceiling doctrine. Usable: (a) logprob scoring over LEGAL actions instead of
string matching for every future LLM eval, (b) SCORE formula (outs × pot/call, algebraically =
pot odds; bias +≈1pp, 97% concordance, ZERO wrong calls) as a narrowly bounded one-sided
oracle KNOB at level L/F: "SCORE fold ⟹ exact fold or marginal call in the Δ band".
