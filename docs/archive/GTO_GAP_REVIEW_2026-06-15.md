# Weg zu 100% GTO — Code-Review & Verbesserungs-Ladder

*Erstellt 2026-06-15 nach einem vollständigen Durchgang durch die Decision-Engine. Geordnet nach Hebel
Richtung GTO, nicht nach Aufwand. Liest sich als Begleiter zu `NOTES.md` (die gemessenen Gaps) und
`docs/STATE.md` (der Live-State).*

---

## 0. Die ehrliche Rahmung zuerst (sonst zielt der Rest ins Leere)

**„100% GTO" ist für die zwei Modi des Bots zwei verschiedene Dinge:**

- **Heads-Up NLHE:** GTO ist ein wohldefiniertes Objekt (ein im Wert eindeutiges Gleichgewicht). Aber
  niemand hat es je *exakt* erreicht — Slumbot, DeepStack, Supremus sind alle Approximationen. Das
  realistische Ziel ist **„von GTO innerhalb der Messgenauigkeit ununterscheidbar"** = near-zero
  LBR-Exploitability. Das ist erreichbar.
- **6-max:** GTO ist **prinzipiell nicht erreichbar** — multiplayer general-sum ⇒ Nash PPAD-hart,
  nicht eindeutig, No-Regret konvergiert nur zu einem CCE, nicht Nash (steht schon in
  `data/sessions/solvability_6max.md`). Hier ist „100% GTO" das falsche Ziel; das richtige ist
  **bounded exploitability**. Dieser Report behandelt deshalb primär HU.

**Der eine Satz, auf den alles hinausläuft:** GTO ist ein *global gekoppelter Fixpunkt* — die Ranges
müssen über den ganzen Spielbaum konsistent sein. Man kann sich GTO **nicht durch besseres lokales
Heuristik-Tuning annähern**, weil jede lokale Entscheidung von einer korrekten Range abhängt, die
selbst aus dem Gleichgewicht folgt. Man erreicht GTO nur, indem die Strategie *ein einziges
selbstkonsistentes Objekt* wird. Praktisch heißt das genau einen von zwei Wegen:

1. **Real-time Subgame-Resolving mit korrekten Ranges** (der DeepStack/Supremus-Weg) — im Repo als
   `strategy/resolver.py` schon **angelegt, aber unfertig + per Default AUS**.
2. **Ein offline trainiertes Self-Play-Blueprint** (Deep-CFR / CFVnet) — im Repo als `deep_cfr.py`
   gerüstet, bewusst zurückgestellt.

Der aktuelle Bot ist ein **heuristischer Floor + supervised Advisors + Exploit-Layer**. Das ist eine
gute, ehrliche Konstruktion — aber sie ist *strukturell* keine GTO-Strategie und kann es durch
Tuning auch nie werden. Die gemessenen **−160 ±75 bb/100 (paired) gegen die Solver-Oracle** (NOTES,
„DEFINITIVE TexasSolver head-to-head") sind nicht ein „fast GTO mit kleinen Lecks", sondern der
erwartbare Abstand einer Heuristik zum Gleichgewicht.

Die gute Nachricht: das Repo hat den richtigen Weg schon erkannt und teilweise gebaut. Der
**River-Resolver hat bereits −12.9 ±69.6** gemessen (NOTES MVP#2) — das ist das mit Abstand
GTO-näheste Ergebnis im ganzen Projekt. Der Rest dieses Reports ist im Kern: *macht diesen Weg fertig*.

---

## 1. Die Keystone-Schwäche: die Villain-Range ist keine Range

Das ist die wichtigste Einzelsache im ganzen Bot, weil **alles Postflop darauf steht.**

In [`strategy/bot.py`](../pokerbot/strategy/bot.py) `_villain_range` (Z. 481) + `_narrow` (Z. 502):

```python
def _villain_range(self, state):
    raises = self._preflop_raises(state)
    if raises >= 3:   return ps.range_top(0.10)
    if raises == 2:   return ps.range_top(0.20)
    ...
def _narrow(self, classes, board, hole, aggression):
    ...
    keep_frac = {0: 0.92, 1: 0.60, 2: 0.38}.get(aggression, 0.30)
    ranked = sorted(combos, key=lambda c: evaluate(board, list(c)))  # nach absoluter Stärke
    return ranked[:n]
```

Das ist **„die stärksten X% Hände nach absoluter Brettstärke"** — keine pokertheoretische Range. Konsequenzen,
die jede einzelne Postflop-Zahl verfälschen:

- **Keine Bluffs in der Villain-Range.** `_narrow` behält bei Aggression nur die *stärksten* Combos.
  Das Modell glaubt also: *wer auf Turn/River bettet, hat immer Value.* → Der Bot **over-foldet
  Bluffcatcher** (er denkt, er sei nie gegen einen Bluff) und **under-blufft selbst** (er denkt,
  Villain callt immer mit Value). Das ist exakt die Klasse von Leak, die im −160-Head-to-head
  „facing-bet DEFENSE / turn-river LINES" als Hauptbleed benannt ist.
- **Keine Draws gewichtet, keine Action-Lineage.** Eine echte Range entsteht aus den Aktionen
  (open → call → check-raise …), nicht aus einem statischen Stärke-Perzentil.
- **Die Equity (`equity_vs_range`) ist mathematisch sauber, aber gegen die falsche Verteilung** →
  jede MDF/Pot-Odds/Value-Schwelle danach ist auf Sand gebaut.

**Fix (das Fundament für fast alles andere):** ein **Bayesian action-consistent Range-Tracker** —
Start aus den Preflop-Ranges, dann pro Betting-Aktion ein Bayes-Update über die
Blueprint-/Solver-Policy (P(Aktion | Hand) gewichtet die Combos). Genau das ist die in
[`strategy/range_tracker.py`](../pokerbot/strategy/range_tracker.py) als „P0-proper refinement"
markierte, noch fehlende Postflop-Narrowing-Stufe. Heute ist `range_tracker` **nur preflop-line-aware**
(SRP → sb_open/bb_defend; 3bet → top 18%). Ohne diese Stufe kann **weder der Advisor noch der Resolver
GTO sein.**

> Ohne korrekte Ranges ist „mehr GTO" unmöglich. Mit ihnen fällt die Hälfte der anderen Punkte von
> selbst. **Das ist der höchste Hebel im Projekt.**

---

## 2. Den echten GTO-Pfad anschalten: der Resolver

[`strategy/resolver.py`](../pokerbot/strategy/resolver.py) ist der eigentliche Weg zu Postflop-GTO und
schon gut gebaut: er löst den **tatsächlichen öffentlichen River-State live mit TexasSolver bis zum
Terminal** (River = 1 Betting-Runde ⇒ **kein Value-Net nötig**, sauber exakt). In `bot.py` aber:

```python
self.use_resolver = False        # Z. 82 — river resolver AUS
self.use_turn_resolver = False   # Z. 83 — turn resolver AUS
```

Zwei Dinge blockieren ihn:

1. **Die Ranges, die reingehen, sind falsch** — `river_ranges()` liefert nur preflop-Linien-Ranges (wieder
   das Problem aus §1). Der Resolver löst also das *richtige Brett mit zu weiten Ranges* → er gibt die
   GTO-Strategie für ein *anderes Spiel* zurück.
2. **Er ist per Default aus** (richtig so, solange #1 offen ist).

**Fix (der direkte −160 → ≈0 Pfad):**
- Erst §1 (korrekte Continuation-Ranges) bauen, dann in `river_ranges` einspeisen.
- `use_resolver=True` (River zuerst — exakt lösbar, sauberster Win), dann `use_turn_resolver=True`
  (Turn→River-Subtree, größerer Baum, langsamer).
- Gaten über AIVAT / die paired `gto_oracle_match`. NOTES MVP#2 hat River-Resolver schon bei **−12.9**
  gemessen — das ist der Beweis, dass dieser Weg trägt.
- Latenz live: River-Solve ist ms–s; Turn-Solve teurer. Für eine reine GTO-Maschine ggf. Caching nach
  Board-Bucket + Linie.

**Das ist konkret der Übergang von „heuristik, die GTO-Frequenzen nachahmt" zu „spot-spezifisch GTO".**

---

## 3. Facing-Bet-Defense & Sizing — wo die bb/100 wirklich bluten

NOTES sagt explizit: der deterministische GTO-gap (31% Flop / 29% River) ist **frequenztreu** —
unsere Bet-vs-Check-*Frequenzen* matchen den Solver. Aber: *„the gap measures only bet-vs-check at the
lead/cbet nodes; it does NOT capture SIZING / facing-bet DEFENSE / turn-river LINES, where the real EV
leak sits."*

Im Code sieht man genau das:

- **Der Advisor feuert nur auf Bet-vs-Check-Knoten** (flop/turn/river, first-to-act/after-check). **Wenn
  der Bot einen Bet *facing* ist**, läuft die Heuristik: `call_thresh = req + MDF-shade`, Value-Raise ab
  `eq ≥ 0.72`, sonst Fold (`bot.py` Z. 290–328). D.h. der „GTO-gegroundete" Teil deckt **Betting ab, aber
  nicht Defending.** Defending ist die Hälfte des Spiels und hier rein heuristisch.
- **Sizing mischt nicht.** GTO nutzt mehrere Größen mit Frequenzen; der Bot bluff-bettet fix ~60% Pot,
  value über `pick_value_size`. NOTES-Leak #2: *„fold-equity-optimal sizing ≠ EV-optimal"* — `max(folds)`
  ist nicht `max(EV)`.
- **MDF-shade ist evtl. nicht EV-gegroundet** (NOTES-Leak #3): MDF ist gegen Underbluffer das falsche
  Modell.

**Fix:** Fällt größtenteils aus §1+§2 heraus — sobald der Resolver mit korrekten Ranges läuft, *ist* die
Facing-Bet-Antwort und das Sizing die GTO-Antwort (gemischt, range-vs-range). Bis dahin bleibt es eine
Heuristik, die per Konstruktion nicht GTO sein kann. **Nicht einzeln wegtunen — durch den Resolver
ersetzen.**

---

## 4. Preflop ist nicht GTO (und die beste Tabelle ist nicht mal eingebunden)

Überraschender Befund beim Durchgang:

- **Push/Fold (≤14bb)** in [`cfr_preflop.py`](../pokerbot/strategy/cfr_preflop.py) ist echtes MCCFR-Nash —
  **aber nur des JAM/FOLD-Abstraktionsspiels.** Es modelliert *nur* All-in oder Fold. Echtes GTO bei 14bb
  enthält Min-Raises, Limps, Non-Allin-3bets. Reines Push/Fold ist nur bis ~10bb wirklich GTO-nah.
- **Tiefere Stacks (>14bb)** in `bot.py` `_preflop` (`_bb_vs_open`, `_vs_3bet`, `_deep_reraise`) sind ein
  **Perzentil-Stärke-Heuristik-System** mit *festen* Sizings: 2.5bb open, 3.2× 3bet, 2.3× 4bet, feste
  Value/Bluff-Frequenz-Bänder. Keine Size-Mischung, keine GTO-Frequenzen.
- **Die distillierte 88.6%-PokerBench-Tabelle** ([`preflop_gto.py`](../pokerbot/strategy/preflop_gto.py))
  ist laut eigenem Docstring **nur in den 6max-RFI eingebunden — nicht in den HU-`bot.py`.** Der HU-Bot
  benutzt also seine schwächere Heuristik, obwohl die bessere Tabelle im Repo liegt.

**Fix:**
- `preflop_gto.py` in `bot.py._preflop` einbinden und um vs-open / vs-3bet / vs-4bet erweitern (Keys mit
  der Preflop-Action-Sequenz, wie im Docstring als „Step 4b" vermerkt).
- Mittlere Stacks: echte Preflop-Solves mit Open-Size- + 3bet/4bet-Bäumen und **Mischung**, statt fixer
  Sizes.
- Push/Fold: entweder das CFR-Spiel um Min-Raise/Limp-Linien erweitern, oder dokumentieren, dass es nur
  ≤~10bb GTO ist.

---

## 5. Die Advisors: ein Approximations-Pfad, kein GTO-Pfad

Die MLP-Advisors ([`strategy/advisor.py`](../pokerbot/strategy/advisor.py)) sind sauberer Glue über echte
Solver-Daten und sinnvoll. Aber als GTO-Mechanismus haben sie eine **Decke**, und der Grund steht in den
Features ([`strategy/features.py`](../pokerbot/strategy/features.py)) + NOTES-Leaks #1/#5:

- **Der Info-Set ist zu grob.** `_vector` kodiert: tier (air/medium/strong), 5 Texturen, role IP/OOP,
  ein paar Draw-Booleans, overcards, scalar strength. **Keine** Linie, **kein** SPR, **kein** Pot-Typ
  (SRP vs 3bet-Pot), **keine** Range-Asymmetrie. → K72r in BTN-vs-BB-SRP wird mit K72r im 3bet-Pot in
  *einen* Info-Set gemittelt (NOTES-Leak #1). GTO behandelt die völlig verschieden.
- **Trainiert auf P(bet)/MSE, nicht auf reach-weighted EV-gap** (NOTES-Leak #5): ein Netz kann die
  *Frequenz* matchen und trotzdem an seltenen High-EV-gap-Knoten bluten. Eine Frequenz-Übereinstimmung
  ist *nicht* GTO.
- **Coverage begrenzt:** Flop-Netz aus voller Coverage, Turn aus nur 46 Flop-Files (+ laufender Solve),
  River 1308 Boards. 3bet-Pots, mehrere Stacktiefen fehlen ganz.

**Fix (falls der Advisor-Pfad weiter verfolgt wird):** Linie/SPR/Pot-Typ/Position als Features;
Loss = reach-weighted EV-gap statt MSE; Solver-Coverage-Kampagne (RunPod/GCP mass-solve) für 3bet-Pots
+ Stacktiefen. **Aber ehrlich:** ein supervised Advisor *approximiert* GTO, er *ist* es nie. Für „100%"
ist er die zweitbeste Schiene hinter dem Resolver/Self-Play. Sinnvoll als schneller, breiter Floor und
als Fallback, wenn der Resolver eine Linie nicht lösen kann.

---

## 6. Verifikation — ohne sie ist jeder GTO-Claim wertlos

Man kann „nah an GTO" nicht *behaupten*, nur *messen*. Die Mess-Disziplin im Repo ist exzellent
(paired/duplicate, AIVAT-bewusst, Noise-Floors, Skinner-bewusste Reverts — siehe `scorecard.py`,
`duplicate.py`). Zwei Lücken bleiben, beide blockieren einen belastbaren GTO-Nachweis:

- **LBR ist nur v1 und range-blind** (NOTES „Move A"): die uniforme Card-Resampling-Variante *sieht eine
  korrumpierte Range nicht* (injizierter c-bet-air/river-overbluff → paired-delta ~0 trotz 99/300
  Feuern). Echtes GTO ⇔ near-zero Exploitability, und das certifiziert nur ein echter Best-Response.
  **Fix: LBR v2** — Bayesian action-consistent Range + multi-street Best-Response. Das ist das *einzige
  interne* Instrument, das „wie nah an GTO" ohne externen Key beziffern kann. (Hängt wieder an §1.)
- **GTO Wizard Key ist 401** (`benchmark/gtowizard.py` ist fertig + offline-getestet, blockt nur auf
  gültigem Key). AIVAT vs GTOW-AI ist der definitive externe Maßstab. **Fix:** gültigen Key besorgen,
  dann `--num-hands 2500` für die Leaderboard-Zahl. (User-Entscheidung — outward-facing, verbraucht Quota.)

---

## 7. Kleinere, konkrete Code-Beobachtungen (richtig, aber niedrigerer Hebel)

- **Equity-Noise:** `EQUITY_ITERS=1500` live, **120 in Benchmarks** (`floor_map`, `gto_oracle_match`). 120
  MC-Samples flippen dünne Pot-Odds-Entscheidungen — genau so ein Bug wurde am River schon gefunden und
  durch exakte Enumeration (`equity.py` Z. 49–57) behoben. Flop/Turn sind noch MC. Erwägen: suit-canonical
  Equity-Cache (steht als „Simplify Tier-A" in STATE.md) und höhere Bench-Iters für decision-grade Läufe.
- **Der Exploit-Layer ist korrekt GTO-neutral.** Das LCB-Gate (`exploit_engine.choose_river`) fällt bei
  dünnen Daten auf den Floor zurück (`cold-start → floor`), also *schadet* er der GTO-Nähe nicht — er ist
  orthogonal. Wichtig: gegen einen *echten* GTO-Gegner gibt es keine ausnutzbaren Folds, das Gate bleibt
  also am Floor. Gut so. (Für „100% GTO" würde man den Exploit-Layer ohnehin abschalten — er ist die
  *Anti*-GTO-Schiene für die ausbeutbare Feld-Population. Die zwei Ziele „GTO" und „max-exploit" sind
  verschiedene Knöpfe; der Bot trennt sie sauber über `exploit=True/False`.)
- **`value_raise_eq=0.72` + feste 0.8×Pot-Value-Raise** (`bot.py` Z. 307–311): Punkt-Schätzung, keine
  Mischung — wird vom Resolver ersetzt.
- **`_has_initiative` ist nur preflop-abgeleitet** (Z. 469): korrekt für SRP, aber in komplexeren Linien
  (float, delayed c-bet, probe) ist „Initiative" kein Boolean. Der Resolver braucht das Konzept gar nicht.

---

## 8. Die Ladder — geordnet nach Hebel Richtung GTO

| # | Schritt | Warum es GTO-Hebel ist | Hängt an |
|---|---------|------------------------|----------|
| **1** | **Bayesian action-consistent Range-Tracker** (Postflop-Continuation-Narrowing in `range_tracker.py`) | Fundament: ohne korrekte Ranges ist *nichts* GTO. Fixt Equity, Defense, Bluffcatch in einem. | — |
| **2** | **Resolver anschalten** (River, dann Turn) mit den korrekten Ranges aus #1; AIVAT-gegatet | *Der* echte Postflop-GTO-Pfad; River exakt lösbar; schon −12.9 gemessen | #1 |
| **3** | **Facing-Bet-Defense + Sizing** über den Resolver statt Heuristik | Wo die −160 real bluten (NOTES) | #1, #2 |
| **4** | **Preflop-GTO einbinden** (`preflop_gto.py` in HU-bot; vs-open/3bet/4bet; gemischte Sizes) | HU-Preflop ist aktuell Heuristik; die bessere Tabelle ist nicht mal verdrahtet | — |
| **5** | **LBR v2** (range-aware, multi-street) | Das einzige interne Instrument, das GTO-Nähe *zertifiziert* | #1 |
| **6** | **Advisor-Info-Set verbreitern** (Linie/SPR/Pot-Typ; EV-gap-Loss) + Solver-Coverage-Kampagne | Macht die Approximations-Schiene + den Fallback besser | Coverage-Compute |
| **7** | **GTO Wizard Key** → AIVAT-Leaderboard | Definitiver externer GTO-Maßstab | gültiger Key (User) |
| **8** | **Self-Play-Blueprint** (Deep-CFR/CFVnet, Leduc→NLHE) | Der *andere* prinzipielle GTO-Weg; teuer, daher zuletzt | RunPod-GPU |

**Wenn nur EINE Sache gemacht wird:** #1 (Range-Tracker). Es ist der Keystone, der #2/#3/#5 erst möglich
macht und für sich allein schon jede Postflop-Zahl korrigiert.

**Der realistische „so nah an GTO wie HU geht"-Pfad:** #1 → #2 → #3 → #5 (gaten) → #4. Das bringt den
gemessenen Abstand plausibel von −160 Richtung ≈0 vs Solver und macht den Claim *überprüfbar*.

---

## 9. Fazit in drei Sätzen

1. Der Bot ist eine *saubere, ehrlich gemessene Heuristik mit Exploit-Layer* — aber strukturell **keine**
   GTO-Strategie, und kein Maß an lokalem Tuning macht ihn zu einer; GTO ist ein global gekoppelter
   Fixpunkt, der nur über Resolving-mit-korrekten-Ranges oder Self-Play erreichbar ist.
2. Beide echten Wege sind im Repo **schon angelegt** (`resolver.py`, `deep_cfr.py`) und der Resolver hat
   bereits das GTO-näheste Ergebnis geliefert (−12.9) — er ist nur durch **eine fehlende Komponente
   blockiert: korrekte Postflop-Ranges** (§1).
3. „100% GTO" ist für HU als *„innerhalb der Messgenauigkeit / near-zero LBR"* realistisch erreichbar
   (Ladder oben) und für 6-max prinzipiell unmöglich (dort ist bounded exploitability das richtige Ziel).

*— Review-Pass über bot.py, advisor.py, resolver.py, range_tracker.py, postflop.py, gto_oracle.py,
exploit_engine.py, opp_model.py, equity.py, gto_baseline.py, features.py, preflop_gto.py, cfr_preflop.py,
floor_map.py, gto_oracle_match.py, scorecard.py + CLAUDE/STATE/NOTES.*
