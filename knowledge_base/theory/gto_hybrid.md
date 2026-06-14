# GTO hybrid (near-GTO baseline + adaptive regime switch)

## Math (OpenAI gpt-5.1)

Ich strukturiere das in drei Blöcke, mit Formeln und so wenig „Story“ wie möglich.

---

## 1) GTO-Approximation mit dem, was ihr habt

### 1.1 Fundamentale Zielgröße

Sei  
- \(G\) das echte NLHE-Spiel,  
- \(\sigma^*\) ein Nash-Gleichgewichts-Strategieprofil,  
- \(u_i(\sigma)\) der erwartete Wert für Spieler \(i\) im Spiel (in bb/Hand o.ä.).  

Für 2‑Spieler Nullsummen gilt:

\[
\text{Exploitability}(\sigma) 
= \max_{\tau} u_2(\sigma,\tau) - u_2(\sigma^*, \sigma^*)
= \max_{\tau} u_1(\tau,\sigma) - u_1(\sigma^*, \sigma^*)
\]

In bb/100: \(\epsilon := \text{Exploitability}(\sigma)\) ist der maximal mögliche Verlust ggü. perfekter GTO-Spielweise, wenn ein adversarialer Gegner perfekt ausnutzt.

Nahe GTO heißt: \(\epsilon\) „klein“ (z.B. < 5–10 bb/100) auf der relevanten Teilmenge der Zustände (Positionen, Stackgrößen etc.).

---

### 1.2 Deep CFR (Neural) als Kern-Baseline

Eure Validierung: Leduc mit Deep CFR, NashConv von 2.33 → 0.33.  
In einem 2‑Spieler Nullsummen-Spiel entspricht NashConv im Wesentlichen der Summe der Exploitabilities der Spieler; für symmetrisches Spiel:

\[
\text{NashConv}(\sigma) = \text{Exploitability}_1(\sigma) + \text{Exploitability}_2(\sigma) \approx 2\epsilon
\]

also \(\epsilon \approx \frac{\text{NashConv}}{2}\).

**Übertrag auf NLHE:**

1. **Spielabstraktion**  
   - Diskretisierung der Action-Sizes: z.B. {Check, 33%, 75%, 125%, All-in} statt kontinuierlich.  
   - Bucketing von Handstärken bzw. Equity/Draw-Struktur (ähnlich Pluribus / Libratus-Patterns, aber ihr könnt die Infos aus Acevedo verwenden: Kategorie-Splitting nach „top pair good kicker“, „nut FD + overcards“ etc.).  
   - Board-Klassen (trocken / middling / wet, paired / unpaired etc.).

2. **Deep CFR auf dem abstrahierten Spiel**  
   - Genau die OpenSpiel+PyTorch-Pipeline, aber auf euer NLHE-Abstraktionsspiel.  
   - Output: Strategieprofile \(\hat{\sigma}\) mit einem **upper bound** auf die Exploitability im abstrahierten Spiel: \(\epsilon_{\text{abs}}\).

3. **De-Abstraktion (Action Translation)**  
   - Mapping von abstrakten Actions auf reale Betgrößen:  
     - z.B. „75% Pot“ im Model → 70–80% Pot in Realität, mit feinem Jitter.  
   - Hands aus Buckets auf konkrete Combos mappen: innerhalb eines Buckets gleiche Mischstrategie.  

Die Gesamtexploitability im echten Spiel ist dann:

\[
\epsilon_{\text{real}} \le \epsilon_{\text{abs}} + \epsilon_{\text{abstraktion}}
\]

\(\epsilon_{\text{abstraktion}}\) ist der Fehler durch Bucketing + Action-Diskretisierung. Den kann man grob upper-bounds messen, indem man im abstrahierten Spiel:

- verschiedene Abstraktionsgranularitäten vergleicht (coarse vs. fine Buckets) und
- die Strategie der feineren Abstraktion als Gegner für die grobe benutzt.

Differenz in EV stellt eine empirische Obergrenze für den Abstraktionsfehler dar.

**Realistisch erreichbarer GTO-Grad**

Mit moderner Hardware (GPU-Pods, Deep CFR oder DCFR) und guter Abstraktion:

- Exploitability im abstrahierten Spiel im Bereich \< 10^-3 Pot pro Hand ist üblich in Forschung (Libratus, Pluribus).  
- Übertragen auf Echtgeld: \(\epsilon_{\text{real}} \lesssim 1–3\) bb/100 für typische Stacks/Spots ist realistisch, sofern
  - Action-Sets sinnvoll (ca. 4–6 Sizes/Street),
  - Board/Hand-Buckets ausreichend fein (100–1000 Buckets, je nach Street).

**Konkrete Pipeline für euch**

1. **Preflop**  
   - Push/Fold Nash-Solver (MCCFR) nutzen für <= 20–25 bb Stacks → nahezu GTO Push/Fold-Ranges.  
   - Für deeper Stacks: Buch-Ranges aus *Modern Poker Theory* als Startpolicy. Dann:
     - Preflop-NLHE mit Action-Abstraktion (Raise-Sizes: 2–2.5x, 3x, 4x, All-in, etc.) als separates Spiel definieren.
     - Deep CFR laufen lassen, beginnend von Buch-Ranges als initial policy (warm start).  
   - Output: Preflop-Policy \(\hat{\sigma}^{\text{PF}}\) mit niedriger abstrahierter Exploitability.

2. **Postflop**  
   - Für typische Pot-Konfigurationen (Single-Raised Pot, 3bet pot, Blind vs Blind, etc.) getrennte Subgames und Strategien trainieren.  
   - Start-Approximation aus Acevedo/Chen:  
     - z.B. C-Bet-Frequenzen durch Toy-Game-Formeln (s.u.),  
     - Range-Balancing auf Basis MDF etc.  
   - Dann Deep CFR verfeinern.

3. **Exploit-Bot**  
   - Eure aktuelle Exploiter-Policy \(\sigma^{\text{exploit}}\) wird zusätzlich als explizites „Best-Response-orientiertes“ Policy-Netz trainiert, das GTO-Baseline als Prior nutzt, aber RL-artig auf Population-Leaks optimiert.

---

## 2) Bill Chen / Toy-Games → Near-GTO-Baseline ohne Solver

Kernideen, die ihr mathematisch nutzen könnt:

### 2.1 Indifferenzprinzip

In Nullsummen-Spielen im Gleichgewicht gilt: der Gegner ist indifferent zwischen allen Reaktionen, die er mit positiver Wahrscheinlichkeit spielt.

Formal, einfaches River-Bluff-Spot:

- Pot: \(P\), Hero kann mit Frequenz \(f_B\) bluffen, Betgröße \(B\).  
- Villain callt mit Frequenz \(c\).  
- Hero hat zwei Handklassen: Value (V) und Bluff (L).  
- EV des Calls gegen Heros gemischte Strategie:

\[
\text{EV}_\text{Villain}(\text{Call}) = x \quad \text{EV}_\text{Villain}(\text{Fold}) = 0
\]

Im Gleichgewicht: \(x=0\) (Indifferenz).

Konkreter:

Sei  
- Bluff-Anteil in Heros Bet-Range: \(\alpha\),  
- Value-Anteil: \(1-\alpha\).

Villain gewinnt bei Call gegen Bluff: \(P+B\)  
und verliert bei Call gegen Value: \(B\).

\[
\text{EV}_\text{Villain}(\text{Call}) = \alpha (P+B) - (1-\alpha) B = 0
\]

\[
\Rightarrow \alpha (P+B) = (1-\alpha) B \Rightarrow \alpha = \frac{B}{P+2B}
\]

Das ist die optimale **Blufffrequenz in der Bet-Range** für diesen 1-Street-Toyspot (equal equity 0/1 Setup).

---

### 2.2 Chen/Ankenman-Formel: \(\alpha = \frac{s}{1+s}\)

Viele Quellen geben die Blufffrequenz direkt in Abhängigkeit des Bet-Sizes \(s = B/P\) (Bet als Pot-Multiple). Der sauber hergeleitete Standardfall (auf 0/1-Spiel kalibriert) ist

\[
\alpha^* = \frac{s}{1+s} \quad\text{(unter geeigneter Normalisierung des Payoff-Spiels)}
\]

Der exakte Ausdruck hängt von der gewählten Toy-Game-Definition ab (Chen benutzt [0,1]-Verteilungen statt 0/1-Binär-Payoffs). Wichtig: strukturell habt ihr immer Form

\[
\alpha^*(s) = \frac{\text{Funktion in } s}{\text{Funktion in } s + \text{Konstante}}
\]

Ihr könnt die exakten Toy-Setups aus *The Mathematics of Poker* nehmen und für die dortige Payoff-Normalisation:

- Held-out-Formeln für **Gleichgewichts-Blufffrequenzen** je Betgröße,
- und daraus Range-Aufteilungen ableiten.

Nutzbar in der Engine:

**Heuristik für River-Bets:**

- Input: \(s = B/P\) (Ziel-Betgröße).  
- Compute optimale Bluff-Dichte \(\alpha^*(s)\) aus Toy-Formel (z.B. \(\alpha = s/(1+s)\) oder die korrekte Variante für euer Setup).  
- Range-Aufteilung:
  - sortiere Hände nach EV als Bet (Value) vs. Check.  
  - definier Value-Teil bis Value-Grenzhand (z.B. Top X %).  
  - Bluff-Kandidaten = Hände mit klar negativem Showdown-EV.  
  - wähle so viele Bluffs, dass \(\frac{\text{\#Bluffs}}{\text{\#Value + \#Bluffs}} \approx \alpha^*(s)\).

Damit bekommt ihr für alle „reinen“ River-Entscheidungen eine **toy-game-kalibrierte Balance**, auch ohne vollständigen Solver.

---

### 2.3 Mindest-Verteidigungsfrequenz (MDF)

MDF ergibt sich aus der Bedingung, dass der Gegner mit einem reinen Bluff-Einsatz nicht automatisch +EV hat.

Pot vor Bet: \(P\), Bet: \(B\).  
Villain blufft immer, Hero foldet mit Frequenz \(f\).  
EV des Bluffers:

\[
\text{EV}_\text{Bluff} = f \cdot P - (1-f) \cdot B
\]

MDF ist kleinste Call-Frequenz \(c = 1-f\), so dass \(\text{EV}_\text{Bluff} \le 0\):

\[
fP - (1-f) B \le 0 \Rightarrow fP \le (1-f) B
\Rightarrow f \le \frac{B}{P+B}
\Rightarrow c \ge 1 - \frac{B}{P+B} = \frac{P}{P+B}
\]

**MDF-Formel:**

\[
\text{MDF} = \frac{P}{P+B}
\]

Benutzbar als baseline-call-Frequenz beim Bluffcatchen, wenn ihr annehmt, dass Villain ungefähr „maximal“ bluffen könnte.

Strategisch:  
- Sortiere deine Hände nach EV zum Call vs. Fold (bzw. nach Handstärke / Blockerqualität).  
- Call so viele Combos, dass deine Call-Frequenz \(\approx \text{MDF}\).

Das ist „GTO-ish“ gegen einen Bluff-heavy Pot-Multiple, solange die Bet-Range des Gegners nicht massiv value-lastig ist.

---

### 2.4 [0,1]-Toy-Games (Chen & Ankenman)

Grundsetup (stark vereinfacht, aber mathematisch brauchbar):

- Spieler 1 zieht \(x \sim U[0,1]\) (Handstärke).  
- Spieler 2 zieht \(y \sim U[0,1]\), unabhängig.  
- beide kennen ihr eigenes, nicht das gegnerische \(x,y\), aber die Verteilungen.  
- Moves: bet/check, call/fold, ggf. variierende Betgrößen.  

Nash-Strategien haben Form:

- Es gibt **Schwellenwerte** \(t_B, t_C\):  
  - Wenn \(x > t_B\) → Player 1 bettet for Value.  
  - Wenn \(x < t_L\) → Player 1 kann mit optimaler Frequenz bluffen (mixing).  
  - Player 2 callt mit \(y > t_C\) und foldet sonst.  

Indifferenz-Bedingungen liefern Gleichungen für \(t_B, t_C\) und die Blufffrequenz:

Beispiel (einfacher Case, eine Betgröße):

1. Bedingung: Player 2 ist indifferent zwischen Call/Fold mit Grenzhand \(y = t_C\).  
2. Bedingung: Player 1 ist indifferent zwischen Bet/Check mit Grenzhand \(x = t_B\).

Diese Gleichungen kann man **auf unsere NLHE-Situationen mappen**, indem man:

- \(x\) als quantile der eigenen Handstärke-Verteilung interpretiert (z.B. EQ vs Range),  
- \(y\) als quantile gegnerischer Handstärke,  
- und Betgröße \(s\) als \(B/P\).

Dann liefert das Toy-Game:

- Value-Schwelle (ab welcher Equity vs Range man Value betten sollte),  
- Blufffenster (unterhalb welcher Equity man Bluffs mischen darf),  
- optimale Mischfrequenzen (z.B. Bluffanteil in bet-Range als Funktion von \(s\)).

**Implementierbare Heuristik:**

Für jede Street:

1. Approximiere deine Equity-Verteilung \(F_H(e)\) gegen geschätzte Gegner-Range.  
2. Wähle eine Betgröße \(s\).  
3. Aus Toy-Game-Gleichungen ableiten:
   - Equity-Grenze \(e_V\) (Value),  
   - Equity-Grenze \(e_L\) (Bluff-Untergrenze),  
   - Blufffrequenz in \([0,e_L]\) bzw. relative Bluff/Value-Ratio.  
4. Mische gemäß dieser Schwellen, um „balanced by construction“ zu sein.

Damit habt ihr eine **analytische near-GTO-Baseline**, ohne vollständigen Solver, die ihr als Prior ins Netz füttern könnt.

---

## 3) Regime-Switch: Wann Exploit > GTO?

Wir brauchen eine quantitative Bedingung:

> Exploiten lohnt nur, wenn der EV-Gewinn gegen den Gegner-Leak den zusätzlichen EV-Verlust durch eigene Exploitability übersteigt.

### 3.1 Notation

- \(\sigma^{\text{GTO}}\): eure near-GTO-Baseline (Exploitability \(\epsilon\)).  
- \(\sigma^{\text{EXP}}\): eine exploitative Policy, die auf Population/Opponent getuned ist.  
- \(u(\sigma_H,\sigma_V)\): EV (bb/Hand) von Hero vs Villain.

Definiere:

1. **GTO-versus-Gegner-EV**:
   \[
   v_{\text{GTO}} := u(\sigma^{\text{GTO}}, \sigma_V)
   \]

2. **Exploit-EV gegen aktuelle Schätzung der Gegnerstrategie \(\hat{\sigma}_V\)**:
   \[
   v_{\text{EXP}} := u(\sigma^{\text{EXP}}, \hat{\sigma}_V)
   \]

3. **Eigen-Exploitability der Exploit-Policy** (Upper bound):
   \[
   \epsilon_{\text{EXP}} := \max_{\tau} u(\tau, \sigma^{\text{EXP}}) - u(\sigma^{\text{GTO}}, \sigma^{\text{GTO}})
   \]
   Praktisch: \(\epsilon_{\text{EXP}}\) ist schwer exakte zu berechnen, aber ihr könnt:
   - GTO-Bot als Gegner nutzen: \(\Delta u = u(\sigma^{\text{GTO}},\sigma^{\text{EXP}}) - u(\sigma^{\text{GTO}},\sigma^{\text{GTO}}) \approx -\epsilon_{\text{EXP}}\) (lower bound),  
   - plus Sicherheitszuschlag.

### 3.2 Safe-Exploit-Kriterium

Wir wollen nur exploiten, wenn der **sichere Mehrwert** positiv ist.  
Der Mehrwert ist

\[
\Delta v := v_{\text{EXP}} - v_{\text{GTO}}
\]

Aber beide Terme sind geschätzt, plus Varianz. Außerdem kann der tatsächliche \(\sigma_V\) von \(\hat{\sigma}_V\) abweichen.

Sicherheits-Bound-Ansatz:

- Sei \(\widehat{\Delta v}\) der empirische EV-Unterschied (oder best estimate) aus eurem Opponent-Modell:  
  \[
  \widehat{\Delta v} \approx u(\sigma^{\text{EXP}}, \hat{\sigma}_V) - u(\sigma^{\text{GTO}}, \hat{\sigma}_V)
  \]
- Sei \(\epsilon\) die Exploitability eurer GTO-Baseline (klein).  
- Sei \(\tilde{\epsilon}\) ein Upper bound auf die **zusätzliche** Exploitability, die durch Exploit-Policy entsteht:
  \[
  \tilde{\epsilon} \approx \epsilon_{\text{EXP}} - \epsilon
  \]

Safe-Exploit-Bedingung:

\[
\widehat{\Delta v} > k \cdot \tilde{\epsilon}
\]

mit einem Sicherheitsfaktor \(k\). Eure Idee „~2·epsilon“ entspricht \(k = 2\).  

Intuition:

- Worst-Case: Villain adaptiert optimal, so dass ihr \(\tilde{\epsilon}\) mehr verliert, als ihr durch den bisher beobachteten Leak gewinnt.  
- Mit Faktor 2 verlangt ihr, dass der beobachtete Exploit-Vorsprung mindestens doppelt so groß ist wie das zusätzliche Worst-Case-Leak, d.h. selbst bei starker Adaption bleibt Netto-EV > 0.

Konkrete Entscheidungsregel in bb/100:

\[
\widehat{\Delta v} \ (\text{bb/100}) > 2 \cdot \tilde{\epsilon} \ (\text{bb/100})
\]

---

### 3.3 Live-Schätzung von \(\widehat{\Delta v}\) und \(\tilde{\epsilon}\)

#### 3.3.1 Schätzung des Gegner-Leak-EVs

Für jeden Gegner i haltet ihr ein Modell \(\hat{\sigma}_i\) (Parameter: Fold-to-Cbet, 3bet-Frequenz, River-Overfold etc.).  
Für eine bestimmte Abweichung (z.B. overfold am River):

1. Modelliert ihr zwei Policies:

   - \(\sigma^{\text{GTO}}\)  
   - \(\sigma^{\text{EXP}}\) (z.B. mehr Bluffs in Spots, wo Villain overfoldet)

2. Simuliert (oder analytisch approximiert) ihr den EV-Unterschied gegen \(\hat{\sigma}_i\):

   \[
   \widehat{\Delta v}_i = u(\sigma^{\text{EXP}}, \hat{\sigma}_i) - u(\sigma^{\text{GTO}}, \hat{\sigma}_i)
   \]

3. Statistische Sicherheit: Bei endlicher Stichprobe N Hände ist eure \(\widehat{\Delta v}_i\) noisy.  
   - Schätzt Standardfehler \(\text{SE}(\widehat{\Delta v}_i) \approx \frac{\hat{\sigma}_\text{outcome}}{\sqrt{N}}\).  
   - Nehmt ein Konfidenz-Intervall, z.B. 95% lower bound:
     \[
     \widehat{\Delta v}_i^{\text{LB}} = \widehat{\Delta v}_i - 1.96 \cdot \text{SE}(\widehat{\Delta v}_i)
     \]
   - Setzt in die Safe-Exploit-Bedingung die **untere Schranke** ein:
     \[
     \widehat{\Delta v}_i^{\text{LB}} > 2 \cdot \tilde{\epsilon}
     \]

Damit exploitet ihr erst, wenn der beobachtete Vorteil statistisch signifikant und groß genug ist.

#### 3.3.2 Schätzung der zusätzlichen Exploitability \(\tilde{\epsilon}\)

Offline-Precompute:

1. Lasst GTO-Bot vs. GTO-Bot spielen → Basis-Quote (0 oder minimal).  
2. Lasst Exploit-Bot vs. GTO-Bot spielen:
   - beobachteter EV: \(u(\sigma^{\text{EXP}},\sigma^{\text{GTO}})\)  
   - dann
     \[
     \tilde{\epsilon} \approx u(\sigma^{\text{GTO}},\sigma^{\text{GTO}}) - u(\sigma^{\text{EXP}},\sigma^{\text{GTO}})
     \]
     (typisch negativ für EXP).  

Das gibt euch je nach Exploit-Regel einen festen, konservativen Wert \(\tilde{\epsilon}\) in bb/100.

Wenn ihr mehrere Exploit-Module habt (z.B. River-Overbluff, Turn-Overfold), könnt ihr für jedes Modul einen eigenen \(\tilde{\epsilon}_k\) precomputen und im Live-System nur einzelne Module aktivieren, die ihre jeweilige Safe-Exploit-Bedingung erfüllen.

---

### 3.4 Konkreter Regime-Switch-Algorithmus

Für jeden Gegner i:

1. Initial: spiele \(\sigma^{\text{GTO}}\).  
2. Für jedes Exploit-Modul k (z.B. „Villain foldet zu viel auf 3-Bets“):
   - Online-Schätzung des Leaks (Parameter \(\theta_{i,k}\)), z.B. empirische Fold-Frequenz.  
   - Aus \(\theta_{i,k}\) + analytischem Modell/Simulation: erwarteter Exploit-Gewinn \(\widehat{\Delta v}_{i,k}\).  
   - Schätze Varianz/SE → Lower bound \(\widehat{\Delta v}_{i,k}^{\text{LB}}\).  
   - Known \(\tilde{\epsilon}_k\) aus Offline-Benchmark gegen GTO.
   - Wenn
     \[
     \widehat{\Delta v}_{i,k}^{\text{LB}} > 2 \cdot \tilde{\epsilon}_k
     \]
     → Modul k **aktiv** (abweichen von GTO im entsprechenden Subspace

## Theory (Claude)

# HYBRID-ARCHITEKTUR: GTO-Default mit Exploit-Override

Lass mich brutal ehrlich anfangen: Eure -207 bb/100 gegen Slumbot sind kein "Tuning-Problem", sondern ein **Architektur-Fehler**. Euer Exploiter hat keine sichere Default-Strategie — er "exploitet" auch dann, wenn nichts zu exploiten ist, und VPIP 0.75 ist purer Selbstmord gegen balanciertes Spiel. Die Lösung ist nicht "weniger exploiten", sondern **eine echte GTO-Basis, von der aus man kontrolliert abweicht**.

---

## 1) DIE ARCHITEKTUR

```
                    ┌─────────────────────────────────┐
   Spielzustand ───▶│   FEATURE / OBSERVATION LAYER    │
   (Hand, Board,    │   (Hand-Buckets, Pot-Odds, SPR,  │
    Aktionen,       │    Position, Aktions-History)    │
    Stats)          └──────────────┬──────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
   ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
   │  GTO-BASELINE    │  │ REGIME-DETEKTOR  │  │  EXPLOIT-LAYER   │
   │  σ_GTO           │  │  (Bayesian)      │  │  Δ-Adjustments   │
   │  Deep CFR +      │  │  liefert:        │  │  pro Gegner-Leck │
   │  Buch-Ranges     │  │  λ ∈ [0,1]       │  │                  │
   └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘
            │                     │                     │
            └─────────────────────┼─────────────────────┘
                                  ▼
              σ_final = (1-λ)·σ_GTO  ⊕  λ·σ_exploit
              mit HARD-CAP: λ ≤ λ_max(confidence, exploitability)
                                  │
                                  ▼
                          AKTION + Sizing
```

### Kernprinzip: **GTO ist der Anker, Exploit ist die Abweichung**

`σ_final = blend(σ_GTO, σ_exploit, λ)` — wobei `λ` der **Exploit-Anteil** ist, gesteuert vom Regime-Detektor. Bei `λ=0` spielt ihr reine GTO (unexploitable). Das fixt Slumbot sofort.

**Wichtig:** Blending NICHT naiv linear auf Wahrscheinlichkeiten mischen ohne Kontrolle — ihr braucht einen **Exploitability-Budget**:

```python
def safe_blend(sigma_gto, sigma_exploit, lam, max_exploitability):
    # Naiver Blend
    sigma = (1 - lam) * sigma_gto + lam * sigma_exploit
    # Wie weit weicht das von GTO ab? (in EV-Verlust-Worst-Case)
    deviation = estimate_exploitability(sigma, sigma_gto)
    if deviation > max_exploitability:
        # Skaliere lam zurück bis im Budget
        lam = solve_lam_for_budget(sigma_gto, sigma_exploit, max_exploitability)
        sigma = (1 - lam) * sigma_gto + lam * sigma_exploit
    return sigma
```

Das ist der entscheidende Punkt: **Ihr begrenzt, wie ausnutzbar ihr selbst werdet.** Gegen Slumbot bleibt das Budget bei ~0, ihr spielt GTO.

---

### REGIME-DETEKTOR — die wichtigste neue Komponente

Der Detektor muss EINE Frage beantworten: *"Wie sicher bin ich, dass dieser Gegner exploitable ist, und wie stark?"* → Output: `λ` pro Decision-Node.

#### Signale (live, pro Gegner gesammelt):

| Signal | Was es misst | GTO-Indikator | Exploit-Indikator |
|---|---|---|---|
| **Fold-to-CBet** | Folds vs erwartete GTO-Frequenz | ≈ MDF | >> MDF (überfoldet) oder << (klebt) |
| **Fold-to-3Bet** | 3Bet-Defense | balanciert | überfoldet → 3Bet-Bluff |
| **VPIP/PFR-Gap** | Preflop-Looseness | tight gap | großer Gap = passiv/loose |
| **WTSD / W$SD** | Showdown-Tendenz | ~GTO-Range | Calling-Station / Nit |
| **Bet-Sizing-Tells** | Size↔Strength-Korrelation | dekorreliert | korreliert (lesbar) |
| **Aggression-Frequenz** | AFq pro Street | balanciert | extrem → exploitable |
| **Limp/Open-Limp** | klassisches Fischsignal | nie | ja → schwach |

#### Schwellen & Statistische Signifikanz (Bill Chen liefert hier den Hebel!)

Ihr dürft **nicht** nach 10 Händen exploiten — das ist genau, was euren Exploiter killt. Nutzt die **Bernoulli-Varianz + z-Score** aus Chen direkt:

```python
def is_leak_significant(observed_freq, gto_freq, n_samples, z_threshold=2.0):
    # Bernoulli-Varianz (Chen): sigma = sqrt(p(1-p)/n)
    p = gto_freq
    se = (p * (1 - p) / n_samples) ** 0.5
    if se == 0: return False, 0.0
    z = (observed_freq - gto_freq) / se
    return abs(z) > z_threshold, z
```

**Regel:** Ein Leck wird erst zum Exploit, wenn `|z| > 2.0` (≈95% Konfidenz). Davor: `λ = 0`, reine GTO. Das ist die direkte Anwendung eurer Chen-Auszüge ("Significance of extreme deviations in binary outcomes").

#### λ-Berechnung (Bayesian, pro Leck):

```python
def compute_lambda(leaks):
    # Jedes Leck: (z_score, ev_gain_if_exploited)
    confidence = 0.0
    for leak in leaks:
        sig, z = is_leak_significant(leak.obs, leak.gto, leak.n)
        if sig:
            # Konfidenz wächst mit z und Sample-Size, sättigt
            conf = 1 - exp(-(abs(z) - 2.0))  # 0 bei z=2, →1 bei großem z
            confidence = max(confidence, conf * leak.ev_weight)
    lam = clamp(confidence, 0.0, LAMBDA_MAX)  # LAMBDA_MAX z.B. 0.7
    return lam
```

#### Umschalt-Logik (3 Regimes):

```
λ = 0.0          → REINE GTO    (kein Read / Gegner balanciert / n < min_samples)
0 < λ < 0.7      → MIXED        (Leck erkannt, vorsichtige Abweichung)
λ → LAMBDA_MAX   → FULL EXPLOIT (großes signifikantes Leck, viel Sample)
```

**Anti-Slumbot-Schalter:** Wenn der Detektor erkennt, dass der Gegner *selbst* GTO-nah spielt (alle Frequenzen innerhalb z<2 von GTO **UND** unsere bisherigen Exploit-Versuche verlieren EV) → `λ = 0` *forced*, plus **Exploitability-Self-Check**: Misst, ob WIR gerade exploitable werden, und zieht zurück.

---

## 2) WIE BUCH-WISSEN DIE GTO-BASELINE INFORMIERT

Deep CFR auf NLHE braucht Monate Compute und konvergiert nie perfekt. **Die Bücher sind euer Warm-Start, eure Sanity-Checks und euer Fallback dort, wo das Netz noch schlecht ist.**

### Modern Poker Theory (Acevedo) — konkrete Hebel:

- **Preflop-Ranges als Prior/Anchor:** Acevedos GTO-Open/3Bet/Call-Ranges (positionsabhängig) → direkt als **Initialisierung** der Deep-CFR-Preflop-Strategie und als **Hard-Fallback** für Preflop, wo das Netz instabil ist. Preflop ist klein genug, das kann fast tabelliert sein.
- **MDF (Minimum Defense Frequency)** = `1 - bet/(pot+bet)` → liefert den **GTO-Referenzwert** für euren Regime-Detektor (Fold-to-CBet-Signal). Ohne MDF wisst ihr nicht, was "überfolden" überhaupt bedeutet.
- **Sizing-Buckets:** Acevedos Standardsizes (33/50/75/100/overbet) → das **Aktions-Abstraction-Set** für Deep CFR. Verhindert Aktionsraum-Explosion.

### Bill Chen & Ankenman — die strukturelle Theorie:

- **Indifferenz-Prinzip:** Optimale Bluff-Frequenz macht Gegner indifferent. → `Bluffs : Value = bet : (pot+bet)` am River. Das ist euer **GTO-Frequenz-Check**: Wenn Deep CFR River-Bluffs außerhalb dieses Verhältnisses ausspuckt → Bug oder Nichtkonvergenz.
- **Optimale Bluff-/Value-Ratio** und **α (optimale Bluffcatch-Frequenz)** → direkt verdrahtbare Formeln für River-Spots, wo Deep CFR teuer/ungenau ist.
- **[0,1]-Toy-Games:** Liefern die *Struktur* (polarisierte Ranges betten groß, Bluffcatcher rufen mit Frequenz α) → als **Regularisierung/Sanity-Layer** über dem Netz.
- **Varianz/CLT** → euer ganzes Regime-Detektor-Signifikanz-Framework (siehe oben).

**Konkret:** 

```python
sigma_gto = neural_deep_cfr(state)
sigma_gto = enforce_chen_constraints(sigma_gto, state)  # Bluff:Value-Ratio, MDF
sigma_gto = blend_with_book_prior(sigma_gto, acevedo_range(state), 
                                   weight=netz_unsicherheit(state))
```

Wo das Netz unsicher/unkonvergiert ist (hohe nash_conv lokal), zieht ihr stärker Richtung Buch.

---

## 3) WARUM DAS DIE SLUMBOT-NIEDERLAGE FIXT

Die -207 bb/100 hatten **drei** Ursachen, alle behoben:

1. **VPIP 0.75 (zu loose):** Eure Baseline war ein Exploiter ohne GTO-Anker. → **Neue Baseline ist Deep CFR + Acevedo-Ranges**, VPIP fällt auf
