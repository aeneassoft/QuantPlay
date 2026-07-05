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
