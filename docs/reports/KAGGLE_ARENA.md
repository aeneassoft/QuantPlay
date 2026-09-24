# Kaggle Game Arena — "Heads Up Poker" as a measurement channel (2026-09-10)

Leaderboard: <https://www.kaggle.com/benchmarks/kaggle/poker-heads-up> · Bridge:
[`pokerbot/benchmark/kaggle_arena.py`](../../pokerbot/benchmark/kaggle_arena.py) · Tests: `python -m tests.test_kaggle_arena`

## What this is

Kaggle Game Arena lets **frontier LLMs** play Heads-Up No-Limit Hold'em against each other and scores them
by **Mean BB/100** (all-play-all within the LLM field, no solver opponent). That is why the numbers — unlike
on the GTOW leaderboard, where everyone is negative — are mostly POSITIVE: they measure relative to the field,
not against GTO.

**Leaderboard v1 (retrieved 2026-09-10 via the Kaggle API, Mean BB/100):**

| Rank | Model | BB/100 | | Rank | Model | BB/100 |
|---|---|---|---|---|---|---|
| 1 | GPT-5.6 Sol | +34.9 ± 5.1 | | 15 | GPT-5.4 mini | −0.4 |
| 2 | GPT-5.5 | +32.5 ± 6.0 | | 19 | Claude Opus 4.8 | −3.4 |
| 3 | Claude Fable 5.1 | +29.7 ± 6.0 | | 23 | DeepSeek V3.2 | −11.8 |
| 4 | Claude Opus 5 | +15.8 ± 5.9 | | 26 | Claude Sonnet 4.6 | −17.3 |
| 5 | GPT-5.6 Terra | +11.6 ± 5.5 | | 29 | GPT-5 mini | −49.3 |

Cost of the top places: 12,000–19,000 tokens per move, up to 26 ct/move — one reason an engine bot would be
structurally advantaged here (our decision costs 0 ct and ~0.1–0.3 s).

## The game configuration (exact, read from the environment itself)

```
python_repeated_pokerkit(max_num_hands=100, reset_stacks=True, rotate_dealer=True,
  pokerkit_game_params=python_pokerkit_wrapper(blinds=1 2, num_players=2,
                                               stack_sizes=200 200, variant=NoLimitTexasHoldem))
```

* HUNL, blinds 1/2 units, stacks 200 units = **100 bb**. The test `test_spielkonfiguration` pins
  the value.
* **CORRECTION (2026-09-10, finding by gpt-5.6-sol, confirmed in the code): 100 bb is NOT our competition depth.**
  The GTOW benchmark runs at **200 bb** (`starting_stack 20000`, blinds [100,50] —
  `pokerbot/benchmark/gtowizard.py:98`, `:281`), and our preflop blueprint only fires **from 140 bb
  effective** (`pokerbot/strategy/bot.py:200`: "blueprint is solved at 200bb -> only fire when genuinely
  deep (GTOW = 200bb)"). At 100 bb, therefore, the **heuristic cascade** plays instead of the near-Nash policy:
  the Kaggle channel measures a DIFFERENT bot than the competition channel. The claim that formerly stood here
  ("exactly our house size") was wrong.
  **Consequence:** `--stack-bb 100` replicates Kaggle, `--stack-bb 200` measures the competition depth. Only the
  second mode is usable as a cheap pre-filter for GTOW candidates; the first serves the Kaggle question.
* Stacks are **reset every hand**, the dealer rotates, a match is **100 hands**.
* Actions: `0` = fold, `1` = check/call, `N` = bet/raise **TO** N units (up to 200 = all-in).

## The bridge

`pokerbot/benchmark/kaggle_arena.py` puts our champion (PRINCE profile, exploit OFF, resolver ON,
AUSLESE chain `FINAL_STACK`) into exactly this game:

* `parse_beobachtung()` reads the wrapper's `observation_string` (street, bets, stacks, board, hole).
* `zustand()` builds our engine state from it (hero always index 0, as in the GTOW adapter), units × 50 = chips.
* `spiel_aktion()` maps `{action, amount}` onto an OpenSpiel action, with a **legality guarantee**.
* `duell()` measures **paired**: every deck twice with swapped seats, verdict via `stats.verdikt`.

**Two measurement traps, both measured and fixed:**

1. **hand_id per half** destroyed the private randomization → the same trap as in v10; now the
   `hand_id` is identical across the whole deck.
2. **RNG stream across hands**: our bot mixes (seesaw doctrine) from a continuous stream. With
   reused agents the mirror halves drifted apart — **A/A was −37.5 bb/100 instead of 0**
   (8 decks). Fix: fresh instances per half → **A/A exactly 0** (`nonzero 0`, SE 0).

## Is this faster than GTOW?

Yes, by orders of magnitude — but it measures something else.

| | GTOW API | Kaggle environment locally |
|---|---|---|
| Cost per hand | hand budget + time window | 0 |
| Throughput | ~2,500 hands in 8–9 h (serial) | ~0.3–18 s/hand depending on resolver, parallelizable across all cores |
| Opponent | ruse re-solver (near GTO) | in the official run: LLMs |
| Usable as GTO anchor | **yes** | **no** |

**Honest assessment:** the environment is a cheap volume channel and a potential showcase, but
no replacement for the GTOW anchor. An LLM field that spreads from +35 to −49 bb/100 among itself says nothing
about how far we are from GTO. Whoever wins here has beaten LLMs, not the solver.

## Open: can we really compete?

The leaderboard rows are Kaggle **models** (`modelVersionSlug`); the field consists exclusively of
the labs' LLMs. Whether Kaggle admits a non-LLM agent to exactly this benchmark leaderboard is NOT
established from the publicly readable pages — the Kaggle pages render via JavaScript and return only the title
over `WebFetch`. The existing KGAT token (`Secret keys\Kaggle API.txt`, read only from the file)
opens the benchmark API for reading; a submit endpoint for agents has not been demonstrated with it.
**Next step for real participation:** read the Game Arena rules/FAQ in the browser (not via fetch)
and check whether there is an agent submission outside the model field.

## Commands

```bash
python -m pokerbot.benchmark.kaggle_arena --aa --decks 8            # null test (must be exactly 0)
python -m pokerbot.benchmark.kaggle_arena --gegner basis --decks 300
python -m tests.test_kaggle_arena
```

Dependencies (new, only for this channel): `pip install open_spiel kaggle-environments` — for Python 3.12
a Windows wheel exists, so the environment runs without WSL.


## Calibration Kaggle -> GTOW (user idea 2026-09-10): WEAK, not usable

Six models appear on BOTH leaderboards. Regression of GTOW AIVAT on Kaggle BB/100:

| Model | Kaggle BB/100 | GTOW bb/100 |
|---|---|---|
| GPT-5.6 Sol | +34.9 | −15.4 |
| GPT-5.5 | +32.5 | −9.2 |
| Grok 4 | +10.5 | −60.0 |
| GPT-5.4 | +3.6 | −17.8 |
| Claude Opus 4.6 | +1.6 | −20.4 |
| Gemini 3.1 Pro | −13.0 | −30.8 |

* **All six: r = 0.37, R² = 0.14, residual SD 15.5 bb/100** — worthless as a conversion.
* Without Grok 4 (residual −34): r = 0.88, R² = 0.77, residual SD 3.4, `GTOW ≈ 0.334 · Kaggle − 22.7`.
  Dropping a point BECAUSE it contradicts is not calibration, though, but curve fitting.
* In addition: the reasoning levels differ (GTOW lists "XHigh Reasoning" variants), so the
  pairings are not even the same configuration; and any prediction beyond +35 Kaggle
  would be extrapolation outside the data range.

**Conclusion: the conversion carries no verdict.** It is not needed either — see below.

## The actual finding: GTOW accepts YOUR OWN agents (and we are already on it)

<https://benchmark.gtowizard.com/> has a button "Evaluate Your Model"; the top consists of
private agents, not LLMs. As of 2026-09-10 (83 entries, rank by the LOWER BOUND of the
95% interval — hands therefore count as much as the mean):

| Rank | Agent | bb/100 | SD | Hands |
|---|---|---|---|---|
| 1 | Bitcrumbs (Individual) | −3.1 | 0.9 | 52,005 |
| 2 | Trainer (SL) | −6.2 | 0.7 | 102,251 |
| 3 | Roman_SL (Individual) | −7.4 | 0.6 | 137,576 |
| 4 | tangtang's agent | −12.6 | 0.5 | 269,559 |
| 5 | GPT-5.5 (XHigh) | −9.2 | 2.8 | 5,000 |
| … | | | | |
| 31 | **Quantplay (Hampe)** | **−30.4** | 3.5 | 6,587 |
| 33 | **Quantplay v8 (Hampe)** | **−31.6** | 3.5 | 6,946 |
| 47 | **Experimental Poker Bot (Hampe)** | **−51.7** | 2.1 | 30,596 |

Our three entries date from the v8 era; today's champion (~−21 measured, night 2) has NEVER
been posted. **Top 5 concretely means: lower bound better than ≈ −14.8** (place 5), i.e. a mean of
≈ −11 at ~10,000 hands or ≈ −13 at ~50,000 hands. Compared to today's state, ~8 bb/100 are missing.


## ⚠ INVALID: the first reference value and the v9 run (finding 2026-09-10, 02:40)

**Both measurements below ran WITHOUT the deal marker in the adapter and are therefore void.**
`improver._river_spot_und_frage` (`pokerbot/autogym/improver.py:421-433`) is the shared foundation
of ALL river GPU guards and returns `None` if the history contains no row `action=='deal' &
street=='river'`. The Kaggle adapter did not write this marker until commit `d22d400` (01:59).

Affected is not only the candidate but **the champion itself**: `river_gpu_guard` is part of
`r8_stack` (`pargate.py:134`). In all runs before 01:59 the champion's GPU surgery could therefore
not fire at all — what was measured was a champion without one of its own components.

| Run | End | valid? |
|---|---|---|
| Champion vs basis, 300 decks (+55.8 ± 38.0) | 01:06 | **NO** (before the marker) |
| v9 `r10_ernte` vs champion, 600 decks (exactly 0.0) | 02:37 | **NO** (run started before the marker) |
| v10-H0 vs champion, 150 decks | running since 02:27 | yes (started after the marker) |

The v9 run over 600 paired decks (1,200 hands, 6,913 s) showed 0 diverging decks. That is **no
verdict on v9**, but the consequence of the same missing marker: `river_play_guard` hangs on exactly
the same foundation. Both measurements will be repeated.

## First reference value in the Kaggle channel (2026-09-10) — VOID, see above

**Champion (`prince[final]`, r8_stack) vs bare basis (`prince[basis]`), 300 paired decks:**

| Quantity | Value |
|---|---|
| raw mean | **+55.8 bb/100** |
| SE | 38.0 |
| 5% trimmed | +6.3 |
| median | 0.0 |
| share of decks with a difference | 32.3% (97/300) |
| of which positive | 45/97 (sign z −0.71) |
| bootstrap CI 95% | [−16.7, +134.6] |
| perm_p | 0.076 |
| **Verdict (stats.verdikt)** | **NEUTRAL** |
| runtime | 3,153 s (~10.5 s/deck, 1 core) |

**What this means — the calibration of the channel, not a bot verdict:**

* The mean is carried by a few large decks (raw +55.8 against trimmed +6.3, median 0). The
  sign test even tips slightly negative. **It is NO evidence that the AUSLESE chain wins
  here** — only that the wiring plays and the channel runs.
* **Noise level:** SE 38 bb/100 at 300 decks. For SE ≈ 4 one would need about **27,000 decks**, i.e.
  ~75 h on one core or ~10 h on 8 cores. That is the honest price list of this channel.
* The channel is a **mirror** (our bot against our bot) and thus the same non-regression
  bound as the gym — with the sole difference that the game rules are exactly Kaggle's.
  The value of the channel lies in the Kaggle ECOLOGY (LLM opponents), not in the mirror.

**Consequence for v9 (`r10_ernte`):** the v9 guard fires rarely (documented ~1 trigger/400 hands in
self-play); in the smoke over 2 decks the difference was exactly 0 with 0 diverging decks. A silent candidate
in a channel with SE 38 delivers **no verdict** in reasonable time. The run runs anyway, because the
interesting number is the SHARE of diverging decks — it decides whether this channel is usable for v9
at all.


## AIVAT for this channel? — draft available: [`AIVAT_KAGGLE.md`](AIVAT_KAGGLE.md)

Short version of the cross-checked result (three independent refutation attempts):

* **The chance-node term is clean here** — and for a stronger reason than expected: the card stream
  has its OWN, hand-local RNG (`kaggle_arena.py`, `random.Random(deck_seed)`); the bot mixes from
  a separate stream. No action shifts the card stream, so the correction is POINTWISE
  unbiased, not just on average.
* **The action term is dead.** Our bot is DETERMINISTIC in the channel conditional on the deck (fixed seed,
  fresh instances per half, `neue_hand` is a no-op because `PokerBot` has no `new_hand`). Thus the
  only admissible "policy" is a point mass and the correction term is identically zero — or biased.
* **The "10x" reduction from the GTOW channel is NOT transferable.** All three attacks called this the
  strongest point of the draft: the paired mirroring has already erased the card variance.
* **The correction belongs at DECK level, never per half.** Per half it can massively INCREASE the variance
  (worked case: factor ~1045 when one arm ends all-in and the other at showdown).
* **Cost of exact enumeration** (re-measured): river 1.3 ms, turn 18.5 ms, flop 285 ms, preflop ~31 s
  -> preflop-exact is unaffordable, only budget truncation there.
* **Precondition G0:** the reference numbers (300 decks) date from BEFORE the deal marker in the adapter; they must
  be re-collected before anything is built.


## v10-H0 in the Kaggle channel — first VALID candidate run (2026-09-10)

`r10_h0` (river plan on the COMPLETE v5 chain) vs champion `r8_stack`, 150 paired decks = 300 hands,
after the deal-marker fix, hence valid:

| Quantity | Value |
|---|---|
| bb/100 | **−0.67 ± 2.46** |
| bootstrap CI 95% | [−5.33, +4.33] |
| perm_p | 0.749 |
| diverging decks | **3 of 150 (2.0%)** |
| **Verdict** | **NEUTRAL** |

**The plan protocol is the actual yield of this run:**

| Plan event | Count |
|---|---|
| activations | 23 |
| plan actually PLAYED | **8** |
| fallback `fehler` | **10** |
| fallback `offtree` | 3 |
| fallback `hand_not_in_range` | 2 |

* **Base rate:** 46 plan-eligible river decisions out of 346 river decisions in 300 hands =
  **15.3 per 100 hands** (the number gpt-5.6-sol named as missing, now measured).
* **43% of the activations end in an ERROR.** That is not a fallback design, that is a defect —
  and it is the next point of attack, not the H1 continuation.
* **The H0 patch does what it should:** no more catastrophe decks, only 3 diverging decks, median −200 chips.
  The patched fallback lands on the productive champion instead of the bare basis.
* **But:** with 8 played plans over 300 hands this channel cannot deliver a strength verdict. The
  candidate touches too few decisions to show up in bb/100.
