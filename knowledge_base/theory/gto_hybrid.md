# GTO hybrid (near-GTO baseline + adaptive regime switch)

## Math (OpenAI gpt-5.1)

I structure this in three blocks, with formulas and as little "story" as possible.

---

## 1) GTO approximation with what you have

### 1.1 Fundamental target quantity

Let  
- \(G\) be the real NLHE game,  
- \(\sigma^*\) a Nash equilibrium strategy profile,  
- \(u_i(\sigma)\) the expected value for player \(i\) in the game (in bb/hand or similar).  

For 2‑player zero-sum games:

\[
\text{Exploitability}(\sigma) 
= \max_{\tau} u_2(\sigma,\tau) - u_2(\sigma^*, \sigma^*)
= \max_{\tau} u_1(\tau,\sigma) - u_1(\sigma^*, \sigma^*)
\]

In bb/100: \(\epsilon := \text{Exploitability}(\sigma)\) is the maximum possible loss relative to perfect GTO play when an adversarial opponent exploits perfectly.

Near GTO means: \(\epsilon\) "small" (e.g. < 5–10 bb/100) on the relevant subset of states (positions, stack sizes, etc.).

---

### 1.2 Deep CFR (neural) as the core baseline

Your validation: Leduc with Deep CFR, NashConv from 2.33 → 0.33.  
In a 2‑player zero-sum game, NashConv essentially corresponds to the sum of the players' exploitabilities; for a symmetric game:

\[
\text{NashConv}(\sigma) = \text{Exploitability}_1(\sigma) + \text{Exploitability}_2(\sigma) \approx 2\epsilon
\]

so \(\epsilon \approx \frac{\text{NashConv}}{2}\).

**Transfer to NLHE:**

1. **Game abstraction**  
   - Discretization of the action sizes: e.g. {Check, 33%, 75%, 125%, All-in} instead of continuous.  
   - Bucketing of hand strengths or equity/draw structure (similar to Pluribus / Libratus patterns, but you can use the information from Acevedo: category splitting by "top pair good kicker", "nut FD + overcards", etc.).  
   - Board classes (dry / middling / wet, paired / unpaired, etc.).

2. **Deep CFR on the abstracted game**  
   - Exactly the OpenSpiel+PyTorch pipeline, but on your NLHE abstraction game.  
   - Output: strategy profiles \(\hat{\sigma}\) with an **upper bound** on the exploitability in the abstracted game: \(\epsilon_{\text{abs}}\).

3. **De-abstraction (action translation)**  
   - Mapping of abstract actions to real bet sizes:  
     - e.g. "75% pot" in the model → 70–80% pot in reality, with fine jitter.  
   - Map hands from buckets to concrete combos: the same mixed strategy within a bucket.  

The total exploitability in the real game is then:

\[
\epsilon_{\text{real}} \le \epsilon_{\text{abs}} + \epsilon_{\text{abstraction}}
\]

\(\epsilon_{\text{abstraction}}\) is the error due to bucketing + action discretization. It can be measured as a rough upper bound by, in the abstracted game:

- comparing different abstraction granularities (coarse vs. fine buckets) and
- using the strategy of the finer abstraction as the opponent for the coarse one.

The difference in EV represents an empirical upper bound on the abstraction error.

**Realistically attainable degree of GTO**

With modern hardware (GPU pods, Deep CFR or DCFR) and good abstraction:

- Exploitability in the abstracted game in the range \< 10^-3 pot per hand is common in research (Libratus, Pluribus).  
- Transferred to real money: \(\epsilon_{\text{real}} \lesssim 1–3\) bb/100 for typical stacks/spots is realistic, provided
  - the action sets are sensible (approx. 4–6 sizes/street),
  - the board/hand buckets are fine enough (100–1000 buckets, depending on the street).

**Concrete pipeline for you**

1. **Preflop**  
   - Use a push/fold Nash solver (MCCFR) for <= 20–25 bb stacks → nearly GTO push/fold ranges.  
   - For deeper stacks: book ranges from *Modern Poker Theory* as the starting policy. Then:
     - Define preflop NLHE with action abstraction (raise sizes: 2–2.5x, 3x, 4x, all-in, etc.) as a separate game.
     - Run Deep CFR, starting from the book ranges as the initial policy (warm start).  
   - Output: preflop policy \(\hat{\sigma}^{\text{PF}}\) with low abstracted exploitability.

2. **Postflop**  
   - Train separate subgames and strategies for typical pot configurations (single-raised pot, 3bet pot, blind vs blind, etc.).  
   - Starting approximation from Acevedo/Chen:  
     - e.g. c-bet frequencies via toy-game formulas (see below),  
     - range balancing based on MDF, etc.  
   - Then refine with Deep CFR.

3. **Exploit bot**  
   - Your current exploiter policy \(\sigma^{\text{exploit}}\) is additionally trained as an explicit "best-response-oriented" policy network that uses the GTO baseline as a prior, but optimizes RL-style on population leaks.

---

## 2) Bill Chen / toy games → near-GTO baseline without a solver

Core ideas you can use mathematically:

### 2.1 Indifference principle

In zero-sum games in equilibrium: the opponent is indifferent between all responses he plays with positive probability.

Formally, a simple river bluff spot:

- Pot: \(P\), hero can bluff with frequency \(f_B\), bet size \(B\).  
- Villain calls with frequency \(c\).  
- Hero has two hand classes: value (V) and bluff (L).  
- EV of the call against hero's mixed strategy:

\[
\text{EV}_\text{Villain}(\text{Call}) = x \quad \text{EV}_\text{Villain}(\text{Fold}) = 0
\]

In equilibrium: \(x=0\) (indifference).

More concretely:

Let  
- the bluff share in hero's betting range be \(\alpha\),  
- the value share: \(1-\alpha\).

Villain wins when calling against a bluff: \(P+B\)  
and loses when calling against value: \(B\).

\[
\text{EV}_\text{Villain}(\text{Call}) = \alpha (P+B) - (1-\alpha) B = 0
\]

\[
\Rightarrow \alpha (P+B) = (1-\alpha) B \Rightarrow \alpha = \frac{B}{P+2B}
\]

This is the optimal **bluff frequency in the betting range** for this 1-street toy spot (equal equity 0/1 setup).

---

### 2.2 Chen/Ankenman formula: \(\alpha = \frac{s}{1+s}\)

Many sources give the bluff frequency directly as a function of the bet size \(s = B/P\) (bet as a pot multiple). The cleanly derived standard case (calibrated to the 0/1 game) is

\[
\alpha^* = \frac{s}{1+s} \quad\text{(under a suitable normalization of the payoff game)}
\]

The exact expression depends on the chosen toy-game definition (Chen uses [0,1] distributions instead of 0/1 binary payoffs). Important: structurally you always have the form

\[
\alpha^*(s) = \frac{\text{function of } s}{\text{function of } s + \text{constant}}
\]

You can take the exact toy setups from *The Mathematics of Poker* and, for the payoff normalization used there:

- held-out formulas for **equilibrium bluff frequencies** per bet size,
- and derive range splits from them.

Usable in the engine:

**Heuristic for river bets:**

- Input: \(s = B/P\) (target bet size).  
- Compute the optimal bluff density \(\alpha^*(s)\) from the toy formula (e.g. \(\alpha = s/(1+s)\) or the correct variant for your setup).  
- Range split:
  - sort hands by EV as a bet (value) vs. check.  
  - define the value part down to the marginal value hand (e.g. top X %).  
  - bluff candidates = hands with clearly negative showdown EV.  
  - choose as many bluffs as needed so that \(\frac{\text{\#Bluffs}}{\text{\#Value + \#Bluffs}} \approx \alpha^*(s)\).

This gives you a **toy-game-calibrated balance** for all "pure" river decisions, even without a complete solver.

---

### 2.3 Minimum defense frequency (MDF)

MDF follows from the condition that the opponent does not automatically have +EV with a pure bluff bet.

Pot before the bet: \(P\), bet: \(B\).  
Villain always bluffs, hero folds with frequency \(f\).  
EV of the bluffer:

\[
\text{EV}_\text{Bluff} = f \cdot P - (1-f) \cdot B
\]

MDF is the smallest call frequency \(c = 1-f\) such that \(\text{EV}_\text{Bluff} \le 0\):

\[
fP - (1-f) B \le 0 \Rightarrow fP \le (1-f) B
\Rightarrow f \le \frac{B}{P+B}
\Rightarrow c \ge 1 - \frac{B}{P+B} = \frac{P}{P+B}
\]

**MDF formula:**

\[
\text{MDF} = \frac{P}{P+B}
\]

Usable as the baseline call frequency when bluff-catching, if you assume that villain could bluff roughly "maximally".

Strategically:  
- Sort your hands by EV of calling vs. folding (or by hand strength / blocker quality).  
- Call as many combos as needed so that your call frequency is \(\approx \text{MDF}\).

This is "GTO-ish" against a bluff-heavy pot multiple, as long as the opponent's betting range is not massively value-heavy.

---

### 2.4 [0,1] toy games (Chen & Ankenman)

Basic setup (heavily simplified, but mathematically usable):

- Player 1 draws \(x \sim U[0,1]\) (hand strength).  
- Player 2 draws \(y \sim U[0,1]\), independently.  
- both know their own \(x,y\), not the opponent's, but they know the distributions.  
- Moves: bet/check, call/fold, possibly varying bet sizes.  

Nash strategies have the form:

- There are **thresholds** \(t_B, t_C\):  
  - If \(x > t_B\) → player 1 bets for value.  
  - If \(x < t_L\) → player 1 can bluff with the optimal frequency (mixing).  
  - Player 2 calls with \(y > t_C\) and folds otherwise.  

Indifference conditions yield equations for \(t_B, t_C\) and the bluff frequency:

Example (simple case, one bet size):

1. Condition: player 2 is indifferent between call/fold with the marginal hand \(y = t_C\).  
2. Condition: player 1 is indifferent between bet/check with the marginal hand \(x = t_B\).

These equations can be **mapped onto our NLHE situations** by:

- interpreting \(x\) as a quantile of one's own hand-strength distribution (e.g. EQ vs range),  
- \(y\) as a quantile of the opponent's hand strength,  
- and the bet size \(s\) as \(B/P\).

The toy game then yields:

- the value threshold (from which equity vs range one should value-bet),  
- the bluff window (below which equity one may mix in bluffs),  
- optimal mixing frequencies (e.g. the bluff share in the betting range as a function of \(s\)).

**Implementable heuristic:**

For each street:

1. Approximate your equity distribution \(F_H(e)\) against the estimated opponent range.  
2. Choose a bet size \(s\).  
3. Derive from the toy-game equations:
   - the equity boundary \(e_V\) (value),  
   - the equity boundary \(e_L\) (lower bluff boundary),  
   - the bluff frequency in \([0,e_L]\) or the relative bluff/value ratio.  
4. Mix according to these thresholds in order to be "balanced by construction".

This gives you an **analytical near-GTO baseline**, without a complete solver, that you can feed into the network as a prior.

---

## 3) Regime switch: when is exploit > GTO?

We need a quantitative condition:

> Exploiting only pays if the EV gain against the opponent's leak exceeds the additional EV loss from one's own exploitability.

### 3.1 Notation

- \(\sigma^{\text{GTO}}\): your near-GTO baseline (exploitability \(\epsilon\)).  
- \(\sigma^{\text{EXP}}\): an exploitative policy tuned to the population/opponent.  
- \(u(\sigma_H,\sigma_V)\): EV (bb/hand) of hero vs villain.

Define:

1. **GTO-versus-opponent EV**:
   \[
   v_{\text{GTO}} := u(\sigma^{\text{GTO}}, \sigma_V)
   \]

2. **Exploit EV against the current estimate of the opponent's strategy \(\hat{\sigma}_V\)**:
   \[
   v_{\text{EXP}} := u(\sigma^{\text{EXP}}, \hat{\sigma}_V)
   \]

3. **Own exploitability of the exploit policy** (upper bound):
   \[
   \epsilon_{\text{EXP}} := \max_{\tau} u(\tau, \sigma^{\text{EXP}}) - u(\sigma^{\text{GTO}}, \sigma^{\text{GTO}})
   \]
   In practice: \(\epsilon_{\text{EXP}}\) is hard to compute exactly, but you can:
   - use the GTO bot as the opponent: \(\Delta u = u(\sigma^{\text{GTO}},\sigma^{\text{EXP}}) - u(\sigma^{\text{GTO}},\sigma^{\text{GTO}}) \approx -\epsilon_{\text{EXP}}\) (lower bound),  
   - plus a safety margin.

### 3.2 Safe-exploit criterion

We only want to exploit if the **safe added value** is positive.  
The added value is

\[
\Delta v := v_{\text{EXP}} - v_{\text{GTO}}
\]

But both terms are estimated, plus variance. In addition, the actual \(\sigma_V\) can deviate from \(\hat{\sigma}_V\).

Safety-bound approach:

- Let \(\widehat{\Delta v}\) be the empirical EV difference (or best estimate) from your opponent model:  
  \[
  \widehat{\Delta v} \approx u(\sigma^{\text{EXP}}, \hat{\sigma}_V) - u(\sigma^{\text{GTO}}, \hat{\sigma}_V)
  \]
- Let \(\epsilon\) be the exploitability of your GTO baseline (small).  
- Let \(\tilde{\epsilon}\) be an upper bound on the **additional** exploitability created by the exploit policy:
  \[
  \tilde{\epsilon} \approx \epsilon_{\text{EXP}} - \epsilon
  \]

Safe-exploit condition:

\[
\widehat{\Delta v} > k \cdot \tilde{\epsilon}
\]

with a safety factor \(k\). Your idea "~2·epsilon" corresponds to \(k = 2\).  

Intuition:

- Worst case: villain adapts optimally, so that you lose \(\tilde{\epsilon}\) more than you gain from the leak observed so far.  
- With factor 2 you require that the observed exploit advantage is at least twice as large as the additional worst-case leak, i.e. even under strong adaptation the net EV stays > 0.

Concrete decision rule in bb/100:

\[
\widehat{\Delta v} \ (\text{bb/100}) > 2 \cdot \tilde{\epsilon} \ (\text{bb/100})
\]

---

### 3.3 Live estimation of \(\widehat{\Delta v}\) and \(\tilde{\epsilon}\)

#### 3.3.1 Estimating the opponent-leak EV

For each opponent i you keep a model \(\hat{\sigma}_i\) (parameters: fold-to-cbet, 3bet frequency, river overfold, etc.).  
For a specific deviation (e.g. overfolding on the river):

1. You model two policies:

   - \(\sigma^{\text{GTO}}\)  
   - \(\sigma^{\text{EXP}}\) (e.g. more bluffs in spots where villain overfolds)

2. You simulate (or approximate analytically) the EV difference against \(\hat{\sigma}_i\):

   \[
   \widehat{\Delta v}_i = u(\sigma^{\text{EXP}}, \hat{\sigma}_i) - u(\sigma^{\text{GTO}}, \hat{\sigma}_i)
   \]

3. Statistical safety: with a finite sample of N hands your \(\widehat{\Delta v}_i\) is noisy.  
   - Estimate the standard error \(\text{SE}(\widehat{\Delta v}_i) \approx \frac{\hat{\sigma}_\text{outcome}}{\sqrt{N}}\).  
   - Take a confidence interval, e.g. the 95% lower bound:
     \[
     \widehat{\Delta v}_i^{\text{LB}} = \widehat{\Delta v}_i - 1.96 \cdot \text{SE}(\widehat{\Delta v}_i)
     \]
   - Plug the **lower bound** into the safe-exploit condition:
     \[
     \widehat{\Delta v}_i^{\text{LB}} > 2 \cdot \tilde{\epsilon}
     \]

This way you only exploit once the observed advantage is statistically significant and large enough.

#### 3.3.2 Estimating the additional exploitability \(\tilde{\epsilon}\)

Offline precompute:

1. Let the GTO bot play vs. the GTO bot → base rate (0 or minimal).  
2. Let the exploit bot play vs. the GTO bot:
   - observed EV: \(u(\sigma^{\text{EXP}},\sigma^{\text{GTO}})\)  
   - then
     \[
     \tilde{\epsilon} \approx u(\sigma^{\text{GTO}},\sigma^{\text{GTO}}) - u(\sigma^{\text{EXP}},\sigma^{\text{GTO}})
     \]
     (typically negative for EXP).  

Depending on the exploit rule, this gives you a fixed, conservative value \(\tilde{\epsilon}\) in bb/100.

If you have several exploit modules (e.g. river overbluff, turn overfold), you can precompute a separate \(\tilde{\epsilon}_k\) for each module and in the live system activate only those individual modules that satisfy their respective safe-exploit condition.

---

### 3.4 Concrete regime-switch algorithm

For each opponent i:

1. Initially: play \(\sigma^{\text{GTO}}\).  
2. For each exploit module k (e.g. "villain folds too much to 3-bets"):
   - Online estimate of the leak (parameter \(\theta_{i,k}\)), e.g. the empirical fold frequency.  
   - From \(\theta_{i,k}\) + an analytical model/simulation: the expected exploit gain \(\widehat{\Delta v}_{i,k}\).  
   - Estimate the variance/SE → lower bound \(\widehat{\Delta v}_{i,k}^{\text{LB}}\).  
   - Known \(\tilde{\epsilon}_k\) from the offline benchmark against GTO.
   - If
     \[
     \widehat{\Delta v}_{i,k}^{\text{LB}} > 2 \cdot \tilde{\epsilon}_k
     \]
     → module k **active** (deviate from GTO in the corresponding subspace

## Theory (Claude)

# HYBRID ARCHITECTURE: GTO default with exploit override

Let me start brutally honestly: your -207 bb/100 against Slumbot is not a "tuning problem", but an **architecture error**. Your exploiter has no safe default strategy — it "exploits" even when there is nothing to exploit, and VPIP 0.75 is pure suicide against balanced play. The solution is not "exploit less", but **a real GTO basis from which one deviates in a controlled way**.

---

## 1) THE ARCHITECTURE

```
                    ┌─────────────────────────────────┐
   Game state ─────▶│   FEATURE / OBSERVATION LAYER    │
   (Hand, Board,    │   (Hand-Buckets, Pot-Odds, SPR,  │
    actions,        │    Position, action history)     │
    Stats)          └──────────────┬──────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
   ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
   │  GTO-BASELINE    │  │ REGIME DETECTOR  │  │  EXPLOIT-LAYER   │
   │  σ_GTO           │  │  (Bayesian)      │  │  Δ-Adjustments   │
   │  Deep CFR +      │  │  yields:         │  │  per opp. leak   │
   │  book ranges     │  │  λ ∈ [0,1]       │  │                  │
   └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘
            │                     │                     │
            └─────────────────────┼─────────────────────┘
                                  ▼
              σ_final = (1-λ)·σ_GTO  ⊕  λ·σ_exploit
              with HARD CAP: λ ≤ λ_max(confidence, exploitability)
                                  │
                                  ▼
                          ACTION + sizing
```

### Core principle: **GTO is the anchor, exploitation is the deviation**

`σ_final = blend(σ_GTO, σ_exploit, λ)` — where `λ` is the **exploit share**, controlled by the regime detector. At `λ=0` you play pure GTO (unexploitable). That fixes Slumbot immediately.

**Important:** do NOT blend naively and linearly on probabilities without control — you need an **exploitability budget**:

```python
def safe_blend(sigma_gto, sigma_exploit, lam, max_exploitability):
    # Naive blend
    sigma = (1 - lam) * sigma_gto + lam * sigma_exploit
    # How far does this deviate from GTO? (in worst-case EV loss)
    deviation = estimate_exploitability(sigma, sigma_gto)
    if deviation > max_exploitability:
        # Scale lam back until within budget
        lam = solve_lam_for_budget(sigma_gto, sigma_exploit, max_exploitability)
        sigma = (1 - lam) * sigma_gto + lam * sigma_exploit
    return sigma
```

That is the decisive point: **you limit how exploitable you yourself become.** Against Slumbot the budget stays at ~0 and you play GTO.

---

### REGIME DETECTOR — the most important new component

The detector must answer ONE question: *"How sure am I that this opponent is exploitable, and how strongly?"* → output: `λ` per decision node.

#### Signals (live, collected per opponent):

| Signal | What it measures | GTO indicator | Exploit indicator |
|---|---|---|---|
| **Fold-to-CBet** | folds vs expected GTO frequency | ≈ MDF | >> MDF (overfolds) or << (sticky) |
| **Fold-to-3Bet** | 3bet defense | balanced | overfolds → 3bet bluff |
| **VPIP/PFR gap** | preflop looseness | tight gap | large gap = passive/loose |
| **WTSD / W$SD** | showdown tendency | ~GTO range | calling station / nit |
| **Bet-sizing tells** | size↔strength correlation | decorrelated | correlated (readable) |
| **Aggression frequency** | AFq per street | balanced | extreme → exploitable |
| **Limp/open-limp** | classic fish signal | never | yes → weak |

#### Thresholds & statistical significance (Bill Chen provides the lever here!)

You must **not** exploit after 10 hands — that is exactly what kills your exploiter. Use the **Bernoulli variance + z-score** from Chen directly:

```python
def is_leak_significant(observed_freq, gto_freq, n_samples, z_threshold=2.0):
    # Bernoulli variance (Chen): sigma = sqrt(p(1-p)/n)
    p = gto_freq
    se = (p * (1 - p) / n_samples) ** 0.5
    if se == 0: return False, 0.0
    z = (observed_freq - gto_freq) / se
    return abs(z) > z_threshold, z
```

**Rule:** a leak only becomes an exploit when `|z| > 2.0` (≈95% confidence). Before that: `λ = 0`, pure GTO. This is the direct application of your Chen excerpts ("Significance of extreme deviations in binary outcomes").

#### λ computation (Bayesian, per leak):

```python
def compute_lambda(leaks):
    # Each leak: (z_score, ev_gain_if_exploited)
    confidence = 0.0
    for leak in leaks:
        sig, z = is_leak_significant(leak.obs, leak.gto, leak.n)
        if sig:
            # Confidence grows with z and sample size, saturates
            conf = 1 - exp(-(abs(z) - 2.0))  # 0 at z=2, →1 for large z
            confidence = max(confidence, conf * leak.ev_weight)
    lam = clamp(confidence, 0.0, LAMBDA_MAX)  # LAMBDA_MAX e.g. 0.7
    return lam
```

#### Switching logic (3 regimes):

```
λ = 0.0          → PURE GTO     (no read / opponent balanced / n < min_samples)
0 < λ < 0.7      → MIXED        (leak detected, cautious deviation)
λ → LAMBDA_MAX   → FULL EXPLOIT (large significant leak, large sample)
```

**Anti-Slumbot switch:** if the detector recognizes that the opponent *himself* plays close to GTO (all frequencies within z<2 of GTO **AND** our exploit attempts so far are losing EV) → `λ = 0` *forced*, plus an **exploitability self-check**: it measures whether WE are currently becoming exploitable, and pulls back.

---

## 2) HOW BOOK KNOWLEDGE INFORMS THE GTO BASELINE

Deep CFR on NLHE needs months of compute and never converges perfectly. **The books are your warm start, your sanity checks and your fallback wherever the network is still poor.**

### Modern Poker Theory (Acevedo) — concrete levers:

- **Preflop ranges as prior/anchor:** Acevedo's GTO open/3bet/call ranges (position-dependent) → directly as the **initialization** of the Deep CFR preflop strategy and as a **hard fallback** for preflop wherever the network is unstable. Preflop is small enough that it can almost be tabulated.
- **MDF (minimum defense frequency)** = `1 - bet/(pot+bet)` → provides the **GTO reference value** for your regime detector (fold-to-cbet signal). Without MDF you don't know what "overfolding" even means.
- **Sizing buckets:** Acevedo's standard sizes (33/50/75/100/overbet) → the **action abstraction set** for Deep CFR. Prevents an explosion of the action space.

### Bill Chen & Ankenman — the structural theory:

- **Indifference principle:** the optimal bluff frequency makes the opponent indifferent. → `Bluffs : Value = bet : (pot+bet)` on the river. That is your **GTO frequency check**: if Deep CFR spits out river bluffs outside this ratio → bug or non-convergence.
- **Optimal bluff-to-value ratio** and **α (optimal bluff-catching frequency)** → formulas that can be wired directly for river spots where Deep CFR is expensive/inaccurate.
- **[0,1] toy games:** provide the *structure* (polarized ranges bet big, bluff catchers call with frequency α) → as a **regularization/sanity layer** over the network.
- **Variance/CLT** → your entire regime-detector significance framework (see above).

**Concretely:** 

```python
sigma_gto = neural_deep_cfr(state)
sigma_gto = enforce_chen_constraints(sigma_gto, state)  # bluff:value ratio, MDF
sigma_gto = blend_with_book_prior(sigma_gto, acevedo_range(state), 
                                   weight=netz_unsicherheit(state))
```

Where the network is uncertain/unconverged (high nash_conv locally), you pull more strongly toward the book.

---

## 3) WHY THIS FIXES THE SLUMBOT DEFEAT

The -207 bb/100 had **three** causes, all fixed:

1. **VPIP 0.75 (too loose):** your baseline was an exploiter without a GTO anchor. → **The new baseline is Deep CFR + Acevedo ranges**, VPIP drops to
