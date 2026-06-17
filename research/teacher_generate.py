"""TEACHER generation — a frontier-scale Qwen (Qwen3-235B-A22B on the B300) DRIVES our DSL over thousands of spots via
vLLM batched inference; each emitted program-of-thought is engine-GATED (grammar-valid + executes to a legal action),
then saved as distillation candidates. The big model is a TEACHER, not the deployment model: its gated output is the
warm-start corpus we SFT-distil into the 8B (CLAUDE.md: SFT/distillation = warm-start; the engine is TRUTH, the
frontier a GATED PRIOR). The heavier EV-truth gate (pipeline/filter.EVFilter) runs on the PC after the pull — so the
pod stays a fast, robust GENERATOR (the 2-node split: frontier feeds the PC's dataset, EV-gated there).

Full B300 utilization = the 235B (fp8) resident in vRAM + vLLM high-throughput batched generation saturating compute.

Run (pod): BASE=Qwen/Qwen3-235B-A22B-Instruct-2507-FP8 N=8000 OUT=/root/teacher_raw.jsonl python3 -u -m research.teacher_generate
"""
from __future__ import annotations

import json
import os
import time

from pokerbot.brain import modes
from pokerbot.brain.dsl_grammar import matches
from pokerbot.brain.executor import run_program
from pokerbot.brain.format_spot import format_spot
from pokerbot.brain.policy import build_messages, extract_program
from dataset.schema import make_example
from training.rl_env import TRAIN_LEAGUE, gen_decision_states

BASE = os.environ.get("BASE", "Qwen/Qwen3-235B-A22B-Instruct-2507-FP8")
N = int(os.environ.get("N", "8000"))
OUT = os.environ.get("OUT", "/root/teacher_raw.jsonl")
SEED = int(os.environ.get("SEED", "0"))
TEMP = float(os.environ.get("GEN_TEMP", "0.7"))        # diversity -> varied mixed strategies (the engine gate filters junk).
#                                                        NOT "TEMP" (collides with the Windows %TEMP% path env var)
MAXTOK = int(os.environ.get("MAXTOK", "320"))
VLLM_MEM = float(os.environ.get("VLLM_MEM", "0.90"))   # fill the GPU vRAM (235B fp8 ~235GB + KV cache)
TP = int(os.environ.get("TP", "1"))                    # vLLM tensor-parallel size (2 -> split the 235B across 2x H200)
MAXLEN = int(os.environ.get("MAXLEN", "2048"))
WALLCLOCK_S = float(os.environ.get("WALLCLOCK_S", "0"))  # >0 -> stop generating-new-batches past this (budget guarantee)


def build_spots(n: int, seed: int = 0):
    """Diverse 6-max decision spots (the target domain): the rotating-button league self-play covers all positions /
    streets / textures. Returns [(snap, spot)] (snap kept for the optional pod-side EV check; the PC re-gates anyway)."""
    out = []
    for snap, spot in gen_decision_states(profiles=TRAIN_LEAGUE, hero_seat=0, n_states=n, seed=seed):
        out.append((snap, spot))
    return out


def gate_and_rows(spots, completions):
    """Engine-gate each (spot, raw completion): extract the program, require it to grammar-match AND run to a legal
    action. Returns (kept_rows, n_ok, n_total). vLLM-INDEPENDENT -> unit-testable locally with hand-fed completions."""
    rows, ok = [], 0
    for (snap, spot), text in zip(spots, completions):
        prog = extract_program(text or "")
        if not matches(prog):
            continue
        res = run_program(prog, spot, strict=True, seed=0)
        if not res["ok"]:
            continue
        ok += 1
        mix = res.get("mix") or {}
        spot_text = spot if isinstance(spot, str) else format_spot(spot)
        rows.append(make_example(
            "distill", spot_text, prog,
            action={"action": res["action"], "size_bb": res.get("amount_bb")}, type_="decision",
            meta={"teacher": BASE, "mixed": len([v for v in mix.values() if v > 0]) >= 2, "mix": mix}))
    return rows, ok, len(spots)


CHUNK = int(os.environ.get("CHUNK", "1500"))           # spots per generate-batch; wall-clock is checked between chunks


def main():
    from vllm import LLM, SamplingParams
    from transformers import AutoTokenizer
    modes.set_mode("fast")                                          # cheap engine equity in the gate's run_program
    t0 = time.time()
    print(f"TEACHER-GEN model={BASE} N={N} TP={TP} | loading vLLM (vram_util={VLLM_MEM}) ...", flush=True)
    llm = LLM(model=BASE, gpu_memory_utilization=VLLM_MEM, max_model_len=MAXLEN, trust_remote_code=True,
              tensor_parallel_size=TP, enforce_eager=False)
    tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)
    print(f"TEACHER_MODEL_LOADED in {time.time()-t0:.0f}s", flush=True)   # the campaign greps this = the fail-fast marker
    sp_params = SamplingParams(temperature=TEMP, top_p=0.9, max_tokens=MAXTOK, seed=SEED)

    # Chunked generation: stop at N OR the wall-clock budget, whichever first. Incremental append -> a crash still leaves
    # all completed chunks on disk (robust). Each chunk uses a fresh spot seed for diversity.
    open(OUT, "w", encoding="utf-8").close()                        # truncate
    kept = ok_tot = seen = chunk = 0
    deadline = (t0 + WALLCLOCK_S) if WALLCLOCK_S > 0 else None
    while seen < N:
        if deadline and time.time() >= deadline:
            print(f"  wall-clock budget hit -> stop (generated {seen})", flush=True)
            break
        n_this = min(CHUNK, N - seen)
        spots = build_spots(n_this, seed=SEED + chunk * 100003)     # distinct spots per chunk
        prompts = [tok.apply_chat_template(build_messages(sp), tokenize=False, add_generation_prompt=True)
                   for _, sp in spots]
        outs = llm.generate(prompts, sp_params)
        rows, ok, tot = gate_and_rows(spots, [o.outputs[0].text for o in outs])
        with open(OUT, "a", encoding="utf-8") as f:
            for ex in rows:
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")
        kept += len(rows); ok_tot += ok; seen += tot; chunk += 1
        print(f"  chunk {chunk}: +{len(rows)} kept (total {kept}/{seen}, gate-pass {ok_tot/max(1,seen):.0%}) "
              f"| {time.time()-t0:.0f}s elapsed", flush=True)

    dt = time.time() - t0
    print(f"TEACHER_GEN_OK kept={kept}/{seen} (gate-pass {ok_tot/max(1,seen):.0%}) "
          f"-> {OUT} | {dt:.0f}s ({kept/max(1,dt)*60:.0f} rows/min)", flush=True)


if __name__ == "__main__":
    main()
