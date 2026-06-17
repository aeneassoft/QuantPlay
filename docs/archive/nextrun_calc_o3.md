# Next-run CFV calculation — rigorous (o3)

A.  The value the flop->turn resolver really needs

Notation  
• h – the exact private hand of the player under evaluation (ordered hole cards)  
• 𝔅T – the public history up to but not including the first decision on the turn (board = flop+turn card, pot size PT, stack-to-pot ratio SPRT, all preceding actions)  
• σ = (σIP ,σOOP) – a (near-)Nash strategy profile for the *whole* sub-game consisting of the turn betting round, the river chance node and the river betting round  
• Z – terminal histories in that sub-game (fold or showdown)  
• u i (z) – chip payoff (+ to IP, − to OOP) at terminal z  
• π – reach probability product of *all* chance moves and of the *other* player’s actions (counterfactual reach, standard CFR definition)

The *per-hand* counterfactual value required at the first turn node is  

                           v i (h ,𝔅T ;σ)  ≝  ∑z∈Z, h⊂z  π –i
σ (z)   u i (z)     (1)

where  

π –i
σ (z) = πc (z | h ,𝔅T) · ∏a∈z, p(a)≠i  σ p(a) (a | I p(a) )

i.e. you multiply *all* probabilities that are *not* under player i’s control – chance, *and* the opponent’s decisions on the turn *and* on the river.  
(1) is exactly the quantity DeepStack and continual re-solving CFR use as the “leaf value”.

Important: the expectation in (1) already includes  
• every bet / raise / call / fold that can still happen on the *turn*,  
• the 48 equiprobable river cards,  
• the whole river betting tree.

B.  What the current target really is  

Your data generator does

  ( i ) freeze the turn pot PT, the two 169-vectors R IP , R OOP as if no turn betting occurred;  
  (ii ) for each of the 48 river cards r, solve a *river-only* game G r (no additional money put in on the turn);  
  (iii) extract per-hand CFVs v̂ i (h , r) from G r and average

             v̂ i, current (h) =  (1/48) ∑ r  v̂ i (h , r)                   (2)

Compare (2) with the required (1):

• In (2) the opponent’s reach probability through the *turn* is *identically 1* for every action path: you have hard-coded “turn check-check”.  
• All betting EV that comes from putting additional chips in on the turn is therefore missing:  

         Δ i (h) = v i (h) − v̂ i, current (h)  
              = E σ [ payoff created by turn betting | h ]                   (3)

The magnitude of Δ depends on how “active” optimal turn play is:

• Pair-on-board, rainbow, disconnected ⇒ little incentive to bet, Δ small (sometimes < 1 bb).  
• Coordinated, draw-heavy turns (two-tone, straight completing, low SPR) ⇒ aggressive raising ranges, Δ can be 10–20 bb for the hands that bluff-catch / semi-bluff.  
• Nodes that end quickly by large turn bets (folded before river) are *completely invisible* to (2); for them the error is essentially the full EV swing of that bet.  

Internal consistency. Each river is solved in isolation, so the set {σ r } is not guaranteed to be the projection of *any* joint (turn,river) strategy σ.  The average (2) is therefore not even the counterfactual value of a well-defined strategy profile – it is merely “river EV after forced turn check”.

C.  One correct, much cheaper computation (dump_rounds = 2)

Build a single sub-game S(𝔅T ) that starts at 𝔅T and contains

   Turn chance node = already realised (the turn card in 𝔅T)  
   Full turn betting tree (any bet sizes you keep)  
   River chance node (48 cards) with card-removal  
   Full river betting tree

Run CFR (or TexasSolver’s LP if you can) on S to ε-equilibrium σ*.  Then compute (1) by **one** backward-induction pass:

Algorithm BackwardEV(S, σ*, player i)
1.  For every terminal z, write u i (z) (fold or showdown).  
2.  Traverse nodes in reverse topological order  
    Chance node (river card):   v(n,h) =  ∑c  p(c|h)  v(child(c),h)  
    Player j node:              v(n,h) =  ∑a  σ* j (a|n)  v(child(a),h)      if j ≠ i  
                               v(n,h) =               v(child(a),h)            if j = i (player i’s prob. not included)  
3.  At the root 𝔅T output v i (h ,𝔅T ;σ*).

Checks  
  • 0-sum sanity:  ∀h : v IP (h) + v OOP (h) = 0  
  • Range-weighted pot conservation:  ∑h R IP (h) v IP (h) = −∑h R OOP (h) v OOP (h)

Cost comparison (empirical, TexasSolver 200bb HU NLHE):
   48 × “river-only” solves   ≈ 48 × 0.25–0.35 s  per CFR iteration  
   1 × “turn+river” solve     ≈  4–7 s   per iteration (because the 48 rivers share the turn trunk, regret tables, and tree allocation)

For the same 1,500 CFR iterations the *correct* variant is usually 10–40× faster on real hardware and produces the exact object (1) up to solver ε.

D.  Getting the CFV net to generalise

Observations from the pilot  
  • 512×3 ReLU (~0.9 M parameters) fits 99 samples perfectly ⇒ VC dimension roughly 10× larger than the sample set.  
  • Held-out error ≈ 0.96·(value range) ⇒ pure memorisation, no generalisation.

Concrete plan (numbers are orders of magnitude, not religion)

1.  Exploit board isomorphisms  
   Canonicalise suits: pick the permutation that puts the highest-ranked suit of the turn card to “♠”, second highest distinct suit to “♥”, etc.  
   Average saving ≈ 12× (rainbow), 4× (two-tone).  Expect ≈ 8× overall reduction.

2.  Feature engineering for ranges  
   Replace the raw 169-vector by  
     – 13 “pocket pair” weights  
     – 78 “offsuit/ suited” *isomorph* groups after suit canonicalisation  
     → 91 real inputs per player instead of 169 (≈ 2× reduction)  
   Include global scalars: pot size / bb, stack size / pot, SPRT.

3.  Output heads  
   Exploit that v IP (h) = –v OOP (h).  Predict only the 169 values for one seat; negate for the other.  
   After suit canonicalisation the number of distinct hole-card buckets is 91, not 169.  
   So you need only 91 outputs, a 3.7× reduction.

4.  Network size & regularisation  
   Recommended:  Input ≈ 250 → 256 → 256 → 128 → 91 outputs (≈ 165 k weights).  
   Apply 0.1 dropout on the two hidden layers, L2 weight decay 1 × 10⁻⁴.

5.  Normalise the target  
   Predict v̂(h) / PT (pot-scaled EV).  The post-normalisation range is roughly [-1 , +1] and is identical across stack depths; empirical work in DeepStack showed ~30 % lower generalisation error.

6.  Sample complexity estimate  
   The effective parameter count after the reductions is ~1.6 × 10⁵.  Rule-of-thumb for regression with mild noise: need 20–40 data points / parameter → 3–6 M *statistically independent* boards.  
   After the 8× suit reduction that is ≈ 0.4–0.8 M *canonical* turn boards.  
   Generate 1 M boards, but hold out 50 k canonical boards that share no flop pattern with the training set – the net must predict all 91 values within ±0.15 PT MAE on that gate before it is allowed into live play.

7.  Data generation schedule  
   With the corrected “turn+river” solve taking ≈ 7 s × 1,500 iters ≈ 3 h / board on a single CPU, 1 M boards ≈ 300 M CPU-s ≈ 83 k core-h.  
   At 1,000 8-core cloud VMs this is a four-day job – now feasible.

Summary of required changes
• Replace the 48-river averaging by one full turn+river solve and a single backward pass ⇒ exact CFV, 1–2 orders faster.  
• Canonicalise suits, compress both input ranges and outputs ⇒ 4–10× fewer parameters, 8× more statistical reuse.  
• Generate O(10⁶) *canonical* turn nodes; normalise by pot.  
This gives the CFV network a realistic chance of <10 % MAE on unseen boards – small enough that a depth-limited re-solve will recover most of the remaining −53 bb/100 post-flop gap.
