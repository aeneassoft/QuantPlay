# Research-Sweep 2026-07-05 — Perplexity-Paper-Suche (verifiziert) + OpenAI-Mathe-Konsult

**Auftrag (User):** Konkrete Papers zu Strukturanpassung / Code-Struktur / Mathematik über die Perplexity-API
suchen, **jedes Paper auf Existenz prüfen** (Halluzinations-Gate), OpenAI zu konkreten mathematischen Fragen
unserer Formeln konsultieren, alles bündeln. Rohdaten: `data/research_sweep/` (pplx_raw.json,
candidates.json, verified.json, openai_math.json).

**Methodik-Befund vorweg (wichtig):** Perplexity lieferte überwiegend REAL EXISTIERENDE Papers, aber mit
**systematisch vertauschten Metadaten** — falsche Autoren bei richtigen Titeln, arXiv-IDs dem falschen Paper
zugeordnet, DOIs verwechselt (z. B. DeepStacks DOI am Libratus-Eintrag, unser Parallel-CFR als „2405"
statt 2605, „Safe and Nested Subgame Solving" mit vier falschen Autoren). **Kein Paper aus diesem Sweep darf
ohne den Verifikations-Layer zitiert/geladen werden.** Die Tabelle unten enthält NUR verifizierte Einträge
mit KORRIGIERTEN Metadaten.

---

## Teil 1 — OpenAI-Mathe-Konsult: 4 Fragen zu UNSEREN Formeln (voll beantwortet)

### 1.1 eCall-Sizer + v3.2-Thin-Value-Schwelle ✅/⚠️
- **VERIFIZIERT:** Unser Sizer-Score `score(s) = F + (1−F)·(e_call·(1+2s) − s)` ist **exakt EV(bet) in
  Pot-Einheiten** (nicht nur affin) → der argmax des eCall-Sizers ist mathematisch sauber.
- **⚠️ v3.2-Schwelle ist ein Spezialfall:** „bette thin iff e_call(s_min) ≥ 0.5" ist NICHT die exakte
  Bedingung. Exakt: **e_call > [ s + (e_showdown − F)/(1−F) ] / (1+2s)** — je nach F und e_showdown liegt
  die wahre Schwelle über ODER unter 0.5. Alle vier Größen (F, e_call, s, e_showdown=unsere eq) berechnen
  wir bereits → **v3.2b-Kandidat: die exakte Schwelle statt der 0.5-Heuristik** (ein 3-Zeilen-Patch in der
  bot.py-Naht; erst nach dem v3.2-Verdikt, Protokoll).
- Qualitativ: Kann Villain nach unserem Check selbst betten (wir realisieren mehr als e_showdown), steigt
  EV(check) → die Thin-Value-Schwelle wird STRENGER. Unsere 0.5 ist also eher zu locker als zu streng.

### 1.2 v3.3-Raise-Reweight ✅ + konkrete Verbesserung
- **VERIFIZIERT:** λ=1 reproduziert die Ziel-Klassenmarginale exakt (nach Normalisierung), lässt
  Intra-Klassen-Verhältnisse unverändert, und ist die **exakte I-Projektion (min KL)** des Priors auf die
  Klassen-Constraint-Menge. λ<1 = unterrelaxierter Schritt auf der Exponentialfamilien-Geodäte. Unser
  Design ist damit prinzipiell sauber.
- **Konkrete Verbesserung (Shrinkage bei kleinem n):** Dirichlet(1)-Posterior-Mittel statt roher Frequenzen:
  `t̃_k = (1 + n·f_k) / (5 + n)`. Bei der **Jam-Mix (n=29)**: Gewicht auf Empirie ≈ 0.85 (spürbar);
  bei Street-Mixes (n=96–263): 0.95–0.98 (vernachlässigbar). → **v3.3-Konstanten-Update: die Jam-Mix
  Laplace-shrinken** (two-pair+ 0.414→~0.38, air 0.069→~0.10). Flag ist noch ungeshippt → Update VOR dem
  v3.3-Gate erlaubt (kein Post-Gate-Retuning).
- **Zero-Sicherheit bestätigt:** Nur positive Faktoren → kein Live-Combo wird genullt → die o3-Schranke hält.

### 1.3 Covered-Stack-Pot-Odds (AUDIT_FIX-Mitglied) ✅
- **VERIFIZIERT KORREKT** inkl. Street-Commitment-Fall: unsere Formel reduziert auf das First-Principles-
  Ergebnis `e* = S/(P₀+2S)` (bzw. mit Commitment c: Nenner P₀+2c+2S — algebraisch identisch zu unserer
  Implementierung über den Engine-Pot). Beispiel quantifiziert: alte Formel verlangte **90.9 %** Equity, wahr
  sind **40 %** → Over-Fold-Band von ~51 Prozentpunkten im HU-App-Fall (vs GTOW unerreichbar, Stacks gleich).

### 1.4 MDF-Schwellen-Floor (AUDIT_FIX-Mitglied) ✅ mit Empfehlung
- **VERIFIZIERT:** req = s/(1+2s) ist korrekt als Equity-Schwelle (nicht MDF — Namensnuance);
  EV-Verlust einer Fehl-Verteidigung = (req−e)·(1+2s); unser req/2-Floor begrenzt ihn auf (req/2)·(1+2s) ✓.
- **Einschränkung:** Ein harter Floor ist von einem ADAPTIVEN Über-Bluffer ausbeutbar (max s pro Call).
  Gegen GTOW irrelevant (statisch, Dossier-verifiziert). OpenAI-Empfehlung für die Zukunft: Kappe der
  Summen-Discounts bei ~0.4·req (≙ Floor 0.6·req) statt req/2 — notiert, kein Churn vor dem v3.4-Gate.

---

## Teil 2 — Verifizierte Papers (27/36 bestätigt; Metadaten KORRIGIERT, wo Perplexity sie vertauschte)

### A-Priorität: der v4-Stack (Li & Huang — direkt aus dem Parallel-CFR-Literaturverzeichnis extrahiert)
| Paper | Beleg | Relevanz |
|---|---|---|
| **EVPA: Efficient Online Pruning and Abstraction for Imperfect Information EFGs** (Li & Huang, ICLR 2025) | OpenReview exakter Titel-Match ✓ | Online-Pruning: bis zu 2 Größenordnungen Solve-Beschleunigung; v4-Baustein #2 |
| **TurboReBeL: 250× Accelerated Belief Learning for Large IIEFGs** (Li & Huang, 2026b) | zitiert in arXiv 2605.19928 mit OpenReview-Link (yMo7Z670f6); Direkt-Fetch fehlgeschlagen → **UNBESTÄTIGT, im Browser prüfen** | DAS Leaf-Netz-Trainings-Paper — die v4-Kern-Abhängigkeit |
| **WEVA: Effective, Efficient, and General Information Abstraction for IIEFGs** (Li & Huang, 2026a, arXiv 2605.x) | zitiert in 2605.19928 (ID im PDF trunkiert) | Lossy-Abstraktion für größere Handräume; v4-Baustein #3 |

### B: Struktur-Anpassung / Re-Solving (existenz-verifiziert)
| Paper | Korrekte Zitation | Perplexity-Fehler | Nutzen für uns |
|---|---|---|---|
| Safe and Nested Subgame Solving for IIG | **Brown & Sandholm**, NIPS 2017, arXiv:1705.02955 | falsche Autoren + falsche ID | die Safe-Re-Solving-Mathematik, die unserem Resolver fehlt |
| Monte Carlo Continual Resolving (MCCR) | Šustr et al., arXiv:1812.07351 | — | Continual Resolving OHNE Supercomputer — Blueprint für den Resolver-Umbau |
| Automated Action Abstraction of IIEFGs | **Hawkin/Holte/Szafron**, AAAI 2011, DOI 10.1609/aaai.v25i1.7880 | falsche Autoren | Bet-Size-LERNEN statt Hand-Grid — Alternative zum Census-Grid |
| Evaluating State-Space Abstractions in EFGs | Johanson et al., 2013 | — | Karten-Bucketing (EMD) für die v4-Abstraktion |
| Libratus | IJCAI-Demo 10.24963/ijcai.2017/772 + Science 2018 **10.1126/science.aao1733** | Science-DOI mit DeepStack verwechselt | Nested-Resolving-Architektur |
| Pluribus | Science 2019, 10.1126/science.aay2400 | — | Depth-limited Search unter Budget |
| Deep CFR | Brown et al., arXiv:1811.00164 | Duplikat-Eintrag mit falschen Autoren+ID | Abstraktionsersatz durch Netze |
| Signal Observation Models & Historical Information Integration in Poker AI | arXiv:2403.11486 (2024) | — | Abstraktion↔Solving↔Translation-Paradigma |

### C: Range/Belief-Tracking (verifiziert)
| Paper | Korrekte Zitation | Nutzen |
|---|---|---|
| ReBeL | **Brown/Bakhtin/Lerer/Gong**, NeurIPS 2020, arXiv:2007.13544 (P: falsche Autoren) | Public-Belief-State-Wert-Netze = v4-Leaf-Netz-Formalismus |
| Exploitability Descent | Lockhart et al., IJCAI 2019, arXiv:1903.05614 (P: falsche ID) | Exploitability als direktes Trainingsziel |
| Bayes' Bluff | Southey et al., UAI 2005, arXiv:1207.1411 | der Urahn unseres Range-Trackers |
| Game Theory-Based Opponent Modeling in Large IIG | Ganzfried & Sandholm, AAMAS 2011 | Range-Schätzung + Deviation-Response |
| CFR+ / Zinkevich-CFR / Continual-Resolving-Linie | Tammelin arXiv:1407.5042 · NIPS 2007 · Burch 2015ff | Fundament (in unserer Bibliothek abgedeckt) |

### D: CFR-Mathematik (verifiziert)
| Paper | Korrekte Zitation | Nutzen |
|---|---|---|
| Deep (Predictive) Discounted CFR | Xu et al., AAAI 2026, arXiv:2511.08174 — **PDF besitzen wir** | neuronale DCFR+/PDCFR+-Approximation, Varianzreduktion fürs Leaf-Training |
| Dynamic Discounted CFR (DDCFR) | ICLR 2024 (+ AAAI-Version 10.1609/aaai.v40i20.38780) | adaptive Discount-Schedules mit Garantien |
| Stable-Predictive Optimistic CFR | Farina/Kroer/Sandholm, ICML 2019, **arXiv:1902.04982** (P: falsche ID) | bessere Konvergenzrate — Kandidat für den v4-Solver-Kern |
| Discounted CFR (DCFR) | **Brown & Sandholm**, AAAI 2019, **arXiv:1809.04040** (P: falsche Autoren+ID) | die DCFR-Schranken (TexasSolver nutzt DCFR) |
| MCCFVFP | arXiv:2309.03084, NeurIPS 2024 | CFV-basiertes Fictitious Play, 20-50 % schnellere Konvergenz |

### E: Poker-Mathematik / Evaluation / Code (verifiziert)
| Paper | Korrekte Zitation | Nutzen |
|---|---|---|
| AIVAT | Burch et al., AAAI 2018, **arXiv:1612.06915** (P: falsche ID+Autoren) | unser Mess-Standard — Estimator-Annahmen |
| DeepStack | Science 2017, arXiv:1701.01724 | CFV-Netz-Training (v4-Referenz) |
| Solving Large EFGs with Strategy Constraints | **Davis/Waugh/Bowling**, AAAI 2019, 10.1609/aaai.v33i01.33011861 (P: falsche Autoren/Jahr) | Strategie-Constraints — Kandidat fürs „bounded exploit overlay" (Nordstern) |
| Architectural Tactics for ML-Enabled Systems (SLR) | SSRN/JSS 2024, 10.2139/ssrn.4909520 | einziger Code-Struktur-Treffer: Komponentisierung/Versionierung — deckt sich mit unserem Registry/Flag/Gate-Design |

### Aussortiert (nicht existent wie behauptet / Halluzinations-Verdacht)
- „Public Belief MDPs for Planning…" (Titel existiert nicht; das Konzept lebt in ReBeL/MCCR)
- „Opponent Range Estimation in No-Limit Texas Hold'em" (Ganzfried/Sandholm haben ANDERE Titel)
- „Variance Reduction in Experiments in IIG" mit arXiv:1710.06169 (ID gehört woanders hin)
- „Codified Context" arXiv:2602.20478 (nicht auffindbar)
- „Strongly Considered Action Abstractions…" arXiv:1302.4210 (ID-Titel-Mismatch)
- „Computing Correlated Equilibria…" arXiv:2207.07520 + „Robust Strategy Computation…" arXiv:2103.01196 (ID-Mismatches)
- DREAM: existiert (echte ID sehr wahrscheinlich arXiv:2006.10410), Perplexitys 1902.04074 ist falsch (Nachprüfung heute rate-limitiert)
- „Regret-Based Pruning in EFGs" (Brown & Sandholm NIPS 2015 — sehr wahrscheinlich real; Prüfung heute inconclusive)

**Halluzinations-Bilanz: 9/36 Kandidaten ausgefiltert; zusätzlich trugen ~10 der 27 VERIFIZIERTEN falsche
Autoren, IDs oder DOIs — die Verifikationspflicht war voll berechtigt. Kein Eintrag oben ist ungeprüft.**

---

## Teil 3 — Konsequenzen / Queue

1. **v3.3-Konstanten:** Jam-Mix Laplace-geshrinkt (vor dem Gate — Flag ungeshippt). 
2. **v3.2b (nach v3.2-Verdikt):** exakte Thin-Value-Schwelle statt e_call≥0.5.
3. **v3.4:** req/2-Floor bleibt (0.6·req als Alternative notiert, GTOW-irrelevant).
4. Paper-Queue: siehe Teil 2 nach Verifikation.
5. **Paper-Beschaffung (User/Browser):** EVPA (OpenReview ICLR 2025) + TurboReBeL (openreview.net/forum?id=yMo7Z670f6, unbestätigt) + WEVA + MCCR (arXiv:1812.07351) + Safe-and-Nested (arXiv:1705.02955) + Stable-Predictive (arXiv:1902.04982) nach books/papers/CFR/ laden.
6. **v4-Machbarkeitskarte** (auf User-Befehl): TurboReBeL zuerst lesen — wenn „250× Belief-Learning" hält, schrumpft die v4-Leaf-Netz-Hürde dramatisch.

## EVPA + Embedding-CFR Implementierungs-Verdikte (2026-07-05, beide Paper agenten-gelesen)
- **EVPA (ICLR 2025, verifiziert):** Kern = Ensemble-CFV-Pruning + Online-Bucketing VOR dem Solve (69-79%
  Baumreduktion, spielbar bei 0.02s). OHNE die Netze ist nur GEOMETRIE-Pruning sound. GEBAUT: resolver.
  _prune_degenerate_arms (POKERB_ARM_PRUNE, default OFF) — Mechanik korrekt, aber die gepaarte Battery MASS:
  TexasSolver kollabiert Über-All-in-Arme INTERN bereits (eps identisch bis 1e-8, Zeit flach) -> **No-op vs
  TexasSolver, behalten als v4-Baustein** (eigener CFR-Kern kontrolliert den Baum selbst). NICHT gebaut
  (bewusst): Census-Frequenz-Pruning (Gegner-Policy != Dominanz — die GTO-Score-Lektion), Range-Hard-Zeroing
  (o3-Schranke). v4-NOTIZ: EVPA-Datenkorpus (TexasSolver-gelabelte (Spot,Hand,Line)->EV-Paare) kann JETZT
  gesammelt werden — der Solve-Cache ist der Anfang; das M=10-Ensemble ist billig (H100, ~Tage).
- **Embedding CFR (arXiv:2511.12083, 17pp — nicht 182):** Soft-Karten-Abstraktion für Blueprint-Solves;
  NICHT unser Problem (verlustfreie Subgames). EIN Baustein: HandEbdNet-Rezept (Per-Street-W/D/L-Profil-CNN)
  als v4-Leaf-Netz-Featurization ('Schritt 0', optional, 3080Ti). Baureihenfolge unverändert.
- **Flop-No-Go-Retest** mit EVPA-minimalem Menü (1 Size/Street): läuft (bwfga5qs2) — Ergebnis folgt.

## TurboReBeL VERIFIZIERT (2026-07-05 Nacht, Agent mit direktem OpenReview-Browserzugriff)
- **Referenz (verifiziert):** Boning Li, Longbo Huang, *"TurboReBeL: 250x Accelerated Belief Learning for
  large Imperfect-Information Extensive-Form Games"*, ICLR-2026-Submission #5768, openreview.net/forum?id=yMo7Z670f6
  — **REJECTED** (26.01.2026; Ratings 2/2/4/6, Soundness 1–2). Nicht auf arXiv, nicht in DBLP. Dieselben
  Autoren wie unser v4-Paper (books/papers/CFR/2605.19928v1.pdf). Formal nur als "OpenReview preprint,
  rejected" zitierbar; **die 250×/450×-Headline NIE zitieren** (Meta-Review: unbelegte Schätzung; Thm 1–2
  fehlerhaft; SSMIG vs. Augmentation nie separat abliert).
- **Trotzdem verwertbar (als A/B-gegatete Engineering-Experimente, eigene Messzahlen):**
  1. **SSMIG:** pro Depth-Limited-Solve T Value-Targets ernten (eines je CFR-Iteration, gemittelte
     Strategien) statt 1 → der größte Datenkosten-Hebel fürs v4-Leaf-Netz. (Ehrlich: TexasSolver exponiert
     keine Per-Iteration-Dumps — greift erst im eigenen v4-CFR-Kern.)
  2. **Iso-Augmentation:** Suit-Iso (unser `isomorph.py`!) + Chip/Stack-Skalierung als Trainingsdaten-
     Multiplikator; korreliert → nie als unabhängige Samples zählen, Augmentation at-batch-time.
  3. **Machbarkeits-Anker:** 10M (TurboReBeL) bzw. 60M Samples (Li et al. 2024, im Rebuttal) reichen
     forumsbelegt für Slumbot-schlagende HUNL-Value-Netze — NICHT ReBeLs 4.5B. v4-Budget: zweistellige
     Millionen solve-derived Samples = Desktop/1-Pod-Regime.
  4. **Gate-Rezept:** Turn-Endgame mit EXAKTER Exploitability als billiges erstes Gate (= unsere
     Grounded-Gate-Doktrin); ihre Schwäche (kein LBR, kleine Abstraktion) nicht kopieren.

## AIVAT verstanden (2026-07-06 ~01:00 — Paper arXiv:1612.06915 via ar5iv gelesen; Burch/Schmid/Moravčík/Bowling AAAI'18)
- **Konstruktion:** Kontroll-Variaten an CHANCE-Knoten UND Entscheidungs-Knoten der analysierten Spieler;
  Baseline = beliebige Value-Funktion ṽ; imaginary observations marginalisieren unbekannte Gegner-Karten.
- **★ DAS NO-CHEESE-THEOREM (Thm 1):** E[Σ Korrekturen] = 0 UNABHÄNGIG von der Baseline-Qualität — Zitat:
  *"a player cannot appear to do better by changing their play to take advantage of the estimation method."*
  → **AIVATs Mittelwert ist nicht gambar.** Pre-registriert: jede künftige Idee "wir passen uns an die Metrik
  an und gewinnen bb" ist per Theorem ein Artefakt. Anpassung an AIVAT ≠ Metrik-Gaming (unmöglich).
- **Was Anpassung LEGITIM heißt (die 3 echten Hebel):** (1) Pures EV optimieren — Glück wird subtrahiert,
  Gamble-Linien kriegen keinen Credit. (2) **Varianz-Seite gehört UNS:** Residual-SD hängt am Spielstil +
  daran, wie gut GTOWs Baseline unsere Linien abdeckt → Tail-Kill + On-Tree-Sizings = engere SE = schnellere/
  billigere Gates (gemessen: per-Hand-SD 1000-Ära → 214 heute; ±2SE@2500 skaliert mit SD). Lower-variance
  style = cheaper truth. (3) Off-Tree-Linien = schlechterer Baseline-Fit = mehr RAUSCHEN (nie Bias) — ein
  Mess-Speed-Argument für Census-Snapping zusätzlich zum EV-Argument.
- **money_mine-KAVEAT (paper-bestätigt):** Das Paper stützt KEINE Unverzerrtheit für KONDITIONIERTE
  Teilmengen (z.B. nur Fold-Hände) — Bucket-Summen mischen echtes EV mit Baseline-Residuen, die mit der
  Konditionierung korrelieren. money_mine bleibt RANKING-Heuristik; Magnituden nicht wörtlich nehmen
  (Caveat in Skript + JSON nachgezogen).
- **Instrumenten-Kandidat (post-Ladder):** EIGENES lokales AIVAT für nicht-GTOW-Messungen (Canary/Slumbot/
  Duplicate) — Unverzerrtheit gilt für JEDE Baseline → unsere Advisor/Solver-Values genügen; ~10× Varianz
  auf unseren $0-Gates wäre ein Instrumenten-Durchbruch (NOTES' DIVAT-Notiz, jetzt paper-fundiert).

## TurboReBeL THEORIE-Tiefgang (2026-07-06 ~00:20 — Theoreme + alle 4 Reviews VERBATIM gesichert)
Voller Report: `data/research_sweep/turborebel_theory.md` (+ Rebuttal-PDF + Reviews-Rohdaten ebenda;
OpenReview ist inzwischen challenge-gesperrt — Quellen: 1× Live-API-Zugriff + Wayback-PDF + 2 unabhängige,
byte-identische HF-Mirrors). Kernbefund (eigene Analyse, deckt sich mit Reviewer uRCN/hYMG): **Theorem 1 ist
wahrscheinlich FALSCH wie formuliert, nicht nur unterbewiesen** — Beweisschritt (C) behauptet uniforme
per-Infoset-CFV-Konvergenz der CFR-Average-Strategie zu einem BELIEBIGEN Nash σ* mit O(1/√T); das garantiert
CFR nicht (nicht-eindeutige NE ⇒ Ω(1)-Off-Path-CFV-Differenz — exakt der Grund, warum Safe-Resolving-Gadgets
existieren; das nachgereichte Gift-Gadget zitiert zirkulär Thm 1). Thm 2 = konditional okay, aber leer, weil
seine Prämisse Thm 1 IST. **$0-Falsifikationstests designed (Leduc):** T1 = zwei distinkte NEs erzeugen,
max_I |v^σ̄T(I) − v^σ*(I)| über T plotten (Vorhersage: σ*-abhängiges Plateau statt O(1/√T)-Zerfall an
Off-Path-Infosets); T2 = SSMIG-Pipeline-Exploitability vs die behauptete Schranke. Konsequenz für v4
UNVERÄNDERT: SSMIG + Iso-Augmentation als gegatete Engineering-Hebel, Theorie nie zitieren.

## NAL / "Reducing Variance 2025" Verdikt (2026-07-05 Nacht, inline VOLL gelesen — existenz-verifiziert)
- **Paper:** Meng, Chen, Li, Yang, Zhang, Gao — *Reducing Variance of Stochastic Optimization for Approximating
  Nash Equilibria in Normal-Form Games*, **ICML 2025 (PMLR 267)**. PDF: `books/papers/Variance/`.
- **Kern:** Nash Advantage Loss (NAL) = Surrogat-Loss mit stop-gradient-Konstruktion, dessen Gradient
  (F − ⟨F,x̂⟩·1 = der "Advantage") mit EINER Zufallsvariable unverzerrt schätzbar ist → Varianz O(σ) statt
  O(σ²) der einzigen bisherigen unbiased Loss (Gemp 2024, Innenprodukt zweier unabhängiger Schätzer);
  empirisch 2–6 Größenordnungen weniger Varianz. Entropie-Regularisierung (τ-Annealing) → inneres NE;
  Dualitätslücke ≤ C·‖∇NAL‖ (Thm 4.2/4.3).
- **VERDIKT: PARKEN — keine Anwendung bei uns.** (1) **Nur Normalform**: die Theorie (Lemma 4.1, Gradienten-
  Gleichheit ⇔ NE) braucht Linearität der Utility über dem Strategie-SIMPLEX — gilt NICHT für Behavioral-
  Strategien in Extensive-Form (multilinear); NFG-Konversion von Poker ist exponentiell. (2) Selbst im
  winzigen Kuhn-Poker (NFG) konvergiert NAL bei kleinem S nicht exakt (Paper §5 selbst). (3) Trotz Ordner-
  namens "Variance": das ist TRAININGS-Loss-Varianz beim NE-Berechnen, NICHT Mess-Varianz (AIVAT/paired
  bleibt unser Werkzeug). (4) Nicht mit dem v4-Pfad (CFR-Familie) komponierbar. Randnotiz fürs Archiv:
  n-Spieler-general-sum-NE via Adam wäre höchstens für kleine abstrahierte 6-max-NFGs interessant — kein
  aktueller Bedarf (CFR+ deckt Preflop, Multiplayer-Stance bleibt CCE via Regret).

## MCCFR-Linie geprüft (2026-07-06, User-Links, alle existenz-verifiziert)
- Lanctot/Waugh/Zinkevich/Bowling, "Monte Carlo Sampling for Regret Minimization in Extensive Games"
  (NeurIPS 2009) = das kanonische MCCFR (zwei Spiegel-Links). + MCCFVFP (Ju et al., NeurIPS 2024):
  MCCFR + Fictitious Play, ~20-50% schneller IN MC-Settings.
- **VERDIKT: kein Upgrade für uns, wäre ein DOWNGRADE fürs TexasSolver-Teil.** MCCFR gewinnt nur bei
  Bäumen zu groß fürs Full-Traversal; ein Postflop-Subgame ist klein, TexasSolvers full-width VEKTORISIERTES
  DCFR verarbeitet alle 1326 Combos gleichzeitig (Amortisierung) -> Sampling verliert genau das = langsamer.
  Gemessen im Code: Preflop = EXAKTES CFR+ (bewusst nicht gesampelt), Postflop = TexasSolver vektorisiert,
  MCCFR nur im geshelvten deep_cfr.py (plateaute ~1500 mbb). Sampling-CFR nur relevant, falls wir je (a) den
  Flop selbst lösen (aber Roadmap = Library + Leaf-Netz, nicht MCCFR) oder (b) einen v4-Label-Gen-Kern bauen
  (deep_cfr.py, getrennt von TexasSolver). Die CFR-Variante ist NICHT der Engpass; Range-Qualität + Flop-
  Abdeckung sind es (Präzisions-Doktrin: wir nutzen bereits die präzisere Full-Width-Variante).
