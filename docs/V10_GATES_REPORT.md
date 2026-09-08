# V10 GATES-REPORT — Synthese der Gate-Laeufer G1–G5 (2026-09-07/08)

**Zweck:** eine Seite, die den Ship-Entscheid fuer v10 („River-Fundament", `docs/V10_BUILD_CARD.md`) traegt.
Jede Zahl traegt ihre Quelle (Datei + Kommando). Kein Strategie-Code wurde von den Gate-Laeufern
veraendert; keine git-Commits. Zeitfenster der Messungen: 2026-09-07 22:00 → 2026-09-08 01:41.

**Arme:** A = v5-H (`r8_stack`, PRINCE, exploit OFF, TexasSolver ON) · B = v10 (`r10_stack` = K1-Hero-Range +
K2-oeffentlicher River-Plan statt `river_gpu_guard`). Kanal-Vokabular (Karte E2): **Gym** = pargate-Kanal
(exploit ON, kein PRINCE, Resolver AUS) = Integritaets-/Nichtverschlechterungs-Schranke, NIE Ship-Evidenz;
**Live** = PRINCE + Resolver ON = der GTOW-Kanal.

---

## 1. Gate-Tabelle

| Gate | Status | Kennzahl (gemessen) | Schwelle (Karte) | Quelle (Datei · Kommando) |
|---|---|---|---|---|
| **G1** Invarianten/Tests | **GRUEN (Evidenz zusammengesetzt)** | 13 Test-/Smoke-Bloecke, alle exit 0: hero_range 19/19 (Σ=1 ≤1e-6, Invarianz, Guard-Transformation vs Enumeration ≤1e-6), river_plan 27/28 (1 uebersprungen: Latenz-Hartgrenze wegen fremder GPU-Last), runtime_config 19 OK (1 skip „E5 NICHT LIVE"), gtow_nacht_v10 31/31, river_strategy_identity 20/20, integration_v10 4/4, contracts 250 gruen, game/bot/range_tracker/math_suite 20/20 OK; HU-App-Smoke v5-H gruen + Fehlkonfig-Gatter v10-auf-r8 bricht korrekt ab (exit 1); Golden-Set r8 vs basis pre == post (IDENTISCH). **K3-Kontrollen** (Matching Pennies / Karten-Fixture ≤1e-6 / A/A exakt 0 / Oracle-Identitaet 60/60) **15/15 gruen** | alle gruen; pytest-Kommando ausfuehrbar | `data/runs/v10/G1_tests.txt` (Bloecke `### …`) · `python -u -m research.g1_gate_runner`; K3-Kontrollen aus `data/runs/v10/g4_logs/kontrollen_tests.log` (22:15:13) · `python -u -m tests.test_river_br_pruefstand`. **Luecke:** der G1-Runner hat den Block `test_river_br_pruefstand` NICHT geschrieben (Log endet bei test_river_plan 22:14:36; `G1_summary.json` fehlt) — die Evidenz stammt aus dem G4-Lauf derselben Code-Version. `python -m pytest …` → exit 1 „No module named pytest" (Ersatz: Modul-Runner, identischer Testumfang) |
| **G2a** A/A + Golden nach Code-Aenderung | **BESTANDEN** | pargate A/A r10 vs r10, **576 Decks: bb100 0.0, se 0.0, nonzero 0/576** (Bank 1090000, 212,9 s); Golden-A/A 40 Decks nonzero 0; r8-vs-basis pre == post_g2a IDENTISCH; Trace: k1_fallback 0/4, k1_likelihood 4/4 | A/A EXAKT 0; Golden identisch | `data/runs/20260907_220348_pargate_r10_stack/{result,config,edges}.json` · `python -u -m pokerbot.autogym.pargate --kandidat r10_stack --incumbent r10_stack --decks 600 --workers 12 --seed 1 --deck-seed0 1090000`; `data/runs/v10/golden_r10_AA_v2.json`, `golden_r8_vs_basis_post_g2a.json`, `G2a_zusammenfassung.json` |
| **G2** Latenz/Ausfuehrung Live-Kanal | **NICHT GRUEN — VERFEHLT (Tendenz) bei reduzierter Stichprobe n=10** | Plan-Pot p99(=max) v10 **7,55 s** (nominell < 8) · Gesamt-p99 v10 **7,55 s > v5-H 5,54 s** auf identischen 10 Zustaenden → Kriterium 2 verfehlt · 0 Aufrufe ≥ 30 s · **K2-Trace: Plan gespielt 1/10, deadline 7/10, hand_not_in_range 2/10** | Plan-Pot p99 < 8 s UND Gesamt-p99 v10 ≤ v5-H UND kein Aufruf ≥ 30 s; ≥ 500 geschichtete Aufrufe (Auftrag ≥ 150/Arm, ≥ 50 Plan-Pots) | `data/runs/v10/G2_latenz_probe10.json` (`gate_urteil.status` = `VERFEHLT_REDUZIERTE_STICHPROBE`), `G2_latenz_probe10_roh_A.jsonl`, `_roh_B.jsonl`, `G2_latenz_probe10_k2trace_B.jsonl` · `python -u -m research.v10_latenz --probe 10 --n 150` |
| **G3** K1-Oracle-Abnahme (TV) | **VERFEHLT** | Hauptlauf 64 VG / 145 Knoten / je Guard-Klasse ≥ 16 (button 16, sel_m15 18, turn_wert 18), S=12: TV K1 vs Orakel **mittel 0,2085 · p95 0,758 · max 0,876**; Orakel-Rauschboden mittel 0,095; **untere Schranke (TV − Floor) mittel 0,1446 · p95 0,620 · max 0,819** → ueber ALLEN drei Budgets auch nach Rausch-Abzug; Klassenebene (Aktionsklasse statt Size) mittel 0,1037 — ebenfalls ueber Budget; 21/64 Faelle untere Schranke > 0,10; `urteil_roh` = verfehlt, `urteil_budget` = orakel_zu_grob; Rekonstruktions-Fehler 0, hero_injiziert 0, Hero-Hole ausserhalb K1-Support 21/64 | TV mittel ≤ 0,02 · p95 ≤ 0,05 · max ≤ 0,10; ≥ 64 VG, ≥ 128 Knoten, jede Guard-Klasse ≥ 16× | `data/runs/v10/g3_k1_gate_20260907_231422.json` (Felder `tv_k1_vs_orakel`, `tv_k1_korrigiert_untere_schranke`, `urteil_*`), Log `g3_k1_gate_run.log` · `python -u -m research.g3_k1_gate --zensus-n 300 --n 64 --je-klasse 16 --seeds 12 --workers 8 --zeitbudget-s 4200`; Zensus `g3_census_20260907_221523.json`; Pilot (n=6, S=64) `k1_oracle_20260907_190257.json` |
| **G4** Holdout-Pruefstand (K3) | **UNVOLLSTAENDIG** (n=11 < 20 Roots; Kriterium auf n=11 erfuellt, aber Gym-Kanal) | ΔE_H = w(A)−w(B) **−10,08 ± 1,66 bb/Root = −113,0 ± 18,6 bb/100** (Bootstrap-OG95 −85,4), alle 11 Roots negativ (= B weniger ausbeutbar); ΔR als B-Nachteil **−4,04 ± 0,99 bb/100** (OG95 −2,61; B in 11/11 Roots geringerer Regret); Sensitivitaet Villain=Preflop-Null: ΔE_H −126,2 ± 16,8, gleiches Vorzeichen; UNSUPPORTED 0/11; Tail-Root 2981435 Δ −22,7 bb (dichterer Baum NICHT gerechnet); Kontrollen 15/15 | einseitige 95 %-OG ΔE_H ≤ +0,5 UND ΔR ≤ +0,5 bb/100, eine < 0; Vollstatus ≥ 20 Roots; Arm A = v5-Politik (Live) | `data/runs/v10/G4_holdout.json` + `.md`, `G4_pruefstand_holdout_gym_tracker.json`, `G4_pruefstand_holdout_gym_preflop.json`, `G4_pilot_live_2981343.json` (Live-Pilot UNSUPPORTED) · `python -u -m research.river_br_pruefstand --split holdout --arm-a oracle --kanal gym --seeds 4 --workers 8 --roots 224 --zeitbudget-s 5400 --name G4_pruefstand_holdout_gym_tracker`; Auswertung `python -m research.g4_auswertung --haupt … --sens … --name G4_holdout` |
| **G5** Spiegel 2000 Decks + Analyzer-Export | **BESTANDEN** (mit Befund + reduziertem Export) | r10 vs r8, **n=1968 Decks: +11,68 ± 10,85 bb/100**, CI95 [−9,39, +33,06], verdict NEUTRAL, perm_p 0,156, Trim 0,00; Divergenz 114/1968 (5,8 %); Katastrophen |Edge| ≥ 150 bb: 1 negativ (Deck 1226 −153 bb) + 1 positiv (Deck 336 +161 bb), 1,65 % der Summe; Replay 23/23 deterministisch; Export 200/200 Haende CRLF-sauber (IDs 130000–130199, Tag 90, Seed 1109) | nicht < −10 mit CI komplett negativ; klar negativer Befund → Untersuchung; Export 1500 Haende | `data/runs/20260908_002035_pargate_r10_stack/{config,result,edges}.json` · `python -u -m pokerbot.autogym.pargate --kandidat r10_stack --incumbent r8_stack --decks 2000 --workers 12 --seed 1 --deck-seed0 1110000`; `data/runs/v10/G5_BERICHT.json`, `g5_spiegel_auswertung.json`, `g5_divergenz_replay.log`; Export `data/gtow_upload/hu_v10_r10_stack_200.txt` (+ `_konfig.json`, `_selektion.txt`); Ledger `data/runs/v10/g5_analyzer_ledger.json` |

---

## 2. Reduktionen gegenueber der Karte (Power ehrlich)

| Gate | Karte verlangt | Gefahren | Folge fuer die Power |
|---|---|---|---|
| G1 | `python -m pytest …` | pytest nicht installiert → Modul-Runner derselben sechs Dateien (19+28+15+19+31+1 Tests) | Testumfang identisch; das Karten-Kommando bleibt unausfuehrbar (Karte umschreiben oder pytest installieren) |
| G1 | K3-Kontrollen im G1-Lauf | G1-Runner schrieb den Block nicht (Lauf endete nach test_river_plan); Evidenz aus dem G4-Kontrolllauf 22:15 (15/15) | Inhaltlich gedeckt (gleiche Code-Version, keine Aenderung an `river_br_pruefstand.py` danach); formal ein zusammengesetzter Nachweis |
| G1 | Fault-Injection Timeout/503/Prozessabbruch | Prozessabbruch + Ledger-Write-Fault getestet; Timeout/503 nur als String-Klassifikation/Mock — KEIN echter Injektionstest in Adapter/Harness | Luecke bleibt offen (Befund B6) |
| G2 | ≥ 500 geschichtete Aufrufe (Auftrag ≥ 150 je Arm, ≥ 50 Plan-Pots) | **n=10 je Arm, nur Plan-Pots** (Probe); Vollmessung `--messe --n 150 --plan-min 50` (~15 min) NICHT gestartet (Bericht vom Orchestrator erzwungen) | p99 = Maximum; kein Gate-Urteil moeglich — die Tendenz (7,55 > 5,54; Plan 1/10) ist replikationspflichtig |
| G2 | Live-Haende mit gsr-Uebersetzung, 8 parallele Haende | Zustaende aus dem Entwicklungs-Split (Nacht 2), sequentiell, `PokerBotAgent._decide` direkt | Queue-Deadline-Effekt live eher STAERKER als gemessen |
| G3 | Orakel-Floor ≤ 0,01 (Werkzeug-Vorbedingung) | S=12 Seeds statt ~256 (Hochrechnung S=256 ≈ 20 h, S=12 = 55 min) → Floor 0,095 | Ein „im_budget" waere auf Exakt-Ebene NICHT nachweisbar gewesen; ein „verfehlt" ist ueber die untere Schranke (TV − Floor) robust — und genau das trat ein (mittel 0,1446 > 0,02) |
| G3 | natuerliche Stichprobe | stratifiziert: erste 16 VG je Guard-Klasse + 20 „keine" = 64 | Gesamt-Mittel ueberrepraesentiert Guard-Faelle (konservativ nach oben); Klassen-Kennzahlen unverzerrt je Klasse — und JEDE Klasse liegt einzeln ueber Budget (untere Schranke mittel: button 0,123 · keine 0,083 · sel_m15 0,092 · turn_wert 0,325) |
| G3 | Abnahme getrennt je Kanal (E3: Gym + Live) | nur Gym (`k1_oracle --kanal gtow` → SystemExit „nicht verdrahtet") | Live-TV unbekannt; nach P1-Meldung eher groesser (PRINCE/LINE_U/Turn-Resolver aendern P(bet)) |
| G4 | Arm A = v5-Politik LIVE; ≥ 20 Roots (Vollstatus); Entwicklungs-Split; Tail gegen dichteren Baum | Arm A im **Gym**-Kanal (Live-Pilot: `UNSUPPORTED` durch REACH_EPS-Inkonsistenz + 473 s fuer den schmalsten Root); **11 Roots** (Zeitbudget 5400 s; voller Holdout 224 Roots ≈ 33 h kalt, Cache setzt fort: 313 Knoten-Tabellen fp 01baf241872c); Entwicklungs-Split nicht gerechnet; Tail-Root nicht nachgeprueft | Deltas messen v5-GYM vs Plan, NICHT v5-H vs Plan → Betrag (−113 bb/100) NICHT auf Live uebertragbar (live spielt TexasSolver 93 % der River-Entscheidungen); Richtung robust ueber zwei Villain-Familien; Power SE 18,6 (ΔE_H) / 0,99 (ΔR) bb/100 |
| G5 | 2000 Decks; Export 1500 Haende | 1968 Decks (48 Jobs × 41); **Export 200 statt 1500** (11,6 s/Hand im PRINCE-Live-Kanal, TexasSolver-Waits; 500er nach 98 Haenden abgebrochen, Identitaet nicht verbrannt); Divergenz-Replay nach 23/114 Decks gestoppt (56 % der Summe |Edge|) | SE 10,85 statt ~10,76 (egal); Analyzer-SE ≈ 2,7× breiter als bei 1500 → Mechanik-/Tail-/Stichproben-Grade, KEIN EV-loss-Vergleich gegen die 1500er-Anker; Vollprogramm-Kommando mit frischer Identitaet 132000/91/1110 steht in G5_BERICHT.json (~2,2–4,8 h) |
| Mess-Disziplin | eine Worker-Flotte zur Zeit | G1/G2a/G3/G4 liefen teils PARALLEL (G4-Pilot GPU + g3-Zensus waehrend G1; G4-Hauptlauf waehrend G3) | Latenz-Anhang von test_river_plan kontaminiert (nicht zitiert); G3-Orakelzeiten sind Obergrenzen; Korrektheits-/Determinismus-Zahlen unberuehrt |

---

## 3. Befunde und Risiken (priorisiert)

**R1 — G3 VERFEHLT, strukturell (Karte: „Verfehlt → K2 NICHT frei").** Die K1-Hero-Range weicht vom
decide()-Orakel auf Exakt-Ebene (finale Chips) mit mittlerer TV 0,21 ab; auch nach Abzug des Orakel-
Rauschens bleibt die untere Schranke bei 0,145 (Budget 0,02), max 0,82 (Budget 0,10). URSACHE gemessen:
das Advisor-Likelihood-Backend ist groessenagnostisch (V10_FAKTEN B8), die Basis waehlt Sizes hand-
abhaengig — der Pilot zeigte auf Aktionsklassen-Ebene noch 0,0035, der Hauptlauf aber auch dort 0,104
(turn_wert-Klasse 0,147, „keine" 0,111): die Abweichung ist NICHT nur Size-Information. Groesster Treiber:
turn_wert-Faelle (untere Schranke mittel 0,325). Quelle: `g3_k1_gate_20260907_231422.json`.

**R2 — G2: der River-Plan wird live kaum gespielt (Probe 1/10).** Nach EINER 7,5-s-Deadline laeuft der Solve
im einzigen Solve-Thread weiter (`river_plan.py` LIVE_SOLVE_WORKER=1, QUEUE_BUDGET_S=0,5), die Folge-
Entscheidungen scheitern am 0,5-s-Queue-Budget → Status `deadline` 7/10, `hand_not_in_range` 2/10. Damit ist
v10 im Live-Kanal in ~90 % der Plan-Pots die NACKTE Basis (r6_button + wert_bremse OHNE river_gpu_guard) —
genau die Konfiguration, die in G5 alle drei Decks ≤ −100 bb erzeugt hat (R4). Zusaetzlich Gesamt-p99 v10
7,55 s > v5-H 5,54 s. Quelle: `G2_latenz_probe10_k2trace_B.jsonl`, `G2_latenz_probe10.json`. n=10 —
replikationspflichtig ueber `--messe --n 150 --plan-min 50`.

**R3 — K1 Range-Kollaps-Leck.** Hero-Hole ausserhalb des K1-Supports (Masse 0): 21/64 im G3-Hauptlauf,
12,2 % im Integrations-Selbstplay, 2/10 in der G2-Probe. Im K2-Pfad bedeutet das `hand_not_in_range` →
Basis; button_disziplin-Faelle (Karte: „Prior UNVERAENDERT") zeigen im Orakel eine reale Selektion (Support
354 vs 838 Combos) — die Karte ist an dieser Stelle MESSBAR inkonsistent (Reviewer-Befund bestaetigt).

**R4 — G5-Obduktion: die Grossverluste kommen aus dem Fallback, nicht aus dem Plan.** Alle drei Decks ≤ −100 bb
(1226/1308/1677) entstehen in der nackten Basis: 2× `offtree` (Villain-Basis-Size 900/1660 trifft den
0,35/0,75/1,5-Baum nicht → Basis jammt/callt), 1× Sub-Schwellen-Pot (928 < 1500) ohne Chirurgie. Off-Tree-
Quote in den 23 groessten Divergenz-Decks: 20/48 Plan-Pot-Entscheidungen (42 %). Die 3 reinen Plan-Decks
sind alle positiv (+219 bb). Design-Frage an den Integrator: Fallback-Ziel = r8-Chirurgie statt nackter
Basis (neuer Hash → G2 wiederholen). Quelle: `g5_divergenz_replay.log`, `g5_katastrophen_trace.jsonl`.

**R5 — G4 nur Gym, nur 11 Roots.** Richtung konsistent (B in 11/11 Roots weniger ausbeutbar UND weniger Regret,
robust ueber zwei Villain-Familien), aber gegen v5-GYM ohne TexasSolver gemessen; der Live-Pilot faellt
durch die Werkzeug-Inkonsistenz REACH_EPS (Befund 1 im G4-Bericht) auf `UNSUPPORTED`. Vorzeichen-Konvention
von `delta_regret` (R(A)−R(B)) im Pruefstand widerspricht der Gate-Lesart — vor einem Vollstatus im
Werkzeug vereinheitlichen (Befund 2).

**R6 — K5-Kanal fuer `illegal` fehlt (blockiert das G6-Verdikt).** `legalisiert:<von>-><nach>` + Fingerprint-Feld
`legalisierung_ledger` existieren in `gtowizard.py`/`runtime_config.py`/`gtow_ledger.py` nicht (grep 0
Treffer) → jede Nacht endet mit `kein_verdikt`. E5-Patch (`poker_agent.py:74` act_dict synchron) NICHT
angewandt. Quelle: G1-Bericht B7/B8, `docs/V10_LEDGER_PATCH.md`.

**R7 — Hygiene.** pargate-Fortsetzbarkeit ohne Code-Fingerprint (Block-Ordner nur fuer den JETZIGEN Code
gueltig); Selbsttests schreiben prozess_start-Ledger nach `data/runs/v10/` (via `POKERB_LEDGER_PFAD`
umlenken); STATE.md-Hand-ID-Ledger um 130000–130199/Tag 90/Seed 1109 zu ergaenzen (naechster freier
Vorschlag 132000/91/1110).

**Positiv (gesichert):** A/A EXAKT 0 auf 576 + 40 + 10 Decks nach der letzten Code-Aenderung (river_plan.py
mtime 21:56:19); E7-Isolation haelt (r8_stack/basis byte-identisch pre == post); Sampling-Test 10k Seeds
gruen; Chip-Erhaltung/Legalitaet 300 Haende; K4-Gatter bricht Fehlkonfig korrekt ab; Fingerprints beider
Arme == Profil (A eee8af7010cd / B b31771f55a39).

---

## 4. SHIP-ENTSCHEID-VORLAGE (nach Karte)

Regel: v10 ist GTOW-reif NUR wenn **G1 gruen UND G2 gruen UND G3 im TV-Budget UND G4-Kriterium erfuellt UND
G5 ohne Katastrophe**. Karte zusaetzlich: „G3 verfehlt → K2 NICHT frei"; „nach G4 keine Strategiekorrektur
im selben Release; jede Aenderung = neuer Hash, Gates wiederholen".

| Bedingung | Stand | Erfuellt? |
|---|---|---|
| G1 gruen | alle Bloecke gruen; K3-Kontrollen 15/15 (aus G4-Lauf) | JA (zusammengesetzt) |
| G2 gruen | n=10: Gesamt-p99 7,55 > 5,54 s verfehlt; Plan gespielt 1/10; Vollmessung fehlt | **NEIN** |
| G3 im TV-Budget | untere Schranke mittel 0,1446 > 0,02, p95 0,620 > 0,05, max 0,819 > 0,10 | **NEIN — VERFEHLT** |
| G4-Kriterium erfuellt | auf n=11 erfuellt (OG95 −85,4 / −2,61 ≤ +0,5), aber Gym-Kanal, n < 20 | UNVOLLSTAENDIG |
| G5 ohne Katastrophe | +11,68 ± 10,85, 1 neg./1 pos. Deck ≥ 150 bb, symmetrisch | JA |

### ENTSCHEID: **v10 (`r10_stack`) ist NICHT GTOW-reif.**

**Genauer Grund (bindend nach Karte):** G3 ist VERFEHLT — die K1-Hero-Range verletzt das TV-Budget auf allen
drei Kennzahlen auch nach Abzug des Orakel-Rauschens (mittel 0,1446 / p95 0,620 / max 0,819 vs
0,02 / 0,05 / 0,10; `data/runs/v10/g3_k1_gate_20260907_231422.json`), damit ist K2 laut Karte NICHT frei.
Unabhaengig davon ist G2 nicht gruen: auf identischen Zustaenden Gesamt-p99 v10 7,55 s > v5-H 5,54 s, und
der Plan wurde in der Probe nur in 1/10 Plan-Pots gespielt (7/10 `deadline`; `G2_latenz_probe10.json`,
`G2_latenz_probe10_k2trace_B.jsonl`). G4 ist unvollstaendig (11/20 Roots, Gym statt Live).

**Konsequenz:** Kein Tag `auslese-v10-rc`, keine GTOW-Staffel (G6) mit diesem Artefakt. Der GTOW-Stand bleibt
**auslese-v5 (Tag ec11fde) = FINAL_STACK `r8_stack`** = Arm A/v5-H. Die Staffel in Abschnitt 5 ist NUR fuer
den Fall dokumentiert, dass ein NEUER Hash alle Gates besteht.

**Was ein Re-Release braeuchte (Reihenfolge nach Karte, jede Aenderung = neuer Hash → G2a A/A + G1–G5 neu):**
1. K1: Size-bewusstes Likelihood-Backend (oder Orakel-Kalibrierung je Size-Arm) + Klaerung button_disziplin
   (Prior „unveraendert" ist messbar falsch); Ziel G3 untere Schranke ≤ 0,02/0,05/0,10; K1-Support-Leck (21/64).
2. K2: Fallback-Ziel = r8-Chirurgie statt nackter Basis in Plan-Pots und Sub-Schwellen-Eskalationen; Solve-
   Worker/Queue-Budget so, dass eine Deadline nicht die Folge-Haende blockiert; Off-Tree-Abbildung der
   Villain-Sizes (42 % `offtree`).
3. K5/K4: Legalisierungs-Kanal + E5-Patch, sonst `kein_verdikt` per Konstruktion.
4. G2 Vollmessung (`python -u -m research.v10_latenz --messe --n 150 --plan-min 50`), G4 Fortsetzung ueber den
   Oracle-Cache bis n ≥ 20 (Rest ≈ 1,5–2 h fuer Roots 12–20) + Live-Kanal nach REACH_EPS-Fix.

---

## 5. GTOW-Staffel — exakte Kommandos (NUR nach bestandenen Gates; aus `python -m research.gtow_nacht_v10 --help`)

Muenze: `data/runs/v10_muenze.json` = `BAAB_dann_ABBA` (2026-09-07 16:47:57) → **Nacht 1 = B A A B**
(v10, v5-H, v5-H, v10; Paare (1,2),(3,4)), **Nacht 2 = A B B A**. Arme (Env je Chunk, alle anderen POKERB_* gestrippt):
A = `POKERB_PRINCE=1 POKERB_AUSLESE_STACK=r8_stack POKERB_ERWARTE_PROFIL=v5-H`;
B = `POKERB_PRINCE=1 POKERB_AUSLESE_STACK=r10_stack POKERB_ERWARTE_PROFIL=v10`; zusaetzlich `POKERB_ARM`,
`POKERB_K2_TRACE=<Manifest-Dir>/k2_trace/…`. Der Treiber ruft VOR jedem Start Ledger-Abgleich + `clear_inprogress`
(409-Waisen-Pflicht) selbst auf. Manifest: `data/runs/v10/gtow_manifest_v10.json`.

```
# Vorbedingungen: Tag auslese-v10-rc gesetzt; Legalisierungs-Kanal + E5-Patch live (sonst kein_verdikt)
PYTHONUTF8=1 python -u -m research.gtow_nacht_v10 --plan                 # druckt Sequenz + Env, startet NICHTS
PYTHONUTF8=1 python -u -m research.gtow_nacht_v10 --smoke 20  --arm B    # Smoke 20 (v10)
PYTHONUTF8=1 python -u -m research.gtow_nacht_v10 --smoke 100 --arm B    # Smoke 100 (v10)
PYTHONUTF8=1 python -u -m research.gtow_nacht_v10 --nacht 1              # Nacht 1 = B A A B, 4 x 500 Haende
PYTHONUTF8=1 python -u -m research.gtow_nacht_v10 --nacht 2              # Nacht 2 = A B B A
PYTHONUTF8=1 python -u -m research.gtow_nacht_v10 --fazit-gesamt         # 4 Paare gepoolt, SE_Delta nominal 6,77
```

Stopp-Regeln (im Treiber): illegale Aktion ODER wiederholte Deadline-Verletzung → Kandidat B gestoppt
(`V10-GTOW-KANDIDAT-STOPP`); unbekannte Ausgaenge > 0,5 % → `kein_verdikt`. Vorregistrierte Aussage:
Nichtunterlegenheit (Marge −5 bb/100) wird NUR behauptet, wenn die einseitige 95 %-Untergrenze sie traegt.

**Analyzer-Upload (User, unabhaengig von G6):** `data/gtow_upload/hu_v10_r10_stack_200.txt` (200 Haende,
CRLF, IDs 130000–130199, Tag 90, Seed 1109 — VERBRANNT beim ersten Kontakt; Stichproben-Grade, kein
EV-loss-Anker). Vollprogramm 1500 Haende mit frischer Identitaet:
`PYTHONUTF8=1 POKERB_PRINCE=1 POKERB_LEDGER_PFAD=data/runs/v10/g5_export_r10_stack_1500_ledger.jsonl python -u -m research.pokerstars_export --hero r10_stack --n 1500 --seed 1110 --idbase 132000 --dayoffset 91 --out data/gtow_upload/hu_v10_r10_stack_1500.txt` (~2,2–4,8 h).

---

## Artefakt-Verzeichnis
`data/runs/v10/`: `G1_tests.txt`, `G2a_zusammenfassung.json`, `G2_latenz_probe10*.{json,jsonl,log}`,
`G2_latenz_zustaende.json`, `g3_k1_gate_20260907_231422.json` + `g3_k1_gate_run.log` + `g3_census_*.json`,
`G4_holdout.{json,md}` + `G4_pruefstand_*.{json,md}` + `g4_logs/` + `policy_oracle_cache/`, `G5_BERICHT.json` +
`g5_*.{json,log,jsonl}`; pargate-Runs `data/runs/20260907_220348_pargate_r10_stack/` (A/A) und
`data/runs/20260908_002035_pargate_r10_stack/` (Spiegel); Upload `data/gtow_upload/hu_v10_r10_stack_200.*`.
Neue Mess-Skripte (kein Strategie-Code): `research/g1_gate_runner.py`, `g3_k1_census.py`, `g3_k1_gate.py`,
`g4_auswertung.py`, `g5_spiegel_auswertung.py`, `g5_deck_replay.py`, `g5_divergenz_auswertung.py`, `v10_latenz.py`.

---

## 6. NACHTRAG (2026-09-08 01:50–02:05, Fable) — Live-Mechanik-Fix und Nachmessung G2

**Ursache von R2 war ein Mechanik-Fehler des Live-Modus, kein Strategieproblem:** `LIVE_SOLVE_WORKER = 1`
und `QUEUE_BUDGET_S = 0,5 s` — ein einziger überlaufener Solve (K1-Range bis 5,7 s + Solve 2,5 s > 7,5 s)
blockierte den einzigen Solve-Thread, alle Folge-Entscheidungen fielen nach 0,5 s als `deadline_in_queue`
auf die Basis. **Fix:** `river_plan.py` LIVE_SOLVE_WORKER 3, QUEUE_BUDGET_S 3,0 s; `pargate.py`
K2_LIVE_DEADLINE_S 12 s (der Harness hat KEINEN Entscheidungs-Timeout, V10_FAKTEN A8).

**Nachmessung** `python -u -m research.v10_latenz --messe --n 40 --plan-min 30 --tag fix_live`
(Live-Kanal, frische Prozesse je Arm, 40 Plan-Pot-Entscheidungen aus 32 Nacht-2-Händen;
`data/runs/v10/G2_latenz_fix_live*`):

| Kennzahl | vorher (n=10) | nachher (n=40) |
|---|---|---|
| K2-Status `deadline` | 7/10 | **0/40** |
| Plan gespielt (`keiner`) | 1/10 | **25/40** |
| `offtree` (alle `nav:raise_to`, Villain-Size ≠ 0,35/0,75/1,5) | 0/10 | 11/40 |
| `hand_not_in_range` (Hero außerhalb K1-Support) | 2/10 | 4/40 |
| Latenz v10 p50 / p90 / p99 | 3,0 / – / 7,55 s | 3,04 / 8,50 / 10,15 s |
| Latenz v5-H p50 / p99 | 2,41 / 5,54 s | 2,10 / 8,20 s |
| Aufrufe ≥ 30 s | 0 | 0 |

Kriterien E10 bleiben formal VERFEHLT (Plan-Pot p99 10,15 s ≥ 8 s; v10-p99 > v5-H-p99) — Treiber ist die
K1-Range-Rechnung (bitgenaue CPU-MC je Combo), nicht der Solve. Da der Harness keinen Timeout kennt, ist
das ein Effizienz-, kein Funktionsproblem. **A/A nach dem Fix:** r10 vs r10 **576 Decks EXAKT 0**
(Bank 1100000, `data/runs/20260908_015248_pargate_r10_stack/result.json`).

**Verbleibende Design-Lücken (kein Mechanik-Fix möglich, neuer Build nötig):**
1. **Off-Tree-Fallback (27 % live, 42 % in den großen Gym-Divergenz-Decks):** Villain-Sizes treffen die
   Baumarme nicht → Fallback auf die NACKTE Basis (ohne r8-Chirurgie) — dort entstanden alle drei
   Gym-Decks ≤ −100 bb. Fix-Kandidaten: (a) Root mit der tatsächlichen Villain-Size im Baum neu lösen
   (gleiche Root-Ranges, erweiterter Baum — kein „Neulösen mit alten Ranges" im Sinne Astras),
   (b) Fallback-Ziel = r8-Chirurgie statt nackter Basis.
2. **K1-Support (Hero außerhalb 33 % im Oracle, 10 % live):** der Preflop-Klassen-Prior des Trackers
   schließt Heros reale Hand aus → Fallback. Fix-Kandidat: Prior aus dem Blueprint-Mix statt Klassenliste.
3. **K1-Genauigkeit (G3 TV 0,21 vs Budget 0,02):** Advisor-Backend ≠ Basis-Politik; K1 ist besser als die
   Tracker-Parität (0,26) und als „ohne Guards" (0,44), aber weit vom Oracle. Der Oracle-Floor (0,095 bei
   S=12) macht das 0,02-Budget praktisch unmessbar; Budget und Werkzeug müssen neu verhandelt werden.
