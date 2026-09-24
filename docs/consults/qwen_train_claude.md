# Qwen 6-max training pipeline — technical (claude-opus-4-8)

# 6-MAX QWEN POKER BOT — BUILD SPEC

Ground rule up front: your hard-learned lesson is the spine of this whole design. **Everything in stages 1–3 is warm-start. The only thing that lifts you above the teacher is stage 4 (RL/self-play with realized-EV reward).** I'll flag overkill aggressively.

---

## 1. TRAINING STACK

### Model size + GPU

You already have a working Qwen3-class LoRA at 71.7% on a single pod. Don't get greedy.

- **Qwen3-8B** (or Qwen3-14B if you want headroom) is the sweet spot. **14B is the most you should run RL on a single GPU.**
- **GPU: single H100 80GB** (RunPod ~$2-3/hr) for 8B-14B. An **A100 80GB** works but RL throughput hurts. **Do not** try this on a 48GB card (A6000/L40S) for RL — you need room for policy + ref model + vLLM rollout cache + optimizer states. QLoRA can squeeze 14B onto 48GB for *SFT only*, but RL rollouts will OOM you constantly.

**Recommendation: Qwen3-8B, H100 80GB, QLoRA for both stages.** Cheaper, faster iteration, and at 8B your bottleneck is *data quality and reward signal*, not parameter count. Poker decision policy is not a 70B-scale reasoning problem.

### LoRA/QLoRA vs full FT

- **QLoRA (4-bit NF4 base + LoRA adapters)** for SFT and RL. Full FT of even 8B on one GPU with a ref model in memory is painful and buys you little here. Your task is narrow-domain adaptation, exactly what LoRA is for.
- LoRA config that actually works for reasoning tasks (not the toy `r=8`):
```yaml
lora_r: 32
lora_alpha: 64
lora_dropout: 0.05
target_modules: [q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj]  # ALL linears
modules_to_save: []   # keep embeddings frozen; Qwen tokenizer already has what you need
bias: none
```
- For RL you **reuse the SFT LoRA as the policy init AND the frozen reference**. The KL is measured against the SFT checkpoint, not base Qwen.

### Stages + libraries

```
Stage 0: data prep            (your code + dedup/decontam — section 2)
Stage 1: SFT  (warm start)    TRL SFTTrainer + PEFT + bitsandbytes
Stage 2: RL  (lift)           TRL GRPOTrainer + vLLM rollout backend
                              (or verl if you want more throughput control)
```

**Use TRL.** You already have a TRL/Axolotl-shaped workflow implied. For a single GPU, TRL's `GRPOTrainer` with `use_vllm=True` is the cleanest. `verl` is better at multi-GPU rollout/training disaggregation — overkill on one H100. Stick with TRL unless you scale to 4+ GPUs.

### SFT config

```yaml
# Axolotl or TRL SFTTrainer
sequence_len: 4096          # poker CoT spots fit; 8192 only if you keep long histories
sample_packing: true
pad_to_sequence_len: true
micro_batch_size: 4
gradient_accumulation_steps: 8   # eff batch 32
num_epochs: 2                    # 2-3 max; PokerBench overfits fast (your step-500 plateau)
learning_rate: 1.0e-4            # LoRA can take higher lr than full FT
lr_scheduler: cosine
warmup_ratio: 0.03
optimizer: adamw_bnb_8bit
weight_decay: 0.0
bf16: true
flash_attention: true
train_on_inputs: false           # MASK the prompt; only train on the response/CoT+action
```
**Critical: `train_on_inputs: false`.** You only compute loss on the assistant turn (reasoning + final action). Training on the prompt teaches it to generate poker spots — useless and dilutes signal.

### RL algorithm: GRPO

GRPO is right here because **you have no good reward model and you don't want to train one** — your reward comes from the *engine* (realized EV/win-rate), which is a clean programmatic signal. GRPO's group-relative advantage removes the need for a value head, and it loves verifiable/programmatic rewards.

```yaml
# TRL GRPOConfig
algorithm: GRPO
num_generations: 8            # group size G. 8 is the floor; 16 if throughput allows
                              # (8 samples per prompt, advantage = normalize within group)
beta: 0.04                    # KL coef vs SFT ref. START HIGH (0.04-0.1).
                              # Poker reward is noisy; high KL prevents reward-hacking collapse.
learning_rate: 1.0e-6         # RL lr is 100x lower than SFT. Non-negotiable.
temperature: 1.0              # need exploration in rollouts
top_p: 1.0
max_prompt_length: 2048
max_completion_length: 1024   # cap CoT; long rambles = wasted compute
per_device_train_batch_size: 8
gradient_accumulation_steps: 4
num_iterations: 1             # mu=1, standard GRPO
use_vllm: true
vllm_gpu_memory_utilization: 0.35   # leave room for the trainer on same GPU
loss_type: dr_grpo            # Dr.GRPO removes length bias — IMPORTANT, poker doesn't reward verbosity
scale_rewards: false          # with dr_grpo
```

### The reward — this is where you win or lose

**Rule-based / engine-based reward, NOT a reward model.** Three components, composed:

1. **Legality + format gate (hard).** If the model emits an illegal/unparseable action → reward = large negative (e.g. -1.0) and skip the EV calc. This must dominate early or RL degenerates into malformed output.
2. **Realized EV reward (the real signal).** For each decision in self-play, the reward is the **per-hand bb/100 outcome**, but raw hand outcomes are *brutally high-variance* (you fold and the hand ends; you stack off and lose to a 2-outer). Two fixes:
   - **All-in EV adjustment / AIVAT-style variance reduction** when the hand goes to showdown all-in — use the engine's equity calc, not the realized board. Cuts variance massively.
   - **Group baseline does the rest** — GRPO normalizes within the group of 8 generations *for the same spot*, which is exactly the variance-reduction structure you want. Make sure your group is 8 rollouts **from the same game state** so the baseline is meaningful.
3. **Optional shaping (small, decaying):** tiny bonus for matching solver action on PokerBench-style spots, coefficient → 0 over training. This keeps it tethered early. **Decay it to zero** or you've just rebuilt the imitation ceiling that capped your HU net at -72.

Don't build a reward model. You have an EV ground truth (the engine). A learned RM would only inject error and reward-hacking surface.

---

## 2. DATA PIPELINE

### Canonical poker-spot prompt format (LOCK THIS NOW)

This must be **byte-identical** between SFT, RL rollouts, and live inference. Define it once in `format_spot.py` and import everywhere. Any drift = silent eval/train/serve skew.

```
<|im_start|>system
You are a 6-max No-Limit Hold'em decision engine. Reason step by step, then output a single action.
Output your final action on the last line as: ACTION: <fold|check|call|raise X|all-in>
where X is the total bet size in big blinds.
<|im_end|>
<|im_start|>user
Game: 6-max NLHE, 100bb effective
Hero: BTN  |  Hole: As Kd
Stacks (bb): UTG 100, HJ 98, CO 100, BTN(hero) 102, SB 100, BB 100
Blinds: SB 0.5, BB 1.0
Preflop: UTG fold, HJ raise 2.5, CO fold
Flop (pot 6.0): Th 7c 2d  | HJ check
Turn: -
River: -
Hero to act on flop.
<|im_end|>
<|im_start|>assistant
```

Assistant target (SFT):
```
HJ opened from HJ and checked the flop on a dry Th7c2d board. ...
[3–8 lines of CoT: range vs range, equity, board texture, exploit note]
ACTION: raise 4
<|im_end|>
```

**Parser regex (used everywhere):** `ACTION:\s*(fold|check|call|all-in|raise\s+[\d.]+)`. If it doesn't match → format penalty.

### Transforming your knowledge_base into JSONL

Each KB source maps to a different example *type*. Tag every example with `source` and `type` so you can ablate and reweight.

**(a) PokerBench (560k) — the spine of SFT.** Already instruction→action. Wrap into the canonical format above. The PokerBench prompts already encode position/board/history — normalize them into your template. **This is your largest bucket but cap its weight** so the model doesn't become a pure solver-imitator (that's your -72 plateau in disguise).

**(b) `knowledge_base/ranges` (preflop blueprints/tables) → spot examples.** Expand each range cell into concrete preflop decision examples: sample a hand from the range, build the prompt, target = the table's action+frequency. Generate a few hundred k of these — cheap, high-precision, grounds preflop.

**(c) `knowledge_base/postflop` (solver frequencies) → spot examples** same as (b) but for flop/turn/river nodes. These + PokerBench are your "GTO baseline" knowledge.

**(d) `knowledge_base/math` (math.json + formulas.py) → tool/reasoning examples.** Two uses:
   - SFT examples teaching the CoT to *do the math* (pot odds, equity needed, SPR) — "pot is 6, call is 4, you need 40% equity..."
   - **Better: expose formulas.py as a tool at inference.** But that complicates RL. For v1, bake the math into CoT examples. Don't build tool-calling yet — overkill.

**(e) `knowledge_base/concepts` + `theory` (books, CFR/GTO papers) → distillation seeds, NOT raw SFT.** Raw book prose is bad SFT data (it's not in spot→action form). Use these as **context for frontier distillation** (section 3): "here's the concept, generate 50 spot examples illustrating it." Don't dump prose into the training set — it teaches the model to talk about poker, not play it.

**(f) `knowledge_base/exploit` (11.5k directives/playbooks) → conditional examples.** Build prompts that include an opponent-tendency tag (`Villain stat: 3bets 12%, folds to cbet 65%`) and target the exploit-adjusted action. **This is your differentiator vs solver bots** — the population-exploitation angle. Generate spot examples where the optimal action *deviates from GTO* given reads.

**(g) `hand_histories` (10k Pluribus + pros) → trajectory examples + RL eval.** Convert each decision point into a spot→action example (Pluribus actions are decent but not gospel — tag them, low weight in SFT). **More valuable: use these as a fixed eval set and as opponent models in self-play.**

### Dedup + decontamination (do not skip)

```python
# Dedup: MinHash LSH on the prompt's structural key
key = (hole_cards_canonical, board_canonical, position, action_history_canonical)
# Exact-key dedup first, then near-dup via datasketch MinHashLSH on the full prompt text (threshold 0.85)
```

**Decontamination vs PokerBench test set — MANDATORY** (your eval depends on it):
```python
# 1. Hash the canonical spot-key of every PokerBench TEST example -> set
# 2. Remove from your TRAIN pool any example whose spot-key collides
# 3. Also fuzzy-check: same hole+board+positions = contamination even if history differs slightly
```
Log how many you drop. If you drop a lot, your generated data is leaking the test distribution.

### Split + mix weights (starting point)

```
train/val: 98/2 random by spot-key (val NEVER shares a spot-key with train)
SFT mix (by example count, post-dedup):
  PokerBench           45%
  ranges (preflop)     15%
  postflop freqs       15%
  exploit conditional  15%   <- weight UP; this is your edge
  math CoT              5%
  hand-history spots    5%
```

---

## 3. FRONTIER-API-IN-THE-LOOP

### Topology decision: **separate orchestrator, NOT the pod calling APIs directly.**

The pod should be 100% GPU-bound. Mixing async HTTP/rate-limit/retry logic into the training process is how you get a stalled H100 burning $3/hr while waiting on an OpenAI 429. Decouple.

```
┌─────────────────────────────────────────────────────────────┐
│  Hetzner box (USE IT HERE — this is its actual job)          │
│                                                               │
│  Distillation orchestrator:                                   │
│   - N async workers (asyncio + httpx) calling                 │
│     OpenAI (o3/GPT-5.x) + Claude (Opus) concurrently          │
│   - Spot generator: samples states from engine / KB concepts  │
│   - Redis: dedup cache (spot-key -> response) + work queue    │
│   - Quality gate -> writes accepted JSONL to object storage   │
│     (S3/R2) in shards                                          │
└─────────────────────────────────────────────────────────────┘
                          │  shards land in S3/R2
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  RunPod H100 pod                                              │
│   - Training loop polls S3 for new shards each epoch          │
│   - Offline buffer (mostly) + optional online refresh         │
└─────────────────────────────────────────────────────────────┘
```

**Yes, use the Hetzner box.** This is exactly the workload it's good for: long-running, network-bound, cheap-CPU. Don't pay H100 rates to wait on API latency.

### Offline buffer vs online interleave

**Offline buffer for 90% of it.** Generate the distillation corpus *before* and *between* training stages, write to S3, pod consumes it like any other dataset. Online interleaving (pod blocks on fresh frontier critiques mid-step) sounds cool and is **overkill + a throughput killer**. 

The ONE place online-ish distillation earns its keep: **RL critique on hard spots**. During RL, log spots where the policy is high-uncertainty or loses big. Periodically (async, batched, off the critical path) send those to Opus/o3 for a critique, and fold the critiques back as *new SFT examples in a periodic re-SFT pass* or as preference pairs. This is "active distillation" done sanely — batched and offline, not blocking.

### Generation recipe (quality gates are the whole game)

For each spot:
1. Query **both** o3 and Opus (and your own current checkpoint).
2. Each returns CoT + `ACTION:`.
3. **Quality gates:**
   - Parse must succeed.
   - Action must be **legal** in the engine.
   - **Cross-check against solver/EV where you have it** (ranges/postflop KB). If frontier action's EV is much worse than solver action → **reject or label as negative**. *This is how you avoid importing the frontier's -10 to -30 bb/100 mistakes.*
   - Agreement bonus: if o3 and Opus agree AND it matches solver → high-confidence positive.
4. Dedup by spot-key against existing buffer (Redis).
5. Write accepted → S3 shard with `source: distill, teacher: {o3|opus}, confidence: {hi|lo}`.

**Never blindly trust the frontier.** Gate every example against your EV ground truth. Frontier models are a *prior*, the engine is *truth*.

### Cost model (rough, brutal honesty)

```
Target distill corpus: ~150k accepted examples
Acceptance rate after gates: ~50% -> ~300k API calls
2 teachers -> ~600k calls
Avg ~1.5k input + 800 output tokens (CoT)

o3-class: very expensive. Budget assuming ~$10-15 / 1M output tokens, more for reasoning tokens.
  600k calls * ~2.3k tok ≈ 1.4B tokens. At reasoning-model prices this is THOUSANDS of dollars
  ($3k–10k range) and is your single biggest cost line — bigger than the GPU.
```
**Mitigation:** Use the cheaper frontier tier (GPT-5-mini / Claude Sonnet) for *bulk* generation, reserve o3/Opus for *hard spots and critiques only*. Cache aggressively (Redis spot-key). **Don't regenerate spots you already have.** This is where 90% of cost waste happens.

H100 cost by comparison: a full SFT+RL run is maybe 100-200 GPU-hours = $300-600. **The frontier API is your dominant cost. Budget it explicitly and cap it.**

---

## 4. SELF-PLAY HARNESS

### Wiring `sixmax.py` as the RL environment

GRPO needs: given a state, produce G completions, score each. Your engine produces states and scores actions. Bridge:

```python
class SixMaxRLEnv:
    """Wraps pokerbot/arena/sixmax.py for GRPO rollouts."""

    def sample_states(self, n) -> list[GameState]:
        # Run hands; at each hero decision point, snapshot the state.
        # Pull from a buffer of mid-hand states across many seats/streets.
        # IMPORTANT: balance position/street so RL doesn't over-train preflop BTN.

    def state_to_prompt(self, gs) -> str:
        return format_spot(gs)   # SAME function as SFT/inference

    def parse_action(self, completion, gs) -> Action | None:
        m = ACTION_RE.search(completion)
        if not m: return None
        return self.legalize(parse(m), gs)   # see masking

    def legalize(self, action, gs) -> Action | None:
        # Legal-move mask: fold only if facing bet; check only if no bet;
        # clamp raise to [min_raise, stack]; map "all-in" correctly.
        # If action is illegal-but-parseable, you have a choice:
        #   (a) return None -> format penalty (teaches legality), OR
        #   (b) snap to nearest legal -> softer. USE (a) early, (b) late.

    def reward(self, gs, action) -> float:
        if action is None: return -1.0
        # Roll the hand forward. For all-in spots use equity (AIVAT-style),
        # not the dealt river, to kill variance.
        return ev_bb(gs, action)   # in bb, then GRPO group-normalizes
```

### Batching parallel tables for throughput

This is your throughput bottleneck — the engine, not the GPU, if you're naive.

- **Pre-generate a large pool of decision states offline** (run thousands of hands with the current/opponent policies, snapshot every hero decision). Store as a state buffer. RL then samples prompts from this buffer — **decouples engine sim from GPU rollout**.
- For the GRPO group: **G=8 completions for the SAME state**, score each by rolling that one state forward 8 ways. vLLM batches the 8 generations trivially.
- Refresh the state buffer every K RL steps using the *current* policy (so you don't train forever against stale states). This is roughly a replay-buffer pattern.

### Opponent panel (who fills the other 5 seats)

Mix, don't self-play-only:
- **Frozen SFT checkpoint** (anchor).
- **Earlier RL checkpoints** (self-play league — prevents cycling/forgetting; this is the Pluribus-style robustness move that matters in multiplayer general-sum where there's no Nash to converge to).
- **Pluribus hand-history-derived policy** + **a couple of heuristic bots** (TAG, LAG, calling-station) — these give the exploit signal your exploit-KB is meant to capture.
- Optionally **other LLMs** via API as opponents (expensive, use sparingly in eval not training).

**Why a league + heuristic mix:** in 6-max general-sum, pure self-play can converge to a weird equilibrium that's exploitable by the field. A diverse panel keeps the policy robust and is what actually correlates with bb/100 vs real opponents.

---

## 5. EVAL + GATES + ORCHESTRATION

### Eval harness (three tiers, increasing cost)

1. **PokerBench decision-accuracy** (cheap, every checkpoint): held-out, decontaminated. Your dev metric, paper-validated to correlate with win-rate. Run on every checkpoint. **This is a proxy — never your go/no-go alone.**
2. **bb/100 vs opponent panel** (medium, every N checkpoints): play 50k+ hands vs the frozen panel in `sixmax.py`. **Use AIVAT/all-in-EV variance reduction** or you'll need 500k hands to see signal. This is your **target metric**.
3. **Bounded exploitability (LBR-style)** (expensive, milestone only): run a Local Best Response — an adversary that, at each node, picks the action maximizing immediate EV against your fixed policy. Gives an *upper-bounded exploitability* number. In 6-max this isn't true exploitability (no Nash), but LBR catches gross leaks (e.g. "never folds to river raise"). Run at major milestones, not every step.

### Checkpoint selection

Select on **bb/100 vs panel**, not PokerBench accuracy. Your whole thesis is that accuracy caps and RL lifts EV above it. If you select on accuracy you'll re-cap yourself at the imitation ceiling. Keep PokerBench as a sanity floor (if it craters, something broke).

### Go/No-Go gates

```
GATE 0 (SFT sanity):     PokerBench held-out acc >= 70% (you're already here at 71.7%).
                         If RL doesn't START from >=70%, fix SFT first.
GATE 1 (RL not broken):  format-legality rate >= 99% after 200 RL steps.
                         If illegal-action rate climbs -> reward/KL misconfigured, STOP.
GATE 2 (RL lifting):     bb/100 vs frozen-SFT panel > +5 bb/100 and rising.
                         THIS IS THE CORE GATE. If RL can't beat its own SFT init,
                         the whole "RL lifts above teacher" thesis is failing — stop and debug
                         (reward variance? KL too high? state buffer stale?).
GATE 3 (robustness):     positive bb/100 vs EACH panel member (not just average).
                         Negative vs one bot = exploitable hole.
GATE 4 (no leak):        LBR exploitability not catastrophically worse than SFT init.
GATE 5 (no reward hack): manual read of 50 CoT traces — reasoning still coherent,
                         not degenerated into action-spamming. (GRPO+poker reward CAN
                         find degenerate folds-everything local optima — watch for it.)
```

### The one self-killing RunPod run

```
RunPod pod entrypoint (orchestrated, self-killing):

  [0] pull decontaminated SFT JSONL + distill shards from S3
      (distillation already generated by Hetzner orchestrator — runs ASYNC, ahead of pod)
  [1] SFT (TRL SFTTrainer, QLoRA)         ~30-60 GPU-hr
      -> eval GATE 0; if fail -> push logs, SELF-KILL
  [2] build state buffer from engine (warm policy = SFT ckpt)
  [3] RL (TRL GRPO + vLLM)                ~60-120 GPU-hr
      -> periodic eval GATES 1,2 every N steps
      -> refresh state buffer + league opponents every K steps
      -> if GATE 1 fails -> SELF-KILL (broken run, save money)
  [4] full eval: PokerBench + bb/100 panel + LBR -> GATES 3,4,5
  [5] select best ckpt by bb/100, push adapter + eval report + traces to S3
  [6] SELF-KILL
```

**Async distillation feeds the pod, not the other way around.** The Hetzner orchestrator runs continuously, building the S3 buffer. The pod is a clean, self-terminating GPU job that consumes a snapshot. This keeps the expensive H100 from ever idling on API I/O, and lets you re-run training cheaply against an accumulating distill corpus.

---

## Honest risk callouts

- **Biggest risk isn't the stack — it's reward variance + reward hacking in stage 4.** Poker RL collapses easily. Mitigations: AIVAT, GRPO group-from-same-state, high initial KL, decaying solver-match shaping, GATE 5 trace audits.
- **6-max has no ground truth.** bb/100-vs-panel is only as good as your panel. A narrow panel = a bot that beats your panel and loses to the world. Invest in panel diversity (heuristic + league + Pluribus-derived).
- **Frontier distillation is your #1 cost and #1 way to re-import the -10/-30 ceiling.** Gate every distilled example against EV truth. It's a prior, not an oracle.
- **Overkill flags:** online interleaved distillation (don't), reward model (don't — you have an engine), 70B model (don't), full FT (don't), verl/multi-GPU (not yet), Hetzner-as-anything-but-the-distill-orchestrator (don't).

Start: Qwen3-8B, QLoRA, TRL SFT→GRPO on one H100, Hetzner running gated bulk distillation into S3, RL reward = engine EV with AIVAT. Prove GATE 2 (RL beats its own SFT init) before scaling anything.
