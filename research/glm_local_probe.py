"""Run the TRAINED GLM-Z1-9B LOCALLY (4-bit on the 12GB 3080 Ti) on postflop spots to SEE its ACTUAL programs +
decisions in the spots where it spews — grounded debugging of the LLM<->engine interface, $0, no pod. Mirrors
_GLMBrain._gen (chat-template + <think>-strip + greedy) but via transformers .generate instead of the vLLM server.
Also shows what the postflop_corset would do to each decision (the engine bound).

Run: python -m research.glm_local_probe [n=8]
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("HF_HUB_OFFLINE", "1")                  # the GLM base is cached -> never reach out

import torch                                                  # noqa: E402
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig  # noqa: E402
from peft import PeftModel                                    # noqa: E402

from pokerbot.brain import api, modes                         # noqa: E402
from pokerbot.brain.policy import build_messages, extract_program, parse_completion  # noqa: E402
from pokerbot.strategy import postflop_corset                 # noqa: E402
from dataset.build import from_hu_postflop                    # noqa: E402

BASE = os.environ.get("GLM_BASE", "THUDM/GLM-Z1-9B-0414")
ADAPTER = os.environ.get("GLM_ADAPTER", "models/qwen_poker_lora")


def load():
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                             bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(BASE, quantization_config=bnb, device_map="cuda",
                                                 trust_remote_code=True)
    model = PeftModel.from_pretrained(model, ADAPTER)
    model.eval()
    return tok, model


def gen(tok, model, spot) -> str:
    prompt = tok.apply_chat_template(build_messages(spot), tokenize=False, add_generation_prompt=True)
    i = prompt.rfind("<think>")                               # SFT-aligned: strip the forced <think> (program-only)
    if i != -1:
        prompt = prompt[:i]
    ids = tok(prompt, return_tensors="pt").to(model.device)
    with torch.no_grad():
        out = model.generate(**ids, max_new_tokens=modes.current().max_new_tokens, do_sample=False,
                             pad_token_id=tok.eos_token_id)
    return tok.decode(out[0][ids["input_ids"].shape[1]:], skip_special_tokens=True)


def _decide(tok, model, spot):
    raw = gen(tok, model, spot)
    r = parse_completion(raw, spot, timeout_s=modes.current().time_budget_s)
    return f"{r.get('action')} {r.get('amount') or ''}".strip(), r.get("ok"), extract_program(raw)[:140]


def main():
    """A/B the LLM<->engine hand-read WIRING: each spot decided twice (format_spot.INCLUDE_MADE_HAND OFF then ON).
    Selection is biased to STRONG made hands (where a NL misread-down loses value) + WEAK controls (the ON line must
    not turn a correct fold into a spew). Run: python -m research.glm_local_probe"""
    modes.set_mode("standard")
    from pokerbot.brain import format_spot as _fs
    tok, model = load()
    print(f"GLM loaded 4-bit on {torch.cuda.get_device_name(0)} | VRAM used GB "
          f"{round(torch.cuda.memory_allocated() / 1e9, 1)}", flush=True)
    import random as _r
    pool = list(from_hu_postflop.build(n_per_line=150))
    _r.Random(7).shuffle(pool)
    want = {("strong", True): 2, ("strong", False): 2, ("mid", False): 1, ("weak", True): 1, ("weak", False): 1}
    seen, spots = {}, []
    for s in pool:
        eq = float(api.equity(s.hero_hole, api.range_top(0.5), s.board, iters=300))   # draw-aware strength proxy
        bucket = "strong" if eq > 0.58 else ("mid" if eq > 0.40 else "weak")
        key = (bucket, s.to_call > 0)
        if seen.get(key, 0) < want.get(key, 0):
            seen[key] = seen.get(key, 0) + 1
            spots.append((bucket, eq, s))
        if len(spots) >= sum(want.values()):
            break

    changed = 0
    for bucket, eq, spot in spots:
        cat, strength = api.hand_rank(spot.hero_hole, spot.board)
        face = "facing-bet" if spot.to_call > 0 else "checked-to"
        _fs.INCLUDE_MADE_HAND = False
        d0, ok0, p0 = _decide(tok, model, spot)
        _fs.INCLUDE_MADE_HAND = True
        d1, ok1, p1 = _decide(tok, model, spot)
        _fs.INCLUDE_MADE_HAND = False
        diff = d0.split()[0] != d1.split()[0]
        changed += diff
        print(f"\n--- [{bucket} eq={eq:.2f} {face}] {spot.street} {spot.hero_hole} board={spot.board} "
              f"to_call={spot.to_call} | ENGINE={cat}({strength:.2f})", flush=True)
        print(f"  OFF: {d0:13} ok={ok0} | {p0!r}", flush=True)
        print(f"  ON : {d1:13} ok={ok1}{'   <<< CHANGED' if diff else ''} | {p1!r}", flush=True)
    print(f"\nA/B done | {len(spots)} spots | decision changed on {changed}", flush=True)


if __name__ == "__main__":
    main()
