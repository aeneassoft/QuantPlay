# Hard/valuable spots + data + OpenSpiel — GPT-5.5

## Brutal bottom line

Your biggest leak is not “needs more neural magic.” It is that the current core is strategically blind in the exact HUNL nodes where money moves:

- **fcpa = fold/call/pot/all-in** cannot express small flop bets, geometric turn bets, river block bets, or overbets correctly.
- **20-dim strength buckets** collapse hands that are strategically opposite: e.g. same equity, different blockers; same pair, different kicker; same draw, different nut potential.
- Beating call-station / always-fold / random proves plumbing, not GTO quality.
- The Leduc DCFR+ result is useful evidence that the update path works, but it does **not** validate HUNL strength.

I cannot honestly assign exact bb/100 loss by spot without your hand-attribution logs vs GTO Wizard. The bb/100 bands below are **directional estimates**, not measured facts from your build. You should make the next GTO Wizard A/B log every hand into these spot buckets and compute actual contribution.

---

# 1. Hardest + most valuable HUNL spots

## Ranked by difficulty × EV leverage for your current architecture

### 1. River polarized decision nodes: bluff-catching, bluff selection, thin value

**Examples**

- Facing river bet/overbet after flop c-bet + turn barrel.
- Missed flush/straight draw rivers.
- Paired rivers after turn aggression.
- River all-in / 1.25x / 2x pot spots.
- Bluff-catching with one-pair / bluff-catcher class hands.
- Choosing bluffs with correct blockers and unblockers.

**Likely EV leverage:** very high. In weak HUNL bots this can easily be a **double-digit bb/100 class leak**, but your exact number is unmeasured.

**Why hard for your current fcpa + 20-dim bucket net**

- River decisions are terminal: one bad call/fold loses a full bet immediately.
- Bluff-catch thresholds are size-sensitive.  
  - 0.5 pot needs ~25% equity.
  - 1 pot needs ~33%.
  - 2 pot needs ~40%.
  Your current pot/all-in sizing cannot represent these thresholds well.
- Strength buckets do not know blockers:
  - Nut flush blocker vs non-blocker.
  - Straight blocker.
  - Blocking villain’s bluffs vs unblocking folds.
  - Missed draw unblockers.
- Same “one-pair bucket” can be pure call, mix, or pure fold depending on suit/rank removal and line.

**Next-run requirements**

Bet sizes needed:

- River: **0.5 / 0.75 / 1 / 1.25 / 2 / all-in**
- Do not force every size everywhere if compute explodes, but river overbet sizes are non-negotiable if you want Wizard-like postflop quality.

Features needed:

- Exact card occupancy: private + board rank/suit.
- Hand class + kicker.
- Flush/straight blocker flags.
- Missed draw flags.
- Board texture: paired, monotone, 4-flush, 4-straight, disconnected, etc.
- Full action history: who bet flop/turn, bet sizes, check-throughs, raises.

**Validation priority:** highest. Build a PokerBench/GTO Wizard slice specifically for river facing-bet and river betting nodes, stratified by bet size and board texture.

---

### 2. Turn barreling / double-barrel give-up / overbet setup

**Examples**

- Flop c-bet gets called, turn changes texture.
- Turn completes flush/straight.
- Turn pairs board.
- Turn overcard shifts range advantage.
- Combo draws deciding between barrel/check.
- Made hands deciding protection/value/check.
- Turn overbet when bettor is polarized vs caller condensed.

**Likely EV leverage:** very high. Probably another **double-digit bb/100 class** candidate if currently mishandled.

**Why hard for your current architecture**

- Turn is where river EV is built. Bad turn betting creates impossible river ranges.
- Current fcpa pot betting is too coarse:
  - Many GTO turn bets are 0.5–0.75 pot.
  - Polar spots often use 1.25–2 pot.
  - Pot-only makes your strategy too chunky and easy to punish.
- Strength bucket does not distinguish:
  - Pair + flush draw.
  - Nut draw vs dominated draw.
  - Open-ender vs gutshot.
  - Overcards + backdoor equity.
  - Made hand with redraw vs vulnerable made hand.
- It cannot identify turn-card effects:
  - Completes flush.
  - Completes straight.
  - Pairs board.
  - Is overcard to board.
  - Bricks all draws.

**Next-run requirements**

Bet sizes needed:

- Turn: **0.5 / 0.75 / 1 / 1.25 / 2 / all-in**
- The **1.25 and 2 pot** sizes matter specifically for polarized-vs-condensed nodes.

Features needed:

- Draw class: FD, NFD, OESD, gutshot, combo draw, backdoor draw.
- Blocker class.
- Turn-card texture delta: brick/completer/pair/overcard.
- SPR and pot geometry.

**Validation priority:** top 2. Track after-flop-cbet-called turn nodes separately.

---

### 3. High-frequency flop c-bet / check / check-raise strategy in single-raised pots

**Examples**

- BTN raises, BB calls.
- A-high dry boards.
- K-high/Q-high semi-dry boards.
- Low connected boards.
- Paired boards.
- Monotone/two-tone boards.
- BB check-raise decisions.
- IP small range bet vs check-back.

**Likely EV leverage:** high because frequency is massive. Individual pots are smaller, but errors occur constantly.

**Why hard for current architecture**

- fcpa pot-only flop c-bet is a major abstraction problem.
  - Many solver strategies use **small 0.25–0.33 pot** or **0.5 pot** range bets.
  - Pot betting forces a more polarized strategy and distorts BB defense.
- Strength buckets miss board/range interaction:
  - A72r is not 987ss.
  - KKT is not 654 two-tone.
  - Same hand strength has different strategic value by board class.
- Check-raise lines are rare in self-play traversal, so compute-limited Deep CFR may undertrain them.

**Next-run requirements**

Bet sizes needed:

- Flop: **0.33 / 0.5 / 0.75 / 1**
- All-in usually only relevant at low SPR; do not let flop jam pollution dominate high-SPR SRPs.

Features needed:

- Board texture tensor:
  - Paired/unpaired.
  - Monotone/two-tone/rainbow.
  - Connectedness/gaps.
  - High-card rank.
  - Broadway density.
- Hand-board interaction:
  - Top pair/middle pair/bottom pair.
  - Overpair.
  - Two overcards.
  - Backdoor flush/straight.
  - Nut advantage proxies.

**Validation priority:** top 3. This is high-frequency and likely explains a lot of broad postflop loss.

---

### 4. 3-bet pots / low-SPR stack-off and c-bet trees

**Examples**

- BTN opens, BB 3-bets, BTN calls.
- 3-bettor c-bets small on A/K-high boards.
- Caller floats low connected boards.
- Low SPR turn shove / call decisions.
- Overpair/top-pair stack-off thresholds.
- A/K blocker-driven 4-bet/5-bet preflop effects carrying into postflop.

**Likely EV leverage:** high. Less frequent than SRP, but pots are larger.

**Why hard for current architecture**

- Sparse samples + high pot size = high variance learning.
- Stack-off decisions are sensitive to exact hand class and blockers.
- Current features likely do not encode preflop range context strongly enough.
- Pot/all-in abstraction is especially bad in low-SPR geometry where 0.25–0.5 flop bets set up turn jams.

**Next-run requirements**

Bet sizes needed:

- Flop 3BP: **0.33 / 0.5 / 0.75 / all-in depending on SPR**
- Turn 3BP: **0.5 / 0.75 / 1 / all-in**
- River: **0.5 / 1 / all-in**

Features needed:

- Full preflop action history.
- Position.
- SPR.
- Overpair/top pair/kicker.
- A/K blockers.
- Nut flush/straight blockers.
- Board texture.

**Validation priority:** top 4. If your net is losing broad postflop EV, 3BP low-SPR mistakes are likely expensive.

---

### 5. Preflop HU open / limp / defend / 3-bet / 4-bet abstraction

**Likely EV leverage:** medium-high due to frequency.

This is less “deep neural hard” than postflop, but your current **pot/all-in-only** abstraction can still create systematic loss.

**Important warning:** preflop should not blindly reuse postflop pot-fraction sizes. HU preflop needs a separate abstraction:

- BTN limp.
- BTN minraise / 2.0bb / 2.5bb / maybe 3bb.
- BB 3-bet sizes.
- BTN 4-bet sizes.
- All-in at appropriate stack depths.

If your HUNL game only allows pot-sized preflop raises, you are not playing the same strategic game as GTO Wizard.

**Validation priority:** sanity check, not main research focus. If preflop is badly abstracted, all postflop comparisons are contaminated.

---

### 6. Check-raise and raise/continue branches

**Examples**

- BB check-raise flop after BTN c-bet.
- BTN defending vs check-raise.
- Turn raise vs barrel.
- River raise bluff/value.

**EV leverage:** medium-high, but sample frequency is lower.

**Why hard**

- Rare branches in self-play.
- Large pot swings.
- Requires blocker/draw/nut-class features.
- Current pot/all-in raise sizes are too coarse.

**Next-run needs**

- Raise-size abstraction, not just bet-size abstraction.
- Strong action-history encoding.
- Stratified replay/training batches so rare raise nodes are not drowned by common check/call nodes.

---

### 7. Monotone, paired, four-liner, four-flush, and texture-shift boards

**EV leverage:** medium, but strategically difficult.

These are not one spot; they are board classes where bucketed hand strength fails badly.

**Why hard**

- “Flush” is not enough. Nut flush blocker matters.
- Trips on paired board differs from full house blockers.
- Straight on four-liner board differs by rank/blockers.
- Bucket features miss removal effects.

**Next-run needs**

- Exact card occupancy.
- Suit-specific features.
- Nut hand class / near-nut class.
- Blocker flags.

---

## The 3–4 spots that should drive your next-run priorities

If you force me to choose, prioritize these:

### Priority A — SRP flop c-bet/check/check-raise trees

Because they are high frequency and your current pot-only abstraction is badly mismatched.

Need:

- 0.33 / 0.5 / 0.75 sizing.
- Board texture features.
- Hand-board interaction.
- Check-raise branch validation.

---

### Priority B — Turn barrel/give-up/overbet after flop c-bet called

Because turn errors create bad river ranges.

Need:

- 0.75 / 1 / 1.25 / 2 sizing.
- Draw and blocker features.
- Turn-card texture-delta features.

---

### Priority C — River polar bet/fold/call decisions

Because terminal mistakes are high EV and blocker-driven.

Need:

- 0.5 / 0.75 / 1 / 1.25 / 2 / all-in.
- Exact blockers/unblockers.
- Missed draw detection.
- River pot-odds encoding.

---

### Priority D — 3-bet pot low-SPR trees

Because the pots are large and sparse training will otherwise underfit them.

Need:

- Preflop action context.
- SPR geometry.
- 0.33 / 0.5 flop sizing and all-in geometry.
- High-card/blocker features.

---

# 2. Using PokerBench + Pluribus without contaminating the pure self-play core

Your proposed use is mostly correct.

The pure self-play GTO core must not receive supervised labels from PokerBench, Pluribus, GTO Wizard, TexasSolver, Qwen, or any imitation model.

## PokerBench as validation: yes, with caveats

Using PokerBench as a **held-out validation set** is non-contaminating if:

- No gradients are taken from PokerBench labels.
- No supervised pretraining uses PokerBench labels.
- No early stopping repeatedly overfits to the same PokerBench validation score.
- No hyperparameter search treats PokerBench as the training objective without a sealed test split.

Good uses:

1. **Held-out action-match validation**
   - Compare trained self-play policy to solver-labeled HUNL spots.
   - Stratify by street, position, pot type, board texture, action facing, and bet size.

2. **Hard-spot diagnostic**
   - Find where your self-play net diverges most:
     - River facing overbet.
     - Turn barrel.
     - 3-bet pot c-bet.
     - BB check-raise defense.
   - This is excellent.

3. **Action abstraction coverage**
   - Before training, check what fraction of solver actions can be reasonably mapped to your legal sizes.
   - If many PokerBench solver bets map poorly to your abstraction, your training run is handicapped before it starts.

4. **Regression suite**
   - After each major code change, report spot-family metrics, not just global action match.

Caveats:

- “Action match %” is not EV.
- If PokerBench has mixed frequencies, use cross-entropy / KL / Brier score against frequencies instead of hard top-1 match.
- If PokerBench only has hard labels, top-1 match is still useful but noisy.
- Multiple solver actions can be close in EV; without per-action EVs, you cannot know whether a mismatch is severe.

## PokerBench warm-start: I would not recommend it for the pure core

Do **not** warm-start the self-play advantage/policy nets from PokerBench labels if you want to honestly claim the core escaped the imitation ceiling.

Even if later self-play continues, in finite compute with function approximation, the supervised initialization can remain embedded. That is contamination for your stated goal.

Acceptable alternatives:

- Train a **separate imitation baseline** on PokerBench. Useful comparator, not the GTO core.
- Train a **separate evaluator/critic/reporting model**. Do not feed it into CFR updates.
- Use PokerBench to choose validation slices. That does not poison the equilibrium, though it can contaminate evaluation if you overfit architecture choices to it.
- Use game-rule auxiliary labels like hand class/draw flags/equity-vs-random if you want representation pretraining. That is not solver imitation, but direct engineered features are probably simpler and higher EV.

## Pluribus 6-max histories: okay for exploit overlay, not GTO core

Your proposed use is right:

- Use Pluribus histories for:
  - Evaluation spot distribution.
  - Opponent-model training.
  - Exploit overlay research.
  - Line-frequency priors for non-GTO exploit mode.

Do not use them to train the self-play GTO core policy or advantage nets.

Important caveats:

- Pluribus is 6-max, not HUNL.
- 6-max preflop ranges are not HU ranges.
- Multiway history is not directly compatible with HUNL.
- 10k hands is small for detailed postflop opponent modeling.
- Pluribus data is strong-player data, not equilibrium labels.

Best use:

- Extract heads-up postflop portions only if possible.
- Use as a distribution of realistic public states/lines.
- Train opponent model separately:
  - `p_opp(action | info_state)`
- Use exploit overlay as:
  - baseline GTO policy from self-play core;
  - opponent model adjustment;
  - KL/entropy cap so exploit mode does not go insane.

Keep logs separate:

- `core_gto_selfplay`
- `imitation_baseline`
- `exploit_overlay`

Do not mix their weights or replay buffers.

## What would poison the equilibrium claim

These would contaminate the pure self-play core:

- Supervised PokerBench action labels into advantage net.
- Supervised PokerBench action labels into average-strategy net.
- Distilling your Qwen PokerBench model into the core.
- Behavior cloning Pluribus into the core.
- Using TexasSolver frequencies as policy targets for the core.
- Reward shaping from solver labels.
- Selecting traversals/states based on solver-labeled “correctness” and updating regrets off-distribution without proper CFR logic.
- Training on GTO Wizard actions.

These do not poison the core:

- Validation-only PokerBench metrics.
- Sealed final PokerBench test split.
- TexasSolver cache validation only.
- Pluribus-only exploit overlay.
- Self-play warm-start from an earlier pure self-play model.
- Hand evaluator / card-feature / draw-feature engineering from game rules.
- Legal action abstraction design.

## Better sensible use you may be missing

### 1. Use PokerBench to build a hard-spot validation matrix

Do not report only global action match. Report:

- Street:
  - flop / turn / river
- Pot type:
  - SRP / 3BP / 4BP
- Position:
  - IP / OOP
- Facing:
  - unopened / facing bet / facing raise
- Line:
  - c-bet / probe / check-raise / double barrel / river overbet
- Board texture:
  - paired / monotone / two-tone / connected / high-card / low-card
- Bet size:
  - small / medium / pot / overbet / all-in

This will tell you whether the finer abstraction actually fixes the broad postflop leak.

### 2. Use PokerBench/TexasSolver frequencies to test action-size coverage

Before burning compute, answer:

- How often does solver choose a size close to one of your legal sizes?
- How often are you forcing 0.75 into a spot where solver uses 0.33?
- How often are you missing overbet?
- How often are river block bets absent?

This is validation/design, not training.

### 3. Keep a sealed benchmark

If you repeatedly tune architecture using the same PokerBench split, you are not poisoning the equilibrium training, but you are poisoning your claimed evaluation.

Use:

- Dev validation split: for diagnostics.
- Sealed final split: rarely touched.
- GTO Wizard paired A/B: actual performance gate.

---

# 3. OpenSpiel methodology to mirror

## Ranked by EV-gained / effort

### 1. Mirror OpenSpiel-style information-state tensor principles

**Verdict:** highest EV / medium effort. Do this.

Your 20-dim strength-bucket representation is the wrong abstraction for HUNL.

You do not need OpenSpiel installed locally to copy the important idea:

> Feed the net a mostly lossless information-state representation, not a tiny human equity bucket.

Minimum representation should include:

- Private cards as exact rank/suit occupancy.
- Board cards as exact rank/suit occupancy.
- Street.
- Player to act.
- Position.
- Pot size.
- Stack sizes.
- Amount to call.
- Current street contributions.
- SPR.
- Legal action mask.
- Betting history by street:
  - checks;
  - calls;
  - bets;
  - raises;
  - sizes as pot fractions;
  - last aggressor.
- Preflop action history.

Then concatenate derived poker features:

- Hand class.
- Kicker class.
- Draw class.
- Nut draw flags.
- Blocker flags.
- Board texture.
- Turn/river texture changes.
- Pot odds.

Do **not** replace exact occupancy with only derived features. Exact cards are necessary because blockers are strategic information.

This is probably the highest-value architectural change after bet sizing.

---

### 2. Mirror Deep CFR reservoir sampling and average-policy memory correctly

**Verdict:** very high EV / low-medium effort.

You already have external-sampling MCCFR + dual nets. The risk is subtle implementation bias.

Important things to mirror/check:

- Separate advantage memories per player.
- Store advantage/regret targets only for legal actions.
- Use legal action masks everywhere.
- Do not train invalid actions.
- Store average-strategy samples across iterations, not just final regret-net output.
- Weight average-strategy samples according to your CFR/DCFR+ schedule.
- Use reservoir sampling or a defensible replacement so memory is not just recent easy states.
- Ensure external sampling:
  - samples chance/opponent actions;
  - enumerates traverser actions;
  - backs up counterfactual values correctly.

Brutal point: if the average-policy net is wrong, your “strategy” can be just a noisy last-iterate policy. That can look okay versus fish and still be highly exploitable.

---

### 3. Keep OpenSpiel-style exploitability/nash_conv tests for toy and reduced games

**Verdict:** high EV for correctness / not directly full-HUNL EV.

Do this for:

- Kuhn.
- Leduc.
- Tiny deck toy NLHE.
- Very small stack abstractions.
- Your own reduced HUNL test game.

Do **not** expect exact full HUNL exploitability. That is not realistic for your current system.

For full HUNL, use approximate diagnostics:

- Local best response / LBR-style probes.
- PokerBench/TexasSolver frequency validation.
- GTO Wizard paired A/B.
- Spot-bucket EV attribution.

Your Leduc exploitability improvement 445 → 338 is a useful regression signal, but it is not enough. You need spot-specific HUNL diagnostics.

---

### 4. Read/mirror OpenSpiel Deep CFR / Deep CFR+ implementation invariants

**Verdict:** medium-high EV / low effort.

Worth mirroring:

- Traversal structure.
- Advantage target generation.
- Reservoir handling.
- Average policy training.
- Evaluation loop.
- Legal-action masking.
- Iteration weighting.

Not worth doing:

- Blindly porting code that does not match your custom HUNL abstraction.
- Making your cloneable local project dependent on OpenSpiel if Windows/local install is a hard constraint.

Use OpenSpiel as a reference oracle, not as your product architecture.

---

### 5. OpenSpiel universal_poker tensor exactly

**Verdict:** concept yes; exact port maybe overkill.

The exact OpenSpiel tensor is useful as a reference, but you do not need to copy it byte-for-byte.

What you need is the principle:

- lossless public/private state;
- betting history;
- legal actions;
- normalized scalar context.

Your own tensor can be better for this project if it includes poker-specific derived features.

---

### 6. RNaD / NFSP / PSRO

**Verdict:** not worth replacing Deep CFR now.

#### NFSP

Not recommended for your core.

- Older approach.
- Usually less compelling than Deep CFR for this kind of imperfect-information poker setting.
- Adds RL instability.
- Not likely to fix your current main leaks: action abstraction and features.

#### PSRO

Not recommended for pure HUNL GTO core right now.

- Useful for population/exploit research.
- Expensive.
- Meta-strategy quality depends on oracle quality.
- Better fit for exploit overlay or opponent adaptation than base equilibrium.

#### RNaD

Not recommended now.

- High engineering burden.
- Unclear value for your from-scratch HUNL build.
- Does not solve your immediate abstraction/feature/traversal bottlenecks.
- Risk of self-deception: changing algorithm while the game representation is still strategically blind.

Stay with Deep CFR/DCFR+ until the representation, bet abstraction, and traversal throughput are no longer the obvious bottlenecks.

---

# OpenSpiel C++ traverse vs vectorizing your own

## Brutal answer

OpenSpiel C++ traverse on a RunPod is useful as a **reference and speed benchmark**, but I would not make it the main answer for your project unless you are willing to give up the “self-contained cloneable local HUNL core” requirement.

Because:

- OpenSpiel is not installable locally on your Windows setup.
- Your custom HUNL game, action abstraction, and feature set are evolving.
- Integration friction can eat the speed gains.
- You need tight logging/validation vs GTO Wizard and PokerBench spot buckets.
- A pod-only dependency makes reproducibility worse.

## What I would do instead, ranked

### 1. Profile first

Before rewriting anything, measure:

- % time in Python traversal recursion.
- % time in hand evaluation.
- % time in feature construction.
- % time in neural net inference.
- GPU utilization.
- replay buffer overhead.

Do not guess.

### 2. Batch neural inference

High EV if GPU is underused.

External sampling is sequential, but you can still batch many infoset evaluations from multiple traversal workers.

Aim for:

- traversal workers generate states;
- batcher collects states;
- GPU evaluates advantage/policy nets in batches;
- workers continue.

This is usually higher value than naive NumPy “vectorization” of recursive tree logic.

### 3. Move hand evaluation / feature construction hot paths out of pure Python

Use:

- Numba,
- Cython,
- pybind11 C++,
- Rust extension,
- or precomputed lookup tables.

Card evaluation and draw/texture feature construction can become major bottlenecks once you add richer features.

### 4. Multiprocessing traversal actors

Run multiple traversal workers feeding shared reservoirs.

Be careful with:

- RNG independence.
- reservoir correctness.
- stale network versions.
- deterministic eval mode.

### 5. Context-gate the new bet sizes

Your next abstraction has 7 sizes. Applying all 7 at every node may explode compute.

Use all sizes as the global menu, but prune by context:

- Flop SRP: mostly 0.33 / 0.5 / 0.75 / maybe 1.
- Turn: 0.5 / 0.75 / 1 / 1.25 / 2 depending on texture and SPR.
- River: include 0.5 / 0.75 / 1 / 1.25 / 2 / all-in.
- Low SPR: all-in becomes more relevant.
- Very high SPR flop jams should usually be absent or rare.

This is not imitation; it is action abstraction design.

### 6. Use OpenSpiel pod as reference, not primary

Good uses:

- Verify Deep CFR traversal methodology.
- Compare speed.
- Run universal_poker experiments.
- Check your toy-game exploitability against a known implementation.

Bad use:

- Depending on OpenSpiel pod for every serious run while your local self-contained code diverges.
- Using OpenSpiel-generated solver/imitation labels to train your core.  
  Self-play generated by OpenSpiel CFR is not imitation data, but it still undermines your stated from-scratch/local architecture goal if it becomes the main pipeline.

---

# Final concrete priority order

If optimizing EV-gained / effort for the next run:

1. **Implement richer lossless info-state features**
   - Exact card occupancy + action history + stack/pot/SPR + legal mask.
   - Add derived hand/draw/blocker/texture features.
   - This directly attacks the 20-dim bucket ceiling.

2. **Implement finer but context-gated bet abstraction**
   - Especially 0.33/0.5 flop, 0.75/1/1.25/2 turn/river, all-in by SPR.
   - Also fix preflop sizing separately if currently pot-only.

3. **Build spot-bucket validation**
   - PokerBench/TexasSolver validation only.
   - GTO Wizard paired A/B with spot attribution.
   - Do not trust global action-match alone.

4. **Audit Deep CFR/DCFR+ mechanics against OpenSpiel**
   - Reservoir sampling.
   - Average-policy memory.
   - Legal masks.
   - Iteration weighting.
   - External-sampling backup correctness.

5. **Fix traversal throughput**
   - Profile.
   - Batch NN inference.
   - Move hand eval/features out of Python.
   - Multiprocessing workers.
   - Use OpenSpiel pod as reference, not core dependency.

6. **Keep PokerBench/Pluribus out of the core**
   - PokerBench = validation/diagnostics.
   - Pluribus = exploit overlay/eval distribution.
   - No supervised labels into the pure self-play GTO weights.

7. **Do not chase RNaD/NFSP/PSRO yet**
   - That is algorithm-shopping while your representation/action abstraction are still the dominant leaks.
