"""Build the 4 ORDERED curriculum shards (docs/llm_curriculum.md): a_contract -> b_ground -> c_decide -> d_exploit.

The LLM curriculum (for an LLM, not a human): the base already KNOWS poker concepts + Python, so we teach the 3 things
it lacks, in order — (a) the output CONTRACT (always emit a valid program), via the CLEAREST engine-oracle decisions;
(b) engine GROUNDING (which api.* answers which question), via the 66 verified formulas; (c) DECISION quality easy->hard,
the harder self-play decisions (+ optional PokerBench); (d) bounded EXPLOIT (the GTO-lens overlay). Difficulty = the
engine-oracle EV-SPREAD (pilot.rank_state, via from_selfplay's meta). Globally deduped + decontaminated vs the
PokerBench test set (schema.dedup). Reuses the existing builders; CPU/$0 (no PokerBench unless --pb).

Run (local proof): python -m dataset.build.curriculum 1500
Run (pod scale):   python -m dataset.build.curriculum 4000 --pb -1 --exploit -1
"""
from __future__ import annotations

import argparse
from collections import Counter

from pokerbot import config
from dataset import schema
from dataset.decontam import pokerbench_test_keys
from dataset.build import from_calc, from_exploit, from_math, from_pokerbench, from_selfplay

A_FRAC = 0.35   # the clearest (highest EV-spread) decisions form the CONTRACT stage; the rest are the harder c_decide


def _tag(examples, phase):
    out = []
    for ex in examples:
        ex.setdefault("meta", {})["phase"] = phase
        out.append(ex)
    return out


def build(n_decisions: int = 1500, pb: int = 0, exploit: int = 0, ground: bool = False, seed: int = 0):
    """Return {phase: [examples]} for phases a,b,c,d — globally deduped + decontam'd, decisions sorted easy->hard.
    Default = DECISIONS ONLY (user principle 2026-06-17: every example must DRIVE a decision; the comment-only
    math/exploit phases are off unless --ground/--exploit, to be re-added later as decision-SHAPED reasoning)."""
    print(f"generating {n_decisions} reasoning-loop decisions ...", flush=True)
    decisions = []
    for i, ex in enumerate(from_selfplay.build(n=n_decisions, seed=seed)):
        decisions.append(ex)
        if (i + 1) % 200 == 0:
            print(f"  {i + 1}/{n_decisions} decisions", flush=True)
    decisions.sort(key=lambda e: e.get("meta", {}).get("clarity", 0.0), reverse=True)   # clearest (far from boundary) first
    cut = int(len(decisions) * A_FRAC)
    a_contract, c_self = decisions[:cut], decisions[cut:]

    b_ground = (list(from_calc.build()) + list(from_math.build())) if ground else []    # comment-only knowledge (off by default)
    d_exploit = list(from_exploit.build(limit=None if exploit < 0 else exploit)) if exploit else []
    c_decide = list(c_self)
    if pb:                                                                # PokerBench solver decisions (HF; pod scale)
        c_decide += list(from_pokerbench.build(limit=None if pb < 0 else pb))

    # tag phase, dedup GLOBALLY (validate + relevance + cross-shard dedup + PokerBench-test decontam), then split back
    tagged = _tag(a_contract, "a") + _tag(b_ground, "b") + _tag(c_decide, "c") + _tag(d_exploit, "d")
    kept = list(schema.dedup(tagged, decontam_keys=pokerbench_test_keys()))
    by = {"a": [], "b": [], "c": [], "d": []}
    for ex in kept:
        by[ex.get("meta", {}).get("phase", "c")].append(ex)
    return by


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("n", nargs="?", type=int, default=1500, help="self-play decisions to generate")
    ap.add_argument("--pb", type=int, default=0, help="PokerBench rows into c_decide (-1=all; 0=skip, e.g. local)")
    ap.add_argument("--exploit", type=int, default=0, help="exploit rows in d_exploit (0=off; -1=all)")
    ap.add_argument("--ground", action="store_true", help="include the comment-only math/formula grounding shard")
    a = ap.parse_args()
    out = config.ROOT / "dataset" / "shards"
    out.mkdir(parents=True, exist_ok=True)
    by = build(n_decisions=a.n, pb=a.pb, exploit=a.exploit, ground=a.ground)
    names = {"a": "a_contract", "b": "b_ground", "c": "c_decide", "d": "d_exploit"}
    total = 0
    for ph in ("a", "b", "c", "d"):
        path = out / f"{names[ph]}.jsonl"
        n = schema.write_jsonl(path, by[ph])
        total += n
        print(f"  {names[ph]:11s}: {n:5d} rows -> {path}")
    print(f"total kept: {total} | hygiene: {schema.ex_stats[0]}")
    print("decision action mix:",
          dict(Counter(e["action"]["action"] for e in by["a"] + by["c"] if e.get("action"))))


if __name__ == "__main__":
    main()
