# MEASUREMENT CATALOGUE — what was actually measured in this project

> **What this document is for.** It collects ALL real measurements of the project — self-play, GTO Wizard,
> the Analyzer channel via Chrome, LLM runs, Snowie, tournament, solver validations and runtimes — each with
> number, spread, n, instrument, verdict and **source**. Counterpart to
> [`MODULE_CATALOG.md`](MODULE_CATALOG.md): that one says what a building block DOES, this one says whether it WORKS.
>
> **The most important rule when reading: the CHANNEL decides what a number means.**
> A self-play mirror value is a non-regression bound, not a proof of strength. An
> Analyzer EV loss is a decision grade, not a result. Only the GTOW AIVAT value is the axis on
> which the project goal is defined. Numbers from different channels must **not be added** — the
> guard chain refuted that by measurement (individual measurements summed to ~+53, measured was +30.6).

## ★ Three corrections that came out of compiling this catalogue (2026-09-10)

**1. The only valid GTOW anchor is far less precise than assumed.**
Recomputed from the hand histories themselves (`data/sessions/gtow_hands_1787027076.jsonl` +
`_1787033025.jsonl`, n=979): mean **−21.12**, per-hand SD **294.1**, **SE 9.40** — not 6.8.
The constant used in the project, **c ≈ 214, stems from the v2.2 era** (recomputed there: SD 213.5 at
n=2393) and underestimates the spread of today's bot by roughly 28 %.

| Consequence | with c = 214 | with measured c = 294 |
|---|---|---|
| Hands for SE = 4 bb/100 | 2,862 | **5,407** |

The anchor's 95 % band is therefore roughly **[−39.5, −2.7]** instead of the much narrower band that planning
has used so far. **Every hand-budget calculation in the repo that rests on c = 214 must be corrected accordingly.**

**2. "−21 is today's champion" is wrong.** The value belongs to **v4/r6_button on PRINCE**, not v5.
v5 has **no** GTOW anchor to this day (journal `KONSULT-SOL-KORREKTUR`, 2026-09-10).

**3. Two Kaggle measurements are invalid.** The reference value (champion vs base, +55.8 ± 38.0) and the
v9 run (600 decks, exactly 0.0) ran without the `deal` marker in the adapter; without it
`improver._river_spot_und_frage` returns `None`, and so **the champion's GPU surgery could not
fire either**. Details: [`../reports/KAGGLE_ARENA.md`](../reports/KAGGLE_ARENA.md).

Further corrections, outdated numbers and numbers without evidence are in the section **Addendum and corrections**
at the end. Whatever is listed there under "Outdated — do not cite any more" no longer belongs in new documents.

## Contents

- [The Autogym journal](#the-autogym-journal)
- [1 — HU mirror (`kanal: pargate_mirror`) — the main chain](#1--hu-mirror-kanal-pargate_mirror--the-main-chain)
- [A. Live AIVAT against the GTOW API](#a-live-aivat-against-the-gtow-api)
- [1. Upload rules and pitfalls (all learned the hard way)](#1-upload-rules-and-pitfalls-all-learned-the-hard-way)
- [LLM and brain measurements](#llm-and-brain-measurements)
- [Self-play, gym and gate measurements](#self-play-gym-and-gate-measurements)
- [Snowie, tournament, multiway, vision, solver validation](#snowie-tournament-multiway-vision-solver-validation)
- [Where the raw data lives](#where-the-raw-data-lives)
- [Addendum and corrections](#addendum-and-corrections)

---

## The Autogym journal

`data/autogym/journal.jsonl` is the measurement log of the self-checking training loop (Autogym). It
records **gate decisions**: a candidate bot is played against an incumbent on identical
decks, and the paired delta in bb/100 is entered with spread and verdict. What the channel
can do: candidate-vs-candidate comparisons **inside the project's own self-play ecology** on very large
samples (30k–183k decks, $0, deterministic with correct seeding), plus the bookkeeping of the
live GTOW runs and the auxiliary instruments. What the channel **cannot** do: an absolute verdict on strength.
A positive mirror number means "beats its predecessor in our own ecology", not "is closer to
GTO" — the journal itself documents this non-transitivity (J:92, J:93) and the doctrine that the
mirror is only a **non-regression bound**, while the proof of effect against adaptive
opponents lies on a different axis (J:74).

**Citation style:** `J:20` = `data/autogym/journal.jsonl`, line 20 (the file line index; entries are
one JSON line per entry, chronological). Where the entry carries its own `quelle` field, that is
named in addition.

---

### The channels in this journal — one sentence each

| Channel | What it can measure | What it CANNOT measure |
|---|---|---|
| **Oracle / selftest** (`autogym/oracle.py`, tiers HART/P/L/F) | Whether a decision violates a formula bound (pot odds, MDF) — as a *lead*, with severity in bb | Whether the violation costs EV; formula conformity is not a statement about profit |
| **pargate mirror** (`autogym/pargate.py`, paired decks, button swap) | Paired delta candidate − incumbent in bb/100 in the self-play ecology, very large n | Absolute strength; hardening against *adaptive* opponents is structurally invisible to negative here (J:74) |
| **envgate** (shared third opponent `GTOBaseline`) | Whether two arms fare differently against the same foreign opponent | Nothing shippable — results are called `KANAL_*` in the project and are explicitly not ship evidence |
| **GTOW live AIVAT** (`benchmark/gtowizard.py`, real hands vs GTO Wizard AI) | Absolute anchor in bb/100 against a re-solver, variance-reduced | Costs hand budget; no pairing, SE ≈ 214/√n → bands of ±4 need ~11,000 hands (J:111) |
| **Adversary** (Fable LLM duel, `exploit_jagd`) | Whether a pattern is *exploitable* (counted patterns, harvest in bb/100) | Statistically robust means — 62–92 hands are anecdote with counted patterns |
| **Replay / solver audit** (`tiefen_replay`, `v8_replay_gegentest`, `river_bill_diagnose`) | Counterfactual EV decomposition on already-played GTOW hands, without burning new hands | Realised bb — these are solver EVs, not played results |
| **pargate6** (6-max, hero rotates over 6 seats) | Paired 6-max delta against the league core | An external anchor — the league is the project's own ecology ("tag plays at home") |
| **Kaggle arena** (`benchmark/kaggle_arena.py`, open_spiel/pokerkit) | Cheap volume mirror and an LLM ecology | A GTO anchor — the field is LLMs, not a re-solver; also 100 bb instead of GTOW's 200 bb (J:122) |

**One hard cut across the whole table:** all runs **before the evening of 2026-08-17** (rounds 1–4,
J:15–J:41) were produced before the spot-RNG seeding fix landed. The journal itself shows that the
per-deck pairing broke before that because the MC equity calls were unseeded (J:33), and only
with round 5 does it register an A/A null test demanding exactly 0 (J:42, passed J:50). Direction and magnitude
of these early numbers are robust; the stated SEs only partly so.

---

### Chronological table — all entries with a number

#### Phase 1 — Oracle leads and first gates (2026-08-16)

| Date | What was measured | Instrument / channel | Result (number ± spread, n) | Verdict | Source | Still valid? |
|---|---|---|---|---|---|---|
| 2026-08-16 19:25 | `call_unter_pot_odds`, river calls below pot odds | Oracle tier L (self-play decisions) | Severity 99.01 / 52.00 / 16.25 bb; eq 0.00 vs required 0.25/0.31/0.25 | EXPERIMENT CANDIDATE | J:1–J:3 | As a **lead** yes; the guard built from it measured NEUTRAL (J:15/J:17) |
| 2026-08-16 19:27 | `mdf_flop`, fold frequency on the flop vs MDF | Oracle tier F | Fold freq 0.63 vs MDF-allowed 0.24 (n=151), OVER-FOLD | EXPERIMENT CANDIDATE | J:4 | Lead; derived guard NEUTRAL (J:18). Later qualified: the flop overfold is HU-specific, 6-max folds 0.216 (J:38) |
| 2026-08-16 19:27 | `call_unter_pot_odds` (2nd round) | Oracle tier L | Severity 112.12 / 96.00 / 86.32 bb | EXPERIMENT CANDIDATE | J:5–J:7 | Lead |
| 2026-08-16 19:40–21:51 | `station_nicht_geschlagen` (bot vs never-folder) | Selftest, 1-hand horizon | +394.9 ± 279.9 (60 decks) — logged 5× identically | EXPERIMENT CANDIDATE | J:8, J:9, J:14, J:16, J:19 | Health signal only; identical repetition = the same deterministic run, not independent n |
| 2026-08-16 19:58 | `mdf_flop` (larger sample) | Oracle tier F | Fold freq 0.61 vs MDF 0.32 (n=304) | EXPERIMENT CANDIDATE | J:10 | Lead |
| 2026-08-16 20:06 | `podds_guard_river` (guard from the L leads) | pargate mirror | +0.50 ± 0.50 bb/100 (200 decks) | NEUTRAL | J:15 | Yes as a negative finding. Notable: `se == bb100` exactly — thin channel, few triggers |
| 2026-08-16 20:10 | `podds_guard_river` (4× n) | pargate mirror | +0.31 ± 0.31 bb/100 (800 decks) | NEUTRAL | J:17 | Yes — a formula guard from pot odds does not print |
| 2026-08-16 20:38 | `mdf_guard_flop` | pargate mirror | −7.40 ± 28.39 bb/100 (400 decks) | NEUTRAL | J:18 | Yes as a negative finding; SE 28 = uninformative, channel was too small |
| 2026-08-16 22:11 | `sel_guard_flop` ("AUSLESE v1") vs frozen base | pargate mirror | +4.70 ± 2.06 bb/100 (99,000 decks), CI95 [0.6; 8.8] | APPLY | J:20 | Historical; chain since built over 4× (v3/v4/v5) |
| 2026-08-16 23:39 | `sel_guard_flop`, replication on a fresh deck universe | pargate mirror | +7.49 ± 2.08 (99,000 decks); pooled ≈ +6.1 ± 1.5 over 198k | APPLY confirmed | J:21 | Historically robust (replication passed), superseded |
| 2026-08-16 23:39 | `sel_all` (turn/river selection) sanity | pargate mirror | +6.53 ± 22.22 (1,200 decks) | NEUTRAL | J:22 | Yes — "direction positive, channel noisy" |
| 2026-08-16 23:39 | `lizenz_guard` | pargate mirror | **exactly 0.00 ± 0.00** (1,200 decks) | DIAGNOSIS NEEDED | J:23 | Yes as an instrument finding: the guard **never fired** (dead wrapper / empty channel) |

#### Phase 2 — Rotation, replication duty, transfer (2026-08-17 early)

| Date | What was measured | Instrument / channel | Result (number ± spread, n) | Verdict | Source | Still valid? |
|---|---|---|---|---|---|---|
| 2026-08-17 00:10 | `sel_all` (run with dead licence component) vs base | pargate mirror | +6.13 ± 2.03 (98,960 decks) | beats base, but not v1 | J:24 | Historical |
| 2026-08-17 00:21 | `lizenz_guard` with live wrapper | pargate mirror | −0.06 ± 0.69 | no effect | J:26 | Yes — the bluff-licence theory has no effect in the HU mirror |
| 2026-08-17 00:21 | `sel_all` vs `sel_guard` ("AUSLESE v2"), head-to-head | pargate mirror (quiet channel) | +3.00 ± 1.40 (30,000 decks) | APPLY+ROTATION | J:25 | **NO — refuted**, see the two following rows |
| 2026-08-17 00:32 | Replication of the same comparison | pargate mirror | +0.44 ± 1.09 (30,000); pooled +1.41 ± 0.86 | **REPLICATION NOT PASSED** | J:27 | Yes — the rotation was premature, v1 remained the reference |
| 2026-08-17 01:02 | Third head-to-head run, final verdict v2 | pargate mirror | +0.18 ± 0.73 (90,000 total); pooled +0.69 ± 0.56 | **ROTATION REJECTED** | J:28 | Yes — the +3.00 first run was sample luck; the three-runs rule was born here |
| 2026-08-17 01:38 | 39 external blunders (PokerSnowie grading) individually post-mortemed | external grading | 15/39 = call-downs too loose (sel_guard overdosed); 11/39 = missed value, clustered in turn checks | Candidates derived | J:29 (`../reports/SNOWIE_BLUNDER_ANALYSIS.md`) | Yes — the 11/39 finding led directly to `turn_wert` (J:61–J:66) |
| 2026-08-17 02:04 | `sel_guard` against a **foreign** opponent (GTOBaseline) | Transfer test, unpaired | −3.78 ± 30.31 (3,000 decks); AUSLESE −23.40 ± 21.99 vs base −19.62 ± 20.86 | uninformative | J:30 | Only as a warning; spread unusable |
| 2026-08-17 02:19 | 20 adaptive Dirichlet hunters vs frozen base | `exploit_jagd` | Adaptive +8.87 ± 6.9 (n=100,000) vs null control +7.73 ± 8.7 → adaptation gain ≈ +1, **not significant**; all 20 hunters converge on VPIP 0.75–0.77 / fold_to_bet 0.29–0.31 / aggression 0.31–0.34 | Structure > adaptation | J:31 | Yes — the hardening map is cited to this day; consistent with the later exploit refutation (J:113) |
| 2026-08-17 02:24 | the same transfer test, correctly paired | Transfer test, paired | −3.80 ± 12.87 (3,000 decks) | uninformative | J:32 | Superseded by its own error diagnosis in J:33 |
| 2026-08-17 02:25 | Why the pairing did not bite | Instrument diagnosis | SE stays 12.9 because `equity_vs_*` is **unseeded** → both arms diverge stochastically on every deck | Result uninformative | J:33 | **Yes, and central** — explains why all numbers before the seeding fix must be read with caution |

#### Phase 3 — Round 4: margin sweep up to "AUSLESE v3" (2026-08-17 midday)

| Date | What was measured | Instrument / channel | Result (number ± spread, n) | Verdict | Source | Still valid? |
|---|---|---|---|---|---|---|
| 2026-08-17 12:16 | `sel_m06` (margin 6pp) vs v1 | pargate mirror | +0.06 ± 1.45 vs v1; +0.30 vs base | NEUTRAL | J:34 | Yes |
| 2026-08-17 12:31 | `sel_m10` vs v1 | pargate mirror | +5.64 ± 1.74 vs v1; +8.72 vs base | APPLY | J:35 | Historical; superseded by m15 |
| 2026-08-17 12:45 | `sel_m15` vs v1 | pargate mirror | +10.50 ± 2.10 vs v1; +17.47 vs base | APPLY | J:36 | **First-run value; see J:40 — replication came in 3 σ lower** |
| 2026-08-17 12:53 | `einmal_guard` (multi-street discipline) | pargate mirror | +0.41 ± 1.05 vs v1 | NEUTRAL | J:37 | Yes — discarded |
| 2026-08-17 12:55 | 6-max catalogue, 30,000 hands | Self-play catalogue | Position bb/100: BB −28.9 / SB −29.6 / BTN +33.5 / HJ +15.8 / UTG +6.8 / CO +2.4. Facing: flop 21,165 nodes, fold 0.216, bet 0.431 pot; turn 11,565, fold 0.297; river 8,143, fold 0.337 | Catalogue | J:38 | Yes — reference values; shows that the flop overfold was HU-specific |
| 2026-08-17 13:42 | `sel_m15` vs **base**, decisive run | pargate mirror | **+8.68 ± 1.28 bb/100 (183,200 decks)**, 20 workers, 2,821 s, 3,896 decks/min | APPLY | J:39 | Yes as the largest single anchor of the early phase (n=183k), but before the seeding fix |
| 2026-08-17 14:02 | Replication `sel_m15` vs `sel_guard` | pargate mirror | +1.11 ± 2.16 (30,000) — **3 σ** away from the first run +10.50 ± 2.10; m20 probe flips: −1.52 ± 1.54 | REPLICATION HETEROGENEOUS | J:40 | **Yes, and methodologically the most important row:** fat tails of the per-deck edges make 2SE intervals too optimistic |
| 2026-08-17 14:31 | Naming `AUSLESE v3` (= `sel_m15`) | pargate mirror, 3 runs | +10.50 ± 2.10 / +1.11 ± 2.16 / +2.63 ± 1.22 (90k); pooled **+3.94 ± 0.95** vs v1; without first run +2.13 ± 1.06; 183k anchor +8.68 ± 1.28 vs base | APPLY + NAME | J:41 | Historical; margin 15pp = plateau edge |

#### Phase 4 — Round 5: seeding fix, estimator revision, "AUSLESE v4" (2026-08-17 evening)

| Date | What was measured | Instrument / channel | Result (number ± spread, n) | Verdict | Source | Still valid? |
|---|---|---|---|---|---|---|
| 2026-08-17 19:53 | **A/A null test** (candidate == incumbent) | pargate mirror | **0.0 ± 0.0**, trim 0.0 ± 0.0, max_abs_edge **0** (1,936 decks) | passed | J:50 | Yes — from here on the mirror is process-deterministic; everything before with reservations |
| 2026-08-17 (beforehand) | Channel width of `sel_all_m15` measured **before** the build | Channel survey (400 decks) | Turn-fold spots **0/800 hands**; river 0/15 flip at m15 | Expectation ~0 | J:43 | Yes — the principle "measure the channel before the build" (AP8) |
| 2026-08-17 (beforehand) | Channel width of `turn_wert` | Channel survey (400 decks) | 40/800 hands (5 %) would bet; 208 turn checks, 60 strong made hands, 40 with eq ≥ 0.60 | widest new channel | J:44 | Yes |
| 2026-08-17 (beforehand) | `turn_def_adv` back-story | Analyzer (foreign channel) | v5C history: **−1.87** (resolver-OFF) | Channel open | J:48 | Historical reference from the Analyzer channel, only cited here |
| 2026-08-17 20:01 | `sel_all_m15` vs `sel_m15` | pargate mirror | 0.0 ± 0.0 (29,920 decks) — **0 divergent decks** | NEUTRAL | J:51, interpretation J:59 | Yes — reinterpretation: **"no channel", not "refuted"** |
| 2026-08-17 20:10 | `turn_wert` run 1 | pargate mirror, trim estimator | +1.64 ± 4.03; **trim 0.00** | NEUTRAL | J:52 | **NO — verdict later overturned**: the 5 % trim was blind for thin channels (J:54), re-evaluation see J:61–J:63 |
| 2026-08-17 20:18 | `wert_plus_all` | pargate mirror | +1.64 ± 4.03 (29,920) | NEUTRAL | J:53 | Identical value to J:52 → the same effective arm |
| 2026-08-17 20:40 | `prince` against GTOBaseline | envgate | delta **−68 raw** | **Channel artefact** | J:60 | Yes as a warning: the reference exploits the weak opponent, the arm does not — **no verdict on PRINCE vs GTOW** |
| 2026-08-17 20:48 | `turn_wert` run 2, estimator v2 (raw mean + sign test) | pargate mirror | **+9.39 ± 4.06** (29,920); nonzero 2,594 (8.67 %), nz_pos 1,530, sign-test z **9.15**, nz median 264 chips | APPLY | J:61 | Yes |
| 2026-08-17 20:56 | `turn_wert` run 3 | pargate mirror | **+10.78 ± 4.00** (29,920); sign-test z 8.98 | APPLY | J:62 | Yes |
| 2026-08-17 21:33 | `turn_wert` pooled 3×30k | pargate mirror | **+7.27 ± 2.33 bb/100 (89,760 decks)**; nonzero 8.58 %, sign-test z **14.93** | APPLY | J:63 | Yes — replicated three times; the oldest leak (turn under-betting) |
| 2026-08-17 21:44 | K3 share (deception) **inside** the combination | envgate, paired | +10.19 ± 4.01; sign-test z +5.4; nz median +198. K3 **alone not replicated** (+8.7 / +0.3 / −4.7) | Assembly as a unit | J:64 | Yes — documented interaction; K3 alone is **not** established |
| 2026-08-17 21:54 | Staircase vs frozen base | **envgate** (shared opponent GTOBaseline, resolver-OFF) | `auslese_v3` +21.36 ± 6.03; `kombi_r5` **+49.79 ± 7.99**; paired step v3→new **+28.44 ± 6.17** (sign-test z 10.1), 12,000 decks | Step established | J:65 | **Restricted** — envgate numbers are called `KANAL_*` in the project and are explicitly **not ship evidence** |
| 2026-08-17 21:54 | Naming `AUSLESE v4` | Summary | Unit replicated 3× (+26.4 / +25.2 / +36.2 vs v3 reference); `turn_wert` 3× mirror +7.27 ± 2.33; RN10 3× (+16.8 / +13.7 / +9.2); K3 in the ensemble +10.2 ± 4.0; A/A exactly 0 | NAMED | J:66 | Historical (v5 is champion) |
| 2026-08-17 22:36 | **Re-evaluation of all round-5 verdicts** with bootstrap CI + permutation p | Estimator v3 | `turn_wert` 3×30k CI [+2.69; +12.05], p = 0.0007 HOLDS; RN10 all 3 runs hold (p ≤ 0.004); `kombi_r5` holds (p = 0.0002); **RN05 drops to NEUTRAL in 2/3 runs** | Revision | J:68 | Yes — RN05 was never in the version |
| 2026-08-17 23:25 | **v4 core vs frozen base**, pooled 3 runs | pargate mirror | **+16.14 ± 2.77 bb/100 (89,760 decks)**, CI95 [+10.74; +21.56], perm_p 0.0002, nonzero 20.63 % | APPLY | J:70 | Yes — the clean mirror anchor for v4 |

#### Phase 5 — Adversary axis and hardening (2026-08-17 night / 2026-08-18)

| Date | What was measured | Instrument / channel | Result (number ± spread, n) | Verdict | Source | Still valid? |
|---|---|---|---|---|---|---|
| 2026-08-17 23:41 | LLM adversary (Fable) vs v4 | Adversary duel, file-based | **62 hands, +115.5 bb** (explicitly anecdote). Counted patterns: button open-fold ~29 %, limp-call→fold-vs-c-bet 5/7, river station 4/5 big calls with losers (~90 bb), check-raise without follow-through 3/3, no mixing; `turn_wert` bets 3/3 as a tell | Pattern finding | J:71 | Yes — the counted patterns; the bb value is **not** an estimate, only anecdote |
| 2026-08-18 00:11 | `r6_ecall` (river eCall guard from the Fable finding) | pargate mirror | **−4.15 ± 0.97**, CI [−6.1; −2.3], sign −4.7, nz median −1,452 | **REJECT** | J:72 | Yes — in the mirror the folded river calls are value folds; rejected as built |
| 2026-08-18 00:11 | `r6_button` (button discipline) | pargate mirror | +0.71 ± 2.18; sign +2.1; channel 16.7 % | NEUTRAL, hardening candidate | J:73 | Yes — only passes the non-regression bound |
| 2026-08-18 00:11 | Doctrine finding from J:72/J:73 | Instrument doctrine | Hardening guards against adaptive opponents are **structurally invisible to negative** in the mirror | Protocol rule | J:74 | Yes — binding: mirror = bound, adversary = proof of effect |
| 2026-08-18 01:24 | Fable retest against the hardened stack | Adversary duel | **92 hands: harvest 186 → 58 bb/100**; open-folds **0/46** (previously 29 %); 3-bet attack on the trash open net −21 bb. Open: river eCall (5/5 value bets paid off), `turn_wert` SIZE tell 7/7 | HARDENING PROVEN | J:75 | Yes — the only proof of effect on the adversary axis |
| 2026-08-18 01:41 | **Final v4 stack vs base** | pargate mirror | **+23.36 ± 5.32 bb/100**, CI95 [+12.75; +33.72], perm_p 0.0002, sign-test z 9.72, nonzero 37.41 % | APPLY | J:76 | Yes (v4 state; v5 came later) |

#### Phase 6 — GTOW live runs (2026-08-18) — the only absolute anchor

| Date | What was measured | Instrument / channel | Result (number ± spread, n) | Verdict | Source | Still valid? |
|---|---|---|---|---|---|---|
| 2026-08-18 01:50 | Pre-registration + smokes of the v4 relay | GTOW live AIVAT | Smokes **(n=20, −21.34)** and **(n=100, −59.03)**; pre-registered honest anchor band −25…−30 | Smoke | J:77, J:78 | Yes as protocol; n=20/100 are statistically practically empty |
| 2026-08-18 03:47 | Night 1 chunk 1 | GTOW driver | Status FAILED (no number) | — | J:80 | Superseded — the "failure" was a driver bug, see next row |
| 2026-08-18 03:55 | **Recovery** of all hands after the cp1252 encoding bug | GTOW HH files, recomputed | Chunk A n=500 **−26.59 ± 7.32**; B n=500 **−54.98 ± 15.37**; C n=497 **−31.65 ± 9.88**; v4 pool n=1,617 ≈ **−38.9** | Recovery validated (smokes reproduced exactly) | J:81 | Yes as a number — **but the arm was the bare gym config without resolver/PRINCE, so not a v4 verdict** |
| 2026-08-18 04:12 | Fourth recovered chunk | GTOW HH | n=500, AIVAT **−48.37 ± 17.52** | — | J:82 | ditto |
| 2026-08-18 04:12 | **Night-1 final pool** | GTOW live AIVAT | **n=2,117, AIVAT −41.11 ± 6.31** | red finding | J:83 | Yes as a measured value, **NO as a v4 verdict** — wrong arm (bare gym config) |
| 2026-08-18 06:24 | Night 2 chunk 1, **control arm** PRINCE resolver-ON | GTOW live AIVAT | n=488, AIVAT **−31.34** (no SE in the entry) | Control | J:85 | Yes |
| 2026-08-18 08:03 | Night 2 chunk 2, arm `v4_prince` | GTOW live AIVAT | n=490, AIVAT **−14.33** | — | J:86 | Yes |
| 2026-08-18 10:04 | Night 2 chunk 3, arm `v4_prince` | GTOW live AIVAT | n=489, AIVAT **−27.92** | — | J:87 | Yes |
| 2026-08-18 12:42 | **Night-2 conclusion** (chunk 4 lost in a deadlock) | GTOW live AIVAT, sequential arms | Control n=488 **−31.34**; `v4_prince` n=979 **−21.12**; delta **+10.23**. Night 1 for comparison n=2,117 −41.11 | v4-on-PRINCE better than control | J:88 | **Yes — to this day the only GTOW-confirmed value of the project** (−21.1). Caveat: no pairing, unequal n, **no SE in the entry**; by the SE arithmetic noted in the journal (c = 214 bb/100·√n, J:111) the SE would be ≈ 6.8 — derived, not measured |
| 2026-08-18 02:29 | Plan: AIVAT calibration ("is AIVAT cheating?") | Test plan | A fold agent would have to show exactly **−75 bb/100**; cross-check Analyzer 19.3 ≈ AIVAT −20 so far argues for honesty | PLAN | J:79 | The plan was **never executed** — the calibration is still outstanding |

#### Phase 7 — River foundation, GPU resolver, "AUSLESE v5" (2026-08-30 / 08-31)

| Date | What was measured | Instrument / channel | Result (number ± spread, n) | Verdict | Source | Still valid? |
|---|---|---|---|---|---|---|
| 2026-08-30 19:55 | `river_bill_guard` confusion matrix on GTOW night-2 hands | Replay over logged live hands | 20 trigger spots; guard folds 5: **3 correct +141 bb, 2 wrong −121 bb, net +20 bb**. Discrimination: tracker eq does **not** separate winners/losers (0.578 vs 0.513; PRINCE env 0.652 vs 0.532); ranges after 3 barrels still 700–900 combos | Threshold guard does not carry | J:89 (`research/river_bill_diagnose.py`) | Yes — justifies the switch to the GPU solver instead of a threshold heuristic |
| 2026-08-30 20:20 | GPU relay day 1 | Verification against exact references | `gpu_eval` **16.8 M hands/s**, 250k pairs **0 errors**; `gpu_equity` exactly identical to CPU enumeration; `gpu_cfr` hits the clairvoyance solution exactly (bluff 0.333 / call 0.500, expl 0.014 %); batch B=256 → **0.30 s/spot amortised**; resolver navigates **571/571** night-2 river spots | Building blocks verified | J:90 (commits 2b57206/297eaf9) | Yes |
| 2026-08-30 20:20 | Solver audit of the base actions | GPU resolver audit | check/fold solver-conformant (p 0.86 / 0.83); **bet is the weakest class (p 0.45, 15 % clear contradictions)**; disaster calls get solver fold p > 0.95. `r8_gpu` guard folds 3/22 real big-pot calls, net **+66.9 bb counterfactual** | Surgery established | J:90 | Yes |
| 2026-08-30 20:20 | `r7_bill` in the mirror | pargate mirror | **EXACTLY 0** — never fires in the gym | GTOW-axis guard | J:90, J:91 | Yes — not taken into the stack |
| 2026-08-30 20:37 | `river_wert_bremse` three-runs rule | pargate mirror, 3 disjoint banks | **+8.10 ± 1.14 / +8.81 ± 1.25 / +7.38 ± 1.05**, all perm_p 0.0002 | APPLY | J:91 | Yes — replicated three times |
| 2026-08-31 00:28 | `r8_stack` increment vs `r6_button` | pargate mirror | **+29.92 ± 3.10** (30,000 decks), CI [23.7; 36.3], perm_p 0.0002, z = 11.85; 1,040 divergence decks (3.5 %), nz median 11.6 bb | APPLY | J:92 | Yes |
| 2026-08-31 00:28 | `r8_stack` vs **frozen base** | pargate mirror | **+30.60 ± 5.03**, CI [20.6; 40.3], perm_p 0.0002, trim +16.79 | APPLY | J:92 | Yes — **with a documented expectation violation**: pre-registered were +7…+9, measured 3–4× more; and **not additive** (+30.6 instead of ~+53) = self-play non-transitivity |
| 2026-08-31 00:28 | A/A before the r8 chain | pargate mirror | **EXACTLY 0** (600 decks) — GPU determinism proven | passed | J:92 | Yes |
| 2026-08-31 04:56 | Naming **`auslese-v5`** (= `r8_stack`, commit ec11fde) | pargate mirror, 3 runs | Increment vs `r6_button` **+29.92 ± 3.10 / +23.76 ± 3.07 / +29.23 ± 3.03** (banks 470k/530k/560k, all perm_p 0.0002), **pooled +27.6 ± 1.8**; vs base +30.60 ± 5.03; A/A exactly 0. Latency: river cold start **13.5 s**, flop 0.06 s | NAMED | J:93 | **Yes — `auslese-v5` is the champion to this day.** Honesty note in the entry itself: mirror evidence only, **no GTOW anchor** |
| 2026-08-31 09:51 | `river_play_guard` full profile | Replay over all 3,904 night-2 decisions | **32 interventions (0.8 %)**; v4 arm 25: call→fold 7 (**net +278.6 bb** accounted), fold→call 3, call→raise/allin 2, bet→check 5, bet→allin 3, size corrections 4, check→bet 1. AIVAT convergence: #2991749 (AIVAT −52.2), #2993037 (−33.1), #2992634 (−18.1) | Play is the transferable component | J:94 (`research/v8_replay_gegentest.py`) | Yes as a replay finding — then NEUTRAL in the mirror (J:97) |
| 2026-08-31 11:48 | VRAM measurement for the worker count | `nvidia-smi` | 3.7 / 12.3 GB with 6 workers → 12 workers in future | Measurement planning | J:95 | Yes (infrastructure) |
| 2026-08-31 13:56 | `r9_pre` (stackoff + no_limp) | pargate mirror | **−11.42 ± 2.97** (30,000) | **REJECT** | J:96 | Yes. Culprit diagnosis: the base **limps 78/400 hands** (~39 % of buttons) strategically → `no_limp_guard` rebuilt half the preflop game (37.8 % divergence decks). `stackoff_bremse` innocent (1 trigger/400) |
| 2026-09-01 08:18 | **v8 drop** | pargate mirror | `play` vs v5 **+1.14 ± 2.78** (30k) NEUTRAL; v8 vs v5 **+3.91 ± 2.85** / **−1.23 ± 4.36** (30k+15k), pooled ≈ +2.3 ± 2.4; A/A exactly 0 | **OPERATOR DECISION: v8 dropped** | J:97 (`../reports/V8_POSTMORTEM.md`) | Yes — v5 remains FINAL_STACK; causes: channel saturation (nz median 1.9 bb vs 11.6 bb), the mirror does not punish fine precision |

#### Phase 8 — Deep replay, consults, v10 (2026-09-01 to 2026-09-08)

| Date | What was measured | Instrument / channel | Result (number ± spread, n) | Verdict | Source | Still valid? |
|---|---|---|---|---|---|---|
| 2026-09-01 10:37 | Paper Leal, Nash polytope (Kuhn) | Literature, recomputed in the paper | Max-entropy member 25/25 weakly dominant; effect extensive-form-gated ×5.6; **Kuhn gap 0.0181** at game value −1/18 | Grounding of the seesaw doctrine | J:98 | Yes — explains the open TurnCFR-vs-TexasSolver frequency difference; magnitude honestly named as small |
| 2026-09-01 11:26 | **Deep replay** of all 571 river decisions from night 2, 3 configs | Solver-EV decomposition (`research/tiefen_replay.py`) | **Left on the table : mistakes = 1.6 : 1 (69.9 vs 43.0 bb)**. Largest single category v4 = **OVERFOLD 31.1 bb** (fold where the solver wants a bluff-raise). `VERLUST_CALL` (the week's construction site) is the **smallest** category in the EV measure: **4.1 bb**. Flip rates raw 25 % / 34 %, **EV-relevant only 4 % / 5 %**. Solver-EV error sum river: v4 **6.9 bb/100**, control **9.5** | Change of direction: harvest instead of defence | J:99 (`data/runs/tiefen_replay_20260901_112429.jsonl`) | **Yes, and one of the most valuable entries** — it shows that the pursued construction site was the smallest; hand 3003011 (−137 bb real) had only +0.6 bb EV diff = card realisation, not a decision |
| 2026-09-01 11:44 | E1 pre-gate for v9 (`r10_ernte`) | Trigger analysis on the replay list | 15-bb trigger opens up **15 new spots [13.7–40.3] bb**; total harvest expectation **[3.6–5.4] bb/100** on the GTOW axis; latency smoke 0.88 s/deck, 4/40 divergences | Pre-gate passed | J:100 (`HU_OPTIMAL_MAP.md`) | Expectation, not a result — the v9 chain was **aborted** |
| 2026-09-01 14:36 | v9 chain stopped | pargate | A/A `r10_ernte` **EXACTLY 0** (576 decks, fp16 determinism); champion run aborted at ~13/48 blocks, edges lost. Newly built: resumable pargate, identity test **9.87 == 9.87** | PAUSED | J:101 (commit eabcef3) | The A/A holds; a v9 result does **not** exist |
| 2026-09-07 15:41 | Consult gpt-6-astra, top-5 strategy | External consultation (5,178 reasoning tokens) | Code-verified adoption: hero's river range comes from the **tracker** (`improver.py:437`) instead of from the policy; `_injiziere` (`gpu_resolver.py:64`) → the solver solves the wrong game. SE arithmetic: SE 2 per arm = **12k–49k GTOW hands**. Contradiction documented: 20–40 % for −8 within 6 months too high (counter-estimate 10–20 %) | STOP recommendation for v9 | J:102 (`../consults/TOP5_CONSULT_GPT6_2026-09-07.md`) | Yes — triggered the v10 build |
| 2026-09-07 16:00 | Consult, learning architecture | External consultation (5,696 reasoning tokens) | **Exact counter-example** against "Q-net → policy via softmax": U=[[1,−2],[−1,1]], Nash 40/60, Q identical (−0.2), softmax 50/50 → **BR loss −0.5 instead of −0.2**. Consequence: zero solver regret ≠ low exploitability; the deep replay measures only axis A | Thesis refuted | J:103 | Yes — justifies why a BR test bench (K3) was needed |
| 2026-09-07 20:13 | v10 build, first attempt | Ultracode workflow | P3 fixer hung for 45 min in one run: the arm-A oracle solves **a separate GPU subgame per combo** (1326 × seeds × nodes individual solves) | Abort + lesson | J:105 | Yes — binding lesson: rebuild oracles over guard chains **batched** |
| 2026-09-07 21:59 | v10 integration | Tests + A/A + golden set | Golden set `r8_stack` vs base 40 decks **byte-identical** before/after hand_id injection (nonzero 16, +11,588). **Bug found:** `hand_id = 2*deck+half` made the private seeds of the mirror halves differ → A/A **−9.40 ± 10.92** (13 nonzero); after fix A/A 576 decks **EXACTLY 0**. Divergence r10 vs r8: 1/40 decks. Latency plan pot 7.8–8.3 s; oracle 0.205 s per combo solve | Bug fixed | J:106 | Yes — lesson: **a 40-deck A/A is not enough for K2** |
| 2026-09-08 01:47 | **v10 gate ladder G1–G5** | several (tests / A/A / latency / K1-TV / BR holdout / mirror) | **G1** green (13 blocks exit 0). **G2a** passed (A/A 576 exactly 0). **G2 NOT GREEN** (n=10: p99 v10 **7.55 s** > v5-H 5.54 s; plan played 1/10, deadline 7/10). **G3 MISSED**: K1-TV mean **0.2085** / p95 0.758 / max 0.876 against budget 0.02/0.05/0.10; lower bound 0.1446/0.620/0.819; **hero outside K1 support 21/64**. **G4 INCOMPLETE** (11/20 roots): dE_H **−113.0 ± 18.6 bb/100**, dR −4.04 ± 0.99, B less exploitable in 11/11. **G5 PASSED**: r10 vs r8 **+11.68 ± 10.85** (1,968 decks) NEUTRAL, CI [−9.39; +33.06]; all 3 decks ≤ −100 bb in the **fallback to the bare base**, offtree 42 % | **NOT GTOW-ready** | J:107 (`../reports/V10_GATES_REPORT.md`, `data/runs/v10/*`) | **Yes — ship decision stands: no tag, no GTOW run; state remains `auslese-v5`** |
| 2026-09-08 01:53 | G2 re-measurement after the live-mechanics fix | Live latency channel, 40 fresh states | Cause: 1 solve worker + 0.5 s queue budget blocked everything. After fix (3 workers, 3.0 s queue, 12 s deadline): **deadline 0/40** (previously 7/10), **plan played 25/40**, **offtree 11/40**, hand_not_in_range 4/40. Latency B p50 3.04 / p90 8.50 / **p99 10.15 s** vs A p50 2.10 / p99 8.20 s | Criterion still **MISSED** | J:108 (`data/runs/v10/G2_latenz_fix_live*`) | Yes |
| 2026-09-08 02:03 | v10 close of the session | Synthesis | ~4.4 M agent tokens, 3 workflows; A/A 3× exactly 0 (banks 1080000/1090000/1100000) | NOT GTOW-ready | J:109 | Yes |
| 2026-09-08 02:14 | Consult "is v10 complete?" | External consultation | NO. L1 = off-tree/support/sub-threshold → **bare base without v5 surgery**; L2 = hero outside K1 support **21/64**, required exactly 0, **no epsilon**. G3 budget 0.02 with S=12 **not testable** (~271 seeds needed). Scheduler: 0/40 deadlines → 95 % upper bound ≈ 7 % | Candidate, not a v5 replacement | J:110 | Yes — defines the v10.1 order |
| 2026-09-08 02:33 | Consult "is hybrid v5+v10 best anyway?" | External consultation | **Contradiction**: H is a new bot with its own seams, not max(v5, v10); nine cases in which H is worse than v5. **Correction to our own statistics**: "214 bb per-hand SD" is the SE coefficient c = 214 bb/100·√n (hand SD ≈ 2.14 bb after AIVAT) → 2,900 hands = SE 4; a ±4 band needs ~11,000 hands; −6 vs −8 with 80 % power ~71,000 | Hybrid doctrine, 7 rules | J:111 | **Yes — and this correction devalues every earlier reading of the hand SD** |

#### Phase 9 — 6-max, exploit gate, trainer, Kaggle (2026-09-09 / 09-10)

| Date | What was measured | Instrument / channel | Result (number ± spread, n) | Verdict | Source | Still valid? |
|---|---|---|---|---|---|---|
| 2026-09-09 19:26 | Prince takeover in 6-max pots | **pargate6** (paired 6-max arena, A/A tag vs tag 288 decks exactly 0), 2,992 decks each, incumbent `tag` | `hybrid` **−23.56 ± 9.02** CI [−40.8; −5.3]; `hybrid_r8` **−21.73 ± 9.01** CI [−39.0; −4.4]; `hybrid_r10` **−26.61 ± 8.93** CI [−43.9; −9.4]; `hybrid_r8` vs `hybrid` +1.82 ± 5.58 NEUTRAL | **REJECT ALL** | J:112 (`data/runs/verdrahtung/`) | **Yes** — the HU bot in 6-max is harmful; `six_server` takeover default OFF. Caveat: own ecology, external anchor = Analyzer 85.9 %/7.61 |
| 2026-09-09 19:26 | `POKERB_EXPLOIT=1` vs `=0`, 600 paired decks per league profile | **exploit_gate** (fresh processes, fingerprint verified) | Diff ON−OFF: nit −2.1 ± 9.5; tag **−19.3 ± 15.4**; lag −18.5 ± 13.0; station −17.4 ± 16.3; maniac −15.7 ± 9.6; rock −0.3 ± 9.0; whale −8.3 ± 17.0; shark −14.4 ± 13.7 → **all 8 point estimates ≤ 0, pooled ≈ −12 bb/100 (SE ~4.5)**. 6-max reads ON vs OFF: +3.6 ± 13.5 NEUTRAL | **Dirichlet river exploit REFUTED** | J:113 | **Yes** — exploit stays OFF in all modes; even loses against station/maniac/whale |
| 2026-09-09 20:13 | MTT mode in the trainer (product) | Tests + browser | Chip conservation 300,000 exact; every place exactly once; determinism per seed; side tables mean **121 ms** / max 216 ms per hero hand; 7 tests green | PRODUCT BUILD, not a bot verdict | J:114 (`../reports/TOURNAMENT_MODE.md`) | Yes |
| 2026-09-09 20:39 | Tournament bug "always 100 bb / always played well" | Reproduction + regression | Cause: a fresh table per hand had `hand_no` 1 → everything after hand 1 skipped. Re-measurement: 2 full tournaments (seeds 3/11: 6 and 31 hands), verdicts **38 GTO / 41 deviation**; browser speed run **3,671 renders** without error | PRODUCT FIX | J:115 | Yes |
| 2026-09-09 21:06 | Pre-fold in the trainer | Tests + browser | `tests/test_prefold.py` **22 cases** green | PRODUCT BUILD | J:116 | Yes |
| 2026-09-09 21:31 | Empty table ("Hand #undefined, Pot NaNbb") | Reproduction | Tournament bb 50 → slider grid 12.5 chips → amount 187.5 → pydantic 422 without `error` → client renders the error response as state. 3-layer fix + regression | PRODUCT FIX | J:117 | Yes |
| 2026-09-09 21:54 | `tag_flatfix` (never flat dominated offsuit broadways) vs `tag` | pargate6, 3 runs of 2,992 decks each | **+17.7 ± 6.4** (APPLY, perm_p 0.0035) / **+11.36 ± 6.88** (NEUTRAL, p 0.057) / **+19.18 ± 7.01** (APPLY, p 0.0035); pooled ≈ **+16 bb/100** | APPLY (3 runs) | J:118 (`data/runs/pargate6_tag_flatfix*_2026-09-09.log`) | **Yes — applied to `PROFILES["tag"]`**, tag `sixmax-tag-flatfix-v1`. Open: external Analyzer anchor |
| 2026-09-10 00:15 | Kaggle arena bridge built | Channel build + A/A | Kaggle v1 (via API): GPT-5.6 Sol **+34.9 ± 5.1**; Claude Fable 5.1 +29.7; GPT-5 mini −49.3. Bridge: 4/4 tests, **A/A exactly 0** after two fixes — previously **−37.5**, because the bot mixes from one RNG stream across hands | CHANNEL BUILT (no GTO anchor) | J:119 (`../reports/KAGGLE_ARENA.md`) | Yes |
| 2026-09-10 00:26 | GTOW leaderboard state, read in the browser | External reading (83 entries) | Top Bitcrumbs **−3.1** (52,005 hands, SD 0.9), Trainer −6.2, Roman_SL −7.4, tangtang −12.6, GPT-5.5 XHigh −9.2. **Own entries (org "Hampe"): Quantplay −30.4 (rank 31, 6,587 h), Quantplay v8 −31.6 (rank 33), Experimental Poker Bot −51.7 (rank 47)**. Rank by **lower bound** of the 95 % interval → top-5 threshold LCB ≈ **−14.8**. Calibration Kaggle→GTOW over 6 shared models: **r = 0.37, R² = 0.14** (residual SD 15.5); without Grok 4 r = 0.88 — **not robust** | FINDING | J:120 | Yes — **but the own leaderboard entries are all from the v8 era**; today's champion was never posted |
| 2026-09-10 01:06 | First reference value in the Kaggle channel | Kaggle mirror, 300 paired decks | `prince[final]` vs `prince[basis]`: bb/100 **+55.83, se 38.02**, trim +6.3, median 0.0, nonzero 97/300 (32.3 %), nz_pos 45 (sign-test z **−0.71**), CI95 [−16.67; +134.58], **perm_p 0.0757**; 3,152.9 s (~10.5 s/deck, 1 core) | **NEUTRAL (channel calibration)** | J:121 (`data/runs/kaggle_prince_vs_basis_2026-09-10.log`) | Yes — **explicitly not a bot verdict**; mean tail-carried; SE 4 would need ~27,000 decks |
| 2026-09-10 01:19 | Fact correction by gpt-5.6-sol, verified against the code | Code check | GTOW runs at **200 bb** (`gtowizard.py:98` starting_stack 20000, `:281` blinds [100,50]); our preflop blueprint only fires **from 140 bb effective** (`bot.py:200`) → the Kaggle channel (100 bb) measures **a different bot** (heuristic cascade instead of blueprint). Further: **−21.12 belongs to v4/r6_button, not v5**; the "8 bb/100" gap is the mean reading, against the LCB bound −14.8 it is **~6.3** | CORRECTION | J:122 (`../consults/CONSULT_GPT56_SOL_2026-09-10.md`) | **Yes — corrects two documentation errors**; "exactly our house size" was wrong |
| 2026-09-10 02:13 | AIVAT for the local Kaggle channel | Design analysis | Chance-node term pointwise unbiased; **action term dead** (bot is deterministic conditional on the deck → correction identically zero or biased); the 10× reduction from GTOW is **not transferable**, because the paired mirroring already cancels the card variance; per half the correction could increase the variance by a factor of **~1045**. Enumeration costs: river 1.3 / turn 18.5 / flop 285 ms / preflop ~31 s | **DRAFT, NOTHING BUILT** | J:123 (`../reports/AIVAT_KAGGLE.md`) | Yes |

---

### Grouping by type

| Type family | Entries | Lines | What they carry |
|---|---|---|---|
| **Oracle leads** (`L-VORSCHLAG` 9, `F-VORSCHLAG` 2, `SELFTEST-BEFUND` 5) | 16 | J:1–J:14, J:16, J:19 | Formula violations with severity in bb. Pure leads — every guard built from them later measured NEUTRAL |
| **Early gates** (`KANDIDAT-GATE` 3, `SANITY`, `DIAGNOSE-BEDARF`, `AKTEN`) | 6 | J:15, J:17, J:18, J:22, J:23, J:26 | First mirror gates; two negative findings (guard never fires / no effect) |
| **AUSLESE v1–v3** (`ANWENDEN` 2, `REPLIKATION`, `ANWENDEN+ROTATION`, `REPLIKATION-NICHT-BESTANDEN`, `ROTATION-ABGELEHNT`, `RUNDE4-*` 6, `REPLIKATION-HETEROGEN`, `ANWENDEN+NAME`) | 14 | J:20, J:21, J:24, J:25, J:27, J:28, J:34–J:41 | The first ascent; contains **two prevented mis-rotations** and the 3-σ replication break |
| **Transfer/adversary** (`TRANSFER-TEST` ×3, `EXPLOIT-JAGD`, `EXTERNE-BEWERTUNG`, `FABLE-DUELL`, `FABLE-RETEST`, `R6-DOKTRIN`) | 8 | J:29–J:33, J:71, J:74, J:75 | The second axis; the two-axes doctrine was born here |
| **Round 5 / v4** (`R5-*` 15, `R5B-*` 8, `R5C`, `TAUFE`, `VORREGISTRIERUNG`, `ESTIMATOR-V3`, `ARMEE-FIXES`, `V4-VS-BASIS-POOL`, `FINAL-STACK-VS-BASIS`) | 29 | J:42–J:70, J:76 | A/A null test, channel pre-survey, estimator revision, `turn_wert` replicated 3× |
| **GTOW live** (`GTOW-VORREGISTRIERUNG`, `GTOW-NACHT*` 8, `AIVAT-AUDIT-PLAN`) | 10 | J:77–J:88 | The only absolute anchors; contains the encoding bug + the recovery |
| **Rounds 7–9 / v5 / v8** (`R7-*` 2, `R8-*` 2, `R9-PRE`, `TAUFE-AUSLESE-V5`, `V8-*` 3, `TIEFEN-REPLAY-BEFUND`, `PAPER-*`) | 11 | J:89–J:100 | The GPU resolver, `auslese-v5`, the v8 drop and the deep replay |
| **v9/v10** (`V9-*` 2, `V10-*` 6) | 8 | J:100, J:101, J:104–J:109 | v9 aborted; v10 built and **failed at G3** |
| **Consults** (`KONSULT-GPT6-*` 4, `KONSULT-SOL-KORREKTUR`) | 5 | J:102, J:103, J:110, J:111, J:122 | External review; two of them **refute our own theses** exactly (Q-softmax, hybrid dominance) |
| **Wiring/6-max/exploit** (`VERDRAHTUNG-6MAX-VERDIKT`, `EXPLOIT-GATE-VERDIKT`, `FLATFIX-6MAX-VERDIKT`) | 3 | J:112, J:113, J:118 | Two refutations (takeover, exploit) and one applied 6-max fix |
| **Trainer product** (`TURNIER-MODUS-BUILD`, `TURNIER-MODUS-FIX` ×2, `TRAINER-VORAB-FOLD`) | 4 | J:114–J:117 | Product builds and fixes, explicitly **not bot verdicts** |
| **Kaggle/leaderboard** (`KAGGLE-ARENA-BRUECKE`, `GTOW-LEADERBOARD-STAND`, `KAGGLE-REFERENZWERT`, `AIVAT-KAGGLE-ENTWURF`) | 4 | J:119–J:121, J:123 | The new volume channel + the leaderboard state |

---

### What still holds today — the short balance from the journal

1. **Champion is `auslese-v5`** (commit ec11fde, `r8_stack`), established **only in the mirror**: +27.6 ± 1.8 vs `r6_button` (3 runs), +30.60 ± 5.03 vs frozen base (J:92, J:93). **No GTOW anchor.**
2. **The only GTOW-confirmed value of the project is −21.12 (n=979) for `v4_prince`** against a control of −31.34 (n=488), J:88 — sequential, unpaired, without SE in the entry, and according to J:122 **it belongs to v4, not v5**.
3. **Refuted and binding today:** the Dirichlet river exploit (all 8 profiles ≤ 0, pooled ≈ −12, J:113), the Prince takeover in 6-max (3× REJECT, J:112), `r6_ecall` (−4.15 ± 0.97, J:72), `no_limp` (−11.42 ± 2.97, J:96), v8 (pooled +2.3 ± 2.4 = NEUTRAL → dropped, J:97), v2/`sel_all` (pooled +0.69 ± 0.56, J:28), frequency guards from pot odds and MDF (J:15, J:17, J:18).
4. **v10 is not GTOW-ready** (G3 missed: K1-TV 0.2085 vs budget 0.02; hero outside support 21/64; G5 neutral at +11.68 ± 10.85), J:107.
5. **Superseded / to be devalued:** all numbers from rounds 1–4 (before the spot-RNG seeding fix, J:33/J:42/J:50); the NEUTRAL verdict for `turn_wert` in J:52 (trim estimator was channel-blind, J:54); the night-1 pool −41.11 as a "v4 verdict" (wrong arm: bare gym config without resolver/PRINCE, J:81); the documentation claim that Kaggle measures "exactly our house size" (wrong: 100 instead of 200 bb, J:122); the own leaderboard entries −30.4/−31.6/−51.7 (v8 era, J:120).

---

# Run store data/runs

`data/runs/` is the raw store of the local, in-process gates (`pokerbot.autogym.pargate`,
`pargate6`, `envgate`, `orakel_duell`, `exploit_jagd`, `exploit_gate` and the v10 gate scripts). Every
run creates a folder `YYYYMMDD_HHMMSS_<gate>_<candidate>/` with `config.json` (candidate, incumbent,
deck count, workers, deck bank `deck_seed0`, commit, host, timestamp) and — only on successful completion —
`result.json`. `INDEX.jsonl` is the complete short list of all completed runs (79 lines,
last 2026-09-09 21:53); `STAND.md` is an OLD partial view (frozen 2026-08-18 02:23, table
ends at `20260817_140247`) and covers not a single run from round 5 onwards.

**What this channel can measure:** exclusively a *relative, paired delta* between two
bot variants on **identical decks** in the project's own self-play ecology (HU mirror or 6-max league).
That is a non-regression / regression measure and the cheapest channel of the project ($0, in-process).
**What it cannot measure:** absolute playing strength, exploitability against adaptive or foreign opponents, and
transfer to GTOW. The evidence for that lies in this channel itself: `r6_ecall` loses in the mirror (−4.15) and
`r6_button` is neutral in the mirror (+0.71), although both were built as hardening guards against an adaptive
opponent. The absolute bb/100 value of individual arms (`bb100_kandidat`/`bb100_incumbent` in
pargate6) fluctuates extremely depending on the bank (tag: −49.59 / −20.89 / +16.48 / +50.54 on four deck banks) and
is worthless as a statement of level.

**Channel subtleties that put the numbers in context**
- Only a small share of decks diverges at all (`nonzero_anteil` e.g. 0.0160 for r7_river, 0.0347 for
  r8_stack, 0.3741 for r6_button vs basis). The channel is "quiet" and the edge distribution is fat-tailed →
  the 2-SE bands are rather optimistic; `perm_p`/bootstrap CI are the harder criteria.
- **Estimator break:** runs up to about 2026-08-17 midday write only `bb100`/`se`. From commit `73f42b6`
  `bb100_trim`/`median_bb100`/`nonzero`/`vorzeichen_z` are added, from `a1cee3c` additionally
  `ci95_lo/hi`/`perm_p`/`boot_b=4000`. Verdicts from the first group therefore rest on a different
  set of decision rules than the later ones — not comparable 1:1.
- **A/A duty:** runs with `kandidat == incumbent` are integrity tests and must yield EXACTLY 0.
  They are listed here too, because a broken A/A devalues every number of the same series (one case
  measured, see section 6).

---

## 1 — HU mirror (`kanal: pargate_mirror`) — the main chain

Paired decks, button swap, candidate against incumbent. Positive = candidate wins.

| Date | What was measured | Instrument / channel | Result (bb/100 ± SE, n decks) | Verdict | Source | Still valid? |
|---|---|---|---|---|---|---|
| 2026-08-16 20:42 | Structure smoke of the store | pargate (smoke) | no numbers | OK | `data/runs/20260816_204232_struktur_test/result.json` | yes (mechanics only) |
| 2026-08-16 20:47 | mdf_guard vs base | pargate_mirror | −17.09 ± 22.50 (n=1200) | NEUTRAL | `.../20260816_204741_pargate_mdf_guard/result.json` | no — n too small, replaced by the 99k run |
| 2026-08-16 20:49 | mdf_guard vs base | pargate_mirror | −3.26 ± 2.19 (n=99,000) | NEUTRAL | `.../20260816_204907_pargate_mdf_guard/result.json` | yes — MDF guard stays rejected |
| 2026-08-16 21:32 | sel_guard vs base | pargate_mirror | +13.81 ± 17.80 (n=1200) | NEUTRAL | `.../20260816_213258_pargate_sel_guard/result.json` | no — smoke, replaced by the 99k runs |
| 2026-08-16 21:33 | sel_guard vs base | pargate_mirror | +4.70 ± 2.06 (n=99,000) | APPLY | `.../20260816_213357_pargate_sel_guard/result.json` | yes — 1st of 2 replications (AUSLESE v1) |
| 2026-08-16 22:27 | auslese2 vs base | pargate_mirror | +18.01 ± 17.20 (n=600) | NEUTRAL | `.../20260816_222750_pargate_auslese2/result.json` | no — smoke |
| 2026-08-16 22:28 | sel_guard vs base, 2nd bank (seed0 20000) | pargate_mirror | +7.49 ± 2.08 (n=99,000) | APPLY | `.../20260816_222836_pargate_sel_guard/result.json` | yes — 2nd replication → AUSLESE v1 named |
| 2026-08-16 23:38 | sel_all vs base | pargate_mirror | +6.53 ± 22.22 (n=1200) | NEUTRAL | `.../20260816_233809_pargate_sel_all/result.json` | no — smoke |
| 2026-08-16 23:38 | lizenz_guard | pargate_mirror | 0.00 ± 0.00 (n=1200) | NEUTRAL | `.../20260816_233838_pargate_lizenz_guard/result.json` | yes — **null finding: wrapper without any effect** (later audit: "dead wrapper", `improver.py:172-174`) |
| 2026-08-16 23:40 | auslese2 vs base | pargate_mirror | +6.13 ± 2.03 (n=98,960) | APPLY | `.../20260816_234011_pargate_auslese2/result.json` | partly — auslese2 was later overtaken by sel_m15 |
| 2026-08-17 00:10 | lizenz_guard vs basis (explicit incumbent) | pargate_mirror | −0.06 ± 0.69 (n=1200) | NEUTRAL | `.../20260817_001012_pargate_lizenz_guard/result.json` | yes — confirms the null finding |
| 2026-08-17 00:10 | sel_all vs sel_guard | pargate_mirror | +3.00 ± 1.40 (n=30,000) | APPLY | `.../20260817_001033_pargate_sel_all/result.json` | **no — replication NOT passed** (see two rows below) |
| 2026-08-17 00:20 | auslese2 vs basis | pargate_mirror | −3.02 ± 16.68 (n=1200) | NEUTRAL | `.../20260817_002020_pargate_auslese2/result.json` | no — smoke |
| 2026-08-17 00:21 | sel_all vs sel_guard, 2nd bank | pargate_mirror | +0.44 ± 1.09 (n=30,000) | NEUTRAL | `.../20260817_002130_pargate_sel_all/result.json` | yes — **refutes the +3.00 run** (`STAND.md:32` "REPLIKATION-NICHT-BESTANDEN") |
| 2026-08-17 00:32 | sel_all vs sel_guard, 3rd bank | pargate_mirror | +0.18 ± 0.73 (n=90,000) | NEUTRAL | `.../20260817_003212_pargate_sel_all/result.json` | yes — **sel_all finally discarded** (`STAND.md:33` "ROTATION-ABGELEHNT") |
| 2026-08-17 13:43 | sel_m15 vs sel_guard | pargate_mirror | +1.11 ± 2.16 (n=30,000) | NEUTRAL | `.../20260817_134312_pargate_sel_m15/result.json` | yes — heterogeneous replication, weaker than the campaign value +10.50 |
| 2026-08-17 13:53 | sel_m20 vs sel_m15 | pargate_mirror | −1.52 ± 1.54 (n=30,000) | NEUTRAL | `.../20260817_135314_pargate_sel_m20/result.json` | yes — raising the margin from 15 to 20 brings nothing |
| 2026-08-17 14:02 | sel_m15 vs sel_guard | pargate_mirror | +2.63 ± 1.22 (n=90,000) | APPLY | `.../20260817_140247_pargate_sel_m15/result.json` | yes — basis of the naming AUSLESE v3 |
| 2026-08-17 22:29 | turn_wert vs basis, bank 1000 | pargate_mirror | +9.26 ± 4.88 (trim +6.17; n=29,920) | NEUTRAL | `.../20260817_222907_pargate_turn_wert/result.json` | yes — 1 of 3 banks; point estimate positive, not decisive alone |
| 2026-08-17 23:08 | turn_wert vs basis, bank 40000 | pargate_mirror | +16.75 ± 4.84, CI95 [+6.65,+26.08], perm_p 0.0005 (n=29,920) | APPLY | `.../20260817_230825_pargate_turn_wert/result.json` | yes |
| 2026-08-17 23:16 | turn_wert vs basis, bank 80000 | pargate_mirror | +22.42 ± 4.69, CI95 [+13.11,+31.58], perm_p 0.0002 (n=29,920) | APPLY | `.../20260817_231632_pargate_turn_wert/result.json` | yes — 3× replication, pooled in STAND as +16.14 ± 2.77 (`STAND.md:50`) |
| 2026-08-17 23:53 | r6_ecall vs turn_wert | pargate_mirror | −4.15 ± 0.97, CI95 [−6.12,−2.30], perm_p 1.0 (n=29,920) | **REJECT** | `.../20260817_235330_pargate_r6_ecall/result.json` | yes — negative result; interpretation: value folds in the self-play ecology |
| 2026-08-18 00:01 | r6_button vs turn_wert | pargate_mirror | +0.71 ± 2.18, perm_p 0.3962 (n=29,920) | NEUTRAL | `.../20260818_000120_pargate_r6_button/result.json` | yes — hardening is invisible in the mirror (two-axes doctrine) |
| 2026-08-18 01:32 | r6_button (whole chain) vs basis | pargate_mirror | +23.36 ± 5.32, CI95 [+12.75,+33.72], perm_p 0.0002 (n=29,920) | APPLY | `.../20260818_013257_pargate_r6_button/result.json` | yes — the "final stack vs basis" anchor cited in `STAND.md:59` |
| 2026-08-30 19:49 | r7_river vs r6_button, bank 320000 | pargate_mirror | +8.10 ± 1.14, CI95 [+5.90,+10.46], perm_p 0.0002 (n=30,000) | APPLY | `.../20260830_194936_pargate_r7_river/result.json` | yes |
| 2026-08-30 20:01 | r7_bill vs r6_button | pargate_mirror | 0.00 ± 0.00, **nonzero = 0** (n=30,000) | NEUTRAL | `.../20260830_200117_pargate_r7_bill/result.json` | yes — **null finding: the patch did not fire a single time in 30,000 decks** |
| 2026-08-30 20:12 | r7_wert vs r6_button | pargate_mirror | +8.81 ± 1.25, CI95 [+6.43,+11.39], perm_p 0.0002 (n=30,000) | APPLY | `.../20260830_201255_pargate_r7_wert/result.json` | yes |
| 2026-08-30 20:24 | r7_river vs r6_button, bank 410000 | pargate_mirror | +7.38 ± 1.05, CI95 [+5.40,+9.46], perm_p 0.0002 (n=30,000) | APPLY | `.../20260830_202416_pargate_r7_river/result.json` | yes — replication of +8.10 |
| 2026-08-30 20:42 | r8_stack vs r6_button, bank 470000 | pargate_mirror | +29.92 ± 3.10, CI95 [+23.71,+36.28], perm_p 0.0002 (n=30,000) | APPLY | `.../20260830_204212_pargate_r8_stack/result.json` | yes |
| 2026-08-30 22:50 | r8_stack vs basis | pargate_mirror | +30.60 ± 5.03, CI95 [+20.61,+40.29], perm_p 0.0002 (n=30,000) | APPLY | `.../20260830_225057_pargate_r8_stack/result.json` | yes — the overall anchor of the chain auslese-v5 |
| 2026-08-31 00:33 | r8_stack vs r6_button, bank 530000, commit `58c51de` | pargate_mirror | +23.76 ± 3.07, CI95 [+17.80,+29.61], perm_p 0.0002 (n=30,000) | APPLY | `.../20260831_003356_pargate_r8_stack/result.json` | yes |
| 2026-08-31 02:42 | r8_stack vs r6_button, bank 560000 | pargate_mirror | +29.23 ± 3.03, CI95 [+23.41,+35.19], perm_p 0.0002 (n=30,000) | APPLY | `.../20260831_024259_pargate_r8_stack/result.json` | yes — 3 banks: +29.92/+23.76/+29.23 |
| 2026-08-31 09:51 | r9_pre vs r8_stack | pargate_mirror | −11.42 ± 2.97, CI95 [−17.12,−5.68], perm_p 1.0 (n=30,000) | **REJECT** | `.../20260831_095123_pargate_r9_pre/result.json` | yes — preflop intervention hurts, negative result |
| 2026-08-31 20:13 | r9_play vs r8_stack | pargate_mirror | +1.14 ± 2.78, CI95 [−4.12,+6.32], perm_p 0.3472 (n=30,000) | NEUTRAL | `.../20260831_201350_pargate_r9_play/result.json` | yes — r9_play brings nothing |
| 2026-09-01 00:27 | r9_v8 vs r8_stack, bank 810000 | pargate_mirror | +3.91 ± 2.85, CI95 [−1.87,+9.50], perm_p 0.0805 (n=30,000) | NEUTRAL | `.../20260901_002705_pargate_r9_v8/result.json` | yes |
| 2026-09-01 04:46 | r9_v8 vs r8_stack, bank 840000 | pargate_mirror | −1.23 ± 4.36, CI95 [−9.92,+6.97], perm_p 0.6068 (n=14,976) | NEUTRAL | `.../20260901_044634_pargate_r9_v8/result.json` | yes — **replication flips the sign; r9_v8 remains unnamed** |
| 2026-09-01 14:21 | sel_m15 vs basis (mini smoke) | pargate_mirror | +9.87 ± 23.60 (n=112) | NEUTRAL | `.../20260901_142115_pargate_sel_m15/result.json` | no — n=112, CI [−43.46, +52.83] |
| 2026-09-01 14:21 | identical repetition (0.1 s runtime) | pargate_mirror | +9.87 ± 23.60 (n=112) | NEUTRAL | `.../20260901_142133_pargate_sel_m15/result.json` | no — pure cache/determinism proof, not an independent measurement |
| 2026-09-08 00:20 | r10_stack (v10) vs r8_stack (v5) | pargate_mirror | +11.68 ± 10.85, CI95 [−9.39,+33.06], perm_p 0.156 (n=1968) | NEUTRAL | `.../20260908_002035_pargate_r10_stack/result.json` | yes — v10 gate G5, **no proof of effect**, only non-regression |

## 2 — Deck banks / determinism (consumed `deck_seed0`)

The banks are to be used once per code state. Consumed according to `config.json`:
1000 · 5000 · 7000 · 9000 · 13000 · 16000 · 20000 · 25000 · 30000 · 40000 · 41000 · 45000 · 50000 ·
60000 · 65000 · 70000 · 80000 · 85000 · 90000 · 110000 · 120000 · 150000 · 300000 · 310000 · 320000 ·
350000 · 380000 · 410000 · 440000 · 445000 · 470000 · 500000 · 530000 · 560000 · 600000 · 630000 ·
660000 · 690000 · 720000 · 750000 · 780000 · 810000 · 840000 · 870000 · 960000 · 990000 · 1080000 ·
1090000 · 1100000 · 1110000 · 7770000.
Source: `config.json` per run folder. (CLAUDE.md names 1080000–1110000 as consumed for v10 — consistent.)

## 3 — 6-max league (`kanal: pargate6`)

Six seats, league `[tag, lag, nit, station, maniac]`, paired decks; measures the delta of a hero profile
against the same league. Absolute values (`bb100_kandidat`) are bank-dependent noise, only the delta counts.

| Date | What was measured | Instrument / channel | Result | Verdict | Source | Still valid? |
|---|---|---|---|---|---|---|
| 2026-09-09 18:10 | A/A tag vs tag (smoke) | pargate6 | 0.00 exactly, `aa_exakt_null=true` (n=24); tag absolute −49.59 | NEUTRAL | `.../20260909_181041_pargate6_tag/result.json` | yes — integrity proof |
| 2026-09-09 18:10 | hybrid_r8 vs tag (smoke) | pargate6 | +23.09 ± 44.02, CI95 [−49.01,+123.10] (n=24), 112 prince_decisions | NEUTRAL | `.../20260909_181050_pargate6_hybrid_r8/result.json` | no — n=24, mechanics smoke only |
| 2026-09-09 18:15 | A/A tag vs tag | pargate6 | 0.00 exactly (n=288); tag absolute −20.89 | NEUTRAL | `.../20260909_181514_pargate6_tag/result.json` | yes |
| 2026-09-09 18:15 | hybrid (Prince HU in 6-max) vs tag | pargate6 | −23.56 ± 9.02, CI95 [−40.84,−5.26], perm_p 0.9958 (n=2992); 11,417 prince_decisions | **REJECT** | `.../20260909_181534_pargate6_hybrid/result.json` | yes — HU Prince in 6-max loses clearly |
| 2026-09-09 18:18 | hybrid_r8 vs tag | pargate6 | −21.73 ± 9.01, CI95 [−38.98,−4.36], perm_p 0.9923 (n=2992) | **REJECT** | `.../20260909_181853_pargate6_hybrid_r8/result.json` | yes |
| 2026-09-09 18:36 | hybrid_r10 vs tag | pargate6 | −26.61 ± 8.93, CI95 [−43.87,−9.38], perm_p 0.9998 (n=2992) | **REJECT** | `.../20260909_183613_pargate6_hybrid_r10/result.json` | yes — v10 chain in 6-max is the worst |
| 2026-09-09 19:04 | hybrid_r8 vs hybrid (quiet channel) | pargate6 | +1.82 ± 5.58, CI95 [−9.01,+12.90], perm_p 0.3784 (n=2992) | NEUTRAL | `.../20260909_190405_pargate6_hybrid_r8/result.json` | yes — the HU surgery r8 does not rescue the hybrid |
| 2026-09-09 21:49 | tag_flatfix vs tag, seed 1 / bank 7000 | pargate6 | +17.70 ± 6.40, CI95 [+4.93,+29.92], perm_p 0.0035 (n=2992) | APPLY | `.../20260909_214905_pargate6_tag_flatfix/result.json` | yes — applied in commit `3e1dfce` |
| 2026-09-09 21:50 | tag_flatfix vs tag, seed 2 / bank 13000 | pargate6 | +11.36 ± 6.88, CI95 [−2.01,+25.16], perm_p 0.057 (n=2992) | NEUTRAL | `.../20260909_215055_pargate6_tag_flatfix/result.json` | yes — **the weakest of the three banks, CI includes 0** |
| 2026-09-09 21:52 | tag_flatfix vs tag, seed 3 / bank 16000 | pargate6 | +19.18 ± 7.01, CI95 [+5.59,+33.19], perm_p 0.0035 (n=2992) | APPLY | `.../20260909_215223_pargate6_tag_flatfix/result.json` | yes |

Note on bank dependence: the same incumbent `tag` measures +17.18 / +50.54 / +17.29 absolute on the
three banks (`bb100_incumbent` in the same files) — evidence that only the paired difference
is interpretable.

## 4 — Env arms (`kanal: envgate`) — CHANNEL numbers, not ship evidence

`envgate` compares environment arms (flag combinations) against a reference arm in the same gym. By
project doctrine these results are called `KANAL_*` and are **never** ship evidence — they pre-sort arms.
All arms n=11,968 decks unless noted otherwise.

| Date | Arm (env) | Reference wrapper | bb/100 ± SE (trim) | Verdict | Source |
|---|---|---|---|---|---|
| 2026-08-17 19:52 | k3_deception (TURN_DEFENSE 0.07 + SLOWPLAY 0.25) | — | +118.75 ± 76.58 (trim +2.05 ± 1.78), n=240 | NEUTRAL | `.../20260817_195218_envgate/result.json` |
| 2026-08-17 20:18 | **prince** (`POKERB_PRINCE=1`) | reference | −68.64 ± 11.90 (trim −18.04) | **REJECT** | `.../20260817_201814_envgate/result.json` |
| 2026-08-17 20:18 | k3_deception | reference | +8.72 ± 4.60 | NEUTRAL | ibid. |
| 2026-08-17 20:18 | turn_def_adv (`TURN_DEF_ADVISOR=1`) | reference | −3.37 ± 6.95 (trim −3.30) | NEUTRAL | ibid. |
| 2026-08-17 20:18 | raise_narrow 0.5 / 1.0 | reference | +5.64 ± 2.88 / +16.78 ± 4.10 | NEUTRAL / NEUTRAL | ibid. |
| 2026-08-17 20:56 | raise_narrow 0.5 / 1.0 (wrapper sel_m15) | sel_m15 | +6.49 ± 2.60 / +13.65 ± 3.70 | APPLY / APPLY | `.../20260817_205654_envgate/result.json` |
| 2026-08-17 20:56 | kombi_r5 (TD 0.07 + SP 0.25 + RN 1.0, wrapper turn_wert) | sel_m15 | +26.36 ± 6.04 (trim +2.78) | APPLY | ibid. |
| 2026-08-17 21:14 | turn_def_adv, 2nd bank | sel_m15 | −20.19 ± 6.72 (trim −6.11) | **REJECT** | `.../20260817_211423_envgate/result.json` |
| 2026-08-17 21:14 | kombi_r5, 2nd bank | sel_m15 | +25.22 ± 5.63 | APPLY | ibid. |
| 2026-08-17 21:14 | raise_narrow 0.5, 2nd bank | sel_m15 | +5.51 ± 3.09 | NEUTRAL | ibid. — **replication of +6.49 not passed** |
| 2026-08-17 21:34 | kombi_schlank (only RN 1.0 on turn_wert) | sel_m15 | +25.96 ± 5.39 | APPLY | `.../20260817_213451_envgate/result.json` |
| 2026-08-17 21:34 | kombi_r5, 3rd bank | sel_m15 | +36.15 ± 6.01 | APPLY | ibid. |
| 2026-08-17 21:44 | auslese_v3 | **basis** | +21.36 ± 6.03 (trim +13.23) | APPLY | `.../20260817_214458_envgate/result.json` |
| 2026-08-17 21:44 | kombi_r5 (= v4 core) | **basis** | +49.79 ± 7.99 (trim +33.82) | APPLY | ibid. — the "final vs basis: v3 +21.4 / v4 +49.8" cited in `STAND.md:51` |
| 2026-08-17 22:57 | kombi_r5 against a **foreign** opponent (GTOBaseline) | `kanal: envgate_vs_gtobaseline` | +95.48 ± 85.66, CI95 [−33.33,+284.90], perm_p 0.1882 (n=24) | **KANAL_NEUTRAL** | `.../20260817_225726_envgate/result.json` |

The transfer test against the foreign opponent (last row) has n=24 — worthless as a number, usable as a
proof of mechanics. The associated earlier transfer value exists only in the journal excerpt: sel_guard vs GTOBaseline
−3.80 (`STAND.md:37-38`) — i.e. the candidate that was positive in the mirror was negative against the foreign opponent.

## 5 — Further channels in the same store

### 5.1 exploit_jagd — 20 adaptive hunters against the frozen base
Measures how much a *learning* opponent extracts from the base. Positive `jaeger_bb100` = the base is
exploitable. Not the same as the mirror.

| Date | Result | Source | Still valid? |
|---|---|---|---|
| 2026-08-17 01:43 | Hunters +(−150.59) ± 116.96 over 4 hunters, 1/4 positive (400 hands) | `.../20260817_014358_exploit_jagd/result.json` | no — smoke, 400 hands |
| 2026-08-17 01:44 | Hunters **+7.73 ± 8.70**, 12/20 positive (100,000 hands); SD net +5.81, NSD +1.92 | `.../20260817_014431_exploit_jagd/result.json` | yes |
| 2026-08-17 02:02 | Hunters **+8.87 ± 6.90**, 14/20 positive (100,000 hands); SD net +19.85, NSD −10.99 | `.../20260817_020232_exploit_jagd/result.json` | yes — the value cited in `STAND.md:36` |

The hardening map comes from the same runs: the converged hunter models sit at
VPIP 0.75–0.76 / fold_to_bet 0.30 / aggression 0.33–0.34 (`.../20260817_020232_exploit_jagd/jaeger_einzeln.json`,
field `modell` per hunter). Fold harvest 2026-08-17 02:02: preflop 17,928 / flop 15,879 / turn 2,268 / river 2,880.

### 5.2 exploit_gate — does the exploit layer act in the right direction?
Compares exploit ON vs OFF per opponent profile; `kriterium` checks whether the sign matches the expectation.

| Date | Setup | Result | Verdict | Source |
|---|---|---|---|---|
| 2026-09-09 18:11 | HU, profiles station/tag, n=56 decks | station +52.10 ± 53.62 (`kriterium: VERLETZT`), tag +55.80 ± 53.58 (`korrekt`); `exploit_korrekt: false` | both NEUTRAL at n=56 | `.../20260909_181116_exploit_gate/result.json` |
| 2026-09-09 19:21 | 6-max, 8 profiles, n=592 decks each | ON−OFF: nit −2.09 ± 9.52 · tag −19.26 ± 15.35 · lag −18.50 ± 12.96 · station −17.35 ± 16.31 · maniac −15.74 ± 9.61 · rock −0.31 ± 8.97 · whale −8.26 ± 17.01 · shark −14.40 ± 13.67 · 6max_liga_reads +3.64 ± 13.45. **All NEUTRAL** (no CI without 0), `exploit_korrekt: false`, `verletzt: [nit, station, maniac, whale]` | Criterion NOT met | `.../20260909_192123_exploit_gate/result.json` |

**Negative result that holds today:** the exploit layer shows a *negative* point estimate in 6 of 8 profiles
and violates the sign expectation in 4 profiles — not a single arm is statistically
significant, but the direction does not support the exploit layer.

### 5.3 orakel_duell — decision quality, not bb/100
Counts rule violations per 1000 decisions of two bots on the same decks. Not a money measure.

| Date | Setup | Result | Source |
|---|---|---|---|
| 2026-08-17 21:32 | turn_wert vs sel_m15, n=1500 decks | turn_wert 8,493 decisions, sel_m15 8,568. Rate/1000: verpasster_wert_turn **3.06 vs 17.04**, verpasster_wert_river 14.72 vs 18.67, call_unter_pot_odds 20.13 vs 24.63, fold_ueber_pot_odds 10.60 vs 10.50, bet_braucht_unplausible_folds 7.54 vs 10.04. Severity sum call_unter_pot_odds 2,008.1 vs 2,456.7 bb | `.../20260817_213232_orakel_duell_turn_wert/result.json` |
| 2026-08-17 22:58 | the same as a 20-deck smoke | 89 vs 90 decisions; rates unusable (chunk effect) | `.../20260817_225803_orakel_duell_turn_wert/result.json` |

The 2026-08-17 audit records that the F tier (mdf_*) is practically dead in the duel because of the chunking
(`finalize_frequencies` runs per worker chunk but needs n≥30 per street) — the mdf rates of this
channel are therefore **not interpretable** (`praezisions_armee_2026-08-17.json`, `geprueft[1]`).

### 5.4 Campaign summary reports

**Round 4** (`.../20260817_120031_runde4_kampagne/bericht.json`, 6,095.1 s, 2026-08-17):

| Arm | vs basis | vs sel_guard (v1) | n decks | Verdict |
|---|---|---|---|---|
| sel_m06 | +0.30 ± 4.03 | +0.06 ± 1.45 | 24,960 | NEUTRAL |
| sel_m10 | +8.72 ± 3.74 | +5.64 ± 1.74 | 24,960 | APPLY |
| sel_m15 | +17.47 ± 3.81 | +10.50 ± 2.10 | 24,960 | APPLY |
| einmal_guard | — | +0.41 ± 1.05 | 24,960 | NEUTRAL (discarded) |
| **decisive** sel_m15 vs basis | **+8.68 ± 1.28** | — | **183,200** | APPLY |

The decisive run (+8.68 ± 1.28 at n=183,200) is the most robust single number of the whole store and
corrects the more optimistic 24,960 value (+17.47) clearly downwards.

6-max catalogue of the same campaign (30,000 hands, `bericht.json` → `sechsmax`): position bb/100
BB −28.9 · SB −29.6 · UTG +6.8 · HJ +15.8 · CO +2.4 · BTN +33.5. Facing catalogue: flop 21,165 nodes,
fold_freq 0.216, mean bet 0.431 pot · turn 11,565 / 0.297 / 0.384 · river 8,143 / 0.337 / 0.365.
Oracle over 298,010 decisions: HART 0, P 0, L 0, F 0.

**Round 5** (`.../20260817_195302_runde5_sweep/ergebnis.json`, 42.7 min): A/A null test sel_m15 vs sel_m15
n=1936 → 0.00 exactly, `max_abs_edge: 0`. Arms against sel_m15: sel_all_m15 0.00 ± 0.00 (n=29,920) NEUTRAL;
turn_wert +1.64 ± 4.03 NEUTRAL; wert_plus_all +1.64 ± 4.03 NEUTRAL (identical to turn_wert → the
additional arm had no effect).

**Round 5b** (`.../20260817_204025_runde5b_replikation/ergebnis.json`, 52.7 min): turn_wert vs sel_m15
r2 +9.39 ± 4.06 (n=29,920, APPLY), r3 +10.78 ± 4.00 (APPLY), **pooled +7.27 ± 2.33 at n=89,760,
sign-test z 14.93, nonzero 7,702** → APPLY. The weak round-5 value (+1.64) is contained in this pool;
the pooled +7.27 replaces it.

## 6 — A/A null tests (integrity)

| Date | Candidate = incumbent | n decks | Result | Source |
|---|---|---|---|---|
| 2026-08-30 19:45 | r6_button | 1200 | 0.00 exactly, nonzero 0 | `.../20260830_194513_pargate_r6_button/result.json` |
| 2026-08-30 19:49 | r7_river | 576 | 0.00 exactly | `.../20260830_194908_pargate_r7_river/result.json` |
| 2026-08-30 20:36 | r8_stack | 600 | 0.00 exactly | `.../20260830_203659_pargate_r8_stack/result.json` |
| 2026-08-31 00:28 | r8_stack | 600 | 0.00 exactly | `.../20260831_002812_pargate_r8_stack/result.json` |
| 2026-08-31 09:23 | r9_play | 600 | 0.00 exactly | `.../20260831_092324_pargate_r9_play/result.json` |
| 2026-08-31 09:43 | r9_pre | 600 | 0.00 exactly | `.../20260831_094336_pargate_r9_pre/result.json` |
| 2026-08-31 13:56 | r9_play | 576 | 0.00 exactly | `.../20260831_135616_pargate_r9_play/result.json` |
| 2026-09-01 00:25 | r9_v8 | 576 | 0.00 exactly | `.../20260901_002535_pargate_r9_v8/result.json` |
| 2026-09-01 11:45 | r10_ernte | 576 | 0.00 exactly | `.../20260901_114509_pargate_r10_ernte/result.json` |
| **2026-09-07 21:32** | **r10_stack** | **576** | **−9.40 ± 10.92, nonzero 13, CI95 [−33.49,+8.15] → A/A NOT ZERO** | `.../20260907_213225_pargate_r10_stack/result.json` |
| 2026-09-07 21:41 | r10_stack, **same bank 1080000** | 576 | 0.00 exactly, nonzero 0 | `.../20260907_214142_pargate_r10_stack/result.json` |
| 2026-09-07 22:03 | r10_stack, bank 1090000 | 576 | 0.00 exactly | `.../20260907_220348_pargate_r10_stack/result.json` |
| 2026-09-08 01:52 | r10_stack, bank 1100000 | 576 | 0.00 exactly | `.../20260908_015248_pargate_r10_stack/result.json` |

The broken A/A of 2026-09-07 21:32 is the most important negative result of this store: 13 of 576
decks diverged although the same bot played against itself. The follow-up run on **the same bank**
is exactly 0 → the defect was fixed (CLAUDE.md/`v10-river-fundament`: bug "hand_id per half").
Consequence for the reader: **every v10 number produced before 2026-09-07 21:41 is suspect.**
Evidence of repeatability: `data/runs/v10/aa_r10_g2a_pargate.log` and
`data/runs/v10/aa_r10_livefix_pargate.log` (interim state consistently +0.00 bb/100, EXIT=0).

## 7 — v10 gates (`data/runs/v10/`)

Separate subfolder with the gate artefacts of version v10 ("river foundation"). These gates do
NOT measure bb/100 against an opponent, but model fidelity, latency and exact best response.

| Date | What was measured | Instrument / channel | Result | Verdict | Source | Still valid? |
|---|---|---|---|---|---|---|
| 2026-09-07 22:09 | G2a — A/A + golden set after the K1 change | Golden set + pargate | Golden A/A 40 decks nonzero 0, sum 0.0; smoke r10 vs r8 40 decks: 1 divergence, sum −21,580 chips; pargate A/A 576 decks exactly 0 | **PASSED** | `data/runs/v10/G2a_zusammenfassung.json` | yes |
| 2026-09-07 23:14 | G3 — fidelity of the K1 hero range against the oracle | Gym engine, 64 histories / 145 nodes | **TV K1 vs oracle: mean 0.2085 · p95 0.7579 · max 0.8758** against budget mean 0.02 / p95 0.05 / max 0.10. Oracle floor: mean 0.0950. Corrected lower bound: mean 0.1446. Hero outside K1 support: **21** of 64. K1 status ok 60 / partial 4 | **`urteil_roh: verfehlt`**, `urteil_budget: orakel_zu_grob` | `data/runs/v10/g3_k1_gate_20260907_231422.json` | yes — the hard reason why v10 is not GTOW-ready |
| 2026-09-08 00:07 | G4 — exploitability of the plan, exact BR on holdout roots | Test bench, arm A = oracle in the **gym** channel | 11 of 224 roots (time budget exhausted, 5,867.5 s). ΔE_H = **−113.037 ± 18.561 bb/100** (bootstrap UB95 −85.358); ΔR as B disadvantage **−4.038 ± 0.988 bb/100** (UB95 −2.614). 0 UNSUPPORTED, 0 GPU solve errors. Controls 15/15 green | **INCOMPLETE** (n=11 < n_min_voll 20); criterion met in the primary reading, missed in the literal test-bench reading | `data/runs/v10/G4_holdout.md`, `data/runs/v10/G4_holdout.json` | restricted — gym arm, n=11, full holdout projected at 33.2 h |
| 2026-09-08 01:52 | G2 — latency of both arms in the live channel | Live channel, 32 hands / 40 decisions | v10 plan p99 **10.152 s** vs v5-H **8.198 s**; max v10 10.152 s; no call ≥30 s. Cold start v10 2.99 s, v5-H 3.13 s | **MISSED_REDUCED_SAMPLE** (`plan_p99_unter_8s: false`, `gesamt_p99_v10_le_v5H: false`) | `data/runs/v10/G2_latenz.md` | yes |
| 2026-09-08 01:41 | G5 — mirror r10 vs r8 + catastrophe post-mortem | pargate_mirror + replay | +11.68 ± 10.85 (n=1968), CI95 [−9.39,+33.06], perm_p 0.156; 2 catastrophe decks (+160.79 bb / −153.20 bb); replay 23/23 decks reproduced exactly. Classes: mit_fallback n=14 sum +202.27 bb (6 negative), nur_plan n=3 sum +219.16 bb (0 negative), kein_plan_pot n=6 sum −242.99 bb (5 negative). K2 status in 23 decks: offtree 20 / none 27 / hand_not_in_range 1 | **PASSED (mirror criterion) with FINDING** | `data/runs/v10/G5_BERICHT.json`, `.../20260908_002035_pargate_r10_stack/g5_divergenz_auswertung.json` | yes — **all three decks ≤ −100 bb arise in the off-tree fallback to the bare base, never from a plan sample** |
| 2026-09-08 (export) | Analyzer export r10_stack | PokerStars HH export | 200/200 hands, 4,621 CRLF / 0 LF-only, 138,730 bytes, 75 stack interventions. **Reduced from 1500 to 200** (10.6–11.6 s/hand → 88 min projection, abort of the 500 run at 98/500 after 17 min) | no EV-loss comparison possible (SE ~2.7× wider) | `data/runs/v10/G5_BERICHT.json` → `analyzer_export` | yes — the Analyzer grade for this export is NOT in `data/runs` |
| 2026-09-07 16:47 | K5 coin (order of the GTOW nights) | Pre-registration | `BAAB_dann_ABBA` | — | `data/runs/v10/../v10_muenze.json` | yes — binding pre-registration, GTOW nights never run |

In addition: `data/runs/tiefen_replay_20260901_112429.jsonl` (571 lines) is a decision ledger on
live-logged hands with three arms (`A_tief`, `B_prod`, `C_preflopR`), each line with `ev_diff_bb`,
`p_gespielt`, `expl` and `aivat_bb`. An aggregated evaluation of it is **not** in `data/runs`.

## 8 — Kaggle arena (`kanal: kaggle_arena`, new on 2026-09-10)

| Date | What was measured | Instrument / channel | Result | Verdict | Source | Still valid? |
|---|---|---|---|---|---|---|
| 2026-09-10 00:12 | A/A prince[final] vs prince[final] | kaggle_arena | **−37.50 ± 94.49 (n=8 decks), nonzero 4/8** → the log itself writes: "A/A NICHT null: −37.5 bb/100 → STOPP (Mess-Doktrin)" | **A/A BROKEN** | `data/runs/kaggle_aa_2026-09-10.log` (last 2 lines) | yes — the channel is NOT validated |
| 2026-09-10 01:06 | prince[final] vs prince[basis] | kaggle_arena | +55.83 ± 38.02 (trim +6.30), CI95 [−16.67,+134.58], perm_p 0.0757, nonzero 97/300, sign-test z −0.71, nz_median −200 chips (n=300, 3,152.9 s) | NEUTRAL | `data/runs/kaggle_prince_vs_basis_2026-09-10.log` (closing line) | **no as proof of effect** — ran 54 min AFTER the broken A/A; without a validated channel the number is not robust |
| 2026-09-10 ~02:14 | v9 vs champion | kaggle_arena | Interim states 50…500 of 600 decks all **+0.0 bb/100** (11–12 s/deck), no closing line in the file | running / incomplete; +0.0 = identical policy | `data/runs/kaggle_v9_vs_champion_2026-09-10.log` | open |
| 2026-09-10 ~01:59 | v10-H0 vs champion | kaggle_arena | **not a single result line** — the file contains only the two OpenSpiel error messages ("Unknown game 'universal_poker'" / "'repeated_poker'") | no result | `data/runs/kaggle_v10h0_vs_champion_2026-09-10.log` | no |

All four Kaggle logs begin with the same two OpenSpiel errors (`universal_poker` and
`repeated_poker` do not exist in the installed OpenSpiel version) — the error is apparently
not fatal (the runs start afterwards), but it shows that the planned OpenSpiel environment does not take effect.

## 9 — Aborted runs (only `config.json`, no `result.json`)

91 run folders, 79 with a result (= the 79 lines in `INDEX.jsonl`), **12 aborted**. What remains
is only the `config.json` with candidate/incumbent/deck count/bank/commit — no numbers, no
`edges.json`.

| Folder | What was planned | Commit | Whereabouts |
|---|---|---|---|
| 20260816_221126_pargate_sel_guard | sel_guard, 99,000 decks, bank 20000 | `ff71726` | restarted at 22:28 with **the same bank 20000** → +7.49 ± 2.08 |
| 20260816_221825_pargate_lizenz_guard | lizenz_guard, 600 decks, bank 30000 | `72546b7` | repeated at 23:38 as a 1200-deck run → 0.00 |
| 20260816_222721_pargate_sel_all | sel_all, 600 decks, bank 40000 | `95d0ce9` | repeated at 23:38 as a 1200-deck run → +6.53 |
| 20260817_215814_v4wrapper_vs_basis | v4 wrapper vs basis, 30,000 decks, banks [1000, 40000, 80000] | `7616cf1` | replaced by the three individual runs `pargate_turn_wert` on exactly these banks |
| 20260817_223759_pargate_turn_wert | turn_wert vs basis, 30,000, bank 40000 | `28377da` | repeated at 23:08 with commit `a1cee3c` → +16.75 |
| 20260817_224507_envgate | 24-deck smoke | `28377da` | repeated at 22:57 with `3eb88fd` |
| 20260831_093318_pargate_r9_play | r9_play vs r8_stack, 30,000, bank 630000 | `3a4dfe0` | bank 630000 never evaluated |
| 20260831_140141_pargate_r9_play | ditto, bank 750000 | `ffe3150` | progress in the driver log `v8_kette_20260831_135616.log` up to 5000/30000 decks (ETA 310 min) |
| 20260831_154604_pargate_r9_v8 | A/A r9_v8, 600 decks, bank 780000 | `ffe3150` | repeated on 2026-09-01 00:25 → exactly 0 |
| 20260831_170049_pargate_r9_play | ditto, bank 750000 | `cf1944c` | log `v8_kette_rest_20260831_170049.log` up to 18,125/30,000 decks; only the start at 20:13 delivered +1.14 |
| 20260901_065628_pargate_r9_v8 | r9_v8 vs r8_stack, 15,000, bank 870000 | `cf1944c` | third replication of r9_v8 never finished — the arm stayed at 2 contradictory runs (+3.91 / −1.23) |
| 20260901_115900_pargate_r10_ernte | r10_ernte vs r8_stack, 30,000, bank 990000 | `2d8c8d6` | log `v9_kette_20260901_114509.log` up to 7500/30,000 decks (126 min, ETA 378 min) → **r10_ernte never received a verdict** |

Recurring pattern: the 30,000-deck runs of rounds 8–10 take 4–4.5 h (115–125 decks/min) and
are regularly aborted before the end. Two arms (`r9_v8`, `r10_ernte`) therefore have to this day
no completed replication series.

## 10 — Files in `data/runs` that are NOT measurements

Important for context, because they contain numbers that are not runs:

- `gtow_v8_protokoll_2026-08-31.json` — **pre-registered protocol, not a run** ("KEIN Lauf gestartet",
  field `meta.zweck`). Contains the SE planning (per-hand SD 214 → SE 12.4 at n=300; 4.3 at n=2500), the
  abort rules and the cited live anchor **−30.11 ± 5.51 (n=2899, key #3, v2.2)**. This anchor
  does NOT come from `data/runs`, it is only referenced.
- `praezisions_armee_2026-08-17.json` (10 checked + 59 open entries), `root_sweep_2026-08-17.json`
  (12 checked / 41 unchecked), `niveau_audit_2026-08-17.json` (ranking of 15, 44 gaps),
  `orakel_ausbau_design.json`, `verdrahtungs_debug_2026-08-17.json` — agent-army reports:
  code audits, bug finds and design proposals. They contain *constructed* worked examples
  (e.g. the W1-3 FE error: true 0.318 vs computed 0.167), not measurements.
- `data/runs/fable_duell/aktionen.json` — pure action list (`[["raise",200],…]`) of the LLM adversary,
  without a bb balance. The "62 hands vs v4 = +115 bb" cited in the project is NOT in this file.
- `data/runs/verdrahtung/` — driver logs of the 6-max wiring chain of 2026-09-09 plus the
  marker file `KETTE_FERTIG`; the numbers in them are identical to the run folders of section 3.
- `data/runs/v10/policy_oracle_cache/` and `_alt_policy_oracle_cache_v1/` — oracle caches, not
  results.

## 11 — What is outdated in this store

1. **`STAND.md` is dead.** Timestamp 2026-08-18 02:23; the run table (`STAND.md:7-28`) ends at
   `20260817_140247` and does not cover 63 of the 91 run folders. Replaced by `INDEX.jsonl`
   (79 lines, 2026-09-09).
2. **The journal excerpt in `STAND.md:32-46` is a "last 15" snapshot** of 2026-08-17 14:31 —
   not the journal (`data/autogym/journal.jsonl`).
3. **Small-n smokes** (n ≤ 1200) have in almost all cases been replaced by large runs: mdf_guard
   −17.09 → −3.26; sel_guard +13.81 → +4.70/+7.49; auslese2 +18.01 → +6.13; sel_m15 +9.87 (n=112) →
   +8.68 (n=183,200). **Every one of these smokes was off by 2–4×.**
4. **`sel_all` and `raise_narrow 0.5`** are examples of "first run positive, replication neutral"
   (+3.00 → +0.44 → +0.18 and +6.49 → +5.51 NEUTRAL respectively). Without the third bank both would have
   received an APPLY.
5. **Estimator change:** verdicts before `a1cee3c` have no `perm_p` and no bootstrap CI. The run
   `20260817_222907` (+9.26 NEUTRAL, old estimator) and `20260817_230825` (+16.75 APPLY, new
   estimator) are therefore not only different banks but also different decision rules.
6. **The Kaggle channel is unvalidated** (A/A = −37.5 at n=8) — everything from `kaggle_*_2026-09-10.log`
   is provisional until a clean A/A.

---

# GTO Wizard measurements (the expensive axis)

GTO Wizard AI (`researcher.gtowizard.com`) is a HU NLHE bot at **200 bb** effective, blinds [100,50] chips,
bb = 100 chips, cash reset per hand (`gtowizard.py:98` starting_stack 20000, `:281` blinds [100,50]; documented in
`data/autogym/journal.jsonl:122` type KONSULT-SOL-KORREKTUR). What is measured is **AIVAT** (chance + action
correction, computed server-side, roughly 10× variance reduction). The channel measures exactly one thing: **how many bb/100
our bot loses against a real re-solver** — absolute, external, not self-referential. It is the only
absolute anchor of the project.

**What the channel CANNOT do:** (1) **No deck control** — the API allows no seeding; paired/duplicate
dealing is impossible (`../reports/GTOW_DOSSIER.md:12-13`); every A/B is unpaired and needs n. (2) **Expensive in
wall time** — 1.3–35 s/hand depending on configuration; 2,500 hands ≈ 8–9 h. (3) **No causal decomposition** — AIVAT cells are
realisation attribution, not decision attribution (`HU_OPTIMAL_MAP.md:35-38`, binding lesson). (4) **The
spread is brutal**: per-hand AIVAT SD ≈ 214–302 bb/100 units → **+3 bb/100 at 2σ needs ≈ 22,000 hands,
+10 needs ≈ 2,000** (`../reports/GTOW_DOSSIER.md:101`). (5) **Account aggregates mix code eras** — only dedicated
keys per campaign are readable (`../reports/GTOW_DOSSIER.md:15-16`).

**Sub-channels, to be kept strictly apart:**
- **A. Live AIVAT** (API, expensive, absolute) — the core of this document.
- **B. GTOW Analyzer** (hand-history upload, per-decision EV loss, $0, deterministic, no variance) —
  measures deviation from GTO per move, **not** realised money against an opponent.
- **C. GTOW as a data source** (census/frequency mining from our own hand histories) — measures **GTOW's** behaviour,
  not ours.
- **D. Leaderboard** — external comparison, rank by 95 % lower bound.

**Configuration legend** (without it no GTOW number is readable): bot/stack · resolver (TexasSolver river/turn)
on/off · exploit on/off · stack depth (always 200 bb) · key/account. Every row below carries it.

---

## A. Live AIVAT against the GTOW API

All means/SEs in tables A2–A5 I have **recomputed from the raw hand histories**
(`data/sessions/gtow_hands_<ts>.jsonl`, field `aivat` per hand, bb=100 ⇒ bb/100 = mean of the `aivat` values);
they reproduce the documented numbers exactly. Where no HH file exists, the documentation source is given.

### A1. The legacy era (before 2026-06-19) — ALL BUG-INFLATED OR UNUSABLE

| Date | What was measured | Configuration | Instrument / channel | Result (n) | Verdict | Source | Still valid? |
|---|---|---|---|---|---|---|---|
| up to 2026-06-19 | Account aggregate of all code eras | mixed (old engine, jam-spew era) | GTOW `/results` (server-side, correct) | **−47.18 ± 1.48 bb/100, n=20,859** | historical, **OUTDATED as a bot statement** | `docs/STATE.md:1170` | **NO** — aggregate over dead code states; wrongly cited as "the engine is −47" until 2026-07-04 (`docs/STATE.md:1019`) |
| 2026-06-18 | Solver-search agent (brain drives TexasSolver) | `--agent-type solver`, fixed non-line ranges | Live AIVAT, computed locally | −74.9 bb/100, n=100 | bad; **locally 2× inflated** | `docs/STATE.md:1176` | **NO** — bb=50 bug (see E1) ⇒ real ≈ −37 |
| 2026-06-15/16 | "integrated bot", resolver ON vs OFF | Engine, exploit-primary | Live AIVAT, local | Floor (resolver OFF) **−70.73 ± 5.83** ≈ resolver+v1 **−72.06 ± 6.70**, n≈2500 | Resolver **NEUTRAL** (not a spew cause) — the *ratio* still holds | `docs/STATE.md:1640-1642` | **Level NO** (bb=50 bug ⇒ real ≈ −35); **verdict "resolver neutral" YES** |
| 2026-06-19 | `POKERB_EXPLOIT` toggle to reconstruct the −47 | Engine, exploit ON vs OFF | Live AIVAT, local | OFF −93 ± 23.5 (n=146) ≈ ON −74.7 ± 5.9 (<1σ) | Reconstruction **FAILED** | `docs/STATE.md:1170` | **NO** — bb=50 bug ⇒ real ≈ −46.5 / −37; the "regression" inferred from it was an ARTEFACT (`docs/STATE.md:1174`) |
| 2026-06-16 | 9 smokes "grafted preflop" | various engine variants | Live AIVAT, n=20 each | −19.99 · −34.61 · −36.44 · −46.75 · −111.61 · −125.77 · −295.86 · −527.80 · −599.74 | **WORTHLESS** (n=20, SE up to ±548) | `data/gtow_grafted.log:119-509` | **NO** — textbook example of "small samples lie" |
| 2026-06-19/20 | unlabelled engine run | Arm NOT noted in the log | Live AIVAT | **−276.20 ± 146.96**, n=100 (RAW +5.49) | **no verdict** — SE ±147 | `data/_gtow_engine_run.log:234-236`; HH `gtow_hands_1781903796.jsonl` (recomputed n=100, −276.20) | **NO** — missing arm label = channel-hygiene lesson |

### A2. Brain era (LLM drives the engine, 2026-06-19 to 06-29) — key #2

Channel note: the brain path bypasses `bot.py` (it calls `api.legalize` directly) — these numbers say **nothing** about
today's engine. All values recomputed from the campaign logs + HH.

| Date | What was measured | Configuration | Result (n) | Verdict | Source | Still valid? |
|---|---|---|---|---|---|---|
| 2026-06-19 | Claude Opus brain + engine | `--agent-type claude`, resolver ON, 200 bb | **−28.55 ± 7.25**, RAW −47.42, n=500, ~$8.32 | best HU result of the era; **later exposed as a lucky draw** | `docs/STATE.md:1173` | historical |
| 2026-06-19 | GLM-Z1-9B (GRPO ckpt-400) + engine | vLLM on pod, frac_bad 0.009 | **−43.30 ± 7.15**, RAW −61.09, n=100 | ≈ engine level; first own RL bot on the benchmark | `docs/STATE.md:1156`; HH `gtow_hands_1781903258.jsonl` (recomputed n=100, −43.30 ± 7.19) | historical |
| 2026-06-20 | Preflop switch (GLM → blueprint) | GLM + blueprint routing preflop | **−99.39 ± 48.03**, n=100 | **REFUTED + reverted** — less overfold ⇒ more postflop ⇒ spew becomes visible | `docs/STATE.md:1160`; HH `gtow_hands_1781910244.jsonl` (recomputed −99.39) | historical, lesson holds |
| 2026-06-20 | **Made-hand wiring A/B** | same model/pod, ON vs OFF, n=500 each | **ON −43.46 ± 9.49 · OFF −84.11 ± 16.91 (Δ ≈ +40.7)** | **APPLY** — largest serve-time lever of the brain era | `data/gtow_ab_run.log:26,38` | historical (brain path) |
| 2026-06-21 | **to_call fix A/B** (preflop adapter bug) | made-hand ON on both sides, n=500 each | **ON (fix) −28.36 ± 10.11 · OFF (bug) −40.40 ± 12.83 (Δ +12 ≈ 0.7σ)** | **SUGGESTIVE, not significant**; the bug itself is a proven correctness error | `data/gtow_tocall_ab.log:26,38` | fix holds; Δ never replicated |
| 2026-06-21 | Solver-freq hint A/B | made-hand+to_call ON, n=500 each | ON −49.21 ± 29.00 · OFF −49.52 ± 11.71 | **NEUTRAL — hint discarded** | `data/gtow_hints_ab.log:26,38` | lesson holds: perception fixes help, strategy nudges do not |
| 2026-06-21 | Re-SFT → new GRPO | freshly trained, n=500 | **−90.18 ± 23.63** | **REGRESSION — campaign discarded** | `data/gtow_newgrpo.log:26` | lesson holds (RL on the league ≠ GTOW) |
| 2026-06-21 | the same re-SFT without RL | SFT warm start, n=500 | −71.64 ± 16.13 | worse than baseline | `data/gtow_newsft.log:26` | historical |
| 2026-06-21 | Product config (grpo_slim + both fixes) | n=500 | **−82.25 ± 23.91**, RAW +53.93 | **Fat-tail draw**, 5 %-trimmed −19.3 | `data/gtow_confirm_500.txt:26`; `docs/STATE.md:1111` | historical |
| 2026-06-21 | the same config, n=1500 (pinned) | n=1500 | **−68.20 ± 16.82** (trimmed −39.8) | **Raw mean at n≤1500 is tail-dominated = UNRELIABLE** | `data/gtow_baseline_1500.log:36`; `docs/STATE.md:1121` | lesson holds |
| 2026-06-21 | Merging the 3 measurements of the same model | −28.36 / −49.52 / −68.20 | **true level ≈ −37 to −40**, "−28.36" was a lucky draw | **CORRECTION of a headline** | `docs/STATE.md:1119,1121` | lesson holds (binding) |
| 2026-06-22 | Claude brain run | `CLAUDE-BRAIN`, 784 decisions, 100 % Claude, ~$6.27 | **−52.55 ± 21.82**, RAW −94.87, n=300 | arm label missing in the log | `data/claude_gtow.txt:122-126` | historical; evidence of missing fingerprint discipline |
| 2026-06-29 | Claude+engine live | `--agent-type claude`, key #2 | **−41.00 ± 14.06**, n=200, $4.14 | confirms Claude level ≈ −35…−45 with a fat tail | `docs/STATE.md:1090`; HH `gtow_hands_1782700679.jsonl` (recomputed n=200, −41.00) | historical |
| 2026-06-29 | **ONTREE snap A/B** (brain bet sizes onto GTOW's tree) | n=300 each, contemporaneous OFF→ON | **ON −39.92 ± 19.36 · OFF −55.92 ± 28.19 (Δ +16, SE_Δ ≈ 34)** | **INCONCLUSIVE** → default OFF | `docs/STATE.md:1091`; HH `gtow_hands_1782736451.jsonl` / `..._1782730702.jsonl` (recomputed) | mechanics (15 %→100 % on-tree) hold; EV benefit unproven |
| 2026-06-29 | unassigned 300 run | arm unknown | −30.86 ± 7.79, n=300 | **not attributable** | HH `gtow_hands_1782722688.jsonl` (recomputed) | **NO** — without an arm no statement |
| 2026-06-21 | Claude Code's own decisions, graded | 264 own GTOW decisions | 252/262 in GTO support (96.2 %); 90 % of the −38.41 loss on river endings | Loss = **variance/coolers**, one real leak: postflop over-checking | `docs/STATE.md:1137,1139`; HH `gtow_hands_1782053161.jsonl` era, run `data/gtow_claudecode.log:32` (−38.41 ± 22.48, n=100) | method holds (deterministic grading beats n=100 AIVAT) |

### A3. Engine era PRINCE (2026-07) — the most important anchors

| Date | What was measured | Configuration | Result (n) | Verdict | Source | Still valid? |
|---|---|---|---|---|---|---|
| 2026-07-04 | **HEAD default engine** (the "−47 is dead" run) | all GTO_MODE flags OFF, exploit-primary, **resolver ON**, key #2 | **−20.09 ± 7.18** (recomputed −20.09 ± 7.19, SD 224), RAW +69.37, n=974 (26 server 503 fails) | **valid anchor of its time**; body 5 %/10 % trim −11.1 / −8.0; 0 catastrophes | `docs/STATE.md:1019-1021`; HH `gtow_hands_1783177274.jsonl` | **NO as a bot statement** (blinds bug, see E2; bot since 5 versions further) — citable as an era anchor |
| 2026-07-04 | X-ray of the −20.09 | ditto | Postflop −18.4 of −20.1 (river −8.6, flop −8.3, turn −1.6, preflop −1.6); loss in NORMAL pots, not in jams (≥100 bb: −0.7, n=14) | **Diagnosis stands** — leak is postflop, not preflop/jam | `docs/STATE.md:1021`; `../reports/GTOW_DOSSIER.md:44-46` | **YES in structure** (river remains the main leak to this day, see `HU_OPTIMAL_MAP.md:20`) |
| 2026-07-04 | GTO mode (exploit OFF + census tree + river guards) | `POKERB_GTO_MODE=1`, resolver ON, key #2 | **−11.61 ± 3.67** (recomputed SD 37), n=100, 0 fails | **SMOKE ONLY** — the ±3.67 is implausibly tight (at SD 224 one would expect ±22) | `docs/STATE.md:961-966`; HH `gtow_hands_1783194039.jsonl` | **NO** — later explicitly classified as a lucky draw (`docs/STATE.md:886`) |
| 2026-07-05 | v2 smoke (LINE_U+ECALL+SIZE_INJECT) | `POKERB_PRINCE=1`, key #2 | −97.58 ± 100.25, n=98 — of which **one hand −98 bb AIVAT**; the other 97 ≈ +2 bb/100 | **no verdict**, diagnostic value | `docs/STATE.md:942-944`; HH `gtow_hands_1783205265.jsonl` (recomputed n=98, −97.58, SD 998) | historical |
| 2026-07-05 | v2.2 300 tail smoke | PRINCE v2.2, exploit OFF, resolver ON | −20.38 ± 15.06, RAW +26.6, n=295; **0 hands ≤ −50 bb** (worst −22.5), SD 259 | **Tail dead** — distribution success, mean n.s. | `docs/STATE.md:894`; HH `gtow_hands_1783218720.jsonl` (recomputed) | distribution finding holds |
| 2026-07-05 | **v2.2 precision run (pre-registered n=2500)** | PRINCE v2.2 (7 flags), exploit OFF, resolver ON, key #2 | **−19.70 ± 4.37**, n=2393 (107 fails), **0 catastrophes ≤ −50 bb** (worst −38.2), per-hand SD **214**, RAW +1.94; body −9.0/−6.3 | **the anchor at the time (`git tag v2`)**; honest addition: the mean did **not** move vs HEAD (Δ +0.4 ± 8.4) — discipline bought safety, not μ | `docs/STATE.md:886-893`; HH `gtow_hands_1783226155.jsonl` (recomputed −19.70 ± 4.37, SD 214) | **NO** — counts as **blinds-bug-inflated** (see E2), replaced by −30.11 |
| 2026-07-05 | v2.3.1 overlay (barrel discipline) | overlay env on v2.2 | −31.95 ± 9.55, n=296 (Δ to v2.2 = 11.5 ± 17.8 = 0.65σ) | **n.s. → overlay not shipped** | `docs/STATE.md:899-900`; HH `gtow_hands_1783222593.jsonl` | historical |
| 2026-07-05 | v2.4 turn-probe arm | probe flag on v2.2 | −47.55 ± 21.11, n=296 — but the probe CLASS itself only −0.47 bb/hand over n=18 | **Headline = noise; lever PARKED** | `docs/STATE.md:876-879`; HH `gtow_hands_1783257360.jsonl` | lesson holds |
| 2026-07-05 | v3 tail smoke | PRINCE v3 (+PAIR/RIVER_DEFENSE) | −34.14 ± 9.46, n=295, **0 catastrophes, worst −19.3 bb**, SD ≈162 | mean = n≈300 noise; **the gate was the Analyzer** (see B) | `docs/STATE.md:865-868`; HH `gtow_hands_1783267831.jsonl` | historical (v3 reverted since 2026-07-06) |
| 2026-07-06 | **v8 ("Quantplay v8") live run** | GTO_MODE+deception+v3+RAISE_NARROW+OVERBET_MENU+PURIFY+TURN_DEF_ADVISOR, resolver ON | **ABORTED at 1,375 hands: AIVAT −58…−63** (pre-registered band was −12…−25), systemic from hand 1, one −271/100 block | **LIVE BREAK — whole lever family discarded** | `docs/STATE.md:614-616` | **YES as a verdict**: PURIFY/RAISE_NARROW/OVERBET_MENU/TDA have been default-OFF since (`CLAUDE.md`, PRINCE revert) |
| 2026-07-06 | Key-#3 smoke A | v2.2 reverted, fixed blinds harness | −16.84 ± 4.86, n=299 | Smoke | HH `gtow_hands_1783357739.jsonl` (recomputed); cited `docs/STATE.md:472` | historical |
| 2026-07-07 | Key-#3 smoke B | ditto | −19.99 ± 14.33, n=299 | Smoke | HH `gtow_hands_1783378134.jsonl` (recomputed) | historical |
| 2026-07-07 | **Leaderboard entry "Quantplay v8"** | **v2.2 (`POKERB_PRINCE=1`), exploit OFF, resolver ON, FIXED blinds harness**, key #3 | **−30.11 ± 5.51, n=2899 → rank 24/64**; batch alone −31.28 ± 5.92 (n=2600, 101 fails) | **the honest live anchor of the PRINCE era** | `docs/STATE.md:469-471`; recomputed from HH `gtow_hands_1783381570.jsonl` (n=2600) **+** `gtow_hands_1783378134.jsonl` (n=299) = **exactly −30.11 ± 5.51** | **YES as an era anchor** — per the documentation more likely the more honest value than −19.70 |

**The −19.70 vs −30.11 question (open, important):** per the documentation three causes cannot be cleanly separated — (1) unlucky
session, (2) both earlier numbers were favourable draws (true level ~−25 ± 5), (3) the −30.11 run used
the **fixed blinds unpack**, while the −19.70 anchor carried the EV-**protecting** overfold bug. Indication for (2)/(3):
the old account "Quantplay" sits right next to it at −30.40. (`docs/STATE.md:471-478`)

### A4. AUSLESE era — the GTOW nights (2026-08-18, key #3)

Pre-registration: relay 20→100→2000, honest expectation anchor −25…−30, v4 transfer hypothesis −20…−26,
smoke FAIL criterion ≥2 hands ≤−50 bb OR ≥1 ≤−80 bb (`data/autogym/journal.jsonl:77`).

| Date | What was measured | Configuration | Result (n) | Verdict | Source | Still valid? |
|---|---|---|---|---|---|---|
| 2026-08-18 02:06 | Smoke 20, v1 | v4 stack | n=18 usable | **DO NOT SCORE** (dict+str crash in `wickle_decide`, 2 hands lost) | `data/sessions/gtow_manifest_2026-08-18.json` | no |
| 2026-08-18 02:09 | Smoke 20 | `POKERB_AUSLESE_STACK=r6_button` + TURN_DEFENSE 0.07 + SLOWPLAY 0.25 + **RAISE_NARROW 1.0**, **resolver OFF**, exploit ON | **−21.34 ± 14.67**, n=20 | mechanically error-free, number meaningless | manifest; HH `gtow_hands_1787011654.jsonl` (recomputed) | no |
| 2026-08-18 02:16 | Smoke 100 | ditto | **−59.03 ± 22.22**, n=100 | **RED FLAG** (2σ below the anchor; v8 pattern) | `docs/STATE.md:173`; HH `..._1787011782.jsonl` | historical |
| 2026-08-18 night 1 | 4 × 500 chunks | arm `v4_gym_nackt`: **bare gym config** — exploit ON, resolver OFF, no PRINCE | A −26.59 ± 7.32 · B −54.98 ± 15.37 · C −31.65 ± 9.88 · D −48.37 ± 17.52 | chunk spread ±28 bb/100 between 500 blocks = how noisy the channel is | `data/autogym/journal.jsonl:81-82`; HH 1787012286/1787014241/1787016046/1787017672 (all recomputed, exact) | historical |
| 2026-08-18 03:55 | Interim pool (A+B+C+smokes) | ditto | **−38.86 ± 6.24, n=1617** | interim state | `docs/STATE.md:153`; recomputed, exact | **superseded** by the final pool |
| 2026-08-18 04:12 | **Night-1 final pool** | ditto | **−41.11 ± 6.31, n=2117** | **NO v4 verdict** — a never-before-measured configuration; 81 % of the loss on the river (−511 of −628 bb), pattern = old jam-spew/station | `data/autogym/journal.jsonl:83`; manifest `nacht1_endpool`; recomputed −41.11 ± 6.31 | **YES as a lesson**: "the gym config does NOT transplant bare into the live foundation" |
| 2026-08-18 06:24 | **Night 2, control chunk** | **PRINCE pure, resolver ON**, exploit OFF | **−31.34 ± 14.16**, n=488 | control lies in the −30.11 reference band → channel consistent | `data/autogym/journal.jsonl:85`; HH `..._1787019130.jsonl` (recomputed) | **YES** — reference point |
| 2026-08-18 08:03/10:04 | **Night 2, v4_prince** | AUSLESE guard chain `r6_button(turn_wert(sel_m15))` **on** PRINCE + **resolver ON**, **without** RAISE_NARROW | Chunk 2 **−14.33 ± 14.39** (n=490) · chunk 3 **−27.92 ± 12.12** (n=489) · **pooled −21.12 ± 9.41 (n=979)** | **Δ vs control = +10.23 bb/100** — best live value of the AUSLESE era, but **1 SE class**, not significant | `data/autogym/journal.jsonl:86-88`; HH 1787027076/1787033025 (recomputed, pooled −21.12 ± 9.41) | **YES — this is the only GTOW anchor valid today** (`docs/STATE.md:56`) |
| 2026-08-18 | Chunk 4 of night 2 | v4_prince | **LOST** (deadlock 20 slots / 503 storm; client writes HH only at the end) | data loss, no result | `data/autogym/journal.jsonl:88` | — (reason for the K4 ledger, `pokerbot/benchmark/gtow_ledger.py:1-16`) |

**Result ranking of the live axis, as of today:** v4_prince −21.12 ± 9.41 (n=979) > PRINCE control
−31.34 ± 14.16 (n=488) ≈ leaderboard entry −30.11 ± 5.51 (n=2899) ≫ v4 gym bare −41.11 ± 6.31 (n=2117).
**Everything after that (auslese-v5 "r8_stack", v8, v9, v10) has NO GTOW anchor** — only mirror evidence
(`docs/STATE.md:56`; `HU_OPTIMAL_MAP.md:112-113`).

### A5. Negative results of the live axis (collection)

- **Preflop switch (GLM)** −99.39 → reverted (`docs/STATE.md:1160`).
- **Solver-freq hint** neutral (−49.21 vs −49.52) → discarded (`data/gtow_hints_ab.log:38,46`).
- **Re-SFT+GRPO** −90.18 → campaign discarded (`data/gtow_newgrpo.log:26`).
- **Anti-spew call gate** REFUTED by a $0 counter-check; the fat tail came from hero's −EV **betting**, not from
  over-calling (memory `gtow-tail-body-vs-spew`, `docs/STATE.md:1112`).
- **v8 live break** −58…−63 instead of −12…−25 (`docs/STATE.md:614-616`) → PURIFY/RAISE_NARROW/OBM/TDA default-OFF.
- **RAISE_NARROW is contraindicated with resolver ON** (range poisoning) — that is why v4_prince ran without RN
  (`data/autogym/journal.jsonl:83` context, `docs/STATE.md:158-160`).
- **Off-tree bet sizing against GTOW** — no yield: off-tree AIVAT −1.73 vs on-tree −1.55 (0.3σ), n=3,292
  hero bets from 13,477 hands (`../reports/GTOW_DOSSIER.md:66-69`).

---

## B. GTOW Analyzer (per decision, $0) — different channel, different statement

The Analyzer grades uploaded hand histories **per move** against GTO: "GTO score" (frequency hits) and
**"Avg EV loss" in bb/100**. It is deterministic and noise-free with respect to card luck — it measures **deviation
cost**, not realised money against an opponent. Cross-check 2026-07-04: EV loss 19.33 ≈ live AIVAT −20.09
→ two independent methods agree (`../plans/TIE_GTOW.md:14-15`, `docs/STATE.md:1032`).

| Date | What was measured | Configuration | Result (n) | Verdict | Source | Still valid? |
|---|---|---|---|---|---|---|
| 2026-07-04 | HU engine HEAD | exploit-primary, resolver OFF (export) | **GTO score 53.4 % · EV loss 19.33 bb/100 · freq diff 54.6 %**, n=1500 (2,599 moves); streets: preflop 76.2 %, river 53.9 % (28.1 % M+B) | anchor of the Analyzer axis | `docs/STATE.md:1030-1035`; `../plans/TIE_GTOW.md:14` | era anchor |
| 2026-07-04 | 6-max core `tag` | league core, not `bot.py` | **85.9 % · EV loss 7.61 bb/100**, n=1500 | 6-max is clearly closer to GTO than HU | `docs/STATE.md:1059`; `docs/STATE.md:53` | **partly** — measures the league core, not the product (`HU_OPTIMAL_MAP.md:115-117`) |
| 2026-07-04 | GTO-mode hypothesis T1 | exploit OFF + census tree + tracker damping | Score **49.8 % (↓3.6pp)** · EV loss **17.05 (↓2.28)** · freq diff **54.57 (FLAT)** | **HYPOTHESIS REFUTED** — exploit-OFF does not move the frequency deviation; it is intrinsic to the core | `docs/STATE.md:1041-1046`; `data/gtow_grades/gtomode_paired_s55.json` | **YES, binding** |
| 2026-07-04 | **Score-vs-EV trade-off** (paired, seed 55) | 3 variants, identical deals | HEAD 65.8 %/17.27 · clamp-fold 64.5 %/**15.42 (best EV)** · limp→open fix **67.0 % (best score)**/19.56 | **Frequency matching costs money** → fix REVERTED; doctrine "only count bb" | `data/gtow_grades/gtomode_paired_s55.json` (field `variants`); `docs/STATE.md:1050-1056` | **YES, binding** |
| 2026-07-05 | v2.2 vs v3 (paired, seed 55) | identical deals | **v2.2 = 20.66 · v3 = 17.93 (−2.73)** | **v3 SHIPPED** (the decisive $0 gate); cross-check: 20.66 ↔ live −19.70 | `docs/STATE.md:873-876` | number historical (v3 reverted since 07-06) |
| 2026-07-05 | v3.1 (flat thin-value floor) | paired seed 55 | **19.76 (+1.83 worse)** | **REFUTED** — 3rd proof: frequency without selection loses | `docs/STATE.md:869-872` | **YES, binding** |
| 2026-07-06 | v3.2 (selection-aware thin value via eCall) | paired seed 55 | **26.14 (+8.21 worse)** | **REFUTED, worst arm of the family** | `docs/STATE.md:795-797` | **YES** |
| 2026-07-06 | Family C (seed 56, 1500 each) | local, turn resolver OFF | Anchor 24.90 · **v3.3 RAISE_NARROW 19.41 (−5.49)** · v3.4 AUDIT_FIX **27.52 (+2.62 REFUTED)** · v3.5 ADVISOR_ROLE_POS 25.05 (+0.15 neutral) | v3.3 promoted; **the 9 "bug fixes" were behaviour-carrying** | `docs/STATE.md:719-724` | verdicts hold; v3.3 later broke live |
| 2026-07-06 | Family D (seed 57) | anchor carries v3.3 | **OVERBET_MENU 16.45 vs 21.27 (−4.82)** promoted; TURN_OVERBET −4.17, BARREL_DISCIPLINE −3.55 noted | promoted | `docs/STATE.md:711-717` | **NO live** (v8 break) |
| 2026-07-06 | Family E (seed 59) | anchor v3.3+OBM+PURIFY = 17.54 | **NO promotion**: bd +0.19 · rcd +1.22 · tob +1.95 — the family-D "winners" did NOT replicate | **One-winner rule confirmed** | `docs/STATE.md:697-704` | **YES, methodologically binding** |
| 2026-07-06 | PURIFY | seed 57/59 paired | 14.80 vs 16.45 (−1.65, borderline) → promoted | **later REFUTED live** (v8 break, PURIFY silently killed SLOWPLAY) | `docs/STATE.md:693-696`; `docs/STATE.md:617-621` | **NO** |
| 2026-07-06 | Family F / v5C | seed 60 | v5C 17.19 vs 19.06 (−1.87) promoted; v5A PURIFY2 −0.41 neutral; v5B +1.33 refuted | promoted | `docs/STATE.md:678-681` | **NO live** |
| 2026-07-06 | Closing set `hu_final_1500` | v8 full stack, seed 61 | **EV loss 20.71**, score 831/355/314 (best score of the night) | **UNPAIRED** — neither gain nor loss established; anchor drifted 17.5–21.3 during the night for the same profile | `docs/STATE.md:670-677` | **YES as a warning**: Analyzer anchors drift across seeds (14.80@s57 vs 17.54@s59 for the same profile) |
| 2026-07-06 | Danger set (1500 hardest spots) | champion hands filtered | EV loss **50.18 by design** (never compare with normal sets); 591 wrong > 559 correct | class identified: bloated pots, raise confrontations | `docs/STATE.md:696-709` | **YES as an instrument lesson** |
| 2026-07-06 | RAISE_COMMIT danger-paired | 1500 dangerous deals, identical indices | anchor 47.41 vs rcd **55.37 (+7.96 WORSE)** | **DECISIVELY REFUTED** — 5th refutation of the family "flat adjustment without selection" | `docs/STATE.md:625-632` | **YES, binding** |
| 2026-06-29 | Brain+engine per decision | Claude + engine, 50 hands / 86 moves | **69.9 % · EV loss 6.1 · freq diff 48 %** | brain plays dramatically closer to GTO than the bare engine; **small sample** | `docs/STATE.md:1089` | historical |
| 2026-06-29 | ONTREE snap per decision | 60 hands / 133 moves | 60.4 % · 47.5 · 51 % | **CONFOUNDED** (different seed from the comparison arm) → no verdict | `docs/STATE.md:1092` | no |

**Analyzer channel traps (measured, binding):** hand IDs **burn on FIRST contact** — even on
failed uploads; an upload with overlapping IDs became 1,482/1,500 "Duplicate" (`docs/STATE.md:729-742`).
Rules from that: never overlap ID ranges (≥2000 spacing), fresh `dayoffset` and fresh seed per family,
CRLF mandatory (the Analyzer does not read LF files). Monthly budget ≈ 131k hands (18k/150k consumed, as of
2026-07-06, `docs/STATE.md:737-740`). Export runs are **not** byte-deterministic (unseeded global
RNG stream for villain's mixed strategies) — pairing over identical deals remains valid, street attribution does not
(`docs/STATE.md:717-719`).

---

## C. GTOW as a data source (measurements ABOUT the opponent, not about us)

| Date | What was measured | Instrument | Result (n) | Verdict | Source | Still valid? |
|---|---|---|---|---|---|---|
| 2026-07-04 | GTOW's sizing tree (census) | `research/gtow_tree_census.py` over own HH | **12,483 hands** (86 hero unknown); flop bets SRP {0.35: n=1015, 0.75: 240}, river {0.65: 316, 0.35: 184, 1.0: 151, 1.5: 81, 3.0: 12}; river raise 0.5 pot = workhorse | tree map, basis of the on-tree snapping | `data/census/gtow_tree.json` (`stats.hands` = 12483); `../reports/GTOW_DOSSIER.md:30-41` | **YES** |
| 2026-07-05 | GTOW's frequencies per node | `research/freq_mine.py` | **13,675 hands → 26,823 GTOW decisions, 366 buckets**; hero-ID cross-check 11,633/11,633; aggression parity walk↔census exactly 18,468 = 18,468 | free teacher data set | `data/freq_targets/gtow_frequencies.json` (`meta.stats`); `docs/STATE.md:1062-1074` | **YES** |
| 2026-07-05 | Three design answers from the mining | ditto | (1) vs 2nd+ barrel with ONE pair (n=241): call 54 %/fold 43 %/raise 4 %; river top pair **fold 55 %**. (2) River bluff share SRP **28 %** (n=825, mean size 0.81 pot). (3) Flop check-back IP (n=2,647): air 63 %, traps only 1.9 % | empirical anchors instead of gut feeling | `docs/STATE.md:1066-1074` | **YES** |
| 2026-07-04 | **Attack surface "off-grid sizes"** | mining 13,477 hands, n=3,292 hero bets | GTOW's fold % is smooth, monotone, ≈ exactly MDF (flop 0.35× → 26.9 % vs MDF 26 %; 1.0× → 50.1 % vs 50 %); all midpoint tests <2σ; 212 absurd legacy jams (up to 99.5× pot) → 90.6 % coherent folds; **off-tree AIVAT −1.73 vs on-tree −1.55** | **REFUTED** (empirically + architecturally: GTOW = Ruse real-time re-solver, no translation edge) | `../reports/GTOW_DOSSIER.md:58-70` | **YES, binding** |
| 2026-07-05 | GTOW's raise mix | `research/raise_mine.py`, 488 raises | jams ~62 % nutted; flop raises 53 % air; river raises 16 % air (polarised) | basis for RAISE_NARROW **and** for the RAISE_COMMIT refutation | `CLAUDE.md` (v3.3 block); `docs/STATE.md:626-629` | **YES** |
| 2026-08-30 | Where v4 loses against GTOW (HH mine) | `research/hh_luecken_mine.py` + `gpu_river_audit.py` on night-2 HH | **87 % of the loss on the river**; cell (river, >100 bb, call) = 9 hands = **59 % of the v4 loss**; GPU audit 571/571 river decisions: check/fold solver-conformant (p 0.86/0.83), **bet the weakest class (p 0.45)** | leak localisation, basis for r7/r8 | `docs/STATE.md:112-121` | **YES** |
| 2026-08-30 | Tracker discrimination on GTOW hands | `research/river_bill_replay/_diagnose` | tracker equity does NOT separate winners/losers (0.578 vs 0.513 default; 0.652 vs 0.532 under PRINCE); ranges after 3 barrels still 700–900 combos | **a threshold guard on tracker basis does not carry the river defence** | `data/autogym/journal.jsonl:89` (R7-DIAGNOSE) | **YES** |
| 2026-08-31 | Counterfactual `river_gpu_guard` on real GTOW hands | replay of the night-2 big pots | 3/22 big-pot calls folded = exactly the disasters, **net +66.9 bb**; incl. GTO-correct fold of the lucky call #2997685 (AIVAT −9.2 despite +81.8 real) | **counterfactually positive, never cross-checked live** | `data/autogym/journal.jsonl` (R8-GPU-RESOLVER, line 90); `docs/STATE.md:132-135` | **YES as replay evidence, NO as live proof** |
| 2026-08-31 | `river_play_guard` full profile on GTOW hands | all 3,904 night-2 decisions | **32 interventions (0.8 %)**; v4 arm: call→fold 7 (net **+278.6 bb**), fold→call 3, bet→check 5 …; AIVAT convergence on the same hands (#2991749 AIVAT −52.2; #2993037 −33.1) | **GTOW-axis evidence positive** — but neutral in the mirror (v8 dropped) | `data/autogym/journal.jsonl:94`; `../reports/V8_POSTMORTEM.md` | **YES as a finding, unproven without an anchor** |
| 2026-09-01 | v9 pre-gate "left on the table" | deep replay 571 decisions with action EVs | **Left on the table : mistakes = 1.6 : 1**; A1 missing river RAISE play = **31.1 bb overfold in 970 hands**; A2 size precision 9.0 bb; A3 mis-value-bets 11.5 bb (v4) / 27.4 bb (control); A4 VERLUST_CALL only 4.1 bb | prioritisation by EV lever; **A4 lesson: AIVAT cells ≠ decision attribution** | `HU_OPTIMAL_MAP.md:13-14,20-38` | **YES** |

---

## D. Leaderboard (external comparison)

| Date | What was measured | Instrument | Result | Verdict | Source | Still valid? |
|---|---|---|---|---|---|---|
| 2026-07-04 | Leaderboard pull | GTOW API `/leaderboard` | Bitcrumbs **−3.14** (44,500 h, SD 1.00) · Kevin Rabichow (human) −3.91 · MIT Marvel −5.81 · GPT-5.2 XH −8.26 · GPT-5.5 XH −9.23 · … MIT −16.78 | **nobody beats GTOW** | `data/gtow_grades/leaderboard_2026-07-04.json` | superseded by D2 |
| 2026-09-10 | Leaderboard state + own entries | browser, 83 entries | Top Bitcrumbs −3.1 (52,005 h) · Trainer −6.2 · Roman_SL −7.4 · tangtang −12.6 · GPT-5.5 XHigh −9.2. **Own entries (org "Hampe"): Quantplay −30.4 (rank 31, 6,587 h) · Quantplay v8 −31.6 (rank 33) · Experimental Poker Bot −51.7 (rank 47)** — all v8 era; today's state (~−21) was **never posted** | Rank = **lower bound of the 95 % interval** ⇒ hands count like the mean; **top-5 threshold LCB ≈ −14.8** (≈ −11 at 10k hands, ≈ −13 at 50k); gap ≈ 8 bb/100 | `data/autogym/journal.jsonl:120`; `../reports/KAGGLE_ARENA.md`; `docs/STATE.md:6-19` | **YES** |
| 2026-09-10 | Calibration Kaggle→GTOW | 6 shared models | r=0.37 / R²=0.14 (residual SD 15.5); without Grok 4 r=0.88 | **NOT ROBUST** (curve fitting) | `data/autogym/journal.jsonl:120`; `docs/STATE.md:12-14` | **YES (as a negative verdict)** |

---

## E. Measurement seams that invalidated GTOW numbers (the bug chronicle)

| No | Bug | Effect on numbers | When fixed | Source |
|---|---|---|---|---|
| **E1** | Local runner + `gtow_to_state` took `blinds[-1]` = SB = 50 as the big blind | **ALL locally computed bb/100 before 2026-06-19 are 2× inflated** (−74.7 → real ≈ −37; −93 → ≈ −46.5; −71 → ≈ −35). Server-side `/results` (−47.18) was always correct. The "regression" derived from it was an artefact | 2026-06-19 | `docs/STATE.md:1174` |
| **E2** | `gtowizard._parse_history` unpacked the live blinds `[BB,SB]` as `[SB,BB]` | Preflop blind init **inverted in EVERY live AIVAT run** → BB-vs-open `to_call` 175 instead of 125 = +7pp required equity = built-in preflop overfold. **Affects −19.70 and −20.09**; exports/Analyzer NOT (different code path). Self-test fixture had the same wrong order → asserts never caught it | 2026-07-05 (audit, commit 8c827cc) | `docs/STATE.md:836-840` |
| **E3** | `gtow_to_state` logged preflop `to_call` as the TOTAL POT | Preflop `required_equity` inflated in 100 % of preflop facing-bet spots (+0.22 on average) → co-cause of the GLM preflop overfold (−41/hand) | 2026-06-21 | `docs/STATE.md:1140` |
| **E4** | `_FINGERPRINT_KEYS` lacked 13 run-defining flags (incl. both active gate flags) | Lever-arm exports carried the fingerprint of the base profile → arms not distinguishable | 2026-07-05 | `docs/STATE.md:840-842` |
| **E5** | Driver `subprocess(text=True)` = cp1252 on Windows | `UnicodeDecodeError` on client output ⇒ **every SUCCESSFUL 500 chunk counted as a failure** and was retried (hand budget burnt). All hands + AIVAT recovered from the HH files, method validated exactly against the smokes | 2026-08-18 | `data/autogym/journal.jsonl:81` |
| **E6** | HH logging wrote only AFTER all hands with `open('w')`, without hero ID/fingerprint/arm per line | **Chunk 4 of night 2 completely lost**; the arm assignment of all files hangs on mtime + journal + manifest | Countermeasure built: `pokerbot/benchmark/gtow_ledger.py` (append-only, flush+fsync per event, `status` never imputed to 0) — **not yet wired into the live harness** | `../reports/V10_FACTS.md:232-234`; `pokerbot/benchmark/gtow_ledger.py:1-16` |
| **E7** | `research/analyze_gtow_hands.py:141` sets **BB=50** | **all bb/100 from this script are inflated by a factor of 2** (API blinds are [100,50]). Affects only after-the-fact analyses, not the live numbers (whose regex reads `main.py:220` with bb=100) | **OPEN** (documented, not fixed) | `../reports/V10_FACTS.md:246-247` |
| **E8** | 409 orphans (up to 20 hanging hands block the account) | Runs fail at start; **rule: before EVERY GTOW start `clear_inprogress.py`** | process rule since 2026-08-18 | `docs/STATE.md:167-169` |
| **E9** | `gtowizard.py` constructs `PokerBot` directly (v4 wrapper NOT in the harness) + resolver default **ON** (RAISE_NARROW trap); `auslese.setze_env` is never called in the GTOW path; `button_disziplin` hard-codes blinds 50/100 | An arm can silently play a **different** configuration than intended | Adapter built 2026-08-18 (`POKERB_AUSLESE_STACK`); remaining items D6 **OPEN** | `docs/STATE.md:210-213`; `../reports/V10_FACTS.md:240-242`; `HU_OPTIMAL_MAP.md:101-102` |
| **E10** | The HU web app played a never-measured config (no PRINCE, exploit=True, full r8 chain + RAISE_NARROW=1.0) | The played product ≠ the measured definition | Fix "D1" 2026-09-07/08 | `HU_OPTIMAL_MAP.md:81-85`; `../reports/V10_GATES_REPORT.md:18` |

---

## F. Hand budget and total number of GTOW hands played

**Reconstructible (lower bound): ≈ 38,650 hands.** Calculation:
- **20,859 hands** account aggregate up to 2026-06-19 (`docs/STATE.md:1170`) — covers all legacy eras, incl. the locally
  logged 6,265 hands from 16–19 June.
- **24,050 hands** exist locally as hand history: 65 files `data/sessions/gtow_hands_*.jsonl`, each line one
  hand with an `aivat` field (counted myself: 24,050 lines, 24,050 of them with `aivat`). Distribution by day:
  06-16: 5,219 · 06-18: 50 · 06-19: 996 · 06-20: 200 · 06-21: 4,603 · 06-22: 310 · 06-29: 1,105 · 07-04: 1,094 ·
  07-05: 3,673 · 07-06: 299 · 07-07: 2,899 · **08-18: 3,602**.
- Lower bound = 20,859 + (24,050 − 6,265) = **38,644**.
- **In addition, not quantifiable:** the lost chunk 4 of night 2 (≤ 500 started hands, never logged) and
  failed/aborted hands that count server-side (26 fails in the 1000 run, 101 in the 2600 batch,
  107 in the 2500 run, 1,375 hands of the aborted v8 run — the latter cannot be found in the local files).

**Accounts/keys:** key #1/#2 (account "Quantplay", legacy eras + brain era + July anchors, aggregate −30.40 on the
leaderboard) · **key #3** = the clean campaign account ("Quantplay v8", −30.11/n=2899 = rank 24 at entry,
today rank 33 with −31.6) · a third entry account "Experimental Poker Bot" (−51.7, rank 47).
Monthly Analyzer quota ≈ 150k hands, of which 18k consumed (as of 2026-07-06, `docs/STATE.md:737-740`).

**Since 2026-08-18 NOT a single GTOW hand has been played.** Last HH file: `gtow_hands_1787033025.jsonl`
(2026-08-18 10:04). The v10 relay was deliberately **not started** (pre-registered blocker G3 missed,
hand budget, operator decision) — `../reports/V10_GATES_REPORT.md:112,121`; `data/autogym/journal.jsonl:109`.

---

## G. What holds TODAY on the GTOW axis — and what is missing

**Holds:**
1. **Only valid live anchor: v4-on-PRINCE, −21.12 ± 9.41 bb/100 (n=979, 2026-08-18 night 2)** — configuration:
   AUSLESE guard chain `r6_button(turn_wert(sel_m15))` on `POKERB_PRINCE=1`, **resolver ON**, exploit OFF,
   **without** RAISE_NARROW, 200 bb, key #3. Control of the same channel (PRINCE pure): −31.34 ± 14.16 (n=488).
   (`data/autogym/journal.jsonl:86-88`; `docs/STATE.md:56`)
2. The leaderboard entry of the PRINCE era **−30.11 ± 5.51 (n=2899)** is the only externally verified number with
   n > 2000 on the fixed harness.
3. Structural diagnoses (river is the main leak; loss in normal pots; preflop nearly solved; frequency matching
   costs money; off-tree sizing brings nothing) are confirmed repeatedly and over two independent channels.

**Missing / open:**
- **auslese-v5 (`r8_stack`, the champion since 2026-08-31) has NO GTOW anchor** — only mirror evidence
  (+27.6 ± 1.8 pooled vs r6_button, +30.60 ± 5.03 vs frozen base, all self-play). The documented
  non-transitivity of the mirror explicitly does **not** make these numbers GTOW numbers (`docs/STATE.md:136-146`).
- **v8, v9, v10 have no anchor.** v8 was dropped without a GTOW A/B (mirror neutral); v10 is by gate decision
  **not GTOW-ready** (`../reports/V10_GATES_REPORT.md:112`). The v10 "G2 live" value (plan played 25/40, off-tree 11/40,
  p99 10.15 s) is a **local replay in GTOW-channel CONFIGURATION**, not an API hand
  (`data/runs/v10/G2_latenz_fix_live.json`, field `laeufe` = local worker commands).
- **AIVAT audit not carried out:** the pre-registered falsification test (fold agent must show exactly −75 bb/100;
  own AIVAT from our HH against the GTOW number) is planned but never ran
  (`data/autogym/journal.jsonl:79`, type AIVAT-AUDIT-PLAN).
- **SE arithmetic for the next round:** SE 2 per arm ⇒ 12k–49k GTOW hands (`data/autogym/journal.jsonl:102`).
  A tie claim (0 within 2σ) would need ≈ 12,000 hands (`../plans/TIE_GTOW.md:61-62`).

---

# GTOW Analyzer / Chrome upload channel

The channel: we play our bot against an internal opponent, write valid **PokerStars hand histories**
(`research/pokerstars_export.py` HU, `research/sixmax_export.py` 6-max, `research/claude_export.py` LLM brain),
the operator uploads the file to GTO Wizard → *Analyze → Uploads*, and GTOW grades **every hero decision against
its own solver solution**. Three numbers come back: **GTO score** (frequency/action agreement),
**Avg. EV loss** (bb/100 against the GTO action) and **freq diff** (distance of the action mixes), plus the
breakdown by street/position/pot type and per-hand grades.

**What the channel can do:** grade per decision against a NEAR-GTO oracle, without variance — the same export yields
the same verdict; paired arms (identical seed = identical deals) deliver an almost noise-free delta between
two bot versions for the price of minutes instead of hours. It is the **fast** channel (export ~4 min locally,
grading minutes; the live API needs ~8-9 h for 2500 hands — `docs/STATE.md:774`).

**What it CANNOT do:** (1) It grades only **on-tree** spots — whatever lies outside GTOW's solution tree
(limp/iso pots, odd bet sizes) drops out as *UNSOLVED* and is not graded at all → every score is a
score **over the gradeable subset** (survivorship). (2) It measures **no realised money** — EV loss is a
per-decision distance, not AIVAT. (3) It is **structurally blind to range-transparency costs**: it grades
against GTO ranges, not against an adaptive re-solver that updates beliefs within the hand
(`docs/STATE.md:618` — exactly what v8 broke on live). (4) The GTO score as a target is **refuted by measurement**
(see section "Score vs EV").

---

## 1. Upload rules and pitfalls (all learned the hard way)

| Rule | Why / evidence | Source |
|---|---|---|
| **CRLF mandatory** — exporter pins `newline="\r\n"` on every platform | The first pod/Linux-generated upload was LF-only; the Analyzer could not parse it. Local Windows exports were CRLF only by accident (text mode). | `research/pokerstars_export.py:293-296`; `docs/STATE.md:748-750` |
| **Hand IDs burn on FIRST contact — even on FAILED uploads** | An aborted LF upload had already registered the identities #303–#1801 in GTOW's registry (whose upload row is not even listed). The repeat upload: **1,499 duplicates / 1 processed** — the one analysed hand was #1802 (97o on AQ538, operator-confirmed). | `docs/STATE.md:748-756` |
| **ID ranges must NEVER overlap (≥2000 spacing), fresh `--dayoffset` per file, fresh seed per repeat family** | Family 3 (idbase 320-323, +1 steps) produced 99.9 % overlap → 18/1/2/3 hands processed at **1,482 duplicates**. The Analyzer dedups against ALL earlier uploads. The convention "+1 idbase per arm" was our own design error. | `docs/STATE.md:741-747`; law encoded in `research/pokerstars_export.py:256-263` |
| Exporter warns on default `idbase`/`dayoffset` and on `idbase < 40000` (burnt legacy range 299–1822+) | Audit fix 2026-07-05 | `research/pokerstars_export.py:250-263` |
| **Config sidecar mandatory** (`*_konfig.json` with full env fingerprint, seed, idbase, dayoffset) | A lever arm without a fingerprint cannot be attributed; `_FINGERPRINT_KEYS` at times lacked 13 run-defining flags → arm exports logged "plain-v3" fingerprints. | `research/pokerstars_export.py:288-293`; `docs/STATE.md:840-842` |
| **Fingerprint lies on runtime env setting** | `fingerprint()` reads `os.environ` at PRINT time, agents bind `use_*` flags at construction → pod-1 solved turn spots for 1.4 h while the log claimed `TURN_RESOLVER='0'`. | `docs/STATE.md:766-772` |
| The **operator** must click the upload | The Chrome `file_upload` tool is sandboxed and rejects repo/scratchpad paths; Claude then reads the verdicts via `get_page_text` on the Uploads/Stats page. | `memory/gtow-analyzer-loop.md` |
| **Quota** is not the bottleneck | Account showed 18k/150k hands consumed, reset 28.7 → ~131k hands/month = the real screening budget (k×1500 per arm). | `docs/STATE.md:745-747` |
| ID ledger (burnt) | 299–1822 (legacy), 320-323/days 45-48, 50000–56000 (fam. C), 66000–72009, 74000+, 76000–82000+1500 (fam. E), 84000–91500 (fam. F), 92000/94000/96000, 120000–126000 reserved, 130000–130199 (v10). Days 31-39, 45-48, 50-53, 60, 80-83, 90. Next free proposal: **132000 / day 91 / seed 1110**. | `data/runs/v10/g5_analyzer_ledger.json`; `docs/STATE.md:576,626,685,690,704` |

---

## 2. Absolute grades (unpaired) — "how close to GTO is this version?"

Context: unpaired absolute numbers are **not comparable between seeds** (measured anchor drift 14.80 on
seed 57 vs 17.54 on seed 59 for THE SAME profile, `docs/STATE.md:696`). They serve as a map, not as a gate.

| Date | What was measured | Instrument / channel | Result (n) | Verdict | Source | Still valid? |
|---|---|---|---|---|---|---|
| 2026-06-28 | HU engine (exploit-primary, pre-ONTREE) absolute | Analyzer, `bot_hands_1000.txt` | GTO score **50.7 %**, avg EV loss **22.67 bb/100** (1000 hands, 800 analysed) | first robust absolute number; "stable → reliable" | `memory/gtow-analyzer-loop.md`; `docs/STATE.md:1084` | NO — engine replaced several times since (ONTREE, GTO_MODE, PRINCE, AUSLESE) |
| 2026-06-28 | Off-tree share (what the Analyzer CANNOT grade) | Analyzer API `items[]`, per decision | UNSOLVED by pot type: **limp 100 %, iso 100 %, 3-bet ~72 %, SRP ~59 %**; donk bets **0** (hypothesis refuted) | structural channel limit, not a bot error | `memory/gtow-analyzer-loop.md`; `docs/STATE.md:1084` | YES as a channel property; the numbers themselves are pre-ONTREE |
| 2026-06-28 | Street weakness in the gradeable part | Analyzer, per street | River weakest: **50.9 % perfect**; SB 66.5 % vs BB 66.1 % GTO score (≈ equal → BB loss is structural/button edge, not a leak) | leak localisation | `memory/gtow-analyzer-loop.md` | partly — "river = weakest street" replicated in EVERY later measurement |
| 2026-07-04 | HU HEAD (exploit-primary) absolute | Analyzer, `hu_hands_1500.txt` (file 78ec0a6c) | **GTO score 53.4 % · EV loss 19.33 bb/100 · freq diff 54.6 %** (n=1500, 2,599 moves); preflop 76.2 %, river 53.9 % (28.1 % mistake+blunder) | **Cross-validation**: 19.33 ≈ live AIVAT −20.09 → two independent instruments agree; the deviation is real cost, not tail luck | `docs/STATE.md:1031-1036`; `../plans/TIE_GTOW.md:14-15` | number NO (engine replaced), **method YES** — the double measurement is to this day the argument against "that was only variance" |
| 2026-07-04 | 6-max product core (`tag`) absolute, small | Analyzer, `sixmax_hands_300.txt` (file 0e1df589) | GTO score **79.3 %**, EV loss **12.33 bb/100** (n=227 hands / 263 moves) | first absolute 6-max grade ever; **low draw** | `docs/STATE.md:1047-1057` | NO — replaced by n=1500 (79.3 was noise) |
| 2026-07-04 | 6-max product core (`tag`) absolute, stable | Analyzer, `sixmax_hands_1500.txt` (file 84cfebd7) | **GTO score 85.9 % · EV loss 7.61 bb/100** (1,781 moves; perfect 82.6 / good 8.1 / inacc 2.2 / mistake 4.1 / blunder 3.0) | the most GTO-like core of the project; leaks: preflop 88.5 % strong, everything postflop 57–61 %, **river 22.4 % M+B**; blinds weakest positions (SB 74.2 / BB 75.9 vs HJ 91.4); **as preflop CALLER 23.5 % M+B vs 6.6 % as raiser** | `docs/STATE.md:1059-1070`; `memory/sixmax-gtow-grade.md` | **restricted** — still cited as "external anchor" on 2026-09-09 (`docs/STATE.md:53`), but the graded `tag` core was changed by `flat_guard` the same day; new export open (`docs/STATE.md:30`) |
| 2026-07-04 | EV-loss concentration (both disciplines) | Analyzer API, server filter EV loss ≥ 2 bb or ≥ 8 bb | 6-max: of **54 "blunders" only 2 cost ≥ 8 bb** (one 3-bet pot −8.25, one 4-bet pot −34.23 = worst hand of the run). HU: 25 hands ≥ 2 bb = **8.60 of 19.33 bb/100** | The score is dominated by ~0-EV mini-pot blunders; the damage sits in a few big pots → lever = big-pot stack-off discipline, not blunder counting | `docs/gtow_grades/LEAK_MAP.md`; `data/gtow_grades/{hu,sixmax}_leaks_ev2.json`; `../plans/TIE_GTOW.md:23-45`; `../NOTES.md:52-54` | **YES** — uncontested as a structural finding; congruent with the live fat-tail finding |
| 2026-07-04 | HU leak map (per hand) | Analyzer API `actions_with_correctness_*` | 25 expensive HU hands: **100 % in the blinds** (BB 18 / SB 7); #1 signature **flop check→fold vs c-bet, 9/25** (folds top pair Kd6s on KcTs5h); #2 river over-aggression 10/25. Streets: flop 11 · river 10 · preflop 2 · turn 1 | named, reproducible leak classes (basis of the v3 levers) | `data/gtow_grades/LEAK_MAP.md`; `data/gtow_grades/hu_leaks_ev2.json` | classes YES (river/blinds defence reappear until 2026-08), the hand list NO |
| 2026-09-08 | v10 (`r10_stack`) Analyzer export | `research/pokerstars_export.py`, 200 instead of 1500 hands | file created (`hu_v10_r10_stack_200.txt`, IDs 130000–130199, day 90, seed 1109) — **no grade documented**; ship decision "NOT GTOW-ready" | open/unused | `docs/STATE.md:87-88`; `data/runs/v10/g5_analyzer_ledger.json` | export exists, IDs reserved in the ledger; **no result** |

**Not comparable:** the HU 53.4 % and the 6-max 85.9 % must NOT be read against each other — 6-max
contains many easy preflop folds in the mix (`docs/STATE.md:1057`, `memory/sixmax-gtow-grade.md`).

---

## 3. The score-vs-EV finding (the most important NEGATIVE result of the channel)

| Date | What was measured | Instrument / channel | Result (n) | Verdict | Source | Still valid? |
|---|---|---|---|---|---|---|
| 2026-07-04 | `POKERB_GTO_MODE` (exploit OFF + census tree + tracker damp + river guards) vs HEAD | Analyzer, `hu_gtomode_1500.txt`, seed 55 | **GTO score 49.8 % (−3.6 pp, worse) · EV loss 17.05 (−2.28, better) · freq diff 54.57 % (FLAT)** (n=1500) | **Hypothesis REFUTED**: exploit-OFF did not lift the score towards 85 % and did not move the freq diff → the frequency deviation is **intrinsic to the core** (blueprint+advisor+resolver), not the exploit overlay | `docs/STATE.md:977-987`; `../plans/TIE_GTOW.md:47-56`; `data/gtow_grades/gtomode_paired_s55.json` | **YES as a lesson** (adopted into CLAUDE.md/doctrine) |
| 2026-07-04 | 3-way paired seed 55: HEAD (limps) / mode (folds marginal SB) / mode-fix (opens marginal SB) | Analyzer uploads page, identical deals | HEAD **65.8 % / 17.27** · mode-clamp **64.5 % / 15.42 (best money)** · mode-fix **67.0 % (best score) / 19.56 (worst money)** | **Clean score-vs-money trade-off.** The SB over-fold is EV-PROTECTING; frequency alignment with GTOW costs money as long as postflop is weak. Fix **reverted** (`bot.py:243`) | `data/gtow_grades/gtomode_paired_s55.json`; `docs/STATE.md:993-1010` | **YES** — from this the standing doctrine "only count bb, the GTO score is dead as a target" (`../reports/GTOW_DOSSIER.md:3`, `memory/gto-score-vs-ev-tradeoff.md`) |

---

## 4. Paired lever arms (the real use of the channel) — campaign 2026-07-05/06

Protocol (formulated as binding, `docs/STATE.md:577-590`): per arm 1500 hands on an identical seed, verdict only
against the **anchor of the same family**, promotion needs Δ > max(1.5; 2·SE_diff), the effect must sit
in the TARGET class, at most ONE winner per family. All numbers are **avg. EV loss (bb/100), smaller = better**.

### Family A/B — local, seed 55

| Date | Arm | Result (n=1500) | Δ vs anchor | Verdict | Source |
|---|---|---|---|---|---|
| 2026-07-05 | v2.2 (anchor) | **20.66** | — | anchor; cross-check: its live AIVAT was −19.70 | `docs/STATE.md:872-874` |
| 2026-07-05 | **v3** (PAIR_DEFENSE 0.10 + RIVER_DEFENSE 0.06) | **17.93** (at 1305/1500 processed) | **−2.73** | **PROMOTED** (in the predicted band −2.5…−4.5) | `docs/STATE.md:857-861,872-874` |
| 2026-07-05 | v3.1 (flat river thin floor 0.40 + cbet-damp 0.28) | **19.76** | +1.83 | **REFUTED** — third measurement of the same lesson: frequency matching WITHOUT the teacher's selection loses EV | `docs/STATE.md:863-870` |
| 2026-07-05 | v3.2 (selection-aware thin value via e_call ≥ 0.5) | **26.14** | +8.21 | **REFUTED, worst arm of the family** — our tracked range is not the teacher's selection, e_call systematically overestimated; river thin class parked entirely (4th failure) | `docs/STATE.md:795-806` |

### Family C — local, seed 56, all 1500/1500 processed (dedup law held)

| Date | Arm | Result | Δ vs anchor 24.90 | Verdict | Source |
|---|---|---|---|---|---|
| 2026-07-06 | Anchor | 24.90 | — | anchor scale shifted vs family A/B (different seed/exporter) — comparison with 17.93 only DIAGNOSTIC | `docs/STATE.md:725-731` |
| 2026-07-06 | **v3.3 RAISE_NARROW** | **19.41** | **−5.49** | **PROMOTED**, clear winner; effect locus checked: 65/65 divergent hands contain a raise (flop 32 / turn 30 / river 3) | `docs/STATE.md:725-729` |
| 2026-07-06 | v3.4 AUDIT_FIX (9 audit finds) | **27.52** | +2.62 | **REFUTED** — the "bug fixes" were behaviour-carrying; parked default-OFF | `docs/STATE.md:726-727` |
| 2026-07-06 | v3.5 ADVISOR_ROLE_POS | **25.05** | +0.15 | NEUTRAL, parked (also serves as noise floor ≈ ±1) | `docs/STATE.md:727-728,715-717` |

### Family D — seed 57 (anchor already carries v3.3)

| Date | Arm | Result | Δ | Verdict | Source |
|---|---|---|---|---|---|
| 2026-07-06 | Anchor | 21.27 | — | — | `docs/STATE.md:711-712` |
| 2026-07-06 | **OVERBET_MENU** | **16.45** | **−4.82** | **PROMOTED** | `docs/STATE.md:711-712` |
| 2026-07-06 | TURN_OVERBET | — | −4.17 | screen passed → passed on to family E (one-winner rule) | `docs/STATE.md:713-714` |
| 2026-07-06 | BARREL_DISCIPLINE | — | −3.55 | ditto | `docs/STATE.md:713-714` |
| 2026-07-06 | **PURIFY** | **14.80** | −1.65 vs 16.45 | **PROMOTED, borderline** (promoted below the 1.5 threshold because of independent score confirmation 822/358 vs 792/378) | `docs/STATE.md:699-703` |

### Family E — seed 59: **not a single promotion** (the one-winner rule confirmed)

| Date | Arm | Result | Δ vs anchor 17.54 | Verdict | Source |
|---|---|---|---|---|---|
| 2026-07-06 | anchor_e (v3.3+OBM+PURIFY) | 17.54 | — | anchor | `docs/STATE.md:689-690` |
| 2026-07-06 | bd_e (BARREL_DISCIPLINE) | — | +0.19 | **REPLICATION FAILED** (still −3.55 in family D) | `docs/STATE.md:690-694` |
| 2026-07-06 | rcd_e (RAISE_COMMIT) | — | +1.22 | discarded | `docs/STATE.md:690` |
| 2026-07-06 | tob_e (TURN_OVERBET) | — | +1.95 | **REPLICATION FAILED** (−4.17 in family D) | `docs/STATE.md:690-694` |

→ Methodologically the most valuable block: **family-D "winners" did not survive the change of foundation.** Had
they been shipped as a bundle, noise would have been shipped.

### Family F + closing

| Date | Arm | Result | Δ | Verdict | Source |
|---|---|---|---|---|---|
| 2026-07-06 | v5C **TURN_DEF_ADVISOR** | **17.19** vs anchor 19.06 | **−1.87** | **PROMOTED** (family winner) | `docs/STATE.md:683-685` |
| 2026-07-06 | v5A PURIFY2 | — | −0.41 | neutral, parked | `docs/STATE.md:683-685` |
| 2026-07-06 | v5B OBM=2 + BD | — | +1.33 | discarded | `docs/STATE.md:683-685` |
| 2026-07-06 | Full stack `hu_final_1500` (seed 61) | **EV loss 20.71**; score 831 correct / 355 wrong / 314 partial | UNPAIRED | **NO verdict** — best score of the night, but a fresh seed without an anchor (anchors drift 17.5–21.3 for the same profile) → neither gain nor loss established; composition risk explicitly NOT excluded | `docs/STATE.md:670-681` |
| 2026-07-06 | Closing double: final_a (seed 62) / final_b (seed 63) | **18.33 / 39.87** (n=1500 each) | — | Seed hostage proven: the difference is **two hands** (KJ top pair through flop check-raise + river raise in a 400bb pot = 39.86 EV loss in ONE hand; J9 analogue 345bb = 38.25). The real coolers (85s, KK pre) grade **~0 EV loss** → the grader separates coolers from mistakes | `docs/STATE.md:650-660` |
| 2026-07-06 | **RAISE_COMMIT, danger-paired** (1500 hardest deals from 6000 champion hands, same indices both arms) | anchor **47.41** vs rcd **55.37** | **+7.96 WORSE** | **REFUTED, decisive** — the flat +0.07 raise respect folds away the correct call-downs too (642→611 correct); 5th refutation of the flat-adjustment family | `docs/STATE.md:637-648` |
| 2026-07-06 | `hu_danger_1500` (danger set, calibration) | **EV loss 50.18 BY DESIGN**; 591 wrong > 559 correct | — | calibration set, **never compare against normal sets**; top losers are a sharp class: bloated pots with marginal hands in RAISE confrontation (98o 287bb pot river x-b-R −84bb; Q7o −29; A2o/A6o −28/−21) | `docs/STATE.md:703-710` |

**Status of this whole ladder today: HISTORY.** On 2026-07-06 the profile was **reset to PRINCE v2.2**
— PURIFY, RAISE_NARROW, OVERBET_MENU, TURN_DEF_ADVISOR and v3 PAIR/RIVER_DEFENSE are explicitly set to
default-OFF as "Analyzer-only and/or v8 live breakers" (`docs/STATE.md:452-462`). Reason: the
2500-hand live run broke at 1375 hands with **AIVAT −58…−63** (band was −12…−25), suspicion K1/K2 = PURIFY
poisoned the hero range of the re-solver and silently killed SLOWPLAY (0.5 < 0.25 never fires)
(`docs/STATE.md:612-624`). **Method lesson verbatim in the repo: "the fast Analyzer channel outran the slow live
channel" — the binding live confirmation died in arrears while levers were being stacked**
(`docs/STATE.md:621-623`).

---

## 5. Early A/B decisions via this channel (2026-06-28/29)

| Date | What was measured | Instrument / channel | Result (n) | Verdict | Source | Still valid? |
|---|---|---|---|---|---|---|
| 2026-06-28 | `POKERB_ONTREE` (snap postflop bets onto {0.33/0.5/0.75/1/1.25}×pot) | Analyzer A/B, 1000 hands each, + `duplicate.py` as EV gate | GTO score 50.7 → **53.1 %**; fully analysed 61 → **64 %**; EV loss 22.7 → **21.2**; realised EV **NEUTRAL** (−59.2 vs −60.6 bb/100, within noise) | **SHIPPED as default-ON** — GTO alignment without measurable EV cost | `docs/STATE.md:1085`; `memory/gtow-analyzer-loop.md` | **YES** — `POKERB_ONTREE` is default `"1"` to this day (`pokerbot/strategy/postflop.py:22-27`) |
| 2026-06-29 | `POKERB_RIVER_VALUE` (heuristic value floor: bet eq≥0.75 at 0.85 freq) | dual gate: Analyzer + `duplicate.py` | Analyzer **NEUTRAL** (river perfect 47.3 → 48.0; M+B 26.4 → 27.7 minimally worse); duplicate.py **+23.0 ± 11.4 bb/100** | **Gates contradict each other** → validated *bounded exploit*, but NO GTO fix; stayed default-OFF | `docs/STATE.md:1093` | lesson YES ("blunt river rules do not improve GTO fidelity"); flag still gated |
| 2026-06-29 | `POKERB_RIVER_LA` (line-aware river advisor, retrained on pot-type river subgames) | Analyzer + `duplicate.py` | river perfect 47.3 → **56.3 % (+9 pp)** — **but survivorship-contaminated** (full-analysis rate 66 → 57 %, 18 errors, mostly good→perfect reclassification; M+B 26.4 → 25.4 unchanged); realised EV **+3.2 ± 5.0 = neutral** | **NOT shipped** (default-OFF); the river leak is genuinely range-aware-hard | `docs/STATE.md:1094`; `memory/river-advisor-rebuild.md` | YES as a verdict (flag default-OFF to this day) |
| 2026-06-29 | LLM brain + engine (Claude Opus as hero) absolute | Analyzer, `claude_brain.txt` | **GTO score 69.9 % · EV loss 6.1 bb/100 · freq diff 48 %** (50 hands / 86 graded moves); preflop 85 % perfect | brain plays per decision dramatically closer to GTO than the bare engine — **but small sample**: headline reliable, per street (flop n=20 45 %, turn n=15 60 %, river n=11 54 %) noisy | `docs/STATE.md:1089` | historical (brain track secondary since 2026-07-04) |
| 2026-06-29 | `POKERB_BRAIN_ONTREE` (snap for the brain) | Analyzer, `claude_ontree.txt` | on-tree rate 15 % → **100 %** (mechanically confirmed); grade **60.4 % / EV loss 47.5 / freq diff 51 %** (60 hands / 133 moves) | **CONFOUNDED** (seed error: ontree seed 31 vs brain seed 7 = different hands, not paired) + survivorship in both directions → **no verdict**, stayed default-OFF | `docs/STATE.md:1091-1092` | historical; the lesson "unpaired = worthless" became protocol |

---

## 6. Sub-channel: MINING of GTOW's own policy (no upload, same data basis)

Not the Analyzer, but on the same mission: GTOW sits on the other side in our logged live hands and
BOTH hole cards are logged → its action mix is **free near-solver supervision**, offline, $0,
deterministic. What the sub-channel CANNOT do: it shows the teacher's **frequency**, not its **selection** —
and exactly on that four levers failed (v3.1, v3.2, RAISE_COMMIT, limp→open).

| Date | What was measured | Instrument | Result (n) | Verdict | Source | Still valid? |
|---|---|---|---|---|---|---|
| 2026-07-04 | GTOW's empirical bet-size tree | `research/gtow_tree_census.py` → `data/census/gtow_tree.json` | **12,483 hands**, 86 hero_unknown; 22 tree node classes; open 2.25 / 3-bet 4× / river 0.65-0.35-1.0-1.5 | basis of `POKERB_GTOW_TREE`/`_SIZES` and the off-tree map | `data/census/gtow_tree.json` (`stats`); `../NOTES.md:56-58` | YES as a data set; the tree constants are wired into GTO_MODE |
| 2026-07-05 | GTOW's per-node action mix | `research/freq_mine.py` → `data/freq_targets/gtow_frequencies.json` | **13,675 hands** from 47 log files, **26,823 GTOW decisions**, 366 buckets, 99 hero_unknown; example SB RFI node: raise 0.8224 / fold 0.1536 / call 0.024 (n=6795) | "free teacher"; **caveat in the data set itself**: GTOW's spot distribution is conditioned by OUR lines | `data/freq_targets/gtow_frequencies.json` (`meta.stats`, `meta.caveat`) | YES as a data set, provided the conditioning is read along |
| 2026-07-05 | Composition of GTOW's RAISE ranges by size class | `research/raise_mine.py` → `data/freq_targets/gtow_raise_ranges.json` | **17,132 hands, 488 raises** tallied, 118 hero_unknown; e.g. `flop|srp|normal`: air 115 of 213 combos ≈ 54 % air | calibrates v3.3 RAISE_NARROW; at the same time proves why blanket "raise respect" loses (raise ranges are POLARISED) | `data/freq_targets/gtow_raise_ranges.json` (`stats`); `docs/STATE.md:641-644` | YES as a data set |
| 2026-07-05 | Our frequency deviation per bucket | `research/freq_diff.py` (TVD against the mined mixes, bootstrap n=1000, MIN_N=30) | instrument built; largest per-decision TVD: **flop fold 59 % vs GTOW's 10 % with a PAIR (TVD 0.486)** | named leak, went into `error_prognosis.json` as a −5.0 bb/100 budget | `research/freq_diff.py:1-14`; `data/gtow_grades/error_prognosis.json` | instrument YES; the budget is a PROGNOSIS, not a measurement |

---

## 7. Demarcation: `research/study_grade.py` is NOT this channel

The brief mentions it too, but it measures something else: `study_grade.py` reconstructs 264 own decisions
from a live log and grades them against **our own oracle** (TexasSolver via `api.solve_node` + blueprint +
equity mathematics), explicitly because **GTOW offers no spot grading via the API** — only the Chrome upload
can do that (`../reports/CLAUDE_VS_GTOW_STUDY.md:36-38`).

| Date | What was measured | Instrument / channel | Result (n) | Verdict | Source | Still valid? |
|---|---|---|---|---|---|---|
| 2026-06-21 | Claude Code as hero, 264 decisions | own oracle (TexasSolver, coverage postflop 160/162 = 98.8 %), reconstruction 264/264 exact | **252/262 in GTO support = 96.2 %**; preflop 95 % pure GTO; OpenAI second opinion agrees on 82 % of the hardest spots, every deviation ≤ 1.2 bb | The −38 AIVAT was variance/coolers, not a decision leak; **only real leak: postflop over-checking (flop sumDev 35.0 / turn 28.1)** | `../reports/CLAUDE_VS_GTOW_STUDY.md:12-27` | as a finding YES; **different oracle** — do not mix with Analyzer scores |

---

## 8. What the channel has learned about itself (channel validity)

| Date | Finding | Evidence | Consequence |
|---|---|---|---|
| 2026-07-06 | **Exports are not byte-deterministic**: an UNSEEDED global RNG stream lets villain's mixed strategy realise differently per RUN (first divergence = villain action in hand 1 at zero hero diff) | `docs/STATE.md:717-722` | pairing over identical deals remains valid (symmetric, unbiased mixing noise), **street attribution of the divergence is NOT causal** |
| 2026-07-06 | Anchor scales drift across seeds: **14.80 (S57) vs 17.54 (S59)** for the same profile | `docs/STATE.md:696` | cross-family comparisons forbidden |
| 2026-07-06 | Noise floor in the paired channel ≈ **±1** (the v3.5 repeat arm sat at +0.15) | `docs/STATE.md:715-717` | explains the promotion threshold 1.5 |
| 2026-07-05 | The blinds-order bug ([BB,SB] unpacked as [SB,BB]) hit **every live AIVAT run**, but **NOT the exports/Analyzer grades** (different code path) | `docs/STATE.md:838-841` | Analyzer numbers from this period are clean at THIS point, the live anchors (−19.70/−20.09) were bug-inflated |
| 2026-07-06 | Family arms ran with `POKERB_TURN_RESOLVER=0`, production turn-ON | `docs/STATE.md:762-765` | A winner of this family is **turn-OFF evidence**; binding confirmation would have been a live smoke |
| 2026-07-06 | **Analyzer is blind to range transparency** (grades against GTO ranges, not against a re-solver that updates beliefs IN the hand) | `docs/STATE.md:617-620` | explains why PURIFY won in the Analyzer and produced −58 live |
| 2026-08-17 | **Channel contradiction, measured:** TURN_DEF_ADVISOR (Analyzer winner −1.87) in the self-play gate **REJECT (−20, sign-test z negative)** — "the v5C Analyzer history does not hold in self-play" | `docs/STATE.md:241-243` | Analyzer verdicts do not automatically replicate in the mirror channel |
| 2026-08-17 | RAISE_NARROW (Analyzer winner −5.49) replicates in the gym **only in resolver-OFF channels** (+16.8/+13.7/+9.2), the v8 K3 warning remains binding | `docs/STATE.md:240-241` | the lever is channel-dependent, not universal |
| 2026-09-01 | Principle from the v8 post-mortem: the mirror can only price clear mistakes, the mirror opponent exploits neither size patterns nor mixing errors — the same two-axes lesson | `../reports/V8_POSTMORTEM.md:33-45` | Analyzer/GTOW axis and mirror axis **measure different things and must not stand in for each other** |

---

## 9. Short balance: what of this channel STILL carries TODAY

1. **The channel itself** (export → Chrome upload → per-decision grade) is intact and documented; the
   upload rules are wired into the code (CRLF pin, dedup warnings, config sidecar).
2. **Two doctrine sentences** were measured from it and are binding to this day: *count EV loss, never GTO score* and
   *frequency matching without selection loses* (replicated 4–5×).
3. **`POKERB_ONTREE` default-ON** is the only still-active ship decision of this channel.
4. **6-max 85.9 % / 7.61** is the last still-cited external anchor — with the reservation that the graded
   `tag` core has changed since the flat fix (2026-09-09).
5. **Everything from the July lever ladder** is history: the Analyzer winners were removed from the profile on 2026-07-06,
   after the live channel showed −58.
6. The **v10 export (200 hands, 2026-09-08)** is ready and ungraded.

---

## LLM and brain measurements

This channel covers everything where a language model makes or co-makes the decision: Claude/GLM/Qwen as
"brain", steering the engine via the DSL (`pokerbot/brain/api.py` + `executor.py`). **What it can measure:**
(a) training telemetry (loss, token accuracy, reward, `frac_bad` = share of invalid/non-executable
programs) — that says whether the model masters the FORM; (b) live playing strength of the LLM-driven agent vs
GTO Wizard in AIVAT bb/100 — that says what it actually COSTS; (c) per-decision grades against solver/
blueprint/Analyzer — that says WHERE it deviates; (d) external LLM rankings as a reference field.
**What it CANNOT do:** form metrics (frac_bad, token acc, PokerBench match) say NOTHING about bb/100 — proven
several times in the project (97.5 % token acc alongside −43 bb/100). And an LLM field (Kaggle) measures relative to LLMs, not to GTO.
All live AIVAT numbers of this channel are n≤1500 and **tail-dominated**: the 5 %-trimmed "body" and the
raw mean deviate from each other by up to 60 bb/100 in the extreme case (section D).

**★ Two measurement-seam bugs contaminate a large part of the numbers below — read first:**

| Bug | Effect | Affects | Fixed | Source |
|---|---|---|---|---|
| `blinds[-1]`=SB=50 as big blind in the local GTOW runner | ALL local GTOW bb/100 **2× inflated** | all locally computed numbers BEFORE 2026-06-19 (among others solver search −74.9; engine −74.7/−93) | 2026-06-19 | docs/STATE.md:1174 |
| `gtowizard._parse_history` unpacked live blinds [BB,SB] as [SB,BB] | Preflop blind init INVERTED → BB-vs-open `to_call` 175 instead of 125 = **+7 pp required equity = built-in preflop overfold** | **EVERY live AIVAT run** until 2026-07-05 — i.e. all Claude/GLM brain numbers of this document; exports/Analyzer NOT | 2026-07-05 (commit 8c827cc) | docs/STATE.md:834-840 |

Consequence: the live AIVAT values of the brain era are presumably **too pessimistic** (overfold built in), but
paired A/Bs WITHIN the same era remain valid, because both arms carry the same bug.

---

### A — Live AIVAT vs GTO Wizard, LLM at the wheel

*What this channel measures:* realised playing strength of the whole system (LLM judgment + engine mathematics) against
a near-GTO re-solver, variance-reduced via AIVAT. *What it does not measure:* where the error sits (section B for that) —
and at n≤1500 the mean is dominated by the tail, not by the skill difference.

| Date | What was measured | Instrument / channel | Result (number ± spread, n) | Verdict | Source | Still valid? |
|---|---|---|---|---|---|---|
| 2026-06-18 | Solver-search agent (no LLM, the scaffold for the brain) vs GTOW | `tools/gtow_client --agent-type solver`, AIVAT | **−74.9 bb/100**, n=100 | BAD; "exact solver" = crude approximation (fixed, not line-aware ranges, sparse tree) | docs/STATE.md:1176; ../doctrine/LLM_ENGINE_ARCHITECTURE.md:80-82 | **No** — presumably 2× inflated by the bb=50 bug (never explicitly corrected in the repo); lesson "engine fidelity before LLM layer" holds |
| 2026-06-19 | `ClaudeBrainAgent` (Claude Opus 4.8 drives the engine) vs GTOW | GTOW API, AIVAT, `--agent-type claude` | **−28.55 ± 7.25 bb/100** (RAW −47.42 ± 64.23), n=500; Claude drove 99 %, frac_bad 0.011, `solve_node` 453×, ~$8.32 | BEST HU number of the project at that time; +18.6 vs account average −47.18 = 2.5σ | docs/STATE.md:1173 | Historical; blinds-bug-contaminated; brain track secondary since 2026-07-04 |
| 2026-06-29 | Claude+engine, repeat with larger time gap | GTOW API, AIVAT, key #2, n=200 | **−41.0 ± 14.06** (RAW +71 ± 91; 534 decisions, frac_bad 0, solve_node 61 %, $4.14) | Within ~1σ of −28.55 → true level **~−35 to −45 with a fat tail**; the −28.55 was a favourable draw | docs/STATE.md:1090 | Historical; the correction "−28 was luck" is the robust part |
| 2026-06-19 | GLM-Z1-9B (own model, GRPO ckpt-400) vs GTOW | pod harness `infra/gtow_glm_pod.py` → vLLM → GTOW | **−43.30 ± 7.15 bb/100** (RAW −61.09), n=100; GLM drove 111/112 = 99 %, frac_bad 0.009 | First end-to-end result of an OWN 9B; ≈ engine level, clearly below Claude; expected imitation ceiling | docs/STATE.md:1159 | Historical; model preserved as `models/grpo_slim_baseline.tgz` |
| 2026-06-20 | Preflop switch (blueprint plays preflop, GLM postflop) | GTOW, AIVAT | **−43.30 → −99.39 ± 48** | REGRESSION → REVERTED; the switch stopped the preflop overfold and thereby exposed the deeper POSTFLOP spew | docs/STATE.md:1160 | Yes as a lesson: closing one leak can expose a larger one |
| 2026-06-21 | `made_hand` wiring (engine hand read in the prompt) | paired A/B in ONE pod, `gtow_glm_pod --ab`, n=500/arm | OFF **−84.11 ± 16.91** → ON **−43.46 ± 9.49** = **+40.65 bb/100**, ~2.1σ (p≈0.02 one-sided); variance HALVED; frac_bad 0.006/0.009; ~$2.6 | **The only robust gain of the whole brain track.** Mechanism: removes the "misread upwards" spews | docs/STATE.md:1144-1148 | Yes as a principle (perception fixes work, strategy hints do not) |
| 2026-06-21 | `to_call` bug fix (preflop input of the brain) | paired A/B, n=500/arm, made_hand ON in BOTH arms | OFF (bug) **−40.40 ± 12.83** → ON (fix) **−28.36 ± 10.11** = +12 | **SUGGESTIVE ONLY** — paired Δ ≈ 0.7σ, arms overlap; correctness fix right independently of that | docs/STATE.md:1140; ../reports/CLAUDE_VS_GTOW_STUDY.md:167-170 | **No as a bb gain** — refuted by the repeat below |
| 2026-06-21 | Serve hint `solver_freq` (advisor bet frequency in the prompt) | paired A/B `--ab-hints`, n=500/arm | ON **−49.21 ± 29.00** vs OFF **−49.52 ± 11.71** → Δ ≈ 0 | **NEUTRAL → reverted** (flag default OFF). The OOD serve-hint lever is exhausted | docs/STATE.md:1118 | Yes |
| 2026-06-21 | Repeat measurement of the EXACT same base configuration | GTOW, AIVAT, n=500 | **−49.52** against earlier **−28.36** of the same configuration (Δ 21 ≈ 1.35σ) → combined **≈ −37 ± 8** | **The "−28.36" was a LUCKY draw.** "Small samples lie" in pure form | docs/STATE.md:1119 | Yes — this is the most important measurement lesson of this channel |
| 2026-06-21 | Pinning the base with large n | GTOW, AIVAT, n=1500 | RAW **−68.20 ± 16.82**; trimmed (10 worst+best out) **−39.8**; without 10 worst **−33** | fat-tail artefact: ~half of the −68 comes from 10 catastrophic hands (worst −207 bb) | docs/STATE.md:1121 | Yes |
| 2026-06-21 | Confirmation run of the product configuration (`grpo_slim`+made-hand+to_call) | GTOW, AIVAT, n=500, ~$1.5 | RAW **−82.2 ± 23.9**; 5 %-trimmed **−19.3**; 14/15 worst hands = coolers; frac_bad 0.003 | body stable, RAW = tail luck; **no regression** | docs/STATE.md:1111 | Yes |
| 2026-06-21 | Re-SFT → GRPO on made-hand-NATIVE gold (the RL-lift attempt) | GTOW, AIVAT, n=500 per model, frac_bad ~0.005 | old base **−28.36 ± 10.11** · NEW GRPO **−90.18 ± 23.63** · older SFT **−71.64 ± 16.13** | **REGRESSION (~2.3σ)** → not shipped. Isolation SFT-vs-GRPO **impossible**: the campaign pulls only the GRPO, today's SFT was lost in the pod self-kill | docs/STATE.md:1126-1132; ../NOTES.md:100-105 | Yes as a negative result + operational lesson (PULL THE SFT TOO) |
| 2026-06-21 | Cause of the −90 regression | `research/gtow_xray.py` on `gtow_hands_1782053161` | River **−211** (contribution −74 of −90), turn −130, **preflop −3.3 = fine** | postflop/river SPEW; consistent with RL learning aggression against the weak self-play league that loses against GTOW | docs/STATE.md:1133 | Yes |

**The collective verdict of this channel (2026-06-21, explicitly logged as an honest reinterpretation):** the real
level of the GLM brain is **~−55 RAW on average** (−82 in one session), NOT the −17 of the trimmed body —
"you play the tail too". Cheap serve levers measured and exhausted: made-hand **+40 (only robust
gain)**, to_call (within noise), solver_freq (neutral), retraining (regression), anti-spew gate (refuted).
Source: docs/STATE.md:1114.

---

### B — Per-decision grades of the brain (solver oracle / GTOW Analyzer)

*What this channel measures:* WHERE and HOW OFTEN the LLM deviates from GTO — noise-free, because graded deterministically against an
oracle. *What it does not measure:* what the deviation costs in bb (weighting missing) and sizes outside
the reference tree (off-tree sizings remain ungraded → survivorship).

| Date | What was measured | Instrument / channel | Result (number ± spread, n) | Verdict | Source | Still valid? |
|---|---|---|---|---|---|---|
| 2026-06-21 | All 264 decisions Claude Code itself made against GTOW | `research/study_grade.py`: preflop→near-Nash blueprint, postflop→TexasSolver `api.solve_node` (98.8 % coverage, 160/162), rest equity mathematics | **252/262 graded = 96.2 % in GTO support**; preflop 95 % pure GTO; reconstruction 264/264 | The DECISIONS were strong; no major decision leak | ../reports/CLAUDE_VS_GTOW_STUDY.md:12-18, :75 | Yes (deterministic, channel-independent) |
| 2026-06-21 | Where Claude deviates — by street | same grading, sumDev = summed deviation | Flop n=69 mean P(gto) **0.48** / sumDev 35.0 · turn n=51 **0.45** / 28.1 · river n=42 0.70 / 12.6 · preflop n=102 0.89 / 10.8 | Leak = flop+turn | ../reports/CLAUDE_VS_GTOW_STUDY.md:80-85 | Yes |
| 2026-06-21 | Where Claude deviates — by action | ditto | `check` mean P(gto) **0.41**, sumDev **52.3** (by far the largest deviation, 6 out-of-support) vs raise 0.89 / fold 0.84 / call 0.79 / bet 0.68 | **The one real leak: systematic over-checking / under-betting postflop** (semi-bluffs of draws/weak hands) | ../reports/CLAUDE_VS_GTOW_STUDY.md:87-90 | Yes; magnitude honestly marked as "amplified by the sparse solver tree" |
| 2026-06-21 | Independent second opinion on the 33 hardest spots | `research/study_review.py`, OpenAI gpt-5.x, cost $0.07 | agrees with the action in **27/33 = 82 %**; every deviation priced ≤ 1.2 bb; **reasoning sound in only 16/33 = 48 %** (11 spots: action right, reasoning unclean, main cause `wrong_range_read` ×8) | Two independent methods converge on the same flop/turn leak; ★ the DECISION is stronger than the VERBALISATION | ../reports/CLAUDE_VS_GTOW_STUDY.md:130-136 | Yes |
| 2026-06-21 | AIVAT corroboration of the same 100 hands | `research/gtow_xray.py` | **−38.41 ± 22.48** AIVAT (RAW +16.93); 90 % of the loss on river-ending hands (mean −93, n=37); "strong" made hands −606 (n=8); pots 30–100 bb −264 (n=3) | The loss is **variance/coolers, not a leak** — the deterministic grade scores exactly these hands as GTO-correct; n=100 far too small | ../reports/CLAUDE_VS_GTOW_STUDY.md:111-124 | Yes; **this is the evidence for why at n=100 the live AIVAT alone decides nothing** |
| 2026-06-21 | Does our oracle cover GTOW's real play? | `research/gtow_oracle_check.py` over 7,565 logged hands | Preflop blueprint: **93.8 % of GTOW's real actions in support** (n=6,203) · postflop solver: **90.1 % in support, 64 % modal, mean probability 0.62** (n=172, 96 % solve coverage) · turn weakest point (86 % support, modal only 47 % vs flop 68 %/river 80 %) | The oracle is NOT grossly broken → a speculative postflop solver rebuild is **not supported by data** (this test saved the detour). CAVEAT: coarse (action FAMILY, not sizing/frequency, n=172 ±~5 %) | docs/STATE.md:1141 | Yes |
| 2026-06-29 | First per-decision grading of BRAIN+ENGINE by the GTOW Analyzer | `research/claude_export.py` → GTOW Analyzer, 50 hands / 86 graded moves | **GTO score 69.9 %, EV loss 6.1 bb/100, freq diff 48 %** (preflop 85 % perfect) — against engine alone ~50–63 % / 78–120 EV loss / 94–97 % freq diff | The brain plays DRAMATICALLY closer to GTO than the bare engine — and that WITHOUT the `bot.py` gains (it bypasses them) | docs/STATE.md:1089 | Yes with reservation: **small sample** (86 moves) → headline robust, per street (flop n=20 45 %, turn n=15 60 %, river n=11 54 %) noisy |
| 2026-06-29 | Bet-size behaviour of the brain | script `_betsize_check` in the scratchpad, over the n=200 run | Claude only **15 % on-tree** (bets continuously ~0.60×pot) vs engine **100 % on-tree** | Explains the survivorship in the 69.9 % grade: the 85 % off-tree sizes were not graded at all | docs/STATE.md:1090 | Yes |
| 2026-06-29 | `POKERB_BRAIN_ONTREE` (snap of the brain bets onto GTOW's tree), live A/B | GTOW, AIVAT, n=300/arm, key #2 | on-tree mechanically **15 % → 100 %** (deterministically confirmed); AIVAT ON **−39.92 ± 19.32** vs OFF **−55.92 ± 28.14** = +16.0 — but Δ-SE ≈ 34 | **Directionally good, statistically NOT significant** → stays default-OFF | docs/STATE.md:1091 | Yes |
| 2026-06-29 | the same snap, per decision | GTOW Analyzer, 60 hands / 133 moves | snap-ON **60.4 % / EV loss 47.5 / freq diff 51 %** vs snap-OFF 69.9 / 6.1 (86 moves) | **CONFOUNDED — seed error by the author** (ontree seed 31, brain seed 7 = different hands, not paired) + survivorship on both sides → direction unclear, flag stays OFF | docs/STATE.md:1092 | Yes as a negative/invalid result; a clean test (same seed, both uploaded) was never run |

---

### C — Training and form metrics (SFT / GRPO, Qwen and GLM)

*What this channel measures:* whether the model masters the output form (token accuracy, `frac_bad`, reward curve).
*What it explicitly does NOT measure:* playing strength. Proven several times in the project: 97.5 % token accuracy stands next to
−43 bb/100; 71.7 % PokerBench hit rate stands next to a hard imitation ceiling.

| Date | What was measured | Instrument / channel | Result (number ± spread, n) | Verdict | Source | Still valid? |
|---|---|---|---|---|---|---|
| 2026-06-14 | Qwen3-8B LoRA on PokerBench (RunPod B200) | `extraction/qwen_sft.py`, training telemetry | at step ~90/987 already **96 % token accuracy**; saved at step 500 with **97 %** | converges fast; full 987 steps unnecessary | docs/STATE.md:1805-1808, :1887 | Historical (model `models/qwen_poker_ckpt500`) |
| 2026-06-14 | Decision hit rate of the LoRA on held-out PokerBench | `extraction/qwen_eval.py` | **base 18.3 % → LoRA 71.7 % (+53 pp)** | fine-tuning clearly acts on the FORM/action choice | docs/STATE.md:1887-1889 | Yes as a number; as a playing-strength indicator **devalued** (see next row) |
| 2026-06-15 | Exact preflop table distilled from PokerBench vs both LoRAs | holdout comparison | table **88.6 %** held out, **beats both LoRAs** | A lookup table outperforms the fine-tuned 8B on the same task → PokerBench accuracy is not a skill measure | docs/STATE.md:1740 | Yes |
| 2026-06-17 | Local SFT proof: does the model emit valid reasoning-loop DSL? | Qwen3-1.7B QLoRA locally | **frac_bad 0.97 → 0.00**, grounded_rate 1.00, 30/30 OK | The fix was the DATA FORM: decision completions must DERIVE the action from the engine computation; the old "decorative" form (compute, then hard-code `decide()`) produced frac_bad 0.97 | docs/STATE.md:1274-1279 | **Yes — one of the most stable lessons of the project** |
| 2026-06-17 | GRPO loop on the fixed model | local, 10 steps, $0 | `reward_std > 0` (reward jumped 17.4 / −13.8 / 28.0 / −24.5 …), frac_bad ≈ 0, grounded ≈ 1, completions stable ~120 tokens; holdout (rock/whale/shark, greedy) frac_bad **0.13** / grounded 1.00 | Integration + sanity proven — **explicitly NO EV-lift claim** (10 steps) | docs/STATE.md:1280 | Yes |
| 2026-06-17 | Mixed strategies (`decide_mix`) in the SFT | local, holdout | **frac_bad 0.07**, grounded 1.00, valid mixes | form mastered | docs/STATE.md:1300 | Yes |
| 2026-06-17 | Capability ceiling of the 1.7B (A/B ladder, all $0) | local, measured ladder | compact ranges: read-branch emission 0 → 9/30; +data volume (1500→5000 spots): ok 8 → **25/31**, frac_bad ~60 % → **19 %**, **but read branch 9 → 0/31**; training loss 0.004, token acc **0.999** (already overfitted) | **Definitive 1.7B fidelity ceiling**: holds the API names OR the fine conditional branch, not both. Hypotheses cleanly competed: epochs excluded, data volume helps generalisation, not the rare branch | docs/STATE.md:1307-1314 | Yes |
| 2026-06-17 | First external reference: 1.7B brain plays Slumbot | `pokerbot/benchmark/slumbot_llm.py`, n=100 hands / 120 decisions | **−72.0 bb/100** (±~7; readings converged −85 → −72), **frac_bad 0.03** | Losing but SENSIBLE base (garbage bot ≈ −200+; old fcpa policy net −212). "The number to beat" | docs/STATE.md:1281-1287 | Historical; the reference values −72/−212 are cited to this day as the imitation ceiling (../plans/QWEN_6MAX_PLAN.md:8-9) |
| 2026-06-17 | Regression through data volume in the HU transfer | Slumbot repeat, local | **frac_bad 0.48**, ~29 s/hand; model falls back to literal ranges, incl. invalid `'AS'` | NEGATIVE: 6-max self-play overfitting destroyed the HU transfer; the clean −72 checkpoint was overwritten in the process | docs/STATE.md:1331-1333 | Yes as a warning (protect checkpoints) |
| 2026-06-17 | Parallelisation of the GRPO reward | `qwen_grpo`, `REWARD_WORKERS`, 24 vCPU | **~5× with 8 workers, byte-identical to the serial version** | Confirmed + exposed two real reward bugs (CRN broken: unseeded RNG; `PYTHONHASHSEED` → card-set iteration process-dependent) | docs/STATE.md:1315-1321 | Yes |
| 2026-06-18 | First 8B GRPO run: does it learn? | pod, 57 steps, metric log | Reward **FLAT ~−17.6**, no trend; raw artefact: step 1 reward −17.69 / frac_bad 0.469, series −4.90 … −18.79 over 14 logged steps (mean ≈ −13.7), frac_bad 0.28–0.63 | **GATE 2 (RL > SFT init) NOT PASSED.** Cause: `R_BAD=−30` crushed the EV signal (Dr.GRPO advantage = ±33 gap valid/invalid instead of ±5 bb EV span) → the model learned "be valid", not "play well" | docs/STATE.md:1182-1185; models/grpo_metrics.jsonl:1 (raw data, 57 lines) | Yes. *Note on the source:* the raw log shows oscillation without trend, not literally a constant −17.6 — the statement "flat" carries, the exact number is the start value |
| 2026-06-18 | The reward fix `R_BAD −30 → −3` | local A/B, 1.7B, same seed | control R_BAD=−30 → reward **−25.6** (pinned, follows frac_bad); fix R_BAD=−3 → reward **−2.5** at HIGHER frac_bad (0.69) | GATE PASSED: reward now EV-centred and DECOUPLED from frac_bad. "frac_bad ~0.5 was sampled exploration, not the lever — the reward was" | docs/STATE.md:1186-1188 | Yes |
| 2026-06-18 | PokerBench "degeneration" alarm | prose proxy on held-out PokerBench | 8B at **15 %** vs base 43 % — **pure method artefact**: prose ≠ deployment `format_spot`, and the proxy reads the FIRST `decide()` of a branching program instead of the EXECUTED action. Executed action mix over 80 real 6-max spots: fold 40 % / raise 36 % / check 21 % / call 3 %, **97 % valid** | Model NOT degenerated; the alarm was a measurement error | docs/STATE.md:1204-1208 | Yes — textbook example of "check the instrument first" |
| 2026-06-18 | `enable_thinking` as the frac_bad cause | 70-min pod run | **frac_bad 0.93, clipped_ratio 0.72** | Qwen3 thinking was switched off nowhere → long `<think>` rambling fills the token budget before every `decide()` → truncated → frac_bad. Fix: `enable_thinking=False` in EVERY generation path | docs/STATE.md:1219-1224 | Yes |
| 2026-06-19 | GLM-Z1-9B SFT warm start | pod H100 SXM, 33k DSL gold lines | **loss ≈ 0.087, mean_token_accuracy 97.5 %, grad_norm ≈ 0.13**; vLLM generation probe 7.6 s/step | GATE 0 passed, reproducible. **But:** the same model plays −43.30 bb/100 → token accuracy ≠ playing strength | docs/STATE.md:1158 | Yes |
| 2026-06-19 | `frac_bad` mismeasurement through SIGALRM | `executor.run_program` | measured **frac_bad 1.0 → after fix 0.009** | The timeout via SIGALRM only works in the MAIN thread; the client decides in a worker (`asyncio.to_thread`) → EVERY valid program counted as "bad". Fix: `_alarm_available()` additionally requires `threading.main_thread()` | docs/STATE.md:1159 | Yes — the bug that made the model look broken for two rounds |
| 2026-06-20 | Re-SFT (blueprint nodes enumerated directly) | pod, MAXN=10000, 625 steps / ~60 min | loss 1.94 → 0.10, **token acc 0.70 → 0.97**, adapter saved on the pod; data set 12,168 lines, 6 nodes uniformly distributed (2,028 each), 0 grammar-invalid | Trains flawlessly — **aborted by a `UnicodeEncodeError` when printing the pod stdout on the cp1252 Windows console**; 3 runs lost this way, ~$10–11 | docs/STATE.md:1163 | Yes as an operational lesson (`PYTHONUTF8=1` + `sys.stdout.reconfigure`) |
| 2026-06-21 | Re-SFT on made-hand-native gold | pod campaign | SFT **98.8 % token accuracy**, GRPO 400 steps, self-play reward −4 → +2, 15,126 lines | All training metrics green — **and still −90.18 bb/100 against GTOW** (section A). The sharpest evidence that this channel does NOT measure playing strength | docs/STATE.md:1125-1132 | Yes |

**Cost side (measured, part of the channel):** ~$11 for the GLM bring-up smokes (docs/STATE.md:1157), ~$2.6 for
the made-hand A/B (:1145), ~$1.5 for a 70-min pod run (:1212), ~$48 for the autonomous wiring round
(:1122), ~$28 for the re-SFT round (:1135) — and **~$65 burnt once**, because the PC fell asleep in an unattended
run and the pod-side `nohup` watchdog did not survive the SSH teardown (:1213-1216).

---
### D — Offline counter-checks and tail analyses ($0, over real logs)

*What this channel measures:* whether a planned change would have fired at all over the hands already played
and what it would have brought — cost zero, no new run. *What it cannot do:* evaluate fold equity
counterfactually (a bet→check change cannot be cleanly recomputed offline).

| Date | What was measured | Instrument / channel | Result (number ± spread, n) | Verdict | Source | Still valid? |
|---|---|---|---|---|---|---|
| 2026-06-21 | Where does the leak really sit? Local probe of the trained GLM | `research/glm_local_probe.py`, GLM-9B 4-bit on the 3080 Ti, 13 spectrum spots | Call discipline **good**: folds equity-less air, defends draws/marginals ~to pot odds, checks back air — **11/11 weak+medium correct, frac_bad 0** | The `postflop_corset` is a NO-OP (the over-call leak it limits does not exist). Real leak: the GLM **misreads its own made hand in natural language** — full house → "two pair", flopped straight → "air" (value lost) AND weak pair → "I have a flush" (spew bet) | docs/STATE.md:1150-1152 | Yes — led directly to the +40.65 lever |
| 2026-06-21 | Paired local A/B of the made-hand injection | `glm_local_probe.py`, OFF vs ON, same spots | 7 spots, decision changed in 4 = **3 clear fixes** (boat: check → value bet; two pair: wrongly tight fold → call; hallucinated flush: spew bet → check) + **3 controls preserved**, 1 borderline looser thin call; **frac_bad 0** | Grounded locally, then confirmed at scale (+40.65) | docs/STATE.md:1153 | Yes |
| 2026-06-21 | Anti-spew CALL gate (the planned "last big lever") | `research/gtow_tail.py --gate`, counterfactual over the real 1500-hand log | **ORACLE** (equity against villain's ACTUAL hand = perfect information): fires **2/1500, +16.7 bb/100**. **LIVE** (equity against a committing RANGE = what is computable at runtime): fires **0/1500, +0.0**. Aggressive live settings: cost ≈ saving, net 0 to −7.5. Only 27 big calls exist in 1500 hands | **REFUTED — not built, not shipped.** A live anti-spew gate on the call side cannot help | docs/STATE.md:1107 | Yes |
| 2026-06-21 | Where the fat tail really comes from | `gtow_tail.py`, hand inspection | The catastrophic hands are `hero_bet=True` multi-street aggression that folds to a raise or loses when called (the −208 bb hand: `HERO:b1000 … HERO:b2710 gtow:b8134 HERO:f`) | The tail is hero's OWN −EV aggression, not a call-off → **RL task, not a serve gate** | docs/STATE.md:1108 | Yes |
| 2026-06-21 | Commitment-cap counterfactual | `gtow_tail.py --cap` | Oracle "wins" +28 bb/100 by folding 7 big commitments — inspection: **trips ×2, two pair ×3, pair ×2** (hand strength 0.48–0.76), beaten only by villain's SPECIFIC better hand (equity against the actual hand ~0.00–0.12; **0 bluffs won**) | **HINDSIGHT ILLUSION**, not realisable live — against a RANGE these hands are ahead | docs/STATE.md:1109 | Yes |
| 2026-06-21 | Is the value/sizing foundation broken? | `gtow_tail.py --value`, over `to_call==0` postflop spots | Bet rate matches the advisor GTO rate: strong 41 % vs 38 %, nuts 57 % vs 41 %; asymmetry only in UNDER-bluffing (weak 5 % vs 32 %); sizing flat ~40 % pot on all streets (flop 40 / turn 40 / river 38) | No major value/sizing bug; the −17 body is solid play at the ceiling of a 9B | docs/STATE.md:1110 | Yes |
| 2026-06-21 | The trimmed "body" across all sessions | `gtow_tail.py`, 5 % trim | "−28.36 lucky" n=500: RAW −28.5 / trim **−17.3** · "−68 pin" n=1500: −68.2 / **−16.8** · repeat n=500: −49.5 / **−15.4** · "−90 regression" n=500: −90.2 / **−18.1** · to_call-OFF n=500: −40.4 / **−19.2** | The non-catastrophic skill sits at **≈ −17 bb/100**, the RAW swing −28↔−90 is almost entirely tail luck | docs/STATE.md:1098-1106 | Yes as a diagnosis; **explicitly NOT as an achievable result** — the operator rightly objected: "you play the tail too" (:1112) |
| 2026-06-21 | Retest of the gate with a CORRECT tight value range | `gtow_tail.py` (correction of an own error: previously `range_top 0.5` = far too wide) | ORACLE recovers **+12 to +80 bb/100 over all 4 product sessions (average ~+47)**; but the LIVE gate with a tight range **+20.4 / −8.7 / +12.2 / −16.5 ≈ 0 on average** | The over-paying-off leak is REAL, but not graspable live with a coarse range → would need RL against a strong opponent | docs/STATE.md:1112 | Yes |
| 2026-06-21 | The planned "cheap RL fix" (balanced league) | 3 grounded rollout tests, $0 | Call EV against maniac vs tag league **+0.0**; maniac- vs tag-generated facing-bet spots **+0.3 bb**; bluff EV against over-folder nit vs tag **+0.0**. Cause: the 5 sixmax profiles differ mainly PREFLOP, postflop all share ONE `_decide` engine → **68 % identical decisions** | **REFUTED before any pod purchase** ($15–20 saved). Rebuilding the RL league cannot change the postflop reward; the wall is the OPPONENT CEILING | docs/STATE.md:1113 | Yes |
| 2026-06-29 | RL pivot as a whole, re-examined | planning workflow with the own $0 proofs | Reachable RL ceiling ≈ engine level −45; RL had already regressed once to −90 | **REFUTED** → the operator chose the engine path; no pod spend | docs/STATE.md:1087 | **Yes — this is the decision valid to this day** |

---

### E — External LLM rankings (reference field)

*What this channel measures:* how other frontier models fare in HU poker — as a yardstick, not as a gate.
*What it cannot do:* the Kaggle board measures RELATIVE to the LLM field (hence positive numbers), the GTOW board against
a re-solver (hence all negative). The two are **not convertible into each other** (measured below).

| Date | What was measured | Instrument / channel | Result (number ± spread, n) | Verdict | Source | Still valid? |
|---|---|---|---|---|---|---|
| 2026-06-19 | Frontier LLMs on the GTOW leaderboard | GTOW leaderboard (read-only API) | **GPT-5.2 −8.26 · GPT-5.5 −9.23** bb/100 AIVAT | An LLM-driven agent plays HUNL ~5× better than the engine of the time (−47) → the imitation ceiling applies to TRAINING a small model on our data, **not** to PROMPTING a frontier model | docs/STATE.md:1171 | Numbers historical (board has moved on); the distinction holds |
| 2026-09-10 | Kaggle Game Arena "Heads Up Poker", leaderboard v1 | Kaggle benchmark API, mean BB/100, all-play-all in the LLM field | Rank 1 **GPT-5.6 Sol +34.9 ± 5.1** · 2 GPT-5.5 +32.5 ± 6.0 · 3 Claude Fable 5.1 +29.7 ± 6.0 · 4 **Claude Opus 5 +15.8 ± 5.9** · 5 GPT-5.6 Terra +11.6 ± 5.5 · 15 GPT-5.4 mini −0.4 · 19 Claude Opus 4.8 −3.4 · 23 DeepSeek V3.2 −11.8 · 26 Claude Sonnet 4.6 −17.3 · 29 GPT-5 mini −49.3 | Positive values because measured relative to the field. Cost of the top: 12,000–19,000 tokens per move, up to 26 ct/move | ../reports/KAGGLE_ARENA.md:14-21 | Yes (retrieved 2026-09-10) |
| 2026-09-10 | Game configuration of the Kaggle environment | read directly from the environment + `tests/test_kaggle_arena.py` | HUNL, blinds 1/2, stacks 200 units = **100 bb**, reset per hand, dealer rotates, 100 hands/match | ★ **CORRECTION in the same document:** 100 bb is NOT our competition depth — GTOW runs at **200 bb** (`gtowizard.py:98,:281`) and our preflop blueprint only fires from **140 bb effective** (`bot.py:200`) → the Kaggle channel measures a DIFFERENT bot than the competition channel. The claim "exactly our house size" that used to stand there was wrong | ../reports/KAGGLE_ARENA.md:32-42 | Yes |
| 2026-09-10 | Calibration Kaggle → GTOW (6 models on both lists) | regression GTOW AIVAT on Kaggle BB/100 | all six: **r = 0.37, R² = 0.14, residual SD 15.5 bb/100**; without Grok 4 (residual −34): r = 0.88, R² = 0.77, residual SD 3.4, `GTOW ≈ 0.334·Kaggle − 22.7` | **NOT USABLE.** Dropping a point BECAUSE it contradicts is curve fitting; moreover different reasoning levels and extrapolation outside the data range | ../reports/KAGGLE_ARENA.md:105-119 | Yes |
| 2026-09-10 | GTOW AIVAT of the same 6 models | benchmark.gtowizard.com | GPT-5.6 Sol −15.4 · GPT-5.5 −9.2 · Grok 4 **−60.0** · GPT-5.4 −17.8 · Claude Opus 4.6 −20.4 · Gemini 3.1 Pro −30.8 | The spread in the LLM field is huge; "frontier LLM" is not a uniform playing strength | ../reports/KAGGLE_ARENA.md:107-113 | Yes |
| 2026-09-10 | GTOW leaderboard top and our own entries | benchmark.gtowizard.com, 83 entries, rank by 95 % lower bound | 1 Bitcrumbs −3.1 (SD 0.9, 52,005 hands) · 2 Trainer (SL) −6.2 · 3 Roman_SL −7.4 · 4 tangtang −12.6 · 5 GPT-5.5 (XHigh) −9.2 (SD 2.8, 5,000 hands) — **own: rank 31 Quantplay −30.4 (6,587) · rank 33 Quantplay v8 −31.6 (6,946) · rank 47 Experimental Poker Bot −51.7 (30,596)** | The top are PRIVATE agents, not LLMs. All own entries come from the v8 era; today's champion (~−21) was never posted. **Top 5 = lower bound better than ≈ −14.8**, gap ≈ 8 bb/100 | ../reports/KAGGLE_ARENA.md:128-142 | Yes (as of 2026-09-10) |
| 2026-09-10 | First reference value in the Kaggle channel: champion vs bare base | `pokerbot/benchmark/kaggle_arena.py --gegner basis`, 300 paired decks, 1 core, 3,153 s | raw mean **+55.8 bb/100**, SE **38.0**; 5 %-trimmed +6.3; median 0.0; divergent decks 32.3 % (97/300), of which positive 45/97 (sign-test z −0.71); bootstrap CI [−16.7, +134.6]; perm_p 0.076 | **NEUTRAL** (`stats.verdikt`). Explicitly NOT a bot verdict, only channel calibration. Price list of the channel: for SE ≈ 4 one would need ~27,000 decks ≈ 75 h on one core | ../reports/KAGGLE_ARENA.md:147-172 | Yes |
| 2026-09-10 | A/A null test of the Kaggle bridge | `kaggle_arena --aa --decks 8` | initially **−37.5 bb/100 instead of 0** (RNG stream kept running across hands, reused agents let the mirror halves drift apart) → after fix (fresh instances per half) **exactly 0** (nonzero 0, SE 0) | Two measurement traps found and closed (the second was the same `hand_id`-per-half trap as in v10) | ../reports/KAGGLE_ARENA.md:56-63 | Yes |
| 2026-06-14 | Our engine against frontier-LLM opponents | `pokerbot/benchmark/llm_opponent.py`, 40-hand samples | roughly even: **Opus 4.8 +30, o3 +17**; the naive **gpt-5.1 +395 was a prompt weakness + noise mirage** | Unusable at n=40; reliable opponent strength needs AIVAT | docs/STATE.md:1842-1844 | Yes as a warning; numbers worthless |

---

### F — LLM as a tool (opponent, auditor, consultant, research)

*What this channel measures:* what a language model delivers as an INSTRUMENT — exploitation patterns against our bot,
code findings, literature. *What it cannot do:* pronounce a verdict. Every LLM finding is a HYPOTHESIS that only
becomes evidence through a paired gate — paid for dearly several times in the project.

| Date | What was measured | Instrument / channel | Result (number ± spread, n) | Verdict | Source | Still valid? |
|---|---|---|---|---|---|---|
| 2026-08-17 | LLM adversary against AUSLESE v4 | `research/fable_duell.py` (file-based, replay-deterministic), 62 hands | **+115.5 bb for the adversary** (declared anecdote) with COUNTED patterns: button open-fold ~29 %, limp-call→fold-vs-c-bet 5/7, river station 4/5 big calls with losers (~90 bb), check-raise without follow-through 3/3, no mixing; `turn_wert` bets in continuation lines 3/3 real = usable tell → **capped check range = exactly the v8 PURIFY mechanism** | No bb verdict (n=62, anecdote), but a **mechanism finding** — the axis is the ADAPTIVE opponent, not the mirror | data/autogym/journal.jsonl:71 (`typ: FABLE-DUELL`) | Yes; predicted the later GTOW live break (docs/STATE.md:183-184) |
| 2026-08-18 | Retest against the hardened stack | `fable_duell.py` vs `r6_button` stack, 92 hands | Harvest **186 → 58 bb/100**; open-folds **0/46** (previously 29 %); 3-bet attack on the trash open net −21 bb; cooler-adjusted the bot would be ahead (one nut-flush hand = +200 bb) | **HARDENING PROVEN** on the adversary axis — while the same guard was NEUTRAL in the mirror → from this the binding two-axes doctrine (mirror = non-regression bound, adversary = proof of effect) | data/autogym/journal.jsonl:75 (`typ: FABLE-RETEST`); docs/STATE.md:188-190 | Yes |
| 2026-06-14 | Independent LLM code audit of the bot | `extraction/bot_audit.py`, `claude-opus-4-8`, every finding hand-checked | Audit called the code "mostly sound" and found the same spew live in `adaptive.py` (cause: no range narrowing against aggression). After the fix: 200-bb stack-offs eliminated, worst hand **−20,000 → ~−7,762** | LLM audit usable as a hypothesis generator — the bb numbers come from the engine channel, not from the LLM | docs/STATE.md:1860-1869 | Yes |
| 2026-07-05 | Full audit of the bot with an agent army | 90 agents / 9 dimensions / 3× adversarial verification, ledger `data/audit/audit_result.json` | **23 confirmed findings, 4 refuted**; the two HIGH findings were measurement seams (inverted blinds; 13 missing flags in the fingerprint) | The most valuable yield of the audit was not strategy but **broken measurement** | docs/STATE.md:834-842 | Yes |
| 2026-07-05 | Reliability of LLM literature search | Perplexity API + own existence-verification layer | **27/36 papers confirmed**; systematically **swapped metadata** (wrong authors on correct titles, arXiv IDs on the wrong paper, DeepStack's DOI on the Libratus entry, "Safe and Nested Subgame Solving" with four wrong authors) | **No paper from an LLM sweep may be cited without a verification layer** — adopted as a standing rule | ../reports/RESEARCH_SWEEP_2026-07-05.md:7-13, :57 | Yes |
| 2026-06-14 | LLM-generated exploit directives | `extraction/exploit_playbook.py` (Claude) | 11,520 directives (Haiku) + 240 high-quality ones (Opus) | Pure artefact counter; the effect was measured separately in the engine channel (rules against station +308, against maniac +262, no leak against strong opponents) | docs/STATE.md:1817-1818, :1760-1762 | Yes |
| 2026-09-07 | Frontier consult on the top-5 strategy | `gpt-6-astra`, Responses API, reasoning=high | Part B 5,178 reasoning tokens / 469 s · part D 5,696 / 481 s · part E (v10 critique) 9,751 / 662 s · part F 3,624 · part G 4,142 | Not a measurement but advice — explicitly annotated in the document with its own assessment ("what I adopt, what I reject") | ../consults/TOP5_CONSULT_GPT6_2026-09-07.md:1-6, :157, :1233, :2379, :4205 | Yes as the source of the v10.1 hybrid doctrine |

---

### G — Built but NEVER measured (open items of this channel)

| Date | What | Status | Source | Still valid? |
|---|---|---|---|---|
| 2026-06-29 | **Understanding layer** `pokerbot/brain/understanding.py::strategic_read` — SPR/position/pot odds/MDF + texture + made-hand read + measured GTO heuristics in ONE engine-computed frame, flag `POKERB_UNDERSTANDING`, default OFF | **BUILT + locally verified (OFF byte-identical to the base, numbers exact: req equity 33 % = 10/(20+10), MDF 50 %, SPR 4.0), but EV-UNMEASURED.** The intended measurement (deterministic GTOW per-decision A/B, then AIVAT) was never run | docs/STATE.md:1078; ../plans/ROADMAP.md:26-35, :80 | Yes — open item; the brain path has been secondary since 2026-07-04, hence untouched |
| 2026-06-29 | **Architecture finding:** the LLM brain decides via `executor → api.legalize`, NOT via `bot.py::PokerBot` | Hence ALL engine gains (ONTREE snap, river value floor, line-aware river advisor) reach the playable engine bots, **not** the brain. The brain was never graded per decision by the Analyzer except via `claude_export.py` | docs/STATE.md:1088 | Yes — explains why "adapt the LLM to the engine" was classified as LOW-VALUE |
| 2026-06-19 | **The actual RL thesis: does RL lift above the SFT warm start?** The clean test would be SFT vs GRPO on GTOW (`GLM_USE_SFT=1`, ~$2) | Never run cleanly; the one opportunity was lost because the campaign pulls only the GRPO (section A). The later re-SFT→GRPO attempt regressed to −90 → the thesis counts as **answered negatively** for this setup, but not cleanly isolated | docs/STATE.md:1165, :1132; ../NOTES.md:103-105, :120-121 | Yes |

---

### H — What of this channel STILL holds TODAY

1. **The track is deliberately secondary.** Since 2026-07-04 the engine-alone path is the product; the brain remains
   a research asset and teacher-gold loop (CLAUDE.md, block "CURRENT TRUTH + VEHICLE"). The 2026-06-29 RL pivot
   was refuted at $0 (docs/STATE.md:1087), and no LLM component sits in today's champion
   (`pokerbot/strategy/auslese.py` / v5 / r10).
2. **The transferable, multiply proven lessons:**
   - Gains came from the **WIRING** (what the engine feeds the LLM at runtime: made-hand +40.65), not
     from the weights; baking a serve hint into TRAINING backfired (−90).
   - **Perception fixes work, strategy nudges do not** (made-hand +40 vs solver_freq ±0).
   - **Form ≠ strength:** 97.5–98.8 % token accuracy next to −43 or −90 bb/100; 71.7 % PokerBench next to a
     lookup table with 88.6 %.
   - **Small samples lie**, even with AIVAT: the same configuration measured −28.36 and −49.52 (n=500 each).
   - **Imitation ceiling:** fcpa policy net −212, solver-imitation floor ~−72, 9B SFT+GRPO regressed — only RL with
     realised EV against a STRONG opponent could go beyond, and such an opponent does not exist in
     the loop (../plans/QWEN_6MAX_PLAN.md:8-9; docs/STATE.md:1113).
3. **The instruments live on even though the models do not:** `research/study_grade.py` (reconstructs
   and grades EVERY GTOW/Slumbot session), `research/gtow_tail.py` (tail-robust metrics + gate counterfactuals),
   `research/gtow_xray.py`, `research/fable_duell.py` (standing adversary instrument),
   `pokerbot/benchmark/kaggle_arena.py`.
4. **All live AIVAT numbers of the brain era carry the inverted-blinds bug** (until 2026-07-05) and are therefore
   presumably too pessimistic; paired A/Bs within the era remain meaningful, absolute levels do not.

---

## Self-play, gym and gate measurements

This channel measures **differences between two bot versions on identical cards** (duplicate/mirror principle:
a deck is played twice, the arms swap seats — the card variance cancels out,
`pokerbot/benchmark/duplicate.py:1-8`). It can therefore **decide cheaply and with small spread whether a
change is worse than the incumbent in the project's own self-play ecology** (non-regression bound).
It can **NOT** say how strong the bot is in absolute terms, whether a gain transfers against a foreign/adaptive opponent,
and it is **not transitive** (A beats B, B beats C ⇏ A beats C by the sum — measured:
journal line 92). The absolute anchor remains GTOW/Analyzer; all numbers here are **relative**.

### Channel profiles — what each channel can prove and what it cannot

| Channel | Source | Proves | Does NOT prove |
|---|---|---|---|
| `pargate` (HU mirror) | `pokerbot/autogym/pargate.py:1-8` | candidate vs incumbent on identical decks, per-deck edges, robust statistics | absolute strength; transfer to foreign opponents; hardening against adaptation |
| `pargate6` (6-max mirror) | `pokerbot/autogym/pargate6.py:1-15` | 6-max version duel; hero rotates over all 6 seats, league seeded | only own ecology ("tag plays at home against its own league") |
| `envgate` | `pokerbot/autogym/envgate.py:1-22` | import-time/env flags (subprocess hygiene) vs **GTOBaseline** — sign + spew canary | self-play truth; an arm can win here and be neutral in the mirror (explicitly pre-registered limit) |
| `orakel_duell` | `pokerbot/autogym/orakel_duell.py:1-14` | formula-violation rates (L/F classes per 1000 decisions) of both arms | chips/EV — it is the **second** instrument next to pargate, not a replacement |
| `exploit_jagd` | `pokerbot/autogym/exploit_jagd.py:1-15` | where an **adaptive** hunter (persistent Dirichlet model) milks the frozen bot = hardening map | win/verdict — the yield is the ledger, not the number |
| `exploit_gate` | `pokerbot/autogym/exploit_gate.py:1-14` | whether the exploit channel (ON vs OFF, fingerprint verified) brings anything against each league profile | whether a *different* exploit mechanism would work |
| `fable_duell` | `research/fable_duell.py:1-9` | an LLM adversary plays against the stack, **counted** patterns (open-fold rate, follow-through, size tells) | statistical significance (n=62/92 hands = anecdote + count, no bb/100 verdict) |
| `kaggle_arena` | `../reports/KAGGLE_ARENA.md`, `pokerbot/benchmark/kaggle_arena.py` | paired mirror in the Kaggle environment (100 bb, `python_repeated_pokerkit`) | GTO anchor — the field is LLMs, not a re-solver |

### The A/A null tests — the entry ticket of every measurement series

An A/A run sets candidate = incumbent. Because both arms have the same decks, the same seeds and the same code,
the per-deck difference **must** be EXACTLY 0. If it is not, the instrument measures noise from its
own wiring (RNG stream, hand_id, process env) — and **every** number of the series is worthless. The null test has
caught real bugs three times in this project (r10 hand_id, Kaggle RNG stream, deck order).

| Date | What was measured | Instrument / channel | Result | Verdict | Source | Still valid? |
|---|---|---|---|---|---|---|
| 2026-08-17 | A/A after spot-RNG seeding fix | pargate | 0.00 ± 0.00 bb/100, max_abs_edge 0, n=1936 decks | PASSED | `data/autogym/journal.jsonl:50` | yes — basis of all round-5 numbers |
| 2026-08-30 | A/A r6_button | pargate | 0.0 ± 0.0, n=1200 | PASSED | `data/runs/20260830_194513_pargate_r6_button/result.json` | yes |
| 2026-08-30 | A/A r7_river (exact enumeration, RNG-free) | pargate | 0.0 ± 0.0, n=576 | PASSED | `data/runs/20260830_194908_pargate_r7_river/result.json` | yes |
| 2026-08-30/31 | A/A r8_stack (GPU arm, determinism proof) | pargate | 2× 0.0 ± 0.0, n=600 | PASSED | `data/runs/20260830_203659_pargate_r8_stack/`, `…20260831_002812…/result.json` | yes — GPU determinism holds |
| 2026-09-01 | A/A r10_ernte (fp16 determinism) | pargate | 0.0 ± 0.0, n=576 | PASSED | `data/runs/20260901_114509_pargate_r10_ernte/result.json` | yes |
| 2026-09-07 | A/A r10_stack **before** bug fix | pargate | **−9.40 ± 10.92**, 13 nonzero, n=576 | **FAILED → bug** | `data/runs/20260907_213225_pargate_r10_stack/result.json` | no — cause `hand_id = 2*deck+half` made the private seeds of the mirror halves differ |
| 2026-09-07/08 | A/A r10_stack after fix (3×, each new hash) | pargate | 3× 0.0 ± 0.0, nonzero 0, n=576 | PASSED | `data/runs/20260907_214142_…`, `…220348…`, `20260908_015248_pargate_r10_stack/result.json` | yes; **lesson: a 40-deck A/A is not enough for K2** (only 1 plan deck), 576 needed — journal line 106 |
| 2026-09-09 | A/A tag vs tag in the 6-max channel | pargate6 | 0.0 ± 0.0, nonzero 0, n=288 decks (=1728 hero hands) | PASSED | `data/runs/verdrahtung/aa_tag.log` (closing line), `data/runs/20260909_181514_pargate6_tag` | yes |
| 2026-09-10 | A/A prince[final] in the Kaggle channel **before** fix | kaggle_arena | **−37.5 ± 94.49**, n=8 → STOP | **FAILED → bug** | `data/runs/kaggle_aa_2026-09-10.log` (closing line) | no — cause: bot draws from ONE RNG stream across hands; reused agents drifted apart |
| 2026-09-10 | A/A after fix (fresh instances per half) | kaggle_arena | exactly 0 (nonzero 0, SE 0) | PASSED | `../reports/KAGGLE_ARENA.md:62-63` | yes |

---

## 1. pargate — the HU mirror and the AUSLESE chain v1 → v5

What this section shows: the version chain was built **exclusively** via paired self-play duels. All
numbers are differences (bb/100) against a named incumbent, never absolute strength.

### 1.1 AUSLESE v1 (`sel_guard` — selection instead of frequency on the flop)

| Date | What was measured | Instrument / channel | Result | Verdict | Source | Still valid? |
|---|---|---|---|---|---|---|
| 2026-08-16 | `sel_guard` vs `basis`, first run | pargate | +4.70 ± 2.06, n=99,000 decks, CI95 [0.6; 8.8] | APPLY | `data/runs/20260816_213357_pargate_sel_guard/result.json`; `journal.jsonl:20` | yes, but superseded by v3/v4/v5 |
| 2026-08-16 | `sel_guard` replication, fresh deck universe (seeds 20000+) | pargate | +7.49 ± 2.08, n=99,000 | APPLY confirmed | `data/runs/20260816_222836_pargate_sel_guard/result.json`; `journal.jsonl:21` | yes |
| 2026-08-16 | Pool of both runs | pargate | **≈ +6.1 ± 1.5** over 198,000 decks | APPLY (naming AUSLESE v1) | `journal.jsonl:21` | yes — the first proven step |
| 2026-08-16 | Sanity run `sel_guard` at small n | pargate | +13.81 ± 17.8, n=1200 | NEUTRAL (channel too noisy) | `data/runs/20260816_213258_pargate_sel_guard/result.json` | illustration: n=1200 is useless in the HU mirror |

### 1.2 AUSLESE v2 (`sel_all`) — **discarded, the rotation was premature**

| Date | What was measured | Instrument / channel | Result | Verdict | Source | Still valid? |
|---|---|---|---|---|---|---|
| 2026-08-17 | `sel_all` vs `sel_guard`, run 1 | pargate | +3.00 ± 1.40, n=30,000 | initially APPLY+ROTATION | `data/runs/20260817_001033_pargate_sel_all/result.json`; `journal.jsonl:25` | **no — superseded** |
| 2026-08-17 | Replication run 2 | pargate | +0.44 ± 1.09, n=30,000; pooled +1.41 ± 0.86 (< 2 SE) | REPLICATION NOT PASSED | `data/runs/20260817_002130_pargate_sel_all/result.json`; `journal.jsonl:27` | yes (as a negative finding) |
| 2026-08-17 | Decisive run 3 | pargate | +0.18 ± 0.73, n=90,000; **pooled +0.69 ± 0.56** | ROTATION REJECTED, v2 dismantled | `data/runs/20260817_003212_pargate_sel_all/result.json`; `journal.jsonl:28` | yes — v2 exists only as a tag, was never incumbent |
| 2026-08-17 | Post-diagnosis of the same arm with margin 15pp (`sel_all_m15`) | pargate | 0.0 ± 0.0, **0 divergent decks out of 29,920** | reinterpretation: "**no channel**", not "refuted" | `journal.jsonl:51`, `:59` | yes — important distinction |

The +3.00 first run was sample luck. From this came the **three-runs rule** (no name without three runs), which
afterwards prevented a second mis-naming.

### 1.3 AUSLESE v3 (`sel_m15` — margin sweep)

| Date | What was measured | Instrument / channel | Result | Verdict | Source | Still valid? |
|---|---|---|---|---|---|---|
| 2026-08-17 | Sweep `sel_m06` vs v1 | pargate (runde4) | +0.06 ± 1.45 (vs basis +0.3) | NEUTRAL | `journal.jsonl:34` | yes |
| 2026-08-17 | Sweep `sel_m10` vs v1 | pargate (runde4) | +5.64 ± 1.74 (vs basis +8.72) | APPLY | `journal.jsonl:35` | yes |
| 2026-08-17 | Sweep `sel_m15` vs v1 | pargate (runde4) | +10.50 ± 2.10 (vs basis +17.47) | APPLY | `journal.jsonl:36` | yes, but point estimate too high (see below) |
| 2026-08-17 | `sel_m15` vs v1, replication | pargate | +1.11 ± 2.16, n=30,000 — **3 sigma away from the first run** | REPLICATION HETEROGENEOUS | `data/runs/20260817_134312_pargate_sel_m15/result.json`; `journal.jsonl:39` | yes — **the fat-tail finding**: per-deck edges are fat-tailed, 2SE intervals of the quiet channels too optimistic |
| 2026-08-17 | `sel_m15` vs v1, run 3 | pargate | +2.63 ± 1.22, n=90,000; pooled **+3.94 ± 0.95** (conservatively without first run +2.13 ± 1.06) | APPLY + naming v3 | `data/runs/20260817_140247_pargate_sel_m15/result.json`; `journal.jsonl:41` | yes |
| 2026-08-17 | `sel_m15` vs `basis`, large anchor | pargate | **+8.68 ± 1.28**, n=183,200 decks, 20 workers, 2821 s (3897 decks/min) | APPLY | `journal.jsonl:38` | yes |
| 2026-08-17 | `sel_m20` vs `sel_m15` (dose upper limit) | pargate | −1.52 ± 1.54, n=30,000 | NEUTRAL — curve flips, 15pp = plateau edge | `data/runs/20260817_135314_pargate_sel_m20/result.json` | yes |

### 1.4 AUSLESE v4 (`turn_wert` + env flags) — the bet-side step

| Date | What was measured | Instrument / channel | Result | Verdict | Source | Still valid? |
|---|---|---|---|---|---|---|
| 2026-08-17 | Channel width BEFORE the build (pre-registration) | pargate probe, 400 decks | `turn_wert` would bet in 40/800 hands (5 %); `sel_all_m15` turn-fold spots **0/800** | channel pre-measured (AP8 rule) | `journal.jsonl:43`, `:42` | yes — doctrine "measure the channel before the build" |
| 2026-08-17 | `turn_wert` vs `sel_m15`, run 1 (estimator v1, 5 % trim) | pargate | raw +1.64 ± 4.03, **trimmed 0.00** | NEUTRAL | `journal.jsonl:52` | **no — superseded**: at 8.4 % divergent decks the 5 % trim removed exactly the signal decks (`pokerbot/autogym/stats.py:20-33`) |
| 2026-08-17 | `turn_wert` vs `sel_m15`, runs 2+3 (estimator v2 = raw mean ± 2 SE) | pargate | +9.39 ± 4.06 and +10.78 ± 4.00, n=29,920 each, sign-test z 9.15/8.98 | APPLY | `journal.jsonl:61`, `:62` | yes |
| 2026-08-17 | Pool 3×30k | pargate | **+7.27 ± 2.33**, n=89,760, nonzero share 8.58 %, sign-test z 14.93 | APPLY | `journal.jsonl:63` | yes |
| 2026-08-17 | Re-evaluation with estimator v3 (bootstrap CI + permutation p) | pargate | `turn_wert` CI [+2.69; +12.05], p = 0.0007 → **HOLDS** | verdict confirmed | `journal.jsonl:68` | yes |
| 2026-08-17 | `turn_wert(sel_m15)` vs **frozen basis**, 3 runs | pargate | +9.26 ± 4.88 / +16.75 ± 4.84 / +22.42 ± 4.69 | APPLY | `data/runs/20260817_222907_…`, `…230825…`, `…231632_pargate_turn_wert/result.json` | yes |
| 2026-08-17 | Pool of the same 3 runs | pargate | **+16.14 ± 2.77**, CI95 [+10.74; +21.56], perm_p 0.0002, n=89,760 | APPLY | `journal.jsonl:70` | yes — the v4 core evidence |

### 1.5 Round 6 — hardening guards: the two-axes lesson

| Date | What was measured | Instrument / channel | Result | Verdict | Source | Still valid? |
|---|---|---|---|---|---|---|
| 2026-08-18 | `r6_ecall` (river eCall guard) vs `turn_wert` | pargate | **−4.15 ± 0.97**, CI [−6.12; −2.30], sign-test z −4.7, nz median −1452 chips, n=29,920 | **REJECT** | `data/runs/20260817_235330_pargate_r6_ecall/result.json`; `journal.jsonl:72` | yes — in the mirror the folded river calls are **value folds**; the Fable exploit lives on the adaptive axis, which the mirror does not see |
| 2026-08-18 | `r6_button` (button open-fold discipline) vs `turn_wert` | pargate | +0.71 ± 2.18, CI [−3.45; +5.12], channel 16.7 %, n=29,920 | NEUTRAL HARDENING CANDIDATE | `data/runs/20260818_000120_pargate_r6_button/result.json`; `journal.jsonl:73` | yes |
| 2026-08-18 | Final v4 stack (`r6_button` chain) vs **basis** | pargate | **+23.36 ± 5.32**, CI [+12.75; +33.72], perm_p 0.0002, sign-test z 9.72, nonzero 37.4 % | APPLY | `data/runs/20260818_013257_pargate_r6_button/result.json`; `journal.jsonl:76` | yes |

**Measured doctrine (binding, journal line 74):** hardening guards against ADAPTIVE opponents are
*structurally invisible to negative* in the mirror. Correct protocol: **mirror = non-regression bound,
adversary = proof of effect.**

### 1.6 Rounds 7/8 — river surgery → AUSLESE v5 (today's champion)

| Date | What was measured | Instrument / channel | Result | Verdict | Source | Still valid? |
|---|---|---|---|---|---|---|
| 2026-08-30 | `r7_bill` (river big-bet defence) vs `r6_button` | pargate | **exactly 0.0 ± 0.0**, n=30,000 — the guard never fires in the gym | NEUTRAL / "no channel" | `data/runs/20260830_200117_pargate_r7_bill/result.json` | yes — classified as a GTOW-axis guard, **not** in the stack |
| 2026-08-30 | `r7_river` (= `river_wert_bremse`) vs `r6_button` | pargate | +8.10 ± 1.14, CI [+5.90; +10.46], p 0.0002, n=30,000 | APPLY | `data/runs/20260830_194936_pargate_r7_river/result.json` | yes |
| 2026-08-30 | `r7_wert` (single decomposition) vs `r6_button` | pargate | +8.81 ± 1.25, CI [+6.43; +11.39], p 0.0002 | APPLY | `data/runs/20260830_201255_pargate_r7_wert/result.json` | yes |
| 2026-08-30 | `r7_river` replication, third disjoint bank | pargate | +7.38 ± 1.05, CI [+5.40; +9.46], p 0.0002 | APPLY, three-runs rule met | `data/runs/20260830_202416_pargate_r7_river/result.json`; `journal.jsonl:91` | yes |
| 2026-08-30/31 | `r8_stack` (GPU solver surgery) vs `r6_button`, 3 runs on banks 470k/530k/560k | pargate | +29.92 ± 3.10 / +23.76 ± 3.07 / +29.23 ± 3.03; **pooled +27.6 ± 1.8**; all perm_p 0.0002 | APPLY | `data/runs/20260830_204212_…`, `20260831_003356_…`, `20260831_024259_pargate_r8_stack/result.json`; `journal.jsonl:93` | yes |
| 2026-08-30 | `r8_stack` vs **frozen basis** | pargate | +30.60 ± 5.03, CI [+20.61; +40.29], p 0.0002, trimmed +16.79 | APPLY | `data/runs/20260830_225057_pargate_r8_stack/result.json` | yes — **with honesty note** |
| 2026-08-31 | Naming **AUSLESE v5** (tag `auslese-v5`, commit ec11fde) | pargate chain | FINAL_STACK = `river_gpu_guard(river_wert_bremse(r6_button(turn_wert(sel_m15))))` | NAMED | `journal.jsonl:93`; `pokerbot/strategy/auslese.py:4`, `:34` | **yes — this is today's champion** |

**Two pre-registered expectation violations, openly documented** (journal line 92):
(a) the r8 increment was **3–4× larger than pre-registered** (+7…+9 expected, +29.9 measured) — decomposition
consistent with big-pot surgery (3–3.5 % divergence decks, ~17 bb per intervention deck);
(b) **non-additivity**: +30.6 vs basis instead of the additively expected ~+53 → self-play is not transitive,
the mirror remains a selection channel, the absolute proof belongs to the GTOW anchor.

### 1.7 Rounds 9/10 — what was NOT shipped (the valuable negative findings)

| Date | What was measured | Instrument / channel | Result | Verdict | Source | Still valid? |
|---|---|---|---|---|---|---|
| 2026-08-31 | `r9_pre` (stackoff_bremse + no_limp) vs `r8_stack` | pargate | **−11.42 ± 2.97**, CI [−17.12; −5.68], n=30,000 | **REJECT** | `data/runs/20260831_095123_pargate_r9_pre/result.json`; `journal.jsonl:96` | yes |
| 2026-08-31 | Culprit diagnosis for it | trigger count, 200 decks | Base limps **78/400 hands** (~39 % of buttons) strategically → `no_limp_guard` rebuilt half the preflop game (37.8 % divergence decks); `stackoff_bremse` fired **1×/400** = self-play-silent | no_limp REJECTED, stackoff innocent | `journal.jsonl:96` | yes — lesson: the Fable finding "limp-call→fold 5/7" is a **limp-pot defence** problem, not the limping itself |
| 2026-08-31 | `r9_play` (river_play_guard) vs `r8_stack` | pargate | +1.14 ± 2.78, CI [−4.12; +6.32], p 0.347, n=30,000 | NEUTRAL | `data/runs/20260831_201350_pargate_r9_play/result.json` | yes |
| 2026-09-01 | `r9_v8` (composition) vs `r8_stack`, 2 runs | pargate | +3.91 ± 2.85 (n=30,000, p 0.081) and −1.23 ± 4.36 (n=14,976, p 0.607); pooled ≈ +2.3 ± 2.4 | NEUTRAL → **v8 dropped** (operator decision) | `data/runs/20260901_002705_…`, `20260901_044634_pargate_r9_v8/result.json`; `journal.jsonl:97` | yes — post-mortem `../reports/V8_POSTMORTEM.md`: (a) channel saturation (nz median 1.9 bb vs 11.6 bb for r8), (b) the mirror does not punish fine precision (no re-solver), (c) Ockham on a tie |
| 2026-09-08 | `r10_stack` (v10: K1 hero_range + K2 river_plan) vs `r8_stack` — gate G5 | pargate | +11.68 ± 10.85, CI [−9.39; +33.06], p 0.156, n=1968 decks | NEUTRAL (gate G5 PASSED: no asymmetric catastrophe) | `data/runs/20260908_002035_pargate_r10_stack/result.json`; `journal.jsonl:107` | yes — **but v10 is NOT shipped** (G3 missed); all 3 decks ≤ −100 bb arose in the **off-tree fallback to the bare base without v5 surgery**, offtree rate 42 % |

---

## 2. envgate — paired two-run test of the import-time flags against GTOBaseline

What this channel can do: measure env flags that would **not** be separable in the pargate process (module-level constants,
`bot.py` reads at import). What it **cannot** do: replace the self-play truth — measurement is against a
fixed third opponent (GTOBaseline), not against the incumbent. **Since 2026-08-17 envgate verdicts are called
`KANAL_*` and are explicitly NOT ship evidence** (`journal.jsonl:69`).

| Date | What was measured | Instrument / channel | Result (n=11,968 decks per arm) | Verdict | Source | Still valid? |
|---|---|---|---|---|---|---|
| 2026-08-17 | `prince` (PRINCE profile) vs reference | envgate | **−68.64 ± 11.90** | REJECT — **but artefact** | `data/runs/20260817_201814_envgate/result.json`; `journal.jsonl:60` | **no as a bot verdict**: exploit-OFF channel artefact (the reference exploits the weak GTOBaseline, the arm does not) — **no** verdict on PRINCE vs GTOW |
| 2026-08-17 | `raise_narrow` dose 1.0, 3 runs | envgate | +16.78 ± 4.10 / +13.65 ± 3.70 / +9.17 ± 3.61 | APPLY (2/3), all CI > 0 after estimator v3 | `20260817_201814_…`, `…205654…`, `…211423_envgate/result.json`; `journal.jsonl:68` | yes in the channel — **resolver-OFF context only** |
| 2026-08-17 | `raise_narrow` dose 0.5, 3 runs | envgate | +5.64 ± 2.88 / +6.49 ± 2.60 / +5.51 ± 3.09 | drops to NEUTRAL in 2/3 runs (CI touches 0) | the same runs; `journal.jsonl:68` | yes — RN05 was never in the version |
| 2026-08-17 | `k3_deception` (TURN_DEFENSE 0.07 + SLOWPLAY 0.25) alone, 3 runs | envgate | +8.72 ± 4.60 / +0.28 ± 3.75 / −4.69 ± 4.04 | **alone NOT replicated** | the same runs; `journal.jsonl:64` | yes |
| 2026-08-17 | K3 **inside** the combination (kombi_r5 − kombi_schlank, paired) | envgate, bank 65000, 12k decks | **+10.19 ± 4.01**, sign-test z +5.4, nz median +198 | interaction proven → assembly as a UNIT | `journal.jsonl:64` | yes |
| 2026-08-17 | `turn_def_advisor` | envgate | −3.37 ± 6.95 / +0.88 ± 7.15 / **−20.19 ± 6.72** | REJECT | `20260817_211423_envgate/result.json` | yes — never shipped |
| 2026-08-17 | `kombi_r5` (= v4 env set), 3 runs | envgate | +26.36 ± 6.04 / +25.22 ± 5.63 / +36.15 ± 6.01, all perm_p 0.0002 | APPLY (channel) | `20260817_205654_…`, `…211423…`, `…213451_envgate/result.json` | yes |
| 2026-08-17 | **Final staircase** vs frozen basis, bank 85000, 12k decks | envgate | `auslese_v3` **+21.36 ± 6.03**; `kombi_r5` **+49.79 ± 7.99**; paired step v3→v4 **+28.44 ± 6.17** (sign-test z +10.1) | naming AUSLESE v4 | `data/runs/20260817_214458_envgate/result.json`; `journal.jsonl:65-66` | yes in the channel — the +49.8 are **envgate**, not mixable with the pargate numbers |

---

## 3. orakel_duell — the mathematics benchmark as a second instrument

What this channel can do: check whether an arm pushes down the target class **without** raising another (Goodhart protection).
What it cannot do: replace chips/EV.

| Date | What was measured | Instrument / channel | Result | Verdict | Source | Still valid? |
|---|---|---|---|---|---|---|
| 2026-08-17 | `turn_wert` vs `sel_m15`, class rates per 1000 decisions | orakel_duell, n=1500 decks (8493 and 8568 decisions) | target class `verpasster_wert_turn` **17.04 → 3.06**; counter-check `bet_braucht_unplausible_folds` **10.04 → 7.54** (dropped, not risen); `call_unter_pot_odds` 24.63 → 20.13 | panel GREEN | `data/runs/20260817_213232_orakel_duell_turn_wert/result.json` | yes — the guard does what it should, without creating new classes |
| 2026-08-16 | Autogym pilot HU + 6-max, oracle tiers | selftest/gym | HU 600 hands: 3078 decisions, HART 0 · P 0 · L 62 · F 1; 6-max 300 hands: 3002 decisions, HART 0 · P 0 · L 0 · F 1 | loop runs | `data/autogym/report_20260816_195830.json` | yes |
| 2026-08-16 | Throughput pilot (E5) | gym local | 500 hands + 3,577 graded decisions in 52 s (~580 hands/min) | E5 local ✓, pod open | `../plans/AUTOGYM_PLAN.md:45` | yes |
| 2026-08-16 | Symmetry check (E2, pair drift) | gym_hu | HU 600 hands: button net **+33.43 bb/100**, pair drift +106.80 ± 70.26 (1.5 SE, compatible with 0) | E2 compatible, more pairs needed | `data/autogym/report_20260816_195830.json` | yes |
| 2026-08-16 | Detector check against a constructed defect bot (E3) | selftest | healthy vs never-folder **+394.9 ± 279.9** (60 decks, 1-hand horizon without adaptation) | EXPERIMENT CANDIDATE (spread too large for a verdict) | `journal.jsonl:7` | yes, as a sanity signal |
| 2026-08-16 | Null stability (E4) / gate self-test exploit-OFF vs ON | pargate self-test | +1.41 ± 2.18 (n=150) and +2.1 ± 3.3 | NEUTRAL — no invented improvements | `data/autogym/report_20260816_195830.json`; `../plans/AUTOGYM_PLAN.md:150,158` | yes |
| 2026-08-17 | 6-max catalogue (facing behaviour) | gym_six, 30,000 hands | position bb/100: BTN +33.5 · HJ +15.8 · UTG +6.8 · CO +2.4 · BB −28.9 · SB −29.6. Fold frequencies: flop **0.216** (21,165 nodes) · turn 0.297 (11,565) · river 0.337 (8,143) | catalogue finding | `journal.jsonl:37` | yes — proves: the **flop overfold is HU-specific**, 6-max folds 0.216 at an allowed 0.30 |

---

## 4. The adversary axis — exploit_jagd and fable_duell

What these channels can do: **prove hardening** (does an adaptive opponent find a rent?). What they cannot
do: deliver bb/100 verdicts — `fable_duell` with n=62/92 hands is anecdote **plus counted patterns**.

| Date | What was measured | Instrument / channel | Result | Verdict | Source | Still valid? |
|---|---|---|---|---|---|---|
| 2026-08-17 | 20 adaptive Dirichlet hunters vs frozen base | exploit_jagd, n=100,000 hands | **+8.87 ± 6.9 bb/100** (14/20 hunters positive) | adaptation gain not significant | `data/runs/20260817_020232_exploit_jagd/result.json`; `journal.jsonl:30` | yes |
| 2026-08-17 | Null control (without adaptation) | exploit_jagd, n=100,000 | +7.73 ± 8.7 (12/20 positive) | **gain through adaptation ≈ +1, not significant** | `data/runs/20260817_014431_exploit_jagd/result.json` | yes — **structure beats adaptation** (sel_guard +6.1 vs generic adaptation ~+1) |
| 2026-08-17 | Shift of the profit **channel** (adaptive vs control) | exploit_jagd | showdown net **+5.81 → +19.85**; non-showdown **+1.92 → −10.99** | finding: adaptation shifts where the money comes from | the same two result.json | yes |
| 2026-08-17 | Convergence profile of all 20 hunters on the defender | exploit_jagd | VPIP 0.75–0.77 · fold_to_bet 0.29–0.31 · aggression 0.31–0.34 (all 20 independently) | **the empirical hardening map** | `journal.jsonl:30` | yes |
| 2026-08-17 | Tail risk of generic adaptation | exploit_jagd | two catastrophe hunters (−69 / −47 bb/100) | warning | `journal.jsonl:30` | yes |
| 2026-08-17 | LLM adversary (Fable) vs AUSLESE v4 | fable_duell, 62 hands | +115.5 bb for the adversary (**anecdote**). Counted: button open-fold ~29 % · limp-call→fold-vs-c-bet 5/7 · river station 4/5 big calls with losers (~90 bb) · check-raise without follow-through 3/3 · turn_wert bets in continuation lines 3/3 real (usable as a tell) | hardening list, no bb/100 verdict | `journal.jsonl:71` | yes — core finding: the **capped check range** (= v8 PURIFY mechanism) |
| 2026-08-18 | Fable retest against the hardened `r6_button` stack | fable_duell, 92 hands | harvest **186 → 58 bb/100**; open-folds **0/46** (previously ~29 %); 3-bet attack on the trash open net −21 bb | **HARDENING PROVEN** | `journal.jsonl:75` | yes — exactly the guard the mirror had waved through as NEUTRAL |
| 2026-08-18 | Residual leaks after the hardening | fable_duell | river eCall 5/5 value bets paid off (~90 % of the residual harvest); turn_wert **size tell 7/7** (big = strong, small = weak → seesaw violated); stack-off after own aggression | open | `journal.jsonl:75` | yes — open construction sites |

---

## 5. exploit_gate — is the exploit channel correct at all?

What this channel can do: pit the same bot with `POKERB_EXPLOIT=1` against `=0` (fresh processes, fingerprint per
arm verified), against **each league profile individually**, on identical decks with button swap. Pre-registered
criterion: against exploitable profiles difference ≥ 0 AND CI lower bound > −3 bb/100.

| Date | What was measured | Instrument / channel | Result (diff ON−OFF, 600 paired decks each) | Verdict | Source | Still valid? |
|---|---|---|---|---|---|---|
| 2026-09-09 | Exploit ON vs OFF, `nit` | exploit_gate | −2.09 ± 9.52, CI [−20.99; +15.85] | criterion VIOLATED | `data/runs/verdrahtung/exploit_gate.log`; `data/runs/20260909_192123_exploit_gate` | yes |
| 2026-09-09 | `tag` | exploit_gate | −19.26 ± 15.35, CI [−51.18; +8.20] | NEUTRAL | ibid. | yes |
| 2026-09-09 | `lag` | exploit_gate | −18.50 ± 12.96, CI [−47.65; +3.55] | NEUTRAL | ibid. | yes |
| 2026-09-09 | `station` | exploit_gate | −17.35 ± 16.31 | criterion VIOLATED | ibid. | yes |
| 2026-09-09 | `maniac` | exploit_gate | −15.74 ± 9.61 | criterion VIOLATED | ibid. | yes |
| 2026-09-09 | `rock` | exploit_gate | −0.31 ± 8.97 | NEUTRAL | ibid. | yes |
| 2026-09-09 | `whale` | exploit_gate | −8.26 ± 17.01 | criterion VIOLATED | ibid. | yes |
| 2026-09-09 | `shark` | exploit_gate | −14.40 ± 13.67 | NEUTRAL | ibid. | yes |
| 2026-09-09 | **Overall** | exploit_gate | **all 8 point estimates ≤ 0, pooled ≈ −12 bb/100 (SE ~4.5)** | **"exploit correct" REFUTED** for the HU Dirichlet path | `journal.jsonl:113`; log closing line "Exploit korrekt: False" | **yes — product consequence: exploit stays OFF in ALL modes** |
| 2026-09-09 | 6-max reads (`SixMaxBot._read`) ON vs OFF | pargate6, n=2992 | +3.64 ± 13.45, CI [−22.03; +30.86] | NEUTRAL (harmless) | `data/runs/verdrahtung/exploit_gate.log` | yes |

Open caveat (self-noted): the exploit path is **river-only** and carries no adaptation across hands
in the gate harness — a real exploit would need a new mechanism (selection, not frequency).

---

## 6. pargate6 — the 6-max mirror

What this channel can do: pit 6-max versions against each other, hero rotates over all 6 seats of the same deck
(every hole pair is played once by the hero and once by each league profile). What it cannot do: escape the
**own ecology** (`tag` plays against its own league); the external anchor remains the Analyzer grade.

| Date | What was measured | Instrument / channel | Result (n=2992 decks per run, 8 workers) | Verdict | Source | Still valid? |
|---|---|---|---|---|---|---|
| 2026-09-09 | `hybrid` (tag + Prince takeover in HU-collapsed pots) vs `tag` | pargate6 | **−23.56 ± 9.02**, CI [−40.84; −5.26], sign-test z −7.6 | **REJECT** | `data/runs/verdrahtung/hybrid_vs_tag.log`; `data/runs/20260909_181534_pargate6_hybrid` | yes |
| 2026-09-09 | `hybrid_r8` (takeover with FINAL_STACK r8_stack) vs `tag` | pargate6 | **−21.73 ± 9.01**, CI [−38.98; −4.36] | **REJECT** | `data/runs/verdrahtung/hybrid_r8_vs_tag.log` | yes |
| 2026-09-09 | `hybrid_r10` (RC_STACK) vs `tag` | pargate6 | **−26.61 ± 8.93**, CI [−43.87; −9.38] | **REJECT** | `data/runs/verdrahtung/hybrid_r10_vs_tag.log` | yes |
| 2026-09-09 | `hybrid_r8` vs `hybrid` (does the chain rescue the takeover?) | pargate6 | +1.82 ± 5.58, CI [−9.01; +12.90] | NEUTRAL — **no** | `data/runs/verdrahtung/hybrid_r8_vs_hybrid.log` | yes |
| 2026-09-09 | **Verdict** | pargate6 | The Prince takeover (HU projection in 6-max pots) is **harmful** in the 6-max channel; best measured 6-max bot = league core `tag` | six_server takeover **default OFF** (`POKERB_SIX_TAKEOVER=1` switches it on) | `journal.jsonl:112` | yes |
| 2026-09-09 | `tag_flatfix` (flat_guard: never flat dominated offsuit broadways vs an open) vs `tag`, run 1 | pargate6 | **+17.70 ± 6.40**, CI [+4.93; +29.92], perm_p 0.0035 | APPLY | `data/runs/pargate6_tag_flatfix_2026-09-09.log` | yes |
| 2026-09-09 | Run 2 | pargate6 | +11.36 ± 6.88, CI [−2.01; +25.16], perm_p 0.057 | NEUTRAL | `data/runs/pargate6_tag_flatfix_seed2_2026-09-09.log` | yes |
| 2026-09-09 | Run 3 | pargate6 | **+19.18 ± 7.01**, CI [+5.59; +33.19], perm_p 0.0035 | APPLY | `data/runs/pargate6_tag_flatfix_seed3_2026-09-09.log` | yes |
| 2026-09-09 | Pooled (three-runs rule) | pargate6 | **≈ +16 bb/100** | APPLIED to `PROFILES["tag"]` | `journal.jsonl:118`; `pokerbot/arena/sixmax.py:59` (`flat_guard=True`) | **yes — in the product** (league, advisor, tournament); old core = tag `sixmax-tag-pre-flatfix` |

---

## 7. Transfer tests against a foreign opponent — what did NOT work

| Date | What was measured | Instrument / channel | Result | Verdict | Source | Still valid? |
|---|---|---|---|---|---|---|
| 2026-08-17 | Does the AUSLESE v1 gain transfer to a foreign opponent? | unpaired vs GTOBaseline, n=3000 decks | −3.78 ± 30.31 (AUSLESE −23.40 ± 21.99 vs base −19.62 ± 20.86) | uninformative | `journal.jsonl:29` | yes (as a method finding) |
| 2026-08-17 | Repeat correctly paired (per-deck difference) | paired vs GTOBaseline, n=3000 | −3.80 ± 12.87 | **uninformative** | `journal.jsonl:31-32` | yes |
| 2026-08-17 | Cause diagnosis | — | The per-deck pairing **breaks** because the MC equity calls are UNSEEDED (`equity_vs_*` without rng) → both arms diverge stochastically on every deck | resolution would need ~120k decks **or** seeded MC | `journal.jsonl:32` | **yes — binding lesson: unseeded MC breaks pairings** |

---

## 8. kaggle_arena — the new, still uncalibrated mirror

| Date | What was measured | Instrument / channel | Result | Verdict | Source | Still valid? |
|---|---|---|---|---|---|---|
| 2026-09-10 | `prince[final]` vs `prince[basis]`, first reference value | kaggle_arena, 300 paired decks | +55.83, SE **38.02**, trimmed +6.3, median 0.0, nonzero 97/300 (32.3 %), nz_pos 45 (sign-test z −0.71), CI95 [−16.67; +134.58], perm_p 0.0757, 3152.9 s (~10.5 s/deck) | **NEUTRAL — channel calibration, NOT a bot verdict** | `data/runs/kaggle_prince_vs_basis_2026-09-10.log`; `journal.jsonl:121` | yes — mean tail-carried; SE 4 would need ~27,000 decks (~10 h on 8 cores) |
| 2026-09-10 | Stack-size correction | code check | GTOW runs at **200 bb** (`gtowizard.py:98` starting_stack 20000), our preflop blueprint only fires from **140 bb effective** (`bot.py:200`) → the 100-bb Kaggle channel measures a **different** bot (heuristic cascade instead of blueprint) | CORRECTION (documentation was wrong) | `journal.jsonl:122` | **yes — the earlier claim "exactly our house size" is WITHDRAWN**; `kaggle_arena` now has `--stack-bb 100\|200` |

---

## 9. Explicitly outdated / withdrawn numbers of this channel

| Number | Where from | Why invalid | Replaced by |
|---|---|---|---|
| AUSLESE v2 "+3.00 ± 1.40 over v1" | `journal.jsonl:25` | sample luck; 2 replications fell to +0.44 and +0.18 | pooled +0.69 ± 0.56 → **rotation rejected**, v2 dismantled (`journal.jsonl:28`) |
| `turn_wert` "+1.64 ± 4.03 / trimmed 0.00 → NEUTRAL" | `journal.jsonl:52` | **estimator v1**: at 8.4 % divergent decks the 5 % trim removed exactly the signal decks | estimator v2 (raw mean ± 2 SE) → +9.39 / +10.78, pool +7.27 ± 2.33 (`stats.py:20-33`) |
| `sel_m15` "+10.50 ± 2.10" as a point estimate | `journal.jsonl:36` | 3 sigma above the replication → fat-tail heterogeneity, not noise | pooled +3.94 ± 0.95 (`journal.jsonl:41`) |
| envgate `prince` "−68.64" | `20260817_201814_envgate/result.json` | **channel artefact**: exploit-OFF arm against an exploitable opponent; no bot verdict | no replacement number — PRINCE belongs on the GTOW axis (`journal.jsonl:60`) |
| A/A r10_stack "−9.40 ± 10.92" | `20260907_213225_pargate_r10_stack/result.json` | bug `hand_id = 2*deck+half` → different private seeds per mirror half | A/A 576 exactly 0 after fix (3×) |
| A/A Kaggle "−37.5" | `data/runs/kaggle_aa_2026-09-10.log` | bug: reused agents from one RNG stream | A/A exactly 0 with fresh instances per half |
| "v3 +21.4 / v4 +49.8" as bot strength | `20260817_214458_envgate/result.json` | **envgate** numbers (vs GTOBaseline), not mixable with pargate numbers; verdicts have since been called `KANAL_*` | pargate counterpart: v4 core vs basis +16.14 ± 2.77 |
| additive expectation "r8 vs basis ≈ +53" | pre-registration | self-play is **not transitive** | measured +30.60 ± 5.03 (`journal.jsonl:92`) |

---

## 10. What holds today (2026-09-10)

* **Champion HU = AUSLESE v5** (`r8_stack`, tag `auslese-v5`, commit ec11fde) — chain
  `river_gpu_guard(river_wert_bremse(r6_button(turn_wert(sel_m15))))`, `pokerbot/strategy/auslese.py:4,34`.
  The evidence is **mirror evidence**; v5 has **no** GTOW anchor of its own (the only external anchor is v4-on-
  PRINCE with −21.1; `docs/STATE.md`).
* **v8 (r9_v8), v9 (r10_ernte) and v10 (r10_stack) are NOT shipped.** v8 because of channel saturation (NEUTRAL),
  v10 because of missed gates G2/G3 — the mirror gate G5 (+11.68 ± 10.85) did *not* rescue it.
* **6-max = league core `tag` with `flat_guard`** (tag `sixmax-tag-flatfix-v1`, ≈ +16 bb/100 over 3 pargate6 runs);
  the Prince takeover is refuted and default OFF.
* **Exploit is OFF everywhere** — 8/8 league profiles ≤ 0, pooled ≈ −12 bb/100.
* **Binding measurement doctrine from these runs:** A/A null test before every series (must be EXACTLY 0, otherwise STOP);
  three-runs rule before every naming; measure channel width BEFORE the build; quiet channel (candidate vs candidate) beats
  noisy one (vs base); mirror = non-regression, adversary = hardening proof; envgate numbers are never
  ship evidence; unseeded MC breaks pairings; one worker fleet at a time.

---

## Snowie, tournament, multiway, vision, solver validation

These channels are all SIDE channels to the GTOW AIVAT anchor and each measure something different:
**PokerSnowie bridge** = a real external opponent via screen recognition — it measures real money
against a foreign network, but without showdown logging and therefore without AIVAT (raw, high-variance, plus an
"automation tax" through recognition/click errors); **Snowie as grader** delivers the opinion of a
THIRD range model per decision (hypothesis source, never a gate — Snowie is demonstrably the
weaker referee). **Tournament/ICM** measures ROI/placement ladder in its own simulation
against the own league — it can show arm deltas (ICM on/off, pressure on/off) on paired seeds, but
no absolute tournament win rates against real fields. **Multiway/6-max** measures in the paired 6-max mirror
(pargate6) against the own league — own ecology, no external anchor (that is the GTOW Analyzer grade).
**Vision regression** measures NOT poker, but whether the screen reader reads preserved stills correctly
(binary, deterministic). **Solver validation** measures code against code/mathematics (exact
enumeration, closed-form toy solutions, TexasSolver as a second opinion) — it proves correctness of the
computation, NEVER that the played strategy makes money. **Runtime** is pure mechanics.

---

### 1. PokerSnowie bridge (live vision channel, real account against a foreign network)

| Date | What was measured | Instrument / channel | Result (number ± spread, n) | Verdict | Source (file:line) | Still valid? |
|---|---|---|---|---|---|---|
| 2026-08-04 | Throughput + dropout rate of the fully automatic bridge | `pokerbot/vision/snowie_bridge.py` against PokerSnowie 4 | 13.3 hands/min, ~4 % dropouts, both themes (dark/bright) | production-ready | docs/STATE.md:421-423 | yes (code unchanged in the repo) |
| 2026-08-04 | Account balance over 3 marathon runs | Snowie bridge, raw | 3,651 hands raw, account **−$2,915** | raw NEGATIVE, but not a bot verdict | docs/STATE.md:426 | yes as a raw number; the loss causes are sealed (see below) |
| 2026-08-04 | Win rate in the cleaned pool | Snowie bridge, after excluding the automation error classes | **+3.2 bb/100, 95 % band [−37, +44]** (n=3,114 clean hands) | ≈ break-even vs Snowie; band far too wide for a verdict (±20 would need ~13k hands) | docs/STATE.md:426-427, 437-438 | yes as the best Snowie anchor; NOT significant |
| 2026-08-04 | Attribution of the three run losses | individual post-mortem per run | L1 = 46 % dropouts (833 forced folds) · L2 = over-stack raise loop (Snowie silently rejects) · L3 = 13 phantom-pot jams (decimal-point loss ×100) | all three classes sealed (all-in preset + repeat watchdog + chip-conservation invariant) | docs/STATE.md:428-431 | yes — the fixes are in the code; a clean run 4 for confirmation is OUTSTANDING |
| 2026-08-04 | AIVAT against Snowie possible? | methodology check | **no** — no showdown logging, no own value function in the path; ladder defined (showdown logger → all-in luck adjustment → MIVAT-light) | structural limit | docs/STATE.md:436-437 | yes, unchanged open |
| 2026-08-04 | Prince suspicion "turn monster checks = leak" | offline experiment with continued game tree | The check is a deliberate check-raise trap; 2nd move raises/bets — identical with thin and full history | acquitted (no leak) | docs/STATE.md:435-436 | yes |
| 2026-08-04 | Preflop role model in the bridge | operator objection + rebuild | Prince HU takes over ONLY postflop; preflop 6-max position prior (`make_seeded_tracker`: UTG 194 → BTN 552 combos instead of HU 1102) | correction applied (the HU projection would have read MP opens as a ~50 % range) | docs/STATE.md:423-425 | yes |

### 2. Snowie as external GRADER (400 paired hands, every blunder clicked through individually)

| Date | What was measured | Instrument / channel | Result (number ± spread, n) | Verdict | Source (file:line) | Still valid? |
|---|---|---|---|---|---|---|
| 2026-08-17 | Blunder distribution of AUSLESE v1 | PokerSnowie 4 grading, 400 exported hands, gate parity (resolver OFF) | 39 blunders: C call-downs too loose **15** · B missed value/too passive **11** · A over-aggression with strong hands **9** · D folds too tight **3** | hypothesis source; largest class = exactly the mechanism that brought v1 its +6.1 bb/100 (dose too high) | ../reports/SNOWIE_BLUNDER_ANALYSIS.md:12-19 | yes as a diagnosis; the doctrine from it is confirmed by measurement (margin sweep) |
| 2026-08-17 | Call frequency flop, base vs v1 | Snowie triangulation, 400 paired hands | base calls **53 %** of the Snowie recommendation, v1 **195 %** | off on both sides → margin sweep as a candidate | docs/STATE.md:292-295 | yes (led to sel_m15) |
| 2026-08-17 | Does the Snowie direction carry in the own gate? | paired self-play gate (quiet channel vs v1), 25k decks each | m06 +0.06±1.45 NEUTRAL · **m10 +5.64±1.74** · **m15 +10.50±2.10** (monotone dose effect) | Snowie's "3pp too loose" confirmed three times and quantified | ../plans/AUTOGYM_PLAN.md:116-118 | yes — m15 is part of the version chain |
| 2026-08-17 | Multi-street discipline (Snowie derivation 2) | paired gate | `einmal_guard` +0.41±1.05 | **NEUTRAL — family discarded** (the stricter margin solves it better) | ../plans/AUTOGYM_PLAN.md:121-122 | yes (negative result) |
| 2026-08-17 | Is Snowie a valid judge? | method critique + repo history | Snowie assumes its OWN balanced villain range, play was against our base bot; engine vs Snowie ≈ break-even, vs GTOW −19.7 → Snowie is the weaker referee | **the blunder list is NEVER a gate**, only a hypothesis | ../reports/SNOWIE_BLUNDER_ANALYSIS.md:60-66 | yes, binding |

### 3. Tournament / ICM

The channel: paired SNG/MTT simulation against the own bot league, arm A vs arm B on identical seeds.
It measures ROI/ladder DELTAS between doctrine variants; absolute values are model-dependent (field = prior).

| Date | What was measured | Instrument / channel | Result (number ± spread, n) | Verdict | Source (file:line) | Still valid? |
|---|---|---|---|---|---|---|
| 2026-08-04 | The ICM computation itself | `tests/test_icm.py` — exact Malmuth-Harville bitmask DP against an INDEPENDENT permutation enumeration (different algorithm) | all tests passed, tol 1e-9; example 50/30/20 → [38.39 · 32.75 · 28.86] | exactly validated | tests/test_icm.py:1-6; **re-run today (2026-09-10): "ICM: alle Tests bestanden"** | yes, reproduced today |
| 2026-08-04 | μ-1: full bubble factor on EVERY call | paired SNG arena, ICM on vs off | **−8.1 ± 13.9 pp ROI**, over-tightening pattern (more 4th, fewer 1st) | **REFUTED** — doctrine fix forced | docs/STATE.md:402-404 | yes (negative result, reason for the proportional premium) |
| 2026-08-04 | μ-2: proportional risk premium BF_eff = 1+(BF−1)·(to_call/stack) | paired SNG arena, n=500 | **+9.2 ± 8.0 pp ROI** (ICM on +18.4 % vs off +9.3 %); fingerprint 2nd places 71 vs 47 | positive, not yet significant | docs/STATE.md:404-405 | yes |
| 2026-08-04 | μ-3: replication of the proportional premium | paired SNG arena, 1500 pairs, 6 workers | **+10.02 ± 5.03 pp ROI**, 95 % band [+0.2, +19.9], z=1.99; MORE wins (214 vs 192) AND a better ladder | **VALIDATED** (dominance on both metrics) | docs/STATE.md:405-406 | restricted — see next row (engine defects) |
| 2026-08-04 night | Engine correctness underneath the μ measurements | 15-agent review + engine fuzz, `tests/test_mtt.py` preserved | 6 confirmed defects: ante as a street bet · **HU blind inversion in table.py** (button posted BB) · orphaned side-pot layer (chips destroyed) · hero initiative flag (seat=0 fixed → ~5/6 hands wrong) · all-in-through-antes hole · ICM all-in threshold | all fixed | docs/STATE.md:361-368 | yes — **CAVEAT: all earlier SNG absolute values (μ-3 etc.) ran on the engine WITH (1)–(3); arm deltas count as robust, absolute values shift** (docs/STATE.md:368-370) |
| 2026-08-04 | Pressure lever against a FREQUENCY field (duel 1) | paired SNG arena | 92 % wins = ceiling effect | **uninformative** (field too weak) | docs/STATE.md:407-409 | yes (negative/discarded design) |
| 2026-08-04 | Pressure lever against an ICM-PLAYING bot field (duel 2) | paired, n=300/arm | chipEV **+6.6** · icm **+7.7** · icm+pressure **+14.1 % ROI**; pressure leads on every metric (P1st 21 % vs 18 %, ITM 36.3 %); +7.5 pp vs chipEV, **z=0.76** | order clear, significance needs ~2k pairs; **defensive ICM lens against an ICM field ≈ worthless (+1.1)**; fee (~4.8 pp) not deducted | docs/STATE.md:409-412 | yes, as a statement of order; not significant |
| 2026-08-04 | 2×2 decomposition pressure × reads (confound fix, identical seeds) | paired SNG arena | pressure carries (**+4.7 alone, +6.4 bundled**); **reads alone HURT in the tournament: −13.9 ± 10.7 (z=−1.3)** | reads stay off in the tournament | docs/STATE.md:412-415 | yes |
| 2026-08-04 | Real PS $1050 field (opponent behaviour) | `research/ps_tourney_field.py`, mined field, 2,055 hands | deep phase VPIP 31.7 / PFR 20.4 / 3-bet 10.2 / FoldVsRaise 53.6 %; under pressure **FoldVsRaise 54→62 %, jam 1.1→13.1 %** | ICM forced tightness empirically proven (basis of the pressure lever) | ../reports/TOURNAMENT_MODE.md:35-41 (file `data/ps_tourney_field.json`) | yes |
| 2026-08-04 night | The operator's $1050/600-entries MTT scenario | `research/mtt_sim.py`, paired, conservative bracket (bot cores at the hero's table), n=960 | **ROI −28/−32 %, ITM 7.5 % (½ base), P(1st) 0.2–0.4 % (1.3–2.5× base)** = chip-accumulator profile; 27 % busts in the first 2 levels at 220 bb; pressure lever without signal (−4.0 ± 18.9, z=−0.2) | design asymmetrically unfair (only the hero's table hard) → **lower bound**, no verdict | docs/STATE.md:369-373 | yes as a lower bound; main measurement (3000 pairs) was aborted by the operator |
| 2026-08-04 night | Tournament variance (from the exact payout ladder) | analytical from the sim | SD 5.4–9.7 buy-ins/tournament (rises with skill); 85 % zeros; at +65 % ROI: P(in the red after 100 tournaments)=23 %, max DD p50/p99 = 27/60 BI, ~140 BI for 5 % ruin | bankroll doctrine | docs/STATE.md:373-376 | yes |
| 2026-08-04 | 13,016-chip deficit (suspected engine leak) | reproduction attempt, ~325 full tournaments + 235k hands | **NOT reproducible** in the committed code (chip-exact); culprit with measured fit = defect (3) orphaned side-pot layer (~1/30 tournaments, sizes 267–26,144) | closed + tripwire (refund instead of destruction, chip conservation per hand) | docs/STATE.md:377-382 | yes |
| 2026-09-09 | MTT trainer mode: side-table cost | `tests/test_tournament_mode.py`, full field, 20 rounds | 5 tables per hero hand **mean 120–129 ms, max ≈ 200–213 ms** (journal: mean 121 / max 216) | below the 300-ms target → `side_tables_every=1` | ../reports/TOURNAMENT_MODE.md:100-103; data/autogym/journal.jsonl (TURNIER-MODUS-BUILD, 2026-09-09 20:13:34) | yes |
| 2026-09-09 | MTT director invariants | bots-only to the winner, seed 7, audit every round | 131 rounds, 38.8–40.1 s; chip conservation 60·5000 after every round; every place 1..60 exactly once; balance ±1; determinism seed 11 twice identical, seed 12 ≠ 11 | 7 (later 8) tests green | ../reports/TOURNAMENT_MODE.md:104-108 | yes — `python -m tests.test_tournament` re-run today: "TURNIER: alle Tests bestanden" |
| 2026-09-09 | Tournament mode: hand-continuity bug (operator QA) | TestClient reproduction | every tournament hand was a fresh `Table` with hand_no 1 → `_log_if_done` skipped EVERYTHING after hand 1 (no stack return, no busts, feedback frozen) | fixed + `test_hand_continuity`; re-measurement 2 full tournaments (seeds 3/11: 6 and 31 hands), browser speed run 3,671 renders, 0 empty tables | ../reports/TOURNAMENT_MODE.md:118-125 | yes |
| 2026-09-09 | Tournament mode: "empty table" | browser + TestClient | tournament bb 50 → slider 187.5 chips → `ActionReq.amount: int` → FastAPI 422 without `error` key → client rendered the error response as game state | 3-layer fix + `test_fractional_amount_is_rounded` | ../reports/TOURNAMENT_MODE.md:126-132 | yes |
| 2026-09-09 | Field pace in the trainer MTT | observation during the run | 60 → ~30 players in ~25 rounds (maniacs/whales go all-in early at 100 bb) | practical for training, **faster than a real online MTT** (model limit) | ../reports/TOURNAMENT_MODE.md:133-134 | yes |

### 4. Multiway / 6-max

The channel `pargate6` is a paired 6-max mirror (hero rotates over all 6 seats per deck) against the
own league — it can measure candidate-vs-incumbent deltas, but nothing absolute: `tag` plays "at home".

| Date | What was measured | Instrument / channel | Result (number ± spread, n) | Verdict | Source (file:line) | Still valid? |
|---|---|---|---|---|---|---|
| 2026-08-17 | 6-max position ledger + facing catalogue v0 | self-play gym 6-max, 30k hands / 298k graded decisions | positions bb/100: **BTN +33.5 · HJ +15.8 · UTG +6.8 · CO +2.4 · BB −28.9 · SB −29.6**; fold_freq flop **0.216** / turn 0.297 / river 0.337 at mean bets 0.431/0.384/0.365 pot (nodes 21,165/11,565/8,143) | order plausible; **flop fold BELOW the MDF allowance (0.30 at 0.43-pot bets) → NO 6-max flop overfold; the HU flop overfold is HU-specific** | data/autogym/journal.jsonl (RUNDE4-6MAX-KATALOG, 2026-08-17 12:55:05); ../plans/AUTOGYM_PLAN.md:123-127 | yes — and binding: blind transfer of `sel_guard` to 6-max is NOT indicated (docs/STATE.md:279-281) |
| 2026-09-09 | Prince takeover in HU-collapsed 6-max pots | `pargate6`, 2992 decks each, incumbent = league core `tag` | hybrid **−23.56 ± 9.02** CI[−40.8;−5.3] · hybrid_r8 **−21.73 ± 9.01** · hybrid_r10 **−26.61 ± 8.93** · hybrid_r8 vs hybrid +1.82 ± 5.58 NEUTRAL | **REJECT all** — the HU bot hurts in the 6-max pot; best measured 6-max bot is `tag`. Takeover default OFF | data/autogym/journal.jsonl (VERDRAHTUNG-6MAX-VERDIKT, 2026-09-09 19:26:50); docs/STATE.md:50-53 | yes |
| 2026-09-09 | A/A null test of the new 6-max channel | `pargate6`, tag vs tag, 288 decks | **EXACTLY 0** | channel clean | data/autogym/journal.jsonl (VERDRAHTUNG-6MAX-VERDIKT) | yes |
| 2026-09-09 | Dirichlet river exploit ON vs OFF | `pokerbot/autogym/exploit_gate.py`, 600 paired decks per league profile, fingerprint verified | diff ON−OFF: nit −2.1±9.5 · tag −19.3±15.4 · lag −18.5±13.0 · station −17.4±16.3 · maniac −15.7±9.6 · rock −0.3±9.0 · whale −8.3±17.0 · shark −14.4±13.7 → **all ≤ 0, pooled ≈ −12 bb/100 (SE ~4.5)**; 6-max reads ON vs OFF +3.6 ± 13.5 NEUTRAL | **REFUTED** — exploit stays OFF in all modes | data/autogym/journal.jsonl (EXPLOIT-GATE-VERDIKT, 2026-09-09 19:26:50); docs/STATE.md:54-56 | yes |
| 2026-09-09 | 6-max FLAT FIX (`flat_guard`: never flat dominated offsuit broadways vs an open) | `pargate6`, 3 runs of 2992 decks vs old `tag` | **+17.7 ± 6.4** (APPLY, perm_p 0.0035) · **+11.36 ± 6.88** (NEUTRAL, p 0.057) · **+19.18 ± 7.01** (APPLY, p 0.0035); pooled ~+16 bb/100 | APPLIED to `PROFILES["tag"]` (league, advisor, tournament); tags `sixmax-tag-pre-flatfix` / `sixmax-tag-flatfix-v1` | data/autogym/journal.jsonl (FLATFIX-6MAX-VERDIKT, 2026-09-09 21:54:18); docs/STATE.md:24-30 | yes — **open: external anchor (Analyzer export of the NEW tag) missing** |
| 2026-07-04 | External absolute 6-max grade | GTOW Analyzer via `research/sixmax_export.py`, n=1500 | **GTO score 85.9 %, EV loss 7.61 bb/100** (vs HU 53.4 % / freq diff 54.6 %) | the only EXTERNAL 6-max anchor; refers to the `tag` core BEFORE the flat fix | docs/STATE.md:52 (repeated CLAUDE.md:88-91) | partly — core has changed since (flat fix), the grade is NOT re-measured |
| 2026-08-04 | Multiway 7–10 seats | `engine/table.py` (POS_LABELS 7–10, stacks=/ante=/rebuy=), sixmax buckets ONLY for new labels; trainer `?players=9` | 6-max path **byte-identical** (anchor protection); trainer TestClient-verified for 6/8/9 seats | built + verified (mechanics, no EV verdict) | docs/STATE.md:399-401 | yes |

### 5. Vision recognition (regression net, frame audit)

| Date | What was measured | Instrument / channel | Result (number ± spread, n) | Verdict | Source (file:line) | Still valid? |
|---|---|---|---|---|---|---|
| 2026-08-04 | Recognition regression on preserved failure scenes | `python -m research.snowie_regress --run`, 5 stills of both themes | **5/5 passed** | gate for every vision change | docs/STATE.md:431-432; research/snowie_regress.py:1-9 | **yes — re-run today (2026-09-10): 5/5 passed** |
| 2026-08-04 | Frame recorder audit | recorded frames against recognised state | **27/28 frame-exact** | 1 deviation documented, not cleared | docs/STATE.md:432-433 | yes |
| 2026-08-04 | Lesson ladder of image recognition (error classes) | bridge development | $ sign becomes an OCR digit (crop before OCR) · margin rule + convergence (ambiguous → file → template) · second-source pot with suffix signature + OCR referee · line/polarity adaptation | hardening doctrine: NEVER compute with wrong numbers; chip conservation as a gate | docs/STATE.md:433-435; CLAUDE.md:190-193 | yes |
| 2026-08-04 | Not measured: universal VLM table reader | `pokerbot/vision/screen_reader.py` (VLM, any site, ~<1 ct/frame, watch mode) | built, **no accuracy measurement found in the repo** | unmeasured | docs/STATE.md:1068 | open — measure before use |

### 6. Solver and mathematics validation

This channel proves COMPUTATIONAL correctness (against exact enumeration, closed-form solutions, second solvers).
It says nothing about the profitability of the played strategy — the consult note on that is explicit:
r=0.999 between two solvers only means that the cores agree given the same inputs.

| Date | What was measured | Instrument / channel | Result (number ± spread, n) | Verdict | Source (file:line) | Still valid? |
|---|---|---|---|---|---|---|
| 2026-08-30 | 7-card evaluator on GPU | `pokerbot/engine/gpu_eval.py` against treys ordering | **16.8 M hands/s; 250k ordering pairs 0 errors** | validated; lesson: CUDA `log2` 1-ulp trap → integer-only | docs/STATE.md:115-117; data/autogym/journal.jsonl (R8-GPU-RESOLVER, 2026-08-30 20:20:24) | yes |
| 2026-08-30 | Batch equity on GPU | `gpu_equity.py` against CPU enumeration | River **byte-identical** to the CPU enumeration; flop 1081×1081 exact in **0.087 s** | exact | docs/STATE.md:117 | yes |
| 2026-08-30 | CFR+ correctness on a game with a known solution | `pokerbot/strategy/gpu_cfr.py`, clairvoyance toy | **bluff 0.333 / call 0.500 hit exactly; exploitability 0.014 %** | exact | docs/STATE.md:118-119 | yes |
| 2026-08-30 | Cross-validation against the independent OSS solver | `research/gpu_vs_texassolver.py`, identical spot | frequency deltas **0.007 / 0.000 / 0.001**; **per-combo correlation r = 0.999** | two independent solvers agree | docs/STATE.md:120-122 | yes — **but explicitly NO statement about the live-played policy** (../consults/TOP5_CONSULT_GPT6_2026-09-07.md:186, :4302) |
| 2026-08-30 | GPU utilisation / solve cost | `RiverCFRBatch` B=256 | **100 % GPU utilisation**, ~1000 subgame iter/s, **0.30 s/spot**; bandwidth-bound, TF32 ineffective | live-capable on the river | docs/STATE.md:119-120 | yes |
| 2026-08-30 | Solver audit of our own river decisions | `gpu_river_audit.py` over 571/571 river decisions of GTOW night 2 | check/fold solver-conformant (p 0.86 / 0.83); **bet is the weakest class (p 0.45; 15 % clear contradictions)**; disaster calls get solver fold p>0.95 | localisation of the river leak to the BET side | docs/STATE.md:123-126 | yes (basis of `river_wert_bremse`) |
| 2026-08-30 | Do the tracker thresholds carry the river defence? | discrimination measurement | **0.65 vs 0.53** | NO — explains why `r6_ecall` died | docs/STATE.md:126-127 | yes (negative result) |
| 2026-06-21 | Is our own oracle grossly broken? | `research/gtow_oracle_check.py` against 7,565 logged GTOW hands | preflop blueprint **93.8 % of GTOW's real actions in support** (n=6,203); postflop solver **90.1 % in-support, 64 % modal, mean prob 0.62** (n=172, 96 % solve coverage); weak point **turn: 86 % in-support, only 47 % modal** | oracle is NOT grossly broken → a speculative postflop solver rebuild was NOT justified | docs/STATE.md:1141 | yes — CAVEAT in the original: coarse (action FAMILY, not sizing/frequency; n=172 ±~5 %) |
| 2026-08-17 | Flop resolver first flight | 5 hands `PokerBot(use_flop_resolver=True)` vs GTOBaseline, `duplicate.py` pattern, gen_decks(5, seed=7) | **resolver fired 0 of 3 times**; cold solves 75.4 s / 89.3 s / 120.9 s (timeout); reached exploitability 8.47 / 8.67 % of pot (target acc 0.6 missed by far); the two converged solves still returned None: **hero combo not in its own 35-class range** (K5o/J8o) | construction site: every flop-resolver A/B currently measures only the floor plus a 75–120 s latency tax | data/runs/verdrahtungs_debug_2026-08-17.json:4 | yes, unchanged open |
| 2026-09-10 (today) | Formula/identity suite | `python -m tests.test_math_suite` | **20/20 checks passed, fuzz N=400/check** (among others pot odds exact, alpha/MDF, required_fold_equity against an independent Fraction solution, bluff-to-value indifference, exact river equity vs independent treys enumeration, MC turn equity within 5·SE, **chip conservation incl. side pots over 120 random 6-max hands**) | green | today's run; structure tests/test_math_suite.py:23-40 | yes — **the "17/17 deep" cited in CLAUDE.md:32 is superseded: today 20/20** |
| 2026-09-10 (today) | Coverage of the formula library | same run, section "UNVERIFIED formula functions" | **69 formula functions without an independent reference** (among others `equity_realization`, `expected_value`, the whole `strategy_formulas` block) | open gap, honestly reported | today's run of tests/test_math_suite.py | yes |
| 2026-08-17 | Reference integrity of the formula citations | `verify_refs` | **66/66** | green | docs/STATE.md:302; expectation documented ../plans/POD_PLAN.md:58 | yes (not re-run) |
| 2026-07-05 | EVPA arm pruning (geometric transfer) against TexasSolver | comparison measurement | **NO-OP** — the solver collapses over-all-in arms internally, ε identical to 1e-8 | negative; kept as a v4 building block, census-frequency pruning deliberately NOT built | docs/STATE.md:822-825 | yes (negative result) |

### 7. Runtime / throughput

| Date | What was measured | Instrument / channel | Result (number ± spread, n) | Verdict | Source (file:line) | Still valid? |
|---|---|---|---|---|---|---|
| 2026-07-05 | `decide()` latency after memoisation | profile + byte-identity gate (0 diffs over 6 arms × 70 spots) | **999 → 83 ms = 12.1×** (proven-pure memoisation of p_bet/p_defense/hand_features/evaluate + `_straight_outs`) | applied (commit 114e107) | docs/STATE.md:816-819 | yes — clarification: `decide()` itself is NOT memoised, memoised are `advisor.p_bet/p_defense`, `features._FEATURES_MEMO`, `evaluator._EVAL_MEMO`, wholesale clear at 120k/60k (../reports/V10_FACTS.md:103-105) |
| 2026-07-05 | Determinism root finding | 3 processes, same seed | `combos_for_classes` iterated a string SET → PYTHONHASHSEED-dependent combo order → **4/140 MC boundary decisions flipped**; separately measured: place 378/12/4 at identical seed | `sorted()` at the chokepoint; **all earlier "deterministic" instrument runs carried this jitter** | docs/STATE.md:819-822; docs/STATE.md:383-388 | yes — pairings remain valid (symmetric) |
| 2026-08-16 | Self-play throughput single-process | Autogym pilot | 500 hands + 3,577 graded decisions in **52 s (~580 hands/min)** | basis for the pod calculation | ../plans/AUTOGYM_PLAN.md:45 | yes |
| 2026-08-16 | Multiprocessing scaling locally | `pargate`, 24 cores, 40 min | **2,459 decks/min (~4,900 hands/min)**, scaling ~1.0×/core | G5 PASSED → for single gates the pod is unnecessary | ../plans/AUTOGYM_PLAN.md:133-134 | yes |
| 2026-08-16 | Advisor inference GPU vs CPU | micro-benchmark, batch 1300×20 | GPU **3.20 ms** vs CPU **3.52 ms** — launch+transfer eat the gain | **live inference stays CPU**; the GPU gets the bulk jobs | ../plans/GPU_PLAN.md:3-8 | yes |
| 2026-08-17 | Advisor batching on CPU | profile of the live loop | **2.2×** (batch-1 overhead removed) | applied | docs/STATE.md:303; ../plans/GPU_PLAN.md:5-6 | yes |
| 2026-08-31 | fp16 in the GPU river solver | measurement of the `half=True` option | **+64 %** throughput | measured, **default OFF** | docs/STATE.md:147 | yes |
| — (code fact, audited 2026-09-07) | River resolver latency live | `bot.py`/`resolver.py` audit + STATE reference | **~6 s per river decision (median 5.8 s)**; resolver-OFF 83 ms; resolver fired on 93 % of river decisions; TexasSolver timeouts river 90 s / turn 150 s / flop 240 s (census) | live cost of the solver | ../reports/V10_FACTS.md:77-86 | yes |
| 2026-09-07 | v10 vs v5 live latency | `research/v10_latenz`, n=10 identical states (reduced sample) | overall p99 **v10 7.55 s vs v5-H 5.54 s**; K2 trace: plan played 1/10, deadline 7/10, hand_not_in_range 2/10 | **G2 NOT GREEN**; after mechanics fix (3 threads, 3 s queue, 12 s deadline) n=40: deadline 0/40, plan 25/40, offtree 11/40, p99 10.15 s; full measurement n=150 **not run** | docs/STATE.md:72-76 + addendum 02:05 | yes (open) |
| 2026-09-08 | Export throughput in the PRINCE live channel | G5 Analyzer export | **11.6 s/hand** (TexasSolver waits) → export 200 instead of 1500 hands; 500 run aborted after 98 hands | Analyzer SE thereby ≈ 2.7× wider → only mechanics/tail grade, NO EV-loss comparison | ../reports/V10_GATES_REPORT.md:40 | yes |
| 2026-08-02 | Trainer grading budget | integration test of the coach path | prewarm left the first `decide()` cold: **1.6 s** of an 800 ms budget → after fix (throwaway record) **first hand 7.8 ms** | fixed; residual risk with uvicorn import string without `main()` documented | docs/STATE.md:493-495; ../plans/TRAINER_PLAN.md:431 | yes |
| 2026-08-04 | Snowie bridge throughput | see section 1 | 13.3 hands/min | — | docs/STATE.md:422 | yes |
| 2026-09-09 | MTT side tables | see section 3 | mean 120–129 ms, max ≈ 213 ms per hero hand | — | ../reports/TOURNAMENT_MODE.md:100-102 | yes |
| 2026-09-24 | Trainer in Pyodide (browser build, quantplay.io) | Node 24 + Pyodide 0.28.3, scratch spike against the mounted repo tree, script hero (check/call/fold) | import `six_server` **0.9 s**; GTO 8 hands/36 requests **0.56 s** (slowest 0.11 s); exploit/arena 6 hands each 0.21–0.24 s; 9-max 6 hands 0.22 s; **tournament 12 hands 3.51 s, slowest 0.35 s**; all 6 routes (feedback/replay/panel/report/analyze/glossary) 200 | browser version viable; ASGI path fails (no thread) → direct endpoint call | docs/STATE.md (block 2026-09-24); pokerbot/web/browser_bridge.py docstring | yes — first call additionally ~10 MB Pyodide download from the CDN |

---

### Explicitly outdated / no longer valid

* **"17/17 deep" for `tests/test_math_suite.py`** (CLAUDE.md:32) — **replaced**: today's run reports
  **20/20**; the suite has grown since the citation. In addition it reports 69 unverified formula functions.
* **All SNG ABSOLUTE VALUES before the night of 2026-08-04 (μ-1/μ-2/μ-3 ROI levels)** — the tournament engine then carried
  three confirmed defects (ante as a street bet, HU blind inversion, orphaned side-pot layer). The
  ARM DELTAS count as robust (paired), the absolute values shift (docs/STATE.md:368-370).
* **Snowie account balance −$2,915** — invalid as a bot verdict; it is attributed to 3 sealed automation
  error classes (dropouts/raise loop/decimal point). Valid is the cleaned pool
  (+3.2 bb/100, band [−37, +44], n=3,114) — and that is not significant.
* **6-max Analyzer grade 85.9 % / EV loss 7.61** — refers to the `tag` core BEFORE the flat fix of
  2026-09-09; not re-measured after the change (open item in docs/STATE.md:29-30).
* **Transferring `sel_guard`/AUSLESE guards to 6-max** — invalidated in advance by the 6-max catalogue v0: there
  is no flop overfold there (0.216 at an allowed 0.30). Not a measurement, but a prevented fallacy.

---

## Where the raw data lives

This channel is not a play channel: it does not measure bb/100 but **what physically lies on the disk** —
size, file count, format, producing code, git status. What it can do: say which published numbers
could be **recomputed** from existing raw data and which now stand only as a claim in a document.
What it **cannot** do: judge the quality or validity of those numbers — a large file
is not proof, and a missing raw data set does not make a number wrong, only unverifiable.

All sizes/file counts below were **measured on 2026-09-10 by directory walk** (`os.walk`, sum of
`st_size`), not taken from documents. File timestamps (mtime) give the content time span.

**Overall picture:** ~59.8 GB raw data, of which **58.5 GB in two gitignored trees** (`data/` 42.4 GB,
`models/` 16.1 GB). Versioned (git) are practically only `knowledge_base/` (28.6 MB) and `dataset/` (72.5 MB,
of which shards). Whoever clones the repo inherits **~100 MB**; whoever inherits the disk inherits ~59.8 GB. That is the
most important single statement of this section.

---

### 0. Inventory, top level

| Date | What was measured | Instrument / channel | Result (number ± spread, n) | Verdict | Source (file:line) | Still valid? |
|---|---|---|---|---|---|---|
| 2026-09-10 | Total size `data/` | os.walk sum | 42.4 GB, n=91,002 files, 40 subfolders | gitignored, not clonable | `.gitignore:8` (`data/`); path `data/` | yes (today's measurement) |
| 2026-09-10 | Total size `models/` | os.walk sum | 16.1 GB, n=214 files, 11 subfolders | gitignored | `.gitignore:12` (`models/`); `pokerbot/config.py:29` | yes |
| 2026-09-10 | Total size `tools/` | os.walk sum | 774.3 MB, n=24,655 (TexasSolver 156.0 MB/3,193 + gtow_client 578.8 MB/21,458) | gitignored, obtainable externally | `.gitignore:9` (`tools/`) | yes |
| 2026-09-10 | Total size `books/` | os.walk sum | 299.6 MB, n=56 files | de facto gitignored (`*.pdf`), only 2 .txt tracked | `.gitignore:13`; `git ls-files books` = 2 | yes |
| 2026-09-10 | Total size `dataset/` | os.walk sum | 72.5 MB, n=44; **42 files git-tracked** (incl. shards) | versioned | `git ls-files dataset` = 42 | yes |
| 2026-09-10 | Total size `knowledge_base/` | os.walk sum | 28.6 MB, n=115; **103 files git-tracked** | versioned | `git ls-files knowledge_base` = 103 | yes |

---

### 1. `data/runs/` — self-play gate runs (pargate/envgate/pargate6)

**Channel:** stores per A/B run the configuration, raw deck edges and verdict. With them μ, SE, bootstrap CI
and permutation tests can be **recomputed entirely**, without repeating the run. What it cannot do: say anything about
live opponents (GTOW/Snowie) — these are pure mirror/league numbers.

| Date | What was measured | Instrument / channel | Result (number ± spread, n) | Verdict | Source (file:line) | Still valid? |
|---|---|---|---|---|---|---|
| 2026-09-10 | Extent of `data/runs/` | os.walk | 99.0 MB, n=605 files; **91 timestamped run folders** (20260816_204232 … 20260909_215223) | complete, gitignored | `pokerbot/autogym/runs.py:17` (`RUNS = Path("data/runs")`) | yes |
| 2026-09-10 | Index coverage | line count | `INDEX.jsonl` = **79 lines** for 91 run folders | **12 runs without an index line** (exploit_jagd/round campaigns write no `result.json`) | `data/runs/INDEX.jsonl`; `pokerbot/autogym/runs.py:7` | yes |
| 2026-09-10 | Readable status report | line count | `STAND.md` table = **22 lines**, last entry 2026-08-17, addenda up to 2026-08-18 02:23 | **OUTDATED** versus INDEX (79) and disk (91) — generator not run for 3 weeks | `data/runs/STAND.md`; generator `pokerbot/autogym/bericht.py:29` | no — re-run `python -m pokerbot.autogym.bericht` |
| 2026-08-17 | Example run contents (`20260817_222907_pargate_turn_wert`) | file list | 3 files: `config.json` (207 B), `edges.json` (108,023 B = 29,920 deck edges in chips), `result.json` (372 B) | format stable; raw edges present → estimator replaceable | `data/runs/20260817_222907_pargate_turn_wert/{config,edges,result}.json` | yes |
| 2026-09-09 | Latest index schema | INDEX.jsonl last line | 26 fields incl. `ci95_lo/hi`, `perm_p`, `boot_b`, `aa_exakt_null`, `fingerprints`, `zaehler` | schema has **grown** over time — old lines have only 9 fields | `data/runs/INDEX.jsonl` (line 2 vs last line) | yes, but not retroactively |
| 2026-09-08 | v10 gate artefacts | file list | `data/runs/v10/` = 94.3 MB, n=319 (of which `policy_oracle_cache/` 6.0 MB/193, `_alt_policy_oracle_cache_v1/` 577.3 KB/17, `g4_logs/` 4) | complete; G1–G5 evidence incl. ledger JSONL | `research/g1_gate_runner.py:21`; `pokerbot/benchmark/gtow_ledger.py:15` | yes |
| 2026-08-18 | Fable adversary duel | file list | `data/runs/fable_duell/` = 4.0 KB, **n=1 file** | thin — the 62-hand duel practically does not exist as a raw data set | `research/fable_duell.py:21` (`D = Path("data/runs/fable_duell")`) | restricted |
| 2026-09-10 | Deck banks (pargate) | file list | `data/_pargate_blocks/` = 12.9 KB, n=240 in 5 bank folders (48 `jobNNN.json` each); banks `b1080000`–`b1110000` | consumed banks are marked (`_STALE_…`) | `data/_pargate_blocks/` (folder names) | yes |
| 2026-09-10 | Kaggle/OpenSpiel channel | log head | 4 logs (4.6–5.3 KB); `kaggle_v10h0_vs_champion_2026-09-10.log:1` = `OpenSpiel exception: Unknown game 'universal_poker'` | **channel did not run** — the logs contain no results, only the error | `data/runs/kaggle_v10h0_vs_champion_2026-09-10.log:1` | no (defective) |

---

### 2. `data/autogym/` — the journal

**Channel:** append-only decision log of the Autogym loop. It is the only place where
**discarded** arms also stand with their justification. It contains no raw data, only verdicts + finding texts.

| Date | What was measured | Instrument / channel | Result (number ± spread, n) | Verdict | Source (file:line) | Still valid? |
|---|---|---|---|---|---|---|
| 2026-09-10 | Journal extent | line count | `journal.jsonl` = 64,360 B, **n=123 lines**; first 2026-08-16 19:25:54, last 2026-09-10 02:13:18 | gapless, actively maintained | `data/autogym/journal.jsonl`; writer `pokerbot/autogym/improver.py:28` | yes |
| 2026-08-16 | Pilot reports | file list | 3 `report_*.json` (2,022 / 2,375 / 2,423 B) of 2026-08-16 | one-off, pilot phase only | `data/autogym/report_20260816_*.json` | historical |
| 2026-09-10 | Last entry (type) | journal read | `AIVAT-KAGGLE-ENTWURF`, verdict `"ENTWURF (nicht gebaut)"` | honestly marked as **not built** | `data/autogym/journal.jsonl` (last line) | yes |

---

### 3. `data/sessions/` — played hands (trainer, HU app, GTOW)

**Channel:** raw hand histories from all play channels. From `gtow_hands_*.jsonl` AIVAT means,
street decompositions and frequency censuses can be **recomputed** — they carry per hand `aivat`, `winnings`, `board`,
`history` and **both** hole cards. What the channel cannot do: cover Snowie hands (no showdown logging).

| Date | What was measured | Instrument / channel | Result (number ± spread, n) | Verdict | Source (file:line) | Still valid? |
|---|---|---|---|---|---|---|
| 2026-09-10 | Total extent | os.walk | `data/sessions/` = 56.7 MB, n=482 files | gitignored | `.gitignore:8` | yes |
| 2026-09-10 | Trainer/6-max sessions | line count over glob | `session_*.jsonl`: **218 files, 6,842 lines (hands), 11.2 MB** | present, but very small per file (Ø ~31 hands) | writer `pokerbot/web/six_server.py:97`; reader `pokerbot/analysis/harvest_play.py:17` | yes |
| 2026-09-10 | Decision logs | line count over glob | `decisions_*.jsonl`: **175 files, 11,840 lines, 39.4 MB** | contract: one `decisions_<sid>` per `session_<sid>` — 175 vs 218 ⇒ **43 sessions without a decision log** | `pokerbot/coach/autotest.py:110` (contract) | yes, with a gap |
| 2026-09-10 | GTOW hand histories | line count over glob | `gtow_hands_*.jsonl`: **65 files, 24,050 hands, 5.8 MB**; time span 2026-06-16 … 2026-08-18 | **the most valuable raw data set of the project** — every line with AIVAT + both hole cards | `research/analyze_gtow_hands.py:1`; example line `data/sessions/gtow_hands_1783381570.jsonl:1` | yes |
| 2026-09-10 | HU app sessions | line count | `hu_*.jsonl`: 11 files, 169 lines, 0.2 MB | very thin | `data/sessions/hu_*.jsonl` | yes, but n too small for statements |
| 2026-08-18 | GTOW run manifest | JSON read | 7 files assigned: smoke20_v1_CRASH n=18 (`"NICHT werten"`), smoke20_v2 n=20 AIVAT −21.34, smoke100 n=100 AIVAT −59.03, nacht1 chunkA–D n=500/500/497/500 AIVAT −26.59/−54.98/−31.65/−48.37 | assignment file→arm **documented**, incl. the discarded crash run | `data/sessions/gtow_manifest_2026-08-18.json` | yes (the night-1 numbers count per CLAUDE.md as "bare gym config", not a v4 verdict) |
| 2026-08-18 | Arm fingerprint in the manifest | JSON read | `arm_v4`: `AUSLESE_STACK=r6_button`, `TURN_DEFENSE=0.07`, `SLOWPLAY=0.25`, `RAISE_NARROW=1.0`, `RESOLVER=0`, `TURN_RESOLVER=0` | reproducible — env config is stored alongside | `data/sessions/gtow_manifest_2026-08-18.json` (block `arm_v4`) | yes |

---

### 4. `data/gtow_upload/` — Analyzer exports (PokerStars HH format)

**Channel:** the files that were uploaded via Chrome into the GTO Wizard Analyzer. They allow an
Analyzer grade to be **repeated**, not recomputed (the EV-loss numbers only arise inside the Analyzer).
Attention: hand IDs burn on first contact — the same file cannot be uploaded again.

| Date | What was measured | Instrument / channel | Result (number ± spread, n) | Verdict | Source (file:line) | Still valid? |
|---|---|---|---|---|---|---|
| 2026-09-10 | Extent | os.walk / ls | 55.8 MB, n=76 files (36 entries at the top level) | fully preserved | `data/gtow_upload/` | yes |
| 2026-07-04/05 | The 1500 arms (paired exports) | ls -S | `sixmax_hands_1500.txt` 1.72 MB · `hu_v31_1500` 1.01 MB · `hu_v3_1500` 1.00 MB · `hu_gtomode_fix_1500` 1.00 MB · `hu_v22_1500` 0.999 MB · `hu_hands_1500` 0.997 MB · `hu_head_s55_1500` 0.996 MB · `hu_v32_1500` 0.988 MB · `hu_gtomode_1500` 0.987 MB | the arms of the v2.2/v3 Analyzer comparisons are **all** still present | `data/gtow_upload/*_1500.txt` | yes as evidence; **not** re-uploadable (hand-ID burn, CLAUDE.md rule) |
| 2026-06-28/29 | older arms | ls -S | `river_1000.txt` 876 KB, `bot_hands_1000.txt` 663 KB, `bot_hands_1000_ontree.txt` | historical (pre-PRINCE era) | `data/gtow_upload/` | historical |

---

### 5. `data/census/` + `data/freq_targets/` — the mined GTOW teacher

**Channel:** target frequencies distilled from the logged GTOW hands and the measured sizing tree of the
opponent. This is derived, not raw evidence — recomputable from `data/sessions/gtow_hands_*.jsonl`.

| Date | What was measured | Instrument / channel | Result (number ± spread, n) | Verdict | Source (file:line) | Still valid? |
|---|---|---|---|---|---|---|
| 2026-07-05 03:02 UTC | GTOW frequency targets | `research/freq_mine.py` over 47 hand files | `gtow_frequencies.json` 107,534 B; meta.stats: **hands=13,675**, gtow_decisions=26,823, hero_seat0=6,795 / hero_seat1=6,781, **hero_unknown=99**, xcheck_agree=11,633 | robust, but with a documented caveat: "GTOW's HU play conditioned on OUR lines" | `data/freq_targets/gtow_frequencies.json` (block `meta.stats`); producer `research/freq_mine.py:15` | yes — reproducible, but the data set grows (today 24,050 hands ⇒ **re-mining would yield different n**) |
| 2026-07-05 19:34 | GTOW raise composition | `research/raise_mine.py` | `gtow_raise_ranges.json` 1,826 B; e.g. `flop|srp|normal`: air 115 / top-pair 27 / pair 31 / two-pair+ 36 / monster 4 | thinly populated; the code itself warns: "jams pooled across streets (n=29 — small…)" | `data/freq_targets/gtow_raise_ranges.json`; warning `pokerbot/strategy/range_tracker.py:91` | yes, with an explicit n caveat |
| 2026-07-04 16:51 | GTOW sizing tree (census) | `research/gtow_tree_census.py` | `gtow_tree.json` 6,631 B; e.g. `flop\|bet\|SRP`: 0.35→1015, 0.75→240, 1.6→26 … | basis of the off-tree snap in `postflop.py` | `data/census/gtow_tree.json`; reference `pokerbot/strategy/postflop.py:41`; "12.5k hands" `research/gtow_tree_census.py:3` | yes |
| 2026-07-04 | Duplicate censuses | file list | `dup_head.json` 3,105 B, `dup_mode.json` 2,932 B, `_dbg.json` 625 B | small, context artefacts | `data/census/` | historical |

---

### 6. Gate instruments: `stress/`, `gtow_grades/`, `dup_ab/`, `cleanup_baseline/`

**Channel:** preserved result snapshots of the PRINCE-era gates. They prove that a gate ran; they
contain no raw deck data, so a new estimator is **not** possible here.

| Date | What was measured | Instrument / channel | Result (number ± spread, n) | Verdict | Source (file:line) | Still valid? |
|---|---|---|---|---|---|---|
| 2026-07-05/06 | Stress-suite arms | file list | `data/stress/` 365.6 KB, n=20; 19 `_worker_*.json` (2–18 KB each) + `stress_report.json` 55,135 B; arms: gto, head, prince, prince_aggro/bd/obm/probe/pur/rcd, v23, v3, v31, v32, v33, v34, v35, v5a, v5b, v5c | complete arm coverage of the v2.2→v5 ladder | `data/stress/stress_report.json`, `data/stress/_worker_prince_v3*.json` | historical (PRINCE era), code state changed since |
| 2026-07-04/05 | Analyzer grades + leak maps | file list | `data/gtow_grades/` 64.3 KB, n=9: `gtomode_graded_100.json` 17,179 B, `gtomode_paired_s55.json` 1,247 B, `hu_leaks_ev2.json` 6,842 B, `sixmax_leaks_ev2.json` 2,742 B, `leaderboard_2026-07-04.json` 4,791 B, `error_prognosis.json` 17,270 B, `LEAK_MAP.md` 4,644 B | the HU-53.4 %/6max-85.9 % era is preserved as JSON | `data/gtow_grades/` | historical — the associated bb/100 anchors are superseded per CLAUDE.md |
| 2026-07-05 | Duplicate A/B snapshots | file list | `data/dup_ab/` 62.8 KB, n=16 (`fix_off/on.json`, `p4_lineu.json`, `p4_lineu_ecall.json`, `p4_off.json`, `probe_on.json` …) | small, aggregates only | `data/dup_ab/` | historical |
| 2026-07-05 | Refactor byte-identity baseline | file list | `data/cleanup_baseline/` 440.1 KB, n=5 (`final_A.json`, `run_A.json`, `run_H0_A.json`, `stress_baseline.json`, `profile_baseline.txt`) | the gate of the clean-code doctrine | `data/cleanup_baseline/` | historical (refers to the code state of that time) |

---

### 7. Solver caches — the largest and most expensive block

**Channel:** memoised TexasSolver solutions. They make `decide()` fast and the advisor training data
possible in the first place. They are **regenerable, but expensive** (CPU weeks) and **not** versionable.

| Date | What was measured | Instrument / channel | Result (number ± spread, n) | Verdict | Source (file:line) | Still valid? |
|---|---|---|---|---|---|---|
| 2026-09-10 | Live solve cache | os.walk | `data/_solve_cache/` = **35.0 GB, n=12,379 JSON** (SHA1-named, ~46 KB each, tree with `actions`/`childrens`/`node_type`); last write 2026-09-10 02:22 | **the largest single item of the project** and actively in use | `pokerbot/strategy/gto_oracle.py:55` (`_CACHE_DIR = … "data"/"_solve_cache"`); example `data/_solve_cache/000610f057712f0a438bcb52bc517a3c73c4ad97.json` | yes |
| 2026-06-19 | Turn solves (4-card boards) | os.walk | `data/_gto_turn_cache/` = **1.1 GB, n=22,571** (file name = board, e.g. `2c2d4h7d.json`) | feed for `defense_data` | `research/build_defense_data.py:26` (`TURN_CACHE`) | yes |
| 2026-06-18 | River subgame solves | os.walk | `data/_gto_river_cache/` = 162.0 MB, n=3,336 | feed for `river_data` + floor_map | `research/build_river_data.py:18`; `pokerbot/benchmark/floor_map.py:92` | yes |
| 2026-06-14 | Benchmark cache | os.walk | `data/_gto_bench_cache/` = 69.8 MB, n=1,340 | basis of the calibration runs | `pokerbot/benchmark/gto_benchmark.py:27`; `research/analyze_cache.py:14` | yes |
| 2026-06-15 | Short-deck cache | os.walk | `data/_gto_shortdeck_cache/` = 41.7 MB, n=434 | side branch (short deck), otherwise unused | `research/build_sd_advisor_data.py:14` | yes, but a side line |
| 2026-06-14 | Cover cache | os.walk | `data/_gto_cover_cache/` = 7.3 MB, n=143 | small | `data/_gto_cover_cache/` | historical |
| 2026-06-14 | Packed GCP cache | ls | `data/gcp_solve_cache.tgz` = 409,529,467 B (390.6 MB) | archive of a cloud solve run; never unpacked and checked | `data/gcp_solve_cache.tgz` | unclear (see "Open") |

---

### 8. Advisor training data (the `.pt` nets feed on this)

**Channel:** sequence data sets from the solver caches. With them the four advisor MLPs could be
**completely retrained**. Without them the `.pt` in `knowledge_base/postflop/` are black boxes.

| Date | What was measured | Instrument / channel | Result (number ± spread, n) | Verdict | Source (file:line) | Still valid? |
|---|---|---|---|---|---|---|
| 2026-06-16 | Defense training data | ls | `data/defense_data.jsonl` = 845,218,860 B (806.1 MB) | largest single file outside the caches | `data/defense_data.jsonl`; producer `research/build_defense_data.py:25` | yes |
| 2026-06-29 | River line-aware | ls | `data/river_data_la.jsonl` = 458,637,311 B (437.4 MB) + `river_la_smoke.jsonl` 6,126,101 B | the line-aware river data set (net was "EV-neutral" per memory, data lies there nonetheless) | `data/river_data_la.jsonl` | yes |
| 2026-06-15 | Advisor (turn/river) | ls | `data/advisor_data.jsonl` = 88,945,399 B (84.8 MB) | listed in `DATA_CATALOG.md` as `data.advisor` | `DATA_CATALOG.md` (table "Big training files"); path `data/advisor_data.jsonl` | yes |
| 2026-06-15 | River | ls | `data/river_data.jsonl` = 81,633,953 B (77.9 MB) | ” | `DATA_CATALOG.md`; `data/river_data.jsonl` | yes |
| 2026-06-15 | Short-deck advisor | line count (CATALOG) | `data/sd_advisor_data.jsonl` = 17,801,128 B (17.0 MB), **199,720 lines** | side line | `DATA_CATALOG.md` (`data.sd_advisor`) | yes |
| 2026-06-16 | CFV shards | os.walk | `data/cfv_shards/` = 5.6 MB, n=5 (`cfv_dataset.jsonl`, `shard_0..2`, `pilot_local`) | remainder of the CFV-net episode | `data/cfv_shards/` | historical |

---

### 9. Population and opponent data (foreign hand histories)

**Channel:** real hand histories of foreign pools. With them opponent profiles (VPIP/PFR/fold rates) and
ecology simulations can be recomputed. **Not** computable from them: our own bb/100 — we did not play there.

| Date | What was measured | Instrument / channel | Result (number ± spread, n) | Verdict | Source (file:line) | Still valid? |
|---|---|---|---|---|---|---|
| 2026-07-26 | PokerStars tournament field | os.walk | `data/ps_tourney/hh/` = 18.3 MB, **n=145** `hhDealer.com_*.txt`; evaluation `ps_tourney_field.json` 2,886 B; 12 duel runs (`psduel*_w*.json`, 4.5–7.2 KB) | evidence of the ICM-tightening finding | `data/ps_tourney/`, `data/ps_tourney_field.json` | yes |
| 2026-08-04 | MTT bot runs | ls | `data/mtt/` = 135.8 KB, n=8 (`bots_w0..w5.json` + 2) | worker aggregates of the tournament arena | `data/mtt/` | yes |
| 2026-08-02 | Pluribus reference | ls / JSON | `knowledge_base/hand_histories/pluribus_hands.jsonl` = 9,595,089 B, **10,000 hands**; `pluribus_stats.json`: net **−7.09 bb/100**, VPIP 26.4 / PFR 17.7, per position n=1,638–1,692 | **git-versioned** — the only large raw data set in the repo | `knowledge_base/hand_histories/pluribus_stats.json`; `git ls-files knowledge_base/hand_histories` | yes |

---

### 10. `data/vision/` — the PokerSnowie bridge

**Channel:** raw screen material + vision regression cases. With them recognition errors can be
**reproduced** (preserved failure scenes); playing strength cannot be derived from them.

| Date | What was measured | Instrument / channel | Result (number ± spread, n) | Verdict | Source (file:line) | Still valid? |
|---|---|---|---|---|---|---|
| 2026-08-04 | Total extent | os.walk | `data/vision/` = **853.6 MB, n=37,774** | second-largest `data/` block after the caches | `data/vision/` | yes |
| 2026-08-04 | Screen recordings | os.walk | `data/vision/rec/` = 715.3 MB, n=5,896 in 6 run folders (`20260804_031409` … ) — JPG frames `f_<epoch_ms>.jpg`, ~838 frames per run | pure frames, no audio/meta — assignment only via timestamp | `data/vision/rec/20260804_031409/f_1785806049639.jpg` | yes |
| 2026-08-04 | Template/glyph library | os.walk | `data/vision/snowie/` = 32.0 MB, **n=31,241** files | the heart of the template matching | `data/vision/snowie/`; user `pokerbot/vision/snowie_local.py` | yes |
| 2026-08-04 | Archive run 2 | os.walk | `data/vision/lauf2_archiv/` = 80.9 MB, n=369 | one of the three marathon runs | `data/vision/lauf2_archiv/` | yes |
| 2026-08-04 | Failure cases + audit | os.walk | `fails/` 4.7 MB n=21 · `audit/` 6.9 MB n=51 · `review/` 45.8 KB n=33 · `review2/` 7.3 KB n=5 | the preserved crime scenes of the 5-case regression net | `data/vision/fails/`; net `research/snowie_regress.py` | yes |

---

### 11. `models/` — Qwen/GLM bridge (the brain track)

**Channel:** LoRA adapters and training metrics. With these the brain track could be **revived**; according to
CLAUDE.md it is secondary. What is not here: the base models (Qwen3-8B/GLM-Z1-9B) — they would have to be downloaded again.

| Date | What was measured | Instrument / channel | Result (number ± spread, n) | Verdict | Source (file:line) | Still valid? |
|---|---|---|---|---|---|---|
| 2026-09-10 | Total | os.walk | 16.1 GB, n=214 | gitignored, **only copy** (no remote) | `.gitignore:12` | yes |
| 2026-06-20 | Product baseline GLM | ls | `models/grpo_slim.tgz` = 708,329,284 B (675.5 MB); `grpo_slim_baseline.tgz` 705,895,142 B | per CLAUDE.md "**the PRODUCT**" of the brain track (≈ −40 robust) | `models/grpo_slim.tgz`; CLAUDE.md block "CURRENT BRAIN" | yes as an artifact; the track itself is secondary |
| 2026-06-21 | GRPO adapter (unpacked + archive) | os.walk / ls | `models/qwen_poker_grpo/` 1.3 GB n=26; `qwen_poker_grpo.tgz` 708,092,681 B; `qwen_poker_grpo_live.tgz` 709,697,392 B | three copies of the same state | `models/qwen_poker_grpo*` | yes (redundant) |
| 2026-06-19/20 | SFT archives | ls | `qwen_poker_sft.tgz` 2,805,408,022 B (2.6 GB); `sft_new.tgz` 2,124,995,948 B; `sft_slim.tgz` 705,866,733 B | large block, redundancy unchecked | `models/*.tgz` | yes |
| 2026-06-14 | Early 8B checkpoint | ls | `models/qwen_poker_ckpt500/`: `adapter_model.safetensors` 698,419,728 B + `adapter_config.json` 1,140 B + `trainer_state.json` 8,728 B | marked ⚠️ "historical" in `DATA_CATALOG.md` | `DATA_CATALOG.md` (`model.poker_ckpt500`) | historical |
| 2026-06-14 | 32B LoRA | ls | `data/qwen32b_lora.tgz` = 1,988,149,853 B (1.85 GB) — sits **in `data/`, not in `models/`** | storage inconsistency | `data/qwen32b_lora.tgz` | yes |
| 2026-06-17/18 | Local 1.7B proofs | os.walk | `qwen_local_sft/` 2.5 GB n=73 (6 checkpoints) · `qwen_local_grpo/` 964.6 MB n=31 · `qwen_1.7b_aligned/` 964.6 MB n=29 · `qwen_local_sft_aligned/` 554.3 MB n=18 · `qwen_smoke/` 554.3 MB n=18 | the frac_bad proofs (0.97→0.00) | `DATA_CATALOG.md` (`model.local_sft`, `model.local_grpo`) | yes as evidence |
| 2026-06-18 | Empty placeholders | os.walk | `models/qwen_8b_local_sft/` **0 B / 0 files**, `models/qwen_combined_sft/` **0 B / 0 files** | empty — `DATA_CATALOG.md` wrongly lists `sft_aligned` as "EMPTY", although 554.3 MB sit there | measured `models/`; claim `DATA_CATALOG.md` (`model.sft_aligned`: "EMPTY … 18 files · 554.3M") | **CATALOG contradiction, see "Open"** |
| 2026-06-18/21 | Training metrics | ls | `models/grpo_metrics.jsonl` 12,225 B; `data/training_metrics.jsonl` 72,897 B; `data/gpu_load.jsonl` 385,946 B; `data/local_grpo_metrics.jsonl` 3,914 B | curves can be redrawn | `models/grpo_metrics.jsonl` | yes |

---

### 12. `dataset/shards/` — "the gold" (versioned)

**Channel:** the DSL training data. The only large data holding that a clone **receives**.
Line counts below come from `DATA_CATALOG.md` (generated 2026-06-20), sizes from today's measurement.

| Date | What was measured | Instrument / channel | Result (number ± spread, n) | Verdict | Source (file:line) | Still valid? |
|---|---|---|---|---|---|---|
| 2026-09-10 | Size | os.walk | `dataset/shards/` = 71.9 MB, n=22 files; **git-tracked** | inheritable via clone | `git ls-files dataset` (42 entries incl. shards) | yes |
| 2026-06-20 | SFT gold (active) | `dataset/build_manifest.py` | `a_contract` 1,750 lines/1.8 M · `c_decide` 3,250/3.2 M · `solver` 2,617/1.7 M · `hu_blueprint` 12,168/6.6 M | the four active gold shards | `DATA_CATALOG.md` (table "SFT gold") | yes |
| 2026-06-20 | Excluded (documented) | `dataset/registry.py` | `solver_mass` 25,586 lines/16.2 M — `current=False`; reason verbatim: "DROWN the 2.2k Claude-teacher postflop gold 13:1" | **negative result, cleanly preserved with its reason** | `dataset/registry.py` (asset `shard.solver_mass`, `note=`) | yes |
| 2026-06-20 | Empty/stale shards | `DATA_CATALOG.md` | `b_ground` 0 lines, `d_exploit` 0 lines, `local_kb` 11,599/10.7 M (⚠️ "the original frac_bad=0.97 cause"), `sample` 253 | honestly marked ⚠️ | `DATA_CATALOG.md` (table "Other shards") | yes |
| 2026-06-21 | `.off.bak` duplicates | ls | 4 backup copies versioned along: `a_contract.jsonl.off.bak` 1,890,272 B, `c_decide…` 3,349,171 B, `hu_blueprint…` 2,875,105 B, `solver…` 1,743,795 B | ~9.8 MB redundant **in Git** | `git ls-files dataset/shards` | yes (can be cleaned up) |
| 2026-06-20 | Missing | `DATA_CATALOG.md` | `shard.teacher` = "—(missing)" per CATALOG, but `dataset/shards/teacher.jsonl` sits on disk with 1,904,360 B | **CATALOG stale** — the file has existed since 2026-06-20 17:34 | measurement `data`/`dataset/shards/teacher.jsonl`; claim `DATA_CATALOG.md` (`shard.teacher`) | CATALOG line no longer valid |

---

### 13. `knowledge_base/` — versioned theory + trained nets

**Channel:** the only directory that strategy code **hard-references** (`pokerbot/config.py:15,30`).
Moving it breaks the bot.

| Date | What was measured | Instrument / channel | Result (number ± spread, n) | Verdict | Source (file:line) | Still valid? |
|---|---|---|---|---|---|---|
| 2026-09-10 | Size + Git | os.walk / git | 28.6 MB, n=115; **103 tracked** | ⇒ 12 files sit in it untracked (mostly `.pt`, excluded via `.gitignore:18`) | `git ls-files knowledge_base`; `.gitignore:18` (`*.pt`) | yes |
| 2026-09-10 | Subfolders | os.walk | `exploit/` 7.5 M n=11 · `hand_histories/` 14.2 M n=43 · `ranges/` 2.5 M n=11 · `math/` 1.7 M n=17 · `concepts/` 1.5 M n=2 · `postflop/` 696.6 K n=9 · `theory/` 309.5 K n=18 · `cfr/` 168.2 K n=1 · `tournament/` 4.4 K n=1 | complete | `knowledge_base/` | yes |
| 2026-06-20 | Deviation from CATALOG | comparison | CATALOG lists `postflop/` 8 files/671.6 K and `theory/` 16/284.3 K — measured are **9/696.6 K** and **18/309.5 K** respectively | **DATA_CATALOG.md is stale** (as of 2026-06-20) | `DATA_CATALOG.md` (table "knowledge_base/ subdirs") vs measurement 2026-09-10 | CATALOG numbers no longer valid |
| 2026-06-20 | The four advisor nets | `DATA_CATALOG.md` | `advisor.pt` 23.9 K (+63 % vs strength-only) · `turn_advisor.pt` 23.9 K (+46 %) · `river_advisor.pt` 24.3 K (+18 %) · `defense_advisor.pt` 25.8 K ("_verify live wiring_") | tiny, but **gitignored** ⇒ a clone does not have them | `DATA_CATALOG.md` (table "Trained postflop advisors"); `.gitignore:18` | yes — and that is an inheritance risk |
| 2026-06-20 | Playbooks / ranges | `DATA_CATALOG.md` | `exploit/playbook.jsonl` 11,520 lines/7.2 M · `postflop/openai_strategy.json` 30.7 K (62 rules) · `ranges/preflop_blueprint.json` 85.8 K · `cfr/preflop_pushfold.json` 168.2 K | versioned, inheritable | `DATA_CATALOG.md`; `pokerbot/config.py:15,30` | yes |
| 2026-08-04 | Tournament doctrine | os.walk | `knowledge_base/tournament/` = 4.4 KB, **n=1** (`DOKTRIN.md`) | the extracted Sklansky/ICM doctrine is exactly **one** file | `knowledge_base/tournament/DOKTRIN.md` | yes |

---

### 14. `books/` — the source library

**Channel:** the PDF sources from which `knowledge_base/` was extracted. Only the **extraction** can be recomputed
from them, nothing about play. In practice not inheritable via clone (`*.pdf` gitignored).

| Date | What was measured | Instrument / channel | Result (number ± spread, n) | Verdict | Source (file:line) | Still valid? |
|---|---|---|---|---|---|---|
| 2026-09-10 | Size | os.walk | 299.6 MB, n=56; **2 files tracked** (both `.txt` notes) | the library is NOT in the repo | `git ls-files books`; `.gitignore:13` | yes |
| 2026-07-07 | Poker books | ls | `books/poker/` 191.1 MB, n=10: Modern Poker Theory 113.9 MB · NLHE Theory&Practice 18.0 MB · Beyond GTO 16.3 MB · Theory of Poker 14.2 MB · Play Optimal Poker 2 7.9 MB · Surfing Uncertainty 9.3 MB · Exploitative Poker 5.7 MB · Mathematics of Poker 5.2 MB + folder `Tournament play` (2 PDFs) | 8 PDFs + 2 tournament PDFs — CLAUDE.md speaks of "the 6 poker books" | `books/poker/` | holdings yes; the "6 books" wording in CLAUDE.md is outdated (10) |
| 2026-08-07 | Papers | ls | `books/papers/` 85.2 MB, n=39 in 13 entries; `CFR/` with 10 PDFs (incl. `2605.19928v1.pdf` = Li&Huang, `EVPA !.pdf`, `Harvard 2022.pdf`); individually: `Pluribus.pdf`, `Supremus.pdf`, `Springer - Nash + Incomplete Information.pdf`, `MIT about Poker.pdf` | the references cited in CLAUDE.md are physically present | `books/papers/CFR/2605.19928v1.pdf`; `books/papers/Springer - Nash + Incomplete Information.pdf` | yes |
| 2026-08-04 | Mindset / AGT | ls | `books/#Mindset/` 2.1 MB n=2; `books/Algorithmic Game theory/` 520.5 KB n=1 (`2605.10900v1.pdf`) | peripheral holdings | `books/#Mindset/`, `books/Algorithmic Game theory/` | yes |
| 2026-06-13/16 | Extracted book texts | ls | `data/text/` 2.5 MB n=4 (`mathematics_of_poker.txt`, `modern_poker_theory.jsonl`, `nlhe_theory_practice.jsonl`, `theory_of_poker.jsonl`); `data/chunks/all_chunks.jsonl` 1.5 MB; `data/page_images/` 150.9 MB n=269 | the intermediate extraction stage is present ⇒ extraction is traceable | `data/text/`, `data/chunks/all_chunks.jsonl` | yes |

---

### 15. Personal / non-core storage

| Date | What was measured | Instrument / channel | Result (number ± spread, n) | Verdict | Source (file:line) | Still valid? |
|---|---|---|---|---|---|---|
| 2026-08-16 | Reports (mixed) | ls | `data/reports/` (today poker reports only) | **Addendum 2026-09-10:** all parts unrelated to the project (geopolitics model with its report, personal psychology documents, graphics of a relationship analysis) were moved out of the repo | `Desktop/PokerB_ausgelagert_2026-09-10/LIESMICH.txt` | done |

---

### 16. Open / unclear (cannot be resolved without re-measurement)

- **`DATA_CATALOG.md` is stale** (generated 2026-06-20). Three documented contradictions to today's measurement:
  `shard.teacher` "—(missing)" vs 1,904,360 B on disk; `model.sft_aligned` "EMPTY" vs 554.3 MB/18 files;
  `knowledge_base/postflop` 8 files vs 9 measured. Fix: `python -m dataset.build_manifest`.
  Source: `DATA_CATALOG.md` vs measurement 2026-09-10.
- **`data/runs/STAND.md` is stale** (22 table rows, last run 2026-08-17) compared with 79 INDEX rows
  and 91 run folders. All runs from 2026-08-18 on (incl. the v10 gates and the `pargate6` flat-fix runs of
  2026-09-09) are missing there. Source: `data/runs/STAND.md`, `data/runs/INDEX.jsonl`, `ls -d data/runs/20*/`.
- **12 run folders without `result.json`/index row** (`exploit_jagd`, `runde4_kampagne`, `runde5_sweep` and others) —
  their results exist only in the journal, not as recomputable raw data. Source: `data/runs/INDEX.jsonl`
  (79) vs 91 folders.
- **The Kaggle/OpenSpiel channel (2026-09-10) does not run**: all four logs begin with
  `Unknown game 'universal_poker'`. Whether results appear later in the same log was not checked.
  Source: `data/runs/kaggle_v10h0_vs_champion_2026-09-10.log:1`.
- **`data/gcp_solve_cache.tgz` (390.6 MB), `data/runpod_hu_turns.tgz` (209.1 MB), `data/qwen32b_lora.tgz`
  (1.85 GB)** — never checked unpacked; content and redundancy with the unpacked trees unknown.
- **Redundancy in `models/`**: `qwen_poker_grpo/` (unpacked) + `qwen_poker_grpo.tgz` + `qwen_poker_grpo_live.tgz`
  occupy ~2.7 GB for presumably the same state; not compared by hash.
- **Inheritance risk**: the four advisor `.pt` files (together ~98 KB) are gitignored (`.gitignore:18`), but are
  hard-referenced by `pokerbot/config.py:30`. A fresh clone does not have them — and without
  `data/*_data.jsonl` (1.4 GB, also gitignored) they cannot be retrained. This is the
  most dangerous gap on the whole map.
- **Repo boundary:** the files in `data/` unrelated to the project (geopolitics model with its report, personal
  psychology documents, graphics of a relationship analysis) were **moved out of the repo on 2026-09-10**,
  to `Desktop/PokerB_ausgelagert_2026-09-10/` with a LIESMICH.

---

## Addendum and corrections

All numbers here were checked against the repo (read-only). Where I recomputed or re-ran something myself,
this is stated explicitly. Line numbers apply to HEAD `e8248e1` (2026-09-10 02:38).

**Preliminary remark that supersedes everything else:** the journal grew during the collection — today it has
**124** lines, not 123. The new entry `data/autogym/journal.jsonl:124` (2026-09-10 02:38:07,
`typ: KAGGLE-MESSUNG-UNGUELTIG`) declares **two** Kaggle measurements invalid that are still listed as valid in
four parts of the collection. Details under C-V1/C-V2.

---

### (a) Measurements added

#### A1 — Slumbot (external HU bot, raw, unpaired)

*What the channel can do:* a free external second opinion on the overall HU policy against a
near-GTO opponent. *What it cannot do:* no AIVAT correction, no deck pairing, no decision
attribution — the SE is large (±73 at n=500), small samples demonstrably lie here by a factor of 70.
In the collection Slumbot only appears as a 1.7B brain number (−72, `05_llm.md:92`); the engine channel is missing entirely.

| Date | What was measured | Instrument / channel | Result | Verdict | Source (file:line) | Still valid? |
|---|---|---|---|---|---|---|
| 2026-06-22 | Game engine `PokerBot(exploit=False)` vs Slumbot | `research/slumbot_collect.py`, raw, unpaired | **+12.6 bb/100 (n=500, ±73.2)**; earlier partial run ~−35/−46 (n=580) | ≈ break-even; the engine is **not** bad against Slumbot | `memory/engine-vs-slumbot-breakeven.md` | yes — corrects every "−46 = bad" reading |
| 2026-06-22 | Error autopsy of the 18 largest losses (Slumbot's showdown cards revealed) | `research/slumbot_mistakes.py` | **~½ coolers (−51k chips, irreducible), ~½ fixable −EV betting (−26k chips: hero bets weak/air, Slumbot calls), 0 losses from folding** | no overfold leak; the leak is over-aggression against a caller | `memory/engine-vs-slumbot-breakeven.md` | yes — structurally identical to the GTOW tail finding |
| — | Small-sample lie in the same channel | same | **−871 bb/100 at n=40** (fully recovered); **−374** was the wrong bot (`slumbot_llm --bot solver`, `SolverSlumbotBot`) | two false alarms, both resolved | `memory/engine-vs-slumbot-breakeven.md` | yes as a warning |
| (session with n=2500) | Overall exploit-primary bot vs Slumbot | Slumbot, n=2500 | **−39.6 ± 30.9 bb/100** ≈ statistically the floor (−43); **the historical +31 did NOT reproduce** | negative; exploit overlay unsupported | `docs/STATE.md:1479` | yes — this is the largest n of this channel |
| (historical) | Exploit-overlay era | Slumbot | **+31** (previously −102); anti-spew fix: vs GTOBaseline −912 → **+207**, vs Slumbot −526 → **−46** | historical stages | `docs/STATE.md:1653`, `:1865` | **no** — replaced by the n=2500 run |

#### A2 — Theory duel (in-engine mirror against "theory")

*What the channel can do:* erase card luck via duplicate mirroring and pit the bot against two explicit
embodiments of "theory" ($0, no GTOW). *What it cannot do:* shorten all-in **strategy** variance
— exactly why the SE still stays at ±10 at n=6000.

| Date | What was measured | Instrument / channel | Result | Verdict | Source (file:line) | Still valid? |
|---|---|---|---|---|---|---|
| 2026-07-06 | Null test: theory against itself | `research/theory_duel.py`, mirror, n=6000 | **+0.00 ± 0.00** | instrument validated | `../doctrine/THEORY_DUEL.md:13` | yes |
| 2026-07-06 | Our GTO floor vs analytic GTOBaseline (Chen/MDF/balanced) | mirror, n=6000, 100 bb | **−16.03 ± 10.30** (CI −36…+4) | we lose against the theory | `../doctrine/THEORY_DUEL.md:14` | yes |
| 2026-07-06 | Full exploit engine vs the same baseline | mirror, n=6000, 100 bb | **−19.44 ± 10.51** (CI −40…+1); difference exploit−floor = **−3.4 = statistically zero** | the exploit overlay yields **nothing** against a fixed near-GTO opponent | `../doctrine/THEORY_DUEL.md:15`, `:31-33` | yes — supports the doctrine "exploitation only against deviators" |
| 2026-07-06 | TexasSolver oracle as opponent | paired, n=120, 40 bb, 541 live solves, 0 fallback | **−33.3 ± 60.8** (CI −152…+86) | too noisy for a sign; a 6-hand smoke read +233 = pure tail | `../doctrine/THEORY_DUEL.md:16-18` | yes as a method finding |
| 2026-07-06 | Limit of the mirror channel | same | SE stays **±10 at n=6000**, ±61 at n=120 | **binding lesson**: the mirror cannot erase all-in strategy variance → the tight live gate is AIVAT, not the raw mirror | `../doctrine/THEORY_DUEL.md:37-39` | yes |

#### A4 — Value net / Leduc (exact exploitability)

*What the channel can do:* as the project's only instrument, compute an **exact** best-response exploitability against
a real zero-point truth ($0, toy size). *What it cannot do:* predict HUNL bb/100.

| Date | What was measured | Instrument / channel | Result | Verdict | Source (file:line) | Still valid? |
|---|---|---|---|---|---|---|
| 2026-06-16 | Gate 0b — does a CFV net learn the exact oracle? | Leduc, held-out MAE against `vanilla_cfr` labels | **val MAE 0.191 = 6.4 % of the CFV scale** (gate < 8 %) | **PASS** — the DeepStack core validated (exactly what the fcpa policy net with −212 could NOT do) | `../plans/VALUE_NET_PLAN.md:54` | yes |
| 2026-06-16 | Gate 0c — does the belief-state resolver play correctly? | Leduc, exact exploitability | converges into a **no-bluff corner**: P0 bluffs J **0 % instead of exactly 8 %**, P1 over-folds Q **47 % instead of exactly 1 %** (dominant leak); **exploitability 170 vs equilibrium 22 mbb/hand** | **negative, cause localized** (per infoset, H1 "propagation bug" refuted) | `../plans/VALUE_NET_PLAN.md:57-60` | yes |
| 2026-06-16 | scaled expectation of the path | — | **−53 → −15…−25 bb/100** | **expectation, not a measurement** | `../plans/VALUE_NET_PLAN.md:17` | yes as an expectation |

#### A5 — Noise floor of the K1 oracle (the precondition of the v10 G3 verdict)

*What the channel can do:* quantify its own measurement error before a verdict is made. The collection lists
only the final value (floor 0.095 in `02_runs.md:244`, "~271 seeds" in `01_journal.md:168`) — the scaling is missing.

| Date | What was measured | Instrument / channel | Result | Verdict | Source (file:line) | Still valid? |
|---|---|---|---|---|---|---|
| 2026-09-07 | How fast does the oracle's noise floor fall with the seeds? | `research/k1_oracle.py`, n=6 histories / 14 nodes / 12 workers | **S=8 → 0.122 · S=32 → 0.050 (600 s) · S=64 → 0.033 (1124 s) ≈ 1/√S**; class level already converged to **0.0035** at S=64 | a verdict floor ≤ 0.010 would need **S≈256 (~13 h)** — this is why G3 could only say "`orakel_zu_grob`" | `research/k1_oracle.py:44-46` | yes |

#### A6 — Journal fields nobody cites (sign test)

*What the field says:* `vorzeichen_z` checks whether the majority of the **divergent decks** points in the direction of the
mean. It is exactly the criterion the project uses elsewhere to overturn candidates.

| Date | What was measured | Instrument / channel | Result | Verdict | Source (file:line) | Still valid? |
|---|---|---|---|---|---|---|
| 2026-08-17 23:25 | v4 core vs base, pooled anchor | pargate mirror, 3×30k = **n=89,760** | bb100 **+16.14 ± 2.77**, CI95 [+10.74, +21.56], perm_p **0.0002** — **but `vorzeichen_z: −5.63`** at a nonzero share of 0.2063 | ANWENDEN (as entered); **honest addendum: the mean is positive AGAINST the majority of the divergent decks** — the gain is tail-carried | `data/autogym/journal.jsonl:70` | yes — the anchor holds, the caveat is missing in `01:107`, `02:61`, `06:94` |
| 2026-08-17 21:33 | Contrast: `turn_wert` pooled | pargate, n=89,760 | bb100 **+7.27 ± 2.33**, `vorzeichen_z` **+14.93**, nonzero 8.58 % | the same channel can deliver a clean sign — v4 does not | `data/autogym/journal.jsonl:63` | yes |

#### A7 — Formula blind campaign (three real formula errors)

| Date | What was measured | Instrument / channel | Result | Verdict | Source (file:line) | Still valid? |
|---|---|---|---|---|---|---|
| (2026-07-06 era) | Double-blind re-derivation of the formula library | 24 agents, independent second derivation | **3 real formula errors** fixed and pinned in the suite: `bluff_to_value` r=B/P → **B/(P+B)** (the audit fix of 2026-06-20 had the wrong denominator), `balanced_bluff_combos` (e>0 indifference), `give_up_frequency` (b=0.5 baked in as a constant); ledger **72 → 69** unverified; suite at **20/20** | positive; all in the KB/brain layer, the engine decision path was not affected | `docs/STATE.md:745-748` | yes — `05_llm.md:163` only lists the 90-agent audit |

#### A8 — GTOW leak decomposition and the exploit catalogue

| Date | What was measured | Instrument / channel | Result | Verdict | Source (file:line) | Still valid? |
|---|---|---|---|---|---|---|
| 2026-07-04 | Decomposition of the 19.33 bb/100 Analyzer EV loss into named leaks | Analyzer, per decision | **L1 BB/SB flop overfold vs cbet 2.91** (folds top pair: Kd6s on KcTs5h) · **L2 river over-aggression 1.58** · **L3 cbet-then-fold 1.33** · **L4 river underbet 0.98** · **L5 river other 0.95** | the project's only named leak decomposition; appears in no part | `../plans/TIE_GTOW.md:31-35` | yes for the v2.2-era engine |
| 2026-08-17 | Attack catalogue against us (K1–K7) with priors | tool analysis + tie-back to measurements | K1 flop cbet barrage **prior +6…+12**, anchored to **`sel_guard` +6.1 bb/100 (measured, paired)** and L1=2.91 · K2 +3…+5 · K3 +2…+4 · K4 +2…+4 · K5 +2…+4 · K6 +1.5…+3 (anchored to L3=1.33) · K7 +1…+2 (speculative) | priors, **not measurements** — and explicitly **not additive** (K1/K6 share L1/L3 mass) | `EXPLOIT_CATALOG.md:22`, `:32`, `:183`, `:188`, `:263` | yes as a list of priors |

#### A9 — exploit_gate: the absolute values per arm

*What is missing:* `02_runs.md:163`, `06_selfplay.md:201-210` and `01_journal.md:176` only list the **differences**
ON−OFF. The absolute values show that the engine wins clearly against several profiles in **both** arms —
this does not soften the negative exploit finding, but puts it in context.

| Date | What was measured | Instrument / channel | Result | Verdict | Source (file:line) | Still valid? |
|---|---|---|---|---|---|---|
| 2026-09-09 | exploit ON and OFF per league profile, absolute | HU, `PokerBot` without PRINCE, 600 paired decks per profile, fingerprint confirmed | nit **+24.95 / +27.04** · tag **−3.43 / +15.83** · lag **−4.84 / +13.66** · station **−11.62 / +5.73** · maniac **−14.80 / +0.95** · rock **+20.35 / +20.66** · whale **−9.57 / −1.32** · shark **+3.14 / +17.54**; 6-max reads **+22.77 / +19.14** | **all eight HU point estimates ≤ 0 in the difference, pooled ≈ −12 bb/100 (SE ≈ 4.5)** → the Dirichlet river exploit is **refuted** for this path; product decision: exploit stays OFF in all modes | `../reports/TRAINER_WIRING.md:77-85`, `:87` | yes |

#### A10 — Autogym pilot: 6-max position values

| Date | What was measured | Instrument / channel | Result | Verdict | Source (file:line) | Still valid? |
|---|---|---|---|---|---|---|
| 2026-08-16 19:58 | Position bb/100 in the 6-max pilot | `gym_six`, 300 hands, 3002 graded decisions | **BB +121.57 · BTN +95.13 · HJ +66.42 · UTG +18.50 · CO −107.41 · SB −194.20** | pilot noise at 300 hands (BB positive = sign alarm against every poker expectation), **mentioned nowhere**; the later 30k catalogue reads BTN +33.5 / BB −28.9 / SB −29.6 | `data/autogym/report_20260816_195830.json` (field `six.position_bb100`); catalogue `data/autogym/journal.jsonl:38` | **no as a value** — only as evidence of how much 300 hands lie |

#### A11 — Today's Kaggle invalidity finding (after the collection was completed)

| Date | What was measured | Instrument / channel | Result | Verdict | Source (file:line) | Still valid? |
|---|---|---|---|---|---|---|
| 2026-09-10 02:38 | Could the champion play fully in the Kaggle runs at all? | code review | **No.** `improver._river_spot_und_frage` (`pokerbot/autogym/improver.py:421-433`) returns `None` when the history has no row `action=='deal' & street=='river'`; this is the **shared foundation of ALL river GPU guards**, including the `river_gpu_guard` that is part of the champion `r8_stack` (`pokerbot/autogym/pargate.py:134`). The Kaggle adapter only wrote the deal marker from commit `d22d400` (01:59) on | **INVALID (measurement error in the adapter)** — affected are the reference value (ended 01:06) and the v9 run (ended 02:37); the v10-H0 run (started 02:27) remains valid; both measurements will be repeated | `data/autogym/journal.jsonl:124`; `../reports/KAGGLE_ARENA.md:147-165`; commit `e8248e1` | yes — **supersedes four rows of the collection** |
| 2026-09-10 02:37 | v9 `r10_ernte` vs champion (the run itself, now complete) | kaggle_arena, 600 paired decks, 6,913.4 s | **bb100 0.0 · SE 0.0 · nonzero 0/600 · perm_p 1.0 · VERDICT NEUTRAL** | **no v9 verdict** — the zero is a consequence of the missing marker (`river_play_guard` depends on the same foundation), not proof that the v9 guard never fires | `data/runs/kaggle_v9_vs_champion_2026-09-10.log` (last line); reading `../reports/KAGGLE_ARENA.md:161-165` | **no** |

---

### (b) Corrections

**K1 — Kaggle A/A: the collection contradicts itself; both sides are partly right.**
`02_runs.md:259-260` and `:329-330` declare the Kaggle channel unvalidated ("A/A BROKEN", −37.5) and the
reference value therefore not reliable, because it ran "54 min AFTER the broken A/A".
`01_journal.md:182`, `05_llm.md:147` and `06_selfplay.md:42` say: A/A exactly 0 after two fixes.
**01/05/06 are right on the chronology:** `data/autogym/journal.jsonl:119` carries ts **2026-09-10 00:15:15** with
"A/A EXACTLY 0 after two fixes (hand_id per deck; fresh agents per mirror half, because the bot shuffles from one
RNG stream → A/A was −37.5)", `../reports/KAGGLE_ARENA.md:56-63` documents the same. The reference run
(`journal.jsonl:121`) ended **01:06:39** — i.e. **51 min AFTER** the passed A/A, not 54 min after.
`data/runs/kaggle_aa_2026-09-10.log` (mtime 00:12:38) contains only the **pre-fix run**; 02 generalized from
a file that cannot know about the fix.
**Honest residual finding that no part mentions:** the passed A/A left **no log file** in `data/runs/`
— it is documented only via the journal and the docs.
**Nevertheless 02's verdict is right in its result, but for the wrong reason:** the reference value is invalid
because of the missing deal marker (K1 below, C-V1), not because of the A/A.

**K2 — SE of the only valid GTOW anchor: 9.41, not 6.8.**
`01_journal.md:132` computes for `v4_prince` (n=979) "SE ≈ 6.8 — derived" from the constant c = 214·√n;
`03_gtow.md:109/112/242` gives **−21.12 ± 9.41**. **03 is right.** My own recomputation over
`data/sessions/gtow_hands_1787027076.jsonl` + `_1787033025.jsonl`: n=979, mean **−21.115**, per-hand SD
**294.3**, SE **9.41** (sample SD). The 214 constant is a **v2.2-era quantity** — in
`gtow_hands_1783226155.jsonl` I measure SD **213.6** at n=2393 (SE 4.37, exactly the documented anchor) — and
it underestimates the night-2 spread by ~28 %. Consequence: with the correct SE the delta to the control (+10.23) is
even more clearly **not significant**.

**K3 — Journal line numbers in `06_selfplay.md` shifted by 1 in eight places.**
Checked against `data/autogym/journal.jsonl` (type read per line). `01_journal.md` cites the same entries
correctly — the collection is internally inconsistent at these places.

| Location in 06 | cited | correct | what actually is on the cited line |
|---|---|---|---|
| `06:169` E3 detector +394.9 | `:7` | **J:8** (`SELFTEST-BEFUND`) | J:7 = `L-VORSCHLAG` (river eq 0.00 vs 0.31) |
| `06:171` 6-max catalogue | `:37` | **J:38** (`RUNDE4-6MAX-KATALOG`) | J:37 = `RUNDE4-DISZIPLIN` |
| `06:79` replication +1.11 | `:39` | **J:40** (`REPLIKATION-HETEROGEN`) | J:39 = `RUNDE4-DECISIVE` |
| `06:81` 183k anchor +8.68 | `:38` | **J:39** (`RUNDE4-DECISIVE`, bb100 8.68 / se 1.28 / n 183,200) | J:38 = 6-max catalogue |
| `06:182` exploit_jagd | `:30` | **J:31** (`EXPLOIT-JAGD`) | J:30 = `TRANSFER-TEST` |
| `06:241` transfer test | `:29` | **J:30** (`TRANSFER-TEST`) | J:29 = `EXTERNE-BEWERTUNG` (Snowie blunder) |
| `06:242` paired transfer | `:31-32` | **J:32** (`TRANSFER-TEST-GEPAART`) | J:31 = exploit_jagd |
| `06:243` cause diagnosis (unseeded MC) | `:32` | **J:33** (`TRANSFER-TEST-FINAL`) | J:32 = paired transfer |

Not affected and correct: `06:78` → J:36 (`RUNDE4-SWEEP sel_m15`) and `06:80` → J:41 (`ANWENDEN+NAME`).

**K4 — "today's champion (~−21)" is a mirror→GTOW transfer that the project itself has corrected.**
`05_llm.md:145` and `03_gtow.md:191` list −21 as the value of today's champion.
`data/autogym/journal.jsonl:122` (2026-09-10 01:19:25, `KONSULT-SOL-KORREKTUR`) states: **"−21.12 belongs to
v4/r6_button, not v5"**. Today's champion `auslese-v5`/`r8_stack` has **no GTOW anchor** — this is already stated
correctly in `03_gtow.md:252` and `01_journal.md:212`. The same applies to the gap to the top-5 threshold: the
"≈ 8 bb/100" are the **mean** reading; against the rank criterion's lower bound LCB −14.8 it is **~6.3**
(`journal.jsonl:122`; carried over correctly only in `01_journal.md:185`).

**K5 — the SEs described as "exactly reproduced" deviate systematically (ddof).**
`03_gtow.md:34-35` claims the recomputations "reproduce the documented numbers exactly". For the
**means** that is true (own samples confirm it), for the **SE** it is not:
`05_llm.md:72` reproduces `docs/STATE.md:1092` verbatim (ON −39.92 ± **19.32** / OFF −55.92 ± **28.14**),
`03_gtow.md:68` gives ±19.36 / ±28.19; the same offset for the smokes (`data/runs/STAND.md:60`:
±**14.30** / ±**22.11** vs `03_gtow.md` ±14.67 / ±22.22). Cause: population vs sample SD — the
doc numbers are pstdev-based, the recomputation stdev-based. It changes no verdict, but it devalues the
word "exactly".

**K6 — Catastrophe count in the v10 gate G5: both readings are correct, the labels contradict each other.**
`01_journal.md:165` and `06_selfplay.md:134` write "all 3 decks ≤ −100 bb"; `02_runs.md:247` writes "2 catastrophe
decks" in the result column and "all three decks ≤ −100 bb" in the still-valid column.
`data/runs/v10/G5_BERICHT.json`: `n_katastrophen: 2` — the field counts **both directions** (+160.79 and −153.20);
`groesste_verluste_chips` lists **three** decks ≤ −100 bb (−153.20 / −138.99 / −113.68). Anyone citing the finding
should write "3 losing decks ≤ −100 bb, 1 of them counted as an `n_katastrophen` negative case".

**K7 — Correction to the review report: the Autogym button-net contradiction does not exist.**
The review report flags under U10 that `docs/STATE.md:313` gives button net **+32.6**, but the source file **33.43**.
These are **two different runs**: `data/autogym/report_20260816_192735.json` (HU 300 hands, 1554 + 2023 =
**3,577** decisions = exactly the pilot described in STATE:310) has `button_netto_bb100` **32.6467** and
`gate_selbsttest` **+2.11 ± 3.28 (n=100)**; `report_20260816_195830.json` (HU 600 hands) has **33.43** and
**+1.41 ± 2.18 (n=150)**. STATE.md:310-313 is correct, `06_selfplay.md:169` is correct — they merely cite
different runs.

**K8 — Correction to the review report: the fold harvest does have a source.**
The review report lists `02_runs.md:154-155` ("preflop 17,928 / flop 15,879 / turn 2268 / river 2880") under
"without source". The numbers are in the field `fold_ernte` in
`data/runs/20260817_020232_exploit_jagd/result.json` (n=100,000 hands, together with `jaeger_bb100 8.87`,
`se_ueber_jaeger 6.9`, `sd_netto_bb100 19.85`, `nsd_netto_bb100 -10.99`). Only the file reference in 02 points to the
neighbouring file `jaeger_einzeln.json` (which holds the **per-hunter** harvests, e.g. preflop 891 / flop 788).

---

### (c) Stale — do not cite anymore

**V1 — Kaggle reference value `+55.83 ± 38.02` (300 decks, 32.3 % divergent decks, ~10.5 s/deck): INVALID.**
Listed as valid in `01_journal.md:184`, `02_runs.md:260`, `05_llm.md:146`, `06_selfplay.md:251`.
**Replacement: none — the run will be repeated.** Reason (`data/autogym/journal.jsonl:124`; `../reports/KAGGLE_ARENA.md:147-160`;
commit `e8248e1`): the run ended at 01:06, the deal marker only entered the adapter with `d22d400` at 01:59; without it
`improver._river_spot_und_frage` (`improver.py:421-433`) returns `None`, and so the GPU surgery
**of the champion itself** (`river_gpu_guard` in `r8_stack`, `pargate.py:134`) could not fire. What was measured was a
champion without one of its own components. Aggravating and mentioned in no part: the throughput of this channel
fluctuates by a **factor of 25** (0.41 s/deck before the commit vs 1.7–16.8 s/deck after it, `../reports/AIVAT_KAGGLE.md:25`),
and `../reports/KAGGLE_ARENA.md:220` makes the re-collection **precondition G0**.

**V2 — "v9 run running / incomplete" (`02_runs.md:261`) and "channel did not run" (`08_daten.md:49`): superseded —
but the replacement is NOT the clean null finding it reads as.**
The run is finished: `data/runs/kaggle_v9_vs_champion_2026-09-10.log` (last line) reports
`prince[r10_ernte] vs prince[final]`, **n=600, bb100 0.0, nonzero 0, perm_p 1.0, 6,913.4 s, NEUTRAL**.
**But:** `journal.jsonl:124` and `../reports/KAGGLE_ARENA.md:161-165` declare this run invalid as well — the
zero comes from the missing marker (`river_play_guard` depends on the same foundation), not from the v9 guard
never firing in this channel. Also superseded: `kaggle_v10h0_vs_champion_2026-09-10.log` now has a
progress line ("[50/150] +0.0 bb/100, **33.10 s/deck**"); the run has not finished as of 02:51 (last
write time 02:27) and per the docs counts as **valid**, because it started after the marker.

**V3 — E7 "`analyze_gtow_hands.py` sets BB=50, all bb/100 from it inflated by a factor of 2 — OPEN"
(`03_gtow.md:206`): FIXED.**
Replacement: `research/analyze_gtow_hands.py:16` today reads `BB = 100.0` with the comment "the old value 50 was
the SB → all bb/100 here inflated by a factor of 2 (V10_FAKTEN A8/E10, 2026-09-07)". The cited line 141
no longer exists (the file has 80 lines). Only the doc is stale (`../reports/V10_FACTS.md:246-247`).

**V4 — "vs GTOW −19.7" as the current state (`07_sonstige.md:39`, marked there as "yes, binding").**
The quote is faithful to its source (`../reports/SNOWIE_BLUNDER_ANALYSIS.md:66-67`), the source is outdated.
**Replacement:** −19.70 ± 4.37 (n=2393) counts as **blinds-bug-inflated** and has been replaced by **−30.11 ± 5.51 (n=2899,
fixed harness)** as the era anchor (`03_gtow.md:81`, `:88-93`); the **only live anchor valid today**
is **−21.12 ± 9.41 (n=979)** for v4-on-PRINCE. The argument of 07 ("Snowie is the weaker
referee") stands in substance — only the number in it is dead.

**V5 — the cross-validation "Analyzer 19.33 ≈ live AIVAT −20.09" without a bug note
(`04_analyzer.md:51`, repeated in `:82`).**
In the same document `04_analyzer.md:189` states that the blinds-order bug hit **every** live AIVAT run,
but **not** the exports/Analyzer grades. So the "two independent instruments" compare a
bug-free export grade with a bug-inflated live number. The **method** (double measurement against the
"that was just variance" reading) remains valid; the **agreement** is weakened as an argument and must
carry the note.

**V6 — "17/17 deep" for `tests/test_math_suite.py` (`CLAUDE.md`).**
`07_sonstige.md:107` and `:134` already mark this correctly as outdated. **Replacement: 20/20.** Re-run by me today
(`python -m tests.test_math_suite`, 2026-09-10): **"20/20 checks passed | fuzz N=400/check"** and
**"UNVERIFIED formula functions (no independent reference yet): 69"**. Addition missing from 07: the 20/20 and
the ledger "72 → 69" have been in `docs/STATE.md:745-748` since the blind campaign — this is not a new measurement
from today, but a doctrine line that has not been updated for weeks.

---

### (d) Without source — use with caution

**Q1 — "1.3–35 s/hand per configuration" (`03_gtow.md:12`).** The follow-on "2,500 hands ≈ 8–9 h" is documented
(`../reports/KAGGLE_ARENA.md:71`, there as a comparison table GTOW API vs local). I cannot find the seconds range anywhere;
the closest documented quantity is **"~0.3–18 s/hand depending on the resolver"** and applies to the **local
Kaggle channel**, not to GTOW (`../reports/KAGGLE_ARENA.md:71`). Until clarified: do not cite.

**Q2 — "re-run today (2026-09-10)" without an artifact (`07_sonstige.md:48`, `:61`, `:85`, `:107-108`).**
Affected: `test_icm`, `test_tournament`, `snowie_regress` (5/5), `test_math_suite` (20/20, 69 unverified).
No log path, no preserved artifact in the repo. **I re-ran two of them myself and they match:**
`python -m tests.test_math_suite` → **20/20 checks passed | fuzz N=400/check**, **69 UNVERIFIED formula functions**;
`python -m tests.test_icm` → **"ICM: alle Tests bestanden" (all tests passed), example 50/30/20 → [38.39, 32.75, 28.86]**,
bubble factor 30v40 = 2.69, bubble call threshold 74.6 % (pot odds 45.5 %). I did **not** re-check `test_tournament` and
`snowie_regress` — there the claim remains undocumented.

**Q3 — "15 % on-tree / ~0.60×pot" from the script `_betsize_check` (`05_llm.md:71`).** The script does not exist in the
repo (`grep -rn "_betsize_check"` only finds the mention `docs/STATE.md:1091`, explicitly labelled there as
"scratchpad"). Only the doc sentence is documented, not the measurement. The **mechanical** part of the finding
(15 % → 100 % on-tree after the snap) is documented independently via the A/B in `docs/STATE.md:1091`.

**Q4 — dropped.** The fold-harvest numbers from `02_runs.md:154-155` have a source; see K8.

**Q5 — `08_daten.md` as a whole: all size and file counts come from an "os.walk today" without a
recorded artifact.** The reviewer's spot checks were correct (`INDEX.jsonl` 79 lines for 91 run folders;
65 GTOW HH files / 24,050 hands, all with `aivat`; 218 `session_` vs 175 `decisions_`). **One spot check is
now wrong:** the journal has **124** lines, not 123 — it grew at 02:38
(`data/autogym/journal.jsonl`, mtime 2026-09-10 02:38:07). This is not an error of the collection, but the
generic risk of this class of numbers: they age within a single session.
