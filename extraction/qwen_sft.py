"""Fine-tune Qwen (LoRA) on the public PokerBench GTO dataset (RZ412/PokerBench) — a real poker LLM that
saturates the GPU steadily. This is the strategic/language layer (exploit hypotheses, coaching, curriculum
direction) on top of the DeepMind net. Run on the pod (GPU): python -u -m extraction.qwen_sft
Env: BASE (default Qwen/Qwen3-8B), MAXN (cap train rows), EPOCHS.
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
OUT = "/root/qwen_poker_lora"


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


def main():
    ds = load_pokerbench()
    cols = ds.column_names
    ins = "instruction" if "instruction" in cols else cols[0]
    out = "output" if "output" in cols else cols[-1]
    print(f"PokerBench: {len(ds)} rows | fields: {ins} -> {out}", flush=True)
    if MAXN and len(ds) > MAXN:
        ds = ds.shuffle(seed=0).select(range(MAXN))
    ds = ds.map(lambda ex: {"messages": [{"role": "user", "content": str(ex[ins])},
                                          {"role": "assistant", "content": str(ex[out])}]},
                remove_columns=cols)

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
                    num_train_epochs=EPOCHS, learning_rate=2e-4, bf16=True, logging_steps=20,
                    save_steps=int(os.environ.get("SAVE_STEPS", "500")), max_length=1024, packing=True, warmup_ratio=0.03,
                    lr_scheduler_type="cosine", report_to="none")
    trainer = SFTTrainer(model=model, train_dataset=ds, peft_config=peft, args=cfg, processing_class=tok)
    trainer.train()
    trainer.save_model(OUT)
    print(f"SAVED LoRA -> {OUT} | GPU peak {torch.cuda.max_memory_allocated()/1e9:.1f} GB", flush=True)


if __name__ == "__main__":
    main()
