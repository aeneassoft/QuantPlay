# HU OPTIMAL MAP — full assessment before v9 (2026-09-01)

**Method:** Four kinds of sources, collected separately and synthesized here: (1) measurement data of the
GPU relay (deep replay 571 decisions with action EVs, HH mine, GPU audit, gate history),
(2) documented open work sites (level audit/army/root sweep, deduplicated against what landed since 30.08.),
(3) code as-is verification (flag defaults, trees, texture systems — every line file:line-
checked, agent "code-ist"), (4) 6max sharing structure (agent "sixmax-transfer").
**6max column:** AUTO = takes effect automatically (shared substrate: cards/evaluator/equity/postflop) ·
BRIDGE = takes effect automatically in HU-collapsed 6max pots (Prince takeover in six_server GTO mode,
`--hybrid` export, Snowie bridge — practically a large share of the river spots) · PORT = technique
transferable, needs work · NO = HU-specific.

**Lead finding (deep replay, EV-weighted):** left on the table : errors = **1.6 : 1**. The map is
therefore sorted by EV lever, not by age of the work site.

---

## A. DECISION QUALITY (the money)

**A1 · The missing river RAISE game — largest single gap (31.1bb OVERFOLD in 970 hands).**
Evidence: deep replay — fold→raisejam with Jd8h/9c5c (bluff raises!), fold→call; plus VERPASST_VALUE
5.7bb (call→raisejam) and VERPASST_BLUFF 5.5bb. The TexasSolver census tree HAS river raise arms
(35/65/100/150 + raise 50/100, resolver.py:21-26), the GPU tree too — but the fold decisions
never ASK the solver (play/surgery trigger was ≥30bb; the harvest sits in 8–30bb pots).
Fix: play guard with a deep trigger (~15bb) + fp16 for the latency budget. **→ v9 core.** [6max: BRIDGE]

**A2 · SIZE precision (9.0bb).** raise2.7→raisejam, bet1.5→bet0.35 — the solver size is known
but not played; the r8 surgery override moreover hardcodes 0.75·pot (improver.py, collision
with RIVER_ECALL sizing — dead-code map "double-resolver crossing"). Fix: output the tree-arm size
(already correctly implemented in the play guard). **→ v9 core.** [6max: BRIDGE]

**A3 · Mis-value bets (VERLUST_AGGRO 11.5bb v4 / 27.4bb control).** Partly addressed by
wert_bremse (3× replicated +8); rest = play-guard region between the thresholds. [6max: BRIDGE]

**A4 · VERLUST_CALL is the SMALLEST category in the EV measure (4.1bb).** The famous −121bb AIVAT cell
was predominantly card realization (#3003011: −137bb real, +0.6bb EV diff). Lesson binding: **AIVAT
cells are realization, not decision attribution — prioritization in future only via
action EVs** (tiefen_replay machine). No further defense round justifiable. [6max: AUTO as a lesson]

**A5 · Turn/flop stage unsolved.** Turn: TurnCFR built+cross-validated (OOP r=0.944), deployment too
expensive/quiet (r9_turn 3/3904); flop: no GPU stage; both streets play advisor/heuristic
(solver-EV error there still unmeasured — the river 6.9bb/100 are ONLY the river). Fix path:
canonical board library (A6) instead of live solves. [6max: BRIDGE/PORT]

**A6 · Canonical solve library instead of board categories.** Suit ISO is the only lossless
board abstraction (1,755 canonical flops — fully enumerable with the batch machine at 0.3s/spot;
turn ~16k). ISO cache exists, default OFF (gto_oracle.py:54, raw env read).
Fix: ISO ON (measurement), then flop/turn library for standard geometries+range prototypes.
[6max: BRIDGE — the same boards]

**A7 · Preflop stack-off (GTOW class D, −13.8bb/hand cell).** stackoff_bremse built, 10/10
self-tests, self-play-silent (1 trigger/400) — to be carried as a GTOW arm, proof only at the anchor.
[6max: PORT — class logic the same, ranges different]

## B. RANGE MODEL (the solver's input)

**B1 · Tracker reconstruction does not carry the river CALL defense** (discrimination 0.65/0.53; ranges
after 3 barrels 700–900 combos). BUT: EV-relevant, the range swap flips only 5% of the river VERDICTS
(deep replay) — the big-pot verdicts are more range-robust than thought; the range acts mainly on the
MIXES (34% raw flip). Consequence: range-structure work (line consistency, bet-range DB from
census+showdowns, structural bluff quantities) is **a frequency/policy lever, not a verdict lever** —
important, but to be queued behind A1/A2. [6max: BRIDGE via make_seeded_tracker + PORT for priors]

**B2 · hand-not-in-range** (flop resolver 0/3 maiden flight): solved in the GPU path via hero injection;
open in the TexasSolver path (bot.py:1104 approach documented). [6max: BRIDGE]

**B3 · Preflop prior coarseness** (limp-raise inversion, symmetric 3bet prior — army rest[21]).
[6max: PORT]

## C. COMPUTE / GPU

**C1 · Double resolver at the river** (GTOW channel: TexasSolver ON + GPU guard, 13.5s cold start).
A/B "GPU replaces TexasSolver river" (POKERB_RESOLVER=0) = protocol arm B2, fully pre-registered.
**C2 · fp16** (+64% measured, half=True, default OFF — v9 uses it, A/A must prove it).
**C3 · Entropy anchor (Leal):** CFR+ provably picks low-entropy polytope members; an MMD-like
anchor → max entropy = better hedge (Kuhn 25/25, extensive-form ×5.6). Gate: adversary axis
(exploit_jagd/Fable), NEVER the mirror. [all 6max: BRIDGE]

## D. CODE HEALTH (verified, file:line in the agent report)

**D1 · AKTIV_FALSCH — the HU web app plays a never-measured config:** no PRINCE profile,
exploit=True, full r8_stack chain + RAISE_NARROW=1.0 (server.py:19-43 + launcher). The exploit
deviations and the GTO guard work AGAINST EACH OTHER at the same river node. **Immediate fix (channel
hygiene, no gate needed: the app should play the MEASURED v5 definition):** PRINCE + exploit-OFF
in server.py. [6max: six_server has the env flags correct — check whether PRINCE is missing there too]

**D2 · AKTIV_FALSCH — the 9 AUDIT_FIX bugs run live** (default 0, not in PRINCE_PROFILE;
bot.py:62) **and the advisor role inversion in 3bet pots likewise** (ADVISOR_ROLE_POS=0, bot.py:65-70).
Fix path: as GTOW arm flags (the gym channel is flag-free by design); pre-register the expectation.
[6max: BRIDGE]

**D3 · Silent advisor loads** (advisor.py:62-70, every exception → silently heuristic, 0 log paths) +
no golden vector, no .pt SHA (level audit rank 7, "foundation of all bb numbers"). ~2h. [AUTO]

**D4 · Six board-texture views** (1 canonical + 3 duplicates of the 5-class collapse in
advisor/bot/gto_benchmark + 2 derived) → ONE source (postflop.classify_board), the rest consumers;
byte-identity gate as the refactor barrier. [AUTO — postflop is the widest shared channel]

**D5 · RAISE_NARROW import-time trap:** global on ALL tracker consumers; a later
use_resolver=True in the same process arms v8-K3 without a flag change. Fix: hard code guard
(enforce the contraindication instead of a comment). **D6 ·** gtowizard adapter does not call setze_env()
(stack without env half possible); button_disziplin hardcodes blinds 50/100. **D7 ·** OppModel
is fed under PRINCE but never consumed (state-carrying dead code). **D8 · TOT_HARMLOS**
(no action needed, documented): brain/ entirely, models/ legacy, adaptive/unified_exploit/
playbook/corset/distill/deep_cfr* orphans.

## E. MEASUREMENT/PROOF CHANNEL (institutionalize the v8 lesson)

**E1 · The mirror does not price harvest precision** (v8 postmortem; channel saturation, nz_median
1.9bb). Before every precision build: $0 EV proof on the GTOW hands (action-EV machine) as a
pre-gate; medium term a **re-solver proxy opponent** in the gym (GPU solver as opponent policy) — the
only $0 channel that can price A1/A2/C3. **E2 · GTOW anchor v5** = the absolute proof; everything
since v4 is selection channel (awaits user command; protocol + arms B1/B2 ready). **E3 ·**
AIVAT-light in the mirror (rank 1, open), FDR ledger/Pocock (rank 3/4, partly), deck-bank register
(rank 10, discipline instead of code), LBR v2 as a christening requirement (rank 13, open). **E4 ·** 6max measurement channel:
the 85.9% grade measures the LEAGUE tag core, not bot.py — only `--hybrid` measures the product; pargate6
does not exist (SixMaxBot.rng unseeded = pairing blocker, army rest[32]).

## F. 6MAX TRANSFER SUM

Automatic (AUTO): everything in engine/ (cards/evaluator/equity), postflop.py (widest channel — used
directly by bot.py AND the league), D3/D4 hygiene. Via the BUILT bridge (BRIDGE): the complete
HU stack incl. all v9 river improvements acts in HU-collapsed 6max pots (six_server GTO
mode, --hybrid, Snowie) — that is practically the majority of the 6max river decisions. Deliberately
NOT transferred: the AUSLESE guard CHAIN in the bridge (only env flags act — a wiring
decision that v9 should examine). HU-specific remain: range_tracker walk (2 seats hard),
button_disziplin, blueprint. Real multiway (3+ at the river) needs its own work: multiway equity
missing on both sides, F(s) fold curve is single-opponent, advisor priors HU-trained.

---

## THE v9 CUT (user assignment: build → vs frozen → vs champion)

**v9 = the river harvest package:** play guard deep (trigger ~15bb, fp16, solver sizes from the tree,
addresses A1+A2+A3 rest) + wert_bremse below it + stackoff_bremse (GTOW-silent hardening) on the
r6_button chain. Pre-gates: $0 EV harvest proof on night 2 (E1) → latency smoke → A/A (fp16
determinism!) → ladder vs r8_stack (champion v5) and vs basis (frozen). Pre-registration:
mirror expectation NEUTRAL to slightly positive (v8 lesson — the mirror barely sees harvest); the
ship criterion is non-deterioration in the mirror + a clearly positive EV harvest proof on the
GTOW axis. In parallel (no gate needed): D1 channel hygiene of the HU app.
NOT in v9 (deliberately): range-structure round (B1 — policy lever, needs the E1 proxy channel),
entropy anchor (C3 — needs the adversary gate), flop library (A6 — own round), D2 flags
(GTOW arm, not gym).
