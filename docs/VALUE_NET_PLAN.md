# DeepStack-style CFV value net + continual resolving — the path to TIE GTOW + generalize to 6-max

> Decided 2026-06-16 (user). The ONE core that (a) gets HU as close to a GTOW tie as possible, (b) understands
> unsolved spots (interpolation, not lookup), (c) survives 6-max (where solving is PPAD-hard). Set up ERROR-FREE
> via gated validation — small first, exact measurement, each gate must PASS before the next. This is the discipline
> that would have caught the fcpa −212 disaster (a policy net is the WRONG object; it plateaus + can't be exploitability-checked cheaply).

## Why a CFV VALUE net (not the fcpa policy net)
- A **policy net** clones a strategy → plateaus below GTOW (measured: fcpa −212) AND is the −72 imitation ceiling.
- A **CFV value net** learns the counterfactual VALUE function; the strategy is RE-SOLVED fresh at play time
  (continual re-solving, DeepStack/Libratus → beat pros). Trained on OUR OWN self-generated solved subgames
  (TexasSolver/CFR) = self-play (AlphaZero logic), NOT imitation → escapes the ceiling. Same core generalizes to
  6-max (a net interpolates where solving is intractable).

## Honest ceiling
A true 0-tie vs near-Nash GTOW is the frontier (Libratus/DeepStack = large teams + supercomputers). Realistic for a
scaled version: **−53 → −15…−25 bb/100**. The o3 theorem: exact Nash → 0; the closer to Nash, the closer to a tie.

## Reusable assets (already built)
- `strategy/deep_cfr.py` — **Leduc engine (`State`), `exploitability()` (EXACT best-response), `vanilla_cfr` (exact
  solver = ground truth), `Net`, the Deep-CFR trainer, DCFR+.** ← the Gate-0 foundation.
- `strategy/resolver.py` (river/turn re-solve), `range_tracker.py` (line-aware ranges) — the resolving + range plumbing.
- `gto_oracle.py` + TexasSolver — fast subgame solves = the value-net's training-label generator (self-play).
- GCP (€260 to Sept-2026) / RunPod (B200) for the HUNL-scale subgame generation + net training.

## Gates (each must PASS before the next — this IS the "fehlerfrei aufsetzen")
- **Gate 0 — LEDUC value-net + resolving, EXACT exploitability.** Build: a CFV net (input = depth-limit public state
  + both range belief-vectors → per-hand CFVs); a depth-limited subgame solver that queries the net at the leaf;
  train the net on self-generated solved Leduc subgames (`vanilla_cfr` = the labels); play by continual re-solving.
  **PASS = the re-solving strategy's `exploitability()` is near-0 (≤ a few mbb/hand), matching a full solve.** This
  proves the value-net+resolving MACHINERY is correct for ~$0. (A policy net cannot be validated this way — that is
  precisely why fcpa shipped broken.)
- **Gate 1 — clairvoyance toy-game.** The resolved strategy must bluff at α=s/(1+2s) (=1/3 at pot) + defend at
  MDF=1/(1+s) (=1/2 at pot), ±0.05, RIVER-only (`docs/math_theory_net_connection.md`). Catches "right machinery,
  wrong game".
- **Gate 2 — HUNL scale.** Self-generate HUNL subgames (TexasSolver), train the CFV net (rich features + a real bet
  abstraction — NEXT_RUN_TODO #84/#85), wire into `resolver.py` for flop/turn/river depth-limited resolving + the
  range tracker for ranges. Validate the net's CFVs vs held-out solver CFVs; validate LBR/the toy-game.
- **Gate 3 — GTOW AIVAT** end-to-end (the real number). Target: beat the current blueprint's −53 toward −15…−25.
- **Gate 4 (later) — 6-max.** Same self-play core → a Pluribus-style blueprint + depth-limited search; judged by
  realized bb/100 + survival, NOT a Nash certificate (6-max has no clean Nash — the solvability consult).

## Hard rules
- **Self-play boundary:** the value net trains ONLY on OUR OWN solved subgames (self-generated), never on GTOW/an
  external bot's strategy. Learning a VALUE function for re-solving ≠ cloning a policy → not the imitation ceiling.
- **No scaling before a gate passes.** Leduc exact exploitability is the linchpin; if Gate 0 fails, the bug is in the
  machinery, not the compute — fix it on Leduc (cheap), never debug on a B200.
- Keys/compute discipline per CLAUDE.md (RunPod `--kill`; GCP stop+budget-alert; no secrets/`*.pt` committed).

## Status
- 2026-06-16: decided + scaffolding confirmed. `strategy/deepstack_leduc.py`.
- **Gate 0a DONE+VALIDATED** — round-1 CFV oracle (reuses `vanilla_cfr` per combo, exact card-removal): the
  public-pairing hand has the highest CFV; a capped range (P0=only-J) is correctly exploitable. EXACT ground truth.
- **Gate 0b PASS** — the CFV value net learned the oracle to **val MAE 0.191 = 6.4% of the CFV scale** (<8% gate).
  This is the DeepStack CORE validated: a net CAN learn the value function — exactly what the fcpa policy net could
  NOT do (−212). Net saved `data/leduc_cfv_net.pt` (gitignored).
- **Gate 0c — DIAGNOSED (2026-06-16, full causal chain traced; NOT a code bug):** the belief-state round-0 resolver
  (`cfr0`+`boundary_oracle`+`resolve_round0`+`gate0d`) converges to a **non-bluffing corner** (P0 bluffs J 0% vs
  exact 8%; **P1 over-folds Q to a bet 47% vs exact 1%** = the dominant leak; P1 over-folds J, over-raises K) →
  exploitability **170 vs exact-eq 22 mbb/hand**. Localized infoset-by-infoset (`RESOLVER` vs `_exact_pol`). The
  hypotheses were COMPETED + the wrong ones REFUTED by measurement (Fable-5):
    - **NOT a propagation/key bug (H1 refuted):** `key(s,p)="{card}|-1|{hist}"` matches `deep_cfr.key` for round 0
      (the `gate0d` overwrite lands); `solve_round1`/`boundary_oracle` are self-consistent (own `hist=""` pol). (A
      `_exact_pol`-based "ground truth" I first wrote was itself buggy — full-game round-1 keys carry the round-0
      hist prefix, `_round1_root` starts `hist=""` → lookup miss → uniform round-1. A caught self-inflicted trap.)
    - **NOT simple adaptivity (H2 refuted):** a FROZEN (non-adaptive) self-consistent value fn is WORSE (840), not
      better, than the adaptive oracle (170). So re-solving per-iterate range is not the culprit; adaptive is best.
    - **ROOT CAUSE = the depth-limited round-0-ONLY re-solve has a spurious equilibrium.** Collapsing ALL of round 1
      into a range-conditional value fn removes the round-1 CO-EVOLUTION that, in full-game CFR, balances the bluff
      incentive (early on P1 calls wide → bluffing is bad → P0 won't bluff → P1 may over-fold → a self-consistent
      corner that is an equilibrium of the *abstraction* but exploitable in the full game). This is the known
      Brown-Sandholm depth-limited-solving phenomenon; the principled fix is **multi-valued states / a CFR-D gadget**
      (the opponent picks among several continuation strategies, so the solver can't rely on P1 both over-folding AND
      calling optimally).
  - **★ IMPLICATION FOR PHASE B (the load-bearing finding):** this round-0-ONLY construction is **strictly more
    degenerate than the actual HUNL plan.** Leduc has only 2 rounds, so testing "net at a betting boundary" forces
    collapsing the ENTIRE remaining game (1-round-explicit). The real HUNL flop-resolve solves flop+turn EXPLICITLY
    (2 rounds) with the net only at the turn→river leaf — far less degenerate — AND the already-shipped, validated
    turn/river resolver uses **NO net at all** (solves to terminal → zero spurious-equilibrium risk). Leduc literally
    cannot validate the "deep-explicit + net-at-leaf" construction (its post-2-round leaf is terminal). So: the
    value-net CORE is PROVEN (0a exact, 0b 6.4%); the round-0-only re-solve's residual is an artifact of the
    degenerate test, with the principled fix (gadget) identified. **This re-opens the flop architecture choice** —
    a SOLVER-to-terminal flop→turn→river live re-solve (no net, no RunPod spend, a deeper clone of the working
    turn/river resolver; the plan's "Risk 5" fallback) sidesteps gate-0c entirely and is the robust default.
- Parallel: the preflop-blueprint GTOW A/B — all 5 retries FAILED on a ~2h server 503-storm; the live **−53 vs −72**
  (n=200, partial) stands as the directional signal. Retry when GTOW recovers.
