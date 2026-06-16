# Per-situation solutions — poker (gpt-5.5)

## Bottom line

Your intuition is **correct**: the fix is not “slightly better bet/check frequencies.” Your current floor is losing because it does **not know the actual public state**: line, SPR, ranges after previous actions, size faced, and downstream betting tree. It predicts a marginal `P(bet)` for collapsed situations. That can match aggregate solver frequencies and still dump EV.

The honest architecture for this bot is:

> **Supervised blueprint + targeted real-time resolving at high-leverage nodes.**

Not full “solve everything always” yet. Not just a bigger frequency net. Use the supervised model as a fast fallback/range prior, but let TexasSolver solve the actual situation when the decision is expensive: facing bets, turn/river after prior betting, river value/bluff sizing, OOP check-raise/probe nodes.

The solver that beat you is already available locally. The point is to stop imitating its marginal frequencies and start using it on the actual public state.

---

# 1. Decomposing the measured `-160 ± 75 bb/100`

First brutal caveat: **160 paired hands is not enough to precisely allocate the loss.** The overall result is meaningful enough to kill the earlier `+184` unpaired fantasy, but the subcategory decomposition below is necessarily approximate. Treat it as an engineering prior, not a measured truth.

Also, these categories interact. If you fix sizing, defense EV changes. If you fix turn resolving, river ranges change. So the numbers should not be interpreted as cleanly additive.

Still, for a history-free frequency floor like yours, the likely decomposition of the `-160 bb/100` is roughly:

| Leak source | Rough contribution | Confidence | Why |
|---|---:|---:|---|
| **Facing-bet defense** | **45–70 bb/100** | High | MDF/pot-odds defense is not a solver calling/raising range. It misses blocker logic, raise mixes, combo selection, and per-size defense. This is probably the largest single bleed. |
| **Turn/river line context after betting** | **35–60 bb/100** | High | Your advisor averages across radically different infosets: check-check turn, cbet-called turn, probe line, delayed cbet line, raise line, different SPRs. The same board+hand features require different actions depending on line and ranges. |
| **Bet sizing** | **25–45 bb/100** | Medium/high | One fold-equity-optimal size cannot represent solver’s small range bets, polar overbets, geometric sizing, block bets, jams, etc. Correct bet frequency with wrong size still creates bad pot geometry and wrong continuing ranges. |
| **OOP check-raise / probe game** | **15–35 bb/100** | Medium | If OOP mostly check/calls/check/folds and lacks solver x/r/probe structure, IP realizes too much equity and OOP’s range becomes capped. Important, but probably smaller than facing-bet defense and turn/river context. |
| **Residual / noise / preflop / exploit layer / bugs** | `±20+ bb/100` | Medium | The measured sample is small; any exploit gate triggering versus a solver would also be suspect. |

My best midpoint allocation:

- Facing-bet defense: **~55 bb/100**
- Turn/river context collapse: **~45 bb/100**
- Sizing: **~35 bb/100**
- OOP x/r/probe: **~25 bb/100**

Total: **~160 bb/100**

The biggest bleed is **not the flop cbet frequency**. Your aggregate frequencies are already aligned: `47/47`, `75/74`, `22/22`, river `30/31`. The bleed is in:

1. **Which combos continue versus bets**
2. **Which size is used**
3. **Which future line is chosen after prior action**
4. **How ranges are updated after each action**

A marginal `P(bet)` model does not represent any of that.

Self-deception flag: the deterministic GTO-gap looking “okay” is not evidence of a strong policy. It scores the wrong object. Matching solver’s aggregate bet/check rates while using one size and MDF defense is like matching a chess engine’s “move piece frequency” while blundering tactics.

---

# 2. Best architecture for “more solutions per situation”

## Ranking by EV gained / effort

My ranking for **your exact resources**:

1. **Hybrid: supervised blueprint + targeted real-time resolving**  
   Best move. Highest EV/effort. Use TexasSolver only where the floor is structurally blind.

2. **Minimal real-time resolving on river and turn/facing-bet nodes**  
   This is the first concrete implementation of the hybrid. It directly attacks the biggest bleeds.

3. **Richer supervised full-action strategy net**  
   Valuable as a blueprint and fallback, but it will plateau unless it is conditioned on full public state and trained on many more solved node types.

4. **CFV/value net for depth-limited resolving**  
   Eventually important for fast flop solving, but overkill before you prove that river/turn resolving recovers EV.

5. **Full real-time terminal solving at every postflop decision**  
   Theoretically best in HU, but likely too slow and too much engineering as a first move.

---

## (i) Real-time depth-limited subgame solving

This is the most honest answer if the goal is to approach the TexasSolver oracle. The oracle beat you because it solved the actual situation. Your bot averaged over situations.

But “real-time solving” does not mean solving the entire game from scratch every decision with a giant tree. The minimal viable resolver should be much narrower.

### Minimal viable version

Build a **public-state resolver**:

At each decision, maintain:

- Board
- Pot
- Effective stack
- SPR
- Action history with sizes
- Legal actions
- Your full range at this public node
- Villain’s full range at this public node
- Your actual hand, used only after the strategy is computed

Important: do **not** solve with only your actual hand. The solver needs your **range**, otherwise you are not producing a GTO-like strategy for the public state.

Range update:

```text
range_next(hand) ∝ range_prev(hand) × policy(action | state, hand)
```

For villain, use the best available policy estimate:

1. Previous real-time solve if available
2. Rich supervised blueprint
3. Current advisor fallback
4. Exploit model only if intentionally deviating

For your own range, update using the policy your bot would have used at prior nodes, not the actual hand only.

### Priority nodes to resolve

Do not start with flop cbet. Your flop aggregate frequencies are not the measured disaster. Start where your bot is structurally dumb.

#### Priority 1: River facing-bet defense

This is the cheapest and highest signal.

When villain bets river, solve the current river subgame with:

- Fold/call
- Maybe raise jam or one raise size if stacks allow
- Villain response to raises
- Exact board and ranges

This gives you:

- Correct call/fold combos
- Blocker-sensitive bluffcatching
- Raise mixes
- Per-size defense

No value net needed. River resolves to terminal.

Expected gain if the diagnosis is right: **~25–50 bb/100** by itself.

#### Priority 2: River betting/checking/sizing when checked to or first to act

Solve river nodes where you decide whether to:

- Check
- Bet small/block
- Bet medium
- Overbet/jam if applicable

This attacks the single-size heuristic and river bluff/value construction.

Expected additional gain: **~15–35 bb/100**.

#### Priority 3: Turn facing-bet defense and turn-after-betting lines

When facing a turn bet, or when acting after a flop cbet/call line, solve the turn subgame to terminal using a compact action abstraction.

Example turn action set:

- Check/call/fold as legal
- Bet/raise sizes: `33%`, `75%`, `150%/jam` depending SPR
- Maybe cap to 2 raise sizes to keep it fast

No value net is required if you solve turn-to-river terminal, but it may be seconds rather than milliseconds.

Expected gain: **~30–60 bb/100** if speed is acceptable.

#### Priority 4: OOP check-raise and probe nodes

Resolve OOP nodes like:

- Flop OOP facing IP cbet
- Turn OOP after flop checked through
- Turn OOP after check/calling flop
- River probe after turn check-through

This fixes the missing OOP aggression/protection game.

Expected gain: **~15–35 bb/100**.

#### Priority 5: Flop first-action cbet/lead

This is lower priority for your measured problem. Your aggregate cbet/lead frequencies are already close. The missing pieces are sizing and future tree, but full flop solving is the slowest.

Flop solving becomes attractive after you have:

- A value/CFV net, or
- A very compact action tree, or
- Precomputed/warm-started common flop solves

---

## Ranges, depth, and leaves

### River

- Solve to terminal.
- No value net.
- Fastest and cleanest.
- Best first test.

### Turn

- Prefer solve to terminal with compact action abstraction.
- No value net needed initially.
- May be seconds per spot.
- Good second test.

### Flop

Three options:

1. **Full flop-to-river solve with compact tree**  
   Highest accuracy, slowest.

2. **Depth-limit to turn with crude equity leaf**  
   Cheap, but dangerous. Equity leaf overestimates realization and misses future betting EV. Use only as an experiment, not as final architecture.

3. **Depth-limit to turn/river with CFV/value net**  
   Real architecture used by strong bots. More engineering.

---

## Live speed reality

You said TexasSolver solves one postflop spot in **milliseconds to seconds** locally. That is enough for a prototype, but not automatically enough for live play.

Strong bots make real-time solving fast by:

1. **Solving only the current public subgame**, not the whole game.
2. **Using small action abstractions**: 2–4 bet sizes, capped raises.
3. **Depth-limiting** at flop/turn and using a value/CFV net.
4. **Warm-starting** from previous solves or nearby cached spots.
5. **Caching** solved public states keyed by board, pot, SPR, line, ranges.
6. **Using a blueprint fallback** when the solve is not ready.
7. **Resolving selectively**, not at every trivial node.

For your first real test, do not build the full DeepStack/Libratus-style stack. Build:

> **River resolver + turn resolver + compact action tree + range tracker.**

If that does not recover material EV, the “real-time solve” direction is either implemented wrong or the diagnosis is incomplete.

---

## (ii) Richer supervised strategy net

This is useful, but it is not enough by itself unless you make it much more state-specific.

Your current advisor:

```text
(board + hand features + role) -> P(bet)
```

The next blueprint needs:

```text
(public state + hand + ranges + legal actions) -> full action distribution
```

Inputs should include:

- Street
- Board cards
- Hole cards
- Position/IP/OOP
- Pot
- Effective stack
- SPR
- Full action history
- Previous bet sizes
- Size currently faced
- Aggressor/initiative status
- Node type: cbet, probe, delayed cbet, barrel, facing bet, facing raise, etc.
- Range summaries:
  - Equity distribution
  - Nut advantage
  - Range-vs-range equity
  - Polarization measures
  - Blocker features
  - Previous street range weights if feasible

Outputs should include a full legal action distribution, not only `P(bet)`:

- Fold
- Call
- Check
- Bet small
- Bet medium
- Bet large/overbet
- Jam
- Raise small
- Raise jam

You need training data from many more node types:

- Facing flop cbet
- Facing turn barrel
- Facing river bet
- OOP check-raise
- IP response to check-raise
- Turn probes
- Delayed cbets
- River block bets
- River overbets
- Raise/call/fold nodes per size faced

Your current cache of `~1340` flop and `~1308` river solved spots is not enough if those are mostly lead/cbet marginal strategies. You need solved **public states**, not just boards.

### How far can pure supervised close the gap?

Rough estimate:

- Current floor: `-160 bb/100`
- Richer supervised multi-action blueprint with proper line/SPR/size conditioning: maybe improves **50–90 bb/100**
- Very large supervised blueprint trained on many solved public states: maybe improves **80–120 bb/100**
- But it likely plateaus around **-40 to -80 bb/100** versus a live-solving oracle unless the dataset is enormous and the model is effectively approximating a resolver.

Why the plateau?

1. Public states are continuous: ranges, SPRs, sizes, lines.
2. Off-tree sizes create unfamiliar states.
3. Frequency labels do not tell the net which mistakes are expensive.
4. Current cache stores strategy frequencies only, not action EVs or CFVs.
5. Small imitation errors compound through range updates.

So yes, build the richer supervised net — but as a **blueprint**, not as the final answer.

---

## (iii) Value/CFV net

A value/CFV net becomes important when you want fast depth-limited resolving, especially from the flop.

The relevant recipe, also similar in spirit to the MIT Poker / GTO-Wizard-style depth-limited approach, is:

1. Use a blueprint to provide ranges.
2. At the current public state, run a depth-limited solve.
3. At the depth limit, call a neural value function.
4. The value net outputs counterfactual values for private hands/ranges.
5. The resolver uses those values instead of rolling out the entire game tree.

This is the DeepStack/Supremus-style idea.

But for your bot, it is **not the first step**.

Why?

- Your current cache stores **strategy frequencies only**.
- A CFV net needs **counterfactual value labels**, preferably per hand at public states.
- If TexasSolver can dump CFVs, great. If not, you need to modify extraction or compute them.
- Training a reliable CFV net is harder than training a policy imitation net.
- River and many turn solves do not need a value net because they can solve to terminal.

So the honest order is:

1. Prove river/turn resolving helps.
2. Add richer blueprint/range tracker.
3. Then train CFV net to make flop resolving fast.

Building the CFV net first is likely overkill.

---

## (iv) Hybrid: supervised blueprint + targeted real-time resolving

This is the move.

Architecture:

```text
Preflop:
    CFR / lookup / Nash push-fold

Postflop blueprint:
    Rich supervised multi-action strategy net
    Full public-state conditioning
    Used for instant fallback and range updates

Range tracker:
    Maintains both players' public ranges through the line
    Uses blueprint or previous solver policy for Bayesian updates

Resolver:
    Calls TexasSolver at high-leverage nodes
    River: exact terminal solve
    Turn: compact terminal solve
    Flop: only selected x/r / facing-raise / high-pot nodes initially

Action selector:
    Use solver strategy for actual combo
    Sample mixed actions, do not always argmax
    Fall back to blueprint if solve not ready

Exploit layer:
    Only allowed to deviate when confidence is real
    Against solver benchmark, should mostly be disabled
```

This is essentially the Pluribus pattern in simplified HU form: strong offline blueprint, real-time search only in the actual situation, limited action abstraction, fallback when search is unavailable.

For your measured problem, this directly attacks the blind spots:

| Current blind spot | Hybrid fix |
|---|---|
| One marginal `P(bet)` | Public-state strategy |
| One heuristic size | Solver size mix |
| MDF defense | Solver call/raise/fold range |
| History-free turn/river | Ranges updated through actual line |
| Missing x/r/probe | Solver includes those nodes |
| Cold-start exploit layer | Blueprint/resolver fallback |

Expected recovery if implemented correctly:

- River-only resolving: **~30–60 bb/100**
- River + turn resolving: **~70–120 bb/100**
- River + turn + key flop x/r/probe resolving: **~90–140 bb/100**
- Full strong hybrid with CFV net and rich blueprint: could get much closer, but do not assume zero. Action abstraction, range tracking errors, and off-tree handling still cost EV.

Given your measured `-160 ± 75`, I would not claim “this will make you winning.” I would claim:

> If the diagnosis is right, targeted resolving should materially reduce the loss in a paired test. If it does not, your range tracker/action abstraction/benchmark assumptions are wrong.

---

# 3. Concrete first step that cheaply proves or kills the direction

Do this:

## Build a river resolver first

Implement:

1. Range tracker from preflop to river.
2. TexasSolver wrapper for current river public state.
3. Compact river action abstraction:
   - If facing bet: fold/call, plus maybe jam/raise if legal.
   - If not facing bet: check, bet `33%`, bet `75%`, overbet/jam if legal.
4. Use solver strategy for actual hand.
5. Fall back to current floor if solve times out.

Then run a new paired benchmark:

- Current floor vs TexasSolver
- Floor + river resolver vs TexasSolver
- Same duplicate/paired setup
- At least **1,000 paired hands**, preferably more

Your current SE is `±75 bb/100` over 160 hands. Scaling roughly by `sqrt(n)`, 1,000 hands gets you around:

```text
75 * sqrt(160 / 1000) ≈ 30 bb/100
```

Still noisy, but enough to see whether river resolving recovers a big chunk.

### Pass/fail criterion

If river resolving recovers **30+ bb/100**, continue.

If it recovers **0–15 bb/100**, either:

1. River is not the main leak,
2. Your range tracking is bad,
3. The river abstraction is too poor,
4. The resolver integration is wrong,
5. Or the measured `-160` was partly sample/path noise.

Then add turn resolving and rerun.

---

## Better: run intervention ablations

To decompose the `-160` empirically, make variants:

1. **Solver sizing only**  
   Keep your bet/check decision, but use solver-like size mix when betting where possible.

2. **Solver facing-bet defense only**  
   Whenever facing bet/raise, use TexasSolver response.

3. **Solver turn/river line only**  
   Use resolver only after any previous postflop betting sequence.

4. **Solver OOP x/r/probe only**  
   Resolve OOP check-raise/probe nodes.

5. **Full river resolver**

Run each paired against TexasSolver for 1k+ hands. That gives actual EV deltas instead of guessing.

Because your cache has no per-action EVs, outcome-based paired ablation is the cheapest honest decomposition.

---

# 4. Is richer supervised enough, or is real-time solving the honest answer?

## User intuition: correct

Yes, the intuition is right:

> You need more situation-specific GTO, not better marginal frequencies.

But be precise: “more solutions” must mean more solutions for the **actual public state**:

- Line
- Pot
- SPR
- Ranges
- Size faced
- Legal sizes
- Position
- Previous actions

More board-only caches or better `P(bet)` labels will not solve it.

## Richer supervised model plateau

A richer supervised net can become a much better blueprint. It can probably recover a meaningful chunk of the loss.

Expected plateau:

- Small upgrade from current advisor: still bad, maybe `-120 to -150`
- Full public-state supervised action net: maybe `-70 to -100`
- Very large multi-node supervised blueprint: maybe `-40 to -80`
- Near-solver strength purely from supervised imitation: possible only with huge data and excellent state/range conditioning, but then you are effectively approximating a resolver offline.

The main limitation is that supervised frequencies do not know which errors are expensive. Two 10% frequency errors can have wildly different EV cost. Without action EVs/CFVs, the net treats them too similarly.

## Real-time solving plateau

Targeted real-time solving should plateau much higher:

- River/turn targeted resolving: likely gets you much closer quickly.
- Full continual resolving with value net: honest path toward solver-level HU play.
- Remaining losses come from:
  - Bad range reconstruction
  - Action abstraction mismatch
  - Solver timeout / low iteration count
  - Off-tree size mapping
  - Sampling/mixing mistakes
  - Exploit layer deviations

So the honest answer is:

> A richer supervised model is necessary as a blueprint, but not sufficient as the final architecture. The EV move is hybrid resolving.

---

# Final recommendation

Do not spend the next month making the current `P(bet)` advisor prettier. That is optimizing the proxy that already misled you.

Build in this order:

1. **River public-state resolver**
   - Exact river solve
   - Per-size facing-bet defense
   - River value/bluff sizing
   - Paired test 1k+ hands

2. **Range tracker**
   - Update both players’ ranges through actual line
   - Use own historical strategy, not actual hand-only ranges

3. **Turn resolver**
   - Facing-bet defense
   - Turn after flop cbet/call
   - Turn probe/delayed cbet
   - Compact action abstraction

4. **Richer supervised blueprint**
   - Full action distribution
   - Conditioned on line/SPR/size/range summaries
   - Used for fallback and range updates

5. **Key flop resolver**
   - OOP vs cbet check-raise
   - IP response to x/r
   - High-pot/high-SPR leverage nodes

6. **CFV/value net**
   - Only after resolving proves EV gain and speed becomes the bottleneck

That is the best EV/effort path for this bot. The measured `-160` was not a frequency problem. It was a public-state strategy problem.
