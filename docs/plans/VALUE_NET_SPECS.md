# VALUE_NET_SPECS.md — leaf-CFV value-net build specifications (deep-read, 2026-07-06)

Distilled from 4 local papers (all existence-verified, extracted via pdfplumber; page refs = PDF page of the
local file). Purpose: the engineering spec for OUR leaf-CFV net — the missing piece of the v4 path
(real-time depth-limited CFR + neural leaves, `ROADMAP.md`, memory `parallel-cfr-v4-path`).

Sources:
1. `books/papers/Supremus.pdf` — Zarick/Pellegrino/Brown/Banister, *Unlocking the Potential of Deep
   Counterfactual Value Networks* (PRIMARY: the improvements that made CFV nets actually win).
2. `books/papers/originals/DeepStack_2017_arxiv1701.01724.pdf` — the canonical baseline.
3. `books/papers/CFR/06027-AAAI26.XuH-GT.pdf` — Xu et al., *Deep (Predictive) Discounted CFR*, AAAI-26.
4. `books/papers/originals/ReBeL_2020_arxiv2007.13544.pdf` — SECONDARY: PBS value-net loop essentials.

Rule followed throughout: numbers/formulas are quoted from the extracted text; anything I could not find
is marked **NOT-FOUND**.

---

## (A) Input / output encoding — per paper

| | DeepStack (2017) | Supremus (2020) | ReBeL (2020) | VR-DeepDCFR+ (AAAI-26) |
|---|---|---|---|---|
| **Input** | pot size as fraction of players' total stacks + both players' ranges bucketed to **1,000 clusters** each, as probability vectors over buckets; public cards condition the bucketing (p.8, Fig.3 p.9) | flattened array of length **2,001**: both players' distributions over private hands + public cards "compressed into a single array of length 1,000" per player + 1 element pot as fraction of starting chips (p.5) | `1 (agent index) + 1 (acting agent) + 1 (pot/stack) + 5 (board card indices, card-embedded) + 2×1326 (infostate beliefs)` — **no card abstraction at all** (p.17–18) | infoset features (game-generic; poker encoding **NOT-FOUND** in main text — appendix is in the extended arXiv version) |
| **Output** | vector of counterfactual values per player per bucket (1,000 + 1,000), "interpreted as fractions of the pot size" (p.8, p.25) | "expected values of each of the 1,000 buckets, represented as a fraction of the current pot size" (p.5) | vector of values for each infostate of the indexed agent (1,326 hands), one agent per query (p.17) | per-action cumulative advantages `R(I,a|θ)` + average strategy `Π(I,a|ψ)` |
| **Net** | feedforward, **7 fully-connected hidden layers × 500 nodes**, "parametric rectified linear units for the output"; Fig.3 labels hidden layers "linear, PReLU" (p.8–9). 7 layers > strictly necessary — validation error flat beyond 5 layers at 10M samples (Fig.5, p.27) | "same architecture as DeepStack": 7×500 feedforward + external zero-sum network (p.5) | MLP, **6 hidden layers × 1536**, GeLU + LayerNorm; single net for ALL 6 value "layers" (end/start of every round) (p.8, p.17–18) | MLP 3×64 (small games) / 128 neurons (FHP); separate nets: cumulative-advantage R, instantaneous-advantage r (PDCFR+ only), history-value Q, average-strategy Π (p.6) |
| **Bucketing** | 1,000 buckets via "k-means clustering with earth mover's distance over hand-strength-like features"; preflop aux net inputs the **169** strategically distinct hands directly (p.26–27) | same 1,000-bucket scheme (p.5); details of DeepStack's river action-bucketing "were never presented" (Supremus p.4) | none — deliberate; unique policy per infostate (p.16–17) | n/a |
| **Key normalizations** | pot ∈ input as fraction of stack; CFV output as fraction of pot ("to improve generalization across poker situations", p.25) | same | pot/stack in input; stack/bet randomization for robustness (p.16) | utilities normalized to [−1,1] per game (p.6); learn **advantages**, not reach-weighted regrets (see §C) |

**Where the nets sit (leaf placement):**
- DeepStack: depth limit = end of current round; flop+preflop use the turn/flop/aux nets, the TURN solves
  to end of game with a bucketed river abstraction, the river solves exactly (Table 4, p.22). Only querying
  at round starts means "we don't need to include the bet faced as an input to the function" (p.22).
- Supremus: **value nets at the end of EVERY round except the final one** — including a river net queried
  from the turn (p.5–6). This kills the chance-branching blowup and is one of its main wins over DeepStack.
- ReBeL: always solves to end of current round; single net must learn six layers of values (p.17).

## (B) Training-data generation recipes (with counts)

### DeepStack (p.25–26)
Random situations = (pot, ranges, public cards); betting history NOT needed ("the pot and ranges are a
sufficient representation", p.25).
1. **Pot sampling** (verbatim footnote, p.25): "The fixed distribution selects an interval from the set of
   intervals {[100,100), [200,400), [400,2000), [2000,6000), [6000,19950]} with uniform probability,
   followed by uniformly selecting an integer from within the chosen interval." (First interval printed as
   `[100,100)` in the PDF — likely a typo for [100,200); flagged, not invented.)
2. **Range sampling** — recursive procedure `R(S,p)` assigning probabilities summing to p (verbatim, p.26):
   - "If |S| = 1, then Pr(s) = p."
   - "Otherwise, (a) Choose p1 uniformly at random from the interval (0,p), and let p2 = p − p1.
     (b) Let S1 ⊂ S and S2 = S \ S1 such that |S1| = ⌊|S|/2⌋ and all of the hands in S1 have a hand
     strength no greater than hands in S2. Hand strength is the probability of a hand beating a uniformly
     selected random hand from the current public state. (c) Use R(S1,p1) and R(S2,p2)."
   - Full range = `R(all hands, 1)`. Point: cover the range-space CFR visits during re-solving, "not just
     ranges that are likely part of a solution" (p.26).
3. **Counts + label solves:**
   - Turn net: **10 million** turn situations, each solved with **1,000 iterations of CFR+**, actions
     {fold, call, pot, all-in}, NO card abstraction. Cost: 6,144 CPU cores, "over 175 core years" (p.26).
   - Flop net: **1 million** flop situations, solved with DeepStack's own depth-limited solver + the
     trained turn net at turn leaves. Cost: 20 GPUs, half a GPU-year (p.26). → nets are trained
     **backward: deeper round first**, each round's labels bootstrap on the previously trained net.
   - Preflop auxiliary net: **10 million** situations; labels = enumerate all **22,100** flops and average
     the flop net's outputs (p.26).
4. **Optimizer:** Adam, Huber loss, mini-batch **1,000**, lr **0.001 → 0.0001 after 200 epochs**, ~350
   epochs / 2 days on one GPU, pick epoch with lowest validation loss (p.26).
5. Measured accuracy (fraction of pot, train/validation Huber): turn 0.016/**0.026**, flop 0.008/**0.034**,
   aux 0.000053/0.000055 (p.27). Caveat noted by the authors: multiple equilibria exist, so these losses
   may overestimate true error (p.27).

### Supremus (p.7–8) — the scaled recipe
- Subgames "generated in a manner identical to DeepStack". Each subgame solved with **4,000 iterations per
  player of DCFR+** (vs DeepStack's 1,000 CFR+) (p.7).
- Counts: river **50M**, turn **20M**, flop **5M**, preflop aux **10M** (DeepStack: no river net, 10M turn,
  1M flop, 10M aux) (p.7). Train order: river → turn → flop → aux (p.7).
- Resulting Huber losses (train/validation, Table 1 p.8):

  | Network | Supremus | DeepStack |
  |---|---|---|
  | River | 0.010 / 0.015 | N/A |
  | Turn | 0.008 / **0.010** | 0.016 / 0.026 |
  | Flop | 0.0092 / **0.011** | 0.008 / 0.034 |
  | Auxiliary | 0.000069 / 0.000070 | 0.000053 / 0.000055 |

  The flop validation loss is **3× lower** than DeepStack's (p.7) — driven by 5× data + better labels
  (DCFR+ 4,000 iters) + the river net removing the turn round's abstraction error.
- Headline causality: DeepStack-reimpl **loses to Slumbot −63±40 mbb/g**; with (i) DCFR+, (ii) GPU solver
  (1,000 flop iters in 0.8 s, >6× faster; exploitability 3 mbb/g reached >5,000× faster), (iii) more/better
  data, (iv) river net, (v) wider action set → Supremus **beats Slumbot +176±44 mbb/g**; LBR: 951±96 vs
  DeepStack-reimpl 536±68 (p.5–8). No single magic trick — convergence quality + net accuracy + data scale.

### ReBeL (p.6, p.16–18) — self-play bootstrap instead of random situations
- No random-situation generation: training PBSs come **only from self-play trajectories**
  (exploration ε = 0.25). Explicit negative result: "training on PBSs sampled uniformly randomly without
  information abstraction results in extremely poor performance in a value network" (p.17; Fig.2 p.9
  "Random Beliefs Value Net" flatlines). DeepStack's random-situation recipe only worked because of
  bucketing + its handcrafted realistic-situation samplers.
- Label = for the subgame rooted at β_r solved by T CFR-D iterations, add the **average over iterations**
  `(Σ_t v^{π_t}(β_r))/T` to the value-net data D_v (p.6, Algorithm 1). Leaf-PBS for the next subgame is
  sampled at a random iteration t ~ unif{0, T−1} so that "v̂ [is] accurate for leaf PBSs on every
  iteration" (p.6) — the net must be good on the ranges CFR passes through, not just at convergence.
- Value-net error bound: O(1/√T) for any PBS encounterable during play (Theorem 2, p.7).
- Training-scale numbers: circular buffer **12M** samples; Adam lr **3e-4** halved every 800 epochs; epoch
  = 2,560,000 examples; batch **1024**; results after 1,750 epochs; 90 DGX-1 (8×V100) machines for data
  generation (p.18). Stack sizes randomized $5,000–$50,000, bet sizes perturbed ±0.1×pot during training
  (p.14, p.16). All-in EVs are LEARNED, not the precomputed-rollout shortcut (p.17).

### VR-DeepDCFR+ / VR-DeepPDCFR+ (AAAI-26, p.4–6)
Model-free (no simulator): K outcome-sampling traversals per iteration; **advantage buffer cleared every
iteration** (bootstrap replaces replay); reservoir strategy buffer; circular history-value buffer 1e6.
FHP scale-up: 1e8 episodes, buffer 1e7, 128 neurons/layer. Hyperparameters: **α=2, γ=2** (VR-DeepDCFR+),
**α=2.3, γ=2** (VR-DeepPDCFR+); exploration ε in sampling policy `ξ = ϵ/|A(I)| + (1−ϵ)σ_t` (p.5–6).
Result: FHP head-to-head avg rewards **11.6±1.2** (VR-DeepDCFR+) / 11.3±0.9 (VR-DeepPDCFR+) vs
−7.8±1.4 (OS-DeepCFR) / −2.0±3.1 (DREAM) (p.7).

## (C) Loss functions + zero-sum constraint (verbatim)

### DeepStack zero-sum outer network (p.8)
> "This architecture is embedded in an outer network that forces the counterfactual values to satisfy the
> zero-sum property. The outer computation takes the estimated counterfactual values, and computes a
> weighted sum using the two players' input ranges resulting in separate estimates of the game value. These
> two values should sum to zero, but may not. Half the actual sum is then subtracted from the two players'
> estimated counterfactual values. This entire computation is differentiable and can be trained with
> gradient descent."

I.e. with per-bucket outputs f_1, f_2 and input ranges r_1, r_2: `err = r_1·f_1 + r_2·f_2;
f_i ← f_i − err/2` (formula reconstructed from the quoted prose; not printed as an equation in the paper).
Supremus uses "an external network to enforce that the weighted averages of the outputs for each player
sum to zero" (p.5) — same construction. AAAI-26 enforces zero-sum on the history-value net directly:
"Since we assume the game is two-player zero-sum, we have Q_1(h,a|w) = Q(h,a|w) and
Q_2(h,a|w) = −Q(h,a|w)" (p.6).

### Training criteria
- DeepStack: "Adam stochastic gradient descent procedure minimizing the average of the **Huber losses**
  over the counterfactual value errors" (p.26). Supremus: same, "Adam with Huber loss" (p.4).
- ReBeL: "We use pointwise Huber loss as the criterion for the value function and mean squared error (MSE)
  over probabilities for the policy. In preliminary experiments we found MSE for the value network and
  cross entropy for the policy network did worse." (p.8).

### AAAI-26 — why advantages, and the exact losses
Problem with regressing counterfactual values/regrets directly: "counterfactual values are expected
utilities weighted by opponents' reach probabilities, which diminish significantly over long episodes.
These reach probabilities vary widely across information sets, making it challenging for networks to
effectively learn values across diverse orders of magnitude" (p.4, citing Van Hasselt et al. 2016).
Fix: regress **advantages** `A^σ(I,a) = u^σ(I,a) − u^σ(I)`; relation `r_t(I,a) = π^{σ_t}_{−i}(I) A^{σ_t}(I,a)`
→ fitting cumulative advantages is a *weighted* CFR (p.2, p.4, Theorem 2 p.5).

Tabular updates being approximated (p.2–3):
- CFR+: `R_t(I,a) = max(R_{t−1}(I,a) + r_t(I,a), 0)`
- DCFR: positive regrets ×`(t−1)^α/((t−1)^α+1)`, negative ×`(t−1)^β/((t−1)^β+1)` each iteration; cumulative
  strategy `C_t(I,a) = C_{t−1}(I,a)·((t−1)/t)^γ + π_i^{σ_t}(I)σ_t(I,a)`
- DCFR+ (used by Supremus with a delay d): `R_t(I,a) = max(R_{t−1}(I,a)·(t−1)^α/((t−1)^α+1) + r_t(I,a), 0)`
- PDCFR+ prediction: `R̃_{t+1}(I,a) = max(R_t(I,a)·t^α/(t^α+1) + r̃_{t+1}(I,a), 0)`

Neural losses (Algorithm 1, p.4; discount/clip form p.6):
- Cumulative-advantage net (bootstrap from previous iteration's net, buffer cleared per iteration):
  `L(θ_t) = E_{(I,r̄)∼B_V} [ Σ_a ( max(R(I,a|θ_{t−1}),0)·(t−1)^α/((t−1)^α+1) + r̄(I,a) − R(I,a|θ_t) )² ]`
- Instantaneous-advantage net (PDCFR+ only): `L(φ_t) = E [ Σ_a (r̄(I,a) − r(I,a|φ_t))² ]`
- History value net (variance-reduction baseline, off-policy TD):
  `L(ω_t) = E_{(t,h,â,û,h′,I′,i)∼B_Q} [ ( û + Σ_{a′} σ^{t+1}(I′,a′) Q(h′,a′|ω′) − Q(h,â|ω_t) )² ]`
- Average-strategy net (DCFR's γ-weighting baked into the loss):
  `L(ψ) = E_{(I,t,σ_t)∼B_Π} [ (t/T)^γ Σ_a (σ_t(I,a) − Π(I,a|ψ))² ]`
- Baseline-corrected sampled values: `v̄(I,a|z) = Q(h,a) + (v̄(I′|z) − Q(h,a))/ξ_t(I,a)` if a = â else
  `Q(h,a)`; sampled advantage `r̄(I,a) = v̄(I,a) − Σ_{a′} σ_t(I,a′) v̄(I,a′)` (Algorithm 2, p.5).

**What transfers to OUR supervised CFV-label setting vs their RL-style setting:**
- TRANSFERS: (1) regress pot-normalized / advantage-like targets, never opponent-reach-weighted raw chip
  values (this independently re-derives our `train_cfv_net.py` target-standardization fix, ../NOTES.md);
  (2) the zero-sum constraint (outer-layer correction or Q_2 = −Q_1 symmetry); (3) DCFR+ as the LABEL
  solver schedule (their evidence + Supremus's: faster convergence per compute → better labels per CPU
  hour); (4) the (t/T)^γ average weighting if we ever distill an average policy.
- DOES NOT TRANSFER: bootstrapped per-iteration buffers, importance sampling, the history-value baseline —
  all exist to cope with sampled episodes and no simulator. TexasSolver gives us exact solves; our labels
  are supervised regression, so plain Huber on solver CFVs is the right loss.

## (D) Resolving / gadget procedure

### Continual re-solving state (DeepStack p.5)
Maintain only: own range + a vector of opponent counterfactual values (upper bounds). Updates:
> "(i) Own action: replace the opponent counterfactual values with those computed in the re-solved
> strategy for our chosen action. Update our own range using the computed strategy and Bayes' rule.
> (ii) Chance action: replace the opponent counterfactual values with those computed for this chance
> action from the last re-solve. Update our own range by zeroing hands in the range that are impossible
> given new public cards. (iii) Opponent action: no change to our range or the opponent values are
> required."
At game start: own range uniform, opponent CFVs = value of being dealt each hand (p.5). No opponent-range
tracking, no action translation (p.5, p.8).

### The CFR-D gadget game (DeepStack p.22, p.24)
> "the CFR-D gadget does this by giving the opponent the option, after being dealt a uniform random hand,
> of terminating the game (T) instead of following through with the game (F), allowing them to simply earn
> that hand's bound on its counterfactual value." (p.24)
Gadget value `GV^S_{w,σ}(σ^S) = Σ_{I∈I_2^S} max(w_I, BV_I(σ→σ^S))` (p.28). DeepStack picked the CFR-D
gadget over the max-margin gadget ("performed better in early testing", p.22).

**Warm-starting opponent ranges in the gadget (p.24):** two options — conservative: replace the uniform
deal with `b·(estimated range from previous re-solve) + (1−b)·uniform` (keeps guarantees); aggressive:
with probability b force follow-through with a hand from the estimated range (faster, loses guarantees if
the estimate is wrong). DeepStack uses this only for the FIRST action of a round, with **b = 0.9**;
conservative when second to act, aggressive when first to act (p.24).

### Solver inside the re-solve
- DeepStack: "a hybrid of vanilla CFR and CFR+, which uses regret matching+ like CFR+, but does uniform
  weighting and simultaneous updates like vanilla CFR. When computing the final average strategy and
  average counterfactual values, we omit the early iterations of CFR in the averages" (p.22).
  Table 4 (p.22): preflop 1000 iters (980 omitted), flop 1000 (500), turn 1000 (500), river 2000 (1000).
  Preflop aux net used only during the omitted iterations; final iterations do the full 22,100-flop
  enumeration; preflop re-solves are cached per betting sequence (p.22–23).
- Supremus **DCFR+** (p.7): DCFR modified so the average-policy weight of iteration t is
  `max{0, t−d}` (d = 100 in their experiments) instead of t², i.e. delayed-start LINEAR averaging.
  Convergence guarantee retained: O(1/√T). Plus: with a CFV net at the leaves, **simultaneous updates
  converge faster than alternating** (the reverse of the tabular folklore; p.7, Fig.3).
- ReBeL variant: leaf values are queried EVERY iteration at the current-iteration PBS
  (`v̂(s_i(z)|β_z^{π_t})`, CFR-D) or average-policy PBS (CFR-AVG) (p.6); test-time safety comes from
  "pick a random iteration and assume all players' policies match the policies on that iteration"
  (p.8, Theorem 3) — no explicit gadget needed if the net was trained by the self-play loop.

### Action abstraction inside lookahead (Table 2, Supremus p.8; coordinates disambiguated from the PDF)
| | 1st action | 2nd action | 3rd action | Remaining |
|---|---|---|---|---|
| DeepStack | F,C,0.5,1.0,2.0,A | F,C,0.5,1.0,2.0,A | F,C,1.0,A | F,C,1.0,A |
| Supremus | F,C,0.33,0.5,0.75,1.0,1.25,2.0,A | F,C,0.25,0.5,1.0,A | F,C,0.25,A | F,C,1.0,A |

(DeepStack Table 4 p.22 gives its per-round variant: ½P added on first/second actions, river
F,C,½P,P,2P,A.) Sparse-tree error study (Table 5, p.23): {F,C,P,A} is the sweet spot — L1 25.51 mbb/g on
a 61k-node tree vs 18.06 for the 555k-node 9-size tree; a single non-pot size is much worse
(F,C,2P,A → 64.79).

## (E) RECOMMENDED SYNTHESIS — our build (HU NLHE, TexasSolver labels, 15.7 GB RAM PC + optional pod)

Design stance: **DeepStack encoding + Supremus training recipe + AAAI-26 target hygiene; ReBeL only as a
warning about data distribution** (self-play-realistic ranges beat uniform-random ranges; we get realism
via DeepStack's R(S,p) sampler + range-tracker-derived priors, not via ReBeL's full RL loop — that needs
90 DGX-1s).

### Net spec (both gates)
- Input: `[pot/eff_stack] + board-one-hot(52) + range_OOP + range_IP` (range encoding per gate below).
- Output: two CFV vectors (one per player), **as fractions of the pot** (DeepStack p.25 normalization —
  this is the paper-grade version of our train_cfv_net standardization fix).
- Zero-sum outer layer (differentiable, in-graph): `err = r_OOP·f_OOP + r_IP·f_IP; f ← f − err/2`.
- Body: start small (3×256 for Gate-0/1 pilots; DeepStack's own ablation says ≥5×500 only pays at ≥10M
  samples, p.27). Huber loss, Adam, batch 1,000, lr 1e-3 → 1e-4 after plateau, keep best-validation epoch
  (DeepStack p.26). Validation split **by board** (our existing GATE B2 discipline).

### Gate-0 — Leduc toy (ties to `pokerbot/strategy/deep_cfr.py`; $0, exact-exploitability-gated)
Purpose: prove the full loop — (situation sampler → solver labels → CFV net with zero-sum layer →
depth-limited re-solve through the gadget → exploitability) — in a game where `deep_cfr.exploitability()`
is EXACT. This is the verification-grounding gate before any HUNL spend.
1. Situations: root-of-round-2 Leduc states = (public card, pot, both ranges over the 6-card deck).
   Sample ranges with the DeepStack `R(S,p)` recursive splitter (hand strength = rank vs public card).
2. Labels: solve each round-2 subgame exactly with the existing `vanilla_cfr` (or the `dcfrplus` flag)
   from `deep_cfr.py`; per-hand CFVs for both players.
3. Net: input ~ (pot + 3-card public one-hot + 2×6 range) → 2×6 CFVs; zero-sum layer as above.
4. Re-solve: at the round-1→round-2 boundary replace the chance-expanded subtree with the net; implement
   the CFR-D gadget (T/F opponent choice with w_I bounds, §D) for acting at round 2.
5. GATE: exploitability of (depth-limited + net) vs full solve, as a function of label count and net error
   — this empirically instantiates DeepStack Theorem 1 (`exploitability ≤ k₁ε + k₂/√T`, p.6) and tells us
   the ε→exploitability exchange rate before buying any HUNL labels.

### Gate-1 — HUNL river-then-turn CFV net (ties to `research/cfv_data.py`, `research/train_cfv_net.py`, `pokerbot/strategy/gto_oracle.py`)
Follow **Supremus train order: river net FIRST** (p.7) — river labels are single cheap exact TexasSolver
solves (no deeper net, no chance averaging), and the river was our measured #1 leak.
1. **Gate-1a river net.** Situation = (5-card board, pot, both ranges); sampler = R(S,p) ranges + the
   DeepStack pot-interval distribution rescaled to our 100bb game, MIXED with realistic ranges from our
   range-tracker/session logs (ReBeL's uniform-PBS failure, p.17, says purely synthetic uniform ranges
   would starve the net of the on-path distribution; DeepStack's own recipe is "cover the space CFR
   visits", p.26 — do both: ~70% R(S,p) / ~30% tracked-realistic. The exact mix is a knob, NOT-FOUND in
   any paper). Labels: one TexasSolver river solve per situation, {F,C,P,A} tree (Table 5 p.23 justifies
   this as the accuracy/cost sweet spot), extract per-combo CFVs via the B1-validated `cfv_eval`.
2. **Gate-1b turn net.** Labels per the ../NOTES.md 2026-06-16 vetted lesson (o3 + gpt-5.5,
   `docs/consults/nextrun_*`): **ONE `dump_rounds=2` turn+river solve + a single backward-induction pass**
   (river backward-pass + river CHANCE node with card-removal) — NOT the 48-river-average (which prices a
   forced turn check-check, omits turn betting, Δ up to 10–20bb on coordinated turns, and costs 48
   solves/sample). `k_rivers` stays a pilot-only debugging knob. Alternative (paper-canonical, DeepStack
   p.26): depth-limited turn solves querying the Gate-1a river net at river leaves — adopt whichever is
   cheaper per validated label once both are timed.
3. **Range encoding + the 169 suit-aliasing gate (BLOCKING, ../NOTES.md open risk):** our current 169-class
   input may alias suit-distribution information the CFV genuinely depends on (flush boards), and "more
   data cannot fix missing input information". Before any big run: same-board/same-169/different-suit
   direct-solve pairs; if weighted-CFV-L1 > ~0.75 bb → move to combo-level (2×1326, ReBeL-style — works
   without abstraction per ReBeL p.16, but needs far more data) or 169 + board-relative suit-blocker
   features. DeepStack's answer was 1,000 public-card-conditioned EMD buckets (p.26) — the middle ground
   if 169 fails the gate and 1326 is too data-hungry for our sample budget.
4. **Counts (honest budget).** Paper scale is out of reach (10M turn labels = 175 core-years at 1,000
   CFR+ iters, DeepStack p.26; Supremus 50M river). Our pilot ladder: 10k river labels (local CPU,
   mass-solve machinery) → train → Gate-0-style exchange-rate extrapolation → decide pod spend. A pod
   campaign inherits the 2-node discipline (CPU mass-solve local / long single-pod runs, no setup-barrier
   `ex.map` — the ZERO-samples root cause of 2026-06-16).
5. **Label solver settings:** TexasSolver accuracy knob ≈ the papers' iteration counts; target label
   noise ≪ net Huber target. Reference points: DeepStack 1,000 CFR+ iters; Supremus 4,000 DCFR+
   iters/player and its d=100 delayed-linear averaging (§D) — if we ever swap the label solver, DCFR+
   with delay is the measured-best schedule.
6. **Deployment target:** the flop/turn re-solver (`resolver_probe.py` / gto_oracle machinery) queries the
   net at round-boundary leaves exactly as DeepStack Table 4; gadget per §D with the b=0.9 warm-start rule.
   End state = Supremus's structure: value function at end of every round, wide first-action set, DCFR+.

### Explicit NOT-FOUNDs (do not cite these as known)
- DeepStack's turn-round river action-bucketing details ("never presented" — Supremus p.4).
- Supremus subgame-generation specifics beyond "identical to DeepStack" (p.7); its GPU kernel details.
- AAAI-26 poker-specific input encoding + network details beyond 3×64/128-neuron MLPs (in the extended
  arXiv version 2511.08174, not the local PDF).
- Any paper's optimal synthetic/realistic range-mix ratio (our 70/30 is a knob to A/B, not literature).
- ReBeL's exact Huber δ, and DeepStack's Huber δ parameter: not stated in either PDF.
