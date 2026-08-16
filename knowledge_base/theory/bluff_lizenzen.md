# BLUFF-LIZENZEN — die strukturellen Voraussetzungen des Bluffens, mathematisch
(Programm-Dokument, 2026-08-16; Anlass: Brown 2026 + das AUSLESE-v1-Gate — Auswahl, nicht Quote)

**These:** Ein Bluff ist nie „eine schwache Hand mit Frequenz f", sondern eine Hand mit einer
**Lizenz** — einer berechenbaren strukturellen Eigenschaft, die den Bluff profitabel macht.
Brown misst: NULL Haende sind in allen vier Modellvarianten pure Bluffs; die 27 realen
Bluff-Haende zerfallen danach, WELCHE fallengelassene Vereinfachung sie lizenziert.
Unsere Aufgabe: die Lizenzen finden, kategorisieren, als Formeln fassen, dann messen.

Alle Groessen unten sind aus LEGALER Information berechenbar: eigene Karten h, Board B,
Einsatzgroesse b, Pot P, und die Bayes-Tracker-Range des Gegners W = {Combo c -> Gewicht w(c)}
(aus der gespielten Linie). Continue-Range C(W,b) = die Combos, die W gegen Groesse b
weiterspielt (Defense-Advisor / MDF-Kern der staerksten Combos).

## L1 — BLOCKER-LIZENZ (Karten-Entfernung auf der Continue-Seite)
    Block(h) = 1 − [ Σ_{c∈C, c∩h≠∅} w(c) ] / [ Σ_{c∈C} w(c) ]  … relativer Gewichtsverlust
    praeziser als Score:  Block(h) = Σ_{c∈C} w(c)·1[c∩h≠∅] / Σ_{c∈C} w(c)
Hero haelt Karten, die die WEITERSPIEL-Combos des Gegners physisch reduzieren (Nut-Flush-
Blocker etc.). Lizenz, wenn Block(h) ≥ β. Quelle: Brown (Karten-Entfernung = die 169x169-
Nicht-Skalaritaet); count_hand_combos_with_blockers liegt unverdrahtet in formulas.py.

## L2 — UNBLOCKER-LIZENZ (die Fold-Seite nicht beruehren)
    Unblock(h) = 1 − Σ_{c∈F} w(c)·1[c∩h≠∅] / Σ_{c∈F} w(c),   F = W \ C (die Fold-Range)
Hero haelt KEINE Karten der Gegner-FOLD-Range — jede geblockte Fold-Combo senkt die realisierte
Fold-Frequenz unter die MDF-Rechnung. Vollstaendige Lizenzstaerke = Block(h)·Unblock(h)-Paar.

## L3 — EQUITY-BACKUP (Semi-Bluff-Lizenz)
    E_called(h) = Equity(h | C(W,b), B)     … Equity GEGEN DIE CALLING-Range
    Lizenz, wenn  FE_noetig(P, b, E_called) = (b − E_called·(P+2b)) / (P + b − E_called·(P+2b))
    unter der realistischen Fold-Schaetzung liegt (required_fold_equity, verdrahtet, E1-geprueft).
Outs machen den Bluff zweistufig profitabel. Quelle: semi_bluff_ev (Formelsammlung), Brown
(Nichtdeterminismus-Variante lizenziert eigene Bluff-Haende).

## L4 — CAP-LIZENZ (Range-Asymmetrie)
    Cap(W,B) = Σ_{c∈W} w(c)·1[staerke(c,B) ≥ nut-Schwelle] / Σ w(c)   … Nut-Anteil des Gegners
    Lizenz, wenn Cap(W,B) ≤ κ  (der Gegner KANN kaum stark sein — seine Linie hat ihn gecappt).
Quelle: nut_fraction/capped_range_penalty (Sammlung, bisher NICHT_VERDRAHTBAR mangels Range —
die Tracker-Range macht sie jetzt berechenbar!). Das ist der sel_guard-Trick auf der Bet-Seite.

## L5 — GEOMETRIE-LIZENZ (Sizing/SPR)
    b*(P, s) aus geometric_bet_fraction_to_all_in; Lizenz fuer Overbet-Polarisierung nur, wenn
    die eigene Range am Knoten die Nut-Seite besitzt (L4 gespiegelt auf Hero) und SPR den
    Druck traegt (stackoff_equity_threshold_from_spr). Quelle: Brown (Bet-Groessen-Achse).

## Das Messprogramm (vorregistriert)
1. **Katalogisieren:** alle Bluff-Instanzen aus decisions.jsonl.gz + dem GTOW-Raise-Mining
   (488 Raises: Flop 53% Air) + Browns 27 Haenden je Lizenz scoren -> welche Lizenzen treten
   real auf, einzeln oder im Buendel?
2. **Orakel-Checks:** L-Check `bluff_ohne_lizenz` (Hero-Bet mit niedriger Equity UND
   Block·Unblock·Cap alle unter Schwelle = struktureller Spew) + F-Check Lizenz-Raten.
3. **Kandidat (Runde 3, gegen AUSLESE v1):** der Bet-seitige Selektions-Guard — Bluffs nur
   mit Lizenz-Score ueber Schwelle, Value unangetastet. Erwartung vorregistriert VOR dem Bau.
4. **Ehrlichkeit:** Schwellen (β, κ, …) sind Knoepfe mit Schranken; die Lizenz-DEFINITIONEN
   sind Formeln und unveraenderlich. Erst Katalog (deskriptiv), dann Check (normativ) —
   nie umgekehrt, sonst bauen wir Dogma statt Messung.
