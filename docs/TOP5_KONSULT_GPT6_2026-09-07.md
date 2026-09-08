# TOP-5-KONSULT — gpt-6-astra (2026-09-07) + Bewertung durch Fable

**Anlass (User):** „Wie muss das Projekt weitergehen, damit der Bot unter die Top 5 kommt?" Das
neueste OpenAI-Modell (`gpt-6-astra`, Responses-API, reasoning=high, 5.178 Reasoning-Tokens,
469 s) bekam das vollständige, belegte Briefing (Teil A) und lieferte die Ausarbeitung (Teil B).
Teil C ist meine Bewertung: was ich übernehme, was ich ablehne, was ich gegen den Code geprüft habe.

---

## TEIL A — Das Briefing (wörtlich gesendet)

# BRIEFING: Pokerbot "PokerB" — Weg in die Top 5 des GTO-Wizard-AI-Leaderboards

Du wirst als externer Chef-Architekt konsultiert. Wir wollen eine ehrliche, tiefe, umsetzbare
Strategie-Ausarbeitung, keine Ermutigung. Alles Folgende ist gemessen und belegt (Quellen im Repo).

## 1. Das Ziel und der Maßstab

- Ziel: Heads-Up No-Limit Hold'em Bot, der auf dem öffentlichen GTO-Wizard-AI-Leaderboard
  in die TOP 5 kommt. Der Maßstab ist AIVAT bb/100 gegen den GTO-Wizard-AI-Bot (ein
  Echtzeit-Re-Solver der Ruse-Familie, praktisch Nash). Alle Teilnehmer verlieren gegen ihn.
- Leaderboard-Lage: bester Eintrag −3,14 bb/100; Frontier-LLMs mit hohem Reasoning −8 bis −9.
  Top 5 heißt realistisch: besser als etwa −8.
- Unser letzter Live-Anker: v4-Bot auf PRINCE-Fundament −21,12 (n=979); Kontrollarm ohne
  Guards −31,34 (n=488), gleiche Nacht. Ältere Messung PRINCE v2.2 −19,70 ± 4,37 (n=2393),
  aber durch einen Blinds-Reihenfolge-Bug in der Live-Schnittstelle inflationiert; ehrlicher
  Bereich −25 bis −30 für die alte Version.
- Der aktuelle Stand v5 hat NOCH KEINEN GTOW-Anker. Im Self-Play-Spiegel liegt v5 +27,6 ± 1,8
  bb/100 über v4 und +30,6 ± 5,0 über der eingefrorenen Basis (30k gepaarte Decks, dreifach
  repliziert, A/A-Nulltest exakt 0). Self-Play ist aber nicht transitiv zu GTOW; wir wissen
  nicht, wie viel davon gegen GTOW ankommt.

## 2. Architektur (was existiert)

Python 3.12, Windows, eine RTX 3080 Ti (12 GB), 12 CPU-Worker. Kein Cloud-Budget außer
gelegentlichen RunPod-Pods (H100, ca. 30 $ Reserve).

- Preflop: nahe-Nash-Blueprint (Solver-gegrafteter Chart, gemessen ≈ −1,6 bb/100 Verlust).
- Range-Tracker: Bayes-Rekonstruktion der Gegner-Range über Aktionen (Trennschärfe am River
  schwach: eq 0,65 vs 0,53 zwischen Gewinnern und Verlierern; nach 3 Barrels 700–900 Combos).
- Flop/Turn: MLP-Advisors (auf Solver-Frequenzen trainiert) + Heuristiken (Textur, SPR, MDF).
  KEIN Echtzeit-Solving auf Flop; TurnCFR auf GPU gebaut und gegen TexasSolver kreuzvalidiert
  (OOP r=0,944), aber im Einsatz zu teuer/zu leise (3 Eingriffe in 3904 Entscheidungen).
- River: GPU-Tensor-CFR+ über 1326×1326-Combo-Matrizen, Batch B=256 = 100 % GPU-Auslastung,
  0,30 s pro Spot, Kreuzvalidierung gegen TexasSolver r=0,999. Daraus Guards:
  river_wert_bremse (keine Value-Bet mit eq<0,5 vs Range; 3× repliziert +8 bb/100 im Spiegel)
  und river_gpu_guard (Solver-Chirurgie nur wenn p_basis<0,10 und p_alt>0,70, Pot ≥ 30 bb).
- Guard-Wrapper-Architektur: Strategie-Änderungen NUR als Wrapper um die eingefrorene
  Basis-Politik (v5 = river_gpu_guard(river_wert_bremse(button_disziplin(turn_wert(sel_guard))))).
- Deception-Schicht (Turn-Defense, Slowplay, Seesaw-Doktrin: Mixing nie abflachen; eine
  Purify-Variante brach live von −20 auf −58 ein).
- Exploit-Overlay (Dirichlet-Gegnermodell) existiert, ist gegen GTOW aber −EV (deviation cost).
- Messinfrastruktur: pargate (gepaarte Decks, Button-Tausch, Bootstrap-Verdikte, fortsetzbare
  Blöcke), GTOW-Harness (in-process, HH-Logging, AIVAT je Hand), GTOW-Analyzer-Export
  (PokerStars-HH → per-Entscheidung EV-Verlust), Tiefen-Replay (Aktions-EVs je Combo für
  reale GTOW-Hände über den GPU-Solver), LLM-Adversar (Fable-Duell) und 20 persistente
  Exploit-Jäger.

## 3. Was wir über die verbleibende Lücke wissen (Tiefen-Replay auf 571 realen River-Spots vs GTOW)

- 81 % des v4-Verlusts lag am River (Nacht 1), davon 59 % in 9 Big-Pot-Calls. Die Chirurgie
  (v5) hat genau diese Klasse entfernt.
- Liegengelassener EV : Fehler-EV = 1,6 : 1. Die größte Restkategorie ist OVERFOLD (31 bb in
  970 Händen): der Bot foldet am River, wo der Solver einen Bluff-RAISE will. Danach SIZE
  (9 bb), Fehl-Value-Bets (11,5 bb), verpasste Bluffs (5,5 bb). Verlust-Calls sind im EV-Maß
  die kleinste Kategorie (4,1 bb) — AIVAT-Zellen sind Realisierungs-, nicht Entscheidungs-Attribution.
- Solver-Konformität am River: check 0,86, fold 0,83, bet nur 0,45 (15 % klare Widersprüche).
- Flop/Turn-EV-Fehler gegen einen Solver sind UNVERMESSEN (kein Flop-Solver, TurnCFR nicht
  im Einsatz). Aus dem alten Analyzer-Grade: Verlust River −8,6 + Flop −8,3 + Preflop −1,6
  (Stand Juli, vor allen Guards).
- Range-Sensitivität: Range-Tausch (Tracker vs Preflop-Nullhypothese) kippt 34 % der
  Best-Arme roh, aber nur 5 % der EV-relevanten Urteile (>0,25 bb).
- Konvergenz: 150 vs 600 CFR-Iterationen kippen 25 % der Best-Arme roh, 4 % EV-relevant.

## 4. Was wir versucht haben und was scheiterte (bindende Lehren)

- Frequenz-Matching auf GTOW-Frequenzen: 3× refutiert (Score steigt, EV fällt). Selektion
  (welche Hände) schlägt Frequenz (wie oft).
- Imitationslernen: HU-Policy-Net −212; Solver-Imitations-Floor Plateau −72; SFT eines 9B-LLM
  + GRPO regressierte (−90). Lehre: Imitation ≤ Lehrer, RL brauchte besseren Reward als
  Self-Play-Liga.
- Frontier-LLM als "Brain" (Program-of-Thought über unsere Engine-API): −28,55 AIVAT, langsam,
  teuer, nicht unseres. Sekundär.
- Bet-Size/Translation-Attacken gegen GTOW: refutiert (13,5k Hände; GTOW re-solvt ohne Baum-Grenze).
- v8 = Solver-PLAY am River (statt nur Chirurgie) + Stack-off-Bremse: im Spiegel NEUTRAL
  (+2,3 ± 2,4 gepoolt über 45k Decks), obwohl das Replay auf realen GTOW-Händen +278,6 bb
  Kontrafaktik zeigte. Ursache: der Self-Play-Spiegel bepreist Feinpräzision nicht (der
  Spiegel-Gegner ist kein Re-Solver, exploitiert weder Size-Muster noch Mix-Fehler; die
  Klarfälle waren schon geerntet; Korrekturen nz_median 1,9 bb vs 11,6 bb bei der Chirurgie).
  KERNPROBLEM: unser einziger billiger Messkanal (Self-Play) ist für die verbleibenden Gewinne blind.
- Leal (arXiv 2606.28308): CFR+ wählt niedrig-Entropie-Mitglied des Nash-Polytops;
  Max-Entropie-Mitglied ist besserer Hedge. Kandidat: Entropie-Anker im GPU-CFR (ungebaut).

## 5. Die Messkosten (DAS Engpass-Problem — bitte ernst nehmen)

- Self-Play-Spiegel: 30k gepaarte Decks mit GPU-Arm dauern ca. 8 Stunden (12 Worker; die GPU
  ist geteilt zwischen Workern). Ergibt SE ≈ 3 bb/100. Für Effekte < 5 bb/100 brauchen wir
  mehrere solche Läufe (3-Läufe-Regel vor jeder Taufe).
- GTOW-Live-Anker: ca. 8–9 Stunden für 2500 Hände über die API; nachts gefahren; dazu ein
  begrenztes Hand-Budget und Server-Instabilität (503-Stürme, Deadlocks). SE bei n≈1000
  liegt bei ± 7 bis ± 14 bb/100. Eine Messung, die −8 von −12 unterscheidet, braucht
  n ≈ 5000+ pro Arm, also Wochen.
- GTOW-Analyzer (Chrome-Upload gegradeter Hand-Histories, per-Entscheidung EV-Verlust):
  Minuten pro 1500 Hände, aber manuell (User-Upload), und misst EV-Verlust gegen die
  Analyzer-Lösung, nicht AIVAT.
- Tiefen-Replay (unser GPU-Solver auf realen GTOW-Händen, 0 $): Minuten. Misst aber nur den
  River, nur gegen unseren eigenen Solver, in-sample auf gespielten Händen.
- Ein Entwicklungs-Zyklus "bauen → Spiegel-Gate → GTOW-Anker" kostet damit 1–2 Wochen
  Wandzeit; wir haben in vier Wochen zwei Bot-Versionen sauber getauft (v4, v5).

## 6. Bindende Randbedingungen

- Chip-Erhaltung, Σp=1, EV-Linearität sind unverhandelbar; alles andere ist drehbar.
- Verdikte nur über gepaarte Messungen mit A/A-Nulltest; Zahlen nur mit Quelle.
- Ein Entwickler (Claude-Agent) + ein Product-Owner; kein Team, kein Rechenzentrum.
- Hardware fest: 3080 Ti + 12 Kerne lokal; Pods nur punktuell.
- Der Bot muss live in unter ~10 s pro Entscheidung antworten (GTOW-Harness-Timeout).

## 7. Offene, registrierte Kandidaten (ungebaut oder ungemessen)

A1 River-Raise-Spiel (Play-Guard mit tiefem Trigger 15 bb, fp16; vorregistrierte Erwartung nur
+3,6 bis +5,4 bb/100 auf der GTOW-Achse) · A5/A6 Flop/Turn: kanonische Solve-Bibliothek
(1755 Suit-ISO-Flops, mit unserer Batch-Maschine enumerierbar) statt Live-Solves · C3
Entropie-Anker · E1 Re-Solver-Proxy-Gegner im Gym (unser GPU-Solver als Gegner-Politik = der
einzige 0-$-Kanal, der Feinpräzision bepreisen könnte) · Value-of-Computation-Arbiter
(Resolver nur wo ΔEV erwartet) · Depth-limited CFR + neuronale Blätter (Li & Huang 2026,
ReBeL-Familie) als "v4-Pfad" — nie begonnen · D1/D2 Code-Hygiene (HU-App spielt falsche
Konfig; 9 Audit-Fixes und Advisor-Rollen-Fix live aus).

## 8. Die Frage an dich

Erarbeite eine Strategie, wie dieses Software-Engineering-Projekt weitergeführt werden muss,
damit der Bot realistisch unter die Top 5 kommt (besser als ca. −8 bb/100 AIVAT vs GTOW).
Wir erwarten eine Ausarbeitung mit:

1. Eine ehrliche Einschätzung: ist Top 5 mit dieser Hardware, diesem Team und diesen
   Messkosten erreichbar? Mit welcher Wahrscheinlichkeit, in welchem Zeitraum? Wo liegt der
   Boden der aktuellen Guard-Wrapper-Architektur, und warum?
2. Die Ziel-Architektur, die Top 5 tatsächlich erreichen kann (welche Straßen brauchen
   echtes Solving, welche Abstraktion, welcher Algorithmus, welches Blatt-Bewertungsmodell,
   wie das auf einer 3080 Ti in <10 s pro Entscheidung läuft). Bitte mit Rechenbudget-Schätzung.
3. Das Messproblem: wie bauen wir einen billigen, schnellen Messkanal, der Verbesserungen
   gegen einen Re-Solver sichtbar macht, ohne jede Stufe 8 h Spiegel + Nächte GTOW zu kosten?
   Konkrete Vorschläge (Exploitability-Rechnung, Best-Response gegen unsere Politik,
   Proxy-Gegner, Sequenzierung von Messungen, Stichproben-Ökonomie).
4. Eine priorisierte Schritt-Folge (Phasen mit Meilensteinen, je mit Abbruch-Kriterium und
   dem Beweis, der die Phase abschließt). Was zuerst, was nie.
5. Die Risiken und Denkfehler, die du in unserem bisherigen Vorgehen siehst.
6. Was wir sofort STOPPEN sollten, weil es keine Top-5-Wirkung hat.

Antworte auf Deutsch, strukturiert, konkret, ohne Schmeichelei. Wo du spekulierst, sage es.
Wo du Rechenbudgets oder Effekte schätzt, gib die Annahmen an.


---

## TEIL B — Die Antwort von gpt-6-astra (wörtlich, ungekürzt)

# Urteil

**Top 5 ist mit der Hardware nicht ausgeschlossen. Mit dem bisherigen Entwicklungs- und Messverfahren ist es aber kein belastbarer Plan.**

Der entscheidende Engpass ist derzeit nicht die Zahl der CFR-Iterationen und auch nicht das Fehlen eines größeren Netzes. Es sind drei miteinander gekoppelte Probleme:

1. **Ihr kennt den aktuellen Abstand zum Ziel nicht.** v5 hat keinen GTOW-Anker.
2. **Euer Haupt-Gate misst zunehmend die falsche Fähigkeit.** Ein schwacher Spiegelgegner kann Verbesserungen gegen einen Re-Solver nicht zuverlässig bewerten.
3. **Die Strategie wird lokal repariert, ohne dass Aktionswahl, eigene Range und Fortsetzungsstrategie überall zusammenpassen.** Die großen Fehler lassen sich so entfernen; die verbleibende Lücke wird damit erheblich schwieriger.

Meine Empfehlung ist deshalb:

> **Zuerst einen unabhängigen, entscheidungsbasierten Messkanal und einen kleinen Re-Solver-Prüfstand bauen. Parallel v5 live verankern. Danach River als kohärente Strategie integrieren, Turn aktivieren und erst anschließend Flop-Re-Solving mit gelernten Fortsetzungswerten entwickeln.**

Nicht zuerst: vollständige Flop-Bibliothek, Entropie-CFR, mehr Self-Play-Replikate oder ein neues großes Policy-Netz.

Alle Ist-Zahlen im Folgenden stammen aus eurem Briefing; ich habe das Repository und die genannten Arbeiten nicht geprüft. Eigene Zahlen kennzeichne ich als **Planungsannahmen**, **Rechnungen** oder **subjektive Einschätzungen**.

---

# 1. Erreichbarkeit, Wahrscheinlichkeit und Architektur-Boden

## 1.1 Was die bisherigen Ergebnisse tatsächlich belegen

| Befund | Zulässige Schlussfolgerung | Nicht zulässige Schlussfolgerung |
|---|---|---|
| v5 schlägt v4 im Spiegel deutlich | Die Änderungen haben gegen diese Gegnerklasse erheblichen Wert | v5 ist gegen GTOW entsprechend viele bb/100 besser |
| River-CFR korreliert mit TexasSolver mit r=0,999 | Wesentliche Implementierungsteile stimmen offenbar gut überein | Die live gewählten Aktionen sind fast optimal |
| v8 im Spiegel neutral, Replay positiv | Der Spiegel ist möglicherweise unempfindlich; Replay zeigt einen Kandidaten | v8 gewinnt live sicher den kontrafaktischen Replay-EV |
| 81 % der alten Attribution am River | River war ein sehr lohnendes Reparaturziel | Flop und Turn kosten nach River-Reparatur wenig |
| Range-Tausch kippt nur 5 % der EV-relevanten Urteile | Viele untersuchte River-Entscheidungen sind gegen diesen konkreten Range-Tausch robust | Der Tracker ist für Raise-Spiel und frühere Straßen ausreichend |

**Die v5-Live-Verankerung hat aktuell mehr Informationswert als die nächste Guard-Idee.** Sie entscheidet, ob ihr ein Restproblem von vielleicht wenigen bb/100 habt oder noch eine grundsätzlich schwache Postflop-Strategie.

Ein kleiner Live-Anker wird diese Frage nicht präzise beantworten. Er kann aber grobe Welten unterscheiden, große Regressionen erkennen und neue Zustände für den Analyzer liefern.

## 1.2 Meine Erfolgseinschätzung

Eine empirisch begründete Erfolgswahrscheinlichkeit ist aus diesen Daten nicht identifizierbar. Als **subjektiven Planungsprior** würde ich für die feste Schwelle **−8 bb/100** ansetzen:

| Horizont | Subjektive Chance, die Schwelle tatsächlich zu überschreiten |
|---|---:|
| Vier Wochen | unter 10 % |
| Drei Monate | etwa 10–25 % |
| Sechs Monate | etwa 20–40 % |

Annahmen:

- Der Entwickler arbeitet überwiegend an diesem Projekt.
- GTOW bleibt ausreichend zugänglich.
- Analyzer-Feedback ist regelmäßig verfügbar.
- Die Architektur wird wie unten beschrieben umgestellt.
- Es gibt keinen weiteren grundlegenden Interface- oder Bewertungsfehler.
- Gemeint ist die feste Schwelle, nicht ein möglicherweise stärker werdendes tatsächliches Top-5-Feld.

Diese Spannen sind keine Messresultate. Der erste saubere v5-Anker kann sie stark verschieben.

**Ein rein statistisch überzeugender Nachweis ist zusätzlich schwieriger als das Erreichen der Spielstärke.** Ein tatsächlich bei −7 liegender Bot lässt sich mit eurem Hand-Budget unter Umständen lange nicht sicher von −9 unterscheiden.

## 1.3 Wo liegt der Boden der Guard-Wrapper?

Es gibt **keinen mathematischen Wrapper-Boden**: Ein Wrapper kann theoretisch die Basis vollständig ersetzen. Praktisch hat eure derzeitige Bauweise aber einen klaren Sättigungspunkt:

- Sie korrigiert überwiegend bereits besuchte Zustände.
- Harte Trigger übergehen kleine, häufige EV-Verluste.
- Änderungen am River verändern vorher notwendige Value-/Bluff-Zusammensetzungen.
- Eine neue Bet- oder Raise-Strategie erzeugt neue Folgezustände, für die alte Guards nicht konstruiert wurden.
- Die eigene Range wird inkonsistent, wenn sie weiterhin aus der Basis statt aus der tatsächlich ausgeführten Wrapper-Politik rekonstruiert wird.
- Lokale „gute Aktionen“ ergeben nicht automatisch eine schwer exploitierbare Gesamtstrategie.

Eine seriöse numerische Untergrenze lässt sich daraus nicht ableiten.

Es gibt allerdings ein Warnsignal: In der alten Analyzer-Messung summieren sich **Flop 8,3 und Preflop 1,6 auf 9,9 bb/100 Entscheidungsverlust**, noch ohne Turn und River. Das ist **keine AIVAT-Untergrenze** und kein aktueller Messstand. Es zeigt aber: Falls die Flop-Schwäche weitgehend fortbesteht, wird perfektes River-Spiel allein das Ziel wahrscheinlich nicht retten.

**Planerische Konsequenz:** Weitere Guards sind ein sinnvoller Brückenpfad, aber keine tragfähige Top-5-Zielarchitektur.

---

# 2. Zuerst die Metriken sauber trennen

Ihr braucht künftig drei getrennte Ergebniszeilen. Kein Gesamtscore, der sie vermischt.

### A. Zielmetrik: AIVAT gegen GTOW

Das ist das eigentliche Produktziel. Es ist eine Gegnerleistungsmetrik, keine direkte Exploitability-Messung.

### B. Referenz-Regret auf festgehaltenen Entscheidungen

Wie viel EV verliert die Kandidatenpolitik gegenüber einer bestimmten Solver-Referenz in denselben Zuständen?

Billig und sensitiv, aber abhängig von:

- Zustandsverteilung;
- Ranges;
- Aktionsbaum;
- Fortsetzungsstrategie;
- Solverqualität.

### C. Robustheit beziehungsweise beschränkte Exploitability

Wie viel gewinnt eine Best Response oder ein stärkerer Proxy gegen die Kandidatenpolitik in einem definierten Testspiel?

Das schützt vor Verbesserungen, die nur gegen eine Referenz gut aussehen.

**Release-Regel:** B und C selektieren Kandidaten. A bestätigt das Produkt. B oder C dürfen niemals als „erwarteter AIVAT-Gewinn“ umetikettiert werden, solange keine belastbare Kalibrierung existiert.

---

# 3. Zielarchitektur

## 3.1 Was tatsächlich gebraucht wird

Nicht „ReBeL komplett nachbauen“. Das wäre für dieses Team ein zu großes Programm.

Die sinnvolle Zielarchitektur ist:

> **Starker Preflop-Blueprint + konsistente öffentliche Beliefs + straßenübergreifendes, beschränktes Re-Solving + range-konditionierte Fortsetzungswerte + harte Laufzeitkontrolle.**

| Teil | Ziel |
|---|---|
| Preflop | Bestehenden Blueprint behalten, Interface und Übergaberanges korrigieren |
| River | Vollständige Solver-Politik im gewählten Aktionsbaum statt nur Chirurgie |
| Turn | Explizites Re-Solving, zunächst selektiv, später für den Großteil relevanter Entscheidungen |
| Flop | Kleiner Online-Baum mit gelernten Turn-Fortsetzungswerten; starke Bibliotheks-/Blueprint-Fallbacks |
| Beliefs | Beide Spielerranges aus der tatsächlich gespielten Politik fortschreiben |
| Sicherheit | Deadline, legaler Fallback, Solverdiagnostik, Unsicherheits- und OOD-Erkennung |
| Exploit-Overlay | Gegen GTOW aus |

**Echtes Online-Solving auf jeder Flop-Entscheidung ist keine notwendige Bedingung für Top 5.** Eine hinreichend gute Flop-Strategiebibliothek könnte reichen. Eure vorhandenen MLP-Advisors sind dafür aber noch nicht nachgewiesen stark genug. Deshalb muss Flop in die Zielarchitektur als messbar optimierbare Komponente hinein.

## 3.2 River: von isolierten Eingriffen zur kohärenten Strategie

Der nächste River-Schritt sollte nicht „noch niedrigere Guard-Schwelle“ heißen, sondern:

1. Solver berechnet eine vollständige Strategie für beide Ranges.
2. Bet-, Raise- und Call-Auswahl stammen aus demselben Spiel.
3. Die ausgegebene Verteilung wird nicht nachträglich durch unmodellierte Heuristiken verzerrt.
4. Folgeentscheidungen verwenden passende Ranges und denselben Fortsetzungsplan.
5. Fallbacks gelten bei fehlender Qualität oder Zeit, nicht aufgrund einer zweiten widersprüchlichen Strategiedoktrin.

**Den erfolgreichen Wert-Guard zunächst als Vergleichsarm behalten**, nicht sofort entfernen. Langfristig gehört er in einen EV-basierten Sicherheitsmechanismus.

Warum? Equity gegen die gesamte gegnerische Range ist weder eine hinreichende noch eine notwendige Bedingung für eine profitable Bet. Entscheidend sind insbesondere:

- Equity gegen die Calling- und Raising-Range;
- Fold-EV;
- Größe;
- Reaktion auf ein Raise;
- EV gegenüber Check.

Eine harte `eq < 0,5`-Regel kann große Fehler verhindern und gleichzeitig dünne Value-Bets oder profitable Bluff-/Raise-Linien blockieren.

### Aktionsabstraktion

- Fold/Check/Call vollständig.
- Wenige, aber sinnvoll gewählte Bet- und Raisegrößen.
- All-in und korrekte Min-Raise-Regeln.
- Tatsächliche gegnerische Größe exakt in den Root übernehmen.
- Offline gegen einen dichteren Größenbaum testen.

Die Größen sollten aus unabhängigen Solver-EVs und euren realen Zuständen kommen, nicht aus Frequenz-Matching.

## 3.3 Turn: erst die vorhandene Maschine nutzbar machen

Ihr habt bereits TurnCFR. **Drei Eingriffe in 3904 Entscheidungen sind zunächst ein Integrationsbefund, kein Beweis geringer Turn-Relevanz.**

Vor einem neuen Algorithmus braucht ihr eine Funnel-Auswertung:

- Wie viele Entscheidungen waren prinzipiell lösbar?
- Wie viele wurden wegen Zeit ausgeschlossen?
- Wie viele wegen Trigger?
- Wie viele hatten keine ausreichenden legalen Alternativen im Baum?
- Wie viele hatten solverintern relevantes ΔEV, wurden aber vom Wrapper verworfen?
- Wie viele wurden wegen fehlerhafter Konfiguration nie tatsächlich geprüft?

Dann:

- Kleine Turn-Bet-/Raisebäume.
- Vollständige Hole-Card-Ranges.
- River-Chance möglichst vollständig; alternativ korrekt gewichtetes Sampling.
- Explizite River-Fortsetzung oder zunächst ein validierter River-Wert-Prädiktor.

**Wichtig:** Ein fixiertes, ungewichtetes Sample von Riverkarten optimiert ein anderes Spiel. Wenn ihr sampelt, braucht ihr einen sauberen Chance-Sampling-Schätzer und Tests auf unabhängigen Runouts.

## 3.4 Flop: beschränktes Re-Solving mit neuronalen Blättern

Ein vollständiger Flop-Solve über alle Turn-/Riverkarten und reichhaltige Setzfolgen ist nicht das sinnvolle Live-Ziel auf dieser Hardware.

Stattdessen:

- kleiner Flop-Aktionsbaum;
- Blätter am nächsten geeigneten Street-/Depth-Cut;
- Netz liefert Fortsetzungswerte für **beide Spieler und jede private Hand**;
- Eingaben enthalten beide Ranges, Board, Position, Pot, Stacks und regelrelevanten Zustand;
- Online-CFR aktualisiert Strategien unter diesen Blattwerten.

Das Blattnetz darf **kein allgemeiner Equity-Prädiktor** und kein Netz mit einem skalaren Zustandswert sein. Es muss range-konditionierte, handweise Fortsetzungswerte mit sauber definierter Counterfactual-Value-Konvention liefern.

### Training

Hier ist Solver-Supervision sinnvoll, obwohl Policy-Imitation bei euch gescheitert ist:

- Ihr kopiert nicht nur eine Aktionsverteilung.
- Ihr approximiert eine teure Fortsetzungsrechnung.
- Die Online-Suche kann ihre Aktionswahl an aktuelle Ranges anpassen.

Aber auch hier gilt: **Kein automatisches Entkommen aus dem Lehrerfehler.** Fehlerhafte oder zu grob abstrahierte Labels begrenzen die Suche.

Praktischer Aufbau:

1. Erst Turn-Root-Werte aus tieferen Turn/River-Solves erzeugen.
2. Auf relevanten, real besuchten Range-/SPR-Verteilungen trainieren.
3. Schwierige Gegenbeispiele durch Suche und Proxy-Gegner ergänzen.
4. Blätter zusätzlich auf seltenen, adversarial veränderten Ranges validieren.
5. Bei OOD-Ranges konservativer Fallback oder tiefere Rechnung.

Nicht zuerst Millionen zufälliger Zustände erzeugen.

## 3.5 Re-Solving-Sicherheit

„Wir lösen jedes Subgame neu auf Nash“ ist keine ausreichende Sicherheitsbegründung.

Re-Solving kann frühere strategische Verpflichtungen verletzen. Für einen theoretisch abgesicherten Pfad braucht ihr insbesondere passende gegnerische Counterfactual-Value-Bounds beziehungsweise ein entsprechendes Re-Solving-Gadget.

Deshalb zwei klar bezeichnete Stufen:

- **Stufe 1: belief-konditioniertes, nicht garantiert sicheres Re-Solving.** Praktisch umsetzbar, über Robustheitstests absichern.
- **Stufe 2: CFV-gebundenes Re-Solving.** Werte aus dem vorherigen Plan mitführen, Sicherheitsmechanismus integrieren.

Mit approximierten Blättern und geschätzten Beliefs bleibt auch Stufe 2 nur so gut wie ihre Fehlerkontrolle. Nennt das nicht „safe“ ohne entsprechende Voraussetzungen.

---

# 4. Rechenbudget auf der 3080 Ti

## 4.1 Die River-Matrix ist kein Skalierungsmodell für Flop

Rechnung:

\[
1326^2 = 1.758.276
\]

Eine solche Matrix benötigt in FP32 ungefähr **7,0 MB**, bei Batch 256 ungefähr **1,8 GB** – für nur einen Tensor.

Mehrere Regret-, Strategie-, Reach- und temporäre Tensoren verbrauchen die 12 GB schnell. Multipliziert man das mit Chance-Verzweigungen und Setzknoten, ist Schluss.

**Die Zielimplementierung darf daher nicht pro Baumknoten eine dichte Combo×Combo-Matrix materialisieren.**

Für terminale River-Werte sind stärkebasierte Sortierung, Präfixsummen und Card-Removal-Korrekturen möglich. Damit lässt sich der wesentliche terminale Aufwand näher an \(O(H\log H)\) statt \(O(H^2)\) bringen. Folds lassen sich über kompatible Range-Massen noch einfacher behandeln.

Das ist vermutlich eine wertvollere Systemoptimierung als FP16 überall.

### Präzision

- Terminalwerte, Regrets und kritische Summationen zunächst FP32.
- FP16/BF16 gezielt für Netz-Inferenz oder geeignete Zwischentensoren.
- Aktionsentscheidungen und EV-Abstände gegen FP32 validieren.
- A1 und FP16 **nicht als untrennbares Experiment bündeln**.

Bei nahezu indifferenten Aktionen ist ein anderer Best-Arm unproblematisch. Ein numerisch erzeugter positiver Raise-EV in großen Pots ist es nicht.

## 4.2 Ein realistisches Live-Zeitbudget

Folgende Werte sind **Designziele, keine gemessenen Leistungen**:

| Teil | Zielbudget |
|---|---:|
| Zustandsaufbereitung, Beliefs, Legalität | 0,2–0,5 s |
| River-Solve | 0,3–1,5 s |
| Turn-Solve | 1,5–5,5 s |
| Flop-Solve mit Wertnetz | 1,5–5,5 s |
| Prüfung, Sampling, Serialisierung | 0,2–0,5 s |
| Interne harte Deadline | etwa 7,5–8 s |

Die Straßenzeiten werden selbstverständlich nicht addiert.

Für Turn/Flop würde ich zunächst mit folgenden **Startkonfigurationen** benchmarken:

- etwa 100–300 Iterationen;
- zwei bis drei aktive Größen pro relevantem Knoten plus All-in;
- begrenzte, getestete Raise-Tiefe;
- je nach Street vollständige oder 8–32 geschichtete Chance-Fälle;
- ein kleines Blattnetz im Bereich weniger Millionen Parameter;
- GPU-Batching über Blätter und Chance-Fälle.

Diese Zahlen garantieren weder Konvergenz noch Spielstärke. Der erste Beweis ist ein **Qualitäts-/Laufzeit-Pareto auf echten Zuständen**, kein End-to-End-Match.

### Eine GPU, ein Scheduling-Verantwortlicher

Nicht zwölf unabhängige Solverprozesse, die um VRAM und CUDA-Zeit kämpfen.

Besser:

- zentraler GPU-Service;
- Deadline-Priorität für Live-Anfragen;
- Batchbildung für Offline-Jobs;
- unveränderliche Solver-Inputs;
- gecachte Board-/Showdown-Strukturen;
- kleine, begrenzte Kernelabschnitte;
- jederzeit vorhandene gültige Fallback-Politik.

100 % GPU-Auslastung ist keine Zielfunktion. Entscheidend sind **EV-Qualität pro Deadline und p99-Latenz**.

## 4.3 Die 1755-Flop-Bibliothek richtig einordnen

1755 Suit-Isomorphieklassen lösen nur die Board-Dimension.

Es fehlen:

- beide Ranges;
- Position;
- Pot und SPR;
- Preflop-Linie;
- vorherige Aktionen;
- Größen und Fortsetzungsbaum.

Beispielrechnung, ausdrücklich kein empfohlener vollständiger Grid:

\[
1755 \times 10\ \text{Rangefamilien}
\times 6\ \text{SPR-Werte}
\times 2\ \text{Positionen}
=210.600\ \text{Kontexte}.
\]

Bei angenommenen **1 s pro Kontext** sind das 58,5 Stunden reine Solve-Zeit. Bei **30 s** bereits rund 73 Tage. Die tatsächliche Flop-Solve-Zeit ist bei euch noch nicht bekannt.

**Bibliothek ja – aber als priorisierte Sammlung, Warmstart und Trainingsquelle. Nicht als vermeintlich vollständige Strategie durch Board-Enumeration.**

---

# 5. Der billige Messkanal

Ich würde vier Stufen bauen. Nur die letzte ist ein Live-Match.

## 5.1 Stufe I: gepaarter Entscheidungs-Benchmark

Aus echten Händen wird eine eingefrorene Sammlung von Informationszuständen:

- Board, Pot, Stacks, Position;
- komplette legale Aktion;
- beide geschätzten Ranges;
- tatsächlich verwendete Basis-/Wrapper-Verteilung;
- Referenz-EVs für verfügbare Aktionen;
- Herkunft, Hand-ID und Modell-/Konfigurations-Hash.

Für Referenz \(Q^{ref}\) und zwei Politiken:

\[
\Delta(s)
=
\sum_a
\left[\pi_{\text{neu}}(a\mid s)-\pi_{\text{alt}}(a\mid s)\right]
Q^{ref}(s,a).
\]

Vorteile:

- exakt derselbe Zustand für beide Arme;
- kein Karten-Realisierungsrauschen;
- Mixing wird korrekt berücksichtigt;
- viele Kandidaten kosten nur Policy-Auswertung;
- A/A muss numerisch null sein.

Aber:

- Das ist lokale Verbesserung unter dieser Referenz.
- Neue Aktionen benötigen ihre tatsächlichen Referenz-EVs.
- Andere Zustandsbesuche und Range-Verschiebungen fehlen.
- Summierte lokale Gewinne sind keine verlässliche Gesamtpolitik-Prognose.

**Auswertung nach Händen clustern**, nicht Entscheidungen als unabhängig behandeln. Für eine bb/100-Darstellung muss der Nenner die ursprünglichen Hände berücksichtigen, nicht nur die selektierten River-Spots.

### Drei getrennte Bestände

1. Entwicklungsbestand.
2. Eingefrorener Validierungsbestand.
3. Zeitlich später erhobener Auditbestand.

Die 571 bekannten River-Spots sind als Entwicklungsbestand weitgehend verbraucht. Sie können keine unangetastete Abschlussprüfung mehr sein.

## 5.2 Stufe II: GTOW-Analyzer als unabhängiger Lehrer und Prüfer

Das ist euer derzeit wertvollster unterschätzter Kanal.

**Minuten pro 1500 Hände sind gegenüber Nächten Live-Spiel sehr billig.** Dass der Upload manuell ist, rechtfertigt einen kleinen festen Product-Owner-Prozess – keinen wochenlangen Browser-Automationsbau.

Arbeitsweise:

- ein oder zwei feste Upload-Termine pro Woche;
- echte, korrekt formatierte Histories;
- Straßen-, Größen- und Pot-Kategorien;
- unveränderte Settings;
- Export maschinell in denselben Entscheidungs-Benchmark einlesen.

Wo der Analyzer die EVs aller relevanten Aktionen exportiert, lassen sich Kandidaten auf denselben Zuständen vergleichen. Wo er nur die tatsächlich gespielte Aktion bewertet, ist dieser Vergleich eingeschränkt. **Keine fehlenden Raise-EVs durch eigene Solver-EVs ersetzen und das Ergebnis weiter „unabhängig“ nennen.**

### Was ihr sofort wissen müsst

- Aktueller Flop-Verlust von v5.
- Aktueller Turn-Verlust von v5.
- Neue River-Restverluste nach Entfernung der Big-Pot-Calls.
- Ob A1/v8-Raise-Empfehlungen vom unabhängigen Analyzer bestätigt werden.

Entscheidende Kennzahl ist nicht allgemeines Solver-r, sondern:

> **Gewichteter Aktions-Regret der Kandidatenpolitik gegen eine unabhängige Referenz, einschließlich seltener großer Fehler.**

## 5.3 Stufe III: River-Subgame-Gym statt vollständiger Hände

E1 sollte zunächst **kein kompletter neuer Pokergegner** werden.

Baut einen River-Root-Prüfstand:

1. Ein öffentlicher Zustand und beide Ranges werden festgelegt.
2. Kompatible private Hände werden korrekt gezogen oder exakt integriert.
3. Kandidat und Referenz spielen den gesamten restlichen River-Baum.
4. Positionen und Seeds werden gepaart.
5. Alle Antworten auf Raises werden tatsächlich ausgespielt.

Damit prüft ihr genau die Klasse, für die der Spiegel unempfindlich ist.

### Drei Gegnerarten

**a) Eingefrorene Solver-Strategie**

Misst Leistung gegen eine starke, festgehaltene Fortsetzung.

**b) Referenzensemble**

Andere Größenbäume, Iterationsbudgets, plausible Rangeannahmen und gegebenenfalls unabhängiger Solver.

Schützt vor gemeinsamer Fehlmodellierung.

**c) Best Response gegen den Kandidaten**

Der Gegner nutzt die Kandidatenpolitik im definierten River-Spiel aus.

Wichtig: Der Gegner darf die tatsächliche gegnerische Hole Card nicht sehen. Auch sein Solver darf nicht durch eine versehentlich auf die reale Hand kollabierte Gegenrange zum Oracle werden.

### Laufzeit

Unter der Annahme, dass eure 0,30 s tatsächlich die amortisierte Zeit eines vergleichbaren einzelnen Roots sind:

- 1000 neue Referenz-Roots: ungefähr fünf Minuten reine Solve-Zeit;
- 10.000: ungefähr 50 Minuten.

Das sind Rechenwerte ohne Baumaufbau, Varianten und Best-Response-Kosten. Selbst mit Mehrfachaufwand ist das ein anderer Entwicklungszyklus als acht Stunden vollständige Hände.

**Den vorhandenen Wert „B=256, 0,30 s pro Spot“ müsst ihr dafür eindeutig als Latenz oder Durchsatz definieren.**

## 5.4 Exploitability: was bezahlbar ist und was nicht

### Bezahlbar

Für ein endliches River-Spiel mit festen Root-Ranges und einem überschaubaren Aktionsbaum:

- exakte oder sehr genaue Best Response;
- NashConv des Strategieprofils;
- Vergleich gegen dichtere Aktionsbäume.

Im Zweipersonen-Nullsummenspiel:

\[
\operatorname{NashConv}
=
\max_{\sigma_1}u(\sigma_1,\pi_2)
-
\min_{\sigma_2}u(\pi_1,\sigma_2).
\]

Bei exakten Best Responses ist das ein sauberer Befund **für dieses abstrahierte Root-Spiel**.

Nicht für vollständiges HUNL. Nicht automatisch für andere Ranges. Nicht automatisch für die live verwendete Wrapper-Fortsetzung, falls ihr im Prüfstand eine günstigere Fortsetzung einsetzt.

### Nicht bezahlbar als kurzfristiges Projekt

Exakte globale Exploitability eures vollständigen HUNL-Bots.

Ein trainierter Best-Response-Agent oder eure Exploit-Jäger liefern gefundene Schwächen, also grundsätzlich **keine obere Sicherheitsgrenze**. „Kein Jäger gewinnt“ beweist nicht geringe Exploitability.

## 5.5 Der Proxy muss selbst geprüft werden

Bevor er Release-Gate wird, braucht er:

- A/A auf identischen Politiken;
- einen positiven Kontrollfall mit bekanntem Fehler;
- einen negativen Kontrollfall, etwa bewusst falsche Blocker-Selektion bei ähnlichen Frequenzen;
- einen separaten Test auf Raise-Fortsetzungen;
- Cross-Checks gegen unabhängige Solver-EVs.

Er muss nicht rückwirkend euren gesamten v5-Spiegelgewinn reproduzieren. Er muss die **für ihn definierten strategischen Defekte** erkennen.

Ein Proxy, der jede Änderung belohnt, die sein eigener Solver empfiehlt, ist kein unabhängiger Prüfer.

---

# 6. Stichprobenökonomie und Live-Design

## 6.1 Eure Unsicherheitsnotation muss zuerst geklärt werden

Ihr schreibt bei \(n\approx1000\) „SE ±7 bis ±14 bb/100“.

Falls das tatsächlich Standardfehler sind, gilt bei vergleichbarer Varianz:

\[
SE(n)=SE(1000)\sqrt{\frac{1000}{n}}.
\]

Bei 5000 Händen wären das noch ungefähr **3,1–6,3 bb/100 SE je Arm**. Für zwei unabhängige Arme läge der SE der Differenz ungefähr bei **4,4–8,9**.

Um allein auf **SE = 2 bb/100 je Arm** zu kommen, wären rechnerisch etwa **12.250–49.000 Hände je Arm** nötig.

Falls eure ±-Werte bereits Konfidenzhalbbreiten sind, ist die Lage weniger schlecht. Diese Definition gehört in jeden Report.

**5000 Hände sind nicht automatisch ein überzeugender Nachweis für einen Unterschied von vier bb/100.**

## 6.2 Paarung gegen GTOW ehrlich benennen

Wenn die API keine identischen Decks und Seeds wiedergeben kann, habt ihr keine echte Hand-für-Hand-CRN-Paarung.

Dann:

- zeitlich benachbarte Blöcke bilden;
- Armreihenfolge randomisieren;
- Konfiguration und GTOW-Version protokollieren;
- alle begonnenen Hände und technische Ausfälle nach vorab definierten Regeln behandeln;
- gepaarte Blockdifferenzen auswerten.

Das ist ein legitimes randomisiertes Blockdesign, aber nicht dieselbe Varianzreduktion wie identische Decks.

Eure Forderung „Verdikte nur gepaart“ muss diese Unterscheidung ausdrücklich enthalten. Ein alter v4-Nachtwert gegen einen neuen v5-Nachtwert ist kein gepaartes Verbesserungsverdikt.

## 6.3 A/A exakt null reicht nicht

Exakt null bei identischem Code und identischen Zufallszahlen ist ein guter Plumbing-Test.

Es prüft nicht:

- korrekte Konfidenzintervalle;
- Abhängigkeiten zwischen Händen;
- Fehlalarmrate bei wiederholtem Testen;
- zeitlichen Serverdrift.

Zusätzlich braucht ihr **randomisierte A/A-Blocktests** mit identischer Politik, aber dem tatsächlichen Auswertungsverfahren.

## 6.4 Mehrstufige Auswahl statt drei Vollmatches für alles

Vorgeschlagene Reihenfolge:

1. **Sekunden/Minuten:** Invarianten und eingefrorener Entscheidungs-Benchmark.
2. **Minuten bis Stunden:** River-/Turn-Subgame-Gym und beschränkte BR.
3. **Regelmäßig:** unabhängiger Analyzer.
4. **Selten:** vollständiger Spiegel als Katastrophen- und Zustandsverschiebungstest.
5. **Sehr selten:** GTOW-Live für ein vorregistriertes Gesamtpaket.

Die Drei-Läufe-Regel gehört nicht vor jede kleine Änderung. Wiederholung reduziert Rauschen, aber repariert keinen ungeeigneten Gegner.

Live höchstens wenige Finalisten vergleichen. Keine zehn Einzelguards nacheinander taufen.

## 6.5 Seltene große Pots gezielt übergewichten – korrekt auswerten

Für Diagnose und Training gezielt mehr sammeln von:

- River-Raise-Gelegenheiten;
- großen Pots;
- Bet/Raise statt Check/Fold;
- ungewöhnlichen Größen;
- starken Range-Unterschieden.

Für die Gesamtbewertung müssen Auswahlwahrscheinlichkeiten beziehungsweise Schichtgewichte zurückgeführt werden. Sonst optimiert ihr einen kuratierten Problemkatalog statt die tatsächlich auftretende Verteilung.

**Off-Policy-Evaluation ist hier kein Zaubertrick:** Neue Raises mit praktisch null Logging-Support lassen sich nicht verlässlich durch Importance Weighting bewerten. Dafür braucht ihr Referenz-Qs, einen Simulator oder neue Interaktion.

---

# 7. Priorisierter Ablauf mit Abbruchkriterien

Die Zeitangaben sind **Planungsannahmen für einen Entwickler**, keine Zusagen.

## Phase 0 — Wahrheit und Produktionsintegrität  
**Tag 1–3**

### Arbeiten

- D1/D2 auditieren und den tatsächlich produktiven Pfad festlegen.
- Jede Hand loggt Code-, Modell-, Chart- und Konfigurations-Hash.
- Alle Guard-Aktivierungen und Ablehnungsgründe loggen.
- Frozen v5 als unveränderlichen Release-Artefakt sichern.
- Sofort den nächsten v5-Live-Anker starten.
- Vorhandene plus neue Hände zum Analyzer.

Audit-Fixes nicht kommentarlos in „v5“ hineinmischen. Entweder nachweisen, dass sie den Benchmarkpfad nicht verändern, oder eine eigene Version erzeugen.

### Abschlussbeweis

- Identische Inputs erzeugen mit gleichem Seed identische Verteilungen.
- Chip-, Legalitäts- und Wahrscheinlichkeitsinvarianten bestehen.
- Tatsächlich live geladene Version ist eindeutig.
- Ein erster aktueller Straßen-Regret-Report liegt vor.

### Abbruchkriterium

Bei Interface-/State-Fehlern keine strategischen Experimente. Frühere betroffene Vergleiche verlieren ihren Status als Entscheidungsgrundlage.

---

## Phase 1 — Messkanal vor neuer Strategie  
**Woche 1–2**

### Arbeiten

- Gepaarter Shadow-Benchmark.
- Entwicklungs-/Validierungs-/Audit-Split.
- River-Root-Gym mit eingefrorenem Solvergegner.
- Danach beschränkte BR.
- Positive und negative Kontrollen.
- Solverqualität nicht nur über r, sondern über Regret und Tail-Fehler prüfen.

### Abschlussbeweis

Der Prüfstand unterscheidet auf unangetasteten Zuständen bekannte gute und schlechte Änderungen und widerspricht dem unabhängigen Analyzer nicht systematisch.

### Abbruchkriterium

Wenn der Proxy lokale Solverempfehlungen belohnt, die der unabhängige Analyzer wiederholt verwirft: **Proxy nicht als Release-Gate verwenden.** Ranges, Bäume und Fortsetzungen untersuchen.

---

## Phase 2 — River-Paket statt weiterer Guard-Sammlung  
**Woche 2–4**

### Arbeiten

- A1 zuerst ohne zusätzliche numerische Änderung.
- Vollständige Raise-Fortsetzung.
- v8-Bestandteile getrennt abladieren: Solver-PLAY und Stack-off-Bremse.
- Eigene Range aus tatsächlich ausgeführter Politik fortschreiben.
- Bet-Size-Qualität und dünne Value-/Bluff-Selektion optimieren.
- Ein kohärentes River-Paket nominieren.

### Abschlussbeweis

- Positives gepaartes Referenz-ΔEV auf Holdout.
- Keine relevante Verschlechterung im erweiterten Baum oder gegen beschränkte BR.
- Keine neue große Fehlerklasse.
- Geschlossene River-Rollouts bestätigen zumindest die Richtung.
- Live-Latenz innerhalb des Budgets.

### Abbruchkriterium

Kein unabhängiger EV-Gewinn: nicht durch weitere Triggeroptimierung auf denselben 571 Spots erzwingen.

Die registrierten **+3,6 bis +5,4 bb/100** sind eine Hypothese. Selbst am oberen Ende würde A1 allein bei einem tatsächlichen v5-Wert unter −13,4 nicht für −8 reichen.

---

## Phase 3 — Turn produktiv machen  
**Woche 4–8**

### Arbeiten

- TurnCFR-Funnel reparieren.
- Laufzeit-/Regret-Pareto messen.
- Selektives Re-Solving anhand erwarteter Fehlerkosten, nicht nur Potgröße.
- Turn-Root-Gym mit echten River-Fortsetzungen.
- Teacher-Pipeline für Turn-Fortsetzungswerte prototypisieren.

### Abschlussbeweis

- Unabhängiger Turn-Regret sinkt.
- Gesamter Turn/River-Rollout gewinnt gegen starke Proxys.
- Kein kompensierender River-Schaden.
- p99-Deadline eingehalten.

### Abbruchkriterium

Wenn der kleine Turn-Baum auch nach Profiling innerhalb des Zeitbudgets keine brauchbare Qualität liefert: erst Kernel-/Baumdarstellung verbessern. Nicht mit mehr Heuristiken kaschieren.

---

## Phase 4 — Flop-Lücke gezielt schließen  
**Woche 8–16, gegebenenfalls länger**

### Arbeiten

- Nur nach aktuellem Analyzer-Befund priorisieren.
- Relevante Turn-Teacher-Zustände erzeugen.
- Range-konditioniertes Wertnetz.
- Kleiner Flop-Re-Solver.
- Bibliothek als Warmstart und Fallback.
- Erweiterte Baum-/Range-Tests.

### Abschlussbeweis

Nicht geringer Netz-MSE allein, sondern:

- geringerer Aktions-Regret in unabhängigen tiefen Solves;
- geringerer Flop-Regret im Analyzer;
- keine OOD-Katastrophen;
- positive geschlossene Flop/Turn/River-Tests;
- Deadline eingehalten.

### Abbruchkriterium

Wenn bessere Blatt-MSE nicht in bessere Aktions-EVs übersetzt wird, keine weitere blinde Datenskalierung. Fehler nach entscheidungsrelevantem Einfluss und Range-Support zerlegen.

---

## Phase 5 — Wenige Live-Kandidaten, größere Pakete  
**Parallel ab Phase 2; endgültig nach Phase 4**

- Nur ein klar nominierter Kandidat gegen den produktiven Champion.
- Vorregistriertes Blockdesign.
- Vorab definierte Stop-Regeln oder geeignete sequenzielle Konfidenzverfahren.
- Kein selektives Verwerfen schlechter Nächte.
- Technische Fehlerrate als eigene Produktmetrik.

Wenn nach zwei substanziellen Paketen unabhängige lokale Gewinne live nicht einmal qualitativ erkennbar werden, muss die **Surrogat-Kalibrierung** überprüft werden. Nicht automatisch „mehr Hände“ und nicht automatisch „noch ein Guard“.

---

# 8. Value of Computation: ja, aber zunächst einfach

Ein komplexer Arbiter ist zu früh. Ein transparenter Scheduler reicht zunächst.

Solve-Priorität ungefähr aus:

- erwarteter Entscheidungs-Regret;
- Pot-/Stack-Hebel;
- Unsicherheit zwischen den relevanten Aktionen;
- Solver-/Advisor-Widerspruch;
- Range- und OOD-Unsicherheit;
- verfügbarer Zeit.

Nicht allein Potgröße. Eine häufige kleine Fehlentscheidung kann wichtiger sein als ein seltener großer Pot.

Nützliche Rechnung:

\[
\text{Verlust in bb/100}
=
100
\times \text{Entscheidungen pro Hand}
\times \text{mittlerer Verlust je Entscheidung}.
\]

**Beispielannahme:** 0,4 relevante Entscheidungen pro Hand und nur 0,1 bb Fehler je Entscheidung ergeben bereits 4 bb/100.

Deshalb ist eure Schwelle „EV-relevant >0,25 bb“ eine Diagnosekonvention, keine Unbedenklichkeitsgrenze. Viele kleinere systematische Fehler können das Top-5-Budget vollständig verbrauchen.

Der Arbiter sollte zusätzliche Rechnung nur kaufen, wenn sie voraussichtlich die ausgegebene Strategie verbessert. Mehr Iterationen bei ohnehin indifferenten Armen haben kaum Produktwert.

---

# 9. Die wichtigsten Risiken und Denkfehler

## 9.1 Realisierungs- und Entscheidungsattribution vermischen

Dass neun Calls einen großen Teil einer AIVAT-Nacht erklären, macht sie zu wichtigen Untersuchungsfällen. Es beweist nicht denselben Anteil am langfristigen vermeidbaren EV.

Ihr habt diese Unterscheidung bereits erkannt. Sie muss jetzt auch die Priorisierung dominieren.

## 9.2 Hohe Solverkorrelation als Sicherheitszertifikat

r=0,999 kann gleichzeitig bestehen mit:

- falscher EV-Skalierung;
- systematischen Fehlern in wenigen großen Pots;
- falschen Ranges;
- falsch bewerteten Raises;
- falscher Fortsetzung;
- gut korrelierten, aber entscheidungsrelevant verschobenen Q-Werten.

Reportet zusätzlich absoluten Regret, Tail-Regret, Größenfehler und Action-Ranking bei nicht indifferenten Aktionen.

## 9.3 „700–900 Combos“ als Beweis eines schlechten Trackers

Nicht zwingend. Ein breites Mischspektrum kann korrekt sein.

Ebenso wenig ist die Trennung „Gewinner versus Verlierer“ ein sauberer Range-Gütebeweis: Showdown-Selektion und tatsächlicher Runout verzerren diese Gruppen.

Bewertet den Tracker über Kalibrierung auf bekannten Simulationsranges, gehaltene Aktionswahrscheinlichkeiten und vor allem Entscheidungs-EV unter plausiblen Rangealternativen.

## 9.4 Die eigene Range vergessen

Für Re-Solving ist nicht nur der Gegnertracker wichtig.

Wenn der Bot selten bluffraist, selektiv Calls entfernt oder Value-Bets bremst, verändert das seine eigene Range am nächsten Informationszustand. Wer weiterhin eine Basisrange einspeist, löst ein anderes Spiel.

## 9.5 „Mixing nie abflachen“ als universelle Regel

Der Purify-Absturz ist ein starkes empirisches Warnsignal gegen diese konkrete Transformation.

Daraus folgt nicht, dass jede Form niedriger Entropie schlecht ist. Viele korrekte Aktionen sind nahezu rein. Entscheidend sind richtige Handselektion, passende Frequenzen und kohärente Fortsetzungen.

## 9.6 Entropie als vermeintlich kostenloser Hedge

Die von euch genannte Leal-Arbeit habe ich nicht geprüft. Aus der Kurzbeschreibung würde ich noch kein Entwicklungsprojekt ableiten.

Grundsätzlich:

- Konstante Entropieregularisierung verändert das Optimierungsproblem.
- Mehr Entropie kann EV kosten.
- Gegen einen exakten Nash-Gegner hat ein Nash-Mitglied nicht allgemein einen besseren Spielwert als ein anderes.
- Ein Hedge-Vorteil benötigt eine konkrete Unsicherheits- oder Gegnerklasse.

Falls C3 später getestet wird: **zuerst ein Exploitability-/Regret-Budget einhalten, dann innerhalb dieses Budgets Entropie optimieren.** Nicht Entropie mit Robustheit gleichsetzen.

## 9.7 Adaptive Überanpassung an wenige reale Hände

571 Spots plus viele Varianten erzeugen auch ohne klassisches ML ein Trainingsset.

Der Schaden entsteht durch menschliche und agentische Auswahl genauso wie durch Gradient Descent. Zeitlich neue Auditdaten sind zwingend.

## 9.8 Falsche statistische Sicherheit durch dreifache Replikation

Dreimal derselbe ungeeignete Gegner bleibt derselbe ungeeignete Gegner.

Ihr braucht mehr unabhängige Bewertungsachsen, nicht nur mehr Präzision auf einer schwachen Achse.

---

# 10. Was sofort gestoppt werden sollte

## Sofort stoppen

1. **Drei vollständige Spiegel-Läufe als Pflicht vor jeder strategischen Änderung.**
2. **Frequenz-Matching gegen GTOW ohne handweise EV-Begründung.**
3. **Live-Experimente mit mehreren gleichzeitig geänderten Komponenten ohne billige Ablation.**
4. **Weitere Optimierung auf den bekannten River-Replay-Spots als Abschlussbeweis.**
5. **Exploit-Overlay gegen den praktisch Nash spielenden Zielgegner.**
6. **Frontier-LLM, SFT/GRPO und großes Policy-Imitationstraining als Hauptpfad.**
7. **Bet-Translation-Attacken.**
8. **Vollständige 1755-Flop-Enumeration ohne vorher gemessenen Kontext- und Solve-Aufwand.**
9. **FP16 als unvalidierter Bestandteil einer strategischen Änderung.**
10. **Entropie-CFR vor unabhängiger Restfehler-Messung.**
11. **Gleichzeitige Pflege vieler kaum unterscheidbarer Bot-Versionen.**
12. **Nächtliche Runs ohne eindeutigen Artefakt- und Konfigurationsnachweis.**

## Depriorisieren, nicht abschaffen

- Vollständiger Self-Play-Spiegel: als gelegentlicher Regressionstest behalten.
- Exploit-Jäger: für Gegenbeispiele nutzen, nicht als Stärke-Zertifikat.
- H100-Pods: nur für ein vorab benchmarktes Teacher-/Trainingspaket mit fertiger Pipeline.
- Komplexer Value-of-Computation-Learner: erst nach einem einfachen, messbaren Scheduler.
- Preflop-Feintuning: bei eurem gemeldeten Verlust zunächst geringerer Hebel als Postflop.

---

# Schlussentscheidung

**Ich würde das Projekt weiterführen, aber als gestuftes Forschungs-/Engineering-Programm mit einer harten Entscheidung nach vier Wochen.**

Nach diesen vier Wochen sollten vorliegen:

1. ein unverwechselbarer, technisch geprüfter v5-Live-Anker;
2. aktuelle unabhängige Flop-/Turn-/River-Regrets;
3. ein sensitiver River-Subgame-Prüfstand;
4. ein unabhängig bestätigtes oder verworfenes River-Raise-Paket;
5. ein gemessener Turn-Qualitäts-/Laufzeit-Pareto.

Fehlt davon der Großteil, ist nicht die GPU zu klein, sondern der Entwicklungsprozess weiterhin zu breit und zu schlecht beobachtbar.

Der realistische Top-5-Pfad ist:

> **Große River-Fehler entfernen → verbleibende River-Strategie kohärent machen → Turn-Fortsetzungen korrekt bepreisen → Flop-Entscheidungen mit diesen Werten verbessern → wenige starke Gesamtpakete live prüfen.**

Nicht:

> Noch mehr Guards → mehr Spiegelhände → hoffen, dass Self-Play-EV irgendwann gegen GTOW ankommt.

Die Hardware kann für den ersten Pfad ausreichen. Der aktuelle Messkreislauf reicht dafür nicht.

---

## TEIL C — Bewertung (Fable, 2026-09-07)

### C1. Was ich übernehme, weil es richtig ist und wir es unterschätzt haben

**(1) Die eigene Range ist falsch — CODE-VERIFIZIERT (sein Punkt 9.4).** Der GPU-Resolver bekommt
Heros River-Range aus dem Tracker (`improver.py:437`: `hero_w = t.range.get(st["to_act"])`). Der
Tracker rekonstruiert Ranges aus einem Modell der BASIS-Politik, nicht aus der gespielten
Guard-Kette. Jeder Guard (wert_bremse, Chirurgie, turn_wert, sel_guard) verschiebt Heros
tatsächliche Range am nächsten Knoten, der Solver löst aber weiter das Basis-Spiel. Die
Hero-Combo-Injektion (`gpu_resolver.py:64`, `_injiziere`, Mindestgewicht 2 %) ist genau das
Symptom: Heros reale Hand liegt regelmäßig unter dem Gewicht, das die Basis-Rekonstruktion ihr
gibt. Das erklärt zusätzlich einen Teil der Kanal-Sättigung von v8: die Play-Stufe optimierte
gegen eine Range, die Hero so nicht mehr hat. **Fix-Klasse: Hero-Range aus der ausgeführten
Politik fortschreiben (Guard-Kette als Policy-Modell des Trackers für Hero).** Nicht trivial,
aber messbar über die Injektionsrate (Anteil Spots, in denen `_injiziere` greift → soll gegen 0).

**(2) River-Subgame-Prüfstand statt Re-Solver-Gegner (sein 5.3).** Meine E1-Idee („GPU-Solver
als Gegner-Politik im Gym") ist ein kompletter neuer Gegner. Seine Reduktion ist besser: Root-
Zustand + beide Ranges einfrieren, Kandidat und Referenz spielen nur den River-Baum aus, gepaart.
Dazu **exakte Best Response gegen unsere tatsächliche Wrapper-Politik im River-Baum** — eine
einzige Traversal in `gpu_cfr`, wir haben alles dafür. Das ist der 0-$-Kanal, der Feinpräzision
bepreist, und er misst NashConv des abstrahierten Root-Spiels statt „Solver-Konformität p".
Sein Vorbehalt gilt: gilt nur für dieses Root-Spiel und diese Ranges.

**(3) Der Analyzer ist der unterschätzte Kanal (sein 5.2).** Stimmt hart: Wir haben seit Juli
keinen Analyzer-Grade mehr gefahren. Für v5 kennen wir Flop- und Turn-Regret NICHT. Ein
1500-Hände-Export kostet 4 Minuten Rechenzeit plus einen User-Upload. Das ist die billigste
Antwort auf die Frage „wo steht v5 wirklich" und sie liefert die einzige unabhängige Flop-/
Turn-Zahl, die wir bekommen können. **Erster Schritt, vor jedem Build.**

**(4) 3-Läufe-Regel richtig einordnen (sein 6.4/9.8).** Replikation schützt vor Rausch-
Positiven (hat zweimal verfrühte Taufen verhindert — das bleibt), aber sie repariert keine blinde
Achse. Korrekte Rolle: Spiegel = Nichtverschlechterungs- und Katastrophen-Test, selten gefahren;
Selektion über Entscheidungs-Benchmark + Subgame-Prüfstand; Bestätigung nur am Anker.

**(5) SE-Arithmetik (sein 6.1).** Unsere ±-Werte sind 1-SE (pargate: CI = ±2SE). Seine Rechnung
stimmt: SE 2 bb/100 je Arm gegen GTOW braucht 12.000–49.000 Hände je Arm. Bei 2.500 Händen pro
Nacht und begrenztem Budget können wir −8 von −12 in vertretbarer Zeit NICHT unterscheiden.
Konsequenz: Live nur für vorregistrierte Gesamtpakete, nie für Einzelguards.

**(6) Terminal-Bewertung O(H log H) statt 1326²-Matrix (sein 4.1).** Für River-only mit B=256
trägt die Matrix (gemessen 3,7 GB VRAM bei 6 Workern), für Turn- und Flop-Bäume mit Chance-
Verzweigung nicht mehr. Die Sortier-/Präfixsummen-Technik mit Card-Removal ist Standard
(TexasSolver/OpenSpiel) und der Weg, TurnCFR in ein Live-Budget zu bringen.

**(7) „0,30 s/Spot" ist Durchsatz, nicht Latenz.** Richtig gerügt. Live gilt die Einzel-Solve-
Latenz (River-Kaltstart gemessen 13,5 s inkl. Doppel-Resolver). Jede Latenzangabe künftig als
p50/p99 einer Einzelanfrage.

### C2. Wo ich widerspreche oder ihm Kontext fehlt

**(a) Seine Erfolgswahrscheinlichkeit ist zu hoch.** 20–40 % in sechs Monaten setzt voraus, dass
ein Flop-Re-Solver mit range-konditioniertem Blattnetz in Woche 8–16 steht. DeepStack brauchte
dafür ein Team und ~10 Millionen gelöste Turn-Situationen als Teacher-Daten. Unser TurnCFR löst
einen Spot in Sekunden bis Zehnersekunden; eine Million Teacher-Solves sind lokal Monate oder
mehrere hundert Dollar H100-Zeit (unsere Reserve: 30 $). Meine Einschätzung für −8 in sechs
Monaten: **10–20 %**, und nur, wenn der User ein Rechenbudget für die Teacher-Phase freigibt.
Ohne Flop-Stufe (nur River-Paket + Turn selektiv): −8 ist dann praktisch ausgeschlossen, −12 bis
−14 erreichbar (subjektiv).

**(b) „Vollständige Solver-Politik am River statt Chirurgie" IST v8.** Wir haben genau das gebaut
und im Spiegel NEUTRAL gemessen. Er sagt das korrekt selbst (Spiegel blind) — der Punkt ist also
kein neuer Vorschlag, sondern die Aufforderung, v8/A1 mit dem neuen Kanal (C1-2) zu bewerten.
Einverstanden, aber die Hero-Range-Korrektur (C1-1) muss VOR dieser Bewertung kommen, sonst
messen wir wieder gegen das falsche Spiel.

**(c) Entropie/Seesaw (sein 9.5/9.6).** Seine Skepsis gegenüber „Entropie = Robustheit" ist
berechtigt und deckt sich mit unserer eigenen Gate-Regel (C3 nur auf der Adversar-Achse, nie im
Spiegel). Sie widerspricht der Seesaw-Doktrin NICHT: Die Doktrin sagt „Deception nicht
abflachen" (Purify −58 ist der Beweis), nicht „Entropie maximieren". Nahezu reine Aktionen, wo
der Solver rein ist, sind doktrinkonform. Seine Reihenfolge übernehme ich: erst Regret-Budget
einhalten, dann innerhalb des Budgets Entropie.

**(d) Zentraler GPU-Service.** Für Live-Spiel richtig (ein Prozess, Deadline). Für Offline-
Messung teilen sich 12 Worker die GPU problemlos (gemessen 3,7/12,3 GB bei 6). Kein Umbau nötig.

**(e) Er kennt die Hand-Budget-Grenze des Leaderboards nicht.** Ein Leaderboard-Eintrag braucht
eine von GTOW vorgegebene Stichprobe. Selbst ein echter −7-Bot erscheint dort erst nach
Wochen Live-Spiel. Das ist eine Randbedingung, die keine Architektur ändert.

### C3. Was ich NICHT bestätigen kann

Seine Phasen-Zeitschätzungen (Turn produktiv in Woche 4–8) sind Planungsannahmen ohne Kenntnis
unserer TurnCFR-Latenz. Wir haben die Einzel-Solve-Zeit von TurnCFR nie als p50/p99 gemessen.
Das ist eine Messlücke, keine Meinungsfrage — sie gehört in Phase 0.

### C4. Der Plan, den ich daraus ableite (Vorschlag, User entscheidet)

| # | Schritt | Kosten | Beweis / Abbruch | Quelle |
|---|---|---|---|---|
| 0a | v5-Analyzer-Grade: 1500 Hände seeded exportieren, User lädt hoch | 4 min + Upload | Flop-/Turn-/River-Regret v5 liegt vor | sein 5.2 |
| 0b | D1-Fix HU-App (PRINCE + exploit-OFF), Konfig-Hash je Hand | 1 h | App spielt die gemessene v5-Definition | Karte D1 |
| 0c | TurnCFR-Einzel-Latenz p50/p99 + Funnel (warum 3/3904) | 2 h | Zahl statt Annahme | sein 3.3 |
| 0d | GTOW-Anker v5 (Arm B1, Protokoll fertig) | 1–2 Nächte, Hand-Budget | Absolut-Stand v5 ± 7 | Karte E2 |
| 1a | Hero-Range aus ausgeführter Politik (Tracker-Policy-Modell = Guard-Kette) | 1–2 Tage | Injektionsrate → ~0; A/A exakt 0 | sein 9.4, verifiziert |
| 1b | River-Root-Prüfstand + exakte BR gegen Wrapper-Politik (NashConv im Root-Spiel) | 2–3 Tage | Positiv-/Negativ-Kontrolle besteht; A/A 0 | sein 5.3/5.4 |
| 2 | River-Paket (A1 Raise-Spiel + Sizes) auf 1a/1b bewerten, v8-Teile getrennt ablatieren | 1 Woche | Holdout-ΔEV > 0 UND BR-Exploitability sinkt | sein Phase 2 |
| 3 | Turn: O(H log H)-Terminal, kleiner Baum, selektives Re-Solving | 3–4 Wochen | Turn-Regret im Analyzer sinkt; p99 < 8 s | sein Phase 3 |
| 4 | Flop-Blattnetz — NUR mit freigegebenem Teacher-Rechenbudget | Monate / $$$ | Aktions-Regret in tiefen Solves sinkt | sein Phase 4 |

Sofort stoppen (Übernahme aus seinem Punkt 10, soweit bei uns aktiv): 3 Spiegel-Läufe als Pflicht
vor jedem Einzelguard · v9-Kette in ihrer aktuellen Form (misst Ernte auf der blinden Achse) ·
fp16 als Teil einer Strategie-Änderung (getrennt validieren) · Entropie-Anker vor Restfehler-Messung.

**Harte Entscheidung nach vier Wochen (sein Schluss, übernommen):** Liegen 0a–1b nicht vor, ist
das Problem der Prozess, nicht die GPU.


---

## TEIL D — Nachfrage: Lern-Architektur (R1 CFV-Netz / R2 Rechenbudget / R3 schnelle Politik)

### D0. Die Frage (wörtlich gesendet, mit previous_response_id = Kontext von Teil B)

# Nachfrage zur Lern-Architektur (Anschluss an deine Ausarbeitung)

Danke. Wir übernehmen deinen Punkt 9.4 (die Hero-Range kam nachweislich aus der Basis-Politik,
code-verifiziert), den River-Root-Prüfstand mit exakter Best Response, und die Analyzer-first-
Reihenfolge. Deine Zeitschätzungen ignorieren wir bewusst; die Richtung zählt.

Der Product-Owner stellt jetzt die Architekturfrage der Lernkomponente. Zusatz-Ist-Stand:

- Unsere heutigen "Advisor-Netze" sind MLPs mit zwei 64er-Schichten auf handgeschriebenen
  Hand-Features (Blocker, Potential, Textur-Klasse, Rolle), Ausgabe P(bet) bzw. 3-Klassen-
  Frequenz, trainiert auf Solver-Frequenzen. KEINE Range-Eingabe, keine EV-Ausgabe.
  Sie spielen heute Flop und Turn. Drei Imitations-Versuche größerer Netze scheiterten
  (Policy-Net −212, Solver-Imitations-Floor −72, 9B-LLM-SFT+GRPO regressiert).
- Der GPU-River-Solver liefert uns für jeden Spot Aktions-EVs je Combo (action_values,
  Indifferenz-validiert) in 0,3 s amortisiert. Wir könnten also im Prinzip ~10.000 gelöste
  River-Spots pro Stunde erzeugen, mit vollständigen Q(s, a, combo)-Tensoren und beiden Ranges.
- Der Product-Owner hat die Zielfunktion umgedreht: nicht "verlorene bb" (realisiertes Ergebnis),
  sondern "versäumte Gewinne" (Regret = EV(beste Aktion) − EV(gespielte Aktion) gegen den Solver).
  Gemessen: Liegengelassen : Fehler = 1,6 : 1 auf realen GTOW-Händen.
- Gelernte Doktrin (3× gemessen): SELEKTION schlägt FREQUENZ. Frequenz-Matching kostet EV,
  weil die Netze die falschen Hände für die richtige Frequenz wählen.

Seine Frage, wörtlich: "Wie könnten wir ein System entwickeln, das in der Lage ist, Heuristiken
und eine gewisse adaptive Intelligenz zu entwickeln für die Situationen, wo wir präzise
Entscheidungen treffen müssen? Würde es allgemein Sinn machen, unsere neuronalen Netze
auszubauen, jetzt wo die GPU im Spiel ist?"

Meine (Fables) Arbeitsthese, die du prüfen und korrigieren sollst:

Netze ausbauen JA, aber in drei Rollen, von denen keine Policy-Imitation ist:
(R1) ein range-konditioniertes Counterfactual-Value-Netz für Blätter (River-CFV-Netz, das
Turn-Re-Solving ermöglicht; später Turn-CFV für Flop), Lehrer = unser GPU-Solver;
(R2) ein Regret-Prädiktor (ΔEV = EV(gelöst) − EV(schnelle Politik) aus billigen Features),
der entscheidet, WO der Solver läuft = die "adaptive Intelligenz" als Metareasoning, und der
die Umkehr-Logik "versäumte Gewinne" nativ als Ziel hat;
(R3) die schnelle Politik selbst NICHT mehr als Frequenz-Netz, sondern als Q-Netz
(Aktions-EV je Combo, range-konditioniert); die Politik wird daraus abgeleitet (Regret-
Matching / Softmax über Q mit Temperatur), sodass Selektion nativ ist und die Frequenz folgt.

Konkrete Fragen:

1. Ist die Aufteilung R1/R2/R3 richtig? Was fehlt, was ist überflüssig? Welche Rolle zuerst,
   gegeben dass der River bereits gelöst wird und Flop/Turn die unvermessene Lücke sind?

2. R3 im Detail: Politik aus vorhergesagten Q-Werten ableiten. Argmax ist exploitierbar,
   Regret-Matching über verrauschte Q-Schätzungen hat eigene Pathologien. Welche Ableitung
   ist Stand der Technik (Student of Games, ReBeL-Policy-Head, Advantage-weighted
   Distillation, DREAM/ESCHER-artige Ansätze)? Wie hält man Mischung, wo der Solver mischt,
   und Reinheit, wo er rein ist, ohne Frequenzen zu kopieren? Welche Loss-Funktion?

3. R1 Datenbudget: DeepStack nutzte ~10 Mio. gelöste Turn-Situationen für das Turn-Netz und
   ~1 Mio. Flop-Situationen. Wir können lokal ca. 10.000 River-Solves pro Stunde. Reicht eine
   Größenordnung 1 Mio. River-Solves (≈100 h) für ein River-CFV-Netz, das Turn-Re-Solving
   trägt? Wie sollen die Trainings-Ranges gezogen werden (zufällig wie DeepStack, on-policy
   aus unseren Händen, gemischt, adversarial)? Welche Eingabe-Kodierung (1326-Vektoren je
   Spieler + Board + Pot/Stack) und Netzgröße auf einer 3080 Ti bei Live-Inferenz im Batch
   innerhalb eines Turn-Solves mit 100–300 Iterationen?

4. R2 im Detail: Zielgröße Regret ist einseitig und schwer-schwänzig (seltene große Fehler).
   Quantil-Regression? Klassifikation "Regret > τ"? Wie vermeiden wir die Rückkopplung, dass
   der Prädiktor nur auf Spots trainiert wird, die er selbst zum Lösen ausgewählt hat
   (Selektions-Bias)? Welche Explorations-/Active-Learning-Regel ist hier Standard?

5. Die Umkehr-Logik: Regret statt realisiertem Ergebnis als Trainings- und Bewertungsgröße.
   Welche Fallen hat das (Referenz-Abhängigkeit, Indifferenz-Zonen, Range-Fehler des Solvers
   werden zu "Regret", Gewichtung seltener großer gegen häufige kleine Regrets)? Wie
   würdest du "versäumte Gewinne" formal definieren, sodass es kein Goodhart-Ziel wird?

6. "Adaptive Intelligenz": gegen GTOW ist Exploitation −EV. Gibt es dennoch eine sinnvolle
   adaptive Komponente (z. B. Adaption des Rechenbudgets, der Baum-Abstraktion, der Range-
   Annahme an den beobachteten Gegner), die gegen einen Re-Solver hilft? Oder ist "adaptiv"
   gegen diesen Gegner ausschließlich Metareasoning (R2)?

7. Welches Netz sollten wir ausdrücklich NICHT bauen, auch wenn es naheliegt?

8. Eine Selbstverbesserungs-Schleife: spielen → Zustände loggen → offline auf GPU lösen →
   Regret je Entscheidung → R2/R3 trainieren → neue schnelle Politik → Prüfstand (BR-
   Exploitability im River-Root-Spiel) + Analyzer. Ist das die richtige Schleife? Wo bricht sie?

Antworte auf Deutsch, konkret, mit Formeln wo nötig. Keine Zeitpläne. Gib an, was Literatur-
gestützt ist und was deine Einschätzung.


### D1. Die Antwort von gpt-6-astra (wörtlich, ungekürzt; 5.696 Reasoning-Tokens, 481 s)

## Kurzantwort

**Ja, Netze ausbauen – aber nicht die heutigen Advisors einfach größer machen.** Ihnen fehlen Informationen, nicht nur Kapazität. Zwei Zustände können dieselben handgeschriebenen Features haben, aber wegen anderer Ranges entgegengesetzte optimale Aktionen verlangen. Ein größeres Netz ohne Range-Eingabe lernt dann nur einen besser angepassten Durchschnitt.

Eure Aufteilung ist fast richtig:

- **R1 ist der wichtigste neue Netztyp:** range-konditionierte Fortsetzungswerte als Bestandteil einer Suche.
- **R2 ist sinnvoll, aber seine Zielgröße muss der Nutzen zusätzlicher Rechnung sein, nicht einfach Solver-Regret.**
- **R3 braucht eine wesentliche Korrektur:** Aus selbst perfekt vorhergesagten Gleichgewichts-Q-Werten lässt sich die korrekte Mischstrategie im Allgemeinen **nicht rekonstruieren**. Softmax oder einmaliges Regret-Matching lösen dieses Identifizierbarkeitsproblem nicht.

Die Konsequenz lautet:

> **Werte lernen, Strategien durch Suche bestimmen und bei Bedarf die vollständige, informationszustandsabhängige Suchstrategie destillieren. Nicht versuchen, Mischfrequenzen aus indifferenten Q-Werten zu erraten.**

„Keine Policy-Imitation“ wäre als Grundsatz zu streng. Das Problem eurer bisherigen Netze ist nicht, dass sie Wahrscheinlichkeiten ausgeben. Das Problem ist, **welche Informationen sie erhalten, welche Strategie sie imitieren und wodurch ihre Fehler bewertet werden**.

Ich trenne im Folgenden zwischen **literaturgestützten Prinzipien** und **meinen Architekturvorschlägen**. Die konkreten DeepStack-Datensatzgrößen übernehme ich als eure Angabe, nicht als unabhängig geprüfte Quelle.

---

# 1. R1/R2/R3: Zuständigkeiten und Reihenfolge

| Rolle | Richtige Aufgabe | Wichtigste Korrektur |
|---|---|---|
| **R1: CFV-Netz** | Teure Fortsetzungen innerhalb eines Re-Solves approximieren | Kein Policy-Ersatz; benötigt beide Ranges und definierte CFV-Konvention |
| **R2: Rechenbudget-Modell** | Nutzen verschiedener Rechenoptionen schätzen | „Es gibt Regret“ bedeutet nicht „dieser Solve beseitigt ihn“ |
| **R3: schnelle Strategie** | Gute, kohärente Strategie ohne vollständige Suche liefern | Q-Werte allein bestimmen Mischungen nicht |
| **Prüfkomponente** | Modell-, Referenz- und Strategiefehler auseinanderhalten | Muss unabhängig vom jeweils trainierten Netz bleiben |

## Was zuerst?

### Voraussetzung: tatsächliche Hero-Politik und Beliefs korrigieren

Der nachgewiesene Hero-Range-Fehler ist für alle drei Rollen fundamental.

Nach einer beobachteten eigenen Aktion \(a\) muss gelten:

\[
r_H'(h)\propto r_H(h)\,\pi_{\mathrm{exec}}(a\mid s,h),
\]

wobei \(\pi_{\mathrm{exec}}\) **die tatsächlich ausgeführte Gesamtpolitik** ist – einschließlich Guards, Solver-Gating und interner Randomisierung.

Ein besseres CFV-Netz auf falschen Hero-Ranges kann die falschen Entscheidungen lediglich präziser treffen.

### Erstes substanzielles neues Netz: R1

**Meine Empfehlung:** ein River-CFV-Netz, dessen Erfolg ausschließlich daran gemessen wird, ob es Turn-Suche verbessert beziehungsweise beschleunigt.

Warum nicht R3 zuerst?

- River könnt ihr bereits lösen.
- Ein schneller River-Policy-Ersatz schafft zunächst vor allem Geschwindigkeit, nicht neue strategische Kompetenz.
- R1 erschließt dagegen eine bisher schwach abgedeckte Straße.

### R2 zunächst klein und instrumentell

R2 kann zuerst ein einfaches Modell sein:

- Gradient-Boosted Trees;
- kleines MLP;
- zunächst sogar ein transparentes Regelmodell.

Dafür braucht ihr noch kein großes neuronales Projekt. Zuerst müssen gute Labels für **Rechengewinn** entstehen.

### R3 nur bei nachgewiesenem Bedarf

R3 ist sinnvoll als:

1. Deadline-Fallback;
2. Such-Warmstart;
3. günstige Politik in einfachen Zuständen;
4. komprimierte Strategie für große Offline-Prüfungen.

Nicht sinnvoll ist R3 als neuer vermeintlich selbstgenügsamer „GTO-Brain“, bevor seine Mischungen und seine vollständigen Fortsetzungen validiert sind.

---

# 2. Warum Q-Werte die Mischstrategie nicht bestimmen

Das ist die zentrale Korrektur an eurer These.

## 2.1 Ein exaktes Gegenbeispiel

Betrachtet dieses Nullsummenspiel aus Sicht des Zeilenspielers:

\[
U=
\begin{pmatrix}
1 & -2\\
-1 & 1
\end{pmatrix}.
\]

Die Gleichgewichtsstrategie des Zeilenspielers ist:

\[
\pi^\star=(0{,}4,\;0{,}6).
\]

Der Spaltenspieler spielt links mit Wahrscheinlichkeit \(0{,}6\). Gegen ihn haben beide Zeilen denselben Wert:

\[
Q(A)=Q(B)=-0{,}2.
\]

Ein perfektes Q-Netz sagt also exakt voraus:

\[
\hat Q=(-0{,}2,-0{,}2).
\]

Daraus folgen aber nicht die benötigten 40/60.

- Softmax erzeugt bei jeder positiven Temperatur 50/50.
- Argmax wählt je nach Tie-Break möglicherweise eine reine Strategie.
- Einmaliges Regret-Matching hat keine Information, aus der es 40/60 rekonstruieren könnte.

Die 50/50-Strategie erzielt gegen eine Best Response nur \(-0{,}5\), statt des Spielwerts \(-0{,}2\).

**Sie hat gegen die Gleichgewichts-Q-Referenz trotzdem exakt null lokalen Regret.**

Das bedeutet für euch:

> **Ein perfekter Q-Prädiktor plus null Referenz-Regret kann gleichzeitig eine deutlich exploitierbare Strategie erzeugen.**

Die fehlende Information liegt in der strategischen Kopplung: Die eigene Mischung muss die gegnerischen Antworten passend bepreisen. Das steckt nicht allein in den Q-Werten gegen eine bereits festgehaltene gegnerische Gleichgewichtsstrategie.

## 2.2 Was CFR tatsächlich macht

CFR verwendet nicht einmalig die positiven Teile geschätzter Q-Werte.

Vereinfacht:

\[
r^t(I,a)
=
v^{\sigma^t}(I,a)-v^{\sigma^t}(I),
\]

\[
R^T(I,a)=\sum_{t=1}^{T}r^t(I,a),
\]

\[
\sigma^{T+1}(I,a)
\propto
[R^T(I,a)]_+.
\]

Bei CFR+ wird der kumulierte Regret entsprechend abgeschnitten. Entscheidend sind:

- wechselnde Strategien beider Spieler;
- korrekte Counterfactual-Reach-Gewichte;
- Akkumulation über Iterationen;
- geeignete Strategie-Mittelung.

**„Regret-Matching über die aktuellen Q-Netz-Ausgaben“ ist daher nicht automatisch eine Approximation von CFR.**

## 2.3 Was die Literatur tatsächlich unterstützt

| Ansatz | Relevante Lehre |
|---|---|
| **DeepStack** | Gelernte handweise Fortsetzungswerte innerhalb von Re-Solving |
| **ReBeL** | Lernen auf öffentlichen Belief-Zuständen, verbunden mit Suche und Self-Play |
| **Student of Games** | Zusammenspiel von Suche, Wert-/Politiklernen und Selbstspiel |
| **Deep CFR** | Funktionsapproximation für Regrets innerhalb eines iterativen Regret-Minimierungsverfahrens |
| **DREAM / ESCHER** | Gelernte Werte beziehungsweise Advantages als Bestandteile geeigneter Regret-Schätzer und Trainingsverfahren |
| **Advantage-weighted Distillation** | Kann gute Aktionen stärker gewichten, liefert für sich aber keine Gleichgewichts- oder Mischgarantie |

Keiner dieser Ansätze rechtfertigt die Schlussfolgerung:

> „Einmal Q gegen einen Solver lernen, dann Softmax – damit erhalten wir eine robuste Pokerstrategie.“

---

# 3. Wie R3 stattdessen gebaut werden sollte

Es gibt drei seriöse Varianten.

## Variante A: Wertnetz plus kleine Suche

Das ist strategisch die sauberste Variante:

- Netz liefert Blattwerte oder Such-Warmstarts.
- CFR bestimmt die Verteilungen.
- Die ausgegebene Strategie ist die geeignete gemittelte Suchstrategie.

**Meine bevorzugte Lösung, wo das Budget reicht.**

## Variante B: gemeinsamer Policy-/Value-Student

Ein Netz erhält den vollständigen Informationszustand und lernt:

- CFVs oder Q-Werte;
- Aktions-Advantages;
- die vollständige Lehrerstrategie je Combo.

Ja, das enthält Policy-Distillation. Aber es ist etwas anderes als das von euch widerlegte Frequenz-Matching.

### Frequenz-Matching

\[
\sum_h w(h)\,\pi_\theta(\mathrm{bet}\mid s,h)
\approx
f_{\mathrm{GTOW}}(\mathrm{bet}\mid s).
\]

Das lässt offen, **welche Hände** betten.

### Informationszustandsabhängige Distillation

\[
\pi_\theta(a\mid s,h,r_1,r_2)
\approx
\pi_T(a\mid s,h,r_1,r_2).
\]

Hier wird gerade die Selektion gelernt.

Eure bisherigen Fehlschläge widerlegen nicht grundsätzlich Policy-Distillation. Sie widerlegen die konkret getesteten Daten-, Eingabe-, Lehrer- und Trainingskombinationen.

## Variante C: vollständiges neuralisiertes Regret-Learning

Deep-CFR-/DREAM-/ESCHER-artige Schleifen können sinnvoll sein, wenn ihr langfristig eine eigenständige schnelle Strategie lernen wollt.

Das ist aber ein anderes Projekt als „Q-Netz auf unseren River-Tensoren trainieren“:

- iterative Gegner- und Politikänderungen;
- passende Sampling-Schätzer;
- Regret- beziehungsweise Value-Memory;
- Strategie-Mittelung;
- explizite Kontrolle von Approximation und Distribution Shift.

Ich würde das nicht vor R1 beginnen.

---

## 3.1 Meine konkrete Loss-Empfehlung für einen schnellen Student

Seien:

- \(Q_T(s,h,a)\): Lehrer-Aktionswerte;
- \(\pi_T(s,h,a)\): zur Referenz passende Lehrerstrategie;
- \(\pi_\theta\): Student;
- \(\hat Q_\theta\): Q-Head.

Definiert:

\[
V_T(s,h)=\sum_a \pi_T(a\mid s,h)Q_T(s,h,a),
\]

\[
A_T(s,h,a)=Q_T(s,h,a)-V_T(s,h).
\]

Dann etwa:

\[
\mathcal L
=
\lambda_A\mathcal L_{\mathrm{adv}}
+
\lambda_\pi\mathcal L_{\mathrm{policy}}
+
\lambda_R\mathcal L_{\mathrm{regret}}
+
\lambda_V\mathcal L_{\mathrm{value}}.
\]

Mit:

\[
\mathcal L_{\mathrm{policy}}
=
\mathbb E_{s,h}
\left[
w_\pi(s,h)\,
D_{\mathrm{KL}}(\pi_T\Vert\pi_\theta)
\right],
\]

\[
\mathcal L_{\mathrm{regret}}
=
\mathbb E_{s,h}
\left[
w_R(s,h)
\sum_a\pi_\theta(a\mid s,h)
\left(\max_b Q_T(s,h,b)-Q_T(s,h,a)\right)
\right].
\]

Der Advantage-Loss vergleicht zentrierte Aktionswerte, beispielsweise mit Huber-Loss. Dadurch wird nicht ein großer gemeinsamer Pot-Offset zum dominierenden Lernsignal.

Die Rollen sind verschieden:

- **Regret-Loss:** keine Wahrscheinlichkeit auf klar schlechte Aktionen verschwenden.
- **Policy-Loss:** richtige Mischung in Indifferenzzonen lernen.
- **Advantage-Loss:** EV-Abstände und Selektion lernen.
- **Value-Loss:** absolute Fortsetzungswerte lernen, falls sie gebraucht werden.

Die \(\lambda\)-Werte sind Hyperparameter, keine theoretischen Konstanten.

### Wichtig: keine Lücke in Indifferenzzonen lassen

Ein reiner Regret-Loss hat bei indifferenten Aktionen keinen Gradienten zur richtigen Mischung. Genau dort ist der Policy- beziehungsweise strategische Robustheits-Term notwendig.

### Lehrerstrategie und Q müssen zusammenpassen

Speichert nicht:

- Q-Werte der letzten CFR-Iteration;
- zusammen mit einer anders gemittelten Strategie;
- unter einer dritten Range-Version.

Q-Werte sollten unter der gespeicherten Referenzfortsetzung nachgerechnet werden. Eure Indifferenzvalidierung ist dafür eine gute Grundlage, ersetzt aber diese Zuordnung nicht.

## 3.2 Kann man ohne Policy-Labels auskommen?

Ja – wenn man stattdessen die strategische Eigenschaft direkt optimiert.

Beispielsweise über einen Best-Response-Oracle im River-Spiel:

\[
\mathcal E_1(\pi_1)
=
v^\star-\min_{\sigma_2}u(\pi_1,\sigma_2).
\]

Dann wird nicht verlangt, eine bestimmte Nash-Mischung zu kopieren, sondern eine wenig exploitierbare Strategie zu erzeugen.

Das ist konzeptionell attraktiv, aber rechen- und optimierungstechnisch anspruchsvoller. Ein exakter BR-Prüfstand ist zunächst ein **Evaluator**, nicht automatisch ein stabiler differenzierbarer Trainingsalgorithmus.

**Meine Einschätzung:** Lehrerstrategie plus EV-Loss plus BR-Prüfung ist für euch der wesentlich kürzere Weg.

## 3.3 Reinheit und Mischung praktisch

- Bei einem robusten, deutlichen EV-Abstand kann die Politik nahezu rein sein.
- In Indifferenzzonen übernimmt sie eine kohärente Lehrer-/Suchmischung.
- Bei widersprüchlichen Referenzen oder hoher Modellunsicherheit wird gelöst.
- Keine globale Temperatur soll gleichzeitig all diese Fälle reparieren.

Softmax kann eine Parametrisierung des Policy-Heads sein. **Softmax direkt über vorhergesagte Q-Werte ist hier nicht die strategische Lösung.**

---

# 4. R1: Was genau das CFV-Netz lernen muss

## 4.1 CFV ist nicht einfach „EV meiner Hand“

Legt zuerst eure Konvention schriftlich fest.

Für einen öffentlichen Zustand \(s\), eigene Hand \(h\), gegnerische Hand \(k\), Rangegewichte \(r_{-i}(k)\) und Kompatibilitätsmaske \(M(h,k)\):

\[
v_i^{CF}(s,h)
=
\sum_k
r_{-i}(k)M(h,k)\,
u_i^{\pi_T}(s,h,k).
\]

Hier wird **nicht mit der eigenen Handwahrscheinlichkeit multipliziert**.

Die kompatible gegnerische Masse ist:

\[
c_i(h)=\sum_k r_{-i}(k)M(h,k).
\]

Falls euer Solver stattdessen bedingte Hand-EVs ausgibt:

\[
V_i^{cond}(s,h)
=
\frac{v_i^{CF}(s,h)}{c_i(h)}
\]

für \(c_i(h)>0\).

Diese Größen sind nicht austauschbar. Ein Netz kann bedingte Werte lernen und sie anschließend korrekt in CFVs umrechnen. Aber die Schnittstelle muss eindeutig sein.

**Vor einer Million Labels braucht ihr einen Roundtrip-Test:**

> Solverwert → gespeichertes Target → Netz-Schnittstellenkonvention → rekonstruierter CFR-Blattwert.

Ohne diesen Test droht ein sehr gut trainiertes Netz mit falscher Reach-Skalierung.

## 4.2 Nullsummenkonsistenz

Bei einer tatsächlich nullsummig definierten Auszahlungskonvention muss gelten:

\[
\sum_h r_1(h)v_1^{CF}(h)
+
\sum_k r_2(k)v_2^{CF}(k)
=0.
\]

Achtung: Manche EV-Konventionen behandeln den bereits im Pot liegenden Betrag als gemeinsamen zukünftigen Gewinn. Dann ist die Summe nicht null, sondern enthält eine bekannte Konstante. Das muss vor dem Training vereinheitlicht werden.

Eine entsprechende Konsistenzschicht oder ein Konsistenz-Loss ist sinnvoll. Sie ersetzt keine korrekten einzelnen Handwerte.

## 4.3 Eingaben

Ein guter erster Aufbau:

- zwei Rangevektoren mit je 1326 Einträgen;
- Board-Kodierung;
- Pot;
- effektive und gegebenenfalls beide Stacks;
- Position und handelnder Spieler;
- ausstehender Callbetrag;
- regelrelevante Raise-Information;
- Spiel-/Abstraktionskennung, falls mehrere Lehrerbäume verwendet werden.

Nicht alles davon muss am River-Street-Start variieren. Aber unterschiedliche legale Spiele dürfen nicht dieselbe Eingabe erhalten.

### Suit-Symmetrie

Entweder:

1. Board kanonisieren und **beide Rangevektoren sowie Outputs konsistent permutieren**, oder
2. eine geeignete symmetrieberücksichtigende Architektur verwenden.

Für den ersten belastbaren Prototyp würde ich Variante 1 plus Suit-Permutations-Tests nehmen.

Ein Fehler bei der Range-Permutation ist gefährlicher als ein zu kleines Netz.

## 4.4 Netzgröße

**Mein Startvorschlag, kein Literaturstandard:**

- zwei bis drei Hidden-Layer;
- Breite 512–1024;
- Residualverbindungen optional;
- Output: \(2\times1326\) Werte;
- insgesamt grob 3–8 Millionen Parameter, abhängig von Eingabekodierung und Tiefe.

Das ist auf 12 GB unproblematisch. Das Hauptproblem ist nicht die Gewichtsspeicherung, sondern:

- Zahl der Blattabfragen pro Entscheidung;
- Batching;
- CFR-Tensoren;
- Synchronisation;
- Abdeckung der Rangeverteilung.

Ein Transformer oder großes Karten-Foundation-Modell ist für diesen ersten Schritt nicht begründet.

---

# 5. Reicht eine Million River-Solves?

**Möglicherweise ja für einen eng definierten, relevanten Turn-Re-Solver. Nein als allgemeine Garantie für beliebige HUNL-Ranges und Aktionsbäume.**

Die Anzahl allein sagt wenig. Entscheidend sind:

- Vielfalt der öffentlichen Zustände;
- Vielfalt und Struktur der Ranges;
- Lehrerqualität;
- Suchverteilung;
- Abstraktion;
- erforderliche Fehlergrenze.

Eine Million fast ähnlicher Zustände kann weniger wert sein als eine wesentlich kleinere, gut konstruierte Sammlung.

## 5.1 Nicht nur gespielte River-Ranges sammeln

Der wichtigste zusätzliche Punkt:

> **R1 wird auf Ranges abgefragt, die während der CFR-Iterationen entstehen – nicht nur auf Ranges, die eure aktuelle Politik tatsächlich zum River spielt.**

Frühe Suchiterationen können sehr andere Blatt-Ranges erzeugen:

- stark konzentrierte;
- fast leere;
- ungewöhnlich blufflastige;
- außerhalb der bisherigen Policy-Verteilung.

Ein reines On-Policy-Trainingsset unterschätzt diesen Shift.

Loggt deshalb zusätzlich **Blattzustände aus echten Turn-Suchläufen**, einschließlich Zwischeniterationen.

## 5.2 Vorschlag für die Datenmischung

Folgende Mischung wäre mein Startpunkt, nicht ein literaturbelegtes Optimum:

| Anteil | Herkunft |
|---|---|
| 50 % | erreichbare Zustände aus verschiedenen Politiken und tatsächliche Suchblatt-Ranges |
| 25 % | strukturierte Perturbationen dieser Ranges |
| 15 % | breite synthetische Zustände, nach Board/SPR/Rangeform geschichtet |
| 10 % | adversariale beziehungsweise hochunsichere Zustände |

Strukturierte Perturbationen können umfassen:

- temperaturartige Konzentration/Abflachung;
- Value-/Bluff-Masse verschieben;
- Blockerfamilien gezielt verändern;
- Mischungen mehrerer erreichbarer Ranges;
- plausible alternative Aktions-Likelihoods.

Nicht ausreichend: unabhängige Zufallsgewichte über 1326 Combos ziehen und das „Abdeckung“ nennen.

Dabei müssen Board-Kompatibilität und nichtverschwindende gemeinsame Range-Masse erhalten bleiben.

## 5.3 Adversariale Datenerzeugung

Neue Lehrerlabels bevorzugt dort erzeugen, wo:

- mehrere Netze uneinig sind;
- die kleine und die große Referenz stark abweichen;
- Turn-Suche das Netz auffällig stark „ausnutzt“;
- eine Best Response neue schlechte Regionen erreicht;
- Blattfehler tatsächlich die Root-Strategie verändern.

Letzteres ist besonders wichtig. Nicht jeder große CFV-Fehler ist entscheidungsrelevant, und kleine Fehler können eine strategisch wichtige Mischung verschieben.

## 5.4 Datenmenge über Lernkurven entscheiden

Nicht eine Million vorab als notwendige Aufgabe festlegen.

Vergleicht mehrere Größenordnungen, beispielsweise:

\[
10^4,\quad 5\cdot10^4,\quad 2\cdot10^5,\quad 10^6.
\]

Für jede Stufe dieselben gehaltenen Prüfungen:

1. CFV-Fehler;
2. Tail-Fehler;
3. Turn-Root-Aktions-Regret gegenüber tiefer Referenz;
4. NashConv-/BR-Verschlechterung im Prüfspiel;
5. Verhalten auf nichttrainierten Rangefamilien.

Wenn sich nur MSE verbessert, aber Turn-Entscheidungen nicht, ist weitere Datenskalierung noch nicht begründet.

## 5.5 Datenvolumen und Inferenzrechnung

Aus eurer angenommenen Rate:

\[
10^6 / 10^4 = 100
\]

Stunden reine Datenerzeugung im genannten Durchsatzmodell. Das ist eine Budgetrechnung, keine Aussage über die benötigte Datenmenge.

Unkomprimierte FP32-Daten:

- CFVs beider Spieler: etwa **10,6 GB pro Million Roots**;
- beide Rangevektoren: weitere **10,6 GB**;
- fünf Q-Werte je Combo für beide Spieler: weitere **53 GB**, falls ihr diese tatsächlich vollständig speichert.

Dazu kommen Strategien, Metadaten und gegebenenfalls weitere Baumknoten. Ihr solltet nicht unbemerkt einen vollständigen Baum-Dump pro Root zum Standard machen.

### Live-Inferenz

Für ein dichtes Netz mit \(P\) Parametern, \(I\) Iterationen und \(L\) Blattabfragen pro Iteration näherungsweise:

\[
F \approx 2PIL
\]

Gleitkommaoperationen.

**Beispielannahme:**

\[
P=5\cdot10^6,\quad I=200,\quad L=256
\]

ergibt ungefähr:

\[
F=5{,}12\cdot10^{11},
\]

also rund **0,51 TFLOP reine Netzrechnung**.

Das ist grundsätzlich mit eurer GPU vereinbar. Es ist aber keine Latenzprognose: kleine Batches, 200 Synchronisationspunkte, Range-Aufbereitung und CFR können dominieren.

Deshalb:

- Ranges auf der GPU halten;
- Blätter gemeinsam inferieren;
- keine Python-Schleife je Combo;
- vorallozierte Tensoren;
- feste Shapes, wo möglich;
- gemischte Präzision nur validiert;
- Netz- und CFR-Zeit separat messen.

---

# 6. R2: Regret-Prädiktor oder Value-of-Computation-Modell?

## 6.1 Drei verschiedene Zielgrößen

Ihr müsst unterscheiden:

### A. Verfügbarer lokaler Regret

\[
R_{\mathrm{ref}}(s,\pi_0)
=
\max_a Q_{\mathrm{ref}}(s,a)
-
\sum_a\pi_0(a\mid s)Q_{\mathrm{ref}}(s,a).
\]

Das sagt: Unter dieser Referenz wäre lokal etwas zu holen.

### B. Tatsächlicher Nutzen einer Rechenoption \(m\)

\[
G_{\mathrm{ref}}(s,m)
=
\sum_a
\left[
\pi_m(a\mid s)-\pi_0(a\mid s)
\right]
Q_{\mathrm{ref}}(s,a).
\]

Das sagt: Diese konkrete Rechnung verändert die ausgegebene Politik um diesen Referenz-EV.

**\(G\) kann negativ sein. Nicht auf null abschneiden.**

### C. Robustheitsgewinn

Beispielsweise:

\[
G_{\mathrm{BR}}(s,m)
=
\mathcal E_s(\pi_0)-\mathcal E_s(\pi_m).
\]

Das sagt: Die zusätzliche Rechnung macht die Strategie im definierten Root-Spiel weniger exploitierbar.

Diese Größen können auseinanderlaufen. Insbesondere kann eine bessere Mischung \(G_{\mathrm{ref}}=0\), aber \(G_{\mathrm{BR}}>0\) haben.

**R2 sollte langfristig B vorhersagen und C als Sicherheits-/Zusatzsignal berücksichtigen. A allein reicht nicht.**

## 6.2 Rechenentscheidung

Für verschiedene Modi, etwa:

- kein Solve;
- kleiner Baum;
- größerer Baum;
- mehr Iterationen;
- weitere Rangehypothesen;

kann der Arbiter wählen:

\[
m^\star
=
\arg\max_m
\left[
\widehat{\mathbb E}[G(s,m)]
-
\lambda \widehat C(s,m)
\right]
\]

unter einer Deadline-Nebenbedingung.

\(\lambda\) ist der Schattenpreis eures Rechenbudgets, kein universeller Pokerparameter.

Für den ersten Arbiter reichen wenige Modi. Ein kontinuierlicher „intelligenter“ Scheduler ist unnötig.

## 6.3 Schwere Schwänze: welche Losses?

**Nur Klassifikation \(R>\tau\) reicht nicht.** Sie unterscheidet nicht zwischen einem seltenen 0,5-bb- und einem seltenen 50-bb-Fehler.

**Nur Quantilregression reicht ebenfalls nicht.** Ein hohes Quantil ist nicht der erwartete EV-Gewinn.

Mein Vorschlag:

- ein Head für den bedingten Erwartungswert des Rechengewinns;
- ein Head für relevante Überschreitungswahrscheinlichkeiten;
- einige Quantile als Risiko-/Unsicherheitssignal;
- gegebenenfalls ein separater Head für negative Solve-Effekte.

Bei nichtnegativem Regret kann ein Hurdle-Modell sinnvoll sein:

\[
\mathbb E[R\mid x]
=
P(R>\tau\mid x)\,
\mathbb E[R\mid R>\tau,x]
+
P(R\le\tau\mid x)\,
\mathbb E[R\mid R\le\tau,x].
\]

Für signierten Rechengewinn müssen auch negative Fälle modelliert werden.

### Vorsicht mit Log-Targets und Huber

- Ein Modell auf \(\log(1+R)\) schätzt nicht automatisch den arithmetischen EV-Erwartungswert.
- Huber kann das Training stabilisieren, aber gerade die seltenen großen Fehler heruntergewichten.
- Reines MSE zielt auf den Mittelwert, kann bei schweren Schwänzen jedoch schlecht trainierbar sein.

Deshalb große Fehler beim Sampling übergewichten, aber für die Zielverteilung korrekt gewichten. Die Tail-Auswertung separat berichten.

## 6.4 Selektions-Bias verhindern

Der Standardbaukasten aus Active Learning und Contextual-Bandit-Evaluation ist hier passend:

1. **Zufälliger Auditstrom mit strikt positiver Auswahlwahrscheinlichkeit.**
2. Zusätzliche Auswahl nach Unsicherheit, erwarteter Verbesserung und Diversität.
3. Auswahlwahrscheinlichkeit jedes gelabelten Zustands speichern.
4. Gehaltene Bewertung auf einem vom aktuellen Selektor unabhängigen Bestand.
5. Bei Bedarf Propensity-Gewichtung für die Zielverteilung.

**Mein Startvorschlag:** etwa 5–10 % der Label-Kapazität ausschließlich für einen zufälligen Auditstrom reservieren. Das ist eine Designannahme, kein bewiesener optimaler Anteil.

Bei Auswahlwahrscheinlichkeit \(e(s)\) kann eine Zielverteilungsbewertung beispielsweise Gewichte \(1/e(s)\) benötigen. Sehr kleine Wahrscheinlichkeiten erzeugen hohe Varianz; eine positive Untergrenze ist daher praktisch wichtig.

Uncertainty Sampling allein reicht nicht. Ein Netz kann gerade dort selbstsicher falsch sein, wo es nie Daten gesehen hat.

## 6.5 Der subtile Rückfall in eure Wrapper-Problematik

Wenn R2 anhand der tatsächlichen Hole Card entscheidet, ob gelöst wird, entsteht:

\[
\pi_{\mathrm{exec}}(a\mid s,h)
=
g(s,h)\pi_{\mathrm{solve}}(a\mid s,h)
+
[1-g(s,h)]\pi_{\mathrm{fast}}(a\mid s,h).
\]

Diese Hybridpolitik ist im Allgemeinen **nicht** die Strategie, deren Gleichgewicht der Solver berechnet hat.

Beispiel: Nur bestimmte Bluffkandidaten werden gelöst, Value-Hände bleiben in der schnellen Politik. Dann kann die kombinierte Raise-Range erneut falsch sein.

Deshalb zunächst:

- Rechenregime möglichst anhand öffentlicher Zustandsinformationen wählen;
- vollständige Range-Politik dieses Regimes evaluieren;
- bei handabhängigem Gating die Hybridpolitik explizit im BR-Prüfstand testen;
- Hero-Beliefs mit der wirklichen Gesamtpolitik aktualisieren.

**R2 darf nicht unbemerkt eine neue Generation inkohärenter Guards erzeugen.**

---

# 7. „Versäumte Gewinne“ formal sauber definieren

Die Umkehr ist als Diagnostik sinnvoll. Als neue ökonomische Zielfunktion ist sie weniger neu, als die Formulierung nahelegt.

Bei festem Zustand und fester Referenz ist

\[
\max_a Q(a)-Q(a_{\mathrm{gespielt}})
\]

einfach lokaler Opportunity Loss. Er umfasst sowohl:

- zu viel bezahlte Calls;
- verpasste profitable Bets;
- verpasste Raises;
- falsche Größen.

Die Kategorien „liegengelassen“ und „Fehler“ sind eine nützliche Fehler-Taxonomie. **Sie rechtfertigen keine unterschiedliche Gewichtung gleicher verlorener bb.**

## 7.1 Bevorzugte Definition

Für eine gemischte Politik:

\[
R_{\mathrm{ref}}(s,h;\pi)
=
\max_{a\in A(s)}Q_{\mathrm{ref}}(s,h,a)
-
\sum_{a\in A(s)}
\pi(a\mid s,h)Q_{\mathrm{ref}}(s,h,a).
\]

Das ist besser als nur die gesampelte Aktion auszuwerten:

- weniger Monte-Carlo-Rauschen;
- korrektes Feedback für Mixing;
- dieselbe Politik erhält nicht wegen eines Zufallsdraws ein anderes Urteil.

Eine aggregierte Kennzahl lautet:

\[
\mathcal R_D(\pi)
=
\mathbb E_{(s,h)\sim D}
[R_{\mathrm{ref}}(s,h;\pi)].
\]

In jedem Report gehören \(D\), Referenz, Größenbaum, Ranges und Fortsetzung ausdrücklich dazu.

## 7.2 Die fünf wesentlichen Fallen

### 1. Referenzabhängigkeit

Ein falscher Solver-Raise wird zu einem großen „verpassten Gewinn“. Das Netz lernt den Fehler zuverlässig.

Gegenmittel:

- unabhängiger Analyzer;
- dichtere Bäume;
- Konvergenzvarianten;
- plausible Rangevarianten;
- getrennte Lehrer- und Auditreferenzen.

### 2. Null Regret bedeutet nicht geringe Exploitability

Das Matrixbeispiel zeigt das bereits bei perfekter Referenz.

Deshalb immer mindestens zwei Achsen:

\[
\left(
\mathcal R_D(\pi),
\quad
\mathcal E_D(\pi)
\right).
\]

Eine skalare Zusammenmischung kann wichtige Regressionen verdecken.

### 3. Indifferenz und Solverrauschen

Wenn Q-Unterschiede kleiner als Lehrerunsicherheit sind:

- nicht den zufälligen Best-Arm als harte Wahrheit trainieren;
- EV-Abstände und Unsicherheit speichern;
- Mischung beziehungsweise BR-Verhalten prüfen.

Eine starre Indifferenzschwelle darf aber keine systematischen kleinen Fehler unsichtbar machen.

### 4. Zustandsverteilung ändert sich

Gewinne auf alten Zuständen sind kein vollständiger Politikgewinn.

Neue Raises erzeugen neue Antworten. Andere Turn-Bets verändern River-Ranges. Lokale Verbesserungen auf \(D_{\mathrm{alt}}\) sind nicht automatisch Verbesserungen auf \(D_{\mathrm{neu}}\).

### 5. Häufigkeit und Größenordnung

Die zentrale Größe ist:

\[
100
\times
\text{Zustandsbesuche pro Hand}
\times
\text{mittlerer Verlust pro Besuch}.
\]

Große Pots dürfen für Datenerzeugung übergewichtet werden. Der Ergebnisreport muss auf die Zielverteilung zurückgewichtet werden.

## 7.3 Kein Goodhart-Ziel: Drei getrennte Prüfungen

Ich würde „versäumte Gewinne“ nicht zum alleinigen Fitnesswert machen.

**A. Lokaler Referenz-Regret:**  
Findet und trainiert präzise Entscheidungsfehler.

**B. Strategische Robustheit im definierten Spiel:**  
Findet Misch-, Range- und Fortsetzungsfehler.

**C. Externe Leistung beziehungsweise unabhängiger Analyzer:**  
Prüft die Übertragbarkeit.

Ein Kandidat muss nicht jede Kennzahl strikt verbessern. Aber ein Gewinn in A bei deutlichem Schaden in B darf nicht als Fortschritt veröffentlicht werden.

---

# 8. Was „adaptive Intelligenz“ gegen GTOW sinnvoll bedeutet

Nicht ausschließlich R2. Es gibt mindestens vier sinnvolle adaptive Ebenen.

## 8.1 Zustandsabhängige Rechnung

Das ist R2:

- mehr Rechnung bei unsicherer, wichtiger Entscheidung;
- weniger bei robust klaren Aktionen;
- gezielte zusätzliche Range-/Baumvarianten.

## 8.2 Adaptive Aktionsabstraktion

Wenn der aktuelle Baum fragwürdig ist:

- zusätzliche Größe einfügen;
- Raise-Tiefe erweitern;
- tatsächliche gegnerische Größe exakt übernehmen;
- Baum gegen größere Referenz testen.

Dabei braucht ihr Gegenkontrollen: Ein kleines Netz kann eine Größe für unwichtig erklären, gerade weil sie nie ordentlich untersucht wurde.

## 8.3 Adaptive Beliefs

Es gibt einen wichtigen Unterschied:

- **Auf die beobachtete Aktionsfolge konditionieren** ist notwendige Pokerlogik.
- **Auf vermutete gegnerische Leaks exploiten** ist eine zusätzliche strategische Entscheidung.

Auch gegen Nash müsst ihr nach Check, Bet und Raise andere Ranges haben.

Darüber hinaus kann man Unsicherheit über die Gegnerstrategie modellieren, etwa durch mehrere plausible Aktions-Likelihood-Modelle. Daraus entstehen mehrere plausible Ranges.

Aber: Ein robustes Spiel gegen eine Menge von Rangehypothesen ist ein anderes Optimierungsproblem als ein Nash-Solve für eine bekannte Range. Mehr Konservatismus ist nicht kostenlos.

Meine Empfehlung gegen GTOW:

- Basis-Likelihood nahe an einer starken Referenz halten;
- beobachtete Aktionen korrekt konditionieren;
- Range-Ensemble als Unsicherheitsdiagnose nutzen;
- exploitative Verschiebungen nur bei unabhängig belegtem Nutzen aktivieren.

## 8.4 Adaptive Datenbeschaffung

Das System kann selbst erkennen:

- welche Boards;
- welche Rangeformen;
- welche Größen;
- welche Fortsetzungen

sein Modell noch schlecht beherrscht, und dafür zusätzliche Lehrerlabels erzeugen.

Das ist eine sehr reale Form adaptiver Kompetenz – ohne ein Gegner-Leak ausnutzen zu müssen.

**Gegen einen Re-Solver ist die produktivste Adaption wahrscheinlich die Adaption der eigenen Repräsentation, Suche und Datenbasis.** Nicht die laufende Jagd nach dessen vermeintlichen Frequenzfehlern.

---

# 9. Welche Netze ihr ausdrücklich nicht bauen solltet

## Nicht bauen

### 1. Den heutigen Advisor nur breiter machen

Ohne Ranges und strategische Zustandsinformation bleibt das Kernproblem bestehen.

### 2. Ein Q-Netz mit globalem Argmax oder Q-Softmax als „GTO-Policy“

Selbst perfekte Q-Werte reichen nicht für die korrekte Mischung.

### 3. Ein skalares Winrate-/Equity-Netz als CFR-Blatt

Ein einzelner Zustandswert enthält nicht die handweisen Counterfactual-Informationen, die der Re-Solver braucht.

### 4. Einen Regret-Klassifikator als einziges Rechenbudgetmodell

„Fehler wahrscheinlich“ ist nicht gleich „Rechnung lohnt sich“, und Wahrscheinlichkeiten allein ignorieren die Schadenshöhe.

### 5. Einen neuen großen End-to-End-Policy-Lerner ohne BR- und Referenzkontrolle

Damit würdet ihr eure alten Fehlschläge mit besserer GPU-Auslastung wiederholen.

### 6. Ein Netz auf normalisierten marginalen GTOW-Frequenzen

Das optimiert erneut die falsche Handselektion.

### 7. Einen Unsicherheits-Head, der sich selbst zertifiziert

Die Sicherheit eines Netzes lässt sich nicht allein daraus ableiten, dass ein zweiter Head desselben Netzes „sicher“ ausgibt.

### 8. Ein einziges Multitask-Monolith-Netz für R1, R2 und R3 zum Start

R1 braucht wertgenaue, rangeweite Outputs. R2 braucht billige Vorhersagen vor der Rechnung. R3 braucht kohärente Strategien. Gemeinsame Komponenten können später sinnvoll sein, aber zunächst würden sich Fehlerursachen und Trainingsziele unnötig vermischen.

---

# 10. Die Selbstverbesserungsschleife: richtig, aber mit wichtigen Ergänzungen

Eure vorgeschlagene Schleife ist ein guter Ausgangspunkt:

> spielen → loggen → lösen → Regret → lernen → neue Politik → prüfen.

In dieser Form ist sie aber anfällig für Selbstbestätigung.

## Die korrigierte Schleife

### 1. Versionierte Zustände sammeln

Loggen:

- vollständiger öffentlicher Zustand;
- beide Ranges;
- ausführbare Politik für alle relevanten Combos;
- Gating-Regel und Auswahlwahrscheinlichkeit;
- Solver-/Netz-/Konfigurationsversion;
- legaler Aktionsbaum;
- tatsächlich gespielte Aktion.

### 2. Mehrere Datenquellen mischen

Nicht nur eigene gespielte Hände:

- aktuelle Politik;
- eingefrorene ältere Politiken;
- starke Proxy-Gegner;
- Suchblatt-Zustände;
- BR-erzeugte Gegenbeispiele;
- zufälliger Auditstrom.

### 3. Lehrerlabels erzeugen

Speichern:

- CFVs;
- Q-Werte;
- vollständige geeignete Solverstrategie;
- Rest-Regret beziehungsweise Solverqualität;
- Range- und Baumvarianten bei kritischen Fällen.

**Speichert die Strategie mit, auch wenn ihr zunächst nur R1 trainiert.** Sie später nachzuerzeugen kostet unnötig Rechnung und kann wegen geänderter Solverversionen inkonsistent werden.

### 4. R1 und R2 getrennt trainieren

- R1 lernt Fortsetzungswerte.
- R2 lernt den Nutzen konkreter Rechenoptionen gegenüber einer klar versionierten schnellen Politik.

Wenn die schnelle Politik geändert wird, ändern sich R2-Labels. Vorhandene Referenz-Qs erlauben häufig eine billige Neuberechnung des lokalen Rechengewinns.

### 5. R3 nur als definierten Student oder Suchbestandteil trainieren

Nicht „Q rein, Softmax raus“.

### 6. Geschlossene Fortsetzungen prüfen

Ein Raise muss vollständig bis zum Terminal gespielt beziehungsweise bewertet werden. Eine gute Root-Aktion mit schlechter Antwort auf das Re-Raise ist kein guter Kandidat.

### 7. Exakte BR im definierten River-Spiel

Die gesamte Kandidatenpolitik prüfen, einschließlich:

- neuer Größen;
- Antwortstrategien;
- R2-Gating;
- Fallbacks;
- eigener Rangefortschreibung.

### 8. Unabhängigen Audit anwenden

- neue, gehaltene Zustände;
- unabhängiger Analyzer;
- andere Größenbäume;
- Range-Sensitivität;
- anschließend externe Spielprüfung.

## Wo die Schleife sonst bricht

| Bruchstelle | Folge |
|---|---|
| Nur selbst ausgewählte Zustände werden gelabelt | Blinde Flecken bleiben unsichtbar |
| Lehrer und Prüfer sind dieselbe Approximation | Gemeinsame Fehler wirken wie Fortschritt |
| Q-Regret ist alleinige Fitness | Mischungen können kollabieren |
| Neue Raises haben keine vollständige Fortsetzung | Kontrafaktischer Gewinn verschwindet live |
| Hero-Range basiert auf alter Politik | Das System trainiert auf seinem eigenen Belief-Fehler |
| R1 sieht nur gespielte Ranges | Suche findet und exploitiert OOD-Blätter |
| R2 trainiert gegen eine veraltete schnelle Politik | Rechenbudget wird falsch verteilt |
| Alle alten Prüfstände werden fortlaufend optimiert | Kein unabhängiger Nachweis bleibt übrig |

---

# Meine konkrete Architekturentscheidung

Ich würde für PokerB jetzt Folgendes festlegen:

1. **Die heutigen Advisors bleiben vorübergehend Fallback, werden aber nicht einfach vergrößert.**
2. **Erstes neues großes Lernartefakt: River-CFV-Netz für Turn-Suche.**
3. **R2 zunächst als kleines, auditierbares Value-of-Computation-Modell.**
4. **Q-Werte als Hilfsziel, Fehlerdiagnose und Suchinformation nutzen – nicht als alleinige Quelle der Mischstrategie.**
5. **Wenn eine schnelle neue Politik gebraucht wird: vollständigen range-konditionierten Policy-/Value-Student bauen, mit EV-Loss und BR-Gate.**
6. **Keine dogmatische Ablehnung von Policy-Distillation. Ablehnen solltet ihr marginales Frequenz-Matching und schlecht konditionierte Imitation.**

Die Leitidee sollte sein:

> **Selektion wird durch richtige Informationen und EV-Abstände gelernt. Mischung wird durch strategische Kopplung bestimmt. Rechnung wird durch ihren tatsächlichen Nutzen zugeteilt.**

Alle drei Aufgaben in „ein größeres Q-Netz“ zu komprimieren wäre der nächste naheliegende, aber grundlegende Architekturfehler.

### D2. Bewertung (Fable)

**Meine These R3 („Q-Netz, Politik daraus ableiten") ist WIDERLEGT, und zwar exakt.** Sein 2×2-
Gegenbeispiel ist korrekt: Im Gleichgewicht sind alle Aktionen im Support indifferent, ein perfekter
Q-Prädiktor liefert also identische Werte, aus denen die Mischung (40/60) nicht rekonstruierbar ist.
Softmax gibt 50/50, hat null lokalen Regret und verliert gegen Best Response 0,3 mehr als der
Spielwert. Übertragen: **null Regret gegen den Solver beweist keine niedrige Exploitability.** Das
trifft auch unsere Tiefen-Replay-Metrik: sie misst Regret-Achse A, nie Achse B (BR). Beide Achsen
gehören künftig in jeden Report, getrennt, nie als Skalar gemischt.

**Übernommen:**
1. **Reihenfolge R1 → R2 (klein) → R3 (nur bei Bedarf).** Erstes neues Lernartefakt = River-CFV-Netz,
   dessen einziger Erfolgsmaßstab ist, ob es Turn-Suche trägt (Turn-Root-Regret gegen tiefe Referenz
   sinkt). Nicht MSE.
2. **CFV-Konvention schriftlich + Roundtrip-Test vor dem ersten Label** (Solverwert → Target →
   Netz → rekonstruierter CFR-Blattwert; Nullsummen-Konsistenz; Suit-Permutation beider Range-
   Vektoren). Unser gpu_cfr hat invest0-Zentrierung (der frühere Turn-Utility-Bug) — genau die
   Konventionsfalle, die er meint.
3. **Trainings-Ranges = Such-Blatt-Ranges, nicht nur gespielte.** Das Netz wird in CFR-Iterationen auf
   Ranges abgefragt, die keine Politik je spielt. Logging der Zwischeniterations-Blätter aus echten
   TurnCFR-Läufen + strukturierte Perturbationen. Datenmenge über Lernkurven (10⁴/5·10⁴/2·10⁵/10⁶),
   nicht vorab „1 Million".
4. **R2-Ziel = Nutzen der Rechnung G(s,m) = Σ[π_m − π_0]·Q_ref, signiert, nicht Regret A.** Hurdle-
   Modell + Erwartungswert-Head + Überschreitungs-Head; 5–10 % zufälliger Audit-Strom mit
   gespeicherter Auswahlwahrscheinlichkeit gegen den Selektions-Bias. Erst als GBT/kleines MLP.
5. **Sein 6.5 trifft unsere Guard-Architektur ins Mark:** hand-abhängiges Gating (river_gpu_guard
   feuert je Hand auf p_basis/p_alt) erzeugt eine Hybrid-Politik π_exec = g·π_solve + (1−g)·π_fast,
   deren Raise-Range NICHT die des Solvers ist. Das ist derselbe Defekt wie die Hero-Range aus Teil C,
   von der anderen Seite. Konsequenz: Rechenregime nach ÖFFENTLICHEM Zustand wählen (Pot, Board,
   Linie), dann die volle Range-Politik dieses Regimes spielen; hand-abhängiges Gating nur mit BR-Test.
6. **Distillation nicht dogmatisch ablehnen.** Unsere Fehlschläge widerlegten Frequenz-Matching
   (marginal, ohne Range) und schlecht konditionierte Imitation — nicht informationszustandsabhängige
   Distillation π_θ(a|s,h,r₁,r₂) ≈ π_T. Sein Loss (Advantage-Huber + KL-Policy + Regret-Term +
   Value) ist der Bauplan, falls R3 je gebraucht wird.
7. **„Versäumte Gewinne" formal = lokaler Opportunity Loss der gemischten Politik**
   R(s,h;π) = max_a Q − Σ_a π(a)Q(a), erwartet über D; D, Referenz, Baum, Ranges im Report. Die
   Taxonomie liegengelassen/Fehler ist Diagnostik, rechtfertigt keine unterschiedliche Gewichtung
   gleicher bb. Kein Goodhart: drei Prüfungen (Regret A, BR-Exploitability B, Analyzer C).
8. **Nicht bauen:** Advisor nur breiter; Q-Softmax-Policy; skalares Equity-Netz als Blatt;
   Regret-Klassifikator als alleiniger Arbiter; End-to-End-Policy ohne BR-Kontrolle; Netz auf
   GTOW-Frequenzen; selbst-zertifizierender Unsicherheits-Head; Multitask-Monolith zum Start.

**Wo ich anders gewichte:** Sein Vorschlag, R3 zurückzustellen, setzt voraus, dass Live-Latenz durch
Suche gedeckt ist. Bei uns spielen die winzigen Advisors heute Flop und Turn LIVE; solange R1 die
Turn-Suche nicht trägt, bleiben sie der Produktpfad. Praktisch heißt das: R1 ist das Forschungs-
artefakt, aber der erste messbare Produkt-Hebel bleibt der River (Hero-Range-Fix + öffentliches
Gating + BR-Prüfstand), weil dort der Solver schon existiert.

**Antwort auf die User-Frage „Netze ausbauen?":** Ja, aber die richtige Formel lautet: **Werte lernen
(R1), Strategien durch Suche bestimmen, Rechnung nach Nutzen verteilen (R2).** Nicht: die
Advisors vergrößern, nicht: ein Q-Netz als Politik. Die GPU rechtfertigt den Ausbau, weil sie den
Lehrer (gelöste Spots mit vollständigen CFV/Q/Strategie-Tensoren) in Serie liefern kann — sie
ersetzt aber kein Trainings-Signal, das wir vorher nicht hatten.


---

## TEIL E — v10-Entwurf (Fable) und Kritik (gpt-6-astra, 9.751 Reasoning-Tokens, 662 s)

### E0. Der Entwurf (wörtlich gesendet)

# v10 — Build-Karte ENTWURF (Fable) zur Kritik

Der Product-Owner hat entschieden: der nächste Build heißt v10, wird in EINEM Rutsch von einer
Agenten-Flotte gebaut (parallel, disjunkte Dateien), durch die Gates geführt und dann gegen GTOW
getestet. Deine Zeitangaben ignorieren wir; deine Richtung ist angenommen. Kritisiere den Schnitt,
entscheide die vier offenen Fragen, und liefere am Ende DEINE Fassung der Build-Karte.

## Basis und Rahmen

- Basis: auslese-v5 = r8_stack = river_gpu_guard(river_wert_bremse(button_disziplin(turn_wert(sel_guard_flop m=0,15))))
  auf dem Live-Fundament PRINCE (exploit OFF, TURN_DEFENSE 0,07, SLOWPLAY 0,25), TexasSolver-River-
  Resolver ON (bot.py-intern; Nacht 1 ohne ihn = −38,9 → der Resolver ist ein Live-Träger, bleibt AN).
- Bekannte Defekte (heute verifiziert): (a) Hero-Range am River-Beginn kommt aus dem Tracker, der
  BEIDE Sitze mit demselben Advisor-Modell (P(bet)/P(call) je Combo, Solver-Frequenz-MLP) fortschreibt
  → für Hero ist das weder Basis noch Guard-Kette; die 2 %-Hero-Combo-Injektion kaschiert es.
  (b) river_gpu_guard gated HAND-abhängig (p_basis<0,10 & p_alt>0,70) → Hybrid-Politik.
  (c) HU-Web-App spielt PRINCE-los mit exploit ON (server.py:37). (d) gtowizard-Adapter ruft setze_env
  nicht. (e) Kein Konfig-Hash je Hand im HH-Log.
- Vorhanden: river_play_guard (v8) = ÖFFENTLICHES Gating (Straße=River, Pot ≥ min_pot), löst das
  Subgame mit eingefrorenen River-Beginn-Ranges, sampelt Heros Aktion deterministisch (crc32 über
  Lage) aus der Solver-Mischung, Sizes exakt aus dem Baum-Arm, Legalitätsgatter. Im Spiegel NEUTRAL
  (+2,3±2,4 gepoolt), im Replay auf GTOW-Händen +278,6 bb kontrafaktisch.
- GPU-CFR liefert: RiverCFRBatch.solve/exploitability/_br/_ev/action_values; Bäume mit
  bet_sizes (0,35/0,75/1,5 Pot), raise 2,7×, max 2 Raises, Jam. Einzel-Solve-Latenz: gemessen als
  Durchsatz 0,3 s/Spot bei B=256; Live-Einzelabfrage ~1–3 s (fp32, 150 Iter) — wird im Smoke gemessen.
- Bot-Entscheidung live: decide() ~83 ms je Aufruf (memoisiert); 1326 Combos × decide = ~110 s → die
  exakte Range-Politik der Kette ist LIVE nicht rechenbar, OFFLINE (12 Worker) schon.
- GTOW-Harness: in-process, ~10 s Zeitbudget je Entscheidung (Timeout-Klasse), Chunks à 500 Hände,
  ~2–2,5 h je Chunk, Nacht = 4 Chunks, HH mit AIVAT je Hand, clear_inprogress vor jedem Start,
  503-Stürme/Deadlocks kommen vor (Chunk-Verlust). Kein v5-Anker vorhanden.

## Komponenten des Entwurfs

**K1 Hero-Range aus der ausgeführten Politik (Guard-konsistent).** Neues Modul
`pokerbot/strategy/hero_range.py`: startet mit der Tracker-Hero-Range am River-Beginn und wendet je
Hero-Aktion vor dem River die Konsistenz-Filter der Guards an, die im Stack aktiv sind:
- button_disziplin: Hero=Button, Preflop-Open 2,5× beobachtet → Hero-Preflop-Range = ALLE Combos
  (die Guard-Regel öffnet 100 %), nicht die Tracker-Klassenliste.
- turn_wert (check→2/3-Pot-Bet bei Trips+/Two-Pair/Überpaar mit Hole-Beteiligung UND eq≥0,60 vs
  Villain-Tracker-Range): Hero hat am Turn ohne Einsatz vor sich GEBETTET → Combos mit Guard-Bedingung
  bekommen Gewicht 1 (sie betten sicher); Hero hat GECHECKT → diese Combos bekommen Gewicht 0.
  Equity je Combo vs Range vektorisiert auf der GPU (gpu_equity, ms).
- sel_guard Flop (fold→call, wenn eq vs Villain-Range ≥ Pot-Odds + 0,15): Hero hat am Flop einen
  Einsatz GECALLT → Combos mit Guard-Bedingung: Gewicht = 1 (Näherung: Raise-Anteil ignoriert);
  Hero hat GEFOLDET → Hand zu Ende, irrelevant.
- wert_bremse/GPU-Guard wirken erst AM River → betreffen die River-Beginn-Range nicht.
Näherungscharakter dokumentiert. Messgröße: INJEKTIONSRATE (Anteil River-Spots, in denen Heros reale
Combo unter 2 % Masse liegt) auf den Nacht-2-Spots vorher/nachher; Ziel deutlich ↓. Dazu offline die
EXAKTE Range-Politik (decide je Combo, 12 Worker) auf einer Stichprobe als Wahrheit für den Filter.
FRAGE 1: Reicht der Filter-Ansatz für v10, oder muss K1 die exakte Range-Politik live approximieren
(z. B. Cache je Board-Klasse)? Welche Fehler des Filter-Ansatzes würdest du erwarten?

**K2 Öffentliches Gating am River = r10_stack.** Der hand-abhängige river_gpu_guard wird ERSETZT durch
river_play_guard (öffentlich: Pot ≥ P_min) MIT K1-Hero-Range; darunter bleibt wert_bremse + Basis.
Stack: r10_stack = river_play_guard[K1](river_wert_bremse(button_disziplin(turn_wert(sel_guard)))).
Mixing bleibt (deterministische Hash-Stichprobe aus der Solver-Mischung). fp32, 150 Iter.
FRAGE 2: P_min = 15 bb (v9-Vorgate: erschließt 15 Neu-Spots je 970 Hände, Latenz-Smoke 0,88 s/Deck
mit fp16) oder 20/30 bb (Latenz-Sicherheit im 10-s-Budget)? fp16 bleibt draußen (getrennt validieren).

**K3 BR-Prüfstand (Instrument, kein Bot-Code).** `research/river_br_pruefstand.py`: für eine Menge
River-Root-Zustände (Nacht-2-HH + Tiefen-Replay-Trackliste; Split Entwicklung/Holdout nach Hand-ID,
Holdout unangetastet) baut er OFFLINE Heros exakte Range-Politik an jedem Hero-Knoten des River-Baums
(decide je Combo, Kandidat und Incumbent) und rechnet: (i) exakte Villain-Best-Response gegen diese
Politik, (ii) Exploitability relativ zum Solver-Wert des Root-Spiels, (iii) lokalen Referenz-Regret
R(s,h;π)=max_a Q − Σ π(a)Q(a) gemittelt über D, getrennt ausgewiesen, nie als Skalar gemischt.
Kontrollen: A/A (identische Politik → identisch), positiv (Solver-Durchschnittsstrategie → niedrig),
negativ (argmax-purifizierte Solver-Strategie → höher). Nenner: je Hand, nicht je River-Spot.

**K4 Kanal-Hygiene.** server.py: PRINCE + exploit OFF + FINAL_STACK; gtowizard.py: setze_env(resolver_on=
True) vor bot-Import; HH-Log: Konfig-Hash (Stack-Name, Env-Flags, Git-HEAD, iters) je Hand;
Injektionsrate + Solve-Latenz je River-Entscheidung als Felder.

**K5 GTOW-Nachtfahrplan v10.** `research/gtow_nacht_v10.py`: Arme A = v5 (PRINCE + r8_stack, resolver ON)
und B = v10 (PRINCE + r10_stack, resolver ON), Chunks à 500, HH + Manifest, clear_inprogress, Retry.
FRAGE 3: Blockdesign bei 4 Chunks/Nacht ohne CRN-Paarung: A B B A? A B A B? 2 Nächte (ABAB, BABA)?
Was ist bei SE ~±10 je 500er-Chunk überhaupt aussagefähig, und wie formulieren wir die Vorregistrierung
ehrlich (Ziel: „v10 nicht schlechter als v5 + Absolut-Stand beider" statt „v10 gewinnt signifikant")?

**Gates vor GTOW (Reihenfolge):** (G1) Unit-Tests + A/A r10_stack vs r10_stack 600 Decks EXAKT 0;
(G2) Latenz-Smoke je River-Entscheidung p50/p99 (Budget < 8 s) + 40-Deck-Divergenz-Smoke;
(G3) K3-Prüfstand: Kontrollen bestehen; v10 auf Holdout: Exploitability ≤ v5 UND Regret ≤ v5;
(G4) Tiefen-Replay Holdout (Achse A) v10 vs v5.
FRAGE 4: Spiegel 15k vs r8_stack (4 h, SE ~4) als Katastrophen-Test VOR GTOW, oder danach, oder gar
nicht für v10? Ship-Kriterium des Spiegels wäre nur Nichtverschlechterung (CI-Untergrenze > −5).

**Ausgeschlossen aus v10 (bewusst):** CFV-Netz (R1, eigener Forschungs-Track), Turn-Re-Solving,
Entropie-Anker, stackoff/no_limp, fp16, GPU-ersetzt-TexasSolver (Arm B2 später), Advisor-Umbau.

## Was ich von dir will

1. Kritik am Schnitt: Was ist falsch, was fehlt, was gehört raus? Insbesondere: ist K1 als Filter
   sauber genug, um K2 darauf zu bauen, oder erzeugt der Filter neue Inkonsistenz (z. B. Turn-Bet-Größen
   ≠ 2/3 durch Engine-Clamp; Villain-Range-Abhängigkeit der eq-Bedingung; sel_guard-Raise-Anteil)?
2. Entscheide die vier Fragen mit Begründung.
3. Für jede Komponente: der konkrete Abnahmetest (Zahl, Schwelle, Kontrolle), der sie abschließt.
4. Die Reihenfolge der Agenten-Arbeitspakete für einen Bau in einem Rutsch (welche Pakete parallel,
   welche sequentiell, welche Datei-Grenzen, welche Schnittstelle zwischen K1 und K2/K3 zuerst
   festgezogen werden muss).
5. Risiken, die den GTOW-Test entwerten würden, und wie wir sie vorher abfangen.
6. Deine finale Build-Karte v10 in kompakter Form (Komponenten, Gates, GTOW-Design, Vorregistrierung).

Deutsch, konkret, ohne Zeitpläne.


### E1. Die Kritik (wörtlich, ungekürzt)

# Entscheidung

**Der Schnitt ist grundsätzlich richtig, aber der Entwurf ist in seiner jetzigen Form nicht freigabefähig.** Drei Punkte sind keine Detailkorrekturen, sondern Voraussetzungen:

1. **K1 ist derzeit kein konsistentes Range-Update.** Der Filter überschreibt beziehungsweise multipliziert bereits verarbeitete Evidenz falsch und setzt Aktionswahrscheinlichkeiten zu häufig auf 1.
2. **K2 braucht eine vollständige Ausführungssemantik:** richtige Ranges am Einstieg, kohärente Fortsetzung, eindeutige Priorität gegenüber dem internen TexasSolver und echte private Randomisierung.
3. **K3 muss die tatsächlich ausgeführte gemischte Politik prüfen, nicht einmal gesampelte Aktionen oder eine projizierte Idealversion.** Außerdem müssen beide Arme im selben Root-Spiel bewertet werden.

Die vier Entscheidungen vorweg:

| Frage | Entscheidung |
|---|---|
| **1. K1-Filter ausreichend?** | **Nicht in der vorgelegten Form.** Korrektes Likelihood-Replay ab Prior; Guard-Transformationen exakt, verbleibende Approximation gegen Offline-Oracle prüfen. Kein Board-Klassen-Cache als Ersatz. |
| **2. \(P_{\min}\)?** | **15 bb**, sofern der vollständige FP32-Latenztest besteht. Pot-Schwellen sind keine Deadline-Garantie. Kein automatisches Hochsetzen nach Ergebnisansicht. |
| **3. GTOW-Design?** | **Zwei Nächte, ABBA und BAAB; Reihenfolge vorab zufällig bestimmen.** Explorative Vergleichsmessung und Absolut-Anker, kein eingeplanter Nichtunterlegenheitsnachweis. |
| **4. 15k-Spiegel?** | **Kein verpflichtender 15k-Lauf für v10, weder davor noch danach.** Stattdessen kurzer geschlossener Integrationstest vor GTOW. Die vorgeschlagene CI-Regel ist kein billiger Katastrophentest. |

Alle nachfolgend vorgeschlagenen Schwellen sind **Engineering-Abnahmekriterien**, keine aus euren bisherigen Daten abgeleiteten Naturkonstanten.

---

# 1. K1: Der Filter muss zu einem Likelihood-Replay werden

## 1.1 Warum der aktuelle Ansatz mathematisch nicht stimmt

Für eine beobachtete eigene Aktion \(a_t\) gilt:

\[
r_{t+1}(h)
\propto
r_t(h)\,
\pi_{\mathrm{exec}}(a_t\mid s_t,h).
\]

Über die gesamte Vorgeschichte:

\[
r_{\mathrm{River}}(h)
\propto
r_{\mathrm{initial}}(h)\,
M_{\mathrm{Board}}(h)
\prod_{t\in\text{Hero-Aktionen}}
\pi_{\mathrm{exec}}(a_t\mid s_t,h).
\]

Die Ausgangsrange am River aus dem Tracker enthält bereits dessen Aktions-Likelihoods. Wenn ihr darauf neue Filter legt, entfernt ihr die alten falschen Likelihoods nicht.

Eine nachträgliche Korrektur wäre nur als Verhältnis sauber:

\[
r_{\mathrm{neu}}(h)
\propto
r_{\mathrm{Tracker}}(h)
\prod_t
\frac{\pi_{\mathrm{exec}}(a_t\mid s_t,h)}
     {\pi_{\mathrm{Tracker}}(a_t\mid s_t,h)}.
\]

Das funktioniert nur, wenn:

- sämtliche alten Faktoren bekannt sind;
- sie zum gleichen damaligen Zustand gehören;
- kein benötigter Support bereits auf null gesetzt wurde.

**Deshalb für v10: vom Prior beziehungsweise korrekten Preflop-Ausgangspunkt vorwärts rekonstruieren. Nicht die fertige Tracker-Range mit zusätzlichen 0/1-Filtern „reparieren“.**

## 1.2 Die Guard-Transformationen lassen sich exakt formulieren

Die allgemeine Form lautet:

\[
\pi_{\mathrm{exec}}(a\mid s,h)
=
\sum_{a_0}
\pi_{\mathrm{vorher}}(a_0\mid s,h)\,
\mathbf 1\!\left[T(s,h,a_0)=a\right].
\]

Dabei umfasst \(T\) die gesamte relevante Transformation einschließlich:

- Guard;
- Größenberechnung;
- Chip-Rundung;
- Clamp;
- Legalitätsreparatur;
- Zusammenführung identischer finaler Aktionen.

Bei stochastischen Guards wird über deren interne Verzweigungen zusätzlich summiert.

### `turn_wert`

Wenn der Guard ausschließlich Check in eine bestimmte Bet \(b^\star\) umwandelt:

\[
\pi_{\mathrm{exec}}(b^\star\mid h)
=
\pi_{\mathrm{vorher}}(b^\star\mid h)
+
\mathbf 1_{C(h)}
\pi_{\mathrm{vorher}}(\mathrm{check}\mid h),
\]

\[
\pi_{\mathrm{exec}}(\mathrm{check}\mid h)
=
[1-\mathbf 1_{C(h)}]
\pi_{\mathrm{vorher}}(\mathrm{check}\mid h).
\]

**Eine beobachtete Bet macht die Wahrscheinlichkeit nicht automatisch zu 1.**

Andere Betgrößen der vorherigen Politik bleiben andere Aktionen – außer die Engine bildet sie auf denselben finalen Chipbetrag ab.

### `sel_guard`

Für Fold → Call:

\[
\pi_{\mathrm{exec}}(\mathrm{call}\mid h)
=
\pi_{\mathrm{vorher}}(\mathrm{call}\mid h)
+
\mathbf 1_{C(h)}
\pi_{\mathrm{vorher}}(\mathrm{fold}\mid h).
\]

Der Raise-Anteil bleibt erhalten.

Euer Ansatz „bei erfüllter Bedingung Call-Gewicht 1“ überschätzt genau die Hände, die noch häufig raisen. Das kann am River Value- und Bluff-Massen systematisch verschieben.

### `button_disziplin`

Wenn der tatsächlich ausgeführte Guard **jede** Combo auf dieselbe finale Open-Größe zwingt, liefert diese Aktion keine Handselektion:

\[
\pi_{\mathrm{exec}}(\mathrm{open}\ 2{,}5\times\mid h)=1.
\]

Das bedeutet: **Prior an dieser Stelle unverändert lassen.**

Es bedeutet nicht: am Ende die gesamte Range auf „alle Combos“ zurücksetzen und spätere Evidenz überschreiben.

## 1.3 Die damalige Villain-Range ist Teil des Zustands

Für den Turn-Guard muss die Bedingung mit der Range berechnet werden, die der Bot **vor der damaligen Turn-Aktion** verwendet hat.

Nicht mit:

- der River-Range;
- einer nach der Turn-Bet aktualisierten Range;
- einer rückblickend besseren Range;
- einem Snapshot, der bereits die tatsächliche Hero-Hand aus der öffentlichen Gegenrange entfernt hat.

Für jede hypothetische Hero-Combo muss Card Removal korrekt neu erfolgen.

Sonst bewertet ihr nicht die damalige Politik, sondern eine Politik mit anderer oder sogar zukünftiger Information.

## 1.4 Live muss nicht 1326-mal `decide()` laufen

Ihr braucht eine schmale neue Schnittstelle:

```python
action_likelihoods(snapshot, policy_id) -> [combo, canonical_action]
```

Sie berechnet Verteilungen, ohne:

- zu sampeln;
- Tracker zu mutieren;
- eine Hand weiterzuspielen;
- globale RNG-Zustände zu verändern.

Die vorhandenen Advisor-MLPs lassen sich grundsätzlich gebatcht auswerten. Die Guards werden anschließend als Transformationen dieser Verteilungen angewendet.

Das ist **kein Advisor-Umbau im strategischen Sinn**: gleiche Modelle und Regeln, andere Auswertungsschnittstelle.

Wo die tatsächliche Basisverteilung nicht kurzfristig batchfähig ist, darf ein approximierter Backend hinein – aber nur mit expliziter Kennzeichnung und Oracle-Abnahme.

**Ein Cache nach Board-Klasse reicht nicht.** Die Likelihood hängt außerdem von Ranges, Position, Pot, Stacks, Aktionsfolge und aktiver Konfiguration ab.

## 1.5 Die Injektionsrate ist als Hauptziel ungeeignet

Wenn ihr wörtlich meint:

> „Die tatsächliche Combo hat weniger als 2 % normalisierte Range-Masse“,

dann ist das kein Fehlerindikator.

Bei einer gleichmäßigen Range über 200 Combos hat jede Combo 0,5 %. Bei 800 Combos 0,125 %. Eine gute breite Range würde euren Test fast immer „verfehlen“.

**Ziel darf nicht sein, die tatsächliche Hand auffällig wahrscheinlich zu machen.**

Noch wichtiger: Eine öffentliche Hero-Range darf nicht abhängig davon verändert werden, welche tatsächliche Hero-Combo gerade vorliegt. Sonst löst ihr für verschiedene private Hände unterschiedliche vermeintliche öffentliche Spiele.

Für K1 stattdessen messen:

- Abstand zur Offline-Oracle-Range;
- Support-Verletzungen;
- Likelihood der tatsächlich ausgeführten Aktion;
- nachgelagerten Strategie-/BR-Schaden;
- Häufigkeit ungültiger Range-Rekonstruktionen.

Die alte Injektionsrate nur als Legacy-Diagnostik behalten.

### K1-Abnahme

**Harte Tests:**

- Wahrscheinlichkeiten endlich, nichtnegativ, Summe je Verteilung innerhalb \(10^{-6}\).
- Ungültige Board-Combos exakt null.
- Guard-Transformation gegen explizite Enumeration: maximale Wahrscheinlichkeitsabweichung \(10^{-6}\).
- Gleiche öffentliche Historie mit verschiedener tatsächlicher Hero-Hand ergibt dieselbe öffentliche Hero-Range, bis auf \(10^{-6}\) numerische Toleranz.
- Keine tatsächliche-Hand-Injektion im K1/K2-Pfad.
- Größenvergleich über finale ganzzahlige Chipbeträge, nicht über Labels wie „2/3 Pot“.

**Oracle-Stichprobe:**

- mindestens 128 Aktionszustände;
- jede Guard- und Clamp-Klasse mindestens 16-mal, nötigenfalls synthetische Fixtures;
- zusätzlich mindestens 64 vollständige gehaltene Vorgeschichten.

Für einen ausdrücklich approximierten Likelihood-Backend schlage ich vor:

- mittlere Total-Variation-Distanz der finalen Hero-Range \(\le 0{,}02\);
- 95. Perzentil \(\le 0{,}05\);
- kein Fall \(>0{,}10\);
- zusätzlicher gewichteter BR-Verlust gegenüber Oracle-Ranges höchstens **0,5 bb/100** auf dem definierten Prüfbestand.

Diese Grenzen sind ein Fehlerbudget, keine Sicherheitsgarantie. Verfehlt K1 sie, ist K2 darauf **nicht freigegeben**.

---

# 2. K2: Öffentliches Gating ist notwendig, aber noch keine kohärente Strategie

## 2.1 Entscheidung: \(P_{\min}=15\) bb

Ich würde 15 bb registrieren.

Begründung:

- Ihr wollt gerade kleine, bislang ungeerntete River-EV-Korrekturen erschließen.
- Die genannten 15 zusätzlichen Spots pro 970 Hände sprechen nicht für eine gewaltige zusätzliche Live-Last.
- Der bisherige fp16-Smoke sagt allerdings nichts Verlässliches über den neuen FP32-End-to-End-Pfad.
- Größere Pots sind nicht automatisch schneller zu lösen.
- Eine höhere Pot-Schwelle beseitigt keine einzelne zu langsame Entscheidung.

**Latenz wird durch Deadline-Steuerung abgesichert, nicht durch Hoffnung auf seltenere Solves.**

Wenn 15 bb das Latenz-Gate verfehlt, wird nicht nach Betrachtung der EV-Ergebnisse auf 20 oder 30 optimiert. Dann muss entweder die Implementierung korrigiert oder eine neue, ausdrücklich registrierte Konfiguration geprüft werden.

## 2.2 „Eingefrorene River-Beginn-Ranges“ sind nur unter einer Bedingung korrekt

Zulässig:

1. Ein Root-Spiel wird mit den Ranges dieses Roots gelöst.
2. Die vollständige Strategie wird gespeichert.
3. Weitere Aktionen folgen den passenden Knoten dieses Plans.

Nicht zulässig:

1. An jedem späteren River-Knoten ein neues lokales Spiel aufsetzen.
2. Dabei immer wieder die unveränderten River-Beginn-Ranges einspeisen.

Dann ignoriert ihr die inzwischen beobachteten Bets, Calls und Raises.

### Erforderlicher Vertrag

K2 braucht einen `RiverPlan`:

- Root-Zustand und Root-Ranges;
- Tree- und Konfigurations-Hash;
- vollständige gemittelte Strategie;
- Zuordnung aktueller Historie → Baumknoten;
- definierte Off-Tree-Behandlung;
- klarer Fallback-Status.

Wenn die öffentliche Schwelle erst nach einer gegnerischen Bet erreicht wird, müssen die Einstiegsranges bereits auf diese Aktion konditioniert sein.

**Einmal aktivierter Plan bleibt für diese Fortsetzung aktiv.** Keine unprotokollierte Rückkehr zwischen Solver und Basis.

Bei einer Off-Tree-Aktion:

- Ranges korrekt fortschreiben;
- entweder ausdrücklich neu lösen;
- oder den definierten Fallback verwenden.

Kein stilles Neulösen mit alten Ranges.

## 2.3 CRC32 über die Lage ist allein keine Mischstrategie

Wenn die Aktion vollständig aus einem bekannten deterministischen Hash des Informationszustands folgt, ist die Politik an diesem Informationszustand rein.

Dass über viele verschiedene Hände ungefähr die gewünschte Frequenz entsteht, ist nicht dasselbe wie korrektes Mixing.

Für v10:

- private, unabhängige Randomisierung;
- reproduzierbar über einen aufgezeichneten privaten Seed;
- pro Hand/Entscheidung eine stabile RNG-Adresse;
- Policy-Abfragen für K1/K3 verbrauchen keine Zufallszahlen.

Ein geeignetes Schema ist ein privater Hand-Seed plus keyed Hash über die Entscheidungsadresse. CRC32 allein ist keine geeignete Quelle privater Randomisierung.

**K3 bekommt die Verteilung vor dem Sampling**, nicht die aus einem Seed erzeugte einzelne Aktion.

Für A/A verwenden beide Arme dieselben Testseeds. Live werden die Seeds nicht dem Gegner offengelegt.

## 2.4 TexasSolver bleibt an – aber die Priorität muss sichtbar sein

Ich würde die Resolver-Abschaltung nicht in v10 hineinziehen.

Aber es muss eine Trace-Kette geben:

```text
Basisvorschlag
→ interner TexasSolver-Eingriff
→ verbleibende Guards
→ K2-Planentscheidung
→ Legalitätsabbildung
→ Sampling
→ finale Aktion
```

Jede Änderung nach der K2-Entscheidung muss entweder:

- semantisch identische Legalitätsabbildung sein;
- oder ausdrücklich Teil der geprüften Gesamtpolitik.

Wenn der interne Resolver nachträglich die Solveraktion wieder überschreibt, prüft K3 sonst die falsche Strategie.

Auch die Laufzeit beider Resolver gehört ins End-to-End-Budget. Keine stillschweigende Architekturänderung unter der Bezeichnung „Optimierung“.

### K2-Abnahme

- K2-Aktivierung unabhängig von der tatsächlichen Hole Card.
- Finale Größen exakt aus dem Plan, nach dokumentierter Chip-Abbildung.
- Verteilungen je Knoten innerhalb \(10^{-6}\) normalisiert.
- Vorgegebene Check–Bet–Raise–Call- und Off-Tree-Historien laufen ohne Range-Reset durch.
- Keine Sample-Aktion wird als Policy-Verteilung ausgegeben.
- Sampling-Test über 10.000 private Seeds je Testverteilung: Abweichung je Arm höchstens \(5\) Binomial-Standardfehler plus Rundungstoleranz.
- Testverteilungen mit Wahrscheinlichkeit 0 oder 1 werden exakt eingehalten.

**Latenz:**

- mindestens 500 vollständige Entscheidungsaufrufe über geschichtete Zustände;
- darunter beide Positionen, Schwellenfälle, Raises, Jams, kalte und warme Caches;
- p99 der gesamten Entscheidung \(<8\) s;
- kein regulärer Testaufruf \(\ge9\) s;
- vorbereiteter Fallback und technische Deadline vor dem Harness-Timeout;
- künstlich verzögerter GPU-Job darf die Hand nicht blockieren oder später ein veraltetes Ergebnis einspielen.

---

# 3. K3: Den Prüfstand enger spezifizieren, nicht größer behaupten

## 3.1 Beide Arme müssen im selben Root-Spiel spielen

Wenn ihr v5 mit seiner Tracker-Range und v10 mit seiner korrigierten Range jeweils gegen einen eigenen Spielwert bewertet, vergleicht ihr verschiedene Spiele.

Für einen Root \(s\) braucht ihr eine gemeinsame Evaluationsverteilung:

\[
\rho_s(h,k).
\]

Für Hero vorzugsweise aus dem Offline-Oracle der tatsächlich ausgeführten Vorgeschichte. Die Vorgeschichte vor dem River ist für A und B strategisch gleich, sofern K4 dort nichts verändert.

Dann:

- v5 erhält intern die Beliefs, die v5 tatsächlich verwenden würde;
- v10 erhält intern K1-Beliefs;
- beide werden extern unter derselben \(\rho_s\) bewertet.

So wird der Schaden falscher interner Beliefs sichtbar, statt durch einen Wechsel des Bewertungsmaßstabs zu verschwinden.

Villain-Ranges bleiben eine Referenzannahme. Mindestens eine plausible alternative Rangefamilie gehört deshalb in die Sensitivitätsprüfung.

## 3.2 Einseitiger Sicherheitsverlust ist nicht vollständige Exploitability

Für die Hero-Politik:

\[
w(\pi_H)=\min_{\sigma_V}u(\pi_H,\sigma_V).
\]

Mit dem Spielwert \(v^\star\):

\[
E_H(\pi_H)=v^\star-w(\pi_H).
\]

Das ist der **einseitige Sicherheitsverlust der Hero-Politik im definierten Root-Spiel**.

Wenn ihr beide Spielerpolitiken bewertet, könnt ihr zusätzlich NashConv berichten.

Da der Solverwert approximiert ist, sollte K3 eine Spielwert-Klammer ausgeben:

\[
L\le v^\star\le U.
\]

Für den gepaarten Vergleich ist das angenehm:

\[
E_H(\pi_B)-E_H(\pi_A)
=
w(\pi_A)-w(\pi_B).
\]

Der unbekannte gemeinsame Spielwert fällt heraus.

**Der gepaarte BR-Unterschied kann also exakt sein, obwohl die absolute Verlustzahl nur in einem Intervall bekannt ist.**

## 3.3 `decide()` je Combo ist nur dann ein Oracle, wenn es die Verteilung liefert

Ein Aufruf je Combo, der eine gesampelte Aktion liefert, ergibt eine purifizierte Politik.

Erforderlich ist:

```python
policy_distribution(
    snapshot,
    hero_combo,
    policy_version
) -> probabilities_over_final_actions
```

Dabei müssen:

- Zustand und private Historie korrekt rekonstruiert werden;
- Caches alle relevanten Inputs enthalten;
- Tracker und RNG unverändert bleiben;
- spätere Fortsetzungen dieselben sein wie live.

„Memoisiert“ ist hier kein Qualitätsmerkmal. Ein Cache, dessen Key die hypothetische Hero-Hand oder Range-Version nicht enthält, macht die Oracle-Stichprobe wertlos.

## 3.4 Der Baum muss unter den Kandidatenaktionen geschlossen sein

Die genannten Größen 0,35/0,75/1,5 Pot, 2,7× Raise, zwei Raises und Jam sind ein endliches Prüfspiel.

Es ist nur dann eine exakte BR gegen die tatsächliche Politik in diesem Spiel, wenn deren Aktionen darin repräsentiert sind.

Problemfälle:

- Basis bettet 1/3 statt 0,35 Pot;
- TexasSolver liefert zusätzliche Größen;
- Clamps erzeugen andere Chipbeträge;
- v5 raiset in einer Tiefe, die der Prüfbaum abschneidet.

Deshalb:

- finale Größen beider Arme in den Evaluationsbaum aufnehmen;
- keine stille Nearest-Size-Translation;
- keine still erzwungene Call/Fold-Fortsetzung;
- nicht unterstützte Roots ausdrücklich als `UNSUPPORTED` markieren.

Für den freigegebenen Prüfbestand fordere ich **Off-Tree-Masse null**. Wenn das nicht erreichbar ist, müsst ihr den Anspruch ändern: „exakte BR gegen projizierte Politiken im eingeschränkten Spiel“ ist ein anderer Test.

## 3.5 Die negative Kontrolle ist nicht allgemein gültig

„Argmax-Purify muss schlechter sein“ stimmt nicht für jeden Root. Manche Gleichgewichte sind rein, manche Änderungen betreffen nur indifferente und ungefährliche Bereiche.

Verwendet zusätzlich einen analytischen Mischungs-Test, beispielsweise Matching Pennies:

- Gleichgewichtsmischung: Sicherheitsverlust 0;
- reine Strategie: Sicherheitsverlust 1 in den gewählten Auszahlungseinheiten.

Außerdem eine kleine Karten-Fixture mit verborgenen Händen, deren BR durch unabhängige Enumeration berechnet wird.

Sie muss verhindern, dass `_br` versehentlich für jede gegnerische Hole Card getrennt maximiert und damit zum Oracle-Gegner mit Sicht auf Heros Karten wird.

## 3.6 Der genaue Wrapper-Oracle ist nicht automatisch billig

Mit euren Zahlen ergibt bereits

\[
200\ \text{Roots}
\times10\ \text{Hero-Knoten}
\times2\ \text{Arme}
\times1326
\times0{,}083\ \text{s}
/12
\]

ungefähr **10,2 Stunden idealisierte CPU-Wandzeit**, ohne zusätzliche GPU-Konkurrenz. Das ist eine Rechnung aus euren Angaben, kein Benchmark.

Deshalb:

- K2-Strategien direkt als vollständige Combo-Matrizen exportieren;
- identische vollständige Solver-Inputs wiederverwenden;
- Oracle-Extraktion cachen und versionieren;
- den teuren v5-Oracle nicht für jedes neue Auswerteskript neu erzeugen.

Ein vollständiger Plan ist hier nicht nur strategisch sauberer, sondern spart erhebliche Prüfkosten.

## 3.7 Holdout und Nenner

Ein nachträglich nach Hand-ID gesplitteter Bestand ist nicht unangetastet, wenn diese Hände bereits für v8, Trigger oder K1-Diagnosen verwendet wurden.

Falls kein echter unbenutzter Bestand existiert:

- gesonderten v5-Kalibrierungsbestand erheben;
- daraus Holdout einfrieren;
- diesen nicht nachträglich als unbeeinflussten A/B-Vergleich verkaufen.

Für BR-Auswertungen:

- genau ein vollständiger River-Root pro Quellhand;
- nicht mehrere verschachtelte Sicherheitsverluste derselben Hand addieren;
- Root-Besuchswahrscheinlichkeit beziehungsweise Auswahlgewichte berücksichtigen.

„Durch Anzahl aller Hände teilen“ reicht nur, wenn die Auswahl aus diesen Händen vollständig oder korrekt gewichtet ist.

### K3-Abnahme

**Instrument:**

- A/A-BR-Differenz numerisch 0, Toleranz \(10^{-6}\) bb;
- analytischer Mischungs-Test innerhalb \(10^{-6}\);
- kleine Karten-Fixture gegen unabhängige Enumeration innerhalb \(10^{-6}\) bb;
- keine private Kartenleckage;
- keine nicht ausgewiesene Aktionsprojektion;
- gemeinsame Evaluationsranges für beide Arme.

**Referenzqualität:**

- gemittelte Solverstrategie, nicht letzte Iteration;
- Spielwert-Klammer berichten;
- für lokale Q-Regret-Urteile adaptiv genauer lösen, statt 150 Iterationen als Wahrheit festzuschreiben.

**Kandidaten-Gate auf gehaltenen Daten:**

Definiert „Verlustdifferenz“ als B minus A; negativ ist besser.

Mein Vorschlag:

- einseitige 95%-Obergrenze für \(\Delta E_H\) höchstens **+0,5 bb/100**;
- einseitige 95%-Obergrenze für \(\Delta R\) höchstens **+0,5 bb/100**;
- mindestens eine der beiden Obergrenzen liegt unter 0;
- Tail-Fälle separat ausweisen und gegen dichteren Baum prüfen.

Das erlaubt ein kleines vorab definiertes Fehlerbudget, statt beide verrauschten Kennzahlen strikt monoton zu verlangen. Die beiden Konfidenzintervalle bleiben getrennt; das ist kein globales Sicherheitszertifikat.

---

# 4. K4: Kanal-Hygiene muss für beide Arme identisch sein

K4 ist zwingend. Aber dadurch entsteht ein wichtiger Namenspunkt:

**Arm A ist die eingefrorene v5-Strategie auf einem geprüften, einheitlichen Produktionskanal.** Nicht automatisch dieselbe ausführbare Konfiguration wie irgendeine frühere Nacht.

Nennt ihn im Manifest beispielsweise `v5-H`, falls die Kanalreparatur sein bisheriges Verhalten verändert.

## 4.1 Frischer Prozess je Chunk

`setze_env()` vor `bot`-Import ist fragil, wenn irgendein transitiver Import `bot` bereits geladen hat.

Für v10:

- dünner Launcher ohne vorzeitigen Pokerbot-Import;
- unveränderliche Konfiguration vor Initialisierung;
- **frischer Prozess je Chunk und Arm**;
- keine Umschaltung globaler Env-Flags in einem bereits importierten Bot;
- eigener Memo-/Tracker-Zustand je Prozess.

Das ist unter Windows mit Spawn besonders wichtig.

## 4.2 Hash reicht nur mit aufgelöster Konfiguration

In den Fingerprint gehören mindestens:

- Source-Artefakt beziehungsweise Dirty-Tree-Status;
- Modell- und Chart-Hashes;
- PRINCE;
- Exploit-Flag;
- vollständiger Stack;
- Deception-Parameter;
- TexasSolver-Status und Version;
- GPU-Solver-Version;
- Größenbaum, Raise-Tiefe, Iterationen, Präzision;
- \(P_{\min}\);
- K1-Version;
- Sampling- und Fallback-Modus.

Nicht nur die gewünschte Konfiguration loggen. Beim Start muss geprüft werden, was **tatsächlich geladen** wurde.

PokerStars-HH nicht durch proprietäre Felder unlesbar machen. Metadaten gegebenenfalls in eine JSONL-Sidecar mit eindeutiger Hand-ID.

## 4.3 Dauerhaftes Hand-Ledger statt Chunk-Verlust

Nach jeder abgeschlossenen Hand persistieren:

- Hand-ID;
- Arm und Artefakt-Hash;
- Ergebnis/AIVAT;
- technische Ereignisse;
- Abschlussstatus.

`clear_inprogress` darf erst nach Abgleich offener Hände aufgerufen werden.

Bei einem unbekannten Ausgang:

- nicht blind dieselbe Aktion erneut senden;
- nicht null EV imputieren;
- nicht die ganze bisherige 500er-Datei verwerfen;
- Fall als unbekannt markieren und rekonstruieren, soweit API-seitig möglich.

### K4-Abnahme

- 100 % der Smoke-Hände tragen gültigen Konfigurations-Fingerprint.
- Bewusste Fehlkonfiguration bei PRINCE, Exploit oder Resolver führt zum Startabbruch.
- A und B laufen nachweislich in frischen Prozessen.
- Prozessabbruch nach einer abgeschlossenen Hand verliert deren Datensatz nicht.
- Wiederanlauf erzeugt keine doppelt gezählte Hand-ID.
- Fault-Injection für 503, verspätete Antwort und Prozessabbruch besteht.
- Die strategische v5-Verteilung bleibt auf einem eingefrorenen Golden-Set unverändert, soweit K4 nur Kanalhygiene beansprucht.

---

# 5. GTOW: ABBA/BAAB, aber keine versprochene Nichtunterlegenheit

## 5.1 Design

Ich würde vorab eine Münze ziehen:

- entweder Nacht 1: **ABBA**, Nacht 2: **BAAB**;
- oder umgekehrt.

Damit sind über beide Nächte:

- beide Arme in jeder Chunk-Position vertreten;
- beide Reihenfolgen AB und BA vertreten;
- lineare nächtliche Trends teilweise abgefangen.

Benachbarte Chunks bilden die vorgesehenen Vergleichspaare. Das ist **randomisiertes Blockdesign ohne CRN**, keine Hand-für-Hand-Paarung.

Keine Reihenfolgenänderung aufgrund von Zwischenergebnissen.

## 5.2 Was die Messung leisten kann

Falls die genannten ±10 tatsächlich **Standardfehler je 500er-Chunk** sind:

Bei vier Chunks je Arm:

\[
SE_A \approx SE_B \approx \frac{10}{\sqrt4}=5.
\]

Unter vereinfachter Unabhängigkeitsannahme:

\[
SE_{B-A}\approx\sqrt{5^2+5^2}=7{,}1\ \text{bb/100}.
\]

Die einseitige 95%-Untergrenze wäre näherungsweise:

\[
\widehat\Delta - 1{,}645\cdot7{,}1
\approx
\widehat\Delta-11{,}6.
\]

Bei beobachtetem Gleichstand könnt ihr also **nicht** zeigen, dass v10 höchstens 5 bb/100 schlechter ist.

Die Rechnung ist sogar optimistisch, wenn zwischen Chunks Abhängigkeiten oder zusätzliche Nacht-Effekte bestehen. Vier Blockpaare rechtfertigen keinen naiven, hochpräzisen Cluster-Bootstrap.

## 5.3 Ehrliche Vorregistrierung

**Primäres Ziel:**

> Aktuellen AIVAT-Stand beider eingefrorener Arme schätzen und große Regressionen beziehungsweise große Verbesserungen erkennen.

**Primärer Vergleich:**

\[
\Delta=\mu_{\mathrm{v10}}-\mu_{\mathrm{v5-H}}.
\]

**Sekundär:**

- einseitige Nichtunterlegenheitsprüfung mit Marge \(-5\) bb/100;
- Erfolg nur, falls die vorregistrierte Untergrenze tatsächlich über \(-5\) liegt;
- andernfalls lautet das Ergebnis **„Nichtunterlegenheit nicht nachgewiesen“**, nicht „gleich gut“.

**Produktentscheidung und statistischer Beweis trennen:**

Ihr könnt v10 aufgrund starker Offline-Gates und unauffälligem Live-Pilot provisorisch einsetzen. Ihr dürft daraus keinen bewiesenen Live-Gewinn oder bewiesene Nichtunterlegenheit machen.

## 5.4 Technische Ausfälle vorregistrieren

Getrennt zählen:

1. Server-/Transportfehler;
2. Bot-Deadline-Verletzungen;
3. illegale Aktionen;
4. unbekannte Handabschlüsse;
5. erfolgreiche Fallbacks.

Mein Vorschlag:

- illegale Bot-Aktion: sofortiger Stopp des Kandidaten;
- wiederholte Bot-Deadline-Verletzung: Stopp;
- unbekannte Ausgänge über 0,5 % je Arm oder über 0,5 Prozentpunkte Armdifferenz: kein unqualifiziertes Leistungsverdikt, technische Untersuchung.

Das sind bewusst strenge Engineering-Grenzen. Fehlende Ergebnisse können gerade bei großen Pots selektiv sein und den AIVAT-Anker verzerren.

---

# 6. Spiegel: die vorgeschlagene Regel ist zu teuer für ihre Funktion

Bei einem Spiegel-SE von 4 bb/100 und beobachtetem Gleichstand liegt die einseitige 95%-Untergrenze bei:

\[
0-1{,}645\cdot4=-6{,}6.
\]

Die Regel

> CI-Untergrenze \(>-5\)

würde also selbst bei beobachtetem Gleichstand nicht bestehen.

Das ist ein Nichtunterlegenheitstest mit begrenzter Power, kein bloßer Katastrophentest.

**Meine Entscheidung: kein verpflichtender 15k-Spiegel für v10.**

Stattdessen vor GTOW:

- etwa 2000 gepaarte vollständige Decks;
- A/A separat;
- technische Integrität;
- tatsächlich erreichte K2-Fortsetzungen;
- auffällige Stack-off-/Raise-Katastrophen;
- Diagnose ungewöhnlicher Ergebnisverschiebungen.

Keine Pflicht, auf diesem Kanal einen positiven Effekt zu zeigen.

Ein klar negativer Befund muss untersucht werden. Ein breites Intervall um null ist kein Veto gegen einen Kandidaten, dessen Zielkompetenz der Spiegel bekanntermaßen schwach bewertet.

---

# 7. Änderungen an den Gates

Ich würde eure Gate-Reihenfolge so ändern:

## G0 — Vertrag, Artefakt und Datenstatus

Vor strategischen Tests:

- Konfiguration eingefroren;
- Policy-/Range-/Plan-Schnittstellen fest;
- echte Holdout-Herkunft dokumentiert;
- beide Arme reproduzierbar startbar.

## G1 — Mathematische und technische Invarianten

- K1-Transformationen;
- Range-Support;
- Größen-/Legalitätsabbildung;
- private Randomisierung;
- BR-Oracle-Kontrollen;
- Fault-Injection.

## G2 — Geschlossene Ausführung und Latenz

- 40-Deck-Divergenz-Smoke;
- zusätzliche erzwungene Fixtures, damit alle wesentlichen K2-Zweige tatsächlich erreicht werden;
- vollständiger 500-Entscheidungs-Latenztest;
- A/A über 600 gepaarte Decks, exakt 0 bei identischen Testseeds und deterministischer Testausführung.

A/A soll zwei getrennte Instanzen vergleichen, nicht zweimal denselben gecachten Ergebnisvektor.

## G3 — K1-Oracle-Abnahme

Vor BR-Interpretation müssen die Range-Eingaben glaubwürdig sein.

## G4 — Gemeinsamer River-Prüfstand

- gemeinsames Root-Spiel;
- exakte beziehungsweise klar abgegrenzte BR;
- lokaler Regret;
- Range-/Baum-Sensitivität;
- gehaltene Daten.

Euer bisheriges G4-Tiefen-Replay ist bei derselben Referenz keine zweite unabhängige Evidenz. Es wird eine Auswertung innerhalb dieses Gates, nicht ein zusätzlicher „Beweis“.

## G5 — Analyzer-Audit und kurzer geschlossener Spiegel

Analyzer-first heißt auch hier:

- kritische neue Raises und Sizes unabhängig prüfen;
- Originalhände und verfügbare unabhängige Aktions-EVs verwenden;
- eigene Solver-EVs nicht als Analyzer-Bestätigung ausgeben.

## G6 — GTOW-Pilot

Nur unverändertes Release-Artefakt aus den vorangegangenen Gates.

---

# 8. Agenten-Flotte: Dateitrennung reicht nicht, zuerst die Verträge

Parallelbau ist möglich. **Parallel unterschiedliche Annahmen implementieren und am Ende Dateien zusammenwerfen ist es nicht.**

## 8.1 Zuerst festzuziehende Schnittstellen

Ein verantwortlicher Integrator besitzt beispielsweise:

`pokerbot/strategy/contracts.py`

Mit mindestens:

### `PolicySnapshot`

- vollständiger öffentlicher Zustand;
- kanonische Aktionshistorie;
- öffentliche Range-Snapshots;
- regelrelevante Größen in Chips;
- Policy-/Konfigurations-ID;
- Zustand vor der jeweiligen Aktion.

### `ActionKey`

```text
fold | check | call | raise_to(chips)
```

Semantisch gleiche finale Aktionen werden zusammengeführt. „Bet 0,75 Pot“ ist kein hinreichender Aktionsschlüssel.

### `RangeState`

- beide Rangevektoren;
- Boardmasken;
- Herkunft und Konvention;
- Rekonstruktionsstatus;
- Versions-/Zustandshash.

### `PolicyTable`

- `[combo, action]`;
- legale Aktionen;
- keine Samples;
- keine Nebenwirkungen.

### `RiverPlan`

- Root;
- Ranges;
- Baum;
- gemittelte Strategien;
- aktueller Knoten;
- Off-Tree-/Fallback-Regel;
- Deadline-/Qualitätsstatus.

**Diese Verträge werden vor dem Parallelbau eingefroren.**

## 8.2 Parallelisierbare Pakete

| Paket | Besitz |
|---|---|
| **P1 Hero-Likelihood/Reconstruction** | `hero_range.py`, eigene Tests |
| **P2 River-Plan und Sampling** | `river_play_guard.py`, Sampling-Helfer, eigene Tests |
| **P3 Oracle und BR-Prüfstand** | `research/policy_oracle.py`, `river_br_pruefstand.py`, eigene Fixtures |
| **P4 Runtime/Logging-Hygiene** | Runtime-Konfigmodul, `server.py`, `gtowizard.py`, HH-Sidecar |
| **P5 Nacht-Orchestrierung** | `gtow_nacht_v10.py`, Manifest-/Retry-Tests gegen Mock-API |
| **Integrator** | `bot.py`, Stack-Registry, gemeinsame Verträge, finale Verdrahtung |

Niemand außer dem Integrator ändert gleichzeitig `bot.py` oder die Stack-Registry.

P3 kann mit analytischen und synthetischen Politiken beginnen, während P1/P2 gebaut werden. P5 kann gegen eine Mock-API arbeiten. P4 muss vor realen End-to-End-Tests integriert sein.

## 8.3 Sequentielle Abhängigkeiten

```text
Verträge
 ├─ P1
 ├─ P2
 ├─ P3-Instrument
 ├─ P4
 └─ P5-Mock
        ↓
Integration durch einen Besitzer
        ↓
K1-Oracle + K2-Fortsetzungsprüfung
        ↓
K3-Kandidatenprüfung
        ↓
Artefakt einfrieren
        ↓
GTOW
```

Nach dem Holdout-Verdikt keine „kleine“ Strategiekorrektur mehr im gleichen Release. Jede relevante Änderung bekommt einen neuen Artefakt-Hash und wiederholt die betroffenen Gates.

---

# 9. Risiken, die den GTOW-Test entwerten würden

Die wichtigsten sind:

1. **Arm A ist nicht die behauptete v5-Konfiguration.**  
   Gegenmittel: tatsächliche Runtime-Konfiguration prüfen, gegebenenfalls `v5-H` benennen.

2. **Globale Env-/Importzustände laufen zwischen Armen weiter.**  
   Gegenmittel: frischer Prozess je Chunk.

3. **Hero-Range enthält Wissen um die tatsächliche Hand.**  
   Gegenmittel: öffentliche-Hand-Invarianztest, keine 2%-Injektion im neuen Pfad.

4. **K3 prüft Verteilungen, live wird deterministisch purifiziert.**  
   Gegenmittel: private Randomisierung und getrennte Policy-/Sampling-Schnittstelle.

5. **Live löst jeder River-Knoten mit alten Root-Ranges neu.**  
   Gegenmittel: gespeicherter Plan und definierte Off-Tree-Behandlung.

6. **TexasSolver oder Legalitätslogik überschreibt K2 unbemerkt.**  
   Gegenmittel: vollständige Entscheidungstraces und Prüfung der finalen Politik.

7. **Nur erfolgreich abgeschlossene Chunks werden ausgewertet.**  
   Gegenmittel: persistentes Hand-Ledger, unbekannte Ausgänge und Abbrüche ausdrücklich berichten.

8. **Ein bereits optimierter Replay-Bestand wird zum Holdout erklärt.**  
   Gegenmittel: tatsächliche Provenienz statt nachträglichem Zufallssplit.

9. **Jeder Arm wird gegen seine eigene günstige Referenzrange bewertet.**  
   Gegenmittel: gemeinsames Evaluationsspiel.

10. **Off-Tree-Aktionen werden still auf günstige Größen projiziert.**  
    Gegenmittel: Aktionsabschluss prüfen, Unsupported-Fälle nicht verstecken.

11. **Ein breit unentschiedener Live-Pilot wird als Nichtunterlegenheit getauft.**  
    Gegenmittel: statistische Aussage vorab festschreiben.

---

# Finale Build-Karte v10

## Ziel

**Kohärenteres River-Spiel durch korrigierte Hero-Beliefs und öffentlichen Solver-Einstieg.**  
Kein CFV-Netz, kein Turn-Solving, kein Entropieprojekt, kein fp16, kein Resolver-Austausch.

## Arme

- **A:** eingefrorene v5-Strategie auf geprüftem identischem Kanal, PRINCE und TexasSolver ON, Exploit OFF.
- **B:** gleiche Basis; handabhängiger äußerer GPU-Guard ersetzt durch K2; K1 für den neuen Solverpfad.
- Gemeinsame Hygieneänderungen explizit dokumentieren.
- Keine weiteren strategischen Änderungen.

## Komponenten

### K1 — Hero-Likelihood-Replay

- Rekonstruktion ab Prior/korrektem Preflop-Ausgangspunkt.
- Guard-Transformationen über finale Aktionswahrscheinlichkeiten.
- Damalige Range- und Zustandssnapshots.
- Keine tatsächliche-Hand-Injektion.
- Approximation nur mit Offline-Oracle-Abnahme.

### K2 — Öffentlicher River-Plan

- Einstieg bei **Pot ≥15 bb**, eindeutig definierte Pot-Konvention.
- FP32, zunächst 150 Iterationen für Live.
- Gemittelte Solverstrategie.
- Gespeicherter Plan statt unkontrollierter lokaler Re-Solves.
- Private, reproduzierbare Randomisierung.
- Exakte finale Chipgrößen.
- Deadline und vorbereiteter Fallback.
- TexasSolver bleibt ON; Priorität und Laufzeit vollständig protokolliert.

### K3 — River-Prüfstand

- Ein gemeinsames Root-Spiel je Quellhand.
- Beide Arme mit ihren echten internen Beliefs und Fortsetzungen.
- Exakte Villain-BR im ausdrücklich definierten, geschlossenen Spiel.
- Einseitiger Sicherheitsverlust und lokaler Regret getrennt.
- Analytische Mischungs- und Karten-Kontrollen.
- Echter Holdout; Range-/Baum-Sensitivität.
- Kein stilles Size-Mapping.

### K4 — Produktionsintegrität

- Unveränderliche Runtime-Konfiguration.
- Frischer Prozess je Chunk.
- Vollständiger Artefakt-/Modell-/Konfigurations-Fingerprint.
- Persistentes Hand-Ledger und JSONL-Telemetrie.
- Fault-Injection für Timeout, 503 und Wiederanlauf.

### K5 — GTOW-Pilot

- Zwei Nächte.
- Sequenzen **ABBA / BAAB**, Reihenfolge vorab zufällig.
- 500 abgeschlossene Hände je geplantem Chunk; offene/fehlende Ausgänge separat.
- Keine ergebnisabhängige Reihenfolgen- oder Versionsänderung.

## Gates

1. Verträge, Datenprovenienz und Artefakt.
2. Invarianten, Sampling, BR-Kontrollen, Fault-Injection.
3. A/A 600 Decks exakt 0; Divergenz-/Fortsetzungs-Smoke.
4. End-to-End-Latenz: p99 <8 s, kein regulärer Testaufruf ≥9 s.
5. K1-Oracle-Abnahme.
6. Holdout: gepaarte BR- und Regret-Kriterien mit registriertem Fehlerbudget.
7. Unabhängiger Analyzer-Audit und kurzer geschlossener Spiegel.
8. GTOW mit unverändertem Artefakt.

## Vorregistrierte Aussage

> Der Live-Test schätzt den aktuellen AIVAT-Stand beider Arme und deren Differenz. Er ist primär explorativ und auf große Effekte beziehungsweise Regressionen ausgerichtet. Nichtunterlegenheit mit Marge −5 bb/100 wird nur behauptet, wenn die vorregistrierte Konfidenzgrenze sie tatsächlich trägt. Ein unentschiedenes Ergebnis wird nicht als Gleichwertigkeit bezeichnet.

**So würde ich v10 bauen lassen. Der entscheidende Unterschied zum Entwurf: Nicht „bessere Filter plus mehr Solver“, sondern eine überprüfbare Kette von öffentlicher Historie über Aktions-Likelihoods und Beliefs bis zur tatsächlich ausgeführten vollständigen Strategie.**

### E2. Reconciliation (Fable) → docs/V10_BUILD_CARD.md

Übernommen: K1 als Likelihood-Replay ab Prior mit exakten Guard-Transformationen (Massenverschiebung
statt 0/1-Filter; damalige Villain-Range; keine Hand-Injektion; Invarianztest; Oracle-Abnahme mit TV-
Budget) · K2 mit gespeichertem RiverPlan, privater Randomisierung (keyed hash statt crc32 über Lage),
Trace-Kette, Deadline 7,5 s, P_min 15 bb · K3 gemeinsames Root-Spiel, gepaartes ΔE_H (Spielwert fällt
heraus), analytische und Karten-Kontrollen, echter Holdout (Nacht-1) · K4 Fingerprint/Ledger/Fresh-
Process · K5 ABBA/BAAB per Münze (Ergebnis: BAAB dann ABBA, data/runs/v10_muenze.json) · Spiegel nur
2000 Decks · Vorregistrierung ohne Nichtunterlegenheits-Versprechen.
Abweichungen (begründet in der Karte): Advisor-Backend für Basis-Likelihood (bot.py exponiert keine
Mischverteilung) · Gating am River-BEGINN (pot_river) statt bei Heros Entscheidung · A-Oracle mit ≥4
Seeds als Schätzung.


---

## TEIL F — Vollständigkeitsfrage nach den Gates (2026-09-08; Kontext-Hinweis: dieser Aufruf hing an Astras ERSTER Antwort, nicht an Teil D/E — das Briefing war selbsttragend)

### F0. Frage (wörtlich)

# Frage: Ist v10 vollständig? Gate-Ergebnisse und offene Lücken

v10 wurde gebaut (K1–K5, Verträge, 8 Testdateien grün) und durch die Gates geführt. Hier die Messlage
mit Quellen; danach die Frage.

## Was bestanden hat
- **A/A** r10_stack vs r10_stack: 576 gepaarte Decks EXAKT 0, dreimal (drei Banken), auch nach zwei
  Code-Änderungen. Golden-Set r8_stack vs basis byte-identisch vor/nach hand_id-Injektion.
- **Bug gefunden durch den 576-Deck-A/A:** hand_id war je Spiegelhälfte verschieden → private Seeds
  verschieden → A/A −9,4 ± 10,9. Fix: hand_id = Deck-Adresse für beide Hälften. 40 Decks hätten das nie
  gezeigt (≈1 Plan-Deck).
- **G5 Spiegel** r10 vs r8 (v5), 1968 Decks, Gym-Kanal: +11,68 ± 10,85 bb/100, CI [−9,4; +33,1],
  114 Divergenz-Decks (5,8 %), 66 positiv. Katastrophen ≥150 bb: 1 negativ, 1 positiv.
- **G4 Prüfstand** (11 Holdout-Roots, Arm A = v5 im Gym-Kanal, Arm B = Plan, gemeinsames Root-Spiel,
  exakte BR): ΔE_H = w(A)−w(B) = −10,1 ± 1,7 bb/Root, alle 11 Roots negativ (Plan weniger ausbeutbar);
  ΔR: R(A) 0,52 vs R(B) 0,16 bb/Root, Plan in 11/11 besser; Sensitivität mit Villain-Preflop-Nullhypothese
  gleiches Vorzeichen. Aber: n=11 von 224 (voller Holdout 33 h), und Arm A ist v5-GYM ohne TexasSolver.

## Was verfehlt wurde
- **G3 K1-Oracle:** TV(K1, decide()-Oracle über 64 Vorgeschichten, 145 Knoten, S=12) mittel 0,209,
  p95 0,76, max 0,88; Oracle-Rauschboden 0,095 → untere Schranke 0,145. Budget war 0,02/0,05/0,10.
  Vergleich: Tracker-Parität (die Range, die v5 nutzt) TV 0,259; ohne Guard-Transformationen 0,439.
  K1 ist also besser als der Status quo, aber weit vom Oracle. **Heros reale Hand liegt in 21/64 Fällen
  AUSSERHALB des K1-Supports** (Preflop-Klassen-Prior des Trackers schließt sie aus).
- **G2 Latenz/Ausführung (Live-Kanal, PRINCE, TexasSolver ON):** erste Probe: Plan gespielt 1/10,
  7/10 „deadline" — Ursache Mechanik (ein Solve-Thread, 0,5 s Queue-Budget: eine langsame Entscheidung
  blockierte alle folgenden). Fix: 3 Threads, 3 s Queue, 12 s Deadline (der Harness hat keinen
  Entscheidungs-Timeout). Nachmessung 40 Plan-Pot-Entscheidungen: deadline 0/40, **Plan gespielt 25/40,
  offtree 11/40** (Villain-Sizes 0,5/0,66 Pot treffen die Baumarme 0,35/0,75/1,5 nicht; exakter
  Chip-Vergleich ohne Snapping, wie du verlangt hast), hand_not_in_range 4/40. Latenz v10 p50 3,0 / p99
  10,2 s vs v5 2,1 / 8,2 s.
- **Off-Tree-Fallback ist die Katastrophenquelle:** alle drei Gym-Decks ≤ −100 bb entstanden im Fallback
  auf die NACKTE Basis (r6_button + wert_bremse ohne die v5-GPU-Chirurgie): zwei über offtree, eines in
  einem Pot unter der 15-bb-Schwelle, der dann über 30 bb eskalierte (dort hatte v5 die Chirurgie).

## Die drei bekannten Lücken
L1 Off-Tree: Fallback auf nackte Basis. Kandidaten: (a) Root mit der tatsächlichen Villain-Size im Baum
NEU lösen (gleiche Root-Ranges vom River-Beginn, erweiterter Baum), (b) Fallback-Ziel = v5-Chirurgie.
L2 K1-Support: Preflop-Prior aus Blueprint-Mischung statt Tracker-Klassenliste.
L3 K1-Genauigkeit: Advisor-Backend ≠ Basis-Politik; TV 0,21. Budget 0,02 mit S=12 nicht messbar.

## Kontext aus unserer Versionsgeschichte (bitte gegenprüfen)
- v5-Sprung (+27,6 ± 1,8 Spiegel) kam aus der GPU-Chirurgie in Big Pots (Desaster-Calls). v10 ERSETZT
  diese Chirurgie durch den Plan; wo der Plan nicht greift (offtree, Support, Sub-Schwelle), fehlt sie.
- v8 (Solver-Play, hand-abhängig gated, mit Injektion) war im Spiegel NEUTRAL (+2,3 ± 2,4), im Replay
  auf GTOW-Händen +278 bb.
- Purify (Mixing abflachen) brach live von −20 auf −58 ein: Live-Brüche kamen bisher aus Struktur-
  änderungen der Politik, nicht aus Feinpräzision.

## Fragen
1. Ist v10 in diesem Zustand eine VOLLSTÄNDIGE Version im Sinne deiner Build-Karte, oder fehlt etwas,
   das nicht in L1–L3 steht? Welche Lücke ist die gefährlichste für den Live-Test?
2. Deine Reihenfolge und konkrete Lösung für L1–L3. Insbesondere L1: ist (a) Neulösen mit erweitertem
   Baum bei gleichen Root-Ranges konsistent mit deiner Plan-Doktrin? Oder (b)? Oder Size-Toleranzband?
3. G3: Ist das Budget 0,02 mit unserem Oracle sinnvoll prüfbar? Was ist das richtige Kriterium, wenn K1
   den Status quo (Tracker 0,26) verbessert, aber das Oracle nicht erreicht? Reicht „besser als Tracker +
   Support-Verletzung ≈ 0" als Freigabe für K2?
4. Sollen wir mit dem heutigen v10 die GTOW-Smokes (20/100 Hände) fahren, um Live-Fakten (Off-Tree-Quote
   gegen echte GTOW-Sizes, Plan-Quote, Fallback-Verluste) zu bekommen, oder erst L1/L2 schließen?
5. Was in v10 ist aus deiner Sicht bereits belastbar bewiesen und darf bleiben, was ist noch Hypothese?

Deutsch, konkret, keine Zeitpläne.


### F1. Antwort gpt-6-astra (wörtlich, 3.624 Reasoning-Tokens)

## Kurzurteil

**Nein: v10 ist ein implementierter Kandidat, aber noch keine vollständig qualifizierte Ersatzversion für v5.** Die genaue Build-Karte und die K1–K5-Verträge liegen mir hier nicht vor; eine formale Vollständigkeit dieser Artefakte kann ich deshalb nicht bestätigen. Nach den gemeldeten Ergebnissen sind jedenfalls zentrale Ausführungs- und Modellannahmen nicht erfüllt.

Die wichtigste Unterscheidung:

- **Der Plan verbessert die untersuchten abstrahierten Root-Spiele.**
- **Die tatsächlich ausgeführte Gesamtpolitik ist nicht identisch mit diesem Plan.**
- **Gerade dort, wo sie abweicht, fehlen bisherige Schutzmechanismen.**

Meine Reihenfolge lautet:

> **L1(b): vollständigen v5-Fallback herstellen → L2: Support strukturell korrigieren → instrumentierter Live-Smoke → L3: Policy-/Oracle-Konformität verbessern → L1(a): kontrolliertes Off-Tree-Re-Solving.**

Shadow-Messungen gegen GTOW können bereits vorher laufen. **Den heutigen, nachweislich ungeschützten v10 würde ich nicht selbst handeln lassen.**

---

# 1. Ist v10 vollständig? Was fehlt außer L1–L3?

## 1.1 Die Gates tragen derzeit unterschiedliche Aussagen

| Gate | Derzeit belastbare Aussage | Was nicht bewiesen ist |
|---|---|---|
| A/A | Die getesteten identischen Ausführungspfade sind nach dem Seed-Fix gepaart reproduzierbar | Vollständige Branch-Abdeckung, korrekte Unsicherheitsintervalle, Live-Thread-Sicherheit |
| G5 Spiegel | Punktschätzer zugunsten v10; keine erkennbare massive Gesamtregression in dieser Stichprobe | Positive Wirkung: CI umfasst deutliche Gewinne und Verluste |
| G4 Prüfstand | Plan ist in den elf untersuchten gemeinsamen Root-Spielen gegenüber **diesem Gym-Arm A** besser | Verbesserung gegenüber produktivem v5; Übertragbarkeit auf alle Roots oder GTOW |
| G3 K1 | K1 liegt im Mittel näher am gemeldeten Oracle als Tracker-Parität | Erfüllung des Vertrages; korrekter Support; hinreichend genaue eigene Range |
| G2 Ausführung | Der Queue-Fix verbessert den beobachteten Durchlauf; Plan wird tatsächlich verwendet | Verlässliche Planabdeckung, belastbare Tail-Latenz, geschlossene Fallback-Strategie |

**G3 ist nicht bestanden. G2 ist funktionell verbessert, aber wegen 37,5 % Nicht-Plan-Ausführung in dieser Probe und ungeschütztem Fallback nicht als erfolgreicher Plan-Deployment-Nachweis abgeschlossen.**

Die Quote allein wäre kein Ausschlussgrund: Ein bewusst hybrider Bot darf häufig v5 spielen. Dann muss aber genau diese Hybridpolitik gebaut, protokolliert und bewertet werden.

## 1.2 Gefährlichste Lücke für den nächsten Live-Test: L1

**L1 ist die unmittelbar gefährlichste Lücke.** Nicht, weil Off-Tree prinzipiell schlimmer als falsche Ranges wäre, sondern weil ihr hier bereits eine konkrete Regression identifiziert habt:

- Plan kann nicht handeln.
- v5-Chirurgie wurde entfernt.
- Die schwächere Basis übernimmt.
- In genau diesem Pfad liegen eure gemeldeten schweren Verluste.

Das ist kein Forschungsrisiko mehr, sondern ein bekannter Integrationsfehler.

**L2 ist der stärkste fundamentale Korrektheitsfehler.** Eine tatsächlich erreichte eigene Hand darf bei korrekter Rekonstruktion der eigenen gespielten Politik nicht strukturell ausgeschlossen sein. 21/64 sind kein numerisches Randproblem.

**L3 ist danach das größte verbleibende Modellrisiko.** Auch bei perfekter Abdeckung kann ein Plan auf einer falschen eigenen Range systematisch falsch zusammengesetzt sein.

## 1.3 Zusätzlich fehlt die „Policy Closure“

Das steht nicht vollständig in L1–L3:

> Was gilt nach einer Abweichung vom Plan für alle späteren Entscheidungen derselben Street?

Beispiel:

1. Ein Plan wird am River-Beginn erzeugt.
2. Ein Fallback spielt eine andere Aktionsverteilung.
3. Eine spätere Aktion passt zufällig wieder in den alten Baum.
4. Der Bot nimmt den alten Plan wieder auf.

**Das ist nicht automatisch konsistent.** Dass die tatsächlich gewählte Aktion im Baum vorkommt, reicht nicht. Die Wahrscheinlichkeit, mit der verschiedene Hände diese Aktion genommen haben, kann durch den Fallback verändert worden sein.

Ihr braucht einen expliziten Zustandsautomaten, etwa:

- `PLAN_VALID`
- `PLAN_INVALID_OFFTREE`
- `PLAN_INVALID_EXECUTION`
- `FALLBACK_COMMITTED`
- `RESOLVED_NEW_PLAN`

**Standardregel: Nach strategisch abweichendem Fallback kein stilles Zurückspringen in den alten Plan.** Eine Wiederaufnahme benötigt nachgewiesene Prefix-/Range-Konsistenz.

Ebenso muss der Prüfstand die **wirklich ausgeführte Hybridpolitik** bewerten, nicht nur den idealen Plan ohne Fallbacks.

## 1.4 Zusätzlich fehlen Kanalparität und Scheduler-Nachweis

### Kanalparität

G4 vergleicht gegen v5-GYM ohne TexasSolver. Damit fehlt gerade ein Bestandteil, den ihr als wesentliche v5-Stärke beschreibt.

Das macht G4 nicht wertlos. Es macht seine Aussage enger:

> Der Plan schlägt die getestete Gym-Referenz im definierten Root-Spiel.

Für „ersetzt produktives v5“ braucht ihr einen Vergleich gegen dessen tatsächliche vollständige Entscheidungslogik.

### Scheduler

Drei Threads beseitigen nicht automatisch alle Probleme eines überlasteten Solvers. Prüfen müsst ihr insbesondere:

- Thread-Sicherheit von Solver, Caches und RNG;
- verspätete Ergebnisse nach Ablauf einer Entscheidung;
- Ergebnisse, die versehentlich in einen inzwischen veränderten Zustand übernommen werden;
- weiterlaufende Arbeiten nach Deadline;
- verbleibendes Zeitbudget für den Fallback.

Jedes Solverresultat braucht einen unveränderlichen Schlüssel aus mindestens Hand-/Street-/State-ID, Range-, Baum- und Policy-Version. **Ein veraltetes Ergebnis darf nie ausgeführt werden.**

Außerdem: **0/40 Deadlines beweist keine geringe Deadline-Rate.** Bei unabhängigen, repräsentativen Versuchen liegt die einseitige 95-%-Obergrenze rechnerisch noch bei ungefähr 7,2 %. Eure Stichprobe ist möglicherweise zusätzlich selektiert.

Der gemeldete p99 aus 40 Beobachtungen ist praktisch eine Beschreibung des oberen Stichprobenendes, keine belastbare Produktions-p99-Schätzung.

---

# 2. L1: zuerst vollständiger v5-Fallback, danach Re-Solving

## 2.1 Sofortige Lösung: L1(b)

Die grundlegende Routing-Regel sollte lauten:

```text
wenn ein gültiger, zustandskonsistenter Plan rechtzeitig verfügbar ist:
    Plan-Verteilung ausführen
sonst:
    vollständige produktive v5-Verteilung ausführen
```

**Nicht:** nackte Basis plus ausgewählte Guards.

Das gilt für alle Nicht-Plan-Fälle:

- Off-Tree;
- Support-Fehler;
- unterhalb der Plan-Schwelle;
- Deadline;
- Solverfehler;
- ungültiges oder veraltetes Ergebnis;
- ungültiger Plan nach früherem Fallback.

### Besonders wichtig: Pot-Schwellen sind keine dauerhafte Befreiung

Wenn am River-Beginn der Pot unter 15 bb liegt, darf das nicht bedeuten:

> Diese Hand bekommt auf dem gesamten River keine v5-Chirurgie mehr.

Der Fallback muss **bei jeder Entscheidung mit dem aktuellen Zustand** ausgewertet werden. Eskaliert der Pot später über die v5-Schwelle, muss die entsprechende v5-Logik greifen.

### Was „Fallback auf v5“ beweisen muss

Für denselben Informationszustand:

\[
\pi_{\text{v10, Fallback}}(\cdot\mid s)
=
\pi_{\text{v5, produktiv}}(\cdot\mid s)
\]

einschließlich:

- Modell-/Konfiguration;
- Guard-Reihenfolge;
- Solverzugang;
- RNG-Konvention;
- Legalitätsbehandlung.

Wenn das aus Laufzeitgründen nicht garantiert werden kann, müsst ihr einen weiteren degradierten Fallback explizit ausweisen. Dann dürft ihr aber nicht mehr behaupten, alle Nicht-Plan-Zustände seien durch v5 abgesichert.

**Planzeit plus nachträglich gestartete vollständige v5-Latenz kann euer Gesamtbudget überschreiten.** Bekannte Off-Tree-/Support-Fälle deshalb vor unnötigem Solve erkennen; für erst spät erkennbare Fehler ein bewusstes Fallback-Budget beziehungsweise eine vorbereitete Rückfallstrategie vorsehen.

L1(b) beseitigt den bekannten Schutzverlust. Es beweist noch keine globale Nichtregression: Der Plan kann zuvor andere Zustände erzeugt haben als v5.

## 2.2 L1(a): gleiche Root-Ranges reichen nicht für Konsistenz

**Ein kompletter Neu-Solve vom River-Beginn mit erweitertem Baum und unveränderten Anfangsranges ist nicht automatisch konsistent mit einem bereits ausgeführten Plan.**

Beispiel:

- Alter Plan: Hero checkt bestimmte Hände mit bestimmten Wahrscheinlichkeiten.
- Villain setzt eine nicht enthaltene Größe.
- Neuer Root-Solve ändert rückwirkend Heros ursprüngliche Check-Strategie.
- Die neue Fortsetzung setzt dadurch eine andere Check-Range voraus als tatsächlich gespielt wurde.

Gleiche Anfangsranges verhindern diesen Fehler nicht.

### Drei unterschiedliche Fälle

**Fall A: Erweiterung vor der ersten Ausführung des Plans**

Unproblematischer: Baum erweitern, komplett lösen, dann diesen Plan ausführen. Die zusätzlichen Größen 0,5 und 0,66 Pot vorab aufzunehmen ist deshalb eine sinnvolle Abdeckungsmaßnahme, sofern Laufzeit und Qualität bestehen bleiben.

Es löst das allgemeine Off-Tree-Problem allerdings nicht.

**Fall B: Neu-Solve nach bereits ausgeführten eigenen Aktionen**

Dafür müsst ihr mindestens:

- den tatsächlich ausgeführten eigenen Prefix für **alle Hände** festhalten;
- die daraus entstehenden eigenen Reaches verwenden;
- die tatsächliche Villain-Aktion exakt abbilden;
- eine explizite Belief-Regel für diese zuvor nicht modellierte Aktion besitzen;
- die neue Fortsetzung als neuen Plan behandeln.

Ein vollständiger Root-Neu-Solve mit unveränderten eigenen Prefix-Strategien kann ein sinnvoller konstruktiver Ansatz sein. Ein unbeschränkter Root-Neu-Solve ist etwas anderes.

**Fall C: Behauptung eines „sicheren“ Re-Solves**

Dafür reichen weder gleiche Root-Ranges noch ein eingefrorener Prefix. Ihr benötigt zusätzliche Sicherheitsbedingungen, etwa passende gegnerische CFV-Grenzen.

Und: Eine Garantie im alten abstrahierten Spiel deckt eine dort gar nicht vorhandene gegnerische Größe nicht ohne Weiteres ab.

**Meine Empfehlung:** L1(a) später als eigenen, eingeschränkt konsistenten Re-Solve-Pfad bauen. Nicht als schnellen Patch ausgeben, der die bisherigen Plan-Garantien automatisch erbt.

## 2.3 Kein strategisches Size-Toleranzband als Sofortlösung

Meine Forderung nach exakten Größen bedeutet:

> Pot, Einsatz, Stack und Auszahlungen müssen den tatsächlichen Chips entsprechen.

Sie bedeutet nicht, dass ihr rohe Fließkommazahlen auf bitgenaue Gleichheit prüfen sollt.

Zulässig:

- kanonische Integer-Chips;
- regelkonforme Rundung;
- Zusammenführen numerisch identischer Größen;
- winzige technische Toleranzen bei Darstellungskonversionen.

**0,66 Pot auf 0,75 oder 0,5 auf 0,35 zu mappen ist keine technische Toleranz.** Es ist eine strategische Translation, die Ranges, Pot Odds und Raise-Fortsetzungen verändert.

Das könnte man als eigene Näherungsmethode untersuchen. Für euren gegenwärtigen Fehler ist es die schlechtere Erstlösung als vollständiger v5-Fallback.

---

# 3. L2: Support strukturell reparieren, nicht die reale Hand hineinpatchen

## 3.1 Der richtige Prior

„Blueprint-Mischung statt Tracker-Klassenliste“ ist die richtige Richtung, **wenn diese Mischung tatsächlich die gespielte Preflop-Politik beschreibt**.

Für die eigene Range gilt schematisch:

\[
r_H(h\mid \mathcal H)
\propto
r_0(h)
\prod_{t:\,\text{Hero handelt}}
\pi_{\text{ausgeführt},t}(a_t\mid h,\mathcal H_t).
\]

Dabei müssen enthalten sein:

- tatsächlicher Preflop-Blueprint;
- tatsächliche Mischungs- und Routing-Regeln;
- spätere Advisors;
- Guards;
- sonstige politikverändernde Wrapper.

Eine globale Mischung von Charts reicht nicht, wenn die Komponentenauswahl hand- oder zustandsabhängig ist.

## 3.2 Was nicht zulässig ist

Nicht:

```text
wenn reale Hero-Hand fehlt:
    dieser Hand epsilon geben
```

Damit hängt die vermeintlich öffentliche Range von der tatsächlich gezogenen privaten Hand ab. Ihr behandelt ein Rekonstruktionsproblem durch privilegierte Information, statt es zu lösen.

Zulässig ist eine vorab definierte, für alle Hände gleich angewendete numerische Stabilisierung. Sie ersetzt aber keine korrekte strukturelle Unterstützung.

Prüft zusätzlich:

- Suit-Kanonisierung;
- Combo-Indizes;
- Board-Masken;
- Unterlauf kleiner Wahrscheinlichkeiten;
- falsche Interpretation gerundeter Blueprint-Nullen.

## 3.3 Das richtige Support-Kriterium ist nicht „ungefähr null“

Für **strukturelle Support-Verletzungen** ist das Ziel exakt null:

> Jede unter der tatsächlich gespielten Politik erreichbare eigene Hand muss nach dieser Historie positiven Support besitzen.

Ein endlicher Test kann das nicht global beweisen. Deshalb braucht ihr beides:

1. konstruktiv korrekte Range-Erzeugung;
2. gezielte Regressionstests auf zuvor fehlende Hände und seltene Linien.

Das ist stärker als „im nächsten Sample trat nichts auf“.

---

# 4. L3 und G3: Was ist sinnvoll prüfbar?

## 4.1 Das alte Budget ist mit diesem Oracle nicht als Pass-Kriterium auflösbar

Ein TV-Rauschboden von 0,095 ist nicht mit einem sauber nachweisbaren Zielwert 0,02 vereinbar.

Aber daraus folgt nicht:

> K1 wäre wahrscheinlich schon hinreichend genau.

Eure gemeldeten Abweichungen und der Backend-Unterschied zeigen ein reales Modellproblem.

Die „untere Schranke 0,145“ kann ich ohne Herleitung und Konfidenzniveau nicht als zertifizierte Schranke bestätigen. Aus Mittelwert 0,209 und Rauschboden 0,095 allein folgt sie nicht. Ein empirischer Rauschboden darf nicht beliebig als sichere Fehlerkorrektur subtrahiert werden.

### Größenordnung des Sampling-Problems

Nur als Näherungsrechnung unter \(S^{-1/2}\)-Skalierung:

\[
S_{\text{neu}}
\approx
12\left(\frac{0{,}095}{0{,}02}\right)^2
\approx 271.
\]

Für einen Rauschboden von 0,01 wären es ungefähr 1083 statt zwölf Samples.

Das sind **keine garantierten erforderlichen Samplezahlen**: Posterior-Normalisierung, kleine Aktionswahrscheinlichkeiten und Supportfehler können die Skalierung verschlechtern. Es zeigt aber, dass S=12 keine Präzisionsprüfung für 0,02 ist.

## 4.2 Beste Lösung: Politik auswerten statt Aktionen sampeln

K1 sollte nach Möglichkeit nicht ein anderes Advisor-Backend approximieren lassen, was `decide()` tatsächlich tut.

Besser ist eine gemeinsame, möglichst reine Schnittstelle:

```text
policy_distribution(informationszustand, hypothetische_hand, policy_version)
    -> vollständige Aktionsverteilung
```

Diese muss die tatsächlich wirksamen Wrapper enthalten.

Dann:

- `decide()` sampelt aus dieser Verteilung;
- K1 verwendet dieselbe Verteilung für die Likelihood;
- Tests vergleichen denselben Policy-Kern;
- zusätzliche stochastische Berechnung innerhalb der Policy wird separat behandelt.

Dabei müssen Zustand, Historie und Policy-Version eingefroren sein. Eine Gegenfaktik für eine andere Hand darf keine persistenten Tracker- oder Plan-Zustände mutieren.

**Der Unterschied „Advisor-Backend ≠ Basis-Politik“ ist kein unvermeidliches Pokerproblem, sondern zunächst ein Schnittstellenproblem.**

## 4.3 „Besser als Tracker + Support null“ reicht nur für weitere K2-Experimente

**Als Freigabe für nachgelagerte K2-Tests: ja. Als vollständige strategische Produktionsfreigabe: nein.**

Der Grund: Eine im Mittel bessere Range kann gerade bei den planentscheidenden Blockern oder starken Händen schlechter sein. TV gewichtet nicht nach strategischem Schaden.

Für eine beschränkte Funktion \(f\) gilt:

\[
|\mathbb E_p f-\mathbb E_q f|
\le
(\max f-\min f)\,\operatorname{TV}(p,q).
\]

In großen Pots kann selbst eine kleine TV-Abweichung relevant sein. Umgekehrt kann eine größere TV-Abweichung strategisch fast bedeutungslos bleiben.

### Ich würde G3 in drei Teile zerlegen

#### G3-S: strukturelle Korrektheit

Harte Anforderungen:

- keine strukturellen Support-Verletzungen;
- korrekte Board-/Combo-Masken;
- normalisierte, endliche Ranges;
- tatsächlicher Policy-Pfad als Likelihood-Grundlage.

#### G3-P: Policy-/Posterior-Parität

- Oracle-Rauschen separat bestimmen;
- auf einem Teilbestand präziseres oder deterministisches Oracle;
- K1 gegen Tracker **gepaart** vergleichen;
- Mittel und problematische Tails untersuchen;
- nach Händen/Historien clustern, nicht nach einzelnen Combos.

Eine Verbesserung des Mittelwerts reicht nicht, wenn die schlechtesten entscheidungsrelevanten Fälle regressieren.

#### G3-D: downstream Entscheidungsqualität

Auf demselben gemeinsamen Referenzspiel vergleichen:

- Plan mit K1;
- Plan mit Tracker;
- Plan mit präziserer Referenzrange;
- vollständiges produktives v5.

Messen:

- Aktions-Regret;
- Worst-Case-Wert beziehungsweise BR-Schaden;
- Tail-Verluste;
- Empfindlichkeit der Raise-/Call-Selektion.

**Nicht jedem Arm sein eigenes Bewertungsuniversum geben.** Sonst kann ein Plan unter seiner eigenen falschen Range hervorragend aussehen.

Das ist eine sinnvolle neue Freigabelogik. Sie darf aber nicht rückwirkend als „altes G3 bestanden“ verbucht werden. Vertrag ändern, Hypothese registrieren, auf unbenutzten Fällen prüfen.

---

# 5. GTOW-Smokes: heute oder nach den Fixes?

## Meine Entscheidung

### Heute möglich: v5 handelt, v10 läuft im Shadow

Damit könnt ihr bereits messen:

- reale GTOW-Größen;
- Off-Tree-Gründe;
- Support-Verletzungen;
- potentielle Planabdeckung;
- Rechenzeiten;
- Unterschiede zwischen Produktions- und Gym-Kanal.

Wichtig: Diese Quoten gelten zunächst für **unter v5 erreichte Zustände**, nicht für die spätere Zustandsverteilung eines handelnden v10.

### Heute nicht empfohlen: unfixed v10 handelt

Die Information „0,5/0,66-Pot-Größen treten auf und der Fallback ist schwächer“ habt ihr bereits. Dafür müsst ihr keine bekannten Schutzlücken gegen GTOW ausspielen.

### Nach L1(b) und struktureller L2-Korrektur: begrenzter handelnder Smoke

Dafür muss L3 noch nicht vollständig gelöst sein, solange das Experiment ausdrücklich **technische und verteilungsbezogene Diagnostik**, nicht strategische Freigabe, bedeutet.

Der vollständige 224-Root-Lauf ist dafür ebenfalls keine Voraussetzung.

## Was 20/100 Hände beantworten können

- Funktioniert das Routing?
- Stimmen State- und Plan-IDs?
- Welche Größen werden tatsächlich gesehen?
- Sind Fallbacks vollständig?
- Treten Support- oder Ausführungsfehler auf?
- Wie verändert sich die Planquote?

**Nicht belastbar:** AIVAT-Wirkung, Fallback-EV oder Sicherheit vor seltenen Katastrophen.

„Fallback-Verluste“ bitte trennen in:

1. realisierten Ausgang von Fallback-Händen;
2. unabhängigen Entscheidungs-Regret;
3. Differenz zur vollständigen v5-Verteilung im identischen Zustand.

Nur die dritte Größe isoliert unmittelbar den behaupteten Schutzverlust. Ein nach Plan-Aktionen erreichter schlechter Fallback-Zustand kann auch durch frühere Planentscheidungen verursacht worden sein.

## Pflichtlogging pro Entscheidung

Mindestens:

- Plan prinzipiell zulässig?
- Plan tatsächlich ausgeführt?
- Ablehnungsgrund;
- vollständige Fallback-Version;
- aktuelle Pot-/Stack-Werte;
- exakte gegnerische Größe;
- Plan-/State-/Range-Hash;
- bereits vom Plan abgewichen?
- Queue-, Solve- und Gesamtlatenz;
- verspätetes Ergebnis verworfen?
- tatsächliche ausgeführte Aktionsverteilung.

Gezielte Tests müssen zusätzlich Off-Tree, Supportfehler, späte Pot-Eskalation und künstliche Deadline auslösen. Auf zufällige 576-Deck-Abdeckung allein würde ich mich dafür nicht verlassen.

---

# 6. Was bereits bleiben darf – und mit welchem Status

## Belastbar genug, um es zu behalten

### Der hand_id-/Seed-Fix

Der Test hat einen konkreten Paarungsfehler entdeckt; der Fix beseitigt ihn auf den gemeldeten Banken. Das ist ein echter Infrastrukturgewinn.

Die Schlussfolgerung lautet allerdings nicht, dass 40 Decks den Fehler prinzipiell niemals hätten zeigen können. **Gezielt erzwungene Planpfade sind stärker als bloß größere zufällige A/A-Samples.**

### Der Plan-Solver als strategischer Kandidat

Die elf G4-Roots liefern konsistente Evidenz zugunsten des Plans **innerhalb dieses Prüfstands**.

Zur Vorzeichenkonvention: Wenn \(w\) der Worst-Case-Auszahlungswert für Hero ist, bedeutet \(w(A)-w(B)<0\), dass B besser ist. Wenn \(w\) hingegen als positive Exploitability definiert wäre, wäre das Vorzeichen anders zu lesen. Diese Definition gehört ausdrücklich in den Report.

### Die vollständige v5-Chirurgie als Rückfallstrategie

Sie darf nicht durch die Einführung des Plans versehentlich verschwinden. Sie ist der bestehende produktive Schutz, bis ihr deren Ersatz tatsächlich geprüft habt.

### Exakte Chips und gemeinsame Root-Spiele

Beides sind richtige Grundlagen. Gemeinsame Root-Ranges machen den Vergleich intern fair; sie beweisen nicht, dass diese Ranges die realen Hände korrekt beschreiben.

## Nur als experimentelle Komponente behalten

### K1

K1 ist nach euren Daten ein besserer Näherungskandidat als der Tracker, aber noch kein korrekt qualifizierter Belief-Lieferant. Support reparieren, Backend-Parität herstellen, downstream prüfen.

### Der Drei-Thread-Scheduler

Behalten, sofern Thread-Sicherheit und veraltete Ergebnisse kontrolliert werden. „0/40 Deadline“ allein qualifiziert ihn nicht.

### Der v10-Stack

Als experimenteller Stack behalten. Nicht als neuer Champion deklarieren.

## Weiterhin Hypothesen

- v10 verbessert produktives v5 gegen GTOW.
- Der G5-Punktschätzer bildet einen positiven echten Spiegel-Effekt ab.
- Die elf G4-Roots repräsentieren die übrigen 213.
- K1 verbessert die Planqualität auf der realen Zustandsverteilung.
- Die Fallbacks erklären den gesamten negativen Tail.
- Ein unbeschränkter erweiterter Root-Neu-Solve erhält Plan-Konsistenz.

Falls die elf Roots wegen kurzer Laufzeit zuerst fertig wurden, droht zusätzlich **Komplexitäts-/Pot-Bias**. 11/11 ist dann kein repräsentativer Querschnitt, selbst wenn jeder Einzelbefund korrekt ist.

---

# 7. Gegenprüfung eurer Versionsgeschichte

Drei Präzisierungen:

1. **Den gesamten v5-Sprung darf ich nicht der GPU-Chirurgie allein zuschreiben.** Im früheren Briefing besteht v5 aus mehreren Wrappern; allein für die Wertbremse nennt ihr repliziert etwa +8 bb/100. Der Gesamtvergleich +27,6 ist keine isolierte Ablation der Chirurgie. Die aktuelle Fallback-Beobachtung stützt aber klar, dass ihr einen wichtigen Schutz entfernt habt.

2. **v8 bleibt ein ernsthafter Kandidat, kein verpasster bewiesener Live-Gewinn.** Spiegelneutralität widerlegt den Nutzen nicht. Die +278 bb Replay-Kontrafaktik beweist ihn ebenfalls nicht. Solver-PLAY und Stack-off-Bremse müssen weiterhin getrennt betrachtet werden.

3. **Purify begründet Vorsicht bei Strukturänderungen, nicht Entwarnung bei Feinpräzision.** Aus einem großen strukturellen Fehlschlag folgt nicht, dass Range- oder Fortsetzungsfehler ungefährlich wären. Gerade v10 verändert Struktur: ganze Aktionspläne, ihre Ranges und ihr Zusammenspiel mit Fallbacks.

---

## Endgültige Freigabeentscheidung

**Heutiger Status:** gebaut, teilweise validiert, nicht vollständig qualifiziert.

**Gefährlichste unmittelbare Lücke:** ungeschützter Fallback.

**Zwingende Reihenfolge:**

1. Vollständiges produktives v5 in allen Nicht-Plan-Pfaden wiederherstellen.
2. Planinvalidierung und spätere Wiederaufnahme explizit regeln.
3. K1-Support aus der tatsächlich gespielten Politik rekonstruieren.
4. Produktionsnahe, gezielte Routing-/Concurrency-Tests bestehen.
5. Instrumentierten Live-Smoke fahren.
6. K1 nach messbarer Policy-Parität und downstream EV bewerten.
7. Off-Tree-Re-Solving separat hinzufügen und qualifizieren.

**Nicht erforderlich vor dem technischen Smoke:** perfektes TV=0,02 oder der gesamte 224-Root-Holdout.

**Sehr wohl erforderlich:** keine bekannten ungeschützten Pfade und keine systematische Ausgrenzung tatsächlich erreichter eigener Hände.

Der entscheidende Abschlussbeweis ist nicht „der Plan ist gut“, sondern:

> **Die tatsächlich ausgeführte Politik aus Plan, Beliefs, Fallback und Wiederaufnahme ist geschlossen definiert – und genau diese Politik wurde gegen die vollständige produktive Referenz geprüft.**

---

## TEIL G — Die Hybrid-These des PO (2026-09-08, Kette an Teil F)

### G0. Frage (wörtlich)

# Nachfrage: Die Hybrid-These des Product-Owners

Der Product-Owner (PO) hat deine Vollständigkeits-Antwort gelesen und stellt zwei Thesen auf, die du
prüfen sollst. Ich (Fable) gebe dir dazu meine Zahlen und Zweifel.

## These 1 (PO): „Der Hybrid aus v5 und v10 spielt wahrscheinlich sowieso am besten von allen Alternativen."
Gemeint ist H = { K2-River-Plan (K1-Range, öffentlich gated, pot_river ≥ 15 bb), wenn ein gültiger Plan
vorliegt und Heros Hand im Support ist; SONST die vollständige produktive v5-Politik (TexasSolver-Resolver
+ wert_bremse + GPU-Chirurgie mit Injektion) — je Entscheidung neu ausgewertet, also auch bei
Sub-Schwellen-Eskalation }. Das entspricht deiner L1(b)-Empfehlung.

Messlage dazu: v10 (mit NACKTER Basis als Fallback) vs v5 im Gym-Spiegel +11,7 ± 10,9 (1968 Decks), alle
drei Decks ≤ −100 bb aus dem nackten Fallback. Plan-Quote live 25/40, offtree 11/40, Support 4/40.
G4: Plan in 11/11 Roots weniger ausbeutbar und weniger Regret als v5-Gym (Arm A ohne TexasSolver).

Meine Zweifel an „dominiert beide Eltern":
(a) Der Plan verändert Heros River-Range gegenüber der Basis (er spielt eine andere Mischung). Wenn dann in
derselben Hand ein Fallback auf v5 greift, rechnet v5s Chirurgie mit der TRACKER-Range (Basis-Modell), nicht
mit der vom Plan erzeugten Range — die Chirurgie löst dann ein anderes Spiel als das gespielte (deine
Policy-Closure-Sorge).
(b) Selektionseffekt: der Fallback greift systematisch in bestimmten Zuständen (Villain bettet 0,5/0,66 Pot;
Hero hält eine Hand außerhalb des Prior-Supports). Eine Politik, die dort v5 spielt und sonst Plan, ist eine
neue Politik mit eigener Exploitability — nicht Max(v5, v10).
(c) Wo v5 und Plan sich widersprechen und der Plan „gewinnt", haben wir nur G4 (11 Roots, Gym-Arm) als
Evidenz; live ist v5 dort der TexasSolver, und TexasSolver und GPU-Solver stimmen zu r=0,999 überein — der
Plan-Vorteil live könnte klein sein, während die Fallback-Nähte neue Kosten haben.

## These 2 (PO): „Wir bauen ja immer einen Hybrid. Jede neue Bot-Version ist ein Hybrid."
Historisch stimmt das: v1–v5 sind Guard-Wrapper um eine Basis (sel_guard, turn_wert, button_disziplin,
wert_bremse, GPU-Chirurgie), also Hybride aus Basis + Regeln + Solver-Eingriffen. Dein früherer Einwand
gegen hand-abhängige Hybride (Teil D 6.5, Teil E) steht dagegen. Frage: Was ist die DOKTRIN für
prinzipientreues Hybrid-Bauen? Welche Hybride sind unbedenklich (öffentliches Gating, geschlossene
Fortsetzung, gemessene Nähte) und welche gefährlich? Wie misst man den Hybrid selbst statt seiner Teile?

## Zusatzfrage (PO): Fable orchestriert jede Hand live gegen GTOW
Der PO überlegt, mich (das Modell, das hier schreibt) an jeder Entscheidung über dem Hybrid entscheiden
zu lassen (ich sehe Engine-Dossier: Basis, TexasSolver, Plan-Verteilung, Solver-EVs je Aktion, K1-Range,
Pot-Geometrie; ich wähle und begründe). Historie: Claude Opus 4.8 als Gehirn über der Engine −28,55 AIVAT;
Frontier-LLMs ohne Engine auf dem Leaderboard −8 bis −9; meine 264 gegradeten Entscheidungen 96 % im
Solver-Support. Meine Kostenrechnung: Per-Hand-SD ≈ 214 bb → SE = 214/√n bb/100; Top-5-Band (±4) braucht
~2.900 Hände, −6 von −8 unterscheiden ~32.000; mit mir ~25.000 Tokens und 1–3 Minuten je Hand → 500 Hände
Diagnose ≈ 12 Mio. Tokens/1 Tag, 5.000 Hände ≈ 125 Mio./10 Tage. Mein Vorschlag: 300–500 Hände als
Diagnose (Lehrer-Datensatz „wo widerspreche ich der Engine und warum"), dann Arbiter-Modus (Eingriff nur bei
Unsicherheit der Engine), Beweis nur mit der Engine allein.

## Fragen
1. Ist These 1 haltbar? Unter welchen präzisen Bedingungen dominiert H beide Eltern, und welche unserer
   Messungen würde das zeigen (Prüfstand mit der WIRKLICH ausgeführten Hybridpolitik, Spiegel, Live)?
   Nenne die Fälle, in denen H schlechter als v5 sein kann.
2. Wie muss H gebaut sein, damit die Nähte (a) und (b) keine Kosten erzeugen? Konkret: welche Range
   bekommt die v5-Chirurgie im Fallback (Tracker, K1, oder die vom ausgeführten Plan-Prefix erzeugte)?
3. These 2: formuliere die Hybrid-Doktrin in 5–8 Regeln, die wir in CLAUDE.md verankern können.
4. Zur Orchestrierung durch mich: stimmst du meiner Zahlen- und Rollenrechnung zu (Diagnose ja, Beweis
   nein)? Was würde den Lehrer-Datensatz maximal wertvoll machen, und wo ist der Irrtum, den ich als
   Spieler am ehesten begehe (Exploit-Versuchung, Over-Checking, Range-Blindheit)?
5. Konkreter nächster Build in Reihenfolge (v10.1 = H?), mit Abnahmetests.

Deutsch, konkret, keine Zeitpläne. Antworte auch dort direkt, wo du dem PO widersprichst.


### G1. Antwort gpt-6-astra (wörtlich, 4.142 Reasoning-Tokens)

## Urteil zu den beiden Thesen

**These 1 ist in dieser Form nicht haltbar.** H ist der naheliegende nächste Kandidat und repariert einen bekannten Schutzverlust. Daraus folgt weder „wahrscheinlich bester Bot“ noch „dominiert beide Eltern“.

**These 2 ist als Beschreibung eurer Software richtig, als strategische Rechtfertigung aber unzureichend.** Fast jede praktische Poker-KI ist ein Hybrid aus unterschiedlichen Verfahren. Entscheidend ist, ob daraus eine wohldefinierte Gesamtpolitik mit konsistenten Fortsetzungen entsteht — und ob genau diese Gesamtpolitik geprüft wurde.

Deine Zweifel (a), (b) und (c) sind berechtigt. Zwei zusätzliche Präzisierungen:

- H ist wegen `Heros Hand im Support` **nicht vollständig öffentlich gegated**. Dieser Teil der Auswahl hängt von privater Information ab.
- „Vollständiges unverändertes v5 als Fallback“ und „Fallback mit korrigierter, vom Hybrid erzeugter Range“ sind nach einem abweichenden Plan-Prefix **nicht dieselbe Politik**. Diese beiden Ziele müssen im Build ausdrücklich getrennt werden.

---

# 1. Wann kann H beide Eltern dominieren?

## 1.1 Zuerst definieren, was „dominiert“ bedeutet

Es gibt mindestens drei unterschiedliche Behauptungen:

1. **Gegnerleistung:** H erzielt gegen GTOW einen höheren Erwartungswert als beide Eltern.
2. **Robustheit:** H besitzt einen besseren Worst-Case-Wert beziehungsweise geringere Exploitability.
3. **Punktweise Verbesserung:** H ist gegen jeden möglichen Gegner mindestens so gut wie beide Eltern.

Eure Messungen belegen derzeit keine dieser drei Behauptungen für die produktive Gesamtpolitik. Die dritte wäre eine besonders starke, im Allgemeinen nicht zu erwartende Eigenschaft.

Eine bessere Worst-Case-Absicherung garantiert außerdem nicht automatisch eine höhere Auszahlung gegen einen bestimmten, nicht exakt optimalen Gegner.

## 1.2 Eine hinreichende Bedingung gegen einen festen Gegner

Eine einfache, präzise hinreichende Konstruktion wäre:

- Beide Eltern spielen bis zum Auswahlpunkt identisch.
- Der Auswahlpunkt hat dieselben tatsächlich entstandenen Root-Ranges.
- Beide Alternativen definieren vollständige Fortsetzungen.
- Ihr kennt deren korrekte bedingte EVs gegen denselben festen Gegner.
- H wählt an jedem Auswahlpunkt die Fortsetzung mit dem höheren EV.
- Rechenfehler, Timeouts und spätere Politikwechsel sind in diesen EVs enthalten.

Dann kann H gegen diesen Gegner beide Eltern im Gesamterwartungswert mindestens erreichen.

**Diese Voraussetzungen habt ihr nicht.** Insbesondere sind eure G4-Werte keine verlässlichen konditionalen Live-EVs der beiden vollständigen produktiven Fortsetzungen.

Für häufiges Umschalten zwischen Eltern wäre eine andere hinreichende Bedingung nötig: Jeder Wechsel müsste unter den tatsächlich entstehenden Zuständen eine nachgewiesene Policy-Improvement-Bedingung erfüllen. Dabei braucht man korrekte **Fortsetzungs-Q-Werte**, nicht nur lokal attraktive Aktionen aus unterschiedlichen Solverrechnungen.

## 1.3 Eine hinreichende Bedingung für Robustheit

Für einen abstrahierten endlichen Prüfstand könnt ihr die vollständige Hybridpolitik gegen eine exakte BR auswerten.

Mit

\[
w(\pi)=\min_\sigma u(\pi,\sigma)
\]

würde

\[
w(H)\geq \max\{w(v5),w(v10)\}
\]

die entsprechende Worst-Case-Dominanz **in diesem Prüfstand** zeigen.

Ein theoretisch abgesichertes Re-Solving-Verfahren könnte Nichtverschlechterung gegenüber einer Referenz unter seinen Voraussetzungen garantieren. Euer heutiges Routing „Plan, sonst v5“ liefert diese Garantie nicht.

## 1.4 Was eure bisherigen Zahlen tatsächlich nahelegen

Aus dem Briefing:

- v10 gegen v5-Gym: positiver, aber sehr unsicherer Punktschätzer.
- Alle drei schweren negativen Decks entstanden im nackten Fallback.
- G4: Plan schlägt in elf Roots den schwächeren Gym-Referenzarm.
- Produktive Planabdeckung: 25/40 Entscheidungen.

Daraus folgt:

> Es gibt einen konkreten Grund, den nackten Fallback durch einen stärkeren zu ersetzen, und einen konkreten Grund, den Plan weiterzuverfolgen.

Nicht:

> Die Kombination ist wahrscheinlich besser als jede vollständige Elternpolitik.

Die drei Verlustdecks sind **positive Kontrollen für die Reparatur**, kein unverbrauchter Beweis für deren durchschnittlichen Gewinn.

## 1.5 Fälle, in denen H schlechter als v5 sein kann

1. **Falsche eigene Range:** Der Plan verändert Heros Check-/Bet-/Raise-Range; der Fallback rechnet mit dem alten Modell.
2. **Falsche gegnerische Range:** Eine Off-Tree-Aktion wird mit einer ungeeigneten Likelihood aktualisiert.
3. **Private Selektion:** Bestimmte Hände gehen systematisch zum Plan, andere zu v5; beide Komponenten wurden für andere Gesamtverteilungen konstruiert.
4. **Unpassende Fortsetzungen:** Der Plan erzeugt eine Raise-Linie, deren spätere Antwort v5 anders zusammensetzt.
5. **Schlechterer Plan in produktiven Zuständen:** G4 gegen v5-Gym überschätzt den Vorteil gegenüber v5 mit TexasSolver.
6. **Rechenbedingte Politikänderung:** Plan und Resolver konkurrieren um Ressourcen; aus einer strategischen Verbesserung wird häufiger ein degradierter Fallback.
7. **Unsichtbarer Wiedereinstieg:** Nach einem Fallback wird ein alter Plan wieder aufgenommen, obwohl dessen Reaches nicht mehr stimmen.
8. **Abstraktionskosten:** Der Plan ist in seinem Baum gut, aber seine Betgrößen oder Raise-Fortsetzungen sind gegen reale Größen schlechter.
9. **Rückwirkung auf die Exploitability:** Einzelne lokal sinnvolle Änderungen verschieben die gesamte Bluff-/Value-Zusammensetzung ungünstig.

Zu deinem Punkt (c): **r=0,999 entscheidet diesen Vergleich nicht.** Gute Übereinstimmung der Solver bei gleichen Inputs sagt wenig darüber, welcher produktive Stack bessere Ranges, Bäume, Trigger und Fortsetzungen verwendet. Sie macht einen großen reinen „Solverkern-Vorteil“ allerdings weniger plausibel als einen Vorteil durch bessere Einbettung.

---

# 2. Wie H gebaut werden muss — und welche Range der Fallback bekommt

## 2.1 Es gibt zwei unterschiedliche Hybridversionen

### H₀: Schutzverlust repariert

- Plan, wenn verwendbar.
- Sonst unverändertes produktives v5.

Das ist L1(b) als unmittelbare Reparatur. Es verhindert, dass ihr absichtlich auf die nackte Basis zurückfallt.

**H₀ ist noch kein range-konsistenter Hybrid.**

### H₁: ausführungs-konsistenter Hybrid

- Plan, wenn verwendbar.
- Die tatsächlich ausgeführte Gesamtpolitik wird über die Historie fortgeschrieben.
- Nach einem Plan-Prefix erhält die Fallback-Fortsetzung passende Ranges.
- Kein unkontrolliertes Zurückspringen in den alten Plan.

Das ist die eigentliche Zielversion.

Wenn ihr v5 dafür andere Ranges übergebt, nennt diese Komponente beispielsweise **`v5_continuation`**. Sie verwendet bewährte v5-Mechanismen, ist aber nicht mehr byte-identisch mit der ursprünglichen v5-Politik.

## 2.2 Welche eigene Range ist richtig?

**Nicht pauschal Tracker. Nicht unverändertes K1. Sondern die aus der tatsächlich ausgeführten Hybridpolitik entstandene Range.**

Schematisch:

\[
r_H(h\mid \mathcal H_t)
\propto
r_{H,0}(h)
\prod_{j<t:\,\text{Hero handelt}}
\pi_H(a_j\mid h,\mathcal H_j).
\]

Dabei ist \(\pi_H\) die wirklich ausgeführte Hybridpolitik, einschließlich ihrer Auswahlregeln.

Für eine Auswahlvariable \(g\):

\[
\pi_H(a\mid h,s)
=
g(h,s)\,\pi_{\text{Plan}}(a\mid h,s)
+
[1-g(h,s)]\,\pi_{\text{Fallback}}(a\mid h,s).
\]

Das ist wichtig: **Nur den Plan-Prefix fortzuschreiben reicht nicht, wenn manche Hände bereits im Prefix anders geroutet wurden.**

Die Datenquelle für \(r_{H,0}\) kann ein korrigiertes K1 sein. K1 liefert dann die Ausgangsrekonstruktion, nicht die unveränderliche Range für alle späteren Entscheidungen.

### Beispiel

Hero checkt am River:

- Handklasse X nach Plan fast immer.
- Handklasse Y wegen eines Support-/Routingpfads nach v5 nur selten.

Nach dem Check muss die Check-Range beide tatsächlichen Wahrscheinlichkeiten berücksichtigen. Weder eine reine Plan-Check-Range noch eine reine v5-Check-Range ist korrekt.

## 2.3 Welche gegnerische Range ist richtig?

Das ist ein separates Problem.

Die gegnerische Range wird aus:

- der Ausgangsrange,
- beobachteten gegnerischen Aktionen,
- eurem expliziten gegnerischen Aktionsmodell

fortgeschrieben.

Eine Villain-Bet von 0,66 Pot, die im Planbaum nicht existiert, besitzt unter diesem diskreten Planmodell keine unmittelbar verwendbare Aktionswahrscheinlichkeit. Ihr braucht deshalb eine definierte Off-Tree-Belief-Regel.

Möglichkeiten sind etwa:

- ein separat validiertes Aktionsmodell für reale Größen;
- ein erweiterter Solve als Modell der gegnerischen Likelihood;
- konservative Referenzranges mit Sensitivitätsprüfung.

**Die vom eigenen Plan erzeugte Hero-Range löst dieses Villain-Problem nicht.** Ebenso darf Heros tatsächliche Hole Card nicht heimlich zur Konstruktion einer vermeintlich öffentlichen gemeinsamen Range verwendet werden.

## 2.4 Wenn noch keine Planaktion ausgeführt wurde

Dann gibt es noch keinen vom Plan verursachten eigenen Prefix-Bruch.

In diesem Fall ist der unveränderte produktive v5-Pfad eine saubere Kompatibilitätsreferenz. Das gilt beispielsweise, wenn der Plan bereits vor seinem ersten Einsatz verworfen wird.

Sobald der Plan eine andere Verteilung ausgeführt hat, bestehen zwei Möglichkeiten:

- bewusst H₀ spielen und die Nahtkosten messen;
- auf eine range-konsistente Fortsetzung H₁ wechseln.

**Beides gleichzeitig als „unverändertes v5 und konsistent mit dem Plan“ zu bezeichnen wäre falsch.**

## 2.5 Supportprüfung darf kein regulärer privater Selector bleiben

`Hero-Hand nicht im Support → v5` ist als Notfallreaktion nötig, solange der Fehler existiert. Als strategische Standardregel ist es problematisch.

Die bessere Konstruktion:

1. K1-Support aus der tatsächlichen eigenen Politik herstellen.
2. Den Plan möglichst anhand öffentlicher, vollständiger Range-Kriterien validieren.
3. Die Prüfung der realen Hand als Assertion beziehungsweise Fehlerdetektor behalten.
4. Ein Auftreten als Defekt zählen, nicht als normale Hybridselektion.

Ein Plan, dessen Input strukturell erreichbare Hände ausschließt, sollte nicht dadurch „gültig“ werden, dass die gerade gezogene Hand zufällig enthalten ist.

## 2.6 Geschlossene Fortsetzung statt Pingpong

Mein Standard wäre:

- **Vor erster Planaktion:** Plan oder v5 auswählen.
- **Nach Planbeginn:** Plan weiterführen, solange gültig.
- **Nach strategischem Planabbruch:** konsistente Fallback-Fortsetzung; alter Plan bleibt ungültig.
- **Neuer Plan:** nur durch expliziten, geprüften Re-Solve.

Bei v5-Fortsetzung werden die Guards weiterhin pro Entscheidung mit dem aktuellen Pot ausgewertet. Ein anfangs kleiner Pot verliert also nicht dauerhaft seine Big-Pot-Chirurgie.

Diese Konstruktion beseitigt vermeidbare Zustands- und Belief-Brüche. **Sie garantiert trotzdem keine Nahtkosten von exakt null.** Ein korrekt definierter Hybrid kann strategisch schlechter sein als ein Elternteil. Null Kosten erfordern zusätzlich EV-/Sicherheitsbedingungen oder einen entsprechenden Nachweis.

---

# 3. Hybrid-Doktrin für `CLAUDE.md`

Die folgenden sieben Regeln würde ich verbindlich aufnehmen.

### 1. Bewertet wird die ausgeführte Gesamtpolitik

Eine Version umfasst Plan, Guards, Ranges, Routing, Fallbacks, Deadlines und Wiederaufnahme. Komponenten-Ergebnisse sind keine Release-Ergebnisse.

### 2. Öffentliches Gating ist der Standard, keine Gütegarantie

Öffentliches Gating erleichtert konsistente öffentliche Beliefs. Handabhängiges Gating ist nicht grundsätzlich verboten, muss aber als vollständige, für alle Hände definierte Strategie in Range-Rekonstruktion und Prüfung eingehen. Fehlerbedingte Support-Selektion ist kein gewünschtes Strategiemerkmal.

### 3. Ranges folgen den tatsächlich ausgeführten Aktionswahrscheinlichkeiten

Nach jedem eigenen strategischen Eingriff werden die eigenen Reaches aus der Gesamtpolitik fortgeschrieben. Kein stiller Wechsel zurück zu Basis-Reaches. Tatsächliche private Karten reparieren keine öffentliche Range.

### 4. Jeder Wechsel besitzt eine geschlossene Fortsetzung

Kein stilles Wiedereinsteigen in einen alten Plan nach abweichendem Prefix. Ein neuer Plan benötigt einen expliziten Zustands-, Belief- und Konsistenzübergang.

### 5. Kein unsichtbarer degradierter Fallback

Jeder Nicht-Plan-Pfad hat ein benanntes Ziel und einen eigenen Fehlergrund. „v5-Fallback“ darf nur heißen, dass die spezifizierte vollständige v5-Logik tatsächlich ausführbar ist. Range-korrigierte Fortsetzungen werden separat versioniert.

### 6. EVs dürfen nur bei gleichen Bedeutungen verglichen werden

Gleicher Zustand, gleiche Chip-Konvention, klar definierte Ranges und Fortsetzungen. Kein Maximum aus Solver-EVs unterschiedlicher Spiele bilden. Solver-Support und hohe Frequenzübereinstimmung ersetzen keinen Regret-Nachweis.

### 7. Freigabe prüft Auswahl und Nähte, nicht nur die Eltern

Gepaarte Tests der vollständigen Hybridpolitik gegen die produktive Referenz; gezielte Nahtfälle; unabhängige EV-Prüfung; BR im definierten Testspiel; Live-Bestätigung getrennt ausweisen. Alle Ergebnisse gelten nur für die getesteten Artefakte und Ausführungskanäle.

**Korrektur meiner früheren zugespitzten Kritik:** Handabhängigkeit allein ist kein Fehler — jede Pokerpolitik hängt von der Hand ab. Gefährlich ist eine handabhängige Zusammenfügung, deren Auswirkungen auf die Gesamtstrategie nicht modelliert und geprüft werden.

---

# 4. Fable als Live-Orchestrator

## 4.1 Die statistische Rechnung hat einen Einheitenfehler

Du schreibst:

> Per-Hand-SD ≈ 214 bb → SE = 214/√n bb/100.

Das passt nicht zusammen.

Für Handwerte \(X_i\) in bb gilt:

\[
\widehat m_{100}=100\,\overline X,
\qquad
SE(\widehat m_{100})
=
\frac{100\,SD(X)}{\sqrt n}.
\]

Falls **214 tatsächlich die SD je Hand in bb** ist, wäre der Koeffizient im bb/100-Standardfehler **21.400**, nicht 214.

Vermutlich meinst du:

> Der empirische SE-Koeffizient beträgt ungefähr \(c=214\) bb/100, also \(SE(n)\approx214/\sqrt n\).

Das entspräche einer Handwert-SD von 2,14 bb, etwa für entsprechend varianzreduzierte Handwerte. Diese Interpretation muss anhand eurer Logs bestätigt werden.

## 4.2 Unter der Annahme \(c=214\)

Rechnung mit Normalapproximation und vergleichbarer Varianz:

| Hände | SE in bb/100 | Ungefähre zweiseitige 95-%-Halbbreite |
|---:|---:|---:|
| 500 | 9,6 | 18,8 |
| 2.900 | 4,0 | 7,8 |
| 5.000 | 3,0 | 5,9 |
| 32.000 | 1,2 | 2,3 |

Damit gilt:

- **2.900 Hände liefern ungefähr SE=4**, nicht ein 95-%-Band von ±4.
- Für ein zweiseitiges 95-%-Band von ungefähr ±4 braucht ihr rechnerisch etwa **11.000 Hände**.
- Rund **31.000–32.000 Hände** passen zu einer einseitigen 95-%-Fehlerspanne von ungefähr zwei bb/100 gegenüber einer festen Schwelle.
- Das ist noch keine Testplanung mit beispielsweise 80 % Power. Für einen tatsächlichen Wert −6 gegen die feste Grenze −8 wären unter diesen Annahmen ungefähr **71.000 Hände** für einen einseitigen Test mit 80 % Power nötig.
- Beim Vergleich zweier geschätzter Arme zählt die Varianz der Differenz. Bei echter Paarung müsst ihr deren Koeffizienten messen; die Ein-Arm-Zahl ist dafür nicht ausreichend.

Das sind Modellrechnungen, keine Zusagen über eure tatsächliche AIVAT-Varianz.

## 4.3 Token- und Laufzeitrechnung

Unter der Annahme **25.000 Tokens je vollständiger Hand einschließlich aller Aufrufe**:

- 500 Hände: **12,5 Mio. Tokens**.
- 5.000 Hände: **125 Mio. Tokens**.

Bei ein bis drei Minuten je Hand ergeben sich rein rechnerisch:

- 500 Hände: etwa **8,3–25 Stunden**.
- 5.000 Hände: etwa **83–250 Stunden**.

Deine Größenordnung stimmt also, wenn die Annahmen stimmen. Sie ist aber kein guter Grund, diesen Messkanal zu verwenden. Außerdem entspricht diese Betriebsweise nicht mehr dem ursprünglichen kurzen Entscheidungsbudget — auch wenn der Harness inzwischen keinen harten Timeout setzt.

## 4.4 Rollenentscheidung: Diagnose ja, aber nicht bevorzugt durch neues Live-Spiel

**Ich stimme der Diagnose-Rolle zu. Ich würde nicht pauschal 300–500 zusätzliche Live-Hände mit Fable als handelndem Gehirn finanzieren.**

Der bessere erste Einsatz ist:

- reale geloggte Zustände;
- Shadow-Entscheidungen;
- gezielt ausgewählte Konflikt- und Nahtfälle;
- unabhängige anschließende Bewertung.

Neue Interaktion ist dann gerechtfertigt, wenn eine konkrete Hypothese über neu erzeugte Folgezustände anders nicht prüfbar ist.

„Beweis nur mit Engine allein“ ist richtig, **wenn Engine allein das Produkt ist**. Wenn Fable produktiv mitentscheidet, muss dagegen die Fable-plus-Engine-Politik selbst bewertet werden. Einen grundsätzlichen Ausschluss von LLMs aus empirischen Beweisen gibt es nicht; hier ist ihr Einsatz nur teuer und bislang nicht überzeugend begründet.

Die −28,55 des früheren Engine-LLM-Arms sind ein negativer Anker für diesen Ansatz. Die −8 bis −9 anderer Leaderboard-LLMs sind kein Beleg, dass ein zusätzlicher LLM-Selector euren Stack verbessert.

## 4.5 96 % Solver-Support sind kein ausreichender Stärkeindikator

Diese Zahl sagt nicht:

- ob die richtige Frequenz gewählt wurde;
- wie teuer die übrigen Entscheidungen waren;
- ob dieselben EVs und Ranges zugrunde lagen;
- ob eine alternative Aktion innerhalb des Supports deutlich besser gewesen wäre;
- ob die Fortsetzung konsistent war.

Ein Modell kann fast immer eine Aktion im Solver-Support wählen und trotzdem eine schlecht zusammengesetzte, exploitable Gesamtpolitik spielen.

## 4.6 Der wertvollste Lehrer-Datensatz

Nicht hauptsächlich „Hand, Entscheidung, schöne Begründung“.

Pro Fall speichern:

1. **Unveränderlichen vollständigen Informationszustand.**
2. **Versionierte Engine-Verteilungen**, nicht nur gewählte Aktionen.
3. **Beide Ranges und deren Herkunft.**
4. **Vergleichbarkeit der gezeigten EVs:** Solver, Baum, Skalierung, Fortsetzung.
5. **Fables konkrete Änderung:** Aktion beziehungsweise Verteilung und Größe.
6. **Falsifizierbare Begründung:** etwa falscher Blocker, falsche Calling-Range, inkonsistenter Prefix.
7. **Erwartete EV-Richtung und Unsicherheit.**
8. **Unabhängiges nachträgliches Urteil** und vollständige Fortsetzungsprüfung.

Fables Vorschlag wird vor der unabhängigen Bewertung festgehalten. Sonst entsteht nachträgliche Rationalisierung statt eines prüfbaren Lehrerbeitrags.

Der Bestand braucht:

- gezielt überrepräsentierte Konflikte und Nähte;
- zusätzlich einen zufälligen Kontrollanteil;
- Herkunfts- beziehungsweise Auswahlgewichte;
- einen unangetasteten Auditteil.

Das Ziel ist, wiederkehrende Fehler in **deterministische, testbare Engine-Verbesserungen** zu übersetzen. Nicht, Fables Stil zu imitieren.

## 4.7 Der wahrscheinlichste Spieler-Irrtum

Von deinen drei Kandidaten halte ich **Range-Blindheit in einer präziseren Form** für die wichtigste Gefahr:

> Du wählst für die tatsächliche Hand die überzeugendste lokale Aktion aus, obwohl die konkurrierenden Empfehlungen unterschiedliche Ranges und Fortsetzungen voraussetzen.

Dazu kommt die **Selektionsverzerrung durch verrauschte EVs**: Wer aus mehreren Schätzungen immer die attraktivste auswählt, selektiert auch deren positive Fehler.

Beispiele:

- Plan sagt Raise, TexasSolver sagt Call — aber nicht unter demselben Spiel.
- Du bevorzugst mit offensichtlichen Value-Händen die aggressive Engine und mit unklaren Händen die vorsichtige.
- Jede Einzelbegründung klingt vernünftig; die Gesamtstrategie verliert ihre Bluff-/Value-Balance.
- K1 kennt die tatsächliche Selektionswahrscheinlichkeit des LLM nicht und rekonstruiert anschließend erneut die falsche Range.

**Erklärungen sind keine Aktions-Likelihoods.**

Die Exploit-Versuchung ist gegen GTOW ebenfalls gefährlich und bei euch bereits negativ vorbelastet. Over-Checking kann ein Symptom sein, aber ich würde es nicht ohne Daten als Hauptfehler festlegen.

---

# 5. Wie der Hybrid selbst gemessen wird

## 5.1 Drei klar versionierte Kandidaten

Mindestens unterscheiden:

- **P:** vollständiges produktives v5.
- **H₀:** Plan plus unverändertes produktives v5 als Fallback.
- **H₁:** Plan plus ausführungs-konsistente Fallback-Fortsetzung.

Den nackten v10-Fallback braucht ihr als historische beziehungsweise gezielte negative Kontrolle, nicht als weiter zu optimierenden Champion.

## 5.2 Prüfstand: vollständige Politik, gemeinsames Spiel

Der Prüfstand muss:

- produktives v5 tatsächlich enthalten;
- reale Off-Tree-Größen im Referenzspiel zulassen;
- alle Raise-Fortsetzungen ausspielen;
- die Hybrid-Auswahl für alle Hände auswerten;
- Fallback und Planinvalidierung ausführen;
- tatsächlich verwendete Ranges übernehmen;
- keine günstigere Ersatzfortsetzung für den Plan unterstellen.

Eine exakte BR gegen den isolierten K2-Plan ist **keine exakte BR gegen H**.

Für Rechenfehler und Deadlines braucht ihr zusätzlich Ausführungstests beziehungsweise ein klar bezeichnetes Fehlermodell. Eine ideale strategische BR-Auswertung ohne Deadlinepfade bleibt eine Ideal-Auswertung.

## 5.3 Naht-Ablationen

Besonders aussagekräftig sind gepaarte Vergleiche:

- H₀ gegen nackten v10: Wirkung der Schutzreparatur.
- H₁ gegen H₀: Wirkung der ausführungs-konsistenten Beliefs.
- H₁ gegen P: eigentliche Produktfrage.

Gezielte Zustände:

- Plan-Check → Villain 0,5/0,66 Pot → Fallback.
- Plan-Bet → Off-Tree-Raise.
- Ursprünglich kleiner Pot → spätere Big-Pot-Entscheidung.
- Supportfehler.
- Deadline nach bereits ausgeführtem Plan-Prefix.
- Versuch eines Wiedereinstiegs in den alten Plan.

Die bekannten Verlustdecks müssen repariert werden, dürfen aber nicht den gesamten positiven Nachweis bilden.

## 5.4 Spiegel und Live

- **Spiegel:** prüft geschlossene Rollouts und neue Zustandsverteilungen gegen diesen Gegner; kein GTOW-Beweis.
- **Prüfstand:** prüft definierte strategische Eigenschaften im Referenzspiel.
- **Live:** prüft das eigentliche Gegnerleistungsziel.

Für „H besser als beide Eltern“ braucht ihr zwei entsprechende Vergleiche, einschließlich sauberer Unsicherheit. Ein günstiger Punktschätzer gegen einen Elternteil reicht nicht.

Wenn identische GTOW-Decks nicht verfügbar sind, verwendet randomisierte zeitlich gepaarte Blöcke und nennt das nicht Hand-für-Hand-Paarung.

---

# 6. Konkreter nächster Build und Abnahmetests

**Ja: v10.1 sollte der Hybrid werden — aber als ausdrücklich definierter H₁-Kandidat, nicht als behauptetes Maximum der Eltern.** H₀ ist ein notwendiger Zwischenstand der Reparatur.

## Schritt 1: Vollständigen v5-Fallback herstellen

Abnahme:

- Vor jeder ausgeführten Planaktion ist der Fallback im identischen Zustand distributionsgleich mit produktivem v5.
- Kein unbezeichneter nackter Basis-Pfad.
- Späte Pot-Eskalation aktiviert die aktuellen v5-Guards.
- Bekannte Verlustdecks laufen durch den vorgesehenen Schutzpfad.
- Fallback-Rechenbudget ist tatsächlich vorhanden.

## Schritt 2: K1-Support und tatsächlichen Policy-Pfad korrigieren

Abnahme:

- Die zuvor ausgeschlossenen erreichbaren Hände sind enthalten.
- Keine Reparatur durch Einfügen nur der tatsächlichen Hand.
- Range-Erzeugung verwendet tatsächliche Mischungs-/Wrapper-Regeln.
- Supportfehler werden als Defekt, nicht als normale Selektionsklasse gezählt.
- Planvalidierung ist soweit möglich unabhängig von der gerade gezogenen privaten Hand.

## Schritt 3: Prefix-Ledger und Range-Übergabe bauen

Das Ledger speichert genug, um die Wahrscheinlichkeit des ausgeführten Prefix für alle relevanten Hände zu rekonstruieren.

Abnahme:

- Kleine synthetische Bäume: Range-Rekonstruktion entspricht direkter Enumeration.
- Plan-/Fallback-Mischungen werden korrekt berücksichtigt.
- `v5_continuation` erhält die rekonstruierte eigene Range.
- Villain-Range und Off-Tree-Likelihood haben eine dokumentierte Herkunft.
- Keine Mutation durch Shadow- oder Gegenfaktik-Auswertung.

## Schritt 4: Fortsetzungs-Zustandsautomat schließen

Abnahme:

- Kein stiller Wiedereinstieg in einen ungültigen Plan.
- Kein veraltetes Threadresultat wird ausgeführt.
- Jede Entscheidung loggt Modus, Plan-ID, Range-Version und Wechselgrund.
- Erzwungene Deadline-, Off-Tree- und Eskalationsfälle enden in einer legalen, bezeichneten Fortsetzung.
- A/A enthält gezielt diese Zweige, nicht nur zufällige Deckabdeckung.

## Schritt 5: H₀/H₁/P im produktionsnahen Prüfstand vergleichen

Abnahme:

- Arm P ist wirklich produktives v5.
- Gemeinsames erweitertes Root-Spiel.
- Vollständige ausgeführte Hybridpolitik.
- Gepaarte Naht-Ablationen.
- BR-/Regret-Report mit klaren Einheiten und Geltungsbereich.
- Unverbrauchte Auditfälle zusätzlich zu den bekannten Fehlerdecks.

Das bestehende G3-TV-Ziel wird dabei nicht rückwirkend als bestanden erklärt. Für eine breitere strategische Freigabe bleiben messbare Policy-Parität und downstream Qualität erforderlich.

## Schritt 6: Shadow und begrenzter handelnder Smoke

Abnahme des technischen Smokes:

- Routing und Artefakte stimmen.
- Keine bekannten ungeschützten Pfade.
- Keine strukturellen Supportverletzungen.
- Planquote und Fallbackgründe sind vollständig erfasst.
- Alle Solverresultate gehören zum tatsächlich ausgeführten Zustand.

**Das ist eine technische Abnahme, keine Stärke-Taufe.**

Fable sollte dabei zunächst Schattenanalyst sein. Ein produktiver LLM-Arbiter wäre eine weitere neue Hybridpolitik und würde den gerade zu schließenden K1-/Closure-Vertrag wieder öffnen.

---

## Schlussfolgerung

Dem PO widerspreche ich in einem zentralen Punkt:

> **Der Hybrid ist nicht deshalb wahrscheinlich der beste Bot, weil er jeweils einen starken Elternteil benutzt. Er ist ein neuer Bot, dessen Auswahlregeln und Übergänge eigene Gewinne und eigene Fehler erzeugen.**

Die richtige positive Aussage lautet:

> **Ein geschlossener Hybrid ist euer sinnvollster nächster Kandidat, weil er den Plan testbar integriert, ohne bekannte v5-Schutzmechanismen absichtlich wegzuwerfen.**

Deine stärkste Rolle ist derzeit nicht, jede Hand überzeugender als die Engine zu kommentieren. Sie ist, **inkompatible Empfehlungen, falsche Beliefs und teure Übergangsfehler in falsifizierbare Tests und reproduzierbare Engine-Verbesserungen zu übersetzen.**