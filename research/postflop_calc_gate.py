"""Gate the GPT-5.5-generated post-flop calculations — the EV-truth filter extended to pure math (CLAUDE.md: frontier
= prior, ENGINE = truth). For each spec: exec its `python_function`, evaluate its `verify_expr`, and KEEP it only if the
result matches `verify_value` within tolerance. Writes the verified subset + a reject report.

Run: python -m research.postflop_calc_gate
"""
from __future__ import annotations

import itertools
import json
import math
import sys
from fractions import Fraction

from pokerbot import config

_BASE = sys.argv[1] if len(sys.argv) > 1 else "postflop_calc"   # also gates strategy_calc (same schema)
SRC = config.KNOWLEDGE_DIR / "math" / f"{_BASE}.json"
OUT = config.KNOWLEDGE_DIR / "math" / f"{_BASE}_verified.json"

_ALLOWED_MODS = {"math": math, "itertools": itertools, "fractions": __import__("fractions"),
                 "typing": __import__("typing")}


def _safe_import(name, *a, **k):                                          # whitelist: only math/itertools/fractions
    root = name.split(".")[0]
    if root in _ALLOWED_MODS:
        return _ALLOWED_MODS[root]
    raise ImportError(f"import '{name}' not allowed in the gate")


_SAFE_BUILTINS = {f.__name__: f for f in (
    min, max, abs, round, sum, len, sorted, range, float, int, bool, str, list, dict, tuple,
    enumerate, zip, any, all, map, filter, divmod, pow, set, frozenset, reversed, set)}
_SAFE_BUILTINS.update({"True": True, "False": False, "None": None, "__import__": _safe_import})


def gate_one(calc: dict, tol: float = 1e-6):
    """(ok, value, error). exec the function, eval the self-check, compare to verify_value."""
    g = {"__builtins__": _SAFE_BUILTINS, "math": math, "itertools": itertools, "Fraction": Fraction}
    try:
        exec(calc.get("python_function", ""), g)                         # noqa: S102 — our own generated math, gated
        val = eval(calc.get("verify_expr", ""), g)                       # noqa: S307
        if isinstance(val, bool):
            val = int(val)
        want = float(calc.get("verify_value"))
        ok = abs(float(val) - want) <= tol * max(1.0, abs(want))
        return ok, float(val), None
    except Exception as e:  # noqa: BLE001
        return False, None, f"{type(e).__name__}: {e}"


def main():
    if not SRC.exists():
        print(f"no {SRC} yet (run research.postflop_calc_consult first)")
        return
    data = json.loads(SRC.read_text(encoding="utf-8"))
    calcs = data.get("calculations", [])
    kept, rejects = [], []
    for c in calcs:
        ok, val, err = gate_one(c)
        if ok:
            kept.append(c)
        else:
            rejects.append((c.get("name", "?"), err or f"got {val} != {c.get('verify_value')}"))
    OUT.write_text(json.dumps({"calculations": kept}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"GATE: {len(kept)}/{len(calcs)} post-flop calcs verified -> {OUT}")
    from collections import Counter
    print("verified by category:", dict(Counter(c.get("category", "?") for c in kept)))
    if rejects:
        print(f"\nREJECTED {len(rejects)} (engine could not confirm):")
        for nm, why in rejects[:40]:
            print(f"  - {nm}: {why[:90]}")


if __name__ == "__main__":
    main()
