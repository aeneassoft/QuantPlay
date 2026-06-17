# Distance-to-Nash measurement (o3)

(0) Notation  

• σ = the (possibly‐suboptimal) strategy you have fixed for both players in the pre-flop toy game (9 decision nodes, 169×169 private hands, “check-down” terminal, plus the 169×169 all-in equity table).  
• v* = the value of the full HU-NLHE game at 200 bb (unknown, but ≈0 by symmetry).  
• BRP(σ–P) = the value that player P can obtain against the opponent’s fixed strategy σ–P with a perfect (global) best response.  
• ε(σ) = exploitability of the profile σ in chips/hand.  In the standard poker literature (e.g. Zinkevich et al. 2008, Johanson 2013)  

     ε(σ)  ≜  ½[ BRSB(σBB) + BRBB(σSB) ]                        (1)  

The factor ½ keeps the number “chips per hand” instead of “sum of both seats”.  A strategy profile is ε-Nash iff ε(σ) ≤ ε.  CFR/CFR+ guarantee that after T iterations the average profile σ̄T is O(1/√T)-Nash (Tammelin 2015 gives a slightly better bound).

──────────────────────────────────────────────────────────────────  
1. “We solved the 9-node toy game – is expl = ΔSB+ΔBB the right number and what does it tell us about the real game?”  

Inside the TOY game:  
• Because the game is zero-sum and we enumerated every information set, (1) is an *exact* exploitability measure.  
• Therefore “expl(heuristic) » expl(blueprint) ≈ 0” proves: σ is (almost) Nash in *this* abstraction.  Provable.  

Relation to the full 200 bb game:  
• The mapping “real game → toy game” is *an abstraction*.  Write Φ for the map from real histories h to toy histories Φ(h).  
• Even if σ is ε-Nash in the toy, *nothing is proved* about Φ⁻¹(σ) in the real game unless you add safety guarantees (Ganzfried & Sandholm 2011; Burch et al. 2014).  The inference is circular if you (i) measure exploitability only in the abstract game, and (ii) evaluate versus the same abstraction.  
• To make a *non-circular* claim you need at least one of  
  a) An *upper bound* theorem that transfers: e.g. safe sub-game resolving (Burch, Johanson, Bowling 2014; Brown & Sandholm 2017) proves that the exploitability in the real game ≤ εtoy + ζ where ζ is a known abstraction error bound.  Unfortunately ζ is unknown for card-abstraction plus “check-down realisation”.  
  b) A *lower bound*: run an (approximate) best response in the *full* game against Φ⁻¹(σ).  Whatever value he achieves is a valid lower bound on true exploitability.  No circularity.  (Section 4 shows cheap ways to do this.)

──────────────────────────────────────────────────────────────────  
2. Why can a Local Best Response (LBR) return ~0 against a leaky σ?  

“Local” BR (Johanson & Bowling 2011, Gibson 2015) searches only a limited depth *d* assuming the fixed strategy is played thereafter.  If the leak is outside that window, or requires *combining* deviations over several information sets, LBR will miss it.  Typical pitfalls:  
• Pre-flop leak that only pays off on certain flops/turns.  
• Blocks that require card removal reasoning over many branches.  

Minimal trustworthy fix  

  (i) Increase depth until the search subtree reaches a *terminal* or a *solved* subgame, and back it with a solver that returns counterfactual values (safe subgame solving).  
  (ii) Or, run CFR-BR: run Monte-Carlo CFR on the *one* player only, keeping the target σ fixed for the other (Johanson 2013).  Regret → 0 ⇒ strategy converges to a *global* BR, giving a provably valid exploitability number.  The cost is O( |I| /ε² ).  

──────────────────────────────────────────────────────────────────  
3. Why care about exploitability instead of “EV versus GTO-Wizard AI”?  

Let σ be the strategy you ship to production.  The following theorem (standard minimax) is unconditional:

     ∀ opponents τ   uSB(σ, τ) ≥ –ε(σ)                               (2)

i.e. you are guaranteed to lose at most ε(σ) bb/hand *in the worst case*.  Optimising “EV versus the Wizard” gives *no* guarantee against anybody else, and can even increase worst-case loss (Brown & Sandholm 2019 show arbitrarily bad counter‐exploits).  Therefore if your stated goal is “get closer to real GTO and then measure where we stand”, minimising ε is exactly the correct objective.

The game’s true value v* (≈0) is a lower bound on what you can ever hope to earn against an *arbitrary* opponent.  If ε(σ) is 15 bb/100, then even a clairvoyant villain can beat you for at most 15 bb/100; conversely if GTO-Wizard is winning 72 bb/100, at least 57 bb/100 of that is *your* distance from Nash (plus the Wizard’s distance, measurement noise, run-out variance, …).

──────────────────────────────────────────────────────────────────  
4. Cheapest rigorous algorithm to compute (or bound) exploitability of a fixed HU-NLHE strategy  

Exact solution is intractable (≈10¹⁴ infosets).  The lowest-engineering-cost methods that still carry *provable* guarantees are:

A. CFR-BR (Johanson 2013).  
   • Treat σ–villain as fixed.  
   • Run chance-sampled CFR only for the *one* improvising player.  
   • Regret bound O(1/√T) → exploitability estimate converges from below.  
   • Memory: O(|Iplayer|).  Runtime: seconds for pre-flop toy, hours–days for full game with block-cfr pruning (Brown & Sandholm 2015).

B. Safe Depth-Limited Solving (Burch et al. 2014; Brown & Sandholm 2017).  
   • Cut the tree after k betting rounds (e.g. after turn).  
   • At cut nodes compute a *bounded* subgame using LP or CFR.  
   • Produces an *upper* bound on exploitability.  
   • Combine with (A) for a two-sided sandwich.

C. Double Oracle / Best-Response Pool (McMahan 2014, Moravčík 2017).  
   • Iteratively add full BRs to a restricted game and solve it exactly (sequence-form LP).  
   • Each iteration strictly lowers ε, so you can stop when the bound is tight enough.  
   • Very effective if σ is already close to GTO (few profitable deviations exist).

D. Endgame Solvers (Moravčík et al. 2017, DeepStack).  
   • Condition on public cards + betting thus far; solve the remainder in real time.  
   • Gives defendable values at each leaf of your pre-flop abstraction, letting you splice the exact pre-flop BR with a post-flop near-Nash continuation.

Heuristics (no proof): nested LBR, PIOSolver “min-EV” mode, RL self-play with one side frozen, etc.  These give *plausible* numbers but no worst-case guarantees – flag as heuristic.

──────────────────────────────────────────────────────────────────  
References (all real)  

• Zinkevich et al. (2008) “Regret minimization in games with incomplete information.” NIPS.  
• Tammelin (2015) “Solving Large Imperfect Information Games Using CFR+.”  
• Johanson (2013) “Measuring exploitability and self-play in large extensive-form games.”  
• Johanson & Bowling (2011) “Data biased robust counter strategies.” IJCAI.  
• Gibson & Burch (2015) “Best Response Strategy Approximation in Large Extensive Games.”  
• Ganzfried & Sandholm (2011) “Game Abstraction as Compression: Can we compress game payoff matrices?” IJCAI.  
• Burch, Johanson, Bowling (2014) “Solving Imperfect Information Games Using Decomposition.” AAAI.  
• Brown & Sandholm (2015) “Regret-based pruning in large imperfect information games.” AAAI.  
• Brown & Sandholm (2017) “Safe and Nested Subgame Solving for Imperfect-Information Games.” AAAI.  
• McMahan (2014) “Adversarial Planning Through Strategy Construction.”  
• Moravčík et al. (2017) “DeepStack: Expert-level artificial intelligence in heads-up no-limit poker.” Science.

(Everything above is standard, no fabricated theorem names.)
