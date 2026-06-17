# Alpha consult — poker/exploit (gpt-5.5)

## Brutal headline

**Exploit-primary is directionally right, but only if “max exploit” means “robust best response to a calibrated opponent model,” not “jam the posterior-mean leak with 62 rules.”** Your current system’s biggest leak is not lack of GTO purity; it is that the exploit layer is still mostly **coarse-stat nudging** sitting on top of a floor whose action EVs are weak/derived. That captures small EV and misses the big static-bot EV.

Honest target ranking:

| Target | Attainable edge | Honest ceiling |
|---|---:|---|
| **Slumbot** | Highest. Static + public API + abstraction/translation leaks are actually probeable. | **Realistic strong tailored: +8 to +15 bb/100. Stretch: +20 to +25. >30 bb/100 requires a major discovered bug/leak; hype until proven.** |
| **Supremus AI** | Unknown. I do **not** know its exact current architecture. If it is CFVnet/search-lineage and strong, crude exploits will not crush it. | **Realistic: -5 to +3 bb/100. Stretch +5 to +8 only if it is static, accessible, and has exploitable action/river/value-net leaks.** |
| **GTO Wizard AI** | Least-loss target. If benchmark is solved/near-solved fixed action set, there may be no material exploit. | **Realistic: -4 to -1 bb/100 for an excellent agent. 0 to +1 only via implementation bug/abstraction leak/noise. “Crush” is hype.** |

Your current Slumbot result **+2.2 bb/100 over 500h** is promising but not proof. In HUNL variance terms, that could easily be inside confidence noise unless your hand count is huge and variance reduction is strong. Treat it as: **“we are probably somewhere between mildly losing and mildly winning; the exploit layer improved the floor materially.”**

---

# 1. Pressure-test exploit-primary

## Is the concept sound?

Yes, with a correction.

The sound version is:

> Maintain a posterior opponent model. At each decision, choose the action with highest **robust lower-confidence EV** versus that model. Fall back to the GTO floor when the exploit’s lower-confidence EV does not beat the floor by enough.

The unsafe/hype version is:

> Predict villain folds 63% instead of 54%, therefore blast every node with the posterior-mean best response.

That will overfit, especially in sparse turn/river nodes.

A practical decision rule should be something like:

\[
a^* = \arg\max_a \text{LCB}_\alpha \left[ EV(a \mid M) - EV(\pi_{\text{floor}} \mid M) \right]
\]

where:

- \(M\) = opponent-model posterior, not a point estimate.
- \(\text{LCB}_\alpha\) = lower confidence bound over model uncertainty.
- \(\pi_{\text{floor}}\) = your GTO-ish insurance policy.
- Execute exploit only if:

\[
\max_a \text{LCB}_\alpha[\Delta EV(a)] > \tau
\]

where \(\tau\) covers rake/noise/model-bias/implementation risk.

For **static opponents**, the safety bound can be loose. They do not adapt. Your only real enemy is model error.

For **adaptive opponents**, the safety bound matters a lot. You need to limit how exploitable your counter-strategy becomes if villain starts adjusting.

---

## When is max-exploit safe?

### Safe-ish: static opponents

Max-exploit is safe when:

1. Opponent policy is stationary.
2. Opponent does not update to your frequencies.
3. Your model has enough data in the relevant node cluster.
4. Your candidate action does not push the game into unknown future states.
5. Raise response is modeled, not ignored.
6. You account for card removal/range composition.

This describes **Slumbot better than most targets**. If Slumbot is static and exposed through a public API, then once you identify a true fold/call/raise curve leak, you should not “nudge.” You should hammer it.

Example:

- If Slumbot overfolds river 4-flush boards to 125% pot when you hold the nut-flush blocker, do not bluff at GTO frequency.
- Bluff every combo whose LCB EV is positive.
- Cut the bluff if the blocker class, line, or size cluster is outside confidence.

Against a static bot, balance is mostly irrelevant except insofar as the bot’s fixed policy conditions on public history and card removal.

---

### Not safe: adaptive opponents

Max-exploit becomes dangerous when:

1. Opponent notices your overbluff/overfold/size skew.
2. Opponent has a meta-adaptation layer.
3. Opponent’s strategy changes after you probe.
4. Opponent is human or human-supervised.
5. Match format is long enough for them to counter-adjust.

Then you need a **safe-exploit frontier**.

Practical implementation:

\[
\pi_\lambda = (1-\lambda)\pi_{\text{floor}} + \lambda\pi_{\text{exploit}}
\]

with \(\lambda\) chosen by:

- Model confidence.
- Evidence of opponent stationarity.
- Cost of being counter-exploited.
- Observed drift in villain frequencies.
- Match length.

Against Slumbot, \(\lambda\) can often approach 1 in confident nodes.

Against Supremus or unknown adaptive opponents, \(\lambda\) should start small.

Against GTO Wizard, \(\lambda\) should usually be 0 unless you have hard evidence of a static implementation leak.

---

## What breaks exploit-primary?

### 1. Posterior-mean overfitting

If your model says villain folds 70% on a rare river node after 8 samples, max-exploit will torch money.

Fix:

- Use Bayesian shrinkage.
- Use lower-confidence EV, not mean EV.
- Demand minimum sample/effective sample thresholds.
- Bucket nodes hierarchically.

---

### 2. Range-composition blindness

Your current LBR is already proven vacuous because it misses range-composition leaks and passive-after-move under-exploits. That same weakness will corrupt exploit-primary if you only model aggregate fold frequencies.

Bad model:

> “Villain folds 62% to river overbet.”

Useful model:

> “Villain folds 74% to river overbet on 4-flush boards after bet/bet/check line, but only when their range contains capped one-pair hands. They call too much with A-high flush blockers and under-defend non-blocker bluffcatchers.”

You need response curves conditioned on:

- Line.
- Board class.
- Size.
- Range cap.
- Blockers.
- Villain’s likely hand distribution.
- Raise frequency.

---

### 3. Local action EV without future continuation EV

A flop exploit cannot be evaluated only by immediate fold equity. You need future EV after call/raise. Your “fold-equity-optimal sizing” is likely leaving alpha or creating punts because the best size is often the one that maximizes **full-tree EV**, not immediate folds.

Fix:

- River exploit first: no future street.
- Then turn exploit: one future street.
- Then flop exploit: needs continuation model.

---

### 4. Action EVs are missing from the solver cache

This is a major architecture leak.

You have solver frequencies but no per-action EVs. A supervised MLP predicting solver \(P(\text{bet})\) can match frequencies and still choose low-EV actions in exploit mode. Solver action frequency is not the same as action value.

Actionable fix:

- Rebuild/extend cache with:
  - per-action EV,
  - counterfactual values,
  - regrets,
  - range distributions,
  - node reach probabilities,
  - response frequencies by hand class.

If you cannot get action EVs from the old cache, re-solve a smaller but strategically targeted subset. Do not pretend policy-only cache gives reliable EV gaps.

---

### 5. Coarse stats are too weak

VPIP, fold-to-bet, aggression frequency are useful for weak bots. They are not enough for Slumbot/Supremus/GTO Wizard.

The 62-rule overlay probably crushes bad bots because bad bots have giant population leaks. Against strong bots, this becomes timid, noisy, and often wrong.

Replace “rules nudging” with:

- per-node response models,
- calibrated uncertainty,
- robust BR action selection,
- active probing,
- node-locked evaluation.

---

# 2. Per-target crush plan and honest ceilings

---

## Target 1: Slumbot

### Honest assessment

Slumbot is your best realistic target.

Why?

- It is static.
- It is accessible.
- It has public API exposure.
- It is CFR/abstraction-lineage.
- It likely has action/card abstraction imperfections.
- It does not learn your exploit during the match.

But do not oversell it. Slumbot is not a fish. A true +50 bb/100 claim against it would require a discovered severe bug or a broken off-tree translation. Your current +2.2 bb/100 does not justify that.

### Honest bb/100 ceiling

| Exploit quality | Expected true winrate |
|---|---:|
| Current system, after noise | likely around **-3 to +6 bb/100** |
| Better fold-curve + river exploit | **+5 to +10 bb/100** |
| Strong tailored static exploit | **+8 to +15 bb/100** |
| Heavy reverse engineering, off-tree size sweeps, robust node model | **+15 to +25 bb/100** |
| >30 bb/100 | hype unless you discover a major implementation leak |

A realistic “crush” target is **+10 bb/100**. A very strong target is **+15 to +20**. Anything beyond that needs evidence.

---

## Slumbot: concrete leaks to probe

You should not assume the leak. You should actively map it.

### A. Bet-size fold/call/raise curves

This is probably the highest-EV area.

For each common node, estimate:

\[
P(\text{fold}), P(\text{call}), P(\text{raise}) \mid \text{street, line, board, size, blockers}
\]

Probe sizes:

- 20–25% pot
- 33% pot
- 50% pot
- 66–75% pot
- 100% pot
- 125–150% pot
- all-in thresholds where relevant

Look for discontinuities. Static abstraction bots often have response cliffs around sizes that map to different abstract actions.

Actionable hammer:

- If fold curve jumps from 47% to 61% between 75% and 100% pot, use the larger size with bluffs.
- If call frequency is inelastic from 50% to 100% pot, size up value.
- If raise response is underdeveloped versus small bets, block-bet thin and bluff wider.
- If raise response is overaggressive versus capped lines, induce.

---

### B. Off-tree bet sizes

This is where a static abstracted bot can leak.

Probe sizes not likely to be native abstraction sizes:

- 27% pot
- 42% pot
- 58% pot
- 83% pot
- 117% pot
- 143% pot

You are looking for translation mistakes:

- overfolds to weird overbets,
- underraises versus tiny bets,
- calls same range versus larger size,
- overuses one response bucket,
- treats 83% like 75% but gives you more value,
- treats 117% like 150% and overfolds.

Do not assume off-tree sizes are good. Some strong bots handle them smoothly. But if Slumbot has action abstraction artifacts, this is where you find them.

---

### C. Paired boards

Probe:

- paired flops: 772r, KK4r, 554tt,
- paired turns after c-bet/call,
- paired rivers after bet/bet,
- double-paired boards,
- trips/boat blocker effects.

Potential leaks:

- overfolding bluffcatchers because ranges are hard to represent,
- under-bluffing rivers when board pairs,
- overcalling because trips/boats are overestimated,
- poor distinction between blocker classes.

Hammer:

- If overfolding: bluff with relevant boat/trips blockers and low showdown value.
- If overcalling: thin-value merged ranges; reduce zero-equity bluffs.
- If underbluffing: overfold your bluffcatchers.
- If overbluffing: call down with blockers/unblockers selected by exact range model.

---

### D. Monotone and 4-flush boards

These are classic abstraction-stress spots.

Probe:

- monotone flop after SRP c-bet,
- turn four-flush,
- river four-flush after bet/bet,
- low monotone vs high monotone,
- A-high monotone boards,
- paired + flush boards.

Important blocker classes:

- nut-flush blocker,
- second-nut blocker,
- no-flush blocker,
- pair + flush blocker,
- straight-flush adjacent blockers.

Hammer:

- If Slumbot overfolds 4-flush rivers to large bets, bluff aggressively with nut blockers.
- If it overcalls with blocker-heavy bluffcatchers, value bet thinner and stop bluffing no-blocker trash.
- If it underbluffs monotone runouts, fold more bluffcatchers.
- If it overbluffs when checked to on 4-flush, bluffcatch wider with correct unblockers.

---

### E. Straightening rivers and 4-liners

Probe:

- one-card-to-straight rivers,
- four-liner boards,
- low connected boards,
- wheel-completing A/5 turns/rivers,
- Broadway straight completions.

Potential leaks:

- poor blocker valuation,
- overfolding non-straight bluffcatchers,
- underbluffing missed flush draws,
- overbluffing hands with irrelevant blockers.

Hammer:

- Bluff with straight blockers when fold curve says yes.
- Bluffcatch with hands that unblock missed draws.
- Overfold when villain’s betting range is value-heavy in that cluster.

---

### F. Thin-value thresholds

This is underused alpha.

Most exploit systems focus on bluffing overfolds. But against static bots, **thin value versus inelastic calls** can be just as profitable.

Map:

\[
P(\text{call}) \mid \text{size, line, board, villain range cap}
\]

Then compute value EV by hand class.

Hammer:

- If Slumbot calls too much versus 75% pot, value bet second pair/top pair weak kicker in the right nodes.
- If it folds too much versus 125%, polarize: bigger value, more bluffs.
- If it calls similarly versus 50% and 100%, choose 100% with value.
- If it calls much more versus 33% but not enough to justify value size-down, use small block-value with medium hands.

---

### G. Turn/river abstraction

Your old turn solve was deleted. That hurts. Turn/river are where Slumbot may leak most because abstraction burden explodes.

Probe lines:

- flop check/check → turn stab,
- flop c-bet/call → turn overbet,
- flop c-bet/call → turn check → river probe,
- delayed c-bet lines,
- check-raise flop → turn barrel,
- bet/check/bet river,
- block bet river after passive line,
- donk turns/rivers after range-shifting cards.

Static bots often have less precise strategy in low-frequency lines. Your active probing should deliberately visit these, but only with EV-safe candidate hands.

---

## Slumbot implementation plan

### Phase 1: Stop donating from the floor

Before hard exploiting, fix the obvious floor issues:

1. Preflop HU should be near exact for the actual stack/action menu.
2. River module should be EV-based, not frequency-based.
3. Stop using MDF as a primary defense versus a known static bot. MDF is insurance, not exploit.
4. Replace global fold-to-bet with per-node fold curves.
5. Add raise-risk modeling. Many “fold equity” exploits die to under-modeled raises.

---

### Phase 2: Build a Slumbot response map

For each candidate node cluster, randomize size among a small set and log response.

Minimum cluster features:

- street,
- position,
- pot type: SRP/3BP/4BP/limp,
- preflop aggressor,
- action line,
- board texture,
- turn/river texture transition,
- bet size as continuous log fraction of pot,
- effective SPR,
- hero blocker class,
- villain range cap estimate.

Model output:

- fold probability,
- call probability,
- raise probability,
- raise size distribution if relevant,
- showdown hand-class distribution after call.

Use Bayesian shrinkage so rare nodes inherit from parent buckets.

Example hierarchy:

```text
All river bets
  → river IP after bet/bet
    → flush-completing river
      → 4-flush
        → paired 4-flush
          → size 100–150% pot
            → nut-blocker / no-nut-blocker
```

You need partial pooling. Otherwise you overfit.

---

### Phase 3: River exploit first

River is the cheapest high-quality exploit because there is no future street.

For every river candidate action/size:

\[
EV_{\text{bet}} =
P_f \cdot pot
+
P_c \cdot [Equity \cdot (pot+bet) - (1-Equity)\cdot bet]
+
P_r \cdot EV_{\text{vs raise}}
\]

Use posterior samples of \(P_f, P_c, P_r\), not point estimates.

Then:

- value bet if LCB value EV > check EV,
- bluff if LCB bluff EV > check EV,
- choose size by LCB EV,
- if confidence is low, use floor.

This alone can move several bb/100 versus static over/underfolders.

---

### Phase 4: Turn barrel exploit

Turn exploit needs river continuation model.

Model:

- fold to turn bet,
- call range after turn call,
- raise frequency,
- river fold/call curve after turn call,
- river stab frequency when checked to.

Start with high-frequency nodes:

- IP c-bet flop → called → turn barrel,
- flop check/check → turn stab,
- OOP check-call flop → turn donk/probe opportunities,
- 3bet pot flop c-bet → turn jam/large barrel.

---

### Phase 5: Flop exploit

Flop exploit has highest volume but most future complexity.

Avoid pure fold-equity sizing. Instead, evaluate:

- immediate fold EV,
- turn realization after call,
- raise punishment,
- future barrel profitability,
- showdown realization when checking.

Use c-bet size sweeps on:

- dry A/K high boards,
- low disconnected boards,
- paired boards,
- monotone boards,
- two-tone connected boards,
- dynamic Broadway boards.

---

# 3. Supremus AI

## Honest caveat

I do **not** know Supremus AI’s exact current architecture. I will not pretend otherwise.

If it is truly in the strong HUNL family with CFVnet/search/re-solving lineage, then it is much less likely to have simple global fold/call leaks. These agents tend to be stronger in exactly the places where rule overlays fail.

So the honest answer is:

- You might overtake it if it is static, accessible, and has exploitable approximation/translation/value-network errors.
- You should not expect a Slumbot-style public-API reverse-engineering path unless you can collect enough hands and force enough off-distribution states.
- “Crushing Supremus” is hype without evidence.

## Honest bb/100 ceiling

| Scenario | Expected result |
|---|---:|
| Current bot with coarse exploit | likely losing, maybe **-15 to -3 bb/100** depending strength |
| Strong floor + bounded exploit | **-5 to +2 bb/100** |
| Static Supremus + enough API volume + discovered abstraction/value-net leak | **+3 to +8 bb/100** |
| “Crush” | not credible without a demonstrated structural leak |

## What to probe

If you get access, probe for:

### A. Off-tree sizing translation

Same as Slumbot, but expect smoother response.

Test:

- weird small bets,
- weird overbets,
- non-geometric turn/river sizing,
- all-in threshold sizes,
- min-raises,
- block bets.

If response is smooth and close to theory, abandon.

---

### B. CFV/value-net out-of-distribution spots

If it uses value networks or approximate search, look for OOD states:

- rare river textures,
- low-frequency turn cards,
- abnormal pot geometries,
- unusual SPRs,
- lines not common in training,
- weird check-raise lines,
- delayed overbets,
- donk lines after range-shifting cards.

The exploit is not “it folds too much globally.” The exploit would be:

> Force the search/value approximation into states where its continuation values are biased, then take actions that repeatedly harvest that bias.

That is hard.

---

### C. River blocker/value errors

Even strong agents can leak on river if abstraction/network cannot represent fine blocker classes.

Probe:

- 4-flush,
- paired 4-flush,
- four-liner straights,
- double-paired boards,
- nut-blocker overbets,
- no-blocker bluffcatch calls.

But again: no claim until measured.

---

# 4. GTO Wizard AI

## Honest assessment

This is not a “crush” target.

If GTO Wizard AI is playing a solved/near-solved strategy in a restricted action set, then the honest goal is **least loss**, not positive exploit.

The public AIVAT benchmark matters. If every agent loses and best is around **-3 bb/100**, that is strong evidence that:

1. Their strategy is hard to exploit.
2. Most agents lose more from their own floor errors than they gain from attempted exploits.
3. Positive winrate claims need serious evidence.

The complaint that it “hides behind its restriction to solving” is emotionally understandable but strategically irrelevant. If the game/action set is restricted to solved states, then that is the game being benchmarked. You cannot exploit off-tree leaks if off-tree actions are unavailable.

## Honest bb/100 ceiling

| Goal | Expected result |
|---|---:|
| Current system | likely worse than leaderboard best unless floor is upgraded |
| Strong least-loss system | **-4 to -2 bb/100** |
| Elite benchmark-tuned system | **-2 to 0 bb/100** |
| Positive EV | only plausible via bug, mismatch, implementation leak, or noise |

## Any exploitable static leak?

Possible but not something I would bank on:

- finite precision mixing errors,
- action abstraction mismatch,
- preflop/rake/stack setting mismatch,
- implementation bug,
- off-tree handling if open play allows off-tree sizes,
- deterministic RNG or sampling artifacts,
- timeout/mapping errors.

But if the benchmark is fixed-action solved play, the exploit-primary layer should mostly turn itself off. Your objective versus GTO Wizard should be:

1. minimize floor exploitability,
2. match action set exactly,
3. remove your own heuristic leaks,
4. use AIVAT/duplicate evaluation,
5. avoid fancy exploits unless statistically proven.

---

# 5. Ranked by attainable edge / effort

## 1. Slumbot — best target

**Edge potential:** high for a strong tailored exploit.  
**Effort:** medium-high.  
**Realistic ceiling:** **+8 to +15 bb/100**, stretch **+20 to +25**.

Why it is best:

- static,
- public,
- can be sampled,
- abstraction/action translation can be probed,
- exploit-primary is actually appropriate.

Main work:

- fold/call/raise curve model,
- off-tree size sweeps,
- blocker-aware river exploit,
- turn/river continuation model,
- robust LCB action selection.

---

## 2. Supremus — unknown/moderate target

**Edge potential:** unknown, likely modest.  
**Effort:** high.  
**Realistic ceiling:** **-5 to +3**, stretch **+5 to +8** only if structural leak exists.

Main work:

- determine stationarity,
- test off-tree response,
- probe value-net/OOD spots,
- use bounded exploit,
- do not assume crush.

---

## 3. GTO Wizard — least-loss target

**Edge potential:** very low.  
**Effort:** high if trying to gain positive EV.  
**Realistic ceiling:** **-4 to -1**, possible **0** with elite floor. Positive winrate is unlikely.

Main work:

- improve floor,
- match solved action set,
- eliminate your own river/preflop/turn leaks,
- do not over-exploit phantom leaks.

---

# 6. Where your real alpha is

Your real alpha is **not** the five poker books. It is not the 62-rule overlay. It is not matching solver \(P(\text{bet})\). It is not “GTO but with confidence nudges.”

Your real alpha, if built correctly, is:

## A. Opponent-specific static reverse engineering

For Slumbot especially, the edge is:

> public bot + stationary policy + enough hands + causal probing = exploitable response surface.

Most generic bots do not do this deeply. They play a solid floor and maybe adjust coarse stats. A true per-target response map is different.

---

## B. Active probing

This can be real alpha if you do it sanely.

You should not probe random obscure spots. Probe high-frequency, high-future-value nodes:

- BTN open/BB defend response,
- flop c-bet response in SRP,
- turn barrel response after common flop line,
- river fold/call curve after common polar line,
- 3bet pot c-bet response.

Probe by choosing between actions that are both plausibly close in EV, then use the observed response to reduce uncertainty.

Formula:

\[
\text{ProbeScore}(a) =
\text{LCB ImmediateEV}(a)
+
\lambda \cdot \text{ExpectedFutureEVGain}(a)
\]

Information gain should be measured in **future EV reduction of uncertainty**, not generic entropy.

---

## C. Robust exploit frontier

The edge is not merely “exploit hard.” The edge is:

> exploit hard only when the model justifies it; otherwise revert to floor.

That lets you capture big EV versus static/weak opponents without torching money versus strong/unknown ones.

---

## D. Paired/duplicate A/B harness

This is valuable. Keep it. Most exploit changes are noisy. Your harness is a real advantage if it prevents shipping fake alpha.

But your LBR is vacuous. Replace or demote it.

---

# 7. What you are missing that would actually move the crush

## 1. Per-action EV infrastructure

This is the biggest missing piece.

You need action EVs, not just action frequencies.

Store:

- action EV,
- counterfactual value,
- range at node,
- reach probability,
- strategy probability,
- regret,
- board/runout class,
- pot/SPR,
- line.

Without this, you cannot cleanly answer:

> “Is this exploit better than the floor?”

---

## 2. Node-locked exploit solver/evaluator

Build an evaluator that can node-lock the opponent model and compute best response.

Pipeline:

1. Learn opponent response model.
2. Node-lock villain policy.
3. Solve/roll out hero best response.
4. Compare to floor.
5. Generate candidate exploit actions.
6. Validate in paired A/B.

This replaces the vacuous LBR.

---

## 3. River-first exact exploit

Your river is blocker-aware analytic already. Make it fully opponent-model driven.

River is where you can get clean EV:

- exact hand enumeration,
- no future street,
- explicit fold/call/raise EV,
- easy confidence gating.

If you want fast bb/100 improvement versus Slumbot, start here.

---

## 4. Raise-response modeling

Your “fold-equity-optimal” sizing likely underestimates how much raises punish you.

For every bet candidate, you need:

- fold probability,
- call probability,
- raise probability,
- raise size distribution,
- EV versus raise.

A size with slightly higher folds but much higher raise punishment can be bad.

---

## 5. Range-composition model

Do not model villain only as “foldy” or “sticky.”

Model what hands reach each node.

You need:

- preflop range by action,
- postflop filtering by line,
- showdown-updated hand-class distributions,
- blocker-conditioned response estimates,
- passive-line range caps.

This is exactly where your current LBR is blind.

---

## 6. 6-max joint belief

Your 6-max architecture is currently not coherent for serious exploit.

“Each seat decides independently” fails because:

- ranges are jointly conditioned,
- card removal is multi-opponent,
- squeeze dynamics matter,
- one player’s overfold affects another’s incentive,
- multiway equities are non-separable.

For now, do not sell the system as a Pluribus killer. HU is where this architecture can actually become sharp.

---

# 8. The opponent model: what to model

You need separate models for:

## A. Villain response facing a bet

For each node:

\[
P(fold/call/raise \mid state, size)
\]

Inputs:

- street,
- position,
- pot type: SRP/3BP/4BP/limp,
- effective stack / SPR,
- action sequence,
- preflop aggressor,
- current aggressor,
- bet size as continuous pot fraction,
- board texture,
- turn/river transition,
- hero blocker class,
- estimated villain range cap,
- previous villain aggression/passivity.

Outputs:

- fold probability,
- call probability,
- raise probability,
- raise size distribution,
- uncertainty.

Use multinomial logistic/spline models with Bayesian shrinkage.

---

## B. Villain betting/stabbing model

When villain has initiative or opportunity:

\[
P(check/bet_s/bet_m/bet_l/overbet \mid state)
\]

Model:

- bet frequency by size,
- size distribution,
- aggression by board class,
- delayed c-bet frequency,
- probe frequency,
- river bluff frequency,
- under/overbluff by line.

---

## C. Showdown/range model

You only see villain cards at showdown, so use them hard.

Model:

- hand class after each line,
- missed draws that bluff,
- bluffcatch classes that call,
- slowplays,
- thin-value thresholds,
- blocker usage.

Use Bayesian filtering:

1. Start from preflop range.
2. Filter by each action likelihood.
3. At showdown, update action likelihood for the revealed hand class.
4. Propagate to similar node clusters.

---

## D. Sizing tells

For weak/exploitable bots, sizing tells can be huge.

Model:

\[
P(size \mid handclass, board, line)
\]

Examples:

- small bet = weak made hand,
- pot bet = polarized,
- overbet = underbluffed,
- block bet = capped thin value,
- check-raise size = value-heavy.

For strong bots, sizing tells may be small. For weak bots, this is where +300 to +700 bb/100 comes from.

---

## E. Type/drift/tilt model

For humans or adaptive agents:

- foldy/sticky/aggressive/passive type,
- tilt after losing big pot,
- adaptation to your overbets,
- change-point detection,
- recent-frequency drift.

For Slumbot, drift should be near zero. For unknown opponents, you need a stationarity detector.

---

# 9. How to learn fast and robustly online

## A. Use hierarchical Bayesian shrinkage

Do not create isolated buckets that need thousands of hands.

Example:

```text
Global river fold-to-bet prior
  → river IP/OOP
    → line class
      → board class
        → size curve
          → blocker class
```

Each child inherits from parent until enough data exists.

This gives you fast early estimates without insane overfitting.

---

## B. Use continuous size curves, not size bins only

For fold curves:

\[
P_f(size) = \sigma(\beta_0 + \beta_1 \log(size/pot) + spline(size) + board/line effects)
\]

Constrain or regularize the curve. Pure bins are noisy. But allow kinks/discontinuities for abstraction artifacts.

Best practical compromise:

- smooth logistic curve,
- plus learned “abstraction kink” effects at candidate sizes,
- Bayesian uncertainty on each.

---

## C. Use priors by opponent class

Initial prior should not be blank.

Use:

- GTO-ish prior for strong unknowns,
- population weak-bot prior,
- Slumbot-specific prior,
- Supremus-specific prior if data exists,
- human pool prior if relevant.

Early classifier:

- VPIP/PFR/3bet,
- fold to c-bet,
- aggression frequency,
- showdown looseness,
- river call frequency,
- sizing entropy.

After 50–200 hands, choose mixture weights over opponent types.

---

## D. Use active probing with budget

Active probing should be controlled.

Good probing spots:

- high-frequency,
- low immediate EV cost,
- likely future recurrence,
- likely to discriminate between opponent types,
- safe against raises.

Bad probing spots:

- rare river nodes,
- massive pot sacrifices,
- nodes where all candidate actions are far below floor,
- unknown raise response,
- multiway chaos.

Probe budget:

- versus static Slumbot: larger budget early, because information persists forever;
- versus adaptive opponent: smaller budget, because probes reveal you too;
- versus GTO Wizard: basically zero unless testing a suspected implementation leak.

---

# 10. Cheapest version that already improves/crushes the field

If you want the cheapest high-EV implementation, do this:

## MVP 1: River exploit engine

Replace river rules with robust EV optimization.

For each river:

1. Estimate villain range.
2. Estimate fold/call/raise response by size.
3. Enumerate exact equity versus call range.
4. Compute EV for check/call/bet sizes.
5. Choose action by lower-confidence EV.
6. Fall back to floor when uncertain.

This is the cleanest place to exploit Slumbot and weak bots.

---

## MVP 2: Bayesian fold/call/raise curves

Replace global stats and 62 nudges with:

- per-street,
- per-position,
- per-line,
- per-board-class,
- continuous size response curves.

Even a simple Bayesian logistic model will beat hand-written nudges.

---

## MVP 3: Common-node flop/turn exploit

Only handle high-volume nodes first:

- BTN SRP c-bet IP,
- BB facing c-bet,
- turn barrel after flop c-bet/call,
- river after bet/bet,
- 3bet pot flop c-bet.

Do not try to model the entire game tree equally. That dilutes sample and engineering effort.

---

## MVP 4: Slumbot-specific off-tree size sweeper

For Slumbot, create an experiment scheduler:

```text
Node cluster: IP SRP flop c-bet
Board class: A-high dry
Candidate sizes: 25, 33, 50, 75
Hands used: medium-equity/backdoor hands where EV gap is small
Goal: estimate fold/raise curve
Stop condition: confidence interval separates best size
```

Do the same for:

- paired flops,
- monotone flops,
- turn overbets,
- river 4-flush,
- river paired boards,
- block bets,
- overbets.

---

# 11. Final verdict

## Exploit-primary is correct for Slumbot and weak/static bots

But implement it as:

> robust posterior best response, not posterior-mean YOLO.

Against Slumbot, this is your main path to real edge.

Honest Slumbot target:

- **+10 bb/100**: realistic and strong.
- **+15 bb/100**: excellent.
- **+20 to +25 bb/100**: possible with serious reverse engineering.
- **+30+ bb/100**: hype unless a major bug/leak is found.

## Supremus is not a promised crush

I do not know the exact architecture. If it is strong CFVnet/search lineage, expect modest or no positive edge unless you discover a real static leak.

Honest target:

- **least-loss to small win**.
- **+5 bb/100** would already be a serious achievement.
- “Crush” is not justified.

## GTO Wizard is least-loss

Do not waste effort trying to “exploit-primary” a near-solved benchmark unless you have evidence of implementation leakage.

Honest target:

- minimize your own mistakes,
- aim near leaderboard best,
- positive EV is unlikely.

## Your real alpha

The real alpha is:

1. Slumbot-specific response modeling.
2. Active probing.
3. Robust exploit selection.
4. River/turn blocker-aware EV engine.
5. Node-locked opponent-model best response.
6. Paired A/B validation.

The missing crush-mover is not another book, not another rule, and not higher action-match accuracy.

It is:

> **a calibrated per-node opponent model connected to a real EV-based best-response engine.**
