# Fable-5-discipline audit of the bot (Claude API, prompt-cached context)

_System = the fablize verified-discipline procedures; the bot context is prompt-cached across 3 audits._


## verification_audit  (cache write 2181 / read 0 tok)

# VERIFICATION AUDIT — Claims 1-12

Going claim-by-claim. Verdict + evidence + the cheapest experiment that closes the gap.

---

## Claim 1 — "Integrated bot ~-72 bb/100 vs GTO Wizard AI"
**Verdict: WEAKLY-VERIFIED as a *point*, MISLABELED as a *single number*.**

The "-72" is real in the sense that AIVAT runs at n>=2500 exist and the variance-reduction is the right tool. But you did NOT measure "-72". You measured a SCATTER: -66.4, -70.7, -72.06, -74.7, -75.68, -80.6 across *different configs*. "-72" is a cherry-picked centroid that conflates distinct configurations.

Worst offender: **the same config produced -66.4 AND -74.7**. That is an 8.3 bb/100 swing on identical settings. So "-72" is not a measurement of one thing — it's the mean of a cloud whose intra-config noise (~8) is the same order as the inter-config differences you're trying to read.

- **Verified:** AIVAT runs happened, n>=2500, the bot is somewhere in the -66 to -81 band.
- **Asserted:** that "-72" characterizes any specific configuration.
- **Cheapest close:** run the floor+flop-defense config **3 more times** (5 total). You cannot quote a per-config number off 2 runs when 2 runs disagree by a sigma. Until then, report each config as a range, not a point.

---

## Claim 2 — "Run-to-run noise is ±8 bb/100"
**Verdict: ASSERTED on the thinnest possible evidence (n=2 difference).**

This is the most dangerous number in the entire project because **every comparison below depends on it.** You inferred a standard deviation from a SINGLE pair (-66.4 vs -74.7 ≈ "1 sigma apart"). That's not an estimate of sigma — it's one draw from |X1−X2|, which itself has ~100% relative uncertainty. The true sigma could be 4 or could be 14; you cannot tell from two points.

Calling two samples "~1 sigma apart" is also circular: you *defined* the gap as 1 sigma, then quote that as the sigma.

- **Cheapest close:** the same 5 repeated runs from Claim 1 give you an honest sigma for free. This is THE highest-leverage cheap experiment in the whole audit — it underwrites claims 1, 3, 6, 8, 12. Do this first.

---

## Claim 3 — "The resolver HURTS / range-tracker didn't recover it"
**Verdict: ASSERTED — the effect is INSIDE the noise.**

resolver -72/-76 vs floor -66/-71. The resolver-vs-floor gap is ~4-6 bb/100. Your own (unproven) noise estimate is ±8. **The claimed harm is smaller than one sigma of the noise you yourself posited.** This is not evidence the resolver hurts; it's evidence you can't yet distinguish it from break-even.

This is exactly the INVESTIGATION-PROTOCOL failure: you stopped at the first plausible cause ("resolver hurts") without competing the hypothesis "resolver is neutral and you're reading noise."

- **Cheapest close:** PAIRED/duplicate eval, floor vs resolver on the SAME decks (you already have the GTOBaseline duplicate harness). Card-luck cancels, so you'll detect a 4-6 bb/100 effect at far smaller n than AIVAT needs. Until paired, this claim is unsupported.

---

## Claim 4 — "vs Slumbot +31 bb/100"
**Verdict: NOT EVIDENCE OF ANYTHING. stderr ±46 on a +31 mean.**

+31 ± 46 → the CI straddles zero by a mile. You cannot reject "Slumbot beats us" or "we crush Slumbot by 70." This number should not be quoted as a result at all; it's a null.

- **Cheapest close:** Slumbot doesn't offer duplicate boards, so you need n. To get stderr down to ~±15 you need ~9x the hands (~18k). If that's too expensive, **drop the claim** — don't launder a null as "+31."

---

## Claim 5 — "vs weak bots +300..+700 bb/100"
**Verdict: VERIFIED-ENOUGH (low stakes).**

Effect size dwarfs any plausible noise; even sloppy n shows it. The wide range (+300 to +700) honestly reflects opponent-dependence. This is the one place a big number survives thin evidence because the signal is 10-50x the noise.
- **Caveat:** confirm it's not n-per-opponent that's tiny enough to be unstable per-bot. But the *aggregate* claim "we crush weak bots" is safe. Low audit priority.

---

## Claim 6 — "Floor matches solver FREQUENCIES but loses bb/100"
**Verdict: THE STRONGEST CLAIM IN THE SET — VERIFIED, and the sign-flip honesty is exemplary.**

This is the model of how to do it: aggregate freqs aligned (31%/29% gap) *yet* a **PAIRED** oracle head-to-head = -160 ±75 (n=80 decks). And — critically — you caught that the unpaired +184 was card variance and that pairing flipped the sign. That is the INVESTIGATION PROTOCOL done right: you reproduced, competed hypotheses (freq-match vs EV-match), and traced the cause (frequency-matching ≠ EV-matching).

- **One caveat:** -160 ±75 at n=80 is a ~2.1 sigma result. Real, but I'd want it tightened — at n=80 the paired design is doing heavy lifting and you're one unlucky board-cluster from -90. Still, the *sign and mechanism* are solid; this is your most trustworthy finding.
- **Cheapest tighten:** push the paired oracle to n=300 decks. Cheap, deterministic, and nails the magnitude.

---

## Claim 7 — "DCFR+ 445→338 mbb, still falling"
**Verdict: VERIFIED as a single trajectory; OVERREAD as a trend.**

This is honestly reported (you flag "one run," you note iter-75 was *worse* at 544 before dropping, you waited for plateau). Good. But:
- "Still falling" is an eyeball on one seed. The 544→338 path shows DCFR+ is non-monotone, so "still falling at 338" could be another transient.
- The real anchor is the comparison: vanilla tabular CFR hits ~21 mbb. **Your neural DCFR+ at 338 is ~16x worse than tabular** on a game small enough to solve exactly. That's the load-bearing fact and it's verified by the exact-exploitability gate (your gold standard). The neural net is far from the achievable floor.

- **Cheapest close:** 2-3 more seeds of the DCFR+ run to confirm "falling" isn't a single lucky descent. The exact-exploitability gate makes this cheap and unambiguous.

---

## Claim 8 — "First HUNL fcpa net beats call-station/always-fold/random"
**Verdict: SPLIT — vs always-fold VERIFIED; vs call-station ASSERTED (eval is uselessly noisy).**

- vs always-fold ~+47 **stable** → fine, but beating always-fold is a near-trivial bar (just bet your good hands). Low information.
- vs call-station +1621→+519→+1333 across iters → **this is not a measurement, it's a random number generator.** A 3x swing means your eval n is far too small / variance uncontrolled. You cannot claim "beats call-station" with a number that bounces 3x; you can only claim "is positive vs call-station," and even that needs the CI.

The phrase "beats X/Y/Z" bundles one verified result (fold), one near-trivial, and one un-measured. Unbundle it.

- **Cheapest close:** call-station has no strategy, so **duplicate/paired eval cancels nearly all variance** for free. Run paired vs call-station; the ±1100 swing should collapse to a tight CI. There is no excuse for ±1100 against a fixed-strategy opponent.

---

## Claim 9 — "Fine bet abstraction + richer features = next-highest-leverage upgrade"
**Verdict: ASSERTED. NOT measured on our bot — you say so yourself.**

"4 sources converge" is consensus-of-priors, not evidence about THIS bot. MoP/AAAI-paper/GPT-5.5/Supremus agreeing tells you it's a *reasonable hypothesis*, not that it's *your* highest-leverage lever. This is the classic "the plan is" masquerading as a finding. Convergent priors have a real failure mode: they all share the same blind spot (none of them measured your resolver-hurts or freq-vs-EV problem).

- **Cheapest close:** an ablation. Add ONE finer bet size to the existing fcpa abstraction → fcpah, re-eval paired. One axis, measured, on your bot. Until then this is a hypothesis, not a roadmap fact.

---

## Claim 10 — "Plateau priors: fcpa -50..-80, fine -20..-45, value-net -15..-30"
**Verdict: HOPED. Explicitly flagged as GPT-5.5 engineering priors, not measured.**

Credit for the honest flag. But these numbers should never appear next to your *measured* -72 in any summary, because the human eye anchors on them. The danger isn't the priors — it's adjacency to real measurements creating false equivalence. Keep them in a clearly-walled "untested projections" box.
- **Close:** these only become real by building the things and measuring. No cheap experiment; that's the whole project.

---

## Claim 11 — "A B200 won't help; Python MCCFR traverse is the bottleneck"
**Verdict: WEAKLY-evidenced (reasoned + one anecdote). Not profiled.**

You have a real observation (GPU slower for tiny Leduc nets due to transfer overhead) and a plausible mechanism. But "tiny Leduc nets" is exactly the regime where GPU loses; it tells you nothing about HUNL-scale nets where the batch is big enough to amortize transfer. Generalizing from the toy case to "B200 won't help" is unsupported — possibly backwards.

- **Cheapest close:** `cProfile` / a single timed run on the HUNL net. Five minutes. Get the actual %-time-in-traverse vs %-in-net-forward. You're spending a paragraph of conviction on a measurement that costs one command. Do it before any hardware decision.

---

## Claim 12 — "Commit-cap anti-spew fix"
**Verdict: HONESTLY UNPROVEN, correctly left OFF.**

+8.5 ±12 (straddles zero, ns), fired 3/600 decks. You correctly note the opponent doesn't create the spot, so the test is **underpowered by construction** — n_effective is 3, not 600. Leaving it off is the right call. This is good discipline: a non-result reported as a non-result.
- **Cheapest close:** test against an opponent that *does* over-commit (a spewy bot), so the fix actually fires. Against GTOBaseline this fix is untestable, full stop.

---

## TRUSTWORTHINESS RANKING (most → least)

| Rank | Claim | Verdict | Why |
|---|---|---|---|
| 1 | **6** (freq≠EV, paired -160) | VERIFIED | Paired design, sign-flip caught, mechanism traced |
| 2 |


## causal_chain_audit  (cache write 0 / read 2181 tok)

# CAUSAL-CHAIN AUDIT: The -72 bb/100 vs GTO Wizard AI

## Verdict up front

**The cause is NOT traced. It is measured and bounded, but not localized.** You have a robust *magnitude* (-72, tight across configs) and you have *correlational dissection* (resolver vs floor deltas). You do **not** have a per-street / per-line / per-size attribution of where the loss is generated. The phrase "broad postflop quality" is a label for an untraced gap, not a finding.

Let me hold each piece to the evidence.

---

## 1. What is actually verified vs. asserted

| Claim | Status | The evidence that exists |
|---|---|---|
| Magnitude ≈ -72 | **VERIFIED** | n≥2500 AIVAT, 6 configs clustering -66 to -81. This is real and decision-grade. |
| Run-to-run noise ±8 | **WEAK/ASSERTED** | Claim 2 — TWO data points (-66.4, -74.7). You cannot estimate a sigma from n=2. This is a guess dressed as a number. |
| Resolver hurts | **SUGGESTIVE, not isolated** | -72/-76 < -66/-71. But the floor configs themselves span 15bb (-66 to -81). The resolver delta (~5-6bb) is *inside* your own unmeasured noise band. You have not falsified "resolver is neutral + you got unlucky." |
| Floor matches freqs but loses bb/100 | **PARTIALLY VERIFIED** | This is your strongest real finding. The paired oracle -160±75 (Claim 6) is the load-bearing evidence: frequency-matching ≠ EV-matching. **But it does not tell you WHICH decisions cost the EV.** |

The freq-match-but-lose result (Claim 6) is the one genuinely traced *mechanism* (you imitate frequencies, frequencies are a lossy projection of strategy, so you bleed EV on the conditional/sizing details freqs throw away). That is a real localized cause — **of the FLOOR**. It is not a localization of the -72 across streets.

---

## 2. Did you FALSIFY any competing hypothesis, or assert convergence?

You named five hypotheses: **abstraction, features, convergence, ranges, sizing.**

**Falsified: zero.** Here is the honest accounting:

- **Convergence** — you have Leduc exact exploitability as a gate, but that gates the *neural pivot*, not the floor's deployed strategy. The floor is solver-imitation; its "convergence" is the solver's, which is fine. So convergence is *eliminated for the floor by construction*, not by experiment — acceptable, but note it's an argument, not a measurement.
- **Ranges** — Claim 3 (range-tracker "did not recover it") is the closest you got, and it is correlational and inside the noise band. Not falsified, not confirmed.
- **Abstraction / Features / Sizing** — these are the three that Claim 9 says "4 sources converge" on. **Convergence of opinions is not falsification of the other three.** GPT-5.5 + Supremus + a paper + MoP agreeing that fine bet abstraction is high-leverage is *prior*, not *posterior*. You explicitly flag Claim 9 as "NOT measured on our bot" and Claim 10's priors as "not-measured." **Good — you flagged it. But that flag is exactly the admission that the cause is untraced.**

So the answer to "did we falsify any or assert convergence?" is: **you asserted convergence among external opinions and measured none of the five hypotheses against the actual -72.** The five remain fully alive and uncontrasted.

---

## 3. Is the neural-net pivot grounded in a traced cause?

**No. It is a method-switch hoping to escape a cause you never localized.**

The logic chain as it stands:
1. Floor imitates frequencies → loses EV (the ONE traced thing, Claim 6).
2. Therefore: build a from-scratch self-play net that doesn't imitate.

Step 2 is reasonable as a *hypothesis* but the inference is incomplete. You traced that imitation is lossy. You did **not** trace that imitation-loss is the *dominant term* in the -72. Possible the dominant term is your **bet-size abstraction** (which the neural net inherits unless fcpa→fine), or your **resolver's range construction**, or a specific street. If the -72 is 50bb of "wrong sizes on turn" and 22bb of "imitation slop," Deep CFR with fcpa abstraction fixes the small term and keeps the big one.

And the neural evidence itself (Claims 7, 8) is **thin and bouncy**: one Leduc run, eval bouncing +1621→+519→+1333. By your own standard ("INVESTIGATION PROTOCOL: COMPETE the hypotheses, trace the COMPLETE causal chain") the pivot is currently a hope, not a traced remedy. The GTOW baseline of the net is "RUNNING now" — until it lands, the pivot has **zero** GTOW evidence.

This is the central honesty point: **you are switching engines to fix a leak whose location in the engine you never measured.**

---

## 4. The single cheapest experiment to trace WHERE the -72 comes from

**You almost certainly already have the data: the per-hand GTOW logger.** No new compute. The experiment is a *read* of existing logs, not a new run.

### The experiment: EV-attribution decomposition of the per-hand GTOW log

If the per-hand logger captured, per decision node: street, action taken, pot size, and the AIVAT/EV baseline, then:

1. **Group the per-hand EV loss by STREET** (preflop / flop / turn / river). Sum the AIVAT-adjusted EV contribution per street. This alone tells you if -72 is a river problem or a turn problem or smeared. *Cheapest, do first.*
2. **Within the worst street, group by LINE** (e.g., "checked-to on turn IP," "facing turn barrel," "river overbet faced"). Rank lines by total EV bled.
3. **Group by SIZE BUCKET** of your own action and of the action you faced — does the loss concentrate where the *opponent* uses sizes outside your abstraction (the abstraction hypothesis becomes directly testable: if your biggest losses are on nodes where GTOW bet 0.33x or 1.5x pot and you mapped to your nearest bucket, that's a measured abstraction cost).

This decomposition **directly contrasts three of your five hypotheses on real data**:
- Loss concentrated on off-grid sizes → **abstraction** is the cause (validates Claim 9 *for your bot*).
- Loss concentrated on specific streets with on-grid sizes but wrong frequencies/holdings → **features/imitation** (validates the pivot).
- Loss concentrated where the resolver was active vs not → **ranges/resolver** (turns Claim 3 from correlational into causal).

### The gating question you must answer FIRST (cheapest check of all)
**Does the per-hand gtow logger actually record the per-node EV/AIVAT baseline and the sizes faced — or only the final per-hand result and your action?** 

- If it logs per-node EV deltas → you can do the full street/line/size attribution in an afternoon of pandas, **zero compute.**
- If it only logs hand outcomes + actions (no baseline EV per node) → you can still do **street-of-last-aggression** and **size-bucket** breakdowns by outcome, which is weaker (no AIVAT per node, so noisier) but still localizes to street within a few thousand hands. Cheaper than any new run.

**This is the one experiment to run.** It converts -72 from a number into a map. Until that map exists, every word about abstraction-vs-features-vs-ranges — including the neural pivot's justification — is reasoning over an unobserved distribution.

---

## 5. Cheapest fix to the *secondary* groundless claims (while you're in the logs)

- **Claim 2 (±8 noise):** you cannot fix n=2 from logs, but you CAN bootstrap a per-hand variance estimate from any single n≥2500 run's per-hand EVs → a real CI on a single config, replacing the fake ±8. Free, same data.
- **Claim 3 (resolver hurts):** once you have street/line attribution, tag resolver-active vs floor-only nodes and compare their EV bleed directly. Turns a between-run correlation into a within-run paired contrast. Free, same data.

---

## Bottom line

- The -72 is **real and verified**; its **cause is not traced**, it is *bounded and labeled* ("broad postflop quality" = untraced gap).
- You **falsified none** of abstraction/features/convergence/ranges/sizing; you asserted convergence of *opinions*, which you correctly flagged as not-measured.
- The neural pivot is **grounded in one real sub-finding (imitation is lossy)** but **not grounded in evidence that imitation-loss dominates the -72** — so it is currently a method-switch hoping to dodge an unlocalized cause.
- **Cheapest experiment:** per-street → per-line → per-size EV-attribution read of the existing per-hand GTOW log. **First verify the logger records per-node EV/AIVAT** (one grep / one schema check). If yes: full trace, zero compute. If no: street-of-aggression + size-bucket outcome breakdown, still zero new compute, still localizes.

Do that read before spending another GPU-hour on the pivot. You are choosing a cure without an X-ray, and the X-ray is probably already in your `logs/` directory.


## next_build_rigor  (cache write 0 / read 2181 tok)

# NEXT-BUILD RIGOR AUDIT: Fine Abstraction + Richer Features

## First, name the violation in the premise

Claim 9 ("fine bet abstraction is the next-highest-leverage upgrade") cites "4 sources converge." Under FABLE-5 discipline this is a **PROMISING-WITHOUT-DOING** flagged correctly by your own note ("NOT measured on our bot") — but the danger is that you'll let convergence stand IN PLACE of a measurement. Four people agreeing about your bot is zero bits of evidence about your bot. MoP theory, an AAAI paper, GPT-5.5, and Supremus all reason from priors that may not bind on YOUR codebase, YOUR abstraction, YOUR opponent (GTOW AI). Convergence of priors raises your subjective probability; it does not move a single bb/100. Treat claim 9 as a HYPOTHESIS, not a justified plan.

## The noise floor kills naive A/B testing — do the math first

This is the cheapest and most important thing to verify, and it costs zero compute.

Your run-to-run noise is "±8 bb/100" — and that number is itself almost worthless: claim 2 is **INFERRED from TWO data points** (-66.4 vs -74.7). Two points give you essentially no estimate of σ. The real σ could be 8, could be 15. **Before any abstraction work, your cheapest highest-value experiment is to pin σ.**

- **Test:** Run the SAME config (floor+flop-defense, the one you ran twice) 3 more times. Total 5 runs.
- **Cost:** Same as one abstraction experiment, but it CALIBRATES every future experiment.
- **Pass/fail:** You now have a real σ. If σ ≥ ~10 bb/100, then to detect a 15 bb/100 improvement at the conventional 2σ separation you need the difference to clear ~28 bb/100 — meaning fine-abstraction must move you from -72 to better than ~-44 in a SINGLE n≥2500 run to be distinguishable from noise. That is the bar. Know it before you spend the compute.

Without this, you will run fine-abstraction once, see -64, and "the convergence was right." That -64 is **inside your own measured noise band.** That is the rationalization trap, pre-loaded.

## Smallest falsifiable test for fine-abstraction itself

The mistake would be to build the full fine-abstraction net and run GTOW at n=2500. That's the expensive end. Decompose:

**Gate 0 (free, do today):** Does the current coarse abstraction actually limit you? Take 50–100 hands where your bot's GTOW-measured loss is largest and check: in how many is the bot FORCED to a wrong sizing bucket because the action it "wanted" isn't in the abstraction? 

- **Pass:** ≥30% of large-loss decisions are abstraction-pinned (the right size exists outside the bucket grid).
- **KILL:** <10% are abstraction-pinned. If the losses come from RANGE/strategy errors inside available buckets, finer buckets cannot help — you'd be adding resolution where the error isn't. **This single cheap check can kill the direction before any training.**

**Gate 1 (cheap, exact):** Re-run fine vs coarse abstraction in **Leduc with exact exploitability** — your gold gate. You already have deep_cfr.py Leduc. Add the finer bet grid there.

- **Pass:** finer abstraction reaches measurably lower exact exploitability at matched compute.
- **KILL:** finer abstraction does NOT lower Leduc exploitability, or needs vastly more iterations to plateau. If the mechanism doesn't help in the game where you can MEASURE TRUTH EXACTLY, the HUNL claim that it will help is unsupported. This is the strongest cheap falsifier you own — use it.

**Gate 2 (paired, mid-cost):** Fine vs coarse, paired/duplicate vs GTOBaseline (card-luck cancelled, the method that already flipped your +184 floor result to -160). The pairing is what gives you signal at low n.

- **Pass:** fine beats coarse by a paired margin clearing 2× the paired stderr.
- **KILL:** paired difference is non-significant or negative — same as the commit-cap +8.5 ±12 (ns) outcome in claim 12. If it lands there, fine-abstraction is "left OFF, unproven," not "the next-highest-leverage upgrade."

**Only after Gates 0–2 pass** do you spend the n≥2500 GTOW run. The full GTOW eval is the LAST step, not the test.

## What result KILLS the direction (write this down NOW so you can't wriggle)

Pre-register, before seeing data:
1. Gate 0 shows <10% abstraction-pinned losses, **OR**
2. Gate 1 shows no exploitability reduction in exact Leduc, **OR**
3. Gate 2 paired margin is non-significant or negative.

Any one of these KILLS fine-abstraction as "highest leverage." The forbidden move is: get a GTOW result of -64 (inside noise), declare partial success, and keep going. -64 vs -72 with σ≥8 is **NULL**. Say it now.

## The deeper question: yes, you are at high risk of the same trap

This is the sharpest part of your question and the answer is **YES, and worse.**

The floor trap (claim 6) was: aggregate frequencies matched the solver (31%/29% gap, "freqs aligned") **but the paired oracle test was -160 ±75.** Frequency-match ≠ EV-match because EV lives in the *conditional* policy — the right size with the right hand in the right node — which marginal frequencies average away.

Now consider self-play Deep CFR. The trap mutates:

- **Your training objective is regret minimization, NOT bb/100 vs GTOW AI.** A net can drive self-play regret toward zero and STILL lose to GTOW, because GTOW is a different opponent than the self-play distribution. You'd be matching your own equilibrium's frequencies, not exploiting GTOW.
- **The eval evidence already shows the instability that hides this.** Claim 8: call-station eval bounces +1621→+519→+1333. That is huge eval variance masking what the policy actually converged to. A frequency-stable, EV-unstable net is exactly the floor trap wearing a new coat.
- **Claim 7's "445→338, still falling"** is a single run measured by an exploitability proxy, not by EV vs your target opponent. "Still falling" is HOPED progress, not DONE progress against the goal.

**The specific guard:** never accept "self-play regret/exploitability dropped" as evidence of "beats GTOW." Those are different metrics on different opponents. The ONLY thing that closes this gap is the metric you actually care about: paired EV vs GTOW (or your GTOBaseline as proxy). 

**Cheapest guard experiment:** build the **clairvoyance toy game you already have planned but NOT built.** It's listed in your validation methods as "planned, not yet built." Under FABLE-5 that's a promise, not a result. It is precisely the instrument that separates "frequency-correct" from "EV-correct" in a setting with known ground truth. Build it before, not after, you trust the self-play net's EV. It will catch the floor trap recurrence at near-zero compute.

## Multi-story scorecard

| Objective | Status |
|---|---|
| σ is known | **DECLARED, not evidenced** (2 points). Fix: 5-run replication, free-ish. |
| Fine-abstraction helps | **HYPOTHESIS** (convergent opinion only). Gates 0–2 unbuilt. |
| Self-play net beats GTOW | **NOT EVIDENCED.** Only self-play proxies + bouncy head-to-head exist. |
| Clairvoyance EV-vs-freq guard | **PLANNED = not done.** Highest-value cheap build. |

**Cheapest path that closes the most gaps:** (1) 5× replication to pin σ, (2) Gate 0 abstraction-pinning audit on existing GTOW loss hands — both essentially free and either could kill the direction before you burn the compute. Do those two before anything else.
