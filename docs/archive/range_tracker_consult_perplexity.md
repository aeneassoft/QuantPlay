# 1_perplexity — range-tracker P0 consult

Elapsed: 56.0s

---

You are trying to bolt a DeepStack‑style “blueprint + on‑the‑fly resolving” engine onto a very thin blueprint (only P(bet) for IP/OOP on each street), and the bottleneck is turning observed actions into believable ranges so TexasSolver doesn’t solve garbage states.

Modern strong HU systems all solve this exact problem, but none of them have your exact constraint (P(bet) only), so we have to map their mechanisms to your setting.

Below I’ll first answer your 5 questions, then summarize how DeepStack, Libratus/Pluribus, and GTO Wizard‑like systems do it and how that maps onto your design.

---

## (1) Filling in the missing policy for range updates

You only have **P(bet | state, hand)** from the blueprint, nothing for:

- facing‑bet defense: call / fold / raise  
- bet sizing: which size gets chosen when “bet” happens

Your range update is Bayesian:

\[
w_{t+1}(h) \propto w_t(h) \cdot \pi(\text{observed action} \mid s_t, h)
\]

So you need a **pseudo‑policy** \(\pi\) for all “silent” actions. You want something:

- **Coherent with your blueprint**
- **Simple to implement**
- **Biased towards not over‑narrowing ranges** (safer than over‑confident narrowing)

### 1.1 General principle: low‑information updates for unknown policy mass

For actions that the blueprint does not model, use **minimal‑information priors**:

- Treat the action as only weakly discriminative between hands.
- Update mostly via *legality* and *gross line consistency* (e.g., folding removes the hand; calling keeps it but doesn’t strongly reweight).
- Only use strong hand‑dependent reweighting where you have *some* model (e.g., P(bet)).

This mimics what DeepStack/Libratus do when they step outside their blueprint: they introduce gadget subgames and default policies that avoid over‑confident inferences rather than trying to be clever with no data.

### 1.2 Villain calls your bet (no call policy)

You know villain did **not fold** and did **not raise**; you don’t know how calling is distributed over hands.

A defensible rule:

- Remove impossible hands (cards seen on board/your hand).
- Apply **zero extra reweighting** for the call itself:
  - For every remaining villain combo \(h\):

    \[
    w_{t+1}(h) \propto w_t(h)
    \]

- Optionally, apply a *mild* structural reweight:
  - On very polar textures or huge bet sizes, slightly upweight hands that are structurally plausible calls (medium‑strength made hands, strong draws), and downweight pure air and nutted hands that would almost always raise in GTO:
    - This can be done with a hand‑class heuristic (e.g., made hand strength, nut potential), not another model.

For v1, I would recommend: **pure legality update only** for calls (no reweighting beyond card removal). This makes calls almost non‑informative, which is conservative but safe: you don’t hallucinate fake precision.

### 1.3 Villain raises your bet (no raise policy, no size model)

Raising *is* strongly informative in HU NLHE; doing nothing would be too weak. But you also don’t want to overfit.

Simple rule:

- Define a **hand‑class heuristic**:

  - Category A: nutty / very strong made hands and strong combo draws  
  - Category B: good but non‑nut value + strong draws  
  - Category C: bluff / junk

- For **small raises**:
  - Upweight A and B, mildly downweight C:

    \[
    w_{t+1}(h) \propto w_t(h) \cdot f_{\text{size}}(h)
    \]

  where \(f_{\text{size}}(h)\) is, e.g., 1.5 for A, 1.2 for B, 0.7 for C.

- For **large raises (overbets, jam)**:
  - Upweight polar hands (A + C), downweight middling value (B).

These hand‑class heuristics can be derived offline from your blueprint plus a generic solver: e.g., run GTO for a grid of textures and record which hand classes raise which sizes; convert to a coarse “raise‑suitability score” per hand class and size. That gives you a fixed table to drive \(f_{\text{size}}\).

If you’re worried about overfitting, cap the reweighting: don’t allow any combo to be multiplied by more than, say, 2× or less than 0.5× in a single update.

### 1.4 Villain bets into you (no bet‑vs‑check model, no size model)

Now you are OOP/IP facing a bet. You know:

- Villain did not check.
- Villain chose a size.

You have no P(bet) for villain’s range here, so treat it analogously to 1.3:

- Create a hand‑class heuristic mapping:
  - For each board texture and size bucket, which hand classes tend to bet?
- Update:

\[
w_{t+1}(h) \propto w_t(h) \cdot g_{\text{size}}(h)
\]

where \(g_{\text{size}}(h)\) is again a limited‑range multiplier (e.g., 0.7–1.5) with similar logic (value + draws for “normal” sizes; polar for overbets).

### 1.5 Your own actions (for your own range)

When **you** act, you *do* have P(bet). Use that heavily:

- If you bet: \(w_{t+1}(h) \propto w_t(h) \cdot P_{\text{blueprint}}(\text{bet} \mid s, h)\)
- If you check: \(w_{t+1}(h) \propto w_t(h) \cdot (1 - P_{\text{blueprint}}(\text{bet} \mid s, h))\)

For your own call/raise decisions (when you deviate from blueprint): either

- Use the *same* hand‑class heuristic scheme as for villain, or
- Better: record the *actual policy* used by your decision agent (e.g., if the resolver recommended a mixed call/raise/fold strategy for each of your combos) and feed that back into the tracker so your own range reconstruction is internally consistent with the strategy used to select your move.

In v1, using the resolver’s own recommended strategy to weight your range is ideal, because it’s exactly the distribution you plan to play from that node onward.

---

## (2) Per‑combo vs class‑level weighted ranges into TexasSolver

TexasSolver supports per‑combo weights (`AsKh:0.62`). There are two concerns:

- **Fidelity**: class‑level aggregation (e.g., all AKs share the same weight) smears differences in blockers and specific blueprint nuances.
- **Solve stability / performance**: more granular ranges can increase tree size and numerics.

In practice:

- DeepStack and Libratus represent ranges at full combo resolution internally; CFR‑based solvers natively work on individual information sets/combos.
- Commercial solvers (PioSolver, GTO+, GTO Wizard backends) all accept per‑combo ranges; their abstraction happens at *action abstraction*, not *hand abstraction* at this stage.

Given modern hardware and HU trees, **per‑combo weights are standard and sound**. Aggregating to class average is a premature optimization and will reduce the quality of blocker‑sensitive decisions (which your river/turn resolver especially cares about).

So for v1:

- **Use full 1326 per‑combo weighted ranges.**
- Only consider class‑level aggregation if you later find performance issues, and even then, keep full resolution at least on later streets (turn/river) where blockers matter most.

---

## (3) Fidelity: our range vs villain’s range

For the resolver’s recommended action **for you**, what matters more?

- Villain‑range fidelity: affects payoff and best response.
- Self‑range fidelity: affects how much your own mixed strategy is constrained by future counterfactual regret.

From the theory:

- If we treat the real‑time resolve as “solving a subgame from this public state given ranges,” then:
  - Villain range errors directly shift the EV landscape and can strongly change which action is best.
  - Your own range only matters to the extent the solver needs a consistent strategy for *both* players for future branches.

But you’re only going to *sample one action for one hand* from the solver’s strategy and use that; you’re not committing to perfectly follow the whole strategy tree.

This is very close to DeepStack’s setup: it cares most about **opponent range approximation** (via counterfactual value networks), while its own range is mostly known exactly from its internal strategy tracking.

Implication for you:

- **Villain‑range fidelity is much more critical** for EV than perfectly modeling your own mixed range.
- Your own range matters mainly for:
  - Future consistency (if you ever want to use the same subgame multiple times).
  - Exploitability from a perfect opponent who knows your entire strategy (not your main concern vs real humans / pools).

In an HU bot vs human scenario with limited real‑time resolving:

- Prioritize:
  - Accurate **villain range** narrowing (good priors, correct card removal, conservative but not crazy heuristics).
  - Exact **our hand** representation at the node (we know what we hold).
- Accept:
  - Rougher model of our *full* range distribution, especially in branches we’re unlikely to reach after our chosen action.

So your “fidelity budget” should go:

1. Villain range on current street and likely future lines.
2. Our own hand and immediate branch frequencies.
3. Full distribution of our range in exotic future branches (can be coarser).

---

## (4) Validating the range tracker without ground‑truth ranges

You won’t have labeled “true ranges,” but you can still test the tracker via **self‑consistency and EV‑based checks**.

### 4.1 Blueprint‑consistency tests

Offline, simulate a large number of hands where **both players follow the blueprint + some fixed policy for the missing actions** (e.g., a full GTO sim or your own agent).

- Log the *true* private hands used in simulation.
- Run your range tracker on the state sequence.
- At each node, compare:
  - The tracker’s posterior over hands vs the empirical distribution of hands present in the simulation at that node.

Metrics:

- KL divergence between tracker and empirical distributions.
- Calibration curves: for each probability bucket [0.0–0.1, 0.1–0.2, …], how often is the hand actually present?

Even if your blueprint is incomplete, you can fill in the missing actions with a fixed approximating policy for this evaluation only.

### 4.2 Solver‑based cross‑checks

Do a two‑step check at random nodes:

1. Take the reconstructed ranges (ours and villain’s) and run a local solve **A**.
2. Take “ground truth‑ish” ranges:

   - Either from a full‑game solver export (e.g., from a pre‑solved tree),
   - Or from your simulation log in 4.1 (using empirical frequencies).

   Run local solve **B**.

Compare:

- **Exploitability / EV difference**: how much worse is strategy A (from tracker ranges) when evaluated against strategy B’s ranges?
- In HU, you can approximate exploitability of A vs B by letting each best‑respond to the other’s strategy.

If the EV difference is small in big pots/high‑leverage spots, your tracker is “good enough.” If you see large EV swings, that node type / situation needs better tracking logic.

### 4.3 Internal consistency checks

For any real‑time state:

- Check **monotonicity** down a line: range width should not *increase* as more actions are observed.
- Check **plausibility of frequencies**:
  - E.g., at river facing big overbet, it’s implausible that villain still has 40% total air in range if your update logic thinks they rarely bluff here.
- Use **coarse equity sanity checks**:
  - Compute equity of your hand vs villain’s reconstructed range. If it’s wildly inconsistent with simple heuristics (e.g., solver says bluff‑catch but tracker says villain range is almost always nuts), flag for inspection.

These are not proofs, but they detect *gross* tracking failures.

---

## (5) Safe minimum‑viable tracker + gating by confidence

Your goal: a tracker that is **never worse than using the floor strategy**.

A naive tracker can be harmful if it:

- Over‑narrows villain to too weak a range → over‑bluff / over‑thin‑value.
- Over‑narrows villain to too strong a range → over‑fold.

A safe minimum‑viable design:

### 5.1 MV tracker rules

1. **Preflop**:
   - Use your existing class‑set priors for SB open / BB defend.
   - Expand to full combo distributions uniformly within each class.

2. **All streets, villain actions**:
   - Always enforce legality (card removal).
   - For *calls*:
     - Do **no Bayesian reweighting** beyond legality.
   - For *checks* where you have P(bet) for villain (if you ever train that):
     - Use the same P(bet) logic as for your own range: checked hands get weight × (1 − P(bet|h)).
   - For *bets/raises*:
     - Use **very mild** hand‑class heuristics with tight caps on multipliers (e.g., 0.8–1.25).
     - No multi‑step compounding of extreme multipliers down multiple streets.

3. **All streets, your actions**:
   - Use *full* P(bet) update for your own bet/check choices.
   - For your calls/raises made by the resolver:
     - Use the **resolver’s own action probabilities** as your update policy (since you have them).

This tracker is “safe” because:

- It never pretends to know a lot about villain’s calls.
- It only modestly reweights on aggressive actions.
- It’s very conservative; in the worst case, your villain range remains similar to the preflop prior + card removal.

### 5.2 Gating the resolver with a range‑confidence measure

You should **gate** whether you call TexasSolver at all based on a simple confidence score.

Define confidence \(C\) as a combination of:

- \(C_{\text{depth}}\): more actions taken → less confidence if many were of types you don’t model well.
- \(C_{\text{entropy}}\): if villain range entropy is extremely high (close to uniform) or extremely low (concentrated on tiny set), flag.
- \(C_{\text{support}}\): fraction of combos with non‑negligible weight; ultra‑narrow (<5% of starting combinations) is suspicious given poor information.

Example:

\[
C = 1 - \alpha \cdot \text{entropy\_normalized} - \beta \cdot \text{unmodeled\_actions\_count}
\]

If \(C < C_{\text{min}}\), **skip resolving** and fall back to the floor blueprint (or your non‑resolving agent). This prevents the resolver from being fed hallucinated inputs.

---

## How existing strong systems reconstruct ranges (and mapping to you)

### DeepStack

- Uses a **blueprint strategy** solved offline and a **deep counterfactual value network** to estimate the continuation values of ranges at depth‑limited frontier states.[DeepStack paper]
- In real time, it does **continual re‑solving**: at each decision point, it solves a local subgame given its *current belief* over both players’ ranges and uses the value network at depth cutoffs.
- Range tracking:
  - I
