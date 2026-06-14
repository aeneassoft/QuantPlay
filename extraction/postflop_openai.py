"""Comprehensive OpenAI (gpt-5.1) query for an implementable HU NLHE postflop + bet-sizing
strategy, centered on the EDGE: choosing bet sizes that maximize fold-equity EV and exploit
an opponent's folding thresholds.

Output: knowledge_base/postflop/openai_strategy.json
Run:    python -m extraction.postflop_openai
"""
from __future__ import annotations

import json

from pokerbot import config
from extraction.llm import openai_json

SYSTEM = (
    "You are a world-class No-Limit Hold'em theorist AND a software engineer. You design "
    "postflop strategies that are DIRECTLY IMPLEMENTABLE as code (concrete thresholds, formulas, "
    "and numeric parameters), grounded in modern GTO + exploitative theory (Modern Poker Theory, "
    "The Theory of Poker, NLHE: Theory & Practice). Be precise and quantitative, not vague."
)

USER = (
    "Design a complete, implementable HEADS-UP NLHE postflop decision + bet-sizing system for a "
    "bot, optimized to MAXIMIZE EV and especially to EXPLOIT a static, near-GTO opponent (like "
    "Slumbot) by attacking its folding thresholds.\n\n"
    "Center the design on this EDGE: for any spot, determine the bet size that best exploits how "
    "often the opponent folds — i.e. given an opponent fold-frequency-vs-size curve F(s) (s = bet "
    "as a fraction of the pot), pick the size that maximizes EV; when bluffing choose the size "
    "where fold equity is most profitable, when value-betting choose the largest size still called "
    "enough.\n\n"
    "Cover concretely: (1) board-texture classification (dry/wet/paired/monotone/connected) and "
    "how it changes c-bet frequency and size; (2) c-bet, turn-barrel, river decisions by range/nut "
    "advantage; (3) the fold-equity math: the alpha = s/(1+s) breakeven, EV formulas for a bluff "
    "and for a value bet as functions of s and F(s)/call-freq, and the algorithm to pick the "
    "EV-maximizing size; (4) how to estimate/learn F(s) from observed opponent responses and how "
    "to exploit a static bot that over- or under-folds at particular sizes (overbets, small "
    "stabs); (5) bluff selection by blockers and equity; (6) defense by MDF and when to deviate; "
    "(7) deep-stack (200bb) adjustments. Give concrete numeric default parameters a program can "
    "plug in immediately."
)

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "summary": {"type": "string"},
        "rules": {
            "type": "array",
            "items": {
                "type": "object", "additionalProperties": False,
                "properties": {
                    "area": {"type": "string"},
                    "condition": {"type": "string"},
                    "action": {"type": "string"},
                    "size_pct_pot": {"type": "number"},
                    "formula": {"type": "string"},
                    "rationale": {"type": "string"},
                },
                "required": ["area", "condition", "action", "size_pct_pot", "formula", "rationale"],
            },
        },
        "fold_equity": {
            "type": "object", "additionalProperties": False,
            "properties": {
                "alpha_formula": {"type": "string"},
                "ev_bluff_formula": {"type": "string"},
                "ev_value_formula": {"type": "string"},
                "pick_bluff_size_algorithm": {"type": "string"},
                "pick_value_size_algorithm": {"type": "string"},
                "exploit_static_bot_algorithm": {"type": "string"},
                "estimate_fold_curve_algorithm": {"type": "string"},
            },
            "required": ["alpha_formula", "ev_bluff_formula", "ev_value_formula",
                         "pick_bluff_size_algorithm", "pick_value_size_algorithm",
                         "exploit_static_bot_algorithm", "estimate_fold_curve_algorithm"],
        },
        "parameters": {
            "type": "array",
            "items": {
                "type": "object", "additionalProperties": False,
                "properties": {"name": {"type": "string"}, "value": {"type": "number"},
                               "meaning": {"type": "string"}},
                "required": ["name", "value", "meaning"],
            },
        },
    },
    "required": ["summary", "rules", "fold_equity", "parameters"],
}


def main() -> None:
    data, (pin, pout) = openai_json(SYSTEM, USER, SCHEMA, "postflop_strategy", max_tokens=16000)
    out = config.KNOWLEDGE_DIR / "postflop" / "openai_strategy.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"saved -> {out}  (prompt={pin} completion={pout} tokens)")
    print(f"rules={len(data.get('rules', []))}  parameters={len(data.get('parameters', []))}")
    print("\nfold_equity.alpha_formula:", data["fold_equity"]["alpha_formula"])
    print("pick_bluff_size_algorithm:", data["fold_equity"]["pick_bluff_size_algorithm"][:400])
    print("exploit_static_bot_algorithm:", data["fold_equity"]["exploit_static_bot_algorithm"][:400])
    print("\nsample rules:")
    for r in data.get("rules", [])[:8]:
        print(f"  [{r['area']}] {r['condition']} -> {r['action']} ({r['size_pct_pot']}% pot)")


if __name__ == "__main__":
    main()
