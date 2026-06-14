"""Evaluate the fine-tuned Qwen LoRA vs the base model on held-out PokerBench — prove the decision gain
before wiring it into the bot. Loads the base in 4-bit (fits the 12 GB RTX 3080 Ti), evaluates base, then
attaches the LoRA adapter and evaluates again, on the SAME held-out spots. Metric = decision match:
does the model's chosen action match PokerBench's GTO action (lenient: first action keyword).

Run: python -m extraction.qwen_eval [N]
"""
from __future__ import annotations

import re
import sys

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

from extraction.qwen_sft import load_pokerbench

BASE = "Qwen/Qwen3-8B"
ADAPTER = r"C:\Users\hampe\Desktop\PokerB\models\qwen_poker_ckpt500"
N = int(sys.argv[1]) if len(sys.argv) > 1 else 120
_ACTS = ["fold", "check", "call", "bet", "raise", "all-in", "allin"]


def _action(text: str) -> str:
    t = (text or "").lower()
    for a in _ACTS:
        if a in t:
            return "allin" if a in ("all-in", "allin") else a
    m = re.search(r"[a-z]+", t)
    return m.group(0) if m else ""


def _heldout(n):
    ds = load_pokerbench()
    cols = ds.column_names
    ins = "instruction" if "instruction" in cols else cols[0]
    out = "output" if "output" in cols else cols[-1]
    ds = ds.shuffle(seed=12345).select(range(n))      # a slice independent of the (seed=0) training shuffle
    return [(str(r[ins]), str(r[out])) for r in ds]


def _gen(model, tok, prompt):
    msgs = [{"role": "user", "content": prompt}]
    ids = tok.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt").to(model.device)
    with torch.no_grad():
        out = model.generate(ids, max_new_tokens=64, do_sample=False,
                             pad_token_id=tok.pad_token_id or tok.eos_token_id)
    return tok.decode(out[0][ids.shape[1]:], skip_special_tokens=True)


def _score(model, tok, data, label):
    hit = 0
    for i, (q, gold) in enumerate(data):
        pred = _action(_gen(model, tok, q))
        if pred and pred == _action(gold):
            hit += 1
        if (i + 1) % 40 == 0:
            print(f"  [{label}] {i+1}/{len(data)} running acc {hit/(i+1):.1%}", flush=True)
    acc = hit / len(data)
    print(f"== {label}: decision-match {acc:.1%} ({hit}/{len(data)}) ==", flush=True)
    return acc


def main():
    data = _heldout(N)
    print(f"held-out: {len(data)} PokerBench spots\n", flush=True)
    tok = AutoTokenizer.from_pretrained(BASE)
    qcfg = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16,
                              bnb_4bit_quant_type="nf4")
    print("loading base (4-bit)...", flush=True)
    base = AutoModelForCausalLM.from_pretrained(BASE, quantization_config=qcfg, device_map="cuda")
    base.eval()
    base_acc = _score(base, tok, data, "BASE")
    print("attaching LoRA adapter...", flush=True)
    lora = PeftModel.from_pretrained(base, ADAPTER)
    lora.eval()
    lora_acc = _score(lora, tok, data, "LoRA")
    print(f"\nRESULT: base {base_acc:.1%} -> LoRA {lora_acc:.1%}  (delta {lora_acc-base_acc:+.1%})")


if __name__ == "__main__":
    main()
