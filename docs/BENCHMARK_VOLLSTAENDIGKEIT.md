# BENCHMARK_VOLLSTAENDIGKEIT.md — Abgleich Inventur vs. Repo-Quellen (2026-08-16)

**Frage:** Der Nutzer sagt, 95% der noetigen Mathematik liege schon im Repo und muesse nur
ZUSAMMENGESTELLT werden. Stimmt das — und was fehlt der Benchmark (`pokerbot/autogym/oracle.py`)
fuer VOLLSTAENDIGKEIT?

**Kurzurteil:** Fuer die ENTSCHEIDUNGS-Mathematik (Cash, HU + 6-max) stimmt die 95%-These:
die Inventur (AUTOGYM_INVENTUR.md, 77 Funktionen) deckt die drei Formeldateien vollstaendig ab,
und die `*_verified.json` liefern zu jeder Funktion sogar fertige `verify_expr`/`verify_value`-
Paare = quasi mitgelieferte E1-Referenzen. ABER: die Inventur hat **drei ganze Repo-Domaenen nie
inventarisiert**, die fuer eine VOLLSTAENDIGE Benchmark dazugehoeren und montierbar sind —
**(A) ICM/Turnier** (`pokerbot/strategy/icm.py` + `tournament.py` + `arena/tourney.py`),
**(B) Mess-/Varianz-Statistik** (`mathematics_of_poker.json`: 443 Eintraege, viele mit Python),
**(C) das MoP-Korpus selbst** (Toy-Game-/Grenzwert-Anker als Cross-Checks). Echt fehlend (nicht
im Repo) sind nur 5 Punkte, siehe Abschnitt 5.

---

## 1. Quellen-Abgleich (was die Inventur abdeckt — und was nicht)

| Quelle | Umfang | In der Inventur? | Befund |
|---|---|---|---|
| `knowledge_base/math/formulas.py` | 12 Funktionen | ✓ vollstaendig | 7 davon verdrahtet/gespiegelt (v0+W1-1..3) |
| `knowledge_base/math/postflop_formulas.py` | 34 Funktionen | ✓ vollstaendig | Welle 1/2 geplant |
| `knowledge_base/math/strategy_formulas.py` | 32 Funktionen | ✓ vollstaendig | Welle 1/2 geplant |
| `knowledge_base/math/math.json` | 13 Eintraege, `verified`-Flags | ✓ (identisch mit formulas.py) | `reverse_implied_odds` verified:false, Code defekt — korrekt als NICHT gelistet |
| `knowledge_base/math/postflop_calc_verified.json` | 34 Kalkulationen | ⚠ nur indirekt | traegt je Funktion `verify_expr` + `verify_value` = **fertige E1-Referenzen, ungenutzt** |
| `knowledge_base/math/strategy_calc_verified.json` | 32 Kalkulationen | ⚠ nur indirekt | dito |
| `knowledge_base/math/mathematics_of_poker.json` | **443 Eintraege** (name/concept/formula/python) | **✗ NICHT inventarisiert** | Varianz, CI, Risk-of-Ruin, Kelly, Turnier-Varianz-k, Malmuth-Harville/Weitzman, Jam-or-Fold-Schwellen, Alpha/MDF-Toy-Game-Anker — vieles mit ausfuehrbarem Python |
| `knowledge_base/concepts/concepts.json` | 813 Konzepte (qualitativ) | ✗ (zu Recht) | keine Formeln; als Benchmark-Quelle korrekt ausgeschlossen |
| `tests/test_math_suite.py` | 17 Deep-Checks, Fraction-Kultur | ⚠ teilweise | enthaelt SCHON Fraction-Referenzen fuer W1-Kandidaten (alpha/MDF `_alpha_mdf`, Bluff-Ratio `_bluff_ratio`, RFE `_rfe`, Konventions-Checks `_observed_fracs_conventions`) — das Orakel dupliziert sie bisher nicht, es sollte sie IMPORTIEREN |
| `pokerbot/strategy/icm.py` | exaktes Malmuth-Harville, bubble_factor, icm_call_threshold (getestet: `tests/test_icm`) | **✗ NICHT inventarisiert** | komplette ICM-Checkfamilie montierbar |
| `pokerbot/strategy/tournament.py` | icm_required_equity, anteiliges Risiko-Premium (validiert +10,0 ± 5,0 pp ROI), bf_matrix, Director | **✗ NICHT inventarisiert** | Turnier-Gym-Anschluss montierbar (`arena/tourney.py` existiert) |
| `pokerbot/engine/equity.py` | equity_vs_hand / equity_vs_range | ✓ (als Rueckschau-Motor) | multiway-Rueckschau (alle Holes) fehlt noch, kleiner Umbau |

**Zaehlung:** 12+34+32 = 78 Definitionen, 77 eindeutig (1 Doppel `bluff_catcher_breakeven_equity`
≡ `equity_needed_to_call`-Familie) — die Inventur-Statistik stimmt. Verdrahtet heute: 7 Checks.

---

## 2. Aus dem Repo MONTIERBAR — Block A: ICM / Turnier

Das Gym dafuer existiert schon (`pokerbot/arena/tourney.py`, gepaarte SNG-Arena) — es ist nur
nicht an das Orakel angeschlossen. Vorschlag: `gym_tourney.py` analog `gym_hu.py`, Records um
`stacks_all`, `payouts`, `bf` erweitert.

| Baustein | Quelle | Kategorie | Regel-Skizze | Fraction-Referenz |
|---|---|---|---|---|
| ICM-Summen-Invariante | `strategy/icm.py:22` (`icm_equities`) | **HART** | Σ ICM-Equities = Σ Payouts, exakt, jede Hand | Winner-take-all: `icm_equities([200,100,100],[1,0])` = exakt `[1/2, 1/4, 1/4]` (Stack-Proportion per Fraction) |
| ICM-Monotonie | `strategy/icm.py` | **HART** | groesserer Stack ⇒ ≥ ICM-Equity (Permutations-Check) | Gleiche Stacks ⇒ exakt gleiche Equity per Symmetrie |
| Malmuth-Harville vs. Enumeration | `strategy/icm.py` + `tests/test_icm.py` | E1-Selbsttest | unabhaengige Enumeration (bereits im Test) als Orakel-Referenz uebernehmen | 3 Spieler, rationale Stacks: MH-Produktformel per Fraction nachrechnen |
| `bubble_factor` HU-Grenzfall | `strategy/icm.py:101` | E1-Selbsttest | HU winner-take-all ⇒ BF exakt 1 (CLAUDE.md-Anker: Prince spielt Endspiele unangetastet) | `bubble_factor(HU, [1,0])` == 1 exakt |
| `icm_call_ohne_odds` | `icm.py:126` (`icm_call_threshold`) + `tournament.py:71` (`icm_required_equity`) | **L** | Rueckschau-Call unter der ICM-Schwelle (Chip-req · BF_eff), Marge wie LEAD_MARGIN | Identitaet `icm_required_equity(req, 1)` == req (BF=1 kollabiert auf Cash) per Fraction |
| Anteiliges Risiko-Premium | `tournament.py` (BF_eff = 1+(BF−1)·(to_call/Stack)) | **Knob** | Skalar validiert (gepaart, +10,0 ± 5,0 pp); Schranken: Anteils-Formel fix, kein voller BF (REFUTIERT −8pp) | to_call=Stack ⇒ BF_eff = BF exakt; to_call=0 ⇒ 1 |
| `icm_pressure_mult` | `tournament.py:136` | **Knob** | Druck-Hebel Doktrin 9; Schranken aus DOKTRIN.md | Grenzfall: keine ICM-Spannung ⇒ Mult 1 |
| Turnier-Varianz-k | `mathematics_of_poker.json` („Tournament variance multiple k") | **Kontext** | Payout-Struktur ⇒ Varianz-Vielfaches; gewichtet Turnier-Gate-SE | k fuer Winner-take-all-Struktur geschlossen per Fraction |

## 3. Aus dem Repo MONTIERBAR — Block B: Mess-/Varianz-Statistik (die Benchmark der Benchmark)

Die Gate-Doktrin (ANWENDEN > 2·SE) steht und faellt mit der SE-Berechnung — aber NICHTS prueft
heute die Statistik des Gates selbst. `mathematics_of_poker.json` traegt die noetigen Formeln
mit Python: Varianz-Additivitaet, SD/Var-Relation, CI des Winrates, SE-Skalierung mit n,
Stichprobengroesse fuer Praezision. Vorschlag: **neue Stufe „MESS"** (Selbsttest des Harness,
laeuft in `selftest.py`, nie im Improver-Gebiet):

| Baustein | Quelle (MoP-Eintrag) | Kategorie | Fraction-Referenz |
|---|---|---|---|
| SE des gepaarten Gates | „Scaling variance with sample size" | MESS (E-Stufe) | konstruierte Paar-Serie mit rationalen Werten ⇒ SE geschlossen per Fraction, gegen `duplicate_ab`-SE |
| Varianz-Additivitaet | „Additivity of variance across poker hands" | MESS | Var(X+Y) = Var(X)+Var(Y) fuer unabhaengige rationale Serien, exakt |
| CI / Stichprobengroesse | „Approximate confidence interval …", „Sample size needed …" | MESS | n = (z·σ/ε)² an rationalen σ,ε; z fix |
| Bernoulli-Varianz | „Variance of Bernoulli outcome" | MESS | p(1−p) per Fraction, Maximum exakt bei p=1/2 |

## 4. Aus dem Repo MONTIERBAR — Block C: Multiway + MoP-Anker + Selbsttest-Importe

| Baustein | Quelle | Kategorie | Regel-Skizze | Fraction-Referenz |
|---|---|---|---|---|
| Multiway-Equity-Bedarf | `postflop_formulas.py:403` (`multiway_independent_equity_need`) | **L** (6-max!) | gym_six loggt `n_opponents` schon; Call der die Action schliesst, req-Equity vs Feld: per-Gegner-Bedarf = target^(1/n) uebersteigt Draw-Obergrenze ⇒ Lead. Unabhaengigkeits-Annahme ehrlich als Naeherung deklarieren (NOTES.md-Eintrag) | target 1/4, n=2 ⇒ exakt 1/2 |
| Multiway-Rueckschau | `engine/equity.py` + gym_six | Umbau (klein) | gym_six loggt `villain_hole=None` — stattdessen ALLE aktiven Holes loggen ⇒ L-Stufe (Pot-Odds-Rueckschau) laeuft auch 6-max; braucht `equity_vs_hands` (Mehrgegner-MC, ~20 Zeilen um `equity_vs_hand`) | All-in-Faelle exakt enumerierbar (Board-Restkarten) wie `_river_equity_exact` in test_math_suite |
| Geometrisches Sizing | `postflop_formulas.py:208/218` | **Kontext** | Severity-Gewichtung + Sizing-Bucket-Referenzlinie (W1-4/5) | SPR 4, 1 Street ⇒ f = 4 (Pot-Faktor) exakt; `(1+2f)^streets = 1+2·spr` als Fraction-Identitaet |
| SPR-Familie Cross-Check | `postflop_formulas.py:188/198` + `strategy_formulas.py:263` | E1-Selbsttest | Dreifach-Identitaet `stackoff_equity_threshold_from_spr(spr)` == Nullstelle von `commitment_margin_by_spr` == `equity_needed_to_call(P+S, S)` | spr = S/P rational ⇒ spr/(1+2·spr) per Fraction (Inventur W1-9 nennt sie schon — hier als gegenseitiger Selbsttest aller drei) |
| Combo-Zaehlung | `formulas.py:473` + `postflop_formulas.py:291/321` | E1-Selbsttest | Blocker-Kombinatorik gegen Brute-Force-Enumeration (52 Karten) | AKs ohne Blocker = 4, AA = 6, mit einem As tot: AA = 3 — exakt |
| test_math_suite-Referenzen importieren | `tests/test_math_suite.py` (`_alpha_mdf`, `_bluff_ratio`, `_rfe`, `_observed_fracs_conventions`) | E1 | die W1-4/5/7-Checks NICHT neu herleiten: die Fraction-Referenzen existieren, das Orakel-Selbsttest-Modul soll sie aufrufen (Pruefer getrennt vom Geprueften bleibt gewahrt — die Suite ist der unabhaengige Pruefer) | vorhanden (17/17 deep) |
| MoP-Toy-Game-Anker | `mathematics_of_poker.json` („Golden mean r=√2−1", AKQ-α, Clairvoyance-Calling) | E1-Selbsttest | Grenzwert-Anker fuer die F-Familie: α(s)-Kurve, MDF-Komplement, P=1-Bluff-Cutoff | α = s/(1+s) an rationalen s per Fraction; MDF+α = 1 Identitaet (deckt sich mit Inventur W1-5) |
| Jam-or-Fold-Modell | `mathematics_of_poker.json` (Jam-or-Fold Game #1/#2, Schwellen mit Python) | **F** (spaeter) | Referenzkurve fuer `short_stack_open_shove_fraction` (Inventur W2) — aus dem MoP-Modell BERECHNEN statt externe Nash-Tabelle zu suchen | [0,1]-Spiel-Schwellen geschlossen, per Fraction nachrechenbar |

---

## 5. ECHT FEHLEND (nicht im Repo montierbar) — mit Ergaenzungs-Skizze

1. **Bankroll/RoR/Kelly als geprueftes Modul.** Die Formeln stehen als Python-STRINGS in
   `mathematics_of_poker.json` (R(b)=e^(−2μb/σ²), Kelly f=2p−1, RoRU, Halb-Bankroll-Regel), aber
   nirgends als importierbares, getestetes Modul — CLAUDE.md nennt die Bankroll/Varianz-Achse
   selbst „un-formalisiert". *Skizze:* `knowledge_base/math/bankroll_formulas.py` (~8 Funktionen
   aus den MoP-Eintraegen), Fraction-/Closed-Form-Referenzen (Kelly p=3/5 ⇒ f=1/5 exakt; RoR-
   Exponent an rationalen μ,σ²,b algebraisch), Anschluss an test_math_suite. Kategorie: Kontext/
   MESS (bewertet Sessions, nie Einzelentscheidungen). Aufwand ~1 Session.
2. **`reverse_implied_odds` ist defekt** (math.json verified:false, dataclass-Dekorator ohne `@`
   ⇒ TypeError). Kein neues Wissen noetig, nur ein Code-Fix + Verifikation — bis dahin bleibt der
   Baustein zu Recht draussen.
3. **Mehrgegner-Rueckschau-Equity** (`equity_vs_hands`): der Engine-Baustein fuer die 6-max-
   L-Stufe existiert nicht (nur vs EINE Hand / EINE Range). *Skizze:* MC-Erweiterung von
   `equity_vs_hand` auf eine Liste bekannter Holes (im Self-Play sind ALLE Holes bekannt);
   exakter Enumerations-Zweig fuer River/All-in als Referenz (Muster `_river_equity_exact`).
4. **Nash-Push/Fold-Referenzdaten** (externe validierte Tabelle a la HoldemResources) fuer
   `short_stack_open_shove_fraction`: nicht im Repo. *Skizze:* NICHT extern beschaffen, sondern
   aus dem MoP-Jam-or-Fold-Modell einmalig selbst berechnen (`research/jam_or_fold_solve.py`,
   CPU-Minuten) und als `data/jam_or_fold_reference.json` einfrieren; gegen die publizierten
   Grenzfaelle (S→0 ⇒ any-two) plausibilisieren.
5. **Rake-Realismus:** das Gym ist rake-frei (Knob rake=0, bewusst). Fuer eine Benchmark, die je
   auf echte Sites zielt (CoinPoker/GG), fehlt ein Rake-Modell je Site (Struktur + Cap als Daten).
   *Skizze:* kleines `data/rake_models.json` + der schon vorhandene Knob
   `pot_odds_required_equity_with_rake`; erst relevant, wenn ein Live-Ziel ansteht — bewusst
   dokumentierte Luecke, kein Blocker.

**Nicht fehlend, sondern bewusst ausgeschlossen (bestaetigt):** die 17 range-basierten Funktionen
(NICHT_VERDRAHTBAR — das Gym liefert Haende, keine Ranges), `effective_multi_street_required_equity`
(braucht den geplanten Einsatzplan), concepts.json (qualitativ). Der Ausschluss ist ehrlich und
bleibt richtig.

---

## 6. Knob-Register-Ergaenzungen (zusaetzlich zur Inventur-Tabelle)

| Knob | Quelle | Default | Schranken |
|---|---|---|---|
| BF_eff-Anteils-Formel | `tournament.py` | anteilig (validiert) | Form fix; voller BF verboten (refutiert) |
| ICM_LEAD_MARGIN | neu (Block A) | 0.15 wie LEAD_MARGIN | [0.10, 0.25]; Orakel-Knob ⇒ Improver-gesperrt |
| icm_pressure_mult-Staerke | `tournament.py:136` | Doktrin-9-Wert | aus DOKTRIN.md; nur mit Bedingungs-Test |
| MULTIWAY_INDEP_ANNAHME | neu (Block C) | Unabhaengigkeit | KEIN Knob — deklarierte Naeherung, NOTES.md-Eintrag |
| RAKE_MODELL | echt fehlend Nr. 5 | rake=0 | Mess-Konfig, nie Improver |

## 7. Empfohlene Reihenfolge

1. **Sofort, $0:** test_math_suite-Referenzen ins Orakel-Selbsttest-Modul importieren (Abschn. 4)
   + die `verify_expr`-Paare der `*_verified.json` als maschinelles E1-Netz ueber ALLE 66
   Kalkulationen laufen lassen (ein ~30-Zeilen-Runner; deckt die komplette Welle 1/2 vorab).
2. **Welle 1 wie geplant** (Inventur 1→3, 4+5, 6→8, 9+10) — dieser Abgleich aendert daran nichts.
3. **Block B (MESS-Stufe)** vor dem naechsten Gate-Lauf — die Gate-SE ist die teuerste ungepruefte
   Zahl des Systems.
4. **Block A (ICM/Turnier-Gym)** als eigene Disziplin — Arena existiert, Anschlussaufwand klein,
   erschliesst den validierten Turnier-Stack fuer die Schleife.
5. **Echt-fehlend Nr. 3 (equity_vs_hands)** zusammen mit Welle 2 (hand_id/Line) — macht die
   L-Stufe 6-max-faehig, der groesste Hebel fuer die 6-max-Benchmark.
6. Nr. 1 (Bankroll-Modul) und Nr. 4 (Jam-or-Fold-Referenz) opportunistisch; Nr. 5 (Rake) erst
   bei einem Live-Ziel.
