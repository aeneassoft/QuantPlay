# CONDITIONAL POKER LEMMAS — effektive Mathematik mit expliziten Bedingungs-Knöpfen (2026-07-06)

> User-Direktive: "Axiome als Knöpfe, effektive statt dogmatischer Mathematik, bedingte Beweise für Profit."
> Die Übersetzung, die funktioniert: **Die Rechen-Axiome (Wahrscheinlichkeit, Chip-Erhaltung, EV-Linearität)
> bleiben heilig — sie SIND das Profit-Messgerät (AIVAT/Analyzer rechnen durch sie).** Die legitimen Knöpfe
> sitzen eine Ebene höher: MODELL-Annahmen, Gleichgewichts-Begriffe, Präzisions-Budgets, Spiel-Perturbationen.
> Jedes Lemma hier ist ein bedingter Satz: Bedingung (der Knopf) → Aussage → Bedingungs-TEST → Profit-Link.
> Das Goldbach-Muster (`assume_yes.py` / CONDITIONAL_GOLDBACH_THEOREM): Annahme erzwingen, Konsequenz ernten,
> Bedingung messen — nie die Arithmetik lockern.

## L1 — Purifikations-Lemma (Gleichgewichts-Axiom als Knopf) [= Q4, lizensiert]
**Bedingung:** Der Gegner ist STATISCH (adaptiert nie an unsere Frequenzen).
**Aussage:** Dann kostet das Runden unserer Mixed-Strategie auf die modale Aktion (mix ≥ 0.5 → 1.0) keinen
ausbeutbaren EV — Mixing schützt nur gegen Adaption; gegen einen statischen Gegner ist es reine Varianz.
**Bedingungs-Test:** GTOW-Dossier ($0, 13.5k Hände): GTOW ist der Ruse-Re-Solver, adaptiert NICHT an uns
(Translation-Attacke refuted, Harvest ~0). GTOWs eigenes Benchmark-Paper §4.3.1 lizensiert es explizit.
**Profit-Link:** die ~10.7 bb/100 Spread-Scheibe der Fehlerbilanz; zusätzlich Varianzreduktion in jedem Arm.
**Status:** gebaut-fähig in Stunden (`POKERB_PURIFY`), GTOW-Ladder ONLY (vs Menschen bleibt Mixing!), Q2-gegated.

## L2 — Perturbierte-Gleichgewichts-Lemma ("Mr. Orange", Johanson 2007 Kap. 7) [Spiel-Axiom als Knopf]
**Bedingung:** Wir lösen das FALSCHE Spiel absichtlich: Villains Utility um +δ skaliert (Sieger-Bonus).
**Aussage:** Das Gleichgewicht des perturbierten Spiels ist im ECHTEN Spiel eine aggressive Strategie mit
BESCHRÄNKTER Exploitability (Johanson gemessen: +7% Bonus → nur 35 mbb/g exploitierbar) — Aggression mit
bewiesener Leine statt gefühlter.
**Bedingungs-Test:** exakte Best-Response auf River-Subgames ist lokal berechenbar → δ-Sweep: Exploitability(δ)
+ Analyzer-EV(δ) Kurven; der Knopf δ wird empirisch auf den Profit-Sweet-Spot gestellt.
**Profit-Link:** der River-Aggressions-Leak (−1.6 benannt, River gesamt −8.5 = größter Bleed) — genau die
Klasse, wo "GTO-treu" zu passiv gegen GTOWs reale Calling-Mixe ist.
**Status:** braucht den Mini-CFR (numpy, Hebel E aus NOTES) — POST-Ladder-Kandidat; der einzige echte
"Axiom-Tweak für Profit" mit Beweis-Anker. DAS ist die beste Verkörperung der User-Direktive.

## L3 — Thin-Value-Schwellen-Lemma (v3.2b, OpenAI-verifiziert) [Modell-Annahme als Knopf — MESSBAR GESCHEITERT]
**Bedingung:** Die getrackte Calling-Range == Villains wahre Calling-Range an diesem Knoten.
**Aussage:** Dann ist Bet s dünn-profitabel gdw. e_call ≥ exakte Schwelle(s, Line) (geschlossene Form im
Sweep-Doc §1.1; die 0.5-Approximation war der Spezialfall).
**Bedingungs-Test:** v3.2-Refutation (26.14 vs 17.93!) = die BEDINGUNG ist falsch (Tracker-Check-Lines zu
breit → e_call systematisch überschätzt), nicht der Satz. Das Lemma LOKALISIERT damit die Arbeit: Range-
Qualität (v3.3-Familie) ist der Blocker, nicht die Schwellen-Mathematik.
**Profit-Link:** river-thin bleibt geparkt BIS der Bedingungs-Test grün wird — dann ist die Ernte schon
fertig abgeleitet. Bedingte Beweise konservieren Arbeit über Refutationen hinweg.

## L4 — Suit-Isomorphie-Lemma (Johanson §2.5.1) [Exaktheit GRATIS aus Symmetrie]
**Bedingung:** Ranges sind KLASSEN-level (169er, suit-invariant) — was unser emit() konstruktiv garantiert.
**Aussage:** Dann ist der kanonische Solve unter Suit-Permutation EXAKT (kein Approximationsfehler) → 24×
Cache-Kollaps ohne EV-Kosten.
**Bedingungs-Test:** end-to-end bewiesen (permutiertes Board → 5.0s→0.0s, identische Strategie).
**Profit-Link:** die Flop-Bibliothek + jeder Warm-Cache-Hit = weniger Timeout→Floor-Fallbacks.
**Status:** GEBAUT (POKERB_ISO_CACHE); die Bibliothek erzwingt kanonisches Keying (FLOP_LIBRARY.md §4).

## Präzisions-Knöpfe (kein Lemma, aber dieselbe Philosophie: Exaktheit ist ein BUDGET)
MC-EQUITY_ITERS / k_rivers / uint8-Quantisierung (256 Stufen << Solver-Rauschen) / RAM-Dial float32→uint8→1bit
(Johanson hoch, Jackson runter). Regel: jeder Knopf trägt sein Fehlerbudget EXPLIZIT; die Mathe-Suite
(tests/test_math_suite.py) pinnt, WO Exaktheit Pflicht ist (Kern-Identitäten) vs. wo Toleranz legitim ist
(dokumentierte Konditionierung, MC-SE). "Loosen" ohne Budget = Messgerät zerstören; "loosen" mit Budget =
Engineering.

## Anti-Lemma (die rote Linie, einmal aufgeschrieben)
Chip-Erhaltung, Wahrscheinlichkeits-Koheränz (Σp=1, p∈[0,1]), EV-Linearität und Zero-Sum sind NICHT
verhandelbar — nicht aus Dogma, sondern weil AIVAT/Analyzer/Leaderboard Profit DURCH sie definieren. Ein
"Breakthrough", der sie verletzt, ist per Konstruktion ein Artefakt (CLAUDE.md-Honesty-Gate: eine zu gute
Zahl ist ein Bug, nie ein Sieg).
