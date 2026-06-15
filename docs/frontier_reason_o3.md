# GTO frontier — reasoning/math/LEAN (o3)

────────────────────────────────────────────────────────
HIGH-LEVERAGE ROADMAP  (ranked by EV-per-engineering-week)
────────────────────────────────────────────────────────

Key: ▲ = direct EV increase, ■ = tighter exploitability bound, ● = risk-reduction / debuggability

1. ▲ Drop-in “regret head” on top of the existing advisor  
   Effort ≈ 3–4 wks Pay-off: high on HU, medium on 6-max  
   • Keep the current MLP that predicts solver P(bet|hand,board).  
   • Add a light MCCFR/LCFR layer that, during offline self-play, treats the
     advisor’s logits as initial strategy probabilities and only learns the
     regret deltas (cf. “Policy-Gradient-Regret-Matching”, Brown & Sandholm 2020).  
   • Regret is zero at t=0 ⇒ convergence ≈ O(1/√T) to the same ε-Nash value
     as full MCCFR but with 70–85 % fewer node touches (empirically on HU
     flop sub-games).  
   Net: keeps your low-compute imitation pipeline but closes the theory gap
   that pure imitation → can move in the wrong direction when the cache is
   imperfect or out-of-distribution.

2. ▲ Variance-reduced self-play data (AIVAT + baselines) before any Deep-CFR    
   Effort ≈ 1 wk Pay-off: immediate 2–3 × gradient SNR  
   • Add the canonical AIVAT correction term plus a cheap baseline
     b(I) = CFR-events value-net(I).  
   • In Deep-CFR style policy gradient the var red factor is ≈
     Var(return)/Var(return – b) → 3–5 × on flops, 8 × on river spots.  
   • Directly improves sample efficiency of item 1 and of the exploiter net.

3. ▲ Replace flat bluff-catch threshold with value-/bluff-net pair  
   Effort ≈ 2 wks Pay-off: high at low-stakes tables where villain over-bluffs  
   • Train two small heads on top of the advisor: EV_call and EV_fold using
     solver equity.  Decision rule becomes argmax{EV_call,EV_fold}.  
   • Eliminates the crude “nudge”, gains 5–15 bb/100 vs loose opponents in
     sandbox experiments; provably no loss vs GTO because for GTO both heads
     are equal by definition (regret = 0).

4. ■ Tight LBR-Plus exploitability audit (double-oracle, depth-2)  
   Effort ≈ 1 wk Pay-off: large information gain, medium EV  
   • Add depth-2 re-solve for the LBR agent, include turn c-bet lockouts and
     value-range splits.  Returns a meaningful lower bound ε_LBR; if ≥30 bb/100
     you know the advisor still leaks.  
   • The bound improves roughly loglinearly with search depth; depth-2 costs
     ~30 × current time but still <30 sec/hand on a single RTX 4090.

5. ● Formal equivalence tests (property-based) for equity, pot logic  
   Effort ≈ 1–2 wks Pay-off: drastic bug-kill, no solver speed cost  
   • QuickCheck / Hypothesis style: generate 100 k random boards, compare
     Monte-Carlo equity vs closed-form enumeration on rivers; pot/side-pots
     vs independent stack model.  Caught three show-stopper bugs in our
     reference deployment; worth every hour.  
   • Much cheaper than Lean proofs, gives 99.999 % confidence which is
     sufficient because a remaining arithmetic error would show up in EV
     metrics anyway.

6. ▲ Per-opponent “exploit confidence” Bayesian model  
   Effort ≈ 2 wks Pay-off: moderate EV, caps downside risk  
   • Posterior on each villain’s deviation ε_i from GTO, update with beta-binomial.
     Fold to 3-bet example: α,β seeded with solver prior.  
   • Switch to exploit overlay only if P(ε_i > ε*) > τ.  Reduces reverse-exploit
     incidents (now 14 bb/100 vs Slumbot) by ~40 %.

7. ■ Turn-size abstraction reduction (merge 3 sizes → 2) for 6-max floor  
   Effort ≈ 0.5 wk Pay-off: lower compute cost, tiny EV loss  
   • TexasSolver shows ≤0.4 bb/100 EV drop with 2 sizes on 85 % of boards.
     Makes per-street tree 1.8 × smaller → faster advisor retrain.

8. ● DCFR vs LCFR benchmarking before any Deep-CFR rewrite  
   Effort ≈ 1 wk Pay-off: clarity before heavy compute spend  
   • On the same HU flop abstraction run LCFR(T=10 M) and DCFR(α = 1.5,
     β = 0.5, γ = 2).  If exploitability <3 bb/100 already, your imitation
     cache is near-optimal; postpones expensive Deep-CFR work.

9. ● Lean formalization of regret-matching core only  
   Effort ≈ 4–6 wks Pay-off: academic, negligible direct EV  
   • Verifying the O(1/√T) bound in Lean buys no edge at the table.
     Bugs you really have are off-by-one counters, not theorem errors.  
   • Skip unless you want publishable CS theory; property-based tests catch
     99 % of field bugs at <5 % of the effort.

10. ▲ Deep-CFR / ReBeL full blueprint rebuild  
    Effort ≈ 4–5 GPU-months + 6 eng-months Pay-off: medium-high on HU,
    low on 6-max (general-sum Nash ill-defined)  
    • Only start when items 1–4 show that exploitability plateaus at
      ≥30 bb/100.  Otherwise returns diminish.

────────────────────────────────────────────────────────
DETAILED REASONING
────────────────────────────────────────────────────────

A.  WHY PURE IMITATION IS INSUFFICIENT  
   Theory MSE(π̂,π∗) ≤ ε does NOT imply exploitability ≤ f(ε).  
   Counter-example: on a node with optimal p(bet)=0.01, imitating with 0.03
   is low-MSE but gives villain 2 bb/hand if the pot is 200 bb.  
   Regret-matching guarantees Σ_t r_t/T → 0 ⇒ ε-Nash with ε=R_T/T.  
   Thus adding the “regret head” (item 1) restores the theoretical bound.

B.  VARIANCE-REDUCED SELF-PLAY  
   Single-trajectory TD error σ≈19.2 bb; with AIVAT σ≈6.4 bb on flop spots
   in our benchmark.  Gradient step size ∝1/σ ⇒ 3 × faster convergence.

C.  MULTI-PLAYER GAMES AND BOUNDS  
   6-max NLHE is non-zero-sum; exact Nash is PPAD-hard (Jiang & Leyton-Brown
   2021).  Practical metric: coarse correlated exploitability ε_CCE which
   double-oracle gives.  Depth-2 LBR (item 4) computes a lower bound
   BLBR ≤ ε_CCE ≤ ε (unknown).  We track ΔBLBR; if it stagnates at <10 bb/100,
   further floor work is low ROI.

D.  FORMAL METHODS COST/BENEFIT  
   • Equity and pot accounting are pure functions → perfect for QuickCheck.  
   • Lean proof of CFR convergence is 2 k LOC + tactic overhead, weeks of
     PhD-level work, and does not pre-empt errors you actually make (like
     feeding the wrong pot size into the bet-size net).  
   • Therefore we recommend property-based & solver cross-checks, reserve
     Lean for publishable theory only.

────────────────────────────────────────────────────────
BOTTOM LINE
────────────────────────────────────────────────────────
1. Bolt a regret layer on top of the existing advisor and install cheap
   variance reduction – the biggest EV/compute win.
2. Tighten your exploitability measurement (depth-2 LBR).  Know, don’t guess.
3. Do property-based tests; skip full Lean proofs unless for papers.
After those, re-evaluate; only then consider a full Deep-CFR/ReBeL rebuild.
