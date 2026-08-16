# SNOWIE-BLUNDER-ANALYSE — alle 39 Blunder von AUSLESE v1, einzeln durchgeklickt
(2026-08-17; Quelle: PokerSnowie 4, 400 exportierte Haende, Gate-Paritaet ohne Resolver)

## Der Befund in einem Satz
**Die groesste Blunder-Klasse ist genau der Mechanismus, der AUSLESE v1 seine +6,1 bb/100
gebracht hat: zu lose Call-Downs (15 von 39 = 38%).** Snowie sieht damit dasselbe wie unsere
GTO-Balance-Auswertung (Call Flop 195% der Empfehlung) -- die Richtung war richtig, die DOSIS
ist zu hoch, und die Ueberdosis konzentriert sich in MEHRSTRASSEN-Calls.

## Die vier Fehlerklassen

| Klasse | Anzahl | Muster |
|---|---|---|
| **C — zu lose Call-Downs** (Snowie: FOLD) | **15** | Call Flop -> Call Turn -> Call River mit einem Paar, Brett-Paar oder A-high |
| **B — verpasster Wert / zu passiv** (Snowie: BET/RAISE) | 11 | Turn-Check mit Ueberpaar/Trips, River-Check mit zwei Paar, verpasste Flop-Raises |
| **A — Ueberaggression mit starken Haenden** (Snowie: CHECK/CALL) | 9 | Bet/Raise statt Falle mit Flush/Trips/Top-Two; Thin-Value-Bets, die geraist werden |
| **D — zu enge Folds** (Snowie: CALL) | 3 | Fold mit Open-Ender / zwei Paar am River |

## Die belegenden Einzelfaelle (Auswahl, mit Snowies EV)

**C — Call-Downs (die teuersten):**
- K5o auf 7♣J♥7♥8♦6♥: Call Flop+Turn+River $15,56 mit Brett-Paar. FOLD 100%, Call **−7,10 EV**
- A♥2♥ auf 9♦A♣Q♠4♣8♣: River-Call $33,20 gegen Raise mit Top-Pair-Weak-Kicker. FOLD 100%, Call **−15,02 EV**
- T♥3♣ auf Q♣Q♦T♦4♦A♥: River-Call $33,20 gegen Raise. FOLD 100%, Call **−10,12 EV**
- 6♦Q♦ auf 5♥6♥K♠2♥9♥ (4 Herz): Call-Down mit zweitem Paar. FOLD 84%, Call **−6,92 EV**
- Mehrere gewonnene Haende sind trotzdem Blunder (Q♦7♣, T♦2♠) — Snowie bewertet den PROZESS,
  nicht das Ergebnis. Das ist methodisch genau richtig und deckt sich mit unserer Doktrin.

**B — verpasster Wert (die groessten Luecken):**
- Q♣Q♠ auf 9♣8♥4♦A♦3♥: Turn-Check UND River-Check mit Ueberpaar. BET 100% (**26,73** bzw. **35,42 EV**)
- 4♦6♦ auf 4♠3♠8♣T♦4♣ (Trips): River-Check. BET 100% (**19,17** vs 15,90 EV)
- A♦Q♠ auf Q♣9♠T♥A♣K♣ (zwei Paar): River-Check. BET 100% (**25,55** vs 18,88 EV)
- 9♣8♦ auf 2♣5♣J♣7♠Q♥: River-Check mit High-Card — Snowie will hier BLUFFEN. BET 100%

**A — Ueberaggression mit Monstern:**
- K♠9♠ auf 5♠2♠A♠ (geflopptes Flush): Bet $2,50. CHECK 100% (**13,49** vs 11,36 EV) — Falle verpasst
- J♥8♦ auf K♣Q♥J♦J♠ (Trips): Raise $27,50. CALL 100% (**8,80** vs 5,42 EV)
- A♠K♣ auf A♦K♥6♦3♦8♠ (Top-Two): River-Bet $50. CHECK 100% (**63,62** vs 44,79 EV)

## Die drei abgeleiteten Kandidaten (Runde 4, jeder durchs eigene Gate)

1. **MARGEN-SWEEP (hoechste Prioritaet).** sel_guard nutzt +3pp ueber die Pot-Odds. Snowie sagt:
   zu locker. Sweep +8pp / +12pp / +15pp gegen AUSLESE v1 — Erwartung: das Optimum liegt
   zwischen der Basis (53% Call-Frequenz) und v1 (195%).
2. **MEHRSTRASSEN-DISZIPLIN.** Fast alle C-Blunder sind Call-Ketten: Der Guard dreht den
   Flop-Fold zum Call, danach callt der Bot Turn UND River weiter. Kandidat: der Guard darf
   die Hand nur EINMAL retten; auf spaeteren Strassen gilt die Basis-Entscheidung (oder eine
   verschaerfte Schwelle). Das erklaert auch, warum sel_all (alle Strassen) nichts brachte.
3. **TURN-WERT-BETS.** Klasse B haeuft sich am Turn mit starken Haenden — der aelteste
   dokumentierte Postflop-Leak des Repos, jetzt von einem dritten System bestaetigt.
   Kandidat: Wert-Bet-Guard am Turn (Bet, wenn Equity vs Tracker-Range hoch UND gecheckt wurde).

## Ehrlichkeitsvermerk
Snowies Netz ist eine dritte, unabhaengige Meinung — nicht Wahrheit. Es approximiert sein
EIGENES Gleichgewicht, und die GTO-Balance-Ansicht ist ausdruecklich Beta. Was TRAEGT: die
Uebereinstimmung dreier unabhaengiger Instrumente (unser MDF-Orakel, unser gepaartes Gate,
Snowies Blunder-Liste) darin, dass die Call-Frequenz am Flop der zentrale Hebel ist — und dass
wir jetzt auf der ANDEREN Seite des Optimums stehen. Kein Kandidat wird ohne unser eigenes
gepaartes Gate geschifft; Snowie liefert Hypothesen, nicht Urteile.
