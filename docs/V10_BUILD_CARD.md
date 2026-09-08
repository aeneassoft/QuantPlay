# V10 BUILD-KARTE — „River-Fundament" (2026-09-07)

**Herkunft:** Fable-Entwurf → Kritik gpt-6-astra (docs/TOP5_KONSULT_GPT6_2026-09-07.md, Teil E) →
diese abgestimmte Fassung. User-Auftrag: v10 in EINEM Rutsch (Ultracode-Flotte) bauen, Gates, GTOW.
Astras Zeitangaben sind irrelevant; seine Richtung und Abnahmekriterien sind übernommen, wo unten
nicht ausdrücklich anders entschieden (Abschnitt „Abweichungen").

## Ziel
Kohärenteres River-Spiel durch (K1) korrigierte Hero-Beliefs und (K2) öffentlichen Solver-Einstieg mit
gespeichertem Plan; dazu (K3) ein Prüfstand, der beide Arme im selben Root-Spiel bewertet, (K4)
Produktionsintegrität, (K5) GTOW-Pilot. **Nicht in v10:** CFV-Netz, Turn-Solving, Entropie, fp16,
Resolver-Austausch (TexasSolver bleibt AN), stackoff/no_limp, Advisor-Umbau, Strategieänderungen
außerhalb des River-Solver-Pfads.

## Arme
- **A = v5-H:** eingefrorene v5-Strategie (r8_stack) auf dem reparierten Kanal (PRINCE, exploit OFF,
  TexasSolver ON). „-H" weil K4 den Kanal repariert; strategische Verteilung auf Golden-Set unverändert.
- **B = v10:** gleiche Kette darunter (r6_button + wert_bremse); der hand-abhängige river_gpu_guard ist
  ERSETZT durch K2 (öffentlicher River-Plan) mit K1-Hero-Range. Stack-Name `r10_stack`.

## K1 — Hero-Likelihood-Replay (`pokerbot/strategy/hero_range.py`)
Rekonstruktion von Heros River-Beginn-Range VORWÄRTS ab Preflop-Prior:
r_river(h) ∝ r_0(h) · M_board(h) · Π_t π_exec(a_t | s_t, h) über alle Hero-Aktionen vor dem River.
- **Basis-Likelihood-Backend (approximiert, GEKENNZEICHNET):** das Advisor-Modell des Trackers
  (P(bet)/P(check) je Combo, P(call) via Defense-Advisor), gebatcht — dieselben Modelle wie heute,
  neue Auswertungsschnittstelle ohne Sampling/Nebenwirkung.
- **Guard-Transformationen EXAKT** als Verschiebung von Aktionsmasse:
  - turn_wert (check→Bet b* bei Bedingung C(h)): π_exec(b*|h) = π_vor(b*|h) + 1_C(h)·π_vor(check|h);
    π_exec(check|h) = (1−1_C(h))·π_vor(check|h). C(h) mit der DAMALIGEN Villain-Range (Snapshot vor der
    Turn-Aktion, Card-Removal je hypothetischer Hero-Combo neu), Equity vektorisiert (gpu_equity).
  - sel_guard Flop (fold→call bei C(h)): π_exec(call|h) = π_vor(call|h) + 1_C(h)·π_vor(fold|h); Raise-Anteil
    bleibt.
  - button_disziplin (Open 2,5× für JEDE Combo): Prior an dieser Stelle UNVERÄNDERT (keine Selektion).
  - Größenvergleich über finale ganzzahlige Chipbeträge (Engine-Clamp), nicht über Labels.
- **Keine Hero-Hand-Injektion** im K1/K2-Pfad. Invarianz: gleiche öffentliche Historie, andere Hero-Hand
  → identische öffentliche Hero-Range (≤1e−6).
- **Abnahme:** Σ=1 (1e−6), Board-Combos exakt 0, Guard-Transformation vs explizite Enumeration ≤1e−6,
  Invarianztest; **Oracle-Stichprobe** (≥64 gehaltene Vorgeschichten + ≥128 Aktionszustände, jede
  Guard-Klasse ≥16×): Oracle = offline decide() je Combo über mehrere Seeds (empirische Verteilung);
  mittlere TV-Distanz der finalen Hero-Range ≤0,02, p95 ≤0,05, kein Fall >0,10. Verfehlt → K2 NICHT frei.
  Injektionsrate nur noch Legacy-Diagnostik.

## K2 — Öffentlicher River-Plan (`river_play_guard` → `pokerbot/autogym/river_plan.py`)
- **Gating öffentlich und straßenweit:** Entscheidung AM RIVER-BEGINN: pot_river (Pot beim River-Deal)
  ≥ **15 bb (1500 Chips)** → die ganze River-Straße wird nach dem Plan gespielt; sonst Basis+wert_bremse.
  Kein Hochsetzen nach Ergebnisansicht.
- **RiverPlan:** einmal je Hand am River-Beginn gelöst (Root = River-Beginn, K1-Hero-Range, Tracker-
  Villain-Range, Baum 0,35/0,75/1,5 Pot + Raise 2,7× + Jam, fp32, 150 Iter, GEMITTELTE Strategie);
  gespeichert (Root-/Baum-/Konfig-Hash); jede Hero-Entscheidung navigiert die gespielte Sequenz zum
  Knoten. Off-Tree-Villain-Aktion → definierter Fallback (Basis) + Log `offtree`; kein stilles Neulösen.
  Cache je Hand (ein Solve pro River, nicht pro Entscheidung).
- **Private Randomisierung:** u = keyed_hash(private_seed, hand_id, decision_addr); private_seed im Gym
  deterministisch aus Deck-Seed+Sitz (A/A exakt 0 bleibt), live aus os.urandom (geloggt, nie
  gegnerseitig ableitbar). Policy-Abfragen (K1/K3) verbrauchen keine Zufallszahlen. Sampling-Test 10k
  Seeds je Testverteilung ≤5 Binomial-SE; p∈{0,1} exakt.
- **Sizes** exakt aus dem Baum-Arm → Chips (dokumentierte Abbildung), Legalitätsgatter wie v8.
- **Trace je Entscheidung:** basis → texassolver_eingriff → guards → plan_entscheidung(Verteilung) →
  legalität → sample → final. Jede Änderung NACH der Plan-Entscheidung ist reine Legalitätsabbildung.
- **Deadline:** interne Deadline 7,5 s → Fallback Basis-Aktion; verspätetes GPU-Ergebnis wird verworfen.
- **Abnahme:** Aktivierung unabhängig von Hole Card; Verteilungen normalisiert; Check–Bet–Raise–Call- und
  Off-Tree-Fixtures ohne Range-Reset; Latenz ≥500 Entscheidungsaufrufe (geschichtet: beide Positionen,
  Schwelle, Raise, Jam, kalt/warm) **p99 < 8 s, kein regulärer Aufruf ≥ 9 s.**

## K3 — River-Prüfstand (`research/policy_oracle.py`, `research/river_br_pruefstand.py`)
- **Gemeinsames Root-Spiel je Quellhand:** ein River-Root, Evaluations-Verteilung ρ_s = (K1-Hero-Range
  [gekennzeichnet], Tracker-Villain-Range) für BEIDE Arme; intern spielt A mit seinen Beliefs, B mit K1.
  Sensitivität: mindestens eine alternative Villain-Range-Familie (Preflop-Nullhypothese).
- **Politiken:** B = Plan-Strategie exakt (Combo-Matrix aus dem Solve, KEIN Sampling). A = Oracle der
  ausgeführten v5-Politik: decide() je Combo je Hero-Knoten, ≥4 Seeds → empirische Verteilung
  (gekennzeichnet als Schätzung). Baum unter den Aktionen beider Arme GESCHLOSSEN: finale Sizes beider
  Arme in den Evaluationsbaum; nicht darstellbare Roots = `UNSUPPORTED` (ausgewiesen, nicht projiziert).
- **Kennzahlen getrennt:** einseitiger Sicherheitsverlust E_H(π)=v*−min_σV u(π,σV) mit Spielwert-Klammer
  [L,U]; gepaart ΔE_H = w(π_A)−w(π_B) (Spielwert fällt heraus); lokaler Regret R(s,h;π)=max_a Q−Σπ(a)Q(a)
  gegen gemittelte Solverstrategie (adaptiv genauer gelöst für Q-Urteile). Nenner: je Quellhand, ein Root
  pro Hand, Auswahlgewichte ausgewiesen.
- **Kontrollen:** A/A ≤1e−6; analytisch Matching Pennies (Mischung 0 / rein 1); kleine Karten-Fixture
  gegen unabhängige Enumeration ≤1e−6 (verhindert Oracle-Gegner mit Sicht auf Heros Karten);
  Purify-Kontrolle als weiche Plausibilität, nicht als harte Regel.
- **Holdout:** Nacht-1-Hände (data/sessions/gtow_hands_17870122xx.., Chunks A–D, nie für v8/Trigger/K1
  genutzt) = HOLDOUT; Nacht-2 = Entwicklung. Provenienz im Report.
- **Kandidaten-Gate (Holdout):** einseitige 95 %-Obergrenze ΔE_H ≤ +0,5 bb/100 UND ΔR ≤ +0,5 bb/100,
  mindestens eine der beiden <0; Tail-Fälle separat gegen dichteren Baum.

## K4 — Produktionsintegrität (`pokerbot/runtime_config.py`, `server.py`, `gtowizard.py`, Sidecar)
- server.py: PRINCE + exploit OFF + FINAL_STACK (D1). gtowizard-Adapter: unveränderliche Runtime-Konfig
  VOR Bot-Import; Startabbruch bei Fehlkonfiguration (PRINCE/Exploit/Resolver); frischer Prozess je Chunk
  (gtow_nacht spawnt bereits Subprozesse — beibehalten).
- Fingerprint je Hand (JSONL-Sidecar, Hand-ID): Git-HEAD + dirty, Modell-Hashes (.pt), PRINCE, Exploit,
  Stack, Deception-Parameter, TexasSolver-Status, GPU-Solver-Version, Baum/Iter/Präzision, P_min,
  K1-Version, Sampling-/Fallback-Modus, private_seed-Herkunft. Prüfung dessen, was GELADEN wurde.
- Persistentes Hand-Ledger (Hand-ID, Arm, Hash, AIVAT, technische Ereignisse, Status) nach jeder Hand;
  clear_inprogress erst nach Abgleich; unbekannte Ausgänge markiert, nie 0 imputiert.
- **Abnahme:** 100 % Smoke-Hände mit Fingerprint; Fehlkonfig → Abbruch; Abbruch nach Hand verliert nichts;
  Wiederanlauf ohne Doppelzählung; Fault-Injection (Timeout, 503, Prozessabbruch); v5-Golden-Set
  (Verteilung auf 40 Decks) byte-identisch vor/nach K4.

## K5 — GTOW-Pilot (`research/gtow_nacht_v10.py`)
- Zwei Nächte, Chunks à 500; Sequenzen ABBA / BAAB; Reihenfolge VORAB per Münze (protokolliert);
  benachbarte Chunks = Vergleichspaare (randomisiertes Blockdesign OHNE CRN). Keine Änderung nach
  Zwischenergebnissen. Staffel davor: Smoke 20 → 100 mit v10.
- Technische Ausfälle getrennt: Transport, Deadline-Verletzung, illegale Aktion, unbekannter Abschluss,
  Fallbacks. Illegale Aktion oder wiederholte Deadline-Verletzung → Stopp des Kandidaten. Unbekannte
  Ausgänge >0,5 % → kein Leistungsverdikt.
- **Vorregistrierte Aussage:** Der Live-Test schätzt den AIVAT-Stand beider Arme und deren Differenz
  Δ = μ_v10 − μ_v5-H; primär explorativ (große Effekte/Regressionen). Nichtunterlegenheit mit Marge
  −5 bb/100 wird NUR behauptet, wenn die einseitige 95 %-Untergrenze sie trägt (bei SE≈7 je Differenz
  ist das bei Gleichstand NICHT der Fall → dann „nicht nachgewiesen", nie „gleich gut").

## Gates (Reihenfolge, jedes mit Beweis-Artefakt in data/runs/v10/)
G0 Verträge eingefroren (contracts.py), Holdout-Provenienz, beide Arme startbar ·
G1 Invarianten: K1-Transformationen, Support, Sampling, BR-Kontrollen, Fault-Injection ·
G2 A/A r10_stack 600 Decks EXAKT 0 (zwei Instanzen, gleiche Test-Seeds) + 40-Deck-Divergenz-Smoke +
erzwungene K2-Fixtures + Latenz 500 Aufrufe (p99<8 s) ·
G3 K1-Oracle-Abnahme (TV-Budget) ·
G4 Holdout-Prüfstand (ΔE_H, ΔR, Sensitivität) ·
G5 Kurzer Spiegel 2000 gepaarte Decks vs r8_stack (Katastrophen-/Integritätstest, KEIN Effekt-Nachweis;
klar negativer Befund → Untersuchung) + Analyzer-Export für User-Upload ·
G6 GTOW Smoke 20/100 → Nächte mit unverändertem Artefakt (Tag `auslese-v10-rc`).
Nach G4 keine Strategiekorrektur im selben Release; jede Änderung = neuer Hash, Gates wiederholen.

## Abweichungen von Astras Fassung (bewusst)
1. Basis-Likelihood = Advisor-Backend (approximiert), weil bot.py keine Mischverteilung exponiert;
   Astra erlaubt das mit Oracle-Abnahme — die ist Gate G3.
2. Gating am RIVER-BEGINN (pot_river) statt „Pot ≥ 15 bb bei Heros Entscheidung": verhindert, dass Hero
   eine River-Aktion mit der Basis spielt und erst danach in den Plan wechselt.
3. A-Oracle mit ≥4 Seeds statt vollständiger Verteilung (nicht exponiert); Kosten durch Root-Anzahl
   (≤120) und Caching begrenzt; als Schätzung gekennzeichnet.
4. Spiegel G5 = 2000 Decks (Astras Vorschlag), kein 15k.

## Agenten-Pakete (disjunkte Besitzverhältnisse)
P0 Scouts (Fakten) → P0b Verträge (`pokerbot/strategy/contracts.py`) → parallel P1 K1 · P2 K2 · P3 K3 ·
P4 K4 · P5 K5 (Mock) → Integrator (pargate-Registry `r10_stack`, auslese, Verdrahtung) → Reviewer je
Paket (adversarial) → Gate-Läufer G1–G5 → Bericht. Niemand außer dem Integrator ändert bot.py oder die
Stack-Registry.

## ENTSCHEIDUNGEN NACH DEN SCOUTS (2026-09-07, Fable; Fakten: docs/V10_FAKTEN.md, Verträge: pokerbot/strategy/contracts.py)
- **E1 K2-Eingriffspunkt = (b):** In Plan-Pots (pot_river ≥ 1500 Chips) ist der GPU-River-Plan DIE River-
  Politik; der interne TexasSolver-River-Resolver wird dort NICHT aufgerufen (K2 ist der äußerste Wrapper und
  ruft base(st) in Plan-Pots nicht). Unterhalb der Schwelle und am Turn bleibt TexasSolver AN wie in v5.
  Präzisierung der Karte: „TexasSolver bleibt AN außer in River-Plan-Pots". Der Trace hat in Plan-Pots
  keinen Basis-Eintrag (dokumentiert).
- **E2 Kanäle:** G2 (A/A) und G5 (2000-Deck-Spiegel) laufen auf dem pargate-Kanal (exploit ON, kein PRINCE,
  Resolver AUS) und werden so GEKENNZEICHNET (Gym-Kanal = Integritäts-/Nichtverschlechterungs-Schranke).
- **E3 K1-Backend:** Advisor-Likelihood + exakte Guard-Transformationen für Preflop/Flop/Turn (River-Beginn-
  Range braucht die River-Politik nicht). G3-TV-Abnahme getrennt je Kanal (Gym: Turn-Resolver AUS; Live: AN).
  Zusätzlich `resolver.river_strategy()` (Verteilung statt Sample, additiv, Byte-Identität von river_resolve
  bewacht) — für K3s Arm-A-Politik.
- **E4 Hand-Adresse:** `hand_id` wird in `duplicate._setup_fixed` in den State injiziert (Deck-Index);
  private_seed(Gym) = keyed_hash(job_seed, hand_id, seat). Abnahme: 40-Deck-Golden-Set r8_stack vs basis
  byte-identisch vor/nach (data/runs/v10/golden_*.json) + A/A. Live: hand_id aus gtow_to_state, private_seed
  aus os.urandom je Prozess (geloggt).
- **E5 Deadline:** Gym = feste 150 Iterationen, KEIN Zeitabbruch (Determinismus). Live = zusätzlich 7,5 s
  Zeit-Deadline im Plan-Guard (Solve im Thread, verspätetes Ergebnis verworfen, Status im Trace) und
  `PokerBotMVP.act` via asyncio.to_thread.
- **E6 Guard-Bedingungen bitgenau:** C(h) für turn_wert/sel_guard wird mit demselben CPU-MC-Pfad (iters 160,
  `_spot_rng` mit hypothetischer Combo) je Combo nachgebildet, damit G3 K1 misst und nicht eine GPU-
  Approximation. „gpu_equity vektorisiert" aus K1 gestrichen.
- **E7 Injektion:** K2 nutzt `RiverCFRBatch` direkt (eigener Pfad in river_plan.py); gpu_resolver.py bleibt
  unverändert → r8_stack/r10_ernte byte-identisch.
- **E8 Ledger/Fingerprint:** `pokerbot/benchmark/gtow_ledger.py` + dokumentierter Minimal-Patch in der
  gitignorierten tools/gtow_client main.py (docs/V10_LEDGER_PATCH.md); Fingerprint + Fehlkonfig-Gatter
  (SystemExit) in `PokerBotAgent.__init__`; `POKERB_AUSLESE_STACK` in die Fingerprint-Keys.
- **E9 Holdout:** die vier Nacht-1-Dateien namentlich (gtow_hands_1787012286/1787014241/1787016046/
  1787017672.jsonl), Provenienz `v4_gym_nackt` (exploit ON, resolver OFF) ausgewiesen; nur Root-Geometrie +
  Villain-Range genutzt; Ausschluss-Zähler im Report.
- **E10 Zahlen:** A/A = 576 Decks (12 Worker × 48 Jobs), neue Bank 1080000 ff.; Einheiten 20000/50/100.
  **Latenz-Gate korrigiert:** der Harness hat KEINE Entscheidungs-Deadline (nur httpx 180 s, Chunk 10800 s);
  Gate = Plan-Pot-Entscheidungen p99 < 8 s UND Gesamt-p99 v10 ≤ Gesamt-p99 v5-H (keine Regression) UND kein
  Aufruf ≥ 30 s. `analyze_gtow_hands.py` BB=50→100 korrigieren, bevor es zitiert wird.
- **E11 Rollen:** K1 Hero = Initiative-Rolle (wie decide), Villain = Position (wie Tracker); Abweichung in G3
  nach Pot-Typ getrennt. `p_defense_batch` additiv mit Identitäts-Wache erlaubt („Advisor-Umbau" =
  Gewichts-/Feature-Änderung, ausgeschlossen).

## NACHTRAG INTEGRATION (2026-09-07 abends, Fable)
- hand_id im Gym = DECK-Adresse (hand_id_basis + deck_idx), für beide Spiegelhälften GLEICH — gemessen
  notwendig: mit halb-eindeutigen Adressen war der A/A −9,40 ± 10,92 (private Seeds der Hälften verschieden).
- K1_AKZEPTIERTE_STATUS = ("ok", "teilweise") (river_plan.py): „teilweise" = legality-only-Raise-Knoten, den
  der Tracker identisch behandelt; Fallback hätte alle Guard-Transformationen verworfen. Neuer Hash → G2a.
- Latenz-Treiber ist K1 (bitgenaue CPU-MC-Guard-Bedingungen je Combo, bis 5,7 s), nicht der Solve (2,5 s).
- K3-Oracle: exakt nur mit einem GPU-Solve je Combo (Injektion); 0,205 s/Combo → G4 ist ein Mehrstunden-Gate;
  Budget in Stufe 3: 150 min, Status UNVOLLSTAENDIG bei n < 20 Roots, Fortsetzung über den Oracle-Cache.
