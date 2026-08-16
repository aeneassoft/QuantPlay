# Brown (2026): Value, Bluff, and Cyclic Dominance — VNM auf der echten 169×169-Matrix

**Quelle:** Aaron Brown, *"Value, Bluff, and Cyclic Dominance: Completing the Von Neumann Poker
Project"*, Version 3. Mai 2026, SSRN-Arbeitspapier (`books/papers/Poker Math 2026/ssrn-6709840.pdf`,
36 S. inkl. Supplement S1–S9). Vollextraktion 2026-08-16, jede Zahl mit Seitenbeleg (S. = gedruckte
Seitenzahl = PDF-Seite). **Ehrlichkeits-Konvention dieses Dokuments:** Was das Paper nicht
enthält, steht unten unter NICHT-GEFUNDEN; interne Inkonsistenzen des Papers sind markiert.

**Das Spiel (VNM-Betting, S. 1–2, S. 28–29):** Pot = 1, Bet = B (Pot-relativ). Alice zuerst:
check → sofortiger Showdown um 1; bet B → Bob foldet (Alice gewinnt 1) oder callt (Showdown um
1+2B; Gewinner +1+B, Verlierer −B relativ zum Einsatz). Eine Straße, keine Raises. Hände = die
169 strategischen Preflop-Klassen von Heads-up Texas Hold'em; Showdown per echter Equity-Matrix.

---

## 1. Die vier Modellvarianten (2×2-Faktordesign, S. 3)

| Variante | Matrix | probabilistisch | transitiv |
|---|---|---|---|
| **Real** | die echte 169×169-Equity-Matrix W | ja | **nein** (7.108 nicht-transitive Tripel, S. 2) |
| **Pythagorean** | Mᵢⱼ = eᵢ²/(eᵢ²+eⱼ²), eᵢ = Zeilenmittel von W (Gewinnrate vs Zufallshand). Quadrierung gewählt, damit die extremsten Matchups wie real bei 90–95 % liegen (S. 3) | ja | ja |
| **Deterministic** | W binarisiert: Mᵢⱼ = 1 falls Wᵢⱼ > 0.5, sonst 0; exakte Gleichstände bleiben 0.5 (S. 3) | nein | **nein** |
| **Both** | Pythagorean binarisiert — am nächsten am VNM-Original (S. 3) | nein | ja |

Der klassische VNM-[0,1]-Uniform-Fall (S. 28–29, S3) ist die Ecke, in der ALLE Vereinfachungen
gleichzeitig gelten; "Both" ist sein endliches 169-Hand-Analogon.

**Equity-Matrix-Konstruktion (S. 27, S2):** Wᵢⱼ = P(i gewinnt) + 0.5·P(Split), per **exakter
Enumeration** aller C(48,5) = 1.712.304 Boards je Paarung; Suit-Fälle bei zwei suited Händen
frequenzgewichtet gemittelt. Combo-Zahlen cᵢ = 6 (Paare) / 4 (suited) / 12 (offsuit), Σ = 1.326;
Card-Removal über konditionale Prioren p(j|i) = c(j|i)/Σₖc(k|i) (z. B. AcKs blockt AKs 4→3).

---

## 2. Alle quantitativen Resultate (mit Seitenbeleg)

### 2.1 Das Zyklus-Fundament
- AKo schlägt JTs **59,5 %**; JTs schlägt 33 **53,2 %**; 33 schlägt AKo **53,4 %** (S. 2).
  Zyklus-Margen α = 0,190, β = 0,064, γ = 0,068 (S. 6); Zeilen-Equities eᴬᴷᵒ = 0,520,
  eᴶᵀˢ = 0,479, e₃₃ = 0,501 (S. 31, S6).
- Die 169er-Matrix enthält **7.108 nicht-transitive Tripel** (S. 2).
- RPS-Wahlspiel auf diesen drei Händen: Gleichgewicht AKo ≈ **20 %**, 33 ≈ **59 %**, JTs ≈ 21 %
  (S. 6) — die stärkste Hand wird am seltensten gespielt; Frequenz ∝ Beute-schlägt-Räuber-Marge,
  die eigene Stärke ist **irrelevant** (S. 6).
- Betting-Spiel auf den drei Händen (S. 7–8, S6 S. 31–33): B < 7,4: Alice bettet AKo+33 (Value),
  checkt JTs, Bob callt alles. Bei B ≈ 7,44 erreicht Bobs Call-Schwelle B/(1+2B) genau JTs'
  Posterior-Winrate 0,4685 (= 0,5·0,405 + 0,5·0,532) → Bob beginnt JTs zu folden → **JTs tritt
  als Bluff ein** (zyklischer Bluff: schwächste Hand in Roh-Equity, aber Räuber von 33/Beute von
  AKo). Bei hohem B mixt auch AKo; **33 bettet und callt bei jedem B zu 100 %** (Räuber von AKo,
  stärkste Hand gegen die Bluff-Range; volle Grid-Tabelle B = 0,001…100 in S6, S. 32).

### 2.2 Die Taxonomie des Real-Spiels (S. 8–10)
- Bei 0 < B < 0,10 bettet Alice exakt **88 Hände** (Value); Bob callt alles (S. 8).
- **Drei Phasen** (S. 8–9): (1) B 0,10–0,72: Bob beginnt zu folden, keine Bluffs — das Regime der
  meisten Poker-Spieltheorie; (2) ab B = 0,72: mittlere Value-Hände **pivoten** zu Bluffs, neue
  Bluffs treten ein; (3) ab B = 5: Exits beginnen.
- Taxonomie: **88 Value-Hände** (davon 87 "temporary value": Pivot → Exit, kein Rückkehr; **AA
  pivotet und exitet nie** im Grid) + **27 pure Bluffs** (nie Value-Phase; Eintritt erst bei
  positivem B, Exit bei hohem B) + **54 passive Hände** (betten bei keinem B) (S. 9–10).
- **Die 27 puren Bluffs (vollständige Liste, S. 9):** 32s, 42s, 43s, 52s, 53s, 54s, 54o, 62s,
  63s, 64s, 65s, 65o, 73s, 74s, 75s, 76s, 76o, 84s, 85s, 86s, 87s, 96s, 97s, J5s, Q5o, T6s, T8o.
  Roh-Equity-Band der puren Bluffs: **0,36–0,50** (S. 17) — NICHT der Boden der Verteilung.
- **65s-Ausreißer:** Exit bei **B = 225**, >3× länger als der nächstlängste Persister; Roh-Equity
  0,430 = Rang **128/169** (S. 9, S. 22). Der klarste Einzelhand-Fingerabdruck der zyklischen
  Dominanz.

### 2.3 Die zwei Gesetze: Pivot- vs Exit-Ordnung (S. 10, Tabelle S. 19)

| Ranking | Spearman vs **Pivot**-Ordnung | Spearman vs **Exit**-Ordnung |
|---|---|---|
| Roh-Equity | **0,98** | 0,73 |
| Chen-Formel | 0,72 | **0,88** |
| Sklansky-Gruppe (invertiert) | 0,68 | 0,85 |

- **Gesetz 1:** Die Value→Bluff-Pivot-Ordnung folgt der Roh-Equity fast perfekt (0,98) — der
  klassische VNM-Teil ist robust (S. 10, S. 16, S. 21).
- **Gesetz 2:** Die Exit-Ordnung folgt "Playability": die Praktiker-Rankings (Chen 0,88,
  Sklansky 0,85), die NICHT für dieses Spiel gebaut wurden, schlagen die Roh-Equity (0,73),
  weil Suitedness/Connectedness **Zyklus-Dichte** kodieren (S. 10, S. 19–21). Chen-Beispiele:
  AKs = 12, 22 = 5, 72o = −1 (S. 19).
- **Bluff-Persistenz invertiert:** Innerhalb der 27 puren Bluffs korreliert Exit-B mit Roh-Equity
  **−0,42** — je schwächer der Bluff, desto länger bleibt er (S. 11). Exits: 65s = 225,
  54s = 59, 43s = 54, 53s = 41; kürzeste: J5s = 0,98, Q5o = 1,15, T6s = 1,19, T8o = 1,32 (S. 11).

### 2.4 Vier-Matrix-Zerlegung (S. 11–14)

Kategorie-Zählung (Tabelle S. 12):

| Matrix | Value | Pure Bluff | Passiv |
|---|---|---|---|
| Real | 88 | 27 | 54 |
| Pythagorean | 93 | 5 (*) | 71 |
| Deterministic | 83 | 14 | 72 |
| Both | 83 | 11 | 75 |

(*) **Paper-Inkonsistenz:** S8 (S. 35) nennt für Pythagorean **7** pure Bluffs (= 5 Pyth-only
+ 87s, T6s, die auch real Bluffs sind); die Tabelle S. 12 sagt 5. Nicht auflösbar aus dem PDF.

- **Der klassische Kern: 106/169 Hände** sind in allen vier Matrizen gleich kategorisiert
  (S. 12): **70 klassische Value-Hände** (inkl. AA; Paare, alle Ax/Kx, stärkste Broadways) +
  **36 klassische Passiv-Hände** (Offsuit-Junk) + **0 klassische Bluffs**. **Kein einziges Blatt
  ist in allen vier Varianten ein Bluff** — Bluffen ist strukturell weit sensitiver auf die
  Matrix-Geometrie als Value/Passivität (S. 12).
- **Die 27 Real-Bluffs, zerlegt nach benötigten Features (S. 13):**
  - **7 brauchen Nicht-Transitivität, keine Probabilistik** (real+det, nicht in den transitiven):
    **43s, 53s, 54s, 54o, 63s, 64s, 65s** — die saubersten zyklischen Bluffs; identisch unter
    allen drei transitiven Konstruktionsvarianten (S8, S. 35).
  - **14 brauchen beides** (nur real): 65o, 73s, 74s, 75s, 76s, 76o, 84s, 85s, 86s, 96s, 97s,
    J5s, Q5o, T8o.
  - **4 komplexe Fälle:** 32s, 42s (real+Both); 52s, 62s (real+det+Both) — Boden der
    Equity-Verteilung, sensibel spezifisch auf die Pythagorean-Approximation.
  - **2 brauchen nur Probabilistik** (real+Pyth, nicht deterministisch): **87s, T6s**.
  - Bilanz: 25/27 brauchen Nicht-Transitivität in irgendeiner Form (21 absolut + 4), 2 brauchen
    Probabilistik (S. 13).
- **15 Phantom-Bluffs der vereinfachten Spiele** (Bluff dort, real passiv; S. 13–14):
  - 5 nur Pythagorean: **98o, J3s, J4s, Q3o, Q4o** — die "Bluffs des Skalar-Denkens"; in real
    ein Fehler, weil die Zyklen andere Kandidaten in die Rolle setzen (S. 13–14).
  - 5 nur Both: **43o, 72o, 73o, 82o, 83o** — absolut schwächster Offsuit-Junk; mittlere
    Zyklus-Zahl 7, eine Größenordnung unter den zyklischen Bluffs (S. 14).
  - 3 nur Deterministic + 2 in Det&Both — **Hände NICHT namentlich genannt** (S. 14).

### 2.5 Cepheus-Vergleich (S. 17–19)
- Cepheus (HU-Limit, Bowling et al. 2015), Dealer-Erstaktion: 149 raise / 19 fold / 1 mixed (S. 17).
- Bestes Matching bei **B ≈ 2,05**: Jaccard **0,67**; Alice bettet dort 100 Hände, **alle 100 in
  Cepheus' Raise-Range**; Alices Range ist bei JEDEM B eine **strikte Teilmenge** von Cepheus
  (S. 17). B ≈ 2,05 ≈ **4× der nominale Preflop-Bet-to-Pot** (nominal ≈ 0,5, effektiv ≈ 1,5)
  — der Multiplikator misst den Implied-Odds-Effekt der späteren Straßen (S. 17, S. 22).
- Die 49 Cepheus-nicht-Alice-Hände (S. 18; Paper nennt einmal "50-hand gap" — Inkonsistenz,
  vermutlich die 1 Mixed-Hand): suited Broadway-mit-Rag (J2s–J6s, Q2s–Q4s, T2s–T6s), offsuit
  Broadway-mit-Rag (J3o–J8o, Q3o–Q7o), niedrige Offsuit-Connectors (43o, 53o, 64o, 74o, 75o,
  76o), niedrige/mittlere suited (73s, 83s, 84s, 92s–95s, 85s–98s) — durchweg Hände, deren
  Multi-Street-Equity den Bet trägt, die Single-Street-Equity aber nicht.
- **Zweck-Ehrlichkeit des Autors:** VNM-Betting studiert man "to extract strategic insight
  applicable beyond THE, not to improve THE play" (S. 19).

### 2.6 Praktiker-Vergleich (S. 19–20)
- Sklansky-Gruppen 1–6 = 52 Hände; das Modell bettet ≥ 88 bei niedrigem B; **62 Hände**, die das
  Modell (in irgendeiner Matrix) spielt, stuft Sklansky als Gruppe 7–9 ("fold from most
  positions") ein — und **alle 62 raist auch Cepheus** (S. 20). HU spielt fundamental weiter als
  Full-Ring-Cutoffs; Sklanskys ORDNUNG ist gut, seine Cutoffs sind für ein anderes Spiel.

### 2.7 Solver + Robustheit (S7–S8, S. 33–35)
- Iterative Best Response mit Glättung: Init r=0/c=1; ε = 10⁻⁹; Glättung α = 0,01; Konvergenz
  Δ < 10⁻⁶; max 10.000 Iterationen; sonst Tail-Average der letzten 2.000 (Fictitious-Play-Mittel).
- Grid: **1.352 B-Werte auf [0,1; 315]** (Spacing 0,02 bis B=0,72; 0,001 in der Pivot-Zone
  [0,72; 1,50]; 0,005–0,5 bis 100; 5,0 bis 315) (S. 34). — **Inkonsistenz:** S9 (S. 35) spricht
  von "48 B values" für die veröffentlichten CSVs.
- Saubere Konvergenz: real 27 % (Ø 12.694 Iter.), Pyth 66 % (Ø 3.567), det/Both 3 % (Ø 9.738).
- **Exploitability-Check:** real/Pyth max < 0,001 Pot-Einheiten (real max 0,0009 bei B ≈ 145;
  Pyth 0,00002); det/Both bis 0,063 (viele Indifferenzpunkte). Kategorisierungen dagegen robust.
- **S8-Robustheit:** transitive Alternativen Linear eᵢ/(eᵢ+eⱼ) und Logit: klassischer Kern
  verschiebt sich ≤ 5 Hände; die **7 Zyklus-Bluffs sind identisch** unter allen Konstruktionen;
  needs-both verschiebt ≤ 1 Hand; Bluff-Zahl transitiv: Pyth 7 / Linear 3 / Logit 6.

---

## 3. Geschlossene Formeln (exakt, wie im Paper)

1. **Bobs Call-Schwelle (Pot-Odds; S. 7, S4 S. 30):** Bob callt mit Hand j gdw. seine
   Posterior-Gewinnwahrscheinlichkeit > **B/(1+2B)** (Pot = 1). Komplementärform über die
   Verlustwahrscheinlichkeit: Schwelle **(1+B)/(1+2B)**. Allgemein (Pot P vor dem Einsatz,
   Einsatz b absolut): benötigte Equity = **b/(P+2b)** — identisch mit unserer
   `equity_needed_to_call`. Herleitung: 0 = (1+B) − E[W]·(1+2B).
2. **Alices Bet-EV (S4, S. 29):** V_bet(i) = Σⱼ p(j|i)·[(1−cⱼ)·1 + cⱼ·(Wᵢⱼ·(1+2B) − B)].
3. **Alices Check-EV (S4, S. 29):** V_check(i) = Σⱼ p(j|i)·Wᵢⱼ.
4. **Bobs Call-EV (S4, S. 30):** V_call(j) = Σᵢ q(i|j,bet)·[(1+B) − Wᵢⱼ·(1+2B)]; Fold-EV = 0.
5. **Bobs Posterior (S4, S. 30, wie gedruckt):** q(i|j,bet) = p(i|j)·cᵢ·rᵢ / Σₖ p(k|j)·cₖ·rₖ —
   **Notations-Kollision im Paper:** cᵢ ist hier der Combo-Count aus S2, NICHT Bobs
   Call-Frequenz cⱼ; ob p(i|j) bereits combo-gewichtet ist (dann wäre cᵢ doppelt), lässt das
   PDF offen.
6. **Gleichgewicht (Komplementarität, S4, S. 30):** rᵢ > 0 ⟹ V_bet ≥ V_check; rᵢ < 1 ⟹
   V_bet ≤ V_check; cⱼ > 0 ⟹ V_call ≥ 0; cⱼ < 1 ⟹ V_call ≤ 0.
7. **RPS-Räuber-Beute-Gesetz (S. 6; Beweis S5, S. 30–31):** Margen α = 2a−1, β = 2b−1,
   γ = 2c−1 ⟹ Gleichgewichtsfrequenzen **r = β/(α+β+γ), p = α/(α+β+γ), s = γ/(α+β+γ)**.
   Beweis: M = W − ½J ist antisymmetrisch; symmetrisches Nash ⟺ Mx = 0; Kern des 3×3
   antisymmetrischen M = Kreuzprodukt-Vektor (β/2, α/2, γ/2). Gilt für jedes symmetrische
   3×3-Nullsummenspiel mit positiven Margen.
8. **Pythagorean-Approximation (S. 3):** P(i schlägt j) = eᵢ²/(eᵢ²+eⱼ²).
9. **Equity-Definition (S2, S. 27):** Wᵢⱼ = P(Sieg) + ½·P(Split) — als exakter Bruch
   darstellbar: (2·Siege + Splits)/(2·1.712.304).
10. **Drei-Hand-Indifferenz (S6, S. 32):** 0,4685 = B/(1+2B) ⟹ B ≈ 7,44 (JTs'
    Bluff-Emergenz-Schwelle).
11. **Klassisches VNM-[0,1]-Modell (S3, S. 28):** Schwellenstruktur 0 < t_bluff < t_value < 1,
    Bob-Schwelle t_call; qualitativ: t_value ↑, t_bluff ↓, t_call ↑ mit B; Bluff:Value-Verhältnis
    in Alices Range = Bobs Pot-Odds (Indifferenz-Eigenschaft). **Die expliziten geschlossenen
    Ausdrücke t_v(B), t_b(B), t_c(B) werden referenziert, aber im PDF NICHT abgedruckt.**

---

## 4. VERDRAHTUNGS-VORSCHLÄGE (Orakel-Checks, `pokerbot/autogym/oracle.py`)

Alle vier folgen dem Sicherheits-Kontrakt (AUTOGYM_PLAN): Knöpfe = Mess-Konfig (Improver-gesperrt),
Fraction-Referenz-Pflicht vor Verdrahtung (E1), F-Stufe erzeugt Vorschläge, nie Patches.

### V1 — `value_ordnung` (F) ★ der vielversprechendste: range-freier Ordnungs-Check
**Idee (Gesetz 1, S. 10):** Auf der VALUE-Seite folgt das Gleichgewicht der Equity-Ordnung fast
perfekt (Spearman 0,98). Also: Innerhalb eines Knoten-Buckets (Straße × B-Bucket × node_typ)
müssen Heros Value-Bets eine **obere Menge der Equity-Ordnung** bilden — bettet Hero Klasse X,
checkt aber eine strikt equity-höhere Klasse Y im selben Bucket, ist das eine Ordnungs-Verletzung
= Lead. **Entscheidend (S. 11, S. 13):** Die Brown-27-Bluffklassen sind von der Prüfung
AUSGENOMMEN — dort ist Ordnungs-Verletzung gleichgewichtskonform (Bluff-Exit korreliert −0,42).
- **Stufe:** F (aggregiert je Bucket, n ≥ 30); Einzel-Verletzungen als Lead-Liste im Proof.
- **Felder:** street, pot, amount/to_call (→ B-Bucket), action, hero_hole (→ 169-Klasse);
  range-frei — kein villain_hole nötig. Preflop-Variante zuerst (Klassen-Equity wohldefiniert);
  Postflop-Variante später über Rückschau-Equity (braucht villain_hole, wird L-artig verrauscht).
- **Fraction-Referenz:** Spearman auf ganzzahligen Rängen ist exakt rational (Fraction).
  Referenz-Ordnung = exakt enumerierte 169er-Equities ((2·Siege+Splits)/(2·1.712.304), S2).
  **ACHTUNG:** das Repo-Asset `knowledge_base/ranges/preflop_eqmatrix.json` ist MC mit sims=600
  — NICHT referenz-tauglich; vor Verdrahtung einmalig exakt enumerieren (CPU-billig, treys).
- **Knob-Schranken:** `ORDNUNG_RHO_MIN` ∈ [0,80; 0,98] (Start 0,90; Brown-Anker 0,98 ist die
  Ein-Straßen-Obergrenze, Mehrstraßen-Spiel darf drunter); `N_MIN_BUCKET` = 30 (fix);
  Ausnahme-Menge = Brown-27 (fixe Liste, KEIN Knob).

### V2 — `fold_ordnung` (F): der Verteidigungs-Spiegel
**Idee (Bobs Schwellenstruktur, S. 7/S4):** Bobs Gleichgewichts-Continue-Menge ist die Spitze der
Posterior-Winrate-Ordnung. Range-freier Spiegel von V1: Im selben Bucket callt Hero Klasse X,
foldet aber eine strikt equity-höhere Klasse Y = Ordnungs-Verletzung. Deckt genau die
Seesaw-Bruchklasse ab (v8: Check-Range transparent), ohne eine Frequenz vorzuschreiben —
reine Ordnung, keine Quote; komplementär zum (refutierten) mdf_guard.
- **Stufe:** F. **Felder:** wie V1 + call_closes_action (Welle-1-Feld, schon geplant).
- **Fraction-Referenz:** identisch V1 (dieselbe exakte Ordnung, derselbe Spearman-Bruch).
- **Knob-Schranken:** teilt `ORDNUNG_RHO_MIN` mit V1 ODER eigener `FOLD_RHO_MIN` ∈ [0,75; 0,95]
  (Verteidigung ist posterior-abhängig, also lockerer); N_MIN = 30 (fix).

### V3 — `bluff_struktur` (F): Bluffs aus der Zyklus-Region, nie aus dem Junk
**Idee (S. 13–14, S. 17):** Reale Bluffs kommen aus dem Band Equity 0,36–0,50 (suited
Connectors/Gapper, hohe Zyklus-Dichte); Boden-Junk-Bluffs (Brown-54-Passiv + die Both-only-Klasse
43o/72o/73o/82o/83o) existieren nur in den vereinfachten Spielen. Check: Anteil der
Hero-Bluffs (Bet/Raise mit Rückschau-Equity < Schwelle) aus Brown-Passiv-Klassen > Band = Befund.
- **Stufe:** F (Aggregat); braucht Rückschau → nur HU-Gym mit villain_hole, L-artige Unschärfe
  ehrlich im Proof vermerken.
- **Felder:** hero_hole (Klasse), villain_hole, board, street, action, amount.
- **Fraction-Referenz:** Mengen-Klassifikation ist exakt (Klassenlisten fix); Anteil =
  Fraction(k, n); Equity-Band-Grenzen 0,36/0,50 als Fraction(9,25)/Fraction(1,2) dokumentiert.
- **Knob-Schranken:** `BLUFF_EQ_MAX` (Rückschau-Equity, ab der ein Bet als Bluff zählt)
  ∈ [0,15; 0,35] (Start 0,25); `JUNK_BLUFF_BAND` (erlaubter Junk-Anteil) ∈ [0,10; 0,35]
  (Start 0,20 — Mehrstraßen-Poker bluff auch Junk mit Blockern; nie auf 0 klemmen).

### V4 — `bluff_persistenz_hoch_b` (L): die falschen Bluffs im großen Pot
**Idee (S. 11):** Die Persistenz-Ordnung invertiert — bei hohem B überleben nur die Zyklus-Kern-
Bluffs (65s-Typ); die Kurz-Persister (J5s Exit 0,98; Q5o 1,15; T6s 1,19; T8o 1,32) und alle
Phantom-Bluffs sind bei B ≥ 2 gleichgewichtsfremd. Check: Hero-Bluff (wie V3 erkannt) bei
Bet-to-Pot ≥ B_HOCH mit Klasse ∈ {J5s, Q5o, T6s, T8o} ∪ Brown-54 = einzelner Lead.
- **Stufe:** L (pro Entscheidung buchbar, severity = (req−eq)·Pot-Logik wie bestehende L-Checks).
- **Felder:** wie V3 + pot/amount für die B-Ratio.
- **Fraction-Referenz:** Exit-Schwellen sind empirische Grid-Werte (keine Formel) — als fixe
  ANKER-Liste dokumentieren, nicht als berechnete Referenz; der B-Ratio-Bruch amount/pot exakt.
- **Knob-Schranken:** `B_HOCH_MIN` ∈ [1,5; 5,0] (Start 2,0 — der Cepheus-Best-Match-Punkt);
  Klassenlisten fix (kein Knob).

**Transfer-Ehrlichkeit (bindend für alle vier):** Browns Modell ist EINE Straße, Preflop-Klassen,
HU. V1 preflop ist die sauberste Übertragung; V3/V4 übertragen Klassen-Prioren auf ein Spiel, in
dem Postflop-Bluffs board-/blocker-getrieben sind — deshalb F/L (Lead-Generatoren), nie P, und
jede Kalibrierung VOR Validierung journalfähig machen (FOLD_LEAD_MARGIN-Präzedenz).

---

## 5. BOT-DOKTRIN — was Brown für den Kandidaten-Entwurf bindend macht

1. **Bluff-Auswahl ist STRUKTURELL, nie Quote.** Null Hände sind Bluffs in allen vier Matrizen
   (S. 12): WELCHE schwache Hand blufft, ist reine Matrix-Geometrie (Zyklus-Position/Suitedness;
   im Mehrstraßen-Spiel: Blocker/Board/Sizing), nicht Schwäche und nicht eine Frequenz-Zielzahl.
   Das ist die unabhängige theoretische Bestätigung des vierten Mess-Datenpunkts (mdf_guard
   −3,26 NEUTRAL): **Frequenz ohne Selektion druckt nicht — Kandidaten müssen Selektion tragen.**
2. **Die Value-Seite ist klassisch und robust** (Pivot-Spearman 0,98; 70 Value-Hände in allen
   vier Matrizen): Ordnungs-Checks und Equity-Logik sind auf der Value-Seite legitime,
   fast-invariante Prüfgründe. Auf der Bluff-Seite ist Ordnungs-Treue ausdrücklich NICHT zu
   erwarten (−0,42) — ein Orakel, das Bluffs an der Equity-Ordnung misst, misst falsch.
3. **Rolle ist eine Funktion der Bet-Größe, nicht der Hand** (Pivot bei ~0,72+, Exits ab 5,
   87/88 Value-Händen wechseln die Rolle): Kandidaten-Design muss Hand-Rollen
   sizing-konditionieren; jede statische Hand→Rolle-Tabelle ist per Brown falsch.
4. **Frequenzen folgen der Räuber-Beute-Marge, nicht der eigenen Stärke** (r ∝ β; AKo 20 % vs
   33 59 %): stützt die Seesaw-Doktrin formal — die Mixing-Frequenzen des Gleichgewichts sind
   aus der eigenen Handstärke NICHT ablesbar; wer sein Mixing an Stärke koppelt (oder abflacht),
   verlässt das Gleichgewicht messbar. Kein neuer Knopf, aber der Beweisgrund, warum
   Purify-artiges Abflachen live brach (−58).
5. **Playability = Zyklus-Dichte** (Chen 0,88/Sklansky 0,85 > Equity 0,73 auf der Exit-Ordnung):
   Suitedness/Connectedness-Features in Advisor-MLPs sind keine Heuristik-Folklore, sondern
   Proxies einer messbaren Gleichgewichts-Größe. Suppenfleisch-konform: als Features, nie Dogma.
6. **HU spielt weit** (62 Sklansky-7–9-Hände, die Modell UND Cepheus spielen, S. 20): jede
   Tightness-Intuition aus Full-Ring-Quellen ist für HU-Preflop unzuständig.
7. **Transfer-Grenze (Brown selbst, S. 19):** Einstraßen-VNM verbessert THE-Spiel nicht direkt;
   Cepheus-Vergleich zeigt die VNM-Range als strikte Teilmenge (Multi-Street-Equity fehlt).
   Browns Listen gehören in CHECKS und PRIOREN (Abschnitt 4), nie als direkte Aktionsregeln in
   `bot.py`.

---

## 6. NICHT-GEFUNDEN / Inkonsistenzen (ehrlich)

- **Nicht abgedruckt:** die geschlossenen Ausdrücke t_v(B), t_b(B), t_c(B) des klassischen
  [0,1]-Modells (nur referenziert, S. 28); die Pivot-B-Werte der 87 Hände; die vollständige
  88er-Value-Liste und 54er-Passiv-Liste als explizite Aufzählung (nur qualitativ beschrieben +
  Beispiele 32o, 42o, J2o, T2o, 92o); die Namen der 3 Det-only- und 2 Det&Both-Bluffs (S. 14);
  eine formale Definition von "cycle count / cycle density" (nur der Wert 7 für die
  Both-only-Bluffs, S. 14); die Supplement-CSVs/Code (holdem_real.csv, gto_grid_full*.csv,
  solve_one_B_v4.py — referenziert, nicht im PDF).
- **Paper-Inkonsistenzen:** Pythagorean-Bluff-Zahl 5 (Tabelle S. 12) vs 7 (S8, S. 35);
  "49 hands" (S. 17) vs "50-hand gap" (S. 18); Grid "1.352 B-Werte" (S7, S. 34) vs "48 B values"
  (S9, S. 35); die Cassidy-2015-Referenz trägt "[volume and pages to confirm]" — das Paper ist
  ein Arbeitspapier-Draft (Version 2026-05-03).
- **Nicht im Paper:** 6-max/Multiway-Aussagen; Postflop-Bluff-Selektion (Blocker); Raises;
  jede AIVAT/bb-Messung. Alle Zahlen hier sind Einstraßen-VNM-Gleichgewichte.
