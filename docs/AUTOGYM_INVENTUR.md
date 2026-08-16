# AUTOGYM_INVENTUR.md — Vollinventur der Mathematik-Assets (Panel, 2026-08-16)

> 77 eindeutige Formelfunktionen kategorisiert (4 Agenten + Synthese; Kategorien roh: {'CHECK_F': 21, 'NICHT_VERDRAHTBAR': 29, 'CHECK_L': 21, 'KONTEXT_FEATURE': 34, 'KNOB_PRIOR': 27, 'CHECK_P': 2}). Ergebnis = der Verdrahtungsplan fuer das Orakel.
> Welle 1 braucht KEINEN Engine-Umbau, nur Record-Erweiterungen an den zwei Gym-Call-Sites.

VERDRAHTUNGSPLAN AUTOGYM-ORAKEL (pokerbot/autogym/oracle.py, Stufen HART/P/L/F)

Grundlage geprueft: `grade_decision` erhaelt heute NUR {street, pot, to_call, action, amount, hero_hole, board, villain_hole} (gym_hu.py:42-47, gym_six.py:44-49); an BEIDEN Call-Sites liegen aber Stacks/all_in/Position bereits im Zustand vor — Felder daraus sind billige Record-Erweiterungen (Welle 1), echte neue Aufzeichnung (Hand-Verknuepfung, Ergebnis, Line) ist Welle 2.

---

## 1. STATISTIK

77 eindeutige Funktionen (die Inventur enthaelt 14 Doppeleintraege; der letzte Eintrag `equity_denial_value` ist abgeschnitten). 4 Kategorien-KONFLIKTE zwischen Erst- und Zweiteintrag, jeweils auf das konservativere Zweiturteil aufgeloest:
- `bluff_catcher_call_ev`: L→**F** (nur aggregiert belastbar)
- `pot_odds_required_equity_with_rake`: L→**KNOB** (rake=0 kollabiert auf das schon verdrahtete `equity_needed_to_call`)
- `reverse_implied_odds_max_future_loss`: L→**KONTEXT**
- `effective_multi_street_required_equity`: L→**NICHT** (braucht den GEPLANTEN Einsatzplan)

| Kategorie | Anzahl |
|---|---|
| CHECK_P | 1 |
| CHECK_F | 16 (davon 1 verdrahtet: `minimum_defense_frequency_by_bet_fraction`) |
| CHECK_L | 14 (davon 2 identisch mit Verdrahtetem: `bluff_catcher_breakeven_equity`, `compute_pot_odds` = nur Cross-Check) |
| KONTEXT_FEATURE | 19 |
| KNOB_PRIOR | 10 |
| NICHT_VERDRAHTBAR | 17 |

---

## 2. WELLE 1 — naechste Verdrahtung (10 Checks + 2 Instrumentierungen; kein Engine-Umbau, nur Record-Erweiterung an den beiden Call-Sites)

Neue Record-Felder aus vorhandenem Zustand: `effective_stack` (min(my_stack, villain_stack)+committed-Logik), `call_closes_action` (Gegner all_in oder to_call ≥ my_stack), `node_typ` ('bet'|'raise', HU aus history/cur_bet, 6-max aus obs), `n_opponents` (obs['n_active']-1).

1. **expected_value** — `knowledge_base/math/formulas.py:104` — Stufe **L**, Regel `fold_ueber_pot_odds` (Spiegel des verdrahteten `call_unter_pot_odds`): Fold bei to_call>0 mit Rueckschau-eq ≥ req+Marge. Felder: vorhanden (HU-only via villain_hole). Verifikation: EV = eq·(P+C) − C per Fraction; Nullstelle bei eq = C/(P+C). Knob: LEAD_MARGIN 0.15 [0.10, 0.25].
2. **exact_two_card_draw_equity** + Zulieferung **combined_draw_outs** — `postflop_formulas.py:413/426` — Stufe **P**, Regel `allin_call_ohne_odds`: Call, der die Action all-in schliesst (keine Implied Odds), und selbst die OPTIMISTISCHE Out-Obergrenze deckt die Pot-Odds nicht ⇒ beweisbar −EV, range-frei, laeuft auch 6-max. Felder: + `call_closes_action`. Verifikation: 1 − C(38,2)/C(47,2) = 378/1081 exakt; outs=0 ⇒ 0. Knob: OUTS_SAFETY (+2 Outs Sicherheitsaufschlag) [0, 4].
3. **required_fold_equity** — `formulas.py:322` — Stufe **L**, Regel `bet_ohne_gewinnweg`: Hero-Bet/Raise mit FE_req > 1 bei Rueckschau-E vs villain_hole kann bei keiner Fold-Frequenz profitieren. Felder: vorhanden (amount ist geloggt). Verifikation: E=0 ⇒ FE = R/(P+R) = Alpha (Fraction); Nenner-Fix formulas.py:361 suite-gepinnt. Knob: FE_MARGIN 0.10 [0.05, 0.20].
4. **minimum_defense_frequency_by_bet_fraction** (Verfeinerung) — `postflop_formulas.py:92` — Stufe **F**: das bestehende MDF-Band von je-Strasse auf je-(Strasse × Sizing-Bucket) verfeinern; `facing_bets` traegt pot+bet bereits. Verifikation: Fraction(1, 1+f); halbes Pot ⇒ 2/3. Knobs: SIZING_BUCKETS [0.33, 0.66, 1.0, 1.5, ∞], MDF_BAND 0.10 [0.05, 0.15], N_MIN 30.
5. **breakeven_bluff_percentage** — `formulas.py:594` — Stufe **F**, Regel `pool_overfold_vs_alpha`: dieselben `facing_bets`-Tupel von der BETTOR-Seite gelesen — Fold-Frequenz > alpha+Band ⇒ any-two-Bluff druckt. Verifikation: exakte Identitaet alpha + MDF = 1 per Fraction (Komplement des Checks Nr. 4, gegenseitiger Selbsttest). Knobs: wie Nr. 4.
6. **required_fold_fraction_for_raise** — `postflop_formulas.py:82` — Stufe **F**, Regel `mdf_am_raise_knoten`: Alpha/MDF getrennt fuer node_typ='raise' (das verdrahtete Band deckt nur Bets). Felder: + `node_typ`. Verifikation: 300/(300+150)=2/3 per Fraction; Identitaet mit `breakeven_fold_equity_pure_bluff`. Knobs: eigenes RAISE_N_MIN 30 (duenner besetzt).
7. **river_bluff_to_value_ratio** + q-Ziel **bluff_to_value_and_frequencies** — `strategy_formulas.py Index 18` / `formulas.py:183` — Stufe **F**, Regel `river_ratio`: jede Hero-River-Bet in Rueckschau via villain_hole als Value (eq>0.5) / Bluff klassifizieren, aggregiertes Verhaeltnis je Sizing-Bucket vs B/(P+B). HU-only. Verifikation: B=P ⇒ Bluffanteil 1/3 (Docstring-Anker); Kette q=B/(P+2B), r=B/(P+B) per Fraction; Form 2026-07-06 in tests/test_math_suite.py gepinnt. Knobs: RATIO_BAND 0.15 [0.10, 0.25], N_MIN 30, VALUE_EQ_SCHWELLE 0.5 (fix, keine Stellschraube).
8. **bluff_catcher_call_ev** — `postflop_formulas.py:102` — Stufe **F**, Regel `pool_bluff_fraktion`: an River-Bet-Knoten die Bluff-Fraktion des BETTORS (im Self-Play ist dessen Hole = das geloggte villain_hole) vs q* = B/(P+2B); Abweichung ⇒ Over-Fold/Over-Call-Vorschlag fuer die Verteidiger-Seite. Felder: vorhanden. Verifikation: Nullstelle exakt bei q* per Fraction; algebraisch identisch `exploit_call_deviation_ev`. Knobs: Q_BAND 0.10 [0.05, 0.20], N_MIN 30.
9. **commitment_margin_by_spr** — `strategy_formulas.py Index 26` — Stufe **L**, Regel `committed_fold` / `stackoff_unter_schwelle`: Fold trotz eq ≥ spr/(1+2spr)+Marge bzw. Stack-off weit darunter. Felder: + `effective_stack` (HU-only fuer die eq-Seite). Verifikation: Fraction-Identitaet S/(P+2S) = spr/(1+2spr) = equity_needed_to_call(P+S, S). Knob: LEAD_MARGIN gemeinsam mit Nr. 1.
10. **set_mining_implied_odds_margin** — `strategy_formulas.py Index 24` — Stufe **L**, Regel `setmine_ohne_odds`: Pocket-Pair-Call preflop mit eff/call < Schwelle — kein villain_hole noetig, laeuft HU UND 6-max. Felder: + `effective_stack`. Verifikation: call 2 / eff 30 / sf 0.8 ⇒ exakt 0 auf der Schwelle. Knobs: SETMINE_FAKTOR 12 [10, 15], stack_factor-Klemme [0.6, 1.0].
11. *(Instrumentierung)* **fold_frequency_exploit_ev** / **exploit_fold_deviation_ev** — `postflop_formulas.py:122` / `Index 20` — KONTEXT: severity_bb der F-Verdicts beziffern (oracle.py:118 setzt heute 0.0). Verifikation: Nullstelle exakt bei f = alpha (Identitaet `breakeven_bluff_percentage`); 0.7·100−0.3·50=55.
12. *(Nur Selbsttest)* **compute_pot_odds** — `formulas.py:7` — Identitaets-Cross-Check `compute_pot_odds(P,B,C)[1] == equity_needed_to_call(P+B,C)` in `oracle._selftest`-Analog / test_math_suite — kein neues Urteil.

Reihenfolge-Empfehlung: 1→3 (L/P, per-Entscheidung, sofort Signal), dann 4+5 (gleiche Datenbasis, gegenseitige Verifikation), dann 6→8 (Aggregations-F), zuletzt 9+10 (brauchen das effective_stack-Feld).

---

## 3. WELLE 2 — braucht echte Gym-Erweiterung (neue Aufzeichnungsfelder)

Neue Felder (Record-Schema-Erweiterung + teils Aggregations-Maschinerie):
- **`hand_id` + `decision_idx`** (Verknuepfung aller Records einer Hand): → `implied_odds_extra_needed` (L), `call_ev_with_implied_gain` (L, realisierter future_gain aus den Folge-Records), `reverse_implied_odds_max_future_loss` als aggregierter Detektor.
- **`hand_result`** (Netto-bb der Hand je Sitz, Showdown ja/nein, Gewinner): → empirisches `equity_realization` (Knob-Kalibrierung statt Prior), `realized_equity_by_position_spr`-Validierung, money_mine-Anbindung.
- **`line`** (Aktionsfolge je Strasse, mind. Hero: checked/bet/raised + Marker check-then-face-bet): → `delayed_cbet_ev` (L; braucht die Check/Give-up-Erkennung), `minimum_check_raise_defense_combos` (F; Verteidigungs-Split Check-Call vs Check-Raise am Check-Knoten), `check_raise_vs_check_call_delta` (L).
- **Aggregierte Pool-Fold-Frequenzen als Zweipass-Input** (erst sammeln, dann graden — Maschinerie, kein Feld): → `semi_bluff_ev` (L), `raise_ev_with_fold_equity` (L, verpasste Raises), Verschaerfung von `required_fold_equity` (FE_req vs Pool-FE+Marge).
- **`hero_pos` / `first_in` / `caller_count`** (gym_six hat position_label schon lokal, wird nicht geloggt; HU: Button-Rolle): → `preflop_calling_range_fraction` (F), `short_stack_open_shove_fraction` (F, Vergleich gegen publizierte Nash-Push/Fold-Tabellen), `suited_connector_implied_odds_margin` (L).
- **Rueckschau-Klassifikations-Aggregator je Knotenklasse** (street × node_typ × sizing-bucket × Rolle): → `balanced_bluff_combos`, `target_bluff_combos_for_polar_bet`, `alpha_break_even_bluff_frequency`, `optimal_value_to_bluff_ratio`, `bluff_to_value_ratio_by_pot_fraction`, `breakeven_fold_equity_pure_bluff`, `calling_frequency_to_indifferent_bluffer` (alle F — dieselbe Familie wie W1-Nr. 7/8, nur feiner geschluesselt; erst sinnvoll, wenn die Knotenklassen n≥30 fuellen).
- **Kontext-Felder fuer Severity** (`spr` via compute_spr, `initiative`, `n_opponents`): → `stackoff_equity_threshold_from_spr`, `commitment_spr_for_equity`, `multiway_independent_equity_need`, `initiative_value`, `in_position_ev_premium`, `realized_equity_by_position_spr`, `equity_denial_value`, `geometric_bet_fraction_to_all_in`, `per_street_geometric_bets`, `hand_class_combo_count`, `card_removal_fraction`, `outs_to_equity_rule_2_and_4` (alle KONTEXT — gewichten, urteilen nie).

---

## 4. NICHT VERDRAHTEN (ehrlich)

Alle aus demselben Grund: **das Gym liefert Haende, keine Ranges** — pro Entscheidung existiert kein Range-Objekt, und ein empirischer Range-Aggregator (Holdings je Linie ueber viele Haende) ist ein eigenes Bauprojekt, kein Check:
`polarized_bet_ev`, `range_vs_range_ev`, `nut_advantage_index`, `nut_fraction`, `polarization_degree`, `mergedness_index`, `capped_range_penalty`, `range_morphology_selector`, `cbet_frequency`, `barrel_continuation_frequency`, `give_up_frequency`, `range_advantage_to_bet_frequency`, `reverse_implied_odds_discounted_equity`, `range_combo_count`, `count_hand_combos_with_blockers`.
Zusaetzlich:
- `effective_multi_street_required_equity` — braucht den GEPLANTEN Mehrstrassen-Plan, den kein Entscheidungs-Record enthaelt; die realisierte Variante ist P&L-Attribution (money_mine), kein Formel-Check.
- `reverse_implied_odds` (math.json:273-334) — verified:false, Code defekt (dataclass-Dekorator ohne @ ⇒ TypeError); erst nach Code-Fix ueberhaupt bewertbar.
- `cbet_frequency` ausdruecklich NICHT als degradierten Prior-Check verdrahten (Neutral-Nullen fuer range_advantage/nut_advantage waeren Selbstbetrug).

---

## 5. KNOB-REGISTER (KNOB_PRIOR + Check-interne Konstanten)

| Knob | Quelle | Default | Schranken |
|---|---|---|---|
| R (equity_realization_ev) | postflop_formulas.py:239 | 1.0 | [0.5, 1.2] |
| R (equity_realization) | formulas.py:624 | 1.0 | [0.5, 1.05] (Klemmen wie realized_equity_by_position_spr) |
| dirty_out_weight | postflop_formulas.py:438 | 0.5 | [0, 1] |
| rake_fraction / rake_cap | postflop_formulas.py:132 | 0 (Gym rake-frei) | [0, 0.05] / ≥0 |
| preflop_open_raise_size_bb | strategy_formulas Index 1 | 2.25/2.50/3.00 je Pos. | [2.0, 3.5], 0.25-Raster |
| preflop_threebet_size_bb | Index 2 | IP 3x / OOP 4x | IP [2.5, 3.5], OOP [3.5, 4.5], Cap ≤ effective_bb, IP<OOP |
| preflop_fourbet_size_bb | Index 3 | IP 2.2x / OOP 2.5x | IP [2.0, 2.6], OOP [2.2, 3.0], Untergrenze 3bet+open, Cap ≤ eff |
| preflop_squeeze_size_bb | Index 4 | open·(3\|4 + Caller) | Basis [2.5, 4.5], +1/Caller [0.5, 1.5], monoton in callers, Cap ≤ eff |
| bounded_read_deviation_ev | Index 28 | sensitivity 2 | edge-Clip [−1, 1] hart; sensitivity [0, 3]; |EV| ≤ P+R per Konstruktion |
| stat_read_delta | Index 29 | 0.5/0.3/0.2 | Simplex Σ=1, jedes Gewicht [0, 1]; Output-Clip [−1, 1] |
| realization-Klemme (preflop_calling_range_fraction) | Index 5 | — | [0.45, 0.90] (Konstanten sind zugleich Knobs) |
| LEAD_MARGIN | oracle.py:28 | 0.15 | [0.10, 0.25] |
| MDF_BAND | oracle.py:32 | 0.10 | [0.05, 0.15] |
| EQ_ITERS | oracle.py:30 | 200 | ≥200 (SE ≪ LEAD_MARGIN halten) |
| N_MIN (F-Stufe) | oracle.py:110 | 30 | ≥30, nie senken |
| SIZING_BUCKETS (neu, W1-4/5/7) | — | [0.33, 0.66, 1.0, 1.5] | Kanten fix pro Messreihe (sonst Bucket-Gaming) |
| RATIO_BAND / Q_BAND (neu, W1-7/8) | — | 0.15 / 0.10 | [0.10, 0.25] / [0.05, 0.20] |
| FE_MARGIN (neu, W1-3) | — | 0.10 | [0.05, 0.20] |
| OUTS_SAFETY (neu, W1-2) | — | +2 Outs | [0, 4] |
| SETMINE_FAKTOR / SC-Schwellen | Index 24/25 | 12 / max(8, 20−3·IP−2·Caller) | [10, 15] / Untergrenze 8 fix |

Bindend (Improver-Doktrin, oracle.py Kopf): HART ist unantastbar; nur P darf autonom gepatcht werden (Wrapper hinter gepaartem A/B-Gate); L/F erzeugen Vorschlaege, nie Auto-Patches; jede Knob-Drehung braucht den expliziten Bedingungs-Test (CONDITIONAL_POKER_LEMMAS-Muster).
