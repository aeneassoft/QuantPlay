# V8-POSTMORTEM — warum die Play-Stufe keinen messbaren Vorteil brachte

**Datum:** 2026-09-01 · **Entscheid:** v8 (r9_v8 = Solver-PLAY + stackoff_bremse auf der v5-Kette)
wird NICHT getauft; `auslese-v5` (FINAL_STACK = r8_stack) bleibt der Stand. User-Entscheid nach
Vorlage der Zwischenverdikte; dieser Report ist die angeforderte Ursachen-Analyse.

## 1. Die Messlage (alle Läufe 12 Worker, A/A-gesichert, gepaarte Decks)

| Vergleich | n Decks | bb/100 | 95%-CI | Verdikt |
|---|---|---|---|---|
| r9_play vs r8_stack (v5) | 30.000 | **+1,14 ± 2,78** | [−4,1; +6,3] | NEUTRAL |
| r9_v8-A/A | 576 | exakt 0,0 | — | Messung sauber |
| r9_v8 vs r8_stack, Lauf 1 | 30.000 | **+3,91 ± 2,85** | [−1,9; +9,5] | NEUTRAL |
| r9_v8 vs r8_stack, Lauf 2 | 14.976 | **−1,23 ± 4,36** | [−9,9; +7,0] | NEUTRAL |
| gepoolt (invers-varianz) | ~45k | **≈ +2,3 ± 2,4** | — | null bis schwach positiv |

(Lauf 3 + Treppe vs v4/basis beim Drop-Entscheid abgebrochen. Run-Ablagen:
`data/runs/20260831_*_pargate_r9_*` + `data/runs/v8_kette_rest_*.log`.)

Zum Kontrast die GTOW-Achsen-Evidenz derselben Play-Komponente (Replay auf den echten
Nacht-2-Händen, `research/v8_replay_gegentest.py`): 32 Eingriffe/3904 Entscheidungen,
Fold-Kontrafaktik **netto +278,6bb**, mehrfach AIVAT-konvergent (#2991749 AIVAT −52,2 →
Solver-check; #2993037 AIVAT −33,1 → Solver-raise). Beide Messungen sind konsistent —
sie messen verschiedene Achsen.

## 2. Warum kein Vorteil im Gate-Kanal — vier Ursachen

**(a) Kanal-Sättigung: die Chirurgie hatte die Mirror-Ernte schon eingefahren.**
Der v5-Sprung (+27,6 ± 1,8 vs v4) kam aus den seltenen, teuren Klarfällen — Big-Pot-Desaster
mit ~17bb je Divergenz-Deck. Play unterscheidet sich von der Chirurgie NUR zwischen den
Schwellen (0,10 < p_basis < 0,70): feine Size-Korrekturen, marginale Misch-Entscheidungen.
Genau dort ist der Solver aber (fast) indifferent — beide Seiten der Mischung tragen ähnlichen
EV. Der Mirror kann nur klare Fehler bepreisen, und die waren mit v5 bereits weggeräumt.
Messbar: v8-Divergenzen hatten nz_median **1,9bb** gegenüber **11,6bb** bei der v5-Chirurgie —
zehnmal kleinere Korrekturen.

**(b) Die Selfplay-Ökologie bestraft Feinpräzision nicht.**
Value-Raise statt Call, halbierte Fehl-Size, gerettete Overfolds — diese Gewinne existieren
gegen einen Gegner, der die feinere Politik ausnutzt bzw. bezahlt. Der Spiegel-Gegner
(v5-Familie) ist kein Re-Solver: er exploitiert weder Size-Muster noch Mix-Fehler. Dies ist
dieselbe Zwei-Achsen-Lektion wie bei r6_ecall (Mirror −4,15, GTOW-relevant) und r7_bill
(Mirror exakt 0) — diesmal auf der Bet-Seite.

**(c) Die Stichproben-Arithmetik seltener Grenzfälle.**
Play-Mehreingriffe über die Chirurgie hinaus: <1% der Entscheidungen; im Gym ~3% Divergenz-
Decks mit ~2bb-Medianen. Ein kleiner Effekt × neutraler Spiegel-Erwartungswert ist bei 45k
Decks (SE ~2,4) statistisch unsichtbar; eine Bestätigung von +2 bräuchte >150k Decks — für
einen Effekt, der in diesem Kanal strukturell klein ist. Das Messbudget gehört dann nicht
mehr in diesen Kanal.

**(d) Komplexitäts- und Latenz-Kosten bei Gleichstand.**
v8 = v5 im einzigen Kanal, der hier entschieden hat — aber mit mehr Code im heißen Pfad,
mehr GPU-Latenz pro River-Spot und einem zusätzlichen (gemessen einmal gecrashten,
dann gegateten) Aktions-Zweig. Bei Gleichstand gewinnt die einfachere Version (Ockham,
und die Clean-Code-Disziplin des Repos).

## 3. Ehrliche Rest-Unsicherheit

Es bleibt MÖGLICH, dass v8 gegen GTOW real besser wäre — die Replay-Evidenz deutet darauf,
und der Spiegel kann diese Frage prinzipiell nicht beantworten. Unbewiesen ist es, solange
kein Anker läuft. Falls je gewünscht: der billigste Beweis wäre ein GTOW-A/B **v5 vs
v5+play** (je ~2500 Hände, Protokoll fertig in `data/runs/gtow_v8_protokoll_2026-08-31.json`,
Arm-Konfiguration nur um POKERB_AUSLESE_STACK=r9_play zu ergänzen). Bis dahin gilt der
konservative Schluss des Drops.

## 4. Was die Runde trotzdem eingebracht hat (bleibt im Repo)

- **Bestätigung von v5:** drei weitere A/A-exakt-0-Beweise und ~45k Decks, in denen v5 von
  einer aggressiveren Variante nicht geschlagen wurde.
- **Instrumente:** `research/v8_replay_gegentest.py` (parametrischer Guard-Gegentest auf
  echten GTOW-Händen), `research/gpu_river_audit.py`, das GTOW-v8-Protokoll.
- **Default-OFF-Arme** (gebaut, registriert, nicht getauft): `r9_play` (inkl. Legalitäts-
  Gatter), `r9_turn` (TurnCFR-Chirurgie), `stackoff_bremse`; jederzeit re-testbar.
- **Negative Ergebnisse mit Erklärung:** no_limp (−11,42: die Basis limpt ~39% strategisch —
  Limp-Pot-*Verteidigung* wäre der richtige Kandidat, nicht Limp-Streichung); turn_gpu
  (3/3904 Eingriffe = zu leise für Evidenz); play (Kanal-Sättigung, dieser Report).
- **Prozess-Lehren:** bash-Ketten-Stopp killt nur das aktive Glied (Prozessfamilie killen);
  Solver-Aktionen brauchen Legalitäts-Gatter gegen all-in-Gegner; Erwartungsbänder vor
  jedem Lauf ins Journal.

## 5. Stand nach dem Drop

`auslese-v5` bleibt FINAL_STACK (Tag ec11fde): Mirror-Treppe +27,6 ± 1,8 vs v4, +30,6 ± 5,0
vs Basis, GPU-Chirurgie live-smoke-grün. Der vorbereitete GTOW-Anker (Arm B1 = v5) wartet
auf User-Kommando.
