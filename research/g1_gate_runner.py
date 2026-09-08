"""G1 Gate-Laeufer (v10, docs/V10_BUILD_CARD.md G1) — fuehrt die Invarianten-/Test-Kommandos der Karte NACHEINANDER
als Subprozesse aus und protokolliert jede Ausgabe woertlich nach data/runs/v10/G1_tests.txt (+ G1_summary.json).

Nur Messung, kein Strategie-Code. Jeder Block traegt Kommando, Exit-Code, Dauer, Zeitstempel; die Ausgabe wird
1:1 angehaengt, damit jede Zahl im Bericht per (Datei + Kommando) zitierbar ist.

Aufruf (Repo-Root):  PYTHONUTF8=1 python -u -m research.g1_gate_runner
Konventionen: subprocess IMMER encoding='utf-8' (cp1252-Falle, CLAUDE.md); Shell-POKERB_* werden gestrippt
(Gate-Kanal-Hygiene wie pargate), PYTHONUTF8=1 gesetzt; Tests, die eine Env brauchen, bekommen sie explizit.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "runs" / "v10"
LOG = OUT_DIR / "G1_tests.txt"
SUMMARY = OUT_DIR / "G1_summary.json"
PY = sys.executable

# (Name, Kommando, Zusatz-Env, Timeout s). Reihenfolge: kurz -> lang, GPU-Suiten zuletzt.
KOMMANDOS: list[tuple[str, list[str], dict[str, str], int]] = [
    ("pytest_versuch", [PY, "-m", "pytest", "tests/test_hero_range.py", "tests/test_river_plan.py",
                        "tests/test_river_br_pruefstand.py", "tests/test_runtime_config.py",
                        "tests/test_gtow_nacht_v10.py", "tests/test_river_strategy_identity.py", "-q"], {}, 600),
    ("test_gtow_nacht_v10", [PY, "-u", "-m", "tests.test_gtow_nacht_v10"], {}, 600),
    ("test_runtime_config", [PY, "-u", "-m", "tests.test_runtime_config"], {}, 900),
    ("test_river_strategy_identity", [PY, "-u", "-m", "tests.test_river_strategy_identity"], {}, 600),
    ("test_hero_range", [PY, "-u", "-m", "tests.test_hero_range"], {}, 900),
    ("test_game", [PY, "-u", "-m", "tests.test_game"], {}, 600),
    ("test_bot", [PY, "-u", "-m", "tests.test_bot"], {}, 900),
    ("test_range_tracker", [PY, "-u", "-m", "tests.test_range_tracker"], {}, 600),
    ("test_math_suite", [PY, "-u", "-m", "tests.test_math_suite"], {}, 900),
    ("contracts_selbsttest", [PY, "-u", "-m", "pokerbot.strategy.contracts"], {}, 600),
    ("gtowizard_offline_selbsttest", [PY, "-u", "-m", "pokerbot.benchmark.gtowizard"], {}, 600),
    ("hu_app_smoke_testclient_v5H", [PY, "-u", "-m", "tests.test_runtime_config", "--server"],
     {"POKERB_ERWARTE_PROFIL": "v5-H"}, 900),
    ("hu_app_smoke_fehlkonfig_v10_muss_abbrechen", [PY, "-u", "-m", "tests.test_runtime_config", "--server"],
     {"POKERB_ERWARTE_PROFIL": "v10"}, 900),
    ("test_integration_v10", [PY, "-u", "-m", "tests.test_integration_v10"], {}, 900),
    ("test_river_plan", [PY, "-u", "-m", "tests.test_river_plan"], {}, 1800),
    ("test_river_br_pruefstand", [PY, "-u", "-m", "tests.test_river_br_pruefstand"], {}, 2400),
]


def _env(extra: dict[str, str]) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("POKERB_")}
    env["PYTHONUTF8"] = "1"
    env.update(extra)
    return env


def _lauf(name: str, cmd: list[str], extra: dict[str, str], timeout: int) -> dict:
    t0 = time.perf_counter()
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        p = subprocess.run(cmd, cwd=str(ROOT), env=_env(extra), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        rc, out, err = p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired as e:
        rc, out, err = -999, (e.stdout or ""), (e.stderr or "") + f"\n[TIMEOUT nach {timeout}s]"
    dauer = time.perf_counter() - t0
    kopf = (f"\n{'=' * 100}\n### {name}\n### Kommando: {' '.join(cmd)}\n### Zusatz-Env: {extra or '{}'}\n"
            f"### Start: {stamp}  Dauer: {dauer:.1f}s  Exit: {rc}\n{'=' * 100}\n")
    with LOG.open("a", encoding="utf-8") as f:
        f.write(kopf)
        f.write("--- STDOUT ---\n" + out + "\n--- STDERR ---\n" + err + "\n")
    print(f"[{stamp}] {name}: exit={rc} dauer={dauer:.1f}s", flush=True)
    return {"name": name, "kommando": " ".join(cmd), "env": extra, "exit": rc, "dauer_s": round(dauer, 1),
            "stdout_tail": out[-600:], "stderr_tail": err[-600:]}


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    git = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=str(ROOT), capture_output=True, text=True,
                         encoding="utf-8").stdout.strip()
    dirty = subprocess.run(["git", "status", "--short"], cwd=str(ROOT), capture_output=True, text=True,
                           encoding="utf-8").stdout
    with LOG.open("w", encoding="utf-8") as f:
        f.write(f"G1 GATE — Invarianten/Tests (docs/V10_BUILD_CARD.md G1)\nStart {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"Python {sys.version.split()[0]}  HEAD {git}  dirty-Zeilen {len(dirty.splitlines())}\n"
                f"Treiber: research/g1_gate_runner.py  (Shell-POKERB_* gestrippt: "
                f"{sorted(k for k in os.environ if k.startswith('POKERB_'))})\n")
    ergebnisse = [_lauf(*k) for k in KOMMANDOS]
    SUMMARY.write_text(json.dumps({"head": git, "start": ergebnisse and time.strftime("%Y-%m-%d"),
                                   "laeufe": ergebnisse}, indent=1, ensure_ascii=False), encoding="utf-8")
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"\n{'#' * 100}\nENDE {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        for e in ergebnisse:
            f.write(f"{e['name']:48s} exit={e['exit']:>4}  dauer={e['dauer_s']:>7.1f}s\n")
    print("FERTIG", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
