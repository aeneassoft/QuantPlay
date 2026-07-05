"""PokerBench-style STREET-SPLIT + a held-out TEST fold over our SFT-gold shards.

PokerBench splits preflop/postflop with a clean train/test split; we mirror that structure (the user's "lay our data
out like PokerBench, but better"): read the gold shards (`registry.sft_gold()`), tag each example's STREET (parsed from
the canonical `format_spot` text), split into preflop/flop/turn/river TRAIN shards + a decontaminated TEST fold (split
by `spot_key`, so a key never spans train+test → no leakage) for a $0 local eval. Our edge over PokerBench is preserved:
program-of-thought completions + the canonical format_spot + global dedup/decontam. Reuses `dataset/schema`.

Run: python -m dataset.build.streets [--test-frac 0.02]
"""
from __future__ import annotations

import argparse
import json
import random
import re
from collections import Counter
from pathlib import Path

from pokerbot import config
from dataset import registry, schema

_STREET = re.compile(r"to act on the (preflop|flop|turn|river)", re.IGNORECASE)


def street_of(spot_text: str) -> str:
    """Parse the street from the canonical format_spot text ('... Hero to act on the <street>.'). Default preflop."""
    m = _STREET.search(spot_text or "")
    return m.group(1).lower() if m else "preflop"


def main(test_frac: float = 0.02, seed: int = 0) -> None:
    rng = random.Random(seed)
    gold = registry.sft_gold()
    rows = []
    for p in gold:
        for line in Path(p).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    print(f"loaded {len(rows)} gold rows from {len(gold)} shards", flush=True)

    # group by spot_key so a key never spans train+test (no leakage), then carve the test fold
    by_key: dict[str, list] = {}
    for r in rows:
        r.setdefault("meta", {})["street"] = street_of(r.get("spot", ""))
        by_key.setdefault(schema.spot_key(r.get("spot", "")), []).append(r)
    keys = list(by_key)
    rng.shuffle(keys)
    test_keys = set(keys[: int(len(keys) * test_frac)])

    buckets: dict[str, list] = {"preflop": [], "flop": [], "turn": [], "river": []}
    test: list = []
    for k, grp in by_key.items():
        for r in grp:
            (test if k in test_keys else buckets[r["meta"]["street"]]).append(r)

    out = config.ROOT / "dataset" / "shards" / "streets"
    out.mkdir(parents=True, exist_ok=True)
    print("STREET-SPLIT (train shards):", flush=True)
    for st in ("preflop", "flop", "turn", "river"):
        n = schema.write_jsonl(out / f"train_{st}.jsonl", buckets[st])
        print(f"  train_{st:8s}: {n:6d}", flush=True)
    nt = schema.write_jsonl(out / "test_holdout.jsonl", test)
    print(f"  test_holdout : {nt:6d} (held out by spot_key, ~{test_frac:.0%})", flush=True)
    print("overall street dist:", dict(Counter(r["meta"]["street"] for r in rows)), flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--test-frac", type=float, default=0.02)
    a = ap.parse_args()
    main(test_frac=a.test_frac)
