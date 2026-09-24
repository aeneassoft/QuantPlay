# PAPERS_2026.md — triage of the five new 2026 papers (2026-08-16)

Folder: `books/papers/Poker Math 2026/`. None was in the repo before (RESEARCH_SWEEP knows only
2605.19928 = Li&Huang CFR, a different paper). Existence of all five verified locally (PyMuPDF).

## ★★★ Brown — *Value, Bluff, and Cyclic Dominance* (SSRN 6709840, 36 pp.)
Solves the von Neumann betting game for the first time on the REAL 169x169 equity matrix of HU-THE, over
all bet sizes, dropping all three VNM simplifications simultaneously. Findings:
- **106/169 hands behave classically** (value follows raw equity; pivot order Spearman 0.98).
- **Zero hands are pure bluffs in all four model variants** — the bluff SELECTION is structural
  (blockers/non-determinism/sizing), not determined by a frequency.
- Cyclic dominance (RPS structure) as the frame — the theoretical version of our seesaw doctrine.
**Direct use:** (1) a new range-free F/L check: value-bet ordering vs raw equity;
(2) the 169x169 matrix as a reference object for preflop checks; (3) THEORY CONFIRMATION of
today's gate result: mdf_guard (frequency without selection) −3.26, sel_guard (selection) +13.8
sanity — Brown says structurally the same: bluff/continue is selection, not a quota.

## ★★★ SPIRAL — Self-Play on Zero-Sum Games (ICLR 2026, 28 pp.)
LLM self-play on zero-sum games (among them Kuhn poker) against self-improving copies =
auto-curriculum without human labels; **role-conditioned advantage estimation (RAE)**
stabilizes multi-agent LLM RL; beats SFT on 25k expert trajectories, +10% transfer on
8 reasoning benchmarks (Qwen+Llama). **Direct use:** the answer to our open
RL question (GLM-GRPO regression: the league reward was wrong) — self-play curriculum + RAE is the
candidate for the 'better reward' STATE.md demands. Deep-read before every new RL run.

## ★★ Diniz — *Learning Strategic Poker Decision-Making with LLMs* (master's thesis UFU, 91 pp.; scanned 2026-08-16)
**What was built/measured:** pure SUPERVISED PREDICTION on **PokerBench** (YES, used directly:
~63k preflop / ~500k postflop train, 1k/10k eval, original splits, 100bb fixed stacks; labels = GTO Wizard
preflop + WASM-Postflop postflop). 6 open LLMs compared few-shot (best: **Qwen3-14B**, preflop
76.1% / postflop 51.5% action acc), then Qwen3-14B SFT-adapted per stage via LoRA/QLoRA →
**93.3% preflop / 91.8% postflop** (McNemar p<0.001, OR 5.9/14.9). No play, no EV, no
exploitability, no whole hands — only label agreement at isolated states (the thesis says
so itself explicitly). Publications: ENIAC 2025, BRACIS 2026, "PokerLLM" (submitted to IEEE ToG).
**Methodology core (the actually usable part):** (1) **hybrid pipeline** — action via next-token
LOG-PROB SCORING over the LEGAL actions (deterministic, no parsing error counted as a policy error),
sizing separately via greedy generation + numeric parser; (2) **Ac-s metric** — continuous
action-and-sizing accuracy: a correct aggressive action receives proportional sizing credit
(scale- and direction-symmetric), plus a conditional sizing score ONLY after a correct action
(measured: 0.994/0.992 — i.e. the residual error is ACTION choice, not sizing calibration).
**What falls out for our dataset format:** (a) confirms our format_spot/PokerBench alignment;
(b) the logprob-over-legal-actions evaluator + Ac-s can be adopted directly into `training/qwen_eval.py`
(cleaner token acc than exact string matching); (c) ablations: persona almost irrelevant,
prompt STRUCTURE and logprob scoring carry; preflop sizing is temperature-sensitive → greedy.
**Honestly:** confirms our imitation-ceiling doctrine — 93% label agreement without a single
measured bb. No blocker, no new lever for the autogym path.

## ★ SCORE Method (SSRN 6297138, 12 pp.; read completely 2026-08-16)
**The heuristic as a formula:** `SCORE = outs × (Pot/Call)`; call iff SCORE > 50 (turn) or > 25 (flop).
Algebraically exactly equivalent to the pot-odds inequality n/N ≥ C/(P+C) rearranged to
`n·P/C ≥ N−n` — so the EXACT turn threshold is **46−n** (varies with the outs); the fixed 50
is ALWAYS above it. **Conservative bias quantified:** additional requirement on pot/call =
`Δ = 50/n − (46−n)/n = 1 + 4/n` (n=4: +2.0 pot/call ≈ +1.7pp equity; n=9: ≈ +0.95pp; n=15: ≈ +0.46pp);
weighted ≈ **+1pp**, largest protection at few outs. Simulation 10^7 spots: 97.1/97.5% concordance,
**zero false calls** (deviation only in the fold direction), rejected calls on average +$0.43 EV (rake
eats that). **Fits as an oracle KNOB? YES, narrowly bounded:** as a documented ONE-SIDED approximation
check at stage L/F ("SCORE fold ⟹ exact fold OR marginal call ≤ Δ band") — the bound
`46−n ≤ SCORE < 50` is exactly checkable as a Fraction. NEVER as a HART reference (no Fraction substitute,
deliberately biased). **Honest limit of the flop 25:** the derivation assumes TWO cards for ONE
call price (exactly ≈ 23−n/2) — conservative only relative to this implied-odds-friendly model;
against the single-street computation (rule of 2) 25 is LIBERAL. For the bot, exact computation remains mandatory;
main use = COACHING track (a human-usable 3-operation rule with a known ±1pp bias).

## ○ 2605.22972 — *Balancing relational generalization and memorization* (Columbia, 39 pp.)
NOT a poker paper (theoretical neuroscience/ML). Tangentially relevant to the
generalization-vs-memorization question of the v4 value nets; probably misfiled in the poker
folder. Honestly: low priority.

**Recommended order:** Brown deep-read + check extraction (next benchmark wave) →
SPIRAL deep-read before the next RL run → Diniz scan → SCORE during coach work.
