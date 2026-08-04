"""BILDSCHIRM-REKORDER für die Snowie-Verifikation (User, 2026-08-04).

Zweck: WÄHREND die Brücke spielt, den Tisch als Zeitstempel-Frames mitschneiden. Danach wird jede
geloggte Entscheidung (snowie_session_*.jsonl, Feld ts) dem zeitlich nächsten Frame zugeordnet und
per Auge geprüft: hat der Bot GENAU das gelesen, was auf dem Tisch stand?

Frames statt Videodatei mit Absicht: einzelne Bilder lassen sich gezielt öffnen und vergleichen;
der Dateiname trägt die Unix-Zeit in Millisekunden — dieselbe Uhr wie der Entscheidungs-Log.

  python -m research.snowie_record --seconds 480
"""
from __future__ import annotations

import argparse
import os
import time

from pokerbot.vision import snowie_local as SL
from pokerbot.vision.snowie_bridge import esc_pressed

REC_DIR = os.path.join("data", "vision", "rec")
FRAME_S = 0.5              # 2 Frames/s: genug, um jeden Entscheidungsmoment zu treffen
JPEG_Q = 70                # ~120 KB/Frame — Stunden passen auf die Platte


def run(seconds: float) -> None:
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = os.path.join(REC_DIR, stamp)
    os.makedirs(out, exist_ok=True)
    print(f"Aufnahme -> {out} (ESC stoppt)", flush=True)
    t_end = time.time() + seconds
    n = 0
    while time.time() < t_end and not esc_pressed():
        t0 = time.time()
        try:
            SL.grab().convert("RGB").save(os.path.join(out, f"f_{int(t0 * 1000)}.jpg"),
                                          quality=JPEG_Q)
            n += 1
        except Exception as e:  # noqa: BLE001 — ein kaputter Frame beendet keine Aufnahme
            print("Frame-Fehler:", e, flush=True)
        time.sleep(max(0.0, FRAME_S - (time.time() - t0)))
    print(f"FERTIG: {n} Frames in {out}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=480)
    a = ap.parse_args()
    run(a.seconds)


if __name__ == "__main__":
    main()
