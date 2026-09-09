# Turnier-Modus des Trainers (MTT 60 Spieler) — Stand 2026-09-09

Der fünfte Modus des 6-max/Multiway-Trainers (`Poker Trainer.bat` → `/training`, Startbildschirm-Button
**Turnier**). Ein MTT mit **60 Spielern an 6 Tischen à 10 Sitzen**; der Mensch sitzt am **Hero-Tisch**
(voll gespielt: Engine `pokerbot/engine/table.py`, Liga-Bots, UI, Berater), die 5 Nebentische spielt der
**MTT-Direktor** (`pokerbot/arena/mtt.py`) vollautomatisch — **eine Hand je Nebentisch pro Hero-Hand**
(gleiche Turnieruhr). Kein Prince-Takeover (pargate6-refutiert, `docs/TRAINER_VERDRAHTUNG.md`), Reads AUS
wie im GTO-Modus.

## Struktur (Konstanten in `pokerbot/arena/mtt.py`)

| Konstante | Wert | Warum |
|---|---|---|
| `N_PLAYERS` / `SEATS_PER_TABLE` | 60 / 10 | Product-Owner-Vorgabe; 6 Tische |
| `START_STACK` | 5000 = 100 BB bei 25/50 | Vorgabe |
| `MTT_LEVELS` | 10 Level 25/50 → 800/1600, **Ante ab Level 3** (≈ BB/8 wie die PS-$1050-Leiter, `data/ps_tourney_field.json`: 0,13·BB) | Vorgabe |
| `HANDS_PER_LEVEL` | 12 (konfigurierbar `MTT(hands_per_level=…)`) | Level je Hände, nicht Minuten (Sim-Konvention aus `strategy/tournament.py`) |
| `LEVEL_EXTENSION_FACTOR` | 1,5 | nach Level 10 wächst der BB weiter → Terminierungs-Garantie |
| `PAYOUT_PCT_TOP9` | 27,8/18,9/13,3/10/7,8/6,7/5,6/5/4,9 % | Vorgabe 25/17/12/9/7/6/5/4,5/4,5 (= 90 %) auf 100 % normiert; `payouts()` legt den Rundungsrest auf Platz 1 → Summe EXAKT der Pool (`BUYIN` 10 × 60 = 600) |
| `EXACT_ICM_AT` | 12 | ab hier ist die Malmuth-Harville-Bitmask-DP (2^n) exakt bezahlbar (`research/mtt_sim.py`) |
| `BUBBLE_WINDOW_FACTOR` / `PRESSURE_CAP` / `PRESSURE_SLOPE` | 1,6 / 1,5 / 0,6 | Geld-Bubble-Fenster 9 < left ≤ 14: nur der Druck-Multiplikator (mtt_sim-Konstanten) |
| `ICM_HINT_BF` | 1,15 | Berater zeigt den ICM-Hinweis erst ab diesem Bubble-Faktor |

**Direktor-Mechanik** (übernommen aus `research/mtt_sim.py` + `Director` in `strategy/tournament.py`):
Eliminierung bei 0 Chips (kein Rebuy), **globale Platzvergabe** je Runde (Simultan-Busts: größerer
Start-Stack platziert höher — Sklansky-Regel), **Tisch-Kollaps** auf ⌈alive/10⌉ Tische (kleinster Tisch wird
aufgelöst, Spieler in die kürzesten Tische), **Balancing auf ±1** (Bewegung erst ab Differenz ≥ 2), Final
Table bei ≤ 10 Spielern, dann bis Heads-up. Zieht der Hero um, meldet die UI „Tischwechsel“ (der Hero sitzt
immer auf Sitz 0 — die Sitzreihenfolge bleibt durch Rotation erhalten). Button wandert über Namen.
**Determinismus:** ein Turnier-Seed (`/api/new_session {seed}`) steuert Sitzlosung, Profil-Verteilung,
jede Bot-RNG (`SixMaxBot(seed=…)`) und jedes Deck (Seed je Tisch-uid + Tisch-Handnummer).

## Population (`FIELD_MIX`, ein PRIOR — kein gemessener Fit)

station 30 % · tag 22 % · lag 15 % · nit 12 % · rock 8 % · whale 5 % · maniac 4 % · shark 4 % (Liga-Profile
aus `pokerbot/arena/sixmax.py`; größte-Reste-Rundung auf 59 Sitze, `field_counts`). Begründung: der gemine-te
PS-$1050-Pool (`data/ps_tourney_field.json`, 2.055 Hände; deep-Phase VPIP 31,7 / PFR 20,4 / 3bet 10,2 /
FoldVsRaise 53,6 %) ist loose-passiv (VPIP−PFR-Lücke 11 pp) → Stations+Whales 35 %, Regs-Kern 61 %, Maniacs
selten. Die gemessene Zwangs-Tightness unter Druck (FoldVsRaise 54→62 %, Jam 1,1→13,1 % short) erzeugen die
Bots selbst: ab ≤ 12 Verbliebenen bekommen ALLE Bots `obs['icm']` (exakte Stacks + Rest-Payouts →
`tournament.icm_scaled_req`, anteiliges Risiko-Premium = die μ-3-validierte Schicht), im Bubble-Fenster nur
den Druck-Multiplikator; davor Chip-EV. Profile tragen Avatare (`AVATARS`: 🐟 station, 🎯 tag, 🔥 lag,
🧊 nit, 🗿 rock, 🐳 whale, 🃏 maniac, 🦈 shark) — die UI zeigt sie am Sitz.

## Berater-Logik (`six_server.Session._tournament_advise`)

Nach jeder Hero-Aktion: Spot-Record (`coach/decision_log.capture_decision`) → Referenz-Oracle →
`oracle.oracle_diff` (Verb-Vergleich, bet/raise normalisiert):
* Tisch multiway: `SixMaxOracle` (tag-Kern, Reads leer, per-Spot-RNG) — dieselbe Referenz wie der Grader.
* Turnier heads-up (`table.n == 2`): `PrinceOracle(stack=auslese.FINAL_STACK, kanal='live')`.
* Urteil: **„GTO ✓“** oder **„Abweichung: <Aktion> [<bb>] — <rationale.reasoning>“**.
* **ICM-Hinweis** (vor der Aktion berechnet, `MTT.hero_icm`): nur wenn die exakte Rechnung bezahlbar ist
  (≤ 12 Verbliebene) und BF > 1,15 gegen den relevanten Gegner (`pick_villain`: Aggressor, sonst Coverstack):
  facing bet → „ICM: Call braucht +X pp Equity (r' statt r; Bubble-Faktor b vs Name)“ via
  `icm_scaled_req` (All-in-Calls exakt, sonst anteiliges Premium); sonst der Flip-Anker.
* Summenstatistik: Entscheidungen, GTO-Quote (HUD + Ergebnis), Top-3-Abweichungen — **Rang = Pot in bb**
  (Proxy für Kosten; ein EV-Verlust je Entscheidung ist ohne Solver nicht billig verfügbar — Grenze).
* Das bestehende Hand-Ende-Grading (`_grade_and_flush`, Feedback-Panel) läuft unverändert weiter.

## API

* `POST /api/new_session {mode:'tournament', seed?, step:true}` — Seed optional (None = zufällig).
* `POST /api/action`, `/api/step`, `/api/hand`, `GET /api/state` unverändert; `view()` liefert zusätzlich
  **`tournament`**: `level, sb, bb, ante, players_left, n_entries, rank, hero_stack_bb, avg_stack_bb,
  next_payout{place,amount}, hands_to_level, round_no, table_no, tables, final_table, table_change
  (einmalig), finished, place, payout, prize_pool, payouts[], side_ms, avatars{name→emoji},
  advisor{last{text,match,oracle,human,street,hand_no,icm}, stats{decisions,gto,gto_quote,top_deviations}}`.
* Nach `finished` liefert `/api/hand` keine neue Hand mehr (Hero ausgeschieden = Platz + Payout, oder Sieg);
  UI: Ergebnis-Overlay + „Turnier neu“. Alles in der Session — kein Server-Neustart.

## UI (`static/training.html`, minimal-invasiv)

Mode-Button **Turnier** + Beschreibung, Badge, **Turnier-HUD** im Panel (Level/Blinds/Ante, Spieler x/60,
Rang, Tisch x/y + FINAL-TABLE, Stack bb, Ø-Stack, nächste Payout-Stufe, Hände bis Level, GTO-Quote),
**Urteilszeile** unter dem HUD (+ ICM-Zeile, Log-Eintrag je neuem Urteil), Tischwechsel im Log/Ticker,
Final-Table-Banner, **Ergebnis-Overlay** (Platz, Payout, GTO-Quote, Top-3-Abweichungen, „Turnier neu“ /
„Zum Menü“). Sitzgeometrie jetzt dynamisch (`seatCoords(n)` aus six.html; n=6 bleibt byte-identisch zu den
alten Plätzen), Avatar-Farben auf 10 Sitze erweitert. Mobile-Tauglichkeit = die bestehende Stage-Skalierung.

## Messungen (2026-09-09, `python -m tests.test_tournament_mode`, 7 Tests)

* **Nebentische:** 5 Tische je Hero-Hand **mean 120–129 ms, max ≈ 200–213 ms** (volles Feld, 20 Runden) —
  unter dem 300-ms-Ziel → `side_tables_every = 1` (jede Hero-Hand). Fallback-Knopf für langsamere Rechner:
  `MTT.side_tables_every = 2` (dokumentiert, nicht aktiv).
* **Bots-only bis zum Sieger (Seed 7, Audit jede Runde):** 131 Runden, 38,8–40,1 s; Chip-Erhaltung
  60·5000 nach jeder Runde, jeder Platz 1..60 genau einmal, Balance ±1, kein Tisch < 2 außer Final.
* **Determinismus:** Seed 11 zweimal → identisch (Sieger, Plätze, Runden); Seed 12 ≠ Seed 11.
* **Server-Smoke:** new_session → 30 Hero-Aktionen (Call/Check/Fold) → jedes Mal ein Urteil; GTO-Quote 0,50
  (Passiv-Skript, kein Spielurteil); Chip-Erhaltung über alle Tische.
* Vorbestehend, nicht Turnier-bedingt: „Trainer-Grading > 800 ms (Hand 1)“ ohne `main()`-Prewarm (auch im
  GTO-Modus 6-max reproduziert).

## Browser-Verifikation (2026-09-09, Trainer :8011, Turnier-Button → Hand gespielt)

* 10 Sitze mit Profil-Avataren, Badge TOURNAMENT, Verlauf zeigt je Hero-Aktion das Urteil (`✓ GTO ✓` bzw.
  `△ Abweichung: Call — Continue 66 vs 3bet (Top 24%)`), keine Konsolenfehler.
* **Zwei Fehler dabei gefunden + behoben:** (1) HUD und Urteil-Feld waren gerendert, aber unsichtbar —
  `style.display=''` löscht nur den Inline-Stil, die CSS-Regel `#thud{display:none}` blieb wirksam → jetzt
  `display='block'`. (2) Tischnummer zeigte „Tisch 11/6": die `TableHost`-uid war der Namens-Offset
  (0/10/20…), nicht der Tisch-Index → `i // seats_per_table` (verschiebt die Deck-Seeds der Tische; alle 7
  Tests danach grün, Chip-Erhaltung und Determinismus unverändert).

## Nachtrag (2026-09-09, User-QA) — der Hand-Kontinuitäts-Bug

**Befund des Users:** „immer 100 bb pro Spieler", „immer gut gespielt", einmal ein leerer Tisch.
**Ursache (reproduziert per TestClient):** jede Turnierhand ist eine frische `Table` (hand_no 0 → 1);
`_log_if_done` prüft `t.hand_no != logged_hand` und hielt deshalb JEDE Hand nach der ersten für schon geloggt →
keine Stack-Rückgabe ans Feld (`after_table_hand`), keine Busts, keine Turnieruhr, kein neues Feedback: alle
Hände starteten wieder von den Stacks nach Hand 1, das Banner zeigte das Hand-1-Urteil. **Fix:** die neue Table
übernimmt die Handnummer der alten (`_tournament_prepare`). **Regression:** `test_hand_continuity` (3 Hände:
hand_no/hands_done/logged_hand laufen mit, Feedback gehört zur aktuellen Hand, Hero-Stack fließt zurück, Uhr +3).
**Nachmessung:** zwei volle Turniere per TestClient (Seeds 3/11, Zufalls-Hero): Hände 6 bzw. 31, Feedback folgt
der Hand, Busts/Platz korrekt (Platz = Verbliebene zum Bust-Zeitpunkt), Urteile gemischt (Seed 11: 38 GTO ✓ /
41 Abweichung); Browser-Schnelllauf über >3 Turniere, 3.671 Renders: 0 leere Tische, 0 Konsolenfehler.
**Leerer Tisch — GEFUNDEN + BEHOBEN (zweiter User-Screenshot: „Hand #undefined · Pot NaNbb", Netto „NaN"):**
Turnier-Blinds sind 50/75/150 … Chips; das Viertel-bb-Raster des Bet-Sliders ergibt dann z. B. 3,75 bb =
187,5 Chips → `ActionReq.amount: int` → FastAPI-422 `{"detail": …}` → die Antwort hatte keinen `error`-Schlüssel
→ der Client renderte sie als Spielzustand: Sitze entfernt, `v.seats.forEach` warf, Board blieb stehen. Im
Cash-Trainer (bb 100, Raster 25) trat das nie auf. **Fix (3 Schichten):** Server `amount: float` + Rundung auf
ganze Chips; Client `api()` macht jede Nicht-OK-/Nicht-Zustands-Antwort zu `{error}`; `render()` rendert nie
ohne `seats`; `send()` rundet den Betrag. Regression `test_fractional_amount_is_rounded` (212,5 → 212, Antwort
ist ein Zustand); Browser: provozierte 422 → Fehlerzeile, 10 Sitze bleiben; 112,5 Chips → 113 gesetzt.
**Beobachtung Feldtempo:** 60 → ~30 Spieler in ~25 Runden (Maniacs/Whales gehen bei 100 bb früh all-in) — für
eine Trainingssitzung praktisch (Geld in ~30–50 Händen), aber schneller als ein echtes Online-MTT.

## Grenzen

* ICM exakt erst ab ≤ 12 Verbliebenen; davor nur das Bubble-Fenster-Heuristik-Druckfeld, kein BF-Hinweis
  (bei 60 Spielern liegt die Geld-Bubble bei 10 → exakt abgedeckt).
* Top-3-Abweichungen nach Pot-Größe, nicht nach EV-Verlust; die Referenz ist der tag-Kern (85,9 % GTO-Score
  im Analyzer), kein Solver.
* Level-Uhr zählt Hero-Hände; Nebentische spielen synchron eine Hand — keine Zeit-Level, kein Dead-Button.
* Feld-Mix ist ein begründeter Prior; eine Kalibrierung auf gemessene Bot-VPIP/FvR je Profil steht aus.
