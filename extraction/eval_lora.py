"""Held-out eval of the PokerBench LoRA: action-match % vs GTO on UNSEEN rows. Training used
shuffle(seed=0).select(range(25000)); we eval on the NEXT rows (same loader+shuffle => disjoint, true
held-out). Grounded 'did the 32B actually learn GTO' test, not just train-loss. Runs on the pod.
"""
import os
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
from qwen_sft import load_pokerbench, BASE   # reuse loader -> identical shuffle ordering -> clean held-out

LORA = "/root/qwen_poker_lora"
N = int(os.environ.get("EVALN", "60"))
SKIP = int(os.environ.get("EVALSKIP", "25000"))
ACTIONS = ["fold", "check", "call", "bet", "raise", "allin"]


def find_action(s: str) -> str:
    s = s.lower().replace(",", " ").replace(".", " ")
    for w in s.split():
        for a in ACTIONS:
            if w.startswith(a):
                return a
    return ""


def main():
    tok = AutoTokenizer.from_pretrained(BASE)
    model = AutoModelForCausalLM.from_pretrained(BASE, torch_dtype=torch.bfloat16, device_map="cuda",
                                                 attn_implementation="sdpa")
    model = PeftModel.from_pretrained(model, LORA)
    model.eval()
    ds = load_pokerbench().shuffle(seed=0)
    cols = ds.column_names
    ins = "instruction" if "instruction" in cols else cols[0]
    outc = "output" if "output" in cols else cols[-1]
    held = ds.select(range(SKIP, SKIP + N))
    m = e = t = 0
    for i, ex in enumerate(held):
        try:
            instr, gold = str(ex[ins]), str(ex[outc])
            try:                                            # Qwen3 emits <think> by default -> kill it
                prompt = tok.apply_chat_template([{"role": "user", "content": instr}], tokenize=False,
                                                 add_generation_prompt=True, enable_thinking=False)
            except TypeError:
                prompt = tok.apply_chat_template([{"role": "user", "content": instr}], tokenize=False,
                                                 add_generation_prompt=True)
            ids = tok(prompt, return_tensors="pt").to("cuda")
            with torch.no_grad():
                o = model.generate(**ids, max_new_tokens=24, do_sample=False,
                                   pad_token_id=(tok.pad_token_id or tok.eos_token_id))
            gen = tok.decode(o[0][ids.input_ids.shape[1]:], skip_special_tokens=True).strip()
            t += 1
            if i < 5:
                print(f"[ex{i}] GEN={gen!r} | GOLD={gold!r}", flush=True)
            ga, gg = find_action(gen), find_action(gold)
            if gg and ga == gg:
                m += 1
            if gen.lower().split()[:2] == gold.lower().split()[:2]:
                e += 1
        except Exception as ex2:  # noqa: BLE001
            print("row err:", ex2, flush=True)
    print(f"EVAL_DONE action_match={100*m/max(1,t):.1f}% exact_match={100*e/max(1,t):.1f}% n={t}", flush=True)


if __name__ == "__main__":
    main()
