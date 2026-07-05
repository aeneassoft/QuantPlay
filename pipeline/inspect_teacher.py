"""DSL-shard QUALITY inspector ($0, NO torch) — the Phase-0c/1d gate instrument. For each shard: action-mix %,
grounded-rate (an `api.*` call before the first `decide`), decide_mix-vs-single ratio, `meta.mixed` share, and per-street
coverage. Prints the teacher shard side-by-side with the solver+selfplay baseline + a degeneracy verdict, so we can
decide GO (scale the 32B teacher) / NO-GO (escalate MODEL_NAME to Qwen3-Next-80B-A3B-FP8) BEFORE any big spend.

Degeneracy = no single action should exceed 70% (a collapsed/pure teacher), and the aggression (bet+raise+allin) share
should be within ~15pp of the solver baseline (real GTO is mixed). These are the plan's Gate-0c criteria.

Run: python -m pipeline.inspect_teacher [shard ...]   (default: teacher solver solver_mass a_contract c_decide)
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter

from pokerbot import config

_AGGRO = {"bet", "raise", "allin", "all-in"}


def _street(spot_text: str) -> str:
    m = re.search(r"act on the (\w+)", spot_text or "")
    return m.group(1) if m else "?"


def stats(path: str) -> dict:
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    n = len(rows)
    acts, streets = Counter(), Counter()
    grounded = decide_mix = mixed_meta = 0
    for ex in rows:
        a = (ex.get("action") or {}).get("action")
        if a:
            acts[a] += 1
        comp = ex.get("completion", "")
        di = comp.find("decide")
        if "api." in (comp[:di] if di >= 0 else comp):          # an engine call BEFORE the commit = derived, not gut
            grounded += 1
        if "decide_mix" in comp:
            decide_mix += 1
        if (ex.get("meta") or {}).get("mixed"):
            mixed_meta += 1
        streets[_street(ex.get("spot", ""))] += 1
    aggro = sum(acts[a] for a in acts if a in _AGGRO)
    return {"n": n, "acts": acts, "streets": streets, "grounded": grounded,
            "decide_mix": decide_mix, "mixed_meta": mixed_meta, "aggro_share": aggro / max(1, n)}


def _fmt(s: dict) -> str:
    n = max(1, s["n"])
    am = ", ".join(f"{a} {c / n:.0%}" for a, c in s["acts"].most_common())
    st = ", ".join(f"{k} {c / n:.0%}" for k, c in s["streets"].most_common())
    return (f"n={s['n']} | grounded {s['grounded'] / n:.0%} | decide_mix {s['decide_mix'] / n:.0%} | "
            f"mixed-meta {s['mixed_meta'] / n:.0%} | aggro {s['aggro_share']:.0%}\n"
            f"    actions: {am}\n    streets: {st}")


def main():
    names = sys.argv[1:] or ["teacher", "solver", "solver_mass", "a_contract", "c_decide"]
    collected = {}
    for name in names:
        p = name if name.endswith(".jsonl") else str(config.ROOT / "dataset" / "shards" / f"{name}.jsonl")
        try:
            s = stats(p)
            collected[name] = s
            print(f"=== {name} ===\n    {_fmt(s)}")
        except FileNotFoundError:
            print(f"=== {name} === MISSING")
    # Gate-0c verdict on the teacher shard (vs the solver baseline aggression)
    if "teacher" in collected:
        t = collected["teacher"]
        base = collected.get("solver") or collected.get("solver_mass")
        top = max((c / max(1, t["n"]) for c in t["acts"].values()), default=0)
        verdict = ["GO" if top <= 0.70 else f"NO-GO: top action {top:.0%} > 70% (collapsed)"]
        if base:
            d = abs(t["aggro_share"] - base["aggro_share"])
            verdict.append(f"aggro vs solver: {t['aggro_share']:.0%} vs {base['aggro_share']:.0%} (Δ{d:.0%}{' OK' if d <= 0.15 else ' >15pp!'})")
        print("\nGATE-0c teacher verdict:", " | ".join(verdict))


if __name__ == "__main__":
    main()
