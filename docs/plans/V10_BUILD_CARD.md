# V10 BUILD CARD — "River Foundation" (2026-09-07)

**Origin:** Fable draft → critique by gpt-6-astra (../consults/TOP5_CONSULT_GPT6_2026-09-07.md, part E) →
this reconciled version. User assignment: build v10 in ONE go (Ultracode fleet), gates, GTOW.
Astra's time estimates are irrelevant; its direction and acceptance criteria are adopted wherever
not explicitly decided otherwise below (section "Deviations").

## Goal
More coherent river play through (K1) corrected hero beliefs and (K2) a public solver entry with
a stored plan; plus (K3) a test bench that evaluates both arms in the same root game, (K4)
production integrity, (K5) GTOW pilot. **Not in v10:** CFV net, turn solving, entropy, fp16,
resolver replacement (TexasSolver stays ON), stackoff/no_limp, advisor rebuild, strategy changes
outside the river-solver path.

## Arms
- **A = v5-H:** frozen v5 strategy (r8_stack) on the repaired channel (PRINCE, exploit OFF,
  TexasSolver ON). "-H" because K4 repairs the channel; strategic distribution on the golden set unchanged.
- **B = v10:** the same chain underneath (r6_button + wert_bremse); the hand-dependent river_gpu_guard is
  REPLACED by K2 (public river plan) with the K1 hero range. Stack name `r10_stack`.

## K1 — Hero likelihood replay (`pokerbot/strategy/hero_range.py`)
Reconstruction of hero's river-start range FORWARD from the preflop prior:
r_river(h) ∝ r_0(h) · M_board(h) · Π_t π_exec(a_t | s_t, h) over all hero actions before the river.
- **Base likelihood backend (approximated, LABELED):** the tracker's advisor model
  (P(bet)/P(check) per combo, P(call) via the defense advisor), batched — the same models as today,
  new evaluation interface without sampling/side effect.
- **Guard transformations EXACT** as a shift of action mass:
  - turn_wert (check→bet b* under condition C(h)): π_exec(b*|h) = π_vor(b*|h) + 1_C(h)·π_vor(check|h);
    π_exec(check|h) = (1−1_C(h))·π_vor(check|h). C(h) with the villain range OF THAT TIME (snapshot before the
    turn action, card removal recomputed per hypothetical hero combo), equity vectorized (gpu_equity).
  - sel_guard flop (fold→call under C(h)): π_exec(call|h) = π_vor(call|h) + 1_C(h)·π_vor(fold|h); raise share
    stays.
  - button_disziplin (open 2.5× for EVERY combo): prior UNCHANGED at this point (no selection).
  - Size comparison over final integer chip amounts (engine clamp), not over labels.
- **No hero-hand injection** in the K1/K2 path. Invariance: same public history, different hero hand
  → identical public hero range (≤1e−6).
- **Acceptance:** Σ=1 (1e−6), board combos exactly 0, guard transformation vs explicit enumeration ≤1e−6,
  invariance test; **oracle sample** (≥64 held histories + ≥128 action states, each
  guard class ≥16×): oracle = offline decide() per combo over several seeds (empirical distribution);
  mean TV distance of the final hero range ≤0.02, p95 ≤0.05, no case >0.10. Failed → K2 NOT free.
  Injection rate only legacy diagnostics from now on.

## K2 — Public river plan (`river_play_guard` → `pokerbot/autogym/river_plan.py`)
- **Gating public and street-wide:** decision AT THE START OF THE RIVER: pot_river (pot at the river deal)
  ≥ **15 bb (1500 chips)** → the whole river street is played per plan; otherwise base+wert_bremse.
  No raising the threshold after seeing the result.
- **RiverPlan:** solved once per hand at the start of the river (root = river start, K1 hero range, tracker
  villain range, tree 0.35/0.75/1.5 pot + raise 2.7× + jam, fp32, 150 iters, AVERAGED strategy);
  stored (root/tree/config hash); every hero decision navigates the played sequence to the
  node. Off-tree villain action → defined fallback (base) + log `offtree`; no silent re-solve.
  Cache per hand (one solve per river, not per decision).
- **Private randomization:** u = keyed_hash(private_seed, hand_id, decision_addr); private_seed in the gym
  deterministic from deck seed+seat (A/A exactly 0 remains), live from os.urandom (logged, never
  derivable by the opponent). Policy queries (K1/K3) consume no random numbers. Sampling test 10k
  seeds per test distribution ≤5 binomial SE; p∈{0,1} exact.
- **Sizes** exactly from the tree arm → chips (documented mapping), legality gate as in v8.
- **Trace per decision:** basis → texassolver_eingriff → guards → plan_entscheidung(distribution) →
  legalität → sample → final. Every change AFTER the plan decision is pure legality mapping.
- **Deadline:** internal deadline 7.5 s → fallback base action; a late GPU result is discarded.
- **Acceptance:** activation independent of hole cards; distributions normalized; check–bet–raise–call and
  off-tree fixtures without range reset; latency ≥500 decision calls (stratified: both positions,
  threshold, raise, jam, cold/warm) **p99 < 8 s, no regular call ≥ 9 s.**

## K3 — River test bench (`research/policy_oracle.py`, `research/river_br_pruefstand.py`)
- **Shared root game per source hand:** one river root, evaluation distribution ρ_s = (K1 hero range
  [labeled], tracker villain range) for BOTH arms; internally A plays with its beliefs, B with K1.
  Sensitivity: at least one alternative villain-range family (preflop null hypothesis).
- **Policies:** B = plan strategy exactly (combo matrix from the solve, NO sampling). A = oracle of the
  executed v5 policy: decide() per combo per hero node, ≥4 seeds → empirical distribution
  (labeled as an estimate). Tree CLOSED under the actions of both arms: final sizes of both
  arms into the evaluation tree; roots that cannot be represented = `UNSUPPORTED` (reported, not projected).
- **Metrics separately:** one-sided safety loss E_H(π)=v*−min_σV u(π,σV) with game-value bracket
  [L,U]; paired ΔE_H = w(π_A)−w(π_B) (game value drops out); local regret R(s,h;π)=max_a Q−Σπ(a)Q(a)
  against the averaged solver strategy (adaptively solved more precisely for Q verdicts). Denominator: per source hand, one root
  per hand, selection weights reported.
- **Controls:** A/A ≤1e−6; analytic matching pennies (mix 0 / pure 1); small card fixture
  against independent enumeration ≤1e−6 (prevents an oracle opponent with sight of hero's cards);
  purify control as soft plausibility, not as a hard rule.
- **Holdout:** night-1 hands (data/sessions/gtow_hands_17870122xx.., chunks A–D, never used for v8/trigger/K1)
  = HOLDOUT; night 2 = development. Provenance in the report.
- **Candidate gate (holdout):** one-sided 95 % upper bound ΔE_H ≤ +0.5 bb/100 AND ΔR ≤ +0.5 bb/100,
  at least one of the two <0; tail cases separately against a denser tree.

## K4 — Production integrity (`pokerbot/runtime_config.py`, `server.py`, `gtowizard.py`, sidecar)
- server.py: PRINCE + exploit OFF + FINAL_STACK (D1). gtowizard adapter: immutable runtime config
  BEFORE the bot import; start abort on misconfiguration (PRINCE/exploit/resolver); fresh process per chunk
  (gtow_nacht already spawns subprocesses — keep).
- Fingerprint per hand (JSONL sidecar, hand ID): git HEAD + dirty, model hashes (.pt), PRINCE, exploit,
  stack, deception parameters, TexasSolver status, GPU solver version, tree/iters/precision, P_min,
  K1 version, sampling/fallback mode, private_seed origin. A check of what was LOADED.
- Persistent hand ledger (hand ID, arm, hash, AIVAT, technical events, status) after every hand;
  clear_inprogress only after reconciliation; unknown outcomes marked, never imputed as 0.
- **Acceptance:** 100 % of smoke hands with fingerprint; misconfiguration → abort; abort after a hand loses nothing;
  restart without double counting; fault injection (timeout, 503, process abort); v5 golden set
  (distribution on 40 decks) byte-identical before/after K4.

## K5 — GTOW pilot (`research/gtow_nacht_v10.py`)
- Two nights, chunks of 500; sequences ABBA / BAAB; order IN ADVANCE by coin flip (logged);
  adjacent chunks = comparison pairs (randomized block design WITHOUT CRN). No change after
  interim results. Ladder beforehand: smoke 20 → 100 with v10.
- Technical failures separated: transport, deadline violation, illegal action, unknown completion,
  fallbacks. Illegal action or repeated deadline violation → stop of the candidate. Unknown
  outcomes >0.5 % → no performance verdict.
- **Pre-registered statement:** The live test estimates the AIVAT level of both arms and their difference
  Δ = μ_v10 − μ_v5-H; primarily exploratory (large effects/regressions). Non-inferiority with margin
  −5 bb/100 is claimed ONLY if the one-sided 95 % lower bound supports it (at SE≈7 per difference
  that is NOT the case at a tie → then "not demonstrated", never "equally good").

## Gates (order, each with a proof artifact in data/runs/v10/)
G0 contracts frozen (contracts.py), holdout provenance, both arms startable ·
G1 invariants: K1 transformations, support, sampling, BR controls, fault injection ·
G2 A/A r10_stack 600 decks EXACTLY 0 (two instances, same test seeds) + 40-deck divergence smoke +
forced K2 fixtures + latency 500 calls (p99<8 s) ·
G3 K1 oracle acceptance (TV budget) ·
G4 holdout test bench (ΔE_H, ΔR, sensitivity) ·
G5 short mirror 2000 paired decks vs r8_stack (catastrophe/integrity test, NO effect proof;
clearly negative finding → investigation) + Analyzer export for user upload ·
G6 GTOW smoke 20/100 → nights with unchanged artifact (tag `auslese-v10-rc`).
After G4 no strategy correction in the same release; every change = new hash, repeat gates.

## Deviations from Astra's version (deliberate)
1. Base likelihood = advisor backend (approximated), because bot.py exposes no mixed distribution;
   Astra allows that with oracle acceptance — that is gate G3.
2. Gating at the START OF THE RIVER (pot_river) instead of "pot ≥ 15 bb at hero's decision": prevents hero
   from playing a river action with the base and only then switching into the plan.
3. A oracle with ≥4 seeds instead of the full distribution (not exposed); cost bounded by the number of roots
   (≤120) and caching; labeled as an estimate.
4. Mirror G5 = 2000 decks (Astra's proposal), not 15k.

## Agent packages (disjoint ownership)
P0 scouts (facts) → P0b contracts (`pokerbot/strategy/contracts.py`) → in parallel P1 K1 · P2 K2 · P3 K3 ·
P4 K4 · P5 K5 (mock) → integrator (pargate registry `r10_stack`, auslese, wiring) → reviewer per
package (adversarial) → gate runners G1–G5 → report. Nobody except the integrator changes bot.py or the
stack registry.

## DECISIONS AFTER THE SCOUTS (2026-09-07, Fable; facts: ../reports/V10_FACTS.md, contracts: pokerbot/strategy/contracts.py)
- **E1 K2 entry point = (b):** In plan pots (pot_river ≥ 1500 chips) the GPU river plan IS the river
  policy; the internal TexasSolver river resolver is NOT called there (K2 is the outermost wrapper and
  does not call base(st) in plan pots). Below the threshold and on the turn TexasSolver stays ON as in v5.
  Clarification of the card: "TexasSolver stays ON except in river plan pots". The trace has no base entry in
  plan pots (documented).
- **E2 Channels:** G2 (A/A) and G5 (2000-deck mirror) run on the pargate channel (exploit ON, no PRINCE,
  resolver OFF) and are LABELED as such (gym channel = integrity/non-regression bound).
- **E3 K1 backend:** advisor likelihood + exact guard transformations for preflop/flop/turn (the river-start
  range does not need the river policy). G3 TV acceptance separately per channel (gym: turn resolver OFF; live: ON).
  Additionally `resolver.river_strategy()` (distribution instead of sample, additive, byte identity of river_resolve
  guarded) — for K3's arm-A policy.
- **E4 Hand address:** `hand_id` is injected into the state in `duplicate._setup_fixed` (deck index);
  private_seed(gym) = keyed_hash(job_seed, hand_id, seat). Acceptance: 40-deck golden set r8_stack vs basis
  byte-identical before/after (data/runs/v10/golden_*.json) + A/A. Live: hand_id from gtow_to_state, private_seed
  from os.urandom per process (logged).
- **E5 Deadline:** gym = fixed 150 iterations, NO time abort (determinism). Live = additionally 7.5 s
  time deadline in the plan guard (solve in a thread, late result discarded, status in the trace) and
  `PokerBotMVP.act` via asyncio.to_thread.
- **E6 Guard conditions bit-exact:** C(h) for turn_wert/sel_guard is reproduced per combo with the same CPU-MC path (iters 160,
  `_spot_rng` with hypothetical combo), so that G3 measures K1 and not a GPU
  approximation. "gpu_equity vectorized" struck from K1.
- **E7 Injection:** K2 uses `RiverCFRBatch` directly (own path in river_plan.py); gpu_resolver.py stays
  unchanged → r8_stack/r10_ernte byte-identical.
- **E8 Ledger/fingerprint:** `pokerbot/benchmark/gtow_ledger.py` + documented minimal patch in the
  gitignored tools/gtow_client main.py (../reports/V10_LEDGER_PATCH.md); fingerprint + misconfiguration gate
  (SystemExit) in `PokerBotAgent.__init__`; `POKERB_AUSLESE_STACK` into the fingerprint keys.
- **E9 Holdout:** the four night-1 files by name (gtow_hands_1787012286/1787014241/1787016046/
  1787017672.jsonl), provenance `v4_gym_nackt` (exploit ON, resolver OFF) reported; only root geometry +
  villain range used; exclusion counters in the report.
- **E10 Numbers:** A/A = 576 decks (12 workers × 48 jobs), new bank 1080000 ff.; units 20000/50/100.
  **Latency gate corrected:** the harness has NO decision deadline (only httpx 180 s, chunk 10800 s);
  gate = plan-pot decisions p99 < 8 s AND overall p99 v10 ≤ overall p99 v5-H (no regression) AND no
  call ≥ 30 s. Correct `analyze_gtow_hands.py` BB=50→100 before it is cited.
- **E11 Roles:** K1 hero = initiative role (like decide), villain = position (like the tracker); deviation in G3
  separated by pot type. `p_defense_batch` additive with identity guard allowed ("advisor rebuild" =
  weight/feature change, excluded).

## INTEGRATION ADDENDUM (2026-09-07 evening, Fable)
- hand_id in the gym = DECK address (hand_id_basis + deck_idx), the SAME for both mirror halves — measured as
  necessary: with half-unique addresses the A/A was −9.40 ± 10.92 (private seeds of the halves differed).
- K1_AKZEPTIERTE_STATUS = ("ok", "teilweise") (river_plan.py): "teilweise" = legality-only raise node, which
  the tracker treats identically; a fallback would have discarded all guard transformations. New hash → G2a.
- The latency driver is K1 (bit-exact CPU-MC guard conditions per combo, up to 5.7 s), not the solve (2.5 s).
- K3 oracle: exact only with one GPU solve per combo (injection); 0.205 s/combo → G4 is a multi-hour gate;
  budget in stage 3: 150 min, status UNVOLLSTAENDIG at n < 20 roots, continuation via the oracle cache.
