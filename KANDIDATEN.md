# KANDIDATEN — was gebaut/geplant, aber nie am Anker gemessen ist (Stand 2026-09-10)

Kurznotiz, damit die Liste nicht wieder aus zehn Dateien zusammengesucht werden muss.
**Achtung: die Zahlen stehen auf VERSCHIEDENEN Achsen** (GTOW-AIVAT, Gym-Spiegel, Analyzer-EV-Loss) und
sind nicht direkt vergleichbar. Einziger echter GTOW-Anker bleibt **v4-auf-PRINCE −21,1** (Nacht 2).
Ziel-Massstab: Top 5 auf benchmark.gtowizard.com = **Untergrenze besser als ≈ −14,8** → es fehlen ~8 bb/100.

## Mit vorregistrierter Zahl

| # | Kandidat | Status | Notierte Erwartung | Quelle |
|---|---|---|---|---|
| 1 | **v9 / `r10_ernte`** (River-Raise-Ernte + Size-Praezision, Trigger 15 bb, fp16) | gebaut, A/A exakt 0 (576 Decks), Champion-Lauf bei ~13/48 Bloecken abgebrochen | **+3,6 bis +5,4 bb/100 GTOW-Achse**; Spiegel vorregistriert „NEUTRAL bis +8" | `data/autogym/journal.jsonl:100` |
| 2 | **v4-Pfad** (depth-limited CFR + neuronale Blaetter, EVPA, TurboReBeL) | nur geplant, nie begonnen | „ladder ≈ **−10 asymptote**, v4 = the way below −8" | `CLAUDE.md:169` |
| 3 | **Kanonische Flop-/Turn-Solve-Bibliothek** (1755 Suit-ISO-Flops) | nur geplant | zielt auf die **Flop-Blutung −6,4…−8,3** | `NOTES.md:647`, `docs/TIE_GTOW.md:19` |
| 4 | **v10 / `r10_stack`** (K1 Hero-Likelihood + K2 River-Plan) | gegated, **kein GTOW-Anker**, G3 verfehlt | Spiegel **+11,7 ± 10,9 NEUTRAL** (CI schliesst 0 ein) | `docs/STATE.md:84` |
| 5 | **v8-Play-Komponente** (`river_play_guard`) als GTOW-A/B | gebaut, nie am Anker | „+278,6 bb Replay, AIVAT-konvergent" — ausdruecklich unbewiesen | `docs/STATE.md:105` |
| 6 | **A7 `stackoff_bremse`** | gebaut, im Selfplay stumm (1 Trigger/400) | GTOW-Klasse D, **−13,8 bb je Zelle** | `docs/HU_OPTIMAL_KARTE.md:51` |

Fremd-Einordnung zu #1 (Astra): „Die registrierten +3,6 bis +5,4 bb/100 sind eine **Hypothese**. Selbst am
oberen Ende wuerde A1 allein bei einem tatsaechlichen v5-Wert unter −13,4 nicht fuer −8 reichen."
(`docs/TOP5_KONSULT_GPT6_2026-09-07.md:813`)

## Als Hebel markiert, ohne Zahl

* **Value-of-Computation-Arbiter** — Resolver-Budget nur wo es die Entscheidung kippt; notiert als „ONE
  buildable high-leverage lever" und „implementable core of the v4 path" (`CLAUDE.md:175`).
* **v10.1 = geschlossener Hybrid H0 → H1** (Astra Teil G). Warnung im Journal: „H ist ein NEUER Bot mit
  eigenen Naehten, **nicht Max(v5,v10)**" (`data/autogym/journal.jsonl:111`).
* **R1 CFV-Netz** (River-CFV fuer Turn-Suche) — „erstes substanzielles neues Netz"; R3 nur bei Bedarf.
* **Re-Solver-Proxy-Gegner im Gym (E1)** — „der einzige $0-Kanal, der A1/A2/C3 bepreisen kann".
* **`turn_wert`-SIZE-Entkopplung** (der 7/7-Tell) — „wichtigster Einzelfix" gegen die Seesaw-Verletzung.
* **Turn/River-Selektion** (`sel_turn`/`sel_all`) — das alte Ablehnungs-Verdikt ist per Konstruktion
  NICHTIG; die Sache ist **ungemessen, nicht refutiert** (`docs/STATE.md:255`).

## Nur „offen / Queue"

GTOW-Anker fuer v5 (Shadow-Nacht) · C1-A/B „GPU ersetzt TexasSolver-River" · Limp-Pot-DEFENSE ·
Bluff-Follow-Through- und Seesaw-Mixing-Guards · B1 Range-Struktur-Runde · v10-Re-Release (K2-Fallback auf
r8-Chirurgie statt nackter Basis, Off-Tree-Abbildung, K1-Support) · externer Analyzer-Anker fuer den neuen
6max-`tag` nach dem Flat-Fix.

## Naechster Schritt (User, 2026-09-10)

**v9 (`r10_ernte`) im Kaggle-Kanal messen** — der erste Referenzwert entsteht gerade.
Protokoll + Ergebnisse: [`docs/KAGGLE_ARENA.md`](docs/KAGGLE_ARENA.md).
