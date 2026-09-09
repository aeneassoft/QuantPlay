# Trainer-Verdrahtung — Ist-Stand nach dem Bau vom 2026-09-09

Welcher Bot spielt in welchem Modus mit welcher Kette, welchem Exploit-Schalter und welchem Resolver.
Quellen: `pokerbot/web/server.py` (HU-App), `pokerbot/web/six_server.py` (6-max-Trainer), `pokerbot/coach/oracle.py`
(`PrinceOracle(stack=, kanal=)`), `pokerbot/arena/hybrid.py` (`HybridHero`), `pokerbot/strategy/auslese.py`.

| Modus / Kanal | Bot | Stack (AUSLESE-Kette) | Exploit | Resolver (River/Turn) | Nachweis |
|---|---|---|---|---|---|
| HU-App Gegner (`server.py`, `POKERB_AUSLESE=1` Default) | `PokerBot` + PRINCE-Profil | `FINAL_STACK` = `r8_stack`, kanal `live` | AUS | AN (TexasSolver; `POKERB_RESOLVER=0` schaltet ab) | `/api/view` → `fingerprints.bot` |
| HU-App **Berater** für den Menschen (`server.py`, NEU) | `PokerBot` (Sitz des Menschen), **identische Konfig** | `r8_stack`, kanal `live` | AUS | AN | `fingerprints.advisor` — Smoke: Hash `fbb88ac7ffe4` == Gegner; `GET /api/advice` |
| HU-App mit `POKERB_AUSLESE=0` (Debug) | nackter `PokerBot` | `basis` | AN (Konstruktor) | AUS | Fingerprint `stack='basis'` |
| 6-max-Trainer GTO-Modus, multiway (`six_server`) | `SixMaxBot`-Liga, Reads AUS | — | AUS | — | `Session.bots` |
| 6-max-Trainer GTO-Modus, Pot heads-up Hero-vs-Bot (Takeover) | `PrinceOracle` (Prince v2.2 + Positions-Prior-Tracker) | **`FINAL_STACK` (`r8_stack`), kanal `live`** — Env `POKERB_SIX_STACK` (`r10_stack` / `basis`) | AUS | AUS (Antwortzeit; unverändert) | Smoke: `SESSION.prince.stack == 'r8_stack'`, Override `basis`→None, `r10_stack` |
| 6-max-Trainer Exploit-/Arena-/Punish-Modus | `SixMaxBot`-Liga, Reads AN | — | Liga-Reads (bounded) | — | kein Prince |
| Analyzer-Export `research/sixmax_export.py --hybrid` | `HybridHero` (tag-Kern + Prince, **ohne Stack** = wie bisher) | keiner (Default `stack=None`) | AUS | AUS | byte-identisch zum Stand vor dem Move (plain 4550 B, hybrid 3550 B, n=4/3) |
| `pargate6` Kandidaten | `tag` (Reads AUS) / `tag_reads` / `hybrid` / `hybrid_r8` / `hybrid_r10` | — / — / None / `r8_stack` / `r10_stack`, kanal `gym` | AUS (Reads nur `tag_reads`) | AUS | `result.json` `zaehler.prince_decisions`, `aa_exakt_null` |
| `exploit_gate` HU-Arme | `PokerBot` **ohne PRINCE** (`POKERB_PRINCE=0`), Projektion wie Grader | `basis` | ON / OFF explizit je Arm (`POKERB_EXPLOIT`) | AUS | `fingerprints.exploit_on.exploit=True` / `exploit_off.exploit=False`, `prince=False` |

Prince-Takeover im Trainer: `kanal='live'` (K2-Deadline/os.urandom nur für `r10_stack`); für `r8_stack` ist der
Kanal wirkungslos. Die AUSLESE-Import-Flags (`TURN_DEFENSE 0.07`, `SLOWPLAY 0.25`) setzt `server.py` per
`setze_env`; der 6-max-Launcher setzt sie NICHT — `oracle.py` setzt nur `POKERB_PRINCE=1`. Wer den Takeover mit der
vollen v5-Env will, setzt sie im Launcher (`PokerB 6max spielen.bat`) — offener Punkt, bewusst nicht still geändert.

## Messungen (Kommandos)

A/A-Nulltest ist Pflicht VOR jeder Reihe (Smoke 24 Decks lief: `bb100 0.0, se 0.0, nonzero 0, aa_exakt_null True`).

**1. 6-max-Kandidatenvergleich, 3000 Decks je Kandidat vs `tag` (eine Flotte zur Zeit; ~2 s/Deck/Arm single-core):**
```powershell
python -m pokerbot.autogym.pargate6 --kandidat tag       --incumbent tag --decks 300  --workers 8   # A/A muss exakt 0
python -m pokerbot.autogym.pargate6 --kandidat hybrid    --incumbent tag --decks 3000 --workers 8
python -m pokerbot.autogym.pargate6 --kandidat hybrid_r8 --incumbent tag --decks 3000 --workers 8
python -m pokerbot.autogym.pargate6 --kandidat hybrid_r10 --incumbent tag --decks 3000 --workers 8
```
Ergebnis: `data/runs/<ts>_pargate6_<kand>/result.json` (bb100 = gepaarte Differenz über 6 Rotationen je Deck,
`bb100_kandidat`/`bb100_incumbent` = je Arm vs Liga, `ci95_*`, `verdict` via `stats.verdikt`). Gleiche `--workers`
je Vergleich (Villain-OppModels lernen je Job-Block).

**2. Exploit-Gate, 600 Decks je Profil (+ 6-max Reads ON/OFF):**
```powershell
python -m pokerbot.autogym.exploit_gate --decks 600 --workers 8 --sixmax
```
Kriterium vorregistriert in `exploit_gate.py`: station/maniac/nit/whale Diff ≥ 0 und CI-Untergrenze > −3;
tag/shark nicht signifikant negativ. Smoke (56 Decks, station/tag): station +52,1 ± 53,6 CI[−4,4, 160,7] →
bei dieser n formal VERLETZT (CI zu breit), tag +55,8 ± 53,6 korrekt — Zahlen ohne Aussagekraft, Mechanik bewiesen.

**3. Analyzer-Export --hybrid n=1500 (NUR das Kommando; Hand-IDs verbrennen beim ersten Kontakt — Ledger
`data/runs/v10/g5_analyzer_ledger.json`, nächster Vorschlag 132000 / Tag 91 / Seed 1110 laut STATE.md):**
```powershell
$env:POKERB_PRINCE="1"; python -m research.sixmax_export --hybrid --n 1500 --seed 1110 --idbase 132000 --dayoffset 91 --out data/gtow_upload/sixmax_hybrid_1500.txt
```
(CRLF-Pflicht vor dem Upload; danach Ledger-Eintrag in STATE.md.)

## MESSERGEBNISSE (2026-09-09, Logs data/runs/verdrahtung/, Run-Ablagen data/runs/*_pargate6_*)

**6-max-Kandidaten (pargate6, Hero rotiert über 6 Sitze je Deck, Liga tag/lag/nit/station/maniac geseedet, 8 Worker)**

| Kandidat vs Incumbent | Decks | bb/100 | CI95 | Verdikt |
|---|---|---|---|---|
| tag vs tag (A/A) | 288 | 0,0 ± 0,0 | — | exakt 0 |
| hybrid (tag + Prince-Takeover, ohne Kette) vs tag | 2992 | −23,56 ± 9,02 | [−40,8; −5,3] | VERWERFEN |
| hybrid_r8 (Takeover mit r8_stack) vs tag | 2992 | −21,73 ± 9,01 | [−39,0; −4,4] | VERWERFEN |
| hybrid_r10 (Takeover mit r10_stack) vs tag | 2992 | −26,61 ± 8,93 | [−43,9; −9,4] | VERWERFEN |
| hybrid_r8 vs hybrid | 2992 | +1,82 ± 5,58 | — | NEUTRAL |

**Verdikt:** Der Prince-Takeover (HU-Projektion des PokerBot in HU-kollabierten 6-max-Pötten) schadet im
6-max-Kanal; die Guard-Kette rettet ihn nicht. Bester gemessener 6-max-Bot = Liga-Kern `tag`. Einschränkung:
Selbst-Ökologie (tag spielt gegen seine eigene Liga). Externer Anker = Analyzer-Grade (tag-Kern 85,9 % / 7,61;
Hybrid nie gegradet) → Export-Kommando oben. **Produktentscheid:** `six_server` GTO-Modus spielt den Liga-Kern;
Takeover nur mit `POKERB_SIX_TAKEOVER=1`.

**Exploit-Gate (HU, PokerBot ohne PRINCE, POKERB_EXPLOIT=1 vs 0 je Arm im frischen Prozess, Fingerprint bestätigt,
600 gepaarte Decks je Profil)**

| Profil | ON | OFF | Diff ON−OFF | CI95 |
|---|---|---|---|---|
| nit | +24,95 | +27,04 | −2,09 ± 9,52 | [−21,0; +15,9] |
| tag | −3,43 | +15,83 | −19,26 ± 15,35 | [−51,2; +8,2] |
| lag | −4,84 | +13,66 | −18,50 ± 12,96 | [−47,7; +3,6] |
| station | −11,62 | +5,73 | −17,35 ± 16,31 | [−51,8; +12,9] |
| maniac | −14,80 | +0,95 | −15,74 ± 9,61 | [−35,8; +2,5] |
| rock | +20,35 | +20,66 | −0,31 ± 8,97 | [−18,4; +16,9] |
| whale | −9,57 | −1,32 | −8,26 ± 17,01 | [−43,1; +23,5] |
| shark | +3,14 | +17,54 | −14,40 ± 13,67 | [−42,5; +9,6] |
| 6-max Reads ON vs OFF (pargate6) | +22,77 | +19,14 | +3,64 ± 13,45 | [−22,0; +30,9] |

**Verdikt:** Alle acht HU-Punktschätzer ≤ 0, gepoolt ≈ −12 bb/100 (SE ≈ 4,5): der Dirichlet-River-Exploit
(`bot.py:_river_exploit`) verliert gegen jedes Liga-Profil, auch gegen die ausbeutbaren. „Exploit-Modus korrekt"
ist damit nicht belegt, sondern für diesen Pfad refutiert (konsistent mit PRINCE = exploit OFF und dem GTOW-
Befund). 6-max-Reads sind neutral (harmlos). **Produktentscheid:** Exploit bleibt in allen Modi AUS; der
`six_server`-Modus „exploit" (Reads) bleibt als Spielgefühl-Variante. Ein echter Exploit bräuchte einen neuen
Mechanismus (Selektion statt Frequenz, mehr als River-only) mit diesem Gate als Abnahme.


## Vorab-Fold (User, 2026-09-09) — mehr Hände pro Stunde

**Was:** Solange die Gegner vor dir handeln, zeigt der Wartebalken links „Fold vorab" (Taste F). Ein Klick
setzt `POST /api/prefold`: der Server spielt die Hand SOFORT im Hintergrund zu Ende — Bots handeln, der Hero
foldet an seiner Stelle regulär über `human_action("fold")` (Decision-Capture, Benotung, Turnier-Urteil wie ein
normaler Fold), die Chips wandern korrekt. Der Client zeigt nur das Ergebnis (Board, Gewinner, Protokoll) und
deckt die nächste Hand nach 1,5 s automatisch aus (`T.PREFOLD_NEXT`).
**Sonderfälle:** kommt kein Einsatz beim Hero an (Check frei, z. B. BB ohne Raise), wird der Vorab-Fold
aufgehoben und der Hero ist normal dran (`prefold: "check_frei"`) — ein Fold statt Gratis-Check wäre reiner
EV-Verlust; folden alle vor ihm, gewinnt er kampflos (`"kampflos"`). Doppel-Vorab-Fold → 400.
**Klick-Rennen / Layout (User-QA):** der Vorab-Fold IST der Fold-Button (gleiches `mk('Fold',…)`, Klasse
`fold`, Beschriftung „Fold") und sitzt PIXELGLEICH an der Stelle des echten Fold-Buttons. Layout der Reihe
(`btnRow`): zwei Hälften je 50 % — links [Fold][Check/Call] rechtsbündig, rechts [Raise][All-in] linksbündig —
so liegt die Mitte zwischen Call und Raise EXAKT unter der Mitte der Hero-Karten (gemessen: beide x 384);
fehlende Buttons werden unsichtbare Platzhalter (`.ph`, min-width 200), der Wartebalken trägt die Größenzeile
als Platzhalter mit dem Wartetext (Fold in beiden Zuständen x 161,1 / y 490,5). Zusätzlich ist die Aktionsleiste beim Wechsel Warten →
„du bist dran" 350 ms gesperrt (`.bar.lock`, `T.TURN_LOCK`) — beim ersten Browser-Test landete ein verspäteter
Klick sonst auf „Raise" (27 bb mit 32s). Der Verlaufs-Ticker steht jetzt UNTER der Aktionsleiste (überlagerte
vorher den Hero-Sitz bei 10 Sitzen).
**Tests:** `python -m tests.test_prefold` (Chip-Erhaltung, Hero gefoldet + Hand vorbei in einem Aufruf, Fold als
benotete Entscheidung, Doppel-Fold abgewiesen, Turnier-Urteil, Sonderfälle). Gilt für alle Modi des 6-max-
Trainers (`training.html`); die HU-App (`server.py`) hat keinen Vorab-Fold.
