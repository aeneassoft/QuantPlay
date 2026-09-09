# Kaggle Game Arena — „Heads Up Poker" als Messkanal (2026-09-10)

Leaderboard: <https://www.kaggle.com/benchmarks/kaggle/poker-heads-up> · Bruecke:
[`pokerbot/benchmark/kaggle_arena.py`](../pokerbot/benchmark/kaggle_arena.py) · Tests: `python -m tests.test_kaggle_arena`

## Was das ist

Kaggle Game Arena laesst **Frontier-LLMs** gegeneinander Heads-Up No-Limit Hold'em spielen und bewertet sie
mit **Mean BB/100** (All-play-all im LLM-Feld, kein Solver-Gegner). Deshalb sind die Zahlen — anders als beim
GTOW-Leaderboard, wo alle negativ sind — grossteils POSITIV: sie messen relativ zum Feld, nicht gegen GTO.

**Leaderboard v1 (abgerufen 2026-09-10 ueber die Kaggle-API, Mean BB/100):**

| Rang | Modell | BB/100 | | Rang | Modell | BB/100 |
|---|---|---|---|---|---|---|
| 1 | GPT-5.6 Sol | +34,9 ± 5,1 | | 15 | GPT-5.4 mini | −0,4 |
| 2 | GPT-5.5 | +32,5 ± 6,0 | | 19 | Claude Opus 4.8 | −3,4 |
| 3 | Claude Fable 5.1 | +29,7 ± 6,0 | | 23 | DeepSeek V3.2 | −11,8 |
| 4 | Claude Opus 5 | +15,8 ± 5,9 | | 26 | Claude Sonnet 4.6 | −17,3 |
| 5 | GPT-5.6 Terra | +11,6 ± 5,5 | | 29 | GPT-5 mini | −49,3 |

Kosten der Spitzenplaetze: 12.000–19.000 Token je Zug, bis 26 ct/Zug — ein Grund, warum ein Engine-Bot hier
strukturell im Vorteil waere (unsere Entscheidung kostet 0 ct und ~0,1–0,3 s).

## Die Spielkonfiguration (exakt, aus der Umgebung selbst gelesen)

```
python_repeated_pokerkit(max_num_hands=100, reset_stacks=True, rotate_dealer=True,
  pokerkit_game_params=python_pokerkit_wrapper(blinds=1 2, num_players=2,
                                               stack_sizes=200 200, variant=NoLimitTexasHoldem))
```

* HUNL, Blinds 1/2 Einheiten, Stacks 200 Einheiten = **100 bb**. Der Test `test_spielkonfiguration` haelt
  den Wert fest.
* **KORREKTUR (2026-09-10, Befund gpt-5.6-sol, am Code bestaetigt): 100 bb ist NICHT unsere Wettbewerbstiefe.**
  Der GTOW-Benchmark laeuft auf **200 bb** (`starting_stack 20000`, Blinds [100,50] —
  `pokerbot/benchmark/gtowizard.py:98`, `:281`), und unser Preflop-Blueprint feuert erst **ab 140 bb
  effektiv** (`pokerbot/strategy/bot.py:200`: „blueprint is solved at 200bb -> only fire when genuinely
  deep (GTOW = 200bb)"). Bei 100 bb spielt also die **Heuristik-Kaskade** statt der near-Nash-Politik:
  der Kaggle-Kanal misst einen ANDEREN Bot als der Wettbewerbskanal. Die frueher hier stehende Behauptung
  „genau unsere Hausgroesse" war falsch.
  **Konsequenz:** `--stack-bb 100` repliziert Kaggle, `--stack-bb 200` misst die Wettbewerbstiefe. Nur der
  zweite Modus ist als billiger Vorfilter fuer GTOW-Kandidaten brauchbar; der erste dient der Kaggle-Frage.
* Stacks werden **je Hand zurueckgesetzt**, der Dealer rotiert, ein Match sind **100 Haende**.
* Aktionen: `0` = Fold, `1` = Check/Call, `N` = Bet/Raise **TO** N Einheiten (bis 200 = All-in).

## Die Bruecke

`pokerbot/benchmark/kaggle_arena.py` steckt unseren Champion (PRINCE-Profil, exploit AUS, Resolver AN,
AUSLESE-Kette `FINAL_STACK`) in genau dieses Spiel:

* `parse_beobachtung()` liest die `observation_string` des Wrappers (Strasse, Bets, Stacks, Board, Hole).
* `zustand()` baut daraus unseren Engine-Zustand (Held immer Index 0, wie im GTOW-Adapter), Einheiten × 50 = Chips.
* `spiel_aktion()` bildet `{action, amount}` auf eine OpenSpiel-Aktion ab, mit **Legalitaets-Garantie**.
* `duell()` misst **gepaart**: jedes Deck zweimal mit getauschten Sitzen, Verdikt ueber `stats.verdikt`.

**Zwei Mess-Fallen, beide gemessen und behoben:**

1. **hand_id je Haelfte** zerstoerte die private Randomisierung → dieselbe Falle wie in v10; jetzt ist die
   `hand_id` deck-weit identisch.
2. **RNG-Strom ueber Haende**: unser Bot mischt (Seesaw-Doktrin) aus einem fortlaufenden Strom. Mit
   wiederverwendeten Agenten liefen die Spiegelhaelften auseinander — **A/A war −37,5 bb/100 statt 0**
   (8 Decks). Fix: je Haelfte frische Instanzen → **A/A exakt 0** (`nonzero 0`, SE 0).

## Ist das schneller als GTOW?

Ja, um Groessenordnungen — aber es misst etwas anderes.

| | GTOW-API | Kaggle-Umgebung lokal |
|---|---|---|
| Kosten je Hand | Hand-Budget + Zeitfenster | 0 |
| Durchsatz | ~2.500 Haende in 8–9 h (seriell) | ~0,3–18 s/Hand je nach Resolver, parallelisierbar über alle Kerne |
| Gegner | Ruse-Re-Solver (nahe GTO) | im offiziellen Lauf: LLMs |
| Taugt als GTO-Anker | **ja** | **nein** |

**Ehrliche Einordnung:** die Umgebung ist ein billiger Volumen-Kanal und ein potenzielles Schaufenster, aber
kein Ersatz fuer den GTOW-Anker. Ein LLM-Feld, das untereinander +35 bis −49 bb/100 streut, sagt nichts
darueber, wie weit wir von GTO entfernt sind. Wer hier gewinnt, hat LLMs geschlagen, nicht den Solver.

## Offen: koennen wir wirklich antreten?

Die Leaderboard-Zeilen sind Kaggle-**Modelle** (`modelVersionSlug`), das Feld besteht ausschliesslich aus
LLMs der Labore. Ob Kaggle einen Nicht-LLM-Agenten in genau dieses Benchmark-Leaderboard aufnimmt, ist aus
den oeffentlich lesbaren Seiten NICHT belegt — die Kaggle-Seiten rendern per JavaScript und liefern ueber
`WebFetch` nur den Titel. Der vorhandene KGAT-Token (`Secret keys\Kaggle API.txt`, nur aus der Datei gelesen)
oeffnet die Benchmark-API lesend; ein Submit-Endpunkt fuer Agenten ist damit nicht nachgewiesen.
**Naechster Schritt fuer eine echte Teilnahme:** die Game-Arena-Regeln/FAQ im Browser lesen (nicht per Fetch)
und pruefen, ob es eine Agenten-Einreichung ausserhalb des Modell-Feldes gibt.

## Kommandos

```bash
python -m pokerbot.benchmark.kaggle_arena --aa --decks 8            # Nulltest (muss exakt 0 sein)
python -m pokerbot.benchmark.kaggle_arena --gegner basis --decks 300
python -m tests.test_kaggle_arena
```

Abhaengigkeiten (neu, nur fuer diesen Kanal): `pip install open_spiel kaggle-environments` — fuer Python 3.12
existiert ein Windows-Wheel, die Umgebung laeuft also ohne WSL.


## Eichung Kaggle -> GTOW (User-Idee 2026-09-10): SCHWACH, nicht benutzbar

Sechs Modelle stehen auf BEIDEN Ranglisten. Regression GTOW-AIVAT auf Kaggle-BB/100:

| Modell | Kaggle BB/100 | GTOW bb/100 |
|---|---|---|
| GPT-5.6 Sol | +34,9 | −15,4 |
| GPT-5.5 | +32,5 | −9,2 |
| Grok 4 | +10,5 | −60,0 |
| GPT-5.4 | +3,6 | −17,8 |
| Claude Opus 4.6 | +1,6 | −20,4 |
| Gemini 3.1 Pro | −13,0 | −30,8 |

* **Alle sechs: r = 0,37, R² = 0,14, Residual-SD 15,5 bb/100** — als Umrechnung wertlos.
* Ohne Grok 4 (Residuum −34): r = 0,88, R² = 0,77, Residual-SD 3,4, `GTOW ≈ 0,334 · Kaggle − 22,7`.
  Einen Punkt zu streichen, WEIL er widerspricht, ist aber keine Eichung, sondern Kurvenanpassung.
* Zusaetzlich: die Reasoning-Stufen unterscheiden sich (GTOW listet „XHigh Reasoning"-Varianten), die
  Paarungen sind also nicht einmal dieselbe Konfiguration; und jede Vorhersage ueber +35 Kaggle hinaus
  waere Extrapolation ausserhalb der Datenspanne.

**Fazit: die Umrechnung traegt kein Verdikt.** Sie wird auch nicht gebraucht — siehe unten.

## Der eigentliche Befund: GTOW nimmt EIGENE Agenten (und wir stehen schon drauf)

<https://benchmark.gtowizard.com/> hat einen Knopf „Evaluate Your Model"; die Spitze besteht aus
Privat-Agenten, nicht aus LLMs. Stand 2026-09-10 (83 Eintraege, Rang nach der UNTERGRENZE des
95-%-Intervalls — Haende zaehlen also so viel wie der Mittelwert):

| Rang | Agent | bb/100 | SD | Haende |
|---|---|---|---|---|
| 1 | Bitcrumbs (Individual) | −3,1 | 0,9 | 52.005 |
| 2 | Trainer (SL) | −6,2 | 0,7 | 102.251 |
| 3 | Roman_SL (Individual) | −7,4 | 0,6 | 137.576 |
| 4 | tangtang's agent | −12,6 | 0,5 | 269.559 |
| 5 | GPT-5.5 (XHigh) | −9,2 | 2,8 | 5.000 |
| … | | | | |
| 31 | **Quantplay (Hampe)** | **−30,4** | 3,5 | 6.587 |
| 33 | **Quantplay v8 (Hampe)** | **−31,6** | 3,5 | 6.946 |
| 47 | **Experimental Poker Bot (Hampe)** | **−51,7** | 2,1 | 30.596 |

Unsere drei Eintraege stammen aus der v8-Ära; der heutige Champion (~−21 gemessen, Nacht 2) ist NIE
gepostet worden. **Top-5 heisst konkret: Untergrenze besser als ≈ −14,8** (Platz 5), also Mittelwert
≈ −11 bei ~10.000 Haenden oder ≈ −13 bei ~50.000 Haenden. Gegenueber dem heutigen Stand fehlen ~8 bb/100.


## Erster Referenzwert im Kaggle-Kanal (2026-09-10)

**Champion (`prince[final]`, r8_stack) vs nackte Basis (`prince[basis]`), 300 gepaarte Decks:**

| Groesse | Wert |
|---|---|
| roher Mittelwert | **+55,8 bb/100** |
| SE | 38,0 |
| 5 %-getrimmt | +6,3 |
| Median | 0,0 |
| Anteil Decks mit Unterschied | 32,3 % (97/300) |
| davon positiv | 45/97 (Vorzeichen-z −0,71) |
| Bootstrap-CI 95 % | [−16,7, +134,6] |
| perm_p | 0,076 |
| **Verdikt (stats.verdikt)** | **NEUTRAL** |
| Laufzeit | 3.153 s (~10,5 s/Deck, 1 Kern) |

**Was das heisst — die Kalibrierung des Kanals, nicht ein Bot-Verdikt:**

* Der Mittelwert wird von wenigen grossen Decks getragen (roh +55,8 gegen getrimmt +6,3, Median 0). Der
  Vorzeichen-Test kippt sogar leicht ins Negative. **Es ist KEIN Nachweis, dass die AUSLESE-Kette hier
  gewinnt** — nur, dass die Verdrahtung spielt und der Kanal laeuft.
* **Rausch-Niveau:** SE 38 bb/100 bei 300 Decks. Fuer SE ≈ 4 braeuchte man rund **27.000 Decks**, also
  ~75 h auf einem Kern bzw. ~10 h auf 8 Kernen. Das ist die ehrliche Preisliste dieses Kanals.
* Der Kanal ist ein **Spiegel** (unser Bot gegen unseren Bot) und damit dieselbe Nichtverschlechterungs-
  Schranke wie das Gym — mit dem einzigen Unterschied, dass die Spielregeln exakt Kaggles sind.
  Der Wert des Kanals liegt in der Kaggle-OEKOLOGIE (LLM-Gegner), nicht im Spiegel.

**Konsequenz fuer v9 (`r10_ernte`):** der v9-Guard feuert selten (dokumentiert ~1 Trigger/400 Haende im
Selfplay); im Smoke ueber 2 Decks war die Differenz exakt 0 bei 0 abweichenden Decks. Ein stiller Kandidat
in einem Kanal mit SE 38 liefert in vertretbarer Zeit **kein Verdikt**. Der Lauf laeuft trotzdem, weil die
interessante Zahl der ANTEIL abweichender Decks ist — er entscheidet, ob dieser Kanal fuer v9 ueberhaupt
taugt.
