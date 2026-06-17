"""Convert the ENGINE-VERIFIED calc toolkits (postflop_calc_verified + strategy_calc_verified — GPT-5.5-generated,
gated) into DSL MATH training examples: teach the model that `api.<fn>` exists, what it computes, and a real verified
call. This is the number-sense layer (MathGLM, docs/math_accuracy_strategy.md) — so Qwen PROPOSES these engine
functions correctly in its decision programs (the engine still computes the value). type='math'."""
from __future__ import annotations

import json

from pokerbot import config
from dataset.schema import make_example

_FILES = ("postflop_calc_verified.json", "strategy_calc_verified.json")


def build(limit: int | None = None):
    n = 0
    for fname in _FILES:
        p = config.KNOWLEDGE_DIR / "math" / fname
        if not p.exists():
            continue
        for c in json.loads(p.read_text(encoding="utf-8")).get("calculations", []):
            spot = (f"Poker math — {c['name']} ({c.get('category', '')}). {c['definition']} "
                    f"Formula: {c['formula_plain']}. How do you compute this EXACTLY in our engine?")
            comp = (f"# {c['name']}: compute with the engine API, not mental arithmetic.\n"
                    f"# {(c.get('worked_example') or '').strip()[:280]}\n"
                    f"# exact, engine-verified: {c['verify_expr']} == {c['verify_value']}\n"
                    f"# in a decision program, call: api.{c['function_name']}(...)")
            yield make_example("math", spot, comp, type_="math",
                               meta={"function": c["function_name"], "category": c.get("category"),
                                     "verified": True})
            n += 1
            if limit and n >= limit:
                return
