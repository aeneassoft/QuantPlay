# Qwen 6-max training pipeline — conceptual+RL (gpt-5.5)

## Bottom line

Your right bet is **not “more PokerBench SFT” and not PPO-on-hands**. The best practical recipe is:

1. **Clean domain adaptation / theory grounding** — small, optional, before decision SFT.
2. **High-volume supervised policy SFT** — PokerBench + solved ranges/postflop + curated theory/exploit examples.
3. **Preference / critique training** — action comparisons from solver/rollout/frontier-gated labels.
4. **Expert-iteration self-play** — generate 6-max states, evaluate candidate actions by rollouts vs a frozen diverse league, train Qwen toward EV-improved action distributions, repeat.
5. **Keep frontier APIs as targeted teachers/critics, not the reward and not the final authority.**

Brutal honesty: **SFT + frontier distillation alone probably will not beat a well-prompted Opus/Claude brain on genuinely novel poker reasoning.** It may beat it on latency, consistency, cost, private range knowledge, and eventually on your specific 6-max arena if expert-iteration works. The only credible way to “lift above the teacher” is **environmental policy improvement**, not more imitation.

---

# 1. Staged curriculum

## Stage 0 — Freeze evals, action schema, and baselines first

Before more training, lock down:

- **Action schema**: no free-form prose in live play.
  - Example:
    ```json
    {
      "action": "raise",
      "size_bb": 7.5,
      "size_class": "75_pot",
      "confidence": 0.62
    }
    ```
  - Map to legal actions: fold/check/call/raise sizes/all-in.
  - Use a fixed bet-size abstraction initially: e.g. 25%, 33%, 50%, 75%, 100%, 150% pot, all-in, plus preflop standard raises.

- **Canonical state serializer**:
  - Positions, stacks, pot, SPR, action history, board, hero cards, legal actions, opponent stats if available.
  - Do not include future cards or hand result.

- **Baselines**:
  - Current Qwen LoRA.
  - Base Qwen.
  - Prompted Opus/GPT/o3 on a spot set, not necessarily full-hand expensive eval.
  - Simple scripted bots.
  - Other LLM bots.

- **Frozen evals**:
  - PokerBench held-out.
  - Private six-max spot set.
  - Arena panel with fixed seeds.
  - LBR-style bounded exploitability proxy.

Why first: otherwise every later improvement is vulnerable to leakage, Goodharting, or panel overfit.

---

## Stage 1 — DAPT-lite / continued pretraining on theory

Use this only as **domain grounding**, not as the main skill source.

Recommended:

- Start from base Qwen, not the already PokerBench-SFT LoRA, for the clean final run.
- Do a **small continued-pretraining pass** on cleaned MD/JSON, not raw PDFs.
- Low LR, short duration.
- Then do SFT.

Data here:

| Source | Use in Stage 1? | Purpose |
|---|---:|---|
| `knowledge_base/math` | Yes | Pot odds, MDF, Kelly, combinatorics, EV formulas |
| `knowledge_base/concepts` | Yes | Terminology, strategic language |
| `knowledge_base/theory` | Yes, but low weight | Teach that 6-max is not clean 2p zero-sum Nash |
| Raw PDFs | Mostly no | Only use if extraction missed material |
| Hand histories | Small amount | Format/action-history familiarity |
| Ranges/postflop tables | Small amount | Not ideal for pure LM continuation; better for SFT |

Brutal honesty: DAPT may help the model sound and reason more poker-native, but **do not expect large bb/100 gains**. If GPU budget is tight, convert theory into instruction examples instead and skip DAPT.

Expected ROI:

- Poker terminology/formula recall: helpful.
- Decision quality: modest.
- Risk: catastrophic drift or more verbose “book poker” if overdone.

---

## Stage 2 — SFT policy warm-start

This is where your current LoRA got the big jump: 18.3% to 71.7% PokerBench held-out match. Continue, but broaden the supervised target beyond PokerBench.

Main objective:

- Produce legal, compact, strategically sane actions.
- Learn preflop charts and solver-calibrated postflop frequencies.
- Learn exploit adjustment language, but not overfit to noisy hand outcomes.

Data mapping:

| Source | Use | Training format |
|---|---|---|
| PokerBench | High weight | State → optimal/matched action; optional short rationale |
| Ranges | High weight | Preflop spot → mixed strategy / range frequencies |
| Postflop solver-calibrated frequencies | High weight | State → action distribution, not just one-hot action |
| Math | Medium | Verified EV/pot odds/MDF/calculation tasks |
| Concepts/books | Medium-low | Strategic QA, “when does this heuristic apply?” |
| Theory papers | Low | Meta-reasoning: why 6-max ≠ solved Nash; exploitability caveats |
| Exploit directives/playbooks | Medium | Opponent leak → adjustment; include anti-overadjustment examples |
| Hand histories | Low-medium | Parse/analyze hand; identify mistakes; do not blindly imitate winner |
| Frontier rationales | Low-medium | Short structured explanations for existing high-confidence labels |

Important: train **action-first**. Rationales are useful for supervision, but the live model should not need long chain-of-thought to act.

Example target:

```json
{
  "action": "call",
  "size_class": null,
  "strategy": {
    "fold": 0.08,
    "call": 0.72,
    "raise_75_pot": 0.20
  },
  "rationale": [
    "BTN range retains more medium-strength hands.",
    "Pot odds require about 27% equity.",
    "Hero blocks nut-flush continues.",
    "Raising is mixed but call dominates against unknown population."
  ]
}
```

Do **not** train huge verbose CoTs as the default. Use short rationales/features.

---

## Stage 3 — Preference training / DPO-style calibration

After SFT, add comparisons.

This is not “human preference” in the usual chat sense. It should be **poker-EV preference**:

- Correct action > plausible bad action.
- Higher rollout-EV action > lower rollout-EV action.
- Solver-frequent action > solver-zero-frequency punt.
- Against opponent leak, exploit adjustment > default line, but only when leak evidence exists.

Good sources:

| Source | Preference examples |
|---|---|
| PokerBench | Solver/label action vs legal bad alternatives |
| Postflop frequencies | High-frequency action vs low-frequency action |
| Ranges | Correct mixed range vs dominated range |
| Frontier critiques | Qwen output vs corrected output, only if gated |
| Self-play rollouts | Candidate action A has higher estimated EV than B |
| Exploit playbooks | Adjustment with opponent stats vs unjustified over-exploit |

Use DPO/IPO/AWR here, but keep a supervised anchor.

Recommended objective shape:

```text
Loss = DPO_or_IPO(EV-ranked pairs)
     + alpha * SFT_anchor_loss
     + beta * KL_to_reference_policy
     + gamma * format/legal_action_loss
```

Do not turn close EV differences into hard deterministic labels. Poker is mixed. If call and raise differ by noise-level EV, train a distribution, not “raise is correct, call is wrong.”

---

## Stage 4 — Expert-iteration self-play

This is the core RL recipe.

Do not try to compute six-max Nash. Do not run vanilla PPO over full hand transcripts. Instead:

1. Let current Qwen/panel generate realistic six-max states.
2. At sampled decision states, enumerate/suggest candidate actions.
3. Estimate each candidate action’s EV by rollouts against a frozen opponent mixture.
4. Train Qwen toward the better action distribution.
5. Add the improved checkpoint to a league only if it passes gates.

This is **expert iteration**, with rollout-EV acting as the expert/improvement operator.

Why this order:

- SFT makes exploration sane.
- Preference training teaches local action ranking.
- Expert iteration is what can lift above PokerBench/frontier teachers.
- League/panel training prevents single-opponent overfit.

---

# 2. Data mix and anti-memorization

## Suggested SFT mix

For the first serious post-DAPT SFT run:

| Data category | Approx. example weight |
|---|---:|
| PokerBench decision points | 40–50% |
| Solved preflop ranges | 10–15% |
| Solver-calibrated postflop frequencies | 10–15% |
| Math/formula/calculation tasks | 5–10% |
| Concepts/book-derived strategic QA | 5–10% |
| Exploit directives/playbooks | 10–15% |
| Hand-history analysis | 5% |
| Frontier-distilled rationales/critiques | 5–10% |

After the model is already stable, shift toward:

| Data category | Later-stage weight |
|---|---:|
| Rollout/self-play preference data | 50–70% |
| PokerBench/solver anchor | 15–25% |
| Ranges/postflop anchor | 10–15% |
| Theory/math/exploit maintenance | 5–10% |
| Frontier targeted data | 5–10% |

Theory should not dominate decision training. If 30–50% of late training is book/theory text, you are probably training a poker commentator, not a poker player.

---

## How to convert each root-folder source

### `knowledge_base/math`

Convert to verified programmatic tasks:

- Pot odds.
- MDF.
- Bet-size thresholds.
- EV of bluff/call/fold.
- Combinatorics/blockers.
- Stack-to-pot ratio.
- Kelly/variance/risk if relevant.

Example:

```text
Instruction:
Pot is 80bb. Villain bets 40bb. Hero estimates 31% equity if calling.
Should Hero call in pure chip EV terms?

Target:
Call. Hero must call 40 to win 160, needing 25% equity. 31% > 25%.
```

Use `formulas.py` to auto-check answers. This is low-leakage and high-quality.

---

### `knowledge_base/concepts`

Convert to:

- Short strategic QA.
- “When does this heuristic fail?”
- Board texture classification.
- Range/nut advantage explanations.
- Multiway caveats.

Avoid blindly training old book heuristics as universal truth. Label context.

Example:

```text
Instruction:
In a 6-max single-raised pot, UTG opens and BB calls. Flop is A72 rainbow.
Who has range advantage and why?

Target:
UTG generally has range and nut advantage due to stronger Ax density. BB has many weak pairs and suited connectors. UTG can c-bet frequently small, but sizing/frequency depend on stack depth and population.
```

---

### `knowledge_base/theory`

Use mostly for meta-strategy, not action labels.

Train the model to know:

- HU zero-sum solver intuition does not transfer cleanly.
- Six-max is multiplayer/general-sum.
- CFR convergence guarantees differ.
- Evaluation should be empirical: bb/100 vs panel, LBR, robustness.
- Population exploitation can be rational.

This prevents the model from hallucinating “solver-perfect Nash” claims.

---

### `knowledge_base/exploit`

High value if converted correctly.

Format:

```text
Input:
6-max cash. Villain in BB folds 72% to BTN steals over 500 hands and under-3bets.
Hero is BTN with K7s, 100bb.

Target:
Open wider than baseline. K7s is profitable. Use standard/minor larger open depending pool. Do not overreact if SB is aggressive.
```

Also create anti-overexploit pairs:

```text
Rejected:
Open any two cards because BB overfolds.

Chosen:
Open significantly wider but retain blockers/playability; monitor SB squeeze frequency.
```

Exploit data is dangerous if unconditional. Always include:

- Opponent tendency.
- Sample size/confidence.
- Position.
- Stack depth.
- Counter-adjustment risk.

---

### `knowledge_base/ranges`

This is high-value supervised data.

Convert tables to:

- Spot → mixed range.
- Hand class → action frequency.
- Full range summaries.
- Randomized hole-card queries.

Example:

```json
{
  "spot": "6max 100bb, LJ open, CO facing raise",
  "hand": "AQo",
  "target_strategy": {
    "fold": 0.05,
    "call": 0.35,
    "3bet": 0.60
  }
}
```

Preflop memorization is not bad. It is basically the point. But still hold out some chart cells/positions for measuring generalization.

---

### `knowledge_base/postflop`

Also high-value.

Use soft labels whenever possible:

```json
{
  "state": "...",
  "target_strategy": {
    "check": 0.42,
    "bet_33": 0.36,
    "bet_75": 0.22
  }
}
```

If you have solver EVs, create preferences:

- Bet 33 > overbet if overbet has poor EV.
- Check and bet small both acceptable if EV close.

Do not force pure actions when solver frequency is mixed.

---

### `knowledge_base/hand_histories`

Use carefully.

Good uses:

- Teach action-sequence parsing.
- Teach realistic population lines.
- Ask model to analyze decisions street by street.
- Re-label important spots with solver/frontier/rollout when possible.

Bad use:

- “Hero won, therefore hero’s action was good.”
- Imitating every Pluribus/pro action at full weight.
- Including future runout before the decision.

For each decision point, mask future information:

```text
Known to hero:
Hole cards, board so far, stacks, pot, previous actions.

Unknown:
Future board, villain hole cards unless revealed already, final result.
```

---

### Raw PDFs

Do not train on raw OCR/PDF text unless necessary. It is noisy and often copyright-sensitive. Prefer your extracted JSON/MD.

---

## Anti-memorization and leakage controls

Concrete steps:

1. **Immutable eval split**
   - Lock PokerBench held-out/test.
   - Never send eval prompts to frontier APIs for labeling.
   - Never train on model critiques of eval examples if you will report them.

2. **Split by hand/source, not row**
   - Hand histories: split by complete hand ID.
   - PokerBench: split by canonical spot/hand, not prompt paraphrase.
   - Ranges: hold out cells/position classes, not just exact wording.

3. **Canonical dedup**
   - Normalize suits, positions, stack sizes, action sequence.
   - Hash canonical state.
   - Use MinHash/near-dedup on text prompts.

4. **Result masking**
   - For hand histories, remove future cards and showdown results from decision prompts.

5. **Rationale leakage check**
   - Frontier rationales for PokerBench train spots can mention the given label.
   - Frontier rationales for eval spots are forbidden.

6. **Do not optimize only PokerBench accuracy**
   - It is a cheap dev metric, not the target.
   - Require arena bb/100 and LBR not to degrade.

---

# 3. Frontier-in-the-loop active distillation

## What frontier models should produce

Use frontier APIs for four things.

### A. Short rationales for existing high-quality labels

For PokerBench/solver/range spots, the label is already better than the frontier model. Ask the frontier model to explain the known label, not override it.

Output should be structured:

```json
{
  "key_factors": [
    "Hero is IP with range advantage",
    "SPR is low enough that top pair has high stack-off value",
    "Villain's line is polar"
  ],
  "pot_odds": "Hero needs 28% equity",
  "blockers": "Ah blocks nut flush continues",
  "recommended_action": "call",
  "confidence": 0.74
}
```

Reject if the rationale contradicts the label.

---

### B. Critiques of Qwen outputs

Prompt frontier model with:

- State.
- Legal actions.
- Qwen proposed action.
- Qwen rationale.
- Optional known label if available.

Ask:

```json
{
  "is_legal": true,
  "main_error": "...",
  "better_action": "...",
  "severity": "major/minor",
  "confidence": 0.0-1.0,
  "explanation": [...]
}
```

These become:

- DPO pairs: corrected action > Qwen action.
- Critique SFT examples: “identify why this line is bad.”
- Hard-negative data.

But only if gated.

---

### C. Labels for novel/self-play spots

For states generated by your arena where no solver label exists, ask frontier models for:

- Action distribution, not one-hot.
- Confidence.
- Key assumptions.
- Exploitative vs baseline recommendation.
- “What information would change your decision?”

Example:

```json
{
  "strategy": {
    "fold": 0.15,
    "call": 0.55,
    "raise_75_pot": 0.30
  },
  "baseline_action": "call",
  "exploit_adjustment": "raise more if villain overfolds turns",
  "confidence": 0.61,
  "uncertainty": "multiway range interaction; close EV"
}
```

Use these as **candidate actions** for rollout evaluation, not final truth.

---

### D. Hard negatives

Ask frontier models to generate plausible but bad actions:

```json
{
  "bad_action": "jam",
  "why_bad": "Overrepresents hand and folds out worse while isolating against better",
  "better_action": "call"
}
```

This is useful for DPO.

---

## What frontier models should not be

Do not use frontier models as:

- The final reward.
- A replacement for chip EV.
- A pure one-shot teacher whose labels dominate training.
- An authority on six-max equilibrium.

Given your own lesson — HU frontier models are still -10 to -30 bb/100 vs GTO Wizard — blind distillation imports errors. In six-max, their exact strategic calibration is even less reliable.

---

## Quality gates

Use a hard gate before adding frontier examples.

### Mechanical gates

Reject if:

- Illegal action.
- Wrong pot size.
- Wrong pot odds arithmetic.
- Uses future information.
- Confuses positions/stacks.
- Contradicts legal raise sizing.

### Agreement gates

Prefer examples where:

- GPT/OpenAI and Claude agree on action class.
- Or one frontier model agrees with solver/PokerBench.
- Or frontier suggestion wins rollout EV.

Reject or downweight when frontier models disagree sharply.

### Calibration gates

Build a small calibration set of known labels:

- PokerBench train/dev.
- Solved preflop.
- Postflop solved frequencies.
- Your own hand-reviewed spots.

Measure each frontier model by cluster:

- Preflop 3bet pots.
- Multiway flops.
- River bluff-catchers.
- Low SPR.
- Monotone boards.
- Paired boards.
- Exploitative adjustments.

If Opus/GPT is weak in a cluster, reduce its label weight there.

### EV gates

For novel states:

- Frontier label becomes a candidate.
- Roll it out against the panel.
- Train on it only if it is competitive or clearly superior.

---

## Is active on-demand generation worth it?

Partly.

**Worth it:** targeted active distillation after you know Qwen’s weak spots.

**Overkill:** fully online API calls inside every training step.

Recommended compromise:

1. Train/evaluate Qwen.
2. Cluster mistakes:
   - Street.
   - Position.
   - Stack depth.
   - Pot type.
   - Board texture.
   - Action type.
   - Opponent profile.
3. Generate 10k–50k targeted frontier examples for those clusters.
4. Gate them.
5. Add them to SFT/DPO mix.
6. Repeat every few expert-iteration rounds.

Do not bulk-generate 500k generic frontier rationales. You will pay for a lot of mediocre labels and imported mistakes.

---

# 4. RL / self-play recipe for six-max poker LLM

## Pick: expert iteration, not vanilla PPO

My pick:

> **Expert iteration with rollout-EV policy improvement, trained via soft SFT/AWR/DPO-style losses.**

Why not vanilla PPO?

- Sparse terminal reward over long hands.
- Huge variance.
- Token-level credit assignment is misaligned because the meaningful action is one structured decision, not a long text.
- Multiplayer non-stationarity makes PPO chase transient exploits.
- PPO will happily overfit to quirks of the latest self-play population.

Why not pure DPO?

- DPO is useful for training on comparisons.
- But DPO alone does not explore or improve the policy.
- You need an environment loop to generate better comparisons.

Why not pure GRPO?

- GRPO-style group-relative updates can work at the **spot level**: sample several actions for the same state, reward by rollout EV, update relative to the group.
- But full-hand GRPO with realized chip outcome is still high-variance.
- If you use GRPO tooling, use it as an implementation of spot-level expert iteration, not as blind online RL.

---

## Core loop

### Step 1 — Maintain a league/panel

Include:

- Current Qwen.
- Previous Qwen checkpoints.
- Current PokerBench LoRA.
- Base scripted TAG/LAG/nit/calling-station/maniac bots.
- Other LLM policies if affordable.
- Exploitative archetypes.
- Maybe prompted Opus/GPT on a limited spot basis.

Suggested training opponent mixture:

| Opponent type | Weight |
|---|---:|
| Frozen strong/reference bots | 30–40% |
| Previous Qwen checkpoints | 20–30% |
| Current/self-play variants | 20–30% |
| Exploitative/weird population bots | 10–20% |

Do not train only against the latest self. That is how collapse happens.

---

### Step 2 — Generate states

Run many six-max hands.

Store every Qwen decision state:

```json
{
  "state": "...",
  "hero_position": "CO",
  "street": "turn",
  "pot_type": "3bet_pot",
  "spr": 3.2,
  "board_texture": "paired_flushdraw",
  "legal_actions": [...],
  "qwen_action": "...",
  "opponent_profiles": [...]
}
```

Oversample high-leverage spots:

- River bluff-catchers.
- Facing large bets.
- 3bet/4bet pots.
- Multiway flops.
- Low SPR.
- Spots where Qwen disagrees with PokerBench/frontier/rollouts.
- Spots with high pot size.

---

### Step 3 — Generate candidate actions

For each state, candidate actions come from:

- Qwen samples at temperature.
- Legal action abstraction.
- Current policy top-k.
- Previous checkpoints.
- Solver/range prior if available.
- Frontier suggestions if gated.
- Simple tactical alternatives: fold/call/small bet/big bet/jam.

Usually 4–8 candidates per state is enough. More is expensive and often redundant.

---

### Step 4 — Estimate action EV by rollouts

For each state-action pair:

```text
Q_hat(s,a) = average net bb from rolling out hand after forcing action a
```

Use:

- Fixed opponent policies from the league.
- Common random numbers where possible.
- All-in equity adjustment instead of raw runout result.
- Same public state and legal private-card constraints.
- Multiple seats/positions.

Rollout counts:

| Spot type | Initial rollout count |
|---|---:|
| Preflop/common spots | 16–32 |
| Flop/turn medium pots | 32–64 |
| River/large pots/all-in | 64–256 |

Do not train on noisy tiny EV differences. Require:

- Confidence interval separation, or
- EV gap > roughly 0.25–0.5bb for a single decision, depending pot size/variance.

For close actions, produce mixed targets:

```text
p*(a|s) ∝ π_ref(a|s) * exp(Q_hat(s,a) / temperature)
```

This is better than hard winner-take-all labels.

---

### Step 5 — Train policy improvement

Create examples:

#### Soft target SFT/AWR

```json
{
  "state": "...",
  "target_strategy": {
    "call": 0.55,
    "raise_75": 0.35,
    "fold": 0.10
  }
}
```

#### Pairwise DPO

```json
{
  "chosen": "call",
  "rejected": "jam",
  "ev_gap_bb": 1.8
}
```

Recommended training mix per expert-iteration round:

| Data | Weight |
|---|---:|
| New rollout-EV soft targets/pairs | 60–70% |
| PokerBench/range/postflop anchor | 20–30% |
| Exploit/theory/math maintenance | 5–10% |
| Frontier targeted examples | 0–10% |

Keep KL to the SFT reference. Poker policies need stability and mixedness.

---

## Reward design

Training reward should be:

```text
terminal net bb, all-in adjusted when possible
```

But do not naively assign the final hand result to every token/action. Instead use decision-level rollout EV.

For model selection, use a robust score:

```text
Score(policy) =
  mean bb/100 vs evaluation panel
  - λ * LBR_exploitability_proxy
  - μ * worst_cluster_loss
  - ν * PokerBench_drop_penalty
```

Where:

- `mean bb/100` is the main target.
- `LBR` punishes policies that are easy to exploit.
- `worst_cluster_loss` stops the model from farming weak bots while losing badly to one archetype.
- `PokerBench_drop_penalty` prevents forgetting solver-derived fundamentals.

Example promotion rule:

- Promote checkpoint only if:
  - Arena bb/100 improves with 95% bootstrap CI or clear practical margin.
  - PokerBench accuracy drops < 2–3 percentage points.
  - LBR exploitability proxy does not worsen materially.
  - No catastrophic loss to any major opponent cluster.

---

## Credit assignment

Bad approach:

```text
Play full hand, receive +73bb, reinforce every generated token.
```

Good approach:

```text
At a decision state, force action A/B/C, roll out each many times, estimate local action EV.
```

This converts poker RL into many contextual bandit-style decisions with reduced variance.

You can still train a value model later, but that is not the first priority. A learned value/reward model is useful for rollout pruning, not as the ground truth.

---

## Preventing self-play collapse

Concrete safeguards:

1. **Frozen league**
   - Keep old checkpoints and scripted archetypes.
   - Never only train current-vs-current.

2. **Robust objective**
   - Optimize average plus worst-case constraints.
   - Do not let one fish bot dominate the reward.

3. **SFT/KL anchor**
   - Maintain 20–30% anchor data early.
   - Reduce later only if robustness holds.

4. **Entropy/mixing**
   - Poker has close mixed spots.
   - Do not collapse all frequencies to pure actions because of noisy rollouts.

5. **Held-out opponent panel**
   - Training panel and eval panel must differ.
   - Otherwise you will manufacture fake bb/100.

6. **LBR-style checks**
   - Approximate one-seat best response against Qwen with others fixed.
   - Run per seat and per opponent mixture.

7. **Seed discipline**
   - Fixed dev seeds for comparability.
   - Fresh final seeds for reporting.

---

# 5. ROI, risks, and cheapest de-risking experiment

## Does this realistically beat just prompting Opus 4.8?

Three separate answers:

### On latency/cost/control

Yes, likely.

A tuned local Qwen is cheaper, faster, more controllable, and can encode your private ranges/exploit data.

### On PokerBench-style decision match

Likely yes or competitive, especially since your current Qwen LoRA is already strong on PokerBench-style prompts.

### On true six-max win-rate against diverse opponents

Uncertain.

Brutal version:

- **Plain SFT:** probably does not beat Opus robustly.
- **SFT + one-shot frontier distill:** may approach Opus style but inherits mistakes.
- **Expert iteration vs a good six-max league:** the only realistic path to beating Opus in your environment.
- **General robustness beyond your panel:** still uncertain.

If you optimize hard against your arena, you can probably beat prompted Opus **in that arena**. Beating it as a general poker brain is much less guaranteed.

---

## Biggest risks

### 1. Reward/panel overfit

You may build a bot that crushes your bots and loses to a new style.

Mitigation:

- Diverse league.
- Held-out panel.
- LBR.
- Worst-cluster penalty.

---

### 2. Noisy EV estimates

Poker variance is brutal.

If standard deviation is ~100–150 bb/100, then:

- 25k hands gives very noisy results.
- 100k hands can detect large changes.
- 500k+ hands may be needed for modest improvements.
- Millions are needed for small bb/100 differences.

Use all-in adjusted EV and bootstrap confidence intervals.

---

### 3. Frontier mistake distillation

GPT/Claude will make plausible, articulate poker mistakes.

Mitigation:

- Frontier outputs are candidates/critics, not truth.
- Gate by legality, arithmetic, agreement, solver checks, and rollout EV.
- Keep frontier-labeled data minority weight.

---

### 4. Hand-history result bias

Training on “winning” lines teaches superstition.

Mitigation:

- Mask future cards/results.
- Re-label decisions.
- Low weight for raw imitation.

---

### 5. Action abstraction mismatch

If your model can choose weird sizes or illegal actions, evaluation becomes garbage.

Mitigation:

- Constrained output.
- Legal-action parser.
- Fixed sizing abstraction at first.

---

### 6. PPO/GRPO instability

Full-hand token-level RL is likely expensive and unstable.

Mitigation:

- Use expert iteration / rollout-ranked decisions.
- If using GRPO tooling, use it spot-wise.

---

### 7. DAPT overkill

Too much theory continuation can make the model verbose and less policy-sharp.

Mitigation:

- DAPT-lite only.
- Watch PokerBench/action accuracy after DAPT.
- If it drops, skip DAPT in final recipe.

---

## Cheapest de-risking experiment

Do this before a full RunPod spend.

### Goal

Test whether **rollout-EV expert iteration improves current Qwen beyond SFT**.

### One-week experiment

1. **Start from current Qwen LoRA.**

2. **Generate 10k–20k six-max decision states**
   - From arena self-play and panel play.
   - Focus on turn/river and large pots.
   - Exclude eval seeds.

3. **For each state, create 4 candidate actions**
   - Qwen action.
   - One alternative legal action.
   - Heuristic/bot action.
   - Optional frontier suggestion for only 1k–2k hard spots.

4. **Roll out each candidate**
   - 32–64 rollouts per action.
   - Fixed opponent mixture.
   - Common random seeds where possible.
   - All-in adjusted EV.

5. **Build DPO/AWR dataset**
   - Only use pairs with clear EV gap or CI separation.
   - Keep mixed labels for close spots.

6. **Fine-tune a small LoRA**
   - 1 epoch.
   - Mix:
     - 60% rollout preference/soft targets.
     - 30% PokerBench/range anchor.
     - 10% exploit/theory/frontier critique.

7. **Evaluate**
   - PokerBench held-out.
   - 100k+ hands vs held-out panel if engine is fast.
   - LBR proxy.
   - Compare against original Qwen LoRA.

### Pass criteria

Continue to full pipeline only if:

- Arena bb/100 improves by a practically meaningful amount, e.g. +10–20 bb/100 on dev panel, or statistically significant smaller gain.
- PokerBench accuracy drops < 2–3 percentage points.
- LBR proxy does not worsen materially.
- Improvement transfers to held-out opponents, not only training bots.

If this cheap expert-iteration pilot does **not** move bb/100, the full frontier+DAPT+RL pipeline is probably overkill until the environment, action abstraction, or rollout evaluator is fixed.

---

## Final recommendation

Build the full system, but prioritize ruthlessly:

1. **First priority:** reliable six-max arena eval + constrained action schema.
2. **Second:** SFT on PokerBench/ranges/postflop with theory/exploit support.
3. **Third:** rollout-EV expert iteration.
4. **Fourth:** targeted frontier critiques for weak clusters.
5. **Low priority / overkill:** raw-PDF DAPT, long CoT distillation, full PPO over hand transcripts, frontier-as-reward.

Your measured lesson is exactly right: imitation gives you the floor. The ceiling comes only from a policy-improvement loop tied to actual six-max EV and robust opponent diversity.
