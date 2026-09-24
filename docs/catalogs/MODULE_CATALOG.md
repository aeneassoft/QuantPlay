# MODULE CATALOGUE — the building blocks of PokerB, described one by one

> **What this document is for.** It describes every module of this project SO that it can be judged
> INDIVIDUALLY: purpose, interface, input/output, dependencies, state, cost, measurement status and
> the one pitfall. The audience is a developer who does NOT know our bot and wants to build something of
> their own from these parts — they should be able to decide per module: take it or build it themselves.
>
> **Caution before computing further:** the measurement catalogue corrects, at its top, three things that were
> long misquoted in the project (variance coefficient 294 instead of 214, the anchor belongs to v4 not v5, two
> invalid Kaggle measurements). Anyone building from this module catalogue should read that FIRST.
>
> **Read alongside:** [`MEASUREMENT_CATALOG.md`](MEASUREMENT_CATALOG.md) — it records what was actually MEASURED on each
> building block and which of it still holds today. The module catalogue says what a part DOES; the measurement
> catalogue says whether it WORKS. Situation report: [`STATE.md`](../STATE.md). Doctrine: [`../CLAUDE.md`](../../CLAUDE.md).
> Candidates never measured at the anchor: [`CANDIDATES.md`](CANDIDATES.md).
>
> **Two warnings up front.**
> 1. **REFUTED modules are explicitly included.** Whatever is marked REFUTED here was disproved by
>    measurement — not forgotten. That is the most valuable part of the catalogue.
> 2. **There is no measurement status without a source.** Where it says `UNMEASURED`, no number exists. A module
>    can look excellent and still never have been proven.
>
> Created 2026-09-10 by 12 parallel reading agents + a completeness check against the file tree
> (410 Python modules found). The addendum at the end closes the gaps discovered in the process.

## Contents

- [Game Engine](#game-engine)
- [Strategy Core](#strategy-core)
- [Opponent and Range Reading](#opponent-and-range-reading)
- [Solver and Re-Solving](#solver-and-re-solving)
- [AUSLESE Guard Chain](#auslese-guard-chain)
- [v10 Packages (River Foundation)](#v10-packages-river-foundation)
- [Measurement Infrastructure](#measurement-infrastructure)
- [External Benchmarks](#external-benchmarks)
- [Opponents, League, Tournament](#opponents-league-tournament)
- [Products: Trainer, Coach, Vision](#products-trainer-coach-vision)
- [LLM Brain Track (historical)](#llm-brain-track-historical)
- [Knowledge Base, Data, Tools](#knowledge-base-data-tools)
- [Addendum — further modules](#addendum--further-modules)

---

## Game Engine

This subsystem is the rules-compliant foundation: card representation, 7-card hand evaluation, equity calculation
and two state machines (heads-up and N-player table with side pots), plus optional GPU accelerators.
You need it if you want to simulate hands, run an RL/self-play environment or compute equities;
you do NOT need it if you only make decisions at someone else's table (online client, third-party framework) —
then the card format, evaluator and equity suffice, and the two state machines are superfluous.
All modules are pure Python without network/IO (exceptions: `sd_eval.py` reads a file, the GPU modules need
torch); there is no strategy and no dependency on `pokerbot/strategy/` in this direction.

**Card convention (applies to the whole subsystem except the GPU modules):** a card is a 2-character string
`rank+suit`, rank from `"23456789TJQKA"`, suit from `"shdc"` — e.g. `'As'`, `'Td'`, `'2c'` (`cards.py:10-11`). That is
exactly the format `treys` expects, which is why there is no conversion table. Board and hole are lists of
such strings. Chips are ALWAYS `int` (blinds default sb=50/bb=100, i.e. 1 bb = 100 chips, `game.py:31`,
`table.py:44`). The GPU modules use a second encoding: `int64 = rank*4 + suit` with rank 0='2'..12='A',
suits `'shdc'` (`gpu_eval.py:196-201`) — the bridge is `gpu_eval.encode()`.

### Cards & hand classes — `pokerbot/engine/cards.py`
**Purpose.** Card strings, a shuffled deck and the 169 starting-class notation (`AA`/`AKs`/`AKo`) including
the mapping to concrete combos and back.

**Interface.**
- `make_deck() -> list[str]` — the 52 card strings in fixed order (rank outer, suit inner), `cards.py:19-20`.
- `class Deck(exclude: list[str] | None = None, rng: random.Random | None = None)` — shuffled remaining deck; `deal(n=1)
  -> list[str]` pops from the END of the list, `cards.py:23-33`.
- `hand_class(c1, c2) -> str` — map two cards to the canonical class, high rank first (`cards.py:36-44`).
- `normalize_class(hc) -> str` — bring loose spellings (`'kqs'`, `'qKs'`) to the canonical form (`:47-56`).
- `all_hand_classes() -> list[str]` — all 169 starting classes, deduped, in fixed order (`:59-78`).
- `expand_class(hc) -> list[tuple[str, str]]` — class to concrete combos: pair 6, suited 4, offsuit 12 (`:81-92`).
- `rank_value(rank) -> int` — 0..12 for '2'..'A'; `RANKS`, `SUITS`, `RANK_ORDER` as module constants.

**Input/Output.** In: card strings or class strings. Out: lists of card strings or lists of
2-tuples `(card, card)`. No dicts, no state in the functions.

**Dependencies.** Only `random` from the stdlib. The module is the root of the subsystem — everything else
imports it, it imports nothing. Replaceable if you bring your own card format; but then you must also adapt
`evaluator.py` (treys format) and the GPU bridge.

**Status.** Functions are stateless. `Deck` is stateful per hand (`self.cards` shrinks on `deal`);
build a new `Deck` per hand, do not reset (that is how `game.start_hand` and `table.start_hand` do it).

**Cost.** Not measured separately; all functions are O(52) or smaller. `all_hand_classes()`/`expand_class()`
are unmemoized — cache them yourself when calling in hot loops.

**Measurement status.** UNMEASURED (no dedicated test, no EV number). Indirectly correctness-checked: `tests/test_game.py`
(300 hands) and `tests/test_table.py` (500 hands) run on it and hold chip conservation — both executed
today, output "All chip-conservation & legality invariants held" and "Chip conservation & non-negative
stacks held every hand (incl. side pots)" respectively.

**Usable standalone?** Yes, fully isolated — copy the file, no dependency except `random`.

**Pitfalls.** `Deck.__init__` calls `rng.shuffle`; without a passed `rng`, `random.Random()` draws OS entropy →
runs are not reproducible. Anyone who wants to run paired/duplicate measurements MUST pass a seeded `rng`
through. Additionally: sets (`set`) of class strings are NOT deterministically iterable — that produced process
divergence three times in the repo (see `equity.py:124-126` and `../NOTES.md:21-27`); always `sorted()` before
`expand_class`.

### Hand evaluator + made-hand taxonomy — `pokerbot/engine/evaluator.py`
**Purpose.** 7-card hand evaluation via `treys` (memoized) plus the project-wide shared taxonomy
"air / pair / top-pair / two-pair+ / monster".

**Interface.**
- `evaluate(board: list[str], hole: list[str]) -> int` — score of the best 5 out of board+hole; **lower = stronger**
  (1 = royal flush, 7462 = worst high card). board+hole together must be >= 5 cards (`evaluator.py:31-39`).
- `hand_rank_name(score) -> str` — treys class name ("Two Pair", "Flush", ...) (`:42-43`).
- `best_five_name(board, hole) -> str` — short form of both (`:46-47`).
- `made_class(board, hole) -> str` — `'preflop' | 'air' | 'pair' | 'top-pair' | 'two-pair+' | 'monster'`; deliberately
  DEMOTES when the board makes the hand (board pair, double-paired board, board trips, 5-card board that
  plays on its own → `'air'`), and counts a straight as `'two-pair+'` (`:56-97`).

**Input/Output.** In: two lists of card strings. Out: `int` (score), `str` (name/class). No dicts.

**Dependencies.** HARD: `treys` (`requirements.txt`, `treys>=0.1.8`). `made_class` additionally on
`collections.Counter`. The treys part is replaceable (any 7-card evaluator with a total order will do), but then
the score direction flips and all comparisons `hs < vs` in the rest of the subsystem must be flipped along with it.

**Status.** Two module-global caches: `_CARD_INTS` (52 entries, complete after the first pass) and
`_EVAL_MEMO` (up to `_EVAL_MEMO_MAX = 120_000` entries, cleared COMPLETELY when reached, `evaluator.py:16-18,
33-38`). Both are pure function memos — nothing has to be reset between hands; they only cost RAM.

**Cost.** Measured today (this machine, CPython 3.12, cache cleared beforehand): 20.000 distinct 7-card
hands in 0,221 s = **~90.000 evaluate/s cold**; the same hands again = **~4,25 M/s from the memo**. The
memo was part of the measured `decide()` speed-up 999 ms → 83 ms (12,1x, `CLAUDE.md:163`,
`docs/STATE.md:817`, commit 114e107). RAM of the full memo not measured.

**Measurement status.** MEASURED POSITIVE for the memoization (12,1x on `decide()`, source above; byte identity of the
output proven, "0 diffs over 6 arms x 70 spots", `docs/STATE.md:818-819`). `made_class` itself: UNMEASURED in bb
— it is a taxonomy, not a lever; it is shared by `research/freq_mine.py:50-53`, `strategy/range_tracker.py:272-279`
and `coach/range_story.py` so that measured class mixes are comparable at all.

**Usable standalone?** Yes. Minimal: `pip install treys` + `cards.py` is not even needed (only the
card format). `made_class` is likewise standalone.

**Pitfalls.** The score direction is INVERSE to intuition (smaller = better) — and exactly the opposite of the
GPU evaluator in the same directory (`gpu_eval.score7`: larger = better). Anyone mixing both is guaranteed to
flip a comparison the wrong way somewhere. Secondly: `made_class` is deliberately NOT hand strength but a
hero-contribution class; a flush on the board is `'air'` here.

### Equity (Monte Carlo + exact river enumeration) — `pokerbot/engine/equity.py`
**Purpose.** Hero equity against a single hand, against a combo range, against a WEIGHTED combo range and
against a class range — enumerated exactly on the river, Monte Carlo before that.

**Interface.** (all with `board=None|list[str]`, `iters=DEFAULT_ITERS`, `rng=None`)
- `equity_vs_hand(hero, villain, board, iters, rng) -> float` — hero vs one concrete hand. On the river (board=5)
  NO sampling but an exact comparison → 1.0/0.5/0.0 (`equity.py:15-35`).
- `equity_vs_range(hero, villain_combos, board, iters, rng) -> float` — vs a list of 2-tuples. On the river **exact
  enumeration** over all combos (hero score once, variance 0); flop/turn MC over (combo, runout) (`:38-76`).
- `equity_vs_weighted_range(hero, combo_weights: dict, board, iters, rng) -> float` — the same for
  `{(card,card): weight}`; river = exact weighted enumeration, before that MC with weighted combo draws
  (`:79-117`).
- `equity_vs_class_range(hero, classes, board, iters, rng) -> float` — class strings (`'AKs'`) instead of combos;
  expands internally over `sorted(classes)` (`:120-130`).
- Constants: `BOARD_SIZE = 5`, `DEFAULT_ITERS = 3000` (code comment `:12`: "~0.9pp standard error").

**Input/Output.** In: card lists; for the weighted variant a dict whose keys are 2-tuples of
card strings and whose values are positive floats (weights need NOT be normalized). Out: a `float`
in [0,1]. **`float('nan')` if no villain combo remains after blocker filtering** (`:46, :89-90`) — the
caller must catch that.

**Dependencies.** `cards.expand_class`/`make_deck` and `evaluator.evaluate` — both hard, but trivially
replaceable. No numpy, no torch.

**Status.** Stateless except for `_FULL = make_deck()` (module-global, immutable) and the evaluator memo.
Nothing to reset.

**Cost.** Measured today (this machine): `equity_vs_hand`, flop, iters=3000: **0,041 s**;
`equity_vs_range`, flop, 200 combos, iters=3000: **0,041 s** (the cost depends on `iters`, NOT on the
combo count — one combo is drawn per iteration); `equity_vs_range` on the RIVER exact over 990 combos:
**0,011 s**. The number of evaluations is `len(combos)+1` on the river, `2*iters` before that.

**Measurement status.** MEASURED POSITIVE (correctness): the river enumeration is byte-identical to the independent
GPU enumeration — "River: 20 Proben exakt gegen CPU-Enumeration OK", tolerance 1e-9 (`gpu_equity.py:99-111`;
journal entry `R8-GPU-RESOLVER`, 2026-08-30: "gpu_equity exakt (River identisch CPU-Enum)"). MEASURED POSITIVE
(determinism): the `sorted()` fix in `equity_vs_class_range:124-129` fixed a reproduced process divergence
(same seed → place 378/12/4), afterwards verified byte-identical across processes (`../NOTES.md:21-27`).
UNMEASURED: whether `iters=3000` is the right precision — `../NOTES.md:203` explicitly says "TUNING IS PROVISIONAL";
an exact turn enumeration instead of MC is listed as an open item in `../NOTES.md:650-651`.

**Usable standalone?** Yes. Minimal: `cards.py` + `evaluator.py` + treys. This is the part a foreign bot can
most readily adopt without knowing anything else from the repo.

**Pitfalls.** Without a passed `rng`, every call is non-reproducible; with a shared `rng`, consecutive
calls are correlated — for paired A/B measurements you need a deterministically derived seed per decision
(in the repo: "unseeded MC breaks pairings", `CLAUDE.md`, measurement lessons).
Second pitfall: `equity_vs_range` samples the villain combo UNIFORMLY; anyone passing a range with
different combo counts per class implicitly gets the combo weighting — that is usually
right, but it is not a class-uniform distribution.

### Heads-up state machine — `pokerbot/engine/game.py`
**Purpose.** Complete HU NLHE hand: blinds, betting rounds, streets, showdown, refund of uncalled
bets — with a JSON-capable state snapshot.

**Interface.**
- `HeadsUpGame(names=("You","Bot"), starting_stack=10000, sb=50, bb=100, seed=None)` — `game.py:31`.
- `start_hand() -> None` — new hand: switch button, deal, post blinds. Raises `RuntimeError` if a
  player has <= 0 chips (`:68-94`).
- `legal_actions() -> dict` — see output below (`:97-128`).
- `act(action: str, amount: int|None = None) -> None` — `'fold' | 'check' | 'call' | 'bet' | 'raise' | 'allin'`.
  `amount` is the cumulative **TO level of the street**, not the increment; it is truncated via `int()` and
  SILENTLY clamped to `[raise_min, raise_max]` (`:131-183`).
- `state(hide: int|None = None) -> dict` — complete snapshot; `hide=k` masks the hole cards of player k
  as `["??","??"]` as long as nothing is revealed (`:290-307`).
- `pot() -> int`, `match_over() -> bool`; attributes `board`, `street`, `button`, `to_act`, `hand_over`, `result`,
  `history`, `players[0..1]` (dataclass `Player` with `stack/hole/folded/all_in/committed_street/committed_total`).

**Input/Output.** `legal_actions()` returns `{to_act, to_call, can_fold, can_check, can_call, call_amount,
can_raise, is_bet, raise_min, raise_max, pot}` — when the hand is over ONLY `{"to_act": None}`. `state()` returns
`{hand_no, button, street, board, pot, current_bet, to_act, hand_over, result, sb, bb, history, players[], legal}`;
**no `hand_id`** (`../reports/V10_FACTS.md:43-45`). `history` knows exactly 5 forms: fold/check
`{player,action,street}` · call `{player,action:'call',amount,street}` · bet/raise `{player,action,to,street}` ·
deal `{action:'deal',street,board}` without `player`; the label `'allin'` NEVER appears in the history (a jam is
a bet/raise with `to == committed_street+stack`) (`../reports/V10_FACTS.md:35-40`, `game.py:143-181,234-239`).
`result` = `{winner, reason:'fold'|'showdown', pot, reveal, board, [hands]}`.

**Dependencies.** `cards.Deck`, `evaluator.evaluate`/`best_five_name` — hard, but small. Otherwise only stdlib.
No dependency on strategy/advisor.

**Status.** Per hand: everything except `players[].stack`, `button` and `hand_no` is reset in `start_hand()`.
Per session: stacks carry over; anyone wanting independent hands resets the stacks themselves before each `start_hand()`
(that is how `tests/test_game.py:37` does it). `seed` only fixes the internal `random.Random`.

**Cost.** Not measured separately (the table variant manages ~6.200 hands/s, see below; HU is cheaper).

**Measurement status.** MEASURED POSITIVE (invariants): `python -m tests.test_game` executed today — "OK: played 300
hands | showdowns=109 folds=191 allin_hands=23 ... All chip-conservation & legality invariants held across every
hand." The channel on top of it is the project's entire measurement apparatus (paired duplicate runs `duplicate.py`,
`pargate`, GTOW adapter), i.e. the module has run millions of times. An EV value is meaningless for an engine —
UNMEASURED in bb, by construction.

**Usable standalone?** Yes: `cards.py` + `evaluator.py` + treys, nothing else. The strategy interface the rest
of the repo uses is `decide(state_dict) -> (action, amount)` with the `state()` dict above
(`pokerbot/benchmark/duplicate.py:8-9,101-115`).

**Pitfalls.** `amount` is a TO level and is silently clamped: anyone passing the increment unknowingly plays a
different size without an exception ever being raised. Second point: `can_fold` is defined as
`can_call` (`game.py:119`) — but a fold at `to_call == 0` is nevertheless NOT rejected and folds the hand
(`../reports/V10_FACTS.md:32-33`); so your bot can throw itself away. Thirdly: the engine default is
`starting_stack=10000` (100 bb), but all measurement channels of the repo run 20000/50/100 = 200 bb
(`../reports/V10_FACTS.md:47-49`) — numbers are only comparable at equal stack depth.

### N-player table / RL environment — `pokerbot/engine/table.py`
**Purpose.** 2–10 seats No-Limit Hold'em with correct side pots, optional antes and optional auto-rebuy — the
environment on which self-play, the 6-max league and the web app run.

**Interface.**
- `Table(names, starting_stack=10000, sb=50, bb=100, seed=None, human_seat=0, stacks=None, ante=0, rebuy=True)` —
  `stacks` = individual starting stacks (tournament), `ante` = dead up-front tax per hand, `rebuy=False` leaves busted
  players busted (`table.py:44-51`).
- `start_hand() -> None` — auto-rebuy (if active), reset, button+1, deal, antes BEFORE the blinds, blinds,
  determine first actor (`:103-154`).
- `legal_actions() -> dict` — for the seat CURRENTLY to act (`:163-181`).
- `act(action, amount=None) -> None` — `'fold'|'check'|'call'|'bet'|'raise'|'allin'`; `amount` = TO level of the
  street, `int()`-truncated and silently clamped; every (re-)raise reopens the action (`has_acted=False`
  for all others) (`:184-225`).
- `obs_for(seat) -> dict` — observation for a seat (`:340-352`).
- `position_label(seat) -> str` — `BTN/SB/BB/UTG/UTG+1/UTG+2/UTG+3/LJ/HJ/CO` depending on table size
  (`POS_LABELS`, `:17-27`, `:94-100`).
- `pot() -> int`; attributes `seats[]` (dataclass `Seat`), `board`, `street`, `button`, `to_act`, `hand_over`,
  `result`, `history`, `hand_no`.

**Input/Output.** `legal_actions()` → `{to_act, to_call, can_fold, can_check, can_call, call_amount, can_raise,
is_bet, raise_min, raise_max, pot}`; when the hand is over only `{"to_act": None}`. `obs_for(seat)` →
`{hole, board, to_call, pot, my_stack, bb, n_active, position, preflop_raises, cur_bet, my_committed_street,
street, can_check, can_call, can_raise, raise_min, raise_max}`. `result` on a fold ending:
`{reason:'fold', pot, reveal:False, winners:[{seat,name,amount}], board}`; at showdown additionally
`{pots:[{amount,winners}], shown:{seat:{hole,rank}}}` — **`shown` contains ONLY winners** (mucking, `:332-334`).

**As an RL environment.** The loop is `start_hand()` → while `not hand_over`: `obs_for(to_act)` /
`legal_actions()` → `act(a, amt)` → at the end `result` as the reward source (the stack difference per seat is the
clean reward quantity, not `result['pot']`, see pitfalls). There is NO `reset()` and no
gym/gymnasium interface; `start_hand()` is the reset. There are no observation encoders — `obs_for` returns
raw Python types, featurizing is your job.
- **Side pots**: `_build_pots()` layers over `committed_total` (`:272-285`); each layer gets its
  eligible set, split remainders go to the first winner clockwise from the button (`:317-321`). A
  layer without eligibles (fold ABOVE an all-in cap) is REFUNDED to the contributors instead of destroyed
  (`:301-309`) — the comment there cites the fuzz finding "-99 Chips auch ohne Antes moeglich".
- **Antes**: are committed before the blinds and afterwards `committed_street` is reset to 0, otherwise the
  ante counts against `current_bet` (`:124-135`; the comment lists the three bugs this produced in the 600-player
  MTT audit, chip conservation −32/table).
- **Heads-up special case**: at `n == 2` the button is the small blind and acts first preflop (`:136-140`) —
  this used to be inverted and affected every multiway endgame that shrank to 2 players.
- **Rebuy**: `rebuy=True` (default) tops up every stack < 1 bb to `starting_stack` in `start_hand()` (`:104-106`).

**Dependencies.** `cards.Deck`, `evaluator.evaluate`/`best_five_name`. Otherwise stdlib. No strategy imports.

**Status.** Per hand: board, street, history, `committed_*`, `folded/all_in/has_acted` (reset in `start_hand`).
Per session: `seats[].stack`, `button`, `hand_no`, the internal RNG. For independent hands reset the stacks
yourself (`tests/test_table.py:32-33`).

**Cost.** Measured today: 2.000 complete 6-max hands with a trivial random policy in 0,323 s =
**~6.200 hands/s** single-threaded (without bot decision time; in practice that dominates by orders of magnitude).

**Measurement status.** MEASURED POSITIVE (invariants): `python -m tests.test_table` executed today — "OK: 500 six-max
hands | showdowns=486 folds=14 allin_hands=498 side-pot_hands=374 / Chip conservation & non-negative stacks held
every hand (incl. side pots)." Chip conservation is a non-negotiable gate in the project (`CLAUDE.md`,
operative doctrine). UNMEASURED in bb (environment, not a lever).

**Usable standalone?** Yes: `cards.py` + `evaluator.py` + treys. No server, no config import.

**Pitfalls.** **`obs_for(seat)` mixes two perspectives**: `hole`/`my_stack`/`position` come from the
passed seat, but `to_call`/`can_check`/`can_call`/`can_raise`/`raise_min`/`raise_max` come from
`legal_actions()` and apply to the player who is CURRENTLY to act (`table.py:340-352`). Verified today: at
a 3-seat table `obs_for(not_to_act)` returns `to_call=100, can_check=False` — the actor's values. Call it only
with `seat == table.to_act`. And after the hand ends it raises `KeyError: 'to_call'`, because `legal_actions()` then only
returns `{"to_act": None}` (reproduced today).
Two further mines: (a) `act('raise', None)` raises `TypeError: int() argument ... not 'NoneType'` instead of a
clean ValueError (reproduced today; `game.py` checks this explicitly, `table.py:208` does not). (b)
`result['pot']` also contains uncalled bets — there is no `_refund_uncalled` in `table.py` as in
`game.py:241-251`; reproduced today: seat jams 1000, everyone folds, `result['pot'] = 1150`, actual
profit +150. For bb/100 always compute stack differences, never `result['pot']`. (c) The auto-rebuy is ON by
default and silently tops up stacks — set `rebuy=False` for every measurement.

### Suit isomorphism — `pokerbot/engine/isomorph.py`
**Purpose.** Board canonicalization via suit relabeling (Johanson 2007 §2.5.1): up to 24 solve-cache entries per
strategic situation collapse into one.

**Interface.**
- `canonical_board(board: list[str]) -> tuple[list[str], dict]` — canonical board (lexicographically minimal over
  all 24 suit permutations, card order preserved) plus the suit map used
  (`isomorph.py:20-28`).
- `apply_map(card: str, suit_map: dict) -> str` — apply the same map to an arbitrary card (hero hole)
  (`:31-32`).
- `main()` — self-test (`:35-49`).

**Input/Output.** In: list of card strings. Out: `(list, dict)` with dict `{'s':'h', 'h':'s', ...}`.

**Dependencies.** Only `itertools`. Completely free-standing.

**Status.** Stateless (`_ALL_PERMS` is a constant).

**Cost.** O(24 · |board|) per call, as stated in the docstring; absolute latency not measured.

**Measurement status.** MEASURED POSITIVE (correctness): self-test executed today — "isomorph self-test: 500 boards x
24 relabelings -> canonical form idempotent + invariant. OK". MEASURED POSITIVE (effect on the cache):
`../NOTES.md:645-646` — "permuted board -> cache collapse 5.0s->0.0s, identical strategy", up to 24x hit rate on
the 12-GB cache. UNMEASURED in bb; the switch `POKERB_ISO_CACHE` is default OFF in the repo
(`pokerbot/strategy/gto_oracle.py:54`).

**Usable standalone?** Yes, one file without dependencies.

**Pitfalls.** The canonicalization is only EXACT if nothing suit-bearing besides board and hero hole enters
the solve — in the repo that holds because ranges are CLASS strings and navigation runs over bet-size labels
(`isomorph.py:4-7`). Anyone passing suit-specific ranges (`AhKh`) or suit-dependent features through
gets wrong cache hits — silently.

### Short-deck evaluator (6+) — `pokerbot/engine/sd_eval.py`
**Purpose.** Hand evaluation for the 36-card variant 6+ Hold'em, deliberately separated from the 52-card treys path.

**Interface.**
- `available() -> bool` — is the rank table present (`sd_eval.py:41-42`).
- `rank5(cards5_tuple) -> int` — `lru_cache(200000)`; **lower = better** (`:51-53`).
- `rank7(cards7) -> int` — best (smallest) result over the 21 five-card subsets (`:56-61`).
- `best_hand_rank(hole, board) -> int` (`:64-66`); `normalized_strength(hole, board) -> float` in [0,1], 1 = best
  (`:69-72`).
- Constants `SD_RANKS = "6789TJQKA"`, `SD_SUITS = "cdhs"`, `SD_DECK` (36 cards).

**Input/Output.** In: card strings with ranks 6..A (a 2–5 raises `KeyError`, intentionally as a
leakage guard). Out: `int` rank or `float` strength.

**Dependencies.** HARD on a FILE: `tools/TexasSolver-v0.2.0-Windows/resources/compairer/
card5_dic_sorted_shortdeck.txt` (C(36,5) = 376.992 lines), path via `pokerbot.config.ROOT` (`:22-23`). Without the
TexasSolver bundle the module is useless. The import of `pokerbot.config` is the only coupling into the repo and
could be replaced by a path parameter.

**Status.** Module-global `_DICT` (lazily loaded, 376.992 entries) plus the `lru_cache`. RAM not measured.

**Cost.** Not measured. `rank7` does up to 21 dict lookups per hand.

**Measurement status.** UNMEASURED in bb. Correctness: the docstring documents a verification from 2026-06-15
(variant: flush > full house, A-6-7-8-9 wheel, **trips > straight**) — the source for that is the docstring itself
(`sd_eval.py:1-7`), no test script in the repo. File availability checked today: `available() == True`.

**Usable standalone?** Yes, if you have the rank table and replace the `config` import with a path.
Consumer in the repo: `research/build_sd_advisor_data.py`.

**Pitfalls.** The variant rule **trips beat straight** is room-dependent — the docstring warns itself:
"confirm vs the target room before any COMPETITIVE use". Anyone who does not check that evaluates systematically
wrong in a standard 6+ room.

### GPU evaluator — `pokerbot/engine/gpu_eval.py`
**Purpose.** Vectorized 7-card evaluator as a single torch batch operation, order-isomorphic to the
CPU evaluator.

**Interface.**
- `score7(cards: torch.Tensor) -> torch.Tensor` — `[N,7]` long (cards 0..51) → `[N]` long score,
  **larger = better** (`gpu_eval.py:75-193`). Score layout: `category * 13^5 + k1*13^4 + ... + k5`,
  category 8 = straight flush .. 0 = high card.
- `encode(cards: list[str]) -> list[int]` — bridge `'As'` → `rank*4+suit` (`:200-201`).
- `verify_vs_reference(n=200_000, seed=7) -> (checked, errors)` — order isomorphism against
  `evaluator.evaluate` on n random pairs (`:204-225`).
- `benchmark(n=2_000_000) -> dict` (`:228-...`); `DEVICE` = cuda if available, else cpu (`:32`).
- Executable: `python -m pokerbot.engine.gpu_eval` (verification + benchmark).

**Input/Output.** In: `torch.Tensor [N,7] dtype=long`. Out: `torch.Tensor [N] dtype=long` on `DEVICE`.
No dicts.

**Dependencies.** HARD: `torch` — **not declared in `requirements.txt`** (locally 2.11.0+cu128, CUDA
available, checked today). For the verification additionally `cards.py` + `evaluator.py`. Also runs on CPU
(slower), but is pointless there.

**Status.** Stateless; only constants (`_P13`, `_STRAIGHTS`). No RNG.

**Cost.** MEASURED: **16,8 M hands/s** (`docs/STATE.md:115-116`; journal `R8-GPU-RESOLVER` 2026-08-30).
Memory: the intermediate tensors are `[N,13]`/`[N,7]` long — relevant for N in the millions, not measured.

**Measurement status.** MEASURED POSITIVE (correctness): 250.000 order pairs, **0 errors** (`docs/STATE.md:115-116`,
journal `R8-GPU-RESOLVER`). UNMEASURED in bb — it is an accelerator, not a lever; the docstring itself says
"ADDITIV: dieses Modul aendert NICHTS am bestehenden Pfad" (additive: this module changes NOTHING in the existing path). There is NO file under `tests/` for it, only the
`__main__` self-test (`../reports/V10_FACTS.md:27`).

**Usable standalone?** Yes, for `score7`/`encode` torch suffices. For `verify_vs_reference` you additionally need
treys + `cards.py` + `evaluator.py`.

**Pitfalls.** The score direction is INVERSE to the CPU evaluator (here larger = better, there smaller = better) —
that is the number-one error source when mixing. Second, expensively learned point: `_highest_bit` is
intentionally integer-only, because CUDA `log2` may be off by 1 ulp and delivered a wrong rank at exact powers of
two (`gpu_eval.py:53-56`, "lesson: CUDA-log2 1-ulp trap" `docs/STATE.md:116`). Anyone who
"optimizes" that builds in a silent single-case error.

### GPU equity (exact enumeration) — `pokerbot/engine/gpu_equity.py`
**Purpose.** Hero equity against EVERY combo of a range with a fully enumerated runout space, as a batch tensor op.

**Interface.**
- `equity_vs_range_exakt(hero: list[str], villain_combos: list[tuple[str,str]], board: list[str]) -> torch.Tensor`
  — `[C]` float on CPU; **one equity per villain combo** (not a scalar!); combos that block hero/board
  get `NaN` (`gpu_equity.py:34-87`).
- `_verify()` / `_benchmark()` — only via `python -m pokerbot.engine.gpu_equity` (`:90-169`).

**Input/Output.** board with 3, 4 or 5 cards. Enumerates river: C combos; turn: C × 46 river cards;
flop: C × 1081 turn/river pairs (`:3-8`). Output `[C]` with NaN for blocked combos — the caller must
apply `nanmean()`/its own weighting; the module delivers NO weighted aggregation.

**Dependencies.** HARD: `torch` (not in `requirements.txt`) and `gpu_eval` (`DEVICE`, `encode`, `score7`).
For the verification additionally `equity.py` as the CPU reference.

**Status.** Stateless, no RNG, no cache.

**Cost.** MEASURED: flop, 1081 combos × 1081 runouts EXACT in **0,087 s** (`docs/STATE.md:117`). Memory
scales with C×R (the `[C,R,7]` tensor) — at 1326 combos × 1081 runouts that is ~10 M long entries per
intermediate step; peak VRAM not measured.

**Measurement status.** MEASURED POSITIVE (correctness): river byte-identical to the CPU enumeration, tolerance 1e-9, 20
samples; flop within the 4-SE band of the CPU MC (`gpu_equity.py:99-131`; `docs/STATE.md:117`; journal `R8-GPU-RESOLVER`).
UNMEASURED in bb. **Important: `../reports/V10_FACTS.md:204-206` records — "NO 1326-batch variant, NO
weighted variant, no production caller"**; the module today is a tool/building block, not part of the running
bot. In `../plans/V10_BUILD_CARD.md:157` the card "gpu_equity vectorized" was STRUCK from the K1 plan again.

**Usable standalone?** Yes: torch + `gpu_eval.py` + `gpu_equity.py`. For the self-test additionally treys,
`cards.py`, `evaluator.py`, `equity.py`.

**Pitfalls.** The return value is a vector per combo, not a scalar — `float(eq)` fails, and a naive
`eq.mean()` returns NaN as soon as a single combo blocks (correct is `nanmean()`, as the verification does
`:107`). Secondly, the verification computes UNWEIGHTED uniformly over the combos; anyone with range weights
must write the aggregation themselves.

### Package export — `pokerbot/engine/__init__.py`
**Purpose.** Re-export of the card and evaluator primitives.

**Interface.** `RANKS, SUITS, make_deck, Deck, hand_class, all_hand_classes, expand_class, rank_value,
normalize_class, evaluate, hand_rank_name, best_five_name` (`__init__.py:2-12`).

**Input/Output.** Not applicable.

**Dependencies.** `cards.py`, `evaluator.py` — i.e. an `import pokerbot.engine` immediately pulls in `treys`.

**Status.** Stateless.

**Cost.** Import time of treys; not measured.

**Measurement status.** UNMEASURED (pure re-export file).

**Usable standalone?** Not applicable.

**Pitfalls.** `equity`, `game`, `table`, `made_class`, `sd_eval`, `isomorph` and the GPU modules are NOT
exported here — you must import them with the full path (`from pokerbot.engine.table import Table`). Anyone relying on
`from pokerbot.engine import *` does not get half the engine.

---

## Strategy Core

This subsystem is the complete decision pipeline of a **heads-up no-limit bot**: a state dict in,
a legal action plus a justifying rationale dict out. It consists of one large rule tree (`bot.py`) and
four small, cleanly isolable preflop data layers (strength model, range definitions, a CFR-solved
push-fold blueprint, a near-Nash 200bb blueprint). You need it ONLY if you want a HU bot — the core is
hard-wired for 2 players (`1 - hero_idx` in ~20 places); for 6-max a separate, independent core exists
(`pokerbot/arena/sixmax.py`). The preflop data layers (2nd–8th below), by contrast, are individually reusable and
clearly the most valuable parts if you want to build your own tree.

---

### Decision pipeline (PokerBot) — `pokerbot/strategy/bot.py`

**Purpose.** A 1320-line rule tree that produces a legal action plus structured justification from a heads-up
game state by querying preflop blueprints, MC equity, trained solver advisors, a range tracker and
optional real-time resolvers in a fixed priority chain.

**Interface.**
- `PokerBot(hero_idx: int, seed: int | None = None, exploit: bool = True)` — one bot object for ONE seat.
  `hero_idx` is the seat index (0/1), `seed` seeds `random.Random` for mixed strategies.
- `decide(state: dict) -> dict` — the only real API. Raises `ValueError` if `state["legal"]["to_act"]`
  is not `hero_idx` (bot.py:206-207).
- `observe_opponent(street: str, action: str, facing_bet: bool) -> None` — feeds the aggregate opponent model
  (`OpponentModel`), must be called by the caller after EVERY opponent action (bot.py:1292).
- `observe_hand_end(final_state=None) -> None` — closes the hand and feeds the opponent's reactions to
  our river bets into the Dirichlet node model (bot.py:1295-1320).
- Public attributes as A/B switches (set in `__init__`, bot.py:155-201): `exploit`, `use_resolver`,
  `use_turn_resolver`, `use_flop_resolver`, `use_range_tracker`, `use_blueprint`, `bp_deep_min_bb`,
  `bp_jam_min_pct`, `deep_jam_pct`, `value_raise_eq`, `use_commit_cap`, `use_probe`, `use_deepcfr`,
  `tracker_cls` (swappable range-tracker class), `fold_model`.

**Input/Output.** Input = the engine's state dict (`pokerbot/engine/game.py:state()`). Load-bearing keys:
`street` ("preflop"/"flop"/"turn"/"river"), `board` (list of 2-character cards), `pot` (chips), `bb`, `sb`,
`button` (seat index), `current_bet`, `history` (list; entries `{player, action, street}` plus
`{action:"deal", street, board}` at every board deal — both forms are read, game.py:239),
`players` (list per seat with `hole`, `stack`, `committed_street`, `committed_total`, `all_in`, `folded`) and
`legal` with `to_act`, `to_call`, `can_check`, `can_call`, `can_raise`, `is_bet`, `raise_min`, `raise_max`, `pot`.
Output = `{"action": str, "amount": int|None, "rationale": dict}`. `action` is one of
`fold|check|call|bet|raise|allin`; `amount` is a **target total bet for this street** ("to"), NOT a delta
(game.py:168-172), and is `None` for fold/check/call/allin. `rationale` always carries `reasoning` (plain text,
`_mk`, bot.py:1286) plus path-dependent diagnostic fields — preflop `phase/hand/hand_class/percentile/eff_stack_bb/
position`, postflop additionally `made_hand/equity/villain_combos/texture/required_equity/mdf/call_threshold`,
resolver paths only a thin `{phase, street, hand, made_hand, board, range_conf, resolver:True}`.

**Dependencies.** HARD: `pokerbot.engine.cards` (hand_class/expand_class), `pokerbot.engine.evaluator`
(treys-based), `pokerbot.engine.equity` (`equity_vs_range`, `equity_vs_weighted_range`),
`pokerbot.strategy.preflop_strength`, `ranges`, `postflop` (sizing/texture/constants), `advisor`
(trained MLPs), `opp_model`, `opponent`, `blueprint`, `preflop_blueprint`, `gto_mode`, `pokerbot.config`
(paths to `knowledge_base/`). REPLACEABLE (lazily imported, each in try/except or with None fallback):
`range_tracker` (falls back to the `_narrow` heuristic), `resolver` (falls back to the floor),
`deepcfr_adapter` (only with `use_deepcfr=True`).

**Status.** Per session: `opp` (aggregate opponent frequencies), `opp_model` (Dirichlet per river node),
`_probe_spent_bb` (risk budget of the off-tree probes), `rng`. Per hand: `_river_keys` (cleared at the start of every
preflop decision, bot.py:217), `_hand_u`/`_hand_u_by_id` (line draw per hand, only under
`POKERB_LINE_U`; the id variant is trimmed at >64 entries). Per decision: `_cur_street`,
`_cur_committed`, `_ecall_exact_to`, `_cur_state/_cur_hole/_cur_board`. Reset between sessions = new object;
a reset between hands is NOT necessary, but `observe_hand_end` must be called, otherwise
`_river_keys` grow and the Dirichlet model learns nothing.

**Cost.** `decide()` ≈ **83 ms** after the memoization of `advisor.p_bet/p_defense` (before 999 ms, factor
12,1; CLAUDE.md:163 / ../plans/TRAINER_PLAN.md:563 / ../reports/V10_FACTS.md:103 — the advisor is memoized, not
`decide` itself). The dominant item postflop is the MC equity with `EQUITY_ITERS = 1500` (bot.py:29).
With `use_resolver=True` a real river solve is added (latency not documented in this file; the
cache flags `POKERB_SOLVE_CACHE/POKERB_ISO_CACHE` are, per gto_mode.py:83-86, not semantics-neutral at the
timeout edge). Memory: small, except for the advisor net loaded once and the JSON tables.

**Measurement status.** MEASURED — the overall bot has been measured several times against GTO Wizard (AIVAT):
HEAD default (all flags off) **−20,09 ± 7,18 bb/100, n=974** (CLAUDE.md, block 2026-07-04);
profile PRINCE v2.2 **−19,70 ± 4,37 bb/100, n=2393, 0 catastrophes** (gto_mode.py:32-34);
current single confirmed live anchor **v4-on-PRINCE −21,1** (docs/STATE.md:52).
REFUTED is the exploit path: `POKERB_EXPLOIT=1` vs `0`, 600 paired decks per league profile, all 8
point estimates ≤ 0, pooled ≈ **−12 bb/100 (SE ~4,5)** (journal `data/autogym/journal.jsonl`, entry
`EXPLOIT-GATE-VERDIKT`, 2026-09-09) → `_river_exploit` loses against EVERY profile, even the
exploitable ones. The range tracker as the equity source is MEASURED POSITIVE on the range metric
(L1 0,437 vs `_narrow` 0,756 vs uniform 0,995 = +42 % closer to the solver truth, ../NOTES.md) and
EV-wise NEUTRAL to slightly positive (duplicate n=250: ON>OFF +50,5 ± 40,7; vs GTOBaseline −31,4 ± 58).

**Usable standalone?** Yes, but only with half the repo. Minimally required: `pokerbot/engine/*` (cards, evaluator,
equity), `pokerbot/config.py` (path to `knowledge_base/`), `strategy/{preflop_strength, ranges, postflop,
advisor, opp_model, opponent, blueprint, preflop_blueprint, gto_mode}` and the JSON/PT artifacts under
`knowledge_base/`. Without the advisor net and without blueprints the bot still runs — each of these layers has
an `available()` fallback to the heuristic. `tests/test_bot.py:14` shows the minimal state dict required
for a self-build.

**Pitfalls.** The tree is **strictly heads-up**: `state["players"][1 - self.hero_idx]` appears everywhere
(e.g. bot.py:330, 630, 712, 1044) — at a 3+-player table it reads the wrong seat and does not raise but
silently computes wrong. Secondly: `amount` is a **to amount**, not a raise delta; anyone interpreting it as a
delta systematically builds min-raises. Thirdly: the behavior depends on ~25 environment variables
that are read at **IMPORT time** (bot.py:32-105) — `gto_mode.apply()` or `auslese.setze_env()` MUST
run before the import, otherwise the configuration is half on.

---

### Depth gate and push-fold layer (cross-section through `_preflop`)

`_preflop` (bot.py:264-317) branches first by effective stack depth. `_eff_stack` = minimum over both
players of `stack + committed_total` (bot.py:1226-1227), divided by `bb`. This yields **three regimes**:

1. **`eff_bb <= 14` → push/fold** (bot.py:278). `_pushfold` (bot.py:381-424) queries the CFR blueprint
   `blueprint.pushfold(eff_bb, hand_class)` and handles three nodes: call/fold against an all-in per
   the solved `call` probability; SB first-in jam/fold per the `jam` probability; BB re-jam against
   a non-all-in raise if the percentile lies above `1 - R.call_shove_fraction(eff_bb)`.
   If the blueprint file is missing, the percentile fallback `R.push_fraction(eff_bb)` takes its place
   (bot.py:396, 415).
2. **`14 < eff_bb < bp_deep_min_bb (140.0)` → heuristic cascade.** Neither push/fold nor blueprint fire.
   The chain plays SB first-in (open top `R.SB_OPEN_FRAC = 0.84` to 2,5bb) → BB option after limp →
   `_bb_vs_open` (equity vs SB open range × realization factor 0,82) → `_vs_3bet` → `_deep_reraise`
   (stack-off only above `deep_jam_pct = 0.985`). **This is the regime in which 100-bb play takes place** —
   i.e. the usual cash-game depth and e.g. the Kaggle arena (100 bb, docs/STATE.md:7).
3. **`eff_bb >= 140` → 200-bb blueprint** (bot.py:319-379), provided `use_blueprint=True` and the file exists.
   If the blueprint returns no distribution for the node, the code falls back to the heuristic cascade
   (`return None`).

Two clamps sit above the blueprint: `bp_jam_min_pct = 0.90` forbids jam/5bet bluffs below the
top 10 % at the nodes 4BET/5BET (the checkdown solve is blocker-blind and would jam 76s for 200 bb,
../NOTES.md:329), and `POKERB_GTOW_NOLIMP` renormalizes the SB limp mass onto open/fold.

The depth gate is an **honesty boundary, not an optimization**: the blueprint was solved at 200 bb,
below that it would be outside its model (../NOTES.md:333-335 "100bb apps fall through to the heuristic").

---

### Flag and profile layer (GTO mode / PRINCE) — `pokerbot/strategy/gto_mode.py`

**Purpose.** Import-order-safe access to ~40 behavior flags plus two named profiles, so that a
measured run is reproducible and can be logged as a fingerprint.

**Interface.**
- `flag(name: str, default: str) -> str` — priority: explicit env variable > PRINCE profile > GTO-mode profile >
  default (gto_mode.py:114-125). Strategy modules read exclusively through this.
- `apply() -> bool` — expands the active profiles into the environment via `os.environ.setdefault`; must run BEFORE the
  import of `pokerbot.strategy.*`.
- `enabled()` / `prince_enabled()` — state of the two profile switches.
- `fingerprint() -> dict` — the env slice that defines a run (`_FINGERPRINT_KEYS`, gto_mode.py:72-97).
- Constants `PROFILE`, `PRINCE_PROFILE`, `FINAL_PROFILE`.

**Input/Output.** Input: `os.environ`. Output: strings (the calling modules cast to
float/bool themselves). `fingerprint()` returns a dict `{FLAG_NAME: value-or-None}`.

**Dependencies.** None except `os`. Fully decouplable — the only reason to adopt it is
the pattern.

**Status.** Stateless (reads `os.environ` on every call). `apply()` mutates the process environment; a reset
requires a new process, because the consumers freeze the values at import time.

**Cost.** Negligible (dict lookups).

**Measurement status.** MEASURED POSITIVE as a profile: `PRINCE_PROFILE` is the only configuration validated at **AIVAT −19,70 ± 4,37
(n=2393, 0 catastrophes, per-hand SD 214)** (gto_mode.py:32-34). REFUTED as a stack:
the levers added after v2.2 (`POKERB_PURIFY`, `POKERB_RAISE_NARROW`, `POKERB_OVERBET_MENU`,
`POKERB_TURN_DEF_ADVISOR`, `POKERB_PAIR_DEFENSE`, `POKERB_RIVER_DEFENSE`) are explicitly excluded because
their stacked v8 state broke live at **AIVAT −58** (gto_mode.py:56-66).

**Usable standalone?** Yes, one file, no dependencies.

**Pitfalls.** The order. `apply()` after the first `import pokerbot.strategy.bot` has no effect on
all flags that are read as module constants (bot.py:32-105) — a half-configured bot that silently
plays wrong. The comment in gto_mode.py:5-6 says so explicitly; it is nevertheless the most frequently
documented mistake in the repo.

---

### 200-bb preflop blueprint (near-Nash) — `pokerbot/strategy/preflop_blueprint.py`

**Purpose.** Loads a preflop strategy solved offline with exact CFR+ and maps a live state
(position, number of raises, all-in flag) to one of nine blueprint nodes, from which the mixed
GTO action is drawn.

**Interface.**
- `available() -> bool` — loads the JSON lazily; `False` on a missing/broken file (caller falls back).
- `node_for_state(is_sb: bool, raises: int, can_check: bool, villain_allin: bool) -> str | None` — the pure
  structural mapping to `ROOT|LIMP|OPEN|ISO|3BET|4BET|JAMSB|5BET|JAMBB`; `None` = outside the tree.
- `actions(node: str, hc: str) -> dict | None` — the solved action→probability distribution.
- `pick(node: str, hc: str, rng) -> tuple[str, dict] | None` — draws an action from the mix.
- `SIZES_BB: dict` — action→total bet in bb (`limp 1.0, open 2.5, iso 4.5, 3bet 10, 4bet 24, 5bet 60`;
  under `POKERB_GTOW_SIZES=1` instead the 2.25/4.5/9/27/67.5 measured at GTO Wizard, lines 34-37).

**Input/Output.** Input: structural features of the state plus the 169 hand class ("AA", "AKs", "72o").
Output: `(action, distribution)` with actions from `fold|check|call|limp|open|iso|3bet|4bet|5bet|jam`. Data source:
`knowledge_base/ranges/preflop_blueprint.json` (88 KB, 9 nodes × 169 classes; under `POKERB_GRAFT=1` instead
`preflop_blueprint_solvergraft.json`).

**Dependencies.** HARD only `pokerbot.config` (path) and `gto_mode.flag`. The JSON itself is the actual
value; the loader is trivially rebuildable.

**Status.** Stateless after the one-time load (module-global `_BP`). No reset needed; switching the
file at runtime is not intended.

**Cost.** Parse ~88 KB JSON once, then dict lookups. Not measured, but obviously negligible.

**Measurement status.** UNMEASURED as an EV lever. The intended gate — GTOW-AIVAT A/B `use_blueprint` ON vs OFF at
n≥2500 — is **DEFERRED** to this day; only a directional run with n=200 exists (docs/STATE.md:1585-1590,
../NOTES.md:337). MEASURED was only a non-circular side metric: the exploitability in the simplified
preflop game drops from 6,12 to 2,03 with the solver-grafted variant (../NOTES.md:380-386). VERIFIED (unit,
not EV): all 9 node mappings, all-in discipline (QQ/AKo fold 200-bb jams at 0,96; AA/KK call),
jam clamp and the robust shove detection (docs/STATE.md:1585-1589).

**Usable standalone?** Yes — with the JSON and your own hand-class normalization the loader is rebuilt in 30 lines.
The file is solved at 200 bb; for 100 bb no equivalent exists.

**Pitfalls.** `node_for_state` counts `raises` as the number of all preflop `bet|raise` entries in the history
(bot.py:1229-1231). Anyone with a different history semantics (e.g. blinds counted as a bet) lands systematically
one node too deep — and then a 4bet range applies to a 3bet situation.

---

### Push-fold blueprint loader — `pokerbot/strategy/blueprint.py`

**Purpose.** Serves the CFR-solved short-stack jam/call probabilities for the nearest
solved stack depth.

**Interface.**
- `available() -> bool` — loads lazily, `False` on a missing file.
- `pushfold(stack_bb: float, hand_class: str) -> dict | None` — `{"jam": p, "call": p}` for the nearest
  solved depth (`min(stacks, key=|x - stack_bb|)`, blueprint.py:29-31).

**Input/Output.** Input: effective depth in bb (float) and hand class (normalized via
`cards.normalize_class`). Output: two probabilities. Source:
`knowledge_base/cfr/preflop_pushfold.json` (172 KB, stack depths 2-20 bb × 169 classes).

**Dependencies.** `pokerbot.config`, `pokerbot.engine.cards.normalize_class`. Both replaceable.

**Status.** Stateless (module cache `_pf`).

**Cost.** 172 KB JSON once, then two dict lookups. Not measured.

**Measurement status.** MEASURED POSITIVE against an external reference, NOT against EV: the output matches
published Nash push-fold charts almost exactly (10 bb: SB jam ≈ 55 %, BB call ≈ 44 %; AA/KQo ≈ 100 %, 72o ≈ 0 %) —
`docs/archive/pluribus_and_benchmarking.md:30-33`. The file itself confirms this
(10 bb: `AA {jam 0.999, call 0.999}`, `A5s {0.751, 0.735}`, `KQo {0.998, 0.995}`, `72o {0.0, 0.003}`). A
bb/100 A/B of the push-fold layer against the percentile heuristic is UNMEASURED.

**Usable standalone?** Yes, this is the most easily extractable building block of the whole repo: one JSON plus
two functions. Directly usable for a short-stack tournament bot.

**Pitfalls.** The nearest depth is taken without interpolation — at 20,4 bb you get the
20-bb solution, at 25 bb likewise the 20-bb solution (the gate in `bot.py:278` catches that, your own
caller does not). And the solution applies to the pure jam-or-fold game: it knows no min-raises.

---

### Push-fold CFR solver — `pokerbot/strategy/cfr_preflop.py`

**Purpose.** Produces the blueprint above via chance-sampled Counterfactual Regret Minimization over the
HU push-fold game (SB jams or folds, BB calls or folds) for every stack depth 2-20 bb.

**Interface.**
- `solve_stack(stack_bb: float, iters: int, rng: random.Random) -> dict` — solves ONE depth, returns
  `{class: {"jam": p, "call": p}}`.
- `main()` — CLI: `python -m pokerbot.strategy.cfr_preflop [--iters N] [--quick]`; writes
  `knowledge_base/cfr/preflop_pushfold.json` (only without `--quick`).
- `_regret_match(regret, key, n)` — standard regret matching (positive regrets normalized, otherwise uniform).

**Input/Output.** Input: stack depth, iterations (default 120 000), RNG seed (`random.Random(0)` in `main`).
Output: the JSON table. The payoffs are hard-coded (cfr_preflop.py:60-80): fold → SB −0,5;
jam+fold → SB +1; jam+call → ±S on the showdown, with `w = 1|0.5|0` from a sampled 5-card board.

**Dependencies.** `pokerbot.engine.cards` (make_deck/hand_class/expand_class), `pokerbot.engine.evaluator`,
`preflop_strength` (only for the console output), `pokerbot.config`.

**Status.** Stateless per call; the regret/strategy tables live only inside `solve_stack`.

**Cost.** Not measured. Order of magnitude from the code: 19 depths × 120 000 iterations with one
9-card sample and two evaluator calls each — a one-time offline run, nothing for runtime.

**Measurement status.** MEASURED POSITIVE via the produced table (see `blueprint.py` above: agreement with
published Nash charts). The solver itself has no convergence test of its own in the repo → the
convergence quality is UNMEASURED.

**Usable standalone?** Yes, with your own hand evaluator. It is a clean, short, readable
CFR reference example (98 lines of core logic) — useful even just for learning.

**Pitfalls.** The BB regrets are weighted with the counterfactual reach `sigma_sb[JAM]` (cfr_preflop.py:77-86);
anyone leaving that out in a rebuild gets a plausible-looking but wrong call range.

---

### Preflop strength model — `pokerbot/strategy/preflop_strength.py`

**Purpose.** Delivers for each of the 169 hand classes the all-in equity against a random hand and from it a
combo-weighted percentile — the number on which practically every preflop heuristic of the bot stands.

**Interface.**
- `strength(hc: str) -> float` — equity vs random (0..1).
- `percentile(hc: str) -> float` — share of all combinations this class beats (0..1, higher = stronger).
- `range_top(fraction: float) -> set[str]` — the strongest `fraction` of all hands as a class set.
- `ranked_classes() -> list[str]` — all 169 classes sorted by strength.
- Constants `ALL_CLASSES`, `COMBOS`, `TOTAL_COMBOS` (= 1326).

**Input/Output.** Input: hand-class string, normalized via `normalize_class`. Output: floats or
`set[str]`. Cache: `data/preflop_strength.json` — if the file is missing, it is computed on first call with 4000
MC iterations per class and written (`_compute`, preflop_strength.py:24-30, `random.Random(0)`).

**Dependencies.** `pokerbot.engine.cards`, `pokerbot.engine.equity.equity_vs_class_range`, `pokerbot.config`.

**Status.** Module-global `_strength` / `_percentile`, filled once via `_ensure()`. Stateless from the
caller's point of view; no reset needed.

**Cost.** First call without cache: 169 × 4000 MC draws (not measured, but the reason for the cache).
Then dict lookups.

**Measurement status.** UNMEASURED as its own lever. A known failure case found by the operator is on record:
the hot-and-cold ranking **overrates offsuit aces** — A2o in the CO against an LJ open gets percentile 0,691
and was therefore flatted; the counter-fix (`flat_guard`, in the 6-max core, not here) measures against the old core
+17,7 ± 6,4 / +11,4 ± 6,9 / +19,2 ± 7,0 bb/100 over 2992 paired decks each (docs/STATE.md, block
"6MAX FLAT-FIX", 2026-09-09).

**Usable standalone?** Yes, completely — it only needs an equity calculator. The produced JSON is a
generally useful 169 table.

**Pitfalls.** A percentile from all-in equity vs random is **not playability**. That is exactly the
A2o case documented above: dominated offsuit aces rank high and play badly. Anyone using `range_top()` naively as an
open/call range inherits this error.

---

### HU range definitions — `pokerbot/strategy/ranges.py`

**Purpose.** Defines the heads-up preflop ranges as percentile bands on the strength model and provides the
combination expansion with which every equity calculation in the bot is fed.

**Interface.**
- Constants (ranges.py:16-22): `SB_OPEN_FRAC = 0.84`, `BB_3BET_VALUE_FRAC = 0.13`, `BB_DEFEND_FRAC = 0.66`,
  `SB_4BET_VALUE_FRAC = 0.075`, `SB_CALL_3BET_FRAC = 0.34`, `BB_CALL_4BET_FRAC = 0.06`,
  `BLUFF_BAND = (0.40, 0.60)`.
- Range functions `sb_open()`, `bb_3bet_value()`, `bb_defend()`, `bb_call_open()`, `sb_4bet_value()`,
  `sb_call_3bet()`, `bb_call_4bet()`, `bluff_band()` → each a `set[str]` of hand classes.
- `push_fraction(eff_bb) -> float` / `call_shove_fraction(eff_bb) -> float` — the percentile fallbacks of the
  push-fold layer (steps 0,70/0,55/0,45/0,38/0,30 at ≤6/8/10/12/otherwise bb).
- `combos_for_classes(classes, dead) -> list[tuple[str,str]]` — expands classes to concrete combinations
  and filters dead cards.
- `extracted_ranges()`, `match_grid(keywords, stack_bb)`, `grid_action(grid, hand_class)` — optional
  enrichment from extracted book grids (`knowledge_base/ranges/ranges_grids.json`).

**Input/Output.** In/out are class sets or combination lists `[("As","Kd"), ...]`. `dead` is
a list of card strings (hole + board).

**Dependencies.** `preflop_strength` (hard — all bands are percentiles on it), `pokerbot.engine.cards`,
`pokerbot.config` (only for the grids).

**Status.** Stateless; `_extracted` is a lazy cache.

**Cost.** `combos_for_classes` is O(classes × combinations) with one `sorted()` sort per call and
is called in EVERY preflop equity calculation — not measured separately, but the most frequent call in the preflop path.

**Measurement status.** UNMEASURED as range calibration (the bands are a setting, not a solver result).
MEASURED is a correctness property: the `sorted()` line in `combos_for_classes` (ranges.py:84) fixes a
determinism bug — before the fix, at identical seed in two processes **4 of 140 actions** diverged, because the
iteration over a `set` was PYTHONHASHSEED-dependent (ranges.py:76-81); with `PYTHONHASHSEED=0` it was 0.
The sister version in `engine/equity.py:123-126` cites a second piece of evidence (same seed, three processes →
hero place 378/12/4 in a 600-player MTT).

**Usable standalone?** Yes, provided you take `preflop_strength` along. `combos_for_classes` alone is a useful
30-line building block.

**Pitfalls.** Exactly the fixed bug is the one an outsider reproduces in a rebuild: **never iterate over a
`set` that determines a Monte Carlo order.** Without canonical sorting, paired A/B tests are
worthless, and the error is invisible because every single run looks plausible.

---

### Solver-distilled RFI table — `pokerbot/strategy/preflop_gto.py`

**Purpose.** Lookup of an open/fold decision (RFI, unopened) per position and hand class, distilled from 63k
PokerBench preflop spots.

**Interface.**
- `rfi(pos: str, hand: str, min_n: int = 3) -> dict | None` — record `{action, n, mix, raise_bb?}` or `None`
  if the key is missing or the sample is below `min_n`.
- `_table()` — `lru_cache` loader; missing file → empty dict → all lookups `None`.

**Input/Output.** Key schema exactly `"{pos}|0|none|none|0|{hand}"` (preflop_gto.py:27). Source:
`knowledge_base/ranges/preflop_gto_table.json` (1,1 MB, 17 034 entries; example record
`BB|1|UTG|UTG|2|97s → {"action":"fold","n":3,"mix":{"fold":1.0}}`). `action` is one of
`raise|fold|check|call`.

**Dependencies.** Only `pokerbot.config`. Fully self-contained.

**Status.** Stateless (`lru_cache(maxsize=1)`).

**Cost.** Parse 1,1 MB JSON once, then dict lookup. Not measured.

**Measurement status.** MEASURED against held-out actions: **88,6 % action match** on held-back PokerBench spots
(docstring preflop_gto.py:2-3; confirmed in `docs/archive/BOT_PARTS_CATALOG.md:65`). As an EV lever UNMEASURED —
and the remaining 11,4 % are explicitly marked in the repo as possible high-EV blunders
(`docs/archive/GTO_LEAK_LADDER.md:27`).

**Usable standalone?** Yes, this is the simplest building block here: one JSON and one lookup function.

**Pitfalls.** The module is **NOT wired into the HU bot**. The only caller in the repo is
`pokerbot/arena/sixmax.py:170`, and there only for the profile `tag` and only for the unopened situation; the
positions are first merged via `POS_RFI_BUCKET` (`UTG+1/+2/+3 → UTG`, `LJ → HJ`,
sixmax.py:35). Anyone reading the 88,6 % as "the bot's preflop strategy" is mistaken: `bot.py` uses the
weaker percentile heuristic (`docs/archive/BOT_PARTS_CATALOG.md:27`).

---

### AUSLESE stack (the final, wrapped bot) — `pokerbot/strategy/auslese.py`

**Purpose.** The single source of the composition of the shipped HU bot: it wraps a named chain of
guard wrappers around `PokerBot.decide` and sets the associated import-time flags.

**Interface.**
- `FINAL_STACK = "r8_stack"` (christened `auslese-v5`), `RC_STACK = "r10_stack"` (v10 release candidate),
  `AUSLESE_ENV = {"POKERB_TURN_DEFENSE": "0.07", "POKERB_SLOWPLAY": "0.25"}`,
  `AUSLESE_ENV_RESOLVER_OFF` = the same plus `POKERB_RAISE_NARROW=1.0`.
- `setze_env(resolver_on: bool = False) -> None` — sets the flags via `setdefault`; call **before** the import of
  `pokerbot.strategy.bot`.
- `wickle_decide(pb, stack: str | None = None, kanal: str = "live") -> Callable[[dict], dict]` — returns a
  `decide`-compatible function that preserves the rationale dict and marks a guard intervention with
  `auslese_guard: True` (auslese.py:72-79).

**Input/Output.** Input: a `PokerBot` instance, a stack name, a channel (`"live"` = deadline +
`os.urandom` seed, `"gym"` = deterministic for paired gates). Output: the same dict as `decide()`,
possibly with overridden `action`/`amount`.

**Dependencies.** HARD on `pokerbot.autogym.pargate._wickle` (the stack definitions) and via that on
`pokerbot.autogym.improver` (the individual guards `sel_guard`, `turn_wert_guard`, `button_disziplin_guard`,
`river_wert_bremse`, `river_gpu_guard`). These guards are the actual content and live outside
`strategy/`. Imports are deliberately lazy (auslese.py:29-31).

**Status.** The wrapper holds a `merker` dict for the last base decision (auslese.py:55). It is therefore
**not concurrency-safe** — one wrapper instance per seat/game.

**Cost.** Not measured for the wrappers themselves; the `river_gpu_guard` in v5 solves river subgames on the GPU
(auslese.py:11-13), which dominates the latency of those decisions.

**Measurement status.** MEASURED POSITIVE in the gym mirror, NOT against GTOW: `wert_bremse` replicated 3×
(+8,10 / +8,81 / +7,38, three banks, perm_p 0,0002); `r8_stack` vs `r6_button` 3×30k pooled **+27,6 ± 1,8**
(all p=0,0002); against the frozen base **+30,60 ± 5,03**; A/A exactly 0 (auslese.py:6-10, journal
`R7-REPLIKATION` / `R8-FINALE`). The v4 core against base in the mirror **+16,14 ± 2,77** (auslese.py:16-17).
**Explicitly without an external anchor:** GTOW-confirmed is only v4-on-PRINCE with **−21,1** bb/100;
"v5 (r8_stack) has mirror evidence, no anchor" (docs/STATE.md:52).

**Usable standalone?** No. Without `pokerbot/autogym/` the file is an empty shell — it contains only names
and flags, no strategy.

**Pitfalls.** Two binding rules stand in the docstring and both were bought by measurement: (1) `RAISE_NARROW`
is **contraindicated** with the resolver switched on (v8 finding K3) — that is why `setze_env(resolver_on=True)`
omits the flag; (2) the guards are **HU-only** (2-player state expressions) and must never be wired into the multiway
core (auslese.py:16-18). Plus the logged crash case: `rationale` is a **dict**, not a
string — a concatenation crashes exactly at the guard intervention (auslese.py:76-77).

---

## Opponent and Range Reading

This subsystem answers a single question: *which hands can the opponent hold here, and how often does he do what?*
It consists of three independently usable layers — (a) static preflop priors as class sets, (b) a
per-combo Bayes tracker that reweights the range along the observed betting line, (c) small solver-imitating
MLPs ("advisor") that supply the tracker with the likelihood `P(action | combo)`. Added to that are two opponent models
(aggregate + per-node Dirichlet) and the sizing/texture library that turns a read range into a bet size.

Do you need this? If your bot only computes equity vs random: no, then this is massive overkill. If you feed a solver
(CFR/TexasSolver) at runtime or want to make bluffcatch/thin-value decisions: yes — without a
reconstructed villain range you compute against a fantasy distribution, and exactly that was demonstrably
the cause of a −72-bb/100 run in this repo (`docs/STATE.md:1093`).

Caution up front: almost everything here is **heads-up (2 players)**. The tracker is explicitly HU-only
(`range_tracker.py:19`), the guards above it likewise (`auslese.py:16-17`). For 6-max there is only the much simpler
variant in `pokerbot/arena/sixmax.py`.

---

### Preflop strength model — `pokerbot/strategy/preflop_strength.py`
**Purpose.** Delivers for each of the 169 hand classes the all-in equity vs. a random hand and from it a combo-weighted
percentile, from which "the best X % of all hands" can be formed as a set.

**Interface.**
- `strength(hc: str) -> float` — all-in equity of the class (e.g. `"AKs"`) vs. random, computed/cached from MC.
- `percentile(hc: str) -> float` — 0..1, share of all combos this class beats.
- `range_top(fraction: float) -> set[str]` — the strongest `fraction` of all hands (combo-weighted) as a class set.
- `ranked_classes() -> list[str]` — all 169 classes sorted by strength.

**Input/Output.** Pure strings: class names in the format `"AA" | "AKs" | "AKo"`. Output float or `set[str]`.
The cache lives as `data/preflop_strength.json` (class → equity, 4 decimal places).

**Dependencies.** `pokerbot.engine.cards` (class enumeration/expansion) + `pokerbot.engine.equity`
(`equity_vs_class_range`) — both hard on the first computation, afterwards only the JSON file.
Replaceable: you can replace the JSON with your own equity tables, the format is trivial.

**Status.** Stateless externally; module-wide lazy caches `_strength`/`_percentile` (`preflop_strength.py:20-21`),
filled once per process. Nothing to reset.

**Cost.** Initial computation `_compute(iters=4000)` = 169 × MC(4000) — not measured, but one-off; afterwards
JSON load. Memory: 2 × 169 entries.

**Measurement status.** UNMEASURED as a standalone component (no A/B; it is a definitional basis, not a lever).

**Usable standalone?** Yes, practically dependency-free once `data/preflop_strength.json` is present — otherwise
you additionally need the engine's MC equity calculator.

**Pitfalls.** `range_top(f)` returns the strongest f **combo-weighted**, not f×169 classes; and the order is
*equity vs. random*, not playability. `72o` and `A2o` therefore sit differently than in a real opening range —
exactly there a 6-max opening range stood out in the repo (A2o was classified as a call, percentile 0,691 > 0,665;
commit `468bcc1`).

---

### Preflop range library — `pokerbot/strategy/ranges.py`
**Purpose.** Named HU preflop ranges (SB open, BB defend, 3bet value, …) as class sets plus the canonical
combo expander that all range consumers use.

**Interface.**
- `sb_open() / bb_defend() / bb_3bet_value() / bb_call_open() / sb_4bet_value() / sb_call_3bet() / bb_call_4bet() -> set[str]`
  — each a `range_top(<constant>)` derivation; the constants stand openly at the top of the module (`ranges.py:16-22`).
- `bluff_band() -> set[str]` — medium hands (percentile 0,40–0,60) as polarized 3bet/4bet bluffs.
- `push_fraction(eff_bb) / call_shove_fraction(eff_bb) -> float` — push/fold widths by effective stack.
- `combos_for_classes(classes, dead) -> list[tuple[str,str]]` — expands classes to concrete combos, filters
  dead cards, **sorts the classes** first.
- `extracted_ranges() / match_grid(keywords, stack_bb) / grid_action(grid, hand_class)` — optional matching against
  GTO grids extracted from a book (`ranges_grids.json`); `grid_action` returns `(action, freq)` or `None`
  (= fold in these charts).

**Input/Output.** Class strings in, `set[str]` or combo tuples `("As","Kh")` out. Grids are dicts with the
keys `label`, `villain_action`, `stack_bb`, `pure` (list `{hand, action}`), `mixed` (list
`{hand, actions:[{action, freq}]}`).

**Dependencies.** `preflop_strength` (hard), `engine.cards` (hard), `config.RANGES_DIR` for the grid JSON (soft —
if missing, `extracted_ranges()` returns `[]`).

**Status.** Stateless; one lazy cache `_extracted`.

**Cost.** `combos_for_classes` over an 85 % range = a few hundred to ~1300 tuples; not measured separately.

**Measurement status.** MEASURED POSITIVE (but as a determinism fix, not as an EV lever): the `sorted(classes)` in
`combos_for_classes` is the reason runs are reproducible — before, the combo order depended on the
`PYTHONHASHSEED`, whereby MC equity paired the same RNG draws with different villain combos and
mixed-strategy boundary decisions flipped between identical runs: **4 of 140 actions**, with
`PYTHONHASHSEED=0` 0 diffs (`pokerbot/strategy/ranges.py:77-81`).

**Usable standalone?** Yes. Minimal: `preflop_strength` + `engine.cards`.

**Pitfalls.** The range widths are **HU constants** (`SB_OPEN_FRAC = 0.84`). Anyone using them unchecked for 6-max
reads an MP opening range of ~15–20 % as ~50 % — exactly this error occurred in the PokerSnowie bridge
and was replaced there by a 6-max position prior (CLAUDE.md, pillar 1).

---

### Range tracker (per-combo Bayes) — `pokerbot/strategy/range_tracker.py`
**Purpose.** Reconstructs for BOTH HU seats the range at the current public node by reweighting the preflop prior
along the observed postflop line with `P(observed action | combo)`.

**Interface.**
- `class RangeTracker(advisor=None)` — `advisor` is an object/module with `available(street)`, `p_bet(...)`,
  optionally `p_bet_batch(...)`, `defense_available()`, `p_defense(...)`; `None` → loads `strategy.advisor` lazily and
  degrades to legality-only if torch/model are missing.
- `RangeTracker.build(state) -> RangeTracker` — walks preflop prior + postflop line; defensive (any broken
  history is swallowed, the partial result stands).
- `RangeTracker.range: dict[int, dict[tuple[str,str], float]]` — seat → {combo: weight}, sum 1.
- `RangeTracker.confidence(seat) -> float` in [0.2, 1.0] — `1 − CONF_SLOPE·heur_ratio`, capped at 0,4 if the
  effective combo count (inverse Herfindahl) is < 10.
- `RangeTracker.emit(seat, dead) -> str` — the range as a **class-wise weighted TexasSolver string**
  (`"AQs:0.62,KQo:0.31,…"`, normalized to max=1).
- `weighted_ranges(state, advisor=None) -> (oop_str, ip_str, conf)` — convenience wrapper; OOP = non-button.
- `river_ranges(state) -> (oop_str, ip_str)` — v1 fallback: pure class sets by preflop raise count only.
- Constants: `WEIGHT_FLOOR=1e-6`, `EMIT_FLOOR=1e-4`, `CONF_THRESHOLD=0.5`.

**Input/Output.** Input is a state dict with the load-bearing keys `button` (int), `board` (list of
2-character cards), `history` (list of rows with `player`, `action` ∈ bet/raise/allin/check/call/fold/deal,
`street`, on aggressive rows `to` = **street-cumulative** level), `players` (each `stack`, `committed_total`),
`bb`. Output: combo→weight dict or class string + confidence.

**Dependencies.** `strategy.advisor` (soft — without it every step becomes legality-only, the range stays the
prior), `strategy.ranges` + `preflop_strength` (hard, prior), `engine.cards.hand_class` (hard),
`engine.evaluator.made_class` (only in the RAISE_NARROW path), `strategy.gto_mode.flag` (hard, flag reading).

**Status.** **Per hand/per call**: the tracker has no snapshot API. The only mechanism to get the range at an
earlier point in time is a history cut plus a complete rebuild (`../reports/V10_FACTS.md:137-139`).
Instances are rebuilt in the bot per decision (`bot.py:987`, `bot.py:1005`) — nothing persists, nothing has to be
reset, but there is also no cross-hand adaptation.

**Cost.** MEASURED: a rebuild costs **210 ms cold / 7,2 ms warm** (`../reports/V10_FACTS.md:138-139`). The lion's share
is advisor forward passes; `p_bet` was, before the memoization, **57 % of the `decide()` runtime at 196k calls**
(`pokerbot/strategy/advisor.py:78-80`). Memory: ≤ 1326 floats per seat.

**Measurement status.** MEASURED POSITIVE, with one known breaking point.
- Accuracy against solver truth (held-out): the `P(call)` update **halves the range L1 error** compared to
  doing nothing — flop +59 % / turn +60 % / river +47 % (`docs/STATE.md:1493-1496`, tool `check_range_l1.py`).
- Against the previous heuristic (`_narrow` = "keep top X % by board strength"): its L1 was **0,756 at
  ~0,995 for uniform-random** (i.e. almost worthless), the action-consistent tracker **0,437 = +42 % closer to the
  truth** (flop +51 / turn +44 / river +30) (`docs/STATE.md:1508-1511`).
- End-to-end smoke: on a turn bet-call line OOP shrinks from 658 to 302 effective combos and the confidence
  rises 0,833 → 1,0 (`docs/STATE.md:1497-1498`).
- BREAKING POINT (historical, expensive): because `P(check)=1−P(bet)` was applied multiplicatively per street, the
  range **inverted** towards air after check/check; together with a dead confidence gate (slope 0,5 floors exactly to
  `CONF_THRESHOLD`) the resolver fired in **93 %** of river decisions on a wrong equilibrium —
  documented as **−72 ± 6,70 bb/100 (n=2498)** (`docs/STATE.md:1093`). The remedies are the knobs
  `TRACKER_ALPHA` (damping, champion value 0,5) and `TRACKER_CONF_SLOPE` (0,7) — both in the profile
  (`pokerbot/strategy/gto_mode.py:19-20`).
- `TRACKER_AGGRO_FULL` (fully believe from the 2nd aggressive action of a seat, alpha→1): gates passed,
  paired canary **+20,5 ± 42,5** — shipped (`pokerbot/strategy/gto_mode.py:52`).
- `RAISE_NARROW` (reweighting of the raise range onto the mined GTOW mix): **clearly positive in the Analyzer channel**
  (v3.3 = 19,41 EV loss vs. anchor 24,90, `docs/STATE.md:724-726`) and **replicated 3× in envgate**
  (+16,8 / +13,7 / +9,2, `docs/STATE.md:240`) — **but ONLY resolver-OFF**. With the resolver running the lever is
  **CONTRAINDICATED**: the narrowed villain range poisons the live resolver (v8 finding K3), therefore excluded from the
  product (`pokerbot/strategy/gto_mode.py:61`, `pokerbot/strategy/auslese.py:16-17`).
- `AUDIT_FIX` (counts raise as an aggressive action): **REFUTED** — v3.4 = 27,52 EV loss vs. anchor 24,90
  (+2,62 worse), permanently parked default-OFF (`docs/STATE.md:725-726`).

**Usable standalone?** Yes, with a restriction. Minimally you need: `preflop_strength.json`, `ranges.py`,
`engine.cards`, a state dict in the format above. Without `advisor` it runs, but then makes exclusively
legality-only updates → the range stays the preflop prior and `confidence()` drops to 0,5 (or below the gate
if you turn the slope up). The benefit comes almost entirely from the advisor.

**Pitfalls.** Two, and both bite immediately.
(1) **`emit()` delivers CLASS weights, not combo weights** — although internally it computes per combo. Reason
(verified in the repo): TexasSolver v0.2.0 does not usefully accept per-combo range strings, the strategy dump
comes back empty (`range_tracker.py:375-382`). Anyone feeding the solver `"AsKh:0.6"` silently gets nothing.
(2) **The tracker queries the advisor by POSITION (`IP` iff `seat == button`), but `bot.decide()` by INITIATIVE**
(last preflop raiser) — two different conventions on the same net (`range_tracker.py:179-180` vs.
`../reports/V10_FACTS.md:133-136`). This is known and was tested as an arm (`ADVISOR_ROLE_POS` = 25,05 vs. 24,90 =
neutral, parked, `docs/STATE.md:726-728`) — but anyone wiring the tracker fresh must decide on ONE convention
and carry it through everywhere. Addendum: `_p_call` queries with a **fixed 0,66 pot**, the real bet size is
not passed through (`range_tracker.py:163-169`); the error then deliberately goes towards "too wide" (safe), not
towards "too narrow".

---

### Solver-frequency MLPs ("Advisor") — `pokerbot/strategy/advisor.py`
**Purpose.** Five small MLPs that imitate a solver's frequency decision per hand: `P(bet)` for
flop/turn/river and `(P_fold, P_call, P_raise)` facing a bet — the likelihood backend of the tracker and at the same time
the bet-frequency source of `bot.decide()`.

**Interface.**
- `available(street="flop") -> bool` / `defense_available() -> bool` — whether torch + checkpoint could be loaded.
- `p_bet(hole, board, role, street="flop", pot_type=None) -> float | None` — solver `P(bet)` for exactly this hand
  at this node; `None` = net not available, caller must fall back to the heuristic.
- `p_bet_batch(combos, board, role, street, pot_type=None) -> dict[tuple, float|None]` — one forward pass for many
  combos; shares the memo with `p_bet`.
- `p_defense(hole, board, role, size_faced, street="flop") -> (P_fold, P_call, P_raise) | None` — `size_faced` is
  the bet size as a **pot fraction**.
- `p_defense_batch(combos, board, role, size_faced, street) -> dict[tuple, tuple|None]` — ditto batched.

**Architecture (read, not claimed).** All nets are the same pattern:
`Linear(d,64) → ReLU → Linear(64,64) → ReLU → Linear(64,1) → Sigmoid` for the bet heads (`advisor.py:64-65`),
and `Linear(d,64) → ReLU → Linear(64,64) → ReLU → Linear(64,3)` + softmax for the defense head
(`advisor.py:173-174`). The feature vector (`_vector`, `advisor.py:44-51`): tier one-hot (air/medium/strong, 3) +
texture one-hot (high/low/connected/monotone/paired, 5) + role bit (IP) + 7 bools (flush_draw, backdoor_flush,
nut_flush_blocker, made_straight, oesd, gutshot, has_draw) + `overcards/2` + `strength` (= `1 − treys_rank/7462`)
= 18 dimensions. Defense: + street one-hot (3) + `size_faced` = 22. River line-aware: + pot-type one-hot
(srp/3bet/4bet) = 21. **There is no range, pot, SPR or history information whatsoever in the input**
(`../reports/V10_FACTS.md:131-132`) — that is the hard ceiling of these heads.

**Which heads exist.** `knowledge_base/postflop/`: `advisor.pt` (flop, OOP=donk/IP=cbet), `turn_advisor.pt`
(turn, lead/barrel), `river_advisor.pt`, `river_advisor_la.pt` (line-aware, 21-dim, only with `POKERB_RIVER_LA=1`
AND a passed `pot_type`), `defense_advisor.pt` (3-output, flop+turn+river in ONE net via the street one-hot).

**Training data.** Not from hand histories but from the **TexasSolver cache**: `research/build_advisor_data.py`
reads every solved board node, takes per (board, role, combo) the solver strategy and sums the
BET/RAISE/ALLIN shares to `y = P_bet`; X = the feature vector above. Training in `research/train_advisor.py`
(flop), `train_turn_advisor.py`, `train_river_advisor.py`, `train_defense_advisor.py`, `train_river_la.py`
(river subgame solves per pot type, built by `build_river_la.py`). **Held out BY BOARD** and gated against two
baselines: context-collapsed (mean per texture/size) and strength-only (≈ equity threshold) —
if the net does not beat the strength-only baseline by >3 %, the table is shipped instead of the net
(`research/train_defense_advisor.py:1-8`).

**Input/Output.** `hole` = list of two card strings, `board` = list of 3/4/5 cards, `role` = `"IP"`/`"OOP"`
(**case-sensitive**, `../reports/V10_FACTS.md:130`), `street` ∈ flop/turn/river. Out: float or triple or `None`.

**Dependencies.** `torch` (soft — if missing, all functions return `None`, and the tracker degrades cleanly),
the `.pt` files under `config.KNOWLEDGE_DIR/postflop` (soft, same behavior), `strategy.features`
(hard), `engine.evaluator.evaluate` (hard), `strategy.postflop.classify_board` for the texture (hard, circular
import resolved locally in `_texture`).

**Status.** Stateless in its result, but **module-globally cached**: `_NETS`, `_DEF` (nets), `_PBET_MEMO`,
`_PDEF_MEMO` (120 000 entries each, cleared completely on overflow, `advisor.py:82-84`). Something has to be reset only
if you swap nets or test the batch identity (`advisor._PDEF_MEMO.clear()`, see
`tests/test_hero_range.py:366`). **Important:** `RIVER_LA` is read at **import time** (`advisor.py:28`) —
setting flags after the import has no effect.

**Cost.** MEASURED: `p_bet_batch` = one forward pass, **13/17/27 ms per full range** (flop/turn/river) versus
**61–65 ms** for single calls; `p_defense` single **68–70 ms per full range** (`../reports/V10_FACTS.md:127-129`;
the "NO `p_defense_batch`" noted there is outdated — the batch function exists by now,
`advisor.py:224`). The batch conversion brought **2,2×** in the gate overall (`docs/STATE.md:302`).

**Measurement status.** MIXED, different per head — please read individually:
- Defense advisor (multi-street, held out by board): beats strength-only by **flop +63 % / turn +46 % /
  river +18 %** (gate bar was >+3 %) → PASS (`docs/STATE.md:1490-1491`). MEASURED POSITIVE.
- River advisor: **+51 %** against the frequency baseline → **+38,6 ± 15,6 bb/100** paired floor improvement
  (`docs/STATE.md:1714-1715`). MEASURED POSITIVE.
- Turn advisor (#41): **+8 bb/100, sub-1σ** → kept, but not significant (`docs/STATE.md:1713`). NEUTRAL.
- River blocker signal (#40): **0 effect** (`docs/STATE.md:1713`). NEUTRAL.
- **Defense advisor on the RIVER in the floor: REFUTED** — flop defense lifted the floor −70,7 → **−66,4** (+4,3,
  marginal), adding the river defense pushed it to **−80,6 (−14 worse)**, rolled back to
  flop-only (`docs/STATE.md:1679-1681`). That is why `bot.py:602` has `_def_streets=('flop',)`, while the
  tracker uses `p_defense` on all three streets — this difference is intentional.
- `RIVER_LA` (line-aware river): training good (held-out MSE 0,169 → 0,095 = +44 % vs. frequency baseline,
  1,52 M rows), **effect neutral**: GTOW river-perfect 47,3 → 56,3 % is survivorship-biased, paired
  realized EV **+3,2 ± 5,0 = neutral**; under-betting only half fixed (eq≥0,80 is bet 33 → 47 %)
  (`docs/STATE.md:1094`). Default OFF in HEAD, but `"1"` in the GTO profile (`pokerbot/strategy/gto_mode.py:15`).
- As a serve-time hint to an LLM: **REFUTED/NEUTRAL** — paired A/B n=500/arm, with advisor bet-frequency hint
  **−49,21 ± 29,00** vs. without **−49,52 ± 11,71**, Δ ≈ 0 (`docs/STATE.md:1118`).

**Usable standalone?** Yes, this is the most easily extractable component: `advisor.py` + `features.py` +
a treys evaluator + the five `.pt` files. Without the checkpoints it is an empty shell that returns `None`
everywhere — the `.pt` files are the actual asset and stem from the project's own solver cache.

**Pitfalls.** The feature vector **must match the training script byte-exactly** — order of
`TIERS`/`TEX`/`BOOLS`, `overcards/2`, `strength = 1 − rank/7462`, and for the defense head additionally that the
**texture is computed on the FLOP board** (`board[:3]`), not on the current one (`advisor.py:208`, `:248`). A
swapped one-hot position produces no error, only silent nonsense frequencies. Second pitfall: the
identity guard `research/advisor_batch_check.py:24` calls the role in lowercase (`'ip'/'oop'`), so that
in both arms the role bit is 0 — the IP path is **not covered** by this test (evidence gap,
`../reports/V10_FACTS.md:143-144`).

---
### Hand features (blockers/potential) — `pokerbot/strategy/features.py`
**Purpose.** Converts (hole, board) into the strategically relevant features the advisor nets consume —
so that "55 % equity" is no longer fungible (nut-flush blocker ≠ vulnerable top pair ≠ combo draw).

**Interface.**
- `hand_features(hole, board) -> dict` — postflop only (board ≥ 3). Load-bearing keys: `made` (plain-text name of the
  best five), `tier` ∈ {air, medium, strong}, `made_flush`, `flush_draw`, `backdoor_flush`, `nut_flush_blocker`,
  `made_straight`, `oesd`, `gutshot`, `overcards` (int 0–2), `has_draw`.
- `RANKS = "23456789TJQKA"` — the rank order everything refers to.

**Input/Output.** Cards as 2-character strings; out a flat dict. **A shallow copy is
returned** (`features.py:69`), so that a mutating caller does not poison the cache.

**Dependencies.** `engine.evaluator.best_five_name` (hard, treys). Nothing else.

**Status.** Stateless; two module-global memos: `_STRAIGHT_MEMO` (exact and bounded by the domain — all subsets
of 13 ranks) and `_FEATURES_MEMO` (60 000 entries, cleared completely on overflow).

**Cost.** MEASURED: `_straight_outs` was **30 % of the `decide()` runtime at 10 M generator calls**,
`hand_features` was called **241k× for 70 decisions** (via the tracker's per-combo advisor
queries) — both are the reason for the memoization (`features.py:41-42`, `:58-60`).

**Measurement status.** UNMEASURED as an EV lever (it is a feature definition). MEASURED POSITIVE as a performance fix
within the `decide()` speed-up from 999 → 83 ms (12,1×, CLAUDE.md v3 block, commit `114e107`).

**Usable standalone?** Yes — the cleanest single file of the subsystem, needs only a 7-card evaluator.

**Pitfalls.** `tier` lumps two pair and better into `"strong"` and every single pair into `"medium"` —
so a set on a paired board and a bottom pair are only two steps apart in the one-hot. Anyone retraining the
nets on finer tiers must change `_vector` in `advisor.py` too (the dimension `d` is baked into the
checkpoint).

---

### Aggregate opponent model — `pokerbot/strategy/opponent.py`
**Purpose.** The cheap read over a session: VPIP, fold-to-bet, aggression — with Bayesian shrinkage towards a
prior, so that the first hands do not exploit noise.

**Interface.**
- `class OpponentModel()` — counter object.
- `record(street, action, facing_bet) -> None` — book one observed opponent action.
- `end_hand() -> None` — hand counter.
- `fold_to_bet_freq(k=6) / aggression_freq(k=6) / vpip(k=6) -> float` — shrunk rates
  (`(done + prior·k)/(n + k)`; VPIP prior 0,7 = HU-loose).
- `confidence() -> float` — `min(1, faced_bet/20 + pf_actions/30)`, scales the exploit strength.
- `summary() -> dict` — `{hands, vpip, fold_to_bet, aggression, confidence}`.

**Input/Output.** Only primitives (street name, action string, bool). Out floats or the summary dict.

**Dependencies.** None. Pure stdlib, ~68 lines.

**Status.** **Per session.** All counters live until re-instantiation; there is no `reset()` — anyone changing
opponent builds a new object. In the bot it hangs on `PokerBot.opp` and is fed via `observe_opponent` /
`observe_hand_end` (`../plans/TRAINER_PLAN.md:544`).

**Cost.** Negligible (integer increments).

**Measurement status.** UNMEASURED in isolation. It is the entrance of the exploit path, whose overall verdict stands further below.

**Usable standalone?** Yes, completely; just copy it.

**Pitfalls.** `record()` does not distinguish by street when `facing_bet` is set — preflop folds against
an open land in the same `fold_to_bet` pot as river folds. For a serious HUD statistic that is too coarse.

---

### Per-node Dirichlet opponent model — `pokerbot/strategy/opp_model.py`
**Purpose.** A Dirichlet posterior over the opponent's response (fold/call/raise) to **our** bet, keyed
by a coarse node bucket — the data basis of the exploit path.

**Interface.**
- `size_bucket(frac: float) -> str` — pot fraction → `q|half|twothird|pot|big|over` (bounds `_SIZE_BINS`,
  `opp_model.py:17`); deliberately also catches off-tree sizes between solver nodes.
- `node_key(street, role, line, board_class, size_frac) -> str` — `"street|role|line|board_class|bucket"`.
- `class OppModel(kappa=3.0)` — `observe(key, resp, w=1.0)`, `posterior(key, prior=(0.5,0.4,0.1)) -> ([P_fold,P_call,P_raise], n_eff)`,
  `save(path=None)`, `load(path=None)`.
- `seed_from_fold_curve(model, curve_path=None, street="river", n_eff=30.0) -> int` — seeds the river buckets from
  a measured fold curve `[size, fold_prob, n]` across all board classes/roles; returns the number of seeded
  buckets.

**Input/Output.** Pure strings + floats. Persistence as flat JSON `{node_key: [c_fold, c_call, c_raise]}`
under `data/opp_model.json`. `posterior` returns the posterior **mean** plus `n_eff` = sum of the *observed*
counts (the prior deliberately does not count — `n_eff` is the uncertainty driver of the LCB gate).

**Dependencies.** `pokerbot.config` only for the default paths. Otherwise **pure stdlib, no numpy**.

**Status.** **Per session, optionally persistent.** Counts accumulate across hands; `save()`/`load()` make
the read against static opponents cross-session. Reset = new object or delete the JSON.

**Cost.** Not measured; one dict lookup plus three additions per query.

**Measurement status.** See the joint exploit block below. The module itself has a self-test
(`python -m pokerbot.strategy.opp_model`) that checks cold start = prior and "45 observations → over-folder dominates"
(`opp_model.py:86-97`).

**Usable standalone?** Yes, trivially — 97 lines without real dependencies.

**Pitfalls.** The name clash: there is a **second, completely different `OppModel` class** in
`pokerbot/arena/sixmax.py:274` (a dataclass with VPIP/PFR/3bet counters for the 6-max league). Anyone pulling the wrong
import gets a type error in a completely different place — this is noted in the repo as a known trap
(`../plans/TRAINER_PLAN.md:49`, `:354`).

---

### River exploit engine (LCB gate) — `pokerbot/strategy/exploit_engine.py`
**Purpose.** Chooses on the river the EV-maximal action against the Dirichlet response distribution — but only if a
lower confidence bound over the model uncertainty confirms the gain; otherwise the floor plays.

**Interface.**
- `action_ev(kind, size_frac, eq, pot, resp) -> float` — `EV_check = eq·pot`;
  `EV_bet = f·pot + c·[eq·(pot+bet) − (1−eq)·bet] + r·(−bet)` (a raise is conservatively valued as "we fold").
- `choose_river(cands, floor_idx, eq, pot, eps_frac=0.30, z=0.5) -> (idx, mode, lam, evs)` —
  `cands` is a list `(kind, size_frac, resp|None, n_eff)`; `mode` ∈ `floor|mix|exploit`; `lam` is the
  probability with which the caller actually plays the exploit action.
  Formula: `gain = EV(a*) − EV(floor)`; `LCB = gain − pot·z/√(n_eff+1)`; `LCB ≤ 0` → floor;
  otherwise `lam = min(1, LCB/(eps_frac·pot))`.

**Input/Output.** Only numbers; no cards, no state. That makes the module extremely testable.

**Dependencies.** Only `math`. The caller (`bot.py:1162-1173`) supplies the `resp` triples from `OppModel`.

**Status.** Stateless.

**Cost.** Not measured; O(#candidates).

**Measurement status.** See the exploit block below. The built-in self-test checks the safety property:
cold start (n_eff=0) → floor; confirmed over-folder (n_eff=60) → bluff; well-sampled over-caller (n=250) →
thin value (`exploit_engine.py:44-62`). An independent review confirmed that the layer is constructed **GTO-neutral**
— with thin data it correctly falls back to the floor (`docs/archive/GTO_GAP_REVIEW_2026-06-15.md:218`).

**Usable standalone?** Yes, 62 lines, no dependencies. This is the cleanest "safe exploit" building block here.

**Pitfalls.** `eq` must be the equity **against the calling range**, not against the total range — otherwise
the formula systematically over-value-bets. And `n_eff` must not include the prior, otherwise the gate opens
already at zero observations (`opp_model.posterior` therefore deliberately returns only the observed sum).

---

### ⚠ Exploit path — the joint measurement verdict (opp_model + exploit_engine + adaptive + unified_exploit)
**In short: against a leaky pool the exploit path prints a lot of money; against a near-GTO opponent it is NEUTRAL to
harmful, and the hypothesis that it causes the bot's GTO deviation is REFUTED.** The shipped
champion therefore runs it **off** (`"POKERB_EXPLOIT": "0"`, `pokerbot/strategy/gto_mode.py:13`).

The numbers, individually sourced:
- **REFUTED (the core hypothesis):** exploit-OFF was supposed to lift the GTO score and shrink the frequency difference to GTOW.
  Measured (Analyzer, n=1500, seed 55, vs. HEAD 53,4 % / 19,33 / 54,6 %): **GTO score 49,8 %
  (−3,6pp, worse) · EV loss 17,05 bb/100 (−2,28, better) · freq diff 54,57 % (FLAT, 54,6 → 54,57)** →
  the frequency deviation is **intrinsic to the core** (blueprint + advisors + resolver), not driven by the exploit
  overlay (`docs/STATE.md:977-983`).
- **NEUTRAL in the paired self-play gate:** exploit-OFF vs. ON = **+2,1 ± 3,3 bb/100** (`docs/STATE.md:314`).
- **POSITIVE against the exploitable pool** (that is the flip side, and it is measured): `PokerBot(exploit=ON)`
  beats every league profile, worst case **+1 bb/100** against the strong peer; station +493, maniac +757,
  sticky +393, trappy +161 (`docs/STATE.md:1790-1792`). Older measurement series on the same axis: station +109,
  maniac +224, nit +58, foldy +78, sticky +135, trappy +42; mechanism **+33 against a steep size cliff**
  (`docs/STATE.md:1707-1709`).
- **`AdaptiveExploiter` = over-specialization:** crushes weak opponents hardest (+727/+1275), **but loses −47
  against the strong peer**; cause measured knob by knob: its BASE `decide()` is weaker than that of
  `PokerBot` (−56 with all exploit knobs OFF) — not a mis-tuned gate (`docs/STATE.md:1794-1797`).
- **`unified_exploit.py` (62 book rules → nudges) is DE FACTO DEAD** for the playing bot: reachable only via
  `adaptive.py`, which no app/live path uses (`docs/archive/BOT_PARTS_CATALOG.md:20-25`, `:89`). In any case
  only the 4 rules run whose trigger statistic is measured live (`vpip`, `aggression_freq`, `fold_to_bet`,
  `fold_to_cbet` — `unified_exploit.py:28`), the rest is hard-disabled.

Practical consequence for an outside developer: take `exploit_engine.choose_river` + `opp_model` **if your
target pool is exploitable** (micro cash, freeroll, bots). If you are building against a solver/near-GTO opponent, skip the
layer — there it measurably costs you nothing and measurably gains you nothing, but it produces variance.

---

### Bounded-exploit overlays (reference, largely orphaned) — `adaptive.py`, `unified_exploit.py`, `playbook.py`, `calibration.py`
**Purpose.** The older, second exploit stack: its own bot (`AdaptiveExploiter`) with an online fold curve,
probe controller, knob interface and three directive sources (book rules, LLM playbook, live LLM), which all feed
into the same capped nudge channel `{bluff, value, foldcatch}`.

**Interface (the load-bearing parts).**
- `adaptive.OpponentProfile` — `see_decision(street, la, action)`, `fold_at(size) -> float` (size-bucketed
  fold curve), `aggression()`, `vpip()`, `confidence()`, `summary()`.
- `adaptive.Knobs` (boolean control knobs per exploit dimension), `adaptive.TwoModelGate.knobs(prof) -> Knobs`,
  `adaptive.ProbeController(budget_bb=40, max_frac=0.4, freq=0.12).consider(pot_bb, prof)` — unorthodox test moves
  only on already PREDICTED weakness, sized small, against a hard session risk budget.
- `adaptive.AdaptiveExploiter(hero, seed, iters, knobs).decide(state)`; `observe_opponent`, `observe_hand_end`,
  `set_live_directive(directive)`, `refresh_llm_exploit(coach, context)`.
- `unified_exploit.nudge(stats: dict, postflop: bool, cap=0.2) -> dict` — aggregates the firing book rules to
  `{bluff, value, foldcatch}`, each channel clamped to ±cap; `{}` if nothing fires.
- `playbook.directive_to_nudge(...)` — cold-start prior from an LLM-precomputed profile×spot grid
  (`knowledge_base/exploit/playbook*.jsonl`), fades with growing live confidence.
- `calibration.Calibrator(name, path, half_life=300.0)` — logs every probability PREDICTION we acted on
  against the later OBSERVED outcome; corrects systematic bias **selection-aware**
  (only in the spots where we actually act), recency-weighted, persisted per opponent.

**Input/Output.** `unified_exploit.nudge` takes a flat stat dict (only the measured keys, missing
keys = rule off) and returns channel→delta. Rules come from `knowledge_base/exploit/unified.json` with the
fields `stat`, `condition` (`">0.6"` strings), `delta`, `magnitude` (small/medium/large → 0,10/0,20/0,30),
`confidence`, `spot`.

**Dependencies.** `adaptive` pulls `calibration`, `playbook`, `unified_exploit`, `ranges`, `preflop_strength`,
`engine.equity` — hard. `unified_exploit` and `playbook` need only `config` + their JSON/JSONL (soft: if the
file is missing they return empty).

**Status.** Per session (profiles, probe budget, calibrator). The `ProbeController` has a **stop-loss over the
session** — anyone not rebuilding the object keeps playing with a used-up budget.

**Cost.** Not measured.

**Measurement status.** REFUTED/ORPHANED as a product path (see exploit block above: −47 against the strong peer, base
weaker than `PokerBot`, `unified_exploit` unreachable for the live bot). The conclusion drawn from this analysis
stands verbatim in the repo: the SAFE extras (calibration, playbook cold start, LLM strategist) should be ported onto
the robust `PokerBot` floor, **not the other way round** (`docs/STATE.md:1796-1797`).

**Usable standalone?** `unified_exploit.py` and `calibration.py` yes (small, clearly delimited). `adaptive.py`
(19 KB, its own bot) only if you take its whole substructure along — but then you also take along its measured
weakness.

**Pitfalls.** `unified_exploit._holds` checks `">"` **before** `">="` (`unified_exploit.py:45-51`) — a condition
`">=0.6"` falls into the `">"` branch and `float(">=0.6"[1:])` = `float("=0.6")` raises `ValueError`, so the rule
silently never fires. Anyone writing their own rules with `>=`/`<=` gets no error, only silence.

---

### Postflop: texture, fold models and sizing — `pokerbot/strategy/postflop.py`
**Purpose.** Classifies boards, models the opponent's fold frequency over the bet size and from that chooses the
EV-maximal bluff or value size — including the range-based river sizer.

**Interface.**
- `classify_board(board) -> dict` — flags `paired`, `monotone`, `twotone`, `connected`, `high`, `dynamic`.
- `flop_class(tex) -> str` — mapping to 6 categories: `High_dry|Low_dry|High_dynamic|Low_dynamic|Paired|Monotone`.
- `cbet_policy(board, ip=True) -> (freq, size_frac)` — texture-conditioned flop c-bet from `FLOP_CBET`
  (`postflop.py:100-107`, source `knowledge_base/postflop/openai_strategy.json`); OOP: ~15pp less often, larger.
- `ev_bluff(s, F) -> float` = `F − s·(1−F)`.
- `value_score(s, F, eq) -> float` = `F + (1−F)·(e_call·(1+2s) − s)` with `e_call = max(0.10, eq − 0.25·s)`.
- `class PriorFoldModel(fold_to_bet=0.5, confidence=0.0).fold(street, s)` — GTO indifference `s/(1+s)`, shifted
  by the live read; without `GTO_FOLD_PRIOR` additionally `+0.04` "they fold too much".
- `class LearnedFoldModel(table, min_n=6, max_dist=None)` + `.load(path)` — measured fold rates per (street, size);
  with `max_dist` the learned rate is used ONLY near a measured point, otherwise the GTO prior → the exploit
  stays restricted to proven spots.
- `pick_bluff_size(pot, model, street, hero_committed, hero_stack) -> (to_amount, ev, size_frac)`;
  `pick_value_size(...) -> (to_amount, score, size_frac)`.
- `snap_to_tree(bet_chips, pot, street=None) -> int` — rounds to the GTOW size grid;
  `snap_raise_to_tree(desired_to, call_level, pot, to_call, street) -> int` — raise as an increment above the call,
  as a fraction of the post-call pot.
- `pick_value_size_ecall(pot, hero_committed, hero_stack, hole, board, villain_w, hero_w)` — **river sizer from the
  tracked ranges**: per candidate size villain's CALLING SET is determined exactly (his combos with equity ≥ his
  pot odds `s/(1+2s)` against our perceived range), from which `F` and `e_call` come from the SAME distribution.
- `thin_value_probe(...) -> (to_amount, e_call, call_share, size_frac) | None` — selection gate: at the
  SMALLEST size the calling range is widest; if we do not even beat that, no thin value exists.

**Input/Output.** Chips as int, sizes as pot fraction (float). `villain_w`/`hero_w` are `{combo: weight}` —
exactly the format of `RangeTracker.range`. Outputs are **target amounts** (`to_amount` = street-cumulative),
not increments.

**Dependencies.** `strategy.gto_mode.flag` (hard), `engine.cards.RANK_ORDER` (hard),
`engine.evaluator.evaluate` (hard, only in the eCall path), the range tracker (soft — without it
`pick_value_size_ecall` returns `None` and the caller falls back to `pick_value_size`).

**Status.** Stateless, **but all flags are read at IMPORT time** (`ONTREE`, `GTOW_TREE`,
`RIVER_VALUE_FLOOR_EQ`, `AUDIT_FIX`, `_OVERBET_MENU` — `postflop.py:27,36,44,211,268`). Setting env variables after the
import has no effect; `gto_mode.apply()` must run before.

**Cost.** `_ecall_rows` sorts both ranges once and then answers every equity query in O(log n) via
prefix sums (`postflop.py:298-310`) — river-only, because there exact enumeration is possible. Absolute cost not measured.

**Measurement status.** Partly very well measured:
- **`ONTREE` (bet snap to {0.33, 0.5, 0.75, 1.0, 1.25}): MEASURED POSITIVE/NEUTRAL → default ON.** A/B, 1000
  hands per arm + `duplicate.py`: GTO score 50,7 → **53,1**, EV loss vs. GTO 22,7 → **21,2**, realized EV
  **neutral** (−59,2 vs. −60,6 bb/100, within noise) (`pokerbot/strategy/postflop.py:22-27`; `docs/STATE.md:1085`).
- **River value floor (`POKERB_RIVER_VALUE`): DUAL GATE DISAGREES.** GTOW grade **neutral** (river-perfect
  47,3 → 48,0; mistake+blunder 26,4 → 27,7 = slightly worse), paired realized EV
  **+23,0 ± 11,4 bb/100 vs. GTOBaseline (2σ gain)** → classified as a *validated, bounded exploit*, not
  as a GTO fix (`docs/STATE.md:1093`). Default OFF in HEAD, `0.75` in the GTO profile (`gto_mode.py:14`).
- **`POKERB_RIVER_ECALL` (the range-based river sizer): MEASURED POSITIVE**, paired canary **+133,8 ± 60**,
  i.e. better than 2SE → ON in the champion profile (`pokerbot/strategy/gto_mode.py:48`).
- **Flat thin-value frequency (v3.1): REFUTED.** Analyzer paired **19,76 vs. 17,93** — GTOW does bet 43 %
  of the river pairs, but it **selects which ones**; a flat frequency floor loses
  (`pokerbot/strategy/postflop.py:366-367`). From that arose `thin_value_probe` (selection instead of frequency).
- **`POKERB_OVERBET_MENU` (2,0×/2,5× value arms): Analyzer gain −4,82 ONLY resolver-OFF**, the
  resolver-ON interaction was never tested → excluded from the product (`pokerbot/strategy/gto_mode.py:62`).
- **`AUDIT_FIX` (among others phantom size candidates in the sizer): REFUTED**, v3.4 = 27,52 vs. anchor 24,90
  (+2,62 worse) (`docs/STATE.md:725-726`) — although the individual findings were plausible. Stands as a warning:
  "the 9 bug fixes were behavior-bearing".
- **Two real calculation errors, found and fixed (documented in the code):** (a) `value_score` used to charge our own
  bet only on losses, i.e. refunded it on wins — slope 3e−1 instead of 2e−1, whereby the score in the
  thin-value zone `e_call ∈ (1/3, 1/2)` ROSE with size and favored jams (`postflop.py:138-141`);
  (b) candidate sizes the stack cannot realize all map to the same all-in amount, but were
  scored with their PHANTOM fold rate — the argmax fired all-in bluffs on a fold rate the opponent never
  faces (`postflop.py:206-221`, `:318-323`). The jam candidate has since been capped at 2× pot, because otherwise the
  sizer jammed 3,4× pot independent of hand strength.

**Usable standalone?** Yes, in tiers. `classify_board`/`flop_class`/`cbet_policy`/`ev_bluff`/`value_score`/
`PriorFoldModel`/`LearnedFoldModel`/`snap_to_tree` need only `RANK_ORDER` and a flag stub. The eCall functions
additionally need an evaluator **and** two tracked ranges — without the range tracker they are not usable.

**Pitfalls.** The one everyone fails on: **`pick_value_size_ecall` needs `hero_w` = the OPPONENT's view of OUR
range**, filtered **only by the board**, not by our hole cards. Anyone inserting "our real
hand" or a hole-filtered range here builds in exactly the bias that `_tracked_ranges_both` avoids
(`postflop.py:292-294`, `bot.py:996-999`). Secondly: the function deliberately returns `None` if *nobody*
would call — "everyone folds" is not a value bet, that decision belongs in the bluff path
(`postflop.py:331-334`).

---

### Hero likelihood replay (K1, v10) — `pokerbot/strategy/hero_range.py`
**Purpose.** Reconstructs **our own** public range at the start of the river without ever reading our real hole
cards — so that a solver can be fed a range-consistent hero distribution instead of the
actual hand.

**Interface (selection from ~40 public functions).**
- `rekonstruiere(st0, guards=STANDARD_GUARDS, hero=None, advisor=None) -> K1Rekonstruktion` — the main path.
- `hero_range_river_start(st0, guards=…) -> dict` / `villain_range_river_start(st0, hero=None) -> dict` —
  convenient short forms, return `{combo: weight}`.
- `range_state_river_start(...) -> RangeState` — with provenance fields (`herkunft='k1_likelihood'`,
  `hero_injiziert=False`).
- `knoten_liste(st0, hero) -> list[Knoten]` — the hero decision nodes before the river (public state +
  observed action, both holes as `'??'`).
- `action_likelihoods(st_vor_aktion, seat, guards=…) -> …`, `knoten_modell(zustand, seat, guards=…) -> KnotenModell`
  with `.likelihood(combo, beobachtet) -> float|None`.
- `Konvention(rolle_bet, size_faced, raise_modelliert)`; `K1_KONVENTION` (initiative + real size) vs.
  `TRACKER_PARITAET` (position + fixed 0,66) — with `guards=()` the latter is byte-equal to the tracker hero range.
- `versions_hash(guards, konvention) -> str` — fingerprint for the protocol.

**Model.** `r_river(h) ∝ r_0(h) · M_board(h) · Π_t π_exec(a_t | s_t, h)` over all hero actions before the river.
Three layers: (1) prior + board mask exactly as `RangeTracker`; (2) base likelihood from the same advisor nets
(batched, without side effects on RNG or tracker); (3) the guard transformations as an exact shift of
action mass per combo (e.g. `turn_wert`: `π_exec(b*|h) = π_vor(bet|h) + 1_C(h)·π_vor(check|h)`).

**Input/Output.** A state dict from two possible channels (engine `HeadsUpGame.state()` or adapter
`gtow_to_state`); only the intersection `player/action/street/to` + `deal.street` is used. Out:
`{combo: weight}` or `RangeState`/`K1Rekonstruktion` with protocol.

**Dependencies.** `range_tracker` (hard — prior, board mask, normalization), `advisor` (hard for the
likelihood), `pokerbot.autogym.improver` (hard — `_spot_rng`/`_RANK_ORD` are the reference for bit-exact
guard conditions), `engine.equity.equity_vs_weighted_range`, `strategy.contracts`, `knowledge_base.math.formulas`.
This is the most heavily interlocked file of this subsystem.

**Status.** Per hand; no persistent state. **INVARIANT (binding in the module):** this path NEVER reads hero's
real hole cards; same public history + different hero hand → identical range (secured by test,
`hero_range.py:26-30`).

**Cost.** Expensive. The guard condition `C(h)` is a CPU MC with `iters=160` **per hypothetical combo** — in
live operation the K1 range was measured at **up to 5,7 s** (`../reports/V10_GATES_REPORT.md:181`); that dominates
the 7,5-s deadline there more than the actual solve (`../reports/V10_GATES_REPORT.md:201`).

**Measurement status.** **FAILED (gate G3), built but not accepted.** Measured against an exact policy oracle:
total variation **mean 0,2085 · p95 0,758 · max 0,876** against a budget of **0,02 / 0,05 / 0,10**; even after
subtracting the oracle noise floor (0,095) the lower bound remains at **mean 0,1446** — above all three budgets,
and every guard class individually as well (`../reports/V10_GATES_REPORT.md:21`, `:108`). Additionally a
**support leak**: hero's actual hand lies in **21 of 64** cases outside the K1 support (mass 0), live
`hand_not_in_range` in 4/40 cases (`../reports/V10_GATES_REPORT.md:63`, `:195`). The champion therefore remains
`auslese-v5`; v10 is **not** released (`../reports/V10_GATES_REPORT.md:114`).

**Usable standalone?** Practically no. It hangs on tracker, advisor, the autogym improver and the
contracts dataclasses. As an *idea* (range-consistent hero distribution instead of injected real hand) it is
transferable; as code it is the least extractable part of this catalogue.

**Pitfalls.** The documented main reason for G3: the **advisor backend is not the base policy** that
was actually played (`../reports/V10_GATES_REPORT.md:213`). Anyone building a range from a likelihood reconstruction
must draw the likelihood from the **actually executed** policy — not from a model of it. That is
laid down in the repo as the binding hybrid doctrine (CLAUDE.md, v10 block, rule 3).

---

### 6-max opponent model (the lean variant) — `pokerbot/arena/sixmax.py`
**Purpose.** The counterpart for multi-player tables: per seat a counter object fed exclusively from **public**
actions, plus a capped, confidence-gated read.

**Interface.**
- `class OppModel` (dataclass, `sixmax.py:274`) — fields `hands, vpip, pfr, tb, tb_opp, faced_bet, fold_bet,
  agg, agg_opp`; methods `fold_to_bet()` (only from `faced_bet ≥ 8`, otherwise `None`), `threebet()` (from `tb_opp ≥ 6`),
  `aggression()` (from `agg_opp ≥ 8`).
- `SixMaxBot(seat, knobs, seed=None)` with `self.opp: dict[int, OppModel]`; `new_hand(seats)`;
  `_read(obs) -> dict` — returns capped deltas like `{"cont_bonus": …}` / `{"call_delta": ±0.07}` plus a
  text `tag`; empty dict = just play the profile.

**Input/Output.** `obs` is the engine's seat observation (`board`, `to_call`, `n_active`,
`preflop_raises`). Out a small delta dict.

**Dependencies.** Only the engine observation; no nets, no models.

**Status.** Per session per observed seat; `new_hand(seats)` resets the **hand state** (active seats,
aggressor, street), the counters deliberately stay.

**Cost.** Negligible.

**Measurement status.** UNMEASURED as an isolated lever. The thresholds (`threebet > 0.11`, `aggression > 0.55` /
`< 0.30`) are set as priors, not measured.

**Usable standalone?** Yes — if you are building 6-max and not HU, this is the realistic starting point instead of the
HU tracker.

**Pitfalls.** The minimum-n gates (`≥8`, `≥6`, `≥8`) return `None`, not 0. Anyone not catching that
gets `TypeError` instead of a conservative read. And: the same class is named like
`pokerbot/strategy/opp_model.OppModel` but is something completely different (see there).

---

### Not in this repo: `robustheit.py`
Named in the assignment, but **in `C:\Users\hampe\Desktop\PokerB` no file with `robust` in its name exists except
`research/runpod_solve_robust.sh`** (a shell script for solver runs on the pod, not a strategy module).
A file `strategie/robustheit.py` does not belong to this bot and is therefore not described here.

---

### How the parts hang together in the running bot (wiring map)
Anyone wanting to rebuild this needs the order — it stands like this in `pokerbot/strategy/bot.py`:

1. `bot.decide()` builds a fresh `RangeTracker` when needed (`bot.py:987`, `:1005`) and takes the
   villain range **only** if `confidence(v) ≥ CONF_THRESHOLD` — otherwise `None`, and the floor falls back to the old
   heuristic (`bot.py:977-993`). That is the o3 safety principle: better too wide than wrongly narrow.
2. The bet frequency comes per street from `pf_advisor.p_bet` (flop `bot.py:770-777`, turn `:796-803`,
   river `:826-833` incl. `pot_type` for the line-aware head).
3. On the river `_tracked_ranges_both` pulls **both** ranges from ONE tracker build (`bot.py:996-1013`) and feeds
   with them `postflop.thin_value_probe` (selection gate) and `postflop.pick_value_size_ecall` (size).
4. For the resolver `weighted_ranges(state)` is passed as TexasSolver strings, again confidence-gated
   (`bot.py:1043-1051`, `:1071-1078`, `:1098-1104`).
5. The exploit path (`opp_model.posterior` → `exploit_engine.choose_river`) sits alongside (`bot.py:1162-1173`) —
   but switched off in the shipped profile.

The cheapest sensible excerpt for a foreign bot is items 1+2: tracker + advisor. Item 3 only pays off
once your ranges demonstrably hold — the eCall sizer is only as good as the distribution you give it.

---

## Solver and Re-Solving

This subsystem answers ONE question: "What is, at exactly this postflop node, with exactly these two
ranges, the equilibrium strategy of my hand?" There are two independent compute engines for it — an
external CPU process (TexasSolver, seconds to minutes per solve) and a home-grown tensor CFR+ on the GPU
(river/turn, milliseconds to seconds) — plus the wrappers that translate their answer into a legal engine
action. You need this ONLY if your bot wants more postflop than heuristic/net; a bot with pure
advisor/blueprint postflop runs without a single line of it.

### Call chain and cost at a glance (sources at each module)

| Who calls when | Compute engine | Cost per solve |
|---|---|---|
| `bot.decide` → river, `use_resolver` | TexasSolver (`resolver.river_resolve`) | ~6 s, median 5,8 s (docs/STATE.md:1093); cache hit 0,02–0,03 s |
| `bot.decide` → turn, `use_turn_resolver` | TexasSolver (`resolver.turn_resolve`) | ~6 s/turn decision (../NOTES.md:49-50); census measurement 5,5 s (research/flop_feasibility.py:3) |
| `bot.decide` → flop, `POKERB_FLOP_RESOLVER=1` | TexasSolver (`resolver.flop_resolve`) | 75,4 / 89,3 / 120,9 s (timeout) — NOT live-capable |
| Guard wrapper in the big-pot river | GPU (`gpu_resolver.solve_spots` → `RiverCFRBatch`) | 209 ms/spot (research/policy_oracle.py:26-29) |
| v10 plan, one solve per river street | GPU (`river_plan.loese_plan` → `RiverCFRBatch` B=1) | Live measured 4,3 s first hand (river_plan.py:44-48) |
| Mass audit/batch | GPU (`RiverCFRBatch` B=64..256) | 0,30 s/spot amortized (docs/STATE.md:115-116) |

---

### TexasSolver driver — `pokerbot/strategy/gto_oracle.py`

**Purpose (1 sentence).** Runs the bundled TexasSolver console binary as a subprocess, reads the JSON dump
and delivers the GTO strategy of a postflop node per combo.

**Interface.**
- `available() -> bool` — does the binary exist under `SOLVER_DIR/console_solver.exe`.
- `solve(board, oop_range: str, ip_range: str, pot=20.0, eff_stack=100.0, bets=None, accuracy=0.5,
  max_iter=150, threads=8, allin_threshold=0.67, dump_rounds=2, timeout=180, keep_files=False, tag=None,
  mode='holdem') -> dict` — writes an input file in the TexasSolver grammar (`set_pot` /
  `set_effective_stack` / `set_board` / `set_range_oop` / `set_range_ip` / `set_bet_sizes …` / `build_tree` /
  `start_solve` / `dump_result`), starts `subprocess.run(cwd=SOLVER_DIR, timeout=…)` and returns the
  root node of the dump. `mode='shortdeck'` switches to 6+ Hold'em via CLI flag.
- `strategy_for(node: dict, c1: str, c2: str) -> dict | None` — `{action label: probability}` for a
  concrete hand at the node; `None` if the combo is not in the range/not in the dump.
- `_parse_exploitability(stdout)` (internal, but important) — reads the last exploitability printed by the
  solver and attaches it to the result as `data["_exploitability_pct"]` + `data["_solve_iters"]`.

**Input/Output.** In: board as a list of 2-character cards (`['Qs','Jh','2h']`), ranges as
TexasSolver range STRINGS at the 169-class level (`"AA,KK,AKs,AQs:0.5,…"`), bet tree as a list of finished
`set_bet_sizes` lines. Out: the parsed dump dict; load-bearing keys `strategy.actions` (labels like
`"CHECK"`, `"BET 66"`, `"ALLIN"`), `strategy.strategy` (`{"AsKd": [p1,p2,…]}`), `childrens` (label → child node),
`node_type`, plus our additions `_exploitability_pct`, `_solve_iters`, `_suit_map`.

**Dependencies.** Hard: the binary in `tools/TexasSolver-v0.2.0-Windows` (path overridable via `TEXASSOLVER_DIR`)
and `subprocess`. Soft: `pokerbot.engine.isomorph.canonical_board` — only with
`POKERB_ISO_CACHE=1`. Otherwise only standard library; replaceable by any solver that delivers a
strategy dump (then rebuild the `strategy_for`/`childrens` shape).

**Status.** Stateless per call, BUT with a persistent disk cache: `data/_solve_cache/<sha1>.json`, key =
sha1(board, both range strings, pot, eff, bets, accuracy, max_iter, dump_rounds, mode) — without hole cards,
without history, i.e. ONE solve for all combos and seeds of the same node (`gto_oracle.py:58-62`). The cache
is shared process state: in the repo currently 12.209 files / 35 GB (measured 2026-09-10 via `du`). To
reset: delete the directory or `POKERB_SOLVE_CACHE=0`.

**Cost.** A cold river solve with the census arms ~6 s (docs/STATE.md:1093), turn 5,5 s
(research/flop_feasibility.py:3), flop-to-terminal 75–121 s (data/runs/verdrahtungs_debug_2026-08-17.json).
Cache hit 0,02–0,03 s (same source). Every concurrent solve is its own process with
~400–500 MB RSS (research/mass_solve.py:5-7).

**Measurement status.** MEASURED POSITIVE as a reference: against our independent GPU CFR on an identical river spot
frequency deltas 0,007 / 0,000 / 0,001 and per-combo correlation **0,999** (docs/STATE.md:121-122,
`research/gpu_vs_texassolver.py`). On the turn the same cross-validation only partially: OOP bet delta 0,031,
OOP call delta 0,000, correlation 0,944, but IP bet-after-check 0,416 (our CFR) vs 0,321 (TexasSolver) at
expl≈0 on both sides (../NOTES.md:701-711) — classified as equilibrium SELECTION of two CFR variants, not
as a bug (../NOTES.md:712-726).

**Usable standalone?** Yes, this is the most isolated module of the repo. Minimal: the binary, `board`, two
range strings, `pot`, `eff_stack` — `python -m pokerbot.strategy.gto_oracle` runs a demo (flop QsJh2h).
No bot, no engine needed.

**Pitfalls.** The range strings must be EXPLICIT classes: TexasSolver rejects the offsuit shorthand with `+`
with "format not recognize" — and only AT solve time, after a successful `build_tree`
(research/flop_feasibility.py:24-26). Secondly: `strategy` is only filled per combo at the dumped ROOT node,
deeper nodes carry `"strategy": null` (`gto_oracle.py:164-174`) — anyone choosing `dump_rounds` too small
navigates into an empty dict.

---

### Solver binary — `tools/TexasSolver-v0.2.0-Windows/`

**Purpose (1 sentence).** The bundled OSS postflop solver package (TexasSolver v0.2.0, discounted-CFR class)
that the driver above calls.

**Interface.** `console_solver.exe -i <eingabedatei.txt>` with the working directory in the solver folder;
optionally `--mode shortdeck`. Alongside lie `TexasSolverGui.exe` (unused by the code) and the
subfolders `ranges/`, `parameters/`, `resources/`.

**Input/Output.** In: a text file with one command line per line (grammar in the docstring of
`gto_oracle.py:8-13`). Out: the JSON file written via `dump_result <datei>` + progress lines with
the achieved exploitability on stdout.

**Dependencies.** No Python dependency; the Qt5 DLLs in the folder belong to the GUI, the console binary
runs without them.

**Status.** The folder is the working directory: the driver writes `_oracle_in_<tag>.txt` /
`_oracle_out_<tag>.json` into it and deletes them in a `finally`. Currently 102 orphaned
`_oracle_*` files lie there (measured 2026-09-10) — the result of aborted runs; harmless, but the folder grows.
Total size 163 MB.

**Cost.** See driver. Memory ~400–500 MB per concurrent process (research/mass_solve.py:5-7).

**Measurement status.** MEASURED POSITIVE (cross-validation 0,999, see above). Additionally: the short-deck mode
was verified 2026-06-15 (solve converges, dump parses unchanged through `strategy_for`,
`gto_oracle.py:73-76`).

**Usable standalone?** Yes — it is a self-contained third-party product. Minimal: Windows binary + one
input file. For Linux, `SOLVER_DIR`/`EXE` would have to point to a self-built `console_solver`.

**Pitfalls.** The working directory MUST be the solver folder (relative resource paths). And: the
`timeout` of our driver is NOT in the cache key — a run that hit the timeout dumps nothing, so that
is not a correctness problem, but a cache hit and a cold timeout run yield
DIFFERENT bot actions (resolver strategy vs floor). That is exactly why `POKERB_ISO_CACHE` and
`POKERB_SOLVE_CACHE` are in the config fingerprint (`gto_mode.py:84-87`).

---

### Street resolvers — `pokerbot/strategy/resolver.py`

**Purpose (1 sentence).** Translates the actual public game state into a TexasSolver solve,
navigates the played line in the solved tree and draws the GTO action of our hand.

**Interface.**
- `river_strategy(state, hole, board, pot, eff_stack, oop_str, ip_str, la, acc, iters, timeout) -> dict|None`
  — the DISTRIBUTION at the river node (raw `{Label: p}`), consumes NO random number.
- `river_resolve(..., rng, …) -> (action, amount) | None` — `river_strategy` + exactly one
  `rng.choices`; byte identity to the pre-split version is guarded by `tests/test_river_strategy_identity.py`.
- `turn_resolve(...) -> (action, amount) | None` — solves turn+river to terminal, reads only the turn node.
- `flop_resolve(...) -> (action, amount) | None` — solves flop+turn+river to terminal (no value net).
- Internal but reusable building blocks: `_street_actions(state, street)` (the actions of ONE
  betting round), `_match_label(action, amount, node)` (engine action → nearest solver label),
  `_label_to_action(lbl, la)` (label → engine action + chip amount), `_inject_observed_sizes(...)` (the
  ACTUALLY observed villain size as an additional tree arm), `_prune_degenerate_arms(...)`
  (EVPA-like pruning of arms from 85 % of the remaining stack).

**Input/Output.** In: `state` as an engine dict with `history` (entries `{action, street, player, to|amount}`)
and `board`; `hole` as a 2-list; `pot` = pot at the START OF THE STREET (not the current one!); `eff_stack`;
`oop_str`/`ip_str` as TexasSolver range strings; `la` = the engine's legal-actions dict
(`to_call`, `can_raise`, `is_bet`, `raise_max`). Out: `("bet"|"raise"|"call"|"check"|"fold", amount_or_None)`
or `None` = "play your floor".

**Dependencies.** Hard: `gto_oracle` (the solve) and `gto_mode.flag` (flag reading). The caller
(`bot.py:1037-1117`) supplies the ranges from `range_tracker.weighted_ranges` — replaceable by any source
that delivers two range strings + a confidence; without good ranges the module is demonstrably harmful
(see measurement status).

**Status.** Stateless. The only carried state is the passed `rng` (one sample per call) and
the disk cache in the driver.

**Cost.** River ~6 s, median 5,8 s per decision; with the resolver OFF the same decision costs 83 ms
(../reports/V10_FACTS.md:83-84, reference docs/STATE.md:1000). Turn ~6 s (../NOTES.md:49-50). Flop 75–121 s
(measurement below). Timeouts: census profile river 90 s / turn 150 s / flop 240 s, compact profile 40/60/120 s
(`resolver.py:38-39,52,67-68,78`).

**Measurement status.** Mixed, and that is the most important sentence of this chapter:
- REFUTED in the original configuration: with preflop-only ranges vs GTO Wizard **−72,06 ± 6,70
  bb/100 (n=2498)**, and the floor WITHOUT resolver was at **−70,73 ± 5,83** → statistically identical, the
  resolver was NEUTRAL, the loss lay in the floor (docs/STATE.md:1640-1642). That is the only isolated
  live A/B measurement ON/OFF that exists.
- The ranges were the cause: the range tracker is a prerequisite, not a refinement (../NOTES.md:446-455).
  With tracker ranges the resolver is part of the later live anchors (−19,70 ± 4,37 or, more honestly,
  −30,11 ± 5,51, docs/STATE.md:212-213) — but NOT measured in isolation against OFF.
- Firing rate live: **93 % of river decisions** (../reports/V10_FACTS.md:79) — the resolver IS the
  played river policy, not a rare add-on.
- `flop_resolve`: REFUTED as a live lever. First flight 0 of 3 firings, latency 120,86 s (timeout) / 89,28 s /
  75,38 s, achieved exploitability of the two finished solves 8,47 / 8,67 % of pot (target 0,6 clearly missed);
  the two converged solves nevertheless returned `None`, because hero's real hand (K5o, J8o) was not in the
  emitted 35-class own range (data/runs/verdrahtungs_debug_2026-08-17.json). Independently of that
  already on 2026-07-05: **49/50 timeouts at 300 s** (docs/STATE.md:913).

**Usable standalone?** Partly. `river_strategy`/`river_resolve` need only the driver, two
range strings and a `state` dict with `history`+`board` in our form — `research/smoke_weighted_resolve.py`
shows exactly this minimal call. `_match_label`/`_label_to_action`/`_street_actions` are copyable without
change.

**Pitfalls.** The `pot` parameter is the pot at the START OF THE STREET (`bot.py` computes
`pot − committed_street of both players`), not the current pot; anyone passing the current one solves a
different game and never notices, because `river_resolve` silently returns `None` on errors. Second-biggest trap:
`hand-not-in-range` — the emitted ranges are 169-CLASS strings (`range_tracker.emit`, ../NOTES.md:368-372),
the real hero hand can be missing, and then every A/B arm is byte-equal to the floor, only with a latency tax.

---

### GPU CFR core — `pokerbot/strategy/gpu_cfr.py`

**Purpose (1 sentence).** Solves river and turn subgames as vector CFR+ over dense 1326-combo tensors on the
GPU, in milliseconds instead of seconds.

**Interface.**
- `combo_index(c1, c2) -> int` — canonical index 0..1325 (order irrelevant).
- `range_vector(cw: dict) -> Tensor[1326]` — `{('As','Kd'): weight}` → dense float32 vector on `DEVICE`.
- `showdown_matrix(board) -> (W[1326,1326], M[1326,1326])` — W = sign(score_i − score_j), M = compatibility
  mask (card removal sits exactly in M).
- `build_river_tree(pot, eff_stack, bet_sizes=(0.35,0.75,1.5), raise_sizes=(2.7,), max_raises=2,
  invest0=(0,0)) -> Node` and `build_turn_tree(...)` — HU trees, OOP acts first.
- `class RiverCFR(board, r_oop, r_ip, pot, eff_stack, **baum_kw)` with `solve(iters=400)`,
  `avg_sigma(node) -> [1326, n_acts]`, `exploitability() -> float` (exact best response, in % of pot),
  `strategy_at_root() -> {act: Tensor}`.
- `class RiverCFRBatch(boards, r_oop[B,1326], r_ip[B,1326], pot, eff_stack, half=False, **baum_kw)` —
  B subgames simultaneously, same tree GEOMETRY, free boards/ranges; additionally
  `action_values(node, reach_opp, spieler) -> [B,1326,n_acts]` (EV per action, both sides play the
  average strategy).
- `class TurnCFR(board4, r_oop, r_ip, pot, eff_stack, **baum_kw)` — turn betting + chance node + the 48
  river runouts as a batch dimension.
- `Node` with `actor` (0=OOP, 1=IP, −1=terminal), `acts` (labels like `"check"`, `"bet0.75"`, `"raise2.7"`,
  `"betjam"`), `kids`, `pot`, `invest` (chips per role since subgame start), `terminal`.

**Input/Output.** In: board as a card list, ranges as `[1326]` or `[B,1326]` float32 tensors
(NOT normalized — normalization happens internally via the mask), pot/stack as chips. Out: per node a
`[1326, n_acts]` matrix of probabilities; exploitability as a percentage of the pot.

**Dependencies.** Hard: `torch` and `pokerbot.engine.gpu_eval` (`DEVICE`, `encode`, `score7` — the
vectorized 7-card evaluator, order-verified against the CPU reference). `DEVICE` automatically falls
back to CPU if no CUDA is present (`gpu_eval.py:32`) — then everything runs, only slowly. Otherwise nothing:
no bot, no engine states.

**Status.** Per instance: the regret and strategy-sum tensors at every node. One instance = ONE subgame
(or one batch); to "reset" you throw it away and build a new one. `solve()` is cumulative —
calling it twice continues the iteration.

**Cost.** `RiverCFRBatch` B=256: 100 % GPU utilization, ~1000 subgame iterations/s, **0,30 s/spot
amortized** (docs/STATE.md:115-116, RTX 3080 Ti). Measured via `solve_spots` 209 ms/spot at
max_batch=192, 215 ms at 64 — bandwidth-bound, the batch size brings hardly anything
(research/policy_oracle.py:26-29). Memory: W and M are `[1326,1326]` float32 per board (≈14 MB per pair),
i.e. linear in B — measured 5,3 GB peak at B=192, 2,7 GB at B=64 (research/policy_oracle.py:36-38).
`half=True` (fp16 for W/M, {−1,0,1} exactly representable) measures **+64 %** throughput at identical
exploitability, but is default OFF (gpu_cfr.py:271-274, docs/STATE.md:148).

**Measurement status.** MEASURED POSITIVE (correctness, not bb): (1) clairvoyance toy with closed-form solution
hit exactly — bluff share 0,333 (target 1/3), call frequency 0,500 (target 1/2), exploitability 0,014 % of
pot (docs/STATE.md:114-115, reproducible with `python -m pokerbot.strategy.gpu_cfr`); (2) cross-validation
against TexasSolver on an identical river spot: correlation 0,999, deltas ≤0,007 (docs/STATE.md:121-122);
(3) batch-vs-single `max|dSigma|` in the self-test ~1e-7 (gpu_cfr.py benchmark output). Turn tier:
PARTIAL — correlation 0,944, but an IP frequency difference of 0,095 (../NOTES.md:701-711), explained as
polytope selection (../NOTES.md:712-726), not proven as an error.

**Usable standalone?** Yes, this is, next to `gto_oracle`, the second cleanly isolated building block. Minimal:
`torch` + `pokerbot/engine/gpu_eval.py` + `gpu_cfr.py`. The built-in self-test runs without the rest
of the repo.

**Pitfalls.** `avg_sigma` returns at reach 0 a UNIFORM distribution 1/n — that is not a strategy
but the absence of a strategy. Anyone reading it as a policy plays, at exactly the nodes where
their own range does not contain the hand at all, uniformly distributed nonsense. The repo has a dedicated
contract for that (`contracts.PolicyTable.undefiniert`, docs/V10_FAKTEN B10) and a fallback status
`hand_not_in_range`.

---

### GPU river resolver — `pokerbot/strategy/gpu_resolver.py`

**Purpose (1 sentence).** Packages `RiverCFRBatch` into a usable resolver: freeze ranges at the start of the river,
batch spots by tree geometry, navigate the played sequence in the solved tree, output hero's
strategy at the query node.

**Interface.**
- `class RiverSpot(board, hero_w, vill_w, pot_river, eff_stack, hero_oop, seq, hero_hole, tag=None)` —
  `seq` is a list `(wer, kind, size_chips)` with `wer ∈ {'hero','vill'}` and
  `kind ∈ {'check','bet','raise','call','fold'}`; the LAST sequence action is the decision to be
  checked, navigation goes up to just before it.
- `solve_spots(spots, iters=300, max_batch=192, mit_evs=False, **baum_kw) -> list[dict|None]` — per spot
  `{'acts': [...], 'sigma': [...], 'zusatz_norm': [...], 'expl': float, 'gespielt': kind, 'tag': …}`,
  optionally `'ev_je_akt'`. `None` = navigation or combo failed.
- `spr_bucket(spr) -> float` — the geometry grouping (SPR buckets 0.25 … 10.0, `POT_NORM = 100`).
- Constants as knobs: `HERO_MIN_GEWICHT = 0.02`, `DEFAULT_ITERS = 300`, `SPR_BUCKETS`.

**Input/Output.** In: ranges as `{('As','Kd'): weight}` dicts (not as strings — unlike the
TexasSolver path, here there is NO 169-class aliasing). Out: the strategy at hero's query node plus
`zusatz_norm` = the additional investment per arm in POT_NORM units; the real chip amount is
`zusatz_norm/100 * pot_river`.

**Dependencies.** Hard: `gpu_cfr` (and thus torch). Otherwise nothing — the caller supplies the ranges.

**Status.** Stateless; every `solve_spots` call builds fresh CFR instances.

**Cost.** 209 ms/spot (max_batch=192) or 215 ms (64); VRAM 5,3 GB or 2,7 GB
(research/policy_oracle.py:26-29,36-38). Beware of scaling: because `_injiziere` puts every hero combo with its own
weight into the range, EVERY combo gets its OWN solve — 1081 combos ≈ 226 s per node
(same source). That is exactly the trap that left a v10 build agent hanging for 45 min
(journal V10-BAU-NEUSTART).

**Measurement status.** MEASURED POSITIVE as a tool: solves and navigates 571 of 571 river decisions of a
real GTOW night (docs/STATE.md:119-120); self-test checks sigma sum = 1. As a STRATEGY source only
indirectly measured — the bb numbers hang on the guards below.

**Usable standalone?** Yes, with `gpu_cfr`. `python -m pokerbot.strategy.gpu_resolver` runs a
synthetic spot through. You only have to translate your own history into the `seq` format.

**Pitfalls.** The hero injection (`HERO_MIN_GEWICHT = 0.02`) does solve the
`hand-not-in-range` problem of the TexasSolver path, but makes the range HAND-DEPENDENT — the solved spot
is no longer the same for all combos. That is the reason why the v10 plan (`river_plan.py`) deliberately
BYPASSES the `gpu_resolver` and uses `RiverCFRBatch` directly.

---

### River GPU guards — `pokerbot/autogym/improver.py` (`river_gpu_guard`, `river_play_guard`, `_river_spot_und_frage`)

**Purpose (1 sentence).** The two wrappers that actually hook the GPU solver into the played policy —
once as conservative surgery (override only clear errors), once as full play of the solved
policy.

**Interface.**
- `_river_spot_und_frage(st, frage_kind) -> (RiverSpot, pot_river) | None` — cuts the history at the
  river deal, builds both ranges from it via `RangeTracker().build`, translates the river actions into
  additional amounts. That is the reusable substructure.
- `river_gpu_guard(make_strat, min_pot_chips=3000, iters=150, p_max_basis=0.10, p_min_alt=0.70)` — a
  factory decorator: from `make_strat(seat) -> (st) -> (action, amount)` comes the same signature, but on the
  river with pot ≥ `min_pot_chips` the base action is overridden if the solver gives it
  p < 0,10 AND an alternative has p > 0,70. Deterministic, no RNG.
- `river_play_guard(make_strat, min_pot_chips=3000, iters=150, half=False)` — plays in the same spots the
  SOLVED mix, sampled via a `crc32` hash of the SITUATION (cards/board/pot/history length), so that
  paired A/B runs remain reproducible.

**Input/Output.** In/out: the gym state dict (`street`, `pot`, `current_bet`, `to_act`, `button`,
`players[].{stack, committed_street, hole, all_in}`, `history`, `board`) → `(action, amount)`, where `amount`
follows the engine convention "raise-TO level".

**Dependencies.** Hard: `gpu_resolver.solve_spots`, `range_tracker.RangeTracker`, the gym state format.
HU-ONLY — the state expressions are two-player (`auslese.py:17-18`).

**Status.** Stateless per decision (the range tracker is rebuilt from the history per call — that
costs, but buys determinism).

**Cost.** One solve per firing decision, i.e. ~0,2 s GPU plus tracker reconstruction. The live smoke
measures 13,5 s river cold start, because there TexasSolver resolver AND GPU guard run simultaneously
("double resolver", docs/STATE.md:146-147).

**Measurement status.**
- `river_gpu_guard`: **MEASURED POSITIVE, replicated three times.** The stack `r8_stack` with this guard against
  its predecessor: +29,92 ± 3,10 / +23,76 ± 3,07 / +29,23 ± 3,03 bb/100 (30k paired decks each, three
  disjoint banks, all perm_p 0,0002; pooled +27,6 ± 1,8), against the frozen base +30,60 ± 5,03;
  A/A exactly 0 (`pokerbot/strategy/auslese.py:7-10`, journal `TAUFE-AUSLESE-V5`). Caution: that is the
  MIRROR channel (self-play against its own predecessor), not a GTOW anchor.
- `river_play_guard`: **REFUTED/NEUTRAL — dropped.** play vs v5 +1,14 ± 2,78 (30k), the full v8 arm
  +3,91 ± 2,85 or −1,23 ± 4,36, pooled ~+2,3 ± 2,4 = NEUTRAL; post-mortem `../reports/V8_POSTMORTEM.md`:
  channel saturation (the surgery had already harvested the clear cases), the rest lies in indifference zones
  (docs/STATE.md:96-104).
- The thresholds 0,10/0,70 are not guessed: the GPU audit over 571 river decisions found
  check/fold solver-conformant (p 0,86 / 0,83), **bet as the weakest class (p 0,45, 15 % clear
  contradictions)**, and the disaster calls get solver-fold p > 0,95 (docs/STATE.md:123-125).

**Usable standalone?** Only with our range tracker and our state format. The IDEA is portable and
cheap to rebuild; the code itself is not.

**Pitfalls.** Legality. The 30k mirror found exactly here the crash "Cannot bet/raise": the solver branch
says "raise", but the engine does not allow it (opponent all-in or stack ≤ to_call) — `river_play_guard`
checks that explicitly (`opp['all_in']`, `me['stack'] > to_call`) and otherwise falls to the passive branch.
Anyone rebuilding the guard and leaving out this check gets crashes in rare spots.

---

### Turn GPU guard — `pokerbot/autogym/turn_gpu.py`

**Purpose (1 sentence).** The same surgery pattern on the turn, with `TurnCFR` (turn betting + 48 river runouts).

**Interface.** `turn_gpu_guard(make_strat, min_pot_chips=3000, iters=120, …)` — factory decorator as
above; `_turn_seq(hist_nach_deal, hero_seat)` and `_navigiere_turn(cfr, seq, skala)` are the turn variants
of the sequence translation and tree navigation. Tree deliberately small: `TURN_BETS=(0.75,)`,
`RAISE_SIZES=(2.7,)`, `MAX_RAISES=1`, river only 0,75 bet without raise.

**Input/Output.** As the river guard; `_turn_seq` returns `None` as soon as a further deal is in the
history (the guard never fires after the river deal).

**Dependencies.** Hard: `gpu_cfr.TurnCFR`, `gpu_resolver.POT_NORM` and `gpu_resolver._injiziere`
(hero injection). HU-only.

**Status.** Stateless.

**Cost.** Not separately documented as a number in the repo; the docstring names the 48-runout batch as the
cost driver and the self-test measures cold+warm (`python -m pokerbot.autogym.turn_gpu`).

**Measurement status.** REFUTED/too quiet: **fired 3 of 3904 decisions** — the channel is too thin for a
verdict (docs/STATE.md:105-106, "turn_gpu 3/3904 zu leise"). The underlying `TurnCFR` mathematics is
only partially cross-validated (correlation 0,944, IP frequency difference left open, ../NOTES.md:701-726).

**Usable standalone?** Yes in the same sense as the river guard (self-test present), but without
measured benefit.

**Pitfalls.** The threshold `min_pot_chips=3000` on the TURN hits almost nothing — anyone adopting the pattern
must measure the firing rate FIRST, otherwise they measure their base 3900 times and noise once.

---

### Public river plan (v10 K2) — `pokerbot/autogym/river_plan.py`

**Purpose (1 sentence).** Replaces the per-decision, hand-dependent surgery with ONE solve per river
street with public (hole-free) activation and private randomization.

**Interface.**
- `ist_aktiviert(st, min_pot_chips=1500) -> (bool, pot_river)` — the public gate decision, reads
  NO hole cards.
- `loese_plan(st, hero_seat, hand_adresse, iters=150, …) -> GeloesterPlan` — the one solve at the start of the river
  (`RiverCFRBatch` B=1, real eff stack, NO SPR bucket, no hero injection).
- `GeloesterPlan.verteilung(pfad, hole) -> (pfad, probs|None, labels)`, `.tabelle(pfad) -> PolicyTable`,
  `.im_support(hole) -> bool`.
- `navigiere(gp, st) -> Navigation` — exact chip comparison with `OFFTREE_TOLERANZ_CHIPS = 1`, NO silent
  snapping; off-tree → fallback.
- `class RiverPlanFabrik(make_strat, min_pot_chips, iters, …)` — the actual wrapper, with
  `aufwaermen()` (pull the CUDA cold start of 2–3 s forward), `statistik(seat)`, `letzter_trace(seat)`.
- Constants: `BAUM_KW` (bet 0,35/0,75/1,5 + raise 2,7x + jam, max 2 raises), `DEFAULT_MIN_POT_CHIPS = 1500`,
  `DEFAULT_ITERS = 150`, `LIVE_SOLVE_WORKER = 3`, `QUEUE_BUDGET_S = 3.0`.

**Input/Output.** In: gym/live state dict. Out: `(action, amount)` plus a
`contracts.EntscheidungsTrace` per decision with status (`offtree`, `deadline`, `hand_not_in_range`,
`deadline_in_queue`, …) and time attribution (`zeiten_ms.queue/ranges/solve/gesamt`).

**Dependencies.** Hard: `gpu_cfr` (directly, NOT via `gpu_resolver`), `pokerbot.strategy.contracts`,
optionally `pokerbot.strategy.hero_range` (K1) for the hero range, otherwise the range tracker.

**Status.** Per hand and seat: a plan cache (`CACHE_GROESSE = 16`), one running solve per hand
(`_LaufenderSolve`), a private seed (gym: deterministic from `hand_adresse`; live: `os.urandom`).
Reset = new `RiverPlanFabrik`.

**Cost.** Live measured (RTX 3080 Ti, 4 parallel hands): with 8 solve threads 19,6 s/hand and 0/4 plans
in time, with 1 thread 4,3 s for the first hand and the rest in the queue (river_plan.py:44-48) — the
solves serialize on the GIL. Final configuration after the gate fix: 3 threads, 3 s queue budget, 12 s deadline;
re-measurement n=40 plan pots: deadline 0/40, plan played 25/40, offtree 11/40, hand_not_in_range 4/40,
p99 10,15 s (docs/STATE.md:95-96).

**Measurement status.** NEUTRAL in the mirror, but **rejected** as a release. G5: r10 vs r8 on 1968 paired decks
**+11,68 ± 10,85 bb/100**, CI95 [−9,39, +33,06], perm_p 0,156 = NEUTRAL (../reports/V10_GATES_REPORT.md:23).
G4 (exact best response against the fixed policy, 11 holdout roots): the plan is less exploitable in 11/11
roots, ΔE_H −113,0 ± 18,6 bb/100 — but in the GYM channel, not transferable live
(../reports/V10_GATES_REPORT.md:22,39). **G3 FAILED** (K1 hero range TV 0,2085 instead of ≤0,02) → ship decision
"NOT GTOW-ready" (../reports/V10_GATES_REPORT.md:21,89). And the hard finding: all three decks ≤ −100 bb
arose in the FALLBACK to the naked base, not in the plan (docs/STATE.md:84-86).

**Usable standalone?** Practically no — the module hangs on `contracts.py` (42 KB of contracts), on the range tracker
and on the state format. What an outsider should take along are the two design rules: public gating
and one solve per street instead of per decision.

**Pitfalls.** The fallback is the most dangerous part, not the plan: anyone who on off-tree/deadline falls back to a
DIFFERENT policy than the one from whose range the plan was computed plays a mixed policy that
nobody has evaluated — exactly that is where the only catastrophe decks came from.

---

### Cross-validation — `research/gpu_vs_texassolver.py`, `research/gpu_vs_texassolver_turn.py`

**Purpose (1 sentence).** Puts both solvers on the same spot with FORCED identical tree geometry and
compares frequencies and per-combo policy.

**Interface.** Both are scripts with `main()`: `python -m research.gpu_vs_texassolver` or
`…_turn`. Constants at the top of the file: `BOARD`/`BOARD4`, `OOP_CLASSES`, `IP_CLASSES`, `POT=100`, `EFF=75`.

**Input/Output.** In: the constants. Out: console output with OOP bet frequency, IP bet-after-check,
OOP call-vs-bet per solver, the three deltas, the per-combo correlation and a PASSED/NOT verdict at
delta < 0,05.

**Dependencies.** Hard: both solvers (`gto_oracle` + `gpu_cfr`) and `strategy.ranges.combos_for_classes`.

**Status.** Stateless.

**Cost.** One GPU solve (600 iterations) + one TexasSolver solve (accuracy 0.1, 400 iterations,
timeout 300 s).

**Measurement status.** MEASURED POSITIVE (river): deltas 0,007 / 0,000 / 0,001, correlation 0,999
(docs/STATE.md:121-122). PARTIAL (turn): OOP delta 0,031, call delta 0,000, correlation 0,944, IP bet
0,416 vs 0,321 (../NOTES.md:701-711).

**Usable standalone?** Yes — it is the cheapest way to check a self-built CFR against an independent
reference. The trick is copyable: `eff_stack = 0,75 · Pot` makes bet size and
jam collapse to the same single arm in BOTH solvers, whereby the trees are provably identical.

**Pitfalls.** A frequency delta is not proof of error. Two highly converged solvers of the same
zero-sum game have the same VALUE, but may play different frequencies at indifferent nodes
(Nash polytope). The exact discriminator stands in ../NOTES.md:708-710: load the strategy of one solver into the
tree of the other and measure its exploitability THERE — ~0 means multiplicity, large means tree bug.

---

### Exact best-response test bench — `research/river_br_pruefstand.py`, `research/policy_oracle.py`, `research/k3_roots.py`

**Purpose (1 sentence).** Evaluates two hero policies in the SAME river root game with an exact
villain best response — the only method in the repo that measures exploitability instead of counting bb.

**Interface.**
- `k3_roots` — extracts per source hand exactly one root (start of the river) from the GTOW hand histories, including
  geometry, live-faithful engine state and both ranges; splits `holdout` / `entwicklung`.
- `policy_oracle` — delivers the DISTRIBUTION of the actually executed bot policy per hero combo at a
  node as `contracts.PolicyTable`, by decomposing the stack analytically (base `decide()` over S seeds +
  the guard rule as a pure function of the solver result).
- `river_br_pruefstand` — `br_gegen_fest` (exact villain BR against a fixed hero policy,
  information-set-faithful), game-value bracket [L,U], local regret from `RiverCFRBatch.action_values`.

**Input/Output.** In: hand-history JSONL + an arm name. Out: JSON with ΔE_H (bb/root and bb/100), ΔR,
bootstrap upper bounds, UNSUPPORTED counters.

**Dependencies.** Hard: `gpu_cfr`, `contracts`, `range_tracker`, the bot itself (for arm A). Very tightly bound to
our repo.

**Status.** Cache per (root_hash, knoten_hash, kanal, S, stack, code fingerprint) under
`data/runs/v10/policy_oracle_cache/`.

**Cost.** ~0,21 s GPU per combo; a full node with 1081 combos ≈ 226 s; the full holdout (224 roots)
≈ 33 h cold (research/policy_oracle.py:26-31, ../reports/V10_GATES_REPORT.md:39).

**Measurement status.** MEASURED POSITIVE as a tool: controls 15/15 green (matching pennies, card fixture
≤1e-6, A/A exactly 0, oracle identity 60/60 against the direct `decide()` of the full chain,
../reports/V10_GATES_REPORT.md:18). As a measurement channel still INCOMPLETE (11 instead of 20 roots, gym channel only).

**Usable standalone?** No. But the PRINCIPLE is the most important import of this chapter: an exact BR against
one's own fixed policy is cheaper and sharper than any bb mirror — it needs no opponent.

**Pitfalls.** Tree closure. If arm A plays sizes that do not exist in the evaluation tree,
they must NOT be projected onto the nearest arm (a review found 8 % of pot projection error: 0,67 pot
became 0,75). The test bench instead inserts the exact arm-A amounts as additional arms and
otherwise marks the root as UNSUPPORTED.

---

### Solver audit and feasibility measurement — `research/gpu_river_audit.py`, `research/flop_feasibility.py`

**Purpose (1 sentence).** Two one-off tools: one grades every played river decision against the
GPU solver, the other measures whether a flop solve is affordable at all.

**Interface.** Both scripts (`python -m research.gpu_river_audit`,
`python -m research.flop_feasibility`). `gpu_river_audit` reads the hand histories, builds a `RiverSpot` per hero river
action, batches by geometry and outputs (1) the distribution of p(played action), (2) the clear
deviations (p_played < 0,10 with alternative > 0,70) with hand IDs and real outcome.
`flop_feasibility` times ~50 REAL flop spots from the session logs with a lean 3-street tree.

**Input/Output.** In: `data/sessions/gtow_hands_*.jsonl`. Out: console/JSON statistics.

**Dependencies.** `gpu_resolver` + `range_tracker` or `gto_oracle`; plus the replay helpers
(`research/gtow_tree_census.py`, `research/hh_luecken_mine.py`).

**Status.** Stateless (the solve cache takes effect).

**Cost.** Audit: 571 spots, GPU-saturated, per the docstring $0 and deterministic.
Feasibility measurement: up to 50 × 300 s.

**Measurement status.** Both MEASURED and with consequence: audit → 571/571 graded, check p 0,86 / fold p 0,83 /
**bet p 0,45 with 15 % clear contradictions**, disaster calls solver-fold p > 0,95 (docs/STATE.md:123-125) —
from that arose the guard thresholds. Feasibility → **NO-GO: 49/50 timeouts at 300 s**
(docs/STATE.md:913), later independently confirmed by the 0/3 firing rate of the built `flop_resolve`.

**Usable standalone?** Only with our logs. The pattern ("grade every real decision against an
independent solver before you build a rule") is the actual value.

**Pitfalls.** The audit grades against a solver fed with RECONSTRUCTED ranges — a
contradiction can be a policy error OR a range error. The repo lost a candidate on exactly that
(r6_ecall).

---

### Mass solve — `research/mass_solve.py`

**Purpose (1 sentence).** Runs random boards through TexasSolver in the background and thereby fills the
disk solve cache (and a distillation dataset).

**Interface.** `python -m research.mass_solve [minuten] [max_workers] [threads_je_solve] [min_free_mb]
[mb_je_solve]`.

**Input/Output.** In: runtime + resource limits. Out: per board one atomically written
JSON file in the cache; already cached boards are skipped, abort/restart loses nothing.

**Dependencies.** Hard: `gto_oracle` + the binary; `pokerbot.benchmark.gto_benchmark._IP/_OOP` for the
ranges.

**Status.** Writes into the shared disk cache.

**Cost.** RAM-adaptive: every concurrent solve is its own process with ~400–500 MB; the script measures
the free memory per round and runs only as many parallel solves as fit above a safety threshold
(mass_solve.py:5-9). On a 16-GB box RAM, not CPU, is the binding limit.

**Measurement status.** UNMEASURED as an EV lever. Documented is only the side effect: the cache in the repo comprises
12.209 entries / 35 GB (measured 2026-09-10), and cache hits push a 6-s solve down to 0,02–0,03 s
(data/runs/verdrahtungs_debug_2026-08-17.json).

**Usable standalone?** Yes, it needs only the driver and the binary.

**Pitfalls.** CPU mass solve and a GPU training job must not run on the same machine — the
CPU job starves the GPU job (CLAUDE.md "Heavy compute", mass_solve.py:2-3). And: the cache grows
without bound; 35 GB for 12k nodes is ~3 MB per solve.

---

**Delimitation.** `pokerbot/strategy/deep_cfr.py`, `deep_cfr_hunl.py`, `deepstack_leduc.py` and
`cfr_preflop.py` lie in the same directory but do NOT belong to this subsystem: those are
self-play/net learners or a preflop CFR, not re-solving at decision time. `pokerbot/brain/api.py`
contains with `solve_node`/`_run_solve` a second, independent call path into the same
TexasSolver driver (for the LLM path, with its own uuid tag against file collisions in parallel solves).

---

## AUSLESE Guard Chain

The guard chain is a collection of **decorators around a finished poker strategy**: each guard takes a
strategy factory, fetches the base decision and may override it in exactly ONE narrowly delimited node
(e.g. "river bet with a medium-strength hand becomes check"). You need the subsystem if you want to improve an existing bot logic
step by step and **measurably** without touching its source code — not if you build a strategy from
scratch. The actual value lies less in the code (each guard is 20–60 lines) than in the measurements: eleven
of the guards described here are measured NEUTRAL or REFUTED, only four are in the shipped stack.

**Common contract (all guards, without exception).**
Signature: `guard(make_strat, **schwellen) -> make(seat) -> decide(st) -> (action, amount)`.
`make_strat` is a factory `seat:int -> callable(st)->(action, amount)`; the guard builds its base with
`base = make_strat(seat)`, in `decide` **always first** calls `a, amt = base(st)` and then decides whether it
overrides. Actions are strings `"fold" | "check" | "call" | "bet" | "raise" | "allin"`; `amount` is for
`bet`/`raise` the **street target level in chips** (engine convention `game.py act`), otherwise `None`. Hero is always
`st["players"][st["to_act"]]` — **not** a `hero_idx` field (`../reports/V10_FACTS.md:171`, section A5). Every guard
wraps its computation in `try/except Exception: pass`, i.e. in doubt the base action stands — convenient,
but without a log (see pitfalls). `bb = 100` chips, HU starting stack 20 000 chips = 200 bb.

**The state (`st`) every guard reads** — produced by `pokerbot/engine/game.py:290 state()`:
`street` (`"preflop"|"flop"|"turn"|"river"`), `board` (list of 2-character cards `'As'`), `pot` (int, chips, including
the bet hero is currently facing), `current_bet`, `to_act`, `button`, `sb`, `bb`, `hand_no`,
`history` (list of dicts with `player`/`action`/`street`/`to`/`amount`, plus `{"action":"deal","street":...}` markers),
`players` (2 dicts with `hole`, `stack`, `committed_street`, `committed_total`, `folded`, `all_in`, `is_button`),
`legal`. `to_call` is computed by every guard itself as `max(0, st["current_bet"] - me["committed_street"])`.
Additionally the gate injects `st["hand_id"]` (deck address, `pokerbot/benchmark/duplicate.py:43-51`) — the engine
itself knows no `hand_id`.

---

### Guard framework + A/B gate — `pokerbot/autogym/improver.py`
**Purpose.** Holds the wrapper factory, the spot-bound RNG, the paired A/B gate and the journal writing that
all individual guards share.
**Interface.**
`guarded(make_strat, guard_names: list[str])` (`:626`) — wraps the mini-rules registered in `GUARDS` around a
factory; fires only at `to_call == 0`.
`GUARDS` (`:32`) — whitelist of the rules a *provable* oracle finding may arm autonomously. Contains
exactly one entry: `free_fold` = "fold at to_call=0 becomes check".
`_spot_rng(st) -> random.Random` (`:41`) — deterministic RNG per spot; seed = `crc32` over
`sorted hole cards | board | street | pot | current_bet | committed_street | len(history)`. Without it paired
measurements break (documented: transfer test SE 12,9 despite identical decks, journal.jsonl:33).
`gate_ab(make_candidate, make_incumbent, n_decks, seed) -> dict` (`:649`) — plays paired duplicate decks and
passes the verdict: `ANWENDEN` at `bb100 - 2*se > 0`, `VERWERFEN` at `bb100 + 2*se < -1`, otherwise `NEUTRAL`.
`improve_round(hu_report, n_decks=150, seed=11, exploit=True) -> list[dict]` (`:664`) — one round of the loop:
P findings of the oracle are patched autonomously and gated individually, L/F findings only as a proposal in the journal.
`_journal(entry)` (`:642`) — appends a dict + timestamp to `data/autogym/journal.jsonl`.
**Input/Output.** `gate_ab` returns `{"bb100", "se", "n_decks", "verdict"}`. `improve_round` takes an
`OracleReport` (`.provable`, `.freq`, `.leads` with `.rule`, `.proof`, `.severity_bb`) and returns the journal entries.
**Dependencies.** `pokerbot.benchmark.duplicate` (`duplicate_ab`, `gen_decks`, `pokerbot`) — hard, but trivially
replaceable (around 90 lines, see entry *pargate*). `.oracle.OracleReport` — only for `improve_round`, replaceable.
**Status.** Stateless. `_spot_rng` deliberately holds NO state across calls (per-seat sequences desynchronized
the arms, comment `:44-47`).
**Cost.** `gate_ab` = `n_decks` × 2 hands, single-core. The parallel replacement (`pargate`) manages 3 600–3 900
decks/min at 20–22 workers (journal.jsonl:39, :52).
**Measurement status.** UNMEASURED for `free_fold`/`guarded`: the journal contains **zero** entries of type
`P-AUTOPATCH` (counted in `data/autogym/journal.jsonl`), in the pilot run the P class was empty ("HART 0, P 0, L 35,
F 3", `CLAUDE.md`). The autonomous patch path is built but has never been triggered.
**Usable standalone?** Yes. `gate_ab` + your own strategy factory suffices; `duplicate.duplicate_ab` needs only the
HU engine.
**Pitfalls.** The `verdict` threshold `-1.0 bb/100` is a deliberate *non-regression* tolerance, not a
significance test — and `2*SE` is too optimistic for these fat-tailed distributions. For real verdicts use
`pokerbot/autogym/stats.py:verdikt` (bootstrap), not `gate_ab`.

---
### `podds_guard` — `pokerbot/autogym/improver.py:56`
**Purpose.** A river call becomes a fold when the equity against a **uniform** opponent range does not cover the pot odds.
**Interface.** `podds_guard(make_strat, margin=0.02, iters=120)`. Trigger: `a == "call"` and `to_call > 0` and
`street == "river"`. Draws 40 random combos from the remaining deck, estimates `equity_vs_range(..., iters=120)`; on
`eq + margin < equity_needed_to_call(pot, to_call)` → `("fold", None)`.
**Input/Output.** State dict in, `(action, amount)` out.
**Dependencies.** `knowledge_base.math.formulas.equity_needed_to_call`, `pokerbot.engine.cards.make_deck`,
`pokerbot.engine.equity.equity_vs_range` — all three hard, but one function each and easy to write yourself
(`equity_needed_to_call = to_call / pot`, where `pot` here already includes the call).
**Status.** Stateless.
**Cost.** 40 combos × 120 MC iterations per trigger; not measured individually.
**Measurement status.** MEASURED NEUTRAL: `+0,31 ± 0,31 bb/100` on 800 decks
(`data/autogym/journal.jsonl:17`, type `KANDIDAT-GATE`, rule `podds_guard_river`, 2026-08-16).
**Usable standalone?** Yes, minimally: one equity function + pot odds. No range tracker needed.
**Pitfalls.** The uniform range is almost always too weak on the river → the guard produces value-folds. The
substantive successor version with a tracker range (`river_ecall_guard`) was for that reason even REFUTED (−4,15). If you
want pot-odds discipline, take the **exact enumeration** (`_river_eq_exakt`) and a real range, not this.

---

### `mdf_guard` — `pokerbot/autogym/improver.py:86`
**Purpose.** The opposite direction of `podds_guard`: a flop fold facing a bet becomes a call when the equity vs
a uniform range covers the pot odds (answer to the oracle finding "flop over-fold 0,63 vs MDF-allowed 0,24").
**Interface.** `mdf_guard(make_strat, margin=0.0, iters=120, streets=("flop",))`. Trigger: `a == "fold"`,
`to_call > 0`, `street in streets`; on `eq >= equity_needed_to_call(pot, to_call) + margin` → `("call", None)`.
**Input/Output.** As above.
**Dependencies.** Identical to `podds_guard`.
**Status.** Stateless.
**Cost.** 40 combos × 120 MC iterations per trigger; not measured individually.
**Measurement status.** MEASURED NEUTRAL, three times: `−17,09 ± 22,50` (1 200 decks), `−3,26 ± 2,19` (99 000 decks)
(`data/runs/STAND.md`, runs `20260816_204741` / `20260816_204907`) and `−7,40 ± 28,39` (400 decks,
`data/autogym/journal.jsonl:18`). Point estimates consistently negative, never significant.
**Usable standalone?** Yes, like `podds_guard`.
**Pitfalls.** This is pure **frequency matching** (MDF says "you fold too much" → call more). Refuted three times
independently in the repo; what worked was **selection** (`sel_guard`, below): not *how often*, but
*which hands*. This is where the most expensive lesson of the whole subsystem lives.
Historical bug note: the `streets` parameter originally landed here instead of in `sel_guard` and referenced
an undefined name (NameError on every facing-bet fold, comment `:92-94`) — in case you see an old revision.

---

### `sel_guard` (+ margin variants `sel_m06/m10/m15/m20`, `sel_all`) — `pokerbot/autogym/improver.py:119`
**Purpose.** The same node as `mdf_guard`, but the equity is computed against the opponent's **weighted tracker
range** (Bayes over the line played) — trash keeps folding, only genuinely paying hands get rescued.
**Interface.** `sel_guard(make_strat, margin=0.03, iters=160, streets=("flop",))`. Trigger: `a == "fold"`,
`to_call > 0`, `street in streets`. Builds `RangeTracker().build(st)`, pulls the opponent's weights
`t.range[1 - st["to_act"]]` (dict `(card1, card2) -> weight`), computes
`equity_vs_weighted_range(hole, cw, board, iters=160, rng=_spot_rng(st))`; on
`eq >= equity_needed_to_call(pot, to_call) + margin` → `("call", None)`.
**Input/Output.** As above; additionally the tracker reads `st["history"]`.
**Dependencies.** `pokerbot.strategy.range_tracker.RangeTracker` — **hard and expensive**: this is the actual
substance of the guard. Replaceable only by your own range model with the same output shape.
`pokerbot.engine.equity.equity_vs_weighted_range` and `equity_needed_to_call` — hard, but small.
**Status.** Stateless; the tracker is rebuilt from the history for every decision (there is **no**
snapshot API in the repo, `../reports/V10_FACTS.md:138`).
**Cost.** Tracker rebuild measured at **210 ms cold / 7,2 ms warm** (`../reports/V10_FACTS.md:139`), plus 160 MC iterations.
**Measurement status.** MEASURED POSITIVE, repeatedly, and the only guard with a clean margin curve:
· `margin=0.03`, flop: `+4,70 ± 2,06` (99 000 decks, journal.jsonl:20) and replication `+7,49 ± 2,08`
  (99 000 decks, journal.jsonl:21) → pooled ≈ `+6,1 ± 1,5`; christened **AUSLESE v1**.
· Margin sweep vs v1 (journal.jsonl:34-36): `m06 +0,06 ± 1,45` NEUTRAL · `m10 +5,64 ± 1,74` ANWENDEN ·
  `m15 +10,50 ± 2,10` ANWENDEN · `m20 −1,52 ± 1,54` NEUTRAL (`data/runs/STAND.md`, run `20260817_135314`).
· `m15` decisive: `+8,68 ± 1,28` vs frozen base on **183 200 decks** (journal.jsonl:39); three
  direct runs vs v1 `+10,50 / +1,11 / +2,63` → pooled `+3,94 ± 0,95`; christened **AUSLESE v3** (journal.jsonl:41).
· `sel_all` (flop+turn+river, margin 0.03): vs base `+6,13 ± 2,03`, but in the direct comparison vs flop-only
  `+3,00 / +0,44 / +0,18` → pooled `+0,69 ± 0,56`, rotation REJECTED (journal.jsonl:28).
· `sel_all_m15` vs `sel_m15`: **exactly 0,00 on 29 920 decks** — the turn/river rescue channel is simply
  EMPTY at a 15 pp margin (journal.jsonl:51 + interpretation :59). Read that as "no channel", not as "refuted".
· Transfer to a foreign opponent (GTOBaseline, 3 000 decks, paired): `−3,80 ± 12,87` — uninformative, because the
  measurement at the time used unseeded MC (journal.jsonl:33). So the gain is proven **in the mirror**, not against a
  foreign opponent.
**Usable standalone?** Yes, but only with a range tracker. Without it the guard degenerates into `mdf_guard` (NEUTRAL).
**Pitfalls.** The margin is not fine-tuning, it is the active ingredient: 3 pp → +6, 15 pp → +17 vs base, 20 pp tips over.
Whoever adopts the guard and sets the margin to "mathematically correct" (0.0) gets `mdf_guard` back. Second:
`m15` means that 15 percentage points of equity above the pot odds are demanded — that is deliberately *not* a GTO quantity.

---

### `lizenz_guard` — `pokerbot/autogym/improver.py:156`
**Purpose.** Bet side: flop/turn bets and raises with equity below `junk_eq` against the tracker range become
check or fold ("bluffs need a licence" — Brown's bluff-equity band 0,36–0,50, not the bottom of the distribution).
**Interface.** `lizenz_guard(make_strat, junk_eq=0.20, iters=160)`. Trigger: `a in ("bet","raise","allin")` and
`street in ("flop","turn")`; on `eq < junk_eq` → `("check", None)` if `to_call == 0`, else `("fold", None)`.
**Input/Output.** As `sel_guard`.
**Dependencies.** `RangeTracker`, `equity_vs_weighted_range` — hard.
**Status.** Stateless.
**Cost.** Tracker rebuild + 160 MC iterations per trigger.
**Measurement status.** MEASURED NEUTRAL: `−0,06 ± 0,69` on 1 200 decks (`data/autogym/journal.jsonl:26`, type `AKTEN`) —
"the base hardly bluffs without a licence". Before that a **null measurement as diagnosis**: `0,00 ± 0,00` on 1 200 decks, because the
wrapper did not have `"bet"` in the trigger list and therefore never fired (journal.jsonl:23, type `DIAGNOSE-BEDARF`).
**Usable standalone?** Yes (tracker required).
**Pitfalls.** Exactly the bug found here will happen to you too: the **opening bet is called `"bet"` in
this engine, not `"raise"`** (comment `:173-175`). A guard that measures exactly `0,00 ± 0,00` is not
neutral — it is dead. Always measure the **channel width** first (how often does it fire?) before reading the verdict.

---

### `einmal_guard` — `pokerbot/autogym/improver.py:192`
**Purpose.** Multi-street discipline: the selection rescue (as in `sel_guard`) may rescue a hand only **once**;
from the second opportunity of the same hand onward the base decision applies again.
**Interface.** `einmal_guard(make_strat, margin=0.03, iters=160)`. Trigger: flop fold facing a bet and
`not zustand["gerettet"]`; after a rescue `gerettet = True` is set.
**Input/Output.** As `sel_guard`.
**Dependencies.** `RangeTracker`, `equity_vs_weighted_range` — hard.
**Status.** **Per hand.** Holds `{"hand": hand_no, "gerettet": bool}` in the closure and resets as soon as
`st["hand_no"]` changes. If your engine does not supply `hand_no` or it is (as in the duplicate mirror) constantly 1
or 2, the reset is broken — then you need `st["hand_id"]`.
**Cost.** As `sel_guard`, but rarer (at most one trigger per hand).
**Measurement status.** MEASURED NEUTRAL: `+0,41 ± 1,05 bb/100` vs AUSLESE v1 (`data/autogym/journal.jsonl:37`, type
`RUNDE4-DISZIPLIN`, 2026-08-17).
**Usable standalone?** Yes.
**Pitfalls.** The state is bound to `hand_no` (`:207-208`) — in the paired gate `hand_no` is **always 1 or 2**
(`pokerbot/benchmark/duplicate.py:43-45`), so the reset wrongly fires per mirror half. That is exactly the
class of error that silently corrupts a paired measurement.

---

### `turn_wert_guard` — `pokerbot/autogym/improver.py:230`
**Purpose.** The bot's oldest documented leak on the **bet side**: a turn check with a strong made hand becomes
a ~2/3-pot value bet.
**Interface.** `turn_wert_guard(make_strat, frac=0.66, min_eq=0.60, iters=160)`. Trigger: `a == "check"`,
`to_call == 0`, `street == "turn"`, both stacks > 0. Two conditions must hold:
(a) hand class via treys `get_rank_class` — `kl <= 6` (trips or better) OR `kl == 7` (two pair) with
hole-card involvement OR an overpair (pocket pair higher than every board card); (b) `eq >= min_eq` against the
tracker range. Then `("bet", int(frac * st["pot"]))`; the engine clamps to `[raise_min, raise_max]`.
**Input/Output.** As `sel_guard`, additionally `pokerbot.engine.evaluator.evaluate(board, hole)`.
**Dependencies.** `treys` (soft — if the import fails, `_klasse is None` and the guard switches itself
off completely), `pokerbot.engine.evaluator`, `RangeTracker`, `equity_vs_weighted_range` — hard.
**Status.** Stateless.
**Cost.** Tracker + 160 MC iterations per turn-check node; not measured individually. Channel width pre-measured:
**40 of 800 hands (5 %)** would bet (journal.jsonl:44).
**Measurement status.** MEASURED POSITIVE, three-runs rule satisfied: `+1,64 ± 4,03` (run 1, journal.jsonl:52),
`+9,39 ± 4,06` (:61), `+10,78 ± 4,00` (:62); **pooled `+7,27 ± 2,33` bb/100 over 89 760 decks**, bootstrap CI
`[+2,69; +12,05]`, `perm_p 0,0007`, nonzero share 8,58 % (journal.jsonl:63, type `R5B-POOL`). The guard core
(`turn_wert(sel_m15)`) vs frozen base: `+16,14 ± 2,77`, CI `[+10,74; +21,56]`, `perm_p 0,0002`
(journal.jsonl:70, type `V4-VS-BASIS-POOL`). **Applied** — part of `FINAL_STACK`.
**Usable standalone?** Yes, if you have a hand evaluator and a range model.
**Pitfalls.** Two, both measured. (1) **Readability**: the LLM duel counted the guard bets "in
continuation lines 3/3 genuine" — i.e. usable as a tell; the guard bets *only* for value, never as a bluff, and
thereby caps the check range (journal.jsonl:71). Whoever adopts it adopts a balance violation. (2) The
equity RNG seed `_spot_rng(st)` contains the **hero hole cards** (`../reports/V10_FACTS.md`, A5) — irrelevant for a
gate measurement, not irrelevant for any range-based analysis of your own bot.

---

### `button_disziplin_guard` (stack name `r6_button`) — `pokerbot/autogym/improver.py:606`
**Purpose.** The button never open-folds heads-up: `fold` at `to_call == 50` preflop becomes a 2,5× open to 250.
**Interface.** `button_disziplin_guard(make_strat)` — no parameters. Trigger: `a == "fold"`,
`street == "preflop"`, `to_call == 50` **and** `me["committed_street"] == 50`. No hand condition.
**Input/Output.** As above.
**Dependencies.** None except the state. The only guard without an import.
**Status.** Stateless.
**Cost.** Negligible (two integer comparisons).
**Measurement status.** MEASURED NEUTRAL in the mirror, POSITIVE on the adversary axis:
Mirror `+0,71 ± 2,18 bb/100`, channel 16,7 % (`data/autogym/journal.jsonl:73`, type `R6-GATE`) — the self-play base
does not punish open-folds. The LLM adversary did: before the guard 29 % button open-folds; after the guard
**0 of 46**, and the opponent's harvest fell from 186 to 58 bb/100 over 92 hands (journal.jsonl:75, type
`FABLE-RETEST`). **Applied** — part of `FINAL_STACK`.
**Usable standalone?** Yes, fully isolated.
**Pitfalls.** The chip numbers 50 (SB) and 250 (open) are **hard-coded** to 100-chip blinds. In any other
blind structure the guard never fires — another silent zero. And: this is the prototype of the repo's **two-axis
doctrine** — hardening guards against adaptive opponents are structurally invisible to negative in the mirror; the mirror
is only a non-regression bound, the proof belongs to the adversary (journal.jsonl:74, type `R6-DOKTRIN`).

---

### `river_ecall_guard` (stack name `r6_ecall`) — `pokerbot/autogym/improver.py:282` — **REFUTED**
**Purpose.** River calls against large bets (≥ 60 % pot) only when the equity vs the tracker range covers pot odds + margin.
**Interface.** `river_ecall_guard(make_strat, marge=0.05, iters=200)`. Trigger: `a == "call"`,
`street == "river"`, `to_call >= 0.6 * max(1, pot - to_call)`; on `eq < pot_odds + marge` → `("fold", None)`.
**Input/Output.** As `sel_guard`.
**Dependencies.** `RangeTracker`, `equity_vs_weighted_range` — hard.
**Status.** Stateless.
**Cost.** 200 MC iterations per trigger.
**Measurement status.** **MEASURED REFUTED:** `−4,15 ± 0,97 bb/100`, CI `[−6,1; −2,3]`, sign-z −4,7,
nz-median −1 452 chips (`data/autogym/journal.jsonl:72`, type `R6-GATE`, verdict VERWERFEN). Diagnosis: in the mirror
the folded calls are **value-folds** — the self-play ecology bets enough bluffs there. Not in the stack.
**Usable standalone?** Technically yes — but do not adopt it in this form.
**Pitfalls.** Two named causes: (1) MC with `iters=200` carries ~3,5 pp standard error — exactly the noise
on which the guard failed (comment `:317-319`); the successor computes **exactly** on the river (`_river_eq_exakt`).
(2) The trigger is a pure threshold without selection (no blockers, no equity-deficit measure).

---

### `_river_eq_exakt` + `river_bill_guard` (stack name `r7_bill`) — `pokerbot/autogym/improver.py:315` / `:338`
**Purpose.** `_river_eq_exakt` computes river equity by **full enumeration** over the weighted range
(no RNG, noise-free). `river_bill_guard` uses it for a tight big-pot river defense.
**Interface.**
`_river_eq_exakt(hole, cw: dict, board) -> float` — `cw` = `{(card1, card2): weight}`; blocked combos are
skipped; returns `(worse + 0.5*tied) / mass`, `nan` on empty mass.
`river_bill_guard(make_strat, marge=0.04, overbet_marge=0.02, min_frac=0.6, min_pot_chips=3000)` — trigger:
river call, `to_call >= min_frac * pot_vor`, `pot + to_call >= min_pot_chips`. A fold happens only on
`eq < pot_odds − m_eff` (margin **negative**: only clearly −EV calls, never the marginal call); for overbets/jams
(`to_call >= pot_vor`) the tighter `overbet_marge` applies.
**Input/Output.** As `sel_guard`; additionally `pokerbot.engine.evaluator.evaluate` (treys convention:
**lower score = better hand**).
**Dependencies.** `RangeTracker`, `evaluate` — hard. No MC, no RNG.
**Status.** Stateless.
**Cost.** Enumeration over all range combos (after 3 barrels still 700–900 combos, journal.jsonl:89); not
measured in seconds.
**Measurement status.** MEASURED DEAD in the mirror + NEUTRAL in replay: `r7_bill` mirror **exactly 0** — it never fires in the gym
(`data/autogym/journal.jsonl:91`, type `R7-REPLIKATION`). Replayed on real GTOW hands: 20 trigger spots,
5 folds of which 3 correct (+141 bb) and 2 wrong (−121 bb) = net **+20 bb** (journal.jsonl:89, type `R7-DIAGNOSE`).
The explicit verdict there: "a threshold guard on a tracker basis does not carry the river big-bet defense" — the
missing information is the polarized bet range, i.e. a solver question. **Not in the stack.**
**Usable standalone?** `_river_eq_exakt` yes and recommended without reservation (30 lines, no dependency except
an evaluator). The guard around it: no.
**Pitfalls.** The tracker equity **does not separate winners from losers** — measured 0,578 vs 0,513 in the default
and 0,652 vs 0,532 with the PRINCE env (journal.jsonl:89). A guard can only be as sharp as its range model;
more threshold tuning does not help there.

---

### `river_wert_bremse` (stack name `r7_wert`) — `pokerbot/autogym/improver.py:378`
**Purpose.** A river bet with a **strong** made hand (two pair or better) needs ≥ 50 % equity against the
tracker range — otherwise the hand is a bluff-catcher on this board and the check dominates.
**Interface.** `river_wert_bremse(make_strat, min_eq=0.50)`. Trigger: `a == "bet"`, `to_call == 0`,
`street == "river"`, treys class `kl <= 7`. On `_river_eq_exakt(...) < min_eq` → `("check", None)`.
Bluffs and weak hands remain untouched; the raise node is deliberately not covered.
**Input/Output.** As `sel_guard`; RNG-free.
**Dependencies.** `treys` (soft), `pokerbot.engine.evaluator`, `RangeTracker`, `_river_eq_exakt` — hard.
**Status.** Stateless.
**Cost.** One range enumeration per river-bet node; not measured individually.
**Measurement status.** MEASURED POSITIVE, three-runs rule satisfied on three disjoint deck banks, each vs `r6_button`:
`+8,10 ± 1,14` · `+8,81 ± 1,25` · `+7,38 ± 1,05`, all `perm_p 0,0002`
(`data/autogym/journal.jsonl:91`, type `R7-REPLIKATION`). **Applied** — part of `FINAL_STACK`.
Counter-evidence, honestly noted: on 3 904 real GTOW decisions it intervenes only **10 times**, and the
typical case was not braked under the live tracker — the evidence is self-play-side (journal.jsonl:94).
**Usable standalone?** Yes, provided evaluator + range model are present.
**Pitfalls.** The threshold 0,50 is not theory, but the boundary "do I beat the range or not". The
guard brakes **only the bet node with a strong hand** — deliberately one mechanism per guard. Whoever extends it to raises or
weak hands purifies the bluff side and violates the mixing (the project's seesaw doctrine).

---

### `_river_spot_und_frage` + `_frage_kind` (substrate of the solver guards) — `pokerbot/autogym/improver.py:421` / `:472`
**Purpose.** Translates a running state into a solvable river subgame: freezes the tracker ranges **at the
start of the river** and reconstructs the river betting sequence in additional chip amounts.
**Interface.** `_river_spot_und_frage(st, frage_kind) -> (RiverSpot, pot_river) | None`. Searches
`st["history"]` for the marker `{"action":"deal","street":"river"}`, cuts there, builds `RangeTracker().build(st0)`,
walks through the actions after it (level tracking per seat) and appends `("hero", frage_kind, 0.0)`.
`pot_river = st["pot"] − sum of the river bets`; `eff = min(stack + committed_street)`.
`_frage_kind(a, to_call)` maps the base action to `"raise" | "bet" | a`.
**Input/Output.** State in; out comes a `pokerbot.strategy.gpu_resolver.RiverSpot` (board, hero weights,
villain weights, `pot_river`, `eff`, `hero_oop`, `seq`, `hero_hole`) plus `pot_river`. `None` if no
river-deal marker exists or `pot_river <= 0`.
**Dependencies.** `gpu_resolver.RiverSpot`, `RangeTracker` — hard.
**Status.** Stateless.
**Cost.** One tracker rebuild (210 ms cold / 7,2 ms warm, `../reports/V10_FACTS.md:139`).
**Measurement status.** UNMEASURED as a unit of its own; the `pot_river` computation is verified (`1400 == 1400`,
`../reports/V10_FACTS.md`, A5).
**Usable standalone?** Only together with a history in the described format.
**Pitfalls.** **Without the `deal` marker in the history the function silently returns `None`** — the guard
above it then never fires and you see exactly 0. That is exactly what happened in the Kaggle adapter (commit `d22d400`:
"without it v10 reported 'fehler:root_nicht_rekonstruierbar' and played 0 times in 30 hands"). If you port these
guards, the deal marker is a mandatory part of your history format.

---

### `river_gpu_guard` (stack name `r8_gpu`, in the champion `r8_stack`) — `pokerbot/autogym/improver.py:477`
**Purpose.** Solver **surgery** on the river: in large pots the subgame is solved with the ranges frozen at the
start of the river, and the base action is overridden only if the solver clearly rejects it.
**Interface.** `river_gpu_guard(make_strat, min_pot_chips=3000, iters=150, p_max_basis=0.10, p_min_alt=0.70)`.
Trigger: `street == "river"` and `st["pot"] >= min_pot_chips` (current pot, **not** `pot_river`). Solves via
`solve_spots([spot], iters=150)`, determines `p_basis` (for bet/raise the maximum over all bet/raise arms) and the
best alternative; overrides only if `p_basis < 0.10` AND `sigma[best] > 0.70`. Mapping:
`fold`→fold (only when `to_call>0`), `call`→call, `check`→check (only when `to_call==0`), `bet…`→`("bet", int(0.75*pot))`.
**Input/Output.** State in; `solve_spots` returns per spot `{"acts": [str], "sigma": [float], "zusatz_norm": [float]}`.
**Dependencies.** `pokerbot.strategy.gpu_resolver.solve_spots` (→ `gpu_cfr.RiverCFRBatch`, torch + CUDA) — **hard
and heavy**; `_river_spot_und_frage` → `RangeTracker`. Without the GPU solver nothing of this guard remains.
**Status.** Stateless and deterministic (no RNG; argmax only in the clear case) — A/A exactly 0 proven on 600 decks
(`data/autogym/journal.jsonl:92`).
**Cost.** Throughput `0,30 s/spot` amortized at batch 256 (journal.jsonl:90); **single solve** (B=1, fp32,
150 iterations, RTX 3080 Ti) measured `0,9–1,1 s` at SPR 1, `2,0–2,55 s` at SPR 3, `2,5 s` at SPR 7, setup
18–23 ms warm / 289 ms cold (`../reports/V10_FACTS.md`, A6). The guard calls **one B=1 solve per decision** —
that is the latency driver of the whole chain.
**Measurement status.** MEASURED POSITIVE, the largest single jump of the project (caution: the increment includes
`river_wert_bremse`, which alone brings ≈ +8):
`r8_stack` vs `r6_button`: `+29,92 ± 3,10` / `+23,76 ± 3,07` / `+29,23 ± 3,03` on three banks of 30 000 decks each,
pooled `+27,6 ± 1,8`, all `perm_p 0,0002`; vs frozen base `+30,60 ± 5,03`; A/A exactly 0
(`data/autogym/journal.jsonl:92`, type `R8-FINALE-LAUF1`; summary of the three runs :93, type
`TAUFE-AUSLESE-V5`). Solver audit on 571 real river spots:
disaster calls receive solver `fold` with p > 0,95, the mis-value-bets solver `check` with p ≈ 1,0 (:90).
**Applied** — the core of `FINAL_STACK = r8_stack`.
**Usable standalone?** No, practically not. You need the GPU river CFR, the resolver wrapper and the
range tracker; those are three further modules.
**Pitfalls.** Three on record (`../reports/V10_FACTS.md`, A5/A6): (1) The bet size is **hard-coded to `0.75*pot`**,
although the comment next to it claims "size from the tree arm". (2) `solve_spots._injiziere` pushes
hero's actual combo with minimum weight 0,02 into the hero range — so the solver solves a game in which hero
partially "knows" his card; that is the documented structural defect v10 set out to fix. (3) `except:
pass` without a log: a permanently failing solver is indistinguishable from a guard that never fires.

---

### `river_play_guard` (stack names `r9_play`, `r10_ernte`) — `pokerbot/autogym/improver.py:535` — **dropped**
**Purpose.** The level above surgery: in big-pot river spots the solved policy is **played** (sampled from
the solver mix), not just the clear error corrected.
**Interface.** `river_play_guard(make_strat, min_pot_chips=3000, iters=150, half=False)`. After the solve, sampling is
deterministic: `u = crc32("v8play|" + hole|board|pot|current_bet|committed_street|len(history)) / 2^32`,
then cumulative selection over `sigma`. Sizes come from the tree arm: `betrag = zus[wahl]/100 * pot_river`, target level
`int(me["committed_street"] + betrag)`; jam at `betrag >= stack-1`. Legality gate: `kann_raisen = (not opp.all_in)
and me["stack"] > to_call`, otherwise the guard falls back to the passive branch.
**Input/Output.** As `river_gpu_guard`, additionally `zusatz_norm` from the solver result.
**Dependencies.** Identical to `river_gpu_guard` — hard.
**Status.** Stateless; deterministic via the spot hash (A/A exactly 0 proven, journal.jsonl:97).
**Cost.** As `river_gpu_guard`; `half=True` (fp16) was built as a latency lever (`r10_ernte`, trigger 1 500 chips).
**Measurement status.** MEASURED NEUTRAL in the mirror → **dropped**: `play` vs v5 `+1,14 ± 2,78` (30 000 decks);
the full v8 composition vs v5 `+3,91 ± 2,85` and `−1,23 ± 4,36` (30k + 15k, pooled ≈ `+2,3 ± 2,4`), A/A exactly 0
(`data/autogym/journal.jsonl:97`, type `V8-DROP`). Opposing evidence on the GTOW axis, explicitly marked as
unproven: 32 interventions on 3 904 decisions (0,8 %), of which 7 `call→fold` with net **+278,6 bb**
on the balance (journal.jsonl:94, type `V8-PLAY-PROFIL`). The documented cause analysis (`../reports/V8_POSTMORTEM.md`):
channel saturation — the surgery had already harvested the clear cases, the play differences lie in
indifference zones (nz-median 1,9 bb vs 11,6 bb).
**Usable standalone?** No (as `river_gpu_guard`).
**Pitfalls.** The sampling hash **contains the hero hole cards** (`../reports/V10_FACTS.md`, A5). Thus the
"mix" depends on private information instead of the public state — exactly the defect the project's
hybrid doctrine later names "hand-dependent gating". Also: no deadline, `except: pass`.

---

### `turn_gpu_guard` — `pokerbot/autogym/turn_gpu.py:170`
**Purpose.** The same solver surgery as `river_gpu_guard`, but on the **turn**: the turn+river subgame is solved with the
ranges frozen at the start of the turn (turn betting + 48-runout river batch).
**Interface.** `turn_gpu_guard(make_strat, min_pot_chips=3000, iters=120, p_max_basis=0.10, p_min_alt=0.70)`.
Trigger only `street == "turn"` and `pot >= min_pot_chips`; never fires after the river deal. Core:
`_turn_urteil(st, a, amt, iters, p_max_basis, p_min_alt) -> {"acts","sigma","p_basis","urteil"}` (`:87`);
`urteil` is `None` if the surgery thresholds do not engage.
Helpers: `_turn_seq(hist_nach_deal, hero_seat)` (`:29`) and `_navigiere_turn(cfr, seq, skala)` (`:56`).
Tree geometry as module constants: `TURN_BETS=(0.75,)`, `RAISE_SIZES=(2.7,)`, `MAX_RAISES=1`,
`RIVER_KW={"bet_sizes":(0.75,), "raise_sizes":(), "max_raises":1}` (`:23-26`) — deliberately small because of latency.
**Input/Output.** As the river solver guards.
**Dependencies.** `pokerbot.strategy.gpu_cfr` (`TurnCFR`, `combo_index`, `range_vector`),
`pokerbot.strategy.gpu_resolver` (`POT_NORM`, `_injiziere`) — hard, GPU-bound.
**Status.** Stateless, deterministic (no RNG).
**Cost.** The only number in the repo is the code comment "high trigger (**latency 12–14 s**)"
(`pokerbot/autogym/pargate.py:150`) — not backed by a measurement run. The self-test (`python -m
pokerbot.autogym.turn_gpu`) measures cold/warm, but no result is stored in the repo.
**Measurement status.** UNMEASURED in the gate: there is **no** A/B result for `r9_turn`. The channel is documented
as too thin — "turn_gpu 3/3904 too quiet" (`docs/STATE.md:110`) or "replay 3/3904 = no accountable evidence"
(`pokerbot/autogym/pargate.py:159-160`). Remains a default-OFF arm.
**Usable standalone?** No — needs the complete GPU-CFR stack.
**Pitfalls.** The trigger `min_pot_chips` is set to **5 000** (not 3 000) in `_wickle`, precisely because of the latency
(`pargate.py:152`). At 12–14 s per decision the guard is unusable for live play against a clock; it is a
research arm, not a product.

---

### `stackoff_bremse` — `pokerbot/autogym/preflop_guards.py:42`
**Purpose.** Large preflop stack-offs only with selected hand classes: from 100 bb total investment only
premium hands remain free, middle classes up to below 150 bb, everything else folds.
**Interface.** `stackoff_bremse(make_strat, premium=("AA","KK","QQ","AKs","AKo"), mittel=("JJ","TT","AQs"),
grenze_hart=15000, grenze_weich=10000)`. Trigger: `street == "preflop"`, `to_call > 0`,
`a in ("call","raise","allin")`. Computes the **total investment after the action**:
call → `committed_total + min(to_call, stack)`; allin/`amt is None` → `committed_total + stack`;
raise → `committed_total - committed_street + min(amt, committed_street + stack)`.
Below `grenze_weich` it never intervenes; `to_call == 0` (opens, BB option) likewise never.
Helper `_hand_klasse(hole)` (`:31`) → `'KK' | 'AKs' | 'J9o'`.
**Input/Output.** As above. Constants: `_GRENZE_WEICH = 10000`, `_GRENZE_HART = 15000` chips (`:27-28`).
**Dependencies.** None except the state — deliberately kept so, so that the import does not drag in gate machinery
(comment `:18-19`).
**Status.** Stateless.
**Cost.** Negligible (string comparisons).
**Measurement status.** UNMEASURED as an effect — the channel is **mute** in self-play: counted **1 trigger per 400
hands** (`data/autogym/journal.jsonl:96`, type `R9-PRE-VERDIKT`, there explicitly "innocent" of the −11,42 of the
combo arm). The motivation comes from the GTOW axis (disaster class D, "−13,8 bb per cell",
`CANDIDATES.md` → `HU_OPTIMAL_MAP.md:51`), but was never measured there as an A/B.
Functionally checked: 10/10 cases in the self-test (`python -m pokerbot.autogym.preflop_guards`, `:136-179`).
**Usable standalone?** Yes, completely isolated — the most easily adoptable guard of the collection.
**Pitfalls.** The limits are **absolute chip values** for 100-chip blinds and a 200-bb starting stack. And the guard
is measured ineffective in self-play: if your bot rarely builds 100-bb stack-offs with J9o anyway, you are
only buying code. Measure the trigger rate first.

---

### `no_limp_guard` — `pokerbot/autogym/preflop_guards.py:85` — **REFUTED**
**Purpose.** Remove the HU button limp: `call` at `to_call == 50` and `committed_street == 50` becomes a
2,5× open to 250.
**Interface.** `no_limp_guard(make_strat)` — no parameters. Constants `_SB_CHIPS = 50`,
`_OPEN_RAISE_TO = 250` (`:23-24`).
**Input/Output.** As above.
**Dependencies.** None.
**Status.** Stateless.
**Cost.** Negligible.
**Measurement status.** **MEASURED REFUTED** (as part of the arm `r9_pre`): `−11,42 ± 2,97 bb/100` on 30 000 decks,
verdict VERWERFEN; the culprit diagnosis attributes the loss to the `no_limp_guard` — the base limps **78 of 400
hands (~39 % of buttons) strategically**, so the guard rebuilt half the preflop game (37,8 % divergence decks)
(`data/autogym/journal.jsonl:96`, type `R9-PRE-VERDIKT`).
**Usable standalone?** Yes — but the measurement says: don't.
**Pitfalls.** This is the lesson recorded in the repo: the triggering finding ("limp-call → fold to
c-bet 5/7 = free money") was a **limp-pot defense** problem, not a limp problem. A guard that switches off a
strategic frequency completely instead of repairing the follow-up node costs more than the leak was worth.

---

### `river_plan_guard` (stack names `r10_stack`, `r10_h0`) — `pokerbot/autogym/river_plan.py:920`
**Purpose.** The v10 replacement for `river_gpu_guard`: **one** solve per hand at the start of the river, whose plan then applies to all
decisions of that hand — gating by **public** state, randomization from a private seed
instead of from the hole cards.
**Interface.** `river_plan_guard(make_strat, min_pot_chips=DEFAULT_MIN_POT_CHIPS, iters=DEFAULT_ITERS,
deadline_s=None, trace_pfad=None, privater_seed=None, modus="gym", solve_worker=LIVE_SOLVE_WORKER,
queue_budget_s=None, aufwaermen=True) -> RiverPlanFabrik`. `modus="gym"`: private seed deterministic from
(hand_adresse, seat), fixed iterations, no timeout → A/A exactly 0. `modus="live"`: `os.urandom(16)` per process,
deadline, `solve_worker` parallel solve threads. Hero outside the public range → **always** base with
status `hand_not_in_range`.
**Input/Output.** As the other river guards; additionally a trace with status codes
(`plan` / `deadline` / `offtree` / `hand_not_in_range` / `fehler`).
**Dependencies.** `pokerbot.strategy.hero_range` (K1 hero-likelihood replay), `gpu_cfr.RiverCFRBatch`,
`RangeTracker` — hard. Constants: `LIVE_SOLVE_WORKER = 3`, `QUEUE_BUDGET_S = 3.0`,
`K1_AKZEPTIERTE_STATUS = ("ok","teilweise")` (`:82,:84,:240`).
**Status.** **Per hand** (plan cache) and **per process** (live seed, solve threads). On a hand change the plan must
be discarded, otherwise you play the previous hand's plan.
**Cost.** Measured live (n=40 plan pots, after the thread fix): p50 3,04 s, p90 8,50 s, **p99 10,15 s**
(`data/autogym/journal.jsonl:108`, type `V10-LIVEFIX-G2-NACHMESSUNG`; also `docs/STATE.md:95`);
deadline aborts 0/40, comparison arm v5 p50 2,10 s / p99 8,20 s.
**Measurement status.** MEASURED NEUTRAL in the mirror, gate ladder **not passed** → **not shipped**:
G5 `r10` vs `r8` `+11,68 ± 10,85` on 1 968 decks, CI `[−9,39; +33,06]` (NEUTRAL);
G3 MISSED (K1 total variation 0,2085 mean against a budget of 0,02; hero outside the K1 support in 21 of
64 cases); live the plan was played only 25/40, `offtree` 11/40
(`data/autogym/journal.jsonl:107`, type `V10-GATES`, and `../reports/V10_GATES_REPORT.md`).
`r10_h0` (2026-09-10, commit `d22d400`) is the patch against that: the same plan, but on the **complete** v5 chain
instead of on `r8`-without-surgery, so that a fallback never lands below the champion; documented so far is only
"A/A exactly 0" (commit message) — otherwise UNMEASURED.
**Usable standalone?** No. Of all guards the heaviest dependency load (solver + its own hero-range model).
**Pitfalls.** The documented catastrophe source: if the plan fails (off-tree size, deadline, hand not in the
range), `r10_stack` landed on the **bare base without the v5 surgery** — all three gym decks with ≤ −100 bb
came from this fallback (`data/autogym/journal.jsonl:107`). A guard with a degraded, invisible fallback is
more dangerous than no guard at all.

---

### `wickle_decide` + `FINAL_STACK` — `pokerbot/strategy/auslese.py`
**Purpose.** The **one source** of the shipped guard stack for all consumer channels (web app, benchmarks,
export) — so that no two channels ever play different chains.
**Interface.**
`FINAL_STACK = "r8_stack"` (`:34`) — the champion: `river_gpu_guard(river_wert_bremse(r6_button(turn_wert(sel_m15))))`.
`RC_STACK = "r10_stack"` (`:35`) — release candidate v10, **not** christened.
`AUSLESE_ENV = {"POKERB_TURN_DEFENSE": "0.07", "POKERB_SLOWPLAY": "0.25"}` (`:36`);
`AUSLESE_ENV_RESOLVER_OFF` adds `POKERB_RAISE_NARROW = "1.0"` (`:37`).
`setze_env(resolver_on=False)` (`:40`) — sets the flags via `setdefault`; **must run before the import of
`pokerbot.strategy.bot`**, because the flags are read at import time.
`wickle_decide(pb, stack=None, kanal="live") -> decide(st) -> dict` (`:49`) — wraps the stack **dict-preserving** around
`PokerBot.decide`: the base factory remembers the complete decision dict, and if the guard chain
changes `(action, amount)`, a new dict with `auslese_guard: True` is returned.
**Input/Output.** In: a bot instance with `.decide(st) -> {"action","amount","rationale",…}`. Out: the same
signature, but with the guard chain. `kanal="gym"` enforces determinism (paired gates), `"live"` gives K2 arms
a deadline + `os.urandom` seed.
**Dependencies.** `pokerbot.autogym.pargate._wickle` — hard (the composition lives there).
**Status.** Per bot instance. The guard chain is built **once** (`kette = stack_fabrik(0)`), so stateful
guards (`einmal_guard`, K2 plan cache) live as long as the instance.
**Cost.** That of the chosen stack; the wrapper itself is a function call.
**Measurement status.** MEASURED POSITIVE for the chain as a whole: v4 era `+23,36 ± 5,32` vs frozen base
(`data/autogym/journal.jsonl:76`, type `FINAL-STACK-VS-BASIS`); v5 era `r8_stack` vs base `+30,60 ± 5,03`
(journal.jsonl:92). **Absolute external measurement missing**: the only real GTOW anchor belongs to v4-on-PRINCE with
`−21,12 bb/100 AIVAT` over 979 hands (journal.jsonl:88, type `GTOW-NACHT2-FAZIT-MANUELL`) — v5 has only
mirror evidence (`docs/STATE.md`, section 2026-09-09).
**Usable standalone?** Yes, if your bot offers a `decide(st) -> dict`.
**Pitfalls.** `rationale` is a **dict**, not a string. The original code appended a string on a guard intervention
and crashed exactly when a guard fired — the error survived a 20-hand smoke test
(comment `:76-78`). Second: calling `setze_env` **after** the bot import is ineffective and silent.
Third: the guards are HU-only (2-player state expressions, `st["players"][1 - st["to_act"]]`) — the 6-max measurement
rejected the integration as harmful (`hybrid_r8 −21,73 ± 9,01` vs the pure 6-max core, journal.jsonl:112).

---

### `_wickle` (stack composition) + `par_gate` — `pokerbot/autogym/pargate.py`
**Purpose.** `_wickle` is the **only** place where the guard chains are named and composed;
`par_gate` is the paired A/B gate across all CPU cores.
**Interface.**
`_wickle(name: str, basis, kanal: str = "gym")` (`:69`) — wraps the named stack around a finished strategy factory;
`ValueError(name)` on an unknown name. `KANDIDATEN` (`:18-47`) is the whitelist of all names.
`_baue_fabrik(name, seed)` (`:194`) — the gate channel: `_wickle(name, pokerbot(exploit=True, seed=seed))`.
`par_gate(kandidat, n_decks, workers, seed=1, deck_seed0=1000, incumbent="basis") -> dict` (`:238`).
CLI: `python -m pokerbot.autogym.pargate --kandidat sel_m15 --decks 30000 --workers 20 --incumbent basis`.
**The registered stack names (built from inside out):**
| Name | Composition |
|---|---|
| `basis` | the bare strategy (no guard) |
| `mdf_guard` / `podds_guard` / `sel_guard` / `einmal_guard` / `lizenz_guard` | one guard each with default parameters |
| `sel_m06` / `sel_m10` / `sel_m15` / `sel_m20` | `sel_guard(margin=0.06 / 0.10 / 0.15 / 0.20)` |
| `sel_all` | `sel_guard(streets=("flop","turn","river"))` |
| `auslese2` | `lizenz_guard(sel_guard(streets=all))` |
| `sel_all_m15` / `sel_turn_m15` | `sel_guard(margin=0.15, streets=all / flop+turn)` |
| `turn_wert` | `turn_wert_guard(sel_guard(margin=0.15))` ← **AUSLESE v4 core** |
| `wert_plus_all` | `turn_wert_guard(sel_guard(margin=0.15, streets=all))` |
| `r6_ecall` | `river_ecall_guard(turn_wert)` — REFUTED |
| `r6_button` | `button_disziplin_guard(turn_wert)` |
| `r7_bill` / `r7_wert` / `r7_river` | `river_bill_guard` / `river_wert_bremse` / both, each on `r6_button` |
| `r8_gpu` | `river_gpu_guard(r6_button)` |
| **`r8_stack`** | `river_gpu_guard(river_wert_bremse(r6_button))` ← **`auslese.FINAL_STACK`, the champion** |
| `r9_play` | `river_play_guard(river_wert_bremse(r6_button))` |
| `r9_pre` | `stackoff_bremse(no_limp_guard(r8_stack))` — REFUTED (−11,42) |
| `r9_turn` | `turn_gpu_guard(r8_stack, min_pot_chips=5000, iters=80)` |
| `r9_v8` | `stackoff_bremse(river_play_guard(river_wert_bremse(r6_button)))` — deliberately WITHOUT `no_limp` and WITHOUT `turn_gpu` |
| `r10_ernte` | like `r9_v8`, but `min_pot_chips=1500, iters=150, half=True` (fp16) |
| `r10_stack` | `river_plan_guard(river_wert_bremse(r6_button), min_pot_chips=1500, iters=150)` = v10 |
| `r10_h0` | `river_plan_guard(r8_stack, …)` = v10.0 patch "H0-lite" |
The full champion chain from inside out is therefore:
`basis → sel_m15 → turn_wert → button_disziplin → river_wert_bremse → river_gpu` (`pargate.py:80-140`, confirmed
in `../reports/V10_FACTS.md`, A5). The outer wrapper always sees the inner one's decision.
**Input/Output.** `par_gate` returns `{"kandidat","incumbent","kanal","bb100","se","bb100_trim","median_bb100",
"nonzero","nonzero_anteil","nz_pos","vorzeichen_z","nz_median_chips","ci95_lo","ci95_hi","perm_p","workers",
"sekunden","decks_pro_min","verdict","edges"}`. The per-deck edges land in `data/runs/<lauf>/edges.json`.
**Dependencies.** `improver` (the guards), `preflop_guards`, `turn_gpu`, `river_plan`, `duplicate`, `stats`,
`runs` — all hard, but `_wickle` itself is a pure if-chain and rebuilt in 10 minutes.
**Status.** `par_gate` is **resumable**: every finished job block is written to
`data/_pargate_blocks/<kandidat>__vs__<incumbent>__s<seed>__b<deckseed>__c<chunk>/jobNNN.json`; a
restart with identical parameters skips computed blocks and is byte-identical to the run that completed.
The block name carries all result-determining quantities — change code, and you must take a **new deck bank**
(`--deck-seed0`), otherwise you read old blocks.
**Cost.** Measured **3 608–3 897 decks/min** at 20–22 workers (`data/autogym/journal.jsonl:39, :51, :52, :61`).
GPU arms: the code comments say `--workers <= 6`, later corrected to 12 (VRAM 3,7 of 12,3 GB at
6 workers, journal.jsonl:95).
**Measurement status.** MEASURED POSITIVE as an instrument (not as a strategy): the A/A null test (candidate == incumbent)
yields **exactly 0,00 ± 0,00** — proven on 1 936 decks (journal.jsonl:50), 600 decks in the GPU arm (:92) and 576 decks
in the v10 arm (:107). An A/A unequal to 0 has every time been a real bug in the repo (unseeded MC; `hand_id` differing
per mirror half; RNG stream across hands).
**Usable standalone?** `_wickle` yes (pure composition). `par_gate` needs `duplicate` + `stats` + `runs`.
**Pitfalls.** The worker cleans up the environment before every run (`:204-217`): all `POKERB_*` variables are
**deleted**, `OPENBLAS/OMP/MKL_NUM_THREADS = 1` set and `torch.set_num_threads(1)` called. Without the first,
inherited shell flags silently color **both** gate sides; without the second OpenBLAS dies at init; without the third
every worker spawns torch with core-count threads and the parallelization collapses, although all cores look "busy".
All three are documented in the repo as debug evidence. Second pitfall: **`imap_unordered` + `extend`
destroys the deck→edge mapping** — the blocks are therefore assembled ordered by job index (`:255-286`),
otherwise edges are no longer pairable across runs and arms.

---

### Verdict statistics — `pokerbot/autogym/stats.py`
**Purpose.** Turn per-deck chip edges into the verdict — fat-tail-aware, because the classical 2-SE rule is
too optimistic for these distributions.
**Interface.**
`robust_stats(edges, bb=100, trim=0.05, haende_je_deck=2) -> dict` (`:17`) — raw mean + SE in bb/100
(`skala = 1/haende_je_deck/bb*100`), plus trimmed mean, median and the **sparse diagnostics**: `nonzero`,
`nonzero_anteil`, `nz_pos`, `vorzeichen_z`, `nz_median_chips`.
`bootstrap_ci(edges, b=4000, seed=17) -> {"ci95_lo","ci95_hi","perm_p","boot_b"}` (`:59`) — percentile bootstrap +
sign-flip permutation test, which draws **only the non-zero edges** (zeros contribute neither to the resample sum nor to the
flip) → cost `b*m` instead of `b*n`, deterministic.
`verdikt(st) -> "ANWENDEN" | "VERWERFEN" | "NEUTRAL"` (`:93`) — base is the raw mean ± 2 SE; at
`nonzero_anteil < SPARSE_SCHWELLE` (`0.02`, `:90`) the bootstrap interval additionally carries the verdict (`ci95_lo > 0` and
`perm_p < 0.025`).
**Input/Output.** In: list of chip edges per deck (sign = candidate minus incumbent). Out: dicts as above.
**Dependencies.** Only `random` from the standard library.
**Status.** Stateless, deterministic (fixed bootstrap seed).
**Cost.** `bootstrap_ci` = `2 * b * m` additions; at 30 000 decks and a 3 % channel a few seconds. Not measured.
**Measurement status.** MEASURED POSITIVE as a correction: the re-evaluation of all round-5 verdicts with the bootstrap let
`turn_wert` hold (CI `[+2,69; +12,05]`, `p 0,0007`), let `RN05` drop in 2 of 3 runs
(`data/autogym/journal.jsonl:68`, type `ESTIMATOR-V3`). Before that, the 5 % trim had been built in and had to be
**withdrawn**: with thin guard channels (8,4 % or 1 % divergent decks) the trimming removes exactly
the signal decks — the trimmed value was 0,00 at a raw `+1,64` (docstring `:20-28`, journal.jsonl:54).
**Usable standalone?** Yes, completely — 109 lines without project dependency.
**Pitfalls.** The scale assumes **two hands per deck** (HU mirror with seat swap). For the 6-max arena
`haende_je_deck` is set differently — whoever forgets that measures off by the factor of the seat rotation. And: a
`bb100 == 0.00` with `nonzero == 0` does not mean "neutral", but "the guard never fired" (see
`lizenz_guard`, `r7_bill`, `sel_all_m15`).

---

## v10 packages (river foundation)

This subsystem replaces a hand-dependent river heuristic with ONE public river plan solved once per hand:
a hero range is reconstructed without looking at the real hole cards (K1), with it a CFR subgame is solved at the
start of the river (K2), the played sequence is navigated exactly through the tree and the action is sampled privately.
You need this ONLY if you (a) have a GPU river solver, (b) want to rule out the accusation "your range reconstruction secretly
reads its own hand" and (c) are willing to take measurement infrastructure along. **It is NOT shipped:**
the acceptance gate G3 was missed, the champion remained `auslese-v5` (`../reports/V10_GATES_REPORT.md`, section 4).

---

### Contracts (data types + canonicalization) — `pokerbot/strategy/contracts.py`
**Purpose.** Frozen, solver- and strategy-free data types (frozen dataclasses) with hard validation, which all
v10 parts use as a common language — plus the rule for how an engine action is canonicalized to a comparable chip
amount.

**Interface.**
- `karte_int(card) -> int` / `combo_index(c1, c2) -> int` / `combo_kanonisch(c1, c2) -> tuple` — card and
  combo encoding (rank*4+suit, `_RANKS="23456789TJQKA"`, `_SUITS="shdc"`, 1326 combos lexicographic,
  `contracts.py:47-73`); identical to `gpu_cfr.combo_index`.
- `konfig_hash_aus(mapping) -> str` — sha256 over sorted JSON; the fingerprint building block of all packages.
- `ActionKey(kind, chips=None)` with `fold()/check()/call()/raise_to(chips)` and
  `als_engine_aktion(legal) -> (action, amount)` — `bet`/`raise`/`allin` collapse onto `raise_to(chips)`,
  distinguished ONLY via the final integer TO level (`contracts.py:82-121`).
- `kanonisiere(action, amount, state) -> ActionKey` — mirrors the engine rule: `int(amount)` (truncation), then
  silent clamp to `[legal.raise_min, legal.raise_max]`; `allin` = `raise_max` (`contracts.py:124-155`).
- `kanonisiere_history_eintrag(h) -> ActionKey | None` — history line -> key, `deal` -> None; reads only `to`
  (float allowed), NEVER `amount` on `call`.
- `PolicySnapshot.aus_state(state, policy_id, konfig_hash)` — public state WITHOUT any hole card, with
  `pot_bei_strassenbeginn()` (`pot − Σ committed_street`) and `legale_keys()`.
- `RangeState.aus(hero, villain, board, herkunft, konvention, rekonstruktions_status, versions_hash, hero_injiziert,
  hero_rolle)` — two range vectors with board mask; validates hard: board combos EXACTLY 0, no duplicate combos,
  with `konvention="normiert_summe_1"` Σ=1 ± 1e-6, and `herkunft="k1_likelihood"` forbids `hero_injiziert=True`.
- `PolicyTable(aktionen, zeilen, undefiniert, herkunft)` with `p(combo, key)` / `verteilung(combo)` — every row Σ=1;
  `undefiniert` is the place for combos without a strategy (reach 0), and `p()` returns `None` there, not 0.
- `RiverPlan(root, ranges, baum_hash, konfig_hash, knoten, aktueller_pfad, pot_river, schwelle_chips, aktiviert, …)` —
  validates among other things `aktiviert == (pot_river >= schwelle_chips)` (public gating, no raising it after the fact).
- `EntscheidungsTrace(basis, final, texassolver, guards, plan_verteilung, legalitaet, sample_u, fallback_status,
  offtree, deadline_status, hand_adresse, decision_addr)` — validates the causal chain: a genuine mix without `sample_u`
  throws, `final != legalitaet` throws, `offtree=True` without `fallback_status="offtree"` throws.
- Vocabulary tuples: `ACTION_KINDS`, `FALLBACK_STATUS`, `DEADLINE_STATUS`, `REKONSTRUKTIONS_STATUS`,
  `RANGE_KONVENTION`, `RANGE_HERKUNFT`, `PRIVATE_SEED_QUELLE`, `SUMMEN_TOLERANZ = 1e-6` (`contracts.py:31-44`).

**Input/Output.** In: a state `dict` with the keys `players` (per seat `stack`, `committed_street`,
`committed_total`, `hole`), `board`, `street`, `pot`, `current_bet`, `button`, `to_act`, `history`, `bb`, optionally
`legal` (`to_call`, `can_check`, `can_call`, `can_raise`, `raise_min`, `raise_max`, `is_bet`) and optionally `hand_id`.
Out: the named frozen dataclasses; invalid inputs throw `ValueError` instead of passing silently.

**Dependencies.** Only the standard library (`hashlib`, `itertools`, `json`, `dataclasses`). No engine, no torch.
This is the only v10 building block without a hard repo binding — it is fully portable as long as your state dict
carries the keys named above.

**Status.** Stateless (all types frozen). Nothing to reset.

**Cost.** Not measured; pure Python object construction. `PolicyTable.p()` is a linear search over the rows
(`contracts.py:425-434`) — with 1326 rows in a loop that is O(n²).

**Measurement status.** UNMEASURED as an EV effect (by construction: no strategy). The built-in self-test
(`python -m pokerbot.strategy.contracts`, `contracts.py:568`) ran in gate G1 with **250 checks green**
(`../reports/V10_GATES_REPORT.md`, gate table G1; raw file `data/runs/v10/G1_tests.txt`).

**Usable standalone?** Yes, copyable as a single file. Minimally required: bring your state format onto the
intersection keys. The self-test compares `combo_index` against `gpu_cfr.combo_index` when torch is present,
and skips that otherwise.

**Pitfalls.** `EntscheidungsTrace.basis` is annotated as `ActionKey`, but K2 deliberately passes `None` there in the plan
path (annotation unchecked at runtime, documented in the `river_plan.py` docstring). Whoever takes the annotation
seriously and checks statically breaks the only productive caller.

---
### K1 — hero-likelihood replay — `pokerbot/strategy/hero_range.py`
**Purpose.** Reconstructs hero's PUBLIC range at the start of the river forward from prior x board mask x
action likelihood — without reading the real hole cards.

**Interface.**
- `rekonstruiere(st0, guards=STANDARD_GUARDS, hero=None, konvention=K1_KONVENTION, advisor=None) -> K1Rekonstruktion`
  — the main call; returns `hero_range` (canonical combos -> weight, Σ=1), `villain_range` (tracker),
  `status` (`ok` | `teilweise` | `fehlgeschlagen`), `grund`, `pot_river`, `knoten` (log per hero node),
  `heur`/`total` (legality-only steps).
- `hero_range_river_start(st0, guards, hero, konvention) -> dict` — only the range (empty on failure).
- `villain_range_river_start(st0, hero) -> dict` — tracker villain range at the start of the river.
- `range_state_river_start(...) -> contracts.RangeState` — the same as a validated contract; throws on failure.
- `knoten_modell(zustand, seat, guards, konvention, combos, advisor) -> KnotenModell` and
  `action_likelihoods(...) -> PolicyTable` — the executed policy AT ONE node per combo, individually testable.
- `bedingung_turn_wert(zustand, combo, villain_range) -> bool` / `bedingung_sel(...)` — the bit-exact
  guard conditions C(h).
- `prior_range(st0, hero, advisor)`, `knoten_liste(st0, hero)`, `lebende_combos(board)`,
  `schneide_am_river(st0)`, `versions_hash(guards, konvention)`.
- `Konvention(rolle_bet, size_faced, raise_modelliert)`; constants `K1_KONVENTION` (role by INITIATIVE, real
  bet size) and `TRACKER_PARITAET` (role by POSITION, `size_faced=0.66`) — with `guards=()` the latter is
  byte-identical to the tracker hero range.

**Input/Output.** In: a complete hand state (engine form OR GTOW adapter form) with `history` that
contains a `deal` entry with `street == "river"`. Out: `dict[(c1,c2) -> float]` with Σ=1, board combos removed,
plus status and a log per node (`KnotenProtokoll`: `street`, `beobachtet`, `guard`, `guard_ziel`, `n_combos`,
`n_c`, `masse_c`, `modelliert`, `ziel_getroffen`).

**Dependencies.** HARD and deep: `pokerbot.strategy.range_tracker` (prior `_init_preflop`, `_remove_dead`,
`_normalize`, damping `TRACKER_ALPHA`/`TRACKER_AGGRO_FULL`, `_narrow_raise`), `pokerbot.autogym.improver`
(`_RANK_ORD`, `_spot_rng` — the reference for bit-exact C(h)), `pokerbot.engine.equity.equity_vs_weighted_range`,
`pokerbot.engine.evaluator`, `treys` (optional; without treys `turn_wert` never fires), `contracts`,
`knowledge_base.math.formulas.equity_needed_to_call`. The advisor MLPs (`p_bet_batch`/`p_defense_batch`) supply the
base likelihood — if they are missing, the node degrades to `legality-only` and the status becomes `teilweise`.
**Practically nothing is replaceable**: the module is a mirror of YOUR bot. For a foreign bot you must rewrite the
likelihood source (step 2) and the guard transformations (step 3) completely; only the scaffold
(replay of the public history, `_Replay`, `ereignisse`, `_wende_an`) is transferable.

**Status.** Stateless externally (every call builds a fresh `RangeTracker`). No reset needed. There is
NO side effect on RNG or tracker — that is intentional (`knoten_modell` docstring).

**Cost.** High and CPU-bound: per hero node `equity_vs_weighted_range` runs with `GUARD_EQUITY_ITERS = 160`
(`hero_range.py:63`) for EVERY live combo. In the G2 live measurement the K1 range was the latency driver with
**up to 5,7 s per decision** (`../reports/V10_GATES_REPORT.md`, section 6, fix justification for
`K2_LIVE_DEADLINE_S = 12.0`, `pokerbot/autogym/pargate.py:53`).

**Measurement status.** **REFUTED as acceptance — gate G3 MISSED.** Measured against a decide() oracle (offline decide per
hypothetical combo): TV distance **mean 0,2085 · p95 0,758 · max 0,876**; after subtracting the oracle noise floor
(0,095) the lower bound remains **mean 0,1446 · p95 0,620 · max 0,819** — the card's budget was
**0,02 / 0,05 / 0,10**. Even at the action-class level (instead of size) still 0,1037. Additionally: hero's real hand lay in
**21/64** cases outside the K1 support. Source: `data/runs/v10/g3_k1_gate_20260907_231422.json`, cited in
`../reports/V10_GATES_REPORT.md` gate table G3 and findings R1/R3. The EV contribution of the range itself is UNMEASURED.
**Why missed:** the advisor likelihood backend is size-agnostic (knows only bet-vs-check), the real base
chooses sizes hand-dependently — the reconstruction structurally cannot explain a size decision. The biggest
driver are `turn_wert` cases (lower bound 0,325). Additionally the card's assumption "`button_disziplin`
leaves the prior unchanged" is measurably false (oracle support 354 vs 838 combos, finding R3).

**Usable standalone?** No — without `range_tracker`, `improver` and the advisor nets nothing runs. What you can adopt
is the IDEA and the structure (prior -> board mask -> product of the action likelihoods -> normalization, with a
status instead of a silent approximation).

**Pitfalls.** The `KnotenModell.likelihood` contract: `None` means "not modelled" and the caller MUST then leave the
combo unchanged (legality-only), `0.0` means "this combo would never have acted like this". Whoever reads `None` as 0
collapses the range to mass 0 — and `rekonstruiere` then returns status `fehlgeschlagen` with an empty range,
not an exception.

---

### K2 — public river plan — `pokerbot/autogym/river_plan.py`
**Purpose.** A wrapper around an arbitrary strategy factory that, in large river pots, no longer draws the decision
per decision, but from ONE CFR plan solved at the start of the river, and samples privately.

#### Activation
Purely public and street-wide: `ist_aktiviert(st, min_pot_chips) -> (bool, pot_river)` with
`pot_river = pot − Σ committed_street` (`pot_river_aus_state`, `river_plan.py:114-131`). Default threshold
`DEFAULT_MIN_POT_CHIPS = 1500` (= 15 bb at bb=100, `river_plan.py:73`). Activation does NOT depend on the hole cards
nor on the current bet. Below the threshold and outside the river the base runs through unchanged,
without trace (`_entscheide`, `river_plan.py:710-714`).

#### Root reconstruction
`state_am_river_beginn(st)` (`river_plan.py:205`) cuts the history after the river deal
(`river_deal_index`) and rewinds the chips to the start of the river: `committed_street = 0`, `stack += committed_street`,
`committed_total -= committed_street`, `pot = pot_river`, `current_bet = 0`, `to_act = 1 − button` (OOP first) and a
freshly built `legal` block. Without a river deal (silent all-in run-out) there is no root and no plan.
`eff_stack_aus_state` = `min(stack + committed_street)`, invariant across the street.

#### Ranges
`ranges_am_river_beginn(st0, hero_seat) -> RiverRanges | None` (`river_plan.py:283`): villain always via
`RangeTracker().build(st0)`, hero via K1 (`_k1_hero_range`, lazily imported). Accepted K1 statuses are
`("ok", "teilweise")` (`K1_AKZEPTIERTE_STATUS`, `river_plan.py:240`, with written-out justification); only
`fehlgeschlagen`, a K1 import error or an exception fall back to the tracker hero range — with flag
`k1_fallback:<grund>`. Board combos are hard-filtered to 0 (`_ohne_board_combos`). `root_hash_aus` hashes
board + both ranges (quantized to `RANGE_QUANT_STELLEN = 6`) + `pot_river` + `eff` + role + tree + iterations.

#### Solve
`loese_plan(st, hero_seat, hand_adresse, iters=150, half=False, …) -> GeloesterPlan | None` (`river_plan.py:454`)
calls `gpu_cfr.RiverCFRBatch` DIRECTLY (B=1) with the REAL `eff` (no SPR bucket) and `pot_river` in chips; tree
`BAUM_KW = {"bet_sizes": (0.35, 0.75, 1.5), "raise_sizes": (2.7,), "max_raises": 2}` (`river_plan.py:72`),
`DEFAULT_ITERS = 150`, averaged strategy (`avg_sigma`). `gpu_resolver.solve_spots` is deliberately NOT used —
so there is no hero injection and the existing v5 path remains byte-identical. `Zeiten(ranges_s, solve_s,
gesamt_s)` is always measured (`cuda.synchronize` before stopping, `_gpu_fertig`).

#### Navigation
`navigiere(gp, st) -> Navigation(pfad, status, grund)` (`river_plan.py:510`) walks the played river steps
through the tree. Every step must hit an arm to within **±`OFFTREE_TOLERANZ_CHIPS` = 1 chip**
(`arm_index_fuer` / `_passt_raise`) — **no nearest snapping**. A TO level >= `eff` is clipped to `eff` (the
covering villain may bet more). Status `offtree` (villain size not in the tree), `fehler` (`akteur_desync`,
`terminal_erreicht`, `hero_nicht_am_zug`, `kein_river_deal`) or `ok`.

#### Private randomization
`private_u(private_seed, hand_adresse, decision_addr) -> float` = keyed blake2b / 2^64 (`river_plan.py:175`).
Seed origin: `modus="gym"` -> `privater_seed_gym(hand_adresse, seat)` = blake2b with fixed `GYM_SALZ`
(deterministic, so that A/A stays exactly 0); `modus="live"` -> `prozess_seed()` = `os.urandom(16)` once per process;
`privater_seed=` overrides both (`test_seed`). Distribution and sampling are SEPARATE:
`GeloesterPlan.verteilung()` returns the row, `sample_aus_verteilung(probs, u)` chooses. `ist_degeneriert(probs)`
(one p with |p−1| ≤ 1e-6) means argmax WITHOUT a random number — degenerate nodes consume no u.

#### Fallback status
`_fallback` writes a contract status and calls `base(st)`:
- `offtree` — villain size does not hit the tree.
- `deadline` — live: solve not in time (flag `deadline_in_queue` if it did not even begin).
- `hand_not_in_range` — hero's real combo has weight 0 in the public range. The `avg_sigma` row there would be
  uniform 1/n (reach-0 phantom) and must NEVER be read as a strategy; `verteilung()` therefore returns `probs=None`
  (`river_plan.py:403-414`). That is a contract, not a knob.
- `fehler:<Typ>` — solve exception or `root_nicht_rekonstruierbar`.
In plan pots `base(st)` is otherwise NOT called (decision E1) — the underlying resolver is omitted there.

#### Live parallelism
`_LaufenderSolve` per hand: a follow-up decision of the same hand waits on the SAME future (`solve_geteilt`) instead of
solving anew. The deadline counts from solve START; the queue waiting time has its own budget
(`QUEUE_BUDGET_S = 3.0`, `river_plan.py:84`), `LIVE_SOLVE_WORKER = 3` (`river_plan.py:82`). A late result
is discarded for the missed decision, but cached (`plan_verspaetet_genutzt`). `aufwaermen()` absorbs the
CUDA cold start (2-3 s) before the first hand. LRU cache `CACHE_GROESSE = 16` plans per seat; a cache hit with
deviating `pot_river`/`eff`/`button` is discarded (`cache_root_abweichung`).

#### Trace
`_schreibe_trace` writes one JSONL line per plan-pot decision (`trace_pfad`): `version`, `seat`,
`hand_adresse`, `decision_addr`, `fallback_status`, `offtree`, `deadline_status`, `flags` (sorted), `basis`,
`final`, `legalitaet`, `sample_u`, `gewaehlter_arm`, `plan_verteilung`, `pfad`, `root_hash`, `baum_hash`,
`pot_river`, `eff`, `range_herkunft`, `private_seed_quelle` — plus `latenz_ms` and `zeiten_ms`
(`queue`/`ranges`/`solve`/`gesamt`) ONLY in live mode, so that the gym trace stays byte-deterministic.
`statistik(seat)` counts `plan_pot_entscheidungen` and every `fallback_status`.

**Interface (short form).** `river_plan_guard(make_strat, min_pot_chips=1500, iters=150, deadline_s=None,
trace_pfad=None, privater_seed=None, modus="gym", solve_worker=3, queue_budget_s=None, aufwaermen=True)
-> RiverPlanFabrik`; the factory is `f(seat) -> d(st) -> (action, amount)` — the same pattern as the other
guard wrappers. Diagnostics: `letzter_plan(seat)`, `letzter_trace(seat)`, `statistik(seat)`, `basis_aufrufe(seat)`,
`private_seed_quelle`, `private_seed_hex`.

**Input/Output.** In: the same state `dict` as the base strategy (engine or adapter form), ideally
with `hand_id` — otherwise the hand address falls back to a card hash (flag `cache_key_ohne_hand_id`).
Out: `(action, amount)` in engine convention (`amount` = raise TO level), produced by `legalisiere()`
(`river_plan.py:539`): `fold` at `to_call == 0` -> `check`; bet/raise only if the opponent is not all-in and
`stack > to_call`; `betrag >= stack − 1` -> `allin`.

**Dependencies.** HARD: `pokerbot.strategy.gpu_cfr` (`RiverCFRBatch`, `range_vector`) + torch/CUDA;
`pokerbot.strategy.range_tracker`; `contracts`. SOFT/replaceable: `pokerbot.strategy.hero_range` (K1) is imported LAZILY
and falls back cleanly to the tracker — the module runs without K1.

**Status.** Per seat a `_SitzZustand` with LRU plan cache (per hand), running solves, counters and last
trace/plan. The cache lives across hands and is invalidated only via the hand address and the root check
— there is NO explicit `reset()`. Whoever plays hands without a unique `hand_id` must know that.
`_PROZESS_SEED` is a process singleton (live).

**Cost.** Solve measured ~2,5 s per hand, K1 ranges up to 5,7 s (live channel, `../reports/V10_GATES_REPORT.md` section 6).
Live latency after the mechanics fix: p50 3,04 s / p90 8,50 s / p99 10,15 s (n=40, ibid.). One solve runs in a
thread; several solves serialize on the GIL (module docstring, measurement 2026-09-07).

**Measurement status.** MIXED, NEVER anchored live as EV.
- Gym mirror against the champion: `r10_stack` vs `r8_stack`, **n=1968 decks: +11,68 ± 10,85 bb/100, CI95
  [−9,39, +33,06], verdict NEUTRAL, perm_p 0,156** (`data/runs/20260908_002035_pargate_r10_stack/result.json`, cited
  in `../reports/V10_GATES_REPORT.md` gate G5). So **NEUTRAL**.
- Exploitability in the K3 test bench (gym channel, n=11 holdout roots): **ΔE_H = w(A) − w(B) = −10,08 ± 1,66 bb/root =
  −113,0 ± 18,6 bb/100**, all 11 roots negative (= the plan is less exploitable), ΔRegret −4,04 ± 0,99 bb/100
  (gate G4). But: arm A ran in the GYM (without TexasSolver), the magnitude is **not** transferable to live.
- Live mechanics (n=40 plan pots): plan played 25/40, `offtree` 11/40, `hand_not_in_range` 4/40, `deadline` 0/40
  (`../reports/V10_GATES_REPORT.md` section 6).
- Gate G2 (latency) **MISSED**: plan-pot p99 10,15 s ≥ 8 s and v10 p99 > v5-H p99 (8,20 s).
- **The catastrophe source is the fallback, not the plan:** all three gym decks ≤ −100 bb arose in the bare
  base (2x `offtree`, 1x sub-threshold pot), the three pure plan decks were all positive (+219 bb) —
  finding R4, `data/runs/v10/g5_divergenz_replay.log`.
- A/A null test after the last code change: **576 decks EXACTLY 0** (`data/runs/20260908_015248_pargate_r10_stack/
  result.json`).

**Usable standalone?** Yes, if you have (1) a river CFR solver with the `RiverCFRBatch` interface
(`avg_sigma(node)`, `root`, `node.acts/kids/actor/invest`), (2) a villain range source and (3) a
base strategy as `make(seat) -> d(st) -> (action, amount)`. K1 is optional. Without CUDA it runs on CPU torch,
but the latency numbers above then do not apply.

**Pitfalls.** The **size convention of the tree**: `bet{f}` invests `f · pot AT THE NODE` (including all
previous river bets), NOT `f · pot_river`; `raise2.7` invests 2,7 · to_call ADDITIONALLY; arms from 85 %
of the remaining stack coincide with the jam. Whoever reads this wrongly gets `offtree` at every second node and
notices it only from the counter. Second stumbling block: the docstrings of `river_plan_guard` and of the module still name the
OLD values (`LIVE_SOLVE_WORKER = 1`, `QUEUE_BUDGET_S = 0,5 s`, deadline 7,5 s) — the constants are 3 / 3,0 and the
live deadline is set to 12,0 in `pargate.py:53`.

---

### K4 production integrity — runtime fingerprint + misconfiguration gate — `pokerbot/runtime_config.py`
**Purpose.** Answers per process the question "WHICH bot produced this bb/100 number?" — from the live object
and the module constants frozen at import, not from the env intent.

**Interface.**
- `fingerprint_geladen(bot, stack_name) -> dict` — the fingerprint. Mandatory fields (`PFLICHTFELDER`,
  `runtime_config.py:64`): `git`, `advisor_pt`, `prince`, `prince_geladen`, `prince_importflags`, `gto_mode`,
  `gto_mode_flags`, `exploit`, `use_resolver`, `use_turn_resolver`, `stack`, `turn_defense`, `slowplay`,
  `gpu_solver`, `k1_version`, `river_plan`, `private_seed_quelle`, `pythonhashseed`, `pid`, `fingerprint_hash`.
- `fingerprint_hash(fp) -> str` — sha256 over the strategy-relevant part; `_NICHT_IM_HASH = ("pid", "zeit_utc",
  "fingerprint_hash", "python", "advisor_geladen_jetzt")` keeps the hash process- AND warm-up-invariant.
- `pruefe_konfiguration(erwartet, ist)` — `SystemExit` with ALL deviations (not just the first).
- `gatter_aus_env(fp, log=print) -> str | None` — reads `POKERB_ERWARTE_PROFIL`; set = armed, unset = log only.
- Building blocks individually: `git_stand()`, `sha256_datei()`, `advisor_hashes(bot)`, `advisor_geladen_jetzt()`,
  `gpu_solver_version()`, `k1_version()`, `river_plan_konstanten()`, `private_seed_quelle(bot)`,
  `prince_importflags()`, `prince_abweichungen(importflags, exploit)`.
- Profiles: `ERWARTUNGSPROFILE = {"v5-H": {... "stack": "r8_stack"}, "v10": {... "stack": "r10_stack"}}`.

**Input/Output.** In: the living bot object (read are `exploit`, `use_resolver`, `use_turn_resolver`,
`use_probe`, `use_deepcfr`, `use_blueprint`, `use_range_tracker`, `private_seed_quelle`) + the name of the stack
wrapped around `decide`. Out: a flat JSON-able dict + a hash string; or `SystemExit`.

**Dependencies.** HARD on this repo: `pokerbot.config`, `pokerbot.strategy.gto_mode` (`PRINCE_PROFILE`,
`enabled()`, `fingerprint()`), `contracts`. The list `_PRINCE_IMPORTKONSTANTEN` (`runtime_config.py:40-47`) names
env key, module, constant and parser for six flags by name — for another bot that is the only place
you have to rewrite, but it is completely project-specific.

**Status.** Stateless; every call reads afresh. `git_stand()` starts two `subprocess` calls
(`_GIT_TIMEOUT_S = 10`).

**Cost.** Not measured. Dominated by the two git calls and the sha256 hashes of the advisor `.pt` files —
once per process start, not per hand.

**Measurement status.** UNMEASURED as EV (by construction no strategy code). Measured EFFECT: in gate G1
`test_runtime_config` ran with **19 OK, 1 skip** and the misconfiguration gate correctly aborted a v10 expectation run on `r8_stack`
with exit 1 (`../reports/V10_GATES_REPORT.md` gate G1). The reason for the module is a documented damage: the
GTOW harness previously ran without any config check and the HU web app played a never-measured configuration
(module docstring, `HU_OPTIMAL_MAP.md` D1).

**Usable standalone?** The pattern yes, the code no. Transferable are the two ideas that were learned expensively here:
(1) distinguish **env intent** from **frozen import state** — if a strategy module is imported BEFORE an
env variable is set, the constant stays wrong forever, while the intent query reports "on";
(2) take runtime state (which nets the lazy cache currently holds) out of the hash, otherwise it flips after warm-up
and two chunks of the same arm are no longer comparable.

**Pitfalls.** `prince_importflags()` imports the strategy modules itself. If you call the fingerprint too early —
before setting the env — you freeze the constants with the wrong env and the fingerprint still reports
"OK", because it measures exactly what is loaded now. Order: set env, then build bot, then fingerprint.

---

### K4 hand ledger — `pokerbot/benchmark/gtow_ledger.py`
**Purpose.** Append-only JSONL ledger that writes every hand event of a benchmark run to disk IMMEDIATELY, so that
an abort loses nothing and a restart knows the open hands.

**Interface.**
- `GtowLedger(pfad=None)` with `prozess_start(fingerprint)`, `hand_start(hand_id, arm, fingerprint_hash)`,
  `hand_end(hand_id, aivat, winnings, status, technische_events=())`, `offene_haende()`.
- File-based readers: `lese(pfad)`, `abgleich(pfad) -> {offen, abgeschlossen, doppelt_gestartet}`,
  `offene_haende(pfad)`, `offene_haende_alle(verzeichnis)`.
- Process singleton + exception-free hooks: `standard_ledger()`, `melde_hand_start(agent, hand_id)`,
  `melde_hand_ende(agent, hand_id, terminal, status="ok", technische_events=())`.
- `STATUS = ("ok", "unbekannt", "fehler")`; `python -m pokerbot.benchmark.gtow_ledger` lists open hands.

**Input/Output.** In: `hand_id`, an arm name (env `POKERB_ARM`, else `agent.stack_name`, else class name),
a fingerprint hash, and at the end a terminal object (`GameServiceResponse` with `game_state.aivat_score` /
`.winnings`, or a mapping). Out: one JSONL line per event with `typ`, `zeit`, `pid` — file
`data/runs/v10/ledger_<prozess-start>.jsonl`, overridable via `POKERB_LEDGER_PFAD`.

**Dependencies.** Only `pokerbot.config` for the directory; the agent hooks access defensively via `getattr`.
Practically replaceable by three lines of your own code — the value lies in the rules, not in the code.

**Status.** Per process a singleton with sets `_gestartet`/`_beendet`, which are reconstructed FROM THE FILE on
construction (a double start is detected across process boundaries too). `schreibfehler` is counted and
appended on the next successful write.

**Cost.** One `flush()` + `os.fsync()` per event — deliberately expensive. Not measured.

**Measurement status.** UNMEASURED (no EV effect possible). Documented reason: the old harness wrote the
hand histories only AFTER all hands with `open('w')`, **chunk 4 of night 2 was completely lost**
(module docstring, `../reports/V10_FACTS.md` A8). In gate G1 process abort and ledger write fault were tested
(`../reports/V10_GATES_REPORT.md`, section 2).

**Usable standalone?** Yes, a single file without real dependencies (except the directory).

**Pitfalls.** The hard rule sits in `hand_end`: `status == "ok"` with `aivat is None` is automatically downgraded to
`"unbekannt"` — **an unknown outcome is NEVER imputed as 0**. Whoever "simplifies" this line when porting
gets a clean-looking mean out of missing data.

---

### K3 — policy oracle (the executed policy as a table) — `research/policy_oracle.py`
**Purpose.** Delivers the distribution of the ACTUALLY executed bot policy per hero combo at a river node as
`contracts.PolicyTable` — so that an existing heuristic becomes evaluable in the same game as a solver.

**Interface.**
- `PolicyOracle(kanal="gym", seeds=4, workers=4, stack="r8_stack", cache_dir=CACHE_DIR)`.
- `.tabelle(root_hash, st, hero_seat, combos=None) -> (PolicyTable, meta)` — only uncached combos are
  computed, the cache file carries the union of all requests.
- `.direkt(st, hero_seat, combos, seeds) -> {(combo, seed): key_str}` — reference actions of the FULL chain for the
  identity test.
- `.roh(root_hash, st, combos)` — per seed/label the final and the base action (making the surgery visible).
- `.schliessen()` — terminate the pools (mandatory, otherwise the processes hang).
- Free helpers that other v10 tools import too: `lebende_combos(board)`, `combos_mit_masse(vektor)`,
  `zustand_nach_pfad(root_state, pfad, hero_seat)` (engine chip accounting), `legal_fuer(st, seat, min_raise)`,
  `mit_hole(st, hero_seat, combo)`, `knoten_hash(st)`, `erster_hero_knoten(root)`, `code_fingerprint()`,
  `chirurgie(a, amt, st, res, …)` (the GPU guard rule as a pure function).
- CLI: `python -m research.policy_oracle --split entwicklung --roots 2 --seeds 2 --kanal gym --workers 4`.

**Input/Output.** In: an engine state at the hero node + the `root_hash` of the root. Out: `PolicyTable` (rows
per combo, `undefiniert` for combos without a row) + `meta` with `herkunft`, `fehler`, `gpu_solve_fehler`, `gueltig`,
`sekunden`, `sekunden_gpu`. Cache files under `data/runs/v10/policy_oracle_cache/`, key
`(root_hash, knoten_hash, kanal, S, stack, code_fingerprint)`.

**Dependencies.** HARD and maximally project-specific: it decomposes exactly ONE known stack composition
(`r8_stack == river_gpu_guard(r7_wert)`, `pargate.py:100-108`) into "base decide per combo over S seeds" plus
"surgery rule". Furthermore `pokerbot.autogym.pargate._baue_fabrik`, `pokerbot.strategy.gpu_resolver.solve_spots`,
torch/CUDA, `contracts`. The constructor throws if `stack != "r8_stack"`.

**Status.** Two `multiprocessing` pools (spawn): a CPU pool for the decide() calls, a Pool(1) for the
GPU solves (the GPU is never shared by several processes — 12 workers ran into CUDA OOM, which the guard silently
swallowed). Plus a disk cache. `schliessen()` is mandatory; the workers set the channel env BEFORE the bot import.

**Cost.** MEASURED (RTX 3080 Ti, 150 iter fp32): **209 ms/spot at max_batch=192, 215 ms at 64** —
bandwidth-bound, the batch size brings nothing; **1081 combos ≈ 226 s per GPU node** (module docstring,
`policy_oracle.py:26-33`). Hence `GPU_BATCH_MAX = 64` (2,7 GB peak instead of 5,3 GB). The full holdout (224 roots)
was estimated at **≈ 33 h cold** (`../reports/V10_GATES_REPORT.md`, section 2, row G4).

**Measurement status.** Validated as a tool, not as a strategy: the identity test against the DIRECT decide() of the
full chain ran **60/60** and the K3 controls in total **15/15 green**
(`data/runs/v10/g4_logs/kontrollen_tests.log`, cited in `../reports/V10_GATES_REPORT.md` gate G1).
The `--kanal live` (PRINCE + resolver ON) fell to `UNSUPPORTED` in the G4 pilot (473 s for the narrowest root,
`REACH_EPS` inconsistency) — the live channel is thus **UNMEASURED**.

**Usable standalone?** No. The idea is transferable (query your own policy with swapped hole cards
over S seeds and read the result as a distribution), the code is not.

**Pitfalls.** A table run with `gpu_solve_fehler > 0` is NOT cached and is invalid — whoever uses the
return value without `meta["gueltig"]` computes with half tables. And: the `code_fingerprint()` belongs in
the cache key, otherwise an old policy survives every code change in the cache.

---

### K3 — river best-response test bench — `research/river_br_pruefstand.py`
**Purpose.** Evaluates two hero policies (existing heuristic vs solver plan) in the SAME river root game with exact
villain best response — the only place in the repo that substantiates "less exploitable" as a number.

**Interface.**
- `bewerte_root(root, orakel=None, arm_a="purify", villain_familie="tracker") -> dict` — one root.
- `baue_baum(pot, eff, bets_je_rolle, raises_je_rolle, …) -> Node`, `knoten_mit_pfad`, `zusatzarme`.
- `br_gegen_fest(spiel, root, sigma_fest, spieler_br) -> (wert, vektor)` — EXACT best response, information-set-
  faithful (villain maximizes per OWN combo against the hero-reach-weighted sum).
- `garantiewert(spiel, root, sigma_hero, hero_rolle)`, `lokaler_regret(cfr_q, root, spiel, sigma_pi, hero_rolle)`,
  `reach_je_knoten`, `sigma_aus_cfr`, `sigma_auf_baum(sigma_quelle, baum_quelle, baum_ziel, rolle)`,
  `purifiziere(sigma)`.
- `sigma_arm_a(orakel, root, spiel, r_hero, hero_rolle)` — builds the evaluation tree by iterative CLOSURE
  (hero arms = K2 tree ∪ exact chip amounts of the heuristic per node, max `MAX_SCHLIESSUNGSRUNDEN = 3`).
- `aggregiere(ergebnisse, n_haende, n_roots_ge_schwelle)`, `schreibe_report(name, konfig, ergebnisse, agg)`.
- `Unsupported` — root not representable; is REPORTED, never projected.
- CLI: `python -m research.river_br_pruefstand --split holdout --arm-a oracle --kanal gym --seeds 4 --workers 8
  --roots 224 --zeitbudget-s 5400 --name …`; `--arm-a` in `("purify", "identisch", "oracle")`.

**Input/Output.** In: a root dict from `research/k3_roots.py` (`board`, `pot_river`, `eff`, `hero_oop`,
`ranges`, `root_state`, `hand_id`, `provenienz`). Out per root: `w_a_bb`, `w_b_bb`, `delta_e_h_bb`, bracket
`L_bb`/`U_bb`, `e_h_a_band_bb`, `regret_a_bb`, `regret_b_bb`, `delta_regret_bb`, `expl_b_pct_pot`,
`n_knoten_eval`, `n_zusatz_arme`, `status` (`ok` | `UNSUPPORTED` + `grund`). Aggregate: mean + SE per root and
`bb100_alle_haende` (mean x 100 x selection weight = roots ≥ threshold / all hands of the split).

**Dependencies.** HARD: torch, `pokerbot.strategy.gpu_cfr` (`RiverCFRBatch`, `Node`, `range_vector`,
`showdown_matrix`), `research.policy_oracle`, `research.k3_roots`, `contracts`. `--arm-a purify`/`identisch`
need NO oracle — so the test bench runs as a pure solver tool.

**Status.** Stateless per root; the oracle (if used) carries its pools and the cache.

**Cost.** Per root: one 150-iter solve (arm B) + one 600-iter solve (Q verdicts) + in oracle mode the
node tables (~0,21 s GPU per combo). `--zeitbudget-s` aborts in a controlled way and reports that in the report.
11 roots ran through in a 5400-s budget (`../reports/V10_GATES_REPORT.md` gate G4).

**Measurement status.** Tool validated (matching-pennies fixture, card fixture ≤1e-6, A/A exactly 0, oracle identity
60/60 — **15/15 green**, `data/runs/v10/g4_logs/kontrollen_tests.log`). Result gate G4: **INCOMPLETE** —
ΔE_H **−10,08 ± 1,66 bb/root = −113,0 ± 18,6 bb/100** (bootstrap UB95 −85,4), 11/11 roots negative; ΔRegret
**−4,04 ± 0,99 bb/100**; sensitivity with villain=preflop null: −126,2 ± 16,8 (same sign);
UNSUPPORTED 0/11. **Why incomplete:** the card demanded ≥ 20 roots and arm A in the LIVE channel; measured were
11 roots in the GYM channel (the live pilot `G4_pilot_live_2981343.json` ended `UNSUPPORTED`). Live the champion plays
the TexasSolver in 93 % of river decisions — the magnitude is therefore not transferable, only the direction.

**Usable standalone?** The solver part yes (`--arm-a purify` compares the averaged CFR strategy against its own
purified version — a clean self-test without any bot dependency). The oracle part only with this repo.

**Pitfalls.** Two expensively learned traps sit in the code as comments: (1) arm B is solved on the K2 tree and
MUST be mapped by label onto the evaluation tree before evaluation (`sigma_auf_baum`) — otherwise the
columns are shifted as soon as the closure adds an arm; (2) the upper bound U must be computed on the
EVALUATION TREE, not on the K2 tree, otherwise the band is mislabelled. And:
`SIZE_TOL_CHIPS = 1.0` is intentional — an 8 % tolerance window projected 0,67-pot bets onto 0,75.

---

### K3 — river roots from hand histories — `research/k3_roots.py`
**Purpose.** Extracts per source hand EXACTLY ONE river root (state before the first river action) from logged
hand histories and persists geometry, engine state and both ranges as JSONL.

**Interface.**
- `dateien_je_split(split) -> {Dateiname: Provenienz}` — `holdout` = four files fixed by name,
  `entwicklung` = the arms from `research.hh_luecken_mine.ARME`.
- `extrahiere_roots(dateien, split) -> (roots, ausschluss_zaehler, n_haende)`.
- `schreibe_roots(split, roots, zaehler, n_haende, dateien) -> Path` — JSONL with header line.
- `lade_roots(split, min_pot=0.0) -> (kopf, roots)` — ranges converted back into combo-tuple dicts.
- `river_sequenz(riv, hero_seat)`, `root_hash(board, pot_river, eff, hero_oop, vill)`,
  `range_als_json` / `range_aus_json`.
- CLI: `python -m research.k3_roots --split entwicklung` or `--split holdout`.

**Input/Output.** In: JSONL hand histories from `data/sessions/` (one hand per line with `hand_id`, `aivat`,
`winnings` and the actions). Out: `data/runs/v10/k3_roots_<split>.jsonl` — header line with `n_haende`, `n_roots`,
`ausschluss`, `hero_k1`, `pot_river_ge_1500`; then per root `board`, `pot_river`, `eff`, `hero_seat`, `button`,
`hero_oop`, `hero_hole`, `seq_river`, `aivat_bb`, `win_bb`, `root_hash`, `hero_k1_status`,
`ranges.{hero_tracker, vill_tracker, hero_k1}` and `root_state` (the live-faithful engine state).

**Dependencies.** HARD on this repo's replay chain: `research.gtow_tree_census` (`BB`, `hero_seat_of`,
`replay`), `research.hh_luecken_mine` (`ARME`, `SESS`, `replay_voll`), `research.river_bill_replay.spot_state`,
`pokerbot.strategy.range_tracker`. K1 is imported LAZILY (if missing: `hero_k1_status="fehlt"`, no abort).

**Status.** Stateless; writes one file per split.

**Cost.** Not documented as a number (the CLI prints the runtime per run). The holdout split has **224 roots**
(`../reports/V10_GATES_REPORT.md` gate G4).

**Measurement status.** UNMEASURED (data preparation). The exclusion counters are the honesty channel:
`aivat_none`, `hero_seat_none`, `kein_river`, `rekonstruktion` (pot gate |pot_eigen − pot| > 1 chip), `eff_null`,
`range_leer` — they stand in the header line of every output file.

**Usable standalone?** No, not without the replay chain. Transferable is the discipline: ONE root per hand,
exclusions counted instead of silently dropped, the `holdout` split frozen by name.

**Pitfalls.** The holdout split comes from a run with DIFFERENT provenance (`v4_gym_nackt`, exploit ON,
resolver OFF). Only root geometry and villain range from it are usable — hero's actions back then are
explicitly NOT a teaching signal (module docstring).

---

### Golden set / divergence smoke — `research/golden_set.py`
**Purpose.** Proves byte-identity of a reference policy BEFORE and AFTER an infrastructure change, by running two
stacks against each other on N fixed decks and landing the edge PER DECK on disk.

**Interface.** CLI only + one internal function:
`python -m research.golden_set --a r8_stack --b basis --decks 40 --seed 424242 --out <datei>.json` produces the
run; `python -m research.golden_set --vergleich ALT NEU` prints `IDENTISCH` or `ABWEICHUNG in Decks [...]` and
sets the exit code (0/1).

**Input/Output.** In: two stack names from `pargate`, deck count, seed. Out: JSON with `a`, `b`, `decks`,
`seed`, `sek_je_deck`, `edges` (list per deck), `nonzero`, `summe`.

**Dependencies.** `pokerbot.autogym.pargate._baue_fabrik`, `pokerbot.benchmark.duplicate` (`duplicate_ab`,
`gen_decks`), torch (only to pin the thread count). Replaceable by any paired duplicate runner.

**Status.** Stateless. Deliberately sets `OPENBLAS/OMP/MKL_NUM_THREADS=1`, `torch.set_num_threads(1)` and **removes
all `POKERB_*` env variables** (`golden_set.py:20-24`) — the gate channel is flag-free.

**Cost.** `sek_je_deck` is in every output file; no reference value fixed in the repo.

**Measurement status.** Passed as a tool: in gate G2a `r8` vs `basis` was **pre == post IDENTICAL** and the
golden A/A over 40 decks had **nonzero 0** (`data/runs/v10/golden_r10_AA_v2.json`,
`golden_r8_vs_basis_post_g2a.json`, cited in `../reports/V10_GATES_REPORT.md` gate G2a).

**Usable standalone?** Yes, if your repo has a paired deck runner. The tool is 60 lines and the benefit
lies in the rule, not in the code.

**Pitfalls.** `--vergleich` checks `edges`, `a`, `b` and `seed` — but NOT whether the deck bank was
changed in between or a different code revision ran. Two "identical" runs with different deck counts
silently compare only the prefix (`zip`).

---
### G3 acceptance tool: K1 oracle — `research/k1_oracle.py` + `research/g3_k1_gate.py` + `research/g3_k1_census.py`
**Purpose.** Measures how far the K1 range deviates from the actually executed policy (TV distance), by querying the
stack at every hero node with SWAPPED hole cards over S seeds; `g3_k1_gate.py` is the
stratified gate run around it, `g3_k1_census.py` the preliminary census of the guard frequencies.

**Interface.** CLI-driven:
`python -m research.k1_oracle --n 6 --seeds 8 --workers 4` (pilot) or
`python -u -m research.g3_k1_gate --zensus-n 300 --n 64 --je-klasse 16 --seeds 12 --workers 8 --zeitbudget-s 4200`.
`g3_k1_gate.waehle(vgs, n, je_klasse, klassen)` implements the stratification (first `je_klasse` histories
per guard class, then fill up with `keine`).

**Input/Output.** In: gym decks in self-play of the stack; the engine states before every hero decision are
RECORDED (no replay). Out: `data/runs/v10/k1_oracle_<ts>.json` or `g3_k1_gate_<ts>.json` with
`tv_k1_vs_orakel` (mean/p95/max), `tv_k1_korrigiert_untere_schranke`, the noise floor, the metrics per
guard class, the sample check and `urteil_roh`/`urteil_budget`.

**Dependencies.** `pargate._baue_fabrik`, `pokerbot.strategy.hero_range`, `duplicate.gen_decks`,
`multiprocessing` (spawn). The channel `gtow` (live) is provided as a switch, but **not wired** — the
call ends with `SystemExit` and a clear message.

**Status.** Process pool; results per history, time budget aborts in a controlled way and reports the reduction.

**Cost.** MEASURED (n=6, 14 nodes, 12 workers): **S=8 -> noise floor 0,122 | S=32 -> 0,050 (600 s) |
S=64 -> 0,033 (1124 s)**, i.e. ≈ 1/√S; 64 histories at S=64 ≈ 3,3 h; a floor ≤ 0,010 would have demanded S ≈ 3000
(module docstring `k1_oracle.py`, reports `data/runs/v10/k1_oracle_20260907_18*/19*.json`).
The gate run went with S=12 (floor 0,095, 55 min).

**Measurement status.** Tool functional, verdict **MISSED** (see K1 above). Two tool findings are
transferable and documented in the code: (1) a SHARED seed across all combos turns the estimated
probability into a step function with S common thresholds instead of an empirical distribution —
fix: `seed_eff = keyed_hash(seed, Knoten-Adresse, combo)`; (2) pure MC had a noise floor of 0,20 at S=8 =
as large as the measured signal — fix: the bot's first `random()` is stratified onto the grid point (k+½)/S.
The budget verdict is only issued if the noise floor is ≤ half the mean budget, otherwise it reads
`orakel_zu_grob` or `unterpowert`.

**Usable standalone?** No (depends on `pargate` + K1). The two tool findings above are what is transferable.

**Pitfalls.** The overall mean of the gate run is a STRATIFIED mean (guard cases
over-represented) — it is conservative upward and must not be cited as a natural rate. The
class metrics are unbiased per class.

---

### G2 latency measurement — `research/v10_latenz.py`
**Purpose.** Measures the wall time of `decide()` of both arms on identical, real river states in a
fresh subprocess each with live env — and reads the K2 trace along.

**Interface.** CLI: `--bau` (generate state list), `--probe N` (N decisions per arm + extrapolation),
`--messe --n 150 --plan-min 50` (full measurement), `--bericht` (evaluation of existing raw JSONL only), `--tag`.

**Input/Output.** In: `data/runs/v10/k3_roots_entwicklung.jsonl`; per hero river decision the state
BEFORE the action is reconstructed with `policy_oracle.zustand_nach_pfad` and mirrored onto hero=seat 0. Out:
`G2_latenz*.json` + `.md` + raw JSONL per arm + the K2 trace of the candidate. Stratified by pot class
(< 1500 / ≥ 1500), position (IP/OOP) and facing (check/bet); cold start is reported separately.

**Dependencies.** `research.k3_roots`, `research.policy_oracle`, `pokerbot.benchmark.gtowizard.PokerBotAgent`
(built directly, so that fingerprint + K4 gate run along), `subprocess`.

**Status.** Stateless; a fresh subprocess per arm.

**Cost.** The full measurement was estimated at **~15 min** and NOT started
(`../reports/V10_GATES_REPORT.md`, section 2, row G2).

**Measurement status.** Tool ran; gate **G2 MISSED**. Probe n=10: plan-pot p99 (= maximum) 7,55 s, overall p99 v10
7,55 s > v5-H 5,54 s, 0 calls ≥ 30 s, K2 trace plan played 1/10, `deadline` 7/10, `hand_not_in_range` 2/10
(`data/runs/v10/G2_latenz_probe10.json`, `gate_urteil.status = VERFEHLT_REDUZIERTE_STICHPROBE`). After the
mechanics fix (n=40): `deadline` 0/40, plan played 25/40, `offtree` 11/40, `hand_not_in_range` 4/40,
p50/p90/p99 = 3,04 / 8,50 / 10,15 s vs v5-H 2,10 / – / 8,20 s — **formally still missed** (p99 ≥ 8 s and
v10 > v5-H); the driver is the K1 computation, not the solve (`../reports/V10_GATES_REPORT.md`, section 6).

**Usable standalone?** No. Transferable is the design: same states, fresh processes per arm, cold start
separate, strata fixed beforehand.

**Pitfalls.** The measurement calls `PokerBotAgent._decide` directly and sequentially — the real harness plays 5–8
hands in parallel. The queue/deadline effect live is therefore rather STRONGER than measured here (ibid., section 2).

---

### K5 — GTOW night schedule — `research/gtow_nacht_v10.py`
**Purpose.** Driver for the live benchmark: runs two arms in a chunk sequence fixed BEFOREHAND by coin toss,
with env hygiene, ledger reconciliation, event classification and pre-registered stop rules.

**Interface.** CLI: `--plan` (prints sequence + env, starts nothing), `--smoke N --arm B`, `--nacht 1`,
`--nacht 2`, `--fazit-gesamt`.

**Input/Output.** In: the arm definitions (`A = PRINCE + r8_stack`, `B = PRINCE + r10_stack`, both WITHOUT
RAISE_NARROW), the coin `data/runs/v10_muenze.json` (`BAAB_dann_ABBA`), an API key. Out: manifest
`data/runs/v10/gtow_manifest_v10.json` (written after EVERY chunk), journal entries
`V10-GTOW-VORREGISTRIERUNG` / `-CHUNK` / `-NACHT-FAZIT` / `-GESAMT-FAZIT`, plus per chunk a K2 trace path
(`POKERB_K2_TRACE`) and a ledger.

**Dependencies.** `tools/gtow_run.py` (fresh subprocess per chunk, timeout 10800 s, max 3 retries),
`pokerbot.benchmark.gtow_ledger` (lazy), `clear_inprogress` (409-orphan duty before EVERY start and retry),
`pokerbot.autogym.pargate` via `POKERB_AUSLESE_STACK`.

**Status.** Manifest-driven; every run reads the previous candidate chunks as history, so that the
stop counters run over the ENTIRE live test (smoke + both nights).

**Cost.** 4 x 500 hands per night; the pre-registered statement reckons with SE ≈ 6,77 bb/100 for the ENTIRE test
(4 block pairs: 214·√(2/500)/√4), 9,57 per single night.

**Measurement status.** UNMEASURED as a result — **the series was never run for v10** (ship decision: not
GTOW-ready, `../reports/V10_GATES_REPORT.md` section 4; STATE.md: "no tag auslese-v10-rc, no G6 series"). The
driver itself is tested: **31/31 green** (`tests/test_gtow_nacht_v10.py`, gate G1). R6 remains blocking: the
channel for `illegal` (`legalisiert:<von>-><nach>` in `technische_events` + fingerprint field) does not exist —
grep 0 hits — therefore every night ends by construction with `kein_verdikt`.

**Usable standalone?** No (bound to the GTOW API). Transferable is the construction: the sequence is fixed BEFOREHAND
and there is no code path that reads it and writes it differently depending on the result; and: **a 0 without a channel is
not a measurement** — if the event channel is missing, that is recorded in the manifest as `kanal='fehlt'`, not as 0.

**Pitfalls.** The harness aborts the WHOLE chunk on every non-busy HTTP error (busy = 409/502/503/504).
Therefore EVERY attempt is evaluated and summed over attempts; an `http_4xx` does NOT lead to a blind retry
(two further 500s would be burned hand IDs).

---

### Wiring point — `r10_stack` / `r10_h0` in `pokerbot/autogym/pargate.py`
**Purpose.** Defines HOW the river plan is hooked into the stack chain — not a module of its own, but the place
where an outsider reads the composition.

**Interface.** `_wickle(name, basis, kanal="gym")` (`pargate.py:69`) and `_baue_fabrik(name, seed)`.
- `r10_stack` (`pargate.py:173-186`): `river_plan_guard(river_wert_bremse(r6_button(basis)), min_pot_chips=1500,
  iters=150, **_k2_kanal_kw(kanal))` — the same chain as the champion, but the hand-dependent GPU surgery
  (`river_gpu_guard`) is REPLACED.
- `r10_h0` (`pargate.py:187-192`, user patch 2026-09-10): `river_plan_guard(r8_stack(basis), …)` — "H0-LITE": the
  plan sits on the COMPLETE v5 chain, so a fallback never lands below the champion. That is the direct
  answer to finding R4 (catastrophes in the bare fallback).
- `_k2_kanal_kw(kanal)` (`pargate.py:58-67`): `modus`, `trace_pfad` from `POKERB_K2_TRACE`, and in the live channel
  `deadline_s = K2_LIVE_DEADLINE_S = 12.0` (`pargate.py:53`).
- Consumption: `pokerbot.strategy.auslese.wickle_decide(pb, stack=None, kanal="live")` wraps the stack dict-preserving around
  `PokerBot.decide` and passes `private_seed_quelle` through to the K4 fingerprint (`auslese.py:52-70`);
  `FINAL_STACK = "r8_stack"`, `RC_STACK = "r10_stack"` (`auslese.py:34-35`).

**Input/Output.** In: a stack name + a base factory. Out: a factory `f(seat) -> d(st) -> (action, amount)`.

**Dependencies.** HARD on the guard collection in `pokerbot.autogym.improver` and `preflop_guards`.

**Status.** The returned wrapper holds the K2 state (plan cache per seat).

**Cost.** See K2.

**Measurement status.** `r10_stack`: see K2 (gym mirror NEUTRAL, +11,68 ± 10,85 bb/100, n=1968). **`r10_h0`:
UNMEASURED** — so far only a diagnostic run via the Kaggle bridge exists
(`data/runs/kaggle_v10h0_vs_champion_2026-09-10.log`); commit `d22d400` records: A/A exactly 0, and after the
fix of a missing `deal` marker in the Kaggle adapter, in the sample **1 plan played, 1 offtree**. That is
a mechanics check, not a verdict.

**Pitfalls.** `kanal="live"` switches on deadline AND `os.urandom` seed — so the run is no longer
deterministic. Every paired gate (A/A must be EXACTLY 0) MUST run with `kanal="gym"`.

---

### Gate runners (collective entry) — `research/g1_gate_runner.py`, `g4_auswertung.py`, `g5_spiegel_auswertung.py`, `g5_deck_replay.py`, `g5_divergenz_auswertung.py`
**Purpose.** One-off scripts that each execute one gate or condense its raw data into a verdict (test collection run,
bootstrap evaluation of the test bench, mirror statistics, deterministic replay of individual divergence decks,
divergence post-mortem).

**Interface.** Each a CLI with `--haupt/--sens/--name`-style arguments; the exact commands are in the
source column of `../reports/V10_GATES_REPORT.md`, section 1.

**Input/Output.** In: the raw artifacts under `data/runs/v10/` or `data/runs/<ts>_pargate_*/`. Out: the
cited reports (`G1_tests.txt`, `G4_holdout.{json,md}`, `G5_BERICHT.json`, `g5_divergenz_replay.log`,
`g5_katastrophen_trace.jsonl`).

**Dependencies.** On the respective measurement modules and the artifact paths; no strategy code.

**Status.** Stateless.

**Cost.** Not measured (evaluation, seconds to minutes; `g5_deck_replay` replays decks).

**Measurement status.** UNMEASURED (tools). Known gap: the G1 runner did NOT write the block
`test_river_br_pruefstand`, the log ends after `test_river_plan` and `G1_summary.json` is missing —
the evidence for this block comes from a separate run of the same code version
(`../reports/V10_GATES_REPORT.md`, gate G1 "gap").

**Usable standalone?** No — pure project scripts.

**Pitfalls.** They assume that the artifacts come from EXACTLY one code revision. In the v10 run G1,
G2a, G3 and G4 partly ran in PARALLEL (contrary to the house rule "one worker fleet at a time") — the latency appendix of
`test_river_plan` is therefore considered contaminated and is not cited (ibid., section 2, last row).

---

### The missed gates — summary for an outsider

| Gate | What was checked | Verdict | Why |
|---|---|---|---|
| G1 tests/invariants | 13 test/smoke blocks | GREEN (composite) | all exit 0; one block is missing from the main log and comes from a second run of the same code version; `pytest` was not installed, the module runner was used |
| G2a A/A + golden | determinism after code change | PASSED | 576 decks EXACTLY 0, golden pre == post |
| **G2 latency** | p99 < 8 s, v10 ≤ v5-H, no call ≥ 30 s | **MISSED** | n=10 probe: 7,55 s > 5,54 s; after mechanics fix n=40: p99 10,15 s vs 8,20 s. The driver is the K1 CPU-MC computation per combo, not the GPU solve. Full measurement never started |
| **G3 K1 acceptance** | TV(K1, decide oracle) ≤ 0,02 / 0,05 / 0,10 | **MISSED — the blocker** | lower bound after noise subtraction 0,1446 / 0,620 / 0,819. Structural cause: the likelihood backend knows only bet-vs-check, the base chooses sizes hand-dependently; additionally the assumption "button_disziplin leaves the prior unchanged" is measurably false. Card: "G3 missed -> K2 NOT released" |
| **G4 holdout test bench** | ≥ 20 roots, arm A LIVE | **INCOMPLETE** | 11 roots in the GYM channel (time budget; live pilot UNSUPPORTED). Direction unambiguous (11/11 less exploitable), magnitude −113 bb/100 NOT transferable to live |
| G5 mirror + export | no catastrophe | PASSED (with finding) | +11,68 ± 10,85 bb/100 NEUTRAL; 1 deck each ≥ 150 bb in both directions. **Post-mortem: all three decks ≤ −100 bb arose in the FALLBACK to the bare base, never in the plan** — the three pure plan decks were all positive |

**Decision (binding, `../reports/V10_GATES_REPORT.md` section 4): v10 (`r10_stack`) is NOT GTOW-ready; the state
remains `auslese-v5` (`r8_stack`).** What a re-release would need: (1) a size-aware likelihood backend for K1
plus clarification of `button_disziplin` and the support leak; (2) fallback target = full v5 chain instead of bare base
(exactly that is the `r10_h0` patch of 2026-09-10, unmeasured) and an off-tree treatment of villain sizes
(27 % live, 42 % in the large gym divergence decks); (3) the legalization channel, otherwise every live night ends by
construction with `kein_verdikt`; (4) G2 full measurement and G4 up to n ≥ 20 in the live channel. Every change = new hash =
all gates anew.

---

## Measurement infrastructure

This subsystem answers exactly one question: **is bot version B better than bot version A — and in a way that the answer is not card luck?** The core is duplicate poker (the same deck twice with swapped seats), around it lie a parallel driver across all CPU cores, a decision rule with pre-registered thresholds, a mathematics oracle as a second, independent instrument and a run store that binds every verdict to commit + configuration.

You need it as soon as you have more than one bot version. Without paired measurement a bb/100 number from a few hundred hands is pure noise — in this repo plausible fixes were repeatedly built in after naive measurement and refuted later. If you build only ONE bot and never change it, you can skip this chapter; as soon as you iterate, it is the most expensive part you would have to rebuild yourself.

Everything here is pure CPU work, runs locally, costs nothing but time and depends only on `multiprocessing`, your own engine and your own strategy factory.

---

### The binding rules (adoptable, independent of the code)

These four rules are not convention in the repo, but acceptance conditions. They are cheaper to rebuild than the code and save more.

**1. A/A null test before every measurement series.** Before candidate is measured against incumbent, the same arm runs against itself. The result must be **exactly 0** — every per-deck difference 0, not "close to 0". If it is not, there is an uncontrolled noise source (unseeded Monte-Carlo equity, set iteration, RNG stream across hands, thread count) and the whole measurement series is worthless. Evidence that this is no ritual: `data/runs/INDEX.jsonl` shows on 2026-09-07 two A/A runs of the same arm `r10_stack`, 576 decks — the first `-9.4 ± 10.92` (run `20260907_213225_pargate_r10_stack`, cause: `hand_id` was assigned differently per mirror half), the third after the fix `bb100 0.0, se 0.0, nonzero 0/576` (`data/runs/20260907_220348_pargate_r10_stack/result.json`). Without the A/A test the difference would have been booked as an effect.

**2. Three-runs rule before every christening.** A candidate gets a name/tag only when it replicates on **three fresh deck banks** (different `deck_seed0`). Reason: in the repo two premature christenings after a single positive run were prevented (`CLAUDE.md`: "no name without 3 runs"). Measured example of why: `tag_flatfix` vs `tag`, three runs of 2992 decks each → `+17,7±6,4 (ANWENDEN)` / `+11,4±6,9 (NEUTRAL)` / `+19,2±7,0 (ANWENDEN)` (journal `FLATFIX-6MAX-VERDIKT`, 2026-09-09). A single run alone would have said "NEUTRAL" or "ANWENDEN" depending on chance.

**3. Channel vocabulary.** A measurement channel may only use words that fit its evidential power. In the repo:
- Self-play mirror against the incumbent (`pargate`, `pargate6`) → `ANWENDEN` / `NEUTRAL` / `VERWERFEN`. That is ship evidence.
- Measurement against a FOREIGN reference opponent (`envgate` vs `GTOBaseline`) → `KANAL_POSITIV` / `KANAL_NEUTRAL` / `KANAL_NEGATIV` (code: `envgate.py:118`). That is explicitly **not** ship evidence, only sign + spew canary.
- External anchor (commercial solver/leaderboard) → that is the only absolute truth, but expensive and scarce.
The reason for the separation is measured: the arm `prince` wins in the mirror and loses in the `envgate` channel raw −68 bb/100, because there it plays against an exploitable opponent with exploit switched off (`envgate.py:39-41`). Whoever labels both channels with the same word ships artifacts.

**4. Decision only via the one pre-registered rule, never after seeing the numbers.** The rule is in `stats.verdikt` (below in detail) and is not adjusted per case. Additional rules learned from damage: one worker fleet at a time (RAM); the quiet channel (candidate vs candidate) beats the loud one (candidate vs base); measure channel width BEFORE building (if only 1 % of decks diverge at all, you need different statistics than at 40 %).

---

### Duplicate gate (core) — `pokerbot/benchmark/duplicate.py`
**Purpose.** Plays every fixed deck twice with swapped seats, so that the card luck cancels out exactly and only the skill difference remains.

**Interface.**
- `gen_decks(n, seed=0) -> list[(hole0, hole1, board5)]` — n fixed deals, each from a fresh shuffle without replacement.
- `duplicate_ab(make_a, make_b, decks, start=20000, sb=50, bb=100, return_edges=False, hand_id_basis=0) -> (bb100, se[, edges])` — A's card-adjusted edge over B in bb/100 plus standard error; `return_edges=True` additionally returns the per-deck chip differences (prerequisite for paired deltas across several configurations).
- `naive_ab(make_a, make_b, hands, ...) -> (bb100, se)` — the same measurement WITHOUT variance reduction, exists only for the contrast proof.
- `gto(seed=1, **params)` / `pokerbot(exploit=False, seed=1, value_raise_eq=0.72, **flags)` — the two bundled strategy factories.
- `_setup_fixed(g, h0, h1, board5, button, start)` — sets fixed cards into a running `HeadsUpGame` (internal, but also used by `gym_hu` and `orakel_duell`).

**Input/Output.** Inputs are **factories**, not bots: `make_strat(seat) -> decide(state) -> (action, amount)`. `state` is the engine state dict with `to_act`, `street`, `pot`, `current_bet`, `board`, `players[i]{hole, stack, committed_street, all_in}`; `duplicate_ab` additionally injects `state["hand_id"]` (see pitfalls). Output: `bb100 = mean(edges)/2/bb*100` (2 hands per deck), `se` analogously, `edges` as a chip list.

**Dependencies.** `pokerbot.engine.cards`, `pokerbot.engine.game.HeadsUpGame` (hard — the engine is the legality truth), `pokerbot.strategy.gto_baseline.GTOBaseline` (only for the factory `gto()`, replaceable). The principle itself is engine-agnostic: you only need an engine into which cards and button can be hard-set.

**Status.** Stateless across runs; WITHIN a run ONE `HeadsUpGame` instance is reused and set up anew per deck. The factories are called fresh per mirror half — a bot with opponent memory would break the pairing (exactly for that there is `exploit_jagd`).

**Cost.** Pure CPU. Measured via `pargate`: CPU-only arms ~2.500 decks/min at 12 workers (`data/runs/INDEX.jsonl`, run `20260830_202416_pargate_r7_river`: 30.000 decks in 723,2 s = 2.489 decks/min). Memory negligible (one chip number per deck).

**Measurement status.** MEASURED POSITIVE as an instrument: A/A over 576 decks yields `bb100 0.0, se 0.0, nonzero 0` (`data/runs/20260907_220348_pargate_r10_stack/result.json`) — the null channel is exact, not just small. The variance-collapse range "10-50x" claimed in the docstring is a **design claim**; the factor is measured by `python -m pokerbot.benchmark.duplicate` itself, a fixed number for it does not exist in the repo.

**Usable standalone?** Yes, this is the most easily extractable building block of the whole project. Minimally required: a HU engine with settable cards + two strategy factories. ~70 lines.

**Pitfalls.** The default stack is `start=20000` at `bb=100`, i.e. **200 bb deep** — not 100 bb. `pargate` inherits this default, `pargate6` on the other hand plays 100 bb (`START_STACK=10000`). Whoever compares numbers from both channels compares two different games.

---

### Decision statistics — `pokerbot/autogym/stats.py`
**Purpose.** Converts a list of per-deck chip differences into a verdict — by a rule fixed BEFORE the measurement.

**Interface.**
- `robust_stats(edges, bb=100, trim=0.05, haende_je_deck=2) -> dict` — location/spread raw and trimmed, plus sparse diagnostics.
- `bootstrap_ci(edges, b=4000, seed=17, bb=100, haende_je_deck=2) -> dict` — percentile bootstrap + sign-flip permutation test, both only over the non-zero edges.
- `verdikt(st) -> "ANWENDEN" | "NEUTRAL" | "VERWERFEN"` — the decision rule.

**Input/Output.** In: `edges` = chip differences per deck (candidate minus incumbent, summed over all mirror halves/rotations of the deck). Out (load-bearing keys): `n_decks`, `bb100` (raw mean, scaled `1/haende_je_deck/bb*100`), `se`, `bb100_trim`, `median_bb100`, `nonzero`, `nonzero_anteil`, `nz_pos`, `vorzeichen_z`, `nz_median_chips`; from the bootstrap `ci95_lo`, `ci95_hi`, `perm_p`, `boot_b`.

**The rule verbatim (`stats.py:93-110`).**
1. Base is the **raw** mean ± 2·SE.
2. `ANWENDEN` if `bb100 − 2·se > 0`.
3. `VERWERFEN` if `bb100 + 2·se < −1.0` — note the **asymmetry**: the lower bound is −1 bb/100, not 0. That is a deliberate tolerance band ("non-regression"), so that a neutral candidate is not rejected on every bit of noise.
4. Otherwise `NEUTRAL`.
5. **Sparse clause:** if `nonzero_anteil < SPARSE_SCHWELLE` (0.02, `stats.py:90`), the bootstrap interval carries the verdict: `ANWENDEN` only additionally at `ci95_lo > 0` AND `perm_p < 0.025`; `VERWERFEN` only additionally at `ci95_hi < −1.0`. Otherwise `NEUTRAL`.

Why exactly so — both are damage history: The 5 % trim was originally the decision statistic (fat-tailed per-deck edges). After the spot-RNG seeding fix (A/A exactly 0) the run heterogeneity disappeared, and the trim became harmful: with thin channels (e.g. 1 % divergent decks) a 5 % trim removes exactly the signal decks (`stats.py:19-31`, estimator v2). The trim remains as a diagnostic field, but no longer decides. The sparse clause came afterwards, because the CLT-2SE under-covered at ~55 effective divergence decks out of 12k (`stats.py:59-66`).

**Dependencies.** None except the standard library (`random`). Completely extractable.

**Status.** Stateless. The bootstrap is deterministic (fixed `seed=17`).

**Cost.** `bootstrap_ci` costs `b*m` draws with m = number of non-zero edges (not `b*n`) — at 4000 repetitions and a few thousand non-zero decks fractions of a second.

**Measurement status.** UNMEASURED as a lever of its own — it is a decision rule, not a bot feature, and has no bb/100. Its calibration is indirectly documented: A/A yields `verdict NEUTRAL` at `bb100 0.0` (loc. cit.), and the estimator switch v1→v2 is documented in the docstring with the reason (turn_wert 8,4 % / raise_narrow 1 % divergent decks).

**Usable standalone?** Yes, immediately — `edges` list in, verdict out. That is the cheapest import from this repo.

**Pitfalls.** `bootstrap_ci` uses `random.Random.binomialvariate`, which exists **only from Python 3.12**. On 3.11 the call dies with `AttributeError` — and only at the end of a long run, after the compute time has already been burned.

---

### HU parallel gate — `pokerbot/autogym/pargate.py`
**Purpose.** Runs `duplicate_ab` across all CPU cores on disjoint deck blocks and delivers a finished verdict including run storage.

**Interface.**
- `par_gate(kandidat, n_decks, workers, seed=1, deck_seed0=1000, incumbent="basis") -> dict` — the gate; the return contains all `robust_stats`/`bootstrap_ci` fields plus `verdict` and `edges`.
- `_wickle(name, basis, kanal="gym")` — **the one source of the stack composition**: translates an arm name (`"r8_stack"`, `"turn_wert"`, …) into the nested guard wrappers around a finished strategy factory. The export channels import this function too, so that a diverging copy is never graded.
- `_baue_fabrik(name, seed)` — `_wickle` around the `duplicate.pokerbot(exploit=True)` base.
- CLI: `python -m pokerbot.autogym.pargate --kandidat <name> --incumbent <name> --decks N --workers W --seed S --deck-seed0 B`.

**Input/Output.** Inputs are **names** from the constant `KANDIDATEN` (`pargate.py:18-52`), not objects — deliberately, because closures are not picklable under Windows `spawn`. Output: `result.json` + `edges.json` in the run folder, one line in `data/runs/INDEX.jsonl`, verdict on stdout. Intermediate states: every finished job block is stored as `data/_pargate_blocks/<kand>__vs__<inc>__s<seed>__b<bank>__c<chunk>/jobNNN.json`.

**Dependencies.** `duplicate.py` (hard), `stats.py` (hard), `runs.py` (storage, replaceable), `improver.py` + `preflop_guards.py` + `river_plan.py` + `turn_gpu.py` (only for the concrete arm names — the mechanics themselves know no strategy).

**Status.** Per run. Worker processes are sanitized: all inherited `POKERB_*` env variables are deleted, `OPENBLAS/OMP/MKL_NUM_THREADS=1` set, `torch.set_num_threads(1)` (`pargate.py:200-224`). **The block cache is persistent state and must be discarded on a code change** (see pitfalls).

**Cost.** Measured (`data/runs/INDEX.jsonl`): CPU-only arms 30.000 decks in ~700 s at 12 workers (~2.500 decks/min); arms with GPU river solver 115–390 decks/min (e.g. `r8_stack` vs `r6_button`, 30.000 decks, 6 workers, 7.725 s = 233 decks/min). For GPU arms the code carries the requirement `--workers <= 6` (`pargate.py:36`).

**Measurement status.** MEASURED POSITIVE as an instrument: A/A `r10_stack` vs `r10_stack`, 576 decks, `bb100 0.0 / se 0.0 / nonzero 0`, 212,9 s (`data/runs/20260907_220348_pargate_r10_stack/result.json`). As a producer of bot verdicts it has delivered among others: `sel_guard` +4,7 ± 2,06 (99.000 decks, ANWENDEN) and `mdf_guard` −3,26 ± 2,19 (99.000 decks, NEUTRAL) — both `data/runs/STAND.md`.

**Usable standalone?** Only together with `duplicate.py` + `stats.py`. The arm name list is project-specific and must be replaced by your own; the scaffold (job split, env hygiene, ordered block assembly, resumability) is transferable.

**Pitfalls.** The block cache is **not** keyed by code version — only by arm names, seeds and block size. If you change the strategy code and start with the same parameters, the run silently mixes old and new blocks. The repo solves that by convention ("one fresh deck bank per code revision", `deck_seed0` 1080000/1090000/1100000/1110000 are used up) and in an emergency by hand: under `data/_pargate_blocks/` lies a folder `_STALE_hand_id_2k_half__r10_stack__vs__r10_stack__s1__b1080000__c12` — a bank manually renamed into quarantine. Second pitfall: `chunk = n_decks // (workers*4)`, so the actual deck count is rounded down (600 requested at 12 workers → 576 played).

---

### 6-max parallel gate — `pokerbot/autogym/pargate6.py`
**Purpose.** Transfers the duplicate principle to a multiplayer table: one deck is played n times, the hero rotates over all seats.

**Interface.**
- `par_gate6(kandidat, incumbent, n_decks, workers, seed=1, deck_seed0=5000, n_seats=6, liga=LIGA, fabrik_spec="pokerbot.autogym.pargate6:held_fabrik", env_fn=arm_env) -> dict`
- `gen_decks6(n, seed, n_seats=6) -> list[(holes[n_seats], board[5])]`
- `spiele_block(held, decks, deck_id0, n_seats, liga, seed) -> {"chips": [...], "prince_decisions", "kern_fallbacks", "illegal_fallbacks", "fingerprint"}`
- `held_fabrik(name)` — the standard heroes; **swappable** via `fabrik_spec` as a string `"modul:funktion"` (that is how `exploit_gate` uses the same arena with its own heroes).
- `arm_env(name) -> dict` — the env flags an arm receives in the fresh process; likewise swappable via `env_fn`.

**Input/Output.** In: arm names + deck parameters. The **hero contract** is what matters if you hook in your own bots: the object needs `decide(obs) -> {"action", "amount"}`, `new_hand(seats)`, `observe(actor, street, action, to_call, preflop_raises)`; optionally `setze_sitz(seat)` (otherwise `.seat` is set), `bind_table(table)`, `.hand_id`, `.fingerprint`, `.rng`. Out: the same statistics fields as `pargate`, plus `bb100_kandidat` / `bb100_incumbent` (absolute values per arm against the league), `aa_exakt_null`, `zaehler` (fallback counters per arm), `fingerprints`.

**Structure of the rotation (`pargate6.py:134-165`).** Button fixed on seat 0; in rotation `r` the hero sits on seat `r`, seat `s` carries the league profile `LIGA[(s − r − 1) % 6]`. Thus the hero sees every position exactly once, and every hole pair is played once by the hero and once by every villain profile. Villain RNGs are seeded per `(deck, rotation, seat)`; the villain objects live across the whole job block, so that their opponent models can collect observations — **same `--workers` = same learning windows**, otherwise two runs are not comparable.

**Dependencies.** `pokerbot.engine.table.Table` (hard — N-player engine with side pots), `pokerbot.arena.sixmax` (the league; replaceable by arbitrary opponents), `stats.py`, `duplicate.HAND_ID_STRIDE_JE_DECKSEED`, `runs.py`.

**Status.** Per job block. Every job runs in a **fresh process** (`mp.Pool(workers, maxtasksperchild=1)`), because the arm env flags are read at import time and would otherwise mix across reused pool processes. No block cache (unlike `pargate`) — an abort loses everything.

**Cost.** Measured: `tag_flatfix` vs `tag`, 2992 decks × 6 rotations × 2 arms in **90,4 s** at 8 workers (`data/runs/20260909_214905_pargate6_tag_flatfix/result.json`). With the heavy hybrid hero: the same deck count in 1.038–1.671 s (`20260909_190405_pargate6_hybrid_r8`, `20260909_183613_pargate6_hybrid_r10`).

**Measurement status.** MEASURED POSITIVE as an instrument (A/A `tag` vs `tag`, 288 decks, EXACTLY 0 — journal `VERDRAHTUNG-6MAX-VERDIKT`, 2026-09-09) and as a producer of sharp verdicts: it refuted the 6-max "Prince takeover" (hybrid −23,56 ± 9,02 / hybrid_r8 −21,73 ± 9,01 / hybrid_r10 −26,61 ± 8,93 vs `tag`, 2992 decks each, all VERWERFEN) and confirmed the flat fix (+17,7/+11,4/+19,2 over 3 runs).

**Usable standalone?** Yes, provided your engine offers `obs_for(seat)` / `legal_actions()` / `act()` and you can hard-set cards. `fabrik_spec` + `env_fn` are explicitly built as foreign hook-in points.

**Pitfalls.** `aa_exakt_null` in the result is **only meaningful when `kandidat == incumbent`** — with different arms it always says `False` (`pargate6.py:227`). Whoever reads the field as a "measurement was clean" traffic light reads nonsense. The A/A must be run as a separate run.

---
### Env pair gate — `pokerbot/autogym/envgate.py`
**Purpose.** Measures flags that are read at **import time** and are therefore process-global — in the normal gate they would color both arms simultaneously.

**Interface.** Essentially a CLI: `python -m pokerbot.autogym.envgate --decks 12000 --arme prince,k3_deception --referenz-wrapper sel_m15`. Internally: `_arm_lauf(...)` (child mode, activated via `--arm-lauf`), `ARME` (dict arm name → `{"env": {...}, "wrapper": <pargate-Arm-Name>}`, `envgate.py:36-61`).

**Input/Output.** In: arm names from `ARME`. Every arm runs as a **subprocess** with a hygienic env (all `POKERB_*` of the parent stripped, `PYTHONHASHSEED=0`, BLAS threads 1, then exactly the arm flags) and plays its carrier stack against the env-INSENSITIVE `GTOBaseline` on identical, ordered decks. The parent forms paired per-deck deltas `Arm − Referenz`. Out: `edges_<arm>.json` per arm (incl. `fingerprint()` of the loaded configuration) and a `result.json` with `{arm: {...stats..., "verdict": "KANAL_*", "kanal": "envgate_vs_gtobaseline", "arm_spec": {...}}}`.

**Dependencies.** `pargate._baue_fabrik` (hard, same carrier stack as the mirror gate), `duplicate.gto` as reference opponent, `stats.py`, `pokerbot.strategy.gto_mode` (`apply()` + `fingerprint()`), `runs.py`.

**Status.** Per run; the mandatory null arm `referenz` (empty env, same wrapper) always runs first and defines the pairing base.

**Cost.** Not measured as a throughput number in the repo. The order of magnitude follows from the design: one full pass is `len(arme)+1` complete `duplicate_ab` runs of `--decks` each (default 12.000).

**Measurement status.** MEASURED, but as a **subordinate channel**. Delivered numbers: combo arm `kombi_r5` replicated 3× `+25 … +36` vs the v3 reference; cumulative finale vs frozen base `v3 +21,4` → `v4 +49,8` (`data/runs/STAND.md`, addendum 2026-08-18 00:36). REFUTED as a ship channel: the arm `prince` measures here a **channel artifact** of raw −68 bb/100, because exploit-OFF plays against an exploitable baseline (`envgate.py:39-41`) — in the mirror and live the same arm is the validated champion. Hence the hard rule `envgate results are called KANAL_* and are NEVER ship evidence` (`CLAUDE.md:386`).

**Usable standalone?** Only if your bot has import-time flags at all. If it does not (everything configurable via constructor), you do not need this module — then `pargate` suffices.

**Pitfalls.** The measured effect is always "arm against a FOREIGN reference opponent", never "arm against the incumbent". An arm can clearly win here and be exactly neutral in self-play. That is not a weakness of the implementation, but the honest limit of the channel — it is in the docstring and was nevertheless paid for expensively once.

---

### Exploit gate — `pokerbot/autogym/exploit_gate.py`
**Purpose.** Checks with a pre-registered criterion whether the opponent-exploitation channel (Dirichlet opponent model) is correctly wired at all and earns money.

**Interface.**
- `gate_profil(profil, n_decks, workers, seed, deck_seed0) -> dict` — one league profile, exploit ON vs OFF.
- `gate_sixmax_reads(...) -> dict` — the 6-max variant (`tag_reads` vs `tag`).
- `kriterium(profil, res) -> "korrekt" | "VERLETZT" | None` — the pre-registered rule.
- `held_fabrik(name)` / `ProjektierterPokerBot` — the hero that connects a HU bot to the `pargate6` arena via the grader projection.
- CLI: `python -m pokerbot.autogym.exploit_gate --decks 600 --workers 8 --sixmax`.

**The criterion verbatim (`exploit_gate.py:94-104`).** Against **exploitable** profiles (`station`, `maniac`, `nit`, `whale`): `bb100 >= 0` AND `ci95_lo > −3.0`. Against profiles where exploit must not cost anything (`tag`, `shark`): `bb100 + 2*se >= 0`. `lag`/`rock` are informational only.

**Input/Output.** In: profile names. Out per profile `{profil, bb100_on, bb100_off, diff_bb100, se, ci95, verdict, fingerprints, aa_exakt_null, n_decks, sekunden, kriterium}`; in the overall result `exploit_korrekt` (bool) + list `verletzt`.

**Dependencies.** `pargate6.par_gate6` with `n_seats=2` (hard — it is the arena), `pokerbot.coach.oracle.PrinceOracle`, `pokerbot.arena.hybrid.HybridHero._record` (the state projection), `pokerbot.runtime_config.fingerprint_geladen` (the proof that the arm switch really took effect).

**Status.** Per hand/per block. Important: the **adaptation protocol** must be fed — `observe_opponent(...)` per opponent action and `observe_hand_end(...)` at hand end, otherwise the Dirichlet model stays empty and the test measures nothing by construction (this error happened once in the repo and is noted in the docstring).

**Cost.** Measured: 592 decks per profile in 25–32 s (`data/runs/20260909_192123_exploit_gate/result.json`); the full run over 8 profiles + 6-max took a few minutes.

**Measurement status.** MEASURED — and the result is **REFUTING for the checked channel**: all eight point estimates ≤ 0, pooled approx. −12 bb/100; `exploit_korrekt: false`, violated `[nit, station, maniac, whale]` (source: `data/runs/20260909_192123_exploit_gate/result.json`; individual values: nit −2,09 ± 9,52 · tag −19,26 ± 15,35 · lag −18,50 ± 12,96 · station −17,35 ± 16,31 · maniac −15,74 ± 9,61 · rock −0,31 ± 8,97 · whale −8,26 ± 17,01 · shark −14,40 ± 13,67, 592 decks each). 6-max reads ON vs OFF: +3,64 ± 13,45 NEUTRAL. Consequence in the repo: exploit stays OFF everywhere (journal `EXPLOIT-GATE-VERDIKT`, 2026-09-09).

**Usable standalone?** Only with `pargate6` + a bot that has an opponent model. The **pattern** (measure one feature against opponent archetypes ON/OFF paired, with a pass criterion noted beforehand) on the other hand is immediately transferable and the cheapest way to demystify an unmeasured "exploit layer".

**Pitfalls.** A single profile at 592 decks has SE ~9–17 bb/100 — most individual verdicts are formally `NEUTRAL`. The statement only emerges from the fact that **all eight signs** point in the same direction. Whoever reads only one row finds "no effect".

---

### Oracle duel — `pokerbot/autogym/orakel_duell.py`
**Purpose.** Holds the same two arms that `pargate` compares in chips against the mathematics oracle — as a second, independent instrument with a side-effect panel.

**Interface.** `duell(kandidat, incumbent, n_decks, workers, seed=1, deck_seed0=1000) -> (dict, rows)`; CLI `python -m pokerbot.autogym.orakel_duell --kandidat turn_wert --incumbent sel_m15 --decks 1500`.

**Input/Output.** In: two `pargate` arm names. Both play the same decks with seat swap; **every decision is booked to the respective strategy**. Out per arm: `decisions`, `gelegenheiten` (counters `check_gelegenheit_{turn,river}` / `facing_bet_{turn,river}`), `zielklassen_je_gelegenheit` (e.g. `verpasster_wert_turn_je100`), `rate_je_1000` (all oracle rules per 1000 decisions), `severity_bb_summe`. Additionally it writes `decisions.jsonl.gz` into the run folder (all flagged decisions + 3 % sample, with strategy label).

**Dependencies.** `oracle.py` (hard), `pargate._baue_fabrik` (hard), `duplicate._setup_fixed`/`gen_decks`, `runs.entscheidungs_logger`.

**Status.** Per run. Important detail: the F tier (frequencies) is **not** finalized per chunk, but the raw data is passed up and pooled once in the parent — otherwise the n≥30 minimum per street is never reached in the chunk and the whole tier is silently dead.

**Cost.** Not recorded as a throughput number in the repo; the cost is dominated by the hindsight equity (`EQ_ITERS=200` Monte Carlo per flagged decision).

**Measurement status.** MEASURED as an instrument (it delivered the side-effect panel for `turn_wert`, pre-registered in `runde5b.py:16-19`: `verpasster_wert_turn` must fall, `bet_braucht_unplausible_folds` must not rise, HART = 0). It has no bb/100 number of its own by construction.

**Usable standalone?** Only together with `oracle.py` and an arm name list.

**Pitfalls.** The normalization. Rates "per 1000 decisions" are **not** comparable between arms, because a more aggressive arm changes the hand lengths and thus the denominator. Therefore the code normalizes the target classes per **eligible opportunity** (`check_gelegenheit_*`, `facing_bet_*`) and separately by street. Whoever rebuilds this and picks the wrong denominator measures hand length instead of quality.

---

### Mathematics oracle — `pokerbot/autogym/oracle.py`
**Purpose.** Turns the formula collection into machine-checkable verdicts on individual self-play decisions, separated by robustness.

**Interface.**
- `grade_decision(rep, rec, bb=100) -> bool` (True = this decision was flagged) — the main call.
- `grade_hand_conservation(rep, before, after, hand_no, bb=100)` — the HART tier.
- `finalize_frequencies(rep)` — the F tier, only at the end of a run over all collected `facing_bets`.
- `manifest() -> {"verdrahtet_v0": [...], "offen": [...]}` — the honest state of the formalization.
- Data types: `Verdict(tier, rule, severity_bb, proof)`, `OracleReport(decisions, hard, provable, leads, freq, facing_bets)` with `.counts()`.

**The four tiers (and why the separation matters).**
- **HART** — never-adjustable invariants, currently only chip conservation. A violation is a bug, not style.
- **P** — per decision provably dominated actions, currently only `free_fold` (fold at `to_call = 0`). The only class that may be patched automatically.
- **L** — "leads": hindsight equity against the ACTUAL opponent hand with a large margin. Individually noisy, aggregated a leak detector. Never a proof. Rules: `call_unter_pot_odds` (margin 0.15), `fold_ueber_pot_odds` (0.30), `allin_call_ohne_odds` (range-free, via the optimistic 21-outs upper bound), `bet_braucht_unplausible_folds` (required fold frequency > 0.75), `verpasster_wert_{turn,river}` (check with strong made hand and hindsight equity ≥ 0.75), `verpasster_raise`.
- **F** — fold frequency per street against the MDF band (0.10), only from n ≥ 30 per street, and **only over-fold** is a finding.

**Input/Output.** `rec` is a flat dict: `street`, `pot`, `to_call`, `action`, `amount`, `hero_hole`, `board`, `villain_hole` (None if multiway/unknown), `call_closes_action`, `effective_stack`, `n_opponents`. Output is the mutated `OracleReport`.

**Dependencies.** `knowledge_base.math.formulas` + `postflop_formulas` (hard — the formulas are immutable in the project), `pokerbot.engine.equity.equity_vs_hand`, optionally `treys` for the made-hand class (falls back cleanly to `None`).

**Status.** The `OracleReport` collects over the whole run; `facing_bets` must be completely filled before `finalize_frequencies` runs. The hindsight equity is **record-bound deterministic**: `_rec_rng` seeds from `(hero_hole, villain_hole, board, street, pot)` via CRC32, so that the same decision gets the same verdict across runs and processes.

**Cost.** Measured in the pilot: 3.577 graded decisions (500 hands, HU + 6-max) in **52,2 s** locally, incl. playing (`data/autogym/report_20260816_192735.json`). The cost driver is `EQ_ITERS = 200` Monte-Carlo iterations per equity call.

**Measurement status.** MEASURED as a detector: pilot HART 0 / P 0 / L 35 / F 3 on the healthy bot (`report_20260816_192735.json`); the very first pilot run reported HART 40 — that was a bug in the **checker itself**, not in the bot (`report_20260816_192554.json`; the chip-conservation balance counted `committed` wrongly). As a SOURCE of improvement the balance is mixed: the guards derived from L/F `mdf_guard` (−3,26 ± 2,19, n=99.000) and `podds_guard`/`lizenz_guard` were booked REFUTED or NEUTRAL in the gate (`data/runs/STAND.md`); the selection-based guards (`sel_guard` +4,7 ± 2,06, n=99.000) carried. Core lesson of the project from that: **selection beats frequency** — which hands, not how often.

**Usable standalone?** Yes, `grade_decision` is a pure function over a dict. Minimally required: your formulas + an equity function. The rest is ~250 lines without foreign state.

**Pitfalls.** The **pot conventions of the formulas are opposite** and specifically commented in the code (`oracle.py:139-146`): `minimum_defense_frequency` wants the pot BEFORE the bet, `equity_needed_to_call` the pot INCLUDING it. The code therefore stores `pot − to_call` for the F tier and `pot` for the L tier. Whoever mixes these up gets an oracle that judges systematically and quietly wrong. Second point: L findings are hindsight against ONE opponent hand, never against a range — they are hypotheses, not proofs.

---

### HU gym — `pokerbot/autogym/gym_hu.py`
**Purpose.** Lets the HU bot play against itself on paired decks and keeps the books: position value, symmetry drift and every decision through the oracle.

**Interface.** `run(n_pairs=200, seed=7, exploit=True, eq_iters=120, start=20000, bb=100) -> dict`.

**Input/Output.** In: only numbers. Out: `disziplin`, `haende`, `abbrueche`, `button_netto_bb100`, `paar_drift_bb100`, `paar_drift_se`, `orakel` (the counter short form) and `orakel_report` (the object itself).

**The 4-block.** Every deck is played **four times**: holes × button fully crossed (`(h0,h1)/btn0`, `(h0,h1)/btn1`, `(h1,h0)/btn0`, `(h1,h0)/btn1`). With a mere button swap only the position cancels out, not the cards — the symmetry check would be practically powerless. In the 4-block both cancel exactly, and `paar_drift` must tend to 0.

**Dependencies.** `duplicate._setup_fixed`/`gen_decks` (hard), `pokerbot.engine.game.HeadsUpGame`, `pokerbot.strategy.bot.PokerBot`, `oracle.py`.

**Status.** Per run. The two bots live across all hands (module constant `EQUITY_ITERS` is set at construction). On a hang (>500 actions) the hand is **not** booked and no HART verdict is issued — otherwise an abort would be a false chip-conservation finding.

**Cost.** Measured: 300 HU hands + 200 6-max hands + oracle + gate self-test together 52,2 s (`data/autogym/report_20260816_192735.json`); a later run with 600 HU hands 75,3 s incl. everything (`report_20260816_195830.json`).

**Measurement status.** MEASURED: button net (the card-adjusted value of the position) **+32,65 bb/100** at 300 hands or **+33,43** at 600 hands (both reports above) — two independent runs, consistent. Pair drift 300 hands: +294,0 ± 194,6; 600 hands: +106,8 ± 70,3 — both within 2·SE of 0, so E2 passed, but with a very wide band.

**Usable standalone?** Yes, if you have a HU engine and a bot. The 4-block is what is actually transferable and rebuilt in ~15 lines.

**Pitfalls.** `run()` returns the non-serializable `orakel_report` object along — whoever writes the result directly to JSON gets a `TypeError`. The caller must `pop` the key beforehand (that is what `run_local.py:59` does). And: the pair drift still has a band of ±70 bb/100 even at 600 hands — it is a symmetry alarm, not a precision measurement.

---

### 6-max gym — `pokerbot/autogym/gym_six.py`
**Purpose.** The same for the multiplayer table: self-play of the 6-max core with position ledger, chip conservation and oracle.

**Interface.** `run(n_hands=300, seed=7, n_players=6, profile="tag", start=10000, bb=100) -> dict`.

**Input/Output.** Out: `disziplin`, `haende`, `abbrueche`, `position_bb100` (net per position label BB/SB/UTG/HJ/CO/BTN), `orakel`, `orakel_report`.

**Dependencies.** `pokerbot.arena.sixmax` (PROFILES + SixMaxBot), `pokerbot.engine.table.Table`, `oracle.py`.

**Status.** Fresh table per hand (deterministic seed `seed*100003 + h`, rebuy-free), so that chip conservation remains cleanly checkable — but the **bots live persistently across all hands**. Both are necessary: bots created anew per hand could never fill their opponent models, and without the `new_hand()` call `pf_aggressor = None` remains, whereby the complete c-bet branch would be unreachable (measured: `cbet_policy` 0× in 300 hands without protocol, 143× with).

**Cost.** Measured: 200 hands as part of the 52,2-s pilot (`report_20260816_192735.json`).

**Measurement status.** MEASURED: position ledger over 30.000 hands — `BB −28,9 · SB −29,6 · UTG +6,8 · HJ +15,8 · CO +2,4 · BTN +33,5` bb/100; facing-bet catalog `flop fold_freq 0,216 · turn 0,297 · river 0,337` (journal `RUNDE4-6MAX-KATALOG`, 2026-08-17). At the pilot sizes (200–300 hands) on the other hand the position numbers are noisy in the three digits (`BTN +335,6`, `report_20260816_192735.json`) — unusable.

**Usable standalone?** Yes, with an N-player engine. The ledger is the valuable part: position values are a card-poor, fast-converging control quantity.

**Pitfalls.** The **L tier of the oracle is dead here by construction** — multiway there is no unique hindsight opponent hand, `villain_hole` is passed as `None`, and all L rules hang on it. In all pilot reports therefore `"L": 0` for 6-max. That is not a clean bot, that is a switched-off detector.

---

### Self-test of the loop — `pokerbot/autogym/selftest.py`
**Purpose.** Checks in one command four pre-registered expectations of the measurement machinery itself, before one believes its bot verdict.

**Interface.** `python -m pokerbot.autogym.selftest [--quick]`; internally `e1_orakel_wahrheit() -> (ok, rows)`, `_defekt_factory(seed, mode)` with `mode in ("station", "folder")`, `_lead_rate(rep, rule=None)`. Exit code 0 only at 4/4.

**The four expectations.**
- **E1 oracle truth:** every wired formula against an **independently hand-computed `Fraction` reference** (checker separated from the checked). In the code there are 9 such checks (`selftest.py:37-70`), tolerance `1e-12`.
- **E2 symmetry:** pair drift of the healthy bot in self-play `|drift| < 2·SE`.
- **E3 detector:** a constructed defect bot is (a) detected by the oracle (lead rate ≥ 2× healthy, compared on **the same rule** that matches the defect signature) and (b) rejected by the gate.
- **E4 null stability:** healthy vs healthy (other seeds) must produce **no** `ANWENDEN` — the loop invents no improvements.

**Input/Output.** No input except `--quick`. Output: PASS/FAIL lines on stdout, a journal entry `SELFTEST-BEFUND`, exit code.

**Dependencies.** `gym_hu`, `improver.gate_ab`, `duplicate.pokerbot`, `knowledge_base.math.*`.

**Status.** Stateless, but E3 **monkeypatches** `gym_hu._make_bot` and restores it in the `finally`.

**Cost.** Docstring names "~2-4 min locally"; `--quick` reduces the samples (60 instead of 150 pairs, 60 instead of 120 gate decks). Not independently re-measured.

**Measurement status.** PARTIAL. E1 is verifiably green today (the related, broader formula regression `verify_refs` runs with **66/66 exact**, re-run today). Evidence for a completely green 4/4 run does **not** exist in the repo: `docs/STATE.md:316` lists "get selftest E1–E4 green" as an open next step. The journal contains only the side finding E3c: healthy vs never-folder `+394,9 ± 279,9` at 60 decks (journal `SELFTEST-BEFUND`, 2026-08-16). For the gate proof E3b the **always-folder** is deliberately used, not the station: only the folder has a mathematically certain sign (it gives away every pot as soon as a bet is made); the station is not certainly beatable over a 1-hand horizon without adaptation.

**Usable standalone?** The pattern yes, the code no. Transferable is the idea: **deliberately construct a broken bot with a known sign and demand that your measurement machine finds it.** Without this test you do not know whether your gate can measure anything at all.

**Pitfalls.** E3a compares lead rates. If one compares the TOTAL rate instead of the individual rule matching the defect signature, newly added oracle rules with a different subject dilute the metric and the detector test silently fails (noted in the code as a measured finding, `selftest.py:118-124`).

---

### Run storage — `pokerbot/autogym/runs.py`
**Purpose.** Binds every measurement result to configuration, git commit and host, in ONE structure for all runs.

**Interface.**
- `neuer_run(name, config) -> Path` — creates `data/runs/<JJJJMMTT_HHMMSS>_<name>/` and writes `config.json` (your config plus `commit` from `git rev-parse --short HEAD`, `host`, `ts`).
- `schliesse_run(d, result)` — writes `result.json` and appends a line `{"run": <ordner>, **result}` to `data/runs/INDEX.jsonl` (append-only).
- `entscheidungs_logger(run_dir, sample=0.03) -> (log_fn(rec, geflaggt), flush_fn)` — collects ALL flagged decisions plus a 3 % random sample of the unremarkable ones (base rate) and writes them as `decisions.jsonl.gz`.

**Input/Output.** Dicts in, files out. `INDEX.jsonl` is the one-line-per-run table from which `bericht.py` builds the overview.

**Dependencies.** Only the standard library + a `git` binary in the PATH (falls back to `"?"` if missing).

**Status.** File system. The folder name contains the second — two runs in the same second collide (`mkdir(exist_ok=False)` throws).

**Cost.** Negligible; `edges.json` at 30.000 decks is a few hundred kB.

**Measurement status.** UNMEASURED (infrastructure without EV effect). Its value is indirectly documented: all numbers cited in this catalog come from `data/runs/*/result.json` or `INDEX.jsonl`.

**Usable standalone?** Yes, ~40 lines, copyable. The one point that counts: **the commit hash in `config.json`**. Without it a half-year-old measurement can no longer be attributed.

**Pitfalls.** `schliesse_run` writes the complete `result` dict into the index line. Raw data (`edges`) must be taken out beforehand, otherwise the index file bloats to megabytes — `pargate.main()` does exactly that (`res.pop("edges")`, then separately as `edges.json`).

---

### Formula regression net — `pokerbot/autogym/verify_refs.py`
**Purpose.** Checks that the formula functions in the repo today still compute exactly what was fixed at their verification.

**Interface.** `python -m pokerbot.autogym.verify_refs`; exit code 0 only at 100 %.

**Input/Output.** In: `knowledge_base/math/postflop_calc_verified.json` and `strategy_calc_verified.json`, each with entries `{function_name, verify_expr, verify_value}`. The runner `eval`s every expression against the installed module and compares with tolerance `1e-9`. Out: one line `verify_refs: P/T exakt, M fehlend, D Drift/Fehler` plus detail lines.

**Dependencies.** `knowledge_base.math.postflop_formulas` + `strategy_formulas` (hard).

**Status.** Stateless.

**Cost.** A few seconds (re-run today).

**Measurement status.** MEASURED POSITIVE: **66/66 exact, 0 missing, 0 drift** — re-run live today (2026-09-10); the same number stands in `docs/STATE.md:302`.

**Usable standalone?** Yes, if you store your formulas with fixed reference values.

**Pitfalls.** The docstring says it itself and it is the core: `verify_expr`/`verify_value` come from **the same generation** as the formulas. That is a **consistency** test, not a truth test — it catches drift and regression, not a formula entry that was wrong from the start. The truth tier are the 9 independently hand-computed `Fraction` references in `selftest.E1`. Whoever reads 66/66 as "our mathematics is proven" has misunderstood the test.

---

### Status report — `pokerbot/autogym/bericht.py`
**Purpose.** Renders `data/runs/INDEX.jsonl` + `data/autogym/journal.jsonl` into a readable page `data/runs/STAND.md`.

**Interface.** `python -m pokerbot.autogym.bericht` (only `main()`, no API).

**Input/Output.** In: the two JSONL files. Out: Markdown with a run table (run | candidate | bb/100 | SE | n | verdict) and the last 15 journal entries.

**Dependencies.** Only `runs.py` conventions (file paths are hard-wired).

**Status.** Stateless; overwrites `STAND.md` completely.

**Cost.** Milliseconds.

**Measurement status.** UNMEASURED (reporting tool).

**Usable standalone?** Only with the same storage convention. 30 lines — faster written yourself than ported.

**Pitfalls.** It overwrites `STAND.md` completely, while in the repo **hand-written addenda** stand at the bottom of the same file (the "Nachtrag 2026-08-18" blocks, from which several numbers of this catalog come). A careless run deletes them.

---

### Campaign drivers — `pokerbot/autogym/runde4.py`, `runde5.py`, `runde5b.py`
**Purpose.** Run entire, pre-written measurement campaigns automatically (phases, seeds, replications) and report themselves.

**Interface.** One CLI each without arguments: `python -m pokerbot.autogym.runde4` / `runde5` / `runde5b`. `runde4` has a time budget (`ZIEL_SEKUNDEN = 2*3600`, `WORKERS = 20`), `runde5` starts with an A/A null test as acceptance and aborts on violation, `runde5b` runs the three-runs rule to completion (two fresh deck banks plus combo assembly plus oracle-duel panel).

**Input/Output.** In: nothing (everything hard-coded in the driver). Out: run folders per phase, journal entries, a campaign JSON.

**Dependencies.** `pargate`, `envgate`, `orakel_duell`, `gym_six`, `runs.py` — all hard.

**Status.** Per campaign; **strictly sequential fleets** (one worker fleet at a time, RAM rule).

**Cost.** `runde4` is explicitly designed for 2 h wall clock (phases ~45/12/35 min plus remaining time for the decisive measurement).

**Measurement status.** MEASURED as drivers (they produced the journal entries `RUNDE4-SWEEP`, `RUNDE4-DECISIVE sel_m15 ANWENDEN 8.68`, `RUNDE4-6MAX-KATALOG` — `data/autogym/journal.jsonl`, 2026-08-17). They have no bb/100 of their own.

**Usable standalone?** No — they are project-specific scripts, not a library. Transferable is solely the **pattern**: write expectations into a constant BEFORE the run (`runde5.ERWARTUNGEN`), then measure. That makes post-hoc rationalization mechanically hard.

**Pitfalls.** They deliberately did not christen — `runde5.py:14` says it explicitly: "this driver measures, it does not christen". Whoever lets such a driver take part in the decision no longer has a gate, but an optimizer on its own metric.

---

### Exploit hunt — `pokerbot/autogym/exploit_jagd.py`
**Purpose.** Unleashes adaptive hunters (persistent opponent model) over many hands on the frozen bot — **diagnosis, not victory**: every exploit found is a hardening instruction.

**Interface.** `python -m pokerbot.autogym.exploit_jagd --haende 100000 --workers 20`. Internally `_jagd((seed, n_hands)) -> ledger`.

**Input/Output.** In: hands + hunter count. Out (aggregated): `jaeger_bb100`, `se_ueber_jaeger` (SE **over the independent hunters**, not over hands), `jaeger_positiv` ("14/20"), `sd_netto_bb100` / `nsd_netto_bb100` (showdown vs non-showdown), `fold_ernte` per street, `showdown` (won/lost/split); per hunter additionally `modell` (the final profile of the opponent model) in `jaeger_einzeln.json`.

**Dependencies.** `pokerbot.engine.game.HeadsUpGame`, `pokerbot.strategy.bot.PokerBot`, `runs.py`.

**Status.** The hunter is ONE persistent bot over all its hands (exactly the adaptation the paired gate deliberately never allows); the defender is created fresh per hand (the frozen bot does not learn).

**Cost.** Measured: 100.000 hands with 20 workers in **971,9 s** or 998,8 s (`data/runs/20260817_020232_exploit_jagd/result.json`, `…_014431_…`).

**Measurement status.** MEASURED, result differentiated: adaptive hunters **+8,87 ± 6,9** bb/100 (14/20 positive) against the null control **+7,73 ± 8,7** (12/20) — the adaptation GAIN is ~+1 and **not significant**. The finding lies elsewhere: the win channel shifts hard (showdown +5,8 → +19,9; non-showdown +1,9 → −11,0) and **all 20 independent hunters converge on the same defender profile**: VPIP 0,75–0,77, fold_to_bet 0,29–0,31, aggression 0,31–0,34. That is the empirical hardening map. Two catastrophe hunters (−69/−47) show the tail risk of generic adaptation. (Source: journal `EXPLOIT-JAGD`, 2026-08-17 02:19:27, plus the two `result.json`.)

**Usable standalone?** Yes. It is the simplest building block here: two bots, one loop, one ledger.

**Pitfalls.** The **adaptation protocol**. The first 100k run was NULL by construction, because `observe_opponent` was never called — the Dirichlet model stayed at `hands: 0, confidence: 0` and the "hunter" was an ordinary bot. The fix stands as a comment at the spot (`exploit_jagd.py:53-56`). If you test a learning opponent model, verify FIRST that it receives observations at all.

---

### Cross-reference: the minimal gate — `pokerbot/autogym/improver.py::gate_ab`
`improver.py` belongs by content to the improvement loop, but contains the **smallest complete gate function** of the repo, on which `selftest` and `run_local` fall back:

```
gate_ab(make_candidate, make_incumbent, n_decks, seed) -> {"bb100", "se", "n_decks", "verdict"}
```

It calls `gen_decks` + `duplicate_ab` and applies the same threshold logic as `stats.verdikt`, only without sparse clause and without bootstrap (`improver.py:649-662`): `ANWENDEN` at `bb100 − 2·se > 0`, `VERWERFEN` at `bb100 + 2·se < −1.0`, otherwise `NEUTRAL`. Whoever wants to take only ONE building block from this chapter: these are 12 lines over `duplicate_ab`, and they are the difference between "feels better" and "measured better". Also there: `_journal(entry)` (`improver.py:642`), which appends every finding with a timestamp to `data/autogym/journal.jsonl` — journal duty is binding in the project.

---

### What counts as REFUTED in this subsystem (so that you do not rebuild it)

- **The Dirichlet river exploit as a channel:** `exploit_gate` measures all eight league profiles ≤ 0, pooled approx. −12 bb/100, `exploit_korrekt: false` (`data/runs/20260909_192123_exploit_gate/result.json`). Exploit is OFF everywhere in the repo.
- **Frequency matching as an improvement principle:** the frequency-driven guards from the F/L findings (`mdf_guard` −3,26 ± 2,19 at n=99.000, `podds_guard`, `lizenz_guard`) were booked NEUTRAL/negative in the gate (`data/runs/STAND.md`), the selection-driven ones (`sel_guard` +4,7 ± 2,06 at n=99.000) carried. Project lesson: **selection beats frequency.**
- **The 5 % trim as a decision statistic:** was estimator v1, is refuted for thin channels (it removes exactly the signal decks) and remains only as a diagnostic field in the result (`stats.py:19-31`).
- **`envgate` positives as ship evidence:** the arm `prince` measures a channel artifact of raw −68 bb/100 there and is at the same time the live-validated champion (`envgate.py:39-41`). Hence the separate vocabulary `KANAL_*`.
- **Adaptive generics as an edge:** the 20-hunter campaign shows an adaptation gain of ~+1 bb/100 at SE 6,9 — not significant — with simultaneously two catastrophe hunters (−69/−47) (journal `EXPLOIT-JAGD`).

---

## External benchmarks

This subsystem answers exactly one question: **how good is my bot, measured against something that I did not build
myself?** It consists of protocol adapters (foreign API/environment -> our engine state dict -> back into
the foreign action language) and of evaluators (bb/100, AIVAT, variance reduction, exploitability). No module
here makes a poker decision — they only transport.

You need **at most the one adapter for the opponent you really want to measure**. The rest is
ballast. Whoever only needs an internal regression bound takes `duplicate.py` (paired decks) and ignores
the whole chapter. Whoever needs an absolute GTO distance needs GTO Wizard — and for that an access you
have to obtain yourself.

**A warning up front that applies to almost every module here:** `data/` and `tools/` are gitignored in this
repo (`.gitignore:8-9`). The GTOW client (`tools/gtow_client/`), the Pluribus/PHH hand histories
(`data/_phh_repo/`) and all run results are **not** part of what you get. The adapters are there,
the counterpart and the data are not.

---

### GTO Wizard adapter — `pokerbot/benchmark/gtowizard.py`

**Purpose.** Maps the GTO Wizard researcher API (`GameServiceResponse` <-> `ActRequest`) onto our
engine state, so that an arbitrary bot with `.decide(state)` plays against GTO Wizard AI and is AIVAT-evaluated.

**Interface.**
- `parse_cards(s: str | None) -> list[str]` (`:39`) — `'AsKdQh'` -> `['As','Kd','Qh']`.
- `_parse_history(action_history, button_seat, blinds)` (`:45`) — reconstructs from the flat token list
  (`'f'`, `'c'`, `'k'`, `'bX'`, `'_'`) our history list plus the amounts paid in per street by both
  players; returns `(history, committed_hero, committed_villain, street_idx)`.
- `gtow_to_state(gsr: dict) -> dict` (`:92`) — the core: complete API response -> our state dict, hero
  ALWAYS normalized to index 0.
- `decision_to_act(decision: dict, leg: dict, la_codes: list[str]) -> dict` (`:157`) — `{action, amount}` ->
  `{"action": "f|c|k|b", "amount": int|None}`, clamped to `raise_range`, with legality guarantee.
- `class PokerBotAgent` (`:184`) — `__init__(seed=7, exploit=True, use_resolver=None, use_turn_resolver=None)`,
  `act_dict(gsr) -> dict` (`:251`, synchronous), `act_async(gsr)` (`:261`, `asyncio.to_thread`),
  `hand_end(final_gsr=None)` (`:269`, feeds the opponent model with the final state).

**Input/Output.** In: the API response as a dict with `game` (`blinds`, `starting_stack`) and `game_state`
(`street`, `common_pot`, `total_pot`, `board_cards` as a string, `players[{stack, position, hole_cards}]`,
`legal_actions`, `raise_range{min,max}`, `action_history`, `is_hand_over`, `winnings`, `aivat_score`). Out: the
engine state dict with the load-bearing keys `street`, `board`, `pot`, `bb`, `current_bet`, `button`,
`hand_id`, `history`, `players[0..1]` (each `hole`, `stack`, `committed_street`, `committed_total`, `is_button`)
and `legal` (`to_call`, `can_fold/check/call/raise`, `raise_min`, `raise_max`, `is_bet`). The hero is the seat
whose `hole_cards` are set — the opponent has `None` there.

**Dependencies.** Hard: `pokerbot.strategy.bot.PokerBot` (only in `PokerBotAgent`, lazily imported),
`pokerbot.strategy.gto_mode.apply()` (called at module level BEFORE every strategy import, because
`postflop`/`advisor` read their flags at import time), `pokerbot.runtime_config`, `pokerbot.benchmark.gtow_ledger`,
optionally `pokerbot.strategy.auslese`. **The two pure mapping functions `gtow_to_state` and
`decision_to_act` depend on nothing** except `os` — they are individually copyable.

**Status.** `PokerBotAgent` is stateful per session: the wrapped `PokerBot` carries range tracker and
opponent model. Reset happens via `hand_end()` or the underlying `observe_hand_end`. A
`threading.Lock` (`self._decide_lock`) serializes all `decide` calls, because a decision mutates bot state
— several parallel hands therefore share ONE bot instance and one lock. `hand_id` from the response
addresses the per-hand randomization; without it parallel hands mix.

**Cost.** Measured in the live channel with resolver ON: **8,9 s/hand** (n=974, `docs/STATE.md:1021`), **10,1 s/hand**
(n=100, `docs/STATE.md:963`), **12,6 s/hand** (n=98, `docs/STATE.md:942`). With parallelism ~2.500 hands in
8–9 h (`CLAUDE.md`, block "MESS-OEKONOMIE"). The adapter itself costs nothing measurable; the time sits in the bot
and in the API.

**Measurement status.** The channel is the anchor of the project, thus MEASURED — with numbers that were won through it:
HEAD engine **AIVAT −20,09 ± 7,18 bb/100 (n=974)** (`docs/STATE.md:1021`); v4-on-PRINCE **−21,12 (n=979)** against
control arm **−31,34 (n=488)** (journal `GTOW-NACHT2-FAZIT-MANUELL`, `data/autogym/journal.jsonl`). On the adapter
itself TWO bugs were measured and fixed, both with direct bb/100 effect: (1) `to_call` was read as
`total_pot − common_pot` and was inflated preflop by the whole pot (`:114-124`, env
`POKERB_TOCALL_FIX=0` restores the error for the A/B); (2) `blinds` arrives live as `[BB, SB]`, but was
unpacked as `[SB, BB]` — every live run carried a built-in preflop over-fold (`:52-58`, fix: unpack
by size). The self-test `python -m pokerbot.benchmark.gtowizard` (`:290`) freezes both cases as asserts.

**Usable standalone?** Yes, the mapping layer: `gtow_to_state` + `decision_to_act` are two pure functions
without project dependency. Minimally you only need your own bot with `.decide(state)`. For a real
run you additionally need the **GTOW client**, and that lies under `tools/gtow_client/` — **gitignored**, so
not in what you get. It is the client provided by GTO Wizard; the class there is called
`PokerBotMVP` and calls `PokerBotAgent.act_dict`/`act_async`.

**Pitfalls.** The adapter reads its configuration from environment variables, some of which take effect **at import
time** (`_apply_gto_mode()` at module level, `auslese.setze_env` before the `bot` import). Whoever imports the bot beforehand
or sets a variable afterwards measures a different bot than they think — exactly for that
`runtime_config.fingerprint_geladen` (below) exists. Second pitfall: `act_dict` called synchronously from the event loop
blocks ALL parallel hands; the counter `loop_blockierende_aufrufe` (`:246`) makes that visible, but the
client must await `act_async`, otherwise your "parallel" run runs serially.

---

### GTOW hand ledger — `pokerbot/benchmark/gtow_ledger.py`

**Purpose.** Append-only JSONL protocol that writes every hand event of a live run to disk IMMEDIATELY,
so that an abort does not lose the whole chunk.

**Interface.**
- `class GtowLedger(pfad=None)` with `prozess_start(fingerprint)`, `hand_start(hand_id, arm, fingerprint_hash)`,
  `hand_end(hand_id, aivat, winnings, status, technische_events=())`, `offene_haende()`.
- `lese(pfad) -> list[dict]`, `abgleich(pfad) -> {"offen", "abgeschlossen", "doppelt_gestartet"}`,
  `offene_haende(pfad)`, `offene_haende_alle(verzeichnis)`.
- `standard_ledger() -> GtowLedger` — the one ledger of this process.
- `melde_hand_start(agent, hand_id)` / `melde_hand_ende(agent, hand_id, terminal, status="ok", ...)` — the hooks
  for the client; both NEVER throw.

**Input/Output.** In: `hand_id`, arm name, fingerprint hash, and at the end the terminal response (dict or
object), from which `aivat_score` and `winnings` are pulled. Out: one JSON line per event with `typ`,
`zeit`, `pid` plus the fields of the event. File:
`data/runs/v10/ledger_<prozess-start>.jsonl`, overridable with `POKERB_LEDGER_PFAD`.

**Dependencies.** Only `pokerbot.config` for `DATA_DIR` — trivially replaceable. Otherwise standard library.

**Status.** Per process a singleton (`_LEDGER`). The file name binds the ledger to exactly this process. On
restart the existing file is read, so that a double start of a hand across process boundaries
is noticed. Reset = new file or new process.

**Cost.** One `open('a')` + `flush()` + `os.fsync()` per event. Not measured; at ~10 s/hand irrelevant,
with a fast offline channel `fsync` per hand would be noticeable.

**Measurement status.** UNMEASURED as a quantity — but the reason is measured: "chunk 4 of night 2 was completely
lost" (module docstring, reference `../reports/V10_FACTS.md` A8), journal `GTOW-NACHT2-FAZIT-MANUELL`
("chunk-4 hands NOT logged (client writes HH only at the end) = lost").

**Usable standalone?** Yes, completely. Replace the `config` import with a path and you have a generic
crash-safe run ledger.

**Pitfalls.** The discipline, not the code: `status="ok"` without AIVAT is automatically downgraded to
`"unbekannt"` (`:71-72`) — a missing value is NEVER imputed as 0. Whoever writes the evaluation themselves and
counts `unbekannt` as 0 makes exactly the error this module is meant to prevent.

---

### Runtime fingerprint + misconfiguration gate — `pokerbot/runtime_config.py`

**Purpose.** Produces per process a hash of what is ACTUALLY loaded (bot flags from the living object,
advisor file hashes, git revision), and aborts the run if it does not match the expected profile. Does not sit
in the `benchmark/` directory, but is a hard dependency of the GTOW adapter.

**Interface.** `fingerprint_geladen(bot, stack_name) -> dict` (`:225`), `fingerprint_hash(fp) -> str`
(`:266`), `pruefe_konfiguration(erwartet, ist)` (`:272`, `SystemExit` on deviation), `gatter_aus_env(fp,
log=print)` (`:285`), plus building blocks `git_stand()`, `sha256_datei()`, `advisor_hashes(bot)`,
`prince_importflags()`, `prince_abweichungen(...)`.

**Input/Output.** In: the living bot instance + the name of the guard chain. Out: a dict with the
mandatory fields (`PFLICHTFELDER`, `:64`) including `fingerprint_hash`; `pid`, `zeit_utc` and the hash itself do
NOT enter the hash (`_NICHT_IM_HASH`, `:73`).

**Dependencies.** `pokerbot.strategy.gto_mode` (target values of the PRINCE profile), `hashlib`/`inspect`/
`subprocess` (git). For a foreign project the concept is transferable, the code is not — it knows our
flags by name.

**Status.** Stateless (reads only).

**Cost.** One `git` call with 10 s timeout (`_GIT_TIMEOUT_S`, `:75`) + SHA256 over the loaded
advisor files, once per process. Not measured more precisely.

**Measurement status.** UNMEASURED as an effect. The reason is documented: "the GTOW harness ran without any config check
(`gto_mode.fingerprint()` existed, but was never called; `POKERB_AUSLESE_STACK` was missing from the
fingerprint keys), and the HU web app played a never-measured configuration" (module docstring `:3-6`).

**Usable standalone?** Only as a pattern. Take the idea (fingerprint from the OBJECT, not from the env intent), not
the file.

**Pitfalls.** Without `POKERB_ERWARTE_PROFIL` the gate only logs and does not abort — a misconfiguration
then only shows up in the evaluation, if at all.

---

### Slumbot client — `pokerbot/benchmark/slumbot.py`

**Purpose.** Plays our bot via the public Slumbot API (HUNL, 200 bb, 50/100) and computes the
win rate in bb/100.

**Interface.**
- `parse_tokens(seg: str) -> list[str]` (`:40`) — splits a street segment of the action string into
  `k`/`c`/`f`/`b<to>`.
- `build_state(hole, board, action, client_pos, button) -> dict | None` (`:58`) — **the reusable
  centerpiece**: reconstructs the complete engine state solely from Slumbot's action string; `None` if
  the hand is already over.
- `decision_to_incr(dec, state) -> str` (`:148`) — `{action, amount}` -> Slumbot's increment string
  (`'f'`/`'k'`/`'c'`/`'b<to>'`).
- `play_hand(bot, token, verbose=False) -> (winnings, token)` (`:163`) — one complete hand.
- `play_hand_verbose(bot, token, verbose=False) -> (winnings, token, record)` (`:207`) — the same loop, additionally
  returns a rich row.

**Input/Output.** In: JSON from `POST /api/new_hand` and `POST /api/act` with `token`, `client_pos`,
`hole_cards`, `board`, `action`, `winnings`, and **at showdown** `bot_hole_cards` + `won_pot`. Out: our
state dict (the same load-bearing keys as with the GTOW adapter: `street`, `board`, `pot`, `history`,
`players`, `legal`); `play_hand_verbose` additionally returns `{hole_cards, board, bot_hole_cards, action,
winnings, won_pot, client_pos, button}` — exactly the format that `slumbot_adjust.py` consumes.

**Dependencies.** `urllib.request` (no `requests`), `pokerbot.strategy.bot.PokerBot` only in `main()`;
`build_state`/`decision_to_incr`/`parse_tokens` are pure and project-free. The passed bot is duck-typed:
`.decide(state)` + `.hero_idx` (+ optionally `.observe_hand_end`).

**Status.** The `token` carries the session across all hands — it must be passed on from hand to hand.
The bot itself is stateful per session (opponent model is fed via `observe_hand_end`). No
global state in the module.

**Cost.** Not measured. The script prints ms/hand every 20 hands (`:288-291`); the network round trip is one
`_post` per decision with 30 s timeout and up to 4 attempts (`:26-38`). No API key, no cost.

**Measurement status.** MEASURED, but **contradictory and variance-dominated** — exactly that is the lesson:
- `−39,6 ± 30,9 bb/100` (exploit-primary, n=2500, `docs/STATE.md:1478`); there explicitly: "the historical
  **+31** did NOT reproduce".
- `+31 bb/100` (earlier MVP measurement, `docs/STATE.md:1652`).
- `≈ −5 bb/100` over 500 hands (`docs/STATE.md:1791`).
- `−46` after the anti-spew fix, before that `−526` (`docs/STATE.md:1864`).
Note: at ±31 SE three of these numbers are compatible with each other. Slumbot alone carries no verdict.

**Usable standalone?** Yes, and it is the cheapest external channel of all: no key, no account, no
registration. Minimally you need `build_state` + `decision_to_incr` + the `play_hand` loop and a bot with
`.decide`.

**Pitfalls.** The button determination. `button = client_pos if first_action == "" else 1 - client_pos`
(`:168`) — the button is derived from whether an action has already happened at the first response. Whoever gets that
wrong builds the blinds in the wrong way round preflop and systematically measures a different bot (we actually made the same
error in the GTOW adapter, see above). Second point: `b<to>` is a CUMULATIVE
street bet, not an increment — despite the field name `incr` in the API.

---

### All-in EV correction for Slumbot runs — `pokerbot/benchmark/slumbot_adjust.py`

**Purpose.** Replaces in a logged Slumbot run the realized result of all pots that went all-in **before the river**
with the equity EV of the two known hands — variance reduction without AIVAT.

**Interface.** `analyze(path: str, iters: int = 20000) -> dict` (`:130`) — reads the JSONL, returns raw and
corrected; `_reconstruct(action, button) -> dict` (`:37`), `_adjusted_net(row, iters) -> (float, bool)`
(`:87`), `_bb100(nets) -> (bb100, stderr)` (`:117`).

**Input/Output.** In: the JSONL from `play_hand_verbose` (fields `hole_cards`, `board`, `bot_hole_cards`,
`action`, `winnings`, `won_pot`, `client_pos`, `button`). Out: a dict with RAW and ADJUSTED bb/100, each with
standard error.

**Dependencies.** The chip reconstruction mirrors `slumbot.build_state` (blinds 50/100, stacks 20000) —
soft coupling, but a drift apart silently breaks the numbers. Equity comes from our engine module.

**Status.** Stateless (pure file evaluator).

**Cost.** One Monte Carlo with `iters` (default 20.000) per corrected hand. Not measured.

**Measurement status.** UNMEASURED as an effect of its own (no bb/100 comparison "raw vs corrected" with source found).
The prerequisite is verified: Slumbot delivers `bot_hole_cards` only at showdown (module docstring
`slumbot.py:213-216`, "verified 2026-06-18"), and the chip reconstruction was "cross-validated to the chip"
(`docs/STATE.md:1178`).

**Usable standalone?** Yes, if your hand logs carry the same fields. The idea is portable: only correct pots
that went all-in BEFORE the river — after the river the result is deterministic and a
"correction" only adds error.

**Pitfalls.** The all-in street is recognized by a player's cumulative payment hitting 20000
— at other stack depths or blinds the module is silently wrong.

---

### Slumbot with LLM brain — `pokerbot/benchmark/slumbot_llm.py`

**Purpose.** Lets an LLM (or a solver bot, or a control baseline) play against Slumbot instead of the engine
— the same client loop, different decider.

**Interface.** `spot_from_slumbot(st: dict) -> Spot` (`:51`); `class VLLMBackend(url, model,
max_new_tokens=None)` (`:72`); `class _LLMBot` / `class AllCallBot` / `class SolverSlumbotBot(seed=0,
sample_log=None)` (`:124`/`:142`/`:184`) — all three duck-typed like a bot (`.decide(st)`, `.hero_idx`);
`class Counters` (`:106`, counts `frac_bad`); `class ProgressLog(path, t0, counters)` (`:288`);
`_run_stream(...)` (`:340`) for parallel Slumbot sessions.

**Input/Output.** In: the same Slumbot state as above, translated into our canonical `Spot` format.
Out: bb/100 ± standard error plus `frac_bad` (share of invalid/non-executable LLM programs) and a
progress JSONL.

**Dependencies.** Hard: `pokerbot.benchmark.slumbot` (the loop is reused, not forked),
`pokerbot.brain.*` (spot format, executor), for the local path `transformers`, for the fast path a
running vLLM server.

**Status.** Per stream one Slumbot session (token). With `--concurrency K`, K independent games run in a
thread pool against the same vLLM server.

**Cost.** `transformers` path: **~28 s/hand sequential** (module docstring `:10`), elsewhere
~29 s/hand measured (`docs/STATE.md:1331`). vLLM path in a GTOW run: 1,27 s/hand after the cold start
(`docs/STATE.md:1159`, there GTOW instead of Slumbot).

**Measurement status.** MEASURED: the SFT-1.7B brain reached **−72,0 bb/100 at frac_bad 0,03 (n=100)**
(`docs/STATE.md:1281-1283`). A solver run over 299 hands yielded raw −106 and was discarded as noisy
(`docs/STATE.md:1176`).

**Usable standalone?** Only with half the project (brain layer + executor). What you should really take away
is `--baseline allcall`: a model-free always-check/call baseline that MUST be clearly NEGATIVE. If it
is not, your harness lies — that is the cheapest self-deception check in the whole repo.

**Pitfalls.** `frac_bad` is the number that saves you: an LLM run with a high share of invalid programs
measures your fallback, not your model. Historically `frac_bad` once stood at 1,0 because of a
SIGALRM-in-worker-thread bug (`CLAUDE.md`, block GLM) — the model looked dead and was not.

---

### Slumbot adaptive — `pokerbot/benchmark/slumbot_adaptive.py`

**Purpose.** Plays the `AdaptiveExploiter` live against Slumbot and lets it learn its fold curve
online in the process.

**Interface.** `walk_decisions(action: str, button: int)` (`:18`) — walks the action string and returns
the opponent decision points, so that the opponent model can observe them; plus a `main()` with `--hands`,
`--iters`.

**Input/Output.** As `slumbot.py` (it imports its client as `S`), additionally every observed
opponent action is booked into the model. Out: bb/100.

**Dependencies.** Hard on `pokerbot.benchmark.slumbot` and `pokerbot.strategy.adaptive`.

**Status.** Per session: the learned fold curve grows across hands. For a clean A/B it must be
reset — otherwise run 2 measures a different model than run 1.

**Cost.** Not measured.

**Measurement status.** **REFUTED as a bot path.** The `AdaptiveExploiter` itself is measured weaker than
`PokerBot`: "adaptive's BASE decide() is weaker than PokerBot's (−56 with all exploit knobs OFF), NOT a
mis-tuned gate" (`docs/STATE.md:1795-1797`). The Dirichlet river exploit was later independently refuted (ON
vs OFF, 600 paired decks, all 8 diffs ≤ 0, pooled ≈ −12 bb/100; `docs/STATE.md`, block "Exploit-Gate",
journal `EXPLOIT-GATE-VERDIKT`).

**Usable standalone?** Only as an example of how to reconstruct opponent actions from an action string.

**Pitfalls.** Online learning and measuring bite each other: the bot in hand 400 is not the bot from hand 1, so the
bb/100 is a mean over a drifting policy.

---

### Claude as player vs Slumbot — `pokerbot/benchmark/claude_vs_slumbot.py`

**Purpose.** Experiment: a frontier LLM decides, but receives ALL structured signals that our
engine computes for the spot — does reasoning over our own signals beat our own decision?

**Interface.** `class ClaudePlayer` — drop-in for `slumbot.play_hand` (`.decide(state) -> {action, amount}`,
`.hero_idx`, `.observe_hand_end`). Flow per docstring: internal `PokerBot(exploit=True)` produces the
`rationale`, which is formatted into the prompt, the model answers, the answer is parsed and legalized,
everything is logged.

**Input/Output.** In: Slumbot state. Out: bb/100 plus a per-decision log (engine action vs
Claude action vs justification).

**Dependencies.** `pokerbot.benchmark.slumbot`, `pokerbot.strategy.bot`, `research/llm.py` (API call),
API key.

**Status.** Per session (the internal bot learns along).

**Cost.** Not measured; one API call per decision, i.e. several per hand.

**Measurement status.** UNMEASURED as bb/100 — the docstring says it itself: "raw bb/100 vs Slumbot is
variance-dominated at small n (the point is CAPABILITY + DATA, not a precise number)" (`:12`). The related
Claude run against GTOW is measured (−28,55 AIVAT, `CLAUDE.md`, block CURRENT BRAIN), but that is a different
module.

**Usable standalone?** Only with our engine — the whole point is that the LLM is served OUR analysis.

**Pitfalls.** Clear project rule on this: "this is an LLM-as-player EVAL, never a training label for the GTO
core" (`:14`). Whoever takes the outputs as training data imports the teacher's errors.

---

### LBR (Local Best Response) — `pokerbot/benchmark/lbr.py`

**Purpose.** Estimates a LOWER bound of exploitability, by having an opponent choose locally at every node the
EV-best action (EV via Monte-Carlo rollout) and then continue playing passively.

**Interface.**
- `lbr_bb100(make_bot, hands=120, K=8, start=10000, sb=50, bb=100, seed=7, iters=80) -> (mean, se, net_list)`
  (`:121`) — the only function you need; `make_bot(seat)` is a factory.
- `_candidates(game, la)` (`:66`) — LBR's local action set: check/call/fold + ~2/3 pot + all-in.
- `_rollout_ev(game, lbr_idx, action, amount, rollout_bot, K, rng)` (`:84`) — mean chip gain over K
  rollouts with **freshly drawn** bot cards.
- `class _NitBot` (`:28`) — always-check/fold target as a mechanics test: LBR MUST take it apart.

**Input/Output.** In: a bot factory. Out: `(mean, se, net)` — LBR's win rate in chips per hand
(`bb = 100`), i.e. "this much the bot loses at least against a local best responder".

**Dependencies.** Hard: `pokerbot.engine.game.HeadsUpGame` (LBR needs an engine that can be
`copy.deepcopy`-ed and played on) and `pokerbot.engine.cards.make_deck`. The measured bot is
duck-typed.

**Status.** Stateless between calls; WITHIN a run it is re-seeded per hand
(`g.rng = random.Random(f"deck-{seed}-{_hi}")`, `:132-133`), so that hand *i* sees identical cards and identical
rollout randomness across different bot versions — that makes the run paired.

**Cost.** Not measured. Structure: `hands × decisions × |candidates| × K` full
`copy.deepcopy` rollouts. That is the most expensive channel in the directory; the default values (120 hands, K=8,
`iters=80`) are already economy versions.

**Measurement status.** **REFUTED as an absolute gate — that is the most important single piece of information in this chapter.**
`lbr_falsify.py` showed over 300 paired hands (`../NOTES.md:598-608`):
- **Range-blind:** injected c-bet-air and river-overbluff leaks yielded paired deltas of **+123 / −31
  bb/100 (≈ 0)**, although they fired in 99 or 95 of 300 hands — the uniform card draw cannot see a
  corrupted RANGE.
- **Under-exploited:** even an EXTREME overfolder brings only **+289 ± 175** (fold-any-bet) or **+323 ± 175**
  (overfold-50) — right direction, but no 3σ at 300 hands.
- Clean bot: **+141 ± 298** = noise.
Earlier, independently: "LBR v1 too loose to score the floor (loses −987 to it; nit-sanity +75 OK)"
(`docs/STATE.md:1798`). The mechanics work (nit test), the evidential power does not.

**Usable standalone?** Yes, if your engine is deep-copyable and can be played on from an arbitrary state.
Exactly that is the requirement most engines do not meet.

**Pitfalls.** The one point: **do not believe the number.** LBR v1 with uniform card draw measures only
fold/bet RESPONSES, never the range composition. Whoever reads "our bot is barely exploitable" from it has
deceived themselves. The documented repair (LBR v2: Bayes-consistent, action-dependent range +
multi-street best response) is **not built** in the repo (`../NOTES.md:608`).

---

### LBR falsification — `pokerbot/benchmark/lbr_falsify.py`

**Purpose.** Tests the LBR itself: injects KNOWN leaks into the frozen bot and measures whether the LBR
finds them.

**Interface.** `class LeakyBot(seat, spec="clean", seed=0)` (`:21`) — wraps a `PokerBot` and
corrupts exactly one decision; `SPECS` (`:69`) lists the six arms: `nit_ref`, `clean`, `fold_any_bet`,
`overfold_50` (fold response, card-independent) and `cbet_air`, `overbluff_river` (range composition).

**Input/Output.** In: nothing (builds its bots itself). Out: per arm the LBR win rate, compared with
`clean`.

**Dependencies.** `pokerbot.benchmark.lbr` (`lbr_bb100`, `_NitBot`), `pokerbot.strategy.bot.PokerBot`.

**Status.** The wrapper has its own RNG (`seed + 99`) for the probabilistic leaks.

**Cost.** Six full LBR runs. Not measured, but six times the most expensive channel.

**Measurement status.** MEASURED — and the result is a NEGATIVE FINDING about the instrument, not about the bot:
see the numbers under `lbr.py` (`../NOTES.md:598-608`). Usable by-product of the same work: `lbr_bb100` has since
re-seeded per hand and is thus a paired A/B channel (`../NOTES.md:605-607`).

**Usable standalone?** Yes, conceptually: this is the template for "falsify your measurement instrument before you
believe it". Transferable to any exploitability measure.

**Pitfalls.** A leak must FIRE often enough, otherwise you measure nothing — that is why the module logs in how
many of the 300 hands the injected leak took effect at all. Without this counter "delta ≈ 0" could also have
meant "leak never fired".

---

### Kaggle Game Arena — `pokerbot/benchmark/kaggle_arena.py`

**Purpose.** Plugs our bot into the OPEN-SOURCE environment of the Kaggle leaderboard "Heads Up Poker"
(`python_repeated_pokerkit` via OpenSpiel) and measures paired on identical decks with seat swap.

**Interface.**
- `spiel(stack_einheiten=200)` (`:68`) — loads the game; the game string is IMPORTED from `kaggle_environments`
  (not copied), so that a change there is noticed.
- `parse_beobachtung(obs: str) -> dict` (`:98`) — the wrapper's `observation_string` -> `{strasse, bets,
  stacks, start, board, hole, pot_gesamt}`.
- `zustand(state, spieler, historie, hand_id) -> dict` (`:130`) — OpenSpiel state -> our engine state
  (hero ALWAYS index 0, units × 50 = chips).
- `spiel_aktion(entscheidung, state, spieler) -> int` (`:177`) — `{action, amount}` -> OpenSpiel action
  (`0` fold, `1` check/call, `N` bet/raise **TO** N units), with legality guarantee.
- `spiele_hand(agenten, deck_seed, hand_id, stack_einheiten=200) -> float` (`:244`) — one hand, net of seat 0.
- `duell(a_fabrik, b_fabrik, decks, seed0=90000, stack_einheiten=200) -> dict` (`:303`) — the paired channel.
- Agents: `PrinceAgent(stack="final", seed=7, kanal="gym")` (`:196`), `BasisAgent` (`:223`), `RufAgent`
  (`:230`, call station, wiring smoke only).
- `instrumentiere_plan()` (`:43`) — attaches (idempotently) counters to the river plan, without changing a
  decision.

**Input/Output.** In: agent factories + deck count. Out: a statistics dict with `bb100`, `se`, `trim`,
`median`, `nonzero`, bootstrap CI, `verdict` (from `stats.verdikt`), plus `plan` (activations/played/fallbacks)
and `basisrate` (among others `planfaehig_je_100_haende`).

**Dependencies.** External hard: `open_spiel` (`pyspiel`) and `kaggle-environments` — `pip install open_spiel
kaggle-environments`, for Python 3.12 there is a Windows wheel (`../reports/KAGGLE_ARENA.md`, section commands).
Internal: `pokerbot.autogym.stats` (verdict), `pokerbot.strategy.auslese` + `pokerbot.strategy.bot` (only for
`PrinceAgent`). Parser, state adapter and action mapping depend on none of that.

**Status.** Critical and measured: `duell` creates **FRESH agent instances per mirror half** (`:315-317`),
because our bot mixes from a continuous RNG stream. The `hand_id` is **identical per deck**, not per
half (`:325-327`). Module-global counters `_ZAEHLER` and `_PLAN` are zeroed at the beginning of every `duell`.

**Cost.** Measured: **300 paired decks (= 600 hands) in 3.153 s on one core ≈ 10,5 s/deck**
(`../reports/KAGGLE_ARENA.md`, table "Erster Referenzwert"). The documentation comparison names 0,3–18 s/hand depending on
resolver, parallelizable. Cost per hand: 0 (runs locally).

**Measurement status.** The channel is calibrated, the first verdict is **NEUTRAL**: `prince[final]` vs `prince[basis]`,
300 paired decks: raw mean **+55,8 bb/100, SE 38,0**, 5 %-trimmed +6,3, median 0,0, deviating decks
97/300 (32,3 %), of which 45 positive (sign-z −0,71), bootstrap CI [−16,7, +134,6], `perm_p` 0,076
(`../reports/KAGGLE_ARENA.md`, journal `KAGGLE-REFERENZWERT`). **A/A exactly 0** after two fixed measurement traps
(`hand_id` per half; RNG stream across hands — A/A stood at **−37,5** at 8 decks before). Price list of the
channel, from the same source: for SE ≈ 4 one would need ~27.000 decks ≈ 75 h on one core.

**Usable standalone?** Yes — this is the most easily adoptable adapter in the chapter: `parse_beobachtung`,
`zustand` and `spiel_aktion` are three pure functions, you only need the two packages and a bot with
`.decide`. `duell` additionally needs our `stats` module; your own mean-with-SE will do as well.

**Pitfalls.** **The stack depth.** Kaggle plays 200 units = **100 bb**, the GTOW competition 200 bb — and
our preflop blueprint only fires from 140 bb effective (`pokerbot/strategy/bot.py:200`). At `--stack-bb 100`
you therefore measure a DIFFERENT bot (heuristic cascade instead of near-Nash blueprint) than in the competition channel
(`../reports/KAGGLE_ARENA.md`, "KORREKTUR"). Second point, explicitly binding in the project: **the channel is NOT a
GTO anchor.** The official field are LLMs, not a re-solver; a win here beats LLMs, not the solver. The
attempt to calibrate Kaggle bb/100 to GTOW AIVAT has measurably failed (6 common models, **r = 0,37,
R² = 0,14, residual SD 15,5**; only after removing Grok 4 r = 0,88 — that would be curve fitting,
`../reports/KAGGLE_ARENA.md`, section "Eichung").

---
### LLM opponent inside our engine — `pokerbot/benchmark/llm_opponent.py`

**Purpose.** Seats a frontier-LLM agent as the OPPONENT inside our own HU engine (200 bb) to play against an
LLM in leaderboard style.

**Interface.** `llm_opponent(model: str, seat: int = 1, naive: bool = False)` (`:91`) — returns a
`decide(st)` function; internally `_prompt(st, seat, naive)` (`:38`), `_parse(text)` (`:81`),
`_legalize(st, seat, action, frac)` (`:66`).

**Input/output.** In: our engine state. Out: a legal action. Two prompt modes: `--naive` (one line, JSON-only,
**weak baseline — do not trust its win rate**) and the default (rich state with pot odds/SPR/position/history,
chain-of-thought, `reasoning_effort=high` on gpt-5.x).

**Dependencies.** `research/llm.py` + API key; our engine as the playing field.

**Status.** Stateless per decision (no memory across hands).

**Cost.** Not measured; one API call per decision.

**Measurement status.** UNMEASURED, and the module itself says why: "Raw bb/100 over a modest sample is
NOISE-dominated (HU variance ~±200 bb/100 over 100 hands) — directional only" (`:11-12`).

**Usable standalone?** Yes, if you have LLM access — the prompt builder is the actual work and depends only
on the state dict.

**Pitfalls.** The `--naive` mode exists as a control group, not as an opponent. Whoever measures it by mistake as
"the LLM" has beaten a straw man.

---

### GTO oracle match (local GTOW substitute) — `pokerbot/benchmark/gto_oracle_match.py`

**Purpose.** Head-to-head bb/100 against an opponent that queries TexasSolver live at EVERY postflop decision
and samples from its GTO mix — the local substitute when no GTOW access is available.

**Interface.** `class GTOOracleAgent(seat, seed=0, acc=_ACC, iters=_ITERS)` (`:73`) with `.decide(st)`;
`run_paired(hero, oracle, decks, start=4000, sb=50, bb=100)` (`:190`) — paired run; `_match_label(action,
amount, committed, node)` (`:46`) maps our action onto a tree branch.

**Input/output.** In: two agents + deck count. Out: bb/100 with standard error. Both players are dealt from
the SRP ranges so that the solve ranges stay consistent.

**Dependencies.** Hard: `pokerbot.strategy.gto_oracle` and therefore **TexasSolver as an external binary** (lives
under `tools/` — gitignored).

**Status.** Per hand; the oracle agent falls back to the bot floor when the spot is not solvable or the hand
is not in the range.

**Cost.** One live solve per decision — the docstring names that explicitly as the reason for small samples
(`:7`). Measured elsewhere in the project: `solve_node` ~76 s (`docs/STATE.md:1113`), though in a different
configuration.

**Measurement status.** UNMEASURED as a headline number in the current era. The docstring itself lists three honest
limitations: small samples, ranges without exact continuation propagation (so only APPROXIMATELY near-GTO), and
a fixed bet-size abstraction in which our off-tree advantage stays invisible.

**Usable standalone?** Only with TexasSolver and our oracle layer. Whoever has both gets a $0 GTO opponent.

**Pitfalls.** A static solve has a fixed sizing abstraction — this channel by construction CANNOT measure whether
your bot exploits off-tree sizes well. It measures "loss against GTO", not "win against a solver with a tree".

---

### Pluribus decision match — `pokerbot/benchmark/pluribus_bench.py`

**Purpose.** Replays the 10,000 Pluribus hand histories, reconstructs every decision situation and measures
how often our 6-max bot picks the same action category as Pluribus.

**Interface.** `replay(path)` (`:51`) — one PHH file -> decision nodes; `cat_actual(verb, to_call)`
(`:33`) and `cat_bot(action)` (`:41`) — mapping onto the four categories aggressive/call/check/fold;
`decide_with(obs) -> dict` (`:221`); `main()` with `--max-hands`, `--iters`.

**Input/output.** In: PHH TOML files from `data/_phh_repo/data/pluribus` (`:26`). Out: match rate overall, per
street, per position, plus a confusion breakdown — and as a by-product
`data/training/pluribus_decisions.jsonl` (observation -> action) for imitation learning (`:27`).

**Dependencies.** Hard: the PHH data (`data/` is gitignored — you have to fetch it yourself from uoftcprg/phh-dataset)
and our 6-max decider.

**Status.** Stateless per hand (pure replay).

**Cost.** Listed as CPU-intensive ("CPU-LIVE", `docs/archive/BOT_PARTS_CATALOG.md:125`), otherwise not
measured. The MC equity iterations are adjustable via `--iters`.

**Measurement status.** UNMEASURED in this file. The measured number belongs to the NEWER successor
`research/pluribus_match.py`: **76.6 % bucket agreement over 15,169 decisions** (preflop 82.4 %,
flop 65.6 / turn 63.5 / river 61.9; `docs/STATE.md:560`). Important framing from there: Pluribus is NOT
GTO ground truth (raw −7.09 bb/100 against pros in the dataset), and **both sides MIX** — identical
60/40 mixes would yield ~52 % agreement by pure arithmetic, so 76.6 % is a lower bound.

**Usable standalone?** Yes, if you have the PHH data and your bot offers a 6-max `decide`. The matching
pattern is the actual transfer, not the code.

**Pitfalls.** Decision agreement is NOT a strength measurement. A bot that imitates a mixing opponent 100 %
would be worse than the opponent — and the mixing floor (see above) makes every rate below 100 % ambiguous.

---

### PHH leak cross-section — `pokerbot/benchmark/phh_leaks.py`

**Purpose.** Checks across four different hand-history sources whether "folds too much against small/
pot-sized postflop bets" is a Pluribus specialty or a general weakness.

**Interface.** `parse_file(path)` (`:35`), `replay_hand(d)` (`:46`), `collect(paths, target=None)` (`:97`),
`agg(stats, hu, streets, buckets)` (`:121`), `report(label, hands, dec, stats)` (`:133`). Size buckets:
`small` <0.45 pot, `med` 0.45–0.8, `pot` 0.8–1.3, `over` >1.3 (`BUCKETS`, `:23`).

**Input/output.** In: PHH files from `data/_phh_repo/data` (`:22`) — sources `pluribus`, `wsop`, `famous`,
`handhq`. Out: fold frequency per street and size bucket, compared with `alpha = to_call / pot` (the
maximum unexploitable fold frequency heads-up postflop); `fold% > alpha` = exploitable over-fold.

**Dependencies.** Only `tomllib`, `glob` and the data — **the module needs no cards and no bot**, it
reads only actions and sizes. So it also works with hidden hole cards (`"????"`).

**Status.** Stateless.

**Cost.** Pure parsing, not measured; no solver, no equity.

**Measurement status.** UNMEASURED — no sourced result of this run could be found in `docs/`. The
underlying Pluribus fold leak is listed elsewhere as an exploit projection (~+4 bb/100,
`docs/archive/META_STRATEGY.md:36`), but that is `pluribus_leaks.py`, not this module.

**Usable standalone?** Yes, this is the most self-contained module of the chapter: PHH files in, fold statistics out. No
project code needed except `config.ROOT`.

**Pitfalls.** `alpha = to_call/pot` is the HU bound. In multiway pots it is not the right reference, and the
sources `wsop`/`famous`/`handhq` are predominantly not heads-up — the aggregation must filter for that (the
parameter `hu` in `agg`), otherwise you compare against the wrong bound.

---

### Scorecard aggregator — `pokerbot/benchmark/scorecard.py`

**Purpose.** Runs all key-free measurement axes one after another and writes ONE JSON plus a readable
summary, split into "loss against near-GTO" and "edge against the field".

**Interface.** `axis_gto_gap(limit)` (`:48`), `axis_duplicate(decks_n)` (`:62`), `axis_internal(hands)`
(`:78`), `axis_field(hands)` (`:88`), `axis_exploit_proof(hands)` (`:105`), `axis_slumbot(hands,
exploit_primary)` (`:119`); `main()` with `--quick` / `--full` / `--hands` / `--iters`; `_se(net)` and `_noise(n)`
(`:30`/`:34`) provide the standard error and the HUNL noise threshold.

**Input/output.** In: flags. Out: a dict/JSON with `timestamp`, `git_sha`, `agent`, `config`, `axes` and
`errors`. **After EVERY axis the (partial) file is written** (`:174`), so a crash loses nothing; a
failed axis lands as an entry in `errors` instead of killing the run.

**Dependencies.** Practically the whole directory (`duplicate`, `internal`, `floor_map`, `exploit_proof`,
`slumbot`) plus the strategy. Not portable.

**Status.** Stateless; `--full` pulls network (Slumbot), `--quick` runs offline.

**Cost.** Not measured as a number. Default `--quick`: 500 hands per unpaired axis, 250 decks paired, 250
flop boards; `--full`: 1500 / 600 / all boards + two Slumbot runs of 2×`H` hands each (`:150-160`).

**Measurement status.** UNMEASURED as an instrument (it only aggregates other modules' numbers).

**Usable standalone?** No. Take the two ideas with you: persist partial results after every axis, and print
every unpaired bb/100 number NEXT TO the noise threshold `~90/sqrt(N/100)` (`_noise`, `:34`), so that nobody
takes a single number for significant.

**Pitfalls.** The doctrine is in the docstring and is the project's lesson: "A single unpaired number is
NEVER presented as significant" (`:9-10`). The aggregator nevertheless tempts you to quote the prettiest
axis.

---

### Paired decks (duplicate/mirror) — `pokerbot/benchmark/duplicate.py`

**Purpose.** The internal standard gate: the same deck is played twice with swapped seats, so that card
luck cancels out and only the policy difference remains. Not an external benchmark — but the channel
against which all external numbers are cross-read.

**Interface.**
- `gen_decks(n, seed=0)` (`:21`) — n fixed deals `(hole0, hole1, board[5])`.
- `duplicate_ab(make_a, make_b, decks, start=20000, sb=50, bb=100, return_edges=False, hand_id_basis=0)`
  (`:67`) — A's card-adjusted edge over B in bb/100 + standard error; with `return_edges=True` additionally
  the per-deck edges for paired differences across configurations.
- `naive_ab(make_a, make_b, hands, ...)` (`:91`) — the same measurement WITHOUT variance reduction, as a contrast.
- Factories `gto(...)` (`:106`) and `pokerbot(...)` (`:116`).

**Input/output.** In: two strategy factories `make(seat) -> decide(state) -> (action, amount)`. Out:
`(bb100, se)` or `(bb100, se, edges)`; the conversion accounts for two hands per deck (`:82-84`).

**Dependencies.** `pokerbot.engine.game.HeadsUpGame`, `pokerbot.engine.cards.make_deck`,
`pokerbot.strategy.gto_baseline` (only for the bundled factories).

**Status.** Stateless between calls. **But:** the `hand_id` is injected into the state and is identical for
BOTH mirror halves (`:76`), because the strategies' private randomness is `f(hand_id, seat)`. With
`2*idx+half`, 6/276 decks were measured non-zero and replay-identically reproducible (comment `:41-48`).
`HAND_ID_STRIDE_JE_DECKSEED = 1_000_000` (`:49`) keeps blocks in disjoint address spaces.

**Cost.** Not measured; two hands per deck without network.

**Measurement status.** MEASURED POSITIVE as an instrument — it is the channel through which the project's
applied changes were accepted, e.g. the 6max flat fix with 3 runs of 2992 decks each: **+17.7 ± 6.4 / +11.4 ± 6.9 /
+19.2 ± 7.0 bb/100** (`docs/STATE.md`, block "6MAX FLAT-FIX"). The docstring names a variance reduction of
~10–50× versus naive matching (`:1-3`); the exact number is to be reproduced in the `main()` self-test, it is not
documented with a number in `docs/`.

**Usable standalone?** Yes, as soon as your engine allows hole cards and board to be FIXED in advance (`_setup_fixed`,
`:32`). That is the only real requirement.

**Pitfalls.** **The A/A null test.** Set candidate = incumbent; the result must be EXACTLY 0. If it is not,
you are measuring your RNG, not your strategy — measured in the project: A/A stood at −9.4 instead of 0 (v10,
`../reports/V10_GATES_REPORT.md`) and at −37.5 instead of 0 in the Kaggle channel, both times because of random-number
addressing, not because of poker.

---

### Internal baseline opponents — `pokerbot/benchmark/internal.py`

**Purpose.** Fast, network-free cross-check against simple exploitable opponents — a strong bot MUST take
them apart.

**Interface.** `run(opp: str, hands: int, start=10000, sb=50, bb=100, seed=1) -> float` (`:49`) — bb/100
against one of the three opponents; `station(la, rng)` (`:19`), `maniac(la, rng)` (`:28`), `nit(la, rng)` (`:39`).

**Input/output.** In: opponent name + hand count. Out: bb/100.

**Dependencies.** `pokerbot.engine.game.HeadsUpGame`, `pokerbot.strategy.bot.PokerBot`.

**Status.** Stateless.

**Cost.** Not measured; no network, no solver calls.

**Measurement status.** MEASURED POSITIVE, but against trivial opponents: `PokerBot(exploit=ON)` beats everything, worst
case +1 bb/100 against the strong peer; station +493, maniac +757, sticky +393, trappy +161
(`docs/STATE.md:1789-1792`, measured with the `beat_them_all` pattern over 250 hands per pairing).

**Usable standalone?** Yes, trivially — three functions of ~10 lines each. The value lies in the role: smoke
detector, not tape measure.

**Pitfalls.** These numbers grow with the opponent's stupidity, not with your bot's strength. "+757
against the maniac" proves nothing about GTO proximity; the project has documented exactly this contrast (against the
field +hundreds, against GTOW −20).

---

## What else lives in the directory (not part of this chapter)

These files live in `pokerbot/benchmark/` but measure against INTERNAL opponents or against our own
solver cache; they do not belong to "external benchmarks" and are listed here only so that you do not consider
anything lost when browsing the directory — they are NOT reviewed in the full catalogue format:

| File | one line |
|---|---|
| `beat_them_all.py` | Tournament of our bot against the internal opponent suite (source of the +493/+757 numbers). |
| `calibrate.py` | Calibrates the field of internal opponents. |
| `exploit_proof.py` | Paired proof that the exploit layer prints money against a constructed leak. |
| `floor_ablate.py` | Ablation of individual floor components, paired. |
| `floor_map.py` | GTO gap across several streets/textures against the solver cache. |
| `gto_benchmark.py` | Evaluates the baseline against the TexasSolver cache across many flops (GTO implausibility per node). |
| `pluribus_leaks.py` | Leak mining in the Pluribus histories (exploit projection). |
| `preflop_ab.py`, `range_tracker_ab.py`, `sixmax_gap.py` | Small single-purpose A/B scripts. |
| `probe.py`, `weaponize.py` | Older exploit probes. |
| `runpod_train.py` | Pod hookup, not a benchmark. |

Associated drivers live outside the directory and are worthless for an outside developer without our
infrastructure: `research/gtow_nacht.py`, `research/gtow_nacht_v10.py` (night schedule with
pre-registered arm order), `research/gtow_ab.py`, `research/gtow_xray.py`, `research/gtow_tail.py`,
`research/analyze_gtow_hands.py`, `tools/gtow_run.py`, `tools/gtow_measure_chunked.py`.

## What I could not resolve

- **Cost per hand** for `slumbot.py`, `lbr.py`, `gto_oracle_match.py`, `phh_leaks.py`, `pluribus_bench.py` and
  `scorecard.py` is nowhere documented as a number in the repo — it says "not measured" there, not estimated.
- **`phh_leaks.py`** has no findable result entry; the frequently quoted "+4 bb/100
  exploit projection" belongs to `pluribus_leaks.py`.
- **Variance reduction of `duplicate.py`**: the docstring says "~10-50×"; I did not find a measured number with a
  source (the contrast run `naive_ab` exists, its result is not documented).
- **The Slumbot numbers contradict each other** (+31 / −5 / −39.6 / −46); I listed all four with sources
  instead of picking one. At SE ±31 none of them is a verdict.

---

## Opponents, league, tournament

This subsystem provides **opponents for measuring** (a league of 16 named player types, all produced by ONE
decision function with different knobs) and **tournament semantics** (ICM, bubble factor,
director over levels/antes/elimination/table balance). Whoever builds only a cash bot needs exactly one
piece of it: the league as sparring partner for paired A/B gates. Whoever wants to play tournaments needs `icm.py` +
`tournament.py`; everything above that (`tourney.py`, `mtt.py`) is simulation infrastructure, not strategy code.

---

### 6-max league (core + profiles + online opponent model) — `pokerbot/arena/sixmax.py`
**Purpose (1 sentence).** A position-aware, complete 6-max NLHE decision function that is parameterised via a
knob dataclass (`Knobs`) into 16 different player types — league opponents AND the project's currently
best-measured 6-max bot in one.

**Interface.**
- `decide_6max(obs: dict) -> dict` — stateless call of the neutral `tag` profile; no opponent model.
- `class Knobs` (dataclass, `sixmax.py:39-52`) — `name, open_mult, tb_pct, fb_pct, flat_hi, cont_lo,
  value_eq, raise_eq, bluff_mult, call_delta, flat_guard`. That is the entire profile language.
- `PROFILES: dict[str, Knobs]` (`:55-87`) — `nit, tag, tag_flatfix, lag, station, maniac` (league),
  `rock, whale, shark` (held-out types that were never trained against).
- `class SixMaxBot(seat: int, knobs: Knobs, seed: int | None = None)` — a stateful seat.
  - `.new_hand(seats: list[int])` — hand start, increments `hands` per opponent.
  - `.observe(actor: int, street: str, action: str, to_call: int, preflop_raises: int)` — feed in ONE publicly
    observed action; builds VPIP/PFR/3-bet/fold-vs-bet/aggression per opponent seat from it.
  - `.decide(obs: dict) -> dict` — decision incl. exploit deltas from its own opponent model.
- `class OppModel` — counters + three confidence-gated derivations: `fold_to_bet()` (from 8 observations),
  `threebet()` (from 6), `aggression()` (from 8); below that `None` → no exploit.
- `seed_modul_rng(seed: int | None)` (`:130`) — makes the stateless path (`decide_6max`) reproducible.
- `_dominated_offsuit(hc) -> bool` (`:97`) — the FLAT-FIX filter (A2o–A9o/K2o–K9o/Q2o–Q9o/J2o–J8o).

**Input/output.** In: the `obs` dict from `pokerbot/engine/table.py::obs_for` (`table.py:340-352`).
Load-bearing keys: `hole` (2 cards as `'As'` strings), `board`, `to_call`, `pot`, `my_stack`, `bb`,
`n_active`, `position` (label `EP/UTG/MP/HJ/CO/BTN/SB/BB`, plus `UTG+1..+3`/`LJ` for 7–10-max),
`preflop_raises`, `cur_bet`, `my_committed_street`, `street`, `can_check/can_call/can_raise`,
`raise_min/raise_max`. Optional `obs['icm']` (see `tournament.py`) — if the key is missing, the
tournament layer is NEVER touched (byte identity with the cash behaviour).
Out: `{"action": "fold"|"check"|"call"|"raise", "amount": int|None, "rationale": {...}}`. `rationale`
carries `hand` (169 class), `percentile`, `pos`, `profile`, `eff_bb`, `reasoning` (plain text) — pure
diagnostics, irrelevant for play.

**Dependencies.**
- HARD: `pokerbot.engine.cards.hand_class`, `pokerbot.engine.equity.equity_vs_class_range`,
  `pokerbot.engine.evaluator.best_five_name`, `pokerbot.strategy.preflop_strength` (169-class percentile,
  cached in `data/preflop_strength.json`), `pokerbot.strategy.postflop` (`VALUE_EQ`, `BLUFF_EQ`,
  `classify_board`, `cbet_policy`, `pick_value_size`, `PriorFoldModel`).
- REPLACEABLE: `pokerbot.strategy.preflop_gto.rfi` (solver-distilled RFI table; returns `None` when the
  file is missing → fallback to the percentile heuristic). `pokerbot.strategy.tournament` is imported ONLY when
  `obs['icm']` is present, and then lazily.

**Status.** `decide_6max` = stateless (except for the module RNG `_RNG`, `:127`). `SixMaxBot` = **per session**:
the `OppModel` per opponent lives across hands and is NEVER reset; `new_hand()` resets only the
hand state (`active`, `cur_agg`, `pf_aggressor`, `_street`, `_vpip_done`, `_pfr_done`). For a
clean A/B run a FRESH instance must therefore be built — otherwise the bot carries reads from the previous
block.

**Cost.** Postflop one Monte-Carlo equity run with `EQ_ITERS = 400` iterations per decision
(`sixmax.py:36`). Absolute latency not measured separately; documented as a system number: paired 6-max run
≈ **2 s per deck and arm single-core** (one deck = hero rotates over 6 seats, `../reports/TRAINER_WIRING.md:28`)
and **5 ten-handed tables per round in 120–129 ms mean / 200–213 ms max** in the MTT (`../reports/TOURNAMENT_MODE.md:82`).
Memory: negligible (one `OppModel` counter object per opponent seat).

**Measurement status.**
- Core `tag`, externally graded in absolute terms: **MEASURED POSITIVE — GTO score 85.9 % / EV loss 7.61 bb/100** over
  1781 moves from n=1500 hands (GTO Wizard Analyzer, `docs/STATE.md:1059`). Leaks per the same source:
  river (22.4 % mistake+blunder), blinds OOP, "as preflop caller" 23.5 % M+B vs 6.6 % as raiser.
- `flat_guard` (FLAT-FIX): **MEASURED POSITIVE — 3 runs `tag_flatfix` vs `tag`, 2992 paired decks each:
  +17.7 ± 6.4 (perm_p 0.0035) · +11.36 ± 6.88 (p 0.057, NEUTRAL) · +19.18 ± 7.01 (p 0.0035); pooled ≈ +16
  bb/100** — journal `data/autogym/journal.jsonl`, entry `typ: "FLATFIX-6MAX-VERDIKT"`, 2026-09-09 21:54:18;
  applied in `sixmax.py:59`. **A limitation that is not in the verdict and that I see in the code:** the
  measured arm was called `tag_flatfix`, and `sixmax.py:170` gates the solver-distilled RFI table on
  `k.name == "tag"`. The candidate therefore played its opens from the percentile heuristic instead of from the
  solver table — the three runs compare `flat_guard` AND "without the GTO RFI table" against the original,
  while the SHIPPED state (`flat_guard=True` on `tag`) keeps the table. Whoever adopts the number
  adopts this confound with it.
- Online reads (`_read`, `:358`): **MEASURED NEUTRAL — +3.64 ± 13.45 bb/100, CI [−22.0; +30.9]** (reads ON vs
  OFF, pargate6; `../reports/TRAINER_WIRING.md:85`). In the tournament context, isolated, even **negative:
  −13.9 ± 10.7 pp ROI** (2×2 decomposition, `docs/STATE.md:414-415`).
- A/A null test of the measurement chain: `tag` vs `tag`, 288 decks, **exactly 0.0 ± 0.0** (`../reports/TRAINER_WIRING.md:60`).
- Determinism: `tests/test_sixmax_seed.py` — same seed ⇒ identical decision sequence over 40 hands.

**Usable standalone?** Yes, this is the most easily extractable piece of the repo. Minimum needed:
`pokerbot/engine/` (cards, equity, evaluator, table for `obs_for`), `strategy/preflop_strength.py` (+ its
cache file, otherwise it computes Monte Carlo for 169 classes on first start), `strategy/postflop.py`,
`strategy/preflop_gto.py` (optional). Whoever only wants opponents builds `SixMaxBot(seat, PROFILES["station"])` and
feeds an `obs` dict in the form above — your own engine only has to provide these 17 keys for that.

**Pitfalls.** The bot is **seat-indexed and initiative-dependent**: `decide()` derives from
`self.pf_aggressor == self.seat` whether it plays the c-bet role or the check-to-the-raiser role (`:388-390`).
Whoever reuses `SixMaxBot` instances across hands and changes the seating order in the process (busts, moves)
MUST re-set `bot.seat = i` per hand — otherwise the role logic silently flips into its opposite (exactly this error
is documented in `mtt.py:236` as "mtt_sim find #4" and is corrected there in `bots_for()` every hand).
Second stumbling block: `observe()` must be called by EVERY bot for EVERY action of all seats (fan-out),
otherwise the opponent models stay empty and the profiles play their static knobs.

---

### HybridHero (tag core multiway + HU takeover) — `pokerbot/arena/hybrid.py`
**Purpose (1 sentence).** An agent that plays the `tag` league core multiway and, as soon as the pot has
collapsed to hero against exactly ONE villain, hands over to the heads-up bot (`PrinceOracle`).

**Interface.**
- `class HybridHero(seat=0, stack: str|None=None, seed: int|None=None, prince=None, kanal="gym")`.
  `stack` = name of the AUSLESE guard chain around the HU share (`None` = bare Prince v2.2).
- `.setze_sitz(seat)`, `.bind_table(table)`, `.new_hand(seats)`, `.observe(*args)` — SixMaxBot-compatible
  protocol so that an arena treats both agents alike.
- `.decide(obs) -> dict` — HU pot ⇒ `prince.decide(record)`, otherwise `bot.decide(obs)`.
- Counters: `.prince_decisions`, `.kern_fallbacks`.
- `KERN_PROFIL = "tag"` (`hybrid.py:12`).

**Input/output.** In: the same `obs` dict as `SixMaxBot`, PLUS a bound `Table` object
(`bind_table`) — without it `_heads_up()` is never true and the hybrid is a pure `tag`. The HU path builds in
`_record()` (`:51-61`) a dict with `spot` (from `brain.format_spot.spot_from_table`), `obs`, `legal`,
`history`, `street`, `hand_id`, `spot_fp`. Out: the same decision dict.

**Dependencies.** HARD: `pokerbot.arena.sixmax`, `pokerbot.coach.oracle.PrinceOracle`,
`pokerbot.brain.format_spot`, `pokerbot.coach.decision_log`, a `pokerbot.engine.table.Table`.
The Prince part pulls in the complete HU bot (`pokerbot/strategy/bot.py`, ~94 kB) — that is the heaviest
dependency in this part of the catalogue.

**Status.** Per hand via the encapsulated `SixMaxBot` (which in turn holds reads per session — here however
switched off: `self.bot._read = lambda obs: {}`, `:26`). `self.table` and `self.hand_id` must be re-set
per hand. `prince_decisions`/`kern_fallbacks` run over the whole run and are not reset.

**Cost.** Not measured separately. The HU path is considerably more expensive than the core (it runs the full
PokerBot stack); in the trainer it therefore runs with the resolver OFF (`../reports/TRAINER_WIRING.md:13`).

**Measurement status.** **REFUTED.** pargate6, 2992 paired decks each against the incumbent `tag`
(`../reports/TRAINER_WIRING.md:61-64`, journal `typ: "VERDRAHTUNG-6MAX-VERDIKT"`, 2026-09-09 19:26:50):
`hybrid` (without chain) **−23.56 ± 9.02**, CI [−40.8; −5.3] → REJECT · `hybrid_r8` **−21.73 ± 9.01**,
CI [−39.0; −4.4] → REJECT · `hybrid_r10` **−26.61 ± 8.93**, CI [−43.9; −9.4] → REJECT ·
`hybrid_r8` vs `hybrid` **+1.82 ± 5.58** → NEUTRAL (the guard chain does not save it).
Consequence in the product: the takeover is **default OFF** in the 6-max trainer, only `POKERB_SIX_TAKEOVER=1`
switches it on (`pokerbot/web/six_server.py:153-158`). Limitation of the verdict, as stated in the source:
self-ecology (`tag` plays against its own league); the hybrid was never graded externally.

**Usable standalone?** Only as a pattern, not as a building block — the 71 lines are trivial, the value is in the
two bots behind them. Whoever wants to rebuild the idea "strong HU bot takes over as soon as the pot is HU" should
know that it **lost when measured** here.

**Pitfalls.** `decide()` checks `self.table is not None and not self.table.hand_over and self._heads_up()`.
Whoever forgets `bind_table` silently gets a pure `tag` bot — the run looks successful and measures the
wrong thing. Exactly that is what `tests/test_hybrid.py:24` checks (`prince_decisions > 0`). Secondly, the HU branch is
`except Exception` (`:69`): every Prince error silently falls back to the core and is only visible in
`kern_fallbacks` — print this counter in every run.

---

### SNG arena (paired single-table tournaments) — `pokerbot/arena/tourney.py`
**Purpose (1 sentence).** Plays whole single-table SNGs of the hero against a league field and measures the ICM effect as
a paired experiment: arm A (ICM on) and arm B (ICM off) play the same seeds against the same profiles.

**Interface.**
- `run_tourney(structure: Structure, hero_factory, seed: int, icm_on: bool = True,
  field: list[str] | None = None) -> dict` — ONE tournament to the winner; returns
  `{"place": int, "payout": float, "hands": int}` of the hero.
- `run_batch(n: int, hero_factory, structure=SNG9, base_seed=1000) -> dict` — n pairs; returns per arm
  `{roi_pct, se_pct, netto, n, platz_verteilung}` plus `delta = {roi_pp, se_pp}` of the paired difference.
- `main()` / CLI: `python -m pokerbot.arena.tourney --tourneys 400 [--seed N] [--out datei.json]`.
  `--out` writes the raw data per pair (for exact pooling of several workers instead of averaging aggregates).
- `FIELD_PROFILES` (`:19`) = 8 opponents (`tag, lag, nit, station, maniac, tag, lag, nit`) ⇒ 9-max.

**Input/output.** In: a `Structure` (from `strategy/tournament.py`) and a `hero_factory(rng)` that
provides an agent with `.decide(obs)` and optionally `.observe(...)`/`.bind_table(...)`. Out: dicts as above;
money amounts in the same unit as `Structure.buyin`, ROI in percent or percentage points.

**Dependencies.** HARD: `pokerbot.arena.sixmax` (the field), `pokerbot.strategy.tournament`
(`Director`, `Structure`, `SNG9`), indirectly `pokerbot.engine.table`. The `hero_factory` is the
exchange point — that is where you plug in any bot of your own.

**Status.** Fresh per tournament: `Director`, agents, table. Stateless across the batch. Important:
`_mk_agents` (`:22`) builds the field bots fresh per tournament, so they carry no reads from tournament to tournament.

**Cost.** Not measured separately. Documented order-of-magnitude anchor from the same code family: a full
60-player MTT bots-only runs in **38.8–40.1 s / 131 rounds** (`../reports/TOURNAMENT_MODE.md:85`).

**Measurement status.** **MEASURED POSITIVE — this is the channel that validated the proportional risk premium**
(`docs/STATE.md:402-406`): μ-1 (full bubble factor on every call) **REFUTES itself: −8.1 ± 13.9 pp
ROI** with an over-tightening fingerprint (more 4th places — survived to the bubble, bled out there) →
doctrine fix → μ-2 **+9.2 ± 8.0 pp** (n=500; 2nd places 71 vs 47) → **μ-3: +10.02 ± 5.03 pp ROI,
95 % band [+0.2; +19.9], z = 1.99 — VALIDATED**, with MORE wins (214 vs 192) AND a better ladder
(n=1500 pairs, 6 parallel workers). Additional finding on the pressure lever against an ICM-playing bot field
(n=300/arm, paired): chipEV +6.6 / icm +7.7 / **icm+pressure +14.1 % ROI** — ordering clear, z = 0.76, so
significance still open (`docs/STATE.md:409-412`). The model fee (~4.8 pp) is not deducted in any of these numbers.

**Usable standalone?** Yes, if you take `strategy/tournament.py` + `engine/table.py` along. The rest is a
120-line game loop with paired seed management — rebuilding that is cheaper than adopting the coupling to
our `Structure` class if you have your own tournament structure.

**Pitfalls.** **Only the hero** gets the ICM lens (`:56-59`); the field deliberately stays chip-EV-naive.
Whoever equips both sides with ICM measures something else (that measurement exists and is called "defensive
ICM lens against an ICM field ≈ worthless, +1.1 pp", `docs/STATE.md:412-413`). Secondly: the game loop catches
every bot exception and plays `check/call/fold` (`:65-69`) — a broken candidate thereby produces
plausible but meaningless results instead of a crash.

---

### MTT director (60 players, 6 tables) — `pokerbot/arena/mtt.py`
**Purpose (1 sentence).** Runs a multi-table tournament: field generation by profile mix, tournament clock, side tables
fully automatic, global place assignment, table collapse and balancing, plus the ICM context generation for bots
and a hero advisor.

**Interface.**
- `class MTT(seed, hero_name="Du", hero_bot=None, n_players=60, seats_per_table=10, hands_per_level=12,
  start_stack=5000)`.
- State queries: `.level()`, `.level_index()`, `.hands_to_level()`, `.payouts()`, `.payouts_remaining()`,
  `.next_payout()`, `.rank_of(name)`, `.avg_stack()`, `.over()`, `.hero_out()`, `.hero_host()`,
  `.is_final_table()`, `.total_chips()`.
- Flow: `.build_table(host) -> Table` · `.bots_for(table) -> {seat: SixMaxBot}` ·
  `.start_stacks(table)` · `.play_bot_hand(host) -> [(name, start_stack)]` (busts) ·
  `.after_table_hand(table, host, start_stacks)` · `.play_side_tables()` ·
  `.advance_round(hero_busts)` (round close after a hero hand) · `.play_round_all()` (bots-only) ·
  `.run_bots_only(max_rounds=5000, audit=False) -> {winner, rounds, places}`.
- ICM: `.icm_ctx(table, seat, aggressor, start_stacks, pressure_cache) -> dict | None` ·
  `.hero_icm(table, seat, aggressor, start_stacks, obs) -> dict | None` (advisor text).
- `.audit_invariants()` — chip conservation, table sizes, balance ±1, gapless place assignment (assert-based).
- Free functions: `field_counts(n_bots, mix)` (largest-remainder rounding), `make_league_bot(profile, seed)`.
- Constants (`:27-68`): `N_PLAYERS 60`, `SEATS_PER_TABLE 10`, `START_STACK 5000`, `BUYIN 10.0`,
  `HANDS_PER_LEVEL 12`, `MTT_LEVELS` (10 levels, ante from level 3), `LEVEL_EXTENSION_FACTOR 1.5`,
  `PAYOUT_PCT_TOP9`, `FIELD_MIX`, `AVATARS`, `EXACT_ICM_AT 12`, `BUBBLE_WINDOW_FACTOR 1.6`,
  `PRESSURE_CAP 1.5`, `PRESSURE_SLOPE 0.6`, `ICM_HINT_BF 1.15`.

**Input/output.** In: an integer seed (controls seat draw, profile distribution, every bot RNG and every
deck) and optionally a `hero_bot`. Out: `Table` objects per hand, bust lists `(name, start_stack)`, and for
the advisor a dict with `bf`, `villain`, optionally `req_chip`/`req_icm`/`text`. The ICM context has the
keys `stacks`, `payouts`, `seat`, `aggressor`, `invested`, `pressure`, `pressure_mult` — or, in the
bubble window, ONLY `{pressure, pressure_mult}`.

**Dependencies.** HARD: `pokerbot.arena.sixmax` (field), `pokerbot.engine.table.Table` (needs
`stacks=`, `ante=`, `rebuy=`, `human_seat=`), `pokerbot.strategy.icm.bubble_factor`,
`pokerbot.strategy.tournament` (`BlindLevel`, `icm_pressure_mult`, `icm_required_equity`, `icm_scaled_req`,
`pick_villain`). The hero table itself is NOT played here but by the trainer (`web/six_server.py`).

**Status.** One `MTT` object per tournament: `entrants` (stacks, alive, place), `tables` (`TableHost` with
`names`, `button_name`, `hand_no`), `alive`, `next_place`, `round_no`, `hero_place`, `table_change`. None
of it is resettable — a new tournament = a new object. The league bots in the field carry their `OppModel`
across the whole tournament.

**Cost.** **MEASURED:** 5 side tables per hero hand **mean 120–129 ms, max ≈ 200–213 ms** (full field,
20 rounds, `../reports/TOURNAMENT_MODE.md:82`); a complete bots-only tournament (seed 7, audit every round)
**131 rounds in 38.8–40.1 s** (`:85`). Fallback knob for slower machines: `MTT.side_tables_every = 2`.

**Measurement status.** **UNMEASURED as a strategy** — there is no EV/ROI verdict for the MTT mode; the source
says so explicitly ("No measurement verdict — the mode is a trainer product, not a bot candidate",
`docs/STATE.md:44-45`). What is measured are mechanical properties (`tests/test_tournament_mode.py`,
7 tests, `../reports/TOURNAMENT_MODE.md:82-90`): chip conservation 60·5000 after every round, every place 1..60 exactly
once, balance ±1, determinism (seed 11 twice identical, seed 12 different). `FIELD_MIX` is
explicitly **a prior, not a measured fit** (`mtt.py:46-52`).

**Usable standalone?** Only together with our `Table` (which must know the `stacks=`/`ante=`/`rebuy=` parameters)
and the league. Two small parts are worth extracting: the **ICM economy tiering** in `icm_ctx`
(exact ≤ 12 remaining, otherwise bubble-window multiplier, otherwise chip EV) and the **rebalancing routine**
`_rebalance` (`:337-363`) — both are tournament logic you would otherwise have to derive yourself.

**Pitfalls.** The clock counts **hero hands**, not time, and every side table plays exactly ONE hand per
hero hand. A ten-handed table really takes longer for a hand than a heads-up table — the model ignores
that. Whoever pulls tournament statistics out of this director (field tempo, bubble timing) is therefore measuring a
synchronised artificial world: the documentation itself notes "60 → ~30 players in ~25 rounds … faster than
a real online MTT" (`../reports/TOURNAMENT_MODE.md`, addendum).

---

### ICM mathematics (Malmuth-Harville, exact) — `pokerbot/strategy/icm.py`
**Purpose (1 sentence).** Computes the $ value of tournament stacks exactly (bitmask DP over the place recursion) and
derives bubble factor and exact all-in call thresholds from it.

**Interface.**
- `icm_equities(stacks: list[float], payouts: list[float]) -> list[float]` — $ equity per player; exact,
  `lru_cache` over the bitmask (2^n states instead of n! paths); stops as soon as the place depth exceeds the last
  paid position.
- `icm_equities_mc(stacks, payouts, iters=20_000, rng=None) -> list[float]` — the same Harville assumption
  sampled, for large fields (n > `MC_THRESHOLD = 12`).
- `icm_equity(stacks, payouts, hero) -> float` — convenience wrapper.
- `bubble_factor(stacks, payouts, hero, villain) -> float` — `|ΔEq(lose)| / ΔEq(win)` for the flip
  of the effective stack; ≥ 1.0; `inf` if the win gradient is ≤ 0.
- `icm_call_threshold(stacks, payouts, hero, villain, to_call, pot_before) -> float` — exact equity threshold
  for an all-in call over three worlds (fold/win/lose): `(E_fold − E_lose)/(E_win − E_lose)`; returns
  `1.01` if a call can never be right, and falls back to chip-EV pot odds for flat payouts.

**Input/output.** In: two number lists (chips, prize money) + indices. `len(payouts) <= len(stacks)`;
the rest pays 0. Out: floats in the currency unit of the `payouts`, or a probability threshold.
**The convention of `icm_call_threshold` is critical and pinned in the docstring** (`icm.py:129-136`):
`stacks` = BEHIND stacks at the moment of decision, `pot_before` = total pot INCLUDING the villain's shove and hero's
investment so far, `to_call` = remaining payment. Whoever feeds it differently violates chip conservation.

**Dependencies.** NONE except the standard library (`functools.lru_cache`, `random` lazily in the
MC variant). This is the most cleanly isolated module of this part of the catalogue.

**Status.** Stateless. The `lru_cache` sits INSIDE the call and is cleared via `rec.cache_clear()`
(`icm.py:60`) before returning — there is no module-wide cache that lives across calls.

**Cost.** Not measured in seconds. Documented structural statement: exact is affordable up to ~10–12 players
(`MC_THRESHOLD = 12`, `icm.py:19`), above that the MC variant; in the MTT the exact computation is only switched on from
`EXACT_ICM_AT = 12` remaining (`mtt.py:64`). `bubble_factor` costs **three** full
`icm_equities` runs, `icm_call_threshold` likewise three.

**Measurement status.** **MEASURED POSITIVE (correctness, not EV):** `tests/test_icm.py` checks the recursion against
an **independent permutation enumeration** (deliberately a different algorithm) plus the closed form for
2 players; `tests/test_tournament.py` checks the book anchors (BF 2.56 ⇒ 71.9 % on the flip). There is no EV verdict
for this module — it delivers numbers, not policy; the policy in `tournament.py` is measured.

**Usable standalone?** Yes, without restriction — copyable as a single file without any repo dependency. This is
the module of this part that an outsider should most readily adopt instead of rewriting it.

**Pitfalls.** `bubble_factor` can return `float("inf")` (win gradient ≤ 0, e.g. when hero already
holds the covering stack and the payout jump dominates). Every caller must catch this case — in the repo
`tournament.icm_scaled_req` (`:124-125`), `icm_pressure_mult` (`:159`) and `mtt.hero_icm` (`:405`) do that
individually. Whoever only takes `max()`/means over a BF matrix otherwise gets `inf` or `nan` into the
strategy.

---

### Tournament doctrine + director — `pokerbot/strategy/tournament.py`
**Purpose (1 sentence).** The layer between ICM mathematics and the cash core: it translates bubble factors into
corrected call thresholds (on the call side only), provides tournament structures and runs a
single-table tournament.

**Interface.**
- `@dataclass(frozen=True) BlindLevel(sb, bb, ante=0, hands=10)`.
- `@dataclass(frozen=True) Structure(name, levels, payouts_pct, start_stack=10_000, buyin=100.0)` with
  `.level_at(hand_no) -> BlindLevel` (last level repeats) and `.payouts(n_entries) -> list[float]`.
  Ready-made structures: `SNG9` (50/30/20 %), `SNG6` (65/35), plus the sensitivity arms `FLAT9` (6 flat
  places) and `TOP_HEAVY9` (80/20).
- `icm_required_equity(req_chip: float, bf: float) -> float` — `r' = bf·r / (bf·r + (1−r))`; `bf ≤ 1` ⇒ `r`.
- `pick_villain(stacks, hero, aggressor) -> int` — the aggressor, otherwise the largest opposing stack.
- **`icm_scaled_req(req_chip, obs, to_call, pot) -> float`** — THE ONE entry point for the cash core
  (`sixmax._decide` calls exactly this, at three places: `sixmax.py:190`, `:227`). All-in calls
  (`to_call >= my_stack`) compute exactly via `icm_call_threshold`, everything else via the **proportional
  risk premium** `BF_eff = 1 + (BF−1)·(to_call/Stack)` (`tournament.py:131-133`).
- `icm_pressure_mult(obs, villains=None) -> float` — steal widening of the covering stack:
  `min(1.6, 1 + 0.5·(mean BF of the opponents against us − 1))`; respects a precomputed
  `ctx["pressure_mult"]` (MTT path). Is multiplied onto the open fraction in `sixmax.py:166-167`.
- `bf_matrix(stacks, payouts) -> list[list[float]]` — all pairwise BFs, for diagnostics/reports.
- `class Director(structure, names, seed=None)` — `.alive()`, `.payouts_remaining()`, `.over()`,
  `.next_table() -> Table`, `.icm_ctx(table, seat, aggressor) -> dict`, `.after_hand(table)`,
  `.results() -> [{name, place, payout}]`.

**Input/output.** `icm_scaled_req` reads `obs['icm']` with the keys `stacks` (start-of-hand chips per
seat), `payouts` (remaining prize money), `seat` (hero), `aggressor` (seat or `None`), `invested` (seat→already
invested; only for the all-in path) — plus `obs['my_stack']`. **If `obs['icm']` is missing, the function returns
`req_chip` unchanged; the cash core then never touches it (deliberate anchor protection.)**
Out: a corrected required equity in [0,1].

**Dependencies.** HARD: `pokerbot.strategy.icm`, `pokerbot.engine.table.Table` (only for the `Director`;
the doctrine formulas above are Table-free). Replaceable: the `Structure` constants are pure data.

**Status.** The formulas are stateless. The `Director` is **per tournament**: `entrants` (stack/alive/place),
`hand_no`, `_button_name`, `_next_place`, `_start_stacks`. `_start_stacks` is set in `next_table()` and
read in `after_hand()` — the two necessarily belong together.

**Cost.** One `icm_scaled_req` with BF path = three `icm_equities` runs; the all-in path = three more.
`icm_pressure_mult` = one BF per opponent, therefore precomputed once per hand in the MTT and cached
(`mtt.py:259-263`). Absolute latency not measured.

**Measurement status.**
- **Proportional risk premium: MEASURED POSITIVE / VALIDATED — +10.02 ± 5.03 pp ROI, 95 % band [+0.2; +19.9],
  z = 1.99, n = 1500 paired tournaments** (`docs/STATE.md:405-406`); mechanism fingerprint: more wins
  (214 vs 192) AND a better ladder.
- **Full bubble factor on every call: REFUTED — −8.1 ± 13.9 pp ROI** with an over-tightening pattern
  (`docs/STATE.md:402-404`). That is exactly why the proportional formula exists; it is not a refinement but
  a fix for a measured failure.
- **Pressure lever (`icm_pressure_mult`): MEASURED POSITIVE but not significant — icm+pressure +14.1 % ROI vs
  icm +7.7 vs chipEV +6.6 (n = 300/arm, paired, z = 0.76)**; in the 2×2 decomposition the pressure contributes
  +4.7 pp alone / +6.4 bundled (`docs/STATE.md:409-416`).
- Mechanics: `tests/test_tournament.py` — chip conservation over whole tournaments incl. ante side pots,
  determinism, book anchors, **cash parity** (without `obs['icm']` the sixmax core decides byte-identically).

**Usable standalone?** The doctrine formulas (`icm_required_equity`, `icm_scaled_req`, `pick_villain`,
`icm_pressure_mult`) yes — they need only `icm.py` and a dict. The `Director` not without our `Table`.

**Pitfalls.** The premium hits **exclusively the call side** (gap concept: jam and open ranges
stay chip-EV, because fold equity under ICM is the protected form of equity). Whoever applies `icm_scaled_req` to
the bet/jam side as well rebuilds exactly the over-tightening that was refuted as μ-1. Second, subtler
point: the all-in path must return the **uncalled excess** of the villain's shove to him
(`tournament.py:117-122`) and reduce the `behind` stacks for EVERY seat by `invested` — both are bugs caught in the
repo (third-party bets existed twice, hero was gifted other players' chips). Whoever copies the formula
and leaves out these two corrections calls too loosely at the bubble.

---

### Open Poker arena client (WebSocket) — `pokerbot/arena/openpoker.py`
**Purpose (1 sentence).** Connects the stateless 6-max core via WebSocket to the online arena
openpoker.ai — auth, lobby join, `your_turn` → decision → `action`.

**Interface.** `class OpenPokerClient(api_key, buy_in=2000, verbose=True)` with
`.position_label(n_active) -> str` (dealer-relative seating order → our position labels), `.reset_hand()`,
`async .run()` (connection loop), `async .handle(ws, msg: dict)` (message dispatch); `main()` as
CLI entry (`python -m pokerbot.arena.openpoker`, key via `OPENPOKER_API_KEY`).

**Input/output.** In: JSON messages from the server (`connected`, `table_joined`, `your_turn`, …). The
client maintains a light table model from them (`my_seat`, `dealer_seat`, `sb/bb`, `hole`, `board`, `street`,
`seat_stacks`, `preflop_raises`, `my_committed_street`) and builds the `obs` dict for `decide_6max` from it.
Out: an `action` message that mirrors back `hand_id` and `turn_token`. Unknown message types
are logged, not discarded.

**Dependencies.** HARD: `pokerbot.arena.sixmax.decide_6max`, `websockets` (lazily imported in `.run()`,
`:142`; if missing, the client prints `pip install websockets` and aborts). Otherwise only the standard library.

**Status.** Per connection/hand: the table model above; `.reset_hand()` resets board/street/`preflop_raises`.
No opponent model — it uses the stateless core, no `SixMaxBot`.

**Cost.** Not measured.

**Measurement status.** **UNMEASURED.** Only connectivity is documented: "endpoint reachability +
auth handshake confirmed (server responds exactly per docs)" (`docs/archive/EDGE_UND_ARENA.md:34-36`). There
is no bb/100 result from this arena, and the source itself notes that individual live fields
(e.g. the dealer position per hand) are only partially specified in the third-party docs. The module is listed in
`docs/archive/BOT_PARTS_CATALOG.md:105` as "TOOL" — tool, not product path.

**Usable standalone?** Only against exactly this provider. As a template, the separation "protocol adapter builds
`obs` → core decides → adapter forms `action`" is useful — that is the transferable pattern, the rest is
provider-specific.

**Pitfalls.** `position_label` silently falls back to `"CO"` when the table model is incomplete
(`:57-58`, `:63`). The bot then plays a wrong position without anything being noticed — whoever wants to use the client
in production must turn this default into a visible error.

---

### Haiku pilot (LLM steers exploit knobs) — `pokerbot/arena/haiku_pilot.py`
**Purpose (1 sentence).** Experiment: an LLM (Claude Haiku) reads the opponent profile every N hands and sets four
boolean exploit switches of the `AdaptiveExploiter`, to test whether LLM steering beats the automatic
knob setting.

**Interface.** `haiku_knobs(client, summary: dict, fold_curve: dict) -> Knobs` (one model call, JSON
back, default knobs on any error) · `class HaikuPilot(client, hero=0, iters=90, refresh=40)` with
`.decide(st)`, `.observe_opponent(st, a)`, `.observe_hand_end()` (re-sets every `refresh` hands as soon as
`prof.confidence() > 0.1`) · `main()` (`--hands`, `--refresh`, `--iters`).

**Input/output.** In: the opponent summary + the fold curve at 0.33- and 0.9-pot sizings. Out: a
`Knobs` object with `exploit_bluff`, `exploit_value`, `exploit_bluffcatch`, `probe` (each 0/1). The comparison
in `main()` prints bb/100 "auto-knobs" against "haiku-pilot" for three synthetic opponents.

**Dependencies.** HARD: `anthropic` (real API key from `pokerbot.config`),
`pokerbot.strategy.adaptive.AdaptiveExploiter`, `pokerbot.benchmark.beat_them_all`. **The
`AdaptiveExploiter` cluster is documented in the repo as orphaned** — no live path uses it, only
benchmarks and this script (`docs/archive/BOT_PARTS_CATALOG.md:20`).

**Status.** Per session: the encapsulated `AdaptiveExploiter` (opponent profile) + `self.h` (hand counter) +
`self.last` (most recently set knobs). No reset provided.

**Cost.** One LLM call per `refresh` hands (default 40) — so money and network latency, but deliberately NOT in
the per-hand loop. Not measured.

**Measurement status.** **UNMEASURED** — no result numbers of this pilot are stored in the repo. The overarching
mechanism it steers has since been measured negative: the exploit gate (HU PokerBot, 600 paired
decks per league profile) found **all eight diffs ON−OFF ≤ 0, pooled ≈ −12 bb/100 (SE ≈ 4.5)** and thereby declares
the exploit path refuted (`../reports/TRAINER_WIRING.md:74-95`, journal `typ: "EXPLOIT-GATE-VERDIKT"`).
That is not the same piece of code, but the same idea — whoever rebuilds the pilot should know this measurement.

**Usable standalone?** No, without `adaptive.py` + `beat_them_all.py` + API key nothing runs. Transferable is
only the pattern: **the LLM sets strategy flags at minute cadence, the fast engine decides every hand** —
no LLM in the per-hand loop.

**Pitfalls.** `haiku_knobs` catches every exception and then returns knobs with all defaults **at 1**
(`:44-46`) — a silently failed API call looks identical in the log to "the LLM wants all
exploits on". Whoever measures with it is, in doubt, measuring the error path.

---

## Products: trainer, coach, vision

This subsystem is everything that lets a human near the bot: two FastAPI game servers (heads-up and
6-max/tournament), a grading chain that grades every human decision against a bot reference and explains it in
German, session statistics and a screen bridge that reads a third-party poker software (PokerSnowie 4)
via template matching and plays it automatically. For a pure bot you need NONE of it — the servers
are thin wrappers around `engine/table.py`. Three things are interesting individually: the decision-capture/grader chain
(P0 schema, deterministic, fail-soft), the Snowie gate (how to prevent a bot from computing with misread
numbers) and the hand logger as a JSONL format.

---

## Web apps

### Heads-up server — `pokerbot/web/server.py`
**Purpose.** FastAPI app in which a human (seat 0) plays heads-up against the production bot, with a second,
identically configured bot as advisor and optional Claude coaching.

**Interface.**
- `class Session(stack=10000, sb=50, bb=100)` — holds `HeadsUpGame`, the opponent bot, the advisor bot, the coach,
  the session log path.
- `Session.start_hand() -> list[dict]` / `Session.advance() -> list[dict]` — starts, or lets the bot act
  until the human is to act; returns bot events.
- `Session.human_action(action: str, amount: int|None) -> list[dict]` — fetches the advisor recommendation BEFORE the move,
  feeds the opponent model, executes the action, lets the bot continue.
- `Session.beratung() -> dict|None` — champion recommendation at the current decision point (None = not to act).
- `Session.fingerprints() -> dict` — core fields of both bots (hash, stack, exploit, resolver flags, PRINCE flags);
  documents in the view that opponent and advisor play the same policy.
- `Session.view(events) -> dict`.
- HTTP routes: `GET /` (HTML), `POST /api/new_game {stack,sb,bb}`, `POST /api/next_hand`, `POST /api/action
  {action, amount}`, `GET /api/state`, `GET /api/advice`, `POST /api/coach/explain`, `POST /api/coach/review`,
  `POST /api/coach/ask {question}`.
- `main()` — argparse `--host/--port/--open`, starts uvicorn (default port 8000).

**Input/output.** In: JSON bodies (`ActionReq{action, amount}`, `NewGameReq{stack,sb,bb}`, `AskReq{question}`).
Out: `view()` dict with `state` (the `HeadsUpGame.state(hide=BOT)` dict), `fingerprints`, `human_idx`, `bot_idx`,
`bot_events` (each `{who, action, amount, rationale, street}`), `coach_available`, `match_over`. Coach routes return
`{"text": ...}`. Every finished hand is appended as full `game.state()` JSON to
`data/sessions/hu_<timestamp>.jsonl`.

**Dependencies.** Hard: `pokerbot.engine.game.HeadsUpGame`, `pokerbot.strategy.bot.PokerBot`, FastAPI/uvicorn/
pydantic. Hard with the default switched on: `pokerbot.strategy.gto_mode.apply()` and `pokerbot.strategy.auslese.
setze_env/wickle_decide/FINAL_STACK` (the repo's guard-chain profile), `pokerbot.runtime_config` (fingerprint +
misconfiguration gate). Replaceable: `pokerbot.coach.coach.Coach` (only the three coach routes).

**Status.** A single module global `SESSION` — the app is ONE player and ONE table. `POST /api/new_game`
replaces it completely; everything so far (opponent model, comments, log path) is gone afterwards. Within a session:
state per hand (`last_bot`, `last_human`, `counted`) and per session (`log_path`, the bot's opponent model).

**Cost.** Not measured in this module. The resolver is ON by default (`POKERB_RESOLVER=0` switches it off), which
dominates the response time; the comment in `server.py:44-46` names exactly that as the reason for the switch.

**Measurement status.** UNMEASURED as a product. The played configuration is the measured one: PRINCE, exploit OFF,
resolver ON, `wickle_decide(FINAL_STACK)` — per `docs/STATE.md:47-49` deliberately wired that way ("opponent AND advisor
= champion config"). The GTOW anchor of the policy itself is elsewhere (STATE.md:56-57: only v4-on-PRINCE −21.1 is
GTOW-confirmed).

**Usable standalone?** Yes: `python -m pokerbot.web.server --open`. Minimum needed are engine + strategy + FastAPI.
Without an Anthropic key everything runs except the three coach routes (`coach_available:false`).

**Pitfalls.** The env flags are set BEFORE the bot import (`server.py:20-27`), because `postflop.py`/`advisor.py`
read their flags at IMPORT TIME. Whoever imports the module from another process that has already loaded
`pokerbot.strategy` silently gets a different policy than the measured one. Also: `_INDEX` is read ONCE at
import — UI changes need a server restart (unlike `six_server`).

---

### 6-max / trainer / tournament server — `pokerbot/web/six_server.py`
**Purpose.** The main product server: human on seat 0 against 1–9 league bots, in five modes (`gto`, `exploit`,
`arena`, `tournament`, `match`), with the complete trainer chain (capture → grading → German feedback →
replay → report).

**Interface.**
- `class Session(stack=10000, sb=50, bb=100, mode="gto", players=6, seed=None)` — builds table, bot assignment,
  session paths, loads the coach modules lazily.
- `Session.start_hand(auto_advance=True) -> list[dict]` — new hand; `auto_advance=False` = step mode (client
  drives the bots via `/api/step`).
- `Session.human_action(action, amount, step_mode=False) -> list[dict]` — core: builds the decision record
  BEFORE `table.act()`, executes, appends the record only after a successful `act` (an illegal action must not leave a
  ghost record), feeds all opponent models.
- `Session.prefold() -> list[dict]` — pre-fold: plays the hand to completion immediately in the background; special cases
  `check_frei` (a free check cancels the pre-fold) and `kampflos`.
- `Session.step() -> list[dict]` — exactly ONE bot action.
- `Session.view(events) -> dict`.
- `Session._grade_and_flush()` — grades all records of the finished hand and renders the feedback (budget
  `GRADING_BUDGET_MS = 800`, warning on overrun, `six_server.py:40`).
- HTTP: `GET /` (six.html), `GET /training` (training.html), `POST /api/new_session {stack_bb, mode, step,
  players, seed}`, `POST /api/hand {step}`, `POST /api/action {action, amount: float|None, step}`,
  `POST /api/prefold`, `POST /api/step`, `GET /api/state`, `POST /api/analyze`, `GET /api/glossary`,
  `GET /api/feedback/last`, `GET /api/replay/last`, `GET /api/opponent_panel`, `GET /api/report`.
- `main()` — `--host/--port/--open/--trainer`; calls `grader.prewarm()` once at startup.

**Input/output.** The `view()` dict is the contract with the client; load-bearing keys: `hand_no, button, sb, bb,
street, board, pot, current_bet, to_act, hand_over, result, human_seat, session_net, hands_done, seats[]
(seat/name/stack/hole/folded/all_in/committed_street/is_human/is_button/is_turn/pos/net/won), legal, bot_events,
mode, coach (the feedback dict at hand end), difficulty{profiles, error_rate}, prince_seat, arena_news,
tournament, prefold`. Two JSONL files are written per session:
`data/sessions/session_<sid>.jsonl` (hand records) and `data/sessions/decisions_<sid>.jsonl` (graded
decision records).

**Dependencies.** Hard: `engine/table.Table`, `arena/sixmax` (PROFILES/SixMaxBot),
`web/session_log`, FastAPI. Hard only in tournament mode: `arena/mtt.MTT`. Soft (all via `_coach(name)` lazily +
`try/except`, every missing file only switches off its feature): `coach.registry`, `coach.difficulty`,
`coach.decision_log`, `coach.grader`, `coach.templates_de`, `coach.oracle`, `coach.replay`,
`coach.opponent_panel`, `coach.trainer_report`, `coach.glossar_de`, `coach.range_story`,
`analysis.session_analysis`.

**Status.** A module global `SESSION`; `POST /api/new_session` replaces it (the registry writes the
end line beforehand). Per hand: `_pending_decisions`, `prefold_state`, `last_graded`, `last_feedback`, `last_hand_record`.
Per session: `human_net`, `hands_done`, `_grade_counts`, `last_error_rate`, the bots' opponent models, in the tournament
additionally the complete `MTT` state. Resetting means: build a new `Session`.

**Cost.** Grading budget 800 ms per hand (constant, with console warning on overrun). First hand
after `prewarm()` measured 7.8 ms grading (`docs/STATE.md:494`); without prewarm the first `decide()` cost ~1.6 s.
Side tables in the tournament ≈ 120–130 ms per hero hand (`docs/STATE.md:35`).

**Measurement status.** Mixed.
- Trainer chain overall: MEASURED POSITIVE as a gate — "autotest 8/8 PASS over 800 hands / 1411 decisions"
  (`docs/STATE.md:496`).
- Prince HU takeover in HU-collapsed 6-max pots: **REFUTED** — hybrid −23.6 ± 9.0, hybrid_r8 −21.7 ± 9.0,
  hybrid_r10 −26.6 ± 8.9 bb/100 vs league core `tag`, 2992 paired decks each, all REJECT
  (`docs/STATE.md:50-52`, journal `VERDRAHTUNG-6MAX-VERDIKT`). Hence default OFF
  (`POKERB_SIX_TAKEOVER=1` switches it on).
- Exploit reads of the league: **REFUTED** — ON vs OFF, 600 paired decks, all 8 diffs ≤ 0, pooled ≈ −12 bb/100
  (`docs/STATE.md:53-55`, journal `EXPLOIT-GATE-VERDIKT`).
- The league core `tag` with `flat_guard`: MEASURED POSITIVE, +17.7 ± 6.4 / +11.4 ± 6.9 / +19.2 ± 7.0 bb/100 in three
  pargate6 runs (journal `FLATFIX-6MAX-VERDIKT`).
- Tournament and pre-fold mode: UNMEASURED as EV ("No measurement verdict — the mode is a trainer product, not a
  bot candidate", `docs/STATE.md:44-45`); function gates: `tests/test_tournament_mode.py`, `tests/test_prefold.py`.

**Usable standalone?** Yes: `python -m pokerbot.web.six_server --open` (table) or `--trainer` (coaching UI).
Minimum: engine + arena league + FastAPI; the entire `coach/` layer may be missing, then you play without grading.
Multiway via `?players=9` or `NewReq.players` (2–10).

**Pitfalls.** The trainer modules are loaded via `importlib` inside a bare `except Exception` — a
syntax error or a missing import in `coach/grader.py` switches grading off SILENTLY, without an error message in the
server log. Whoever debugs the chain must call `_coach("grader")` by hand. Second pitfall: `ActionReq.amount`
is deliberately `float` — in the tournament the quarter-bb slider at bb=50 produces amounts like 187.5, and an `int`
field responded with pydantic 422, which the client renders as game state (empty table, "Hand #undefined";
`six_server.py:582-585`).

---

### Browser bridge (serverless trainer) — `pokerbot/web/browser_bridge.py` + `web/` (2026-09-24)
**Purpose.** Lets the complete trainer (`six_server.Session`, league, grader, feedback, replay, report) run in the
visitor's browser — Pyodide (Python 3.13 as WebAssembly) in a Web Worker, no server. This is
the version on https://quantplay.io.
**Interface.** `dispatch(method: str, path: str, body: str | None) -> str` returns JSON
`{"status": int, "body": str}`; `body` is the response text of the FastAPI endpoint. Unknown routes → 404
(the UI fallbacks `/api/feedback`→`/api/feedback/last`, `/api/glossar`→`/api/glossary` stay intact),
invalid bodies → 422, exceptions → 500 with text (the table never freezes). Query strings are ignored.
**Why not the ASGI app itself:** FastAPI runs synchronous endpoints in the threadpool; Pyodide has no
threads (`RuntimeError: can't start new thread`, measured 2026-09-24). Therefore the endpoint functions are
called directly and their pydantic models are reconstructed from the body (`typing.get_type_hints`, because the
annotations are strings).
**Browser side.** `web/src/bridge.js` replaces `window.fetch` for `/api/*` (as the FIRST script in `<head>`,
injected by `web/build.py`), shows a loading overlay and forwards requests to `web/src/worker.js`; the
worker loads Pyodide 0.28.3 from jsDelivr, the Pyodide packages (pydantic, anyio, …), five vendored wheels
(`web/wheels/`: fastapi, starlette, treys, typing_inspection, annotated_doc — with `deps=False`, otherwise
micropip tries PyPI) and the bundle `pokerbot_bundle.zip` (pokerbot/*.py+*.html without vision/benchmark, knowledge_base
math/ranges/cfr/postflop-json/tournament, `data/preflop_strength.json`). `training.html` itself is unchanged
(one source for local and online).
**Dependencies.** Hard: `six_server` importable without torch (Prince takeover off, advisor nets missing in the
bundle and loaded lazily → fallback). `six_server` reads `static/six.html` at import → HTML belongs in the
bundle (first live error). Session logs land in the worker's MEMFS (volatile).
**Status.** In production on quantplay.io; locally `python web/build.py` + `python -m http.server 8765 --directory
web/dist`. Deploy: `cd web && vercel deploy --prod` (project `quantplay`, without git hookup).
**Cost.** First call: Pyodide ~10 MB + packages (CDN, cached) + 1.6 MB own files; cached afterwards.
**Measurement status.** Node+Pyodide: import 0.9 s; 5 hands with grading 0.32 s, slowest request 0.11 s
(tournament 0.35 s). Not a strength measure — identical code as locally. Tests: `tests/test_browser_bridge.py` (5).
**Pitfall.** Whoever does not rebuild `web/dist/` deploys the old trainer: `dist/` is versioned and is served by
Vercel 1:1; `index.html` carries the build hash, the bundle is cache-busted via `?v=`.

### Hand logger — `pokerbot/web/session_log.py`
**Purpose.** Turns a fully played `Table` into ONE JSONL record and appends it to a file.

**Interface.** `build_hand_record(table) -> dict`; `append_record(path, rec: dict) -> None` (creates directories,
writes UTF-8 + `ensure_ascii=False`).

**Input/output.** In: a `Table` after hand end. Out:
`{hand_no, button, sb, bb, human_seat, positions{seat:pos}, hole{seat:[cards]}, board[], actions[{street, seat,
pos, action, amount, is_human}], result, net{seat:chips}}`. `amount` is `h["to"] or h["amount"]` — so for
`bet/raise` the street commit-TO total, for `call` the chips added (the convention of `table.py`).
`net` = chips won minus `committed_total`.

**Dependencies.** None except the duck-typed `Table` interface (`seats`, `history`, `result`, `hand_no`,
`button`, `sb`, `bb`, `board`, `n`, `position_label`). Freely replaceable.

**Status.** Stateless.

**Cost.** Not measured (one `json.dumps` + one append per hand).

**Measurement status.** UNMEASURED — pure format module. It is however the input of `analysis.session_analysis`,
`coach.replay`, `coach.trainer_report` and `coach.export_gtow`.

**Usable standalone?** Yes, if you rebuild the Table interface. `append_record` is also reused in the repo for
the registry and the GTOW ledger.

**Pitfalls.** The filter `if "player" not in h` discards the `blinds` and `deal` events of the engine history.
Whoever wants to animate from the record later must reconstruct blinds and board reveal — exactly what
`coach/replay.py` does. Also, the dict keys are STRINGS after the JSON round trip, not ints.

---

### Training dashboard — `pokerbot/web/train_dashboard.py`
**Purpose.** Tiny FastAPI server that displays `data/training_metrics.jsonl` + `data/eval_gates.json` as
canvas charts during a pod training run.

**Interface.** `GET /` (reads `static/train_dashboard.html` fresh per request), `GET /api/metrics ->
{"metrics": [...], "gates": {...}|None}`; `main()` with `--host/--port/--open` (default port 8001).

**Input/output.** In: two files in the data directory, streamed from the pod via scp. Out: the JSON above.
Missing/broken files yield an empty list or `null`, never an error.

**Dependencies.** FastAPI + `pokerbot.config` (only for `DATA_DIR`). Trivially replaceable.

**Status.** Stateless.

**Cost.** Not measured.

**Measurement status.** UNMEASURED — observation tool, belongs to the (now secondary) LLM training track.

**Usable standalone?** Yes, but only meaningful with the pod training run that writes the JSONL.

**Pitfalls.** There is no schema check: the HTML expects specific metric keys; whoever hooks up a different
training script sees empty charts instead of an error message.

---

### UI files — `pokerbot/web/static/{index.html, six.html, training.html, train_dashboard.html}`
**Purpose.** Four standalone HTML pages without a framework: HU table (`index.html`), 6-max table (`six.html`,
19 KB), trainer interface with coaching panel (`training.html`, 75 KB — table left ~60 %, panel right ~40 %,
Snowie layout 2560×1440), training dashboard.

**Interface.** No Python API. `training.html` documents its server contract in the header comment:
`POST /api/new_session|/api/action|/api/hand|/api/analyze`, `GET /api/glossary` (fallback `/api/glossar`),
`GET /api/replay/last`, `GET /api/bot_read` (fallback `/api/opponent_panel`), plus the `view` fields.

**Input/output.** Every POST response is the FULL `view()` dict; `render(v)` redraws everything from it — there
is no incremental client state.

**Dependencies.** Only the routes of the respective server. All optional fields degrade to placeholders.

**Status.** In the browser; no server state.

**Cost.** Not measured.

**Measurement status.** UNMEASURED (UI). As a gate there is: `six.html` byte-identical on the trainer build (P2-7,
`docs/STATE.md:496-497`) and browser verification at 2560×1440.

**Usable standalone?** Only together with the matching server.

**Pitfalls.** `six_server` reads `six.html`/`training.html` FRESH per request (edit → F5 suffices),
`server.py` caches `index.html` at import (edit → restart needed). This asymmetry is guaranteed to cost
half an hour once.

---

## Trainer chain (`pokerbot/coach/`)

The chain is: `decision_log` (snapshot) → `grader` (4 math checks) + `oracle` (reference bot) → `templates_de`
(German text) → `replay`/`trainer_report`/`opponent_panel` (views). It is deterministic, works
ONLY on dicts and needs no server.

### Decision capture — `pokerbot/coach/decision_log.py`
**Purpose.** Builds from the live `Table`, exactly BEFORE `table.act()`, an immutable snapshot of the
human decision (schema `trainer.decision.v1`).

**Interface.**
- `capture_decision(table, session_id: str, hand_no: int, mode: str, action: str, amount) -> dict` — pure
  read, does not mutate the table.
- `spot_fingerprint(spot: dict) -> int` — crc32 over canonical JSON of
  `{street, board, hero_hole, pot, to_call, line}`; NEVER `hash()` (process-salted).
- Constants: `SCHEMA_VERSION`, `HUMAN_SEAT = 0`, `CAPTURE_BUDGET_MS = 5.0`.

**Input/output.** Out: `{schema, session_id, hand_id ("<sid>-<hand_no>"), ts, mode, street, spot, obs, legal,
history, human_action{action, amount}, spot_fp}`. `spot` = `asdict(format_spot.spot_from_table(...))`,
`obs`/`legal` are literally `table.obs_for(0)` / `table.legal_actions()`, `history` only the entries with
`player`. `amount` for `bet/raise` = commit-TO total in chips; for `allin` `amount=None` and the effective
size sits in `legal["raise_max"]`. The grade fields (`checks`, `oracle`, `grade`, `grade_typ`,
`erklaerung_kurz`, `grade_ms`) are added later by `grader.grade_decision`.

**Dependencies.** Hard: `pokerbot.brain.format_spot.spot_from_table` and the Table interface. Otherwise only
stdlib.

**Status.** Stateless.

**Cost.** MEASURED in its own self-test: budget 5 ms, `min()` over 5 runs must stay below it
(`decision_log.py:123-129`); the module deliberately calls neither equity nor advisor nor oracle.

**Measurement status.** MEASURED POSITIVE (function, not EV): own self-test green —
`python -m pokerbot.coach.decision_log` checks schema keys, non-mutation, fp determinism, collision freedom
and the latency. Part of the "11/11 module selftests green" gate (`docs/STATE.md:497`).

**Usable standalone?** Yes, if you take `format_spot` along. Whoever has their own spot format only needs the
`spot_fingerprint` idea (crc32 instead of `hash`).

**Pitfalls.** The caller MUST append the record to the pending list only after a successful `table.act()` —
otherwise every illegal action (HTTP 400) leaves a ghost record that is graded later. That is
caller discipline, not enforced by the module.

---

### Reference oracle — `pokerbot/coach/oracle.py`
**Purpose.** Provides, for a decision record, the action of a reference policy: PRINCE v2.2 (the HU production bot)
for heads-up spots, the neutral league core `tag` for multiway spots.

**Interface.**
- `record_to_hu_state(rec: dict) -> dict` — projects a (6-max) record onto the HU `game.state()` dict that
  `PokerBot.decide` consumes; modelled 1:1 after `benchmark/gtowizard.py`. Raises `ValueError` if not exactly
  2 players are active.
- `class PrinceOracle(seed=7, stack: str|None=None, kanal="gym")` with `.decide(rec) -> {source, action, amount,
  rationale}` — `stack` optionally wraps the AUSLESE guard chain (`wickle_decide`) around `decide`.
- `class SixMaxOracle(profile="tag")` with `.decide(rec) -> {...}`.
- `oracle_decision(rec) -> dict` — routes by `n_active == 2`.
- `oracle_diff(rec, oracle=None) -> {"match": bool, "oracle_action": str, "size_diff_frac": float|None,
  "oracle": dict}` — `size_diff_frac` = |human TO − oracle TO| / pot-as-faced, only when BOTH are aggressive.

**Input/output.** In: the `trainer.decision.v1` record. Out: the dicts above; amounts are commit-TO
street totals in chips, `allin` resolves to `legal["raise_max"]`. Every synthesised action passes through
`api.legalize` (`_legalized`) before it is returned.

**Dependencies.** Hard: `pokerbot.strategy.bot.PokerBot` (lazily imported), `pokerbot.strategy.gto_mode`,
`pokerbot.arena.sixmax._decide` + `PROFILES`, `pokerbot.brain.api.legalize`. Replaceable only by plugging in your own
reference policy — the interface (`.decide(rec)`) is narrow.

**Status.** Module singletons `_PRINCE` / `_SIXMAX`. They DO NOT LEARN (the learning paths `observe_opponent` /
`observe_hand_end` are deliberately never called) and are re-seeded before every call with `random.Random(rec["spot_fp"])`
— which is why reuse is safe and grading is repeatable. Nothing needs to be reset.

**Cost.** Not measured directly. The module switches `use_resolver`/`use_turn_resolver` explicitly OFF, with the
justification that a cold river solve costs seconds (`oracle.py:172-174`) — that is this module's latency
decision.

**Measurement status.** MEASURED POSITIVE (function): own self-test green, part of the 11/11 gate
(`docs/STATE.md:497`). As a 6-max PLAYER the HU projection is REFUTED (see six_server: hybrid arms
−21.7 to −26.6 bb/100, journal `VERDRAHTUNG-6MAX-VERDIKT`) — as a GRADING reference it stays in use and
is honestly called "bot assessment" in the text.

**Usable standalone?** Yes, if you take PRINCE or the league core along. Whoever only wants the adapter:
`record_to_hu_state` is independent and shows cleanly how to tip an n-player spot onto a HU solver.

**Pitfalls.** The env flags (`POKERB_PRINCE=1` + `gto_mode.apply()`) are set at module import, BEFORE any
strategy import. Whoever imports `pokerbot.strategy` beforehand grades against a different policy than intended — and
does not notice. Secondly: `state["hand_id"]` must not be missing, otherwise a scalar fallback in the bot
(`LINE_U`) kicks in and the decision drifts.

---

### Grader — `pokerbot/coach/grader.py`
**Purpose.** Grades ONE decision record with four cheap deterministic checks plus the oracle diff and
assigns a grade from `{ok, teuer, leak}` from that.

**Interface.**
- `grade_decision(rec: dict) -> dict` — mutates the record IN PLACE: sets `checks`, `oracle`, `grade`,
  `grade_typ`, `confidence`, `erklaerung_kurz`, `grade_ms`.
- Callable individually: `check_pot_odds(rec)`, `check_mdf(rec)`, `check_sizing(rec)`, `check_advisor(rec)`.
- `assemble_grade(checks, oracle_diff, street, n_active) -> {grade, grade_typ, confidence, erklaerung_kurz}`.
- `prewarm() -> dict` — once at server start: loads the advisor nets, builds a throwaway `PokerBot` and
  grades a synthetic record; returns an availability map.
- Thresholds as module constants: `POT_ODDS_TOLERANCE 0.05`, `MDF_SMALL_BET_X 0.5`, `SIZING_ERR_HARD 0.5`,
  `MIX_SUPPORT 0.15`, `OK_SIZE_DIFF 0.25`, `EQUITY_ITERS 600`.

**Input/output.** In: the record. Out (in the record): `checks = {pot_odds{req, eq_max, violated},
mdf{mdf, size_faced, strength, violated}, sizing{human_frac, snapped_frac, err, violated},
advisor{available, node, role, dist{aktion:p}, chosen, p_chosen}}`, plus `grade` ∈ {ok, teuer, leak},
`grade_typ` ∈ {pot_odds, mdf, sizing, advisor_freq, oracle_diff} and a `confidence` label
("math (unassailable)" / "solver frequency (HU-trained, approximation)" / "bot assessment").
The rule: `leak` ONLY on a hard math violation, never because a reference was missing; `ok` on mixed
support (advisor frequency ≥ 15 %), oracle match or close sizing; otherwise `teuer`.

**Dependencies.** Hard: `pokerbot.brain.api` (equity/required_equity/mdf/hand_rank),
`pokerbot.brain.understanding` (position, `STRONG_MADE`), `pokerbot.strategy.advisor` (the solver-frequency MLPs),
`pokerbot.strategy.postflop.snap_to_tree/snap_raise_to_tree`, `gto_mode`. Soft: `coach.oracle` — if it is missing or
raises, the diff degrades to `{"source": "none"}` and the grade remains possible.

**Status.** Stateless per call. The advisor nets and blueprint caches are module-global and read-only.

**Cost.** First graded hand after `prewarm()` 7.8 ms (`docs/STATE.md:494`); without prewarm the first `decide()` alone
cost ~1.6 s of the 800 ms budget. The autotest gates the median grading latency at 250 ms
(`autotest.py:36 MEDIAN_GRADE_MS_BUDGET`).

**Measurement status.** MEASURED POSITIVE (function + sanity): self-test green; autotest 8/8 over 800 hands /
1411 decisions (`docs/STATE.md:496`). The sanity check "station is graded worse than tag" only separates
cleanly from ~300 graded decisions per profile — at ~120 the rates were in the noise (.057 vs .059,
`docs/STATE.md:494-496`), which is why the autotest WARNs on small runs instead of failing. NO EV measurement: the
grader does not play, it grades.

**Usable standalone?** Only with `brain/api` + `brain/understanding` + `strategy/advisor` + `strategy/postflop`. The
four checks individually are however readable, adoptable recipes; `check_pot_odds` needs only an equity function.

**Pitfalls.** The pot conventions are error source no. 1 and are nailed down in the docstring:
`required_equity(to_call, pot)` with pot AS-FACED (villain's bet is already in), `mdf(bet, pot)` with the PRE-bet pot
(`spot.pot - spot.to_call`). Whoever confuses one of the two gets systematically wrong grades that still
look plausible. Secondly: `check_advisor` queries the net by POSITION, the oracle internally by INITIATIVE —
two different quantities from the same net that sit side by side in the record and must not be
confused.

---
### German feedback templates — `pokerbot/coach/templates_de.py`
**Purpose.** Renders graded records into warm German sentences; computes NOTHING and decides NOTHING itself.

**Interface.**
- `render_decision_feedback(rec: dict) -> {"text", "html", "terms"}` — one decision, 1–2 sentences.
- `render_hand_feedback(records: list[dict], hand_result: dict|None=None, mode="gto") -> {"text","html","terms"}`
  — only the suboptimal decisions, one line each with street tag + reason + bot frequencies, followed by the
  strategy section (range narrative).
- Helper formatters that are useful individually: `eins_von(p)`, `freq_vergleich(p)`, `pot_frac_de(frac)`,
  `equity_satz(eq, req)`.
- `TERMS_USED` — frozenset of all glossary term ids these templates can emit.

**Input/output.** In: the graded record; every access goes through `.get()` with a German fallback. An
unknown `grade` deliberately raises `ValueError` (vocabulary pinned: `ok`/`teuer`/`leak`). Out: `text` (plain text),
`html` (with glossary spans via `glossar_de.markup`, fallback = text), `terms` (the term ids that occur).

**Dependencies.** Soft: `coach.glossar_de` (without it `html` falls back to `text`), `coach.range_story`
(without it the narrative falls back to the old heuristic). Otherwise stdlib.

**Status.** Stateless, deterministic.

**Cost.** Not measured; runs within the 800 ms hand-end budget.

**Measurement status.** MEASURED POSITIVE (function): self-test checks branch coverage, determinism and
TERMS_USED coverage; part of the 11/11 gate (`docs/STATE.md:497`).

**Usable standalone?** Yes — it is pure dict→text. Whoever builds their own records only has to fill `grade`, `grade_typ` and the
`checks`.

**Pitfalls.** The language layer must not compute any number ANEW; all numbers must be in the record. Whoever
"quickly" derives a quantity here breaks the convention and risks a text that contradicts the grade.

---

### Language contract + LLM backend — `pokerbot/coach/language.py`
**Purpose.** Pins the payload schema `coach.v1` between grader, templates and optional render backends and
gates LLM text on the numbers from the payload.

**Interface.** `make_payload(...) -> dict`, `validate_payload(payload) -> dict` (raises on vocabulary drift),
`validate_numbers(text, payload) -> list[str]` (returns the numbers that are in the text but NOT in the
payload), `get_backend(name="templates") -> LanguageBackend`, `class TemplateBackend`, `class OllamaBackend`
(local `qwen3:8b` via `http://localhost:11434`, hard timeout limit 2 s, fallback to templates).

**Input/output.** Payload schema: `{schema:'coach.v1', mode, hand_id, street, hero_pos, grade, grade_typ,
confidence, human_action{action, amount_bb?}, oracle_action|None, numbers{equity_pct?, required_equity_pct?,
mdf_pct?, pot_bb?, to_call_bb?, bet_frac_pot?, snapped_frac_pot?, advisor_*_pct?, spr?, ev_diff_bb?},
strategic|None, mixed{is_mixed, dist}|None, glossar_terms[]}`. Missing values are OMITTED, never set to 0.

**Dependencies.** `coach.templates_de` for the template backend; `requests`/urllib for Ollama. Without Ollama
everything runs through templates.

**Status.** One module counter `FALLBACKS`.

**Cost.** Ollama timeout hard at 2.0 s (`OLLAMA_TIMEOUT_S`); templates after that.

**Measurement status.** UNMEASURED as a product lever. Self-test green (part of the 11/11 gate). The LLM backend is NOT
wired into the shipped path — `six_server` calls `templates_de` directly.

**Usable standalone?** Yes. `validate_numbers` is the transferable part: the rule "an LLM may rephrase,
but not invent a number" is implemented here as a checkable function.

**Pitfalls.** The number whitelist must distinguish board counts ("3 cards") and lexical forms ("3-bet") from
real numbers — there are special rules for that (`_BOARD_COUNT_WHITELIST`, `_LEXICAL_NUM_RE`). Whoever
wants to gate their own texts trips over exactly that.

---

### Glossary — `pokerbot/coach/glossar_de.py`
**Purpose.** The single registry of German poker terms of the coaching layer plus the markup mechanism that
makes them clickable in the text.

**Interface.** `term(name, text=None) -> dict|str|None`, `get(term_id) -> dict`, `markup(text) -> str`
(sets `<span class="term" data-term="...">`), `as_json() -> list[dict]` (the route `GET /api/glossary`),
`all_terms() -> set[str]`.

**Input/output.** Entry: `{begriff, synonyme[], erklaerung (1–3 sentences, ≤ 220 characters), formel?, quelle?}`.
Formulas/sources come from the docstrings in `knowledge_base/math/formulas.py`.

**Dependencies.** None except stdlib.

**Status.** Stateless (module constants + compiled regexes).

**Cost.** Not measured.

**Measurement status.** MEASURED POSITIVE (coverage): 61 entries (`docs/STATE.md:497`), minimum requirement
`MIN_ENTRIES = 50`; self-test checks length limit and markup idempotence.

**Usable standalone?** Yes — it is one file of text plus two regex functions.

**Pitfalls.** `markup()` must not run twice: already-set spans are skipped via `_SPAN_RE`.
Whoever HTML-escapes the text beforehand destroys the detection.

---

### Session registry — `pokerbot/coach/registry.py`
**Purpose.** Append-only JSONL with one start and one end line per trainer session, because the module global
`SESSION` dies completely on "New".

**Interface.** `register_start(session) -> dict|None`, `register_end(session) -> dict|None`,
`sessions(path=None) -> list[dict]` (folds start/end per `session_id`, last wins, order = first
occurrence). Path: `data/trainer/registry.jsonl`.

**Input/output.** In: a duck-typed session object (`session_id`, `path`, `decisions_path`, `table`,
`bots`, `mode`, `hands_done`, `human_net`). Out: start line `{event:'start', session_id, ts, mode, stack_bb,
session_log_path, decisions_path, profile_assign, fingerprint}` — `fingerprint` = `gto_mode.fingerprint()`, i.e.
the exact flag set under which grading took place. End line `{event:'end', session_id, ts, hands_done, human_net}`.

**Dependencies.** `pokerbot.strategy.gto_mode.fingerprint`, `pokerbot.web.session_log.append_record`,
`pokerbot.config`. All replaceable.

**Status.** Two lines per session; otherwise stateless. The reader skips broken lines.

**Cost.** Not measured (two appends per session).

**Measurement status.** MEASURED POSITIVE (function): self-test checks folding, torn-line tolerance and that a
write error only produces a warning; part of the 11/11 gate.

**Usable standalone?** Yes.

**Pitfalls.** The mode comes BINDINGLY from the session, never from an env variable — otherwise the provenance
of the grading would be wrong. And: `register_end` must run BEFORE the session is replaced, otherwise the end line
is missing permanently.

---

### Difficulty controller — `pokerbot/coach/difficulty.py`
**Purpose.** Translates the error rate of the last session into a harder or softer opponent lineup.

**Interface.** `error_rate(decision_records) -> (rate, n)`, `default_composition(mode="gto") -> dict`,
`update(session_error_rate, current_composition, n=None) -> dict` (pure, at most ONE step),
`load_state()`, `save_state(composition, rate, n, ts)`, `current_assignment() -> {seat: profil}`.

**Input/output.** Composition: `{tier: int, profiles: {seat: profilname}, exploit_gain: float, mode: str}`.
Ladder `PRESET_LADDER` T0…T4 (T2 = the default lineup tag/lag/nit/station/maniac). Target band
`TARGET_BAND = (0.10, 0.20)`, below `MIN_DECISIONS = 30` nothing moves. The `exploit_gain` fine dial exists
only in exploit mode. State file `data/trainer/difficulty.json`.

**Dependencies.** `pokerbot.config` (only DATA_DIR); the profile names must exist in `arena/sixmax.PROFILES`.

**Status.** One JSON file; losing it is harmless (default T2).

**Cost.** Not measured (pure arithmetic).

**Measurement status.** UNMEASURED as a learning effect. The 10–20 % band is declared in the docstring itself as a HYPOTHESIS
(85 % rule), not as a measurement. The controller code is green per self-test.

**Usable standalone?** Yes, completely — `update` is a pure function with no import except `config`.

**Pitfalls.** `six_server` calls the controller only in `gto` mode and only if the registry knows a PREVIOUS session
with `error_rate` (`six_server.py:129-135`). Whoever tests without a finished session in the registry
never sees an adjustment and wrongly takes the module for dead.

---

### Replay compiler — `pokerbot/coach/replay.py`
**Purpose.** Builds an ordered step list for playback from a hand record (+ the graded decisions).

**Interface.** `compile_replay(hand_record: dict, decision_records: list[dict]|None=None) -> dict`;
`load_last_hand(session_path, decisions_path) -> (hand_record, decisions)`.

**Input/output.** In: the `build_hand_record` dict and the `trainer.decision.v1` records. Out:
`{hand_no, button, sb, bb, human_seat, positions, hero_hole, board, steps[], result, net, final_pot}`.
Blinds and the 3/1/1 board reveal are reconstructed (they are missing in the record because `session_log` filters out
the `blinds`/`deal` events). Pot math follows the Table semantics: `call` = chips added,
`bet`/`raise` = street commit-TO.

**Dependencies.** None — pure dict→dict, no FastAPI, no engine import.

**Status.** Stateless.

**Cost.** Not measured.

**Measurement status.** MEASURED POSITIVE (function): self-test green. During integration two REAL defects were
found and fixed here: the coach matching compared `hand_no` against the `<session>-<hand_no>` `hand_id` (result:
0 coach texts in the replay) and the verdict sat nested under `oracle` (`docs/STATE.md:491-493`).

**Usable standalone?** Yes, the cleanest module to adopt from this directory.

**Pitfalls.** The bot cards: `hole{}` contains ALL hands. The compiler shows other players' cards only via
`result["shown"]` when `result["reveal"]` is true — whoever renders the record directly accidentally reveals everything
to the trainee and makes the feedback results-oriented.

---

### Opponent panel — `pokerbot/coach/opponent_panel.py`
**Purpose.** Translates the reads the league bots have learned about the human into German sentences
("Seat 3 has noticed: you often fold to river bets").

**Interface.** `was_bot_gelernt(bots: dict) -> list[{seat, name, beobachtung_de}]` — max. 4 entries
(`MAX_OBSERVATIONS`), padded to at least 2 with honest blanks ("not enough data yet").

**Input/output.** In: `{seat: SixMaxBot}` from the session. Out: the list above, `beobachtung_de` already with
glossary markup.

**Dependencies.** Soft, but in substance hard-coupled to `arena/sixmax`: the trigger thresholds are imported from
`READ_THREEBET_HAPPY/READ_OVERFOLD/READ_STATION/READ_AGGRO_HI/READ_AGGRO_LO`, with mirrored literals
as fallback plus a drift guard in the self-test.

**Status.** Stateless; the state lives in the bots' opponent models.

**Cost.** Not measured.

**Measurement status.** MEASURED POSITIVE (function): self-test with a synthetic OppModel. The EV benefit of the
underlying reads, by contrast, is REFUTED (exploit gate: all 8 diffs ≤ 0, pooled ≈ −12 bb/100,
`docs/STATE.md:53-55`) — the panel remains useful as a TEACHING AID, although the exploit itself is switched off.

**Usable standalone?** Only with the league (`arena/sixmax`) — the thresholds are exactly its thresholds.

**Pitfalls.** The thresholds MUST stay mirrored. If the panel shows reads the bots do not actually
react to, the human learns something wrong — hence the import instead of own constants.

---

### Session report — `pokerbot/coach/trainer_report.py`
**Purpose.** Summarises a training session from the two JSONL files into a German retrospective.

**Interface.** `report(session_path, decisions_path) -> dict`; `format_report_text(rep) -> str`.

**Input/output.** Out: `{n_hands, n_decisions, grade_dist{ok,teuer,leak}, error_rate, leak_top[],
stats{...}, best_moment, teuerstes_moment, narrative_de}`. `leak_top` = the three most frequent `grade_typ` buckets.
All accesses key-tolerant via `.get()`.

**Dependencies.** None except stdlib (reads only JSONL).

**Status.** Stateless.

**Cost.** Not measured.

**Measurement status.** MEASURED POSITIVE (function): self-test with synthetic hands/decisions; part of the
11/11 gate.

**Usable standalone?** Yes.

**Pitfalls.** The report explicitly grades NO results — whoever adds a bb/100 line tips over the
fairness doctrine and creates exactly the results orientation the whole chain is built against.

---

### Range narrative — `pokerbot/coach/range_story.py`
**Purpose.** Generates the strategy section of the hand feedback from a GENUINELY computed range reconstruction
("Preflop the opponent represents top 5 % … you represent a flush draw").

**Interface.** `build_story(records, hand_result=None) -> list[str]` (on any hard problem `[]`, then
`templates_de` falls back to the old heuristic); `class StoryTracker(RangeTracker)`;
`make_seeded_tracker(villain_pos: str|None, villain_raised: bool|None) -> type` — a tracker class with
a 6-max position prior instead of the HU prior.

**Input/output.** In: the decision records of a hand + `table.result`. Out: list of German sentences.
Priors as constants: `RAISER_FRAC {1:0.20, 2:0.09, 3:0.04}`, `CALLER_FRAC {0:0.55, 1:0.28, 2:0.12, 3:0.06}`,
`OPEN_FRAC` per position (UTG 0.15 … BTN 0.42).

**Dependencies.** Hard: `strategy.range_tracker.RangeTracker`, `engine.equity.equity_vs_weighted_range`,
`coach.oracle.record_to_hu_state`, the evaluator's `made_class` taxonomy.

**Status.** One tracker per hand; MC equity deterministically seeded from `spot_fp` + street.

**Cost.** `EQ_ITERS = 200` for flop/turn (~3.5 pp SE, per the comment "enough for a narrative"), river
enumerated exactly. Absolute latency not measured; it runs within the 800 ms hand-end budget (which is why
`grader.prewarm` explicitly pre-warms the turn/river nets as well).

**Measurement status.** UNMEASURED as a learning effect. The 6-max position prior is documented as wiring:
`make_seeded_tracker` yields UTG 194 to BTN 552 combos instead of the HU 1102 (`docs/STATE.md:425-426`). Self-test
green.

**Usable standalone?** Only with tracker + equity engine. `make_seeded_tracker` is the reused part — the
Snowie bridge and the 6-max takeover use exactly this factory.

**Pitfalls.** The live bot's tracker priors are HU-calibrated (SB open 84 % of all hands). Whoever outputs them
unchanged as 6-max teaching text tells the human nonsense — which is exactly why `StoryTracker`
overrides ONLY the preflop priors and leaves the postflop updates untouched.

---

### Autotest harness — `pokerbot/coach/autotest.py`
**Purpose.** Lets league bots play the human seat through the COMPLETE trainer stack and checks whether logger →
grader → renderer → report survive N hands without a crash, within the latency budget and with a plausible grade distribution.

**Interface.** `run_all(hands) -> dict`, `run_arm(client, six_server, profile, mode, hands, seed, ...)`,
`normalize_action(dec, legal) -> (action, amount)`; CLI
`python -m pokerbot.coach.autotest [hands] [--hands N] [--deep] [--json PATH] [--selftest]`.
Eight checks: `_zero_crash`, `_decisions_schema`, `_grade_latency`, `_grade_distribution_sanity`,
`_feedback_nonempty`, `_report_builds`, `_mode_toggle`, `_replay_reconstructs`.

**Input/output.** In: nothing but parameters; drives `six_server` via `fastapi.testclient.TestClient`.
Out: a result dict + exit code (0 = PASS/WARN, 1 = FAIL). Gates: `MEDIAN_GRADE_MS_BUDGET = 250`,
`DEEP_HANDS = 300`, vocabulary `{ok, teuer, leak}`.

**Dependencies.** `six_server`, the entire coach chain, `arena/sixmax`, `fastapi.testclient`.

**Status.** One persistent injected RNG per arm (deliberately NO per-spot reseed — that would be fake mixing).

**Cost.** Not documented as wall time; the deep run is 300 hands per arm.

**Measurement status.** MEASURED POSITIVE: "autotest 8/8 PASS over 800 hands / 1411 decisions" (`docs/STATE.md:496`).
Important limitation, measured: at ~120 graded decisions per profile the station and tag error rates
are in the noise (.057 vs .059) — clean separation only from 300+ (`docs/STATE.md:494-496`); small runs therefore WARN.

**Usable standalone?** Only with the server. Transferable is the pattern: a deliberate fault probe (patch the grader
so that records are written without `grade`) proves that the harness detects anything at all.

**Pitfalls.** The driver MUST normalise `bet` to `raise` and clamp amounts into `[raise_min, raise_max]`,
otherwise the server responds with 400 and `zero_crash` fails spuriously.

---

### GTOW export of the trainer hands — `pokerbot/coach/export_gtow.py`
**Purpose.** Writes a trainer session as a PokerStars 6-max hand history so that the GTO Wizard Analyzer can
independently cross-check the trainer's own grades.

**Interface.** `export_session(session_path, out_path=None, ledger_path=None) -> {n_hands, idbase, out,
warnungen}`; `record_to_export(rec) -> dict`; `class ExportError(ValueError)`; CLI `main()`.

**Input/output.** In: `session_<sid>.jsonl`. Out: a `.txt` with CRLF line endings (the Analyzer parses only
CRLF) and a ledger entry `{idbase, n_hands, file, session, ts}`. Missing `deal` events on all-in run-outs
are injected synthetically, because the 6-max exporter generates street headers ONLY from `deal` events.

**Dependencies.** Hard: `research.sixmax_export.format_hand`, `pokerbot.web.session_log.append_record`.

**Status.** A persistent ledger; `_fresh_idbase` allocates a fresh block.

**Cost.** Not measured.

**Measurement status.** UNMEASURED as an export result (no Analyzer grade of a trainer session documented in the repo). The
module has a self-test. The bot's own 6-max Analyzer anchor is 85.9 % GTO score / 7.61 EV loss
(`docs/STATE.md:52-53`), but comes from `research/sixmax_export.py`, not from this module.

**Usable standalone?** Yes, with `research/sixmax_export`.

**Pitfalls.** Hand IDs BURN on first contact — even on a failed upload. The ledger is therefore
advanced BEFORE the file is written. Whoever reuses an `idbase` ruins the
Analyzer history. And: the human's RAW sizes are exported (no snapping), which produces off-tree warnings
— deliberately so, because snapping would shift the pot accounting of all subsequent streets.

---

## Coach (LLM branch)

### Claude coach — `pokerbot/coach/coach.py`
**Purpose.** On-demand coaching via the Claude API: explains the bot's move, evaluates the user's own move against the
bot reference, answers free questions.

**Interface.** `class Coach(model=None, language="de")` with `.available -> bool`,
`.explain_move(state, hero_idx, decision) -> str`, `.review_user_move(state, hero_idx, user_action, user_amount,
bot_decision) -> str`, `.ask(question, state=None, hero_idx=0) -> str`; module function
`describe_hand(state, hero_idx) -> str`.

**Input/output.** In: the `game.state()` dict + the bot decision incl. `rationale`. Out: German
prose. Without an API key an honest notice text comes back instead of an exception; API errors are returned as
`(Coach-Fehler: ...)`.

**Dependencies.** Hard: `anthropic` (import at module level — which is why the import is encapsulated in
`coach/__init__.py`, so that the trainer modules stay importable without the package), `pokerbot.config` (key + model),
`knowledge_base/concepts` (injected into the cached system prompt, max. 180 concepts / 14,000 characters).

**Status.** The knowledge string is loaded once per instance; the system prompt uses
`cache_control: ephemeral`.

**Cost.** Not measured. It is the only paid path in this subsystem, and it runs only on an
explicit click, not per action.

**Measurement status.** UNMEASURED (text quality, no EV effect). Smoke test: `tests/test_coach.py`.

**Usable standalone?** Yes, with a key. `describe_hand` alone is a usable state serialiser.

**Pitfalls.** The coach sees `state(hide=BOT)` — the bot cards are `??` in it. Whoever accidentally gives it the
full state gets explanations based on hidden cards, and the trainee learns
results orientation.

---

### CoinPoker parser — `pokerbot/coach/coinpoker.py`
**Purpose.** Reads CoinPoker hand histories and turns every hero decision into a canonical `Spot`.

**Interface.** `parse_file(path) -> list[Hand]`, `hero_decisions(hand) -> list[Decision]`
(each `Spot` + the action actually played), `summary(hand) -> dict`; dataclasses `Hand`, `Decision`.

**Input/output.** In: `.txt` in CoinPoker format (chips in ₮ ≈ $; "raises X to Y" with Y = total, "bets X",
"NAME: ALLIN X" with X = increment, "collected ₮X from pot" WITHOUT colon). Out: `Spot` objects from
`pokerbot/brain/format_spot.py`.

**Dependencies.** Hard: `pokerbot.brain.format_spot`.

**Status.** Stateless.

**Cost.** Not measured.

**Measurement status.** UNMEASURED.

**Usable standalone?** Yes, if you adopt the `Spot` format. Otherwise it is a site-specific parser.

**Pitfalls.** The amount semantics change per verb (total for `raises to`, increment for `ALLIN`). Whoever
mixes them up builds pot accounting that only shows up two streets later.

---

### Station simulation — `pokerbot/coach/station_sim.py`
**Purpose.** `station_sim` is an explicit Monte-Carlo study against a modelled calling station (real cards, real
showdowns, paired A/B on identical deals).

**Interface.** `station_sim.compare(scenario, size, barrels, mega, n, seed) -> dict` and
`station_sim.run(n=6000) -> dict`.

**Input/output.** Pure parameters in, metric dicts or a PDF out.

**Dependencies.** Engine evaluator (station_sim), `reportlab` (PDF).

**Status.** Stateless per run, seeded.

**Cost.** `station_sim` not measured.

**Measurement status.** UNMEASURED in the sense of bot EV. It produces numbers about a MODELLED opponent, not a
measured one. `station_sim` says so in its own docstring: the league was the wrong instrument, hence the explicit
opponent construction.

**Usable standalone?** `station_sim` yes (the engine evaluator suffices).

**Pitfalls.** The module measures against a SELF-BUILT opponent assumption. Results are hypotheses about the
assumption, never evidence about the real population.

---

### Meta coach — `pokerbot/coach/meta_coach.py`
**Purpose.** Steers the improvement loop between training checkpoints: JSON with metrics in,
prioritised directives as JSON out. It plays no hands.

**Interface.** `class MetaCoach` (provider `anthropic` or an OpenAI-compatible endpoint), `main()` as
a demo on real numbers.

**Input/output.** In: checkpoint dict (solver gaps, bb/100, current parameters). Out: structured JSON
with directives.

**Dependencies.** An LLM provider.

**Status.** Stateless.

**Cost.** Not measured (deliberately designed as "cheap enough per checkpoint").

**Measurement status.** UNMEASURED. Belongs to the LLM track, which is marked SECONDARY in the repo.

**Usable standalone?** Yes, it is a thin prompt wrapper.

**Pitfalls.** LLM directives are hypotheses, not findings. Without a paired gate behind it, every
adopted directive is unmeasured — the repo has paid dearly for that several times.

---

## Session analysis (`pokerbot/analysis/`)

### Session statistics — `pokerbot/analysis/session_analysis.py`
**Purpose.** Computes the classic human metrics from a session JSONL and lets Claude write a short
German comment on them.

**Interface.** `compute_stats(recs: list[dict]) -> dict`, `narrative(stats) -> str`,
`analyze_session(path) -> {"stats": ..., "narrative": ...}` (this is the response of `POST /api/analyze`).

**Input/output.** In: `build_hand_record` lines. Out: `{hands, vpip_pct, pfr_pct, threebet_pct,
postflop_aggression_factor, postflop{bets,raises,calls,folds}, went_to_showdown_pct, net_bb, bb_per_100,
avg_postflop_bet_bb}`.

**Dependencies.** `pokerbot.config` + `anthropic` (only for `narrative`; without a key an empty string comes back).

**Status.** Stateless.

**Cost.** Not measured (one pass over the lines).

**Measurement status.** UNMEASURED — descriptive statistics, not a lever.

**Usable standalone?** Yes, with the JSONL format.

**Pitfalls.** The seat keys are strings after the JSON round trip; the code handles both cases
(`net.get(hs, net.get(int(hs) ...))`). And `_folded` only checks WHETHER the human folded at some point — as a
showdown filter that is coarse.

### Further analysis scripts — `pokerbot/analysis/{session_deep, harvest_play, luck_vs_skill, pluribus_catalog}.py`
**Purpose.** `session_deep` narrates across several of the user's own sessions (meta patterns, tilt over time, via Claude);
`harvest_play` verifies reads from recently played sessions and measures the bots' preflop tendencies;
`luck_vs_skill` splits the net into a non-showdown share (fold equity) and a showdown share and estimates the
luck share via exact flop equity against the actual opponent hands; `pluribus_catalog` parses the 10,000
Pluribus hands of the PHH dataset into `knowledge_base/hand_histories/pluribus_hands.jsonl` and aggregates their
stats per position.

**Interface.** All as `python -m pokerbot.analysis.<modul> [n_sessions]`; reusable functions:
`luck_vs_skill.flop_equity(hole, opp_holes, flop)`, `pluribus_catalog.parse_hand(path)` and
`classify_preflop(rec, seat)`, `session_deep.user_sessions()`.

**Input/output.** Session JSONL or PHH TOML in; console text or a JSONL out.

**Dependencies.** `analysis.session_analysis`, engine equity, `tomllib`, optionally `anthropic`.

**Status.** Stateless.

**Cost.** Not measured.

**Measurement status.** UNMEASURED. `luck_vs_skill` names its own approximation: one session is a small
sample, and flop equity as the sole proxy for "got it in good" is coarse.

**Usable standalone?** `pluribus_catalog` yes (only the dataset needed); the others need our session format.

**Pitfalls.** These are one-off analysis scripts, not maintained libraries — they expect the exact
log format and break on schema changes.

---

## Vision (`pokerbot/vision/`)

### Snowie image recognition — `pokerbot/vision/snowie_local.py`
**Purpose.** Reads cards from the PokerSnowie 4 window purely locally via template matching — no VLM, no cost.

**Interface.** `window_bbox()`, `grab() -> Image`, `crop_frac(img, box)`, `match(glyph, kind) -> (label|None,
score)`, `read_card(img, key, learn=False)`, `read_cards(img=None, learn=False) -> dict`, `slot_occupied(img, key)
-> bool`, `suit_by_colour(glyph) -> list[str]`, `dump(img=None) -> str`; CLI `--dump`, `--read`, `--learn`.

**Input/output.** In: a screenshot (PIL). Out: `{"hero": [card|None, card|None], "board": [...],
"unreadable": int}`. Cards are the repo's 2-character codes (`'As'`, `'Td'`). Templates live as PNG under
`data/vision/snowie/tpl/<art>/<label>.png`.

**Dependencies.** `numpy`, `PIL`, `ctypes` (Windows DPI + window search via
`vision.screen_reader.pick_window`). Windows-bound.

**Status.** Template cache; otherwise stateless.

**Cost.** Not documented as milliseconds in the module. The complete read is ~0.1 s instead of ~4 s VLM
(`snowie_bridge.py:187`).

**Measurement status.** MEASURED POSITIVE in combination (see bridge). Isolated: the thresholds are measured live
(`MATCH_MIN = 0.72`, `MATCH_MARGIN = 0.05` — the best label must clearly beat the second-best FOREIGN label).
Regression net `research/snowie_regress.py` (preserved crime scenes of both themes).

**Usable standalone?** Yes, but only for PokerSnowie 4 on Windows: the regions are hard-measured as fractions of the
window.

**Pitfalls.** Uncertain means None, not "best hit". Whoever softens the margin rule to have fewer pauses
silently gets wrong cards — the most expensive error class, because nothing crashes.

---

### Snowie table state + gate — `pokerbot/vision/snowie_state.py`
**Purpose.** Reads the COMPLETE table state (seats, positions, stacks, bets, pot, buttons) and decides
via a gate whether the read is good enough to play on.

**Interface.**
- `read_state(img=None, learn=False) -> dict` — the one main function.
- `gate(s, strict_bets=True) -> str|None` — None = usable, otherwise the reason to PAUSE.
- `duplicate_cards(s) -> str|None`, `implausible(s) -> str|None` — the two plausibility guards.
- Building blocks: `dealer_seat(img)`, `seat_live(img, seat)`, `hero_turn(img)`, `position_of(dealer)`,
  `read_bets`, `read_buttons`, `read_number`, `read_numbers_batched`, `match_digit`.

**Input/output.** Out: `{hero_turn, hero_cards, board, cards_unreadable, dealer, positions, hero_position,
live{seat:bool}, bets{seat:float}, stacks{seat:float|None}, pot, hero_bet, max_bet, buttons, can_check,
call_amount, raise_min_dollars, players_in_hand, unknown_bet}`. Amounts are DOLLARS, not chips.

**Dependencies.** `vision.snowie_local`, `numpy`, `PIL`; optionally Tesseract
(`C:\Program Files\Tesseract-OCR\tesseract.exe`) as a second number source.

**Status.** Stateless per read. The history state (fix position per hand, pot may never shrink)
deliberately lives in `snowie_bridge.HandTracker`.

**Cost.** Documented in the code: the batch OCR for pot + all stacks costs 131 ms instead of 557 ms with templates
(`snowie_state.py:673-674`); the single-OCR arbiter in the conflict case ~340 ms
(`snowie_state.py:696-698`).

**Measurement status.** MEASURED POSITIVE in combination (see bridge). Every threshold in the module has a named crime scene:
pot with mandatory second source, because the batch OCR read '39' as '539' (the currency symbol became a digit); the
plausibility limit, because a stack was read as 14104 instead of ~180 and the bot raised 206 dollars into a
9-dollar pot; duplicate check, because a board was read live as `6s Ks 2h Jd 6s`.

**Usable standalone?** Only for PokerSnowie 4 on Windows. Transferable is the GATE PATTERN, not the geometry.

**Pitfalls.** The order in the gate carries meaning: the relaxation `strict_bets=False` MUST take effect before the
bet-level check, otherwise the escalation refuses itself with exactly the blocker it is meant to bypass
(`snowie_state.py:794-798`). Whoever reorders the checks rebuilds this trap.

---

### Snowie bridge — `pokerbot/vision/snowie_bridge.py`
**Purpose.** The game loop: read window → gate → `obs` for our bot → decision → ctypes click, with
history guards and JSONL log.

**Interface.**
- `run(n_hands, strict, bb_dollars, probe) -> None`; CLI
  `python -m pokerbot.vision.snowie_bridge --probe | --hands 50 [--bb 2.0] [--loose]`.
- `read_local(img=None) -> dict` (delegates to `snowie_state.read_state`).
- `to_obs_local(s, bb_dollars=2.0, committed=0.0) -> dict` — dollar state → engine `obs`.
- `class HandTracker` — position and pot monotonicity over a hand.
- `class StreetTracker` — hero's street bet from the STACK DIFFERENCE instead of from the tiny bet font;
  `cur_bet = my bet + to_call` is thereby an identity.
- `class ActionLog` — reconstructs opponent actions from the deltas between still frames.
- `class PrinceHU` — builds a `trainer.decision.v1` record from the vision read and lets `PrinceOracle`
  decide.
- `make_hero()` — the multiway core (`arena/sixmax` profile `tag`, reads OFF).
- `act(bbox, obs, decision, bb_dollars) -> str` — decision into clicks.
- `esc_pressed()` — ESC terminates everything.

**Input/output.** `to_obs_local` provides the load-bearing keys `hole, board, to_call, pot, my_stack, bb(=100),
n_active, position, preflop_raises, cur_bet, my_committed_street, street, can_check, can_call, can_raise,
raise_min, raise_max` — all in chips (bb = 100). Every decision goes to
`data/vision/snowie_session_<timestamp>.jsonl`.

**Dependencies.** Hard: `vision.snowie_state`, `vision.snowie_local`, `arena.sixmax`, `coach.oracle.
PrinceOracle`, `coach.range_story.make_seeded_tracker`, `ctypes` (clicks), `PIL`. Windows-bound.

**Status.** Per hand: `HandTracker` (fix position once, pot may never shrink), `StreetTracker`,
`ActionLog`. Per run: log file, stale counters (`MAX_STALE = 400`, `BLOCK_GIVEUP = 12`).

**Cost.** MEASURED: 13.3 hands/min, ~4 % dropouts, both themes (`docs/STATE.md:421-423`); one local read
~0.1 s instead of ~4 s VLM, 0 instead of ~4 ct per move (`snowie_bridge.py:187`).

**Measurement status.** MEASURED — and the number needs its context: three marathon runs, 3,651 hands raw, account
−$2,915; the CLEANED pool (3,114 clean hands) yielded **+3.2 bb/100, 95 % band [−37, +44]**
(`docs/STATE.md:426-427`) — i.e. ≈ break-even against Snowie, while the automation tax ate the account.
Every loss class was individually autopsied and sealed: L1 = 46 % dropouts (833 forced folds), L2 =
over-stack raise loop, L3 = 13 phantom pot jams through decimal-point loss ×100 (answer: the
chip-conservation invariant). Full AIVAT is NOT possible here (no showdown logging) — the ladder towards it is
defined in STATE.md.

**Usable standalone?** No: it is built on PokerSnowie 4 under Windows and needs `snowie_state` +
`snowie_local` + a bot. Transferable is the ARCHITECTURE (gate → history guards → click verification →
regression net).

**Pitfalls.** Prince takes over HU pots ONLY POSTFLOP. The reason is measured and important: an MP open is a
15–20 % range; the HU projection would read ~50 % from it (`docs/STATE.md:423-425`). Whoever switches the takeover
on preflop as well "for simplicity" plays against an invented opponent range. The second pitfall is `raise_min`:
Snowie's raise button carries the SLIDER SUGGESTION, not the minimum, and its '$' was once read as '3' —
which is why the minimum is COMPUTED (`2 × bet level`), never read off.

---

### Universal screen reader — `pokerbot/vision/screen_reader.py`
**Purpose.** Reads ANY poker table via VLM (OpenAI) into a strict JSON schema — without site-specific
templates.

**Interface.** `list_windows() -> list[dict]`, `pick_window(pattern) -> dict|None`, `capture(bbox=None) ->
Image`, `dhash(img) -> int`, `hamming(a, b) -> int`, `read_table(img, model=None) -> (dict, (w, h))`,
`pretty(t) -> str`; CLI `--list | --once [--window "Coin"] | --watch [--interval 2.0]`.

**Input/output.** In: a window screenshot. Out: `TABLE_SCHEMA` JSON (seats, stacks, board, pot, buttons;
cards as 2-character codes). Watch mode writes to `data/vision/table_states.jsonl`.

**Dependencies.** `research.llm.openai_json` (paid), `PIL`, `ctypes`. Windows for the window search.

**Status.** The last dHash for change detection.

**Cost.** Cost dampers in the code: downscale to `MAX_W = 1280` and a 64-bit dHash with `HASH_DIST_MIN = 6` —
unchanged frames trigger no API call. Absolute cost/latency not measured; the bridge cites as a comparison
value ~4 s and ~4 ct per VLM move (`snowie_bridge.py:187`).

**Measurement status.** UNMEASURED as a play path. It has been SUPERSEDED in Snowie operation: "LOCAL read (standard
since 2026-08-04)" (`snowie_bridge.py:187`) — only `pick_window` is still used from it.

**Usable standalone?** Yes, with an OpenAI key. It is the generic route if you do not want to build templates.

**Pitfalls.** Exactly the two errors that `snowie_state.py` documents in its header docstring: the VLM reported
a logically impossible button state (fold yes, check no, call no → 17 free checks thrown away as folds)
and a seat order that did not start at the dealer button (position wrong in 26 of 57 cases).
Structural questions (what is legal, who sits where) do not belong to a language model — they follow deterministically
from bets and layout. Moreover, per project rule the frontier API runs only on the PC, never on a pod.

---

## LLM brain track (historical)

This subsystem lets a language model play poker by NOT naming the action but writing a small
Python program over a typed engine API ("program of thought"); a sandbox executes it, the
engine enforces legality, the model supplies only judgment. The branch is SECONDARY in the project and largely
frozen: the best LLM numbers (Claude over the engine −28.55 to −41 AIVAT bb/100; own 9B model
−43.30, after retraining −90.18) lie below the pure engine path, and the RL lift was refuted by measurement.
Whoever only wants to build a bot needs almost none of it — with one exception: `api.py`, `format_spot.py`,
`executor.py` and `grammar.py` are a clean, reusable pattern for "the LLM may have things computed, but
invent nothing", and `training/rl_env.py` is a usable rollout/EV measurement environment independent of the LLM.

---

# Part A — `pokerbot/brain/` (the brain-engine seam)

### Engine API (DSL vocabulary) — `pokerbot/brain/api.py`
**Purpose.** Thin, typed shell over equity, poker math, board texture, blueprint, advisor, live solver and
legality — exactly the functions an LLM program may call.
**Interface.**
- `equity(hero, villain, board=None, iters=None, seed=0) -> float` — Monte-Carlo equity; `villain` may be a class list
  (`['AA','AKs']`), combo list (`[('As','Ks')]`) or weighted dict; `iters=None` takes the active
  compute-mode budget (`brain/modes.py`).
- `range_top(frac) -> list[str]` — top `frac` of the 169 starting classes as a compact range prior.
- `required_equity(to_call, pot)`, `pot_odds(to_call, pot)`, `mdf(bet, pot)`, `spr(eff, pot)`,
  `outs_equity(outs, cards_to_come=2)` — pot odds/MDF/SPR/outs from `knowledge_base/math/formulas.py`.
- `board_texture(board) -> dict` (paired/monotone/twotone/connected/high/dynamic), `hand_rank(hole, board) ->
  (name, strength)` (strength = 1 − treys/7462), `hand_class_of(hole) -> str`.
- `preflop_mix(spot) -> dict|None`, `preflop_solve(spot) -> dict|None` — blueprint mix, or the same mix as
  ready-to-play DSL verbs incl. `_sizes_bb`; both only HU 200bb, 6-max returns `None` (`api.py:130`).
- `solver_freq(hole, board, role, street) -> float|None` — P(bet) of the trained advisor MLPs.
- `solve_node(spot) -> dict|None` — search at runtime: starts TexasSolver on the real board, navigates
  the line of the current street and returns `{fold|check|call|bet|raise|allin: prob, '_sizes_bb': {...}}` for the
  concrete hand; `None` preflop, at `n_active>2`, on an unnavigable line, timeout or any exception.
- `legalize(spot, action, size_bb=None) -> (action, amount_chips)` — enforces a legal action, falls back safely to
  check>call>fold.
In addition, `knowledge_base/math/postflop_formulas.py` and (if present) `strategy_formulas.py` are pulled via
wildcard into the module namespace, so they are callable as `api.<fn>` (`api.py:21-26`).
**Input/output.** Cards are 2-character strings (`'As'`). `spot` is always a `format_spot.Spot` (chips raw,
`spot.bb` = big blind in chips); the solver computes in big blinds, `legalize` returns chips. Load-bearing
return keys: action verbs plus the private hint `_sizes_bb` (total bet in bb per verb) — it is
NOT a frequency and must never be normalised along.
**Dependencies.** Hard: `pokerbot/engine/{equity,evaluator,cards}`, `pokerbot/strategy/postflop.classify_board`,
`knowledge_base/math/formulas.py`. Soft/replaceable (all in try/except, `None` when missing):
`strategy/preflop_blueprint`, `strategy/preflop_strength`, `strategy/advisor`, `strategy/gto_oracle` (TexasSolver binary).
**Status.** Almost stateless; BUT a module-wide solve cache `_SOLVE_CACHE` plus `_SOLVE_INFLIGHT` (`api.py:188-198`)
lives across the whole process. Key = board + bucketed pot (4 bb) + bucketed stack (10 bb) + range hash.
For a clean measurement you must restart the process or clear the cache.
**Cost.** Import 0.07 s, `equity` with 1000 MC iterations ~17 ms (own smoke in this session, standard mode).
`solve_node` is expensive: a wide HU flop solve ~30 s at 8 threads, ~57 s at 4, ~79 s at 2 (measurement note
`api.py:181-185`, 2026-06-18); cap `SOLVE_TIMEOUT` default 150 s.
**Measurement status.** As a module UNMEASURED (no own bb/100 arm). Documented partial numbers: `solve_node` fired in a
live run on 61 % of decisions (`docs/STATE.md:1090`) or 453 times in n=500 (`docs/STATE.md:1173`); the
brain bet sizes lie only 15 % on GTOW's grid versus 100 % for the engine path (`docs/STATE.md:1090`).
The switch `POKERB_BRAIN_ONTREE` (snap to {0.33/0.5/0.75/1/1.25}×pot, `api.py:461-468`) is built and
unit-verified but EV-UNMEASURED; `POKERB_LINE_RANGES` (line-aware starting ranges, `api.py:332-338`) likewise
default OFF and unmeasured.
**Usable standalone?** Yes, this is the most reusable piece. Minimum needed: `pokerbot/engine/*`,
`knowledge_base/math/formulas.py` and a `Spot`-like object. Without the TexasSolver binary and without the
advisor models, `solve_node`/`solver_freq` simply return `None`.
**Pitfalls.** The combination "everything in try/except → `None`" and "cache also stores failures" makes
errors invisible: an expired solve timeout is CACHED as `None` (`api.py:293`), the bot silently falls back to
its fallback, and the measurement measures a degraded bot without anything turning red anywhere.

### Canonical spot + prompt rendering — `pokerbot/brain/format_spot.py`
**Purpose.** The one representation of a decision situation, byte-identical across SFT, RL, inference and eval.
**Interface.**
- `@dataclass Spot(street, board, bb, hero_seat, hero_pos, hero_hole, pot, to_call, n_active, seats, legal, line,
  villain_fold=0.5, villain_aggro=0.5)` with `Spot.b(chips) -> float` (chips → bb).
- `spot_from_table(table, seat) -> Spot` — builds the spot from a running `pokerbot/engine/table.py`.
- `format_spot(spot) -> str` — renders the prompt text (deterministic, everything in bb).
- `ACTION_RE` — shared parser for `ACTION: <fold|check|call|bet N|raise N|all-in>`.
**Input/output.** `seats` = list of `{seat,pos,stack,committed_total,folded,all_in}`; `legal` =
`{can_fold,can_check,can_call,can_raise,raise_min,raise_max}` in CHIPS; `line` = ordered
`{street,pos,action,amount_bb,hero}`. Output is plain text, ~8-12 lines.
**Dependencies.** Hard only `re`/`dataclasses`; `spot_from_table` depends hard on the Table API
(`legal_actions/position_label/obs` conventions). `api.hand_rank` and `understanding.strategic_read` are imported
LAZILY, only when the respective switches are on.
**Status.** Stateless per call. But three module switches are read ONCE at import from the environment:
`INCLUDE_MADE_HAND` (`POKERB_MADE_HAND`, default ON), `INCLUDE_SOLVER_FREQ` (`POKERB_SOLVER_FREQ`, default OFF),
`INCLUDE_UNDERSTANDING` (`POKERB_UNDERSTANDING`, default OFF). A later `os.environ[...]` has no effect any more.
**Cost.** < 1 ms per call without extra blocks (own smoke). With `INCLUDE_MADE_HAND` a
treys evaluation is added (negligible), with `INCLUDE_SOLVER_FREQ` an advisor forward pass.
**Measurement status.** `INCLUDE_MADE_HAND`: MEASURED POSITIVE — paired GTOW A/B n=500 per arm, OFF −84.11 → ON −43.46,
2.1σ, variance halved (`docs/STATE.md:1120`); before that locally paired 7 spots, 3 clear corrections, 3 controls
unchanged (`docs/STATE.md:1153`). `INCLUDE_SOLVER_FREQ`: MEASURED NEUTRAL — ON −49.21 ± 29.00 vs OFF
−49.52 ± 11.71, Δ ≈ 0 (`docs/STATE.md:1118`), hence default OFF. `INCLUDE_UNDERSTANDING`: UNMEASURED
(`docs/STATE.md:1078`).
**Usable standalone?** Yes. `Spot` + `format_spot` depend on nothing heavy; you can build spots by hand (that is how
`tests/test_made_hand_read.py` does it). Only `spot_from_table` needs the engine Table.
**Pitfalls.** The project's measured lesson stands as a hard rule at the head of the file (`format_spot.py:31-32`):
serve hints (like the made-hand block) must NOT be baked into the training data — exactly that made the
model worse from −28 to −90. Whoever trains and serves must therefore know which blocks were on.

### Program sandbox — `pokerbot/brain/executor.py`
**Purpose.** Executes the decision program emitted by the model in a restricted way and returns a legal action.
**Interface.** `run_program(program, spot, timeout_s=None, strict=True, seed=0) -> dict`. In the program namespace
are exactly `api`, `spot`, `decide(action, size_bb=None)`, `decide_mix(mix, size=None)` and a whitelist of
21 builtins (`executor.py:21-24`) — no `__import__`, `open`, `exec`, `eval`, `compile`.
**Input/output.** In: program text + `Spot`. Out: `{action, amount, ok, error, intended, mix}` — `action`
legalised, `amount` = total bet in CHIPS or `None`; `ok=False` on grammar violation, exception, missing
`decide` or illegally intended action (exactly that is the hard negative for RL); `mix` = normalised
frequencies if `decide_mix` was used.
**Dependencies.** Hard: `brain/api.py` (legalisation) and `brain/grammar.py` (AST gate, only with `strict=True`).
**Status.** Stateless. The mix draw is deterministic via `seed` (common random numbers).
**Cost.** ~17 ms for a program with one `api.equity` call at 1000 iterations (own smoke); without
equity in the microsecond range. The wall-clock cap applies only under POSIX and only in the main thread.
**Measurement status.** MEASURED POSITIVE as a bug fix: `_alarm_available()` additionally requires `threading.main_thread()`,
because SIGALRM in worker threads raises an exception and thereby counted EVERY decision as "bad" — that pushed
`frac_bad` from 1.0 to 0.009 without anything changing in the model (`docs/STATE.md:1159`).
**Usable standalone?** Yes, with `api.py` + `grammar.py`. For your own vocabulary it suffices to swap the namespace in
`run_program` (`executor.py:56`) and the owner list in `grammar.py:36`.
**Pitfalls.** The sandbox is a whitelist, NOT a security boundary against a malicious author: infinite
loops are capped only under POSIX/main thread, and memory hogging is not capped at all. For
third-party/unchecked model outputs in a server process you additionally need process isolation.

### AST gate (semantic) — `pokerbot/brain/grammar.py`
**Purpose.** Structural rejection: only programs whose entire AST lies in a whitelist may run.
**Interface.** `validate_program(program) -> (ok: bool, reason: str)`.
**Input/output.** Text in, truth value + plain-text reason out (`"disallowed construct: FunctionDef"`,
`"attribute access only on api/spot"`, `"no decide() — a decision program must commit an action"`).
**Dependencies.** Only `ast`. Fully self-contained.
**Status.** Stateless.
**Cost.** One `ast.parse` + one `ast.walk` — not measurably relevant.
**Measurement status.** UNMEASURED as an EV lever; the repo has no separate acceptance number for this AST gate (the
quoted 7/7 · 8/8 · 40/40 belong to the regex variant `dsl_grammar.py`, `docs/STATE.md:1396`). It takes effect
via `executor.run_program(strict=True)`, whose rejections become visible as `ok=False` in `frac_bad`.
**Usable standalone?** Yes, without any dependency. Adapting means changing `_ALLOWED_NODES`, `_OWNERS`, `_SAFE_CALLS`.
**Pitfalls.** Attribute access is allowed ONLY on `api`/`spot` (`grammar.py:59-60`) — so even
`m.get('bet')` or `sorted(x)[0].foo` fails. A model that writes idiomatic Python is permanently rejected;
you have to trim the system prompt very tightly to this form (see `policy.SYSTEM_PROMPT`, section FORM RULES).

### Constrained-decoding grammar (generative) — `pokerbot/brain/dsl_grammar.py`
**Purpose.** The same language as a REGEX, so that invalid tokens cannot even be sampled during decoding.
**Interface.** `matches(program) -> bool`; `vllm_regex(think_cap_chars=None) -> str` (for
`GRPOConfig(vllm_structured_outputs_regex=...)`); `regex_logits_processor(tokenizer)` (local, via `outlines`,
returns `None` if `outlines` is missing).
**Input/output.** Text in, bool or regex string out. The form is: any number of comment/assignment
lines, then exactly one `decide(...)`/`decide_mix({...})` or an `if/elif/else` whose branches each commit
exactly once (`dsl_grammar.py:37-56`).
**Dependencies.** `re` (hard); `outlines`+`transformers` only for the logits processor (soft).
**Status.** Stateless.
**Cost.** Not measured (regex match on a few hundred characters).
**Measurement status.** UNMEASURED as an EV lever; accepted as a gate: 7/7 valid DSL forms accepted, 8/8 foreign
constructs rejected, 40/40 real completions (`docs/STATE.md:1396`). Also documented is the purpose of the `think_cap_chars` arm: without a hard cap
on the thinking block the model filled the token budget with `<think>` chatter before a `decide` came → `frac_bad` 0.93
(`dsl_grammar.py:64-73`, `docs/STATE.md` same finding for `policy.QwenPolicy`).
**Usable standalone?** Yes for `matches`; the vLLM path needs TRL/vLLM, the local path `outlines`.
**Pitfalls.** The regex is a STRICT subset of what `grammar.py` accepts. Whoever uses both must
change them together, otherwise constrained decoding produces programs that the AST gate later rejects
(or, conversely, you train on a form that is not decodable live).

### Qwen policy bridge + system prompt — `pokerbot/brain/policy.py`
**Purpose.** Connects a loaded (model, tokenizer) pair into `policy(table, seat) -> (action, amount_chips)` and
holds the ONE system prompt that SFT, RL, inference and eval use in common.
**Interface.**
- `SYSTEM_PROMPT` (str, ~50 lines) — describes the API vocabulary, the form rules and three example programs.
- `build_messages(spot) -> [{'role':'system'...},{'role':'user'...}]`.
- `extract_program(text) -> str` — peels the program out of raw text (removes `<think>` blocks, also dangling,
  and Markdown fences).
- `parse_completion(text, spot, timeout_s=None) -> dict` — raw text → `run_program(strict=True)` → result dict
  plus `program`; on a rejected program an `ACTION:` line is legalised as a last resort, but `ok` stays `False`.
- `@dataclass QwenPolicy(model, tok, sampling=False, constrained=True, max_new_tokens=None, temperature=1.0,
  top_p=1.0)` with `decide_verbose(table, seat)` and `__call__(table, seat)`.
**Input/output.** In: Table+seat or Spot. Out: `(action, amount_chips)` or the full parse dict.
**Dependencies.** `brain/{api,dsl_grammar,modes,executor,format_spot}` hard. `torch`/`transformers` only in
`QwenPolicy._generate` — `build_messages`/`parse_completion` are deliberately model-free and thus $0-testable.
**Status.** `QwenPolicy` holds the model and a logits processor; otherwise stateless per decision.
**Cost.** Not measured for the local transformers path in this file; the project note on local
operation: ~5–30 s per decision without vLLM (memory [[playable-product-launchers]]), via vLLM on the pod
1.27 s/hand after the cold start (`docs/STATE.md:1159`).
**Measurement status.** The prompt itself is the training/inference seam and MEASURED critical: a missing or
deviating system prompt in SFT led to `frac_bad=1.0`, and `enable_thinking=False` (`policy.py:133`) was the
fix for `frac_bad=0.93` (comments `policy.py:132-135`, `training/qwen_sft.py:22-25`). The overall result of the
Qwen/GLM track is REFUTED (see `training/qwen_grpo.py`).
**Usable standalone?** `build_messages`/`extract_program`/`parse_completion` yes, without GPU. `QwenPolicy` needs a
loaded HF model.
**Pitfalls.** `extract_program` cuts at `</think>` — if the thinking block runs into the token limit and never
closes, an EMPTY program text remains, which is counted as a hard negative. That looks like a dumb
model but is a budget problem.

### Claude as brain — `pokerbot/brain/claude_brain.py`
**Purpose.** A frontier model (Claude Opus) writes the decision program; everything after that is identical to the
Qwen path.
**Interface.** `@dataclass ClaudeBrain(model=None, thinking=True, strict=True, max_tokens=6000)` with
`decide_spot(spot) -> dict` (form like `parse_completion`, additionally `program`) and `report() -> dict`
(`decisions, valid, frac_bad, called_solve_node, errors, in_tok, out_tok, cache_tok`).
**Input/output.** In: `Spot`. Out: legal action + metadata. On an API error a safe `check` is
legalised and `ok=False` set — the hand never aborts.
**Dependencies.** `research/llm.ask_claude` (imported lazily), `brain/{api,modes,executor,format_spot,
policy}`. Keys come from `pokerbot/config.py`.
**Status.** Counters per instance (thread-safe via `self._lock`); the HTTP calls themselves are stateless, so
many hands in parallel are possible.
**Cost.** MEASURED: ~$8.32 for 500 hands (`docs/STATE.md:1173`), $4.14 for 200 hands
(`docs/STATE.md:1090`) — so roughly 1.7–2 cents per hand plus the latency of one reasoning call per decision.
**Measurement status.** MEASURED, but below the engine path: −28.55 ± 7.25 AIVAT bb/100 (n=500, `frac_bad` 0.011,
`solve_node` 453×, `docs/STATE.md:1173`); re-measurement −41.0 ± 14.06 (n=200, `docs/STATE.md:1090`) → honest
framing ~−35 to −45 with a fat margin. Two named leaks: deep-jam spew (program degenerated to "always
call", ~−7 bb/100 from ~2 % of hands, `claude_brain.py:32-34`) and reflexive ~0.60×pot river bets against
solver-measured ~0.33×pot (`claude_brain.py:44-48`). Against each there is a prompt addition; the river addition
`POKERB_CLAUDE_RIVERSIZE` is default OFF and EV-UNMEASURED.
**Usable standalone?** Yes, if you replace `research/llm.ask_claude` with your own API call — the class is
thin (117 lines) and otherwise depends only on prompt + executor.
**Pitfalls.** The brain path BYPASSES `pokerbot/strategy/bot.py` completely (it calls `api.legalize` directly).
Every improvement that lives in the engine strategy — sizing grid, guards, profiles — does not reach the brain.
Exactly on that the comparison "brain vs engine" has broken down again and again in the project (memory
[[brain-engine-two-products]]).

### Understanding layer — `pokerbot/brain/understanding.py`
**Purpose.** Fuses SPR/position/pot odds/MDF, board texture, hand strength, initiative and measured GTO heuristics into
ONE engine-computed text block, so that the model can reason even without a solve.
**Interface.** `strategic_read(spot) -> str` (only public function). The priors stand as named
constants at the top: `RIVER_BET_MEDIAN_X=0.33`, `RIVER_CHECK_RATE=0.58`, `SPR_COMMITTED=1.0`, `SPR_DEEP=6.0`,
`STRONG_MADE=0.62`, `MEDIUM_MADE=0.40`.
**Input/output.** `Spot` in, multi-line text out (`STRATEGIC READ (...)` + four bullet points:
Geometry / Hand vs board / Initiative / Principle).
**Dependencies.** Only `brain/api.py` (hard). No solver, no net.
**Status.** Stateless, purely deterministic.
**Cost.** < 1 ms (own smoke; contains a treys evaluation, no MC simulation).
**Measurement status.** UNMEASURED. Built and locally verified (OFF byte-identical, ON correct numbers), but the
realised EV benefit is explicitly unproven (`docs/STATE.md:1078`, `../plans/ROADMAP.md:26-35`). The two
river numbers 0.33/0.58 come from an own solver measurement over 5 boards × 2 pot types
(`understanding.py:21-22`).
**Usable standalone?** Yes — this is the lightest reusable block of the whole track (only `api.py` needed), and it
also works for a completely different LLM or as explanatory text for humans.
**Pitfalls.** `_draw_note` (`understanding.py:93-101`) derives from `board_texture`, and `twotone` there means
"exactly two cards of the same suit" (`strategy/postflop.py:89`). On a 5-card river the layer therefore
writes "flush possible", although with only two suited cards no flush is possible at all — reproduced myself
(board `As Kd 2h 7c 9d` → "wet/dynamic board; flush possible"). Whoever feeds the block into the model feeds
a false claim along with it here.

### Compute modes — `pokerbot/brain/modes.py`
**Purpose.** Makes the accuracy-versus-time trade-off explicit and globally switchable.
**Interface.** `Mode` dataclass (`name, time_budget_s, equity_iters, rollout_k, max_new_tokens,
exact_threshold, sympy_verify, analysis`); four instances `FAST/STANDARD/DEEP/TRAIN`; `current()`, `set_mode(mode)`,
context manager `using(mode)`.
**Input/output.** Mode name or `Mode` in, active `Mode` out.
**Dependencies.** None.
**Status.** GLOBAL, process-wide (`_active` as a one-element list, `modes.py:42`). Consumers are `api.equity`
(MC iterations), `rl_env.rollout_action_ev` (rollout count), `policy.QwenPolicy` (token and time budget).
**Cost.** Negligible; the values however are the dominant cost lever of all other modules
(STANDARD: 1000 equity iterations, 5 s budget; DEEP: 8000 iterations, 180 s).
**Measurement status.** UNMEASURED (configuration layer, no EV arm).
**Usable standalone?** Yes, 62 lines without dependencies.
**Pitfalls.** Global state plus default `STANDARD`: whoever forgets to set `TRAIN`/`FAST` in a measurement run
measures with different equity iterations than the comparison run — and MC iterations change decisions at
boundary spots. Always set explicitly, never rely on the default.

### Solver search as policy — `pokerbot/brain/solver_policy.py`
**Purpose.** Entirely without LLM: postflop is played directly from the live solve, otherwise it falls back to a fallback policy.
**Interface.** `SolverSearchPolicy(seat=0, fallback=None, seed=0)`, callable as `policy(table, seat) ->
(action, amount_chips)`; counters `.solved` and `.fell_back`.
**Input/output.** Table+seat in; legal action out. Default fallback is a `SixMaxBot` TAG
(`solver_policy.py:26-34`).
**Dependencies.** `brain/api.solve_node` + `format_spot.spot_from_table` (hard); the default fallback pulls in
`arena/sixmax` and `training/rl_env` (replaceable: any callable with the same signature suffices).
**Status.** Own RNG per instance for the mix draw; the solve cache lives in `api.py`, not here.
**Cost.** Dominated by `solve_node` (30–79 s per NEW solve, `api.py:181-185`); cache hits are cheap.
**Measurement status.** UNMEASURED in bb/100. Only the coverage is documented: HU solve rate ~1.0, 25/25 in the smoke of
2026-06-18 (`solver_policy.py:14-15`); 6-max falls back frequently, because TexasSolver handles two players.
**Usable standalone?** Yes, if TexasSolver is reachable via `strategy/gto_oracle` and you pass your own
fallback.
**Pitfalls.** Unusably slow for real play as long as the cache is cold — and the ranges are FIXED
single-raised-pot defaults on every street (`api.py:204-208`), so systematically too wide in 3-bet/limped pots.
The solver then delivers a precise answer to the wrong question.

---

# Part B — `training/` (self-play reward + Qwen/GLM training)

### RL environment + rollout EV — `training/rl_env.py`
**Purpose.** Evaluates any policy via realised EV against a bot league and provides the rollout EV that
feeds both the pilot and the GRPO reward.
**Interface.**
- `league_policy(bot) -> policy(table, seat)` (the bot stays reachable as `_p.bot` so that CRN reseeding works).
- `play_hand(table, policies, observers) -> {seat: net_chips}`.
- `make_league(profiles, hero_seat=0, seed=None) -> {seat: SixMaxBot}`.
- `evaluate_policy(hero_policy, profiles=(...), n_hands=500, seed=0, hero_seat=0, starting_stack=10000, sb=50,
  bb=100) -> {bb_per_100, n, total_bb, std_bb}`.
- `selfplay_zero_sum_check(...) -> {per_seat_bb_per_100, worst_hand_residual_chips}` (chip conservation as an invariant).
- `rollout_action_ev(snapshot, hero_seat, action, amount, cont_policy, profiles=(...), k=None, base_seed=0,
  bb=100) -> float` — mean hero net in bb, measured from the snapshot, i.e. EV RELATIVE TO AN IMMEDIATE FOLD.
- `gen_decision_states(profiles=(...), hero_seat=0, n_states=50, seed=0)` — generator of `(snapshot_table, spot)`.
- Constants `TRAIN_LEAGUE = ("tag","lag","nit","station","maniac")`, `HELDOUT_LEAGUE = ("rock","whale","shark")`.
**Input/output.** Policies are `callable(table, seat) -> (action: str, amount_chips|None)`. Snapshots are
`deepcopy` copies of the Table; `rollout_action_ev` does NOT mutate the passed snapshot.
**Dependencies.** Hard: `pokerbot/engine/table.py`, `pokerbot/arena/sixmax.py`, `brain/modes.py`. `brain/
format_spot` only in the generator (lazy).
**Status.** Per hand: the Table. Between rollouts there is an explicit reset — `_reseed_for_rollout` reshuffles only
the cards NOT YET dealt, `_reset_cont` resets opponent model, hand fields and RNG of the hero
continuation bot (`rl_env.py:130-152`). Without this reset the reward is not reproducible.
**Cost.** Not measured as a number in the repo; building the state buffer is documented as SINGLE-THREADED
and was the bottleneck of one run (`docs/STATE.md:1196`).
**Measurement status.** MEASURED POSITIVE as a measuring instrument (see `training/pilot.py`), but REFUTED as an RL reward:
`make_league` builds all opponents from THE SAME `SixMaxBot` engine (~68 % identical postflop behaviour) and the
hero continuation is hard-coded `tag` (`qwen_grpo.py:116`) → the reward measures "engine against engine", not GTO; the
attainable RL ceiling was estimated from that at ~engine level and the RL track was discontinued (`docs/STATE.md:1087`).
**Usable standalone?** Yes — alongside `api.py` this is the most usable piece for an outsider: a paired,
seed-controlled EV measurement environment for arbitrary policies. Only `engine/table.py` and an opponent bot are needed.
**Pitfalls.** `rollout_action_ev` measures EV RELATIVE to the snapshot stack, so fold is 0 by definition. Whoever
compares the number with an absolute bb/100 quantity compares two different things.

### De-risk pilot (EV signal proof) — `training/pilot.py`
**Purpose.** Proves locally and free of charge whether rollout EV carries a learnable signal at all before spending GPU
money.
**Interface.** `candidate_actions(snapshot) -> [(action, amount, label)]`; `rank_state(snapshot, hero_seat,
cont_policy, k=16, profiles=..., base_seed=0) -> [{action, amount, label, ev_bb}]` (best first);
`baseline_profile(profile, hero_seat=0)`, `baseline_random(seed=0)`; `run_pilot(n_states=8, k=16, seed=0,
profiles=..., hero_seat=0, baselines=None) -> dict`.
**Input/output.** Out come, per spot, the EV-ranked candidates plus the gap between oracle action and
every baseline, aggregated to `{gap, sem, sig_2sem}`.
**Dependencies.** `training/rl_env.py`, `pokerbot/arena/sixmax.py` (hard).
**Status.** Stateless; pairing via `base_seed` (all candidates share the seed = CRN) and a FRESH
holdout seed for the unbiased re-measurement (`pilot.py:104-113`).
**Cost.** Not measured; scales with `n_states × candidates × k` rollouts.
**Measurement status.** MEASURED POSITIVE: n=200 against random +11.03 ± 3.31, against maniac +5.21 ± 1.77, against tag
+5.62 ± 1.81 — all > 2·SEM; the gap grew with the sample (+2.06 → +5.62), holdout league (rock/whale/shark)
n=50 likewise significant (+3.52 ± 1.39 against tag) — `docs/STATE.md:1388-1394` and `:1404-1407`.
**Usable standalone?** Yes, entirely without LLM and without GPU. It is a general "which action would have been better
here" machine.
**Pitfalls.** The oracle has FORESIGHT (it rolls out the future) — it is the upper bound a learned
policy approaches, not an attainable target. Whoever reads the oracle gap as "this is how much training brings" deceives
themselves systematically.

### SFT trainer — `training/qwen_sft.py`
**Purpose.** LoRA fine-tuning of a base model on PokerBench and/or on the project's own DSL shards.
**Interface.** No command line, via environment variables: `BASE` (default `Qwen/Qwen3-8B`), `MAXN`, `EPOCHS`,
`BATCH`, `QUANT4`, `ATTN`, `DSL` (comma-separated JSONL shards), `SKIP_PB`, `OUT`, `CURRICULUM`, `REPLAY`,
`PACKING`, `ASSIST_ONLY`, `GRAD_CKPT`, `MAX_LEN`. Functions: `load_pokerbench()`, `load_dsl(paths)`,
`load_curriculum(paths, replay, seed)`, class `_OrderedSFT` (enforces a sequential sampler), `main()`.
**Input/output.** Shard lines are `{"spot": ..., "completion": ...}`; they become
`{messages:[system,user,assistant]}` with `policy.SYSTEM_PROMPT` as the system role. Out: a LoRA adapter under `OUT`.
**Dependencies.** Hard: `torch`, `transformers`, `peft`, `trl`, `datasets`, `bitsandbytes` — and
`pokerbot/brain/policy.SYSTEM_PROMPT` (deliberately, so that training and inference see the same prompt).
**Status.** Files only; sets `TOKENIZERS_PARALLELISM=false` BEFORE the transformers import (`qwen_sft.py:11-14`),
because `map()` otherwise hangs in a futex (observed: 21k lines, 32 minutes without progress).
**Cost.** MEASURED: ~60 min / 625 steps at `MAXN=10000` on an H100 (`docs/STATE.md:1163`).
**Measurement status.** MEASURED POSITIVE as a warm start: loss ≈ 0.087, mean token accuracy 97.5 % on 33k
DSL gold lines (`docs/STATE.md:1158`); a second run 1.94 → 0.10 at token accuracy 0.70 → 0.97
(`docs/STATE.md:1163`). So the model learns the language — what it does NOT learn is to play better (next
entry).
**Usable standalone?** Yes, if you replace `SYSTEM_PROMPT` with your own; otherwise nothing depends on the poker part.
**Pitfalls.** `ASSIST_ONLY=1` (loss only on the answer) was the fix against `frac_bad` — and the system prompt in
training MUST be the same as at inference, otherwise the model hallucinates `import api` under the unseen prompt
(`qwen_sft.py:22-25`). That is the most expensive, most frequently repeated error of this track.

### GRPO/DAPO trainer — `training/qwen_grpo.py`
**Purpose.** RL over realised self-play EV, to lift the policy above its SFT start.
**Interface.** `build_state_buffer(n, oversample=1.5, spread_eps=0.5, k_screen=8, profiles=TRAIN_LEAGUE,
hero_seat=0, seed=0, decontam=True) -> [(snapshot, spot)]`; `make_ev_reward(snapshots, hero_seat=0,
profiles=TRAIN_LEAGUE, k=K_ROLL, bb=100) -> reward_func(completions, sid, base_seed, ...) -> [float]`;
`build_dataset(states, tok=None, seed=0) -> (Dataset, snapshots)`; `make_config(out_dir)`;
`load_policy_model(base, adapter)`; `main()`. Reward knobs as environment variables: `R_BAD` (default −3),
`R_CLIP` (25), `R_FMT` (2.0), `K_ROLL` (16), `REWARD_TIMEOUT_S`, `REWARD_WORKERS`.
**Input/output.** Dataset columns `prompt`, `sid`, `base_seed`; reward = clipped rollout EV + format bonus
± decaying "engine-grounded" shaping. Out: adapter + `models/grpo_metrics.jsonl`-style curves
(`step, reward, reward_std, frac_bad, engine_grounded_rate, ...`).
**Dependencies.** `training/{rl_env,pilot}`, `pokerbot/brain/{executor,format_spot,policy,dsl_grammar}`,
`pokerbot/arena/sixmax` (hard, CPU); `trl`/`torch`/`vllm` only in config/trainer (pod GPU).
**Status.** A process pool for the rollouts (`_POOL`), snapshots as a side table; CRN per completion via
`base_seed`, so that the group-relative advantage estimate isolates the ACTION and not the card luck.
**Cost.** Not cleanly measured; documented is a step profile from `models/grpo_metrics.jsonl` (step 1:
52.2 s incl. warm-up, then ~2 s per step in that run).
**Measurement status.** REFUTED as an EV lever. (1) First run with `R_BAD=-30`: reward flat at −17.69, the group
learned "be valid" instead of "play well" — evidence line 1 in `models/grpo_metrics.jsonl` plus the justification
`qwen_grpo.py:29-34`; fix to −3. (2) The trained 9B reached −43.30 ± 7.15 AIVAT (n=100,
`docs/STATE.md:1159`), i.e. about engine level. (3) A retraining (re-SFT on made-hand-native gold + fresh
GRPO) REGRESSED to −90.18 (`docs/STATE.md:1132`). (4) The root-cause analysis ($0, `docs/STATE.md:1087`) attributes
the ceiling to the reward (league from one bot engine, hard tag continuation). Conclusion in the repo: the gains
lay in the WIRING at inference time, not in the weights (`docs/STATE.md:1135`).
**Usable standalone?** The CPU half (`build_state_buffer`, `make_ev_reward`, `build_dataset`) runs without
torch/trl and is thus testable in isolation — deliberately layered that way. The trainer itself needs a GPU box.
**Pitfalls.** The reward is only as strong as the league. Whoever adopts this setup adopts the measured
trap: the model learns to beat its own league, and precisely thereby loses against a real solver opponent.
### PokerBench eval — `training/qwen_eval.py`
**Purpose.** Compares the base model against the LoRA on held-out PokerBench spots via action agreement.
**Interface.** `main()` (invocation `python -m training.qwen_eval [N]`), helpers `_action(text)`, `load_pokerbench()`,
`_heldout(n)`, `_gen(model, tok, prompt)`, `_score(model, tok, data, label)`.
**Input/Output.** PokerBench rows in, hit rate (first action keyword) out.
**Dependencies.** `torch`, `transformers`, `peft`, `datasets` (hard) plus an HF download.
**Status.** Stateless.
**Cost.** Not measured.
**Measurement status.** UNMEASURED in this file; the project's assessment of the metric is negative — action matching
against a reference says little about bb/100 (the same lesson as with the GTO score, `docs/STATE.md` head block).
**Usable standalone?** Yes. Contains a hard-coded adapter-path constant (`qwen_eval.py:20`, Windows path) —
adjust it.
**Pitfalls.** `_action` takes the FIRST action word in the text; a model that writes "I don't fold, I raise" in
running prose is scored as "fold".

### GTO-anchored eval + gate ladder — `training/qwen_eval_gto.py`
**Purpose.** Measures the policy against a HELD-OUT opponent league and condenses the release criteria into a ladder.
**Interface.** `league_eval(policy, league=HELDOUT_LEAGUE, n_hands=2000, seed=0, hero_seat=0) ->
{per_type, mixed_bb100, worst_bb100, spread_bb100}`; `gate_ladder(grpo, sft, pokerbench_acc, dsl_emit_rate,
legality, lbr_delta=None) -> dict`; `pokerbench_acc(model, tok, n=200) -> (acc, emit_rate)`; `main()`.
**Input/Output.** Policy in, metrics out; `main()` writes `eval_gates.json` (path via `GATES_OUT`).
Gates: G0 PokerBench accuracy ≥ 0.70 and DSL emission rate ≥ 0.99; G1 legality ≥ 0.99; G2 GRPO bb/100 >
SFT bb/100 (the core thesis); G3 worst case ≥ 0; G4 exploitability not worse.
**Dependencies.** `training/rl_env.py` (hard, model-free) — only `pokerbench_acc`/`main` need GPU models.
**Status.** Stateless; `EVAL_MIXED_ONLY=1` skips the five individual types (that was the cause of the timeout).
**Cost.** Not measured; scales with `n_hands` × league size × 2 adapters.
**Measurement status.** UNMEASURED as its own arm; the ladder was built as an instrument and $0-verified
(`docs/STATE.md:1398-1401`). A `data/eval_gates.json` is NOT present in this working directory.
**Usable standalone?** `league_eval`/`gate_ladder` yes, pure and model-free.
**Pitfalls.** The league here is "held out" only relative to the training league — all profiles come from the same
`arena/sixmax.py` engine. That is a robustness APPROXIMATION, not an independent opponent.

### Pod preflight check — `training/preflight.py`
**Purpose.** Fails within one to two minutes if the GPU environment or the TRL API does not fit — instead of after
an expensive half hour of model loading.
**Interface.** `main()`; output `PREFLIGHT1_OK` or `PREFLIGHT1_FAIL: ...` with return code ≠ 0.
**Input/Output.** Nothing in; status lines out.
**Dependencies.** `torch/transformers/trl/peft/bitsandbytes/datasets/vllm` (hard) plus
`training.qwen_grpo.{make_config, build_state_buffer, make_ev_reward}`.
**Status.** Stateless.
**Cost.** Per the header ~1–2 min, no model loading.
**Measurement status.** UNMEASURED as an EV lever; proven as a safeguard: a real bf16 matmul catches Blackwell cards
on which `torch.cuda.is_available()` is true but the kernels are missing (`preflight.py:20-25`).
**Usable standalone?** Yes, but only meaningful for exactly this stack.
**Pitfalls.** It checks the TRL configuration by CONSTRUCTION — if TRL changes its signatures, the script itself is
the first thing that has to be adjusted.

---

# Part C — `pipeline/` (PC hub: gated distillation, orchestration)

### EV truth filter — `pipeline/filter.py`
**Purpose.** The anti-hallucination gate: no proposal from a foreign model enters the dataset without the engine
having checked it deterministically.
**Interface.** `@dataclass Verdict(ok, reason, gate)`; `class EVFilter(decontam_keys=None)` with
`gate(ex, spot=None) -> Verdict` and `.stats` (`in, kept, schema, irrelevant, decontam, dup, illegal, ev`).
Gate chain: G1 schema, G2 topical relevance, G3 decontamination against the PokerBench test set, G4 deduplication,
G5 legality (`api.legalize` must leave the action unchanged), G6 EV plausibility (folding although a free check is
available; a call whose equity even against a RANDOM villain hand is clearly below break-even).
**Input/Output.** `ex` = dataset row from `dataset/schema.make_example` (fields `spot`, `completion`,
`action{action,size_bb}`); optionally the structured `Spot`, without which only G1–G4 run. Out: `Verdict`.
**Dependencies.** `pokerbot/brain/api.py`, `dataset/schema.py` (hard).
**Status.** PER RUN: `self.seen` (dedup) and `self.decontam`. One instance per build; not thread-safe
(`distill_run.py` therefore deliberately gates single-threaded).
**Cost.** G6 computes an MC equity against ALL remaining combos — not measured, but the most expensive stage.
**Measurement status.** UNMEASURED as an EV lever. The idea was later recommended as a live instrument ("EVFilter-G6 at
serve time against the catastrophe hands", `docs/STATE.md:1122`), but never measured in that form.
**Usable standalone?** Yes, if you take `dataset/schema.py` along or supply the three calls (`validate`, `is_relevant`,
`spot_key`) yourself.
**Pitfalls.** G6 is deliberately BLUNT: it measures against a random villain hand, i.e. a generous upper bound of
hero equity, and rejects only clear losers. Whoever takes it for a quality judgment lets a great deal of mediocrity
through.

### Frontier distillation loop — `pipeline/frontier_loop.py`
**Purpose.** Queries a frontier model on WEAK spots, presses every answer through `EVFilter` and appends only what is
accepted to a JSONL shard.
**Interface.** `frontier_proposer(provider='claude') -> proposer(spot_text) -> (proposal, (in_tok, out_tok))`;
`to_example(spot_text, proposal) -> dict`; `run(weak_spots, ev_filter=None, out_path=None, proposer=None,
provider='claude', limit=None) -> {accepted, rejected, filter, tokens, reject_reasons}`.
**Input/Output.** In: iterable `Spot`s. Proposal = JSON with `action`, `size_bb`, `reasoning`; from that a
program `# <reason>\ndecide('call', 7.5)` is built. Out: statistics + appended rows.
**Dependencies.** `dataset/schema`, `brain/format_spot`, `pipeline/filter`, `research/llm` (hard) — the
`proposer` is injectable so the loop can be tested without API cost.
**Status.** The `EVFilter` holds the state; the loop itself is stateless.
**Cost.** Token consumption is returned; no latency measurement in the repo.
**Measurement status.** UNMEASURED (no bb/100 number for data distilled from it). The overarching finding applies:
imitation lifts the START, not the ceiling (`pipeline/distill_teacher.py:6-7`).
**Usable standalone?** Yes, with your own `proposer` and your own gate.
**Pitfalls.** `to_example` truncates the reasoning to 500 characters and turns it into ONE comment line plus
`decide(...)` — that is exactly the "decorative" form that, measured in the project, produced `frac_bad` 0.97, while
the derivational form (`if eq >= req: ...`) gave 0.00 (memory [[reasoning-loop-not-decoration]]). Training on it
teaches the model not to compute.

### Weak-spot monitor — `pipeline/monitor.py`
**Purpose.** Defines the shared cluster taxonomy and finds the weakest clusters so distillation regrows there.
**Interface.** `cluster_of(spot) -> (street, hero_pos, spr_bucket, texture_tag)`;
`weak_clusters(records, k=10, min_n=20) -> [(cluster, mean_score, n)]`; `spots_in_clusters(spot_pool,
target_clusters)` (generator).
**Input/Output.** `records` = `[{'cluster': key, 'score': float, 'n': int}]`, higher score = better. Out: the
k weakest clusters with at least `min_n` observations.
**Dependencies.** `brain/api.py` (SPR + texture), `brain/format_spot.Spot`.
**Status.** Stateless.
**Cost.** Not measured (pure aggregation).
**Measurement status.** UNMEASURED.
**Usable standalone?** Yes, very small (52 lines).
**Pitfalls.** The buckets are coarse (3 SPR levels, 5 texture classes) — a "weak cluster" can be a mixture of very
different spots. Usable as a lead, not as proof.

### PC↔pod transport — `pipeline/orchestrate.py`
**Purpose.** Packs code and data into ONE tarball, pushes it to the pod via scp and pulls adapter/report back.
**Interface.** `build_tarball(out_path=None, members=None) -> str`; `push(ip, port, tarball,
remote='/root/bundle.tgz', unpack_to='/root/pokerb')`; `pull(ip, port, remote, local)`.
**Input/Output.** Default `BUNDLE` = `pokerbot, dataset, training, infra, research` plus four
`knowledge_base` subfolders (`orchestrate.py:23-25`); out `subprocess.CompletedProcess`.
**Dependencies.** `pokerbot/config.py`, an SSH key (path hard-coded, `orchestrate.py:18`), `scp`/`ssh`
in PATH.
**Status.** Stateless; files on both sides.
**Cost.** Not measured. Rationale in the header: `scp -r` over hundreds of small files hung, a single
tarball did not.
**Measurement status.** UNMEASURED.
**Usable standalone?** Yes, but the key path is hard-coded and Windows-specific.
**Pitfalls.** The bundle deliberately omits `books/` and `knowledge_base/hand_histories`. Whoever uses a module on
the pod that reads those paths gets a FileNotFound there that is never seen locally.

### Teacher distillation (run) — `pipeline/distill_run.py`
**Purpose.** Generates HU postflop spots, queries Claude in parallel, gates single-threaded and writes a shard.
**Interface.** `main()` (arguments `--n`, `--out`, `--threads`), helper `_propose(spot, proposer)`.
**Input/Output.** Out: JSONL shard with accepted rows plus gate statistics.
**Dependencies.** `dataset/build/from_hu_postflop`, `pipeline/{filter,frontier_loop}`, `research/llm`.
**Status.** One `EVFilter` per run.
**Cost.** The header cites a pilot run at ~$4 for n=300 (`distill_run.py:10`).
**Measurement status.** UNMEASURED (no EV arm on the generated data).
**Usable standalone?** Only together with the `dataset/` branch.
**Pitfalls.** ONLY the API calls are parallel; the gate is deliberately serial because `EVFilter` holds state.
Parallelising it silently destroys dedup and statistics.

### Teacher distillation (harvest) — `pipeline/distill_teacher.py`
**Purpose.** Filters the raw candidates of the large teacher model pulled back from the pod into an SFT corpus.
**Interface.** `main()` (`python -m pipeline.distill_teacher [in] [out]`).
**Input/Output.** `data/teacher_raw.jsonl` in → `dataset/shards/teacher.jsonl` out. Legality was already
enforced on the pod via `run_program`; here schema/relevance/decontamination/dedup run.
**Dependencies.** `pipeline/filter`, `pokerbot/config`, optionally `dataset/decontam`.
**Status.** One filter per run.
**Cost.** Not measured.
**Measurement status.** UNMEASURED; the file itself states the limit: distillation lifts the START, not the
ceiling (`distill_teacher.py:6-7`).
**Usable standalone?** Only as part of the ensemble.
**Pitfalls.** If `dataset/decontam` is missing, the code silently falls back to an EMPTY decontamination set
(`distill_teacher.py:20-24`) — G3 then runs without effect and you may be training on test spots.

### Shard quality inspector — `pipeline/inspect_teacher.py`
**Purpose.** $0 gate before large spends: shows action mix, grounding rate and degeneracy per shard.
**Interface.** `stats(path) -> dict`, `main()` (`python -m pipeline.inspect_teacher [shard ...]`).
**Input/Output.** JSONL shards in; per shard action shares, share with an `api.*` call before the first
`decide` ("grounded"), `decide_mix` share, street coverage.
**Dependencies.** `pokerbot/config` (hard), otherwise standard library — no torch.
**Status.** Stateless.
**Cost.** Not measured (pure line reading).
**Measurement status.** UNMEASURED. The thresholds are SET as gate criteria, not measured: no single action
above 70 %, aggression share within ~15 percentage points of the solver baseline (`inspect_teacher.py:6-8`).
**Usable standalone?** Yes, with minimal adjustment of the config import.
**Pitfalls.** "grounded" is a pure text check for `api.` before the first `decide` — a program that computes the
number and then ignores it counts as grounded.

### Self-growing mathematics — `pipeline/math_loop.py`
**Purpose.** Lets a frontier model propose new exact formulas, checks each against the engine and materialises
only the verified ones into the callable toolbox.
**Interface.** `grow_math(request, model='gpt-5.5', max_tokens=16000, consult=None) -> dict`.
**Input/Output.** Text request in; out the number of verified/rejected formulas and the path of the
newly generated `postflop_formulas.py`.
**Dependencies.** `research/{llm, postflop_calc_consult, postflop_calc_gate}` (hard).
**Status.** Writes into `knowledge_base/math/` — i.e. into the project doctrine's forbidden zone.
**Cost.** Not measured.
**Measurement status.** UNMEASURED as an EV lever. Proven is the one-off yield of the underlying path: 34
generated postflop calculations, ALL 34 engine-verified (`docs/STATE.md:1409-1412`).
**Usable standalone?** No — without the `research/` gate path it is just an LLM call.
**Pitfalls.** It writes generated code into the math core. In this repo those files are immutable by
doctrine; an outsider should redirect the output path before running it.

### Run evaluation — `pipeline/process_run.py`
**Purpose.** Turns the four artifacts pulled back from a pod run into ONE verdict.
**Interface.** `unpack_adapter()`, `gate_summary() -> (rows, pass_bool|None)`, `curve_summary() -> rows`,
`gpu_summary() -> rows`, `verdict(gates_pass, curve_rows) -> str`, `main()`.
**Input/Output.** Reads (all optional) `models/qwen_poker_grpo.tgz`, `data/eval_gates.json`,
`data/training_metrics.jsonl`, `data/gpu_load.jsonl`; prints gate ladder, learning curve, GPU load, verdict.
**Dependencies.** `pokerbot/config` (hard); no torch.
**Status.** Unpacks the adapter into `models/qwen_poker_grpo/`.
**Cost.** Not measured.
**Measurement status.** UNMEASURED. In this working directory `data/eval_gates.json` is missing,
`data/training_metrics.jsonl` is present — so the report only runs partially.
**Usable standalone?** Only for exactly this quartet of files.
**Pitfalls.** Missing files are reported as "run not finished", not as an error — an empty report
looks like a harmless interim state even if the run actually crashed.

---

# Part D — Models and odds and ends

### Model artifacts — `models/` (not in git)
**Purpose.** Stores the LoRA adapters and the packed pod results of this track.
**Interface.** None — files. Adapters are loaded via `peft.PeftModel.from_pretrained(base, path)`.
**Input/Output.** Existing directories/files (state of this working directory):
`qwen_poker_ckpt500/`, `qwen_poker_grpo/` (both base `Qwen/Qwen3-8B`, LoRA r=64), `qwen_poker_lora/`
(base `THUDM/GLM-Z1-9B-0414`, r=64), `qwen_local_*`, `qwen_1.7b_aligned/`, `qwen_smoke/`, plus the tarballs
`grpo_slim.tgz` (708 MB), `grpo_slim_baseline.tgz` (706 MB), `qwen_poker_grpo.tgz` (708 MB),
`qwen_poker_grpo_live.tgz` (710 MB), `qwen_poker_sft.tgz` (2.8 GB), `sft_new.tgz` (2.1 GB),
`sft_slim.tgz` (706 MB) and the curve `grpo_metrics.jsonl`.
**Dependencies.** `peft`/`transformers` and the respective base model from the network.
**Status.** Pure artifacts; `models/` is gitignored (`.gitignore:12`) — a clone of the repo does NOT have them.
**Cost.** Storage as above (total ~8 GB in the directory).
**Measurement status.** The protected state `grpo_slim_baseline.tgz` is the model with −43.30 ± 7.15 AIVAT, or
robustly classified ~−37 to −40 with a fat left tail (`docs/STATE.md:1159`, `:1121`). The later models
are REFUTED (−90.18, `docs/STATE.md:1132`).
**Usable standalone?** Only with the matching base model and the same prompt wiring (made-hand block ON,
to_call fix ON — otherwise you measure a different bot).
**Pitfalls.** Adapter and serve configuration belong together. The same weights with a different prompt produced
differences of 40 bb/100 in the project (`docs/STATE.md:1120`) — without the flags an adapter is worthless.

### RunPod serverless teacher — `../../infra/serverless/handler.py` (repo root)
**Purpose.** A vLLM worker that generates DSL programs in batch and engine-gates them directly on the worker.
**Interface.** RunPod job `{"input": {"n", "seed", "temperature", "max_tokens"}}` →
`{"examples": [...], "kept", "total", "model"}`.
**Input/Output.** JSON only; the spots come from `research/teacher_generate.build_spots`, the gating from
`gate_and_rows`.
**Dependencies.** `runpod`, `vllm`, `transformers`, `pokerbot/brain/{modes,policy}`, `research/teacher_generate`.
**Status.** Loads the model ONCE at cold start at module level; sets `modes.set_mode("fast")` globally.
**Cost.** Not measured.
**Measurement status.** UNMEASURED.
**Usable standalone?** Only on RunPod serverless.
**Pitfalls.** `modes.set_mode("fast")` is process-wide — the gate equity in the worker therefore computes with 300
MC iterations, while a local re-check takes 1000 by default and can reach different verdicts.

### Related tools outside the three folders (signposts only, not catalogue format)
- `research/claude_brain_smoke.py` — local output check of the Claude brain before spending any money.
- `research/claude_export.py` — lets the brain play and exports PokerStars hand histories for
  external GTO grading.
- `research/claude_vs_engine.py` — paired decision diff brain vs engine including the program comments
  as "reasoning".
- `research/glm_local_probe.py` — runs the trained 9B locally in 4-bit; this is how the hand-reading error was found
  that led to the made-hand block.
- `research/teacher_generate.py` — the spot and gate functions that `../../infra/serverless/handler.py` reuses on the pod.
- `infra/gtow_glm_pod.py` — isolated pod that merges the GRPO adapter into the base, serves it via vLLM and plays
  against the external benchmark.
- `research/llm.py` — the shared Claude/OpenAI call helpers (structured output, prompt caching, retries).
- `pokerbot/strategy/postflop_corset.py` — uses `brain/api.py` to cap a call against a large bet;
  MEASURED as a NO-OP (over 13 spectrum spots the model did not over-call at all; `docs/STATE.md:1152`).
- `tests/test_made_hand_read.py` — the $0 test that pins down the made-hand block; a good entry point to
  see how to build a `Spot` by hand.

---

## Knowledge base, data, tools

This subsystem contains no game logic: it is the store (distilled book/solver/opponent knowledge as
JSON and Python), the data directory (registry + converters + shards) and the toolbox (miners, gates,
consult and replay scripts) from which the strategy modules are fed and the measurements are produced.
You will need almost none of it in full — but the formula modules, the range blueprints, the
run-storage convention and two or three miners can each be taken over on their own, without the rest of the repo.
If you take only ONE thing: the run storage + the journal (below), because without them no number survives.

---

# 1. knowledge_base/ — the distilled knowledge

### Core formulas — `knowledge_base/math/formulas.py`
**Purpose (1 sentence).** 12 basic formulas extracted from the poker books and executed at generation time (pot odds,
MDF, EV, SPR, fold equity, outs, blocker combinatorics, equity realisation) as pure stdlib Python.
**Interface.**
- `compute_pot_odds(P, B, C) -> (ratio, required_equity)` — pot odds as a ratio and as required equity.
- `equity_needed_to_call(pot_before_call, call_amount, villain_risked_this_street=0.0) -> float`.
- `expected_value(probabilities, payoffs) -> float` — sum of p·payoff, with length/sum check.
- `minimum_defense_frequency(pot, bet) -> float` — MDF = p/(p+b).
- `bluff_to_value_and_frequencies(P, ...)` — bluff/value ratio and frequencies of a polar bet.
- `required_future_winnings_for_implied_odds(pot_size, call_cost, hit_probability) -> float`.
- `required_fold_equity(P, R, C, E) -> float` — required fold frequency of a raise/jam.
- `outs_to_equity_rule_2_and_4(outs, cards_to_come) -> float`.
- `compute_spr(effective_stack, pot_size) -> float`.
- `count_hand_combos_with_blockers(pattern, known_cards) -> int`.
- `breakeven_bluff_percentage(bet_size, pot_size) -> float` — alpha = b/(b+p).
- `equity_realization(eq, pot, cost, ev=None) -> (…)`.
**Input/Output.** Only floats/ints or card lists as 2-character strings (`'As'`); returns float or tuple.
No dicts, no state, no IO.
**Dependencies.** Only `math`/`typing` — NO repo dependency. Fully copyable.
**Status.** Stateless.
**Cost.** Not measured (arithmetic one-liners; the cost lies in the caller).
**Measurement status.** UNMEASURED as an EV lever. The functions were executed at generation time
(`research/extract_math.py:111 verify()` runs the generated code). The CLAUDE.md doctrine on this is
explicit: formulas are "soup meat" — features inside empirical deciders, never dogma above them; formula-based
frequency matching was refuted 3x by measurement (CLAUDE.md, block "OPERATIVE DOKTRIN").
**Usable standalone?** Yes, completely. Copy the file, done.
**Pitfalls.** `compute_pot_odds` and `equity_needed_to_call` define `pot` DIFFERENTLY (once as the pot BEFORE
the bet plus the bet separately, once as the pot INCLUDING the bet). Mixing them computes silently wrong.

### Extended formula modules — `knowledge_base/math/postflop_formulas.py`, `knowledge_base/math/strategy_formulas.py`
**Purpose (1 sentence).** 66 further calculation functions (34 postflop, 32 strategic) as a callable library —
bluff/value ratios, geometric sizing, rake-corrected pot odds, range combinatorics, preflop sizings,
polarisation/texture indices, exploit deltas.
**Interface.** All module functions, all type-annotated, among them
`alpha_break_even_bluff_frequency(bet, pot)`, `minimum_defense_frequency_by_bet_fraction(pot_fraction)`,
`per_street_geometric_bets(pot, effective_stack, streets) -> list[float]`,
`pot_odds_required_equity_with_rake(to_call, pot, rake_fraction, rake_cap)`,
`range_combo_count(hand_classes, known_cards) -> int`,
`preflop_open_raise_size_bb(position, effective_bb, ante_bb=0.0)`,
`cbet_frequency(texture_wetness, in_position, spr, range_advantage, nut_advantage)`,
`exploit_fold_deviation_ev(pot_size, bet_size, actual_fold_frequency, equilibrium_fold_frequency)`.
**Input/Output.** Scalars in, scalars/lists out. `hand_classes` = sequence `(rank1, rank2, suited|None)`.
**Dependencies.** stdlib only (`math`, `typing`). Replaceable/copyable.
**Status.** Stateless.
**Cost.** Not measured.
**Measurement status.** UNMEASURED as playing strength. MEASURED NEUTRAL as consistency: `pokerbot/autogym/verify_refs.py`
runs all stored `verify_expr` references against the installed modules — per CLAUDE.md
(AUTOGYM block) most recently 66/66. An important caveat sits in the tool itself (`verify_refs.py:5-9`):
verify_expr comes from the same generation as the formula; that is consistency, NOT truth.
**Usable standalone?** Yes. The only caveat: caution with the heuristic functions —
`cbet_frequency`, `range_morphology_selector`, `capped_range_penalty` and others are LLM-generated models, not
derivations from poker theory.
**Pitfalls.** The modules are NOT all of equal standing: the exact ones (alpha, MDF, pot odds, combinatorics)
sit next to free heuristics with invented weights. Whoever adopts them as a block imports the
heuristics too — they are EV-measured nowhere in this repo.

### Raw math artifacts — `knowledge_base/math/*.json` / `*.md`
**Purpose (1 sentence).** The source from which the three formula modules were materialised, plus the
full-text book extraction.
**Interface.** Pure data files: `math.jsonl` (13 rows, each `{id, topic, formula:{name, definition,
formula_latex, …}, worked_example, function_name}`), `math.json` (the same, merged),
`postflop_calc_verified.json` / `strategy_calc_verified.json` (`{"calculations": [ {category, definition,
formula_plain, function_name, inputs, name, python_function, verify_expr, verify_value, worked_example} ]}`),
`mathematics_of_poker.json` + `.md` (book extract, 540 KB Markdown).
**Input/Output.** Output only. Consumers: `dataset/build/from_math.py`, `dataset/build/from_calc.py`,
`pokerbot/autogym/verify_refs.py`.
**Dependencies.** None.
**Status.** Stateless, static.
**Cost.** ~1.5 MB total.
**Measurement status.** UNMEASURED (data artifacts).
**Usable standalone?** Yes — the `*_verified.json` are the most interesting piece: they contain the
Python source of EVERY function plus an executable self-test expression, so they are an immediately
regenerable formula package.
**Pitfalls.** `postflop_calc.json` and `postflop_calc_verified.json` are byte-identical in size (40937) — the
"verified" file is not a filtered subset; the name suggests a selection that did not take place.

### Concepts — `knowledge_base/concepts/concepts.jsonl`
**Purpose (1 sentence).** 67 records of strategy concepts drawn from the books (title, category,
summary, details) — prose knowledge, not code.
**Interface.** JSONL, each row `{id: "<book>:<pages>", book, concepts: [{title, category, summary,
details, …}]}`.
**Input/Output.** Read only. Generated by `research/extract_concepts.py`.
**Dependencies.** None (data).
**Status.** Static.
**Cost.** 765 KB.
**Measurement status.** UNMEASURED as playing strength. NOT listed as active gold in `dataset/registry.py`; the
mixture of concepts+math+exploit in one shard (`shard.local_kb`) is explicitly marked there as the cause of an
earlier training failure (`registry.py:83-86`, "the original frac_bad=0.97 cause; NOT the gold").
**Usable standalone?** Yes as prompt/RAG material. Worthless for an engine, because not machine-evaluable.
**Pitfalls.** It is book prose. It sounds like truth and is checked against bb/100 nowhere.

### Theory extracts — `knowledge_base/theory/`
**Purpose (1 sentence).** Distillates of research papers and consult answers (Pluribus, Supremus, Deep-CFR+,
sequential equilibrium, WEVA abstraction, algorithmic game theory) plus in-house doctrine documents.
**Interface.** JSON per paper (`pluribus_paper.json`, `supremus_paper.json`, `deep_pdcfr_paper.json`,
`weva_abstraction_paper.json`, `seq_equilibrium_cfr_paper.json`, `nn_architecture_paper.json`,
`algorithmic_game_theory.json`) + Markdown analyses (`grand_synthesis.md`, `brown_vnm_169.md`,
`bluff_lizenzen.md`, `exploit_gto_bridge.md`, `gto_hybrid.md`, `poker_for_compute.md`, …).
**Input/Output.** Read only.
**Dependencies.** None.
**Status.** Static.
**Cost.** ~350 KB.
**Measurement status.** UNMEASURED. `harvard_general_cfr_paper.json` is 2 bytes — an empty JSON, i.e. a
failed extraction run that was never deleted.
**Usable standalone?** Yes as reading material.
**Pitfalls.** Metadata from LLM consults is partly unverified here; the repo has its own rule for that
(CLAUDE.md: "Perplexity scrambles metadata — NEVER cite unverified"). Take no paper citation from
these files without cross-checking.

### Exploit knowledge — `knowledge_base/exploit/`
**Purpose (1 sentence).** Precomputed "opponent looks like X in spot Y → shift action Z by Δ" directives
plus measured opponent leaks.
**Interface.**
- `playbook.jsonl` — 11,520 rows, each `{opp:{vpip,pfr,fold_to_cbet,three_bet,af}, ctx:{stack_bb,hero_position,
  street,facing}, directive:{reasoning, level, target, adjust:{action, freq_delta}, confidence}}`.
- `unified.json` — 62 condensed rules `{stat, condition, spot, adjustment, delta, magnitude, confidence,
  rationale, merged}`.
- `pluribus_leaks.json` (`decisions`, `leaks`, `bet_size_footprint`, `river_call_strength`),
  `slumbot_fold.json`, `stack_depth_params.json`, `beyond_gto.json`, `exploitative_poker.json`.
**Input/Output.** Read only; consumed by `pokerbot/strategy/unified_exploit.py`,
`pokerbot/strategy/playbook.py` and `dataset/build/from_exploit.py`.
**Dependencies.** None (data). The consumers are hard, the format is replaceable.
**Status.** Static.
**Cost.** playbook.jsonl 7.2 MB — read line by line, not all into memory.
**Measurement status.** MEASURED NEGATIVE for the HU exploit path hanging off it: the journal
(`data/autogym/journal.jsonl`, entry `EXPLOIT-GATE-VERDIKT` of 2026-09-09) measures `POKERB_EXPLOIT=1` against 0
on paired decks, 600 decks per league profile: all eight point estimates ≤ 0, pooled about −12 bb/100 (SE ~4.5).
Verdict there verbatim: "the Dirichlet river exploit LOSES against every league profile". The 6-max read path
is NEUTRAL in the same entry (+3.6 ± 13.5).
**Usable standalone?** Yes — `unified.json` (62 rules) is small and directly translatable into your own overlay
logic.
**Pitfalls.** The playbook is LLM-generated (`research/exploit_playbook.py`), not measured from hands.
It is a PROPOSAL generator; the repo measured the exploit mechanism hanging off it and switched it OFF.
Adopt the data, not the assumption that it works.

### Preflop ranges — `knowledge_base/ranges/` + `knowledge_base/cfr/preflop_pushfold.json`
**Purpose (1 sentence).** The finished preflop blueprints: per node and hand class an action mix.
**Interface.**
- `preflop_blueprint.json` — dict with nodes `OPEN, LIMP, ISO, 3BET, 4BET, 5BET, JAMSB, JAMBB`; per node
  dict hand class → mix, e.g. `"AA": {"fold": 0.0, "call": 0.0, "3bet": 1.0}`.
- `preflop_blueprint_k0.json`, `preflop_blueprint_solvergraft.json` — variants of the same format.
- `preflop_pushfold.json` — Nash push/fold, keyed by effective stack in bb (`"2"…"9"…`).
- `preflop_eqmatrix.json` (`{n, sims, eq}` — precomputed class-vs-class equities),
  `preflop_gto_table.json` (1.1 MB), `preflop_leaf_table.json`, `ranges_grids.json`, `range_captions.json`,
  `ranges_vision.jsonl` (38 vision-parsed book grids).
**Input/Output.** Read only; the consumer is `pokerbot/strategy/preflop_blueprint.py`.
**Dependencies.** None (data). Hand-class notation is the usual one (`AKs`, `T9o`, `77`).
**Status.** Static.
**Cost.** ~2.5 MB total; `preflop_eqmatrix.json` 500 KB.
**Measurement status.** MEASURED POSITIVE in the ensemble, not in isolation: CLAUDE.md calls preflop a "near-solved
blueprint" with a share of about −1.6 bb/100 of the total loss against GTO Wizard (decomposition of the −20 run).
In isolation the blueprint was not A/B-tested against an alternative in this repo.
**Usable standalone?** Yes, this is the most easily adoptable part of the whole knowledge base: load the JSON,
form the hand class, draw the mix.
**Pitfalls.** The blueprint is used in the bot only from a certain stack depth — per journal entry
`KONSULT-SOL-KORREKTUR` (2026-09-10) it fires "only from 140 bb effective (bot.py:200)". Whoever expects it at 100 bb
measures a different bot than they think; exactly this error is recorded in the journal as a corrected documentation
claim.

### Postflop artifacts — `knowledge_base/postflop/`
**Purpose (1 sentence).** The trained solver-imitation nets (bet frequency per street) plus two small
calibrated tables and a rule playbook.
**Interface.** Files, not functions: `advisor.pt` (flop), `turn_advisor.pt`, `river_advisor.pt`,
`river_advisor_la.pt` (line-aware), `defense_advisor.pt`, `deepcfr_hunl.pt` (556 KB, decommissioned),
`texture_freqs.json` (`{"IP": {"ALL":0.741, "connected":0.609, "high":0.785, "low":0.73, "monotone":0.576,
"paired":0.781}, "OOP": {…0.224…}}`), `calibrated_priors.json` (`{"cbet_eq":0.72, "donk_eq":0.75}`),
`openai_strategy.json` (`{summary, rules[15], fold_equity, parameters}`).
**Input/Output.** `.pt` = torch MLPs, loaded by `pokerbot/strategy/advisor.py`; the JSONs by
`pokerbot/strategy/postflop.py` and `playbook.py` respectively.
**Dependencies.** The `.pt` need torch AND the exact feature order of the trainer
(`research/train_*_advisor.py`) — hard coupling; a net without its feature construction is worthless.
**Status.** Static (loaded once per process).
**Cost.** ~24 KB per net; load time not measured. There is a measured batch speed-up of the
advisor path of 2.2x (CLAUDE.md, AUTOGYM block "Advisor-Batch (2,2x)").
**Measurement status.** MEASURED POSITIVE per the registry description: flop +63 % against a pure hand-strength baseline,
turn +46 %, river +18 % (`dataset/registry.py:97`, `:99`, `:101`). Caution: that is an imitation metric
(closeness to the solver frequency), NOT bb/100. `defense_advisor.pt` carries the note
"verify live wiring" in the same file (`registry.py:104`) — so the wiring is not confirmed even within the repo.
**Usable standalone?** Only with the matching trainer. In practice: retrain instead of adopting.
**Pitfalls.** The registry describes `openai_strategy.json` as "the 62-rule postflop strategy playbook"
(`registry.py:112`) — the file actually contains 15 rules under `rules`; the 62 are in
`knowledge_base/exploit/unified.json`. The description is wrong.

### Hand histories — `knowledge_base/hand_histories/`
**Purpose (1 sentence).** 10,000 complete 6-max Pluribus hands with all hole cards as an evaluation and
opponent-model distribution.
**Interface.** `pluribus_hands.jsonl` — each row `{hand, players[6], bb, button, positions{seat:pos},
holes{seat:"TcQc"}, board[], actions[{seat, verb, amount, street}]}`; verbs in PHH style (`f`, `cbr`, …).
`pluribus_stats.json` — aggregated (`hands_catalogued: 10000`, `pluribus_net_bb_per_100: -7.09`, `by_position`
with vpip/pfr/avg_open_bb per position).
**Input/Output.** Read only; consumers `pokerbot/analysis/pluribus_catalog.py`, `benchmark/pluribus_leaks.py`.
**Dependencies.** None.
**Status.** Static.
**Cost.** 9.6 MB.
**Measurement status.** MEASURED as a datum (not as a lever): `pluribus_net_bb_per_100 = -7.09` over the 10,000
catalogued hands (`knowledge_base/hand_histories/pluribus_stats.json`).
**Usable standalone?** Yes — clean, fully revealed 6-max material, good for opponent models and
replay tests.
**Pitfalls.** The amounts are in chips at `bb: 100`; whoever reads them as bb is off by a factor of 100.

### Tournament doctrine — `knowledge_base/tournament/DOKTRIN.md`
**Purpose (1 sentence).** Ten points of ICM/tournament doctrine with exact formulas (Malmuth-Harville, bubble factor,
gap concept, phase curve), as the specification of the tournament modules.
**Interface.** Markdown. Names the implementations: `pokerbot/strategy/icm.py`,
`pokerbot/strategy/tournament.py`, `pokerbot/arena/tourney.py`, tests `tests/test_icm.py`,
`tests/test_tournament.py`.
**Input/Output.** Read only (doctrine, not code).
**Dependencies.** None.
**Status.** Static.
**Cost.** 4.5 KB.
**Measurement status.** MEASURED POSITIVE for the lever built from it: the PROPORTIONAL risk premium
(`BF_eff = 1+(BF−1)·(to_call/Stack)`) measures, per CLAUDE.md (block 2026-08-04), paired at n=1500
**+10.0 ± 5.0 pp ROI, 95% band [+0.2, +19.9]**; the FULL bubble factor was REFUTED in the same experiment
(−8 pp).
**Usable standalone?** Yes as a specification — the formulas are exact enough to reimplement.
**Pitfalls.** Point 7 of the doctrine: heads-up has BF exactly 1.0. Whoever applies the bubble factor in the HU
endgame too bends exactly the part that is already measured.

### Scorecard — `knowledge_base/scorecard.json`
**Purpose (1 sentence).** Frozen result of an old evaluation run (gto_gap / duplicate) with timestamp
and git SHA.
**Interface.** JSON: `{timestamp, git_sha, agent, config:{mode,hands,decks,iters}, axes:{gto_gap:{buckets:
{ALL,OOP:ALL,IP:ALL}}, duplicate:{…}}}`.
**Input/Output.** Generated by `research/bot_audit.py`; listed in `registry.py` under the role `eval`.
**Status.** Static.
**Dependencies.** None.
**Cost.** 2.9 KB.
**Measurement status.** STALE: state `2026-06-15`, `git_sha 53690a7`, agent "PokerBot(exploit=True) -- the unified
MVP". The exploit mode has been measured negative since 2026-09-09 (see Exploit knowledge above) — the numbers
describe a bot that no longer exists.
**Usable standalone?** No, only as a format template.
**Pitfalls.** The file looks like a current state and is not one. The repo has a standing rule for that
(CLAUDE.md: the living truth is in `docs/STATE.md`).

---

# 2. dataset/ — data management

### Data registry — `dataset/registry.py`
**Purpose (1 sentence).** The ONE enumeration of all training/knowledge assets with role, description, schema,
provenance and a `current` flag, so the training pipeline finds data by ROLE instead of by path.
**Interface.**
- `@dataclass(frozen=True) Asset(key, path, role, desc, schema, provenance, stage, current, note)`.
- `ROLES = ("sft_gold","raw_shard","kb_advisor","kb_playbook","kb_ranges","kb_math","model","train_data","eval")`.
- `ASSETS: list[Asset]` — the list itself (currently 30 entries).
- `get(key) -> Asset`; `by_role(role, current_only=True) -> list[Asset]`.
- `sft_gold() -> list[Path]` — only `current` shards that exist on disk.
- `advisor(street) -> Path|None` for `'flop'|'turn'|'river'|'defense'`.
- `model(name) -> Asset`.
- `stats(asset) -> dict` — `{exists, bytes, rows?, action_mix?}`; counts rows only below 64 MB
  (`_ROWCOUNT_MAX_BYTES`), otherwise `rows_uncounted: True`.
- `grep(term, roles=…, limit=20) -> list[{key, line, snippet}]` — content search over all catalogued JSONL.
**Input/Output.** Purely declarative; returns are `Path`/`Asset`/dict.
**Dependencies.** Only `pokerbot.config` (for the root paths). No torch. Easily replaceable.
**Status.** Stateless.
**Cost.** Import is cheap; `stats()` reads the file (seconds for large JSONL).
**Measurement status.** UNMEASURED (infrastructure, not a playing lever).
**Usable standalone?** Yes — the PATTERN is what is worth adopting, not the entries. A file catalogue with
role + `current` flag + an honest note per asset is cheap and prevents exactly the mix-ups documented in the
repo.
**Pitfalls.** The registry only DESCRIBES; it moves/renames nothing (comment `registry.py:14-16`),
and its descriptions can diverge from the content — example `registry.py:112` (see above, "62 rules" for
a 15-rule file). Descriptions are not a contract.

### Example schema + hygiene — `dataset/schema.py`
**Purpose (1 sentence).** Defines the one training record and the three hygiene gates (validity,
domain relevance, dedup/decontam).
**Interface.**
- `make_example(source, spot, completion, action=None, type_="decision", meta=None) -> dict`.
- `is_relevant(text, min_hits=2) -> bool` — regex gate over ~50 poker/math terms.
- `spot_key(spot) -> str` — sha1 over whitespace-/case-normalised spot text.
- `validate(ex) -> bool`; `dedup(examples, decontam_keys=None)` (generator, statistics in `ex_stats[0]`);
  `write_jsonl(path, examples) -> int`.
- `VALID_SOURCES = {pokerbench, ranges, postflop, exploit, math, concepts, distill, selfplay, solver}`.
**Input/Output.** A record = `{"source","type","spot","completion","action":{action,size_bb}|None,
"meta":{}}`; JSONL out.
**Dependencies.** stdlib only.
**Status.** One module-global side channel `ex_stats` (list with one element) — overwritten on every
`dedup()` pass.
**Cost.** Linear in the number of rows.
**Measurement status.** UNMEASURED.
**Usable standalone?** Yes, completely (stdlib).
**Pitfalls.** `ex_stats` is set ONLY at the end of the generator. Whoever consumes `dedup()` only partially or
interleaves two runs reads the statistics of the wrong run.

### Decontamination — `dataset/decontam.py`
**Purpose (1 sentence).** Holds the spot keys of the PokerBench TEST split so that no training example
contains a test spot.
**Interface.** `pokerbench_test_keys(refresh=False) -> set` — reads the cache
`dataset/decontam_keys.json` (484 KB) or rebuilds it via HuggingFace `RZ412/PokerBench` split='test'.
**Input/Output.** Set of sha1 strings, directly passable to `schema.dedup(..., decontam_keys=…)`.
**Dependencies.** `pokerbot.config`, `dataset.schema`; `datasets` (HF) ONLY on refresh — otherwise falls
back silently to an empty set.
**Status.** File cache.
**Cost.** Cache read ~0.5 s.
**Measurement status.** UNMEASURED.
**Usable standalone?** Yes.
**Pitfalls.** Without HF access the function returns an EMPTY set and only prints a
message (`decontam.py:29-31`) — decontamination then silently drops out, and the caller does not notice.

### Data map — `dataset/build_manifest.py` (→ `DATA_CATALOG.md`, `dataset/manifest.json`)
**Purpose (1 sentence).** Renders a never-stale Markdown map plus a machine-readable manifest from the registry,
including an appendix of files not yet catalogued.
**Interface.** `build() -> (markdown, manifest_list)`; `main()`. Invocation:
`python -m dataset.build_manifest`.
**Input/Output.** Reads `dataset.registry` + disk, writes `DATA_CATALOG.md` (git-versioned) and
`dataset/manifest.json` (list of asset dicts with live row counts/sizes).
**Dependencies.** `dataset.registry`, `pokerbot.config`. Hard, but trivially replaceable.
**Status.** Stateless.
**Cost.** Not measured; runs over all JSONL below 64 MB (row counting).
**Measurement status.** UNMEASURED.
**Usable standalone?** Yes, together with the registry.
**Pitfalls.** `DATA_CATALOG.md` is checked in and is NOT regenerated automatically. The current state
dates from 2026-06-20 and diverges from the disk.

### The converters — `dataset/build/`
**Purpose (1 sentence).** Twelve scripts that build uniform DSL training records from the local sources (formulas, playbook,
solver, self-play, blueprint, PokerBench).
**Interface.** Every module exports `build(...)` as a generator over example dicts:
- `from_math.build()` — `knowledge_base/math/math.json` → math problems with an `api.<fn>` call as the solution.
- `from_calc.build(limit=None)` — the two `*_calc_verified.json` → "this engine function exists" examples.
- `from_exploit.build(limit=None)` — `playbook.jsonl` → read→adjustment through the GTO lens.
- `from_pokerbench.build(limit=None, streaming=True)` + `parse_output(out)` — HF PokerBench → `decide(a, size_bb)`.
- `from_selfplay.build(n=800, seed=0, hero_seat=0, profiles=TRAIN_LEAGUE)` — real program loops
  (compute → branch → act), NOT hard-coded `decide()` calls.
- `from_solver.build(boards=None, oop_range, ip_range, …)` + `mass_solve(n, out_path, …)` — TexasSolver mixes
  → `decide_mix({...}, size=)`.
- `from_hu.build_enum()` — drives a HU table to EVERY blueprint node and emits node × hand class.
- `from_hu_postflop.build(n_per_line=400, seed=0)` — HU postflop spots per pot type (limp/SRP/3bet/4bet).
- `run.main(full, pb, decontam)` — the collective run (`python -m dataset.build.run [--full]`).
- `curriculum.build(n_decisions=1500, pb=0, exploit=0, ground=False, seed=0)` — the four ordered shards
  a_contract → b_ground → c_decide → d_exploit.
- `streets.street_of(spot_text)` + `main(test_frac=0.02, seed=0)` — street split + decontaminated test fold.
- `add_made_hand.add_made_hand_line(spot_text)`, `verify()`, `apply_to_gold()` — retroactive insertion of the
  made-hand line, byte-identical to `format_spot` with the flag switched on.
**Input/Output.** In: the knowledge base + the engine. Out: JSONL into `dataset/shards/`.
**Dependencies.** HARD on `pokerbot.brain.format_spot`, `pokerbot.brain.api`, `pokerbot.engine.table`,
`pokerbot.strategy.gto_oracle`, `training.rl_env`. These converters are the part of the catalogue most tightly grown
into the rest of the repo — practically not adoptable in isolation.
**Status.** Stateless per run; `add_made_hand --apply` REWRITES the shards (creates `<shard>.off.bak`).
**Cost.** Not measured except: `from_selfplay` needs one MC-equity call per spot (docstring: "no
rollouts (cheap: one MC-equity per spot)").
**Measurement status.** MEASURED POSITIVE for the FORM of the completion: the "reasoning-loop" form against the
decorative form gave locally `frac_bad` 0.97 → 0.00 (memory entry `reasoning-loop-not-decoration`, repeated in the
module docstring `from_selfplay.py:1-6`). MEASURED NEGATIVE for the data mix:
`shard.solver_mass` was REMOVED from the active gold because 25.6k non-line-aware flop solves drown the 2.2k
teacher examples 13:1 (`registry.py:60-64`).
**Usable standalone?** No. Worth adopting is the principle: one file per source, all with the same
`build()` signature, one global dedup/relevance gate behind them.
**Pitfalls.** All converters write into the same spot format. If you change the format
(e.g. insert a line), all old shards are out of distribution — that is exactly why
`add_made_hand.py` exists, and the corresponding registry entry describes the case as expensive rework.

### The shards — `dataset/shards/`
**Purpose (1 sentence).** The generated training data itself.
**Interface.** JSONL in the `schema.make_example` format. Active per the registry: `a_contract.jsonl` (1,750
rows), `c_decide.jsonl` (3,250), `solver.jsonl` (2,617), `hu_blueprint.jsonl` (12,168),
`claude_study.jsonl`, `teacher.jsonl`. Not active: `solver_mass.jsonl` (25,586), `local_kb.jsonl` (11,599),
`sample.jsonl` (253), `decisions.jsonl` (200), `b_ground.jsonl` and `d_exploit.jsonl` (0 rows).
Row counts from `DATA_CATALOG.md` (state 2026-06-20).
**Input/Output.** Read only, by `training/`.
**Dependencies.** None (data).
**Status.** Static; `.off.bak` files are the pre-made-hand versions.
**Cost.** ~50 MB.
**Measurement status.** MEASURED NEGATIVE for the purpose they were built for: the GLM-Z1-9B brain trained
on them never got past the teacher ceiling per CLAUDE.md; a re-SFT with subsequent GRPO
REGRESSED to −90.18 bb/100 against GTO Wizard. The core lesson is stated there verbatim: "the wins are the WIRING
…, not the weights".
**Usable standalone?** As reading material yes. As training gold only if you build the same DSL and the same engine.
**Pitfalls.** Two shards are empty (0 bytes) and are nevertheless in the catalogue. Check row counts, trust
no file list.

---

# 3. `data/` — the storage conventions

### Run storage — `pokerbot/autogym/runs.py` (+ `data/runs/`)
**Purpose (1 sentence).** A single directory structure for EVERY measurement run, so that every number in the repo has an
address.
**Interface.**
- `neuer_run(name, config) -> Path` — creates `data/runs/<YYYYMMDD_HHMMSS>_<name>/` and writes `config.json`,
  automatically enriched with `commit` (git rev-parse --short HEAD), `host`, `ts`.
- `schliesse_run(d, result) -> None` — writes `result.json` AND appends a row to `data/runs/INDEX.jsonl`.
- `entscheidungs_logger(run_dir, sample=0.03) -> (log_fn, flush_fn)` — collects ALL decisions flagged by the
  oracle plus a 3 % random sample of the unremarkable ones into `decisions.jsonl.gz`.
**Input/Output.** In: two dicts. Out: a folder with `config.json` / `result.json` (in practice also observed
`edges.json`, `log.txt`, `jaeger_einzeln.json`) and a row in `INDEX.jsonl`
(`{run, kandidat, bb100, se, n_decks, workers, sekunden, decks_pro_min, verdict}`).
**Dependencies.** stdlib + `git` in PATH (falls back to `"?"`).
**Status.** One directory per run; `INDEX.jsonl` is append-only, never rewritten.
**Cost.** Negligible.
**Measurement status.** UNMEASURED (infrastructure). The provable benefit: runs whose stdout was lost were
recovered afterwards from these files (CLAUDE.md, GTOW night block: recovery from the HH files after the
cp1252 driver bug).
**Usable standalone?** Yes — 60 lines of stdlib, immediately transferable, and the best single import from this repo.
**Pitfalls.** `neuer_run` uses `mkdir(exist_ok=False)`. Two runs in the same second with the same
name crash. And: the `verdict` in `INDEX.jsonl` is the verdict of the respective gate, not ship proof —
CLAUDE.md explicitly demands three runs for that ("no name without 3 runs").

### Journal — `data/autogym/journal.jsonl`
**Purpose (1 sentence).** The append-only logbook of all verdicts, pre-registrations and findings in prose plus numbers
— the source cited as evidence in the repo.
**Interface.** JSONL, free keys per entry type. Always present: `typ`, `ts`. Frequent: `regel`,
`befund`, `verdict`, `bb100`, `se`, `n`/`n_decks`, `ci95_lo`/`ci95_hi`, `perm_p`, `quelle`, `kandidat`,
`incumbent`. Currently 122 entries, 44 distinct types (among them `L-VORSCHLAG`, `KANDIDAT-GATE`, `R5-GATE`,
`EXPLOIT-JAGD`, `FABLE-DUELL`, `FABLE-RETEST`, `GTOW-NACHT2-CHUNK`, `EXPLOIT-GATE-VERDIKT`,
`KONSULT-SOL-KORREKTUR`).
**Input/Output.** Append only. The reading recipe is in CLAUDE.md:
`python -c "import json; [print(l.strip()) for l in open('data/autogym/journal.jsonl', encoding='utf-8').readlines()[-30:]]"`.
**Dependencies.** None.
**Status.** Append-only across the entire project lifetime.
**Cost.** 63 KB.
**Measurement status.** The journal IS the measurement status of the project. Examples with number and source:
`EXPLOIT-JAGD` (2026-08-17): adaptive +8.87 ± 6.9 at n=100,000 against null control +7.73 ± 8.7;
`FABLE-RETEST` (2026-08-18): harvest 186 → 58 bb/100, open-folds 0/46;
`EXPLOIT-GATE-VERDIKT` (2026-09-09): exploit ON−OFF pooled about −12 bb/100 (SE ~4.5).
**Usable standalone?** Yes, and urgently recommended: a flat JSONL with `typ`/`ts`/`befund`/`verdict` costs
nothing and is the difference between a measured and a narrated project.
**Pitfalls.** The keys are NOT uniform (44 types, 47 distinct keys). Whoever wants to evaluate this
by machine needs separate code per type — it is a logbook, not a table.

### Further `data/` locations (convention)
**Purpose (1 sentence).** Fixed storage locations per tool class, so outputs remain findable.
**Interface.** (Observed convention, not code):
- `data/sessions/` — hand histories. `gtow_hands_<epoch>.jsonl`: each row `{hand_id, aivat, winnings, board,
  street, history[], gtow_folded, players[{position, hole}]}` (65 files). `session_*.jsonl` (6-max trainer,
  218 files): `{hand_no, button, sb, bb, human_seat, positions, hole, board, actions, result, net}`.
  `decisions_*.jsonl` (175 files, `schema: "trainer.decision.v1"`): `{session_id, hand_id, ts, mode, street,
  spot{…}, legal, obs, human_action, oracle, grade, grade_typ, erklaerung_kurz, confidence, spot_fp}`.
  `hu_*.jsonl` — HU-app states.
- `data/freq_targets/` — `gtow_frequencies.json` (366 buckets), `gtow_raise_ranges.json`.
- `data/census/` — `gtow_tree.json` (the measured opponent tree).
- `data/gtow_grades/` — analyzer verdicts (`hu_leaks_ev2.json`, `sixmax_leaks_ev2.json`, `replay_index.json`,
  `LEAK_MAP.md`).
- `data/stress/` — `stress_report.json` + `_worker_<cfg>.json` per configuration.
- `data/research_sweep/` — miner/sweep results (`money_mine.json`, `component_matrix.json`, …).
- `data/runs/STAND.md` — hand-maintained summary of the runs (table + addenda).
**Input/Output.** See per tool below.
**Dependencies.** None.
**Status.** Growing; `data/` is gitignored.
**Cost.** At the time of observation the folder is several GB and contains ~250 loose files in the root
directory next to the structured subfolders.
**Measurement status.** UNMEASURED (convention).
**Usable standalone?** Yes — the convention, not the data.
**Pitfalls.** `data/` is not versioned. Everything in it is exactly as reproducible as the generating
command is documented — and the root of `data/` holds a lot whose producer can no longer be
found.

---

# 4. `research/` — the reusable tools

### LLM helpers — `research/llm.py`
**Purpose (1 sentence).** Encapsulated Claude and OpenAI calls with schema enforcement, prompt caching, retries and a
JSONL checkpoint for resumable runs.
**Interface.**
- `anthropic_client()`, `openai_client()` — lazy singletons.
- `image_block(path) -> dict` — base64 PNG block for vision calls.
- `claude_json(system, content, schema, *, model=None, max_tokens=8000, thinking=False, cache_system=True)
  -> (parsed_dict, (in_tok, out_tok, cache_read_tok))`.
- `ask_claude(system, user, *, model=None, max_tokens=4096, thinking=False, temperature=1.0,
  cache_system=True) -> (text, (in, out, cache_read))` — thinking blocks are DISCARDED, only the visible
  answer is returned; with `thinking=True` or `max_tokens>=16000` it streams.
- `openai_json(system, user, schema, name, *, model=None, max_tokens=12000, images=None)
  -> (parsed, (prompt_tok, completion_tok))`.
- `class Checkpoint(path)` with `has(id)`, `add(id, data)`, `all()`, `close()`.
**Input/Output.** Strings + JSON schema in; parsed dicts or text plus token counters out.
**Dependencies.** `anthropic`, `openai`, `pokerbot.config` (for the keys). The config dependency
is trivially replaceable; the SDKs are not.
**Status.** Two module-global clients; `Checkpoint` holds an open file (don't forget `close()`).
**Cost.** Network-bound. Retry backoff `2**attempt`, capped at 30 s, 6 attempts.
**Measurement status.** UNMEASURED as a tool. The Claude brain built with it is MEASURED: −28.55 AIVAT against
GTO Wizard (CLAUDE.md, brain block) — worse than the pure engine (−20 raw).
**Usable standalone?** Yes, except for the `config` import (2 lines).
**Pitfalls.** With `thinking=True` the API forces `temperature=1` — the passed `temperature` value
is then silently ignored (`llm.py:129-132`). Whoever believes they are measuring temperature variants with thinking
measures nothing.

### CPU mass solver — `research/mass_solve.py`
**Purpose (1 sentence).** Runs TexasSolver over random boards and fills a solver cache, with
RAM-adaptive parallelism.
**Interface.** Command line:
`python -m research.mass_solve [minutes] [max_workers] [threads_per_solve] [min_free_mb] [mb_per_solve]`.
Functions: `free_mb()` (Windows `GlobalMemoryStatusEx`), `fit_workers()`, `solve_one(_)`, `main()`.
Env: `STACKS` (comma list), `DUMP` (1=flop, 2=+turn), `STREET` (3=flop, 5=river subgame), `CACHE_NAME`.
**Input/Output.** Out: one JSON file per board in the cache directory (`data/_gto_bench_cache` among others),
written ATOMICALLY (tmp + `os.replace`), i.e. abort-safe.
**Dependencies.** HARD: `pokerbot.strategy.gto_oracle` (TexasSolver wrapper), `pokerbot.strategy.distill`,
`pokerbot.benchmark.gto_benchmark` (default ranges). Plus the TexasSolver binary under `tools/`.
**Status.** The cache IS the state; already solved boards are skipped (a restart loses nothing).
**Cost.** Documented (docstring): ~400–500 MB per concurrent solve; the defaults keep 1500 MB free
and budget 550 MB per solve. A 24-minute default.
**Measurement status.** MEASURED NEGATIVE for use as training gold: the 25,586 rows generated from it
were excluded from the active SFT gold (`dataset/registry.py:60-64`, "~-47 quality … DROWN the
2.2k Claude-teacher postflop gold 13:1"). As a cache filler UNMEASURED.
**Usable standalone?** Only with the gto_oracle wrapper and the solver binary. The RAM adaptation
(`free_mb`/`fit_workers`), on the other hand, is 15 lines and individually copyable.
**Pitfalls.** `free_mb()` is Windows-specific and falls back to `1e9` on other systems — the
RAM throttle is then silently OFF, and the machine swaps itself to a standstill.

### Money mine — `research/money_mine.py`
**Purpose (1 sentence).** Attributes the AIVAT-weighted P&L of all logged hands to coarse patterns and lists the
biggest burners and printers.
**Interface.** `mine(files) -> dict` (key `"street|terminal_shape|hand_class|pot_bucket"` →
`{aivat_bb, win_bb, n}`), `report(tag, table, top=15)`, `main()`. Helpers: `_hero_hole(h)` (only where
provable), `_terminal_shape(h)`, `_pot_bucket(h, bb)`, `_bb_of(path)`.
Invocation: `python -m research.money_mine`.
**Input/Output.** In: `data/sessions/gtow_hands_*.jsonl`. Out: `data/research_sweep/money_mine.json`
(`{all_files, single_era, era_file}`) + two printed tables.
**Dependencies.** `treys`, `research.freq_mine.hand_class`. The freq_mine dependency is one line.
**Status.** Stateless.
**Cost.** Not measured; two full passes over all session files.
**Measurement status.** MEASURED POSITIVE as a lead generator: the top finding was "flop folds vs SMALL bets (≤0.40
pot): −127.5 bb / 207 folds in the v2.2-era run; vs 0.65+ almost clean (−4.2)" (`docs/STATE.md:777`).
**Usable standalone?** Yes, as soon as your hand logs carry `aivat`, `winnings`, `board`, `history`, `players[].hole`.
**Pitfalls.** The caveat documented in the module itself is the important one (`money_mine.py:11-17`):
AIVAT is unbiased over ALL hands, but the buckets CONDITION (on street, terminal shape) — the
sums mix real EV with baseline residue. Rankings are leads, amounts are soft. Secondly: the
bb size is determined EMPIRICALLY from the smallest non-zero win amount; an older script had 50
hard-wired, which made the first numbers too large by a factor of 2.

### Frequency mine — `research/freq_mine.py`
**Purpose (1 sentence).** Extracts from the logged hands the opponent's (GTO Wizard's) actual action frequencies
per node — free teacher supervision, without a solver.
**Interface.** `board_texture(board) -> str` (`monotone|paired|other|preflop`),
`hand_class(board, hole)` (alias for `pokerbot.engine.evaluator.made_class`),
`walk_decisions(hand) -> (decisions, btn_seat)`, `mine(files) -> dict`, `print_report(r, top_n=20)`,
`save_json(r, files, out_path)`, `main()`.
Invocation: `python -m research.freq_mine [--files GLOB] [--out PATH] [--top N]`.
**Input/Output.** In: `data/sessions/gtow_hands_*.jsonl`. Out:
`data/freq_targets/gtow_frequencies.json` with `{meta, buckets, specials}`. A bucket key is
`street|node-class|pot-type|hand-class|texture`, the value `{n, freq{action:share}, counts, mean_bet_frac,
n_bet_sized, mean_raise_frac, n_raise_sized}`. `specials` contains `facing_2nd_plus_barrel`,
`river_bluff_share`, `river_raises_n`, `flop_checkback_ip`.
**Dependencies.** HARD on `research.gtow_tree_census` (replay, hero-seat identification, pot type) and on
`pokerbot.engine.evaluator`.
**Status.** Stateless, deterministic, read-only.
**Cost.** Not measured (pure log reading).
**Measurement status.** MEASURED POSITIVE as an instrument: 26,823 teacher decisions in 366 buckets from 13,675
hands, 0 replay errors, 99.3 % hero identified, cross-check 11,633/11,633 (`docs/STATE.md:919-921`).
Three robust anchors from it (ibid.): facing the 2nd+ barrel with ONE pair n=241 → call 54 % / fold 43 % /
raise 4 %; river bluff share first-in SRP 28 % at a mean size of 0.81 pot; flop check-back IP consists
63 % of air and only 1.9 % traps. Using these frequencies as a TARGET, however, was measured and REFUTED
(CLAUDE.md: frequency matching refuted 3x).
**Usable standalone?** Only together with `gtow_tree_census.py` and logs in the GTOW format.
**Pitfalls.** The measured frequencies are conditioned on OUR lines (`meta.caveat` in the
output file: "GTOW's HU play conditioned on OUR lines"). It is not solver output but the behaviour
of an opponent against exactly one bot.

### Raise mine — `research/raise_mine.py`
**Purpose (1 sentence).** Decomposes the opponent's raise range by raise-size class and pot type, because the
aggregate polarisation blurs the decisive distinction (normal raise vs jam).
**Interface.** `gtow_raises(hand, gtow) -> list[{street, pot_type, size_cls, board}]`,
`mine(files) -> {composition, stats}`, `main()`. Invocation: `python -m research.raise_mine`.
Constants: `START_STACK=20000`, `JAM_TOL=1.0`, `BIG_RAISE_FRAC=1.5` (raise increment / pot-after-call ≥ 1.5
= "huge").
**Input/Output.** In: the same session logs. Out: `data/freq_targets/gtow_raise_ranges.json` with
`composition["street|pot_type|size_cls"] = {hand_class: count}` and `stats`.
**Dependencies.** `research.freq_mine.hand_class`, `research.gtow_tree_census` (`hero_seat_of`, `replay`).
**Status.** Stateless.
**Cost.** Not measured.
**Measurement status.** MEASURED (descriptive), recomputed from the output file:
`stats = {hands: 17132, raises_tallied: 488, hero_unknown: 118}`. Largest buckets:
`flop|srp|normal` n=213 → 18.8 % nutted / 54.0 % air; `turn|srp|normal` n=73 → 38.4 % / 30.1 %;
`river|srp|normal` n=69 → 59.4 % / 15.9 %. Pooled over all jam buckets (n=29) 62.1 % nutted. The lever
RAISE_NARROW built from this was measured later and, per CLAUDE.md, is only active `resolver-OFF` and is not
part of the final configuration.
**Usable standalone?** Like freq_mine: only with census + matching logs.
**Pitfalls.** 118 of 17,132 hands have no identifiable hero and drop out — and the small
buckets are TINY (`turn|4bet+|jam` n=1). Whoever reads the table without the n column builds on a single
hand.

### Opponent tree census — `research/gtow_tree_census.py`
**Purpose (1 sentence).** Reconstructs the opponent's empirical bet-size tree from the logged action tokens
and measures how much of OUR OWN play lies outside that tree.
**Interface.** `replay(hand)`, `hero_seat_of(hand, net, folder) -> int|None`, `pot_type_of(pf_raises)`,
`bucket(x)`, `census(files, hero_files) -> dict`, `grid_from(counter, min_share=0.05)`,
`off_grid_share(counter, grid, tol=0.075)`, `main()`.
Constants: `BB=100.0`, `SB=50.0`, `GRID=[0.33, 0.5, 0.75, 1.0, 1.25]`.
Invocation: `python -m research.gtow_tree_census [--files GLOB] [--hero-files GLOB]`.
**Input/Output.** In: session logs. Out: `data/census/gtow_tree.json` + printed summary.
**Dependencies.** `pokerbot.engine.evaluator`. Otherwise stdlib.
**Status.** Stateless, deterministic.
**Cost.** Not measured.
**Measurement status.** MEASURED as the basis of the tree adaptation: per CLAUDE.md the 12.5k-hand census
`data/census/gtow_tree.json` was produced from it. The attack derived from it ("off-tree sizings") is MEASURED
and REFUTED (memory `beat-gtow-refuted`, CLAUDE.md: 13.5k hands, "off-tree earned 0"; the opponent is a
real-time re-solver without a translation boundary).
**Usable standalone?** Yes, if your logs use the token format `bX` (cumulative per round) and `_` (end of street).
**Pitfalls.** The token semantics are duplicated in THREE places (`gtow_tree_census.replay`,
`freq_mine.walk_decisions`, `raise_mine.gtow_raises`). Whoever changes one of them gets silently diverging
numbers from two miners.

### Stress suite — `research/stress_suite.py`
**Purpose (1 sentence).** 70 hand-built catastrophe spots in which it is measured whether a configuration
commits IRRESPONSIBLY (>30 % of the remaining stack with too weak a hand) or tips into the opposite (folds nuts/traps).
**Interface.** Command line `PYTHONUTF8=1 python -m research.stress_suite`. Internally:
`class HU` (spot construction), scenario kit (`srp_turn_barrel`, `srp_river_barrel`,
`threebet_river_jam`, `counterfeit_river`, `checkraise_after_cbet`, `five_bet_jam`, `junk_vs_4bet`,
`river_first_in`, `trap_line`), `build_spots() -> list[dict]`, `classify(sp, action, amount)`,
`run_worker(cfg, only)`, `run_orchestrator(configs, only)`, `main()`.
Constants: `SEED=42`, `START_STACK=20000`, `STACKOFF_FRAC=0.30`, `SIZE_CAP_X_POT=1.5`,
`WORKER_TIMEOUT_S=780`.
**Input/Output.** In: a list of configuration names (`CONFIGS` maps names → env dict). Out:
`data/stress/stress_report.json` (`{meta, fingerprints, summary, spots, matrix}`; `summary[cfg] =
{irresponsible, over_nit, errors, irresponsible_spots[], over_nit_spots[], error_spots[]}`) plus
`_worker_<cfg>.json`.
**Dependencies.** HARD on `pokerbot.strategy.bot.PokerBot` and the HU engine. Every configuration runs in
its own SUBPROCESS, because the env flags are read at import.
**Status.** Fresh `PokerBot(0, seed=42)` per spot — mixed nodes are drawn ONCE; that is a
deterministic draw, not a frequency estimate (stated as such in `meta.note` of the output file).
**Cost.** Budgeted at under 15 minutes per configuration (`WORKER_TIMEOUT_S=780`).
**Measurement status.** MEASURED POSITIVE as a gate with a concrete catch: the suite found the "eCall OVER-JAM"
live (3.4x-pot all-in, insensitive to hand strength), which another channel had previously REWARDED
(`docs/STATE.md:906-910`). In the later run the number of irresponsible spots fell from 20 to 13 at 0
over-nit (`docs/STATE.md:911-913`). The most recently stored report reports for `prince`
`irresponsible: 18, over_nit: 0, errors: 0` (`data/stress/stress_report.json`, state 2026-07-06 04:16).
**Usable standalone?** The PRINCIPLE yes (constructed spots + two symmetric error classes), the code no —
it knows the internal HU interface.
**Pitfalls.** Both resolvers are forcibly switched off (`BASE_ENV`). So the suite says NOTHING
about behaviour with the re-solver switched on — and that is exactly the production configuration.

### Graded replay — `research/replay_graded.py`
**Purpose (1 sentence).** Deterministically replays the catastrophe hands graded by the external analyzer and
re-queries the CURRENT configuration at every graded decision point — a minutes-long gate instead of a
noisy live run.
**Interface.** `python -m research.replay_graded --config head|gto|prince`. Internally:
`chunk_cards(s)`, `parse_street_tokens(spec)`, `hero_decisions(row)`, `deal_hand(g, stack)`,
`row_matches_deal(row, hole, pos, full_board)`, `scan_matches(px, rows)`, `load_cache/save_cache`,
`replay_hand(px, g, idx)`, `compare(decisions, taken)`, `print_report(...)`, `main()`.
Constants: `EXPORT_SEED=55`, `EXPORT_N=1500`, `GRADES_PATH="data/gtow_grades/hu_leaks_ev2.json"`,
`CACHE_PATH="data/gtow_grades/replay_index.json"`, `BAD_GRADES={BLUNDER, WRONG_MOVE, MISTAKE}`,
`GOOD_GRADES={BEST_MOVE, CORRECT_MOVE}`, `SIZE_TOLERANCE_BB=0.011`.
**Input/Output.** In: the graded rows (action tokens like `X:BEST_MOVE B F:BLUNDER`). Out: report
with `n_now_different` (healed blunders) and `n_regressions_on_correct` (the regression signal).
**Dependencies.** HARD on the HU engine and on a deterministic export run. All
pokerbot imports happen ONLY in `main()`, after the env flags are set.
**Status.** A file cache of the deal index (configuration-independent).
**Cost.** "minutes-long" per the docstring; not measured more precisely.
**Measurement status.** MEASURED POSITIVE as a gate: in the v2.3.1 round "replay 16-flips/7-clean best-yet"
(`docs/STATE.md:903`).
**Usable standalone?** No — it presupposes the complete determinism chain (deck shuffled once per hand,
decider seeded per hand).
**Pitfalls.** Comparisons AFTER a hero deviation are marked as TAINTED: from there on the opponent sees a
different state, the later graded points are no longer the same spots. Whoever averages the hit rate over
all points instead of only the clean ones measures nonsense.

### LLM adversary — `research/fable_duell.py`
**Purpose (1 sentence).** Lets a language model (or a human) play HU against the full bot stack by keeping
state as an action log on disk and deterministically replaying the match on every call.
**Interface.**
`python -m research.fable_duell --neu` (reset session)
`python -m research.fable_duell --akt call` (or `fold|check|call|allin|bet:300|raise:600`).
Internally: `_spiel(bis_aktion) -> (game, bot_decide, log, netto, hand_i)`, `_zeig(g, netto, hand_i)`, `main()`.
**Input/Output.** In: an action as a string. Out: one JSON line on stdout with
`{hand_nr, score_agent_bb, street, deine_karten, board, pot, to_call, dein_stack, bot_stack, du_bist_button,
legal{check,call,raise_min,raise_max}, history_der_hand}`. State: `data/runs/fable_duell/aktionen.json`.
**Dependencies.** HARD on `pokerbot.autogym.pargate._baue_fabrik`, `pokerbot.benchmark.duplicate`,
`pokerbot.engine.game.HeadsUpGame`. Env defaults are set in the module header
(`POKERB_TURN_DEFENSE=0.07`, `POKERB_SLOWPLAY=0.25`, `POKERB_RAISE_NARROW=1.0`); the bot stack is selectable via
`FABLE_STACK` (default `turn_wert`).
**Status.** File-based, complete; every call rebuilds everything (`N_DECKS=200`, deck seed 4242,
game seed 0) — the agent always sits in seat 0.
**Cost.** The replay grows LINEARLY with the number of actions so far; not measured, but the cost
per move rises over a session.
**Measurement status.** MEASURED POSITIVE as a diagnostic instrument, with explicit anecdote labelling.
Journal `FABLE-DUELL` (2026-08-17): "62 hands, +115.5bb (anecdote)" — the value of this run was the
COUNTED patterns: button open-fold ~29 %, check-raise without follow-through 3/3, river station 4/5 big calls
with losers (~90 bb), capped check range. Journal `FABLE-RETEST` (2026-08-18) against the hardened
stack: "harvest 186 → 58 bb/100", open-folds 0/46, verdict "HARDENING PROVEN".
**Usable standalone?** No (engine-bound). The pattern — file-based state + deterministic
replay instead of a running process — is on the other hand very transferable and is what makes an LLM opponent
usable in the first place.
**Pitfalls.** 62 or 92 hands are statistically nothing. The repo turned this into an explicit doctrine
(STAND.md, addendum 2026-08-18): the mirror channel is a NON-REGRESSION bound, the
adversary is the EFFECT proof — two instruments, two questions, no number from one in the other.

### Exploit hunt — `pokerbot/autogym/exploit_jagd.py`
**Purpose (1 sentence).** 20 independent, PERSISTENT exploit bots hunt the frozen base bot in parallel to
produce a hardening map (diagnosis, not victory).
**Interface.** `python -m pokerbot.autogym.exploit_jagd --haende 100000 --workers 20`.
Internally: `_jagd((seed, n_hands)) -> ledger_dict`, `main()`.
**Input/Output.** Out: a run folder (via `runs.neuer_run`/`schliesse_run`) with aggregated result
(`haende, jaeger_bb100, se_ueber_jaeger, jaeger_positiv, sd_netto_bb100, nsd_netto_bb100, fold_ernte{preflop,
flop,turn,river}, showdown{gewonnen,verloren,split}, sekunden`) and `jaeger_einzeln.json` per hunter.
**Dependencies.** HARD on `pokerbot.engine.game.HeadsUpGame`, `pokerbot.strategy.bot.PokerBot`,
`pokerbot.autogym.runs`. Sets `torch.set_num_threads(1)` and `botmod.EQUITY_ITERS = 120` per worker.
**Status.** The HUNTER is persistent over all its hands (its Dirichlet opponent model accumulates) —
exactly what the normal gate harness prevents with fresh bots per deck. The DEFENDER is fresh per hand.
When adopting, that is the central design decision.
**Cost.** Multiprocessing, one fleet; CLAUDE.md warns explicitly: "one worker fleet at a time (RAM)".
**Measurement status.** MEASURED NEUTRAL for the adaptation gain, POSITIVE as a map. Journal `EXPLOIT-JAGD`
(2026-08-17, n=100,000): adaptive +8.87 ± 6.9 (14/20 hunters positive) against null control +7.73 ± 8.7 → the
adaptation GAIN is ~+1 and not significant. What was usable was the other thing: the win channel shifts
hard (showdown +5.8 → +19.9; non-showdown +1.9 → −11.0) and ALL 20 hunters converge independently on
the same defender profile (VPIP 0.75–0.77, fold_to_bet 0.29–0.31, aggression 0.31–0.34). Two
catastrophe hunters (−69/−47) show the tail risk of generic adaptation. Core lesson in the entry: the targeted
structural exploit (+6.1) clearly beats the generic Dirichlet adaptation (~+1).
**Usable standalone?** Only with a HU engine and an adaptive bot. What is transferable is the design: N independent
hunters with different seeds, a frozen defender, and the CONVERGENCE of the opponent models as the result
instead of the bb number.
**Pitfalls.** The module does NOT live in `research/` but in `pokerbot/autogym/`. And: the 20 hunters
are not 20 independent samples of the same size as 20 independent runs — the SE is formed over the
hunters, not over the hands, which is correct here but easy to confuse.

### Vision regression net — `research/snowie_regress.py`
**Purpose (1 sentence).** Preserves screen stills with expected values and, after every change to the
screen reader, checks ALL of them at once.
**Interface.**
`python -m research.snowie_regress --add "pot=4,hero=218,cards=2h7c"` (save the current frame with expected values)
`python -m research.snowie_regress --run` (check all cases).
Internally: `_cases() -> list[dict]`, `add(spec)`, `check(case) -> list[str]` (empty list = passed),
`run() -> int` (number of failures), `main()`.
Checkable keys: `cards`, `board`, `pot`, `hero`, `call`, `pos`, `gate`.
**Input/Output.** Storage `data/vision/snowie/regress/` with `case_NNN.png` and `cases.json`
(`[{file, want:{…}}]`).
**Dependencies.** `PIL`, `pokerbot.vision.snowie_local` (screenshot), `pokerbot.vision.snowie_state`
(state reading + gates). `--add` needs the running target program on screen; `--run` does not.
**Status.** The case collection on disk grows.
**Cost.** Not measured (template matching per image).
**Measurement status.** UNMEASURED as a number. The motivating finding is in the docstring and is itself a measurement
(`snowie_regress.py:3-6`): three corrections of that session were verified on ONE still and
"three times that turned out to be a fallacy — one fix repaired one field and destroyed another".
CLAUDE.md calls the resulting net the "5-case regression net".
**Usable standalone?** Yes, if you have a screen reader with a `read_state(img) -> dict` function —
the pattern is 90 lines and universal.
**Pitfalls.** The numeric check in `check()` is improvised: it compares strings with a
float special case inside a nested conditional expression (`snowie_regress.py:57-62`). Expected
values with signs or thousands separators silently fail.

### Deep replay — `research/tiefen_replay.py`
**Purpose (1 sentence).** Re-solves every hero river decision of real live hands in three configurations and
categorises where EV was lost AND where EV was left on the table.
**Interface.** `POKERB_TRACKER_ALPHA=0.5 POKERB_TRACKER_CONF_SLOPE=0.7 python -m research.tiefen_replay`.
Internally: `extrahiere(arm, dateien)`, `_spots(eintraege, preflop_ranges)`, `kategorisiere(res, e)`, `main()`.
The three configurations: A) 600 iterations with tracker ranges (reference), B) 150 iterations with
tracker ranges (production budget → flip rate = noise), C) 600 iterations with PREFLOP ranges
(null hypothesis: is the postflop Bayes value or harm?).
**Input/Output.** In: the logged hands of the live arms. Out:
`data/runs/tiefen_replay_<ts>.jsonl` (one row per decision, all intermediate values) plus an aggregated
console report. Categories: `VERLUST_CALL`, `VERLUST_AGGRO`, `OVERFOLD`, `VERPASST_VALUE`, `VERPASST_BLUFF`,
`SIZE`, `OK` (threshold `INDIFF_BB = 0.25`).
**Dependencies.** HARD on `pokerbot.strategy.gpu_resolver` (RiverCFRBatch), `range_tracker`,
`research.gtow_tree_census`, `research.hh_luecken_mine`, `research.river_bill_replay`. Needs the GPU paths.
**Status.** Stateless, deterministic per the docstring.
**Cost.** "$0, deterministic, GPU-batched"; no runtime documented in the repo.
**Measurement status.** UNMEASURED as a lever (it is a diagnostic instrument). The corresponding live measurement
is in CLAUDE.md: 81 % of the loss of the first GTOW night was on the river, in the old jam-spew/station pattern.
**Usable standalone?** No — it needs the GPU resolver, the range tracker and logs in the in-house format.
**Pitfalls.** The three arms deliver EV values FROM DIFFERENT TREES. The project's hybrid doctrine
explicitly forbids the naive comparison for that (CLAUDE.md, rule 6: "compare EVs only at equal meaning
— no max over solver EVs of different games"). Only EV DIFFERENCES within ONE arm are
meaningful; the module docstring says the same.

### External consult — `research/konsult_sol.py`
**Purpose (1 sentence).** Sends a project briefing with a fixed, very strict role and question prompt to
a strong external model and stores answer plus raw answer.
**Interface.** `python -m research.konsult_sol --briefing <path.md> --out <file.md>
[--modell gpt-5.6-sol] [--effort high] [--max-tokens 40000]`. Internally: `schluessel()`, `main()`.
Module constants: `MODELL`, `SCHLUESSEL_DATEI` (path to the key file), `ROLLE` (the system prompt),
`FRAGEN` (the question catalogue).
**Input/Output.** In: a Markdown file with the project state. Out: the answer as `.md` and the
complete raw answer as `<out>.raw.json`, plus token counters on stdout.
**Dependencies.** `openai` (Responses API with `reasoning={"effort": …}`). No pokerbot import — this
script is free-standing.
**Status.** Stateless.
**Cost.** Network-bound; `max_output_tokens` 40,000 by default.
**Measurement status.** MEASURED POSITIVE in one concrete case: the consult corrected three documentation facts, one
of them confirmed against the code (journal `KONSULT-SOL-KORREKTUR`, 2026-09-10): the competition runs at 200 bb
(`gtowizard.py:98`, `:281`), our preflop blueprint fires only from 140 bb effective (`bot.py:200`) — so the
100-bb measurement channel measured a DIFFERENT bot. Verdict in the entry: "CORRECTION (docs wrong, now fixed)".
**Usable standalone?** Yes, completely — it is a single script without repo dependency.
**Pitfalls.** The VALUE lies in the `ROLLE` prompt, not in the script: it demands the separation of "what I
know / what I suspect / what must be measured", for every recommendation the cheapest refuting test,
and explicitly "Invent NO numbers about the project". Without these clauses you get plausible inventions
back. The key path is absolute and Windows-specifically hard-coded (`konsult_sol.py:16`).

### Golden set / divergence smoke — `research/golden_set.py`
**Purpose (1 sentence).** Proves byte-identity of a reference policy BEFORE and AFTER an infrastructure change
and counts divergence decks between two states.
**Interface.**
`python -m research.golden_set --a <stack> --b <stack> --decks 40 --seed 424242 --out <file.json>`
`python -m research.golden_set --vergleich <before.json> <after.json>`.
Internally: `_lauf(a, b, decks, seed) -> dict`, `main()`.
**Input/Output.** Out: JSON with the per-deck edges.
**Dependencies.** `pokerbot.autogym.pargate._baue_fabrik`, `pokerbot.benchmark.duplicate`.
**Status.** Stateless; clears ALL `POKERB_*` environment variables and pins BLAS/torch to one thread —
the gate channel is flag-free (pargate convention).
**Cost.** Not measured.
**Measurement status.** UNMEASURED as a number; it is an identity gate (success = "exactly equal").
**Usable standalone?** No (pargate-bound).
**Pitfalls.** Precisely the env/thread hygiene is the point: CLAUDE.md documents that set iteration and
`PYTHONHASHSEED` used to add jitter to every "deterministic" run. A byte-identity gate
without this hygiene proves nothing.

### Export in gate configuration — `research/snowie_export.py`
**Purpose (1 sentence).** Exports hands in EXACTLY the same bot configuration in which the gate measured —
so that export and gate describe the same bot.
**Interface.** `python -m research.snowie_export --hero turn_wert --n 400 --out <path>`. Internally:
`_hero(variante, idx)`, `main()`.
**Input/Output.** `--hero` takes a pargate CANDIDATE name; the guard chain comes from the one source
`pargate._wickle`. Out: hand-history file plus a sidecar with the run fingerprint.
**Dependencies.** `pokerbot.autogym.pargate`, the HU engine.
**Status.** Env flags are set by the SHELL and read at import.
**Cost.** Not measured.
**Measurement status.** UNMEASURED as a lever. The docstring documents a fixed bug of this class
(`snowie_export.py:6-9`): previously the script built locally a different guard stack than the gate, although the
docstring promised gate parity.
**Usable standalone?** No.
**Pitfalls.** This is the general pitfall of the whole measurement system: exporter and gate MUST use the same
bot construction, otherwise you compare two bots and call it a measurement.

### Extraction pipeline — `research/extract_text.py`, `chunk.py`, `extract_math.py`, `extract_concepts.py`, `extract_book.py`, `extract_ranges_vision.py`, `exploit_playbook.py`
**Purpose (1 sentence).** The chain that produced the entire `knowledge_base/` from PDF books.
**Interface.** In order:
1. `extract_text.extract_book_text(book_key) -> list[dict]` + `is_range_page(text)` — PDF → `data/text/<book>.jsonl`
   (per page `{book, page, text, n_chars, n_images}`) and rendered range-chart PNGs.
2. `chunk.chunk_book(book_key, target_tokens=6000)` + `ntok(s)` — greedily pack pages into token-bounded chunks
   → `data/chunks/all_chunks.jsonl`.
3. `extract_math`: `load_pages()`, `gather_passages(pages, keywords, max_chars=16000)`,
   `verify(fn_code, call_expr) -> (ok, msg)` — asks the model for formula + Python + example and EXECUTES the
   function; output `knowledge_base/math/math.jsonl` → `math.json` + `formulas.py`.
4. `extract_concepts.main()` — chunks → `knowledge_base/concepts/concepts.jsonl`.
5. `extract_book.extract(pdf, out, focus, model)` — focused extraction from large books; chunks without
   hits return `[]`, so irrelevant chapters stay cheap.
6. `extract_ranges_vision.render(book_key, page_index, dpi=200)` + `main()` — 13×13 range grids via vision.
7. `exploit_playbook`: `_profile(vpip, fcb, three, agg)`, `_cells()`, `_work(cell)` — grid of
   opponent profiles × contexts, highly parallel → `knowledge_base/exploit/playbook.jsonl`.
**Input/Output.** PDF in, JSON/JSONL out. All runs are resumable via `research.llm.Checkpoint`.
**Dependencies.** `research.llm` (and thus the API keys), `pokerbot.config` (paths), a PDF reader,
`tiktoken` for the chunk size.
**Status.** Checkpoint files; an aborted run resumes.
**Cost.** Network-/API-bound. `exploit_playbook` runs by default with 40 concurrent calls and is
explicitly built to run alongside local CPU load.
**Measurement status.** UNMEASURED as an EV contribution. The only built-in truth test is `extract_math.verify()`
(the generated function must be executable and deliver the claimed result) — that checks consistency,
not correctness.
**Usable standalone?** Yes, with your own books and your own API keys; only `pokerbot.config` has to be
replaced.
**Pitfalls.** The module docstrings all say `python -m extraction.<name>` — the directory has been called
`research/` since a rename. Every command in these docstrings is wrong; correct is
`python -m research.<name>`.
### Formula regression net — `pokerbot/autogym/verify_refs.py`
**Purpose (1 sentence).** Runs every stored verification expression of the calc JSONs against the formula modules
that sit in the repo TODAY and reports drift.
**Interface.** `python -m pokerbot.autogym.verify_refs`. Internally: `main()`;
`QUELLEN = [("knowledge_base/math/postflop_calc_verified.json", postflop_formulas),
("knowledge_base/math/strategy_calc_verified.json", strategy_formulas)]`, `TOL = 1e-9`.
**Input/Output.** In: the two `*_verified.json`. Out: counters passed/missing/total on stdout.
**Dependencies.** `knowledge_base.math.postflop_formulas`, `knowledge_base.math.strategy_formulas`.
**Status.** Stateless.
**Cost.** Seconds (66 function calls).
**Measurement status.** MEASURED as consistency: 66/66 per CLAUDE.md (AUTOGYM block, "verify_refs (66/66)").
**Usable standalone?** Yes, if your formulas have the same format with `verify_expr`/`verify_value`.
**Pitfalls.** The honesty clause is in the module itself (`verify_refs.py:5-9`): `verify_expr` comes
from the SAME generation as the formula. It is a drift net, not a proof of correctness; the
truth tier is the nine independent `Fraction` references in `selftest.E1`.

---

## What an outsider should take from this subsystem

Directly adoptable (no or trivial dependencies): `knowledge_base/math/formulas.py` and the two
`*_calc_verified.json` (formulas incl. self-test), `knowledge_base/ranges/preflop_blueprint.json` and
`cfr/preflop_pushfold.json` (finished preflop mixes), `knowledge_base/hand_histories/pluribus_hands.jsonl`
(10,000 revealed 6-max hands), `pokerbot/autogym/runs.py` (run storage), `dataset/schema.py`,
`research/konsult_sol.py` and the patterns of `snowie_regress.py` and `fable_duell.py`.

Do not adopt without your own measurement: the exploit playbook (the mechanism hanging off it is measured
negative), the frequency targets as a target (frequency matching is refuted three times), the advisor `.pt`
(feature-coupled), the concept/theory prose (never checked against bb/100).

---

## Addendum — further modules

This part adds the modules that have no entry in parts 01–12. Families of nearly
identical scripts (consults, pod probes, ecology parsers) appear as a GROUP entry in the same format —
every path is named, the interface per file. At the end: the corrections to the existing parts and
the table of deliberately omitted files.

---

## A — `pokerbot/`

### Central configuration — `pokerbot/config.py`
**Purpose.** One module holds all project paths, model IDs and the API-key resolution; every other module
in the repo imports paths from here instead of building them itself.
**Interface.** No functions except `pdf_path(book_key: str) -> Path` (path to one of the three
registered books). Everything else is module constants: `ROOT`, `DATA_DIR`, `KNOWLEDGE_DIR`, `RANGES_DIR`,
`MATH_DIR`, `POSTFLOP_DIR`, `DATASET_DIR`, `SHARDS_DIR`, `MODELS_DIR`, `TEXT_DIR`, `CHUNK_DIR`,
`PAGE_IMAGE_DIR`, `CONCEPTS_DIR`; keys `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GTOWIZARD_API_KEY`;
models `CLAUDE_MODEL` (default `claude-opus-4-8`), `CLAUDE_HAIKU_MODEL`, `OPENAI_MODEL` (None = runtime
resolution), `OPENAI_MODEL_PREFERENCE` (list, best first); books `BOOKS`, `BOOK_TITLES`.
**Input/Output.** Input: environment variables (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GTOWIZARD_API_KEY`,
`CLAUDE_MODEL`, `OPENAI_MODEL`) and three key files under `C:\Users\hampe\Desktop\Secret keys\`.
Output: `Path` objects and `str | None` keys. **Side effect on import:** the loop
`config.py:31-33` creates twelve directories via `mkdir(parents=True, exist_ok=True)`.
**Dependencies.** Standard library only (`os`, `pathlib`). Hardest dependency in the other
direction: the catalogue cites `config` 31 times as a dependency of other modules.
**Status.** Stateless, but the keys are read ONCE at import — an environment value set later
has no effect.
**Cost.** Three file reads plus twelve `mkdir` at import; not measured.
**Measurement status.** UNMEASURED (infrastructure, no EV effect).
**Usable standalone?** Yes, but for an outsider it is more a template than a building block: the
key paths are wired absolutely to the author's machine (`config.py:36-38`, `config.py:56`).
Minimal: replace the three `_SECRET_DIR` lines with your own paths or set all keys via environment
variable — then the module runs unchanged.
**Pitfalls.** `_read_key()` catches `OSError` and returns `None` — a wrong path produces NO
error message but a silent `None` key; the comments at `_GTOW_KEY_FILE` document
exactly this case (a moved key silently fell back to the environment variable, which a
PC restart then lost).

### Near-GTO sparring partner — `pokerbot/strategy/gto_baseline.py`
**Purpose.** A deliberately HARD-TO-EXPLOIT (not exploiting) heads-up opponent built from Chen formulas,
MDF defence and texture-conditioned c-betting — the default villain in all paired measurement channels.
**Interface.** `GTOBaseline(hero=0, seed=0, iters=300, params=None)` — constructor;
`decide(state) -> (action, amount)` the only load-bearing method (`action` in fold/check/call/bet/raise,
`amount` in chips or `None`); `observe_opponent(*a, **k)` and `observe_hand_end(*a, **k)` are deliberate
no-op hooks so the class can be dropped without adjustment into hero loops that expect an adaptive bot.
`main()` plays it live against Slumbot (`--hands`, `--iters`).
**Input/Output.** Input = the engine `state` dict with the load-bearing keys `legal`
(`pot`, `to_call`, `can_check`, `can_raise`, `is_bet`, `raise_min`, `raise_max`), `players[i]`
(`hole`, `committed_street`), `board`, `street`, `bb`, `current_bet`, optionally `aggressor`, `button`,
`history`. Output = the tuple `(action, amount)`.
**Dependencies.** Hard: `engine.cards.hand_class`, `engine.equity.equity_vs_class_range`,
`engine.evaluator.best_five_name`, `strategy.preflop_strength`, `strategy.postflop.cbet_policy` +
`classify_board`. Replaceable: `benchmark.slumbot` (only in `main()`).
**Status.** One `random.Random(seed)` per instance — i.e. STATEFUL across the session: the same
instance does not necessarily return the same action for the same spot. For paired measurements each arm
must be constructed ANEW with the same `seed`. No hand/session memory beyond that.
**Cost.** Postflop, one Monte-Carlo equity with `iters` passes per decision (default 300;
`benchmark/duplicate.py:108` constructs it with `iters=120`). Absolute cost not measured.
**Measurement status.** MEASURED POSITIVE as a calibration of two parameters: `cbet_eq` and `donk_eq` are
solver-calibrated, c-bet frequency lowered from 93% to 80% (GTO ~75%), holdout loss 0.62 -> 0.50
(source: comment `pokerbot/strategy/gto_baseline.py:29-31`, produced by `benchmark/calibrate.py`;
the same number in `docs/STATE.md:1742-1743`). The docstring cites as motive a superseded baseline at
−207 bb/100 against Slumbot (`gto_baseline.py:3`) — that is the number of the PREDECESSOR, not of this class.
A bb/100 value of this class itself is NOT documented in the repo: UNMEASURED as absolute playing strength.
**Usable standalone?** Yes, and that is its main value. Minimally required: the `engine/` package (cards, evaluator,
equity) plus `strategy/preflop_strength.py` and `strategy/postflop.py`. The rest of the strategy layer
(advisors, tracker, resolver, guards) is NOT needed.
**Pitfalls.** Initiative. The calibrated c-bet branch fires only if `state["aggressor"]` is set
or derivable from `state["history"]` (`gto_baseline.py:105-115`). If both are missing, the class
silently falls into the generic equity-threshold branch — exactly this case is commented in the code as an earlier bug
("without this the calibrated c-bet branch below was dead in real play"). Whoever hangs the class into
their own engine must supply `history` entries with `action` and a `"deal"` marker.

### Leduc value net + depth-limited re-solving (gate 0) — `pokerbot/valuenet/gate0_leduc.py`
**Purpose.** The complete DeepStack machinery (CFV labels -> value net -> trunk re-solving with
CFR-D gadget) on Leduc Hold'em, where exploitability is EXACTLY computable — the preliminary gate before
the same construction is let loose on No-Limit Hold'em.
**Interface.** Phase 1 (labels): `solve_subgame(pub, pot_half, r0, r1, iters, hist="") -> (policy, Z)`,
`subgame_cfvs(pub, pot_half, r0, r1, iters)`, `generate_labels(n_situations, label_iters, workers)`,
`label_stability_probe(n_probe, iters_lo=500, iters_hi=1000)`. Phase 2 (net): `class CFVNet(nn.Module)`
with built-in zero-sum correction in `forward`, `train_net(x, y)`. Phase 3 (re-solving):
`class TrunkResolver(leaf_fn, hero=None)` with `run(iters)`, `policy()`, `opponent_constraints()`;
`gadget_resolve(leaf_fn, trunk_iters, fill_iters)`, `resolve_subgame_gadget(...)`, `gadget_fill(...)`,
`harvest_query_beliefs(trunk_pols)`, `generate_boot_labels(...)`. Phase 4 (gate): `full_solve(iters)`,
`exact_constraints(pol_full)`, `main()`.
**Input/Output.** Input: nothing from outside — the situations are sampled (`_situation`,
`_sample_belief`). Intermediate format: NumPy arrays `x` (features: public one-hot, pot, both
belief vectors) and `y` (pot-normalised CFVs per rank, both players); intermediate storage
`data/research_sweep/gate0_leduc_labels.npz` and `..._boot.npz`. Output:
`data/research_sweep/gate0_leduc.json` with the load-bearing keys `config`, `label_stability`, `labels`,
`net` (`mae_train_pot`, `mae_holdout_pot`), `resolve` (incl. `residual_decomposition_mbb`), `gate`
(`pass`, `delta_mbb`, `full_solve_mbb_per_hand`, `net_resolved_mbb_per_hand`, `trunk_policy_table`).
**Dependencies.** Hard: `pokerbot.strategy.deep_cfr` (supplies `State`, `vanilla_cfr`, `exploitability`,
`key`, `regret_match`, `root_states`, `NACT`, `_avg`) — without this module nothing runs at all; `numpy`,
`torch`. Replaceable: nothing. The module does NOT touch the production bot.
**Status.** Per run. Persisted phase by phase: labels and results are written to disk and reused on the
next start — whoever changes a constant must delete `data/research_sweep/gate0_leduc*.npz`,
otherwise the next phase keeps computing on old labels.
**Cost.** From the result JSON of the same run: label generation 4,500 subgames in 186.7 s on twelve
processes (`labels.seconds`), net training 5.7 s (`net.seconds`). The docstring cites for the whole
pass "< 30 min CPU", `--quick` ~1 min (`gate0_leduc.py:38-39`).
**Measurement status.** REFUTED — the gate FAILED. `data/research_sweep/gate0_leduc.json`:
`gate.pass = false`, `gate.delta_mbb = 90.89` against a pre-registered bar of 10.0 mbb/hand
(`gate.bar`); full solve 10.02 mbb/hand, net-based re-solving 100.91 mbb/hand. The NET itself is
not the problem in the narrow sense (holdout MAE 0.0604 pot fractions); the decomposition attributes 69.64 mbb
to the net error at the trunk beliefs and 21.25 mbb to the construction itself. Positive partial findings:
the gadget recovered 106.05 mbb (oracle trunk) and 26.94 mbb (fill) relative to the predecessor
iteration (`resolve.residual_decomposition_mbb`). Prehistory in `../plans/VALUE_NET_PLAN.md:52-79`:
gate 0a validated, gate 0b PASSED (val MAE 0.191 = 6.4% of the CFV scale), gate 0c diagnosed as a
spurious equilibrium of the depth-limited construction.
**Usable standalone?** Yes, as a self-contained research package — but only together with
`pokerbot/strategy/deep_cfr.py`. The two together are a complete, exactly evaluable Leduc test bench;
that is the most honest place to test your own re-solving ideas before spending money on GPUs.
**Pitfalls.** The CFV convention. The docstring (`gate0_leduc.py:32-36`) warns explicitly: labels and
trunk leaf MUST use the same normalisation (`CFV0[a] = sum_b r1[b]*mult(a,b|pub)*u0*(a,b)/Z`), otherwise
the re-solving is SILENTLY wrong — no error, just bad numbers. Second stumbling block: the
`BELIEF_FLOOR = 0.01` applies ONLY to net queries; the exact fill solves use `FILL_BELIEF_FLOOR =
1e-6`, because 0.01 injects about 2% phantom mass into every subgame (noted in the code as measured
composition cost).

### Solver distillation into a policy net — `pokerbot/strategy/distill.py`
**Purpose.** A small stochastic MLP learns the action distribution of the TexasSolver oracle under supervision
— the cheap, sample-efficient way to a low GTO gap.
**Interface.** `features(hole, board, role_ip, pot, stack) -> list[float]` (fast features);
`build_dataset(pot=20.0, stack=100.0) -> (X, Y)` reads the solver cache; `train(X, Y, epochs=300, lr=1e-3,
hidden=(128,128), device=None, seed=0, net=None, bs=0)` trains (torch is imported only here);
`eval_gap(net, X, Y)` returns the selector (mean TV/KL to the GTO target distribution);
`solve_focus_spots(focus, n=8, pot=20.0, stack=100.0, workers=8, threads=16, max_iter=30, seed=None)`
solves new boards on target; `main()`.
**Input/Output.** Input: the JSON files of the solver cache `data/_gto_bench_cache`. Output: `X` =
feature vectors, `Y` = distribution over the five canonical action buckets `ACTIONS = ["fold_check",
"call", "aggr_small", "aggr_big", "allin"]` (small/big boundary at 0.66 pot, `_bucket`).
**Dependencies.** Hard: `pokerbot.config`, `engine.evaluator.evaluate`, `strategy.postflop.classify_board`,
a filled solver cache. Soft: `torch` (only for training, deliberately lazily imported so the
data build runs everywhere).
**Status.** Stateless; the cache on disk is the only memory.
**Cost.** Not measured. The docstring cites as design target "fits a 30-min pod run".
**Measurement status.** MEASURED NEGATIVE / capped: the distilled floor stalls at around 17% TV on
SRP flop data (`docs/STATE.md:1898`). That fits the project doctrine of the imitation ceiling
(CLAUDE.md: solver-imitation floor plateau ~−72). As a standalone bb/100 lever: UNMEASURED.
**Usable standalone?** Only with your own solver cache in the expected JSON format (nodes with `children`,
action names like `BET 6.6`, `CHECK`, `ALLIN`). Without the cache the module is empty.
**Pitfalls.** The five buckets are the ceiling. Whoever needs overbets does not get them here — `_bucket`
folds every size above 0.66 pot into ONE bucket; exactly that is named in `docs/STATE.md:1899-1900` as the
next stage ("finer action buckets (add overbets)").

### Deep-CFR adapter — `pokerbot/strategy/deepcfr_adapter.py`
**Purpose.** Deploys the from-scratch-trained HUNL Deep-CFR policy net as the decision core by
translating the live engine state back into EXACTLY the trainer's feature function.
**Interface.** `class LoadedPolicy(path, device="cpu")` with `strategy(feat, legal) -> {action: p}`
(softmax over the legal actions, renormalised); `live_features(state, hero_idx) -> (feat_vec, p)`
reconstructs the trainer features, `p` is the trainer's player index (0 = button);
`legal_fcpa(la) -> [int]` maps the engine `legal` dict to fold/call/pot/allin;
`_selfcheck(n=800)` is the built-in proof.
**Input/Output.** Input: engine `state` (`street`, `board`, `players[i].hole`/`committed_total`/
`is_button`, `legal.to_call`, `history` with `street` and `action`) plus a checkpoint path with the
key `policy`. Output: feature vector and action distribution over the fcpa constants from
`deep_cfr_hunl`.
**Dependencies.** Hard and irreducible: `pokerbot.strategy.deep_cfr_hunl` (supplies `Net`, `HState`,
`features`, `new_hand`, `FOLD/CALL/POT/ALLIN`) plus `torch`, `numpy`. The adapter deliberately duplicates NO
feature logic.
**Status.** `LoadedPolicy` holds the loaded net (per session); `live_features` is stateless.
**Cost.** One forward pass of a small MLP per decision; not measured.
**Measurement status.** MEASURED POSITIVE only as RECONSTRUCTION: `_selfcheck` checks on random states
`np.allclose(f_true, f_live, atol=1e-6)` and prints PASS/FAIL — a proof executable inside the module itself
that training and inference features are identical (`deepcfr_adapter.py:69-104`). The playing strength of the
net is REFUTED: the fcpa policy net of this family reached −212 bb/100 (CLAUDE.md,
"a HU policy net hit −212"); the master catalogue explicitly fences off `deep_cfr*.py` in `04_solver.md:580`.
**Usable standalone?** Only with `deep_cfr_hunl.py` and a trained checkpoint. The value for an
outsider lies in the PATTERN, not the result: "call the trainer's feature function yourself instead of
copying it, and prove the identity with a self-test" is the transferable idea.
**Pitfalls.** The chip frame is wired in (SB 50 / BB 100 / stack 20,000 = 200bb, docstring line 3).
Whoever plays with other blinds gets silently mis-scaled features — the self-test does NOT catch that,
because it uses the same scale on both sides.

### Empty package module — `pokerbot/valuenet/__init__.py`
0 bytes. Pure package marker, no content, no re-exports.

---

## B — `infra/`: pod control

### Pod lifecycle — `infra/runpod_run.py`
**Purpose.** Provisions a RunPod pod (GPU or CPU), reports its SSH endpoint and terminates it
again — the one place in the project where money is spent.
**Interface.** `launch(fast=False, disk=60)` tries a preference list of GPUs/clouds until one
comes up; `launch_cpu(flavor="cpu5c", vcpu=32, disk=40)`; `status()` polls every tracked pod and prints
`publicIp` + port mappings; `stop(pid)` PAUSES (container disk remains, storage keeps being billed);
`kill()` terminates EVERY tracked pod via `DELETE /pods/{id}` and empties the session file; `gpus()`
lists GPU types with prices via GraphQL; `is_blackwell(gpu)`. CLI: `--launch [--fast] / --cpu
[--flavor --vcpu] / --gpus / --status / --kill`.
**Input/Output.** Input: the RunPod API key from `C:\Users\hampe\Desktop\Secret keys\
Runpod-machiavel key.txt` (`KEY_FILE`, line 18) and the public SSH key from
`C:\Users\hampe\.ssh\pokerb_runpod.pub`; optionally `POD_IMAGE`. Output: console lines plus the
session file `data/_runpod_session.json` in the format `{"ids": [...]}` (the old `{"id": x}` is still read by
`_tracked_ids()`).
**Dependencies.** Only `pokerbot.config` (for `ROOT`) and standard library (`urllib`). Replaceable: the
`config` dependency is one line.
**Status.** Per session, on disk: `data/_runpod_session.json`. `_track()` APPENDS IDs and never
overwrites — so that `--kill` really catches all pods. Reset = delete the file (running pods are
then, however, no longer tracked and keep running on the bill).
**Cost.** Real money. `gpus()` prints the current hourly prices; `launch()` outputs `costPerHr` of the
created instance. No stored number in the repo.
**Measurement status.** UNMEASURED (infrastructure). Documented are only operational findings as code comments:
Blackwell cards (B200/B300, sm_100/103) fell back to the math path without torch `+cu128` and
therefore ran about 10 times slower (observed 2026-06-14, 14B at ~25 s/it — `runpod_run.py:29-33`);
the correct B300 ID is `NVIDIA B300 SXM6 AC`.
**Usable standalone?** Yes, practically immediately — it is a thin REST client. Minimal: your own API key,
your own SSH pubkey, adjust `KEY_FILE`/`PUBKEY_FILE`.
**Pitfalls.** `stop()` is NOT `kill()`. A paused pod keeps being billed for storage — the
project rule is therefore `--kill` without exception (CLAUDE.md). Second point: the session file is GLOBAL;
two parallel campaigns share it, and a `--kill` of one terminates the other's pods too
(exactly what `infra/eval_pod.py:5-7` warns about).

### Self-killing RL campaign — `infra/runpod_rl_campaign.py`
**Purpose.** One command runs the complete training run on a freshly provisioned H100/H200:
setup, DSL-SFT (gate 0), DAPO-GRPO, GTO-anchored holdout evaluation, result pull — and ALWAYS terminates the
pod (`atexit` + `finally`).
**Interface.** Module with `main()`/CLI; the phases are SSH commands chained as steps.
No reusable API — the value lies in the flow pattern.
**Input/Output.** Input: the code tarball (repo subset) plus the gold shards; output: the best
LoRA adapter and the log files, via scp back to the PC.
**Dependencies.** Hard: `infra/runpod_run` (provisioning + kill), a working
SSH key, the pod setup scripts, `training/`. Not replaceable without rebuilding.
**Status.** Per campaign; the pod is the state. Reset = terminate the pod, check the session file.
**Cost.** GPU hours; not stored as a number in the repo.
**Measurement status.** REFUTED as a lever — not the script, but what it measures: the chain SFT -> GRPO
produced in its last execution a REGRESSION from −28 to −90.18 against GTO Wizard (CLAUDE.md,
"a re-SFT on made-hand-NATIVE gold + a fresh GRPO REGRESSED to −90.18"). The SFT warm start itself
works (token accuracy 97.5%, `docs/STATE.md:1159`).
**Usable standalone?** No — it is the wiring of THIS project. Transferable is the pattern:
self-killing (`atexit` AND `finally`), gate ladder between the phases, result pull before the kill.
**Pitfalls.** The pull sits at the END. Two runs of the project died of SSH timeouts and
lost the model in the process (memory `grpo-reward-fix-and-timeout-fragility`); the countermeasure was an
independent watchdog (`infra/_resft_mon.py`) and an intermediate grabber (`infra/_grab_sft.py`).

### Campaign pods (group) — `infra/{cfv_pod_campaign,eval_pod,export_pod,slumbot_pod,ablation_pod}.py`
**Purpose.** Five identically built, self-killing single-purpose campaigns: CFV data generation on several
CPU pods, isolated Slumbot baseline measurement, parallel generation of the whole analyzer arm family,
HU Slumbot benchmark with a vLLM-hosted brain, and the RESOLVER-ON ablation.
**Interface.** One `main()` per file with its own flags; no importable building blocks.
`cfv_pod_campaign` provisions N CPU pods, sets each up (TexasSolver Linux + repo code) and merges
the shards; `eval_pod` measures `qwen_poker_ckpt500` against Slumbot; `export_pod` generates several
1500-hand exports in parallel; `slumbot_pod` starts a vLLM server (base model + LoRA) and lets the
brain play through the engine; `ablation_pod` runs the 2x2 isolation with resolvers switched on.
**Input/Output.** Input: code tarball + the respective artifacts (adapter, cache, seeds). Output: the
pulled result files in the local `data/`.
**Dependencies.** All hard on `infra/runpod_run`; `export_pod` additionally on
`research/pokerstars_export` or `research/sixmax_export`; `slumbot_pod` on `pokerbot/benchmark/slumbot*`.
**Status.** Per campaign. `eval_pod` explicitly resolves the conflict of the SHARED session file —
it must not co-kill a pod that is training in parallel (`eval_pod.py:5-7`).
**Cost.** The reason for `export_pod` is explicitly time: a 1500-hand seed-55 export takes HOURS
LOCALLY when the turn-solve cache is cold after a lever change (`export_pod.py:3-5`). Absolute
numbers: not measured.
**Measurement status.** UNMEASURED as a lever (tools). `ablation_pod` carries its motivation as a documented number: the
live break of −58 showed that all night levers had been validated resolver-OFF, while
live play is resolver-dominated (`ablation_pod.py:3-5`; the same story in CLAUDE.md as the v8 break).
**Usable standalone?** No. For an outsider they are templates, not building blocks.
**Pitfalls.** The shared session file from `runpod_run` — whoever runs two of these campaigns at the same
time risks a `kill()` terminating both pods. `eval_pod` is the only file that handles this
case explicitly; the others do not.

### Pod probes and watchdogs (group) — `infra/{runpod_launch,runpod_check,runpod_recon,runpod_cpu_probe,_grab_sft,_resft_mon}.py`
**Purpose.** Six small helpers around the pod control: a dry-run launcher, three read-only
API probes and two independent watchdogs that catch a hanging run.
**Interface.** `runpod_launch` checks the balance, prints recipe and cost estimate and provisions
NOTHING without `--go` (114 lines); `runpod_check` (32 l.) checks connectivity/auth; `runpod_recon` (38 l.)
lists available deploy mutations and GPU/CPU options; `runpod_cpu_probe` (35 l.) finds the valid
CPU flavor IDs; `_grab_sft` (93 l.) polls the pod for
`/root/qwen_poker_lora/adapter_model.safetensors`, pulls it to `models/sft_new.tgz` and DELETES the pod;
`_resft_mon` (121 l.) polls independently of the campaign and kills on stall.
**Input/Output.** Input: API key, pod ID from the session file. Output: console lines; for
`_grab_sft` additionally the tarball.
**Dependencies.** All on `infra/runpod_run` or directly on the RunPod REST API; `_grab_sft`/`_resft_mon`
additionally on working `ssh`/`scp` under Windows.
**Status.** Stateless except for the shared session file.
**Cost.** The three probes cost nothing (read-only, explicitly "no pods provisioned, no cost").
**Measurement status.** UNMEASURED. The reason `_resft_mon` exists is a documented operational failure: the
campaign's SSH timeout does NOT fire cleanly under Windows; a crashed SFT left the pod
idling and billing (`_resft_mon.py:3-5`).
**Usable standalone?** `runpod_check`/`runpod_recon`/`runpod_cpu_probe` yes, immediately and harmlessly. The
watchdogs only with the corresponding campaign.
**Pitfalls.** `_grab_sft` and `_resft_mon` KILL pods on their own. Whoever starts them parallel to a running
campaign without understanding the session file can switch off their own training run.

---

## C — `research/`: provenance of the core assets

### Preflop blueprint via exact CFR+ — `research/preflop_solve.py`
**Purpose.** Produces the near-Nash HU 200bb preflop blueprint through noise-free CFR+ over a real
bet-size tree (limp / 2.5bb open / 3-bet 10 / 4-bet 24 / 5-bet 60 / jam) — the asset that catalogue part
02 describes as a finished product.
**Interface.** `build_eqmatrix(sims, rng) -> list[list[float]]` builds the 169x169 all-in equity matrix
(upper triangle via MC, lower via symmetry, diagonal 0.5); `load_eqmatrix(sims, rebuild)` caches
it to `knowledge_base/ranges/preflop_eqmatrix.json`; `traverse(node, i, j, EQ, r_sb, r_bb, regret,
strat)` is the CFR+ recursion step (returns the SB's counterfactual value); `main()` runs the
iterations and writes the result. The tree itself is the module constant `TREE`
(node -> `(to_act, sb_inv, bb_inv, [(action, kind, n_sb, n_bb, next_node)])`, `kind` in
`foldSB`/`foldBB`/`sd`/`sd_allin`/`node`).
**Input/Output.** Input: flags only (`--iters`, `--sims`, `--realize-kappa`, `--rebuild-eq`,
`--leaf-table`). Output: `knowledge_base/ranges/preflop_blueprint.json` in the format
`{node: {hand_class: {action: probability}}}` (with `--leaf-table`:
`preflop_blueprint_solvergraft.json`).
**Dependencies.** Hard: `pokerbot.config`, `engine.cards` (`all_hand_classes`, `expand_class`,
`make_deck`), `engine.evaluator.evaluate`, `research.preflop_leaves.leaf_w`. Replaceable: `preflop_leaves`
is a 3-line function (the seam for calibrated leaf values).
**Status.** Stateless per run; the equity matrix on disk is the only cache. If `--sims` is raised,
`load_eqmatrix` rebuilds it automatically.
**Cost.** MEASURED: equity matrix ~3 min plus CFR+ ~3.5 min = ~6 min locally, single-core, then cached
(`docs/STATE.md:1595-1596`). The same entry records that the cloud LOSES here (GCP setup alone
~15 min, a CFR loop does not use many vCPUs).
**Measurement status.** MEASURED POSITIVE. Exact preflop exploitability in the model game: `expl(blueprint) = 3.3`
against `expl(heuristic) = 234` bb/100, i.e. 71 times less exploitable (`docs/STATE.md:1610-1611`, measured
with `research/preflop_exploit.py`). Live only DIRECTIONAL: −53 ± ~24 bb/100 with blueprint on (n=200)
against the −72 baseline (`docs/STATE.md:1616`) — explicitly not significant.
**Usable standalone?** Yes, this is one of the most easily isolatable modules of the repo. Minimally required:
card code and a hand evaluator; `TREE` and `traverse` are readable on their own. Whoever wants a different
bet tree changes only `TREE`.
**Pitfalls.** The continuation approximation. Non-all-in showdowns are scored as a CHECKDOWN
(`kind == "sd"`, `leaf_w`), so there is NO postflop play in the model. That captures the all-in discipline
cleanly but underestimates the realisability of suited/connected hands — the docstring says so
itself (lines 9-13), and `docs/STATE.md:1617-1620` additionally warns: low in-model exploitability
can mean mere convergence to the WRONG (checkdown) game. Second pitfall: an early
chance-sampled variant left the deep 4bet/5bet/jam nodes as pure noise
(72o called 200bb jams) — hence the precomputed equity matrix.

### Leaf-value calibration (group) — `research/{preflop_calibrate,preflop_leaves,preflop_ranges}.py`
**Purpose.** Replace the checkdown estimate at the see-flop leaves of the blueprint with a realisation premium
per node MEASURED from real TexasSolver flop solves.
**Interface.** `preflop_ranges.reaching_ranges()`/`load_blueprint()`/`sd_leaves()` return the
reach-weighted ranges per see-flop node (95 l.). `preflop_calibrate.calibrate_node(node, blueprint,
n_flops, n_samples, max_iter, ...)` solves suit-canonical flops at the node and measures via rollout the
realised EV of the in-position player; `flop_realized_ev(root, board, oop_str, ip_str, pot0, n_samples,
...)` is the core, `_rollout`/`_checkdown_v0` the two valuations, `_canonical_flops(n, rng)` the
board selection (259 l.). `preflop_leaves.load_leaf_table(path)`, `build_kappa_map(table, blueprint, EQ) ->
{node: kappa}` and `leaf_w(node, e, kmap, default_kappa) -> float` form the one seam that
`preflop_solve.traverse` and `preflop_exploit._leaf` use jointly (59 l.).
**Input/Output.** Input: the blueprint plus TexasSolver. Output:
`knowledge_base/ranges/preflop_leaf_table.json` with `w_node` per node; from it via
`build_kappa_map` a `{node: kappa_node}` by the formula
`kappa_node = (w_node - E[e]) / (4 * E[e*(1-e)])`, reach-weighted.
**Dependencies.** Hard: `pokerbot.strategy.gto_oracle` (i.e. TexasSolver), `engine.cards`,
`engine.evaluator`, `research.preflop_ranges`. `preflop_leaves` depends on nothing but `json`.
**Status.** Stateless; tables on disk.
**Cost.** Not measured (depends on the number of solved flops times `max_iter`).
**Measurement status.** UNMEASURED as an EV lever — no bb/100 comparison blueprint-with-graft against
blueprint-without-graft is documented in the repo. The construction itself is deliberately BACKWARD-COMPATIBLE:
`kmap=None` or a missing node yields exactly the old checkdown behaviour (`preflop_leaves.py:13-15`).
**Usable standalone?** `preflop_leaves` yes (pure arithmetic). `preflop_calibrate` only with a working
TexasSolver.
**Pitfalls.** The fidelity level. `preflop_calibrate` solves ONLY the flop round (`dump_rounds=1`) and
checks turn+river down via equity (docstring lines 9-11). Whoever takes that for a full-blown
postflop continuation overestimates the number.

### Exact preflop exploitability — `research/preflop_exploit.py`
**Purpose.** Measures the EXACT distance to Nash in the preflop model game via best-response enumeration — the
metric with which the blueprint was set against the old heuristic.
**Interface.** Module with `main()`; computes `½[BRV_SB + BRV_BB]` (Johanson convention) over all
enumerated infosets of the `TREE` from `preflop_solve`, with a per-NODE decomposition.
**Input/Output.** Input: a strategy profile (blueprint JSON or the heuristic). Output:
exploitability in bb/100 total and per node.
**Dependencies.** Hard: `research.preflop_solve` (tree), `research.preflop_leaves.leaf_w`, the
equity matrix.
**Status.** Stateless.
**Cost.** Not measured.
**Measurement status.** MEASURED POSITIVE as a tool — it LOCALISED two concrete leaks: 3BET +164 bb/100
(SB over-folds against 3-bets) and 4BET +87 (BB folds 98% against 4-bets), which mechanistically explains the −72
against GTO Wizard (`docs/STATE.md:1611-1615`).
**Usable standalone?** Only together with `preflop_solve`.
**Pitfalls.** Circularity. `docs/STATE.md:1617-1620` records the vetted warning: in-model
exploitability is a CONVERGENCE test, not a true Nash distance — "low expl can just mean convergence to
the WRONG (checkdown) game". The non-circular variant would need independent leaf values.

### Preflop reference works (group) — `research/{preflop_table,preflop_probe,parse_ranges}.py`
**Purpose.** Three independent preflop sources next to the solved blueprint: a lookup table distilled from
PokerBench, 30 constructed test spots against the 6-max core, and the range captions from
*Modern Poker Theory*.
**Interface.** `preflop_table` (159 l.) distils PokerBench spots into a table with the key
`hero_pos + level + last-raiser-pos + 169 hand classes` and measures action agreement on the
holdout. `preflop_probe` (161 l.) runs 30 constructed spots against the `tag` core and sets prediction
against measurement. `parse_ranges` (114 l.) parses the `Hand Range N:` lines from the book without an API.
**Input/Output.** PokerBench dataset or book text in; JSON tables into `knowledge_base/ranges/`
out.
**Dependencies.** `preflop_table` needs the PokerBench dataset (external); `preflop_probe` the
6-max core; `parse_ranges` only the extracted book text.
**Status.** Stateless.
**Cost.** Not measured.
**Measurement status.** MEASURED POSITIVE for `preflop_table`: 88.6% agreement on the holdout, better than
both LoRAs; the result sits as `knowledge_base/ranges/preflop_gto_table.json` and is wired into the 6-max RFI
(`docs/STATE.md:1741-1743`). CAUTION: the same state notes elsewhere that
`preflop_gto.py` (88.6%) is NOT wired into the HU `bot.py` (`docs/STATE.md:1672`). `preflop_probe`
and `parse_ranges`: UNMEASURED.
**Usable standalone?** `parse_ranges` yes. `preflop_table` only with PokerBench.
**Pitfalls.** 88.6% action agreement is NOT playing strength — the project doctrine (CLAUDE.md,
measured several times) is that frequency imitation without the teacher's selection costs EV.

### Advisor data builders (group) — `research/{build_river_data,build_turn_data,build_defense_data}.py`
**Purpose.** Generate the training data of the three advisor nets (river, turn, facing-bet defence) from the
already existing TexasSolver caches — without new solves.
**Interface.** One `main()` per file. `build_river_data` (67 l.) runs over
`data/_gto_river_cache/*.json`; the cache root IS the OOP river node and its `CHECK` child the
IP node, hence no line walk. `build_turn_data` (96 l.) has `_smallest_bet(children)` (the
non-all-in c-bet = smallest `BET` size) and `_extract(node, role, board4, tex, rows)`; it follows the
classic turn-barrel line flop CHECK -> BET -> CALL -> turn. `build_defense_data` (122 l.) has
`_defense_rows(defender, node, board, tex, st, street, size_faced)`, `_bet_children(node)` and
`_process_cache(cache_dir, street, nboard, cap=None)`; it pulls from BOTH caches (flop 3-card and
river 5-card) the nodes one level deeper.
**Input/Output.** Input: the solver cache directories. Output: JSONL rows into
`data/river_data.jsonl`, `data/turn_data.jsonl`, `data/defense_data.jsonl`. Features uniformly
`FEAT = ["tier","flush_draw","backdoor_flush","nut_flush_blocker","made_straight","oesd","gutshot",
"overcards","has_draw"]` plus texture and role; target `y` = P(bet) for river/turn, `(P_fold, P_call,
P_raise)` for defence.
**Dependencies.** Hard: `pokerbot.config`, `pokerbot.benchmark.gto_benchmark` (`_CACHE`, `texture`),
`engine.evaluator.evaluate`, `strategy.features.hand_features`.
**Status.** Stateless.
**Cost.** Not measured; `build_turn_data` ran ON THE POD per the docstring, because the DUMP=2 cache files
at ~8 MB each were too large to pull.
**Measurement status.** UNMEASURED as standalone levers (data builders). The advisors trained from them are
described in catalogue part 03.
**Usable standalone?** Only with a TexasSolver cache in the expected dump format.
**Pitfalls.** The three files look interchangeable but are not: `build_river_data` deliberately
mirrors `build_advisor_data` (flop) and NOT `build_turn_data` — because the river cache root is already the
sought node. Whoever copies the turn logic to the river walks the tree one level too deep.
Secondly, `build_defense_data` covers ONLY flop and river; turn and further sizes/SPRs are missing and
would need new solves (docstring line 7).

### CFV net chain (group) — `research/{cfv_eval,cfv_data,train_cfv_net}.py`
**Purpose.** The three steps that were supposed to deliver the turn-leaf value net for a flop resolver: pull CFVs from
solved river subgames, generate a dataset from them, train the net.
**Interface.** `cfv_eval` (168 l., phase B step 8) extracts per-combo river CFVs from a
solved TexasSolver dump — the training labels. `cfv_data` (171 l., step 9) generates from them the
dataset `cfv_dataset.jsonl`: (4-card turn board + both ranges + pot) -> per-combo turn-boundary CFVs.
`train_cfv_net` (140 l., step 10) trains the net on `cfv0[169]`/`cfv1[169]`.
**Input/Output.** Solver dumps in, `cfv_dataset.jsonl` in the middle, a `.pt` net out.
**Dependencies.** Hard: TexasSolver (for the labels), `torch` (for the net), the zero-sum convention
from `cfv_eval` (`value0 = winnings0 - (pot/2 + street_contrib0)`), which `preflop_calibrate` explicitly
adopts.
**Status.** Stateless; dataset and net on disk.
**Cost.** Not measured; the data generation was the reason for `infra/cfv_pod_campaign.py` (several
CPU pods).
**Measurement status.** UNMEASURED at HUNL scale. The SAME construction principle was REFUTED on Leduc
(see `pokerbot/valuenet/gate0_leduc.py`: gate failed, 90.89 mbb above the bar) —
though with the explicit caveat in `../plans/VALUE_NET_PLAN.md:70-79` that the Leduc version
is MORE STRICTLY degenerate than the HUNL plan (there flop+turn would be explicit, the net only at the turn->river leaf).
**Usable standalone?** Only as a chain and only with a solver.
**Pitfalls.** The sign and normalisation convention. It must be identical between `cfv_eval`, `cfv_data` and the
query site in the resolver; if it is not, the result is silently wrong (the same trap that
`gate0_leduc.py:32-36` documents for Leduc).

### Cache tools and short deck (group) — `research/{mass_solve_shortdeck,train_sd_advisor,texture_freqs,analyze_cache,inspect_node}.py`
**Purpose.** Five tools on the solver cache: a short-deck variant of mass solving, the corresponding
advisor, the extraction of exact per-texture frequencies, and two inspectors.
**Interface.** `mass_solve_shortdeck` (69 l.) mirrors the parallel pattern of `mass_solve.py` with
`mode='shortdeck'` (36 cards, 6-A) into `data/_gto_shortdeck_cache`. `train_sd_advisor` (77 l.) trains
the short-deck bet-vs-check advisor on `data/sd_advisor_data.jsonl`, held out BY BOARD, against a
(role, texture) frequency baseline. `texture_freqs` (63 l.) pulls the exact GTO bet frequencies of the
OOP donk and the IP c-bet node from the 1340-board cache into
`knowledge_base/postflop/texture_freqs.json`. `analyze_cache` (106 l.) prints what real GTO does on these
flops, broken down by texture. `inspect_node` (49 l.) exposes the raw structure of a
DUMP=2 chance node.
**Input/Output.** Cache JSONs in; JSON tables, a `.pt` or console output out.
**Dependencies.** Hard: `pokerbot.config`, `pokerbot.benchmark.gto_benchmark`, TexasSolver for the
mass solving.
**Status.** Stateless.
**Cost.** Not measured. Order of magnitude: the cache directory `data/_solve_cache` contained 12,493 files
at the time of writing this addendum — the number GROWS with every run and is not a fixed value (part 04
cites 12,209, an interim count 12,395).
**Measurement status.** UNMEASURED, with one exception: `texture_freqs` replaced measured heuristics with
solver frequencies and feeds the c-bet policy that was calibrated in `gto_baseline` (93% -> 80%,
`gto_baseline.py:29-31`). `train_sd_advisor` is, per its own docstring, explicitly a SANITY test, not a
product.
**Usable standalone?** `analyze_cache` and `inspect_node` yes (pure readers). The rest needs TexasSolver.
**Pitfalls.** Short deck is a DIFFERENT game (flush beats full house, changed equities). Whoever accidentally
hangs the short-deck cache into the full-deck pipeline gets plausible but wrong numbers.

---

## D — `research/`: external grading

### HU export for the GTO Wizard analyzer — `research/pokerstars_export.py`
**Purpose.** Lets the HU bot play against `GTOBaseline` and writes the hands as a
PokerStars hand history so the GTO Wizard analyzer can grade EVERY hero decision against GTO — the
fast, free half of the measurement economy (the 6-max counterpart is `sixmax_export.py`).
**Interface.** `hero_decider(seat, seed, resolver=None)` returns a decider that uses EXACTLY the
live GTOW agent (`benchmark.gtowizard.PokerBotAgent`, seat 0 mandatory);
`villain_decider(seat, seed)`; `stack_mit_protokoll(variante, roh_decider, hand_idx, protokoll)` wraps
the v4 guard stack from the ONE source `autogym.pargate._wickle` around a finished decider and logs
every intervention; `play_hand(g, hero_seat, idx, resolver=None, ...)`; `format_hand(hand_id, dt, names, button,
holes, history, result, hero_seat) -> str` produces the text block; `money(chips) -> str`; `main()`.
**Input/Output.** Input: flags (`--n`, `--out`, `--hero`, seeds) plus the environment variables of the
GTO mode. Output: a text file with PokerStars-formatted hands at SB 50 / BB 100 / stack 20,000
(= 200bb, `pokerstars_export.py:29`); hero switches seat every hand so both positions are graded;
stacks are reset every hand (cash game).
**Dependencies.** Hard: `strategy.gto_mode.apply` (MUST run before every strategy import, see
Pitfalls), `engine.game.HeadsUpGame`, `strategy.bot`, `strategy.gto_baseline.GTOBaseline`,
`benchmark.gtowizard.PokerBotAgent`, `autogym.pargate` (`KANDIDATEN`, `_wickle`).
**Status.** Per run; the module-global `GEFEUERT` collects the guard interventions over all hands and is
NOT cleared automatically.
**Cost.** The catalogue frame (CLAUDE.md, measurement economy) cites for the export of 1500 hands locally
about 4 minutes after memoisation; `infra/export_pod.py:3-5` on the other hand records that a
1500-hand export with a COLD turn-solve cache takes hours.
**Measurement status.** MEASURED POSITIVE as a measurement channel — the HU arm of this export delivered the first absolute
GTO grade of the HU engine: GTO score 53.4% / freq-diff 54.6% (CLAUDE.md, ★★★ CURRENT-TRUTH block; the
6-max counterpart came to 85.9% / EV loss 7.61). As an EV lever: UNMEASURED (it is a measuring instrument).
**Usable standalone?** The FORMATTER yes: `format_hand` and `money` are a standalone
PokerStars serialiser that can be fed from any engine. The rest hangs on this bot.
**Pitfalls.** Two, both paid for dearly. (1) `_apply_gto_mode()` sits DELIBERATELY before the
strategy imports (`pokerstars_export.py:15-21`) — the flags are read at import; whoever moves the line
exports a DIFFERENT configuration than the one measured live. (2) The guard stack
comes from `pargate._wickle`; an earlier local copy had a different margin and UNSEEDED
Monte Carlo — that broke the pairing of paired comparisons (comment `pokerstars_export.py:57-62`).
In addition the ledger rule from CLAUDE.md applies: hand IDs burn on FIRST contact, never repeat `idbase`/`dayoffset`.

### Decision grading of our own session (group) — `research/{study_grade,study_analyze,study_review,study_distill}.py`
**Purpose.** A reusable test bench that grades every logged decision of a GTOW/Slumbot session
against the best available truth — preflop against the blueprint, postflop against the solver — and
carries the finding through to teacher-gold distillation.
**Interface.** `study_grade` (481 l.) is the core: `reconstruct_spot(session_hand, hero, button,
prefix, street)`, `hero_decision_points(history, button, hero)`, `hero_seat_and_button(session_hand,
hero_hole)`, `audit_inputs(feat, spot, reasoning)` (separates "the wiring delivered wrong maths" from
"the judgment was wrong"), `grade_preflop(feat, action)`, `grade_postflop(spot, feat, action, amount_bb,
solve)`, `grade_one(dec, session_hand, recon_pref, solve)`, `run(stage, threads, solve_threads, limit)`,
`regrade_unscored(...)`; CLI stages `--stage recon` (free) and `--stage grade` (with solver).
`study_analyze` (258 l.) turns that into the ranked leaks + edges and selects the ~36 hardest spots;
`study_review` (130 l.) fetches an INDEPENDENT OpenAI second opinion for them (a Claude self-review would be
biased); `study_distill` (92 l.) distils the good decisions into teacher gold.
**Input/Output.** Input: `data/claude_play/thought_log.jsonl` plus the session hand histories.
Output: append-only JSONL with one grade per decision (resumable — already graded `seq` are
skipped).
**Dependencies.** Hard: `pokerbot.benchmark.slumbot.build_state` and
`benchmark.slumbot_llm.spot_from_slumbot` (the same seam the live bot uses), `api.solve_node`
(TexasSolver), the preflop blueprint. Replaceable: the OpenAI second opinion in `study_review`.
**Status.** Per run, but resumable via the JSONL file; `regrade_unscored` fills in gaps.
**Cost.** Deterministic and free except for the solver's CPU (docstring line 16); the
stage `recon` runs without a solver.
**Measurement status.** MEASURED POSITIVE as a tool: 264 decisions graded, postflop solver coverage 98.8%
(160/162), plus an independent second opinion on the 33 hardest spots (`docs/STATE.md:1139`). Finding:
96.2% in support, the −38 AIVAT was river/big-pot VARIANCE rather than leaks; the one real small leak was
postflop over-checking (memory `claude-code-vs-gtow-study`).
**Usable standalone?** The reconstruction part yes, if you have hand histories in the Slumbot token format. The
grading part needs blueprint + solver.
**Pitfalls.** The EV loss is a PROXY. `api.solve_node` returns no EV per action; only for
call/fold is the number real bb (docstring lines 12-14). Whoever reads the sum as bb/100 overstretches it.
Secondly: the module uncovered the `to_call` wiring bug only BECAUSE it sets the logged against the
reconstructed inputs (`input_inflated`) — dropping this separation turns a
wiring bug into an apparent judgment problem.

### Slumbot tools (group) — `research/{slumbot_collect,slumbot_mistakes,slumbot_v22}.py`
**Purpose.** Play against the freely available Slumbot, log richly and pull out the mistakes.
**Interface.** `slumbot_collect` (54 l.) plays `PokerBot(exploit=False)` against Slumbot and writes per
hand the hole cards, board, the full action string, `winnings`, `won_pot` and Slumbot's showdown cards into
a JSONL. `slumbot_mistakes` (78 l.) reads that file and exposes the mistakes.
`slumbot_v22` (105 l.) runs the set v2.2 anchor WITH the Slumbot-specific exploit switched on.
**Input/Output.** Network in, JSONL out, mistake list on the console.
**Dependencies.** Hard: `pokerbot.benchmark.slumbot` (HTTP client + `build_state`), internet.
**Status.** One Slumbot `token` per session.
**Cost.** Network latency per decision; not measured.
**Measurement status.** MEASURED NEUTRAL: the engine sits at roughly break-even against Slumbot (+12.6 at n=500;
the earlier cited −46/−871/−374 were wrong), and the mistakes split roughly in half into coolers and
fixable −EV over-bluffing (memory `engine-vs-slumbot-breakeven`, tools explicitly
`slumbot_collect`/`slumbot_mistakes`).
**Usable standalone?** Yes, as soon as your own bot serves the `(action, amount)` interface — Slumbot is
public and free. For an outsider this is the cheapest external reality test in the whole repo.
**Pitfalls.** n=500 against Slumbot is statistically thin; the project history at exactly this spot
(four different "measured" numbers for the same engine) is the warning.

### Oracle cross-check and remaining tools (group) — `research/{gtow_oracle_check,play_gtow,pokerbench_grounded}.py`
**Purpose.** Check whether our own solver oracle agrees with the strongest available benchmark;
provide a handshake through which an agent plays GTO Wizard hand by hand; open up PokerBench as a
grounded 6-max reference.
**Interface.** `gtow_oracle_check` (245 l.) sets the oracle's recommendation against GTOW's ACTUAL
play. `play_gtow` (73 l.) is the file-handshake driver for the `ClaudeCodeAgent`.
`pokerbench_grounded` (93 l.) parses the 563k templated PokerBench decisions into structured spots.
**Input/Output.** GTOW hand histories or the PokerBench dataset in; agreement statistics or
structured spots out.
**Dependencies.** Hard: GTOW API key (for the cross-check), TexasSolver, PokerBench.
**Status.** Stateless.
**Cost.** Solver CPU; not measured.
**Measurement status.** MEASURED POSITIVE for `gtow_oracle_check`: our solver/blueprint oracle is about 90%
aligned with GTOW, i.e. NOT grossly broken — this finding CLEARED AWAY the speculative
postflop-solver overhaul (CLAUDE.md, "our solver/blueprint ORACLE is ~90% aligned with
GTOW (NOT grossly broken) → the speculative postflop-solver overhaul ... is NOT justified by the data").
`play_gtow`, `pokerbench_grounded`: UNMEASURED.
**Usable standalone?** `pokerbench_grounded` yes (only the public dataset). The other two need
the GTOW researcher access.
**Pitfalls.** The GTOW access is the project's scarce channel (CLAUDE.md: hand budget, ledger obligation).
Whoever thoughtlessly runs the cross-check over many hands burns budget that is needed for live
anchors.

---

## E — `research/`: diagnosis and effect proofs

### River-bill replay — `research/river_bill_replay.py`
**Purpose.** Hindsight confusion matrix: would the `river_bill_guard` really have folded the measured big-pot river-call
disasters, and how many won big-pot calls would it have cost?
**Interface.** `spot_state(hand, hero_seat, spot_idx, acts) -> dict | None` reconstructs the state at the
call spot faithfully to live; `main()` runs both arms (control and v4_prince) and prints the matrix.
**Input/Output.** Input: the logged GTOW-night-2 hand histories (`data/sessions/gtow_hands_*.jsonl`).
Output: per spot `fold_net = -committed_total_hero_vor_call` and `delta = fold_net - winnings` (positive =
the fold would have saved), aggregated into the matrix.
**Dependencies.** Hard: `benchmark.gtowizard._parse_history` (the validated token translator), the
real `river_bill_guard` code path (wrapped around a dummy base that always returns `('call', None)`), the
hero-seat logic `hero_seat_of`.
**Status.** Stateless, deterministic.
**Cost.** Free, runs on logged data.
**Measurement status.** MEASURED, mixed — and therefore instructive. Journal `data/autogym/journal.jsonl`, entry
`R7-DIAGNOSE` of 2026-08-30 19:55:52: 20 trigger spots, the guard folds 5 of them — 3 correctly (+141bb),
2 wrongly (−121bb), net +20bb. The same entry records the DISCRIMINATION finding: the tracker equity
does NOT separate winners and losers (default 0.578 vs 0.513; PRINCE env 0.652 vs 0.532; the ranges are still
700-900 combos wide after three barrels), and the two 200bb stack-offs lie BELOW the trigger.
**Usable standalone?** Only with our hand logs and the guard. The PATTERN is transferable, though: hold a guard
against real outcomes known from the future before shipping it.
**Pitfalls.** The docstring says it itself (lines 22-25): this is an EFFECT-PROOF proxy for a
gate decision, NOT a bb/100 estimator — the fold does not change the opponent's future adaptation along with it.
And the consistency gate is mandatory: if the reconstructed pot does not match `replay_voll.pot_before`,
the hand is EXCLUDED and counted (never compute with wrong numbers).

### River coherence diagnosis — `research/river_coherence.py`
**Purpose.** Grades the value/bluff/bluff-catch coherence of our bot against the SOLVED
river equilibrium — the river diagnostic score.
**Interface.** Module with `main()` (562 l.); result into
`data/research_sweep/river_coherence.json`.
**Input/Output.** Played river decisions in; one score per category out.
**Dependencies.** Hard: the solver, the range tracker; specification `../doctrine/RIVER_SYSTEM.md` and
`data/research_sweep/openai_river_consult.json`.
**Status.** Stateless.
**Cost.** Solver CPU; not measured.
**Measurement status.** UNMEASURED as a lever (diagnostic tool); the result JSON sits in the repo, no
bb number derived from it is documented in the catalogue.
**Usable standalone?** No, interwoven with tracker and solver.
**Pitfalls.** A coherence score is a FREQUENCY metric. The project doctrine (CLAUDE.md, measured three
times) says that frequency alignment without the teacher's selection COSTS EV — a better score is
therefore no ship argument.

### Component competence matrix — `research/component_matrix.py`
**Purpose.** Measures WHICH decision-producing component of the bot is the best in WHICH region of the game,
graded against the TexasSolver oracle — the operationalisation of the principle "ensemble, don't discard".
**Interface.** Module with `main()` (672 l.); result into
`data/research_sweep/component_matrix.json`.
**Input/Output.** Spot sample in; per (component x region) a quality out.
**Dependencies.** Hard: all evaluated components (blueprint, advisors, resolver, heuristics) plus
TexasSolver.
**Status.** Stateless.
**Cost.** Solver CPU per spot; not measured.
**Measurement status.** UNMEASURED as a lever. The underlying idea is recorded in the memory `ensemble-not-discard`
(weight per-context reliability instead of discarding a component on its average), but a
measured bb improvement derived from it is not documented in the repo.
**Usable standalone?** No.
**Pitfalls.** The matrix is only as good as the oracle. Since the cross-check attests the oracle ~90% alignment with
GTOW, the remaining 10% are exactly the cells in which the matrix can mislead.

### River and resolver probes (group) — `research/{river_bill_diagnose,river_leak,river_probe,resolver_probe,freq_diff,v8_replay_gegentest}.py`
**Purpose.** Six narrow probes on the same river/resolver complex: discrimination of the tracker equity,
leak attribution with our own maths, behavioural profile, resolver latency and fire rate,
frequency difference to the teacher, and an axis counter-test for arbitrary guard stacks.
**Interface.** `river_bill_diagnose` (84 l.) sets, for the 20 trigger spots, the exact equity against
the tracker range. `river_leak` (57 l.) repeats `PokerBot(exploit=False)` against `GTOBaseline` (seed 7)
and logs per river decision `rationale['equity']` and, before a bet, the required equity — without
GTOW. `river_probe` (129 l.) profiles hero's river behaviour on the same 1000 hands as the
GTOW upload by action x hand strength x SPR. `resolver_probe` (60 l.) measures latency and fire rate of the
line-aware resolver. `freq_diff` (265 l.) buckets HERO (PRINCE v2.2) and GTOW into the same buckets as
`freq_mine`. `v8_replay_gegentest` (219 l.) runs arbitrary guard stacks against the real
night-2 hands.
**Input/Output.** Logged hands or fresh self-play runs in; console/JSON findings out.
**Dependencies.** Hard: the respective bot path plus `gtowizard._parse_history` for the replay probes.
**Status.** Stateless.
**Cost.** `resolver_probe` MEASURES cost (that is its purpose); the others are cheap because they run on
logs.
**Measurement status.** UNMEASURED as a lever (measuring instruments). A documented finding gained from them is in the
journal entry on `river_bill_diagnose` (see `river_bill_replay` above: tracker equity does not discriminate).
**Usable standalone?** `river_leak` most readily — it needs only your own bot and the baseline, no
external account.
**Pitfalls.** These probes produce HYPOTHESES, not verdicts. The project doctrine demands for every
verdict a paired gate (`pargate`/`envgate`) and three runs before a naming.

### Acquisition, range and channel tools (group) — `research/{blindspot_radar,grounded_blindspots,check_floor_range,danger_pair,duplicate_mode_ab,theory_duel,flop_pilot}.py`
**Purpose.** Seven tools for the question "where should I look next and what do I measure it with":
LLM-triaged active learning, its grounded counterpart, a range gate, a class-dense A/B builder,
the fast local canary measurement, a duel against theory itself and a solve-cost pilot.
**Interface.** `blindspot_radar` (204 l.) triages via LLM which spots should be solved.
`grounded_blindspots` (93 l.) does the same WITHOUT an LLM: where does the analytical floor (`GTOBaseline`) deviate
most strongly from the solver, straight from the cache. `check_floor_range` (119 l.) checks whether the per-combo
P(call) of the action-consistent tracker lies closer to the solver's true post-call range than the
`_narrow` heuristic. `danger_pair` (49 l.) builds class-dense arms for RARE levers that are invisible on normal
1500-hand sets. `duplicate_mode_ab` (92 l.) runs HEAD against GTOW mode on
MIRRORED decks against `GTOBaseline` — free, without network, card luck cut twice.
`theory_duel` (59 l.) sets the bot against the two in-engine embodiments of poker theory.
`flop_pilot` (88 l.) measures what ONE flop-to-terminal solve really costs to convergence.
**Input/Output.** Cache/logs/seeds in; candidate lists or paired deltas out
(`flop_pilot` into `data/research_sweep/flop_pilot.json`).
**Dependencies.** Hard: `GTOBaseline` and the solver cache; `blindspot_radar` additionally an LLM API.
**Status.** Stateless.
**Cost.** `flop_pilot` measures it: the predecessor `research/flop_feasibility.py` capped at 300 s and
got 49 of 50 timeouts (`flop_pilot.py:4-5`).
**Measurement status.** MEASURED NEGATIVE for the LLM triage: `blindspot_radar` is a hypothesis generator; it
REFUTED its own top marking by measurement (memory `blindspot-radar-and-verify`); the solver is
the linchpin verifier, play tests are too noisy for single rules. The rest: UNMEASURED as
levers.
**Usable standalone?** `grounded_blindspots` and `duplicate_mode_ab` yes, with cache or baseline respectively.
**Pitfalls.** `duplicate_mode_ab` measures against `GTOBaseline`, not against GTOW. The
autogym doctrine (CLAUDE.md) is hard here: such channel results are called `KANAL_*` and are NEVER
ship evidence.

---

---

## G — `research/`: tournament and MTT

### PS tournament field and duel (group) — `research/{ps_tourney_field,ps_tourney_duel}.py`
**Purpose.** Measure a real high-stakes tournament field BY PHASE and let our own tournament arms
compete against it — the core trick: the measured frequencies of the pool ALREADY CONTAIN its ICM behaviour,
instead of simulating it.
**Interface.** `ps_tourney_field` (125 l.): `_phase(eff_bb) -> str` (deep >40bb / mid 15-40 / short
<15), `parse() -> dict`, `main()`. `ps_tourney_duel` (202 l.): `_hand_class(hole)`, `_phase(eff_bb)`,
`make_hero(arm)` with the three arms `chipEV` (tag core pure), `icm` (tag + ICM lens: proportional
risk premium + exact all-in threshold) and `icm+druck` (plus the cover-stack pressure lever + live reads),
`run_one(structure, arm, seed, field_kind="freq")`, `main()`.
**Input/Output.** Input: PokerStars tournament hand histories under `data/ps_tourney/hh/**/*.txt`.
Intermediate format: `data/ps_tourney_field.json` with the key `phasen` (per phase VPIP, FoldVsRaise,
jam share). Output of the duel: ROI/ladder per arm under two payout regimes (`sng65_35` and
`winner_take_all`).
**Dependencies.** Hard: `arena.sixmax.PROFILES`/`SixMaxBot`, `strategy.preflop_strength`,
`strategy.tournament` (`BlindLevel`, `Director`, `Structure`) — and for the duel mandatorily the JSON file
produced by `ps_tourney_field`.
**Status.** `ps_tourney_duel` loads `FIELD` at IMPORT (module level, line 33) — if the file is missing, the
import already fails. Paired seeds per tournament.
**Cost.** Not measured.
**Measurement status.** MEASURED POSITIVE as evidence of the field's ICM tightness: the $1050 measurement shows
FoldVsRaise 54% -> 62% and jam 1.1% -> 13.1% from deep to short (CLAUDE.md, pillar 2). The corresponding
lever itself (proportional risk premium in `strategy/tournament.py`) is separately validated paired:
+10.0 ± 5.0 pp ROI at n=1500, 95% band [+0.2, +19.9] — the FULL bubble factor on the other hand was REFUTED
(−8pp, bubble bleed-out). Those numbers belong to `tournament.py`, not to these two files.
**Usable standalone?** `ps_tourney_field` yes, if you have PokerStars tournament histories — it is a pure
parser. The duel needs the whole tournament layer.
**Pitfalls.** The phase is approximated via effective stack depth in bb, NOT via the number of
remaining players — the docstring calls that a deliberate approximation, because players-remaining cannot be
reconstructed across tables from hand histories. Under `winner_take_all` ICM is by definition
equal to chipEV; whoever measures an ICM gain there measures a bug.

### Tournament simulations (group) — `research/{mtt_sim,mtt_report,tonight_sim,turnier_live,turnier_replay}.py`
**Purpose.** Five scenario simulations and evaluations around tournaments: a 600-player MTT, the
campaign pooling, a 60-player freezeout, the measurement of a running tournament
and the replay of a logged 88-hand tournament through the engine.
**Interface.** `mtt_sim` (383 l.) simulates the $1050/$600k event; `mtt_report` (78 l.) pools the
worker JSONs and computes the PAIRED verdicts; `tonight_sim` (464 l.) the 60-player freezeout with 50k start,
10-handed tables and a limpy field; `turnier_live` (270 l.) measures what
was actually played; `turnier_replay` (422 l.) runs Prince v2 (GTO) and the exploit layer over
the same hands.
**Input/Output.** Structure/field parameters or hand histories in; ROI/ladder JSON out.
**Dependencies.** Hard: `strategy/tournament.py`, `strategy/icm.py`, `arena/sixmax.py`.
**Status.** Per run; `mtt_report` presupposes that several workers wrote into the same directory.
**Cost.** Not measured.
**Measurement status.** UNMEASURED as a lever (scenario tools). The validated tournament number hangs on
`strategy/tournament.py` (see above), not on these simulations.
**Usable standalone?** No.
**Pitfalls.** Simulated fields are constructed. `mtt_report` is the only module of the group that
computes paired verdicts — numbers from the other four without this pairing are scenario descriptions,
not measurements.

---

## H — `research/`: vision (PokerSnowie)

### Glyph collector — `research/snowie_collect.py`
**Purpose.** Teaches the local recognition the card and digit deck ONCE: clicks bluntly through
play-money hands and stores every glyph the template matching does not yet know.
**Interface.** `_collect(sub, kind, seen, bright) -> bool` stores an unknown glyph (True = new),
with dedup against already collected ones by the same metric as the recognition; `run(iters, pause)` the
collection loop; `main()` with `--iter`, `--pause`.
**Input/Output.** Input: the running PokerSnowie 4 cash table on screen. Output: PNG files
under `SL.DUMP_DIR/{rank_b,rank_h,digit}/` (board ranks, hero ranks, digits) plus, at every opportunity,
evidence images of the amount field under `.../bet/soll_<value>_<n>.png`. At the end it prints median/min/max of the
amount-entry time in milliseconds.
**Dependencies.** Hard: `pokerbot.vision.snowie_local` (regions, `grab`, `crop_frac`, `match`,
`_binary`, `_score`), `pokerbot.vision.snowie_state` (`_binary_bright`, `number_fields`, `_digit_boxes`,
`match_digit`, `hero_turn`), `pokerbot.vision.snowie_bridge` (`_click_frac`, `_type_number`, `window_box`),
`PIL`, `numpy`. And: an actually open PokerSnowie window.
**Status.** Per run. The `seen` dictionary is preloaded at the start from the EXISTING templates so that
known glyphs are not collected again. Reset = empty the dump directory.
**Cost.** One screen grab plus template comparisons per round, default pause 0.45 s; absolute values not
measured. It MEASURES the amount-entry time itself at runtime (no value stored in the repo).
**Measurement status.** UNMEASURED. The module is explicitly "NOT play and NOT a measurement" (docstring line 3).
What hangs on it is measured: the bridge as a whole plays 13.3 hands/min with ~4% dropouts, and the
cleaned pool of 3,114 clean hands gave +3.2 bb/100 [−37, +44] (CLAUDE.md, pillar 1).
**Usable standalone?** Only with the whole `pokerbot/vision` package and PokerSnowie. But it is STEP 1
of the chain — without it the recognition cannot be set up anew on a new machine or theme.
**Pitfalls.** `DEDUP_MIN = 0.82` is the whole difference between "deck learned" and "dozens of copies
of the same character". And the constant `AMOUNT_BOX = (1766, 1234, 1878, 1282)` is a LIVE-MEASURED
pixel coordinate — at a different resolution or window the module types into the void without
complaining. The collected glyphs must afterwards be labelled BY HAND (the last line of the
run says where).

### Snowie watchdog and recorder (group) — `research/{snowie_marathon,snowie_record}.py`
**Purpose.** Get a multi-hour Snowie run through at all (stage watchdog) and make it
verifiable (screen recording).
**Interface.** `snowie_marathon` (109 l.): `hands_in(files) -> int` recounts the PLAYED hands
(hole-card changes with at least one decision) from the session logs; the loop starts the
bridge in stages of `CHUNK_HANDS = 150` with `PAUSE_S = 20` pause and gives up after
`MAX_BARREN_CHUNKS = 5` stages without a new hand. `snowie_record` (53 l.): `run(seconds)` records the
table with `FRAME_S = 0.25` (4 frames/s) as JPEGs with `JPEG_Q = 70` (~120 KB/frame) into
`data/vision/rec/<timestamp>/`; the file name carries the Unix time in milliseconds — the same clock as
the decision log, so every decision can be matched to the nearest frame.
**Input/Output.** Session logs or screen in; stage reports or frame sequences out.
**Dependencies.** Hard: `pokerbot.vision.snowie_bridge` (the marathon starts it as a subprocess, the
recorder uses `esc_pressed`), `snowie_local.grab`.
**Status.** The marathon's counter is DELIBERATELY not in the process but reconstructed from the logs
— that is why it survives the death of a stage. Stop via the file `data/vision/STOP`.
**Cost.** Recorder: ~120 KB per frame at 4 frames/s (from the constants, justified in the code as "hours fit on
the disk").
**Measurement status.** UNMEASURED (operational tools). The marathon construction is the reason why
3,651 hands in three runs came together at all (CLAUDE.md, pillar 1).
**Usable standalone?** The recorder almost (it needs only `grab` and an ESC query). The marathon is bound to
the bridge's log format.
**Pitfalls.** ESC ends only the RUNNING stage; the watchdog waits afterwards and continues if the
STOP file is missing (docstring lines 8-10). Whoever wants to "end" the run via ESC in truth restarts it.

---

## I — `research/`: net/RL remnants and small tools

### RL/net remnants (group) — `research/{deep_cfr_nlhe,openspiel_leduc,distill_improve,eval_lora,llm_probe,llm_exploit_demo,teacher_serverless_client,pod_run30}.py`
**Purpose.** Eight leftovers of the net and LLM phases: neural Deep CFR on abstracted HUNL, the
OpenSpiel validation on Leduc, a local distillation improver, the holdout evaluation of a LoRA,
two LLM probes, the client for the serverless teacher and a 30-minute pod orchestrator.
**Interface.** `deep_cfr_nlhe` (111 l.) runs neural Deep CFR on OpenSpiel `universal_poker`
(fcpa) on the GPU pod. `openspiel_leduc` (55 l.) measures the exploitability of OpenSpiel's Deep CFR on
Leduc — a low `nash_conv` proves that the neural solver converges. `distill_improve` (40 l.)
improves the distillation net locally via minibatching (the full-batch baseline underfits ~328k examples,
because it makes only `epochs` gradient steps in total). `eval_lora` (66 l.) measures action
agreement on UNSEEN PokerBench rows (constructed disjointly via the same loader with
`shuffle(seed=0)`). `llm_probe` (18 l.) and `llm_exploit_demo` (29 l.) check what the local LoRA
actually outputs and demonstrate the chain directive -> `directive_to_nudge` -> capped adjustment, respectively.
`teacher_serverless_client` (132 l.) fires generation jobs at the serverless endpoint and appends the
engine-GATED examples to `data/teacher_raw.jsonl`. `pod_run30` (80 l.) is a time-capped
distillation orchestrator with LLM-driven curriculum.
**Input/Output.** Depending on the module: OpenSpiel games, PokerBench rows, LoRA adapters, endpoint answers.
**Dependencies.** Hard and heavy: OpenSpiel, `torch`, `peft`/`transformers`, a RunPod endpoint.
**Status.** Per run.
**Cost.** GPU time; not measured.
**Measurement status.** REFUTED as a product path: the fcpa policy net of this family reached −212 bb/100
(CLAUDE.md) and `04_solver.md:580` explicitly fences off the whole Deep-CFR family. `openspiel_leduc`
is UNMEASURED in the repo as a METHODOLOGY validation (no stored `nash_conv`). The imitation ceiling is
the summarising lesson: TRAINING a small model on our data cannot outperform us.
**Usable standalone?** `openspiel_leduc` yes (it depends only on OpenSpiel and is a clean
convergence test). The rest is project-interwoven.
**Pitfalls.** These modules look like a way forward and demonstrably are not. Whoever adopts them
should first read `04_solver.md:580` and the −212 finding.

### Knowledge and formula tools (group) — `research/{consolidate_exploit,postflop_calc_gate,postflop_calc_materialize,md_to_pdf,pdf_peek,peek_pb}.py`
**Purpose.** Six small tools: merge exploit primitives, gate LLM-generated postflop calculations
against the engine and materialise them, a Markdown-to-PDF
renderer and two file peekers.
**Interface.** `consolidate_exploit` (65 l.) deduplicates and normalises the book-extracted
exploit primitives into ONE database, keyed by the MEASURABLE opponent statistics of the bot ->
`knowledge_base/exploit/unified.json`. `postflop_calc_gate` (77 l.) is the EV truth filter for pure
mathematics: for every specification `python_function` is executed, `verify_expr` evaluated, and only
what passes remains. `postflop_calc_materialize` (63 l.) casts the verified calculations into ONE
importable module `knowledge_base/math/postflop_formulas.py` and afterwards verifies ALL TOGETHER
(catches name collisions that the individual check does not see). `md_to_pdf` (96 l.) renders simple Markdown to A4 PDF (German-safe: Helvetica/
WinAnsi covers umlauts, ß, em dash, typographic quotation marks). `pdf_peek` (36 l.) pulls a
page range as text; `peek_pb` (9 l.) loads PokerBench train and shows three real preflop rows.
**Input/Output.** JSON specifications, Markdown, PDFs.
**Dependencies.** Largely self-contained; `postflop_calc_*` needs the formula collection.
**Status.** Stateless.
**Cost.** Negligible; not measured.
**Measurement status.** MEASURED POSITIVE for `consolidate_exploit` as a condensation: 262 exploit primitives plus
95 AGT concepts from five books, deduplicated to 62 stat-keyed, wireable rules
(`docs/STATE.md:1745-1747`). The rest: UNMEASURED.
**Usable standalone?** `md_to_pdf` and `pdf_peek` immediately and without project reference. `postflop_calc_gate` is
valuable as a PATTERN: LLM proposal -> execute -> check assertion -> keep only what passes.
**Pitfalls.** `postflop_calc_materialize` deliberately verifies TWICE (individually when gating, jointly
when materialising) — whoever drops the second pass does not catch name collisions.

### Frontier consults (table) — `research/*_consult.py` and relatives
Forty one-off scripts following ONE pattern: one (or a few) LLM queries with a fixed question stated
in the docstring; result as Markdown or JSON into `knowledge_base/` or `docs/`. They have NO
importable interface except `main()`, are stateless, cost API credit and are as levers
uniformly UNMEASURED — what they deliver is a GATED PRIOR, never a training label (CLAUDE.md:
"the engine is TRUTH, the frontier a GATED PRIOR"). The pitfall is the same for all forty: the
answers sit as prose in the repo and READ like findings; the pattern with the gate is described in
`12_wissen.md` at `research/konsult_sol.py`, and `research/perplexity_search.py` carries the
project's hard warning (CLAUDE.md: Perplexity scrambles metadata — NEVER cite unverified).

| Path | one line |
|---|---|
| `research/alpha_consult.py` | Frontier query on alpha/bluff-frequency theory. |
| `research/cfr_papers_consult.py` | Which CFR papers are relevant for us. |
| `research/cfr_tips.py` | Practical CFR implementation hints. |
| `research/exploit_gto_bridge.py` | Bridge between exploit rules and GTO base. |
| `research/exploit_synthesis.py` | Synthesis of the exploit primitives from the books. |
| `research/gto_frontier_consult.py` | State of the GTO research frontier. |
| `research/gto_hybrid.py` | Hybrid of GTO floor and exploit overlay. |
| `research/gto_shortcut.py` | Are there shortcuts to GTO quality. |
| `research/grand_synthesis.py` | Overall synthesis of all extracted knowledge sources. |
| `research/hard_spots_consult.py` | Second opinion on the hardest spots. |
| `research/landscape_consult.py` | Map of the poker-AI landscape. |
| `research/math_theory_consult.py` | Mathematical theory follow-up questions. |
| `research/mathematics_of_poker.py` | Targeted extraction from *The Mathematics of Poker*. |
| `research/nash_consult.py` | Nash-equilibrium questions for 6-max. |
| `research/nash_keyword_consult.py` | Keyword-driven Nash literature query. |
| `research/nextrun_consult.py` | What should run next. |
| `research/orchestrate_consult.py` | Orchestration of the two-node pipeline. |
| `research/phase1_consult.py` | Planning query on phase 1. |
| `research/phase5_math_check.py` | Maths cross-check for phase 5. |
| `research/poker_for_compute.py` | Where compute pays off most in poker. |
| `research/postflop_calc_consult.py` | Generates the postflop calculation specifications (gate: `postflop_calc_gate`). |
| `research/postflop_openai.py` | Postflop strategy playbook via OpenAI. |
| `research/qwen_train_consult.py` | Training recipe for Qwen. |
| `research/range_tracker_consult.py` | Design questions on the range tracker. |
| `research/river_consult.py` | River-system specification (source of `river_coherence`). |
| `research/rl_consult.py` | RL recipe and reward design. |
| `research/runpod_gto_consult.py` | Pod use for GTO computation. |
| `research/shortdeck_consult.py` | Short-deck particularities. |
| `research/simplify_consult.py` | Where to simplify instead of adding. |
| `research/situational_consult.py` | Situational play questions. |
| `research/solvability_proof_consult.py` | Is 6-max solvable (result: PPAD-hard, see memory). |
| `research/solvability_query.py` | Short form of the same question. |
| `research/strategy_to_formula_consult.py` | Translate strategy text into formulas. |
| `research/surfing_consult.py` | *Surfing Uncertainty* -> value-of-computation arbiter. |
| `research/synthesis_consult.py` | Synthesis query across several sources. |
| `research/theory_qa.py` | Free theory Q&A round. |
| `research/wso_consult.py` | Tournament/WSO-related query. |
| `research/math_audit.py` | OpenAI audit of `knowledge_base/math/formulas.py` (honestly declared as a review, not as confirmation). |
| `research/fable5_bot_audit.py` | Audit of the bot through the fablize discipline lens. |
| `research/perplexity_search.py` | Search-backed research — metadata unreliable, never cite unverified. |
| `research/venice_models.py` | Lists Venice.ai models (key kept out of the output). |
| `research/probe_apis.py` | Checks both API keys and resolves the best OpenAI model. |

---

## J — Corrections to parts 01–12

These points sit here because an outside developer would otherwise read two contradictory statements.

1. **`research/k3_roots.py` carries a foreign grade in `04_solver.md:473`.** The collective entry awards
   `river_br_pruefstand`, `policy_oracle` AND `k3_roots` jointly "MEASURED POSITIVE … controls 15/15
   green". The controls belong to the test bench and the oracle. `06_v10.md:466` is right for the same module:
   UNMEASURED (data preparation).
2. **Four modules have opposite measurement labels in two parts** (resolvable in substance, contradictory
   in print): `pokerbot/arena/sixmax.py` (03 UNMEASURED as an isolated lever / 09 MEASURED POSITIVE
   85.9% GTO score, EV loss 7.61), `pokerbot/autogym/stats.py` (05 MEASURED POSITIVE as a correction / 07
   UNMEASURED as a standalone lever), `research/golden_set.py` (06 passed as a tool / 12
   UNMEASURED as a number), `research/mass_solve.py` (04 UNMEASURED as an EV lever / 12 MEASURED NEGATIVE as
   training gold). BOTH are correct in each case, but only with the qualifier "as what".
3. **Name collision `mass_solve`.** Part 12 attributes the 25,586 excluded `solver_mass` rows to
   `research/mass_solve.py`; per the same chapter they were produced by
   `dataset/build/from_solver.mass_solve(...)`. Two different things with the same name — keep them apart when
   rebuilding.
4. **Two line references overshoot the end of the file** (content is correct in each case): `04_solver.md:68/:237/:375`
   points to `../NOTES.md:712-726`, `../NOTES.md` has 724 lines; `07_messung.md:65` points to
   `stats.py:93-110`, `pokerbot/autogym/stats.py` has 109 lines (both recounted today).
5. **The cache size is a snapshot, not a fixed value.** Part 04 cites for `data/_solve_cache`
   12,209 entries / 35 GB (measured 2026-09-10); at the time of writing this addendum it was 12,493 files.
   The cache grows with every run.
6. **Dead start instructions in the docstrings.** 86 modules in `research/` and `infra/` carry
   `python -m extraction.<module>` in their docstring. The package `extraction/` no longer exists (today `research/`). Each
   of these lines is a wrong instruction — all start commands named in this addendum were corrected to
   `research.`/`infra.`. Affected are, among others, `infra/runpod_run.py`,
   `research/preflop_solve.py`, `research/build_*_data.py`, `research/pdf_peek.py`.
7. **Missing cross-reference.** `04_solver.md:580` correctly fences off `deep_cfr.py`, `deep_cfr_hunl.py` and
   `deepstack_leduc.py`, but does not point to `pokerbot/valuenet/gate0_leduc.py`, which
   USES `deep_cfr.py` as its foundation (`State`, `vanilla_cfr`, `exploitability`).

---

## K — Rightly missing (table only)

| Path | one line | Reason |
|---|---|---|
| `pokerbot/__init__.py` | Package docstring with subpackage overview, `__version__ = "0.1.0"` (11 l.). | Trivial, no behaviour. |
| `pokerbot/coach/__init__.py` | Re-export of `Coach`, wrapped in `try/except` so the trainer modules stay importable without `anthropic` installed (11 l.). | Trivial; the one non-obvious line is the import guard. |
| `pokerbot/autogym/__init__.py` | Docstring with the four-part split of the autogym + entry point `python -m pokerbot.autogym.run_local` (10 l.). | Trivial. |
| `pokerbot/valuenet/__init__.py` | 0 bytes. | Pure package marker. |
| 12 further `__init__.py` | 0–1 lines. | Pure package markers. |
| `pokerbot/benchmark/{beat_them_all,calibrate,exploit_proof,floor_ablate,floor_map,gto_benchmark,pluribus_leaks,preflop_ab,range_tracker_ab,sixmax_gap,probe,weaponize,runpod_train}.py` | 13 benchmark drivers. | Deliberately kept as a table in `08_benchmarks.md:738`; directory thereby complete (17 full entries + 13 rows). |
| `research/{claude_brain_smoke,claude_export,claude_vs_engine,glm_local_probe,teacher_generate}.py`, `infra/gtow_glm_pod.py`, `research/llm.py`, `pokerbot/strategy/postflop_corset.py` | 8 signposts of the brain track. | Declared in `11_brain.md:608`; `postflop_corset` is MEASURED NO-OP. |
| `research/{gtow_nacht,gtow_nacht_v10,gtow_ab,gtow_xray,gtow_tail,analyze_gtow_hands}.py` | 6 GTOW drivers. | Declared in `08_benchmarks.md:759` — worthless without our researcher access and our hand budget. |
| all 12 `dataset/build/*.py` | The converters knowledge -> DSL. | Fully covered by the collective entry `12_wissen.md:330`, each with `build()` signature. |
| `pokerbot/strategy/{deep_cfr,deep_cfr_hunl,deepstack_leduc}.py` | 1,232 lines of self-play/net learning path. | Explicit fencing-off in `04_solver.md:580` (no re-solving at decision time); `deep_cfr.py` is, however, the hard dependency of `valuenet/gate0_leduc.py` (see correction 7). |
| `research/{runde4,runde5,runde5b,g4_auswertung,g5_*}.py`, extraction pipeline, exploit overlays, `analysis/*`, `coach/*` | Campaign and pipeline families. | Covered by group headings in parts 05/07/10/12. |
