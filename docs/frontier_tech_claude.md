# GTO frontier — vet + implementation (Claude claude-opus-4-8)

Alright. Let me cut through both of these. A lot of it is correct *in general* and wrong *for you* because they don't know your codebase constraints (no real-time solver, consolidation phase, gates are solver-EV-gap not bb/100). Let me separate signal from theater.

---

## 1. VETTING — what's real & applicable vs hype/hallucinated

### gpt-5.5

**REAL and applicable:**

- **"Your LBR losing to you proves nothing" → vacuous lower bound.** Correct, and you already *said* this in your own writeup. So this isn't a new insight, it's confirmation. The actionable part — build an LBR that can rediscover *injected* leaks before you trust it — is legitimately the highest-value thing in either document. More below.
- **Action-match / MSE ≠ EV.** This is the single most correct technical criticism. Your advisor is trained on P(bet); 88.6% preflop action-match and held-out MSE can both look great while you bleed on the rare high-EV-gap nodes. This is real and you have the solver cache to measure it directly.
- **"History-free floor averages incompatible information sets."** Real and you literally labeled it "history-free" yourself. K72r in a BTN-vs-BB SRP is a different object than in a 3-bet pot. Your advisor conditions on board+hand features, not line/SPR/range-asymmetry. This is a genuine structural leak. BUT — fixing it fully is exactly the "add complexity" trap your phase forbids. The *measurement* of how much it costs is cheap; the fix is not.
- **River is your most solvable street and is still heuristic.** Correct and the cheapest real EV. You have exact enumeration already. The gap is you haven't solver-*calibrated* it.
- **MDF is wrong vs underbluffers; use pot-odds EV with credible bounds.** Correct in principle. But — careful — you already shade MDF by villain bluffiness. So the gap is whether your shading is EV-grounded or a hand-wave. That's a verification task, not a rewrite.
- **Fold-equity-optimal sizing is not EV-optimal.** Correct theory. Whether it's actually costing you depends on how "fold-equity-optimal" is implemented. Needs measurement, not assumption.

**HYPE / over-complex / off-course for your phase:**

- **"Range/line/SPR/position-conditioned policy model" (their Rank 2, Phase 3).** This is a full postflop rewrite. High effort, "consolidation phase says no." It's a *correct* direction for a different project. For you it's the thing to *budget against* via EV-gap measurement, not build now.
- **"6-max joint range model."** Correct that independent-seat is structurally behind Pluribus. Also a multi-month rebuild that contradicts your stated phase. Park it. Crushing weak 6-max is fine; don't pretend it's Pluribus-grade and don't rebuild it now.
- **Bayesian/δ-safe exploit with exploitability-budget constraint.** The *theory* (RNR, restricted Nash response, LCB-gated deviation) is sound. The convexity bound `Expl(σ_λ) ≤ (1-λ)Expl(σ₀)+λExpl(σ₁)` is correct math. But you can't compute `Expl(σ₀)` because your LBR is vacuous — so the whole budget framework is unbuildable until eval exists. This is downstream of fixing eval. Don't start here.

**No outright hallucinations in gpt-5.5.** The SE math is right (`SE ≈ σ/√(N/100)`, ~4.5 bb/100 at 50k hands) and reinforces what your gates already encode. It's verbose and repeats your own honest caveats back at you as if they're revelations, but it's not lying.

### o3

This one has more to flag because it makes **specific empirical claims it cannot possibly know about your benchmark.**

- **"70–85% fewer node touches", "σ≈19.2 bb → 6.4 bb with AIVAT", "3 show-stopper bugs in our reference deployment", "now 14 bb/100 vs Slumbot reduced ~40%", "≤0.4 bb/100 EV drop merging 3→2 sizes on 85% of boards", "depth-2 LBR <30 sec/hand on RTX 4090".** These are **fabricated specifics** — confident numbers presented as measured facts about systems o3 has never run. The *directions* may be reasonable; the *numbers* are hallucinated. Treat every decimal as decoration, not data.
- **"Regret is zero at t=0 ⇒ convergence to same ε-Nash as full MCCFR with 70–85% fewer node touches."** The general idea (warm-start CFR from an imitation prior) is real and reasonable. The convergence guarantee being *preserved* by warm-starting from arbitrary logits is **not** clean — CFR's O(1/√T) bound doesn't care about your init, and a bad init can hurt as easily as help. The "70–85% fewer" is invented. Item 1 is "bolt MCCFR onto the advisor" which is **a real-time-ish solver by another name** — directly contradicts your "NOT a real-time solver" identity and is a months-long subsystem. This is the over-complex centerpiece dressed as a "drop-in head." It is not drop-in.
- **AIVAT (item 2) is real and correct as a *variance-reduction technique for evaluation*.** But o3 frames it as accelerating self-play *gradient SNR* for a Deep-CFR pipeline you don't have. AIVAT's genuine value *for you* is evaluation variance reduction in your A/B harness — and even that matters only because your gate isn't bb/100 anyway. Lower priority than they imply.
- **Item 5 (property-based tests for equity/pot logic) — REAL, cheap, on-philosophy.** This is the one o3 item that fits your phase perfectly: deterministic checks, kills bugs, no solver cost. The "3 show-stopper bugs" anecdote is fabricated but the *practice* is exactly your "deterministic check" gate. Endorse.
- **Item 9 (Lean) — o3 itself says skip it.** Agreed. See §4.
- **Item 10 (Deep-CFR/ReBeL rebuild) — correctly gated behind "only if exploitability plateaus ≥30 bb/100."** Fine as a tripwire, irrelevant now.

**Bottom line on the two:** gpt-5.5 is the better strategic diagnosis (verbose, no fabrications, but mostly echoes your own honesty). o3 has the one cheap on-philosophy win (property tests) buried among fabricated benchmark numbers and a mislabeled CFR-rewrite "drop-in."

---

## 2. GENUINE HIGH-LEVERAGE MOVES → concrete, smallest-first, with your gates

Ordered by EV-per-effort *given your consolidation phase*. Everything here is measure-or-fix on **existing** modules, no new subsystems except #1.

### Move A — Make the LBR non-vacuous OR scrap it for a leak-injection harness (highest leverage)
**Why:** Everything else (safe-exploit budgets, "are we low-exploitability?", trusting any change) is downstream of having a leak-finder you can trust. You already know your LBR is vacuous.

**Smallest first — don't build "real LBR," build a falsifiable test of the one you have:**
1. In your LBR module: write a **leak-injection wrapper** around your frozen bot policy. Inject a known leak — e.g. force river fold-frequency +20pp on a board class, or remove all river bluffs.
2. Run current LBR against the corrupted bot.
3. **Deterministic gate:** if LBR does *not* show a measurably higher exploit vs the corrupted bot than vs clean, your LBR is provably blind → it's not measuring exploitability, document it as such and stop citing it.
4. Only if it *can't* find injected leaks do you invest in the depth-limited river/turn best-response (o3 item 4's *idea*, ignore its numbers). And even then: river-only exact BR first (you have enumeration), turn later.

**Verification:** deterministic (injected leak detected: yes/no). No bb/100.

This is ~1 week and tells you whether you're flying blind. Do this **before** anything labeled "safe exploit."

### Move B — Solver-EV-gap audit of the advisor (not action-match)
**Why:** Directly tests gpt-5.5's most-correct criticism using assets you already have (TexasSolver caches + advisor).

**Smallest first:**
1. In your advisor eval harness, for every cached solver node you train/validate on, compute `ΔEV(s,h) = EV_solver(a_solver*) − EV_solver(a_bot)` using the **solver's own EVs already in the cache** — you don't need a new solve.
2. Reach-weight it (use solver reach probs if cached, else uniform-within-node as a floor).
3. Produce the leak-bucket table by texture/street/line. This is a reporting change, not a model change.

**Verification:** reach-weighted solver EV-gap (your existing gate, just aggregated differently). 

**Likely outcome:** most of your 11.4% preflop mismatch and advisor MSE will be near-zero-EV indifference nodes (fine), and a small set of buckets will carry the loss. *That* tells you whether the "history-free averaging" leak is real or theoretical — without a rewrite.

### Move C — River solver-calibration (highest *EV* once eval exists)
**Why:** Your own writeup admits river is "not yet solver-calibrated." It's the most solvable street and you have exact enumeration.

**Smallest first:**
1. Don't build a full "river solve cache by public-state class" (that's the over-complex version). Instead: take your existing turn-coverage solve outputs and **extract realized river sub-strategies** where they exist; calibrate the bluffcatch threshold and bluff-selection against *those* combo-exact frequencies.
2. Replace the "small bluffcatch-threshold nudge" with the combo-exact `EV(call) = E·(P+B) − (1−E)·B > 0` decision **where you have a calibrated villain river range**; keep the heuristic only where you don't.

**Verification:** solver EV-gap on river nodes that exist in your cache + held-out frequency-match. Deterministic on the enumeration math.

### Move D — Property-based tests on equity/pot/side-pot (cheapest, on-philosophy)
**Why:** o3's one good cheap item, and it's literally your "deterministic check" gate.

**Smallest first:** Hypothesis/QuickCheck-style: generate random rivers, assert MC-equity within CI of exact enumeration; assert pot/side-pot accounting against an independent reimplementation. ~1–2 days for the first batch.

**Verification:** deterministic, pass/fail.

### Move E — Audit (don't rebuild) the FE-optimal sizing and MDF-shading
**Why:** gpt-5.5 is right *in theory*; you don't know if it's costing you.
**Smallest first:** for a sample of nodes where solver gives EV-per-size, compare your chosen size's solver-EV vs the argmax size. If the gap is small, leave it (consolidation phase). If a bucket bleeds, fix that bucket only.
**Verification:** solver EV-gap per size.

---

## 3. THE single biggest high-leverage move

**Make your exploitability evaluation falsifiable — via leak-injection — before trusting any further change.**

Not "build a real LBR" (that's the expensive version). The move is: **prove or disprove that your current adversarial eval can detect a known, injected leak.**

Concrete step plan:
1. **Freeze** the current bot policy behind a clean interface (you have this for self-play).
2. **Write `inject_leak(policy, spec)`** in/next to your LBR module: parametric corruptions — river overfold +Δ, kill-all-river-bluffs, c-bet-everything on one texture, MDF→0 on overbets.
3. **Run current LBR vs {clean, corrupted}.** Record exploit delta.
4. **Deterministic gate:** LBR must show strictly higher exploit vs each corrupted variant than vs clean, by a margin exceeding eval noise. Tabulate which leak types it catches and which it misses.
5. **Decision fork:**
   - If it catches the big leaks → your eval is usable; now run Move B (EV-gap audit) and Move C (river) and *trust* the LBR to confirm fixes don't open new holes.
   - If it's blind → you've quantified exactly what to fix in the LBR (almost certainly: needs Bayesian range tracking + exact river BR). Build *only* river-exact BR first.

**Why this and not river calibration first:** Move C is higher raw EV, but without a trustworthy leak-finder you can't verify Move C didn't open a new hole, and you can't ever validate the "safe exploit" thesis that is supposedly your edge. Eval is the keystone. It's also ~1 week and pure deterministic verification — perfectly on-phase.

---

## 4. LEAN / formalization — honest verdict FOR YOU

**Not worth it. Skip Lean entirely.** o3 agrees with itself here and it's right.

Reasoning specific to you:
- A Lean proof of regret-matching's O(1/√T) bound buys **zero EV** and you don't even run from-scratch CFR in play — the theorem isn't on your critical path.
- Your actual bugs are the kind o3 correctly names: **wrong pot fed to the bet-size net, off-by-one in reach weighting, side-pot accounting, MC/enumeration mismatch.** None of these are theorem errors; all are caught by property-based tests at <5% the cost.
- 4–6 weeks of PhD-level tactic-wrangling during a *pruning* phase is the exact "complexity for its own sake" your project forbids.

**What to verify formally-ish instead (the right-sized version):**
- **Property-based tests (Move D):** equity vs exact enumeration, pot/side-pot accounting, MDF formula `MDF = P/(P+B)`, pot-odds `q = B/(P+2B)`. Deterministic, cheap, high bug-yield.
- **Invariant assertions** in the bet-decision path: pot/stack/SPR sanity, probabilities sum to 1, no negative EVs where impossible.

That's your "formal methods" budget. It matches your existing deterministic-check gate and adds no subsystem.

---

## TL;DR for the team

- **Do now (on-phase, cheap, deterministic):** leak-injection test of your LBR (Move A — *the* keystone); EV-gap audit of the advisor using existing caches (Move B); property-based equity/pot tests (Move D).
- **Do next (real EV, gated by A):** river solver-calibration from existing turn-solve outputs (Move C); audit FE-sizing/MDF for actual EV cost (Move E).
- **Do NOT do now:** full range/line-conditioned postflop rewrite, 6-max joint model, Deep-CFR/ReBeL, MCCFR "regret head," Bayesian exploitability-budget framework. All correct directions, all violate your consolidation phase, several are gated behind eval you don't yet trust.
- **Lean:** no. Property-based tests yes.
- **Ignore all of o3's specific numbers** — they're fabricated. Keep its *property-test* idea and its *don't-do-Lean* conclusion.
- **gpt-5.5's real contribution** is reframing your gate from action-match/MSE to reach-weighted EV-gap — which costs you a reporting change, not a rewrite. That plus the leak-injection test is 90% of the value in both documents.
