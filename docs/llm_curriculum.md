# LLM Curriculum — Qwen3-8B program-of-thought poker brain

A curriculum **for an LLM, not for a human.** A human starts at zero (what is a pair? how often does a flush hit?)
and must *memorize* the statistics because his head has no calculator. **Our 8B base already knows all of that** —
poker rules, hand rankings, the terminology, and Python — from pretraining. So the curriculum does NOT re-teach
concepts. It teaches the three things the base does **not** have, in the order an LLM actually acquires them:

1. our **output contract** (the DSL form — the cheap, fast-converging sub-skill it lacks → FIRST),
2. **engine-grounding** (derive from `api.*`, not from pretrained poker folklore),
3. **decision quality** (easy→hard), then **bounded exploitation**, then the **emergent mastery only RL can give**.

Math is never memorized — it is delegated to code (the engine). The model learns *which engine call answers which
question*, not the numbers. This is the same paradigm Qwen2.5-Math was post-trained for (TIR — tool-integrated
reasoning); we apply it to poker.

---

## The base model (researched, sourced 2026-06-17)

- **"Qwen2.5-8B" does not exist.** Qwen2.5 dense tops out at 7B (0.5/1.5/3/7/14/32/72B); the **8B is Qwen3**. So
  "Qwen 2.5 8B" resolves to **Qwen3-8B** — which is already our base. ([Qwen2.5 blog](https://qwenlm.github.io/blog/qwen2.5/),
  [Qwen3 blog](https://qwenlm.github.io/blog/qwen3/))
- **Qwen3-8B:** 8.2B params, 36 layers, GQA 32q/8kv, **32 768 native ctx** (131 072 via YaRN), vocab 151 936, **base +
  instruct both exist**, pretraining deliberately math/code-heavy (synthetic data from Qwen2.5-Math/Coder).
  ([model card](https://huggingface.co/Qwen/Qwen3-8B))
- **Decision — base = Qwen3-8B.** Fallback if we want maximal raw-code-format fidelity with zero thinking-toggle risk:
  **Qwen2.5-Coder-7B-Instruct** (strongest code-syntax prior). Qwen2.5-Math-7B has the *perfect paradigm* (TIR) but is
  "not recommended for other tasks" → borrow the idea, not the weights.

### Three Qwen facts that SHAPE this curriculum
1. **Non-thinking is a first-class hard switch** (`enable_thinking=False`). Our program-of-thought **IS** the reasoning
   — we want NO `<think>` trace: it would blow up per-generation latency in the CPU-bound RL reward loop. **Train and
   run non-thinking throughout.** (Alibaba later split Qwen3 into separate Instruct/Thinking checkpoints — the hybrid
   was a known wart; training non-thinking-only sidesteps it.)
2. **Format is the cheap, fast-converging sub-skill** (in RL it lands in ~50 steps, *before* correctness). → put a
   format/contract stage FIRST; reward format separately from EV.
3. **SFT-cold-start, then low-lr GRPO.** RL-from-base works only for *known* domains (DAPO/R1-Zero on math); our engine
   API is a **novel DSL the base has never seen** → SFT must teach the contract first, then GRPO (lr ~1e-6, KL≈0)
   optimizes EV. This is exactly the user's "bewusst (SFT) → automatisch (RL)" split.

---

## The five phases

Each phase = an ordered dataset shard built by our existing builders, trained non-thinking, with **completion-only
loss** (mask the prompt — see below) and a **replay slice of earlier phases mixed in** (prevents forgetting; published
curriculum result). The difficulty signal for ordering is **our own candidate-EV spread** (`pilot.rank_state`) — the
same machinery that pre-filters zero-gradient RL states also ranks SFT spots easy→hard.

| Phase | Goal (what the LLM acquires) | Data source (our builder) | Gate / metric |
|---|---|---|---|
| **A — Contract** | Emit a VALID DSL program every time: `# comment` · `var = api.fn(...)` · final `decide(...)`. Trivial/clear spots, high volume. | `dataset/build/from_selfplay.py` (engine-oracle decisions), clearest spots first | **DSL-emit / grammar-match ≥ 99 %** (frac_bad < 1 %) |
| **B — Grounding** | Map question → the RIGHT engine call; derive from `api.*`, not folklore. The 66 verified formulas as worked examples. | `dataset/build/from_calc.py` (postflop+strategy formulas) + math/exploit shards | **engine_grounded_rate ≥ 90 %** (api.* before decide) |
| **C — Decision quality (easy→hard)** | Spot → EV-optimal action across the full distribution. C1 clear (unambiguous fold/value) → C2 standard → C3 marginal (high EV-spread). Optional sub-order by street. | PokerBench (decide-form, decontam'd) + engine-oracle self-play, ranked by EV-spread | **PokerBench-acc ≥ 70 %** (G0) |
| **D — Bounded exploit (GTO-lens)** | Decisions vs reads/profiles: deviate by Δ, justified by EV vs its exploitability cost. The hardest → last. | `knowledge_base/exploit/` playbook (11.5k) + range_tracker/opp_model-conditioned spots | exploit shards don't raise frac_bad / don't tank held-out robustness-spread |
| **E — RL self-play (emergent)** | Lift ABOVE the SFT teacher via realized EV — the "feel" no explicit data can teach (the user's "automatic"). | `training/qwen_grpo.py` (DAPO-GRPO) on `rl_env` self-play + the league | **G2: RL > SFT-init by sig. bb/100** (the thesis) |

Phases A→D = SFT (the conscious foundation). Phase E = RL (the automatic mastery). Decontaminate every SFT shard vs
the PokerBench test split (`dataset/decontam.py`) throughout.

---

## Cross-cutting principles (the "for an LLM, not a human" essence)

1. **Non-thinking, always** (`enable_thinking=False`) — the program is the reasoning; no `<think>`. Sampling per the
   official non-thinking card: T 0.7 / top-p 0.8 / top-k 20 (NOT greedy in any thinking path).
2. **Completion-only loss masking** (`assistant_only_loss=True`, or a response-template collator) + **`packing=False`**
   for Phase A. *This is the current bug:* `qwen_sft.py` trains on the full sequence with `packing=True` → the model
   learns to re-predict the prompt instead of to PRODUCE the program. Fixing this is Phase-A's enabling change and a
   prime frac_bad suspect.
3. **Replay / interleave** earlier phases forward (≈10-20 % of each later phase) — LoRA is forgetting-resistant for
   code/math but not immune; carrying prior data prevents the narrow poker pass from crowding out the base code prior.
4. **Difficulty = candidate-EV spread** (`pilot.rank_state`) — one signal orders the SFT curriculum AND gates RL
   (drop zero-spread states = DAPO dynamic sampling). No separate difficulty model needed.
5. **LoRA recipe:** r 32 / alpha 64 (= 2·r; our current r64/α128 is also fine, more capacity), `all-linear` targets,
   **SFT lr 2e-4**, ≤ 3 epochs, completion-only. **RL lr ~1e-6**, **KL ≈ 0** (DAPO `beta=0`), separate binary
   **format-reward** + the realized-EV reward + the small decaying engine-grounded shaping.

---

## Why this is the frac_bad fix

The local proof showed frac_bad = 1.0 / engine_grounded_rate = 0.0 / short completions. Causes, in order of
confidence: (1) **full-sequence loss + packing** (model never cleanly learned "produce ONLY the program") → Phase-A's
masking change; (2) **no format-first staging** (math+exploit data taught no `decide()` until late) → Phase A IS the
decision-form, first; (3) the **1.7B local proof is genuinely weak** — the real target is 8B, where format (the cheap
sub-skill) lands far more reliably. The curriculum addresses (1) and (2) structurally; (3) is why the proof is a
plumbing test, not the model.

## Build order
1. **Phase-A enabling fix** in `qwen_sft.py`: `assistant_only_loss=True`, `packing=False` for the contract stage, and
   make a `CURRICULUM` env that trains shards in order A→D with replay. Re-run the local proof → expect frac_bad ↓.
2. Stage the existing builders into ordered shards (`dataset/shards/{a_contract,b_ground,c_decide,d_exploit}.jsonl`),
   each ranked by EV-spread, decontam'd.
3. Phase E unchanged (DAPO-GRPO already built) — add an explicit binary format-reward alongside the EV reward.
4. Scale on the pod (Qwen3-8B, the curriculum'd SFT → GRPO).
