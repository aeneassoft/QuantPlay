# SNOWIE BLUNDER ANALYSIS — all 39 blunders of AUSLESE v1, clicked through one by one
(2026-08-17; source: PokerSnowie 4, 400 exported hands, gate parity without resolver)

## The finding in one sentence
**The largest blunder class is exactly the mechanism that gave AUSLESE v1 its +6.1 bb/100:
call-downs that are too loose (15 of 39 = 38%).** Snowie thus sees the same thing as our
GTO-balance evaluation (call flop 195% of the recommendation) -- the direction was right, the DOSE
is too high, and the overdose concentrates in MULTI-STREET calls.

## The four error classes

| Class | Count | Pattern |
|---|---|---|
| **C — call-downs too loose** (Snowie: FOLD) | **15** | call flop -> call turn -> call river with one pair, a board pair or A-high |
| **B — missed value / too passive** (Snowie: BET/RAISE) | 11 | turn check with overpair/trips, river check with two pair, missed flop raises |
| **A — over-aggression with strong hands** (Snowie: CHECK/CALL) | 9 | bet/raise instead of trapping with flush/trips/top-two; thin value bets that get raised |
| **D — folds too tight** (Snowie: CALL) | 3 | fold with an open-ender / two pair on the river |

## The individual cases as evidence (selection, with Snowie's EV)

**C — call-downs (the most expensive):**
- K5o on 7♣J♥7♥8♦6♥: call flop+turn+river $15.56 with a board pair. FOLD 100%, call **−7.10 EV**
- A♥2♥ on 9♦A♣Q♠4♣8♣: river call $33.20 against a raise with top pair weak kicker. FOLD 100%, call **−15.02 EV**
- T♥3♣ on Q♣Q♦T♦4♦A♥: river call $33.20 against a raise. FOLD 100%, call **−10.12 EV**
- 6♦Q♦ on 5♥6♥K♠2♥9♥ (4 hearts): call-down with second pair. FOLD 84%, call **−6.92 EV**
- Several won hands are nevertheless blunders (Q♦7♣, T♦2♠) — Snowie grades the PROCESS,
  not the result. That is methodically exactly right and matches our doctrine.

**B — missed value (the biggest gaps):**
- Q♣Q♠ on 9♣8♥4♦A♦3♥: turn check AND river check with an overpair. BET 100% (**26.73** and **35.42 EV**)
- 4♦6♦ on 4♠3♠8♣T♦4♣ (trips): river check. BET 100% (**19.17** vs 15.90 EV)
- A♦Q♠ on Q♣9♠T♥A♣K♣ (two pair): river check. BET 100% (**25.55** vs 18.88 EV)
- 9♣8♦ on 2♣5♣J♣7♠Q♥: river check with high card — Snowie wants to BLUFF here. BET 100%

**A — over-aggression with monsters:**
- K♠9♠ on 5♠2♠A♠ (flopped flush): bet $2.50. CHECK 100% (**13.49** vs 11.36 EV) — trap missed
- J♥8♦ on K♣Q♥J♦J♠ (trips): raise $27.50. CALL 100% (**8.80** vs 5.42 EV)
- A♠K♣ on A♦K♥6♦3♦8♠ (top two): river bet $50. CHECK 100% (**63.62** vs 44.79 EV)

## The three derived candidates (round 4, each through its own gate)

1. **MARGIN SWEEP (highest priority).** sel_guard uses +3pp over the pot odds. Snowie says:
   too loose. Sweep +8pp / +12pp / +15pp against AUSLESE v1 — expectation: the optimum lies
   between the base (53% call frequency) and v1 (195%).
2. **MULTI-STREET DISCIPLINE.** Almost all C blunders are call chains: the guard turns the
   flop fold into a call, after which the bot keeps calling turn AND river. Candidate: the guard may
   rescue the hand only ONCE; on later streets the base decision applies (or a
   tightened threshold). That also explains why sel_all (all streets) brought nothing.
3. **TURN VALUE BETS.** Class B piles up on the turn with strong hands — the oldest
   documented postflop leak of the repo, now confirmed by a third system.
   Candidate: value-bet guard on the turn (bet when equity vs tracker range is high AND it was checked).

## Honesty note
Snowie's net is a third, independent opinion — not truth. It approximates its
OWN equilibrium, and the GTO-balance view is explicitly beta. What CARRIES: the
agreement of three independent instruments (our MDF oracle, our paired gate,
Snowie's blunder list) that the call frequency on the flop is the central lever — and that
we now stand on the OTHER side of the optimum. No candidate is shipped without our own
paired gate; Snowie supplies hypotheses, not verdicts.

## ADDENDUM (user objection, 2026-08-17): EV reconstruction + the outdated referee

**1. Snowie's EVs are reconstructible** -- from every graded call follows its implied
opponent equity: eq_snowie = (EV_call + b) / (P + 2b). Example A2s river call $33.20:
EV −15.02 -> eq_snowie ~13% vs our tracker range (>= pot odds ~31%). The difference per
spot = the quantified disagreement of two RANGE MODELS, tabulable for all 39.

**2. The referee is outdated AND grades against the wrong opponent.** Snowie
assumes its own balanced villain range; the hands were played against OUR base bot.
Repo history: engine vs Snowie ~break-even (adjusted +3.2), vs GTOW −19.7 -> Snowie is the
weaker referee. Its blunder list is a source of hypotheses, never a gate (the doctrine
'frequency-matching to foreign referees costs' applies to Snowie too).

**3. The question back to US: does +6.1 transfer at all?** Our gate measures vs our own
bot. If the call-downs live off its over-bluffing, part of the gain is self-play
exploitation (tipping risk #3). TRANSFER TEST (started): sel_guard bot and base bot each
paired against the FOREIGN opponent GTOBaseline on the same decks; the difference of the two
edges shows how much of the selection remains against an opponent whose leaks it has never
seen.
