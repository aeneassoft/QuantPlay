# Optimising poker theory for ML/computation

## OpenAI gpt-5.1

1) Repräsentation: Wie man Poker so modelliert, dass Compute wirklich besser ist als „Buchtheorie“
-------------------------------------------------------------------------------

Der Kern: Du willst **alles** in Begriffe gießen, über die man
- Erwartungswerte sauber definieren kann,
- Belief-States und Gegenfaktoren (counterfactual values) berechnen kann,
- Gradienten / Regrets / Policy-Updates sauber ableiten kann.

### a) Zentrale mathematische Objekte

**Spielmodell (für 2p NLHE, CGT-Style):**

- Zustandsraum: Histories \(h = (a_1, a_2, ..., a_t)\).  
- Öffentliche Infos: Board, Pot, Betgrößen-Historie, wer am Zug ist, effektive Stacks.  
- Private Infos: Hole Cards \(c_i\).  
- Informationsmengen \(I\): Menge von Histories, die für einen Spieler **ununterscheidbar** sind (gleiche Public-Infos, eigene Karten, aber Gegnerkarten unbekannt).  
- Strategien \(\sigma_i(I)\): Wahrscheinlichkeitsverteilungen über Aktionen \(a\in A(I)\).  
- Payoff: \(u_i(h)\) am Terminalzustand (Showdown / Fold).

**Rechentechnisch relevante Größen:**

- **Belief State**:  
  \(b(I)\) = Verteilung über alle möglichen verdeckten Karten / vorherigen Mixes, konsistent mit Public-Line.  
  Praktisch: „Rangerverteilung“ über Kombos (oft faktorisierte Approx).

- **Counterfactual Value (CFV)**:  
  \(v_i^\sigma(I)\) = erwarteter Payoff von Player \(i\), *bedingt* darauf, dass sich das Spiel in \(I\) befindet, gewichtet mit der Wahrscheinlichkeit, dass der Gegner & Chance zu \(I\) geführt haben. Zentral bei CFR, DeepStack, ReBeL.

- **Regret** \(r(I,a)\):  
  Vorteil, den man gehabt hätte, wenn man in \(I\) immer Aktion \(a\) statt der aktuellen Policy gewählt hätte:
  \[
  r(I,a) = v_i^\sigma(I \text{ mit } a) - v_i^\sigma(I)
  \]
  -> Regret-Matching / (D)CFR.

**Menschliche Begriffe → Maschinenprimitiven**

- **Ranges**:  
  Mensch: „Er openraist 25% Range, ich 3-bette 10%“  
  Maschine:  
  - Verteilung \(\rho_{\text{pre}}\) über Hole-Karten,  
  - aktualisierte Posteriorverteilung nach Actions: \(\rho_{\text{post}}(c_{\text{villain}} \mid h)\).  
  Implementiert als:
  - tabellarisch (Abstraktion),
  - oder parametrisiertes Modell \(f_\theta(\text{public obs}) \to\) Dichte über “bucketed” Handtypen / Kartenbits.

- **Polarisierung**:  
  Mensch: starke + Bluffs, keine mittelstarken Hände.  
  Maschine:
  - Policy, die die Aktion „große Bet“ nur in CFV-Extremen (sehr hoch / sehr niedrig) wählt.  
  - Lässt sich als Struktur im Q-Value sehen: Aktion „Potbet“ wird für Hände mit großen \(|v - \text{EV-Fold}|\) bevorzugt.  
  - In Repräsentationen lernt das Modell typischerweise „Monotonien“: je stärker/ schwächer, desto eher große Bets.

- **MDF (Minimum Defense Frequency)**:  
  Mensch: \(\text{MDF} = \frac{\text{Pot}}{\text{Pot}+\text{Bet}}\).  
  Maschine:
  - Der exakt gleiche Ausdruck taucht auf, wenn man eine BR-Optimierung (bester Call/Fold-Mix) gegen eine gegebene Bluff-Frequenz auflöst.  
  - Aber Compute muss nicht MDF „wissen“: CFR/Best-Response-Iteration *induzieren* MDF, weil jede Abweichung von MDF zu ausnutzbaren Bluffs/Folds führt.  
  - Praktisch: MDF ist eine **starke Prior** / initialisierende Heuristik für die Policy (siehe Teil 2).

- **Blocker**:  
  Mensch: „Mein A♣ blockt seine Nut-Flushes → bessere Bluffbet.“  
  Maschine:
  - CFV-Differenz entsteht, weil bestimmte Kartenkombos in der Belief-Verteilung dünner werden, wenn ich diese Karte halte.  
  - Feature-seitig: Input-Encoding, das einzelne Kartenbits + Suit-Pattern sauber wiedergibt; das Netz lernt, wie Kartensymmetrien CFVs verschieben.  
  - Explizit kann man „Blocker-Features“ als zusätzliche Eingaben codieren (z. B. Counts spezifischer Nuthände, die mein Holding blockt).

- **Equity**:  
  Mensch: „Equity vs Range“ = Gewinnwahrscheinlichkeit im All-in.  
  Maschine:
  - Equity ist nur *ein* Bestandteil des CFV, unter der Policy / Betting-Strategie.  
  - Wichtig: Statt isolierter Preflop/Flop-Equity optimiert Compute den **gesamten Wert** über das gesamte Subgame.  
  - Technisch: \(v_i^\sigma(I)\) integriert beides – Equity & erwartete Folding-/Bluffselektion.

### b) Wo 1 Stunde Compute 3 Jahre Pro-Wissen dominiert

**Compute ist überlegen, sobald:**

1. **Genaue Mischfrequenzen in komplexen SPOTs**  
   - Z. B. 3-bet-Pot, SPR ~ 2, multi-street Betting mit vielen Bet-Sizes.  
   - Ein lokaler Solver (TexasSolver) + cf-values über ein Board-Sampling kann:
     - exakte Frequenzen für Hunderte/ Tausende von Händen ausgeben,  
     - Fehlerkurven (wie schlecht ist „always c-bet 60% Pot“) hochauflösend liefern.  
   - Ein Mensch kann qualitativ verstehen: „turn check-raise ist polar“, aber nicht:
     - „Hand X bettet 32% Flop, 51% Turn, 8% River, mit welcher Kombo Gewichtung, um IP-Check-Back-Leaks zu bestrafen.“

2. **Leakkurven / Exploit-Stärke quantifizieren**  
   - Beispiel: „Villain foldet Flop vs c-bet 55% statt GTO 35%“ → Compute kann:
     - systematisch Best-Response suchen,  
     - exploitative Linie in bb/100 ausrechnen, per Boardklasse / Commitment-Level.  
   - Diese fein granulierten „Leak-Mapping-Heatmaps“ sind jenseits dessen, was ein Pro per Intuition konstruieren kann.

3. **Abstraktion & Subgame-Re-Solving** in vielen Spots  
   - Durch **cached GTO-Benchmarks** kannst du in 1h:
     - Tausende Strategien quer über Boardklassen gegen GTO ground truth scoren,  
     - unter Variation von Parametern (Aggression, C-bet-Frequenz, Sizing-Mix usw.) optimale Hyperparameter finden.  
   - Der Mensch kann zwar Regeln finden, aber **nicht** 1000 Varianten durchsimulieren und ihren GTO-Gap bewerten.

4. **Belief-State-Optimierung > statische Heuristik**  
   - OppModel + Node-Locking:  
     - Compute kann (über No-Regret/Gradienten) automatisch finden, wie stark man von GTO abweicht, um ein bestimmtes OppModel maximal auszubeuten, bei fixierter Exploitability-Budget-Constraint.  
   - Menschen sind hier qualitativ gut („vs Nit fold ich mehr“), aber:
     - Compute kann diese Adjustments sehr präzise in Mischfrequenzen/Line-Auswahl anpassen, inkl. komplexer Multiline-Exploits.

**Wo Compute **NICHT** einfach 3 Jahre Pro ersetzt:**

1. **Priors / Abstraktionen / Domain-Reduktion**  
   - Welche Bet-Sizes überhaupt zulassen?  
   - Welche States zusammenlegen (Board-Cluster, SPR-Klassen, Positionen)?  
   - Welche menschlichen Heuristiken sparen 90% des Suchraums, ohne 90% der EV zu killen?  
   -> Hier sind gute „Theorie-Priors“ Gold wert und reduzieren Compute massiv.

2. **Modellspezifikation**  
   - Architektur von Value/Policy-Netz, Feature-Design, Parameterisierung von Ranges (z. B. Bucketing, Suit-Isomorphien).  
   - Ein starker Pro, der gleichzeitig die Compute-Pipeline versteht, kann sehr gut einschätzen, **welche** Details wichtig sind (z. B. tiefe River-Value-Traps vs. Turn-Aggressionsmuster) und das Netz/Fokus entsprechend lenken.

3. **Meta-Strategie / Game-Selection / Reale Populationsannahmen**  
   - Selbst das perfekte 2p-zero-sum GTO löst nicht:
     - Multiway-Dynamiken,  
     - Rake/Struktur-spezifische Anpassungen,  
     - Live-Tells, Zeitverhalten, etc.  
   - Menschen liefern robustere High-Level-Priors, in welchen Games/Lineups welcher Exploit-Regime-Modus sinnvoll ist.

4. **Deutung & Robustheit**  
   - Compute kann tausende Spots solve’n, aber:
     - Pattern-Erkennung auf einem abstrahierten Level („was *bedeutet* diese Range-Krümmung?“) ist weiterhin eine menschliche Stärke.  
   - Diese Einsichten helfen, Fehler der Abstraktion / Overfitting zu erkennen.

---

2) Analytische Theorie als relaxierte Prior: Prinzipielle Frameworks
--------------------------------------------------------------------

Deine Intuition („Chen, MDF, α=s/(1+s) als *relaxierbare* Struktur“) passt sehr gut in mehrere etablierte Frameworks:

### a) Analytische Formeln als **Priors / Initialisierung**

**Bayes-Prior / Architektur-Prior:**

- Beispiel: Deine initiative-/range-aware Chen/MDF-Heuristik liefert:
  - für jeden Spot eine „hart kodierte“ Policy \(\pi_{\text{theory}}(I)\),  
  - oder Target-Kennzahlen (z. B. „C-bet 70% auf trockenem Board“).
- Im Lernmodell:
  - Initialisiere Policy-Netz \( \pi_\theta \approx \pi_{\text{theory}}\) (Supervised-Init: MSE / CE auf \(\pi_{\text{theory}}\)).  
  - Danach: Self-Play / CFR-Updates, um von dieser Approximation *weg* zu verbessern.

Positiver Effekt:
- Suchraum ist von Anfang an im vernünftigen Regime (z. B. kein massives Overbluffen auf nut-lastigen Boards).
- Compute wird für Feinjustierung genutzt, nicht für „Grundschultheorie“.

### b) Analytische Theorie als **Soft-Regularisierung**

Formell:  
\[
\mathcal{L}(\theta) = \mathcal{L}_{\text{game}}(\theta) + \lambda \cdot \mathcal{R}(\theta)
\]
mit z. B.
\[
\mathcal{R}(\theta) = \sum_I D_{\text{KL}}\left(\pi_\theta(\cdot\mid I) \;\|\; \pi_{\text{theory}}(\cdot\mid I)\right)
\]

Interpretation:
- \(\mathcal{L}_{\text{game}}\): Exploitability-Näherung, BR-Loss, DCFR-Objektiv oder Self-Play-Cross-Entropy / Advantage-Loss.  
- \(\mathcal{R}\): „Bleib nicht zu weit von der Theorie-Policy weg, außer wenn es EV bringt.“

**Constraint-Annealing / Homotopy:**

- Starte mit hohem \(\lambda\) (starke Theorie-Bindung),  
- reduziere \(\lambda\) über Zeit („Engine wärmt auf“).  
- Ergebnis: Model beginnt im Theorienahen Regime, löst sich dann, wenn Daten (Self-Play / GTO-Benchmark) Gründe liefern.

Das ist exakt die Idee von:
- **Lagrange-Multiplikatoren / Lagrangian Relaxation**:
  - Theoretische Constraints (z. B. MDF, Pot-Control auf bestimmten Boards) als soft constraints implementieren,  
  - Lagrange-Multiplikator \(\lambda\) wird dynamisch (oder per Schedule) angepasst.

### c) Analytik als **Curriculum**

Curriculum Learning-Ansatz:

1. Phase 1:  
   - Nur einfache Spots mit hoher analytischer Abdeckung (z. B. single-raised Pots, CBET-only, wenig Sizing-Optionen).  
   - Loss = Distanz zu analytischer Policy + leichter Self-Play-Anteil.

2. Phase 2:  
   - Komplexere Spots (3bet-Pots, Turns, Rivers, verschiedene Sizings).  
   - Mehr Gewicht auf explizite Gegenfaktoren (CFV-Schätzung, Best-Response-Loss).

3. Phase 3:  
   - Vollständige Self-Play/Exploitability-Optimierung; analytische Theorie nur noch als Regularisierung für Out-of-Distribution-States.

So verstärken sich Theorie & Lernen, statt zu kollidieren:
- Theorie definiert den „Startraum“ und die „erlaubten Tendenzen“.
- Lernkomponente nutzt Abweichungen von der Theorie nur dann, wenn diese **messbar EV-positiv**sind.

### d) Konkrete Konstruktion für euch

**Beispiel: α = s / (1 + s)** (Kontrolle über Aggressionsgrad vs. Stack/Pot-Verhältnis)

- Verwende α als deterministische Funktion deiner Features (SPR, Position, Initiative).  
- Policy-Netz lernt *Residuums-Parameters* \(\delta\alpha\):  
  \[
  \alpha_{\text{eff}} = \frac{s}{1+s} + f_\theta(\text{state})
  \]
  mit Regularisierung \(\|\delta\alpha\|^2\) oder KL vs. Basis-α.  
- So bleibt die globale Struktur (höhere s → höhere Aggression) erhalten, aber Subtleties (z. B. speziell Q-high-Boards vs K-high) lernt das Netz.

**MDF-Baseline**

- Für jeden Betspot: analytische MDF \(\text{MDF}_{\text{theory}}\).  
- Netz gibt \(\text{MDF}_\theta(I)\) aus.  
- Regularisierung:
  \[
  \mathcal{R}(I) = (\text{MDF}_\theta(I) - \text{MDF}_{\text{theory}})^2
  \]
  es sei denn, GTO-Benchmark zeigt klar, dass Abweichung besser ist → dann \(\lambda\) lokal senken (adaptive Regularisation).

---

3) „Computation Substrate“: Worauf aufbauen?
---------------------------------------------

### a) OpenSpiel

**OpenSpiel (DeepMind, Open-Source)** ist im Moment das Nächstliegende zu „Qiskit für Spieltheorie“:

- Framework für:
  - Representation von **Simultan- und Sequenzspielen** mit unvollständiger Information,  
  - CFR, DCFR, XFP, PSRO, RL-Algorithmen,  
  - diverse Beispielspiele (u. a. Leduc, Kuhn, Goofspiel, einige Poker-Varianten).

- Stärken:
  - Sehr modulare Darstellung von Spielen (Infosets, Actions, Transitions).  
  - Saubere Implementationen von klassischen Algorithmen (Counterfactual Regret Minimization + Varianten, Policy Gradients, etc.).  
  - Integration mit JAX / TensorFlow / PyTorch möglich.

- Schwächen:
  - Für NLHE in voller Komplexität nur als Spiel-Template nutzbar;  
  - keine Out-of-the-box hoch optimierte NLHE-Lösungsmodule wie Pio/TexasSolver.  
  - Performance & Abstraktionen sind generisch, nicht NLHE-optimiert.

Trotzdem:  
**Als konzeptionelles & experimentelles Substrat ist OpenSpiel absolut sinnvoll**, insbesondere, um:
- neue CFR-Varianten, Exploitability-Metriken, OppModel-Algorithmen etc. erstmal in Leduc/Kuhn zu testen,  
- generische IIGS- (Imperfect Information Game Solving) Pipelines zu validieren.

### b) Andere relevante OSS-Bausteine

- **ACPC/annual computer poker competition code**  
  - Legacy, aber gute Referenzen für:  
    - Game-Abstraction,  
    - Best-Response-Tools,  
    - Evaluator.

- **DeepStack/Deep CFR/Pluribus Open Repos** (teils inoffiziell, teils Reimplementierungen):  
  - z. B.:
    - Open-Source „Deep CFR“-Implementierungen (Python/C++/PyTorch)  
    - RLCard (mehr RL-orientiert, Poker & Kartenspiele, aber weniger game-theoretisch streng)

- **Poker-Spezifische Projekte**:
  - Es gibt diverse GitHub-Repos für:
    - Counterfactual Regret Minimization in Texas Hold’em,  
    - Abstraktion & Bucketing.  
  - Qualität variiert, aber manche enthalten solide Evaluatoren + CFR-Kerne.

### c) Wann lohnt sich bespoke Tooling?

Mit deinem Setup:

- **Ihr habt bereits**:
  - TexasSolver (lokaler Postflop-GTO-Oracle),
  - GTO-Benchmark (GTO-Gap-Scorer, cached),
  - OppModel.

Was hier fehlt, was generische Frameworks nicht gut lösen:

1. **Nahtlose Integration von NLHE-Spezifika + High-Performance-Lösungen**
   - Board-Equity-Evaluatoren,  
   - Suit-/Isomorphie-Symmetrisierung,  
   - SPR-Stratifizierung und Subgame-Resolving.

2. **Custom Training-Loops**:
   - Online Re-solving mit GTO-Oracle-Calls,  
   - Node-Locking basierend auf OppModel-Schätzungen,  
   - Exploitability-Budgeting (Regime Blend \(\sigma = (1-\lambda)\cdot \text{GTO} + \lambda\cdot \text{Exploit}\)).

Das spricht **klar für eine eigene Infrastruktur**, aber nicht „from scratch“:
- Nutze OpenSpiel als **Referenz für Algorithmen** (CFR-Varianten, Exploitability-Berechnung, PSRO-Ideen).  
- Eure NLHE-Engine (TexasSolver + Abstraktion + Evaluator) ist der eigentliche „Hardware-Sim“.  
- Baue ein dünnes, gut designtes Interface:
  - `GameState`-Objekt mit ähnlicher API wie OpenSpiel, aber NLHE-optimiert,  
  - Adapter für Self-Play / DCFR / ReBeL-like Search, die eure Solver-Calls einbinden.

---

4) Konkreter Trainings-Plan für die Pod-Runs
--------------------------------------------

Ziel: In 1 GPU-Stunde **maximalen Fortschritt** bzgl.
- (a) GTO-Gap auf eurem Benchmark,
- (b) Exploit bb/100 vs. OppModel / realistische Gegnerprofile.

### a) Repräsentation auf dem Pod

**State-Features (Input)**:
- Öffentliche Infos:
  - Board (bitmap: 52-Karten-One-Hot oder komprimierte Rank/Suit-Features + Isomorphien),
  - Potgrösse, effektive Stacks, SPR,
  - Position (IP/OOP), Street, vergangene Betgrößen (als normalisierte Größen, z. B. Pot-Fraction),
  - Action-History-Embedding (LSTM/Transformer light oder einfach aggregierte Stats wie „Anzahl Bets/Raises“, Max-Bet-Multiplier etc.).

- Private Infos:
  - Eigene Hole Cards (One-Hot oder embed),
  - optional: Bucket-ID (wenn du Abstraktion nutzt).

**Outputs** (Policy/Value):

- **Policy Head**:  
  - Wahrscheinlichkeitsverteilung über diskrete Aktionen (Fold, Call, Raise {x1/2, x2/3, Pot, All-In, …}).  
  - Optional Multi-Head: separater Head für Bluff/Value classifiers, falls du polarisierte Strukturen forcieren willst.

- **Value Head**:  
  - CFV-Schätzung unter aktueller (oder Ziel-)Policy \(\hat{v}_\theta(I)\).  
  - Optional: Value-Head per Handklasse (z. B. 169/1326-Buckets), nützlich für Node-Locking/Range-Visualisierung.

### b) Trainingsziel/e in 1h: Kombination aus 3 Loss-Komponenten

**1. Supervised + distillation von TexasSolver (GTO-Oracle):**

- Nutze gecachte GTO-Stategien als „Ground Truth“ in vielen Spots (bereits vorhanden durch dein Benchmarking).  
- Loss-Komponenten:
  - Policy-Distillation:  
    \[
    \mathcal{L}_{\text{policy}} = \mathbb{E}_I \left[ D_{\text{KL}}\big(\pi_\theta(\cdot\mid I) \|\; \pi_{\text{GTO}}(\cdot\mid I)\big) \right]
    \]
  - Value-Distillation:
    \[
    \mathcal{L}_{\text{value}} = \mathbb{E}_I \left[ \|\hat{v}_\theta(I) - v_{\text{GTO}}(I)\|^2 \right]
    \]

Das ist sehr compute-effizient:
- Oracle-/Benchmark-Daten sind gecached.  
- In 1h kannst du sehr viele Batches durchschieben (reines Feedforward + Backprop).  
- Ergebnis: kleiner, schnell evaluierbarer „approx-GTO-Netz“, das weite Bereiche des Zustandsraums abdeckt.

**2. Exploit-Learning vs OppModel (mit Exploitability-Budget)**

Parallel (oder in späterer Phase desselben Runs):

- Sammle Self-Play/Off-Policy Daten, bei denen PokerB gegen:
  - reine GTO-approx-Policy, und  
  - OppModel-Policy (realistische Gegner) spielt.

- Ziel: Lerne eine **Exploit-Policy** \(\pi_\theta^{\text{exploit}}\), aber mit Soft-Constraint auf GTO-Nähe.

Loss:

- EV-Metrik vs OppModel:
  \[
  \mathcal{L}_{\text{exploit}} = -\mathbb{E}_{\text{episodes}}[ \text{bb/100 vs OppModel} ]
  \]
- plus Regularisierung:
  \[
  \mathcal{R} = \mathbb{E}_I D_{\text{KL}}\big(\pi_\theta^{\text{exploit}}(\cdot\mid I) \|\; \pi_\theta^{\text{GTO-approx}}(\cdot\mid I)\big)
  \]
- Gesamt:
  \[
  \mathcal{L}_{\text{total}} = \mathcal{L}_{\text{policy}} + \beta \mathcal{L}_{\text{value}} + \gamma \mathcal{L}_{\text{exploit}} + \lambda \mathcal{R}
  \]

mit:
- \(\beta\): Gewichtung Value-Distillation,
- \(\gamma\): Fokus auf Exploit-Update in dieser Pod-Session,
- \(\lambda\): Exploitability-Budget-Kontrolle (Regime-Blending).

**Compute-Effizienz:**
- Du kannst viele Off-Policy-Transitions aus vorhandenen Simulationen recyceln (Replay Buffer).  
- Neue Episoden gegen OppModel können parallel auf vielen CPUs laufen; GPU macht nur Training.  
- 1h reicht, um signifikante Updates zu machen, solange das Netz schlank ist (z. B. < 50M Parameter).

**3. Direkte Optimierung der GTO-Gap über DCFR-like Objective (optional)**

Wenn du Exploitability schätzen kannst (z. B. über approximierten Best-Response oder existierenden Benchmark), könntest du:

- GTO-Gap als Differenz zwischen:
  - Wert unter deiner Policy,  
  - Wert unter Oracle-GTO.  
- Minimieren via:
  - Gradient-basierter Policy-Optimierung (bewusst einfache Policy Gradient / advantage actor-critic),  
  - oder CFR-ähnlichen Updates, bei denen Regrets in einem Netz gespeichert werden (Deep CFR).

Für 1h-Runs ist aber meist **Policy-/Value-Distillation + leichte RL-Exploit-Komponente** effizienter als vollwertiges CFR-Training.

### c) Meta-Coach (Claude Haiku) im Loop

Claude kann sinnvoll eingesetzt werden, um:

1. **Hyperparameter-Suche im Kleinen zu steuern**:
   - nach jedem Pod-Run:
     - GTO-Gap-Change,
     - Exploit-bb/100-Change,
     - Exploitability-Budget (Effektive KL-Entfernung von GTO).  
   - Claude bewertet: welche Loss-Gewichtungen (\(\beta, \gamma, \lambda\)) funktionierten,  
   - schlägt neue Konfigurationen / Curriculum-Schritte vor.

2. **Curriculum-Design**:
   - Reihenfolge der Spots, die stärker trainiert werden sollen (z. B. River-Entscheidungen mit hohem EV-Impact zuerst).  
   - Identifikation von Boardklassen, in denen GTO-Gap besonders groß ist → fokussiertes Retraining.

3. **Node-Locking-Policy**:
   - vorgeschlagene Node-Locks gegen OppModel (z. B. „Vs. dieser Gegner: im 3bet-Pot check-raise-Frequenz in Spots X/Y erhöhen“), die dann durch TexasSolver lokal verifiziert und in die Trainingdaten integriert werden.

---

Kurzfassung Handlungsplan:

1. **Representation fixieren**: kompaktes Policy+Value-Netz mit reichhaltigen, aber leichtgewichtigen Features (Board, History, Cards, SPR).  
2. **Analytische Theorie als Prior**: Policy init auf Chen/MDF-Variante, Soft-Regularisierung gegen diese Heuristik mit annealing.  
3. **Gecachte Oracle-Daten ausnutzen**: Distillation von TexasSolver-GTO in großem Batch-Training → GTO-Gap schnell reduzieren.  
4. **Exploit-Komponente**: kleine RL-Schicht darauf, die vs. OppModel EV maximiert, aber KL-gebunden an GTO-approx bleibt (Exploitability-Budget).  
5. **Bespoke Tooling**: eure TexasSolver+Abstraktion ist die „Hardware“, mit einem dünnen, OpenSpiel-inspirierten, aber NLHE-spezifischen Solver-/Training-Interface oben drauf.  
6. **1h-Pod-Run**:  
   - ~70–80% Zeit Distillation / GTO-Gap-Minimierung,  
   - ~20–30% Zeit Exploit-Finetuning vs OppModel & Replay,  
   - nach dem Run: evaluieren, Hyperparameter adaptieren (Meta-Coach).

## Claude claude-opus-4-8

# Antwort: Pod-Foundation konkret machen

## 1) Recursive-ToM-LLM auf Hand Histories — wertvoll oder Essay?

**Urteil: Als Trainingssignal weitgehend Essay. Als Konzept-Miner und Test-Generator wertvoll — aber nur in stark eingeschränkter Form.**

Das Problem mit "rekursiver ToM über alle Spieler" als Lernsignal: Es ist nicht *grounded*. Die LLM-Prosa ("er denkt, dass ich denke…") produziert keine überprüfbaren EVs. Du hast aber bereits den GTO-Benchmark als ground truth — jedes LLM-ToM-Argument muss sich daran messen lassen, sonst ist es Geschwätz. **Verwende den Benchmark als Lügendetektor für die LLM-Reasoning.**

Wo es konkret Wert hat (nach Priorität):

- **(a) Spot-Generator / Stress-Test-Miner — JA.** Haiku liest Hand Histories und schlägt *Knotenkategorien* vor, in denen Blocker / Polarisierung / Range-Asymmetrie entscheidend sind ("hier hängt alles am Nut-Blocker"). Das sind Kandidaten-Spots, die du dann **mit dem Solver verifizierst**. Output: eine kuratierte, schwierigkeitsgewichtete Spot-Liste für den Benchmark — genau da, wo dein Bot wahrscheinlich am meisten GTO-Gap hat.
- **(b) Feature-Discovery — JA, begrenzt.** Wenn die LLM-ToM konsistent auf eine Größe zeigt, die in deinem Encoding fehlt (z.B. "Anzahl der Nut-Combos, die mein Holding blockt"), ist das ein konkreter Feature-Vorschlag. Das ist billig zu testen: Feature rein → GTO-Gap auf Benchmark fällt? behalten.
- **(c) Direktes Policy-Signal — NEIN.** Ablenkung. LLM-ToM-Text in Loss-Funktionen zu gießen ist teuer, rauschig und vom Solver dominiert.

**Operationalisierung (gehört NICHT in den Hot-Pod-Loop, sondern offline davor):**
```
HH → Haiku: "markiere Knoten, wo ToM/Blocker/Polarisierung den Baum kippt"
   → Solver verifiziert jeden markierten Knoten (CFV-Sensitivität)
   → behalte nur Knoten mit hoher CFV-Varianz → "Hard-Spot-Set"
   → speise Hard-Spot-Set in den Benchmark ein (Gewichtung)
```
Das **füttert** den Pod-Run (besseres Eval-Set), läuft aber asynchron auf CPU.

---

## 2) Chen/MDF-Schwellen als Priors — der Self-Improvement-Loop

Genau richtig und sofort buildbar. Deine hand-coded Baseline ist eine *parametrisierte Policy* π_θ mit kleinem θ (Open-%, 3bet-%, MDF-Fudge, c-bet-Größen, Polarisierungs-Cutoffs). Das ist ein niedrigdimensionales, billig-evaluierbares Optimierungsproblem — perfekt für CPU + Haiku-Coach.

**Der Loop (CPU-only, kein GPU nötig):**
```
θ_0 = Chen/MDF-Defaults (gute Priors → schneller Start)
loop:
  1. PROPOSE θ':
       - Haiku schlägt strukturierte Edits vor ("erhöhe BTN-open 2%, polarisiere Turn-bet")
       - PARALLEL: CMA-ES / Bayes-Opt schlägt numerische Schritte vor
  2. EVALUATE: GTO-Gap(π_θ') auf gewichtetem Spot-Set  (Sekunden, gecacht)
  3. ACCEPT wenn Gap sinkt (mit Exploitability-Budget als Constraint)
  4. LOG (θ', gap, welcher Proposer) → füttert Haiku als Kontext zurück
```

**Wichtige Designentscheidungen:**
- **Haiku ist Vorschlags-Proposer, nicht Schiedsrichter.** Akzeptanz entscheidet *immer* der Benchmark. Haiku gewinnt nur, wenn es schneller in gute Regionen springt als blinde Suche — das misst du (Accept-Rate pro Proposer).
- **θ pro Subgame-Klasse** (per SPR-Bucket × Initiative × Board-Textur), nicht global. Sonst mittelt sich alles weg.
- **Exploitability-Budget als harte Nebenbedingung**, nicht als Term im Loss — sonst optimiert der Loop sich in ausnutzbare Ecken.

Dieser Loop ist auch dein **Dry-Run** für die Pod-Infrastruktur: gleiche propose→eval→accept-Schleife, nur dass auf dem Pod ein neuronales π_θ und DCFR-Updates die Rolle von CMA-ES übernehmen.

---

## 3) Was VOR dem Pod-Launch fertig sein muss — geordnet

Prinzip: **Der Pod darf erst laufen, wenn die Reward-/Eval-Pipeline wasserdicht ist.** Ein GPU-Pod, der gegen einen falschen oder langsamen Benchmark optimiert, verbrennt Geld in die falsche Richtung.

**Tier 0 — Eval-Integrität (Blocker, ohne das kein Launch):**
1. **Benchmark als API mit stabilem Contract**: `gto_gap(policy, spot_set) → scalar + per-node breakdown`, deterministisch, gecacht, < Sekunden. Das ist dein Reward-Signal — es muss bombenfest sein.
2. **Exploitability-Budget-Check als separater Gate**: jede Policy bekommt `(gto_gap, exploitability)`. Akzeptanz nur wenn beide ok.
3. **Spot-Set fixiert + versioniert** (inkl. des Hard-Spot-Set aus §1a, falls fertig — sonst ohne, kein Blocker).

**Tier 1 — Loop-Mechanik auf CPU validieren (vor GPU):**
4. **Der §2-Loop läuft end-to-end** auf der Baseline und senkt nachweislich den Gap. Wenn das auf CPU nicht funktioniert, funktioniert es auf dem Pod auch nicht — nur teurer.
5. **State-Encoding eingefroren**: Public-Obs + Karten-Bits + Suit-Pattern + Blocker-Counts (das eine Feature aus §1b, falls verifiziert). Encoding-Änderungen mitten im Pod-Run = Neustart.

**Tier 2 — Pod-spezifisch (das eigentlich Neue):**
6. **Kleines on-pod π_θ-Netz** (Policy + Value-Head), das dasselbe Encoding frisst und am selben Benchmark gemessen wird.
7. **DCFR-Update-Schleife** über subgame-resolved CFVs, Value-Net als Bootstrap an Subgame-Blättern (die etablierte GTO-Abkürzung: re-solve + abstraction + value-fn + SPR + DCFR).
8. **Haiku-Meta-Coach-Hook**: gleiche Schnittstelle wie im CPU-Loop, schlägt jetzt Hyperparameter / Abstraktions-Edits / Node-Lock-Targets vor.

**Bewusst NICHT vor dem Launch (Ablenkungen):**
- Volle ReBeL-Belief-Search — zu schwer, später.
- DeepNash/R-NaD-Pfad — anderer Paradigmen-Ast, jetzt parallelisiert die Aufmerksamkeit. Parken.
- LLM-ToM als Loss-Signal (§1c).
- 6-max / Multiway — erst 2p zero-sum sauber (nur da gilt deine no-regret→Nash-Garantie).

---

## 4) Das EINE höchste-Hebel-Ding zuerst auf den Pod

**Die Reward-Pipeline als Pod-Service: `gto_gap` + Exploitability-Gate, als der gemeinsame, deterministische, schnelle Fitness-Operator, an den sowohl der CPU-Prior-Loop (§2) als auch das on-pod π_θ (§3-Tier2) andocken.**

Begründung: Alles andere — Haiku-Coach, DCFR, Prior-Tuning, neuronale Policy — ist nur ein *Proposer*. Der Benchmark ist der *Selektor*. In jedem Selbstverbesserungs-System bestimmt die Qualität und Geschwindigkeit des Selektors die Qualität des Endprodukts; ein starker Proposer mit schwachem Selektor optimiert konfident in die falsche Richtung. Du hast den Selektor schon (TexasSolver-Oracle + gecachter Benchmark) — der höchste Hebel ist, ihn als **stabilen, deterministischen, sub-sekunden-schnellen Service** zu härten, an dem CPU- und GPU-Welt austauschbar hängen.

Konkret heißt "zuerst": Tier-0 fertig, dann den §2-CPU-Loop daran laufen lassen, *Gap-senkt-nachweislich* verifizieren — **erst dann** GPU-Strom anschalten.
