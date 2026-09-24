# Brown (2026): Value, Bluff, and Cyclic Dominance — VNM on the real 169×169 matrix

**Source:** Aaron Brown, *"Value, Bluff, and Cyclic Dominance: Completing the Von Neumann Poker
Project"*, version of 3 May 2026, SSRN working paper (`books/papers/Poker Math 2026/ssrn-6709840.pdf`,
36 pp. incl. supplement S1–S9). Full extraction 2026-08-16, every number with a page reference (p. = printed
page number = PDF page). **Honesty convention of this document:** what the paper does not
contain is listed below under NOT FOUND; internal inconsistencies of the paper are marked.

**The game (VNM betting, pp. 1–2, pp. 28–29):** pot = 1, bet = B (pot-relative). Alice first:
check → immediate showdown for 1; bet B → Bob folds (Alice wins 1) or calls (showdown for
1+2B; winner +1+B, loser −B relative to the stake). One street, no raises. Hands = the
169 strategic preflop classes of heads-up Texas Hold'em; showdown via the real equity matrix.

---

## 1. The four model variants (2×2 factorial design, p. 3)

| Variant | Matrix | probabilistic | transitive |
|---|---|---|---|
| **Real** | the real 169×169 equity matrix W | yes | **no** (7,108 non-transitive triples, p. 2) |
| **Pythagorean** | Mᵢⱼ = eᵢ²/(eᵢ²+eⱼ²), eᵢ = row mean of W (win rate vs. a random hand). Squaring chosen so that the most extreme matchups lie at 90–95% as in reality (p. 3) | yes | yes |
| **Deterministic** | W binarized: Mᵢⱼ = 1 if Wᵢⱼ > 0.5, else 0; exact ties stay 0.5 (p. 3) | no | **no** |
| **Both** | Pythagorean binarized — closest to the VNM original (p. 3) | no | yes |

The classic VNM [0,1] uniform case (pp. 28–29, S3) is the corner in which ALL simplifications
hold simultaneously; "Both" is its finite 169-hand analogue.

**Equity matrix construction (p. 27, S2):** Wᵢⱼ = P(i wins) + 0.5·P(split), via **exact
enumeration** of all C(48,5) = 1,712,304 boards per pairing; suit cases for two suited hands
averaged with frequency weights. Combo counts cᵢ = 6 (pairs) / 4 (suited) / 12 (offsuit), Σ = 1,326;
card removal via conditional priors p(j|i) = c(j|i)/Σₖc(k|i) (e.g. AcKs blocks AKs 4→3).

---

## 2. All quantitative results (with page references)

### 2.1 The cycle foundation
- AKo beats JTs **59.5%**; JTs beats 33 **53.2%**; 33 beats AKo **53.4%** (p. 2).
  Cycle margins α = 0.190, β = 0.064, γ = 0.068 (p. 6); row equities eᴬᴷᵒ = 0.520,
  eᴶᵀˢ = 0.479, e₃₃ = 0.501 (p. 31, S6).
- The 169 matrix contains **7,108 non-transitive triples** (p. 2).
- RPS choice game on these three hands: equilibrium AKo ≈ **20%**, 33 ≈ **59%**, JTs ≈ 21%
  (p. 6) — the strongest hand is played least often; frequency ∝ prey-beats-predator margin,
  one's own strength is **irrelevant** (p. 6).
- Betting game on the three hands (pp. 7–8, S6 pp. 31–33): B < 7.4: Alice bets AKo+33 (value),
  checks JTs, Bob calls everything. At B ≈ 7.44 Bob's call threshold B/(1+2B) exactly reaches JTs'
  posterior win rate 0.4685 (= 0.5·0.405 + 0.5·0.532) → Bob starts folding JTs → **JTs enters
  as a bluff** (cyclic bluff: weakest hand in raw equity, but predator of 33/prey of
  AKo). At high B, AKo also mixes; **33 bets and calls at 100% for every B** (predator of AKo,
  strongest hand against the bluffing range; full grid table B = 0.001…100 in S6, p. 32).

### 2.2 The taxonomy of the Real game (pp. 8–10)
- At 0 < B < 0.10 Alice bets exactly **88 hands** (value); Bob calls everything (p. 8).
- **Three phases** (pp. 8–9): (1) B 0.10–0.72: Bob starts folding, no bluffs — the regime of
  most poker game theory; (2) from B = 0.72: medium value hands **pivot** to bluffs, new
  bluffs enter; (3) from B = 5: exits begin.
- Taxonomy: **88 value hands** (of which 87 are "temporary value": pivot → exit, no return; **AA
  never pivots and never exits** within the grid) + **27 pure bluffs** (never in a value phase; entry only at
  positive B, exit at high B) + **54 passive hands** (bet at no B) (pp. 9–10).
- **The 27 pure bluffs (complete list, p. 9):** 32s, 42s, 43s, 52s, 53s, 54s, 54o, 62s,
  63s, 64s, 65s, 65o, 73s, 74s, 75s, 76s, 76o, 84s, 85s, 86s, 87s, 96s, 97s, J5s, Q5o, T6s, T8o.
  Raw-equity band of the pure bluffs: **0.36–0.50** (p. 17) — NOT the bottom of the distribution.
- **65s outlier:** exit at **B = 225**, >3× longer than the next-longest persister; raw equity
  0.430 = rank **128/169** (p. 9, p. 22). The clearest single-hand fingerprint of cyclic
  dominance.

### 2.3 The two laws: pivot vs. exit order (p. 10, table p. 19)

| Ranking | Spearman vs **pivot** order | Spearman vs **exit** order |
|---|---|---|
| Raw equity | **0.98** | 0.73 |
| Chen formula | 0.72 | **0.88** |
| Sklansky group (inverted) | 0.68 | 0.85 |

- **Law 1:** The value→bluff pivot order follows raw equity almost perfectly (0.98) — the
  classic VNM part is robust (p. 10, p. 16, p. 21).
- **Law 2:** The exit order follows "playability": the practitioner rankings (Chen 0.88,
  Sklansky 0.85), which were NOT built for this game, beat raw equity (0.73),
  because suitedness/connectedness encode **cycle density** (p. 10, pp. 19–21). Chen examples:
  AKs = 12, 22 = 5, 72o = −1 (p. 19).
- **Bluff persistence inverted:** within the 27 pure bluffs, exit B correlates with raw equity at
  **−0.42** — the weaker the bluff, the longer it stays (p. 11). Exits: 65s = 225,
  54s = 59, 43s = 54, 53s = 41; shortest: J5s = 0.98, Q5o = 1.15, T6s = 1.19, T8o = 1.32 (p. 11).

### 2.4 Four-matrix decomposition (pp. 11–14)

Category counts (table p. 12):

| Matrix | Value | Pure bluff | Passive |
|---|---|---|---|
| Real | 88 | 27 | 54 |
| Pythagorean | 93 | 5 (*) | 71 |
| Deterministic | 83 | 14 | 72 |
| Both | 83 | 11 | 75 |

(*) **Paper inconsistency:** S8 (p. 35) gives **7** pure bluffs for Pythagorean (= 5 Pyth-only
+ 87s, T6s, which are also real bluffs); the table on p. 12 says 5. Not resolvable from the PDF.

- **The classic core: 106/169 hands** are categorized identically in all four matrices
  (p. 12): **70 classic value hands** (incl. AA; pairs, all Ax/Kx, strongest broadways) +
  **36 classic passive hands** (offsuit junk) + **0 classic bluffs**. **Not a single hand
  is a bluff in all four variants** — bluffing is structurally far more sensitive to the
  matrix geometry than value/passivity (p. 12).
- **The 27 real bluffs, decomposed by required features (p. 13):**
  - **7 need non-transitivity, no probabilism** (real+det, not in the transitive ones):
    **43s, 53s, 54s, 54o, 63s, 64s, 65s** — the cleanest cyclic bluffs; identical under
    all three transitive construction variants (S8, p. 35).
  - **14 need both** (real only): 65o, 73s, 74s, 75s, 76s, 76o, 84s, 85s, 86s, 96s, 97s,
    J5s, Q5o, T8o.
  - **4 complex cases:** 32s, 42s (real+Both); 52s, 62s (real+det+Both) — bottom of the
    equity distribution, specifically sensitive to the Pythagorean approximation.
  - **2 need only probabilism** (real+Pyth, not deterministic): **87s, T6s**.
  - Balance: 25/27 need non-transitivity in some form (21 absolute + 4), 2 need
    probabilism (p. 13).
- **15 phantom bluffs of the simplified games** (bluff there, passive in real; pp. 13–14):
  - 5 Pythagorean only: **98o, J3s, J4s, Q3o, Q4o** — the "bluffs of scalar thinking"; in real
    a mistake, because the cycles put other candidates into that role (pp. 13–14).
  - 5 Both only: **43o, 72o, 73o, 82o, 83o** — the absolutely weakest offsuit junk; mean
    cycle count 7, an order of magnitude below the cyclic bluffs (p. 14).
  - 3 Deterministic only + 2 in Det&Both — **hands NOT named** (p. 14).

### 2.5 Cepheus comparison (pp. 17–19)
- Cepheus (HU limit, Bowling et al. 2015), dealer's first action: 149 raise / 19 fold / 1 mixed (p. 17).
- Best match at **B ≈ 2.05**: Jaccard **0.67**; Alice bets 100 hands there, **all 100 in
  Cepheus' raising range**; Alice's range is a **strict subset** of Cepheus at EVERY B
  (p. 17). B ≈ 2.05 ≈ **4× the nominal preflop bet-to-pot** (nominal ≈ 0.5, effective ≈ 1.5)
  — the multiplier measures the implied-odds effect of the later streets (p. 17, p. 22).
- The 49 Cepheus-not-Alice hands (p. 18; the paper once says "50-hand gap" — inconsistency,
  presumably the 1 mixed hand): suited broadway-with-rag (J2s–J6s, Q2s–Q4s, T2s–T6s), offsuit
  broadway-with-rag (J3o–J8o, Q3o–Q7o), low offsuit connectors (43o, 53o, 64o, 74o, 75o,
  76o), low/medium suited (73s, 83s, 84s, 92s–95s, 85s–98s) — throughout, hands whose
  multi-street equity carries the bet but whose single-street equity does not.
- **The author's honesty about purpose:** one studies VNM betting "to extract strategic insight
  applicable beyond THE, not to improve THE play" (p. 19).

### 2.6 Practitioner comparison (pp. 19–20)
- Sklansky groups 1–6 = 52 hands; the model bets ≥ 88 at low B; **62 hands** that the
  model plays (in some matrix) are rated by Sklansky as groups 7–9 ("fold from most
  positions") — and **Cepheus also raises all 62** (p. 20). HU plays fundamentally wider than
  full-ring cutoffs; Sklansky's ORDER is good, his cutoffs are for a different game.

### 2.7 Solver + robustness (S7–S8, pp. 33–35)
- Iterative best response with smoothing: init r=0/c=1; ε = 10⁻⁹; smoothing α = 0.01; convergence
  Δ < 10⁻⁶; max 10,000 iterations; otherwise tail average of the last 2,000 (fictitious-play mean).
- Grid: **1,352 B values on [0.1, 315]** (spacing 0.02 up to B=0.72; 0.001 in the pivot zone
  [0.72, 1.50]; 0.005–0.5 up to 100; 5.0 up to 315) (p. 34). — **Inconsistency:** S9 (p. 35) speaks
  of "48 B values" for the published CSVs.
- Clean convergence: real 27% (avg. 12,694 iter.), Pyth 66% (avg. 3,567), det/Both 3% (avg. 9,738).
- **Exploitability check:** real/Pyth max < 0.001 pot units (real max 0.0009 at B ≈ 145;
  Pyth 0.00002); det/Both up to 0.063 (many indifference points). Categorizations, by contrast, are robust.
- **S8 robustness:** transitive alternatives linear eᵢ/(eᵢ+eⱼ) and logit: the classic core
  shifts by ≤ 5 hands; the **7 cycle bluffs are identical** under all constructions;
  needs-both shifts by ≤ 1 hand; transitive bluff count: Pyth 7 / linear 3 / logit 6.

---

## 3. Closed-form formulas (exact, as in the paper)

1. **Bob's call threshold (pot odds; p. 7, S4 p. 30):** Bob calls with hand j iff his
   posterior win probability > **B/(1+2B)** (pot = 1). Complementary form via the
   loss probability: threshold **(1+B)/(1+2B)**. In general (pot P before the bet,
   absolute bet b): required equity = **b/(P+2b)** — identical to our
   `equity_needed_to_call`. Derivation: 0 = (1+B) − E[W]·(1+2B).
2. **Alice's bet EV (S4, p. 29):** V_bet(i) = Σⱼ p(j|i)·[(1−cⱼ)·1 + cⱼ·(Wᵢⱼ·(1+2B) − B)].
3. **Alice's check EV (S4, p. 29):** V_check(i) = Σⱼ p(j|i)·Wᵢⱼ.
4. **Bob's call EV (S4, p. 30):** V_call(j) = Σᵢ q(i|j,bet)·[(1+B) − Wᵢⱼ·(1+2B)]; fold EV = 0.
5. **Bob's posterior (S4, p. 30, as printed):** q(i|j,bet) = p(i|j)·cᵢ·rᵢ / Σₖ p(k|j)·cₖ·rₖ —
   **notation collision in the paper:** cᵢ here is the combo count from S2, NOT Bob's
   call frequency cⱼ; whether p(i|j) is already combo-weighted (in which case cᵢ would be counted twice), the
   PDF leaves open.
6. **Equilibrium (complementarity, S4, p. 30):** rᵢ > 0 ⟹ V_bet ≥ V_check; rᵢ < 1 ⟹
   V_bet ≤ V_check; cⱼ > 0 ⟹ V_call ≥ 0; cⱼ < 1 ⟹ V_call ≤ 0.
7. **RPS predator-prey law (p. 6; proof S5, pp. 30–31):** margins α = 2a−1, β = 2b−1,
   γ = 2c−1 ⟹ equilibrium frequencies **r = β/(α+β+γ), p = α/(α+β+γ), s = γ/(α+β+γ)**.
   Proof: M = W − ½J is antisymmetric; symmetric Nash ⟺ Mx = 0; kernel of the 3×3
   antisymmetric M = the cross-product vector (β/2, α/2, γ/2). Holds for every symmetric
   3×3 zero-sum game with positive margins.
8. **Pythagorean approximation (p. 3):** P(i beats j) = eᵢ²/(eᵢ²+eⱼ²).
9. **Equity definition (S2, p. 27):** Wᵢⱼ = P(win) + ½·P(split) — representable as an exact fraction:
   (2·wins + splits)/(2·1,712,304).
10. **Three-hand indifference (S6, p. 32):** 0.4685 = B/(1+2B) ⟹ B ≈ 7.44 (JTs'
    bluff-emergence threshold).
11. **Classic VNM [0,1] model (S3, p. 28):** threshold structure 0 < t_bluff < t_value < 1,
    Bob threshold t_call; qualitatively: t_value ↑, t_bluff ↓, t_call ↑ with B; bluff:value ratio
    in Alice's range = Bob's pot odds (indifference property). **The explicit closed-form
    expressions t_v(B), t_b(B), t_c(B) are referenced, but NOT printed in the PDF.**

---

## 4. WIRING PROPOSALS (oracle checks, `pokerbot/autogym/oracle.py`)

All four follow the safety contract (AUTOGYM_PLAN): knobs = measurement config (locked for the improver),
mandatory Fraction reference before wiring (E1), the F tier generates proposals, never patches.

### V1 — `value_ordnung` (F) ★ the most promising: range-free order check
**Idea (Law 1, p. 10):** On the VALUE side the equilibrium follows the equity order almost
perfectly (Spearman 0.98). So: within a node bucket (street × B bucket × node_typ)
hero's value bets must form an **upper set of the equity order** — if hero bets class X
but checks a strictly higher-equity class Y in the same bucket, that is an order violation
= a lead. **Crucial (p. 11, p. 13):** the Brown-27 bluff classes are EXEMPT from the
check — there, an order violation is equilibrium-conforming (bluff exit correlates −0.42).
- **Tier:** F (aggregated per bucket, n ≥ 30); individual violations as a lead list in the proof.
- **Fields:** street, pot, amount/to_call (→ B bucket), action, hero_hole (→ 169 class);
  range-free — no villain_hole needed. Preflop variant first (class equity well-defined);
  postflop variant later via hindsight equity (needs villain_hole, becomes L-style noisy).
- **Fraction reference:** Spearman on integer ranks is exactly rational (Fraction).
  Reference order = exactly enumerated 169 equities ((2·wins+splits)/(2·1,712,304), S2).
  **CAUTION:** the repo asset `knowledge_base/ranges/preflop_eqmatrix.json` is MC with sims=600
  — NOT suitable as a reference; enumerate exactly once before wiring (CPU-cheap, treys).
- **Knob bounds:** `ORDNUNG_RHO_MIN` ∈ [0.80, 0.98] (start 0.90; the Brown anchor 0.98 is the
  single-street upper bound, multi-street play may fall below it); `N_MIN_BUCKET` = 30 (fixed);
  exception set = Brown-27 (fixed list, NOT a knob).

### V2 — `fold_ordnung` (F): the defensive mirror
**Idea (Bob's threshold structure, p. 7/S4):** Bob's equilibrium continue set is the top of the
posterior win-rate order. Range-free mirror of V1: in the same bucket hero calls class X
but folds a strictly higher-equity class Y = order violation. Covers exactly the
seesaw breakage class (v8: check range transparent) without prescribing a frequency —
pure order, no quota; complementary to the (refuted) mdf_guard.
- **Tier:** F. **Fields:** as V1 + call_closes_action (wave-1 field, already planned).
- **Fraction reference:** identical to V1 (the same exact order, the same Spearman fraction).
- **Knob bounds:** shares `ORDNUNG_RHO_MIN` with V1 OR its own `FOLD_RHO_MIN` ∈ [0.75, 0.95]
  (defense is posterior-dependent, hence looser); N_MIN = 30 (fixed).

### V3 — `bluff_struktur` (F): bluffs from the cycle region, never from the junk
**Idea (pp. 13–14, p. 17):** real bluffs come from the equity band 0.36–0.50 (suited
connectors/gappers, high cycle density); bottom-junk bluffs (Brown-54 passive + the Both-only class
43o/72o/73o/82o/83o) exist only in the simplified games. Check: share of
hero bluffs (bet/raise with hindsight equity < threshold) from Brown passive classes > band = finding.
- **Tier:** F (aggregate); needs hindsight → HU gym with villain_hole only; note the L-style fuzziness
  honestly in the proof.
- **Fields:** hero_hole (class), villain_hole, board, street, action, amount.
- **Fraction reference:** set classification is exact (class lists fixed); share =
  Fraction(k, n); equity band bounds 0.36/0.50 documented as Fraction(9,25)/Fraction(1,2).
- **Knob bounds:** `BLUFF_EQ_MAX` (hindsight equity below which a bet counts as a bluff)
  ∈ [0.15, 0.35] (start 0.25); `JUNK_BLUFF_BAND` (allowed junk share) ∈ [0.10, 0.35]
  (start 0.20 — multi-street poker also bluffs junk with blockers; never clamp to 0).

### V4 — `bluff_persistenz_hoch_b` (L): the wrong bluffs in the big pot
**Idea (p. 11):** the persistence order inverts — at high B only the cycle-core
bluffs (65s type) survive; the short persisters (J5s exit 0.98; Q5o 1.15; T6s 1.19; T8o 1.32) and all
phantom bluffs are alien to equilibrium at B ≥ 2. Check: hero bluff (detected as in V3) at
bet-to-pot ≥ B_HOCH with class ∈ {J5s, Q5o, T6s, T8o} ∪ Brown-54 = individual lead.
- **Tier:** L (bookable per decision, severity = (req−eq)·pot logic like the existing L checks).
- **Fields:** as V3 + pot/amount for the B ratio.
- **Fraction reference:** exit thresholds are empirical grid values (not a formula) — document them as a fixed
  ANCHOR list, not as a computed reference; the B-ratio fraction amount/pot is exact.
- **Knob bounds:** `B_HOCH_MIN` ∈ [1.5, 5.0] (start 2.0 — the Cepheus best-match point);
  class lists fixed (not a knob).

**Transfer honesty (binding for all four):** Brown's model is ONE street, preflop classes,
HU. V1 preflop is the cleanest transfer; V3/V4 transfer class priors to a game in
which postflop bluffs are board-/blocker-driven — hence F/L (lead generators), never P, and
make every calibration journal-ready BEFORE validation (FOLD_LEAD_MARGIN precedent).

---

## 5. BOT DOCTRINE — what Brown makes binding for candidate design

1. **Bluff selection is STRUCTURAL, never a quota.** Zero hands are bluffs in all four matrices
   (p. 12): WHICH weak hand bluffs is pure matrix geometry (cycle position/suitedness;
   in the multi-street game: blockers/board/sizing), not weakness and not a target frequency.
   This is the independent theoretical confirmation of the fourth measurement data point (mdf_guard
   −3.26 NEUTRAL): **frequency without selection does not print — candidates must carry selection.**
2. **The value side is classic and robust** (pivot Spearman 0.98; 70 value hands in all
   four matrices): order checks and equity logic are legitimate, nearly invariant
   test grounds on the value side. On the bluff side, order fidelity is explicitly NOT to be
   expected (−0.42) — an oracle that measures bluffs against the equity order measures wrongly.
3. **Role is a function of the bet size, not of the hand** (pivot at ~0.72+, exits from 5,
   87/88 value hands change role): candidate design must make hand roles
   sizing-conditional; every static hand→role table is wrong according to Brown.
4. **Frequencies follow the predator-prey margin, not one's own strength** (r ∝ β; AKo 20% vs
   33 59%): formally supports the seesaw doctrine — the equilibrium's mixing frequencies
   CANNOT be read off one's own hand strength; whoever couples their mixing to strength (or flattens it)
   measurably leaves the equilibrium. Not a new knob, but the reason why
   Purify-style flattening broke live (−58).
5. **Playability = cycle density** (Chen 0.88/Sklansky 0.85 > equity 0.73 on the exit order):
   suitedness/connectedness features in advisor MLPs are not heuristic folklore, but
   proxies of a measurable equilibrium quantity. Consistent with the "soup meat" doctrine: as features, never dogma.
6. **HU plays wide** (62 Sklansky-7–9 hands that the model AND Cepheus play, p. 20): every
   tightness intuition from full-ring sources is not applicable to HU preflop.
7. **Transfer limit (Brown himself, p. 19):** single-street VNM does not directly improve THE play;
   the Cepheus comparison shows the VNM range as a strict subset (multi-street equity is missing).
   Brown's lists belong in CHECKS and PRIORS (section 4), never as direct action rules in
   `bot.py`.

---

## 6. NOT FOUND / inconsistencies (honestly)

- **Not printed:** the closed-form expressions t_v(B), t_b(B), t_c(B) of the classic
  [0,1] model (only referenced, p. 28); the pivot B values of the 87 hands; the complete
  88-hand value list and 54-hand passive list as an explicit enumeration (only described qualitatively +
  examples 32o, 42o, J2o, T2o, 92o); the names of the 3 Det-only and 2 Det&Both bluffs (p. 14);
  a formal definition of "cycle count / cycle density" (only the value 7 for the
  Both-only bluffs, p. 14); the supplement CSVs/code (holdem_real.csv, gto_grid_full*.csv,
  solve_one_B_v4.py — referenced, not in the PDF).
- **Paper inconsistencies:** Pythagorean bluff count 5 (table p. 12) vs 7 (S8, p. 35);
  "49 hands" (p. 17) vs "50-hand gap" (p. 18); grid "1,352 B values" (S7, p. 34) vs "48 B values"
  (S9, p. 35); the Cassidy 2015 reference carries "[volume and pages to confirm]" — the paper is
  a working-paper draft (version 2026-05-03).
- **Not in the paper:** 6-max/multiway statements; postflop bluff selection (blockers); raises;
  any AIVAT/bb measurement. All numbers here are single-street VNM equilibria.
