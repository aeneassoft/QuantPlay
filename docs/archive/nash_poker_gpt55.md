# Nash in poker — practical (gpt-5.5)

Short version: **your fire is preflop**. At 200bb HU, a crude “top-84% open to 2.5bb + crude defenses + loose stack-offs” can absolutely lose at the scale you are seeing. **Fixing preflop and killing deep-stack all-in spew is the highest-ROI move by far.** Your postflop non-jam term being only ~−10 means you should not spend the next month polishing river probes while torching 50–65 bb/100 before/at preflop all-ins.

---

## 1. Is HU 200bb preflop cleanly solvable to Nash?

### Exact answer: **only approximately in the real no-limit game.**

There are two different meanings of “solvable”:

| Game definition | Solvability |
|---|---|
| Fixed stack, fixed blinds, **fixed preflop size menu**, fixed postflop abstraction / continuation values | Yes, CFR-style methods can solve very accurately. |
| Full HU NLHE 200bb with continuous bet sizes and exact postflop game tree | No public “clean exact Nash chart” exists. It is approximated. |

Preflop is much more tractable than postflop because it has fewer public states, but it is **not independent** of postflop. A preflop hand’s EV depends on postflop realization across thousands of boards. So “preflop Nash” is really a root strategy attached to a postflop equilibrium/approximation.

### How close is GTO Wizard preflop to true Nash?

I cannot audit GTO Wizard’s proprietary engine, so I will not pretend to know its exact exploitability. But practically:

- It is almost certainly **orders of magnitude closer** to a strong HU 200bb equilibrium than your current heuristic.
- Any residual GW preflop error is likely in marginal mixed frequencies and size-dependent details, not “losing 50 bb/100 preflop.”
- For your purposes, treat GW’s preflop as **near-Nash enough that crude self-play heuristics will get punished**.

Your −50 bb/100 preflop term is not plausibly explained by “GTO Wizard preflop is slightly off.” It is your bot.

---

### Where real HU 200bb Nash-ish preflop differs from “open top-84% to 2.5bb”

A fixed top-X open model is too crude in several ways.

#### A. SB/button does not just open a monotone top 84%

In HU, SB/button posts 0.5bb, acts first preflop, but has position postflop. That creates a very wide VPIP strategy.

At no rake, strong equilibrium-ish SB strategies often include:

- raising,
- limping,
- limp-calling,
- limp-reraising,
- folding some trash,
- mixing premiums between raise and limp-trap lines,
- mixing marginal hands between raise/limp/fold.

A simple “top 84% raise, bottom 16% fold” misses the limp part. Depending on allowed sizes and rake, the SB may VPIP **well above 84%**. Some hands that are not profitable as 2.5bb raises may still be profitable limps.

So your 84% frequency may be in the rough neighborhood for a **raise-only 2.5bb abstraction**, but it is not a real HU 200bb preflop equilibrium.

#### B. Real preflop ordering is not pure raw hand strength

A strength model usually overvalues raw equity and undervalues:

- suitedness,
- connectivity,
- blockers,
- domination/reverse-implied-odds,
- nut potential,
- postflop playability,
- position.

Example categories:

- Some suited trash / connected hands can outperform higher “raw strength” offsuit junk.
- A5s-type hands can be useful as 3bet/4bet blockers at low frequency.
- Hands like K4o/Q5o/J6o may look “high-card decent” in a crude model but realize badly.
- Medium offsuit dominated hands can be traps at 200bb.

#### C. Limping matters

At 200bb, limping is not just a fish action. A Nash-ish SB strategy can use limps for:

- weak hands that do not want to invest 2.5bb,
- medium hands that want cheap realization,
- traps,
- hands that benefit from keeping BB’s range wide.

If your bot lacks a serious limp strategy, it is forced into bad raise/fold choices.

#### D. Multiple open sizes can matter

If the game allows multiple sizes, equilibrium may use/mix sizes such as:

- limp,
- 2.0bb,
- 2.25bb,
- 2.5bb,
- sometimes 3.0bb.

A single 2.5bb size is playable as an abstraction, but then the strategy must be solved for that abstraction. You cannot just say “top 84%.”

#### E. BB defense is not crude MDF or top-X

Versus a 2.5bb SB open, BB is getting a price and closing preflop action, but will be OOP postflop. Strong BB defense uses:

- wide calls,
- 3bets with value and blocker/semi-bluff hands,
- some mixed folds,
- size-dependent adjustments.

A common crude leak is either:

- overfolding BB and letting SB print, or
- overdefending garbage that realizes terribly OOP, or
- 3betting/calling with badly constructed ranges.

Your attribution saying preflop is near “always-fold level” suggests the whole preflop response system, not just SB open frequency, is broken.

#### F. 3bet/4bet/5bet ranges mix heavily

At 200bb, real strategies are not:

> “premium = raise, medium = call, weak = fold.”

They mix:

- AA/KK sometimes slowplay/call,
- QQ/AK often continue but are not automatic 200bb stack-offs,
- suited Ax blocker hands can 4bet bluff at small frequency,
- some suited broadways and pairs mix between call/3bet/fold,
- 5bet strategies are narrow and highly size-sensitive.

Deep stacks make this more important because mistakes get amplified.

---

## 2. 200bb all-in discipline: what hands can profitably get all-in preflop?

### Key point: there is no universal 200bb “stack-off chart.”

The profitable call/jam range depends on:

- open size,
- 3bet size,
- 4bet size,
- whether the jam is a 4bet jam, 5bet jam, or 6bet jam,
- pot odds,
- villain’s range,
- blockers,
- whether you are jamming with fold equity or calling off.

But as a practical rule versus near-GTO at 200bb:

> **Do not treat QQ, AK, JJ, TT, AQ as automatic preflop stack-offs.**  
> **AA is the only trivial full-stack preflop get-in. KK is often mixed/contextual. Everything else is line-dependent.**

That is the brutal practical answer.

---

### Normal 200bb line example

Suppose blinds 0.5/1.

Line:

- SB opens 2.5bb.
- BB 3bets to 10bb.
- SB 4bets to 25bb.
- BB jams 200bb effective.
- SB has 25bb in and must call 175bb more.
- Final pot if called ≈ 400bb.

SB’s equity threshold:

\[
\text{Required equity} = \frac{175}{400} = 43.75\%
\]

So when facing that 200bb jam after 4betting to 25bb, you need roughly **44% equity versus villain’s jamming range**.

That is a high bar.

Approximate equities:

| Hero hand | Villain range | Rough equity | Incremental EV of calling 175 into 400 |
|---|---:|---:|---:|
| KK | AA only | ~18% | ~−103bb |
| QQ | KK+ | ~18% | ~−103bb |
| AKs | KK+ | ~23% | ~−83bb |
| AKo | QQ+/AK | ~38–40% | ~−15 to −23bb |
| QQ | QQ+/AK | ~39–41% | ~−10 to −19bb |
| AA | KK+/bluffs | huge | very +EV |

These are approximate, but directionally decisive.

So if your bot is calling 200bb jams with QQ/AK because “heads-up ranges are wide,” it can bleed catastrophically.

---

### Practical 200bb stack-off discipline

#### Facing a full 200bb preflop jam after normal 3bet/4bet sizing

Default versus near-GTO:

- **AA:** call/jam always.
- **KK:** call sometimes / often depending on node; not always mandatory if villain’s jam range is too AA-heavy. Against proper GTO with enough blocker bluffs, KK may be protected as a call/mix.
- **QQ:** usually not a full 200bb call-off after shallow 4bet investment unless pot odds/range are very favorable.
- **AKs/AKo:** continue in many non-all-in lines, but not automatic 200bb stack-offs.
- **JJ/TT/AQ/AJs/etc.:** do not stack off 200bb versus near-GTO.

#### As the jammer

A Nash-ish 200bb all-in range is polarized and low-frequency:

- Value: mostly **AA**, **KK**, sometimes context-dependent **AKs/QQ** in later/committed nodes.
- Bluffs: low-frequency blocker hands, often Ax-suited/Kx-suited type hands, but only if the fold equity and blocker effect justify it.
- Pure spew: jamming medium pairs, AQ, KQs, random suited connectors, weak Ax at high frequency.

Important distinction:

- **A5s as a blocker bluff jam** may be theoretically mixed in some node.
- That does **not** mean “A5s wants to get called for 200bb.”
- It means its jam EV comes from fold equity and blockers. If called, it usually hates life.

---

### How much does too-loose 200bb stack-off bleed?

A lot. One wrong deep preflop call can cost 80–120bb at the decision.

Example: You 4bet to 25bb, face a 200bb jam, and call QQ versus KK+.

- Required equity: 43.75%.
- Actual equity: ~18%.
- Incremental loss versus folding:

\[
0.18 \times 400 - 175 = 72 - 175 = -103bb
\]

That is one hand.

So an overall −15 bb/100 all-in leak can come from a very low frequency of bad stack-offs. For example:

- If a bad all-in decision costs ~100bb,
- then making it only 0.15% of hands contributes:

\[
100 \times 0.0015 \times 100bb = 15bb/100
\]

So yes: your measured **−15 bb/100 deep preflop all-in term** is entirely consistent with “getting it in as a dog at 200bb.”

On your reported “−385/−527 per hand on preflop all-ins”: I need to flag unit ambiguity. If those numbers are bb/100 on the all-in subset, that is −3.85 to −5.27bb per all-in occurrence, which may include many jams that got folds and AIVAT smoothing. If those are raw bb per hand, that exceeds a 200bb stack and is a scaling/reporting issue. But directionally, the diagnosis is clear: **your all-in subtree is toxic.**

---

### Emergency safety patch

Until you have a proper preflop solve:

1. **Ban open-jams and early 3bet/4bet jams at 200bb.**
2. Allow 200bb preflop call-off mostly with:
   - AA always,
   - KK only in approved high-bluff / solver-known nodes.
3. Do not call full-stack jams with:
   - QQ,
   - AK,
   - JJ,
   - TT,
   - AQ,
   - suited broadways,
   unless the pot is already so bloated that equity threshold is much lower.
4. Prefer non-all-in 4bets/5bets to preserve fold/call/jam structure.

This may overfold some mixed theoretical bluff-catchers, but it should immediately cut the catastrophic tail.

---

## 3. What preflop bet-size abstraction does your self-play net require?

### fcpa = fold/call/POT/allin is not good enough for HU 200bb preflop.

For deep preflop NLHE, fcpa is a bad abstraction because it misses the important size geometry.

Preflop needs:

- small opens,
- limps,
- realistic OOP 3bets,
- realistic IP 4bets,
- non-all-in 5bets,
- all-in only late in the tree.

With fcpa, your bot is forced into distorted decisions:

- SB can limp or pot-open, but may miss 2.0/2.25/2.5bb opens.
- BB pot-3bet sizes may be wrong relative to normal HUNL sizes.
- 4bets/5bets become too chunky.
- “All-in” appears as the only large-size option, encouraging deep-stack jam spew.

At 200bb, that is dangerous.

---

### Minimal preflop size menu

If you want a practical from-scratch Deep CFR abstraction, I would use at least something like this.

#### SB unopened

Actions:

- fold,
- limp,
- raise 2.0bb,
- raise 2.5bb,
- optionally raise 3.0bb.

Minimal acceptable version:

- fold,
- limp,
- raise 2.5bb.

Better:

- fold,
- limp,
- raise 2.0bb,
- raise 2.5bb,
- raise 3.0bb.

#### BB versus SB limp

Actions:

- check,
- raise to 3.5bb,
- raise to 4.5bb or 5bb.

You need BB iso sizes. Limp pots are a big part of HU equilibrium if limps are allowed.

#### BB versus SB open

Versus open size \(R\), include:

- fold,
- call,
- 3bet to about 3.5x open,
- 3bet to about 4.5x open.

Examples:

| SB open | Smaller 3bet | Larger 3bet |
|---:|---:|---:|
| 2.0bb | 7bb | 9bb |
| 2.5bb | 9bb | 11bb |
| 3.0bb | 10.5bb | 13bb |

You can simplify to one 3bet size, but then it should be realistic, usually around 9–11bb versus 2.5bb.

#### SB versus BB 3bet

Actions:

- fold,
- call,
- 4bet small: around 2.2x–2.5x the 3bet,
- optionally 4bet larger.

Example versus BB 3bet to 10bb:

- call,
- 4bet to 22bb,
- 4bet to 25bb or 27bb.

Do **not** make 4bet jam the only aggressive option.

#### BB versus SB 4bet

Actions:

- fold,
- call,
- 5bet non-all-in to around 50–65bb,
- jam, but with low equilibrium frequency.

Example:

- SB 4bets to 25bb.
- BB can 5bet to 55–65bb.
- BB can jam 200bb, but this should not be overused.

The non-all-in 5bet is important. If your abstraction only has call/pot/allin, it may force hands into bad shove/fold buckets.

#### After a 5bet

At that point, allow:

- fold,
- call,
- jam.

You may also include a non-all-in 6bet, but for a minimal abstraction, 5bet non-all-in + 6bet jam is probably acceptable.

---

### Practical minimal abstraction recommendation

If compute is limited, use this:

**Unopened SB:**

- fold,
- limp,
- R2.5.

**Versus limp:**

- check,
- R4.5.

**Versus open:**

- fold,
- call,
- 3bet to 10bb versus 2.5bb open.

**Versus 3bet:**

- fold,
- call,
- 4bet to 24bb.

**Versus 4bet:**

- fold,
- call,
- 5bet to 60bb,
- jam.

**Versus 5bet:**

- fold,
- call,
- jam.

That is not perfect, but it is dramatically better than fcpa for 200bb.

If you can afford more, add:

- 2.0bb open,
- 3.0bb open,
- two 3bet sizes,
- two 4bet sizes,
- maybe two iso sizes versus limp.

---

### Important: do not let self-play learn the wrong abstraction equilibrium

Deep CFR will minimize regret in the game you give it. If the game only has fold/call/pot/allin, it can become excellent at a **bad toy game** and still lose badly versus GTO Wizard’s real-size strategy.

This exactly matches your audit warning:

> minimizing self-play regret is not the same as maximizing bb/100 versus GTO Wizard AI.

If your action abstraction is wrong, self-play convergence is not enough.

---

## 4. How much of HU 200bb EV is preflop versus postflop?

There is no clean universal “GTO EV is X% preflop, Y% postflop” decomposition. At equilibrium, EV is a root value, and street attribution depends on the counterfactual baseline.

But for your bot, the answer is obvious from your own X-ray:

| Component | Your measured loss |
|---|---:|
| Preflop non-all-in / preflop strategy | ~−50 bb/100 |
| Deep preflop all-in spew | ~−15 bb/100 |
| Postflop non-jam | ~−10 bb/100 |
| Total | ~−75 bb/100 |

So preflop-related damage is roughly:

\[
-50 + -15 = -65 \text{ bb/100}
\]

Out of ~−75 bb/100 attributed loss:

\[
65 / 75 \approx 87\%
\]

That is the ballgame.

### Would nailing preflop Nash get you most of the way to GTO Wizard parity?

Yes, based on your data.

If you replace your current preflop with a strong HU 200bb blueprint and kill the all-in spew, the optimistic recoverable amount is roughly:

\[
50 + 15 = 65 \text{ bb/100}
\]

Realistically, it may not be perfectly additive because:

- postflop ranges will change,
- your postflop net may behave differently in new nodes,
- attribution can move between buckets,
- GTO Wizard’s exact sizes/strategy may differ from your abstraction,
- sample n=2500, even AIVAT, is not infinite.

But the priority is still clear. A reasonable expectation is that a good preflop fix recovers **most of the current gap**, maybe something like **40–65 bb/100**, leaving you perhaps in the −10 to −30 bb/100 zone depending on postflop robustness and abstraction quality.

That is not a promise. But it is the correct engineering bet.

---

## Brutal practical diagnosis

Your current strategy is likely losing because of three preflop problems:

1. **SB strategy is not a real HU strategy.**  
   Top-84% to 2.5bb ignores limps, mixed opens, playability, blocker structure, and size dependence.

2. **BB defense/3bet/4bet ranges are crude.**  
   HU preflop EV is extremely sensitive to defend frequencies and range construction.

3. **200bb all-in logic is probably catastrophically loose.**  
   At 200bb, QQ/AK/JJ/AQ-type hands are not automatic stack-offs. A few wrong stack-offs can create the entire −15 bb/100 all-in term.

---

## What I would do next

1. **Stop training fcpa preflop for 200bb.**  
   It is the wrong game.

2. **Implement a real preflop size abstraction.**  
   At minimum: limp, 2.5bb open, realistic 3bet, realistic 4bet, non-all-in 5bet, jam only late.

3. **Hard-gate 200bb preflop all-ins.**  
   Temporary rule: call full-stack jams with AA; KK only in approved nodes; fold QQ/AK to full 200bb jams unless pot odds are much better.

4. **Train or import a preflop blueprint separately.**  
   Do not wait for end-to-end self-play to rediscover HU 200bb preflop from a broken size menu.

5. **Evaluate by EV/AIVAT, not frequency matching.**  
   Your paired-oracle result already proved frequency match can be EV trash.

Final answer: **HU 200bb preflop is approximately solvable and should be treated as your first-order problem. GTO Wizard is close enough that your crude preflop is getting annihilated. Fixing preflop plus all-in discipline is the highest-ROI path and likely recovers most of the −72 bb/100 gap.**
