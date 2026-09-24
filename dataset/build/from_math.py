"""Convert knowledge_base/math (Mathematics of Poker → formulas) into VERIFIED math-reasoning examples that teach the
brain to use the engine-API math (api.pot_odds / mdf / spr / ...) rather than do LLM arithmetic. Answers are the
formula's own `verify_result` → high-precision, low-leakage (docs/doctrine/DATASET_SPEC.md)."""
from __future__ import annotations

import json

from pokerbot import config
from dataset.schema import make_example


def build():
    d = json.loads((config.KNOWLEDGE_DIR / "math" / "math.json").read_text(encoding="utf-8"))
    rows = d if isinstance(d, list) else list(d.values())
    for r in rows:
        we = r.get("worked_example")
        desc = we.get("inputs_description") if isinstance(we, dict) else (str(we) if we else "")
        spot = (f"Poker math task — {r.get('name')}.\n{(r.get('definition') or '')[:280]}\n"
                f"Formula: {(r.get('formula_plain') or '')[:280]}\n"
                f"Worked example: {desc[:280] if desc else '(apply the formula)'}\n"
                f"Compute the result and state it.")
        comp = (f"# Use the engine math, not mental arithmetic: api.{r.get('function_name')}(...)\n"
                f"# {r.get('name')} — {(r.get('definition') or '')[:140]}\n"
                f"result = {r.get('verify_result')}")
        yield make_example("math", spot, comp, type_="math",
                           meta={"name": r.get("name"), "fn": r.get("function_name"),
                                 "verified": str(r.get("verified"))})
