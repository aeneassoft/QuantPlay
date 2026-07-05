"""Parallel frontier consult for the RL run (user directive): OpenAI = RL KNOWLEDGE (what makes our poker GRPO actually
LIFT bb/100 above SFT), Claude = TECHNICAL IMPLEMENTATION in OUR build (GLM-Z1-9B wiring + RTX PRO 6000 local-train +
qwen_grpo). Saves docs/rl_consult_openai.md + docs/rl_consult_claude.md. Frontier = a GATED PRIOR — verify before applying.
Run:  python -m research.rl_consult
"""
from __future__ import annotations

import json
from pathlib import Path

from research.llm import ask_claude, openai_json

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    try:
        return (ROOT / rel).read_text(encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        return f"(missing: {e})"


BRIEF = """GOAL: RL a **GLM-Z1-9B** (THUDM, reasoning-tuned, MIT) poker brain to LIFT realized bb/100 ABOVE its SFT
init — the lift has NEVER yet worked for us (prior GRPO runs either didn't learn [R_BAD=-30 swamped the EV signal,
now fixed to -3] or died on RunPod infra timeouts). The brain drives our engine via program-of-thought DSL
(api.* calls -> executor -> exact legal action); reward = engine REALIZED EV via self-play (verifiable, no reward
model). SFT spine = PokerBench 560k (we hit 71.7% action-acc) + our solver/self-play/Claude-teacher gold.
COMPUTE UPDATE: training now runs LOCALLY on an **RTX PRO 6000 (Blackwell, 96 GB VRAM)** — so NO RunPod (kills the
infra-fragility that broke prior runs); caveat: Blackwell needs a cu128 torch for real kernel throughput (the B200
lesson). A $50 RunPod pod is only a fallback. Honest ceiling: nobody beats GTO Wizard (best -3.14); a 9B won't match
Claude's measured -28; value = OURS + RL-able + improvable."""


def _oai_obj(props):
    return {"type": "object", "additionalProperties": False, "properties": props, "required": list(props)}


def main() -> None:
    context = (BRIEF
               + "\n\n=== docs/RL_RUNCARD.md (our consolidated run-card) ===\n" + _read("docs/RL_RUNCARD.md")
               + "\n\n=== training/qwen_grpo.py (the actual DAPO/GRPO trainer) ===\n" + _read("training/qwen_grpo.py"))

    # ---- OpenAI: RL KNOWLEDGE ----
    oai_sys = ("You are a top expert in RL for LLMs (RLVR / GRPO / DAPO / PPO) AND poker AI. Be concrete, skeptical, and "
               "mechanism-level. Do NOT flatter. Your job: maximize the probability our RL run actually LIFTS bb/100 "
               "above the SFT init, and name what is most likely to make it FAIL + the fix.")
    oai_schema = _oai_obj({
        "reward_design": {"type": "string"},
        "dynamic_sampling_and_variance": {"type": "string"},
        "entropy_collapse_and_kl": {"type": "string"},
        "glm_z1_reasoning_model_rl_specifics": {"type": "string"},
        "sft_to_rl_handoff": {"type": "string"},
        "most_likely_failure_and_fix": {"type": "string"},
        "top_5_actions": {"type": "array", "items": {"type": "string"}},
    })
    oai_user = ("Give the RL KNOWLEDGE that most increases P(the lift happens) for THIS setup:\n" + context)
    print("consulting OpenAI (RL knowledge) ...", flush=True)
    oai, oai_use = openai_json(oai_sys, oai_user, oai_schema, "rl_knowledge", max_tokens=9000)
    (ROOT / "docs" / "rl_consult_openai.md").write_text(
        "# RL consult — OpenAI (RL knowledge)\n\n" + "\n\n".join(
            f"## {k}\n{v if not isinstance(v, list) else chr(10).join('- ' + str(x) for x in v)}"
            for k, v in oai.items()), encoding="utf-8")
    print(f"  OpenAI done (tokens {oai_use}) -> docs/rl_consult_openai.md", flush=True)

    # ---- Claude: TECHNICAL IMPLEMENTATION IN OUR BUILD ----
    cl_sys = ("You are a senior ML engineer giving a CONCRETE, file-level technical implementation plan for THIS exact "
              "codebase. No fluff, no generic advice — specific changes (file:function), with the GLM-Z1 + RTX-PRO-6000 "
              "specifics. Flag anything in the shown code that will break the lift.")
    cl_user = ("Implement the RL run in OUR build. Deliver: (1) GLM-Z1-9B wiring into training/qwen_sft.py + "
               "training/qwen_grpo.py (GLM chat template, BOUNDED thinking [GLM-Z1 reasons then emits the DSL program; "
               "extract_program strips <think>; cap so think doesn't fill max_completion_length], tokenizer, the vLLM "
               "structured-output regex); (2) the exact SFT + GRPO config for LOCAL training on an RTX PRO 6000 "
               "(Blackwell sm_120, 96 GB, cu128 torch) — sizes, QLoRA vs bf16, vllm_gpu_memory_utilization, batch; "
               "(3) the de-risk ladder adapted to LOCAL (no SSH/scp/watchdog — what replaces them); (4) the precise code "
               "changes to make the RL actually LIFT. Be specific to the files shown.\n\n" + context)
    print("consulting Claude (technical implementation) ...", flush=True)
    cl_text, cl_use = ask_claude(cl_sys, cl_user, thinking=True, max_tokens=10000)
    (ROOT / "docs" / "rl_consult_claude.md").write_text(
        "# RL consult — Claude (technical implementation in our build)\n\n" + cl_text, encoding="utf-8")
    print(f"  Claude done (tokens {cl_use}) -> docs/rl_consult_claude.md", flush=True)
    print("CONSULTS COMPLETE.", flush=True)


if __name__ == "__main__":
    main()
