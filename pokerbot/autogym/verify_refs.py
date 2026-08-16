"""AP7 — der verify_expr-Runner: alle Referenzen der verifizierten Calc-JSONs
gegen die INSTALLIERTEN Formelmodule ausfuehren.

Wichtig fuer die Ehrlichkeit: verify_expr/verify_value stammen aus derselben
Erzeugung wie die Formeln (Konsistenz, nicht Wahrheit — test_math_suite-Doktrin).
Dieser Runner prueft deshalb etwas anderes, Wertvolles: dass die HEUTE im Repo
liegenden .py-Funktionen noch exakt das rechnen, was bei der sympy-Verifikation
festgeschrieben wurde — ein Drift-/Regressions-Netz ueber alle 66 Formeln.
Die 9 unabhaengigen Fraction-Referenzen in selftest.E1 bleiben die Wahrheits-Stufe.

  python -m pokerbot.autogym.verify_refs
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from knowledge_base.math import postflop_formulas, strategy_formulas

QUELLEN = [
    ("knowledge_base/math/postflop_calc_verified.json", postflop_formulas),
    ("knowledge_base/math/strategy_calc_verified.json", strategy_formulas),
]
TOL = 1e-9


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    total = passed = missing = 0
    fails: list[str] = []
    for path, mod in QUELLEN:
        rows = json.load(open(Path(path), encoding="utf-8"))["calculations"]
        for r in rows:
            expr, want = r.get("verify_expr"), r.get("verify_value")
            if not expr or want is None:
                continue
            total += 1
            fn = r.get("function_name", "?")
            if not hasattr(mod, fn):
                missing += 1
                fails.append(f"FEHLT   {fn} ({path})")
                continue
            try:
                got = eval(expr, {"__builtins__": {}}, vars(mod))  # Ausdruecke aus dem eigenen Repo
            except Exception as e:
                fails.append(f"FEHLER  {fn}: {e}")
                continue
            if isinstance(got, (list, tuple)):
                ok = all(abs(a - b) < TOL for a, b in zip(got, want)) and len(got) == len(want)
            else:
                ok = abs(got - want) < TOL
            if ok:
                passed += 1
            else:
                fails.append(f"DRIFT   {fn}: {got!r} vs festgeschrieben {want!r}")
    print(f"verify_refs: {passed}/{total} exakt, {missing} fehlend, {len(fails) - missing} Drift/Fehler")
    for f in fails:
        print("  " + f)
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
