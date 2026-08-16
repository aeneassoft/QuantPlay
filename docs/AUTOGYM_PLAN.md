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
| **E6** | **BASIS-Anker (User-Entscheid 2026-08-16):** jeder Kandidat mit lokalem ANWENDEN wird GEPAART gegen den eingefrorenen Basis-Bot gemessen (Tag `autogym-basis`) | Kandidat > Basis mit Effekt > 2·SE; GTOW nur zur Not | offen |

E6 ist die einzige Stufe, die zählt — E1–E5 existieren, damit E6-Messungen nie auf einer
kaputten Schleife stehen. VERSIONIERUNG: vor jeder Veraenderung einfrieren (Tag), ein fertiger
veraenderter Bot bekommt einen NAMEN (Tag) und seine gepaarte Zahl gegen die Basis.

## Verdrahtungs-Backlog (Orakel-Manifest fuehrt live Buch)

v0 verdrahtet: `equity_needed_to_call` (L), `minimum_defense_frequency` (F), Chip-Erhaltung
(HART), `free_fold` (P). **Die Vollinventur ist da: [`AUTOGYM_INVENTUR.md`](AUTOGYM_INVENTUR.md)**
— 77 eindeutige Funktionen kategorisiert (1 P / 16 F / 14 L / 19 Kontext / 10 Knob / 17 ehrlich
nicht verdrahtbar, weil das Gym Haende liefert, keine Ranges). **Welle 1 = 10 Checks + 2
Instrumentierungen ohne Engine-Umbau** (nur Record-Erweiterungen: effective_stack,
call_closes_action, node_typ, n_opponents); empfohlene Reihenfolge 1→3 (per-Entscheidung),
4+5 (gegenseitig verifizierendes MDF/Alpha-Paar), 6→8 (Aggregations-F), 9+10. Welle 2 braucht
hand_id/decision_idx, hand_result und die Line-Historie. Das Knob-Register (mit Schranken)
steht in der Inventur; bindend bleibt: Orakel-Knoepfe sind Mess-Konfig, nicht Improver-Gebiet.

## ZWEI DISZIPLINEN — die 6-max-Paritaet (User-Erinnerung 2026-08-16, bindend)

Die Kandidaten-Schleife misst bisher NUR Prince-HU (duplicate_ab). Der 6-max-Kern
(SixMaxBot-Oekologie) wird vom Orakel gegradet, hat aber KEIN Gate. Arbeitspaket
**AP-6MAX (vor der Basis-Rotation Runde 4):** ein gepaartes 6-max-Gate — gleiche Karten,
Kandidat rotiert ueber die Sitze (6 Rotationen je Deal = Positions- und Kartenkuerzung),
Rest des Tischs = eingefrorene sixmax-Basis; dann laufen dieselben Guards (sel/lizenz —
beide sind range-frei genug: die Tracker-Range braucht HU-Posts, 6-max nutzt den
Positions-Prior aus der Snowie-Bruecke make_seeded_tracker). Versionierung getrennt:
eigene Basis-Tags (autogym-basis-6max), eigene Namen. Die Disziplinen teilen Orakel,
Journal, Run-Ablage und Erwartungs-Leiter.

### AP-6MAX-BEOBACHTUNG — erst Struktur-Katalog, dann Mathematik (User-Design 2026-08-16)

Methode wie beim Bluff-Lizenz-Katalog: DESKRIPTIV vor NORMATIV. Der 6-max-Bot spielt gegen
sich selbst; aufgezeichnet wird die GESPRAECHSSTRUKTUR jeder Hand (Klassenraum-Analogie:
Meldereihenfolge = Position, Wortmeldung = Aktion, das Gespraech kollabiert auf 2-3 Stimmen):
  (1) Knoten-Taxonomie: Open/Call/3bet/Squeeze/Multiway-Pot je Position x Anzahl aktiver
      Spieler x Strasse — WELCHE Entscheidungstypen kommen wie oft vor (die Frequenz-Landkarte
      bestimmt, wo Mathematik ueberhaupt Hebel hat, AP8-Lektion);
  (2) Kollaps-Dynamik: 6 -> n Spieler je Strasse, wer traegt die Verteidigungslast (MDF ist
      multiway NICHT wohldefiniert pro Spieler — die Last teilt sich, das ist neue Mathematik);
  (3) Equity-Schwellen multiway: noetige Equity vs N Caller (Formelsammlung hat die Bausteine);
  (4) Positions-Range-Struktur: die realisierten Ranges je Sitz als empirischer Prior
      (Snowie-Bruecken-Lektion formalisiert).
Ertrag: der 6-max-Struktur-Katalog -> daraus die 6-max-Orakel-Checks (welche HU-Checks
uebertragen, welche multiway neu definiert werden muessen) -> dann erst Kandidaten.
Instrument: gym_six + entscheidungs_logger (gebaut) + neue Struktur-Felder (n_active je
Strasse, Aggressor-Position, Knoten-Typ).

## Kandidaten-Runde 1 abgeschlossen (2026-08-16 abend) — beide Familien sauber erledigt

**G5 BESTANDEN:** 24 Kerne lokal, pargate haelt **2.459 Decks/min ueber 40 min** (~4.900 Haende/min;
Skalierung ~1,0x/Kern). Fuer Einzel-Gates ist der Pod damit unnoetig — die $30 bleiben fuer R3.
**podds_guard (River):** Kanal zu selten (0,015 Knoten/Hand, ~24 Knoten je 1.600 Haende) — die
NEUTRAL-Urteile waren "Kanal zu grob", nicht "kein Effekt". Familie pausiert bis konstruierte Decks.
**mdf_guard (Flop):** dreifach gemessen, 400 → 1.200 → **99.000 Decks: −3,26 ± 2,19 → NEUTRAL**
(95%-Band [−7,6, +1,1], ~1,5 SE unter null). Vierter Datenpunkt der Doktrin: Frequenz-Matching ohne
SELEKTION druckt nicht. Kein Name vergeben, Basis bleibt.
**Lehre fuer Kandidaten-Runde 2:** Kandidaten muessen Selektion tragen (WELCHE Haende weiterspielen
— Tracker-Range/made-hand-Read), nicht Frequenz; und der Mess-Kanal wird VOR dem Bau vermessen (AP8).

## Erster voller Lauf NACH den Review-Fixes (2026-08-16, lokal, 75 s) — der Referenz-Lauf

900 Haende, 6.080 gegradete Entscheidungen. **HU (600, 4-fach gekreuzt):** HART 0 · P 0 · L 62
(2,0% Lead-Rate) · F 1 · Button-Netto **+33,4 bb/100** (Vorlauf +32,6 — die Groesse ist stabil) ·
Paar-Drift +106,8 ± 70,3 (1,5 SE, PASS; zweiter Lauf in Folge positiv → beobachten).
**6-max (300, reparierte Oekologie):** HART 0 · P 0 · F 1; Positions-Ledger bei n=50/Position
noch Rauschen (BB +122 unplausibel, SB −194 plausibel — erst ab ~1.000 Haenden lesbar).
Gate-Selbsttest exploit-OFF +1,4 ± 2,2 → NEUTRAL (konsistent ueber drei Laeufe).
Bekannte Kleinigkeit: Top-L-Vorschlaege enthalten Duplikate aus gespiegelten Durchgaengen
(Dedupe im Improver offen).

## Erste Messwerte (Pilot 2026-08-16, lokal, 52 s)

HU 300 Hände: HART 0 · P 0 · L 35 (Rückschau-Calls bis 112 bb unter Pot-Odds) · F 1 ·
Button-Netto +32,6 bb/100 (kartenbereinigter Positionswert = neue Benchmark-Größe) ·
Paar-Drift +294 ± 195 (1,5 SE, verträglich mit 0 — mehr Paare nötig). 6-max 200 Hände:
HART 0 · P 0 · F 2 (u. a. mdf_flop). Gate-Selbsttest exploit-OFF vs ON: +2,1 ± 3,3 → NEUTRAL.

## Paper-Verankerung 2026 (2026-08-16 — drei Extraktionen trianguliert)

Quellen: Brown VNM-169 (`knowledge_base/theory/brown_vnm_169.md`, Vollextraktion ssrn-6709840),
SPIRAL ICLR 2026 (`docs/SPIRAL_NOTES.md`), Diniz PokerBench-SFT (PDFs in `books/papers/Poker Math 2026/`).

### 1. Brown-Checks in den Verdrahtungs-Backlog (V1–V4, spezifiziert in brown_vnm_169.md §4)

| Check | Stufe | Kern | Priorität |
|---|---|---|---|
| **V1 `value_ordnung`** | F | Value-Bets je Bucket = obere Menge der Equity-Ordnung (Spearman-Anker 0,98); Brown-27-Bluffklassen AUSGENOMMEN | **★ range-frei → VOR Welle 1b einreihen** (nach den laufenden per-Entscheidungs-Checks, vor den restlichen Aggregations-F) |
| **V2 `fold_ordnung`** | F | Verteidigungs-Spiegel: Continue-Menge = Spitze der Posterior-Ordnung; deckt die Seesaw-Bruchklasse (v8) OHNE Frequenz-Vorgabe | mit V1 (teilt Referenz + Felder) |
| **V3 `bluff_struktur`** | F | Bluffs aus der Zyklus-Region (Equity 0,36–0,50), Junk-Anteil > Band = Befund | nach Welle 1 (braucht Rückschau/villain_hole) |
| **V4 `bluff_persistenz_hoch_b`** | L | Kurz-Persister/Junk-Bluffs bei Bet-to-Pot ≥ 2 = Einzel-Lead | nach V3 |

Fraction-Referenz-Pflicht (E1) gilt: Referenz-Ordnung = **exakt enumerierte** 169er-Equities
((2·Siege+Splits)/(2·1.712.304)) — das Repo-Asset `knowledge_base/ranges/preflop_eqmatrix.json`
ist MC sims=600 und NICHT referenz-tauglich; vor V1-Verdrahtung einmalig exakt enumerieren.
Knob-Schranken (ORDNUNG_RHO_MIN [0,80; 0,98] Start 0,90 u. a.) stehen in brown_vnm_169.md;
Orakel-Knöpfe bleiben Improver-gesperrt. Auf der BLUFF-Seite ist Ordnungs-Treue ausdrücklich
NICHT zu erwarten (Persistenz-Korrelation −0,42) — ein Orakel, das Bluffs an der Equity-Ordnung
misst, misst falsch.

### 2. Bindende Kandidaten-Entwurfsregel: Bluff-Auswahl STRUKTURELL, nie Quote

Brown, unabhängig von unserer Messung: **0 von 169 Händen sind Bluffs in allen vier
Matrix-Varianten** — WELCHE schwache Hand blufft, ist reine Matrix-Geometrie (Zyklus-Position/
Suitedness; im Mehrstraßen-Spiel: Blocker/Board/Sizing), nie Schwäche und nie eine
Frequenz-Zielzahl. Das ist die theoretische Bestätigung des vierten Mess-Datenpunkts
(mdf_guard −3,26 ± 2,19 NEUTRAL bei n=99k): **Frequenz ohne Selektion druckt nicht.**
Bindend für jede Kandidaten-Runde ab jetzt: ein Kandidat, der eine Frequenz anhebt/absenkt,
ohne die SELEKTION (welche Hände/Klassen) zu tragen, wird nicht gebaut (sel_guard = der erste
Kandidat dieser Bauart). Ergänzend (Brown §5): Rollen sind Funktionen der Bet-Größe, nicht der
Hand — statische Hand→Rolle-Tabellen sind per Brown falsch; Mixing-Frequenzen folgen
Räuber-Beute-Margen, nicht der eigenen Handstärke (der formale Grund fürs Seesaw / gegen
Purify-Abflachen).

### 3. SPIRAL-RAE = registriertes Reward-Design für JEDEN künftigen RL-Lauf

Die −90-Liga-Regression ist strukturell SPIRALs Fixed-Opponent-Befund (Mistral-Gegner: Winrate
0→62,5% bei Benchmarks UNTER Basis = Ausbeutung statt Lernen). Registriert (Design in
SPIRAL_NOTES.md §5, NICHT gestartet, braucht User-Go + Mess-Slot): (1) Gegner = Self-Play-Kopien
statt sixmax-Liga (Liga nur noch Eval), (2) RAE statt GRPO-Gruppen-Normalisierung — positions-
und format-konditionierte EMA-Baselines `b ← 0,95·b + 0,05·R`, `A = R − b` (BB/BTN haben
inhärent verschiedene EVs = konfundiert), (3) Reward = reiner Chip-Ausgang terminal, ohne
Shaping, (4) voll online, (5) Thinking-Collapse-Wächter (Trace-Länge + Grad-Norm).
Gate: gepaarte Analyzer-Exports ($0) → AIVAT; Winrate-vs-Trainingsgegner als Metrik VERBOTEN.
Ehrlich: HU theoretisch sauber (Zwei-Spieler-Nullsumme), 6-max ohne Konvergenz-Garantie;
Erwartung = Eliminierung der −90-Klasse, kein Versprechen unter −20.

### 4. Diniz (PokerBench-SFT) — kein neuer Hebel, zwei Verwertungen

93,3/91,8% Action-Acc via SFT = reines Label-Agreement, kein EV → bestätigt die
Imitation-Ceiling-Doktrin. Verwertbar: (a) Logprob-Scoring über LEGALE Aktionen statt
String-Matching für jede künftige LLM-Eval, (b) SCORE-Formel (outs × Pot/Call, algebraisch =
Pot-Odds; Bias +≈1pp, 97% Konkordanz, NULL falsche Calls) als eng begrenzter einseitiger
Orakel-KNOB auf Stufe L/F: "SCORE-Fold ⟹ exakter Fold oder marginaler Call im Δ-Band".
