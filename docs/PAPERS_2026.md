# PAPERS_2026.md — Triage der fuenf neuen 2026-Papers (2026-08-16)

Ordner: `books/papers/Poker Math 2026/`. Keines war zuvor im Repo (RESEARCH_SWEEP kennt nur
2605.19928 = Li&Huang-CFR, ein anderes Paper). Existenz aller fuenf lokal verifiziert (PyMuPDF).

## ★★★ Brown — *Value, Bluff, and Cyclic Dominance* (SSRN 6709840, 36 S.)
Loest das Von-Neumann-Wettspiel erstmals auf der ECHTEN 169x169-Equity-Matrix von HU-THE, ueber
alle Bet-Groessen, unter Fallenlassen aller drei VNM-Vereinfachungen gleichzeitig. Befunde:
- **106/169 Haende verhalten sich klassisch** (Value folgt roher Equity; Pivot-Ordnung Spearman 0,98).
- **Null Haende sind in allen vier Modellvarianten pure Bluffs** — die Bluff-AUSWAHL ist strukturell
  (Blocker/Nichtdeterminismus/Sizing), nicht durch eine Frequenz bestimmt.
- Zyklische Dominanz (RPS-Struktur) als Rahmen — die theoretische Fassung unserer Seesaw-Doktrin.
**Direkte Verwertung:** (1) neuer range-freier F/L-Check: Value-Bet-Ordnung vs rohe Equity;
(2) die 169x169-Matrix als Referenzobjekt fuer Preflop-Checks; (3) THEORIE-BESTAETIGUNG des
heutigen Gate-Ergebnisses: mdf_guard (Frequenz ohne Selektion) −3,26, sel_guard (Selektion) +13,8
Sanity — Brown sagt strukturell dasselbe: Bluff/Continue ist Auswahl, nicht Quote.

## ★★★ SPIRAL — Self-Play on Zero-Sum Games (ICLR 2026, 28 S.)
LLM-Self-Play auf Zero-Sum-Spielen (u.a. Kuhn Poker) gegen sich selbst verbessernde Kopien =
Auto-Curriculum ohne menschliche Labels; **role-conditioned advantage estimation (RAE)**
stabilisiert Multi-Agent-LLM-RL; schlaegt SFT auf 25k Experten-Trajektorien, +10% Transfer auf
8 Reasoning-Benchmarks (Qwen+Llama). **Direkte Verwertung:** die Antwort auf unsere offene
RL-Frage (GLM-GRPO-Regression: Liga-Reward war falsch) — Self-Play-Curriculum + RAE ist der
Kandidat fuer den 'besseren Reward', den STATE.md fordert. Deep-Read vor jedem neuen RL-Lauf.

## ★★ Diniz — *Learning Strategic Poker Decision-Making with LLMs* (Master-Arbeit UFU, 91 S.)
LLM-Poker-Entscheidungslernen; vermutlich PokerBench-nah. Scan lohnt fuer Dataset-/Eval-Ideen
des LLM-Zweigs; kein Blocker fuer den Autogym-Pfad.

## ★ SCORE Method (SSRN 6297138, 12 S.)
Vereinfachte Pot-Odds-Heuristik mit eingebautem konservativem Rand — fuer MENSCHEN unter
Zeitdruck. Fuer den Bot irrelevant (wir rechnen exakt); nutzbar im COACHING-Track (User-Spiel)
und ggf. als dokumentierter konservativer Naeherungs-Check im Orakel (Knob).

## ○ 2605.22972 — *Balancing relational generalization and memorization* (Columbia, 39 S.)
KEIN Poker-Paper (theoretische Neurowissenschaft/ML). Tangential relevant fuer die
Generalisierung-vs-Memorisierung-Frage der v4-Value-Nets; im Poker-Ordner vermutlich fehl
einsortiert. Ehrlich: niedrige Prioritaet.

**Empfohlene Reihenfolge:** Brown deep-read + Check-Extraktion (naechste Benchmark-Welle) →
SPIRAL deep-read vor dem naechsten RL-Lauf → Diniz-Scan → SCORE bei Coach-Arbeit.
