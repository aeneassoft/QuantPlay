# Architecture: GTO floor (Deep-CFR net) + LLM strategist + verify/gate bridge

> The design for fusing the **Poker LLM** (Qwen LoRA, fine-tuned on PokerBench) with the **DeepMind-style
> Deep-CFR net** into one bot. Companion to [STATE.md](STATE.md). Written 2026-06-14.

## The core problem this solves
Our honest weakness: we are a strong **exploiter without a GTO floor** — vs near-GTO Slumbot the heuristic
loses (~−170 bb/100); that −deficit *is our own exploitability*. Pure GTO bots (Slumbot, Libratus) have the
opposite gap: they don't **adapt/exploit**. The winning architecture has **both**: an un-exploitable floor
*and* a verified adaptive exploit layer on top. The LLM and the Deep-CFR net are the two halves.

## Two systems, two timescales (the AlphaZero analogy, made precise)
| | Deep-CFR net | Poker LLM (Qwen) |
|---|---|---|
| Role | **GTO floor** (near-Nash policy) | **Strategist** (exploit reasoning, coaching, curriculum) |
| Timescale | per-hand, ~ms | per-opponent / per-session, async (seconds) |
| AlphaZero analog | the **policy net** (fast prior) | the **search/deliberation** — but over OPPONENT-space (level-k ToM), not the game tree |
| Output | action distribution per infoset | bounded, structured exploit **proposals** (JSON) |
| Never | reasons about a specific opponent | sets an action directly / runs per hand (too slow, ungrounded) |

In poker the real-time game-tree search of AlphaZero is replaced by **opponent-model reasoning**: the LLM
deliberates about *who the opponent is and how they deviate from GTO*; the "value function" that checks its
ideas is the **solver + benchmark + calibration loop**, not game rollouts.

## The bridge: propose → verify → gate → apply (the heart of it)
1. **Floor** — Deep-CFR net gives the base action distribution `π_GTO(infoset)` (un-exploitable prior).
2. **Propose** — the LLM reads `OpponentProfile.summary()` + recent hands → emits a **bounded** exploit
   directive (`propose_exploit`: target spot, action, `freq_delta ∈ [−0.3, 0.3]`, confidence). The
   pre-generated **playbook** (`knowledge_base/exploit/playbook*.jsonl`) is the **cold-start** prior for
   opponents we haven't profiled live yet (nearest-profile lookup).
3. **Verify (math disposes)** — the solver/benchmark checks the proposed deviation against an
   **exploitability budget** (does this exploit lose more vs a GTO opponent than it gains? → reject); the
   **calibration loop** ([calibration.py](../pokerbot/strategy/calibration.py)) checks it against observed
   outcomes (are folds actually as frequent as predicted?).
4. **Gate** — apply only when cross-confirmed: the **two-model gate** (fold-curve ⊕ aggression agree) AND
   calibration confidence are high enough. Otherwise → play the floor.
5. **Apply** — final policy = `π_GTO ⊕ bounded_verified_overlay`. The deviation is capped, so even if the LLM
   is wrong, worst-case exploitability stays near the floor + the probe risk-budget. **The floor is never
   compromised.**

## Five principles for "perfect" fusion
1. **Floor never compromised** — overlay is bounded + budgeted; you cannot lose more than the budget.
2. **Right tool, right timescale** — net per-hand (ms); LLM per-session (async). Never call the LLM per hand.
3. **Language proposes, math disposes** — the LLM never sets actions; only hypotheses the solver/benchmark/
   calibration verify (grounding — hallucination can't reach the felt).
4. **Closed loop** — calibration feeds the LLM its own accuracy ("you over-estimated folds by X") → better
   next proposals (the Mycelium learning-engine pattern, now between LLM and reality).
5. **Two touchpoints** — the LLM also touches the net at **training time** as the **curriculum director**
   (which spots Deep-CFR / the solver should spend compute on — the `pod_run30` director) — not just at play.

## Concrete wiring (what to build, in order)
1. **`pokerbot/strategy/cfr_policy.py`** (NEW) — load the trained Deep-CFR net; `policy(infoset) -> probs`.
   Becomes `AdaptiveExploiter.base` (replacing / blending with the analytic `gto_baseline`). = the floor.
2. **Playbook → adaptive overlay** — nearest-profile lookup over `playbook*.jsonl`, applied as the
   cold-start overlay in [adaptive.py](../pokerbot/strategy/adaptive.py) (bounded + gated; reuses existing
   `_pending`/two-model-gate/calibration machinery).
3. **Serve Qwen via vLLM** → `meta_coach(provider="openai", base_url=…)`; run async per session to refine
   the overlay from live reads. → [meta_coach.py](../pokerbot/coach/meta_coach.py)
4. **Verify hook** — `gto_benchmark`/`gto_oracle` scores each directive's exploitability cost;
   `translate.directive_to_change` → clamped param delta. Reject over-budget deviations.
5. **Calibration everywhere** — extend the loop (now in HU adaptive) to 6-max; feed its summary back to the
   LLM for periodic refinement.

## Why this beats imitating any single bot
Slumbot/Pluribus/GTO-Wizard are each an exploitable GTO *approximation*; imitating one is a ceiling. This
design keeps a GTO floor (so we stop bleeding to near-GTO opponents) AND adds a **verified, self-correcting**
exploit layer that GTO bots structurally lack — built to beat opponents we haven't seen, safely.
