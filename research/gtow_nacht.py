"""GTOW-Nachtlauf (2026-08-18): 4x500-Chunks mit Retry + vorregistriertem Checkpoint.

Arm A (v4): AUSLESE-Stack r6_button + TURN_DEFENSE/SLOWPLAY/RAISE_NARROW, resolver-OFF.
Arm K (Kontrolle): PRINCE v2.2 resolver-ON = die -30,11-Referenzkonfig (Key #3).
CHECKPOINT (vorregistriert, Journal): Smokes 20/100 poolten ~-53+-12 (2 Sigma unter
dem Anker -25..-30, v8-Muster). Ist nach Chunk 1 das v4-Pool (Smokes+Chunk1)
<= -45, wechseln die Rest-Chunks auf K -> die Nacht liefert den erklaerenden A/B
statt 2000 Haenden auf einem moeglicherweise gebrochenen Arm.
Jeder Chunk: bis 3 Versuche; vor Retry clear_inprogress (409-Housekeeping).
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY = open(r"C:/Users/hampe/Desktop/Secret keys/Poker/GTOW API key #3.txt", encoding="utf-8").read().strip()

ARM_V4 = {"POKERB_AUSLESE_STACK": "r6_button", "POKERB_TURN_DEFENSE": "0.07",
          "POKERB_SLOWPLAY": "0.25", "POKERB_RAISE_NARROW": "1.0",
          "POKERB_RESOLVER": "0", "POKERB_TURN_RESOLVER": "0"}
ARM_K = {"POKERB_PRINCE": "1"}                     # Resolver default ON im Harness

# Smoke-Vorlast des v4-Arms (heute Nacht, Journal): n=20 @ -21.34, n=100 @ -59.03
V4_VORLAST = [(20, -21.34), (100, -59.03)]
CHECKPOINT = -45.0


def _lauf(env_extra: dict, n: int) -> tuple[int, float] | None:
    env = {k: v for k, v in os.environ.items() if not k.startswith("POKERB_")}
    env.update({"GTOWIZARD_API_KEY": KEY, "PYTHONUTF8": "1"})
    env.update(env_extra)
    p = subprocess.run([sys.executable, "tools/gtow_run.py", "--agent_type", "pokerbot",
                        "--num_hands", str(n)], cwd=REPO, env=env,
                       capture_output=True, encoding="utf-8", errors="replace", timeout=7200)
    out = p.stdout + p.stderr
    m = re.findall(r"AIVAT luck-adj : ([+-]?\d+\.\d+) \+/- [\d.]+ bb/100  \(n=(\d+)\)", out)
    if p.returncode == 0 and m:
        val, nn = float(m[-1][0]), int(m[-1][1])
        return nn, val
    print(f"CHUNK-FEHLER rc={p.returncode}; letzte Zeilen:\n" + "\n".join(out.splitlines()[-5:]), flush=True)
    return None


def _clear() -> None:
    subprocess.run(["uv", "run", "python", "clear_inprogress.py"],
                   cwd=os.path.join(REPO, "tools", "gtow_client", "src"),
                   env={**os.environ, "GTOWIZARD_API_KEY": KEY}, timeout=1200)


def _pool(teile: list) -> float:
    n = sum(t[0] for t in teile)
    return sum(t[0] * t[1] for t in teile) / max(1, n)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.path.insert(0, REPO)
    from pokerbot.autogym.improver import _journal
    _journal({"typ": "GTOW-NACHT-VORREGISTRIERUNG", "regel": "checkpoint_chunk1",
              "erwartung": f"4x500; Checkpoint: v4-Pool (Smokes {V4_VORLAST} + Chunk1) <= {CHECKPOINT} "
                           "-> Rest-Chunks auf Kontrolle PRINCE-resolver-ON (-30,11-Referenz)."})
    v4_teile = list(V4_VORLAST)
    k_teile: list = []
    arm, arm_name = ARM_V4, "v4"
    for chunk in range(1, 5):
        res = None
        for versuch in range(1, 4):
            print(f"== Chunk {chunk}/4 Arm {arm_name} Versuch {versuch} ==", flush=True)
            try:
                res = _lauf(arm, 500)
            except Exception as e:  # noqa: BLE001
                print("Ausnahme:", repr(e), flush=True)
                res = None
            if res:
                break
            _clear()
            time.sleep(60 * versuch)
        if not res:
            print(f"Chunk {chunk} nach 3 Versuchen aufgegeben — weiter.", flush=True)
            _journal({"typ": "GTOW-NACHT-CHUNK", "chunk": chunk, "arm": arm_name, "status": "FEHLGESCHLAGEN"})
            continue
        (v4_teile if arm_name == "v4" else k_teile).append(res)
        _journal({"typ": "GTOW-NACHT-CHUNK", "chunk": chunk, "arm": arm_name,
                  "n": res[0], "aivat": res[1]})
        print(f"Chunk {chunk} [{arm_name}]: AIVAT {res[1]:+.2f} (n={res[0]})", flush=True)
        if chunk == 1 and _pool(v4_teile) <= CHECKPOINT:
            arm, arm_name = ARM_K, "kontrolle"
            print(f"CHECKPOINT AUSGELOEST: v4-Pool {_pool(v4_teile):+.2f} <= {CHECKPOINT} "
                  f"-> Wechsel auf Kontrolle.", flush=True)
    fazit = {"typ": "GTOW-NACHT-FAZIT",
             "v4_pool_aivat": round(_pool(v4_teile), 2), "v4_n": sum(t[0] for t in v4_teile),
             "kontrolle_pool_aivat": round(_pool(k_teile), 2) if k_teile else None,
             "kontrolle_n": sum(t[0] for t in k_teile)}
    _journal(fazit)
    print("NACHT FERTIG:", fazit, flush=True)


if __name__ == "__main__":
    main()
