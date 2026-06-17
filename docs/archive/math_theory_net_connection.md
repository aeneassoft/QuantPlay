# Connecting the Deep CFR net to Mathematical Poker Theory (Claude)

# A. VALIDATION SUITE — Toy Games Your Net Must Rediscover

These are your unit tests. I give exact closed forms and flag uncertainty aggressively. **Critical caveat up front:** most of these are derived for a *fixed bet size b* (often b = pot, half-street, fixed-limit). Your net plays fcpa (fold/call/POT/all-in), so the natural comparison is the **b = P (pot-sized bet)** specialization. I give both the general formula and the b=P number.

---

## A.1 The AKQ Game

Setup (standard MoP version): Each player dealt one card from {A,K,Q}, no replacement; pot = P, single bet of size b allowed; A is the better card. This is the canonical half-street model. The *standard* MoP AKQ game uses **pot = 2, bet = 1** (each antes 1).

**Exact GTO (pot P=2, bet b=1):**

- **Player 1 (out of position, checks-and-calls model)** — the cleanest version is: P2 (in position) bets, P1 has the bluff-catcher (K).
- **Value bets:** A always bets.
- **Bluffs:** Q bluffs with frequency such that K is indifferent. Bluff-to-value ratio = b/(P+b) on the *betting* side; with b=1, P=2: bluff:value = 1:3, i.e. **bluff freq among value = 1/3**.
- **K (bluff-catcher) calls** with frequency = MDF-related: P1 calls Q-bets such that P2's Q-bluff is indifferent → call frequency on the bluff-catcher = **1 − b/(P+b)... ** 

⚠️ **FLAG: The AKQ game has several variants (who's in position, whether OOP can bet, whether it's the "second-best card bluffs" structure). I am NOT 100% certain which variant your net's HUNL reduction maps to, and the exact game value depends on the variant.** The robust, certain extractables from AKQ are:
- Q (worst hand) is the ONLY bluffing candidate; K NEVER bluffs (bluffing with the middle card is dominated). **This is a hard structural assertion you CAN test.**
- A always value-bets.
- **Bluff:value ratio = 1:2 when b=P**; = 1:3 when b = P/2 (half-pot). General: bluffs/value = b/(P+b)... 

⚠️ **FLAG on the ratio:** The value:bluff ratio at the river for a single bet is value:bluff = (P+b):b → bluff fraction *of betting range* = b/(P+2b). I give the rigorous derivation in A.4 — trust A.4's numbers over any AKQ-specific value, because AKQ's exact game value I cannot certify without pinning the variant.

**Game value (to in-position bettor), P=2,b=1:** I recall this is **+1/18 of a bet** in the standard symmetric version. ⚠️ **FLAG: not certain — verify by solving the 3×3 directly.** I recommend you solve AKQ yourself with a tiny LP as a *separate* sanity script and treat that as ground truth, not my recalled number.

---

## A.2 The [0,1] Half-Street Game

Setup: Hands uniform on [0,1] (lower = better, say). Only P2 (in position) can bet, fixed bet b into pot P; P1 checks, then calls/folds. This is the cleanest analytic one.

Let **s = b/P** (bet as fraction of pot).

**Exact GTO:**
- **P2 value-bets** the best fraction of hands; **bluffs** the worst fraction.
- **Bluffing frequency relative to value betting:** value region : bluff region such that bluff:value = s/(1+s)... 

The clean, certain results in terms of α and MDF (these ARE the [0,1] outcomes and they're exact):

- **α (optimal bluff fraction of the betting range), for bet b into pot P:**
$$\alpha = \frac{b}{P+2b} = \frac{s}{1+2s}$$
- **MDF (defender continue frequency):**
$$\text{MDF} = \frac{P}{P+b} = \frac{1}{1+s}$$
- **Bettor bluffs-to-value ratio:** $\frac{\text{bluffs}}{\text{value}} = \frac{b}{P+b} = \frac{s}{1+s}$

**For b = P (s=1, your POT action):**
- α = 1/3 (one-third of the betting range is bluffs) ✅ certain
- value:bluff = 2:1 ✅ certain
- MDF = 1/2 ✅ certain
- Defender folds 1/2 ✅ certain

⚠️ **FLAG on game value of the half-street [0,1]:** The aggressor's EV edge in the half-street [0,1] game I recall as on the order of **+b²/(P+2b)·(something)**; I do NOT trust my memory of the exact constant. **Do not assert a game-value number for the [0,1] half-street — solve it analytically or leave it out of the test suite.**

---

## A.3 The [0,1] Full-Street Game (both can bet / check-raise allowed)

Setup: Both players can bet; introduces check-raising, value of position, and a more complex threshold structure (three regions for the OOP player: bet-for-value, check-call, check-fold, plus a check-raise region).

**Honest flag:** ⚠️ **This game's full solution (the [0,1] "geometric" full-street with bet-then-bet) has multiple threshold parameters and I cannot reproduce the exact thresholds from memory with confidence.** What is *structurally* certain and testable:
- The OOP player develops a **check-raising range** (some of the best hands check intending to raise) — testable structural property.
- IP's betting range is **polarized** relative to the hands it checks back.
- Value of position is **strictly positive**.

**Do NOT write exact numeric assertions for A.3.** Use it only as a structural/qualitative test. If you want numbers here, derive them in a standalone solver script and promote them to tests only after independent verification.

---

## A.4 Clairvoyance Game (nuts-or-air vs bluff-catcher) — THE GOLD STANDARD TEST

This one is **fully certain and exact.** This should be your primary numeric unit test.

Setup: Bettor has either the nuts (wins always) or air (loses always at showdown). Caller has a pure bluff-catcher (beats air, loses to nuts). Pot = P before bet, bet size = b. Bettor chooses bet size and bluff frequency; caller chooses call frequency.

**Exact GTO (closed form, s = b/P):**

| Quantity | Formula | b=P (s=1) | b=½P (s=½) | b=2P (s=2) |
|---|---|---|---|---|
| Bluff fraction of betting range α | $\dfrac{b}{P+2b}=\dfrac{s}{1+2s}$ | **1/3** | 1/4 | 2/5 |
| Value:bluff ratio | $(P+b):b$ | **2:1** | 3:1 | 3:2 |
| Caller's calling freq (vs the bet) | $\dfrac{P}{P+b}=\dfrac{1}{1+s}$ | **1/2** | 2/3 | 1/3 |
| Caller's fold freq | $\dfrac{b}{P+b}=\dfrac{s}{1+s}$ | **1/2** | 1/3 | 2/3 |

**Indifference equations (the assertions):**
- Caller indifferent (call=fold): bettor bluffs so that $q_{\text{bluff}}/(q_{\text{value}}+q_{\text{bluff}}) = b/(P+2b)$.
- Bettor indifferent on bluffs (bet=check air): caller calls at $x^* = P/(P+b)$.

**Optimal bet size:** Because the bettor's EV is **monotonically increasing in b** in the pure clairvoyant game (more polarization = bet bigger, the caller can never punish you because your value is the nuts), **the clairvoyant bettor wants to bet as large as stack allows → all-in.** ✅ certain.

**Game value (to bettor), pure clairvoyance, bet size b:**
$$\text{EV}_{\text{bettor}} = \frac{b}{P+2b}\cdot P \quad\text{(extra EV from the betting option, above checking)}$$

⚠️ **FLAG: I am confident in the form (bettor's profit from the bluffing apparatus = α·P pulled from folds), but verify the additive baseline.** The cleanest *certain* statement: with bet b, the bettor wins the pot fraction $\frac{b}{P+2b}$ of P as extra value via fold equity on bluffs, balanced exactly. For b=P this is (1/3)·P. **Verify this constant against a direct EV calc before asserting.**

---

## A.5 Polarized vs Condensed Range

Setup: Bettor has polarized range (nuts + air), caller has condensed range (all medium bluff-catchers, no nuts, no trash). This reduces **exactly** to the clairvoyance game A.4 because every caller hand is functionally a bluff-catcher (beats all air, loses to all nuts).

**Therefore the A.4 numbers apply verbatim:**
- b=P: α=1/3, value:bluff=2:1, defend=1/2, fold=1/2. ✅
- Bettor wants max sizing (overbet/all-in) the more polarized. ✅

**The one addition:** with a polarized range and *deep* stacks, the GTO bet size **exceeds pot** (overbet). The exact overbet size in a single-street model is unbounded toward all-in for pure polarization; in multi-street it's tempered (see C). The testable single-street claim: **as polarization → pure, optimal s → max (all-in), and α → 1/2** (since α = s/(1+2s) → 1/2 as s→∞). ✅ certain limit.

---

# B. DESIGN — Theory → Net (NO contamination)

These shape the **action abstraction and feature space** (architecture choices), NOT training labels. Legitimate: you're giving the net the *capacity* to express GTO, then letting self-play find it.

## B.1 Bet sizes that matter → the pot-fraction menu

Your current abstraction is **fcpa = fold / call / POT / all-in**. Theory says this is **structurally impoverished** for expressing GTO:

- **Geometric sizing:** to bet the same fraction each street and get stacks in by the river, the per-street geometric size is $s = (SPR_{\text{final}}/SPR_{\text{now}})$-derived; specifically for n streets to felt, $s = (1+SPR)^{1/n} - 1$ per street. POT-only cannot express this.
- **Polarization → overbet:** A.4/A.5 prove polarized ranges want s > 1. You have all-in but **no intermediate overbet** (1.5×, 2×pot). The net literally cannot play the overbet-the-nuts line.
- **Small blocker/merge bets:** condensed-range value wants small (1/4–1/3 pot) bets. You have no sub-pot size.

**Recommended pot-fraction menu (capacity, not labels):**
$$\{0.33,\ 0.5,\ 0.75,\ 1.0,\ 1.5,\ 2.0,\ \text{all-in}\}$$
Minimum viable upgrade from fcpa: add **0.5×, 0.75×, 1.5×**. The 0.33 and 2.0 capture the merge and polar extremes. This does not inject strategy — it only removes a representational ceiling.

⚠️ Honest note: more sizes = larger action space = slower CFR convergence and more variance. There's a real tradeoff; 4–5 sizes is the usual sweet spot in research solvers. Don't go to 7 sizes naively.

## B.2 Features the net needs to EXPRESS GTO

Your 20-dim strength-bucketed feature vector is **insufficient to express GTO** — strength buckets collapse exactly the information GTO depends on. To play α-balanced polarized strategies the net must be able to distinguish:

1. **Range polarity / nut-advantage** — not just *your* hand strength but *which player's range is capped*. Strength buckets give hand-strength, not range-position. **Needed:** features encoding board-relative nuttedness.
2. **Blockers / card removal** — A.4's bluff selection in real HUNL is driven by blockers (bluff with hands that block villain's calls). A pure strength bucket throws this away. **Needed:** explicit blocker features (do you hold a card removing villain's nut/flush combos).
3. **SPR** — bet-sizing geometry (B.1) is a function of SPR. **Needed:** SPR as a continuous feature (you have stacks/pot, so derivable — make sure it's exposed).
4. **Board texture** — dynamic vs static determines draw-equity and thus polarization. **Needed:** texture features (paired, monotone, connected).
5. **Position / who-can-still-bet** — drives check-raise ranges (A.3).

**No contamination:** these are *inputs*, expanding what the net can condition on. You are not telling it the answer.

## B.3 Bounds the net's output MUST respect (sanity-check assertions)

For ANY single river-equivalent polarized bet of size s = b/P, the net's *own* betting strategy, when balanced, must satisfy (these are necessary GTO conditions, usable as **soft validation bounds**, not training targets):

$$\boxed{\alpha_{\text{bluff fraction of betting range}} = \frac{s}{1+2s}}$$
$$\boxed{\text{MDF}_{\text{defender continue}} = \frac{1}{1+s}}$$
$$\boxed{\text{bluff:value} = \frac{s}{1+s}}$$

Quick reference table (s, α, MDF):
| s (bet/pot) | α (bluff frac) | MDF | fold |
|---|---|---|---|
| 0.33 | 0.20 | 0.75 | 0.25 |
| 0.5 | 0.25 | 0.667 | 0.333 |
| 0.75 | 0.30 | 0.571 | 0.429 |
| 1.0 | 0.333 | 0.5 | 0.5 |
| 1.5 | 0.375 | 0.4 | 0.6 |
| 2.0 | 0.40 | 0.333 | 0.667 |

All ✅ certain (these are the algebra of A.2/A.4).

**How to use without contamination:** Run the trained net on *constructed* terminal-ish polarized river spots; measure its realized bluff fraction and defender continue frequency; assert they're within tolerance (say ±0.05) of these. **If it deviates badly with a pure polarized range, that's a bug/under-convergence signal, not a label to train on.**

---

# C. INTERPRETATION + HONEST LIMITS

## C.1 How to read the trained net in theory terms

- **Is it bluffing at α?** Construct synthetic polarized river nodes (give the net a range that is provably nuts-or-air), read off its bet-then-bluff frequency, compare to s/(1+2s). Matches → it discovered balance.
- **Is it defending at MDF?** Give it a bluff-catcher vs a known polarized bettor; its continue frequency should track 1/(1+s) when it believes the opponent is balanced, and should *deviate exploitatively* against an unbalanced opponent (it won't have an opponent model in pure self-play GTO — so expect ~MDF, NOT exploitation; that's correct).
- **Is it polarizing?** Check whether large bets carry both its strongest and weakest hands and whether medium hands check. Polarization = bimodal strength in the betting range.
- **Overbetting the nuts?** Only testable if you give it overbet sizes (B.1). If you don't, absence of overbets is a *representation* failure, not a learning failure — don't misread it.

## C.2 What the theory CANNOT give you (be honest)

1. **Multi-street range-vs-range HUNL GTO has no closed form.** Every clean number above is single-street or fixed-size. The net's actual job — the equilibrium of the full 200bb fcpa tree — is genuinely unsolved analytically. Theory is the **unit test on the leaves**, not the answer to the tree.

2. **α and MDF are river/terminal results.** On flop/turn they bend: future betting, range morphing, and equity realization mean defenders continue *more* than river-MDF (equity to realize) and bluffs include *semi-bluffs* (positive equity when called). **Do NOT assert river-MDF on flop nodes — your net will (correctly) violate it.** This is the #1 way naive theory tests give false failures.

3. **Optimal bet size in multi-street ≠ "always max" (contra A.4).** The clairvoyant "bet bigger always" breaks because real ranges aren't pure-polar, future streets exist, and overbetting caps your own range. Geometric/SPR-driven sizing dominates. So A.4's "go all-in" intuition is a single-street artifact — **don't test for it in multi-street spots.**

4. **Blocker-driven bluff selection** is real GTO but invisible to strength buckets and to all the toy-game value:bluff ratios (which only fix the *quantity*, not *which combos*). The toy games tell you *how many* bluffs, never *which*. Your net may get the count right and selection wrong (or right via features it has).

5. **Mixed strategies / indifference regions:** GTO is full of mixing. The net's softmax output should show *mixing* near indifference points, not pure actions. If your net always plays pure, that's a sign it found a best-response-to-self pocket, not equilibrium — a convergence diagnostic theory can flag but not fix.

## C.3 Bottom line on contamination boundary

- **Allowed (scaffold/test):** action-size menu, feature capacity, leaf-node α/MDF assertions on constructed polarized spots, Leduc exact-exploitability (your existing correctness gate — keep it, it's the best test you have).
- **Forbidden (contamination):** seeding strategies with α-balanced ranges, reward-shaping toward MDF, imitation of solver outputs. Your -72bb/100 imitation floor is exactly the thing to *beat*, not to learn from.

**Strongest single recommendation:** treat **A.4 (clairvoyance, b=P: α=1/3, defend=1/2, value:bluff=2:1)** and **Leduc exact exploitability** as your two hard numeric gates. Demote AKQ game-value, [0,1] half/full-street game-values, and any "always overbet" test to *structural/qualitative* checks until you've independently re-derived their constants with a standalone LP solver — I've flagged each number I couldn't certify above.
