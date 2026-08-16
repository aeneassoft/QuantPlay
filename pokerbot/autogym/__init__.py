"""AUTOGYM — das selbstpruefende Trainings-System (lokal zuerst, Pod spaeter).

Vier Teile, bewusst getrennt (User-Design 2026-08-16):
  oracle.py    die vereinheitlichte Mathematik-Benchmark (Formelsammlung -> Urteile)
  gym_hu.py    Prince-HU-Self-Play mit Buchfuehrung (gepaarte Decks)
  gym_six.py   6-max-Self-Play mit Buchfuehrung
  improver.py  die Verbesserungs-Schleife: minen -> patchen -> Gate -> Urteil

Einstieg:  python -m pokerbot.autogym.run_local
"""
