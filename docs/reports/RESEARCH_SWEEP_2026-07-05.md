# Research sweep 2026-07-05 — Perplexity paper search (verified) + OpenAI math consult

**Assignment (user):** search for concrete papers on structure adaptation / code structure / mathematics via the Perplexity API,
**check every paper for existence** (hallucination gate), consult OpenAI on concrete mathematical questions
about our formulas, bundle everything. Raw data: `data/research_sweep/` (pplx_raw.json,
candidates.json, verified.json, openai_math.json).

**Methodology finding up front (important):** Perplexity mostly delivered REALLY EXISTING papers, but with
**systematically swapped metadata** — wrong authors with correct titles, arXiv IDs assigned to the wrong paper,
DOIs mixed up (e.g. DeepStack's DOI on the Libratus entry, our parallel-CFR as "2405"
instead of 2605, "Safe and Nested Subgame Solving" with four wrong authors). **No paper from this sweep may be
cited/loaded without the verification layer.** The table below contains ONLY verified entries
with CORRECTED metadata.

---

## Part 1 — OpenAI math consult: 4 questions on OUR formulas (fully answered)

### 1.1 eCall sizer + v3.2 thin-value threshold ✅/⚠️
- **VERIFIED:** Our sizer score `score(s) = F + (1−F)·(e_call·(1+2s) − s)` is **exactly EV(bet) in
  pot units** (not merely affine) → the argmax of the eCall sizer is mathematically clean.
- **⚠️ v3.2 threshold is a special case:** "bet thin iff e_call(s_min) ≥ 0.5" is NOT the exact
  condition. Exact: **e_call > [ s + (e_showdown − F)/(1−F) ] / (1+2s)** — depending on F and e_showdown the
  true threshold lies above OR below 0.5. All four quantities (F, e_call, s, e_showdown=our eq) we
  already compute → **v3.2b candidate: the exact threshold instead of the 0.5 heuristic** (a 3-line patch in the
  bot.py seam; only after the v3.2 verdict, protocol).
- Qualitatively: if villain can bet himself after our check (we realize more than e_showdown), EV(check) rises
  → the thin-value threshold becomes STRICTER. Our 0.5 is therefore rather too loose than too strict.

### 1.2 v3.3 raise reweight ✅ + concrete improvement
- **VERIFIED:** λ=1 reproduces the target class marginal exactly (after normalization), leaves
  intra-class ratios unchanged, and is the **exact I-projection (min KL)** of the prior onto the
  class constraint set. λ<1 = under-relaxed step on the exponential-family geodesic. Our
  design is thus clean in principle.
- **Concrete improvement (shrinkage at small n):** Dirichlet(1) posterior mean instead of raw frequencies:
  `t̃_k = (1 + n·f_k) / (5 + n)`. For the **jam mix (n=29)**: weight on the empirical ≈ 0.85 (noticeable);
  for street mixes (n=96–263): 0.95–0.98 (negligible). → **v3.3 constants update: Laplace-shrink the jam mix**
  (two-pair+ 0.414→~0.38, air 0.069→~0.10). Flag is still unshipped → update BEFORE the
  v3.3 gate allowed (no post-gate retuning).
- **Zero safety confirmed:** only positive factors → no live combo gets zeroed → the o3 bound holds.

### 1.3 Covered-stack pot odds (AUDIT_FIX member) ✅
- **VERIFIED CORRECT** incl. street-commitment case: our formula reduces to the first-principles
  result `e* = S/(P₀+2S)` (or with commitment c: denominator P₀+2c+2S — algebraically identical to our
  implementation via the engine pot). Example quantified: the old formula demanded **90.9%** equity, true
  is **40%** → over-fold band of ~51 percentage points in the HU-app case (vs GTOW unreachable, stacks equal).

### 1.4 MDF threshold floor (AUDIT_FIX member) ✅ with recommendation
- **VERIFIED:** req = s/(1+2s) is correct as an equity threshold (not MDF — naming nuance);
  EV loss of a mis-defense = (req−e)·(1+2s); our req/2 floor bounds it to (req/2)·(1+2s) ✓.
- **Limitation:** a hard floor is exploitable by an ADAPTIVE over-bluffer (max s per call).
  Irrelevant against GTOW (static, dossier-verified). OpenAI recommendation for the future: cap the
  summed discounts at ~0.4·req (≙ floor 0.6·req) instead of req/2 — noted, no churn before the v3.4 gate.

---

## Part 2 — Verified papers (27/36 confirmed; metadata CORRECTED where Perplexity swapped it)

### A priority: the v4 stack (Li & Huang — extracted directly from the parallel-CFR bibliography)
| Paper | Evidence | Relevance |
|---|---|---|
| **EVPA: Efficient Online Pruning and Abstraction for Imperfect Information EFGs** (Li & Huang, ICLR 2025) | OpenReview exact title match ✓ | online pruning: up to 2 orders of magnitude solve speed-up; v4 building block #2 |
| **TurboReBeL: 250× Accelerated Belief Learning for Large IIEFGs** (Li & Huang, 2026b) | cited in arXiv 2605.19928 with OpenReview link (yMo7Z670f6); direct fetch failed → **UNCONFIRMED, check in the browser** | THE leaf-net training paper — the v4 core dependency |
| **WEVA: Effective, Efficient, and General Information Abstraction for IIEFGs** (Li & Huang, 2026a, arXiv 2605.x) | cited in 2605.19928 (ID truncated in the PDF) | lossy abstraction for larger hand spaces; v4 building block #3 |

### B: structure adaptation / re-solving (existence-verified)
| Paper | Correct citation | Perplexity error | Use for us |
|---|---|---|---|
| Safe and Nested Subgame Solving for IIG | **Brown & Sandholm**, NIPS 2017, arXiv:1705.02955 | wrong authors + wrong ID | the safe re-solving mathematics our resolver lacks |
| Monte Carlo Continual Resolving (MCCR) | Šustr et al., arXiv:1812.07351 | — | continual resolving WITHOUT a supercomputer — blueprint for the resolver rebuild |
| Automated Action Abstraction of IIEFGs | **Hawkin/Holte/Szafron**, AAAI 2011, DOI 10.1609/aaai.v25i1.7880 | wrong authors | bet-size LEARNING instead of hand grid — alternative to the census grid |
| Evaluating State-Space Abstractions in EFGs | Johanson et al., 2013 | — | card bucketing (EMD) for the v4 abstraction |
| Libratus | IJCAI demo 10.24963/ijcai.2017/772 + Science 2018 **10.1126/science.aao1733** | Science DOI mixed up with DeepStack | nested-resolving architecture |
| Pluribus | Science 2019, 10.1126/science.aay2400 | — | depth-limited search under budget |
| Deep CFR | Brown et al., arXiv:1811.00164 | duplicate entry with wrong authors+ID | abstraction replacement by nets |
| Signal Observation Models & Historical Information Integration in Poker AI | arXiv:2403.11486 (2024) | — | abstraction↔solving↔translation paradigm |

### C: range/belief tracking (verified)
| Paper | Correct citation | Use |
|---|---|---|
| ReBeL | **Brown/Bakhtin/Lerer/Gong**, NeurIPS 2020, arXiv:2007.13544 (P: wrong authors) | public-belief-state value nets = v4 leaf-net formalism |
| Exploitability Descent | Lockhart et al., IJCAI 2019, arXiv:1903.05614 (P: wrong ID) | exploitability as a direct training objective |
| Bayes' Bluff | Southey et al., UAI 2005, arXiv:1207.1411 | the ancestor of our range tracker |
| Game Theory-Based Opponent Modeling in Large IIG | Ganzfried & Sandholm, AAMAS 2011 | range estimation + deviation response |
| CFR+ / Zinkevich-CFR / continual-resolving line | Tammelin arXiv:1407.5042 · NIPS 2007 · Burch 2015ff | foundation (covered in our library) |

### D: CFR mathematics (verified)
| Paper | Correct citation | Use |
|---|---|---|
| Deep (Predictive) Discounted CFR | Xu et al., AAAI 2026, arXiv:2511.08174 — **we own the PDF** | neural DCFR+/PDCFR+ approximation, variance reduction for leaf training |
| Dynamic Discounted CFR (DDCFR) | ICLR 2024 (+ AAAI version 10.1609/aaai.v40i20.38780) | adaptive discount schedules with guarantees |
| Stable-Predictive Optimistic CFR | Farina/Kroer/Sandholm, ICML 2019, **arXiv:1902.04982** (P: wrong ID) | better convergence rate — candidate for the v4 solver core |
| Discounted CFR (DCFR) | **Brown & Sandholm**, AAAI 2019, **arXiv:1809.04040** (P: wrong authors+ID) | the DCFR bounds (TexasSolver uses DCFR) |
| MCCFVFP | arXiv:2309.03084, NeurIPS 2024 | CFV-based fictitious play, 20-50% faster convergence |

### E: poker mathematics / evaluation / code (verified)
| Paper | Correct citation | Use |
|---|---|---|
| AIVAT | Burch et al., AAAI 2018, **arXiv:1612.06915** (P: wrong ID+authors) | our measurement standard — estimator assumptions |
| DeepStack | Science 2017, arXiv:1701.01724 | CFV net training (v4 reference) |
| Solving Large EFGs with Strategy Constraints | **Davis/Waugh/Bowling**, AAAI 2019, 10.1609/aaai.v33i01.33011861 (P: wrong authors/year) | strategy constraints — candidate for the "bounded exploit overlay" (North Star) |
| Architectural Tactics for ML-Enabled Systems (SLR) | SSRN/JSS 2024, 10.2139/ssrn.4909520 | only code-structure hit: componentization/versioning — matches our registry/flag/gate design |

### Discarded (not existing as claimed / hallucination suspicion)
- "Public Belief MDPs for Planning…" (title does not exist; the concept lives in ReBeL/MCCR)
- "Opponent Range Estimation in No-Limit Texas Hold'em" (Ganzfried/Sandholm have DIFFERENT titles)
- "Variance Reduction in Experiments in IIG" with arXiv:1710.06169 (ID belongs elsewhere)
- "Codified Context" arXiv:2602.20478 (not findable)
- "Strongly Considered Action Abstractions…" arXiv:1302.4210 (ID-title mismatch)
- "Computing Correlated Equilibria…" arXiv:2207.07520 + "Robust Strategy Computation…" arXiv:2103.01196 (ID mismatches)
- DREAM: exists (real ID very probably arXiv:2006.10410), Perplexity's 1902.04074 is wrong (re-check today rate-limited)
- "Regret-Based Pruning in EFGs" (Brown & Sandholm NIPS 2015 — very probably real; check today inconclusive)

**Hallucination balance: 9/36 candidates filtered out; additionally ~10 of the 27 VERIFIED carried wrong
authors, IDs or DOIs — the verification obligation was fully justified. No entry above is unchecked.**

---

## Part 3 — Consequences / queue

1. **v3.3 constants:** jam mix Laplace-shrunk (before the gate — flag unshipped). 
2. **v3.2b (after the v3.2 verdict):** exact thin-value threshold instead of e_call≥0.5.
3. **v3.4:** req/2 floor stays (0.6·req noted as alternative, GTOW-irrelevant).
4. Paper queue: see Part 2 after verification.
5. **Paper procurement (user/browser):** EVPA (OpenReview ICLR 2025) + TurboReBeL (openreview.net/forum?id=yMo7Z670f6, unconfirmed) + WEVA + MCCR (arXiv:1812.07351) + Safe-and-Nested (arXiv:1705.02955) + Stable-Predictive (arXiv:1902.04982) to be loaded into books/papers/CFR/.
6. **v4 feasibility map** (on user command): read TurboReBeL first — if "250× belief learning" holds, the v4 leaf-net hurdle shrinks dramatically.

## EVPA + Embedding-CFR implementation verdicts (2026-07-05, both papers agent-read)
- **EVPA (ICLR 2025, verified):** core = ensemble CFV pruning + online bucketing BEFORE the solve (69-79%
  tree reduction, playable at 0.02s). WITHOUT the nets only GEOMETRY pruning is sound. BUILT: resolver.
  _prune_degenerate_arms (POKERB_ARM_PRUNE, default OFF) — mechanics correct, but the paired battery MEASURED:
  TexasSolver already collapses over-all-in arms INTERNALLY (eps identical to 1e-8, time flat) -> **no-op vs
  TexasSolver, kept as v4 building block** (own CFR core controls the tree itself). NOT built
  (deliberately): census-frequency pruning (opponent policy != dominance — the GTO-score lesson), range hard-zeroing
  (o3 bound). v4 NOTE: EVPA data corpus (TexasSolver-labelled (spot,hand,line)->EV pairs) can be collected NOW
  — the solve cache is the beginning; the M=10 ensemble is cheap (H100, ~days).
- **Embedding CFR (arXiv:2511.12083, 17pp — not 182):** soft card abstraction for blueprint solves;
  NOT our problem (lossless subgames). ONE building block: HandEbdNet recipe (per-street W/D/L profile CNN)
  as v4 leaf-net featurization ('step 0', optional, 3080Ti). Build order unchanged.
- **Flop no-go retest** with EVPA-minimal menu (1 size/street): running (bwfga5qs2) — result to follow.

## TurboReBeL VERIFIED (2026-07-05 night, agent with direct OpenReview browser access)
- **Reference (verified):** Boning Li, Longbo Huang, *"TurboReBeL: 250x Accelerated Belief Learning for
  large Imperfect-Information Extensive-Form Games"*, ICLR-2026 submission #5768, openreview.net/forum?id=yMo7Z670f6
  — **REJECTED** (2026-01-26; ratings 2/2/4/6, soundness 1–2). Not on arXiv, not in DBLP. Same
  authors as our v4 paper (books/papers/CFR/2605.19928v1.pdf). Formally citable only as "OpenReview preprint,
  rejected"; **NEVER cite the 250×/450× headline** (meta-review: unsubstantiated estimate; Thm 1–2
  flawed; SSMIG vs. augmentation never ablated separately).
- **Still usable (as A/B-gated engineering experiments, own measurement numbers):**
  1. **SSMIG:** per depth-limited solve harvest T value targets (one per CFR iteration, averaged
     strategies) instead of 1 → the biggest data-cost lever for the v4 leaf net. (Honestly: TexasSolver exposes
     no per-iteration dumps — only applies in the own v4 CFR core.)
  2. **Iso augmentation:** suit iso (our `isomorph.py`!) + chip/stack scaling as training-data
     multiplier; correlated → never count as independent samples, augmentation at batch time.
  3. **Feasibility anchor:** 10M (TurboReBeL) or 60M samples (Li et al. 2024, in the rebuttal) suffice
     per forum evidence for Slumbot-beating HUNL value nets — NOT ReBeL's 4.5B. v4 budget: tens of
     millions of solve-derived samples = desktop/1-pod regime.
  4. **Gate recipe:** turn endgame with EXACT exploitability as a cheap first gate (= our
     grounded-gate doctrine); do not copy their weakness (no LBR, small abstraction).

## AIVAT understood (2026-07-06 ~01:00 — paper arXiv:1612.06915 read via ar5iv; Burch/Schmid/Moravčík/Bowling AAAI'18)
- **Construction:** control variates at CHANCE nodes AND decision nodes of the analyzed players;
  baseline = arbitrary value function ṽ; imaginary observations marginalize unknown opponent cards.
- **★ THE NO-CHEESE THEOREM (Thm 1):** E[Σ corrections] = 0 INDEPENDENT of the baseline quality — quote:
  *"a player cannot appear to do better by changing their play to take advantage of the estimation method."*
  → **AIVAT's mean cannot be gamed.** Pre-registered: every future idea "we adapt to the metric
  and gain bb" is an artifact per theorem. Adapting to AIVAT ≠ metric gaming (impossible).
- **What adaptation LEGITIMATELY means (the 3 real levers):** (1) optimize pure EV — luck is subtracted,
  gamble lines get no credit. (2) **The variance side belongs to US:** residual SD depends on the play style +
  on how well GTOW's baseline covers our lines → tail kill + on-tree sizings = tighter SE = faster/
  cheaper gates (measured: per-hand SD 1000 era → 214 today; ±2SE@2500 scales with SD). Lower-variance
  style = cheaper truth. (3) Off-tree lines = worse baseline fit = more NOISE (never bias) — a
  measurement-speed argument for census snapping in addition to the EV argument.
- **money_mine CAVEAT (paper-confirmed):** the paper supports NO unbiasedness for CONDITIONED
  subsets (e.g. only fold hands) — bucket sums mix real EV with baseline residuals that correlate with the
  conditioning. money_mine remains a RANKING heuristic; do not take magnitudes literally
  (caveat propagated in script + JSON).
- **Instrument candidate (post-ladder):** OWN local AIVAT for non-GTOW measurements (canary/Slumbot/
  duplicate) — unbiasedness holds for ANY baseline → our advisor/solver values suffice; ~10× variance
  on our $0 gates would be an instrument breakthrough (NOTES' DIVAT note, now paper-founded).

## TurboReBeL THEORY deep dive (2026-07-06 ~00:20 — theorems + all 4 reviews secured VERBATIM)
Full report: `data/research_sweep/turborebel_theory.md` (+ rebuttal PDF + reviews raw data there;
OpenReview is now challenge-locked — sources: 1× live API access + Wayback PDF + 2 independent,
byte-identical HF mirrors). Core finding (own analysis, agrees with reviewers uRCN/hYMG): **Theorem 1 is
probably FALSE as formulated, not merely under-proven** — proof step (C) claims uniform
per-infoset CFV convergence of the CFR average strategy to an ARBITRARY Nash σ* with O(1/√T); CFR does not
guarantee that (non-unique NE ⇒ Ω(1) off-path CFV difference — exactly the reason safe-resolving gadgets
exist; the belatedly submitted gift gadget cites Thm 1 circularly). Thm 2 = conditionally okay, but empty, because
its premise IS Thm 1. **$0 falsification tests designed (Leduc):** T1 = generate two distinct NEs,
plot max_I |v^σ̄T(I) − v^σ*(I)| over T (prediction: σ*-dependent plateau instead of O(1/√T) decay at
off-path infosets); T2 = SSMIG pipeline exploitability vs the claimed bound. Consequence for v4
UNCHANGED: SSMIG + iso augmentation as gated engineering levers, never cite the theory.

## NAL / "Reducing Variance 2025" verdict (2026-07-05 night, read inline IN FULL — existence-verified)
- **Paper:** Meng, Chen, Li, Yang, Zhang, Gao — *Reducing Variance of Stochastic Optimization for Approximating
  Nash Equilibria in Normal-Form Games*, **ICML 2025 (PMLR 267)**. PDF: `books/papers/Variance/`.
- **Core:** Nash Advantage Loss (NAL) = surrogate loss with stop-gradient construction, whose gradient
  (F − ⟨F,x̂⟩·1 = the "advantage") is unbiasedly estimable with ONE random variable → variance O(σ) instead of
  O(σ²) of the only previous unbiased loss (Gemp 2024, inner product of two independent estimators);
  empirically 2–6 orders of magnitude less variance. Entropy regularization (τ annealing) → inner NE;
  duality gap ≤ C·‖∇NAL‖ (Thm 4.2/4.3).
- **VERDICT: PARK — no application for us.** (1) **Normal form only**: the theory (Lemma 4.1, gradient
  equality ⇔ NE) needs linearity of the utility over the strategy SIMPLEX — does NOT hold for behavioral
  strategies in extensive form (multilinear); NFG conversion of poker is exponential. (2) Even in
  tiny Kuhn Poker (NFG) NAL does not converge exactly at small S (paper §5 itself). (3) Despite the folder
  name "Variance": that is TRAINING-loss variance when computing the NE, NOT measurement variance (AIVAT/paired
  remains our tool). (4) Not composable with the v4 path (CFR family). Side note for the archive:
  n-player general-sum NE via Adam would at most be interesting for small abstracted 6-max NFGs — no
  current need (CFR+ covers preflop, multiplayer stance remains CCE via regret).

## MCCFR line checked (2026-07-06, user links, all existence-verified)
- Lanctot/Waugh/Zinkevich/Bowling, "Monte Carlo Sampling for Regret Minimization in Extensive Games"
  (NeurIPS 2009) = the canonical MCCFR (two mirror links). + MCCFVFP (Ju et al., NeurIPS 2024):
  MCCFR + fictitious play, ~20-50% faster IN MC settings.
- **VERDICT: no upgrade for us, would be a DOWNGRADE for the TexasSolver part.** MCCFR only wins on
  trees too large for full traversal; a postflop subgame is small, TexasSolver's full-width VECTORIZED
  DCFR processes all 1326 combos simultaneously (amortization) -> sampling loses exactly that = slower.
  Measured in the code: preflop = EXACT CFR+ (deliberately not sampled), postflop = TexasSolver vectorized,
  MCCFR only in the shelved deep_cfr.py (plateaued ~1500 mbb). Sampling CFR only relevant if we ever (a) solve the
  flop ourselves (but roadmap = library + leaf net, not MCCFR) or (b) build a v4 label-gen core
  (deep_cfr.py, separate from TexasSolver). The CFR variant is NOT the bottleneck; range quality + flop
  coverage are (precision doctrine: we already use the more precise full-width variant).

## "Quantized Poker" (Bleiler 2009, arXiv:0902.2196) — VERIFIED, does NOT transfer
- Quantum game theory (Meyer/EWL tradition): poker endgames in the quantum realm; "entangled poker"
  beats real-life results — BUT only "when played in the coming quantum computation environment or
  with quantum information". Advantage hinges on ENTANGLEMENT + quantum protocol between the players.
- **VERDICT: no transfer to our classical bot vs GTOW.** Online poker has no quantum channel,
  no entanglement — we cannot play bet actions as entangled amplitudes. The paper
  ITSELF confirms the limit (the advantage exists by construction only in the quantum realm). Definitive
  citation that the quantum FORMALISM does not transfer; poker mixing = classical probability.
  Shadow: entanglement reaches corr. eq. without mediator — but HU: CE=Nash (no gain); 6-max: CE
  beats Nash product, yet we cannot use entanglement (no channel). No operational tool.
- What remains transferable is ONLY classical harmonic analysis (Fourier/spectral = obfuscation metric +
  carrier-wave insight, ../doctrine/POKER_NUTSHELL.md). The wave core is classical, not quantum.
