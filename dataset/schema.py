"""The training-example SCHEMA + dataset-side hygiene (docs/doctrine/DATASET_SPEC.md). One JSONL record per example:

  {"source","type","spot","completion","action":{action,size_bb}|None,"meta":{...}}

`spot` = the canonical prompt (format_spot output for decisions; a task prompt for math/concept). `completion` =
the assistant target (a program-of-thought that calls `decide(...)`, or a math/CoT answer). `action` = the resulting
{action,size_bb} for decision examples (for verification). Hygiene here: a canonical spot-key (dedup), a hard-coded
RELEVANCE gate (the user's "no hair-shampoo" — only poker/strategy/math/code/reasoning), and a decontam helper.
"""
from __future__ import annotations

import hashlib
import json
import re

VALID_SOURCES = {"pokerbench", "ranges", "postflop", "exploit", "math", "concepts", "distill", "selfplay", "solver"}

# Relevance gate: an example must read as poker / strategy / math / game-theory / code-reasoning, else it is dropped
# (the self-growing dataset must never accrete off-domain knowledge that competes for capacity).
_REL = re.compile(r"\b(pot|bet|raise|call|fold|check|bluff|equity|range|board|flop|turn|river|preflop|postflop|"
                  r"blind|stack|position|btn|utg|hijack|cutoff|gto|nash|exploit|ev|odds|mdf|spr|combo|blocker|"
                  r"hold ?em|poker|nlhe|villain|hero|showdown|all-in|3bet|4bet|cbet|donk|overbet|value|polar|"
                  r"frequenc|solver|decide|action|spot|hand|suit|rank|probability|variance|kelly)\b", re.IGNORECASE)


def make_example(source: str, spot: str, completion: str, action: dict | None = None, type_: str = "decision",
                 meta: dict | None = None) -> dict:
    assert source in VALID_SOURCES, f"bad source {source}"
    return {"source": source, "type": type_, "spot": spot, "completion": completion,
            "action": action, "meta": meta or {}}


def is_relevant(text: str, min_hits: int = 2) -> bool:
    """Deterministic relevance gate (>= min_hits domain terms). The hard-coded anti-off-domain filter."""
    return len(_REL.findall(text or "")) >= min_hits


def spot_key(spot: str) -> str:
    """Canonical hash of a spot for dedup/decontam — whitespace/case-normalized."""
    norm = re.sub(r"\s+", " ", (spot or "").strip().lower())
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()


def validate(ex: dict) -> bool:
    if ex.get("source") not in VALID_SOURCES:
        return False
    if not ex.get("spot") or not ex.get("completion"):
        return False
    if ex.get("type") == "decision" and not (ex.get("action") or {}).get("action"):
        return False
    return True


def dedup(examples, decontam_keys: set | None = None):
    """Yield validated, relevant, deduped examples; skip any spot-key in `decontam_keys` (e.g. the PokerBench test set)."""
    seen = set(decontam_keys or set())
    stats = {"in": 0, "kept": 0, "dup": 0, "irrelevant": 0, "invalid": 0, "decontam": 0}
    for ex in examples:
        stats["in"] += 1
        if not validate(ex):
            stats["invalid"] += 1
            continue
        if not is_relevant(ex["spot"] + " " + ex["completion"]):
            stats["irrelevant"] += 1
            continue
        k = spot_key(ex["spot"])
        if k in seen:
            stats["dup" if (not decontam_keys or k not in decontam_keys) else "decontam"] += 1
            continue
        seen.add(k)
        stats["kept"] += 1
        yield ex
    ex_stats[0] = stats          # stash last-run stats for the runner to print


ex_stats = [None]                # module-level handle for the runner


def write_jsonl(path, examples) -> int:
    n = 0
    with open(path, "w", encoding="utf-8") as f:
        for ex in examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
            n += 1
    return n
