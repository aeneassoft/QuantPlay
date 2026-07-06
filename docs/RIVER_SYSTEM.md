# DAS RIVER-SYSTEM — der Fokus-Punkt der finalen Architektur (2026-07-06)

> User-These (bestätigt + präzisiert): der River ist die entscheidende Straße. OpenAI-Konsult
> (`data/research_sweep/openai_river_consult.json`) + Websuche + eigene Empirie. Compact CFR (Jackson 2016)
> ist die RAM-Achse dieses Systems.

## Die These, ehrlich präzisiert
Der River ist **terminal** (keine Karten mehr → EV rein durch Showdown/Fold) → Fehler unwiederbringlich,
Korrektheit maximal gehebelt, und es ist die Straße, wo ein ressourcen-begrenzter Bauer am BILLIGSTEN nahe
an GTO kommt (kleinster State-Space, exakte Enumeration, Solver in Sekunden). ABER **kein Zauber-Radierer:**
NICHT durch River-Spiel reparierbar sind (1) Über-Fold/Über-Call/Stack-off VOR dem River (Hände, die den
River nie sehen), (2) Pot-Größe (man kann den Pot nicht rückwirkend wachsen lassen — SPR-Missmanagement),
(3) strukturelle Range-Schäden (fehlende Combos), (4) Linien-Inkohärenz, die der Gegner VOR dem River
ausbeutet. → River = bester ROI pro Engineering-Stunde, nicht Absolution.

## Der ENGPASS (OpenAI, gerankt — dritte unabhängige Bestätigung)
1. **Range/Belief-Qualität, die den Solve füttert** — DER Engpass (wie in beiden Vor-Konsulten).
2. **Coverage** (River-Boards × Ankunfts-Linien × Ranges — immens).
3. Exakt-Solve vs Value-Netz Tradeoff.
4. Per-Solve-Latenz — am WENIGSTEN wichtig (River-Solves sind schnell). → NICHT Geschwindigkeit ist das
   Problem, sondern WAS wir dem schnellen Solver an Ranges geben.

## Die Architektur (OpenAI-Empfehlung = deckt sich mit unserer Roadmap)
**Kurzfristig (bester EV/Woche): TexasSolver als River-Engine BEHALTEN + Ranges härten + uint8-Cache.**
KEIN Pivot zu exakter LP oder reiner River-Library jetzt.
- **Range-Härtung** (Phase 1, höchster Hebel): Tracker gegen GTOW-River-Reveals kalibrieren (KL/Cosine-
  Distanz eng), beide Ranges linien-konditioniert.
- **River-State-Cache**: Key = (kanonisches Board, Linien-Summary, grober Range-Hash), Strategien **uint8-
  quantisiert** gespeichert (Compact CFR: 16 Bytes→1 Byte; 256 Stufen ≪ Solver-Rauschen). Wiederverwenden
  bei Wiederholung/Ähnlichkeit → Latenz auf seltene frische Knoten begrenzt.
- **Mittelfristig**: kleines River-CFV-Netz NUR als Fallback für niedrig-Importance/zeitkritische Knoten —
  NIE die primäre Engine (Gate-0-Beweis + Konsult).

## DER POLARISIERUNGS-FIX (konkreter Präzisions-Hebel, ~wenige bb/100)
BEFUND: unser Heuristik-River blufft exploit-getrieben (`bluff_p = 0.30 + conf·(fold_to_bet−0.5)` = Gegner-
Fold-Rate), NICHT polarisiert (Bluff-Menge an Value-Menge via B/(P+B) gekoppelt). Vs den STATISCHEN GTOW ist
das ein STRUKTURELLES LECK: wir über-bluffen wo GTOW weniger foldet, unter-bluffen wo mehr. OpenAI-Magnitude:
30-50% falsche Bluff-Zahl ≈ 0.1-0.3 bb/Hand pro Linien-Cluster → aggregiert ein paar bb/100 unserer −20.
**FIX (reine Präzision, kein Verhaltens-Hebel):** in GTO-Mode die Resolver-Ausgabe NICHT mit der Fold-Rate-
Heuristik überschreiben — die polarisierte Frequenz emergiert korrekt aus CFR, WENN Ranges+Utility stimmen.
Wo wir approximieren (Floor): Bluff-Zahl explizit an B/(P+B)·Value-Menge ankern, dann nur ±20% Exploit-Tweak.
Die `bluff_to_value_and_frequencies`-Formel (Nacht-Fix B/(P+B)) ist die Brücke — sie ist DORMANT, verdrahten.

## DER RIVER-DIAGNOSE-SCORE (dein Rückblick-Score, jetzt spezifiziert)
Pro River-Aggressor-Knoten: aus dem Solve σ* die Value-Menge (EV_bet≥EV_check) und Bluff-Menge markieren →
Ziel-Frequenzen V*_s, B*_s. Unsere Policy π → beobachtete V_s, B_s. Metriken je Size: **miss_value**
(verpasster Thin-Value), **over_value**, **ratio_error** (|B_s/V_s − B*_s/V*_s| = Polarisierungs-Abweichung).
Defender-Seite: overfold_rate / overcall_rate vs die Indifferenz-Schwelle h*. Aggregiert nach Board-Klasse ×
Linie × Position × Size, gewichtet mit Pot/Initial-Pot (EV-Impact). → Heatmap: WO wir bluten (verpasstes
Value / Fehl-Polarisierung / Fehl-Bluffcatch). $0, deterministisch, speist Korpus B.

## Verifizierte Techniken (Zitate geprüft; unsichere markiert)
- **Sequence-Form LP** — Koller/Megiddo/von Stengel, GEB 1996 (VERIFIZIERT). Exakter River-Solve + exaktes
  Best-Response-Gate (River klein genug für exakte LP → das exakte Exploitability-Gate, das CLAUDE.md fordert).
- **HULHE is Solved** — Bowling/Burch/Johanson/Tammelin, Science 2015 (VERIFIZIERT). Endgame-Resolving.
- **Compact CFR** — Jackson 2016 AAAI-Workshop (WIR BESITZEN es; OpenAI riet fälschlich "2021"). uint8 = die
  RAM-Achse des River-Caches/Library.
- Blocker/Card-Removal exakt — Johanson-Thesis 2013 (VERIFY-Abschnitte; wir enumerieren River bereits exakt).
- Accelerating Best-Response — Johanson/Waugh/Bowling/Zinkevich, IJCAI 2011 (VERIFY).

## In den Plan (Roadmap-Einordnung)
Phase 1 (Range-Wahrheit) IST der River-Engpass-Fix. NEU eingereiht: Polarisierungs-Fix (Präzision, GTO-Mode,
sofort baubar) + River-Diagnose-Score (Messung vor jedem River-Hebel) + uint8-River-Cache (Compact CFR).
Das River-CFV-Netz ist der ERSTE Pflaster-Netz-Kandidat (Supremus river-first), aber nachrangig — nach
Range-Wahrheit, als schmaler Fallback, nicht als Motor.

## PARAMETRISCHE RANGE-WELLE — die konkrete Methode für Range-Kalibrierung (User + Brokos, 2026-07-06)
Quelle: Brokos "Play Optimal Poker 2: Range Construction" (S.4): River-Ranges sind polarized/condensed
(saubere 1D-Wellen über Stärke); VOR dem River evolvieren Ranges mit der Zukunftskarte ("hands change
value") = KEINE statische Welle → der mathematische Grund für die Straßen-Doktrin.
**METHODE (Phase 1, River zuerst):** Repräsentiere die River-Range als GLATTE POLARISIERTE FUNKTION
(Achsen: Stärke × Blocker-Dimension, Polarisierungs-Grad, Value/Bluff/Medium-Massen) statt als 1326 freie
Gewichte → GLATTHEITS-PRIOR regularisiert die Rekonstruktion (kann nicht mehr überkonfident-zackig werden
= greift die "confident-wrong"-Quelle an) → kalibriere gegen GTOW-Reveals → optimiere GEMEINSAM mit der
Bet-Frequenz-Welle ("Harmonie" = Polarisierungs-Konsistenz = der B/(P+B)-Fix als Wellen-Ko-Optimierung).
**GRENZEN (ehrlich):** (a) 1D-Stärke verliert Blocker-Info → mind. 2 Achsen (Stärke+Blocker), sonst
Suit-Aliasing; (b) TURN/FLOP: Range evolviert mit der Karte → statische Welle unvollständig, bräuchte die
Range-Welle als Funktion der Zukunftskarte (schwerer). (c) Glattheits-Gewinn vs Blocker-Verlust = EMPIRISCH,
via Reveal-Daten messbar. Strongest auf dem River (Brokos: dort saubere Wellen) = genau der Fokus.
