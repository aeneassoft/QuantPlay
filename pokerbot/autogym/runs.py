"""Run-Ablage — EINE Struktur fuer alle Autogym-Laeufe, lokal wie Pod.

data/runs/<JJJJMMTT_HHMMSS>_<name>/
  config.json    was lief (Kandidat, n, Seeds, Git-Commit, Host)
  result.json    das Urteil (bb100, se, verdict, Orakel-Zaehler)
  log.txt        stdout des Laufs
Der Index data/runs/INDEX.jsonl bekommt je Lauf eine Zeile (append-only).
"""
from __future__ import annotations

import json
import platform
import subprocess
import time
from pathlib import Path

RUNS = Path("data/runs")


def neuer_run(name: str, config: dict) -> Path:
    d = RUNS / f"{time.strftime('%Y%m%d_%H%M%S')}_{name}"
    d.mkdir(parents=True, exist_ok=False)
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                capture_output=True, text=True).stdout.strip()
    except OSError:
        commit = "?"
    config = {**config, "commit": commit, "host": platform.node(),
              "ts": time.strftime("%Y-%m-%d %H:%M:%S")}
    (d / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=1),
                                   encoding="utf-8")
    return d


def schliesse_run(d: Path, result: dict) -> None:
    (d / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1),
                                   encoding="utf-8")
    with (RUNS / "INDEX.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"run": d.name, **result}, ensure_ascii=False) + chr(10))
