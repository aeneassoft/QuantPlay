# POD_PLAN.md — Gesamtplan der nächsten Vorgänge (Synthese, 2026-08-16)

**Stand bei Abfassung:** Schleife lokal bewiesen (Selbsttest 4/4; E1 9/9 Fraction-Referenzen).
Basis eingefroren (Tag `autogym-basis`). Mess-Doktrin = Mathematik-Benchmark (Orakel) +
Self-Play-Gates + gepaartes A/B neuer-vs-alter-Bot — **kein GTOW in dieser Phase**. Erster
Kandidat `podds_guard` (uniforme Range) NEUTRAL (n=800, +0,31 ± 0,31). Verdrahtet: 7 Checks.
Offen: Welle 1b + Welle 2 (siehe [`AUTOGYM_INVENTUR.md`](AUTOGYM_INVENTUR.md)).

Reihenfolge des Plans: **1. Benchmark komplett → 2. lokale Pflicht-Gates → 3. Pod-Einsatz**,
getragen von den Arbeitspaketen (4.), unter der Versionierungs-Regel (5.), mit offenem Blick
auf die Kipp-Risiken (6.).

---

## 1. BENCHMARK KOMPLETT MACHEN

Ergebnis der Vollständigkeitsprüfung: [`BENCHMARK_VOLLSTAENDIGKEIT.md`](BENCHMARK_VOLLSTAENDIGKEIT.md).
Die zehn Befunde, hier als Arbeitsgrundlage:

1. **95%-These BESTÄTIGT für Entscheidungs-Mathematik:** die Inventur deckt alle 78
   Definitionen (77 eindeutig) der drei Formeldateien exakt ab; die Zählung stimmt.
2. **Größter Fund:** `postflop/strategy_calc_verified.json` trägt je Funktion fertige
   `verify_expr`/`verify_value`-Paare = **66 ungenutzte E1-Referenzen** — ein ~30-Zeilen-Runner
   macht daraus sofort ein maschinelles Verifikationsnetz (→ AP7).
3. **Drei Repo-Domänen nicht inventarisiert, aber montierbar:** (A) ICM/Turnier
   (`strategy/icm.py` + `tournament.py` + `arena/tourney.py` — HART Σ-ICM-Invariante,
   L `icm_call_ohne_odds`, Knob BF_eff), (B) Mess-/Varianz-Statistik aus
   `mathematics_of_poker.json` (443 Einträge, viele mit Python — in der Inventur nie erwähnt),
   (C) MoP-Toy-Game-Anker + Multiway.
4. **Vorschlag neue Stufe „MESS":** die Gate-SE selbst gegen eine Fraction-Closed-Form prüfen —
   die teuerste heute ungeprüfte Zahl des Systems (ANWENDEN > 2·SE hängt daran) (→ AP8).
5. **Multiway-L-Stufe ist erreichbar:** `gym_six` loggt `villain_hole=None`, obwohl ALLE Holes
   bekannt sind; fehlender Baustein = `equity_vs_hands` (Mehrgegner-MC, ~20 Zeilen) (→ AP10).
6. `tests/test_math_suite.py` enthält schon Fraction-Referenzen für W1-4/5/7 (`_alpha_mdf`,
   `_bluff_ratio`, `_rfe`) — **importieren statt neu herleiten**.
7. **Echt fehlend (5 Punkte):** Bankroll/RoR/Kelly-Modul (nur JSON-Strings, un-formalisiert),
   `reverse_implied_odds`-Codefix (verified:false), `equity_vs_hands`,
   Jam-or-Fold-Referenzdaten (aus dem MoP-Modell selbst berechenbar), Rake-Modell (bewusst,
   erst bei Live-Ziel).
8. **Bewusste Ausschlüsse bestätigt korrekt:** 17 range-basierte Funktionen,
   `effective_multi_street_required_equity`, concepts.json (813 Einträge, qualitativ).
9. **Knob-Ergänzungen dokumentiert** (ICM_LEAD_MARGIN, BF_eff-Form fix, icm_pressure_mult);
   Multiway-Unabhängigkeit = deklarierte Näherung, kein Knob.
10. **Reihenfolge:** verify_expr-Runner sofort ($0) → Welle 1 unverändert → MESS-Stufe vor dem
    nächsten Gate → ICM-Gym → `equity_vs_hands` mit Welle 2.

---

## 2. LOKALE PFLICHT-GATES vor dem Pod

Jede Stufe mit **vorregistrierter Erwartung** (nicht nach Sicht der Zahlen justieren). Die
Instrumente sind die Schleife selbst (`python -m pokerbot.autogym.selftest`) und der Improver;
alles hier ist $0 und lokal. Der Pod startet erst, wenn G1–G7 grün sind.

| Gate | Prüfung | Vorregistrierte Erwartung |
|---|---|---|
| **G1** | Selbsttest nach JEDER neuen Verdrahtungswelle (E1 wächst mit: jeder neue Check bekommt seine Fraction-Referenz) | E1 exakt (Toleranz 1e-12), E2–E4 PASS; ein FAIL stoppt die Welle |
| **G2** | verify_expr-Runner (AP7) über `strategy_calc_verified.json` | 66/66 PASS oder je Ausnahme ein dokumentierter Ausschlussgrund (wie `reverse_implied_odds` verified:false) |
| **G3** | MESS-Stufe (AP8): die `duplicate_ab`-SE gegen die Fraction-Closed-Form der gepaarten Stichprobenvarianz, auf konstruierten Daten | Übereinstimmung < 1e-12; zusätzlich SE(n) ~ 1/√n über n = 100/400/1600 |
| **G4** | AP1 `tracker_podds_guard` durchs Gate (n=800 Decks) | ANWENDEN (bb100 − 2·SE > 0) ODER zweites NEUTRAL ⇒ Familie „River-Call-Guard" erschöpft, Journal-Eintrag, weiter mit F-Leads |
| **G5** | E5-Vorstufe LOKAL: Multiprocessing-Skalierung auf den lokalen Kernen (Worker = physische Kerne) | ≥ 0,7× lineare Skalierung pro Kern (heute bewiesen sind nur 580 Hände/min single-process) — fällt das, ist die Pod-Rechnung Makulatur, BEVOR Geld fließt |
| **G6** | Determinismus: zwei Läufe gleicher Seed ⇒ identische Orakel-Zählungen + identische Gate-Zahl | byte-identisch (PYTHONHASHSEED-Lektion; set-Iteration ist die bekannte Falle) |
| **G7** | Journal-Hygiene: Dedupe der Top-L-Vorschläge aus gespiegelten Durchgängen (bekannt offen; im Journal sichtbar: 112,12 doppelt) | nach Fix: identische Hand ⇒ genau EIN Lead-Eintrag |

Zusatz-Beobachtung unter G1: die Paar-Drift war zweimal in Folge positiv (+294 ± 195, dann
+106,8 ± 70,3 — je 1,5 SE). Formal PASS, aber ein dritter positiver Lauf in Folge ist ein
vorregistrierter Untersuchungs-Trigger (Sitz-Asymmetrie? OppModel-Persistenz?) — VOR dem Pod
klären, sonst stehen alle Gate-SEs auf einer unverstandenen Asymmetrie.

---

## 3. DER POD-EINSATZ ($140, RunPod Secure Cloud, CPU-Maxcore)

### 3.1 Preislage (recherchiert 2026-08, Listenpreise; Konsole vor Deploy verifizieren — Preise schwanken)

| Instanz | Kerne | $/h | $/vCPU-h | $140 kauft | Hände (@E5-Skalierung ~156/min/Kern) |
|---|---|---|---|---|---|
| CPU compute-opt. (cpu3c/cpu5c) | 2/4/8 vCPU pro Pod ($0.06/0.12/0.24 pro h) | $0.24 @8vCPU | **~$0.030** | 583 h @8vCPU | ~44 Mio @64 Kernen (8 Pods parallel) |
| CPU 64 Kerne aggregiert (8×8er ODER 1 großer, falls Konsole >8 anbietet) | 64 | ~$1.92 | $0.030 | **~73 h** | ≥10.000/min (E5-Soll) → ~44 Mio |
| H100 PCIe | 16 vCPU | $2.89 | $0.181 | 48 h | ~7 Mio |
| H100 SXM | 20 vCPU | $3.29 | $0.165 | 42 h | ~8 Mio |
| H200 | 12–24 vCPU | $4.39–4.59 | ~$0.19 | ~31 h | ~5–9 Mio |
| B200 | 26–28 vCPU | $6.79 | $0.24 | 20 h | ~8 Mio (CPU-seitig) |

**Szenarien ($140):**
- **A — nur-CPU-Maxcore: ~73 h à 64 Kerne.** Bei E5-Soll (≥10k Hände/min) ≈ 44 Mio Hände. Ein
  Gate-Experiment à 2×50k gepaarte Hände ≈ 10 min → **~400 Gate-Experimente**. Klarer Sieger:
  5–6× mehr Kern-Stunden pro Dollar als jeder GPU-Pod.
- **B — GPU-Pod als CPU-Quelle (H100 SXM, 20 vCPU): 42 h ≈ 8 Mio Hände / ~75 Experimente.**
  Nur sinnvoll, wenn dieselbe Session AUCH GPU braucht — aktuell nicht (kein GPU-Training;
  AUTOGYM ist reine CPU-Last).
- **C — gemischt: $115 CPU (≈60 h Maxcore, ~36 Mio Hände) + $25 Reserve** (≈7 h H100 SXM) für
  einen späteren GPU-Bedarf (z.B. Leaf-Net des v4-Pfads).

**Empfehlung: Szenario C.** „Leistungsstärkster Pod" heißt für UNSERE Last (CFR/Self-Play)
Kerne/Dollar, nicht GPU — B200 wäre 8× teurer pro Kern, und die CLAUDE.md warnt ohnehin vor
sm_100. Achtung Instanz-Kappe: die Doku zeigt CPU-Pods bis 8 vCPU → 64 Kerne = 8 parallele
Pods (Preis identisch); `infra/runpod_run.py` braucht dann Multi-Pod-Handling + je Pod
tarball-in/results-out. Falls die Konsole größere CPU-Instanzen listet, die nehmen (weniger
Orchestrierung).

### 3.2 Budget-Aufteilung: die nummerierten Runs

Regeln über allen Runs: **ALWAYS `--kill`** (8 Pods = 8 Kills, atexit+finally), ein
scp-Tarball pro Richtung, 2-Node-Doktrin (kein CPU/GPU-Mix auf einer Box), Community Cloud
meiden (Preemption zerstört gepaarte Läufe), **Ergebnisse + Journal VOR dem Kill zurück-scp'en**
(Lehre aus dem GRPO-Pull-Verlust), lange Sessions statt vieler kurzer (Setup-Steuer).

| Run | Ziel | Dauer | Kosten | Abbruchkriterium | Vorregistrierte Erwartung |
|---|---|---|---|---|---|
| **R1 PILOT** | E5-Gate messen: Hände/min auf 8 vCPU + Orchestrierungs-Smoke auf 2 Pods (tarball rein, Journal raus, beide Kills sauber) | 1 h | ~$2 | < 60% des Solls (< ~94 Hände/min/Kern) → Kill, lokal optimieren, Re-Pilot | ≥ 130 Hände/min/Kern (≈ 156 · 0,85), hochgerechnet ≥ 8.300/min auf 64 Kernen; HART = 0 |
| **R2 KALIBRIER-BLOCK** | Große-n-Referenz der Basis (HU ≥ 50k Paare → Referenz-SE), 6-max-Positions-Ledger auf n ≥ 1.000/Position, Welle-1b-Checks (AP2–AP6) auf großem n validieren | 15 h à 64 Kerne | ~$29 | HART > 0 oder E4-Verletzung auf dem Pod (Schleife kaputt) → sofort Kill + lokales Debugging | Referenz-SE der Basis < 1 bb/100; mdf_flop-Befund zerlegt sich per Sizing-Bucket ohne zu verschwinden (Summen-Konsistenz) |
| **R3 KANDIDATEN-LEITER** | Alle lokal überlebenden Kandidaten (AP1, spätere Guards) gepaart vs `autogym-basis` auf n = 5.000–50.000 Decks; nur > 2·SE-Sieger bekommen Namen | 20 h | ~$38 | 3 Familien in Folge NEUTRAL → STOPP; nicht Stunden nachwerfen, sondern Mess-Kanal überdenken (Abschnitt 6, Punkt 2) | ≥ 1 Kandidat ANWENDEN mit Effekt > 2·SE; jedes Verdikt im Journal |
| **R4 WELLE-2 / MULTIWAY** | Welle-2-instrumentierte Langläufe (hand_id/hand_result/Line-Aggregationen), Multiway-L via `equity_vs_hands`, ICM-Gym-Erstlauf falls AP-Stand es hergibt | 20 h | ~$38 | Welle-2-Instrumentierung nicht lokal G1-grün → Run startet NICHT (kein „auf dem Pod fertig bauen") | Implied-Odds-Familie liefert erste bezifferte L-Leads; Multiway-Lead-Rate vergleichbar zur HU-Größenordnung (Plausibilitätsanker) |
| **RESERVE** | $25 GPU (≈7 h H100 SXM, nur bei konkretem GPU-Bedarf, z.B. v4-Leaf-Net) + ~$8 CPU-Puffer für Re-Pilots/Nachmessungen | — | ~$33 | wird ohne konkreten, vorregistrierten Bedarf NICHT angefasst | — |

Summe: ~$107 verplant + ~$33 Reserve = $140.

---

## 4. DIE ARBEITSPAKETE (Backlog, 10 Pakete)

Abgeleitet aus `journal.jsonl`, `AUTOGYM_INVENTUR.md` (W1b/W2), dem podds_guard-NEUTRAL und
der Vollständigkeitsprüfung (Abschnitt 1).

**Vorab-Befund zur Kernfrage (Tracker-Range): kein neues Plumbing nötig.**
`HeadsUpGame.state()` liefert `"history"` (pokerbot/engine/game.py:304), und
`RangeTracker(advisor=None).build(state)` (pokerbot/strategy/range_tracker.py:279)
rekonstruiert die Range **zustandslos pro Entscheidung** aus genau diesem State-Dict. Der
Wrapper `d(st)` im Improver bekommt den vollen State bereits — also:
`t = RangeTracker().build(st)`; Villain-Combos mit Gewichten liegen in
`t.range[1 - st["to_act"]]` (dict {(c1,c2): w}); Equity via `equity_vs_weighted_range`
(pokerbot/engine/equity.py:79 — **am River exakte gewichtete Enumeration, Null Varianz**,
besser als die 40-Combo-MC-Stichprobe des alten Guards); Vertrauens-Gate via
`t.confidence(villain)` (0.2–1.0, Inverse-Herfindahl-Kollaps-Schutz).

**AP1 — podds_guard v2 (Tracker-Range) [höchste Priorität]**
Ziel: Journal-Leads `call_unter_pot_odds` (Top-Severity 112/99/96/92 bb, alle river, eq 0.00
vs nötig 0.23–0.31) mit legaler Information angreifen; die uniforme Range war zu grob
(NEUTRAL +0,31 ± 0,31, n=800).
Dateien: `pokerbot/autogym/improver.py` (neue Fabrik `tracker_podds_guard`); nur lesend:
`range_tracker.py`, `equity.py`.
Mechanik: nur river + `to_call>0` + `confidence ≥ 0.5` (sonst kein Override); fold wenn
`eq_weighted + margin < equity_needed_to_call(pot, to_call)`; margin 0.02 beibehalten.
Erwartung (vorregistriert): ANWENDEN = bb100 − 2·SE > 0 bei n=800 Decks. Zweites NEUTRAL ⇒
Familie „River-Call-Guard" erschöpft, Journal-Eintrag, weiter mit F-Leads (mdf_flop
OVER-FOLD 0.61 vs 0.32 ist der größere dokumentierte Befund).
Laufzeit: lokal ~3–5 min (1.600 Hände; Tracker-Build nur an River-Call-Knoten); Pod: <1 min.
Deps: keine.

**AP2 — MDF/Alpha-Paar je Sizing-Bucket (W1-4+5)**
Ziel: `facing_bets` von je-Straße auf je-(Straße × Bucket [0.33, 0.66, 1.0, 1.5, ∞])
verfeinern + Alpha-Check von der Bettor-Seite (gegenseitige Verifikation).
Dateien: `oracle.py` (`finalize_frequencies`; `facing_bets` um die Bettor-Zeile erweitern),
Fraction-Anker aus `tests/test_math_suite.py` importieren (Befund 6, Abschnitt 1).
Erwartung: Identität alpha + MDF = 1 exakt per Fraction (Selbsttest-PASS); der bestehende
mdf_flop-Befund muss sich per Bucket zerlegen, ohne zu verschwinden (Summen-Konsistenz);
N_MIN 30 je Bucket.
Laufzeit: +0 s (reine Aggregation); Validierungslauf 900 Hände ≈ 75 s lokal.
Deps: keine.

**AP3 — F-Severity beziffern (W1-11)**
Ziel: `fold_frequency_exploit_ev` / `exploit_fold_deviation_ev` füllen `severity_bb` der
F-Verdicts (heute hart 0.0) — macht F-Leads gegen L-Leads priorisierbar.
Dateien: `oracle.py`.
Erwartung: Nullstelle exakt bei f = alpha (Fraction); Anker 0.7·100 − 0.3·50 = 55; auf dem
Referenzlauf bekommt mdf_flop severity_bb > 0.
Laufzeit: +0 s. Deps: AP2 (gleiche Datenbasis, sinnvoll zusammen).

**AP4 — Raise-Knoten-Alpha/MDF (W1-6)**
Ziel: eigenes Band für `node_typ='raise'` — das verdrahtete MDF-Band deckt nur Bets; Raises
haben eigene Alpha-Geometrie (`required_fold_fraction_for_raise`,
postflop_formulas.py:82).
Dateien: `oracle.py` + Record-Feld `node_typ` an beiden Call-Sites (HU aus
history/current_bet, 6-max aus obs — Welle-1-Feld, kein Engine-Umbau).
Erwartung: 300/(300+150) = 2/3 exakt per Fraction; Identität mit
`breakeven_fold_equity_pure_bluff`; eigenes RAISE_N_MIN 30 (Raise-Knoten sind dünner besetzt
— unter n=30 kein Urteil).
Laufzeit: +0 s. Deps: AP2 (Bucket-Maschinerie wird geteilt).

**AP5 — River-Ratio + Pool-Bluff-Fraktion (W1-7+8)**
Ziel: jede Hero-River-Bet in Rückschau via villain_hole als Value (eq>0.5) / Bluff
klassifizieren; aggregiertes Verhältnis je Sizing-Bucket vs B/(P+B); spiegelbildlich die
Bluff-Fraktion des BETTORS vs q* = B/(P+2B) (`bluff_catcher_call_ev`) → Over-Fold-/
Over-Call-Vorschläge für die Verteidiger-Seite. HU-only.
Dateien: `oracle.py`.
Erwartung: B=P ⇒ Bluffanteil 1/3 (Docstring-Anker); Kette q=B/(P+2B), r=B/(P+B) per
Fraction (in test_math_suite gepinnt, importieren); RATIO_BAND 0.15, Q_BAND 0.10, N_MIN 30,
VALUE_EQ_SCHWELLE 0.5 fix (keine Stellschraube).
Laufzeit: +wenige s (Equity nur an River-Bet-Knoten). Deps: AP2 (Buckets).

**AP6 — Commitment + Setmine (W1-9+10)**
Ziel: `commitment_margin_by_spr` (Fold trotz eq ≥ spr/(1+2spr)+Marge; Stack-off weit
darunter) + `set_mining_implied_odds_margin` (Pocket-Pair-Call preflop mit eff/call <
Schwelle — läuft HU UND 6-max, kein villain_hole nötig).
Dateien: `oracle.py`; das Feld `effective_stack` wird an BEIDEN Call-Sites schon geloggt
(gym_hu.py:48, gym_six.py:50) — reine Orakel-Arbeit.
Erwartung: Fraction-Identität S/(P+2S) = spr/(1+2spr) = equity_needed_to_call(P+S, S);
Setmine-Anker call 2 / eff 30 / sf 0.8 ⇒ exakt 0 auf der Schwelle; SETMINE_FAKTOR 12
[10, 15].
Laufzeit: +0 s. Deps: keine.

**AP7 — verify_expr-Runner ($0, sofort)**
Ziel: die 66 fertigen `verify_expr`/`verify_value`-Paare aus
`knowledge_base/postflop/strategy_calc_verified.json` maschinell ausführen — das größte
ungenutzte Verifikationsnetz des Repos (Abschnitt 1, Befund 2).
Dateien: neu `pokerbot/autogym/verify_runner.py` (~30 Zeilen) + Aufruf im Selbsttest (E1-Anbau).
Erwartung: 66/66 PASS oder je Ausnahme ein dokumentierter Grund; `reverse_implied_odds`
(verified:false, defekter dataclass-Dekorator) bleibt bis zum Codefix ausgeschlossen.
Laufzeit: Sekunden. Deps: keine — **vor allem anderen ausführbar.**

**AP8 — MESS-Stufe: die Gate-SE selbst prüfen**
Ziel: die teuerste ungeprüfte Zahl des Systems absichern — ANWENDEN > 2·SE hängt an der
SE-Berechnung von `duplicate_ab`. Closed-Form der gepaarten Stichprobenvarianz per Fraction
auf konstruierten Daten + SE(n) ~ 1/√n über n = 100/400/1600; perspektivisch die
Varianz-Statistik aus `mathematics_of_poker.json` (443 Einträge) anbinden.
Dateien: `selftest.py` (neue Erwartung E7/MESS), lesend `pokerbot/benchmark/duplicate.py`.
Erwartung: Übereinstimmung < 1e-12; ein FAIL hier entwertet ALLE bisherigen Gate-Verdikte →
darum VOR dem nächsten Gate (G3).
Laufzeit: Sekunden. Deps: keine.

**AP9 — Welle 2: hand_id / hand_result / Line-Historie**
Ziel: Record-Schema um `hand_id`+`decision_idx` (Verknüpfung), `hand_result` (Netto-bb,
Showdown, Gewinner) und `line` (Aktionsfolge je Straße) erweitern → Implied-Odds-Familie
(`implied_odds_extra_needed`, `call_ev_with_implied_gain`, `reverse_implied_odds` als
Aggregat), empirisches `equity_realization` (Knob-Kalibrierung statt Prior),
Check-Raise-Familie; dazu der Dedupe-Fix im Improver (gespiegelte Durchgänge, G7).
Dateien: `gym_hu.py`, `gym_six.py` (Call-Sites), `oracle.py`, `improver.py`.
Erwartung: G1 grün mit erweitertem Schema; erster bezifferter Implied-Odds-Lead auf dem
Referenzlauf; Journal ohne Duplikate.
Laufzeit: Schema +0 s; neue Aggregationen wenige s. Deps: AP2–AP6 (Aggregations-Maschinerie).

**AP10 — equity_vs_hands + Multiway-L (+ ICM-Gym als Anschluss)**
Ziel: `gym_six` loggt heute `villain_hole=None` (gym_six.py:48), obwohl die Table ALLE Holes
kennt — mit `equity_vs_hands` (Mehrgegner-MC, ~20 Zeilen in `pokerbot/engine/equity.py`)
wird die komplette L-Stufe multiway-fähig. Danach ICM-Gym (Abschnitt 1, Befund 3A:
Σ-ICM-Invariante als HART, `icm_call_ohne_odds` als L) auf `arena/tourney.py`.
Dateien: `equity.py`, `gym_six.py`, `oracle.py`; ICM: neu `pokerbot/autogym/gym_icm.py`.
Erwartung: Multiway-Lead-Rate in der Größenordnung der HU-Rate (Plausibilitätsanker);
ICM-HART = 0 auf der gepaarten SNG-Arena.
Laufzeit: MC-Kosten ~n_opponents-fach an L-Knoten; Pod-Run R4. Deps: AP9 sinnvoll vorher.

---

## 5. VERSIONIERUNG

1. **Basis-Tag-Regel:** vor JEDER Veränderung wird eingefroren (aktuell Tag `autogym-basis`).
   Jeder Kandidat mit lokalem ANWENDEN wird GEPAART gegen den eingefrorenen Basis-Bot gemessen
   (E6) — nie gegen einen bewegten Stand.
2. **Namensvergabe nur bei ANWENDEN:** einen Namen (Git-Tag) bekommt ein veränderter Bot
   ausschließlich, wenn das gepaarte Gate vs Basis ANWENDEN sagt (Effekt > 2·SE UND nicht
   unter −1 bb/100). NEUTRAL/VERWERFEN erzeugen Journal-Einträge, keine Namen. Der benannte
   Bot trägt seine gepaarte Zahl im Tag-/Journal-Text.
3. **Journal-Pflicht:** nichts geschieht still — jede Runde, jeder Vorschlag, jedes Verdikt →
   `data/autogym/journal.jsonl`. Pod-Läufe schreiben ihr Journal auf dem Pod und es wird VOR
   dem Kill zurück-scp't. Jeder Gate-Eintrag trägt den Config-Fingerprint (Git-Commit +
   Knob-Werte + Flags — Lektion: der alte Fingerprint übersah 13 Flags).
4. Orakel-Knöpfe bleiben Mess-Konfiguration (für den Improver gesperrt); jede Hand-Drehung
   braucht Begründung + Journal-Eintrag (Goodhart-Schutz, Sicherheits-Kontrakt Punkt 2).

---

## 6. WAS DEN PLAN KIPPEN KANN (ehrlich)

1. **E5-Skalierung fällt.** Bewiesen sind 580 Hände/min single-process; die ≥10.000/min auf
   64 Kernen sind eine ANNAHME (Multiprocessing-Skalierung). Fällt G5 lokal oder R1 auf dem
   Pod (< 60% Soll), ist die ganze Pod-Rechnung Makulatur — dann lokal optimieren
   (Prozess-Pool, EQ_ITERS-Budget, Tracker-Memoisierung), nicht Budget nachwerfen. Verlust
   dann: ~$2 Pilot.
2. **Der Mess-Kanal ist zu unempfindlich für seltene Knoten.** podds_guard feuert nur an
   River-Call-Knoten — seltene Ereignisse × kleiner Effekt = Effekt < SE trotz echter
   Verbesserung. Zweites NEUTRAL bei AP1 kann also auch „Kanal zu grob" heißen, nicht nur
   „Familie leer". Gegenmittel (dann vorregistriert nachrüsten): Feuerrate zuerst messen;
   gepaarte Auswertung NUR über Hände, in denen der Guard feuert (Varianzreduktion auf den
   Behandlungs-Knoten).
3. **Self-Play-Blindheit.** Alle Gates messen neuer-vs-alter-Bot im Selbstspiel. Ein Guard
   kann selbstspiel-NEUTRAL sein und vs GTOW trotzdem gewinnen/verlieren — die Doktrin
   verschiebt GTOW bewusst nach hinten, aber die finale Wahrheit über die Treppe
   (−19,70 → −15 → −10) liefert nur die GTOW-Messung. Das Risiko ist eingepreist, nicht weg.
4. **Rückschau-Bias + Seesaw-Gefahr.** L-Leads vergleichen gegen die EINE tatsächliche
   Gegnerhand; Guards, die daraus zu aggressiv Folds erzwingen, machen den Bot lesbarer
   (v8-Lektion: Abflachen des Mixings brach live auf −58). Jeder Guard braucht darum das
   Gate UND die Frage: reduziert er die Unvorhersehbarkeit?
5. **Paar-Drift-Anomalie.** Zweimal in Folge positive Drift (je 1,5 SE) — noch PASS. Bestätigt
   sich eine echte Sitz-Asymmetrie, sind die SE-Annahmen der Gates verletzt; vorregistrierter
   Trigger: dritter positiver Lauf ⇒ Untersuchung VOR weiterem Pod-Verbrauch.
6. **Orchestrierungs-Risiko 8 Pods.** Multi-Pod-Handling in `infra/runpod_run.py` ist
   ungebaut; ein Fehler dort (hängender Pod, verlorenes Journal) frisst Budget. Gegenmittel:
   R1 enthält den Orchestrierungs-Smoke; Ergebnisse VOR Kill; atexit+finally-Kills; Konsole
   auf größere CPU-Instanzen prüfen (1 Pod schlägt 8).
7. **Preis-/Verfügbarkeitsdrift.** Die Tabelle ist Stand 2026-08 (Listenpreise); vor jedem
   Deploy in der Konsole verifizieren. Secure Cloud kann ausgebucht sein; Community Cloud
   bleibt trotzdem tabu (Preemption zerstört gepaarte Läufe).
8. **Formel-Fundament.** Fällt der verify_expr-Runner (AP7) oder die MESS-Stufe (AP8), steht
   ein Teil der bisherigen Verdikte in Frage — darum laufen beide VOR dem nächsten Gate und
   VOR dem Pod. Das ist der billigste Punkt des Plans, an dem er kippen darf.

Sources (Preise): [RunPod Pricing](https://www.runpod.io/pricing) ·
[getdeploying RunPod](https://getdeploying.com/runpod) ·
[RunPod CPU types (docs)](https://docs.runpod.io/flash/configuration/cpu-types) ·
[Flexprice RunPod Guide](https://flexprice.io/blog/runprod-pricing-guide-with-gpu-costs) ·
[Spheron H100 2026](https://www.spheron.network/blog/runpod-h100-pricing-2026/)
