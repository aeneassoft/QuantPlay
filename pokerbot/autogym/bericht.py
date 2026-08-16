"""STAND-Bericht — Laeufe + Journal zu EINER lesbaren Seite (data/runs/STAND.md).

  python -m pokerbot.autogym.bericht
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    zeilen = ["# AUTOGYM-STAND", ""]
    idx = Path("data/runs/INDEX.jsonl")
    if idx.exists():
        zeilen += ["## Laeufe", "", "| Lauf | Kandidat | bb/100 | SE | n | Verdikt |", "|---|---|---|---|---|---|"]
        for line in idx.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            zeilen.append(f"| {r.get('run','?')} | {r.get('kandidat','-')} | {r.get('bb100','-')} "
                          f"| {r.get('se','-')} | {r.get('n_decks','-')} | {r.get('verdict','-')} |")
    j = Path("data/autogym/journal.jsonl")
    if j.exists():
        zeilen += ["", "## Journal (letzte 15)", ""]
        for line in j.read_text(encoding="utf-8").splitlines()[-15:]:
            r = json.loads(line)
            zeilen.append(f"- [{r.get('ts','')}] {r.get('typ','')} {r.get('regel','')}: "
                          f"{r.get('verdict','')} {r.get('bb100','')}")
    out = Path("data/runs/STAND.md")
    out.write_text(chr(10).join(zeilen) + chr(10), encoding="utf-8")
    print(chr(10).join(zeilen))
    print(f"{chr(10)}-> {out}")


if __name__ == "__main__":
    main()
