# The Mathematics of Poker — extracted models

## Implicit strategy models and EV maximization
Every decision (bet/call/fold) corresponds to an implicit probabilistic model of hand values and opponent behavior; optimal play is choosing actions that maximize expected value given that model.

**Formel:** EV(action) = sum_over_outcomes[ P(outcome | action, info) * payoff(outcome, action) ]

Select action* s.t. EV(action*) = max over feasible actions EV(action).

**Für den Bot:** For every node in the game tree, the bot should explicitly compute EVs from a distribution over opponent hands/actions, then choose the argmax; all later toy-game machinery just refines how to construct those distributions and payoffs.

## Probability as limiting frequency
Model outcomes of deals or actions as random experiments with well-defined long-run frequencies; use these probabilities as inputs to EV calculations.

**Formel:** For event x in repeated trials:
P(x) = lim_{n->∞} (n_x / n)
where n_x is the count of occurrences of x in n trials.

**Für den Bot:** Treat all unknown cards and opponent actions as random variables with explicit probabilities; your strategy and EV calculations must be driven by these probabilities, not heuristics.

## Combinatorial probability from equally likely outcomes
When all microstates (card permutations) are equally likely, probabilities are ratios of counts of favorable combinations to total combinations.

**Formel:** If all outcomes in Ω are equally likely and A ⊆ Ω:
P(A) = |A| / |Ω|

Example (pocket aces in holdem):
Total possible 2-card hands: C(52, 2)
Favorable hands (AA): 4 choose 2 = C(4, 2) = 6
P(AA) = C(4, 2) / C(52, 2) ≈ 1/221

**Für den Bot:** Build all hand and board distributions via combinatorics (choose functions) so that value, bluff, and calling ranges reflect exact combinatorial weights.

## Additivity for mutually exclusive events
If two events cannot happen simultaneously (disjoint), the probability of at least one occurring is the sum of their probabilities; used to aggregate hand combos into range probabilities.

**Formel:** If A and B are mutually exclusive (A ∩ B = ∅):
P(A ∪ B) = P(A) + P(B)

Example (any ace as a single card):
P(Ace) = P(A♠) + P(A♥) + P(A♦) + P(A♣) = 4 * (1/52) = 1/13

**Für den Bot:** Represent ranges as disjoint combination buckets (e.g., each specific combo) and obtain range-level frequencies by summing those combo probabilities.

## Expected value as objective function
Given well-defined probabilities and payoffs, the correct decision is the one that maximizes expected monetary value, assuming risk-neutral utility within the game.

**Formel:** For discrete outcomes i with probabilities p_i and payoffs v_i:
EV = Σ_i p_i * v_i

Poker decision rule (within-game, risk-neutral): choose action a ∈ A maximizing EV(a).

**Für den Bot:** At every node, select actions purely by comparing EV under your current range and the opponent model; ignore in-game risk preferences and psychology when computing the choice.

## Money as proxy for utility in-game
Assume players are sufficiently bankrolled so marginal utility of chip changes is approximately linear across relevant stakes, letting us treat chip EV as the optimization target.

**Formel:** Assumption: U(w) ≈ a * w + b over the relevant wealth range
⇒ argmax_a E[U(w_final)] = argmax_a E[w_final]

Thus, within-game decision criterion simplifies to maximizing chip EV.

**Für den Bot:** For cash-game NLHE modeling, ignore bankroll/ruin concerns within a single hand and optimize pure chip EV; handle Kelly/variance and game selection at a higher meta-layer, not in the hand logic.

## Range-vs-range perspective (distributional play)
Model your holdings and opponent’s holdings as full probability distributions (ranges) rather than single hands; evaluate strategies at the level of these distributions over all possible holdings/boards.

**Formel:** Let H be the set of hero hands, V the set of villain hands, B the set of boards.
Let P_H(h), P_V(v), P_B(b) be distributions.
Given strategies σ_H, σ_V and payoff function π(h, v, b; σ_H, σ_V):
EV(σ_H, σ_V) = Σ_{h∈H} Σ_{v∈V} Σ_{b∈B} P_H(h) P_V(v) P_B(b) π(h, v, b; σ_H, σ_V)

**Für den Bot:** Core search/solver logic must operate on full ranges, not single-hand heuristics; maintain and update distributions over own and opponent holdings and compute EV at the range-vs-range level.

## Meta-game risk (risk of ruin, Kelly, etc.) separated from hand EV
Bankroll, risk of ruin, and Kelly sizing belong to a higher-level model over long sequences of hands, not the per-hand game-theoretic solution; they modify which games/stakes to play, not the correct line within a given hand under the model.

**Formel:** Meta-game model (abstractly):
Given stake size S, winrate μ(S), variance σ²(S), bankroll B, ruin threshold B_min,
choose S to optimize a criterion like:
max_S E[U(B_T(S))] subject to P(B_t < B_min for some t ≤ T) ≤ ε

Within-hand decision: still maximize chip EV conditional on S chosen.

**Für den Bot:** Implement bankroll and risk models as a separate module that determines allowed stakes and buy-ins; do not contaminate the within-hand equilibrium logic with bankroll-aversion heuristics.

## Toy games as reduced models of NLHE
Use small, exactly solvable games (e.g., AKQ, [0,1] games) to derive general structural results (indifference conditions, optimal bluff frequencies, bet sizing relationships) that transfer to NLHE abstractions.

**Formel:** General approach (not a single equation):
1. Define a finite or low-dimensional state space (hands, actions, payoffs).
2. Solve for Nash equilibrium strategies σ* by:
   - Writing payoff matrices or integrals.
   - Applying best-response / indifference conditions.
3. Extract relationships like: optimal bluffing frequency as function of pot odds, MDF, or stack size.
4. Map these relationships onto analogous NLHE nodes via abstraction.

**Für den Bot:** Base NLHE strategy templates and priors on patterns discovered in solved toy games (e.g., bluff/value ratios, MDF, jam-or-fold thresholds) and then refine via more detailed solving or learning.

## Basic probability rules for poker events
Foundational probability identities for mutually exclusive, independent, and dependent events; used to compute hand/board frequencies.

**Formel:** Notation:
- p(A ∪ B) = probability of A or B
- p(A ∩ B) = probability of A and B
- p(A|B) = probability of A given B
- Ā = complement of A

Mutually exclusive events:
(1.2)  p(A ∪ B) = p(A) + p(B)      if p(A ∩ B) = 0

Independent events:
(1.3)  p(A ∩ B) = p(A) p(B)

All events:
(1.4)  p(A ∪ B) = p(A) + p(B) − p(A ∩ B)

Dependent events:
(1.5)  p(A ∩ B) = p(A) p(B|A)

Complement rules and bounds:
(1.6)  0 ≤ p(A) ≤ 1
(1.7)  p(C) = 1     for a certain event C
(1.8)  p(I) = 0     for an impossible event I
(1.9)  p(A) + p(Ā) = 1
(1.10) p(A) = 1 − p(Ā)

**Für den Bot:** Use these identities to compute exact frequencies of preflop combos, board textures, and joint events (e.g., villain 3-bets AND flop comes monotone), feeding accurate priors into range and EV calculations.

## Exact combinatorial probabilities for key holdem events
Concrete applications of the general rules to holdem: pocket pairs, specific pairs, flopped flushes, etc.

**Formel:** Two aces in a 2-card holdem hand:
- Events: A = first card is an ace, B = second card is an ace
- p(A) = 4/52 = 1/13
- p(B|A) = 3/51 = 1/17
- p(AA) = p(A ∩ B) = p(A) p(B|A) = (1/13)(1/17) = 1/221

More generally, any specific pocket pair XY:
- p(XY) = 1/221

Top three pocket pairs:
- p(AA or KK or QQ) = 3 * (1/221) = 3/221

Flopping a flush when holding a suited hand (exact 3 of suit on flop):
- Remaining cards in deck after hero’s 2 hole cards: 50
- Remaining cards of hero’s suit: 11
- Sequential events:
  A = first flop card is of suit: p(A) = 11/50
  B = second flop card is of suit given A: p(B|A) = 10/49
  C = third flop card is of suit given A and B: p(C|A∩B) = 9/48
- p(flop flush) = p(A ∩ B ∩ C) = (11/50)(10/49)(9/48) = 33/3920 ≈ 0.00842

**Für den Bot:** Hard-code high-importance frequencies (e.g., specific pocket pair 1/221; flopped flush ≈ 0.84%) to avoid recomputation and to calibrate preflop and postflop equity and implied-odds heuristics.

## Expected value (EV) of a discrete probability distribution
Core definition of EV for a finite set of outcomes with associated probabilities; basis of all strategy optimization.

**Formel:** Let P be a distribution on n mutually exclusive outcomes i = 1..n, with value v_i and probability p_i.

(1.11)  <P> = sum_{i=1 to n} p_i * v_i

Example fair coin bet for ±$10:
- B = {(+10, 1/2), (−10, 1/2)}
- <B> = (1/2)(+10) + (1/2)(−10) = 0

Biased coin bet (win $11, lose $10):
- B1 = {(+11, 1/2), (−10, 1/2)}
- <B1> = (1/2)(+11) + (1/2)(−10) = +0.5

Dice example (double-sixes wins $30, otherwise lose $1):
- Outcome values: +30 with prob 1/36; −1 with prob 35/36
- <B2> = (1/36)(+30) + (35/36)(−1) = 30/36 − 35/36 = −5/36 ≈ −0.1389

**Für den Bot:** Represent each betting line as a finite set of outcomes (fold/lose/win sizes × hand/board states) with probabilities; choose actions that maximize EV = Σ p_i v_i, not just probability of winning.

## Linearity/additivity of expected value
EV is linear in distributions and in payoffs; EV over multiple independent or dependent trials is the sum of per-trial EVs; scaling or shifting payoffs scales or shifts EV.

**Formel:** Let X and Y be random variables (valued distributions) and a,b real constants.

Linearity:
- E[aX + bY] = a E[X] + b E[Y]

Additivity across trials (X1, ..., Xn):
- E[Σ_{k=1..n} X_k] = Σ_{k=1..n} E[X_k]

Scaling all outcomes of P by constant c:
- If P has outcomes v_i with probs p_i, and P' has outcomes c v_i with probs p_i,
  then <P'> = c <P>.

Shifting all outcomes of P by constant d:
- If P'' has outcomes (v_i + d) with probs p_i,
  then <P''> = <P> + d.

**Für den Bot:** Evaluate long-run profitability by summing per-spot EVs; you can decompose complex hands into sub-games and sum their EV contributions, and you can safely add rake or other constants after computing strategic EVs.

## Range-based expectation notation <A,B>
Expected value of playing one hand-distribution against another; decomposition over opponent’s range elements using their probabilities.

**Formel:** Let A and B be distributions over possible hands for players Hero and Villain.
Let B consist of distinct hands h_j with probabilities p_B(h_j). Then

< A, B > = Σ_{h_j in B} p_B(h_j) * < A, h_j | B >

Example from text:
- A = {AA, KK, QQ, JJ, AKo, AKs}
- B = {AA, KK, QQ}

Then
< A, B > = p_B(AA) < A, AA | B > + p_B(KK) < A, KK | B > + p_B(QQ) < A, QQ | B >

Here <A, AA|B> means EV of playing range A when villain’s specific hand is AA sampled from B.

**Für den Bot:** Model villain as a weighted range, not a single hand; compute EV against that distribution by summing EV vs each candidate hand times its weight, enabling principled range-vs-range decisions and updates.

## Probability distributions for ranges and board-derived abstractions
Discrete distributions over outcomes (hands, board classes, win/lose) as the central representation; can be coarsened (e.g., odd/even, strong/weak) without changing the math.

**Formel:** A probability distribution is a set of mutually exclusive, exhaustive outcomes with associated probabilities.

Example coin flip outcome distribution:
- C = {(heads, 1/2), (tails, 1/2)}

Abstracted distribution (win/lose instead of H/T):
- C' = {(win, 1/2), (lose, 1/2)}

Die roll distribution:
- D = {(1,1/6), (2,1/6), (3,1/6), (4,1/6), (5,1/6), (6,1/6)}

Coarsened (odd/even) distribution:
- D' = {(odd, 1/2), (even, 1/2)}

Range distribution without explicit probabilities (H = {AA, KK, QQ, AKs, AKo}) implicitly retains relative combinatorial frequencies from initial deck state.

**Für den Bot:** Represent villain ranges as discrete distributions over hands (or hand classes) and freely aggregate to coarser abstractions (e.g., nuts/strong/weak/air) for tractable EV computations while preserving total probabilities.

## Relation between probabilities and odds
Mapping between probability p and odds (ratio of failure to success); useful when comparing pot odds and hand odds.

**Formel:** Definition of odds:
- If an event occurs with probability p, its odds against occurring are

  odds_against = (1 − p) : p

- Often scaled to integers, e.g., 0.7 win prob ⇒ odds_against_lose = 0.3 : 0.7 = 3 : 7.

Conversion formulas:
- Given probability p (0 < p < 1), odds_against in numeric form:
  o = (1 − p) / p

- Given odds_against o (expressed as a single number, i.e., o : 1), probability is
  p = 1 / (1 + o)

Pot odds vs equity (standard poker use):
- Required minimum equity p_min to call a bet B into pot P (ignoring rake, future bets):

  p_min = B / (P + B)  (this is not explicitly in the excerpt but follows from EV=0 condition using p and odds).

**Für den Bot:** Internally work with probabilities for EV math, but convert to odds when comparing against pot odds; use p_min = B/(P+B) to decide whether calling with a given equity is profitable.

## Single-trial variance of a discrete outcome distribution
Variance of a per-hand outcome distribution with finitely many outcomes {x_i} and probabilities {p_i}. Describes dispersion of results around EV; is the building block for all session-variance and CLT approximations.

**Formel:** Given outcomes x_i with probabilities p_i, mean μ = Σ_i p_i x_i.
Variance V = Σ_i p_i (x_i - μ)^2.
Standard deviation σ = sqrt(V).

**Für den Bot:** For any modeled action (e.g., jamming range vs call range) you can compute not only EV but also per-hand variance from the discrete payoff distribution; store both for bankroll/risk modules and for sanity-checking variance of training simulations.

## Additivity of variance across independent trials
If hand outcomes are modeled as i.i.d. draws from a fixed distribution, variances add linearly over hands, while EVs add linearly; session standard deviation grows with sqrt(N).

**Formel:** For a single trial with mean μ and variance σ^2:
N independent trials:
Mean: μ_N = N * μ.
Variance: σ_N^2 = N * σ^2.
Standard deviation: σ_N = sqrt(N) * σ.

**Für den Bot:** Given a per-hand EV and per-hand σ from your model, you can instantly predict the distribution scale of 1k, 10k, or 1M-hand samples for variance management and for calibrating how noisy training or evaluation results will be.

## Standard deviation and variance relationship
Standard deviation is the square root of variance; variance is σ^2. Units differ: EV is in chips, variance in chips^2, σ in chips.

**Formel:** σ = sqrt(V).
V = σ^2.

**Für den Bot:** Always track both σ and σ^2; σ is needed for CLT/normal approximations and for communicating dispersion in chip units, σ^2 is additive and convenient for aggregating across hands or lines.

## Normal (Gaussian) PDF for aggregate results
For large samples, the Central Limit Theorem allows approximating the distribution of cumulative outcomes (e.g., session winnings) by a normal distribution with mean μ_N and standard deviation σ_N.

**Formel:** Normal PDF with mean μ and standard deviation σ:
f(x; μ, σ) = 1 / (σ * sqrt(2π)) * exp( - (x - μ)^2 / (2 σ^2) ).

**Für den Bot:** When modeling long-run bankroll or outcome distributions (e.g., rollout evaluations, simulations), you can approximate the distribution of total winnings as Normal(μ_N, σ_N) to quickly compare strategies in risk-adjusted terms.

## Z-score transformation for sample results
Z-score maps a raw outcome x from a Normal(μ, σ) distribution to standard normal coordinates (mean 0, σ=1). This is the basis for computing tail probabilities and quantiles for session results.

**Formel:** z = (x - μ) / σ.
For samples of size N, typically use μ_N, σ_N from aggregation:
z = (x - μ_N) / σ_N.

**Für den Bot:** You can normalize evaluation results (e.g., exploitability estimates, winrates in test pools) into z-scores to compute how statistically significant deviations from expectation are, reducing overfitting to noise.

## Standard normal CDF Φ(z) for tail probabilities
The cumulative distribution function Φ(z) gives P(Z ≤ z) for Z ~ Normal(0,1). Combined with z-scores, this yields approximate probabilities for events like 'session result ≥ x' or 'proportion of wins deviates by at least δ'.

**Formel:** Φ(z) = (1 / sqrt(2π)) ∫_{-∞}^{z} exp(-t^2 / 2) dt.
For outcome X ~ Normal(μ, σ):
P(a ≤ X ≤ b) ≈ Φ( (b - μ)/σ ) - Φ( (a - μ)/σ ).
Right tail: P(X ≥ x) ≈ 1 - Φ( (x - μ)/σ ).
Left tail: P(X ≤ x) ≈ Φ( (x - μ)/σ ).

**Für den Bot:** Use Φ(z) to estimate probabilities of observed deviations: e.g., if an opponent’s showdown frequency over N hands is z standard deviations from a GTO baseline, you can quantify how unlikely this is under GTO and decide whether to attribute it to real exploitability versus variance.

## Probability of winning a session given per-hand EV and σ
Approximate chance that total result after N independent hands is positive, using normal approximation with mean μ_N and σ_N, then computing P(X > 0).

**Formel:** Given per-hand mean μ and standard deviation σ, session size N:
μ_N = N * μ.
σ_N = sqrt(N) * σ.
We want P(X > 0) where X ~ Normal(μ_N, σ_N).
Define z_0 = (0 - μ_N)/σ_N.
P(X > 0) ≈ 1 - Φ(z_0).

**Für den Bot:** Given a strategy’s estimated μ and σ, you can predict the fraction of winning sessions at different lengths; this can be used to compare lines that have similar EV but drastically different variance profiles, if your objective includes session-level risk management.

## Probability of reaching or exceeding a profit target after N trials
Generalization of the session-win probability: compute the chance that cumulative winnings exceed any threshold T, using CLT/normal approximation.

**Formel:** As above, for X ~ Normal(μ_N, σ_N), target T:
μ_N = N * μ.
σ_N = sqrt(N) * σ.
P(X ≥ T) ≈ 1 - Φ( (T - μ_N)/σ_N ).

**Für den Bot:** For bankroll and risk-of-ruin style modules, you can evaluate how often a strategy hits certain profit/loss thresholds over a planned horizon without explicit Monte Carlo, using just μ and σ.

## Variance of Bernoulli outcome (win/lose event modeling)
Many sub-events (e.g., AK vs AQ all-in outcome, or success/failure of a bluff) are Bernoulli; their variance has a simple closed form used to evaluate how noisy proportions will be over N samples.

**Formel:** For Bernoulli variable with P(success) = p, outcome 1 on success and 0 on failure:
Mean μ = p.
Variance V = p (1 - p).
Standard deviation σ = sqrt( p (1 - p) ).
For N trials: μ_N = Np, σ_N = sqrt(N p (1 - p)).

**Für den Bot:** When you observe binary events like 'villain folds to c-bet' over N opportunities, you can compute expected variance of that proportion; only when observed deviation is several σ away from baseline should you significantly adjust your exploitative strategy.

## Significance of extreme deviations in binary outcomes
Using Bernoulli variance plus CLT, you can compute the z-score for an observed count of successes vs the expected count, and determine how plausible it is. The AQ vs AK example (1000 vs expected 1470 over 2000 trials) illustrates extreme improbability.

**Formel:** For Bernoulli with success prob p, over N trials, expected successes μ_N = Np, std dev σ_N = sqrt(N p (1 - p)).
Observed successes x_obs ⇒ z = (x_obs - μ_N) / σ_N.
Tail probability ≈ Φ(z) (for left tail) or 1 - Φ(z) (for right tail).
Very large |z| (e.g., >5) implies extremely low probability under the model.

**Für den Bot:** A learning or opponent-modeling system should use this significance test to decide when observed frequencies (e.g., villain’s call vs fold to jams) are too unlikely under a GTO prior, and thus justify shifting strategy; this prevents overreacting to short-term variance.

## Additivity of variance across poker hands
For independent trials (hands) with per‑hand mean µ and variance σ², the total result over N hands has mean Nµ and variance Nσ²; the standard deviation scales as sqrt(N).

**Formel:** Single hand: EV = µ, Var = σ^2
N hands (independent, identical distribution):
EV_N = N * µ
Var_N = N * σ^2
SD_N = sqrt(Var_N) = σ * sqrt(N)

Expressed per 100 hands when samples are in hands:
EV_per_100 = (EV_N / N) * 100 = µ * 100 (unchanged)
SD_per_100 = (SD_N / N) * 100 = (σ * sqrt(N) / N) * 100 = σ * (100 / sqrt(N))

**Für den Bot:** When aggregating per‑hand EVs of lines or strategies, variance across hands adds linearly and SD grows like sqrt(N); exploit this to understand result dispersion over sessions and to correctly normalize training or evaluation metrics per 100 hands.

## Normal approximation to sum of hand results (Central Limit Theorem)
For a sufficiently large number of independent poker hands with finite variance, the distribution of the total (or average) win/loss approaches a normal distribution, enabling approximate confidence intervals and tail probabilities.

**Formel:** Let X_i be iid per‑hand results with mean µ and variance σ^2.
Total over N hands: S_N = X_1 + ... + X_N
Then for large N:
S_N ≈ Normal(mean = N * µ, variance = N * σ^2)

Sample mean over N hands: M_N = S_N / N
M_N ≈ Normal(mean = µ, variance = σ^2 / N)

Approximate (1 − α) two‑sided interval for M_N using z_{α/2}:
CI_low  ≈ µ − z_{α/2} * (σ / sqrt(N))
CI_high ≈ µ + z_{α/2} * (σ / sqrt(N))

For 95.5% interval, z_{α/2} ≈ 2, so:
CI_low  ≈ µ − 2 * (σ / sqrt(N))
CI_high ≈ µ + 2 * (σ / sqrt(N))

**Für den Bot:** When simulating or evaluating strategies over many hands, treat aggregate results as approximately normal with mean Nµ and SD σ√N; this allows computing how likely large downswings/upswings are and stabilizing learning targets over large samples.

## Sampling distribution of a win rate per 100 hands
Given a per‑hand SD σ (in big bets/hand), the SD of an observed win rate expressed in big bets per 100 hands over N hands is σ * (100 / sqrt(N)); this is used both in maximum likelihood estimation and confidence intervals of a winrate.

**Formel:** Let:
- σ = SD per hand (e.g., in BB/hand)
- N = number of hands in sample
Define winrate W = (total result / N) * 100 (BB/100 hands).

Then:
Var(W) = (100^2 / N^2) * Var(S_N) = (100^2 / N^2) * (N * σ^2) = (100^2 / N) * σ^2
SD(W) = σ_W = 100 * σ / sqrt(N)

Example from text: σ = 2.1 BB/hand, N = 16,900
σ_W ≈ 100 * 2.1 / sqrt(16900) ≈ 1.61 BB/100

**Für den Bot:** Observed winrates over finite samples are noisy; the noise level decreases like 1/sqrt(N). Use σ * 100 / sqrt(N) as the natural scale of winrate fluctuation when deciding if an observed difference in line EVs or opponent results is statistically meaningful.

## Approximate confidence interval for a player’s true win rate (classical)
Given a sample mean win rate and an estimate of per‑hand SD, approximate a confidence interval for the underlying true mean using z‑intervals based on the sampling distribution of the mean.

**Formel:** Inputs:
- Observed sample mean winrate in BB/100: x_bar_100
- SD per hand: s (BB/hand)
- Number of hands: N

First, SD of sample mean in BB/100:
σ_N_100 = 100 * s / sqrt(N)

For an approximate (1 − α) CI using z_{α/2}:
CI_low  ≈ x_bar_100 − z_{α/2} * σ_N_100
CI_high ≈ x_bar_100 + z_{α/2} * σ_N_100

Text example (N = 16,900, x̄_100 = 1.15 BB/100, s = 2.1 BB/hand, z≈2):
σ_N_100 ≈ 1.61
CI_low ≈ 1.15 − 2 * 1.61 ≈ −2.07 BB/100
CI_high ≈ 1.15 + 2 * 1.61 ≈ 4.37 BB/100

**Für den Bot:** Use confidence intervals around estimated line or strategy winrates to decide whether to trust small measured EV differences; avoid overfitting to noise when two actions have overlapping CIs on your evaluation samples.

## Maximum likelihood estimate (MLE) of mean from a normal sample
Under the assumption of iid normal observations with unknown mean and known (or well‑estimated) variance, the maximum likelihood estimate of the population mean is the sample mean.

**Formel:** Let X_1, ..., X_N be iid Normal(µ, σ^2). The likelihood of µ given observed data is:
L(µ) = Π_{i=1}^N [ (1 / (σ√(2π))) * exp(−(X_i − µ)^2 / (2σ^2)) ]

Maximizing L(µ) over µ is equivalent to maximizing log L(µ):
log L(µ) = const − (1 / (2σ^2)) * Σ_{i=1}^N (X_i − µ)^2

Derivative in µ gives:
d/dµ Σ (X_i − µ)^2 = −2 Σ (X_i − µ) = 0 ⇒ Σ X_i = Nµ ⇒ µ_MLE = (1/N) Σ X_i = x̄

In text: observed x̄ = 1.15 BB/100 ⇒ MLE of true mean winrate is 1.15 BB/100.

**Für den Bot:** Whenever you model line outcomes or opponent parameters as normal with unknown mean, treat the empirical average of samples as the MLE for that parameter; this is the natural point estimate your learning module should default to before adding priors.

## Bayes’ theorem (general form for discrete hypotheses)
Bayes’ theorem updates the probability of a hypothesis based on new evidence, combining the prior probability of the hypothesis with the likelihood of observing the evidence under that hypothesis.

**Formel:** Basic conditional probability identity:
P(A ∩ B) = P(A) * P(B | A)

Bayes’ theorem (simple form):
P(B | A) = P(A ∩ B) / P(A) = P(A | B) * P(B) / P(A)

Expanded with explicit complement B̄:
P(B | A) = [ P(A | B) * P(B) ] / [ P(A | B) * P(B) + P(A | B̄) * P(B̄) ]

Where B̄ is the complement of B and P(B̄) = 1 − P(B).

**Für den Bot:** For opponent modelling and hand reading, maintain priors over villain’s hand classes or strategy types and update them with observed actions via Bayes’ rule: posterior ∝ prior × likelihood(action | hypothesis).

## Bayesian inference on a player’s win rate (conceptual model)
Treat each player’s true win rate as a random variable drawn from a population distribution (prior), then update this distribution using observed sample results to obtain a posterior distribution over the player’s true win rate.

**Formel:** Let θ be the true winrate (e.g., BB/100) of a randomly chosen player, with prior density p(θ).
Observed sample statistic X (e.g., sample mean over N hands) has likelihood p(X | θ).

Bayes’ rule in continuous form:
Posterior density: p(θ | X) = [ p(X | θ) * p(θ) ] / p(X)
Where p(X) = ∫ p(X | θ) p(θ) dθ is a normalizing constant.

If we approximate X | θ as Normal(mean = θ, variance = σ_N^2) and choose a conjugate Normal prior θ ~ Normal(µ_0, τ_0^2), then the posterior is θ | X ~ Normal(µ_post, τ_post^2) with:

τ_post^2 = 1 / (1/τ_0^2 + 1/σ_N^2)
µ_post   = τ_post^2 * (µ_0/τ_0^2 + X/σ_N^2)

This yields a weighted average of prior mean and sample mean, with weights inversely proportional to their variances.

**Für den Bot:** Instead of trusting short‑term samples, treat each opponent’s winrate or tendency parameter with a prior (e.g., population distribution from your database) and update toward the observed statistics; this shrinks extreme short‑term observations (like 10 BB/100 over 5k hands) toward realistic values, stabilizing exploitative adjustments.

## Application example of Bayes (test accuracy vs base rate)
The posterior probability of a condition given a positive test depends strongly on the base rate and false positive rate, not just the test’s sensitivity; by analogy, seemingly strong tells or stats can still imply low posterior probabilities if the prior is small or false positive rate is high.

**Formel:** Given:
- Prior probability (base rate) of condition: P(B)
- Sensitivity (true positive rate): P(A | B)
- False positive rate: P(A | B̄)

Posterior probability of condition given positive test:
P(B | A) = [P(A | B) * P(B)] / [P(A | B) * P(B) + P(A | B̄) * (1 − P(B))]

Numerical examples from text:
1) P(B) = 0.05, P(A | B) = 0.8, P(A | B̄) = 0.1:
   P(B | A) = (0.8 * 0.05) / (0.8 * 0.05 + 0.1 * 0.95) ≈ 0.2963

2) Improve sensitivity to 1.0, keep false positive 0.1:
   P(B | A) = (1.0 * 0.05) / (1.0 * 0.05 + 0.1 * 0.95) ≈ 0.345

3) Keep sensitivity 0.8, lower false positive to 0.06:
   P(B | A) = (0.8 * 0.05) / (0.8 * 0.05 + 0.06 * 0.95) ≈ 0.412

**Für den Bot:** When interpreting rare but ‘strong’ actions (e.g., massive river overbet as a bluff), combine how often such lines are used overall (base rate) with how often value vs bluff hands choose them; a line that is almost always value but appears rarely can still mean the posterior bluff frequency is low.

## Bayesian update for villain type given observed action
Use Bayes’ theorem to update the probability that a player is of a certain type (e.g., maniac vs tight) after seeing actions like preflop raises.

**Formel:** Given types T in {t1,...,tk}, prior p(t_i), and observed action A with likelihood p(A | t_i):

Posterior for type t_j:

p(t_j | A) = [ p(A | t_j) * p(t_j) ] / [ Σ_i p(A | t_i) * p(t_i) ]

For 2-type maniac vs tight example:

Let M = maniac, N = non-maniac, A = "raise from cutoff".

p(M | A) = [ p(A | M) * p(M) ] / [ p(A | M) * p(M) + p(A | N) * p(N) ]

With p(A|M)=0.8, p(A|N)=0.1, p(M)=0.1, p(N)=0.9:

p(M | A) = (0.8 * 0.1) / (0.8 * 0.1 + 0.1 * 0.9) ≈ 0.471

**Für den Bot:** Maintain a type distribution for each opponent (e.g., maniac vs nit, loose vs tight) and update it in real time with Bayes’ rule from observed actions (raises, folds, sizings). Use these posteriors immediately in exploitative EV calculations instead of waiting for large samples.

## Sequential Bayesian updates from multiple actions
Apply Bayes’ theorem repeatedly as more actions are observed; the posterior after one hand becomes the prior for the next.

**Formel:** Let θ be a hidden parameter (e.g. “maniac-ness”) and A_1, A_2,... observed actions.

After first action A_1:

p(θ | A_1) ∝ p(A_1 | θ) * p(θ)

After k actions A_1,...,A_k:

p(θ | A_1,...,A_k) ∝ p(θ) * Π_{i=1}^k p(A_i | θ)

For discrete types t_j:

p(t_j | A_1,...,A_k) = [ p(t_j) * Π_{i=1}^k p(A_i | t_j) ] / [ Σ_m p(t_m) * Π_{i=1}^k p(A_i | t_m) ]

**Für den Bot:** Treat opponent modeling as continuous Bayesian inference over types or parameters. After every significant action (e.g., 3-bet, limp, big river call), update the type probabilities multiplicatively and feed the current posterior into your exploitative strategy selection.

## Bayesian estimation of a player’s win rate (parameter learning)
Use a prior distribution over possible true win rates and update it with observed results to get a posterior distribution, rather than equating sample mean to true win rate.

**Formel:** Let θ denote a player’s true win rate (BB/100). Let D be observed sample data (mean x̄ over n hands, sample standard deviation s per 100 hands, or equivalently standard error σ_sample).

Classical (frequentist) MLE:

θ_MLE = x̄.

Bayesian:

Prior: p(θ) over discrete values θ_j with masses p(θ_j).
Likelihood for each θ_j:

Assume sampling distribution x̄ | θ_j ~ Normal(θ_j, σ_sample^2).

Then
p(D | θ_j) ≈ φ((x̄ - θ_j)/σ_sample) / σ_sample,
where φ is the standard normal pdf.

Posterior for θ_j:

p(θ_j | D) = [ p(D | θ_j) * p(θ_j) ] / [ Σ_k p(D | θ_k) * p(θ_k) ].

Posterior expectation (Bayes estimator under squared loss):

E[θ | D] = Σ_j θ_j * p(θ_j | D).

**Für den Bot:** For long-run self-evaluation and opponent modeling (e.g., estimating how much a seat or pool is worth), combine population priors over achievable win rates with observed results; do not overfit to early hot runs. Use posterior means or quantiles instead of raw sample means when deciding game selection or bankroll risk.

## Regression to the mean via Bayesian shrinkage
Observed performance extremes are pulled (shrunk) toward the population mean when sample sizes are small, because some of the extremeness is likely variance rather than true skill.

**Formel:** In a Bayesian normal-normal model, with:

Prior: θ ~ Normal(μ_0, τ^2)
Data: x̄ | θ ~ Normal(θ, σ_sample^2)

Posterior mean (Bayes estimator):

E[θ | x̄] = w * x̄ + (1 - w) * μ_0,

where

w = τ^2 / (τ^2 + σ_sample^2).

w increases with sample size n (since σ_sample^2 = σ^2 / n), so the posterior mean is closer to x̄ as n grows.

This is formal regression to the mean: predictions are a weighted average of the observation and the population mean.

**Für den Bot:** When estimating any rate parameter from limited samples (3-bet frequency, fold-to-cbet, bluff rate), shrink toward a reasonable population prior. Don’t fully trust noisy short-term stats; use a weighted blend of prior and data with weight increasing in sample size.

## Maximally exploitive strategy definition
Given an opponent strategy S, the maximally exploitive strategy is the one that maximizes your expected value against S over all admissible strategies.

**Formel:** Let Σ_A be the set of all strategies for player A and Σ_B for player B.
Let EV_A(σ_A, σ_B) denote A’s expected value when A uses σ_A and B uses σ_B.

Given fixed opponent strategy σ_B = S, A’s maximally exploitive strategy is:

σ_A^*(S) ∈ argmax_{σ_A ∈ Σ_A} EV_A(σ_A, S).

Similarly for B:

σ_B^*(S) ∈ argmax_{σ_B ∈ Σ_B} EV_B(S, σ_B).

**Für den Bot:** Separate your engine conceptually into (i) a model of the opponent’s current strategy S (via Bayesian inference) and (ii) a solver or approximator that finds an approximate best response σ* to S, rather than always playing a fixed equilibrium strategy.

## Toy river bluffing game EV for caller (Example 4.1)
In a simple river toy game, derive the EV of calling vs folding given opponent’s bluff frequency and value frequency.

**Formel:** Game:
- Pot size = P (here P = 4 big bets before river bet).
- Player A has nuts with probability q and pure air with probability 1 - q.
- A always bets nuts, and bluffs (bets) a fraction x of his total hands (so bluffing range fraction among all hands is x, with 0 ≤ x ≤ 1 - q).
- B holds a bluff-catcher: beats all bluffs, loses to nuts.
- Bet size = 1 big bet.

Conditional on facing a bet, the EV for B if he calls:

<B, call> = p(A has nuts | A bet) * (-1) + p(A has bluff | A bet) * (P + 1)

In the specific text setup (P = 4, q = 0.2, total-bluff fraction x):

<B, call> = (0.2)(-1) + 5x = 5x - 0.2.

EV of folding:

<B, fold> = 0.

Indifference point for B (call = fold):

5x - 0.2 = 0  ⇒  x* = 0.04.

So if x > 0.04, B should always call; if x < 0.04, B should always fold.

**Für den Bot:** On rivers where your hand is a pure bluff-catcher vs a polarized bet, EV(call) is linear in villain’s bluff frequency. You can compute your threshold bluff frequency (indifference point) from pot and bet size and compare to your estimate of villain’s bluff rate to decide call vs fold.

## Indifference condition in bluffing games (general form)
In simple river games, optimal bluffing or calling frequencies are found by making the opponent indifferent between their options (e.g., call vs fold, bluff vs check).

**Formel:** Generic one-street river model:
- Pot size before bet: P.
- Bet size: B.
- Aggressor has value hands with probability f_v (of his total range on river) and bluffs with probability f_b (of total range).
- Opponent has a pure bluff-catcher; his options: call or fold.

Conditional on facing a bet:

p_v = f_v / (f_v + f_b)

p_b = f_b / (f_v + f_b)

EV(call) for bluff-catcher:

EV_call = p_b * (P + B) - p_v * B.

Indifference for defender between calling and folding (EV_call = 0):

p_b * (P + B) = p_v * B.

Using p_b = 1 - p_v:

(1 - p_v)(P + B) = p_v B
⇒ P + B - p_v(P + B) = p_v B
⇒ P + B = p_v (P + 2B)
⇒ p_v* = (P + B) / (P + 2B).

Corresponding bluff proportion among *betting range*:

p_b* = 1 - p_v* = B / (P + 2B).

If we parameterize by ratio α = B / P:

p_b* = α / (1 + 2α).

These are the GTO bet/bluff mix for a polarized range on the river in this simple model.

**Für den Bot:** For a single polarized river bet, to be unexploitable your bluff fraction in your betting range should be p_b* = B / (P + 2B). Use this to calibrate river bluff frequencies and to infer villain’s value:bluff ratio from bet sizing.

## Minimum defense frequency (MDF) relation to bet size
The minimum fraction of your range you must continue with versus a bet in order not to allow opponent’s pure bluffs to show immediate profit, given pot and bet size.

**Formel:** Let:
- Pot before bet: P.
- Opponent bet size: B.
- You fold with frequency F (over your range), continue with C = 1 - F.

If opponent bluffs with always-losing hands:

EV(bluff) = F * P - C * B.

MDF is defined by setting EV(bluff) = 0 so that pure bluffs break even at best:

F * P = C * B

Since C = 1 - F:

F * P = (1 - F) * B
⇒ FP = B - BF
⇒ F(P + B) = B
⇒ F* = B / (P + B)

Therefore

MDF = C* = 1 - F* = P / (P + B).

If we define α = B / P, then

MDF = 1 / (1 + α).

**Für den Bot:** Precompute MDF for common bet sizings and use it as a baseline for river defense frequencies with bluff-catchers vs unknown or balanced opponents. Deviate from MDF exploitatively when Bayesian opponent modeling suggests over- or under-bluffing.

## Jam-or-fold equilibrium (all-in shove game structure)
In simplified jam-or-fold games (e.g., short-stacked preflop all-in decisions), equilibrium strategies come from balancing ranges so that opponent is indifferent between calling and folding versus a shove, and between shoving and folding versus a call.

**Formel:** Generic two-player jam-or-fold model:
- Effective stack S (in big blinds or chips).
- Pot before shove: P.
- Shove size = S (risk S to win P).
- Shover has range R_s; caller has range R_c.

Let:
- For caller, EV(call | hand h) = p_win(h, R_s) * (P + S) - (1 - p_win(h, R_s)) * S.
- EV(fold | h) = 0.

Indifference for marginal calling hand h*: EV(call | h*) = 0:

p_win(h*, R_s) * (P + S) - (1 - p_win(h*, R_s)) * S = 0
⇒ p_win(h*, R_s) * (P + S + S) = S
⇒ p_win(h*, R_s) = S / (P + 2S).

Similarly, for marginal shoving hand g* vs caller’s calling range R_c:

EV(shove | g*) = p_fold(R_c) * P + p_call(R_c) * [ p_win(g*, R_c) * (P + S) - (1 - p_win(g*, R_c)) * S ].

At equilibrium, marginal shoves satisfy EV(shove | g*) = 0 (or = EV(fold) when folding has some baseline EV), leading to equations linking R_s and R_c that can be solved numerically or via root-finding.

**Für den Bot:** For short-stack preflop or river jam spots, approximate equilibrium push/fold ranges by enforcing (i) caller’s marginal hands break even vs shover’s range and (ii) shover’s marginal hands break even vs caller’s range. Implement numeric solvers around these indifference equations to generate jam-or-fold charts and to adjust them exploitatively using Bayesian opponent models.

## Pot odds and EV of calling
Relate pot odds and equity to EV of calling a bet; fundamental for comparing call/fold/raise options with given equity estimates.

**Formel:** Let:
- Pot before facing a bet: P.
- Bet size you face: B.
- Your equity vs opponent’s range when called: e = P(win | call).

On a terminal street with no further betting and no fold equity if you call:

EV(call) = e * (P + B) - (1 - e) * B.
EV(fold) = 0.

Indifference between call and fold (EV(call) = 0) gives minimum equity needed to call:

e * (P + B) = (1 - e) * B
⇒ e(P + B) = B - eB
⇒ e(P + B + B) = B
⇒ e* = B / (P + 2B).

Pot odds in ratio form: need e ≥ 1 / (1 + pot_odds_ratio), where pot_odds_ratio = (P + B) / B is the price you are getting.

**Für den Bot:** For every river call decision, compute required equity from pot and bet size (e* = B / (P + 2B)) and compare it with your equity estimate vs villain’s range (informed by Bayesian type and line). On earlier streets, adapt this formula to include implied and reverse implied odds estimates.

## Strategy as mapping from information sets to actions
Formally, a strategy specifies an action at every possible information set (state of knowledge) a player might encounter; in poker this is intractable in full detail, so approximations and abstractions are used.

**Formel:** In extensive-form game theory:

A (pure) strategy for player i is a function s_i that assigns to each information set I_i an action a in A(I_i):

s_i: I_i → A(I_i).

A mixed strategy is a probability distribution over pure strategies. A behavioral strategy specifies, for each information set I_i, a probability distribution over actions at that information set.

In poker, information sets correspond to (private cards, public board cards, betting history, stack sizes, positions, etc.).

**Für den Bot:** Represent your policy as a mapping from abstracted information states (bucketed hand strength, board class, pot size, positions, stack depths, opponent model) to action probabilities, and train/solve these mappings; treat them as behavioral strategies over information sets rather than as isolated hand decisions.

## Single‑street pot‑odds call decision (made hand vs draw)
Draw calls a single bet facing a known made hand when its equity in the enlarged pot exceeds the cost of calling.

**Formel:** EV_call = p_win * (P + B + C) - C
Call iff EV_call > 0

Where:
- P = current pot before betting
- B = bettor’s bet size
- C = caller’s call size
- p_win = caller’s probability of winning at showdown (given one card to come)

Equivalently, in odds form:
Call iff p_win > C / (P + B + C)
Pot odds offered = (P + B + C) : C.

**Für den Bot:** On any street where further betting is effectively over (e.g., shallow SPR, open cards, or terminal abstraction), compare your draw’s equity to C/(P+B+C); call only if equity exceeds this threshold.

## Made hand vs draw: bettor’s EV bet vs check
With a made hand versus a known draw, betting increases EV if the draw can profitably call given pot odds; otherwise betting may drive out dominated equity.

**Formel:** EV_check_made = p_made_wins * P

EV_bet_made = p_made_wins * (P + B + C) - B

Where:
- P = current pot
- B = made hand’s bet size
- C = caller’s call size (typically = B)
- p_made_wins = probability made hand wins at showdown (given one card to come and no fold).

In Example 4.2:
EV_check_A = (35/44)*400
EV_bet_A = (35/44)*520 - 60

**Für den Bot:** When villain’s draw is +EV to call versus your bet, betting your made hands usually strictly dominates checking (you charge his equity and grow the pot linearly with your equity share); use this to bias towards bet‑bet lines versus capped drawing ranges.

## Pot‑odds threshold for draws (equity vs pot odds relation)
Minimum equity required to continue with a draw equals the inverse of 1 plus pot odds; equivalently, compare odds of hitting vs odds laid.

**Formel:** Let:
- P = pot before facing bet
- B = bet you must call (so final pot if you call is P + B + B in heads‑up fixed‑limit)

You call iff:

p_win > B / (P + 2B)

Odds form:
- Pot odds offered = (P + 2B) : B
- Required winning odds (win:lose) < pot odds.

Example 4.2 (turn call):
P = 400, B = 60 ⇒ threshold p_win > 60 / (400 + 120) = 3/26 ≈ 11.5%.

**Für den Bot:** In abstractions where future betting is ignored on a street, enforce a policy: fold draws whose equity is below bet/(pot+2*bet); this approximates correct folding thresholds versus pot‑sized fractions in NLHE.

## Multi‑street immediate pot‑odds vs total (two‑street) equity
Immediate pot odds on the current street use only the probability of hitting on the *next* card, not total probability of eventually winning over multiple streets with future investments.

**Formel:** For two cards to come (turn and river), independent conditional draws:

Total probability of eventually hitting (at least one street):

p_hit_total = 1 - p_miss_turn * p_miss_river

= 1 - (1 - o / U_turn) * (1 - o / U_river)

Where o = number of outs; U_turn, U_river = unseen cards on each street.

BUT immediate flop pot‑odds decision only uses

p_hit_next = o / U_turn

in:

EV_flop_call = p_hit_next * (P + 2B_flop) - B_flop

not p_hit_total.

**Für den Bot:** When your strategy assumes future folds (e.g., you will not pay again if you miss), use only the one‑card hit probability in flop decisions, not the full turn+river equity; otherwise you over‑call facing bets with draws.

## Two‑street call tree EV (fixed‑limit draw vs made hand)
EV of a draw calling on flop and possibly on turn can be decomposed by street and conditional on hit/miss outcomes using the law of total expectation.

**Formel:** Example 4.4 structure (flop and turn betting, then river):

EV_flop_call = EV_turn_given_call  (since flop call is embedded)

On the turn after miss:
EV_turn_call = p_hit_river * (P_turn + 2B_turn) - B_turn

Total turn EV with card types:
EV_turn_total = p(A_or_K_on_turn)*0 + p(other_on_turn)*EV_turn_call

General pattern (one card to come):
EV_turn_total = sum_i p(state_i) * EV(state_i)

where states partition the turn card outcomes (e.g., made‑hand improves and kills draw vs not).

**Für den Bot:** For multi‑street limit or capped‑bet NL subgames, represent draw decisions as explicit trees by card type; compute EV via state partitioning rather than naive ‘equity vs price’, especially when some future cards kill your outs.

## EV comparison: raising to ‘give yourself odds’ vs calling (draw vs made hand)
Raising to supposedly ‘improve your odds’ (by enlarging future pots) is often −EV with a draw, because you invest more now while still not having enough equity against the bigger pot and villain’s stronger continuing range.

**Formel:** Let R = cost when raising line, C = cost when call‑then‑fold line.

Decompose EV when raising as:

EV_raise = EV_win_on_next_card + EV_continue_to_river

EV_win_on_next_card = p_hit_next * (P + contributions_from_raises) - R

EV_continue_to_river = p_miss_next * [ p_hit_river * (P_after_turn_bets) - B_turn ]

Compare with:

EV_call = p_hit_next * (P + 2B_flop) - B_flop

Example 4.6 shows EV_raise ≈ −18.30 vs EV_call ≈ +4.67.

**Für den Bot:** In exploit/heuristic layers, avoid ‘auto‑raising draws to create odds’; only raise draws when the raise itself has standalone EV (fold equity, range advantage, or future street leverage), not just to increase future pot size.

## Total probability of winning by river with a draw (independent streets)
Probability of improving by the river equals one minus the product of missing all your outs on each street.

**Formel:** For a flop draw with o outs, U_turn unseen cards to the turn, U_river unseen to the river:

p_win_by_river = 1 - p_miss_turn * p_miss_river

= 1 - (1 - o / U_turn) * (1 - o / U_river)

Example 4.5:
- o = 8 outs, U_turn = 45, U_river = 44

p_win_by_river = 1 - (37/45)*(36/44) ≈ 0.327 or 32.7%.

**Für den Bot:** Use this total two‑street equity when evaluating preflop/flop all‑ins or jam‑or‑fold subgames where you will see both cards; don’t mix it with single‑street pot‑odds calculations where you intend to fold if you miss.

## Implied odds with fixed future payoff (closed‑card payoff model)
Implied odds = immediate pot odds + expected payoff from future streets when the draw hits and the made hand pays off some fixed amount; EV is sum over hit/no‑hit scenarios on both streets.

**Formel:** General two‑street implied‑odds EV with fixed future bets:

Let:
- P0 = pot before flop bet
- B_f = flop bet size (we call B_f)
- B_t, B_r = turn and river bet sizes when draw hits and is paid off
- C_total = total our contribution in cases considered
- V_hit = total pot we win (including our and villain’s future bets)
- o = outs to flush; U_turn, U_river = unseen cards

Define cases:
1) Hit on turn (H_t): p(H_t) = o / U_turn
   EV(H_t) = V_hit_turn - C_total_turn

2) Miss turn, hit river (M_t ∧ H_r):
   p(M_t ∧ H_r) = (1 - o/U_turn) * (o/U_river)
   EV(M_t ∧ H_r) = V_hit_river - C_total_river

3) Miss both (M_t ∧ M_r):
   p(M_t ∧ M_r) = 1 - p(H_t) - p(M_t ∧ H_r)
   EV(M_t ∧ M_r) = - C_miss

Total EV:

EV_total = p(H_t)*EV(H_t) + p(M_t ∧ H_r)*EV(M_t ∧ H_r) + p(M_t ∧ M_r)*EV(M_t ∧ M_r)

Example 4.7 numerically:
Case 1 prob = 8/45, EV1 = +285
Case 2 prob = (37/45)*(8/44), EV2 = +285
Case 3 prob = remaining, EV3 = -90
EV ≈ 50.67 + 42.61 - 60.55 ≈ +32.73.

**Für den Bot:** Model implied‑odds calls by explicitly adding a term for expected future payoff when you hit; in NLHE, this ‘payoff’ is capped by effective stacks and by villain’s calling frequency, and should be estimated (not assumed equal to stacks).

## Effective pot size / payoff amount in closed‑draw games
When draws are closed (villain cannot see whether you hit), you gain an informational advantage: the made hand must sometimes pay off bets on scary cards, increasing your implied odds via an ‘effective pot size’ term.

**Formel:** Effective pot at decision time ≈ P_effective = P_current + E[future_payoff | draw hits]

Implied‑odds call condition:

p_hit_next * P_effective - C ≥ 0

⇒ p_hit_next ≥ C / P_effective

Where E[future_payoff | draw hits] includes villain’s calling frequency on later streets and bet sizes, minus your additional investments.

**Für den Bot:** In NLHE, especially when you are the in‑position aggressor on dynamic boards, your draws’ ‘effective pot’ is larger than the current pot; account for extra future value when sizing calls and semi‑bluffs, especially vs opponents who over‑call rivers on completed draws.

## Pot odds vs total equity paradox resolution
A draw can have higher total equity by the river than its immediate pot odds suggest yet still be a fold, because the total equity includes scenarios where you must invest additional negative‑EV calls on later streets.

**Formel:** Example 4.5:
Total equity by river:

p_win_total = 1 - (37/45)*(36/44) ≈ 32.7%

Immediate pot odds on flop (P = 135, B = 30):

Pot odds = (135+60):30 = 195:30 ≈ 6.5:1
Single‑street threshold: p_hit_turn > 30 / (135+60) = 30/195 ≈ 15.4%
Actual p_hit_turn = 8/45 ≈ 17.8% ⇒ flop call alone is +EV.

But considering turn call as well:

EV_turn_call = (8/44)*(315) - 60 ≈ −2.73 < 0

So optimal line: call flop, fold turn if miss; total equity 32.7% doesn’t justify calling both streets.

**Für den Bot:** In strategy design, avoid using ‘equity vs pot’ heuristics across multiple future betting rounds; evaluate each decision node with its own subtree, optimally folding some future streets even when your total by‑river equity looks high.

## Single‑street river calling vs bluffing toy game (Example 4.8 structure)
Heads‑up river toy game: one player (B) has a polarized range (nuts 20% / air 80%) and can value bet or bluff for a fixed size into a fixed pot; the other player (A) always loses when calling vs value hands and always wins vs bluffs. Optimal strategies arise by making opponent indifferent: A chooses calling frequency x; B chooses bluffing frequency y over his misses.

**Formel:** Given:
- Pot P before river bet
- Bet size b (risk for bettor, and additional amount caller must call)
- Value region frequency q (here q = 0.2 = B has flush 20%)
- Bluffing frequency y = P(B bets as a bluff | B missed)
- Calling frequency x = P(A calls | B bets)

Expected value of A's call when called:
EV_A_call = q * (-b) + (1 - q) * y * (P + b)

In the excerpt numbers:
P = 655, b = 80, q = 0.2
EV_A_call = 0.2 * (-80) + y * (655 + 80)
EV_A_call = 735*y - 16

Expected value of B’s bluff when he chooses to bluff:
EV_B_bluff = x * (-b) + (1 - x) * P
In numbers:
EV_B_bluff = x * (-80) + (1 - x) * 655
EV_B_bluff = 655 - 735*x

Indifference (zero‑EV) thresholds:
For A (indifferent call/fold):
EV_A_call = 0 => 735*y - 16 = 0 => y* = 16 / 735 ≈ 0.02177 ≈ 2.2%

For B (indifferent bluff/check):
EV_B_bluff = 0 => 655 - 735*x = 0 => x* = 655 / 735 ≈ 0.89116 ≈ 89.1%

Best responses:
- If y > y*, A’s best response is x = 1 (always call)
- If y < y*, A’s best response is x = 0 (always fold)
- If x < x*, B’s best response is y = 1 (always bluff misses)
- If x > x*, B’s best response is y = 0 (never bluff)

Game‑theoretic optimal (Nash) strategies for this toy model occur when each player chooses his frequency exactly at the opponent’s indifference point, so that unilateral deviations do not improve EV.

**Für den Bot:** On a single street with a polarized bettor, the equilibrium style is: caller defends with frequency x* = P / (P + b) (the familiar MDF formula), and bettor bluffs with frequency y* = (q*b)/((1-q)(P+b)) so that the caller is indifferent between calling and folding. Your river module should compute these exact thresholds for any pot and bet size, then compare opponents’ observed bluffing/calling tendencies to choose either near‑GTO frequencies (for robustness) or the best‑response extremes (x≈0/1 or y≈0/1) for maximally exploitative play.

## MDF (Minimum Defense Frequency) / alpha relationship (implicit)
General relationship between pot size, bet size, and required defense frequency in one‑street games, which appears here in the expression for B’s bluff EV and A’s calling threshold. MDF is the minimum calling frequency that makes opponent’s zero‑equity bluffs indifferent; 1−MDF is the maximum fold frequency you can allow before villain’s bluffs auto‑profit.

**Formel:** Given:
- Pot P
- Bet size b
- Villain’s pure bluff EV when you call with frequency x:
EV_bluff = x * (-b) + (1 - x) * P

Indifference condition (EV_bluff = 0):
0 = x * (-b) + (1 - x) * P
=> 0 = -b*x + P - P*x
=> b*x + P*x = P
=> x*(P + b) = P
=> MDF := x* = P / (P + b)

Fold frequency at MDF:
F* = 1 - MDF = 1 - P / (P + b) = b / (P + b)

Defining alpha = b / P (bet as fraction of pot):
MDF = 1 / (1 + alpha)
F* = alpha / (1 + alpha)

These are independent of villain’s value range; they arise solely from the payoff structure vs pure bluffs.

**Für den Bot:** For any river node where villain can have pure bluffs, you should compute MDF = P/(P+b). Against an unknown or strong opponent, defending at least MDF on your range frontier prevents them from printing money with zero‑equity bluffs; versus opponents who visibly under‑bluff, you may intentionally defend less than MDF to exploit their value‑heavy range.

## Indifference principle for optimal frequencies
Optimal mixed strategies in these toy river games are determined by making the opponent indifferent across their available pure actions. Here, A sets his call frequency such that B’s bluffs have EV 0; B sets his bluffing frequency such that A’s calls have EV 0. Any deviation is non‑profitable if the opponent maintains the indifference‑making mix.

**Formel:** General one‑street structure with bettor B and caller A.

1) A’s indifference between call and fold vs B’s betting range:
Let:
- P = pot
- b = bet size
- q = P(B has value | B bets)
- (1-q) = P(B is bluffing | B bets)
- When A calls: payoff_call = q*(-b) + (1-q)*(P + b)
- When A folds: payoff_fold = 0

Indifference condition:
q*(-b) + (1-q)*(P+b) = 0
Solve for q (or, more often, for B’s bluffing intensity determining q), giving the required bluff:value ratio that makes A’s marginal call EV 0.

If B has fixed value frequency q0 and can choose bluff frequency y among his misses, the effective q is
q = q0 / (q0 + (1-q0)*y)
and the same condition yields y* that makes A indifferent (as in item 1).

2) B’s indifference between bluff and check with his misses vs A’s calling frequency x:
- EV_bluff = x*(-b) + (1-x)*P
- EV_check = 0 (ignoring showdown equity for pure air)

Indifference condition:
x*(-b) + (1-x)*P = 0
=> x* = P / (P + b) (the MDF condition).

In any 2‑action, 2‑player stage game, to find a mixed‑strategy equilibrium, equate the opponent’s EV for their pure actions so they are indifferent over them.

**Für den Bot:** General solver logic for small NLHE subgames should explicitly enforce opponent indifference at equilibrium: adjust your bet/bluff frequencies until villain’s marginal calls/raises/checks all have equal EV. Implement this numerically for arbitrary river nodes: treat their boundary hands as indifferent (EV_call = EV_fold), then solve for your optimal bluff:value ratio and their optimal defense frequency.

## Pure bluff EV on river (general formula)
For a one‑street situation where a player with a pure bluff (zero equity when called) considers betting into a pot, the EV of bluffing is linear in opponent’s calling frequency and the pot/bet sizes. This underlies both MDF and exploitative deviations.

**Formel:** Let:
- P = current pot
- b = bet size (risk of bluffer, and call amount for caller)
- x = P(opponent calls | facing bet)

Then the EV of a pure bluff is:
EV_bluff = x * (-b) + (1 - x) * P

Thresholds:
- EV_bluff > 0 if x < P / (P + b)
- EV_bluff = 0 if x = P / (P + b)
- EV_bluff < 0 if x > P / (P + b)

Derivative w.r.t. x:
∂EV_bluff/∂x = -b - P < 0
So EV is strictly decreasing in opponent’s call rate.

**Für den Bot:** Your bluffing module should evaluate EV_bluff for each candidate bluff combo using the current estimate of villain’s calling frequency. Against over‑folders (x < MDF) widen bluffing; against calling stations (x > MDF) prune pure bluffs almost entirely and favor value‑heavy betting.

## Caller EV vs polarized range (general river call decision)
On the river versus a polarized bet (value or bluff) where your hand has no showdown equity versus villain’s value and never loses to villain’s bluffs, your call EV depends only on villain’s bluff frequency and the pot/bet sizes. This is the standard ‘pot odds vs bluff frequency’ decision.

**Formel:** Let:
- P = pot before bet
- b = bet size
- q = P(villain has value | villain bets)
- (1 - q) = P(villain is bluffing | villain bets)

If hero’s hand always loses vs villain’s value and always wins vs villain’s bluffs:
EV_call = q * (-b) + (1 - q) * (P + b)
EV_fold = 0

Call if EV_call > 0:
q * (-b) + (1 - q) * (P + b) > 0
=> (1 - q) * (P + b) > q * b
=> (P + b) - q*(P + b) > q*b
=> (P + b) > q*(P + b + b)
=> q < (P + b) / (P + 2b)

Equivalently, in terms of bluffing frequency B = 1 - q:
EV_call > 0 ⇔ B > b / (P + 2b)

In the specific example, hero’s range is so strong that his hand essentially dominates all of villain’s non‑flush bet hands; they then reformulate in terms of bluffing frequency y among misses, but the core math is the same: call if villain bluffs often enough relative to pot odds.

**Für den Bot:** When facing a river bet and your hand is purely a bluff‑catcher versus a polarized range, compute the minimum bluff frequency needed for a profitable call: B* = b / (P + 2b). If your estimate of villain’s bluffing exceeds this, call; otherwise fold. This should be explicitly coded into your river decision logic, using opponent model outputs for bluffing frequency.

## Exploitative best responses vs off‑equilibrium bluff/call frequencies
Given the linear EV forms, the best responses to opponent deviations are bang‑bang strategies: call 100% or 0% with your marginal hands; bluff 100% or 0% with your miss hands. The slopes of the EV functions dictate that partial adjustments are dominated by extremes when villain is clearly off the indifference point.

**Formel:** Using the EV functions from the excerpt:

1) A’s EV from calling vs B’s bluffing frequency y:
EV_A_call = 735*y - 16 (with P = 655, b = 80, q = 0.2)
- EV_A_call increases linearly in y
- Breakeven at y* = 16 / 735 ≈ 2.2%

Exploitative rule:
- If y > y*, best response is x = 1 (call always with this hand class)
- If y < y*, best response is x = 0 (fold always)

2) B’s EV from bluffing vs A’s calling frequency x:
EV_B_bluff = 655 - 735*x
- EV_B_bluff decreases linearly in x
- Breakeven at x* = 655 / 735 ≈ 89.1%

Exploitative rule:
- If x < x*, best response is y = 1 (bluff all misses)
- If x > x*, best response is y = 0 (never bluff)

These are direct consequences of linearity and the absence of internal maxima; only boundaries x ∈ {0,1}, y ∈ {0,1} can be strict best responses away from the indifference point.

**Für den Bot:** Your exploitative layer should use these linear EV properties: if opponent’s estimated bluff rate is clearly above the indifference threshold, respond by calling with all hands at the margin (not just a little more often); if clearly below, over‑fold these hands. Likewise, if opponent clearly over‑folds below MDF, you should bluff all profitable candidates; if they over‑call, drastically restrict pure bluffs.

## Pot odds and multi‑street EV integration (conceptual model)
Across streets, the EV of a line (e.g., calling a draw) must consider cumulative cost and future implied bets, not just current street pot odds. The excerpt re‑emphasizes that pot odds must be computed over the entire line (all remaining streets) and that implied odds (future winnings when hitting) adjust effective equity.

**Formel:** Single‑street pot odds threshold for a drawing call:
Let:
- P = pot before call
- c = cost to call
- E = equity vs villain’s range conditional on call

Single‑street call EV:
EV_call = E * (P + c) - (1 - E) * c
Call if EV_call > 0:
E * (P + c) > c
=> E > c / (P + c)

Multi‑street integration for a drawing line (conceptual):
Let:
- C_total = sum of future call costs you commit to on this line
- W_hit = expectation when you hit (including implied future bets)
- W_miss = expectation when you miss (often 0 if you fold, or negative if you continue bluffing/etc.)
- p_hit = probability you complete the draw by showdown (accounting for all remaining cards)

Then line EV:
EV_line = -C_total + p_hit * W_hit + (1 - p_hit) * W_miss

Implied odds effectively increase W_hit; reverse implied odds reduce it.

**Für den Bot:** Flop/turn calling logic must evaluate the entire line EV, not just immediate pot odds. Use multi‑street simulations or rollout approximations: compute p_hit over remaining cards, model expected future bets (implied odds), and decide calls/folds/raises based on total EV_line rather than per‑street thresholds.

## Bayesian hand‑reading model (distributional, not single hand)
Opponent modeling is inherently Bayesian: assign a prior distribution over opponent’s hands, update it via Bayes’ theorem using observed betting actions, board runouts, and possible physical tells. Never collapse to a single guessed hand; keep a distribution and compute EV vs that distribution.

**Formel:** Let H denote the random variable for opponent’s hand, A for observed action (e.g., bet, call, raise), and T for any tell.

1) Initial prior over hands (preflop or on street t):
P(H = h) ∝ combinatorial count(h) * adjustments(card_removal, position, known tendencies)

2) Bayesian update on action A = a:
P(H = h | A = a) = [P(A = a | H = h) * P(H = h)] / Σ_{h'} P(A = a | H = h') * P(H = h')

3) Incorporating an additional tell T = t:
P(H = h | A = a, T = t) ∝ P(T = t | H = h, A = a) * P(H = h | A = a)

4) Decision EV for an action d (e.g. call, fold, raise):
EV(d) = Σ_{h} P(H = h | info) * payoff(d, h)

Here P(A = a | H = h) is your strategy model for villain (how often they take action a with each hand), and P(T = t | H = h, A = a) is the tell model. Both are subjective but can be estimated or learned.

**Für den Bot:** Your opponent model should maintain distributions over ranges (possibly at bucket level) and update them via Bayes’ rule with each action rather than collapsing to a single ‘put him on AK’ guess. All EV computations for betting, calling, and raising should integrate over this posterior distribution.

## Jam‑or‑fold preflop model via distribution vs range (satellite example setup)
All‑in preflop decisions in shallow‑stack situations (satellites, push/fold) should be solved by comparing hero’s equity versus the opponent’s shoving distribution, not versus a single hand. Even though the excerpt does not derive formulas, the structure is the standard push/fold EV computation.

**Formel:** Let:
- S = effective stack (both players have at most S)
- pot0 = pot before shove (blinds/antes)
- R = opponent’s shoving range
- h = hero’s hand
- E = equity(h vs R) when all‑in is called

If villain shoves and hero is last to act with no fold equity (jam‑or‑fold vs shove):
- If hero folds: EV_fold = 0 relative to current pot0 (or −blind if you want absolute EV before hand)
- If hero calls:
    * At risk: S - existing committed chips (here ignored for simplicity)
    * Total pot when called: pot0 + 2S
    * Hero’s net when he wins: + (pot0 + S) (wins villain’s S plus pot0, minus his own committed S)
    * Hero’s net when he loses: -S

So calling EV (relative to folding) is:
EV_call = E * (pot0 + S) - (1 - E) * S

Threshold equity for breakeven call:
Set EV_call = 0:
E * (pot0 + S) = (1 - E) * S
=> E*(pot0 + S + S) = S
=> E = S / (pot0 + 2S)

Hero should call if E > S / (pot0 + 2S).

In practice, E is computed as:
E = Σ_{r in R} P(r | R) * equity(h vs r)


**Für den Bot:** In push‑fold preflop spots, your decisions should be based on equity vs the opponent’s shoving range, not on ‘putting them on AK’. For each candidate call, compute E(h vs R) and compare to the threshold E* = S/(pot0 + 2S); call if above, fold otherwise. This is the correct mathematical model for the satellite example described.

## Bayesian update for tells and hand strength
Use Bayes’ theorem to update the probability of a hidden event (e.g., villain is bluffing / has strong hand) after observing a tell or action.

**Formel:** Let A = event of interest (e.g., bluff), T = observed tell.
Bayes’ theorem:
P(A|T) = P(T|A) * P(A) / P(T)

Total probability of T:
P(T) = P(T ∧ A) + P(T ∧ ¬A)
     = P(T|A) * P(A) + P(T|¬A) * P(¬A)

So explicitly:
P(A|T) = [P(T|A) * P(A)] / [P(T|A) * P(A) + P(T|¬A) * (1 - P(A))]

False-positive rate for the tell relative to A:
FP = P(T ∧ ¬A) = P(T|¬A) * (1 - P(A)).

**Für den Bot:** Treat live tells, timing, and unusual bet patterns as Bayesian evidence on top of a range-based prior: maintain P(bluff) or P(strong) and update using explicit likelihoods P(tell|bluff), P(tell|value), rather than making binary reads. Value comes from tells with very low P(tell|¬A) (few false positives).

## Bayesian inversion for generic hand-reading
General conditional probability relationships for inverting from ‘how a hand produces an action’ to ‘how likely a hand is given that action’.

**Formel:** Core identities from the excerpt (using A for event, T for tell/action):
1) By Bayes:
   P(T|A) = P(A ∧ T) / P(A)

2) Using product rule:
   P(A ∧ T) = P(T) * P(A|T)
   so P(T|A) = [P(T) * P(A|T)] / P(A)

3) Bayes in the more useful direction:
   P(A|T) = P(A ∧ T) / P(T)
          = [P(T|A) * P(A)] / P(T)

4) Event decomposition for T:
   P(T) = P(A ∧ T) + P(¬A ∧ T)
        = P(T|A) * P(A) + P(T|¬A) * P(¬A).

**Für den Bot:** When hand-reading from observed actions (bets, raises, calls) or simple timing tells, always think in terms of P(range segment | action) ∝ P(action | segment) * P(segment). Any exploit logic should explicitly model these conditionals instead of hard-coding point reads.

## Exploitative EV vs. a distribution, not a single hand
Expected value is taken over villain’s entire posterior hand distribution and strategy distribution, not over a ‘guessed hand’.

**Formel:** Let H be set of villain hands, S be set of villain strategies.
Our action a has EV:
EV(a) = Σ_{h∈H} Σ_{s∈S} P(h, s | info) * EV(a | h, s)
     = Σ_{h} P(h | info) * [ Σ_{s} P(s | h, info) * EV(a | h, s) ]

Where P(h|info) is the posterior hand distribution after all observed streets and actions.

**Für den Bot:** Do not collapse reads into a single ‘most likely hand.’ Maintain and update a weighted range and (optionally) a mixture over opponent strategy types; compute EV of candidate lines against that distribution. This is the foundation of sound exploit algorithms and counter-exploit adjustments.

## Range refinement via betting patterns (Bayesian filtering)
Each action/street update multiplies prior hand weights by likelihoods of that action with that hand, renormalizing to get a new posterior range.

**Formel:** Discrete hand space H. Start with prior P_0(h).
After observing action sequence O = (o1, o2, ..., ok):
Recursive update for step i:
P_i(h) ∝ P(o_i | h, history) * P_{i-1}(h)
with normalization:
P_i(h) = [P(o_i | h, history) * P_{i-1}(h)] / Z_i
Z_i = Σ_{h∈H} P(o_i | h, history) * P_{i-1}(h)

Final range after k observations: P_k(h) = P(h | o1,...,ok).

**Für den Bot:** Treat each street’s action as a multiplicative filter on villain’s range (prior * likelihood → posterior). The stud example shows how specific board runouts and actions can nearly eliminate whole hand classes; encode similar filtering for NLHE (e.g., certain lines almost rule out no-club holdings on flush-completing turns).

## Combinatorial range construction and weighting
Use combinatorics to enumerate and weight hand categories consistent with the cards seen and pre-street constraints.

**Formel:** If C is a category (e.g., ‘QQ with a club’), and n_C is the count of distinct combo in C given card-removal:
Baseline weight w_C ∝ n_C.
Normalized category probability:
P(C) = n_C / Σ_{D} n_D

If actions have been taken, combine with action likelihoods:
Posterior P(C | actions) ∝ n_C * P(actions | C).

Example structure from the excerpt (stud hand):
AA: 1 combo (forced A♣X)
Q♣Qx: 3 combos
QxQy(no club): 3 combos
J♣Jx: 2 combos
JxJy(no club): 1 combo
X♣Y♣ (low club draws): 6 combos

**Für den Bot:** Base villain’s range weights on exact combinatorics (how many combos of each class remain) before any exploit weighting. Card removal (visible cards, known dead cards) can significantly skew category frequencies; exploit lines that become +EV purely from this combinatorial bias.

## False-positive rate and value of a tell
The strength of a tell is controlled by how rarely it appears when the associated event is NOT true; i.e., its false-positive probability.

**Formel:** Given tell T and event A (e.g., bluff):
False-positive probability for T w.r.t. A:
FP = P(T ∧ ¬A) = P(T|¬A) * P(¬A).

Posterior:
P(A|T) = [P(T|A) * P(A)] / [P(T|A) * P(A) + P(T|¬A) * (1 - P(A))].

As P(T|¬A) → 0, P(A|T) → 1 (for fixed P(A), P(T|A) > 0).

As P(T|A) ≈ P(T|¬A), T carries little information:
P(A|T) ≈ P(A).

**Für den Bot:** When using any side-channel (timing, sizing anomaly, physical tell), estimate not just ‘how often does this happen when bluffing?’ but especially ‘how often does this happen when NOT bluffing?’ Focus exploit logic on signals with very low P(signal|value), not noisy ones that occur in all hand classes.

## Sample-size limits on inferred frequencies
Observed action frequencies over realistic sample sizes yield wide confidence intervals on underlying strategy parameters (like preflop VPIP/PFR); so reads based on small n are weak.

**Formel:** Approximate 95% confidence interval for a Bernoulli proportion p estimated by \hat{p} from n trials:
\hat{p} ± 1.96 * sqrt( \hat{p} * (1 - \hat{p}) / n )

Example from text: n ≈ 121 hands UTG, observed raise frequency \hat{p} = 0.10.
Then roughly p ∈ [0.04, 0.16] at 95% confidence, which supports very different opening ranges.

**Für den Bot:** When learning opponent parameters online (e.g., 3-bet%, c-bet%), integrate variance-aware estimates or Bayesian priors; do not overfit to small samples. Use wide priors and conservative adaptation until counts per node (position, street, texture) are large.

## Strategy-reading via player-type mixtures
Instead of trying to fully infer a unique fixed strategy, maintain a distribution over a few canonical strategy types (e.g., nit, TAG, LAG, maniac) and mix over them.

**Formel:** Let types k ∈ {1,...,K} with prior P(type=k). Each type has its own policy π_k and induced action likelihoods.
Given observed data D (hands, actions, showdowns):
Posterior over types:
P(type=k | D) ∝ P(D | type=k) * P(type=k).

Our decision EV for action a:
EV(a) = Σ_k P(type=k | D) * EV(a | type=k).


**Für den Bot:** Model each opponent as a mixture over a small library of parametric strategies and update the mixture weights with Bayesian evidence from observed actions. Choose lines based on the posterior mixture rather than a single guessed profile; this stabilizes exploit decisions against limited data and opponent adaptation.

## Bayesian read from a rare showdown event
Use Bayes’ theorem to update a prior model of villain’s range/strategy when you see a specific hand at showdown after an unusual line (e.g., raise only once in 100 hands and show AA).

**Formel:** Posterior over strategies s given observed hand h and action a:

P(s | h, a) = [ P(h, a | s) * P(s) ] / Σ_{s'} [ P(h, a | s') * P(s') ]

If we lump strategies into two coarse types, e.g. Tight (T) and Loose (L):

P(T | h, a) = [ P(a | T) * P(h | a, T) * P(T) ] /
             ( P(a | T) * P(h | a, T) * P(T) + P(a | L) * P(h | a, L) * P(L) )

**Für den Bot:** When a player shows an extremely strong hand after very few aggressive actions (e.g., 1 raise in 100 hands -> AA), sharply shift their preflop raising range toward nutted hands using a Bayesian update rather than treating one sample as noise.

## Bayesian value of a tell (frequency × reliability)
A tell (physical or timing/betting pattern) is only useful in proportion to how often it occurs and how diagnostic it is; false positives reduce its EV. Model this as likelihood ratios in Bayes’ theorem.

**Formel:** Let T be the event that a tell is observed, S a strong hand, W a weak hand.

Likelihood ratio (LR):
LR = P(T | S) / P(T | W)

Posterior odds of strong vs weak given the tell:

Odds(S:W | T) = Odds(S:W) * LR

where
Odds(S:W) = P(S)/P(W),
P(S | T)   = Odds(S:W | T) / (1 + Odds(S:W | T)).

**Für den Bot:** Treat any feature (timing, bet size pattern, stat) as a noisy signal; compute or approximate its likelihood ratio vs strong/weak ranges. Ignore low-LR signals instead of overreacting to single noisy events.

## Unbiased vs biased observation sets
You only see a subset of villain’s hands (those that reach showdown or that you’re dealt into), which biases estimates of their global winrate and some frequencies. Only your own hand history is structurally unbiased.

**Formel:** If W_field is villain’s true winrate vs the whole pool, and W_vs_you is villain’s winrate in hands where you are present, then typically

E[W_vs_you] ≤ E[W_field]

because your sample is conditional on you choosing to play:

P(hand in sample) = P(you seated, you don’t sit out, table/game selection, etc.)

so estimates:

\hat{W}_vs_you ≈ (1/N) Σ_{i=1}^N outcome_i

have selection bias relative to W_field.

**Für den Bot:** When estimating opponent quality from your database, treat it as a conditional sample (biased toward lineups and spots you choose). For accurate global stats, rely primarily on your own data; use opponent aggregates cautiously as relative rather than absolute measures.

## Sampling error of estimated winrate (confidence interval)
Model per-hand outcome as an i.i.d. random variable with variance σ². Then the sample mean over N hands has standard deviation σ/√N. This gives confidence intervals for winrate or any frequency (e.g., VPIP).

**Formel:** Per-hand winrate X has mean μ and variance σ².
Sample mean over N hands:

\bar{X}_N = (1/N) Σ_{i=1}^N X_i

Var(\bar{X}_N) = σ² / N
SD(\bar{X}_N) = σ / √N

Approximate 95% confidence interval:

CI_95 ≈ μ̂ ± 1.96 * (σ / √N)

Example from text:
σ² = 4 BB²/hand² → σ = 2 BB/hand.
For target precision ε = 0.01 BB/hand (width ≈ 0.02), need

1.96 * (2 / √N) ≈ 0.01  ⇒  N ≈ (1.96 * 2 / 0.01)².

Text’s worked example: set 2 / √N = 0.005  ⇒  N = (2 / 0.005)² = 160,000.

**Für den Bot:** Treat any stat (your bb/100, villain’s VPIP, etc.) as a noisy estimate: its standard error is σ/√N. Require large N or tolerate wide intervals; don’t overfit opponent models on a few hundred hands when variance is high.

## Scaling variance with sample size (per-hand vs over N hands)
If per-hand standard deviation is σ, the standard deviation of the total result over N hands is σ√N; the standard deviation of the per-hand mean is σ/√N. The same scaling applies to per-hour metrics when you know hands/hour.

**Formel:** Per-hand result X has Var(X) = σ².

Total over N hands: S_N = Σ_{i=1}^N X_i
Var(S_N) = N σ²
SD(S_N) = σ √N

Sample mean: \bar{X}_N = S_N / N
Var(\bar{X}_N) = σ² / N
SD(\bar{X}_N) = σ / √N

If you measure per hour with h hands/hour, then per-hour SD is:

σ_hour = σ * √h.

**Für den Bot:** When evaluating risk/variance or bankroll requirements, convert between per-hand and per-hour or per-session variance using the √N rule instead of ad hoc guesses.

## Sample size needed for given precision (general form)
Rearranging σ/√N = desired standard error gives N as a function of variance and target confidence interval width.

**Formel:** Desired half-width of 95% CI on mean: w.

We want:
1.96 * (σ / √N) = w

Solve for N:
N = (1.96 * σ / w)².

Equivalently, for generic z-level:
N = (z * σ / w)².

**Für den Bot:** For any statistic the bot tracks (e.g., c-bet frequency by node), explicitly compute how many samples are needed before trusting it within ±w; otherwise fall back to priors or population averages.

## Interpreting VPIP and similar one-number stats (context dependence)
Global frequencies like VPIP conflate very different contexts (heads-up vs full-ring, positions, blind vs non-blind). One raw proportion is a mixture over multiple conditional distributions.

**Formel:** Let C be context (position, players, stakes, etc.). A global stat like VPIP is:

VPIP_global = P(V = 1) = Σ_c P(V = 1 | C = c) * P(C = c).

Different mixes of C give same VPIP_global with very different conditional strategies.
Therefore to compare two players A,B fairly:

P_A(V = 1 | C = c) vs P_B(V = 1 | C = c)

rather than just VPIP_global.

**Für den Bot:** Maintain context-conditioned stats (e.g., open-raise frequency by seat and players left) instead of relying on one aggregated VPIP; otherwise the opponent model will misclassify players who mix short-handed/full-ring or play many blinds.

## Contextual street-frequency statistics
Raw frequencies like “% bet turn” are nearly meaningless without conditioning on prior actions and ranges. Correct modeling requires conditioning on path-dependent context: preflop line, flop line, board, and distribution strength.

**Formel:** A naive stat:

Freq_bet_turn_naive = P(B_turn = 1).

Useful stat should condition on context H (hand history prefix):

Freq_bet_turn(H) = P(B_turn = 1 | H)

where H could include:
- number of players seeing turn
- position (IP/OOP)
- flop action sequence (c-bet, x/c, x/r, etc.)
- pot size
- board texture cluster

We approximate by clustering H into a finite set {H_k} and estimating:

P(B_turn = 1 | H_k) ≈ (# times bet on turn in H_k) / (# times reached H_k).

**Für den Bot:** Design the opponent model so that turn/river betting frequencies are stored per node or coarse cluster of similar nodes (line, position, players, board type), not as a single global street frequency.

## Own-play data as the primary unbiased sample
You observe 100% of your own decisions and outcomes, independent of selection by other players. This makes your own hand history the only structurally unbiased sample for deep statistical analysis.

**Formel:** For your own hands, you observe all decisions and outcomes (modulo site bugs), so for any event E (e.g., “3-bet bluff SB vs BTN open”):

P̂(E) = (# times E occurred for you) / (total opportunities for E).

No positional or lineup conditioning on someone else’s table selection biases which of your hands are recorded; all hands you actually played are in sample.

**Für den Bot:** Focus the heaviest statistical optimization and leak-finding on the bot’s own play, where sample coverage is complete; treat opponent stats as lighter-weight and more approximate.

## Volume advantage of multi-tabling (hands per hour vs convergence)
Because estimation error decays as 1/√N, increasing hands/hour by a factor k reduces the time to reach a given statistical precision by the same factor k.

**Formel:** Needed hands N* for target precision is fixed by variance and desired CI.

Time_brick = N* / H_brick
Time_online = N* / H_online

If H_online ≈ k * H_brick ⇒ Time_online ≈ Time_brick / k.

Example from text:
Brick: ~35 hands/hour, 2000 hrs/year ⇒ ~70,000 hands/year.
Online: ~350 hands/hour, 2000 hrs/year ⇒ ~700,000 hands/year.

For N* = 160,000 hands:
Time_brick ≈ 160,000 / 35 ≈ 4,571 hours (~2.3 years at 2000 hrs/year).
Time_online ≈ 160,000 / 350 ≈ 457 hours (~0.23 years = ~3 months).

**Für den Bot:** Exploit the bot’s ability to play very high volume: quickly converge its own strategy estimates and EV baselines by aggregating millions of hands, and schedule periodic strategy re-optimization on this growing dataset.

## EV computation vs a known distribution using face-up analysis
To choose an action given a range model, compute the EV of each line against each hand in villain’s distribution (as if cards were face-up), then take the expectation over the distribution.

**Formel:** Let H be villain’s hand random variable with distribution P(H = h). For an action a (which can encode a multi-branch plan, e.g. bet/fold, check/raise), define EV(a | h) as the EV against specific hand h with perfect knowledge.

Then EV of a against the modeled range:

EV(a) = Σ_h P(H = h) * EV(a | h).

Optimal action:

a* ∈ argmax_a EV(a).

In practice we approximate the sum by integration over hand-strength buckets or Monte Carlo sampling.

**Für den Bot:** Design each decision node as a face-up EV calculation vs a modeled discrete or bucketed range, then choose the line (bet/fold, bet/call, check/raise, etc.) with highest expectation over that range.

## Action abstraction on a street (plan-based options)
Instead of only primitive actions (bet/check), model options as contingent plans for the street, like bet-call, bet-fold, check-call, check-raise. EV of each plan includes downstream reactions on that same street.

**Formel:** Let A_street be a set of contingent plans, e.g.:
- a1 = check-fold
- a2 = check-call
- a3 = check-raise
- a4 = bet-call
- a5 = bet-fold

For each plan a ∈ A_street and each villain hand h, define:

EV(a | h) = Σ_{action sequences consistent with a} P(sequence | h, a) * payoff(sequence, h).

Then as before:
EV(a) = Σ_h P(H = h) * EV(a | h).

Optimal street plan:

a*_street ∈ argmax_{a ∈ A_street} EV(a).

**Für den Bot:** In the tree representation, store and optimize over plan-type actions (bet/fold, bet/call, etc.) at each node instead of treating follow-up choices as separate uncoordinated decisions; this captures correct dependencies in EV computations on a street.

## Single-street bet-call EV vs draw (general form)
EV of betting and calling a raise when villain can no longer put in more money and has known draw equity.

**Formel:** Given:
- P: current pot
- C: effective remaining stack (per player) going in on this street after bet/raise
- q: villain's probability of making the winning draw by showdown

If hero (made hand) bets and calls the raise so that total additional money he invests on this street is C, and no further betting occurs:

p_hero_wins = 1 - q
EV_hero_bet_call = (1 - q) * (P + 2C) - C

**Für den Bot:** When stacks are such that calling a raise ends the betting, compare EV_bet_call to EV_bet_fold / check-lines using the simple formula EV = (1−q)(P+2C)−C; this is the base model for jam-or-fold decisions versus known draw equity.

## Multi-street draw probability decomposition
Computing total draw completion probability over multiple streets using conditional structure.

**Formel:** For a draw that can complete on turn (6th street) or river (7th street):

Let:
- a = p(draw completes on turn)
- b = p(draw completes on river | missed turn)

Total probability draw completes by river:

q = a + (1 - a) * b

Hero win probability when hero cannot improve:

p_hero_wins = 1 - q

Example from text:
- a = 8/42
- b = 8/41

=> q = 8/42 + (34/42)*(8/41)
=> p_hero_wins = 1 - q ≈ 0.6516

**Für den Bot:** For situations where stacks force all-in over two streets, compute villain’s total draw equity as q = a + (1−a)b instead of per-street; this q then feeds directly into jam-or-call EV formulas.

## Comparing bet-call vs bet-fold vs check-fold lines (dominated action elimination)
Static elimination of dominated lines when later-street play is fixed/irrelevant to comparison.

**Formel:** If two strategies differ only in a branch where villain raises and no further betting occurs later, their EV difference is determined solely by that branch:

Let:
- EV_s1_raise_branch: EV of strategy 1 in the raise branch
- EV_s2_raise_branch: EV of strategy 2 in the raise branch

If all other branches have identical EV under the two strategies, then:

EV_s1 - EV_s2 = EV_s1_raise_branch - EV_s2_raise_branch

Hence if EV_bet_call_raise_branch > EV_bet_fold_raise_branch, bet-fold is strictly dominated by bet-call.

**Für den Bot:** When only one subtree differs between two candidate lines (e.g., how you respond to a raise), you can compare them by evaluating only that subtree; lines like bet-fold with large equity share vs a capped draw will often be dominated by bet-call.

## EV of check-call / check-raise when villain checks back with whole range
When villain’s assumed strategy after a check is always check-back, your intended follow-up (call vs check-raise) never occurs, making the EV of multiple check-based lines identical.

**Formel:** If:
- After hero checks, villain checks back with probability 1.
- On future streets, play is the same regardless of whether hero intended check-call or check-raise.

Then:

EV_check_call = EV_check_raise

Example from text:
EV_check_call ≈ 290.24
EV_check_raise ≈ 290.24

**Für den Bot:** If opponent never stabs when checked to, your internal plan to check-raise vs check-call is irrelevant; the EV is governed by their check-back, so allocate this state entirely to a single line in your strategy rather than randomizing.

## Rigid pot-limit jam-or-call EV (made hand vs draw, flop all-in)
All-in EV on flop when stacks are ≤ pot so that a single bet gets stacks in; used to characterize small-stack play.

**Formel:** Given:
- P0: initial pot on flop
- S: effective stack (≤ P0 in the rigid examples, but formula general)
- q: villain’s equity if all-in now (probability villain wins by showdown)

If all money goes in on flop regardless of who initiates:

p_hero_wins = 1 - q
Total pot when all-in: P_allin = P0 + 2S
Hero’s net EV (from his current perspective, counting his future investment as cost):

EV_allin_flop = (1 - q) * P_allin - S

Example from text (X vs 87s, S = 50, P0 = 100, q = 0.5606):
P_allin = 200
EV_X = (1 - 0.5606)*200 - 50 = 0.4394*200 - 50 = 37.88

**Für den Bot:** When stacks are short and betting is effectively jam-or-call, treat any flop bet as leading to an all-in and use EV_allin_flop to decide whether to push your equity edge now or try to delay action.

## Turn bet EV after flop checks (rigid pot-limit, one bet left)
EV of betting turn after flop goes check-check, with villain having had a draw that must call on turn due to pot odds.

**Formel:** In the toy model:
- p_miss_flop = probability villain missed on flop
- p_miss_turn_given_miss_flop = probability villain misses turn given miss on flop
- P_turn: pot at turn when bet goes in
- B: pot-sized bet on turn

EV_turn_bet = p_miss_flop * [ p_miss_turn_given_miss_flop * (P_turn + B) - B ]

From text (case 1, small stacks):
- p_miss_flop = 30/45
- p_miss_turn_given_miss_flop = 29/44
- P_turn = 100 (no flop betting)
- B = 50

EV = (30/45) * [ (29/44)*200 - 50 ] = 54.55

**Für den Bot:** When villain’s flop checking range is draw-heavy and must call a turn pot bet with insufficient equity, checking flop to preserve a bet for the turn can increase EV vs auto-stacking on the flop.

## EV decomposition with conditional subcases
Breaking a multi-street decision into subcases based on how many pot-sized bets go in on a given street, to deduce dominance properties (e.g., who wants second bet in).

**Formel:** Let EV_X(k) be X’s EV in subcase where exactly k pot-sized bets go in on flop (k ∈ {0,1,2,3} in rigid PL with 3-bet depth). Example (deep stacks S ≈ 3P):

Subcase a) k=0: EV_X(0) = 65.15
Subcase b) k=1: EV_X(1) = 95.45
Subcase c) k=2: EV_X(2) = 346.21
Subcase d) k=3: EV_X(3) = -113.62

Logical rules derived by comparing EVs in these subcases:
1) X never puts in the second bet on flop because if he does, Y can make it k=3, his worst case.
2) Y never puts in the second bet because if he does, X can call to get k=2, Y’s worst case.
3) X prefers k=1 to k=0.
4) Y prefers k=0 to k=1.

Equilibrium: both players avoid putting in the second bet; X uses his option to put in the first bet; Y calls.

**Für den Bot:** In deep or semi-deep spots, reason in terms of how many large bets can go in and which player benefits from additional bets; often you and villain will both strategically avoid committing a ‘second pot-sized bet’ on a street.

## EV table as payoff matrix for flop actions (medium stacks)
Mapping action pairs (hero action, villain action) to EVs to infer best responses and equilibrium behavior.

**Formel:** From the medium-stack rigid pot-limit case (S=400, P0=100), X’s EV matrix:

              Y action
           Check    Bet     Call    Raise    Fold
X Bet     95.45   -4.55   95.45   -4.55   100
X Check   65.15   65.15    —       —       —
Check-raise 65.15 -4.55    —       —       —
Check-call 65.15 95.45    —       —       —

Interpretation:
- If X bets, Y’s best is raise (−4.55 for X) vs call (95.45 for X) or fold (100 for X).
- If X checks, Y’s best is bet (95.45 for X) or check (65.15 for X); X’s best vs Y bet is call.
- Given best responses, X’s worst outcome when checking is 65.15, better than his −4.55 worst when betting.

Therefore optimal play: check-check on flop.

**Für den Bot:** Treat flop as a small two-player normal-form game between your action and villain’s response; use EV tables to identify that in some stack-size regimes, optimal is mutual checking despite large equities in play.

## Subcase EV with two flop bets then turn jam (deep stacks)
EV when two pot-sized bets go in on flop with deep stacks leaving a large turn pot and one jam left.

**Formel:** From subcase c) in deep stacks (S=1300, P0=100): two pot-sized bets (total 400 per player) go in on flop.

Given:
- p_hit_turn = 15/45 (villain completes on turn)
- p_miss_turn = 30/45
- Conditional equity on river when turn misses: hero wins with 29/44, villain with 15/44
- Pot after flop action and turn pot bet/call: 2700
- Hero total future net if wins: +500; if loses after miss: −1300; if villain hits on turn: −400

EV_X(2 bets on flop):
EV = (15/45)(-400) + (30/45)[ (29/44)(+500) - (15/44)(+400) ]
   = (15/45)(-400) + (30/45)*193.18
   = 346.21

**Für den Bot:** In deep stacks, allowing multiple bets in early with a strong overpair can be hugely +EV because you preserve large future bets when the draw misses; your flop sizing and willingness to face raises should be calibrated to keep that profitable structure.

## Constructing EV(x): flop investment as a continuous variable (two-bet depth)
Express hero’s EV as a function of total per-player money x that goes in on flop, assuming deterministic optimal play on turn given hit/miss. Then study EV(x) piecewise to find optimal bet sizing and villain’s raising thresholds.

**Formel:** Let:
- x: total amount each player invests on flop, 0 ≤ x ≤ 400
- P0 = 100: initial pot
- Draw structure with 15 outs, modeled as:
  * p_hit_turn = 15/45
  * p_hit_river_given_miss_turn = 15/44

Case 1: 0 ≤ x ≤ 100 (enough stack left to pot turn).
- Pot on turn after flop contributions: P_turn = 2x + 100
- On turn if draw missed, hero bets pot and villain calls.

Outcomes and payoffs (hero viewpoint):
1) Villain wins on turn: prob 15/45, hero net −x
2) Villain wins on river after miss turn: prob (30/45)(15/44), hero net −x − (2x+100)
3) Hero wins: prob 1 − 15/45 − (30/45)(15/44), hero net 3x + 200

Computing:
EV_X(x) = (15/45)(-x)
         + (30/45)(15/44)(-3x - 100)
         + (1 − 15/45 − (30/45)(15/44))(3x + 200)
       = (10/33)x + 65.15

Case 2: 100 ≤ x ≤ 400 (cannot pot turn fully; at most 400 total goes in):
- If villain misses turn, all remaining money goes in on turn; payoffs capped at ±400/500.

Outcomes/payoffs:
1) Villain wins on turn (15/45): hero net −x
2) Villain wins on river given miss (30/45)(15/44): hero net −400
3) Hero wins otherwise: hero net +500

EV_X(x) = (15/45)(-x) + (30/45)(15/44)(-400) + (1 − 15/45 − (30/45)(15/44)) * 500
         = −x/3 + 128.79

So piecewise:
For x in [0, 100]:   EV_X(x) = (10/33) * x + 65.15
For x in [100, 400]: EV_X(x) = −(1/3) * x + 128.79

**Für den Bot:** On boards where future play is essentially forced (draw hits: no betting; miss: pot or jam), you can analytically express EV as a function of flop investment, see where EV increases or decreases, and thereby understand optimal bet sizes and where villain should or should not raise.

## Villain’s raise-size optimization threshold
Given hero’s EV(x) function, villain will choose the raise size that moves x into the region which minimizes hero’s EV; hero chooses a bet size so that villain is indifferent between calling and raising to that minimizing region.

**Formel:** Given EV_X(x) piecewise as in Example 7.3:

For x in [0,100]:      EV_X(x) = (10/33)x + 65.15   (increasing in x)
For x in [100,400]:    EV_X(x) = −(1/3)x + 128.79   (decreasing in x)

Suppose hero bets b, villain can:
- Call: sets x = b
- Raise pot: sets x' = 3b + 100 (since pot raise effectively triples hero’s bet plus initial pot contribution in rigid PL structure for this model)

Hero wants to pick b such that villain is indifferent:

EV_X(b) = EV_X(3b + 100)

We are in regime where b ∈ [0,100] and 3b + 100 ∈ [100,400]. So:

(10/33) * b + 65.15 = −(1/3) * (3b + 100) + 128.79
(10/33)b + 65.15 = −b − 100/3 + 128.79
(10/33 + 1)b = 30.30
(43/33)b = 30.30
b = (30.30) * (33/43) ≈ 23.26

At this b:
EV_X ≈ (10/33)*23.26 + 65.15 ≈ 72.20

This is hero’s guaranteed EV regardless of villain’s choice (call or pot raise).

**Für den Bot:** On draw-heavy boards, optimal flop sizing often comes from making villain indifferent between calling and raising; solving EV_x(call) = EV_x(raise) yields a concrete optimal bet that maximizes your worst-case EV vs a strong opponent.

## Linear EV sensitivity to flop investment for small x
For small x (0 ≤ x ≤ 100) in Example 7.3, hero’s EV increases linearly with x with slope 10/33, quantifying the marginal value of investing more on the flop given future pot geometry.

**Formel:** For x ∈ [0,100]:
EV_X(x) = (10/33) * x + 65.15

So marginal EV gain per flop dollar is:

d(EV_X)/dx = 10/33 ≈ 0.303

i.e., each $1 invested on flop yields ≈ $0.30 increase in EV within this interval.

**Für den Bot:** When future streets are favorable for you (villain forced into bad turn calls if they miss), small flop bets can be very profitable: raising the pot a bit increases your EV at a fixed rate until you hit the region where allowing villain to jam becomes too good for them.

## Linear EV sensitivity to flop investment for large x
For x between 100 and 400 in Example 7.3, hero’s EV decreases linearly with more flop money due to allowing villain to realize too much equity when stacks are too shallow on the turn.

**Formel:** For x ∈ [100,400]:
EV_X(x) = −(1/3) * x + 128.79

So marginal EV change per additional flop dollar is:

d(EV_X)/dx = −1/3 ≈ −0.333

**Für den Bot:** Past a certain flop pot size, each additional dollar you put in on the flop with an overpair vs a strong draw actually reduces your EV because you no longer retain large future bets to punish missed draws; your solver or heuristic should recognize these ‘over-investment’ regions and avoid them.

## Stack-depth rule of thumb: when made hand wants early money vs delayed money
Qualitative model: with limited bets left, the draw wants to accelerate money in; the made hand wants to delay some betting until after one more card, unless stacks are deep enough to still have a later bet.

**Formel:** Let N be the number of pot-sized bets remaining after the current street in rigid pot-limit terms.

In the AA vs 15-out draw toy game:
- If N = 1 (small stacks): any bet leads to all-in now, draw prefers all-in now (more cards to come), made hand cannot maintain future leverage.
- If N = 2 (medium stacks): made hand prefers to delay some betting to turn when draw can be forced to call with worse odds; equilibrium becomes check-check flop.
- If N = 3 (deep stacks): made hand can bet flop and still retain future pot-sized bet on turn, so betting flop is again good (X bets, Y calls).

**Für den Bot:** In NLHE, calibrate your flop betting frequency with strong made hands vs strong draws by effective number of future big bets: with only one pot-sized bet left, you may be forced to stack off; with two, often delay; with three+, you can bet now and still punish misses later.

## Effect of reducing draw outs on all-in decisions (folding despite being equity favorite)
Even when a draw is an equity favorite vs a made hand, additional future pot-sized bets can make continuing unprofitable because of implied odds against the draw (reverse implied odds).

**Formel:** Text remark:
Changing from 15 outs to 14 outs with three pot-sized bets remaining:
- On turn: p_hit_turn = 14/45, p_hit_river_given_miss = 14/44
- Now draw’s single-card odds are worse than pot odds (14/44 < 15/45).
- With pot-sized bets on both flop and turn, the draw’s EV from calling both can be negative even if raw equity vs showdown (with all money in immediately) is > 50%.

Thus a general inequality for a draw with equity q and facing k future pot-sized bets can force a fold:

EV_draw_call_all_in_now = q*(P0+2S) - S
EV_draw_call_vs_future_bets = function of (per-street card odds, number and size of future bets)

For some configurations, EV_draw_call_vs_future_bets < 0 even if q > 0.5.

**Für den Bot:** Your bot should not treat raw equity > 50% as an automatic stack-off; when multiple big bets remain, a favorite draw can still be forced to fold because the made hand can threaten future pot-sized bets that are bad for the draw’s price.

## All‑in jam vs call with known equities (QQ vs AK, fixed stacks)
Model EV of a last‑raise all‑in vs flat‑call with face‑up hands as a function of stack size and equity edge.

**Formel:** Given:
- Hero has equity e vs villain when all‑in and all remaining cards seen.
- Hero stacks S, villain stacks S (effective).
- Current pot P0 before hero acts.
- Hero jam size J (total he puts in now over any amount already invested this street).

If jam is always called, hero’s EV of jamming (relative to folding this street) is:
EV_jam = e * (P0 + 2*S) - (S - already_in)

In the QQ vs AK example (numbers in book):
S = 800 or 1800, already_in = 100 (blind) + 300 (X raise) for Y? (book uses simplified cost values)
They effectively use:
EV_Y_jam = e * (2*S) - (S - 100)
For S=800, e=0.5717:
EV_Y_jam = 0.5717*(800+800) - 700 = 214.72
For S=1800:
EV_Y_jam = 0.5717*(1800+1800) - 1700 = 358.12

EV_call line (call pre, then jam/fold on flop using exact conditional board frequencies) is computed as a separate tree:
EV_call = p(A or K flop w/o Q) * (− amount_called_pre) + p(no A or K flop) * (pot_won)
Example with S=800: EV_call = 0.3*(−200) + 0.7*(400) = 220

**Für den Bot:** For any specific preflop matchup (e.g., QQ vs AK), compute EV of jamming vs calling as a function of effective stack and pot. Don’t rely on vague ‘implied odds’; build trees and recognize that deeper stacks can flip preferences (e.g., deep QQ often wants to jam pre vs exposed AK).

## Draws’ preference for getting all‑in early vs keeping pot small
With near‑coinflip draws (≈40–50% equity vs made hand), EV depends heavily on whether further betting is possible. If all chips go in now, the draw realizes its full equity; if not, future betting allows the favorite to extract more when the draw misses.

**Formel:** Toy model:
- Draw with equity e vs made hand if all cards seen.
- Pot now P0, stacks S.
- Case 1 (all‑in now, always called):
EV_draw_allin = e * (P0 + 2*S) - S

- Case 2 (small pot now, big bet later if miss):
Let p_hit be probability draw hits by river, and assume:
  When hit: villain pays off to some amount B.
  When miss: villain can bet amount B and hero folds losing draw.
Rough structure:
EV_draw_two_stage ≈ e * P0  -  (1 - p_hit) * extra_loss_on_misses

Good draws (e close to 0.5) prefer:
- Maximize proportion of their equity that is locked in pre (all‑in).
- Minimize additional negative EV from future streets when they miss.

**Für den Bot:** For strong draws (≈40–50% equity), prefer jam-or-fold decisions over calling to ‘see one card’ when stacks are such that future streets allow big value extraction against you. Use equity vs villain’s continuing range to decide whether to shove now rather than face future tough spots.

## Showdown equity vs ex‑showdown equity decomposition
Split a hand’s EV into equity from an immediate runout (showdown equity) and equity from future betting (ex‑showdown equity). Total EV is the sum.

**Formel:** Definitions:
- Let E_SD be showdown equity: probability of winning (or pot share) if all remaining cards dealt and both players always check to showdown, times current pot size.
- Let E_ex be ex‑showdown equity: expected value from all *future bets* (positive or negative) starting now.

Total EV:
EV_total = E_SD + E_ex

Example with a weak draw facing a bet and folding:
- Showdown equity vs bet: E_SD = p(win if run out) * P_before_bet
- If hero always folds, his ex‑showdown EV is:
E_ex = −E_SD
so EV_total = 0 (he gives up his showdown equity by folding).

**Für den Bot:** Model each line as EV_total = E_SD + E_ex. For preflop or flop calls with money behind, estimate not only raw pot equity but also how position, range advantage, and skill affect ex‑showdown equity. This helps compare flat‑call vs 3‑bet vs fold in NLHE.

## Exploitative shove vs raise-caller who overfolds to 3‑bets (Example 8.1)
Compute EV of jamming any two cards vs a raiser who (i) opens wide and (ii) calls 3‑bets with too narrow a range. This is a jam‑or‑fold toy model giving a concrete exploitation criterion.

**Formel:** Given:
- Button opens for amount R.
- Blinds B_sb, B_bb (here 5,10), but effective calculation uses pot P0 when facing 3‑bet.
- We in big blind shove for total S (we add amount C = S - B_bb).
- Villain folds fraction f of his opening range to the shove, calls fraction 1 − f with calling range Rc.
- Our equity vs Rc is e.
- Pot when villain folds: P0.
- Pot when called: P1 = P0 + C + (S − R_invested_by_villain_so_far). In the example they use P1 = 200 + 200 + 5 = 405.

General EV of shove:
EV_jam = f * P0 + (1 − f) * (e * P1 − C)

Example numbers:
- Villain raises 350 of 1326 combos, calls 40; so
f = 310 / 350 ≈ 0.8857, 1 − f ≈ 0.1143.
- Pot when we shove and win immediately: P0 = $45.
- Our random hand equity vs {JJ+, AK}: e ≈ 0.2495.
- Cost of jam: C = $190.
- Pot when called: P1 = $405.

Then:
EV_jam = 0.8857*45 + 0.1143*(0.2495*405 − 190) ≈ 29.69 > 0
So jamming any two cards is +EV.

Compare to calling with equity x fraction of pot after call:
EV_call = x * (P0 + call_amount) − call_amount
Set EV_call ≥ EV_jam to find x needed:
x * 65 − 20 ≥ 29.69  ⇒  x ≥ 0.7645

**Für den Bot:** Whenever an opener overfolds to 3‑bets, compute p_fold and equity vs his call range. If EV_shove = p_fold*P0 + (1−p_fold)*(e*P1−C) > 0, jam with very wide or even any two cards. This is the NLHE analog of ‘auto‑profit’ 3‑betting; use it to set baseline exploitative shove/fold ranges.

## Bayesian adjustment for card removal in range frequencies
Use Bayes’ theorem/card removal to adjust villain’s range weights conditional on our hole cards. This changes p_fold and p_call and thus shove EV.

**Formel:** Let:
- Original raising range R with N_total combos.
- Subrange R_call ⊆ R villain uses to call shoves, with N_call combos.
- We observe event H = our hand (e.g., AA) which removes some combos from R and R_call.

Bayes/card removal update:
N_total' = N_total − (# combos in R that are impossible given H)
N_call'  = N_call  − (# combos in R_call impossible given H)

Updated frequencies:
P'(call) = N_call' / N_total'
P'(fold) = 1 − P'(call)

Example with hero=AA:
- Original: N_total = 350, N_call = 40.
- After removing two aces: N_total' = 249, N_call' = 27.
- So P'(call) = 27/249, P'(fold) = 222/249.

Plug into EV_jam formula:
EV_AA_jam = (222/249)*45 + (27/249)*[(0.8343)*405 − 190] ≈ 56.16

**Für den Bot:** Always recompute villain’s call/fold frequencies vs your shove using card removal. Your strongest hands often gain extra EV from blocking calls (e.g., AA vs tight 4‑bet calling ranges); this influences optimal shove vs trap decisions.

## EV comparison of alternative postflop lines vs a known strategy (99 vs tight 3‑bettor, Example 8.2)
Treat opponent’s line as fixed strategy over a finite hand‑type partition, and compute EV of different pure strategies (check‑fold, check‑call/CR turn, check‑raise flop, bet/bet) by weighting per‑hand outcomes by their conditional frequencies.

**Formel:** Setup:
- Hero holds 99.
- Villain’s 3‑bet range on A72r flop: {AA, KK, QQ, JJ, TT, AK, AQs} with conditional frequencies given hero’s 99 and board:
  P(AA) = 3/42
  P(KK) = P(QQ) = P(JJ) = P(TT) = 6/42 each
  P(AK) = 12/42
  P(AQs) = 3/42
Aggregate proportions used:
  Group1 = {AA, AK, AQs}: 3/7 of range
  Group2 = {JJ, TT}: 2/7 of range
  Group3 = {KK, QQ}: 2/7 of range

Strategy 1 (check‑fold flop):
EV_1 = 0 (baseline).

Strategy 2 (check‑call flop, check‑raise turn, then give up if pushed back, otherwise to river):
Per‑type outcomes (in small bets):
- vs {AA, AK, AQs}: −5
- vs {JJ, TT}: +10.5 (7.5 in pot + hero’s 1 flop bet + 2 on turn)
- vs {KK, QQ}: −3
So:
EV_2 = P(Group1)*(−5) + P(Group2)*(+10.5) + P(Group3)*(−3)
EV_2 = (3/7)*(−5) + (2/7)*(10.5) + (2/7)*(−3) = 0

Strategy 3 (check‑raise flop, bet turn aggressively):
- vs {AA, AK, AQs}: −4
- vs {KK, QQ, JJ, TT}: +9.5
Let Group_strongAx: prob = 3/7; Group_pairs: prob = 4/7.
EV_3 = (3/7)*(−4) + (4/7)*(+9.5) = 3.71

Strategy 4 (bet flop, bet turn):
- vs {AA, AK, AQs, KK, QQ}: −3
- vs {JJ, TT}: +8.5
So:
EV_4 = (5/7)*(−3) + (2/7)*(+8.5) = 0.29

Ranking: EV_3 > EV_4 > EV_1 = EV_2.
So check‑raise flop, bet turn is best vs this fixed opponent strategy, despite 99 being far behind in showdown equity.

**Für den Bot:** Don’t collapse decisions to ‘we’re crushed, just fold.’ Against a known or approximated strategy, enumerate opponent hand‑type groups and compute EV of candidate lines. Some aggressive bluff/semi‑bluff lines can outperform folding even when hero’s hand has very poor raw equity, because they exploit range composition and villain’s response rules.

## Indifference of equal-strength actions
When two lines (bet vs check) against a given hand type lead to the same future betting pattern and same number of bets going in, their EVs are equal; only lines that change future action or ranges matter.

**Formel:** <bet> = <check> when future betting is identical

Example from text vs AA on sixth street:
EV_bet(AA) = EV_check(AA)

**Für den Bot:** When evaluating lines, ignore branches where villain’s response and future betting are unchanged; focus computation on branches that actually alter future betting frequencies, pot size, or folding probabilities.

## Single-line EV with showdown equity
EV of a line that results in one more bet going in now and then going to showdown is just equity times final pot minus cost of the bet.

**Formel:** Let P = current pot
let b = bet size
let e = hero equity when called

If hero bets, villain always calls and there is one more street (no more betting):
EV_bet = e * (P + 2b) - b

If hero checks and always goes to showdown now with no more betting:
EV_check = e * P

Difference:
EV_bet - EV_check = e * (P + 2b) - b - eP = 2e b - b = b (2e - 1)

**Für den Bot:** With symmetric one-bet lines, bet if equity > 0.5, check if equity < 0.5; this simple rule underlies many river/value decisions for a solver or heuristic bot.

## Weighted EV over opponent hand distribution
To choose between candidate actions vs a range, compute EV vs each hand type, then take the probability-weighted average. This is Bayesian integration over opponent’s range.

**Formel:** Let opponent hand types be h_i with probabilities p_i (sum p_i = 1).
For an action a, with EV(a | h_i) vs hand type i:

EV(a) = sum_i [ p_i * EV(a | h_i) ]

Example table in text (Bet – Check):
Total_EV(Bet - Check) = sum_i p_i * (EV_bet(i) - EV_check(i))

In their stud8 example:
AA: p = 1/16, diff = 0
Q♣Qx or J♣Jx: p = 5/16, diff ≈ +24
QxQy or JxJy: p = 4/16, diff ≈ +10
X♣Y♣: p = 6/16, diff ≈ -48

Total diff ≈ 0*(1/16) + 24*(5/16) + 10*(4/16) - 48*(6/16) ≈ -8

**Für den Bot:** All action selection should be driven by range-weighted EV, not single-hand narratives; the bot must represent opponent ranges and integrate EV over them to decide between bet/check/raise/fold.

## Multi-branch EV decomposition (hit vs miss future cards)
For draws, EV of betting/checking can be decomposed into disjoint future-card events (e.g., hit vs miss) each with its own conditional line and equity, then recombined via total probability.

**Formel:** Partition future cards into events E_k (e.g., hit calling card vs miss), with probabilities q_k and conditional EVs EV_a(E_k) for action a (bet or check):

EV_a = sum_k [ q_k * EV_a(E_k) ]

Example X♣Y♣ case in text:
Event H (hit calling card) with prob 26/34:
  EV_bet(H) = -88.35
  EV_check(H) = -43.95
Event M (miss) with prob 8/34:
  EV_bet(M) = -120
  EV_check(M) = -60

EV_bet = (26/34)*(-88.35) + (8/34)*(-120) ≈ -95.8
EV_check = (26/34)*(-43.95) + (8/34)*(-60) ≈ -47.7

**Für den Bot:** For multi-street NLHE decisions with draws, explicitly split the tree into hit/miss or card-category branches, compute conditional EV lines per branch, then recombine; this is essential for correct semi-bluff sizing and check/call vs check/fold with draws.

## Pot-odds style value-bet inequality (bet vs check on turn/river)
Betting to deny equity or extract value can be approximated using showdown equity and incremental pot size, comparing EV_bet to EV_check, as done in the stud example vs Q♣Qx.

**Formel:** General pattern in text:

EV_bet = p_win * (P + ΔP_bet) - C_bet
EV_check = p_win * P

So incremental gain from betting:
ΔEV = EV_bet - EV_check = p_win * (P + ΔP_bet) - C_bet - p_win * P
      = p_win * ΔP_bet - C_bet

Where ΔP_bet is the total increase in pot size from betting line (including later streets) and C_bet is additional money hero invests across that line relative to checking.

Example vs Q♣Q♦ in text:
P = 345, game is 30-60, they model one more 60 on 6th and one more 60 on 7th:
ΔP_bet = 120, C_bet = 60, p_win ≈ 0.70:
EV_bet ≈ 0.70*(345+120) - 60 = 265.5
EV_check ≈ 0.70*345 = 241.5
ΔEV ≈ +24

**Für den Bot:** To decide whether to fire another value bet with a strong but non-nut hand, compare p_win * additional pot you create to the extra cost you pay; avoid value bets where this inequality is negative, even if your hand is currently ahead.

## All-in jam EV vs call frequency and equity
For a shove that risks multiple pots, EV decomposes into a fold branch (win current pot) and call branch (realize equity vs calling range). This is the same structure as jam-or-fold toy games.

**Formel:** Let P = current pot
let J = hero's shove size
let f = villain fold probability vs shove
let e = hero's equity when called

EV_jam = f * P + (1 - f) * [ e * (P + J + C) - J ]

If villain calls full with C = J (symmetric stacks):
EV_jam = f * P + (1 - f) * [ e * (P + 2J) - J ]

Relative to folding (0 EV), jam is profitable if EV_jam > 0.

In their example: hero jams 3 into pot 1 (J=3,P=1), assume symmetric stacks and that when called hero has e ≈ 1/3 vs calling range.
If villain calls with his best q fraction and folds 1-q, then f = 1 - q.

So:
EV_jam = (1-q)*1 + q * [ (1/3)*(1+6) - 3 ]
        = 1 - q + q * ( (1/3)*7 - 3 )
        = 1 - q + q * (7/3 - 3)
        = 1 - q + q * (-2/3)
        = 1 - (5/3) q

Jam profitable if 1 - (5/3) q > 0 → q < 3/5.
So if villain only calls with best 25% (q=0.25 < 0.6), jam is clearly +EV.

**Für den Bot:** When evaluating flop/turn overbet jams with strong draws, model EV as fold-branch + call-branch; shoves can be profitable even with only ~33–40% equity if fold probability is high enough relative to pot:stack ratio.

## Threshold villain call frequency for profitable jam (given equity)
Given pot, shove size, and equity e when called, we can derive a maximum call frequency q* above which hero’s shove is break-even; below q*, jam is +EV. This is analogous to optimal bluff frequency conditions.

**Formel:** Assume symmetric stacks (villain calls amount J), hero shoves J into pot P with equity e when called and villain calls fraction q of the time.

EV_jam = (1 - q) P + q [ e (P + 2J) - J ]
Set EV_jam = 0 and solve for q:

0 = P - qP + q [ e (P + 2J) - J ]
0 = P + q [ -P + e(P + 2J) - J ]

So
q* = -P / [ -P + e(P + 2J) - J ]
   = P / [ P - e(P + 2J) + J ]

Jam profitable if villain_call_prob q < q*.

Special case P=1, J=k (overbet multiple k), e given:
q* = 1 / [ 1 - e(1 + 2k) + k ]

**Für den Bot:** For any proposed flop/turn shove, the bot can compute q* and compare it to its estimate of villain’s calling frequency; this provides a fast heuristic to decide whether jamming a strong draw or bluff is profitable.

## Information hiding via range-mixing (distribution vs distribution)
A strong strategy plays multiple hand classes (value, strong draws, some bluffs) through the same betting line to keep opponent’s range inferences wide; the mathematical rationale is that we choose the line that maximizes total distribution EV, not per-hand EV.

**Formel:** Let there be two hand classes A and B, each occurring with the same frequency, and two lines X and Y.
Let EV_A(X), EV_A(Y) be EVs of playing A via X or Y, and EV_B(X), EV_B(Y) for B.
If we must choose a unified line due to information-hiding constraints, we select line L ∈ {X,Y} maximizing:

EV_total(L) = 0.5 * EV_A(L) + 0.5 * EV_B(L)

Even if EV_A(X) > EV_A(Y), if EV_B(Y) - EV_B(X) is sufficiently large, we prefer L = Y overall.

The text’s example: strong made hands slightly prefer small-bet line in a vacuum, but draws strongly prefer jam line; jamming both increases entire distribution EV because it prevents opponent from trimming the tree and counter-exploiting.

**Für den Bot:** When building betting ranges, pick the line that maximizes aggregate range EV, even if some individual hands would earn a bit more via a different line; this justifies jamming both sets and strong draws in some spots to keep the range coherent and hard to exploit.

## Strong draw equity benchmark (≈12 outs on flop)
A “strong” flush draw with ~12 outs (flush + overcards/straight) has ~45% equity vs a one-pair hand on the flop; this underpins its suitability to jam-or-fold strategies.

**Formel:** Approximate equity for N outs over two cards:
Equity ≈ 1 - ((47 - N)/47) * ((46 - N)/46)

For N = 12:
Equity ≈ 1 - (35/47) * (34/46) ≈ 1 - (1190 / 2162) ≈ 0.45

Text assertion: “A hand with twelve outs on the flop has approximately 45% equity in the pot.”

**Für den Bot:** Treat 12–15-out combo-draws as ~45–55% equity vs top pair and structure flop/turn strategies so they can comfortably stack off (jam or call off) against strong but non-nut made hands at typical SPRs.

## Overbet-jam exploitability and counteradjustment
If hero jams only strong draws and small-bets value hands, villain can counter by calling jams only with hands that dominate hero’s draws while playing normally vs small bets. Hero must then include strong value in jam range to restore balance.

**Formel:** Model villain’s call EV vs two hero jamming strategies:

1) Draw-only jams: hero jams with range D (draws) having equity e_D(h) vs each villain hand h.
Villain chooses call set C ⊂ H to maximize:
EV_villain(call with h) = (1 - e_D(h)) * (P + 2J) - J (assuming symmetric)

2) Mixed jams with draws and value V: hero jam range R = D ∪ V; villain’s EV becomes:
EV_villain(call with h) = E_{H∈R} [ (1 - e_H(h)) (P + 2J) - J | jammed ]

By adding V where e_V(h) ≪ e_D(h) (from villain perspective), the average e_H(h) decreases, reducing villain’s calling incentive, thus increasing hero’s fold equity and total EV with both D and V.

Mathematically this is just range-mixing: choose mixing probabilities α_D, α_V to make villain indifferent among borderline calls/folds.


**Für den Bot:** Do not construct a flop jam range that is only draws; always mix in some strong made hands at appropriate frequency so that villain cannot profitably overcall vs jams yet overfold vs small bets, i.e., keep jam range’s average equity vs villain high.

## Balanced strategy (defensive value vs optimal EV)
A strategy’s defensive value is its EV versus the opponent’s maximally exploitive strategy (nemesis). A strategy is balanced if this defensive value is close to its EV versus the opponent’s optimal strategy. Optimal strategies are perfectly balanced (unexploitable).

**Formel:** Let s_A be Hero’s strategy, s_B any Villain strategy, s_B^MES(s_A) Villain’s maximally exploitive response to s_A, and s_B^* an optimal strategy.

Defensive value of s_A:
V_def(s_A) = EV(s_A , s_B^MES(s_A))

Value versus optimal opponent:
V_opt(s_A) = EV(s_A , s_B^*)

Balance measure (one natural definition):
Balance(s_A) = V_def(s_A) - V_opt(s_A)

Optimal strategy s_A^* satisfies:
V_def(s_A^*) = V_opt(s_A^*) = game_value

**Für den Bot:** When you can’t fully solve a NLHE spot, target strategies whose EV against a best‑responding opponent is close to their EV against a solver‑like approximation. Use approximate best‑response tools to quantify and minimize exploitability, not just raw winrate versus a fixed pool model.

## Single‑parameter bluffing game on the river (pot = 3, 20% nuts)
Toy river game: Hero A either has a made flush (20%) or air (80%). Pot is 3 bets. A bets all value hands and may bluff some fraction x of air. Villain B has a bluff‑catcher. B’s maximally exploitive strategy is to fold always if A’s bluff rate is too low, and call always if it is too high. We can explicitly compute B’s EV under both exploitative responses as a function of x.

**Formel:** Given:
- pot_before_bet = 3 (bets)
- freq_value = 0.2 (A has flush)
- freq_air = 0.8 (A has nothing)
- x = fraction of total hands that A uses as bluffs

B’s MES if A bluffs less than 5% of total hands (x < 0.05): fold always.
When B folds, B wins the pot whenever A is bluffing; with probability freq_air * (x / freq_air) = x of A’s total range:
EV_B_fold = +3 * x
(thus the book’s notation <B, fold> = 3x)

B’s MES if A bluffs more than 5% of total hands (x > 0.05): call always.
When B calls:
- Versus value: B loses 1 bet (pays off A’s winning hand)
- Versus bluff: B wins the 3‑bet pot

Let p_val = 0.2 be probability A has value (always bets), and p_bluff = x be total probability A bluffs.
Normalized betting range size: p_total_bet = p_val + p_bluff = 0.2 + x.
Conditional frequencies when facing a bet:
q_val = p_val / (p_val + p_bluff)
q_bluff = p_bluff / (p_val + p_bluff)

B’s EV when calling:
EV_B_call = q_bluff * (+3) + q_val * (−1)
= (3x / (0.2 + x)) − (0.2 / (0.2 + x))
= (3x − 0.2) / (0.2 + x)

In the text’s simplified linearized example they write it as:
<B, call> = x − 0.2
which is an affine model intended only to illustrate dependence on x.

Indifference (optimal A bluffing frequency) occurs where B’s exploitative options yield equal EV:
EV_B_fold = EV_B_call
3x = x − 0.2
=> 2x = −0.2
=> x = −0.1 (this shows their simplified linearization is only illustrative; in a consistent pot‑odds toy model, the critical bluff frequency would instead be set by the usual pot‑odds condition).

**Für den Bot:** For a fixed value‑to‑air composition and pot size, you can explicitly compute a villain’s best‑response EV to your bluff frequency. Use such 1‑parameter toy models to tune river bluff frequencies so that common counter‑strategies (overfolding or overcalling) are approximately indifferent, keeping your line hard to exploit.

## Maximally exploitive strategy (MES) in binary response games
Given a one‑street game where Hero can choose a frequency parameter (e.g., bluff frequency x), and Villain has a binary response (e.g., call or fold), Villain’s best response is pure: choose the action with higher EV given Hero’s current x. The nemesis thus implements a piecewise strategy switching at an indifference point.

**Formel:** Let x parameterize Hero’s strategy (e.g., total bluff frequency). Let Villain actions be a ∈ {call, fold}.
Villain’s EVs are functions:
EV_call(x), EV_fold(x)

Villain’s maximally exploitive strategy a^MES(x):
a^MES(x) = argmax_{a ∈ {call, fold}} EV_a(x)

The switch point x* solves the indifference equation:
EV_call(x*) = EV_fold(x*)

For any x:
- If EV_call(x) > EV_fold(x): best response is call always
- If EV_call(x) < EV_fold(x): best response is fold always
- If EV_call(x) = EV_fold(x): Villain is indifferent; any mix is a best response

**Für den Bot:** When optimizing a single strategic parameter (bluff %, bet size choice between two sizes, etc.), treat the opponent’s counter as pure and piecewise; solve for the indifference point between their pure responses to find your robust mix.

## Optimal mixed strategies and indifference condition
In any zero‑sum two‑player game, if an optimal strategy uses a mixed (randomized) choice among several actions in the same information set, then against the opponent’s optimal counterstrategy all those mixed actions must achieve equal EV. Otherwise the player could unilaterally improve by shifting probability mass to the higher‑EV action.

**Formel:** Let actions in some information set be indexed i = 1..k. Let Hero use mixed strategy p = (p_1, ..., p_k) with p_i ≥ 0, sum p_i = 1. Against opponent’s optimal strategy s_opp^*, Hero’s EV for pure action i in that information set is:
EV_i = EV(action_i , s_opp^*)

If the mixed strategy p is part of an optimal strategy, then for any i with p_i > 0:
EV_i = constant = EV_mix

More explicitly:
∀i, j with p_i > 0 and p_j > 0:
EV_i = EV_j

and EV_mix = Σ_i p_i * EV_i

**Für den Bot:** In NLHE solving, when you see a hand mixing between, say, bet and check, your model should enforce (or verify) that the EVs of bet and check are equal (up to numerical noise). This is the key KKT‑like condition that defines equilibrium mixing: don’t allow mixed lines where one line is strictly higher EV than the other.

## Nemesis / defensive optimization definition of optimal strategy
In two‑player zero‑sum games, define the nemesis as an opponent who always best‑responds to your current strategy. An optimal strategy maximizes your EV against this nemesis. Equivalently, in an optimal strategy pair, each strategy is a best response to the other, and they maximally exploit each other.

**Formel:** Let S_A, S_B be the strategy spaces for players A and B. Let BR_B(s_A) be B’s best response to A’s strategy s_A, and BR_A(s_B) A’s best response to B’s s_B.

Nemesis for A given s_A:
Nemesis_B(s_A) ∈ argmax_{s_B ∈ S_B} EV_A(s_A, s_B)^c
(where ^c indicates B’s EV is −EV_A in zero‑sum.)

Defensive (minimax) value of s_A:
V_def(s_A) = EV_A(s_A , Nemesis_B(s_A)) = min_{s_B ∈ S_B} EV_A(s_A, s_B)

Optimal strategy for A:
s_A^* ∈ argmax_{s_A ∈ S_A} V_def(s_A) = argmax_{s_A ∈ S_A} min_{s_B ∈ S_B} EV_A(s_A, s_B)

Optimal strategy pair (s_A^*, s_B^*):
EV_A(s_A^*, s_B^*) ≥ EV_A(s_A, s_B^*) for all s_A ∈ S_A
EV_A(s_A^*, s_B^*) ≤ EV_A(s_A^*, s_B) for all s_B ∈ S_B

This is the standard minimax / saddle‑point characterization.

**Für den Bot:** When training a NLHE bot, frame the objective as maximizing the worst‑case EV versus a best‑responding opponent (minimax), not just maximizing EV versus a fixed population. Self‑play or RL procedures should explicitly approximate best responses to your current policy and then update towards strategies that improve against that nemesis.

## Odds and Evens optimal mixing
In the 2x2 zero‑sum game Odds and Evens, each player chooses 0 or 1 penny simultaneously; one player wins if the sum is even, the other if odd. Any strategy that plays one action more than 50% lets the nemesis exploit by always matching that higher‑probability action. Optimal play is to randomize 50/50 between pure actions, guaranteeing zero EV.

**Formel:** Let x be Player B’s probability of choosing 0 pennies; (1 − x) is probability of 1 penny.
Player A’s nemesis strategy:
- If x > 0.5: play 0 pennies always
- If x < 0.5: play 1 penny always

From the book (B’s EV vs nemesis):
If x > 0.5 (nemesis plays 0):
EV_B(x > 0.5) = (−1) * x + (1) * (1 − x) = 1 − 2x

If x < 0.5 (nemesis plays 1):
EV_B(x < 0.5) = (−1) * (1 − x) + (1) * x = 2x − 1

At x = 0.5, nemesis is indifferent:
EV_B(0.5) = 0

Thus B’s optimal strategy:
x* = 0.5 (play 0 pennies with probability 0.5 and 1 penny with probability 0.5)
Game value = 0

**Für den Bot:** In simple symmetric zero‑sum subgames where your options are essentially binary (e.g., check/fold vs check/call always), protecting yourself often means mixing exactly enough between the two so that an opponent can’t profit by fixating on one pure counter. The 50/50 mix here is the archetype: symmetry + nemesis response ⇒ equalization point.

## Roshambo (Rock–Paper–Scissors) equilibrium mix
In Rock–Paper–Scissors, there are three pure actions with cyclic dominance. Any deterministic bias allows a nemesis to counter with the dominating pure action. Optimal play is to mix uniformly across all three actions, making the opponent indifferent and guaranteeing zero EV.

**Formel:** Let B’s mixed strategy be p = (p_R, p_P, p_S) over {Rock, Paper, Scissors}. A’s pure responses have EVs:

EV_A(Rock vs B) = −p_P + p_S
EV_A(Paper vs B) = p_R − p_S
EV_A(Scissors vs B) = −p_R + p_P

B wants to choose p to minimize max over A’s pure responses. At equilibrium B chooses:
p_R = p_P = p_S = 1/3

At p_R = p_P = p_S = 1/3:
EV_A(Rock) = −1/3 + 1/3 = 0
EV_A(Paper) = 1/3 − 1/3 = 0
EV_A(Scissors) = −1/3 + 1/3 = 0

So all A’s pure strategies yield the same EV (0): A is indifferent, and B has achieved an optimal mixed strategy. Game value = 0.

**Für den Bot:** Whenever your action set is symmetric (e.g., three sizings that serve similar roles) and you can’t profitably bias toward one without opening a counter, the equilibrium will often be a uniform or symmetry‑respecting mix. Your bot should look for such symmetry and expect flat EV across those actions at equilibrium.

## Nash equilibrium condition (no unilateral profitable deviation)
A Nash equilibrium in a finite game is a strategy profile where each player’s strategy is a best response to the others. In two‑player zero‑sum games this coincides with the minimax optimum. No player can increase EV by unilaterally changing strategy.

**Formel:** Let players i = 1..n, strategies s_i ∈ S_i, and payoff functions u_i(s_1,...,s_n).
A strategy profile s* = (s_1^*,...,s_n^*) is a Nash equilibrium if:
∀i, ∀s_i ∈ S_i:
    u_i(s_i^*, s_{−i}^*) ≥ u_i(s_i, s_{−i}^*)

In the special case of two‑player zero‑sum (u_2 = −u_1), a Nash equilibrium (s_1^*, s_2^*) satisfies:
EV_1(s_1^*, s_2^*) = max_{s_1} min_{s_2} EV_1(s_1, s_2)
                  = min_{s_2} max_{s_1} EV_1(s_1, s_2)

and each s_i^* is a best response to the other:
EV_1(s_1^*, s_2^*) ≥ EV_1(s_1, s_2^*) for all s_1
EV_1(s_1^*, s_2^*) ≤ EV_1(s_1^*, s_2) for all s_2

**Für den Bot:** Solver‑trained strategies for HU or local two‑player subgames in NLHE are approximations to Nash equilibria. When evaluating or updating your bot, focus on whether any unilateral change (e.g., changing only your flop C‑bet frequencies) yields higher EV against a fixed opponent strategy; if so, you’re not yet at equilibrium.

## Balanced vs unbalanced strategy in multi‑parameter settings
In realistic poker settings, strategies contain many coupled parameters (value bet frequencies, bluff frequencies with multiple hand classes, sizings, etc.). A strategy can be suboptimal yet still hard to exploit: its defensive value remains close to its EV versus optimal play. Balance is multi‑dimensional: being off in one parameter can be partially compensated by others, keeping the overall exploitability low.

**Formel:** Let s be a strategy vector comprised of many parameters, s = (θ_1, θ_2, ..., θ_k). Let s^* be an optimal strategy, and Nemesis(s) B’s best response.

Defensive value:
V_def(s) = EV(s , Nemesis(s))

Value under equilibrium opponent:
V_opt(s) = EV(s , s_opp^*)

Exploitability of strategy s (one natural metric):
Exploitability(s) = V_opt(s) − V_def(s)

Small |Exploitability(s)| ⇒ balanced; large |Exploitability(s)| ⇒ unbalanced.

Even if s is not equal to s^*, it may still have small exploitability if nearby in strategy space:
‖s − s^*‖ small ⇒ |Exploitability(s)| small (heuristically, under smoothness).

**Für den Bot:** Your NLHE bot does not need exact GTO in every branch; it needs low exploitability. Allow small strategic simplifications (e.g., coarser bet sizing trees, slightly off value/bluff splits) as long as best‑response analysis shows only small EV loss. Target “balanced enough” strategies computationally feasible to implement at runtime.

## Indifference in finite zero-sum games (mixed strategies)
In any 2-player zero-sum game, whenever a player mixes between multiple pure actions in equilibrium, those actions must have equal expected value versus the opponent’s equilibrium strategy. Solve equilibrium by writing EVs of each mixed action and equating them.

**Formel:** Let player Y mix over actions i with probabilities q_i, and player X respond with strategy p. For any i,j in the support of Y's mix:
EV_Y(action i | p) = EV_Y(action j | p)

Equivalently for X:
EV_X(action k | q) = EV_X(action l | q) for all k,l in support of X's mix.

This is what is done in the Roshambo-S and Cops & Robbers games:
Example (Cops & Robbers robber side):
<robber, rob> = 1 - 2x
<robber, don't> = x
Set equal: 1 - 2x = x  => x = 1/3.

**Für den Bot:** When constructing equilibrium betting / calling / bluffing mixes in toy or abstracted NLHE spots, always impose indifference: actions that are used with positive probability must have equal EV given the opponent’s strategy. This is the core constraint to solve for optimal frequencies.

## Roshambo-S optimal mixed strategy (biased payoff matrix)
Solving a 3×3 zero-sum game via indifference: solve for probabilities over Rock, Paper, Scissors so opponent is indifferent between their three pure actions.

**Formel:** Payoff matrix for Player A (rows=A, cols=B):
         B:   Rock   Paper  Scissors
A: Rock        0     -1      +1
   Paper      +1      0      -2
   Scissors   -1     +2       0

Let A's strategy be {a (Rock), b (Paper), c (Scissors)}, with a + b + c = 1.
EV for B's pure actions vs {a,b,c}:
<B, rock> = c - b
<B, paper> = a - 2c
<B, scissors> = 2b - a
Indifference: c - b = a - 2c = 2b - a, with a + b + c = 1.
Solution: a = 1/2, b = 1/4, c = 1/4.

**Für den Bot:** Even small payoff asymmetries shift optimal frequencies away from uniform. For NLHE, any change in payoff structure (e.g., rake, stack depth, ICM) implies re-optimizing action frequencies; do not assume symmetric-matrix heuristics like simple 1/3 mixes.

## Dominated and strictly dominated strategies; iterative elimination
A strategy S is dominated if there exists S' that yields at least as high EV against all opponent strategies and strictly higher EV against at least one. Strictly dominated means strictly higher EV against all opponent strategies. Iteratively removing dominated strategies reduces the game to a simpler subgame with the same equilibrium payoffs.

**Formel:** Dominance definitions:
Given opponent strategies T in set T:
S' dominates S if
  EV(S', T) >= EV(S, T) for all T, and
  EV(S', T0) > EV(S, T0) for some T0.

S' strictly dominates S if
  EV(S', T) > EV(S, T) for all T.

Iterative elimination rule:
Start with game G (strategy sets S_X, S_Y). Repeatedly remove any dominated strategies from S_X and S_Y to obtain reduced strategy sets S'_X, S'_Y and subgame G'. Then every Nash equilibrium of G' is a Nash equilibrium of G.

**Für den Bot:** In abstraction and action-space design for a poker bot, pre-eliminate strictly dominated lines (e.g., nonsensical bet sizes or impossible mixed lines) to shrink the game tree. However, be cautious: some weak-looking actions may be co-optimal in equilibrium if counter-strategies never reach them.

## Co-optimal strategies (including dominated actions)
An action can be dominated globally but still appear in a co-optimal strategy pair when the opponent’s equilibrium never uses the lines where that domination matters. Co-optimal strategies are all members of some equilibrium pair that share the same game value.

**Formel:** Let G be a zero-sum game with value v. A strategy s_X for player X is co-optimal if there exists a strategy s_Y for player Y such that (s_X, s_Y) is a Nash equilibrium and EV_X(s_X, s_Y) = v.

A strategy a may be dominated by a' in the full game, but if all Nash equilibria of G assign probability 0 to opponent pure strategies where a' strictly outperforms a, then mixing between a and a' yields the same EV v and is co-optimal.

**Für den Bot:** During solving, small-probability or technically dominated actions may persist in equilibrium with negligible weight. A practical NLHE solver/bot can prune or merge such actions for speed, but must ensure that pruned actions are not needed to protect against realistic counter-strategies.

## Cops and Robbers: 2×2 mixed equilibrium
A 2×2 zero-sum game where each player has two pure actions and the equilibrium is a mixed strategy where each player makes the other indifferent between their two actions.

**Formel:** Game structure (payoffs given as (Robber, Cop) in text; but using robber's EV, as they solve):
Robber actions: Rob, Don't.
Cop actions: Patrol, Don't Patrol.
Robber EV matrix (from robber’s perspective inferred from text equations):
           Cop:      Patrol     Don't
Robber: Rob        -1          +1
        Don't     +1           0

Let x = frequency Cop patrols.
Robber EVs:
<robber, rob> = (-1)*x + (1)*(1 - x) = 1 - 2x
<robber, don't> = (1)*x + 0*(1 - x) = x
Indifference: 1 - 2x = x  => x = 1/3.

Let y = frequency Robber robs.
Cop EVs as given:
<cop, patrol> = 2y - 1
<cop, don't>  = -y
Indifference: 2y - 1 = -y  => y = 1/3.

Equilibrium: Cop patrols 1/3, Robber robs 1/3.

**Für den Bot:** This is structurally identical to a simple bluff/call/no-bluff/no-call game. Use equal-EV constraints to derive bluffing and defending frequencies whenever players can exploit each other’s pure strategies (oscillation indicates need for mixing).

## Half-street limit clairvoyance game: optimal calling frequency
In a one-street limit game with pot P and bet size 1, where Y can value bet all winners and bluff some losers, X chooses a single calling frequency c to make Y indifferent between bluffing and checking. This yields X’s minimal-defense frequency.

**Formel:** Game:
- Pot size = P (in bet units).
- Bet size = 1.
- Y has two types of hands vs X: nuts (always win at showdown) and dead (always lose).
- Y bets all nuts and bluffs fraction b of dead.
- X calls with probability c versus any bet.

Y’s EV from bluffing a dead hand:
EV_Y(bluff) = P * (1 - c) - 1 * c = P(1 - c) - c.
Y’s EV from checking a dead hand:
EV_Y(check) = 0.
Indifference condition for dead hands:
P(1 - c) = c  =>  Pc - P = -c  => c(P + 1) = P  =>

c = P / (P + 1).

Thus X’s folding frequency versus a bet is:
fold_freq = 1 - c = 1 - P/(P+1) = 1/(P+1).

**Für den Bot:** On a single street vs a pot-sized limit bet, optimal defense frequency is c = P/(P+1) of your range. This is the basic minimal-defense frequency concept: defend enough that bluffs break even, preventing the bettor from profiting by bluffing any two.

## Half-street limit clairvoyance game: optimal bluffing ratio (alpha)
In the same one-street limit game, Y chooses bluffing frequency b (fraction of dead hands to bluff) so that X is indifferent between calling and folding. This yields the optimal bluff-to-value ratio alpha.

**Formel:** Definitions:
- P = pot size (in bet units).
- Y bets all nut hands and bluffs fraction b of dead hands.
- When X calls:
  * vs value bet, X loses 1.
  * vs bluff, X wins P + 1 (pot plus Y’s bet).

Let b = (#bluffs)/(#value bets) in Y’s betting range. Equivalently, interpret b as the ratio of dead hands bet to nut hands bet.

EV_X(call) = -1 * (1 / (1 + b)) + (P + 1) * (b / (1 + b)).
(Here probability of value bet given bet is 1/(1+b), bluff is b/(1+b).)
EV_X(fold) = 0.

Indifference EV_X(call) = EV_X(fold) = 0:
-1 * (1 / (1 + b)) + (P + 1) * (b / (1 + b)) = 0
Multiply by (1 + b):
-1 + (P + 1)b = 0
(P + 1) b = 1

b = 1 / (P + 1).

Define alpha:
alpha = 1 / (P + 1).   (limit cases)          (11.1)

Then:
- X’s folding frequency vs a bet is also alpha (from previous result: fold_freq = 1/(P+1)).
- Y’s optimal bluff/value ratio is alpha: bluffs : value bets = alpha : 1.
- X’s calling frequency vs a bet is 1 - alpha = P/(P + 1).       (11.2)

**Für den Bot:** On a one-street limit decision facing pot P, your optimal bluff-to-value ratio is alpha = 1/(P+1); your opponent should fold with frequency alpha and call with 1-alpha. This is the fundamental alpha–MDF link: more in the pot → lower optimal bluff ratio and higher defense frequency.

## Generalized alpha for arbitrary bet size (variable s)
Extend the clairvoyance game from fixed bet size 1 to arbitrary bet size 's' measured in pot units. The same indifference logic yields a generalized alpha depending only on s, not on absolute pot size.

**Formel:** Let:
- Pot size before bet: P (in monetary units).
- Y bets size B = s * P, where s is bet size expressed in pots.

The standard generalization (as given in the text) is:
alpha = s / (1 + s).     (variable bet sizes)           (11.3)

Interpretation in the usual poker literature:
- alpha is the optimal *folding* frequency of X versus a bet size s (in pots).
- 1 - alpha is X’s minimal-defense frequency (MDF) versus that bet size: MDF = 1 / (1 + s).

In the limit case where bet size is defined as 1 unit and P is in units of the bet, we instead had:
alpha = 1 / (P + 1).  Here alpha is the bluff:value ratio and also the folding frequency relative to P.

Under the variable-size formulation used in practice (fixing s and letting P be large), the commonly used MDF formulas are:
- MDF (call frequency) = 1 / (1 + s).
- Fold frequency = s / (1 + s) = alpha.

**Für den Bot:** For any single-street spot vs bet size s (in pots), enforce MDF ≈ 1 / (1 + s) as a baseline defense frequency and allow your own bluffing proportions so that opponent is indifferent: use fold_freq = alpha = s/(1+s), call_freq = MDF. This is central for sizing-aware bluffing and defending in NLHE.

## Oscillating pure strategies ⇒ mixed equilibrium
If players can successively exploit each other’s pure strategies in a cycle (A exploits B, then B exploits A’s adjustment, and so on), equilibrium involves mixing between the pure strategies involved in the cycle.

**Formel:** Given zero-sum game where for player X: A and C, and for Y: B and D, suppose:
- If X plays A, Y’s best response is B.
- If Y plays B, X’s best response is C.
- If X plays C, Y’s best response is D.
- If Y plays D, X’s best response is A.

Then:
- There is no pure-strategy equilibrium in {A,C}×{B,D}.
- The equilibrium is mixed over {A,C} for X and {B,D} for Y.

Mathematically: solve for probabilities p,1-p on A,C and q,1-q on B,D such that:
EV_X(A | q) = EV_X(C | q)
EV_Y(B | p) = EV_Y(D | p).

**Für den Bot:** In NLHE, if your best responses to villain’s pure lines keep cycling (e.g., always folding → they bluff any two → you start overcalling → they stop bluffing, etc.), the correct solution is a mixed strategy constrained by indifference, not a fixed pure adjustment.

## Half-street game value and ex-showdown EV
In half-street games, the value is defined as the expected chip flow resulting from betting decisions on that street only (including successful bluffs moving the pot), ignoring the absolute pre-existing pot except via its effect on incentives. For the clairvoyance game, Y’s value is ≥ 0 because Y can always check back (option value).

**Formel:** Definition:
Value(G) = EV_Y(ex-showdown) under optimal play,
where ex-showdown EV counts:
- Bets and calls placed on the considered street.
- The swing of the pot between players when a bluff succeeds (pot moves from X to Y).

For any half-street game where Y can always check back for 0 change:
Value(G) >= 0.

In the clairvoyance game, if X uses optimal c and Y uses optimal b and always value bets nuts, Y’s ex-showdown EV is exactly the game value; X’s is the negative of that (zero-sum). The explicit numeric value is not given in this excerpt, but is computable given distributions.

**Für den Bot:** When modeling one-street NLHE subgames (e.g., river-only or turn simplifications), define and optimize over ex-showdown EV of that street and allow the aggressor to always check back to guarantee ≥0 baseline. This matches real bots’ subgame-solvers that treat earlier streets as sunk.

## Half-street clairvoyance game: optimal bluffing & calling ratios
In a one-bet (half-street) game where Y knows both hands (clairvoyant) and can bet or check, optimal play fixes a ratio between Y’s bluffs and value bets and a corresponding folding ratio for X. These depend only on pot-size P via α = 1/(P+1).

**Formel:** Definitions:
  P = current pot in betting units
  bet size = 1
  α = 1 / (P + 1)

Optimal frequencies (clairvoyant game in this excerpt’s version where Y is nut-or-air 50/50):
  Y value bet frequency among his total hands = 1/2
  Y bluff frequency among his total hands = α/2   (i.e. bluff α of his air hands)
  Y bluff : value-bet ratio = α : 1
  X call frequency among his total hands = 1 - α

Y’s EV in that specific nut/air clairvoyance game:
  <Y> = (frequency of value betting) * (win 1 bet) * (frequency getting called)
      = (1/2) * 1 * (P / (P + 1))
      = P / (2 (P + 1))

General half-street game relationships (from clairvoyance and [0,1] game #2):
  α = 1 / (P + 1)                    # bluff-to-value ratio for bettor
  1 - α = P / (P + 1)                # minimum calling fraction vs a bet
  bettor’s optimal bluffing fraction among value bets = α
  caller’s optimal folding fraction among bluff-catchers = α


**Für den Bot:** In any single-bet NLHE spot with pot P and bet b, target bluff:value ≈ b/(P+b) and call with ≈ P/(P+b) of hands that beat your bluffs. For pot-size bet (b=P) this is bluff:value = 1/2 and call 1/2 of bluff-catchers.

## [0,1] distribution toy games and threshold strategies
In [0,1] games players are dealt a uniform y∈[0,1]; smaller y is stronger. Optimal strategies are pure-threshold: intervals of hands take distinct actions separated by indifference thresholds where the acting player is exactly indifferent between available actions.

**Formel:** Setup:
  y ~ Uniform[0,1] is a player’s ‘hand strength’ (0 best, 1 worst).

Key structural facts:
  • Showdown equity and EV vs neighboring hands are continuous in y.
  • If a region (interval) uses different actions on different sub-intervals, the boundaries between those sub-intervals are thresholds where the player must be indifferent between the actions in equilibrium.

Indifference principle for a threshold t between actions A and B:
  EV_A(t) = EV_B(t)

General method to solve [0,1] toy games:
  1) Parameterize strategy in terms of monotone intervals: e.g.,
     Y bets [0, y1], checks (y1, y0], bluffs (y0, 1].
  2) Write an indifference equation at each threshold (y1, y0, x1*, etc.).
  3) Solve the system of equations; verify consistency (thresholds in [0,1] and ordered).

**Für den Bot:** For continuous hand-strength (like equities or hand rankings), approximate optimal betting/calling with threshold rules (bet above, check middle, bluff below thresholds) and solve for thresholds via indifference (EV of different actions equal at the boundary). This is the right abstraction for range-based NLHE solvers.

## [0,1] Game #1 (no-fold) – bet top half of range
Single half-street, X always calls, Y chooses bet/check with no folding allowed. Pot size is irrelevant. Y maximizes EV by betting all hands with non-negative expectation, which are exactly the best half of his range.

**Formel:** Game structure:
  • X must check-call; cannot fold.
  • Y may bet or check.
  • Pot size P is irrelevant when no folding is allowed.

EV of Y betting with hand y:
  p(X has better hand) = length of [0, y] = y
  p(X has worse hand) = length of [y, 1] = 1 - y

  <Y, bet> = p(better)*(-1) + p(worse)*(+1)
           = y*(-1) + (1-y)*(+1)
           = 1 - 2y

Betting region:
  1 - 2y >= 0  ⇒  y <= 1/2.

Thus Y bets hands y in [0, 1/2], checks y in (1/2, 1].

Overall EV for Y:
  P(y in [0,1/2]) = 1/2.
  Conditional on betting, with probability half of X’s hands (y in [1/2,1]) Y gains 1, with the rest he breaks even.
  So <Y_total> = 1/4.


**Für den Bot:** When villain can’t fold (e.g., capped ranges or forced showdowns), bet all hands with non-negative EV vs his always-calling range. Symmetric single-street spots with no raises often imply: bet top ~half your range.

## [0,1] Game #2 – parameterization and indifference equations
Single half-street, pot P, bet 1. X may fold or call. Y’s optimal strategy is to value-bet his best hands [0, y1], check medium hands (y1, y0], and bluff worst hands (y0,1]. X calls with hands [0, x1*], folds (x1*,1]. Thresholds y1, y0, x1* are pinned by three indifference equations.

**Formel:** Structure:
  P = pot size before Y bets, bet size = 1.
  Y strategy:
    value bets:  y in [0, y1]
    checks:      y in (y1, y0]
    bluffs:      y in (y0, 1]
  X strategy:
    calls:  x in [0, x1*]
    folds:  x in (x1*, 1]

Indifference at X’s calling threshold x1* (call vs fold):
  Weighted EV(call) across Y’s betting region must be 0.
  Contributions when Y has bet:
    Y in [0, y1] (value bets): X loses 1 -> -y1
    Y in [y0,1] (bluffs): X wins pot P+1 -> (P+1)(1 - y0)

  -y1 + (P + 1)(1 - y0) = 0
  ⇒ y1 = (P + 1)(1 - y0)
  ⇔ 1 - y0 = (1/(P + 1)) * y1 = α y1          (11.4)

So Y’s bluffing-interval length is α times his value-bet-interval length; bluff:value ratio = α.

Indifference at Y’s value threshold y1 (bet for value vs check):
  If Y bets hand y1:
    X < y1 → calls and Y loses 1: prob y1
    X in [y1, x1*] → calls and Y wins 1: prob x1* - y1
    X in [x1*,1] → folds and EV 0.

  <Y, bet | y1> = -y1 + (x1* - y1) = x1* - 2 y1.
  <Y, check | y1> = 0.

  x1* - 2 y1 = 0  ⇒  y1 = x1* / 2               (11.5)

Indifference at Y’s bluff threshold y0 (bluff vs check):
  If Y bluffs with y0:
    X in [0, x1*] → calls and Y loses 1: prob x1*
    X in (x1*, y0] → folds and Y wins P: prob y0 - x1*

  <Y, bet | y0> = -x1* + P (y0 - x1*) = P y0 - (P + 1) x1*.
  <Y, check | y0> = 0.

  P y0 - (P + 1) x1* = 0.

Using 1 - y0 = α y1 and (1 - α) = P/(P+1), they rewrite:

  x1* = (P/(P+1)) (1 - α y1) = (1 - α)(1 - α y1)         (11.6)

System of equations:
  (1) 1 - y0 = α y1                       (bluff:value ratio)
  (2) y1 = x1* / 2                       (value threshold)
  (3) x1* = (1 - α)(1 - α y1)            (call threshold)

Solution in terms of α:
  2 y1 = (1 - α)(1 - α y1)
  2 y1 = 1 - α - α y1 + α^2 y1
  1 - α = y1 (2 + α - α^2) = y1 (2 - α)(α + 1)
  ⇒ y1 = (1 - α) / ((2 - α)(α + 1))
  ⇒ x1* = 2 y1 = 2 (1 - α) / ((2 - α)(α + 1))
  ⇒ 1 - y0 = α y1 = α (1 - α) / ((2 - α)(α + 1)).

Recall α = 1/(P+1), 1 - α = P/(P+1).


**Für den Bot:** In single-bet NLHE spots with continuous hand strength, the optimal structure is: value-bet top region, check middle, bluff bottom. Solve three equations: (i) bluff:value ratio = α = bet/(pot+bet); (ii) EV(bet)=EV(check) at top of value region; (iii) EV(bluff)=EV(check) at top of bluff region. That pins your thresholds and thus your mixed strategy at the range level.

## Alpha–MDF relationship (continuous and discrete half-street games)
α encodes the optimal relative frequencies of bluffing and folding in a one-bet game. It is connected to classic minimum defense frequency (MDF). In both discrete clairvoyant and continuous [0,1] games, the same relationships hold: bluff:value = α, fold fraction vs bluffcatchers = α, call fraction = 1−α.

**Formel:** Let P = pot size before a bet, b = bet size (here b=1 in the text but generalizing):
  α = b / (P + b)              # general case
  1 - α = P / (P + b)

For the specific normalization b = 1:
  α = 1 / (P + 1)
  1 - α = P / (P + 1)

Bettor constraints (to make caller indifferent with marginal call hand):
  bluff:value ratio (number of bluff combos / number of value combos) = α.

Caller constraints (to make bettor indifferent with his bluffing hands at threshold):
  folds a fraction α of his *potential call* hands (those beating a bluff).
  calls a fraction 1 - α of those hands.

Equivalently, in common MDF notation:
  MDF = 1 - α = P / (P + b).


**Für den Bot:** Implement α and MDF as core primitives: for any river bet of size b into pot P, (i) constrain your bluff combos to be ~α of your value combos (α = b/(P+b)), and (ii) ensure your calling range defends with MDF = P/(P+b) of bluff-catchers vs a balanced opponent.

## EV of bluffing and value-betting at thresholds
In half-street equilibrium, only threshold hands are indifferent between betting and checking (or between bluffing and checking). Away from thresholds, bluffs can have strictly positive EV relative to checking even though the threshold bluff is break-even.

**Formel:** For a generic threshold t between actions A and B (e.g., bluff vs check):
  EV_A(t) = EV_B(t).

In [0,1] Game #2 specifically:
  At y0 (top of bluff range):
    EV(bluff | y0) = P y0 - (P + 1) x1* = 0.
    EV(check | y0) = 0.

  For any y > y0 (weaker hands nearer 1), X still calls only up to x1*, so EV(bluff | y > y0) = EV(bluff | y0) = 0 vs the same calling strategy, but compared to checking these hands gain equity (because checking with very weak hands has strictly negative showdown EV).

Thus numerically:
  • Threshold bluff y0: EV(bluff) = EV(check) (break-even vs checking).
  • Weaker bluffs y ∈ (y0,1]: EV(bluff) > EV(check).

Similarly at y1 (top of value region):
  EV(bet | y1) = x1* - 2 y1 = 0.
  EV(check | y1) = 0.

  Stronger value hands y < y1: EV(bet | y) > EV(check | y).


**Für den Bot:** When tuning ranges, only the *marginal* value hand and *marginal* bluff should be exactly indifferent; stronger value hands and weaker bluffs should strictly prefer betting over checking. If your solver outputs wide regions with near-zero EV difference, that suggests over-mixing or noise.

## Jam-or-fold game (heads-up high blinds) – structural model
Jam-or-fold games restrict the preflop raiser to shove all-in or fold. This is structurally a half-street game: one bet, opponent chooses call/fold. GTO strategies are again threshold-based in terms of hand-strength distributions (or preflop equities) and satisfy the same α/MDF relationships. While the full equilibrium requires computation, the conceptual model is a direct extension of the half-street games.

**Formel:** Generic jam-or-fold model (preflop heads-up):
  • Blinds post pot P0 (e.g., SB=0.5, BB=1, so P0=1.5 with antes possibly).
  • Jammer risks R chips to win P0; effective stack = R.
  • Caller must call R to win P0 + R.

From jammer’s perspective (one-bet model):
  pot before bet P = P0, bet size b = R.
  So α = b / (P + b) = R / (P0 + R).

Thus the jammer’s optimal bluff:value ratio at equilibrium is:
  bluff:value = α = R / (P0 + R).

From caller’s perspective:
  MDF = P / (P + b) = P0 / (P0 + R).
  So caller should continue (call) with fraction P0/(P0 + R) of hands that are above his calling threshold vs a jam that is perfectly balanced between value and bluffs.

EV of shoving with hand h (equity E vs caller’s calling range):
  Let f_fold be villain’s fold frequency, f_call = 1 - f_fold.

  EV_shove(h) = f_fold * P0 + f_call * [ E * (P0 + R) - (1 - E) * R ].
               = f_fold * P0 + f_call * (E (P0 + R) - R + E R)
               = f_fold * P0 + f_call * (E (P0 + 2R) - R).

Threshold shoving hand h* satisfies EV_shove(h*) = 0.

EV of calling with hand c (equity Ec vs jammer’s jamming range):
  Pot to win on call: P0 + R.
  Cost: R.

  EV_call(c) = Ec * (P0 + R) - (1 - Ec) * R.
             = Ec (P0 + R) - R + Ec R
             = Ec (P0 + 2R) - R.

Threshold call hand c* satisfies EV_call(c*) = 0  ⇒  Ec* = R / (P0 + 2R).

The full solution finds shoving and calling thresholds such that:
  • Given caller’s calling range, marginal shove has EV 0.
  • Given jammer’s jamming range, marginal call has EV 0.

Closed-form for these thresholds in real NLHE requires numerical computation using preflop equity tables, not just the abstract toy model.

**Für den Bot:** Treat preflop jam-or-fold as a one-street game: compute α = R/(P0+R) and MDF = P0/(P0+R), then numerically find shoving and calling thresholds (in terms of preflop equity or hand ranks) where EV=0. Use these to build preflop all-in charts and to train networks to approximate shove/call regions.

## [0,1] Jam-or-Fold Game #1 — Indifference and Thresholds
Uniform [0,1] jam-or-fold toy game where lower number wins full pot. Solve for optimal jamming and calling thresholds via indifference.

**Formel:** Setup:
- Both players stack S
- Blinds: SB(Y)=0.5, BB(X)=1
- Hands ~ Uniform[0,1], lower hand wins entire effective pot S
- Y (attacker) jams with hands h >= y, folds otherwise
- X (defender) calls with hands h >= x, folds otherwise, with constraint x < y

Y's indifference at threshold y:
E_Y(fold) = -1/2
E_Y(jam | y) = P(X calls)(-S) + P(X folds)(+1)
            = x(-S) + (1-x)(+1)
Set equal:
  -xS + 1 - x = -1/2
=> x(1+S) = 3/2
=> x = 3 / (2 + 2S)                 (Eq. 12.1)

X's indifference at threshold x:
- Attacker jams fraction y of hands [y,1]
- Among jammed hands:
    P(Y worse than x | jam) = (y - x)/y
    P(Y better than x | jam) = x/y

E_X(fold) = -1
E_X(call | x) = P(Y better)(-S) + P(Y worse)(+S)
              = (x/y)(-S) + ((y-x)/y)(+S)
              = (S/y)(y - 2x)
Set equal:
 (S/y)(y - 2x) = -1
=> S(y - 2x) = -y
=> S - S^2 x / y = -1
=> y = S^2 x / (S + 1)             (Eq. 12.2)

Substitute x from Eq. 12.1:
 x = 3 / (2 + 2S) = 3 / [2(1+S)]
=> y = S^2 * [3 / (2(1+S))] / (S+1)
=> y = 3S^2 / [2(1+S)^2]

(Note: the text states y = 3S/(1+S)^2 but that is off by a factor S; the consistent derivation with the given matrix value leads to 3S^2/[2(1+S)^2] if E_X(fold) = -1 as written; if instead fold baseline or payoff normalization is different, use the book’s pair:
  x = 3/(2+2S), y = 3S/(1+S)^2.)

Canonical solution as per text:
  x*(S) = 3 / (2 + 2S)
  y*(S) = 3S / (1 + S)^2          (Eq. 12.3)

Y’s game value (using text’s final expression):
  EV_Y(S) = -1/2 + 9S / [4(1+S)^3]

**Für den Bot:** For single-street shove-or-fold with uniform-strength hands where the better hand wins full stack, optimal shove and call frequencies are explicit functions of effective stack S. As S grows, both optimal shove (y) and call (x) frequencies shrink to 0; deep effective stacks tightly constrain preflop jamming ranges when equity realization is perfect.

## [0,1] Jam-or-Fold Game #1 — EV Decomposition
Total game value decomposition using strategy regions and matchup matrix.

**Formel:** Regions (Y by rows, X by columns):
Y regions: [0,x], [x,y], [y,1] (weakest to strongest from Y’s perspective)
X regions: [0,x], [x,y], [y,1]

Payoff entries to Y (attacker) as in matrix in text (sign from Y’s POV):
- When Y folds, X gains 0.5 (Y loses 0.5) — happens with prob 1 - y
- When Y jams and X folds — prob y(1-x) — Y wins +1
- When Y jams and X calls, inside caller’s region:
   * If both hands in [0,x], symmetric -> 0 EV (break-even)
   * If Y in (x,y] and X in [x,y] with Y > X, X wins S
Overall EV to Y:
 EV_Y = P(Y folds)(-1/2) + P(Y jams, X folds)(+1)
        + P(Y jams, X calls and X>Y)(-S) + P(Y jams, X calls and X<Y)(0)

Text’s algebra (after simplification, using equilibrium x,y):
 EV_Y(S) = -1/2 + 9S / [4(1+S)^3]

Sign of EV:
- For 1 <= S <= 2, attacker-favored (EV_Y > 0)
- For S > 2, defender-favored (EV_Y < 0)
- As S -> ∞, EV_Y -> -1/2 (defender just wins SB+BB most of the time).

**Für den Bot:** In shove-or-fold models with full equity realization, deeper stacks structurally favor the defender: the attacker’s EV converges to the blind loss as S increases. For a NLHE bot, wide open-shove ranges with deep stacks are mathematically unsound when villain realizes equity perfectly.

## [0,1] Jam-or-Fold Game #2 — Case S < 3 (Best hand 2/3 equity)
Variant where better hand has only 2/3 equity at showdown; for shallow stacks S < 3, defender must always call because immediate odds dominate.

**Formel:** Setup differences vs Game #1:
- Showdown: better hand gets 2/3 of pot, worse hand 1/3; net swing = S/3 for winner and -S/3 for loser.

Case 1: S < 3, defender’s pot odds:
- If Y jams, pot is 2S, X invests S-1 (additional) to call but always has at least 1/3 equity.
- Immediate pot odds >= 2:1, equity >= 1/3, so folding is dominated.
=> Defender strategy: x = 1 (call all hands).

Attacker’s EV when jamming with cutoff y1 (Y jams for h >= y1):
- P(attacker has best hand) = 1 - y1
- P(attacker has worse) = y1

E_Y(jam | y1) = P(best)*2S*(2/3) + P(worse)*2S*(1/3) - S
              = (1 - y1)*(4S/3) + y1*(2S/3) - S
              = S/3 - 2S y1/3

E_Y(fold | y1) = -1/2

Jam when E_Y(jam|y1) > E_Y(fold):
 S/3 - 2S y1/3 > -1/2
=> 2S - 4S y1 > -3
=> y1 < (2S + 3) / (4S)

Since jam region is h >= y, threshold is:
  y(S) = (2S + 3) / (4S)    for S < 3

So equilibrium for S < 3:
  attacker: jam if h >= y(S), else fold
  defender: always call (x = 1).

**Für den Bot:** When equity is never too bad (worse hand still has 1/3), and stacks are shallow enough that pot odds dominate, the defender should effectively never fold to a shove. For a NLHE bot, with very shallow stacks and non-disastrous equity even with trash, folding to shoves can be strictly dominated; exploit this as the shover with very wide jams.

## [0,1] Jam-or-Fold Game #2 — Case S > 3 (Best hand 2/3 equity) Thresholds
For S > 3, defender cannot call everything; solve equilibrium thresholds with effective stack size S_eff = S/3 using indifference equations.

**Formel:** Showdown payoffs:
- Winner: +S/3
- Loser: -S/3

Y’s indifference at threshold y:
E_Y(fold) = -1/2
E_Y(jam | y) = P(X calls)(-S/3) + P(X folds)(+1)
            = x(-S/3) + (1-x)(+1)
            = -xS/3 + 1 - x                 (Eq. 12.4)
Set equal:
 -xS/3 + 1 - x = -1/2
=> xS + 3x = 9/2
=> x = 9 / [2(S + 3)]                         (Eq. 12.5)

X’s indifference at threshold x:
- Attacker jams fraction y, with same conditional structure as Game #1
E_X(fold) = -1
E_X(call | x) = P(Y better)*(-S/3) + P(Y worse)*(+S/3)
              = (x/y)(-S/3) + ((y-x)/y)(+S/3)
              = (S/3)(y - 2x)/y
Set equal:
 (S/3)(y - 2x)/y = -1
=> S(y - 2x) = -3y
=> y = 2xS / (S + 3)

Substitute x from Eq. 12.5:
 x = 9 / [2(S+3)]
=> y = 2S * [9 / (2(S+3))] / (S+3)
=> y = 9S / (S + 3)^2                          (Eq. 12.6)

Canonical solution for S > 3:
  x*(S) = 9 / [2(S + 3)]
  y*(S) = 9S / (S + 3)^2

Relationship to Game #1:
- Formally identical to Game #1 thresholds with S replaced by S/3 (effective stack).
Game #1:
  x1(S) = 3 / (2 + 2S)
  y1(S) = 3S / (1 + S)^2
Game #2 with S_eff = S/3:
  x2(S) = x1(S/3) = 3 / [2 + 2(S/3)] = 9 / [2(S + 3)]
  y2(S) = y1(S/3) = 3(S/3) / (1 + S/3)^2 = 9S / (S+3)^2

**Für den Bot:** When the better hand’s edge per showdown is only S/3 instead of S, effective stack size shrinks by that factor and both optimal shove and call ranges widen sharply for a given nominal S. In NLHE, poor equity realization (board runouts, randomization) effectively compresses stack size, justifying much looser shove and call ranges than naive stack/blind ratios suggest.

## [0,1] Jam-or-Fold Game #2 — Game Value and Stack Regimes
Game #2 equilibrium EV across stack regions, using effective stack S_eff = S/3. Three distinct regimes of S with different strategy forms and EV expressions.

**Formel:** Define S as actual stack, S_eff = S/3 as effective showdown swing.

Three regions (per text):
1) Very small stacks: S <= 3/2
   - Both players play all hands (jam and always call)
   - Game is effectively symmetric
   - EV_Y(S) = 0

2) Intermediate stacks: 3/2 <= S <= 3
   - Y’s threshold y(S) = (2S + 3)/(4S) (attacker jams h >= y)
   - X calls with all hands (x = 1)
   - Attacker game value:
     EV_Y = P(Y folds)(-1/2) + P(Y jams) P(X>Y)*(+S/3)
          = -(1-y)/2 + y(1-y) S/3
   After algebra (from text):
     EV_Y(S) = (2S - 3) / (48S)      for 3/2 <= S <= 3

3) Large stacks: S >= 3
   - Use Game #1’s EV with S_eff = S/3
   - Game #1 EV: EV1(S_eff) = -1/2 + (3/4) S_eff / (1 + S_eff)^2
   Substitute S_eff = S/3:
     EV_Y(S) = -1/2 + (3/4)*(S/3) / (1 + S/3)^2
             = -1/2 + 27S / [4(S+3)^2]   for S >= 3

Continuity (per text):
EV_Y(S) is continuous at S = 3/2 and S = 3:
- For S <= 3/2: EV_Y = 0
- For 3/2 <= S <= 3: EV_Y = (2S - 3)/(48S)
- For S >= 3: EV_Y = -1/2 + 27S / [4(S+3)^2]

**Für den Bot:** Equilibrium structure (who has edge, and how big) can change qualitatively in different stack regimes with discontinuous optimal strategies even though EV is continuous. A NLHE bot should not expect its optimal jam/call thresholds to vary smoothly with stack size or pot size; piecewise regimes driven by equity vs. pot-odds shifts are normal.

## Effective Stack Size via Equity Realization
Mapping Game #2 (best hand 2/3 equity) to Game #1 via an effective stack height S_eff equal to the actual showdown swing.

**Formel:** Let S be nominal stack and suppose the better hand wins only a fraction p of the pot at showdown (here p = 2/3) and the worse hand wins (1-p), with blinds as before.
- Net gain/loss per showdown for winner/loser:
   winner: +(2p-1)S
   loser:  -(2p-1)S

Define effective stack size:
  S_eff = (2p - 1) * S

In Game #2, p = 2/3, so:
  S_eff = (2*(2/3) - 1) S = (4/3 - 1)S = (1/3)S

Any jam-or-fold solution from Game #1 can be re-used with S replaced by S_eff:
  x_2(S) = x_1(S_eff)
  y_2(S) = y_1(S_eff)
  EV_2(S) = EV_1(S_eff)   (up to blind normalization consistency)

Text demonstration:
Game 1: x_1(S) = 3/(2+2S), y_1(S) = 3S/(1+S)^2
Game 2: x_2(S) = 9/(2S+6), y_2(S) = 9S/(S+3)^2
And indeed x_2(S) = x_1(S/3), y_2(S) = y_1(S/3).

**Für den Bot:** Whenever the better hand’s equity at showdown is p<1, the effective stack height for a shove game is compressed to S_eff=(2p−1)S. A NLHE bot should scale its preflop jam/call frequencies based on effective, not nominal, stack: poor equity realization (multiway pots, boards that flip equities) widens optimal ranges substantially.

## Indifference Principle in Jam-or-Fold Games
Use indifference of threshold hands between available actions to determine optimal mixing frequencies and cutoffs.

**Formel:** Given a jam-or-fold game with continuous strength parameter h and threshold policies:
- Attacker Y: jam if h >= y, fold otherwise
- Defender X: call if h >= x, fold otherwise

At equilibrium:
1) Y’s threshold hand y must satisfy:
   E_Y(jam | h=y) = E_Y(fold | h=y)

   Generic form:
   E_Y(jam | y) = P(call | y)*EV_Y(jam & call) + P(fold | y)*EV_Y(jam & fold)
   E_Y(fold | y) = EV_Y(fold)

2) X’s threshold hand x must satisfy:
   E_X(call | h=x) = E_X(fold | h=x)

   Generic form:
   E_X(call | x) = P(Y stronger | jam)*EV_X(lose) + P(Y weaker | jam)*EV_X(win)
   E_X(fold | x) = EV_X(fold)

In uniform [0,1] games, P intervals map directly to interval lengths, so the conditional probabilities can be expressed via x and y:
   P(Y weaker | jam) = (y - x)/y
   P(Y stronger | jam) = x/y
leading to linear equations in x and y that solve equilibrium frequencies.

**Für den Bot:** Optimal jam/call strategies are found where the marginal indifference hands are exactly break-even between their options. A NLHE bot should tune preflop and postflop thresholds (e.g., bottom of value range, top of folding range) so that these hands are indifferent; this pins down correct bluffing and calling frequencies.

## Jam-or-Fold Game — Threshold Representation of Strategies
In monotone strength settings with two actions (invest or fold), optimal strategies are monotone thresholds rather than arbitrary mixed distributions.

**Formel:** Given continuous hand strength parameter h where larger h is better for one player (or smaller for the other, but fix an ordering) and binary decision invest vs. fold, and opponent also uses monotone response:
- Any strategy that invests with some hands below a folding hand and folds with some strictly better hands is strictly dominated by one that invests with all hands above some threshold and folds with all below.

Formalized for the attacker Y:
- If the set of jamming hands A has measure |A| = y (frequency y), then for any choice of A with that measure, jamming the top-y (or bottom-y, depending on monotone mapping) hands maximizes EV.

Consequently, strategy can be parameterized by a single scalar threshold y and similarly x for defender.

**Für den Bot:** In one-street jam-or-fold models with a monotone strength variable, equilibrium strategies are cutoffs, not arbitrary mixed subsets. A NLHE bot can safely model preflop shove/call/fold policies as simple thresholds in hand-strength metrics (e.g., preflop equity vs. range, or EV proxies) instead of complex non-monotonic mixes.

## Jam-or-Fold No-Limit Hold’em Toy Game (Qualitative)
Apply [0,1] jam-or-fold insights to an actual NLHE preflop shove-or-fold game with realistic equity distribution and use fictitious play to compute equilibrium ranges numerically.

**Formel:** Example 12.3 setup:
- Equal stacks S
- Blinds: SB(Y)=0.5, BB(X)=1
- Attacker can only jam to S or fold
- Defender can call or fold
- If called, full NLHE board is run, better 5-card hand wins full effective pot.

Unlike the [0,1] models:
- Hand equities are not uniform or near 0/1; even worst hands have non-trivial equity.
- Equities are non-transitive, so a simple 1D ordering is imperfect.

Fictitious play procedure (schematic):
1) Initialize strategy profiles σ_Y^0, σ_X^0 (e.g., initial jam/call ranges).
2) For iteration t:
   - Compute best response BR_X(σ_Y^{t}) that maximally exploits σ_Y^{t}.
   - Update σ_X^{t+1} = (1-α_t)σ_X^{t} + α_t BR_X(σ_Y^{t}), with α_t → 0.
   - Compute best response BR_Y(σ_X^{t+1}).
   - Update σ_Y^{t+1} = (1-α_t)σ_Y^{t} + α_t BR_Y(σ_X^{t+1}).
3) Repeat until convergence of strategies or EVs.

Because closed-form thresholds aren’t feasible, one uses brute-force enumeration of all starting-hand pairs with precomputed equity matrix EQ[h_Y, h_X] and explicitly computes EV of shoving/calling/folding against current opponent strategy to choose BR.

**Für den Bot:** For realistic NLHE preflop jam-or-fold situations, closed-form thresholds like the [0,1] models don’t exist; instead, a bot should approximate equilibrium shove and call ranges via iterative best-response (e.g., fictitious play) using a full precomputed equity matrix over starting hands.

## Fictitious play mixing with harmonic weights
Iterative best-response learning where current strategy is updated toward a maximally exploiting response with a decaying (e.g. harmonic 1/n) step size; converges to Nash in these finite games.

**Formel:** Given iteration t, mixing weight m_t (e.g. m_t = 1/t). Old strategy S_old, current best response S_new. Update:
S_next = (1 - m_t) * S_old + m_t * S_new

Componentwise for each information set I and action a:
S_next(I,a) = (1 - m_t) * S_old(I,a) + m_t * S_new(I,a)

**Für den Bot:** Use fictitious play or similar regret-style updates with decaying step sizes to iteratively approach equilibrium jam/call strategies for simplified subgames (e.g., preflop jam-or-fold) instead of hand-tuned charts.

## Jam EV vs tight calling range (ATs vs AA-only defender)
Expected value of an all-in shove with a specific hand against a defender that only calls with AA, parameterized by stack size S; used to find the exact stack where shoving becomes break-even.

**Formel:** Let:
- S = effective stack in big blinds (pre-blind posting, consistent with the excerpt)
- pot = 1.5 (blinds 0.5 and 1)
- p_call = probability defender has AA
- p_fold = 1 - p_call
- e = equity of our specific hand vs AA when called

For ATs vs AA-only range, given in text:
- p_call = 3/1225
- p_fold = 1222/1225
- e_ATs_vs_AA = 0.13336

Jam EV as function of S:
EV_ATs(S) = p_fold * pot + p_call * ( e_ATs_vs_AA * (2S) - S )

Plugging numbers:
EV_ATs(S) = (1222/1225)*1.5 + (3/1225) * (0.13336 * 2S - S)

Break-even stack S* solves EV_ATs(S*) = 0:
(1222/1225)*1.5 + (3/1225) * (0.13336 * 2S* - S*) = 0
=> S* ≈ 833.25

**Für den Bot:** When modeling jam-or-fold, compute per-hand EV against the precise calling range as a function of S and only add a hand to the shove range once its jam EV crosses 0 at that S, not based on naive hand strength vs random.

## Phase-transition style inclusion of hands in jam range
At specific critical stack sizes S*, a given hand switches abruptly from 0% to 100% jam frequency (or vice versa); the equilibrium best response can change discontinuously with small perturbations in S.

**Formel:** General principle: for hand h, define EV_jam(h, S) and EV_fold(h, S) = 0.
Critical stack size S*_h solves:
EV_jam(h, S*_h) = 0
At S > S*_h: EV_jam(h, S) < 0 → optimal frequency f_h(S) = 0
At S < S*_h: EV_jam(h, S) > 0 → optimal frequency f_h(S) = 1
At S = S*_h: EV_jam(h, S) = 0 → any 0 ≤ f_h(S) ≤ 1 is acceptable (indifference).

Example from text: ATs vs AA-only
EV_ATs(S) = (1222/1225)*1.5 + (3/1225)*(0.13336*2S - S)
Solve EV_ATs(S*) = 0 → S* ≈ 833.25
Thus f_ATs(S) jumps from 0 to 1 at S ≈ 833.25 when defender calls only with AA.

**Für den Bot:** Do not assume jam frequencies vary smoothly with stack; treat thresholds per hand: at each S, recompute best-response sets, since equilibrium ranges can change non-monotonically and discontinuously.

## Card removal dominance vs top pair dominance (ATs > KK vs AA-only)
When villain only calls with AA, hands containing an ace can outperform KK as jams because they halve the chance villain has AA (card removal), even though they fare worse when called.

**Formel:** Let h_1, h_2 be two candidate jamming hands.
EV_jam(h, S) = p_fold(h) * pot + p_call(h) * (e_h * 2S - S)
where:
- p_call(h) = P(villain has AA | hero holds h and jams)
- p_fold(h) = 1 - p_call(h)
- e_h = equity of h versus AA when called.

Hand h_1 is better jam than h_2 iff for the relevant S:
EV_jam(h_1, S) > EV_jam(h_2, S)

Although e_KK_vs_AA > e_ATs_vs_AA, for very large S we can have:
EV_jam(ATs, S) > EV_jam(KK, S)
primarily because p_call(ATs) << p_call(KK) via removal of aces from villain’s range.

**Für den Bot:** EV ordering of preflop jams must account for blocking of villain’s calling range; suited Ax and connectors often enter shove ranges earlier than their nominal ‘strength’ vs random would suggest, especially versus tight-calling opponents.

## Indifference condition for defender’s marginal call (AKs vs {AA, ATs, A5s})
Mix attacker’s jamming frequencies so defender’s best prospective additional calling hand (AKs) has zero EV from calling; this pins down optimal bluff/value mix within a given candidate jam set.

**Formel:** Given a discrete attacker jam range with hands h in {AA, ATs, A5s}, and a candidate defender call hand c = AKs, define for each h the contribution to c’s EV difference from calling:
ΔEV_c|h = (freq(h)) * (3/1225) * ( e_c_vs_h * 2S - S )

At S ≈ 833 (simplified as in text), precomputed contributions per *unit* frequency (3/1225 factor folded in):
ΔEV_AKs|AA = -1.5447 * AA%
ΔEV_AKs|ATs = 0.8353 * ATs%
ΔEV_AKs|A5s = 0.8085 * A5s%

Indifference (zero EV) condition:
(-1.5447) * AA% + 0.8353 * ATs% + 0.8085 * A5s% = 0
With AA% = 1 and (in the construction) A5s% = 1:
0.8353 * ATs% + 0.8085 * 1 = 1.5447
⇒ ATs% = (1.5447 - 0.8085) / 0.8353 ≈ 0.8773 (87.73%)

**Für den Bot:** When building jam ranges at a given S, explicitly adjust frequencies of marginal jam hands so that villain’s strongest fold/call borderline hand is indifferent; this yields GTO-like value/bluff proportions in discrete preflop shoving spots.

## Defender call threshold vs equity at small stacks
Closed-form equity threshold above which defender should call an all-in, as a function of stack size S, when pot is (S+1) and call cost is (S−1).

**Formel:** Given:
- S = stack size in big blinds (before blinds)
- Pot when facing the jam: pot = S + 1
- Call cost: C = S - 1
- x = defender’s equity vs attacker’s jamming range when he calls

Defender’s EV from calling:
EV_call = x * (2S) - (S - 1)
Indifference threshold EV_call = 0:
x * (2S) = S - 1
x = (S - 1) / (2S)

Defender should call iff:
Equity(hand vs jam range) > (S - 1) / (2S)

**Für den Bot:** Preflop, a bot can map stack depth S → minimum equity required to call shoves using x > (S−1)/(2S); comparing each hand’s equity vs villain’s shove range to this threshold yields an approximate optimal calling set for short-stack situations.

## Attacker jam threshold vs equity at small stacks (vs call-with-all)
Closed-form equity threshold for attacker’s shove to be profitable when defender calls with all hands, given stack size S and pot geometry.

**Formel:** Assuming defender calls 100% of hands:
- Attacker’s equity with a given hand vs defender’s entire range: y
- If jammed and called, pot = 2S, cost = S - 0.5 (because attacker already invested 0.5 blind)

Attacker EV from jamming:
EV_jam = y * (2S) - (S - 0.5)
Indifference threshold EV_jam = 0:
y * (2S) = S - 0.5

y = (S - 0.5) / (2S)

Attacker should jam iff:
Equity(hand vs call range) > (S - 0.5) / (2S)

**Für den Bot:** When modeling very short stacks where villain effectively calls everything, a bot should jam any hand whose equity vs random exceeds (S−0.5)/(2S); at ~1–2 blinds this means shoving essentially all hands is correct.

## Equity-based jam/call thresholds at specific small S (examples)
Concrete numeric thresholds and range consequences for specific S values: S=1.1, 1.412, 2, 3, illustrating that at very small S both players play almost all hands, then attacker starts dropping the lowest-equity hands as S grows.

**Formel:** General thresholds:
- Defender calls if x > (S - 1)/(2S).
- Attacker jams if y > (S - 0.5)/(2S) (vs call-all assumption).

Examples:
1) S = 1.1
   Defender call threshold: x > (1.1 - 1)/(2*1.1) = 0.1/2.2 ≈ 0.04545
   Attacker jam threshold: y > (1.1 - 0.5)/(2*1.1) = 0.6/2.2 ≈ 0.2727 (3/11)
   Since worst hand 32o has ~32.3% vs random > 27.27%, attacker jams all hands; defender calls all.

2) Critical S for 32o vs call-all case:
   Solve 0.323 = (S - 0.5)/(2S)
   0.323 * 2S = S - 0.5
   0.646S = S - 0.5
   (1 - 0.646)S = 0.5
   0.354S = 0.5 → S ≈ 1.412
   So for S > 1.412 attacker should stop jamming 32o vs call-all.

3) S = 2
   Defender: x > (2 - 1)/4 = 1/4.
   Attacker vs call-all: y > (2 - 0.5)/4 = 1.5/4 = 3/8.
   This excludes exactly 13 worst hands from attacker jamming; defender still calls all hands.

4) S = 3 (initial pass vs call-all):
   Attacker threshold: (3 - 0.5)/6 = 2.5/6 ≈ 5/12 ≈ 0.4167
   Defender threshold: (3 - 1)/6 = 2/6 ≈ 1/3 ≈ 0.3333
   This yields an initial attacker range excluding 34 worst hands; defender then starts folding some lowest-equity hands, and fictitious play refines from there.

**Für den Bot:** Implement fast functions to compute thresholds and decide for each hand at a given S whether it should be jammed/called/folded; for S≈1–2 blinds, the equilibrium is effectively jam-anything, call-anything, but by S≈3+ the very worst hands should be excluded from shoving first.

## General attacker EV with fold and call components (jam-or-fold)
Canonical EV expression for the attacker’s shove when defender may fold some fraction; depends on defender’s fold frequency and hero’s equity conditional on being called.

**Formel:** Let:
- S = stack size in big blinds (before blinds)
- pot_pre = pot before shove (e.g., 1.5 from blinds)
- C_att = attacker’s additional cost to shove (stack committed net of blind; e.g., S - 0.5)
- p_call = defender’s call probability vs our shove
- p_fold = 1 - p_call
- e = attacker’s equity vs defender’s calling range, conditional on call

If called, final pot = 2S and hero’s net EV from called branch is: e * (2S) - C_att.
Total EV from jamming:
EV_jam = p_fold * pot_pre + p_call * ( e * (2S) - C_att )

**Für den Bot:** For any preflop or postflop shove node, compute EV via separate fold and call branches using a single template; this lets the bot optimize bluff frequencies and candidate jam ranges numerically for arbitrary opponent call frequencies.

## General defender EV for a call vs fold (jam-or-fold)
Canonical EV expression for defending vs an all-in: call if equity vs shoving range times final pot exceeds call cost; gives direct equity threshold independent of explicit frequencies.

**Formel:** Let:
- S = stack size in big blinds (before blinds)
- pot_pre = pot before facing shove (e.g., S+1 or from context)
- C_def = additional chips to call (e.g., S - 1)
- x = defender’s equity vs attacker’s jamming range

When calling, final pot = 2S, so EV_call:
EV_call = x * (2S) - C_def
Indifference condition:
x * (2S) = C_def
x = C_def / (2S)

Call iff x > C_def / (2S).

**Für den Bot:** In any shove-facing decision, convert the situation to an implied stack S and call cost, compute the equity threshold x = call_cost / (2S), and compare each candidate hand’s equity vs villain’s shove range to this; it gives a clean MDF-like benchmark for shoving games.

## Jam-or-fold equilibrium construction via fictitious play over S
Using fictitious play, solve for optimal jam-or-fold ranges per stack size S: attacker starts with wide jams vs naive defense, defender best-responds with call/fold based on thresholds, attacker best-responds to that, repeated until convergence.

**Formel:** Algorithmic model (not a closed-form formula):
1) Initialize defender range D_0 (e.g., call-all or some heuristic).
2) Given D_t, for each hand h compute equity e_h_vs_Dt and EV_jam(h, S); choose attacker range A_{t+1} = {h : EV_jam(h, S) > 0}.
3) Given A_{t+1}, for each hand g compute equity e_g_vs_Atplus1 and EV_call(g, S); choose defender range D_{t+1} = {g : EV_call(g, S) > 0}.
4) Optionally mix previous and new strategies with weight m_t (harmonic 1/t):
   A_mix = (1 - m_t) * A_mix + m_t * A_{t+1} (probabilistic form)
   D_mix = (1 - m_t) * D_mix + m_t * D_{t+1}
5) Repeat until A_mix, D_mix stabilize for this S.

Repeat over grid of S to get jam-or-fold tables: for each hand, find maximal S at which it has non-negative jam EV (attacker) or call EV (defender).

**Für den Bot:** Precompute or dynamically approximate per-stack jam-or-fold charts using a fictitious-play loop over discrete S values; these charts give near-equilibrium preflop shove/call ranges for heads-up NLHE across stack depths and can be used as a fast policy or as a prior for deeper solvers.

## Jam-or-fold EV comparison at a given stack size
In shallow-stack all-in or fold games, a hand at the margin between jamming and not jamming is (approximately) indifferent between jamming and taking the next best line (e.g. min-raise/fold). This gives a concrete EV model to locate the jam-or-fold threshold.

**Formel:** Given:
- S = effective stack in units of big blind (BB)
- B = blind already in pot from defender (e.g. 1 unit)
- p_fold = probability defender folds vs jam
- e = equity of attacker’s hand vs defender’s calling range when called (probability of winning the all-in)

Jam EV (attacker):
EV_jam = p_fold * B + (1 - p_fold) * [ e * S + (1 - e) * (-S) ]
       = p_fold * B + (1 - p_fold) * S * (2e - 1)

If attacker instead raises small to R (R < S) and folds to a jam, with defender re-jamming frequency p_reraise:
EV_raise_fold = (1 - p_reraise) * B + p_reraise * (-R)

Jam-or-fold threshold (for a given borderline hand): solve S such that:
EV_jam(S) ≈ EV_raise_fold(S) (or ≥, to prefer jam).

**Für den Bot:** To decide whether a marginal hand should jam preflop at a given stack depth, compare EV_jam and EV_raise_fold using simple equity and fold-frequency estimates; for effective stacks ≲10 BB, the all-in line will often dominate and can be treated as near-optimal jam-or-fold.

## Practical shallow-stack jam-or-fold threshold
When stacks are sufficiently shallow relative to the blinds and antes, near-equilibrium preflop play can be well approximated by a pure jam-or-fold strategy. The book’s detailed analysis plus allowance for flat-calling shows a practical threshold around 10–13 blinds.

**Formel:** Heuristic condition (no explicit closed form):

Let S_eff be effective stack in units of "normalized big blind" where 2/3 of preflop pot (blinds + antes) is mapped to 1 unit.

If S_eff ≤ S_threshold, then restrict strategy to jam-or-fold:
- Typical S_threshold ≈ 10–11 when IP
- S_threshold ≈ 12–13 when OOP

Normalization when blinds/antes differ:
Let pot_pre = SB + BB + sum(antes).
Define scaling factor k = (2/3 * pot_pre)⁻¹, and normalized big blind = 1/k.
Then normalized effective stack is S_eff = S_chips * k.

Jam-or-fold applies if S_eff ≤ S_threshold.

**Für den Bot:** In HU or blind-vs-blind situations with effective stacks ≤ about 10–11 normalized blinds (a bit deeper if you’re OOP), your NLHE preflop engine can safely switch to pure jam-or-fold ranges derived from push/fold tables or solving, treating only the smaller stack as relevant.

## Jam frequency with 16-chip stacks HU (example calibration)
For a specific HU jam-or-fold freezeout with 16-chip stacks and blinds (1,2), the equilibrium button strategy jams an unexpectedly large proportion of hands (~61.7%). This provides a concrete calibration point for solver outputs and heuristic ranges.

**Formel:** Setup:
- Two players, S = 16 chips each.
- Blinds: SB = 1, BB = 2 (button posts SB, BB posts 2).
- Game restricted to preflop jam-or-fold by button; BB responds jam-call or fold.

Result from jam-or-fold tables:
- Optimal button all-in frequency ≈ 61.7% of all starting hands.

No closed-form general formula is given in the excerpt; value comes from precomputed tables/solving.

**Für den Bot:** In HU NLHE with ~8 BB effective (16 chips over 2-chip BB) and jam-or-fold restricted, an equilibrium preflop bot should open-jam around 60–65% on the button; significantly tighter play is leaving money on the table.

## AKQ half-street game: dominated strategy elimination
In the AKQ game with a single betting round, some river actions are strictly dominated and can be removed before solving. This reduces the game to a simple 2x2 mixed-strategy problem involving only bluffing with Q and calling with K.

**Formel:** AKQ Game #1 (P = 2, bet size = 1):
- Deck: {A, K, Q}, each player gets one card.
- Pot P = 2 units before betting, bet size = 1.
- High card wins at showdown.

Dominated for X (the caller):
- With A: folding is dominated by calling (never worse, sometimes better) ⇒ always call A.
- With Q: calling is dominated by folding ⇒ always fold Q.

Dominated for Y (the bettor):
- With K: betting is dominated by checking (never better) ⇒ always check K.
- With A: checking is dominated by betting (never better) ⇒ always bet A.

Reduced strategic choices:
- Y: bet-or-check with Q only.
- X: call-or-fold with K only.

This gives a 2x2 normal-form game in terms of:
- Y1 (Υ1): bet Q (bluff) vs X.
- Y2 (Υ2): check Q.
- X1 (X1): call with K.
- X2 (X2): fold K.

**Für den Bot:** On the river in NLHE, after accounting for obvious dominated actions (never fold the nuts to a one-bet pot, never call with literal zero-equity hands, don’t bet pure bluff-catchers that can’t fold out better), you can reduce many spots to a small game between a bluff-frequency variable and a call-frequency variable, which is then solved by indifference.

## AKQ Game #1 (P=2): payoff matrix and equivalence to Cops and Robbers
Once dominated strategies are removed in AKQ Game #1 with pot 2 and bet 1, the remaining 2x2 payoff matrix (from Y’s perspective) is strategically equivalent to the classic Cops and Robbers game. The unique mixed equilibrium is therefore known without further solving.

**Formel:** Let Y’s strategies: rows = {Y bets Q, Y checks Q}.
Let X’s strategies: columns = {X calls K, X folds K}.

Unscaled payoff to Y (per occurrence, from text):
          X calls K     X folds K
Y bets Q      -1/6          +1/6
Y checks Q    +1/6           0

Multiply by -6 (positive scaling and role swap) to match standard zero-sum matrix form:
          X calls K     X folds K
Y bets Q      +1           -1
Y checks Q    -1            0

This is identical (up to role labeling) to Cops and Robbers:
          Robber robs   Robber stays
Cop patrols     +1            -1
Cop rests       -1             0

Equilibrium mixed-strategy probabilities (from Cops and Robbers analysis):
- Y bluffs with Q with prob b* = 1/3.
- X calls with K with prob c* = 1/3.

**Für den Bot:** Many river spots reduce to simple 2x2 games whose structure (and thus mixed frequencies) is identical across situations; recognizing that your spot is a Cops-and-Robbers-type game lets the bot immediately infer correct call and bluff frequencies without re-solving from scratch.

## AKQ Game #1 (P=2): direct indifference solution
The AKQ half-street game with pot P=2 can be solved by writing each player’s EV as a function of the opponent’s strategy and imposing indifference between that player’s two remaining pure actions. This yields explicit optimal bluffing and calling frequencies.

**Formel:** Notation:
- P = 2 units, bet size = 1.
- b = Y’s bluff frequency with Q (probability bet with Q).
- c = X’s calling frequency with K (probability call with K).

Y’s indifference between bluffing and checking Q:
When Y has Q, X has {A,K} each with prob 1/2.
Pot size = 2; Y bets 1 when he bluffs.

EV_Y(bluff with Q):
<Y, bluff> = p(A)*(-1) + p(K)*[c*(-1) + (1 - c)*(+2)]
            = (1/2)*(-1) + (1/2)*[c*(-1) + (1 - c)*2]
            = 1/2 - (3/2)c
EV_Y(check> = 0

Indifference: 1/2 - (3/2)c = 0  ⇒  c = 1/3.

X’s indifference between calling and folding K (given Y bets A always and Q with freq b):
When Y bets, holding K, Y’s betting range = {A, Q_b}, with equal card priors.

EV_X(call K):
<X, call> = p(A|{A,Q})*(-1) + p(Q|{A,Q})*b*(+1)
           = (1/2)*(-1) + (1/2)*b*(+1)
           = -1/2 + (b/2)

EV_X(fold K):
If X folds and Y is bluffing with Q (prob 1/2 * b), X loses the pot 2:
<X, fold> = p(Q)*b*(-2) = (1/2)*b*(-2) = -b

Indifference: -1/2 + (b/2) = -b  ⇒  b(1 + P) = 1 with P=2 ⇒ b = 1/3.

So equilibrium:
- Y bluffs Q with probability b* = 1/3.
- X calls K with probability c* = 1/3.

**Für den Bot:** On a river with one bet left and pot = 2× bet size, if you always value-bet your nuts and never bluff 100% of your air, optimal play is to bluff about 1/3 as many combos as you value-bet, and call with about 1/3 of your bluff-catchers in the relevant region.

## General AKQ Game #2: equilibrium calling and bluffing frequencies as functions of pot size P
In the AKQ half-street game with arbitrary pot size P and bet size 1, equilibrium bluffing and calling frequencies are explicit functions of P. These reproduce the general α = 1/(P+1) bluffing ratio and the opponent folding fraction α to keep bluffs breakeven.

**Formel:** Setup:
- Pot size before betting: P (in units of bet size).
- Bet size: 1.
- Same dominated-strategy removal as P=2 case.
- Y always value-bets A and never bets K; choice is bluffing with Q freq b.
- X always calls A and never calls Q; choice is calling K freq c.

Y’s expected value bluffing Q (vs A/K equally likely):
EV_Y(bluff with Q) = (1/2)*(-1) + (1/2)*[c*(-1) + (1 - c)*(+P)]
                    = -1/2 - (1/2)c + (1/2)P - (1/2)Pc
Checking Q: EV_Y(check) = 0.

Indifference for Y:
-1/2 - (1/2)c + (1/2)P - (1/2)Pc = 0
Multiply by 2: -1 - c + P - Pc = 0
Rearrange: (P + 1)c = P - 1
⇒ c = (P - 1)/(P + 1).

X’s expected value with K:
Call:
EV_X(call K) = (1/2)*(-1) + (1/2)*b*(+1) = -1/2 + (b/2).
Fold:
When folding vs bluff, lose pot P with prob (1/2)*b:
EV_X(fold K) = (1/2)*b*(-P) = -bP/2.

Indifference:
-1/2 + b/2 = -bP/2
Multiply by 2: -1 + b = -bP
⇒ b(1 + P) = 1
⇒ b = 1/(P + 1) = α.

Total calling and folding frequencies across {A, K} when Y has Q:
- X always calls A (1/2 of hands), and calls K with freq c.
So total call fraction f_call = (1/2) + (1/2)c.
Total fold fraction f_fold = 1 - f_call.
Compute f_fold:
  f_fold = 1 - [1/2 + (1/2)*(P-1)/(P+1)]
         = 1/(P+1) = α.

So: the equilibrium bluff frequency b and the opponent’s folding frequency f_fold are both α = 1/(P+1).

**Für den Bot:** On a river facing a one-bet decision into pot P (in bet units) when your betting range is ‘nuts or air’ and villain can beat a bluff with some fraction of his range, GTO structure is: bluff with fraction α = 1/(P+1) of your value-bet combos, and your opponent should fold α of his total hands that beat a bluff.

## General α (alpha) bluffing ratio and MDF relationship in one-bet games
In a generic one-street game with pot size P and bet size 1, when a player bets a range consisting of value and bluff combinations and the opponent has some hands that beat a bluff, the equilibrium bluffing ratio and fold fraction are both α = 1/(P+1). This is the canonical GTO relation between pot odds, bluff frequency, and minimum-defense frequency (MDF).

**Formel:** Let:
- P = pot size before bet, in units of bet size.
- b = fraction of time bettor uses a bluff (air) at the bottom of range.
- v = fraction of time bettor uses a value hand.
- Opponent’s call vs fold optimum is such that bluffs are exactly 0-EV.

General relation (from Chapter 11, recovered in AKQ):
- Optimal bluff-to-value ratio (in terms of frequency of bluffing combos vs value combos) is:
  α = b / v = 1/(P + 1).
- Equivalently, the opponent’s fold fraction over the set of hands that beat a bluff is also α.

Sometimes written in MDF terms:
- Call (defend) fraction MDF = 1 - α = P/(P + 1).

Bluff 0-EV condition (simplified):
Let F be opponent’s fold frequency (over all hands he reaches decision with).
Then EV(bluff) = F*P - (1 - F)*1 = 0 ⇒ FP = 1 - F ⇒ F = 1/(P + 1) = α.

**Für den Bot:** For any river bet size B into pot P0 in NLHE, target approximate equilibrium: bluff/value ratio α = B / (P0 + B) inverted as α = 1/(P0/B + 1), and ensure your defending ranges vs that bet size have MDF ≈ P0 / (P0 + B); this is the backbone of sizing-dependent GTO frequencies.

## Value of AKQ Game #2 to the bettor as function of P
Given the equilibrium strategies in AKQ Game #2, the overall EV of the game for the bettor (Y) can be expressed explicitly as a function of P. It converges to a constant as P→∞ and ceases to apply when P≤1 (bluffing never profitable).

**Formel:** From the text’s weighted expectation table (p(matchup)=1/6 for each ordered pair (Y,X)):

Matchups and values to Y (the second player in their notation):
- (A, K): 0     with prob 1/6 => contribution 0
- (A, Q): -1/(P+1) with prob 1/6 => contribution -1/[6(P+1)]
- (K, A): 0     with prob 1/6 => contribution 0
- (K, Q): +P/(P+1) with prob 1/6 => contribution P/[6(P+1)]
- (Q, A): 0     with prob 1/6 => 0
- (Q, K): 0     with prob 1/6 => 0

Total value of game to Y:
V_Y(P) = (P - 1) / [6(P + 1)].

Asymptotics:
- As P → ∞, V_Y(P) → 1/6.
- At P = 2 (AKQ Game #1), V_Y(2) = (2 - 1)/(6*3) = 1/18.

Domain restriction:
- The solution with bluffs is only valid for P > 1.
- For P ≤ 1, Y never bluffs, and the game’s structure changes discontinuously.

Bluffing threshold:
- For P just above 1, α = 1/(P+1) is close to 1/2; e.g.
  P = 2 → α = 1/3,
  P = 1.5 → α = 2/5,
  P = 1.1 → α = 10/11,
  P ↓ 1 → α → 1/2 then at P = 1, bluffs vanish (Y’s best response is to never bluff).

**Für den Bot:** The EV edge from having the betting option grows with pot size and caps at a finite constant; in large pots, the bettor’s extra EV is mostly from value-betting thinly, not from bluffing heavily, while when P is barely >1 the GTO solution uses extremely high bluff frequencies but the game value remains modest.

## Bluff profitability threshold in one-bet games (P = 1 cutoff)
In AKQ Game #2 and, by extension, similar one-bet games, there is a critical pot size P* where bluffing ceases to be profitable even if the opponent folds all non-nut bluff-catchers. For the symmetric AKQ setup this cutoff is P = 1, where Y’s best response is to never bluff.

**Formel:** Consider Y’s EV when bluffing Q against an opponent who folds all K (i.e., worst-case for X in terms of folding too much). When X has A he always calls and Y loses 1; when X has K and folds, Y wins P.

EV_Y(bluff | X folds all K) = (1/2)*(-1) + (1/2)*(+P) = (P - 1)/2.

Bluff profitable only if EV_Y(bluff) > 0 ⇒ (P - 1)/2 > 0 ⇒ P > 1.

At P = 1:
EV_Y(bluff) = 0 even if X overfolds maximally. Any realistic calling adds negative EV, so the equilibrium has:
- b* = 0 (never bluff).
For 0 < P < 1:
- Bluffing is strictly -EV for any X strategy; optimal is pure value-betting A only.

**Für den Bot:** On rivers where the bet size is large relative to the pot (P small in bet units, especially P≤1), equilibrium often has very low or even zero bluffing frequency; your NLHE bot should avoid auto-constructing big-bluff ranges when its offered pot odds are too poor for the bluffer, even if the opponent might overfold.

## No‑limit clairvoyant half‑street game: optimal bluffing ratio α(s)
In any single‑bet no‑limit spot with pot = 1 and bet size s, if bettor has only pure nuts or pure air, the unique equilibrium bluff:value ratio that makes caller indifferent is α = s/(1+s).

**Formel:** alpha(s) = s / (1 + s)

Caller must fold fraction alpha(s) of his hands that beat a bluff and call with 1 - alpha(s).

**Für den Bot:** For any chosen bet size s (as a fraction of the pot) in a one‑street polar spot, set bluff combos ≈ alpha(s)*value combos, with alpha(s)=s/(1+s); design calling ranges expecting opponents to fold that same fraction vs balanced play.

## No‑limit clairvoyant half‑street game: EV as function of bet size
When bettor Y value‑bets and bluffs with ratio α(s)=s/(1+s) so that bluffs break even, Y’s total EV as a function of bet size simplifies to linear in s times nut frequency.

**Formel:** Let pot = 1, bet = s, y = P(Y has nuts).
With Y’s bluffs chosen so they break even and X calling accordingly,

f(s) = EV_Y(s) = y * s / (1 + s)

**Für den Bot:** In perfectly polar spots where your range is y fraction value and (1−y) fraction air, your EV grows monotonically with bet size when stacks are deep enough; absent stack/preservation constraints, shoving is best.

## Clairvoyant game with strong value density: ‘always fold’ caller equilibrium
If bettor’s value density is sufficiently high relative to air (e.g. y=3/5 nuts, 2/5 air, deep stacks), the caller’s best response to any finite bet size is to fold 100% of hands; any calling frequency yields strictly negative EV for caller and non‑maximal EV for bettor unless caller folds always.

**Formel:** Example: pot=1, stack=5 (s=5), y=3/5, (1−y)=2/5.
If X calls fraction c of hands vs Y betting all hands for s=5:

EV_Y(bluff | c) = (1−y) * [ (1−c)*1  − c*5 ]
EV_Y(value | c) = y * [ c*5 ]

X can increase his EV by setting c = 0, giving
EV_Y = (1−y)*1 = 2/5.
Any c>0 makes X strictly worse and allows Y to do at least as well by exploiting the calls.

**Für den Bot:** In NLHE spots where your range is very value‑heavy versus villain’s, especially near river with big stacks, optimal defense for villain can be folding everything vs any bet size; your bot should sometimes shove all hands (value and bluffs) when its range is that strong and expect correct opponents to overfold to 0% calling.

## No‑limit AKQ half‑street: optimal bet sizing function f(s)
In AKQ half‑street no‑limit with pot=1 and large stacks, Y chooses a single bet size s for all A and Q used as bluffs. For each s, X’s equilibrium calling frequency and Y’s resultant EV f(s) can be expressed analytically; Y then chooses s maximizing f(s).

**Formel:** Setup: Deck {A,K,Q}, equally likely; X and Y each get one card; X checks, Y may bet s∈(0,1] (fraction of pot) or check. X calls optimal vs Y’s strategy.

From α(s) = s/(1+s), X must call with total frequency 1−α = 1/(1+s).
He always calls with A (prob=1/2 conditional on non‑Q), so remaining call frequency comes from K only:

c_K(s) = 2 * (1/(1+s) − 1/2)
        = (1 − s) / (1 + s)

Y’s EV from the game as a function of s (considering only A vs K interactions, 1/6 of all hands):

f(s) = EV_Y(s) = [prob(A vs K)] * [gain per A v K] 
     = (1/6) * s * (1 − s) / (1 + s)

Up to positive constant, maximize g(s) = s(1−s)/(1+s).
Derivative gives optimum:

f'(s) = 0 ⇒ s^2 + 2s − 1 = 0 ⇒ s = −1 ± √2
Feasible root: s* = √2 − 1 ≈ 0.4142.

**Für den Bot:** In simple polar river spots with one bluff candidate and one medium-strength bluff‑catcher in villain’s range, the optimal pot‑fraction bet size is often near s ≈ √2−1 ≈ 41%; this is a useful heuristic target for value+bluff bets in analogous NLHE situations.

## ‘Golden mean of poker’ r = √2 − 1 and associated frequencies
In the AKQ no‑limit half‑street polar game where villain has half pure bluff‑catchers and half pure nuts, the unique optimal pot‑size fraction is r = √2 − 1, with derived optimal bluffing and calling frequencies.

**Formel:** r = √2 − 1 ≈ 0.41421356.

Optimal strategy in such a polar two‑hand‑class game:
- Bet size: s* = r (fraction of pot)
- Bluffing frequency (per value hand): alpha(r) = r / (1 + r) = 1 − 1/√2 ≈ 0.2929
- Total calling frequency of opponent vs this strategy: 1/(1 + r) = 1/√2 ≈ 0.7071

So:
bluff:value ratio = 1 − 1/√2
opponent calls total fraction 1/√2 (all nuts + some bluff‑catchers).

**Für den Bot:** For many river polar spots with symmetric ranges (opponent has ~50% pure nuts, ~50% pure bluff‑catchers vs your polarized betting range), betting around 40% pot with bluff:value ≈ 0.29 and expecting villain to call ~71% of hands (all nuts + some bluff‑catchers) is near‑optimal; this can seed your bet‑size and frequency priors.

## AKQ no‑limit: calling frequency for bluff‑catchers given bet size
In AKQ NL half‑street, once Y picks s and bluffs in equilibrium, X’s mixed strategy over bluff‑catchers (K) is pinned to make Y’s bluffs break even while always calling with A.

**Formel:** Total call frequency needed:
C_total = 1 / (1 + s).

Let C_A = 1/2 (X always calls with A when he has A/K mix equally likely in calling region), then:

C_total = (1/2) * P(A in calling region) + (1/2) * P(K in calling region)
But in the simplified derivation they write directly:

c_kings(s) = 2 * (1/(1 + s) − 1/2) = (1 − s) / (1 + s)

So X calls with kings with frequency c_kings(s) and folds remaining kings.

**Für den Bot:** Given a chosen pot‑fraction s in a polar river spot against a range with top and middle classes (like A,K), optimal calling frequency for the middle class should fall as s increases following c_mid(s) ≈ (1−s)/(1+s); the bot should thin out bluff‑catcher calls when using bigger bet sizes.

## [0,1] half‑street no‑limit: caller’s indifference function x(s)
In the continuous [0,1] half‑street no‑limit game, X chooses a calling threshold function x(s) such that for any bet size s, Y is indifferent between bluffing at the lower edge and checking; this enforces a specific decreasing call threshold in s.

**Formel:** Let x(s) be X’s minimum hand strength that can profitably call bet size s.
Imposing that Y is indifferent at his bluff/value boundary y (probability space) leads to:

y − x(s) − s x(s) = k       (constant in s)
⇒ x(s) = (y − k) / (1 + s)

Define X0 = x(0) (the threshold below which X never calls, even to tiny bets). Then y − k = X0, so

x(s) = X0 / (1 + s)        (Equation 14.2)

**Für den Bot:** In continuous‑strength river models, optimal calling thresholds should scale roughly like 1/(1+s): the weaker the bet size, the wider you defend; for very large bets s, you should only continue with the very top of your range.

## [0,1] half‑street no‑limit: bettor’s value‑bet frontier y(s)
In the [0,1] game, Y chooses for each bet size s a hand‑strength cutoff y(s) above which he value‑bets, matching that to a bluff region below; value‑bet EV is maximized when y(s) solves a first‑order condition involving x(s).

**Formel:** Given X’s threshold x(s) = X0/(1+s), Y’s EV when value‑betting a hand of strength y with bet size s:

EV_Y_value(y,s) = (prob called and loses)(−s) + (prob called and wins)(+s)
                 = y(−s) + (x(s) − y)s
                 = s x(s) − 2 s y.

Maximizing over y yields:
∂/∂y [s x(s) − 2 s y] = −2s = 0  (the text skips algebra details and directly states the frontier)
Using their calculus and equilibrium conditions, they obtain:

s x'(s) + x(s) − 2 y = 0
Substitute x(s) = X0/(1+s) and x'(s) = −X0/(1+s)^2:

s(−X0/(1+s)^2) + X0/(1+s) − 2y = 0
⇒ X0/(1+s)^2 − 2y = 0
⇒ y(s) = X0 / [2 (1 + s)^2]

**Für den Bot:** Optimal value‑bet thresholds in continuous river spots should fall faster than 1/(1+s); you value‑bet thinner (smaller y) for small bets and much thicker (only strong hands) as s grows, roughly like 1/(1+s)^2 in this stylized model.

## [0,1] half‑street no‑limit: infinite continuum of bet sizes in equilibrium
In the no‑limit [0,1] half‑street game, Y’s optimal strategy is to use a continuum of bet sizes, each tied to a specific hand strength via y(s), while X responds with a continuum of thresholds x(s); despite the apparent information leakage, equilibrium holds because X cannot raise and Y always pairs value bets with correct bluff mass.

**Formel:** Strategy structure (qualitative):
- X: On [0, X0], calls following threshold x(s) = X0/(1+s) vs bet size s; on (X0,1], always folds.
- Y: On [0, y(0)], value‑bets according to y(s) = X0 / [2(1+s)^2] (each y uses a unique s); below his bluff/value threshold, uses matching bluff mass to satisfy α(s).

Key equilibrium relations already summarized:
1) x(s) = X0 / (1 + s)
2) y(s) = X0 / [2 (1 + s)^2]

**Für den Bot:** In rich NLHE rivers (continuous range strengths), GTO can mix many bet sizes tied to different parts of the value range plus matching bluffs; your bot should allow multi‑sizing policies, not just a single bet size, and coordinate bluff mass with value mass for each size.

## [0,1] half‑street continuous betting/bluffing regions
In the [0,1] continuous half‑street game, Y’s optimal value‑bet region and bluff‑bet region are defined by continuous betting functions. The size of each infinitesimal ‘betting slice’ dy corresponding to a quality slice ds follows the usual bluff:value ratio α(s) = s/(1+s). Integrating these differentials yields the total size of Y’s bluff region and pins down the threshold x0 at which Y starts betting.

**Formel:** Given Y’s value‑betting function over strength s ∈ [x0,1]:
y(s) = x0 / (2 * (1 + s)^2)

Value‑bet differential:
dy = x0 / (1 + s)^2 * ds

Local (infinitesimal) bluff:value ratio in this game:
bluff:value at strength s = s / (1 + s)

So bluff‑bet differential mass is:
dB(s) = (s/(1+s)) * dy = s * x0 / (1 + s)^3 * ds

(The excerpt simplifies to a specific form written as s x0 / (1+s)^4 ds; that power is tied to the exact way they normalize; conceptually, it is proportional to s and to dy with an extra (1+s) factor in the denominator.)

Total bluffing region size B is the integral of this differential over s from x0 to 1:
B = ∫[s=x0..1] s * x0 / (1 + s)^4 ds

Substitute t = 1 + s. Limits: s = x0 → t = 1 + x0, s = 1 → t = 2.
B = x0 * ∫[t=1+x0..2] (t-1) / t^4 dt
= x0 * [ -1/(2 t^2) + 1/(3 t^3) ]_{t=1+x0}^2

For the equilibrium choice they derive:
B = (1/6) * (1 - x0^? )   (in the book this simplifies; the excerpt’s last line is garbled but the numeric relationship they use is)
x0 + B = 1
x0 + (1/6)*(1 - x0_term) = 1
Leading to the concrete solution given explicitly later:

x0 = 6/7

And the final equilibrium strategy functions (value‑bet region for X, Y in this [0,1] construction) are:

x(s) = (6/7) * (1 + s)
y(s) = (3/7) * (1 + s)^2

In words: the betting mass density increases with hand strength (1+s) for X and (1+s)^2 for Y, with total normalizations 6/7 and 3/7.

**Für den Bot:** In continuous‑distribution spots (e.g., river with many combos ordered by EV), optimal betting regions can be described by smooth functions x(s), y(s) rather than discrete thresholds, and the local bluff:value ratio still follows an α‑type structure tied to s/(1+s). For a NLHE bot, approximate this by bucketing strength into many bins, applying local MDF/α logic per bin, and letting the betting fraction be an increasing function of hand strength instead of a hard cut‑off.

## Global size of bluff region and threshold x0 in [0,1] half‑street game
The total mass of Y’s bluffing range in the [0,1] half‑street game is a fixed fraction of the entire distribution. Setting the start of bluffing immediately after the value‑bet threshold x0 and requiring that the value‑bet and bluff‑bet regions exactly fill [x0,1] pins down x0. This matches the idea that, in equilibrium, your total number of bluff combos is a fixed multiple/fraction of your value combos integrated over the distribution.

**Formel:** From the differential construction:
Total size of bluff region (mass of hands used as bluffs):
B = ∫ bluff differential over s from x0 to 1
The book integrates and obtains:
B = (1/6) * (1 - x0_term)   (specific functional form is simplified in the text and the last line is printed as 1/6 * ◊; the important step actually used is the numeric relationship below.)

They then use the fact the betting region runs from x0 to 1, and the bluff region is contiguous starting at x0:

x0 + B = 1

Solving this equilibrium condition (with the actual integrated form of B) yields:

x0 = 6/7

Thus total bluff mass is:
B = 1 - x0 = 1/7

And Y’s strategy in this solved [0,1] game uses 1/7 of hands as bluffs overall:
Total bluffs / total hands = 1/7.

**Für den Bot:** Equilibrium often fixes a *global* bluff: value ratio across the whole betting region (here total bluff mass is 1/7 of the distribution). In NLHE, beyond local MDF on specific node lines, ensure that your total number of bluff combos at a node is a controlled fraction of your total betting combos, not just locally correct by sizing. When tuning heuristics, enforce a global ‘bluff budget’ that scales with pot size and payoff asymmetry.

## Full‑street AKQ Game #4 – canonical α and MDF relationships
In the full‑street AKQ limit game with pot P and bet size 1, there is a single bet size. X can bet or check; Y can call/fold vs bet, and bet/check in position. The same α = 1/(P+1) and MDF = (P-1)/(P+1) from the half‑street games reappear. The bluff:value ratio when betting and the fold/call frequencies are fixed by indifference of caller and bluffer.

**Formel:** Definitions:
P = pot size in units (P > 1)
Bet size = 1
α = 1 / (P + 1)

Canonical relationships:
1) Bluff:value ratio for a single bet (X’s or Y’s) when value hands beat bluffs and risk is 1 to win P:
   bluff:value frequency ratio = α = 1/(P+1)

2) Caller’s minimum‑defense frequency (MDF) vs that bet: caller must fold exactly an α fraction of the hands that beat a bluff, thus must *call* with:
   MDF = (P - 1)/(P + 1)

In AKQ Game #4 specifically:
– When X bets with {A (value), Q (bluff)}, Y calls with his kings so that X is indifferent to bluffing Q:
   cy = (P - 1)/(P + 1)   (fraction of Y’s K that call vs X’s bet)

– To make Y indifferent calling K vs fold when facing X’s bet, X’s bluff:value ratio must satisfy:
   b/x = 1/(P + 1) = α            (equation (15.1))
where x is X’s betting frequency with A and b is his bluffing frequency with Q.

– When X checks and Y now value‑bets A and bluffs Q with the same α ratio, X’s check‑calling fraction with K, c, must make Y indifferent to bluffing. With X checking fraction (1-x) of A and all K, total hands after check:
   Total_hands = (1/2)*(1 - x) + (1/2)

Indifference condition (fold α proportion of hands that beat bluffs) leads to:
   (1/2) * (1 - c) = α * Total_hands
   ⇒ 1 - c = α(2 - x)
   ⇒ c = 1 - 2α + αx             (equation (15.2))

Check consistency:
– If x = 0 (X never bets A), then:
   c = 1 - 2α = (P - 1)/(P + 1)  (MDF vs in‑position bet in half‑street game)
– If x = 1 (X always bets A), then:
   c = 1 - α = P/(P + 1)

These show how X’s betting frequency with A shifts his optimal check‑call frequency with K.

**Für den Bot:** For any single bet size b into pot P in NLHE (no further raises), approximate α ≈ b/(P+b) and MDF ≈ P/(P+b+1) vs that bet, but in the classic MoP normalization with bet=1 these reduce to α = 1/(P+1) and MDF = (P-1)/(P+1). Use these as default: choose your bluff combos so bluff:value ≈ α and defend vs bets such that you fold roughly α of the hands that are ahead of the bluffs.

## Full‑street AKQ Game #4 – X’s check‑calling frequency as a function of x
When X can choose to bet some fraction x of his strongest hands (aces) and use a fixed bluff:value ratio with his weakest hands (queens), the optimal fraction of kings that X should check‑call must keep Y indifferent to bluffing with Q after check. This produces a linear relation between X’s A‑betting frequency x and his K‑call frequency c.

**Formel:** Let:
P = pot size, bet = 1
α = 1/(P+1)

x = fraction of A that X bets initially
c = fraction of K that X check‑calls after checking

X checks all K, and checks (1 - x) of A.
Total hands in X’s checking range before Y acts:
   Total_hands = (1/2)*(1 - x) + 1/2 = 1 - x/2

Y, when checked to, bets all A and α of Q. For Y’s Q‑bluffs to be indifferent, X must fold α of the hands in his checking range that beat a bluff (i.e., primarily kings, once A are accounted for). This yields:

(1/2) * (1 - c) = α * (Total_hands)
⇒ 1 - c = α(2 - x)
⇒ c = 1 - 2α + αx        (equation (15.2))

Special cases:
– x = 0 (X never bets A):
   c = 1 - 2α = (P-1)/(P+1)
– x = 1 (X always bets A):
   c = 1 - α = P/(P+1)

**Für den Bot:** When you vary your betting frequency with strong hands (e.g., sometimes slow‑playing top of range), your optimal bluff‑catching frequency with medium hands must adjust linearly to maintain opponent’s indifference to bluffing. A NLHE bot should couple its slow‑play frequency with its call frequency in the check line rather than choosing them independently.

## Full‑street AKQ Game #4 – Game EV as a function of X’s A‑bet fraction x
Given all the indifference‑based frequencies (α, MDF, bluff:value), the only remaining free variable in AKQ Game #4 is X’s betting frequency x with A. The overall game EV to Y is linear in x, so the equilibrium x is at a boundary (0 or 1) depending on P. This is a template for optimizing over a free strategy parameter via EV calculus.

**Formel:** From the case analysis (6 equiprobable matchups (X,Y) ∈ {A,K,Q}×{A,K,Q}, ignoring symmetric ones with no action), the value to the second player Y per random deal is:

EV_Y(x, P) = [ x * (-1 + 3α) + 1 - 2α ] / 6

where α = 1/(P+1).

Derivation sketch:
Cases and values to Y:
(A,K):  X bets with prob x, Y calls with prob (1 - 2α), Y’s EV = -x(1 - 2α)
(A,Q):  X checks with prob (1 - x), Y bluffs Q with prob α, EV = -α(1 - x)
(K,A):  X checks; Y bets A always; X calls with prob 1 - 2α + αx, EV = 1 - 2α + αx
(K,Q):  X checks; Y bluffs Q with prob α, and EV = α(1 - x)
(Q,A):  X bluffs with prob αx, Y calls always with A, EV = αx
(Q,K):  X bluffs with prob αx, Y calls with prob (1 - 2α), but overall bluffer’s net must be zero by indifference, so EV = -αx

Summing and dividing by 6 gives the compact form:
EV_Y(x, P) = (x(-1 + 3α) + 1 - 2α)/6

Now plug α = 1/(P+1):
-1 + 3α = -1 + 3/(P+1) = ( - (P+1) + 3 )/(P+1) = (2 - P)/(P+1)

Thus EV_Y is decreasing in x when P > 2 (coefficient (2 - P) < 0), and increasing in x when 1 < P < 2.
Therefore:
– If P < 2: EV_Y increases with x → X chooses x* = 0 (never bet A).
– If P > 2: EV_Y decreases with x → X chooses x* = 1 (always bet A).

Equilibrium strategies:
If P < 2:
 X: Checks all hands; calls with A and (P-1)/(P+1) of K vs bet.
 Y: Bets all A, bluffs 1/(P+1) of Q.

If P > 2:
 X: Bets all A and 1/(P+1) of Q; calls with P/(P+1) of K vs bet.
 Y: If X checks, bets all A and 1/(P+1) of Q; if X bets, calls with all A and (P-1)/(P+1) of K.

**Für den Bot:** Whenever your simplified model has a free parameter (like how often to bet a class of strong hands), write total EV as a function of that parameter and optimize it—often the optimum is at 0 or 1 (pure strategy). In NLHE solve components (e.g., shove frequency, 3‑bet frequency) by constructing such EV(x) expressions from ranges and equities, then maximizing EV instead of guessing mixed fractions.

## Jam‑or‑fold / spread‑limit extension (AKQ Game #5) and normalization of EV
AKQ Game #5 adds a smaller bet size (1 unit) to a game previously solved at larger bet size (2 units). Because X is indifferent between betting and checking A at P=2 in Game #4, allowing an extra bet size in Game #5 does not change the base equilibrium value if players ignore it. Then they check if deviating to the new smaller size can improve EV. EV scales linearly with bet size, so you can normalize analysis to unit bet and then rescale.

**Formel:** Setup:
– AKQ Game #4 with pot = 2, bet size = 1 has solution where X is indifferent to betting/checking A at P=2. The value to Y is:
   f(1, P) = (x(-1 + 3α) + 1 - 2α)/6

At P = 2, we have α = 1/(2+1) = 1/3 and X can choose x = 0 (check dark) without losing value.
Plugging x = 0, α = 1/3 into f gives:
   f(1, 2) = (0 * (-1 + 3*(1/3)) + 1 - 2*(1/3)) / 6
           = (1 - 2/3) / 6
           = (1/3) / 6
           = 1/18
This EV is *normalized to bet size 1*.

In Game #5, pot = 4 and one of the allowed bet sizes is s = 2 (half‑pot) which corresponds to the same relative size as the previous game. To map EV from unit bet game to s=2 game, multiply by s:
   f(s=2, P=4) = 2 * f(1,2) = 2 * (1/18) = 1/9

This is the equity (for Y) if both players play as though only the 2‑unit bet exists. Next, they analyze if a 1‑unit bet can improve someone’s EV by re‑doing the α and MDF logic at the smaller size, but that part is beyond this excerpt.

**Für den Bot:** Normalize toy calculations to bet=1, compute EV and optimal frequencies there, then rescale linearly by actual bet size s when the game is structurally identical. For multiple bet sizes in NLHE, treat each size as its own subgame with its own α, MDF, and EV profile, and only adopt a size in strategy if it strictly improves EV over the others.

## Strategy as distributions over complex actions (bet / check‑call / check‑fold)
In full‑street games, what look like multiple sequential decisions for X (bet vs check first, then call vs fold later) are better modeled as *single composite actions* from the start: bet now; or check and later call; or check and later fold. Each composite action is chosen for a fraction of the hand distribution. This is the natural way to write payoff matrices and derive equilibrium in multi‑street (or multi‑decision) games.

**Formel:** Instead of modeling X’s decisions as two independent nodes with actions:
– First node: Bet or Check
– Second node (after Check, facing Y’s bet): Call or Fold

We define *strategic options* for X as composite actions:
– B: Bet (with a given hand)
– Cc: Check and call vs a bet
– Cf: Check and fold vs a bet

For each hand h in X’s possible holdings, his strategy is a distribution over {B, Cc, Cf}:
   σ_X(h) = (p_B(h), p_Cc(h), p_Cf(h))
with p_B(h) + p_Cc(h) + p_Cf(h) = 1.

Similarly Y’s composite actions vs a bet are Call or Fold, and vs a check are Bet or Check. The payoff matrix is written in terms of these composite actions, e.g. (from simplified AKQ matrix):
– For X=A, Y=K:
   X:B vs Y:Call → payoff +1 to X, -1 to Y
   X:Cc vs Y:Bet → +1 to X, -1 to Y
   X:Cf vs Y:Bet → +P to Y, -P to X
etc.

Equilibrium conditions then are linear constraints on σ_X(h), σ_Y(h), solved by indifference of each pure composite action in support.

**Für den Bot:** Treat your strategy at a node as choosing complete *lines* (bet now; check‑call; check‑fold) rather than isolated node actions. For a NLHE bot, work at the level of plan‑trees: assign probabilities over (bet size, future continue decision) bundles for each combo, then learn/match the MoP bluff:value and MDF conditions for each line.

## Preemptive bet with medium strength (AKQ, spread limit)
Betting a hand that cannot value-bet or bluff in the usual sense, purely to preempt the opponent’s profitable bluffs with a larger sizing.

**Formel:** EV_check(K) = -2/3
EV_preemptive_bet_1(K) = -1/2
ΔEV = EV_preemptive_bet_1(K) - EV_check(K) = 1/6

Y’s raise-bluff frequency q solves:
(pot_gain_when_bluff_works) * P(X has king and bet) * q = ΔEV
(5) * (1/2) * q = 1/6  =>  q = 1/15

**Für den Bot:** Medium-strength river hands can be bet for a *less negative* EV than checking when they reduce opponent’s future bluffing opportunities with larger sizings; implement a search for such preemptive bets in multi-size trees.

## Raise-bluff frequency to neutralize preemptive bet (AKQ, raise to 3 total)
Defender chooses a raise-bluff frequency so that the bettor is indifferent between checking and making a preemptive bet with a medium hand; the target is *indifference of the betting decision*, not indifference of calling vs folding to the raise.

**Formel:** Let q = Y’s raise-bluff frequency over queens when facing X’s bet of 1.
Each successful bluff when X has K gains Y 5 units (risking 2 when called by A):
(5) * P(X has K) * q = 1/6
With P(X has K)=1/2, q = 1/15

Y’s EV per raise-bluff (conditional on bluffing):
EV_bluff = P(X has K)*5 - P(X has A)*2
To make Y indifferent to raise-bluffing overall, X’s A,K betting mix must satisfy:
P(X has K | bet) / P(X has A | bet) = 2/5   (so EV_bluff = 0).

**Für den Bot:** When you preemptively bet medium hands, expect optimally that villain will sometimes raise-bluff, but typically just enough to erase your edge from betting vs checking, not to make you call- indifferent; your A:K betting proportion should force their raise-bluffs to break even.

## Value-raise vs preemptive bet: A:K betting ratio 5:2 (spread-limit AKQ)
To make opponent indifferent to raise-bluffing, the bettor sets an A:K composition such that raise-bluffs have zero EV.

**Formel:** Y’s raise-bluff when X’s betting range is {A,K}:
Gain = +5 when X has K, Loss = -2 when X has A.
Let pA = P(X holds A | bet), pK = P(X holds K | bet).
EV_bluff = 5 pK - 2 pA
Indifference: 5 pK - 2 pA = 0 and pA + pK = 1
=> pK/pA = 2/5.
=> X must bet A,K in ratio A:K = 5:2.
If X bets 100% of aces, he must bet 40% of kings.

**Für den Bot:** When adding medium-strength hands to a betting range that can face raise-bluffs, set the proportion of strong to medium hands so that villain’s raise-bluffs realize zero EV; this often yields a specific A:K (or value:bluff-catcher) ratio like 5:2.

## Final spread-limit AKQ mixed strategy with two bet sizes
Equilibrium with two bet sizes and preemptive bets: optimal mixed frequencies for X and Y on bet/check, call/fold, raise/raise-bluff that satisfy all indifference conditions.

**Formel:** Player X strategy (spread-limit AKQ):
- Bet 1 with 100% of aces, 40% of kings, 20% of queens.
- If Y raises 1 or 2 over that bet: reraise with aces, fold kings, fold bluff-queens.
- Remaining K,Q: check.
- Versus Y’s bets after checking:
  • Call 1-unit bets with K at frequency 4/5.
  • Call 2-unit bets with K at frequency 2/3.

Player Y strategy:
- If X bets 2: raise 2 with A, call with 1/3 of K, fold Q.
- If X bets 1: raise 1 with A and 1/15 of Q; call with 3/5 of K.
- If X checks: bet 2 with A and 1/3 of Q; check K.

Game value under this equilibrium: EV_X = -1/10.
Naive no-king-bet solution value: EV_X = 1/6.
Difference = (1/6) - (-1/10) = 1/90 in Y’s favor with optimal preemptive/raise-bluff play.

**Für den Bot:** Allow and train for mixed strategies over multiple river sizings including preemptive bets and raise-bluffs; these can reverse the direction of the game’s value compared to naive single-size, no-K-bet solutions.

## Indifference target for raise-bluffer vs original bettor
When preemptive betting exists, the raise-bluffer need not make the bettor indifferent to *calling the raise*; instead, the raise-bluffer chooses a bluffing frequency that makes the bettor indifferent between betting preemptively and checking.

**Formel:** Let:
EV_check(K) = c, EV_pre_bet(K) = b > c initially.
Y selects bluff freq q such that:
EV_pre_bet_new(K) = EV_check(K)
so
c = b - (pot_gain_when_bluff_works) * P(Y has Q | node) * q
=> q = (b - c) / (pot_gain_when_bluff_works * P(Y has Q | node)).

**Für den Bot:** In multi-size river trees, some raise-bluffs are calibrated to neutralize the incentive to preemptively bet with marginal hands, not to equalize call vs fold after the raise; equilibrium search should include these higher-level indifference constraints.

## No-limit AKQ: optimal t (small bet) from maximizing A(t)
In the no-limit AKQ game, X chooses a small bet size t = τ with part of his A/K/Q range to maximize the EV of betting with aces, trading off value vs kings and EV from catching raise-bluffs by queens.

**Formel:** Simplified full-street structure with constraint “X doesn’t bet K”:
If X bets size t with A and some Q, Y calls a total fraction 1/(1+t) of hands to make X’s Q-bluffs indifferent.
For A vs K when X bets t:
<A vs K, bet t> = t * ( 2/(1+t) - 1 ) = (t - t^2) * 2/(1+t).
Maximizing in t yields:
(t + 1)(1 − 2t) − (t − t^2) = 0  =>  1 − t^2 − 2t = 0  =>  t = √2 − 1.
This t coincides with the canonical r from earlier chapters (Equation 14.1).

**Für den Bot:** Optimal small river bet sizes against capped ranges often correspond to solutions of simple EV maximizations like t = sqrt(2)−1; use such closed-form optima as priors or initial seeds for bet-size optimization in NLHE solvers.

## No-limit AKQ: structure of optimal A/K/Q mixing and s0,t,β relationships
In the full no-limit AKQ equilibrium, X and Y choose a specific small bet size τ and a larger counter bet s0; Y’s raise and raise-bluff sizes are derived from α0 = s0/(1+s0) and β = (α0 − t)/(1+t), with constraints from minimum raise size.

**Formel:** X (no-limit AKQ) equilibrium parameters:
- Checks 61.2% of aces; when Y bets s0 behind, X raises all-in.
- Bets τ = 0.2521 with remaining aces; 3-bets all-in if Y raises.
- Bets τ with 15.62% of kings, folds to any raise; checks rest of kings and calls s with enough kings so total defense freq with checked strong hands is 1/(1+s).
- Bets τ with 7.81% of queens, folds to any raise; checks/folds remaining queens.

Y:
- If X checks, Y bets s0 = 0.5422 with all aces and 35.16% of queens.
- If X check-raises all-in, Y continues with aces, folds queens.

If X bets an amount t, Y responds via:
- Define s0 (fixed) and α0 = s0/(1 + s0).
- Define β = (α0 − t)/(1 + t) if α0 > t, else 0.
- Define t2 = α0 / (1 − β) if α0/(1−β) > 2t, else t2 = 2t (min-raise rule).

Y raises to t2 with all aces and β fraction of queens; folds bluff-queens vs further raises.
Y calls with enough kings such that total calling freq with hands that beat a queen equals 1/(1 + t).

**Für den Bot:** In no-limit river spots, one can parametrize villain’s counter-raises and raise-bluff frequency β as explicit functions of your opening size t and their preferred follow-up size s0, then solve for τ that equalizes A’s EV between checking and betting; this gives structured bet-size and mixing rules instead of ad-hoc sizing grids.

## Defensive calling frequency vs bet size (indifference for bluffs)
The caller defends vs a bet of size b into pot 1 by calling with a total frequency 1/(1+b) among hands that beat pure bluffs, to make bluffs with that size break even.

**Formel:** If pot = 1 and bettor bets b, risking b to win 1:
Let f_def = total fraction of hands in caller’s range that continue and beat bluffs.
Indifference for bluffing (0EV bluffs):
EV_bluff = (1 − f_def)*1 − f_def * b = 0
=> 1 − f_def = b f_def  =>  1 = f_def (1 + b)
=> f_def = 1 / (1 + b).

**Für den Bot:** Against any river sizing b into pot 1, your continuing frequency with hands beating pure bluffs should be ~1/(1+b); this MDF-style constraint is repeatedly enforced both after checks (Y’s bet) and versus small t bets in the AKQ model.

## Equating EV of betting vs checking with aces (NL AKQ)
X mixes between betting τ and checking with aces, so their EVs must be equal: A(0) = A(τ). This pins down τ jointly with Y’s counter-strategy.

**Formel:** Let A(t) be X’s EV with aces when he bets t:
A(t) = EV_from_calls_by_kings(t) + EV_from_catching_raise_bluffs_by_queens(t).
Let A(0) be X’s EV from checking with aces:
A(0) = EV_from_catching_bets_by_queens_at_s0.
In equilibrium, when X mixes checking and betting τ with aces:
A(τ) = A(0).
Given Y’s response functions (s0,β,t2) and defense frequencies, this equation in t is solved numerically; in the text, τ ≈ 0.2521 and s0 ≈ 0.5422 satisfy it.

**Für den Bot:** On the river with nut hands (aces) in no-limit, you often must mix between checking to induce bets and betting small to realize immediate value and catch raise-bluffs; these mixing frequencies and bet sizes are determined by solving A(t) = A(0), not by heuristic ‘always bet your nuts’ rules.

## AKQ half‑street: optimal bet size s vs check (indifference in caller’s response node)
Solve for bluff bet size s that makes opponent indifferent between calling and folding with a marginal bluff‑catcher (here: kings after X checks, Y bets). This pins down s in terms of value/bluff mix and payoffs.

**Formel:** Solve for s in the indifference equation between X checking A and X facing bet s:

⟨A, check⟩ = s^2 / (2 (1 + s))
⟨A, bet r⟩ = (r − r^2) / (2 (1 + r))

Set equal to find s (given r):

(r − r^2) / (2 (1 + r)) = s^2 / (2 (1 + s))

Example in text (with prior r choice) gives numerical solution:

s ≈ 0.50879

**Für den Bot:** Any NLHE node where you choose a single bluff size on river vs a capped range can be tuned by solving an indifference equation between checking strong hands and betting them; the AKQ formulas are directly analogous: equate EV(check) and EV(bet) to back out optimal bluff size s for a given thin‑value size r.

## AKQ half‑street: villain’s optimal bet size response q to hero’s checking frequency Ak
Given X’s ace check frequency Ak, Y chooses bet size q with his value hand (ace) to maximize EV when X defends optimally with a mixture of aces and kings vs bet q. This yields q as analytic function of Ak.

**Formel:** X’s total continuing frequency vs bet size q when Y bets after X checks:

F_call(q) = (1 + Ak) / (2 (1 + q))

Kings call fraction (of all possible kings):

K_call(q) = (1 − q Ak) / (2 (1 + q))

Y’s EV when he has A vs K and bets size q (using that expression):

⟨K/A, bet q⟩ = (q − q^2 Ak) / (2 (1 + q))

Maximize in q:

∂/∂q (q − q^2 Ak) / (2 (1 + q)) = 0

Leads to:

(q + 1)^2 = 1/Ak + 1

q + 1 = ± sqrt(1/Ak + 1)

Choose positive root, so:

q = sqrt(1/Ak + 1) − 1

Thus Y’s best‑response bet size to X’s check frequency Ak is:

q*(Ak) = sqrt(1/Ak + 1) − 1

**Für den Bot:** Villain’s optimal value bet size versus your checking range depends only on how much of the strongest hand you check (Ak). In practice, if your solver/bot knows its nut check frequency, it can compute villain’s ideal sizing against that cap; conversely you can regulate Ak to prevent villain from profitably using extreme bet sizes.

## AKQ half‑street: linking X’s Ak and Y’s optimal s (self‑consistent bet size equilibrium)
X chooses ace check frequency Ak so that the q that maximizes Y’s equity equals the candidate equilibrium bet size s. This enforces consistency of both players’ best responses.

**Formel:** Best‑response sizing for Y given Ak:

q(Ak) = sqrt(1/Ak + 1) − 1

Equilibrium requires q(Ak) = s*, where s* was earlier found from X’s own indifference between lines. So solve:

s* = sqrt(1/Ak + 1) − 1

Rearrange:

s* + 1 = sqrt(1/Ak + 1)
(s* + 1)^2 = 1/Ak + 1
1/Ak = (s* + 1)^2 − 1 = s*^2 + 2s*
Ak = 1 / (s*^2 + 2 s*)

Using s* ≈ 0.50879 ⇒ Ak ≈ 0.78342

**Für den Bot:** Your nut checking frequency determines (and is determined by) the opponent’s optimal bet size. In NLHE, nut checks on turn/river must be tuned to your own intended responding strategy; otherwise villains either overbet or underbet to punish you. An equilibrium bot should solve for nut check frequencies Ak that make villain’s best‑response size equal to the size you intend to defend against.

## AKQ half‑street: bluffing frequency vs bet size (α0, MDF‑style link)
For a bet size s0 in a jam‑or‑fold environment with no future action, equilibrium bluffing frequency is proportional to s0/(1 + s0). Define α0 as bluff density per candidate hand.

**Formel:** Y bluffs with queens a fraction s0 / (1 + s0) of the time when X checks a king and will be made indifferent to calling.

Define:

α0 = s0 / (1 + s0)

X’s EV with K vs that strategy when he always folds (by indifference argument):

⟨P1, check K⟩ = (1/2) [ − s0/(1 + s0) ] = − α0 / 2

**Für den Bot:** On a single betting street where villain cannot raise you, optimal bluffing fraction among candidate bluffs is α0 = s/(1 + s). This is the same α–MDF relationship used for jam‑or‑fold: larger sizing (s) ⇒ higher allowed bluff ratio α0.

## AKQ: constraint on opponent’s raise‑bluff frequency β(t) vs your preemptive bet t
If X bets size t with a weak hand (K) into a checking node, Y must choose a raise‑bluff frequency β(t) with her bluffs (Q) large enough that X’s EV from betting t does not exceed his EV from checking. This pins β(t) as a decreasing function of t up to α0.

**Formel:** X’s EV from betting t with K (vs raises that sometimes bluff with Q) is:

⟨P1, bet t / K⟩ = (1/2)(-t) + (1/2) β [−(1 + t)]

Set equal to his check EV −α0/2 (from earlier):

(1/2)(-t) + (1/2) β [−(1 + t)] = −α0/2

Multiply by 2 and rearrange:

−t − β(1 + t) = −α0

β(1 + t) = α0 − t

β(t) = (α0 − t) / (1 + t)    for α0 > t
β(t) = 0                     for t ≥ α0

**Für den Bot:** When you bet a block size t with a medium strength hand into a node where villain can raise, villain’s optimal raise‑bluff frequency β(t) must be high enough to keep your EV from overbetting that line. As you size larger (t→α0), optimal β falls to zero: big bets are self‑protecting vs raises, small bets invite more aggressive raise‑bluffing.

## AKQ: Y’s EV with A when X bets t and Y can raise to t2 (A(t)) and optimal τ(t)
Y’s EV with A vs X’s bet t comes from calling with some fraction of bluff‑catchers and raising with A and some Q’s. Using the previous β(t) and minimum raise constraint t2 ≥ 2t, Y’s EV is maximized at a particular preemptive bet size τ that X should use with kings when trading off value vs exposure to raises.

**Formel:** Y calls with (1 − t)/(1 + t) of his kings vs bet t.

If Y raises to t2 and raise‑bluffs Q a fraction β, X’s A‑hand EV from betting t is:

A(t) = (1/2) [ t (1 − t)/(1 + t) ] + (1/2) [ β t2 ]

Using β(t) = (α0 − t)/(1 + t) and taking minimum raise t2 = 2t:

A(t) ≥ (1/2) [ t (1 − t)/(1 + t) ] + (1/2) [ (α0 − t)/(1 + t) · 2t ]

Simplify (given in text):

A(t) = (1/(2(1 + t))) [ t(1 − 3t + 2α0) ]

Differentiate and set to zero:

A'(t) = 0 ⇒

3 t^2 + 6 t + 2 α0 − 1 = 0

Solve quadratic:

t^2 + 2 t + (2/3) α0 − 1/3 = 0

(t + 1)^2 = (4/3) + (2/3) α0

Optimal preemptive bet size with K (called τ in text):

τ(α0) = sqrt( (4 + 2 α0) / 3 ) − 1

**Für den Bot:** There is an optimal small bet size τ for thin‑value/protection (here with K) balancing value vs being raised. In NLHE, thin value/protection bets on earlier streets should be computed via a similar EV‑maximization vs potential raises, not chosen heuristically.

## AKQ: self‑consistent s0, α0, τ equilibrium when X may bet K and Y may raise
In the extended AKQ full‑street game (X not forced to check K), you jointly solve for Y’s default bet size s0 after check, bluff density α0, and X’s optimal preemptive bet size τ with K such that (i) A’s EV from betting 0 equals betting τ, and (ii) all the previous best‑response relations hold.

**Formel:** Key relationships:

α0 = s0 / (1 + s0)
τ = sqrt( (4 + 2 α0) / 3 ) − 1

Indifference for X’s A between betting 0 and betting τ (A(0) = A(τ)):

(1/2) α0 s0 = (1/2) [ τ(1 − τ)/(1 + τ) ] + (1/2) [ (α0 − τ)/(1 + τ) · 2 τ ]

Solve numerically for s0 (hence α0, τ):

s0 ≈ 0.54224
α0 ≈ 0.35159
τ ≈ 0.25209

**Für den Bot:** Full‑street equilibria with both bet‑and‑raise options require solving coupled nonlinear systems: bet sizes, bluff densities, and mixed frequencies are linked. A serious NLHE bot must numerically solve such systems at representative tree slices (or via CFR) to get self‑consistent sizing and bluffing frequencies.

## AKQ: theoretical raise target t2*(t) for Y’s raise over X bet t (no min‑raise constraint)
Given preemptive bet t, raise‑bluff frequency β(t), and assuming no minimum raise rule, Y chooses a raise size t2 that makes X indifferent calling vs folding K to the raise. This t2 is computed from an indifference condition.

**Formel:** Indifference for X between calling and folding with K after facing raise from t to t2:

Payoffs (from table):

Second player’s hand:
- If X calls w/ K:
  A: −(t2 − t)
  Q: +t2
- If X folds w/ K:
  A: 0
  Q: −(1 + t)

Indifference condition (EV_call = EV_fold), using β as bluff frequency with Q:

(t2 − t) = β (t2 + 1 + t)

(1 − β) t2 = β (1 + t) + t

Substitute β(t) = (α0 − t)/(1 + t):

(1 − β) t2 = α0

t2*(t) = α0 / (1 − β)

Plug β expression:

1 − β = 1 − (α0 − t)/(1 + t) = (1 + t − α0 + t)/(1 + t) = (1 + 2t − α0)/(1 + t)

So:

t2*(t) = α0 (1 + t) / (1 + 2t − α0)

Validity only when this t2*(t) ≥ applicable min‑raise; in no‑constraint theory we just use t2*.

**Für den Bot:** Optimal raise sizing against a given bet t is pinned by making the bettor’s marginal bluff‑catcher (here K) exactly indifferent between calling and folding. In practice, bots can compute raise targets by solving such indifference equations relative to estimated bluffing frequencies β(t).

## AKQ: piecewise optimal raise size s(t) given min‑raise constraint
With a rule that raises must be at least 2t, the actual raise size s(t) is the max of the theoretical t2*(t) and 2t: small t favour raising closer to s0; large t favour minimum raises.

**Formel:** Use theoretical unconstrained target t2*(t) (above) and min‑raise rule t2 ≥ 2t.

Define actual raise function s(t):

If t is small, theoretical t2*(t) > 2t ⇒ Y raises to t2*(t):

s(t) = α0 / (1 − β(t))    for t < t_cross

If t is large, theoretical t2*(t) ≤ 2t ⇒ Y just min‑raises:

s(t) = 2t                  for t ≥ t_cross

Numerically in text, t_cross ≈ 0.2001.

So piecewise:

s(t) = α0 / (1 − β(t))   (t < 0.2001)

s(t) = 2t                (t ≥ 0.2001)

**Für den Bot:** In discrete NLHE bet trees (min‑raise constraints), the theoretically optimal raise target t2*(t) is often clipped by the min‑raise 2t. Small block bets get raised larger toward a stable sizing like s0; larger bets get min‑raised. A bot should explicitly model this clipping when planning bet sizes.

## AKQ: optimal check‑node mix of A and K (parameter k)
In the final full‑street AKQ solution, X must choose how many kings among his checking range so that Y’s optimal bet size after check is s0 (thus Y is indifferent to deviating). Let k be fraction of checking hands that are kings; indifference of Y’s A between betting and checking at size q yields k.

**Formel:** Let k = fraction of X’s checking range composed of kings.

If Y bets size q with A after X checks, X calls with 1/(1 + q) of his total checking hands. Among those, some are A (fraction 1 − k) and the rest K.

Number (mass) of kings that call w.r.t initial k is:

K_call_check = [k − q + k q] / [k (1 + q)]

Y’s EV from betting q with A when checked to:

E_Y(q | A, check) = (k q − q^2 + k q^2) / [k (1 + q)]

Maximize in q and set derivative to 0:

k − 2q + 2kq − q^2 + kq^2 = 0

Factor:

k(1 + 2q + q^2) = 2q + q^2

So:

k = (2q + q^2) / (1 + 2q + q^2)

Plugging q = s0 ≈ 0.54224 gives:

k ≈ 0.57957

**Für den Bot:** The composition of your check range (ratio of medium to strong hands) should be chosen so that villain’s best‑response bet size is exactly the size you anticipate (here s0). Practically, a bot should manage how many bluff‑catchers vs traps it checks to make villain’s value bet sizing indifferent around your intended defense strategy.

## AKQ: optimal bet‑node mix of A and K (betting ratio q/(1+τ+q))
When X bets τ with A and K and Y can raise to some size q optimally, X should choose ratio of kings to aces in betting range so that Y is indifferent to raise‑bluffing. Because X can fold all K to the raise (since min‑raise prevents smaller punishing raises), only A continues vs raise, so mixing only affects villain’s bluff EV.

**Formel:** Let q be Y’s chosen raise size over bet τ. Y gains 1 + τ when bluffs get through, loses q when called. X never calls with K to raises (folds them all), and calls with A such that Y is indifferent to raise‑bluffing.

Call frequency vs raise:

p_call = (1 + τ) / (1 + τ + q)

So fraction of kings in X’s betting range is:

K_bet / A_bet = q / (1 + τ + q)

Numerically, given q from the earlier equilibrium solving, this is ≈ 0.28707.

**Für den Bot:** When you plan to fold your medium hands to raises (pure bluff‑catchers), your value‑betting range should contain a controlled fraction of those mediums to make bluffs break even. For a given bet size τ and expected raise size q, optimal K:A ratio in betting range is q/(1+τ+q).

## AKQ: solving global A/K checking and betting frequencies from two linear constraints
Given target ratios for (i) K share among checking hands (k) and (ii) K share among betting hands (derived from raise‑bluff indifference), you can solve a 2×2 linear system to get absolute frequencies of check vs bet for each hand type.

**Formel:** Let b = total mass of hands in X’s betting range (as a multiple of one hand type), c = total mass in X’s checking range.

From:
- K share among betting hands: K_bet / A_bet = r_b ≈ 0.28707
- K share among checking hands: K_check fraction k ≈ 0.57957 (from earlier)

Translate to linear eqns (using total counts of A and K both equal to 1):

0.28707 b + 0.57957 c = 1     (K constraint)
0.71293 b + 0.42043 c = 1     (A constraint)

Solve for b, c:

b ≈ 1.45595
c ≈ 0.55405

Then derive actual frequencies (fractions of each card type that bet/check):

Ak = fraction of A that check = c / (b + c) ≈ 0.61213
Ab = 1 − Ak ≈ 0.38787

Kk = fraction of K that check = (k c) / 1 ≈ 0.84382
Kb = 1 − Kk ≈ 0.15618

(Values in text: Ak = 61.213%, Ab = 38.787%; Kk = 84.382%, Kb = 15.618%).

**Für den Bot:** Range construction is often a 2×2 (or higher) linear system linking desired composition ratios across actions. A bot should routinely solve such small linear systems to convert target ratios (like given K:A splits for bet/check) into actual per‑hand frequencies.

## AKQ: game values as EV benchmarks
The solved equilibrium yields explicit game values (per hand) that serve as correctness checks and as analogs for exploitability measures in more complex games.

**Formel:** Simplified game where X must check K: value to Y

V_simplified ≈ 0.02761 units per play.

Full game with optimal A/K mixes and preemptive K bets allowed: value to Y

V_full ≈ 0.02682 units per play.

**Für den Bot:** Exact small‑game values provide tight benchmarks for numerical algorithms (CFR, LP solvers). A bot implementation should reproduce these game values when solving corresponding toy trees; discrepancies indicate implementation bugs or inadequate iteration.

## [0,1] no‑fold, one‑bet game: threshold strategy and trivial equilibrium (X bets all)
In a no‑fold [0,1] game with a single bet allowed and no raising, both players sample hands uniformly on [0,1]. X acts first and can bet or check; Y can bet if checked to. Parameterizing strategies with thresholds x1 (X bet/check) and y1 (Y bet/check after X checks), indifference conditions show that equilibrium is trivial: X bets all hands, Y always calls.

**Formel:** Parameterization:

X: bet for all x ≤ x1, check for x > x1
Y (after X checks): bet for y ≤ y1, check for y > y1

Indifference for Y at y1 (bet vs check):

0 = x1 − 2 y1 + 1 ⇒ 2 y1 = x1 + 1

Indifference for X at x1 (bet vs check‑call):

1 − 2 x1 = y1 − 2 x1 ⇒ y1 = 1

Substitute back:

2·1 = x1 + 1 ⇒ x1 = 1

Thus:

x1 = 1, y1 = 1

So X bets all hands, Y never gets to bet; Y always calls X’s bet because folding is banned.

**Für den Bot:** In limit‑like, no‑fold spots with only one bet left, optimal play is to always take the initiative with any hand that could be bet for value, preventing opponent from realizing extra EV by betting after your checks. In NLHE, when facing a huge pot, small remaining stacks, and no fold equity, betting any hand that would call is often optimal to deny opponent’s positional value.

## [0,1] no‑fold, two‑bet game (Game #5): ‘R’ ratio for raising region on last bet
In no‑fold [0,1] with two bets left, no check‑raise, both players uniform in [0,1], the structure is: X bets some bottom fraction, Y raises with bottom fraction of that, and when checked to, Y bets with some bottom fraction of remaining. The size of Y’s raising region relative to X’s betting region on the last bet is R = 1/2, independent of exact thresholds.

**Formel:** Thresholds:

0 < y2 < x1 < y1 < 1

- x1: X’s bet/check threshold.
- y1: Y’s bet/check threshold after X checks.
- y2: Y’s call/raise threshold vs X bet.

At y2 (Y indifferent calling vs raising):

Sum of differences ⇒ 2 y2 − x1 = 0 ⇒ y2 = x1 / 2

Define R = y2 / x1, then:

R = 1/2

In general, in no‑fold games on the last betting opportunity where opponent cannot reraise, the optimal raising region has size R times opponent’s value‑betting region, with R = 1/2.

**Für den Bot:** On the final betting round when villain cannot reraise and you cannot fold, optimal raising for value uses about half the hands opponent value‑bets (R=1/2). In NLHE, this is an analog for thin value raising frequency in capped, no‑fold river spots: you should raise with roughly half of the hands that beat villain’s betting region.

## [0,1] no‑fold Game #5: system of threshold equations and solution
The two‑bet [0,1] no‑fold game’s equilibrium thresholds satisfy three linear equations derived from indifference at y2, x1, and y1. Solving yields explicit thresholds x1, y1, y2.

**Formel:** Equations:

1) At y2:  y2 = R x1, with R = 1/2 ⇒ y2 = x1 / 2

2) At x1 (X indifferent between bet and check‑call):

y2 = 1 − y1

3) At y1 (Y indifferent between check and bet after check):

y1 = (1 + x1) / 2

Solve:

From 1 & 2: x1 / 2 = 1 − y1

Substitute 3 into above:

x1 / 2 = 1 − (1 + x1)/2

x1 / 2 = (2 − 1 − x1)/2 = (1 − x1)/2

⇒ x1 = 1 − x1 ⇒ x1 = 1/2

Then:

y1 = (1 + 1/2)/2 = 3/4

y2 = x1 / 2 = 1/4

Solution:

x1 = 1/2,
y1 = 3/4,
y2 = 1/4.

**Für den Bot:** Betting/raising thresholds in continuous‑strength models often solve from simple linear indifference systems. For NLHE, approximating strength by a scalar (e.g., hand percentile) can give analytic guidance for where to start/stop betting and raising for value in no‑fold or low‑fold‑equity spots.

## [0,1] Game #6: Infinite Raising Game (no check-raise, no folding)
Heads-up one-street [0,1] toy game where both players can raise and reraise without limit, stacks are arbitrarily large, check-raise is forbidden, and nobody can fold. Equilibrium is characterized by a single raising-frequency parameter R that determines all betting thresholds via geometric scaling. Solving for R uses indifference at a boundary type, leading to the ‘golden mean of poker’ R = sqrt(2) - 1.

**Formel:** Definitions and structure:
- Hands are uniformly distributed on [0,1]. Lower number = stronger hand (as in the excerpt’s notation).
- Thresholds:
  0 < y2n < x2n-1 < … < y2 < x1 < y1 < 1
  where x1 is X’s bet/check threshold when checked to, y1 is Y’s bet/check threshold when X checks, y2 is Y’s raise/call threshold when X bets, x3 is X’s reraise/call threshold when facing a raise, etc.

Raising-frequency structure:
- Let R be the fraction of the previous bettor’s range used for raising at each step.
- Then for n > 1:
  yn = R * x_{n-1}   (Y’s n-th raise threshold from X’s previous x)
  xn = R * y_{n-1}   (X’s n-th raise threshold from Y’s previous y)

Check branch (no check-raise allowed):
- Y bets all hands better than x1 and half of hands worse than x1:
  y1 = (1 + x1) / 2
- Size of Y’s raising region equals size of his checking region:
  y2 = 1 - y1
  and also from raising-frequency definition: y2 = R * x1.

Solving for x1 in terms of R:
- Start from:
  y2 = 1 - y1
  y1 = (1 + x1) / 2
  y2 = R * x1
- Substitute and simplify:
  R * x1 = 1 - (1 + x1)/2
  2 R x1 = 2 - 1 - x1
  2 R x1 = 1 - x1
  x1 (2 R + 1) = 1
  x1 = 1 / (2 R + 1)

Indifference at y2 (Y between raising and calling after X bets):
- Payoff table in the excerpt gives the indifference condition:
  x3 + 2 y2 - x1 = 0
- Using x3 = R y2, y2 = R x1:
  R^2 x1 + 2 R x1 - x1 = 0
  x1 (R^2 + 2 R - 1) = 0
  R^2 + 2 R - 1 = 0
- Solve quadratic:
  R = -1 ± sqrt(2)
  Feasible 0 < R < 1 ⇒ R = sqrt(2) - 1.

With r = R = sqrt(2) - 1, all thresholds:
- x1 = 1 / (1 + 2 r)
- y1 = (1 + x1)/2 = (1 + r)/(1 + 2 r)
- y2 = r / (1 + 2 r)
- x3 = r^2 / (1 + 2 r)
- In general (from the excerpt):
  y_n = r^{n-1} / (1 + 2 r)  for even n > 1
  x_n = r^{n-1} / (1 + 2 r)  for odd n > 2

Interpretation of R:
- R = sqrt(2) - 1 ≈ 0.4142
  is the equilibrium fraction of the opponent’s continuing range to raise with on each bet when
  - they cannot fold, and
  - they can re-raise you.

**Für den Bot:** In capped-street or scripted spots where neither player folds and raises can be 3-bet/4-bet etc., the optimal raising frequency is R = sqrt(2) - 1 ≈ 41.4% of the opponent’s continuing range on each raise level. Use a geometric, R-scaled raising subset of your value region (and no bluffs in a no-fold toy) and size your thresholds so that each action keeps opponent indifferent, mirroring the R-scaling pattern.

## [0,1] Game #7: Two-bet, Check-Raise Allowed, No Fold
One-street [0,1] game with exactly two bets left, check-raising allowed, no folding. Compared to the no-check-raise version (Game #5), check-raise introduces an additional threshold x2 and shifts all others. Four indifference conditions (at x2, y2, x1, y1) determine the equilibrium thresholds exactly.

**Formel:** Game structure:
- One street, two bets maximum.
- No folding; check-raise allowed.
- Hands uniform on [0,1], lower = stronger.

Threshold ordering:
  0 < x2 < y2 < x1 < y1 < 1

Strategies in terms of thresholds:
For X:
- X checks and raises (check-raises) if Y bets on [0, x2].
- X bets for value on [x2, x1].
- X checks and calls on [x1, 1].

For Y:
If X bets:
- Y raises for value on [0, y2].
- Y calls on [y2, 1].

If X checks:
- Y bets for value on [0, y1].
- Y checks on [y1, 1].

Indifference equations:
1) X at x2 (indifferent between check-raising and betting):
   2 y1 - y2 - 1 = 0
   ⇒ y2 = 2 y1 - 1.

2) Y at y2 (indifferent between raising and calling vs X bet):
   2 y2 - x1 - x2 = 0
   ⇒ y2 = (x1 + x2) / 2.

3) X at x1 (indifferent between check-calling and betting):
   y2 - 1 + y1 = 0
   ⇒ y2 = 1 - y1.

4) Y at y1 (indifferent between betting and checking vs X check):
   2 x2 + 2 y2 - x1 + 1 = 0
   ⇒ 2 y1 = 1 + x1 - 2 x2   (after substitution).

System to solve:
- 2 y1 = 1 + x1 - 2 x2
- y2 = (x1 + x2)/2
- y2 = 2 y1 - 1
- y2 = 1 - y1

Solving:
- From y2 = 2 y1 - 1 and y2 = 1 - y1:
  2 y1 - 1 = 1 - y1
  3 y1 = 2
  y1 = 2/3
  ⇒ y2 = 1 - y1 = 1/3.

- From y2 = (x1 + x2)/2 with y2 = 1/3:
  1/3 = (x1 + x2)/2
  x1 + x2 = 2/3.

- From 2 y1 = 1 + x1 - 2 x2 with y1 = 2/3:
  4/3 = 1 + x1 - 2 x2
  1/3 = x1 - 2 x2.

- Solve the 2×2 system:
  x1 + x2 = 2/3
  x1 - 2 x2 = 1/3
  ⇒ subtract: 3 x2 = 1/3 ⇒ x2 = 1/9
  ⇒ x1 = 2/3 - x2 = 5/9.

Equilibrium thresholds:
- x1 = 5/9 ≈ 0.5556
- y1 = 2/3 ≈ 0.6667
- x2 = 1/9 ≈ 0.1111
- y2 = 1/3 ≈ 0.3333.

Comparison with Game #5 (two-bet, no check-raise):
- Game #5 thresholds (from the text):
  x1 = 1/2, y1 = 3/4, y2 = 1/4.
- Game #7 thresholds:
  x1 = 5/9 > 1/2  (X bets a slightly wider range for value when he has initiative.)
  y1 = 2/3 < 3/4  (Y bets less often when checked to, fearing a check-raise.)
  y2 = 1/3 > 1/4  (Y raises more often versus X’s bet because X is now checking some strong hands and betting more medium-strength hands).

**Für den Bot:** Allowing check-raises makes the out-of-position player check more strong hands and bet more medium ones, while in-position responds by betting less thinly when checked to but raising wider versus bets. In NLHE, when you can check-raise the flop/turn, you should (i) protect your checking range with strong hands, (ii) extend your value-bet range slightly, and (iii) expect villain to bet less thinly IP but raise your bets more often than in a pure bet/call tree.

## [0,1] Game #8: Infinite Raising with Check-Raise (No Fold)
Full no-fold one-street [0,1] game with unlimited raises, arbitrarily deep stacks, and check-raise allowed. Both players’ strategies are captured by sequences of thresholds {y_n} (Y’s betting/raising boundaries) and {x_n} (X’s thresholds between checking, check-raising, betting, and reraising). The {y_n} sequence follows a simple geometric progression governed by r = sqrt(2) - 1, while {x_n} follows a linear difference equation whose solution oscillates between betting and check-raising regions. The model shows that OOP checks exactly half of his range overall and that each subsequent raise region shrinks by factor r.

**Formel:** Game structure:
- One street, arbitrarily many bets.
- Check-raise allowed, no folding.
- Hands uniform on [0,1], lower = stronger.

Threshold ordering for all positive integers n:
  0 < x_{n+1} < y_{n+1} < x_n < y_n < 1

Y’s thresholds: recursive and closed form
----------------------------------------
From indifference at y_k and y_{k+1}, the text derives a second-order linear difference equation for Y’s thresholds:

(16.1)   y_{k+2} + 2 y_{k+1} - y_k = 0.

General solution to this difference equation is:
- y_n = A * r1^n + B * r2^n, where r1, r2 are roots of λ^2 + 2 λ - 1 = 0.
- However, the text gives a more convenient representation consistent with the poker constraints:

  y_n = r^n / (1 - r)     for n ≥ 0 and r > 0,

where r = sqrt(2) - 1.
Thus:
- Geometric relationship:
  y_n = r * y_{n-1}   for all n ≥ 1.

And specifically:
- y_0 = 1 (by definition, entire range).
- y_1 = r / (1 - r) ≈ 0.7071.
- y_2 = r y_1, y_3 = r y_2, etc.

Y’s strategy interpretation:
- Y bets if checked to with hands below y_1 = r / (1 - r).
- At each subsequent opportunity to add another bet, Y continues with a fraction r of the hands with which he made the previous bet:
  fraction of his previous betting/raising range that raises again = r = sqrt(2) - 1 ≈ 0.4142.

X’s thresholds: recursive and closed form
----------------------------------------
From symmetric indifference constructions at x_k and x_{k+1}, the text obtains another difference equation for X’s thresholds:

(16.2)   x_k + 2 x_{k+1} - x_{k+2} = 2 r^k.

Solving (16.2) yields X’s thresholds in closed form:

  x_n = r^{n-1} * [ (2 r - 1) * (-1)^n + 1 ] / 2   for n ≥ 1.

The excerpt then simplifies this using the value of r:
- For n even:
  the bracket term equals 2 r → x_n = r^n.
- For n odd:
  the bracket term equals 2 (1 - r) → x_n = r^{n-1} (1 - r).

So compactly:
- If n is even (n = 2,4,6,…):
  x_n = r^n.
- If n is odd (n = 1,3,5,…):
  x_n = r^{n-1} (1 - r).

Initial thresholds (numeric):
- r = sqrt(2) - 1 ≈ 0.414213562.
- y_0 = 1.
- y_1 = r / (1 - r) ≈ 0.707107.
- x_1 = 1 - r ≈ 0.585786.
- y_2 = r^2 / (1 - r) ≈ 0.292893.
- x_2 = r^2 ≈ 0.171573.
- y_3 = r^3 / (1 - r) ≈ 0.121320.
- x_3 = r^2 (1 - r) ≈ 0.100505.
- etc.

Geometric relation between Y thresholds:
- From the closed form:
  y_n = r^n / (1 - r) ⇒ y_n / y_{n-1} = r.

X’s checking regions and total check frequency
---------------------------------------------
The text identifies that X’s check-then-raise or check-then-call regions between even and odd x_n’s shrink by powers of r:
- Check regions:
  [x_0, x_1], [x_2, x_3], [x_4, x_5], … with x_0 = 1.
- Sizes:
  size[x_0 → x_1] = 1 - (1 - r) = r.
  size[x_2 → x_3] = r^2 - r^2 (1 - r) = r^3.
  size[x_4 → x_5] = r^4 - r^4 (1 - r) = r^5.
  In general: size[x_{2n} → x_{2n+1}] = r^{2n+1}.

Total fraction of X’s range that checks (sum over all check regions):
- Sum_{n=0 to ∞} r^{2n+1} = r * (1 / (1 - r^2)).
- Using r = sqrt(2) - 1 ⇒ r^2 = 3 - 2 sqrt(2) ≈ 0.1716.
- The text computes:
  r / (1 - r^2) = 1/2.

So:
- X checks exactly 1/2 of his range in equilibrium.
- Of these checking hands, a fraction r will check-raise (the strong part) and the remainder will check-call.

Summary of closed-form strategy parameters:
- r = sqrt(2) - 1 ≈ 0.414213562.
- Y thresholds:
  y_n = r^n / (1 - r),   n ≥ 0,   and y_n = r * y_{n-1}.
- X thresholds:
  x_n = r^n                 if n is even (n ≥ 2),
  x_n = r^{n-1} (1 - r)     if n is odd (n ≥ 1).
- X’s total checking frequency = 1/2.

**Für den Bot:** In deep, multi-raise NLHE spots where both players can bet, raise, re-raise, and check-raise without large sizing constraints, the optimal continuation set shrinks geometrically: each further raise comes from roughly a fixed fraction r ≈ 0.414 of the prior betting range. Out-of-position should check about half its range, composing that checking range of a thin sliver of very strong check-raises plus many more reluctant check-calls; in-position, after betting once, should treat further raises as coming from a geometrically shrinking subset rather than from a fixed percentile or linear threshold.

## Golden Mean of Poker and Raising Frequency R
Across both the infinite raising game without check-raise (Game #6) and with check-raise (Game #8), the equilibrium fraction of the opponent’s continuing range that you should raise with is R = sqrt(2) - 1, sometimes called the ‘golden mean of poker’. In Game #6 it is the fraction of the opponent’s range each player raises with on any given bet when no one can fold; in Game #8 it becomes r, the geometric factor between successive thresholds.

**Formel:** From Game #6 (no check-raise):
- Solving the indifference equation for Y at y2 yields:
  R^2 + 2 R - 1 = 0.
- Roots:
  R = -1 ± sqrt(2).
- Feasible 0 < R < 1 ⇒
  R = sqrt(2) - 1 ≈ 0.414213562.

From Game #8 (with check-raise):
- The ratio between successive Y thresholds is the same r:
  y_n = r * y_{n-1}.
- r is chosen to satisfy all indifference equations and again turns out to be:
  r = sqrt(2) - 1.

Useful numerical equalities:
- r = sqrt(2) - 1 ≈ 0.4142.
- 1 - r = 2 - sqrt(2) ≈ 0.5858.
- r^2 = 3 - 2 sqrt(2) ≈ 0.1716.
- r / (1 - r^2) = 1/2 (used for X’s total checking fraction in Game #8).

**Für den Bot:** When modeling multi-raise streets with fixed bet sizes and no folding (or rare folding), a robust heuristic is that each further raise should come from about 41% of the opponent’s current continuing range. This constant R controls geometric thinning of raises and is a useful calibration point for building simplified NLHE strategies and abstractions.

## No-fold value-extraction ratio (no folding, no raising back)
In no-fold [0,1] games where villain cannot fold and you cannot be raised, optimal play is to take the aggressive action (bet/raise) with exactly half of villain’s range that has taken the passive line so far.

**Formel:** Aggressive fraction = 1/2 of opponent’s current range when: (1) opponent cannot fold, (2) you cannot be raised.

**Für den Bot:** In very-big-pot NLHE spots where (a) stacks are effectively committed and (b) there is no further betting (eg, river all-in called 100%), approximate that you should value-bet about half of villain’s checking range and check the rest for showdown. Do not overbet thinly when you cannot be punished by folds or further raises; focus on extracting with the top ~50% of the realizable range.

## No-fold infinite-raising ratio and the golden mean of poker
In no-fold games with an infinite raise tree, the fraction of the opponent’s range you bet/raise with shrinks from 1/2 toward a constant r = sqrt(2) − 1, the ‘golden mean of poker’. This is the key ratio governing threshold sequences across multiple rounds of riskless value bets.

**Formel:** Characteristic equation: x^2 + 2x − 1 = 0
Roots: x = −1 ± sqrt(2)
Define r = sqrt(2) − 1 ≈ 0.41421356.
Aggressive fraction with infinite possible raises in no-fold game → r.

**Für den Bot:** In very deep, no-fold-like NLHE configurations (e.g., toy modeling of all-in-capable ladders where neither player ever folds), the density of hands that continue for bets converges to about 41.4% of the partner’s continuing range per level. This r reappears in multi-street value-only lines and can be used to parameterize simplified multi-barrel EV models where bluffing is negligible.

## No-fold multi-bet threshold sequence y_n
In the multi-raise no-fold toy game, thresholds y_n describing the minimum hand strength needed to put in the (n+1)-th bet form a geometric progression in r with scale 1/(1−r).

**Formel:** Difference equation: y_{k+2} + 2 y_{k+1} − y_k = 0
Solution (with convergence to 0 for large n):
  y_n = a r^n,  where r = sqrt(2) − 1
Using boundary conditions:
  a = 1 / (1 − r)
So:
  y_n = r^n / (1 − r)


**Für den Bot:** For a simplified model of repeated value betting in NLHE where neither player folds (e.g., modeling thin value on future streets with locked-in calls), the optimal threshold to continue shrinks geometrically. You can approximate continuation thresholds as a geometric progression in r, which allows fast evaluation of how many value bets different hand strengths can support.

## Non-homogeneous threshold sequence x_n (no-fold game)
When a source term (like pot contributions) makes the difference equation non-homogeneous, the threshold sequence x_n becomes a combination of alternating geometric terms and a particular geometric part in r.

**Formel:** Non-homogeneous equation:
  x_k + 2 x_{k+1} − x_{k+2} = 2 r^k
General solution:
  x_n = a (−r)^n + (r/2) r^n,  with r = sqrt(2) − 1
Using x_0 = 1 ⇒ a = (2r − 1)/(2r)
Simplified closed form:
  x_n = r^{n−1} [ (2r − 1)(−1)^n + 1 ] / 2


**Für den Bot:** For more refined no-fold multi-street models where the pot grows with each bet, continuation thresholds alternate above/below a geometric baseline. A bot can plug this x_n into a fast evaluator to approximate whether an extra thin value bet is +EV when you assume villain never folds any continuing hand.

## [0,1] finite-pot one-street game #9: bluff-to-value ratio α
In one-street [0,1] games with finite pot P and bet size 1, the optimal bluffing region size is α times the value-betting region size, with α determined purely by pot odds.

**Formel:** α = 1 / (P + 1)
Bluffing region size (for X): 1 − x0
Value betting region size (for X): x1
Indifference of caller ⇒ 1 − x0 = α x1
So: bluff:value size ratio = α.

**Für den Bot:** On any river jam in NLHE where villain’s calling strategy is roughly equilibrium-like, set your bluff combo count ≈ α times your value combo count, with α ≈ risk / (risk + reward) = (bet size) / (pot + bet). This directly generalizes: optimal bluff frequency is proportional to the inverse of (P+1).

## Finite-pot [0,1] Game #9: caller’s defense fraction (MDF-like)
The player facing a bluff must defend with 1−α of the hands that can beat a bluff, where α is the bluffer’s optimal bluff:value ratio.

**Formel:** α = 1 / (P + 1)
Caller’s defend fraction vs bluffer (of hands that beat a bluff):
  defend_fraction = 1 − α = P / (P + 1)
In Game #9 (when X bets and Y chooses y1*):
  y1* = 1 − α.


**Für den Bot:** For a river bet of size B into pot P in NLHE, the MDF analogue is: call with fraction P / (P + B) of your hands that beat villain’s pure bluffs. This is the same 1−α ratio here. Use it to set your minimal call-down frequencies given a modeled bluff frequency.

## [0,1] Game #9: symmetric α relationships for both players
Both players use the same α in their bluff:value mixes, regardless of direction. For Y facing X’s check and deciding to bluff/value-bet, and for X facing Y’s bet, their bluffing region sizes are α times their value-betting regions.

**Formel:** For X:
  1 − x0 = α x1
For Y (after X checks):
  1 − y0 = α y1
where α = 1 / (P + 1).


**Für den Bot:** On the river in NLHE, in symmetric positions (similar stack, info, and action options), both IP and OOP should target the same bluff:value ratio α determined by pot odds for all bets of a given size. A bot can enforce this symmetry across IP/OOP bet sizes within its strategy.

## Finite-pot [0,1] Game #9: value-betting width when you can’t be raised
If villain could have bet but checked, you cannot be raised, and villain may now call or fold, the optimal value-betting region is all hands villain would have value-bet plus half the hands villain will only call with.

**Formel:** At Y’s threshold y1 vs X’s check, with X’s value-bet threshold x1 and check-call threshold x1* (x1 < y1 < x1*):
Indifference condition:
  y1 = (x1 + x1*) / 2
Interpretation: Y bets all of [x1, y1] (which is equal in size to [y1, x1*]).

**Für den Bot:** On the river OOP when you check and IP checks back most medium hands but cannot raise you (e.g., you lead all-in), your thin value region should include all hands stronger than villain’s value-bet threshold plus about half of villain’s check-back-calling region. This prevents you from under-betting your top range after seeing a check-back.

## Finite-pot [0,1] Game #9: caller’s threshold vs initial bet
When X bets into Y, Y’s calling threshold is such that the expected value of calling equals folding, leading to the proportion equation relating bluffing and value regions.

**Formel:** Y’s indifference at y1* between calling and folding vs X’s bet:
  (P + 1)(1 − x0) − x1 = 0
so
  1 − x0 = α x1,  α = 1/(P+1).
Similarly, for X at x1* vs Y’s bluff/value-bet (after X checks):
  (P + 1)(1 − y0) − y1 = 0
⇒ 1 − y0 = α y1.

**Für den Bot:** Implement river call thresholds by solving an indifference equation: EV(call) = EV(fold). Use the relation that caller must be just indifferent versus the opponent’s bluff:value mix. This is the core of computing optimal call frequencies given bluffer’s α.

## Finite-pot [0,1] Game #9: balancing induce-bluff vs bet-now value
The threshold between betting and checking with a strong but marginal hand is found by equating the EV of inducing bluffs (check-call) with the EV of betting and being called by worse but not inducing bluffs.

**Formel:** At X’s threshold x1 (between check-calling and betting vs Y):
Indifference equation:
  y1* − y1 − (1 − y0) = 0
⇒ size([y1, y1*]) = size([y0, 1])
Interpretation: X gains a bet by checking when Y’s hand is in [y0,1] (induced bluffs) and gains a bet by betting when Y’s hand is in [y1, y1*] (worse calls). These regions must be equal in measure.

**Für den Bot:** In NLHE river spots with bluff-heavy opponents, marginal value hands should often check to induce bluffs when the induced-bluff region (hands villain will bluff with if checked to) is as large as the thin-value-call region. Balance your checks/bets at this threshold so both options yield the same EV against a near-optimal villain.

## Finite-pot [0,1] Game #9: X’s adjusted call-region width vs Y’s bluff
When X has already split off some betting hands and faces a bet from Y after checking, X must call with a 1−α fraction of the remaining subrange that can beat Y’s bluff. This pins x1* relative to x1 and x0.

**Formel:** X’s effective defend set vs Y’s bluff is [x1, x0]. X must call with 1 − α of that:
  (x1* − x1) / (x0 − x1) = 1 − α
⇒ x1* = x1 + (1 − α)(x0 − x1).
This is the informal statement: x1* is 1−α of the way from x1 to x0.

**Für den Bot:** For NLHE river lines where you already removed some hands into your own betting range, when facing a bet you still need to defend about the same MDF fraction, but only within your remaining checking range. Choose your call threshold so that you defend with ≈ P/(P+B) of that check-range that beats bluffs, not of the full distribution.

## Finite-pot [0,1] Game #9: closed-form optimal thresholds
Solving the six indifference equations yields explicit expressions for all six thresholds (x0, x1, x1*, y0, y1, y1*) as functions of α.

**Formel:** Given α = 1 / (P + 1):
  y1   = (1 − α) / (1 + α)
  x1   = (1 − α)^2 / (1 + α)
  y0   = (1 + α)^2 / (1 + α)   [typo in text; effectively y0 is determined via 1 − y0 = α y1]
  x0   = 1 − α * (1 − α)^2 / (1 + α) = 1 − α x1
  y1*  = 1 − α
  x1*  = 1 − α
(Important relationships: y1* = x1* = 1 − α, and 1 − x0 = α x1, 1 − y0 = α y1.)

**Für den Bot:** For a one-street solver abstraction of river NLHE with continuous hand strengths, you can directly compute optimal bet/bluff/call/fold thresholds as explicit functions of α (hence of pot and bet size). This lets a bot approximate GTO ranges in toy games quickly, then map these thresholds back to quantiles of its real hand distributions.

## Finite-pot [0,1] Game #9: optimal call frequency example with P=4
With pot size P=4 and bet=1, α=1/5, and the caller must call 4 times as often as he folds against bluffs to make the bluffer indifferent, resulting in an overall call frequency of 4/5.

**Formel:** P = 4 ⇒ α = 1/(P+1) = 1/5
Bluffer’s EV(bluff) = 0 at indifference ⇒
  Call_freq / Fold_freq = P = 4
Total fraction = Call_freq + Fold_freq = 1
⇒ Call_freq = 4/5 = 1 − α.
So y1* = 1 − α = 4/5.

**Für den Bot:** If you bet 1 into 4 on the river in NLHE and are balanced (α=0.2), villain must call 80% of his hands that beat your pure bluffs to avoid giving your bluffs profit. A solver-based bot should enforce similar defense frequencies in its calling ranges and use them as sanity checks on its learned policies.

## Finite-pot [0,1] Game #9: optimal number of thin value bets (example P=4)
For P=4 in Game #9, the optimal value-betting region size for Y when checked to is y1 = 2/3; this is determined by equating the sizes of the induce-bluff and thin-call regions.

**Formel:** Given P=4 ⇒ α = 1/5.
We have:
  y1* = 1 − α = 4/5
  1 − y0 = α y1 = (1/5) y1
Indifference at x1 gave:
  (region size for thin calls) = (region size for induced bluffs)
⇒ (4/5 − y1) = (1/5) y1
⇒ 4/5 = (6/5) y1
⇒ y1 = 2/3.


**Für den Bot:** With typical bet sizes (e.g., 1 into 4) the optimal checking player, when given the chance to bet, should value-bet quite wide (here ~66% of his top range behind the check). River bots should not be overly nitty with value-bets after a missed c-bet when stacks are shallow relative to pot.

## [0,1] Game #10: structure with raise-bluffs
In a one-street game with two bets left (bet and raise available, no check-raise), Y’s optimal strategy versus X’s bet has three regions: value-raises, calls, folds. To protect value-raises, Y must add raise-bluffs drawn from hands that are worse than both raising and calling hands and that never win if called.

**Formel:** Structural statement (no closed-form in excerpt):
Let Y’s distribution be partitioned into:
  [raise for value] ∪ [call] ∪ [fold]
Raise-bluff region ⊂ [fold] such that raise-bluffs have zero showdown value when called.
Raise-bluff:size to value-raise:size ratio is determined analogously to one-bet α, but with effective pot including both bet and raise sizes.


**Für den Bot:** On the river in NLHE when facing a bet and allowed to raise, your raising range should consist of your strongest value hands plus a bluff segment taken from hands too weak to call and that essentially never win if called. The proportion of raise-bluffs to value-raises is set by an α-like function of (pot + bet + raise). This is the blueprint for constructing solver-style raise vs bet ranges: value-raise strong; call medium; fold worst except for a carefully sized bluff subset.

## Multi-bet [0,1] thresholds y_n*, y_n#
Thresholds partition [0,1] so each hand has a pure action (bet/call/fold/bluff/raise-bluff) at each depth n. y_n* separates calling the nth bet from bluffing the (n+1)th (if allowed) or folding; y_n# separates bluffing the nth bet from already folding to the (n−1)th bet.

**Formel:** Definitions (verbal, no single algebraic expression):
- y_n*: smallest (worst) value hand that is *not* used as a bluff for the (n+1)th bet; it is the threshold between calling the nth bet and either (i) putting in the (n+1)th bet as a bluff (if allowed) or (ii) folding.
- y_n#: threshold between hands that put in the nth bet as a bluff and hands that have already folded to the (n−1)th bet.

These are linked in that y_n* is paired with y_{n+1}# via indifference between bluffing vs folding and calling vs folding at adjacent levels.

**Für den Bot:** Represent river (or any street) strategy as ordered thresholds where each region has a fixed pure action profile (bet/fold/call/raise/raise-bluff). For deeper trees, define and solve for paired value/bluff thresholds per bet level instead of trying to reason action-by-action.

## Alpha for n-bet bluffs: α_n = 1/(P + (2n−1))
Generalized bluffing ratio when a bluff costs n bets into pot P (in units of a single bet): α_n is the fundamental pot-odds ratio that determines optimal value:bluff sizing relationships at level n.

**Formel:** α_n = 1 / ( P + (2n - 1) )

Special cases:
α_1 = 1 / (P + 1)
α_2 = 1 / (P + 3)

As P → ∞, α_n → 0.

**Für den Bot:** When facing a pot P and considering a bluff line that risks n bets total (e.g., raise-then-jam), your optimal bluff-to-value *ratio in handspace* is controlled by α_n. Deeper, more expensive bluffs (larger n) must be rarer (smaller α_n).

## Value-raise / raise-bluff sizing at 2-bet level: y2 and x2*
In [0,1] Game #10 (two-bet, no check-raise), Y’s value raises at threshold y2 and X calls raises down to x2*. Optimality requires Y to raise for value with half of X’s calling region, and X’s raise-call region is a (1−α_2) fraction of his betting range.

**Formel:** From Y’s indifference at y2:
  y2 = x2* - y2  =>  y2 = x2* / 2

From Y’s indifference at y1* (where Y is indifferent between call and raise-bluff vs X’s bet):
  x2* = (P + 2)(x1 - x2*)
  x2* = x1 (P + 2) / (P + 3)
  x2* = (1 - α_2) x1,  where α_2 = 1/(P+3).

**Für den Bot:** For a two-bet sequence where villain cannot 3-bet, your value-raise region on the second bet should be roughly half of opponent’s raise-calling region; your bet-call subset should be a (1−α_2) fraction of your betting range. This limits over-folding to raises and sets correct raise frequency.

## Value-bet vs bluff-bet region size: α relationship (one-bet and embedded)
Standard value/bluff sizing relationship in [0,1] games: the size of the bluffing region equals α times the size of the associated value region. This appears in many equations (e.g., relating x1, x0 or y1, y0) and generalizes per bet level via α_n.

**Formel:** Canonical form (one-bet case, X betting vs Y):
  α x1 = 1 - x0
so size(bluff region) = 1 - x0 = α x1 = α * size(value-bet region).

General n-bet form (from text):
  α_n y_n = (y_n# - y_{n-1}*)
so size(bluff region at level n) = α_n * size(value region at level n).

**Für den Bot:** On any single betting decision (bet/check, raise/call, jam/fold), your bluffing portion of that action should have weight α_n relative to your value portion, where α_n is determined by current pot and bet geometry. This directly underlies balanced c-bet, raise, and jam frequencies.

## Relationship between X’s betting and bluffing regions: α x1 = 1 - x0
In [0,1] Game #10, X’s value-bet region length is x1, his pure-bluff region is [x0,1]. Indifference at Y’s fold/call threshold yields a simple proportionality between X’s value and bluff lengths.

**Formel:** α x1 = 1 - x0  (Equation 17.5)

Equivalently:
  size(X bluff region) = α * size(X value-bet region)
  x0 = 1 - α x1.

**Für den Bot:** When you have a one-shot bet (no further raises), choose your bluffing frequency so that the fraction of your betting range that is bluff equals α = 1/(P+1). That is MDF-style: your opponent then cannot profitably overfold or overcall against your bet.

## Y’s fold fraction vs X’s bluffs: y2# = 1 - α
In [0,1] Game #10 (two-bet, no check-raise), Y’s threshold y2# between raise-bluff and fold versus an X bluff satisfies an MDF-type condition: Y folds exactly an α fraction of his hands.

**Formel:** From X’s indifference at x0:
  y2# = 1 - α   (Equation 17.10)

Interpretation: size(Y folding region) = α, size(Y non-fold region) = 1 − α.

**Für den Bot:** Against a bluffing bet where you can also raise-bluff, optimal defense folds exactly an α fraction of your distribution, independent of hand placement, as long as strategy is undominated. This is the MDF statement: fold_freq = α = 1/(P+1).

## Y’s call vs bet-check threshold: y1 = (x1* + x1)/2
With no raises possible over Y’s call at y1 (one-bet subgame), Y’s call/bet-check threshold is the midpoint between X’s check-call boundary x1* and his bet boundary x1.

**Formel:** y1 = (x1* + x1) / 2   (Equation 17.2)

**Für den Bot:** When villain cannot raise you, your marginal value-bet threshold is roughly the midpoint between your bet and check-call thresholds. This identifies the hand where betting vs check-calling are exactly equal in EV.

## X’s check-call vs bet-fold marginal value region: x1* and y0
X’s marginal check-call threshold x1* is related to Y’s bluffing / not-betting thresholds. It encodes the tradeoff between inducing bluffs vs extracting thin value when X checks marginal hands.

**Formel:** From [0,1] Game #10 (no check-raise):
  x1* = (1 - α)(y0 - x1) + x1   (Equation 17.6)

From X’s indifference at x1* when facing Y’s bet in the no-check-raise game earlier:
  1 - y0 = α y1  (Equation 17.9)

So x1* and y0 are tied by α and y1.

**Für den Bot:** For marginal hands that might value-bet or check-call, solve indifference by accounting for: (i) value from calls by slightly weaker hands, (ii) losses vs induced raises/bluffs when betting, (iii) value from induced bluffs when checking. That defines your exact check-call vs bet-fold cutoff.

## Raise-bluff region sizing at 2-bet level: α_2 y2 = (y2# - y1*)
In the two-bet [0,1] game, Y’s raise-bluff region length equals α_2 times his value-raising region length y2. This is the 2-bet analogue of the standard α relation: costlier raises imply a smaller bluff region.

**Formel:** α_2 y2 = (y2# - y1*)   (Equation 17.7)

Interpretation:
  size(raise-bluff region) = α_2 * size(value-raise region).

**Für den Bot:** When choosing raise frequencies (second bet), make your bluff raises a fraction α_2 of your value raises. This prevents villain from folding too often vs raises without getting punished by your value region.

## Indifference between X bet-fold vs check-call at x1
At X’s marginal bet vs check hand x1, he must be indifferent between betting and then folding to a raise, or checking and possibly calling a bet. The resulting condition links Y’s call-but-no-bet region, Y’s raise-bluff region, and Y’s pure-bluff region.

**Formel:** From table for X at x1 (Equation 17.8):
  y1* - y1 = (P + 1)(y2# - y1*) + (1 - y0)

Left side: size of Y’s region that *calls* X’s bet but would not bet if checked to.
Right side: expected loss vs raise-bluffs ((P+1) times raise-bluff region size) plus missed induced bluffs (1 - y0).

**Für den Bot:** To set optimal thin value-bets, balance: (i) value from calls by weaker hands, vs (ii) punishment from getting bluff-raised off equity, and (iii) loss of bluff-catching EV when you don’t check. This is the structural condition that defines your thinnest profitable bet.

## General relationship between X’s betting and Y’s raising: y2 = R x1 (no check-raise)
In [0,1] Game #10, Y’s value-raise range size y2 is proportional to X’s value-bet range size x1 by a constant R that depends on pot size and number of remaining bets.

**Formel:** Key relationship combining (17.3) and (17.4):
  y2 = x1 (1 - α_2) / 2   (Equation 17.11)
So define:
  R = (1 - α_2)/2
  y2 = R x1.

As P → ∞, α_2 → 0, so R → 1/2.

**Für den Bot:** Your optimal value-raise range on a street should be a fixed fraction R of villain’s value-bet range, determined only by pot/stack geometry. When stacks are deep (large P), you value-raise with about half as many hands (by measure) as villain value-bets with.

## General x1 formula without check-raise (finite bets): Equation 17.12
For non-check-raise [0,1] games with finite number of bets, there is a closed-form expression for X’s core betting threshold x1 in terms of α, α_2 and R (the raise/value ratio). This carries over to games with more bets by just changing R.

**Formel:** From Equation 17.12:
  x1 = (1 - α)^2 / [1 + α + (2 - α)(1 - α_2) R]

where
  α  = 1/(P + 1)
  α_2 = 1/(P + 3)
  R   = y2 / x1 (game-specific ratio for value raise vs bet).

**Für den Bot:** For a given stack/pot configuration and assumed relative aggressiveness R (how often villain raises vs bets), you can compute the exact bottom of your betting range x1 that makes you indifferent between betting and checking. This is the core river-threshold equation for jam-or-check decisions without check-raise possibilities.

## General y1 formula with check-raise (finite bets): Equation 17.13
In the two-bet [0,1] game where check-raise is allowed, the analogue of x1 is Y’s first-bet value threshold y1. The formula mirrors the no-check-raise case but with a different effective R capturing check-raise geometry.

**Formel:** From Equation 17.13:
  y1 = (1 - α) / [1 + α + (1 - α_2) R]

where again
  α  = 1/(P + 1)
  α_2 = 1/(P + 3)
  R is now the appropriate ratio in the check-raise game (effectively ratio of successive Y thresholds in the check-raise variant).

**Für den Bot:** When check-raises are possible, the bottom of your betting range shifts because you must fear being check-raised and also can value from inducing bets. Use a y1-style formula: your minimal value-bet strength is (1−α) divided by a denominator that grows with both α and your opponent’s check-raise frequency encapsulated in R.

## Mapping no-check-raise ratios to check-raise games
The ratio between Y’s thresholds and X’s thresholds in the no-check-raise game becomes the ratio between successive Y thresholds in the check-raise game. This allows reuse of solved no-check-raise structures when enabling check-raises.

**Formel:** Stated relationship:
- In the no-check-raise game, y2 = R x1.
- In the check-raise game, the same R appears as the ratio between successive Y thresholds (e.g., y2 and y1):
  y2 = (1 - α_2)/2 * y1 (in the specific 2-bet case; generally successive yn).

**Für den Bot:** To extend a strategy from a simple bet/call/fold tree to include check-raises, keep the same R between value thresholds but re-interpret it as linking successive thresholds for the aggressor. This lets you build check-raise strategies by ‘recycling’ the no-check-raise solution with minimal extra work.

## Infinite-bet [0,1] games: generic bluff/value relation any_n = (y_n# − y_{n−1}*)
In the infinite-raise, no-check-raise [0,1] game, each bet level n has a value-bet region y_n and an associated bluff region (y_n# − y_{n−1}*). Their lengths satisfy the same α_n proportionality.

**Formel:** For any appropriate n:
  α_n y_n = (y_n# - y_{n-1}*)

where α_n = 1 / (P + (2n - 1)).

**Für den Bot:** In multi-barrel or re-raise wars (e.g., bet/3-bet/5-bet), at each level your bluffing share should shrink according to α_n, the pot-odds at that level. Earlier (cheaper) aggression can be bluff-heavy; later (expensive) bets must be value-dense.

## Limiting behavior as P → ∞ (deep pot limit)
As P → ∞ (very large starting pot), all α_n → 0 and R converges to 1/2 in the two-bet no-check-raise game, so value-betting and value-raising thresholds converge to 1/2 and 1/4 respectively.

**Formel:** As P → ∞:
  α → 0, α_2 → 0.
From y2 = R x1 and R = (1 - α_2)/2 ⇒ R → 1/2.
In [0,1] Game #10 limit table:
  x1 → 1/2
  y2 → 1/4
  x2* → 1/2
and so on.

**Für den Bot:** When the pot is huge relative to the bet (e.g., river after big earlier action), optimal thresholds approach those from the no-pot toy game: bet roughly top half, raise top quarter, and bluff very little. The deeper the pot, the less you should bluff at the margin.

## Explicit closed-form thresholds for [0,1] Game #10 in terms of α
The full solution to the simplest complete two-bet [0,1] game expresses all thresholds as rational functions of α. It’s not to be memorized, but it confirms all local α and R relationships and can be used for calibration.

**Formel:** Given α = 1/(P+1):

 y2  = (1 - α)^2 (1 + 2α) / (7α^2 + 9α + 4)
 y1  = (1 - α)(8α^2 + 9α + 3) / [ (1 + α)(7α^2 + 9α + 4) ]
 y1* = 1 - α - α^2 * (1 - α)^2 (1 + 2α) / (7α^2 + 9α + 4)
 y2# = 1 - α
 y0  = 1 - α(1 - α)(8α^2 + 9α + 3) / [ (1 + α)(7α^2 + 9α + 4) ]
 x2* = 2(1 - α)^2(1 + 2α) / (7α^2 + 9α + 4)
 x1  = 2(1 - α)^2(1 + 2α)^2 / [ (1 + α)(7α^2 + 9α + 4) ]
 x1* = 4(1 - α)(2α^2 + 2α + 1) / (7α^2 + 9α + 4)
 x0  = 1 - 2α(1 - α)^2(1 + 2α)^2 / [ (1 + α)(7α^2 + 9α + 4) ]

**Für den Bot:** You can numerically instantiate the exact equilibrium thresholds for given P to benchmark a solver or to sanity-check river strategies with a discretized [0,1]-style toy model. But for practical NLHE implementation, use the structural α and R rules, not these specific polynomials.

## Finite-pot multi-raise [0,1] game recursion for Rp
Recursive relation for the geometric multiplier Rp that links successive value thresholds (x_n,y_n) when many raises are allowed and a finite pot P is in the middle.

**Formel:** Given pot size P (in betting units) before the first bet of the street, define Rp so that
  y2 = Rp * x1
  x3 = R_{p+2} * y2
  y4 = R_{p+4} * x3
and in general thresholds keep alternating with step-2 pot increments. Plugging these into the indifference
  x1(P+2)/(P+3) = 2 y2 + x3 (P+4)/(P+5)
with y2 = Rp x1 and x3 = R_{p+2} y2 = Rp R_{p+2} x1 gives cancellation of x1 and yields the recursion
  (P+2)/(P+3) = 2 Rp + Rp R_{p+2} (P+4)/(P+5).
Equivalently,
  R_{p+2} = [(P+2)/(P+3) - 2 Rp] * (P+5) / [Rp (P+4)].
Boundary condition: as P -> infinity, Rp -> r = sqrt(2) - 1 (no-fold infinite-raise limit).

**Für den Bot:** For deep multi-raise NLHE spots with finite stacks, optimal value thresholds scale approximately geometrically with a pot-dependent factor Rp. You can approximate this scale factor via the recursion above (with boundary Rp ≈ sqrt(2)-1 at large P) and then place betting/raising thresholds as multiples of earlier ones. This gives a principled way to space thresholds and therefore bluffing regions across multiple raise levels as a function of SPR.

## nth bluffing region size vs value region size (α-power law)
In layered [0,1] betting games, the width of the nth bluffing interval is α^n times the width of the corresponding value interval at that level.

**Formel:** For the nth bet level, with value region [v_n_low, v_n_high] and bluff region [b_n_low, b_n_high],
  |bluff_region_n| = α^n * |value_region_n|,
where α = P / (P + 1) in the one-street finite-pot half-street/full-street games (and similar α-like ratios for general P). In the excerpted three-bet segment:
  x3# - x2* = α^3 x3,
so the size of the 3rd-level bluff-raise region is α^3 times the size x3 of its value region.

**Für den Bot:** As betting continues on a street, optimal bluff frequencies shrink geometrically: deeper raises should be increasingly value-heavy. In practice, for a given SPR-derived α, your 3-bet bluffs should be a much smaller slice of your 3-bet value region than your flop c-bet bluffs are of your flop value range.

## Minimum continue fraction vs α across raise levels
After placing the nth bet for value, you must continue (call or re-raise) with at least a fixed fraction 1 - α^{n+1} of the hands that put in that bet to avoid being exploited by bluff-raises at the next level.

**Formel:** Given the base α for the game and considering sequences of raises:
  When you put in the nth bet for value, you must continue with at least
    1 - α^{n+1}
  of the hands that placed that bet, otherwise an opponent can profitably add (n+1)th-level bluffs.
In the excerpt, for the 3rd bet:
  x3# = (1 - α^2) x1,
which is consistent with the general pattern: the continue region retaining a (1 - α^{n+1}) proportion of the previous value-raiser's range.

**Für den Bot:** Once you bet or raise for value, you cannot over-fold to later raises: at each raise level you must defend a minimum fraction of the range that invested the previous bet. For NLHE, calibrate your fold frequencies on later streets so you do not fold much more than α^{n+1} of your earlier-investing range; otherwise you invite profitable bluff 3/4/5-bets.

## General finite-pot threshold relation (Equation 17.14 form)
Indifference of a critical calling/raising threshold y2 in a three-level betting game with a finite pot P produces a linear relationship among earlier thresholds x1, x3 and y2 after converting α to P.

**Formel:** For a particular three-bet structure with pot P before the street, the y2 indifference condition yields
  (1 - α^2) x1 - α^3 x3 = 2 y2 + (P + 3) α^3 x3.
Using α = P/(P+1) and simplifying, this becomes
  x1 (P + 2)/(P + 3) = 2 y2 + x3 (P + 4)/(P + 5).   (17.14)
This is a specific instance of the general recurrence that links xn, y_{n+1}, x_{n+2} as thresholds are incremented by 2 bets.

**Für den Bot:** Given an SPR (encoded in P) and choices of two adjacent value thresholds x1 and x3, you can solve directly for the intermediate defend/raise threshold y2 by enforcing indifference. This is the blueprint for building multi-threshold strategies: fix two cuts in your range and let indifference pin down the third.

## Geometric threshold structure via Rp on deep streets
Beyond the second raise, the pattern of thresholds becomes geometric up to a scale factor Rp that depends only on the pot size, making the game self-similar at deeper levels.

**Formel:** Given Rp at pot size P,
  y2 = Rp x1
  x3 = R_{p+2} y2
  y4 = R_{p+4} x3
  ...
In the no-fold limit with infinite stack (P → ∞), Rp ≡ r = sqrt(2) - 1 for all thresholds, and in that special case for [0,1] Game #6 (no check-raise):
  x1 = 1 / (1 + 2 r)
  x_n = r^{n-1} x1   (odd n > 1)
  y1 = (1 + r) x1
  y_n = r^{n-1} x1   (even n > 1).

**Für den Bot:** On very deep streets where further raises are possible, optimal value/bluff thresholds tend to fall on a geometric grid (ratio ~ sqrt(2)-1 in the no-fold limit). In NLHE, you can approximate river raising thresholds as geometric in equity distance from the nuts when stacks are deep and folding is rare.

## Game value of infinite-raise no-fold game without check-raise ([0,1] Game #6)
Closed-form EV for Y in the symmetric infinite-raise, no-fold game, using the special region where both players hold strong hands with equity g = r/2 for Y.

**Formel:** Let r = sqrt(2) - 1 and x1 = 1/(1 + 2 r), y1 = (1 + r) x1.
The special strong-vs-strong equity region has Y's equity
  g = r / 2.
The overall expectation for Y is
  <Y> = (1 - y1)(y1 - x1) + r x1^2 / 2.
Plugging numbers: x1 = 1/2, y1 = 3/4, r = sqrt(2) - 1,
  <Y> = (1 - 3/4)(3/4 - 1/2) + r * (1/4) / 2 = 1/16 + r/8 ≈ 0.11428.

**Für den Bot:** In a perfectly symmetric no-fold deep-raise environment, position alone is worth about 0.114 bets to the in-position player. This quantifies that even with arbitrarily many raises allowed, most of the positional edge still comes from the first few actions; later raises add only marginal EV.

## Game value of infinite-raise no-fold game with check-raise ([0,1] Game #7 / 16.4 analogue)
When check-raise is allowed in the infinite-raise no-fold setting, and X is indifferent between betting and check-raising above y2, the strong-vs-strong equity region remains g = r/2, but the matrix shrinks to 2×2 and the overall value simplifies.

**Formel:** Let r = sqrt(2) - 1 and y1 be Y's first betting threshold in the infinite check-raise game with the property x1 = y1, x3 = y3, ... (X's thresholds equal Y's). In the strong-vs-strong region (both > y1), equity remains
  g = r/2.
The simplified payoff matrix leads to overall EV for Y:
  <Y> = r y1^2 / 2.
Using the known optimal y1 = 1 / sqrt(2) (implied by earlier chapters), this gives
  <Y> = r / 4 ≈ 0.10355.

**Für den Bot:** Allowing check-raises in a deep, no-fold environment reduces the in-position player's edge slightly (from ~0.114 to ~0.104). For NLHE, adding check-raise options is worth something to the out-of-position player but not nearly as much as simply giving him the option to lead instead of being forced to check.

## Game value of half-street finite-pot bluff-or-call game ([0,1] Game #2)
Closed-form EV for Y in the finite-pot half-street game with bluffing and calling, where only one bet can go in and X chooses to call or fold facing Y's bet.

**Formel:** Solution thresholds:
  y1 = (1 - α) / [(2 - α)(α + 1)]
  x1* = 2 y1
  1 - y0 = α y1.
Region EVs for X:
  G2 = <X on [0, y1]> = -α y1
  G1 = <X on [y1, y0]> = (1 - α) y1
  G0 = <X on [y0, 1]> = (1 - α) y1 / 2.
Game value for Y (G = -EX) by the weighted sum is
  G = y1 G2 + (y0 - y1) G1 + (1 - y0) G0
    = (1 - α) y1 - (2 - α)(1 + α) y1^2 / 2   (18.1)
which can be simplified using the expression for y1 to
  G = y1 (1 - α) / 2.

**Für den Bot:** In one-street bluff-or-call spots with a capped pot (e.g., river shove for P into P), the GTO EV is fully determined by α and the optimal threshold y1. Once you compute y1 from α, the game value and optimal bluffing frequency follow; this is the foundational MDF/α model for river bluff-catch decisions.

## Game value of finite-pot full-street 2-bet game without check-raise ([0,1] Game #5)
Value of the finite-pot full-street game with one bet and one raise allowed, no check-raise, using best response for X against Y's fixed optimal strategy.

**Formel:** Solution thresholds:
  x1 = 1/4,
  y1 = 3/4,
  y2 = 1/4.
Using a best response for X (betting or checking on [1/4, 3/4] with equal EV), the table in Figure 18.2 yields total EV for Y:
  G_Y = 1/8.
Y's average action is 1 bet, so his edge is 12.5% of his total investment.

**Für den Bot:** When only one bet and one raise are possible and there is no check-raise, position alone is worth about 0.125 bets in this normalized model. In NLHE, when later raises are unlikely (e.g., capped SPR or structure), a large part of positional advantage is captured by the ability to make a single raise after facing a bet.

## Game value of finite-pot full-street 2-bet game with check-raise ([0,1] Game #7, finite version)
Equity impact of allowing check-raises in the finite-pot full-street two-bet game, again via best response for X.

**Formel:** Solution thresholds for the finite 2-bet check-raise game:
  x1 = 5/9,
  y1 = 2/3,
  x2 = 1/9,
  y2 = 1/3.
Using a simplified best-response strategy for X (bet below 5/9, check/call above 5/9), the table in Figure 18.3 yields
  G_Y = 1/9.
Comparing to the no-check-raise case (G_Y = 1/8), the value of check-raise to X is
  ΔG_X = (1/8 - 1/9) = 1/72
in X's favor.

**Für den Bot:** In a finite-pot single-street game, adding check-raises only modestly increases the out-of-position player’s EV (~0.014 bets in this model). For NLHE, the main EV comes from having the opportunity to bet; check-raising refines your defense but is second-order compared to opening the betting.

## Best-response simplification using indifference
When one player is fixed to optimal strategy, the other can be assumed to play any best response on indifference regions to simplify EV computation without changing game value.

**Formel:** If Y plays an optimal strategy σ_Y*, the game value is
  G = max_{σ_X} EV(σ_X, σ_Y*).
For any region R of X's hands where all admissible actions a satisfy
  EV(a | h ∈ R, σ_Y*) = constant,
we may choose any deterministic action on R (e.g., always betting, always checking) to compute EV. This does NOT produce an equilibrium strategy for X but leaves G unchanged.

**Für den Bot:** When solving or approximating toy subgames for training a bot, you can treat the in-difference parts of the best response as arbitrary for EV calculations. This lets you collapse complicated mixed strategies into simple pure ones for value computation, while still using the optimal thresholds from the indifference equations.

## Relation between bluff threshold gaps in finite full-street game ([0,1] Game #9 snippet)
In the finite full-street game with folding, the size of the intermediate region where Y value-bets and X is indifferent to betting vs checking equals the size of the value-bet-but-folds region, enforcing X's indifference.

**Formel:** For [0,1] Game #9 (finite full-street, one bet and one raise, with folding), Y's optimal solution was
  y1 = (1 - α)/(1 + α)
  y0 = (1 + α^2)/(1 + α)
  y1* = 1 - α.
Indifference of X on [0, y1] to betting or checking against Y's strategy requires the gain from Y's extra bet in [y1, y1*] to balance the loss from value-bet calls in [y0, 1]. As shown,
  y1* - y1 = (1 - α) - (1 - α)/(1 + α) = (α - α^2)/(1 + α) = α y1 = 1 - y0.
So
  size([y1, y1*]) = size([y0, 1]).

**Für den Bot:** In finite-pot one-street bet/raise games, the region where your in-position opponent can thin value bet must be offset in size by a region where he overbets into hands that will fold, to keep you indifferent between leading and checking. For NLHE river play, balancing your thin value bet range with appropriate bluff density naturally equalizes these regions and protects your check range.

## [0,1] finite‑pot Game #2 value (X checks dark, Y can bet)
Game value G as function of pot‑to‑bet ratio a=P/(P+1) when X always checks, Y may bet; no folding by X.

**Formel:** Given y1 = (1 - a)/(1 + a), game value for Y is
G(a) = a * (1 - a)^2 / (2 * (1 + a))

Domain: 0 < a < 1.

**Für den Bot:** When modeling single‑street river spots with constrained strategies (e.g. X forced to check), you can express villain’s EV as a smooth function of a=P/(P+1). This lets a bot compare different abstractions or bet‑size configs by evaluating EV(a) directly rather than re‑solving from scratch.

## [0,1] finite‑pot Game #2: threshold y1
Betting threshold y1 for Y’s value region when X checks dark in the finite‑pot [0,1] game.

**Formel:** y1(a) = (1 - a) / (1 + a)

with a = P/(P+1).

**Für den Bot:** River thresholds in simple toy models shrink monotonically as the pot grows (a→1). A bot can approximate real river thresholds by mapping equity cutoffs as a function of a=P/(P+1) and using them to initialize/regularize its policy network.

## [0,1] finite‑pot Game without check‑raise: region payoffs G0..G3
Piecewise EV for Y across X’s hand‑interval regions [y0,1], [y1,y0], [y2,y1], [0,y2] in a two‑bet finite‑pot game where Y can raise but X cannot check‑raise. These are used to form global EV as a weighted sum.

**Formel:** Given parameters a, y0, y1, y2 and derived boundaries y1*, y2#, the local values (from X’s perspective) are:

G0 = <X on [y0,1]> = (1 - a) * y1 / 2
G1 = <X on [y1,y0]> = (1 - a) * y1
G2 = <X on [y2,y1]> = y2 - a * y1
G3 = <X on [0,y2]> = (1 - a^2) * y2 - 1 + a

Global value for Y:
<Y> = y2 * G3 + (y1 - y2) * G2 + (y0 - y1) * G1 + (1 - y0) * G0

which they also expand to:
<Y> = -(1 - a) * y2 - a^2 * y2^2 + (1 + a) * y1 * y2 + (1 - a) * y1 - (1 + a)(2 - a) * y1^2 / 2

**Für den Bot:** Multi‑size/multi‑street abstractions can be evaluated as integrals (or sums) over equity‑rank regions. A bot can estimate EV by partitioning its range into intervals with approximately constant action and plugging into such piecewise formulas, rather than relying only on tabular CFR.

## Triple indifference in region [y2,y1]
In a two‑bet game without check‑raise, X holds hands in [y2,y1] where he is simultaneously indifferent among (i) check‑calling, (ii) bet‑folding, and (iii) bet‑calling versus Y’s optimal strategy. This triple indifference pins down thresholds and frequencies with fewer equations.

**Formel:** For hands in [y2,y1], EV_x(check‑call) = EV_x(bet‑call) = EV_x(bet‑fold).

One of the indifference equations quoted:

y1* - y1 = (P + 1) * (y2# - y1*) + (1 - y0)

EV_x(bet‑call) = 2 (y2# - y1*) + y1* - y1 = (P + 3)(y2# - y1*) + 1 - y0 = y2 + a y1
EV_x(check‑call) = (y2 - 0) + (1 - y0) = y2 + a y1

So EV_x(bet‑call) = EV_x(check‑call) over [y2,y1].

**Für den Bot:** When fitting simplified strategies (e.g. only one bet size and jam), target regions where multiple actions are nearly equal‑EV: there the bot can randomize or slightly mis‑size without big loss. Use triple‑indifference constraints to solve for equilibrium thresholds in compact river models and embed them as priors in learning.

## [0,1] Game #11 (two bets, check‑raise allowed) value relation
Game #11 (two‑bet game with check‑raise) has the same functional value form as Game #10 (no check‑raise) when holding Y’s strategy fixed; only the thresholds y1,y2 change, reducing Y’s equity.

**Formel:** Let V10(y1,y2,...) denote the value formula for Game #10. Then for Game #11 (with check‑raise),
V11 = V10 evaluated at different optimal y1', y2' with y1' ≥ y1, y2' ≥ y2 (qualitative) and V11 ≤ V10 from Y’s perspective.

Formally: V11(y1', y2', ...) = V10(y1', y2', ...), but argmax over X’s additional option shifts (y1', y2') to lower Y’s EV.

**Für den Bot:** Adding actions (e.g., allowing check‑raises or overbets) never decreases your equilibrium EV. A bot’s action space on later streets should be rich (at least include check‑raise) even if usage frequency is low; restricting actions is only acceptable as an exploitative simplification vs weak opponents.

## Strategic options have non‑negative value
In all [0,1] comparisons, whenever one player gains a new legal action (bet, raise, reraise, check‑raise, fold), that player’s equilibrium EV never worsens and usually strictly increases.

**Formel:** For any zero‑sum extensive‑form game Γ and its extension Γ' that differs only by adding actions to player i,
V_i(Γ') ≥ V_i(Γ).

In [0,1] examples:
- Game #2 (X can fold) gives X ≥ EV than Game #1 (no fold).
- Game #4 vs #1 (X gains bet),
- Game #5 vs #4 (Y gains raise),
- Game #6 vs #5 (X gains reraise),
- Game #7 vs #5 (X gains check‑raise):
player with new option never loses equity.

**Für den Bot:** When designing a bot’s action abstraction, prune carefully: any removed action (e.g., small probe bet, small 3‑bet) can only hurt worst‑case EV. Keep at least one bluff size and one value size in each direction on each street.

## Value of r ≈ 0.41 in no‑fold [0,1] river games
In no‑fold [0,1] river games (and their infinite‑pot limits), the optimal raising frequency on each level is approximately r ≈ 0.41 of the preceding betting range. This creates geometric layers of raising frequencies: r, r^2, r^3,...

**Formel:** Let B0 be the set of hands the initial bettor would bet.
Then optimal raising structures follow approximately:
- First bettor bets fraction r of total hands: |B0| ≈ r.
- Second player raises with fraction r of B0: |R1| ≈ r^2 of total hands.
- First player reraises fraction r of R1: |R2| ≈ r^3.
- etc.

Numerically:
r ≈ 0.41
r^2 ≈ 0.1681
r^3 ≈ 0.0689
r^4 ≈ 0.0283
r^5 ≈ 0.0116

**Für den Bot:** On rivers where villain cannot realistically fold much (e.g., huge pot, capped ranges), a good heuristic is: bet with ~40% of hands; raise with ~40% of the hands villain bets; 3‑bet with ~40% of the hands villain raises, etc. A bot can use ~0.35–0.41 as a prior for value+bluff density in such dense, showdown‑oriented spots.

## Example: 1081 NLHE combos on J♥9♣8♠3♦2♣ and r‑layers
Concrete mapping of the r ≈ 0.41 principle to a 1‑street river abstraction on a real board, partitioning 1081 combos into geometric layers corresponding to bet, raise, 3‑bet, etc.

**Formel:** Total combos considered: N = 1081.
Using r ≈ 0.41, they estimate:
N * r ≈ 1081 * 0.41 ≈ 448 (hands to bet)
N * r^2 ≈ 1081 * 0.41^2 ≈ 185 (hands to raise)
N * r^3 ≈ 1081 * 0.41^3 ≈ 77 (hands to 3‑bet)
N * r^4 ≈ 1081 * 0.41^4 ≈ 32 (hands to 4‑bet)
N * r^5 ≈ 1081 * 0.41^5 ≈ 13 (hands to 5‑bet)

They map rough cutoffs:
- First bet: roughly third pair or better.
- Second bet (raise): around QJ or better.
- Third bet: first + third pair.
- Fourth bet: second‑nut straight.
- Fifth bet: nuts.

**Für den Bot:** In practice, a bot can approximate multi‑bet river ranges by sorting combos by equity and then taking cumulative fractions around r, r^2, r^3 as rough targets for bet/raise/3‑bet densities, then refining via solver/self‑play.

## Adjusting r when opponent can fold
In games where the opponent can fold (finite pot, realistic river), optimal raising/bluffing frequency is somewhat smaller than 0.41 because villain’s worst hands disappear from the calling range.

**Formel:** Heuristic adjustment:
- No‑fold games: r ≈ 0.41.
- With fold option: r_effective ≈ 0.35.

So approximate betting frequency:
Bet fraction ≈ 0.35–0.41 of hands that reach the node, conditional on range densities.

**Für den Bot:** A NLHE bot should not automatically port 0.41 to all rivers; when villain folds some hands, target ~35% bet frequency (value+bluff vs checking) as a prior, then adjust via solving/learning. This gives a starting point to calibrate bluff:value ratios and raise densities.

## Flexible vs brittle strategies around thresholds
In many [0,1] games, the player betting ‘into’ a check (X) has flexible regions where near‑threshold misplays have tiny EV cost because opponent will often bet for them. The player deciding whether to bet/value‑bet (Y) has brittle thresholds: failing to bet just‑strong‑enough hands immediately loses EV.

**Formel:** Let θ be a threshold equity for an action A.
- Flexible: dEV/dθ ≈ 0 in a small neighborhood (flat region of EV vs θ).
- Brittle: dEV/dθ < 0 appreciably; small under‑ or over‑shifts in θ produce first‑order EV loss.

In [0,1] games, holding Y optimal, X often has EV_x(h) ≈ constant for h in [θ−ε, θ+ε],
while EV_y(h) is sharply increasing around its betting threshold.

**Für den Bot:** When training or regularizing a bot, give higher precision (tighter constraints, more expressive policy) to brittle decisions: e.g., which thin value hands to bet on river. Slight inaccuracies in flexible regions (e.g., mixing check vs small bet with medium‑strength bluff‑catchers) matter much less.

## Range partitioning into regions with consistent actions
Equilibrium strategies in [0,1] (and [0,1]×[0,1]) games partition the hand space into contiguous regions where each player uses a single pure action (bet, check, call, fold, raise) or a simple mixture only at boundaries.

**Formel:** For equity‑ranked scalar hands h ∈ [0,1], equilibrium defines cutpoints 0 = t0 < t1 < ... < tn = 1 such that:
For h ∈ (ti, ti+1): player uses a fixed action profile Ai (bet, check, call, etc.).
Randomization only occurs at h = ti (ties) to satisfy indifference conditions.

Similarly, in [0,1]×[0,1] we have curves x1,y1,y2 partitioning the square (see separate item).

**Für den Bot:** A bot should treat the river as piecewise‑constant in strategy vs hand strength: most neighboring combos take the same action. Policy networks or tables can be smoothed/regularized to avoid noisy, highly mixed behavior except near key thresholds.

## Bluff–value balancing across regions
In finite‑pot [0,1] games, many regions exist primarily to balance value bets with corresponding bluffs and to specify which parts of the value set continue vs raises. For each value bet region, there is a matching bluff interval and a split of the value interval into call‑vs‑raise and fold‑vs‑raise parts.

**Formel:** Let B_v be a value betting region, B_b a bluffing region, and C ⊂ B_v the subset of value hands that call vs a raise.
Optimality imposes conditions like:
- Villain’s calling frequency f_call satisfies indifference: EV(bluff) = EV(check).
- Ratios:
  #(bluffs that reach node) / #(value bets that reach node) = function of pot odds.

MDF / alpha‑type relation (conceptual here):
If villain risks R to win P and you hold calling frequency c, then his break‑even bluff fraction α satisfies
α = (1 - c) * P / (c * R + (1 - c) * P)

[Note: this is a generalized statement; specific [0,1] forms are given earlier in book.]

**Für den Bot:** A NLHE bot should always pair its value bets with a calibrated bluff region and should subdivide value hands into continue‑vs‑raise vs fold‑vs‑raise segments. Use pot‑odds‑driven bluff:value ratios (alpha/MDF constraints) to initialize/regularize these region sizes.

## [0,1]×[0,1] high‑low game: geometry of Y’s strategies (no‑fold, two bets, no check‑raise)
Two‑dimensional static high‑low [0,1]×[0,1] game with no folding and two bets: Y’s strategies are described by curves y1 and y2 that are circles/quarter‑circles arising from indifference via area equalities of scoop regions.

**Formel:** Let (x,y) be Y’s high/low coordinates.

1) Indifference for raising boundary y2:
Area where X scoops by Y calling = Area where X scoops by Y raising.
This yields
x * y = 0.5 * (1 - y - x)(1 - x - y)
⇒ 2xy = 1 - 2x - 2y + x^2 + y^2 + 2xy
⇒ 1 = (x - 1)^2 + (y - 1)^2

So y2: (x - 1)^2 + (y - 1)^2 = 1 (quarter circle centered at (1,1), radius 1).

2) Indifference for betting boundary y1:
(1 - x)(1 - y) = 0.5 * (y - (1 - x))(x - (1 - y))
⇒ 1 = x^2 + y^2

So y1: x^2 + y^2 = 1 (circle centered at (0,0), radius 1).

3) X’s boundary x1 lies on the diagonal:
x1 satisfies y = 1 - x (by symmetry and equal area regions A and B).

**Für den Bot:** In multi‑attribute spots (e.g., high vs low in split‑pot games, or value vs blocker strength in NLHE), optimal bet/raise thresholds can form curved surfaces, not single scalar cutoffs. A bot should consider 2D (or higher‑D) features—like made‑hand strength vs draw potential—when defining which combos bluff/semi‑bluff vs check.

## [0,1]×[0,1] high‑low game: optimal second‑player betting frequency √2
In the constrained [0,1]×[0,1] high‑low game (two bets, no fold, no card removal, no check‑raise), the fraction of hands that the second player should bet is √2⁄2 ≈ 0.7071.

**Formel:** Result: in this game, the optimal betting frequency for the player acting second is:
Bet fraction = sqrt(2)/2 = 1 / sqrt(2) ≈ 0.7071.

The text states this as “√4” (interpreted as √(1/2) inverse), giving 1/√2.

**Für den Bot:** In some dense showdown‑oriented split‑pot or capped‑range spots, optimal frequencies can be much higher than typical river c‑bet rates (~40–60%). A split‑pot or no‑fold‑like river may justify very high bet frequencies (~70% of hands). A bot’s priors should allow such high bet densities in appropriate nodes.

## Static two‑street clairvoyant game: no incentive for X to bet
In a two‑street static game (hand values don’t change), with limit betting and a clairvoyant opponent Y, X never bets on either street; he only check‑calls with hands that win often enough, because any bet is perfectly exploited.

**Formel:** Given a static distribution where Y knows the final outcome for each hand:
For any candidate betting strategy s_x that includes bets by X, Y can respond perfectly (fold all worse; raise/call all better) so:
EV_x(s_x with betting) ≤ EV_x(s_x' with all checks).

Therefore optimal X strategy: X never bets, only checks (and possibly folds/calls depending on Y’s bet).

**Für den Bot:** In spots where your betting range is nearly face‑up to a strong opponent (e.g., strongly polarized but obvious), your bot should sometimes drastically reduce pure bluffing and favor check‑call/check‑fold strategies, especially in static situations where no future card can rescue your bluffs.

## Single‑street clairvoyant calling strategy (α / MDF)
In any single‑street static game where villain (Y) chooses bet size s into pot P (or s in pot units), the non‑clairvoyant player (X) must defend a fixed fraction α of his range to make Y indifferent with a bluff. This is the core minimum‑defense‑frequency / alpha relationship.

**Formel:** Given pot P and bet size s (both in the same units):

alpha = s / (P + s)
MDF = 1 - alpha = P / (P + s)

When using pot‑normalized bet size s (bet as a multiple of the pot coming into the street):

alpha = s / (1 + s)
MDF = 1 / (1 + s)

**Für den Bot:** For any facing bet, compute α = bet/(pot+bet); fold α of your range (the weakest part) and continue with MDF = pot/(pot+bet) to prevent clairvoyant over‑bluff exploitation.

## Multi‑street static clairvoyant game: X’s street‑by‑street defense
In static multi‑street clairvoyant games, the non‑clairvoyant player X optimally plays each street independently as if it were a one‑street game with the current pot and bet size. On every street n he folds α_n of the hands that reached that street and continues with the rest.

**Formel:** For street n with pot P_n and bet size s_n:

alpha_n = s_n / (P_n + s_n)
MDF_n = 1 - alpha_n = P_n / (P_n + s_n)

Let H_n be the fraction of starting hands that reach street n (before facing the bet).
Then after the call/fold decision on street n:

H_{n+1} = H_n * MDF_n = H_n * P_n / (P_n + s_n)

In the two‑street equal‑bet toy analyzed in the excerpt with initial pot P and bet size 1 on both streets:

alpha_1 = 1 / (P + 1)
H_2 = 1 - alpha_1
On street 2, pot = P + 2, bet = 1:
alpha_2 = 1 / (P + 3)
X folds alpha_2 of H_2, calls with (1 - alpha_2) of H_2.

**Für den Bot:** When facing clairvoyant‑style pressure, choose your fold/call frequencies street‑by‑street using the single‑street α rule based on current pot and bet size, independent of previous streets; do not distort later‑street MDFs because of earlier calls.

## Two‑street clairvoyant toy: X’s detailed strategy (fixed bets)
In the two‑street fixed‑bet clairvoyant toy with pot P, bet size 1 both streets, X has three pure strategies vs Y’s two‑street lines. Indifference implies specific mix among fold‑now (x0), call‑once‑then‑fold (x1), and call‑twice (x2).

**Formel:** Given initial pot P and bet size 1 on both streets:

alpha = 1 / (P + 1)

First‑street indifference Y(Υ1) vs Υ0:
0 = P x0 - x1 - x2
x1 + x2 = 1 - x0
=> x0 = alpha

Second‑street indifference Y(Υ1) vs Υ2(bluff):
alpha P - x1 - x2 = alpha P + (P+1)x1 - 2x2
(P+2)x1 = x2
x1 + x2 = 1 - alpha
=> x1 = alpha^2 (1 - alpha)
=> x2 = (1 - alpha) - x1

So:
• X folds x0 = alpha immediately.
• Of the remaining 1 - alpha, he folds alpha^2 on the second street and calls down with (1 - alpha^2).

**Für den Bot:** In multi‑barrel static spots with equal bet sizes, your optimal fraction of fold‑now / call‑once / call‑twice can be derived purely from the αs at each street; structured multi‑street calling frequencies follow from single‑street MDFs.

## Two‑street clairvoyant toy: Y’s bluffing structure (fixed bets)
Y has nut (value) hands and dead (bluff) hands and three lines: bet‑once‑then‑give‑up (Υ1), check‑down (Υ0), bet‑both (Υ2). Indifference for X between folding, calling once, or twice imposes precise bluff/value ratios on both streets.

**Formel:** Using notation from the excerpt: y2 is the frequency of using Υ2, with yv being Y’s fraction of value hands in Υ2 and yb the fraction of bluffs in Υ2. y1 is frequency of using Υ1 with dead hands.

Indifference X0 vs X1:
P y1 + P yb y2 = - y1 + (P+1) yb y2 + yv y2
=> (P+1) y1 = yv y2 + yb y2
=> y1 = alpha * y2

Indifference X1 vs X2:
- y1 + (P+1) yb y2 + yv y2 = - y1 - 2 yb y2 + 2 yv y2
=> yv y2 = (P+3) yb y2
=> yb = alpha^2 yv

Interpretation:
• On the second street, with pot P+2 and bet 1, bluff:value ratio is alpha^2.
• On the first street, the hands that bet once then give up (Υ1) are alpha times the number of hands he will bet (value+bluff) on the second street.

**Für den Bot:** To be unexploitable in two‑barrel bluffs, choose your river bluff:value ratio using α at the river pot/size, and pre‑river, treat all (future value + future bluffs) as ‘value’ and add first‑street bluffs in proportion α to that set.

## General multi‑street clairvoyant bluff propagation (fixed bet sizes)
Y’s multi‑street bluff plan: on the final street he uses the usual single‑street bluff:value ratio from α_final; on prior streets he pretends that all hands that will bet the next street (value+bluffs) are value, and then adds bluffs to hit the earlier‑street ideal bluffing ratio for that pot and bet.

**Formel:** For final street with pot P_f and bet s_f, with M_f nut hands:

alpha_f = s_f / (P_f + s_f)
Bluff:value ratio on final street:
B_f / M_f = alpha_f
=> B_f = alpha_f * M_f

For previous street k with pot P_k, bet s_k, and M_k hands that will bet on street k+1 (i.e. all M_f + B_f that survive):

alpha_k = s_k / (P_k + s_k)
Total bluffable/value hands on street k: M_k
Bluffs that bet once then give up before k+1:
G_k = alpha_k * M_k
Total betting combos on street k: B_k = M_k + G_k

Iterating backwards over streets gives geometric factors > 1 for total bluffs on the early streets (as in the example where total flop bluffs were 3/5 of the number of value hands).

**Für den Bot:** When planning multi‑street bluff trees, pick your final‑street bluff:value ratio from MDF; then backward‑propagate: at each prior street add a one‑and‑done bluff set sized as α_current times the set of hands you will continue bluffing/value‑betting later.

## General multi‑street clairvoyant game with mixed bet sizes: X’s defense (two streets)
In a two‑street static game with arbitrary bet sizes s1 and s2 chosen by the clairvoyant player, X still defends each street according to its local α. The relation between call‑once and call‑twice frequencies is tied to α2 defined by second‑street pot size and bet s2.

**Formel:** Initial pot: 1
First‑street bet: s1
Second‑street bet: s2

First‑street α1:
alpha1 = s1 / (1 + s1)
=> x0 = alpha1
=> x1 + x2 = 1 - alpha1

Pot after first bet+call:
P2 = 1 + 2 s1
Second‑street α2:
alpha2 = s2 / (P2 + s2) = s2 / (1 + 2 s1 + s2)

From indifference:
x2 + x1 = x1 / alpha2
=> x1 = alpha2 (x1 + x2) = alpha2 (1 - alpha1)
=> x2 = (1 - alpha1) - x1

So of the callers of the first bet, a fraction alpha2 folds to the second bet, and 1 - alpha2 continues.

**Für den Bot:** When facing arbitrary bet sizes across streets, compute α_n from each street’s local pot and bet; among the hands that continue one street, fold an α_{n+1} fraction to the next bet to maintain indifference.

## Two‑street clairvoyant game with mixed bet sizes: Y’s bluffing ratios
In the two‑street arbitrary bet‑size clairvoyant toy, Y’s bluffing ratios again follow α relationships for each street: the number of ‘give‑up after first bet’ bluffs is α1 times the number of future second‑street betting hands, and the second‑street bluff:value ratio is α2.

**Formel:** Pot = 1, first bet s1, second bet s2.

Define α1 and α2 as above:
alpha1 = s1 / (1 + s1)
alpha2 = s2 / (1 + 2 s1 + s2)

Let y2 be frequency of using line Υ2 (bet both streets) with yv nut hands and yb bluffs. y1 is frequency of using Υ1 (bluff once then give up).

Indifference X0 vs X1:
y1 + y2 yb = -s1 y1 + (1 + s1) y2 yb + s1 y2 yv
=> (1 + s1) y1 = s1 y2 (yb + yv)
=> y1 = (s1 / (1 + s1)) y2 = alpha1 * y2

Indifference X1 vs X2:
- s1 y1 + (1 + s1) y2 yb + s1 y2 yv = - s1 y1 - (s1 + s2) y2 yb + (s1 + s2) y2 yv
=> (1 + 2 s1 + s2) y2 yb = s2 y2 yv
=> yb = (s2 / (1 + 2 s1 + s2)) yv = alpha2 * yv

**Für den Bot:** Design your two‑street bluffing tree so that (i) your second‑street bluff:value ratio equals α2 from the second‑street pot and bet, and (ii) your first‑street one‑and‑done bluffs are exactly α1 times the number of hands that will bet the second street.

## Pot‑growth ratio r and transformation between s and r
For each street, define r as the factor by which the pot grows if villain’s bet is called. This r parameter conveniently links bet size s and standard α formulas and underpins geometric pot growth.

**Formel:** For a street with initial pot p and bet size s:
Pot after bet and call: p + 2 s
Define r = (p + 2 s) / p

For the normalized case p = 1:

r = 1 + 2 s

Useful transformation:

r - s = 1 + s = (1 + r) / 2

Alpha in terms of s and r (p = 1):

alpha = s / (1 + s) = s / (r - s)

(These relations hold similarly with general p after normalization.)

**Für den Bot:** Think in terms of r (how much the pot grows if called) rather than raw bet size; this simplifies designing geometric bet progressions and lets you invert between α, s, and r easily.

## Betting factor B_n for value‑carryforward hands (clairvoyant multi‑street, arbitrary bet sizes)
Let M_n be the number of hands that are ‘for value’ on street n+1 (i.e., either actual nuts if it’s the last street, or the set that will bet the next street). On street n, Y bets those M_n plus additional bluffs. The total number of betting hands B_n on that street has a closed form in terms of r_n and s_n.

**Formel:** Normalize pot entering street n to 1.
Bet size (in pot units): s_n
Pot‑growth factor if called: r_n = 1 + 2 s_n

Alpha on street n: alpha_n = s_n / (1 + s_n) = s_n / (r_n - s_n)

With M_n hands to be carried forward as ‘value’ to street n+1, total betting hands on street n (value + bluffs) is:

B_n = M_n * r_n / (r_n - s_n)
Using r_n - s_n = (1 + r_n)/2, we get:
B_n = 2 M_n r_n / (1 + r_n)

This is the core factor relation:
B_n = 2 * M_n * r_n / (1 + r_n)

**Für den Bot:** Given a set of hands that you plan to barrel on the next street (true value + future bluffs), scale up to this street’s full betting range via B_n = 2 M_n r_n / (1 + r_n); this gives the correct blend of current‑street bluffs.

## Two‑street clairvoyant: total betting frequency in terms of r1, r2
With two streets, pot normalized to 1, and total nut fraction y, the total fraction of hands Y bets at least once can be written in terms of r1, r2. Maximizing it (subject to stack constraints) maximizes Y’s equity because X is indifferent to calling vs folding.

**Formel:** Let y be fraction of hands that are final‑street winners.
Let r1, r2 be pot‑growth factors on street 1 and 2.

On the river (street 2):
M2 = y (nut hands), so
B2 = 2 y r2 / (1 + r2)

On street 1, M1 = B2 (all hands that will bet street 2), so
B1 = 2 M1 r1 / (1 + r1) = 4 y r1 r2 / [(1 + r1)(1 + r2)]

Total fraction of hands bet at least once equals B1 (since it’s the earliest betting point):

B_total = 4 y r1 r2 / [(1 + r1)(1 + r2)]

Given fixed stacks N, s1 + s2 = N implies r1 r2 = 1 + 2 N (constant). Thus Y’s equity is proportional to:

f(r1, r2) = r1 r2 / [(1 + r1)(1 + r2)]

With r1 r2 fixed, maximize f by minimizing (1 + r1)(1 + r2) = 2 + 2N + r1 + r2. By AM‑GM, minimized when r1 = r2.

**Für den Bot:** For two‑street stack‑off lines at equilibrium, choose bet sizes so that the pot grows by the same factor on both streets (r1 = r2); this maximizes the fraction of your strong hands that can bet and, symmetrically, the profitability of your bluffs.

## Geometric growth of pot (optimal no‑limit multi‑street bet progression in static clairvoyant games)
In static no‑limit clairvoyant games with M streets, the optimal bet‑sizing scheme (given you always stack off with value by the river) is geometric growth: grow the pot by the same ratio r each street, so that by the final street both stacks are all‑in.

**Formel:** Initial pot: 1
Stacks: S (per player)
Total final pot if all‑in by river: P_final = 1 + 2 S

Let M = number of betting streets.
Geometric pot‑growth factor per street:

G = (P_final)^(1/M) = (1 + 2 S)^(1/M)

Normalized pot entering street n: p_n
Bet size s_n satisfies:

p_n + 2 s_n = G * p_n
=> s_n = (G - 1) * p_n / 2

If we normalize p_n = 1 for formula derivation (then scale):

s = (G - 1)/2

Bluff multiplier (ratio of total betting hands from street m to m+1):

r_b = (1 + 2 s) / (1 + s)


**Für den Bot:** When planning all‑in lines over multiple streets in relatively static situations (e.g., nuts vs capped range), aim to grow the pot by a constant factor each street (geometric bets) rather than flat or arbitrary bet sizes; this maximizes EV vs an optimal defender.

## Three‑street geometric growth: equity expression and generalization
For three streets, the same geometric principle holds: Y’s equity is maximized when the pot‑growth factors r1, r2, r3 are equal given a fixed all‑in stack size. The total bet frequency is proportional to r1 r2 r3 / ((1+r1)(1+r2)(1+r3)).

**Formel:** With three streets, pot normalized to 1 and final nut fraction y:

On river (street 3): B3 = 2 y r3 / (1 + r3)
On turn (street 2): B2 = 2 B3 r2 / (1 + r2)
On flop (street 1): B1 = 2 B2 r1 / (1 + r1) = 8 y r1 r2 r3 / ((1 + r1)(1 + r2)(1 + r3))

Total fraction of hands bet at least once is B1.
Given fixed stacks S, r1 r2 r3 = constant = 1 + 2 S.
Hence maximizing Y’s equity reduces to minimizing (1 + r1)(1 + r2)(1 + r3) subject to r1 r2 r3 constant.
By AM‑GM, this is minimized when r1 = r2 = r3.

**Für den Bot:** For three‑street stack‑off lines (e.g., flop‑turn‑river all‑in trees), choose bet sizes so that the pot multiplies by the same factor each street; avoid under‑ or over‑betting one street relative to others if your goal is to maximize value extraction from an optimally defending villain.

## Two bet‑sizing strategies comparison (flat vs geometric) and ex‑showdown constraint
Example 19.3 compares a naive strategy (bet one‑third stack each street) with the geometric growth strategy in a 3‑street clairvoyant game. Geometric betting yields higher value per winning hand and can flip the game from losing to winning. Also, the max ex‑showdown EV is bounded by the opponent’s showdown EV.

**Formel:** Game: stacks 185, antes 5 each, pot 10, 3 streets, Y wins at showdown if card ∈ {A, K} (prob 2/13).

Showdown EV without betting:

EV_showdown = (2/13) * 10 - (11/13) * 10 = (2 - 11)/13 * 10 = -9/13 * 10 ≈ -3.46

Y must gain +3.46 in ex‑showdown EV via betting to break even.

Flat bet strategy Υ1: bet 60 each street.
Geometric strategy Υ2: choose r so that 10 r^3 = 370 => r ≈ 3.3322, yielding bets s1 ≈ 11.66, s2 ≈ 38.86, s3 ≈ 129.48.

From table:

Value per strong hand:
<Υ1> ≈ $19.16
<Υ2> ≈ $26.41

Constraint: ex‑showdown EV ≤ villain’s showdown equity (here ≈ $5 ante), else villain would optimally fold pre and the game degenerate.

**Für den Bot:** Avoid mechanically splitting stacks into equal dollar bets; instead, approximate geometric bet sizing over remaining streets to maximize value with strong hands and bluffing efficiency, respecting that you cannot extract more ex‑showdown than villain’s underlying showdown equity.

## M‑street geometric pot growth and bluff multiplier rb
In an M‑street geometric pot‑growth clairvoyant game, the bet size on each street and a per‑street bluff multiplier rb fully determine the growth of Y’s bluffing range across streets.

**Formel:** Initial pot: 1
Stacks: S
Final pot if all‑in at river: P = 1 + 2 S

Geometric pot‑growth factor:
G = P^(1/M)
Bet size on each street (normalized pot = 1):

s = (G - 1)/2

On a given street where current pot is normalized to 1, Y has y_v value hands for that street (either nuts, or hands that will bet the next street). He bets:
• y_v value
• (s / (1 + s)) * y_v bluffs
Total betting hands: y_v * (1 + 2 s)/(1 + s)

The ratio of betting hands between successive streets (bluff multiplier) is:

r_b = (1 + 2 s)/(1 + s)


**Für den Bot:** For approximate geometric all‑in lines, you can pre‑compute a per‑street bluff multiplier rb that says: ‘relative to the future value+bluff set, how many hands should I be betting on this street?’; this simplifies multi‑street bluff‑range construction.

## Multi‑street clairvoyant game: geometric betting and hand cascade
In a clairvoyant, static‑value, M‑street no‑limit game with constant bet‑to‑pot ratio s each street, the bettor carries a shrinking set of value hands forward and a larger set of bluffs early, giving up some bluffs each street. Optimal structure is geometric pot growth with fixed s and fixed calling frequency each street.

**Formel:** Let s be the bet size as a fraction of the pot on each street (same s every street).
Let l = 1 be the pot multiple the caller can win (standard normalization).
Then the optimal bluff/value ratio per street is
  r_b = (l + s) / s
Bettor's call frequency each street is
  r_c = l / (l + s) = 1 / (1 + s)
Let y be total number of nut/value hands for Y over the whole game.
Let y_m be the number of value hands Y bets on street m+1, m = 0,...,M-1.
Let y_0 be the number of value hands bet on the first street.
Then
  y_m = y_0 * r_b^m
  y_M = y_0 * r_b^M = y  =>  y_0 = y * r_b^(-M)
Equivalently
  y_m = y * r_b^(m - M)
If X calls optimally each street with fraction r_c, let x_m be the number of hands X continues with on street m+1:
  x_m = r_c^m
Game value (per hand) to Y when X is indifferent is
  V = y_0 - y
which equals the total number of hands Y bluffs initially (each such bluff captures the pot).

**Für den Bot:** On static boards where ranges don’t change much, approximate optimal play by (i) using near‑constant bet‑to‑pot ratios across streets, (ii) shrinking the value range geometrically each street, (iii) maintaining near‑constant calling frequencies by opponent across streets. Use r_b=(1+s)/s to size your bluffing region vs value each street, and treat the earliest street as where you deploy the widest bluff set.

## Auction game limit: mapping continuous bids to multi‑street NLHE
In the symmetric auction toy game with stacks S and pot 1, the equilibrium value of any corresponding multi‑street static game converges to the auction game value as the number of streets M → ∞ when bets are spaced as S/M. Loss from playing the simple "auction strategy" vs the true optimal betting structure is at most ε = S/M per hand.

**Formel:** Auction game: each player chooses a bid s in [0, S]; higher bid wins the pot plus both bids.
Consider an M‑street NL static game where each player: (i) preassigns a total willingness‑to‑invest threshold s_x in [0,S] to each hand, (ii) bets ε = S/M of remaining stack each street until exceeding s_x then stops.
The nemesis can only exploit when the last bet slightly overshoots s_x by at most ε, giving maximal advantage per hand of ε.
Thus for the corresponding poker game with same S and initial pot 1,
  |G_optimal - G_auction| <= ε = S / M
As M → ∞, ε → 0, so
  lim_{M→∞} G_poker(M streets, geometric bets) = G_auction(S).


**Für den Bot:** For deep‑stack static or near‑static spots, a simple geometric, almost "pre‑committed" staking scheme (bet fixed fraction of remaining stack each street up to a per‑hand threshold) is within O(stack/M) of optimal. A NLHE bot can discretize thresholds for each combo and approximate optimal multi‑street betting just by tying bet size schedule to these thresholds, accepting tiny theoretical leakage.

## Auction game equilibrium distributions x(s), y(s)
In the clairvoyant auction game, there are explicit equilibrium cumulative distributions for how often each player bids at least s, linking stack size S and Y’s winning‑hand density y0 to bluffing and calling distributions. These are the continuous counterparts to single‑street calling/bluffing ratios.

**Formel:** Clairvoyant auction game: pot=1, stacks=S.
Y is clairvoyant and has winning hands with total fraction y0 of his overall distribution.
Let x(s) = fraction of X's hands with which he bids at least s.
Let y(s) = fraction of Y's hands with which he bids at least s (counting both winners and bluffs).
Indifference for X between bidding s and s+ds with a losing hand yields differential equation
  -dx / x = ds / (1 + 2s)
Integrate:
  -ln x = (1/2) ln(1 + 2s) + C
  ln(C x^2) = ln(1 + 2s)
  x(s) = k / sqrt(1 + 2s)
Boundary x(0) = 1 => k = 1, so
  x(s) = 1 / sqrt(1 + 2s)
Symmetric logic for Y’s bluff distribution (non‑nut part) gives
  -dy / y = ds / (1 + 2s)  (sign depending on convention)
=>  y(s) = k_y / sqrt(1 + 2s)
Impose that at s = S, Y’s surviving hands equal his total winner mass y0:
  y(S) = y0 = k_y / sqrt(1 + 2S)
=> k_y = y0 * sqrt(1 + 2S)
So equilibrium cumulative bid distributions are
  x(s) = 1 / sqrt(1 + 2s)
  y(s) = y0 * sqrt(1 + 2S) / sqrt(1 + 2s)
with clipping:
  x(s) in [0,1], y(s) in [0,1].
If y(s) computed above exceeds 1 at small s, set y(s)=1 there (Y bluffs with all non‑nut hands up to that s).


**Für den Bot:** The continuous forms x(s)≈1/√(1+2s) and y(s)∝1/√(1+2s) imply that as you move to larger effective bet sizes relative to stack, your continuing/bidding frequencies should decay roughly like 1/√(pot size). A NLHE bot can use this as a heuristic prior for how many combos should be willing to invest to a given stack depth when ranges are static and symmetric.

## Limit of multi‑street clairvoyant game to auction distributions
For the clairvoyant multi‑street game with geometric growth factor G per street, as the number of streets M grows large, the discrete solution (per‑street calling frequencies x_m) converges to the continuous auction x(s) distribution via a mapping between street index m and effective stake s.

**Formel:** Let M be number of streets; let s_1 be the one‑street bet‑to‑pot ratio chosen so that pot grows by factor G each street:
  1 + 2 s_1 = G
Total growth over M streets: pot_M = G^M = P (final pot multiple).
Define effective continuous "stake" s such that
  s_n = (G - 1) / 2  (one‑street ratio from Example 19.4)
Approximate
  s_n ≈ ln G / 2 = (ln P) / (2M)
From the clairvoyant multi‑street solution, caller’s continue fraction after m streets is
  x_m = r_c^m = (1 + s_1)^(-m) ≈ e^{-m s_1}
Relate to pot growth:
  1 + 2 s_1 = G^m => at street m pot ≈ G^m
Using approximations they obtain
  x_m ≈ (1 + 2 s_1)^(-1/2)  (after mapping indices)
Identifying s with current bet level and using the auction result
  x(s) = 1 / sqrt(1 + 2s)
we see that
  x_m → x(s)
So the discrete geometric multi‑street game converges to the auction game as M → ∞, both in value and in distribution shapes.

**Für den Bot:** If you model a many‑street deep‑stack NLHE spot with approximately static ranges, you can move between a discrete street model (per‑street call frequency r_c) and a continuous stack model (x(s)≈1/√(1+2s)). This justifies using continuous risk curves for how many combos reach a given investment level while still being consistent with per‑street MDF‑style decisions.

## Credible bluffs must come from value‑supported distributions
In multi‑street settings, a river bluff is only credible if the path that reached the river also contains enough strong hands that take that line. If a draw is "marked" (everyone sees it and knows the line mostly contains that draw), then even though single‑street ratios might suggest a call frequency, optimal multi‑street play compresses the bluff density because the draw has paid a prior cost on earlier streets.

**Formel:** Principle (qualitative, not a single closed form):
Given a multi‑street sequence where a hand H must pay cost C_pre on earlier streets (bets it calls or makes) to reach a potential bluffing node N with possible reward R at N, H’s EV of "calling with intent to bluff later" is
  EV(H, play) = p(make_draw) * [ (1 - x) * R_win + x * (-R_lose) ] - (1 - p(make_draw)) * C_pre
where x is opponent’s call frequency vs the bluff at N.
To make H indifferent between folding earlier and following this strategy,
  EV(H, play) = 0.
Solving for x yields adjusted calling frequencies that generally differ from the single‑street MDF 1/(1+α) derived ignoring C_pre.

Worked example (Example 20.2):
Pot on turn: 4 big bets; X bets 1, Y calls with some dead hands intending to bluff if flush card arrives.
Flush comes 1/5 of time; river pot becomes 6; Y bets 1 when flush hits.
Let x be X’s calling fraction on river.
Dead‑hand EV if they fold turn = 0.
Dead‑hand EV if they call turn and bluff river when flush card arrives:
  EV_play = p(call_turn)*[ p(flush)*EV_given_flush + p(no_flush)*EV_given_no_flush ]
We condition on them having already called turn, so:
  EV_play = p(flush) * [ x * (-2) + (1 - x) * 5 ] + p(no_flush) * (-1)
Given p(flush)=1/5, p(no_flush)=4/5:
  EV_play = (1/5)*(-2x + 5 - 5x) + (4/5)*(-1)
          = (1/5)*(-7x + 5) - 4/5
          = -7x/5 + 1/5
Set EV_play = 0 for indifference:
  -7x/5 + 1/5 = 0  =>  x = 1/7.
Note this is much smaller than the single‑street MDF 6/7 that would arise if we treated the river in isolation with α=1/6.


**Für den Bot:** Don’t apply MDF 1/(1+α) naively street‑by‑street. When a potential bluff hand had to pay earlier to get to the river node, you can defend less often on the river because the bluff already burned equity earlier. A NLHE bot should compute bluff EVs including their earlier investment, then choose river defense frequencies such that marginal bluff lines are indifferent over the full line, not just the final decision.

## EV of chasing with marked draws vs marked made hands
In the open‑draw clairvoyant limit example, the EV of a dead hand that chooses to call turn intending to bluff when a visible draw completes includes both the cost on misses and the showdown/steal outcomes when it hits, yielding a specific equation for optimal river calling fraction.

**Formel:** Example 20.2 setup:
- Pot on turn: 4 big bets.
- X has exposed AA and bets 1; Y either has a flush draw (with 20% chance to complete) or a dead hand.
- Y sometimes calls turn with dead hands to be able to bluff river if the third heart arrives.
- After Y calls, pot on river when flush arrives: 6 big bets; Y bets 1.

Let x be X’s calling probability on river vs that bet when the 3rd heart hits.
Dead hand's options:
1) Fold turn: EV = 0.
2) Call turn, bluff when flush card comes, give up otherwise:
   With probability p_flush = 1/5: board completes flush, Y bets 1.
      - If X calls (prob x): Y loses 2 total bets (1 on turn, 1 on river): payoff -2.
      - If X folds (prob 1-x): Y wins pot 5 bets (4 pre‑turn + 1 from X on turn): payoff +5.
   With probability 1 - p_flush = 4/5: flush misses, Y has dead hand and folds river: loses 1 bet (the turn call).
So:
  EV_play = (1/5)*[x*(-2) + (1-x)*5] + (4/5)*(-1)
          = (1/5)*(-7x + 5) - 4/5
          = -7x/5 + 1/5.
Indifference EV_play = 0 gives
  -7x/5 + 1/5 = 0  =>  x = 1/7.
Thus AA should call only 1/7 of the time on the river when the obvious flush card hits, far less than the 6/7 one would deduce from single‑street ratios on the river alone.

**Für den Bot:** When the draw is public and had to pay to continue, optimal river defense versus the card that completes it can be extremely tight. A bot should dynamically adjust river call frequencies downward in such "marked draw" spots to reflect the poor economics of bluffing for the drawing player over the whole line rather than maintaining naive single‑street MDF.

## Multi‑street games are not independent chains of one‑street games
In poker, unlike chess/backgammon, the EV of a decision on a given street depends on prior bets and the distributional path that got there. You cannot solve each street as an isolated one‑street game and then chain them; the full‑game equilibrium may require different river strategies compared to the single‑street equilibrium in the same apparent pot/stack state.

**Formel:** General statement rather than a single formula:
Let S be a state that can arise on some street with pot size P and stack left S_eff, and let G_1 be the single‑street game defined by (P, S_eff, range distributions at S) ignoring past actions.
Let G_full be the full multi‑street game that sometimes transitions to S after prior actions with certain frequencies and investments.
In general, the equilibrium strategies at S in G_full differ from those in G_1 because players’ continuation values and bluff EVs must include sunk costs and selection effects from earlier streets.
Formally, if σ_full is a Nash equilibrium of G_full and σ_1 is a Nash equilibrium of G_1, then it is not required (and generically false) that
  σ_full|_S = σ_1,
where σ_full|_S denotes the restriction of σ_full to information sets corresponding to S.
Example 20.2 shows:
- Pure river game (Example 20.1) alone implies call frequency c_river = 6/7.
- But in the two‑street game where that same board and pot size arise after a turn bet and call, full‑game optimality yields river defense c_river = 1/7, due to the turn investment by the bluffing distribution.


**Für den Bot:** Do not design a NLHE bot by solving each street independently based only on current pot/stack and local ranges. Every node’s strategy must be consistent with earlier‑street investments and selection. Use full game trees or at least multi‑street abstractions; when you reuse a single‑street solution, adjust for prior costs and conditional ranges, as in the marked‑draw example where full‑game optimal river defense is 1/7 instead of 6/7.

## River bluff:value ratio in clairvoyance (one-street / 1.5‑street)
Given known river equity and a pot of size P, the player with the concealed hand chooses value-bets plus a balanced set of bluffs so that the opponent is exactly indifferent to calling. This generates the canonical value:bluff ratio and the corresponding call frequency.

**Formel:** On the river with pot size P and 1 bet:
- Optimal bluff:value ratio for bettor's *river range*:
  bluff_count / value_count = 1 / (P + 1)

- Corresponding optimal caller frequency with a bluff‑catcher:
  call_frequency = P / (P + 1)

**Für den Bot:** When betting a polarized range for 1x into pot P on the river, target bluffs ≈ value/(P+1) and expect villain to call ≈ P/(P+1) with their bluff‑catchers.

## Adjusted pot value Pt for a winning concealed hand
In the 1.5‑street clairvoyance game, a winning concealed hand on the river has extra value from being able to bluff some losing hands optimally. This can be folded back into an adjusted pot value Pt to use from the prior street.

**Formel:** Pt = P + P/(P + 1)

Where P is the pot entering the river (before the final 1‑bet street).

**Für den Bot:** When evaluating turn decisions where you will have perfect information on the river and can value‑bet/bluff optimally, treat a certain river win as being worth P + P/(P+1) instead of just P.

## Value of Y’s set from a weak closed draw with implied odds (two‑street draw toy game)
Y calls the turn with a weak closed draw that can either make a small set or a flush; when it makes a set, Y gets implied odds from a river bet that X calls with frequency depending on whether a flush card arrives. The EV of the set conditions the optimal river calling frequencies xf and xn.

**Formel:** Let:
- xf = X’s river call frequency when the flush card comes.
- xn = X’s river call frequency when a non‑flush card comes.
- set hits 1/25, made with a non‑flush card 3/4 of the time, with a flush card 1/4 of the time.
- When Y makes a set and bets, the pot before river is 5 bets (including turn calls); river bet size = 1.

Then Y’s value when he has a set is:
V_set = (3/4) * (5 + xn) + (1/4) * (5 + xf)

**Für den Bot:** When you call turn with a marginal draw, your implied odds depend not just on hit frequency but also on how often opponents will call river bets on different runouts; a solver‑style bot should parameterize these implied odds via call frequencies conditional on each river class.

## Indifference between river bluff lines [C/B/B] and [C/B/K] for weak closed draws
Y splits his weak closed draws between bluffing all rivers and bluffing only on flush rivers. Since some fraction are used for [C/B/B] and some for [C/B/K], the river bluff when the flush misses must be mixed such that Y is indifferent between those two strategies. That yields X’s non‑flush river call frequency xn.

**Formel:** From equating EVs:
⟨[C/B/B]⟩ = ⟨[C/B/K]⟩  ⇒
(77/100)(-2xn + 5(1 - xn)) = -77/100

Simplify the bracket term:
-2xn + 5(1 - xn) = 5 - 7xn
So:
(77/100)(5 - 7xn) = -77/100
5 - 7xn = -1
7xn = 6
xn = 6/7

**Für den Bot:** On boards where only closed draws can exist (no new nut draws possible), an optimal defender must call river at a *high* frequency (here 6/7) to deny EV to bluff‑catching lines that fire all bricks.

## Solving xf (river call frequency vs flush card) from weak‑draw indifference
Y’s turn-weak closed draws must be indifferent between calling and folding given X’s future river strategy. This pins down X’s call frequency xf when the flush card hits, jointly with xn.

**Formel:** Given:
- xn = 6/7 from [C/B/B] vs [C/B/K] indifference.
- One more global indifference relation (from making the weak closed draws just breakeven) yields:
  (1/25) * ( (3/4)(5 + 6/7) + (1/4)(5 + xf) )
  + (19/100)(5 - 7xf) = 61/100
Solving gives:
  xf = 3/7

**Für den Bot:** Facing an open‑ended nut draw (flush completion) plus balanced bluffs, the optimal defence calls significantly *less* often (here 3/7) than on brick rivers, because the bettor has more value combos there.

## Required number of weak closed draws to support flush calls (alpha balance)
Y uses extra semibluff calls on the turn (weak closed draws) to provide enough bluff combos on flush rivers to keep X indifferent at the target call frequency xf. The count of these extra draws y must satisfy the usual alpha (value:bluff) ratio for the flush‑river betting range.

**Formel:** Let:
- y = number (or fraction) of weak closed draws Y calls turn with.
- On the river when flush hits, Y has value from flushes and sets and needs total bluff frequency α = 1/7 (implied by xf = 3/7 and bet size 1 into pot 5 ⇒ P = 5, so α = 1/(P+1) = 1/6 but toy game’s specifics give 1/7 here).
- The probability to have a made hand (flush or set) on flush rivers is:
  p_value_flush = (1/9) * y + 1/10

For equilibrium:
α * p_value_flush = (8/9) * y

Plugging α = 1/7 (from the text):
(1/7) * ( (1/9) y + 1/10 ) = (8/9) y
⇒ (8/9) y = 1/63 + 1/70
⇒ y = 9/550

**Für den Bot:** Turn semibluff frequency with marginal draws must be tuned so that on scary rivers (like flush completions) you have the correct proportion of bluffs to value; adding too many or too few such hands distorts your river bluffing density and makes you exploitable.

## Region/threshold structure of Y’s turn distribution (0,1‑style ordering)
Y’s turn distribution can be partitioned into ordered regions (flush draws, weak closed draws, pure air). For a fixed pot/bet structure, there is a threshold hand at which Y is indifferent between calling and folding / bluffing or not. Depending on counts x,y,z, this threshold lies either in the weak closed draws or in the dead hands.

**Formel:** Distribution parameters:
- x: fraction of strong flush draws.
- y: fraction of weak closed draws.
- z: fraction of dead hands.

Order by intrinsic equity: flush draws > weak closed draws > dead.

There exists a threshold hand h* such that:
EV(call/semibluff with h*) = EV(fold/passive line with h*)

If y is small: threshold lies in dead hands → X makes dead hands indifferent.
If y is large: threshold lies in weak closed draws → X makes weak draws indifferent.

(No closed-form given in the excerpt; it is solved by equating expected values of alternative lines for the marginal hand.)

**Für den Bot:** On the turn, rank your candidate continues (strong draws, weak draws, air) by equity; push the highest‑equity ones into your semibluff region until their marginal EV equals folding, and use only then pure air to fill any remaining bluff quota.

## Definition of the equity functions y(t) and ȳ(t) over an ordered distribution
Given Y’s discrete distribution of possible hands mapped to their showdown winning probabilities, order them from strongest to weakest and define a cumulative equity function ȳ(t) over the top t fraction. This structure parallels the [0,1] game and is used to express optimal betting thresholds in closed form.

**Formel:** Let Y′ be the multiset of (equity, frequency) pairs for Y’s possible hands, with total mass 1.
Order hands so the best equity is first. Define:

- y(t): equity of the best remaining hand after removing the top t fraction of hands (0 ≤ t ≤ 1).
  y(0) = equity of best hand.
  y(1) = equity of worst hand.

- ȳ(t): average equity of the best t fraction of hands:
  ȳ(t) = (1 / t) * ∫_0^t y(s) ds,  for 0 < t ≤ 1
  ȳ(0) = y(0) by continuity.

Properties:
- ȳ(t) is continuous.
- ȳ(t) is decreasing in t, strictly if not all equities equal.
- ȳ(1) is the overall average equity E[y] over Y′.

**Für den Bot:** Internally, the bot should think in terms of a cumulative equity curve over its range: sort hands by equity versus the opponent’s range and represent the top‑t prefix average equity ȳ(t); many optimal thresholds are simple inequalities in terms of ȳ(t).

## Inverse cutoff function τ[y0] (fraction of hands ≥ given equity)
To define optimal betting ranges, it is convenient to invert y(t): for a target minimum equity y0, ask what fraction of hands have equity at least y0. That inverse, τ[y0], characterizes the size of the value‑bet or semibluff region.

**Formel:** Given ordered equity function y(t):
- τ[y0] = sup{ t ∈ [0,1] : y(t) ≥ y0 }

Interpretation: τ[y0] is the fraction of hands with equity ≥ y0.

Example from text (with 39 hands total):
- Hands with equity ≥ 1/2 (i.e., 100% and 41/44 winners) are 18/39 of the distribution.
  ⇒ τ[1/2] = 18/39.

**Für den Bot:** To build betting ranges, choose an equity cutoff y0 (like the EV‑breakeven point) and include exactly the top τ[y0] fraction of hands by equity; this matches continuous‑model optimal thresholds.

## Case 1 in 1.5‑street clairvoyance: Y always bets, X always folds
On the turn, when Y’s overall equity distribution is strong enough, betting any hand is immediately profitable because X never has pot odds to call given Y’s future clairvoyant river play. This yields a global condition on the average equity ȳ(1).

**Formel:** Setup:
- Turn pot size: P.
- If Y bets and is called, pot on river: P + 2.
- The value of a winning hand on the river with clairvoyant play: (P + 2) * t,
  where t encodes the adjusted river value (here t is effectively Pt/(P+2), but in the text they keep t as the generic multiplier).
- Cost of betting the turn: 1 bet.

Y’s EV from betting all hands when X always calls:
EV_bet_all = ȳ(1) * (P + 2) * t - 1

Y’s EV from checking all hands and then playing river optimally:
EV_check_all = P * (status quo)  (since no immediate money goes in on the turn and t is accounted on river)

Condition for X to be forced to fold (Y can always bet profitably):
EV_bet_all ≥ P  ⇒  ȳ(1)(P + 2)t - 1 ≥ P
⇒ ȳ(1) ≥ (P + 1) / ((P + 2)t)

(They also express t explicitly via Pt: t = (P + P/(P+1)) / (P+2) ⇒ the alternative form with (P+3)/( (P+2)(P+4) ), but core inequality is above.)

**Für den Bot:** When your entire range is very strong versus villain’s exposed hand, you can range‑bet a street and villain must essentially fold range; in practice, your solver can detect this by comparing your range’s average equity ȳ(1) to a pot‑size‑dependent threshold.

## Betting threshold when X always calls in 1.5‑street clairvoyance
At the other end of the spectrum, if X were to call all turn bets, then Y should bet only hands whose individual equity y exceeds a certain threshold, derived by comparing the EV of betting versus checking with clairvoyant river play.

**Formel:** If X always calls, then for a given hand with equity y:
- EV_check(y) = y * (P_t) = y * Pt
- EV_bet(y)   = y * (P + 2)t - 1

Y should bet when EV_bet(y) ≥ EV_check(y):
  y(P + 2)t - 1 ≥ y(Pt)
  y ≥ 1 / ((P + 2)t - Pt)

Let y0 = 1 / ((P + 2)t - Pt).
Then Y’s optimal betting set is all hands with equity y ≥ y0, i.e. the top τ[y0] fraction by equity.

**Für den Bot:** Given that the caller defends 100% versus turn bets, you should only bet those hands whose equity exceeds a computable threshold; in NLHE, solvers implicitly do this by comparing each hand’s EV of bet vs check.

## General rule about folding once villain can force you to surrender whole pot
If at some stage villain has a strategy that makes you fold 100% of the time (you can never call profitably vs any action of a certain size), then at any *later* point in the hand, folding to all bets is at least co‑optimal. Otherwise villain can sometimes play suboptimally early to extract extra value later.

**Formel:** If there exists an action a at stage s such that, given ranges R_X,R_Y and bet size B into pot P_s,
EV_X(call | a, P_s, B) < EV_X(fold | a, P_s, B) = -contribution (i.e., must-fold region is 100%),
then for any later stage s' > s and any further action a', a fold is at least co-optimal for X:

∀ a',  EV_X(fold | a', s') ≥ EV_X(mixed response | a', s')

(Argument: any profitable future call would enable an exploit where Y declines to take immediate pot and instead delays with some strong hands.)

**Für den Bot:** In algorithms that consider subgame solving: if your range is already so crushed that you must always fold vs some earlier bet size, there is no incentive to defend later vs smaller or delayed bets; this informs pruning and simplifies subgame strategies.

## Turn clairvoyant game – equity threshold for betting vs checking (Case 3)
In a two‑street clairvoyant game where Y can bet the turn with any subset of hands and X can only call or fold (no raises), Y’s optimal betting region in the interesting case is defined by an equity cutoff y* such that X is indifferent to calling or folding versus that betting range. The average equity of Y’s betting range, yθ(T), must satisfy an indifference equation that pins down the threshold index T in the sorted equity distribution.

**Formel:** Let:
- P = pot size in units of the current bet before the turn bet
- t = ratio of river bet size to turn bet size (in the excerpt, both streets same size so t is used as implied‑odds factor, often t=1 in simple variants)
- y(h) = showdown equity of Y’s specific hand h versus X’s fixed hand
- yθ(T) = average equity of the top fraction T of Y’s distribution (hands sorted from strongest to weakest by y)

Indifference of X to calling vs folding on the turn, when Y bets with hands in the top fraction T (Case 3), gives:

  yθ(T) * (P + 2) * t - 1 = P
  => yθ(T) = (P + 1) / [(P + 2) * t]

Case classification using yθ(T):
- Case 1 (Y bets all hands; X folds always):
    yθ(1) >= (P + 1) / [(P + 2) * t]
- Case 2 (Y only bets hands with positive betting EV; X calls always):
    Let t0 be defined below; if
    yθ(t0) <= (P + 1) / [(P + 2) * t]
    then X can profitably call 100% vs Y’s positive‑EV betting region.
- Case 3 (mixed; Y bets strongest fraction T; X mixes call/fold):
    yθ(T) = (P + 1) / [(P + 2) * t] with 0 < T < 1.

Here t0 is defined by the worst hand in Y’s betting region having zero EV for betting on the turn (see separate item).

**Für den Bot:** On future‑street betting nodes (e.g., turn with river behind), a GTO‑ish turn betting range should be chosen so that X is roughly indifferent with his marginal bluff‑catchers; equivalently, the average equity of your turn betting range, vs his continuing range plus implied river action, should be near (P+1)/((P+2)*t). This is a multi‑street generalization of choosing bet ranges so villain is marginally indifferent with his bluff‑catchers.

## Condition for Y to bet a specific hand on the turn given X’s fold frequency α
Given that X folds α of the time and calls 1−α versus a turn bet, Y should bet exactly those hands whose EV from betting exceeds the EV from checking. This yields an equity cutoff function y_min(α) such that Y bets all hands with equity y ≥ y_min(α).

**Formel:** Let:
- α = X’s folding frequency on the turn (fraction of time he folds vs a bet)
- P, t as above
- y = equity of a specific Y hand vs X

EV if Y bets with hand y:
  EV_bet(y) = α * P + (1 − α) * (y * (P + 2) * t − 1)

EV if Y checks with hand y:
  EV_check(y) = y * P * t

Betting is optimal when EV_bet(y) >= EV_check(y):
  αP + (1 − α)(y (P + 2) t − 1) >= y P t
Rearrange to obtain the minimum equity threshold y_min(α):
  y * [ (1 − α)(P + 2) t − P t ] >= 1 − α (P + 1)
  => y >= [1 − α (P + 1)] / [ (1 − α)(P + 2) t − P t ]

Call this cutoff:
  y_min(α) = (1 − α (P + 1)) / [ (1 − α)(P + 2) t − P t ]

Sign restrictions:
- Left denominator positive if α P < 2, i.e. α < 2/P.
- Right numerator positive if α > 1/(P+1). For α <= 1/(P+1), RHS can be <= 0 and then Y just bets all hands (or all hands with non‑negative betting EV).

**Für den Bot:** Against a given fold frequency α on an earlier street, your betting range should be an equity‑based threshold: bet all hands whose equity vs villain’s range exceeds y_min(α). In practice, the solver‑style rule is: for each node, define villain’s folding frequency and then ensure your bluffs come from the lower‑equity portion above the cutoff where betting EV ≥ checking EV.

## Positive‑EV threshold t0 for Y’s betting hands (zero‑EV worst bet)
t0 is the fraction of Y’s distribution that can be bet (starting from the top) such that the worst hand in that betting set has zero EV for betting vs checking, assuming X calls always. It’s used to decide whether the equilibrium falls into Case 2 (Y only bets positive‑EV hands and X calls 100%).

**Formel:** t0 is defined via the worst hand in the betting region having zero EV when X calls always (α = 0). Let y(t0) be the equity of the marginal (worst) betting hand at fraction t0.

Zero‑EV condition for that marginal hand:
  EV_bet = y(t0) * (P + 2) t − 1 = EV_check = y(t0) * P t
=> y(t0) * ( (P + 2) t − P t ) = 1
=> y(t0) = 1 / [ (P + 2) t − P t ]

Then t0 is defined as:
  t0 = T( y >= y(t0) ) = measure of hands with y >= 1 / [ (P + 2) t − P t ]

In the text they denote this as:
  t0 = T[ 1 / ( (P + 2) t − P t ) ]
meaning “the fraction t such that y(t) is greater than that value”.

Case‑2 condition:
  If yθ(t0) <= (P + 1) / [ (P + 2) t ], then we are in Case 2 (X calls always; Y only bets those t <= t0 hands).

**Für den Bot:** When building a betting range on an early street, one natural baseline is: start with the strongest hands and expand the betting set until the marginal hand’s bet vs check EV breaks even assuming villain always continues. If even this truncated betting range has average equity yθ(t0) small enough, equilibrium can be close to “bet only clear‑value, no bluffs, villain calls everything.”

## X’s optimal fold frequency α* in the mixed Case 3 (turn with river behind)
In Case 3, Y chooses a betting threshold T so that the *average* equity of his betting range is yθ(T) = (P+1)/((P+2)t). For that threshold, the worst betting hand y(T) is also made indifferent between betting and checking when X mixes between call and fold with frequency α*. Solving this indifference gives α* as a function of y(T).

**Formel:** Given:
- y(T) = equity of Y’s *worst* betting hand at threshold T (denoted y(τ) in excerpt)
- As before P, t

We already have Y’s bet vs check cutoff as function of α:
  y >= (1 − α (P + 1)) / [ (1 − α) (P + 2) t − P t ]

At equilibrium in Case 3, the marginal betting hand y(T) is exactly indifferent (makes the inequality an equality). So plug y(T) in and solve for α:

  y(T) = (1 − α (P + 1)) / [ (1 − α) (P + 2) t − P t ]

Solving for α (algebra from text):
  α = [1 − y(T) * ((P + 2) t − P t)] / [ P + 1 − y(T) * (P + 2) t ]

This is the unique α in Case 3 making Y’s marginal betting hand indifferent and thereby fixing X’s optimal fold frequency.

**Für den Bot:** On a turn node with river behind, once you’ve chosen a betting threshold in terms of hand equity (the weakest hand you bet), the *population‑optimal* fold frequency of your opponent is pinned by that marginal hand’s indifference. In NLHE implementation: if you deliberately define a weakest value/semi‑bluff that bets, your fold‑to‑bet frequency should be such that this hand is barely happy to bet; conversely, villain’s GTO fold frequency α* can be backed out from that marginal‑value equity.

## Deviation from single‑street α = P/(P+1) because of implied odds (multi‑street MDF)
On a single street with pot P and bet 1, the standard minimally‑defensible fold frequency against bluffs is α_single = 1/(P+1), so call frequency is 1−α_single = P/(P+1). In this two‑street game with implied odds represented by t, that single‑street relationship no longer applies: X may optimally fold *more* often because folding earlier saves future river losses.

**Formel:** Single‑street benchmark (no future streets, standard toy game):
- If facing a pot‑size‑relative bet of size 1 into pot P on a *final* street, MDF call frequency is:
    call_freq_single = P / (P + 1)
    fold_freq_single = 1 / (P + 1)

In the two‑street clairvoyant game, with implied odds captured by t and Y’s ability to value‑bet river when hitting, X’s optimal folding frequency α* on the turn satisfies the more complex relation:

  α* = [1 − y(T) * ((P + 2) t − P t)] / [ P + 1 − y(T) * (P + 2) t ]

In the concrete example from the text with P = 5, t = 1, and y(T) = 6/44 ≈ 0.13636, we get:

  α* ≈ 0.1965

Compare:
- Single‑street fold MDF with P=5: 1/(P+1) = 1/6 ≈ 0.1667
- Two‑street optimal fold α*: ≈ 0.1965

So X folds more on the turn than single‑street MDF would suggest because calling also exposes him to losing additional river bets when behind.

**Für den Bot:** Minimum‑defense‑frequency calculations like call = P/(P+1) are *not* valid on earlier streets with significant future betting. In NLHE, on turn/ flop against balanced ranges with big implied odds, optimal defense frequencies are typically *lower* than single‑street MDF: folding more often can be correct because calling not only loses the current bet but also sets you up to pay off later streets.

## Indifference principle in mixed strategies (multi‑street extension)
In any mixed‑strategy equilibrium, all actions that are played with positive probability for a given information set / hand (or distribution slice) must have equal EV. The excerpt applies this twice: (1) X’s mixed call/fold strategy on the turn makes Y’s *average* betting hand indifferent to X calling vs folding, giving yθ(T) = (P+1)/((P+2)t); (2) X’s folding frequency α makes Y’s *marginal* betting hand y(T) indifferent between betting and checking, giving the α formula.

**Formel:** General indifference conditions used in this game:

1) X is indifferent between calling and folding versus Y’s *betting range* (average equity yθ(T)):
   EV_call_vs_range = EV_fold_vs_range
   => yθ(T) * (P + 2) t − 1 = P
   => yθ(T) = (P + 1)/((P + 2) t)

2) Y’s marginal betting hand y(T) is indifferent between betting and checking vs X’s mixed response (fold with α, call with 1−α):
   EV_bet(y(T)) = EV_check(y(T))
   => α P + (1 − α) ( y(T) (P + 2) t − 1 ) = y(T) P t
   => solve for α to obtain:
      α = [1 − y(T) ((P + 2) t − P t)] / [ P + 1 − y(T) (P + 2) t ]

These are both direct applications of the general game‑theoretic rule: for an opponent to mix among responses, your strategy must leave them indifferent between their pure responses that are used with positive probability.

**Für den Bot:** Solver equilibria are built by enforcing indifference: (i) choose your betting range so villain’s marginal call is indifferent between calling and folding; (ii) choose your frequencies (e.g., bluff fraction) so your marginal bluff/value hand is indifferent between betting and checking. When coding a bot, these equal‑EV constraints define equations that pin down optimal frequencies and thresholds.

## Distribution strength ordering via yθ(1), yθ(0), and case selection
The function yθ(T) (average equity of the top T fraction of Y’s hands vs X’s fixed hand) is decreasing in T. Comparing yθ(1) and yθ(t0) to the critical value (P+1)/((P+2)t) partitions the game into three strategic regimes: always‑bet, value‑only‑bet, and mixed.

**Formel:** Definitions:
- yθ(T) = average equity over best T fraction of Y’s hands
- yθ(1) = average equity of Y’s whole distribution
- yθ(0) = limit as T→0+ (essentially equity of Y’s absolute nuts)
- critical level: c = (P + 1)/((P + 2) t)
- t0: fraction such that worst hand in top t0 has y(t0) = 1 / ( (P + 2) t − P t )

Three cases:
1) Case 1 (Y bets all hands; X folds always):
   yθ(1) >= c

2) Case 2 (Y only value‑bets; X calls always):
   yθ(t0) <= c

3) Case 3 (mixed; Y bets strongest T in (0,1); X mixes call/fold):
   yθ(T) = c for some 0 < T < 1, and neither Case 1 nor Case 2 hold.

Monotonicity:
- yθ(T) is decreasing in T, so:
   yθ(1) <= yθ(T) <= yθ(0).

This structure ensures exactly one of the three possibilities holds for a given distribution and (P,t).

**Für den Bot:** The overall *shape* and strength of villain’s range (captured by average equity functions like yθ(T)) dictates whether equilibrium is: (i) always bet (you’re very strong), (ii) only value‑bet (you’re weak/close and villain calls everything), or (iii) mixed with bluffs. In NLHE bots, you should treat nodes differently depending on whether your range is distributionally very strong or weak: some nodes are near pure value‑bet / pure check, others require non‑trivial bluffing and mixing.

## Equity concentration vs homogeneous draws in multi‑street games
Two Y distributions with the same *average* showdown equity can have very different strategic power across multiple streets. Concentrating equity into a minority of nut hands (and many trash hands) is stronger than spreading it evenly across many medium‑equity draws because nuts can exploit betting leverage over multiple streets, while homogeneous medium‑equity draws often must wait until resolution to realize equity.

**Formel:** Example comparison:

Distribution A (concentrated):
- 25% hands have y = 1 (nuts)
- 75% hands have y = 0 (dead)
=> yθ(1) = 0.25

Distribution B (homogeneous):
- 100% hands have y = 0.25
=> yθ(1) = 0.25

Showdown equity identical (0.25). However, in a two‑street game with betting:
- Distribution A: top T <= 0.25 have y=1, so yθ(T) = 1 for T<=0.25.
- Distribution B: yθ(T) = 0.25 for all T.

Thus for A, there exists a T such that yθ(T) is very high, making strong value bets and bluffs much more powerful across streets; for B, any betting threshold shares the same moderate equity and cannot leverage future streets as effectively.

**Für den Bot:** In NLHE, ranges with some very strong hands (nuts/top‑set/overpairs) plus many weak hands are strategically superior to flat ranges full of middling draws with the same average equity. Your bot should preserve some very strong hands in its betting/checking ranges across streets to maintain credible threats and maximize leverage, rather than turning them into thin protection or merging them prematurely.

## Closed draws vs open draws and forced defense
In clairvoyant analysis, when a draw is ‘closed’ (there is no further betting opportunity before showdown once the draw card comes), the non‑clairvoyant opponent must defend more (fold only α of his hands) because he cannot cheaply realize his own equity by folding early and avoiding future bets. With open draws (more betting rounds after the draw comes), the non‑clairvoyant player can optimally fold far more often on earlier streets, even above 50%, because calling exposes them to additional future losses when behind.

**Formel:** Qualitative comparison from text:
- Closed‑draw case: opponent must fold just α of his hands (α relatively small, closer to single‑street MDF like 1/(P+1)).
- Open‑draw games (like the one solved here): the non‑clairvoyant player can fold more than half of his hands even in presence of some closed draws.

This is not a single closed form, but rather a structural observation: going from closed to open draws relaxes the lower bound on folding frequency imposed by standard single‑street MDF.

**Für den Bot:** On boards where future betting is likely (open draws, more streets left), your bot can and should defend less on early streets than single‑street MDF suggests, especially out of position. On rivers or effectively closed situations, defense frequencies need to be tighter (closer to standard MDF).

## Threshold structure: one critical equity/hand index governs the whole strategy
In many of these toy games, optimal strategies are characterized by a single threshold T in the ordered distribution: above T you take one action (bet, call, raise) and below T you take another (check, fold). T is chosen so that indifference conditions hold for the marginal hand at that threshold, and the rest of the strategy flows from it. X’s folding frequency α and Y’s betting set are both pinned by this single threshold.

**Formel:** In Case 3 of the clairvoyant game:
- There exists a threshold index T (0 < T < 1) such that:
   1) Y bets exactly the top T fraction of his hands.
   2) yθ(T) = (P + 1)/((P + 2) t).
   3) y(T) (equity of marginal betting hand) satisfies the α formula:
        α = [1 − y(T) ((P + 2) t − P t)] / [ P + 1 − y(T) (P + 2) t ].

Thus T (or equivalently y(T)) determines both players’ mixing frequencies at equilibrium.

**Für den Bot:** In NLHE implementation, for each decision node and action class (e.g. betting vs checking), the equilibrium strategy can often be parameterized by one equity threshold over your range: above it you bet, below it you check. Your bot can approximate GTO by computing such thresholds (via EV comparisons / solver) rather than micro‑tuning each combo independently.

## Indifference principle for preflop raise sizing vs blinds
Choose a single raise size (per position) so that the big blind’s marginal hands are approximately indifferent between calling and folding versus your *whole opening distribution*. This makes your distribution hard to exploit and maximizes total EV of the distribution.

**Formel:** Let R be your raise size, B the big blind, P0 the pot before raising.
Let villain call with range C and fold other hands; let equity(h | call_range) be your hand’s equity when called.
The indifference condition targets a borderline blind hand h* where:
EV(call with h*) ≈ EV(fold) = 0.
Given you raise to R and villain calls (adding R - B):
Pot when called: P_call = P0 + 2R - B
Cost to call: C_cost = R - B
Indifference for blind’s marginal hand h*:
 equity_v(h*) * P_call - C_cost ≈ 0
=> equity_v(h*) ≈ C_cost / P_call = (R - B) / (P0 + 2R - B)

**Für den Bot:** For each position, pick a *single* open size R such that typical blind hands at the edge of their defend range need roughly the equity they actually have; this keeps their decisions tough and your distribution unexploitable, rather than optimizing AA in isolation.

## Distribution construction by marginal EV > 0
Your open range in a given position should be the set of hands whose expected value, *given your entire opening distribution*, is positive versus near-optimal opponents; adding weaker (but still +EV) hands usually increases the EV of the existing strong hands because it weakens your perceived range and gets more action.

**Formel:** Let D be current opening distribution. For candidate hand h not in D, define:
EV_open(h | D ∪ {h}) = EV of raising h given that opponents respond optimally vs D ∪ {h}.
Add h to D if:
EV_open(h | D ∪ {h}) > 0.
Total distribution EV:
EV_total(D) = sum_{h in D} [ freq(h) * EV_open(h | D) ], subject to sum_h freq(h) = 1.
Goal: choose D maximizing EV_total(D) with constraint EV_open(h | D) ≥ 0 for all h ∈ D.

**Für den Bot:** Don’t decide preflop open/fold in isolation; evaluate marginal EV of adding each hand to the *whole* opening range, and include hands (especially nutted-board threats like suited connectors/AXs) that remain +EV when opponents optimally adjust.

## Nut-threat (board coverage) as a distribution-wide equity booster
Including hands that can make the nuts (suited connectors, AXs, small pairs) on common flop textures increases the EV of *all* hands in the raising distribution by improving your perceived nut density and future leverage, even if their raw showdown equity vs random is lower than high-card hands like AJs.

**Formel:** Let D be distribution without some nutty candidate hand type t (e.g., 98s).
Let D' = D ∪ {t}.
Define for each existing hand h ∈ D:
ΔEV(h) = EV(h | D') - EV(h | D).
Nut-threat principle: Summed gain from nut-threat hands exceeds their own raw equity discount, i.e.
∑_{h ∈ D} ΔEV(h) + [EV(t | D') - 0] > 0.
Where EV(t | D') includes higher implied odds from times t flops effective nuts and allows profitable aggression.

**Für den Bot:** Weight preflop range-building not just by static equity but by how much a combo improves your nut coverage on flops. Prefer suited connectors/AXs over marginal offsuit hands when expanding ranges, especially deep-stacked.

## No loss-leader (pure deception) plays in optimal ranges
Playing hands that are intrinsically −EV (e.g., 52o UTG) just to ‘balance’ or deceive is not part of optimal play; mixed strategies and fractional inclusion should only use hands whose inclusion does not decrease overall distribution EV.

**Formel:** For a candidate hand h considered only for ‘deception’, with EV_open(h | D ∪ {h}) < 0,
Adding h lowers total distribution EV:
EV_total(D ∪ {h}) = EV_total(D) + freq(h) * EV_open(h | D ∪ {h}) < EV_total(D).
Thus in equilibrium, for every included hand h:
EV_open(h | D) ≥ 0 (with equality for threshold hands possibly mixed in at fractional frequencies).

**Für den Bot:** Never force in preflop combos that are individually −EV just to ‘look balanced’. If a hand only serves deception but doesn’t at least break even given opponent adjustments, its preflop frequency should be zero.

## Raise-size scaling with position and pot (ratio preservation with antes)
Raise sizes should increase as your opening distribution weakens (later position) to maintain similar pressure on the blinds. With antes, raise size should be adjusted to keep the blind’s pot-odds ratio roughly constant.

**Formel:** Given target blind price ratio: blind calls (R - B) to win (P0 + R), where P0 is dead money before raise.
Without antes (example): blinds 200–400, button raises to R = 1200, P0 = 600
=> blind calls 800 to win 1800, odds = 1800/800 = 2.25.
With antes A for n players: new P0' = 600 + n*A. Want same odds:
(P0' + R') / (R' - 400) ≈ 2.25.
Solve for R':
(P0' + R') = 2.25(R' - 400)
⇒ P0' + R' = 2.25R' - 900
⇒ (2.25 - 1)R' = P0' + 900
⇒ 1.25R' = P0' + 900
⇒ R' = (P0' + 900) / 1.25.
In text example: A = 25, n = 8, so P0' = 600 + 200 = 800.
Solve (x + 800)/(x - 400) ≈ 1800/800 → x ≈ 1350.

**Für den Bot:** Implement position-based static open sizes and, when antes change pot size, solve for the new raise so the blind faces roughly the same price (call:pot ratio) as in non-ante configurations.

## Jamming vs small raise: stack-threshold via weakest hand equity
For short stacks, decide between open-shoving and small-raising by ensuring that, if you small-raise and get shoved on, even your *weakest* hand in the open range has non-negative EV to call; below that stack, jamming removes villain’s profitable options and is preferred.

**Formel:** Setup (example):
- Blinds: 1 (BB), SB=0.5, so initial pot P0 = 1.5.
- You open to R = 2 from stack S.
- Villain shoves all-in to S; you must decide call/fold with bottom of range.
Pot after shove before your call: P = P0 + R + (S - 1) = 1.5 + 2 + (S - 1) = S + 2.5.
You call additional (S - 2). Final pot:
P_final = P + (S - 2) = (S + 2.5) + (S - 2) = 2S + 0.5.
Let e_w be equity of your *worst* hand vs villain’s shove range.
Call EV (relative to folding) for worst hand:
EV_call = e_w * P_final - (S - 2).
Require EV_call ≥ 0 (indifferent threshold):
 e_w * (2S + 0.5) ≥ S - 2
⇒ S ≤ (2 - 0.5 e_w) / (1 - 2 e_w).
Text example uses a slightly different simplified pot accounting leading to:
(0.3188)(2x + 1.5) > x - 2
⇒ x > 6.83.
General form from their accounting:
Let x = stack in BB, e_w = equity of worst hand.
Pot when all-in: P_final = 2x + c, call cost = x - 2 →
 e_w (2x + c) ≥ x - 2.

**Für den Bot:** For each position and candidate open range, compute the worst-hand equity versus a plausible reshove range; if for given stack size a small open would force you to call off −EV with that worst hand, convert your strategy to open-shove instead.

## Indifference of weakest jamming hand at jam/fold cutoff
At the jam-or-fold threshold, your weakest open-jam hand is indifferent between folding and jamming (EV ≈ 0). Similarly, at the jam vs small-raise threshold, your opponent should be willing to commit with the same range against a jam as against a small raise, else you could exploit with hybrid strategies.

**Formel:** Let h_min be weakest hand in shove range J at stack S.
Define villain’s calling/reshoving range N as all hands for which call EV vs your jam is ≥ 0.
Jam EV for h_min:
EV_jam(h_min) = fold_prob * P0 + call_prob * [e_min * (P0 + 2S) - (S - B)],
where e_min is equity of h_min vs N, B is your blind contribution already posted, and P0 is pot before jam.
Jam-or-fold threshold: EV_jam(h_min) ≈ 0.
Indifference for opponent: if you are indifferent between jamming and small-raising at S, then for villain’s committing range N:
N is same vs both strategies → any hand with e_v ≥ required equity threshold versus your shove also commits versus your small raise.
Required equity for villain to call your jam:
Let villain risk S_eff to win (P0 + S_eff + your dead money). If he risks C_v to win W_v:
 e_v ≥ C_v / W_v.

**Für den Bot:** When solving push/fold charts, enforce that at the boundary stack: (1) the bottom shove hand has EV ≈ 0, and (2) villain’s all-in-commit range versus a jam matches their all-in-commit range versus a smaller open; otherwise you leave an exploitable split between jam and raise ranges.

## Direct pot-odds test for calling reshove with worst hand
Given an open size and stack, check whether calling a shove with the bottom of your open range is +EV by directly plugging in its equity and the resulting pot size.

**Formel:** Generic call decision after raising to R from stack S (all in BB units):
Let initial pot P0, villain shoves to S, you have already put R in.
Additional you must call: C = S - R.
Total final pot if you call: P_final = P0 + S + S - B = P0 + 2S - B (B accounts for villains’ and your blinds already in; book’s specific examples hard-code constants like 13.5, 17.5, 21.5).
Let e_w be equity of worst hand vs villain shove range.
Call is +EV if:
 e_w * P_final - C ≥ 0.
Example from text:
For stack 6 and worst hand 77 vs {99+, AK} with e_w = 0.2991 and numbers giving P_final = 13.5 and C = 4:
0.2991 * 13.5 - 4 > 0 → call.
For stack 8 vs {TT+, AK} with e_w = 0.3141, P_final = 17.5, C = 6:
0.3141 * 17.5 - 6 < 0 → fold.

**Für den Bot:** In the push/fold region, for each candidate open range and stack, explicitly test the EV of calling a shove with the worst range member using pot-odds; if negative, either tighten the open range or prefer open-shove at that stack.

## Approximate jam-all-in thresholds by position
Using the above EV and indifference calculations, the authors arrive at practical preflop guidelines: jam first-in with all playable hands when effective stacks are ≈6× the pre-raise pot from early positions and ≈7× from near the button, instead of using smaller open sizes.

**Formel:** Let P_pre be pot before your action (includes blinds + antes).
Define jam thresholds (heuristic):
- From early/front positions: if S ≤ 6 * P_pre → play jam-or-fold: jam with opening range instead of small raise.
- From near button: if S ≤ 7 * P_pre → jam instead of small raise.
Formally, S* (front) ≈ 6 P_pre, S* (button) ≈ 7 P_pre, obtained by solving EV_jam(h_min) ≈ EV_smallraise(h_min) and call-reshove EV constraints for representative ranges.

**Für den Bot:** Encode simple jam thresholds: for a given effective stack and pot, if stack ≤ ~6×pot in early or ~7×pot on button, switch strategy to pure jam-or-fold with your first-in range; otherwise use non-all-in opens and plan for postflop.

## Positional tightening/loosening as random-hands-behind model
Opening tight from early position is required because many players behind can wake up with strong hands; as you approach the button, fewer random hands remain, so you can safely include more marginal but +EV hands in your opening distribution.

**Formel:** Let n be number of players behind.
Let p_strong be probability a given random hand is in ‘punish’ set S_strong.
Probability no one behind has S_strong:
P_no_strong = (1 - p_strong)^n.
Your open EV for a given hand h roughly:
EV_open(h) ≈ P_no_strong * EV_vs_blinds(h) + (1 - P_no_strong) * EV_vs_strong_field(h),
where EV_vs_strong_field(h) decreases for marginal hands.
As n decreases (later position), P_no_strong increases, making more h have EV_open(h) > 0, so you can open wider.

**Für den Bot:** Model opening ranges as a function of number of players left to act; widen as n decreases because the chance of facing a strong hand collapses roughly like (1 − p_strong)^n.

## Strategic-option value and why mid-size opens are bad at very short stacks
Strategic options (ability to choose between actions later) have non-negative value; if you small-raise with a 3 BB stack and allow the blind to either shove pre or flat and force you in postflop with 1 BB left, you give villain a free option. Jamming removes this option and is thus strictly better.

**Formel:** Let Strategy A = small-raise to R < S with stack S very small; Strategy B = open-jam S.
Villain’s payoff under A:
EV_v(A) = max over responses r ∈ {fold, call, shove} of EV_v(r | A) ≥ EV_v(r* | B), where r* is the unique response under jam.
Since option sets satisfy: option_set(A) ⊇ option_set(B),
Value(option_set(A)) ≥ Value(option_set(B)),
and villain’s extra options can’t harm him. Thus our EV under A ≤ our EV under B, holding ranges fixed.
Hence for tiny S, open-jam dominates small-raise.

**Für den Bot:** At very short stacks, avoid non-all-in opens that leave you ‘stuck’ on later streets; they grant villain an extra option at zero cost. For S around a few BB, your preflop strategy should be pure shove/fold, not raise/call/fold.

## Autobet condition and automatic check from weaker range
When the preflop raiser’s flop range is sufficiently stronger than the caller’s, a flop bet with range 100% (autobet) is at least co‑optimal. Given an autobet, the out-of-position player should check entire range; any leading strategy is weakly dominated or gives no improvement.

**Formel:** Let R be raiser’s range, B blind’s range, and EV_R(bet | x) ≥ EV_R(check | x) ∀ x ∈ R with strict inequality for some positive-measure subset. If raiser can bet size s with frequency 1 and blind responds optimally, then:

For blind strategies σ_B:
max_{σ_B} EV_B(check, σ_B) ≥ max_{σ_B} EV_B(lead, σ_B)

⇒ check with entire range is (weakly) optimal given raiser’s autobet.

**Für den Bot:** In spots where preflop raiser’s range is much stronger (e.g., EP vs BB single-raised, static high-card boards), simplify strategy: OOP checks full range, IP can use very high c-bet frequency (often close to 100%) with one bet size, then balance later streets. Your solver/bot can treat many such flops as forced-check-node for OOP and near-autobet for IP, reducing strategy space.

## Action regions and threshold indifference
Each player partitions his range into action regions (fold/call/raise/jam) with threshold hands at the boundaries. Optimality requires that at each threshold hand, the player is indifferent between the neighboring actions, given opponent’s mixed strategy. Opponent’s range composition must make those thresholds indifferent so they cannot be profitably shifted.

**Formel:** Let Y’s action set be {F, C, R}. Let h* be a threshold between call and fold. Optimality requires:

EV_Y(C | h*, σ_X) = EV_Y(F | h*, σ_X)

Similarly for threshold between call and raise:
EV_Y(R | h*, σ_X) = EV_Y(C | h*, σ_X)

EVs are expectations over X’s mixed strategy σ_X and future cards.

Opponent X’s region frequencies f_X^i must satisfy linear indifference conditions at all thresholds.

**Für den Bot:** When designing strategies (especially for check-raise vs bet/call/jam branches), tune bluff/value mixes so that hands at your own boundary (e.g., worst call, worst raise) are indifferent across actions. Conversely, ensure your range composition makes opponent’s marginal hands indifferent so they can’t gain by expanding/contracting any response region.

## Draw vs made-hand response to opponent’s fold/call/raise frequencies
Different hand classes react differently to opponent’s adjustments: strong made hands gain when opponent calls wider or raises more; weak draws gain when folds increase and raises decrease; strong draws can profitably jam vs raises. Balance requires mixing strong value, very strong draws, and very weak draws in aggressive lines (e.g., check-raise) while keeping medium-strength and medium draws in more passive lines.

**Formel:** Let actions of opponent vs your flop raise be {fold with prob f, call with prob c, 3-bet with prob r} (f+c+r=1). For your hand class H, EV_H(raise) = f * W_fold(H) + c * W_call(H) + r * W_3bet(H), where W_* are class-dependent payoffs.

Sign of ∂EV_H/∂f, ∂EV_H/∂c, ∂EV_H/∂r differs by H:

- For weak draws: ∂EV/∂f > 0, ∂EV/∂r < 0.
- For strong made hands: ∂EV/∂c > 0, ∂EV/∂r ≥ 0 (if willing to stack off).
- For very strong draws: ∂EV/∂r can be ≥ 0 because they can profitable jam over 3-bets.

**Für den Bot:** In OOP check-raise ranges on dynamic flops, emphasize: (1) very weak draws that convert large equity share by folds, (2) nutted hands, and (3) strongest draws that can happily stack off. Keep medium-strength made hands and medium draws mostly in call region to stabilize call vs bet strategy and avoid overexposure to 3-bets.

## Check-raise composition model (weak draws, strong value, very strong draws)
Given a check-raise option, the EV of including a hand class depends on its sensitivity to folds, calls, and 3-bets. Optimal composition: (i) very weak draws that massively gain from folds and are unplayable as calls, (ii) strong made hands to correlate pot size with strength and to punish loose calls, (iii) very strong draws that can shove profitably vs 3-bets, sharing stack-off region with value.

**Formel:** Let hand classes be: S (strong made), MD (medium made), SD+ (very strong draws), SD (medium draws), WD (very weak draws). Define fractions x_S, x_SDplus, x_WD included in check-raise range R_cr.

Indifference conditions at opponent’s thresholds (fold/call/3-bet) generate linear constraints:

For villain’s marginal calling hand h_c:
EV_vill(call | h_c) = EV_vill(fold | h_c)
=> mixture of (S, SD+, WD) in R_cr sets average equity vs villain h_c such that bluff/value ratio is correct.

For villain’s marginal 3-bet hand h_r:
EV_vill(3bet | h_r) = EV_vill(call | h_r)
=> share of SD+ and S that continue vs 3-bet must make h_r indifferent.

System: A · [x_S, x_SDplus, x_WD]^T = b, where A, b depend on bet/raise sizes and equities.

**Für den Bot:** On drawy boards facing IP c-bet, build your check-raise range by template: always include your strongest value (sets, 2p, strong straights), add your best combo draws (OESFD, strong pair+FD, etc.) that can 3-bet jam vs re-raises, and pad with lowest-EV draws that would otherwise be folds. Keep A-high FDs and medium-strength one-pairs mostly in check-call to avoid over-bluffing and to protect your calling range.

## Geometric growth bet sizing across streets
Use geometric growth of pot to schedule bet sizes that result in an all-in by river (or desired fraction of stack) while using the same fraction of pot each street. Base scheme on stack depth and flop texture: 3-street geometry on static boards; 4-street (smaller bets) when deep; 2-street (larger bets) on highly dynamic boards or 3-flush boards.

**Formel:** Let P0 be pot at start of betting sequence, S be effective stack you wish to invest by last street, and n be number of betting streets (e.g., 3: flop, turn, river; or 2 if you want to play for stacks over 2 streets). Assume same pot-fraction bet size α each street. Recurrence:

P_{k+1} = P_k + 2 * B_k   where B_k = α * P_k (hero bets αP_k, villain calls αP_k)
=> P_{k+1} = (1 + 2α) * P_k
=> P_n = P_0 * (1 + 2α)^n

Total hero investment across n streets:
I_hero = Σ_{k=0}^{n-1} B_k = Σ_{k=0}^{n-1} α P_k = α P_0 * ((1 + 2α)^n - 1) / (2α)
= (P_0 / 2) * ( (1 + 2α)^n - 1 )

Set I_hero = S_target (≈ effective stack portion to invest):
S_target = (P_0 / 2) * ( (1 + 2α)^n - 1 )
=> (1 + 2α)^n = 1 + 2 S_target / P_0
=> α = ( (1 + 2 S_target / P_0)^(1/n) - 1 ) / 2

**Für den Bot:** Implement a geometric bet-sizing module: given pot, stacks, and desired number of streets, compute α. Use ~3-street α (e.g., 1/2–2/3 pot) on static flops with moderate stacks; use smaller α and 4 streets when very deep; on very drawy or 3-flush boards, switch to 2-street geometry (larger α ≈ pot+) to front-load EV before your range loses equity realization on later streets.

## Texture-dependent adjustment of geometric α
Flop texture changes how much equity weaker ranges realize on later streets due to draw/clairvoyance effects. On more dynamic boards (2-flush, connected, etc.), the in-position weaker range becomes more clairvoyant by river (knows whether their draw missed and can overfold), so the stronger-range bettor should increase earlier-street bet sizes (higher α or fewer streets) to offset ex-showdown disadvantage. On very static boards, smaller α across more streets suffices.

**Formel:** Let α_static be geometric fraction chosen on static board with n streets.

On moderately drawy boards (e.g., two-flush):
α_drawy ≈ α_static + 0.5 * α_static = 1.5 * α_static  (as per text: from 1/2 pot to 3/4 pot)

On highly dynamic boards (e.g., 9♠ 8♠ 7♦, or 3-flush):
Use 2-street geometry instead of 3:

α_dynamic = ( (1 + 2 S_target / P_0)^(1/2) - 1 ) / 2

with S_target chosen to approximate stacking off by turn or river.

**Für den Bot:** Make α a function of board texture: e.g., start from a baseline 3-street α on dry high-card boards; increase α by ~50% on moderate 2-flush / semi-connected boards; on extremely draw-heavy or 3-flush boards, solve for 2-street α instead of 3-street. Hook this into your sizing tree to automatically produce larger bets on dynamic textures.

## Range balancing vs bet size: larger bets imply narrower ranges
For a fixed pot, increasing bet size requires narrowing the betting range (removing some marginal value and many bluffs) to keep bluff:value ratio balanced and prevent exploitation. Conversely, when using smaller bets and more streets, you can bet wider for value and include more bluffs because opponent’s price to call is better and thresholds shift.

**Formel:** In a one-street model with bet size B into pot P, equilibrium bluff:value ratio for bettor’s range vs a calling range that beats bluffs only (MDF model) is:

Let α = B / (P + B). Then optimal bluff fraction among betting hands is approximately:

b / (v + b) = α   (in symmetric [0,1] toy game)

=> b/v = α / (1 - α) = B / P

If we increase B (keeping P fixed), then allowed ratio b/v rises, but total betting range size must shrink because villain’s MDF decreases, i.e. villain can fold more often: MDF = P / (P + B). To avoid over-bluffing versus a now tighter-calling villain, we must reduce total bluffs proportionally to the narrowed call threshold.

**Für den Bot:** Tie your range width to bet size: as you move from 1/2-pot to 3/4-pot to pot or overbet, progressively cull the weakest value hands and most speculative bluffs from that line. Maintain roughly b/v ≈ B/P inside each betting line, but do it over a smaller underlying range at bigger B.

## Free-card danger vs checking behind on draw-heavy boards
On three-flush or draw-heavy flops, checking back gives free cards to many dominated draws, but some hands suffer little from free cards and can be used to protect checking range. Specifically, nut-backdoor plus strong made hand (e.g., A♣Kx on K♣7♣4♣) are ideal check-backs: they are ahead now, not badly hurt by a single club, and can capture induced bluffs on turn.

**Formel:** Let H be a candidate check-back hand on 3-flush flop. EV difference between bet and check:

EV_bet(H) = p_fold * (P0) + p_call * [Eq_vs_call * (P0 + 2B) - (1 - Eq_vs_call) * B]
EV_check(H) = E_turn[EV_future(H | free card)]

H is good check-back if:
(1) ∂EV_check/∂p_draw_realization is small (robust to villain improving).
(2) It captures significant EV vs future bluffs/semi-bluffs after check (line induces bets).

Nut-backdoor + top pair satisfies (1) and (2) better than e.g. bare AQ no club.

**Für den Bot:** On 3-flush flops where you’d otherwise pot-bet range, deliberately protect your check-back node with: (a) some strong showdown hands with nut blocker (A♣Kx, A♣Ax), and (b) some pure air. Avoid checking back medium-strength, non-blocking hands that are very vulnerable to free-card realization; those should mostly bet or fold.

## Turn continuation strategy template
Given a flop betting range, on blank or non-draw-completing turns you must split into check and bet subranges such that both remain balanced: check includes some strong hands, improved medium-strength hands, medium-strength bluff-catchers, and give-ups; bet includes other strong hands, decent value (top pair, 2p) and a mixture of strong and some weaker semi-bluffs, with clear responses vs raises.

**Formel:** Let F be the subset of hands that bet flop. On blank turn T, partition F into:

F_check = F_vsT_strong_subset ∪ F_newly_improved(T) ∪ F_mid_check_call(T) ∪ F_weak_check_fold(T)
F_bet = F_strong_rest(T) ∪ F_decent_value(T) ∪ F_strong_semibluff(T) ∪ F_weak_semibluff(T)

Indifference conditions at villain’s thresholds (call/fold/raise) constrain frequencies:

For villain’s marginal call hand h_c:
EV_vill(call vs F_bet) = EV_vill(fold)
=> P(H ∈ value | H ∈ F_bet) set by b/v ratio as before.

For your marginal check-call hand h_cc:
EV(check-call | h_cc) = EV(check-fold | h_cc)
=> villain’s bluff frequency after your check must make h_cc indifferent.

Need to choose mix in F_check vs F_bet to satisfy both sets of constraints.

**Für den Bot:** On turns after c-betting flop and getting called, avoid ‘check = give up’ leaks. Always leave some strong and call-ready hands in your check range (including some top pairs and slowplayed monsters) and continue betting with a mix of strong value plus draws. Structure it so that: (1) villain can’t profit by auto-betting when checked to, and (2) villain’s marginal turn calls vs your double barrel are indifferent.

## Effect of draw completion on turn strategy
When the obvious draw completes on the turn, many former semi-bluffs convert to strong value, while many one-pair bluff-catchers become relatively weaker. As a result, hands that would have been turn check-calls against a missed draw often demote to check-folds or thin bets; some previously weak bets can now be checked because they block strong draws or hold backdoor nut draws.

**Formel:** Let D be the obvious flop draw, and T be a card that completes D.

For a given hand H:
Equity_shift(H) = Eq_turn(H | T completes D) - Eq_turn(H | T blank)

If H ∈ former semi-bluff class: Equity_shift(H) >> 0 (promotion to value)
If H ∈ medium bluff-catcher (e.g., second pair): Equity_shift(H) << 0 (demotion)

Strategy mapping:
If Equity_shift(H) > θ_pos: include H more in bet/call or bet/3-bet range.
If Equity_shift(H) < θ_neg: demote H towards check-fold or mixed check-call.

θ_pos, θ_neg set by EV and indifference constraints vs villain’s densities after D completes.

**Für den Bot:** Condition your turn strategy heavily on whether the obvious draw hit. When it hits, recategorize: promote your flop semi-bluffs into your primary value region; tighten up your bluff-catchers (more folds/checks); increase use of blocker-based bluffs and backdoor-nut draws. Don’t keep firing turn with the same ‘top pair vs missed draw’ frequency once the draw is actually in.

## Backdoor nut flush draw (ace of suit) card-removal model
Holding the bare ace of the flush on a two-flush flop significantly affects opponent’s distribution: it reduces the number of strong nut-draw hands available to villain and adds runner-runner nut flush equity for you. This changes optimal call/fold decisions versus large raises and matters in equilibrium because villain’s perceived outs differ from true outs.

**Formel:** Example: Board K♣ 7♣ 2♥, hero holds A♣K♦ vs villain shove range.

Let villain’s intended flush-draw combos include A♣X♣. If hero holds A♣, then:

Count_villain_flushdraws_with_AcXc(hero has no Ac) > Count_villain_flushdraws_with_AcXc(hero has Ac)

Formally, card removal:

Let C be deck, H_hero hero hand, R board. Villain combos for class C_v are:
N_vill(C_v | H_hero, R) = | {h ∈ C\(H_hero ∪ R) : h satisfies pattern C_v } |

If Ac ∈ H_hero, then for C_v = {AcXc}:
N_vill(C_v | Ac ∈ H_hero, R) = 0

Thus hero’s posterior weight on villain holding nut FDs must be reduced; EV(call) adjusts upward relative to naive counting, or in some cases downward because villain’s remaining shove range is more value-heavy.

**Für den Bot:** Include explicit card-removal in your decision logic: when you hold the ace of the flush suit on a 2-flush flop, lower the frequency weight of villain’s A-high flush draws in his raise/jam range and slightly increase the weight of sets and non-nut FDs. Use combinatorial counting to adjust equities before solving for call/fold thresholds.

## River as asymmetric [0,1] game plus geometric value-bet sizing
River play is approximately the asymmetric [0,1] game: continuous (here discrete) hand strengths, no more cards to come. Goal is to arrive with a distribution whose strength correlates with pot size. On river, you often just continue the geometric growth bet pattern as value bets with appropriately strong hands.

**Formel:** In [0,1] toy game, if bettor’s distribution F_B(x) and caller’s distribution F_C(y) differ, equilibrium bet size b and bluff/value mix are solved by indifference of caller’s threshold hand y*.

For a given river pot P and target stack S already set by earlier streets, geometric bet size is:
B_river = α * P  (α from earlier geometric plan)

Applicable value range: choose threshold v* such that EV(value bet | strength ≥ v*) ≥ EV(check), and EV(caller(call | y*)) = EV(caller(fold | y*)) given your bluff frequency.

**Für den Bot:** Treat river nodes largely as one-street [0,1] problems: compute pot, allowed bet sizes (from your geometric plan), and then, for each size, choose a strength threshold above which you value bet and below which you either bluff or check, enforcing the MDF-style indifference conditions for villain’s bluff-catchers.

## Preemptive small river bets (blocking/merging) inspired by AKQ
From AKQ toy game: introducing a small bet size on the river with a mixed distribution of medium showdown hands and some strong value can improve EV by ‘preempting’ opponent’s big bet option. These preemptive bets function as block/merge bets: they lock in equity with marginal hands that dislike facing big bets and still extract value from worse and induce raises from better.

**Formel:** Let P be river pot; suppose standard options are {check, large bet B_L}. Introduce small bet B_S (B_S << B_L).

For your marginal showdown hand H_m:
EV_check(H_m) = p_check_through * W_sd(H_m) - p_face_large_bet * L(H_m)
EV_smallbet(H_m) =
  p_vill_fold * (P + B_S) +
  p_vill_call * [Eq_vs_call(H_m) * (P + 2B_S) - (1 - Eq_vs_call(H_m)) * B_S] +
  p_vill_raise * [complex, but often folded vs large raise]

If EV_smallbet(H_m) > EV_check(H_m), include H_m in small-bet range.

To keep villain indifferent with some bluff-catchers, mix in strong value V such that:
EV_vill(call_small | bluffcatcher) = EV_vill(fold_small | bluffcatcher).

This yields b/v ratio for the small-bet line analogous to [0,1] / AKQ solutions.

**Für den Bot:** Add a small river bet size used with: (a) medium-strength showdown hands that don’t want to face a pot/overbet, and (b) a slice of nutted hands. This preemptively blocks villain from making large +EV bluffs and extracts thin value. Calibrate the bluff:value mix in this small-bet line using same indifference/MDF logic as in AKQ/[0,1] games.

## Risk of Ruin function R(b)
Exponential model for probability that a bankroll b is eventually lost when repeatedly playing an independent, identically distributed +EV game with bounded downside.

**Formel:** Given bankroll b (in betting units) and RoR constant α > 0 for a +EV game:
R(b) = exp(-α * b)

For a game with EV < 0: R(b) = 1 for all b.
For a game with no negative outcomes: R(b) = 0 for all b.

**Für den Bot:** For any fixed stake/format, once α is known, the bot can instantly compute its long-run probability of busting a given NLHE bankroll size, guiding stake selection and stop-loss thresholds.

## Multiplicative RoR across bankroll chunks
Risk of ruin for a combined bankroll equals the product of RoR’s of its independent sub-bankrolls, implying log-RoR is linear in bankroll.

**Formel:** Property 5:
R(a + b) = R(a) * R(b)

Define f(x) = ln R(x). Then:
f(a + b) = f(a) + f(b) ⇒ f(x) is linear ⇒ f(x) = -α x
Thus:
ln R(x) = -α x
R(x) = exp(-α x)

**Für den Bot:** Because ln R(b) is linear in b, NLHE bots can treat ‘one bankroll unit’ as a fixed amount of log-risk and scale bankroll requirements proportionally to maintain a target RoR across stakes.

## Risk-of-ruin constant α via moment-generating equation
α is determined by the outcome distribution X of a single trial via an exponential-moment equation, independent of bankroll size.

**Formel:** Let X be the per-trial profit random variable with distribution {x_i} and probabilities {p_i}.
Property 6 + exponential form imply:
R(B) = E[ R(B + X) ]
exp(-α B) = E[ exp(-α (B + X)) ] = exp(-α B) * E[ exp(-α X) ]
⇒ 1 = E[ exp(-α X) ]

So α solves:
E[exp(-α X)] = Σ_i p_i * exp(-α x_i) = 1    (Equation 22.2)

Trivial solution: α = 0 (gives R(b)=1, correct when EV(X) ≤ 0).
Non-trivial α>0 exists and is unique for +EV games with some negative outcomes.

**Für den Bot:** Given a model of NLHE results per session or per tournament (discrete X), the bot can numerically solve E[e^{-αX}] = 1, then use α to map bankroll into RoR and calibrate bankroll requirements for its target risk profile.

## Specific RoR constant for die game example
Worked example of computing α and R(b) for a simple +1/−1-unit game; illustrates how to extract α from a simple discrete distribution.

**Formel:** Game: X = +1 with prob 2/3; X = -1 with prob 1/3.
Equation 22.2:
E[exp(-α X)] = (1/3) * exp(+α) + (2/3) * exp(-α) = 1
Solve:
(1/3)e^α + (2/3)e^{-α} = 1
Multiply by 3e^α:
e^{2α} + 2 = 3e^α
Let y = e^α:
 y^2 - 3y + 2 = 0 ⇒ (y-1)(y-2) = 0 ⇒ y = 1 or y = 2
y=1 ⇒ α=0 (EV≤0 branch). For EV>0 game, choose y=2 ⇒ α = ln 2.
Thus:
R(b) = exp(-α b) = 2^{-b}

Check: For b=1, R(1) = 1/2, matching direct recursion solution.

**Für den Bot:** In analogous binary-outcome NLHE spots (e.g., shove/fold SNG endgames modeled per tournament), the RoR over tournaments decays like c^{-bankroll}, where c is determined by solving E[e^{-αX}] = 1; even simple binary models can yield accurate bankroll–risk curves.

## RoR recursion property over a single play
Risk of ruin at bankroll B equals the expectation of risk of ruin after one more trial; this is the dynamic-programming consistency condition that leads to Equation 22.2.

**Formel:** Let X be outcome of one trial, bankroll B.
Property 6:
R(B) = E[ R(B + X) ]
For discrete X = {x_i} with probabilities {p_i}:
R(B) = Σ_i p_i * R(B + x_i)

Using exponential form R(b) = exp(-α b):
exp(-α B) = Σ_i p_i * exp(-α (B + x_i))
exp(-α B) = exp(-α B) * Σ_i p_i * exp(-α x_i)
⇒ 1 = Σ_i p_i * exp(-α x_i) = E[exp(-α X)]

**Für den Bot:** When simulating or approximating NLHE outcome distributions, the bot can validate a candidate α by checking that R(B) ≈ E[R(B+X)] numerically for multiple B; this serves as a consistency check for its bankroll-risk model.

## Qualitative RoR properties and EV sign cases
Boundary cases linking sign of expectation and presence of negative outcomes to RoR qualitative behavior.

**Formel:** Property 1: If P(X < 0) = 0 ⇒ no negative outcomes ⇒ R(b) = 0 for all b.

Property 2: If EV(X) < 0 ⇒ R(b) = 1 for all b (certain ruin if played indefinitely).

Property 3: If EV(X) > 0 and P(X < 0) > 0 ⇒ R(b) > 0 for all finite b.

Property 4: If EV(X) > 0 and negative outcomes are bounded below ⇒ R(b) < 1 for all b.

Thus, for +EV games with bounded downside and some losses, 0 < R(b) < 1 and R(b) → 0 as b → ∞.

**Für den Bot:** A NLHE bot should: (1) avoid formats where it has negative EV, since eventual bust is guaranteed; (2) recognize that some nonzero bust risk exists at any finite bankroll even in soft games; and (3) exploit capped-loss structures (e.g., capped buy-in cash games) which guarantee R(b) < 1 for +EV play.

## Risk-of-ruin for arbitrary discrete sit-and-go distribution (Example 22.3)
Application of Equation 22.2 to a realistic multi-outcome tournament distribution, showing how to compute α and then R(b) numerically.

**Formel:** Sit-and-go with buyin 200+15, outcomes (net of buyin):
1st: +785 with prob 0.12
2nd: +385 with prob 0.13
3rd: +185 with prob 0.13
4th–10th: -215 with prob 0.62
EV ≈ +35 per tournament.

Solve for α using Equation 22.2:
0.12 * exp(-α * 785)
+ 0.13 * exp(-α * 385)
+ 0.13 * exp(-α * 185)
+ 0.62 * exp(-α * (-215)) = 1

Numeric solution: α ≈ 0.000632
⇒ R(b) = exp(-0.000632 * b) where b is bankroll in dollars.

Example RoR values:
R(500)  ≈ 0.729
R(1000) ≈ 0.532
R(2000) ≈ 0.283
R(3000) ≈ 0.150
R(4000) ≈ 0.080
R(5000) ≈ 0.043
R(7500) ≈ 0.009
R(10000)≈ 0.002

**Für den Bot:** For any NLHE format (cash or SNG/MTT) the bot can build a discrete result distribution per ‘trial’ (session, SNG, etc.), solve Σ p_i e^{-α x_i}=1 numerically, then use R(b)=e^{-αb} to choose conservative or aggressive bankroll targets depending on acceptable bust probability.

## Card-removal-aware bluffing / calling indifference (qualitative)
On the river with marked draws, optimal bluffing frequencies must condition on card removal: opponent chooses bluff combos that block caller’s value hands; caller adjusts call frequencies upward when holding relevant blockers.

**Formel:** In the stud example: Opponent has a marked flush draw; Hero has aces up (two pair), no full house.
Opponent’s clairvoyant bluffing rule on river:
- When Hero does NOT hold one of Villain’s flush cards: Villain can choose bluff probability q such that Hero is indifferent between calling and folding with aces up.
- When Hero DOES hold one of Villain’s flush cards, blocking the made flush, Villain cannot make Hero indifferent for that subset; Hero’s best response is to call 100% in those cases.

Formally, indifference condition (in the no-blocker sub-distribution):
EV(call | no-blocker) = EV(fold | no-blocker)
⇒ P(value | bet, no-blocker) * (−amount_called)
 + P(bluff | bet, no-blocker) * (pot_size + amount_called)
 = 0
with P(bluff | bet, no-blocker) and P(value | bet, no-blocker) determined by Villain’s choice of bluff frequency q on his busted draws.

In blocker cases, no q can satisfy this equality, so Hero deviates to pure calling.

**Für den Bot:** When choosing bluff combos and call frequencies on the river, a NLHE bot must segment states by its own hole cards (blockers). In subtrees where its cards remove many opponent value hands, it should call more (even pure-call); when its cards remove many opponent bluffs, it should call less and bluff more with such blocker hands.

## Preemptive small bets as protection/value mix
When holding medium-strength hands on rivers that complete obvious draws, optimal strategy includes very small ‘preemptive’ bets (around 1/10 to 1/6 pot) mixing strong (e.g., flushes) and medium (e.g., pairs) to prevent exploitation by large bluffs and denial of equity.

**Formel:** Let pot = P, preemptive bet size = bP, with b ∈ [0.1, 1/6].
We partition our river distribution on draw-completing cards into:
- Strong: S (e.g., flushes)
- Medium: M (e.g., one pair, two pair that lose to flushes and strong raises)
- Air: A (busted draws)

We choose betting frequencies f_S, f_M, f_A such that:
1) Versus a raise, medium hands rarely call, so:
   EV(medium | check-call vs potential large bluffs)
   < EV(medium | bP preemptive bet, fold vs raises, get called by worse some %).
2) Opponent’s EV of bluff-raising river vs our small bet is minimized by ensuring our bet range contains enough S (and occasionally some strong M used as bluff-catch vs raises).

Indifference conditions are analogous to standard bluff/value frequency constraints but at small bet size bP instead of full-pot; exact frequencies depend on Villain’s raise size, range, and calling strategy and are not explicitly solved here.

**Für den Bot:** On rivers where a major draw hits and the bot still has many made draws itself plus medium-strength hands that dislike facing big bets, it should introduce very small block-bets (≈10–17% pot) with a balanced mix of value (strong draws made) and protection (medium) to (i) realize equity and (ii) reduce opponent’s profitable bluffing opportunities.

## Bankroll extraction caveat (RoR with withdrawals)
Classical RoR assumes reinvestment of all profits; maintaining a fixed target bankroll while withdrawing profits drives risk of ruin to 1 in infinite horizon.

**Formel:** Assumption of RoR model: All outcomes X are continuously added to bankroll; bankroll can grow without bound.

If instead we enforce bankroll cap B* and remove any profit above B* periodically, then over infinite time horizon:
R(B*) = 1

Intuition: Even +EV games have arbitrarily long downswings; without letting the bankroll grow beyond B*, eventually a downswing will exhaust B* with probability 1.

**Für den Bot:** If a NLHE bot’s operator regularly cashes out profits to keep bankroll at a fixed size, long-run RoR is 100%; to keep RoR meaningfully low, the system must either (a) allow bankroll to grow as winnings accrue or (b) accept higher practical RoR than predicted by the pure model and size stakes more conservatively.

## Exponential risk-of-ruin model and half‑bankrolls
Risk of ruin for a fixed +EV game with IID results is modeled as an exponential in bankroll. A key parameter a encodes the game’s profitability and volatility. A “half‑bankroll” H is the bankroll size where RoR = 1/2, and successive multiples of H reduce RoR geometrically.

**Formel:** Generic exponential RoR model:
R(b) = exp(-a * b)

Half‑bankroll H (bankroll where R(H) = 1/2):
exp(-a * H) = 1/2
=> -a * H = -ln(2)
=> H = (ln 2) / a

Geometric relation in units of half‑bankrolls:
R(n * H) = (1/2)^n
where n = b / H (for integer n; for real n this is an approximation within the exponential model).

**Für den Bot:** Model a given game/tree abstraction by an effective a, then use R(b)=e^{-ab} to quickly translate desired risk-of-bust constraints into required bankroll; the half‑bankroll H=ln2/a gives a compressed, easily comparable measure of how ‘swingy’ a given NLHE strategy+pool combination is.

## Risk of ruin with normally distributed outcomes
When per-period (e.g., per hand, per hour) results X are approximately normal with mean µ>0 and variance σ^2, the critical a that solves E[e^{-aX}] = 1 is a = 2µ/σ^2. Plugging this into the exponential RoR model yields a closed-form approximation for risk of ruin as a function of bankroll.

**Formel:** Setup: X ~ Normal(µ, σ^2), µ>0.

Solve for a in:
E[e^{-aX}] = 1
=> a = 0  OR  a = 2µ / σ^2
Critical (nontrivial) solution:
a* = 2µ / σ^2

Plug into generic RoR model R(b) = exp(-a*b):
R(b) ≈ exp( - (2µ/σ^2) * b )

So the normal-approximation RoR formula is:
R(b) ≈ exp( - 2 * µ * b / σ^2 )

**Für den Bot:** For a fixed NLHE game and seat, estimate long-run per-hand (or per-100) mean µ and variance σ^2 from data; then use R(b) ≈ exp(-2µb/σ^2) to choose game, stake, or stop-loss rules that meet a target risk-of-bust, rather than using ad-hoc ‘X buy-ins’ rules.

## Bias of normal approximation under skew and kurtosis
The exponential/normal RoR formula assumes symmetric, light‑tailed normal results. Large positive skew (tournaments; high upside, bounded downside) and heavy tails (no‑limit ring games) distort risk: skew tends to make the normal approximation overestimate RoR, while kurtosis alone tends to have small effect for realistic NL distributions.

**Formel:** No single closed form; the key comparisons given:

Tournament example (winner‑take‑all, 1 buy‑in risk per event):
- Direct solution for a: solve
  E[e^{-aX}] = (1/50) * e^{-99a} + (49/50) * e^{a} = 1
  Numerical solution: a ≈ 0.01683
  => R(100) = exp(-a * 100) = exp(-1.683) ≈ 18.6%

- Normal approximation using mean w and variance σ^2:
  R(100) ≈ exp(-2 w * 100 / σ^2) = exp(-2*1*100/197) ≈ 36.2%

Limit-ring example distribution (mild skew):
- Direct: a ≈ 0.00378 ⇒ R(300) = exp(-0.00378 * 300) ≈ 32.17%
- Normal approx: R(300) ≈ exp(-2 * 0.02 * 300 / 10.80) ≈ 32.89%

No‑limit ring example with fat tails (kurtosis, small skew):
- Direct: a ≈ 0.004789 ⇒ R(500) = exp(-0.004789 * 500) ≈ 9.12%
- Normal approx: R(500) ≈ exp(-2 * 0.12 * 500 / 50.27) ≈ 9.19%

**Für den Bot:** Do not blindly apply the normal RoR formula to strongly skewed settings like SNG/MTT bankroll modeling; instead, either solve E[e^{-aX}]=1 numerically from the actual discrete payoff distribution or treat tournaments separately. For NL cash, the normal approximation is generally acceptable, but be aware that highly one‑sided ‘win big lose small’ strategies make the normal formula conservative (overestimates RoR).

## Direct computation of a via mgf equation E[e^{-aX}] = 1
For a discrete game with finite outcomes {x_i} and probabilities {p_i}, the key parameter a in the exponential RoR model is defined implicitly by E[e^{-aX}] = 1. Solve this equation numerically, then RoR(b) = e^{-ab} is exact under the model assumptions. This works even for non‑normal, skewed, or heavy‑tailed distributions.

**Formel:** Let X take values x_i with probabilities p_i, i=1..n.
Define F(a) = E[e^{-aX}] - 1 = sum_{i=1}^n p_i * e^{-a x_i} - 1.
We want F(a) = 0 with the nontrivial positive solution a>0 (assuming E[X]>0).

Once a is found:
R(b) = exp(-a * b)

Examples in text:
1) Tournament example:
   (1/50) * e^{-99a} + (49/50) * e^{a} = 1 → a ≈ 0.01683.

2) Limit distribution with many hand outcomes: they numerically find a = 0.00378.

3) NL distribution with fat tails: they numerically find a = 0.004789.

**Für den Bot:** When doing serious bankroll or staking modeling for a specific NLHE strategy, approximate the per‑session payoff distribution explicitly (e.g., via simulation of your strategy vs pool), then solve E[e^{-aX}]=1 numerically to get a, instead of forcing a normal assumption; this is crucial for tournament formats or very asymmetric NL spots.

## Classification of games for RoR modeling (normal vs direct)
Different poker formats have different distributional properties (skew, kurtosis). The choice between using the normal-approximation RoR formula and solving the discrete mgf equation directly depends on these properties.

**Formel:** Summary table from the text:

Type of Game        → Risk formula to use              → Error of normal approximation
-------------------------------------------------------------------------------------
Limit ring games    → Normal distribution (R(b) ≈ e^{-2µb/σ^2})   → Small
Tournaments         → Direct calculation (solve E[e^{-aX}]=1)     → Large (normal gives too-high RoR)
No-limit ring games → Normal distribution (approx OK)            → Small

Underlying reference formulas:
1) Normal approximation:
   R(b) ≈ exp(-2 * µ * b / σ^2)

2) Direct discrete formula:
   Find a>0 such that E[e^{-aX}] = 1, then R(b) = exp(-a * b)

**Für den Bot:** Treat NL cash and limit cash similarly for RoR via the normal formula unless you know the distribution is extremely skewed; treat MTT/SNG bankroll and staking with a separate, more detailed discrete model. A production NLHE bot’s bankroll and table-selection module should switch modeling mode based on format.

## Risk of ruin with uncertain win rate (hierarchical model)
Win rate µ is not known exactly; we only have a noisy estimate w with standard deviation s observed over N hands/hours. We treat µ as a random variable with normal uncertainty around w (standard error s/√N). The effective, ‘robust’ risk of ruin is then the expectation, over this µ‑distribution, of the conditional RoR given µ using the normal approximation formula.

**Formel:** Observed data:
- Sample win rate: w (e.g., bets/hour)
- Sample standard deviation of results: s (≈ σ, the true game SD)
- Sample size: N (hands or hours)

Uncertainty in true win rate µ:
Approximate µ ~ Normal(mean = w, variance = (s^2 / N))
Standard error of w: SE(w) = s / sqrt(N).

Conditional risk of ruin at bankroll b given µ (using normal approximation):
R(b | µ) ≈ exp( - 2 * µ * b / σ^2 )
where we set σ ≈ s.

Define g(µ) as the density of µ:
 g(µ) = Normal(µ; w, s^2/N)

Then the overall, uncertainty‑adjusted RoR is:
R_eff(b) = E_µ[ R(b | µ) ]
         = ∫_{-∞}^{∞} exp( - 2 * µ * b / s^2 ) * Normal(µ; w, s^2/N) dµ

This is the integral of a value function (RoR as function of µ) against the posterior density of µ.

(Closed form is not given in the text; numerically approximating the integral is straightforward.)

**Für den Bot:** A bankroll module that uses only a point estimate of win rate is fragile: early overestimation of win rate leads to dramatically understated RoR. For NLHE cash, maintain (w, s, N) per game tree, treat µ as N(w, s^2/N), and integrate R(b|µ) over that distribution to get a conservative, uncertainty‑aware RoR before allowing aggressive table moves or bankroll withdrawals.

## Classical risk of ruin for fixed win rate
Risk that a bankroll b is eventually lost when repeatedly playing a game with known per-hand win rate w and per-hand standard deviation s, assuming independent results and exponential-approximation to gambler’s ruin.

**Formel:** R(w, b) = exp(-2 * w * b / s^2)

where:
- w  = true mean profit per hand (in same units as b, s)
- s  = standard deviation per hand
- b  = bankroll size

**Für den Bot:** For a given estimated true win rate and variance, the bot can quickly approximate the long-run bust probability at a stake size. This gives a simple bankroll rule: to keep risk of ruin below R*, require b ≥ -(s^2 / (2w)) * ln(R*).

## Sampling error of win-rate estimate
Observed win rate over N hands, with per-hand s, has a normal sampling distribution with standard error σ_w = s / sqrt(N).

**Formel:** σ_w = s / sqrt(N)

Observed win rate distribution:
   w_true ~ Normal(mean = w_hat, sd = σ_w)
where w_hat is the sample mean.

**Für den Bot:** The bot (or its bankroll module) should treat any estimated win rate as noisy with variance s²/N and avoid treating early, high win-rate samples as reliable input for stake choice or Kelly sizing.

## Normal density of win-rate estimate
Given an observed mean win rate w_hat with sampling error σ_w, model the uncertainty in the true win rate w as a normal distribution centered at w_hat.

**Formel:** f_w(x) = (1 / (σ_w * sqrt(2π))) * exp(-(x - w_hat)^2 / (2 * σ_w^2))

**Für den Bot:** When deciding stakes or risk limits, integrate over a distribution of possible true win rates instead of plugging in a point estimate. This means treating the bot’s own edge estimate as a distribution, not a constant.

## Risk of ruin under uncertainty (RoRU)
Expected risk of ruin when the true win rate is itself uncertain and modeled as normally distributed around an observed estimate w with standard error σ_w. It averages the simple risk-of-ruin over that win-rate distribution and accounts explicitly for the chance that the bot is actually a losing player (w_true ≤ 0).

**Formel:** Let
  w  = observed mean win rate
  s  = per-hand standard deviation of game
  b  = bankroll
  σ_w = standard error of win rate estimate

Define auxiliary quantities (using the derivation’s notation):
  u = 2 * b * s / (s**2) - w   (in the excerpt they write u = 2 b s_game / s_game^2 - w; 
                               more generally it is the shift term from completing the square)

The final RoRU formula as given in the text (their Eq. 23.1) is:

  RoRU(w, b; s, σ_w)
    = R(w, b) * exp( 2 * b**2 * σ_w**2 / s**2 - 2 * b * w / s**2 )
      * Φ( (w - 2 * b * σ_w**2 / s**2) / σ_w )
      + Φ(-w / σ_w)

where:
  R(w, b)   = exp(-2 * w * b / s**2)           (simple RoR at win rate w)
  Φ(·)      = standard normal CDF

(Algebraically, their text presents this in several equivalent exponential/completed-square forms; the key structural decomposition is: weighted RoR over w_true > 0 plus probability mass on w_true ≤ 0, whose RoR is 1.)

**Für den Bot:** When sample size is small or variance high, a NLHE bot’s bankroll/risk module should use RoRU instead of simple RoR: add a big penalty for the chance the bot is actually a small or negative winner. This implies more conservative table stakes and game selection early in a bot’s life or after environment changes.

## Decomposition of RoRU into positive and negative win-rate regions
RoRU splits into (1) expected risk of ruin conditional on being a winner (w_true > 0), weighted by the probability of being a winner, plus (2) the probability of being a loser (w_true ≤ 0), whose risk of ruin is 1 regardless of bankroll size.

**Formel:** RoRU = ∫_{0}^{∞} R(x, b) * f_w(x) dx + ∫_{-∞}^{0} 1 * f_w(x) dx

      = E[ R(w_true, b) | w_true > 0 ] * P(w_true > 0)
        + P(w_true ≤ 0)

where f_w(x) is the normal density of the (uncertain) true win rate w_true.

**Für den Bot:** A bankroll module should explicitly track P(edge ≤ 0). Even if current estimate is slightly positive, if P(edge ≤ 0) is large, then effective risk of ruin is high. This pushes the bot to either reduce stakes, gather more data, or stop playing certain games.

## Probability the bot is a losing player given its sample (normal model)
Given observed win rate w and standard error σ_w, the probability that the true win rate is ≤ 0 under the normal model is just the lower tail of the standard normal.

**Formel:** P(w_true ≤ 0 | w, σ_w) = Φ(-w / σ_w)

P(w_true > 0 | w, σ_w) = 1 - Φ(-w / σ_w) = Φ(w / σ_w)

**Für den Bot:** Before taking larger shots (higher stakes) or raising Kelly fractions, the bot should require P(true win rate > 0) to be very high (e.g., ≥ 95%) by checking w / σ_w. Otherwise treat the game as effectively too risky.

## Effect of reducing effective win rate (expenses, rakeback, cashouts)
Risk of ruin depends on the *net* win rate that stays in the bankroll. If a fraction of profits is withdrawn (for living expenses, etc.), the effective w used in RoR/RoRU must be reduced, dramatically increasing risk of ruin when w_eff is small.

**Formel:** Let:
  w_gross  = EV from the game (bets per hand or per 100 hands)
  c        = constant outflow per hand (or per 100 hands), as an equivalent negative win rate

Then effective win rate used for bankroll growth and RoR is:

  w_eff = w_gross - c

Simple RoR using w_eff:

  R_eff(b) = exp(-2 * w_eff * b / s^2)

Similarly, for RoRU, use w = w_eff in place of raw observed w.

**Für den Bot:** A NLHE bot that periodically cashes out winnings (or pays fixed costs like server fees/rake structure changes) must compute RoR based on net w that actually remains in its playing bankroll. Even small outflows can turn a marginal winner into an almost certain bust over time.

## Asymmetry of win-rate estimation error on RoR
Because RoR depends exponentially on w, overestimating w by a small amount severely underestimates RoR, while underestimating w by the same amount only mildly overestimates RoR.

**Formel:** R_true = exp(-2 * w_true * b / s^2)
R_est  = exp(-2 * (w_true + δ) * b / s^2)

Then:
  R_est / R_true = exp(-2 * δ * b / s^2)

If δ > 0 (overestimate), R_est << R_true when b is large; if δ < 0, R_est >> R_true, but the impact is capped at 1 (cannot exceed certainty of ruin).

**Für den Bot:** Bankroll management for a bot should be conservative: treat win-rate estimates as biased high and use a haircut (e.g., multiply w by 0.5 or subtract several standard errors) when sizing stakes or Kelly fractions.

## Virtual bankroll concept
Augment the literal poker bankroll with expected external cash flows (salary, backers, etc.). The effective bankroll for RoR is the maximum total loss the agent is willing/able to cover at the current stakes, not just chips already in the account.

**Formel:** Let:
  B_poker   = current physical bankroll
  B_ext     = present value of likely external infusions available for poker at this stake

Define virtual bankroll:
  B_virtual = B_poker + B_ext

Use B_virtual in place of b in RoR/RoRU, subject to the constraint that the player actually will commit that much before quitting or moving down.

**Für den Bot:** If the NLHE bot is backed by a large funding pool, it can use a larger effective bankroll for risk calculations; but if the backing is conditional or capped, RoR must be computed relative to that cap, not the theoretical wealth of the owner.

## Kelly utility and certainty equivalent
Use logarithmic utility U(x)=ln x in place of dollar-EV to account for bankroll growth and risk aversion; the certainty equivalent of a random gamble is the sure amount X with equal utility.

**Formel:** Given bankroll B and random outcome x from a game X:
U_Kelly_after = E[ ln(B + x) ]
Change in utility from playing = E[ ln(B + x) ] - ln(B)
Certainty equivalent CE satisfies:
ln(CE) = E[ ln(B + x) ]  (or ln(CE) = E[ln(b)] for a generic bet B with outcome b)

**Für den Bot:** When choosing stakes or structures, the bot (or its bankroll manager) should evaluate E[ln(bankroll after)] rather than only chip-EV, to balance growth versus risk of ruin.

## Kelly fraction for even-money edge bets
For a repeated even-money bet with known edge, the Kelly-optimal stake is a fixed fraction of current bankroll that maximizes expected log-growth.

**Formel:** Even-money bet, probability of win p, loss q = 1 - p, stake fraction f of bankroll B:
Outcomes: B(1+f) with prob p; B(1-f) with prob q.
Maximize G(f) = E[ ln(B(1 ± f)) ] = p ln(1+f) + q ln(1-f).
Setting derivative to zero:
G'(f) = p/(1+f) - q/(1-f) = 0
⇒ p(1-f) = q(1+f)
⇒ p - pf = q + qf
⇒ (p - q) = f(p + q) = f
So optimal Kelly fraction f* = p - q = edge per unit staked.

In the book’s numeric example: p = 0.515, q = 0.485 ⇒ f* = 0.03 = 3%.

**Für den Bot:** When the bot (or its owner) estimates a reliable edge in a side bet or format with even-money payouts, the Kelly guideline is to risk edge-fraction of its current bankroll, not to shove full roll; this caps leverage relative to estimated edge.

## Optimal bankroll for a fixed bet game (Kelly growth)
Given a fixed bet size and a favorable game, there exists a bankroll size that maximizes per-hand Kelly utility gain; below or above that, marginal log-growth per play is smaller.

**Formel:** For a game with fixed bet size 1 and outcomes +1 with prob p and −1 with prob q = 1−p, bankroll B:
U(B) = p ln(B − 1) + q ln(B + 1) − ln(B)
Example (die game): win +1 with prob 2/3, lose −1 with prob 1/3:
U(B) = (1/3) ln(B − 1) + (2/3) ln(B + 1) − ln B
Derivative:
U'(B) = 1/[3(B−1)] + 2/[3(B+1)] − 1/B
Solve U'(B)=0 ⇒ B = 3 (optimal bankroll in units of bet size).

**Für den Bot:** For fixed-size buy-ins (e.g., a specific NLHE stake), there is an approximate bankroll level where adding more roll gives diminishing log-growth from that game; this informs when it’s log-utility-optimal to move up or diversify instead of just accumulating at one stake.

## Approximate Kelly utility for small bets via Taylor expansion
When individual game outcomes x are small relative to bankroll B, ln(1+x/B) can be approximated by its second-order Taylor expansion, expressing log-utility in terms of mean and variance of outcomes.

**Formel:** General change in Kelly utility for one play:
U = E[ ln(B + x) ] − ln B = E[ ln(1 + x/B) ].
Taylor series for |t|<1:
ln(1 + t) = t − t^2/2 + t^3/3 − t^4/4 + …
Let t = x/B. If |x| ≪ B, ignore ≥3rd order terms:
ln(1 + x/B) ≈ x/B − x^2/(2 B^2).
Take expectations:
U ≈ E[x]/B − E[x^2]/(2 B^2).
With mean µ = E[x], variance σ^2 = Var(x):
E[x^2] = µ^2 + σ^2.
So
U ≈ µ/B − (µ^2 + σ^2)/(2 B^2).

**Für den Bot:** For cash games where a single session’s swing is small relative to roll, the bot can evaluate formats using U ≈ µ/B − (µ²+σ²)/(2B²), trading off win rate against variance instead of comparing win rates alone.

## Bankroll cutoff between two games using Kelly approximation
Given two games with different win rates and variances, there is a bankroll cutoff c where both have equal approximate Kelly utility; above c you prefer the higher-variance, higher-stakes game, below c the lower one.

**Formel:** Game i has mean µ_i and variance σ_i^2 per unit time (e.g., per hour), bankroll B.
Approximate Kelly utility per unit time:
U_i(B) ≈ µ_i/B − (µ_i^2 + σ_i^2)/(2 B^2).
At cutoff B=c, utilities equal:
µ_1/c − (µ_1^2 + σ_1^2)/(2c^2) = µ_2/c − (µ_2^2 + σ_2^2)/(2c^2).
Multiply by 2c^2:
2c µ_1 − (µ_1^2 + σ_1^2) = 2c µ_2 − (µ_2^2 + σ_2^2).
Rearrange:
2c(µ_1 − µ_2) = (µ_1^2 − µ_2^2) + (σ_1^2 − σ_2^2).
Thus
2c = (µ_1 + µ_2) + (σ_1^2 − σ_2^2)/(µ_1 − µ_2).
When |µ_i| ≪ σ_i (typical in poker), the first term is negligible, giving the book’s approximation:

c ≈ (σ_1^2 − σ_2^2) / (2 (µ_1 − µ_2)).   (Eq. 24.1 simplified)

Example 24.2: $20–40 (game 2): µ_2=35, σ_2=400; $40–80 (game 1): µ_1=60, σ_1=800.
Compute:
2c = 60 + 35 + (800^2 − 400^2)/(60 − 35) = 95 + (640000 − 160000)/25 = 95 + 480000/25 = 95 + 19200 = 19295.
So c ≈ 19295.

**Für den Bot:** Given estimates (µ,σ) for multiple NLHE stakes, the bankroll manager can compute c and program the bot to move up only when bankroll exceeds c (and move down when below), maximizing risk-adjusted growth instead of following arbitrary ‘X buy-ins’ rules.

## Sharpe ratio for poker portfolios
Sharpe ratio summarizes risk-adjusted performance as expectation divided by standard deviation; for scalable opportunities, maximizing Sharpe maximizes risk-adjusted growth.

**Formel:** Sharpe ratio S for a game or portfolio:
S = µ / σ   (Eq. 25.1)
where µ is expectation (e.g., $/hr, bb/100) and σ is standard deviation of results in the same units over the same horizon.

**Für den Bot:** When choosing between formats with different stakes and volatility, compare µ/σ, not just µ; a higher-variance game needs disproportionately higher win rate to be equally attractive on a risk-adjusted basis.

## Diversification between independent +EV poker investments
Mixing independent investments (e.g., staking deals, tournament swaps, different games) can reduce variance faster than it reduces expectation, improving the portfolio’s Sharpe ratio even if one component is ‘worse’ in isolation.

**Formel:** For independent investments A and B with expectations µ_A, µ_B and standard deviations σ_A, σ_B, a portfolio with fraction w in A and (1−w) in B has:
µ_P = w µ_A + (1−w) µ_B
σ_P^2 = (w σ_A)^2 + ((1−w) σ_B)^2   (assuming zero correlation).

Example from text: A and B both have µ=10, σ=100. All-in A: S=0.1. 50/50 mix:
µ_P = 10
σ_P = 100 / sqrt(2) ≈ 70.71
S_P ≈ 10/70.71 ≈ 0.141 > 0.1.

**Für den Bot:** A bot’s owner can improve risk-adjusted returns by spreading capital across multiple independent bots/tables/formats instead of concentrating on a single high-variance edge; lower correlation and balanced stakes raise overall Sharpe.

## Optimal swap/weight between two equal-EV but different-variance tournaments
When two independent tournaments both have the same expectation but different variances, swapping a fraction of action can minimize variance and thus maximize Sharpe ratio.

**Formel:** Text example: Player A’s tournament: µ_A=1 buyin, σ_A=9; B’s: µ_B=1, σ_B=12. A wants to hold fraction α of himself and (1−α) of B. Both have same µ, so µ_P=1 regardless of α. Variance (assuming independence):
σ_P^2 = (α σ_A)^2 + ((1−α) σ_B)^2 = (9α)^2 + (12(1−α))^2.
Differentiate w.r.t α and set to 0:
0 = dσ_P^2/dα = 2 α σ_A^2 − 2 (1−α) σ_B^2
⇒ α σ_A^2 = (1−α) σ_B^2
⇒ α (σ_A^2 + σ_B^2) = σ_B^2
⇒ α* = σ_B^2 / (σ_A^2 + σ_B^2).
In numbers: σ_A=9, σ_B=12 ⇒ α* = 12^2 / (9^2+12^2) = 144 / (81+144) = 144/225 = 0.64.
So A should keep 64% of himself and swap 36%.

**Für den Bot:** For high-variance NLHE tournaments, rational swapping/staking between independent bots or players can significantly reduce bankroll swings per unit of edge; optimal swap fractions depend on relative variances, not just skill or ego.

## General optimal portfolio weights for two independent +EV investments
For two independent +EV investments with possibly different expectations, there is an optimal set of weights that maximize Sharpe by equalizing contribution per unit variance; after normalizing expectations, weights depend only on scaled standard deviations.

**Formel:** Let investments 1 and 2 have expectations w1, w2 and std devs σ1, σ2 per unit capital. Normalize 1’s standard deviation to 1 unit of expectation comparable to 2 by scaling:
s1 = σ1 * (w2 / w1).
After scaling, both have win rate w2, standard deviations s1 and σ2. Let a1, a2 be portfolio weights with a1+a2=1. Portfolio variance (independent assumption):
σ_P^2 = (a1 s1)^2 + (a2 σ2)^2.
Plug a2 = 1−a1:
σ_P^2 = (a1 s1)^2 + (1−a1)^2 σ2^2.
Differentiate and set to zero:
0 = 2 a1 s1^2 − 2 (1−a1) σ2^2
⇒ a1 s1^2 = (1−a1) σ2^2
⇒ a1 (s1^2 + σ2^2) = σ2^2
Thus optimal weights:
a1* = σ2^2 / (s1^2 + σ2^2)   (Eq. 25.2 in spirit)
a2* = s1^2 / (s1^2 + σ2^2)    (Eq. 25.3 in spirit)
Note: s1 includes the w2/w1 factor, so the formula implicitly accounts for different expectations.

**Für den Bot:** If a bankroll manager runs multiple independent NLHE bots with different winrates and variances, the capital allocation that maximizes overall risk-adjusted performance should follow these variance-weighted proportions, not simply ‘put everything on the highest bb/100’.

## Normal-approximation model of long-run hourly winrate
Model a player’s cumulative cash game results over a fixed number of hours as a normal random variable with known mean and standard deviation.

**Formel:** Let hourly winrate be μ ($/hour) and hourly standard deviation be σ ($/hour). Over T hours, total result X is approximated by

X ~ N(w, s^2)
where
w = μ * T
s = σ * sqrt(T)

**Für den Bot:** For bankroll/EV modeling, approximate your long-run result over N hands or hours as normal with mean proportional to volume and standard deviation proportional to sqrt(volume); this underlies risk-of-ruin and staking decisions.

## Backing agreement as a call option (0-threshold)
A staking deal where the backer eats all losses and the player gets a fixed fraction of profits is mathematically a call option on a normal underlying with strike 0. First compute the value of getting 100% of upside and 0% of downside, then multiply by the player’s profit share.

**Formel:** Let X ~ N(w, s^2) be total result over the agreement. Define the 0-strike call value

C_0 = E[max(X, 0)]

For X normal, the closed form is (MoP Eq. 25.6):

z = w / s
C_0 = s * φ(z) + w * Φ(z)

where φ is the standard normal density,
φ(z) = (1 / sqrt(2π)) * exp(-z^2 / 2),
and Φ is the standard normal CDF.

Player gets fraction p of upside only, so player EV = p * C_0.
Backer EV = w - player EV.

**Für den Bot:** If you are staked on a simple ‘X% of profits, no share of losses’ deal, your cash EV is not μT * X%; it’s X% of an option value s*φ(z)+w*Φ(z). This option convexity means riskier, higher-variance games or lines can be +EV for you but -EV for your backer.

## Backing agreement as a call option with threshold a
A deal where the player only starts sharing profits above a threshold a (e.g., after clearing a makeup or target) is a call option with strike a. Again compute the option value for 100% upside above a then scale by the player’s tier percentage.

**Formel:** Let X ~ N(w, s^2). Define a-threshold call

C_a = E[max(X - a, 0)].

MoP Eq. 25.7 (rewritten in standard form):

z_a = (w - a) / s
C_a = s * φ(z_a) + (w - a) * Φ(z_a)

φ and Φ as above.

Player with share p_a on profits above a has EV contribution

EV_player(a-tier) = p_a * C_a.

If the player previously had share p_0 at a=0 with EV p_0 * C_0, and you move the threshold to a>0, the new share p_a needed for parity (same EV) solves

p_a = (p_0 * C_0) / C_a.

**Für den Bot:** In makeup / hurdle structures, getting paid only after some target makes your option more out-of-the-money; to keep the same EV you must negotiate a higher percentage of profits beyond that target. For a bot, this affects how aggressively to chase high-variance edges near the end of a staking period.

## Tiered backing agreements as sums of truncated call options
A multi-tier deal (different percentages in successive profit bands) decomposes into a sum of call options with piecewise strikes. Each tier’s value is the difference of two a-threshold option values, times that tier’s percentage.

**Formel:** Let X ~ N(w, s^2). Consider K tiers with boundaries 0 = a_0 < a_1 < ... < a_K (a_K may be ∞), and player percentage p_k on (a_k, a_{k+1}].

Define C_a = E[max(X - a, 0)] as above.

Tier k’s gross option value V_k (value if player took 100% of that tier) equals

V_k = E[max(X - a_k, 0)] - E[max(X - a_{k+1}, 0)]
    = C_{a_k} - C_{a_{k+1}}.

Player’s EV from tier k = p_k * V_k.

Total player EV = Σ_{k=0}^{K-1} p_k * (C_{a_k} - C_{a_{k+1}}).

**Für den Bot:** If your staking deal has escalating cuts in higher profit tiers, your effective share of overall EV can be much higher than your base % suggests. A bot that models its deal as a sum of truncated calls can evaluate whether entering higher-variance games is worthwhile and how much to value a given staking offer.

## Decomposition of overall expectation into win-side and loss-side components
For X ~ N(w,s^2), we can decompose expectation into the contribution from outcomes above 0 (wins) and below 0 (losses). The call option value C_0 gives the aggregate positive-side contribution; the negative-side expectation is then determined by total mean conservation.

**Formel:** Let X ~ N(w, s^2).

Win-side total (over all X>0):
W_plus = E[ X * 1_{X>0} ] = C_0 = s * φ(z) + w * Φ(z),   z = w/s.

Overall mean: w = E[X] = W_plus + W_minus.
So loss-side total (over all X<0):
W_minus = w - C_0.

In the book’s numerical example: w=4000, s=6000.
They find C_0 ≈ 4906.72, hence W_minus ≈ -906.72.

**Für den Bot:** Under staking, your EV comes only from the positive tail; the heavier that tail relative to total mean, the more of the overall expectation you capture. This encourages high-variance, positively-skewed spots for the staked bot, especially near the end of finite-term deals.

## Tournament chip equity vs prize equity (ICM-style decoupling)
In tournaments, chip stacks have nonlinear value due to payout structure. Chip equity (fraction of chips) differs from prize equity (fraction of prize pool). Near the bubble, tiny stacks can have high prize equity relative to their chips because survival probability is what matters.

**Formel:** Conceptual relationships rather than a specific closed form in the excerpt.

Chip equity for player i early:
CE_i ≈ (stack_i / total_chips) * total_prize_pool.

Prize equity PE_i is the expected cash given stack_i and payout ladder, which is not linear in stack_i. Near bubble or payout steps, PE_i >> CE_i for very short stacks.

Example in text:
Total chips = 300,000, prize pool = $20,000.
Player A stack = 100 chips.
Early-game linear chip value: CE_A ≈ (100 / 300000) * 20000 ≈ $6.67.
Near bubble with two shorter-stacks forced all-in next hand, survival probability to min-cash is estimated at 84%.
Min cash = $250 ⇒ PE_A ≥ 0.84 * 250 ≈ $210 (ignoring upside when doubling).
So PE_A / CE_A ≈ 210 / 6.67 ≈ 31.5x.

**Für den Bot:** A tournament bot must treat chips nonlinearly: survival and payout jumps make 1 extra chip worth much more to a micro-stack near the bubble than to a big stack. Do not reuse cash-game EV logic; use an ICM-like or dynamic model of prize equity when making shove/call decisions in late stages.

## Skill-edge model for tournament risk-taking
Players with a positive per-hand or per-spot skill edge should be more conservative risking their entire stack; players with negative skill should gamble more. The book sketches a recursive model where future edge justifies passing on current thin edges, constrained by the finite number of future high-EV spots.

**Formel:** The excerpt here is conceptual only. Qualitative rule:

Let ΔE_future be expected additional tournament prize EV from playing future hands if you survive, comparing your skill to field average.
Let ΔE_current be tournament prize EV gain from taking some marginal all-in now (relative to folding).

Take the all-in only if
ΔE_current ≥ ΔE_future_lost_from_elimination.

As blinds escalate and stack-to-blind ratio falls, ΔE_future shrinks, so threshold for gambling decreases over time.

**Für den Bot:** In tournament strategy, a strong bot should fold some slightly +chip-EV but high-variance stack-off spots early when its future skill edge is large, but should not overdo this as the number of remaining hands shrinks. A weak or breakeven bot should be more willing to take thin gambles early.

## Theory of Doubling Up (winner‑take‑all, equal skill)
Model tournament win probability as repeated independent doubles of current stack; for equal‑skill players in winner‑take‑all, chip value is linear and C = 0.5.

**Formel:** Let X = number of players (all equal skill, equal stacks).
Let N = number of required doubles to win = log2(X).
Let C = probability to double stack before busting (assumed constant across stack sizes).
Let E = probability of winning the tournament.

Core relationship:
E = C^N          (26.1)

At the start of a winner‑take‑all event with equal skill:
E = 1/X
N = log2(X)
So:
1/X = C^(log2 X)
log2(1/X) = (log2 X) * log2(C)
=> log2(C) = -1
=> C = 0.5

Thus for equal skill in winner‑take‑all, C = 0.5 and chip value is exactly linear in stack size.

**Für den Bot:** In winner-take-all phases where skill is approximately symmetric, treat chip EV as linear and use standard cash-game style EV maximization. The equivalent doubling probability C is 0.5, so no extra conservatism is justified purely by tournament structure in such spots.

## Theory of Doubling Up (unequal skill, winner‑take‑all)
For a player with skill edge, model their constant double‑before‑bust probability C > 0.5 and use it to map stack size to tournament win probability.

**Formel:** Let X = total number of players / starting stacks.
Let N = log2(X) = doubles from 1 stack to all chips.
Let E0 = player’s overall probability of winning (measured in “tournament wins per entry”).
Then:
E0 = C^N
=> C = E0^(1/N) = E0^(1 / log2 X)

For any stack size S (measured in starting stacks), required doubles to win:
N(S) = log2(X/S)
Win probability from stack S:
E(S) = C^N(S) = C^(log2(X/S))

Example from text: X = 100, E0 = 2/100 = 0.02
N = log2 100 ≈ 6.643856
C = 0.5550 (numerically)

**Für den Bot:** Estimate an effective C > 0.5 from your long‑run ROI/ITM data; then map any stack S to a compensated tournament equity E(S) instead of using linear chip EV. This makes the bot fold some positive chip‑EV but negative prize‑EV gambles early when it has a skill edge.

## Nonlinear stack‑to‑equity mapping: E = S^β
Reexpress Theory of Doubling Up as a power law mapping between stack fraction S and normalized equity E, with exponent β determined by C.

**Formel:** Let S = fraction of total chips held (S in (0,1]).
Required doubles to win from S: N = log2(1/S) = -log2 S.
E = C^N = C^(-log2 S).
Using logarithms:
E = S^{-log2 C}.

Define β = -log2 C.
Then:
E = S^β        (26.2)

• Equal skill: C = 0.5 => β = -log2(0.5) = 1, so E = S (linear chips).
• Skilled player: C > 0.5 => β < 1, making E(S) concave in S (diminishing marginal equity of extra chips).

**Für den Bot:** Use E ≈ S^β (β<1 if you’re stronger than the field) as a cheap approximation to convert chip stacks to tournament equity. This makes large stacks worth slightly less than linearly and should bias the bot against high‑variance marginal gambles when already deep.

## Coinflip indifference threshold W* = C
Derive the required win probability W* to be indifferent to a full‑stack all‑in coinflip early in a winner‑take‑all tournament under Theory of Doubling Up.

**Formel:** Initial equity: E0 = C^N, where N = doubles needed from starting stack.
After winning a double: E1 = C^(N-1).
Take a flip with win probability W:
EV(call) in equity units: WE1 + (1-W)*0 = W*C^(N-1).
EV(fold): E0 = C^N.
Indifference condition:
W*C^(N-1) = C^N
=> W = C.

So the minimum required win probability to accept a full‑stack flip is:
W* = C.

Example: If a player would decline a 57–43 all‑in (W=0.57) in a 250‑player tournament, then:
Assuming W* = C ≈ 0.57,
Their win probability:
E0 = C^N = 0.57^log2(250) ≈ 0.01114 ≈ 2.85 buyins per entry.

**Für den Bot:** Calibrate early‑level shove/call thresholds to your estimated C: accept full‑stack flips if your equity ≥ C. A strong bot (C>0.5) should still accept many +chip‑EV flips but can rationally fold some marginal ones; a losing bot (C<0.5) should embrace variance and call closer to chip‑EV thresholds.

## Multiway all‑in requirement (third‑man effect)
In tournaments, a skilled player’s nonlinear equity in chips makes calling as the third all‑in participant require stricter equity than chip‑EV alone (more than 1/(#players)).

**Formel:** Chip‑EV breakeven in a 3‑way all‑in with pot‑sized bet from each player:
Required share of final pot under linear chips: p_chip = 1/4 = 25%.

Under Theory of Doubling Up with C > 0.5, losing all chips is worse than losing the same chips in expectation while retaining future skill leverage.

Example given: C = 0.55 (so E(S) is concave). In a 3‑way all‑in where winning multiplies stack by 4 (two extra doubles equivalent), needed pot share is about 30.25% instead of 25%:

p_tourn ≈ C^2 * p_chip  adjusted upward → about 30.25% for C=0.55.

(Exact general formula is not given; the key result is that the required equity > 1/4 and depends on C.)

**Für den Bot:** When facing multiway all‑ins, require a significantly higher equity share than chip‑EV would suggest. As a rough heuristic, require ~5–10 percentage points more equity than 1/k in k‑way all‑ins when you have a skill edge (C>0.5). Avoid being the third caller with merely chip‑breakeven hands.

## Prize‑pool equity with structured payouts via Theory of Doubling Up
Extend doubling‑up model to prize‑pool equity EN in buyins given match‑play structure and chance to double C, including non‑winner‑take‑all payouts (first + second).

**Formel:** Winner‑take‑all, 256‑player match play:
Total prize pool = 256 buyins, 1st = 256, others 0.
Number of match wins needed: N = 8 (since 2^8 = 256).
Equity in buyins:
EN = (256) * C^8 = (2C)^8.

General formula for winner‑take‑all with X buyins and N doubles:
EN = X * C^N = (2C)^N.

Equal split between 1st and 2nd in 256‑player match play:
1st = 128, 2nd = 128.
Equity:
EN = 128 * C^7 = (2C)^7.

Comparison:
(2C)^8 > (2C)^7  iff C > 1/2.
So when C > 0.5, flattening payouts (more to 2nd) actually *lowers* the skilled player’s equity because some late‑stage edges are replaced by fixed payouts.

General 1st/2nd split: total 256, first fraction f, second fraction (1-f).
1st prize = 256f, 2nd = 256(1-f).

Player’s equity:
EN = 256 * [ f*C^8 + (1-f)*(C^7 - C^8) ]
   = 256 * C^7 * (2fC + 1 - C - f).

Let δ = C - 0.5.
Then:
EN = 256 * C^7 * [ δ(2f - 1) + 1/2 ].

**Für den Bot:** When modeling future tournament EV, don’t treat all chips as aiming at 1st‑place money; incorporate the actual payout structure. In top‑heavy structures, late‑stage chips are more valuable to skilled bots; in flatter payouts, edges are partially capped and variance‑embracing lines become less attractive for winners but better for weaker bots.

## Effective tournament size k under structured payouts
Define an effective field size k for structured payouts so that a skillful player’s equity under the real payout equals their equity in a fictitious winner‑take‑all tournament of size k with the same C.

**Formel:** Goal: Find k such that the player’s equity in the real payout equals equity in a winner‑take‑all event with k players (and same C).

By definition:
(2C)^(log2 k) = EN   (26.3)

where EN is player’s equity in the actual tournament (in buyins), C is double‑up probability.

Equivalently:
log2 k = ln(EN) / ln(2C)
=> k = 2^[ ln(EN) / ln(2C) ].

In the 256‑player match‑play example with 1st fraction f and 2nd fraction (1-f):
EN = 256 * C^7 * [ δ(2f - 1) + 1/2 ], δ = C - 0.5.
Then set:
(2C)^d = EN, with d = log2 k.
Solve:
(2C)^(d-7) = 2 * [ δ(2f - 1) + 1/2 ].
(d - 7)*ln(2C) = ln( 2 * [ δ(2f - 1) + 1/2 ] )
=> d = ln( 2 * [ δ(2f - 1) + 1/2 ] ) / ln(2C) + 7
=> k = 2^d.

Example (from text):
• f = 154/256 ≈ 0.6015625, C = 0.52 (δ = 0.02)
→ d ≈ 7.206, k ≈ 147.68.
So 256‑player event with that 1st/2nd split has skill latitude similar to a 148‑player winner‑take‑all.

**Für den Bot:** Approximate complex payout structures by an effective field size k and then plug k into your doubling‑up model. This lets the bot use a simple winner‑take‑all style mapping E(S) while still roughly accounting for how flat or top‑heavy the payouts are.

## Tournament equity decision example: call/fold with skill edge
Apply the doubling‑up model to a specific NLHE decision to decide whether to call an all‑in when chip‑EV is positive but tournament‑EV (in buyins) is not, due to a skill edge.

**Formel:** Setup:
• 250‑player tournament, starting stack = 1500 chips.
• Player B has edge: starting equity E0 = 1.75 / 250 buyins (1.75 is total expected payoff in buyins).
Compute C:
1.75 / 250 = C^{log2(250)}
=> C ≈ 0.5364.

Stacks:
• If B folds: stack = 2050 chips = 1.36667 starting stacks.
• If B calls and wins: stack = 6075 chips = 4.05 starting stacks.
• If B calls and loses: stack = 0.

We treat the total effective field size as 250 and use E(S) = C^{log2(250/S)} (or equivalently scaled E = S^β up to normalization).

Explicit computations as in text (using original form):
If call & win: S_win = 4.05.
E_win = 0.5364^{log2(250 / 4.05)} = 0.024603 buyins.
If call & lose: E_lose = 0.
If fold: S_fold = 1.36667.
E_fold = 0.5364^{log2(250 / 1.36667)} = 0.009269 buyins.

Given B’s hand equity W = 0.36 versus shove range:
EV(call) = W * E_win = 0.36 * 0.024603 = 0.008857 buyins.
Compare to EV(fold) = E_fold = 0.009269 buyins.
Thus EV(call) < EV(fold): folding maximizes expected prize‑EV despite chip‑EV being +137 chips.

**Für den Bot:** Implement a decision layer that uses your estimated C and effective field size k to compute tournament‑EV for each action. In marginal early‑stage all‑ins, this layer will correctly override some chip‑EV calls into folds when you have a large skill edge, and conversely push a losing bot toward higher‑variance calls.

## General placement‑probability model for arbitrary payout structures (sketch)
Approximate probability of finishing in each place i using doubling‑to‑fraction‑of‑chips events, then sum payouts weighted by these probabilities to get expected buyins; this defines an effective k and skill adjustments for arbitrary payout vectors.

**Formel:** Notation:
• X = total number of players.
• N = log2 X = doubles required for winner‑take‑all.
• C = double‑before‑bust probability.
• vi = payout for finishing i‑th (in buyins), i = 1..X.
• pi = probability of finishing exactly in i‑th place.
• qi = probability of finishing in top i (1st through i‑th).

Player’s equity in buyins:
EN = Σ_{i=1}^X (pi * vi).

Approximation assumption:
Chance of finishing in place N equals chance of doubling to 1/N of chips minus chance of finishing in any strictly higher place.

Model for probabilities:
For i > 1:
pi = C^{N - log2 i} - C^{N - log2(i - 1)}.
For i = 1:
p1 = C^N.

Define cumulative probabilities:
qi = Σ_{j=1}^i pj,   i = 1..X.
Then qi is the chance of finishing in top i.

Using these pi, EN can be computed for any payout {vi}, and then an effective field size k can be defined satisfying:
(2C)^{log2 k} = EN
=> k = 2^{ ln(EN) / ln(2C) } (same as earlier).

**Für den Bot:** For full‑featured tournament bots, approximate finish‑position probabilities using the doubling‑to‑1/i‑chips heuristic and then compute EN = Σ pi vi for the real payout structure. Use the resulting EN and effective k to adjust aggression thresholds, particularly around bubbles and pay jumps, instead of relying on chip‑EV or naive ICM alone.

## Incremental prize ladder representation
Represent tournament payouts via incremental step values wi so that various equity formulas simplify and can be re-expressed in terms of probabilities of finishing at least i‑th.

**Formel:** Given total prize pool P, finish‑place payouts v_i (i = 1..N):

P = sum_{i=1}^N v_i

Define incremental ladder values w_i by:
  w_i = v_i - v_{i+1}   for i = 1..N-1
  w_N = v_N

Then we have the identity:
  P = sum_{i=1}^N w_i

Let p_i be probability of finishing exactly i‑th, and q_i = Prob(finish i‑th or better).
Then:
  q_i = sum_{j=1}^i p_j

We can express expected prize equity E in two equivalent ways:
  E = sum_{i=1}^N p_i * v_i
  E = sum_{i=1}^N q_i * w_i

**Für den Bot:** When evaluating deals or ICM-like equity, convert payouts v_i into incremental steps w_i and work with cumulative finish probabilities q_i; this decomposes equity into “prob of surviving to each ladder + value of that ladder,” which is easier to approximate and combine with survival models.

## Theory of Doubling Up with prize structure (effective field size)
Model tournament skill as a constant chance C of doubling each time until winning a winner-take-all field of size k. For structured payouts, derive an effective winner-take-all field size k_eff that produces the same skill sensitivity.

**Formel:** Base Theory of Doubling Up (winner-take-all):
  Let C = constant probability of winning a double-up.
  Let N = log2 X where X is field size (number of starting stacks).
  A player's win probability (skill) is approximately:
    E = C^N.

Structured prize with incremental steps w_i and survival (cumulative) probs q_i:
  Player's prize equity (in buyins) is:
    E = sum_{i=1}^N q_i * w_i.

They solve for k so that tournament behaves like winner-take-all of size k in the doubling-up model. D is the number of doubles needed to reach k players:
  D = log2 k.

They derive (in approximated, log-linearized form using a base C close to 0.5):
  N - D = - sum_{i=1}^N w_i * log_C(w_i)  (heuristic form; text expresses via
            - sum w_i * (log_C C) = (N - D), etc.)

Key operational identity from the excerpt:
  N - D = sum_{i=1}^N w_i * (some function of log_C)

and then effective field size:
  k_eff = X / 2^{N - D}

In their concrete example:
  N - D = 204 / 256
  X = 256
  k_eff = 256 / 2^{204/256} ≈ 147.35
  D = log2 k_eff.

**Für den Bot:** For early/mid stages where future play is long and skill matters, model win probability as C^{log2 X} and adjust X to an effective field size k_eff that accounts for payout flatness: flatter payouts → smaller k_eff → each chip is worth less in terms of amplifying skill. Use a smaller effective field when computing risk-reward of marginal spots in flatter structures.

## Chip fraction and win-probability abstraction
Represent each remaining player by their chip fraction s_i and an associated first-place win probability x_i (which may or may not equal s_i) to feed into tournament equity models.

**Formel:** Given chip stacks S_i for i = 1..n:
  Total chips T = sum_{i=1}^n S_i
  Chip fraction s_i = S_i / T
  sum_{i=1}^n s_i = 1

Define v_j as payout for j‑th place; total pool V, remaining pool with n left V_n:
  V_n = sum_{j=1}^n v_j

Define p_{i,j} = Prob(player i finishes j‑th).
Basic equity formula:
  E[X_i] = sum_{j=1}^n p_{i,j} * v_j

Approximation usually sets x_i ≈ s_i for equal skill:
  x_i := Prob(player i finishes 1st).

Tournament equity models will approximate p_{i,j} in terms of x_i (and other x_k).

**Für den Bot:** Always normalize stacks to chip fractions and feed them into a separate win-probability model x_i (e.g., x_i ∝ s_i^alpha adjusted for skill); all subsequent ICM-style formulas use x_i rather than raw stacks.

## Proportional chip-count equity (basic ICM-like model)
Simplest deal/equity formula: all players are guaranteed min-cash v_n; the remaining prize pool is split proportionally to their chip fractions.

**Formel:** With n players left and payouts v_1 ≥ v_2 ≥ ... ≥ v_n > 0:
  Guaranteed payout for all: v_n
  Remaining prize pool: W_n = sum_{j=1}^n v_j - n * v_n

Let s_i be chip fraction for player i.
Proportional chip-count equity (Equation 27.1):
  E[X_i] = v_n + s_i * W_n

Interpretation: assumes p_{i,j} = s_i for all j, which is inconsistent but yields:
  E[X_i] = sum_{j=1}^n s_i * v_j = s_i * V_n
  (equivalent to v_n + s_i W_n).

**Für den Bot:** The proportional chip-count formula (ICM in its most naive form) systematically overvalues big stacks (especially when one stack is huge). A NLHE bot should not rely on pure proportional chip equity when modeling bubble/FT risk; it should treat these values as an upper bound for big-stack equity and recognize their bias.

## Landrum–Burns equity model
Model where a player has win probability x_i; if he does not win, his finishes in the remaining places are assumed equally likely. This produces another simple closed-form equity formula.

**Formel:** Let there be n players left, payouts v_1..v_n, and player i has probability x_i of finishing 1st.
The Landrum–Burns model assumes:
  p_{i,1} = x_i
  Conditional on not winning, i is equally likely to finish in any of places 2..n:
    For j = 2..n:
      p_{i,j} = (1 - x_i) / (n-1)

Then expected prize equity:
  E[X_i] = x_i * v_1 + (1 - x_i)/(n-1) * sum_{j=2}^n v_j

In the text’s notation 27.2 they re-express it in terms of v_1 and remaining pool, but the above is the core probability model.

**Für den Bot:** Landrum–Burns underestimates the edge of the big stack and overvalues short stacks (it spreads non-win outcomes uniformly over 2..n). A bot can use it as a lower bound on big-stack equity and an upper bound on short-stack equity when bracketing fair deal values or sanity-checking more expensive models.

## Malmuth–Harville (horse-race-style) tournament model
Generalizes Harville’s horse-racing formula: given win probabilities x_i for each player, the chance of finishing in j‑th place, conditional on some ordering of previous finishers, is proportional to remaining x_i values. This yields more realistic finish distributions, especially for large stacks.

**Formel:** Let players be indexed 1..n with win probs x_i, sum x_i = 1.

Given that some set of players {k_1,..,k_{j-1}} have finished in positions 1..j-1, the conditional probability that player i (not in that set) finishes j‑th is:

  P(i finishes j | k_1 first, k_2 second, ..., k_{j-1} (j-1)th)
    = x_i / sum_{m not in {k_1,..,k_{j-1}}} x_m

(Equation 27.3)  For j = 2 explicitly, conditioned on k winning first:
  P(i finishes 2nd | k 1st) = x_i / (1 - x_k),   for i ≠ k.

Unconditional probability of finishing 2nd:
  p_{i,2} = sum_{k≠i} P(i 2nd | k 1st) * P(k 1st)
          = sum_{k≠i} [ (x_i / (1 - x_k)) * x_k ].

More generally, p_{i,j} is the sum over all permutations of who finishes ahead of i of the product of these conditional ratios.

Equity:
  E[X_i] = sum_{j=1}^n p_{i,j} * v_j.

This is exact under the model once x_i are specified.

**Für den Bot:** Given a reliable model for each player’s chance of winning (x_i), Malmuth–Harville yields a principled finish distribution that strongly favors big stacks to also place highly if they do not win. A bot can precompute this for small n (e.g., 3–6 handed) and use it for accurate final-table or SNG equity calculations rather than naive chip-count or Landrum–Burns approximations.

## Malmuth–Weitzman bust-probability model (ICM-like near the money)
Assumes when someone busts, their chips are spread equally (in expectation) among all opponents. This leads to a system of linear equations whose solution implies each player’s probability of busting next is proportional to the inverse of his win probability (or chip count).

**Formel:** Let x_i be each player’s win probability (can be proxied by chip fractions), and let p_{i,n} be probability that player i busts next (i.e., finishes n‑th with n players left). Malmuth–Weitzman start from:

For each player i:
  p_{i,n} = sum_{k≠i} p_{k,n} * E[Prob(i busts when k busts and his chips are shared)]

Solving the resulting Vandermonde system yields:

  Define
    b = sum_{k=1}^n (1 / x_k)

  Then the solution is:
    p_{i,n} = (1 / x_i) / b

Equivalently:
  p_{i,n} ∝ 1 / x_i.

If x_i ∝ s_i (chip fraction), then:
  p_{i,n} ∝ 1 / s_i.

So the immediate bust probability is inversely proportional to stack size.

Once p_{i,n} are known, we can recursively compute finish probabilities and equity, but the text focuses on this key property as the closed-form solution of the system.

**Für den Bot:** Near the bubble or when only a few ladders remain, model next-out probabilities as inversely proportional to effective stack (or win probability): short stacks bust much more often. This gives a tractable baseline ICM model for deal-making and bubble decisions that is more realistic than pure chip count and easier to approximate in real time than full Harville permutations.

## Basic tournament equity expectation formula
Unified definition of tournament equity as expected payout over finish distributions; any model (chip-count, Landrum–Burns, Harville, Weitzman, Doubling-Up) is just a specific way of generating the p_{i,j}.

**Formel:** Core definition:
  Let p_{i,j} = Prob(player i finishes in place j) for j = 1..n.
  Let v_j be payout for j‑th.

Then tournament prize equity for player i:
  E[X_i] = sum_{j=1}^n p_{i,j} * v_j.

Alternate using incremental w_j and cumulative q_{i,j}:
  w_j = v_j - v_{j+1} for j = 1..n-1; w_n = v_n.
  q_{i,j} = Prob(player i finishes j‑th or better) = sum_{k=1}^j p_{i,k}.

Then
  E[X_i] = sum_{j=1}^n q_{i,j} * w_j.

**Für den Bot:** All tournament models reduce to generating a plausible finish-distribution p_{i,j} from stacks and skills, then taking E = Σ p_{i,j} v_j. A NLHE bot should cleanly separate (1) its model for p_{i,j} (ICM variant, doubling-up, or learned) from (2) the payoff calculation; swapping the model changes risk preferences without touching the payoff code.

## Normalized tournament win rate ω
Maps raw expected dollar (or buy‑in) profit in a tournament to a dimensionless win rate in units of tournament ‘size’ (average prize/buy‑in).

**Formel:** Definitions:
V  = total prize pool
vi = fraction of prize pool for i‑th place, so Vi = vi * V
s  = V / n  = tournament size (average prize pool per entrant)
bc = total cost per player to enter (buy‑in + fee)
εb = bc − s (house fee minus any added money)

Expected gross payoff per tournament:
<E[X]> = − Σ_i Vi / n = − Σ_i (vi * V / n)

Net expectation per tournament:
w = <X> − bc
w = − Σ_i Vi / n − s − εb

Normalized win rate ω:
ω ≡ w / s
= − Σ_i (Vi / (n s)) − 1
Since s = V / n and vi = Vi / V, we get:
ω = − (n / V) Σ_i (Vi / n) − 1
ω = − Σ_i vi − 1
So, in the model where Σ_i vi = 1 (entire prize pool paid out):
ω = −(Σ_i vi − 1) = 0 if rake/fees ignored.

In the specific modeling in the text (rewritten directly):
ω = −(n Σ_i vi / n − 1) = −(n Σ_i vi − 1) vi

[Operationally, in practice you compute w in buy‑ins and then]
ω = w / s.

**Für den Bot:** Track win rate in *normalized buy‑ins per tournament* (ω = EV / average prize/entry), not just ROI; this ω plugs directly into the variance and confidence‑interval formulas below.

## Normalized outcome Z per tournament
Center and scale each tournament result by the tournament ‘size’ so that its mean is the normalized win rate ω; this is the basic random variable for tournament‑sequence statistics.

**Formel:** Definitions:
X  = gross return from the tournament (in buy‑ins)
bc = total cost per tournament (in buy‑ins)
s  = tournament size (average prize pool per entrant, in buy‑ins)

Net single‑tournament outcome in buy‑ins:
x = X − bc
Mean net outcome:
μ = E[X − bc]

Normalized single‑tournament outcome:
Z = (X − s) / s

Special property:
E[Z] = ω

Variance of Z derived in the text (under their finish‑probability model):
Var(Z) = σ_Z^2 = [n Σ_i v_i^2 − 1 − ω] (1 + ω)

where
k ≡ n Σ_i v_i^2  (tournament variance multiple, see next item)
So:
σ_Z^2 = (k − 1 − ω)(1 + ω).

**Für den Bot:** Store each tournament’s result as Z = (payout − average‑prize)/average‑prize; then sample means of Z directly estimate ω with correctly scaled variance.

## Tournament variance multiple k from payout structure
k captures how top‑heavy the payout is; it directly determines the per‑tournament variance of normalized outcomes and the sample‑size needed for reliable win‑rate estimates.

**Formel:** Let vi be the fraction of the prize pool awarded to i‑th place (Σ_i vi = 1 over all paid places).
Define:

k = n Σ_i vi^2

In the simplified ‘equal skill then tilt by ω’ model in the text, they use (dropping the factor n explicitly in numerics):

k = Σ_i vi^2

(Their numeric examples quote k as Σ_i vi^2; operationally it is the same quantity that goes into Var(Z).)

Per‑tournament variance of Z:
σ_Z^2 = (k − 1 − ω)(1 + ω)

For ω ≪ k, they approximate:
σ_Z^2 ≈ k − 1.

**Für den Bot:** From the payout vector v, compute k = Σ vi². Use k (typically ≫1 for top‑heavy MTTs) to set your prior on how noisy tournament results will be and how many tourneys you need before trusting ROI estimates.

## Per‑tournament variance of normalized outcome Z
Given win rate ω and payout‑derived k, obtain a model‑based variance for a single tournament’s normalized outcome Z; this is more reliable than using raw sample variance for modest sample sizes.

**Formel:** Per‑tournament variance of net profit x = X − bc:
Var(x) = E[(X − bc)^2] − (E[X − bc])^2

Under the model with
P(finish in i‑th place) = (1 + ω) / n
and the ω‑tilt approximation used in the book, the derived variance of Z is:

σ_Z^2 = Var(Z) = (k − 1 − ω)(1 + ω)

where
k = Σ_i vi^2 (tournament variance multiple from payout fractions)

For realistic ω (ω ≪ k):
σ_Z^2 ≈ (k − 1)(1 + ω) ≈ k − 1.

**Für den Bot:** Instead of using noisy empirical variance over a small sample, derive per‑tournament variance of Z from the structure: σ_Z² ≈ (k−1)(1+ω). This stabilizes confidence intervals on your true win rate.

## Variance of sample mean of Z over m tournaments
Gives the variance of the observed average normalized outcome over m independent tournaments, using the structure‑based variance rather than raw sample variance.

**Formel:** Let Z_j be independent normalized outcomes for m tournaments, each with mean E[Z_j] = ω and per‑tournament variance σ_Z^2.
Define sample mean:
M = (1/m) Σ_{j=1..m} Z_j
Then:
Var(M) = Var( (1/m) Σ Z_j ) = σ_Z^2 / m

Plugging in σ_Z^2 from above:
Var(M) = [(k − 1 − ω)(1 + ω)] / m

In practice, the text emphasizes ω ≪ k, so:
Var(M) ≈ (k − 1)/m

They summarize (Equation 27.6):
Var(sample mean of Z over m tourneys) ≈ (k − ω)(1 + ω) / m ≈ k / m.

**Für den Bot:** When aggregating results over m tourneys, give the sample mean Z a variance ≈ k/m instead of using naive binomial/normal assumptions; this correctly reflects how top‑heavy structures hugely slow convergence of ROI estimates.

## Estimating k from observed win rate and variance for large m
When the sample size is large, invert the variance relationship to estimate the effective k from observed data instead of from the theoretical payout vector.

**Formel:** Given:
ω_R  = observed normalized win rate over the sample
s_R^2 = observed variance of Z over tournaments in the sample

They propose estimating k via:

k = (ω_R + s_R^2) / (1 + ω_R)

This k can then be plugged back into the win‑rate‑based variance formula:

**Für den Bot:** For huge hand histories where empirical variance is stable, back‑solve k ≈ (ω_R + s_R²)/(1+ω_R) to calibrate your variance model to the actual field instead of relying only on the nominal payout table.

## Hypothesis test: excluding too‑high win rates using (one‑sided) normal approximation
Use a z‑score (under approximate normality of the sample mean of Z) to rule out unrealistically large underlying ω when the observed ω_R is much lower; skew is positive, so this one‑sided test is conservative.

**Formel:** Let ω be a *candidate* true normalized win rate.
Let ω_R be the observed sample mean of Z over m tournaments.
Let Var(ω_R) ≈ Var(M) from above, call its square‑root σ_M = sqrt(Var(M)).

Define z‑score:
T = (ω_R − ω) / σ_M

If T < −2, then ω fails a 95% confidence test for being the true win rate (one‑sided, in the sense that ω is too high to be consistent with observing ω_R that low).

Because the underlying distribution is skew‑positive, the probability of a negative deviation of size ≥2σ is smaller than under a normal, so this test is conservative in excluding high ω.

**Für den Bot:** To sanity‑check whether a claimed ROI is plausible, view that ROI as ω, compute T = (ω_obs − ω)/σ_M; if T < −2, you can (very conservatively) reject that high ROI at ~95% confidence even without full normality.

## Chebyshev bound for two‑sided deviation of ω
Use Chebyshev’s inequality to get a distribution‑free bound on how far the true ω can be from the observed ω_R in units of σ_M, robust to skew.

**Formel:** For any random variable with mean μ and variance σ^2, Chebyshev’s inequality states:
P(|X − μ| ≥ t σ) ≤ 1 / t^2

Applied to our context, let M be the sample mean Z (i.e. observed ω_R), true mean ω, variance Var(M) = σ_M^2.
Then for any B > 0:
P(|M − ω| ≥ B σ_M) ≤ 1 / B^2

Taking B = 4 gives:
P(|M − ω| ≥ 4 σ_M) ≤ 1/16

So the probability that the true ω lies more than 4 standard deviations away from the observed sample mean is at most 1/16, regardless of skew.

**Für den Bot:** For very skewed tournament results where normality is dubious, use Chebyshev: treat ±4σ around your observed ω as enclosing the true ω with at least 15/16 probability; this is crude but guaranteed valid without distributional assumptions.

## Game‑of‑chicken analogy for heads‑up jam/fold in tournaments
All‑in confrontations in tournaments are negative‑sum in ICM terms; both players lose some equity simply by risking elimination. This mirrors the game of chicken and shifts equilibrium strategy in favor of the first jammer.

**Formel:** Game of Chicken payoff matrix:

            Player B
           Drive   Swerve
Player A
Drive    (−10,−10) (1,−1)
Swerve   (−1, 1)   (0, 0)

Key equilibria:
1. Mixed: each player drives with prob p chosen so the other is indifferent (standard textbook result, not explicitly solved here).
2. Pure: (Drive_A, Swerve_B) and (Swerve_A, Drive_B) are both Nash equilibria.

Tournament mapping:
• Drive on  ≈ jam all‑in
• Swerve    ≈ fold
• Accident  ≈ all‑in confrontation where both lose ICM equity compared to folding

No explicit closed‑form equilibrium frequencies are given for the tournament case in the excerpt; the key qualitative result is that the confrontation penalty makes the caller’s threshold tighter than in a zero‑sum cash game.

**Für den Bot:** In jam‑or‑fold tournament spots, especially near bubbles, model the situation as negative‑sum: the caller needs *more* equity than in a cash game. Favor strategies where the first‑in player jams slightly wider, and the caller folds slightly more, moving toward a jam/fold equilibrium biased toward the aggressor.

## Bubble calling threshold vs chip-EV threshold (ICM vs cEV)
On the sit-and-go bubble, the equity requirement to call all-in is higher in prize-EV than in chip-EV because chips map nonlinearly to payouts.

**Formel:** Let:
- V_win = prize-equity (in buy-ins or $) if we call and win
- V_lose = prize-equity if we call and lose (typically 0 if we bust on bubble)
- V_fold = prize-equity if we fold
- X = equity (probability) we win the all-in when we call

Prize-EV call condition:
X * V_win + (1 - X) * V_lose > V_fold
If V_lose = 0, this reduces to:
X * V_win > V_fold
Required equity in prize-EV:
X_prize = V_fold / V_win

Chip-EV call condition (ignoring payout structure):
Let S_callwin = stack if we call and win
S_fold = stack if we fold
Let P = pot we can win such that S_callwin = S_fold + P
Call is breakeven in chip EV when:
X_chip * S_callwin + (1 - X_chip) * 0 = S_fold
=> X_chip = S_fold / S_callwin

Example (excerpt 4-handed SNG, 2500 each, 200-400 blinds, SB jams, BB deciding):
Prize-EV approximation:
V_win = 3.75 buy-ins
V_fold = 2.3 buy-ins
X_prize = 2.3 / 3.75 ≈ 0.6133 (61.33%)

Chip-EV:
S_callwin = 5000
S_fold = 2100
X_chip = 2100 / 5000 = 0.42 (42%)

**Für den Bot:** For SNG bubbles, compute a prize-EV equity threshold X_prize = V_fold / V_win that is usually much higher than the chip-EV threshold S_fold / S_callwin; the bot should substantially tighten all-in calling ranges when busting moves it from a paid to an unpaid finish.

## ICM-based required equity in generic bubble all-in spots
Generalization of the bubble calling threshold: use ICM or an approximation to convert stacks into prize equities and solve for the minimum showdown equity needed to call an all-in.

**Formel:** Inputs:
- stacks_before: vector of chip stacks before the hand
- stacks_if_fold: same as stacks_before but with our stack reduced appropriately if we fold (post-blind)
- stacks_if_call_win: vector if we call and win (we get villain's chips)
- stacks_if_call_lose: vector if we call and lose (our stack often = 0, villain gets our chips)

Let:
- ICM(stacks) = vector of prize-equities (in buy-ins, $ or normalized) from some ICM model
- For hero index h:
  V_fold = ICM(stacks_if_fold)[h]
  V_win  = ICM(stacks_if_call_win)[h]
  V_lose = ICM(stacks_if_call_lose)[h]

Call profitable in prize-EV if:
X * V_win + (1 - X) * V_lose > V_fold
=> X > (V_fold - V_lose) / (V_win - V_lose)

So required equity:
X_required = (V_fold - V_lose) / (V_win - V_lose)

Special case (bubble where V_lose ≈ 0):
X_required ≈ V_fold / V_win

**Für den Bot:** Use an ICM (or approximation) layer: for any all-in decision near payout jumps, compute ICM equities in each branch and solve X > (V_fold − V_lose)/(V_win − V_lose); this directly yields the correct (often very tight) bubble calling thresholds.

## Approximate chip value per ladder (bubble mnemonic)
Approximate the chip-equivalent penalty of busting before a payout jump by mapping the $ value of moving up one place into chips.

**Formel:** Let:
- Δ$ = approximate additional payout for moving up one place (e.g., min-cash difference)
- chip_value = total_chips / total_prize_pool (chips per dollar or per buy-in unit)
Then define an effective penalty in chips for busting:
penalty_chips ≈ Δ$ * chip_value^{-1} = Δ$ * (total_chips / total_prize_pool)

When jamming:
Effective lost chips when called and lose ≈ penalty_chips
Effective chip-EV of jam ≈ chip_EV(jam) - P(called and lose) * penalty_chips

**Für den Bot:** As a quick heuristic when full ICM is expensive, treat busting before a significant ladder as losing an extra penalty_chips; subtract P(called and lose)*penalty_chips from standard chip-EV when evaluating jams, which tightens aggression near large jumps.

## SNG bubble: required equity vs jam (one big stack scenario)
In a 4-handed SNG with one big stack jamming, the medium stacks need very high equity to call because busting to 4th is much worse than folding into the money.

**Formel:** Example configuration (excerpt):
Stacks: (5500 / 1500 / 1500 / 1500), blinds 150–300, payouts 5–3–2.
Big stack jams, big blind (one of 1500 stacks) decides.
Approximate prize equities given in book:
- If BB calls and wins (triples to 4500 vs others):
  V_win = (30%) * 5 + (40%) * 3 + (25%) * 2 + (5%) * 0 = 3.2 buy-ins
- If BB folds:
  V_fold = (10%) * 5 + (30%) * 3 + (30%) * 2 + (30%) * 0 = 2 buy-ins
- If BB calls and loses: V_lose = 0

Required equity:
X_required = V_fold / V_win = 2 / 3.2 = 0.625 = 62.5%

Range with ≥ 62.5% vs random: about {66+, A9s+, AT+, KJs+}, ~7% of hands.

**Für den Bot:** On 4-handed SNG bubbles with a dominant chip leader, medium stacks should call all-in extremely tight (e.g., ~7% vs random jam in this setup); implement a mode where calling ranges shrink sharply when losing the pot likely means bubbling.

## SNG bubble: equal stacks jam-or-fold (sequential chicken)
With 4 equal stacks on the bubble, an open-jammer can shove extremely wide because each caller needs very high equity vs random to justify risking bubbling.

**Formel:** Example configuration (excerpt):
Stacks: (2500 / 2500 / 2500 / 2500), blinds 200–400, payouts 5–3–2.
UTG jams blind; three players behind decide to call or fold.
Given approximations:
- If a player calls and wins:
  V_win = (50%) * 5 + (30%) * 3 + (20%) * 2 = 3.8 buy-ins
- If a player folds:
  V_fold = (25%) * 5 + (25%) * 3 + (25%) * 2 + (25%) * 0 = 2.5 buy-ins
- If call and lose: V_lose = 0

Required equity for any caller:
X_required = V_fold / V_win = 2.5 / 3.8 ≈ 0.658 ≈ 65.8%

Hands achieving this vs random: about {77+, AJs+}, ~5% of hands.

Let p_call ≈ 0.05 per player. Neglecting overcalls, probability UTG gets called by at least one:
P_called ≈ 1 - (1 - p_call)^3 ≈ 1 - 0.95^3 ≈ 0.143
So P_uncontested ≈ 0.857: UTG picks up blinds (600) very often.
If UTG's equity when called is as low as ~25%, jamming is still profitable because:
EV ≈ P_uncontested * 600 + P_called * (0.25 * pot_when_called - 0.75 * risk)
will still be positive for wide ranges (as book notes).

**Für den Bot:** In 4-handed equal-stack SNG bubbles, open-jams can be extremely wide while callers must be extremely tight (requiring ~66% equity vs random); a jam-or-fold module should recognize these chicken-game spots and favor aggressive open-shoving with high fold equity.

## Theory of Doubling Up (rebuys/add-ons chip value model)
Approximate a player’s chance to win a tournament and hence the $EV of chips as a function of stack size, skill-adjusted by a per-double probability C of winning an all-in that doubles the stack.

**Formel:** Definitions:
- Total chips in play: T
- Player stack: x
- C = probability of success each time the player attempts to double through equal-opposition all-ins (skill parameter, e.g., C = 0.54)

Number of doubles needed to reach all chips:
N(x) = log2(T / x)

Probability to win tournament (approximate):
P_win(x) ≈ C^{N(x)} = C^{log2(T/x)}

If total prize pool is P_total and winner-take-all (or we care about first-place share):
E(x) ≈ P_total * C^{log2(T/x)}

Example (excerpt):
T = 1,000,000, C = 0.54, P_total = 90,000.
For x = 6000:
N(6000) = log2(1,000,000/6000) ≈ 7.38
E(6000) = 90,000 * 0.54^{7.38} ≈ $953

For x = 7500:
N(7500) = log2(1,000,000/7500) ≈ 7.06
E(7500) = 90,000 * 0.54^{7.06} ≈ $1,162

Value of adding Δx chips:
ΔE ≈ P_total * [C^{log2(T/(x+Δx))} - C^{log2(T/x)}]

Indifference (breakeven) add-on cost A when buying Δx chips:
A = E(x+Δx) - E(x) = P_total * C^{log2(T/(x+Δx))} - P_total * C^{log2(T/x)}
Add-on is good if A_cost < A.

**Für den Bot:** Use the Theory of Doubling Up as a fast heuristic for the marginal value of extra chips in rebuy/add-on decisions: model EV(x) ≈ P_total * C^{log2(T/x)}; if the incremental EV from adding chips exceeds their $ cost, the bot should rebuy/add on, especially when chips are sold at a discount.

## Add-on / rebuy decision rule via Theory of Doubling Up
Given a skill parameter C and tournament parameters, decide whether a rebuy or add-on is +$EV by comparing its cost to the gain in tournament equity predicted by the doubling-up model.

**Formel:** Given:
- T = total chips after all rebuys/add-ons
- current stack x
- add-on size Δx, cost A_cost
- skill parameter C
- prize pool P_total

Compute:
E_no_addon = P_total * C^{log2(T/x)}
E_with_addon = P_total * C^{log2(T/(x+Δx))}

Add-on is profitable if:
E_with_addon - E_no_addon > A_cost

Rearrange for breakeven stack x* where E_with_addon - E_no_addon = A_cost (usually solved numerically).

**Für den Bot:** Implement a rebuy/add-on module: for each offered extra-chip purchase, compute EV gain via the doubling-up model and compare to cost; in common structures with discounted add-ons, a winning bot should nearly always take them regardless of current stack.

## Short-stack jam-or-fold threshold (conceptual, referenced)
When stack-to-blind ratios become small, raising to a non-all-in size often commits you anyway, so the optimal strategy simplifies to jam-or-fold; threshold is where any standard raise size R leaves a remaining stack small relative to pot so that folding later is dominated.

**Formel:** Let:
- effective stack: S
- blinds+antes total preflop: B
- planned raise size: R
After raising, remaining stack: S_rem = S - R
Pot after raise and blinds call: P ≈ B + R + calls

You are effectively committed if, after betting R, any reasonable continuation (e.g., c-bet, call shove) requires putting in most of S_rem, so that fold EV << shove/call EV.

A crude threshold used in practice: if S ≤ k * B (k around 10–15) and any normal raise size R ≈ 2–3B leaves S_rem ≤ pot size on flop, then prefer jam over small raise: jam-or-fold.

No explicit closed-form is given here; it is a structural rule rather than a precise equation.

**Für den Bot:** For effective stacks under roughly 10–15 blinds, disable normal open-raise sizes and switch preflop strategy to jam-or-fold; any raise size that leaves a remaining stack smaller than the ensuing pot should be replaced by an all-in decision node.

## Chip fraction ≈ prize fraction in winner-take-most single-table formats
In single-table shootouts/satellites where generally only first place matters, the fraction of total chips a player holds is approximately proportional to his share of the prize pool, ignoring skill differences.

**Formel:** Let:
- total_chips = T
- player chips = x
- prize pool = P_total (winner take all or nearly so)
Then approximate prize equity:
E(x) ≈ (x / T) * P_total

This is linear chip-to-$ mapping, contrasting with non-linear ICM in SNGs and satellites.

In heads-up match play with stacks S_big and S_small (S_big ≥ S_small), playing a hand for S_small each effectively:
- Expected equity per hand depends only on S_small; extra chips S_big - S_small are irrelevant for that hand's EV.

Equivalent model: any HU hand with stacks (S_big, S_small) is equity-equivalent to (S_small, S_small) for that hand.

**Für den Bot:** In winner-take-most single-table formats and HU matches, treat chip EV as approximately equal to cash EV; a bigger stack should ignore its surplus chips for per-hand decisions and simply maximize chip gain, without bubble-style tightening.

## Supersatellite seat-equity vs pot-equity tradeoff
In supersatellites that award equal seats to top N players, once a stack is comfortably above a qualification threshold, extra chips provide very little additional seat-equity; risking busting against another big stack is massively -EV in seat probability even with strong hands.

**Formel:** Let:
- Probability of winning a seat by folding all hands: p_fold ≈ 1 for a big stack near the bubble
- Probability of winning seat after calling big all-in: p_call = P(win pot) * p_win_given_stack + P(lose pot) * p_lose_given_stack
But p_win_given_stack ≈ 1 (we are huge lock anyway), p_lose_given_stack ≈ 0 (we bust).

So calling with hand H vs villain range V changes seat probability from:
Seat_prob_before ≈ p_fold ≈ 1
Seat_prob_after ≈ P(win showdown(H vs V))

Seat-EV change:
ΔSeat_EV ≈ P(win showdown) - 1 <= 0

Even with AA vs JJ (P(win) ≈ 0.81):
ΔSeat_EV ≈ 0.81 - 1 = -0.19: a 19 percentage point loss in seat probability for negligible gain (already ~100% to win a seat).

Thus correct decision: always fold in such spots, regardless of card strength.

**Für den Bot:** In supersatellites near the bubble, a large stack should almost never contest big pots vs other large stacks; the bot should fold even AA preflop to massive jams when it’s already virtually guaranteed a seat, since extra chips barely increase seat probability while busting is catastrophic.

## Jam-or-fold stack threshold (≈6× preflop pot)
Binary (jam vs small-raise) preflop model where stack size relative to the preflop pot determines whether equilibrium/near-equilibrium play prefers an all‑in jam or a non‑all‑in raise.

**Formel:** Let S = effective stack, P0 = preflop pot (blinds + antes).
Jam‑or‑fold regime is preferred when: S < c * P0, with c ≈ 6.
Equivalent in blinds (no antes, pot = 1.5 BB): threshold ≈ 9 BB (since 6 * 1.5 ≈ 9).

**Für den Bot:** Implement a preflop mode switch: when the effective stack is below ≈6× the preflop pot (≈9 BB without antes), constrain the action set to jam-or-fold; above that, allow smaller open/3‑bet sizings and postflop play.

## Hand-type selection at short stacks (showdown equity vs implied odds)
At low SPR / jam-or-fold depths, the relevant EV is dominated by raw equity when called, not implied odds. The model ranks hands by shove EV ≈ fold EV + P(folds)*pot + P(called)*[equity*final_pot − risk]. This structurally favors high showdown equity and blocker effects over speculative hands.

**Formel:** For a shove with hand h and stack risk R into pot P0 against a calling range C:
EV_shove(h) = P(fold) * P0 + P(call) * (Eq(h, C) * (P0 + R + R_call) − R)

Where:
- P(fold) + P(call) = 1
- Eq(h, C) = equity of h vs caller's range C
- R_call is opponent's matching stack when call occurs.

At small stacks R ≈ R_call and SPR ≈ 1, ranking hands by Eq(h, C) mostly determines shove profitability.

**Für den Bot:** When stack < ≈10 BB, drive preflop ranges via shove-EV computations that depend almost entirely on equity vs realistic call ranges; prioritize hands like T9s and Ax over low suited connectors that rely on implied odds.

## Blocker value in shove/raise decisions
Blockers reduce the density of strong hands in opponents’ ranges, increasing P(fold) to our jams/opens and thus EV. The model is: call-range combination count is scaled by (1 − card_removal_factor); hands with an ace or other key card gain EV via higher fold equity.

**Formel:** Let N_strong be the number of strong-combo holdings in villain’s pre-decision range; holding a blocker card reduces this.

N_strong(blocker) = N_strong(no_blocker) − Δ

Approximate fold probability improvement:
ΔP(fold) ≈ Δ / Total_combos

EV_raise(blocker) − EV_raise(no_blocker) ≈ ΔP(fold) * (preflop pot + dead money) + higher probability we’re against a weaker range when called.

**Für den Bot:** In late position and especially at short stacks, give extra weight to opens/jams containing blockers to the opponent’s continuing range (e.g., Ax, Kx versus a 3‑bet/call or reshove range), as their value is disproportionately driven by increased fold equity.

## Antes and immediate-profit raise threshold
With antes, there is more dead money relative to raise size, making first-in raises profitable with extremely wide ranges if opponents overfold. Immediate profitability is a one-step EV inequality: p_fold * dead − (1 − p_fold) * risk_given_foldout > 0.

**Formel:** Single-street raise model (no postflop realization assumed):

Let:
- B = small blind
- BB = big blind
- a = ante per player
- n = number of players
- R = our raise size
- p = probability everyone folds

Dead money before raising: D = B + BB + n * a
Risk (simple model, ignoring postflop equity): Risk ≈ R

Immediate EV of raise (fold or we forfeit R when called):
EV_raise ≈ p * D − (1 − p) * R

Raise is immediately profitable (with any two cards) if:
EV_raise > 0
↔ p * D > (1 − p) * R
↔ p > R / (D + R)


**Für den Bot:** In ante stages, compute the minimum fold frequency p > R / (D + R); if population folds more than that to your open or steal size, expand to very wide (even any-two) opens in those positions/situations.

## Tournament variance multiplier and effective winner-take-all size
Multi-payout tournaments are modeled via an equivalent winner-take-all game with reduced field size N_eff and a variance multiplier k so that variance and mean buy-in-equivalent outcomes are preserved. Then outcome distribution over a finite series can be approximated by a binomial on the virtual tournaments.

**Formel:** Given:
- True field size: N
- Tournament variance multiplier: k (empirical, depends on structure; for N ≈ 400, k ≈ 72)

Effective winner-take-all field size:
N_eff ≈ N / k  (up to a scaling constant so that 1 buy‑in edge ≈ 1 / N_eff win prob).

If player’s edge is μ = 1 buyin per real tournament, approximate per‑virtual‑tournament win probability:
q ≈ 1 / 36  (example-specific; in general q = μ / k′ for some structure-dependent k′).

For a fixed series of T tournaments, number of ‘virtual wins’ N_w ~ Binomial(T, q):
P(N_w = n) = C(T, n) q^n (1 − q)^(T − n)

Expected total profit in buyins for backer + player combined:
E[profit_total] = μ * T.

Specific backing outcome table (example T = 70, μ = 1):
Backer’s EV in buyins = Σ_n P(N_w = n) * Backer_share(n) ≈ 30.13 (vs 35 if pure 50/50 with no distortions).

**Für den Bot:** For a tournament‑specialist bot, calibrate an approximate variance multiplier k and use a binomial/normal approximation for series results; this is not about hand play, but about backing/BRM and risk reporting for long tournament schedules.

## Backer EV under fixed-duration agreement
Given a fixed number of tournaments T, a mean edge μ (in buyins per tournament), a profit-split rule, and a distribution approximation for total wins, the backer’s EV is the expectation over possible outcome counts after settlement, which is affected by where in the distribution splits occur.

**Formel:** Let:
- T = number of tournaments
- μ = player’s average profit per tournament (buyins)
- q = probability of win in the virtual winner-take-all model
- N_w ~ Binomial(T, q)
- Outcome(N_w) = total profit in buyins from the real structure (function of N_w)
- Backer_share(N_w) = settlement rule mapping profit to backer’s cut

Then backer’s EV in buyins:
EV_backer = Σ_{n=0}^{T} P(N_w = n) * Backer_share(n)

In the example: T = 70, μ = 1; total joint EV = 70 buyins; EV_backer ≈ 30.13 instead of 35 due to skewed payout structure and profit splitting.

**Für den Bot:** For a staking-aware tournament bot or tool, model the backer’s expectation as a function over the distribution of series outcomes; skew from top-heavy payouts plus settling rules (e.g. settle when ahead) shifts EV from backer to player even when the raw per-tourney edge is fixed.

## Effect of ‘settle when ahead’ clause on backer EV
Settlement rules that allow the player to withdraw profits when ahead interact with tournament skew: upward swings are crystallized and withdrawn, while inevitable downswings remain to be borne by the backer, reducing backer EV versus a single terminal settlement.

**Formel:** Let:
- EV_backer_terminal = expected backer profit with settlement only at the end of T events.
- EV_backer_dynamic = expected backer profit with intermediate settlements (e.g. ‘whenever ahead’).

Simulation result (example, T = 70, μ ≈ 1 buyin/tournament):
EV_backer_terminal ≈ 32 buyins (simulation) vs ≈ 30.13 (binomial approximation)
EV_backer_dynamic ≈ 27 buyins

Value of ‘settle when ahead’ clause to player:
ΔEV_player ≈ EV_backer_terminal − EV_backer_dynamic ≈ 5 buyins.

**Für den Bot:** When designing or evaluating staking for a tournament bot, treat ‘settle when ahead’ as a transfer of several buyins’ worth of EV from backer to player over a medium-length schedule; backer-side logic should discount expected returns accordingly.

## Implicit collusion and impossibility of individual exploitation in certain symmetric 3‑player games
In some 3‑player games, two players can adopt fixed, individually exploitable strategies that jointly form an implicit alliance, making it impossible for a third player to gain positive EV, even with full knowledge of their strategies. The model shows that unexploitable play in multiplayer games is not simply a matter of pairwise exploitation; coalition structure matters.

**Formel:** Toy game setup (Example 29.1):
- Three players ante $10: pot = $30.
- One card each; winners are A or K; losers are all other ranks.
- Bet size = $30; one betting round; any bet may be called or folded.
- At showdown: if any player(s) have an A or K, all winners split pot; if no A or K, all remaining players split pot.

Given two opponents with fixed declared strategies:
- Rock (R): check all hands if possible, call bets only with a winner.
- Maniac (M): bet all hands, call all bets.

Hero’s optimal response when holding a loser and facing a bet:
P(neither opponent holds winner | hero has loser) = (43/51) * (42/50) ≈ 0.708.
Call branch EV with loser (risking $30 into $60 pot with 3 players when no winner):
EV_call_loser = 0.708 * $45 + 0.292 * $0 − $30 ≈ $1.87 > 0.

Overall EV across hand types (including antes), even with optimal response:
EV_total ≈ −$0.707 per hand for hero.


**Für den Bot:** In multiway pots or 3‑way games, bot design must account for coalition-like patterns (implicit collusion); locally ‘exploitable’ lines from multiple opponents can jointly create a configuration where the unseated bot cannot gain. Equilibrium reasoning must be genuinely multiplayer, not just pairwise HU approximations.

## [0,1] Dry Side-Pot Game #2: Indifference System
Two live players X and Y each hold a uniform [0,1] hand; third player Z is all‑in for the antes (pot=9 bets). X checks, Y can check or bet 1. This is a one–half‑street limit game with a dry side pot. Equilibrium is defined by three thresholds: X’s call threshold x, Y’s value‑bet threshold y1, and Y’s symmetric bluffing band of width w centered above x. Indifference of X at x and of Y at the bluffing band endpoints determines x, y1, w.

**Formel:** Parameters:
  pot = 9 (so alpha = 1/10 in usual two-player analog).

Definitions:
  x   = X's calling threshold vs a bet.
  y1  = Y's value-bet threshold.
  YB  = Y's bluffing region, of width w, disjoint from [y1,1].
  w   = width of Y's bluffing band.

1) X indifferent to calling at x:
   Expected value of calling with hand x is 0.
   From case analysis (table in the text):
     wx + 10 w (1 – x) = y1
   Simplify:
     wx + 10w – 10wx = y1
     w (10 – 9x) = y1
   => w = y1 / (10 – 9x)

2) Y value-bet indifference at y1 (standard half-street result):
   At y1, Y is exactly indifferent between betting and checking.
   This gives the usual condition that Y value-bets with half the hands X will call:
     y1 = x – y1
   => y1 = (1/2) x

3) Y bluff-band endpoint indifference (upper endpoint y):
   At y (upper bound of bluff region, y > x), Y must be indifferent between bluffing and checking:
   From case analysis:
     x = 9 (y – x) (1 – y)
   Expand:
     x = 9y – 9x – 9y^2 + 9xy
     10x = 9 (1 + x) y – 9 y^2
     9y^2 – 9 (1 + x) y + 10x = 0
   Divide by 9:
     y^2 – (1 + x) y + (10/9) x = 0
   Quadratic solution for y:
     y = [(1 + x) ± sqrt((1 + x)^2 – 4 * (10/9) x)] / 2

   Symmetry: the two roots are the lower and upper endpoints of the bluffing region. Let
     center c = (1 + x)/2
   Then width of bluff band:
     w = distance between roots
       = sqrt((1 + x)^2 – 40x/9)
       = sqrt(x^2 – (38/9) x + 1)
   (The text writes this as w = ((9/40^2) * (1 – x + x^2))^{1/2} up to algebraic rearrangement; numerically same object.)

4) Equate two expressions for w:
   From (1) and (3) with y1 = x/2:
     w = y1 / (10 – 9x) = (x/2)/(10 – 9x) = x / (20 – 18x)
   and
     w = sqrt(x^2 – (38/9)x + 1)

   Solve:
     x / (20 – 18x) = sqrt(x^2 – (38/9)x + 1)

   Numerical solution (from text):
     x ≈ 0.2848
     y1 = x/2 ≈ 0.1424
     c = (1 + x)/2 ≈ 0.6424
     w ≈ 0.0190

Interpretation:
  • Y value-bets with top ~14.2% of hands.
  • Y bluffs with a thin semi-bluff band of width ~1.9% centered around ~0.6424.
  • Alpha for this game (bluff:value frequency ratio in Y’s betting range) ≈ 1/10.
  • X calls only with top ~28.5% of hands.

Key equilibrium conditions summarized:
  w = y1 / (10 – 9x)
  y1 = (1/2) x
  x / (20 – 18x) = sqrt(x^2 – (38/9)x + 1)
  x ≈ 0.2848, y1 ≈ 0.1424, w ≈ 0.0190.

**Für den Bot:** In multiway spots with a dry side pot and an all‑in main pot, the bluff:value ratio (alpha) is reduced and the caller’s MDF drops sharply. The optimal bluffing region can become a thin, separated semi‑bluff band rather than the bottom of the range. A NLHE bot should: (1) drastically tighten calling frequencies facing side‑pot stabs when a third player is all‑in, and (2) restrict bluffs to hands that retain decent equity versus the all‑in (semi‑bluffs), not pure air, because successful folds still have to beat the all‑in hand.

## Side-Pot [0,1] Game #2: Alpha / MDF Relationships
In the dry side-pot [0,1] game with pot 9 and 1-unit bet, the standard two-player alpha=MDF relationships are modified by the presence of the all‑in player Z. Alpha is the ratio of Y’s optimal bluffing density to value density within his betting range. MDF is X’s optimal call frequency vs the bet. The presence of Z lowers X’s MDF versus the same pot and bet size and increases Y’s effective alpha slightly compared to the pure two-player case.

**Formel:** Standard two-player half-street (pot P, bet B):
  alpha_two_player = B / (P + B)
  MDF_two_player = 1 / (1 + alpha_two_player) = P / (P + B)

For P = 9, B = 1 (no third player):
  alpha_two_player = 1 / (9 + 1) = 1/10
  MDF_two_player = 9/10 = 0.9

In Dry Side-Pot Game #2 (with Z all‑in and still contesting the main pot):
  From solved equilibrium:
    Y value-bets top 14.24% of hands (≈0.1424)
    Y bluffs ≈1.90% of hands (≈0.0190)
    X calls ≈28.5% of hands (≈0.2848)

  Effective alpha_side_pot = (bluff frequency) / (value frequency)
                           ≈ 0.0190 / 0.1424 ≈ 0.133 ≈ 1/7.52

  Text notes alpha "would be 1/10" based on the pot/bet ratio, but the actual optimal pure-bluff density is reduced and replaced by semi-bluffs that have equity versus Z.

  Effective MDF_side_pot = X_call_fraction = x ≈ 0.285

Comparison:
  With no all‑in:
    MDF_two_player = 0.9 (X must defend 90% vs bet size 1 into 9).
  With all‑in present:
    MDF_side_pot ≈ 0.285 (X defends only ~28.5%).

Thus, the naive two-player MDF formula P/(P+B) is not valid in this 3-player dry side-pot setting.

**Für den Bot:** Standard two-player MDF = P/(P+B) is not directly applicable in multiway or side-pot situations. In a 9:1 pot:bet scenario, a two-player bot would defend ~90% MDF, but optimal defense vs a side‑pot stab with a third player all‑in can drop to ~28%. A NLHE bot should adjust MDF downward when another player is all‑in and still competing for the main pot, and it should compute defense thresholds from explicit EV equations, not from two-player heuristics.

## Side-Pot [0,1] Game #2: Semi-Bluffing Band Structure
Unlike the standard [0,1] half-street game where the bettor bluffs with the very bottom of his range, the presence of an all‑in player forces Y’s optimal bluffing set to be an interior band above X’s calling threshold x, not raw bottom cards. These are semi-bluffs: they can win both by folds from X and by beating Z at showdown.

**Formel:** Let X's call threshold be x ≈ 0.2848.
Y's value-bet threshold: y1 = x/2 ≈ 0.1424 (top 14.24%).
Y's bluff band:
  Interval [y_low, y_high] with center c and width w:
    c = (1 + x)/2 ≈ 0.6424
    w ≈ 0.0190
    y_low  ≈ c - w/2 ≈ 0.6329
    y_high ≈ c + w/2 ≈ 0.6519

So Y's strategy:
  • Check with [0, y1) (strong checks) and with (y1, y_low) and (y_high, 1] except top region [y1,1] where top part is value-bet.
  • Value-bet with [y1, 1].
  • Bluff only with the narrow interior semi-bluff band [y_low, y_high].

The band is determined by the quadratic indifference condition at its endpoints:
  9y^2 – 9 (1 + x) y + 10x = 0.

The band width w must also satisfy:
  w = y1 / (10 – 9x).

This structure is qualitatively different from the two-player [0,1] game where the optimal bluff region is typically [0, y0] (bottom of the range).

**Für den Bot:** In multiway/all‑in main‑pot spots, optimal bluffs often come from medium-strength hands that block strong ranges and retain showdown equity versus the all‑in, not from pure trash. A NLHE bot should favor semi‑bluffs (e.g., draws or hands that can beat the all‑in’s range) over pure air when stabbing at a dry side pot, and it should allow for non‑contiguous betting regions in its policy (interior bluff bands), rather than forcing monotone bet thresholds.

## Dry Side-Pot Game #1: Zero-EV Bluffing and Equity Transfer
In the stud dry side-pot game #1, Y either has a straight flush or air versus X’s exposed aces and Z’s exposed kings. Z is all‑in and cannot change his play. In Nash equilibrium, Y never bluffs because successful folds of X do not change who wins the pot (Z always wins unless Y has the straight flush). However, if Y bluffs anyway, even at zero direct EV, he can transfer equity between X and Z. X can respond by deviating from equilibrium (calling some bluffs) to reclaim equity, which inadvertently gives Y positive EV via extra calls when Y has value.

**Formel:** Game description:
  • Pot = P bets, limit river bet size = 1.
  • X has AAAAA and cannot improve.
  • Z has KKKK and is all‑in for P (no further action possible).
  • Y either has a straight flush (always wins if bets and is called) or a pure bluff (always loses to Z if checked down or if X folds).

Equilibrium logic:
  • If Y bluffs (bets) and X folds, Z wins pot P regardless.
  • Y never gains from bluffing: his EV when bluffing is always −1 (the bet) or 0 depending on protocol, but never >0.

Thus, Nash equilibrium:
  • Y value-bets all straight flushes.
  • Y never bluffs.
  • X always folds to a bet.

Deviations:
  • If Y starts bluffing with frequency b>0:
      – X folds: Z captures additional equity that would otherwise be shared between X and Z when X has the best of it.
      – X may then deviate, calling fraction c of bets to protect his equity vs Z.
  • Once X calls with positive frequency, Y now receives additional call volume on his value bets.

Qualitative EV relationships:
  • EV_Y (vs equilibrium) increases with c as long as some b>0, because the extra calls are more often vs value than vs bluffs.
  • EV_X recovers part of the equity stolen by Z when he starts calling, but pays off Y's value bets and thus transfers some of that recovered equity to Y.

No simple closed-form EV is given in the text; only the monotonic relations:
  • d EV_Y / d c > 0 for b>0.
  • d EV_Z / d b > 0 when X plays equilibrium, because more bluffs that fold out X redirect equity to Z.


**Für den Bot:** Bluffing into a dry side pot can be zero or negative EV individually but still useful strategically because it changes how equity is split between opponents. A NLHE bot should recognize that: (1) pure bluffs into dry side pots versus a capped all‑in are often bad in isolation, but (2) occasional side‑pot aggression can induce other players to defend more, increasing call frequency on future value bets. For learning and exploitation modules, the bot should model not just immediate EV but how its bluff frequency affects other players’ incentives and alliances in multiway pots.

## Clairvoyant Maniac Game: Multi-Equilibria and Alliance Conditions
Three-player half-street game: X and Y have symmetric hands and can only check/call/fold, Z is clairvoyant and can bet 1 into a 9-unit pot. Nash equilibria form a continuum: any strategy profile where Z’s bluff:value frequency makes X+Y indifferent to calling and Y never overcalls X’s call is an equilibrium. Deviating by over‑ or under‑bluffing changes which implicit alliance forms (X+Z vs Y, or Y+Z vs X) and can increase Z’s EV when opponents exploit him.

**Formel:** Game description:
  • Pot = 9 units.
  • Z can bet 1 unit or check, knowing all hands.
  • X acts first vs Z’s bet (call or fold); Y acts after X (call or fold) but never raises.
  • X and Y have symmetric, i.i.d. hands (details abstracted).

Equilibrium conditions:
  • Let p_v = prob(Z value-bets when ahead).
  • Let p_b = prob(Z bluffs (bets when behind)).
  • Let r = p_b / p_v (bluff:value ratio = alpha).

  Nash equilibrium constraints:
  1) Total fraction of the time Z gets called (by X or by Y when X folds) must be 9/10.
     This is the standard condition making Z indifferent to bluffing when bet size = 1 and pot = 9:
       alpha_eq = r_eq = 1/10.
     That is, in equilibrium, Z bluffs 1/10 as often as he value-bets.

  2) Y never overcalls when X has already called (because of pot odds):
     When Z value-bets:
       – Y loses 1 unit by overcalling.
     When Z bluffs:
       – By overcalling, Y wins a net of 5 units (splits a 10-unit final pot, but pays 1 to call).

     If Z bluffs with equilibrium frequency r_eq = 1/10, the overcall EV for Y is:
       EV_overcall(Y) = (prob bluff) * (+5) + (prob value) * (−1)
                      ∝ r_eq * 5 + (1) * (−1)
                      = (1/10)*5 − 1 = 0.5 − 1 = −0.5 < 0.
     So overcalling is −EV at equilibrium; hence Y should not overcall.

Example candidate equilibrium:
  • X calls fraction f_X = 0.5 of the time.
  • Y calls fraction f_Y = 0.8 when X folds and 0 when X calls.
  • Z bets all value hands and bluffs with r_eq = 1/10.
  This mixture maintains:
    – Z gets called 9/10 total across both opponents.
    – Y never overcalls.

Deviations and alliances:
  Case 1: Z slightly increases bluff frequency to r1 = 1/8.
    • X’s best response: call 100% of the time vs bets (since bluff rate is higher than equilibrium, calls profitable).
    • Y still has −EV to overcall because r1 is still small.
    • Resulting alliance: X+Z vs Y (Y gets squeezed).
    • But overall for Z this is worse than equilibrium: extra failed bluffs cost him more than he gains from extra call volume.

  Case 2: Z severely overbluffs at r2 = 3/10 (three times equilibrium frequency).
    • X again best-responds by calling always.
    • Y now has +EV to overcall:
        Prob(Z bluff | bet and X call) = 3/13
        Prob(Z value | bet and X call) = 10/13
        EV_overcall(Y) = (3/13)*5 + (10/13)*(−1)
                        = 15/13 − 10/13
                        = 5/13 > 0.
    • So Y should now overcall.
    • Z’s EV per value-bet outcome:
        – When value-betting (10/13 of bets), he collects 2 units (call + overcall).
        – When bluffing (3/13 of bets), he loses 1 unit.
        Expected net per value-bet cycle:
          EV_Z ≈ (10/13)*2 − (3/13)*1 = (20 − 3)/13 = 17/13 ≈ 1.3077 units.
        Compare to equilibrium EV per value bet: 9/10 = 0.9 units.
        So Z gains substantially by overbluffing when both X and Y optimally exploit the deviation.

Alliance interpretation:
  • At equilibrium (r = 1/10): no stable alliance; everyone best-responds.
  • Mild overbluff (r = 1/8): X+Z de facto alliance versus Y (X calls more, Y never overcalls).
  • Heavy overbluff (r = 3/10): Y+Z de facto alliance versus X (Y overcalls, increasing Z’s value-bet EV despite his extra bluff losses, and X is the one leaking most equity).


**Für den Bot:** In three-player pots, there can be whole families of Nash equilibria characterized by aggregate call frequencies rather than unique individual strategies. A player with positional or informational advantage (like Z) can intentionally overbluff to change opponents’ incentives and thereby form implicit alliances that increase his own EV. A NLHE bot should: (1) treat multiway bluff frequencies as tools to manipulate which opponent defends and how often, not just as two-player alpha choices; (2) anticipate that severe overbluffing can be profitable if it induces both a call and an overcall from different players; and (3) explicitly model overcall EV (second caller’s pot odds) when choosing how often to bluff in multiway spots.

## General Multiplayer Lessons: Nash vs. Exploitative Disturbances
In multiplayer non-zero-sum games, Nash equilibrium strategies exist but need not be unique. A single player can deviate from Nash (e.g., by overbluffing) to induce profitable changes in other players’ best responses, forming implicit alliances. The deviator can gain EV without counter-exploiting, which is impossible in two-player zero-sum settings. Equity transfers can occur between opponents when one player’s actions change who contests which pots.

**Formel:** General statements (no single closed form):

1) Nash equilibrium in multiplayer:
   A profile of mixed strategies (s_X, s_Y, s_Z, ...) is a Nash equilibrium if for all players i:
     EV_i(s_i, s_{−i}) ≥ EV_i(s'_i, s_{−i}) for all alternative strategies s'_i.

2) Disturbance by overbluffing:
   Let s be a Nash equilibrium.
   Let player j change to s'_j by increasing bluffing frequency.
   Let other players k∈K best-respond with BR_k(s'_j, s_{−{j,k}}).

   It is possible in 3+ player games that:
     (i) EV_j(s'_j, BR_{−j}) > EV_j(s_j, s_{−j})
     (ii) EV_k(s'_j, BR_{−j}) ≥ EV_k(s_k, s_{−k}) for some k
     (iii) The remaining equity shift is borne by other players (non-zero-sum).

3) Equity transfer via side-pot bluffs:
   Let E_XZ be equity split between X and Z when play is checked down.
   If Y introduces a bluff with frequency b that causes X to fold when X>Z>Y:
     • Z’s equity increases by roughly b * Prob(X>Z>Y) * P_main.
     • X’s equity decreases by same amount.
     • Y’s direct EV of those bluffs can be ≤0.

   If X responds by calling fraction c of Y’s bets:
     • Y’s value bets gain additional EV proportional to c * value_frequency.
     • X recovers some equity versus Z when he correctly calls bluffs.

No explicit singleton formula; these are structural relationships describing how changing one player's strategy re-allocates equity in a non-zero-sum game.

**Für den Bot:** In multiway NLHE, ‘optimal’ (Nash) play is not uniquely defined and can be less relevant than how deviations shift incentives and alliances. A bot should: (1) maintain explicit models of each opponent’s response to changes in its own bluff/value mix; (2) recognize that profitable deviations can increase its EV by changing how opponents share equity with each other (even when individual bluffs are break-even); and (3) avoid assuming that two-player equilibrium concepts (like a single alpha or MDF) extend unchanged to 3+ players.

## Jam-or-fold 10BB equilibrium shove frequency
In a symmetric, heads-up, winner-take-all jam-or-fold toy game with 10 blind stacks, the equilibrium strategy has the button open-jamming about 58.3% of hands. This is derived from solving a two-player zero-sum game where each player’s decision is purely shove-or-fold / call-or-fold, and ranges are constrained by mutual indifference.

**Formel:** No closed-form formula is given in the excerpt; the 58.3% is a solved numerical equilibrium point for a specific jam-or-fold game instance with 10 blind stacks.

In general, for a jam-or-fold model with effective stack S (in blinds), blinds and antes encoded in pot size P0 pre-jam, and button shove frequency f, BB call frequency g, and equity of shoving range vs calling range E[eq], the indifference conditions take the form of:

1) Button indifferent between shoving and folding with marginal shove hand H*:
EV_button_shove(H*) = EV_button_fold(H*)

2) BB indifferent between calling and folding with marginal bluff-catcher hand B*:
EV_BB_call(B*) = EV_BB_fold(B*)

where (schematically)

EV_button_shove(H*) = (1 - g) * P0 + g * [ eq(H* vs BB_call_range) * (P0 + S) - (1 - eq(H* vs BB_call_range)) * S ]
EV_button_fold(H*) = 0 (if folding sacrifices only current investment)

EV_BB_call(B*) = eq(B* vs btn_shove_range) * (P0 + S) - (1 - eq(B* vs btn_shove_range)) * S
EV_BB_fold(B*) = - (BB_blind_already_posted)

Solving these coupled equations over ranges (integrating or summing over hand equities) yields optimal shove and call frequencies such as the 58.3% shove frequency quoted for 10BB.

**Für den Bot:** For 8–12BB effective stacks in HU or near-HU NLHE, the equilibrium open-shove frequencies are much higher than most humans use; a default 10BB SB/BUTTON strategy should be aggressively jam-heavy (on the order of ~55–60% of hands) rather than raise/folding a lot, and your calling ranges must be set via indifference, not intuition, to avoid being overfolded and exploited.

## MDF / over-aggression tradeoff in jam-or-fold defense
In the jam-or-fold toy game, folding too much as the defender is much more costly than calling a bit too wide, because folding yields the entire pot to the aggressor, while an extra losing call only burns one extra stack. This is the same logic as Minimum Defense Frequency (MDF) in multi-street models: there is a lower bound on how often you must continue to prevent the bettor’s automatic profit.

**Formel:** In a single-street bet/fold-or-call toy model with pot P and bet size B (B risked to win P):

• Bluffing player’s risk/reward ratio: alpha = B / (P + B)
• Caller’s Minimum Defense Frequency (MDF), assuming calls are 0-EV with marginal bluff-catchers:

MDF = P / (P + B) = 1 - alpha

In a jam-or-fold model with pot P0 and shove size S:

alpha_jam = S / (P0 + S)
MDF_jam = P0 / (P0 + S)

If defender folds more than MDF_jam vs a shove (i.e., continues less often), then the shover can profitably jam a very wide or even 100% range.

**Für den Bot:** Do not overfold to large bets or shoves; compute MDF from pot and bet size and ensure your continuing range (call+raise) frequency is at least MDF unless you have a strong population exploit, especially in short-stack all-in spots where giving up the pot entirely is very expensive.

## Balanced betting: fixed bluff:value ratio vs total frequency
In the half-street [0,1] game, the second player can change his total betting frequency while maintaining the same bluff:value ratio. This preserves unexploitable balance (opponent is still indifferent with bluff-catchers) but may sacrifice EV by missing value bets. Thus, balance is defined at the strategy level (ratios within an action), not at the absolute frequency level, and is distinct from optimality.

**Formel:** In a generic one-street bet-or-check toy model with pot P and bet B, suppose the bettor’s betting range has:

v = fraction of total hands in the value-bet subset
b = fraction of total hands in the bluff subset

The bluff-to-value ratio r is:

r = b / v

Indifference for the caller’s marginal bluff-catching hands imposes the classic ratio:

r* = B / (P + B) = alpha

If the bettor scales (v, b) to (k * v, k * b) for 0 < k <= 1, then:

b' / v' = (k * b) / (k * v) = b / v = r

so the opponent’s best-response calling frequency (driven by r) is unchanged. The strategy remains balanced (unexploitable) but generally becomes suboptimal in EV when k < 1 because fewer strong hands are value-betting.

**Für den Bot:** Maintain correct bluff:value ratios for each bet size to avoid exploitation, but also push your absolute betting frequency up with strong hands; betting too rarely even with correct ratios is balanced but leaves a lot of value (and fold equity) on the table.

## Action-level distributions and information hiding
A balanced strategy assigns *distributions of hands* to each action such that each opponent response benefits some part of that distribution. For a raise, your range must contain hands that benefit from villain folding (bluffs/semi-bluffs), calling (medium strength/nut draws), and reraising (strong hands) so that villain cannot profit by skewing their responses. This is a structural constraint on the mapping from private hands to public actions.

**Formel:** Let an action A (e.g., turn raise) induce an opponent response R ∈ {fold, call, reraise}. Let your range for action A be partitioned as:

R_A = H_fold ∪ H_call ∪ H_reraise

where:
• H_fold = subset of hands that gain most when villain folds to A
• H_call = subset that gain most when villain calls A
• H_reraise = subset that gain most when villain reraises over A

Balance conditions (informal structural constraints):

1) For any pure response r ∈ {fold, call, reraise}, your expected value with R_A is not strictly worse than vs any mixed response; i.e., villain cannot increase their EV by deviating to a pure response.

2) Information hiding: The conditional distribution over hand strengths given action A is sufficiently mixed, i.e., P(hand ∈ H_fold | A) > 0 and P(hand ∈ H_reraise | A) > 0, etc., so that observing A does not give villain a near-degenerate posterior on your hand strength.

These constraints are enforced in practice by choosing frequency weights p_fold, p_call, p_reraise over the hand subsets that satisfy (approximate) indifference and prevent obvious exploits, rather than by a simple closed-form formula.

**Für den Bot:** For every raise line in your strategy tree, ensure your raising range contains strong value, medium strength, and bluff/semi-bluff components in calibrated proportions so that any of villain’s options (fold/call/raise) benefits some slice of your range; don’t build one-dimensional ranges (like only bluffs or only nuts) for a given action.

## Multi-street ratio preservation (clairvoyant-style betting)
In the clairvoyant and [0,1] toy games, optimal play across multiple streets often consists of betting each street with a fixed bluff:value ratio, then dropping a fraction of bluffs on each later street. In NLHE terms, this means planning your flop/turn/river lines so that your value-to-bluff ratios per bet size remain near the one-street optimum on each street, given how the tree has pruned.

**Formel:** On any given street s with pot P_s and bet size B_s, the one-street optimal bluff:value ratio for that bet size is:

r_s* = B_s / (P_s + B_s)

In a simplified two-street model (turn, river), suppose:

• Turn pot P_T, turn bet B_T  → r_T* = B_T / (P_T + B_T)
• River pot P_R, river bet B_R → r_R* = B_R / (P_R + B_R)

Let V_T and BL_T be counts (or measure) of value and bluff combos that bet turn.

Balance constraints:

BL_T / V_T ≈ r_T*

On the river, after some bluffs have given up and some value has improved/changed, let V_R, BL_R be the bet river combos; then:

BL_R / V_R ≈ r_R*

Subject to these ratio constraints, the optimal strategy chooses which bluff candidates to continue or give up so that the EV of marginal bluff combos is near 0 (indifference) while strong value always continues.

**Für den Bot:** Plan flop/turn/river ranges so that, conditional on taking an aggressive line, you maintain approximate B/(P+B) bluff:value ratios per street and per bet size; this implies you should systematically drop some weaker bluff candidates on later streets while always preserving enough bluffs with your value to keep opponents indifferent.

## Strategic commitment and option reduction (short-stack preflop)
With stack-to-pot ratios near 1 (e.g., 9 BB effective after raising to 3BB from 9 BB), raising smaller than all-in commits you to calling a shove while giving opponents more options (flat/call/shove) and realizing their equity advantage. In toy-game terms, choosing an action that leaves yourself indifferent (or forced) next node but gives villain more branches is typically dominated by collapsing branches (jamming) so that only one decision remains for villain.

**Formel:** Consider tournament stacks in blinds:

• Hero stack S
• Blinds SB, BB, pot P0 = SB + BB (ignoring antes)
• Hero open-raises to R < S on button.

If Hero’s plan is to always call a shove (i.e., their continuation frequency after raising is 100%), then the EV of raising to R with hand H vs jamming with the same hand can be approximated by:

EV_raise(H) = p_fold_pre * P0 + p_call_pre * [EV_postflop_with_S-R_stack] + p_shove_pre * EV_vs_shove(H | invested R)

EV_jam(H) = p_fold_allin * P0 + p_call_allin * EV_showdown(H | all-in)

where p_fold_pre, p_call_pre, p_shove_pre are villain’s probabilities of folding/calling/shoving vs raise R, and p_fold_allin, p_call_allin are the simpler all-in reactions.

In jam-or-fold toy treatments, with SPR small (S ≈ 10 BB), analysis typically finds EV_jam(H) ≥ EV_raise(H) when Hero is effectively pot-committed, because:

• Opponent’s ability to flat-call and realize equity with middling hands is reduced.
• Hero avoids playing postflop with an awkward SPR < 1 and capped action space (cannot fold but still has future decisions).

There is no elementary closed-form "always jam" threshold; it’s a dominance relation between trees: a 2-node tree (jam/fold) vs a larger branching tree (raise to R → flat/shove/fold) under commitment assumptions.

**Für den Bot:** With ~8–12BB in tournaments, prefer jam-or-fold preflop strategies on the button/SB rather than small opens that pot-commit you; when your continuation frequency after raising is essentially 100%, collapsing the decision tree into a single shove is strategically superior and matches jam-or-fold equilibrium models better.

## Reading your own range (self-distribution tracking)
In equilibrium analysis, the opponent’s hand distribution is irrelevant except in the initial deal; optimal play is defined purely in terms of the mapping from your private hand distribution to your actions. The strategic object is your range at each node, conditioned on previous actions. Thus, ‘reading your own hand’—maintaining the posterior distribution of your own possible hole cards given your past actions—is central to constructing balanced, aggressive lines.

**Formel:** Let H be the finite set of hole-card combos you can be dealt.

At node t with public history h_t (actions and board cards), define your range as a conditional distribution:

pi_t(h) = P( hand = h | public_history = h_t, your_strategy ) for h ∈ H

Your mixed strategy at node t is a mapping:

a_t(h) ∼ sigma_t(· | h, h_t)

where sigma_t is a distribution over available actions A_t (e.g., {fold, call, bet_small, bet_big}).

Balance and aggression constraints are expressed entirely in terms of pi_t and sigma_t, e.g.:

• For a bluff-catching action a_bc, EV(a_bc | h_t) = 0 for marginal hands ⇒ sum_{h} pi_t(h) * EV(a_bc | h, h_t) = 0

• For a particular bet size B on street s:
  (Total weight of bluffs in pi_t assigned to bet B) / (Total weight of value hands in pi_t assigned to bet B) ≈ B / (P_s + B)

The opponent’s initial distribution pi_0^opp affects pi_t(h) only through which hands remain possible in H, not through your sigma_t; optimal sigma_t depends only on your own pi_t and payoffs.

**Für den Bot:** Track your own range evolution at every node and enforce balance and correct bluff:value ratios with respect to that range; don’t condition your own strategy on guessed villain hole cards directly, but on your distribution and the structural payoff model, then use villain modeling only to bias around that baseline.

## EV-based decision resolution (local EV nodes)
Because the full game tree is too large, many decisions are reduced to local EV comparisons given an approximate opponent distribution. This is consistent with the book’s approach: treat difficult nodes as small toy games, plug in equity vs an estimated range, and compare EV(call) vs EV(fold) vs EV(raise), often setting thresholds by indifference (EV(call)=EV(fold)).

**Formel:** Single-street call decision with pot P, facing bet B, and hero’s equity e against villain’s betting range:

EV_fold = 0  (ignoring sunk pot share)
EV_call = e * (P + B) - (1 - e) * B

Call is +EV iff EV_call > EV_fold:

e * (P + B) - (1 - e) * B > 0
⇒ e * (P + B) > (1 - e) * B
⇒ e * (P + B + B) > B
⇒ e > B / (P + 2B)

Thus, the minimum equity threshold for a breakeven call is:

e_min = B / (P + 2B)

Indifference condition for bluff-catchers:

Set e = e_min for marginal calling hand class, and solve for range composition (villain’s value:bluff mix) that produces this equity on that class.

**Für den Bot:** Implement fast EV calculators and equity thresholds (e.g., e > B / (P + 2B)) at each decision node so that, given an opponent range estimate, your bot can locally compare EV(call), EV(fold), and candidate raises; then refine these thresholds into indifference-based frequency decisions for marginal hands.

## Aggression bias when EVs are close
Given the asymmetric cost of errors—folding too much concedes whole pots, while excess aggression costs only extra bets—the book recommends choosing the more aggressive option when EVs are close (within noise of modeling error). This is effectively a tie-breaking rule consistent with optimal toy-game solutions that are highly aggressive.

**Formel:** Let two candidate actions for hand h at node t be a_passive and a_aggr with estimated EVs:

EV(a_passive | h_t, h) = EV_p
EV(a_aggr   | h_t, h) = EV_a

Given estimation error δ > 0 (e.g. model or opponent-range noise), if:

|EV_p - EV_a| <= δ

then choose a_aggr.

This can be encoded as a decision rule:

argmax_{a ∈ {a_passive, a_aggr}} [EV(a) + lambda * I[a is aggressive]]

with a small lambda > 0 that biases toward aggression when EVs are close:

if EV_a + lambda > EV_p:
    choose a_aggr
else:
    choose a_passive

No fixed lambda is prescribed; it is a design parameter reflecting how much you want to over-weight aggression relative to small EV differences.

**Für den Bot:** When your EV estimates for a passive and an aggressive line are very similar, bias the policy slightly toward aggression; this mirrors the structure of optimal toy-game strategies and mitigates the high cost of systematic overfolding that many opponents exhibit.

## No additional mathematical content in this excerpt
The provided text is purely biographical and publishing information. It contains no game models, no equilibrium constructions, and no formulas.

**Formel:** 

**Für den Bot:** There is nothing new here to implement: no toy games, no indifference equations, no alpha/MDF, no EV formulas. Use models and results extracted from earlier excerpts instead.
