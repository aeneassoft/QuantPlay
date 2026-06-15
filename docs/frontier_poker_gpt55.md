# GTO frontier — poker/GTO (gpt-5.5)

## Brutal headline

Your bot’s real differentiated asset is **not “more GTO”** than Slumbot/Pluribus/solvers. It is:

1. a **solver-informed default policy**,  
2. an **online exploit layer**,  
3. a **measurement culture that reverts refuted heuristics**,  
4. and, potentially, a **safe fallback mechanism**.

That is good. But do not fool yourself: a history-free postflop floor with frequency imitation, heuristic sizing, MDF-ish defense, and uncalibrated river logic is **not close to a full-game GTO policy**. It can beat weak bots because weak bots leak massively. Against near-GTO, your ceiling is approximately break-even unless your opponent model finds a real static bias.

Your biggest current bottleneck is not another heuristic. It is that your **adversarial evaluation is too weak**, and your postflop floor is not sufficiently **range/line/state-conditioned**.

---

# Ranked by edge gained / effort

| Rank | Move | Edge potential | Effort | Why it matters |
|---:|---|---:|---:|---|
| 1 | Build a **correct non-vacuous LBR / approximate best-response evaluator** plus AIVAT/duplicate eval | Very high | Medium-high | Your current LBR losing to you proves almost nothing. You need an adversary that actually finds leaks. |
| 2 | Replace history-free postflop floor with **range + line + SPR + position conditioned policy/EV model** | Very high | High | Board texture alone is not GTO. Solver strategy is conditional on ranges and prior actions. |
| 3 | River calibration: exact combo enumeration + river solve cache + blocker EV, not heuristic nudges | High | Medium | River mistakes are expensive and easier to solve exactly than earlier streets. |
| 4 | Replace “fold-equity-optimal sizing” with **EV-optimal sizing over discrete candidate sizes** | High | Medium | FE-optimal sizing is often strategically wrong. Sizing is a huge EV lever. |
| 5 | Train on **EV gaps/regrets**, not only solver P(bet) | High | Medium | Action-match/MSE can optimize the wrong objective. |
| 6 | Make exploit layer **Bayesian + δ-safe** rather than rule nudges | Medium-high | Medium | Exploit safely only when opponent deviation is statistically real and EV-positive after uncertainty. |
| 7 | Exact equity/range enumeration where feasible | Medium | Low-medium | MC equity noise can flip close decisions; exact HU enumeration is usually cheap enough. |
| 8 | 6-max joint range/multiway model | Very high for 6-max | Very high | Your current independent-seat 6-max logic is structurally far behind Pluribus-like reasoning. |

---

# 1. What does your bot understand / do about GTO that others do not?

## Short answer

Your bot does **not** understand “GTO” better than Slumbot, Pluribus, or commercial solvers in the pure equilibrium-computation sense.

What it does better, potentially, is:

- combine a **low-ish exploitability floor** with **online opponent-specific exploitation**;
- use solver EV/frequency gates instead of noisy bb/100;
- revert heuristics when measurement refutes them;
- model specific opponents like Slumbot with learned fold curves;
- fall back to a GTO-ish policy when exploit confidence is low.

That is a valid architecture. But it is not “truer GTO.” It is **solver-guided robust exploitation**.

---

## Slumbot: structural blind spots

Slumbot is approximately a heads-up no-limit equilibrium agent built from massive self-play/CFR-style computation with abstraction. It is strong, but not perfect.

Likely residual gaps:

### 1. Card abstraction error

If Slumbot buckets strategically distinct hands together, it can:

- over-bluff or under-bluff certain blocker classes;
- misplay suit-specific runouts;
- misestimate thin value thresholds;
- mishandle rare nut-changing turns/rivers.

Your conversion to EV:

- use exact blockers/card removal;
- learn which textures/lines Slumbot overfolds or overcalls;
- attack abstraction cliffs: paired boards, monotone boards, 4-straight/4-flush rivers, low-frequency overbet nodes, etc.

But be honest: if your river is only “blocker-aware heuristic selection,” you are not yet positioned to reliably exploit Slumbot’s blocker mistakes. You need calibrated river EV.

---

### 2. Static blueprint / no live adaptation

If Slumbot is a fixed policy, repeated exploitation does not cause it to counter-adjust.

Your conversion to EV:

- fit fold/call/raise curves by line, sizing, texture;
- widen value/bluff/foldcatch only after credible sample size;
- use opponent-specific action likelihoods for Bayesian range updates.

This is your actual edge path versus Slumbot.

But your measured result, exploit +2.2 bb/100 over 500h, is not statistically conclusive. If that is around 50k hands and HU SD is ~90–120 bb/100, your standard error is roughly:

\[
SE \approx \frac{100}{\sqrt{500}} \approx 4.5 \text{ bb/100}
\]

So +2.2 bb/100 is basically noise.

---

### 3. Action abstraction / size translation

If Slumbot was trained on limited sizes or translates off-tree bets imperfectly, nonstandard sizes may produce suboptimal defense.

Your conversion to EV:

- use a learned fold curve over size;
- test candidate sizes via AIVAT/duplicate matches;
- prefer sizes where villain response deviates most from solver defense.

But warning: your current “fold-equity-optimal sizing” can self-own. The best size is not the one maximizing folds. It is the one maximizing total EV across value, bluffs, protection, equity realization, and future streets.

---

## Pluribus: structural blind spots

Pluribus is stronger conceptually than a static lookup bot. It uses a blueprint plus depth-limited search. It is not “true GTO,” especially in 6-max, but you should not underestimate it.

Residual gaps:

### 1. Static/non-opponent-specific core

Pluribus does not primarily play a maximally exploitative response to each opponent. It plays a robust approximate equilibrium-like strategy.

Your conversion to EV:

- versus weak/biased players, exploit faster than Pluribus would;
- deviate by opponent: overfolding nit, sticky station, underbluffing passive, over-aggressive spewer;
- use confidence-gated fallback when stats are weak.

This is real.

But versus Pluribus itself or similarly strong agents, your online exploit layer probably finds little unless you discover systematic bet-size/frequency biases.

---

### 2. Depth-limited search and value-function approximation

Pluribus search is not full-game exact solving. Continuation values are approximate. Search can miss long-horizon effects.

Your conversion to EV:

- pressure nodes with high future-street leverage: turn overbets, river polar spots, multiway squeezes;
- exploit if its continuation values under/overestimate certain branches.

But this requires very strong state-specific evaluation. Your current history-free postflop advisor is not enough.

---

### 3. Multiplayer equilibrium weakness

In 6-max, “GTO” is less clean than HU zero-sum. Nash equilibrium exists in finite games, but:

- there is no single minimax value like HU;
- exploitability is not as clean;
- equilibrium may be non-unique;
- collusion/implicit collusion/seat interactions complicate protection;
- exploiting one player can expose you to others.

Your current 6-max architecture — each seat deciding independently from own cards with per-position ranges — is a **major structural deficit** versus Pluribus-style reasoning.

You may crush weak 6-max bots anyway, but do not claim Pluribus-level multiplayer GTO until you model joint ranges, multiway incentives, and seat-coupled actions.

---

## Raw solvers: structural blind spots

Commercial solvers are not deployed full-game bots. They solve specified models.

Blind spots:

### 1. Single-spot myopia

A solver output is only as good as:

- input ranges;
- stack/pot;
- allowed sizes;
- rake assumptions;
- line abstraction;
- future tree.

Your bot can exploit humans/bots who blindly apply wrong solver outputs to the wrong population node.

---

### 2. No online population adaptation

A raw solver says: “equilibrium against equilibrium.”

It does not say: “villain overfolds turn barrels by 18 percentage points in single-raised pots after check-call flop.”

Your exploit layer can convert population deviations into EV.

---

### 3. Fixed sizing tree

Solver equilibrium inside a tree is not necessarily equilibrium in the full game. If a solver uses 33/75/150 only, it may miss the true EV of 20, 50, 110, jam, etc.

Your bot can exploit opponents trained on rigid solver trees by using off-tree sizes if they defend incorrectly.

But again: your sizing logic must be EV-optimal, not fold-equity-optimal.

---

# 2. Where does true 100% GTO lie, and how do we estimate the gap?

## What “100% GTO” means in HU NLHE

For HU NLHE with fixed blinds, stacks, legal chip increments, and no rake, the true GTO strategy is the exact Nash equilibrium of the full extensive-form zero-sum game.

It includes:

- all private card combinations;
- all public boards;
- all legal bet sizes;
- full history dependence;
- exact card removal;
- exact stack/pot geometry;
- exact mixed strategies at every information set.

No public deployed bot has this exactly.

Commercial solvers solve **subgames or abstractions**, not the full game. Slumbot/Pluribus solve/play approximations.

---

## Practical gap estimators

You need three separate measurements.

---

## A. AIVAT / duplicate-hand evaluation for winrate comparisons

Use for bot-vs-bot comparisons, especially A/B testing.

AIVAT/control-variate methods reduce variance by using known strategy probabilities and value estimates. Duplicate matches also reduce variance by making both agents play both sides of identical deals.

Important:

- AIVAT estimates realized performance difference more efficiently.
- It does **not** directly prove low exploitability.
- It needs accurate value functions/action probabilities to be maximally useful.

Typical HU NLHE SD is roughly 80–120 bb/100. To resolve small edges:

\[
SE = \frac{\sigma}{\sqrt{N/100}}
\]

If \(\sigma = 100\) bb/100:

- 50k hands: SE ≈ 4.5 bb/100.
- 1M hands: SE ≈ 1.0 bb/100.
- 4M hands: SE ≈ 0.5 bb/100.

So your +2.2 bb/100 over ~500h is not proof.

---

## B. Correctly implemented LBR / approximate best response

Your current LBR losing to your bot is vacuous.

A valid LBR lower bound works like this:

\[
\text{Exploitability lower bound} \geq \max(0, WR(\text{LBR vs bot}))
\]

If LBR loses, the lower bound is zero. It does not mean your bot is safe.

A useful LBR must:

1. Freeze your bot policy.
2. Estimate your bot’s hidden-card range via Bayes after every action.
3. Include your bot’s actual action probabilities, not just observed frequencies.
4. Search/solve river exactly.
5. Search turn+river at least locally.
6. Include realistic off-tree bet sizes.
7. Use exact card removal.
8. Avoid training/evaluating on the same tiny line samples.
9. Report exploit by bucket: preflop, flop c-bet, turn probe, river bluffcatch, overbet defense, etc.

You need multiple adversaries:

- river exact BR;
- turn-river subgame BR;
- bet-size abuse BR;
- fold-curve exploit BR;
- neural BR trained against frozen bot;
- population-rule BR.

If none beat you, that is evidence, not proof. If one beats you, that is a leak.

---

## C. Solver tree-value gap / reach-weighted regret

For every state you can map to a high-fidelity solver tree:

\[
\Delta EV(s,h) = EV_{\text{solver}}(a^*|s,h) - EV_{\text{solver}}(a_{\text{bot}}|s,h)
\]

Aggregate by reach probability:

\[
\text{Floor regret} =
\mathbb{E}_{s,h \sim \text{bot reach}}
[
\Delta EV(s,h)
]
\]

This is more useful than action-match.

Action-match can be misleading:

- Solver mixes 50/50, bot picks one pure action: action mismatch may have near-zero EV loss.
- Solver pure bets high EV, bot checks: one mismatch may cost huge.
- Frequencies can match while hand selection is terrible.

You should gate changes on **EV gap**, not merely frequency match or MSE.

---

## Rough magnitude expectations for HU NLHE

Use bb/100 for clarity. Conversion:

\[
1 \text{ bb/100} = 0.01 \text{ bb/hand} = 10 \text{ mbb/hand}
\]

Rough expectations:

| System/component | Expected residual gap/exploitability |
|---|---:|
| Highly converged solver inside fixed postflop tree | <0.1–1 bb/100 numerical, but only inside model |
| Fixed-tree abstraction error from missing sizes/range assumptions | 1–10+ bb/100 depending spot |
| Strong HU blueprint agent like Slumbot-class | likely low single-digit to maybe low double-digit bb/100 exploitable by a strong tailored BR; exact public bound unknown |
| Your current history-free floor | I would budget several to 10+ bb/100 exploitability until proven otherwise |
| Weak/exploitable bots | 100–700+ bb/100 leaks are plausible, matching your results |

The important brutal point: your bot can break even versus Slumbot while still being quite exploitable by a stronger tailored BR. Slumbot is not a best-response oracle.

---

# 3. How do you credibly pull ahead?

## The single biggest high-leverage move

If forced to pick one:

> Build a serious adversarial evaluation/leak-finding pipeline, then use it to prune/fix the highest reach-weighted EV leaks.

Your current LBR is too weak. That means you are partially blind. Without a non-vacuous best-response evaluator, you cannot know whether your new exploit rules reduce EV, increase exploitability, or just run hot.

The pipeline should produce this report every build:

| Leak bucket | Reach | EV loss/action | bb/100 cost | Confidence |
|---|---:|---:|---:|---:|
| BTN SRP flop c-bet OOP paired boards | 8.2% | 0.018 bb | 0.15 | High |
| Turn barrel after B-B-X line | 3.1% | 0.09 bb | 0.28 | Medium |
| River bluffcatch vs 75% pot on 4-flush | 1.4% | 0.22 bb | 0.31 | High |
| Off-tree 125% overbet defense | 0.8% | 0.45 bb | 0.36 | Medium |

Then fix the top buckets.

Do not optimize based on aggregate Slumbot bb/100 until you have huge samples. Use solver EV gap, LBR exploit, AIVAT-reduced duplicate matches.

---

## The biggest direct strategic leak to fix

Your largest direct floor weakness is likely:

> The postflop floor is insufficiently public-state/range/history-conditioned.

“Per-texture donk/c-bet frequency” and “advisor predicts solver P(bet) per hand” are not enough.

Solver strategy depends on:

- preflop ranges;
- position;
- stack depth;
- pot size;
- bet sizes used earlier;
- line history;
- range asymmetry;
- nut advantage;
- blocker distribution;
- equity realization;
- future street geometry.

A flop c-bet on `K72r` is not one object. It differs by:

- BTN open vs BB call;
- SB 3-bet pot;
- 4-bet pot;
- limped pot;
- previous action;
- stack depth;
- rake;
- chosen size menu.

If your MLP is mostly board/hand-feature conditioned, it is averaging across strategically different states. That creates an exploitable policy.

---

## What “pulling ahead” realistically means

Against near-GTO:

- You should expect approximately break-even.
- A sustained +2 to +5 bb/100 against Slumbot-like agents would be impressive but needs massive evidence.
- If you observe +10+ bb/100 against a near-GTO bot over small samples, assume variance or a bug until proven otherwise.

Against the real field:

- Most EV comes from exploitation.
- Weak bots leak 100–700 bb/100; your measured crush rates are believable.
- The main risk is that exploit rules trained on weak opponents corrupt the fallback floor and become exploitable versus strong ones.

So your credible path is:

1. Lower floor exploitability.
2. Build a strong leak finder.
3. Make exploit deviations Bayesian and δ-safe.
4. Use opponent-specific exploitation only when the posterior edge exceeds risk.

---

# 4. The math: where you are approximating in EV-costing ways

## 4.1 Equity: MC variance vs exact enumeration

### What can go wrong

Monte Carlo equity creates noisy thresholds.

For equity estimate \(\hat p\) with \(n\) samples:

\[
SE(\hat p) = \sqrt{\frac{p(1-p)}{n}}
\]

Worst case \(p=0.5\):

\[
SE \approx \frac{0.5}{\sqrt n}
\]

So:

| Samples | Equity SE |
|---:|---:|
| 1,000 | 1.58 pp |
| 10,000 | 0.50 pp |
| 100,000 | 0.16 pp |

A 1 percentage-point equity error can flip close calls, thin value bets, or bluffcatchers.

For a call facing bet \(B\) into pot \(P\), required equity is:

\[
q = \frac{B}{P+2B}
\]

If pot is 100 and villain bets 75:

\[
q = \frac{75}{100+150} = 30\%
\]

If MC says 30.7% but true equity is 29.8%, you make a losing call.

### Bigger issue

Equity is not EV. On flop/turn, showdown equity ignores:

- fold equity;
- future barreling;
- reverse implied odds;
- equity realization;
- range interaction;
- positional advantage.

### Rigorous fix

For HU:

- exact river enumeration always;
- exact turn enumeration over 46 rivers;
- exact flop enumeration over \(\binom{47}{2}=1081\) turn-river runouts;
- exact combo-weighted range equities with card removal;
- use bitset evaluators/cached hand ranks;
- use MC only when exact is impossible or when CI width is below EV margin.

Decision rule:

\[
\text{Use MC only if } CI(EV_a - EV_b) \text{ does not cross zero.}
\]

Otherwise enumerate or fall back to solver/value model.

---

## 4.2 Range and board abstraction error

### What you get subtly wrong

Holding out by board is not enough.

A model can generalize across boards but fail across:

- line histories;
- stack depths;
- bet sizes;
- positions;
- preflop ranges;
- prior street filters;
- villain action tendencies.

Solver P(bet) is conditional on the full public state:

\[
\sigma(a|I) = f(\text{ranges}, \text{board}, \text{pot}, \text{stacks}, \text{line}, \text{position}, \text{size tree})
\]

If your advisor approximates:

\[
\sigma(a|h,b) \approx f(\text{hand features}, \text{board features})
\]

you average over incompatible information sets.

That creates strategy-averaging error.

Example:

Same board, `Q♠8♦3♣`.

- BTN open vs BB call: BTN may range-bet small at high frequency.
- SB 3-bet pot: OOP may have overpair/nut advantage and use different sizing.
- Check-raise line turn: ranges are filtered; medium hands shift drastically.

A board-only frequency can be directionally wrong.

### Rigorous fix

Track explicit ranges:

\[
R_t^{P1}(h), R_t^{P2}(h)
\]

Update by Bayes after every action:

\[
R_{t+1}^i(h)
\propto
R_t^i(h) \cdot \sigma_i(a_t|h,s_t)
\]

with exact card removal and normalization.

Then condition the policy/value model on:

- both ranges or compressed range features;
- public board;
- pot;
- stack;
- SPR;
- position;
- line;
- legal size set;
- prior actions.

Better target:

- action EVs;
- regrets;
- range-level frequencies;
- not only P(bet).

---

## 4.3 MDF / indifference: when it is the wrong model

### Correct MDF formula

If villain bets \(B\) into pot \(P\), the breakeven bluff condition for villain is:

\[
F = \frac{B}{P+B}
\]

So defender’s minimum defense frequency is:

\[
MDF = 1 - F = \frac{P}{P+B}
\]

Example:

- Pot 100.
- Bet 75.

\[
MDF = \frac{100}{175} = 57.1\%
\]

### Where MDF applies

MDF is useful in a simplified river toy game:

- polarized bettor;
- bluff has zero showdown value;
- defender cannot raise;
- no future streets;
- no blocker asymmetry;
- no range asymmetry beyond value/bluff composition;
- bettor uses fixed size.

### Where MDF is wrong

MDF is not a general calling rule.

On flop/turn:

- future equity realization matters;
- raises matter;
- blockers matter;
- villain may underbluff;
- villain may overbluff;
- some hands have redraws;
- protection/value denial matter;
- multi-size strategies alter defense obligations.

Versus an underbluffing opponent, defending MDF can torch EV.

If villain’s bluff frequency is below pot-odds threshold, overfolding is correct.

For a river bluffcatcher with equity \(E\) versus villain betting range:

\[
\text{Call if } E > \frac{B}{P+2B}
\]

This is pot odds, not MDF.

### Rigorous fix

Use MDF only as a range-level sanity check.

Decision should be:

\[
EV(call) = E \cdot (P+B) - (1-E)B
\]

Call if:

\[
EV(call) > EV(fold)=0
\]

For exploit adjustment, estimate villain bluff rate with uncertainty:

\[
\theta \sim \text{Beta}(\alpha,\beta)
\]

Then use conservative lower/upper credible bounds.

For bluffcatching, call only if:

\[
LCB(EV(call)) > 0
\]

or if solver fallback says the hand is mandatory defense.

---

## 4.4 Blocker/card-removal exactness

### What you do right

River blocker-aware bluff selection is directionally correct.

Good bluff candidates often:

- block villain’s strongest calls/raises;
- unblock folds;
- have poor showdown value;
- sometimes block villain’s value region.

Good bluffcatchers often:

- block villain’s value;
- unblock villain bluffs.

### What you may get wrong

“Frequency-preserving bluff selection” can still be bad if blocker effects are not EV-calibrated.

Example:

A hand may block villain’s folds more than it blocks calls. It looks like a blocker hand but is actually a bad bluff.

Or a bluffcatcher may block missed draws, making it a worse call despite blocking some value.

### Rigorous formula

For candidate hand \(h\), exact river EV of action \(a\):

\[
EV(a,h)
=
\sum_{v \in R_V, v \cap h = \emptyset}
w(v)
\cdot
EV(a,h,v)
\]

where villain combo weights are updated by line and card removal.

For bluffing:

\[
EV(bluff,h)
=
F_h \cdot P
+
(1-F_h)
\cdot
[
E_h(P+B) - (1-E_h)B
]
\]

where \(F_h\) is villain fold probability conditional on your blockers.

But \(F_h\) must be computed combo-exact:

\[
F_h =
\frac{
\sum_{v \in folds, v \cap h = \emptyset} w(v)
}{
\sum_{v \in R_V, v \cap h = \emptyset} w(v)
}
\]

### Rigorous fix

Build river solver cache and train/evaluate:

- exact combo removal;
- exact fold/call/raise response;
- blocker EV delta;
- bluff/value thresholds by size;
- bluffcatch EV by hand class.

Your river is the most solvable street. There is no excuse for it to remain mostly heuristic.

---

## 4.5 Supervised net imitating solver caches

### What you are doing

You train an MLP to predict solver \(P(bet)\) per hand.

This is useful.

But it is not equivalent to learning GTO.

### Problem 1: action-match is not EV-match

If solver has:

- Action A EV = 1.20
- Action B EV = 1.19

choosing B costs almost nothing.

If solver has:

- Action A EV = 1.20
- Action B EV = 0.70

choosing B is disastrous.

A pure action-matching loss treats these similarly.

### Problem 2: mixed strategies are often non-unique

In equilibrium, actions may mix because they are nearly indifferent.

The exact frequency can be solver-noise-sensitive, tree-sensitive, or abstraction-sensitive.

Training too hard on exact frequencies may imitate irrelevant noise.

### Problem 3: averaging across states creates invalid strategies

If your model averages:

- 80% bet in range-advantage states;
- 20% bet in range-disadvantage states;

it may output 50% bet in both.

That is not GTO. It is a strategically incoherent averaged policy.

### Problem 4: off-tree generalization is uncontrolled

Held-out board MSE says the model interpolates boards.

It does not prove it handles:

- off-tree sizes;
- exploit-adjusted lines;
- rare SPRs;
- check-raise pots;
- unusual river runouts;
- opponent-specific deviations.

### Rigorous fix

Train on EV/regret targets:

\[
A(a|s,h) = EV(a|s,h) - \max_{a'}EV(a'|s,h)
\]

or positive regret:

\[
R^+(a|s,h)=\max(0, EV(a|s,h)-EV_{\text{strategy}}(s,h))
\]

Use loss weighted by:

- reach probability;
- pot size;
- EV gap;
- confidence in solve;
- strategic rarity bucket.

Output:

- all action probabilities;
- action EVs;
- uncertainty;
- range-level aggregate frequencies.

Gate by EV, not action confidence.

---

## 4.6 Confidence-gated blending

### What is not theoretically sound

A confidence-gated blend like:

> use MLP if confident, else frequency baseline

is not automatically game-theoretically safe.

Why?

Because local confidence does not imply global low exploitability.

You can create range-level incoherence:

- too many bluffs selected;
- too few value bets;
- overfolding one blocker class;
- underdefending versus overbets;
- inconsistent lines across streets.

A strategy is not safe because each local classifier is confident.

### When blending can be sound

If you have a baseline strategy \(\sigma_0\) with exploitability \(e_0\), and an exploit strategy \(\sigma_1\) with exploitability \(e_1\), then global mixture:

\[
\sigma_\lambda = (1-\lambda)\sigma_0 + \lambda\sigma_1
\]

has exploitability bounded by convexity:

\[
Expl(\sigma_\lambda)
\le
(1-\lambda)Expl(\sigma_0)+\lambda Expl(\sigma_1)
\]

But your per-node confidence gate is not necessarily a clean global mixture unless modeled as a consistent behavioral strategy and evaluated as such.

### Rigorous fix

Use safe exploitation.

One form:

\[
\max_{\sigma}
EV(\sigma \text{ vs } \hat v)
\]

subject to:

\[
Expl(\sigma) \leq Expl(\sigma_0) + \epsilon
\]

where \(\hat v\) is opponent model.

Approximate versions:

- Restricted Nash Response;
- Data-biased response;
- robust best response with KL constraint;
- lower-confidence-bound EV maximization;
- per-node deviation budgets.

Practical rule:

Only deviate from floor if:

\[
LCB(EV_{\text{exploit}} - EV_{\text{floor}}) > \tau
\]

and cumulative exploitability budget is not exceeded.

---

## 4.7 Sizing: “fold-equity-optimal” is a leak

This is one of the most dangerous simplifications.

For a bluff of size \(B\) into pot \(P\):

\[
EV(bluff)
=
F(B)P
+
(1-F(B))
[
E(P+B) - (1-E)B
]
\]

If pure zero-equity bluff:

\[
EV(bluff)=F(B)P-(1-F(B))B
\]

Maximizing \(F(B)\) is not the same as maximizing EV.

A huge bet may maximize folds but lose too much when called.

For value, the goal is not folds at all. It is:

\[
EV(value)
=
C(B)[E(P+B)-(1-E)B]
+
F(B)P
\]

where \(C(B)=1-F(B)\).

The optimal size depends on:

- hand equity;
- villain calling distribution;
- blocker effects;
- range composition;
- future street leverage;
- raise risk;
- nut advantage;
- minimum defense constraints.

### Rigorous fix

Use discrete candidate sizes:

\[
B \in \{25\%, 33\%, 50\%, 75\%, 125\%, jam\}
\]

Estimate:

\[
EV(B,h,s)
\]

from solver/value model or opponent fold curve with uncertainty.

Choose:

\[
B^* = \arg\max_B LCB(EV(B,h,s))
\]

For the floor, sizes should be solver-calibrated.

For exploit, sizes should be opponent-model-calibrated but uncertainty-penalized.

---

## 4.8 Preflop action-match weakness

Your preflop stack is reasonable:

- verified Nash push/fold short stacks is solid;
- deeper strength-model + PokerBench lookup is practical.

But 88.6% action match is not enough.

The missing 11.4% could be:

- low-EV indifferent noise; or
- high-EV blunders.

You need preflop EV-gap auditing.

For each preflop decision:

\[
\Delta EV = EV(a^*) - EV(a_{\text{bot}})
\]

weighted by frequency.

Also ensure ranges depend on:

- stack depth;
- rake;
- ante;
- open size;
- 3-bet size;
- position;
- table size;
- cold-call/squeeze dynamics;
- opponent tendencies.

In 6-max especially, independent per-seat decisions miss interaction effects.

---

# Specific diagnosis of your current architecture

## Strong parts

You have several real strengths:

1. **Short-stack Nash push/fold**: good, measurable, hard to exploit.
2. **Solver-cache supervised postflop floor**: better than pure heuristics.
3. **Held-out board validation**: better than training-only fit.
4. **Solver-gated changes**: correct philosophy.
5. **Reverting refuted heuristics**: rare and valuable.
6. **Opponent-specific exploit layer**: likely source of most real-world EV.
7. **Noise awareness**: you understand Slumbot bb/100 is noisy.

---

## Weak / self-fooling parts

### 1. “History-free GTO-grounded floor”

This is not truly GTO.

GTO is information-set conditional. A history-free board/hand predictor is an approximation that can average incompatible strategies.

Likely EV cost: high.

---

### 2. “P(bet) advisor”

P(bet) is insufficient.

You need:

- action EVs;
- size EVs;
- regrets;
- range constraints;
- uncertainty;
- reach weighting.

Likely EV cost: medium-high.

---

### 3. “River theory-grounded but not solver-calibrated”

River is where exact combo math matters most and future uncertainty is gone.

If river is not calibrated, you are likely bleeding in:

- bluff selection;
- bluffcatch thresholds;
- thin value;
- overbet defense;
- blocker-specific calls/folds.

Likely EV cost: high.

---

### 4. “MDF shaded by villain bluffiness”

MDF is a range-level constraint in idealized polar games. It is not a universal defense algorithm.

Likely EV cost: medium-high, especially versus underbluffers.

---

### 5. “Fold-equity-optimal sizing”

This is not game-theoretically correct.

Likely EV cost: high.

---

### 6. “6-max independent seats”

This is a fundamental limitation.

You can beat weak 6-max bots anyway, but this is not close to Pluribus-style multi-agent reasoning.

Likely EV cost: very high in serious 6-max environments.

---

# Concrete consolidation plan

## Phase 1: Evaluation first

Build:

1. exact river BR against your frozen bot;
2. turn+river LBR;
3. off-tree sizing attack BR;
4. AIVAT/duplicate-hand A/B harness;
5. reach-weighted solver EV-gap report.

Success criterion:

- LBR must beat old bot versions with known injected leaks.
- LBR must rediscover artificial river overfold/underbluff leaks.
- Reports must identify actionable leak buckets.

If your LBR cannot exploit deliberately broken bots, it is useless.

---

## Phase 2: River hardening

Do this before adding new exploit rules.

- Generate river solve cache by public-state class.
- Exact combo enumerate all river decisions.
- Train blocker EV/value model.
- Replace threshold nudges with calibrated call/fold/bet EVs.
- Audit river EV gap by bucket.

This is likely the cleanest EV gain per engineering hour.

---

## Phase 3: Range/line-conditioned floor

Upgrade postflop input from:

\[
(\text{board}, \text{hand features})
\]

to:

\[
(\text{board}, \text{hand}, R_{hero}, R_{villain}, \text{line}, \text{pot}, \text{SPR}, \text{position}, \text{sizes})
\]

Train on:

- action EVs;
- regrets;
- solver frequencies;
- range aggregate constraints.

This reduces averaging error.

---

## Phase 4: Safe exploit

Replace rule nudges with posterior EV:

\[
EV_{\text{exploit}} - EV_{\text{floor}}
\]

computed under villain model with credible intervals.

Deviate only if:

\[
LCB(\Delta EV) > \tau
\]

and deviation does not exceed exploitability budget.

---

# Final answer to the thesis

Your thesis is mostly correct:

- nobody deployed plays exact 100% full-game GTO;
- Slumbot, Pluribus, and solvers are approximations;
- static near-GTO bots leave residual gaps;
- online adaptation can convert those gaps into EV.

But the part to be careful about:

> “robust low-exploitability blueprint”

You do not yet have strong evidence that your blueprint is low-exploitability. Break-even versus Slumbot does not prove that. A weak LBR losing to you proves nothing. Action-match to solver does not prove that.

The credible path is not more complexity. It is:

1. build a stronger adversarial evaluator;
2. make the floor range/line/EV-conditioned;
3. calibrate river exactly;
4. replace FE sizing and MDF heuristics with EV-based decisions;
5. exploit only with statistical safety.

That is how this architecture can actually pull ahead: not by being “more GTO” than the GTO bots, but by being **less self-deluded, harder to exploit, and faster to exploit real opponent errors**.
