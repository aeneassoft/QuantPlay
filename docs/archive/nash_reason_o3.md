# Nash theory (o3)

(Every statement below is a theorem, a corollary of a theorem, or an explicitly-labelled heuristic.  Standard game-theory references:  
– von Neumann (1928) minimax theorem;  
– Kuhn (1953) perfect-recall extensive-form;  
– Zinkevich et al. (2007) Counterfactual Regret Minimisation, CFR ⇒ ε-Nash in O(1/√T);  
– Burch et al. (2014) “solving Heads-Up Limit Hold’em” – exploitability definition now standard;  
– Brown & Sandholm (2019) safe/robust best response;  
– Bowling et al. (2015) Cepheus; Johanson (2013) exploitability bounds.)

1.  “If my self-play network is ε-expl oitable, what does that guarantee against GTOW?”

   Formalities.  Let Σ₁,Σ₂ be the mixed-strategy spaces of the two players, u the payoff to P1 and –u to P2.  
   v* = min_{σ₁∈Σ₁} max_{σ₂∈Σ₂} u(σ₁,σ₂) = max_{σ₂} min_{σ₁} u(σ₁,σ₂)  (von Neumann).  
   Exploitability of σ₁ is

      expl(σ₁) := max_{σ₂} [v* – u(σ₁,σ₂)].                       (1)

   σ₁ is ε-Nash ⇔ expl(σ₁) ≤ ε.

   Theorem 1 (immediate from (1)).  
     If σ₁ is ε-Nash, then ∀τ ∈ Σ₂,   u(σ₁,τ) ≥ v* – ε.                  (2)

   That is the ONLY universal guarantee.  Note what is NOT guaranteed:

     gap(τ) := u(BR(τ),τ) – u(σ₁,τ) (the “missed value” against that particular opponent)  
     can be arbitrarily large while expl(σ₁) stays small; nothing in (2) upper-bounds it.

   Application to HU NLHE.  The game is perfectly symmetric, so v* = 0 (conjectured, never mathematically proved but widely accepted, and empirically ≤10⁻³ bb/hand).  
   • If GTOW himself is εg-Nash, then max you can ever earn is εg (their own leak); conversely if they are exact GTO the ceiling is 0.  
   • Your observed –72 bb/100 means your σ is at least 72 bb/100 exploitable (Corollary of (2): if u(σ,GTOW)=–72, expl(σ) ≥ 72 because v*≈0).  
   • Playing an exact Nash would therefore raise you from –72 to  ≥ 0 but not above 0; “beating” a near-Nash opponent beyond the game value is impossible in a zero-sum game.

2.  “MIT push/fold statement v. existence of a Nash”

   Finite 2-player games always possess at least one mixed Nash (Nash, 1950).  The MIT remark addresses dynamics, not existence.

   Push/fold subgame with M = effective blinds:

   • For M≤2 the equilibrium in the restricted push/fold action space is essentially unique and best-response dynamics converge (a Lyapunov-stable fixed point).

   • For M≥3 several mixed equilibria exist in the push/fold-only subgame; best-response or fictitious play (Brown & Robinson, 1951) may cycle because every pure best response sends you toward the boundary of another region (classic Rock-Paper-Scissors behaviour).  That is “unstable” in the sense of learning dynamics, not non-existence.

   CFR (or any no-external-regret algorithm) still converges because the average strategy of the cycle converges to the convex set of equilibria (Hart & Mas-Colell, 2000).  So the “instability’’ just warns that naive one-shot best-response tuning of preflop ranges is unreliable; you must solve (or approximately solve) the mixed game.

3.  “Why minimising own exploitability ≠ maximising EV vs a fixed sub-optimal opponent”

   Proposition 2.  
     Let σ be ε-Nash.  For any opponent τ,

         u(σ,τ) = u(BR(τ),τ) – gap(τ)             with 0 ≤ gap(τ) ≤ u(BR(τ),τ) – (v* – ε).    (3)

   Nothing in regret minimisation controls gap(τ); CFR’s loss function is

         L(σ) = expl(σ) = max_{τ} [v* – u(σ,τ)],                     (4)

   which makes the worst case small but is totally indifferent to how much value you leave on the table against any
   particular τ that is not that worst case.  Therefore:

   • Minimising (4) is sufficient for safety, not for exploitation.  
   • To beat a KNOWN fixed τ* (GTOW) you should instead maximise u(σ,τ*) subject, optionally, to a safety constraint.

   Standard objectives for that are:

   (a) Pure best response:  σ := BR(τ*) – maximises win-rate but may itself become hugely exploitable.  
   (b) Robust best response (Brown & Sandholm 2019): maximise   min_{τ∈B(τ*,δ)} u(σ,τ)   where B is a KL-ball or L¹-ball around τ*.  Trades off EV and safety.  
   (c) Solve the full game once (minimum exploitability) and then do opponent modelling on top (double oracle, CFR-BR, or Exploitability Descent).

   For your concrete numbers:

   • –50 bb/100 comes purely from pre-flop frequency errors → that part can be repaired while keeping post-flop policy untouched; a near-Nash pre-flop (e.g. pre-solved 169-card-class range table at 200 bb) would by itself remove almost all of that leak and simultaneously shrink your overall exploitability.  
   • The –15 bb/100 deep-stack shove leak is another clear deviation from any Nash; again fixable without harming safety.  
   • The –10 bb/100 post-flop non-jam term is already small; further gain there almost certainly requires going from “safe” to “exploitative”, which is only worthwhile if GTOW has measurable post-flop leaks (uncertain).

   Correct training/evaluation pipeline given the stated goal “beat GTOW”:

   1. Compute/borrow an explicit near-Nash pre-flop strategy at 200 bb (fast, 169 × 169 matrix LP or modern depth-limited solver).  This deletes the lion’s-share safety leak.  
   2. Freeze GTOW, run CFR-BR or policy-gradient ascent on JUST your side to maximise u(σ,GTOW).  Keep a secondary constraint expl(σ) ≤ ε_safe (e.g. 20 bb/100) so you do not over-fit.  
   3. Validate with AIVAT or exact EV calculation on the hand log; compare both u(σ,GTOW) and expl(σ).  Stop when marginal EV gain ∆EV ≈ cost in added exploitability.

   That objective function – maximise “EV vs GTOW while bounding own exploitability” – is the mathematically consistent way to close the current –72 bb/100 gap.
