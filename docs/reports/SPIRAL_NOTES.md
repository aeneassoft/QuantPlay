# SPIRAL — Full extraction (ICLR 2026)

**Paper:** Liu, Yu, Liu, Guertler et al., *SPIRAL: Self-Play on Zero-Sum Games Incentivizes Reasoning
via Multi-Agent Multi-Turn Reinforcement Learning*, ICLR 2026. Code: `github.com/spiral-rl/spiral`.
Source: `books/papers/Poker Math 2026/ICLR-2026-spiral-...pdf` (28 pp., read completely via fitz, 2026-08-16).
Context for us: our league-reward GRPO measurably regressed to **−90 vs GTOW** (self-play league ≠ GTOW,
the RL learned league-beating aggression). SPIRAL is the candidate for the better reward setup.

---

## 1. The self-play setup (exact)

- **Games:** three two-player zero-sum games from TextArena: **TicTacToe** (spatial, perfect
  information), **Kuhn Poker** (probabilistic, hidden information), **Simple Negotiation**
  (strategic optimization, resource trading). Formally: collection G = {G1..Gn}, each Gi a
  two-player zero-sum Markov game on **turn-level MDPs** (state = complete context,
  action = complete multi-token response, not token level).
- **Opponents = self-improving copies:** ONE shared policy net πθ plays BOTH roles
  (θ0 = θ1 = θ). Role conditioning via the system prompt ("You are Player 0/1"). Hence
  **auto-curriculum**: if the model improves in one role, its opponent automatically becomes
  equally strong — no static opponent that can be exploited.
- **Zero-sum + sparse reward:** r = 0 on all non-terminal states; at the end
  R0(τ) = ρ(sT) ∈ {−1, 0, +1}, R1(τ) = −R0(τ). No reward shaping, no intermediate reward.
- **Fully online, multi-agent, multi-turn:** distributed actor-learner architecture (built on Oat,
  IMPALA style), vLLM for inference, TextArena as vectorized game environment; K parallel actors
  collect trajectories, a central learner does synchronous full-parameter updates (no LoRA,
  no offline batch). Game per rollout drawn randomly from G.
- **Hyperparameters (Table 6):** 400 steps × 128 samples, 8×H100 (~25 h Qwen3-4B / 28 h 8B),
  AdamW (β 0.9/0.95), LR 1e-6 constant, temperature 1.0, max. 8192 response tokens, batch 128,
  discount γ=1, **EMA decay α=0.95**, KL coefficients 0.0, PPO clip 0.2, 2 inner epochs,
  grad clip 1.0. Trained models: Qwen3-4B/8B-Base, Octothinker-8B-Base, Llama-3.1-8B-Instruct,
  DeepSeek-R1-Distill-Qwen-7B, Qwen3-4B-Instruct-2507.

**The central curriculum finding (Tab. 3 + Fig. 5):** training against FIXED opponents fails.
Random opponent → collapse; Mistral-Small-3 as opponent → benchmark average **29.6 (WORSE than the
basis 34.0)**; Gemini-Flash-Lite as opponent → 33.4. The win rate vs Gemini rises 0% → 62.5%
(= exploitation of the static strategy), while self-play holds a constant 50–52% against its own copy
(t−16) — the model keeps learning instead of exploiting a fixed point. **That is structurally exactly
our −90 regression: beating the league ≠ getting better.**

## 2. Role-conditioned Advantage Estimation (RAE)

**Formula (Eq. 2):** per game G and role p ∈ {0,1} a separate baseline, updated via EMA:

```
b_{G,p} ← α · b_{G,p} + (1−α) · R_p(τ)          (α = 0.95)
A_{G,p}(τ) = R_p(τ) − b_{G,p}
```

Policy gradient (Eq. 3) = REINFORCE over full responses, with A_{G,p} instead of raw return:

```
∇J = E_G E_τ [ Σ_p Σ_{t∈T_p} A_{G,p}(τ) · ∇ log πθ(y_t | s_t, p, G) ]
```

Deliberately NO length normalization (length bias, reference to the Dr.-GRPO critique Liu 2025c).

**Why it stabilizes multi-agent LLM RL:**
1. **One net optimizes opposing objectives** (R1 = −R0) — the same weights receive gradients
   in both directions; without centering the variance is enormous, and additionally the environment
   is non-stationary (the opponent is one's own changing policy).
2. **Role asymmetries:** different roles have different expected returns
   (first-move advantage TicTacToe, information asymmetry Kuhn Poker). A global baseline mixes
   that; the role-specific baseline removes the position-conditioned share from the signal —
   the gradient reflects LEARNING, not the inherent position EV.
3. **Measured ablation ("Thinking Collapse", Fig. 6+9):** without RAE, thinking collapses catastrophically after ~100–200
   steps — reasoning traces drop from ~2,000 characters to ~0 (degenerate
   outputs like `\boxed{bet}`), math score crashes 35% → 12%, the gradient norms spike erratically
   and then collapse to ~0 (degenerate policy). With RAE: stable lengths 1,300–1,500,
   gradient norm stable ~0.1, benchmark 40% → 47%.

## 3. All the numbers

**Main table (8 benchmarks: MATH500, AIME24, AIME25, OlympiadBench, AMC-23, Minerva Math,
GPQA-Diamond, MMLU-Pro; average):**

| Model | Basis | SFT-Multi (25k) | SPIRAL-Multi | Δ vs basis |
|---|---|---|---|---|
| Qwen3-4B-Base | 34.0 | 39.7 | **44.5** | **+10.5** |
| Qwen3-8B-Base | 39.5 | 46.1 | **49.6** | **+10.1** |
| Octothinker-8B-Base | 25.8 | 27.0 | **33.8** | +8.0 |
| Llama-3.1-8B-Instruct | 23.9 | 25.0 | **25.9** | +2.0 |
| DeepSeek-R1-Distill-Qwen-7B | 60.4 | 58.3 (−2.1!) | **61.8** | +1.4 |
| Qwen3-4B-Instruct-2507 | 74.1 | 71.9 (−2.2!) | **75.9** | +1.8 |

- **vs SFT-25k:** the SFT data are 25,000 WINNER trajectories from Qwen3-32B self-play (expert).
  SPIRAL beats SFT on all 8 benchmarks. **SFT-52k (doubled) brings NOTHING** (39.7 → 39.7)
  — the gain comes from the RL dynamics, not from the data volume. On already strong models
  (R1-Distill, 4B-Instruct) SFT even REGRESSES, SPIRAL improves further.
- **Only Kuhn Poker (SPIRAL-Kuhn):** 43.4 — a single 3-card game beats SFT on 25k
  expert trajectories (39.7).
- **Fixed opponents (Kuhn):** Mistral opponent 29.6, Gemini opponent 33.4, both ≤ basis 34.0.
- **Specialist transfer (Tab. 4):** poker specialist wins **91.7% Pig Dice** (risk/EV game,
  never seen); TicTacToe specialist 56.0% Snake; Negotiation 55.8% Truth-and-Deception.
- **Multi-game vs Gemini-2.0-Flash (Tab. 5):** 59.5% average vs best specialist 52.9%.
- **OOD complexity (Tab. 8):** 5-Card Kuhn Poker: SPIRAL 50.1 vs SFT 28.6 vs basis 21.9 —
  self-play generalizes to the larger game, imitation does not.
- **Reasoning-pattern transfer (Fig. 4, GPT-4.1-classified, 290 games + 46,792 math solutions):**
  case-by-case analysis 72% (game) → 71% (math, almost perfect), pattern recognition 35% → 45%
  (amplified), EV computation 78% → 28% (selective). Math score in parallel 31.2 → 39.6.
- **As a mid-training stage (Tab. 12):** RLVR→SPIRAL 47.9 > SPIRAL→RLVR 46.5 > RLVR 46.0 > SPIRAL 44.5.
- **Robustness:** 3 seeds (14/42/100): SPIRAL 44.5 ± 0.5 vs SFT 39.6 ± 0.4.
- **Trajectory statistics (Tab. 11):** over training the game length rises 1.7 → 9.6 moves and
  P1 win rate 42.7% → 62.4% (the model learns to use the position advantage); win rate vs
  Gemini-2.0-Flash 12.5% → 67.4%.

## 4. Kuhn Poker details

- **Environment (TextArena):** "5 round game of Kuhn Poker". 3-card deck J/Q/K (J lowest),
  each player antes **1 chip per round** and receives 1 card; 5 rounds; **whoever has the most chips
  after all rounds wins the match**. Actions as bracket tokens: `[check]`, `[bet]`
  (1 chip), `[call]`, `[fold]`.
- **Reward:** ONLY terminal at match level: ρ(sT) ∈ {−1, 0, +1} for the match outcome (not per
  round, not chip-proportional!), zero-sum R1 = −R0. All intermediate moves reward 0.
- **Roles:** Player 0 / Player 1 conditioned via system prompt; active player p = t mod 2.
  Role asymmetry (who acts first / information flow) is exactly what RAE factors out.
- **Trajectory format:** per move the model generates
  `y_t = <think>c_t</think><answer>a_t</answer>` — c = externalized reasoning, a = the action
  (parsed via extract_action). The gradient runs over the FULL sequence y (thinking + action),
  weighted with the match advantage.
- **Partial observability:** the history of all actions is concatenated into the state s_t
  (Markov representation despite the hidden card).
- Observed learned patterns in the Kuhn game: explicit EV computation ("EV(call) = 0×2 − 1×2 = −2 <
  EV(fold) = −1 → fold"), case enumeration, reading opponent patterns across rounds.

## 5. TRANSFER TO US — pre-registered experiment design (NOT to be run immediately)

**Diagnosis match:** our measured GRPO regression (−90 vs GTOW after league-reward RL) is the
SPIRAL fixed-opponent result in pure form: the sixmax league (TAG/LAG/nit/station/maniac) is a
STATIC opponent ensemble → the RL learned league-beating aggression (win rate vs league high,
vs GTOW −90), exactly like Gemini-opponent training 0%→62.5% win rate with WORSE benchmarks.
SPIRAL's two mechanisms additionally address two known construction sites of our own:
(a) the auto-curriculum replaces the league, (b) RAE replaces/repairs the advantage estimation
(our R_BAD=−30 variance problem in `training/qwen_grpo.py`, memory `grpo-reward-fix`, was
the same error type: reward terms that drown the EV signal).

**Concrete changes to `training/qwen_grpo.py` (or a future GLM run via
`infra/gtow_glm_pod.py`):**

1. **Opponents = copies instead of league (core change):** in the rollout loop ONE shared
   policy plays ALL seats (HU first: both seats), conditioned on seat/position in the prompt —
   instead of `arena/sixmax.py` profiles as opponents. Alternatively (weaker form) a frozen-snapshot pool
   of the last k checkpoints. The league may remain as EVAL, never as reward opponent.
2. **RAE instead of group normalization:** GRPO's group-relative advantage over mixed
   positions is confounded in poker — BB ALWAYS loses on average, BTN wins on average.
   Replace with position- and game-conditioned EMA baselines:
   `b_{spiel,pos} ← 0.95·b + 0.05·R`; `A = R − b_{spiel,pos}` (position = seat: SB/BB/BTN/…;
   "game" = stack-depth/format bucket). No length normalization.
3. **Reward = pure zero-sum chip outcome** of the match/hand (bb), terminal, without
   shaping terms (no R_BAD, no legality bonuses — legality is enforced by the executor anyway).
4. **Fully online** (no offline batch of league games): actors collect self-play hands from the
   CURRENT policy, learner updates, weights synchronize — our pod harness can do that
   (Oat reference code in the SPIRAL repo as template).
5. **Thinking-collapse watchdog:** log response length + gradient norm per step; trace length
   → 0 or grad norm → 0 = abort criterion (their collapse came after ~100–200 steps).

**Pre-registration (design, expectation, gate):**
- **Arms:** A = protected baseline (`models/grpo_slim.tgz`, ≈ −40 robust, do NOT touch);
  B = self-play + RAE + chip reward (changes 1–5), same steps/compute as the last
  league run.
- **Expectation (honest):** B eliminates the league-exploitation mode (the −90 class). Expected
  direction: body improvement over −40, NO promise below −20 — SPIRAL demonstrates
  curriculum superiority on tiny games, not NLHE strength. Null hypothesis that can refute
  us: self-play converges to a self-consistent but GTOW-distant style (in HU
  theoretically less likely, since two-player zero-sum → self-play convergence toward
  equilibrium plausible; in 6-max WITHOUT guarantee).
- **Gate (doctrine):** paired seed exports → Analyzer μ comparison first ($0), then AIVAT anchor;
  "never ship a regression" against arm A; win rate vs training opponent is FORBIDDEN as a metric
  (that was the −90 mistake) — only external GTOW numbers count.
- **Status: NOT started.** This is a design document; the run needs the user go
  (pod costs) and a free measurement slot in the gate ladder.

## 6. Honest limits

- **Order of magnitude:** Kuhn Poker = 3 cards, 1 bet size, ~dozens of infosets. 6-max NLHE = ~10^160+
  game tree, continuous sizings, multiway, stack depths. That self-play works on Kuhn
  proves NOTHING about the convergence speed or the plateau on NLHE.
- **Different target measure:** SPIRAL optimizes and measures TRANSFER to math benchmarks (+10% MMLU/AIME),
  not poker exploitability or bb/100. A 50% win rate against its own copy says nothing about the
  exploitability by an external near-GTO opponent (GTOW). Their poker strength was never measured against
  a solver.
- **Theory gap for 6-max:** SPIRAL is strictly two-player zero-sum (there self-play has
  equilibrium anchors). 6-max is multiplayer general-sum — no unique CE, self-play can
  run into cycles or pool-specific conventions (our North Star block). The transfer is
  clean for the HU GTOW channel, a hypothesis for 6-max.
- **Compute + plateau:** 8×H100 × 25 h for TINY games; the authors themselves report
  plateau effects with longer training and reward-hacking risk. NLHE self-play will be more expensive per
  bit of information.
- **Small absolute lifts on strong models:** R1-Distill +1.4, Llama-Instruct +2.0 — the
  +10 headline applies to BASE models with lots of headroom. Our GLM is already SFT'd; realistically
  it is rather the small-lift class.
- **Their Kuhn reward is match-binary** (±1 over 5 rounds), not chip-proportional — for us
  chip EV (bb) is the scoreboard; transferring the binary reward would be an information loss,
  we keep chip EV and adopt only curriculum + RAE + sparsity.
