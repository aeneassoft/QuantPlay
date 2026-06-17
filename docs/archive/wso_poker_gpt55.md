# WSO (War Strategy Optimization) -> poker (gpt-5.5, 2026-06-16)

## 1) What WSO actually is — plainly

WSO is a population-based, derivative-free **single-objective continuous global optimizer**: each “soldier” is a candidate vector \(X_i \in \mathbb{R}^d\), fitness is one scalar objective, and the best/second-best candidates are called **King** and **Commander**. Its **attack/exploitation** update moves a soldier using the King direction plus a Commander–King displacement perturbation, roughly \(X_i' = X_i + 2\rho\,rand\,(C-K) + W_i(K-X_i)\). Its **defense/exploration** update uses the King, Commander, and a random soldier, roughly \(X_i' = X_i + 2\rho(K-X_{rand}) + rand\,W_i(C-X_i)\). A candidate is accepted only if fitness improves; its **rank** increases, and its weight is updated/decayed as a function of rank/iteration, giving large early moves and smaller late moves. The worst “weak soldier” is periodically replaced randomly inside bounds or relocated near the population median/King region. **It is not a poker/game/Nash/equilibrium solver; it is PSO/DE/GA-like black-box continuous optimization with war-themed names.**

---

## 2) Rigorous use in your bot: black-box offline optimizer only

Use WSO only where you can define a bounded low/medium-dimensional vector \(\theta\) and a scalar evaluation \(J(\theta)\).

### Recommended recipe: tune exploit-layer + safety hyperparameters

**Decision vector \(\theta\), example 20–60 dims:**

- LCB gate parameters by node class:  
  \(\theta_{LCB} =\) confidence multiplier \(z\), min sample \(N_{min}\), posterior variance floor, decay half-life.
- Dirichlet opponent-model priors:  
  \(\alpha_0\) by action class/street/position, prior mixing weight to population pool, recency decay.
- Safe-exploit controls:  
  exploit blend cap \(\eta\), max deviation from GTO floor, minimum CFV edge to deviate, fallback threshold.
- Resolver/risk parameters:  
  exploitability penalty weight, LBR alarm threshold, CFV-net uncertainty margin.
- Bet-size grid parameters:  
  pot-fraction sizes in log space, e.g. flop cbet grid \([0.25,0.5,0.75,1.25]\) encoded as ordered logits; turn/river raise sizes; 3-bet/4-bet multipliers.

Use transforms: log for positive parameters, sigmoid for bounded parameters, softmax/sorted transforms for grids/simplex-like pieces.

**Objective:**

\[
J(\theta)= \widehat{EV}_{bb/100}(\theta)
- \lambda \max(0, LBR(\sigma_\theta)-\epsilon)^2
- \mu D(\sigma_\theta,\sigma_{GTO})
\]

where \(\widehat{EV}\) is vs a **frozen opponent model or opponent pool**, \(LBR\) is local-best-response exploitability proxy, and \(D\) penalizes excessive deviation from the CFR/solver floor.

Better: optimize a lower bound, not the mean:

\[
J_{robust}(\theta)=\widehat{EV}(\theta)-c \cdot SE(\widehat{EV})-\lambda \text{risk penalty}
\]

because poker EV estimates are extremely noisy.

**Evaluation:**

1. Freeze GTO floor, resolver, CFV-net, and opponent model/pool.
2. For each WSO soldier \(\theta_i\), run duplicate-hand simulations against the same opponent seeds.
3. Score paired bb/100 difference vs baseline bot, plus LBR/exploitability penalty.
4. WSO updates \(\theta_i\); accept only if the paired estimate improves with enough confidence.
5. Re-evaluate King/Commander periodically with more samples.
6. Final validation: independent seeds, unseen opponents, long run, and LBR stress test.

**Noise catch — mandatory adaptations:**

- Use **common random numbers / duplicate deals** for paired comparisons.
- Use **sequential resampling/racing**: cheap eval all candidates, allocate more hands to top/uncertain candidates.
- Re-sample King and Commander every generation; otherwise WSO will crown variance winners.
- Use bootstrap CIs or Bayesian EV posteriors.
- Consider a surrogate/BO layer if each evaluation is expensive.
- Do not optimize raw short-run bb/100; it will overfit variance.

Defensible secondary uses: bet-size grid selection, prior calibration, LCB threshold tuning, and compact parametric exploit policies. Not defensible: optimizing the entire poker strategy tree directly with WSO.

---

## 3) War metaphor mapping — inspiration only, not math

**Attack strategy → exploit aggression.**  
When villain’s posterior says overfold/overcall/underbluff with high confidence, “attack” corresponds to raising, thin value betting, overbluffing, or sizings that punish that leak.

**Defense strategy → GTO floor / uncertainty fallback.**  
When samples are weak or LCB is negative, “defense” means stay near CFR/TexasSolver baseline, reduce exploit blend, protect against counter-exploitation.

**King → best current candidate line/policy.**  
In experiments, the King is the best-performing parameterization or line against the frozen model. It is **not automatically a true poker best response** unless computed by an actual BR/LBR solver.

**Commander → robust second-best.**  
Useful as a hedge against overfitting: if King wins only on noisy samples but Commander is more stable across opponent clusters, prefer the robust one.

**Weak soldier relocation → abandon losing lines.**  
Lines whose LCB EV is poor, whose exploitability penalty spikes, or whose opponent posterior no longer supports them get frequency cut, reset toward GTO, or reassigned to exploratory alternatives.

**Rank/weight → budget/frequency allocation.**  
Repeatedly validated lines get more sampling/search/frequency; unproven lines get smaller weights or forced exploration. This is a useful design metaphor, not a theorem.

---

## 4) Honest limits — where WSO does not transfer

WSO does **not** solve imperfect-information games, compute Nash equilibria, minimize regret, or produce counterfactual values. CFR/resolving are structurally correct for poker; WSO is not.

A poker strategy is a huge product of information-set simplexes. Naively applying continuous position updates to action probabilities can violate normalization, abstraction constraints, card-removal structure, and information-set consistency.

WSO assumes a relatively stationary black-box objective. Poker opponents adapt; a King found against yesterday’s model can become a trap today.

Raw bb/100 optimization is dangerous: variance is huge, and WSO will happily overfit noise, population artifacts, or one opponent cluster. Without LBR/BR penalties and heldout validation, it can make the bot more exploitable.

For subgame solving, use CFR/depth-limited resolving/CFV nets. For Bayesian opponent modeling, use posterior updates, not WSO. For online action selection, use your GTO floor + LCB-gated exploit layer, not population metaheuristics.

Bottom line: WSO is acceptable as an **offline black-box tuner** for compact exploit-system parameters. It is not a replacement for CFR, safe exploitation, Bayesian opponent modeling, or resolver-based poker reasoning.
