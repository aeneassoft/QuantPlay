"""Fine-tune Qwen (LoRA) on the public PokerBench GTO dataset (RZ412/PokerBench) — a real poker LLM that
saturates the GPU steadily. This is the strategic/language layer (exploit hypotheses, coaching, curriculum
direction) on top of the DeepMind net. Run on the pod (GPU): python -u -m training.qwen_sft
Env: BASE (default Qwen/Qwen3-8B), MAXN (cap train rows), EPOCHS, DSL (comma-sep DSL jsonl shards to MIX IN —
our self-growing dataset/shards in the canonical spot->completion format, byte-identical to inference).
"""
from __future__ import annotations

import os

import torch
from datasets import concatenate_datasets, get_dataset_config_names, load_dataset
from peft import LoraConfig
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from trl import SFTConfig, SFTTrainer

BASE = os.environ.get("BASE", "Qwen/Qwen3-8B")
MAXN = int(os.environ.get("MAXN", "60000"))
EPOCHS = float(os.environ.get("EPOCHS", "1"))
BATCH = int(os.environ.get("BATCH", "16"))      # bigger batch -> more GPU util (B200 has headroom)
QUANT4 = os.environ.get("QUANT4", "0") == "1"   # 4-bit QLoRA for consumer GPUs (e.g. a 24GB RTX 3090)
ATTN = os.environ.get("ATTN", "sdpa")           # sdpa = torch's flash kernel on Hopper/Ampere (fast); B200 sm_100 lacked it
DSL = os.environ.get("DSL", "")                  # comma-sep DSL jsonl shards (our gold) to mix with PokerBench; "" = none
SKIP_PB = os.environ.get("SKIP_PB", "0") == "1"  # train on the DSL shards ONLY (skip the 560k PokerBench HF download — local)
OUT = os.environ.get("OUT", "/root/qwen_poker_lora")
CURRICULUM = os.environ.get("CURRICULUM", "0") == "1"   # load DSL shards IN ORDER (a->d) + replay, NO global shuffle (docs/llm_curriculum.md)
REPLAY = float(os.environ.get("REPLAY", "0.15"))        # fraction of prior-phase rows replayed before each later phase (anti-forgetting)
PACKING = os.environ.get("PACKING", "0") == "1"         # OFF by default -> clean per-example completion-only masking
ASSIST_ONLY = os.environ.get("ASSIST_ONLY", "1") == "1" # completion-only loss (mask the prompt, train on the program) = THE frac_bad fix


def load_pokerbench():
    name = "RZ412/PokerBench"
    try:
        cfgs = get_dataset_config_names(name)
    except Exception:  # noqa: BLE001
        cfgs = []
    parts = []
    for c in (cfgs or [None]):
        d = load_dataset(name, c) if c else load_dataset(name)
        for sp in d:
            if "train" in sp.lower():
                parts.append(d[sp])
    return concatenate_datasets(parts) if len(parts) > 1 else parts[0]


def load_dsl(paths: str):
    """Load our DSL shards (spot->completion JSONL) into the SAME {messages:[user,assistant]} format = the canonical,
    inference-identical chat form (docs/DATASET_SPEC.md). Returns a Dataset (or None if no rows)."""
    import json
    from datasets import Dataset
    rows = []
    for p in [x.strip() for x in paths.split(",") if x.strip()]:
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                ex = json.loads(line)
                rows.append({"messages": [{"role": "user", "content": str(ex["spot"])},
                                          {"role": "assistant", "content": str(ex["completion"])}]})
    return Dataset.from_list(rows) if rows else None


def _rows_for(path: str) -> list:
    """One shard's rows as the canonical {messages:[user,assistant]} chat form (same mapping as load_dsl)."""
    import json
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            ex = json.loads(line)
            rows.append({"messages": [{"role": "user", "content": str(ex["spot"])},
                                      {"role": "assistant", "content": str(ex["completion"])}]})
    return rows


def load_curriculum(paths: str, replay: float = REPLAY, seed: int = 0):
    """Load DSL shards IN ORDER, mixing a `replay` slice of all PRIOR phases before each later phase (curriculum +
    anti-forgetting, docs/llm_curriculum.md). NO shuffle — train order == phase order (paired with _OrderedSFT)."""
    import random

    from datasets import Dataset
    rng = random.Random(seed)
    seq, prior = [], []
    for p in [x.strip() for x in paths.split(",") if x.strip()]:
        cur = _rows_for(p)
        if prior and replay > 0:
            k = min(len(prior), int(len(cur) * replay))
            if k:
                seq += rng.sample(prior, k)
        seq += cur
        prior += cur
        print(f"  + {p}: {len(cur)} rows (running total {len(seq)})", flush=True)
    return Dataset.from_list(seq) if seq else None


def main():
    if CURRICULUM:                                   # ordered curriculum (a->d) + replay, NO global shuffle
        ds = load_curriculum(DSL)
        if ds is None:
            raise SystemExit("CURRICULUM=1 requires DSL=<ordered shards a,b,c,d>")
        print(f"CURRICULUM SFT: {len(ds)} rows (ordered a->d + {REPLAY:.0%} replay, no shuffle)", flush=True)
    elif SKIP_PB:                                     # DSL-only (local): no PokerBench HF download
        ds = load_dsl(DSL)
        if ds is None:
            raise SystemExit("SKIP_PB=1 requires DSL=<shards>")
        print(f"DSL-only SFT: {len(ds)} examples (PokerBench skipped)", flush=True)
    else:
        ds = load_pokerbench()
        cols = ds.column_names
        ins = "instruction" if "instruction" in cols else cols[0]
        out = "output" if "output" in cols else cols[-1]
        print(f"PokerBench: {len(ds)} rows | fields: {ins} -> {out}", flush=True)
        ds = ds.map(lambda ex: {"messages": [{"role": "user", "content": str(ex[ins])},
                                              {"role": "assistant", "content": str(ex[out])}]},
                    remove_columns=cols)
        if DSL:                                      # MIX IN our self-growing DSL gold (program-of-thought completions)
            dsl = load_dsl(DSL)
            if dsl is not None:
                ds = concatenate_datasets([ds, dsl]).shuffle(seed=0)
                print(f"+ DSL: {len(dsl)} examples -> {len(ds)} total train rows", flush=True)
    if MAXN and not CURRICULUM and len(ds) > MAXN:   # never cap/shuffle the curriculum (order is load-bearing)
        ds = ds.shuffle(seed=0).select(range(MAXN))

    tok = AutoTokenizer.from_pretrained(BASE)
    if QUANT4:                                   # QLoRA: 4-bit base fits an 8B model on a 24GB GPU
        from peft import prepare_model_for_kbit_training
        qc = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
        model = AutoModelForCausalLM.from_pretrained(BASE, quantization_config=qc, device_map="cuda",
                                                     attn_implementation=ATTN)
        model = prepare_model_for_kbit_training(model)
    else:
        model = AutoModelForCausalLM.from_pretrained(BASE, torch_dtype=torch.bfloat16, device_map="cuda",
                                                     attn_implementation=ATTN)
    peft = LoraConfig(r=64, lora_alpha=128, lora_dropout=0.05, target_modules="all-linear",
                      task_type="CAUSAL_LM")
    cfg = SFTConfig(output_dir=OUT, per_device_train_batch_size=BATCH, gradient_accumulation_steps=2,
                    num_train_epochs=EPOCHS, learning_rate=2e-4, bf16=True,
                    logging_steps=int(os.environ.get("LOG_STEPS", "5")), logging_first_step=True,
                    max_steps=int(os.environ.get("MAX_STEPS", "-1")),
                    save_steps=int(os.environ.get("SAVE_STEPS", "500")), max_length=1024,
                    packing=PACKING, assistant_only_loss=ASSIST_ONLY,   # completion-only loss = the frac_bad fix; TRL auto-swaps in
                    train_sampling_strategy=("sequential" if CURRICULUM else "random"),  # curriculum order (built-in, no custom sampler)
                    warmup_ratio=0.03, lr_scheduler_type="cosine", report_to="none")  # qwen3_training.jinja = the {% generation %} mask
    trainer = SFTTrainer(model=model, train_dataset=ds, peft_config=peft, args=cfg, processing_class=tok)
    trainer.train()
    trainer.save_model(OUT)
    print(f"SAVED LoRA -> {OUT} | GPU peak {torch.cuda.max_memory_allocated()/1e9:.1f} GB", flush=True)


if __name__ == "__main__":
    main()
