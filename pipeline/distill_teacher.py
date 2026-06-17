"""Distil the B300 TEACHER output into 8B-ready gold (the PC-hub side of the 2-node distillation). Reads the raw
teacher candidates pulled from the pod (`data/teacher_raw.jsonl`), runs the deterministic EV-truth gate
(`pipeline/filter.EVFilter`: schema + relevance + PokerBench-test decontam + dedup — legality was already enforced
on the pod by run_program), and writes `dataset/shards/teacher.jsonl` = the warm-start corpus the 8B SFT trains on.

This is CLAUDE.md-correct: the frontier (our own 235B) feeds ONLY the PC's dataset, EV-gated there; the engine is TRUTH.
The 8B still needs RL above this warm-start (the imitation ceiling) — distillation lifts the START, not the ceiling.

Run: python -m pipeline.distill_teacher [in=data/teacher_raw.jsonl] [out=dataset/shards/teacher.jsonl]
"""
from __future__ import annotations

import json
import sys

from pokerbot import config
from pipeline.filter import EVFilter

try:
    from dataset.decontam import pokerbench_test_keys
except Exception:  # noqa: BLE001
    def pokerbench_test_keys():
        return set()


def main():
    inp = sys.argv[1] if len(sys.argv) > 1 else str(config.ROOT / "data" / "teacher_raw.jsonl")
    out = sys.argv[2] if len(sys.argv) > 2 else str(config.ROOT / "dataset" / "shards" / "teacher.jsonl")
    try:
        rows = [json.loads(l) for l in open(inp, encoding="utf-8") if l.strip()]
    except FileNotFoundError:
        print(f"no teacher data at {inp} (run MODE=teacher on the B300 first)")
        return
    flt = EVFilter(decontam_keys=pokerbench_test_keys())
    kept = []
    for ex in rows:
        if flt.gate(ex).ok:                      # G1-G4 (spot=None; legality already gated on the pod)
            kept.append(ex)
    with open(out, "w", encoding="utf-8") as f:
        for ex in kept:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    mixed = sum(1 for e in kept if (e.get("meta") or {}).get("mixed"))
    print(f"distilled {len(kept)}/{len(rows)} teacher rows -> {out}")
    print(f"  gate stats: {flt.stats}")
    print(f"  genuinely mixed: {mixed}/{len(kept)} ({mixed / max(1, len(kept)):.0%})")
    print(f"  NEXT: add {out} to the 8B SFT DSL (campaign train-mode auto-includes it if present)")


if __name__ == "__main__":
    main()
