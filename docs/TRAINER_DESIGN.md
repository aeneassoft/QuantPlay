# TRAINER_DESIGN.md — Das Trainingsprogramm (Design-Blueprint, 2026-07-08)

**Produkt:** 6-max NLHE Trainingsprogramm auf der bestehenden Plattform (`six_server` + Engine).
**Basis-Bot:** PRINCE v2.2 (`POKERB_PRINCE=1`) — die meist-gemessene Version (Quantplay v8: AIVAT −30.11 ± 5.51,
n=2.899, Rang 24/64; Historie −19.70 n=2.393 auf dem alten Harness). Für menschliche Gegner mehr als stark
genug; die Engine-Grenze wird im Grading ehrlich ausgewiesen.
**Leitprinzip:** Engine = Wahrheit · Templates = Erklärung · kleines LLM = Stimme · Claude (Code, in-session) =
Entwicklungs-Coach. Einfach und effizient — NICHT überladen.

---

## 1. Fairness-Doktrin des Gradings (BINDEND)

Poker ist ein Spiel unvollständiger Information mit gemischten Strategien. Das Grading MUSS das abbilden:

1. **Nie Ergebnisse graden, nur Entscheidungen.** Gewonnene Hand ≠ gute Hand; verlorene ≠ Fehler.
   (Anti-Resultorientierung ist selbst Lehrinhalt №1.)
2. **Grade-Bänder statt binär:**
   - ✓ **OK** — Aktion liegt im gemischten Support (Advisor-Frequenz ≥ ~15 %) ODER innerhalb kleiner
     EV-Toleranz der besten Linie. Mehrere Aktionen können gleichzeitig OK sein — das wird auch GESAGT
     („GTO mischt hier: 60 % Bet / 40 % Check — beides gut").
   - ～ **Teuer** — klar unterlegene Linie, moderater EV-Verlust.
   - ✗ **Leak** — nur bei mathematisch harten Verstößen (Pot-Odds klar verletzt, grobe MDF-Verletzung,
     Sizing-Geometrie-Fehler) oder großem EV-Verlust.
3. **Unsicherheits-Hierarchie ausweisen:** Preflop (near-Nash-Blueprint) und River (Resolver) = harte Urteile;
   Mathe-Checks = unanfechtbar; Flop/Turn-Strategie = „Bot-Einschätzung", so gelabelt. Der Trainer, der seine
   Grenzen nennt, ist glaubwürdiger.
4. **Range-Toleranz:** Der Mensch konstruiert Ranges approximativ. Bewertet wird die ENTSCHEIDUNGSLOGIK
   („war die Aktion gegen eine vernünftige Range vertretbar?"), nicht die Übereinstimmung mit der exakten
   Tracker-Range.
5. **Ton: warm, konkret, nie eiskalt.** Gute Züge werden EXPLIZIT gefeiert (nicht nur Fehler markiert).
   Leaks heißen „teurer Kauf", nicht „Fehler". Jede Kritik trägt die Alternative + den Ein-Satz-Grund.
   Engagement über Inhalt (Hand der Session, beste Entscheidung, Fortschritt seit letzter Session) —
   KEINE Gamification-Bloat (keine Punkte/Badges/Level).

## 2. Zwei Modi

| | GTO-Modus | Exploit-Modus |
|---|---|---|
| Bot-Config | `POKERB_PRINCE=1`, exploit OFF (= die gemessene Basis) | dieselbe Basis + `exploit=True` |
| Verhalten | spielt seine GTO-Approximation, ignoriert Spieler-Tendenzen | GTO-Baseline + **begrenzte, LCB-gegatete Abweichungen** (opp_model/Dirichlet lernt den Trainierenden live) — realistisch, kein Cartoon |
| Trainingszweck | Grundlinie lernen, Balance fühlen | unter Druck bestehen; die eigene Ausbeutbarkeit ERLEBEN |
| ★ Killer-Feature | — | **„Was der Bot über dich gelernt hat"**-Panel: die gelernten Dirichlet-Tendenzen des Trainierenden als Klartext („er hat bemerkt: du foldest 68 % auf River-Bets → er blufft dich öfter"). Exploit-Schicht = Leak-Detektor. |

## 3. Sprachschicht — Interface-first, Backend austauschbar (Verzettel-Schutz)

- **Vertrag:** strukturiertes JSON rein (Grades, Zahlen, rationale, strategic_read) → kurzer Text raus.
  Die Sprachschicht ENTSCHEIDET NICHTS und RECHNET NICHTS (LLM-Autorität invers zur Engine-Kompetenz).
- **Phase jetzt:** deterministische **Templates** (P1) + **Claude Code in-session als Entwicklungs-Coach**
  (kostenlos, beste Qualität): wir spielen, ich coache live, die besten Formulierungen werden in die
  Template-Bibliothek destilliert. Aus dem Optimierungsprozess LERNEN — das ist der Plan des Users.
- **Phase später (P3):** EIN gemessener Latenz-/Qualitätstest: Ollama (Qwen3-8B-Instruct GGUF) vs eigenes
  Serving (GLM-Erfahrung). Kriterium: < 2 s Antwort, kein Halluzinieren der Zahlen (Zahlen kommen NUR aus
  dem JSON). Das einfachere System gewinnt. Unsere GLM-Lektionen (Template-Disziplin, Validitäts-Gates,
  frac_bad-Messung) übertragen sich auf beide.
- **Claude API:** vorerst NICHT (kein Guthaben). Premium-Tiefenreviews laufen als Claude-Code-Sessions.

## 4. Datenschicht

- `data/sessions/` JSONL existiert (pro Hand). NEU: **pro ENTSCHEIDUNG** ein Record:
  `{hand_id, ts, street, spot_fp, state_kompakt, human_action, oracle_action, advisor_dist,
   equity, pot_odds, mdf, grade, grade_typ, erklärung_kurz, mode}`
- Append-only + Session-Registry. Die 1000-Hände-Analyse = die Prince-Protokoll-Maschinerie auf eigene
  Logs (Format kontrolliert → kein Parser nötig).
- Qualitätskontrolle des Trainers selbst: Export der Menschen-Hände im PokerStars-Format
  (`research/pokerstars_export.py`-Pfad) → GTOW-Analyzer als externe Zweitmeinung über unsere Grades.

## 5. Lern-Maximierung

- **Fehlerraten-Band 10–20 %** (85%-Regel, Wilson et al. 2019 — ehrlich: auf Poker eine HYPOTHESE, als
  adaptives Band umgesetzt, nicht als Dogma). Regler = Gegner-Liga (`arena/sixmax.py`: nit/tag/lag/station/
  maniac + Bot ± Exploit) wird pro Session nachgeführt.
- **Sofort-Feedback light** im Spiel (✓/～/✗-Icon, KEIN Textwall — Flow!) + **Tiefenreview nach der Hand**.
- **Leak-Drilling:** schwächste Spot-Kategorie der letzten Sessions wird häufiger erzeugt (spaced repetition
  über Spots). **Interleaving:** Positionen/Stack-Tiefen gemischt.

## 6. UI-Spezifikation (2560×1440, Snowie-orientiert)

- **Layout:** links ~60 % kompakter Tisch, rechts ~40 % Coaching-Panel. Tisch bewusst NICHT groß.
- **Tempo:** maximale Hände/Stunde — Animationen < 300 ms, Bot-Entscheidungen instant (Engine ist schnell),
  Hotkeys (F/C/R + Sizing-Shortcuts), Auto-Deal nach Feedback-Dismiss oder Timeout.
- **Sichtbarkeit:** Akteur-Highlight, Einsatz-Beträge GROSS am Chip, Pot permanent sichtbar, kurze fließende
  Info-Zeile („CO bets 12 → BTN calls"). Optisch sehen, was passiert.
- **Ablauf:** Hand für Hand. Nach JEDER Hand: 3–5-Zeilen-Feedback rechts.
- **Replay-Button:** animierte Wiederholung der Hand, Schritt für Schritt; an jedem Hero-Spot: gespielte vs
  empfohlene Aktion + Ein-Satz-Strategie (aus `strategic_read` + rationale) → „so spielt man die Hand".
  Vollständig deterministisch aus dem Decision-Log rekonstruierbar.
- **NICHT bauen:** Accounts, 3D, Sounds-Design, Mobile, Gamification, Multi-Table. Einfach + effizient.

## 7. Autotest vor Menschen-Einsatz (verbindlich)

Liga-Bots spielen den „Menschen"-Sitz durch den KOMPLETTEN Stack (Logger → Grader → Renderer → Replay →
Sprachschicht): N Hände automatisch. Prüfkriterien: 0 Crashes · Latenz-Budgets eingehalten · Grade-Verteilung
plausibel (station wird schlechter benotet als tag — Sanity!) · jede rationale-Pfad rendert Text
(Template-Coverage) · Session-Report baut.

## 8. Bauphasen

| Phase | Inhalt | Status-Basis |
|---|---|---|
| **P0** | Decision-Logger + Mathe-Grades (pot-odds/MDF/Sizing) + Oracle-Diff | session_log existiert; decide()-rationale existiert |
| **P1** | Erklär-Renderer (Templates auf rationale + strategic_read) + Nach-Hand-Feedback + Session-Report | understanding.py + Protokoll-Maschinerie existieren |
| **P2** | UI-Umbau (Layout/Tempo/Replay) + adaptiver Schwierigkeitsregler + Leak-Drills | six_server/six.html existiert |
| **P3** | Sprachschicht-Backend-Test (Ollama vs eigen) + „Was der Bot gelernt hat"-Panel | opp_model existiert |
| **P4** | Autotest-Harness + Politur | Liga existiert |
