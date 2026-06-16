# Fundamentaler GTO-Schritt: P0 Range-Tracker gebaut, getestet, verdrahtet — und ein falscher Konsens gefangen

*2026-06-15. Session-Deliverable. Ich (Claude) habe selbst fundiert am Bot gearbeitet, nicht nur konsultiert.
Dies dokumentiert was gebaut/verifiziert wurde, den entscheidenden Verify-Everything-Fund, und — wichtig — was
**noch nicht gemessen** ist (die Skinner-Disziplin verlangt diese Trennung).*

---

## 0. Was angefordert war

„Bring den Poker-Bot deutlich näher in Richtung GTO, auch fundamental. Fahr alle APIs + unser Programm hoch.
Geh tiefer in die neuesten Dateien." → Ich bin zuerst in die *neuesten* Dateien gegangen (die GTO-Consults
gpt-5.5/o3 + der `MVP2_RESOLVER_PLAN`), habe dann die APIs **fundiert** (auf das eine offene Teilproblem, nicht
auf „wie GTO?" — das war schon beantwortet) gefeuert, und dann **selbst implementiert + getestet**.

---

## 1. Die konvergente Diagnose (drei unabhängige Quellen, derselbe Befund)

Die −160 bb/100 vs TexasSolver sind **Abstraktions-Fehler**, kein Frequenz-Problem. Drei Quellen, unabhängig:

- **Meine eigene GTO-Review** ([GTO_GAP_REVIEW_2026-06-15.md](GTO_GAP_REVIEW_2026-06-15.md)) → Keystone =
  Bayes-Range-Tracker, dann Resolver.
- **o3** (`situational_reason_o3.md`): CFR-Dekomposition — Bucket-Marginal-Frequenzen matchen lässt
  `Σ π·δ·v` unbeschränkt genau bei Sizing/SPR/Range-Asymmetrie.
- **gpt-5.5** (`situational_poker_gpt55.md`): Hybrid = Blueprint + targeted Resolving, **River-first**,
  getrieben von einem Range-Tracker.

Der `MVP2_RESOLVER_PLAN` macht daraus den Plan; **P0 (der Range-Tracker) ist der Linchpin** und war bis heute
nur ein Preflop-Stub. Der Plan warnt explizit: *„a bad range reconstruction makes the resolver WORSE than the
floor."* → P0 richtig zu bauen ist die fundamentale Voraussetzung für *jeden* GTO-Fortschritt postflop.

> Drei-Quellen-Konvergenz ist ein Pidgeon-Signal. Aber hier steht sie auf o3's CFR-Beweis + gemessenen Zahlen,
> nicht auf Begeisterung. Die ehrliche Konsequenz: die APIs **nicht** nochmal auf „wie GTO?" feuern (Verschwendung)
> — sondern auf das *offene* Teilproblem, das der Plan überspringt.

---

## 2. Der fundierte Consult (das offene P0-Teilproblem)

`extraction/range_tracker_consult.py` → 4 APIs parallel auf die genaue Lücke: **wie baut man die Bayes-Range-
Update, wenn das Blueprint nur P(bet) liefert** (nichts für facing-bet call/fold/raise oder bet-size)?
Antworten in `docs/range_tracker_consult_{o3,claude,perplexity,venice}.md`. Konvergente Synthese:

- **o3 (Sicherheits-Theorem):** nur reweighten wo ein Modell existiert (bet/check via Advisor); für die
  *stillen* Aktionen **legality-only** (mit 1 multiplizieren, nie mit 0 außer logisch unmöglich). Dann kann
  `‖tracked − true‖₁` nur sinken → injizierte Exploitability ≤ (CapPot/2)·L1, **beschränkt**. Eine schlecht-
  genarrowte Range (zeroing live combo) ist **unbeschränkt** schlimmer. „Do nothing unless certain."
- **Fidelity-Budget:** Villain-Range ≫ eigene Range (o3-Bound: eigener Fehler oft = 0 für die tatsächlich
  gehaltene Hand am River).
- **Confidence-Gate:** bei unsicherer Rekonstruktion auf den Floor zurückfallen (Claude).
- **Venice (red-team):** der billige Vorab-Test — korreliert P(bet) überhaupt mit optimalem Spiel? (Ja: Advisor
  ist solver-trainiert, Floor matcht Solver-Frequenzen.)

---

## 3. Was ich gebaut habe

### `pokerbot/strategy/range_tracker.py` — der v2 RangeTracker (der Keystone)
Per-combo Bayes-Tracker, o3's beweisbar-sichere v0:
- **bet/check** → reweight per Advisor-`P(bet)` (das einzige echte Modell).
- **call/raise/bet-size (still)** → legality-only (Gewicht unverändert), zählt gegen Confidence.
- **fold** → beendet die Hand (kommt in einer lebenden Linie nicht vor).
- exakte per-combo Dead-Card-Removal pro Street; Normalisierung; Weight-Floor 1e-6.
- **Confidence** = `1 − 0.5·heuristic_ratio`, gedeckelt nur bei *echtem* Kollaps (effektive Combos < 10, via
  inverse Herfindahl — **nicht** via absolutem Gewichts-Schwellwert; eine breite Range hat winzige per-combo
  Gewichte ~1/N und würde sonst fälschlich als kollabiert geflaggt — diesen Bug habe ich gefangen + gefixt).

### Verdrahtung: `pokerbot/strategy/bot.py`
`_river_resolve` + `_turn_resolve` nutzen jetzt `weighted_ranges(state)` (linien-bewusste getrackte Ranges)
statt des Preflop-Stubs, mit **Confidence-Gate**: `conf < 0.5 → return None → Floor` (safe-by-construction).
Alles hinter dem bestehenden `use_resolver` (per Default AUS) → kein Einfluss auf Live-Spiel / bestehende Tests.

---

## 4. ⚠ Der entscheidende Verify-Everything-Fund (die Pidgeon-Disziplin in Aktion)

**Alle vier APIs behaupteten übereinstimmend: „per-combo weighted ranges (`AsKh:0.62`) sind Standard und
funktionieren mit TexasSolver."** o3 sagte sogar „~20 ms Overhead, zero approximation error."

**Das ist FALSCH für unseren TexasSolver v0.2.0-Build.** Mein End-to-End-Test gegen den echten Binary zeigte:
- class-level Ranges → 58 Strategie-Keys, `strategy_for` funktioniert ✓
- per-combo Ranges → Solver produziert **gar keinen Output** (crasht) oder einen **leeren** per-combo
  Strategie-Dump (`num strategy keys: 0`) → der Resolver kann unsere Aktion nicht lesen ✗

Vier Modelle, selbstbewusst konvergent, **falsch**. Hätte ich es nicht gegen den echten Build getestet, hätte
ich einen Tracker ausgeliefert, der den Solver still mit leeren Strategien füttert. **Das ist exakt die Lektion,
die NOTES.md wieder und wieder dokumentiert** („verify everything", „the unpaired +184 was noise").

**Fix:** der Tracker bleibt intern per-combo (Advisor-P(bet) + exakte Dead-Card-Removal), **aggregiert aber beim
Emit auf class-level gewichtete Strings** (`AQs:0.62,KQo:0.31,...`). TexasSolver expandiert intern + keyt den
Dump per-combo → `strategy_for(node, hero_c1, hero_c2)` funktioniert wieder. Kosten: within-class Gewichts-
Variation geht verloren (eine echte Solver-Constraint, keine Wahl); der Solver macht Card-Removal weiterhin.

### Nebenbefund + Fix: `gto_oracle.py` Null-Crash
Tiefe Knoten / fehlgeschlagene Solves haben `"strategy": null`. `_key`/`strategy_for` crashten darauf
(`AttributeError`) statt sauber `None` zu liefern. Null-safe gemacht (`(x or {})`) → der Resolver floored
anmutig statt live zu crashen wenn man ihn anschaltet. (Gefunden via die End-to-End-Smoke.)

---

## 5. Verifikation (was tatsächlich läuft)

**Unit-Tests** `tests/test_range_tracker.py` (4/4 grün) — die P0-Gate-Checks aus dem Consult:
- Mass-Conservation (Summe→1) + Dead-Card-Exclusion
- Monotone Shrinkage die Linie hinunter (Support wächst nie)
- Confidence ≥ Gate auf einer normalen SRP-River-Linie (0.83) + class-Gewichte sind non-uniform (Advisor
  reweightet wirklich, Spread 0.42..1.0)
- Safety: eine call-schwere Linie zeroet **nie** eine lebende Combo (o3's Theorem)

**End-to-End-Smoke** `extraction/smoke_weighted_resolve.py` (grün, gegen den echten TexasSolver):
- [1] class-level getrackte Ranges lösen → **709 per-combo Strategie-Keys** (non-empty Dump)
- [2] Resolver feuert auf OOP-first-Knoten → `('bet', 330)`
- [3] Resolver feuert auf IP-nach-Check-Knoten → `('check', None)`

→ **Die komplette P0→P1-Pipeline läuft mechanisch end-to-end:** getrackte Ranges → TexasSolver → lesbare
per-combo Strategie → gesampelte GTO-Aktion für unsere Hand, auf beiden River-Knotentypen.

**Regression:** `test_game` (300 Hände, alle Invarianten), `test_bot`, `test_range_tracker` — alle grün. Der
Resolver ist per Default aus → Live-Spiel unverändert.

---

## 6. EHRLICHER STATUS — was NICHT gezeigt ist (Skinner-Disziplin)

Ich habe den **Mechanismus** gebaut und verifiziert: der Keystone (P0) ist gebaut, getestet, verdrahtet; die
Pipeline läuft end-to-end; sie ist safe-by-construction (Gate → Floor). **Ich habe NICHT gemessen, dass der Bot
dadurch näher an GTO spielt.** Konkret nicht gezeigt:

- **Keine EV-Recovery gemessen.** Ob der Resolver mit getrackten Ranges die −160 bb/100 vs TexasSolver
  reduziert, ist **offen**. Das verlangt den P1-Gate: **paired/duplicate ≥1000 Hände vs TexasSolver** (Stunden
  Live-Solve-Compute) **+ ein frischer GTO-Wizard-AIVAT-Lauf**. Beides ist *nicht* in dieser Session gelaufen.
- **Range-Tracker-Treue ungemessen.** Die Tests zeigen Konsistenz (Summe, Shrink, Safety), **nicht** dass die
  rekonstruierten Ranges nah an den *wahren* Ranges sind. Der Consult-Validierungsweg (Solver-Cross-Check auf
  kanonischen Spots) ist noch nicht gebaut.
- **class-level verliert within-class-Treue.** Ein erzwungener Kompromiss (Solver-Constraint) — Effekt auf die
  Resolve-Qualität ungemessen.
- **Nur River end-to-end smoke-getestet.** Turn-Resolver ist verdrahtet aber nicht end-to-end validiert.

> Klartext: Ich habe **den blockierenden Keystone gebaut und bewiesen, dass er den Solver korrekt füttert** —
> das ist echter fundamentaler Fortschritt auf dem GTO-Pfad. Ich habe **nicht** bewiesen, dass der Bot jetzt
> weniger verliert. „Der Resolver feuert" ≠ „der Bot ist näher an GTO". Diese Trennung ist der ganze Punkt.

---

## 7. Konkrete nächste Schritte (in Reihenfolge)

1. **P1-Gate (die Messung, die alles entscheidet):** `use_resolver=True`, paired/duplicate ≥1000 Hände
   Floor vs Floor+River-Resolver vs TexasSolver. Recovert es >2σ (Ziel +30 bb/100, gpt-5.5's Korridor)?
   → behalten. Wenn <15 → Range-Tracker/Abstraction/Integration falsch, oder Diagnose unvollständig.
2. **Range-Tracker-Validierung:** Solver-Cross-Check auf 10-20 kanonischen Spots (Consult §4) — fängt eine
   schlechte Rekonstruktion *bevor* sie still den Resolver verschlechtert.
3. **Facing-Bet-Knoten:** der größte gemessene Bleed (~55 bb/100, gpt-5.5). Aktuell deckt die River-Smoke
   first-to-act + after-check; facing-a-bet (call/fold/raise) braucht eigene Resolve-Rooting-Validierung.
4. **Turn-Resolver** end-to-end (analog zur River-Smoke), dann sein eigener P1-Gate.
5. **GTO-Wizard-Key** (401-blocked) → AIVAT ist die definitive externe Zahl.

---

## 8. Geänderte / neue Dateien

**Neu:** `pokerbot/strategy/range_tracker.py` (v2 Tracker — komplett), `tests/test_range_tracker.py`,
`extraction/range_tracker_consult.py`, `extraction/smoke_weighted_resolve.py`,
`docs/range_tracker_consult_{o3,claude,perplexity,venice}.md`, diese Datei.
**Geändert:** `pokerbot/strategy/bot.py` (`_river_resolve`/`_turn_resolve` → getrackte Ranges + Confidence-Gate),
`pokerbot/strategy/gto_oracle.py` (Null-Safety in `_key`/`strategy_for`).

---

## 9. Fazit

Der **fundamentale Block** (P0 Range-Tracker) ist gebaut, getestet, verdrahtet — und die per-combo→class-level
Solver-Constraint ist gefangen, die ein vierfacher API-Konsens falsch behauptet hatte. Die GTO-Pipeline läuft
jetzt mechanisch end-to-end. **Der nächste Schritt ist nicht mehr Code — es ist die Messung** (P1-Gate), und bis
die läuft, ist „näher an GTO" eine begründete Erwartung, kein Ergebnis.

*— Gebaut + verifiziert gegen den echten TexasSolver v0.2.0-Build. Consults: o3 + gpt-5.5/5.1 + Claude +
Perplexity + Venice. Tests + Smoke grün; EV-Gate offen.*
