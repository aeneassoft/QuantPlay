# EXECUTION PLAN — agreed 2026-06-14 (work top-to-bottom, 1:1)

**How we run this:** step by step. After each numbered step I report + commit, then wait for your go for the
next. **INTERRUPT CAVEAT:** when the big Slumbot run (`be7o77422`: exploit 5000 + baseline 3000) finishes,
we PAUSE whatever step we're on, read the numbers, decide if they change priorities, then resume.
Companion docs: [STATE.md](STATE.md) · [INTEGRATION.md](INTEGRATION.md) · gap audit memory `postflop-spec-unused`.

Backup before we start changing the bot: tag `slumbot-bot-2026-06-14` (pushed). Restore anytime via
`git checkout slumbot-bot-2026-06-14`.

---

## PHASE 1 — Wire the postflop playbook  (cheapest, highest-EV, NO training)
Source of truth: `knowledge_base/postflop/openai_strategy.json` (a full numeric spec the code never reads).
Targets: `pokerbot/strategy/postflop.py`, `bot.py`, `arena/sixmax.py`, `gto_baseline.py`. Measure each
batch with `gto_benchmark` (TV gap) and, when a Slumbot slot is free, a quick Slumbot re-bench.

**1.1 EV-correct value sizing** — replace `postflop.value_score()` with the exact
`EV_value(s)=F·P+(1−F)·(e_call·(P+2sP)−(1−e_call)·sP)` from the spec (current one drops F·P + pot geometry).
→ unit-test the size ranking; `python -m tests.test_bot` green. Commit.

**1.2 Texture-conditioned c-bet** — add `CBET_TABLE[board_class][pos] -> (freq,size)` (from the spec) keyed
off the existing `classify_board()`; call it in `bot._postflop` / `sixmax._decide` / `gto_baseline.decide`
instead of flat `cbet_eq/cbet_size`. Sanity vs our solver cache (~77% dry/high, ~58% wet/monotone, ~⅔ size).
Commit.

**1.3 MDF-driven defense** — make the computed MDF (currently only displayed) SET the continue-fraction,
shaded by the opponent's observed bluffiness (`OpponentModel.aggression_freq`). Commit.

**1.4 Activate the dormant fold model** — build a `LearnedFoldModel` from `pluribus_exploit*` (data exists)
and set it as the default `fold_model` for Pluribus-like spots; honor the under-fold "value-not-bluff" spots.
→ realizes the projected ~+4 bb/100. Commit.

**1.5 RE-BENCHMARK (checkpoint):** `gto_benchmark` gap before/after; quick Slumbot re-bench (≈500 hands) to
see movement. Decide whether to continue to the heavier items.

**1.6 Heavier postflop items** (do as separate, tested commits): turn-barreling branch (range/nut advantage +
turn-card type) [#2]; blocker-based bluff selection [#4]; SPR-aware sizing/commitment [#3]; equity-realization
function replacing the magic `0.82` [#8]; implied/reverse-implied odds + outs→equity & draw detection
[#9,#13]; hand-strength buckets vs scalar cutoffs [#12]; river bluff:value α-anchor [#7]; θ/β over-fold
exploit engine as the unifying primitive [#10].

**Phase 1 DONE when:** `gto_benchmark` TV gap clearly down from ~20%, tests green, and a Slumbot re-bench is
logged. Update STATE.md.

---

## PHASE 2 — Extract what the pod run taught us about PokerBench  (LLM parked otherwise)
Artifacts we already have: `models/qwen_poker_ckpt500/trainer_state.json` (full loss/grad/accuracy curve),
the eval result (base 18.3% → LoRA 71.7%), `extraction/qwen_sft.py` (`load_pokerbench`).

**2.1** Parse `trainer_state.json` → training dynamics (convergence speed, plateau point, final metrics).
**2.2** Document PokerBench structure: configs/splits, fields (instruction→output), the action/label format,
preflop-vs-postflop split, any stack-depth/line coverage (analyze a sample via `datasets`).
**2.3** Characterize content + LIMITS (generic GTO, format-specific, what spots it lacks).
**2.4** Write `docs/POKERBENCH_NOTES.md` (so we never re-learn it) + note how/whether it feeds the neural net.

**Phase 2 DONE when:** `docs/POKERBENCH_NOTES.md` committed; LLM track then parked until after the net.

---

## PHASE 3 — Inventory all datasets + rank by quality
**3.1** Inventory each with size / source / type (solver-truth? real-human? LLM-generated? bot self-play?):
- `data/_gto_bench_cache` (~1340 local solved flops, stack 100) + `data/_gto_cover_cache` (~143 broad, 3 stacks)
- `knowledge_base/hand_histories/` (10k Pluribus)
- RZ412/PokerBench (563k GTO decisions, HF)
- **PHH / pokerkit** (100s of millions real hands: HandHQ 21.6M NL, ACPC, WSOP — external, not yet downloaded)
- `knowledge_base/{concepts,ranges,math,exploit,theory}` (book-extracted) + the exploit playbook (11.5k+240)
**3.2** Rank by quality FOR OUR USES: floor/GTO training → solver cache (exact) > PokerBench (generic GTO);
opponent-modeling/exploit → real-human PHH > Pluribus 10k; reasoning/coaching → book concepts.
**3.3** Decide the training mix for Phase 4 (which data trains the floor net; which seeds exploitation).
**Phase 3 DONE when:** `docs/DATASETS.md` (inventory + quality ranking + "use X for the net") committed.

---

## PHASE 4 — Build out + optimize the NEURAL NET  ★ the point that makes us a real AI ★  (GPU pod + hours)
Goal: a strong, low-exploitability **GTO floor net**. Primary path = distillation-from-solver (compute-
efficient, we have the oracle); Deep-CFR self-play = optional complement.

**4.1** Lock the approach + net architecture (inputs/features, output = action+size buckets, size). Decide
distillation-primary; whether to also run Deep-CFR self-play on the pod.
**4.2 Coverage campaign (CPU):** broad, FAST solver config (flop+turn across stack depths + key lines;
cpu5c, possibly 2–3 pods in parallel — add multi-pod support to `runpod_run`). Build a big GTO training set
(the data Phase 3 says we need). Retrieve to `data/`.
**4.3** Extend `distill.build_dataset` to consume the broader nodes (turn/stack/3bet, stack-suffixed files)
and the richer features the gap audit flagged (SPR, board-class, blockers).
**4.4 Train floor-net v2 (GPU):** bigger net + richer features + broad data → target TV well below 17%;
measure with `eval_gap` (TV) and, ideally, the new **LBR** evaluator. Save `models/floor_net_v2.pt`.
**4.5 (optional)** Deep-CFR self-play on a GPU pod (`deep_cfr_nlhe.py`) to convergence as the alternative
"true" floor; compare exploitability. Always `--kill` the pod.
**Phase 4 DONE when:** a floor net with a measured low TV gap (+ LBR number) exists + is saved.

---

## PHASE 5 — Integrate the neural net correctly
**5.1** Build `pokerbot/strategy/cfr_policy.py`: load the floor net → `policy(state) -> action probs`; map the
bucketed output to concrete legal actions/sizes for the spot (legalize, never illegal).
**5.2** Wire it as the `base`/floor in `adaptive.py` (and `bot.py` path): net distribution = the GTO floor;
the exploit overlay (wired postflop spec + playbook + calibration + optional LLM) sits ON TOP, bounded/gated.
Decide blend (net where confident, analytic fallback elsewhere).
**5.3** Test: `test_bot` green, all decisions legal, floor active; a smoke vs the baselines.
**Phase 5 DONE when:** the bot plays on the neural floor; `cfr_policy` integrated + tested + committed.

---

## PHASE 6 — Run ALL benchmarks  (the open question: are we good at EXPLOITATIVE play?)
**6.1 vs Slumbot** (near-GTO) — large sample, with the new floor + wired spec (+ exploit on/off).
**6.2 vs the exploitable suite** — `beat_them_all.py` (station/nit/maniac + diverse foes): the direct
measure of **exploitative** strength.
**6.3 LBR exploitability** — `pokerbot/benchmark/lbr.py` on the new floor (is the floor robust?).
**6.4 gto_benchmark** — TV gap vs the solver.
**6.5 vs Pluribus** — `pluribus_bench.py` decision-alignment + the projected exploit.
**6.6** Compile a **scorecard** (bb/100 per opponent + exploitability + GTO-gap) → honest verdict on GTO
floor quality AND exploitative edge. Update STATE.md + the honest-status section.
**Phase 6 DONE when:** the scorecard is committed and we can state, with numbers, how good the bot is.

---

## Running rules
- One step → report → commit → wait for go. Small, tested commits (branch → ff-merge → push).
- Always `--kill` pods; keep one CPU/GPU job per box (CPU+GPU don't coexist — see `pod-run-validation`).
- Never commit secrets / models (`*.safetensors`, `models/` are gitignored).
- **If the Slumbot run finishes mid-step:** pause, analyze, decide if it re-orders priorities (bad baseline →
  rush Phase 4 floor; good baseline → emphasize Phase 6 exploitation), then resume.
