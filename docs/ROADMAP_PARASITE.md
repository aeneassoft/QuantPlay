# QUANTPLAY — PARASITÄRE ARCHITEKTUR + ROADMAP DER NÄCHSTEN GRUNDVERSION (2026-07-06)

## Das Leitprinzip: der reduzierte-Genom-Parasit
Wir bauen keinen Solver — wir bauen den ORGANISMUS, der Solver, Gleichgewichts-Engines und Papers als
WIRTE benutzt. Auswahlregel für JEDEN Baustein:
1. **Auslagern (reduziertes Genom):** kann ein Wirt es billiger tun? Solve→TexasSolver,
   Gleichgewicht→GTOW, Architektur→Papers. Unser Genom bleibt winzig (125KB, Consumer-PC, ~$50).
2. **Transferieren (horizontaler Gentransfer):** ist es best-in-domain woanders? Einbauen — DeepStack-
   Gadget, Johanson-Iso, Jackson-uint8, GTOW-Frequenzen. Mosaik-Genom aus lauter Spitzen.
3. **Ernten (Klepto-/Brutparasitismus):** die teure Aufzucht (Solves, aufgedeckte Karten) appropriieren.
4. **Distanz halten (Anti-Mimikry):** zu perfekte Nachahmung tötet den eigenen Edge (v8-PURIFY-Bruch).
5. **Red Queen:** statische Wirte (GTOW) sind sichere Beute; adaptive Gegner brauchen regime-aware Exploit.

## Was wir sind (ehrlich): ein TexasSolver mit Wahrnehmung, Körper, Reflexen, Gedächtnis
Geliehen: Resolver=TexasSolver, Advisors=destilliert, Gold=Solver-Output. UNSER (nicht-Solver):
Range-Rekonstruktion aus der Line · Ganzhand-Orchestrierung · Echtzeit-Routing · Messschleife.
DECKE (ehrlich): wir unterbieten TexasSolvers eigene Exploitability nie → seine Abstraktions-Leaks erben
wir. Deshalb werden bessere Leaf-Werte (Pflaster-Netze) irgendwann relevant — aber SPÄT.
EDGE-ZERLEGUNG (Diagnose, baubar): vs "Solver+WAHRE Ranges" = Range-Fehler; vs "Solver+getrackte Ranges"
= Orchestrierungs-Fehler. Diese zwei Zahlen sagen, wo die −20 wirklich sitzt.

## DIE ZWEI KORPORA (Nervensystem der Iteration; unter dataset/registry.py vereinigen)
- **Korpus A — GOLD:** jeder GTO-validierte (Spot→Aktion/Frequenz). Aus Solve-Cache + GTOW-Reveals +
  Census. Positiver Lehrer: Advisor-Training, Range-Kalibrierung, Flop-Library.
- **Korpus B — SÜNDENREGISTER:** jeder gemessene Fehler (Spot + Abweichung + EV-Kosten). Aus money_mine +
  GTOW-Grades + Danger-Sets. Negativer Lehrer: Scheduler-Prioritäten, Patch-Queue.

## ROADMAP — die nächste Grundversion (jede Phase gegen Anker Tag v2 = −19.70, Präzisions-Doktrin)
**Phase 0 — Korpora vereinigen ($0, Tage).** registry.py um A/B erweitern; money_mine + Grades + Solve-Cache
+ Reveals in eine indizierte Struktur (State-Key: Position/Stack/Pot/Line/Textur). Deliverable: abfragbares
A (Gold) + B (Fehler) mit Coverage-Statistik. IST-Baustein von allem danach.

**Phase 1 — RANGE-WAHRHEIT (höchster Hebel, $0, deterministisch).** GTOW-Reveals als Ground Truth:
State-Key → empirische f_K vs Tracker R̂ → Logit-Korrektur δ_K, geglättet, n<30 zurückfallen. Zwei-Stufen-
Tracker (Bayes → δ_K → renormieren). Gate: Cross-Entropy/Kalibrierung auf Held-out-Keys BESSER; dann
gepaarter Analyzer-Arm vs v2-Flags. Multipliziert JEDES Organ.

**Phase 2 — FLOP-LIBRARY (der Flop-Bleed-Fix, offline, Pod-Skala).** Board-Cluster (paired/mono/twotone/
rainbow × high/mid/low × connect) × Pot/SPR × Bet-Menü; repräsentative Flops offline lösen (Stunden okay),
Online = Lookup + Interpolation. Fällt bei Miss auf Advisors zurück (Graceful Degradation). Gate: vs
TexasSolver auf Held-out-Flops nahe; eigener Analyzer-Arm. Docs/FLOP_LIBRARY.md-Auflagen gelten.

**Phase 3 — SCHEDULER + OFF-TREE-TRANSLATOR (Coordination-Logik, kein Netz).** Importance-Scheduler:
je (Pot, SPR, Textur, Line) → welches Organ + welches Bet-Menü + wieviel Solve-Budget (kein Iter-Budget
auf $1-Pots). Off-Tree-Translator: reale Villain-Aktionen EV-impact-aware auf On-Tree-Proxies + Range-
Anpassung. Beide adressieren gemessene −20→−10-Lecks. Gate: Danger-paired + Live-Smoke.

**Phase 4 — RESOLVER-PRÄZISION (reiner Compute).** Erst die Matrix-Lücke schließen (Resolver GRADEN, bounded
solves) → dort wo er den Advisor schlägt, Iters/exakte-Enumeration hoch. Ändert kein Verhalten.

**Phase 5 — PFLASTER-NETZE (zuletzt, schmal, NUR falls Gate 0 PASS-fähig).** Turn-Boundary-Leaf (Flop-Resolve
ermöglichen) / River-Cut / Range-Residual-Denoiser. Nie zentraler Motor (Gate-0-Beweis + Konsult).

## Definition der finalen Grundversion
Nicht "perfekt", sondern das SKELETT verdrahtet: Blueprint + kalibrierter Tracker + Scheduler + Off-Tree +
Flop-Library + Live-Resolver + Advisors + regime-aware Exploit, mit A/B-Korpora als Nervensystem und den
Pflaster-Netzen als späte, schmale Organe. Jeder spätere Schritt verzinst sich kumulativ auf diesem Skelett.
