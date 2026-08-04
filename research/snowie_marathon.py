"""MARATHON-WÄCHTER für den 2000-Hände-Lauf gegen PokerSnowie (User, 2026-08-04).

Ein nackter 6-Stunden-Prozess stirbt an irgendetwas — der Wächter nicht: er startet die Brücke in
ETAPPEN und zählt die GESPIELTEN Hände (Hole-Karten-Wechsel mit >=1 Entscheidung) selbst aus den
Session-Logs nach, bis das Ziel steht. Stirbt eine Etappe (Snowie-Dialog, Lesefehler-Serie,
MAX_STALE), startet die nächste nach kurzer Pause — der Zähler geht dabei nie verloren, weil er
aus den Logs rekonstruiert wird, nicht aus dem Prozess.

STOPPEN: die Datei data/vision/STOP anlegen (oder den Wächter-Prozess beenden). ESC stoppt nur
die laufende Etappe; der Wächter wartet dann WATCH_ESC_S und macht weiter, falls STOP fehlt.

Korrektheit bleibt Sache der Brücke: falsche Zahlen rechnen nie mit (Gatter-Kette), Unklarheiten
stehen im Etappen-Log, Aufgaben mit Beweisbild in fails/. Dieses Skript fasst nur zusammen.

  python -m research.snowie_marathon --hands 2000
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
import time

OUT = os.path.join("data", "vision")
STOP_FILE = os.path.join(OUT, "STOP")
CHUNK_HANDS = 150          # Etappenlänge: groß genug für Tempo, klein genug für frische Prozesse
PAUSE_S = 20               # Luft zwischen Etappen (Snowie kommt zur Ruhe, Ports/Handles schließen)
MAX_BARREN_CHUNKS = 5      # so viele Etappen ohne EINE neue Hand -> der Tisch ist tot -> aufgeben


def hands_in(files: list[str]) -> int:
    """Gespielte Hände = Hole-Karten-Wechsel über die Session-Logs (nur Hände mit Entscheidung)."""
    n, last = 0, None
    for f in sorted(files, key=os.path.getmtime):
        try:
            lines = open(f, encoding="utf-8").read().splitlines()
        except OSError:
            continue                       # Datei gerade im Schreiben — naechste Zaehlung sieht sie
        for ln in lines:
            try:
                cur = "".join((json.loads(ln).get("obs") or {}).get("hole") or [])
            except Exception:  # noqa: BLE001 — eine kaputte Zeile kostet keine Zaehlung
                continue
            if cur and cur != last:
                n, last = n + 1, cur
    return n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hands", type=int, default=2000)
    a = ap.parse_args()
    t0 = time.time()
    if os.path.exists(STOP_FILE):
        os.remove(STOP_FILE)
    baseline = set(glob.glob(os.path.join(OUT, "snowie_session_*.jsonl")))
    log = open(os.path.join(OUT, "marathon.log"), "a", encoding="utf-8")

    def say(msg: str) -> None:
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
        print(line, flush=True)
        log.write(line + "\n")
        log.flush()

    say(f"MARATHON-START: Ziel {a.hands} Hände (Etappen à {CHUNK_HANDS}; STOP-Datei beendet)")
    chunk, barren = 0, 0
    while True:
        new_files = [f for f in glob.glob(os.path.join(OUT, "snowie_session_*.jsonl"))
                     if f not in baseline]
        done = hands_in(new_files)
        if done >= a.hands:
            say(f"ZIEL ERREICHT: {done} Hände in {(time.time() - t0) / 3600:.1f} h")
            break
        if os.path.exists(STOP_FILE):
            say(f"STOP-Datei gefunden nach {done} Händen — Ende.")
            break
        if barren >= MAX_BARREN_CHUNKS:
            say(f"{barren} Etappen ohne neue Hand — der Tisch antwortet nicht mehr. Ende bei {done}.")
            break
        chunk += 1
        say(f"Etappe {chunk}: {done}/{a.hands} Hände — starte Brücke ({CHUNK_HANDS} Hände) ...")
        before = done
        chunk_log = os.path.join(OUT, f"marathon_chunk_{chunk:03d}.log")
        r = subprocess.run([sys.executable, "-m", "pokerbot.vision.snowie_bridge",
                            "--hands", str(CHUNK_HANDS), "--loose"],
                           stdout=open(chunk_log, "w", encoding="utf-8", errors="replace"),
                           stderr=subprocess.STDOUT)
        try:
            if "ESC" in open(chunk_log, encoding="utf-8", errors="replace").read():
                # ESC heisst ESC (User-Fund: 'stoppt nur fuer eine gewisse Zeit'): der Wille des
                # Menschen am Rechner beendet den GANZEN Marathon, nicht nur die Etappe.
                say(f"ESC in Etappe {chunk} erkannt - Marathon ENDET (Fortschritt bleibt gezaehlt).")
                break
        except OSError:
            pass
        new_files = [f for f in glob.glob(os.path.join(OUT, "snowie_session_*.jsonl"))
                     if f not in baseline]
        after = hands_in(new_files)
        say(f"Etappe {chunk} zu Ende (Exit {r.returncode}): +{after - before} Hände")
        barren = barren + 1 if after == before else 0
        time.sleep(PAUSE_S)
    log.close()


if __name__ == "__main__":
    main()
