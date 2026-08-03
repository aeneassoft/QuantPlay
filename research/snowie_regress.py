"""REGRESSIONSNETZ für die Snowie-Erkennung (2026-08-04).

WARUM: jede Korrektur dieser Sitzung wurde an EINEM Standbild verifiziert — und dreimal hat sich das
als Trugschluss erwiesen (ein Fix reparierte ein Feld und zerstörte ein anderes). Ein Bildschirmleser
braucht dasselbe wie jeder andere Code: einen Testsatz, gegen den JEDE Änderung sofort läuft.

  --add "pot=4,hero=218,cards=2h7c"   speichert den aktuellen Frame MIT Sollwerten
  --run                                prüft ALLE gespeicherten Frames und meldet Abweichungen
"""
from __future__ import annotations

import argparse
import json
import os

from PIL import Image

from pokerbot.vision import snowie_local as SL
from pokerbot.vision import snowie_state as SS

DIR = os.path.join("data", "vision", "snowie", "regress")
IDX = os.path.join(DIR, "cases.json")


def _cases() -> list[dict]:
    return json.loads(open(IDX, encoding="utf-8").read()) if os.path.exists(IDX) else []


def add(spec: str) -> None:
    os.makedirs(DIR, exist_ok=True)
    cases = _cases()
    name = f"case_{len(cases):03d}.png"
    SL.grab().save(os.path.join(DIR, name))
    want = {}
    for part in spec.split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            want[k.strip()] = v.strip()
    cases.append({"file": name, "want": want})
    open(IDX, "w", encoding="utf-8").write(json.dumps(cases, indent=1))
    print(f"gespeichert: {name} <- {want}")


def check(case: dict) -> list[str]:
    """-> Liste der Abweichungen (leer = bestanden)."""
    img = Image.open(os.path.join(DIR, case["file"]))
    st = SS.read_state(img)
    bad = []
    w = case["want"]
    if "cards" in w:
        got = "".join(c or "??" for c in st["hero_cards"])
        if got.lower() != w["cards"].lower():
            bad.append(f"Karten {got} != {w['cards']}")
    if "board" in w:
        got = "".join(st["board"])
        if got.lower() != w["board"].lower():
            bad.append(f"Board {got} != {w['board']}")
    for key, path in (("pot", lambda s: s["pot"]), ("hero", lambda s: s["stacks"].get("hero")),
                      ("call", lambda s: s["call_amount"]), ("pos", lambda s: s["hero_position"])):
        if key in w:
            got = path(st)
            exp = w[key]
            ok = (str(got) == exp) or (got is not None and exp not in ("None", "") and
                                       str(got) == str(float(exp)) if exp.replace(".", "").isdigit() else False)
            if not ok:
                bad.append(f"{key} {got} != {exp}")
    if w.get("gate") == "ok" and SS.gate(st):
        bad.append(f"Gatter blockiert: {SS.gate(st)}")
    return bad


def run() -> int:
    cases = _cases()
    if not cases:
        print("Keine Faelle — erst mit --add anlegen.")
        return 0
    fails = 0
    for c in cases:
        bad = check(c)
        print(f"  {'FAIL' if bad else 'ok  '}  {c['file']}  {'; '.join(bad)}")
        fails += bool(bad)
    print(f"REGRESSION: {len(cases) - fails}/{len(cases)} bestanden")
    return fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--add")
    ap.add_argument("--run", action="store_true")
    a = ap.parse_args()
    if a.add:
        add(a.add)
    else:
        run()


if __name__ == "__main__":
    main()
