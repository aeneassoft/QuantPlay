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

## ★★ Diniz — *Learning Strategic Poker Decision-Making with LLMs* (Master-Arbeit UFU, 91 S.; gescannt 2026-08-16)
**Was gebaut/gemessen wurde:** reine SUPERVISED-PREDIKTION auf **PokerBench** (JA, direkt genutzt:
~63k preflop / ~500k postflop Train, 1k/10k Eval, Original-Splits, 100bb-Fixstacks; Labels = GTO Wizard
preflop + WASM-Postflop postflop). 6 offene LLMs few-shot verglichen (bestes: **Qwen3-14B**, preflop
76,1% / postflop 51,5% Action-Acc), dann Qwen3-14B per LoRA/QLoRA je Stage SFT-adaptiert →
**93,3% preflop / 91,8% postflop** (McNemar p<0,001, OR 5,9/14,9). Kein Spiel, kein EV, keine
Exploitability, keine ganzen Haende — nur Label-Agreement an isolierten Zustaenden (die Arbeit sagt
das selbst explizit). Publikationen: ENIAC 2025, BRACIS 2026, "PokerLLM" (IEEE ToG eingereicht).
**Methodik-Kern (das eigentlich Verwertbare):** (1) **Hybrid-Pipeline** — Aktion via Next-Token-
LOG-PROB-SCORING ueber die LEGALEN Aktionen (deterministisch, kein Parsing-Fehler als Policy-Fehler),
Sizing separat per Greedy-Generation + numerischem Parser; (2) **Ac-s-Metrik** — kontinuierliche
Action-and-Sizing-Accuracy: korrekte aggressive Aktion bekommt proportionalen Sizing-Kredit
(skalen- und richtungssymmetrisch), plus konditionaler Sizing-Score NUR nach korrekter Aktion
(gemessen: 0,994/0,992 — d.h. der Rest-Fehler ist AKTIONS-Wahl, nicht Sizing-Kalibrierung).
**Fuer unser Dataset-Format faellt ab:** (a) bestaetigt unsere format_spot/PokerBench-Ausrichtung;
(b) der Logprob-ueber-legale-Aktionen-Evaluator + Ac-s sind direkt in `training/qwen_eval.py`
uebernehmbar (sauberere Token-Acc als exaktes String-Matching); (c) Ablationen: Persona fast egal,
Prompt-STRUKTUR und Logprob-Scoring tragen; preflop-Sizing ist temperatursensibel → greedy.
**Ehrlich:** bestaetigt unsere Imitation-Ceiling-Doktrin — 93% Label-Agreement ohne einen einzigen
gemessenen bb. Kein Blocker, kein neuer Hebel fuer den Autogym-Pfad.

## ★ SCORE Method (SSRN 6297138, 12 S.; komplett gelesen 2026-08-16)
**Die Heuristik als Formel:** `SCORE = outs × (Pot/Call)`; Call iff SCORE > 50 (Turn) bzw. > 25 (Flop).
Algebraisch exakt aequivalent zur Pot-Odds-Ungleichung n/N ≥ C/(P+C) umgestellt zu
`n·P/C ≥ N−n` — der EXAKTE Turn-Schwellwert ist also **46−n** (variiert mit den Outs); die fixe 50
liegt IMMER darueber. **Konservativer Bias quantifiziert:** Zusatzanforderung an Pot/Call =
`Δ = 50/n − (46−n)/n = 1 + 4/n` (n=4: +2,0 Pot/Call ≈ +1,7pp Equity; n=9: ≈ +0,95pp; n=15: ≈ +0,46pp);
gewichtet ≈ **+1pp**, groesster Schutz bei wenigen Outs. Simulation 10^7 Spots: 97,1/97,5% Konkordanz,
**null falsche Calls** (Abweichung nur in Fold-Richtung), verworfene Calls im Mittel +$0,43 EV (Rake
frisst das). **Passt als Orakel-KNOB? JA, eng begrenzt:** als dokumentierter EINSEITIGER Naeherungs-
Check auf Stufe L/F ("SCORE-Fold ⟹ exakter Fold ODER marginaler Call ≤ Δ-Band") — die Schranke
`46−n ≤ SCORE < 50` ist als Fraction exakt pruefbar. NIE als HART-Referenz (kein Fraction-Ersatz,
absichtlich verzerrt). **Ehrliche Grenze der Flop-25:** die Herleitung setzt ZWEI Karten fuer EINEN
Call-Preis an (exakt ≈ 23−n/2) — konservativ nur relativ zu diesem Implied-Odds-freundlichen Modell;
gegen die Ein-Strassen-Rechnung (Rule-of-2) ist 25 LIBERAL. Fuer den Bot bleibt exakt rechnen Pflicht;
Hauptnutzen = COACHING-Track (menschentaugliche 3-Operationen-Regel mit bekanntem ±1pp-Bias).

## ○ 2605.22972 — *Balancing relational generalization and memorization* (Columbia, 39 S.)
KEIN Poker-Paper (theoretische Neurowissenschaft/ML). Tangential relevant fuer die
Generalisierung-vs-Memorisierung-Frage der v4-Value-Nets; im Poker-Ordner vermutlich fehl
einsortiert. Ehrlich: niedrige Prioritaet.

**Empfohlene Reihenfolge:** Brown deep-read + Check-Extraktion (naechste Benchmark-Welle) →
SPIRAL deep-read vor dem naechsten RL-Lauf → Diniz-Scan → SCORE bei Coach-Arbeit.
