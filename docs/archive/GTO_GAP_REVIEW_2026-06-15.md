# The path to 100% GTO — code review & improvement ladder

*Written 2026-06-15 after a complete pass through the decision engine. Ordered by leverage
toward GTO, not by effort. Reads as a companion to `../NOTES.md` (the measured gaps) and
`docs/STATE.md` (the live state).*

---

## 0. The honest framing first (otherwise the rest aims at nothing)

**"100% GTO" is two different things for the bot's two modes:**

- **Heads-up NLHE:** GTO is a well-defined object (an equilibrium unique in value). But
  nobody has ever reached it *exactly* — Slumbot, DeepStack, Supremus are all approximations. The
  realistic target is **"indistinguishable from GTO within measurement accuracy"** = near-zero
  LBR exploitability. That is achievable.
- **6-max:** GTO is **unreachable in principle** — multiplayer general-sum ⇒ Nash PPAD-hard,
  not unique, no-regret converges only to a CCE, not Nash (already stated in
  `data/sessions/solvability_6max.md`). Here "100% GTO" is the wrong target; the right one is
  **bounded exploitability**. This report therefore deals primarily with HU.

**The one sentence everything comes down to:** GTO is a *globally coupled fixed point* — the ranges
must be consistent across the whole game tree. One **cannot approach GTO through better local
heuristic tuning**, because every local decision depends on a correct range, which itself
follows from the equilibrium. GTO is reached only when the strategy becomes *a single
self-consistent object*. In practice that means exactly one of two paths:

1. **Real-time subgame re-solving with correct ranges** (the DeepStack/Supremus path) — in the repo already
   **laid out as `strategy/resolver.py`, but unfinished + OFF by default**.
2. **An offline-trained self-play blueprint** (Deep-CFR / CFVnet) — in the repo scaffolded as `deep_cfr.py`,
   deliberately deferred.

The current bot is a **heuristic floor + supervised advisors + exploit layer**. That is a
good, honest construction — but it is *structurally* not a GTO strategy and can never become one
through tuning. The measured **−160 ±75 bb/100 (paired) against the solver oracle** (NOTES,
"DEFINITIVE TexasSolver head-to-head") are not an "almost GTO with small leaks", but the
expected distance of a heuristic from the equilibrium.

The good news: the repo has already recognized the right path and partly built it. The
**river resolver has already measured −12.9 ±69.6** (NOTES MVP#2) — by far the most
GTO-near result in the whole project. The rest of this report is, at its core: *finish this path*.

---

## 1. The keystone weakness: the villain range is not a range

This is the single most important thing in the whole bot, because **everything postflop stands on it.**

In [`strategy/bot.py`](../../pokerbot/strategy/bot.py) `_villain_range` (l. 481) + `_narrow` (l. 502):

```python
def _villain_range(self, state):
    raises = self._preflop_raises(state)
    if raises >= 3:   return ps.range_top(0.10)
    if raises == 2:   return ps.range_top(0.20)
    ...
def _narrow(self, classes, board, hole, aggression):
    ...
    keep_frac = {0: 0.92, 1: 0.60, 2: 0.38}.get(aggression, 0.30)
    ranked = sorted(combos, key=lambda c: evaluate(board, list(c)))  # by absolute strength
    return ranked[:n]
```

That is **"the strongest X% of hands by absolute board strength"** — not a poker-theoretic range. Consequences
that distort every single postflop number:

- **No bluffs in the villain range.** Under aggression `_narrow` keeps only the *strongest* combos.
  So the model believes: *whoever bets on the turn/river always has value.* → The bot **over-folds
  bluff-catchers** (it thinks it is never facing a bluff) and **under-bluffs itself** (it thinks
  villain always calls with value). That is exactly the class of leak named in the −160 head-to-head
  as the main bleed, "facing-bet DEFENSE / turn-river LINES".
- **No draws weighted, no action lineage.** A real range arises from the actions
  (open → call → check-raise …), not from a static strength percentile.
- **The equity (`equity_vs_range`) is mathematically clean, but against the wrong distribution** →
  every MDF/pot-odds/value threshold after it is built on sand.

**Fix (the foundation for almost everything else):** a **Bayesian action-consistent range tracker** —
start from the preflop ranges, then per betting action a Bayes update over the
blueprint/solver policy (P(action | hand) weights the combos). That is exactly the still-missing postflop
narrowing stage marked in [`strategy/range_tracker.py`](../../pokerbot/strategy/range_tracker.py) as the
"P0-proper refinement". Today `range_tracker` is **only preflop-line-aware**
(SRP → sb_open/bb_defend; 3bet → top 18%). Without this stage **neither the advisor nor the resolver
can be GTO.**

> Without correct ranges, "more GTO" is impossible. With them, half of the other points fall out
> by themselves. **This is the highest lever in the project.**

---

## 2. Switch on the real GTO path: the resolver

[`strategy/resolver.py`](../../pokerbot/strategy/resolver.py) is the actual path to postflop GTO and
already well built: it solves the **actual public river state live with TexasSolver to the
terminal** (river = 1 betting round ⇒ **no value net needed**, cleanly exact). In `bot.py`, however:

```python
self.use_resolver = False        # l. 82 — river resolver OFF
self.use_turn_resolver = False   # l. 83 — turn resolver OFF
```

Two things block it:

1. **The ranges that go in are wrong** — `river_ranges()` delivers only preflop-line ranges (again
   the problem from §1). So the resolver solves the *right board with ranges that are too wide* → it returns
   the GTO strategy for a *different game*.
2. **It is off by default** (rightly so, as long as #1 is open).

**Fix (the direct −160 → ≈0 path):**
- First build §1 (correct continuation ranges), then feed them into `river_ranges`.
- `use_resolver=True` (river first — exactly solvable, cleanest win), then `use_turn_resolver=True`
  (turn→river subtree, bigger tree, slower).
- Gate via AIVAT / the paired `gto_oracle_match`. NOTES MVP#2 has already measured the river resolver at **−12.9**
  — that is the proof that this path carries.
- Latency live: a river solve is ms–s; a turn solve is more expensive. For a pure GTO machine, possibly caching by
  board bucket + line.

**This is concretely the transition from "a heuristic that imitates GTO frequencies" to "spot-specific GTO".**

---

## 3. Facing-bet defense & sizing — where the bb/100 really bleed

NOTES says explicitly: the deterministic GTO gap (31% flop / 29% river) is **frequency-faithful** —
our bet-vs-check *frequencies* match the solver. But: *"the gap measures only bet-vs-check at the
lead/cbet nodes; it does NOT capture SIZING / facing-bet DEFENSE / turn-river LINES, where the real EV
leak sits."*

In the code you see exactly that:

- **The advisor fires only on bet-vs-check nodes** (flop/turn/river, first-to-act/after-check). **When
  the bot is *facing* a bet**, the heuristic runs: `call_thresh = req + MDF-shade`, value raise from
  `eq ≥ 0.72`, otherwise fold (`bot.py` l. 290–328). I.e. the "GTO-grounded" part covers **betting, but
  not defending.** Defending is half the game and here purely heuristic.
- **Sizing does not mix.** GTO uses several sizes with frequencies; the bot bluff-bets a fixed ~60% pot,
  value via `pick_value_size`. NOTES leak #2: *"fold-equity-optimal sizing ≠ EV-optimal"* — `max(folds)`
  is not `max(EV)`.
- **The MDF shade is possibly not EV-grounded** (NOTES leak #3): MDF is the wrong model against underbluffers.

**Fix:** Falls largely out of §1+§2 — as soon as the resolver runs with correct ranges, the
facing-bet answer and the sizing *are* the GTO answer (mixed, range-vs-range). Until then it remains a
heuristic that by construction cannot be GTO. **Do not tune away individually — replace it with the resolver.**

---

## 4. Preflop is not GTO (and the best table is not even wired in)

Surprising finding during the pass:

- **Push/fold (≤14bb)** in [`cfr_preflop.py`](../../pokerbot/strategy/cfr_preflop.py) is real MCCFR-Nash —
  **but only of the JAM/FOLD abstraction game.** It models *only* all-in or fold. Real GTO at 14bb
  contains min-raises, limps, non-all-in 3bets. Pure push/fold is only really GTO-near up to ~10bb.
- **Deeper stacks (>14bb)** in `bot.py` `_preflop` (`_bb_vs_open`, `_vs_3bet`, `_deep_reraise`) are a
  **percentile-strength heuristic system** with *fixed* sizings: 2.5bb open, 3.2× 3bet, 2.3× 4bet, fixed
  value/bluff frequency bands. No size mixing, no GTO frequencies.
- **The distilled 88.6% PokerBench table** ([`preflop_gto.py`](../../pokerbot/strategy/preflop_gto.py))
  is, per its own docstring, **wired only into the 6max RFI — not into the HU `bot.py`.** So the HU bot
  uses its weaker heuristic although the better table sits in the repo.

**Fix:**
- Wire `preflop_gto.py` into `bot.py._preflop` and extend it with vs-open / vs-3bet / vs-4bet (keys with
  the preflop action sequence, as noted in the docstring as "Step 4b").
- Medium stacks: real preflop solves with open-size + 3bet/4bet trees and **mixing**, instead of fixed
  sizes.
- Push/fold: either extend the CFR game with min-raise/limp lines, or document that it is only
  ≤~10bb GTO.

---

## 5. The advisors: an approximation path, not a GTO path

The MLP advisors ([`strategy/advisor.py`](../../pokerbot/strategy/advisor.py)) are clean glue over real
solver data and sensible. But as a GTO mechanism they have a **ceiling**, and the reason is in the
features ([`strategy/features.py`](../../pokerbot/strategy/features.py)) + NOTES leaks #1/#5:

- **The info set is too coarse.** `_vector` encodes: tier (air/medium/strong), 5 textures, role IP/OOP,
  a few draw booleans, overcards, scalar strength. **No** line, **no** SPR, **no** pot type
  (SRP vs 3bet pot), **no** range asymmetry. → K72r in a BTN-vs-BB SRP is averaged with K72r in a 3bet pot into
  *one* info set (NOTES leak #1). GTO treats those completely differently.
- **Trained on P(bet)/MSE, not on reach-weighted EV gap** (NOTES leak #5): a net can match the
  *frequency* and still bleed at rare high-EV-gap nodes. A frequency match
  is *not* GTO.
- **Coverage limited:** flop net from full coverage, turn from only 46 flop files (+ ongoing solve),
  river 1308 boards. 3bet pots, several stack depths are missing entirely.

**Fix (if the advisor path is pursued further):** line/SPR/pot type/position as features;
loss = reach-weighted EV gap instead of MSE; solver coverage campaign (RunPod/GCP mass-solve) for 3bet pots
+ stack depths. **But honestly:** a supervised advisor *approximates* GTO, it never *is* it. For "100%"
it is the second-best track behind the resolver/self-play. Sensible as a fast, broad floor and
as a fallback when the resolver cannot solve a line.

---

## 6. Verification — without it every GTO claim is worthless

One cannot *claim* "close to GTO", only *measure* it. The measurement discipline in the repo is excellent
(paired/duplicate, AIVAT-aware, noise floors, Skinner-aware reverts — see `scorecard.py`,
`duplicate.py`). Two gaps remain, both block a robust GTO proof:

- **LBR is only v1 and range-blind** (NOTES "Move A"): the uniform card-resampling variant *does not see a
  corrupted range* (injected c-bet air/river overbluff → paired delta ~0 despite 99/300
  firings). Real GTO ⇔ near-zero exploitability, and only a real best response certifies that.
  **Fix: LBR v2** — Bayesian action-consistent range + multi-street best response. That is the *only
  internal* instrument that can quantify "how close to GTO" without an external key. (Depends on §1 again.)
- **GTO Wizard key is 401** (`benchmark/gtowizard.py` is finished + offline-tested, blocks only on a
  valid key). AIVAT vs GTOW-AI is the definitive external yardstick. **Fix:** obtain a valid key,
  then `--num-hands 2500` for the leaderboard number. (User decision — outward-facing, consumes quota.)

---

## 7. Smaller, concrete code observations (correct, but lower leverage)

- **Equity noise:** `EQUITY_ITERS=1500` live, **120 in benchmarks** (`floor_map`, `gto_oracle_match`). 120
  MC samples flip thin pot-odds decisions — exactly such a bug was already found on the river and
  fixed by exact enumeration (`equity.py` l. 49–57). Flop/turn are still MC. Consider: suit-canonical
  equity cache (listed as "Simplify Tier-A" in STATE.md) and higher bench iters for decision-grade runs.
- **The exploit layer is correctly GTO-neutral.** The LCB gate (`exploit_engine.choose_river`) falls back
  to the floor on thin data (`cold-start → floor`), so it does *not harm* GTO proximity — it is
  orthogonal. Important: against a *real* GTO opponent there are no exploitable folds, so the gate stays
  at the floor. Good. (For "100% GTO" one would switch the exploit layer off anyway — it is the
  *anti*-GTO track for the exploitable field population. The two goals "GTO" and "max-exploit" are
  different knobs; the bot separates them cleanly via `exploit=True/False`.)
- **`value_raise_eq=0.72` + fixed 0.8×pot value raise** (`bot.py` l. 307–311): point estimate, no
  mixing — replaced by the resolver.
- **`_has_initiative` is preflop-derived only** (l. 469): correct for SRP, but in more complex lines
  (float, delayed c-bet, probe) "initiative" is not a boolean. The resolver does not need the concept at all.

---

## 8. The ladder — ordered by leverage toward GTO

| # | Step | Why it is GTO leverage | Depends on |
|---|---------|------------------------|----------|
| **1** | **Bayesian action-consistent range tracker** (postflop continuation narrowing in `range_tracker.py`) | Foundation: without correct ranges *nothing* is GTO. Fixes equity, defense, bluff-catching in one. | — |
| **2** | **Switch on the resolver** (river, then turn) with the correct ranges from #1; AIVAT-gated | *The* real postflop GTO path; river exactly solvable; already measured −12.9 | #1 |
| **3** | **Facing-bet defense + sizing** via the resolver instead of the heuristic | Where the −160 really bleed (NOTES) | #1, #2 |
| **4** | **Wire in preflop GTO** (`preflop_gto.py` in the HU bot; vs-open/3bet/4bet; mixed sizes) | HU preflop is currently heuristic; the better table is not even wired | — |
| **5** | **LBR v2** (range-aware, multi-street) | The only internal instrument that *certifies* GTO proximity | #1 |
| **6** | **Widen the advisor info set** (line/SPR/pot type; EV-gap loss) + solver coverage campaign | Makes the approximation track + the fallback better | coverage compute |
| **7** | **GTO Wizard key** → AIVAT leaderboard | Definitive external GTO yardstick | valid key (user) |
| **8** | **Self-play blueprint** (Deep-CFR/CFVnet, Leduc→NLHE) | The *other* principled GTO path; expensive, hence last | RunPod GPU |

**If only ONE thing is done:** #1 (range tracker). It is the keystone that makes #2/#3/#5 possible in the first
place and on its own already corrects every postflop number.

**The realistic "as close to GTO as HU allows" path:** #1 → #2 → #3 → #5 (gate) → #4. That plausibly brings the
measured distance from −160 toward ≈0 vs the solver and makes the claim *verifiable*.

---

## 9. Conclusion in three sentences

1. The bot is a *clean, honestly measured heuristic with an exploit layer* — but structurally **not** a
   GTO strategy, and no amount of local tuning makes it one; GTO is a globally coupled
   fixed point reachable only via re-solving-with-correct-ranges or self-play.
2. Both real paths are **already laid out** in the repo (`resolver.py`, `deep_cfr.py`) and the resolver has
   already delivered the most GTO-near result (−12.9) — it is blocked only by **one missing component:
   correct postflop ranges** (§1).
3. "100% GTO" is realistically achievable for HU as *"within measurement accuracy / near-zero LBR"*
   (ladder above) and impossible in principle for 6-max (there, bounded exploitability is the right target).

*— Review pass over bot.py, advisor.py, resolver.py, range_tracker.py, postflop.py, gto_oracle.py,
exploit_engine.py, opp_model.py, equity.py, gto_baseline.py, features.py, preflop_gto.py, cfr_preflop.py,
floor_map.py, gto_oracle_match.py, scorecard.py + CLAUDE/STATE/NOTES.*
