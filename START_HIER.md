# PokerB — Was du bekommen hast & wie du loslegst

> ⚠️ **Historisches Onboarding (erste Version).** Aktueller Stand: [README.md](README.md) + [docs/STATE.md](docs/STATE.md).
> Der Bot ist seither weit fortgeschritten — Exploit-MVP, 6-max, GTO-Wizard-Benchmark, und jetzt ein **eigenes
> neuronales Self-Play-Netz** (Deep CFR). Die Zahlen unten (−170 vs Slumbot etc.) sind ÜBERHOLT. Unten = wie es
> ursprünglich ausgeliefert wurde, als Referenz.

## 🎮 Sofort spielen
**Doppelklick auf `PokerB spielen.bat`** (liegt auf dem Desktop). Der Server startet und der
Browser öffnet sich automatisch auf http://127.0.0.1:8000 — dann „Neues Spiel" klicken.
Rechts ist das **Coach-Panel**: „Bot-Zug erklären", „Meinen Zug bewerten", oder frei fragen.

## Was drinsteckt
**Deine 3 Bücher — automatisch ausgewertet:**
- **813 Strategie-Konzepte** (Claude Opus 4.8, strukturiert mit umsetzbaren Regeln)
- **348 Range-Captions** + **66 Heads-Up-GTO-Grids** aus den 13×13-Charts (Claude Vision)
- **13 Mathe-Formeln** (OpenAI gpt-5.1), davon **12 per Code-Ausführung verifiziert**

**Der Bot:**
- **Engine**: Karten, Hand-Evaluator, Monte-Carlo-Equity, volle HU-NLHE-Logik (300-Hände-Stresstest bestanden)
- **Decision-Engine**: Preflop-Ranges + Postflop (Gegner-Range → Equity → Pot-Odds/MDF/EV) + **Exploit-Layer** (lernt deine Tendenzen)
- **CFR-Solver** (`cfr_preflop.py`) — **Pluribus' Kern-Algorithmus (MCCFR)**: löst das push/fold-Spiel zu **echtem Nash-Gleichgewicht** (verifiziert gegen bekannte Charts) und steuert das Short-Stack-Spiel
- **Coach** (Claude): erklärt/bewertet/coacht auf Deutsch, **mit Zitaten aus deinen Büchern**

## Wie gut ist er? (ehrlich)
- **Preflop**: GTO-fundiert — push/fold ist **echtes CFR-Nash**; tiefe Stacks equity-gegroundet.
- **Postflop**: stark **heuristisch** (Equity + Pot-Odds + MDF + Exploit) — *kein* vollständiger Solver. Spielt prinzipientreu, ist aber kein Superhuman-Bot postflop.
- **Gegen schwache Gegner** (lokaler Benchmark, 300 Hände): Calling Station **+469 bb/100**, Maniac **+524 bb/100**, Nit **+58 bb/100** — der Exploit-Layer schlägt ausbeutbare Spieler klar.
- **Slumbot-Benchmark** (starker, nahe-GTO HU-Bot, 200bb, 400 Hände): **−170 bb/100 (±81)** — wir verlieren klar gegen einen Top-Bot. Erwartbar: 200bb tief + rein heuristisches Postflop ist der schwerste Test. Genau hier setzt das künftige Postflop-CFR an. (Hohe Varianz; wahre Rate grob −150…−200.)
- **Coach**: exzellent zum Lernen — hier spricht dein Buchwissen am direktesten.

## Deine Fragen — kurz beantwortet
- **Pluribus**: recherchiert & angewandt. Wir nutzen seinen Kern (MCCFR) für das lösbare/verifizierbare Stück (push/fold). Details: `docs/pluribus_and_benchmarking.md`.
- **Profi-Hand-DBs**: nützlich für Exploit-*Populations*-Prior, nicht für GTO. Unser Live-Gegnermodell adaptiert ohnehin. Offene Datensätze (ACPC, Pluribus-Hände) als künftiger Zusatz.
- **Benchmark gegen etablierten Bot**: ✅ via **Slumbot-API** umgesetzt (`pokerbot/benchmark/slumbot.py`).
- **RunPod ($50)**: **bewusst nicht verbraucht** — alles jetzt Baubare läuft lokal. RunPod lohnt für ein *tagelanges* Postflop-CFR-Blueprint-Training (der nächste große Schritt).
- **Rolle von Nicht-LLM-AI**: CFR/Solver = echtes GTO; Equity/Combinatorics/ICM = Mathe-Kern; LLMs = Bücher lesen + Coaching. Genau so kombiniert.

## Nächste Schritte (optional, wenn du weiter willst)
1. **Postflop-CFR-Blueprint** (abstrahiert, offline trainiert — hier kommt RunPod ins Spiel) + Echtzeit-Subgame-Solving → echtes GTO auch postflop.
2. **6-max** (Engine/Strategie sind darauf vorbereitet).
3. **Hand-DB-Exploit-Prior** aus offenen Datensätzen.

## Selbst nachprüfen
```powershell
python -m tests.test_game                 # Engine: 300 Hände, alle Invarianten
python -m tests.test_bot                  # Bot: Legalität + Spot-Checks
python -m pokerbot.strategy.cfr_preflop --quick   # CFR push/fold sanity
python -m pokerbot.benchmark.slumbot --hands 500  # gegen Slumbot benchmarken
```
