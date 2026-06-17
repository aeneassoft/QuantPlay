"""Analyze & verify poker math via OpenAI (gpt-5.1).

For each core math topic we gather the relevant book passages, ask the model for a
formula + a self-contained Python function + a worked example, then VERIFY by executing
the generated function.

Output (checkpointed): knowledge_base/math/math.jsonl
Final merged:          knowledge_base/math/math.json  +  knowledge_base/math/formulas.py

Run:  python -m extraction.extract_math [--limit N]
"""
from __future__ import annotations

import argparse
import json

from pokerbot import config
from research.llm import Checkpoint, openai_json

# topic -> keywords to find supporting passages across the 3 books
TOPICS: list[tuple[str, list[str]]] = [
    ("Pot Odds", ["pot odds", "odds to call", "getting", "to 1"]),
    ("Equity Needed to Call", ["equity", "equity needed", "break even", "breakeven"]),
    ("Expected Value (EV)", ["expected value", " ev ", "expectation"]),
    ("Minimum Defense Frequency (MDF)", ["minimum defense", "defense frequency", "mdf", "defend"]),
    ("Bluff-to-Value Ratio and Bluffing Frequency", ["bluff", "value", "ratio", "indifferent", "optimal bluffing"]),
    ("Implied Odds", ["implied odds"]),
    ("Reverse Implied Odds", ["reverse implied"]),
    ("Fold Equity", ["fold equity"]),
    ("Outs to Equity (Rule of 2 and 4)", ["outs", "rule of 2", "rule of four", "rule of two"]),
    ("Stack-to-Pot Ratio (SPR)", ["spr", "stack-to-pot", "stack to pot", "commitment"]),
    ("Hand Combinatorics and Blockers", ["combinatori", "combos", "combinations", "blocker"]),
    ("Breakeven Bluff Percentage / Bet Risk-Reward", ["breakeven", "risk", "reward", "bet size", "alpha"]),
    ("Equity Realization (R)", ["equity realization", "realize equity", "realiz"]),
]

SYSTEM = (
    "You are a poker mathematician and Python engineer. Given excerpts from three poker books, "
    "produce a precise, self-contained formalization of the requested concept. Return: a clear "
    "definition; the formula in LaTeX and in plain text; the variables; a SELF-CONTAINED Python "
    "function (only the standard library / 'math'); a worked numeric example as a call expression "
    "that can be eval()'d against your function; the expected result; and the source. "
    "The Python function MUST be correct and runnable as written, with a docstring."
)

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "name": {"type": "string"},
        "definition": {"type": "string"},
        "formula_latex": {"type": "string"},
        "formula_plain": {"type": "string"},
        "variables": {
            "type": "array",
            "items": {
                "type": "object", "additionalProperties": False,
                "properties": {"symbol": {"type": "string"}, "meaning": {"type": "string"}},
                "required": ["symbol", "meaning"],
            },
        },
        "function_name": {"type": "string"},
        "python_function": {"type": "string"},
        "worked_example": {
            "type": "object", "additionalProperties": False,
            "properties": {
                "inputs_description": {"type": "string"},
                "call_expression": {"type": "string"},
                "expected_result": {"type": "string"},
            },
            "required": ["inputs_description", "call_expression", "expected_result"],
        },
        "source": {"type": "string"},
        "notes": {"type": "string"},
    },
    "required": ["name", "definition", "formula_latex", "formula_plain", "variables",
                 "function_name", "python_function", "worked_example", "source", "notes"],
}


def load_pages() -> list[dict]:
    pages = []
    for book_key in config.BOOKS:
        for line in (config.TEXT_DIR / f"{book_key}.jsonl").open(encoding="utf-8"):
            pages.append(json.loads(line))
    return pages


def gather_passages(pages: list[dict], keywords: list[str], max_chars: int = 16000) -> str:
    kws = [k.lower() for k in keywords]
    out: list[str] = []
    total = 0
    for p in pages:
        low = p["text"].lower()
        if any(k in low for k in kws):
            snippet = p["text"].strip()
            if len(snippet) > 1800:
                # center on first keyword hit
                idx = min((low.find(k) for k in kws if k in low), default=0)
                start = max(0, idx - 600)
                snippet = snippet[start:start + 1800]
            tag = f"[{config.BOOK_TITLES[p['book']]} p{p['page']}]"
            block = f"{tag}\n{snippet}"
            if total + len(block) > max_chars:
                continue
            out.append(block)
            total += len(block)
    return "\n\n".join(out)


def verify(fn_code: str, call_expr: str) -> tuple[bool, str]:
    ns: dict = {"math": __import__("math")}
    try:
        exec(fn_code, ns)  # noqa: S102 — trusted local math code we just generated
        result = eval(call_expr, ns)  # noqa: S307
        return True, repr(result)
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    pages = load_pages()
    ckpt = Checkpoint(config.MATH_DIR / "math.jsonl")
    todo = [t for t in TOPICS if not ckpt.has(t[0])]
    if args.limit:
        todo = todo[: args.limit]
    print(f"{len(TOPICS)} topics | {len(ckpt.done)} done | processing {len(todo)} now")

    tot_in = tot_out = 0
    for i, (topic, kws) in enumerate(todo, 1):
        passages = gather_passages(pages, kws)
        user = (f"Concept to formalize: {topic}\n\n"
                f"Relevant book excerpts (may be noisy):\n\n{passages}\n\n"
                f"Formalize '{topic}' precisely, grounded in standard poker theory and the excerpts.")
        try:
            data, (ti, to) = openai_json(SYSTEM, user, SCHEMA, "poker_formula", max_tokens=16000)
        except Exception as e:  # noqa: BLE001
            print(f"  [{i}/{len(todo)}] {topic} ERROR: {e}")
            continue
        ok, actual = verify(data.get("python_function", ""),
                            data.get("worked_example", {}).get("call_expression", ""))
        data["verified"] = ok
        data["verify_result"] = actual
        ckpt.add(topic, {"topic": topic, "formula": data})
        tot_in += ti; tot_out += to
        print(f"  [{i}/{len(todo)}] {topic}: verified={ok} result={actual[:60]} (in={ti} out={to})")

    merged = [rec["formula"] for rec in ckpt.all()]
    (config.MATH_DIR / "math.json").write_text(
        json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")

    # also emit a single importable module with all verified functions
    lines = ['"""Verified poker math functions, extracted from the books via OpenAI gpt-5.1."""',
             "import math\n"]
    for f in merged:
        if f.get("verified"):
            lines.append(f"# {f['name']} — {f.get('source','')}")
            lines.append(f["python_function"].strip() + "\n")
    (config.MATH_DIR / "formulas.py").write_text("\n".join(lines), encoding="utf-8")
    ckpt.close()

    n_ok = sum(1 for f in merged if f.get("verified"))
    print(f"\nMerged {len(merged)} formulas ({n_ok} verified) -> math.json + formulas.py")
    print(f"Usage this run: in={tot_in:,} out={tot_out:,} tokens")


if __name__ == "__main__":
    main()
