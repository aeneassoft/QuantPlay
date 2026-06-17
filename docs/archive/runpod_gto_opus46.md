# Closing the GTO gap — poker insight (claude-opus-4-6)

[model=claude-opus-4-6]

# Poker-Strategy Analysis: Closing the Gap from -33 to -3 bb/100

## 1. Where a Frequency-Matching-but-Context-Blind Bot Bleeds EV (Ranked)

The key insight: matching *marginal* frequencies (e.g., "bet 67% on Kh7d2s flop") while collapsing across info-sets means you bet the **right amount but with the wrong hands**. A GTO opponent extracts value from every hand you misassign to the wrong action.

### Rank by EV impact in 200bb HUNL:

**#1: River decisions facing bets/raises (~8-12 bb/100 of your leak)**
This is where the money is. At 200bb, river pots are large (often 30-80bb+, sometimes 200bb+), and the correct action is *extremely* hand-specific. A context-blind bot that knows "defend 60% vs 75% pot bet" but doesn't know *which* 60% is catastrophic here. Specific failures:
- **Bluff-catching with wrong combos.** Calling with Kx on K♠7♦2♣4♥T♣ when you should call A7 (blocks nothing) and fold KJ (blocks opponent's value-bet folds). Blockers swing river call EVs by 20-40bb per hand when pots are large.
- **Over-folding vs overbets, under-folding vs small bets.** GTO Wizard AI uses varied river sizings. Facing a 150% pot overbet, you need to defend ~40%. Facing 33% pot, you defend ~71%. A bot averaging to "defend 58%" gets crushed in both spots.
- **Missing thin value bets / calling too many medium-strength hands instead of betting them.** On the river, the difference between betting QQ for thin value and checking to bluff-catch is often 3-5bb in EV, and the correct action depends on the *exact line taken*.

**#2: Turn barreling/checking decisions (~6-10 bb/100)**
The turn is where range construction diverges most from marginal frequencies. Key failures:
- **Barreling the wrong draws.** A context-blind bot fires turn with the "right frequency" but picks draws randomly. GTO barrels draws that have good blockers to opponent's continuing range and unblock folds. E.g., on K♠7♦2♣ ... 5♠ turn, GTO barrels A♠4♠ (nut flush draw, blocks Ax that continues) but checks J♠9♠ (flush draw that doesn't block folds and has some showdown). Your bot treats these identically.
- **Check-raise construction on turn.** After checking, facing a bet, the turn check-raise range is *tiny and precise* — typically nut draws + sets/two-pair that need protection. Getting this wrong (either never check-raising, or check-raising with the wrong hands) creates massive range imbalances that a near-GTO opponent punishes on the river.
- **Delayed c-bets / check-call-then-lead lines.** One of the most commonly botched spots. After IP checks back flop, OOP needs to lead ("donk") turn on specific runouts (cards that help OOP's range more). A context-blind bot almost certainly misses these entirely.

**#3: Facing-bet defense with correct range composition (~4-7 bb/100)**
Not just *how often* you defend, but *what you defend with*:
- **Folding hands that should raise, calling hands that should fold.** Example: facing a flop c-bet on A♠8♦3♣, you should check-raise A3s (bottom two, needs protection) and fold 65s (no equity), but a context-blind bot might call both because they're both in the "marginal" bucket.
- **Facing multi-street barrels.** After calling flop and turn, your river range should be properly constructed. A context-blind bot that calls flop with a diffuse range arrives at the river with too many hands that can't beat anything and too few nutted hands, making river decisions impossible to get right.

**#4: Sizing selection (~3-5 bb/100)**
At 200bb, sizing precision matters enormously:
- **Flop c-bet sizing by board texture.** On A♠K♦7♣ (dry, static), GTO c-bets 25-33% pot with high frequency. On J♠T♦8♣ (wet, connected), GTO c-bets larger (67-75%) with lower frequency, or checks range frequently. A bot that picks "55% pot always" leaves 2-3bb/100 on the table just on the flop.
- **Overbets.** At 200bb deep, overbetting is a core GTO tool on turn and river, not a novelty. On turn cards that improve your range (e.g., you c-bet A♠K♦7♣, turn K♠ — now you have all KK/AK and opponent doesn't), GTO overbets 125-200% pot. Missing this entirely costs you the ability to play your strongest hands profitably.
- **Small river bets.** GTO uses 25-33% river bets with merged ranges (thin value + blockers) far more than bots realize. This extracts from hands that fold to larger bets.

**#5: Check-raising ranges (flop and turn) (~2-4 bb/100)**
Check-raising is the main OOP counter-strategy. Context-blind construction errors:
- **Flop check-raise range too wide or too narrow.** On 7♠5♦3♣, OOP check-raises sets, two-pair, and straight draws (86s, 64s) plus some overcards (AK with backdoors). Getting the semi-bluff component wrong means your check-raise range is either too nutted (exploitable by folding) or too draw-heavy (exploitable by 3-betting).
- **Not check-raising enough on dynamic boards.** On T♠9♦7♣, check-raise frequency should be higher (~12-15%) because many draws need protection and you need to build pots with strong hands before scare cards arrive.

**#6: Polarization vs. merged ranges (~2-3 bb/100)**
- When IP with a range advantage on the river, GTO often uses a **merged** betting range (bet all value + give up bluffs). When OOP or with a polarized range, GTO uses **large sizings with polar ranges**. A bot that averages into a single strategy for all positions mishandles this.

**#7: Range protection / checking strong hands (~1-3 bb/100)**
- On flop, GTO checks back overpairs (AA on low boards) at non-trivial frequencies to protect checking range. If your bot never checks strong hands (because averaging says "always bet QQ+ on 7♠5♦3♣"), opponent can hammer your checks with impunity.

---

## 2. Priority Spots for Real-Time Re-Solving (Poker Reasoning)

Given your river resolver is built and turn resolver is next, here's the priority ordering with poker justification:

### Tier 1 (implement now, biggest bang):

**A. All river decisions, especially facing bets ≥50% pot**
- Poker reason: These are the largest pots, most hand-specific decisions, and where context-collapse is most punishing. A correct river solution tells you *exactly* which hands to call, fold, and raise based on blockers, the specific runout, and the line taken.
- Specifics: Prioritize spots where effective pot is >30bb (which at 200bb is most rivers that see significant action). Your river resolver should be invoked for *every* river decision if latency allows.
- Expected recovery: 5-8 bb/100.

**B. River bet sizing when you're the bettor**
- Poker reason: Choosing between 33%, 67%, 100%, and 150% pot on the river is one of the highest-EV decisions, and it's *entirely* hand-dependent. With AA on a bricked-out board, you want small (merged). With the nuts + air, you want large (polar).
- Your solver should be queried for optimal sizing, not just action.

**C. Facing overbets (turn and river)**
- Poker reason: GTO Wizard AI *will* overbet. The correct defense vs a 150% overbet is ~40%, using hands with best blockers. A context-blind bot almost certainly over-folds or over-calls here by 10-15%, which at these pot sizes is worth 3-5 bb/100 alone.

### Tier 2 (implement next, high EV):

**D. Turn barrel/check decisions (requires turn resolver)**
- Poker reason: The turn is where the "tree branches" most. After checking flop or betting flop, the turn card changes equity distributions dramatically. A single turn card can shift the range advantage from one player to the other (e.g., flush completing, pair on board).
- Priority sub-spots: (i) Turns after flop check-through (both players have wide ranges, turn decisions heavily card-dependent), (ii) Turns after flop bet-call (ranges are narrower but still diverge significantly by turn card).

**E. OOP turn and river leads ("donk bets")**
- Poker reason: After IP checks back flop, OOP should lead turn on specific cards at specific frequencies. This is one of the most neglected spots in bot-building. Example: flop K♠8♦3♣ checks through; turn 2♠ (puts flush draw on board). OOP should lead ~25-35% with a range of flush draws, slow-played top pairs, and some random equity. If your bot never leads, opponent gets a free card with their entire range.

### Tier 3 (implement after, meaningful):

**F. Flop check-raise ranges (OOP vs c-bet)**
- Important for range construction, but less EV per decision than turn/river because pots are smaller. However, getting flop check-raises right cascades into better turn/river play.

**G. 3-bet/4-bet pot flop play**
- In 3-bet/4-bet pots at 200bb, stacks are often 60-100bb and the flop decision is effectively a turn/river decision in terms of commitment. Re-solving these high-SPR postflop trees pays off disproportionately.

---

## 3. Balance / Mixing / Range-Construction Principles

These are the concrete principles your bot must implement to stop being exploitable:

### River bluff-to-value ratios
The math is simple but the implementation is hand-specific:
- **Pot-sized bet (1x pot):** Opponent must call 33% of range. You need bluffs = value × (sizing / (sizing + pot)). For 1x pot: 1/(1+1) = 50% bluffs, 50% value. So bet 1 bluff combo for every 1 value combo.
- **1/3 pot:** ~20% bluffs. So 1 bluff for every 4 value bets.
- **2x pot overbet:** ~60% bluffs. 1.5 bluffs per value bet.
- **Critical:** your bluffs must be selected by *best blockers to opponent's calling range*. On K♠8♦3♣5♥T♣, the best river bluff is A♠X♠ (missed nut flush draw, blocks AT/AK that call). The worst bluff is 76o (blocks nothing).

### Turn barrel ranges
- **Continue barreling** with: (i) hands that improved (made straights, flushes, two-pair), (ii) draws that gained equity or have good blockers, (iii) value hands that need protection (overpairs on dynamic boards).
- **Check** with: (i) showdown value (middle pair), (ii) draws without blockers, (iii) some strong hands (for check-raise or to protect checking range).
- **Concrete example:** Flop K♠7♦2♣, you c-bet, called. Turn J♠. Barrel: KK, K7s, AK, KQ (value); A♠X♠, Q♠T♠ (good flush draws with overcards); A♠5♠ (nut flush draw, blocks AK). Check: QQ, TT (showdown, don't want to face raise); 9♠8♠ (draw without blockers); some AK (protect checks).

### C-bet sizing by board texture
This is where your flop blueprint should hard-code texture-dependent sizing (not averaged):

| Board Texture | Example | Recommended Size | Frequency |
|---|---|---|---|
| Dry high-card | A♠K♦7♣ | 25-33% pot | 75-90% |
| Dry low | 7♠5♦2♣ | 25-33% pot | 55-70% |
| Monotone | J♠8♠3♠ | Check heavy | 25-35% bet large |
| Wet connected | J♠T♦8♣ | 50-75% pot | 35-50% |
| Paired | K♠K♦7♣ | 25-33% pot | 80-90% |
| Two-tone medium | 9♠7♦5♣ | 33% pot or check | 45-60% |

If your bot uses one sizing across all textures, switch to at least 2 (small / large) keyed on board wetness.

### Defending vs overbets
- **Vs 150% pot overbet:** MDF = 1/(1+1.5) = 40%. But you should slightly over-fold if opponent is balanced (they have more bluffs at this sizing).
- **What to defend with:** Only hands that beat value hands in opponent's range, weighted by blockers. On K♠8♦3♣5♥T♣ facing river overbet, defend: KT+, sets, straights, flushes. Fold: K8, K5 (second pair + kicker). Key: K♠X should fold more often (blocks opponent's missed flush bluffs).
- **Never defend with hands that only beat bluffs if they also block opponent's value.** This is the most common error.

### Check-raising construction
- **Flop OOP vs c-bet:** Check-raise ~10-12% overall. Range should be: ~40% strong made hands (sets, two-pair), ~60% semi-bluffs (straight draws, flush draws with overcards). On J♠T♦8♣: check-raise QJ, JT, 88, TT (value) + 97s, Q9s, A♠X♠ (draws).
- **Critical balance point:** If you only check-raise made hands, opponent folds all their air to raises and you gain nothing. If you only check-raise draws, opponent calls/re-raises and you're dominated. The 40/60 split is what makes the range unexploitable.

---

## 4. Specific High-EV HUNL Spots to Hard-Check Your Bot Against

These are concrete spots where bots commonly bleed and GTO Wizard AI will punish you. Test these explicitly:

### Spot 1: River facing 150% pot overbet on bricked board
Setup: SB opens, BB calls. Flop Q♠8♦3♣ (SB bets 33%, BB calls). Turn 5♥ (SB bets 67%, BB calls). River 2♦ (SB overbets 150% pot).
- **Test:** Does your bot fold KQ here? It should fold ~50% of KQ combos (keeping only those without spade blockers). Does it call Q8? It should always call. Does it call 88? Always. Does it fold A8? Yes, usually.
- **Red flag:** If your bot calls/folds at close to the right *frequency* but with the wrong *hands*, that's the context-collapse problem in action.

### Spot 2: Turn donk bet after IP checks back flop
Setup: SB opens, BB calls. Flop J♠7♦4♣ (SB checks). Turn 2♠ (BB should lead ~30%).
- **Test:** Does your bot ever lead? With what? It should lead with flush draws (X♠Y♠), slow-played J7, 44, and some A-high floats.
- **Red flag:** If your bot checks 100% after opponent checks, it's leaving significant EV on the table.

### Spot 3: 3-bet pot, monotone flop
Setup: BB 3-bets, SB calls. Flop T♠7♠3♠.
- **Test:** BB should check ~70% of range here (range disadvantage on monotone despite being 3-bettor). Does your bot c-bet at high frequency? Red flag.
- **Test 2:** When BB checks and SB bets 33%, does BB check-raise with nut flush + some combo draws? Does BB fold low flush draws (like 5♠4♠)?

### Spot 4: River thin value vs. check-back
Setup: SB opens, BB calls. Flop K♠8♦3♣ (bet/call), Turn 5♥ (check/check), River 2♦. BB has K9.
- **Test:** This is a thin value bet for ~33% pot. Does your bot bet or check? Checking is a significant EV loss (you miss value from Ax, pocket pairs 44-77 that call small).
- **Red flag:** If your bot checks all Kx and only bets two-pair+, it's massively under-betting river.

### Spot 5: SB preflop open-raise sizing and range
- At 200bb, SB should open to 2.5-3x with a range of ~70-85% of hands (not 52% as in tournament play).
- **Test:** Does your bot open 72o from SB? It should (at some frequency). Does it open to the right size?
- **Red flag:** If preflop ranges are significantly off, all postflop play is built on a bad foundation.

### Spot 6: Responding to small river bets (25-33% pot)
- **Test:** Facing a 25% pot river bet, your bot should defend ~71% of range. But more importantly, it should *raise* some strong hands (nuts + bluffs with blockers) at ~5-8% frequency.
- **Red flag:** If your bot only calls or folds (never raises vs small bets), it's exploitable because opponent can small-bet their merged range risk-free.

### Spot 7: 4-bet pot AA on low flop
Setup: SB opens, BB 3-bets, SB 4-bets, BB calls. Flop 7♠5♦3♣. BB has AA.
- **Test:** SB should c-bet small (~25-33%) at very high frequency. BB with AA should call (not raise) almost always. Raising announces your hand and folds out everything you beat.
- **Red flag:** If your bot check-raises AA here, it's a clear exploitability.

---

## Implementation Recommendations (Prioritized for $140 RunPod Budget)

Given your architecture (supervised blueprint + real-time resolving + range tracker):

1. **Make the river resolver the default for ALL river decisions.** If it runs in <2s, use it every time. This is your single biggest EV improvement. Expected gain: 5-8 bb/100.

2. **Add the turn resolver with priority on these sub-trees:** (a) facing bets after check-through, (b) turn card significantly changes texture (flush completes, straight completes, pairs board), (c) pots >30bb. Expected gain: 3-5 bb/100.

3. **Use the $140 on mass-solving turn/river sub-games to build a CFV value net.** Specifically, solve ~50K-100K distinct turn spots (varying board textures × stack depths × bet histories) and train a value network on the resulting continuation values. This lets you re-solve turns with terminal values from the net rather than rolling out to river, which is both faster and more accurate than your current flop-only blueprint.

4. **Implement blocker-aware hand ordering for all defense decisions.** Even without full re-solving, adding a blocker heuristic (prefer hands that block opponent's value, unblock opponent's bluffs) to your existing frequency-matching framework is a quick 1-2 bb/100.

5. **Add OOP leading (donk betting) to your action space if it's currently absent.** Even heuristic donking on favorable turn cards (cards that hit BB's range harder) prevents a systematic leak.

6. **Implement at least 3 bet sizings (33%, 67%, 125%+overbet) rather than 1-2.** The sizing decision is often as important as the bet/check decision. Keying the sizing to a simple board-texture classifier (dry → small, wet → large, advantaged turn → overbet) is a major improvement over a single sizing.

The path from -33 to -10 is mostly the river resolver + blocker-aware hand selection. The path from -10 to -3 requires the turn resolver, the value net, and precise range tracking so your resolves start from accurate range inputs rather than generic ones. The range tracker accuracy is the lynchpin: a river solver given wrong input ranges will produce wrong output strategies.
