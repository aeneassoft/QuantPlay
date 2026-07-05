# River-corset consult (OpenAI math -> Claude technical)

## Context
SYSTEM UNDER TEST: a heads-up No-Limit Hold'em bot at 200bb. An LLM "brain" (a fine-tuned GLM-9B) drives a deterministic
poker ENGINE via program-of-thought: it emits Python calling engine APIs (equity, required_equity, mdf, pot_odds, spr,
board_texture, hand_rank, a TexasSolver node-solve) and the engine executes an exact legal action. Measured vs GTO Wizard
(a near-optimal solver opponent, AIVAT luck-adjusted): -94.14 bb/100 over 100 hands.

GROUNDED DIAGNOSIS (per-hand log): the loss is NOT pervasive. The worst 10 hands = ~103% of the total loss; the other
~90 hands are ~break-even. ~9 of those disasters are on the RIVER and are the bot CALLING a huge bet/overbet — e.g.,
villain bets b5100 (~51bb) into a ~20bb pot and the bot CALLS and loses ~40bb. So the bot's river BLUFF-CATCHING /
over-calling vs large bets is the spew. On most hands it plays fine.

HUMAN/OPERATOR INSIGHTS to evaluate + formalize (the user is an experienced player; treat as hypotheses to make rigorous):
1. The engine still carries a 'bet enough that the opponent folds' (fold-equity-maximizing) principle. The user argues
   this is WRONG at the river: the river is where VALUE is realized, real opponents (and a GTO opponent) do not over-fold,
   so river betting should be value + balanced bluffs (EV-driven), NOT sized to generate folds.
2. The LLM is partly trained on human/Reddit data, where an ALL-IN carries emotional/dramatic weight. For a bot an all-in
   is PURELY a mathematical EV decision (no drama). The corset must strip that human bias.
3. The user proposes: at the river, maybe do NOT try to estimate the opponent's exact range; instead anchor on OUR OWN
   UNEXPLOITABILITY — the minimum-defense-frequency derived from the (fixed) card-dealing distribution — so we cannot be
   exploited by bluffs/overbets regardless of the opponent's actual holding.
4. Commitment bias (context only, NOT our leak): humans who are already big-invested call river all-ins even when -EV.


## OpenAI: river_call_discipline
We are on the river. No further betting after this decision. Consider pot P before villain’s action and villain bets B. All amounts are in big blinds (or any consistent unit).

1. REQUIRED EQUITY TO CALL (INCLUDING OVERBETS)

Let:
- P = pot before villain’s bet
- B = villain’s bet
- C = our call amount = B
- E = our equity vs villain’s betting range, i.e. Pr(we win at showdown | villain bet)

If we FOLD:
- EV_fold = 0 (relative to current pot; we forgo the pot)

If we CALL:
- With prob E we win pot P + villain’s bet B + our call B = P + 2B
- With prob (1−E) we lose our call B

So
EV_call = E·(P + 2B) − (1 − E)·B
         = E·(P + 2B) − B + E·B
         = E·(P + 3B) − B

Call is breakeven when EV_call = 0:

E·(P + 3B) − B = 0
=> E·(P + 3B) = B
=> E_req = B / (P + 3B)

This is the **correct required equity to call** facing a bet B into pot P when the bet is already in the pot and we must invest B to continue.

Note the common confusion:
- B/(P+2B) is the required equity for **shoving B into a pot P when villain always calls**, not for calling a bet of size B into pot P.

2. MINIMUM DEFENSE FREQUENCY (MDF)

We want the **fraction of our range** that must continue (call or raise) to prevent villain’s pure bluffs from auto-profiting when he risks B to win P.

Suppose villain bluffs with frequency f over some subset of our range and we defend (do not fold) with probability MDF (as a function of our distribution), and villain always loses his bluff when called.

Bluff EV if we fold with prob (1 − MDF):
EV_bluff = (1 − MDF)·P − MDF·B

Set EV_bluff = 0 for indifference:
(1 − MDF)·P − MDF·B = 0
=> P − MDF·P − MDF·B = 0
=> P = MDF·(P + B)
=> MDF = P / (P + B)

This is **bet-size MDF**, including overbets (B > P). Diagnostics:
- B = P (pot-sized bet) ⇒ MDF = P / (P+P) = 1/2
- B = 2P (2x pot overbet) ⇒ MDF = P / (P+2P) = 1/3
- B → ∞ ⇒ MDF → 0

Interpretation: if we fold **more often** than 1 − MDF against polarized bets, villain can bluff profitably with any two cards.

3. BLUFF-CATCHER INDIFFERENCE (VILLAIN’S BLUFF RATIO)

Assume villain’s range when betting is polarized: value hands V and bluffs L.

Let:
- v = # of value combos that always beat our bluff-catcher.
- l = # of pure bluff combos that always lose when called.
- f = l / (v + l) = villain’s bluff frequency among bets.

If we call with a hand that loses to all value and beats all bluffs:
- Prob we win = f
- Prob we lose = 1 − f

EV_call = f·(P + 2B) − (1 − f)·B
As before, same structure, just with E replaced by f.

Set EV_call = 0:

f·(P + 2B) − (1 − f)·B = 0
=> f·(P + 2B) − B + f·B = 0
=> f·(P + 3B) = B
=> f* = B / (P + 3B)

Thus a **pure bluff-catcher** (always losing vs value, always winning vs bluffs) is indifferent to calling when the villain’s **bluff frequency** satisfies

f_bluff* = B / (P + 3B)

Equivalent in terms of l and v:

l / (v + l) = B / (P + 3B)
=> l = [B / (P + 3B)] (v + l)
=> l·(P + 3B) = B(v + l)
=> lP + 3Bl = Bv + Bl
=> lP + 2Bl = Bv
=> l/v = B / (P + 2B)

So at the point of indifference, villain’s **bluff:value ratio** (for the range that bets) vs a bluff-catcher is

(bluffs : value)_villain = B : (P + 2B)

This ratio is what we must implicitly or explicitly infer to decide if our call is +EV.

4. DISCIPLINED CALL RULE VS AN OVERBET

Given: villain bets B into P (B may be > P). We have a particular hand h.

Step A: Engine computes our equity for h vs a specified villain river betting range R_bet:

E(h, R_bet) = Pr(h wins at showdown | villain ∈ R_bet)

Use the engine’s equity() API: E = equity(hero_hand, villain_betting_range, board).

Step B: Compute required equity to call:

E_req(P, B) = B / (P + 3B)

Step C: Decision rule for correct, EV-based discipline:

- If E(h, R_bet) < E_req(P, B):
  - EV_call(h) < 0 ⇒ engine MUST fold h.
- If E(h, R_bet) > E_req(P, B):
  - EV_call(h) > 0 ⇒ calling h is **individually profitable** vs R_bet. If we are not using range-level constraints, calling is permitted.
- If E(h, R_bet) = E_req(P, B):
  - h is exactly indifferent; its behavior can be used for fine-tuning MDF.

This is the **local EV guard**: for any specific hand, never call if its equity vs the specified betting range is lower than B / (P + 3B).

To incorporate MDF/unexploitability (anti-overfold guard): see MDF implementation under corset_rules.


## OpenAI: river_bet_discipline
We now consider the case where WE are the bettor on the river with a polarized range: strong value and bluffs.

1. GTO VALUE:BLUFF RATIO AS FUNCTION OF BET SIZE

Let:
- P = pot before our bet
- B = our bet size
- We assume villain’s response strategy is to call optimally vs our bet size.

We want to choose our bluff:value ratio such that villain becomes **indifferent to calling vs folding** with a pure bluff-catcher.

Assume:
- Our value hands (V combos) always win when called.
- Our bluffs (L combos) always lose when called.

We bet all those V and L with same size B.

Villain’s decision with a bluff-catcher:
- If he calls: he wins vs our bluffs, loses vs our value.
- Our betting mixture fraction:
  - Prob(bluff | bet) = f = L/(L+V)
  - Prob(value | bet) = 1−f = V/(L+V)

If villain calls with bluff-catcher:

EV_call = f·(P + 2B) − (1 − f)·B

(He wins pot P and our bet B and his own call B when we are bluffing, and he loses his call B vs value.)

Indifference EV_call = 0 ⇒ same equation as earlier with f in place of E:

f·(P + 2B) − (1 − f)·B = 0
=> f·(P + 3B) = B
=> f* = B / (P + 3B)

Then the implied **bluff:value combo ratio** is

f* = L / (L + V)
=> L / V = f* / (1 − f*)
         = [B/(P + 3B)] / [1 − B/(P + 3B)]
         = [B/(P + 3B)] / [(P + 3B − B)/(P + 3B)]
         = B / (P + 2B)

Thus:

(bluffs : value)_hero = B : (P + 2B)

at game-theoretic indifference for villain’s bluff-catchers.

2. WHY "BET TO MAKE THEM FOLD" IS WRONG AT THE RIVER

On earlier streets, a bet can generate fold-equity that removes villain’s future-equity realization and changes the game tree.

On the **river**, there are no future cards or bets. All the information is already realized except for showdown.
Therefore:

- Our bet does not change any future equity realisation; it only redistributes current pot equity and adds new money.
- A purely "fold-equity maximizing" bet size that is larger than that which maximizes EV for our distribution often **lowers** our EV, because:
  - Our value hands may get called less often than is optimal.
  - Our bluffs risk too much relative to the pot and villain’s optimal MDF.

The right objective on the river is: **maximize EV of the entire range**, i.e., choose bet size and composition (value vs bluffs) such that

EV_range = Σ_h p(h)·EV_h(actions, responses)

is maximized given opponent’s optimal/estimated response.

In particular, for a given B and pot P, we want our bluffs-to-value ratio near the GTO ratio above unless we are deliberately exploiting villain’s misplays.

3. FORMAL EV OF AN ALL-IN / ANY RIVER BET

Let S_eff be the effective stack remaining behind the pot P when we act.
Suppose we consider shoving all-in for B = S_eff.

We model villain’s range after our shove:
- He folds with probability q.
- He calls with probability 1 − q, with some showdown equity E_hero vs his calling range.

EV_shove = q·P + (1 − q)·[E_hero·(P + 2B) − (1 − E_hero)·B]

Explanation:
- With prob q, villain folds and we win P.
- With prob 1 − q, villain calls; then we win with probability E_hero (winning total P + 2B) and lose with probability (1−E_hero) (losing B).

Behavioral/emotional valuations do not enter this formula. All-ins are mechanically evaluated by this expected value expression.

In the special case we are **pure bluffing** and villain never folds his calling range (q determined only by his folding range), E_hero = 0, so

EV_bluff_shove = q·P − (1 − q)·B

and our bluff will be profitable if

q > B / (P + B)

which is another classic ratio but for fold probability, not for required equity of a call.

River betting discipline: when betting or shoving, we should
a) evaluate EV_shove (or EV of chosen bet size B) explicitly via the engine; and
b) constrain our bluff:value ratios to not exceed B:(P+2B) unless exploiting known overfolds.


## OpenAI: unexploitability_vs_range
We compare two approaches for defense vs a river bet:

(A) MDF-BASED DEFENSE (UNEXPLOITABILITY ANCHORED ON POT GEOMETRY)

We treat villain as potentially adversarial and assume he can choose his bluff:value composition to maximize EV, but his **bet size B given pot P is fixed**. We want a defense that guarantees villain’s pure bluffs cannot auto-profit, independent of his actual holding.

From earlier, MDF = P / (P + B) ensures that **any pure bluff** has EV ≤ 0.

This is purely geometric (depends only on P and B) and does not require modeling villain’s range.
It is correct in the worst-case, zero-sum sense:

- If we fold more than 1 − MDF, then there exists a bluffing strategy at that bet size for which villain’s EV > 0.
- If we always defend at least MDF of our range (and our continuing range is not outright dominated), bluffs **cannot** be auto-profitable.

But MDF **does not** say which specific hands must defend, it only constrains the total *fraction* of our range that cannot fold.

(B) RANGE-BASED DEFENSE (EQUITY VS VILLAIN’S ESTIMATED R_BET)

Given an estimated villain betting range R_bet composed of value and bluffs, we can compute for each candidate call hand h its equity

E(h, R_bet) = Pr(h wins | villain ∈ R_bet)

and use the required-equity threshold E_req = B/(P+3B) to decide whether the call is individually +EV.

This is **correct** if our model R_bet is accurate. It yields **exploitation** as opposed to pure unexploitable defense: we fold more often vs under-bluffers, call more often vs over-bluffers.
However, if R_bet is wrong (e.g. we assume over-bluffing, villain actually under-bluffs), it may result in:
- Calling hands that are -EV vs villain’s true range.
- Still not folding enough combos to satisfy MDF (or folding too much), leading to exploitability.

(C) WHEN EACH IS CORRECT

- MDF is correct as a **lower bound constraint** on our defense frequency that holds for all possible villain bluff mixes at that bet size.
- Equity vs R_bet is correct for **hand selection among candidate defendable hands** given an approximate model of villain’s strategy.

GTO theory: at equilibrium, both views coincide:
- Villain’s bluff:value ratio at that bet size is fixed by his own optimization;
- Our calling region is chosen by equity thresholds;
- Our overall defense probability against that bet equals MDF.

But if we do not know villain’s true composition, MDF alone
- prevents over-folding but
- does **not** prevent calling with bad hands and folding better ones, as long as the total defend fraction is respected.

(D) WHAT SHOULD THE CORSET ANCHOR ON?

Given your observations: the LLM is **over-calling** huge river bets vs a near-GTO opponent, causing large losses.
Thus the main failure is:

- Calling with hands that (given the solver’s range) do not meet E_req.
- Possibly defending **more** than MDF with hands too weak.

For a GTO opponent, MDF is already implicitly respected by equilibrium. Over-calling vs such an opponent will always lose.

Therefore, the CORSET should:

1. **Primary anchor:** local EV correctness via E(h, R_bet) ≥ E_req(P,B). This ensures no hand individually makes a call that is mathematically -EV against the engine’s best-guess R_bet (which, for GTO Wizard, can be taken from a solver node or an approximate equilibrium model).

2. **Secondary constraint:** a global MDF lower bound to prevent pathological over-folding when the model of R_bet is extremely conservative (e.g. we think villain always has it). I.e., from the set of hands with E(h, R_bet) ≥ E_req, we must defend at least MDF fraction of our pre-bet range (or whatever range reaches that node), by taking the highest-equity subset.

So the corset logic:
- NEVER call a hand whose equity vs R_bet is below the required threshold (prevents spew calls).
- If after that filter we are still under-defending (< MDF), promote the strongest folded hands up to reach MDF — but *only* if their equity shortfall is small or villain is known to bluff some min amount; else accept controlled exploitability as better than spewing.

Given your current problem (over-calling vs a solver), the dominant constraint must be the **equity-based local EV check**. MDF is a structural bound but should not be used to force additional calls in this setup.


## OpenAI: corset_rules
The corset should be deterministic and numeric, implemented as guards between the LLM proposal and the final engine action, specifically on the river.

I. RIVER CALL DISCIPLINE GUARD

Trigger: We face a river bet B into pot P.

Inputs:
- P: current pot before facing bet
- B: bet size
- hero_range: distribution of hero holdings reaching this node
- villain_range_bet: range for villain conditional on betting B (from a solver node, static model, or worst-case construction)

Step 1: Compute required equity to call

E_req = B / (P + 3B)

Step 2: For the current hand h, compute its equity vs villain’s betting range

E_h = equity(h, villain_range_bet, board)

Step 3: Hard guard: local EV correctness

If E_h < E_req − ε_call_margin:
    FORCE FOLD
else:
    hand is eligible to call

where ε_call_margin is a small positive margin to bias against thin call-spew, e.g. ε_call_margin = 0.01 (1 percentage point) or 0.02.

Rationale: ensures that we never call an overbet with a hand that is clearly below breakeven equity vs our betting-range model.

Step 4: Range-level (optional) MDF safeguard

Let MDF = P / (P + B).

Define:
- eligible_set = {h in hero_range: E_h ≥ E_req − ε_call_margin}
- total_weight = Σ_{h in hero_range} w(h)
- eligible_weight = Σ_{h in eligible_set} w(h)

If eligible_weight / total_weight ≥ MDF:
    We may call with h only if it is in eligible_set.
Else:
    We are under-defending if we fold all ineligible hands.
    In this case, we implement one of two strict policies:
    (Conservative, anti-spew policy, recommended vs GTO Wizard)
    - Do NOT force additional calls; accept under-defense.
    OR
    (Balanced policy, if wanting strict MDF adherence)
    - Sort all h ∉ eligible_set by E_h descending.
    - Promote top hands until defense frequency reaches MDF, but only if for promoted hands E_h ≥ E_req − ε_MDF (ε_MDF small, say 0.03).

Given your current failure mode (over-calling vs GTO), use **conservative policy**: do not override equity guard to chase MDF. That is, never promote any hand with E_h < E_req − ε_call_margin.

Step 5: Call frequency cap vs very large overbets (anti-LLM-dramatic-all-in bias)

For overbets where B ≥ α·P (e.g. α = 1.5 or 2):

- Enforce additional constraint: our calling frequency across the range cannot exceed a maximum f_call_max(B/P) strictly below 1.

Example functional form:

x = B / P
If x ≤ 1:
    f_call_max = 1.0   (no extra cap vs ≤ pot-sized bets)
Else:
    f_call_max = MDF(x) + δ
where MDF(x) = P / (P + B) = 1 / (1 + x)
and δ is a small slack, e.g. δ = 0.10.

Implementation:
- Let base_defended_set = eligible_set (E_h ≥ E_req − ε_call_margin).
- If |base_defended_set| / |hero_range| ≤ f_call_max:
    leave as is.
- Else:
    only call with the top K eligible hands ranked by E_h, where K is the maximum s.t.
    defended_weight / total_weight ≤ f_call_max.

This stops the LLM from hero-calling nearly the entire range against massive overbets, even if its range model misestimates villain’s bluffs.

II. RIVER BETTING / SHOVE DISCIPLINE GUARD

Trigger: We are on the river and have the option to bet or shove.

Inputs:
- P: pot
- S_eff: effective stack (max B we can bet)
- candidate bet sizes: {B_1, ..., B_n}
- hero_range: our range
- villain_range: villain’s range

Guard 1: Disallow "fold-equity only" bets not backed by EV

For each candidate bet size B_i and for each line type (value, bluff), compute via engine:

For each hand h in hero_range:
   - If designated as value for B_i: compute E_h_call = equity(h, villain_call_range(B_i), board)
     Require E_h_call ≥ E_req_value(B_i) = ???
     (for pure value, we typically require E_h_call > 0.5 or high enough that EV(bet) ≥ EV(check); compute explicitly).
   - If designated as bluff for B_i: compute EV_bluff(B_i, h) = q·P − (1 − q)·B_i, with q from villain_fold_prob model.
     Require EV_bluff(B_i, h) ≥ EV_check(h)

If for a candidate B_i the aggregate EV of entire range EV_range(B_i) < EV_range(check):
    forbid that bet size B_i as a whole.

This ensures we are not selecting huge overbets just to "make them fold" if they do not actually increase EV.

Guard 2: Value:bluff ratio bound per size

For a chosen bet size B into pot P, require our bluff:value combo count to satisfy

L / V ≤ B / (P + 2B) + ε_bluff

with small ε_bluff ≥ 0 (e.g. 0.05) to allow slight over-bluffing for exploitative play.

Implementation steps for a given B:

- Determine candidate value set V_B (hands where EV_bet_as_value(B,h) ≥ EV_check(h) + margin_value).
- Determine candidate bluff set L_B (hands where EV_bet_as_bluff(B,h) ≥ EV_check(h) + margin_bluff).
- Compute L = total_weight(L_B), V = total_weight(V_B).
- If L / V > B/(P + 2B) + ε_bluff:
    - Trim bluff set: sort L_B by EV_bet_as_bluff(B,h) ascending and remove lowest-EV bluffs until
      L / V ≤ B/(P + 2B) + ε_bluff.

Guard 3: All-in / very large bet cap

If B ≥ β·P for some β (e.g. β = 1.5 or 2), require stronger conditions:

- Only allow all-in if
  EV_range(shove) ≥ EV_range(best_non_allin_bet) + Δ_allin
  where Δ_allin ≥ 0 (e.g. 0 or small positive to bias *against* dramatic shoves).
- Additionally, for B ≥ β·P, require
  L / V ≤ B/(P + 2B)
  (no ε_bluff slack) i.e. do not allow over-bluffing with massive bets.

III. IMPLEMENTABLE GUARD PSEUDOCODE FOR CALLS (CORE ANTI-SPEW)

On river, facing bet B into P, with hero holding h and villain_betting_range R_bet:

1. E_req = B / (P + 3B)
2. E_h = equity(h, R_bet, board)
3. If E_h < E_req − ε_call_margin:
       action = FOLD
       return
4. Compute x = B / P
   If x > 1:
       MDF = P / (P + B)
       f_call_max = MDF + δ
       // approximate our distribution at this node from hero_range_reach
       // compute eligible_set and its weight; cap as described

But the minimal in-practice corset to remove the disastrous spew is simply Steps 1–3 plus an overbet frequency cap:

- **Hard rule:** never call river with a hand whose equity vs R_bet is below B/(P+3B).
- **Supplementary rule:** for B ≥ 1.5P (overbet) restrict calling frequency to at most MDF + 0.1 by dropping lowest-equity eligible callers.

This pair of guards is sufficient to eliminate huge -EV calls while retaining unexploitable structure vs plausible ranges.


## OpenAI: key_formulas
Compact formula list (all on river, heads-up):

1) Required equity to call facing bet B into pot P

- Call EV:
  EV_call = E·(P + 2B) − (1 − E)·B = E·(P + 3B) − B

- Breakeven (EV_call = 0):
  E_req = B / (P + 3B)

2) Bluff-catcher villain bluff frequency threshold

Given villain bets value+bluffs with probability f of bluffing (among bets), our pure bluff-catcher is indifferent when

- EV_call = f·(P + 2B) − (1 − f)·B = 0
⇒ f* = B / (P + 3B)

3) Villain bluff:value ratio at our bluff-catcher indifference

Let v = #value combos, l = #bluff combos in villain’s betting range.

At indifference:

l / v = B / (P + 2B)

4) Minimum defense frequency (MDF) vs bet B into pot P

To make villain’s pure bluff EV ≤ 0:

- Bluff EV when we defend with prob MDF:
  EV_bluff = (1 − MDF)·P − MDF·B

Indifference EV_bluff = 0:

MDF = P / (P + B)

5) Our own optimal bluff:value ratio when WE bet B into P (villain has bluff-catcher)

For our betting strategy to make villain’s bluff-catcher indifferent:

- Bluff frequency among our bets:
  f_bluff = B / (P + 3B)

- Bluff:value ratio in our betting range:
  L / V = B / (P + 2B)

6) EV of our river shove B (e.g. all-in) into pot P

Let q = Pr(villain folds to shove)
Let E_hero = equity of our hand vs villain’s calling range (conditional on call).

EV_shove = q·P + (1 − q)·[E_hero·(P + 2B) − (1 − E_hero)·B]

Special case (pure bluff, E_hero = 0):

EV_bluff_shove = q·P − (1 − q)·B

Breakeven fold frequency for bluff shove:

q_req = B / (P + B)

7) MDF as function of overbet ratio x = B/P

MDF(x) = P / (P + B) = 1 / (1 + x)

8) Our calling required equity vs overbet ratio x = B/P

E_req(x) = B / (P + 3B) = x / (1 + 3x)

These formulas are all that is needed to implement the corset’s guards (required-equity check, MDF, bluff:value ratio bounds, and EV-based bet/shove evaluation).

## Claude: technical implementation

