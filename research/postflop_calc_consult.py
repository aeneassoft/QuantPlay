"""Comprehensive post-flop CALCULATION generation via the OpenAI API (GPT-5.5) — fill the engine-API's post-flop math
gaps with EXACT, self-verifying functions the brain can call. Output is GATED downstream: each spec ships a machine-
checkable verification (verify_expr == verify_value), so we keep only formulas the ENGINE confirms (CLAUDE.md: frontier
= prior, engine = truth). Saves knowledge_base/math/postflop_calc.json.

Run: python -m research.postflop_calc_consult
"""
from __future__ import annotations

import json

from pokerbot import config
from research.llm import openai_json

OUT = config.KNOWLEDGE_DIR / "math" / "postflop_calc.json"

SYSTEM = (
    "You are a world-class poker mathematician AND a precise Python engineer. You produce EXACT, self-verifying "
    "post-flop No-Limit Hold'em CALCULATION functions for a GTO engine. HARD RULES: pure Python, standard library "
    "ONLY (you may use math, fractions, itertools — NO numpy/scipy). Exactness first: prefer fractions.Fraction or "
    "careful closed-form float; never hand-wave. Every function is deterministic, single-purpose, fully typed in the "
    "signature, and documented. Every function ships a worked example AND a machine-checkable verification "
    "(verify_expr is a Python expression calling the function that evaluates to verify_value within 1e-6). "
    "No prose outside the JSON."
)

USER = (
    "Our 6-max NLHE engine-API ALREADY has: equity(hero,villain,board), required_equity(to_call,pot), "
    "pot_odds(to_call,pot), mdf(bet,pot), spr(eff,pot), outs_equity(outs,cards), board_texture(board), "
    "hand_rank(hole,board). DO NOT duplicate these.\n\n"
    "Generate a LARGE, comprehensive chunk (aim for 28-34 functions) of the POST-FLOP calculations we are MISSING — "
    "the math a GTO bot needs to reason about bet-sizing, bluffing, defense, ranges, and EV after the flop. Cover ALL "
    "of these categories thoroughly:\n"
    "1. Bet-sizing & polarization: optimal value:bluff ratio at a bet size; bluff-to-value ratio by pot-fraction; "
    "alpha (break-even bluff freq) = bet/(bet+pot); polarized bet EV.\n"
    "2. Fold equity & semi-bluff: semi-bluff EV = fold_equity*pot + (1-fold_equity)*(equity_when_called*final_pot - "
    "cost); break-even fold-equity for a pure bluff; required fold% for a raise.\n"
    "3. Defense: minimum defense frequency by bet-fraction; bluff-catcher indifference; calling frequency to make a "
    "bluffer indifferent; over/under-fold exploit value.\n"
    "4. Pot/implied odds: pot odds with rake; implied odds (extra needed to call a draw); reverse implied odds; "
    "effective odds across remaining streets; direct vs implied break-even.\n"
    "5. SPR & commitment: stack-off equity threshold given SPR; commitment SPR for a hand class; geometric bet "
    "fraction to get all-in over N streets; per-street geometric sizing.\n"
    "6. Equity & ranges: equity realization factor R (IP vs OOP); range-vs-range EV given an equity distribution; "
    "nut/range advantage index; equity-denial value of a bet.\n"
    "7. Combinatorics: number of combos of a hand class given known/blocker cards; value:bluff COMBO counts to hit a "
    "target polarization; blocker-adjusted combo count; card-removal effect on a range size.\n"
    "8. EV of decisions: EV(call), EV(fold)=0 baseline, EV(raise) with fold-equity, EV(check-raise) vs EV(check-call); "
    "multiway equity-need adjustment (vs N opponents).\n"
    "9. Draws: exact 2-card draw equity (vs the rule-of-2/4 approximation); combined-draw outs; discounted/anti-outs.\n\n"
    "Make the functions COMPOSE with pot-odds/MDF/SPR reasoning. Each must be exact and independently verifiable."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "calculations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "category": {"type": "string"},
                    "definition": {"type": "string"},
                    "formula_plain": {"type": "string"},
                    "function_name": {"type": "string"},
                    "python_function": {"type": "string"},
                    "inputs": {"type": "string"},
                    "worked_example": {"type": "string"},
                    "verify_expr": {"type": "string"},
                    "verify_value": {"type": "number"},
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
    print("consulting GPT-5.5 for post-flop calculations ...", flush=True)
    data, (pt, ct) = openai_json(SYSTEM, USER, SCHEMA, "postflop_calculations",
                                 model="gpt-5.5", max_tokens=32000)
    calcs = data.get("calculations", [])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    from collections import Counter
    print(f"GPT-5.5 produced {len(calcs)} post-flop calculations -> {OUT}", flush=True)
    print("by category:", dict(Counter(c.get("category", "?") for c in calcs)), flush=True)
    print(f"tokens in/out: {pt}/{ct}", flush=True)


if __name__ == "__main__":
    main()
