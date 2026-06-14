# Phase-5 math double-check (OpenAI gpt-5.1)

Ich gehe Punkt für Punkt durch und trenne klar, wo Theorie „sauber“ ist und wo ihr im Nebel stochert.

---

## 1) Deep CFR auf abstrahiertem HUNL: mathematische Korrektheit & Konvergenz

### 1.1. Theoretische Basis

- **Externe-Sampling MCCFR** ist für endliche Extensive-Form-Games mit perfekter Informationserinnerung *konvergent* gegen eine NE-Strategie der *abstrahierten* Spiels, sofern:
  - Regrets korrekt berechnet werden,
  - Sampling-Verteilung korrekt (importance weights),
  - Alle Infosets unendlich oft getroffen werden,
  - Kein systematischer Bias im Training der Approximatoren entsteht.

- **Deep CFR (Brown & Sandholm 2019)** ersetzt die tabellarische Regret-Tabelle durch:
  - Neuronales Netz für *Advantage* (Regrets) pro Infoset,
  - Speicher (Reservoir/Replay) für Samples der Counterfactual Values,
  - Periodisches Reinit der Netze oder konsequente Online-Approximation der Regrets.

Mathematische Konvergenzgarantien sind *nur* streng für:
- tabellarische CFR / MCCFR,
- lineare oder „spezielle“ Approximatoren mit genauer Regression.

Deep CFR mit Deep Nets ist **heuristisch**, aber empirisch stark (Leduc, Flop Hold’em, HUNL).

### 1.2. In eurem Setting (abstrahiertes HU-NLHE)

- Das Spiel ist endlich (Diskrete Betgrößen, begrenztes Stack, endliche Karten):
  - ⇒ CFR-Konvergenz auf *diesem* Abstraktionsspiel ist prinzipiell gegeben.
- **Abstraktion** (z.B. {fold, call, 0.5p, 1p, all-in}) reduziert das Spiel massiv:
  - Die *theoretische* Lösung ist dann nur eine NE des abgekürzten Spiels.
  - Exploitability in *vollständigem* HUNLHE = ε_abstraction + ε_solver.

Formell:
- Seid \(G\) das echte Spiel, \(\tilde G\) das abstrahierte.
- Euer Deep CFR liefert Strategie \(\tilde\sigma\) mit
  \[
  \epsilon_\text{CFR} := \text{exploitability}_{\tilde G}(\tilde\sigma).
  \]
- Induzierte Strategie in G: \(\sigma^\uparrow\) (natürliche „Lift“-Abbildung).
- Gesamte Exploitability in G:
  \[
  \text{exploitability}_G(\sigma^\uparrow) \le \epsilon_\text{abstraktion} + C \cdot \epsilon_\text{CFR},
  \]
  mit einem problemabhängigen Faktor \(C\) (typisch O(1), aber nicht trivial exakt zu kennen).

**Leduc-Ergebnis (2.33→0.33 nash_conv)** garantiert rein:
- euer *Pipeline-Code* (Sampling, Backprop, Buffers) ist im Prinzip korrekt,
- aber sagt *fast nichts* über die Höhe von ε_abstraction in HU-NLHE.
  - Leduc ist winzig, keine Straßenstruktur wie NLHE, kaum Betsizing-Probleme.
  - Transfer: „der Algorithmus funktioniert“ ja; „Exploitability in HUNL aus Leduc-Werten ableiten“ nein.

### 1.3. Realistische Exploitability / Abstraktionsfehler

**Ohne massive Domain-Expertise** in Bet-/State-Abstraktion:

- ε_abstraction in vollem HUNL mit nur 3 Betgrößen ist typischerweise **riesig**:
  - In älteren ACPC-Bots mit sophisticated Abstraction und Solve (CFR+) lag man in HU-NL eher im Bereich:
    - 10–50 bb/100 Exploitability ggü. „perfektem“ GTO, je nach Modell.
  - Mit sehr grober Action-Abstraktion (kein Splitting von Stack-Regionen, kaum Streetspezifika) sind:
    - **>50 bb/100 Exploitability** gegenüber theoretischem GTO leicht vorstellbar,
    - aber das ist in der Praxis *völlig okay*, solange ihr Slumbot etc. schlagt.

**ε_CFR** im abstrakten Spiel:
- Deep CFR auf HUNL mit 3–4 Betgrößen, 200bb und ohne Card-Abstraktion ist brutaler als Leduc:
  - State-Space explodiert wegen:
    - 52-Karten-Deck, vielen Boards,
    - viel mehr Aktionen pro Street,
    - lange Spielbäume 200bb deep.
- Mit vernünftigem Setup (großer GPU-Pod) ist:
  - eine abstrakte exploitability im Bereich von **1–5 bb/100** *theoretisch* erreichbar, aber nur bei sehr gutem Engineering (Netzarchitektur, Replay, LR-Schedule, Stabilisierung).
- Ich würde konservativ annehmen:
  - ε_CFR im abstrahierten Spiel: **5–20 bb/100**, wenn ihr nicht monatelang feintuned.
  - ε_abstraction: **20–50+ bb/100** gegenüber echtem GTO.
  
Entscheidend: **Slumbot ist selbst abstrahiert und endlich**, ihr braucht *nicht* „echtes GTO“, sondern „besser als Slumbot und Population“.

### 1.4. Wichtige Korrektheits-Pitfalls bei External-Sampling + NN

1. **Regret-Targets:**
   - Deep CFR lernt *advantage*:
     \[
     A(I,a) = v(I,a) - v(I),
     \]
     mit counterfactual reach.
   - Achtet darauf, dass
     - \(v(I)\) korrekt über die Strategie der eigenen und gegnerischen Policy berechnet wird,
     - Counterfactual-Reach-Korrekturen stimmen (importance weights).

2. **Reservoir Buffers / Replay:**
   - Brown 2019: Vorteil-Samples (Advantage) werden mit Reservoir Sampling gespeichert, um eine *gleichverteilte* Menge über alle Iterationen zu approximieren.
   - Fehlerquelle:
     - „Frische“ Iterationen überrepräsentieren,
     - Bias Richtung letzten Policies ⇒ kann Konvergenz ruinieren.
   - Empfehlung:
     - Echten Reservoir-Sampler per Iteration oder global,
     - Limit für Buffergröße (z.B. 1–5 Mio Samples) + uniformes Ziehen beim Training.

3. **Reinit vs. Continual Training:**
   - Deep CFR-Original: *Reinit der Advantage-Netze pro Iteration* (um Distortions bei Approximation der kumulierten Regrets zu vermeiden).
   - Viele Implementationen (einschließlich einiger OpenSpiel-Varianten) weichen davon ab.
   - Wenn ihr **nicht** reinitialisiert, habt ihr:
     - „funktionierend, aber nicht mehr streng begründbar“-Heuristik.
   - Entscheidung:
     - Für „mathematische Sauberkeit“ möglichst nah am Brown-Setup,
     - für Praxis könnt ihr auch `no_reinit + target_network` machen, müsst dann aber auf empirische Stabilität achten.

4. **Averaging-Strategie:**
   - Deep CFR nutzt zusätzlich ein **separates Average-Policy-Netz**, das die (reach-weighted) Durchschnittsstrategie approximiert.
   - Tödlicher Fehler:
     - „Online-Policy“ anstatt „average“ auswerten.
   - Ihr solltet:
     - Bei Evaluation (nash_conv, Matches) strikt die *durchschnittliche* Policy verwenden,
     - nicht die „letzte Iteration“.

---

## 2) Warm-Start per Behavioural Cloning (BC) von Bot-Histories

### 2.1. Bricht BC die CFR-Konvergenz?

Die CFR-Garantie besagt: von *beliebigem Startregret* konvergiert CFR in NE (tabellarisch).
- Wenn ihr BC nur als **Initialisierung der Netzgewichte** nutzt, ändert ihr:
  - initiale Approximator-Parameter, nicht die mathematische Struktur des Updates.
- CFR „sieht“ nur die folgenden Regret-Updates durch MCCFR-Traversals.

**Fazit:**  
- Rein mathematisch: **NEIN**, eine BC-Initialisierung bricht die CFR-Konvergenz im abstrakten Spiel *nicht*, solange:
  - Alle weiteren Updates *on-policy CFR* sind,
  - Ihr die Regrets weiter sauber akkumuliert,
  - Ihr nicht versucht, BC-Loss während CFR weiterzumischen (das wäre dann kein reines CFR mehr).

Gefährlich würden nur **gleichzeitige** Ziele:
- Loss = α·MSE(Regret-Targets) + β·Cross-Entropy zu Bot-Policy,
- dann optimiert ihr *nicht mehr* reine Regrets ⇒ keine CFR-Garantie.

Deshalb:

### 2.2. „Korrekt“ warm-starten

Empfehlung:

1. **Reines BC-Vortraining:**
   - Trainiert ein Policy-Netz mit supervised BC auf Bot-Händer (ACPC, Pluribus),
   - optional ein Advantage-Netz mit pseudo-Targets (aber schwieriger, würde ich lassen).
2. **Transfer auf Deep CFR:**
   - Initialisiert
     - das Policy-/Average-Net mit den BC-Gewichten,
     - das Advantage-Net z.B. zufällig oder grob aus Policy abgeleitete Heuristik.
   - Dann:
     - **ab jetzt nur noch CFR-Loss** (Advantage-MSE, ggf. Policy-Average-Fit) verwenden.
3. **Optional:** Warm-Start der Average-Policy durch Replay-Sampling vergangener BC-States:
   - Im Prinzip: treat BC-Daten wie „Iteration -1“ für den Average-Buffers,
   - aber das ist heuristisch – saubere CFR-Garantie gibt es erst ab Start der MCCFR-Traversals.

### 2.3. Off-Policy-Bedenken

- BC auf Bot-Historien ist **rein supervised**, kein CFR-Update.
- ESR/MCCFR-Updates sind danach **on-policy** bzgl. eurer fortlaufenden Strategien.
- Ihr dürft **nicht** versuchen, aus Bot-Histories *CFR-Advantage*-Targets zu machen, ohne exakte Kenntnis der damals gespielten Strategien & Counterfactual-Reach-Korrekturen:
  - Sonst off-policy Bias in den Regret-Schätzungen,
  - bricht Konvergenzeigenschaften.

**Sicheres Schema:**
- BC = reines Policy-Prior.
- Alle Regret-/Value-Schätzungen nur aus selbst gesampelten CFR-Episoden.

---

## 3) „ONE net: near-GTO + maximaler Exploit“ – geht das?

### 3.1. Mathematische Konfliktlage

Ihr habt zwei Objektive:

1. **GTO-Robustheit:**  
   Minimiere Exploitability:
   \[
   \min_\sigma \max_{\tau} u(\sigma,\tau).
   \]
2. **Best-Response zu fixem Gegner \(\pi^\text{opp}\):**  
   Maximiere:
   \[
   \max_\sigma u(\sigma,\pi^\text{opp}).
   \]

Wenn ihr \(\pi^\text{opp}\) fixiert und nur BR darauf trainiert, bekommt ihr eine Strategie \(\sigma^\text{BR}\), die typischerweise:
- stark exploitabel gegenüber anderen Gegnern ist,
- sehr weit von NE entfernt sein kann.

**Kombination** durch convex combination:
\[
\sigma^\text{mix} = (1-\lambda) \sigma^\text{GTO} + \lambda \sigma^\text{BR}
\]
ist völlig **sauber**:

- Erwartungswert gegen beliebigen Gegner \(\tau\) ist:
  \[
  u(\sigma^\text{mix},\tau) = (1-\lambda)u(\sigma^\text{GTO},\tau) + \lambda u(\sigma^\text{BR},\tau).
  \]
- Exploitability:
  \[
  \text{exploit}(\sigma^\text{mix}) \le (1-\lambda)\,\text{exploit}(\sigma^\text{GTO}) + \lambda\,\Delta,
  \]
  wobei \(\Delta\) begrenzt ist durch die Differenz zwischen Worst-Case-Payoff und BR-Payoff gegen Best-Responder des Gegners. Oberbound grob aus Payoff-Range abschätzbar (in HUNL begrenzt durch Stacksize).

Ihr könnt **exploitability-budget** definieren:
- Nehmt \(\lambda\) so, dass \(\text{exploit}(\sigma^\text{mix}) \le \epsilon_\text{max}\).

### 3.2. In EINEM Netz vs getrennten Policies

Zwei Varianten:

1. **Ein Policy-Net mit Parametrisierung über „Regime“-Input:**
   - Input-Feature z.B. `mode ∈ {GTO, exploit}` oder kontinuierliches λ.
   - Netz lernt \(\pi_\theta(a|s,\lambda)\), sodass:
     - für \(\lambda=0\): GTO-nahe,
     - für \(\lambda=1\): BR-nahe.
   - Training:
     - CFR-Update auf \(\lambda=0\),
     - BR-RL/SL-Update auf \(\lambda=1\),
     - evtl. Interpolation für mittlere λ.

   Problem:
   - Trainingsziele **konfliktieren lokal** im Parameterraum,
   - es gibt keine Garantie, dass \(\pi_\theta(\cdot|s,0)\) tatsächlich die CFR-Lösung bleibt,
   - ihr könnt Konvergenz der GTO-Policy zerstören.

2. **Zwei getrennte Netze + externer Mischer:**
   - \(\pi^\text{GTO}_\theta\) via Deep CFR,
   - \(\pi^\text{BR}_\phi\) via RL / Supervised BR-Suche gegen Population/Slumbot,
   - Laufzeitmischer:
     - Wählt mit Wahrscheinlichkeit \((1-\lambda)\) Aktion aus \(\pi^\text{GTO}\),
     - mit Wahrscheinlichkeit \(\lambda\) aus \(\pi^\text{BR}\),
     - oder mischt auf Action-Probs-Ebene.

   Mathematische Vorteile:
   - CFR-Konvergenz von \(\pi^\text{GTO}_\theta\) bleibt unberührt,
   - BR-Policy kann völlig unabhängig auf Population getuned werden,
   - Exploitability von \(\pi^\text{GTO}_\theta\) ist analysierbar; dann mischt ihr bewusst.

### 3.3. Empfehlung

Für *mathematische Klarheit* und *Engineering-Sicherheit*:

- **Ja**, das Ziel „near-GTO + Exploit“ ist kohärent.
- **Empfehlung:**  
  - Trainiert **separat**:
    - Deep-CFR-Net (GTO-Head),
    - Exploit-Net (BR-Head) gegen Population/Slumbot.
  - Nutzt danach einen **expliziten Mischer** mit kontrolliertem \(\lambda\).

Wenn ihr unbedingt „ein Netz“ wollt:
- Besser als „shared body + zwei Heads“:
  - gemeinsam geteiltes Feature-Extractor-Backbone,
  - zwei getrennte Output-Köpfe (GTO-Policy, Exploit-Policy),
  - CFR-Update wirkt *nur* auf GTO-Head (und Backbone),
  - BR-RL-Update wirkt *nur* auf Exploit-Head (und Backbone),
  - ggf. gradient surgery, um GTO-Stabilität zu schützen.

---

## 4) Evaluation: nash_conv & AIVAT

### 4.1. Abstracted nash_conv als Proxy

- Nash-Conv in \(\tilde G\) misst:
  \[
  \text{nash\_conv}(\sigma) = u(\text{BR}_1(\sigma_2),\sigma_2) + u(\sigma_1,\text{BR}_2(\sigma_1)) - 2 u(\sigma_1,\sigma_2).
  \]
- Für symmetrische 2-Player-Zero-Sum ist das doppelte der Exploitability (je nach Konvention).
- Problem:  
  - Es sagt nichts direkt über Exploitability im echten G,
  - aber: geringer nash_conv in \(\tilde G\) bedeutet „gute Lösung *innerhalb der Abstraktion*“,
  - zusammen mit Head-to-Head vs Slumbot + Population ist das ein **akzeptabler Praxis-Proxy**.

Empirische Heuristik:
- Wenn euer nash_conv in \(\tilde G\) < **1–2 bb/100** ist, und Abstraktion okay, **könnt ihr realistisch** erwarten:
  - solide Performance vs Slumbot,
  - robuste Leistung gegen normale Population.

### 4.2. Leichtgewichtiges AIVAT-Schema

AIVAT = Action-Informed Value Approximation Tool:
- Idee:
  - Nutzen eines Baseline-Value-Modells \(b(s)\), um Varianz durch Luck (Karten, random Actions) zu reduzieren,
  - Beobachtete Rückzahlung \(R\) wird ersetzt durch:
    \[
    \hat R = b(s_0) + \sum_{t} \left( r_t - \mathbb{E}[r_t | s_t] \right),
    \]
    wo \(r_t\) die Inkrement-Rewards sind und \(\mathbb{E}[r_t | s_t]\) durch \(b\) approximiert wird.

Praktikable Minimalversion für HU-NL:

1. **Baseline-Value-Funktion \(b(s)\):**
   - Trainiert ein Netz \(b_\psi(s)\), das aus
     - öffentlichen Karten,
     - Position,
     - Potgröße, Stacks,
     - eigenen geleakten Hole-Cards beim Training
     den *erwarteten EV (in bb)* approximiert.
   - Dazu:
     - Nutzt eure eigene Policy (z.B. GTO-Net),
     - simuliert viele Self-Play-Episoden,
     - trainiert \(b_\psi\) mit MSE auf realized return.

2. **Variance-Reduction beim Match vs Slumbot/Population:**
   - Während Evaluation:
     - Für jeden Decision-Point \(t\) mit State \(s_t\), berechnet \(b_\psi(s_t)\).
     - Entweder:
       - Nutzt eine simple „one-step“-AIVAT:
         \[
         \hat R = R - (b_\psi(s_K)-b_\psi(s_0)),
         \]
         also subtract change im Value-Schätzer,
       - oder (minimal komplexer):
         - Bei jeder Chance-Node (Kartendeal) zieht ihr baseline-Expectation ab und addiert sie als Konstante wieder.

3. **Lightweight-Implementation (Simplifiziert):**
   - Noch simpler, aber brauchbar:
     - Trainiert \(b_\psi\) nur auf dem *Startstate* (Preflop):
       - \(b_\psi\)(ButtonStack, Blinds, HoleCards) = erwarteter Return mit eurer Policy bei zufälligen Boards & Gegner.
     - Für jede Hand:
       \[
       \hat R = R - (b_\psi^\text{hero}(s_0) - b_\psi^\text{villain}(s_0)),
       \]
       oder analog symmetrisch.
   - Dadurch wird vor allem Karten-Varianz reduziert (Preflop Equity Unterschiede).

Das ist kein „voller“ AIVAT, aber:
- sehr leicht zu implementieren,
- reduziert Varianz deutlich gegenüber purem ROI,
- erfordert nur ein Value-Netz + Logging.

---

## 5) Konkrete Config & Compute-Schätzung

**Warnung:** Alles, was jetzt kommt, ist necessarily grob; HUNL ist groß. Ich gebe euch eine *realistische Skizze*, keine Garantie.

### 5.1. Action-Abstraktion

Um Nähe zu Slumbot (200bb, fc + Größen):

- Preflop/Flop:
  - Aktionen: fold, call, bet/raise {0.33p, 1.0p, all-in}
- Turn/River:
  - fold, call, bet/raise {0.5p, 1.0p, all-in}

Das gibt:
- Max ~4 actions per decision (inkl. fold/call),
- etwas feiner Preflop/Flop, um Preflop-Dynamics abzubilden.

Wenn Compute knapp ist, könnt ihr auch:
- Einheitlich {0.5p, 1p, all-in}.

### 5.2. Informationszustands-Features

Pro Spieler-Infoset (Eingabe ins Netz):

- **Kartencodierung:**
  - One-hot: 52 Karten,
  - Hero Holecards: 2×52 („card-present“),
  - Board: bis 5×52,
  - Maske, damit nicht gezogene Karten 0 bleiben.
  - Optional: kompaktere 52-Bit-Maske für „absent/present“.

- **Betting-State:**
  - Potgröße (normiert auf Startstack),
  - Effektiver Stack (in Pot-Multiples),
  - Aktueller Street (0=Preflop,1=Flop,2=Turn,3=River),
  - Letzte Betgröße (in Pot-Multiples),
  - Anzahl Raises in dieser Street,
  - Position (BTN/BB),
  - Wer ist am Zug.

- **History-Features (kompakt):**
  - Binning:
    - #Bets / #Calls / #Folds pro Street,
    - Binary Flags: „Villain bisher aggressor?“, „Hero capped?“ etc.

Gesamtfeature-Dimension im Bereich 300–500 ist machbar.

### 5.3. Netzarchitektur

**Advantage-Net:**

- Input: ~400-dim vector,
- 3–4 Dense-Layer mit 512–1024 Units, ReLU oder SiLU,
- Output: |A|-dimensionale Advantage-Schätzung (4 actions).

Beispiel:
- FC(400→1024) → ReLU
- FC(1024→1024) → ReLU
- FC(1024→512) → ReLU
- FC(512→|A|)

**Average-Policy-Net:**
- gleiche Architektur, aber Softmax-Output (Policy-Logits).

Parameteranzahl:
- Größenordnung 5–15 Mio Parameter, gut auf 1 GPU.

### 5.4. Deep CFR Hyperparameter (für erste ernsthafte Runs)

- **Num Iterationen**: 200–500 (CFR-Iterationen).
- **Traversals pro Iteration**:
  - Richtwert: 10k–100k MCCFR-Traversals pro Spieler.
  - Da HU-symmetrisch: ihr könnt beide Rollen für einen Agenten spielen.

Konkret minimal für „nützlich“:
- 200 Iterationen × 20k Traversals ≈ 4 Mio besuchte Infosets.

- **Train_steps pro Iteration (Advantage-Net)**:
  - 1–2 „Epochs“ über Reservoir-Samples (max 1M–2M Samples).
  - Praktisch im Code: z.B. 5k–10k Mini-Batches à 512.

- **LR**:
  - Start 1e-3,
  - Cosine-Decay oder Step-Decay (z.B. 1e-3 → 3e-4 → 1e-4).

- **Memory / Replay:**
  - Advantage-Buffer: 1–3 Mio Samples (Infoset-Features + target advantages).
  - Average-Policy-Buffer: 1–3 Mio Samples.

### 5.5. Compute-Abschätzung

Angenommen:
- 1 GPU mit ~TFLOP-Level einer V100/A100 (oder ein Pod mit mehreren solcher),
- Forward+Backward pro Sample (Batch 512, Network ~10M param) ca. 1–2 ms / Batch.

Grobe Rechnung:

- Pro Iteration:
  - 20k Traversals (HUNL, 200bb) sind teuer, sagen wir:
    - ca. 0.5–1 Sek pro 1k Traversals auf GPU-beschleunigtem Python/Cpp-Mix ⇒ 10–20 Sek pro Iteration.
  - Training:
    - 10k Batches × 2ms = 20s pro Iteration.

→ 1 Iteration ≈ 30–40s.

- 200 Iterationen:
  - 200 × 40s ≈ 8000s ≈ ~2.2 Stunden auf *einer* gut ausgelasteten GPU.

Das ist **optimistisch**; mit Python-Overhead/OSS-Implementierung, I/O, Debugging:

- Realistisch: 5–10 GPU-Stunden für einen **„Mid-Quality“-Run**,
- 20–50 GPU-Stunden für einen **besseren, feinabgestimmten Run**.

Ob ihr damit Slumbot **deutlich** schlagt, ist unsicher; aber:
- Chance auf „kompetitive“ Performance ist realistisch in 20–50 GPU-Stunden,
- für klar deutlich > GTO-Wizard-Niveau gegen Slumbot ist das eher *unterdimensioniert* (da redet man typischerweise von vielen 100 GPU-Stunden plus viel Domänenwissen).

---

## 6) Potentielle FATAL-Flaws & Höchstrisikofaktor

Mögliche gravierende Stolpersteine:

1. **Fehlerhafte MCCFR-Implementierung** (Sampling, Reach-Weights, Action-Probs):
   - Ihr habt Leduc validiert – gut.
   - Aber sicherstellen, dass:
     - dieselben Fixes in HU-NLHE verwendet werden,
     - keine versteckten Bugs (z.B. in abstracted action_probabilities) vorliegen.

2. **Advantage-Net-Training-Bias:**
   - Unsaubere Reservoir-Samples,
   - zu starke Korrelation zwischen Samples,
   - falsche Targets (z.B. normalisierte Regrets vs. raw advantages gemischt).

3. **Average-Policy falsch repräsentiert / genutzt:**
   - Wenn ihr versehentlich die letzte Iteration statt der averaged Policy spielt, kann Exploitability sehr hoch sein.

4. **Abstraktion zu grob oder inkonsistent:**
   - Z.B. All-in-Knopf in Spots, wo es strategisch nie sinnvoll ist,
   - Oder keine Option für „smallish“ Bet auf River → massiv exploitable.

5. **Meta-Coach (LLM) ändert Hyperparameter / Objective während Lauf**:
   - Wenn der Meta-Loop mitten in der CFR-Optimierung Objectives ändert (z.B. mischt BC / RL-Loss in CFR-Loss), geht jede ernsthafte CFR-Theorie flöten.
   - Lasst den Meta-Coach nur:
     - Runs *beenden* und neue Runs mit *neuen, festen Hyperparametern* starten,
     - nicht Life-Objective während einer Deep-CFR-Laufzeit umdefinieren.

**Einzelner höchstriskanter Annahmefehler (aus meiner Sicht):**

> **„Deep CFR mit relativ wenigen Iterationen/Traversals auf stark abstrahiertem HU-NLHE liefert *automatisch* eine nahe-GTO-Strategie, die Slumbot deutlich schlägt.“**

- Das ist **uns
