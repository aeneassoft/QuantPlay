"""GTOW-Nachtlauf v2 (2026-08-18, ~04:10): der ECHTE finale Bot + eingebauter A/B.

Befund der ersten Nachthaelfte (Journal GTOW-NACHT-BERGUNG): die nackte
Gym-Konfig (exploit-ON, resolver-OFF) verlor -38,9 (n=1617), 81% davon am RIVER
im alten Jam-Spew-/Station-Muster — dem Kanal fehlten Resolver + GTO-Disziplin.

NEUER PLAN (User-Kommando): der finale Bot WIE GEGEN DIE BASIS GEBAUT
(AUSLESE-Guard-Kette r6_button(turn_wert(sel_m15))) auf dem validierten
Live-Fundament: POKERB_PRINCE=1 (bringt TURN_DEFENSE 0.07 + SLOWPLAY 0.25 +
GTO-Mode-Basis inkl. exploit-OFF/Census) + Resolver-ON (Harness-Default).
OHNE RAISE_NARROW (resolver-ON kontraindiziert, v8-K3 — einzige Abweichung
vom Gym-Stack, regelkonform). Chunk 1 = KONTROLLE (PRINCE pur, resolver-ON =
die -30,11-Referenz) -> der A/B liegt in derselben Nacht/Session.
STAPEL-RISIKO (journalisiert): turn_wert_guard kann Resolver-Checks (Slowplay-
Mix) ueberschreiben — genau das prueft der A/B.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY = open(r"C:/Users/hampe/Desktop/Secret keys/Poker/GTOW API key #3.txt", encoding="utf-8").read().strip()

ARM_KONTROLLE = {"POKERB_PRINCE": "1"}
ARM_V4_PRINCE = {"POKERB_PRINCE": "1", "POKERB_AUSLESE_STACK": "r6_button"}
PLAN = [("kontrolle", ARM_KONTROLLE), ("v4_prince", ARM_V4_PRINCE),
        ("v4_prince", ARM_V4_PRINCE), ("v4_prince", ARM_V4_PRINCE)]


def _lauf(env_extra: dict, n: int) -> tuple[int, float] | None:
    env = {k: v for k, v in os.environ.items() if not k.startswith("POKERB_")}
    env.update({"GTOWIZARD_API_KEY": KEY, "PYTHONUTF8": "1"})
    env.update(env_extra)
    p = subprocess.run([sys.executable, "tools/gtow_run.py", "--agent_type", "pokerbot",
                        "--num_hands", str(n)], cwd=REPO, env=env,
                       capture_output=True, encoding="utf-8", errors="replace", timeout=10800)
    out = (p.stdout or "") + (p.stderr or "")
    m = re.findall(r"AIVAT luck-adj : ([+-]?\d+\.\d+) \+/- [\d.]+ bb/100  \(n=(\d+)\)", out)
    if p.returncode == 0 and m:
        return int(m[-1][1]), float(m[-1][0])
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
    _journal({"typ": "GTOW-NACHT2-VORREGISTRIERUNG", "regel": "v4_prince_ab",
              "erwartung": "Chunk 1 Kontrolle PRINCE-resolver-ON (Erwartung ~-30,11-Referenzband); "
                           "Chunks 2-4 v4_prince = AUSLESE-Guards + PRINCE + Resolver-ON ohne RN. "
                           "Hypothese: v4_prince deutlich besser als die -38,9 der Gym-Nackt-Konfig; "
                           "ob >= Kontrolle, entscheidet der A/B. Stapel-Risiko turn_wert x Slowplay-Mix "
                           "beobachten (River-/Turn-Verlustanteile im HH-Mining)."})
    ergebnisse: dict[str, list] = {}
    for i, (arm_name, arm) in enumerate(PLAN, 1):
        res = None
        for versuch in range(1, 4):
            print(f"== Chunk {i}/{len(PLAN)} Arm {arm_name} Versuch {versuch} ==", flush=True)
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
            _journal({"typ": "GTOW-NACHT2-CHUNK", "chunk": i, "arm": arm_name, "status": "FEHLGESCHLAGEN"})
            continue
        ergebnisse.setdefault(arm_name, []).append(res)
        _journal({"typ": "GTOW-NACHT2-CHUNK", "chunk": i, "arm": arm_name, "n": res[0], "aivat": res[1]})
        print(f"Chunk {i} [{arm_name}]: AIVAT {res[1]:+.2f} (n={res[0]})", flush=True)
    fazit = {"typ": "GTOW-NACHT2-FAZIT"}
    for arm_name, teile in ergebnisse.items():
        fazit[f"{arm_name}_aivat"] = round(_pool(teile), 2)
        fazit[f"{arm_name}_n"] = sum(t[0] for t in teile)
    _journal(fazit)
    print("NACHT2 FERTIG:", fazit, flush=True)


if __name__ == "__main__":
    main()
