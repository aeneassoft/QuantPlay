"""Consult OpenAI (gpt-5.5, conceptual pipeline + RL) and Claude (Opus 4.8, TECHNICAL details) on the Qwen 6-max
poker-brain training pipeline: PokerBench + our root-folder theory + frontier-distillation + RL/self-play.
Routing per the user: OpenAI = conceptual/RL/ROI ; Claude = the buildable technical details. Writes docs/qwen_train_*.md.
Run: python -m extraction.qwen_train_consult
"""
from __future__ import annotations

from pokerbot import config

OPENAI_MODEL = "gpt-5.5"
CLAUDE_MODEL = config.CLAUDE_MODEL  # claude-opus-4-8

BRIEF = """OUR SITUATION (ground every answer here; concrete + brutally honest; flag overkill + uncertainty):
- We build a 6-MAX (6-handed) No-Limit Hold'em bot. We PIVOTED AWAY from heads-up: HU is where the solver/value-net
  SOTA lives (DeepStack/Libratus/Supremus, all 2-player zero-sum), but 6-max is multiplayer general-sum (Nash
  PPAD-hard, non-unique, CFR->CCE not Nash) -> the "compute near-Nash" paradigm does NOT transfer (Pluribus didn't
  use it). We chose an LLM as the 6-max "brain" (reasoning/adaptation/population-exploitation), NOT a from-scratch net.
- DECISION: fine-tune an OPEN model = QWEN (strong math/reasoning base, fine-tunable). We ALREADY have a Qwen LoRA
  (Qwen3-class, LoRA SFT on PokerBench, step-500, ~71.7% held-out decision-match vs base 18.3%). We want to go FAR
  beyond plain PokerBench SFT.
- TRAIN QWEN ON A MIX: (1) PokerBench (6-max, ~560k solver-derived decision points, instruction->optimal action +
  natural-language prompts); (2) OUR ROOT-FOLDER THEORY, already extracted to JSON/MD: knowledge_base/math (The
  Mathematics of Poker -> formulas.py + math.json), knowledge_base/concepts (5 poker books), knowledge_base/theory
  (16 files: algorithmic game theory, CFR/Deep-CFR papers, exploit<->GTO bridge, syntheses), knowledge_base/exploit
  (11.5k exploit directives + playbooks), knowledge_base/ranges (solved preflop blueprints/tables), knowledge_base/
  hand_histories (10k Pluribus hands + pro histories), knowledge_base/postflop (solver-calibrated frequencies); plus
  raw PDFs (Mathematics of Poker, Algorithmic Game Theory, Beyond GTO, Exploitative Poker). (3) FRONTIER-MODEL
  DISTILLATION, IN THE LOOP: we can call OpenAI (GPT-5.x/o3) and Claude (Opus 4.8) during training to generate
  high-quality poker reasoning / decisions / critiques on-demand (active distillation), not just a one-shot dump.
  (4) RL / SELF-PLAY on top of SFT -- we ACCEPT that SFT alone caps (the PokerBench paper itself warns plain SFT is
  insufficient); reward = realized win-rate/EV in self-play + vs a bot panel.
- INFRA: a RunPod GPU pod for Qwen training; we can ATTACH the frontier APIs to the same run (the pod or an
  orchestrator calls OpenAI/Claude to generate/critique data during training). A Hetzner box is available as a hub but
  probably unnecessary. We have a self-killing RunPod orchestration pattern already.
- EVAL/BENCHMARK: 6-max has NO clean GTO ground-truth. Eval = PokerBench decision-accuracy (cheap dev metric, paper-
  validated to correlate with win-rate) + realized bb/100 vs a diverse 6-max opponent panel (our bots / other LLMs)
  (target metric) + bounded-exploitability (LBR-style). We have a 6-max engine (pokerbot/arena/sixmax.py + a table
  engine with side pots) we can use as the self-play environment.
- HARD-LEARNED LESSON: pure IMITATION caps at the teacher (our HU policy net hit -212 vs GTO Wizard; a solver-
  imitation floor plateaued ~-72). So distillation/SFT must be a WARM-START that RL/self-play LIFTS above the teacher
  -- never the final policy. Frontier LLMs are only -10 to -30 bb/100 vs GTO Wizard in HU, so distilling them blindly
  also imports their mistakes."""

OPENAI_SYSTEM = ("You are a world-class LLM post-training + RL researcher (SFT, RLHF, GRPO/PPO, self-play, "
                 "knowledge distillation) who also deeply understands poker/GTO. Be concrete, quantify, distinguish "
                 "what reliably helps from hype, and flag overkill. Serve THIS project + its measured lessons.")

OPENAI_Q = BRIEF + """

DESIGN THE FULL PIPELINE CONCEPTUALLY + THE RL RECIPE. Answer each, concretely:
1. STAGED CURRICULUM: the exact stages and WHY that order (continued-pretraining on theory? SFT on PokerBench +
   distilled chain-of-thought? preference/DPO? RL/self-play?). Map each data source to its stage (math/theory books ->
   ?; PokerBench -> ?; frontier-distilled reasoning -> ?; hand-histories -> ?).
2. DATA-MIX + ANTI-MEMORIZATION: how to convert each root-folder source into training examples (instruction / CoT /
   preference), mixing ratios (theory vs decision data), and how to prevent rote memorization + test-set leakage.
3. FRONTIER-IN-THE-LOOP (active distillation): what EXACTLY should OpenAI/Claude produce during training (CoT
   rationales for PokerBench spots? critiques of Qwen outputs? labels for novel/self-play spots? reward signals?), how
   to gate their quality, and how to AVOID distilling their poker mistakes. Is on-demand active generation (targeting
   Qwen's weak spots) worth the complexity over a one-shot bulk distill?
4. RL / SELF-PLAY for a 6-max poker LLM: GRPO vs PPO vs DPO vs expert-iteration -- pick one and justify. The reward
   (win-rate vs panel? EV vs a reference? learned reward?), the sparse-reward credit-assignment over many per-hand
   decisions, and how to keep self-play from collapsing / chasing its own exploits in a multiplayer game.
5. ROI + RISKS: does this realistically beat just prompting Opus 4.8 as the brain? The biggest risks, and the
   CHEAPEST experiment that de-risks the whole plan before the full RunPod spend."""

CLAUDE_SYSTEM = ("You are the implementation lead / staff ML engineer who has shipped LLM fine-tuning + RL pipelines "
                 "(TRL/verl/Axolotl/Unsloth/OpenRLHF) and data pipelines at scale. Give SPECIFIC, buildable technical "
                 "detail: libraries, configs, data schemas, orchestration topologies. Honest about cost + failure modes.")

CLAUDE_Q = BRIEF + """

GIVE THE TECHNICAL DETAILS TO ACTUALLY BUILD THIS (be specific -- libraries, configs, formats, topology):
1. TRAINING STACK: which Qwen3 size for a single RunPod GPU (and which GPU)? LoRA/QLoRA vs full FT? The SFT->RL stages
   with concrete libraries + the RL algorithm config (e.g. GRPO group size, KL coef, lr, batch, seq len) for a poker
   reasoning model. Rule-based reward vs reward model.
2. DATA PIPELINE: the exact transformation from our extracted JSON (knowledge_base/math/math.json, concepts.jsonl,
   theory/*.json, exploit/playbook.jsonl, hand_histories) + the PDFs into JSONL training examples -- the chat/CoT
   schema, dedup, DECONTAMINATION vs the PokerBench test set, train/val split. Give the CANONICAL prompt format for a
   poker spot (hole cards, board, positions UTG..BB, action history, stacks, pot) so SFT matches live inference.
3. FRONTIER-API-IN-THE-LOOP: the concrete architecture to run frontier distillation DURING a RunPod training run --
   async generation workers calling OpenAI/Claude, queue/cache, rate-limit + cost control, dedup, quality gates;
   offline buffer vs online interleave. Should the POD call the APIs directly or a separate orchestrator feed a
   dataset the pod consumes? Give the cleanest topology + a rough cost model.
4. SELF-PLAY HARNESS: how to wire our existing 6-max engine (pokerbot/arena/sixmax.py + the N-player table engine) as
   the RL environment for the Qwen agent -- action parsing, legal-move masking, per-hand reward extraction, and
   batching many parallel tables for throughput.
5. EVAL + GATES + ORCHESTRATION: the eval harness (PokerBench accuracy + bb/100 vs a panel), checkpoint selection, and
   the one self-killing RunPod run (data-prep -> SFT -> RL -> eval -> pull, APIs attached). Concrete go/no-go gates."""


def ask_openai(model, system, user, cap=42000):
    from openai import OpenAI
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    for kw in ({"reasoning_effort": "high", "max_completion_tokens": cap},
               {"reasoning_effort": "medium", "max_completion_tokens": cap}, {"max_completion_tokens": cap}, {}):
        try:
            r = client.chat.completions.create(model=model, messages=msgs, **kw)
            txt = r.choices[0].message.content or ""
            if txt.strip():
                return txt
            print(f"  ({model} empty, finish={r.choices[0].finish_reason})", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"  ({model} err {list(kw)}: {type(e).__name__}: {str(e)[:140]})", flush=True)
    return ""


def ask_claude(model, system, user, cap=16000):
    import anthropic
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    try:
        m = client.messages.create(model=model, max_tokens=cap, system=system,
                                   messages=[{"role": "user", "content": user}])
        return "".join(b.text for b in m.content if b.type == "text")
    except Exception as e:  # noqa: BLE001
        print(f"  (claude err: {type(e).__name__}: {str(e)[:140]})", flush=True)
        return ""


def main():
    out = config.ROOT / "docs"
    out.mkdir(exist_ok=True)
    print(f"=== {OPENAI_MODEL} (conceptual pipeline + RL + ROI) ...", flush=True)
    o = ask_openai(OPENAI_MODEL, OPENAI_SYSTEM, OPENAI_Q)
    (out / "consults" / "qwen_train_gpt55.md").write_text(f"# Qwen 6-max training pipeline — conceptual+RL ({OPENAI_MODEL})\n\n{o}\n", encoding="utf-8")
    print(f"  saved docs/consults/qwen_train_gpt55.md ({len(o)} chars)", flush=True)
    print(f"=== {CLAUDE_MODEL} (TECHNICAL: stack, data pipeline, APIs-in-loop, self-play, gates) ...", flush=True)
    c = ask_claude(CLAUDE_MODEL, CLAUDE_SYSTEM, CLAUDE_Q)
    (out / "consults" / "qwen_train_claude.md").write_text(f"# Qwen 6-max training pipeline — technical ({CLAUDE_MODEL})\n\n{c}\n", encoding="utf-8")
    print(f"  saved docs/consults/qwen_train_claude.md ({len(c)} chars)", flush=True)
    print("DONE — both saved to docs/. Synthesize into a conceptual design + a data-prep + APIs-in-loop plan.", flush=True)


if __name__ == "__main__":
    main()
