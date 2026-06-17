"""Self-growing MATH — the OpenAI math pipeline wired INTO the active-learning loop (PC-hub side).

When the brain repeatedly fails a spot-cluster because it lacks the right formula (a math gap the monitor surfaces),
`grow_math(request)` consults GPT-5.5 for the new EXACT formulas, GATES each against the engine (frontier = prior,
ENGINE = truth — `research/postflop_calc_gate`), merges the VERIFIED ones into the callable toolkit, and re-materializes
`postflop_formulas.py` — so the NEXT pod cycle's brain can call them as `api.<fn>`. This is "compute new mathematics as
the loop needs it", made a primitive.

HARD RULE (CLAUDE.md): this runs on the PC HUB ONLY. The pod RL NEVER calls a frontier API. The monitor (which polls
the pod's eval for weak clusters) is the trigger; the new math flows into the dataset/toolkit for the next run, never
into the live pod. Reuses the proven consult -> gate -> materialize pipeline.

Run (manual): python -m pipeline.math_loop "Generate exact formulas for <the gap>."
"""
from __future__ import annotations

import json
import subprocess
import sys

from pokerbot import config
from research.llm import openai_json
from research.postflop_calc_consult import SCHEMA, SYSTEM
from research.postflop_calc_gate import gate_one

TOOLKIT = config.KNOWLEDGE_DIR / "math" / "postflop_calc.json"


def grow_math(request: str, model: str = "gpt-5.5", max_tokens: int = 16000, consult=None) -> dict:
    """Consult for new formulas -> gate vs the engine -> merge the verified+new into the toolkit -> re-materialize.
    `consult(SYSTEM, request, SCHEMA)` is injectable for offline tests (default = the real GPT-5.5 call). PC-hub only."""
    if consult is None:
        data, _toks = openai_json(SYSTEM, request, SCHEMA, "grown_calc", model=model, max_tokens=max_tokens)
    else:
        data = consult(SYSTEM, request, SCHEMA)
    gen = data.get("calculations", [])
    verified = [c for c in gen if gate_one(c)[0]]                       # engine = truth
    existing = (json.loads(TOOLKIT.read_text(encoding="utf-8")).get("calculations", [])
                if TOOLKIT.exists() else [])
    have = {c.get("function_name") for c in existing}
    added = [c for c in verified if c.get("function_name") not in have]
    TOOLKIT.write_text(json.dumps({"calculations": existing + added}, indent=2, ensure_ascii=False), encoding="utf-8")
    for mod in ("research.postflop_calc_gate", "research.postflop_calc_materialize"):
        subprocess.run([sys.executable, "-m", mod], cwd=str(config.ROOT), capture_output=True)   # re-gate + materialize
    return {"generated": len(gen), "verified": len(verified), "added": len(added),
            "toolkit_size": len(existing) + len(added)}


if __name__ == "__main__":
    req = sys.argv[1] if len(sys.argv) > 1 else "Generate 3 EXACT post-flop NLHE formulas the toolkit likely lacks."
    print(json.dumps(grow_math(req), indent=2))
