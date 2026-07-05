"""GTO-anchored held-out EVAL + the GATE ladder — the go/no-go for the RL run (the real GATE 2).

Measures, on a HELD-OUT league (opponent TYPES the policy never trained against), the things that define "robust GTO"
here: realized bb/100 (mixed + per-type), the ROBUSTNESS-SPREAD (worst-case + max−min across types = the empirical
surrogate for strong-robustness-to-incomplete-information), plus PokerBench decision-accuracy (GATE 0) and legality.
The thesis (GATE 2) = the GRPO policy's mixed bb/100 BEATS its own SFT-init.

`league_eval` / `robustness` / `gate_ladder` are MODEL-FREE pure functions over `rl_env.evaluate_policy` (a policy is any
`policy(table, seat)->(action, amount)`), so they're $0-testable with a league-bot stub. `pokerbench_acc` + `main` need a
GPU model (pod). Per docs/QWEN_6MAX_PLAN.md + the CLAUDE.md robustness theory.
"""
from __future__ import annotations

import os

from training.rl_env import HELDOUT_LEAGUE, evaluate_policy


def league_eval(policy, league=HELDOUT_LEAGUE, n_hands: int = 2000, seed: int = 0, hero_seat: int = 0) -> dict:
    """bb/100 vs EACH held-out opponent type (all 5 seats that type) + a MIXED league. Returns per-type, mixed,
    worst-case and spread = the robustness picture."""
    mixed_only = os.environ.get("EVAL_MIXED_ONLY", "0") == "1"   # GATE-2 needs only the MIXED bb/100 -> skip the 5x per-type
    per = {} if mixed_only else {t: evaluate_policy(policy, profiles=(t,), n_hands=n_hands, seed=seed, hero_seat=hero_seat)["bb_per_100"]
                                 for t in league}                # loop (the eval-timeout cause: per-type x mixed x BOTH adapters)
    mixed = evaluate_policy(policy, profiles=tuple(league), n_hands=n_hands, seed=seed + 1,
                            hero_seat=hero_seat)["bb_per_100"]
    vals = list(per.values()) or [mixed]   # mixed-only -> worst/spread fall back to the mixed value (no per-type data)
    return {"per_type": per, "mixed_bb100": mixed, "worst_bb100": min(vals),
            "spread_bb100": round(max(vals) - min(vals), 2)}


def gate_ladder(grpo: dict, sft: dict, pokerbench_acc: float, dsl_emit_rate: float,
                legality: float, lbr_delta: float | None = None) -> dict:
    """Assemble the GATE ladder from the eval metrics + the SFT-init baseline. G2 (RL > SFT-init mixed bb/100) is the
    core thesis test. G5 (trace audit) is manual. PASS = G0..G3 (G4 advisory if LBR unavailable)."""
    g0 = pokerbench_acc >= 0.70 and dsl_emit_rate >= 0.99
    g1 = legality >= 0.99
    g2 = grpo["mixed_bb100"] > sft["mixed_bb100"]
    g3 = grpo["worst_bb100"] >= 0.0
    g4 = (lbr_delta is None) or (lbr_delta <= 0.0)        # exploitability not worse (lower is better)
    return {"G0_pokerbench+dsl": g0, "G1_legality": g1, "G2_rl_beats_sft_init": g2,
            "G3_robust_vs_each_type": g3, "G4_lbr_not_worse": g4,
            "delta_vs_sft_bb100": round(grpo["mixed_bb100"] - sft["mixed_bb100"], 2),
            "PASS": bool(g0 and g1 and g2 and g3)}


def pokerbench_acc(model, tok, n: int = 200) -> tuple[float, float]:
    """GATE 0: decision-match accuracy on held-out PokerBench + the DSL-emit rate (frac of outputs that parse to a
    legal DSL action). Needs the GPU model. Reuses the held-out slice + action keyword match from training/qwen_eval."""
    import re
    from training.qwen_eval import _heldout, _action
    from pokerbot.brain.policy import build_messages, parse_completion
    from pokerbot.brain.format_spot import Spot
    data = _heldout(n)
    hit = emit = 0
    for prompt, gold in data:
        # PokerBench prompts are prose; wrap as a minimal user message (no structured Spot) -> generate -> parse text
        msgs = [{"role": "user", "content": prompt}]
        enc = tok.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt", return_dict=True,
                                      enable_thinking=False)  # non-thinking (see policy.py)
        import torch
        enc = {k: v.to(model.device) for k, v in enc.items()}
        n_in = enc["input_ids"].shape[1]
        with torch.no_grad():
            out = model.generate(**enc, max_new_tokens=256, do_sample=False,
                                 pad_token_id=tok.pad_token_id or tok.eos_token_id)
        text = tok.decode(out[0][n_in:], skip_special_tokens=True)
        m = re.search(r"decide\(\s*['\"]?(fold|check|call|bet|raise|allin|all-in)", text)
        if m:
            emit += 1
            if _action(m.group(1)) == _action(gold):
                hit += 1
        elif _action(text) == _action(gold):
            hit += 1
    return hit / len(data), emit / len(data)


def main():
    """Pod eval: load the SFT-init + the GRPO adapter, run the GTO-anchored eval, print the GATE ladder."""
    import json
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    import torch
    from pokerbot.brain.policy import QwenPolicy

    base = os.environ.get("BASE", "Qwen/Qwen3-8B")
    sft = os.environ.get("SFT", "/root/qwen_poker_lora")
    grpo = os.environ.get("GRPO", "/root/qwen_poker_grpo")
    n_hands = int(os.environ.get("EVAL_HANDS", "2000"))
    tok = AutoTokenizer.from_pretrained(base)
    qc = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.bfloat16)
    bm = AutoModelForCausalLM.from_pretrained(base, quantization_config=qc, device_map="cuda")

    def evL(adapter):
        m = PeftModel.from_pretrained(bm, adapter)
        m.eval()
        pol = QwenPolicy(m, tok, sampling=False)
        res = league_eval(pol, n_hands=n_hands)
        acc, emit = pokerbench_acc(m, tok)
        return res, acc, emit

    sft_res, sft_acc, sft_emit = evL(sft)
    grpo_res, grpo_acc, grpo_emit = evL(grpo)
    ladder = gate_ladder(grpo_res, sft_res, grpo_acc, grpo_emit, legality=grpo_emit)
    result = {"sft": sft_res, "grpo": grpo_res, "grpo_pokerbench_acc": grpo_acc,
              "grpo_dsl_emit": grpo_emit, "gates": ladder}
    out_path = os.environ.get("GATES_OUT", "/root/eval_gates.json")     # pulled by the orchestrator -> the dashboard
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
    except OSError:
        pass
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
