# QUANTPLAY — DIE FUNDAMENTALE FINALE ARCHITEKTUR (2026-07-06)

> Nicht "der perfekte Spieler" — das SKELETT, auf dem alles Weitere iteriert. Dreifach fundiert:
> (1) die gemessene KOMPETENZ-MATRIX (`data/research_sweep/component_matrix.json`, jede Komponente vs
> TexasSolver-Orakel), (2) der OpenAI-Architektur-Konsult (`data/research_sweep/openai_architecture_consult.json`),
> (3) die eigene Nacht-Empirie (Präzisions-Doktrin, Gate-0-Leduc, v8-Live-Bruch). Alle drei sagen dasselbe.

## Der Edge (unverändert, jetzt formalisiert)
Kein neuer Algorithmus. Der Edge ist **die Architektur + die billigste ehrliche Messschleife + der
GTOW-Vampirismus** (übermenschlicher Lehrer für Centbeträge: aufgedeckte Karten, Per-Decision-Grades,
Frequenzen). Jedes Organ sitzt dort, wo es MESSBAR das beste ist; Compute sitzt am Entscheidungspunkt,
nicht in einer Allwissenheits-Tabelle.

## Die Organe an ihren gemessenen Plätzen (Kompetenz-Matrix, 36 Regionen)
| Region | Bester (gemessen) | GTO-Gap |
|---|---|---|
| Preflop (alle) | **blueprint** (near-Nash CFR) | führt |
| Flop (8/9 Regionen) | **advisor_mlp** | 0.23–0.34 |
| Turn (10/12) | **advisor_mlp** | ~0.3 |
| River (9 Value / 5 Exploit) | **advisor_mlp** bzw. **exploit_overlay** | ~0.3 |
| ÜBERALL letzter Platz | **formula_floor** | 0.53–0.71 (nur noch Fallback) |
KRITISCHE MATRIX-LÜCKE: der LIVE-RESOLVER wurde mit 0 Solves NIE bewertet → seine Region-Siege sind
unvermessen. Das ist der nächste Mess-Schritt (bounded resolver-solves), NICHT eine Design-Annahme.

## Die 7 Schichten (Reihenfolge = Anrufreihenfolge pro Entscheidung)
1. **Blueprint** — Preflop, near-Nash. Bleibt. (Matrix: gewinnt preflop.)
2. **Range-Tracker** — DER Multiplikator. Speist ALLE nachgelagerten Organe; falsche Ranges = confident
   wrong (v8-Bruch, gemessen). → HÖCHSTER HEBEL, siehe unten.
3. **Importance-aware Scheduler (NEU, Architektur-Lücke #1)** — entscheidet je (Pot, SPR, Textur, Line)
   WELCHES Organ + welches Bet-Menü. Ersetzt den heutigen groben "solve/nicht-solve @300s"-Cap. Kein
   Iterations-Budget mehr auf $1-Pots.
4. **Off-Tree-Translator (NEU, Lücke #2)** — mappt beliebige reale Villain-Aktionen (Überbets, Min-Raises,
   Delay-Lines) EV-impact-aware auf das kleine On-Tree-Aktionsset + passt Ranges an. Ein Stück von −20→−10
   blutet heute durch missbehandelte Freak-Lines.
5. **Flop-Library (NEU, Lücke #3)** — offline vorgelöste Flop-Archetypen (Board-Cluster × Pot/SPR ×
   Bet-Menü), Online = Table-Lookup. DAS ist der Flop-Bleed-Fix — NICHT ein Live-Netz. (OpenAI + unser
   NOTES-Queue #1 stimmen überein; Live-Flop-Solve ist gemessen NO-GO, 49/50 Timeouts.)
6. **Live-Resolver (Turn+River)** — dort wo der Scheduler es lohnend nennt; Präzision hochdrehbar
   (mehr Iters, exakte Enumeration — kostet nur Compute, ändert kein Verhalten).
7. **Advisor-MLPs** — die gemessen stärkste statische Schicht; Fallback wo (5)/(6) nicht greifen.
   **exploit_overlay** regime-aware (Lücke #4), primär River/Turn, glättet zur Baseline zurück.
Darunter: **formula_floor** als reiner Not-Fallback (Matrix: gewinnt nie, aber Graceful Degradation).

## WO das neue NETZ +EV ist (deine Kernfrage — Konsult-Ranking, ehrlich)
- **NICHT der zentrale Motor.** Ein globales All-Street-Netz ist −EV/Sackgasse (Gate-0 bewies: off-
  distribution-Fehler dominiert, 70 vs 31 mbb). Advisor-MLP-Ersatz lohnt nicht (Matrix: die winzigen
  Advisors gewinnen schon).
- **+EV nur an DREI schmalen Stellen, und ALLE nachrangig:** (a) Turn-Boundary-Leaf-Netz um Depth-Limited-
  FLOP-Resolving zu ERMÖGLICHEN — strukturell wichtig, aber erst nach Baum-Abstraktion + Gadget lauffähig
  (Gate-0-Linie); (b) River-Leaf-Netz zum SUCH-CUTTEN in großen Bäumen (Kosten sparen, nicht Qualität);
  (c) Range-Residual-Netz als DENOISER auf dem Tracker — aber erst NACH den strukturellen Range-Fixes.
- **Wo Präzision das Netz schlägt:** überall wo der Subgame klein genug zum Lösen ist UND die Inputs
  stimmen → mehr Solver-Iters / exakte Enumeration schlagen jedes 125KB-Netz. Netze reserviert für
  NEUE Such-Regimes (Flop) oder Kosten-Cutting — nie wo 2–5× mehr Iters denselben Gewinn holen.

## Der höchste Einzelhebel: RANGE-WAHRHEIT (nicht ein Netz)
Beide Quellen: Range-Qualität multipliziert JEDES Organ; ein 10–20%-KL-Fehler kostet mehr als jede
0.5%-Solve-Verschärfung. Der saubere Fix nutzt unsere 13.5k GTOW-AUFGEDECKTEN Hände als Ground Truth —
statistische KALIBRIERUNG, kein Netz:
1. Jeden Decision-Node nach abstraktem State keyen (Position, Stack/Pot-Bucket, Line-Abstraktion, Textur-Cluster).
2. Tracker-Output R̂ vs empirische Reveal-Frequenz f_K je Key vergleichen (Cross-Entropy, Kalibrierung).
3. Logit-Korrektur δ_K = logit(f_K) − logit(R̂) lernen, über ähnliche Keys glätten, Keys mit n<30 zurückfallen.
4. Zwei-Stufen-Tracker online: Bayes → δ_K-Korrektur → renormieren. Auf Held-out-Keys evaluieren.
5. Optionales Residual-Netz erst DANACH (der einzige gerechtfertigte Netz-Einsatz nahe am Kern).

## Die Baureihenfolge (Präzisions-Doktrin, jeder Schritt gegen Anker Tag v2 = −19.70)
1. **Range-Kalibrierung** (Reveal-Daten → δ_K) — höchster Hebel, $0, deterministisch.
2. **Flop-Library** (offline Solves, Board-Cluster) — der Flop-Bleed-Fix.
3. **Importance-Scheduler + Off-Tree-Translator** — Coordination-Logik, kein Netz.
4. **Resolver-Präzision hoch** (Iters/Enumeration) wo die Matrix (nach Resolver-Grading) es zeigt.
5. **Pflaster-Netze** zuletzt, schmal: Turn-Boundary (Flop-Resolve ermöglichen) / River-Cut / Range-Residual.
Nichts davon ÄNDERT eine Entscheidung; alles berechnet sie GENAUER. Die finale Version ist dieses Skelett
verdrahtet — sie muss nicht perfekt spielen, sie muss die richtige Architektur SEIN.
