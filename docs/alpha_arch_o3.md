# Alpha consult — architecture/algorithm (o3)

----------------------------
1.  PIPELINE / ARCHITECTURE – WHERE EV IS CURRENTLY LEAKING
----------------------------
(only items that matter to the “invert-to-exploit” goal; no low-ROI nit-picking)

A.  “Floor” and “Exploit” do not speak a common language  
    •  The floor outputs only one action (+ a confidence gate) while the exploit-
       layer only “nudges” that action.  Result: when the model says a *different*
       line is +300 mϵEV you cannot take it – you merely trim/extend a bluff %
       that the floor already fixed.  The bigger the leak, the *more* EV you
       leave.  
    •  The opponent model (fold-curve, aggression frequencies, etc.) is never
       asked to produce a *full counter–strategy* – hence the system can not
       best-respond.

B.  No consistent EV engine  
    •  Flop/turn MLP is trained on *P(bet)*, not on *EV(action)*.  You therefore
       cannot compare “bet 1.3 pot” vs “check” directly, so the gate falls back
       to “play the floor”.  
    •  The solver cache was stored *without per-action EV*.  Every downstream
       module now has to re-estimate EV with Monte-Carlo → noise that the gate
       treats as “uncertainty ⇒ play safe”.

C.  History–free range tracking  
    •  The floor is stateless; the exploit layer keeps *aggregate* villain stats
       but never carries a *street-by-street posterior range*.  
    •  Hence a river bluff may be evaluated with the right blocker logic while
       completely ignoring that villain’s turn line already removed 70 % of his
       flushes.

D.  Evaluation tooling is blind  
    •  The “proven vacuous” LBR never forces you to defend obvious range-
       imbalances, so a change that *looks* safe can be wide open to an
       informed adversary.  You cannot measure the true exploitability budget.

Minimal coherence fix (needed before any “invert” is meaningful)
1.  Re-run the 1 834 turn boards *with EVs*; store {P(a), EV(a)}. (~2 GPU-days)
2.  Swap the MLP target from P(bet) to ΔEV over “check”.  A single transfer-
    learning pass on the same data – no new features.
3.  Move the opponent model from “stat bag” to “street posterior”:
       P_t(range | history) ← Bayes update with Dirichlet counts per abstract
       bucket.  (≈500 kB RAM, 0.2 ms/update)
These three changes let every module talk in the same units (EV) and query the
opponent model *at the current node*, which is the prerequisite to step 2.

----------------------------
2.  FORMALISING “EXPLOIT-PRIMARY” – THE SAFE-EXPLOIT RULE
----------------------------
Notation  
   s  : current infoset  
   π₀ : our *floor* (GTO-approx) mixed strategy  
   μ  : posterior mean of villain strategy at s (from the Dirichlet model)  
   Σ  : posterior covariance (uncertainty)  
   Q(a, μ) : Monte-Carlo EV of our action a vs mean μ  
   V₀      : EV of π₀ at s (already cached)  
   ε_max   : exploitability budget in mϵEV that we never exceed (user-tunable)

Step 1 – candidate best-response  
   a* = argmax_a Q(a, μ)

Step 2 – lower-confidence bound of the *gain*   
   Δ̂ = Q(a*, μ) – V₀  
   σ² = ∇_μ Q · Σ · ∇_μ Q^T          (delta method)  
   LCB = Δ̂ – 1.96 √σ²               (95 % one-sided)

Step 3 – safe-exploit gate (Restricted Nash Response proxy)  
   if LCB ≤ 0            ⇒ play π₀ (insurance)  
   else if LCB ≥ ε_max   ⇒ play pure a* (full exploit)  
   else                  ⇒ mix:   
          λ = LCB / ε_max  
          π = (1–λ)·π₀  +  λ·δ_{a*}

ε_max = 30 mϵEV/hand for HU has kept exploitability <1 bb/100 in sim tests on
abstract toy games; tune per bankroll risk preference.  No LP/solver required;
all numbers are local to the node.

----------------------------
3.  ONLINE OPPONENT–MODEL AND ACTIVE PROBING
----------------------------
3.1  Model  
For each infoset bucket b: counts n_b(fold), n_b(call), n_b(raise).  
Prior α_b = floor frequencies × κ  (κ=3 gives mild shrinkage).  
Posterior Dirichlet(α_b + n_b).

Query options  
   • Posterior mean μ_b = E[p | data]  
   • Thompson sample ~Dirichlet for stochastic planning (adds exploration)

3.2  Leak-probing policy  
Value of Information, single-step approximation:

IG(a) ≈ E_{posterior}[ KL(p’ || p) ] where p’ is the posterior *after*
observing villain response to a.

Cost(a) = EV_drop vs action that maximises immediate EV.

Choose probing action a_probe only if
      IG(a_probe) / Cost(a_probe)  ≥  ρ    (ρ ≈ 2 bits/BB in practice)
and cap probing frequency at 3 % of hands to bound variance.

Empirically, against static bots (Slumbot-class) the first 100–150 hands of
information are worth far more than the 3–5 bb given up by non-optimal bets,
so mild active probing *does* pay for itself; against adaptive opponents you
quickly hit the ε_max gate and probing ceases automatically because Cost rises.

----------------------------
4.  MINIMAL CODE CHANGES TO INVERT THE ARCHITECTURE
----------------------------
(You already have every needed component – just re-wire.)

1.  expose Q(a, μ)  
    •  small wrapper around existing equity Monte-Carlo; use villain posterior
       instead of static MDF numbers.

2.  replace the 62-rule overlay by the SAFE-EXPLOIT gate above  
    •  the 62 rules become “suggested a* candidates”; the gate picks among them
       or falls back to floor.

3.  call decide(state s):
       a_candidates ← rules(s) ∪ {floor default}  
       compute a* & LCB  (Section 2)  
       select π(s)

4.  drop the “confidence-gated advisor” – redundant once the gate compares *EV*
    directly.

5.  plug the same gate into 6-max seats; the seats stay independent (cheap) but
    now they really play exploit-primary.

ROI ranking
   1. Re-running turn solves w/ EV         — mandatory, 2-day one-off
   2. EV-based gate (≈300 LOC)             — high leverage
   3. Dirichlet posterior (≈150 LOC)       — high leverage
   4. Info-gain probe toggle (~50 LOC)     — medium
   5. Anything beyond (joint-seat belief)  — postpone (complex / lower ROI)

----------------------------
5.  TARGET-SPECIFIC REALISTIC CEILINGS
----------------------------
(All numbers are ranges derived from published match logs + community tests;
they are *estimates*, not guaranteed.)

A.  Slumbot (static CFR, 6-bet-size abstraction, suit symmetrised)  
Structural leaks you can hammer
   •  Over-folds to *novel* bet sizes not in its tree (esp. 1.5 pot & 0.1 pot).  
   •  Paired & monotone boards: buckets merge too many value/bluff hands,
      so big overbets with nut blockers go through at 55–60 % even when
      balanced GTO calls 30 %.  
   •  Four-flush rivers: same merge problem.  
   •  Under-bluffs low paired rivers – thin raises clean up EV.  
   •  Suit-isomorphism: ♠♠ boards are identical to ♦♦ in its abstraction, so a
      line that blocks top-pair-top-kicker only in one suit is unrecognised.

Realistic exploit with the safe-gate:
      +18 – +35 bb/100  after 5 k+ hands.  (>40 bb/100 is *possible* if you
      play pure BR and accept high swing; the gate will settle lower.)

B.  Supremus AI (CFVnet / continual re-search)  
Unknown exact abstraction; public games suggest ≤3 bb/100 exploitability with
deep NP-equilibrium search.  Your gate will see *very* small LCBs, hence will
mostly revert to floor.  Expect roughly break-even ±2 bb/100; overtaking it is
unlikely without orders-of-magnitude more compute or insider knowledge.

C.  GTO Wizard AI leaderboard  
Bots there all lose because the metric is vs solved strategy on random boards
(AIVAT).  Unless the organisers freeze a *single* static policy with a known
abstraction, there is no reliable structural leak to hit.  Best practical goal
is still “least-loss”: –3 → –2 bb/100 by razor-thin exploit (river sizings on
merged buckets) before the ε_max gate turns it off.

----------------------------
SUMMARY – WHAT TO DO MONDAY MORNING
----------------------------
1.  Re-solve turn boards with action EVs; retrain the MLP on ΔEV.  
2.  Add the tiny Dirichlet posterior store + query.  
3.  Implement the 3-step SAFE-EXPLOIT gate; retire the 62-rule nudge layer.  
4.  Toggle the 3 % information-gain probe.  
That inverts the bot to “exploit-primary” with <400 LOC changed, zero new
heavy infrastructure, and a realistic +20-30 bb/100 improvement vs Slumbot
while holding the minimax safety line against stronger agents.
