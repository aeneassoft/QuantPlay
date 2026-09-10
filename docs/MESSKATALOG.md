# MESSKATALOG — was in diesem Projekt tatsaechlich gemessen wurde

> **Wofuer dieses Dokument da ist.** Es sammelt ALLE echten Messungen des Projekts — Selbstspiel, GTO Wizard,
> den Analyzer-Kanal ueber Chrome, LLM-Laeufe, Snowie, Turnier, Solver-Validierungen und Laufzeiten — je mit
> Zahl, Streuung, n, Instrument, Verdikt und **Quelle**. Gegenstueck zum
> [`MODULKATALOG.md`](MODULKATALOG.md): der sagt, was ein Baustein TUT, dieser sagt, ob er FUNKTIONIERT.
>
> **Die wichtigste Regel beim Lesen: der KANAL entscheidet, was eine Zahl bedeutet.**
> Ein Selbstspiel-Spiegelwert ist eine Nichtverschlechterungs-Schranke, kein Staerkebeweis. Ein
> Analyzer-EV-Verlust ist eine Entscheidungs-Note, kein Ergebnis. Nur der GTOW-AIVAT-Wert ist die Achse, auf
> der das Projektziel definiert ist. Zahlen aus verschiedenen Kanaelen darf man **nicht addieren** — die
> Guard-Kette hat das gemessen widerlegt (Einzelmessungen summierten sich auf ~+53, gemessen wurden +30,6).

## ★ Drei Korrekturen, die beim Erstellen dieses Katalogs herauskamen (2026-09-10)

**1. Der einzige gueltige GTOW-Anker ist viel unpraeziser als angenommen.**
Nachgerechnet aus den Handhistorien selbst (`data/sessions/gtow_hands_1787027076.jsonl` +
`_1787033025.jsonl`, n=979): Mittel **−21,12**, per-Hand-SD **294,1**, **SE 9,40** — nicht 6,8.
Die im Projekt verwendete Konstante **c ≈ 214 stammt aus der v2.2-Aera** (dort nachgerechnet SD 213,5 bei
n=2393) und unterschaetzt die Streuung des heutigen Bots um rund 28 %.

| Folge | mit c = 214 | mit gemessenem c = 294 |
|---|---|---|
| Haende fuer SE = 4 bb/100 | 2.862 | **5.407** |

Das 95-%-Band des Ankers ist damit rund **[−39,5, −2,7]** statt des viel engeren Bandes, mit dem bisher
geplant wurde. **Jede Hand-Budget-Rechnung im Repo, die auf c = 214 beruht, ist entsprechend zu korrigieren.**

**2. „−21 ist der heutige Champion" ist falsch.** Der Wert gehoert **v4/r6_button auf PRINCE**, nicht v5.
v5 hat bis heute **keinen** GTOW-Anker (Journal `KONSULT-SOL-KORREKTUR`, 2026-09-10).

**3. Zwei Kaggle-Messungen sind ungueltig.** Der Referenzwert (Champion vs Basis, +55,8 ± 38,0) und der
v9-Lauf (600 Decks, exakt 0,0) liefen ohne die `deal`-Marke im Adapter; ohne sie liefert
`improver._river_spot_und_frage` `None`, und damit konnte **auch die GPU-Chirurgie des Champions nicht
feuern**. Details: [`KAGGLE_ARENA.md`](KAGGLE_ARENA.md).

Weitere Korrekturen, veraltete Zahlen und Zahlen ohne Beleg stehen im Abschnitt **Nachtrag und Korrekturen**
am Ende. Was dort unter „Veraltet — nicht mehr zitieren" steht, gehoert nicht mehr in neue Dokumente.

## Inhalt

- [Das Autogym-Journal](#das-autogym-journal)
- [1 — HU-Spiegel (`kanal: pargate_mirror`) — die Hauptkette](#1--hu-spiegel-kanal-pargatemirror--die-hauptkette)
- [A. Live-AIVAT gegen die GTOW-API](#a-live-aivat-gegen-die-gtow-api)
- [1. Upload-Regeln und Fallstricke (alle aus Schaden gelernt)](#1-upload-regeln-und-fallstricke-alle-aus-schaden-gelernt)
- [LLM- und Brain-Messungen](#llm--und-brain-messungen)
- [Selfplay-, Gym- und Gate-Messungen](#selfplay--gym--und-gate-messungen)
- [Snowie, Turnier, Multiway, Vision, Solver-Validierung](#snowie-turnier-multiway-vision-solver-validierung)
- [Welche Rohdaten liegen wo](#welche-rohdaten-liegen-wo)
- [Nachtrag und Korrekturen](#nachtrag-und-korrekturen)

---

## Das Autogym-Journal

`data/autogym/journal.jsonl` ist das Messtagebuch der selbstprüfenden Trainings-Schleife (Autogym). Es
protokolliert **Gate-Entscheidungen**: ein Kandidaten-Bot wird gegen einen Amtsinhaber auf identischen
Decks gespielt, das gepaarte Delta in bb/100 wird mit Streuung und Verdikt eingetragen. Was der Kanal
kann: Kandidat-gegen-Kandidat-Vergleiche **innerhalb der eigenen Selbstspiel-Ökologie** auf sehr großen
Stichproben (30k–183k Decks, $0, deterministisch bei korrektem Seeding) sowie die Buchführung der
GTOW-Live-Läufe und der Nebeninstrumente. Was der Kanal **nicht** kann: ein absolutes Stärke-Urteil.
Eine positive Spiegelzahl heißt „schlägt den Vorgänger in unserer eigenen Ökologie", nicht „ist näher an
GTO" — das Journal dokumentiert diese Nicht-Transitivität selbst (J:92, J:93) und die Doktrin, dass der
Spiegel nur eine **Nichtverschlechterungs-Schranke** ist, während der Wirkungs-Beweis gegen adaptive
Gegner auf einer anderen Achse liegt (J:74).

**Zitierweise:** `J:20` = `data/autogym/journal.jsonl`, Zeile 20 (der Datei-Zeilenindex; Einträge sind
eine JSON-Zeile je Eintrag, chronologisch). Wo der Eintrag ein eigenes `quelle`-Feld trägt, ist es
zusätzlich genannt.

---

### Die Kanäle in diesem Journal — je ein Satz

| Kanal | Was er messen kann | Was er NICHT messen kann |
|---|---|---|
| **Orakel / Selftest** (`autogym/oracle.py`, Stufen HART/P/L/F) | Ob eine Entscheidung eine Formel-Schranke (Pot-Odds, MDF) verletzt — als *Lead*, mit Severity in bb | Ob die Verletzung EV kostet; Formel-Konformität ist keine Gewinn-Aussage |
| **pargate-Spiegel** (`autogym/pargate.py`, gepaarte Decks, Button-Tausch) | Gepaartes Delta Kandidat−Amtsinhaber in bb/100 in der Selbstspiel-Ökologie, sehr große n | Absolute Stärke; Härtung gegen *adaptive* Gegner ist hier strukturell unsichtbar bis negativ (J:74) |
| **envgate** (gemeinsamer dritter Gegner `GTOBaseline`) | Ob zwei Arme gegen denselben fremden Gegner unterschiedlich abschneiden | Nichts Ship-Fähiges — Ergebnisse heißen im Projekt `KANAL_*` und sind ausdrücklich keine Ship-Evidenz |
| **GTOW-Live-AIVAT** (`benchmark/gtowizard.py`, echte Hände vs GTO Wizard AI) | Absoluter Anker in bb/100 gegen einen Re-Solver, varianzreduziert | Kostet Hand-Budget; keine Paarung, SE ≈ 214/√n → Bänder von ±4 brauchen ~11.000 Hände (J:111) |
| **Adversar** (Fable-LLM-Duell, `exploit_jagd`) | Ob ein Muster *ausbeutbar* ist (gezählte Muster, Ernte in bb/100) | Statistisch belastbare Mittelwerte — 62–92 Hände sind Anekdote mit gezählten Mustern |
| **Replay/Solver-Audit** (`tiefen_replay`, `v8_replay_gegentest`, `river_bill_diagnose`) | Kontrafaktische EV-Zerlegung auf bereits gespielten GTOW-Händen, ohne neue Hände zu verbrennen | Realisierte bb — es sind Solver-EVs, keine gespielten Ergebnisse |
| **pargate6** (6-max, Hero rotiert über 6 Sitze) | Gepaartes 6-max-Delta gegen den Liga-Kern | Externen Anker — die Liga ist die eigene Ökologie („tag spielt zu Hause") |
| **Kaggle-Arena** (`benchmark/kaggle_arena.py`, open_spiel/pokerkit) | Billiger Volumen-Spiegel und eine LLM-Ökologie | GTO-Anker — das Feld sind LLMs, kein Re-Solver; außerdem 100 bb statt der GTOW-200 bb (J:122) |

**Eine harte Zäsur quer durch die Tabelle:** Alle Läufe **vor dem 2026-08-17 abends** (Runde 1–4,
J:15–J:41) entstanden, bevor der Spot-RNG-Seeding-Fix landete. Das Journal weist selbst nach, dass die
per-Deck-Paarung vorher brach, weil die MC-Equity-Aufrufe ungeseedet waren (J:33), und registriert erst
mit Runde 5 einen A/A-Nulltest, der exakt 0 verlangt (J:42, bestanden J:50). Richtung und Größenordnung
dieser frühen Zahlen sind belastbar, die angegebenen SE sind es nur eingeschränkt.

---

### Chronologische Tabelle — alle Einträge mit Zahl

#### Phase 1 — Orakel-Leads und erste Gates (2026-08-16)

| Datum | Was gemessen | Instrument/Kanal | Ergebnis (Zahl ± Streuung, n) | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-08-16 19:25 | `call_unter_pot_odds`, River-Calls unter Pot-Odds | Orakel Stufe L (Self-Play-Entscheidungen) | Severity 99,01 / 52,00 / 16,25 bb; eq 0,00 vs nötig 0,25/0,31/0,25 | EXPERIMENT-KANDIDAT | J:1–J:3 | Als **Lead** ja; der daraus gebaute Guard wurde gemessen NEUTRAL (J:15/J:17) |
| 2026-08-16 19:27 | `mdf_flop`, Fold-Frequenz am Flop vs MDF | Orakel Stufe F | Fold-Freq 0,63 vs MDF-erlaubt 0,24 (n=151), OVER-FOLD | EXPERIMENT-KANDIDAT | J:4 | Lead; abgeleiteter Guard NEUTRAL (J:18). Später relativiert: Flop-Overfold ist HU-spezifisch, 6-max foldet 0,216 (J:38) |
| 2026-08-16 19:27 | `call_unter_pot_odds` (2. Runde) | Orakel Stufe L | Severity 112,12 / 96,00 / 86,32 bb | EXPERIMENT-KANDIDAT | J:5–J:7 | Lead |
| 2026-08-16 19:40–21:51 | `station_nicht_geschlagen` (Bot vs Nie-Folder) | Selftest, 1-Hand-Horizont | +394,9 ± 279,9 (60 Decks) — 5× identisch protokolliert | EXPERIMENT-KANDIDAT | J:8, J:9, J:14, J:16, J:19 | Nur Gesundheits-Signal; identische Wiederholung = derselbe deterministische Lauf, kein unabhängiges n |
| 2026-08-16 19:58 | `mdf_flop` (größere Stichprobe) | Orakel Stufe F | Fold-Freq 0,61 vs MDF 0,32 (n=304) | EXPERIMENT-KANDIDAT | J:10 | Lead |
| 2026-08-16 20:06 | `podds_guard_river` (Guard aus den L-Leads) | pargate-Spiegel | +0,50 ± 0,50 bb/100 (200 Decks) | NEUTRAL | J:15 | Ja als Negativ-Befund. Auffällig: `se == bb100` exakt — dünner Kanal, wenige Trigger |
| 2026-08-16 20:10 | `podds_guard_river` (4× n) | pargate-Spiegel | +0,31 ± 0,31 bb/100 (800 Decks) | NEUTRAL | J:17 | Ja — Formel-Guard aus Pot-Odds druckt nicht |
| 2026-08-16 20:38 | `mdf_guard_flop` | pargate-Spiegel | −7,40 ± 28,39 bb/100 (400 Decks) | NEUTRAL | J:18 | Ja als Negativ-Befund; SE 28 = uninformativ, Kanal war zu klein |
| 2026-08-16 22:11 | `sel_guard_flop` („AUSLESE v1") vs eingefrorene Basis | pargate-Spiegel | +4,70 ± 2,06 bb/100 (99.000 Decks), CI95 [0,6; 8,8] | ANWENDEN | J:20 | Historisch; Kette inzwischen 4× überbaut (v3/v4/v5) |
| 2026-08-16 23:39 | `sel_guard_flop`, Replikation auf frischem Deck-Universum | pargate-Spiegel | +7,49 ± 2,08 (99.000 Decks); gepoolt ≈ +6,1 ± 1,5 über 198k | ANWENDEN bestätigt | J:21 | Historisch belastbar (Replikation bestanden), abgelöst |
| 2026-08-16 23:39 | `sel_all` (Turn/River-Selektion) Sanity | pargate-Spiegel | +6,53 ± 22,22 (1.200 Decks) | NEUTRAL | J:22 | Ja — „Richtung positiv, Kanal laut" |
| 2026-08-16 23:39 | `lizenz_guard` | pargate-Spiegel | **exakt 0,00 ± 0,00** (1.200 Decks) | DIAGNOSE-BEDARF | J:23 | Ja als Instrumenten-Befund: der Guard hat **nie gefeuert** (toter Wrapper / leerer Kanal) |

#### Phase 2 — Rotation, Replikations-Pflicht, Transfer (2026-08-17 früh)

| Datum | Was gemessen | Instrument/Kanal | Ergebnis (Zahl ± Streuung, n) | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-08-17 00:10 | `sel_all` (Lauf mit toter Lizenz-Komponente) vs Basis | pargate-Spiegel | +6,13 ± 2,03 (98.960 Decks) | schlägt Basis, aber nicht v1 | J:24 | Historisch |
| 2026-08-17 00:21 | `lizenz_guard` mit lebendigem Wrapper | pargate-Spiegel | −0,06 ± 0,69 | kein Effekt | J:26 | Ja — die Bluff-Lizenz-Theorie ist im HU-Spiegel wirkungslos |
| 2026-08-17 00:21 | `sel_all` vs `sel_guard` („AUSLESE v2"), Direktvergleich | pargate-Spiegel (leiser Kanal) | +3,00 ± 1,40 (30.000 Decks) | ANWENDEN+ROTATION | J:25 | **NEIN — refutiert**, siehe die zwei folgenden Zeilen |
| 2026-08-17 00:32 | Replikation desselben Vergleichs | pargate-Spiegel | +0,44 ± 1,09 (30.000); gepoolt +1,41 ± 0,86 | **REPLIKATION NICHT BESTANDEN** | J:27 | Ja — die Rotation war verfrüht, v1 blieb Referenz |
| 2026-08-17 01:02 | Dritter Direktlauf, Endurteil v2 | pargate-Spiegel | +0,18 ± 0,73 (90.000 gesamt); gepoolt +0,69 ± 0,56 | **ROTATION ABGELEHNT** | J:28 | Ja — der +3,00-Erstlauf war Stichprobenglück; die Drei-Läufe-Regel entstand hier |
| 2026-08-17 01:38 | 39 externe Blunder (PokerSnowie-Bewertung) einzeln obduziert | externe Bewertung | 15/39 = zu lose Call-Downs (sel_guard überdosiert); 11/39 = verpasster Wert, gehäuft Turn-Checks | Kandidaten abgeleitet | J:29 (`docs/SNOWIE_BLUNDER_ANALYSE.md`) | Ja — der 11/39-Befund führte direkt zu `turn_wert` (J:61–J:66) |
| 2026-08-17 02:04 | `sel_guard` gegen **fremden** Gegner (GTOBaseline) | Transfer-Test, ungepaart | −3,78 ± 30,31 (3.000 Decks); AUSLESE −23,40 ± 21,99 vs Basis −19,62 ± 20,86 | uninformativ | J:30 | Nur als Warnung; Streuung unbrauchbar |
| 2026-08-17 02:19 | 20 adaptive Dirichlet-Jäger vs eingefrorene Basis | `exploit_jagd` | Adaptiv +8,87 ± 6,9 (n=100.000) vs Null-Kontrolle +7,73 ± 8,7 → Adaptions-Zugewinn ≈ +1, **nicht signifikant**; alle 20 Jäger konvergieren auf VPIP 0,75–0,77 / fold_to_bet 0,29–0,31 / aggression 0,31–0,34 | Struktur > Anpassung | J:31 | Ja — die Härtungs-Landkarte wird bis heute zitiert; konsistent mit dem späteren Exploit-Refutat (J:113) |
| 2026-08-17 02:24 | derselbe Transfer-Test, korrekt gepaart | Transfer-Test, gepaart | −3,80 ± 12,87 (3.000 Decks) | uninformativ | J:32 | Superseded durch die eigene Fehler-Diagnose in J:33 |
| 2026-08-17 02:25 | Warum die Paarung nicht griff | Instrumenten-Diagnose | SE bleibt 12,9, weil `equity_vs_*` **ungeseedet** ist → beide Arme divergieren stochastisch auf jedem Deck | Ergebnis uninformativ | J:33 | **Ja, und zentral** — begründet, warum alle Zahlen vor dem Seeding-Fix mit Vorsicht zu lesen sind |

#### Phase 3 — Runde 4: Margen-Sweep bis „AUSLESE v3" (2026-08-17 mittags)

| Datum | Was gemessen | Instrument/Kanal | Ergebnis (Zahl ± Streuung, n) | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-08-17 12:16 | `sel_m06` (Marge 6pp) vs v1 | pargate-Spiegel | +0,06 ± 1,45 vs v1; +0,30 vs Basis | NEUTRAL | J:34 | Ja |
| 2026-08-17 12:31 | `sel_m10` vs v1 | pargate-Spiegel | +5,64 ± 1,74 vs v1; +8,72 vs Basis | ANWENDEN | J:35 | Historisch; von m15 abgelöst |
| 2026-08-17 12:45 | `sel_m15` vs v1 | pargate-Spiegel | +10,50 ± 2,10 vs v1; +17,47 vs Basis | ANWENDEN | J:36 | **Erstlauf-Wert; siehe J:40 — Replikation fiel 3 σ tiefer** |
| 2026-08-17 12:53 | `einmal_guard` (Mehrstrassen-Disziplin) | pargate-Spiegel | +0,41 ± 1,05 vs v1 | NEUTRAL | J:37 | Ja — verworfen |
| 2026-08-17 12:55 | 6-max-Katalog, 30.000 Hände | Selbstspiel-Katalog | Positions-bb/100: BB −28,9 / SB −29,6 / BTN +33,5 / HJ +15,8 / UTG +6,8 / CO +2,4. Facing: Flop 21.165 Knoten, fold 0,216, Bet 0,431 Pot; Turn 11.565, fold 0,297; River 8.143, fold 0,337 | Katalog | J:38 | Ja — Referenzwerte; zeigt, dass der Flop-Overfold HU-spezifisch war |
| 2026-08-17 13:42 | `sel_m15` vs **Basis**, Entscheider-Lauf | pargate-Spiegel | **+8,68 ± 1,28 bb/100 (183.200 Decks)**, 20 Worker, 2.821 s, 3.896 Decks/min | ANWENDEN | J:39 | Ja als größter Einzel-Anker der Frühphase (n=183k), aber vor dem Seeding-Fix |
| 2026-08-17 14:02 | Replikation `sel_m15` vs `sel_guard` | pargate-Spiegel | +1,11 ± 2,16 (30.000) — **3 σ** vom Erstlauf +10,50 ± 2,10 entfernt; m20-Probe kippt: −1,52 ± 1,54 | REPLIKATION HETEROGEN | J:40 | **Ja, und methodisch die wichtigste Zeile:** fette Ränder der per-Deck-Edges machen 2SE-Intervalle zu optimistisch |
| 2026-08-17 14:31 | Taufe `AUSLESE v3` (= `sel_m15`) | pargate-Spiegel, 3 Läufe | +10,50 ± 2,10 / +1,11 ± 2,16 / +2,63 ± 1,22 (90k); gepoolt **+3,94 ± 0,95** vs v1; ohne Erstlauf +2,13 ± 1,06; 183k-Anker +8,68 ± 1,28 vs Basis | ANWENDEN + NAME | J:41 | Historisch; Marge 15pp = Plateau-Rand |

#### Phase 4 — Runde 5: Seeding-Fix, Estimator-Revision, „AUSLESE v4" (2026-08-17 abends)

| Datum | Was gemessen | Instrument/Kanal | Ergebnis (Zahl ± Streuung, n) | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-08-17 19:53 | **A/A-Nulltest** (Kandidat == Amtsinhaber) | pargate-Spiegel | **0,0 ± 0,0**, trim 0,0 ± 0,0, max_abs_edge **0** (1.936 Decks) | bestanden | J:50 | Ja — ab hier ist der Spiegel prozess-deterministisch; alles davor mit Vorbehalt |
| 2026-08-17 (vorab) | Kanalbreite `sel_all_m15` **vor** dem Bau vermessen | Kanal-Vermessung (400 Decks) | Turn-Fold-Spots **0/800 Hände**; River 0/15 flippt bei m15 | Erwartung ~0 | J:43 | Ja — das Prinzip „Kanal vor dem Bau vermessen" (AP8) |
| 2026-08-17 (vorab) | Kanalbreite `turn_wert` | Kanal-Vermessung (400 Decks) | 40/800 Hände (5 %) würden betten; 208 Turn-Checks, 60 starke Made Hands, 40 mit eq ≥ 0,60 | breitester neuer Kanal | J:44 | Ja |
| 2026-08-17 (vorab) | `turn_def_adv` Vorgeschichte | Analyzer (fremder Kanal) | v5C-Historie: **−1,87** (resolver-OFF) | Kanal offen | J:48 | Historische Referenz aus dem Analyzer-Kanal, hier nur zitiert |
| 2026-08-17 20:01 | `sel_all_m15` vs `sel_m15` | pargate-Spiegel | 0,0 ± 0,0 (29.920 Decks) — **0 divergente Decks** | NEUTRAL | J:51, Deutung J:59 | Ja — Umdeutung: **„kein Kanal", nicht „refutiert"** |
| 2026-08-17 20:10 | `turn_wert` Lauf 1 | pargate-Spiegel, Trim-Estimator | +1,64 ± 4,03; **trim 0,00** | NEUTRAL | J:52 | **NEIN — Verdikt später gekippt**: der 5-%-Trim war für dünne Kanäle blind (J:54), Neubewertung siehe J:61–J:63 |
| 2026-08-17 20:18 | `wert_plus_all` | pargate-Spiegel | +1,64 ± 4,03 (29.920) | NEUTRAL | J:53 | Identischer Wert wie J:52 → derselbe wirksame Arm |
| 2026-08-17 20:40 | `prince` gegen GTOBaseline | envgate | delta **−68 roh** | **Kanal-Artefakt** | J:60 | Ja als Warnung: die Referenz exploitet den schwachen Gegner, der Arm nicht — **kein Urteil über PRINCE vs GTOW** |
| 2026-08-17 20:48 | `turn_wert` Lauf 2, Estimator v2 (rohes Mittel + Vorzeichen-Test) | pargate-Spiegel | **+9,39 ± 4,06** (29.920); nonzero 2.594 (8,67 %), nz_pos 1.530, Vorzeichen-z **9,15**, nz-Median 264 Chips | ANWENDEN | J:61 | Ja |
| 2026-08-17 20:56 | `turn_wert` Lauf 3 | pargate-Spiegel | **+10,78 ± 4,00** (29.920); Vorzeichen-z 8,98 | ANWENDEN | J:62 | Ja |
| 2026-08-17 21:33 | `turn_wert` gepoolt 3×30k | pargate-Spiegel | **+7,27 ± 2,33 bb/100 (89.760 Decks)**; nonzero 8,58 %, Vorzeichen-z **14,93** | ANWENDEN | J:63 | Ja — dreifach repliziert; der älteste Leak (Turn-Unterbetten) |
| 2026-08-17 21:44 | K3-Anteil (Deception) **in** der Kombi | envgate, gepaart | +10,19 ± 4,01; Vorzeichen-z +5,4; nz-Median +198. K3 **allein nicht repliziert** (+8,7 / +0,3 / −4,7) | Montage als Einheit | J:64 | Ja — dokumentierte Interaktion; K3 allein ist **nicht** belegt |
| 2026-08-17 21:54 | Treppe vs eingefrorene Basis | **envgate** (gemeinsamer Gegner GTOBaseline, resolver-OFF) | `auslese_v3` +21,36 ± 6,03; `kombi_r5` **+49,79 ± 7,99**; gepaarte Stufe v3→neu **+28,44 ± 6,17** (Vorzeichen-z 10,1), 12.000 Decks | Stufe belegt | J:65 | **Eingeschränkt** — envgate-Zahlen heißen im Projekt `KANAL_*` und sind ausdrücklich **keine Ship-Evidenz** |
| 2026-08-17 21:54 | Taufe `AUSLESE v4` | Zusammenfassung | Einheit 3× repliziert (+26,4 / +25,2 / +36,2 vs v3-Referenz); `turn_wert` 3× Spiegel +7,27 ± 2,33; RN10 3× (+16,8 / +13,7 / +9,2); K3 im Verbund +10,2 ± 4,0; A/A exakt 0 | TAUFE | J:66 | Historisch (v5 ist Champion) |
| 2026-08-17 22:36 | **Neubewertung aller Runde-5-Verdikte** mit Bootstrap-CI + Permutations-p | Estimator v3 | `turn_wert` 3×30k CI [+2,69; +12,05], p = 0,0007 HÄLT; RN10 alle 3 Läufe halten (p ≤ 0,004); `kombi_r5` hält (p = 0,0002); **RN05 fällt in 2/3 Läufen auf NEUTRAL** | Revision | J:68 | Ja — RN05 war nie in der Version |
| 2026-08-17 23:25 | **v4-Kern vs eingefrorene Basis**, gepoolt 3 Läufe | pargate-Spiegel | **+16,14 ± 2,77 bb/100 (89.760 Decks)**, CI95 [+10,74; +21,56], perm_p 0,0002, nonzero 20,63 % | ANWENDEN | J:70 | Ja — der saubere Spiegel-Anker für v4 |

#### Phase 5 — Adversar-Achse und Härtung (2026-08-17 nacht / 2026-08-18)

| Datum | Was gemessen | Instrument/Kanal | Ergebnis (Zahl ± Streuung, n) | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-08-17 23:41 | LLM-Adversar (Fable) vs v4 | Adversar-Duell, dateibasiert | **62 Hände, +115,5 bb** (ausdrücklich Anekdote). Gezählte Muster: Button-Open-Fold ~29 %, Limp-Call→Fold-vs-Cbet 5/7, River-Station 4/5 großer Calls mit Verlierern (~90 bb), Check-Raise ohne Follow-Through 3/3, keine Mischung; `turn_wert`-Bets 3/3 als Tell | Muster-Befund | J:71 | Ja — die gezählten Muster; der bb-Wert ist **keine** Schätzung, nur Anekdote |
| 2026-08-18 00:11 | `r6_ecall` (River-eCall-Guard aus dem Fable-Befund) | pargate-Spiegel | **−4,15 ± 0,97**, CI [−6,1; −2,3], Vorzeichen −4,7, nz-Median −1.452 | **VERWERFEN** | J:72 | Ja — im Spiegel sind die gefoldeten River-Calls Value-Folds; als gebaut abgelehnt |
| 2026-08-18 00:11 | `r6_button` (Button-Disziplin) | pargate-Spiegel | +0,71 ± 2,18; Vorzeichen +2,1; Kanal 16,7 % | NEUTRAL, Härtungskandidat | J:73 | Ja — besteht nur die Nichtverschlechterungs-Schranke |
| 2026-08-18 00:11 | Doktrin-Befund aus J:72/J:73 | Instrumenten-Doktrin | Härtungs-Guards gegen adaptive Gegner sind im Spiegel **strukturell unsichtbar bis negativ** | Protokoll-Regel | J:74 | Ja — bindend: Spiegel = Schranke, Adversar = Wirkungs-Beweis |
| 2026-08-18 01:24 | Fable-Retest gegen den gehärteten Stack | Adversar-Duell | **92 Hände: Ernte 186 → 58 bb/100**; Open-Folds **0/46** (vorher 29 %); 3bet-Angriff auf Trash-Open netto −21 bb. Offen: River-eCall (5/5 Value-Bets bezahlt), `turn_wert`-SIZE-Tell 7/7 | HÄRTUNG BEWIESEN | J:75 | Ja — der einzige Wirkungs-Beweis auf der Adversar-Achse |
| 2026-08-18 01:41 | **Finaler v4-Stack vs Basis** | pargate-Spiegel | **+23,36 ± 5,32 bb/100**, CI95 [+12,75; +33,72], perm_p 0,0002, Vorzeichen-z 9,72, nonzero 37,41 % | ANWENDEN | J:76 | Ja (v4-Stand; v5 kam später) |

#### Phase 6 — GTOW-Live-Läufe (2026-08-18) — der einzige absolute Anker

| Datum | Was gemessen | Instrument/Kanal | Ergebnis (Zahl ± Streuung, n) | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-08-18 01:50 | Vorregistrierung + Smokes v4-Staffel | GTOW-Live-AIVAT | Smokes **(n=20, −21,34)** und **(n=100, −59,03)**; vorregistriertes ehrliches Anker-Band −25…−30 | Smoke | J:77, J:78 | Ja als Protokoll; n=20/100 sind statistisch praktisch leer |
| 2026-08-18 03:47 | Nacht-1 Chunk 1 | GTOW-Treiber | Status FEHLGESCHLAGEN (keine Zahl) | — | J:80 | Superseded — der „Fehlschlag" war ein Treiber-Bug, siehe nächste Zeile |
| 2026-08-18 03:55 | **Bergung** aller Hände nach cp1252-Encoding-Bug | GTOW-HH-Dateien, nachgerechnet | Chunk A n=500 **−26,59 ± 7,32**; B n=500 **−54,98 ± 15,37**; C n=497 **−31,65 ± 9,88**; v4-Pool n=1.617 ≈ **−38,9** | Bergung validiert (Smokes exakt reproduziert) | J:81 | Ja als Zahl — **aber der Arm war die nackte Gym-Konfig ohne Resolver/PRINCE, also kein v4-Verdikt** |
| 2026-08-18 04:12 | Vierter geborgener Chunk | GTOW-HH | n=500, AIVAT **−48,37 ± 17,52** | — | J:82 | dito |
| 2026-08-18 04:12 | **Nacht-1-Endpool** | GTOW-Live-AIVAT | **n=2.117, AIVAT −41,11 ± 6,31** | roter Befund | J:83 | Ja als Messwert, **NEIN als v4-Verdikt** — falscher Arm (Gym-Konfig nackt) |
| 2026-08-18 06:24 | Nacht-2 Chunk 1, **Kontrollarm** PRINCE resolver-ON | GTOW-Live-AIVAT | n=488, AIVAT **−31,34** (keine SE im Eintrag) | Kontrolle | J:85 | Ja |
| 2026-08-18 08:03 | Nacht-2 Chunk 2, Arm `v4_prince` | GTOW-Live-AIVAT | n=490, AIVAT **−14,33** | — | J:86 | Ja |
| 2026-08-18 10:04 | Nacht-2 Chunk 3, Arm `v4_prince` | GTOW-Live-AIVAT | n=489, AIVAT **−27,92** | — | J:87 | Ja |
| 2026-08-18 12:42 | **Nacht-2-Fazit** (Chunk 4 im Deadlock verloren) | GTOW-Live-AIVAT, sequenzielle Arme | Kontrolle n=488 **−31,34**; `v4_prince` n=979 **−21,12**; Delta **+10,23**. Nacht 1 zum Vergleich n=2.117 −41,11 | v4-auf-PRINCE besser als Kontrolle | J:88 | **Ja — das ist bis heute der einzige GTOW-bestätigte Wert des Projekts** (−21,1). Einschränkung: keine Paarung, ungleiche n, **keine SE im Eintrag**; nach der im Journal notierten SE-Arithmetik (c = 214 bb/100·√n, J:111) wäre SE ≈ 6,8 — abgeleitet, nicht gemessen |
| 2026-08-18 02:29 | Plan: AIVAT-Kalibrierung („ist AIVAT Betrug?") | Prüfplan | Fold-Agent müsste exakt **−75 bb/100** zeigen; Kreuz-Check Analyzer 19,3 ≈ AIVAT −20 spricht bisher für Ehrlichkeit | PLAN | J:79 | Der Plan ist **nie ausgeführt** — die Kalibrierung steht bis heute aus |

#### Phase 7 — River-Fundament, GPU-Resolver, „AUSLESE v5" (2026-08-30 / 08-31)

| Datum | Was gemessen | Instrument/Kanal | Ergebnis (Zahl ± Streuung, n) | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-08-30 19:55 | `river_bill_guard` Konfusionsmatrix auf GTOW-Nacht-2-Händen | Replay über geloggte Live-Hände | 20 Trigger-Spots; Guard foldet 5: **3 richtig +141 bb, 2 falsch −121 bb, netto +20 bb**. Trennschärfe: Tracker-eq trennt Gewinner/Verlierer **nicht** (0,578 vs 0,513; PRINCE-Env 0,652 vs 0,532); Ranges nach 3 Barrels noch 700–900 Combos | Schwellen-Guard trägt nicht | J:89 (`research/river_bill_diagnose.py`) | Ja — begründet den Wechsel zum GPU-Solver statt Schwellen-Heuristik |
| 2026-08-30 20:20 | GPU-Staffel Tag 1 | Verifikation gegen exakte Referenzen | `gpu_eval` **16,8 Mio Hände/s**, 250k Paare **0 Fehler**; `gpu_equity` exakt identisch zur CPU-Enumeration; `gpu_cfr` trifft die Clairvoyance-Lösung exakt (Bluff 0,333 / Call 0,500, expl 0,014 %); Batch B=256 → **0,30 s/Spot amortisiert**; Resolver navigiert **571/571** Nacht-2-River-Spots | Bausteine verifiziert | J:90 (Commits 2b57206/297eaf9) | Ja |
| 2026-08-30 20:20 | Solver-Audit der Basis-Aktionen | GPU-Resolver-Audit | check/fold solver-konform (p 0,86 / 0,83); **bet ist die schwächste Klasse (p 0,45, 15 % klare Widersprüche)**; Desaster-Calls bekommen Solver-Fold p > 0,95. `r8_gpu`-Guard foldet 3/22 echte Big-Pot-Calls, netto **+66,9 bb kontrafaktisch** | Chirurgie belegt | J:90 | Ja |
| 2026-08-30 20:20 | `r7_bill` im Spiegel | pargate-Spiegel | **EXAKT 0** — feuert im Gym nie | GTOW-Achsen-Guard | J:90, J:91 | Ja — nicht in den Stack aufgenommen |
| 2026-08-30 20:37 | `river_wert_bremse` Drei-Läufe-Regel | pargate-Spiegel, 3 disjunkte Bänke | **+8,10 ± 1,14 / +8,81 ± 1,25 / +7,38 ± 1,05**, alle perm_p 0,0002 | ANWENDEN | J:91 | Ja — dreifach repliziert |
| 2026-08-31 00:28 | `r8_stack` Inkrement vs `r6_button` | pargate-Spiegel | **+29,92 ± 3,10** (30.000 Decks), CI [23,7; 36,3], perm_p 0,0002, z = 11,85; 1.040 Divergenz-Decks (3,5 %), nz-Median 11,6 bb | ANWENDEN | J:92 | Ja |
| 2026-08-31 00:28 | `r8_stack` vs **eingefrorene Basis** | pargate-Spiegel | **+30,60 ± 5,03**, CI [20,6; 40,3], perm_p 0,0002, trim +16,79 | ANWENDEN | J:92 | Ja — **mit dokumentierter Erwartungs-Verletzung**: vorregistriert waren +7…+9, gemessen 3–4× mehr; und **nicht additiv** (+30,6 statt ~+53) = Selfplay-Nicht-Transitivität |
| 2026-08-31 00:28 | A/A vor der r8-Kette | pargate-Spiegel | **EXAKT 0** (600 Decks) — GPU-Determinismus bewiesen | bestanden | J:92 | Ja |
| 2026-08-31 04:56 | Taufe **`auslese-v5`** (= `r8_stack`, Commit ec11fde) | pargate-Spiegel, 3 Läufe | Inkrement vs `r6_button` **+29,92 ± 3,10 / +23,76 ± 3,07 / +29,23 ± 3,03** (Bänke 470k/530k/560k, alle perm_p 0,0002), **gepoolt +27,6 ± 1,8**; vs Basis +30,60 ± 5,03; A/A exakt 0. Latenz: River-Kaltstart **13,5 s**, Flop 0,06 s | TAUFE | J:93 | **Ja — `auslese-v5` ist bis heute der Champion.** Ehrlichkeitsvermerk im Eintrag selbst: nur Spiegel-Evidenz, **kein GTOW-Anker** |
| 2026-08-31 09:51 | `river_play_guard` Vollprofil | Replay über alle 3.904 Nacht-2-Entscheidungen | **32 Eingriffe (0,8 %)**; v4-Arm 25: call→fold 7 (**netto +278,6 bb** bilanziert), fold→call 3, call→raise/allin 2, bet→check 5, bet→allin 3, Size-Korrekturen 4, check→bet 1. AIVAT-Konvergenz: #2991749 (AIVAT −52,2), #2993037 (−33,1), #2992634 (−18,1) | Play ist die übertragbare Komponente | J:94 (`research/v8_replay_gegentest.py`) | Ja als Replay-Befund — im Spiegel dann NEUTRAL (J:97) |
| 2026-08-31 11:48 | VRAM-Messung für Worker-Zahl | `nvidia-smi` | 3,7 / 12,3 GB bei 6 Workern → künftig 12 Worker | Mess-Planung | J:95 | Ja (Infrastruktur) |
| 2026-08-31 13:56 | `r9_pre` (stackoff + no_limp) | pargate-Spiegel | **−11,42 ± 2,97** (30.000) | **VERWERFEN** | J:96 | Ja. Täter-Diagnose: die Basis **limpt 78/400 Hände** (~39 % der Buttons) strategisch → `no_limp_guard` baute das halbe Preflop-Spiel um (37,8 % Divergenz-Decks). `stackoff_bremse` unschuldig (1 Trigger/400) |
| 2026-09-01 08:18 | **v8-Drop** | pargate-Spiegel | `play` vs v5 **+1,14 ± 2,78** (30k) NEUTRAL; v8 vs v5 **+3,91 ± 2,85** / **−1,23 ± 4,36** (30k+15k), gepoolt ≈ +2,3 ± 2,4; A/A exakt 0 | **USER-ENTSCHEID: v8 gedroppt** | J:97 (`docs/V8_POSTMORTEM.md`) | Ja — v5 bleibt FINAL_STACK; Ursachen: Kanal-Sättigung (nz-Median 1,9 bb vs 11,6 bb), Spiegel bestraft Feinpräzision nicht |

#### Phase 8 — Tiefen-Replay, Konsults, v10 (2026-09-01 bis 2026-09-08)

| Datum | Was gemessen | Instrument/Kanal | Ergebnis (Zahl ± Streuung, n) | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-09-01 10:37 | Paper Leal, Nash-Polytop (Kuhn) | Literatur, nachgerechnet im Paper | Max-Entropie-Member 25/25 schwach dominant; Effekt extensive-form-gated ×5,6; **Kuhn-Gap 0,0181** bei Spielwert −1/18 | Fundierung der Seesaw-Doktrin | J:98 | Ja — erklärt die offene TurnCFR-vs-TexasSolver-Frequenzdifferenz; Magnitude ehrlich als klein benannt |
| 2026-09-01 11:26 | **Tiefen-Replay** aller 571 River-Entscheidungen aus Nacht 2, 3 Konfigs | Solver-EV-Zerlegung (`research/tiefen_replay.py`) | **Liegengelassen : Fehler = 1,6 : 1 (69,9 vs 43,0 bb)**. Größte Einzelkategorie v4 = **OVERFOLD 31,1 bb** (Fold, wo der Solver Bluff-Raise will). `VERLUST_CALL` (die Wochen-Baustelle) ist im EV-Maß die **kleinste** Kategorie: **4,1 bb**. Kipp-Raten roh 25 % / 34 %, **EV-relevant nur 4 % / 5 %**. Solver-EV-Fehlersumme River: v4 **6,9 bb/100**, Kontrolle **9,5** | Richtungswechsel: Ernte statt Defense | J:99 (`data/runs/tiefen_replay_20260901_112429.jsonl`) | **Ja, und einer der wertvollsten Einträge** — er zeigt, dass die verfolgte Baustelle die kleinste war; Hand 3003011 (−137 bb real) hatte nur +0,6 bb EV-Diff = Karten-Realisierung, keine Entscheidung |
| 2026-09-01 11:44 | E1-Vorgate für v9 (`r10_ernte`) | Trigger-Analyse auf der Replay-Liste | 15-bb-Trigger erschließt **15 Neu-Spots [13,7–40,3] bb**; Ernte-Erwartung gesamt **[3,6–5,4] bb/100** auf der GTOW-Achse; Latenz-Smoke 0,88 s/Deck, 4/40 Divergenzen | Vorgate bestanden | J:100 (`docs/HU_OPTIMAL_KARTE.md`) | Erwartung, kein Ergebnis — die v9-Kette wurde **abgebrochen** |
| 2026-09-01 14:36 | v9-Kette gestoppt | pargate | A/A `r10_ernte` **EXAKT 0** (576 Decks, fp16-Determinismus); Champion-Lauf bei ~13/48 Blöcken abgebrochen, Edges verloren. Neu gebaut: fortsetzbares pargate, Identitätstest **9,87 == 9,87** | PAUSIERT | J:101 (Commit eabcef3) | Der A/A gilt; ein v9-Ergebnis existiert **nicht** |
| 2026-09-07 15:41 | Konsult gpt-6-astra, Top-5-Strategie | Externe Konsultation (5.178 Reasoning-Tokens) | Code-verifizierte Übernahme: Heros River-Range kommt aus dem **Tracker** (`improver.py:437`) statt aus der Politik; `_injiziere` (`gpu_resolver.py:64`) → der Solver löst das falsche Spiel. SE-Arithmetik: SE 2 je Arm = **12k–49k GTOW-Hände**. Widerspruch dokumentiert: 20–40 % für −8 in 6 Monaten zu hoch (Gegenschätzung 10–20 %) | STOPP-Empfehlung für v9 | J:102 (`docs/TOP5_KONSULT_GPT6_2026-09-07.md`) | Ja — löste den v10-Bau aus |
| 2026-09-07 16:00 | Konsult, Lern-Architektur | Externe Konsultation (5.696 Reasoning-Tokens) | **Exaktes Gegenbeispiel** gegen „Q-Netz → Politik via Softmax": U=[[1,−2],[−1,1]], Nash 40/60, Q identisch (−0,2), Softmax 50/50 → **BR-Verlust −0,5 statt −0,2**. Folge: null Solver-Regret ≠ niedrige Exploitability; das Tiefen-Replay misst nur Achse A | These widerlegt | J:103 | Ja — begründet, warum ein BR-Prüfstand (K3) nötig war |
| 2026-09-07 20:13 | v10-Bau, erster Anlauf | Ultracode-Workflow | P3-Fixer 45 min in einem Lauf hängen: der Arm-A-Oracle löst **je Combo ein eigenes GPU-Subgame** (1326 × Seeds × Knoten Einzel-Solves) | Abbruch + Lehre | J:105 | Ja — bindende Lehre: Oracles über Guard-Ketten **gebatcht** nachbilden |
| 2026-09-07 21:59 | v10-Integration | Tests + A/A + Golden-Set | Golden-Set `r8_stack` vs Basis 40 Decks **byte-identisch** vor/nach hand_id-Injektion (nonzero 16, +11.588). **Bug gefunden:** `hand_id = 2*deck+half` machte die privaten Seeds der Spiegelhälften verschieden → A/A **−9,40 ± 10,92** (13 nonzero); nach Fix A/A 576 Decks **EXAKT 0**. Divergenz r10 vs r8: 1/40 Decks. Latenz Plan-Pot 7,8–8,3 s; Oracle 0,205 s je Combo-Solve | Bug behoben | J:106 | Ja — Lehre: **40-Deck-A/A reicht für K2 nicht** |
| 2026-09-08 01:47 | **v10-Gate-Leiter G1–G5** | mehrere (Tests / A/A / Latenz / K1-TV / BR-Holdout / Spiegel) | **G1** grün (13 Blöcke exit 0). **G2a** bestanden (A/A 576 exakt 0). **G2 NICHT GRÜN** (n=10: p99 v10 **7,55 s** > v5-H 5,54 s; Plan gespielt 1/10, deadline 7/10). **G3 VERFEHLT**: K1-TV mittel **0,2085** / p95 0,758 / max 0,876 gegen Budget 0,02/0,05/0,10; untere Schranke 0,1446/0,620/0,819; **Hero außerhalb K1-Support 21/64**. **G4 UNVOLLSTÄNDIG** (11/20 Roots): dE_H **−113,0 ± 18,6 bb/100**, dR −4,04 ± 0,99, B in 11/11 weniger ausbeutbar. **G5 BESTANDEN**: r10 vs r8 **+11,68 ± 10,85** (1.968 Decks) NEUTRAL, CI [−9,39; +33,06]; alle 3 Decks ≤ −100 bb im **Fallback auf die nackte Basis**, offtree 42 % | **NICHT GTOW-reif** | J:107 (`docs/V10_GATES_REPORT.md`, `data/runs/v10/*`) | **Ja — Ship-Entscheid steht: kein Tag, kein GTOW-Lauf; Stand bleibt `auslese-v5`** |
| 2026-09-08 01:53 | G2-Nachmessung nach Live-Mechanik-Fix | Live-Latenz-Kanal, 40 frische Zustände | Ursache: 1 Solve-Worker + 0,5 s Queue-Budget blockierte alles. Nach Fix (3 Worker, 3,0 s Queue, 12 s Deadline): **deadline 0/40** (vorher 7/10), **Plan gespielt 25/40**, **offtree 11/40**, hand_not_in_range 4/40. Latenz B p50 3,04 / p90 8,50 / **p99 10,15 s** vs A p50 2,10 / p99 8,20 s | Kriterium weiterhin **VERFEHLT** | J:108 (`data/runs/v10/G2_latenz_fix_live*`) | Ja |
| 2026-09-08 02:03 | v10-Abschluss der Sitzung | Synthese | ~4,4 Mio Agenten-Tokens, 3 Workflows; A/A 3× exakt 0 (Bänke 1080000/1090000/1100000) | NICHT GTOW-reif | J:109 | Ja |
| 2026-09-08 02:14 | Konsult „ist v10 vollständig?" | Externe Konsultation | NEIN. L1 = Off-Tree/Support/Sub-Schwelle → **nackte Basis ohne v5-Chirurgie**; L2 = Hero außerhalb K1-Support **21/64**, gefordert exakt 0, **kein Epsilon**. G3-Budget 0,02 mit S=12 **nicht prüfbar** (~271 Seeds nötig). Scheduler: 0/40 Deadlines → 95-%-Obergrenze ≈ 7 % | Kandidat, kein v5-Ersatz | J:110 | Ja — definiert die v10.1-Reihenfolge |
| 2026-09-08 02:33 | Konsult „Hybrid v5+v10 ist sowieso am besten?" | Externe Konsultation | **Widerspruch**: H ist ein neuer Bot mit eigenen Nähten, nicht Max(v5,v10); neun Fälle, in denen H schlechter als v5 ist. **Korrektur an der eigenen Statistik**: „214 bb Per-Hand-SD" ist der SE-Koeffizient c = 214 bb/100·√n (Hand-SD ≈ 2,14 bb nach AIVAT) → 2.900 Hände = SE 4; ein ±4-Band braucht ~11.000 Hände; −6 vs −8 mit 80 % Power ~71.000 | Hybrid-Doktrin, 7 Regeln | J:111 | **Ja — und diese Korrektur entwertet jede frühere Lesart der Hand-SD** |

#### Phase 9 — 6-max, Exploit-Gate, Trainer, Kaggle (2026-09-09 / 09-10)

| Datum | Was gemessen | Instrument/Kanal | Ergebnis (Zahl ± Streuung, n) | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-09-09 19:26 | Prince-Takeover in 6-max-Pötten | **pargate6** (gepaarte 6-max-Arena, A/A tag vs tag 288 Decks exakt 0), je 2.992 Decks, Incumbent `tag` | `hybrid` **−23,56 ± 9,02** CI [−40,8; −5,3]; `hybrid_r8` **−21,73 ± 9,01** CI [−39,0; −4,4]; `hybrid_r10` **−26,61 ± 8,93** CI [−43,9; −9,4]; `hybrid_r8` vs `hybrid` +1,82 ± 5,58 NEUTRAL | **ALLE VERWERFEN** | J:112 (`data/runs/verdrahtung/`) | **Ja** — der HU-Bot in 6-max ist schädlich; `six_server`-Takeover default AUS. Einschränkung: Selbst-Ökologie, externer Anker = Analyzer 85,9 %/7,61 |
| 2026-09-09 19:26 | `POKERB_EXPLOIT=1` vs `=0`, je 600 gepaarte Decks pro Liga-Profil | **exploit_gate** (frische Prozesse, Fingerprint verifiziert) | Diff ON−OFF: nit −2,1 ± 9,5; tag **−19,3 ± 15,4**; lag −18,5 ± 13,0; station −17,4 ± 16,3; maniac −15,7 ± 9,6; rock −0,3 ± 9,0; whale −8,3 ± 17,0; shark −14,4 ± 13,7 → **alle 8 Punktschätzer ≤ 0, gepoolt ≈ −12 bb/100 (SE ~4,5)**. 6-max-Reads ON vs OFF: +3,6 ± 13,5 NEUTRAL | **Dirichlet-River-Exploit REFUTIERT** | J:113 | **Ja** — Exploit bleibt in allen Modi AUS; verliert sogar gegen station/maniac/whale |
| 2026-09-09 20:13 | MTT-Modus im Trainer (Produkt) | Tests + Browser | Chip-Erhaltung 300.000 exakt; jeder Platz genau einmal; Determinismus je Seed; Nebentische mean **121 ms** / max 216 ms je Hero-Hand; 7 Tests grün | PRODUKT-BUILD, kein Bot-Verdikt | J:114 (`docs/TURNIER_MODUS.md`) | Ja |
| 2026-09-09 20:39 | Turnier-Bug „immer 100 bb / immer gut gespielt" | Reproduktion + Regression | Ursache: frische Table je Hand hatte `hand_no` 1 → alles nach Hand 1 übersprungen. Nachmessung: 2 volle Turniere (Seeds 3/11: 6 bzw. 31 Hände), Urteile **38 GTO / 41 Abweichung**; Browser-Schnelllauf **3.671 Renders** ohne Fehler | PRODUKT-FIX | J:115 | Ja |
| 2026-09-09 21:06 | Vorab-Fold im Trainer | Tests + Browser | `tests/test_prefold.py` **22 Fälle** grün | PRODUKT-BUILD | J:116 | Ja |
| 2026-09-09 21:31 | Leerer Tisch („Hand #undefined, Pot NaNbb") | Reproduktion | Turnier-bb 50 → Slider-Raster 12,5 Chips → amount 187,5 → pydantic 422 ohne `error` → Client rendert Fehlerantwort als Zustand. 3-Schicht-Fix + Regression | PRODUKT-FIX | J:117 | Ja |
| 2026-09-09 21:54 | `tag_flatfix` (dominierte Offsuit-Broadways nie flatten) vs `tag` | pargate6, 3 Läufe je 2.992 Decks | **+17,7 ± 6,4** (ANWENDEN, perm_p 0,0035) / **+11,36 ± 6,88** (NEUTRAL, p 0,057) / **+19,18 ± 7,01** (ANWENDEN, p 0,0035); gepoolt ≈ **+16 bb/100** | ANWENDEN (3 Läufe) | J:118 (`data/runs/pargate6_tag_flatfix*_2026-09-09.log`) | **Ja — angewendet auf `PROFILES["tag"]`**, Tag `sixmax-tag-flatfix-v1`. Offen: externer Analyzer-Anker |
| 2026-09-10 00:15 | Kaggle-Arena-Brücke gebaut | Kanal-Bau + A/A | Kaggle v1 (via API): GPT-5.6 Sol **+34,9 ± 5,1**; Claude Fable 5.1 +29,7; GPT-5 mini −49,3. Brücke: 4/4 Tests, **A/A exakt 0** nach zwei Fixes — vorher **−37,5**, weil der Bot aus einem RNG-Strom über Hände mischt | KANAL GEBAUT (kein GTO-Anker) | J:119 (`docs/KAGGLE_ARENA.md`) | Ja |
| 2026-09-10 00:26 | GTOW-Leaderboard-Stand, im Browser abgerufen | Externe Ablesung (83 Einträge) | Spitze Bitcrumbs **−3,1** (52.005 Hände, SD 0,9), Trainer −6,2, Roman_SL −7,4, tangtang −12,6, GPT-5.5 XHigh −9,2. **Eigene Einträge (Org „Hampe"): Quantplay −30,4 (Rang 31, 6.587 H), Quantplay v8 −31,6 (Rang 33), Experimental Poker Bot −51,7 (Rang 47)**. Rang nach **Untergrenze** des 95-%-Intervalls → Top-5-Schwelle LCB ≈ **−14,8**. Eichung Kaggle→GTOW über 6 gemeinsame Modelle: **r = 0,37, R² = 0,14** (Residual-SD 15,5); ohne Grok 4 r = 0,88 — **nicht belastbar** | BEFUND | J:120 | Ja — **aber die eigenen Leaderboard-Einträge sind alle aus der v8-Ära**; der heutige Champion ist nie gepostet |
| 2026-09-10 01:06 | Erster Referenzwert im Kaggle-Kanal | Kaggle-Spiegel, 300 gepaarte Decks | `prince[final]` vs `prince[basis]`: bb/100 **+55,83, se 38,02**, trim +6,3, Median 0,0, nonzero 97/300 (32,3 %), nz_pos 45 (Vorzeichen-z **−0,71**), CI95 [−16,67; +134,58], **perm_p 0,0757**; 3.152,9 s (~10,5 s/Deck, 1 Kern) | **NEUTRAL (Kanal-Kalibrierung)** | J:121 (`data/runs/kaggle_prince_vs_basis_2026-09-10.log`) | Ja — **ausdrücklich kein Bot-Verdikt**; Mittelwert tail-getragen; SE 4 bräuchte ~27.000 Decks |
| 2026-09-10 01:19 | Faktenkorrektur durch gpt-5.6-sol, am Code verifiziert | Code-Prüfung | GTOW läuft auf **200 bb** (`gtowizard.py:98` starting_stack 20000, `:281` Blinds [100,50]); unser Preflop-Blueprint feuert erst **ab 140 bb effektiv** (`bot.py:200`) → der Kaggle-Kanal (100 bb) misst **einen anderen Bot** (Heuristik-Kaskade statt Blueprint). Ferner: **−21,12 gehört v4/r6_button, nicht v5**; die „8 bb/100" Lücke sind die Mittelwert-Lesart, gegen die LCB-Grenze −14,8 sind es **~6,3** | KORREKTUR | J:122 (`KONSULT_GPT56_SOL_2026-09-10.md`) | **Ja — korrigiert zwei Doku-Fehler**; „genau unsere Hausgröße" war falsch |
| 2026-09-10 02:13 | AIVAT für den lokalen Kaggle-Kanal | Entwurfsanalyse | Zufallsknoten-Term punktweise erwartungstreu; **Aktions-Term tot** (Bot ist bedingt aufs Deck deterministisch → Korrektur identisch null oder verzerrt); die 10×-Reduktion aus GTOW ist **nicht übertragbar**, weil die gepaarte Spiegelung die Kartenvarianz bereits löscht; je Hälfte könnte die Korrektur die Varianz um Faktor **~1045** erhöhen. Enumerationskosten: River 1,3 / Turn 18,5 / Flop 285 ms / Preflop ~31 s | **ENTWURF, NICHTS GEBAUT** | J:123 (`docs/AIVAT_KAGGLE.md`) | Ja |

---

### Gruppierung nach Typ

| Typ-Familie | Einträge | Zeilen | Was sie tragen |
|---|---|---|---|
| **Orakel-Leads** (`L-VORSCHLAG` 9, `F-VORSCHLAG` 2, `SELFTEST-BEFUND` 5) | 16 | J:1–J:14, J:16, J:19 | Formel-Verletzungen mit Severity in bb. Reine Leads — jeder daraus gebaute Guard wurde später NEUTRAL gemessen |
| **Frühe Gates** (`KANDIDAT-GATE` 3, `SANITY`, `DIAGNOSE-BEDARF`, `AKTEN`) | 6 | J:15, J:17, J:18, J:22, J:23, J:26 | Erste Spiegel-Gates; zwei Negativ-Befunde (Guard feuert nie / kein Effekt) |
| **AUSLESE v1–v3** (`ANWENDEN` 2, `REPLIKATION`, `ANWENDEN+ROTATION`, `REPLIKATION-NICHT-BESTANDEN`, `ROTATION-ABGELEHNT`, `RUNDE4-*` 6, `REPLIKATION-HETEROGEN`, `ANWENDEN+NAME`) | 14 | J:20, J:21, J:24, J:25, J:27, J:28, J:34–J:41 | Der erste Aufstieg; enthält **zwei verhinderte Fehl-Rotationen** und den 3-σ-Replikationsbruch |
| **Transfer/Adversar** (`TRANSFER-TEST` ×3, `EXPLOIT-JAGD`, `EXTERNE-BEWERTUNG`, `FABLE-DUELL`, `FABLE-RETEST`, `R6-DOKTRIN`) | 8 | J:29–J:33, J:71, J:74, J:75 | Die zweite Achse; hier entstand die Zwei-Achsen-Doktrin |
| **Runde 5 / v4** (`R5-*` 15, `R5B-*` 8, `R5C`, `TAUFE`, `VORREGISTRIERUNG`, `ESTIMATOR-V3`, `ARMEE-FIXES`, `V4-VS-BASIS-POOL`, `FINAL-STACK-VS-BASIS`) | 29 | J:42–J:70, J:76 | A/A-Nulltest, Kanal-Vorvermessung, Estimator-Revision, `turn_wert` 3× repliziert |
| **GTOW-Live** (`GTOW-VORREGISTRIERUNG`, `GTOW-NACHT*` 8, `AIVAT-AUDIT-PLAN`) | 10 | J:77–J:88 | Die einzigen absoluten Anker; enthält den Encoding-Bug + die Bergung |
| **Runde 7–9 / v5 / v8** (`R7-*` 2, `R8-*` 2, `R9-PRE`, `TAUFE-AUSLESE-V5`, `V8-*` 3, `TIEFEN-REPLAY-BEFUND`, `PAPER-*`) | 11 | J:89–J:100 | Der GPU-Resolver, `auslese-v5`, der v8-Drop und das Tiefen-Replay |
| **v9/v10** (`V9-*` 2, `V10-*` 6) | 8 | J:100, J:101, J:104–J:109 | v9 abgebrochen; v10 gebaut und **an G3 gescheitert** |
| **Konsults** (`KONSULT-GPT6-*` 4, `KONSULT-SOL-KORREKTUR`) | 5 | J:102, J:103, J:110, J:111, J:122 | Externe Prüfung; zwei davon **widerlegen eigene Thesen** exakt (Q-Softmax, Hybrid-Dominanz) |
| **Verdrahtung/6-max/Exploit** (`VERDRAHTUNG-6MAX-VERDIKT`, `EXPLOIT-GATE-VERDIKT`, `FLATFIX-6MAX-VERDIKT`) | 3 | J:112, J:113, J:118 | Zwei Refutate (Takeover, Exploit) und ein angewendeter 6-max-Fix |
| **Trainer-Produkt** (`TURNIER-MODUS-BUILD`, `TURNIER-MODUS-FIX` ×2, `TRAINER-VORAB-FOLD`) | 4 | J:114–J:117 | Produkt-Builds und -Fixes, ausdrücklich **keine Bot-Verdikte** |
| **Kaggle/Leaderboard** (`KAGGLE-ARENA-BRUECKE`, `GTOW-LEADERBOARD-STAND`, `KAGGLE-REFERENZWERT`, `AIVAT-KAGGLE-ENTWURF`) | 4 | J:119–J:121, J:123 | Der neue Volumen-Kanal + der Leaderboard-Stand |

---

### Was heute noch gilt — die kurze Bilanz aus dem Journal

1. **Champion ist `auslese-v5`** (Commit ec11fde, `r8_stack`), belegt **nur im Spiegel**: +27,6 ± 1,8 vs `r6_button` (3 Läufe), +30,60 ± 5,03 vs eingefrorene Basis (J:92, J:93). **Kein GTOW-Anker.**
2. **Der einzige GTOW-bestätigte Wert des Projekts ist −21,12 (n=979) für `v4_prince`** gegen eine Kontrolle von −31,34 (n=488), J:88 — sequenziell, ungepaart, ohne SE im Eintrag, und laut J:122 **gehört er v4, nicht v5**.
3. **Refutiert und heute bindend:** der Dirichlet-River-Exploit (alle 8 Profile ≤ 0, gepoolt ≈ −12, J:113), der Prince-Takeover in 6-max (3× VERWERFEN, J:112), `r6_ecall` (−4,15 ± 0,97, J:72), `no_limp` (−11,42 ± 2,97, J:96), v8 (gepoolt +2,3 ± 2,4 = NEUTRAL → gedroppt, J:97), v2/`sel_all` (gepoolt +0,69 ± 0,56, J:28), Frequenz-Guards aus Pot-Odds und MDF (J:15, J:17, J:18).
4. **v10 ist nicht GTOW-reif** (G3 verfehlt: K1-TV 0,2085 vs Budget 0,02; Hero außerhalb Support 21/64; G5 neutral bei +11,68 ± 10,85), J:107.
5. **Überholt/zu entwerten:** alle Zahlen aus Runde 1–4 (vor dem Spot-RNG-Seeding-Fix, J:33/J:42/J:50); das NEUTRAL-Verdikt für `turn_wert` in J:52 (Trim-Estimator war kanalblind, J:54); der Nacht-1-Pool −41,11 als „v4-Verdikt" (falscher Arm: nackte Gym-Konfig ohne Resolver/PRINCE, J:81); die Doku-Behauptung, Kaggle messe „genau unsere Hausgröße" (falsch: 100 statt 200 bb, J:122); die eigenen Leaderboard-Einträge −30,4/−31,6/−51,7 (v8-Ära, J:120).

---

# Lauf-Ablage data/runs

`data/runs/` ist die Roh-Ablage der lokalen, in-process laufenden Gates (`pokerbot.autogym.pargate`,
`pargate6`, `envgate`, `orakel_duell`, `exploit_jagd`, `exploit_gate` sowie die v10-Gate-Skripte). Jeder
Lauf legt einen Ordner `JJJJMMTT_HHMMSS_<gate>_<kandidat>/` mit `config.json` (Kandidat, Incumbent,
Deck-Zahl, Worker, Deck-Bank `deck_seed0`, Commit, Host, Zeitstempel) und — nur bei erfolgreichem Ende —
`result.json` an. `INDEX.jsonl` ist die vollständige Kurzliste aller abgeschlossenen Läufe (79 Zeilen,
zuletzt 2026-09-09 21:53); `STAND.md` ist eine ALTE Teilansicht (eingefroren 2026-08-18 02:23, Tabelle
endet bei `20260817_140247`) und deckt keinen einzigen Lauf ab Runde 5 ab.

**Was dieser Kanal messen kann:** ausschließlich einen *relativen, gepaarten Delta* zwischen zwei
Bot-Varianten auf **identischen Decks** in der eigenen Self-Play-Ökologie (HU-Spiegel bzw. 6-max-Liga).
Das ist ein Nichtverschlechterungs-/Regressionsmaß und der billigste Kanal des Projekts (0 €, in-process).
**Was er nicht messen kann:** absolute Spielstärke, Ausbeutbarkeit gegen adaptive oder fremde Gegner, und
Transfer auf GTOW. Belege dafür stehen in diesem Kanal selbst: `r6_ecall` verliert im Spiegel (−4,15) und
`r6_button` ist im Spiegel neutral (+0,71), obwohl beide als Härtungs-Guards gegen einen adaptiven
Gegner gebaut wurden. Der absolute bb/100-Wert einzelner Arme (`bb100_kandidat`/`bb100_incumbent` in
pargate6) schwankt bank-abhängig extrem (tag: −49,59 / −20,89 / +16,48 / +50,54 auf vier Deck-Bänken) und
ist als Niveau-Aussage wertlos.

**Kanal-Feinheiten, die die Zahlen einordnen**
- Nur ein kleiner Deck-Anteil divergiert überhaupt (`nonzero_anteil` z. B. 0,0160 bei r7_river, 0,0347 bei
  r8_stack, 0,3741 bei r6_button vs basis). Der Kanal ist „leise" und die Edge-Verteilung ist fettrandig →
  die 2-SE-Bänder sind eher optimistisch; `perm_p`/Bootstrap-CI sind die härteren Kriterien.
- **Estimator-Bruch:** Läufe bis ca. 2026-08-17 mittags schreiben nur `bb100`/`se`. Ab Commit `73f42b6`
  kommen `bb100_trim`/`median_bb100`/`nonzero`/`vorzeichen_z` dazu, ab `a1cee3c` zusätzlich
  `ci95_lo/hi`/`perm_p`/`boot_b=4000`. Verdikte aus der ersten Gruppe beruhen also auf einem anderen
  Entscheidungsregel-Satz als die späteren — nicht 1:1 vergleichbar.
- **A/A-Pflicht:** Läufe mit `kandidat == incumbent` sind Integritätstests und müssen EXAKT 0 liefern.
  Sie sind hier mitgelistet, weil ein gebrochener A/A jede Zahl derselben Serie entwertet (ein Fall
  gemessen, siehe Abschnitt 6).

---

## 1 — HU-Spiegel (`kanal: pargate_mirror`) — die Hauptkette

Gepaarte Decks, Button-Tausch, Kandidat gegen Incumbent. Positiv = Kandidat gewinnt.

| Datum | Was gemessen | Instrument/Kanal | Ergebnis (bb/100 ± SE, n Decks) | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-08-16 20:42 | Struktur-Smoke der Ablage | pargate (smoke) | keine Zahlen | OK | `data/runs/20260816_204232_struktur_test/result.json` | ja (nur Mechanik) |
| 2026-08-16 20:47 | mdf_guard vs Basis | pargate_mirror | −17,09 ± 22,50 (n=1200) | NEUTRAL | `.../20260816_204741_pargate_mdf_guard/result.json` | nein — n zu klein, durch 99k-Lauf ersetzt |
| 2026-08-16 20:49 | mdf_guard vs Basis | pargate_mirror | −3,26 ± 2,19 (n=99 000) | NEUTRAL | `.../20260816_204907_pargate_mdf_guard/result.json` | ja — MDF-Guard bleibt abgelehnt |
| 2026-08-16 21:32 | sel_guard vs Basis | pargate_mirror | +13,81 ± 17,80 (n=1200) | NEUTRAL | `.../20260816_213258_pargate_sel_guard/result.json` | nein — Smoke, ersetzt durch die 99k-Läufe |
| 2026-08-16 21:33 | sel_guard vs Basis | pargate_mirror | +4,70 ± 2,06 (n=99 000) | ANWENDEN | `.../20260816_213357_pargate_sel_guard/result.json` | ja — 1. von 2 Replikationen (AUSLESE v1) |
| 2026-08-16 22:27 | auslese2 vs Basis | pargate_mirror | +18,01 ± 17,20 (n=600) | NEUTRAL | `.../20260816_222750_pargate_auslese2/result.json` | nein — Smoke |
| 2026-08-16 22:28 | sel_guard vs Basis, 2. Bank (seed0 20000) | pargate_mirror | +7,49 ± 2,08 (n=99 000) | ANWENDEN | `.../20260816_222836_pargate_sel_guard/result.json` | ja — 2. Replikation → AUSLESE v1 getauft |
| 2026-08-16 23:38 | sel_all vs Basis | pargate_mirror | +6,53 ± 22,22 (n=1200) | NEUTRAL | `.../20260816_233809_pargate_sel_all/result.json` | nein — Smoke |
| 2026-08-16 23:38 | lizenz_guard | pargate_mirror | 0,00 ± 0,00 (n=1200) | NEUTRAL | `.../20260816_233838_pargate_lizenz_guard/result.json` | ja — **Nullbefund: Wrapper ohne jede Wirkung** (späterer Audit: „toter Wrapper", `improver.py:172-174`) |
| 2026-08-16 23:40 | auslese2 vs Basis | pargate_mirror | +6,13 ± 2,03 (n=98 960) | ANWENDEN | `.../20260816_234011_pargate_auslese2/result.json` | teilweise — auslese2 wurde später von sel_m15 überholt |
| 2026-08-17 00:10 | lizenz_guard vs basis (expliziter Incumbent) | pargate_mirror | −0,06 ± 0,69 (n=1200) | NEUTRAL | `.../20260817_001012_pargate_lizenz_guard/result.json` | ja — bestätigt den Nullbefund |
| 2026-08-17 00:10 | sel_all vs sel_guard | pargate_mirror | +3,00 ± 1,40 (n=30 000) | ANWENDEN | `.../20260817_001033_pargate_sel_all/result.json` | **nein — Replikation NICHT bestanden** (siehe zwei Zeilen tiefer) |
| 2026-08-17 00:20 | auslese2 vs basis | pargate_mirror | −3,02 ± 16,68 (n=1200) | NEUTRAL | `.../20260817_002020_pargate_auslese2/result.json` | nein — Smoke |
| 2026-08-17 00:21 | sel_all vs sel_guard, 2. Bank | pargate_mirror | +0,44 ± 1,09 (n=30 000) | NEUTRAL | `.../20260817_002130_pargate_sel_all/result.json` | ja — **refutiert den +3,00-Lauf** (`STAND.md:32` „REPLIKATION-NICHT-BESTANDEN") |
| 2026-08-17 00:32 | sel_all vs sel_guard, 3. Bank | pargate_mirror | +0,18 ± 0,73 (n=90 000) | NEUTRAL | `.../20260817_003212_pargate_sel_all/result.json` | ja — **sel_all endgültig verworfen** (`STAND.md:33` „ROTATION-ABGELEHNT") |
| 2026-08-17 13:43 | sel_m15 vs sel_guard | pargate_mirror | +1,11 ± 2,16 (n=30 000) | NEUTRAL | `.../20260817_134312_pargate_sel_m15/result.json` | ja — heterogene Replikation, schwächer als der Kampagnenwert +10,50 |
| 2026-08-17 13:53 | sel_m20 vs sel_m15 | pargate_mirror | −1,52 ± 1,54 (n=30 000) | NEUTRAL | `.../20260817_135314_pargate_sel_m20/result.json` | ja — Margen-Erhöhung von 15 auf 20 bringt nichts |
| 2026-08-17 14:02 | sel_m15 vs sel_guard | pargate_mirror | +2,63 ± 1,22 (n=90 000) | ANWENDEN | `.../20260817_140247_pargate_sel_m15/result.json` | ja — Grundlage der Taufe AUSLESE v3 |
| 2026-08-17 22:29 | turn_wert vs basis, Bank 1000 | pargate_mirror | +9,26 ± 4,88 (trim +6,17; n=29 920) | NEUTRAL | `.../20260817_222907_pargate_turn_wert/result.json` | ja — 1 von 3 Bänken; Punktschätzer positiv, allein nicht entscheidend |
| 2026-08-17 23:08 | turn_wert vs basis, Bank 40000 | pargate_mirror | +16,75 ± 4,84, CI95 [+6,65,+26,08], perm_p 0,0005 (n=29 920) | ANWENDEN | `.../20260817_230825_pargate_turn_wert/result.json` | ja |
| 2026-08-17 23:16 | turn_wert vs basis, Bank 80000 | pargate_mirror | +22,42 ± 4,69, CI95 [+13,11,+31,58], perm_p 0,0002 (n=29 920) | ANWENDEN | `.../20260817_231632_pargate_turn_wert/result.json` | ja — 3×-Replikation, gepoolt in STAND als +16,14 ± 2,77 (`STAND.md:50`) |
| 2026-08-17 23:53 | r6_ecall vs turn_wert | pargate_mirror | −4,15 ± 0,97, CI95 [−6,12,−2,30], perm_p 1,0 (n=29 920) | **VERWERFEN** | `.../20260817_235330_pargate_r6_ecall/result.json` | ja — negatives Ergebnis; Deutung: Value-Folds in der Self-Play-Ökologie |
| 2026-08-18 00:01 | r6_button vs turn_wert | pargate_mirror | +0,71 ± 2,18, perm_p 0,3962 (n=29 920) | NEUTRAL | `.../20260818_000120_pargate_r6_button/result.json` | ja — Härtung ist im Spiegel unsichtbar (Zwei-Achsen-Doktrin) |
| 2026-08-18 01:32 | r6_button (Gesamtkette) vs basis | pargate_mirror | +23,36 ± 5,32, CI95 [+12,75,+33,72], perm_p 0,0002 (n=29 920) | ANWENDEN | `.../20260818_013257_pargate_r6_button/result.json` | ja — der in `STAND.md:59` zitierte „finale Stack vs basis"-Anker |
| 2026-08-30 19:49 | r7_river vs r6_button, Bank 320000 | pargate_mirror | +8,10 ± 1,14, CI95 [+5,90,+10,46], perm_p 0,0002 (n=30 000) | ANWENDEN | `.../20260830_194936_pargate_r7_river/result.json` | ja |
| 2026-08-30 20:01 | r7_bill vs r6_button | pargate_mirror | 0,00 ± 0,00, **nonzero = 0** (n=30 000) | NEUTRAL | `.../20260830_200117_pargate_r7_bill/result.json` | ja — **Nullbefund: der Patch feuerte in 30 000 Decks kein einziges Mal** |
| 2026-08-30 20:12 | r7_wert vs r6_button | pargate_mirror | +8,81 ± 1,25, CI95 [+6,43,+11,39], perm_p 0,0002 (n=30 000) | ANWENDEN | `.../20260830_201255_pargate_r7_wert/result.json` | ja |
| 2026-08-30 20:24 | r7_river vs r6_button, Bank 410000 | pargate_mirror | +7,38 ± 1,05, CI95 [+5,40,+9,46], perm_p 0,0002 (n=30 000) | ANWENDEN | `.../20260830_202416_pargate_r7_river/result.json` | ja — Replikation von +8,10 |
| 2026-08-30 20:42 | r8_stack vs r6_button, Bank 470000 | pargate_mirror | +29,92 ± 3,10, CI95 [+23,71,+36,28], perm_p 0,0002 (n=30 000) | ANWENDEN | `.../20260830_204212_pargate_r8_stack/result.json` | ja |
| 2026-08-30 22:50 | r8_stack vs basis | pargate_mirror | +30,60 ± 5,03, CI95 [+20,61,+40,29], perm_p 0,0002 (n=30 000) | ANWENDEN | `.../20260830_225057_pargate_r8_stack/result.json` | ja — der Gesamt-Anker der Kette auslese-v5 |
| 2026-08-31 00:33 | r8_stack vs r6_button, Bank 530000, Commit `58c51de` | pargate_mirror | +23,76 ± 3,07, CI95 [+17,80,+29,61], perm_p 0,0002 (n=30 000) | ANWENDEN | `.../20260831_003356_pargate_r8_stack/result.json` | ja |
| 2026-08-31 02:42 | r8_stack vs r6_button, Bank 560000 | pargate_mirror | +29,23 ± 3,03, CI95 [+23,41,+35,19], perm_p 0,0002 (n=30 000) | ANWENDEN | `.../20260831_024259_pargate_r8_stack/result.json` | ja — 3 Bänke: +29,92/+23,76/+29,23 |
| 2026-08-31 09:51 | r9_pre vs r8_stack | pargate_mirror | −11,42 ± 2,97, CI95 [−17,12,−5,68], perm_p 1,0 (n=30 000) | **VERWERFEN** | `.../20260831_095123_pargate_r9_pre/result.json` | ja — Preflop-Eingriff schadet, negatives Ergebnis |
| 2026-08-31 20:13 | r9_play vs r8_stack | pargate_mirror | +1,14 ± 2,78, CI95 [−4,12,+6,32], perm_p 0,3472 (n=30 000) | NEUTRAL | `.../20260831_201350_pargate_r9_play/result.json` | ja — r9_play bringt nichts |
| 2026-09-01 00:27 | r9_v8 vs r8_stack, Bank 810000 | pargate_mirror | +3,91 ± 2,85, CI95 [−1,87,+9,50], perm_p 0,0805 (n=30 000) | NEUTRAL | `.../20260901_002705_pargate_r9_v8/result.json` | ja |
| 2026-09-01 04:46 | r9_v8 vs r8_stack, Bank 840000 | pargate_mirror | −1,23 ± 4,36, CI95 [−9,92,+6,97], perm_p 0,6068 (n=14 976) | NEUTRAL | `.../20260901_044634_pargate_r9_v8/result.json` | ja — **Replikation kippt das Vorzeichen; r9_v8 bleibt ungetauft** |
| 2026-09-01 14:21 | sel_m15 vs basis (Mini-Smoke) | pargate_mirror | +9,87 ± 23,60 (n=112) | NEUTRAL | `.../20260901_142115_pargate_sel_m15/result.json` | nein — n=112, CI [−43,46, +52,83] |
| 2026-09-01 14:21 | identische Wiederholung (0,1 s Laufzeit) | pargate_mirror | +9,87 ± 23,60 (n=112) | NEUTRAL | `.../20260901_142133_pargate_sel_m15/result.json` | nein — reiner Cache-/Determinismus-Nachweis, keine unabhängige Messung |
| 2026-09-08 00:20 | r10_stack (v10) vs r8_stack (v5) | pargate_mirror | +11,68 ± 10,85, CI95 [−9,39,+33,06], perm_p 0,156 (n=1968) | NEUTRAL | `.../20260908_002035_pargate_r10_stack/result.json` | ja — v10-Gate G5, **kein Effektnachweis**, nur Nichtverschlechterung |

## 2 — Deck-Bänke / Determinismus (verbrauchte `deck_seed0`)

Die Bänke sind je Code-Stand einmalig zu verwenden. Verbraucht laut `config.json`:
1000 · 5000 · 7000 · 9000 · 13000 · 16000 · 20000 · 25000 · 30000 · 40000 · 41000 · 45000 · 50000 ·
60000 · 65000 · 70000 · 80000 · 85000 · 90000 · 110000 · 120000 · 150000 · 300000 · 310000 · 320000 ·
350000 · 380000 · 410000 · 440000 · 445000 · 470000 · 500000 · 530000 · 560000 · 600000 · 630000 ·
660000 · 690000 · 720000 · 750000 · 780000 · 810000 · 840000 · 870000 · 960000 · 990000 · 1080000 ·
1090000 · 1100000 · 1110000 · 7770000.
Quelle: `config.json` je Lauf-Ordner. (CLAUDE.md nennt 1080000–1110000 als für v10 verbraucht — deckt sich.)

## 3 — 6-max-Liga (`kanal: pargate6`)

Sechs Sitze, Liga `[tag, lag, nit, station, maniac]`, gepaarte Decks; misst den Delta eines Hero-Profils
gegen dieselbe Liga. Absolutwerte (`bb100_kandidat`) sind bank-abhängiges Rauschen, nur der Delta zählt.

| Datum | Was gemessen | Instrument/Kanal | Ergebnis | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-09-09 18:10 | A/A tag vs tag (Smoke) | pargate6 | 0,00 exakt, `aa_exakt_null=true` (n=24); tag absolut −49,59 | NEUTRAL | `.../20260909_181041_pargate6_tag/result.json` | ja — Integritätsnachweis |
| 2026-09-09 18:10 | hybrid_r8 vs tag (Smoke) | pargate6 | +23,09 ± 44,02, CI95 [−49,01,+123,10] (n=24), 112 prince_decisions | NEUTRAL | `.../20260909_181050_pargate6_hybrid_r8/result.json` | nein — n=24, nur Mechanik-Smoke |
| 2026-09-09 18:15 | A/A tag vs tag | pargate6 | 0,00 exakt (n=288); tag absolut −20,89 | NEUTRAL | `.../20260909_181514_pargate6_tag/result.json` | ja |
| 2026-09-09 18:15 | hybrid (Prince-HU im 6-max) vs tag | pargate6 | −23,56 ± 9,02, CI95 [−40,84,−5,26], perm_p 0,9958 (n=2992); 11 417 prince_decisions | **VERWERFEN** | `.../20260909_181534_pargate6_hybrid/result.json` | ja — HU-Prince im 6-max verliert deutlich |
| 2026-09-09 18:18 | hybrid_r8 vs tag | pargate6 | −21,73 ± 9,01, CI95 [−38,98,−4,36], perm_p 0,9923 (n=2992) | **VERWERFEN** | `.../20260909_181853_pargate6_hybrid_r8/result.json` | ja |
| 2026-09-09 18:36 | hybrid_r10 vs tag | pargate6 | −26,61 ± 8,93, CI95 [−43,87,−9,38], perm_p 0,9998 (n=2992) | **VERWERFEN** | `.../20260909_183613_pargate6_hybrid_r10/result.json` | ja — v10-Kette im 6-max am schlechtesten |
| 2026-09-09 19:04 | hybrid_r8 vs hybrid (leiser Kanal) | pargate6 | +1,82 ± 5,58, CI95 [−9,01,+12,90], perm_p 0,3784 (n=2992) | NEUTRAL | `.../20260909_190405_pargate6_hybrid_r8/result.json` | ja — die HU-Chirurgie r8 rettet den Hybrid nicht |
| 2026-09-09 21:49 | tag_flatfix vs tag, seed 1 / Bank 7000 | pargate6 | +17,70 ± 6,40, CI95 [+4,93,+29,92], perm_p 0,0035 (n=2992) | ANWENDEN | `.../20260909_214905_pargate6_tag_flatfix/result.json` | ja — angewendet in Commit `3e1dfce` |
| 2026-09-09 21:50 | tag_flatfix vs tag, seed 2 / Bank 13000 | pargate6 | +11,36 ± 6,88, CI95 [−2,01,+25,16], perm_p 0,057 (n=2992) | NEUTRAL | `.../20260909_215055_pargate6_tag_flatfix/result.json` | ja — **die schwächste der drei Bänke, CI schließt 0 ein** |
| 2026-09-09 21:52 | tag_flatfix vs tag, seed 3 / Bank 16000 | pargate6 | +19,18 ± 7,01, CI95 [+5,59,+33,19], perm_p 0,0035 (n=2992) | ANWENDEN | `.../20260909_215223_pargate6_tag_flatfix/result.json` | ja |

Anmerkung zur Bank-Abhängigkeit: derselbe Incumbent `tag` misst absolut +17,18 / +50,54 / +17,29 auf den
drei Bänken (`bb100_incumbent` in denselben Dateien) — Beleg dafür, dass nur die gepaarte Differenz
interpretierbar ist.

## 4 — Env-Arme (`kanal: envgate`) — KANAL-Zahlen, keine Ship-Evidenz

`envgate` vergleicht Umgebungs-Arme (Flag-Kombinationen) gegen einen Referenz-Arm im selben Gym. Laut
Projekt-Doktrin heißen diese Ergebnisse `KANAL_*` und sind **nie** Ship-Evidenz — sie sortieren Arme vor.
Alle Arme n=11 968 Decks, sofern nicht anders vermerkt.

| Datum | Arm (Env) | Referenz-Wrapper | bb/100 ± SE (trim) | Verdikt | Quelle |
|---|---|---|---|---|---|
| 2026-08-17 19:52 | k3_deception (TURN_DEFENSE 0,07 + SLOWPLAY 0,25) | — | +118,75 ± 76,58 (trim +2,05 ± 1,78), n=240 | NEUTRAL | `.../20260817_195218_envgate/result.json` |
| 2026-08-17 20:18 | **prince** (`POKERB_PRINCE=1`) | Referenz | −68,64 ± 11,90 (trim −18,04) | **VERWERFEN** | `.../20260817_201814_envgate/result.json` |
| 2026-08-17 20:18 | k3_deception | Referenz | +8,72 ± 4,60 | NEUTRAL | ebd. |
| 2026-08-17 20:18 | turn_def_adv (`TURN_DEF_ADVISOR=1`) | Referenz | −3,37 ± 6,95 (trim −3,30) | NEUTRAL | ebd. |
| 2026-08-17 20:18 | raise_narrow 0,5 / 1,0 | Referenz | +5,64 ± 2,88 / +16,78 ± 4,10 | NEUTRAL / NEUTRAL | ebd. |
| 2026-08-17 20:56 | raise_narrow 0,5 / 1,0 (Wrapper sel_m15) | sel_m15 | +6,49 ± 2,60 / +13,65 ± 3,70 | ANWENDEN / ANWENDEN | `.../20260817_205654_envgate/result.json` |
| 2026-08-17 20:56 | kombi_r5 (TD 0,07 + SP 0,25 + RN 1,0, Wrapper turn_wert) | sel_m15 | +26,36 ± 6,04 (trim +2,78) | ANWENDEN | ebd. |
| 2026-08-17 21:14 | turn_def_adv, 2. Bank | sel_m15 | −20,19 ± 6,72 (trim −6,11) | **VERWERFEN** | `.../20260817_211423_envgate/result.json` |
| 2026-08-17 21:14 | kombi_r5, 2. Bank | sel_m15 | +25,22 ± 5,63 | ANWENDEN | ebd. |
| 2026-08-17 21:14 | raise_narrow 0,5, 2. Bank | sel_m15 | +5,51 ± 3,09 | NEUTRAL | ebd. — **Replikation von +6,49 nicht bestanden** |
| 2026-08-17 21:34 | kombi_schlank (nur RN 1,0 auf turn_wert) | sel_m15 | +25,96 ± 5,39 | ANWENDEN | `.../20260817_213451_envgate/result.json` |
| 2026-08-17 21:34 | kombi_r5, 3. Bank | sel_m15 | +36,15 ± 6,01 | ANWENDEN | ebd. |
| 2026-08-17 21:44 | auslese_v3 | **basis** | +21,36 ± 6,03 (trim +13,23) | ANWENDEN | `.../20260817_214458_envgate/result.json` |
| 2026-08-17 21:44 | kombi_r5 (= v4-Kern) | **basis** | +49,79 ± 7,99 (trim +33,82) | ANWENDEN | ebd. — die in `STAND.md:51` zitierte „Finale vs basis: v3 +21,4 / v4 +49,8" |
| 2026-08-17 22:57 | kombi_r5 gegen **fremden** Gegner (GTOBaseline) | `kanal: envgate_vs_gtobaseline` | +95,48 ± 85,66, CI95 [−33,33,+284,90], perm_p 0,1882 (n=24) | **KANAL_NEUTRAL** | `.../20260817_225726_envgate/result.json` |

Der Transfer-Test gegen den fremden Gegner (letzte Zeile) hat n=24 — als Zahl wertlos, als Mechanik-Beleg
brauchbar. Der zugehörige frühere Transfer-Wert steht nur im Journal-Auszug: sel_guard vs GTOBaseline
−3,80 (`STAND.md:37-38`) — d. h. der im Spiegel positive Kandidat war gegen den fremden Gegner negativ.

## 5 — Weitere Kanäle in derselben Ablage

### 5.1 exploit_jagd — 20 adaptive Jäger gegen die eingefrorene Basis
Misst, wie viel ein *lernender* Gegner aus der Basis herausholt. Positive `jaeger_bb100` = die Basis ist
ausbeutbar. Nicht dasselbe wie der Spiegel.

| Datum | Ergebnis | Quelle | Gilt heute? |
|---|---|---|---|
| 2026-08-17 01:43 | Jäger +(−150,59) ± 116,96 über 4 Jäger, 1/4 positiv (400 Hände) | `.../20260817_014358_exploit_jagd/result.json` | nein — Smoke, 400 Hände |
| 2026-08-17 01:44 | Jäger **+7,73 ± 8,70**, 12/20 positiv (100 000 Hände); SD-Netto +5,81, NSD +1,92 | `.../20260817_014431_exploit_jagd/result.json` | ja |
| 2026-08-17 02:02 | Jäger **+8,87 ± 6,90**, 14/20 positiv (100 000 Hände); SD-Netto +19,85, NSD −10,99 | `.../20260817_020232_exploit_jagd/result.json` | ja — der in `STAND.md:36` zitierte Wert |

Die Härtungs-Landkarte kommt aus denselben Läufen: die konvergierten Jäger-Modelle stehen bei
VPIP 0,75–0,76 / fold_to_bet 0,30 / aggression 0,33–0,34 (`.../20260817_020232_exploit_jagd/jaeger_einzeln.json`,
Feld `modell` je Jäger). Fold-Ernte 2026-08-17 02:02: preflop 17 928 / flop 15 879 / turn 2268 / river 2880.

### 5.2 exploit_gate — greift die Exploit-Schicht in die richtige Richtung?
Vergleicht exploit ON vs OFF je Gegnerprofil; `kriterium` prüft, ob das Vorzeichen zur Erwartung passt.

| Datum | Setup | Ergebnis | Verdikt | Quelle |
|---|---|---|---|---|
| 2026-09-09 18:11 | HU, Profile station/tag, n=56 Decks | station +52,10 ± 53,62 (`kriterium: VERLETZT`), tag +55,80 ± 53,58 (`korrekt`); `exploit_korrekt: false` | beide NEUTRAL bei n=56 | `.../20260909_181116_exploit_gate/result.json` |
| 2026-09-09 19:21 | 6-max, 8 Profile, je n=592 Decks | ON−OFF: nit −2,09 ± 9,52 · tag −19,26 ± 15,35 · lag −18,50 ± 12,96 · station −17,35 ± 16,31 · maniac −15,74 ± 9,61 · rock −0,31 ± 8,97 · whale −8,26 ± 17,01 · shark −14,40 ± 13,67 · 6max_liga_reads +3,64 ± 13,45. **Alle NEUTRAL** (kein CI ohne 0), `exploit_korrekt: false`, `verletzt: [nit, station, maniac, whale]` | Kriterium NICHT erfüllt | `.../20260909_192123_exploit_gate/result.json` |

**Negatives Ergebnis, das heute gilt:** die Exploit-Schicht zeigt in 6 von 8 Profilen einen *negativen*
Punktschätzer und verletzt bei 4 Profilen die Vorzeichen-Erwartung — kein einziger Arm ist statistisch
signifikant, aber die Richtung stützt die Exploit-Schicht nicht.

### 5.3 orakel_duell — Entscheidungs-Qualität, keine bb/100
Zählt Regelverstöße je 1000 Entscheidungen zweier Bots auf denselben Decks. Kein Geldmaß.

| Datum | Setup | Ergebnis | Quelle |
|---|---|---|---|
| 2026-08-17 21:32 | turn_wert vs sel_m15, n=1500 Decks | turn_wert 8493 Entscheidungen, sel_m15 8568. Rate/1000: verpasster_wert_turn **3,06 vs 17,04**, verpasster_wert_river 14,72 vs 18,67, call_unter_pot_odds 20,13 vs 24,63, fold_ueber_pot_odds 10,60 vs 10,50, bet_braucht_unplausible_folds 7,54 vs 10,04. Severity-Summe call_unter_pot_odds 2008,1 vs 2456,7 bb | `.../20260817_213232_orakel_duell_turn_wert/result.json` |
| 2026-08-17 22:58 | dasselbe als 20-Deck-Smoke | 89 vs 90 Entscheidungen; Raten unbrauchbar (Chunk-Effekt) | `.../20260817_225803_orakel_duell_turn_wert/result.json` |

Der 2026-08-17-Audit hält fest, dass die F-Stufe (mdf_*) im Duell durch das Chunking praktisch tot ist
(`finalize_frequencies` läuft pro Worker-Chunk, benötigt aber n≥30 je Straße) — die mdf-Raten dieses
Kanals sind daher **nicht interpretierbar** (`praezisions_armee_2026-08-17.json`, `geprueft[1]`).

### 5.4 Kampagnen-Sammelberichte

**Runde 4** (`.../20260817_120031_runde4_kampagne/bericht.json`, 6095,1 s, 2026-08-17):

| Arm | vs basis | vs sel_guard (v1) | n Decks | Verdikt |
|---|---|---|---|---|
| sel_m06 | +0,30 ± 4,03 | +0,06 ± 1,45 | 24 960 | NEUTRAL |
| sel_m10 | +8,72 ± 3,74 | +5,64 ± 1,74 | 24 960 | ANWENDEN |
| sel_m15 | +17,47 ± 3,81 | +10,50 ± 2,10 | 24 960 | ANWENDEN |
| einmal_guard | — | +0,41 ± 1,05 | 24 960 | NEUTRAL (verworfen) |
| **decisive** sel_m15 vs basis | **+8,68 ± 1,28** | — | **183 200** | ANWENDEN |

Der Decisive-Lauf (+8,68 ± 1,28 bei n=183 200) ist die belastbarste Einzelzahl der ganzen Ablage und
korrigiert den optimistischeren 24 960er-Wert (+17,47) deutlich nach unten.

6-max-Katalog derselben Kampagne (30 000 Hände, `bericht.json` → `sechsmax`): Positions-bb/100
BB −28,9 · SB −29,6 · UTG +6,8 · HJ +15,8 · CO +2,4 · BTN +33,5. Facing-Katalog: Flop 21 165 Knoten,
fold_freq 0,216, mittl. Bet 0,431 Pot · Turn 11 565 / 0,297 / 0,384 · River 8143 / 0,337 / 0,365.
Orakel über 298 010 Entscheidungen: HART 0, P 0, L 0, F 0.

**Runde 5** (`.../20260817_195302_runde5_sweep/ergebnis.json`, 42,7 min): A/A-Nulltest sel_m15 vs sel_m15
n=1936 → 0,00 exakt, `max_abs_edge: 0`. Arme gegen sel_m15: sel_all_m15 0,00 ± 0,00 (n=29 920) NEUTRAL;
turn_wert +1,64 ± 4,03 NEUTRAL; wert_plus_all +1,64 ± 4,03 NEUTRAL (identisch zu turn_wert → der
Zusatz-Arm hatte keine Wirkung).

**Runde 5b** (`.../20260817_204025_runde5b_replikation/ergebnis.json`, 52,7 min): turn_wert vs sel_m15
r2 +9,39 ± 4,06 (n=29 920, ANWENDEN), r3 +10,78 ± 4,00 (ANWENDEN), **gepoolt +7,27 ± 2,33 bei n=89 760,
Vorzeichen-z 14,93, nonzero 7702** → ANWENDEN. Der schwache Runde-5-Wert (+1,64) ist in diesem Pool
enthalten; das gepoolte +7,27 ersetzt ihn.

## 6 — A/A-Nulltests (Integrität)

| Datum | Kandidat = Incumbent | n Decks | Ergebnis | Quelle |
|---|---|---|---|---|
| 2026-08-30 19:45 | r6_button | 1200 | 0,00 exakt, nonzero 0 | `.../20260830_194513_pargate_r6_button/result.json` |
| 2026-08-30 19:49 | r7_river | 576 | 0,00 exakt | `.../20260830_194908_pargate_r7_river/result.json` |
| 2026-08-30 20:36 | r8_stack | 600 | 0,00 exakt | `.../20260830_203659_pargate_r8_stack/result.json` |
| 2026-08-31 00:28 | r8_stack | 600 | 0,00 exakt | `.../20260831_002812_pargate_r8_stack/result.json` |
| 2026-08-31 09:23 | r9_play | 600 | 0,00 exakt | `.../20260831_092324_pargate_r9_play/result.json` |
| 2026-08-31 09:43 | r9_pre | 600 | 0,00 exakt | `.../20260831_094336_pargate_r9_pre/result.json` |
| 2026-08-31 13:56 | r9_play | 576 | 0,00 exakt | `.../20260831_135616_pargate_r9_play/result.json` |
| 2026-09-01 00:25 | r9_v8 | 576 | 0,00 exakt | `.../20260901_002535_pargate_r9_v8/result.json` |
| 2026-09-01 11:45 | r10_ernte | 576 | 0,00 exakt | `.../20260901_114509_pargate_r10_ernte/result.json` |
| **2026-09-07 21:32** | **r10_stack** | **576** | **−9,40 ± 10,92, nonzero 13, CI95 [−33,49,+8,15] → A/A NICHT NULL** | `.../20260907_213225_pargate_r10_stack/result.json` |
| 2026-09-07 21:41 | r10_stack, **gleiche Bank 1080000** | 576 | 0,00 exakt, nonzero 0 | `.../20260907_214142_pargate_r10_stack/result.json` |
| 2026-09-07 22:03 | r10_stack, Bank 1090000 | 576 | 0,00 exakt | `.../20260907_220348_pargate_r10_stack/result.json` |
| 2026-09-08 01:52 | r10_stack, Bank 1100000 | 576 | 0,00 exakt | `.../20260908_015248_pargate_r10_stack/result.json` |

Der gebrochene A/A vom 2026-09-07 21:32 ist das wichtigste negative Ergebnis dieser Ablage: 13 von 576
Decks divergierten, obwohl derselbe Bot gegen sich selbst spielte. Der Folgelauf auf **derselben Bank**
ist exakt 0 → der Defekt wurde behoben (CLAUDE.md/`v10-river-fundament`: Bug „hand_id je Hälfte").
Konsequenz für den Leser: **jede v10-Zahl, die vor 2026-09-07 21:41 entstand, ist verdächtig.**
Belege für die Wiederholbarkeit: `data/runs/v10/aa_r10_g2a_pargate.log` und
`data/runs/v10/aa_r10_livefix_pargate.log` (Zwischenstand durchweg +0,00 bb/100, EXIT=0).

## 7 — v10-Gates (`data/runs/v10/`)

Eigener Unterordner mit den Gate-Artefakten der Version v10 („River-Fundament"). Diese Gates messen
NICHT bb/100 gegen einen Gegner, sondern Modell-Treue, Latenz und exakte Best-Response.

| Datum | Was gemessen | Instrument/Kanal | Ergebnis | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-09-07 22:09 | G2a — A/A + Golden-Set nach K1-Änderung | Golden-Set + pargate | Golden A/A 40 Decks nonzero 0, Summe 0,0; Smoke r10 vs r8 40 Decks: 1 Divergenz, Summe −21 580 Chips; pargate-A/A 576 Decks exakt 0 | **BESTANDEN** | `data/runs/v10/G2a_zusammenfassung.json` | ja |
| 2026-09-07 23:14 | G3 — Treue der K1-Hero-Range gegen das Orakel | Gym-Engine, 64 Vorgeschichten / 145 Knoten | **TV K1 vs Orakel: Mittel 0,2085 · p95 0,7579 · max 0,8758** gegen Budget Mittel 0,02 / p95 0,05 / max 0,10. Floor des Orakels: Mittel 0,0950. Korrigierte untere Schranke: Mittel 0,1446. Hero außerhalb K1-Support: **21** von 64. K1-Status ok 60 / teilweise 4 | **`urteil_roh: verfehlt`**, `urteil_budget: orakel_zu_grob` | `data/runs/v10/g3_k1_gate_20260907_231422.json` | ja — der harte Grund, warum v10 nicht GTOW-reif ist |
| 2026-09-08 00:07 | G4 — Ausbeutbarkeit des Plans, exakte BR auf Holdout-Roots | Prüfstand, Arm A = Oracle im **Gym**-Kanal | 11 von 224 Roots (Zeitbudget erschöpft, 5867,5 s). ΔE_H = **−113,037 ± 18,561 bb/100** (Bootstrap-OG95 −85,358); ΔR als B-Nachteil **−4,038 ± 0,988 bb/100** (OG95 −2,614). 0 UNSUPPORTED, 0 GPU-Solve-Fehler. Kontrollen 15/15 grün | **UNVOLLSTÄNDIG** (n=11 < n_min_voll 20); Kriterium in der primären Lesart erfüllt, in der wörtlichen Prüfstand-Lesart verfehlt | `data/runs/v10/G4_holdout.md`, `data/runs/v10/G4_holdout.json` | eingeschränkt — Gym-Arm, n=11, voller Holdout hochgerechnet 33,2 h |
| 2026-09-08 01:52 | G2 — Latenz beider Arme im Live-Kanal | Live-Kanal, 32 Hände / 40 Entscheidungen | v10 plan-p99 **10,152 s** vs v5-H **8,198 s**; max v10 10,152 s; kein Aufruf ≥30 s. Kaltstart v10 2,99 s, v5-H 3,13 s | **VERFEHLT_REDUZIERTE_STICHPROBE** (`plan_p99_unter_8s: false`, `gesamt_p99_v10_le_v5H: false`) | `data/runs/v10/G2_latenz.md` | ja |
| 2026-09-08 01:41 | G5 — Spiegel r10 vs r8 + Katastrophen-Obduktion | pargate_mirror + Replay | +11,68 ± 10,85 (n=1968), CI95 [−9,39,+33,06], perm_p 0,156; 2 Katastrophen-Decks (+160,79 bb / −153,20 bb); Replay 23/23 Decks exakt reproduziert. Klassen: mit_fallback n=14 Summe +202,27 bb (6 negativ), nur_plan n=3 Summe +219,16 bb (0 negativ), kein_plan_pot n=6 Summe −242,99 bb (5 negativ). K2-Status in 23 Decks: offtree 20 / keiner 27 / hand_not_in_range 1 | **BESTANDEN (Spiegel-Kriterium) mit BEFUND** | `data/runs/v10/G5_BERICHT.json`, `.../20260908_002035_pargate_r10_stack/g5_divergenz_auswertung.json` | ja — **alle drei Decks ≤ −100 bb entstehen im Off-Tree-Fallback auf die nackte Basis, nie aus einer Plan-Stichprobe** |
| 2026-09-08 (Export) | Analyzer-Export r10_stack | PokerStars-HH-Export | 200/200 Hände, 4621 CRLF / 0 LF-only, 138 730 Bytes, 75 Stack-Eingriffe. **Reduziert von 1500 auf 200** (10,6–11,6 s/Hand → 88 min Projektion, Abbruch des 500er-Laufs bei 98/500 nach 17 min) | kein EV-Loss-Vergleich möglich (SE ~2,7× breiter) | `data/runs/v10/G5_BERICHT.json` → `analyzer_export` | ja — der Analyzer-Grade zu diesem Export liegt NICHT in `data/runs` |
| 2026-09-07 16:47 | K5-Münze (Reihenfolge der GTOW-Nächte) | Vorregistrierung | `BAAB_dann_ABBA` | — | `data/runs/v10/../v10_muenze.json` | ja — bindende Vorregistrierung, GTOW-Nächte nie gelaufen |

Ergänzend: `data/runs/tiefen_replay_20260901_112429.jsonl` (571 Zeilen) ist ein Entscheidungs-Ledger auf
live geloggten Händen mit drei Armen (`A_tief`, `B_prod`, `C_preflopR`), je Zeile `ev_diff_bb`,
`p_gespielt`, `expl` und `aivat_bb`. Eine aggregierte Auswertung dazu liegt **nicht** in `data/runs`.

## 8 — Kaggle-Arena (`kanal: kaggle_arena`, neu am 2026-09-10)

| Datum | Was gemessen | Instrument/Kanal | Ergebnis | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-09-10 00:12 | A/A prince[final] vs prince[final] | kaggle_arena | **−37,50 ± 94,49 (n=8 Decks), nonzero 4/8** → Log schreibt selbst: „A/A NICHT null: −37.5 bb/100 → STOPP (Mess-Doktrin)" | **A/A GEBROCHEN** | `data/runs/kaggle_aa_2026-09-10.log` (letzte 2 Zeilen) | ja — der Kanal ist NICHT validiert |
| 2026-09-10 01:06 | prince[final] vs prince[basis] | kaggle_arena | +55,83 ± 38,02 (trim +6,30), CI95 [−16,67,+134,58], perm_p 0,0757, nonzero 97/300, Vorzeichen-z −0,71, nz_median −200 Chips (n=300, 3152,9 s) | NEUTRAL | `data/runs/kaggle_prince_vs_basis_2026-09-10.log` (Schlusszeile) | **nein als Effektnachweis** — lief 54 min NACH dem gebrochenen A/A; ohne validierten Kanal ist die Zahl nicht belastbar |
| 2026-09-10 ~02:14 | v9 vs Champion | kaggle_arena | Zwischenstände 50…500 von 600 Decks alle **+0,0 bb/100** (11–12 s/Deck), keine Schlusszeile in der Datei | läuft / unvollständig; +0,0 = identische Politik | `data/runs/kaggle_v9_vs_champion_2026-09-10.log` | offen |
| 2026-09-10 ~01:59 | v10-H0 vs Champion | kaggle_arena | **keine einzige Ergebniszeile** — die Datei enthält nur die beiden OpenSpiel-Fehlermeldungen („Unknown game 'universal_poker'" / „'repeated_poker'") | kein Ergebnis | `data/runs/kaggle_v10h0_vs_champion_2026-09-10.log` | nein |

Alle vier Kaggle-Logs beginnen mit denselben zwei OpenSpiel-Fehlern (`universal_poker` und
`repeated_poker` sind in der installierten OpenSpiel-Version nicht vorhanden) — der Fehler ist offenbar
nicht fatal (die Läufe starten danach), aber er zeigt, dass die geplante OpenSpiel-Umgebung nicht greift.

## 9 — Abgebrochene Läufe (nur `config.json`, kein `result.json`)

91 Lauf-Ordner, 79 mit Ergebnis (= die 79 Zeilen in `INDEX.jsonl`), **12 abgebrochen**. Was übrig bleibt,
ist jeweils nur die `config.json` mit Kandidat/Incumbent/Deck-Zahl/Bank/Commit — keine Zahlen, kein
`edges.json`.

| Ordner | Was geplant war | Commit | Verbleib |
|---|---|---|---|
| 20260816_221126_pargate_sel_guard | sel_guard, 99 000 Decks, Bank 20000 | `ff71726` | um 22:28 mit **derselben Bank 20000** neu gestartet → +7,49 ± 2,08 |
| 20260816_221825_pargate_lizenz_guard | lizenz_guard, 600 Decks, Bank 30000 | `72546b7` | um 23:38 als 1200-Deck-Lauf wiederholt → 0,00 |
| 20260816_222721_pargate_sel_all | sel_all, 600 Decks, Bank 40000 | `95d0ce9` | um 23:38 als 1200-Deck-Lauf wiederholt → +6,53 |
| 20260817_215814_v4wrapper_vs_basis | v4-Wrapper vs basis, 30 000 Decks, Bänke [1000, 40000, 80000] | `7616cf1` | ersetzt durch die drei Einzelläufe `pargate_turn_wert` auf genau diesen Bänken |
| 20260817_223759_pargate_turn_wert | turn_wert vs basis, 30 000, Bank 40000 | `28377da` | um 23:08 mit Commit `a1cee3c` wiederholt → +16,75 |
| 20260817_224507_envgate | 24-Deck-Smoke | `28377da` | um 22:57 mit `3eb88fd` wiederholt |
| 20260831_093318_pargate_r9_play | r9_play vs r8_stack, 30 000, Bank 630000 | `3a4dfe0` | Bank 630000 nie ausgewertet |
| 20260831_140141_pargate_r9_play | dito, Bank 750000 | `ffe3150` | Fortschritt im Treiber-Log `v8_kette_20260831_135616.log` bis 5000/30000 Decks (ETA 310 min) |
| 20260831_154604_pargate_r9_v8 | A/A r9_v8, 600 Decks, Bank 780000 | `ffe3150` | am 2026-09-01 00:25 wiederholt → exakt 0 |
| 20260831_170049_pargate_r9_play | dito, Bank 750000 | `cf1944c` | Log `v8_kette_rest_20260831_170049.log` bis 18 125/30 000 Decks; erst der Start um 20:13 lieferte +1,14 |
| 20260901_065628_pargate_r9_v8 | r9_v8 vs r8_stack, 15 000, Bank 870000 | `cf1944c` | dritte Replikation von r9_v8 nie fertig — der Arm blieb bei 2 widersprüchlichen Läufen (+3,91 / −1,23) |
| 20260901_115900_pargate_r10_ernte | r10_ernte vs r8_stack, 30 000, Bank 990000 | `2d8c8d6` | Log `v9_kette_20260901_114509.log` bis 7500/30 000 Decks (126 min, ETA 378 min) → **r10_ernte hat nie ein Verdikt bekommen** |

Wiederkehrendes Muster: die 30 000-Deck-Läufe der Runden 8–10 laufen 4–4,5 h (115–125 Decks/min) und
werden regelmäßig vor dem Ende abgebrochen. Zwei Arme (`r9_v8`, `r10_ernte`) haben deswegen bis heute
keine abgeschlossene Replikations-Serie.

## 10 — Dateien in `data/runs`, die KEINE Messungen sind

Wichtig für die Einordnung, weil sie Zahlen enthalten, die keine Läufe sind:

- `gtow_v8_protokoll_2026-08-31.json` — **vorregistriertes Protokoll, kein Lauf** („KEIN Lauf gestartet",
  Feld `meta.zweck`). Enthält die SE-Planung (per-Hand-SD 214 → SE 12,4 bei n=300; 4,3 bei n=2500), die
  Abbruchregeln und den zitierten Live-Anker **−30,11 ± 5,51 (n=2899, key #3, v2.2)**. Dieser Anker
  stammt NICHT aus `data/runs`, sondern wird nur referenziert.
- `praezisions_armee_2026-08-17.json` (10 geprüfte + 59 offene Einträge), `root_sweep_2026-08-17.json`
  (12 geprüft / 41 ungeprüft), `niveau_audit_2026-08-17.json` (15er-Rangliste, 44 Lücken),
  `orakel_ausbau_design.json`, `verdrahtungs_debug_2026-08-17.json` — Agenten-Armee-Berichte:
  Code-Audits, Bug-Funde und Design-Vorschläge. Sie enthalten *konstruierte* Rechenbeispiele
  (z. B. der W1-3-FE-Fehler: wahr 0,318 vs berechnet 0,167), keine Messungen.
- `data/runs/fable_duell/aktionen.json` — reine Aktionsliste (`[["raise",200],…]`) des LLM-Adversars,
  ohne bb-Bilanz. Die im Projekt zitierten „62 Hände vs v4 = +115 bb" stehen NICHT in dieser Datei.
- `data/runs/verdrahtung/` — Treiber-Logs der 6-max-Verdrahtungskette vom 2026-09-09 plus die
  Marker-Datei `KETTE_FERTIG`; die Zahlen darin sind identisch mit den Lauf-Ordnern aus Abschnitt 3.
- `data/runs/v10/policy_oracle_cache/` und `_alt_policy_oracle_cache_v1/` — Oracle-Caches, keine
  Ergebnisse.

## 11 — Was in dieser Ablage veraltet ist

1. **`STAND.md` ist tot.** Zeitstempel 2026-08-18 02:23; die Lauf-Tabelle (`STAND.md:7-28`) endet bei
   `20260817_140247` und deckt 63 der 91 Lauf-Ordner nicht ab. Ersetzt durch `INDEX.jsonl`
   (79 Zeilen, 2026-09-09).
2. **Der Journal-Auszug in `STAND.md:32-46` ist eine „letzte 15"-Momentaufnahme** vom 2026-08-17 14:31 —
   nicht das Journal (`data/autogym/journal.jsonl`).
3. **Kleine-n-Smokes** (n ≤ 1200) sind in fast allen Fällen durch große Läufe ersetzt worden: mdf_guard
   −17,09 → −3,26; sel_guard +13,81 → +4,70/+7,49; auslese2 +18,01 → +6,13; sel_m15 +9,87 (n=112) →
   +8,68 (n=183 200). **Jeder dieser Smokes lag um 2–4× daneben.**
4. **`sel_all` und `raise_narrow 0,5`** sind Beispiele für „Erstlauf positiv, Replikation neutral"
   (+3,00 → +0,44 → +0,18 bzw. +6,49 → +5,51 NEUTRAL). Ohne die dritte Bank hätten beide ein
   ANWENDEN bekommen.
5. **Estimator-Wechsel:** Verdikte vor `a1cee3c` haben kein `perm_p` und kein Bootstrap-CI. Der Lauf
   `20260817_222907` (+9,26 NEUTRAL, alter Estimator) und `20260817_230825` (+16,75 ANWENDEN, neuer
   Estimator) sind also nicht nur verschiedene Bänke, sondern auch verschiedene Entscheidungsregeln.
6. **Der Kaggle-Kanal ist unvalidiert** (A/A = −37,5 bei n=8) — alles aus `kaggle_*_2026-09-10.log`
   ist bis zu einem sauberen A/A vorläufig.

---

# GTO-Wizard-Messungen (die teure Achse)

GTO Wizard AI (`researcher.gtowizard.com`) ist ein HU-NLHE-Bot auf **200 bb** effektiv, Blinds [100,50] Chips,
bb = 100 Chips, Cash-Reset je Hand (`gtowizard.py:98` starting_stack 20000, `:281` Blinds [100,50]; belegt in
`data/autogym/journal.jsonl:122` Typ KONSULT-SOL-KORREKTUR). Gemessen wird **AIVAT** (Chance- + Aktions-
Korrektur, serverseitig gerechnet, ca. 10× Varianzreduktion). Der Kanal misst genau eine Sache: **wie viel bb/100
unser Bot gegen einen echten Re-Solver verliert** — absolut, extern, nicht selbstbezüglich. Er ist der einzige
Absolut-Anker des Projekts.

**Was der Kanal NICHT kann:** (1) **Keine Deck-Kontrolle** — die API erlaubt kein Seeding, gepaarte/duplizierte
Austeilung ist unmöglich (`docs/GTOW_DOSSIER.md:12-13`); jeder A/B ist unpaired und braucht n. (2) **Teuer in
Wallzeit** — 1,3–35 s/Hand je Konfiguration; 2.500 Hände ≈ 8–9 h. (3) **Kein Kausal-Zerlegen** — AIVAT-Zellen sind
Realisierungs-, nicht Entscheidungs-Attribution (`docs/HU_OPTIMAL_KARTE.md:35-38`, bindende Lehre). (4) **Die
Streuung ist brutal**: per-Hand-AIVAT-SD ≈ 214–302 bb/100-Einheiten → **+3 bb/100 auf 2σ braucht ≈ 22.000 Hände,
+10 braucht ≈ 2.000** (`docs/GTOW_DOSSIER.md:101`). (5) **Konto-Aggregate mischen Code-Ären** — nur dedizierte
Keys je Kampagne sind lesbar (`docs/GTOW_DOSSIER.md:15-16`).

**Sub-Kanäle, streng zu trennen:**
- **A. Live-AIVAT** (API, teuer, absolut) — dieses Dokument im Kern.
- **B. GTOW-Analyzer** (Hand-History-Upload, per-Entscheidung EV-Loss, $0, deterministisch, keine Varianz) —
  misst Abweichung von GTO je Zug, **nicht** realisiertes Geld gegen einen Gegner.
- **C. GTOW als Datenquelle** (Census/Freq-Mining aus unseren eigenen Hand-Histories) — misst **GTOWs** Verhalten,
  nicht unseres.
- **D. Leaderboard** — Fremd-Vergleich, Rang nach 95-%-Untergrenze.

**Konfigurations-Legende** (ohne die ist keine GTOW-Zahl lesbar): Bot/Stack · Resolver (TexasSolver River/Turn)
an/aus · exploit an/aus · Stacktiefe (immer 200 bb) · Key/Konto. Jede Zeile unten führt sie mit.

---

## A. Live-AIVAT gegen die GTOW-API

Alle Mittelwerte/SE in den Tabellen A2–A5 habe ich **aus den Roh-Hand-Histories nachgerechnet**
(`data/sessions/gtow_hands_<ts>.jsonl`, Feld `aivat` je Hand, bb=100 ⇒ bb/100 = Mittelwert der `aivat`-Werte);
sie reproduzieren die dokumentierten Zahlen exakt. Wo keine HH-Datei existiert, steht die Doku-Quelle.

### A1. Die Alt-Ära (vor 2026-06-19) — SÄMTLICH BUG-INFLATIERT ODER UNBRAUCHBAR

| Datum | Was gemessen | Konfiguration | Instrument/Kanal | Ergebnis (n) | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|---|
| bis 2026-06-19 | Konto-Aggregat aller Code-Ären | gemischt (Alt-Engine, Jam-Spew-Ära) | GTOW `/results` (serverseitig, korrekt) | **−47,18 ± 1,48 bb/100, n=20.859** | historisch, **VERALTET als Bot-Aussage** | `docs/STATE.md:1170` | **NEIN** — Aggregat über tote Code-Stände; als „die Engine ist −47" bis 2026-07-04 falsch zitiert (`docs/STATE.md:1019`) |
| 2026-06-18 | Solver-Search-Agent (Brain treibt TexasSolver) | `--agent-type solver`, feste Nicht-Linien-Ranges | Live-AIVAT, lokal gerechnet | −74,9 bb/100, n=100 | schlecht; **lokal 2× inflationiert** | `docs/STATE.md:1176` | **NEIN** — bb=50-Bug (s. E1) ⇒ real ≈ −37 |
| 2026-06-15/16 | „integrierter Bot", Resolver ON vs OFF | Engine, exploit-primär | Live-AIVAT, lokal | Floor (Resolver OFF) **−70,73 ± 5,83** ≈ Resolver+v1 **−72,06 ± 6,70**, n≈2500 | Resolver **NEUTRAL** (kein Spew-Verursacher) — das *Verhältnis* gilt weiter | `docs/STATE.md:1640-1642` | **Niveau NEIN** (bb=50-Bug ⇒ real ≈ −35); **Verdikt „Resolver neutral" JA** |
| 2026-06-19 | `POKERB_EXPLOIT`-Toggle zur Rekonstruktion der −47 | Engine, exploit ON vs OFF | Live-AIVAT, lokal | OFF −93 ± 23,5 (n=146) ≈ ON −74,7 ± 5,9 (<1σ) | Rekonstruktion **GESCHEITERT** | `docs/STATE.md:1170` | **NEIN** — bb=50-Bug ⇒ real ≈ −46,5 / −37; die daraus gefolgerte „Regression" war ein ARTEFAKT (`docs/STATE.md:1174`) |
| 2026-06-16 | 9 Smokes „grafted preflop" | diverse Engine-Varianten | Live-AIVAT, je n=20 | −19,99 · −34,61 · −36,44 · −46,75 · −111,61 · −125,77 · −295,86 · −527,80 · −599,74 | **WERTLOS** (n=20, SE bis ±548) | `data/gtow_grafted.log:119-509` | **NEIN** — Musterbeispiel „kleine Stichproben lügen" |
| 2026-06-19/20 | unbeschrifteter Engine-Lauf | Arm im Log NICHT vermerkt | Live-AIVAT | **−276,20 ± 146,96**, n=100 (RAW +5,49) | **kein Verdikt** — SE ±147 | `data/_gtow_engine_run.log:234-236`; HH `gtow_hands_1781903796.jsonl` (nachgerechnet n=100, −276,20) | **NEIN** — fehlende Arm-Beschriftung = Kanal-Hygiene-Lehre |

### A2. Brain-Ära (LLM treibt die Engine, 2026-06-19 bis 06-29) — Key #2

Kanal-Hinweis: der Brain-Pfad umgeht `bot.py` (er ruft `api.legalize` direkt) — diese Zahlen sagen **nichts** über
die heutige Engine. Alle Werte aus den Kampagnen-Logs + HH nachgerechnet.

| Datum | Was gemessen | Konfiguration | Ergebnis (n) | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-06-19 | Claude-Opus-Brain + Engine | `--agent-type claude`, Resolver ON, 200 bb | **−28,55 ± 7,25**, RAW −47,42, n=500, ~$8,32 | bestes HU-Ergebnis der Ära; **später als Glücksziehung entlarvt** | `docs/STATE.md:1173` | historisch |
| 2026-06-19 | GLM-Z1-9B (GRPO ckpt-400) + Engine | vLLM auf Pod, frac_bad 0,009 | **−43,30 ± 7,15**, RAW −61,09, n=100 | ≈ Engine-Niveau; erster eigener RL-Bot am Benchmark | `docs/STATE.md:1156`; HH `gtow_hands_1781903258.jsonl` (nachgerechnet n=100, −43,30 ± 7,19) | historisch |
| 2026-06-20 | Preflop-Switch (GLM → Blueprint) | GLM + Blueprint-Routing preflop | **−99,39 ± 48,03**, n=100 | **REFUTIERT + revertiert** — weniger Overfold ⇒ mehr Postflop ⇒ Spew sichtbar | `docs/STATE.md:1160`; HH `gtow_hands_1781910244.jsonl` (nachgerechnet −99,39) | historisch, Lehre gilt |
| 2026-06-20 | **Made-Hand-Wiring A/B** | gleiches Modell/Pod, ON vs OFF, je n=500 | **ON −43,46 ± 9,49 · OFF −84,11 ± 16,91 (Δ ≈ +40,7)** | **ANWENDEN** — größter Serve-Time-Hebel der Brain-Ära | `data/gtow_ab_run.log:26,38` | historisch (Brain-Pfad) |
| 2026-06-21 | **to_call-Fix A/B** (Preflop-Adapter-Bug) | made-hand ON beidseits, je n=500 | **ON (fix) −28,36 ± 10,11 · OFF (Bug) −40,40 ± 12,83 (Δ +12 ≈ 0,7σ)** | **SUGGESTIV, nicht signifikant**; der Bug selbst ist ein bewiesener Korrektheitsfehler | `data/gtow_tocall_ab.log:26,38` | Fix gilt; Δ nie repliziert |
| 2026-06-21 | Solver-Freq-Hint A/B | made-hand+to_call ON, je n=500 | ON −49,21 ± 29,00 · OFF −49,52 ± 11,71 | **NEUTRAL — Hint verworfen** | `data/gtow_hints_ab.log:26,38` | Lehre gilt: Wahrnehmungs-Fixes helfen, Strategie-Nudges nicht |
| 2026-06-21 | Re-SFT → neues GRPO | frisch trainiert, n=500 | **−90,18 ± 23,63** | **REGRESSION — Kampagne verworfen** | `data/gtow_newgrpo.log:26` | Lehre gilt (RL auf Liga ≠ GTOW) |
| 2026-06-21 | dieselbe Re-SFT ohne RL | SFT-Warmstart, n=500 | −71,64 ± 16,13 | schlechter als Baseline | `data/gtow_newsft.log:26` | historisch |
| 2026-06-21 | Produkt-Konfig (grpo_slim + beide Fixes) | n=500 | **−82,25 ± 23,91**, RAW +53,93 | **Fett-Schwanz-Ziehung**, 5 %-getrimmt −19,3 | `data/gtow_confirm_500.txt:26`; `docs/STATE.md:1111` | historisch |
| 2026-06-21 | dieselbe Konfig, n=1500 (gepinnt) | n=1500 | **−68,20 ± 16,82** (getrimmt −39,8) | **Rohmittel bei n≤1500 tail-dominiert = UNZUVERLÄSSIG** | `data/gtow_baseline_1500.log:36`; `docs/STATE.md:1121` | Lehre gilt |
| 2026-06-21 | Zusammenführung der 3 Messungen desselben Modells | −28,36 / −49,52 / −68,20 | **wahres Niveau ≈ −37 bis −40**, „−28,36" war Glücksziehung | **KORREKTUR einer Schlagzeile** | `docs/STATE.md:1119,1121` | Lehre gilt (bindend) |
| 2026-06-22 | Claude-Brain-Lauf | `CLAUDE-BRAIN`, 784 Entscheidungen, 100 % Claude, ~$6,27 | **−52,55 ± 21,82**, RAW −94,87, n=300 | Arm-Label fehlt im Log | `data/claude_gtow.txt:122-126` | historisch; Beleg für fehlende Fingerprint-Disziplin |
| 2026-06-29 | Claude+Engine Live | `--agent-type claude`, Key #2 | **−41,00 ± 14,06**, n=200, $4,14 | bestätigt Claude-Niveau ≈ −35…−45 mit Fett-Schwanz | `docs/STATE.md:1090`; HH `gtow_hands_1782700679.jsonl` (nachgerechnet n=200, −41,00) | historisch |
| 2026-06-29 | **ONTREE-Snap A/B** (Brain-Bet-Sizes auf GTOWs Baum) | je n=300, kontemporär OFF→ON | **ON −39,92 ± 19,36 · OFF −55,92 ± 28,19 (Δ +16, SE_Δ ≈ 34)** | **INKONKLUSIV** → default-OFF | `docs/STATE.md:1091`; HH `gtow_hands_1782736451.jsonl` / `..._1782730702.jsonl` (nachgerechnet) | Mechanik (15 %→100 % on-tree) gilt; EV-Nutzen unbewiesen |
| 2026-06-29 | unzugeordneter 300er-Lauf | Arm unbekannt | −30,86 ± 7,79, n=300 | **nicht zuordenbar** | HH `gtow_hands_1782722688.jsonl` (nachgerechnet) | **NEIN** — ohne Arm keine Aussage |
| 2026-06-21 | Claude-Code-eigene Entscheidungen, gegradet | 264 eigene GTOW-Entscheidungen | 252/262 im GTO-Support (96,2 %); 90 % des −38,41-Verlusts auf River-Enden | Verlust = **Varianz/Cooler**, ein echter Leak: Postflop-Überchecken | `docs/STATE.md:1137,1139`; HH `gtow_hands_1782053161.jsonl`-Ära, Lauf `data/gtow_claudecode.log:32` (−38,41 ± 22,48, n=100) | Methode gilt (deterministisches Grading schlägt n=100-AIVAT) |

### A3. Engine-Ära PRINCE (2026-07) — die wichtigsten Anker

| Datum | Was gemessen | Konfiguration | Ergebnis (n) | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-07-04 | **HEAD-Default-Engine** (der „−47 ist tot"-Lauf) | alle GTO_MODE-Flags OFF, exploit-primär, **Resolver ON**, Key #2 | **−20,09 ± 7,18** (nachgerechnet −20,09 ± 7,19, SD 224), RAW +69,37, n=974 (26 Server-503-Fails) | **gültiger Anker seiner Zeit**; Körper 5 %/10 %-Trim −11,1 / −8,0; 0 Katastrophen | `docs/STATE.md:1019-1021`; HH `gtow_hands_1783177274.jsonl` | **NEIN als Bot-Aussage** (Blinds-Bug, s. E2; Bot seither 5 Versionen weiter) — als Ären-Anker zitierbar |
| 2026-07-04 | Röntgen des −20,09 | dito | Postflop −18,4 von −20,1 (River −8,6, Flop −8,3, Turn −1,6, Preflop −1,6); Verlust in NORMAL-Pötten, nicht in Jams (≥100 bb: −0,7, n=14) | **Diagnose steht** — Leak ist Postflop, nicht Preflop/Jam | `docs/STATE.md:1021`; `docs/GTOW_DOSSIER.md:44-46` | **JA in der Struktur** (River bleibt bis heute Hauptleak, s. `docs/HU_OPTIMAL_KARTE.md:20`) |
| 2026-07-04 | GTO-Mode (exploit OFF + Census-Baum + River-Guards) | `POKERB_GTO_MODE=1`, Resolver ON, Key #2 | **−11,61 ± 3,67** (nachgerechnet SD 37), n=100, 0 Fails | **NUR SMOKE** — die ±3,67 sind unplausibel eng (bei SD 224 wären ±22 zu erwarten) | `docs/STATE.md:961-966`; HH `gtow_hands_1783194039.jsonl` | **NEIN** — später explizit als Glücksziehung eingestuft (`docs/STATE.md:886`) |
| 2026-07-05 | v2-Smoke (LINE_U+ECALL+SIZE_INJECT) | `POKERB_PRINCE=1`, Key #2 | −97,58 ± 100,25, n=98 — davon **eine Hand −98 bb AIVAT**; die anderen 97 ≈ +2 bb/100 | **kein Verdikt**, Diagnose-Wert | `docs/STATE.md:942-944`; HH `gtow_hands_1783205265.jsonl` (nachgerechnet n=98, −97,58, SD 998) | historisch |
| 2026-07-05 | v2.2 300er-Tail-Smoke | PRINCE v2.2, exploit OFF, Resolver ON | −20,38 ± 15,06, RAW +26,6, n=295; **0 Hände ≤ −50 bb** (schlechteste −22,5), SD 259 | **Tail tot** — Verteilungs-Erfolg, Mittelwert n.s. | `docs/STATE.md:894`; HH `gtow_hands_1783218720.jsonl` (nachgerechnet) | Verteilungsbefund gilt |
| 2026-07-05 | **v2.2 Präzisionslauf (vorregistriert n=2500)** | PRINCE v2.2 (7 Flags), exploit OFF, Resolver ON, Key #2 | **−19,70 ± 4,37**, n=2393 (107 Fails), **0 Katastrophen ≤ −50 bb** (schlechteste −38,2), per-Hand-SD **214**, RAW +1,94; Körper −9,0/−6,3 | **damals der Anker (`git tag v2`)**; ehrlicher Zusatz: Mittelwert bewegte sich **nicht** vs HEAD (Δ +0,4 ± 8,4) — Disziplin kaufte Sicherheit, nicht μ | `docs/STATE.md:886-893`; HH `gtow_hands_1783226155.jsonl` (nachgerechnet −19,70 ± 4,37, SD 214) | **NEIN** — gilt als **Blinds-Bug-inflationiert** (s. E2), ersetzt durch −30,11 |
| 2026-07-05 | v2.3.1-Overlay (Barrel-Disziplin) | Overlay-Env auf v2.2 | −31,95 ± 9,55, n=296 (Δ zu v2.2 = 11,5 ± 17,8 = 0,65σ) | **n.s. → Overlay nicht geshippt** | `docs/STATE.md:899-900`; HH `gtow_hands_1783222593.jsonl` | historisch |
| 2026-07-05 | v2.4 Turn-Probe-Arm | Probe-Flag auf v2.2 | −47,55 ± 21,11, n=296 — aber die Probe-KLASSE selbst nur −0,47 bb/Hand über n=18 | **Schlagzeile = Rauschen; Lever PARKIERT** | `docs/STATE.md:876-879`; HH `gtow_hands_1783257360.jsonl` | Lehre gilt |
| 2026-07-05 | v3-Tail-Smoke | PRINCE v3 (+PAIR/RIVER_DEFENSE) | −34,14 ± 9,46, n=295, **0 Katastrophen, schlechteste −19,3 bb**, SD ≈162 | Mittel = n≈300-Rauschen; **Gate war der Analyzer** (s. B) | `docs/STATE.md:865-868`; HH `gtow_hands_1783267831.jsonl` | historisch (v3 seit 2026-07-06 revertiert) |
| 2026-07-06 | **v8 („Quantplay v8") Live-Lauf** | GTO_MODE+Deception+v3+RAISE_NARROW+OVERBET_MENU+PURIFY+TURN_DEF_ADVISOR, Resolver ON | **ABGEBROCHEN bei 1.375 Händen: AIVAT −58…−63** (vorregistriertes Band war −12…−25), systemisch ab Hand 1, ein −271/100-Block | **LIVE-BRUCH — ganze Lever-Familie verworfen** | `docs/STATE.md:614-616` | **JA als Verdikt**: PURIFY/RAISE_NARROW/OVERBET_MENU/TDA sind seither default-OFF (`CLAUDE.md`, PRINCE-Revert) |
| 2026-07-06 | Key-#3-Smoke A | v2.2 revertiert, fixer Blinds-Harness | −16,84 ± 4,86, n=299 | Smoke | HH `gtow_hands_1783357739.jsonl` (nachgerechnet); zitiert `docs/STATE.md:472` | historisch |
| 2026-07-07 | Key-#3-Smoke B | dito | −19,99 ± 14,33, n=299 | Smoke | HH `gtow_hands_1783378134.jsonl` (nachgerechnet) | historisch |
| 2026-07-07 | **Leaderboard-Eintrag „Quantplay v8"** | **v2.2 (`POKERB_PRINCE=1`), exploit OFF, Resolver ON, GEFIXTER Blinds-Harness**, Key #3 | **−30,11 ± 5,51, n=2899 → Rang 24/64**; Batch allein −31,28 ± 5,92 (n=2600, 101 Fails) | **der ehrliche Live-Anker der PRINCE-Ära** | `docs/STATE.md:469-471`; nachgerechnet aus HH `gtow_hands_1783381570.jsonl` (n=2600) **+** `gtow_hands_1783378134.jsonl` (n=299) = **exakt −30,11 ± 5,51** | **JA als Ären-Anker** — laut Doku wahrscheinlicher der ehrlichere Wert als −19,70 |

**Die −19,70-vs-−30,11-Frage (offen, wichtig):** drei Ursachen sind laut Doku nicht sauber trennbar — (1) Pech-
Session, (2) beide früheren Zahlen waren günstige Ziehungen (wahres Niveau ~−25 ± 5), (3) der −30,11-Lauf nutzte
den **gefixten Blinds-Unpack**, während der −19,70-Anker den EV-**schützenden** Overfold-Bug trug. Indiz für (2)/(3):
das alte Konto „Quantplay" liegt mit −30,40 direkt daneben. (`docs/STATE.md:471-478`)

### A4. AUSLESE-Ära — die GTOW-Nächte (2026-08-18, Key #3)

Vorregistrierung: Staffel 20→100→2000, ehrlicher Erwartungsanker −25…−30, v4-Transfer-Hypothese −20…−26,
Smoke-FAIL-Kriterium ≥2 Hände ≤−50 bb ODER ≥1 ≤−80 bb (`data/autogym/journal.jsonl:77`).

| Datum | Was gemessen | Konfiguration | Ergebnis (n) | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-08-18 02:06 | Smoke 20, v1 | v4-Stack | n=18 verwertbar | **NICHT WERTEN** (dict+str-Crash in `wickle_decide`, 2 Hände verloren) | `data/sessions/gtow_manifest_2026-08-18.json` | nein |
| 2026-08-18 02:09 | Smoke 20 | `POKERB_AUSLESE_STACK=r6_button` + TURN_DEFENSE 0,07 + SLOWPLAY 0,25 + **RAISE_NARROW 1,0**, **Resolver OFF**, exploit ON | **−21,34 ± 14,67**, n=20 | mechanisch fehlerfrei, Zahl bedeutungslos | Manifest; HH `gtow_hands_1787011654.jsonl` (nachgerechnet) | nein |
| 2026-08-18 02:16 | Smoke 100 | dito | **−59,03 ± 22,22**, n=100 | **ROTES TUCH** (2σ unter dem Anker; v8-Muster) | `docs/STATE.md:173`; HH `..._1787011782.jsonl` | historisch |
| 2026-08-18 Nacht 1 | 4 × 500 Chunks | Arm `v4_gym_nackt`: **Gym-Konfig nackt** — exploit ON, Resolver OFF, kein PRINCE | A −26,59 ± 7,32 · B −54,98 ± 15,37 · C −31,65 ± 9,88 · D −48,37 ± 17,52 | Chunk-Streuung ±28 bb/100 zwischen 500er-Blöcken = wie laut der Kanal ist | `data/autogym/journal.jsonl:81-82`; HH 1787012286/1787014241/1787016046/1787017672 (alle nachgerechnet, exakt) | historisch |
| 2026-08-18 03:55 | Zwischenpool (A+B+C+Smokes) | dito | **−38,86 ± 6,24, n=1617** | Zwischenstand | `docs/STATE.md:153`; nachgerechnet, exakt | **überholt** durch den Endpool |
| 2026-08-18 04:12 | **Nacht-1-Endpool** | dito | **−41,11 ± 6,31, n=2117** | **KEIN v4-Verdikt** — eine nie zuvor gemessene Konfiguration; 81 % des Verlusts am River (−511 von −628 bb), Muster = altes Jam-Spew/Station | `data/autogym/journal.jsonl:83`; Manifest `nacht1_endpool`; nachgerechnet −41,11 ± 6,31 | **JA als Lehre**: „Gym-Konfig transplantiert sich NICHT nackt ins Live-Fundament" |
| 2026-08-18 06:24 | **Nacht 2, Kontroll-Chunk** | **PRINCE pur, Resolver ON**, exploit OFF | **−31,34 ± 14,16**, n=488 | Kontrolle liegt im −30,11-Referenzband → Kanal konsistent | `data/autogym/journal.jsonl:85`; HH `..._1787019130.jsonl` (nachgerechnet) | **JA** — Referenzpunkt |
| 2026-08-18 08:03/10:04 | **Nacht 2, v4_prince** | AUSLESE-Guard-Kette `r6_button(turn_wert(sel_m15))` **auf** PRINCE + **Resolver ON**, **ohne** RAISE_NARROW | Chunk 2 **−14,33 ± 14,39** (n=490) · Chunk 3 **−27,92 ± 12,12** (n=489) · **gepoolt −21,12 ± 9,41 (n=979)** | **Δ vs Kontrolle = +10,23 bb/100** — bester Live-Wert der AUSLESE-Ära, aber **1 SE-Klasse**, nicht signifikant | `data/autogym/journal.jsonl:86-88`; HH 1787027076/1787033025 (nachgerechnet, gepoolt −21,12 ± 9,41) | **JA — das ist der einzige heute gültige GTOW-Anker** (`docs/STATE.md:56`) |
| 2026-08-18 | Chunk 4 der Nacht 2 | v4_prince | **VERLOREN** (Deadlock 20 Slots / 503-Sturm; Client schreibt HH erst am Ende) | Datenverlust, kein Ergebnis | `data/autogym/journal.jsonl:88` | — (Ursache für den K4-Ledger, `pokerbot/benchmark/gtow_ledger.py:1-16`) |

**Ergebnis-Ranking der Live-Achse, Stand heute:** v4_prince −21,12 ± 9,41 (n=979) > PRINCE-Kontrolle
−31,34 ± 14,16 (n=488) ≈ Leaderboard-Eintrag −30,11 ± 5,51 (n=2899) ≫ v4-Gym-nackt −41,11 ± 6,31 (n=2117).
**Alles danach (auslese-v5 „r8_stack", v8, v9, v10) hat KEINEN GTOW-Anker** — nur Spiegel-Evidenz
(`docs/STATE.md:56`; `docs/HU_OPTIMAL_KARTE.md:112-113`).

### A5. Negativ-Ergebnisse der Live-Achse (Sammlung)

- **Preflop-Switch (GLM)** −99,39 → revertiert (`docs/STATE.md:1160`).
- **Solver-Freq-Hint** neutral (−49,21 vs −49,52) → verworfen (`data/gtow_hints_ab.log:38,46`).
- **Re-SFT+GRPO** −90,18 → Kampagne verworfen (`data/gtow_newgrpo.log:26`).
- **Anti-Spew-Call-Gate** REFUTIERT per $0-Gegenprobe; der Fett-Schwanz kam von Heros -EV-**Betten**, nicht vom
  Overcallen (Memory `gtow-tail-body-vs-spew`, `docs/STATE.md:1112`).
- **v8-Live-Bruch** −58…−63 statt −12…−25 (`docs/STATE.md:614-616`) → PURIFY/RAISE_NARROW/OBM/TDA default-OFF.
- **RAISE_NARROW ist bei Resolver-ON kontraindiziert** (Range-Vergiftung) — deshalb lief v4_prince ohne RN
  (`data/autogym/journal.jsonl:83`-Kontext, `docs/STATE.md:158-160`).
- **Off-Tree-Bet-Sizing gegen GTOW** — kein Ertrag: off-tree AIVAT −1,73 vs on-tree −1,55 (0,3σ), n=3.292
  Hero-Bets aus 13.477 Händen (`docs/GTOW_DOSSIER.md:66-69`).

---

## B. GTOW-Analyzer (per-Entscheidung, $0) — anderer Kanal, andere Aussage

Der Analyzer graded hochgeladene Hand-Histories **je Zug** gegen GTO: „GTO-Score" (Frequenz-Treffer) und
**„Avg EV loss" in bb/100**. Er ist deterministisch und rauschfrei bezüglich Kartenglück — er misst **Abweichungs-
kosten**, nicht realisiertes Geld gegen einen Gegner. Kreuz-Check 2026-07-04: EV-Loss 19,33 ≈ Live-AIVAT −20,09
→ zwei unabhängige Methoden stimmen überein (`docs/TIE_GTOW.md:14-15`, `docs/STATE.md:1032`).

| Datum | Was gemessen | Konfiguration | Ergebnis (n) | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-07-04 | HU-Engine HEAD | exploit-primär, Resolver OFF (Export) | **GTO-Score 53,4 % · EV-Loss 19,33 bb/100 · Freq-Diff 54,6 %**, n=1500 (2599 Züge); Straßen: Preflop 76,2 %, River 53,9 % (28,1 % M+B) | Anker der Analyzer-Achse | `docs/STATE.md:1030-1035`; `docs/TIE_GTOW.md:14` | Ären-Anker |
| 2026-07-04 | 6-max-Kern `tag` | Liga-Kern, nicht `bot.py` | **85,9 % · EV-Loss 7,61 bb/100**, n=1500 | 6-max ist deutlich GTO-näher als HU | `docs/STATE.md:1059`; `docs/STATE.md:53` | **teilweise** — misst den Liga-Kern, nicht das Produkt (`docs/HU_OPTIMAL_KARTE.md:115-117`) |
| 2026-07-04 | GTO-Mode-Hypothese T1 | exploit OFF + Census-Baum + Tracker-Dämpfung | Score **49,8 % (↓3,6pp)** · EV-Loss **17,05 (↓2,28)** · Freq-Diff **54,57 (FLAT)** | **HYPOTHESE REFUTIERT** — exploit-OFF bewegt die Frequenz-Abweichung nicht; sie ist im Kern intrinsisch | `docs/STATE.md:1041-1046`; `data/gtow_grades/gtomode_paired_s55.json` | **JA, bindend** |
| 2026-07-04 | **Score-vs-EV-Tradeoff** (gepaart, Seed 55) | 3 Varianten, identische Deals | HEAD 65,8 %/17,27 · Clamp-Fold 64,5 %/**15,42 (bestes EV)** · Limp→Open-Fix **67,0 % (bester Score)**/19,56 | **Frequenz-Matching kostet Geld** → Fix REVERTIERT; Doktrin „nur bb zählen" | `data/gtow_grades/gtomode_paired_s55.json` (Feld `variants`); `docs/STATE.md:1050-1056` | **JA, bindend** |
| 2026-07-05 | v2.2 vs v3 (gepaart, Seed 55) | identische Deals | **v2.2 = 20,66 · v3 = 17,93 (−2,73)** | **v3 GESHIPPT** (das entscheidende $0-Gate); Kreuz-Check: 20,66 ↔ Live −19,70 | `docs/STATE.md:873-876` | Zahl historisch (v3 seit 07-06 revertiert) |
| 2026-07-05 | v3.1 (flacher Thin-Value-Floor) | gepaart Seed 55 | **19,76 (+1,83 schlechter)** | **REFUTIERT** — 3. Beweis: Frequenz ohne Selektion verliert | `docs/STATE.md:869-872` | **JA, bindend** |
| 2026-07-06 | v3.2 (selektions-bewusster Thin-Value via eCall) | gepaart Seed 55 | **26,14 (+8,21 schlechter)** | **REFUTIERT, schlimmster Arm der Familie** | `docs/STATE.md:795-797` | **JA** |
| 2026-07-06 | Familie C (Seed 56, je 1500) | lokal, Turn-Resolver OFF | Anker 24,90 · **v3.3 RAISE_NARROW 19,41 (−5,49)** · v3.4 AUDIT_FIX **27,52 (+2,62 REFUTIERT)** · v3.5 ADVISOR_ROLE_POS 25,05 (+0,15 neutral) | v3.3 promoviert; **die 9 „Bugfixes" waren verhaltenstragend** | `docs/STATE.md:719-724` | Verdikte gelten; v3.3 später live gebrochen |
| 2026-07-06 | Familie D (Seed 57) | Anker trägt v3.3 | **OVERBET_MENU 16,45 vs 21,27 (−4,82)** promoviert; TURN_OVERBET −4,17, BARREL_DISCIPLINE −3,55 vorgemerkt | promoviert | `docs/STATE.md:711-717` | **NEIN live** (v8-Bruch) |
| 2026-07-06 | Familie E (Seed 59) | Anker v3.3+OBM+PURIFY = 17,54 | **KEINE Promotion**: bd +0,19 · rcd +1,22 · tob +1,95 — die Familie-D-„Sieger" replizierten NICHT | **Ein-Sieger-Regel bestätigt** | `docs/STATE.md:697-704` | **JA, methodisch bindend** |
| 2026-07-06 | PURIFY | Seed 57/59 gepaart | 14,80 vs 16,45 (−1,65, grenzwertig) → promoviert | **später live REFUTIERT** (v8-Bruch, PURIFY tötete stillschweigend SLOWPLAY) | `docs/STATE.md:693-696`; `docs/STATE.md:617-621` | **NEIN** |
| 2026-07-06 | Familie F / v5C | Seed 60 | v5C 17,19 vs 19,06 (−1,87) promoviert; v5A PURIFY2 −0,41 neutral; v5B +1,33 refutiert | promoviert | `docs/STATE.md:678-681` | **NEIN live** |
| 2026-07-06 | Schluss-Set `hu_final_1500` | v8-Vollstack, Seed 61 | **EV-Loss 20,71**, Score 831/355/314 (bester Score der Nacht) | **UNPAIRED** — weder Gewinn noch Verlust belegt; Anker driftete in der Nacht 17,5–21,3 für dasselbe Profil | `docs/STATE.md:670-677` | **JA als Warnung**: Analyzer-Anker driften über Seeds (14,80@s57 vs 17,54@s59 für dasselbe Profil) |
| 2026-07-06 | Danger-Set (1500 härteste Spots) | Champion-Hände gefiltert | EV-Loss **50,18 by design** (nie mit Normal-Sets vergleichen); 591 falsch > 559 richtig | Klasse identifiziert: aufgeblasene Pötte, Raise-Konfrontationen | `docs/STATE.md:696-709` | **JA als Instrument-Lehre** |
| 2026-07-06 | RAISE_COMMIT danger-gepaart | 1500 gefährliche Deals, identische Indizes | Anker 47,41 vs rcd **55,37 (+7,96 SCHLECHTER)** | **DEZISIV REFUTIERT** — 5. Refutation der Familie „flache Anpassung ohne Selektion" | `docs/STATE.md:625-632` | **JA, bindend** |
| 2026-06-29 | Brain+Engine per-Entscheidung | Claude + Engine, 50 Hände / 86 Züge | **69,9 % · EV-Loss 6,1 · Freq-Diff 48 %** | Brain spielt dramatisch GTO-näher als die nackte Engine; **kleine Stichprobe** | `docs/STATE.md:1089` | historisch |
| 2026-06-29 | ONTREE-Snap per-Entscheidung | 60 Hände / 133 Züge | 60,4 % · 47,5 · 51 % | **KONFUNDIERT** (anderer Seed als der Vergleichsarm) → kein Verdikt | `docs/STATE.md:1092` | nein |

**Analyzer-Kanal-Fallen (gemessen, bindend):** Hand-IDs **verbrennen beim ERSTEN Kontakt** — auch bei
gescheiterten Uploads; ein Upload mit überlappenden IDs wurde zu 1.482/1.500 „Duplicate" (`docs/STATE.md:729-742`).
Regeln daraus: ID-Bereiche nie überlappen (≥2000 Abstand), frischer `dayoffset` und frischer Seed je Familie,
CRLF-Pflicht (der Analyzer liest keine LF-Dateien). Monatsbudget ≈ 131k Hände (18k/150k verbraucht, Stand
2026-07-06, `docs/STATE.md:737-740`). Export-Läufe sind **nicht** byte-deterministisch (ungeseedeter globaler
RNG-Strom für Villains Mischstrategien) — Paarung über identische Deals bleibt gültig, Straßen-Attribution nicht
(`docs/STATE.md:717-719`).

---

## C. GTOW als Datenquelle (Messungen ÜBER den Gegner, nicht über uns)

| Datum | Was gemessen | Instrument | Ergebnis (n) | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-07-04 | GTOWs Sizing-Baum (Census) | `research/gtow_tree_census.py` über eigene HH | **12.483 Hände** (86 Hero unbekannt); Flop-Bets SRP {0,35: n=1015, 0,75: 240}, River {0,65: 316, 0,35: 184, 1,0: 151, 1,5: 81, 3,0: 12}; River-Raise 0,5 Pot = Arbeitspferd | Baum-Karte, Grundlage des On-Tree-Snappings | `data/census/gtow_tree.json` (`stats.hands` = 12483); `docs/GTOW_DOSSIER.md:30-41` | **JA** |
| 2026-07-05 | GTOWs Frequenzen je Knoten | `research/freq_mine.py` | **13.675 Hände → 26.823 GTOW-Entscheidungen, 366 Buckets**; Hero-ID-Kreuzcheck 11.633/11.633; Aggressions-Parität walk↔census exakt 18.468 = 18.468 | freier Lehrer-Datensatz | `data/freq_targets/gtow_frequencies.json` (`meta.stats`); `docs/STATE.md:1062-1074` | **JA** |
| 2026-07-05 | Drei Design-Antworten aus dem Mining | dito | (1) vs 2.+ Barrel mit EINEM Paar (n=241): Call 54 %/Fold 43 %/Raise 4 %; River-Top-Pair **Fold 55 %**. (2) River-Bluff-Anteil SRP **28 %** (n=825, mittlere Size 0,81 Pot). (3) Flop-Check-Back IP (n=2.647): Luft 63 %, Traps nur 1,9 % | empirische Anker statt Bauchgefühl | `docs/STATE.md:1066-1074` | **JA** |
| 2026-07-04 | **Angriffsfläche „Off-Grid-Sizes"** | Mining 13.477 Hände, n=3.292 Hero-Bets | GTOWs Fold-% ist glatt, monoton, ≈ exakt MDF (Flop 0,35× → 26,9 % vs MDF 26 %; 1,0× → 50,1 % vs 50 %); alle Midpoint-Tests <2σ; 212 absurde Legacy-Jams (bis 99,5× Pot) → 90,6 % kohärente Folds; **off-tree AIVAT −1,73 vs on-tree −1,55** | **REFUTIERT** (empirisch + architektonisch: GTOW = Ruse-Echtzeit-Re-Solver, kein Translations-Rand) | `docs/GTOW_DOSSIER.md:58-70` | **JA, bindend** |
| 2026-07-05 | GTOWs Raise-Mix | `research/raise_mine.py`, 488 Raises | Jams ~62 % nutted; Flop-Raises 53 % Luft; River-Raises 16 % Luft (polarisiert) | Grundlage für RAISE_NARROW **und** für die RAISE_COMMIT-Refutation | `CLAUDE.md` (v3.3-Block); `docs/STATE.md:626-629` | **JA** |
| 2026-08-30 | Wo v4 gegen GTOW verliert (HH-Mine) | `research/hh_luecken_mine.py` + `gpu_river_audit.py` auf Nacht-2-HH | **87 % des Verlusts am River**; Zelle (River, >100 bb, call) = 9 Hände = **59 % des v4-Verlusts**; GPU-Audit 571/571 River-Entscheidungen: check/fold solver-konform (p 0,86/0,83), **bet die schwächste Klasse (p 0,45)** | Leak-Lokalisierung, Grundlage für r7/r8 | `docs/STATE.md:112-121` | **JA** |
| 2026-08-30 | Tracker-Trennschärfe an GTOW-Händen | `research/river_bill_replay/_diagnose` | Tracker-Equity trennt Gewinner/Verlierer NICHT (0,578 vs 0,513 default; 0,652 vs 0,532 unter PRINCE); Ranges nach 3 Barrels noch 700–900 Combos | **Schwellen-Guard auf Tracker-Basis trägt die River-Defense nicht** | `data/autogym/journal.jsonl:89` (R7-DIAGNOSE) | **JA** |
| 2026-08-31 | Kontrafaktik `river_gpu_guard` auf echten GTOW-Händen | Replay der Nacht-2-Big-Pots | 3/22 Big-Pot-Calls gefoldet = genau die Desaster, **netto +66,9 bb**; inkl. GTO-korrektem Fold des Glücks-Calls #2997685 (AIVAT −9,2 trotz +81,8 real) | **kontrafaktisch positiv, nie live gegengeprüft** | `data/autogym/journal.jsonl` (R8-GPU-RESOLVER, Z90); `docs/STATE.md:132-135` | **JA als Replay-Evidenz, NEIN als Live-Beweis** |
| 2026-08-31 | `river_play_guard`-Vollprofil auf GTOW-Händen | alle 3.904 Nacht-2-Entscheidungen | **32 Eingriffe (0,8 %)**; v4-Arm: call→fold 7 (netto **+278,6 bb**), fold→call 3, bet→check 5 …; AIVAT-Konvergenz auf denselben Händen (#2991749 AIVAT −52,2; #2993037 −33,1) | **GTOW-Achsen-Evidenz positiv** — im Spiegel aber neutral (v8 gedroppt) | `data/autogym/journal.jsonl:94`; `docs/V8_POSTMORTEM.md` | **JA als Befund, ohne Anker unbewiesen** |
| 2026-09-01 | v9-Vorgate „Liegengelassenes" | Tiefen-Replay 571 Entscheidungen mit Aktions-EVs | **Liegengelassen : Fehler = 1,6 : 1**; A1 fehlendes River-RAISE-Spiel = **31,1 bb Overfold in 970 Händen**; A2 Size-Präzision 9,0 bb; A3 Fehl-Value-Bets 11,5 bb (v4) / 27,4 bb (Kontrolle); A4 VERLUST_CALL nur 4,1 bb | Priorisierung nach EV-Hebel; **A4-Lehre: AIVAT-Zellen ≠ Entscheidungs-Attribution** | `docs/HU_OPTIMAL_KARTE.md:13-14,20-38` | **JA** |

---

## D. Leaderboard (Fremdvergleich)

| Datum | Was gemessen | Instrument | Ergebnis | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-07-04 | Leaderboard-Abzug | GTOW-API `/leaderboard` | Bitcrumbs **−3,14** (44.500 H, SD 1,00) · Kevin Rabichow (Mensch) −3,91 · MIT Marvel −5,81 · GPT-5.2 XH −8,26 · GPT-5.5 XH −9,23 · … MIT −16,78 | **niemand schlägt GTOW** | `data/gtow_grades/leaderboard_2026-07-04.json` | überholt durch D2 |
| 2026-09-10 | Leaderboard-Stand + eigene Einträge | Browser, 83 Einträge | Spitze Bitcrumbs −3,1 (52.005 H) · Trainer −6,2 · Roman_SL −7,4 · tangtang −12,6 · GPT-5.5 XHigh −9,2. **Eigene Einträge (Org „Hampe"): Quantplay −30,4 (Rang 31, 6.587 H) · Quantplay v8 −31,6 (Rang 33) · Experimental Poker Bot −51,7 (Rang 47)** — alle v8-Ära; der heutige Stand (~−21) wurde **nie gepostet** | Rang = **Untergrenze des 95-%-Intervalls** ⇒ Hände zählen wie der Mittelwert; **Top-5-Schwelle LCB ≈ −14,8** (≈ −11 bei 10k Händen, ≈ −13 bei 50k); Lücke ≈ 8 bb/100 | `data/autogym/journal.jsonl:120`; `docs/KAGGLE_ARENA.md`; `docs/STATE.md:6-19` | **JA** |
| 2026-09-10 | Eichung Kaggle→GTOW | 6 gemeinsame Modelle | r=0,37 / R²=0,14 (Residual-SD 15,5); ohne Grok 4 r=0,88 | **NICHT BELASTBAR** (Kurvenanpassung) | `data/autogym/journal.jsonl:120`; `docs/STATE.md:12-14` | **JA (als Negativ-Verdikt)** |

---

## E. Mess-Nähte, die GTOW-Zahlen ungültig gemacht haben (die Bug-Chronik)

| Nr | Bug | Wirkung auf Zahlen | Wann gefixt | Quelle |
|---|---|---|---|---|
| **E1** | Lokaler Runner + `gtow_to_state` nahmen `blinds[-1]` = SB = 50 als Big Blind | **ALLE lokal gerechneten bb/100 vor 2026-06-19 sind 2× überhöht** (−74,7 → real ≈ −37; −93 → ≈ −46,5; −71 → ≈ −35). Serverseitige `/results` (−47,18) war immer korrekt. Die daraus abgeleitete „Regression" war ein Artefakt | 2026-06-19 | `docs/STATE.md:1174` |
| **E2** | `gtowizard._parse_history` entpackte die Live-Blinds `[BB,SB]` als `[SB,BB]` | Preflop-Blind-Init **invertiert in JEDEM Live-AIVAT-Lauf** → BB-vs-Open `to_call` 175 statt 125 = +7pp geforderte Equity = eingebauter Preflop-Overfold. **Betrifft −19,70 und −20,09**; Exporte/Analyzer NICHT (anderer Codepfad). Self-Test-Fixture hatte dieselbe falsche Reihenfolge → Asserts fingen es nie | 2026-07-05 (Audit, Commit 8c827cc) | `docs/STATE.md:836-840` |
| **E3** | `gtow_to_state` loggte Preflop-`to_call` als GESAMTPOT | Preflop `required_equity` in 100 % der Preflop-Facing-Bet-Spots aufgebläht (+0,22 im Mittel) → Mit-Ursache des GLM-Preflop-Overfolds (−41/Hand) | 2026-06-21 | `docs/STATE.md:1140` |
| **E4** | `_FINGERPRINT_KEYS` fehlten 13 laufdefinierende Flags (inkl. beider aktiver Gate-Flags) | Lever-Arm-Exporte trugen den Fingerprint des Basisprofils → Arme nicht unterscheidbar | 2026-07-05 | `docs/STATE.md:840-842` |
| **E5** | Treiber `subprocess(text=True)` = cp1252 auf Windows | `UnicodeDecodeError` beim Client-Output ⇒ **jeder ERFOLGREICHE 500er-Chunk galt als Fehlschlag** und wurde retried (Hand-Budget verbrannt). Alle Hände + AIVAT aus den HH-Dateien geborgen, Methode gegen die Smokes exakt validiert | 2026-08-18 | `data/autogym/journal.jsonl:81` |
| **E6** | HH-Logging schrieb erst NACH allen Händen mit `open('w')`, ohne Hero-Kennung/Fingerprint/Arm je Zeile | **Chunk 4 der Nacht 2 komplett verloren**; die Arm-Zuordnung aller Dateien hängt an mtime + Journal + Manifest | Gegenmaßnahme gebaut: `pokerbot/benchmark/gtow_ledger.py` (append-only, flush+fsync je Ereignis, `status` nie zu 0 imputiert) — **im Live-Harness noch nicht verdrahtet** | `docs/V10_FAKTEN.md:232-234`; `pokerbot/benchmark/gtow_ledger.py:1-16` |
| **E7** | `research/analyze_gtow_hands.py:141` setzt **BB=50** | **alle bb/100 aus diesem Skript sind um Faktor 2 überhöht** (API-Blinds sind [100,50]). Betrifft nur nachträgliche Analysen, nicht die Live-Zahlen (deren Regex liest `main.py:220` mit bb=100) | **OFFEN** (dokumentiert, nicht gefixt) | `docs/V10_FAKTEN.md:246-247` |
| **E8** | 409-Waisen (bis zu 20 hängende Hände blockieren das Konto) | Läufe scheitern am Start; **Regel: vor JEDEM GTOW-Start `clear_inprogress.py`** | Prozessregel seit 2026-08-18 | `docs/STATE.md:167-169` |
| **E9** | `gtowizard.py` konstruiert `PokerBot` direkt (v4-Wrapper NICHT im Harness) + Resolver default **ON** (RAISE_NARROW-Falle); `auslese.setze_env` wird im GTOW-Pfad nie gerufen; `button_disziplin` hartkodiert Blinds 50/100 | Ein Arm kann still eine **andere** Konfiguration spielen als beabsichtigt | Adapter gebaut 2026-08-18 (`POKERB_AUSLESE_STACK`); Restpunkte D6 **OFFEN** | `docs/STATE.md:210-213`; `docs/V10_FAKTEN.md:240-242`; `docs/HU_OPTIMAL_KARTE.md:101-102` |
| **E10** | Die HU-Web-App spielte eine nie gemessene Konfig (kein PRINCE, exploit=True, volle r8-Kette + RAISE_NARROW=1,0) | Das gespielte Produkt ≠ die gemessene Definition | Fix „D1" 2026-09-07/08 | `docs/HU_OPTIMAL_KARTE.md:81-85`; `docs/V10_GATES_REPORT.md:18` |

---

## F. Hand-Budget und Gesamtzahl gespielter GTOW-Hände

**Rekonstruierbar (untere Schranke): ≈ 38.650 Hände.** Rechnung:
- **20.859 Hände** Konto-Aggregat bis 2026-06-19 (`docs/STATE.md:1170`) — deckt alle Alt-Ären ab, inkl. der lokal
  geloggten 6.265 Hände vom 16.–19. Juni.
- **24.050 Hände** liegen lokal als Hand-History vor: 65 Dateien `data/sessions/gtow_hands_*.jsonl`, jede Zeile eine
  Hand mit `aivat`-Feld (selbst gezählt: 24.050 Zeilen, 24.050 davon mit `aivat`). Verteilung nach Tag:
  06-16: 5.219 · 06-18: 50 · 06-19: 996 · 06-20: 200 · 06-21: 4.603 · 06-22: 310 · 06-29: 1.105 · 07-04: 1.094 ·
  07-05: 3.673 · 07-06: 299 · 07-07: 2.899 · **08-18: 3.602**.
- Untere Schranke = 20.859 + (24.050 − 6.265) = **38.644**.
- **Hinzu, nicht bezifferbar:** der verlorene Chunk 4 der Nacht 2 (≤ 500 gestartete Hände, nie geloggt) und
  gescheiterte/abgebrochene Hände, die serverseitig zählen (26 Fails im 1000er-Lauf, 101 im 2600er-Batch,
  107 im 2500er-Lauf, 1.375 Hände des abgebrochenen v8-Laufs — letztere sind in den lokalen Dateien nicht
  auffindbar).

**Konten/Keys:** Key #1/#2 (Konto „Quantplay", Alt-Ären + Brain-Ära + Juli-Anker, Aggregat −30,40 auf dem
Leaderboard) · **Key #3** = das saubere Kampagnen-Konto („Quantplay v8", −30,11/n=2899 = Rang 24 bei Eintrag,
heute Rang 33 mit −31,6) · ein drittes Eintrags-Konto „Experimental Poker Bot" (−51,7, Rang 47).
Monatliches Analyzer-Kontingent ≈ 150k Hände, davon 18k verbraucht (Stand 2026-07-06, `docs/STATE.md:737-740`).

**Seit 2026-08-18 wurde KEINE einzige GTOW-Hand mehr gespielt.** Letzte HH-Datei: `gtow_hands_1787033025.jsonl`
(2026-08-18 10:04). Die v10-Staffel wurde bewusst **nicht gestartet** (vorregistrierter Blocker G3 verfehlt,
Hand-Budget, User-Entscheid) — `docs/V10_GATES_REPORT.md:112,121`; `data/autogym/journal.jsonl:109`.

---

## G. Was auf der GTOW-Achse HEUTE gilt — und was fehlt

**Gilt:**
1. **Einziger gültiger Live-Anker: v4-auf-PRINCE, −21,12 ± 9,41 bb/100 (n=979, 2026-08-18 Nacht 2)** — Konfiguration:
   AUSLESE-Guard-Kette `r6_button(turn_wert(sel_m15))` auf `POKERB_PRINCE=1`, **Resolver ON**, exploit OFF,
   **ohne** RAISE_NARROW, 200 bb, Key #3. Kontrolle desselben Kanals (PRINCE pur): −31,34 ± 14,16 (n=488).
   (`data/autogym/journal.jsonl:86-88`; `docs/STATE.md:56`)
2. Der Leaderboard-Eintrag der PRINCE-Ära **−30,11 ± 5,51 (n=2899)** ist die einzige extern verifizierte Zahl mit
   n > 2000 auf dem gefixten Harness.
3. Struktur-Diagnosen (River ist der Hauptleak; Verlust in Normal-Pötten; Preflop nahezu gelöst; Frequenz-Matching
   kostet Geld; Off-Tree-Sizing bringt nichts) sind mehrfach und über zwei unabhängige Kanäle bestätigt.

**Fehlt / offen:**
- **auslese-v5 (`r8_stack`, seit 2026-08-31 der Champion) hat KEINEN GTOW-Anker** — nur Spiegel-Evidenz
  (+27,6 ± 1,8 gepoolt vs r6_button, +30,60 ± 5,03 vs eingefrorene Basis, alles Selfplay). Die dokumentierte
  Nicht-Transitivität des Spiegels macht diese Zahlen ausdrücklich **nicht** zu GTOW-Zahlen (`docs/STATE.md:136-146`).
- **v8, v9, v10 haben keinen Anker.** v8 wurde ohne GTOW-A/B gedroppt (Spiegel neutral); v10 ist per Gate-Entscheid
  **nicht GTOW-reif** (`docs/V10_GATES_REPORT.md:112`). Der v10-„G2 live"-Wert (Plan gespielt 25/40, off-tree 11/40,
  p99 10,15 s) ist ein **lokaler Replay in GTOW-Kanal-KONFIGURATION**, keine API-Hand
  (`data/runs/v10/G2_latenz_fix_live.json`, Feld `laeufe` = lokale Worker-Kommandos).
- **AIVAT-Audit nicht durchgeführt:** der vorregistrierte Falsifikationstest (Fold-Agent muss exakt −75 bb/100
  zeigen; Eigen-AIVAT aus unseren HH gegen die GTOW-Zahl) ist geplant, aber nie gelaufen
  (`data/autogym/journal.jsonl:79`, Typ AIVAT-AUDIT-PLAN).
- **SE-Arithmetik für die nächste Runde:** SE 2 je Arm ⇒ 12k–49k GTOW-Hände (`data/autogym/journal.jsonl:102`).
  Ein Tie-Anspruch (0 innerhalb 2σ) bräuchte ≈ 12.000 Hände (`docs/TIE_GTOW.md:61-62`).

---

# GTOW-Analyzer / Chrome-Upload-Kanal

Der Kanal: wir spielen unseren Bot gegen einen internen Gegner, schreiben gueltige **PokerStars-Hand-Histories**
(`research/pokerstars_export.py` HU, `research/sixmax_export.py` 6-max, `research/claude_export.py` LLM-Brain),
der User laedt die Datei in GTO Wizard → *Analyze → Uploads* hoch, und GTOW benotet **jede Hero-Entscheidung gegen
seine eigene Solver-Loesung**. Zurueck kommen drei Zahlen: **GTO-Score** (Frequenz-/Aktions-Uebereinstimmung),
**Avg. EV loss** (bb/100 gegen die GTO-Aktion) und **Freq-Diff** (Abstand der Aktions-Mischungen), dazu die
Aufschluesselung nach Strasse/Position/Pot-Typ und per-Hand-Grades.

**Was der Kanal kann:** per-Entscheidung graden gegen ein NAHEZU-GTO-Orakel, ohne Varianz — derselbe Export ergibt
dasselbe Urteil; gepaarte Arme (identischer Seed = identische Deals) liefern ein fast rauschfreies Delta zwischen
zwei Bot-Versionen fuer den Preis von Minuten statt Stunden. Er ist der **schnelle** Kanal (Export ~4 min lokal,
Grading Minuten; die Live-API braucht ~8-9 h fuer 2500 Haende — `docs/STATE.md:774`).

**Was er NICHT kann:** (1) Er benotet nur **On-Tree**-Spots — was ausserhalb von GTOWs Loesungsbaum liegt
(Limp/Iso-Pots, krumme Bet-Sizes) faellt als *UNSOLVED* durch und wird gar nicht bewertet → jeder Score ist ein
Score **ueber die gradebare Teilmenge** (Survivorship). (2) Er misst **kein realisiertes Geld** — EV-loss ist eine
per-Entscheidungs-Distanz, kein AIVAT. (3) Er ist **strukturell blind fuer Range-Transparenz-Kosten**: er graded
gegen GTO-Ranges, nicht gegen einen adaptiven Re-Solver, der innerhalb der Hand Glauben aktualisiert
(`docs/STATE.md:618` — genau daran ist v8 live zerbrochen). (4) Der GTO-Score ist als Ziel **gemessen widerlegt**
(siehe Abschnitt „Score-vs-EV").

---

## 1. Upload-Regeln und Fallstricke (alle aus Schaden gelernt)

| Regel | Warum / Beleg | Quelle |
|---|---|---|
| **CRLF-Pflicht** — Exporter pinnt `newline="\r\n"` auf jeder Plattform | Der erste pod/Linux-erzeugte Upload war LF-only; der Analyzer konnte ihn nicht parsen. Lokale Windows-Exporte waren nur zufaellig CRLF (Textmodus). | `research/pokerstars_export.py:293-296`; `docs/STATE.md:748-750` |
| **Hand-IDs verbrennen beim ERSTEN Kontakt — auch bei GESCHEITERTEN Uploads** | Ein abgebrochener LF-Upload hatte die Identitaeten #303–#1801 bereits in GTOWs Registry eingetragen (dessen Upload-Zeile nicht einmal gelistet wird). Der Wiederholungs-Upload: **1.499 Duplikate / 1 verarbeitet** — die eine analysierte Hand war #1802 (97o auf AQ538, user-bestaetigt). | `docs/STATE.md:748-756` |
| **ID-Bereiche duerfen NIE ueberlappen (≥2000 Abstand), frischer `--dayoffset` je Datei, frischer Seed je Wiederhol-Familie** | Familie 3 (idbase 320-323, +1-Schritte) ergab 99,9 % Ueberlappung → verarbeitet wurden 18/1/2/3 Haende bei **1.482 Duplikaten**. Der Analyzer dedupt gegen ALLE frueheren Uploads. Die Konvention „+1 idbase je Arm" war unser eigener Konstruktionsfehler. | `docs/STATE.md:741-747`; Gesetz kodiert in `research/pokerstars_export.py:256-263` |
| Exporter warnt bei Default-`idbase`/`dayoffset` und bei `idbase < 40000` (verbrannter Alt-Bereich 299–1822+) | Audit-Fix 2026-07-05 | `research/pokerstars_export.py:250-263` |
| **Konfig-Sidecar Pflicht** (`*_konfig.json` mit vollem Env-Fingerprint, Seed, idbase, dayoffset) | Ein Lever-Arm ohne Fingerprint ist nicht zuordenbar; `_FINGERPRINT_KEYS` fehlten zeitweise 13 lauf-definierende Flags → Arm-Exporte loggten „plain-v3"-Fingerprints. | `research/pokerstars_export.py:288-293`; `docs/STATE.md:840-842` |
| **Fingerprint luegt bei Runtime-Env-Setzung** | `fingerprint()` liest `os.environ` zur DRUCK-Zeit, Agenten binden `use_*`-Flags bei Konstruktion → Pod-1 loeste 1,4 h lang Turn-Solves, waehrend das Log `TURN_RESOLVER='0'` behauptete. | `docs/STATE.md:766-772` |
| Upload muss der **User** klicken | Das Chrome-`file_upload`-Tool ist sandboxed und lehnt Repo-/Scratchpad-Pfade ab; Claude liest danach die Verdikte via `get_page_text` auf der Uploads-/Stats-Seite. | `memory/gtow-analyzer-loop.md` |
| **Kontingent** ist nicht der Engpass | Account zeigte 18k/150k Haende verbraucht, Reset 28.7 → ~131k Haende/Monat = das reale Screening-Budget (k×1500 pro Arm). | `docs/STATE.md:745-747` |
| ID-Ledger (verbrannt) | 299–1822 (Legacy), 320-323/Tage 45-48, 50000–56000 (Fam. C), 66000–72009, 74000+, 76000–82000+1500 (Fam. E), 84000–91500 (Fam. F), 92000/94000/96000, 120000–126000 reserviert, 130000–130199 (v10). Tage 31-39, 45-48, 50-53, 60, 80-83, 90. Naechster freier Vorschlag: **132000 / Tag 91 / Seed 1110**. | `data/runs/v10/g5_analyzer_ledger.json`; `docs/STATE.md:576,626,685,690,704` |

---

## 2. Absolut-Grades (unpaired) — „wie GTO-nah ist diese Version?"

Einordnung: unpaired-Absolutzahlen sind **zwischen Seeds nicht vergleichbar** (gemessene Anker-Drift 14,80 auf
Seed 57 vs 17,54 auf Seed 59 fuer DASSELBE Profil, `docs/STATE.md:696`). Sie taugen als Landkarte, nicht als Gate.

| Datum | Was gemessen | Instrument/Kanal | Ergebnis (n) | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-06-28 | HU-Engine (exploit-primary, pre-ONTREE) absolut | Analyzer, `bot_hands_1000.txt` | GTO-Score **50,7 %**, Avg EV-loss **22,67 bb/100** (1000 Haende, 800 analysiert) | erste belastbare Absolut-Zahl; „stabil → verlaesslich" | `memory/gtow-analyzer-loop.md`; `docs/STATE.md:1084` | NEIN — Engine seither mehrfach ersetzt (ONTREE, GTO_MODE, PRINCE, AUSLESE) |
| 2026-06-28 | Off-Tree-Anteil (was der Analyzer NICHT graden kann) | Analyzer-API `items[]`, per-Entscheidung | UNSOLVED nach Pot-Typ: **Limp 100 %, Iso 100 %, 3bet ~72 %, SRP ~59 %**; Donk-Bets **0** (Hypothese widerlegt) | strukturelle Kanal-Grenze, nicht Bot-Fehler | `memory/gtow-analyzer-loop.md`; `docs/STATE.md:1084` | JA als Kanal-Eigenschaft; die Zahlen selbst sind pre-ONTREE |
| 2026-06-28 | Streckenschwaeche im gradebaren Teil | Analyzer, per-Strasse | River am schwaechsten: **50,9 % perfect**; SB 66,5 % vs BB 66,1 % GTO-Score (≈ gleich → BB-Verlust ist strukturell/Button-Edge, kein Leak) | Leak-Lokalisierung | `memory/gtow-analyzer-loop.md` | teilweise — „River = schwaechste Strasse" repliziert in JEDER spaeteren Messung |
| 2026-07-04 | HU-HEAD (exploit-primary) absolut | Analyzer, `hu_hands_1500.txt` (file 78ec0a6c) | **GTO-Score 53,4 % · EV-loss 19,33 bb/100 · Freq-Diff 54,6 %** (n=1500, 2599 Zuege); preflop 76,2 %, River 53,9 % (28,1 % Mistake+Blunder) | **Kreuzvalidierung**: 19,33 ≈ Live-AIVAT −20,09 → zwei unabhaengige Instrumente stimmen ueberein; die Abweichung ist echte Kosten, kein Tail-Glueck | `docs/STATE.md:1031-1036`; `docs/TIE_GTOW.md:14-15` | Zahl NEIN (Engine ersetzt), **Methode JA** — die Doppel-Messung ist bis heute das Argument gegen „das war nur Varianz" |
| 2026-07-04 | 6-max Produkt-Kern (`tag`) absolut, klein | Analyzer, `sixmax_hands_300.txt` (file 0e1df589) | GTO-Score **79,3 %**, EV-loss **12,33 bb/100** (n=227 Haende / 263 Zuege) | erste absolute 6-max-Benotung ueberhaupt; **niedriger Zug** | `docs/STATE.md:1047-1057` | NEIN — durch n=1500 ersetzt (79,3 war Rauschen) |
| 2026-07-04 | 6-max Produkt-Kern (`tag`) absolut, stabil | Analyzer, `sixmax_hands_1500.txt` (file 84cfebd7) | **GTO-Score 85,9 % · EV-loss 7,61 bb/100** (1781 Zuege; Perfect 82,6 / Good 8,1 / Inacc 2,2 / Mistake 4,1 / Blunder 3,0) | der GTO-naechste Kern des Projekts; Leaks: preflop 88,5 % stark, alles postflop 57–61 %, **River 22,4 % M+B**; Blinds schwaechste Positionen (SB 74,2 / BB 75,9 vs HJ 91,4); **als preflop-CALLER 23,5 % M+B vs 6,6 % als Raiser** | `docs/STATE.md:1059-1070`; `memory/sixmax-gtow-grade.md` | **eingeschraenkt** — wird am 2026-09-09 noch als „externer Anker" zitiert (`docs/STATE.md:53`), aber der gegradete `tag`-Kern wurde am selben Tag durch `flat_guard` veraendert; neuer Export offen (`docs/STATE.md:30`) |
| 2026-07-04 | EV-Loss-Konzentration (beide Disziplinen) | Analyzer-API, Server-Filter EV-loss ≥ 2 bb bzw. ≥ 8 bb | 6-max: von **54 „Blunders" kosten nur 2 ≥ 8 bb** (ein 3bet-Pot −8,25, ein 4bet-Pot −34,23 = schlechteste Hand des Laufs). HU: 25 Haende ≥ 2 bb = **8,60 von 19,33 bb/100** | Der Score wird von ~0-EV-Mini-Pot-Blunders dominiert; der Schaden sitzt in wenigen grossen Poetten → Hebel = Big-Pot-Stack-off-Disziplin, nicht Blunder-Zaehlen | `docs/gtow_grades/LEAK_MAP.md`; `data/gtow_grades/{hu,sixmax}_leaks_ev2.json`; `docs/TIE_GTOW.md:23-45`; `NOTES.md:52-54` | **JA** — als Struktur-Befund unwidersprochen; deckungsgleich mit dem Live-Fat-Tail-Befund |
| 2026-07-04 | HU-Leak-Landkarte (per Hand) | Analyzer-API `actions_with_correctness_*` | 25 teure HU-Haende: **100 % in den Blinds** (BB 18 / SB 7); #1 Signatur **Flop check→fold vs c-bet, 9/25** (foldet Top Pair Kd6s auf KcTs5h); #2 River-Ueber-Aggression 10/25. Strassen: Flop 11 · River 10 · Preflop 2 · Turn 1 | benannte, reproduzierbare Leak-Klassen (Grundlage der v3-Hebel) | `data/gtow_grades/LEAK_MAP.md`; `data/gtow_grades/hu_leaks_ev2.json` | Klassen JA (River/Blinds-Defense tauchen bis 2026-08 wieder auf), die Hand-Liste NEIN |
| 2026-09-08 | v10 (`r10_stack`) Analyzer-Export | `research/pokerstars_export.py`, 200 statt 1500 Haende | Datei erzeugt (`hu_v10_r10_stack_200.txt`, IDs 130000–130199, Tag 90, Seed 1109) — **kein Grade dokumentiert**; Ship-Entscheid „NICHT GTOW-reif" | offen/unbenutzt | `docs/STATE.md:87-88`; `data/runs/v10/g5_analyzer_ledger.json` | Export existiert, IDs im Ledger reserviert; **kein Ergebnis** |

**Nicht vergleichbar:** die HU-53,4 % und die 6-max-85,9 % duerfen NICHT gegeneinander gelesen werden — 6-max
enthaelt viele leichte Preflop-Folds im Mix (`docs/STATE.md:1057`, `memory/sixmax-gtow-grade.md`).

---

## 3. Der Score-vs-EV-Befund (das wichtigste NEGATIVE Ergebnis des Kanals)

| Datum | Was gemessen | Instrument/Kanal | Ergebnis (n) | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-07-04 | `POKERB_GTO_MODE` (exploit AUS + Census-Baum + Tracker-Damp + River-Guards) vs HEAD | Analyzer, `hu_gtomode_1500.txt`, Seed 55 | **GTO-Score 49,8 % (−3,6 pp, schlechter) · EV-loss 17,05 (−2,28, besser) · Freq-Diff 54,57 % (FLACH)** (n=1500) | **Hypothese WIDERLEGT**: exploit-OFF hob den Score nicht Richtung 85 % und bewegte den Freq-Diff nicht → die Frequenz-Abweichung ist **intrinsisch im Kern** (Blueprint+Advisor+Resolver), nicht das Exploit-Overlay | `docs/STATE.md:977-987`; `docs/TIE_GTOW.md:47-56`; `data/gtow_grades/gtomode_paired_s55.json` | **JA als Lektion** (in CLAUDE.md/Doktrin uebernommen) |
| 2026-07-04 | 3-Wege gepaart Seed 55: HEAD (limpt) / Mode (foldet marginale SB) / Mode-Fix (oeffnet marginale SB) | Analyzer-Uploads-Seite, identische Deals | HEAD **65,8 % / 17,27** · Mode-Clamp **64,5 % / 15,42 (bestes Geld)** · Mode-Fix **67,0 % (bester Score) / 19,56 (schlechtestes Geld)** | **Sauberer Score-gegen-Geld-Tradeoff.** Der SB-Over-Fold ist EV-SCHUETZEND; Frequenz-Angleichung an GTOW kostet Geld, solange postflop schwach ist. Fix **rueckgaengig gemacht** (`bot.py:243`) | `data/gtow_grades/gtomode_paired_s55.json`; `docs/STATE.md:993-1010` | **JA** — daraus die stehende Doktrin „nur bb zaehlen, GTO-Score ist als Ziel tot" (`docs/GTOW_DOSSIER.md:3`, `memory/gto-score-vs-ev-tradeoff.md`) |

---

## 4. Gepaarte Hebel-Arme (der eigentliche Nutzen des Kanals) — Kampagne 2026-07-05/06

Protokoll (bindend formuliert, `docs/STATE.md:577-590`): pro Arm 1500 Haende auf identischem Seed, Verdikt nur
gegen den **Anker derselben Familie**, Promotion braucht Δ > max(1,5; 2·SE_diff), Effekt muss in der ZIEL-Klasse
sitzen, hoechstens EIN Gewinner pro Familie. Alle Zahlen sind **Avg. EV loss (bb/100), kleiner = besser**.

### Familie A/B — lokal, Seed 55

| Datum | Arm | Ergebnis (n=1500) | Δ vs Anker | Verdikt | Quelle |
|---|---|---|---|---|---|
| 2026-07-05 | v2.2 (Anker) | **20,66** | — | Anker; Kreuz-Check: sein Live-AIVAT war −19,70 | `docs/STATE.md:872-874` |
| 2026-07-05 | **v3** (PAIR_DEFENSE 0.10 + RIVER_DEFENSE 0.06) | **17,93** (bei 1305/1500 verarbeitet) | **−2,73** | **PROMOTED** (im vorhergesagten Band −2,5…−4,5) | `docs/STATE.md:857-861,872-874` |
| 2026-07-05 | v3.1 (flacher River-Thin-Floor 0,40 + cbet-damp 0,28) | **19,76** | +1,83 | **REFUTIERT** — dritte Messung derselben Lektion: Frequenz-Matching OHNE die Selektion des Lehrers verliert EV | `docs/STATE.md:863-870` |
| 2026-07-05 | v3.2 (selektions-bewusster Thin-Value via e_call ≥ 0,5) | **26,14** | +8,21 | **REFUTIERT, schlimmster Arm der Familie** — unsere getrackte Range ist nicht die Selektion des Lehrers, e_call systematisch ueberschaetzt; River-Thin-Klasse komplett geparkt (4. Fehlschlag) | `docs/STATE.md:795-806` |

### Familie C — lokal, Seed 56, alle 1500/1500 verarbeitet (Dedup-Gesetz hielt)

| Datum | Arm | Ergebnis | Δ vs Anker 24,90 | Verdikt | Quelle |
|---|---|---|---|---|---|
| 2026-07-06 | Anker | 24,90 | — | Anker-Skala verschoben ggue. Familie A/B (anderer Seed/Exporter) — Vergleich mit 17,93 nur DIAGNOSTISCH | `docs/STATE.md:725-731` |
| 2026-07-06 | **v3.3 RAISE_NARROW** | **19,41** | **−5,49** | **PROMOTED**, klarer Sieger; Effekt-Lokus geprueft: 65/65 divergierende Haende enthalten einen Raise (Flop 32 / Turn 30 / River 3) | `docs/STATE.md:725-729` |
| 2026-07-06 | v3.4 AUDIT_FIX (9 Audit-Funde) | **27,52** | +2,62 | **REFUTIERT** — die „Bugfixes" waren verhaltenstragend; default-OFF geparkt | `docs/STATE.md:726-727` |
| 2026-07-06 | v3.5 ADVISOR_ROLE_POS | **25,05** | +0,15 | NEUTRAL, geparkt (dient zugleich als Rausch-Boden ≈ ±1) | `docs/STATE.md:727-728,715-717` |

### Familie D — Seed 57 (Anker traegt bereits v3.3)

| Datum | Arm | Ergebnis | Δ | Verdikt | Quelle |
|---|---|---|---|---|---|
| 2026-07-06 | Anker | 21,27 | — | — | `docs/STATE.md:711-712` |
| 2026-07-06 | **OVERBET_MENU** | **16,45** | **−4,82** | **PROMOTED** | `docs/STATE.md:711-712` |
| 2026-07-06 | TURN_OVERBET | — | −4,17 | Screen bestanden → in Familie E weitergereicht (Ein-Sieger-Regel) | `docs/STATE.md:713-714` |
| 2026-07-06 | BARREL_DISCIPLINE | — | −3,55 | dito | `docs/STATE.md:713-714` |
| 2026-07-06 | **PURIFY** | **14,80** | −1,65 vs 16,45 | **PROMOTED, grenzwertig** (unter der 1,5-Schwelle promoted wegen unabhaengiger Score-Bestaetigung 822/358 vs 792/378) | `docs/STATE.md:699-703` |

### Familie E — Seed 59: **keine einzige Promotion** (die Ein-Sieger-Regel bestaetigt)

| Datum | Arm | Ergebnis | Δ vs Anker 17,54 | Verdikt | Quelle |
|---|---|---|---|---|---|
| 2026-07-06 | anchor_e (v3.3+OBM+PURIFY) | 17,54 | — | Anker | `docs/STATE.md:689-690` |
| 2026-07-06 | bd_e (BARREL_DISCIPLINE) | — | +0,19 | **REPLIKATION GESCHEITERT** (in Familie D noch −3,55) | `docs/STATE.md:690-694` |
| 2026-07-06 | rcd_e (RAISE_COMMIT) | — | +1,22 | verworfen | `docs/STATE.md:690` |
| 2026-07-06 | tob_e (TURN_OVERBET) | — | +1,95 | **REPLIKATION GESCHEITERT** (in Familie D −4,17) | `docs/STATE.md:690-694` |

→ Methodisch der wertvollste Block: **Familien-D-„Sieger" ueberlebten den Wechsel des Fundaments nicht.** Haette
man sie als Buendel geshippt, waere Rauschen geshippt worden.

### Familie F + Abschluss

| Datum | Arm | Ergebnis | Δ | Verdikt | Quelle |
|---|---|---|---|---|---|
| 2026-07-06 | v5C **TURN_DEF_ADVISOR** | **17,19** vs Anker 19,06 | **−1,87** | **PROMOTED** (Familien-Sieger) | `docs/STATE.md:683-685` |
| 2026-07-06 | v5A PURIFY2 | — | −0,41 | neutral, geparkt | `docs/STATE.md:683-685` |
| 2026-07-06 | v5B OBM=2 + BD | — | +1,33 | verworfen | `docs/STATE.md:683-685` |
| 2026-07-06 | Gesamt-Stack `hu_final_1500` (Seed 61) | **EV-loss 20,71**; Score 831 correct / 355 wrong / 314 partial | UNGEPAART | **KEIN Verdikt** — bester Score der Nacht, aber frischer Seed ohne Anker (Anker driften 17,5–21,3 fuer dasselbe Profil) → weder Gewinn noch Verlust belegt; Kompositions-Risiko explizit NICHT ausgeschlossen | `docs/STATE.md:670-681` |
| 2026-07-06 | Abschluss-Doppel: final_a (Seed 62) / final_b (Seed 63) | **18,33 / 39,87** (je n=1500) | — | Seed-Geiselhaft belegt: die Differenz sind **zwei Haende** (KJ Top-Pair durch Flop-Check-Raise + River-Raise in 400bb-Pot = 39,86 EV-loss in EINER Hand; J9-Analog 345bb = 38,25). Die echten Cooler (85s, KK-pre) graden **~0 EV-loss** → der Grader trennt Cooler von Fehlern | `docs/STATE.md:650-660` |
| 2026-07-06 | **RAISE_COMMIT, danger-gepaart** (1500 haerteste Deals aus 6000 Champion-Haenden, gleiche Indizes beide Arme) | Anker **47,41** vs rcd **55,37** | **+7,96 SCHLECHTER** | **REFUTIERT, entscheidend** — der flache +0,07-Raise-Respekt foldet die korrekten Call-downs mit weg (642→611 correct); 5. Widerlegung der Flach-Anpassungs-Familie | `docs/STATE.md:637-648` |
| 2026-07-06 | `hu_danger_1500` (Danger-Set, Kalibrierung) | **EV-loss 50,18 BY DESIGN**; 591 Wrong > 559 Correct | — | Kalibrier-Set, **nie gegen Normal-Sets vergleichen**; Top-Verlierer sind eine scharfe Klasse: aufgeblaehte Pots mit marginalen Haenden in RAISE-Konfrontation (98o 287bb-Pot River x-b-R −84bb; Q7o −29; A2o/A6o −28/−21) | `docs/STATE.md:703-710` |

**Status dieser ganzen Leiter heute: HISTORIE.** Am 2026-07-06 wurde das Profil auf **PRINCE v2.2 zurueckgesetzt**
— PURIFY, RAISE_NARROW, OVERBET_MENU, TURN_DEF_ADVISOR und v3 PAIR/RIVER_DEFENSE sind explizit als
„Analyzer-only und/oder v8-Live-Brecher" auf default-OFF gestellt (`docs/STATE.md:452-462`). Grund: der
2500-Hand-Live-Lauf brach bei 1375 Haenden mit **AIVAT −58…−63** ab (Band war −12…−25), Verdacht K1/K2 = PURIFY
vergiftete die Hero-Range des Re-Solvers und toetete stillschweigend SLOWPLAY (0,5 < 0,25 feuert nie)
(`docs/STATE.md:612-624`). **Methoden-Lektion woertlich im Repo: „the fast Analyzer channel outran the slow live
channel" — die bindende Live-Bestaetigung starb im Rueckstand, waehrend Hebel gestapelt wurden**
(`docs/STATE.md:621-623`).

---

## 5. Fruehe A/B-Entscheidungen ueber diesen Kanal (2026-06-28/29)

| Datum | Was gemessen | Instrument/Kanal | Ergebnis (n) | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-06-28 | `POKERB_ONTREE` (Postflop-Bets auf {0,33/0,5/0,75/1/1,25}×Pot snappen) | Analyzer A/B, je 1000 Haende, + `duplicate.py` als EV-Gate | GTO-Score 50,7 → **53,1 %**; voll-analysiert 61 → **64 %**; EV-loss 22,7 → **21,2**; realisiertes EV **NEUTRAL** (−59,2 vs −60,6 bb/100, im Rauschen) | **GESHIPPT als Default-ON** — GTO-Ausrichtung ohne messbare EV-Kosten | `docs/STATE.md:1085`; `memory/gtow-analyzer-loop.md` | **JA** — `POKERB_ONTREE` ist bis heute Default `"1"` (`pokerbot/strategy/postflop.py:22-27`) |
| 2026-06-29 | `POKERB_RIVER_VALUE` (heuristischer Value-Floor: bet eq≥0,75 mit 0,85 Freq) | Dual-Gate: Analyzer + `duplicate.py` | Analyzer **NEUTRAL** (River-perfect 47,3 → 48,0; M+B 26,4 → 27,7 minimal schlechter); duplicate.py **+23,0 ± 11,4 bb/100** | **Gates widersprechen sich** → validierter *bounded exploit*, aber KEIN GTO-Fix; blieb default-OFF | `docs/STATE.md:1093` | Lektion JA („stumpfe River-Regeln verbessern GTO-Treue nicht"); Flag weiterhin gegated |
| 2026-06-29 | `POKERB_RIVER_LA` (line-aware River-Advisor, neu trainiert auf Pot-Typ-River-Subgames) | Analyzer + `duplicate.py` | River-perfect 47,3 → **56,3 % (+9 pp)** — **aber survivorship-verseucht** (Voll-Analyse-Rate 66 → 57 %, 18 Fehler, meist good→perfect-Umklassifizierung; M+B 26,4 → 25,4 unveraendert); realisiertes EV **+3,2 ± 5,0 = neutral** | **NICHT geshippt** (default-OFF); der River-Leak ist echt range-aware-hart | `docs/STATE.md:1094`; `memory/river-advisor-rebuild.md` | JA als Verdikt (Flag bis heute default-OFF) |
| 2026-06-29 | LLM-Brain + Engine (Claude Opus als Hero) absolut | Analyzer, `claude_brain.txt` | **GTO-Score 69,9 % · EV-loss 6,1 bb/100 · Freq-Diff 48 %** (50 Haende / 86 gegradete Zuege); preflop 85 % perfect | Brain spielt per-Entscheidung dramatisch GTO-naeher als die nackte Engine — **aber kleine Stichprobe**: Headline verlaesslich, per-Strasse (Flop n=20 45 %, Turn n=15 60 %, River n=11 54 %) verrauscht | `docs/STATE.md:1089` | historisch (Brain-Track ist seit 2026-07-04 sekundaer) |
| 2026-06-29 | `POKERB_BRAIN_ONTREE` (Snap fuer den Brain) | Analyzer, `claude_ontree.txt` | On-Tree-Rate 15 % → **100 %** (mechanisch bestaetigt); Grade **60,4 % / EV-loss 47,5 / Freq-Diff 51 %** (60 Haende / 133 Zuege) | **KONFUNDIERT** (Seed-Fehler: ontree Seed 31 vs brain Seed 7 = verschiedene Haende, nicht gepaart) + Survivorship in beide Richtungen → **kein Verdikt**, blieb default-OFF | `docs/STATE.md:1091-1092` | historisch; die Lektion „ungepaart = wertlos" wurde Protokoll |

---

## 6. Sub-Kanal: MINING von GTOWs eigener Politik (kein Upload, gleiche Datenbasis)

Nicht der Analyzer, aber im selben Auftrag: GTOW sitzt in unseren geloggten Live-Haenden auf der anderen Seite und
BEIDE Hole-Cards sind geloggt → seine Aktions-Mischung ist **kostenlose Nahe-Solver-Supervision**, offline, $0,
deterministisch. Was der Sub-Kanal NICHT kann: er zeigt die **Frequenz** des Lehrers, nicht seine **Selektion** —
und genau daran sind vier Hebel gescheitert (v3.1, v3.2, RAISE_COMMIT, limp→open).

| Datum | Was gemessen | Instrument | Ergebnis (n) | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-07-04 | GTOWs empirischer Bet-Size-Baum | `research/gtow_tree_census.py` → `data/census/gtow_tree.json` | **12.483 Haende**, 86 hero_unknown; 22 Baum-Knoten-Klassen; Open 2,25 / 3bet 4× / River 0,65-0,35-1,0-1,5 | Grundlage von `POKERB_GTOW_TREE`/`_SIZES` und der Off-Tree-Karte | `data/census/gtow_tree.json` (`stats`); `NOTES.md:56-58` | JA als Datensatz; die Baum-Konstanten sind im GTO_MODE verdrahtet |
| 2026-07-05 | GTOWs per-Knoten-Aktionsmix | `research/freq_mine.py` → `data/freq_targets/gtow_frequencies.json` | **13.675 Haende** aus 47 Log-Dateien, **26.823 GTOW-Entscheidungen**, 366 Buckets, 99 hero_unknown; Beispiel SB-RFI-Knoten: raise 0,8224 / fold 0,1536 / call 0,024 (n=6795) | „freier Lehrer"; **Caveat im Datensatz selbst**: GTOWs Spot-Verteilung ist durch UNSERE Linien konditioniert | `data/freq_targets/gtow_frequencies.json` (`meta.stats`, `meta.caveat`) | JA als Datensatz, sofern man die Konditionierung mitliest |
| 2026-07-05 | Zusammensetzung von GTOWs RAISE-Ranges nach Size-Klasse | `research/raise_mine.py` → `data/freq_targets/gtow_raise_ranges.json` | **17.132 Haende, 488 Raises** getallied, 118 hero_unknown; z. B. `flop|srp|normal`: air 115 von 213 Kombis ≈ 54 % Luft | Kalibriert v3.3 RAISE_NARROW; belegt zugleich, warum pauschaler „Raise-Respekt" verliert (Raise-Ranges sind POLARISIERT) | `data/freq_targets/gtow_raise_ranges.json` (`stats`); `docs/STATE.md:641-644` | JA als Datensatz |
| 2026-07-05 | Unsere Frequenz-Abweichung je Bucket | `research/freq_diff.py` (TVD gegen die geminten Mixe, Bootstrap n=1000, MIN_N=30) | Instrument gebaut; groesste per-Entscheidungs-TVD: **Flop-Fold 59 % vs GTOWs 10 % mit einem PAAR (TVD 0,486)** | benannter Leak, floss in `error_prognosis.json` als −5,0 bb/100 Budget | `research/freq_diff.py:1-14`; `data/gtow_grades/error_prognosis.json` | Instrument JA; das Budget ist eine PROGNOSE, keine Messung |

---

## 7. Abgrenzung: `research/study_grade.py` ist NICHT dieser Kanal

Der Auftrag nennt es mit, aber es misst etwas anderes: `study_grade.py` rekonstruiert 264 eigene Entscheidungen
aus einem Live-Log und benotet sie gegen **unser eigenes Orakel** (TexasSolver via `api.solve_node` + Blueprint +
Equity-Mathematik), ausdruecklich weil **GTOW keine Spot-Benotung ueber die API anbietet** — nur der Chrome-Upload
kann das (`docs/CLAUDE_VS_GTOW_STUDY.md:36-38`).

| Datum | Was gemessen | Instrument/Kanal | Ergebnis (n) | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-06-21 | Claude-Code als Hero, 264 Entscheidungen | eigenes Orakel (TexasSolver, Coverage postflop 160/162 = 98,8 %), Rekonstruktion 264/264 exakt | **252/262 in GTO-Support = 96,2 %**; preflop 95 % rein-GTO; OpenAI-Zweitmeinung stimmt bei 82 % der haertesten Spots zu, jede Abweichung ≤ 1,2 bb | Der −38 AIVAT war Varianz/Cooler, kein Entscheidungs-Leak; **einziger echter Leak: postflop Ueber-Checken (Flop sumDev 35,0 / Turn 28,1)** | `docs/CLAUDE_VS_GTOW_STUDY.md:12-27` | als Befund JA; **anderes Orakel** — nicht mit Analyzer-Scores mischen |

---

## 8. Was der Kanal ueber sich selbst gelernt hat (Kanal-Validitaet)

| Datum | Befund | Beleg | Konsequenz |
|---|---|---|---|
| 2026-07-06 | **Exporte sind nicht byte-deterministisch**: ein UNGESEEDETER globaler RNG-Strom laesst Villains Misch-Strategie pro LAUF anders realisieren (erste Divergenz = Villain-Aktion in Hand 1 bei null Hero-Diff) | `docs/STATE.md:717-722` | Paarung ueber identische Deals bleibt gueltig (symmetrisches, unverzerrtes Misch-Rauschen), **Strassen-Attribution der Divergenz ist NICHT kausal** |
| 2026-07-06 | Anker-Skalen driften ueber Seeds: **14,80 (S57) vs 17,54 (S59)** fuer dasselbe Profil | `docs/STATE.md:696` | Familien-uebergreifende Vergleiche verboten |
| 2026-07-06 | Rausch-Boden im gepaarten Kanal ≈ **±1** (der v3.5-Wiederholungsarm lag bei +0,15) | `docs/STATE.md:715-717` | erklaert die Promotions-Schwelle 1,5 |
| 2026-07-05 | Der Blinds-Reihenfolge-Bug ([BB,SB] als [SB,BB] entpackt) traf **jeden Live-AIVAT-Lauf**, die **Exporte/Analyzer-Grades aber NICHT** (anderer Code-Pfad) | `docs/STATE.md:838-841` | Analyzer-Zahlen aus dieser Zeit sind an DIESER Stelle sauber, die Live-Anker (−19,70/−20,09) waren bug-inflationiert |
| 2026-07-06 | Familien-Arme liefen mit `POKERB_TURN_RESOLVER=0`, die Produktion turn-ON | `docs/STATE.md:762-765` | Ein Sieger dieser Familie ist **Turn-OFF-Evidenz**; bindende Bestaetigung waere ein Live-Smoke gewesen |
| 2026-07-06 | **Analyzer ist blind fuer Range-Transparenz** (graded gegen GTO-Ranges, nicht gegen einen Re-Solver, der IN der Hand Glauben aktualisiert) | `docs/STATE.md:617-620` | Erklaert, warum PURIFY im Analyzer gewann und live −58 produzierte |
| 2026-08-17 | **Kanal-Widerspruch, gemessen:** TURN_DEF_ADVISOR (Analyzer-Sieger −1,87) im Self-Play-Gate **VERWERFEN (−20, Vorzeichen-z negativ)** — „die v5C-Analyzer-Historie haelt im Self-Play nicht" | `docs/STATE.md:241-243` | Analyzer-Verdikte replizieren nicht automatisch im Mirror-Kanal |
| 2026-08-17 | RAISE_NARROW (Analyzer-Sieger −5,49) repliziert im Gym **nur in resolver-OFF-Kanaelen** (+16,8/+13,7/+9,2), v8-K3-Warnung bleibt bindend | `docs/STATE.md:240-241` | Der Hebel ist kanalabhaengig, nicht universell |
| 2026-09-01 | Grundsatz aus dem v8-Postmortem: Mirror kann nur klare Fehler bepreisen, der Spiegelgegner exploitiert weder Size-Muster noch Mix-Fehler — dieselbe Zwei-Achsen-Lektion | `docs/V8_POSTMORTEM.md:33-45` | Analyzer/GTOW-Achse und Mirror-Achse **messen verschiedene Dinge und duerfen sich nicht vertreten** |

---

## 9. Kurzbilanz: was von diesem Kanal HEUTE noch traegt

1. **Der Kanal selbst** (Export → Chrome-Upload → per-Entscheidungs-Grade) ist intakt und dokumentiert; die
   Upload-Regeln sind im Code verdrahtet (CRLF-Pin, Dedup-Warnungen, Konfig-Sidecar).
2. **Zwei Doktrin-Saetze** sind daraus gemessen und bis heute bindend: *EV-loss zaehlen, nie GTO-Score* und
   *Frequenz-Matching ohne Selektion verliert* (4–5× repliziert).
3. **`POKERB_ONTREE` default-ON** ist die einzige noch aktive Ship-Entscheidung dieses Kanals.
4. **6-max 85,9 % / 7,61** ist der letzte noch zitierte externe Anker — mit dem Vorbehalt, dass der gegradete
   `tag`-Kern seit dem Flat-Fix (2026-09-09) veraendert ist.
5. **Alles aus der Hebel-Leiter Juli** ist Historie: die Analyzer-Sieger wurden am 2026-07-06 aus dem Profil
   entfernt, nachdem der Live-Kanal −58 zeigte.
6. Der **v10-Export (200 Haende, 2026-09-08)** liegt bereit und ungegradet.

---

## LLM- und Brain-Messungen

Dieser Kanal umfasst alles, wo ein Sprachmodell die Entscheidung faellt oder mitfaellt: Claude/GLM/Qwen als
"Brain", das ueber die DSL (`pokerbot/brain/api.py` + `executor.py`) die Engine steuert. **Was er messen kann:**
(a) Trainings-Telemetrie (Loss, Token-Genauigkeit, Reward, `frac_bad` = Anteil ungueltiger/nicht ausfuehrbarer
Programme) — das sagt, ob das Modell die FORM beherrscht; (b) Live-Spielstaerke des LLM-getriebenen Agenten vs
GTO Wizard in AIVAT bb/100 — das sagt, was es tatsaechlich KOSTET; (c) Per-Entscheidung-Grade gegen Solver/
Blueprint/Analyzer — das sagt, WO abgewichen wird; (d) externe LLM-Ranglisten als Referenzfeld.
**Was er NICHT kann:** Form-Metriken (frac_bad, Token-Acc, PokerBench-Match) sagen NICHTS ueber bb/100 — im Projekt
mehrfach belegt (97,5 % Token-Acc bei −43 bb/100). Und ein LLM-Feld (Kaggle) misst relativ zu LLMs, nicht zu GTO.
Alle Live-AIVAT-Zahlen dieses Kanals sind n≤1500 und **tail-dominiert**: der 5 %-getrimmte "Koerper" und der
Rohmittelwert weichen im Extremfall um 60 bb/100 voneinander ab (Abschnitt D).

**★ Zwei Mess-Nahtstellen-Bugs kontaminieren einen Grossteil der Zahlen unten — vorab lesen:**

| Bug | Wirkung | Betrifft | Behoben | Quelle |
|---|---|---|---|---|
| `blinds[-1]`=SB=50 als Big Blind im lokalen GTOW-Runner | ALLE lokalen GTOW-bb/100 **2× inflationiert** | alle lokal berechneten Zahlen VOR 2026-06-19 (u. a. Solver-Suche −74,9; Engine −74,7/−93) | 2026-06-19 | docs/STATE.md:1174 |
| `gtowizard._parse_history` entpackte Live-Blinds [BB,SB] als [SB,BB] | Preflop-Blind-Init INVERTIERT → BB-vs-Open `to_call` 175 statt 125 = **+7 pp geforderte Equity = eingebauter Preflop-Overfold** | **JEDER Live-AIVAT-Lauf** bis 2026-07-05 — also saemtliche Claude-/GLM-Brain-Zahlen dieses Dokuments; Exporte/Analyzer NICHT | 2026-07-05 (Commit 8c827cc) | docs/STATE.md:834-840 |

Konsequenz: die Live-AIVAT-Werte der Brain-Aera sind vermutlich **zu pessimistisch** (Overfold eingebaut), aber
gepaarte A/Bs INNERHALB derselben Aera bleiben gueltig, weil beide Arme denselben Bug tragen.

---

### A — Live-AIVAT vs GTO Wizard, LLM am Steuer

*Was dieser Kanal misst:* realisierte Spielstaerke des Gesamtsystems (LLM-Urteil + Engine-Mathematik) gegen einen
nahe-GTO-Re-Solver, varianzreduziert per AIVAT. *Was er nicht misst:* wo der Fehler sitzt (dafuer Abschnitt B) —
und bei n≤1500 ist der Mittelwert vom Tail dominiert, nicht von der Skill-Differenz.

| Datum | Was gemessen | Instrument/Kanal | Ergebnis (Zahl ± Streuung, n) | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-06-18 | Solver-Suche-Agent (kein LLM, das Geruest fuer den Brain) vs GTOW | `tools/gtow_client --agent-type solver`, AIVAT | **−74,9 bb/100**, n=100 | SCHLECHT; "exakter Solver" = grobe Naeherung (feste, nicht linien-bewusste Ranges, magerer Baum) | docs/STATE.md:1176; docs/LLM_ENGINE_ARCHITECTURE.md:80-82 | **Nein** — vermutlich vom bb=50-Bug 2× inflationiert (im Repo nie ausdruecklich nachkorrigiert); Lehre "Engine-Fidelity vor LLM-Schicht" gilt |
| 2026-06-19 | `ClaudeBrainAgent` (Claude Opus 4.8 treibt die Engine) vs GTOW | GTOW-API, AIVAT, `--agent-type claude` | **−28,55 ± 7,25 bb/100** (RAW −47,42 ± 64,23), n=500; Claude fuhr 99 %, frac_bad 0,011, `solve_node` 453×, ~$8,32 | BESTE HU-Zahl des Projekts zu dem Zeitpunkt; +18,6 vs Konto-Schnitt −47,18 = 2,5σ | docs/STATE.md:1173 | Historisch; Blinds-Bug-kontaminiert; Brain-Spur seit 2026-07-04 sekundaer |
| 2026-06-29 | Claude+Engine, Wiederholung mit groesserem Zeitabstand | GTOW-API, AIVAT, key #2, n=200 | **−41,0 ± 14,06** (RAW +71 ± 91; 534 Entscheidungen, frac_bad 0, solve_node 61 %, $4,14) | Innerhalb ~1σ von −28,55 → wahres Niveau **~−35 bis −45 mit fettem Tail**; die −28,55 war eine guenstige Ziehung | docs/STATE.md:1090 | Historisch; die Korrektur "−28 war Glueck" ist der belastbare Teil |
| 2026-06-19 | GLM-Z1-9B (eigenes Modell, GRPO-ckpt-400) vs GTOW | Pod-Harness `infra/gtow_glm_pod.py` → vLLM → GTOW | **−43,30 ± 7,15 bb/100** (RAW −61,09), n=100; GLM fuhr 111/112 = 99 %, frac_bad 0,009 | Erstes Ende-zu-Ende-Ergebnis eines EIGENEN 9B; ≈ Engine-Niveau, deutlich unter Claude; erwartete Imitations-Decke | docs/STATE.md:1159 | Historisch; Modell als `models/grpo_slim_baseline.tgz` konserviert |
| 2026-06-20 | Preflop-Switch (Blueprint spielt Preflop, GLM Postflop) | GTOW, AIVAT | **−43,30 → −99,39 ± 48** | REGRESSION → REVERTIERT; der Switch stoppte den Preflop-Overfold und legte damit den tieferen POSTFLOP-Spew frei | docs/STATE.md:1160 | Ja als Lehre: einen Leak zu schliessen kann einen groesseren freilegen |
| 2026-06-21 | `made_hand`-Verdrahtung (Engine-Handlese im Prompt) | gepaartes A/B in EINEM Pod, `gtow_glm_pod --ab`, n=500/Arm | OFF **−84,11 ± 16,91** → ON **−43,46 ± 9,49** = **+40,65 bb/100**, ~2,1σ (p≈0,02 einseitig); Varianz HALBIERT; frac_bad 0,006/0,009; ~$2,6 | **Der einzige robuste Gewinn der ganzen Brain-Spur.** Mechanismus: entfernt die "Misread-nach-oben"-Spews | docs/STATE.md:1144-1148 | Ja als Prinzip (Wahrnehmungs-Fixes wirken, Strategie-Hinweise nicht) |
| 2026-06-21 | `to_call`-Bugfix (Preflop-Input des Brains) | gepaartes A/B, n=500/Arm, made_hand in BEIDEN Armen ON | OFF (Bug) **−40,40 ± 12,83** → ON (Fix) **−28,36 ± 10,11** = +12 | **NUR SUGGESTIV** — gepaartes Δ ≈ 0,7σ, Arme ueberlappen; Korrektheitsfix unabhaengig davon richtig | docs/STATE.md:1140; docs/CLAUDE_VS_GTOW_STUDY.md:167-170 | **Nein als bb-Gewinn** — durch die Wiederholung unten widerlegt |
| 2026-06-21 | Serve-Hinweis `solver_freq` (Advisor-Bet-Frequenz im Prompt) | gepaartes A/B `--ab-hints`, n=500/Arm | ON **−49,21 ± 29,00** vs OFF **−49,52 ± 11,71** → Δ ≈ 0 | **NEUTRAL → revertiert** (Flag default OFF). Der OOD-Serve-Hinweis-Hebel ist erschoepft | docs/STATE.md:1118 | Ja |
| 2026-06-21 | Wiederholungsmessung der EXAKT gleichen Basiskonfiguration | GTOW, AIVAT, n=500 | **−49,52** gegen frueher **−28,36** derselben Konfiguration (Δ 21 ≈ 1,35σ) → kombiniert **≈ −37 ± 8** | **Die "−28,36" war eine GLUECKS-Ziehung.** "Kleine Stichproben luegen" im Reinformat | docs/STATE.md:1119 | Ja — das ist die wichtigste Mess-Lehre dieses Kanals |
| 2026-06-21 | Pinning der Basis mit grossem n | GTOW, AIVAT, n=1500 | RAW **−68,20 ± 16,82**; getrimmt (10 schlechteste+beste raus) **−39,8**; ohne 10 schlechteste **−33** | Fett-Tail-Artefakt: ~die Haelfte der −68 stammt aus 10 katastrophalen Haenden (schlimmste −207 bb) | docs/STATE.md:1121 | Ja |
| 2026-06-21 | Bestaetigungslauf der Produktkonfiguration (`grpo_slim`+made-hand+to_call) | GTOW, AIVAT, n=500, ~$1,5 | RAW **−82,2 ± 23,9**; 5 %-getrimmt **−19,3**; 14/15 schlimmste Haende = Cooler; frac_bad 0,003 | Koerper stabil, RAW = Tail-Glueck; **kein Regress** | docs/STATE.md:1111 | Ja |
| 2026-06-21 | Re-SFT → GRPO auf made-hand-NATIVEM Gold (der RL-Lift-Versuch) | GTOW, AIVAT, n=500 je Modell, frac_bad ~0,005 | alte Basis **−28,36 ± 10,11** · NEUES GRPO **−90,18 ± 23,63** · aelteres SFT **−71,64 ± 16,13** | **REGRESSION (~2,3σ)** → nicht geshippt. Isolation SFT-vs-GRPO **unmoeglich**: die Kampagne zieht nur das GRPO, das heutige SFT ging beim Pod-Selbstkill verloren | docs/STATE.md:1126-1132; NOTES.md:100-105 | Ja als negatives Ergebnis + operative Lehre (SFT MITZIEHEN) |
| 2026-06-21 | Ursache der −90-Regression | `research/gtow_xray.py` auf `gtow_hands_1782053161` | River **−211** (Beitrag −74 von −90), Turn −130, **Preflop −3,3 = in Ordnung** | Postflop-/River-SPEW; konsistent mit RL, das gegen die schwache Self-Play-Liga Aggression lernt, die gegen GTOW verliert | docs/STATE.md:1133 | Ja |

**Das Sammelurteil dieses Kanals (2026-06-21, ausdruecklich als ehrliche Umdeutung protokolliert):** das reale
Niveau des GLM-Brains ist **~−55 RAW im Schnitt** (in einer Sitzung −82), NICHT die −17 des getrimmten Koerpers —
"den Tail spielt man mit". Billige Serve-Hebel gemessen und erschoepft: made-hand **+40 (einziger robuster
Gewinn)**, to_call (im Rauschen), solver_freq (neutral), Retraining (Regression), Anti-Spew-Gate (widerlegt).
Quelle: docs/STATE.md:1114.

---

### B — Per-Entscheidung-Grade des Brains (Solver-Orakel / GTOW-Analyzer)

*Was dieser Kanal misst:* WO und WIE OFT das LLM von GTO abweicht — rauschfrei, weil deterministisch gegen ein
Orakel gegradet. *Was er nicht misst:* was die Abweichung an bb kostet (Gewichtung fehlt) und Groessen ausserhalb
des Referenzbaums (off-tree-Sizings bleiben ungegradet → Survivorship).

| Datum | Was gemessen | Instrument/Kanal | Ergebnis (Zahl ± Streuung, n) | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-06-21 | Alle 264 Entscheidungen, die Claude Code selbst gegen GTOW traf | `research/study_grade.py`: Preflop→Near-Nash-Blueprint, Postflop→TexasSolver `api.solve_node` (98,8 % Abdeckung, 160/162), Rest Equity-Mathematik | **252/262 gegradete = 96,2 % im GTO-Support**; Preflop 95 % rein-GTO; Rekonstruktion 264/264 | Die ENTSCHEIDUNGEN waren stark; kein grosser Entscheidungs-Leak | docs/CLAUDE_VS_GTOW_STUDY.md:12-18, :75 | Ja (deterministisch, kanal-unabhaengig) |
| 2026-06-21 | Wo Claude abweicht — nach Strasse | dieselbe Gradierung, sumDev = summierte Abweichung | Flop n=69 mittleres P(gto) **0,48** / sumDev 35,0 · Turn n=51 **0,45** / 28,1 · River n=42 0,70 / 12,6 · Preflop n=102 0,89 / 10,8 | Leak = Flop+Turn | docs/CLAUDE_VS_GTOW_STUDY.md:80-85 | Ja |
| 2026-06-21 | Wo Claude abweicht — nach Aktion | dito | `check` mittleres P(gto) **0,41**, sumDev **52,3** (mit Abstand groesste Abweichung, 6 out-of-support) vs raise 0,89 / fold 0,84 / call 0,79 / bet 0,68 | **Der eine echte Leak: systematisches Ueber-Checken / Unter-Betten postflop** (Semi-Bluffs von Draws/schwachen Haenden) | docs/CLAUDE_VS_GTOW_STUDY.md:87-90 | Ja; Magnitude ehrlich als "vom mageren Solver-Baum verstaerkt" markiert |
| 2026-06-21 | Unabhaengige Zweitmeinung auf den 33 haertesten Spots | `research/study_review.py`, OpenAI gpt-5.x, Kosten $0,07 | stimmt der Aktion in **27/33 = 82 %** zu; jede Abweichung ≤ 1,2 bb bepreist; **Begruendung nur 16/33 = 48 % stichhaltig** (11 Spots: Aktion richtig, Begruendung unsauber, Hauptursache `wrong_range_read` ×8) | Zwei unabhaengige Methoden konvergieren auf denselben Flop/Turn-Leak; ★ die ENTSCHEIDUNG ist staerker als die VERBALISIERUNG | docs/CLAUDE_VS_GTOW_STUDY.md:130-136 | Ja |
| 2026-06-21 | AIVAT-Korroboration derselben 100 Haende | `research/gtow_xray.py` | **−38,41 ± 22,48** AIVAT (RAW +16,93); 90 % des Verlusts auf River-End-Haenden (Mittel −93, n=37); "starke" Made-Haende −606 (n=8); Pots 30–100 bb −264 (n=3) | Der Verlust ist **Varianz/Cooler, kein Leak** — der deterministische Grade wertet genau diese Haende als GTO-korrekt; n=100 viel zu klein | docs/CLAUDE_VS_GTOW_STUDY.md:111-124 | Ja; **das ist der Beleg dafuer, warum bei n=100 die Live-AIVAT allein nichts entscheidet** |
| 2026-06-21 | Deckt unser Orakel GTOWs echtes Spiel? | `research/gtow_oracle_check.py` ueber 7.565 geloggte Haende | Preflop-Blueprint: **93,8 % von GTOWs echten Aktionen im Support** (n=6.203) · Postflop-Solver: **90,1 % im Support, 64 % modal, mittlere Wahrscheinlichkeit 0,62** (n=172, 96 % Solve-Abdeckung) · Turn schwaechster Punkt (86 % Support, modal nur 47 % vs Flop 68 %/River 80 %) | Das Orakel ist NICHT grob kaputt → ein spekulativer Postflop-Solver-Umbau ist **nicht datenbelegt** (dieser Test hat den Umweg gespart). CAVEAT: grob (Aktions-FAMILIE, nicht Sizing/Frequenz, n=172 ±~5 %) | docs/STATE.md:1141 | Ja |
| 2026-06-29 | Erste Per-Entscheidung-Gradierung von BRAIN+ENGINE durch den GTOW-Analyzer | `research/claude_export.py` → GTOW-Analyzer, 50 Haende / 86 gegradete Zuege | **GTO-Score 69,9 %, EV-Loss 6,1 bb/100, Freq-Diff 48 %** (Preflop 85 % perfekt) — gegen Engine-allein ~50–63 % / 78–120 EV-Loss / 94–97 % Freq-Diff | Das Brain spielt DRAMATISCH naeher an GTO als die nackte Engine — und zwar OHNE die `bot.py`-Gewinne (es umgeht sie) | docs/STATE.md:1089 | Ja mit Vorbehalt: **kleine Stichprobe** (86 Zuege) → Kopfzahl belastbar, per-Strasse (Flop n=20 45 %, Turn n=15 60 %, River n=11 54 %) verrauscht |
| 2026-06-29 | Bet-Size-Verhalten des Brains | Skript `_betsize_check` im Scratchpad, ueber den n=200-Lauf | Claude nur **15 % on-tree** (bettet kontinuierlich ~0,60×Pot) vs Engine **100 % on-tree** | Erklaert die Survivorship im 69,9-%-Grade: die 85 % off-tree-Groessen wurden gar nicht gegradet | docs/STATE.md:1090 | Ja |
| 2026-06-29 | `POKERB_BRAIN_ONTREE` (Snap der Brain-Bets auf GTOWs Baum), Live-A/B | GTOW, AIVAT, n=300/Arm, key #2 | on-tree mechanisch **15 % → 100 %** (deterministisch bestaetigt); AIVAT ON **−39,92 ± 19,32** vs OFF **−55,92 ± 28,14** = +16,0 — aber Δ-SE ≈ 34 | **Richtungsgut, statistisch NICHT signifikant** → bleibt default-OFF | docs/STATE.md:1091 | Ja |
| 2026-06-29 | derselbe Snap, per-Entscheidung | GTOW-Analyzer, 60 Haende / 133 Zuege | Snap-ON **60,4 % / EV-Loss 47,5 / Freq-Diff 51 %** vs Snap-OFF 69,9 / 6,1 (86 Zuege) | **KONFUNDIERT — Seed-Fehler des Autors** (ontree Seed 31, brain Seed 7 = andere Haende, nicht gepaart) + beidseitige Survivorship → Richtung unklar, Flag bleibt OFF | docs/STATE.md:1092 | Ja als negatives/ungueltiges Ergebnis; sauberer Test (gleicher Seed, beide hochgeladen) wurde nie gefahren |

---

### C — Trainings- und Formmetriken (SFT / GRPO, Qwen und GLM)

*Was dieser Kanal misst:* ob das Modell die Ausgabeform beherrscht (Token-Genauigkeit, `frac_bad`, Reward-Verlauf).
*Was er ausdruecklich NICHT misst:* Spielstaerke. Im Projekt mehrfach belegt: 97,5 % Token-Genauigkeit stehen neben
−43 bb/100; 71,7 % PokerBench-Trefferquote stehen neben einer harten Imitations-Decke.

| Datum | Was gemessen | Instrument/Kanal | Ergebnis (Zahl ± Streuung, n) | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-06-14 | Qwen3-8B LoRA auf PokerBench (RunPod B200) | `extraction/qwen_sft.py`, Trainings-Telemetrie | bei Schritt ~90/987 bereits **96 % Token-Genauigkeit**; gespeichert bei Schritt 500 mit **97 %** | Konvergiert schnell; volle 987 Schritte unnoetig | docs/STATE.md:1805-1808, :1887 | Historisch (Modell `models/qwen_poker_ckpt500`) |
| 2026-06-14 | Entscheidungs-Trefferquote der LoRA auf gehaltenem PokerBench | `extraction/qwen_eval.py` | **Basis 18,3 % → LoRA 71,7 % (+53 pp)** | Fine-Tuning wirkt eindeutig auf die FORM/Aktionswahl | docs/STATE.md:1887-1889 | Ja als Zahl; als Spielstaerke-Indikator **entwertet** (siehe naechste Zeile) |
| 2026-06-15 | Preflop-Exakttabelle destilliert aus PokerBench vs beide LoRAs | Holdout-Vergleich | Tabelle **88,6 %** gehalten, **schlaegt beide LoRAs** | Eine Lookup-Tabelle uebertrifft das fine-getunte 8B auf derselben Aufgabe → PokerBench-Genauigkeit ist kein Skill-Mass | docs/STATE.md:1740 | Ja |
| 2026-06-17 | Lokaler SFT-Beweis: emittiert das Modell gueltige Reasoning-Loop-DSL? | Qwen3-1.7B QLoRA lokal | **frac_bad 0,97 → 0,00**, grounded_rate 1,00, 30/30 OK | Der Fix war die DATENFORM: Entscheidungs-Completions muessen die Aktion aus der Engine-Rechnung ABLEITEN; die alte "dekorative" Form (rechnen, dann `decide()` hartkodieren) erzeugte frac_bad 0,97 | docs/STATE.md:1274-1279 | **Ja — eine der stabilsten Lehren des Projekts** |
| 2026-06-17 | GRPO-Schleife auf dem gefixten Modell | lokal, 10 Schritte, $0 | `reward_std > 0` (Reward sprang 17,4 / −13,8 / 28,0 / −24,5 …), frac_bad ≈ 0, grounded ≈ 1, Completions stabil ~120 Token; Holdout (rock/whale/shark, greedy) frac_bad **0,13** / grounded 1,00 | Integration + Sanity bewiesen — **ausdruecklich KEINE EV-Lift-Behauptung** (10 Schritte) | docs/STATE.md:1280 | Ja |
| 2026-06-17 | Gemischte Strategien (`decide_mix`) im SFT | lokal, Holdout | **frac_bad 0,07**, grounded 1,00, gueltige Mixes | Form beherrscht | docs/STATE.md:1300 | Ja |
| 2026-06-17 | Faehigkeits-Decke des 1.7B (A/B-Leiter, alles $0) | lokal, gemessene Leiter | kompakte Ranges: Read-Zweig-Emission 0 → 9/30; +Datenvolumen (1500→5000 Spots): ok 8 → **25/31**, frac_bad ~60 % → **19 %**, **aber Read-Zweig 9 → 0/31**; Trainings-Loss 0,004, Token-Acc **0,999** (bereits ueberangepasst) | **Definitive 1.7B-Fidelity-Decke**: haelt die API-Namen ODER den feinen Bedingungszweig, nicht beides. Hypothesen sauber konkurriert: Epochen ausgeschlossen, Datenvolumen hilft der Generalisierung, nicht dem seltenen Zweig | docs/STATE.md:1307-1314 | Ja |
| 2026-06-17 | Externer Erstbezug: 1.7B-Brain spielt Slumbot | `pokerbot/benchmark/slumbot_llm.py`, n=100 Haende / 120 Entscheidungen | **−72,0 bb/100** (±~7; Lesungen konvergierten −85 → −72), **frac_bad 0,03** | Verlierende, aber VERNUENFTIGE Basis (Muellbot ≈ −200+; altes fcpa-Policy-Netz −212). "Die Zahl, die zu schlagen ist" | docs/STATE.md:1281-1287 | Historisch; die Referenzwerte −72/−212 werden bis heute als Imitations-Decke zitiert (docs/QWEN_6MAX_PLAN.md:8-9) |
| 2026-06-17 | Regression durch Datenvolumen beim HU-Transfer | Slumbot-Wiederholung, lokal | **frac_bad 0,48**, ~29 s/Hand; Modell faellt auf literale Ranges zurueck, inkl. ungueltigem `'AS'` | NEGATIV: 6-max-Self-Play-Ueberanpassung zerstoerte den HU-Transfer; der saubere −72-Checkpoint wurde dabei ueberschrieben | docs/STATE.md:1331-1333 | Ja als Warnung (Checkpoints schuetzen) |
| 2026-06-17 | Parallelisierung der GRPO-Belohnung | `qwen_grpo`, `REWARD_WORKERS`, 24 vCPU | **~5× bei 8 Workern, byte-identisch zur seriellen Version** | Bestaetigt + deckte zwei echte Reward-Bugs auf (CRN gebrochen: unseeded RNG; `PYTHONHASHSEED` → Karten-Set-Iteration prozessabhaengig) | docs/STATE.md:1315-1321 | Ja |
| 2026-06-18 | Erster 8B-GRPO-Lauf: lernt er? | Pod, 57 Schritte, Metrik-Log | Reward **FLAT ~−17,6**, kein Trend; Rohartefakt: Schritt 1 reward −17,69 / frac_bad 0,469, Serie −4,90 … −18,79 ueber 14 geloggte Schritte (Mittel ≈ −13,7), frac_bad 0,28–0,63 | **GATE 2 (RL > SFT-Init) NICHT BESTANDEN.** Ursache: `R_BAD=−30` erschlug das EV-Signal (Dr.GRPO-Vorteil = ±33-Luecke gueltig/ungueltig statt ±5-bb-EV-Spanne) → das Modell lernte "sei gueltig", nicht "spiel gut" | docs/STATE.md:1182-1185; models/grpo_metrics.jsonl:1 (Rohdaten, 57 Zeilen) | Ja. *Anmerkung zur Quelle:* das Rohlog zeigt Oszillation ohne Trend, nicht buchstaeblich eine Konstante −17,6 — die Aussage "flach" traegt, die exakte Zahl ist der Startwert |
| 2026-06-18 | Der Reward-Fix `R_BAD −30 → −3` | lokales A/B, 1.7B, gleicher Seed | Kontrolle R_BAD=−30 → Reward **−25,6** (angeheftet, folgt frac_bad); Fix R_BAD=−3 → Reward **−2,5** bei HOEHEREM frac_bad (0,69) | GATE BESTANDEN: Reward jetzt EV-zentriert und von frac_bad ENTKOPPELT. "frac_bad ~0,5 war gesampelte Exploration, nicht der Hebel — der Reward war es" | docs/STATE.md:1186-1188 | Ja |
| 2026-06-18 | PokerBench-"Degenerations"-Alarm | Prosa-Proxy auf gehaltenem PokerBench | 8B bei **15 %** vs Basis 43 % — **reines Methodenartefakt**: Prosa ≠ Deployment-`format_spot`, und der Proxy liest das ERSTE `decide()` eines verzweigenden Programms statt der AUSGEFUEHRTEN Aktion. Ausgefuehrter Aktionsmix ueber 80 echte 6-max-Spots: fold 40 % / raise 36 % / check 21 % / call 3 %, **97 % gueltig** | Modell NICHT degeneriert; der Alarm war ein Messfehler | docs/STATE.md:1204-1208 | Ja — Musterbeispiel fuer "erst das Instrument pruefen" |
| 2026-06-18 | `enable_thinking` als frac_bad-Ursache | 70-min-Pod-Lauf | **frac_bad 0,93, clipped_ratio 0,72** | Qwen3-Thinking war nirgends abgeschaltet → langes `<think>`-Geschwafel fuellt das Token-Budget vor jedem `decide()` → abgeschnitten → frac_bad. Fix: `enable_thinking=False` in JEDEM Generationspfad | docs/STATE.md:1219-1224 | Ja |
| 2026-06-19 | GLM-Z1-9B SFT-Warmstart | Pod H100 SXM, 33k DSL-Gold-Zeilen | **Loss ≈ 0,087, mean_token_accuracy 97,5 %, grad_norm ≈ 0,13**; vLLM-Generationsprobe 7,6 s/Schritt | GATE 0 bestanden, reproduzierbar. **Aber:** dasselbe Modell spielt −43,30 bb/100 → Token-Genauigkeit ≠ Spielstaerke | docs/STATE.md:1158 | Ja |
| 2026-06-19 | `frac_bad`-Fehlmessung durch SIGALRM | `executor.run_program` | gemessen **frac_bad 1,0 → nach Fix 0,009** | Der Timeout via SIGALRM funktioniert nur im MAIN-Thread; der Client entscheidet in einem Worker (`asyncio.to_thread`) → JEDES gueltige Programm zaehlte als "bad". Fix: `_alarm_available()` verlangt zusaetzlich `threading.main_thread()` | docs/STATE.md:1159 | Ja — der Bug, der das Modell zwei Runden lang als kaputt erscheinen liess |
| 2026-06-20 | Re-SFT (Blueprint-Knoten direkt enumeriert) | Pod, MAXN=10000, 625 Schritte / ~60 min | Loss 1,94 → 0,10, **Token-Acc 0,70 → 0,97**, Adapter auf dem Pod gespeichert; Datensatz 12.168 Zeilen, 6 Knoten gleichverteilt (je 2.028), 0 grammatikungueltig | Trainiert einwandfrei — **abgebrochen von einem `UnicodeEncodeError` beim Ausdrucken des Pod-Stdout auf der cp1252-Windows-Konsole**; 3 Laeufe so verloren, ~$10–11 | docs/STATE.md:1163 | Ja als operative Lehre (`PYTHONUTF8=1` + `sys.stdout.reconfigure`) |
| 2026-06-21 | Re-SFT auf made-hand-nativem Gold | Pod-Kampagne | SFT **98,8 % Token-Genauigkeit**, GRPO 400 Schritte, Self-Play-Reward −4 → +2, 15.126 Zeilen | Alle Trainings-Metriken gruen — **und trotzdem −90,18 bb/100 gegen GTOW** (Abschnitt A). Der schaerfste Beleg, dass dieser Kanal Spielstaerke NICHT misst | docs/STATE.md:1125-1132 | Ja |

**Kostenseite (gemessen, gehoert zum Kanal):** ~$11 fuer die GLM-Bring-up-Smokes (docs/STATE.md:1157), ~$2,6 fuer
das made-hand-A/B (:1145), ~$1,5 fuer einen 70-min-Pod-Lauf (:1212), ~$48 fuer die autonome Verdrahtungsrunde
(:1122), ~$28 fuer die Re-SFT-Runde (:1135) — und **~$65 einmalig verbrannt**, weil der PC in einem unbeaufsichtigten
Lauf einschlief und der pod-seitige `nohup`-Watchdog den SSH-Abbau nicht ueberlebte (:1213-1216).

---

### D — Offline-Gegenproben und Tail-Analysen ($0, ueber echte Logs)

*Was dieser Kanal misst:* ob eine geplante Aenderung ueber den bereits gespielten Haenden ueberhaupt gefeuert
haette und was sie gebracht haette — Kosten null, kein neuer Lauf. *Was er nicht kann:* Fold-Equity
kontrafaktisch bewerten (eine Bet→Check-Aenderung ist offline nicht sauber nachrechenbar).

| Datum | Was gemessen | Instrument/Kanal | Ergebnis (Zahl ± Streuung, n) | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-06-21 | Wo liegt der Leak wirklich? Lokale Sondierung des trainierten GLM | `research/glm_local_probe.py`, GLM-9B 4-bit auf der 3080 Ti, 13 Spektrum-Spots | Call-Disziplin **gut**: foldet Equity-loses Air, verteidigt Draws/Marginale ~zu Pot-Odds, checkt Air zurueck — **11/11 schwach+mittel korrekt, frac_bad 0** | Der `postflop_corset` ist ein NO-OP (der Over-Call-Leak, den er begrenzt, existiert nicht). Echter Leak: das GLM **liest seine eigene Made Hand in natuerlicher Sprache falsch** — Full House → "two pair", geflopte Strasse → "air" (Wert verloren) UND schwaches Paar → "ich habe einen Flush" (Spew-Bet) | docs/STATE.md:1150-1152 | Ja — fuehrte direkt zum +40,65-Hebel |
| 2026-06-21 | Gepaartes lokales A/B der made-hand-Injektion | `glm_local_probe.py`, OFF vs ON, gleiche Spots | 7 Spots, Entscheidung aenderte sich bei 4 = **3 klare Fixes** (Boat: check → Value-Bet; Two Pair: falsch-tighter Fold → Call; halluzinierter Flush: Spew-Bet → Check) + **3 Kontrollen erhalten**, 1 grenzwertig lockerer Thin Call; **frac_bad 0** | Lokal gegruendet, danach at-scale bestaetigt (+40,65) | docs/STATE.md:1153 | Ja |
| 2026-06-21 | Anti-Spew-CALL-Gate (der geplante "letzte grosse Hebel") | `research/gtow_tail.py --gate`, Kontrafaktual ueber das echte 1500-Hand-Log | **ORAKEL** (Equity gegen Villains TATSAECHLICHE Hand = perfekte Information): feuert **2/1500, +16,7 bb/100**. **LIVE** (Equity gegen eine committende RANGE = was zur Laufzeit berechenbar ist): feuert **0/1500, +0,0**. Aggressive Live-Einstellungen: Kosten ≈ Ersparnis, netto 0 bis −7,5. Nur 27 grosse Calls existieren in 1500 Haenden | **WIDERLEGT — nicht gebaut, nicht geshippt.** Ein Live-Anti-Spew-Gate auf der Call-Seite kann nicht helfen | docs/STATE.md:1107 | Ja |
| 2026-06-21 | Woher der fette Tail wirklich kommt | `gtow_tail.py`, Handinspektion | Die katastrophalen Haende sind `hero_bet=True`-Mehrstrassen-Aggression, die auf einen Raise foldet oder gecallt verliert (die −208-bb-Hand: `HERO:b1000 … HERO:b2710 gtow:b8134 HERO:f`) | Der Tail ist hero-EIGENE −EV-Aggression, kein Call-Off → **RL-Aufgabe, nicht Serve-Gate** | docs/STATE.md:1108 | Ja |
| 2026-06-21 | Commitment-Cap-Kontrafaktual | `gtow_tail.py --cap` | Orakel "gewinnt" +28 bb/100, indem es 7 grosse Commitments foldet — Inspektion: **Trips ×2, Two Pair ×3, Paar ×2** (Handstaerke 0,48–0,76), geschlagen nur von Villains SPEZIFISCHER besserer Hand (Equity gegen die tatsaechliche Hand ~0,00–0,12; **0 gewonnene Bluffs**) | **HINDSIGHT-ILLUSION**, nicht live realisierbar — gegen eine RANGE sind diese Haende vorn | docs/STATE.md:1109 | Ja |
| 2026-06-21 | Ist die Value-/Sizing-Grundlage kaputt? | `gtow_tail.py --value`, ueber `to_call==0`-Postflop-Spots | Bet-Rate deckt sich mit der Advisor-GTO-Rate: strong 41 % vs 38 %, nuts 57 % vs 41 %; Asymmetrie nur beim UNTER-Bluffen (weak 5 % vs 32 %); Sizing flach ~40 % Pot auf allen Strassen (Flop 40 / Turn 40 / River 38) | Kein grosser Value-/Sizing-Bug; der −17-Koerper ist solides Spiel an der Decke eines 9B | docs/STATE.md:1110 | Ja |
| 2026-06-21 | Der getrimmte "Koerper" quer ueber alle Sitzungen | `gtow_tail.py`, 5 %-Trim | "−28,36 gluecklich" n=500: RAW −28,5 / trim **−17,3** · "−68-Pin" n=1500: −68,2 / **−16,8** · Wiederholung n=500: −49,5 / **−15,4** · "−90-Regression" n=500: −90,2 / **−18,1** · to_call-OFF n=500: −40,4 / **−19,2** | Der nicht-katastrophale Skill liegt bei **≈ −17 bb/100**, die RAW-Schwankung −28↔−90 ist fast vollstaendig Tail-Glueck | docs/STATE.md:1098-1106 | Ja als Diagnose; **ausdruecklich NICHT als erzielbares Ergebnis** — der Nutzer widersprach zu Recht: "den Tail spielt man mit" (:1112) |
| 2026-06-21 | Re-Test des Gates mit KORREKTER enger Value-Range | `gtow_tail.py` (Korrektur eines eigenen Fehlers: vorher `range_top 0.5` = viel zu weit) | ORAKEL holt **+12 bis +80 bb/100 ueber alle 4 Produkt-Sitzungen (Schnitt ~+47)**; das LIVE-Gate mit enger Range aber **+20,4 / −8,7 / +12,2 / −16,5 ≈ 0 im Schnitt** | Der Over-Paying-Off-Leak ist REAL, aber mit einer groben Range live nicht greifbar → braeuchte RL gegen einen starken Gegner | docs/STATE.md:1112 | Ja |
| 2026-06-21 | Der geplante "billige RL-Fix" (ausgewogene Liga) | 3 gegruendete Rollout-Tests, $0 | Call-EV gegen maniac vs tag-Liga **+0,0**; maniac- vs tag-erzeugte Facing-Bet-Spots **+0,3 bb**; Bluff-EV gegen Over-Folder-nit vs tag **+0,0**. Ursache: die 5 sixmax-Profile unterscheiden sich vor allem PREFLOP, postflop teilen alle EINE `_decide`-Engine → **68 % identische Entscheidungen** | **WIDERLEGT vor jedem Pod-Kauf** ($15–20 gespart). Das Umbauen der RL-Liga kann den Postflop-Reward nicht aendern; die Wand ist die GEGNER-DECKE | docs/STATE.md:1113 | Ja |
| 2026-06-29 | RL-Pivot insgesamt, erneut geprueft | Planungs-Workflow mit den eigenen $0-Beweisen | Erreichbare RL-Decke ≈ Engine-Niveau −45; RL war schon einmal auf −90 regrediert | **REFUTIERT** → der Nutzer waehlte den Engine-Pfad; kein Pod-Spend | docs/STATE.md:1087 | **Ja — das ist die bis heute gueltige Entscheidung** |

---

### E — Externe LLM-Ranglisten (Referenzfeld)

*Was dieser Kanal misst:* wie andere Frontier-Modelle in HU-Poker abschneiden — als Massstab, nicht als Gate.
*Was er nicht kann:* das Kaggle-Board misst RELATIV zum LLM-Feld (deshalb positive Zahlen), das GTOW-Board gegen
einen Re-Solver (deshalb alle negativ). Die beiden sind **nicht ineinander umrechenbar** (unten gemessen).

| Datum | Was gemessen | Instrument/Kanal | Ergebnis (Zahl ± Streuung, n) | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-06-19 | Frontier-LLMs auf dem GTOW-Leaderboard | GTOW-Leaderboard (read-only API) | **GPT-5.2 −8,26 · GPT-5.5 −9,23** bb/100 AIVAT | Ein LLM-getriebener Agent spielt HUNL ~5× besser als die damalige Engine (−47) → die Imitations-Decke gilt fuer TRAINIEREN eines kleinen Modells auf unseren Daten, **nicht** fuer PROMPTEN eines Frontier-Modells | docs/STATE.md:1171 | Zahlen historisch (Board hat sich weitergedreht); die Unterscheidung gilt |
| 2026-09-10 | Kaggle Game Arena „Heads Up Poker", Leaderboard v1 | Kaggle-Benchmark-API, Mean BB/100, All-play-all im LLM-Feld | Rang 1 **GPT-5.6 Sol +34,9 ± 5,1** · 2 GPT-5.5 +32,5 ± 6,0 · 3 Claude Fable 5.1 +29,7 ± 6,0 · 4 **Claude Opus 5 +15,8 ± 5,9** · 5 GPT-5.6 Terra +11,6 ± 5,5 · 15 GPT-5.4 mini −0,4 · 19 Claude Opus 4.8 −3,4 · 23 DeepSeek V3.2 −11,8 · 26 Claude Sonnet 4.6 −17,3 · 29 GPT-5 mini −49,3 | Positive Werte, weil relativ zum Feld gemessen. Kosten der Spitze: 12.000–19.000 Token je Zug, bis 26 ct/Zug | docs/KAGGLE_ARENA.md:14-21 | Ja (abgerufen 2026-09-10) |
| 2026-09-10 | Spielkonfiguration der Kaggle-Umgebung | direkt aus der Umgebung gelesen + `tests/test_kaggle_arena.py` | HUNL, Blinds 1/2, Stacks 200 Einheiten = **100 bb**, Reset je Hand, Dealer rotiert, 100 Haende/Match | ★ **KORREKTUR im selben Dokument:** 100 bb ist NICHT unsere Wettbewerbstiefe — GTOW laeuft auf **200 bb** (`gtowizard.py:98,:281`) und unser Preflop-Blueprint feuert erst ab **140 bb effektiv** (`bot.py:200`) → der Kaggle-Kanal misst einen ANDEREN Bot als der Wettbewerbskanal. Die frueher dort stehende Behauptung "genau unsere Hausgroesse" war falsch | docs/KAGGLE_ARENA.md:32-42 | Ja |
| 2026-09-10 | Eichung Kaggle → GTOW (6 Modelle auf beiden Listen) | Regression GTOW-AIVAT auf Kaggle-BB/100 | alle sechs: **r = 0,37, R² = 0,14, Residual-SD 15,5 bb/100**; ohne Grok 4 (Residuum −34): r = 0,88, R² = 0,77, Residual-SD 3,4, `GTOW ≈ 0,334·Kaggle − 22,7` | **NICHT BENUTZBAR.** Einen Punkt zu streichen, WEIL er widerspricht, ist Kurvenanpassung; zudem unterschiedliche Reasoning-Stufen und Extrapolation ausserhalb der Datenspanne | docs/KAGGLE_ARENA.md:105-119 | Ja |
| 2026-09-10 | GTOW-AIVAT derselben 6 Modelle | benchmark.gtowizard.com | GPT-5.6 Sol −15,4 · GPT-5.5 −9,2 · Grok 4 **−60,0** · GPT-5.4 −17,8 · Claude Opus 4.6 −20,4 · Gemini 3.1 Pro −30,8 | Die Streuung im LLM-Feld ist riesig; "Frontier-LLM" ist keine einheitliche Spielstaerke | docs/KAGGLE_ARENA.md:107-113 | Ja |
| 2026-09-10 | GTOW-Leaderboard-Spitze und unsere eigenen Eintraege | benchmark.gtowizard.com, 83 Eintraege, Rang nach 95-%-Untergrenze | 1 Bitcrumbs −3,1 (SD 0,9, 52.005 Haende) · 2 Trainer (SL) −6,2 · 3 Roman_SL −7,4 · 4 tangtang −12,6 · 5 GPT-5.5 (XHigh) −9,2 (SD 2,8, 5.000 Haende) — **eigene: Rang 31 Quantplay −30,4 (6.587) · Rang 33 Quantplay v8 −31,6 (6.946) · Rang 47 Experimental Poker Bot −51,7 (30.596)** | Die Spitze sind PRIVAT-Agenten, nicht LLMs. Alle eigenen Eintraege stammen aus der v8-Aera; der heutige Champion (~−21) wurde nie gepostet. **Top 5 = Untergrenze besser als ≈ −14,8**, Luecke ≈ 8 bb/100 | docs/KAGGLE_ARENA.md:128-142 | Ja (Stand 2026-09-10) |
| 2026-09-10 | Erster Referenzwert im Kaggle-Kanal: Champion vs nackte Basis | `pokerbot/benchmark/kaggle_arena.py --gegner basis`, 300 gepaarte Decks, 1 Kern, 3.153 s | roher Mittelwert **+55,8 bb/100**, SE **38,0**; 5 %-getrimmt +6,3; Median 0,0; abweichende Decks 32,3 % (97/300), davon positiv 45/97 (Vorzeichen-z −0,71); Bootstrap-CI [−16,7, +134,6]; perm_p 0,076 | **NEUTRAL** (`stats.verdikt`). Ausdruecklich KEIN Bot-Verdikt, nur Kanal-Kalibrierung. Preisliste des Kanals: fuer SE ≈ 4 braeuchte man ~27.000 Decks ≈ 75 h auf einem Kern | docs/KAGGLE_ARENA.md:147-172 | Ja |
| 2026-09-10 | A/A-Nulltest der Kaggle-Bruecke | `kaggle_arena --aa --decks 8` | zunaechst **−37,5 bb/100 statt 0** (RNG-Strom lief ueber Haende weiter, wiederverwendete Agenten liessen die Spiegelhaelften auseinanderlaufen) → nach Fix (frische Instanzen je Haelfte) **exakt 0** (nonzero 0, SE 0) | Zwei Mess-Fallen gefunden und geschlossen (die zweite war dieselbe `hand_id`-je-Haelfte-Falle wie in v10) | docs/KAGGLE_ARENA.md:56-63 | Ja |
| 2026-06-14 | Unsere Engine gegen Frontier-LLM-Gegner | `pokerbot/benchmark/llm_opponent.py`, 40-Hand-Stichproben | ungefaehr ausgeglichen: **Opus 4.8 +30, o3 +17**; das naive **gpt-5.1 +395 war eine Prompt-Schwaeche + Rausch-Fata-Morgana** | Bei n=40 unbrauchbar; verlaessliche Gegnerstaerke braucht AIVAT | docs/STATE.md:1842-1844 | Ja als Warnung; Zahlen wertlos |

---

### F — LLM als Werkzeug (Gegner, Auditor, Konsulent, Recherche)

*Was dieser Kanal misst:* was ein Sprachmodell als INSTRUMENT liefert — Ausbeutungs-Muster gegen unseren Bot,
Code-Befunde, Literatur. *Was er nicht kann:* ein Verdikt sprechen. Jeder LLM-Befund ist eine HYPOTHESE, die erst
durch ein gepaartes Gate zur Evidenz wird — im Projekt mehrfach hart bezahlt.

| Datum | Was gemessen | Instrument/Kanal | Ergebnis (Zahl ± Streuung, n) | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-08-17 | LLM-Adversar gegen AUSLESE v4 | `research/fable_duell.py` (dateibasiert, Replay-deterministisch), 62 Haende | **+115,5 bb fuer den Adversar** (als Anekdote deklariert) mit GEZAEHLTEN Mustern: Button-Open-Fold ~29 %, Limp-Call→Fold-vs-Cbet 5/7, River-Station 4/5 grosse Calls mit Verlierern (~90 bb), Check-Raise ohne Follow-Through 3/3, keine Mischung; `turn_wert`-Bets in Continuation-Linien 3/3 echt = nutzbarer Tell → **gecappte Check-Range = exakt der v8-Purify-Mechanismus** | Kein bb-Verdikt (n=62, Anekdote), aber ein **Mechanismus-Befund** — die Achse ist der ADAPTIVE Gegner, nicht der Spiegel | data/autogym/journal.jsonl:71 (`typ: FABLE-DUELL`) | Ja; hat den spaeteren GTOW-Live-Bruch vorhergesagt (docs/STATE.md:183-184) |
| 2026-08-18 | Nachtest gegen den gehaerteten Stack | `fable_duell.py` vs `r6_button`-Stack, 92 Haende | Ernte **186 → 58 bb/100**; Open-Folds **0/46** (vorher 29 %); 3bet-Angriff aufs Trash-Open netto −21 bb; cooler-bereinigt waere der Bot vorn (eine Nut-Flush-Hand = +200 bb) | **HAERTUNG BEWIESEN** auf der Adversar-Achse — waehrend derselbe Guard im Mirror NEUTRAL war → daraus die bindende Zwei-Achsen-Doktrin (Mirror = Nichtverschlechterungs-Schranke, Adversar = Wirkungs-Beweis) | data/autogym/journal.jsonl:75 (`typ: FABLE-RETEST`); docs/STATE.md:188-190 | Ja |
| 2026-06-14 | Unabhaengiges LLM-Code-Audit des Bots | `extraction/bot_audit.py`, `claude-opus-4-8`, jeder Befund handgeprueft | Audit nannte den Code "mostly sound" und fand denselben Spew live in `adaptive.py` (Ursache: keine Range-Verengung gegen Aggression). Nach dem Fix: 200-bb-Stack-offs eliminiert, schlimmste Hand **−20.000 → ~−7.762** | LLM-Audit als Hypothesen-Generator brauchbar — die bb-Zahlen stammen aus dem Engine-Kanal, nicht vom LLM | docs/STATE.md:1860-1869 | Ja |
| 2026-07-05 | Voll-Audit des Bots mit einer Agenten-Armee | 90 Agenten / 9 Dimensionen / 3× adversarische Verifikation, Ledger `data/audit/audit_result.json` | **23 bestaetigte Befunde, 4 widerlegt**; die zwei HIGH-Befunde waren Mess-Nahtstellen (invertierte Blinds; 13 fehlende Flags im Fingerprint) | Der wertvollste Ertrag des Audits war nicht Strategie, sondern **kaputte Messung** | docs/STATE.md:834-842 | Ja |
| 2026-07-05 | Zuverlaessigkeit der LLM-Literatursuche | Perplexity-API + eigener Existenz-Verifikations-Layer | **27/36 Papers bestaetigt**; systematisch **vertauschte Metadaten** (falsche Autoren bei richtigen Titeln, arXiv-IDs am falschen Paper, DeepStacks DOI am Libratus-Eintrag, "Safe and Nested Subgame Solving" mit vier falschen Autoren) | **Kein Paper aus einem LLM-Sweep darf ohne Verifikations-Layer zitiert werden** — als stehende Regel uebernommen | docs/RESEARCH_SWEEP_2026-07-05.md:7-13, :57 | Ja |
| 2026-06-14 | LLM-generierte Exploit-Direktiven | `extraction/exploit_playbook.py` (Claude) | 11.520 Direktiven (Haiku) + 240 hochwertige (Opus) | Reiner Artefakt-Zaehler; die Wirkung wurde separat im Engine-Kanal gemessen (Regeln gegen station +308, gegen maniac +262, kein Leak gegen Starke) | docs/STATE.md:1817-1818, :1760-1762 | Ja |
| 2026-09-07 | Frontier-Konsult zur Top-5-Strategie | `gpt-6-astra`, Responses-API, reasoning=high | Teil B 5.178 Reasoning-Token / 469 s · Teil D 5.696 / 481 s · Teil E (v10-Kritik) 9.751 / 662 s · Teil F 3.624 · Teil G 4.142 | Kein Messwert, sondern Beratung — im Dokument ausdruecklich mit eigener Bewertung ("was ich uebernehme, was ich ablehne") versehen | docs/TOP5_KONSULT_GPT6_2026-09-07.md:1-6, :157, :1233, :2379, :4205 | Ja als Quelle der v10.1-Hybrid-Doktrin |

---

### G — Gebaut, aber NIE gemessen (offene Posten dieses Kanals)

| Datum | Was | Stand | Quelle | Gilt heute? |
|---|---|---|---|---|
| 2026-06-29 | **Understanding-Layer** `pokerbot/brain/understanding.py::strategic_read` — SPR/Position/Pot-Odds/MDF + Textur + Made-Hand-Lese + gemessene GTO-Heuristiken in EINEM Engine-berechneten Frame, Flag `POKERB_UNDERSTANDING`, default OFF | **GEBAUT + lokal verifiziert (OFF byte-identisch zur Basis, Zahlen exakt: req-Equity 33 % = 10/(20+10), MDF 50 %, SPR 4,0), aber EV-UNGEMESSEN.** Die vorgesehene Messung (deterministischer GTOW-Per-Entscheidung-A/B, dann AIVAT) wurde nie gefahren | docs/STATE.md:1078; docs/ROADMAP.md:26-35, :80 | Ja — offener Posten; der Brain-Pfad ist seit 2026-07-04 sekundaer, also unbearbeitet |
| 2026-06-29 | **Architektur-Befund:** der LLM-Brain entscheidet ueber `executor → api.legalize`, NICHT ueber `bot.py::PokerBot` | Damit erreichen ALLE Engine-Gewinne (ONTREE-Snap, River-Value-Floor, linien-bewusster River-Advisor) die spielbaren Engine-Bots, **nicht** das Brain. Das Brain wurde nie per-Entscheidung durch den Analyzer gegradet ausser ueber `claude_export.py` | docs/STATE.md:1088 | Ja — erklaert, warum "das LLM an die Engine anpassen" als LOW-VALUE eingestuft wurde |
| 2026-06-19 | **Die eigentliche RL-These: hebt RL ueber den SFT-Warmstart?** Der saubere Test waere SFT vs GRPO auf GTOW (`GLM_USE_SFT=1`, ~$2) | Nie sauber gefahren; die eine Gelegenheit ging verloren, weil die Kampagne nur das GRPO zieht (Abschnitt A). Der spaetere Re-SFT→GRPO-Versuch regredierte auf −90 → die These gilt fuer dieses Setup als **negativ beantwortet**, aber nicht sauber isoliert | docs/STATE.md:1165, :1132; NOTES.md:103-105, :120-121 | Ja |

---

### H — Was von diesem Kanal HEUTE noch gilt

1. **Die Spur ist bewusst sekundaer.** Seit 2026-07-04 ist der Engine-allein-Pfad das Produkt; der Brain bleibt
   Forschungs-Asset und Teacher-Gold-Schleife (CLAUDE.md, Block "CURRENT TRUTH + VEHICLE"). Der 2026-06-29-RL-Pivot
   wurde bei $0 widerlegt (docs/STATE.md:1087), und keine LLM-Komponente sitzt im heutigen Champion
   (`pokerbot/strategy/auslese.py` / v5 / r10).
2. **Die uebertragbaren, mehrfach belegten Lehren:**
   - Gewinne kamen aus der **VERDRAHTUNG** (was die Engine dem LLM zur Laufzeit fuettert: made-hand +40,65), nicht
     aus den Gewichten; einen Serve-Hinweis ins TRAINING zu backen ging nach hinten los (−90).
   - **Wahrnehmungs-Fixes wirken, Strategie-Nudges nicht** (made-hand +40 vs solver_freq ±0).
   - **Form ≠ Staerke:** 97,5–98,8 % Token-Genauigkeit neben −43 bzw. −90 bb/100; 71,7 % PokerBench neben einer
     Lookup-Tabelle mit 88,6 %.
   - **Kleine Stichproben luegen**, auch mit AIVAT: dieselbe Konfiguration mass −28,36 und −49,52 (n=500 je).
   - **Imitations-Decke:** fcpa-Policy-Netz −212, Solver-Imitations-Floor ~−72, 9B-SFT+GRPO regrediert — nur RL mit
     realisiertem EV gegen einen STARKEN Gegner koennte darueber hinaus, und ein solcher Gegner existiert nicht in
     der Schleife (docs/QWEN_6MAX_PLAN.md:8-9; docs/STATE.md:1113).
3. **Die Instrumente leben weiter, auch wenn die Modelle es nicht tun:** `research/study_grade.py` (rekonstruiert
   und gradet JEDE GTOW-/Slumbot-Sitzung), `research/gtow_tail.py` (Tail-robuste Metriken + Gate-Kontrafaktuale),
   `research/gtow_xray.py`, `research/fable_duell.py` (stehendes Adversar-Instrument),
   `pokerbot/benchmark/kaggle_arena.py`.
4. **Alle Live-AIVAT-Zahlen der Brain-Aera tragen den invertierten-Blinds-Bug** (bis 2026-07-05) und sind damit
   vermutlich zu pessimistisch; gepaarte A/Bs innerhalb der Aera bleiben aussagekraeftig, absolute Niveaus nicht.

---

## Selfplay-, Gym- und Gate-Messungen

Dieser Kanal misst **Differenzen zwischen zwei Bot-Versionen auf identischen Karten** (Duplicate-/Spiegel-Prinzip:
ein Deck wird zweimal gespielt, die Arme tauschen die Sitze — die Kartenvarianz kürzt sich weg,
`pokerbot/benchmark/duplicate.py:1-8`). Er kann deshalb **billig und mit kleiner Streuung entscheiden, ob eine
Änderung in der eigenen Selfplay-Ökologie schlechter ist als der Amtierende** (Nichtverschlechterungs-Schranke).
Er kann **NICHT** sagen, wie stark der Bot absolut ist, ob ein Gewinn gegen einen fremden/adaptiven Gegner
transferiert, und er ist **nicht transitiv** (A schlägt B, B schlägt C ⇏ A schlägt C um die Summe — gemessen:
Journal-Zeile 92). Der absolute Anker bleibt GTOW/Analyzer; alle Zahlen hier sind **relativ**.

### Kanal-Steckbriefe — was jeder Kanal beweisen kann und was nicht

| Kanal | Quelle | Beweist | Beweist NICHT |
|---|---|---|---|
| `pargate` (HU-Spiegel) | `pokerbot/autogym/pargate.py:1-8` | Kandidat vs Incumbent auf identischen Decks, per-Deck-Edges, robuste Statistik | absolute Stärke; Transfer auf fremde Gegner; Härtung gegen Adaption |
| `pargate6` (6-max-Spiegel) | `pokerbot/autogym/pargate6.py:1-15` | 6-max-Version-Duell; Held rotiert über alle 6 Sitze, Liga geseedet | nur Selbst-Ökologie ("tag spielt zu Hause gegen seine eigene Liga") |
| `envgate` | `pokerbot/autogym/envgate.py:1-22` | Import-Zeit-/Env-Flags (Subprozess-Hygiene) vs **GTOBaseline** — Vorzeichen + Spew-Kanarienvogel | Selfplay-Wahrheit; ein Arm kann hier gewinnen und im Spiegel neutral sein (explizit vorregistrierte Grenze) |
| `orakel_duell` | `pokerbot/autogym/orakel_duell.py:1-14` | Formel-Verletzungsraten (L/F-Klassen je 1000 Entscheidungen) beider Arme | Chips/EV — es ist das **zweite** Instrument neben pargate, kein Ersatz |
| `exploit_jagd` | `pokerbot/autogym/exploit_jagd.py:1-15` | wo ein **adaptiver** Jäger (persistentes Dirichlet-Modell) den eingefrorenen Bot melkt = Härtungs-Landkarte | Sieg/Verdikt — der Ertrag ist der Ledger, nicht die Zahl |
| `exploit_gate` | `pokerbot/autogym/exploit_gate.py:1-14` | ob der Exploit-Kanal (ON vs OFF, Fingerprint verifiziert) gegen jedes Liga-Profil etwas bringt | ob ein *anderer* Exploit-Mechanismus funktionieren würde |
| `fable_duell` | `research/fable_duell.py:1-9` | ein LLM-Adversar spielt gegen den Stack, **gezählte** Muster (Open-Fold-Quote, Follow-Through, Size-Tells) | statistische Signifikanz (n=62/92 Hände = Anekdote + Zählung, kein bb/100-Verdikt) |
| `kaggle_arena` | `docs/KAGGLE_ARENA.md`, `pokerbot/benchmark/kaggle_arena.py` | gepaarter Spiegel in der Kaggle-Umgebung (100 bb, `python_repeated_pokerkit`) | GTO-Anker — das Feld sind LLMs, kein Re-Solver |

### Die A/A-Nulltests — die Eintrittskarte jeder Messreihe

Ein A/A-Lauf setzt Kandidat = Incumbent. Weil beide Arme dieselben Decks, dieselben Seeds und denselben Code
haben, **muss** die per-Deck-Differenz EXAKT 0 sein. Ist sie das nicht, misst das Instrument Rauschen aus der
eigenen Verdrahtung (RNG-Strom, hand_id, Prozess-Env) — und **jede** Zahl der Reihe ist wertlos. Der Nulltest hat
in diesem Projekt dreimal echte Bugs gefangen (r10 hand_id, Kaggle RNG-Strom, Deck-Ordnung).

| Datum | Was gemessen | Instrument/Kanal | Ergebnis | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-08-17 | A/A nach Spot-RNG-Seeding-Fix | pargate | 0,00 ± 0,00 bb/100, max_abs_edge 0, n=1936 Decks | BESTANDEN | `data/autogym/journal.jsonl:50` | ja — Basis aller Runde-5-Zahlen |
| 2026-08-30 | A/A r6_button | pargate | 0,0 ± 0,0, n=1200 | BESTANDEN | `data/runs/20260830_194513_pargate_r6_button/result.json` | ja |
| 2026-08-30 | A/A r7_river (exakte Enumeration, RNG-frei) | pargate | 0,0 ± 0,0, n=576 | BESTANDEN | `data/runs/20260830_194908_pargate_r7_river/result.json` | ja |
| 2026-08-30/31 | A/A r8_stack (GPU-Arm, Determinismus-Beweis) | pargate | 2× 0,0 ± 0,0, n=600 | BESTANDEN | `data/runs/20260830_203659_pargate_r8_stack/`, `…20260831_002812…/result.json` | ja — GPU-Determinismus gilt |
| 2026-09-01 | A/A r10_ernte (fp16-Determinismus) | pargate | 0,0 ± 0,0, n=576 | BESTANDEN | `data/runs/20260901_114509_pargate_r10_ernte/result.json` | ja |
| 2026-09-07 | A/A r10_stack **vor** Bugfix | pargate | **−9,40 ± 10,92**, 13 nonzero, n=576 | **FEHLGESCHLAGEN → Bug** | `data/runs/20260907_213225_pargate_r10_stack/result.json` | nein — Ursache `hand_id = 2*deck+half` machte die privaten Seeds der Spiegelhälften verschieden |
| 2026-09-07/08 | A/A r10_stack nach Fix (3×, je neuer Hash) | pargate | 3× 0,0 ± 0,0, nonzero 0, n=576 | BESTANDEN | `data/runs/20260907_214142_…`, `…220348…`, `20260908_015248_pargate_r10_stack/result.json` | ja; **Lehre: 40-Deck-A/A reicht für K2 nicht** (nur 1 Plan-Deck), 576 nötig — Journal-Zeile 106 |
| 2026-09-09 | A/A tag vs tag im 6-max-Kanal | pargate6 | 0,0 ± 0,0, nonzero 0, n=288 Decks (=1728 Hero-Hände) | BESTANDEN | `data/runs/verdrahtung/aa_tag.log` (Schlusszeile), `data/runs/20260909_181514_pargate6_tag` | ja |
| 2026-09-10 | A/A prince[final] im Kaggle-Kanal **vor** Fix | kaggle_arena | **−37,5 ± 94,49**, n=8 → STOPP | **FEHLGESCHLAGEN → Bug** | `data/runs/kaggle_aa_2026-09-10.log` (Schlusszeile) | nein — Ursache: Bot zieht aus EINEM RNG-Strom über Hände; wiederverwendete Agenten liefen auseinander |
| 2026-09-10 | A/A nach Fix (frische Instanzen je Hälfte) | kaggle_arena | exakt 0 (nonzero 0, SE 0) | BESTANDEN | `docs/KAGGLE_ARENA.md:62-63` | ja |

---

## 1. pargate — der HU-Spiegel und die AUSLESE-Kette v1 → v5

Was dieser Abschnitt zeigt: die Versionskette wurde **ausschließlich** über gepaarte Selfplay-Duelle gebaut. Alle
Zahlen sind Differenzen (bb/100) gegen einen genannten Incumbent, nie absolute Stärke.

### 1.1 AUSLESE v1 (`sel_guard` — Selektion statt Frequenz am Flop)

| Datum | Was gemessen | Instrument/Kanal | Ergebnis | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-08-16 | `sel_guard` vs `basis`, Erstlauf | pargate | +4,70 ± 2,06, n=99.000 Decks, CI95 [0,6; 8,8] | ANWENDEN | `data/runs/20260816_213357_pargate_sel_guard/result.json`; `journal.jsonl:20` | ja, aber von v3/v4/v5 überholt |
| 2026-08-16 | `sel_guard` Replikation, frisches Deck-Universum (Seeds 20000+) | pargate | +7,49 ± 2,08, n=99.000 | ANWENDEN bestätigt | `data/runs/20260816_222836_pargate_sel_guard/result.json`; `journal.jsonl:21` | ja |
| 2026-08-16 | Pool beider Läufe | pargate | **≈ +6,1 ± 1,5** über 198.000 Decks | ANWENDEN (Taufe AUSLESE v1) | `journal.jsonl:21` | ja — der erste bewiesene Schritt |
| 2026-08-16 | Sanity-Lauf `sel_guard` bei kleinem n | pargate | +13,81 ± 17,8, n=1200 | NEUTRAL (Kanal zu laut) | `data/runs/20260816_213258_pargate_sel_guard/result.json` | Illustration: n=1200 ist im HU-Spiegel nutzlos |

### 1.2 AUSLESE v2 (`sel_all`) — **verworfen, die Rotation war verfrüht**

| Datum | Was gemessen | Instrument/Kanal | Ergebnis | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-08-17 | `sel_all` vs `sel_guard`, Lauf 1 | pargate | +3,00 ± 1,40, n=30.000 | zunächst ANWENDEN+ROTATION | `data/runs/20260817_001033_pargate_sel_all/result.json`; `journal.jsonl:25` | **nein — superseded** |
| 2026-08-17 | Replikation Lauf 2 | pargate | +0,44 ± 1,09, n=30.000; gepoolt +1,41 ± 0,86 (< 2 SE) | REPLIKATION-NICHT-BESTANDEN | `data/runs/20260817_002130_pargate_sel_all/result.json`; `journal.jsonl:27` | ja (als Negativbefund) |
| 2026-08-17 | Entscheider Lauf 3 | pargate | +0,18 ± 0,73, n=90.000; **gepoolt +0,69 ± 0,56** | ROTATION ABGELEHNT, v2 demontiert | `data/runs/20260817_003212_pargate_sel_all/result.json`; `journal.jsonl:28` | ja — v2 existiert nur als Tag, war nie amtierend |
| 2026-08-17 | Nach-Diagnose desselben Arms mit Margin 15pp (`sel_all_m15`) | pargate | 0,0 ± 0,0, **0 divergente Decks auf 29.920** | Umdeutung: „**kein Kanal**", nicht „refutiert" | `journal.jsonl:51`, `:59` | ja — wichtige Unterscheidung |

Der +3,00-Erstlauf war Stichprobenglück. Daraus wurde die **3-Läufe-Regel** (kein Name ohne drei Läufe), die
danach eine zweite Fehl-Taufe verhinderte.

### 1.3 AUSLESE v3 (`sel_m15` — Margen-Sweep)

| Datum | Was gemessen | Instrument/Kanal | Ergebnis | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-08-17 | Sweep `sel_m06` vs v1 | pargate (runde4) | +0,06 ± 1,45 (vs basis +0,3) | NEUTRAL | `journal.jsonl:34` | ja |
| 2026-08-17 | Sweep `sel_m10` vs v1 | pargate (runde4) | +5,64 ± 1,74 (vs basis +8,72) | ANWENDEN | `journal.jsonl:35` | ja |
| 2026-08-17 | Sweep `sel_m15` vs v1 | pargate (runde4) | +10,50 ± 2,10 (vs basis +17,47) | ANWENDEN | `journal.jsonl:36` | ja, aber Punktschätzer zu hoch (s. u.) |
| 2026-08-17 | `sel_m15` vs v1, Replikation | pargate | +1,11 ± 2,16, n=30.000 — **3 Sigma vom Erstlauf entfernt** | REPLIKATION-HETEROGEN | `data/runs/20260817_134312_pargate_sel_m15/result.json`; `journal.jsonl:39` | ja — **der Fat-Tail-Befund**: per-Deck-Edges sind fettrandig, 2SE-Intervalle der leisen Kanäle zu optimistisch |
| 2026-08-17 | `sel_m15` vs v1, Lauf 3 | pargate | +2,63 ± 1,22, n=90.000; gepoolt **+3,94 ± 0,95** (konservativ ohne Erstlauf +2,13 ± 1,06) | ANWENDEN + Taufe v3 | `data/runs/20260817_140247_pargate_sel_m15/result.json`; `journal.jsonl:41` | ja |
| 2026-08-17 | `sel_m15` vs `basis`, Großanker | pargate | **+8,68 ± 1,28**, n=183.200 Decks, 20 Worker, 2821 s (3897 Decks/min) | ANWENDEN | `journal.jsonl:38` | ja |
| 2026-08-17 | `sel_m20` vs `sel_m15` (Dosis-Obergrenze) | pargate | −1,52 ± 1,54, n=30.000 | NEUTRAL — Kurve kippt, 15pp = Plateau-Rand | `data/runs/20260817_135314_pargate_sel_m20/result.json` | ja |

### 1.4 AUSLESE v4 (`turn_wert` + Env-Flags) — der Bet-Seite-Schritt

| Datum | Was gemessen | Instrument/Kanal | Ergebnis | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-08-17 | Kanalbreite VOR dem Bau (Vorregistrierung) | pargate-Probe, 400 Decks | `turn_wert` würde in 40/800 Händen (5 %) betten; `sel_all_m15`-Turn-Fold-Spots **0/800** | Kanal vorgemessen (AP8-Regel) | `journal.jsonl:43`, `:42` | ja — Doktrin „Kanal vor dem Bau vermessen" |
| 2026-08-17 | `turn_wert` vs `sel_m15`, Lauf 1 (Estimator v1, 5 % Trim) | pargate | roh +1,64 ± 4,03, **getrimmt 0,00** | NEUTRAL | `journal.jsonl:52` | **nein — superseded**: der 5 %-Trim entfernte bei 8,4 % divergenten Decks exakt die Signal-Decks (`pokerbot/autogym/stats.py:20-33`) |
| 2026-08-17 | `turn_wert` vs `sel_m15`, Läufe 2+3 (Estimator v2 = rohes Mittel ± 2 SE) | pargate | +9,39 ± 4,06 und +10,78 ± 4,00, je n=29.920, Vorzeichen-z 9,15/8,98 | ANWENDEN | `journal.jsonl:61`, `:62` | ja |
| 2026-08-17 | Pool 3×30k | pargate | **+7,27 ± 2,33**, n=89.760, nonzero-Anteil 8,58 %, Vorzeichen-z 14,93 | ANWENDEN | `journal.jsonl:63` | ja |
| 2026-08-17 | Nachbewertung mit Estimator v3 (Bootstrap-CI + Permutations-p) | pargate | `turn_wert` CI [+2,69; +12,05], p = 0,0007 → **HÄLT** | Verdikt bestätigt | `journal.jsonl:68` | ja |
| 2026-08-17 | `turn_wert(sel_m15)` vs **eingefrorene basis**, 3 Läufe | pargate | +9,26 ± 4,88 / +16,75 ± 4,84 / +22,42 ± 4,69 | ANWENDEN | `data/runs/20260817_222907_…`, `…230825…`, `…231632_pargate_turn_wert/result.json` | ja |
| 2026-08-17 | Pool derselben 3 Läufe | pargate | **+16,14 ± 2,77**, CI95 [+10,74; +21,56], perm_p 0,0002, n=89.760 | ANWENDEN | `journal.jsonl:70` | ja — der v4-Kern-Beleg |

### 1.5 Runde 6 — Härtungs-Guards: die Zwei-Achsen-Lehre

| Datum | Was gemessen | Instrument/Kanal | Ergebnis | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-08-18 | `r6_ecall` (River-eCall-Guard) vs `turn_wert` | pargate | **−4,15 ± 0,97**, CI [−6,12; −2,30], Vorzeichen-z −4,7, nz-Median −1452 Chips, n=29.920 | **VERWERFEN** | `data/runs/20260817_235330_pargate_r6_ecall/result.json`; `journal.jsonl:72` | ja — im Spiegel sind die gefoldeten River-Calls **Value-Folds**; der Fable-Exploit lebt auf der adaptiven Achse, die der Spiegel nicht sieht |
| 2026-08-18 | `r6_button` (Button-Open-Fold-Disziplin) vs `turn_wert` | pargate | +0,71 ± 2,18, CI [−3,45; +5,12], Kanal 16,7 %, n=29.920 | NEUTRAL-HÄRTUNGSKANDIDAT | `data/runs/20260818_000120_pargate_r6_button/result.json`; `journal.jsonl:73` | ja |
| 2026-08-18 | Finaler v4-Stack (`r6_button`-Kette) vs **basis** | pargate | **+23,36 ± 5,32**, CI [+12,75; +33,72], perm_p 0,0002, Vorzeichen-z 9,72, nonzero 37,4 % | ANWENDEN | `data/runs/20260818_013257_pargate_r6_button/result.json`; `journal.jsonl:76` | ja |

**Gemessene Doktrin (bindend, Journal-Zeile 74):** Härtungs-Guards gegen ADAPTIVE Gegner sind im Spiegel
*strukturell unsichtbar bis negativ*. Korrektes Protokoll: **Spiegel = Nichtverschlechterungs-Schranke,
Adversar = Wirkungs-Beweis.**

### 1.6 Runde 7/8 — River-Chirurgie → AUSLESE v5 (der heutige Champion)

| Datum | Was gemessen | Instrument/Kanal | Ergebnis | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-08-30 | `r7_bill` (River-Big-Bet-Defense) vs `r6_button` | pargate | **exakt 0,0 ± 0,0**, n=30.000 — der Guard feuert im Gym nie | NEUTRAL / „kein Kanal" | `data/runs/20260830_200117_pargate_r7_bill/result.json` | ja — als GTOW-Achsen-Guard klassifiziert, **nicht** im Stack |
| 2026-08-30 | `r7_river` (= `river_wert_bremse`) vs `r6_button` | pargate | +8,10 ± 1,14, CI [+5,90; +10,46], p 0,0002, n=30.000 | ANWENDEN | `data/runs/20260830_194936_pargate_r7_river/result.json` | ja |
| 2026-08-30 | `r7_wert` (Einzel-Zerlegung) vs `r6_button` | pargate | +8,81 ± 1,25, CI [+6,43; +11,39], p 0,0002 | ANWENDEN | `data/runs/20260830_201255_pargate_r7_wert/result.json` | ja |
| 2026-08-30 | `r7_river` Replikation, dritte disjunkte Bank | pargate | +7,38 ± 1,05, CI [+5,40; +9,46], p 0,0002 | ANWENDEN, 3-Läufe-Regel erfüllt | `data/runs/20260830_202416_pargate_r7_river/result.json`; `journal.jsonl:91` | ja |
| 2026-08-30/31 | `r8_stack` (GPU-Solver-Chirurgie) vs `r6_button`, 3 Läufe auf Bänken 470k/530k/560k | pargate | +29,92 ± 3,10 / +23,76 ± 3,07 / +29,23 ± 3,03; **gepoolt +27,6 ± 1,8**; alle perm_p 0,0002 | ANWENDEN | `data/runs/20260830_204212_…`, `20260831_003356_…`, `20260831_024259_pargate_r8_stack/result.json`; `journal.jsonl:93` | ja |
| 2026-08-30 | `r8_stack` vs **eingefrorene basis** | pargate | +30,60 ± 5,03, CI [+20,61; +40,29], p 0,0002, getrimmt +16,79 | ANWENDEN | `data/runs/20260830_225057_pargate_r8_stack/result.json` | ja — **mit Ehrlichkeitsvermerk** |
| 2026-08-31 | Taufe **AUSLESE v5** (Tag `auslese-v5`, Commit ec11fde) | pargate-Kette | FINAL_STACK = `river_gpu_guard(river_wert_bremse(r6_button(turn_wert(sel_m15))))` | GETAUFT | `journal.jsonl:93`; `pokerbot/strategy/auslese.py:4`, `:34` | **ja — das ist der heutige Champion** |

**Zwei vorregistrierte Erwartungsverletzungen, offen dokumentiert** (Journal-Zeile 92):
(a) das r8-Inkrement war **3–4× größer als vorregistriert** (+7…+9 erwartet, +29,9 gemessen) — Zerlegung
konsistent mit Big-Pot-Chirurgie (3–3,5 % Divergenz-Decks, ~17 bb je Eingriffs-Deck);
(b) **Nicht-Additivität**: +30,6 vs basis statt der additiv erwarteten ~+53 → Selfplay ist nicht transitiv,
der Spiegel bleibt ein Selektions-Kanal, der Absolut-Beweis gehört dem GTOW-Anker.

### 1.7 Runde 9/10 — was NICHT geshipt wurde (die wertvollen Negativbefunde)

| Datum | Was gemessen | Instrument/Kanal | Ergebnis | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-08-31 | `r9_pre` (stackoff_bremse + no_limp) vs `r8_stack` | pargate | **−11,42 ± 2,97**, CI [−17,12; −5,68], n=30.000 | **VERWERFEN** | `data/runs/20260831_095123_pargate_r9_pre/result.json`; `journal.jsonl:96` | ja |
| 2026-08-31 | Täter-Diagnose dazu | Trigger-Zählung, 200 Decks | Basis limpt **78/400 Hände** (~39 % der Buttons) strategisch → `no_limp_guard` baute das halbe Preflop-Spiel um (37,8 % Divergenz-Decks); `stackoff_bremse` feuerte **1×/400** = selfplay-stumm | no_limp VERWORFEN, stackoff unschuldig | `journal.jsonl:96` | ja — Lehre: der Fable-Befund „Limp-Call→Fold 5/7" ist ein **Limp-Pot-Verteidigungs**-Problem, nicht das Limpen selbst |
| 2026-08-31 | `r9_play` (river_play_guard) vs `r8_stack` | pargate | +1,14 ± 2,78, CI [−4,12; +6,32], p 0,347, n=30.000 | NEUTRAL | `data/runs/20260831_201350_pargate_r9_play/result.json` | ja |
| 2026-09-01 | `r9_v8` (Komposition) vs `r8_stack`, 2 Läufe | pargate | +3,91 ± 2,85 (n=30.000, p 0,081) und −1,23 ± 4,36 (n=14.976, p 0,607); gepoolt ≈ +2,3 ± 2,4 | NEUTRAL → **v8 gedroppt** (User-Entscheid) | `data/runs/20260901_002705_…`, `20260901_044634_pargate_r9_v8/result.json`; `journal.jsonl:97` | ja — Postmortem `docs/V8_POSTMORTEM.md`: (a) Kanal-Sättigung (nz-Median 1,9 bb vs 11,6 bb bei r8), (b) der Spiegel bestraft Feinpräzision nicht (kein Re-Solver), (c) Ockham bei Gleichstand |
| 2026-09-08 | `r10_stack` (v10: K1 hero_range + K2 river_plan) vs `r8_stack` — Gate G5 | pargate | +11,68 ± 10,85, CI [−9,39; +33,06], p 0,156, n=1968 Decks | NEUTRAL (Gate G5 BESTANDEN: keine asymmetrische Katastrophe) | `data/runs/20260908_002035_pargate_r10_stack/result.json`; `journal.jsonl:107` | ja — **aber v10 ist NICHT geshipt** (G3 verfehlt); alle 3 Decks ≤ −100 bb entstanden im **Off-Tree-Fallback auf die nackte Basis ohne v5-Chirurgie**, offtree-Quote 42 % |

---

## 2. envgate — gepaarter Zwei-Lauf-Test der Import-Zeit-Flags gegen GTOBaseline

Was dieser Kanal kann: Env-Flags messen, die im pargate-Prozess **nicht** trennbar wären (Modul-Level-Konstanten,
`bot.py` liest bei Import). Was er **nicht** kann: die Selfplay-Wahrheit ersetzen — gemessen wird gegen einen
festen dritten Gegner (GTOBaseline), nicht gegen den Amtierenden. **Seit 2026-08-17 heißen envgate-Verdikte
`KANAL_*` und sind ausdrücklich KEINE Ship-Evidenz** (`journal.jsonl:69`).

| Datum | Was gemessen | Instrument/Kanal | Ergebnis (n=11.968 Decks je Arm) | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-08-17 | `prince` (PRINCE-Profil) vs Referenz | envgate | **−68,64 ± 11,90** | VERWERFEN — **aber Artefakt** | `data/runs/20260817_201814_envgate/result.json`; `journal.jsonl:60` | **nein als Bot-Urteil**: exploit-OFF-Kanal-Artefakt (die Referenz beutet den schwachen GTOBaseline aus, der Arm nicht) — **kein** Urteil über PRINCE vs GTOW |
| 2026-08-17 | `raise_narrow` Dosis 1.0, 3 Läufe | envgate | +16,78 ± 4,10 / +13,65 ± 3,70 / +9,17 ± 3,61 | ANWENDEN (2/3), alle CI > 0 nach Estimator v3 | `20260817_201814_…`, `…205654…`, `…211423_envgate/result.json`; `journal.jsonl:68` | ja im Kanal — **nur resolver-OFF-Kontext** |
| 2026-08-17 | `raise_narrow` Dosis 0.5, 3 Läufe | envgate | +5,64 ± 2,88 / +6,49 ± 2,60 / +5,51 ± 3,09 | fällt in 2/3 Läufen auf NEUTRAL (CI berührt 0) | dieselben Läufe; `journal.jsonl:68` | ja — RN05 war nie in der Version |
| 2026-08-17 | `k3_deception` (TURN_DEFENSE 0.07 + SLOWPLAY 0.25) allein, 3 Läufe | envgate | +8,72 ± 4,60 / +0,28 ± 3,75 / −4,69 ± 4,04 | **allein NICHT repliziert** | dieselben Läufe; `journal.jsonl:64` | ja |
| 2026-08-17 | K3 **in** der Kombination (kombi_r5 − kombi_schlank, gepaart) | envgate, Bank 65000, 12k Decks | **+10,19 ± 4,01**, Vorzeichen-z +5,4, nz-Median +198 | Interaktion nachgewiesen → Montage als EINHEIT | `journal.jsonl:64` | ja |
| 2026-08-17 | `turn_def_advisor` | envgate | −3,37 ± 6,95 / +0,88 ± 7,15 / **−20,19 ± 6,72** | VERWERFEN | `20260817_211423_envgate/result.json` | ja — nie geshipt |
| 2026-08-17 | `kombi_r5` (= v4-Env-Satz), 3 Läufe | envgate | +26,36 ± 6,04 / +25,22 ± 5,63 / +36,15 ± 6,01, alle perm_p 0,0002 | ANWENDEN (Kanal) | `20260817_205654_…`, `…211423…`, `…213451_envgate/result.json` | ja |
| 2026-08-17 | **Finale-Treppe** vs eingefrorener basis, Bank 85000, 12k Decks | envgate | `auslese_v3` **+21,36 ± 6,03**; `kombi_r5` **+49,79 ± 7,99**; gepaarte Stufe v3→v4 **+28,44 ± 6,17** (Vorzeichen-z +10,1) | Taufe AUSLESE v4 | `data/runs/20260817_214458_envgate/result.json`; `journal.jsonl:65-66` | ja im Kanal — die +49,8 sind **envgate**, nicht mit den pargate-Zahlen mischbar |

---

## 3. orakel_duell — die Mathematik-Benchmark als zweites Instrument

Was dieser Kanal kann: prüfen, ob ein Arm die Zielklasse drückt, **ohne** eine andere zu heben (Goodhart-Schutz).
Was er nicht kann: Chips/EV ersetzen.

| Datum | Was gemessen | Instrument/Kanal | Ergebnis | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-08-17 | `turn_wert` vs `sel_m15`, Klassenraten je 1000 Entscheidungen | orakel_duell, n=1500 Decks (8493 bzw. 8568 Entscheidungen) | Zielklasse `verpasster_wert_turn` **17,04 → 3,06**; Gegenprobe `bet_braucht_unplausible_folds` **10,04 → 7,54** (gesunken, nicht gestiegen); `call_unter_pot_odds` 24,63 → 20,13 | Panel GRÜN | `data/runs/20260817_213232_orakel_duell_turn_wert/result.json` | ja — der Guard tut, was er soll, ohne neue Klassen zu erzeugen |
| 2026-08-16 | Autogym-Pilot HU + 6-max, Orakel-Stufen | selftest/gym | HU 600 Hände: 3078 Entscheidungen, HART 0 · P 0 · L 62 · F 1; 6-max 300 Hände: 3002 Entscheidungen, HART 0 · P 0 · L 0 · F 1 | Schleife läuft | `data/autogym/report_20260816_195830.json` | ja |
| 2026-08-16 | Durchsatz-Pilot (E5) | gym lokal | 500 Hände + 3.577 gegradete Entscheidungen in 52 s (~580 Hände/min) | E5 lokal ✓, Pod offen | `docs/AUTOGYM_PLAN.md:45` | ja |
| 2026-08-16 | Symmetrie-Check (E2, Paar-Drift) | gym_hu | HU 600 Hände: Button-Netto **+33,43 bb/100**, Paar-Drift +106,80 ± 70,26 (1,5 SE, verträglich mit 0) | E2 verträglich, mehr Paare nötig | `data/autogym/report_20260816_195830.json` | ja |
| 2026-08-16 | Detektor-Check gegen konstruierten Defekt-Bot (E3) | selftest | gesund vs Nie-Folder **+394,9 ± 279,9** (60 Decks, 1-Hand-Horizont ohne Anpassung) | EXPERIMENT-KANDIDAT (Streuung zu groß für ein Verdikt) | `journal.jsonl:7` | ja, als Sanity-Signal |
| 2026-08-16 | Null-Stabilität (E4) / Gate-Selbsttest exploit-OFF vs ON | pargate-Selbsttest | +1,41 ± 2,18 (n=150) bzw. +2,1 ± 3,3 | NEUTRAL — keine erfundenen Verbesserungen | `data/autogym/report_20260816_195830.json`; `docs/AUTOGYM_PLAN.md:150,158` | ja |
| 2026-08-17 | 6-max-Katalog (Facing-Verhalten) | gym_six, 30.000 Hände | Positions-bb/100: BTN +33,5 · HJ +15,8 · UTG +6,8 · CO +2,4 · BB −28,9 · SB −29,6. Fold-Frequenzen: Flop **0,216** (21.165 Knoten) · Turn 0,297 (11.565) · River 0,337 (8.143) | Katalog-Befund | `journal.jsonl:37` | ja — belegt: der **Flop-Overfold ist HU-spezifisch**, 6-max foldet 0,216 bei erlaubten 0,30 |

---

## 4. Die Adversar-Achse — exploit_jagd und fable_duell

Was diese Kanäle können: **Härtung beweisen** (findet ein anpassungsfähiger Gegner eine Rente?). Was sie nicht
können: bb/100-Verdikte liefern — `fable_duell` ist mit n=62/92 Händen Anekdote **plus gezählte Muster**.

| Datum | Was gemessen | Instrument/Kanal | Ergebnis | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-08-17 | 20 adaptive Dirichlet-Jäger vs eingefrorene Basis | exploit_jagd, n=100.000 Hände | **+8,87 ± 6,9 bb/100** (14/20 Jäger positiv) | Adaptions-Zugewinn nicht signifikant | `data/runs/20260817_020232_exploit_jagd/result.json`; `journal.jsonl:30` | ja |
| 2026-08-17 | Null-Kontrolle (ohne Adaption) | exploit_jagd, n=100.000 | +7,73 ± 8,7 (12/20 positiv) | **Zugewinn durch Adaption ≈ +1, nicht signifikant** | `data/runs/20260817_014431_exploit_jagd/result.json` | ja — **Struktur schlägt Anpassung** (sel_guard +6,1 vs generische Adaption ~+1) |
| 2026-08-17 | Verschiebung des Gewinn-**Kanals** (adaptiv vs Kontrolle) | exploit_jagd | Showdown-Netto **+5,81 → +19,85**; Non-Showdown **+1,92 → −10,99** | Befund: die Adaption verschiebt, wo das Geld herkommt | dieselben zwei result.json | ja |
| 2026-08-17 | Konvergenz-Profil aller 20 Jäger auf den Verteidiger | exploit_jagd | VPIP 0,75–0,77 · fold_to_bet 0,29–0,31 · aggression 0,31–0,34 (alle 20 unabhängig) | **die empirische Härtungs-Landkarte** | `journal.jsonl:30` | ja |
| 2026-08-17 | Tail-Risiko generischer Adaption | exploit_jagd | zwei Katastrophen-Jäger (−69 / −47 bb/100) | Warnung | `journal.jsonl:30` | ja |
| 2026-08-17 | LLM-Adversar (Fable) vs AUSLESE v4 | fable_duell, 62 Hände | +115,5 bb für den Adversar (**Anekdote**). Gezählt: Button-Open-Fold ~29 % · Limp-Call→Fold-vs-Cbet 5/7 · River-Station 4/5 große Calls mit Verlierern (~90 bb) · Check-Raise ohne Follow-Through 3/3 · turn_wert-Bets in Continuation-Linien 3/3 echt (als Tell nutzbar) | Härtungs-Liste, kein bb/100-Verdikt | `journal.jsonl:71` | ja — Kernbefund: die **gecappte Check-Range** (= v8-Purify-Mechanismus) |
| 2026-08-18 | Fable-Retest gegen den gehärteten `r6_button`-Stack | fable_duell, 92 Hände | Ernte **186 → 58 bb/100**; Open-Folds **0/46** (vorher ~29 %); 3bet-Angriff aufs Trash-Open netto −21 bb | **HÄRTUNG BEWIESEN** | `journal.jsonl:75` | ja — genau der Guard, den der Spiegel als NEUTRAL durchgewinkt hatte |
| 2026-08-18 | Rest-Lecks nach der Härtung | fable_duell | River-eCall 5/5 Value-Bets bezahlt (~90 % der Rest-Ernte); turn_wert-**Size-Tell 7/7** (groß = stark, klein = schwach → Seesaw verletzt); Stack-off nach eigener Aggression | offen | `journal.jsonl:75` | ja — offene Baustellen |

---

## 5. exploit_gate — ist der Exploit-Kanal überhaupt korrekt?

Was dieser Kanal kann: denselben Bot mit `POKERB_EXPLOIT=1` gegen `=0` stellen (frische Prozesse, Fingerprint je
Arm verifiziert), gegen **jedes Liga-Profil einzeln**, auf identischen Decks mit Button-Tausch. Vorregistriertes
Kriterium: gegen ausbeutbare Profile Differenz ≥ 0 UND CI-Untergrenze > −3 bb/100.

| Datum | Was gemessen | Instrument/Kanal | Ergebnis (Diff ON−OFF, je 600 gepaarte Decks) | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-09-09 | Exploit ON vs OFF, `nit` | exploit_gate | −2,09 ± 9,52, CI [−20,99; +15,85] | Kriterium VERLETZT | `data/runs/verdrahtung/exploit_gate.log`; `data/runs/20260909_192123_exploit_gate` | ja |
| 2026-09-09 | `tag` | exploit_gate | −19,26 ± 15,35, CI [−51,18; +8,20] | NEUTRAL | ebd. | ja |
| 2026-09-09 | `lag` | exploit_gate | −18,50 ± 12,96, CI [−47,65; +3,55] | NEUTRAL | ebd. | ja |
| 2026-09-09 | `station` | exploit_gate | −17,35 ± 16,31 | Kriterium VERLETZT | ebd. | ja |
| 2026-09-09 | `maniac` | exploit_gate | −15,74 ± 9,61 | Kriterium VERLETZT | ebd. | ja |
| 2026-09-09 | `rock` | exploit_gate | −0,31 ± 8,97 | NEUTRAL | ebd. | ja |
| 2026-09-09 | `whale` | exploit_gate | −8,26 ± 17,01 | Kriterium VERLETZT | ebd. | ja |
| 2026-09-09 | `shark` | exploit_gate | −14,40 ± 13,67 | NEUTRAL | ebd. | ja |
| 2026-09-09 | **Gesamt** | exploit_gate | **alle 8 Punktschätzer ≤ 0, gepoolt ≈ −12 bb/100 (SE ~4,5)** | **„Exploit korrekt" REFUTIERT** für den HU-Dirichlet-Pfad | `journal.jsonl:113`; Log-Schlusszeile „Exploit korrekt: False" | **ja — Produktkonsequenz: Exploit bleibt in ALLEN Modi AUS** |
| 2026-09-09 | 6-max-Reads (`SixMaxBot._read`) ON vs OFF | pargate6, n=2992 | +3,64 ± 13,45, CI [−22,03; +30,86] | NEUTRAL (harmlos) | `data/runs/verdrahtung/exploit_gate.log` | ja |

Offene Einschränkung (selbst notiert): der Exploit-Pfad ist **River-only** und trägt keine Anpassung über Hände
hinweg im Gate-Harness — ein echter Exploit bräuchte einen neuen Mechanismus (Selektion, nicht Frequenz).

---

## 6. pargate6 — der 6-max-Spiegel

Was dieser Kanal kann: 6-max-Versionen gegeneinander stellen, Held rotiert über alle 6 Sitze desselben Decks
(jedes Hole-Paar wird einmal vom Helden und einmal von jedem Liga-Profil gespielt). Was er nicht kann: aus der
**Selbst-Ökologie** heraus (`tag` spielt gegen seine eigene Liga); der externe Anker bleibt der Analyzer-Grade.

| Datum | Was gemessen | Instrument/Kanal | Ergebnis (n=2992 Decks je Lauf, 8 Worker) | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-09-09 | `hybrid` (tag + Prince-Takeover in HU-kollabierten Pötten) vs `tag` | pargate6 | **−23,56 ± 9,02**, CI [−40,84; −5,26], Vorzeichen-z −7,6 | **VERWERFEN** | `data/runs/verdrahtung/hybrid_vs_tag.log`; `data/runs/20260909_181534_pargate6_hybrid` | ja |
| 2026-09-09 | `hybrid_r8` (Takeover mit FINAL_STACK r8_stack) vs `tag` | pargate6 | **−21,73 ± 9,01**, CI [−38,98; −4,36] | **VERWERFEN** | `data/runs/verdrahtung/hybrid_r8_vs_tag.log` | ja |
| 2026-09-09 | `hybrid_r10` (RC_STACK) vs `tag` | pargate6 | **−26,61 ± 8,93**, CI [−43,87; −9,38] | **VERWERFEN** | `data/runs/verdrahtung/hybrid_r10_vs_tag.log` | ja |
| 2026-09-09 | `hybrid_r8` vs `hybrid` (rettet die Kette den Takeover?) | pargate6 | +1,82 ± 5,58, CI [−9,01; +12,90] | NEUTRAL — **nein** | `data/runs/verdrahtung/hybrid_r8_vs_hybrid.log` | ja |
| 2026-09-09 | **Verdikt** | pargate6 | Der Prince-Takeover (HU-Projektion in 6-max-Pötten) ist im 6-max-Kanal **schädlich**; bester gemessener 6-max-Bot = Liga-Kern `tag` | six_server-Takeover **default AUS** (`POKERB_SIX_TAKEOVER=1` schaltet ein) | `journal.jsonl:112` | ja |
| 2026-09-09 | `tag_flatfix` (flat_guard: dominierte Offsuit-Broadways nie vs Open flatten) vs `tag`, Lauf 1 | pargate6 | **+17,70 ± 6,40**, CI [+4,93; +29,92], perm_p 0,0035 | ANWENDEN | `data/runs/pargate6_tag_flatfix_2026-09-09.log` | ja |
| 2026-09-09 | Lauf 2 | pargate6 | +11,36 ± 6,88, CI [−2,01; +25,16], perm_p 0,057 | NEUTRAL | `data/runs/pargate6_tag_flatfix_seed2_2026-09-09.log` | ja |
| 2026-09-09 | Lauf 3 | pargate6 | **+19,18 ± 7,01**, CI [+5,59; +33,19], perm_p 0,0035 | ANWENDEN | `data/runs/pargate6_tag_flatfix_seed3_2026-09-09.log` | ja |
| 2026-09-09 | Gepoolt (3-Läufe-Regel) | pargate6 | **≈ +16 bb/100** | ANGEWENDET auf `PROFILES["tag"]` | `journal.jsonl:118`; `pokerbot/arena/sixmax.py:59` (`flat_guard=True`) | **ja — im Produkt** (Liga, Berater, Turnier); alter Kern = Tag `sixmax-tag-pre-flatfix` |

---

## 7. Transfer-Tests gegen einen fremden Gegner — was NICHT funktioniert hat

| Datum | Was gemessen | Instrument/Kanal | Ergebnis | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-08-17 | Transferiert der AUSLESE-v1-Gewinn auf einen fremden Gegner? | ungepaart vs GTOBaseline, n=3000 Decks | −3,78 ± 30,31 (AUSLESE −23,40 ± 21,99 vs Basis −19,62 ± 20,86) | uninformativ | `journal.jsonl:29` | ja (als Methodenbefund) |
| 2026-08-17 | Wiederholung korrekt gepaart (per-Deck-Differenz) | gepaart vs GTOBaseline, n=3000 | −3,80 ± 12,87 | **uninformativ** | `journal.jsonl:31-32` | ja |
| 2026-08-17 | Ursachen-Diagnose | — | Die per-Deck-Paarung **bricht**, weil die MC-Equity-Aufrufe UNGESEEDET sind (`equity_vs_*` ohne rng) → beide Arme divergieren auf jedem Deck stochastisch | Auflösung bräuchte ~120k Decks **oder** geseedete MC | `journal.jsonl:32` | **ja — bindende Lehre: ungeseedete MC bricht Paarungen** |

---

## 8. kaggle_arena — der neue, noch unkalibrierte Spiegel

| Datum | Was gemessen | Instrument/Kanal | Ergebnis | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-09-10 | `prince[final]` vs `prince[basis]`, erster Referenzwert | kaggle_arena, 300 gepaarte Decks | +55,83, SE **38,02**, getrimmt +6,3, Median 0,0, nonzero 97/300 (32,3 %), nz_pos 45 (Vorzeichen-z −0,71), CI95 [−16,67; +134,58], perm_p 0,0757, 3152,9 s (~10,5 s/Deck) | **NEUTRAL — Kanal-Kalibrierung, KEIN Bot-Verdikt** | `data/runs/kaggle_prince_vs_basis_2026-09-10.log`; `journal.jsonl:121` | ja — Mittelwert tail-getragen; SE 4 bräuchte ~27.000 Decks (~10 h auf 8 Kernen) |
| 2026-09-10 | Stack-Größen-Korrektur | Code-Prüfung | GTOW läuft auf **200 bb** (`gtowizard.py:98` starting_stack 20000), unser Preflop-Blueprint feuert erst ab **140 bb effektiv** (`bot.py:200`) → der 100-bb-Kaggle-Kanal misst einen **anderen** Bot (Heuristik-Kaskade statt Blueprint) | KORREKTUR (Doku war falsch) | `journal.jsonl:122` | **ja — die frühere Behauptung „genau unsere Hausgröße" ist WIDERRUFEN**; `kaggle_arena` hat jetzt `--stack-bb 100\|200` |

---

## 9. Ausdrücklich veraltete / widerrufene Zahlen dieses Kanals

| Zahl | Woher | Warum ungültig | Ersetzt durch |
|---|---|---|---|
| AUSLESE v2 „+3,00 ± 1,40 über v1" | `journal.jsonl:25` | Stichprobenglück; 2 Replikationen fielen auf +0,44 und +0,18 | gepoolt +0,69 ± 0,56 → **Rotation abgelehnt**, v2 demontiert (`journal.jsonl:28`) |
| `turn_wert` „+1,64 ± 4,03 / getrimmt 0,00 → NEUTRAL" | `journal.jsonl:52` | **Estimator v1**: der 5 %-Trim entfernte bei 8,4 % divergenten Decks exakt die Signal-Decks | Estimator v2 (rohes Mittel ± 2 SE) → +9,39 / +10,78, Pool +7,27 ± 2,33 (`stats.py:20-33`) |
| `sel_m15` „+10,50 ± 2,10" als Punktschätzer | `journal.jsonl:36` | 3 Sigma über der Replikation → Fat-Tail-Heterogenität, nicht Rauschen | gepoolt +3,94 ± 0,95 (`journal.jsonl:41`) |
| envgate `prince` „−68,64" | `20260817_201814_envgate/result.json` | **Kanal-Artefakt**: exploit-OFF-Arm gegen einen ausbeutbaren Gegner; kein Bot-Urteil | keine Ersatzzahl — PRINCE gehört auf die GTOW-Achse (`journal.jsonl:60`) |
| A/A r10_stack „−9,40 ± 10,92" | `20260907_213225_pargate_r10_stack/result.json` | Bug `hand_id = 2*deck+half` → verschiedene private Seeds je Spiegelhälfte | A/A 576 exakt 0 nach Fix (3×) |
| A/A Kaggle „−37,5" | `data/runs/kaggle_aa_2026-09-10.log` | Bug: wiederverwendete Agenten aus einem RNG-Strom | A/A exakt 0 mit frischen Instanzen je Hälfte |
| „v3 +21,4 / v4 +49,8" als Bot-Stärke | `20260817_214458_envgate/result.json` | **envgate**-Zahlen (vs GTOBaseline), nicht mit pargate-Zahlen mischbar; Verdikte heißen seither `KANAL_*` | pargate-Pendant: v4-Kern vs basis +16,14 ± 2,77 |
| additive Erwartung „r8 vs basis ≈ +53" | Vorregistrierung | Selfplay ist **nicht transitiv** | gemessen +30,60 ± 5,03 (`journal.jsonl:92`) |

---

## 10. Was heute (2026-09-10) gilt

* **Champion HU = AUSLESE v5** (`r8_stack`, Tag `auslese-v5`, Commit ec11fde) — Kette
  `river_gpu_guard(river_wert_bremse(r6_button(turn_wert(sel_m15))))`, `pokerbot/strategy/auslese.py:4,34`.
  Belege sind **Spiegel-Evidenz**; v5 hat **keinen** eigenen GTOW-Anker (der einzige externe Anker ist v4-auf-
  PRINCE mit −21,1; `docs/STATE.md`).
* **v8 (r9_v8), v9 (r10_ernte) und v10 (r10_stack) sind NICHT geshipt.** v8 wegen Kanal-Sättigung (NEUTRAL),
  v10 wegen verfehlter Gates G2/G3 — der Spiegel-Gate G5 (+11,68 ± 10,85) hat es *nicht* gerettet.
* **6-max = Liga-Kern `tag` mit `flat_guard`** (Tag `sixmax-tag-flatfix-v1`, ≈ +16 bb/100 über 3 pargate6-Läufe);
  der Prince-Takeover ist refutiert und default AUS.
* **Exploit ist überall AUS** — 8/8 Liga-Profile ≤ 0, gepoolt ≈ −12 bb/100.
* **Bindende Mess-Doktrin aus diesen Läufen:** A/A-Nulltest vor jeder Reihe (muss EXAKT 0 sein, sonst STOPP);
  3-Läufe-Regel vor jeder Taufe; Kanalbreite VOR dem Bau vermessen; leiser Kanal (Kandidat vs Kandidat) schlägt
  lauten (vs Basis); Spiegel = Nichtverschlechterung, Adversar = Härtungs-Beweis; envgate-Zahlen sind nie
  Ship-Evidenz; ungeseedete MC bricht Paarungen; eine Worker-Flotte zur Zeit.

---

## Snowie, Turnier, Multiway, Vision, Solver-Validierung

Diese Kanaele sind alle NEBENkanaele zum GTOW-AIVAT-Anker und messen jeweils etwas anderes:
**PokerSnowie-Bruecke** = ein echter externer Gegner ueber Bildschirm-Erkennung — sie misst reales Geld
gegen ein fremdes Netz, aber ohne Showdown-Logging und damit ohne AIVAT (roh, hochvarianz, plus eine
"Automatisierungs-Steuer" durch Erkennungs-/Klick-Fehler); **Snowie als Grader** liefert die Meinung eines
DRITTEN Range-Modells je Entscheidung (Hypothesen-Quelle, nie Gate — Snowie ist der nachweislich
schwaechere Schiedsrichter). **Turnier/ICM** misst ROI/Platzierungs-Leiter in einer eigenen Simulation
gegen die eigene Liga — es kann Arm-Deltas (ICM an/aus, Druck an/aus) auf gepaarten Seeds zeigen, aber
keine absoluten Turnier-Winrates gegen echte Felder. **Multiway/6-max** misst im gepaarten 6-max-Spiegel
(pargate6) gegen die eigene Liga — Selbst-Oekologie, kein externer Anker (der ist der GTOW-Analyzer-Grade).
**Vision-Regression** misst NICHT Poker, sondern ob der Bildschirmleser konservierte Standbilder korrekt
liest (binaer, deterministisch). **Solver-Validierung** misst Code gegen Code/Mathematik (exakte
Enumeration, geschlossene Toy-Loesungen, TexasSolver als Zweitmeinung) — sie beweist Korrektheit der
Rechnung, NIE dass die gespielte Strategie Geld verdient. **Laufzeit** ist reine Mechanik.

---

### 1. PokerSnowie-Bruecke (Live-Vision-Kanal, echtes Konto gegen fremdes Netz)

| Datum | Was gemessen | Instrument/Kanal | Ergebnis (Zahl ± Streuung, n) | Verdikt | Quelle (datei:zeile) | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-08-04 | Durchsatz + Ausfallrate der vollautomatischen Bruecke | `pokerbot/vision/snowie_bridge.py` gegen PokerSnowie 4 | 13,3 Haende/min, ~4 % Aussetzer, beide Themes (dark/bright) | produktionsreif | docs/STATE.md:421-423 | ja (Code unveraendert im Repo) |
| 2026-08-04 | Kontostand ueber 3 Marathon-Laeufe | Snowie-Bruecke, roh | 3.651 Haende roh, Konto **−$2.915** | roh NEGATIV, aber nicht Bot-Verdikt | docs/STATE.md:426 | ja als Rohzahl; die Verlustursachen sind abgedichtet (s. u.) |
| 2026-08-04 | Winrate im bereinigten Pool | Snowie-Bruecke, nach Ausschluss der Automatisierungs-Fehlerklassen | **+3,2 bb/100, 95 %-Band [−37, +44]** (n=3.114 saubere Haende) | ≈ break-even vs Snowie; Band viel zu breit fuer ein Verdikt (±20 braeuchte ~13k Haende) | docs/STATE.md:426-427, 437-438 | ja als bester Snowie-Anker; NICHT signifikant |
| 2026-08-04 | Zuordnung der drei Lauf-Verluste | Einzel-Obduktion je Lauf | L1 = 46 % Aussetzer (833 Zwangs-Folds) · L2 = Ueber-Stack-Raise-Schleife (Snowie lehnt still ab) · L3 = 13 Fantasie-Pot-Jams (Dezimalpunkt-Verlust ×100) | alle drei Klassen abgedichtet (All-in-Preset + Wiederholungs-Waechter + Chip-Erhaltungs-Invariante) | docs/STATE.md:428-431 | ja — die Fixes sind im Code; ein sauberer Lauf 4 zur Bestaetigung steht AUS |
| 2026-08-04 | AIVAT gegen Snowie moeglich? | Methodik-Pruefung | **nein** — kein Showdown-Logging, keine eigene Wertfunktion im Pfad; Leiter definiert (Showdown-Logger → All-in-Gluecksbereinigung → MIVAT-light) | strukturelle Grenze | docs/STATE.md:436-437 | ja, unveraendert offen |
| 2026-08-04 | Prince-Verdacht "Turn-Monster-Checks = Leak" | Offline-Experiment mit fortgesetztem Spielbaum | Check ist bewusste Check-Raise-Falle; 2. Zug raist/bettet — identisch bei duenner und voller Historie | Freispruch (kein Leak) | docs/STATE.md:435-436 | ja |
| 2026-08-04 | Preflop-Rollenmodell in der Bruecke | User-Einwand + Nachbau | Prince-HU uebernimmt NUR postflop; preflop 6-max-Positions-Prior (`make_seeded_tracker`: UTG 194 → BTN 552 Combos statt HU-1102) | Korrektur angewendet (HU-Projektion haette MP-Opens als ~50 %-Range gelesen) | docs/STATE.md:423-425 | ja |

### 2. Snowie als externer GRADER (400 gepaarte Haende, alle Blunder einzeln durchgeklickt)

| Datum | Was gemessen | Instrument/Kanal | Ergebnis (Zahl ± Streuung, n) | Verdikt | Quelle (datei:zeile) | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-08-17 | Blunder-Verteilung von AUSLESE v1 | PokerSnowie-4-Grading, 400 exportierte Haende, Gate-Paritaet (Resolver OFF) | 39 Blunder: C zu lose Call-Downs **15** · B verpasster Wert/zu passiv **11** · A Ueberaggression mit starken Haenden **9** · D zu enge Folds **3** | Hypothesen-Quelle; groesste Klasse = genau der Mechanismus, der v1 seine +6,1 bb/100 brachte (Dosis zu hoch) | docs/SNOWIE_BLUNDER_ANALYSE.md:12-19 | ja als Diagnose; die Doktrin daraus ist gemessen bestaetigt (Margen-Sweep) |
| 2026-08-17 | Call-Frequenz Flop, Basis vs v1 | Snowie-Triangulation, 400 gepaarte Haende | Basis callt **53 %** der Snowie-Empfehlung, v1 **195 %** | beidseitig daneben → Margen-Sweep als Kandidat | docs/STATE.md:292-295 | ja (fuehrte zu sel_m15) |
| 2026-08-17 | Traegt die Snowie-Richtung im eigenen Gate? | gepaartes Self-Play-Gate (leiser Kanal vs v1), je 25k Decks | m06 +0,06±1,45 NEUTRAL · **m10 +5,64±1,74** · **m15 +10,50±2,10** (monotone Dosis-Wirkung) | Snowies "3pp zu locker" dreifach bestaetigt und quantifiziert | docs/AUTOGYM_PLAN.md:116-118 | ja — m15 ist Teil der Versionskette |
| 2026-08-17 | Mehrstrassen-Disziplin (Snowie-Ableitung 2) | gepaartes Gate | `einmal_guard` +0,41±1,05 | **NEUTRAL — Familie verworfen** (die strengere Marge loest es besser) | docs/AUTOGYM_PLAN.md:121-122 | ja (negatives Ergebnis) |
| 2026-08-17 | Ist Snowie ein gueltiger Richter? | Methoden-Kritik + Repo-Historie | Snowie unterstellt seine EIGENE balancierte Villain-Range, gespielt wurde gegen unseren Basis-Bot; Engine vs Snowie ≈ break-even, vs GTOW −19,7 → Snowie ist der schwaechere Referee | **Blunder-Liste ist NIE Gate**, nur Hypothese | docs/SNOWIE_BLUNDER_ANALYSE.md:60-66 | ja, bindend |

### 3. Turnier / ICM

Der Kanal: gepaarte SNG-/MTT-Simulation gegen die eigene Bot-Liga, Arm A vs Arm B auf identischen Seeds.
Er misst ROI-/Ladder-DELTAS zwischen Doktrin-Varianten; Absolutwerte sind modellabhaengig (Feld = Prior).

| Datum | Was gemessen | Instrument/Kanal | Ergebnis (Zahl ± Streuung, n) | Verdikt | Quelle (datei:zeile) | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-08-04 | ICM-Rechnung selbst | `tests/test_icm.py` — exakte Malmuth-Harville-Bitmask-DP gegen eine UNABHAENGIGE Permutations-Enumeration (anderer Algorithmus) | alle Tests bestanden, tol 1e-9; Beispiel 50/30/20 → [38,39 · 32,75 · 28,86] | exakt validiert | tests/test_icm.py:1-6; **heute nachgelaufen (2026-09-10): "ICM: alle Tests bestanden"** | ja, heute reproduziert |
| 2026-08-04 | μ-1: voller Bubble-Faktor auf JEDEN Call | gepaarte SNG-Arena, ICM an vs aus | **−8,1 ± 13,9 pp ROI**, Ueberstraffungs-Muster (mehr 4., weniger 1.) | **REFUTIERT** — Doktrin-Fix erzwungen | docs/STATE.md:402-404 | ja (negatives Ergebnis, Grund fuer das anteilige Premium) |
| 2026-08-04 | μ-2: anteiliges Risiko-Premium BF_eff = 1+(BF−1)·(to_call/Stack) | gepaarte SNG-Arena, n=500 | **+9,2 ± 8,0 pp ROI** (ICM-an +18,4 % vs aus +9,3 %); Fingerabdruck 2.-Plaetze 71 vs 47 | positiv, noch nicht signifikant | docs/STATE.md:404-405 | ja |
| 2026-08-04 | μ-3: Replikation des anteiligen Premiums | gepaarte SNG-Arena, 1500 Paare, 6 Worker | **+10,02 ± 5,03 pp ROI**, 95 %-Band [+0,2, +19,9], z=1,99; MEHR Siege (214 vs 192) UND bessere Ladder | **VALIDIERT** (Dominanz auf beiden Metriken) | docs/STATE.md:405-406 | eingeschraenkt — s. naechste Zeile (Engine-Defekte) |
| 2026-08-04 nacht | Engine-Korrektheit unter den μ-Messungen | 15-Agenten-Review + Engine-Fuzz, `tests/test_mtt.py` konserviert | 6 bestaetigte Defekte: Ante als Street-Einsatz · **HU-Blind-Inversion in table.py** (Button postete BB) · verwaiste Side-Pot-Schicht (Chips vernichtet) · Hero-Initiative-Flag (seat=0 fix → ~5/6 Haende falsch) · All-in-durch-Antes-Loch · ICM-All-in-Schwelle | alle gefixt | docs/STATE.md:361-368 | ja — **VORBEHALT: alle frueheren SNG-Absolutwerte (μ-3 etc.) liefen auf der Engine MIT (1)–(3); Arm-Deltas gelten als robust, Absolutwerte verschieben sich** (docs/STATE.md:368-370) |
| 2026-08-04 | Druck-Hebel gegen ein FREQUENZ-Feld (Duell 1) | gepaarte SNG-Arena | 92 % Siege = Decken-Effekt | **uninformativ** (Feld zu schwach) | docs/STATE.md:407-409 | ja (negatives/verworfenes Design) |
| 2026-08-04 | Druck-Hebel gegen ein ICM-SPIELENDES Bot-Feld (Duell 2) | gepaart, n=300/Arm | chipEV **+6,6** · icm **+7,7** · icm+druck **+14,1 % ROI**; Druck fuehrt auf jeder Metrik (P1. 21 % vs 18 %, ITM 36,3 %); +7,5 pp vs chipEV, **z=0,76** | Ordnung klar, Signifikanz braucht ~2k Paare; **defensive ICM-Brille gegen ICM-Feld ≈ wertlos (+1,1)**; Fee (~4,8 pp) nicht abgezogen | docs/STATE.md:409-412 | ja, als Ordnungs-Aussage; nicht signifikant |
| 2026-08-04 | 2×2-Zerlegung Druck × Reads (Confound-Fix, identische Seeds) | gepaarte SNG-Arena | Druck traegt (**+4,7 allein, +6,4 gebuendelt**); **Reads allein SCHADEN im Turnier: −13,9 ± 10,7 (z=−1,3)** | Reads bleiben im Turnier aus | docs/STATE.md:412-415 | ja |
| 2026-08-04 | Reales PS-$1050-Feld (Gegner-Verhalten) | `research/ps_tourney_field.py`, gemintes Feld, 2.055 Haende | deep-Phase VPIP 31,7 / PFR 20,4 / 3bet 10,2 / FoldVsRaise 53,6 %; unter Druck **FoldVsRaise 54→62 %, Jam 1,1→13,1 %** | ICM-Zwangs-Tightness empirisch belegt (Grundlage des Druck-Hebels) | docs/TURNIER_MODUS.md:35-41 (Datei `data/ps_tourney_field.json`) | ja |
| 2026-08-04 nacht | $1050/600-Entries-MTT-Szenario des Users | `research/mtt_sim.py`, gepaart, konservative Klammer (Bot-Kerne an Heros Tisch), n=960 | **ROI −28/−32 %, ITM 7,5 % (½ Basis), P(1.) 0,2–0,4 % (1,3–2,5× Basis)** = Chip-Accumulator-Profil; 27 % Busts in den ersten 2 Leveln bei 220 bb; Druck-Hebel ohne Signal (−4,0 ± 18,9, z=−0,2) | Design asymmetrisch unfair (nur Heros Tisch hart) → **Untergrenze**, kein Verdikt | docs/STATE.md:369-373 | ja als Untergrenze; Hauptmessung (3000 Paare) wurde vom User abgebrochen |
| 2026-08-04 nacht | Turnier-Varianz (aus der exakten Payout-Leiter) | analytisch aus der Sim | SD 5,4–9,7 Buy-ins/Turnier (steigt mit Skill); 85 % Nuller; bei +65 % ROI: P(nach 100 Turnieren im Minus)=23 %, Max-DD p50/p99 = 27/60 BI, ~140 BI fuer 5 % Ruin | Bankroll-Doktrin | docs/STATE.md:373-376 | ja |
| 2026-08-04 | 13.016-Chip-Defizit (Verdacht auf Engine-Leck) | Reproduktions-Versuch, ~325 volle Turniere + 235k Haende | im committeten Code **NICHT reproduzierbar** (chip-exakt); Taeter mit gemessenem Fit = Defekt (3) verwaiste Side-Pot-Schicht (~1/30 Turniere, Groessen 267–26.144) | geschlossen + Tripwire (Refund statt Vernichtung, Chip-Erhaltung je Hand) | docs/STATE.md:377-382 | ja |
| 2026-09-09 | MTT-Trainer-Modus: Nebentisch-Kosten | `tests/test_tournament_mode.py`, volles Feld, 20 Runden | 5 Tische je Hero-Hand **mean 120–129 ms, max ≈ 200–213 ms** (Journal: mean 121 / max 216) | unter dem 300-ms-Ziel → `side_tables_every=1` | docs/TURNIER_MODUS.md:100-103; data/autogym/journal.jsonl (TURNIER-MODUS-BUILD, 2026-09-09 20:13:34) | ja |
| 2026-09-09 | MTT-Direktor-Invarianten | Bots-only bis zum Sieger, Seed 7, Audit jede Runde | 131 Runden, 38,8–40,1 s; Chip-Erhaltung 60·5000 nach jeder Runde; jeder Platz 1..60 genau einmal; Balance ±1; Determinismus Seed 11 zweimal identisch, Seed 12 ≠ 11 | 7 (spaeter 8) Tests gruen | docs/TURNIER_MODUS.md:104-108 | ja — `python -m tests.test_tournament` heute nachgelaufen: "TURNIER: alle Tests bestanden" |
| 2026-09-09 | Turnier-Modus: Hand-Kontinuitaets-Bug (User-QA) | TestClient-Reproduktion | jede Turnierhand war eine frische `Table` mit hand_no 1 → `_log_if_done` uebersprang ALLES nach Hand 1 (keine Stack-Rueckgabe, keine Busts, Feedback eingefroren) | gefixt + `test_hand_continuity`; Nachmessung 2 volle Turniere (Seeds 3/11: 6 bzw. 31 Haende), Browser-Schnelllauf 3.671 Renders, 0 leere Tische | docs/TURNIER_MODUS.md:118-125 | ja |
| 2026-09-09 | Turnier-Modus: "leerer Tisch" | Browser + TestClient | Turnier-bb 50 → Slider 187,5 Chips → `ActionReq.amount: int` → FastAPI-422 ohne `error`-Schluessel → Client renderte die Fehlerantwort als Spielzustand | 3-Schicht-Fix + `test_fractional_amount_is_rounded` | docs/TURNIER_MODUS.md:126-132 | ja |
| 2026-09-09 | Feldtempo im Trainer-MTT | Beobachtung im Lauf | 60 → ~30 Spieler in ~25 Runden (Maniacs/Whales gehen bei 100 bb frueh all-in) | praktisch fuer Training, **schneller als ein echtes Online-MTT** (Modell-Grenze) | docs/TURNIER_MODUS.md:133-134 | ja |

### 4. Multiway / 6-max

Der Kanal `pargate6` ist ein gepaarter 6-max-Spiegel (Hero rotiert ueber alle 6 Sitze je Deck) gegen die
eigene Liga — er kann Kandidat-vs-Incumbent-Deltas messen, aber nichts Absolutes: `tag` spielt "zu Hause".

| Datum | Was gemessen | Instrument/Kanal | Ergebnis (Zahl ± Streuung, n) | Verdikt | Quelle (datei:zeile) | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-08-17 | 6-max-Positions-Ledger + Facing-Katalog v0 | Self-Play-Gym 6-max, 30k Haende / 298k gegradete Entscheidungen | Positionen bb/100: **BTN +33,5 · HJ +15,8 · UTG +6,8 · CO +2,4 · BB −28,9 · SB −29,6**; fold_freq Flop **0,216** / Turn 0,297 / River 0,337 bei mittleren Bets 0,431/0,384/0,365 Pot (Knoten 21.165/11.565/8.143) | Ordnung plausibel; **Flop-Fold UNTER der MDF-Erlaubnis (0,30 bei 0,43-Pot-Bets) → KEIN 6-max-Flop-Overfold; der HU-Flop-Overfold ist HU-spezifisch** | data/autogym/journal.jsonl (RUNDE4-6MAX-KATALOG, 2026-08-17 12:55:05); docs/AUTOGYM_PLAN.md:123-127 | ja — und bindend: blinde Uebertragung von `sel_guard` auf 6-max ist NICHT indiziert (docs/STATE.md:279-281) |
| 2026-09-09 | Prince-Takeover in HU-kollabierten 6-max-Poetten | `pargate6`, je 2992 Decks, Incumbent = Liga-Kern `tag` | hybrid **−23,56 ± 9,02** CI[−40,8;−5,3] · hybrid_r8 **−21,73 ± 9,01** · hybrid_r10 **−26,61 ± 8,93** · hybrid_r8 vs hybrid +1,82 ± 5,58 NEUTRAL | **alle VERWERFEN** — der HU-Bot schadet im 6-max-Pott; bester gemessener 6-max-Bot ist `tag`. Takeover default AUS | data/autogym/journal.jsonl (VERDRAHTUNG-6MAX-VERDIKT, 2026-09-09 19:26:50); docs/STATE.md:50-53 | ja |
| 2026-09-09 | A/A-Nulltest des neuen 6-max-Kanals | `pargate6`, tag vs tag, 288 Decks | **EXAKT 0** | Kanal sauber | data/autogym/journal.jsonl (VERDRAHTUNG-6MAX-VERDIKT) | ja |
| 2026-09-09 | Dirichlet-River-Exploit ON vs OFF | `pokerbot/autogym/exploit_gate.py`, 600 gepaarte Decks je Liga-Profil, Fingerprint verifiziert | Diff ON−OFF: nit −2,1±9,5 · tag −19,3±15,4 · lag −18,5±13,0 · station −17,4±16,3 · maniac −15,7±9,6 · rock −0,3±9,0 · whale −8,3±17,0 · shark −14,4±13,7 → **alle ≤ 0, gepoolt ≈ −12 bb/100 (SE ~4,5)**; 6-max-Reads ON vs OFF +3,6 ± 13,5 NEUTRAL | **REFUTIERT** — Exploit bleibt in allen Modi AUS | data/autogym/journal.jsonl (EXPLOIT-GATE-VERDIKT, 2026-09-09 19:26:50); docs/STATE.md:54-56 | ja |
| 2026-09-09 | 6-max FLAT-FIX (`flat_guard`: dominierte Offsuit-Broadways nie vs Open flatten) | `pargate6`, 3 Laeufe à 2992 Decks vs altem `tag` | **+17,7 ± 6,4** (ANWENDEN, perm_p 0,0035) · **+11,36 ± 6,88** (NEUTRAL, p 0,057) · **+19,18 ± 7,01** (ANWENDEN, p 0,0035); gepoolt ~+16 bb/100 | ANGEWENDET auf `PROFILES["tag"]` (Liga, Berater, Turnier); Tags `sixmax-tag-pre-flatfix` / `sixmax-tag-flatfix-v1` | data/autogym/journal.jsonl (FLATFIX-6MAX-VERDIKT, 2026-09-09 21:54:18); docs/STATE.md:24-30 | ja — **offen: externer Anker (Analyzer-Export des NEUEN tag) fehlt** |
| 2026-07-04 | Externer absoluter 6-max-Grade | GTOW-Analyzer ueber `research/sixmax_export.py`, n=1500 | **GTO-Score 85,9 %, EV-Loss 7,61 bb/100** (vs HU 53,4 % / Freq-Diff 54,6 %) | der einzige EXTERNE 6-max-Anker; bezieht sich auf den `tag`-Kern VOR dem Flat-Fix | docs/STATE.md:52 (Wiederholung CLAUDE.md:88-91) | teilweise — Kern hat sich seither geaendert (Flat-Fix), der Grade ist NICHT nachgemessen |
| 2026-08-04 | Multiway 7–10 Sitze | `engine/table.py` (POS_LABELS 7–10, stacks=/ante=/rebuy=), sixmax-Buckets NUR fuer neue Labels; Trainer `?players=9` | 6-max-Pfad **byte-identisch** (Anker-Schutz); Trainer TestClient-verifiziert fuer 6/8/9 Sitze | gebaut + verifiziert (Mechanik, kein EV-Verdikt) | docs/STATE.md:399-401 | ja |

### 5. Vision-Erkennung (Regressionsnetz, Frame-Audit)

| Datum | Was gemessen | Instrument/Kanal | Ergebnis (Zahl ± Streuung, n) | Verdikt | Quelle (datei:zeile) | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-08-04 | Erkennungs-Regression auf konservierten Tatorten | `python -m research.snowie_regress --run`, 5 Standbilder beider Themes | **5/5 bestanden** | Gate fuer jede Vision-Aenderung | docs/STATE.md:431-432; research/snowie_regress.py:1-9 | **ja — heute (2026-09-10) nachgelaufen: 5/5 bestanden** |
| 2026-08-04 | Frame-Rekorder-Audit | aufgezeichnete Frames gegen erkannten Zustand | **27/28 frame-exakt** | 1 Abweichung dokumentiert, nicht ausgeraeumt | docs/STATE.md:432-433 | ja |
| 2026-08-04 | Erkenntnis-Ladder der Bilderkennung (Fehlerklassen) | Bruecken-Entwicklung | $-Zeichen wird zur OCR-Ziffer (vor OCR wegschneiden) · Margin-Regel + Konvergenz (zweideutig → Datei → Vorlage) · Zweitquellen-Pot mit Suffix-Signatur + OCR-Schiedsrichter · Zeilen-/Polaritaets-Adaption | Haertungs-Doktrin: NIE mit falschen Zahlen rechnen; Chip-Erhaltung als Gatter | docs/STATE.md:433-435; CLAUDE.md:190-193 | ja |
| 2026-08-04 | Nicht-gemessen: universeller VLM-Tischleser | `pokerbot/vision/screen_reader.py` (VLM, beliebige Seite, ~<1 ct/Frame, watch mode) | gebaut, **keine Genauigkeits-Messung im Repo gefunden** | ungemessen | docs/STATE.md:1068 | offen — vor Einsatz messen |

### 6. Solver- und Mathematik-Validierung

Dieser Kanal beweist RECHEN-Korrektheit (gegen exakte Enumeration, geschlossene Loesungen, Zweit-Solver).
Er sagt nichts ueber die Profitabilitaet der gespielten Strategie — die Konsult-Notiz dazu ist explizit:
r=0,999 zwischen zwei Solvern heisst nur, dass die Kerne bei gleichen Inputs uebereinstimmen.

| Datum | Was gemessen | Instrument/Kanal | Ergebnis (Zahl ± Streuung, n) | Verdikt | Quelle (datei:zeile) | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-08-30 | 7-Karten-Evaluator auf GPU | `pokerbot/engine/gpu_eval.py` gegen treys-Ordnung | **16,8 Mio Haende/s; 250k Ordnungs-Paare 0 Fehler** | validiert; Lehre: CUDA-`log2` 1-ulp-Falle → integer-only | docs/STATE.md:115-117; data/autogym/journal.jsonl (R8-GPU-RESOLVER, 2026-08-30 20:20:24) | ja |
| 2026-08-30 | Batch-Equity auf GPU | `gpu_equity.py` gegen CPU-Enumeration | River **byte-identisch** zur CPU-Enumeration; Flop 1081×1081 exakt in **0,087 s** | exakt | docs/STATE.md:117 | ja |
| 2026-08-30 | CFR+-Korrektheit an einem Spiel mit bekannter Loesung | `pokerbot/strategy/gpu_cfr.py`, Clairvoyance-Toy | **Bluff 0,333 / Call 0,500 exakt getroffen; Exploitability 0,014 %** | exakt | docs/STATE.md:118-119 | ja |
| 2026-08-30 | Kreuzvalidierung gegen den unabhaengigen OSS-Solver | `research/gpu_vs_texassolver.py`, identischer Spot | Frequenz-Deltas **0,007 / 0,000 / 0,001**; **per-Combo-Korrelation r = 0,999** | zwei unabhaengige Solver einig | docs/STATE.md:120-122 | ja — **aber ausdruecklich KEIN Aussagewert ueber die live gespielte Politik** (docs/TOP5_KONSULT_GPT6_2026-09-07.md:186, :4302) |
| 2026-08-30 | GPU-Auslastung / Solve-Kosten | `RiverCFRBatch` B=256 | **100 % GPU-Auslastung**, ~1000 Subgame-Iter/s, **0,30 s/Spot**; bandbreiten-bound, TF32 wirkungslos | Live-tauglich am River | docs/STATE.md:119-120 | ja |
| 2026-08-30 | Solver-Audit der eigenen River-Entscheidungen | `gpu_river_audit.py` ueber 571/571 River-Entscheidungen der GTOW-Nacht 2 | check/fold solver-konform (p 0,86 / 0,83); **bet ist die schwaechste Klasse (p 0,45; 15 % klare Widersprueche)**; Desaster-Calls kriegen Solver-fold p>0,95 | Lokalisierung des River-Leaks auf die BET-Seite | docs/STATE.md:123-126 | ja (Grundlage von `river_wert_bremse`) |
| 2026-08-30 | Tragen die Tracker-Schwellen die River-Defense? | Trennschaerfe-Messung | **0,65 vs 0,53** | NEIN — erklaert, warum `r6_ecall` starb | docs/STATE.md:126-127 | ja (negatives Ergebnis) |
| 2026-06-21 | Ist unser eigenes Oracle grob kaputt? | `research/gtow_oracle_check.py` gegen 7.565 geloggte GTOW-Haende | Preflop-Blueprint **93,8 % der echten GTOW-Aktionen im Support** (n=6.203); Postflop-Solver **90,1 % in-support, 64 % modal, mean-prob 0,62** (n=172, 96 % Solve-Abdeckung); Schwachstelle **Turn: 86 % in-support, nur 47 % modal** | Oracle ist NICHT grob kaputt → ein spekulativer Postflop-Solver-Umbau war NICHT gerechtfertigt | docs/STATE.md:1141 | ja — CAVEAT im Original: grob (Aktions-FAMILIE, nicht Sizing/Frequenz; n=172 ±~5 %) |
| 2026-08-17 | Flop-Resolver Erstflug | 5 Haende `PokerBot(use_flop_resolver=True)` vs GTOBaseline, `duplicate.py`-Muster, gen_decks(5, seed=7) | **Resolver feuerte 0 von 3 mal**; Cold-Solves 75,4 s / 89,3 s / 120,9 s (Timeout); erreichte Exploitability 8,47 / 8,67 % of pot (Ziel-acc 0,6 weit verfehlt); die zwei konvergierten Solves gaben trotzdem None: **Hero-Combo nicht in der eigenen 35-Klassen-Range** (K5o/J8o) | Baustelle: jeder Flop-Resolver-A/B misst aktuell nur den Floor plus 75–120 s Latenzsteuer | data/runs/verdrahtungs_debug_2026-08-17.json:4 | ja, unveraendert offen |
| 2026-09-10 (heute) | Formel-/Identitaets-Suite | `python -m tests.test_math_suite` | **20/20 checks passed, fuzz N=400/check** (u. a. Pot-Odds exakt, alpha/MDF, required_fold_equity gegen unabhaengige Fraction-Loesung, Bluff-to-Value-Indifferenz, exakte River-Equity vs unabhaengige treys-Enumeration, MC-Turn-Equity innerhalb 5·SE, **Chip-Erhaltung inkl. Side-Pots ueber 120 zufaellige 6-max-Haende**) | gruen | heutiger Lauf; Struktur tests/test_math_suite.py:23-40 | ja — **die in CLAUDE.md:32 zitierten "17/17 deep" sind ueberholt: heute 20/20** |
| 2026-09-10 (heute) | Abdeckung der Formel-Bibliothek | derselbe Lauf, Abschnitt "UNVERIFIED formula functions" | **69 Formelfunktionen ohne unabhaengige Referenz** (u. a. `equity_realization`, `expected_value`, der gesamte `strategy_formulas`-Block) | offene Luecke, ehrlich ausgewiesen | heutiger Lauf von tests/test_math_suite.py | ja |
| 2026-08-17 | Referenz-Integritaet der Formel-Zitate | `verify_refs` | **66/66** | gruen | docs/STATE.md:302; Erwartung dokumentiert docs/POD_PLAN.md:58 | ja (nicht nachgelaufen) |
| 2026-07-05 | EVPA-Arm-Pruning (geometrischer Transfer) gegen TexasSolver | Vergleichsmessung | **NO-OP** — der Solver kollabiert Ueber-Allin-Arme intern, ε identisch zu 1e-8 | negativ; als v4-Baustein behalten, Census-Frequenz-Pruning bewusst NICHT gebaut | docs/STATE.md:822-825 | ja (negatives Ergebnis) |

### 7. Laufzeit / Durchsatz

| Datum | Was gemessen | Instrument/Kanal | Ergebnis (Zahl ± Streuung, n) | Verdikt | Quelle (datei:zeile) | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-07-05 | `decide()`-Latenz nach Memoisierung | Profil + Byte-Identitaets-Gate (0 Diffs ueber 6 Arme × 70 Spots) | **999 → 83 ms = 12,1×** (proven-pure Memoisierung von p_bet/p_defense/hand_features/evaluate + `_straight_outs`) | angewendet (Commit 114e107) | docs/STATE.md:816-819 | ja — Praezisierung: `decide()` selbst ist NICHT memoisiert, memoisiert sind `advisor.p_bet/p_defense`, `features._FEATURES_MEMO`, `evaluator._EVAL_MEMO`, Wholesale-Clear bei 120k/60k (docs/V10_FAKTEN.md:103-105) |
| 2026-07-05 | Determinismus-Wurzelbefund | 3 Prozesse, gleicher Seed | `combos_for_classes` iterierte ein String-SET → PYTHONHASHSEED-abhaengige Combo-Reihenfolge → **4/140 MC-Grenzentscheidungen kippten**; separat gemessen: Platz 378/12/4 bei identischem Seed | `sorted()` am Chokepoint; **alle frueheren "deterministischen" Instrumenten-Laeufe trugen diesen Jitter** | docs/STATE.md:819-822; docs/STATE.md:383-388 | ja — Paarungen bleiben gueltig (symmetrisch) |
| 2026-08-16 | Self-Play-Durchsatz single-process | Autogym-Pilot | 500 Haende + 3.577 gegradete Entscheidungen in **52 s (~580 Haende/min)** | Basis fuer die Pod-Rechnung | docs/AUTOGYM_PLAN.md:45 | ja |
| 2026-08-16 | Multiprocessing-Skalierung lokal | `pargate`, 24 Kerne, 40 min | **2.459 Decks/min (~4.900 Haende/min)**, Skalierung ~1,0×/Kern | G5 BESTANDEN → fuer Einzel-Gates ist der Pod unnoetig | docs/AUTOGYM_PLAN.md:133-134 | ja |
| 2026-08-16 | Advisor-Inferenz GPU vs CPU | Mikro-Benchmark, Batch 1300×20 | GPU **3,20 ms** vs CPU **3,52 ms** — Launch+Transfer fressen den Gewinn | **Live-Inferenz bleibt CPU**; GPU bekommt die Massen-Jobs | docs/GPU_PLAN.md:3-8 | ja |
| 2026-08-17 | Advisor-Batching auf CPU | Profil der Live-Schleife | **2,2×** (Batch-1-Overhead beseitigt) | angewendet | docs/STATE.md:303; docs/GPU_PLAN.md:5-6 | ja |
| 2026-08-31 | fp16 im GPU-River-Solver | Messung der `half=True`-Option | **+64 %** Durchsatz | gemessen, **default OFF** | docs/STATE.md:147 | ja |
| — (Code-Fakt, 2026-09-07 auditiert) | River-Resolver-Latenz live | `bot.py`/`resolver.py`-Audit + STATE-Referenz | **~6 s je River-Entscheidung (Median 5,8 s)**; resolver-OFF 83 ms; Resolver feuerte 93 % der River-Entscheidungen; TexasSolver-Timeouts River 90 s / Turn 150 s / Flop 240 s (Census) | Live-Kosten des Solvers | docs/V10_FAKTEN.md:77-86 | ja |
| 2026-09-07 | v10 vs v5 Live-Latenz | `research/v10_latenz`, n=10 identische Zustaende (reduzierte Stichprobe) | Gesamt-p99 **v10 7,55 s vs v5-H 5,54 s**; K2-Trace: Plan gespielt 1/10, deadline 7/10, hand_not_in_range 2/10 | **G2 NICHT GRUEN**; nach Mechanik-Fix (3 Threads, 3 s Queue, 12 s Deadline) n=40: deadline 0/40, Plan 25/40, offtree 11/40, p99 10,15 s; Vollmessung n=150 **nicht gelaufen** | docs/STATE.md:72-76 + Nachtrag 02:05 | ja (offen) |
| 2026-09-08 | Export-Durchsatz im PRINCE-Live-Kanal | G5-Analyzer-Export | **11,6 s/Hand** (TexasSolver-Waits) → Export 200 statt 1500 Haende; 500er nach 98 Haenden abgebrochen | Analyzer-SE dadurch ≈ 2,7× breiter → nur Mechanik-/Tail-Grade, KEIN EV-Loss-Vergleich | docs/V10_GATES_REPORT.md:40 | ja |
| 2026-08-02 | Trainer-Grading-Budget | Integrationstest des Coach-Pfades | Prewarm liess den ersten `decide()` kalt: **1,6 s** von 800 ms Budget → nach Fix (Wegwerf-Record) **erste Hand 7,8 ms** | gefixt; Restrisiko bei uvicorn-Importstring ohne `main()` dokumentiert | docs/STATE.md:493-495; docs/TRAINER_PLAN.md:431 | ja |
| 2026-08-04 | Snowie-Bruecken-Durchsatz | s. Abschnitt 1 | 13,3 Haende/min | — | docs/STATE.md:422 | ja |
| 2026-09-09 | MTT-Nebentische | s. Abschnitt 3 | mean 120–129 ms, max ≈ 213 ms je Hero-Hand | — | docs/TURNIER_MODUS.md:100-102 | ja |

---

### Ausdruecklich veraltet / nicht mehr gueltig

* **"17/17 deep" fuer `tests/test_math_suite.py`** (CLAUDE.md:32) — **ersetzt**: der heutige Lauf meldet
  **20/20**; die Suite ist seit dem Zitat gewachsen. Zusaetzlich weist sie 69 unverifizierte Formelfunktionen aus.
* **Alle SNG-ABSOLUTWERTE vor 2026-08-04 nacht (μ-1/μ-2/μ-3 ROI-Niveaus)** — die Turnier-Engine trug damals
  drei bestaetigte Defekte (Ante als Street-Einsatz, HU-Blind-Inversion, verwaiste Side-Pot-Schicht). Die
  ARM-DELTAS gelten als robust (gepaart), die Absolutwerte verschieben sich (docs/STATE.md:368-370).
* **Snowie-Kontostand −$2.915** — als Bot-Verdikt ungueltig; er ist zu 3 abgedichteten Automatisierungs-
  Fehlerklassen zugeordnet (Aussetzer/Raise-Schleife/Dezimalpunkt). Gueltig ist der bereinigte Pool
  (+3,2 bb/100, Band [−37, +44], n=3.114) — und der ist nicht signifikant.
* **6-max-Analyzer-Grade 85,9 % / EV-Loss 7,61** — bezieht sich auf den `tag`-Kern VOR dem Flat-Fix vom
  2026-09-09; nach der Aenderung nicht nachgemessen (offener Punkt in docs/STATE.md:29-30).
* **`sel_guard`/AUSLESE-Guards auf 6-max uebertragen** — durch den 6-max-Katalog v0 vorab entkraeftet: es
  gibt dort keinen Flop-Overfold (0,216 bei erlaubten 0,30). Keine Messung, sondern ein verhinderter Fehlschluss.

---

## Welche Rohdaten liegen wo

Dieser Kanal ist kein Spiel-Kanal: er misst nicht bb/100, sondern **was physisch auf der Platte liegt** —
Groesse, Dateizahl, Format, Erzeuger-Code, Git-Status. Was er kann: sagen, welche veroeffentlichten Zahlen
sich aus vorhandenen Rohdaten **nachrechnen** liessen und welche nur noch als Behauptung in einem Dokument
stehen. Was er **nicht** kann: die Qualitaet oder Gueltigkeit dieser Zahlen beurteilen — eine grosse Datei
ist kein Beweis, und ein fehlender Rohdatensatz macht eine Zahl nicht falsch, nur unpruefbar.

Alle Groessen/Dateizahlen unten sind **am 2026-09-10 per Verzeichnis-Walk gemessen** (`os.walk`, Summe der
`st_size`), nicht aus Dokumenten uebernommen. Datei-Zeitstempel (mtime) geben die inhaltliche Zeitspanne an.

**Gesamtbild:** ~59,8 GB Rohdaten, davon **58,5 GB in zwei gitignorierten Baeumen** (`data/` 42,4 GB,
`models/` 16,1 GB). Versioniert (git) sind praktisch nur `knowledge_base/` (28,6 MB) und `dataset/` (72,5 MB,
davon Shards). Wer das Repo klont, erbt **~100 MB**; wer die Platte erbt, erbt ~59,8 GB. Das ist die
wichtigste Einzelaussage dieses Abschnitts.

---

### 0. Bestandsaufnahme oberste Ebene

| Datum | Was gemessen | Instrument/Kanal | Ergebnis (Zahl ± Streuung, n) | Verdikt | Quelle (datei:zeile) | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-09-10 | Gesamtgroesse `data/` | os.walk-Summe | 42,4 GB, n=91.002 Dateien, 40 Unterordner | gitignored, nicht klonbar | `.gitignore:8` (`data/`); Pfad `data/` | ja (Messung von heute) |
| 2026-09-10 | Gesamtgroesse `models/` | os.walk-Summe | 16,1 GB, n=214 Dateien, 11 Unterordner | gitignored | `.gitignore:12` (`models/`); `pokerbot/config.py:29` | ja |
| 2026-09-10 | Gesamtgroesse `tools/` | os.walk-Summe | 774,3 MB, n=24.655 (TexasSolver 156,0 MB/3.193 + gtow_client 578,8 MB/21.458) | gitignored, extern beschaffbar | `.gitignore:9` (`tools/`) | ja |
| 2026-09-10 | Gesamtgroesse `books/` | os.walk-Summe | 299,6 MB, n=56 Dateien | faktisch gitignored (`*.pdf`), nur 2 .txt getrackt | `.gitignore:13`; `git ls-files books` = 2 | ja |
| 2026-09-10 | Gesamtgroesse `dataset/` | os.walk-Summe | 72,5 MB, n=44; **42 Dateien git-getrackt** (inkl. Shards) | versioniert | `git ls-files dataset` = 42 | ja |
| 2026-09-10 | Gesamtgroesse `knowledge_base/` | os.walk-Summe | 28,6 MB, n=115; **103 Dateien git-getrackt** | versioniert | `git ls-files knowledge_base` = 103 | ja |
| 2026-09-10 | Gesamtgroesse `hand histories/` (Repo-Wurzel) | os.walk-Summe | 162,6 MB, n=80 (Days 8 / Historisch 72) | gitignored (Personendaten) | `.gitignore:37` (`hand histories/`) | ja |

---

### 1. `data/runs/` — Selfplay-Gate-Laeufe (pargate/envgate/pargate6)

**Kanal:** speichert je A/B-Lauf Konfiguration, Roh-Deck-Edges und Verdikt. Damit lassen sich μ, SE, Bootstrap-CI
und Permutationstests **komplett neu rechnen**, ohne den Lauf zu wiederholen. Was er nicht kann: nichts ueber
Live-Gegner (GTOW/Snowie) sagen — es sind reine Spiegel-/Liga-Zahlen.

| Datum | Was gemessen | Instrument/Kanal | Ergebnis (Zahl ± Streuung, n) | Verdikt | Quelle (datei:zeile) | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-09-10 | Umfang `data/runs/` | os.walk | 99,0 MB, n=605 Dateien; **91 Zeitstempel-Laufordner** (20260816_204232 … 20260909_215223) | vollstaendig, gitignored | `pokerbot/autogym/runs.py:17` (`RUNS = Path("data/runs")`) | ja |
| 2026-09-10 | Index-Abdeckung | Zeilen-Zaehlung | `INDEX.jsonl` = **79 Zeilen** bei 91 Laufordnern | **12 Laeufe ohne Index-Zeile** (exploit_jagd/runde-Kampagnen schreiben kein `result.json`) | `data/runs/INDEX.jsonl`; `pokerbot/autogym/runs.py:7` | ja |
| 2026-09-10 | Lesbarer Stand-Bericht | Zeilen-Zaehlung | `STAND.md` Tabelle = **22 Zeilen**, letzter Eintrag 2026-08-17, Nachtraege bis 2026-08-18 02:23 | **VERALTET** gegenueber INDEX (79) und Platte (91) — Generator seit 3 Wochen nicht gelaufen | `data/runs/STAND.md`; Generator `pokerbot/autogym/bericht.py:29` | nein — `python -m pokerbot.autogym.bericht` neu laufen lassen |
| 2026-08-17 | Beispiel-Laufinhalt (`20260817_222907_pargate_turn_wert`) | Dateiliste | 3 Dateien: `config.json` (207 B), `edges.json` (108.023 B = 29.920 Deck-Edges in Chips), `result.json` (372 B) | Format stabil; Roh-Edges vorhanden → Estimator austauschbar | `data/runs/20260817_222907_pargate_turn_wert/{config,edges,result}.json` | ja |
| 2026-09-09 | Neuestes Index-Schema | INDEX.jsonl letzte Zeile | 26 Felder inkl. `ci95_lo/hi`, `perm_p`, `boot_b`, `aa_exakt_null`, `fingerprints`, `zaehler` | Schema ist ueber die Zeit **gewachsen** — alte Zeilen haben nur 9 Felder | `data/runs/INDEX.jsonl` (Zeile 2 vs. letzte Zeile) | ja, aber nicht rueckwirkend |
| 2026-09-08 | v10-Gate-Artefakte | Dateiliste | `data/runs/v10/` = 94,3 MB, n=319 (davon `policy_oracle_cache/` 6,0 MB/193, `_alt_policy_oracle_cache_v1/` 577,3 KB/17, `g4_logs/` 4) | vollstaendig; G1–G5-Belege inkl. Ledger-JSONL | `research/g1_gate_runner.py:21`; `pokerbot/benchmark/gtow_ledger.py:15` | ja |
| 2026-08-18 | Fable-Adversar-Duell | Dateiliste | `data/runs/fable_duell/` = 4,0 KB, **n=1 Datei** | duenn — das 62-Hand-Duell liegt praktisch nicht als Rohdatensatz vor | `research/fable_duell.py:21` (`D = Path("data/runs/fable_duell")`) | eingeschraenkt |
| 2026-09-10 | Deck-Baenke (pargate) | Dateiliste | `data/_pargate_blocks/` = 12,9 KB, n=240 in 5 Bank-Ordnern (je 48 `jobNNN.json`); Baenke `b1080000`–`b1110000` | verbrauchte Baenke sind markiert (`_STALE_…`) | `data/_pargate_blocks/` (Ordnernamen) | ja |
| 2026-09-10 | Kaggle/OpenSpiel-Kanal | Log-Kopf | 4 Logs (4,6–5,3 KB); `kaggle_v10h0_vs_champion_2026-09-10.log:1` = `OpenSpiel exception: Unknown game 'universal_poker'` | **Kanal lief nicht** — die Logs enthalten keine Ergebnisse, nur den Fehler | `data/runs/kaggle_v10h0_vs_champion_2026-09-10.log:1` | nein (defekt) |

---

### 2. `data/autogym/` — das Journal

**Kanal:** append-only Entscheidungsprotokoll der Autogym-Schleife. Es ist die einzige Stelle, an der auch
**verworfene** Arme mit Begruendung stehen. Es enthaelt keine Rohdaten, nur Verdikte + Befundtexte.

| Datum | Was gemessen | Instrument/Kanal | Ergebnis (Zahl ± Streuung, n) | Verdikt | Quelle (datei:zeile) | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-09-10 | Journalumfang | Zeilen-Zaehlung | `journal.jsonl` = 64.360 B, **n=123 Zeilen**; erste 2026-08-16 19:25:54, letzte 2026-09-10 02:13:18 | lueckenlos, aktiv gepflegt | `data/autogym/journal.jsonl`; Schreiber `pokerbot/autogym/improver.py:28` | ja |
| 2026-08-16 | Pilot-Reports | Dateiliste | 3 `report_*.json` (2.022 / 2.375 / 2.423 B) vom 2026-08-16 | einmalig, nur Pilotphase | `data/autogym/report_20260816_*.json` | historisch |
| 2026-09-10 | Letzter Eintrag (Typ) | Journal-Lesen | `AIVAT-KAGGLE-ENTWURF`, Verdikt `"ENTWURF (nicht gebaut)"` | ehrlich als **nicht gebaut** markiert | `data/autogym/journal.jsonl` (letzte Zeile) | ja |

---

### 3. `data/sessions/` — gespielte Haende (Trainer, HU-App, GTOW)

**Kanal:** rohe Hand-Histories aus allen Spiel-Kanaelen. Aus `gtow_hands_*.jsonl` lassen sich AIVAT-Mittelwerte,
Street-Zerlegungen und Frequenz-Zensen **neu berechnen** — sie tragen pro Hand `aivat`, `winnings`, `board`,
`history` und **beide** Hole-Cards. Was der Kanal nicht kann: Snowie-Haende abdecken (kein Showdown-Logging).

| Datum | Was gemessen | Instrument/Kanal | Ergebnis (Zahl ± Streuung, n) | Verdikt | Quelle (datei:zeile) | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-09-10 | Gesamtumfang | os.walk | `data/sessions/` = 56,7 MB, n=482 Dateien | gitignored | `.gitignore:8` | ja |
| 2026-09-10 | Trainer-/6max-Sessions | Zeilen-Zaehlung ueber Glob | `session_*.jsonl`: **218 Dateien, 6.842 Zeilen (Haende), 11,2 MB** | vorhanden, aber je Datei sehr klein (Ø ~31 Haende) | Schreiber `pokerbot/web/six_server.py:97`; Leser `pokerbot/analysis/harvest_play.py:17` | ja |
| 2026-09-10 | Entscheidungs-Logs | Zeilen-Zaehlung ueber Glob | `decisions_*.jsonl`: **175 Dateien, 11.840 Zeilen, 39,4 MB** | Vertrag: eine `decisions_<sid>` je `session_<sid>` — 175 vs 218 ⇒ **43 Sessions ohne Entscheidungs-Log** | `pokerbot/coach/autotest.py:110` (Vertrag) | ja, mit Luecke |
| 2026-09-10 | GTOW-Hand-Histories | Zeilen-Zaehlung ueber Glob | `gtow_hands_*.jsonl`: **65 Dateien, 24.050 Haende, 5,8 MB**; Zeitspanne 2026-06-16 … 2026-08-18 | **der wertvollste Rohdatensatz des Projekts** — jede Zeile mit AIVAT + beiden Handkarten | `research/analyze_gtow_hands.py:1`; Beispielzeile `data/sessions/gtow_hands_1783381570.jsonl:1` | ja |
| 2026-09-10 | HU-App-Sessions | Zeilen-Zaehlung | `hu_*.jsonl`: 11 Dateien, 169 Zeilen, 0,2 MB | sehr duenn | `data/sessions/hu_*.jsonl` | ja, aber n zu klein fuer Aussagen |
| 2026-08-18 | GTOW-Lauf-Manifest | JSON-Lesen | 7 Dateien zugeordnet: smoke20_v1_CRASH n=18 (`"NICHT werten"`), smoke20_v2 n=20 AIVAT −21,34, smoke100 n=100 AIVAT −59,03, nacht1 chunkA–D n=500/500/497/500 AIVAT −26,59/−54,98/−31,65/−48,37 | Zuordnung Datei→Arm **dokumentiert**, inkl. verworfenem Crash-Lauf | `data/sessions/gtow_manifest_2026-08-18.json` | ja (die Nacht-1-Zahlen gelten laut CLAUDE.md als „Gym-Konfig nackt", kein v4-Verdikt) |
| 2026-08-18 | Arm-Fingerabdruck im Manifest | JSON-Lesen | `arm_v4`: `AUSLESE_STACK=r6_button`, `TURN_DEFENSE=0.07`, `SLOWPLAY=0.25`, `RAISE_NARROW=1.0`, `RESOLVER=0`, `TURN_RESOLVER=0` | reproduzierbar — Env-Konfig ist mitgespeichert | `data/sessions/gtow_manifest_2026-08-18.json` (Block `arm_v4`) | ja |

---

### 4. `data/gtow_upload/` — Analyzer-Exporte (PokerStars-HH-Format)

**Kanal:** die Dateien, die per Chrome in den GTO-Wizard-Analyzer hochgeladen wurden. Sie erlauben, einen
Analyzer-Grade zu **wiederholen**, nicht ihn nachzurechnen (die EV-Loss-Zahlen entstehen erst im Analyzer).
Achtung: Hand-IDs verbrennen beim ersten Kontakt — dieselbe Datei kann nicht erneut hochgeladen werden.

| Datum | Was gemessen | Instrument/Kanal | Ergebnis (Zahl ± Streuung, n) | Verdikt | Quelle (datei:zeile) | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-09-10 | Umfang | os.walk / ls | 55,8 MB, n=76 Dateien (36 Eintraege oberste Ebene) | vollstaendig erhalten | `data/gtow_upload/` | ja |
| 2026-07-04/05 | Die 1500er-Arme (gepaarte Exporte) | ls -S | `sixmax_hands_1500.txt` 1,72 MB · `hu_v31_1500` 1,01 MB · `hu_v3_1500` 1,00 MB · `hu_gtomode_fix_1500` 1,00 MB · `hu_v22_1500` 0,999 MB · `hu_hands_1500` 0,997 MB · `hu_head_s55_1500` 0,996 MB · `hu_v32_1500` 0,988 MB · `hu_gtomode_1500` 0,987 MB | die Arme der v2.2/v3-Analyzer-Vergleiche liegen **alle** noch vor | `data/gtow_upload/*_1500.txt` | ja als Beleg; **nicht** erneut hochladbar (Hand-ID-Verbrennung, CLAUDE.md-Regel) |
| 2026-06-28/29 | aeltere Arme | ls -S | `river_1000.txt` 876 KB, `bot_hands_1000.txt` 663 KB, `bot_hands_1000_ontree.txt` | historisch (Vor-PRINCE-Ära) | `data/gtow_upload/` | historisch |

---

### 5. `data/census/` + `data/freq_targets/` — der geminte GTOW-Lehrer

**Kanal:** aus den geloggten GTOW-Haenden destillierte Ziel-Frequenzen und der gemessene Sizing-Baum des
Gegners. Das ist abgeleitete, keine Roh-Evidenz — nachrechenbar aus `data/sessions/gtow_hands_*.jsonl`.

| Datum | Was gemessen | Instrument/Kanal | Ergebnis (Zahl ± Streuung, n) | Verdikt | Quelle (datei:zeile) | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-07-05 03:02 UTC | GTOW-Frequenz-Ziele | `research/freq_mine.py` ueber 47 Hand-Dateien | `gtow_frequencies.json` 107.534 B; meta.stats: **hands=13.675**, gtow_decisions=26.823, hero_seat0=6.795 / hero_seat1=6.781, **hero_unknown=99**, xcheck_agree=11.633 | belastbar, aber mit dokumentiertem Caveat: „GTOW's HU play conditioned on OUR lines" | `data/freq_targets/gtow_frequencies.json` (Block `meta.stats`); Erzeuger `research/freq_mine.py:15` | ja — reproduzierbar, aber der Datensatz waechst (heute 24.050 Haende ⇒ **Neu-Mining wuerde andere n liefern**) |
| 2026-07-05 19:34 | GTOW-Raise-Zusammensetzung | `research/raise_mine.py` | `gtow_raise_ranges.json` 1.826 B; z. B. `flop|srp|normal`: air 115 / top-pair 27 / pair 31 / two-pair+ 36 / monster 4 | duenn besetzt; Code warnt selbst: „jams pooled across streets (n=29 — small…)" | `data/freq_targets/gtow_raise_ranges.json`; Warnung `pokerbot/strategy/range_tracker.py:91` | ja, mit ausdruecklichem n-Vorbehalt |
| 2026-07-04 16:51 | GTOW-Sizing-Baum (Zensus) | `research/gtow_tree_census.py` | `gtow_tree.json` 6.631 B; z. B. `flop\|bet\|SRP`: 0.35→1015, 0.75→240, 1.6→26 … | Grundlage des Off-Tree-Snap in `postflop.py` | `data/census/gtow_tree.json`; Referenz `pokerbot/strategy/postflop.py:41`; „12.5k hands" `research/gtow_tree_census.py:3` | ja |
| 2026-07-04 | Duplikat-Zensen | Dateiliste | `dup_head.json` 3.105 B, `dup_mode.json` 2.932 B, `_dbg.json` 625 B | klein, Kontext-Artefakte | `data/census/` | historisch |

---

### 6. Gate-Instrumente: `stress/`, `gtow_grades/`, `dup_ab/`, `cleanup_baseline/`

**Kanal:** konservierte Ergebnis-Snapshots der PRINCE-Ära-Gates. Sie belegen, dass ein Gate lief; sie
enthalten keine Deck-Rohdaten, also ist ein Neu-Estimator hier **nicht** moeglich.

| Datum | Was gemessen | Instrument/Kanal | Ergebnis (Zahl ± Streuung, n) | Verdikt | Quelle (datei:zeile) | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-07-05/06 | Stress-Suite-Arme | Dateiliste | `data/stress/` 365,6 KB, n=20; 19 `_worker_*.json` (je 2–18 KB) + `stress_report.json` 55.135 B; Arme: gto, head, prince, prince_aggro/bd/obm/probe/pur/rcd, v23, v3, v31, v32, v33, v34, v35, v5a, v5b, v5c | vollstaendige Arm-Abdeckung der v2.2→v5-Leiter | `data/stress/stress_report.json`, `data/stress/_worker_prince_v3*.json` | historisch (PRINCE-Ära), Code-Stand seither geaendert |
| 2026-07-04/05 | Analyzer-Grades + Leak-Karten | Dateiliste | `data/gtow_grades/` 64,3 KB, n=9: `gtomode_graded_100.json` 17.179 B, `gtomode_paired_s55.json` 1.247 B, `hu_leaks_ev2.json` 6.842 B, `sixmax_leaks_ev2.json` 2.742 B, `leaderboard_2026-07-04.json` 4.791 B, `error_prognosis.json` 17.270 B, `LEAK_MAP.md` 4.644 B | die HU-53,4-%/6max-85,9-%-Ära ist als JSON konserviert | `data/gtow_grades/` | historisch — die zugehoerigen bb/100-Anker sind laut CLAUDE.md ueberholt |
| 2026-07-05 | Duplicate-A/B-Snapshots | Dateiliste | `data/dup_ab/` 62,8 KB, n=16 (`fix_off/on.json`, `p4_lineu.json`, `p4_lineu_ecall.json`, `p4_off.json`, `probe_on.json` …) | klein, nur Aggregate | `data/dup_ab/` | historisch |
| 2026-07-05 | Refactor-Byte-Identitaets-Basis | Dateiliste | `data/cleanup_baseline/` 440,1 KB, n=5 (`final_A.json`, `run_A.json`, `run_H0_A.json`, `stress_baseline.json`, `profile_baseline.txt`) | das Gate der Clean-Code-Doktrin | `data/cleanup_baseline/` | historisch (bezieht sich auf den damaligen Code-Stand) |

---

### 7. Solver-Caches — der groesste und teuerste Block

**Kanal:** Memoisierte TexasSolver-Loesungen. Sie machen `decide()` schnell und die Advisor-Trainingsdaten
ueberhaupt erst moeglich. Sie sind **regenerierbar, aber teuer** (CPU-Wochen) und **nicht** versionierbar.

| Datum | Was gemessen | Instrument/Kanal | Ergebnis (Zahl ± Streuung, n) | Verdikt | Quelle (datei:zeile) | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-09-10 | Live-Solve-Cache | os.walk | `data/_solve_cache/` = **35,0 GB, n=12.379 JSON** (SHA1-benannt, je ~46 KB, Baum mit `actions`/`childrens`/`node_type`); letzte Schreibzeit 2026-09-10 02:22 | **der groesste Einzelposten des Projekts** und aktiv in Benutzung | `pokerbot/strategy/gto_oracle.py:55` (`_CACHE_DIR = … "data"/"_solve_cache"`); Beispiel `data/_solve_cache/000610f057712f0a438bcb52bc517a3c73c4ad97.json` | ja |
| 2026-06-19 | Turn-Solves (4-Karten-Boards) | os.walk | `data/_gto_turn_cache/` = **1,1 GB, n=22.571** (Dateiname = Board, z. B. `2c2d4h7d.json`) | Futter fuer `defense_data` | `research/build_defense_data.py:26` (`TURN_CACHE`) | ja |
| 2026-06-18 | River-Subgame-Solves | os.walk | `data/_gto_river_cache/` = 162,0 MB, n=3.336 | Futter fuer `river_data` + floor_map | `research/build_river_data.py:18`; `pokerbot/benchmark/floor_map.py:92` | ja |
| 2026-06-14 | Benchmark-Cache | os.walk | `data/_gto_bench_cache/` = 69,8 MB, n=1.340 | Grundlage der Kalibrier-Laeufe | `pokerbot/benchmark/gto_benchmark.py:27`; `research/analyze_cache.py:14` | ja |
| 2026-06-15 | Short-Deck-Cache | os.walk | `data/_gto_shortdeck_cache/` = 41,7 MB, n=434 | Nebenzweig (Short Deck), sonst ungenutzt | `research/build_sd_advisor_data.py:14` | ja, aber Nebenlinie |
| 2026-06-14 | Cover-Cache | os.walk | `data/_gto_cover_cache/` = 7,3 MB, n=143 | klein | `data/_gto_cover_cache/` | historisch |
| 2026-06-14 | Verpackter GCP-Cache | ls | `data/gcp_solve_cache.tgz` = 409.529.467 B (390,6 MB) | Archiv eines Cloud-Solve-Laufs; nie ausgepackt geprueft | `data/gcp_solve_cache.tgz` | unklar (siehe „Offen") |

---

### 8. Advisor-Trainingsdaten (die `.pt`-Netze speisen sich hieraus)

**Kanal:** Sequenzdatensaetze aus den Solver-Caches. Damit liessen sich die vier Advisor-MLPs
**vollstaendig neu trainieren**. Ohne sie sind die `.pt` in `knowledge_base/postflop/` Blackboxen.

| Datum | Was gemessen | Instrument/Kanal | Ergebnis (Zahl ± Streuung, n) | Verdikt | Quelle (datei:zeile) | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-06-16 | Defense-Trainingsdaten | ls | `data/defense_data.jsonl` = 845.218.860 B (806,1 MB) | groesste Einzeldatei ausserhalb der Caches | `data/defense_data.jsonl`; Erzeuger `research/build_defense_data.py:25` | ja |
| 2026-06-29 | River line-aware | ls | `data/river_data_la.jsonl` = 458.637.311 B (437,4 MB) + `river_la_smoke.jsonl` 6.126.101 B | der line-aware River-Datensatz (Netz war laut Memory „EV-neutral", Daten liegen trotzdem) | `data/river_data_la.jsonl` | ja |
| 2026-06-15 | Advisor (Turn/River) | ls | `data/advisor_data.jsonl` = 88.945.399 B (84,8 MB) | in `CATALOG.md` als `data.advisor` gefuehrt | `CATALOG.md` (Tabelle „Big training files"); Pfad `data/advisor_data.jsonl` | ja |
| 2026-06-15 | River | ls | `data/river_data.jsonl` = 81.633.953 B (77,9 MB) | ” | `CATALOG.md`; `data/river_data.jsonl` | ja |
| 2026-06-15 | Short-Deck-Advisor | Zeilen-Zaehlung (CATALOG) | `data/sd_advisor_data.jsonl` = 17.801.128 B (17,0 MB), **199.720 Zeilen** | Nebenlinie | `CATALOG.md` (`data.sd_advisor`) | ja |
| 2026-06-16 | CFV-Shards | os.walk | `data/cfv_shards/` = 5,6 MB, n=5 (`cfv_dataset.jsonl`, `shard_0..2`, `pilot_local`) | Rest der CFV-Netz-Episode | `data/cfv_shards/` | historisch |

---

### 9. Populations- und Gegner-Daten (fremde Hand-Histories)

**Kanal:** echte Hand-Histories fremder Pools. Damit lassen sich Gegner-Profile (VPIP/PFR/Fold-Raten) und
Oekologie-Simulationen nachrechnen. **Nicht** damit rechenbar: unser eigenes bb/100 — wir haben dort nicht gespielt.

| Datum | Was gemessen | Instrument/Kanal | Ergebnis (Zahl ± Streuung, n) | Verdikt | Quelle (datei:zeile) | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-08-04 | GG NL2-Pool (roh) | os.walk | `data/gg_nl2/hh/` = **825,2 MB, n=241** (96 Tagesordner `JJJJ-MM-TT_ONG_NL2_SH_*` mit `hhd_Reg_*_NLH2SH_*.txt`) | groesster fremder HH-Bestand | `data/gg_nl2/hh/` | ja |
| 2026-08-04 | GG NL2-Populationsprofil | ls | `data/gg_nl2_pop.json` = 15.920.721 B (15,2 MB) + 7 Arm-Ergebnisse (`gg_nl2_agame*.json` u. a., je 154–165 B) | abgeleitet, klein — die Arm-Dateien enthalten nur Aggregate | `data/gg_nl2_pop.json`, `data/gg_nl2_all.log` | ja |
| 2026-08-04 | GG High-Stakes (NL2K) | os.walk | `data/gg_hs/` = 14,6 MB, n=80 (21 `.zip`-Tagesarchive + Ableitungen), `gg_hs_pop.json` 120.824 B | belegt den „haertester Pool"-Befund | `data/gg_hs/`, `data/gg_hs_pop.json` | ja |
| 2026-08-06 | GG NL200 | ls | `data/gg_nl200_pop.json` = 646.778 B; 3 Arm-Skripte (`nl200_arm_*.py`, 642–658 B) | Profil ohne beiliegende Roh-HH | `data/gg_nl200_pop.json` | ja, aber Rohquelle fehlt |
| 2026-08-03 | CoinPoker-Population | ls | `coinpoker_pop.json` 268.256 B; Zeitfenster-Splits `…euro_primetime_18-22utc.json` 106.406 B, `…seine_stunden_13-16utc.json` 101.302 B; `coinpoker_tourney_pop.json` 883.424 B | die Grundlage der Zeitfenster-Analysen | `data/coinpoker_pop*.json` | ja |
| 2026-07-26 | PokerStars-Turnierfeld | os.walk | `data/ps_tourney/hh/` = 18,3 MB, **n=145** `hhDealer.com_*.txt`; Auswertung `ps_tourney_field.json` 2.886 B; 12 Duell-Laeufe (`psduel*_w*.json`, 4,5–7,2 KB) | Beleg des ICM-Tightening-Befunds | `data/ps_tourney/`, `data/ps_tourney_field.json` | ja |
| 2026-08-06 | Tages-Splits | os.walk | `data/pd_day/` = 48,6 MB, n=240 (4 Ordner: `0408`, `0508`, `0608`, `hist0803`) | Zeitfenster-Rohdaten | `data/pd_day/` | ja |
| 2026-08-08/09 | GG-Turnier-HHs (eigene) | ls | `data/turnier_final/` 238,2 KB n=4, `data/turnier_live/` 124,7 KB n=2 (`GG2026…Daily Main Event 250.txt` u. a.) | sehr klein — Einzelturniere | `data/turnier_final/`, `data/turnier_live/` | ja |
| 2026-08-04 | MTT-Bot-Laeufe | ls | `data/mtt/` = 135,8 KB, n=8 (`bots_w0..w5.json` + 2) | Worker-Aggregate der Turnier-Arena | `data/mtt/` | ja |
| 2026-08-02 | Pluribus-Referenz | ls / JSON | `knowledge_base/hand_histories/pluribus_hands.jsonl` = 9.595.089 B, **10.000 Haende**; `pluribus_stats.json`: net **−7,09 bb/100**, VPIP 26,4 / PFR 17,7, je Position n=1.638–1.692 | **git-versioniert** — der einzige grosse Rohdatensatz im Repo | `knowledge_base/hand_histories/pluribus_stats.json`; `git ls-files knowledge_base/hand_histories` | ja |
| 2026-02…06 | CoinPoker-Spieler-HHs (fremd) | git ls-files | 41 `.txt` unter `knowledge_base/hand_histories/players - handhistories/Coin Poker/MTT - danic1994_*` — **versioniert** | 5-Card-PLO-MTT eines Dritten; **kein NLHE** und personenbezogen — passt nicht zur Repo-Grenze | `knowledge_base/hand_histories/players - handhistories/…` | fraglich (siehe „Offen") |

---

### 10. `data/vision/` — die PokerSnowie-Bruecke

**Kanal:** Bildschirm-Rohmaterial + Vision-Regressionsfaelle. Damit lassen sich Erkennungsfehler
**reproduzieren** (konservierte Tatorte); Spielstaerke laesst sich daraus nicht ableiten.

| Datum | Was gemessen | Instrument/Kanal | Ergebnis (Zahl ± Streuung, n) | Verdikt | Quelle (datei:zeile) | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-08-04 | Gesamtumfang | os.walk | `data/vision/` = **853,6 MB, n=37.774** | zweitgroesster `data/`-Block nach den Caches | `data/vision/` | ja |
| 2026-08-04 | Bildschirm-Mitschnitte | os.walk | `data/vision/rec/` = 715,3 MB, n=5.896 in 6 Laufordnern (`20260804_031409` … ) — JPG-Frames `f_<epoch_ms>.jpg`, ~838 Frames je Lauf | reine Frames, kein Ton/Meta — Zuordnung nur ueber Zeitstempel | `data/vision/rec/20260804_031409/f_1785806049639.jpg` | ja |
| 2026-08-04 | Template-/Glyphen-Bibliothek | os.walk | `data/vision/snowie/` = 32,0 MB, **n=31.241** Dateien | das Herz des Template-Matchings | `data/vision/snowie/`; Nutzer `pokerbot/vision/snowie_local.py` | ja |
| 2026-08-04 | Archiv Lauf 2 | os.walk | `data/vision/lauf2_archiv/` = 80,9 MB, n=369 | einer der drei Marathon-Laeufe | `data/vision/lauf2_archiv/` | ja |
| 2026-08-04 | Fehlerfaelle + Audit | os.walk | `fails/` 4,7 MB n=21 · `audit/` 6,9 MB n=51 · `review/` 45,8 KB n=33 · `review2/` 7,3 KB n=5 | die konservierten Tatorte des 5-Faelle-Regressionsnetzes | `data/vision/fails/`; Netz `research/snowie_regress.py` | ja |

---

### 11. `models/` — Qwen/GLM-Bruecke (die Brain-Spur)

**Kanal:** LoRA-Adapter und Trainingsmetriken. Damit liesse sich die Brain-Spur **wiederbeleben**; sie ist
laut CLAUDE.md sekundaer. Was hier nicht liegt: die Basismodelle (Qwen3-8B/GLM-Z1-9B) — die muessten neu geladen werden.

| Datum | Was gemessen | Instrument/Kanal | Ergebnis (Zahl ± Streuung, n) | Verdikt | Quelle (datei:zeile) | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-09-10 | Gesamt | os.walk | 16,1 GB, n=214 | gitignored, **einzige Kopie** (kein Remote) | `.gitignore:12` | ja |
| 2026-06-20 | Produkt-Baseline GLM | ls | `models/grpo_slim.tgz` = 708.329.284 B (675,5 MB); `grpo_slim_baseline.tgz` 705.895.142 B | laut CLAUDE.md „**das PRODUKT**" der Brain-Spur (≈ −40 robust) | `models/grpo_slim.tgz`; CLAUDE.md-Block „CURRENT BRAIN" | ja als Artefakt; die Spur selbst ist sekundaer |
| 2026-06-21 | GRPO-Adapter (entpackt + Archiv) | os.walk / ls | `models/qwen_poker_grpo/` 1,3 GB n=26; `qwen_poker_grpo.tgz` 708.092.681 B; `qwen_poker_grpo_live.tgz` 709.697.392 B | drei Kopien desselben Zustands | `models/qwen_poker_grpo*` | ja (redundant) |
| 2026-06-19/20 | SFT-Archive | ls | `qwen_poker_sft.tgz` 2.805.408.022 B (2,6 GB); `sft_new.tgz` 2.124.995.948 B; `sft_slim.tgz` 705.866.733 B | grosser, ungeprueft redundanter Block | `models/*.tgz` | ja |
| 2026-06-14 | Frueher 8B-Checkpoint | ls | `models/qwen_poker_ckpt500/`: `adapter_model.safetensors` 698.419.728 B + `adapter_config.json` 1.140 B + `trainer_state.json` 8.728 B | in `CATALOG.md` als ⚠️ „historical" markiert | `CATALOG.md` (`model.poker_ckpt500`) | historisch |
| 2026-06-14 | 32B-LoRA | ls | `data/qwen32b_lora.tgz` = 1.988.149.853 B (1,85 GB) — liegt **in `data/`, nicht in `models/`** | Ablage-Inkonsistenz | `data/qwen32b_lora.tgz` | ja |
| 2026-06-17/18 | Lokale 1.7B-Beweise | os.walk | `qwen_local_sft/` 2,5 GB n=73 (6 Checkpoints) · `qwen_local_grpo/` 964,6 MB n=31 · `qwen_1.7b_aligned/` 964,6 MB n=29 · `qwen_local_sft_aligned/` 554,3 MB n=18 · `qwen_smoke/` 554,3 MB n=18 | die frac_bad-Beweise (0,97→0,00) | `CATALOG.md` (`model.local_sft`, `model.local_grpo`) | ja als Beleg |
| 2026-06-18 | Leere Platzhalter | os.walk | `models/qwen_8b_local_sft/` **0 B / 0 Dateien**, `models/qwen_combined_sft/` **0 B / 0 Dateien** | leer — `CATALOG.md` fuehrt `sft_aligned` faelschlich als „EMPTY", obwohl dort 554,3 MB liegen | gemessen `models/`; Behauptung `CATALOG.md` (`model.sft_aligned`: „EMPTY … 18 files · 554.3M") | **CATALOG-Widerspruch, siehe „Offen"** |
| 2026-06-18/21 | Trainingsmetriken | ls | `models/grpo_metrics.jsonl` 12.225 B; `data/training_metrics.jsonl` 72.897 B; `data/gpu_load.jsonl` 385.946 B; `data/local_grpo_metrics.jsonl` 3.914 B | Kurven nachzeichenbar | `models/grpo_metrics.jsonl` | ja |

---

### 12. `dataset/shards/` — „das Gold" (versioniert)

**Kanal:** die DSL-Trainingsdaten. Einziger grosser Datenbestand, den ein Klon **mitbekommt**.
Zeilenzahlen unten stammen aus `CATALOG.md` (generiert 2026-06-20), Groessen aus der Messung heute.

| Datum | Was gemessen | Instrument/Kanal | Ergebnis (Zahl ± Streuung, n) | Verdikt | Quelle (datei:zeile) | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-09-10 | Umfang | os.walk | `dataset/shards/` = 71,9 MB, n=22 Dateien; **git-getrackt** | erbbar per Klon | `git ls-files dataset` (42 Eintraege inkl. Shards) | ja |
| 2026-06-20 | SFT-Gold (aktiv) | `dataset/build_manifest.py` | `a_contract` 1.750 Zeilen/1,8 M · `c_decide` 3.250/3,2 M · `solver` 2.617/1,7 M · `hu_blueprint` 12.168/6,6 M | die vier aktiven Gold-Shards | `CATALOG.md` (Tabelle „SFT gold") | ja |
| 2026-06-20 | Ausgeschlossen (dokumentiert) | `dataset/registry.py` | `solver_mass` 25.586 Zeilen/16,2 M — `current=False`; Begruendung woertlich: „DROWN the 2.2k Claude-teacher postflop gold 13:1" | **negatives Ergebnis, sauber begruendet konserviert** | `dataset/registry.py` (Asset `shard.solver_mass`, `note=`) | ja |
| 2026-06-20 | Leere/veraltete Shards | `CATALOG.md` | `b_ground` 0 Zeilen, `d_exploit` 0 Zeilen, `local_kb` 11.599/10,7 M (⚠️ „the original frac_bad=0.97 cause"), `sample` 253 | ehrlich als ⚠️ markiert | `CATALOG.md` (Tabelle „Other shards") | ja |
| 2026-06-21 | `.off.bak`-Doubletten | ls | 4 Backup-Kopien mitversioniert: `a_contract.jsonl.off.bak` 1.890.272 B, `c_decide…` 3.349.171 B, `hu_blueprint…` 2.875.105 B, `solver…` 1.743.795 B | ~9,8 MB redundant **im Git** | `git ls-files dataset/shards` | ja (aufraeumbar) |
| 2026-06-20 | Fehlend | `CATALOG.md` | `shard.teacher` = „—(missing)" laut CATALOG, aber `dataset/shards/teacher.jsonl` liegt mit 1.904.360 B auf der Platte | **CATALOG veraltet** — die Datei existiert seit 2026-06-20 17:34 | Messung `data`/`dataset/shards/teacher.jsonl`; Behauptung `CATALOG.md` (`shard.teacher`) | CATALOG-Zeile gilt nicht mehr |

---

### 13. `knowledge_base/` — versionierte Theorie + trainierte Netze

**Kanal:** das einzige Verzeichnis, das Strategie-Code **hart referenziert** (`pokerbot/config.py:15,30`).
Verschieben bricht den Bot.

| Datum | Was gemessen | Instrument/Kanal | Ergebnis (Zahl ± Streuung, n) | Verdikt | Quelle (datei:zeile) | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-09-10 | Umfang + Git | os.walk / git | 28,6 MB, n=115; **103 getrackt** | ⇒ 12 Dateien liegen ungetrackt darin (v. a. `.pt`, per `.gitignore:18` ausgeschlossen) | `git ls-files knowledge_base`; `.gitignore:18` (`*.pt`) | ja |
| 2026-09-10 | Unterordner | os.walk | `exploit/` 7,5 M n=11 · `hand_histories/` 14,2 M n=43 · `ranges/` 2,5 M n=11 · `math/` 1,7 M n=17 · `concepts/` 1,5 M n=2 · `postflop/` 696,6 K n=9 · `theory/` 309,5 K n=18 · `cfr/` 168,2 K n=1 · `tournament/` 4,4 K n=1 | vollstaendig | `knowledge_base/` | ja |
| 2026-06-20 | Abweichung zu CATALOG | Vergleich | CATALOG nennt `postflop/` 8 Dateien/671,6 K und `theory/` 16/284,3 K — gemessen sind es **9/696,6 K** bzw. **18/309,5 K** | **CATALOG.md ist veraltet** (Stand 2026-06-20) | `CATALOG.md` (Tabelle „knowledge_base/ subdirs") vs. Messung 2026-09-10 | CATALOG-Zahlen gelten nicht mehr |
| 2026-06-20 | Die vier Advisor-Netze | `CATALOG.md` | `advisor.pt` 23,9 K (+63 % vs strength-only) · `turn_advisor.pt` 23,9 K (+46 %) · `river_advisor.pt` 24,3 K (+18 %) · `defense_advisor.pt` 25,8 K („_verify live wiring_") | winzig, aber **gitignored** ⇒ ein Klon hat sie nicht | `CATALOG.md` (Tabelle „Trained postflop advisors"); `.gitignore:18` | ja — und das ist ein Erb-Risiko |
| 2026-06-20 | Playbooks / Ranges | `CATALOG.md` | `exploit/playbook.jsonl` 11.520 Zeilen/7,2 M · `postflop/openai_strategy.json` 30,7 K (62 Regeln) · `ranges/preflop_blueprint.json` 85,8 K · `cfr/preflop_pushfold.json` 168,2 K | versioniert, erbbar | `CATALOG.md`; `pokerbot/config.py:15,30` | ja |
| 2026-08-04 | Turnier-Doktrin | os.walk | `knowledge_base/tournament/` = 4,4 KB, **n=1** (`DOKTRIN.md`) | die extrahierte Sklansky/ICM-Doktrin ist genau **eine** Datei | `knowledge_base/tournament/DOKTRIN.md` | ja |

---

### 14. `books/` — die Quellenbibliothek

**Kanal:** die PDF-Quellen, aus denen `knowledge_base/` extrahiert wurde. Nachrechenbar ist damit nur die
**Extraktion**, nichts Spielerisches. Faktisch nicht erbbar per Klon (`*.pdf` gitignored).

| Datum | Was gemessen | Instrument/Kanal | Ergebnis (Zahl ± Streuung, n) | Verdikt | Quelle (datei:zeile) | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-09-10 | Umfang | os.walk | 299,6 MB, n=56; **2 Dateien getrackt** (beides `.txt`-Notizen) | Bibliothek ist NICHT im Repo | `git ls-files books`; `.gitignore:13` | ja |
| 2026-07-07 | Poker-Buecher | ls | `books/poker/` 191,1 MB, n=10: Modern Poker Theory 113,9 MB · NLHE Theory&Practice 18,0 MB · Beyond GTO 16,3 MB · Theory of Poker 14,2 MB · Play Optimal Poker 2 7,9 MB · Surfing Uncertainty 9,3 MB · Exploitative Poker 5,7 MB · Mathematics of Poker 5,2 MB + Ordner `Tournament play` (2 PDFs) | 8 PDFs + 2 Turnier-PDFs — CLAUDE.md spricht von „the 6 poker books" | `books/poker/` | Bestand ja; die „6 Buecher"-Formulierung in CLAUDE.md ist ueberholt (10) |
| 2026-08-07 | Papers | ls | `books/papers/` 85,2 MB, n=39 in 13 Eintraegen; `CFR/` mit 10 PDFs (u. a. `2605.19928v1.pdf` = Li&Huang, `EVPA !.pdf`, `Harvard 2022.pdf`); Einzeln: `Pluribus.pdf`, `Supremus.pdf`, `Springer - Nash + Incomplete Information.pdf`, `MIT about Poker.pdf` | die in CLAUDE.md zitierten Belegstellen liegen physisch vor | `books/papers/CFR/2605.19928v1.pdf`; `books/papers/Springer - Nash + Incomplete Information.pdf` | ja |
| 2026-08-04 | Mindset / AGT | ls | `books/#Mindset/` 2,1 MB n=2; `books/Algorithmic Game theory/` 520,5 KB n=1 (`2605.10900v1.pdf`) | Randbestand | `books/#Mindset/`, `books/Algorithmic Game theory/` | ja |
| 2026-06-13/16 | Extrahierte Buchtexte | ls | `data/text/` 2,5 MB n=4 (`mathematics_of_poker.txt`, `modern_poker_theory.jsonl`, `nlhe_theory_practice.jsonl`, `theory_of_poker.jsonl`); `data/chunks/all_chunks.jsonl` 1,5 MB; `data/page_images/` 150,9 MB n=269 | die Extraktions-Zwischenstufe liegt vor ⇒ Extraktion nachvollziehbar | `data/text/`, `data/chunks/all_chunks.jsonl` | ja |

---

### 15. Persoenliche / nicht-Kern-Ablagen

| Datum | Was gemessen | Instrument/Kanal | Ergebnis (Zahl ± Streuung, n) | Verdikt | Quelle (datei:zeile) | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-08-16 | Eigene Hand-Histories | os.walk | `hand histories/` = 162,6 MB, n=80 (`Days/` 125,2 KB n=8, `Historisch/` 162,5 MB n=72) | gitignored; Grundlage der Spieler-Report-Pipeline | `.gitignore:37` | ja |
| 2026-08-16 | Berichte (gemischt) | ls | `data/reports/` (heute nur Poker-Berichte, u. a. `Q9o_Finaltisch_Bericht.pdf`, `Simulation_Heute.pdf`) | **Nachtrag 2026-09-10:** alle projektfremden Teile (Geopolitik-Modell samt Bericht, persoenliche Psychologie-Dokumente, Grafiken einer Beziehungsanalyse) wurden aus dem Repo verschoben | `Desktop/PokerB_ausgelagert_2026-09-10/LIESMICH.txt` | erledigt |
| 2026-07-01 | Coach-Artefakte | ls | `data/coach/` 1,0 MB n=24 (`deep_stats.json`, `style_sim.json`, `synth.json`, `range_chart.svg`, `Poker_Report.md` …) | Zwischenstufen der Report-Pipeline | `data/coach/` | ja |

---

### 16. Offen / unklar (nicht auflösbar ohne Nachmessung)

- **`CATALOG.md` ist veraltet** (generiert 2026-06-20). Drei belegte Widersprueche zur Messung von heute:
  `shard.teacher` „—(missing)" vs. 1.904.360 B auf Platte; `model.sft_aligned` „EMPTY" vs. 554,3 MB/18 Dateien;
  `knowledge_base/postflop` 8 Dateien vs. gemessen 9. Behebung: `python -m dataset.build_manifest`.
  Quelle: `CATALOG.md` vs. Messung 2026-09-10.
- **`data/runs/STAND.md` ist veraltet** (22 Tabellenzeilen, letzter Lauf 2026-08-17) gegenueber 79 INDEX-Zeilen
  und 91 Laufordnern. Alle Laeufe ab 2026-08-18 (inkl. der v10-Gates und der `pargate6`-Flat-Fix-Laeufe vom
  2026-09-09) fehlen dort. Quelle: `data/runs/STAND.md`, `data/runs/INDEX.jsonl`, `ls -d data/runs/20*/`.
- **12 Laufordner ohne `result.json`/Index-Zeile** (`exploit_jagd`, `runde4_kampagne`, `runde5_sweep` u. a.) —
  ihre Ergebnisse existieren nur im Journal, nicht als nachrechenbare Rohdaten. Quelle: `data/runs/INDEX.jsonl`
  (79) vs. 91 Ordner.
- **Kaggle-/OpenSpiel-Kanal (2026-09-10) ist nicht lauffaehig**: alle vier Logs beginnen mit
  `Unknown game 'universal_poker'`. Ob spaeter im selben Log Ergebnisse stehen, wurde nicht geprueft.
  Quelle: `data/runs/kaggle_v10h0_vs_champion_2026-09-10.log:1`.
- **`data/gcp_solve_cache.tgz` (390,6 MB), `data/runpod_hu_turns.tgz` (209,1 MB), `data/qwen32b_lora.tgz`
  (1,85 GB)** — nie ausgepackt geprueft; Inhalt und Redundanz zu den entpackten Baeumen unbekannt.
- **Redundanz in `models/`**: `qwen_poker_grpo/` (entpackt) + `qwen_poker_grpo.tgz` + `qwen_poker_grpo_live.tgz`
  belegen ~2,7 GB fuer vermutlich denselben Zustand; nicht per Hash verglichen.
- **Erb-Risiko**: die vier Advisor-`.pt` (zusammen ~98 KB) sind gitignored (`.gitignore:18`), werden aber von
  `pokerbot/config.py:30` hart referenziert. Ein frischer Klon hat sie nicht — und ohne
  `data/*_data.jsonl` (1,4 GB, ebenfalls gitignored) sind sie nicht nachtrainierbar. Das ist die
  gefaehrlichste Luecke der ganzen Landkarte.
- **Repo-Grenze:** Die projektfremden Dateien in `data/` (Geopolitik-Modell samt Bericht, persoenliche
  Psychologie-Dokumente, Grafiken einer Beziehungsanalyse) wurden am **2026-09-10 aus dem Repo verschoben**,
  nach `Desktop/PokerB_ausgelagert_2026-09-10/` mit LIESMICH. Weiterhin im Repo:
  `knowledge_base/hand_histories/players - handhistories/Coin Poker/` mit **41 versionierten**
  5-Card-PLO-MTT-Histories eines Dritten. Das sind Pokerdaten, aber personenbezogen; bewusst belassen.

---

## Nachtrag und Korrekturen

Alle Zahlen hier sind gegen das Repo geprueft (nur lesend). Wo ich selbst nachgerechnet oder nachgelaufen bin,
steht das ausdruecklich dabei. Zeilennummern gelten fuer den Stand HEAD `e8248e1` (2026-09-10 02:38).

**Vorbemerkung, die alles andere ueberholt:** das Journal ist waehrend der Sammlung gewachsen — es hat heute
**124** Zeilen, nicht 123. Der neue Eintrag `data/autogym/journal.jsonl:124` (2026-09-10 02:38:07,
`typ: KAGGLE-MESSUNG-UNGUELTIG`) erklaert **zwei** Kaggle-Messungen fuer ungueltig, die in vier Teilen der
Sammlung noch als gueltig gefuehrt werden. Details unter C-V1/C-V2.

---

### (a) Nachgetragene Messungen

#### A1 — Slumbot (externer HU-Bot, roh, ungepaart)

*Was der Kanal kann:* eine kostenlose externe Zweitmeinung ueber die HU-Gesamtpolitik gegen einen
near-GTO-Gegner. *Was er nicht kann:* keine AIVAT-Korrektur, keine Deck-Paarung, keine Entscheidungs-
Attribution — die SE ist gross (±73 bei n=500), Kleinstichproben luegen hier nachweislich um Faktor 70.
In der Sammlung taucht Slumbot nur als 1.7B-Brain-Zahl (−72, `05_llm.md:92`) auf; der Engine-Kanal fehlt ganz.

| Datum | Was gemessen | Instrument/Kanal | Ergebnis | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-06-22 | Spiel-Engine `PokerBot(exploit=False)` gegen Slumbot | `research/slumbot_collect.py`, roh, ungepaart | **+12,6 bb/100 (n=500, ±73,2)**; frueherer Teillauf ~−35/−46 (n=580) | ≈ break-even; die Engine ist gegen Slumbot **nicht** schlecht | `memory/engine-vs-slumbot-breakeven.md` | ja — korrigiert jede „−46 = schlecht"-Lesart |
| 2026-06-22 | Fehler-Obduktion der 18 groessten Verluste (Slumbots Showdown-Karten aufgedeckt) | `research/slumbot_mistakes.py` | **~½ Cooler (−51k Chips, irreduzibel), ~½ fixierbares -EV-Betten (−26k Chips: Hero bettet schwach/Luft, Slumbot callt), 0 Verluste durchs Folden** | kein Overfold-Leak; der Leak ist Ueber-Aggression gegen einen Caller | `memory/engine-vs-slumbot-breakeven.md` | ja — strukturgleich zum GTOW-Tail-Befund |
| — | Kleinstichproben-Luege im selben Kanal | dito | **−871 bb/100 bei n=40** (voll erholt); **−374** war der falsche Bot (`slumbot_llm --bot solver`, `SolverSlumbotBot`) | zwei Fehlalarme, beide aufgeklaert | `memory/engine-vs-slumbot-breakeven.md` | ja als Warnung |
| (Sitzung mit n=2500) | Gesamt-Bot exploit-primary gegen Slumbot | Slumbot, n=2500 | **−39,6 ± 30,9 bb/100** ≈ statistisch der Floor (−43); **das historische +31 reproduzierte NICHT** | negativ; Exploit-Overlay unterbaut | `docs/STATE.md:1479` | ja — das ist die groesste n dieses Kanals |
| (historisch) | Exploit-Overlay-Aera | Slumbot | **+31** (vorher −102); Anti-Spew-Fix: vs GTOBaseline −912 → **+207**, vs Slumbot −526 → **−46** | historische Etappen | `docs/STATE.md:1653`, `:1865` | **nein** — durch den n=2500-Lauf ersetzt |

#### A2 — Theorie-Duell (in-engine Spiegel gegen „Theorie")

*Was der Kanal kann:* Kartenglueck durch Duplikat-Spiegelung loeschen und den Bot gegen zwei explizite
Verkoerperungen von „Theorie" stellen ($0, kein GTOW). *Was er nicht kann:* All-in-**Strategie**-Varianz
kuerzen — genau deshalb bleibt die SE bei n=6000 noch ±10.

| Datum | Was gemessen | Instrument/Kanal | Ergebnis | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-07-06 | Nulltest: Theorie gegen sich selbst | `research/theory_duel.py`, Spiegel, n=6000 | **+0,00 ± 0,00** | Instrument validiert | `docs/THEORY_DUEL.md:13` | ja |
| 2026-07-06 | Unser GTO-Floor gegen analytische GTOBaseline (Chen/MDF/balanciert) | Spiegel, n=6000, 100 bb | **−16,03 ± 10,30** (CI −36…+4) | wir verlieren gegen die Theorie | `docs/THEORY_DUEL.md:14` | ja |
| 2026-07-06 | Volle Exploit-Engine gegen dieselbe Baseline | Spiegel, n=6000, 100 bb | **−19,44 ± 10,51** (CI −40…+1); Differenz Exploit−Floor = **−3,4 = statistisch null** | das Exploit-Overlay bringt gegen einen fixen near-GTO-Gegner **nichts** | `docs/THEORY_DUEL.md:15`, `:31-33` | ja — belegt die Doktrin „Exploitation nur gegen Abweichler" |
| 2026-07-06 | TexasSolver-Orakel als Gegner | gepaart, n=120, 40 bb, 541 Live-Solves, 0 Fallback | **−33,3 ± 60,8** (CI −152…+86) | zu verrauscht fuer ein Vorzeichen; ein 6-Hand-Smoke las +233 = reines Tail | `docs/THEORY_DUEL.md:16-18` | ja als Methodenbefund |
| 2026-07-06 | Grenze des Spiegel-Kanals | dito | SE bleibt **±10 bei n=6000**, ±61 bei n=120 | **bindende Lehre**: der Spiegel kann All-in-Strategievarianz nicht loeschen → das enge Live-Gate ist AIVAT, nicht roher Spiegel | `docs/THEORY_DUEL.md:37-39` | ja |

#### A3 — Oekologie / Pool-Simulation (Dutzende gemessener bb/100, in keinem Teil)

*Was der Kanal kann:* aus echten fremden Hand-Historien eine Populations-Frequenzhuelle schaetzen und
Strategie-Arme auf identischen Seeds gegen dieses Feld laufen lassen — inklusive Rake. *Was er nicht kann:*
absolute Winrates versprechen; die Agenten sind postflop naiv, deshalb sind alle Bot-Positiva
**modell-optimistisch**. Belastbar sind Ordnung und Abstaende. `08_daten.md:166-172` inventarisiert nur die
Rohdaten dieser Laeufe, keine einzige Zahl daraus.

| Datum | Was gemessen | Instrument/Kanal | Ergebnis | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-08-04 | GG $10/$20 NLHDiamond, Pool-Vermessung | `research/gg_hs_ecology.py`, 12.211 Haende, 611 Spieler | **84,8 % TAG-Regs**; echte Gewinner **+8…+15 bb/100**; Rake 1,93 % / Cap 0,8 bb | haertester vermessener Pool | `docs/STATE.md:441-442` | ja |
| 2026-08-04 | Vier Arme auf gleichen Seeds in diesem Pool | dito, 25k Haende | GTO-Hybrid **+105,7** · Exploit (Live-Reads) **+126,0** · P_D-A-Game **+6,1 ± 15,0** · P_D-Voll-Klon **−216,1** (Rake-Last 13,5 vs 6,3) | Absolutwerte modell-optimistisch; Ordnung belastbar | `docs/STATE.md:442-443` | ja mit Vorbehalt |
| 2026-08-04 | A-Game-Grosslauf | dito, **200k Haende, Seed 23** | **+16,6 ± 5,3 bb/100 nach Rake, 95 %-Band [+6,3, +27,0]** — vollstaendig ueber Null | signifikanter Gewinner am oberen Rand der echten Pool-Gewinner | `docs/STATE.md:444` | ja |
| 2026-08-04 | Preis des Tilts | Differenz Voll-Klon vs A-Game | **~233 bb/100**, davon **~222** allein durch den Reset-Waechter | die teuerste gemessene Verhaltensvariable des Projekts | `docs/STATE.md:445-447` | ja |
| 2026-08-03 | CoinPoker NL200, Pool + Arme | `research/coinpoker_ecology.py`, 124k beobachtete Haende (92 % Regs) | echte Gewinner **+23…+52**; Rake 3,96 % / Cap ~3,1 bb; P_D-Gesamt-Klon **−263 ± 16** (kreuzvalidiert gegen seine echte **−231 ± 89**); Ernst-Klon nach Rake **−31 ± 7** (pre-Rake ≈ 0); tag+Reads **+115 ± 10**; GTO-Hybrid **+109 ± 11** | Klon-Verdikt ueber 3 Pools konsistent (−216/−231/−263) | `docs/STATE.md:536-540` | ja mit Modell-Vorbehalt |
| 2026-08-03 | All-in-Glueck der 458 ernsten Haende | All-in-EV-Bereinigung | roh **+53,7** → adjustiert **−13** (Glueck +67 aus 13 HU-All-ins) | roh war eine Glueckszahl | `docs/STATE.md:541-542` | ja |
| 2026-08-03 | Ein-Schlag-Gesetz (Linien-Sektion) | dieselben 458 Haende | **jede** agg1-Klasse positiv (Konterschlag +8,5/Hand, 3bet+Barrel +30/Hand), **jede** agg2/3-Klasse negativ (−26…−105/Hand); Potenzial ~**+150 bb/100** | scharfe, uebertragbare Regel | `docs/STATE.md:550-552` | ja |
| 2026-08-03 | GG-NL200-Kreuzreplikation | 43k Haende, 88 % TAG | Gesamt-Klon **−231 ± 14** (CP: −263); Ernst-Profil **−18 ± 10** nach Rake / +10 vor Rake | Replikation bestanden | `docs/STATE.md:546-547` | ja |
| 2026-08-03 | Turnierfeld vs Cash fuer dasselbe Profil | $150 CoinMasters, 131k Haende | Turnier-Profil **+6,8 ± 4,7** Chip-EV (n.s.) vs Cash-Profil **+3,1 ± 6,4** | Kostenstruktur (kein Per-Hand-Rake) schlaegt Skill | `docs/STATE.md:548-549` | ja |
| (2026-08) | GG-NL2-Steuerlast + Gewinner-Template | `docs/PREP_GG_NL2.md` | Steuer 4,48 % des Pots ≈ **34–39 bb/100 Last**; Gewinner **+14,9** (n=59) vs Verlierer **−14,7** (n=64); Trennlinie = 3 Punkte weniger VPIP + FvR 78 vs 74 | die Gewinner folden am meisten im Pool | `docs/PREP_GG_NL2.md:18`, `:26` | ja |
| (2026-08) | Hebel-Ranking auf dem A-Game | Simulation, 40k Haende je Arm, gleiche Seeds | Ist-Stil **−210** → A-Game **−29**; Value-Gate allein **+31,1** (Δ +59,8); Limp-Cut Δ +21,2; Call-Disziplin Δ +12,2; **3bet-Up ±0 = bringt nichts**; alle drei gebuendelt **+63,0 ± 10,7** | ein klar negatives Einzelergebnis (3bet-Up) mitgemessen | `docs/PREP_GG_NL2.md:35`, `:41-47` | ja |
| (2026-08) | ehrliche Erwartung nach Abzug der Modell-Optimistik | dito | realistisch **+30 bb/100**, SD **90–110** | Erwartung, keine Messung | `docs/PREP_GG_NL2.md:68` | ja als Erwartung |

#### A4 — Value-Net / Leduc (exakte Exploitability)

*Was der Kanal kann:* als einziges Instrument des Projekts eine **exakte** Best-Response-Exploitability gegen
eine echte Nullpunkt-Wahrheit rechnen ($0, Spielzeug-Groesse). *Was er nicht kann:* HUNL-bb/100 vorhersagen.

| Datum | Was gemessen | Instrument/Kanal | Ergebnis | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-06-16 | Gate 0b — lernt ein CFV-Netz das exakte Orakel? | Leduc, Held-out-MAE gegen `vanilla_cfr`-Labels | **val MAE 0,191 = 6,4 % der CFV-Skala** (Gate < 8 %) | **PASS** — der DeepStack-Kern validiert (genau das, was das fcpa-Policy-Netz mit −212 NICHT konnte) | `docs/VALUE_NET_PLAN.md:54` | ja |
| 2026-06-16 | Gate 0c — spielt der Belief-State-Resolver richtig? | Leduc, exakte Exploitability | konvergiert in eine **Nicht-Bluff-Ecke**: P0 bluff't J **0 % statt exakt 8 %**, P1 over-foldet Q **47 % statt exakt 1 %** (dominanter Leak); **Exploitability 170 vs Gleichgewicht 22 mbb/Hand** | **negativ, Ursache lokalisiert** (infoset-weise, H1 „Propagations-Bug" widerlegt) | `docs/VALUE_NET_PLAN.md:57-60` | ja |
| 2026-06-16 | skalierte Erwartung des Pfads | — | **−53 → −15…−25 bb/100** | **Erwartung, keine Messung** | `docs/VALUE_NET_PLAN.md:17` | ja als Erwartung |

#### A5 — Rauschboden des K1-Orakels (die Vorbedingung des v10-G3-Urteils)

*Was der Kanal kann:* den eigenen Messfehler beziffern, bevor ein Urteil gefaellt wird. Die Sammlung fuehrt
nur den Endwert (Floor 0,095 in `02_runs.md:244`, „~271 Seeds" in `01_journal.md:168`) — die Skalierung fehlt.

| Datum | Was gemessen | Instrument/Kanal | Ergebnis | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-09-07 | Wie schnell faellt der Rauschboden des Orakels mit den Seeds? | `research/k1_oracle.py`, n=6 Vorgeschichten / 14 Knoten / 12 Worker | **S=8 → 0,122 · S=32 → 0,050 (600 s) · S=64 → 0,033 (1124 s) ≈ 1/√S**; Klassen-Ebene bei S=64 bereits auf **0,0035** konvergiert | fuer den Urteils-Floor ≤ 0,010 waere **S≈256 (~13 h)** noetig — das ist der Grund, warum G3 nur „`orakel_zu_grob`" sagen konnte | `research/k1_oracle.py:44-46` | ja |

#### A6 — Journal-Felder, die niemand zitiert (Vorzeichen-Test)

*Was das Feld sagt:* `vorzeichen_z` prueft, ob die Mehrheit der **abweichenden Decks** in die Richtung des
Mittelwerts zeigt. Es ist genau das Kriterium, mit dem das Projekt anderswo Kandidaten kippt.

| Datum | Was gemessen | Instrument/Kanal | Ergebnis | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-08-17 23:25 | v4-Kern gegen Basis, gepoolter Anker | pargate-Spiegel, 3×30k = **n=89.760** | bb100 **+16,14 ± 2,77**, CI95 [+10,74, +21,56], perm_p **0,0002** — **aber `vorzeichen_z: −5,63`** bei nonzero-Anteil 0,2063 | ANWENDEN (so eingetragen); **ehrlicher Zusatz: der Mittelwert ist positiv GEGEN die Mehrheit der divergenten Decks** — der Gewinn ist tail-getragen | `data/autogym/journal.jsonl:70` | ja — der Anker gilt, die Einschraenkung fehlt in `01:107`, `02:61`, `06:94` |
| 2026-08-17 21:33 | Kontrast: `turn_wert` gepoolt | pargate, n=89.760 | bb100 **+7,27 ± 2,33**, `vorzeichen_z` **+14,93**, nonzero 8,58 % | derselbe Kanal kann ein sauberes Vorzeichen liefern — v4 tut es nicht | `data/autogym/journal.jsonl:63` | ja |

#### A7 — Formel-Blindkampagne (drei echte Formelfehler)

| Datum | Was gemessen | Instrument/Kanal | Ergebnis | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| (2026-07-06-Aera) | Doppelt-blinde Neuherleitung der Formelbibliothek | 24 Agenten, unabhaengige Zweitherleitung | **3 echte Formelfehler** gefixt und in der Suite gepinnt: `bluff_to_value` r=B/P → **B/(P+B)** (der Audit-Fix vom 2026-06-20 hatte den falschen Nenner), `balanced_bluff_combos` (e>0-Indifferenz), `give_up_frequency` (b=0,5 als Konstante eingebacken); Ledger **72 → 69** unverifiziert; Suite auf **20/20** | positiv; alles KB-/Brain-Schicht, der Engine-Entscheidungspfad war nicht betroffen | `docs/STATE.md:745-748` | ja — `05_llm.md:163` fuehrt nur das 90-Agenten-Audit |

#### A8 — GTOW-Leak-Zerlegung und der Exploit-Katalog

| Datum | Was gemessen | Instrument/Kanal | Ergebnis | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-07-04 | Zerlegung der 19,33 bb/100 Analyzer-EV-Loss in benannte Leaks | Analyzer, per-Entscheidung | **L1 BB/SB-Flop-Overfold vs Cbet 2,91** (foldet Top Pair: Kd6s auf KcTs5h) · **L2 River-Ueberaggression 1,58** · **L3 Cbet-dann-Fold 1,33** · **L4 River-Underbet 0,98** · **L5 River sonstiges 0,95** | die einzige benannte Leak-Zerlegung des Projekts; kommt in keinem Teil vor | `docs/TIE_GTOW.md:31-35` | ja fuer die v2.2-Aera-Engine |
| 2026-08-17 | Angriffs-Katalog gegen uns (K1–K7) mit Prioren | Werkzeug-Analyse + Rueckbindung an Messungen | K1 Flop-Cbet-Dauerfeuer **Prior +6…+12**, verankert an **`sel_guard` +6,1 bb/100 (gemessen, gepaart)** und L1=2,91 · K2 +3…+5 · K3 +2…+4 · K4 +2…+4 · K5 +2…+4 · K6 +1,5…+3 (verankert an L3=1,33) · K7 +1…+2 (spekulativ) | Prioren, **keine Messungen** — und ausdruecklich **nicht addierbar** (K1/K6 teilen sich L1/L3-Masse) | `docs/EXPLOIT_KATALOG.md:22`, `:32`, `:183`, `:188`, `:263` | ja als Prioren-Liste |

#### A9 — exploit_gate: die Absolutwerte je Arm

*Was fehlt:* `02_runs.md:163`, `06_selfplay.md:201-210` und `01_journal.md:176` fuehren nur die **Differenzen**
ON−OFF. Die Absolutwerte zeigen, dass die Engine gegen mehrere Profile in **beiden** Armen deutlich gewinnt —
das relativiert den negativen Exploit-Befund nicht, ordnet ihn aber ein.

| Datum | Was gemessen | Instrument/Kanal | Ergebnis | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-09-09 | exploit ON und OFF je Ligaprofil, absolut | HU, `PokerBot` ohne PRINCE, 600 gepaarte Decks je Profil, Fingerprint bestaetigt | nit **+24,95 / +27,04** · tag **−3,43 / +15,83** · lag **−4,84 / +13,66** · station **−11,62 / +5,73** · maniac **−14,80 / +0,95** · rock **+20,35 / +20,66** · whale **−9,57 / −1,32** · shark **+3,14 / +17,54**; 6-max-Reads **+22,77 / +19,14** | **alle acht HU-Punktschaetzer ≤ 0 in der Differenz, gepoolt ≈ −12 bb/100 (SE ≈ 4,5)** → der Dirichlet-River-Exploit ist fuer diesen Pfad **refutiert**; Produktentscheid: Exploit bleibt in allen Modi AUS | `docs/TRAINER_VERDRAHTUNG.md:77-85`, `:87` | ja |

#### A10 — Autogym-Pilot: 6-max-Positionswerte

| Datum | Was gemessen | Instrument/Kanal | Ergebnis | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-08-16 19:58 | Positions-bb/100 im 6-max-Pilot | `gym_six`, 300 Haende, 3002 gegradete Entscheidungen | **BB +121,57 · BTN +95,13 · HJ +66,42 · UTG +18,50 · CO −107,41 · SB −194,20** | Pilot-Rauschen bei 300 Haenden (BB positiv = Vorzeichen-Alarm gegen jede Poker-Erwartung), **nirgends erwaehnt**; der spaetere 30k-Katalog liest BTN +33,5 / BB −28,9 / SB −29,6 | `data/autogym/report_20260816_195830.json` (Feld `six.position_bb100`); Katalog `data/autogym/journal.jsonl:38` | **nein als Wert** — nur als Beleg, wie stark 300 Haende luegen |

#### A11 — Der heutige Kaggle-Ungueltigkeits-Befund (nach Abschluss der Sammlung)

| Datum | Was gemessen | Instrument/Kanal | Ergebnis | Verdikt | Quelle | Gilt heute? |
|---|---|---|---|---|---|---|
| 2026-09-10 02:38 | Konnte der Champion in den Kaggle-Laeufen ueberhaupt vollstaendig spielen? | Code-Pruefung | **Nein.** `improver._river_spot_und_frage` (`pokerbot/autogym/improver.py:421-433`) gibt `None` zurueck, wenn in der Historie keine Zeile `action=='deal' & street=='river'` steht; das ist der **gemeinsame Unterbau ALLER River-GPU-Guards**, also auch des `river_gpu_guard`, der Teil des Champions `r8_stack` ist (`pokerbot/autogym/pargate.py:134`). Der Kaggle-Adapter schrieb die deal-Marke erst ab Commit `d22d400` (01:59) | **UNGUELTIG (Messfehler im Adapter)** — betroffen sind der Referenzwert (Ende 01:06) und der v9-Lauf (Ende 02:37); der v10-H0-Lauf (Start 02:27) bleibt gueltig; beide Messungen werden wiederholt | `data/autogym/journal.jsonl:124`; `docs/KAGGLE_ARENA.md:147-165`; Commit `e8248e1` | ja — **ueberholt vier Zeilen der Sammlung** |
| 2026-09-10 02:37 | v9 `r10_ernte` gegen Champion (der Lauf selbst, jetzt vollstaendig) | kaggle_arena, 600 gepaarte Decks, 6.913,4 s | **bb100 0,0 · SE 0,0 · nonzero 0/600 · perm_p 1,0 · VERDIKT NEUTRAL** | **kein v9-Verdikt** — die Null ist die Folge des fehlenden Markers (`river_play_guard` haengt an demselben Unterbau), nicht der Beweis, dass der v9-Guard nie feuert | `data/runs/kaggle_v9_vs_champion_2026-09-10.log` (Schlusszeile); Lesart `docs/KAGGLE_ARENA.md:161-165` | **nein** |

---

### (b) Korrekturen

**K1 — Kaggle-A/A: die Sammlung widerspricht sich; beide Seiten haben teilweise recht.**
`02_runs.md:259-260` und `:329-330` erklaeren den Kaggle-Kanal fuer unvalidiert („A/A GEBROCHEN", −37,5) und den
Referenzwert deshalb fuer nicht belastbar, weil er „54 min NACH dem gebrochenen A/A" lief.
`01_journal.md:182`, `05_llm.md:147` und `06_selfplay.md:42` sagen: A/A nach zwei Fixes exakt 0.
**Es gilt 01/05/06 zur Chronologie:** `data/autogym/journal.jsonl:119` traegt ts **2026-09-10 00:15:15** mit
„A/A EXAKT 0 nach zwei Fixes (hand_id je Deck; frische Agenten je Spiegelhaelfte, weil der Bot aus einem
RNG-Strom mischt → A/A war −37,5)", `docs/KAGGLE_ARENA.md:56-63` dokumentiert dasselbe. Der Referenzlauf
(`journal.jsonl:121`) endete **01:06:39** — also **51 min NACH** dem bestandenen A/A, nicht 54 min danach.
`data/runs/kaggle_aa_2026-09-10.log` (mtime 00:12:38) enthaelt ausschliesslich den **Vor-Fix-Lauf**; 02 hat aus
einer Datei generalisiert, die den Fix nicht kennen kann.
**Ehrlicher Restbefund, den kein Teil nennt:** der bestandene A/A hinterliess **keine Logdatei** in `data/runs/`
— er ist nur ueber Journal und Doku belegt.
**Trotzdem ist 02s Verdikt im Ergebnis richtig, aber aus dem falschen Grund:** der Referenzwert ist ungueltig
wegen der fehlenden deal-Marke (K1 unten, C-V1), nicht wegen des A/A.

**K2 — SE des einzigen gueltigen GTOW-Ankers: 9,41, nicht 6,8.**
`01_journal.md:132` rechnet fuer `v4_prince` (n=979) „SE ≈ 6,8 — abgeleitet" aus der Konstante c = 214·√n;
`03_gtow.md:109/112/242` nennt **−21,12 ± 9,41**. **Es gilt 03.** Eigene Nachrechnung ueber
`data/sessions/gtow_hands_1787027076.jsonl` + `_1787033025.jsonl`: n=979, Mittel **−21,115**, per-Hand-SD
**294,3**, SE **9,41** (Stichproben-SD). Die 214er-Konstante ist eine **v2.2-Aera-Groesse** — in
`gtow_hands_1783226155.jsonl` messe ich SD **213,6** bei n=2393 (SE 4,37, exakt der dokumentierte Anker) — und
unterschaetzt die Nacht-2-Streuung um ~28 %. Konsequenz: das Delta zur Kontrolle (+10,23) ist mit der richtigen
SE noch klarer **nicht signifikant**.

**K3 — Journal-Zeilennummern in `06_selfplay.md` an acht Stellen um 1 verschoben.**
Geprueft gegen `data/autogym/journal.jsonl` (Typ je Zeile gelesen). `01_journal.md` zitiert dieselben Eintraege
korrekt — die Sammlung ist an diesen Stellen in sich inkonsistent.

| Fundstelle in 06 | zitiert | korrekt | was auf der zitierten Zeile wirklich steht |
|---|---|---|---|
| `06:169` E3-Detektor +394,9 | `:7` | **J:8** (`SELFTEST-BEFUND`) | J:7 = `L-VORSCHLAG` (river eq 0,00 vs 0,31) |
| `06:171` 6-max-Katalog | `:37` | **J:38** (`RUNDE4-6MAX-KATALOG`) | J:37 = `RUNDE4-DISZIPLIN` |
| `06:79` Replikation +1,11 | `:39` | **J:40** (`REPLIKATION-HETEROGEN`) | J:39 = `RUNDE4-DECISIVE` |
| `06:81` 183k-Anker +8,68 | `:38` | **J:39** (`RUNDE4-DECISIVE`, bb100 8,68 / se 1,28 / n 183.200) | J:38 = 6-max-Katalog |
| `06:182` exploit_jagd | `:30` | **J:31** (`EXPLOIT-JAGD`) | J:30 = `TRANSFER-TEST` |
| `06:241` Transfer-Test | `:29` | **J:30** (`TRANSFER-TEST`) | J:29 = `EXTERNE-BEWERTUNG` (Snowie-Blunder) |
| `06:242` gepaarter Transfer | `:31-32` | **J:32** (`TRANSFER-TEST-GEPAART`) | J:31 = exploit_jagd |
| `06:243` Ursachen-Diagnose (ungeseedete MC) | `:32` | **J:33** (`TRANSFER-TEST-FINAL`) | J:32 = gepaarter Transfer |

Nicht betroffen und korrekt: `06:78` → J:36 (`RUNDE4-SWEEP sel_m15`) und `06:80` → J:41 (`ANWENDEN+NAME`).

**K4 — „der heutige Champion (~−21)" ist eine Spiegel→GTOW-Uebertragung, die das Projekt selbst korrigiert hat.**
`05_llm.md:145` und `03_gtow.md:191` fuehren −21 als Wert des heutigen Champions.
`data/autogym/journal.jsonl:122` (2026-09-10 01:19:25, `KONSULT-SOL-KORREKTUR`) stellt fest: **„−21,12 gehoert
v4/r6_button, nicht v5"**. Der heutige Champion `auslese-v5`/`r8_stack` hat **keinen GTOW-Anker** — das steht in
`03_gtow.md:252` und `01_journal.md:212` bereits richtig. Gleiches gilt fuer die Luecke zur Top-5-Schwelle: die
„≈ 8 bb/100" sind die **Mittelwert**-Lesart; gegen die Rangkriteriums-Untergrenze LCB −14,8 sind es **~6,3**
(`journal.jsonl:122`; korrekt uebernommen nur in `01_journal.md:185`).

**K5 — die als „exakt reproduziert" bezeichneten SE weichen systematisch ab (ddof).**
`03_gtow.md:34-35` behauptet, die Nachrechnungen „reproduzieren die dokumentierten Zahlen exakt". Fuer die
**Mittelwerte** stimmt das (eigene Stichproben bestaetigen es), fuer die **SE** nicht:
`05_llm.md:72` gibt `docs/STATE.md:1092` woertlich wieder (ON −39,92 ± **19,32** / OFF −55,92 ± **28,14**),
`03_gtow.md:68` nennt ±19,36 / ±28,19; derselbe Versatz bei den Smokes (`data/runs/STAND.md:60`:
±**14,30** / ±**22,11** vs `03_gtow.md` ±14,67 / ±22,22). Ursache: Populations- vs Stichproben-SD — die
Doku-Zahlen sind pstdev-basiert, die Nachrechnung stdev-basiert. Es aendert kein Verdikt, entwertet aber das
Wort „exakt".

**K6 — Katastrophen-Zaehlung im v10-Gate G5: beide Lesarten sind korrekt, die Etiketten widersprechen sich.**
`01_journal.md:165` und `06_selfplay.md:134` schreiben „alle 3 Decks ≤ −100 bb"; `02_runs.md:247` schreibt in der
Ergebnisspalte „2 Katastrophen-Decks" und in der Gilt-heute-Spalte „alle drei Decks ≤ −100 bb".
`data/runs/v10/G5_BERICHT.json`: `n_katastrophen: 2` — das Feld zaehlt **beide Richtungen** (+160,79 und −153,20);
`groesste_verluste_chips` listet **drei** Decks ≤ −100 bb (−153,20 / −138,99 / −113,68). Wer den Befund zitiert,
sollte „3 Verlust-Decks ≤ −100 bb, davon 1 als `n_katastrophen`-Negativfall gezaehlt" schreiben.

**K7 — Korrektur am Pruefbericht: der Autogym-Button-Netto-Widerspruch existiert nicht.**
Der Pruefbericht meldet unter U10, `docs/STATE.md:313` nenne Button-Netto **+32,6**, die Quelldatei aber **33,43**.
Das sind **zwei verschiedene Laeufe**: `data/autogym/report_20260816_192735.json` (HU 300 Haende, 1554 + 2023 =
**3.577** Entscheidungen = genau der in STATE:310 beschriebene Pilot) hat `button_netto_bb100` **32,6467** und
`gate_selbsttest` **+2,11 ± 3,28 (n=100)**; `report_20260816_195830.json` (HU 600 Haende) hat **33,43** und
**+1,41 ± 2,18 (n=150)**. STATE.md:310-313 ist korrekt, `06_selfplay.md:169` ist korrekt — sie zitieren nur
verschiedene Laeufe.

**K8 — Korrektur am Pruefbericht: die Fold-Ernte hat sehr wohl eine Quelle.**
Der Pruefbericht fuehrt `02_runs.md:154-155` („preflop 17.928 / flop 15.879 / turn 2268 / river 2880") unter
„ohne Quelle". Die Zahlen stehen als Feld `fold_ernte` in
`data/runs/20260817_020232_exploit_jagd/result.json` (n=100.000 Haende, zusammen mit `jaeger_bb100 8.87`,
`se_ueber_jaeger 6.9`, `sd_netto_bb100 19.85`, `nsd_netto_bb100 -10.99`). Nur die Dateiangabe in 02 zeigt auf die
Nachbardatei `jaeger_einzeln.json` (dort stehen die **je-Jaeger**-Ernten, z. B. preflop 891 / flop 788).

---

### (c) Veraltet — nicht mehr zitieren

**V1 — Kaggle-Referenzwert `+55,83 ± 38,02` (300 Decks, 32,3 % abweichende Decks, ~10,5 s/Deck): UNGUELTIG.**
Gefuehrt als gueltig in `01_journal.md:184`, `02_runs.md:260`, `05_llm.md:146`, `06_selfplay.md:251`.
**Ersatz: keiner — der Lauf wird wiederholt.** Grund (`data/autogym/journal.jsonl:124`; `docs/KAGGLE_ARENA.md:147-160`;
Commit `e8248e1`): der Lauf endete 01:06, die deal-Marke kam erst mit `d22d400` um 01:59 in den Adapter; ohne sie
liefert `improver._river_spot_und_frage` (`improver.py:421-433`) `None`, und damit konnte die GPU-Chirurgie
**des Champions selbst** (`river_gpu_guard` in `r8_stack`, `pargate.py:134`) nicht feuern. Gemessen wurde ein
Champion ohne eines seiner eigenen Bauteile. Erschwerend und in keinem Teil erwaehnt: der Durchsatz dieses Kanals
schwankt um **Faktor 25** (0,41 s/Deck vor dem Commit gegen 1,7–16,8 s/Deck danach, `docs/AIVAT_KAGGLE.md:25`),
und `docs/KAGGLE_ARENA.md:220` macht die Neuerhebung zur **Vorbedingung G0**.

**V2 — „v9-Lauf laeuft / unvollstaendig" (`02_runs.md:261`) und „Kanal lief nicht" (`08_daten.md:49`): ueberholt —
aber der Ersatz ist NICHT der saubere Nullbefund, als der er sich liest.**
Der Lauf ist fertig: `data/runs/kaggle_v9_vs_champion_2026-09-10.log` (Schlusszeile) meldet
`prince[r10_ernte] vs prince[final]`, **n=600, bb100 0,0, nonzero 0, perm_p 1,0, 6.913,4 s, NEUTRAL**.
**Aber:** `journal.jsonl:124` und `docs/KAGGLE_ARENA.md:161-165` erklaeren auch diesen Lauf fuer ungueltig — die
Null kommt vom fehlenden Marker (`river_play_guard` haengt am selben Unterbau), nicht daher, dass der v9-Guard
in diesem Kanal nie feuert. Ebenfalls ueberholt: `kaggle_v10h0_vs_champion_2026-09-10.log` hat inzwischen eine
Fortschrittszeile („[50/150] +0,0 bb/100, **33,10 s/Deck**"); der Lauf ist um 02:51 noch nicht beendet (letzte
Schreibzeit 02:27) und gilt laut Doku als **gueltig**, weil er nach der Marke startete.

**V3 — E7 „`analyze_gtow_hands.py` setzt BB=50, alle bb/100 daraus um Faktor 2 ueberhoeht — OFFEN"
(`03_gtow.md:206`): GEFIXT.**
Ersatz: `research/analyze_gtow_hands.py:16` steht heute auf `BB = 100.0` mit dem Kommentar „der alte Wert 50 war
die SB → alle bb/100 hier um Faktor 2 ueberhoeht (V10_FAKTEN A8/E10, 2026-09-07)". Die zitierte Zeile 141
existiert nicht mehr (Datei hat 80 Zeilen). Veraltet ist nur die Doku (`docs/V10_FAKTEN.md:246-247`).

**V4 — „vs GTOW −19,7" als geltender Stand (`07_sonstige.md:39`, dort als „ja, bindend" markiert).**
Das Zitat ist quellentreu (`docs/SNOWIE_BLUNDER_ANALYSE.md:66-67`), die Quelle ist ueberholt.
**Ersatz:** −19,70 ± 4,37 (n=2393) gilt als **blinds-bug-inflationiert** und ist durch **−30,11 ± 5,51 (n=2899,
gefixter Harness)** als Aeren-Anker ersetzt (`03_gtow.md:81`, `:88-93`); der **einzige heute gueltige** Live-Anker
ist **−21,12 ± 9,41 (n=979)** fuer v4-auf-PRINCE. Das Argument von 07 („Snowie ist der schwaechere
Schiedsrichter") bleibt inhaltlich stehen — nur die Zahl darin ist tot.

**V5 — die Kreuzvalidierung „Analyzer 19,33 ≈ Live-AIVAT −20,09" ohne Bug-Vermerk
(`04_analyzer.md:51`, wiederholt in `:82`).**
Im selben Dokument stellt `04_analyzer.md:189` fest, dass der Blinds-Reihenfolge-Bug **jeden** Live-AIVAT-Lauf
traf, die Exporte/Analyzer-Grades aber **nicht**. Die „zwei unabhaengigen Instrumente" vergleichen also eine
bugfreie Export-Note mit einer bug-inflationierten Live-Zahl. Die **Methode** (Doppelmessung gegen die
„das war nur Varianz"-Lesart) bleibt gueltig; die **Uebereinstimmung** ist als Argument geschwaecht und muss
den Vermerk tragen.

**V6 — „17/17 deep" fuer `tests/test_math_suite.py` (`CLAUDE.md`).**
`07_sonstige.md:107` und `:134` markieren das bereits korrekt als ueberholt. **Ersatz: 20/20.** Heute selbst
nachgelaufen (`python -m tests.test_math_suite`, 2026-09-10): **„20/20 checks passed | fuzz N=400/check"** und
**„UNVERIFIED formula functions (no independent reference yet): 69"**. Ergaenzung, die 07 fehlt: das 20/20 und
der Ledger „72 → 69" stehen schon seit der Blindkampagne in `docs/STATE.md:745-748` — es ist keine neue Messung
von heute, sondern eine seit Wochen nicht nachgezogene Doktrin-Zeile.

---

### (d) Ohne Quelle — mit Vorsicht

**Q1 — „1,3–35 s/Hand je Konfiguration" (`03_gtow.md:12`).** Der Anschluss „2.500 Haende ≈ 8–9 h" ist belegt
(`docs/KAGGLE_ARENA.md:71`, dort als Vergleichstabelle GTOW-API vs lokal). Die Sekundenspanne finde ich nirgends;
die naechstliegende dokumentierte Groesse ist **„~0,3–18 s/Hand je nach Resolver"** und gilt fuer den **lokalen
Kaggle-Kanal**, nicht fuer GTOW (`docs/KAGGLE_ARENA.md:71`). Bis zur Klaerung: nicht zitieren.

**Q2 — „heute (2026-09-10) nachgelaufen" ohne Artefakt (`07_sonstige.md:48`, `:61`, `:85`, `:107-108`).**
Betroffen: `test_icm`, `test_tournament`, `snowie_regress` (5/5), `test_math_suite` (20/20, 69 unverifiziert).
Kein Logpfad, kein konserviertes Artefakt im Repo. **Zwei davon habe ich selbst nachgelaufen und sie stimmen:**
`python -m tests.test_math_suite` → **20/20 checks passed | fuzz N=400/check**, **69 UNVERIFIED formula functions**;
`python -m tests.test_icm` → **„ICM: alle Tests bestanden", Beispiel 50/30/20 → [38.39, 32.75, 28.86]**,
Bubble-Faktor 30v40 = 2,69, Call-Schwelle Bubble 74,6 % (Pot-Odds 45,5 %). `test_tournament` und
`snowie_regress` habe ich **nicht** nachgeprueft — dort steht die Behauptung weiter unbelegt.

**Q3 — „15 % on-tree / ~0,60×Pot" aus dem Skript `_betsize_check` (`05_llm.md:71`).** Das Skript existiert im
Repo nicht (`grep -rn "_betsize_check"` findet nur die Erwaehnung `docs/STATE.md:1091`, dort ausdruecklich als
„scratchpad"). Belegbar ist nur der Doku-Satz, nicht die Messung. Der **mechanische** Teil des Befunds
(15 % → 100 % on-tree nach dem Snap) ist unabhaengig ueber den A/B in `docs/STATE.md:1091` dokumentiert.

**Q4 — entfaellt.** Die Fold-Ernte-Zahlen aus `02_runs.md:154-155` haben eine Quelle; siehe K8.

**Q5 — `08_daten.md` insgesamt: alle Groessen- und Dateizahlen stammen aus einem „os.walk heute" ohne
festgehaltenes Artefakt.** Stichproben des Pruefers waren korrekt (`INDEX.jsonl` 79 Zeilen bei 91 Laufordnern;
65 GTOW-HH-Dateien / 24.050 Haende, alle mit `aivat`; 218 `session_` vs 175 `decisions_`). **Eine Stichprobe ist
inzwischen falsch:** das Journal hat **124** Zeilen, nicht 123 — es ist um 02:38 gewachsen
(`data/autogym/journal.jsonl`, mtime 2026-09-10 02:38:07). Das ist kein Fehler der Sammlung, sondern das
generische Risiko dieser Klasse von Zahlen: sie altern innerhalb einer Sitzung.
