# Open-source landscape / gaps / hardest spots — gpt-5.5

Below is the brutally honest version: your current **money edge is the adaptive exploit overlay**, but your **floor is too heuristic postflop**, and your **evaluation is too noisy to know which changes are real**. So the priority is:

1. **Make eval much lower variance.**
2. **Improve the floor only where it protects you from near-GTO / good opponents.**
3. **Do not replace your exploit overlay with a pure-GTO clone.**
4. **Use solvers / CFR / datasets as glue and calibration, not as an identity.**

---

# Q1. What to adapt from open source / public research

## 1. Solvers / solver outputs

### A. TexasSolver — you already have this, keep leaning on it

**Project:** TexasSolver  
**What to take:** Solver outputs, EVs, frequencies, node values, action EV gaps, board/runout coverage.  
**How it plugs into your engine:**

- Your planned supervised **GTO-floor advisor** should treat TexasSolver caches as the highest-quality labels.
- Do not train only action labels. Train:
  - action frequency target,
  - action EVs,
  - best-action EV gap,
  - node value,
  - confidence / OOD score.
- Use the advisor as a **postflop floor interpolator**, not as a hard policy.
- Feed your existing heuristic features too:
  - MC equity,
  - pot odds,
  - MDF estimate,
  - fold-equity estimate,
  - position,
  - SPR,
  - board texture,
  - range/nut advantage proxies,
  - blocker features.

**Concrete win:**  
Turns your heuristic floor from “equity + pot odds + MDF-ish” into “solver-shaped EV-aware policy,” especially on flops/turns where your current bot likely overfolds, over-donks, under-check-raises, or sizes badly.

**What not to do:**  
Do not make TexasSolver output the whole bot. Solver policy alone is your ceiling, not your edge. Solver outputs should stabilize the floor and give the exploit overlay a better base.

---

### B. `b-inary/postflop-solver` / open-source postflop solvers

**Project:** `b-inary/postflop-solver` / open-source Rust postflop solver ecosystem.  
**What to take:**

- Independent postflop solving implementation.
- DCFR/CFR-style solving loops.
- Tree/action abstraction handling.
- Batch generation of smaller turn/river subgames.
- Cross-validation against TexasSolver.

**How it plugs in:**

- Use it to generate **extra labels** where TexasSolver cache coverage is thin.
- Use it for **fast sanity checks** on suspicious spots:
  - OOP donk nodes,
  - monotone boards,
  - paired boards,
  - river bluffcatch nodes,
  - low-SPR 3bet pots.
- Use it to produce simplified trees for advisor training, not necessarily production-time solving.

**Concrete win:**  
More solver coverage without over-relying on one implementation. Also useful for detecting if a TexasSolver tree/config/action abstraction is producing weird artifacts.

**What not worth adapting:**  
Do not run a full real-time postflop solver on every hand unless latency and infra are trivial. Your current edge is the overlay; real-time full solving adds complexity and may slow adaptation.

---

### C. Public solver outputs / hand charts

**Project/data:** Public solved charts, community GTO charts, academic abstractions, sample solutions.  
**What to take:**

- Sanity checks for preflop/postflop frequencies.
- Board-class priors.
- Coarse population GTO heuristics.

**How it plugs in:**

- Use as weak labels or validation, not primary labels.
- Compare your advisor recommendations to public baselines on canonical nodes.

**Concrete win:**  
Cheap coverage and sanity checking.

**Warning:**  
Licensing/quality varies wildly. Many “public GTO” charts are simplified, rake-specific, range-specific, or just wrong. Do not train hard on them.

---

## 2. CFR-family frameworks

You already have:

- **CFR+ validated on Leduc** after fixing clairvoyant BR bug.
- **OpenSpiel Deep-CFR on NLHE fcpa**, working but CPU/traversal-bound.

That is the right posture: CFR is a validation/research tool for you, not your immediate production path.

---

### A. OpenSpiel

**Project:** Google DeepMind OpenSpiel  
**What to take:**

- CFR, CFR+, external sampling MCCFR, outcome sampling MCCFR.
- Best-response / exploitability tooling in toy and abstract games.
- Deep-CFR implementation patterns.
- Game-state and policy evaluation utilities.
- Exact exploitability in small games.

**How it plugs in:**

- Keep using OpenSpiel as your **algorithm lab**:
  - Leduc/Kuhn regression tests.
  - Small HUNL abstractions.
  - fcpa/limited-action NLHE abstractions.
- Use it to validate:
  - regret minimization correctness,
  - best-response correctness,
  - policy serialization,
  - LBR approximations,
  - evaluation harnesses.

**Concrete win:**  
Prevents subtle algorithmic bugs like the clairvoyant BR bug from leaking into production logic.

**What not worth doing:**  
Do not try to brute-force full NLHE Deep-CFR through OpenSpiel CPU traversals right now. You already observed the bottleneck. It is not the fastest route to strength.

---

### B. PokerRL / Eric Steinberger ecosystem

**Project:** PokerRL, Deep-CFR implementations, RL research tooling.  
**What to take:**

- Deep-CFR training architecture:
  - traversals,
  - advantage memory,
  - strategy memory,
  - reservoir sampling,
  - distributed actor/learner separation.
- Local Best Response / exploitability-style evaluators if available in your setup.
- NFSP/Deep-CFR baseline agents in small/abstract games.

**How it plugs in:**

- Use PokerRL ideas for your **advisor training infrastructure**, especially replay/reservoir memory and distributed sampling.
- Use its LBR-style tools to attack your bot offline.
- Use trained abstract agents as benchmark opponents.

**Concrete win:**  
Gives you engineering templates for scalable self-play/regret learning without inventing every component.

**What not worth adapting:**  
Do not replace your current exploit overlay with NFSP/Deep-CFR trained from scratch on huge NLHE. It will be expensive, brittle, and likely weaker than your current exploit layer for a long time.

---

### C. RLCard

**Project:** RLCard  
**What to take:**

- Lightweight baselines:
  - CFR,
  - NFSP,
  - DQN,
  - rule agents.
- Simple training/evaluation harnesses.
- Fast toy-game experiments.

**How it plugs in:**

- Use RLCard for cheap regression tests and benchmark opponents.
- Good for sanity-checking exploit overlay behavior against known weak archetypes.

**Concrete win:**  
Fast experimentation, low engineering cost.

**What not worth adapting:**  
RLCard is not where your strongest HUNL bot comes from. Use it as a testbed, not a source of final poker intelligence.

---

### D. CFR variants: what matters for you

#### CFR+

You already validated CFR+ on Leduc.

**Take:** correctness discipline, regret matching+, monotonic exploitability expectation in small games.  
**Win:** trustworthy solver/testing foundation.

#### Linear CFR / LCFR

**Take:** linearly weighted averaging of later iterations.  
**Win:** often better practical convergence than vanilla CFR.

#### Discounted CFR / DCFR

**Take:** discount positive/negative regrets and strategy accumulations.  
**Win:** common in modern postflop solving; can converge faster in large imperfect-information games.

**Use case for you:**  
If you generate more solver labels or build a mini-resolver, use DCFR/LCFR-style weighting.

#### MCCFR

**Take:** external sampling / outcome sampling.  
**Win:** cheaper traversals in large trees.

**Use case:**  
Training abstract subgames and test policies, not full production HUNL yet.

#### Deep-CFR

**Take:** regret/advantage approximation with networks.  
**Win:** can generalize across information sets.

**Use case for you:**  
Better as inspiration for your **supervised advisor** than as a direct production training loop.

#### NFSP

**Take:** average-policy vs best-response decomposition.  
**Win:** good conceptual baseline.

**Use case:**  
Train exploitable and semi-balanced benchmark opponents.

**Not production:**  
NFSP is slow, sensitive, and not the fastest way to beat your field.

#### ReBeL

**Project/method:** Recursive Belief-based Learning; public implementations exist but are not a plug-and-play HUNL solution.  
**What to take:**

- Public belief-state representation.
- Search/value-network combination.
- Depth-limited lookahead with learned continuation values.

**How it plugs in:**

- Use the idea for **depth-limited turn/river resolving**:
  - estimate ranges,
  - solve a small subgame,
  - use advisor/value network as leaf evaluator.

**Concrete win:**  
Can improve hard turn/river nodes without solving full games.

**Brutal truth:**  
Full ReBeL-style implementation is probably not worth it right now. It is high complexity and may distract from easier wins: advisor + better eval + targeted solving.

---

## 3. Card/action abstraction

This is a real gap. Your floor is currently heuristic postflop, and exact river equity by enumeration is not enough because poker decisions are range-vs-range, blocker-sensitive, and line-dependent.

---

### A. Potential-aware card abstraction

**Methods to adapt:**

- EHS / effective hand strength.
- HS² / hand strength squared.
- Rollout-based future equity distributions.
- Potential-aware clustering.
- Earth Mover’s Distance / distributional distance between hands.
- Board-class clustering:
  - paired,
  - monotone,
  - two-tone,
  - rainbow,
  - connected,
  - broadway-heavy,
  - low disconnected,
  - ace-high static,
  - dynamic straight/flush boards.

**Open-source sources to inspect/adapt:**

- OpenSpiel abstractions/examples.
- PokerRL lookup/card encoding systems.
- Academic poker abstraction repos where available.
- ACPC-era abstraction papers/logs.

**How it plugs in:**

- Add bucket features to the advisor:
  - current equity bucket,
  - future potential bucket,
  - nut potential,
  - blocker class,
  - draw class,
  - showdown value class.
- Use potential-aware buckets for:
  - turn barrel selection,
  - river bluff selection,
  - bluffcatch thresholds,
  - check-raise candidates,
  - donk suppression/permission.

**Concrete win:**  
Your bot stops treating “55% equity” hands as equivalent. A vulnerable top pair, a nut-flush blocker, and a weak made hand with no redraw are strategically different.

---

### B. Action abstraction

**Methods to adapt:**

- Solvers’ discrete sizing trees.
- Dynamic action sets based on SPR/position/street.
- Pot geometric sizing.
- Overbet inclusion on nut-advantage runouts.
- Small-block sizing in range-advantage spots.

**How it plugs in:**

Your engine already has fold-equity sizing. Replace/augment it with **street/node-specific allowed size families**:

- Flop:
  - 25–33% range bet sizes,
  - 50–75% polar sizes,
  - check-heavy options OOP.
- Turn:
  - geometric 66–125%,
  - protection/value sizes,
  - overbets on nut-advantage turns.
- River:
  - polar jam/overbet,
  - block bet,
  - thin value 33–50%,
  - check/foldcatch.

**Concrete win:**  
Bad sizing is one of the easiest ways for good bots to exploit a heuristic floor.

**What not to do:**  
Do not lock yourself into one solver’s fixed action abstraction if it kills exploit sizing. Against overfolders, your exploit overlay should still be allowed to increase bluff sizes/frequency within confidence bounds.

---

## 4. Variance reduction / evaluation

This is your most urgent infrastructure gap.

---

### A. AIVAT

**Method:** AIVAT variance reduction for imperfect-information games.  
**What to take:**

- Control variates for chance events.
- Control variates for actions where the strategy is known.
- Baseline value functions from approximate solvers/advisor.
- Unbiased EV estimate with much lower variance.

**How it plugs in:**

You need to log:

- full hand trajectory,
- private/public cards,
- action sequence,
- legal actions,
- pot/stacks,
- your action probabilities,
- showdown/fold result,
- estimated value at key states from advisor/solver cache.

Then implement AIVAT correction terms using:

- your own known mixed strategy,
- chance counterfactual values,
- advisor/solver value estimates as baselines.

**Concrete win:**  
Can reduce required hand volume by an order of magnitude or more if value baselines are decent.

**Brutal truth:**  
AIVAT is engineering-heavy. It is worth it eventually, but your cheapest immediate fix is duplicate/paired evaluation.

---

### B. Duplicate poker / common random numbers

**Method:** Evaluate A/B bots on same card sequences, seat-swapped.  
**What to take:** Duplicate match design from ACPC-style evaluation.  
**How it plugs in:**

For every seed/deck sequence:

1. Bot A plays BTN/SB with cards/deck sequence.
2. Bot B plays BB.
3. Replay same sequence with seats swapped:
   - Bot B gets A’s previous seat/cards.
   - Bot A gets B’s previous seat/cards.
4. Score pairwise difference.

**Concrete win:**  
Massive variance reduction with much less complexity than AIVAT.

**This is the cheapest fix. Do this first.**

---

### C. Local Best Response / LBR

**Projects:** PokerRL-style LBR, OpenSpiel best-response tools, custom LBR.  
**What to take:**

- Approximate local exploitability estimator.
- Agent that sees its own cards/public cards and uses approximate rollout/equity to greedily exploit your policy.

**How it plugs in:**

- Run LBR against:
  - floor only,
  - floor + advisor,
  - floor + overlay,
  - individual overlay rules.
- Track where LBR prints money:
  - overfold nodes,
  - overbluff nodes,
  - bad river calls,
  - bad donk frequencies,
  - sizing tells.

**Concrete win:**  
Finds tactical leaks far faster than waiting for noisy match EV.

**Warning:**  
LBR is not true exploitability in full NLHE. Treat it as a leak detector, not final truth.

---

## 5. Continual re-solving / depth-limited subgame solving

### A. DeepStack/Libratus-style continual resolving

**Method:** Real-time subgame solving from current public state/ranges.  
**Open-source fill-ins:** No complete open-source Libratus/DeepStack clone worth copying 1:1. Use TexasSolver/open postflop solver + your range tracker.  
**What to take:**

- Range estimation.
- Public-tree subgame solving.
- Depth-limited lookahead.
- Leaf value approximation.
- Safe-ish resolving discipline.

**How it plugs in:**

Start with targeted, offline/nearline resolving:

- Precompute common turn/river nodes.
- Solve only high-impact spots:
  - 3bet pots,
  - turn overbet nodes,
  - river polar nodes,
  - monotone/paired boards,
  - facing river large bet.
- Use your advisor as the fallback when no solve exists.
- Use exploit overlay to nodelock opponent tendencies:
  - overfolds to turn barrel,
  - underbluffs river,
  - overcalls small bets,
  - over-donks,
  - folds too much to XR.

**Concrete win:**  
Better floor in exactly the places your heuristic loses to near-GTO.

**What not worth doing yet:**  
Full continual re-solving every hand/street with large trees. It is complex and can make the bot slower without beating your current exploit gains.

---

## 6. Hand-history datasets

### A. PokerBench — you already have 563k labeled GTO decisions

**What to take:** This should be your main supervised advisor dataset after TexasSolver caches.  
**How it plugs in:**

- Train advisor to predict:
  - action class,
  - action distribution,
  - EV gap,
  - fold/call/raise frequencies,
  - confidence.
- Hold out by board class and line, not random rows only.

**Concrete win:**  
Fastest path to improving floor.

**Warning:**  
Action accuracy alone is misleading. Measure EV loss where possible.

---

### B. Pluribus 10k hands — you already have them

**What to take:**

- Population of strong-agent lines.
- Multiway/sizing sanity if applicable.
- Frequencies for unusual lines:
  - donks,
  - overbets,
  - check-raises,
  - delayed c-bets.

**How it plugs in:**

- Use as weak behavioral prior / qualitative audit.
- Do not imitate blindly.
- Extract board/action statistics:
  - where does it check back?
  - where does it overbet?
  - where does it trap?
  - how often does it bluffcatch?

**Concrete win:**  
Good for spotting “our heuristic never does this” blind spots.

**Warning:**  
10k hands is tiny. Not enough to train a policy.

---

### C. Slumbot fold-curve — you already have this

**What to take:** Opponent-specific exploit prior.  
**How it plugs in:**

- Keep using it in overlay.
- Convert to nodelock tendencies:
  - fold vs size,
  - street,
  - line,
  - position,
  - board class.
- Use confidence gates and caps, as you already do.

**Concrete win:**  
This is already your measured edge: +49 bb/100 vs Slumbot with overlay.

**Do not dilute this into pure GTO.**

---

### D. PHH / PokerKit hand-history format

**Project:** PokerKit / PHH ecosystem.  
**What to take:**

- Standardized hand-history representation.
- Parser/replayer format.
- Dataset interchange.

**How it plugs in:**

- Normalize:
  - Slumbot hands,
  - Pluribus hands,
  - self-play logs,
  - ACPC logs,
  - solver node tests,
  - human hand histories.
- Build one replay/evaluation pipeline.

**Concrete win:**  
Less custom glue. Better reproducibility.

---

### E. IRC Poker Database

**Dataset:** Old IRC poker hand database.  
**What to take:**

- Human population tendencies.
- Very rough archetype priors:
  - nit,
  - station,
  - maniac,
  - loose-passive,
  - overfolder.

**How it plugs in:**

- Train opponent-model priors, not GTO floor.
- Extract population stat distributions:
  - VPIP,
  - PFR,
  - aggression,
  - fold-to-bet,
  - showdown frequency.

**Concrete win:**  
Useful for exploit overlay priors when opponent sample is tiny.

**Warning:**  
Old, noisy, often limit/ring-game, not modern HUNL GTO. Do not train strategic decisions directly from IRC hands.

---

### F. ACPC logs / dealer / benchmark ecosystem

**Project/data:** Annual Computer Poker Competition infrastructure and logs.  
**What to take:**

- Match protocol.
- Duplicate match design.
- Historical bot logs where available.
- Benchmark agents if runnable.

**How it plugs in:**

- Use ACPC-style dealer for duplicate A/B testing.
- Replay historical logs to stress parsers/range tracking.
- Benchmark against old agents if available.

**Concrete win:**  
Better evaluation discipline.

---

### G. Other public hand histories

Examples:

- Kaggle poker datasets.
- Publicly shared online hand histories.
- Hand-history corpora from research repos.
- PokerStars/ACR-style HH dumps where legally available.

**Use for:**

- Opponent modeling.
- Population exploit priors.
- Parser robustness.
- Rare line collection.

**Do not use for:**

- Hard GTO floor labels.
- Blind imitation.

**Reason:**  
Human data is contaminated by rake, stake, table type, meta, HUD ecology, and bad play.

---

# Q2. Your biggest gaps vs strongest bots, ranked

## 1. Evaluation noise / inability to tell real improvement from variance

**Impact:** Highest.  
Your Slumbot 400-hand +/-70 to 110 bb/100 CI is too noisy. You cannot prune/consolidate confidently.

**Open-source/project fill:**  
ACPC-style duplicate evaluation, OpenSpiel exploitability/BR tools, PokerRL LBR ideas, AIVAT literature.

**Adaptation:**

- First implement duplicate A/B self-play.
- Then LBR leak testing.
- Then AIVAT once logging/value baselines are mature.

**Concrete win:**  
You stop shipping changes based on noise.

---

## 2. Postflop floor is heuristic, not range/EV-policy aware

**Impact:** Very high.  
This is why floor loses to near-GTO. MC equity + pot odds + MDF is not enough.

**Open-source/project fill:**  
TexasSolver, `postflop-solver`, PokerBench, OpenSpiel/PokerRL abstraction tools.

**Adaptation:**

- Train supervised GTO advisor.
- Use solver EV gap, not just labels.
- Blend with heuristic floor using confidence gates.
- Keep exploit overlay separate.

**Concrete win:**  
Floor loss vs near-GTO should shrink. Overlay then prints from a stronger base.

---

## 3. River exact equity is not equivalent to river strategy

**Impact:** Very high.  
Exact enumeration gives hand equity, but river decisions need:

- range distribution,
- blocker effects,
- MDF by range,
- opponent bluff/value composition,
- bet-size-dependent indifference,
- card removal,
- line history.

**Open-source/project fill:**  
TexasSolver river nodes, postflop solver, LBR leak tests.

**Adaptation:**

- Build river-specific advisor.
- Train on solver river nodes heavily.
- Add blocker/nut-class features.
- Separate:
  - bluffcatch,
  - thin value,
  - block bet,
  - polar bluff,
  - give-up.

**Concrete win:**  
Stops bleeding in the most expensive nodes.

---

## 4. No robust turn/river resolving

**Impact:** High.  
Strong bots win by recalculating strategy after public-card/range shifts.

**Open-source/project fill:**  
TexasSolver/open postflop solver + ReBeL/DeepStack-style ideas.

**Adaptation:**

- Do targeted depth-limited solving for common high-EV spots.
- Use your advisor as leaf/value approximation.
- Use overlay to nodelock opponent deviations.

**Concrete win:**  
Better on the exact streets where stack commitment happens.

---

## 5. Action abstraction/sizing is likely too hand-built

**Impact:** High.  
Bad sizings are exploitable even if fold/call/raise direction is decent.

**Open-source/project fill:**  
TexasSolver trees, public solver configs, postflop solver action abstraction.

**Adaptation:**

- Learn size-family selection by board/line/SPR.
- Allow exploit overlay to deviate from GTO sizes when opponent fold curve supports it.

**Concrete win:**  
More EV from value hands and bluffs; fewer sizing tells.

---

## 6. Range tracking likely weaker than strongest bots

**Impact:** High.  
If your overlay is stat-keyed but range estimates are rough, exploit decisions can fire in the wrong composition spots.

**Open-source/project fill:**  
Solver range mechanics, OpenSpiel information-state discipline, PokerKit/PHH replay tools.

**Adaptation:**

- Maintain explicit weighted ranges through the hand.
- Update by opponent action likelihood.
- Use population/Slumbot fold curves as priors.
- Feed range summaries into advisor/overlay.

**Concrete win:**  
Overlay becomes more surgical and less noisy.

---

## 7. Potential-aware card abstraction missing or underdeveloped

**Impact:** Medium-high.  
Equity-only abstraction misses future playability.

**Open-source/project fill:**  
PokerRL/OpenSpiel encodings, academic abstraction methods.

**Adaptation:**

- Add EHS/future-equity-distribution features.
- Cluster hand classes by future potential.
- Use on flop/turn barrel and bluffcatch decisions.

**Concrete win:**  
Better multi-street planning.

---

## 8. Opponent modeling confidence and nonstationarity

**Impact:** Medium-high.  
You already have confidence-gated caps, which is good. But strongest exploiters adapt by archetype and by node.

**Open-source/project fill:**  
Human HH datasets, PHH pipeline, Bayesian stat models.

**Adaptation:**

- Bayesian priors for stats.
- Decay older observations.
- Separate global/player/node tendencies.
- Track uncertainty and avoid overfitting tiny samples.

**Concrete win:**  
Overlay remains profitable without spazzing into variance.

---

## 9. Full Deep-CFR/ReBeL-scale training

**Impact:** Long-term high, short-term low.  
This is not your current bottleneck.

**Open-source/project fill:**  
OpenSpiel, PokerRL, Deep-CFR repos.

**Adaptation:**  
Keep as research track. Use pieces for advisor/value networks.

**Concrete win:**  
Possible future architecture improvement.

**Not worth now:**  
Full from-scratch HUNL Deep-CFR/ReBeL is too expensive relative to advisor + solver-cache interpolation.

---

# Q3. Benchmarking beyond Slumbot

## Cheapest immediate fix: duplicate A/B evaluation

Do this before AIVAT.

### Wire it like this

Build an internal match runner:

- deterministic deck seed,
- same blinds/stacks,
- same initial conditions,
- bot A vs bot B,
- then seat/card swapped replay,
- record paired EV difference.

Measure:

- bb/100 paired mean,
- paired standard error,
- confidence interval,
- per-street EV contribution,
- showdown vs non-showdown,
- all-in adjusted EV if relevant,
- node tags:
  - SRP,
  - 3bet pot,
  - OOP,
  - IP,
  - monotone,
  - paired,
  - river facing bet,
  - donk node,
  - check-raise node.

**Why this first:**  
It is much easier than AIVAT and will immediately reduce noise in A/B testing.

---

## Second fix: LBR leak detector

Implement or adapt Local Best Response.

### How

Create an opponent that:

- estimates your strategy from logs or by querying your policy,
- uses approximate equity/rollouts,
- greedily chooses high-EV exploits,
- optionally uses restricted action set:
  - fold,
  - call,
  - 33%,
  - 75%,
  - pot,
  - jam.

Run LBR against:

1. floor only,
2. floor + fixed donk cap,
3. floor + advisor,
4. floor + overlay,
5. overlay variants.

**Measure:**

- LBR bb/100 vs your bot,
- biggest exploited lines,
- fold-to-raise leaks,
- river overcall/overfold,
- bluff frequency leaks.

**Concrete win:**  
Finds leaks faster than Slumbot volume.

---

## Third fix: solver-node benchmark suite

Use your TexasSolver caches and PokerBench.

### Construct held-out test sets

By node type:

- flop c-bet IP SRP,
- OOP check response,
- facing flop raise,
- turn barrel after c-bet called,
- delayed c-bet,
- river facing polar bet,
- river thin value/block bet,
- 3bet pot low SPR,
- monotone board,
- paired board,
- four-straight/four-flush river.

### Metrics

Do not rely on action accuracy alone.

Use:

- EV loss vs solver best action,
- EV loss of chosen mixed strategy,
- KL divergence to solver freq,
- top-2 action inclusion,
- blunder rate:
  - > 25 mbb,
  - > 50 mbb,
  - > 100 mbb,
- OOD confidence calibration:
  - when advisor says low confidence, is EV error actually higher?

**Concrete win:**  
You can improve the floor without playing millions of hands.

---

## Fourth fix: OpenSpiel exact exploitability in small abstractions

Use OpenSpiel for:

- Leduc,
- Kuhn,
- small HUNL abstractions,
- fcpa variants,
- limit abstractions.

**Purpose:**  
Not to prove full NLHE strength, but to regression-test algorithmic correctness.

**Concrete win:**  
Catches bugs like your clairvoyant BR bug.

---

## Fifth fix: benchmark opponent zoo

Create/run a stable suite:

### A. Rule-based archetypes

- Nit overfolder.
- Calling station.
- Maniac.
- Fit-or-fold.
- River underbluffer.
- Turn overfolder.
- Flop c-bet overfolder.
- Over-donker.
- Over-check-raiser.
- Min-bet fish.
- Jam-heavy bot.

**Why:**  
Your overlay should crush these. If a change reduces exploit EV here, be suspicious.

### B. RL baselines

From RLCard/PokerRL/OpenSpiel:

- CFR agents in small games.
- NFSP agents.
- DQN-style weak agents.
- Deep-CFR abstract agents if feasible.

**Why:**  
Stable reproducible baselines.

### C. Historical ACPC agents/logs

If runnable:

- ACPC dealer/protocol.
- Old HUNL agents.
- Limit agents for harness validation.

**Why:**  
Useful standardized competition infrastructure.

### D. Slumbot

Still useful, but only with bigger samples.

For Slumbot specifically:

- 400 hands is not enough.
- Target thousands to tens of thousands if API/terms allow.
- Segment by:
  - position,
  - street,
  - pot type,
  - overlay fired vs not fired,
  - showdown/non-showdown.
- Use CUPED/control-variate-ish analysis if you have baseline value estimates.

---

## AIVAT wiring plan

Do after duplicate/LBR.

### Required logs

For every decision:

- full public state,
- private hand,
- legal actions,
- pot/stacks,
- board,
- betting line,
- your mixed action probabilities,
- opponent action observed,
- value estimate from advisor/solver,
- chance event probabilities.

### Baseline value source

Use:

- TexasSolver cache value where available,
- advisor value elsewhere,
- heuristic value as fallback.

### Implementation strategy

Start with chance-event control variates only:

- flop/turn/river card variance reduction.

Then add known-strategy action correction for your own mixed actions.

**Expected win:**  
Much tighter CIs, especially for A/B testing variants.

**Caution:**  
Bad value baselines reduce effectiveness but should not bias if implemented correctly. Incorrect information-set conditioning can bias results. Test on Leduc/OpenSpiel first.

---

# Q4. Hardest NLHE spots you must master

## 1. River facing large bet / jam

**Why this is hard:**  
Exact equity enumeration is insufficient. Need opponent range composition, blocker logic, MDF, pot odds, and population under/overbluff tendencies.

**Where your floor likely fails:**

- Overcalls because hand equity looks okay.
- Overfolds because MDF estimate is crude.
- Ignores blockers.
- Misreads underbluffed lines.
- Calls too much vs value-heavy nodes.
- Folds too much vs overbluffing profiles.

**Attack with your assets:**

- Mine TexasSolver river nodes.
- Train river-specific advisor.
- Add features:
  - blocker to nuts,
  - blocker to missed draws,
  - unblock value,
  - unblock bluffs,
  - showdown class,
  - range percentile,
  - line-based opponent bluff prior.
- Overlay:
  - if opponent underbluffs river, reduce bluffcatch frequency hard.
  - if opponent overbluffs missed draws, widen calls with correct blockers.
- Benchmark with LBR specifically on river nodes.

**Impact:** Highest.

---

## 2. Turn barrel/check decisions after flop c-bet gets called

**Why hard:**  
This is where flop equity realization turns into range-polarization. Heuristic MC equity often misfires.

**Common leaks:**

- Barreling hands with equity but bad blockers.
- Giving up good blocker bluffs.
- Failing to overbet nut-advantage turns.
- Betting too merged OOP.
- Under-checking medium-strength SDV.

**Attack:**

- Use TexasSolver turn caches heavily.
- Generate more turn solves on:
  - overcards,
  - flush-completing turns,
  - straight-completing turns,
  - paired turns,
  - low bricks.
- Advisor target:
  - barrel/check frequency,
  - sizing family,
  - EV gap.
- Add potential-aware abstraction:
  - equity now,
  - equity on future rivers,
  - nut improvement potential,
  - blocker to continuing range.
- Overlay:
  - increase barrel frequency vs turn overfolders.
  - reduce bluffs vs stations.
  - choose larger sizes vs known size-inelastic folders.

**Impact:** Very high.

---

## 3. OOP single-raised pots after checking

**Why hard:**  
OOP strategy is check-heavy, mixed, and sensitive. Your bot already had over-donk issues, which is a symptom.

**Likely leaks:**

- Donking too often.
- Not check-raising enough in right classes.
- Check-calling wrong marginal hands.
- Check-folding too much on range-neutral boards.
- Bad delayed aggression.

**Attack:**

- Keep donk frequency capped.
- Use solver cache to define legal donk board classes:
  - low connected boards where BB has nut/2pair advantage,
  - certain paired/low boards,
  - not generic equity leads.
- Train advisor on OOP nodes separately.
- Add check-raise candidate features:
  - nutted value,
  - combo draws,
  - backdoor equity,
  - blockers to continues.
- Overlay:
  - vs over-cbettors, raise more with solver-approved candidates.
  - vs under-cbettors, stab turns more.
  - vs folders to XR, polarize and increase XR bluff frequency.

**Impact:** Very high.

---

## 4. 3bet/4bet pots, low SPR

**Why hard:**  
Ranges are narrow, equities run close, mistakes are expensive, and stack-off thresholds differ from SRP.

**Likely leaks:**

- Overfolding top-pair/overpair class.
- Misplaying AK/AQ high-card equity.
- Bad small c-bet frequency.
- Not understanding range advantage on A/K high boards.
- River commitment mistakes.

**Attack:**

- Generate dedicated TexasSolver trees for common 3bet pots:
  - BTN vs BB,
  - SB vs BTN,
  - BB vs BTN,
  - 4bet pot BTN/SB if relevant.
- Advisor should include pot-type embedding:
  - SRP,
  - 3bet,
  - 4bet,
  - limp/iso if applicable.
- Sizing abstraction:
  - small flop range bet,
  - turn geometric jam setup,
  - river jam/block.
- Overlay:
  - exploit opponents who overfold to small c-bets in 3bet pots.
  - reduce bluff punts vs stations.

**Impact:** High.

---

## 5. Monotone boards and flush-completing runouts

**Why hard:**  
Equity realization and blocker logic dominate. Heuristic equity often overvalues non-flush made hands.

**Likely leaks:**

- Overbluffing without suit blockers.
- Overcalling without flush blockers.
- Betting too merged.
- Missing small block bets.
- Misplaying nut-flush blocker.

**Attack:**

- Board-class-specific solver cache expansion.
- Advisor features:
  - suit blocker rank,
  - nut-flush blocker,
  - second-nut blocker,
  - no-suit vulnerability,
  - made flush class.
- Overlay:
  - vs overfolders, bluff with correct blockers.
  - vs calling stations, value bet thinner, bluff less.

**Impact:** High.

---

## 6. Paired boards / trips/boat asymmetry

**Why hard:**  
Nut advantage shifts sharply by preflop range and line. Many heuristics over-cbet or overfold.

**Likely leaks:**

- Betting too much on boards that favor BB.
- Not recognizing range advantage on high paired boards.
- Bluffcatching badly on paired rivers.
- Missing overbets when holding nut advantage.

**Attack:**

- Generate solver labels for:
  - paired flop,
  - paired turn,
  - paired river.
- Add features:
  - trips availability by range,
  - boat combos,
  - overpair vulnerability,
  - kicker relevance.
- Overlay:
  - punish opponents who overfold paired boards.
  - reduce bluffcatch vs underbluffed paired-board aggression.

**Impact:** High.

---

## 7. Four-straight / four-flush rivers

**Why hard:**  
Single-card blockers matter enormously. Equity enumeration helps, but range/blocker strategy still matters more.

**Likely leaks:**

- Calling with bluffcatchers that block bluffs.
- Bluffing without key blocker.
- Missing mandatory bluffs with nut blocker.
- Overvalue-betting non-nut made hands.

**Attack:**

- River advisor specialization.
- Solver cache expansion on these runouts.
- Blocker feature engineering:
  - nut straight blocker,
  - nut flush blocker,
  - unblock folds,
  - unblock calls.
- Overlay:
  - vs overfolders, bluff blocker-heavy combos aggressively.
  - vs stations, stop non-nut bluffing.

**Impact:** Medium-high.

---

## 8. Facing raises, especially turn raises

**Why hard:**  
Turn raises are often underbluffed in human pools but balanced in solver pools. Your response must be opponent-dependent.

**Likely leaks:**

- Overfolding vs aggressive bots.
- Overcalling vs value-heavy humans.
- 3bet/jam mistakes with draws.
- Ignoring blockers.

**Attack:**

- Solver cache for raise nodes.
- Overlay stat:
  - raise frequency by street,
  - raise after call line,
  - showdown after raise,
  - aggression by board class.
- Confidence-gated exploit:
  - underbluffer: fold more.
  - overraiser: call/3bet more with correct blockers/equity.

**Impact:** Medium-high.

---

## 9. Thin river value and block betting

**Why hard:**  
Heuristic floors often polarize too much or check too much.

**Likely leaks:**

- Missing thin value vs stations.
- Betting too thin vs check-raise/jam-heavy opponents.
- Failing to block bet marginal hands.
- Using bad sizes.

**Attack:**

- River solver labels.
- Opponent model:
  - call river frequency,
  - raise river frequency,
  - fold to small bet,
  - showdown weakness.
- Overlay:
  - value thinner vs calling stations.
  - block bet more vs passive opponents.
  - check more vs aggressive raisers.

**Impact:** Medium-high, especially in exploitable fields.

---

# What I would prioritize next

## Immediate 1–2 week priority

1. **Duplicate A/B evaluator.**
2. **Solver-node EV-loss benchmark.**
3. **LBR leak detector prototype.**
4. **Train first advisor version on TexasSolver + PokerBench.**
5. **Blend advisor conservatively into postflop floor.**

This gives you measurable progress without killing the exploit edge.

---

## Medium priority

1. Expand TexasSolver/open-solver coverage on:
   - river facing bet,
   - turn barrel spots,
   - OOP SRP,
   - 3bet pots,
   - monotone/paired boards.
2. Add potential-aware hand features.
3. Improve range tracker.
4. Add node-specific overlay priors instead of only broad stat keys.
5. Start AIVAT after logs/value estimates are solid.

---

## Low priority / likely distraction

1. Full HUNL Deep-CFR from scratch right now.
2. Full ReBeL clone.
3. Blind Pluribus imitation.
4. Training strategy from IRC/human HH.
5. Pure-GTO policy replacement.
6. Huge fixed action abstraction that prevents exploit sizing.
7. Real-time full resolving every hand before you have lower-variance eval.

---

# Bottom line

Your best path is not “become Slumbot.” Slumbot-like pure GTO is a **floor**, and you already measured that the **overlay is the profit center**.

The correct architecture is:

```text
solver-calibrated preflop
        +
supervised postflop GTO-floor advisor
        +
range-aware heuristic fallback
        +
confidence-gated exploit overlay
        +
low-variance duplicate/LBR/AIVAT evaluation
```

Use open source to fill infrastructure and calibration gaps:

- **TexasSolver / postflop-solver:** labels and targeted subgame solves.
- **PokerBench:** supervised GTO advisor.
- **OpenSpiel:** correctness, CFR/BR/exploitability tests.
- **PokerRL/RLCard:** baselines, LBR ideas, Deep-CFR/NFSP scaffolding.
- **PHH/PokerKit/ACPC:** hand-history and evaluation plumbing.
- **AIVAT/duplicate poker:** variance reduction.

Do not copy a pure-GTO bot 1:1. Strength comes from a robust floor plus an exploit layer that is allowed to deviate when the evidence is strong.
