# TURNIER-DOKTRIN — destilliert aus den zwei Büchern (2026-08-04)

> Quellen: Sklansky, *Tournament Poker for Advanced Players* (3. Aufl.) + O'Kearney/Carter,
> *Endgame Poker Strategy: The ICM Book*. Systematische Extraktion (4 Leser, Workflow
> `tournament-recon`); Zusammenfassungen in eigenen Worten, Formeln exakt.
> Implementiert in `pokerbot/strategy/icm.py` (Mathematik) + `pokerbot/strategy/tournament.py`
> (Doktrin) + `pokerbot/arena/tourney.py` (Arena). Tests: `tests/test_icm.py`, `tests/test_tournament.py`.

## Die 10 Punkte

1. **$EV statt cEV — ab Hand 1.** Malmuth-Harville: `P_i(1.) = c_i/C`;
   `P_i(2.) = Σ_{j≠i} P_j(1.) · c_i/(C−c_j)` rekursiv; `$EV_i = Σ_k P_i(k)·Payout_k`.
   Chips sind konkav in Geld (Leader-Double-Ups: +$8.44 → +$7.06 → +$5.83).

2. **Bubble-Faktor als universelle Call-Schwelle.** `BF = |ΔEq_verlieren| / ΔEq_gewinnen` (≥1 überall
   außer HU); `required_equity = BF/(BF+1)` beim Flip, allgemein `r' = BF·r/(BF·r + (1−r))`.
   Anker: BF 1.18→54 %, 1.67→63 %, 2.56→72 %, 3.98→80 % (nur noch AA). Jeder Spieler derselben
   Hand hat einen ANDEREN BF.

3. **Paarungs-Matrix (Heuristik ohne exakte Rechnung).** Big-vs-Big 2.5–4.0 (QQ+; AK ist Fold);
   Medium-vs-Medium/Big 1.9–3.0; Short-vs-alles 1.2–1.7; Coverstack-vs-Short 1.0–1.1 (≈Pot-Odds).
   Mikro-Stack am Tisch erhöht die BFs ALLER anderen untereinander (nicht um jeden Preis eliminieren).
   Monster-Stack: der Leader spielt ≈ Chip-EV, alle anderen laddern („playing for the win" = Fallacy).

4. **Payout-Struktur-Effekt (kontraintuitiv).** Top-lastig → BFs sinken Richtung Chip-EV
   (Winner-take-all = kein ICM); flach/Satellite → BFs explodieren UND Fold Equity wird die
   wichtigste Equity-Form. „Kleiner Pay-Jump → gamble" ist exakt invertiert falsch.

5. **Survival-Prämie (Sklansky-Sequenzwette).** Knapp +EV ablehnen ist korrekt, wenn der Verlust
   bessere spätere Spots blockiert (Bankroll-100-Beispiel: Flip nehmen EV +35, passen +50).
   Praktisches Polster: 4.3:1 auf 4:1 ablehnen.

6. **Gap Concept + Aggressor-Bias.** Call-Range ≪ Opening-Range; Gap-Breite ∝ Feld-Tightness.
   Aggression (Shove/Raise mit Fold Equity) ist unter ICM systematisch besser als Callen →
   **Call-Ranges stärker kürzen als Open-/Shove-Ranges** (so verdrahtet: der ICM-Aufschlag sitzt
   nur auf `req`, nie auf den Open-Fraktionen). `Shove-EV = F·Pot + (1−F)·[W·(Pot+Bet) − (1−W)·Bet]`.

7. **Phasen-Kurve.** BF ~1.0–1.2 early → ~1.6 Geldblase → fällt im Geld → ~1.7 an der
   Final-Table-Bubble (ICM-Maximum des Turniers) → sinkt pro FT-Payout → **exakt 1.0 Heads-up**
   (darum spielt der Prince-v2.2-Kern das HU-Endspiel UNVERÄNDERT — Anker-Schutz und Doktrin
   fallen zusammen).

8. **Short-Stack: TIGHTER, nicht gamblen.** Chips pro Einheit ~4× mehr wert als beim Leader.
   Kein Verbluten mit Spekulativem (67s-Call bei 10bb ≈ 20 % Equity-Verlust); Paare <66 nahe dem
   Geld streichen; Blocker aufwerten (A2s > 22); Steal-Ziel = der nächst-kürzeste Stack. All-in-Sein
   ist +EV (garantierte Realisierung + totes Geld) — nicht loosen, um es zu vermeiden.

9. **Big-Stack: Dauer-Aggression auf gecoverte Mediums** (deren BF gegen dich ist maximal), Bubble
   aktiv verlängern, selbst NICHT light callen, Big-vs-Big meiden. Slowplay-Verbot: ~2 EV-Punkte
   opfern für −15 pp Verlustwahrscheinlichkeit ist im Turnier fast immer richtig.

10. **Fehlergewichtung: späte Fehler ≈ 100× frühe Fehler** (5bb bei 100bb-Start ≈ 0.05 Buy-ins;
    1bb bei 20bb-Avg spät ≈ 5 Buy-ins). Eval-Budget auf ≤40bb + ICM konzentrieren; All-in-Call-Gate
    hart verdrahten (exakte Drei-Welten-Rechnung `icm_call_threshold`); Ladder-Wert immer als Delta
    zur aktuellen ICM-Equity.

## Verdrahtungs-Karte (wo die Doktrin im Code sitzt)

| Doktrin | Code |
|---|---|
| BF-Skalierung der Call-Schwelle | `tournament.icm_required_equity` → 2 Hooks in `sixmax._decide` (`req`) |
| Exakter All-in-Call | `icm.icm_call_threshold` via `tournament.icm_scaled_req` (to_call ≥ Stack) |
| Aggressor-/Coverstack-Gegenpart | `tournament.pick_villain` |
| HU = BF 1 → Prince unverändert | kein Hook in `bot.py` (bewusst) |
| Struktur/Eliminierung/Ladder | `tournament.Director` (+ `Table(stacks=, ante=, rebuy=False)`) |
| Gepaarte $ROI-Messung | `pokerbot/arena/tourney.py::run_batch` |
| Payout-Sensitivitäts-Prüfstein | Strukturen `FLAT9` (BFs müssen steigen) vs `TOP_HEAVY9` (fallen) |
