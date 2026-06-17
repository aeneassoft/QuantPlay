"""RunPod SERVERLESS teacher worker (deployed from GitHub). The frontier Qwen (set via MODEL_NAME at deploy time)
GENERATES DSL programs over poker spots and engine-GATES them (grammar-valid + executes to a legal action) right on the
worker — then returns the gated gold. The PC client triggers jobs + does the heavier EV-truth gate + saves (CLAUDE.md:
frontier feeds the PC's dataset, engine is truth). Built on the official vLLM image so the env is RunPod-managed/tested
(no PEP668 / torch-ABI / tokenizer / hf_transfer build hell — the 5 pod-setup failures' root cause is gone).

Cold start loads vLLM ONCE (module level) → warm invocations reuse it. One job = {"input": {"n", "seed", "temperature",
"max_tokens"}} → {"examples":[gated rows], "kept", "total", "model"}.
"""
from __future__ import annotations

import os

import runpod
from transformers import AutoTokenizer
from vllm import LLM, SamplingParams

from pokerbot.brain import modes
from pokerbot.brain.policy import build_messages
from research.teacher_generate import build_spots, gate_and_rows   # reuse the EXACT, locally-verified gate

MODEL = os.environ.get("MODEL_NAME", "Qwen/Qwen3-32B-FP8")          # set at deploy time (32B-FP8 robust; 80B-Next bigger)
TP = int(os.environ.get("TP", "1"))
VLLM_MEM = float(os.environ.get("VLLM_MEM", "0.90"))
MAXLEN = int(os.environ.get("MAXLEN", "2048"))

modes.set_mode("fast")                                              # cheap engine equity in the gate's run_program
print(f"[handler] cold start: loading {MODEL} (TP={TP}, vram={VLLM_MEM}) ...", flush=True)
_llm = LLM(model=MODEL, tensor_parallel_size=TP, gpu_memory_utilization=VLLM_MEM,
           max_model_len=MAXLEN, trust_remote_code=True)
_tok = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True)
print(f"[handler] model loaded — ready.", flush=True)


def handler(job):
    inp = (job or {}).get("input", {}) or {}
    n = int(inp.get("n", 500))
    seed = int(inp.get("seed", 0))
    temp = float(inp.get("temperature", 0.7))
    maxtok = int(inp.get("max_tokens", 320))
    spots = build_spots(n, seed=seed)
    prompts = [_tok.apply_chat_template(build_messages(sp), tokenize=False, add_generation_prompt=True)
               for _, sp in spots]
    outs = _llm.generate(prompts, SamplingParams(temperature=temp, top_p=0.9, max_tokens=maxtok, seed=seed))
    rows, ok, tot = gate_and_rows(spots, [o.outputs[0].text for o in outs])
    return {"examples": rows, "kept": len(rows), "total": tot, "gate_pass": round(ok / max(1, tot), 3), "model": MODEL}


runpod.serverless.start({"handler": handler})
