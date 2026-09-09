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
