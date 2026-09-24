# AIVAT for the local Kaggle HU channel — draft after cross-examination (2026-09-10)

> Arose from the user question "Can't we develop an AIVAT for the Kaggle endpoint?".
> Three research agents (theory / repo inventory / variance structure), one draft, THREE independent
> refutation attempts (unbiasedness, interaction with the pairing, buildability), then this version.
> **None of it is built.** Channel and instruments: [`KAGGLE_ARENA.md`](KAGGLE_ARENA.md).
>
> **Note on the escalation in section 0:** the running `console_solver.exe` and
> `python.exe` processes reported there were this session's own background measurement runs (v9 run, v10-H0 run), NOT a
> second session. The note that HEAD moved during the analysis is correct, however: the deal marker in the
> adapter landed in the middle of the run, and the reference numbers from 300 decks date from before it.

# Estimator for the local Kaggle HU channel — REVISION 2 (after three attacks)

**State: HEAD `d22d400` (2026-09-10 01:59), working tree clean.** All line references below are **re-checked at this HEAD** (the citation hygiene was defective in Rev. 1 — A1/A2/A3 established this independently).

---

## 0. ESCALATION FIRST — nothing gets built before this is resolved

Fallback protocol #5, blocking:

* **HEAD moved during the attack sessions** (`3e1dfce` → `d22d400`; `kaggle_arena.py` 340 → 375 lines). Commit text: v10 patch `r10_h0` + "Kaggle adapter: missing deal marker added — without it v10 reported `fehler:root_nicht_rekonstruierbar`". **The river plan now actually navigates** (A2: 12 `river_strategy` calls in 8 decks) — yesterday's channel is not today's channel.
* **Currently running: 2 × `console_solver.exe` and 7 × `python.exe`** (just checked, nothing terminated). Memory `one-session-per-repo`: very probably a second session.
* **Consequence:** the reference `+55.8 / SE 38.0 / 32.3% / 10.5 s per deck` (`KAGGLE_ARENA.md:153-162`) is **probably outdated**, and with it every calibration in Rev. 1 and in the attacks. The throughput figure varies by a factor of 25 (doc 10.5 s/deck; A2 before the commit **0.41 s/deck** with exactly reproduced metrics; A2 after the commit 1.7–16.8 s/deck).

**Gate G0 (precondition, see §4) must run before any line of code.**

---

## 1. WHAT THE ATTACKS CHANGED

### Struck without replacement

| What | Why | Source |
|---|---|---|
| **Stage 2 "TKE" entirely** | The bot is **deterministic conditional on the deck**: `seed: int = 7` fixed (`kaggle_arena.py:200`, `:226`), fresh instances per half (`:318-319`), `neue_hand` is a no-op (`:215-217`, `hasattr(self.bot,"new_hand")` — `PokerBot` has no `new_hand`). In the measure over which the channel averages, `a_real` is a deterministic function of the deck ⇒ the only B1-compliant "policy" is a **point mass** ⇒ `δ ≡ 0`. An action term is either identically zero or biased. There is no third option. | A1 §2, A3 F3 |
| **Alternative (a): resolver monkeypatch / file `kaggle_policy.py`** | `river_strategy` (`resolver.py:232`) returns the distribution **before** the chain. Behind it: `_label_to_action`/`_raise_to` (`bot.py:1054-1057`), the **override** in `wickle_decide` (`auslese.py:78`, `auslese_guard: True`), `river_gpu_guard` (`improver.py:477ff`, fires from pot 3000 chips = 30 bb, hand-dependent, swallows every exception `:528`) and the harness clamp `int(round(...))` + fallback-to-call at `can_raise=False` (`kaggle_arena.py:191ff`) — **exactly the defining condition of the claimed node class**. `{label: p}` is a distribution over a preimage, not over executed actions ⇒ modelled policy ⇒ real bias, arm-correlated (the chain exists only in the candidate arm, `stack=None` in the basis arm) ⇒ **not** erased by the mirror. | A1 §3, A2 §6, A3 F1 |
| **Alternative (b): K-fold repetition** | `_LINE_U` is ON (`bot.py:89`, PRINCE profile `gto_mode.py:47`): **ONE** uniform per hand, drawn at `bot.py:218-230`, held in the instance (`_hand_u_by_id`, `:148`, read `:489-491`), reused at `:783/812/851`. Fresh seeds estimate the **marginal**, not the conditional given the realized prefix; the same instance reproduces the realized draw ⇒ correction 0. The statement "`E[p̂]=p` and `p̂ ⫫ a_real` ⇒ `E[δ]=0`" is logically false (independence is necessary, not sufficient). Measured: `Random(7).random() = 0.323833` — at all three gates, in both arms, in **all** decks the same value. | A1 §2, A3 F2 |
| **§3.3 "cleaned edges become dense, re-calibrate the sparse branch"** | Factually wrong, doubly: on non-divergent decks `X̃ = 0` remains exact (identical trajectories), and the sparse branch does not engage even today (`SPARSE_SCHWELLE = 0.02`, `stats.py:90`, against `nonzero_anteil` 0.323). The paragraph contradicted its own §5.1. | A1 §5, A2 §5.2, A3 F5 |
| **Action reconstruction à la `slumbot_adjust`** | Superfluous: `parse_beobachtung` returns `pot_gesamt` (`kaggle_arena.py:126`) and `committed_total` (`:159`, `:163`) directly from the `observation_string`. Bug surface without benefit, a good part of the estimated 4–6 h. | A3 F7 |
| **`bereinige_deck` in the `duell` loop + `--stufe` flag** | Contradicts its own architecture rule ("post-hoc, never in the hot path") and breaks its own 2% time criterion (up to 285 ms per half measured). The estimator runs **exclusively offline** on the log. | A3 F7 |

### Corrected (the construction itself)

| Rev. 1 | Rev. 2 | Reason |
|---|---|---|
| `Y = E[u \| h_L]` **per half**, then differentiate | `X̃ = E[X \| c_1…c_{j*}]` **per deck** | The variance guarantee does not survive the halving: `Var(X̃) = Var(Y_h) + Var(Y_r) − 2Cov(Y_h,Y_r)`, and the covariance **consists** of exactly the runout randomness the correction integrates away. A2 worked the harmful case (one arm all-in with pot 400, the other showdown with pot `P_r` ⇒ variance ratio `P_r²/(400−P_r)²`, break-even at `P_r = 200` units; for `P_r = 388` factor ≈ 1045). Deck level makes this case **constructively impossible**. |
| "at stage 1 `ṽ` is exact → the correction cannot hurt" (§5.8) | **struck as a claim, replaced by a test condition**: `Var(X̃) ≤ Var(X)` holds for the deck construction by the tower property; a measured `se_faktor > 1.0` is consequently an **implementation error**, not a statistical result (STOP). | A1 §4, A2 §2 |
| Abort rule "`q̂ < 0.25` ⇒ do not build" | **circular** (`q` is defined via `X̃`). Replaced by the **mass census** `m_chance` — directly measurable from the log, without a finished estimator. | A1 §5(ii) |
| "8 workers = SE factor 0.354, ~0 risk, a few lines" | **Mined.** `river_gpu_guard` solves on the GPU; `research/policy_oracle.py` docstring: *"Pilot 2026-09-07: 12 workers ran into CUDA-OOM, silently swallowed by the guard"* (`improver.py:528`, `except Exception`). Naive parallelization can **silently change the policy**. Becomes its own stage with a hard identity gate. | A3 F6 |
| A1 identity test ("force all chance outcomes") | Made precise: the test is only exact **after** `j*`, because there **no decision follows** ⇒ no RNG continuation ⇒ the mean is exact, not noisy. Preflop all-ins (1.7 million leaves, ~31 s) are **excluded** from the test and handled in production via budget truncation. | A1 §6 |
| Enumeration cost 0.7 / 15.2 / 231 / 2730 ms | **1.3 / 18.5 / 285 / 3454 ms**, preflop ≈ 31 s (A3 re-measured independently, ~25% more expensive than Rev. 1). Conclusion "preflop exact unaffordable" holds. | A3 |
| A2 power calculation `SD(D) ≈ √q·SD(X)` | Backwards — presupposes that the correction only removes variance. Replaced by a **bias budget by construction** (G5). | A1 §6, A2 §5.3 |

### Confirmed (holds, unchanged)

* **The chance term is mathematically clean** — and for a reason Rev. 1 only touched on: the card stream has its **own, hand-local RNG** (`rng = random.Random(deck_seed)`, `kaggle_arena.py:248`); the bot mixes from a separate stream (`bot.py:141`). No action shifts the card stream ⇒ `E[δ|F] = 0` **pointwise**, not just on average. Equal stacks + `reset_stacks` ⇒ no side pot.
* **All four [M] structural properties** (absolute card IDs 0…51, 9 chance nodes of one card each, prefix determinism 600/600, reference run ≈ 4 ms/deck) — independently reproduced by A3.
* **Rejection of modelled policies (K1, TV 0.2085) and of rollout baselines.**
* **Budget truncation as an unbiased weakening.**
* **§5.1 (the "10×" reduction from the GTOW channel is NOT transferable because the mirror has already erased the card variance)** — named by all three attacks as the strongest point of the draft.
* **`spiele_hand` has exactly one caller** (`duell`; `pargate6._spiele_hand` is a namesake) ⇒ additive signature extension is low-risk.

### Newly added (findings worth more than the estimator)

1. **The channel's mixing uniform is frozen.** `u = 0.323833` at `bot.py:783/812/851`, in both arms, in every deck. That is **CRN** (good for the paired difference, and `duell` explicitly justifies the fresh instances by A/A otherwise being −37.5 instead of 0) — but it also means: **the channel measures the arm difference on ONE mixing path**. A candidate whose edge lies at other `u` is invisible. That is the same mechanism as the documented v8 purify break.
2. **`_SIZE_INJECT` freezes at import** (`resolver.py:117`); `POKERB_PRINCE` is only set in `PrinceAgent.__init__` (`kaggle_arena.py:206-208`, before the bot import — so correct in a fresh process). ⇒ **Build rule:** the log harness must **not** import `pokerbot.strategy.*` before the agent, otherwise it measures a different bot.
3. **Where the money is (A2, measured on the old state):** 5 decks carry 83.2% of the sum of squares, all end with a river call, 4 of them at `to_call>0, can_raise=False` (74.4% of the SS). That is the class the action term would hit — and which is **unreachable** for the reasons above. The chance term, by contrast: **0 of 600 halves had a non-empty terminal core** ⇒ on the reference state `q = 0`, `se_faktor = 1.000`.

---

## 2. The corrected core (one page of mathematics)

Cards `c_1…c_9` (absolute IDs, prefix-deterministic, own RNG). Measured quantity `X(D) = (u_hin − u_rück)·50`.

**`j*` := smallest index `j` from which NEITHER of the two mirror halves still has a decision** (each half is terminal or all-in). `j*` is measurable from the history **before** card `j*` ⇒ predictable (B3).

```
X̃(D) = E[ X | c_1…c_{j*} ] = (1/|R|) · Σ_{r ∈ R} X(c_1…c_{j*}, r),   R = all completions
|R| = C(52 − j*, 9 − j*)
```

* **Unbiased** (tower property), **and** `Var(X̃) ≤ Var(X)` — because **both halves are evaluated on the same completion `r`**. Exactly that was the construction error of Rev. 1.
* **Budget truncation:** every predictable `j' ≥ j*` is likewise exactly unbiased and likewise `≤ Var(X)`; the reduction decreases monotonically with `j'`. `j' = 5 − 3` ⇒ 285 ms, `5 − 2` ⇒ 18.5 ms.
* **Degenerate cases resolve themselves:** both halves all-in with identical pot ⇒ `X ≡ 0` for every completion ⇒ `X̃ = 0 = X` (no noise from an algebraic zero — the damage the half construction would have done). One half all-in, the other with further decisions ⇒ `j* = 9` ⇒ correction exactly 0.
* **The three death conditions of the action term** (all three violated today, two of them beyond the reach of an estimator):
  * **P1** The executed mixture must be non-degenerate in the measurement ensemble. → `seed=7` fixed.
  * **P2** The logged `p` must be the **executed** policy (pushforward through the whole chain). → `research/policy_oracle.py::_basis_aktionen` does this correctly (label forcing through the full chain, GPU guard as a pure function, ~209 ms/spot; identity test `tests/test_river_br_pruefstand.py::test_oracle_identitaet_gegen_r8_stack`) — so **not free, not read-only**.
  * **P3** The mixing randomness must be **fresh at the node**. → `_LINE_U` is hand-latent (forbidden zone `pokerbot/strategy/*`).

---

## 3. Stage ladder (Rev. 2)

> **Decision rule unchanged:** a measure is worthwhile exactly when `Var_alt/Var_neu > t_neu/t_alt`. Since the estimator now runs **offline**, `t_neu/t_alt = 1` — the rule only binds the parallelization now.

### S0 — RECORDING (build, uncontested, ~2 h)
The channel persists nothing today. Without a log every mass figure is speculation. Pure appending; `mitschnitt=None` leaves today's path byte-identical. **Yield: makes S1, S2 and S3 measurable in the first place — and allows every evaluation to be repeated post-hoc on old runs.**

### S1 — CENSUS (build, ~1 h, DECIDES on S3)
Purely computational on the log, no estimator needed:
* `m_chance` = share of the sum of squares in decks with `j* < 9`.
* Distribution of `j*`; share of decks with two-sided all-in (`X ≡ 0` algebraically).
* Guard fire rate (`auslese_guard`), share of clamped decisions, share `can_raise=False ∧ to_call>0` and their share of `ΣX²`.
* s/deck, plan activations (`_PLAN`), `river_strategy` calls.

**Pre-registered expectation: `m_chance ≈ 0`** (A2: 0/600 halves with non-empty terminal core) ⇒ **S3 will presumably NOT be built**. That is the prediction, not the hope; the only uncertainty is the v10 plan since `d22d400`.

### S2 — PARALLEL IDENTITY GATE (build, ~2 h, the real SE lever)
8 workers = 8× decks = SE factor **0.354** — more than any estimator here can ever deliver. But: GPU contention can silently change the policy. Hence: runner + **hard identity gate** (G6). The log from S0 provides the diagnosis (guard fire rate per worker count), the edge list the verdict.

### S3 — DKB (deck-core cleaning) — **only if `m_chance ≥ 0.25`**, ~3 h
`j_stern()` + exact enumeration of the completion + `bereinige_lauf`, offline. Values directly from `parse_beobachtung`, no reconstruction. Budget `j'` via flag.

### STRUCK
TKE / resolver recording / `kaggle_policy.py` / repetition probes / rollout baselines / modelled policy / trimmed mean as "variance reduction".

### OUTSIDE THE LADDER (diagnosis, needs explicit assignment)
**The frozen mixing path.** Candidate: `seed = 7 + deck index`, **shared by both arms and both halves of the same deck** — CRN is preserved, A/A stays exactly 0, but `u` spreads over 300 values instead of one. Changes the estimation target (expected value of the strategy instead of one mixing path) and **invalidates every calibration** ⇒ user decision, own paired gate. **Does not make the action term legal** (P3 remains violated).

---

## 4. Gate — acceptance criteria as numbers

**G0 (precondition, blocking).** Second session resolved; fresh reference on `d22d400`: `prince[final]` vs `prince[basis]`, 300 decks, `seed0=90000`, **one** worker. First 50 decks for throughput measurement, then decide. **Pre-registered:** if `nonzero_anteil` deviates by > 0.05 from 0.323 **or** `SE` by > 8 from 38.0, all mass figures of the attacks are invalid and S1 re-derives them.

**G1 (log neutrality).** (i) Edge list with `--log` **element-wise identical** to without (300 decks). (ii) `--aa --decks 8`: `bb100 == 0.0` **and** `nonzero == 0`, **before and after** the intervention. (iii) Runtime overhead **≤ 2%** (median of 3 × 50 decks).

**G2 (census).** S3 is built **iff `m_chance ≥ 0.25`**. All census figures are noted as expectations before the run.

**G3 (identity, pointwise — only with S3).**
* `test_dkb_identitaet`: ≥ 20 decks with `9 − j* ≤ 2` (≤ 990 completions), force all outcomes via `state.clone()` + `apply_action`, run to terminal (after `j*` **no** decision ⇒ no RNG continuation ⇒ the mean is exact). **Acceptance: `|mean_r X(r) − bereinige_deck(...)| ≤ 1e-9` units, 20/20.**
* `test_budget_monotonie`: `j' ∈ {j*, j*+1, j*+2}` — each level meets its own identity exactly, and the reduction decreases monotonically. **3/3.**
* `test_kein_zufall`: `random.Random.random/.sample/.choice` in the estimator process replaced by a throwing dummy ⇒ `bereinige_lauf` runs through.
* `test_schaetzer_determinismus`: twice on the same JSONL ⇒ byte-identical.

**G4 (variance, paired).** On **one** logged run, both estimators from the **same** edge list, deck bootstrap with **identical** resample indices. Report: `se`, `b_se`, `se_faktor`, **CI of the factor**, `n_eff`. **Acceptance S3: upper CI bound of the `se_faktor` ≤ 0.85.** **Hard STOP condition: `se_faktor > 1.0` ⇒ implementation error** (impossible by construction), not to be reported as a statistic.

**G5 (bias budget — new, from A1 §6).** `verdikt` fires ANWENDEN at `bb100 − 2·se > 0` (`stats.py:93-101`). **Halving `se` doubles the sensitivity to any residual bias.** Therefore pre-registered:
* An estimator may only enter a verdict if its bias is **zero by construction** (exact conditional expectation solely over card randomness; no `p`, no `p̂`, no model). DKB meets that; **any action term does not**.
* Until then the **raw** estimator remains the primary number; `b_*` fields are **diagnostics without verdict**. That closes the forking path (two verdicts on the same data) in advance.
* Formal budget for the hypothetical case of an approximate estimator: `|Bias| ≤ 0.25 · SE_ziel = 1.0 bb/100`. **No available test has this power** — approximate estimators are thereby excluded, not "to be measured later".

**G6 (parallel identity, S2).** `W ∈ {1, 4, 8}` on the same 100 decks: **edge lists element-wise identical AND guard fire rate identical. 3/3.** On deviation: worker count capped at the largest identical `W`, report the s/deck curve.

---

## 5. File specification

**Principle (binding, tightened):** the estimator runs **exclusively post-hoc on the log**. `duell` gets **no** `--stufe`, computes **nothing**.

**New**
* `pokerbot/benchmark/kaggle_log.py` (~110 lines): `karte(idx)` (`"23456789TJQKA"[idx//4] + "cdhs"[idx%4]`, verified against `observation_string`), `class Mitschnitt` (append-only: `.chance()`, `.entscheidung()`, `.ende()`, `.als_zeile()`), `schreibe(pfad, zeilen)` (JSONL, one line per half), `referenz_deck()` (4 ms/deck, **diagnostics**: materializes the full board even for early-ending decks).
* `research/kaggle_zensus.py` (~90 lines): **the artifact that decides** — `m_chance`, `j*` distribution, guard/clamp/class shares, s/deck.
* `research/kaggle_parallel.py` (~80 lines): worker runner + G6.
* `pokerbot/benchmark/kaggle_schaetzer.py` (~180 lines, **only on G2 release**): `j_stern(zeile_hin, zeile_rueck)`, `vervollstaendigungen(gesehene_karten, k)`, `bereinige_deck(zeile_hin, zeile_rueck, j_max=…)`, `bereinige_lauf(jsonl, j_max=…)` + own CLI.
* `tests/test_kaggle_schaetzer.py` (G3).

**To log (minimum for S1; bold = mandatory for S3)**
*Deck:* `deck_seed`, `hand_id`, **`chance_ids[9]`**, `hole_s0`, `hole_s1`, `board5`, `stack_einheiten`, `agent_a/b`, `fp_hash`, `git_sha`, `kante_chips`, `divergenz_ply`, `divergenz_strasse`.
*Half:* `haelfte`, `sitz_von_a`, `u_einheiten`, `terminal_typ`, **`letzter_entscheid_ply`**, **`karten_index_nach_letzter_entscheidung`**, **`pot_gesamt`**, **`committed_total[2]`** (both directly from `parse_beobachtung`, `kaggle_arena.py:126/159/163` — **no** reconstruction).
*Decision:* `ply`, `strasse`, `spieler`, `legale_aktionen`, `gewaehlt`, `betrag_einheiten`, `pot_vor`, `to_call`, `can_raise`, `wunsch_action`, `wunsch_betrag_chips` (**before** clamping), `geklemmt`, `fallback_auf_call`, **`auslese_guard`**, `kanal`, `ms`.

**Changed additively:** `kaggle_arena.py` — `spiele_hand(..., mitschnitt=None)` (`:244`), `duell(..., log_pfad=None)` (`:303`), one CLI flag.
**Not touched:** `pokerbot/strategy/*`, `pokerbot/autogym/improver.py`, `pokerbot/autogym/stats.py`, `pokerbot/engine/equity.py`, `knowledge_base/math/*`.
**Build rule (from finding 2):** the log harness **never** imports `pokerbot.strategy.*` before the agent (`_SIZE_INJECT` freezes at import, `resolver.py:117`).

---

## 6. Honest limits

1. **The mirror has already erased the card variance.** The "~10×" reduction of the GTOW channel is not transferable; whoever expects factor 10 counts it twice.
2. **On the reference state the chance term has ZERO mass** (0/600 halves with non-empty terminal core). The most likely outcome of this plan is: **S0+S1 measure that there is nothing to gain.** That is a valid result, not a failure.
3. **The action side is closed.** Three named preconditions, two of them beyond the reach of an estimator, one of them in the forbidden zone.
4. **The measurement seam stays untouched.** `int(round(...))` (`:191`) produces divergences without strategy signal; the field `geklemmt` makes them **visible**, the estimator does not fix them.
5. **Variance ≠ ignorance.** raw +55.8 / trimmed +6.3 / median 0 / sign z −0.71 is well compatible with "true effect ≈ 0". A perfect estimator turns that into a **tight NEUTRAL**. Whoever seeks ANWENDEN needs a better candidate.
6. **The estimation target does not change** (A − B, no GTO anchor; not applicable at all to the Kaggle leaderboard scoring).
7. **Parallelization is the biggest lever and mined.** Hence S2 before S3 — and hence Rev. 1 was wrong with "~0 risk".
8. **Every cost figure here is subject to G0.** Throughput is uncertain by a factor of ~25.
9. **All measurements of the attacks refer to a code state HEAD has left.**

---

## 7. OPEN QUESTIONS

1. **Is a second session running?** 2 × `console_solver.exe` + 7 × `python.exe` active; HEAD moved during the attacks. **Blocking** — start nothing until resolved.
2. **Does the reference `+55.8 / SE 38.0 / 32.3%` still hold on `d22d400`?** The v10 river plan now actually navigates; the channel may have a different distribution.
3. **Where does the throughput contradiction 10.5 vs 0.41 vs 1.7–16.8 s/deck come from?** Warm memoization, machine load, GPU guard active/inactive? Decides whether 27,000 decks cost 3 h or 79 h — and thus whether the whole estimator idea even has an opponent.
4. **`m_chance` on the current state** — the only number that decides on S3. Does the v10 plan (`RC_STACK = "r10_stack"`, `auslese.py:35`) create new all-in-before-river nodes?
5. **Does the channel want the frozen mixing path?** CRN + A/A exactly 0 (today) versus the expected value of the strategy (`seed = 7 + i`, shared by both arms). User decision; changes the estimation target and invalidates the calibration.
6. **`self.rng.` count:** A1 counts 30, A3 exactly 21. Resolvable as 21 direct calls + 9 pass-throughs `rng=self.rng` (`bot.py:335/398/430/459/566/569/1054/1081/1107`). Irrelevant for the plan — **relevant if P1/P3 are ever reopened**, because the pass-through sites (equity MC) are the big consumers and produce the data-dependent stream offset.
7. **Does the `_SIZE_INJECT` import order bite in the production path?** `PrinceAgent.__init__` sets `POKERB_PRINCE` before the bot import (`:206-208`) — so correct in a fresh process. A2 measured the tipping point only in the patch harness. To be settled with a two-line test.
8. **Does the Fable finding "capped check range" apply here?** A1 §8 considers the frozen `u` the same mechanism as the v8 purify break — that concerns the **already reported numbers**, not just the estimator. A counting run over `_line_u` (free from the S0 log) confirms or refutes it.

---

**Order in one sentence:** resolve G0 → build **S0 log** (G1) → compute **S1 census** (G2) → **S2 parallel identity gate** (G6, the real SE lever) → **S3 DKB only if `m_chance ≥ 0.25`** (G3/G4/G5). The action term is struck, not postponed.
