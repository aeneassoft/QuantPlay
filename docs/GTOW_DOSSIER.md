# GTOW DOSSIER — everything we know about the opponent (2026-07-04)

**Doctrine (user, explicit): the GTO-score is DEAD as a target. ONLY bb won/lost matter.** This dossier compiles ALL
information about GTO Wizard AI (the HUNL 200bb bot behind `researcher.gtowizard.com`) from every source we have:
13,477 logged hands (45 sessions), the 12.5k-hand tree census, the graded uploads, the leaderboard, and the API docs.
Purpose: find the holes. **Goal (user): BEAT GTOW — the honest reading: exploit the APPROXIMATION, since a true
equilibrium cannot be beaten in HU (2p zero-sum). Every "+" claim needs pre-registered n (see §9).**

## 1. Platform facts (measured / documented)
- Game: HU NLHE, **200bb** effective, cash reset per hand. bb=100 chips in our units.
- API: `researcher.gtowizard.com`, key-gated but **free**; ≤20 concurrent; intermittent 502/503 (26/1000 hands failed
  in our fresh run — retry loop needed); **NO seed control** → paired dealing impossible → interleaved blocks + AIVAT
  is the best variance control.
- Scoring: AIVAT (chance + action correction, ~10× variance reduction). Account aggregate pollutes across code eras —
  use a dedicated key per campaign (key #2 = current).
- Their reported per-hand AIVAT SD ≈ 2.8 bb/100 × √5000 ≈ **198–224 bb/100-units** (matches our SE 7.18 @ n=974).
- The bot appears **STATIC per hand** (no confirmed cross-hand adaptation — UNVERIFIED, see §8 open questions).

## 2. The leaderboard (2026-07-04 pull, `data/gtow_grades/leaderboard_2026-07-04.json`)
**Nobody beats it.** Best: Bitcrumbs −3.14 (44.5k hands) · Rabichow (pro human) −3.91 · MIT Marvel −5.81 ·
GPT-5.2-XH −8.26 · GPT-5.5-XH −9.23 · Gravel (MIT) −10.61 · … · MIT −16.78 (92k hands). **Ours: −20.09 (n=974) = #11.**
Implication: holes, if they exist, are small or unexploited by everyone so far — the ceiling of the known art is −3.

## 3. GTOW's PREFLOP behavior (measured, 12.5k hands census + graded uploads)
- **Open (SB/BTN): 2.25bb** (66% of opens). **No limps in its tree.** SB opening range ≈ **very wide / near-100%**
  (evidence: it graded OUR folds of 75o/85o/73s/A9o/K5o as BLUNDERS → it plays those hands itself).
- **3bet: ~4× (to ~9bb vs 2.25 open)** (census R9 vs R2.25). 4bet+ pots are RARE in its play (thin nodes, §6).
- Our preflop vs it: −1.6 bb/hand on preflop-ending hands (near-solved blueprint) → preflop is NOT where it beats us.

## 4. GTOW's POSTFLOP tree (the census — its empirical size grid, pot-fractions, with counts)
**FLOP bet (SRP):** 0.35 (1015!) ≫ 0.75 (240) ≫ 1.35–1.75 (~75) — a **two-size core {0.35, 0.75}** + rare overbets.
**FLOP bet (3bet pot):** 0.35 (139) dominant, 0.75/0.85 (~25), 1.35 (15).
**TURN bet (SRP):** 0.35 (393) ≈ 0.75 (337) ≫ 1.35–1.45 (~55), rare 1.6–1.95.
**RIVER bet (SRP):** **0.65 (316) > 0.35 (184) > 1.0 (151) > 1.5 (81) > 3.0 (12)** — a four-size river {0.35, 0.65, 1.0, 1.5} + rare 3× overbet.
**RIVER bet (3bet pot):** 0.35 (30) ≈ 0.65 (27) > 1.0 (12) > 1.5 (7).
**RAISES:** flop {0.35 (62), 0.75 (20)}; turn {0.35 (17), 0.75 (17)}; river {0.5 (23!), 1.0 (10), 1.5 (5)} — river
raise-to-half-pot is its workhorse raise.
**Limped pots (only vs our limps):** flop 0.5 (33), turn 0.5 (69)/0.75 (37), river 0.65 (51)/0.35 (30) — it has a
limped-pot strategy but from FEW samples (our limps were rare) → likely its thinnest solved region it actually plays.
**The GAPS between its nodes (attack map §7):** flop/turn: nothing between 0.35↔0.75 (the 0.5–0.6 gap!); river:
0.35↔0.65 gap, 1.0↔1.5 gap, >1.5↔3.0 gap.

## 5. WHERE it takes our money (the x-ray of −20.09, n=974)
- **Postflop is everything: −18.4 of −20.1** (river −8.6, flop −8.3, turn −1.6; preflop −1.6).
- In NORMAL pots (3–10bb −9.5, <3bb −5.3), NOT jams (≥100bb: −0.7, n=14) — it grinds us in small/mid pots, it does
  not stack us. 0 catastrophes in the fresh run (worst hand −26bb).
- Our body (5/10% trim) −11/−8: the loss is a broad postflop grind + a modest tail.
- Per-decision (Analyzer): our river is the worst street (22–28% mistake+blunder); as ex-post confirmation, its
  river value-betting/raising discipline is what punishes us.

## 6. Its THIN branches (low-sample = least-solved / most attackable in principle)
From the census counts (its own play): **4bet+ pots** (flop bet n=9, turn n=12, river n=7 — tiny), **limped pots**
(it rarely faces them at scale), **flop raise vs our bet in 3bet pots** (n≈20), **turn raises** (n≈37 SRP, 10 in 3bet).
These are the nodes where an approximation is most likely coarse. CAUTION: thin ≠ weak — it may re-solve those nodes
finely; thin only means WE have little data on its behavior there (double-edged).

## 7. THE ATTACK SURFACES — VERDICTS (investigated 2026-07-04, 3-agent workflow: mining + architecture + theory)
1. **Off-grid bet sizes — ★ REFUTED, both empirically and architecturally.**
   - **Architecture (confirmed, arXiv 2603.23660 + GTOW blog):** GTO Wizard AI = the acquired **Ruse engine**
     (Provost & Beardsell) — **DeepStack/ReBeL-class REAL-TIME depth-limited re-solving** with neural leaf values,
     ~3s/street, explicitly "arbitrary stack depths and bet sizes", dynamic per-spot action sets. **There IS no
     translation boundary to straddle** — it inserts our exact size into the subgame and re-solves. Every historical
     translation exploit (LBR's 75–300+ bb/100 vs ACPC bots, the tiny-bet hole, Libratus's nightly patching) targeted
     the pre-solved-abstraction class that GTOW AI was explicitly BUILT TO REPLACE (Ruse beat Slumbot +19.4 ± 4.1,
     partly through exactly that weakness class).
   - **Our own 13,477 hands agree (mining, n=3,292 hero bets):** GTOW's fold% is **smooth, monotone, ≈ exactly MDF**
     at every size (flop 0.35×→26.9% vs MDF 26%; 1.0×→50.1% vs 50%). All midpoint-straddle tests sub-2σ. Even the 212
     absurd legacy monster-jams (up to 99.5× pot) got coherent responses (90.6% fold). **Off-tree hands earned NOTHING
     extra: AIVAT −1.73 vs on-tree −1.55 (0.3σ)** — the raw-winnings "edge" of off-tree betting vanishes under AIVAT.
     Verdict: **NO_SIGNAL**. (Caveat: selection bias + thin off-grid bins; but architecture makes the null expected.)
2. **Rare/thin lines (limp-3bet, donk ladders, overbet-caps) — LOW expected value.** CFR-family blueprints converge
   slowest at thin nodes, but a real-time re-solver has no fixed blueprint to be thin IN; residual = value-net error
   at odd states (unknown, likely small). No literature anchor for a positive number vs this architecture.
3. **Node-avoidance / steering — REFRAMED, and this one is REAL:** its true mechanism vs a near-Nash opponent is
   **reducing OUR donation** (avoid the branches where WE bleed — our river −8.6), not harvesting theirs. This is
   just "fix our postflop" wearing an attack costume.
4. **Stateful adaptation — dead as an attack** (a static bot has no memory to game; timing tells are meaningless),
   but the asymmetry is the one honest long-term hope: a static strategy's holes PERSIST and are farmable forever
   once found. Finding one costs ~50k pre-registered hands per hypothesis (§9).
5. **What does NOT work (all measured):** generic exploit overlay (19.33 vs 17.05 — deviates us more than it exploits
   them); frequency-matching for its own sake (score-vs-EV tradeoff); deliberate off-grid sizing (this section).

## 7b. THE ARITHMETIC OF "BEAT GTOW" (the theory brief, honest)
EV vs their σ = (harvest from σ's holes) − (our donation from our own deviations). **Our donation: 17–19 bb/100.
Realistic best-case total harvest across ALL surfaces vs a real-time re-solver: ~0…+5 bb/100.** → a "+" is
arithmetically unreachable from here; the pivot cannot outrun the donation. Empirical anchor: purpose-built
challengers + a top pro, 44.5k hands — nobody positive, best −3.14. **The rational goal: cut the DONATION toward −3
(leaderboard-top), THEN hole-hunt from a near-zero-donation position.** Beating GTOW is not a strategy problem today;
it is an "our postflop bleeds 17 bb/100" problem.

## 8. OPEN QUESTIONS (remaining intelligence gaps)
- **Adaptation across hands:** unverified (testable: fixed exploitable pattern × n hands → does its counter drift?).
  All current evidence says static per hand.
- **Value-net blind spots:** the ONLY theoretically-live hole class for this architecture (odd stack geometries /
  multi-overbet lines where the leaf net extrapolates). No cheap detector known; would need the 50k-hand discipline.
- **Census grid detail:** its OWN empirical grid is {0.33: 73%, 0.75: 17%, 1.32: 3%} flop / {0.33, 0.75, 0.5, 1.32}
  turn / {0.67: 41%, 0.33: 26%, 1.0: 19%, 1.5: 11%, 3.0: 2%} river — our snap GRID in `gtow_tree_census.py` misses
  0.67/1.5/3.0 on river (minor fix). NOTE: it responds smoothly to sizes it never uses itself (more re-solve evidence).

## 9. MEASUREMENT DOCTRINE for any "+" claim (non-negotiable — we have a history of fake '+' at small n)
- Per-hand AIVAT SD ≈ 224 bb/100-units → **+3 bb/100 at 2σ needs ≈ 22,000 hands**; +5 needs ≈ 8,000; +10 needs ≈ 2,000.
- Pre-register the hypothesis + n BEFORE the run; never extend a running session because it looks good.
- Any "+" is treated as an artifact until the body (trimmed) agrees AND the effect lands in the bucket the lever
  targets (e.g. a translation exploit must show up as villain over-fold/over-call at the attacked sizes, not as
  generic river luck).
- Free to run (in-process from the PC); the cost is wall-clock (~9s/hand → 22k ≈ 55h) + statistical honesty.

## 9b. MATCH-WIN MATH (user goal 2026-07-04: "WIN, even over few hands; variance is acceptable")
Formalized: maximize **P(ahead in chips after n hands)** = Φ(μ√n/σ), NOT EV. Computed from OUR real per-hand
distribution (fresh session n=974, raw per-hand SD **12.97bb = 1297 bb/100-units** — 5.8× the AIVAT SD 224; fat
tails included via bootstrap, drift recentred):

| true drift (bb/100) | n=100 | n=300 | n=500 | n=1000 | n=5000 |
|---|---|---|---|---|---|
| −20 (HEAD raw) | 36.8% | 38.5% | 35.4% | 30.2% | 13.8% |
| −8 (our body) | 41.6% | 42.7% | 41.2% | 40.6% | 33.1% |
| −3 (world best) | 44.6% | 43.8% | 46.9% | 46.5% | 42.6% |
| 0 (tie) | ~45–48% | | | | 48.9% |
| +3 | 45.8% | 47.9% | 50.2% | 51.6% | 55.2% |

**Readings:** (1) **We already "win" short matches routinely** — the fresh 974-hand run finished RAW **+69.4 bb/100**
(we beat GTOW in chips last session!). At ≤300 hands even a −20 bot is ~37% to be ahead; that is what variance does.
(2) **Variance compresses everything toward ~50% but can NEVER push P(win) above it** — only μ>0 makes us a
favorite; at n=100 the gap between −20 and world-class −3 is just 8pp. (3) **Zero-EV variance pump** (legitimate,
small): where the solver/blueprint MIXES (~EV-indifferent), always pick the aggressive/high-variance branch — raises
σ at zero μ cost, worth a few pp of P(win) when behind; flip to the LOW-variance branch the moment μ>0. (4) **The
leaderboard metric (AIVAT) strips variance by construction** (chance+action corrections) — no variance trick touches
it; raw-chip session wins are real wins of money but not of the benchmark. **Conclusion: μ stays king even for the
match-win goal; every bb/100 of river-fix buys more P(win) at every n than any variance strategy.**

## 10. Compiled sources
`data/census/gtow_tree.json` (the tree) · `data/sessions/gtow_hands_*.jsonl` (13,477 hands, 45 sessions) ·
`data/gtow_grades/*.json` (graded uploads incl. paired seed-55 trio + leak maps) · `leaderboard_2026-07-04.json` ·
`docs/TIE_GTOW.md` (the EV ledger) · `docs/STATE.md` #3/#4 (the measured runs) · `tools/gtow_client/` (API client).
**PENDING (workflow `beat-gtow-feasibility`):** §7-verdicts from (a) the off-tree response mining, (b) the
architecture research, (c) the game-theory brief — fold in on completion.
