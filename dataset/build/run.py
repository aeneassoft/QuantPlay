"""Build the DSL training dataset from the local KB sources, with dedup + relevance gating (dataset/schema.py).
NOW: math + exploit (clean, local, no API/download). NEXT converters (same framework): the PokerBench 6-max SPINE
(HF `RZ412/PokerBench` → Spot → format_spot → a program-of-thought completion), `ranges`/`postflop` (solver-freq
programs), and the distill-seeds (concepts/theory via the Phase-3 frontier loop).
Run: python -m dataset.build.run [--full]   (default = a verification SAMPLE)
"""
from __future__ import annotations

import argparse
from collections import Counter

from pokerbot import config
from dataset import schema
from dataset.decontam import pokerbench_test_keys
from dataset.build import from_math, from_exploit, from_pokerbench, from_calc


def main(full: bool, pb: int, decontam: bool) -> None:
    out = config.ROOT / "dataset" / "shards"
    out.mkdir(parents=True, exist_ok=True)
    gen = (list(from_math.build()) + list(from_calc.build())          # math/CoT + the 66 engine-verified formulas
           + list(from_exploit.build(limit=None if full else 200)))
    if pb:                                          # PokerBench spine (HF; streaming). pb<0 -> full.
        gen += list(from_pokerbench.build(limit=None if pb < 0 else pb))
    keys = pokerbench_test_keys() if decontam else set()   # block PokerBench-test spots from ANY source
    deduped = list(schema.dedup(gen, decontam_keys=keys))
    path = out / ("local_kb.jsonl" if full else "sample.jsonl")
    n = schema.write_jsonl(path, deduped)
    print(f"wrote {n} examples -> {path}")
    print("hygiene:", schema.ex_stats[0])
    print("by source:", dict(Counter(e["source"] for e in deduped)))
    print("by type:  ", dict(Counter(e["type"] for e in deduped)))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="full local converters (no PokerBench cap)")
    ap.add_argument("--pb", type=int, default=0, help="PokerBench examples to include (-1 = all; 0 = skip)")
    ap.add_argument("--no-decontam", action="store_true", help="skip the PokerBench-test decontamination gate")
    a = ap.parse_args()
    main(a.full, a.pb, decontam=not a.no_decontam)
