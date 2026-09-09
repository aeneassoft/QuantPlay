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

* HUNL, Blinds 1/2 Einheiten, Stacks 200 Einheiten = **100 bb** — genau unsere Hausgroesse.
  (Aelteres ACPC-Material nennt 200 bb; fuer DIESE Umgebung ist das falsch, der Test `test_spielkonfiguration`
  haelt den Wert fest.)
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
