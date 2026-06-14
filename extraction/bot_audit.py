"""Independent Claude audit of the bot's DECISION code for LLM-introduced flaws.

Sends the strategy files (with line numbers) to Claude Opus and asks it to flag — strictly, with
justification — magic numbers / wrong weightings / cargo-cult heuristics / misplay risks. The prompt
hard-constrains AGAINST inventing problems (prefer false negatives). Output is vetted by hand afterwards.

Run:  python -m extraction.bot_audit
"""
from __future__ import annotations

import json

import anthropic

from pokerbot import config

FILES = [
    "pokerbot/strategy/bot.py",
    "pokerbot/strategy/postflop.py",
    "pokerbot/strategy/gto_baseline.py",
    "pokerbot/strategy/opponent.py",
    "pokerbot/strategy/adaptive.py",
]

SYSTEM = (
    "You are a world-class heads-up No-Limit Hold'em theorist AND a senior Python engineer, auditing a "
    "poker bot's decision code. Much of it was generated with LLM help, so it may contain ARBITRARY magic "
    "numbers, uncalibrated thresholds, wrong weightings, cargo-cult 'poker' heuristics that are not real "
    "GTO/exploit theory, and logic that can misplay or spew chips.\n\n"
    "Your job: find the REAL, concrete, defensible problems. Be rigorous and skeptical.\n"
    "CRITICAL RULES:\n"
    "1. DO NOT invent problems. If something is sound, do not flag it. Prefer FALSE NEGATIVES over false "
    "positives — a wrong flag is worse than a missed one.\n"
    "2. Every finding MUST be justified by concrete poker theory (MDF, pot odds, polarization, range "
    "advantage, ICM-free cash EV, indifference) or a concrete logic/bug argument — not vibes.\n"
    "3. Focus on issues that MATERIALLY change EV or cause misplays. Ignore style/naming.\n"
    "4. If a constant is a reasonable heuristic given the bot has no solver, say so and do NOT flag it.\n"
    "5. Rate your own confidence honestly; if you are unsure, lower the confidence or omit it."
)

INSTRUCTIONS = (
    "Audit the decision code below (line numbers are prefixed as `NNN| `). Return STRICT JSON only:\n"
    '{\n'
    '  "findings": [\n'
    '    {"file": "...", "lines": "e.g. 218 or 218-224", "code": "the exact suspect snippet",\n'
    '     "category": "magic_number|wrong_weighting|misplay_risk|inconsistency|hallucinated_heuristic",\n'
    '     "severity": "high|med|low", "confidence": 0.0-1.0,\n'
    '     "issue": "one sentence: what is wrong",\n'
    '     "why": "poker-theoretic or logical justification",\n'
    '     "fix": "concrete, minimal suggested change"}\n'
    '  ],\n'
    '  "overall": "2-3 sentence honest assessment; explicitly say if the code is mostly sound"\n'
    '}\n'
    "Sort findings by (severity, confidence) descending. Cap at the 15 most important. "
    "Return ONLY the JSON, no prose around it."
)


def _numbered(path: str) -> str:
    text = (config.ROOT / path).read_text(encoding="utf-8")
    lines = text.splitlines()
    return "\n".join(f"{i+1:4d}| {ln}" for i, ln in enumerate(lines))


def main() -> None:
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    blocks = []
    for f in FILES:
        blocks.append(f"\n\n===== FILE: {f} =====\n{_numbered(f)}")
    user = INSTRUCTIONS + "\n" + "".join(blocks)

    print(f"Auditing {len(FILES)} files via {config.CLAUDE_MODEL} ...", flush=True)
    msg = client.messages.create(
        model=config.CLAUDE_MODEL, max_tokens=8000,
        system=SYSTEM,
        messages=[{"role": "user", "content": user}],
    )
    raw = "".join(b.text for b in msg.content if b.type == "text").strip()
    out = config.DATA_DIR / "sessions" / "bot_audit.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(raw, encoding="utf-8")

    # pretty-print a triage table
    try:
        data = json.loads(raw[raw.index("{"):raw.rindex("}") + 1])
    except (ValueError, json.JSONDecodeError) as e:
        print(f"(could not parse JSON: {e}) — raw saved to {out}")
        print(raw[:2000])
        return
    print(f"\n=== OVERALL: {data.get('overall','')}\n")
    fs = data.get("findings", [])
    print(f"{len(fs)} findings (sev | conf | file:lines | category):")
    for x in fs:
        print(f"  [{x.get('severity','?'):4}] c={x.get('confidence','?'):<4} "
              f"{x.get('file','?').split('/')[-1]}:{x.get('lines','?'):8} {x.get('category','?')}")
        print(f"        {x.get('issue','')}")
    print(f"\nFull JSON -> {out}")


if __name__ == "__main__":
    main()
