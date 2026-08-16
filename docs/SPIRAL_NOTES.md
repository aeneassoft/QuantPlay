# SPIRAL — Vollextraktion (ICLR 2026)

**Paper:** Liu, Yu, Liu, Guertler et al., *SPIRAL: Self-Play on Zero-Sum Games Incentivizes Reasoning
via Multi-Agent Multi-Turn Reinforcement Learning*, ICLR 2026. Code: `github.com/spiral-rl/spiral`.
Quelle: `books/papers/Poker Math 2026/ICLR-2026-spiral-...pdf` (28 S., komplett per fitz gelesen, 2026-08-16).
Kontext für uns: unser Liga-Reward-GRPO regredierte gemessen auf **−90 vs GTOW** (Selbstspiel-Liga ≠ GTOW,
das RL lernte liga-schlagende Aggression). SPIRAL ist der Kandidat für den besseren Reward-Aufbau.

---

## 1. Das Self-Play-Setup (exakt)

- **Spiele:** drei Zwei-Spieler-Nullsummenspiele aus TextArena: **TicTacToe** (räumlich, perfekte
  Information), **Kuhn Poker** (probabilistisch, versteckte Information), **Simple Negotiation**
  (strategische Optimierung, Ressourcenhandel). Formal: Sammlung G = {G1..Gn}, jedes Gi ein
  Zwei-Spieler-Nullsummen-Markov-Spiel auf **Turn-Level-MDPs** (Zustand = kompletter Kontext,
  Aktion = komplette Multi-Token-Antwort, nicht Token-Level).
- **Gegner = sich verbessernde Kopien:** EIN geteiltes Policy-Netz πθ spielt BEIDE Rollen
  (θ0 = θ1 = θ). Rollen-Konditionierung über den System-Prompt ("You are Player 0/1"). Dadurch
  **Auto-Curriculum**: verbessert sich das Modell in einer Rolle, wird sein Gegner automatisch
  gleich stark — kein statischer Gegner, der ausgebeutet werden kann.
- **Nullsummen + sparse Reward:** r = 0 auf allen Nicht-Terminal-Zuständen; am Ende
  R0(τ) = ρ(sT) ∈ {−1, 0, +1}, R1(τ) = −R0(τ). Kein Reward-Shaping, keine Zwischenbelohnung.
- **Voll online, Multi-Agent, Multi-Turn:** verteilte Actor-Learner-Architektur (auf Oat aufgebaut,
  IMPALA-Stil), vLLM für die Inferenz, TextArena als vektorisierte Spielumgebung; K parallele Actors
  sammeln Trajektorien, ein zentraler Learner macht synchrone Full-Parameter-Updates (kein LoRA,
  kein Offline-Batch). Spiel pro Rollout zufällig aus G gezogen.
- **Hyperparameter (Tabelle 6):** 400 Steps × 128 Samples, 8×H100 (~25 h Qwen3-4B / 28 h 8B),
  AdamW (β 0.9/0.95), LR 1e-6 konstant, Temperatur 1.0, max. 8192 Antwort-Tokens, Batch 128,
  Discount γ=1, **EMA-Decay α=0.95**, KL-Koeffizienten 0.0, PPO-Clip 0.2, 2 innere Epochen,
  Grad-Clip 1.0. Trainierte Modelle: Qwen3-4B/8B-Base, Octothinker-8B-Base, Llama-3.1-8B-Instruct,
  DeepSeek-R1-Distill-Qwen-7B, Qwen3-4B-Instruct-2507.

**Der zentrale Curriculum-Befund (Tab. 3 + Fig. 5):** Training gegen FIXE Gegner scheitert.
Random-Gegner → Kollaps; Mistral-Small-3 als Gegner → Benchmark-Schnitt **29.6 (SCHLECHTER als die
Basis 34.0)**; Gemini-Flash-Lite als Gegner → 33.4. Die Winrate vs Gemini steigt 0% → 62.5%
(= Ausbeutung der statischen Strategie), während Self-Play konstant 50–52% gegen die eigene Kopie
(t−16) hält — das Modell lernt weiter, statt einen Fixpunkt auszubeuten. **Das ist strukturell exakt
unsere −90-Regression: Liga schlagen ≠ besser werden.**

## 2. Role-conditioned Advantage Estimation (RAE)

**Formel (Gl. 2):** pro Spiel G und Rolle p ∈ {0,1} eine separate Baseline, per EMA aktualisiert:

```
b_{G,p} ← α · b_{G,p} + (1−α) · R_p(τ)          (α = 0.95)
A_{G,p}(τ) = R_p(τ) − b_{G,p}
```

Policy-Gradient (Gl. 3) = REINFORCE über volle Antworten, mit A_{G,p} statt Roh-Return:

```
∇J = E_G E_τ [ Σ_p Σ_{t∈T_p} A_{G,p}(τ) · ∇ log πθ(y_t | s_t, p, G) ]
```

Bewusst KEINE Längen-Normalisierung (Length-Bias, Verweis auf Dr.-GRPO-Kritik Liu 2025c).

**Warum es Multi-Agent-LLM-RL stabilisiert:**
1. **Ein Netz optimiert entgegengesetzte Ziele** (R1 = −R0) — dieselben Gewichte bekommen Gradienten
   in beide Richtungen; ohne Zentrierung ist die Varianz enorm, zusätzlich ist die Umgebung
   nicht-stationär (der Gegner ist die eigene, sich ändernde Policy).
2. **Rollen-Asymmetrien:** verschiedene Rollen haben verschieden hohe erwartete Returns
   (Erstzug-Vorteil TicTacToe, Informations-Asymmetrie Kuhn Poker). Eine globale Baseline vermischt
   das; die rollen-spezifische Baseline entfernt den positionsbedingten Anteil aus dem Signal —
   der Gradient reflektiert LERNEN, nicht die inhärente Positions-EV.
3. **Gemessene Ablation ("Thinking Collapse", Fig. 6+9):** ohne RAE bricht das Denken nach ~100–200
   Steps katastrophal zusammen — Reasoning-Traces fallen von ~2.000 Zeichen auf ~0 (degenerierte
   Outputs wie `\boxed{bet}`), Mathe-Score stürzt 35% → 12%, die Gradienten-Normen spiken erratisch
   und kollabieren dann auf ~0 (degenerierte Policy). Mit RAE: stabile Längen 1.300–1.500,
   Gradienten-Norm stabil ~0.1, Benchmark 40% → 47%.

## 3. Alle Zahlen

**Haupttabelle (8 Benchmarks: MATH500, AIME24, AIME25, OlympiadBench, AMC-23, Minerva Math,
GPQA-Diamond, MMLU-Pro; Durchschnitt):**

| Modell | Basis | SFT-Multi (25k) | SPIRAL-Multi | Δ vs Basis |
|---|---|---|---|---|
| Qwen3-4B-Base | 34.0 | 39.7 | **44.5** | **+10.5** |
| Qwen3-8B-Base | 39.5 | 46.1 | **49.6** | **+10.1** |
| Octothinker-8B-Base | 25.8 | 27.0 | **33.8** | +8.0 |
| Llama-3.1-8B-Instruct | 23.9 | 25.0 | **25.9** | +2.0 |
| DeepSeek-R1-Distill-Qwen-7B | 60.4 | 58.3 (−2.1!) | **61.8** | +1.4 |
| Qwen3-4B-Instruct-2507 | 74.1 | 71.9 (−2.2!) | **75.9** | +1.8 |

- **vs SFT-25k:** die SFT-Daten sind 25.000 GEWINNER-Trajektorien aus Qwen3-32B-Self-Play (Experte).
  SPIRAL schlägt SFT auf allen 8 Benchmarks. **SFT-52k (verdoppelt) bringt NICHTS** (39.7 → 39.7)
  — der Gewinn kommt aus der RL-Dynamik, nicht aus der Datenmenge. Auf bereits starken Modellen
  (R1-Distill, 4B-Instruct) REGREDIERT SFT sogar, SPIRAL verbessert weiter.
- **Nur Kuhn Poker (SPIRAL-Kuhn):** 43.4 — ein einziges 3-Karten-Spiel schlägt SFT auf 25k
  Experten-Trajektorien (39.7).
- **Fixe Gegner (Kuhn):** Mistral-Gegner 29.6, Gemini-Gegner 33.4, beide ≤ Basis 34.0.
- **Spezialisten-Transfer (Tab. 4):** Poker-Spezialist gewinnt **91.7% Pig Dice** (Risiko/EV-Spiel,
  nie gesehen); TicTacToe-Spezialist 56.0% Snake; Negotiation 55.8% Truth-and-Deception.
- **Multi-Game vs Gemini-2.0-Flash (Tab. 5):** 59.5% Schnitt vs bester Spezialist 52.9%.
- **OOD-Komplexität (Tab. 8):** 5-Card Kuhn Poker: SPIRAL 50.1 vs SFT 28.6 vs Basis 21.9 —
  Self-Play generalisiert auf das größere Spiel, Imitation nicht.
- **Reasoning-Muster-Transfer (Fig. 4, GPT-4.1-klassifiziert, 290 Spiele + 46.792 Mathe-Lösungen):**
  Case-by-Case-Analyse 72% (Spiel) → 71% (Mathe, nahezu perfekt), Pattern Recognition 35% → 45%
  (verstärkt), EV-Berechnung 78% → 28% (selektiv). Mathe-Score parallel 31.2 → 39.6.
- **Als Mid-Training-Stufe (Tab. 12):** RLVR→SPIRAL 47.9 > SPIRAL→RLVR 46.5 > RLVR 46.0 > SPIRAL 44.5.
- **Robustheit:** 3 Seeds (14/42/100): SPIRAL 44.5 ± 0.5 vs SFT 39.6 ± 0.4.
- **Trajektorien-Statistik (Tab. 11):** über das Training steigt die Spiellänge 1.7 → 9.6 Züge und
  P1-Winrate 42.7% → 62.4% (das Modell lernt den Positionsvorteil zu nutzen); Winrate vs
  Gemini-2.0-Flash 12.5% → 67.4%.

## 4. Kuhn-Poker-Details

- **Umgebung (TextArena):** "5 round game of Kuhn Poker". 3-Karten-Deck J/Q/K (J niedrigste),
  jeder Spieler antet **1 Chip pro Runde** und bekommt 1 Karte; 5 Runden; **wer nach allen Runden
  die meisten Chips hat, gewinnt das Match**. Aktionen als Klammer-Tokens: `[check]`, `[bet]`
  (1 Chip), `[call]`, `[fold]`.
- **Reward:** NUR terminal auf Match-Ebene: ρ(sT) ∈ {−1, 0, +1} für den Match-Ausgang (nicht pro
  Runde, nicht Chip-proportional!), Nullsumme R1 = −R0. Alle Zwischenzüge Reward 0.
- **Rollen:** Player 0 / Player 1 per System-Prompt konditioniert; aktiver Spieler p = t mod 2.
  Rollen-Asymmetrie (wer zuerst handelt / Informationsfluss) ist genau das, was RAE herausrechnet.
- **Trajektorien-Format:** pro Zug generiert das Modell
  `y_t = <think>c_t</think><answer>a_t</answer>` — c = externalisiertes Reasoning, a = die Aktion
  (per extract_action geparst). Der Gradient läuft über die VOLLE Sequenz y (Denken + Aktion),
  gewichtet mit dem Match-Advantage.
- **Partielle Beobachtbarkeit:** die Historie aller Aktionen wird in den Zustand s_t konkateniert
  (Markov-Repräsentation trotz versteckter Karte).
- Beobachtete gelernte Muster im Kuhn-Spiel: explizite EV-Rechnung ("EV(call) = 0×2 − 1×2 = −2 <
  EV(fold) = −1 → fold"), Fall-Enumeration, Gegner-Pattern-Lesen über Runden.

## 5. ÜBERTRAG AUF UNS — vorregistriertes Experiment-Design (NICHT sofort laufen lassen)

**Diagnose-Match:** Unsere gemessene GRPO-Regression (−90 vs GTOW nach Liga-Reward-RL) ist das
SPIRAL-Fixed-Opponent-Ergebnis in Reinform: die sixmax-Liga (TAG/LAG/Nit/Station/Maniac) ist ein
STATISCHES Gegner-Ensemble → das RL lernte liga-schlagende Aggression (Winrate vs Liga hoch,
vs GTOW −90), exakt wie Gemini-Gegner-Training 0%→62.5% Winrate bei SCHLECHTEREN Benchmarks.
SPIRALs zwei Mechanismen adressieren zusätzlich zwei bekannte eigene Baustellen:
(a) das Auto-Curriculum ersetzt die Liga, (b) RAE ersetzt/repariert die Advantage-Schätzung
(unser R_BAD=−30-Varianz-Problem in `training/qwen_grpo.py`, Memory `grpo-reward-fix`, war
derselbe Fehlertyp: Reward-Terme, die das EV-Signal ertränken).

**Konkrete Änderungen an `training/qwen_grpo.py` (bzw. einem künftigen GLM-Lauf über
`infra/gtow_glm_pod.py`):**

1. **Gegner = Kopien statt Liga (Kern-Change):** in der Rollout-Schleife spielt EINE geteilte
   Policy ALLE Sitze (HU zuerst: beide Sitze), konditioniert auf Sitz/Position im Prompt —
   statt `arena/sixmax.py`-Profile als Gegner. Alternativ (schwächere Form) ein Frozen-Snapshot-Pool
   der letzten k Checkpoints. Die Liga darf als EVAL bleiben, nie als Reward-Gegner.
2. **RAE statt Gruppen-Normalisierung:** GRPOs gruppenrelative Advantage über gemischte
   Positionen ist in Poker konfundiert — BB verliert im Schnitt IMMER, BTN gewinnt im Schnitt.
   Ersetzen durch positions- und spielkonditionierte EMA-Baselines:
   `b_{spiel,pos} ← 0.95·b + 0.05·R`; `A = R − b_{spiel,pos}` (Position = Sitz: SB/BB/BTN/…;
   "Spiel" = Stack-Tiefe-/Format-Bucket). Keine Längen-Normalisierung.
3. **Reward = reiner Nullsummen-Chip-Ausgang** des Matches/der Hand (bb), terminal, ohne
   Shaping-Terme (kein R_BAD, keine Legalitäts-Boni — Legalität erzwingt der Executor ohnehin).
4. **Voll online** (kein Offline-Batch von Liga-Spielen): Actors sammeln Self-Play-Hände von der
   AKTUELLEN Policy, Learner updatet, Gewichte synchronisieren — unser Pod-Harness kann das
   (Oat-Referenz-Code im SPIRAL-Repo als Vorlage).
5. **Thinking-Collapse-Wächter:** Response-Länge + Gradienten-Norm pro Step loggen; Trace-Länge
   → 0 oder Grad-Norm → 0 = Abbruchkriterium (ihr Kollaps kam nach ~100–200 Steps).

**Vorregistrierung (Design, Erwartung, Gate):**
- **Arme:** A = geschützte Baseline (`models/grpo_slim.tgz`, ≈ −40 robust, NICHT anfassen);
  B = Self-Play + RAE + Chip-Reward (Änderungen 1–5), gleiche Steps/Compute wie der letzte
  Liga-Lauf.
- **Erwartung (ehrlich):** B eliminiert den Liga-Ausbeutungs-Modus (die −90-Klasse). Erwartete
  Richtung: Body-Verbesserung gegenüber −40, KEIN Versprechen unter −20 — SPIRAL belegt
  Curriculum-Überlegenheit auf Winzspielen, nicht NLHE-Stärke. Null-Hypothese, die uns widerlegen
  kann: Self-Play konvergiert gegen einen selbst-konsistenten, aber GTOW-fernen Stil (in HU
  theoretisch unwahrscheinlicher, da Zwei-Spieler-Nullsumme → Self-Play-Konvergenz Richtung
  Gleichgewicht plausibel; in 6-max OHNE Garantie).
- **Gate (Doktrin):** gepaarte seed-Exports → Analyzer-μ-Vergleich zuerst ($0), dann AIVAT-Anker;
  "never ship a regression" gegen Arm A; Winrate-vs-Trainingsgegner ist als Metrik VERBOTEN
  (das war der −90-Fehler) — nur externe GTOW-Zahlen zählen.
- **Status: NICHT gestartet.** Dies ist ein Design-Dokument; der Lauf braucht den User-Go
  (Pod-Kosten) und einen freien Mess-Slot in der Gate-Leiter.

## 6. Ehrliche Grenzen

- **Größenordnung:** Kuhn Poker = 3 Karten, 1 Bet-Size, ~Dutzende Infosets. 6-max NLHE = ~10^160+
  Spielbaum, kontinuierliche Sizings, Multiway, Stack-Tiefen. Dass Self-Play auf Kuhn funktioniert,
  beweist NICHTS über die Konvergenzgeschwindigkeit oder das Plateau auf NLHE.
- **Anderes Zielmaß:** SPIRAL optimiert und misst TRANSFER auf Mathe-Benchmarks (+10% MMLU/AIME),
  nicht Poker-Exploitability oder bb/100. Winrate 50% gegen die eigene Kopie sagt nichts über die
  Ausbeutbarkeit durch einen externen Near-GTO-Gegner (GTOW). Ihre Poker-Stärke wurde nie gegen
  einen Solver gemessen.
- **Theorie-Lücke für 6-max:** SPIRAL ist strikt Zwei-Spieler-Nullsumme (dort hat Self-Play
  Gleichgewichts-Anker). 6-max ist Multiplayer-General-Sum — kein eindeutiges CE, Self-Play kann
  in Zyklen oder pool-spezifische Konventionen laufen (unser North-Star-Block). Der Übertrag ist
  für den HU-GTOW-Kanal sauber, für 6-max Hypothese.
- **Compute + Plateau:** 8×H100 × 25 h für WINZIGE Spiele; die Autoren berichten selbst
  Plateau-Effekte bei längerem Training und Reward-Hacking-Risiko. NLHE-Self-Play wird pro
  Informations-Bit teurer sein.
- **Kleine absolute Lifts auf starken Modellen:** R1-Distill +1.4, Llama-Instruct +2.0 — der
  +10-Headline gilt für BASE-Modelle mit viel Luft. Unser GLM ist bereits ge-SFT-et; realistisch
  ist eher die kleine Lift-Klasse.
- **Ihr Kuhn-Reward ist Match-binär** (±1 über 5 Runden), nicht chip-proportional — für uns ist
  Chip-EV (bb) das Scoreboard; die Übertragung des binären Rewards wäre ein Informationsverlust,
  wir behalten Chip-EV und übernehmen nur Curriculum + RAE + Sparsity.
