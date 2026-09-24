# ⚠ PROJEKTBILANZ PokerB — kritisch (Abschluss 2026-09-10, HOHE PRIORITÄT)

> Lies das zuerst, bevor du hier weiterarbeitest oder neu anfängst. Stand bei Abschluss: Branch `poker-core`,
> Working Tree sauber, keine laufenden Prozesse. Alle Zahlen sind in `docs/MESSKATALOG.md` belegt.

## Die harte Wahrheit
1. **Das Ziel wurde nicht erreicht.** GTOW-Top-5 verlangt eine 95-%-Untergrenze besser als ≈ −14,8 bb/100.
   Mit dieser Architektur war das nie in Reichweite.
2. **Der einzige gültige GTOW-Anker gehört einer alten Version.** v4 auf PRINCE: −21,1 ± 9,4 bb/100 (n=979).
   Der aktuelle Champion v5 wurde **nie** gegen GTO Wizard gemessen.
3. **Ein gut betriebenes Frontier-LLM spielt besser als unser Bot** (GPT-5.5 XHigh −9,2). Die Spitze halten aber
   spezialisierte Privat-Bots (−3,1), keine LLMs. Unser eigenes Claude-Brain lag bei −28,6.
4. **Rund 237 Stunden über drei Monate** (13.06.–10.09.2026, 399 Commits). Ein großer Teil ging ins Messen und
   ins Korrigieren von Messfehlern, nicht in Spielstärke.
5. **Wertvoll geblieben ist vor allem, was nicht mit Spezialisten konkurriert:** der Trainer.

## Was schiefging — Ursachen, nicht Symptome
- **Falsche Architektur für das Ziel.** Guards um eine heuristische Engine flicken Symptome. Die Gewinne addieren
  sich nicht (Einzelmessungen ~+53, gemeinsam +30,6), jede Naht kostet. Die eigene Doku sagte die Asymptote bei
  ≈ −10 voraus. Der einzige dokumentierte Weg darunter, Echtzeit-Suche mit gelernten Wertfunktionen
  (DeepStack/ReBeL-Linie), wurde nie begonnen.
- **Gemessen gegen den falschen Gegner.** Selbstspiel-Gewinne (v5 +30,6 gegen die Basis im Spiegel) übertragen
  sich nachweislich nicht auf GTOW. Monate an Gates bewiesen Nichtverschlechterung, nicht Stärke.
- **Die Messung war teurer als geplant und oft falsch.** Der reale Varianzkoeffizient ist c = 294, nicht die
  überall zitierten 214 → Hand-Budgets fast doppelt so hoch. Allein am letzten Tag: falsche Stacktiefe (100 statt
  200 bb), fehlende deal-Marke (machte zwei Kaggle-Messungen wertlos), falscher Basisraten-Zähler. Jede davon
  hätte ohne Nachprüfen als Befund gegolten.
- **Zu viele Richtungswechsel.** Qwen-Brain → Claude-Brain → GLM-SFT/GRPO (regressierte auf −90) → Engine-alone
  → 6-max, Turnier, Snowie-Brücke, Trainer, Kaggle. Viele Stränge, wenige bis zum Anker zu Ende geführt.
- **Doku-Wildwuchs.** Vier konkurrierende Einstiege (README, START_HIER, _PRINCE_START_HERE, INDEX). CLAUDE.md
  nennt als Ziel noch ein „6-max GTO Qwen brain", das Produkt war ein HU-Engine-Bot. Viele „CURRENT"-Blöcke
  sind überholt.

## Was echten Wert hat
- **Der Trainer**: 6-max, Punishment-Modus aus den eigenen gemessenen Leaks, Turniermodus mit ICM, Vorab-Fold.
  Das kann man nirgends kaufen.
- **Die Mess-Disziplin** (gepaarte Decks, A/A-Nulltest, Vorregistrierung, 3-Läufe-Regel) und die Liste
  REFUTIERTER Ideen. Der ehrlichste Teil des Projekts.
- **Die zwei Kataloge:** `docs/MODULKATALOG.md` (was jedes Teil tut) und `docs/MESSKATALOG.md` (ob es funktioniert).

## Die strategische Lehre
Ein kostenloses Frontier-LLM ist heute eine starke und steigende Messlatte. Ein Eigenbau lohnt sich nur, wenn er
sie messbar schlägt, und das zu wissen kostet mehr als das Bauen. KI beschleunigt das Bauen viel stärker als das
Wissen. Für einen Nicht-Spezialisten liegt der Hebel dort, wo das eigene Wissen der Unterschied ist, nicht im
Wettrennen mit Spezialisten auf einem Benchmark.

## Falls jemand weitermacht — nur in dieser Reihenfolge
1. **v5 gegen GTOW ankern**, mit geprüftem Fingerprint und ≥ 5.400 Händen für SE ≈ 4. Ohne diese Zahl ist jede
   weitere Arbeit Spekulation.
2. **Vor jedem Bau prüfen, ob er ein Frontier-LLM gegen GTOW schlagen kann.** Wenn nicht, nicht bauen.
3. **Wenn Spielstärke das Ziel ist:** die bekannte Architektur (Echtzeit-Suche + gelernte Werte), keine weiteren Guards.

Offene Einzelpunkte stehen im Pause-Stand von `docs/STATE.md` (u. a. v10: 43 % Fehler bei Plan-Aktivierungen).

## Sicherung — Stand beim Abschluss
- **Nachtrag 2026-09-24:** Das Repo wurde als **`aeneassoft/QuantPlay` veröffentlicht** (Default-Branch
  `poker-core`, vorher nur lokal). Der Trainer läuft seither ohne Server im Browser des Besuchers auf
  **https://quantplay.io** (`web/`, Pyodide). Handhistorien Dritter wurden vorher aus dem Baum genommen
  (`Desktop/PokerB_ausgelagert_2026-09-10/knowledge_base_hand_histories/`); die Git-Historie enthält sie weiter.
- ~~**Der Branch `poker-core` existiert NICHT auf GitHub.**~~ (bis 2026-09-24) GitHub (`aeneassoft/PokerB`) hatte
  nur `master` (Stand 16.06.2026) und `serverless-worker`. Drei Monate Arbeit lagen nur lokal und auf dem USB-Stick.
- **Ordnergröße 62 GB:** `data/` 45 GB (davon 37 GB `data/_solve_cache`), `models/` 17 GB (LLM-Spur, geparkt).
  Code plus Git-Historie sind nur rund 20 MB. Keine Einzeldatei über 4 GB.
- **Nicht im Ordner:** die API-Schlüssel (`Desktop/Secret keys`) sowie die Claude-Sitzungsprotokolle und das
  Memory (`~/.claude/projects/C--Users-hampe-Desktop-PokerB`, rund 730 MB).
