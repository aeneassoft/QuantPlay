# NEXT NEURAL-NET RUN — TO-DO (one-go execution)

Synthesized 2026-06-16 from FOUR independent sources that **converge on the same answer**, + in-session vetting:
- **Mathematics of Poker** (Claude, `math_theory_net_connection.md`): fcpa is "structurally impoverished"; strength
  buckets can't express GTO (need polarity/blockers/SPR/texture); the clairvoyance toy-game is an EXACT validation.
- **AAAI-26 Deep DCFR+** (`knowledge_base/theory/deep_pdcfr_paper.json`): DCFR+ = the convergence engine (DONE,
  validated: Leduc neural 445→338). Variance-reduction is real but secondary for external sampling.
- **GPT-5.5 architecture consult** (`cfr_architecture_gpt55.md`): Rank-1 = finer betting; Rank-2 = richer features;
  DCFR+ done; VR/scale/resolving are later. (All bb/100 numbers below are ENGINEERING PRIORS, not measured.)
- **Supremus** (`supremus_paper.json`): SOTA uses fine abstraction (F/C/0.33/0.5/0.75/1/1.25/2/A) + CFV value nets +
  continual resolving. We adopt the abstraction now; the value-net/resolving is the deferred ceiling.

**The verdict (vetted, high-confidence): the fcpa abstraction + 20-dim strength features are the ceiling, NOT the
CFR variant. Next run = FINE bet abstraction + RICHER features, gated by a cheap paired A/B vs GTO Wizard.**

---

## The run (do these in order)

### 1. Finer bet abstraction — Rank 1, the biggest lever  `deep_cfr_hunl.py`
Replace fcpa with the menu: **`fold / call|check / 0.33 / 0.5 / 0.75 / 1.0 / 1.25 / 2.0 / all-in`** (pot fractions).
- Prune duplicate/illegal sizes after min-raise + stack-cap rounding; keep the existing `MAX_RAISES` cap.
- `fold` only when `owe>0`; call/check always. This only adds REPRESENTATIONAL CAPACITY — no strategy injected.
- Math grounding: geometric sizing, polarization→overbet, merge→small bets — all impossible under pot-only.
- Cost: ~1.8–2.8× slower/iter (bigger branch factor, Python traverse). Worth it.

### 2. Richer features — Rank 2, bundle with #1  `deep_cfr_hunl.features`
Keep the current 20 + add: **52-dim private-card occupancy + 52-dim board occupancy + explicit hand-class /
draw / blocker / texture flags** → ~140–170 dim. (Strength buckets collapse exactly what GTO needs: nut-advantage,
blockers, SPR, texture.) **NOT WEVA** — vetted low-ROI for full HUNL (its warm-up-CFR-EV method needs a tabular
abstraction that doesn't fit; both GPT-5.5 and our triage agree).

### 3. DCFR+ port to HUNL + target scaling  `deep_cfr_hunl.py`
Port the Leduc-validated DCFR+ into the HUNL trainer (currently LinearCFR): clear adv buffer each iter; target
`max(R_{t-1},0)·(t-1)²/((t-1)²+1) + advantage` (clip BEFORE discount); γ=2 policy averaging via **normalized
`(t/T)²`** (numerical safety vs unbounded `t^γ`). Utilities already scaled `/20000` (SCALE) → keep.

### 4. NO variance-reduction baseline yet — Rank 4, deferred
We use EXTERNAL sampling (the updating player enumerates actions) → VR upside is modest + an unvalidated ES baseline
can silently bias targets. Add it ONLY after: Leduc exploitability still passes + the ES control-variate is validated
at sampled opponent/chance nodes (NOT enumeration nodes).

---

## The gate — cheap paired A/B (decides if this direction is worth big compute)
Three arms, identical wall-clock (~45–90 min each on the 3080 Ti), DCFR+ on, `K=80`, `T≈800–1200`:
- **A** = fcpa + 20 feat  (= the baseline net training now; its GTOW number is Arm A)
- **B** = fine menu + 20 feat
- **C** = fine menu + rich feat

Eval: sanity vs always-fold/check-call/random FIRST (catches action-masking bugs), then **GTO Wizard paired n=500–1000**
(noise ≈ ±18 @ n=500, ±13 @ n=1000). **Continue with fine abstraction only if B or C beats A by ≥15–25 bb/100.**
If not → the next direction is NOT more scale; it's resolving/value-net (#8).

## The two HARD validation gates (math theory — keep both)
- **Leduc exact exploitability** (existing correctness gate — the best test we have).
- **Clairvoyance toy-game test** (NEW): construct a polarized nuts-or-air river spot; assert the net bluffs at
  **α = s/(1+2s)** (=1/3 at pot) and defends at **MDF = 1/(1+s)** (=1/2 at pot), ±0.05. RIVER/terminal ONLY —
  do NOT assert α/MDF on flop/turn (semi-bluffs + equity realization correctly break it).

---

## Compute / scale reality (vetted)
- **CPU traversal + GPU minibatch.** The bottleneck is the Python traverse, NOT the net → a B200 does NOT help the
  current code (and was measured slower for tiny nets). NO pod until a GPU-native job exists (the value-net pipeline).
- Cheap local speedup FIRST: **multiprocess the traversal** (embarrassingly parallel; unused cores on the 3080 Ti box).
- Real run after the A/B passes: `T≈3000, K=80`, fine menu, rich features.

## Deferred (the real ceiling, after the A/B proves abstraction)
- **CFV value net + depth-limited continual resolving** (Supremus/DeepStack). The path to near-parity, but a full
  architecture (public-state ranges, CFV nets, safe re-solving) — not a patch. This is where policy-net-only plateaus.
- **Sequential-Equilibrium refinement** (ICLR-26 paper) → the EXPLOIT overlay (off-equilibrium play vs weak
  opponents), kept SEPARATE from the pure-self-play GTO core.

## Honest plateau priors (NOT measured — engineering priors from GPT-5.5 + our −72)
| architecture | expected vs GTO Wizard |
|---|---:|
| fcpa policy-net (current) | −50…−80 |
| fine-abstraction policy-net | −20…−45 |
| + richer features + much more traverse | −15…−35 |
| value-net + resolving (first competent) | −15…−30 |
| mature Supremus-style resolving | −5…−15 (near 0 only with serious scale) |

**Bottom line: policy-net-only can plausibly beat −72; matching GTO Wizard likely needs resolving. Prove the cheap
abstraction win first; don't burn compute or a pod before the A/B says go.**
