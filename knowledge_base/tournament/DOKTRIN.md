# TOURNAMENT DOCTRINE — distilled from the two books (2026-08-04)

> Sources: Sklansky, *Tournament Poker for Advanced Players* (3rd ed.) + O'Kearney/Carter,
> *Endgame Poker Strategy: The ICM Book*. Systematic extraction (4 readers, workflow
> `tournament-recon`); summaries in our own words, formulas exact.
> Implemented in `pokerbot/strategy/icm.py` (mathematics) + `pokerbot/strategy/tournament.py`
> (doctrine) + `pokerbot/arena/tourney.py` (arena). Tests: `tests/test_icm.py`, `tests/test_tournament.py`.

## The 10 points

1. **$EV instead of cEV — from hand 1.** Malmuth-Harville: `P_i(1.) = c_i/C`;
   `P_i(2.) = Σ_{j≠i} P_j(1.) · c_i/(C−c_j)` recursively; `$EV_i = Σ_k P_i(k)·Payout_k`.
   Chips are concave in money (leader double-ups: +$8.44 → +$7.06 → +$5.83).

2. **Bubble factor as the universal call threshold.** `BF = |ΔEq_lose| / ΔEq_win` (≥1 everywhere
   except HU); `required_equity = BF/(BF+1)` for a flip, in general `r' = BF·r/(BF·r + (1−r))`.
   Anchors: BF 1.18→54 %, 1.67→63 %, 2.56→72 %, 3.98→80 % (only AA left). Every player in the same
   hand has a DIFFERENT BF.

3. **Pairing matrix (heuristic without exact computation).** Big-vs-big 2.5–4.0 (QQ+; AK is a fold);
   medium-vs-medium/big 1.9–3.0; short-vs-anything 1.2–1.7; cover stack-vs-short 1.0–1.1 (≈ pot odds).
   A micro stack at the table raises the BFs of ALL others against each other (do not eliminate it at any price).
   Monster stack: the leader plays ≈ chip EV, everyone else ladders ("playing for the win" = fallacy).

4. **Payout-structure effect (counterintuitive).** Top-heavy → BFs fall toward chip EV
   (winner-take-all = no ICM); flat/satellite → BFs explode AND fold equity becomes the
   most important form of equity. "Small pay jump → gamble" is exactly inverted, i.e. wrong.

5. **Survival premium (Sklansky's sequence bet).** Declining a marginally +EV spot is correct when the loss
   blocks better later spots (bankroll-100 example: take the flip EV +35, pass +50).
   Practical cushion: decline 4.3:1 at 4:1.

6. **Gap concept + aggressor bias.** Calling range ≪ opening range; gap width ∝ field tightness.
   Aggression (shove/raise with fold equity) is systematically better than calling under ICM →
   **cut calling ranges harder than open/shove ranges** (wired that way: the ICM surcharge sits
   only on `req`, never on the open fractions). `Shove-EV = F·Pot + (1−F)·[W·(Pot+Bet) − (1−W)·Bet]`.

7. **Phase curve.** BF ~1.0–1.2 early → ~1.6 at the money bubble → falls in the money → ~1.7 at the
   final-table bubble (the tournament's ICM maximum) → drops per FT payout → **exactly 1.0 heads-up**
   (which is why the Prince v2.2 core plays the HU endgame UNCHANGED — anchor protection and doctrine
   coincide).

8. **Short stack: TIGHTER, do not gamble.** Chips per unit are worth ~4× more than for the leader.
   No bleeding with speculative hands (67s call at 10bb ≈ 20 % equity loss); drop pairs <66 near the
   money; upgrade blockers (A2s > 22); steal target = the next-shortest stack. Being all-in
   is +EV (guaranteed realisation + dead money) — do not loosen up to avoid it.

9. **Big stack: constant aggression on covered mediums** (their BF against you is maximal), actively
   prolong the bubble, do NOT call light yourself, avoid big-vs-big. Slowplay ban: sacrificing ~2 EV points
   for −15 pp probability of loss is almost always right in a tournament.

10. **Error weighting: late errors ≈ 100× early errors** (5bb at a 100bb start ≈ 0.05 buy-ins;
    1bb at a 20bb average late ≈ 5 buy-ins). Concentrate the eval budget on ≤40bb + ICM; hard-wire the
    all-in call gate (exact three-worlds computation `icm_call_threshold`); ladder value always as a delta
    to the current ICM equity.

## Wiring map (where the doctrine sits in the code)

| Doctrine | Code |
|---|---|
| BF scaling of the call threshold | `tournament.icm_required_equity` → 2 hooks in `sixmax._decide` (`req`) |
| Exact all-in call | `icm.icm_call_threshold` via `tournament.icm_scaled_req` (to_call ≥ stack) |
| Aggressor/cover-stack counterpart | `tournament.pick_villain` |
| HU = BF 1 → Prince unchanged | no hook in `bot.py` (deliberate) |
| Structure/elimination/ladder | `tournament.Director` (+ `Table(stacks=, ante=, rebuy=False)`) |
| Paired $ROI measurement | `pokerbot/arena/tourney.py::run_batch` |
| Payout-sensitivity touchstone | structures `FLAT9` (BFs must rise) vs `TOP_HEAVY9` (fall) |
