# Qwen 6-max Poker-Brain — Training Pipeline (synthesis of gpt-5.5 + Opus 4.8 consults, 2026-06-17)

> Source consults (full detail): [`docs/qwen_train_gpt55.md`](qwen_train_gpt55.md) (conceptual + RL) ·
> [`docs/qwen_train_claude.md`](qwen_train_claude.md) (technical). They CONVERGED strongly — high confidence in the spine.

## The spine (both models agree, verbatim-level)
**Stages 1–3 (SFT / distillation / preference) are WARM-START. The ONLY thing that lifts above the teacher is Stage 4
(RL / self-play with realized-EV reward).** This IS our hard-learned lesson (imitation caps: fcpa −212, floor −72),
now stated as a recipe. Corollary: frontier LLMs are only −10..−30 bb/100 vs GTOW (HU) → **distilling them blindly
imports their mistakes** → every distilled example must be GATED against EV ground-truth (the engine), used as a
*prior, not an oracle*.

## Architecture — the staged pipeline
- **Stage 0 — Lock the foundation (do FIRST):** a frozen 6-max eval suite (PokerBench held-out + a private spot set +
  an arena panel with fixed seeds + an LBR proxy) + a CONSTRAINED action schema + a CANONICAL spot serializer
  (`format_spot.py`, byte-identical across SFT / RL / live inference — any drift = silent train/serve skew).
- **Stage 1 — SFT warm-start (QLoRA):** PokerBench (spine, ~45%, but CAP its weight = the −72 imitation trap in
  disguise) + ranges→spot examples + postflop solver-frequencies (soft labels) + exploit-conditional examples
  (**weight UP — our differentiator vs solver bots**) + math→verified-CoT + a little hand-history analysis. `train_on_inputs=false`.
  (DAPT-lite on theory is OPTIONAL/small — too much theory → a poker *commentator*, not a player.)
- **Stage 2 — Preference / DPO (EV-ranked, not chat-preference):** solver/rollout/gated-frontier action comparisons;
  keep an SFT anchor + KL; do NOT harden close mixed spots into pure actions (poker is mixed).
- **Stage 3 — RL = GRPO / expert-iteration self-play (THE LIFT):** group-relative (no reward model — the engine IS the
  reward), G=8 generations **from the SAME state** (the variance-reduction baseline), reward = realized bb with
  **AIVAT / all-in-EV variance reduction** + a hard legality/format gate + a **decaying** solver-match shaping (decay
  to 0 or you rebuild the imitation ceiling). High initial KL (0.04–0.1), RL lr ~1e-6, `dr_grpo` (no length bias).

## Model + stack (Opus, technical)
- **Qwen3-8B** (14B max for single-GPU RL), **QLoRA** (r=32, all linears) for both SFT + RL, **single H100 80GB**.
- **TRL**: `SFTTrainer` → `GRPOTrainer` with `use_vllm=True` (verl only if scaling to 4+ GPUs = not yet).
- RL policy init = the SFT LoRA; KL measured vs the SFT checkpoint (not base Qwen).

## Data prep — root-folder → trainable JSONL (the canonical spot format is locked in Stage 0)
| Source | → training form | weight | note |
|---|---|---|---|
| PokerBench (560k, 6-max) | spot→action (+short CoT) | ~45% | spine; CAP weight |
| `knowledge_base/ranges` | spot→mixed-strategy / freq | ~15% | high-precision preflop grounding |
| `knowledge_base/postflop` | state→action **distribution** (soft) | ~15% | don't force pure when solver mixes |
| `knowledge_base/exploit` (11.5k) | (opponent-tendency tag)→adjusted action + **anti-overexploit pairs** | ~15% | **our edge**; always condition on stat/sample/position |
| `knowledge_base/math` (+formulas.py) | verified pot-odds/MDF/EV CoT tasks (auto-checked) | ~5% | low-leakage, high-quality |
| `hand_histories` (10k Pluribus) | masked-future decision analysis | ~5% | NOT "winner imitation"; better as eval + self-play opponents |
| `concepts` / `theory` / PDFs | **distillation SEEDS, NOT raw SFT** | — | raw prose teaches *talking* about poker; use to prompt frontier spot-gen |

**Mandatory:** canonical dedup (suit/position/stack-normalized spot-key) + **DECONTAMINATE vs the PokerBench test set**
(drop any train spot whose key collides; log the count) + split by spot-key (val never shares a key) + mask future cards/results.

## Frontier-APIs-in-the-loop (topology — Opus was decisive)
**The Hetzner box IS the distillation orchestrator** (its actual job: long-running, network-bound, cheap-CPU). The
**pod stays 100% GPU-bound** — it must NEVER block on an OpenAI 429 while burning H100 $/hr.
```
Hetzner: async workers (httpx) → o3/Opus(+cheaper tier for bulk) → quality-gate → Redis dedup-cache → S3 shards
RunPod H100: polls S3 for shards (OFFLINE buffer, ~90%); consumes like any dataset
```
- **What the frontier produces:** (A) short rationales for KNOWN-good labels, (B) critiques of Qwen outputs → DPO
  pairs, (C) candidate actions for novel/self-play spots (→ rollout-EV evaluated, not trusted), (D) hard negatives.
- **Quality gates (the whole game):** parse-ok → legal → **EV cross-check vs solver/engine (reject if frontier EV ≪
  solver EV)** → agreement bonus (o3 & Opus agree AND matches solver). Use the CHEAPER tier for bulk, reserve o3/Opus
  for hard spots + critiques. Cache by spot-key (90% of cost waste is regeneration).
- **Active distillation done sanely:** during RL, log high-uncertainty / big-loss spots → BATCHED, off-critical-path
  critique → fold back as a periodic re-SFT/preference pass. NOT online-blocking (overkill + throughput killer).
- **Cost reality:** frontier distillation is the **#1 cost line** ($3–10k if naive, > the GPU's $300–600). Cap + cache it.

## Self-play harness
Wrap `pokerbot/arena/sixmax.py` + the N-player table as `SixMaxRLEnv`: `state_to_prompt` (= `format_spot`),
`parse_action` + **legal-move masking** (illegal→format penalty early, snap-to-legal late), `reward` (engine EV,
AIVAT for all-ins). **Pre-generate a state buffer** (snapshot every hero decision over thousands of hands) so engine
sim is decoupled from GPU rollout; refresh every K steps. **Opponent panel = a LEAGUE** (frozen SFT + earlier RL
checkpoints + Pluribus-derived + heuristic TAG/LAG/station) — pure self-play collapses in multiplayer general-sum.

## Eval + gates
- **PokerBench-accuracy** (cheap dev proxy, every ckpt) + **bb/100 vs a diverse panel** (TARGET metric, AIVAT, select
  on THIS not accuracy — else re-cap at the imitation ceiling) + **LBR proxy** (milestone; catches gross leaks).
- **GATE 2 (the core thesis test): RL must beat its own SFT init by +5 bb/100 vs panel and rising.** If it can't, the
  "RL lifts above the teacher" thesis is failing → stop + debug (reward variance / KL / stale buffer). Also: legality
  ≥99%, positive vs EACH panel member, LBR not worse, CoT-trace audit (GRPO+poker can collapse to degenerate folds).

## The sequence (de-risk BEFORE the big spend) — both models' #1 advice
1. **Stage 0** (evals + action schema + canonical format + baselines). $0, days.
2. **Cheapest de-risk pilot (~1 week):** from the CURRENT Qwen LoRA → generate 10–20k 6-max states → 4 candidate
   actions each → 32–64 rollouts/candidate (AIVAT) → DPO/AWR LoRA (1 epoch, 60% rollout / 30% PokerBench anchor /
   10% exploit) → eval vs panel. **PASS = arena bb/100 +10–20 (or sig.) + PokerBench drop <2–3pp + LBR not worse.**
   If this rollout-EV loop does NOT move bb/100, the full DAPT+frontier+RL pipeline is premature — fix env/reward first.
3. **Only if pilot passes:** the full pipeline — bulk gated distillation (Hetzner→S3) + Stage-1 SFT + Stage-3 GRPO on
   the H100 as ONE self-killing run (data-prep → SFT → GATE 0 → RL → GATES 1-2 → full eval GATES 3-5 → pull → kill).

## Overkill flags (don't): online-interleaved distillation · a learned reward model (the engine IS truth) · 70B/full-FT ·
verl/multi-GPU (yet) · raw-PDF DAPT · long-CoT distillation as default · frontier-as-reward/authority.
