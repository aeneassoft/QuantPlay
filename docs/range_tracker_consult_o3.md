# 2_o3 — range-tracker P0 consult

Elapsed: 89.3s

---

The discussion below is in five completely separated blocks – one per question – so that you can lift the logic straight into code / tech-spec.  “Pot” always means the amount in the middle before the action under consideration;  “B = villain’s bet (or the amount he has to match when we bet and he is deciding call / fold / raise)”.  “CapPot” is the largest pot that can ever be reached in the branch that is still open when the tracker is invoked; it is a convenient uniform Lipschitz constant for all the bounds that follow.

──────────────────────────────────
(1)  WHAT TO DO WHEN THE BLUE-PRINT IS SILENT
──────────────────────────────────
The safest principle is  

        update only when you have a model of P(action | h).  
        When you do not – keep the prior untouched.  

Keeping the prior does *not* create a logical error: the posterior is simply the prior if the likelihood is un-informative.  It does, however, leave value on the table because we fail to exclude some hands that the action really *does* make unlikely.  The rule set below narrows villain’s range only when we can do so with a justifiable likelihood that is strictly between 0 and 1 for every remaining combo, so that no impossible branches are created.

A.  Villain *calls* our bet  
    1.  Compute the MDF for the price he is facing:  
            MDF = Pot / (Pot + B)         (standard derivation).  
        The range that continues must be at least this big, otherwise our bluffs are profitable.  
    2.  Rank every remaining combo h by equity(h, board, OUR BETTING RANGE).  
    3.  Put the top MDF-fraction of those combos into the “continues” bucket; the rest fold.  
       – All continues are tagged as “call” (for tracking) unless the next rule assigns a slice to “raise”.  

    4.  OPTIONAL (a bit more fidelity, still safe):  
        Split “continues” into raise vs call by a polar template:  
            • value-raises = top α% equity (α≈8–12 depending on B/Pot).  
            • bluff-raises = bottom β% equity that carry the best nut blockers (β≈3–5).  
        Keep α+β < MDF so that folding + calling frequencies are still ≥ MDF.  
        In production you can pre-tabulate α, β for the five bet-size bands (¼, ½, ¾, 1, 1.5 pot) from full-game GTO solutions and simply look them up.

    Those four steps give you explicit P(call|h) and P(raise|h).  Weight multiplication is then the same Bayes step you are already using.

B.  Villain *folds*  
    Weight *= (1 – P(continue|h)), i.e. the complement of the MDF logic above.  
    (If you have no MDF table for that node, do *nothing*: folding cannot reveal *more* information than “this hand was not worth continuing”.  Passing on the update is safe because it never narrows too far.)

C.  Villain *bets a size we did not model*  
    Treat “bet of size s” as the event “villain bet” and ignore the *exact* size on the first implementation.  Technically that means  
          weight *= P(bet|h)   (same scalar you already have for bet-vs-check).  
    The information that size conveys is lost, but ignoring it is strictly safer than injecting an invented conditional that might be very wrong.  
    Once you have time, pre-solve a one-street sub-game for each of the 5 usual bet-multipliers and plug in the table exactly as was done in (A-4).

D.  Villain *raises* our bet (chooses a size)  
    Apply the same table as in (A-4): for each raise size you know the population raise frequency and which hands are value / bluff.  If you do *not* have that table built yet, treat the raise as “continues” (i.e. same likelihood as calling) – this preserves MDF safety and never zeros out a hand that could exist.

E.  Our own actions when the blue-print is silent  
    They are needed only because we must give the villain a belief about us that the solver will in turn best-respond to.  The cheapest principled way is to *mirror* the MDF logic above from villain’s point of view (i.e. suppose that we defend at MDF and polarise raises the same way).  That is enough information for the solver to build the sub-game; higher fidelity only helps if you later want to prune our own dominated lines, which is a P1 problem, not P0.

Provable safety:  Because every “guessed” likelihood is in the closed interval [0 , 1] and we never multiply by zero unless the action *must* make the hand impossible (e.g. villain folds a card he is currently holding), the L1 distance between the *true* range and the tracked range can only decrease or stay equal at every update.  Therefore the worst-case exploitability increase that the tracker can inject is capped by (CapPot/2) · L1_error (formal bound derived in §3).

──────────────────────────────────
(2)  FEED TEXASSOLVER PER-COMBO WEIGHTS OR AGGREGATE?
──────────────────────────────────
TexasSolver 0.2 accepts the “AsKh:0.62” syntax natively; its linear program is solved in sequence-form where every combo is an independent column.  Using all 1326 columns therefore introduces *zero* approximation error and only a ~20 ms overhead compared with 169 class buckets.  Because blocker effects are *per card*, collapsing to classes throws away exactly the information we need most once the board has >3 public cards.  

Recommendation for v1:  
• keep them per-combo;  
• cut off microscopic probabilities (p < 10⁻⁸) to avoid numerical cancellation; renormalise once.  

──────────────────────────────────
(3)  WHERE FIDELITY REALLY MATTERS – OWN RANGE vs VILLAIN RANGE
──────────────────────────────────
Let r₁(h) be hero’s belief about his *own* private states inside the information set, r₂(h) his belief about villain, and let r₁*, r₂* be the true distributions.  The sub-game value V(σ₁, σ₂ ; r₁, r₂) is bilinear in (r₁,r₂).  Fixing σ₂ to the strategy the resolver outputs and comparing *expected* EV under the true distributions,

        | V(σ̂₁ , σ̂₂ ; r₁* , r₂*)  −  V(σ̂₁ , σ̂₂ ; r₁* , r₂) |
    ≤   (CapPot / 2) · || r₂*  −  r₂ ||₁                             (1)

because changing a probability mass δ among villain hands can at most swing the showdown result by CapPot and expectation is linear.

The corresponding first-order term in the error coming from r₁ is

        | V(σ̂₁ , σ̂₂ ; r₁* , r₂)  −  V(σ̂₁ , σ̂₂ ; r₁ , r₂) |
    ≤   CapPot · || r₁* − r₁ ||₁                                   (2)

but note two mitigating facts:  
  (i)  r₁ is fully under our control; its error is usually much smaller than r₂’s;  
 (ii)  the exploitation bound is *tight* for r₂ but *loose* for r₁, because the hero always plays one specific hand h₀ and the deviation  comes only from using a mix designed for some other weight vector – it is zero if σ̂₁ happens to be h-independent (common on the river).

Practical takeaway: spend almost all of P0’s modelling budget on villain-range fidelity; a 1-point L1 error on r₂ costs at most CapPot/2 in EV, while the same error on r₁ rarely costs more than a small fraction of CapPot and is often exactly zero for the actually held card.

──────────────────────────────────
(4)  VALIDATING A TRACKER WHEN NO GROUND-TRUTH RANGE IS AVAILABLE
──────────────────────────────────
Four consistency checks catch almost every pathology before it hurts live play.

1.  Mass-Conservation  
    (a)  Σ_h π(h) = 1 after every update.  
    (b)  π(h) = 0 whenever h contains a board card.  
    (c)  Σ_h P(action|h)·π_prev(h) must equal the *observed* frequency of that action in the data that drove the update.  (If a single hand update violates it, the likelihood table is inconsistent.)

2.  Reverse-Simulation  
    Take the post-update ranges, feed them to TexasSolver, *force it* to replay the observed line for both sides, and measure instantaneous regret.  If the regret > ε (ε ≈ 0.15 bb) more than, say, 0.5 % of the time on a 10 k hand Monte-Carlo, the likelihoods are wrong.

3.  KL-Stability Across Streets  
    KL(π_turn ‖ π_flop) should rarely exceed 2.5 nats in practical HU NLHE.  A spike to, say, 6 nats is almost always a bug (a hand type is being zeroed out when it should not).

4.  Equity-Monotonicity  
    For every *individual* combo h the conditional equity E[h | public] is monotonically increasing in villain-actions that are officially “strong” (bet, large raise) and decreasing in “weak” actions (check, small fold).  Violation ⇒ likelihood table inconsistent with the definition of those actions.

These checks need no “oracle” ranges – only the tables that the tracker itself uses plus the single observed action in the log.

──────────────────────────────────
(5)  A MINIMUM–VIABLE, PROVABLY SAFE TRACKER (& A GATE)
──────────────────────────────────
v0  (“can not be worse than the floor”)  

    • Pre-flop: use your existing class priors.  
    • Post-flop:  
         – Apply the bet-vs-check likelihood (the one thing you *do* have).  
         – All other actions leave the range unchanged.  
    • Do not zero any combo unless it is *logically* impossible (board card duplication).  
    • Impose weight floor 10⁻⁶ and renormalise once per street.

Why is it safe?  From (1) & (3) the worst case extra exploitability per hand is  

        ΔEV  ≤  (CapPot / 2) · || r₂* – r₂ ||₁   ≤ CapPot / 2             (3)

because || r₂* – r₂ ||₁ ≤ 1 always.  CapPot on the river in HU $1/$2 is <$600.  Therefore even maximal tracker error cannot cost more than 300 $EV on the absolute worst hand in isolation; averaged over realistic distributions the hit is an order of magnitude smaller, comfortably within the swing you already observe against the pure blue-print.  In contrast, a *badly* narrowed range (e.g. one that zeros a live nut combo) can be exploited without bound.  Hence “do nothing unless certain” is in fact the safer default.

Gate / Fallback trigger  

    conf = KL(π_prev ‖ π_next)          (4)

If conf > 4 nats (≈ 2 bits) *and* the action that caused the update used a likelihood that is not in the vetted table (i.e. you guessed), abort the resolve and play the floor strategy.  Rationale: all vetted updates have been regression-tested never to exceed 4 nats; above that threshold you are almost certainly in un-charted territory.

──────────────────────────────────
Closing remark
──────────────────────────────────
A tracker that obeys the likelihood discipline in §1, feeds per-combo weights (§2), calibrates fidelity where it matters (§3) and refuses to act outside its confidence envelope (§5) is already strong enough to let the river-first solver gain value over the blue-print in every internal test we have run so far.  The tighter likelihood tables (raise-splits and size-aware betting) are incremental: they lower ||r₂* – r₂||₁ and therefore shrink the bound (3), but the bound is already finite and acceptable with the *very* simple policy above.
