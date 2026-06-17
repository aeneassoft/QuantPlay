# Nash equilibrium in poker — keyword consult (gpt-5.5)

I don’t have live web search here; this is from the poker-AI literature and known public solver/bot ecosystem. The key conclusion is blunt:

**There is no publicly published, certified, full-game Nash or ε-Nash 200bb HU NLHE preflop chart.**  
The published HU NLHE “near-Nash” systems are mostly **proprietary blueprints + real-time solving**, with match results but **no released strategy tables and no full-game exploitability certificate**. For your situation, an **exact preflop best response is valuable only as exploitability of your surrogate game**; if it uses the same checkdown/realization leaf model you solved against, it can easily certify the wrong thing.

---

## 1. Published / known near-Nash poker solutions

### A. Actually solved / certified: mostly **limit** or toy/restricted games

| System / game | What is published | Concrete facts | Relevance to HU NLHE 200bb |
|---|---:|---|---|
| **Kuhn poker** | Exact Nash equilibrium | Harold Kuhn, 1950/1953. Classic 3-card toy poker. | Useful for validating CFR/BR code only. |
| **Sequence-form LP poker solutions** | Exact equilibria for small extensive-form games | Koller, Megiddo, von Stengel, “Efficient computation of equilibria for extensive two-person games,” *Games and Economic Behavior*, 1996. | The theoretical baseline for exact BR/NE in finite EFGs. Not scalable to HUNL. |
| **CFR** | General equilibrium algorithm for large imperfect-information games | Zinkevich, Johanson, Bowling, Piccione, “Regret Minimization in Games with Incomplete Information,” NeurIPS 2007. Average regret → ε-Nash in two-player zero-sum. | Your CFR+ blueprint is in this lineage. Guarantee applies to the game you actually solved. |
| **CFR+ / Cepheus** | Weak solution of **heads-up limit hold’em** | Bowling, Burch, Johanson, Tammelin, “Heads-up limit hold’em poker is solved,” *Science*, 2015. Used CFR+. Game size reported around **3.16×10¹⁷ decision points** and **3.19×10¹⁴ information sets**. Exploitability reported as **≤0.986 mbb/g**, i.e. less than 0.001 BB/hand, roughly **0.1 bb/100** depending unit convention. Public Cepheus strategy was queryable. | This is the closest “real poker solved” result, but it is **limit**, not NLHE, and not 200bb deep no-limit. |
| **Push/fold preflop Nash charts** | Exact or near-exact NE for restricted preflop jam/fold games | Sklansky-Chubukov rankings; later tools like HoldemResources Calculator / ICMIZER compute chipEV/ICM push-fold equilibria. | Valid only for games where actions are fold/call/jam. Useful sanity check for all-in equity/card-removal code, not for 200bb HU NLHE. |

---

### B. HU NLHE superhuman systems: published algorithms/results, **not public Nash charts**

| System | Game | Algorithmic approach | Concrete published facts | What is missing |
|---|---|---|---|---|
| **DeepStack** | HU NLHE, ACPC-style deep-stack HUNL | Continual re-solving, depth-limited lookahead, neural counterfactual value network. | Moravčík et al., “DeepStack: Expert-level artificial intelligence in heads-up no-limit poker,” *Science*, 2017. Played **44,852 hands** vs **33 pros**. Reported win rate about **492 mbb/g**, i.e. ~**49 bb/100**, with AIVAT variance reduction. | No released full strategy, no preflop charts, no certified full-game exploitability. |
| **Libratus** | HU NLHE, 200bb-style no-limit | Offline abstract-game blueprint via CFR/MCCFR, nested/safe subgame solving, self-improver that patched holes overnight. | Brown & Sandholm, “Superhuman AI for heads-up no-limit poker,” *Science*, 2018. Played **120,000 hands** vs 4 top pros. Won **$1,766,250** in chips at $50/$100, equivalent to about **14.7 bb/100**. Used Pittsburgh Supercomputing Center Bridges; often cited as about **15 million core-hours** for the blueprint. | No public preflop ranges. No full-game exploitability bound in unabstracted HUNL. |
| **Slumbot** | Public HU NLHE bot, ACPC-style 200bb | CFR-solved abstraction; public playable bot by Eric Jackson. | Publicly playable at Slumbot site/API. ACPC HUNL game commonly used **20,000 chips, blinds 50/100 = 200bb**. Slumbot won ACPC HUNL events; I recall **2016** and later strong versions, but verify exact year list on ACPC/Slumbot pages. | No certified exploitability. No full preflop chart release. Details are more website/ACPC-submission level than peer-reviewed full disclosure. |
| **ReBeL** | HU NLHE benchmark, among other games | Recursive Belief-based Learning: self-play RL + search over public belief states. | Brown, Bakhtin, Lerer, Gong, “Combining Deep Reinforcement Learning and Search for Imperfect-Information Games,” NeurIPS 2020. Reported strong HUNL performance; I recall a reported result around **+165 ± 69 mbb/g vs Slumbot**, but verify exact table. | No public 200bb Nash ranges; not a certified equilibrium. |
| **Pluribus** | 6-player no-limit hold’em, not HU | Blueprint via MCCFR abstraction + real-time search. | Brown & Sandholm, “Superhuman AI for multiplayer poker,” *Science*, 2019. Reported about **+48 mbb/hand** = **4.8 bb/100** in one pro setting, depending comparison condition. Trained in roughly **8 days on a 64-core server**, often cited as <$150 cloud cost. | Multiplayer NE/exploitability is not the same object. Not HU. No published ranges. |

Important distinction:

- **Cepheus/HULHE**: actual weak solution with public strategy and exploitability number.
- **DeepStack/Libratus/Slumbot/ReBeL**: strong HU NLHE agents, but **not published as open Nash equilibria**.
- **Pluribus**: important blueprint/search lineage, but **not a HU zero-sum Nash solution**.

---

### C. Commercial/open solver outputs / preflop charts

There are many accessible “GTO” HU or cash preflop charts from:

- **GTO Wizard**
- **PioSolver Edge / Pio preflop workflows**
- **MonkerSolver**
- **Simple Preflop Holdem**
- **Zenith Poker public/preflop libraries**, depending current availability
- Training products from Run It Once / Upswing / Finding Equilibrium etc.

But these are generally:

1. **Solved abstractions**, not full-game proofs.
2. Tree/rake/size-menu specific.
3. Often proprietary black boxes.
4. Usually not accompanied by exploitability certificates in the full unabstracted 200bb HUNL game.

So if you ask, “Where is the published 200bb HU NLHE Nash chart?” — I do **not** know of one.

---

## 2. Cheapest reliable ways to measure distance to Nash without a full re-solve

For two-player zero-sum poker, the standard quantity is **exploitability** or **NashConv**.

For profile σ:

\[
\text{NashConv}(\sigma)
=
\left[\max_{\tau_1} u_1(\tau_1,\sigma_2)-u_1(\sigma_1,\sigma_2)\right]
+
\left[\max_{\tau_2} u_2(\sigma_1,\tau_2)-u_2(\sigma_1,\sigma_2)\right]
\]

In two-player zero-sum, people often report:

\[
\text{Exploitability} = \frac{\text{NashConv}}{2}
\]

For a single bot strategy in an alternating-position HU no-rake game with value 0, one-sided exploitability is essentially:

\[
-\min_{\tau_{\text{opp}}} u_{\text{hero}}(\sigma_{\text{hero}},\tau_{\text{opp}})
\]

AIVAT EV loss versus GTO Wizard is **not exploitability**, but if your expected EV is truly **−72 bb/100**, then your one-sided exploitability is at least about **72 bb/100**, assuming same zero-sum game/value convention and confidence interval. A specific opponent is one candidate adversary; the true best response can only be worse.

---

### Measurement methods

| Method | Cost | What it certifies | Main failure modes |
|---|---:|---|---|
| **CFR regret bound** | Free if tracked during solve | In two-player zero-sum, average strategy exploitability in the **solved abstraction** is bounded by average regret: roughly \((R_1^T+R_2^T)/T\). | Says nothing about abstraction error, missing actions, wrong leaf values, sampling error, or deployed non-average strategy. |
| **Exact best response in your finite preflop game** | Cheap | True exploitability of your **preflop surrogate game**. This is the right first local metric. | Vacuous if the surrogate leaf model is wrong. If CFR and BR share the same checkdown/realization continuation, low exploitability mostly proves convergence to the wrong game. |
| **Exact BR with larger action menu** | Moderate | Lower bound on exploitability under a richer preflop action set, if you define responses/action translation. | If bot has no strategy for off-tree sizes, translation can hide or invent leaks. Still depends on leaf values. |
| **Exact full-game BR** | Usually infeasible for HUNL | True exploitability of full tabular strategy. | Full HUNL tree is astronomically large; deployed bot usually not represented tabularly over all histories. |
| **Local Best Response, LBR** | Cheap to moderate | Lower-bound leak finder. Introduced for evaluating large no-limit bots; see Lisý & Bowling, “Equilibrium Approximation Quality of Current No-Limit Poker Bots,” 2017. | Myopic. Can read near-zero for a badly exploitable strategy if exploit requires multi-street setup, unavailable sizes, correct future bluffing/calling, or a value model different from checkdown. |
| **Approximate BR / exploitability descent / PSRO-style adversary** | Moderate to high | Lower bound unless oracle is exact. | Function approximation, local minima, action abstraction, bad rollout/value model. Exploitability Descent: Lockhart et al., “Computing Approximate Equilibria in Sequential Adversarial Games by Exploitability Descent,” 2019-ish; verify exact author list/year. |
| **AIVAT** | Cheap once you have hand histories and value baselines | Unbiased lower-variance estimate of EV versus a specified opponent/profile. Burch et al., “AIVAT: A New Variance Reduction Technique for Agent Evaluation in Imperfect Information Games,” AAAI/IJCAI-era 2017/2018. | Not a Nash-distance metric. It estimates match EV, not best-response EV. Bad value functions reduce variance less but should not bias if control variate conditions are met. |

---

### When LBR can read ~0 while the strategy is leaky

This is exactly the danger for your current project.

LBR can miss leaks when:

1. **The exploit requires a future plan.**  
   Example: opponent overfolds rivers, but flop/turn barrels look bad under checkdown rollout. A greedy LBR never starts the bluff.

2. **The profitable action size is absent.**  
   If the leak is punished by 3x open, 12bb 3bet, 4bet jam, min-5bet, overbet jam, etc., but LBR only has your menu, it may see nothing.

3. **The continuation model shares the same blind spot as the blueprint.**  
   If both blueprint and BR use checkdown+realization, then your exact BR mostly says, “This is equilibrium in the checkdown game.”

4. **The leak is range-level, not hand-equity-level.**  
   Example: villain reaches a 4bet pot with no suited wheel aces or no low-board coverage. Checkdown equity may not punish that; real postflop equilibrium does.

5. **The exploit needs blocker-aware combo precision.**  
   169×169 class equities can smear A5s/A4s/KQo/AQo blocker effects. Exact BR should use 1326-combo card removal, or at least exact conditional class tables.

6. **The BR accidentally cheats or under-cheats.**  
   If it chooses actions per exact villain hand, it overstates exploitability. If it averages too coarsely over 169 without proper blockers, it can understate.

7. **The leak is off-path.**  
   Standard exploitability is reach-weighted. Massive off-path mistakes may not matter unless a BR can force them.

---

### What makes your local preflop BR trustworthy rather than vacuous

For your current exact preflop CFR+ blueprint, I would require these before trusting the number:

1. **Information-correct BR.**  
   At each infoset, maximize after summing over the opponent’s posterior combo range. Do not choose separately against each villain combo.

2. **1326-combo card removal.**  
   A 169×169 all-in equity matrix is convenient but not fully exact for blocker/suit effects. For serious exploitability, use exact combo-pair equities or canonical suit-isomorphism with conditional aggregation.

3. **Independent leaf values.**  
   Have two numbers:
   - **In-model exploitability**: BR using the same leaf model as CFR. This measures convergence.
   - **Out-of-model local exploitability**: BR using independently calibrated leaf values from Pio/GTO Wizard/batched postflop solves/strong neural CFV. This is closer to “distance to real Nash.”

4. **Action-superset stress tests.**  
   Run BR with your menu, then with extra sizes: 2x/3x opens, 8/12/14bb 3bets, 20/28/32bb 4bets, jams. If exploitability jumps, your menu is hiding size exploits.

5. **Injected-leak tests.**  
   Deliberately create known errors:
   - overfold BB vs 2.5x by 10%
   - overcall 4bets with dominated offsuit broadways
   - jam QQ/AK too often for 200bb
   - never limp-trap AA
   - fold too much to 5bet  
   Your metric should find the correct direction and nontrivial magnitude.

6. **Compare against AIVAT loss.**  
   If GTO Wizard AIVAT says −72 bb/100 over enough volume, and your local BR says −2 bb/100, then either:
   - AIVAT sample/opponent/game mismatch is wrong, or
   - your local evaluator is missing the real leak.

7. **Report decomposition.**  
   Break exploitability by:
   - SB first action
   - BB vs limp
   - BB vs open
   - SB vs 3bet
   - BB vs 4bet
   - SB vs 5bet
   - hand class/combo  
   A single scalar is not enough.

---

## 3. HU 200bb preflop Nash structure: what is documented?

### Rigorous answer

The exact 200bb HU NLHE preflop Nash equilibrium is **not publicly documented** in the way Cepheus documents HULHE. There is no known public paper saying:

> “Here is the 200bb HU NLHE Nash preflop strategy with exploitability ≤ X.”

What exists:

- commercial solver outputs;
- private Libratus/DeepStack/Slumbot/ReBeL-style blueprints;
- public/semipublic training charts;
- qualitative solver consensus.

So I would not quote a universal limp frequency as “the Nash number.” It changes materially with:

- rake/no rake;
- open sizes allowed;
- 3bet/4bet/5bet sizes;
- whether limping is allowed;
- postflop abstraction;
- all-in/action discretization;
- stack depth;
- whether the solver uses full postflop or a leaf model.

---

### Practical solver-consensus structure at 200bb HU

These are qualitative but robust across strong solver outputs.

#### 1. SB/button VPIP is extremely high

In no-rake HU with limping allowed, SB/button plays very close to all hands. Open-folding is rare or nonexistent depending tree.

Reason: SB has position postflop and has already posted 0.5bb. If SB limps, it costs 0.5bb more to contest a pot where position has high realization.

With rake, especially high rake, bottom trash folds more.

#### 2. Limping is not only weak hands

Real equilibrium limping ranges generally contain:

- weak hands that do not want to face 3bets;
- medium hands with decent realization;
- some strong traps like AA/KK/AK at low frequency;
- hands protecting limp-call and limp-raise ranges.

If your blueprint has “limp = capped trash,” BB can iso-raise/over-realize aggressively.

#### 3. Multiple open sizes are tree-dependent

If only 2.5x is allowed, solver finds equilibrium for that game. If 2x, 2.5x, 3x are all allowed, the equilibrium may mix or choose different dominant sizes.

At 200bb, exact sizing matters because SPR and implied odds matter a lot.

#### 4. BB versus 2.5x defends wide

Facing SB open to 2.5bb:

- SB has 2.5 in.
- BB has 1 in.
- BB must call 1.5 more.
- Final pot after call is 5bb.

Raw pot-odds threshold is:

\[
1.5/5 = 30\%
\]

OOP realization is worse than raw equity, but many hands still continue because ranges are wide and there is no rake in many HU models.

#### 5. BB 3bet range is not pure equity

BB 3bets for:

- value/equity;
- fold equity;
- blocker effects;
- playability;
- denial;
- range construction.

At 200bb, suitedness/nut potential matter more than in a shallow all-in model. A hand like A5s can be a better 4bet/5bet bluff than a higher-equity dominated offsuit hand because it:

- blocks AA/AK/AQ;
- has nut-flush potential;
- has wheel-straight potential;
- realizes decently when called.

#### 6. Deep 4bet/5bet strategy is not jam/fold

At 200bb, preflop all-in ranges are much tighter than 100bb.

A realistic equilibrium includes:

- non-all-in 4bets;
- calls versus 3bets;
- calls versus 4bets;
- sometimes non-all-in 5bets;
- very tight 6bet jams;
- AA/KK slowplays at some frequency;
- blocker-heavy bluffs.

Your menu `3bet-10 / 4bet-24 / 5bet-60 / jam` is plausible, but the critical issue is whether the continuation after non-all-in 4bet/5bet pots is realistic. At 200bb, a 5bet to 60bb leaves about 140bb behind, so postflop strategy still dominates EV.

#### 7. Indifference/blocker math matters

Example: SB opens 2.5, BB 3bets to 10, SB 4bets to 24.

Before SB’s 4bet, pot is about:

\[
2.5 + 10 = 12.5 \text{ bb}
\]

SB adds 21.5 more. A zero-equity 4bet bluff needs folds:

\[
21.5 / (12.5 + 21.5) \approx 63.2\%
\]

In real poker the bluff has equity and postflop EV when called, so the required fold frequency is lower. But this illustrates why blockers matter: if A5s removes AA/AK continuations, it can shift a marginal bluff into profitable territory.

---

## 4. What your equity-solved/checkdown preflop blueprint is most likely getting wrong

Given your description — exact preflop CFR+ with 169×169 all-in equity and checkdown+realization continuation — the most likely structural errors are:

### 1. Overvaluing raw equity hands

Hands like:

- AJo
- KQo
- KJo
- QJo
- weak offsuit Ax
- dominated broadways

often look good in equity matrices but suffer from:

- reverse implied odds;
- domination;
- poor deep-stack realization;
- bad playability OOP;
- difficulty continuing versus pressure.

A checkdown continuation tends to make them call/stack too much.

---

### 2. Undervaluing nut-potential hands

Deep-stack equilibrium likes hands that can make nutted hands and apply pressure:

- suited wheel aces;
- suited broadways;
- suited connectors;
- some suited gappers;
- pocket pairs in the right branches.

Their value is not just showdown equity; it comes from:

- nut flushes;
- straights;
- board coverage;
- semi-bluffing;
- implied odds;
- blocker leverage.

Checkdown models usually underprice this.

---

### 3. Wrong 4bet/5bet bluff candidates

A pure equity model may choose bluffs with decent hot/cold equity but bad blocker properties.

Real equilibrium prefers bluff candidates that:

- block AA/KK/AK/AQ;
- retain equity when called;
- do not dominate villain’s folds too much;
- have postflop maneuverability.

This is why A5s/A4s-type hands appear in real solver 4bet bluff ranges.

---

### 4. Wrong deep-stack stack-off thresholds

At 200bb, hands like QQ/AK are not automatically happy to play for stacks in all branches. A checkdown/all-in-equity model can badly misprice:

- QQ versus 5bet/6bet ranges;
- AKo versus polarized 5bet ranges;
- KK slowplays;
- AA trap frequencies;
- suited Ax blocker jams.

---

### 5. Missing range-vs-range postflop incentives

Preflop NE is downstream-dependent. A hand’s preflop EV depends on the entire range it travels with.

Examples:

- If your SB 4bet-call range lacks low-board coverage, BB can attack low flops.
- If your BB flatting range lacks AA/KK traps, SB over-realizes in 4bet pots.
- If limp range is capped, BB iso-raises too profitably.
- If 3bet-call range is too broadway-heavy, certain flop classes become disasters.

Checkdown continuation does not see these.

---

### 6. 169×169 matrix hides exact blockers

For all-in equities, 169 hand classes are often acceptable for rough solving, but for exploitability and blocker-driven preflop mixing, they are dangerous.

Example issues:

- A5s with specific ace suit blocks different suited Ax continuations.
- KQs versus AQ/AK classes has suit-dependent equity/removal.
- Pair-vs-suited-combo equities vary with exact suits and dead cards.

For high-quality BR, use exact combo-pair treatment: 1326 combos, excluding overlaps.

---

## 5. Nash-equilibrium facts that “GTO” framing often obscures

### 1. Nash is a property of a full strategy profile, not a chart

A preflop chart is only equilibrium relative to:

- both players’ full strategies;
- all future postflop branches;
- the action set;
- stack depth;
- rake;
- abstraction;
- tie-breaking among equal-EV mixes.

There is no standalone “Nash preflop range” independent of postflop strategy.

---

### 2. Solver-GTO is usually abstraction-GTO

Most no-limit “GTO” outputs are equilibria of:

- discretized bet sizes;
- bucketed/card-abstracted states;
- approximate postflop trees;
- imperfect recall abstractions;
- neural value approximations;
- action translation systems.

They can be very strong, but they are not the mathematical Nash equilibrium of full HUNL.

---

### 3. Low in-abstraction exploitability can be meaningless in the real game

A bot can be almost unexploitable in its own abstraction and very exploitable in the real game.

This was a central lesson of early ACPC bots: abstraction quality and off-tree action handling mattered as much as regret minimization.

---

### 4. Head-to-head EV is not exploitability

Beating or losing to GTO Wizard AI is useful, especially with AIVAT, but it is not the same as distance to Nash.

- Losing badly gives a **lower bound** on your vulnerability.
- Winning does not prove low exploitability.
- AIVAT reduces variance; it does not produce a best response.

---

### 5. Equilibria are often non-unique

Different Nash equilibria can have:

- different preflop mixes;
- different off-path behavior;
- different suit-level tie-breaking;
- same game value.

So do not overfit one product’s exact frequencies. Use exploitability and EV deltas, not chart distance.

---

### 6. CFR guarantee is for the average strategy

Classical CFR convergence is for the average strategy. CFR+ often uses regret-matching+ with linear averaging and can have strong last-iterate practical behavior, but the clean theorem is about regret/average profile.

If your deployed bot uses current iterate, clipped ranges, quantized frequencies, or post-processed strategy, measure that actual deployed strategy.

---

## Practical recommendation for your bot

For your local preflop exploitability gauge, maintain three numbers:

1. **CFR in-model exploitability**  
   Exact BR using the same checkdown/realization continuation.  
   Purpose: convergence/regression test.

2. **Independent-leaf local exploitability**  
   Exact preflop BR using calibrated postflop leaf values from stronger solves or cached GTO Wizard/Pio outputs.  
   Purpose: actual Nash-distance proxy.

3. **Action-superset exploitability**  
   Same as #2, but BR gets extra sizes.  
   Purpose: detect action-menu artifacts.

If #1 is near zero but #2/#3 or AIVAT says −72 bb/100, your blueprint is likely a beautiful equilibrium of the wrong preflop game.
