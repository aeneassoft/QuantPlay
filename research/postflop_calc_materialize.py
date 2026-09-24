"""Materialize the ENGINE-VERIFIED post-flop calcs (postflop_calc_verified.json) into ONE importable module
`knowledge_base/math/postflop_formulas.py`, then re-verify ALL of them TOGETHER (catches name collisions the per-spec
gate can't). The module is the callable library the engine-API wraps for the brain. Per docs/plans/math_accuracy_strategy.md.

Run: python -m research.postflop_calc_materialize
"""
from __future__ import annotations

import importlib.util
import json
import sys

from pokerbot import config

_BASE = sys.argv[1] if len(sys.argv) > 1 else "postflop_calc"   # also materializes strategy_calc -> strategy_formulas
SRC = config.KNOWLEDGE_DIR / "math" / f"{_BASE}_verified.json"
OUT = config.KNOWLEDGE_DIR / "math" / f"{_BASE.replace('_calc', '_formulas')}.py"

_HEADER = ('"""Post-flop NLHE calculations — GPT-5.5-generated, ENGINE-VERIFIED (each self-check passes; gate +\n'
           'materialize in research/postflop_calc_*). Pure stdlib. The callable library the engine-API exposes to the\n'
           'brain. Regenerate via `python -m research.postflop_calc_materialize`. Per docs/plans/math_accuracy_strategy.md."""\n'
           "from __future__ import annotations\n\n"
           "import itertools  # noqa: F401\n"
           "import math  # noqa: F401\n"
           "from fractions import Fraction  # noqa: F401\n"
           "from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union  # noqa: F401\n\n\n")


def main():
    calcs = json.loads(SRC.read_text(encoding="utf-8")).get("calculations", [])
    seen, bodies, names = set(), [], []
    for c in calcs:
        fn = c.get("function_name")
        if fn in seen:                                          # de-dup repeated function names (keep first)
            continue
        seen.add(fn)
        names.append(fn)
        bodies.append(c["python_function"].strip())
    all_line = "__all__ = " + json.dumps(names) + "\n\n\n"   # so `from postflop_formulas import *` exposes exactly these
    OUT.write_text(_HEADER + all_line + "\n\n\n".join(bodies) + "\n", encoding="utf-8")

    spec = importlib.util.spec_from_file_location(_BASE.replace("_calc", "_formulas"), OUT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)                                # import the materialized module
    ok = 0
    for c in calcs:
        try:
            val = eval(c["verify_expr"], vars(mod))             # noqa: S307 — verified, our own code
            val = int(val) if isinstance(val, bool) else val
            want = float(c["verify_value"])
            if abs(float(val) - want) <= 1e-6 * max(1.0, abs(want)):
                ok += 1
            else:
                print(f"  MISMATCH {c['name']}: {val} != {want}")
        except Exception as e:  # noqa: BLE001
            print(f"  ERROR {c['name']}: {type(e).__name__}: {str(e)[:70]}")
    callables = sum(1 for n in names if callable(getattr(mod, n, None)))
    print(f"materialized {len(names)} functions -> {OUT}")
    print(f"module re-verify (together): {ok}/{len(calcs)} | importable callables: {callables}/{len(names)}")


if __name__ == "__main__":
    main()
