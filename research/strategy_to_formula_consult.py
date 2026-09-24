"""Convert validated POKER STRATEGY (the canonical literature + quality public strategy) into EXACT, self-verifying
mathematical FORMULAS via GPT-5.5 — formalizing prose wisdom into computable functions the brain can call. Same schema
+ gate as research/postflop_calc_consult (→ research.postflop_calc_gate strategy_calc → materialize → api.<fn> + the
DSL dataset). Frontier = prior; every spec ships a machine-checkable self-verification. Per docs/plans/math_accuracy_strategy.md.

Run: python -m research.strategy_to_formula_consult
"""
from __future__ import annotations

import json

from pokerbot import config
from research.llm import openai_json

OUT = config.KNOWLEDGE_DIR / "math" / "strategy_calc.json"

SYSTEM = (
    "You are a world-class poker theorist AND a precise Python engineer. You FORMALIZE validated No-Limit Hold'em "
    "STRATEGY into exact, self-verifying calculation functions. Draw on the canonical literature (Mathematics of "
    "Poker, The Theory of Poker, Modern Poker Theory, NLHE Theory & Practice, Beyond GTO, Exploitative Poker) and "
    "well-established public/solver-validated strategy — but output only MATH (formulas), never prose recipes. HARD "
    "RULES: pure Python, stdlib only (math, fractions, itertools — NO numpy). Exact where it matters. Each function is "
    "deterministic, single-purpose, typed, documented, and ships a worked example AND a machine-checkable verification "
    "(verify_expr calls the function and equals verify_value within 1e-6). No prose outside the JSON."
)

USER = (
    "We already have post-flop EV/odds math + equity/MDF/SPR/pot-odds primitives. Now FORMALIZE the STRATEGIC wisdom "
    "that is usually stated qualitatively — turn it into computable formulas (aim for 28-34 functions) across:\n"
    "1. Preflop sizing/ranges: open-raise size by position+stack; 3bet/4bet sizing (IP/OOP); squeeze sizing by #callers; "
    "calling-range % from pot-odds+position+stack; short-stack open-shove threshold (Nash-ish push/fold by bb).\n"
    "2. Range construction & balance: value:bluff combos by street to stay balanced; polarization degree; capped-range "
    "penalty; nut-fraction of a range; range-morphology (linear/polar/merged) selector by SPR+texture.\n"
    "3. C-bet / barrel theory: c-bet frequency by board texture + position + SPR; double/triple-barrel continuation "
    "frequency; give-up frequency; range-vs-range advantage → bet-frequency mapping.\n"
    "4. Bluffing & defense: river bluff-to-value by bet size; bluff-catcher break-even; over-fold / under-fold exploit "
    "EV; minimum check-raise defense; delayed-cbet value.\n"
    "5. Stack-depth & odds: set-mining implied-odds threshold; suited-connector implied odds; commitment threshold by "
    "SPR + hand class; reverse-implied discount.\n"
    "6. Exploitative deviation (the GTO-lens): EV of a bounded deviation vs a read of strength delta (VPIP/PFR/fold-to-"
    "cbet/aggression) — the size of the +EV deviation as a function of the read's confidence + magnitude.\n"
    "7. Position & realization: equity-realization R by position+SPR; in-position EV premium; initiative value.\n\n"
    "Each formula must be exact, composable with our pot-odds/MDF/SPR/equity primitives, and independently verifiable."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "calculations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"}, "category": {"type": "string"},
                    "definition": {"type": "string"}, "formula_plain": {"type": "string"},
                    "function_name": {"type": "string"}, "python_function": {"type": "string"},
                    "inputs": {"type": "string"}, "worked_example": {"type": "string"},
                    "verify_expr": {"type": "string"}, "verify_value": {"type": "number"},
                },
                "required": ["name", "category", "definition", "formula_plain", "function_name",
                             "python_function", "inputs", "worked_example", "verify_expr", "verify_value"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["calculations"],
    "additionalProperties": False,
}


def main():
    print("consulting GPT-5.5 to formalize poker strategy into formulas ...", flush=True)
    data, (pt, ct) = openai_json(SYSTEM, USER, SCHEMA, "strategy_formulas", model="gpt-5.5", max_tokens=32000)
    calcs = data.get("calculations", [])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    from collections import Counter
    print(f"GPT-5.5 produced {len(calcs)} strategy formulas -> {OUT}", flush=True)
    print("by category:", dict(Counter(c.get("category", "?") for c in calcs)), flush=True)
    print(f"tokens in/out: {pt}/{ct}", flush=True)


if __name__ == "__main__":
    main()
