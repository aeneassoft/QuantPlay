# AUTOGYM_PLAN.md — die selbstprüfende Trainings-Schleife (beschlossen 2026-08-16)

**Ziel: an die GTOW-Baseline herankommen.** Referenz = das validierte **−19,70 ± 4,37 bb/100**
(PRINCE v2.2, n=2.393). Treppe, vorregistriert: −19,70 → **−15** → **−10** → Leaderboard-Band.
Jede Stufe wird vs GTOW gemessen (in-process, $0), nie aus Self-Play extrapoliert.

**Doktrin: lokal bewiesen, dann skaliert.** Überall vorregistrierte Erwartungen; getroffen = bereit.
Der Pod (RunPod, CPU-lastig — CFR/Self-Play braucht Kerne, keine GPU) kommt erst nach E1–E5.

## Architektur (gebaut, `pokerbot/autogym/`)

| Modul | Rolle |
|---|---|
| `oracle.py` | die vereinheitlichte Mathematik-Benchmark: Formelsammlung → Urteile (HART / P / L / F) |
| `gym_hu.py` | Prince-HU-Self-Play, gepaarte Decks mit Button-Tausch (Karten+Position kürzen sich) |
| `gym_six.py` | 6-max-Self-Play, frischer Tisch je Hand, Positions-Ledger |
| `improver.py` | minen → patchen → gepaartes Gate → Journal (`data/autogym/journal.jsonl`) |
| `selftest.py` | der lokale Beweis der Schleife (E1–E4, ein Kommando) |

## Der Sicherheits-Kontrakt — „Mathematik automatisch optimieren, ohne Fehler"

Modular heißt hier: **jede Schicht hat einen anderen Änderbarkeits-Status**, und die Schleife
kann nur anfassen, was ihr Status erlaubt.

1. **Formeln sind unveränderlich.** Eine Formel (`knowledge_base/math/*.py`, 78 Funktionen) wird
   nie automatisch editiert. Verdrahtet wird sie erst, wenn sie eine **unabhängige
   Fraction-Referenz** besteht (E1; Prüfer getrennt vom Geprüften — test_math_suite-Kultur).
2. **Orakel-Knöpfe sind Mess-Konfiguration** (LEAD_MARGIN, MDF_BAND, EQ_ITERS): für den Improver
   **gesperrt**. Eine Schleife, die die Toleranzen ihres eigenen Messgeräts tunen darf,
   optimiert das Messgerät statt des Bots (Goodhart). Änderung nur von Hand, mit Begründung.
3. **Bot-Knöpfe sind das Tuning-Gebiet** (z. B. `value_raise_eq`, Flag-Profile), jeder mit
   deklarierten Schranken. Vorschlag frei — **Anwendung nur durchs gepaarte A/B-Gate**.
4. **P-Patches sind Wrapper, nie Quelltext-Edits** — und auch der beweisbare Patch muss das Gate
   passieren (Bestehensgrenzen vorregistriert: ANWENDEN > 2·SE, VERWERFEN < −1 bb/100).
5. **Nichts geschieht still.** Jede Runde, jeder Vorschlag, jedes Urteil → Journal.

## Die Erwartungs-Leiter (vorregistriert; PASS = bereit für die nächste Stufe)

| | Erwartung | Schwelle | Stand |
|---|---|---|---|
| **E1** | Orakel-Wahrheit: jede verdrahtete Formel vs unabhängige Fraction-Referenz | 7/7 exakt | `selftest` |
| **E2** | Symmetrie: Paar-Drift des gesunden Bots im Selbstspiel | \|Drift\| < 2·SE | `selftest` |
| **E3** | Detektor: konstruierter Defekt-Bot (Station) wird erkannt UND im Gate verworfen | Lead-Rate ≥ 2× gesund; Gate = ANWENDEN für gesund | `selftest` |
| **E4** | Null-Stabilität: gesund vs gesund erzeugt **kein** ANWENDEN (keine erfundenen Verbesserungen) | 0 Fehl-Patches | `selftest` |
| **E5** | Durchsatz lokal: Pilot gemessen 500 Hände + 3.577 gegradete Entscheidungen in 52 s (~580 Hände/min) | Pod-Erwartung ≥ 10.000 Hände/min auf 64 Kernen, sonst lohnt er nicht | Pilot ✓, Pod offen |
| **E6** | **GTOW-Anker:** jeder Kandidat mit lokalem ANWENDEN wird vs GTOW gemessen | nicht schlechter als das −19,70-Band; Treppe −15 → −10 | offen |

E6 ist die einzige Stufe, die zählt — E1–E5 existieren, damit E6-Messungen nie auf einer
kaputten Schleife stehen.

## Verdrahtungs-Backlog (Orakel-Manifest führt live Buch)

v0 verdrahtet: `equity_needed_to_call` (L), `minimum_defense_frequency` (F), Chip-Erhaltung
(HART), `free_fold` (P). Offen: die übrigen der **78 Formelfunktionen** (12 formulas + 34
postflop + 32 strategy), die sympy-verifizierten Calc-JSONs und die 443
Mathematics-of-Poker-Chunks. Die Vollinventur (Welle-1-Checks, Welle-2-Gym-Erweiterungen,
Nicht-verdrahtbar-Liste, Knob-Register) läuft als Panel; Ergebnis wird hier eingetragen.

## Erste Messwerte (Pilot 2026-08-16, lokal, 52 s)

HU 300 Hände: HART 0 · P 0 · L 35 (Rückschau-Calls bis 112 bb unter Pot-Odds) · F 1 ·
Button-Netto +32,6 bb/100 (kartenbereinigter Positionswert = neue Benchmark-Größe) ·
Paar-Drift +294 ± 195 (1,5 SE, verträglich mit 0 — mehr Paare nötig). 6-max 200 Hände:
HART 0 · P 0 · F 2 (u. a. mdf_flop). Gate-Selbsttest exploit-OFF vs ON: +2,1 ± 3,3 → NEUTRAL.
