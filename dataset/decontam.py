"""Decontamination: the PokerBench TEST-set spot-keys, so NO training example (ANY source — PokerBench train, the
local KB converters, the Phase-3 frontier-distillation, Phase-4 self-play) ever leaks a held-out test spot into
training. Addresses the Phase-2 caveat. Cached to dataset/decontam_keys.json (built once from HF `RZ412/PokerBench`
split='test'). Per docs/plans/QWEN_6MAX_PLAN.md / docs/doctrine/DATASET_SPEC.md.
"""
from __future__ import annotations

import json

from pokerbot import config
from dataset.schema import spot_key

_CACHE = config.ROOT / "dataset" / "decontam_keys.json"


def pokerbench_test_keys(refresh: bool = False) -> set:
    """Set of canonical spot-keys for the PokerBench TEST split (cached). Empty set if HF is unavailable."""
    if _CACHE.exists() and not refresh:
        return set(json.loads(_CACHE.read_text(encoding="utf-8")))
    try:
        from datasets import load_dataset
        ds = load_dataset("RZ412/PokerBench", split="test", streaming=True)
        keys = {spot_key((r.get("instruction") or "").strip()) for r in ds if (r.get("instruction") or "").strip()}
        _CACHE.write_text(json.dumps(sorted(keys)), encoding="utf-8")
        return keys
    except Exception as e:  # noqa: BLE001
        print(f"  (decontam: HF test split unavailable -> {type(e).__name__}; proceeding with no decontam keys)")
        return set()


if __name__ == "__main__":
    k = pokerbench_test_keys(refresh=True)
    print(f"PokerBench test spot-keys cached: {len(k)} -> {_CACHE}")
