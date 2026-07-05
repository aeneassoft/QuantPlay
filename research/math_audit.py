"""P5: OpenAI audit of knowledge_base/math/formulas.py — a CORRECTNESS + gaps + improvements review (honest: a review,
NOT a 'confirm our breakthrough' — our −28.55 vs GTOW does not show we out-math it). Sends the formula library to the
OpenAI API (research/llm.openai_json) for a structured audit; saves it to data/math_audit.json.

Run:  python -m research.math_audit
"""
from __future__ import annotations

import json
from pathlib import Path

from pokerbot import config
from research.llm import openai_json

SYSTEM = (
    "You are a rigorous poker game-theory + math reviewer auditing the math-primitive library of a heads-up "
    "No-Limit Hold'em GTO engine (HUNL, 200bb deep). Be precise, skeptical, and concrete — do NOT flatter. Your job is "
    "to find real errors, dangerous approximations, and the MISSING primitives that most plausibly cost bb/100 against "
    "a near-Nash opponent (GTO Wizard). Ground every point in the actual code shown."
)

_OBJ = lambda props: {"type": "object", "additionalProperties": False, "properties": props, "required": list(props)}
SCHEMA = _OBJ({
    "correctness_issues": {"type": "array", "items": _OBJ({
        "formula": {"type": "string"}, "issue": {"type": "string"},
        "severity": {"type": "string"}, "fix": {"type": "string"}})},
    "missing_primitives": {"type": "array", "items": _OBJ({
        "name": {"type": "string"}, "why_it_matters": {"type": "string"}, "bb100_impact": {"type": "string"}})},
    "top_3_actions": {"type": "array", "items": {"type": "string"}},
})


def main() -> None:
    code = (config.KNOWLEDGE_DIR / "math" / "formulas.py").read_text(encoding="utf-8")
    user = (
        "Audit this HUNL GTO engine's math library.\n"
        "1) CORRECTNESS: any formula that is wrong or dangerously approximated — give the exact error + the fix.\n"
        "2) MISSING PRIMITIVES: what a near-Nash HUNL engine needs but is absent (e.g. exact range-vs-range equity, "
        "blocker-aware range weighting, geometric / multi-street bet sizing, indifference/MDF with non-zero-equity "
        "bluffs, equity-realization estimation) — rank by plausible bb/100 cost.\n"
        "3) TOP 3 ACTIONS to most improve play vs GTO Wizard.\n"
        "Honest framing: this is a REVIEW, not a request to confirm a breakthrough.\n\n"
        "```python\n" + code + "\n```"
    )
    audit, usage = openai_json(SYSTEM, user, SCHEMA, "math_audit", max_tokens=9000)
    out = config.DATA_DIR / "math_audit.json"
    out.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"=== OpenAI math audit (tokens in/out = {usage}) ===\n")
    print("CORRECTNESS ISSUES:")
    for c in audit.get("correctness_issues", []) or ["(none)"]:
        print(f"  • [{c.get('severity','?')}] {c.get('formula','?')}: {c.get('issue','')}\n      fix: {c.get('fix','')}"
              if isinstance(c, dict) else f"  {c}")
    print("\nMISSING PRIMITIVES (ranked):")
    for m in audit.get("missing_primitives", []):
        print(f"  • [{m.get('bb100_impact','?')}] {m.get('name','?')}: {m.get('why_it_matters','')}")
    print("\nTOP 3 ACTIONS:")
    for i, a in enumerate(audit.get("top_3_actions", []), 1):
        print(f"  {i}. {a}")
    print(f"\nsaved -> {out}")


if __name__ == "__main__":
    main()
