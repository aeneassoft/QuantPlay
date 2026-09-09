# Vorbemerkung: drei Tatsachen müssen korrigiert werden

1. **Das Wettbewerbsziel und der HU-Hauptkanal sind 200 bb, nicht 100 bb.** Der 140-bb-gated Preflop-Blueprint läuft auf GTOW/pargate, aber nicht in Kaggle. Kaggle ist deshalb kein Volumenkanal für denselben Bot.
2. **−21,12 bb/100 ist kein Anker des heutigen Champions v5.** Es ist der Anker von v4/r6_button auf PRINCE, wahrscheinlich Resolver-ON, aber ohne geprüften Runtime-Fingerprint. v5 kann besser, gleich gut oder schlechter sein; die Selfplay-Differenzen dürfen nicht auf GTOW addiert werden.
3. **Die „fehlenden 8 bb/100“ sind erklärbar:** −21,12 bis ungefähr −13,1 Mittelwert bei rund 50.000 Händen sind etwa 8 bb/100. Bis zur asymptotischen LCB-Grenze −14,8 fehlen dagegen etwa 6,3 bb/100. Das sind keine widersprüchlichen Ziele, sondern dieselbe Leaderboard-Regel bei unterschiedlichem Volumen.

Im Folgenden kennzeichne ich strikt:

- **WAS ICH WEISS:** Theorie, belastbare Projektmessung oder direkte logische Folgerung.
- **WAS ICH VERMUTE:** Planungsprior oder erwartete Größenordnung, ausdrücklich nicht gemessen.
- **WAS GEMESSEN WERDEN MUSS:** fehlender projektspezifischer Nachweis.

---

# Frage 1 – Der „Zwitter“

## Kurzurteil

**Ein ausführbares Programm, das alle Spielvarianten und mehrere Experten enthält: ja.**

**Ein HU-200-bb-Bot, der bei jeder Entscheidung einfach das vermeintlich beste vorhandene Modul auswählt: nein. Das ist in dieser Form ein spieltheoretischer Denkfehler.**

**Tragfähig ist nur ein stark eingeschränkter Zwitter:**

1. ein vollständig definierter produktiver Baseline-Bot,
2. wenige **geschlossene** Experten für klar abgegrenzte öffentliche Roots,
3. ein Selektor, der Teil der Gesamtstrategie ist,
4. korrekte Reach-/Range-Fortschreibung unter genau dieser Gesamtstrategie,
5. vollständige Fortsetzungen und ein produktiver Fallback,
6. nach Möglichkeit eine Subgame-Sicherheitsschranke,
7. Messung der kompilierten Gesamtpolitik, nicht der Module.

Für PokerB heißt das zunächst nicht „alles integrieren“, sondern:

> **v5 als Baseline + genau ein kohärenter River-Experte + vollständige v5-Fortsetzung + konservativer öffentlicher Selektor.**

ICM, 6-max, LLM-Brain, refutierte Exploit-Overlays und ungeschlossene GPU-Aktionspicker gehören nicht in dieselbe HU-Cash-Policy.

---

## 1(a) Ist die Idee tragfähig oder ein Denkfehler?

### WAS ICH WEISS – die spieltheoretische Form

Eine Pokerstrategie ist eine Abbildung von Informationszuständen auf Aktionsverteilungen:

\[
\sigma(a\mid I)
\]

Ein Zwitter mit Experten \(E_1,\dots,E_K\) und Auswahlwahrscheinlichkeiten \(q_k\) ist ebenfalls nur eine Strategie:

\[
\sigma_Z(a\mid I)
=
\sum_k q_k(I)\,\sigma_k(a\mid I)
\]

Das gilt allerdings nur so einfach, wenn der Expertenmodus nach der Auswahl keine fortdauernde verborgene Zustandsvariable ist. Bleibt ein einmal gewählter Experte über mehrere Entscheidungen aktiv, muss der Zustand als gemeinsame Verteilung über Hand und Expertenmodus geführt werden:

\[
r(h,k\mid H_t)
\]

Die Ausbeutbarkeit von \(\sigma_Z\) ist **nicht** das Minimum der Ausbeutbarkeiten der Teile.

### Drei verschiedene Arten von „Mischung“

#### 1. Ex-ante-Auswahl eines ganzen Bots

Am Beginn einer Hand wird Bot A mit Wahrscheinlichkeit \(\lambda\), sonst Bot B gewählt. Gegen einen festen Gegner ist der Erwartungswert linear:

\[
u(\lambda A+(1-\lambda)B,\tau)
=
\lambda u(A,\tau)+(1-\lambda)u(B,\tau)
\]

Damit kann eine solche Mischung gegen denselben festen Gegner **nicht besser als der bessere Elternbot** sein. Sie kann höchstens zwischen beiden liegen.

Für Exploitability gilt wegen der Maximierung durch die Best Response eine Konvexitätseigenschaft: Eine echte konvexe Mischung kann Fehler teilweise ausgleichen, besitzt aber **keine Garantie, besser als das beste Einzelteil zu sein**. Sie ist im Allgemeinen nur gegen den gewichteten Durchschnitt der Elternfehler beschränkt.

#### 2. Kontextabhängige Auswahl an öffentlichen Zuständen

Beispiel:

- Experte A ist besser in kleinen River-Pötten.
- Experte B ist besser in großen River-Pötten.
- Der Selektor sieht Pot, SPR, Board, Aktionsmenge und öffentliche Reach-Verteilungen.

Dann kann der Zwitter besser als beide Gesamtbots sein, **wenn** die Bewertung jeweils unter derselben Root-Verteilung und derselben Fortsetzungsdefinition erfolgt. Das ist der legitime Fall komplementärer Spezialisierung.

#### 3. Aktionsweise „nimm das höchste Q“

Das ist die gefährliche Variante. Q-Werte verschiedener Module sind oft nicht vergleichbar, weil sie verschiedene Dinge voraussetzen:

- verschiedene Hero-Ranges,
- verschiedene Villain-Ranges,
- verschiedene Sizing-Abstraktionen,
- verschiedene Fortsetzungen,
- verschiedene Normalisierungen von CFVs,
- verschiedene Fallbacks,
- verschiedene Annahmen über die gegnerische Reaktion.

Das Maximum zweier inkompatibler Q-Werte ist kein Policy-Improvement. Es ist häufig nur **Auswahlbias**.

### Wann kann der Mischer nachweislich besser sein?

Ein Mischer kann belastbar besser sein, wenn mindestens eine der folgenden Bedingungen erfüllt ist:

1. **Fester Gegner, gleiche Fortsetzung:** Für jeden ausgewählten Root wird der alternative Experte mit identischen Beliefs und identischer nachgelagerter Politik bewertet, und seine erwartete Differenz ist positiv.
2. **Exakte lokale Policy-Improvement-Bedingung:** Die neue Aktion hat unter derselben Reach-Verteilung und unveränderter Fortsetzung höheren Gegenwert. Das ist gegen einen festen Gegner möglich, aber nicht automatisch gegen eine adaptive Best Response.
3. **Safe Subgame Solving:** Der neue Subgame-Plan hält geeignete gegnerische Counterfactual-Value-Grenzen der Baseline ein. Dann kann unter den Modellannahmen garantiert werden, dass die Gesamtstrategie nicht stärker ausbeutbar wird.
4. **Komplementäre Fehler unter einem vollständigen BR-Test:** Die kompilierte Mischung hat gegen die exakte Best Response geringere Exploitability als jeder Elternbot.

### Wann ist er nachweislich schlechter?

1. **Ganzbot-Mischung gegen einen festen Gegner:** Wenn der schlechtere Elternbot positives Gewicht erhält, sinkt der Wert gegenüber dem besten Elternbot, sofern keine Kontextselektion stattfindet.
2. **Selektor erzeugt Hand-/Sizing-Tells:** Wenn Expertenwahl und private Hand korrelieren und diese Korrelation nicht in den Ranges fortgeschrieben wird, erhält Villain falsche oder tatsächlich ausbeutbare Range-Information.
3. **Off-Tree-Fallback verliert produktive Schichten:** Genau das geschah bei v10. Ein Plan mit positivem On-Tree-Verhalten kann insgesamt schlechter sein, wenn die Fehlerrouten auf die nackte Basis fallen.
4. **Unvollständige Fortsetzung:** Ein lokal guter River-Action-Picker ist keine vollständige Strategie, wenn spätere Raises, All-ins, unbekannte Sizings oder Solver-Time-outs undefiniert sind.
5. **Selektor vergleicht inkompatible EVs:** „TexasSolver sagt +x, Advisor sagt +y“ ist wertlos, wenn die Root-Ranges oder Fortsetzungen verschieden sind.
6. **Verborgene Runtime-Selektion:** Wenn schwierige Roots häufiger in den Fallback laufen, ist Timeout selbst ein strategisch korreliertes Gate. Das muss als Teil der ausgeführten Politik gemessen werden.

### Anwendung auf PokerB

**WAS ICH WEISS**

- v10 hat genau den klassischen Zwitterfehler gezeigt: positive reine Plan-Decks, aber große Verluste auf dem degradierenden Off-Tree-Fallback.
- v8 war bereits ein empirischer Test der Doktrin „bestehende Komponente zusätzlich in die Kette“. Ergebnis gegen v5 ungefähr neutral und gesättigt; das widerlegt nicht jeden Zwitter, aber klar den naiven additiven Ansatz.
- v5 selbst ist eine Wrapper-Komposition mit mehreren semantisch unterschiedlichen Schichten. Dass sie im Spiegel stark war, beweist nicht, dass weitere Schichten monoton helfen.
- Der einzige GTOW-Anker wurde stark von wenigen tiefen River-Calls dominiert. Das spricht für gezielte geschlossene River-Reparatur, nicht für eine universelle Komponentenauktion.

**WAS ICH VERMUTE**

- Ein **Zwei-Experten-Hybrid auf River-Roots** kann gegen GTOW wahrscheinlich in der Größenordnung **0 bis +3 bb/100** gegenüber v5 bringen.
- Ein per Entscheidung frei umschaltender „Alles-Zwitter“ hat eine erhebliche Wahrscheinlichkeit, schlechter als v5 zu sein. Meine Planungsannahme wäre **−3 bis +2 bb/100**, weil Naht-, Range-, Off-Tree- und Latenzfehler den theoretischen Auswahlgewinn leicht übersteigen.
- Ein echter sicherer Re-Solver mit konsistenten Beliefs besitzt langfristig mehr Potenzial, ist aber kein Vier-Wochen-Integrationsprojekt.

**WAS GEMESSEN WERDEN MUSS**

- GTOW-Anker des exakt produktiven v5.
- Häufigkeit planfähiger River-Roots pro 100 Hände.
- Pro-Trigger-EV des River-Plans gegenüber v5 unter identischen Root-Ranges.
- Nahtverlust bei Plan → v5-Fortsetzung.
- Exploitability der kompilierten Gesamtpolitik gegen K3-BR.
- Timeout- und Off-Tree-Politik als Teil derselben Messung.

---

## 1(b) Die spieltheoretisch korrekte Formulierung

Die vermutete Begriffsmenge ist richtig, aber unvollständig.

### Erforderliche Begriffe

1. **Policy Closure / Politik-Abschluss**  
   Für jeden erreichbaren Informationszustand existiert eine legale Aktionsverteilung, einschließlich:
   - unbekannter gegnerischer Sizings,
   - Re-Raises,
   - Time-outs,
   - Solverfehler,
   - leeren Supports,
   - Action-Translation-Fehlern.

2. **Reach- und Range-Konsistenz**  
   Die eigenen und gegnerischen Reach-Gewichte folgen genau den tatsächlich ausgeführten Aktionswahrscheinlichkeiten:

   \[
   r_{t+1}(h)
   \propto
   r_t(h)\,\sigma_Z(a_t\mid h,H_t)
   \]

3. **Fortsetzungs-Konsistenz**  
   Der EV einer vorgeschlagenen Aktion wird mit der Fortsetzung bewertet, die nach Auswahl tatsächlich gespielt wird.

4. **Subgame-Sicherheit**  
   Eine neue lokale Strategie darf die für den Gegner garantierten Counterfactual Values nicht unkontrolliert erhöhen.

5. **Selection Observability / Selektor-Semantik**  
   Es muss klar sein, welche Selektorvariablen öffentlich, privat oder rein intern sind und wie ein Gegner daraus über beobachtete Aktionen inferiert.

6. **Joint latent state**  
   Bleibt ein Expertenmodus persistent, reicht eine marginale Handrange nicht. Man braucht \(r(h,k)\), weil dieselbe Hand je Expertenmodus später verschieden spielt.

7. **Action-Semantik**  
   Aktionen müssen über eine gemeinsame kanonische Aktionsmenge verglichen werden. „Bet 75 % Pot“ und „Solver-Aktion 0.66 Pot“ sind nicht dieselbe Aktion.

8. **Runtime als Teil der Strategie**  
   Time-outs und Cache-Hits sind nicht bloß technische Fehler, wenn sie systematisch mit Root-Typen korrelieren.

9. **Abstraktions- und Approximationsbudget**  
   Safe Subgame Solving ist nur relativ zur verwendeten Abstraktion, den CFV-Bounds und den Beliefs sicher. TexasSolver, GPU-CFR und Advisor teilen diese Fehler nicht automatisch.

### Saubere Formulierung

Ich würde den Zwitter **nicht primär als „erweitertes Pokerspiel mit Experten“** implementieren. Das ist theoretisch möglich, erzeugt aber unnötige versteckte Zustände.

Die bessere Formulierung ist:

> Eine einzige kompilierte Verhaltensstrategie auf einem öffentlichen Belief-State, deren interne Berechnung mehrere Experten verwendet.

Der öffentliche Belief-State enthält mindestens:

\[
B_t = (H_t,\; r_H,\; r_V,\; A_{\text{legal}},\; \text{pot},\; \text{stacks},\; \text{position})
\]

Die ausgeführte Strategie ist:

\[
\sigma_Z(a\mid h,B_t)
=
\sum_k q_k(h,B_t,z_t)\,\sigma_k(a\mid h,B_t,z_t)
\]

wobei \(z_t\) den persistenten internen Modus bezeichnet. Falls \(z_t\) die Zukunft beeinflusst, muss die Policy über \(z_t\) abgeschlossen und die Reach-Verteilung darüber fortgeschrieben werden.

### Empfohlene Form: Baseline plus sicherer Spezialist

Nicht:

> „Alle Experten geben eine Aktion ab, der Arbiter nimmt die beste.“

Sondern:

> „Die Baseline besitzt die gesamte Hand. An vorregistrierten öffentlichen Roots darf ein Spezialist die gesamte Resthand übernehmen, wenn Domain-, Sicherheits-, Laufzeit- und EV-Gates erfüllt sind.“

Das reduziert Wechselpunkte drastisch.

### Einschlägige Literatur

- **Kuhn:** Mixed versus behavioral strategies bei perfect recall.
- **Zinkevich et al.:** Counterfactual Regret Minimization.
- **Burch, Johanson, Bowling:** Zerlegung und Subgame Solving in Imperfect-Information Games.
- **Ganzfried & Sandholm:** Endgame Solving und Gefahren des unsicheren Lösens.
- **Brown & Sandholm:** Safe and Nested Subgame Solving; Libratus.
- **Moravčík et al.:** DeepStack und Continual Re-Solving mit Counterfactual Values.
- **Brown et al.:** Deep CFR.
- **Brown et al., ReBeL:** Suche auf Public-Belief-States mit gelernten Werten.

Die für PokerB zentrale Literatur ist nicht Ensemble-Learning, sondern **safe/continual resolving auf öffentlichen Beliefs**.

---

## 1(c) Wovon darf die Auswahl abhängen?

### Öffentliche Auswahl

Die bestehende Doktrin ist als Engineering-Standard richtig:

> Öffentliches Gating ist der Standard.

Zulässige Selektorfeatures:

- Straße,
- öffentliche Aktionshistorie,
- Pot und effektive Stacks,
- SPR,
- Position,
- Board und Textur,
- legale Aktionen,
- Sizing-Abstand zur Abstraktion,
- Entropie und Supportqualität beider Ranges,
- Solver-Konvergenzdiagnostik,
- Cache-Status,
- gemessene Runtime-Prognose,
- Planstatus und Prefix-Ledger.

Nicht zulässig als angeblich „öffentliches“ Feature:

- tatsächliche Hero-Holecards,
- handabhängiger Hash,
- eine Konfidenz, die indirekt aus der tatsächlichen Hand statt aus der gesamten Range berechnet wurde.

### Private Auswahl ist nicht grundsätzlich falsch

Hier ist die Doktrin zu streng, wenn sie als Verbot verstanden wird.

**Handabhängige Auswahl ist spieltheoretisch erlaubt.** Jede Pokerstrategie hängt von den privaten Karten ab. Der korrekte Aggregate ist:

\[
\sigma_Z(a\mid h,B_t)
=
\sum_k q_k(h,B_t)\sigma_k(a\mid h,B_t)
\]

Nach beobachteter Aktion muss die Hero-Range mit genau dieser aggregierten Aktionswahrscheinlichkeit aktualisiert werden:

\[
r'_H(h)
\propto
r_H(h)\sum_k q_k(h,B_t)\sigma_k(a\mid h,B_t)
\]

### Was bei privatem Gating kaputtgeht

Es geht nicht kaputt, **weil** private Karten verwendet werden. Es geht kaputt, wenn das System danach so tut, als wären sie nicht verwendet worden.

Typische Fehler:

1. Der Plan wird für alle Hände mit einer öffentlichen Root-Range gelöst, aber nur starke Hände dürfen ihn verwenden.
2. Der Solver glaubt an \(r_H(h)\), tatsächlich spielt aber eine selektierte Range \(r_H(h)q(h)\).
3. Fallback und Plan haben unterschiedliche Handselektion, die nach außen an Sizings erkennbar wird.
4. Ein persistenter Hash legt pro Hand einen Experten fest, aber spätere Ranges marginalisieren den Expertenmodus weg.
5. Die echte Hand wird nachträglich in einen leeren Range-Support eingefügt. Das repariert keine öffentliche Range, sondern erzeugt private Clairvoyance.

### Saubere Konstruktion für privates Gating

Es gibt zwei zulässige Varianten.

#### Variante A – Auswahl bei jeder Entscheidung neu

- Berechne \(q_k(h,B_t)\).
- Aggregate alle Expertenaktionen zu \(\sigma_Z(a\mid h,B_t)\).
- Sample genau einmal aus der Aggregatverteilung.
- Update die Range mit der vollständigen Aggregatwahrscheinlichkeit.
- Kein Expertenmodus bleibt persistent.

Das ist mathematisch sauber, aber teuer und engineeringseitig schwer, weil alle Experten eine vollständige Aktionverteilung für alle Hände liefern müssen.

#### Variante B – persistenter privater Expertenmodus

- Ziehe \(k\) aus \(q_k(h,B_t)\).
- Führe gemeinsam \(r(h,k)\).
- Bei jeder Aktion:

  \[
  r'(h,k)\propto r(h,k)\sigma_k(a\mid h,B_t,k)
  \]

- Marginalisiere nur dann über \(k\), wenn die spätere Policy nicht mehr von \(k\) abhängt.

Das ist korrekt, aber für PokerB derzeit unnötig komplex.

### Empfehlung

Für die erste Version:

- **nur öffentliche Root-Selektion;**
- private Karten nur innerhalb der gewählten vollständigen Expertenstrategie;
- kein holecard-basierter Expertenhash;
- keine Umschaltung pro Aktion.

| Empfehlung | Erwartete GTOW-Wirkung | Kosten | Risiko | Billigster Falsifikationstest |
|---|---:|---:|---|---|
| Öffentliches Root-Gating statt handabhängigem v9-Hash | direkt etwa 0; verhindert potenziell mehrere bb/100 Naht-/Rangeverlust | 2–4 Bautage | zu konservativ, verpasst echte private Spezialisierung | Auf bestehenden Roots Aggregate-Range mit und ohne Hash vergleichen; K3-BR gegen beide kompilierte Policies |
| Privates Gating erst nach vollständiger \(r(h,k)\)-Unterstützung | zunächst 0 | 1–2 Wochen zusätzlich | hohe Komplexität, neue stille Fehler | Unit-Spiel mit zwei Händen/zwei Experten: Reach-Massen analytisch gegen Ledger prüfen |

---

## 1(d) Konkrete Architektur

## 1. Der ausführbare Bot ist ein Dispatcher, nicht eine Suppe

Am Handbeginn wird nach Spielkonfiguration getrennt:

```text
GameDispatcher
├── HUCash200Policy
├── KaggleHU100Policy
├── SixMaxCashPolicy
└── TournamentICMPolicy
```

Diese Policies dürfen Code teilen, aber nicht dieselbe strategische Kette vortäuschen.

- ICM wird nur im Turniermodus geladen.
- 6-max-`flat_guard` bleibt 6-max.
- HU-Guards werden niemals in Multiway verdrahtet.
- Kaggle-100-bb ist wegen des 140-bb-Blueprint-Gates eine eigene Strategieversion.

## 2. Datenstrukturen

```python
@dataclass(frozen=True)
class PublicStateKey:
    street: int
    board_iso: tuple[int, ...]
    action_history: tuple["CanonicalAction", ...]
    pot_bb_q: int
    stacks_bb_q: tuple[int, int]
    position: int
    legal_action_signature: tuple

@dataclass
class BeliefState:
    hero_reach: np.ndarray      # 1326 oder board-gefiltert
    villain_reach: np.ndarray
    hero_support: np.ndarray
    villain_support: np.ndarray
    normalization_log: list
    source_fingerprint: str

@dataclass
class ExpertProposal:
    expert_id: str
    policy_version: str
    action_probs_by_hand: np.ndarray
    canonical_actions: tuple["CanonicalAction", ...]
    cfv_hero: np.ndarray | None
    cfv_villain: np.ndarray | None
    domain_ok: bool
    safety_certificate: "SafetyCertificate | None"
    predicted_runtime_ms: float
    solve_id: str
    continuation_id: str

@dataclass
class HybridHandState:
    policy_fingerprint: str
    public_key: PublicStateKey
    beliefs: BeliefState
    mode: str                   # BASELINE, PLAN_ACTIVE, CONTINUATION
    active_expert: str | None
    plan_root: PublicStateKey | None
    prefix_ledger: list
    solve_generation: int
    deadline_ns: int
    randomization_seed: bytes
    fallback_reason: str | None
```

### Unverzichtbar im Prefix-Ledger

Für jede Entscheidung:

- öffentlicher Zustand,
- vor der Aktion gültige Hero- und Villain-Reach-Hashes,
- vollständige ausgeführte Aktionsverteilung, nicht nur die gewählte Aktion,
- Expertengewichte,
- gewählte Aktion und kanonische Übersetzung,
- Plan-/Fallbackstatus,
- Runtime und Timeoutgrund,
- Solver-/Policy-Fingerprint,
- Zufallsstream-ID,
- Support- und Normalisierungsdiagnostik.

Ohne vollständige Aktionswahrscheinlichkeit kann H1 die Range nicht rekonstruieren.

## 3. Experten-Schnittstelle

Ein Modul ist nur dann ein auswählbarer Experte, wenn es diese Schnittstelle erfüllt:

```python
class ClosedPolicyExpert(Protocol):
    def domain(self, ctx, beliefs) -> DomainResult: ...
    def propose(self, ctx, beliefs, deadline) -> ExpertProposal: ...
    def continue_after(self, action, next_state, beliefs, deadline) -> ExpertProposal: ...
    def emergency_policy(self, ctx, beliefs) -> ActionDistribution: ...
```

Ein Action-Picker ohne `continue_after` ist **kein Experte**. Er darf höchstens eine Baseline-Aktion überschreiben, und dieser Override muss als neue Gesamtpolitik vermessen werden.

## 4. Welche Experten zuerst?

Für HU-200-bb zunächst nur:

1. `V5ProductiveBaseline`
2. `RiverPlanExpert`
3. optional später `SafeRiverResolveExpert`

Nicht als eigenständige Experten:

- Range-Tracker: Belief-Infrastruktur.
- K3: Prüfstand.
- K4: Instrumentierung.
- GPU-CFR: Rechenbackend.
- Advisor-MLPs: Fallback-/Proposal-Komponente.
- Guards: Teil der kompilierten Baseline, solange nicht einzeln geschlossen.
- TexasSolver: Backend, nicht automatisch eine vollständige Politik.

## 5. Auswahlmechanismus

### Features

Der erste Selektor ist deterministisch und regelbasiert:

```text
street == RIVER
AND pot >= 15 bb
AND public_root_supported
AND hero_support_complete
AND villain_support_complete
AND legal_action_translation_exact
AND predicted_p99_runtime <= remaining_budget
AND no_stale_plan
AND safety_or_value_gate_passed
```

Die 15-bb-Grenze stammt aus dem bestehenden Kandidaten, ist aber noch nicht als optimale Grenze bewiesen.

### Auswahlkriterium

Nicht „höchster vorhergesagter EV“, sondern:

\[
\mathrm{LCB}_{95}(\Delta EV_{\text{Plan-v5}})
-
\mathrm{UCB}_{95}(\text{Nahtverlust})
> 0
\]

Wenn Safe Subgame Solving verfügbar ist, kommt zusätzlich hinzu:

\[
CFV^{\text{new}}_V(I)
\le
CFV^{\text{baseline}}_V(I)+\epsilon_I
\]

für die relevanten gegnerischen Root-Informationszustände.

### Kalibrierung

- Trainings-/Kalibrierungsdaten nach **öffentlichen Roots**, nicht nach einzelnen Entscheidungen splitten.
- Boardfamilien, Potband und Aktionslinie dürfen nicht zugleich in Train und Test liegen.
- Zunächst kein neuronaler Arbiter. Ein kleines GBT oder eine monotone Tabelle reicht.
- Zielwert ist die gepaarte Root-EV-Differenz bei identischen Beliefs und Fortsetzungen.
- Das Modell darf nicht auf den 571 bekannten River-Spots optimiert und dort zugleich bewertet werden.

## 6. Nahtstellen

### Wechsel mitten in einer Hand

Der empfohlene Normalfall:

- Wechsel nur am **River-Eintritt**, bevor Hero dort erstmals handelt.
- Der River-Experte übernimmt die komplette Resthand.
- Bei gegnerischer Off-Tree-Aktion:
  1. Action exakt kanonisieren.
  2. Beliefs mit der tatsächlich beobachteten Aktion aktualisieren.
  3. Entweder innerhalb des Experten neu lösen,
  4. oder auf `v5_continuation` mit den Hybrid-Beliefs wechseln.
- Niemals auf nacktes `PokerBot.decide`.

Wenn der Plan nach einem Prefix ausfällt, gilt:

\[
r_{H,\text{cont}}(h)
\propto
r_{H,\text{root}}(h)
\prod_j \pi_Z(a_j\mid h,H_j)
\]

Das ist H1-artige Fortsetzung. Ein byte-identisches v5 ist dann im Allgemeinen unmöglich; nur die v5-Entscheidungslogik kann mit den neuen Beliefs weiterlaufen.

### Wechsel zwischen Händen

Zwischen Händen gibt es keine Range-Naht. Trotzdem:

- Strategieversion bleibt für einen Messblock eingefroren.
- Keine Online-Auswahl anhand der bisherigen GTOW-Ergebnisse.
- Random Seeds und Policy-Fingerprint werden pro Hand geloggt.
- adaptive Opponent-Modelle bleiben gegen den Nash-Zielgegner aus.

## 7. Fallback-Kette

Die korrekte Kette lautet:

```text
A. Aktiver geschlossener River-Plan
B. v5_continuation mit den tatsächlich entstandenen Hybrid-Beliefs
C. produktive v5-Policy inklusive aller geshippten Guards
D. zeitbegrenzte, eingefrorene v5-Emergency-Policy inklusive Guards
E. legaler letzter Notfallzug, nur bei Enginefehler und als harter Alarm
```

Nicht zulässig:

```text
Planfehler -> nacktes bot.py
```

### Zusätzliche Regeln

- Jeder Solve trägt `(hand_id, public_root, solve_generation, policy_fingerprint)`.
- Ein Ergebnis mit falscher Generation wird verworfen.
- Nach Planinvalidierung kein stiller Wiedereinstieg.
- `except: pass` ist im Entscheidungsweg verboten.
- Jeder Fallback hat einen enumerierten Grundcode.
- `hand_not_in_range` ist kein reparierbarer Warnfall, sondern Domain-Failure.

## 8. Latenzbudget

**WAS ICH WEISS**

- Die bestehende Live-Kette hatte River-Kaltstarts von etwa 13,5 s wegen TexasSolver plus GPU-Guard.
- Die genannte harte Grenze liegt ungefähr bei 6 s.
- v10 lag bereits vor zusätzlichem H0-Fallback bei p99 10,15 s.

**Konkrete Regel, falls 6,0 s tatsächlich der äußere Timeout ist:**

- interner Gesamtdeadline: **5,5 s**,
- letzter Solverstart spätestens bei **5,0 s Restbudgetgrenze** beenden,
- mindestens **0,5 s** für Action-Translation, Fallback und Rückgabe reservieren,
- nur **ein** teurer River-Solve,
- Baseline-/Emergency-Aktion muss vor Ablauf der Reserve verfügbar sein,
- Freigabe nur bei p99 ≤ 5,5 s und Timeoutquote ohne degradierenden Fallback.

Die genauen Subbudgets dürfen erst nach Profiling festgelegt werden. Prozentuale Planung:

| Anteil | Zweck |
|---:|---|
| 10 % | State-/Range-Rekonstruktion, Legalisierung |
| 70–75 % | genau ein ausgewählter Solve |
| 10–15 % | Fortsetzungs-/Fallbackberechnung |
| 5–10 % | Sicherheitsreserve und Rückgabe |

**Nicht parallel TexasSolver und GPU auf demselben Root laufen lassen**, außer in einem Shadow-Audit, dessen Ergebnis nicht live gespielt wird.

| Architekturentscheidung | Erwartete GTOW-Wirkung | Kosten | Risiko | Billigster Falsifikationstest |
|---|---:|---:|---|---|
| Baseline zuerst bereithalten, danach Spezialist | direkt 0 bis +1; verhindert Timeoutkatastrophen | 2–3 Tage | Baselineberechnung verbraucht zu viel Budget | 40-Root-Latenzlauf mit erzwungenen Time-outs |
| Nur ein River-Solve statt TexasSolver+GPU | EV vermutlich −0,5 bis +1; große Latenzwirkung | 2–4 Tage | entfernt einen tatsächlich nützlichen Solver | fertiges B2-Protokoll auf 571 Entscheidungen plus 3 pargate-Läufe |
| Wechsel nur am River-Root | vermutlich besser als freie Umschaltung; 0 bis +2 relativ zum naiven Hybrid | 3–5 Tage | verpasst spätere Spezialfälle | K3-Vergleich Root-Ownership gegen Action-by-Action-Umschaltung |
| Vollständige v5-Emergency-Policy | direkt etwa 0, verhindert schwere Tails | 2–4 Tage | nicht wirklich v5-identisch | erzwungene Fehler an allen Übergängen; Aktion für jeden Zustand vorhanden |

---

## 1(e) Reihenfolge des Baus

## Stufe 0 – Mess- und Produktidentität schließen

### Änderungen

- GTOW-Adapter muss exakt denselben Wrapper wie das Produkt verwenden.
- Runtime-Fingerprint verpflichtend.
- `exploit=False`, Resolverstatus, Blueprint-Gate, Guard-Stack und Fallback-Version werden geloggt.
- Untrackierte `research/konsult_sol.py` vor Tagging klären.
- v5 taggen und Working Tree säubern.

### Gate

- A/A exakt 0.
- Fingerprint des Harnesses entspricht dem Produkt.
- Ein absichtlich deaktivierter Guard muss im Fingerprint und in der Aktionsspur sichtbar sein.
- Kein `kein_verdikt` durch Legalisation.

**Wirkung:** 0 bb/100 direkt; verhindert einen wertlosen GTOW-Anker.  
**Kosten:** 1–3 Tage.  
**Risiko:** entdeckt, dass frühere Anker nicht dieselbe Policy waren.  
**Billigster Falsifikationstest:** zehn geskriptete Zustände durch Server- und GTOW-Pfad schicken und Aktionen/Fingerprints byteweise vergleichen.

---

## Stufe 1 – v5 als explizit geschlossene Baseline kapseln

### Änderungen

- `V5ProductiveBaseline` implementieren.
- Alle Guards bleiben in der dokumentierten Reihenfolge.
- Emergency-Policy enthält ebenfalls die produktiven Schutzschichten.
- Silent exceptions entfernen.
- keine Verhaltensänderung beabsichtigt.

### Gate

- A/A exakt 0.
- Auf einem eingefrorenen Zustandskorpus identische Aktionen und Wahrscheinlichkeiten.
- Drei pargate-Läufe neutral.
- Fallback-Abdeckung 100 % auf synthetischen Legal-/Off-Tree-Fällen.

**Wirkung:** nominal 0; Tail-Risiko sinkt.  
**Kosten:** 3–5 Tage.  
**Risiko:** Wrapper-Reihenfolge verändert sich unbemerkt.  
**Falsifikation:** Golden-trace-Diff über alle aufgezeichneten Divergenzspots.

---

## Stufe 2 – River-Funnel und Shadow-Modus, noch keine Auswahl

### Änderungen

Für jede Live-/Spiegelhand loggen:

- River erreicht?
- Pot ≥ 15 bb?
- K1-Support vollständig?
- Plan möglich?
- Off-tree?
- vorhergesagte und reale Runtime?
- Planaktion versus v5-Aktion?
- jeweilige Aktionswahrscheinlichkeit?
- K3-/Solver-EV-Differenz, soweit offline verfügbar?

### Gate

- Basisrate pro 100 Hände mit CI.
- Supportfehler 0 im freigegebenen Domain.
- Keine handabhängige öffentliche Gate-Entscheidung.
- p99 innerhalb Budget oder Plan bleibt Shadow-only.

**Wirkung:** 0 direkt.  
**Kosten:** 2–4 Tage plus Laufzeit.  
**Risiko:** hoher Logging-Overhead.  
**Falsifikation:** Wenn planfähige Roots so selten sind, dass selbst der obere Pro-Trigger-EV weniger als etwa 1 bb/100 aggregiert, Zwitterpfad stoppen.

---

## Stufe 3 – H0-artiger River-Root-Owner

### Änderungen

- Öffentliche Auswahl am River-Eintritt.
- Plan übernimmt komplette Resthand, solange gültig.
- Bei Nichtverwendbarkeit unveränderte produktive v5.
- Kein Wiedereinstieg.

### Gate

- erzwungene Nahtfälle: keine nackte Basis.
- K3-BR gegen kompilierte Policy nicht schlechter als v5 innerhalb vorregistrierter Toleranz.
- H0 versus v5 in drei pargate-Läufen: CI-Untergrenze > −3 bb/100 gemäß bestehender Regel.
- p99 ≤ internes Deadlinebudget.
- Plan-v5-Root-EV-LCB positiv auf gehaltenen Roots.

**Wirkung:** **Vermutung 0 bis +2 bb/100 gegen GTOW**.  
**Kosten:** 4–7 Tage.  
**Risiko:** K1-Fehler macht On-Tree-Plan selbst falsch.  
**Falsifikation:** Oracle-Range gegen K1-Range austauschen; wenn die Planaktion häufig kippt oder die Root-EV-Differenz negativ wird, H0 nicht live bauen.

---

## Stufe 4 – H1-Fortsetzung

### Änderungen

- vollständige Propensity-Logs,
- Reach-Update unter Hybridpolitik,
- `v5_continuation` mit Hybrid-Beliefs,
- Joint-State, falls Planmodus persistent bleibt.

### Gate

- analytische Toy-Games exakt.
- Range-Masse nach jedem Prefix gegen brute-force Replay.
- H1 versus H0 an erzwungenen Nahtroots: positive LCB oder klare BR-Verbesserung.
- H1 versus v5 als eigentliche Produktfrage.

**Wirkung:** **Vermutung −0,5 bis +1 bb/100 zusätzlich**; primär Tail-/Exploitability-Schutz.  
**Kosten:** 5–10 Tage.  
**Risiko:** fehlerhafte Rekonstruktion verschlechtert trotz „korrekter“ Architektur.  
**Falsifikation:** Wenn H1 auf gehaltenen Nahtroots weder BR noch Root-EV gegenüber H0 verbessert, nicht shippen.

---

## Stufe 5 – Erst danach ein gelernter Arbiter

Nur wenn Stufe 3 oder 4 tatsächlich positive Root-EV-Differenzen erzeugt.

### Gate

- Split nach öffentlichen Root-Clustern.
- Kalibrierungs-LCB korrekt.
- Selektor schlägt einfache feste Pot-/Supportregel out of sample.
- kein Training auf GTOW-Ausgabe desselben Evaluationssatzes.

**Wirkung:** **Vermutung 0 bis +1 bb/100**.  
**Kosten:** 1–2 Wochen.  
**Risiko:** Overfitting an K3/TexasSolver statt GTOW.  
**Falsifikation:** Eine monotone Zweiregel-Baseline erreicht gleichen oder besseren Held-out-EV; dann kein Modell bauen.

---

## 1(f) Welche Bauteile ausdrücklich nicht hineingehören

## Kategorienfehler: nicht einmal HU-Experten

| Bauteil | Urteil |
|---|---|
| ICM-/Turnierschicht | Nicht in HU-Cash. Andere Utility-Funktion. |
| 6-max-Liga und `flat_guard` | Nicht in HU. Andere Spielerzahl und Informationsstruktur. |
| Kaggle-100-bb-Heuristikkette | Nicht in GTOW-200-bb. Anderer Stack und kein Deep-Blueprint. |
| K3 | Prüfstand, keine Spielpolicy. |
| K4 | Ledger/Fingerprint, keine Spielpolicy. |
| Range-Tracker/K1 | Belief-Infrastruktur, nicht als „Aktionsexperte“ behandeln. |

## Refutierte Teile: nicht standardmäßig integrieren

Ausgeschlossen:

- `opp_model`/Dirichlet-Exploit gegen Nash-Zielgegner,
- Frequenz-Matching,
- PURIFY,
- `RAISE_NARROW` im Resolver-ON-Modus,
- `AUDIT_FIX`,
- `no_limp_guard`,
- `r6_ecall`,
- fcpa-Policy-Netz,
- LLM-Gehirne,
- Bet-Translation-Angriffe,
- Prince-Takeover in 6-max,
- handabhängiges v9-Sampling in aktueller Form.

### Ist „im Spiegel refutiert“ allein ein Ausschlussgrund?

**Nein.** Der Spiegel ist nur eine Nichtverschlechterungsschranke gegen den Amtierenden. Ein Modul kann im Spiegel verlieren und gegen GTOW gewinnen, wenn es gezielt einen Fehler des Incumbents nicht mitträgt.

Aber daraus folgt nicht, dass jedes refutierte Modul rehabilitiert werden soll.

Es braucht mindestens:

1. eine mechanistische Zielhypothese,
2. positiven Aktions-EV auf gehaltenen GTOW-/Solver-Roots,
3. geschlossene Fortsetzung,
4. keine Verschlechterung der BR-Metrik,
5. vorregistriertes GTOW-Gesamtpaket.

### Konkrete Urteile

- **`r6_ecall`: ausschließen.** Der Spiegel zeigt Value-Folds; das ist ein plausibler generischer Fehler, kein bloßes Matchup-Artefakt.
- **`r6_button`: behalten.** Spiegel neutral, klarer Adversarbeweis, geringe strategische Komplexität.
- **`stackoff_bremse`: nicht in den Kernselektor aufnehmen, solange zu leise.** Erst Funnel/Basisrate.
- **Advisor-MLPs:** als Baselinekomponente behalten, aber nicht als Wahrheitsoracle für den Arbiter.
- **TexasSolver und GPU-CFR:** als alternative Backends testen, nicht beide ungeprüft seriell ausführen.
- **K1 aktuell nicht shippen:** Support-Leck und Größenagnostik sind ungelöste Policy-Semantikfehler.
- **K2 aktuell nicht shippen:** ohne korrekte Ranges und produktiven Off-Tree-Fallback ist der positive reine Planbefund unzureichend.
- **LLM-Brain-Reste vollständig aus dem Produktpfad entfernen oder hart separieren.** Sie erhöhen Angriffsfläche und Fingerprint-Unsicherheit ohne Zielwert.

| Ausschlussentscheidung | Erwartete GTOW-Wirkung | Kosten | Risiko | Billigster Falsifikationstest |
|---|---:|---:|---|---|
| Refutierte Exploit-/Frequenzmodule nicht integrieren | verhindert erwartbar negative Beiträge; grob mehrere bb/100 möglich | praktisch 0 | ein echter komplementärer Spezialfall wird übersehen | Offline-Aktions-EV auf gehaltenen GTOW-Roots; nur bei positivem LCB neu öffnen |
| ICM/6-max/Kaggle strikt dispatchen | 0 im korrekten HU-Pfad; verhindert Kategorienfehler | 1–2 Tage | Code-Duplikation | Fingerprint-/Importtest je Spielmodus |
| LLM-Pfade aus HU-Produkt entfernen | vermutlich 0 bis positiv | 1 Tag | Verlust eines Diagnosewerkzeugs | LLM nur als separates Tool erhalten, nicht importieren |

---

## 1(g) Wie misst man den Zwitter?

Der Auswahlwert muss separat von Elternwert und Nahtwert gemessen werden.

## Messzerlegung

Für jeden gehaltenen öffentlichen Root werden vier Policies ausgewertet:

1. **P:** produktive v5.
2. **E:** Experte übernimmt geschlossen.
3. **Z-oracle:** wählt im Nachhinein den besseren Experten – nur theoretische Obergrenze.
4. **Z-selector:** tatsächlich eingesetzter Selektor.

Daraus:

### Expertenvorteil

\[
\Delta_E = EV(E)-EV(P)
\]

### Selektor-Regret

\[
R_{\text{sel}}
=
EV(Z_{\text{oracle}})-EV(Z_{\text{selector}})
\]

### Nahtverlust

\[
L_{\text{seam}}
=
EV(E_{\text{geschlossen}})
-
EV(E\rightarrow \text{Fallback})
\]

### Gesamtbeitrag

\[
\Delta_Z
=
\text{Triggerhäufigkeit}
\times
(\Delta_E-R_{\text{sel}}-L_{\text{seam}})
\]

Alle Terme müssen dieselben Einheiten, Root-Gewichte und Fortsetzungen haben.

## Kanal A – K3/exakte Best Response

K3 ist der wichtigste Entwicklungsprüfstand, sofern er wirklich die **kompilierte feste Gesamtpolitik** sieht.

Messen:

- Exploitability v5 versus Zwitter.
- BR-Wert nach Rootfamilie.
- BR-Ausnutzung des Selektors:
  - Expertentells,
  - Sizingtells,
  - Off-Tree-Routen,
  - Timeout-Routen.
- private Randomisierung und persistente Modi müssen Teil der Policy sein.

Freigabe:

- Zwitter-BR nicht schlechter als v5 innerhalb vorregistrierter Toleranz,
- kein Rootcluster mit großer Verschlechterung, auch wenn der Mittelwert neutral ist.

## Kanal B – gepaarter Spiegel

Zweck:

- Integrationsregression,
- grobe Nichtverschlechterung,
- Trigger-/Naht-Funnel,
- Runtime und Determinismus.

Nicht als Beweis verwenden:

- dass der Selektor GTOW besser auswählt,
- dass niedrige Exploitability vorliegt,
- dass stille Module gut sind.

Wichtig: Armspezifische Zufallsstreams müssen so gekoppelt sein, dass Unterschiede von der Policy kommen und nicht vom `hand_id`-Fehler.

## Kanal C – Entscheidungsbasierter Resolver-/Root-Prüfstand

Das ist der fehlende billige Kanal zwischen Spiegel und GTOW.

Dataset:

- neue, eingefrorene öffentliche Roots,
- geschichtet nach Straße, Pot, SPR, Sizing-Abstand, Boardklasse und Supportqualität,
- keine Wiederverwendung der bekannten 571 Spots als finale Bewertung,
- Baseline- und Expertenaktion unter identischen Beliefs,
- Werte für die tatsächlich ausgeführte Fortsetzung.

Dieser Kanal bepreist Auswahl und Naht, nicht nur Komponenten.

## Kanal D – GTOW

Nur Gesamtpakete:

- v5 exakt produktiv,
- Zwitter exakt produktiv,
- ggf. Resolver-Ersetzung als eigenes Paket.

Kein GTOW-Budget für einzelne dünne Guards.

### Empfohlenes Protokoll

1. Erst v5-Anker mit Fingerprint.
2. Danach Zwitter gegen denselben freigegebenen v5-Tag.
3. BAAB/ABBA-Chunks, Transportfehler separat.
4. Vorregistrierte Auswertung ohne zwischenzeitliche Selektoränderung.
5. Keine Rückoptimierung auf einzelne verlorene GTOW-Hände vor Abschluss.

## Overfitting-Schutz

- Split nach Rootfamilien, nicht zufällig nach Händen.
- Mindestens ein vollständig unangetasteter Testblock.
- GTOW ist Bestätigung, kein Training.
- Selektorfeatures vor dem Test einfrieren.
- Einfache Selektorregel als Pflichtbaseline.
- Mehrfachtests berücksichtigen: nicht aus zwanzig Gattern den besten Report picken.
- Action-EV statt AIVAT-Zellen als Entwicklungslabel.
- Artefakte append-only mit Commit und Fingerprint.

| Messmaßnahme | Erwartete GTOW-Wirkung | Kosten | Risiko | Billigster Falsifikationstest |
|---|---:|---:|---|---|
| Root-basierter Entscheidungsprüfstand | indirekt wahrscheinlich größter Entwicklungshebel; 0 direkt | 3–7 Tage | Oracle-Mismatch zu GTOW | Auf alten GTOW-Händen prüfen, ob Root-EV-Rangfolge tatsächliche Fehlerklassen trennt |
| K3 auf kompilierte Policy | 0 direkt; begrenzt Exploitabilityregression | vorhandener Prüfstand plus Integration | Action-Abstraktion macht BR-Zahl optimistisch | kleine exakt enumerierbare Toy-Games |
| GTOW nur für Gesamtpakete | bessere Budgeteffizienz, 0 direkt | 8–9 h je 2.500 Hände | breites CI | Stop, wenn Fingerprint/Legalisierung nicht vollständig ist |

---

## 1(h) Vier-Wochen-Bauskizze

## Woche 1 – Wahrheit über Produkt und Baseline

### Bauen

- GTOW-Adapter auf denselben Wrapperpfad wie Server/pargate.
- Runtime-Fingerprint und append-only Ledger erzwingen.
- `V5ProductiveBaseline` kapseln.
- hardcodiertes River-Sizing, stille Exceptions und `_river_spot_und_frage=None` zunächst instrumentieren, nicht blind ändern.
- A/A und Golden-Traces.

### Gate am Ende der Woche

- A/A exakt 0.
- Produkt-/GTOW-Fingerprint gleich.
- 100 % legaler Output auf geskriptetem Off-Tree-Korpus.
- Drei neutrale pargate-Läufe für die reine Kapselung.
- v5-GTOW-Smoke nur, wenn alle Artefakte vollständig sind.

### Abbruch

- Wenn Server, pargate und GTOW weiterhin verschiedene Policies ausführen: keine strategische Arbeit in Woche 2.

---

## Woche 2 – Shadow-Funnel und bestehende River-Defekte

### Bauen

- vollständiger River-Funnel.
- Plan/v5 parallel nur im Shadow.
- Oracle-Range versus K1-Range auf den vorhandenen 64 Roots.
- fertigen A/B-Test „GPU ersetzt TexasSolver-River“ ausführen.
- Bet-Size-Kommentar/Implementierung durch Aktions-EV klären.
- K1-Supportfehler nicht durch Einfügen der realen Hand reparieren.

### Gates

- planfähige River-Basisrate mit CI.
- Support 100 % im freigegebenen Domain.
- p99 des vorgesehenen Livepfads ≤ internes Budget.
- Shadow-Plan hat positiven Root-EV-LCB gegenüber v5.
- kein doppelter Solver im geplanten Pfad.

### Abbruch

- Wenn Plan-v5-EV auf Oracle-Ranges nicht positiv ist: v10.1 stoppen.
- Wenn die aggregierte obere Potenzialgrenze unter etwa 1 bb/100 liegt: kein Hybridbau in Woche 3.

---

## Woche 3 – Minimaler H0-Root-Owner

### Bauen

- öffentliches River-Root-Gating.
- kompletter produktiver v5-Fallback.
- Zustandsautomat ohne Wiedereinstieg.
- erzwungene Off-Tree-/Timeout-/Stale-Thread-Tests.

### Gates

- A/A exakt 0.
- keine Route auf nacktes `bot.py`.
- K3-BR nicht schlechter.
- drei pargate-Läufe mit CI-Untergrenze > −3.
- Latenzgate bestanden.
- Plan-Only, Fallback-Only und Seam-Only getrennt ausgewiesen.

### Abbruch

- ein einziger ungeklärter degradierter Fallback,
- p99 über Deadline,
- negative K3-LCB,
- mehr als vereinzelte `hand_not_in_range` im behaupteten Domain.

---

## Woche 4 – H1 nur bei bestandenem H0; sonst Champion reparieren und ankern

### Wenn H0 grün

- Prefix-Propensities und Hybrid-Reach.
- H1 versus H0 auf erzwungenen Nahtroots.
- limitierter Smoke.
- GTOW-Paket nur bei positiver held-out Root-LCB und bestandener BR-Schranke.

### Wenn H0 nicht grün

- H1 nicht bauen.
- Champion-Defekte beheben:
  - River-Sizing,
  - silent exceptions,
  - Doppel-Resolver,
  - Range-Support/Fallback.
- exakten v5-Anker fahren.

### Vier-Wochen-Erwartung

**WAS ICH VERMUTE**

- Realistischer Stärkegewinn eines erfolgreichen Minimalhybrids: **0 bis +3 bb/100 gegen GTOW**.
- Ein vollständiger „Alles-Zwitter“ ist in vier Wochen unrealistisch.
- Der größte sichere Ertrag der vier Wochen ist möglicherweise nicht neue Stärke, sondern ein erstmals vertrauenswürdiger v5-Anker plus Entfernung eines River-Latenz-/Sizingdefekts.

---

# Frage 2 – Die Flaggschiff-Version verbessern

## 2(a) Woher kommt der Restverlust strukturell?

## WAS ICH WEISS

Die genannte Straßenzerlegung von ungefähr

- Flop −8,3,
- River −8,6,
- Turn −1,6,
- Preflop −1,6

beschreibt den historischen Anker, nicht gesichert v5.

Außerdem sind AIVAT-Straßenzellen **Realisierungsattribution**, keine kausale Entscheidungsattribution. Der dokumentierte −121-bb-Zellenbefund bei nur ungefähr +0,6 bb Aktions-EV-Differenz zeigt das Problem deutlich.

Belastbarer ist:

- 87 % des historischen Verlusts wurden dem River zugerechnet.
- Neun tiefe River-Calls erzeugten 59 % des v4-Verlusts.
- Solver-Audit:
  - Check/Fold weitgehend konform,
  - Bets schwächste Klasse,
  - Desaster-Calls waren häufig klare Solver-Folds.
- Der gemessene Solver-EV-Fehler von ungefähr 6,9 bb/100 betrifft nur River. Flop und Turn sind in dieser Form unvermessen.

## Strukturelle Ursachen

### River

1. **Mehrere nicht kohärente Entscheidungsschichten**
   - TexasSolver,
   - Range-Tracker,
   - Advisor,
   - Heuristik,
   - `river_wert_bremse`,
   - GPU-Guard.

   Diese Schichten teilen nicht zwingend dieselbe Range, Aktionsabstraktion oder Fortsetzung.

2. **Doppelte Resolverarbeit**
   TexasSolver und GPU-Guard können nacheinander rechnen. Das erzeugt 13,5-s-Kaltstarts und möglicherweise widersprüchliche Policies.

3. **Offener Sizing-Defekt**
   `river_gpu_guard` hardcodet `int(0.75*pot)` entgegen Kommentar. Das ist ein realer Championdefekt, nicht bloß ein Kandidatenproblem.

4. **Silent failure**
   `except: pass` und `None` auf stillen Run-outs machen die ausgeführte Policy unsichtbar.

5. **Tiefe Pötte dominieren**
   Bei 200 bb erzeugen wenige fehlerhafte große Calls oder Bets enorme bb/100-Beiträge.

### Flop

1. Kein produktiver GPU-Flop-Pfad.
2. Advisor/Floor müssen aus begrenzten Features und unvollkommenen Ranges arbeiten.
3. Fehler auf dem Flop propagieren in alle späteren Ranges.
4. Der vorhandene ISO-Cache ist aus; dadurch wird vorhandene Solverarbeit nicht effizient wiederverwendet.
5. Der Flopverlust ist bisher keine Aktions-EV-Messung. Blindes Aktivieren des Flop-Resolvers wäre verfrüht.

### Turn

Der Turn ist wahrscheinlich nicht der Haupthebel. Drei GPU-Eingriffe in 3.904 Entscheidungen zeigen primär einen zu engen Funnel. Der dokumentierte 0,65-Sizing-Tell ist als messbarer Exploit refutiert. Deshalb ist „Turn-Size-Entkopplung = wichtigster Einzelfix“ derzeit nicht haltbar.

### Preflop

Bei 200 bb läuft der starke Blueprint. Deshalb ist ein kleiner Restverlust plausibel:

- Off-tree Sizings,
- Re-Raises außerhalb Blueprint,
- grober Klassenprior,
- seltene Stackoffs.

Die Stackoff-Zelle kann pro Trigger groß sein, aber die Gesamtwirkung bleibt wegen der Seltenheit wahrscheinlich klein.

---

## 2(b) Priorisierte Eingriffe an der bestehenden Architektur

Die Werte sind **Planungsschätzungen**, keine Projektmessungen.

| Rang | Eingriff | Erwartete Wirkung gegen GTOW | Aufwand | Risiko | Billigster Falsifikationstest |
|---:|---|---:|---:|---|---|
| 0 | GTOW-Adapter exakt auf v5-Wrapper + Fingerprint | 0 bb/100 direkt | 1–3 Tage | entdeckt unbrauchbare historische Vergleiche | Golden-State-Diff Server vs GTOW |
| 1 | `river_gpu_guard`: hartcodiertes 0,75-Pot-Sizing, `None`-Run-outs und `except: pass` beheben | **+0,5 bis +3 bb/100** | 2–5 Tage | vermeintlicher Fix verschlechtert Action-Translation | 571er Replay mit handweisem Aktions-EV; nur klare positive LCB übernehmen |
| 2 | „GPU ersetzt TexasSolver-River“ statt Doppel-Resolver | **−0,5 bis +1 bb/100**, aber große Latenzwirkung | 2–4 Tage | TexasSolver war in Teilroots besser | fertiges B2-Protokoll, dann drei pargate-Läufe |
| 3 | River-Call-/Bet-Funnel nach Aktions-EV statt AIVAT-Zelle kalibrieren | **+1 bis +4 bb/100** | 4–8 Tage | bekannte 571 Spots sind überoptimiert | neue held-out River-Roots; klare Solver-Widersprüche müssen out of sample bestehen |
| 4 | `hand_not_in_range` und Preflop-Prior-Support im bestehenden Solverpfad schließen | **+0,3 bis +2 bb/100** | 3–7 Tage | Range wird künstlich geglättet und schlechter | Oracle-Prior-Ablation; echte Hand niemals nachträglich einfügen |
| 5 | vorhandenen Flop-ISO-Cache als Offline-Prüf-/Cachepfad aktivieren, nicht sofort als Live-Override | zunächst 0; bei positiver Prüfung später **+1 bis +4 bb/100** | 1–2 Wochen | Flop-Zellverlust ist Realisierung, kein Aktionsfehler | 200–500 neue geschichtete Flop-Roots mit Action-EV |
| 6 | `stackoff_bremse` nur nach Funnel aktivieren | wahrscheinlich **0 bis +0,5 bb/100** | 1–2 Tage | stiller Kanal, Overfitting an eine Zelle | Triggerzahl pro 10.000 Hände und gewichtetes EV-Ceiling |
| 7 | Turn-GPU-/Turn-Size-Arbeit zurückstellen | erwartet derzeit **<1 bb/100** | — | echter Turnhebel wird verzögert | Funnel zuerst; wenn relevante Coverage entsteht, neu priorisieren |

### Warum Rang 1 vor Flop?

Weil dort gleichzeitig vorliegen:

- ein konkreter implementierter Defekt,
- historisch dominanter Riververlust,
- tiefe Potwirkung,
- vorhandener Auditkorpus,
- geringe Baukosten.

Die Flopblutung könnte größer sein, ist aber als Aktionsfehler noch nicht bepreist.

---

## 2(c) Wo wird Aufwand verschwendet?

Das Team sollte Folgendes einstellen:

1. **Keine weitere Schicht in die Wrapper-Kette setzen, ohne die Gesamtpolitik neu zu vermessen.** v8 und v10 zeigen, warum.
2. **Keine Optimierung auf die bekannten 571 River-Spots als finale Evidenz.** Der Kanal ist weitgehend verbraucht.
3. **Kein Frequenz-Matching.** Dreifach widerlegt; Frequenzähnlichkeit ist weder EV noch Exploitability.
4. **Kein Exploit-Overlay gegen GTOW.** Ziel ist ein Re-Solver/Nash-naher Gegner.
5. **Keine LLM-/SFT-/GRPO-Arbeit für den Wettbewerbsbot.** Die gemessenen Resultate sind klar unterlegen.
6. **Keine Kaggle-Eichung auf GTOW und keine Interpretation des Kaggle-v9-Nullsignals als Stärke.** Bei 100 bb feuert strukturell ein anderer Bot; +0,0 über 100 Decks deutet eher auf keine Divergenz.
7. **Keine Turn-Size-Entkopplung als „wichtigsten Fix“ behandeln.** Der behauptete messbare Exploit wurde refutiert.
8. **Keine weiteren dünnen Guards ohne Funnel.** Ein Trigger pro 400 Hände ist mit dem verfügbaren GTOW-Budget nicht separat bepreisbar.
9. **Kein gleichzeitiger TexasSolver- und GPU-River-Solve im Produkt.**
10. **Keine v10.1-Implementierung, bevor K1 auf Oracle-Ranges positiven Planwert zeigt.**
11. **Keine weiteren Selfplay-Replikate als Ersatz für einen v5-Anker.** Der Spiegel misst zunehmend die falsche Fähigkeit.
12. **Keine Strategieänderung zusammen mit fp16-/Runtime-Änderung.** Sonst ist die Ursache nicht identifizierbar.

---

## 2(d) Optimale Kombination aus Stärke und Handvolumen

Mit dem hausinternen Koeffizienten

\[
SE \approx \frac{214}{\sqrt n}
\]

ist die Leaderboard-Untergrenze ungefähr:

\[
LCB_{95}
=
\mu - 1{,}96\frac{214}{\sqrt n}
\]

Für Top 5 nach der angenommenen Grenze gilt:

\[
\mu - 1{,}96\frac{214}{\sqrt n} > -14{,}8
\]

oder:

\[
n >
\left(
\frac{1{,}96\cdot214}{\mu+14{,}8}
\right)^2
\]

nur falls \(\mu>-14{,}8\).

| Wahrer Mittelwert | Benötigte Hände ungefähr |
|---:|---:|
| −14 | 275.000 |
| −13 | 54.000 |
| −12 | 22.500 |
| −11 | 12.200 |
| −10 | 7.700 |

### Folgerung

- Liegt der wahre Mittelwert bei −15, hilft **kein endliches Volumen**.
- Bei −13 ist Top 5 prinzipiell möglich, aber teuer und fragil.
- Bei −11 wird das Ziel mit ungefähr 10.000–12.000 Händen realistisch.
- Ein Stärkegewinn von zwei bb/100 kann das notwendige Volumen um einen Faktor von zwei bis vier reduzieren.

### Optimale Strategie

1. **Zuerst sicherstellen, dass \(\mu>-14,8\).**
2. Entwicklungsziel nicht −13, sondern ungefähr **−11 bis −12**.
3. Erst dann Volumen akkumulieren.
4. Während eines Leaderboard-Laufs Policy einfrieren; keine adaptive Nachoptimierung.
5. Nicht 50.000 Hände auf einen vermutlich −16-Bot verschwenden.

**WAS GEMESSEN WERDEN MUSS:** Der wahre v5-Mittelwert. Ohne diesen Wert ist jede Volumenplanung Spekulation.

---

# Frage 3 – Potenzial von v10.1, H0 → H1

## 3(a) Realistisches Potenzial

## WAS ICH WEISS

- v9s +3,6 bis +5,4 bb/100 sind eine vorregistrierte Hypothese, keine Messung.
- v10 G5 war neutral mit sehr breitem Intervall.
- Die reinen Plan-Decks waren positiv.
- Die katastrophalen Decks lagen auf Off-Tree-Fallbacks zur nackten Basis.
- K1 verfehlte das TV-Gate stark und verlor in 21/64 Fällen den Support.
- v8 als früherer naiver Hybrid war ungefähr +2,3 ± 2,4 im Spiegel und wurde wegen Sättigung gedroppt.
- Die Basisrate planfähiger River-Pötte pro 100 Hände fehlt.

## WAS ICH VERMUTE

Relativ zu produktivem v5:

- **H0:** mediane Erwartung ungefähr **+1 bb/100**, grober plausibler Bereich **−2 bis +4 bb/100**.
- **H1 zusätzlich zu H0:** ungefähr **−0,5 bis +1 bb/100**.
- **H1 insgesamt gegenüber v5:** grob **−2 bis +4,5 bb/100**.

Diese Unsicherheit ist bewusst breit. Ohne Triggerbasisrate lässt sich nicht einmal die Größenordnung sauber aggregieren:

\[
\Delta bb/100
=
\frac{\text{planfähige Roots}}{100\ \text{Hände}}
\times
\Delta EV_{\text{pro Root}}
-
\text{Naht-/Timeoutkosten}
\]

Die früheren +3,6 bis +5,4 dürfen nicht als Prior für H0/H1 übernommen werden, weil sie weder K1-Fehler noch Fallback- und Nahtkosten sauber enthalten.

---

## 3(b) Ist v10.1 der richtige nächste Build?

**Nicht als nächster Strength-Build.**

Der nächste Schritt sollte ein **No-/Low-Code-Falsifikationstest** sein:

1. K1-Range auf den vorhandenen Roots durch eine Oracle-/Replay-Range ersetzen.
2. K2 mit beiden Ranges lösen.
3. Planaktionen, Mischungen und Aktions-EV gegen v5 vergleichen.
4. planfähige Rootbasisrate messen.
5. Runtime eines Pfades mit genau einem Resolver messen.

Erst wenn dieser Test positiv ist, ist ein minimaler H0-Root-Owner sinnvoll.

### Warum H0 allein den Hauptfehler nicht behebt

H0 repariert den schlechten Fallback, aber nicht:

- falsche On-Tree-Hero-Range,
- Größenagnostik,
- Support-Lecks,
- Action-Translation,
- p99-Latenz,
- fehlende Subgame-Sicherheit.

Ein sauberer Fallback kann einen schlechten Plan nur seltener schädlich machen; er macht ihn nicht gut.

### Empfehlung

| Empfehlung | Erwartete GTOW-Wirkung | Kosten | Risiko | Billigster Falsifikationstest |
|---|---:|---:|---|---|
| v10.1 noch nicht produktiv bauen; zuerst Oracle-Range-Ablation | 0 direkt, spart potenziell Wochen | 1–3 Tage | Oracle nicht identisch zu Live-Belief | vorhandene 64 Roots neu bewerten |
| Bei positivem Test nur H0-Root-Owner bauen | 0 bis +2 bb/100 | 4–7 Tage | On-Tree-Plan bleibt falsch | held-out Root-EV und K3-BR |
| H1 erst bei gemessenem Nahtproblem | −0,5 bis +1 zusätzlich | 5–10 Tage | hohe Komplexität ohne Stärkegewinn | erzwungene H1-vs-H0-Nahtablation |

---

## 3(c) Konstruktionsfehler in H0/H1

### H0

1. **„Unverändertes v5 nach Plan-Prefix“ ist semantisch unmöglich.**  
   Nach einer Planaktion ist die eigene Reach-Verteilung nicht mehr die v5-Reach. Man kann die v5-Entscheidungslogik verwenden, aber nicht behaupten, dieselbe Policy fortzusetzen.

2. **Fallback pro Entscheidung kann Flattern erzeugen.**  
   Plan → v5 → Plan ist verboten. Der Zustandsautomat muss Ownership festhalten.

3. **H0 kann weiter doppelt rechnen.**  
   Wenn K2 ausfällt und danach vollständiges v5 inklusive TexasSolver und GPU startet, steigt die Latenz über v10 hinaus.

4. **On-Tree-K1 bleibt falsch.**  
   H0 repariert nur die degradierende Route.

5. **Timeout-Selektion ist strategisch korreliert.**  
   Schwierige Boards fallen häufiger zurück. Das ist Teil der Policy und kann ein Tell erzeugen.

### H1

1. **Nur Heros Range zu rekonstruieren reicht nicht.**  
   Villains Range muss ebenfalls entlang der beobachteten Aktionen und des verwendeten Gegner-/Blueprintmodells fortgeschrieben werden.

2. **Das Ledger braucht vollständige Propensities.**  
   Die tatsächlich gewählte Aktion allein reicht nicht.

3. **Selektorwahrscheinlichkeiten gehören in die Reach.**  
   Wenn nur einige Hände in den Plan gehen, muss \(q_{\text{Plan}}(h)\) multipliziert werden.

4. **Persistenter Planmodus verlangt \(r(h,k)\).**  
   Marginalisierung über Hände allein verliert Korrelationen zwischen Hand und Fortsetzung.

5. **Action-Translation gehört in die Policy.**  
   Wenn ein Solver 0,66 Pot will und die Engine 0,75 Pot ausführt, muss die Wahrscheinlichkeit der tatsächlich ausgeführten Aktion geloggt und bewertet werden.

6. **Support darf nicht mit der echten Hand repariert werden.**
7. **Stale Solvergebnisse müssen über Generationen ausgeschlossen werden.**
8. **H1 ist noch kein Safe Subgame Solve.**  
   Range-Konsistenz verhindert einen Modellfehler, garantiert aber keine Nichtverschlechterung der Exploitability.
9. **Private Randomisierung muss reproduzierbar, aber nicht strategisch unbeabsichtigt persistent sein.**
10. **Die Baseline muss als geschlossene Emergency-Policy rechtzeitig verfügbar sein.**

---

## 3(d) Billigste Widerlegung vor dem Bau

Der billigste starke Test ist kein weiterer Zufallsdeck-Spiegel.

## Test: Oracle-Range × Planwert × Basisrate

Auf dem vorhandenen Rootkorpus:

1. Rekonstruiere eine bestmögliche Hero-Root-Range ohne echte Holecard-Injektion.
2. Löse K2 einmal mit K1 und einmal mit Oracle-Range.
3. Vergleiche:
   - Support,
   - TV,
   - gewählte Aktion,
   - Mischungsverteilung,
   - Root-EV gegen dieselbe Villain-Range,
   - v5-Root-EV.
4. Nutze K3 für die vollständige Planpolitik.
5. Multipliziere den gehaltenen Pro-Root-Vorteil mit der live gemessenen Triggerbasisrate.
6. Ziehe gemessenen Naht- und Timeoutverlust ab.

### Stopkriterien

v10.1 stoppen, wenn eines gilt:

- Support nicht vollständig im behaupteten Domain.
- Plan-v5-EV-LCB auf Oracle-Ranges ≤ 0.
- positiver Planwert verschwindet beim Split nach öffentlichen Rootfamilien.
- K3-BR wird schlechter.
- p99 überschreitet internes Deadlinebudget.
- aggregierte obere Potenzialgrenze liegt unter ungefähr 1 bb/100.
- der Plan kippt bei Oracle-Range häufig auf andere Aktionsklassen; dann ist K1 kein harmloser Frequenzfehler.

Der bestehende G3-TV-Schwellenwert darf nicht einfach wegdefiniert werden. Falls TV als Gate zu streng sein sollte, muss er durch ein **aktions-EV-basiertes Gate** ersetzt werden, nicht durch „die Aktion sah trotzdem plausibel aus“.

---

## 3(e) Verhältnis zum Zwitter aus Frage 1

**v10.1 ist ein Spezialfall des korrekten Zwitters:**

- Baselineexperte: v5.
- Spezialist: K2-River-Plan.
- Belief-Modul: K1 beziehungsweise dessen reparierter Nachfolger.
- Prüfstand: K3.
- Ledger: K4.
- Selektor: öffentlicher River-Domain-Gate.
- H0: Baseline-Fallback.
- H1: range-konsistente Fortsetzung.

Es sind nur dann zwei verschiedene Dinge, wenn „Zwitter“ weiterhin als freie per-Entscheidung-Komponentenauktion verstanden wird. Diese breite Idee lehne ich ab. Der saubere Zwitter ist genau die verallgemeinerte Form eines korrekt gebauten H1.

---

# Übergreifende Prioritäten mit Wirkung, Kosten und Widerlegung

| Maßnahme | Erwartete Wirkung gegen GTOW | Rechen-/Bauaufwand | Hauptrisiko | Billigster Widerlegungstest |
|---|---:|---:|---|---|
| Exakten v5-Produktpfad im GTOW-Harness herstellen | 0 direkt | 1–3 Tage; danach 8–9 h je 2.500 Hände | zeigt, dass heutige Annahmen falsch sind | Golden-State-/Fingerprint-Diff |
| Champion-River-Sizing und stille Fehler beheben | +0,5 bis +3 | 2–5 Tage | Übersetzung verschlechtert Mischungen | 571er Replay plus neue held-out Roots |
| Doppel-Resolver entfernen | −0,5 bis +1 EV; starke Latenzverbesserung | 2–4 Tage | falschen Solver entfernt | vorhandenes B2-Protokoll |
| Root-basierter v5/K2-Shadow | 0 direkt | 2–4 Tage | Oracle-Mismatch | 64-Root-Ablation |
| Minimaler öffentlicher H0-Root-Owner | 0 bis +2 | 4–7 Tage | K1-On-Tree-Fehler | K3 + held-out Root-EV |
| H1-Range-Fortsetzung | −0,5 bis +1 zusätzlich | 5–10 Tage | hoher Nahtcode ohne Stärke | erzwungene Nahtablation |
| Flop-ISO-Cache als Offline-Prüfstand | später +1 bis +4 möglich | 1–2 Wochen | Flopverlust falsch attribuiert | neue geschichtete Flop-Roots |
| Mehr Selfplay ohne neuen Zielkanal | nahe 0 | laufend teuer | optimiert falsche Achse | Resultate korrelieren nicht mit Root-EV/GTOW |

---

# DIE DREI DINGE, DIE ICH ZUERST TUN WÜRDE

1. **Den GTOW-Adapter auf den exakt produktiven v5-Wrapperpfad mit Runtime-Fingerprint bringen und v5 ankern**, weil jede Stärke- und Volumenentscheidung ohne diesen Wert spekulativ ist.
2. **Den bestehenden Riverpfad reparieren und den vorregistrierten Test „GPU ersetzt TexasSolver-River“ ausführen**, weil hardcodiertes Sizing, stille Fehler und Doppel-Resolver gleichzeitig Stärke, Beobachtbarkeit und Latenz beschädigen.
3. **K2 vor jedem H0/H1-Code auf Oracle-Ranges gegen v5 bewerten und mit der live gemessenen Triggerbasisrate gewichten**, weil dieser billige Test v10.1 vollständig widerlegen kann, bevor weitere Nahtarchitektur gebaut wird.

# WORIN SICH DAS TEAM MEINER EINSCHÄTZUNG NACH IRRT

1. **„Mehr gute Bauteile ergeben einen besseren Bot“ ist falsch.** Mehr Bauteile ergeben mehr Nähte; ohne gemeinsame Ranges und Fortsetzungen steigt die Ausbeutbarkeit leicht.
2. **v5 liegt nicht gemessen bei −21 bb/100.** Der Wert gehört v4/r6_button, und die Selfplay-Inkremente sind nicht additiv oder GTOW-übertragbar.
3. **H0 repariert v10 nicht vollständig.** Es behebt den nackten Fallback, aber nicht die falschen On-Tree-Ranges, Support-Lecks oder Latenz.
4. **Handabhängige Auswahl ist nicht grundsätzlich spieltheoretisch verboten.** Verboten beziehungsweise falsch ist, sie zu verwenden und danach die dadurch entstandene Range-Selektion zu ignorieren.
5. **Range-Konsistenz ist notwendig, aber keine Subgame-Sicherheitsgarantie.**
6. **Der Spiegel kann Integration refutieren, aber GTOW-Stärke nicht bestätigen.**
7. **Die Flop-/River-AIVAT-Zerlegung ist keine kausale Fehlerrechnung.** Priorisierung muss über Aktions-EVs erfolgen.
8. **Turn-Size-Entkopplung ist derzeit nicht der wichtigste Einzelfix.** Der behauptete messbare Sizing-Exploit wurde im Repo selbst refutiert.
9. **Kaggle ist nicht derselbe Botkanal.** Bei 100 bb feuert der Deep-Blueprint nicht.
10. **Der universelle Zwitter ist kein Vier-Wochen-Weg zu Top 5.** Ein enger River-Hybrid plus Championreparatur ist realistisch; „alles integrieren“ nicht.

# WAS MIR AN INFORMATION GEFEHLT HAT

1. Die **Basisrate planfähiger River-Roots pro 100 GTOW-/HU-200-bb-Hände**.
2. Ein sauberer **v5-GTOW-Anker** mit geprüftem Wrapper-, Resolver- und Guard-Fingerprint.
3. Die exakte äußere **GTOW-Entscheidungsdeadline** und ob 6 s hart oder nur projektintern sind.
4. Rohdaten dazu, wie oft `river_gpu_guard` in v5 tatsächlich feuert, ausfällt, `None` erhält oder auf das hardcodierte Sizing übersetzt.
5. Root-EV-Vergleiche von K2 gegen v5 unter **Oracle-Hero-Ranges**.
6. Eine vollständige Beschreibung, ob K3 alle Sizings, Time-outs, Randomisierung und Fallbacks der kompilierten Policy modelliert.
7. Der aktuelle Resolver-AN/AUS-Effekt des exakt produktiven v5.
8. Ob bestehende GTOW-Boardeinträge überschrieben oder nur neue Einträge angelegt werden können.
9. Eine aufgelöste Nacht-1-Zahl und ein geprüfter Fingerprint des Nacht-2-Ankers.
10. Eine belastbare Messung des tatsächlichen Varianzkoeffizienten des aktuellen GTOW-Harnesses statt nur des historischen \(c=214\).
