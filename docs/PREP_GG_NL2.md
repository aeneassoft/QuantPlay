# Preparation: Princedarkness @ GG NL2 ($0.01/$0.02, 6-max)

> Grundlage: 600.000 gekaufte Hände (96 Tage, `data/gg_nl2/hh`), EU-Fenster 09–03 Uhr Berlin =
> 544.175 Hände / 81.723 Spieler. Vermessung: `research/gg_nl2_pop.py` (Zeit-Pass + Population +
> Hebel-Simulation). Alle Simulationszahlen sind [SIMULATION] gegen den frequenz-gefitteten Pool —
> das ROBUSTE Signal ist die REIHENFOLGE der Hebel, nicht der Absolutwert. Stand 2026-08-04.

## 1. Das Habitat (gemessen)

- **Der Pool ist rund um die Uhr fast identisch** (VPIP 30 / PFR 17 / 3bet 7,2 / FvR 53 in jeder
  Stunde). Dein 9–3-Fenster ist volumen-optimal (Peak 17–23 Uhr), strategisch ändert die Uhrzeit
  fast nichts — nur 00–03 Uhr wird es minimal looser (VPIP 31, 3bet 7,5). **Timing ist KEIN Hebel;
  Seat-Selection schon** (Whales VPIP>40 existieren: ~5% des Volumens, erkennbar nach 2 Orbits).
- **Volumen ist reg-dominiert:** 62% reg_tag (VPIP 23/PFR 16/FvR 77) + 17% Nits. Der NL2-Mythos
  "alles Fische" stimmt für die MASSE der Sitzungen nicht — die Fische sind da (81k Accounts!),
  aber die Regs spielen die Hände.
- **Die Steuer ist der stärkste Gegner: 4,48% des Pots** (Rake 3,71% + Jackpot 0,77%, Cap 9,5bb)
  ≈ **34–39 bb/100 Last** im Sim. Jeder kleine Pot ist Steuer-Futter; der Edge muss aus wenigen
  disziplinierten Value-Pötten kommen.
- Echter Showdown (Karten gezeigt) nur in ~5% der Hände; Durchschnitts-Depth 111bb.

## 2. Das Gewinner-Template (echte Winrates, ≥2.000 Hände)

| | WR bb/100 | VPIP | PFR | Limp | 3bet | FvR | WTSD |
|---|---|---|---|---|---|---|---|
| Gewinner (n=59) | **+14,9** (top +49) | 21,7 | 15,9 | 0,8 | 6,6 | **78** | 5,6 |
| Verlierer (n=64) | −14,7 | 24,7 | 16,8 | 1,0 | 5,8 | 74 | 6,6 |

Die Trennlinie ist DISZIPLIN, nicht Fancy Play: 3 Punkte weniger VPIP, engerer Call-Gap, MEHR
Folden gegen Aggression, weniger Showdowns. **Die Gewinner folden am meisten im ganzen Pool.**

## 3. Die Diagnose (P_D gemessen vs Template)

VPIP **55 → 22** · Limp **39% → 0** · Blind-Defense **FvR 27% → ~75%** · 3bet 10,8 (ok, lassen).
Der gemessene Ist-Stil simuliert auf **−210 bb/100** in diesem Pool; das A-Game (nur Tilt weg)
auf −29 — Tilt bleibt die teuerste Einzelvariable (~180 bb/100), aber A-Game ALLEIN reicht bei
NL2 nicht: die Rake drückt Break-even unter Wasser.

## 4. Das Hebel-Ranking [SIMULATION, 40k Hände je Arm, gleiche Seeds]

| Hebel (auf dem A-Game) | bb/100 | Delta |
|---|---|---|
| **Value-Gate** (nur mit Equity betten; Overbet NUR Value) | **+31,1** | **+59,8** |
| Limp-Cut (raise-or-fold preflop) | −7,4 | +21,2 |
| Call-Disziplin (Pot-Odds = harte Grenze) | −16,4 | +12,2 |
| 3bet-Up | −28,6 | ±0 — **bringt nichts** |
| **ALLE DREI GEBÜNDELT (gemessen, nicht addiert)** | **+63,0 ± 10,7** | +91,6 |

Warum das Value-Gate dominiert: der Pool foldet 77% auf Aggression, aber die, die bleiben, gehen
mit — Bluffs (v.a. die 28% Overbet-Bluffs) verbrennen doppelt: gegen die Sticky-Caller UND an
die Rake. Value wird IMMER bezahlt.

## 5. Die Preparation (5 Regeln, in dieser Reihenfolge)

1. **Tilt-Protokoll (nicht verhandelbar):** Nach jedem verlorenen 20bb+-Showdown oder verlorenen
   All-in → 20 Hände nur Baseline-Range (tight öffnen, nichts Dünnes callen). Das ist der
   gemessene Unterschied zwischen −210 und −29.
2. **Bluffe nicht. Bette Value.** Keine Overbet-Bluffs, keine Barrels ohne Equity. Wenn du bettest,
   willst du gecallt werden. (Der +60-Hebel.)
3. **Kein Limp, nirgends.** Raise oder Fold. VPIP-Ziel ~22, Open ~2,5bb.
4. **Blinds sind kein Besitz:** gegen Raises ~75% folden (heute: 27%). Postflop sind Pot-Odds die
   harte Call-Grenze — kein "er könnte bluffen" (er blufft bei NL2 nicht genug).
5. **3bet normal lassen, Uhrzeit frei wählen, auf Whales achten** (VPIP>40 nach 2 Orbits →
   Position auf sie nehmen; dort — und NUR dort — dünner value betten und breiter callen).

**Erwartung ehrlich gerahmt:** das volle Paket simuliert +63 bb/100 (modell-optimistisch); die
echten Top-Regs drucken real +28 bis +49. Realistisches Ziel mit Paket + Disziplin: **+10 bis
+30 bb/100.** Varianz: SD ≈ 90–110 bb/100 → auch als Gewinner sind 20-Buy-in-Schwankungen über
50k Hände normal; Bankroll 40+ Buy-ins ($80+).
