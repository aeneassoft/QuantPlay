# AIVAT fuer den lokalen Kaggle-HU-Kanal — Entwurf nach Gegenpruefung (2026-09-10)

> Entstanden aus der User-Frage „Koennen wir fuer den Kaggle-Endpunkt nicht ein AIVAT entwickeln?".
> Drei Recherche-Agenten (Theorie / Repo-Inventar / Varianzstruktur), ein Entwurf, DREI unabhaengige
> Widerlegungsversuche (Erwartungstreue, Wechselwirkung mit der Paarung, Baubarkeit), dann diese Fassung.
> **Nichts davon ist gebaut.** Kanal und Instrumente: [`KAGGLE_ARENA.md`](KAGGLE_ARENA.md).
>
> **Anmerkung zur Eskalation in Abschnitt 0:** die dort gemeldeten laufenden `console_solver.exe`- und
> `python.exe`-Prozesse waren die eigenen Hintergrund-Messlaeufe dieser Sitzung (v9-Lauf, v10-H0-Lauf), KEINE
> zweite Sitzung. Der Hinweis, dass HEAD waehrend der Analyse wanderte, stimmt dagegen: die deal-Marke im
> Adapter kam mitten in den Lauf hinein, und die Referenzzahlen von 300 Decks stammen von davor.

# Schätzer für den lokalen Kaggle-HU-Kanal — REVISION 2 (nach drei Angriffen)

**Stand: HEAD `d22d400` (2026-09-10 01:59), Working Tree sauber.** Alle Zeilenangaben unten sind **an diesem HEAD nachgeprüft** (die Zitat-Hygiene war in Rev. 1 defekt — A1/A2/A3 haben das unabhängig festgestellt).

---

## 0. ESKALATION ZUERST — nichts wird gebaut, bevor das geklärt ist

Fallback-Protokoll #5, blockierend:

* **HEAD ist während der Angriffssitzungen gewandert** (`3e1dfce` → `d22d400`; `kaggle_arena.py` 340 → 375 Zeilen). Commit-Text: v10-Patch `r10_h0` + „Kaggle-Adapter: fehlende deal-Marke ergänzt — ohne sie meldete v10 `fehler:root_nicht_rekonstruierbar`". **Der River-Plan navigiert jetzt tatsächlich** (A2: 12 `river_strategy`-Aufrufe in 8 Decks) — der Kanal von gestern ist nicht der Kanal von heute.
* **Aktuell laufen 2 × `console_solver.exe` und 7 × `python.exe`** (gerade geprüft, nichts beendet). Memory `one-session-per-repo`: sehr wahrscheinlich eine zweite Sitzung.
* **Folge:** die Referenz `+55,8 / SE 38,0 / 32,3 % / 10,5 s je Deck` (`docs/KAGGLE_ARENA.md:153-162`) ist **vermutlich veraltet**, und mit ihr jede Kalibrierung in Rev. 1 und in den Angriffen. Die Durchsatzangabe schwankt um Faktor 25 (Doku 10,5 s/Deck; A2 vor dem Commit **0,41 s/Deck** bei exakt reproduzierten Kennzahlen; A2 nach dem Commit 1,7–16,8 s/Deck).

**Gate G0 (Vorbedingung, siehe §4) muss vor jeder Zeile Code laufen.**

---

## 1. WAS DIE ANGRIFFE GEÄNDERT HABEN

### Ersatzlos gestrichen

| Was | Warum | Quelle |
|---|---|---|
| **Stufe 2 „TKE" komplett** | Der Bot ist **bedingt aufs Deck deterministisch**: `seed: int = 7` fix (`kaggle_arena.py:200`, `:226`), frische Instanzen je Hälfte (`:318-319`), `neue_hand` ist ein No-op (`:215-217`, `hasattr(self.bot,"new_hand")` — `PokerBot` hat kein `new_hand`). Im Maß, über das der Kanal mittelt, ist `a_real` eine deterministische Funktion des Decks ⇒ die einzige B1-konforme „Politik" ist eine **Punktmasse** ⇒ `δ ≡ 0`. Ein Aktions-Term ist entweder identisch null oder verzerrt. Dritte Möglichkeit gibt es nicht. | A1 §2, A3 F3 |
| **Ersatzweg (a): Resolver-Monkeypatch / Datei `kaggle_policy.py`** | `river_strategy` (`resolver.py:232`) liefert die Verteilung **vor** der Kette. Dahinter: `_label_to_action`/`_raise_to` (`bot.py:1054-1057`), der **Override** in `wickle_decide` (`auslese.py:78`, `auslese_guard: True`), `river_gpu_guard` (`improver.py:477ff`, feuert ab Pot 3000 Chips = 30 bb, handabhängig, schluckt jede Exception `:528`) und die Harness-Klemme `int(round(...))` + Fallback-auf-Call bei `can_raise=False` (`kaggle_arena.py:191ff`) — **genau die definierende Bedingung der beanspruchten Knotenklasse**. `{label: p}` ist eine Verteilung über ein Urbild, nicht über ausgeführte Aktionen ⇒ modellierte Politik ⇒ echter Bias, armkorreliert (die Kette existiert nur im Kandidatenarm, `stack=None` beim Basis-Arm) ⇒ vom Spiegel **nicht** gelöscht. | A1 §3, A2 §6, A3 F1 |
| **Ersatzweg (b): K-fache Wiederholung** | `_LINE_U` ist AN (`bot.py:89`, PRINCE-Profil `gto_mode.py:47`): **EINE** Uniform je Hand, gezogen bei `bot.py:218-230`, in der Instanz gehalten (`_hand_u_by_id`, `:148`, gelesen `:489-491`), wiederverwendet an `:783/812/851`. Frische Seeds schätzen die **Marginale**, nicht die Bedingte gegeben den realisierten Präfix; dieselbe Instanz reproduziert die realisierte Ziehung ⇒ Korrektur 0. Der Satz „`E[p̂]=p` und `p̂ ⫫ a_real` ⇒ `E[δ]=0`" ist logisch falsch (Unabhängigkeit ist notwendig, nicht hinreichend). Gemessen: `Random(7).random() = 0.323833` — an allen drei Gattern, in beiden Armen, in **allen** Decks derselbe Wert. | A1 §2, A3 F2 |
| **§3.3 „bereinigte Kanten werden dicht, Sparse-Zweig neu eichen"** | Sachlich falsch, doppelt: auf nicht-divergenten Decks bleibt `X̃ = 0` exakt (identische Trajektorien), und der Sparse-Zweig greift schon heute nicht (`SPARSE_SCHWELLE = 0.02`, `stats.py:90`, gegen `nonzero_anteil` 0,323). Der Absatz widersprach dem eigenen §5.1. | A1 §5, A2 §5.2, A3 F5 |
| **Aktionsrekonstruktion à la `slumbot_adjust`** | Überflüssig: `parse_beobachtung` liefert `pot_gesamt` (`kaggle_arena.py:126`) und `committed_total` (`:159`, `:163`) direkt aus der `observation_string`. Bugfläche ohne Gegenwert, ein guter Teil der veranschlagten 4–6 h. | A3 F7 |
| **`bereinige_deck` in der `duell`-Schleife + `--stufe`-Flag** | Widerspricht der eigenen Architekturregel („post-hoc, nie im Hot-Path") und bricht das eigene 2-%-Zeitkriterium (bis 285 ms je Hälfte gemessen). Der Schätzer läuft **ausschließlich offline** auf dem Log. | A3 F7 |

### Korrigiert (die Konstruktion selbst)

| Rev. 1 | Rev. 2 | Grund |
|---|---|---|
| `Y = E[u \| h_L]` **je Hälfte**, danach differenzieren | `X̃ = E[X \| c_1…c_{j*}]` **je Deck** | Die Varianzgarantie überlebt die Halbierung nicht: `Var(X̃) = Var(Y_h) + Var(Y_r) − 2Cov(Y_h,Y_r)`, und die Kovarianz **besteht** aus genau der Runout-Zufälligkeit, die die Korrektur wegintegriert. A2 hat den schädlichen Fall durchgerechnet (ein Arm all-in mit Pot 400, der andere Showdown mit Pot `P_r` ⇒ Varianzverhältnis `P_r²/(400−P_r)²`, Break-even bei `P_r = 200` Einheiten; für `P_r = 388` Faktor ≈ 1045). Deck-Ebene macht diesen Fall **konstruktiv unmöglich**. |
| „bei Stufe 1 ist `ṽ` exakt → die Korrektur kann nicht schaden" (§5.8) | **gestrichen als Behauptung, ersetzt durch eine Testbedingung**: `Var(X̃) ≤ Var(X)` gilt für die Deck-Konstruktion per Turmsatz; ein gemessener `se_faktor > 1,0` ist folglich ein **Implementierungsfehler**, kein Statistikergebnis (STOPP). | A1 §4, A2 §2 |
| Abbruchregel „`q̂ < 0,25` ⇒ nicht bauen" | **zirkulär** (`q` ist über `X̃` definiert). Ersetzt durch den **Massen-Zensus** `m_chance` — direkt aus dem Log messbar, ohne fertigen Schätzer. | A1 §5(ii) |
| „8 Worker = SE-Faktor 0,354, ~0 Risiko, wenige Zeilen" | **Vermint.** `river_gpu_guard` löst auf der GPU; `research/policy_oracle.py`-Docstring: *„Pilot 2026-09-07: 12 Worker liefen in CUDA-OOM, vom Guard still geschluckt"* (`improver.py:528`, `except Exception`). Naive Parallelisierung kann **still die Politik ändern**. Wird eigene Stufe mit hartem Identitätsgate. | A3 F6 |
| A1-Identitätstest („alle Chance-Ausgänge erzwingen") | Präzisiert: der Test ist nur **nach** `j*` exakt, weil dort **keine Entscheidung mehr folgt** ⇒ keine RNG-Fortsetzung ⇒ der Mittelwert ist exakt, nicht verrauscht. Preflop-All-ins (1,7 Mio. Blätter, ~31 s) sind vom Test **ausgeschlossen** und werden in der Produktion per Budget-Kürzung behandelt. | A1 §6 |
| Enumerationskosten 0,7 / 15,2 / 231 / 2730 ms | **1,3 / 18,5 / 285 / 3454 ms**, Preflop ≈ 31 s (A3 unabhängig nachgemessen, ~25 % teurer als Rev. 1). Schluss „Preflop exakt unbezahlbar" trägt. | A3 |
| A2-Machtrechnung `SD(D) ≈ √q·SD(X)` | Falsch herum — setzt voraus, dass die Korrektur nur Varianz entfernt. Ersetzt durch ein **Bias-Budget by construction** (G5). | A1 §6, A2 §5.3 |

### Bestätigt (hält, unverändert)

* **Der Chance-Term ist mathematisch sauber** — und aus einem Grund, den Rev. 1 nur streifte: der Kartenstrom hat einen **eigenen, hand-lokalen RNG** (`rng = random.Random(deck_seed)`, `kaggle_arena.py:248`), der Bot mischt aus einem getrennten Strom (`bot.py:141`). Keine Aktion verschiebt den Kartenstrom ⇒ `E[δ|F] = 0` **punktweise**, nicht nur im Mittel. Gleiche Stacks + `reset_stacks` ⇒ kein Seitenpot.
* **Alle vier [M]-Struktureigenschaften** (absolute Karten-IDs 0…51, 9 Chance-Knoten à eine Karte, Präfix-Determinismus 600/600, Referenzlauf ≈ 4 ms/Deck) — von A3 unabhängig reproduziert.
* **Absage an modellierte Politiken (K1, TV 0,2085) und an Rollout-Baselines.**
* **Budget-Kürzung als erwartungstreue Abschwächung.**
* **§5.1 (die „10×"-Reduktion aus dem GTOW-Kanal ist NICHT übertragbar, weil der Spiegel die Kartenvarianz bereits gelöscht hat)** — von allen drei Angriffen als stärkste Stelle des Entwurfs benannt.
* **`spiele_hand` hat genau einen Aufrufer** (`duell`; `pargate6._spiele_hand` ist ein Namensvetter) ⇒ additive Signaturerweiterung ist risikoarm.

### Neu hinzugekommen (Befunde, die mehr wert sind als der Schätzer)

1. **Die Misch-Uniform des Kanals ist eingefroren.** `u = 0.323833` an `bot.py:783/812/851`, in beiden Armen, in jedem Deck. Das ist **CRN** (gut für die gepaarte Differenz, und `duell` begründet die frischen Instanzen explizit damit, dass A/A sonst −37,5 statt 0 war) — aber es heißt auch: **der Kanal misst den Armunterschied auf EINEM Mischpfad**. Ein Kandidat, dessen Edge bei anderen `u` liegt, ist unsichtbar. Das ist derselbe Mechanismus wie der dokumentierte v8-Purify-Bruch.
2. **`_SIZE_INJECT` friert beim Import ein** (`resolver.py:117`), `POKERB_PRINCE` wird erst in `PrinceAgent.__init__` gesetzt (`kaggle_arena.py:206-208`, vor dem Bot-Import — im frischen Prozess also korrekt). ⇒ **Bauregel:** das Log-Harness darf `pokerbot.strategy.*` **nicht** vor dem Agenten importieren, sonst misst es einen anderen Bot.
3. **Wo das Geld liegt (A2, am alten Stand gemessen):** 5 Decks tragen 83,2 % der Quadratsumme, alle enden mit einem River-Call, 4 davon an `to_call>0, can_raise=False` (74,4 % der SS). Das ist die Klasse, die der Aktions-Term treffen würde — und die aus den Gründen oben **nicht erreichbar** ist. Der Chance-Term dagegen: **0 von 600 Hälften hatten einen nichtleeren Terminalkern** ⇒ auf dem Referenzstand `q = 0`, `se_faktor = 1,000`.

---

## 2. Der korrigierte Kern (eine Seite Mathematik)

Karten `c_1…c_9` (absolute IDs, präfix-deterministisch, eigener RNG). Messgröße `X(D) = (u_hin − u_rück)·50`.

**`j*` := kleinster Index `j`, ab dem KEINE der beiden Spiegelhälften noch eine Entscheidung hat** (jede Hälfte ist terminal oder all-in). `j*` ist aus der Historie **vor** Karte `j*` messbar ⇒ prädiktabel (B3).

```
X̃(D) = E[ X | c_1…c_{j*} ] = (1/|R|) · Σ_{r ∈ R} X(c_1…c_{j*}, r),   R = alle Vervollständigungen
|R| = C(52 − j*, 9 − j*)
```

* **Erwartungstreu** (Turmsatz), **und** `Var(X̃) ≤ Var(X)` — weil **beide Hälften auf derselben Vervollständigung `r`** ausgewertet werden. Genau das war der Konstruktionsfehler von Rev. 1.
* **Budget-Kürzung:** jedes prädiktable `j' ≥ j*` ist ebenfalls exakt erwartungstreu und ebenfalls `≤ Var(X)`; die Reduktion sinkt monoton mit `j'`. `j' = 5 − 3` ⇒ 285 ms, `5 − 2` ⇒ 18,5 ms.
* **Degenerierte Fälle lösen sich von selbst:** beide Hälften all-in mit identischem Pot ⇒ `X ≡ 0` für jede Vervollständigung ⇒ `X̃ = 0 = X` (kein Rauschen aus einer algebraischen Null — der Schaden, den die Halb-Konstruktion angerichtet hätte). Eine Hälfte all-in, die andere mit weiteren Entscheidungen ⇒ `j* = 9` ⇒ Korrektur exakt 0.
* **Die drei Todesbedingungen des Aktions-Terms** (alle drei heute verletzt, zwei davon außerhalb der Reichweite eines Schätzers):
  * **P1** Die ausgeführte Mischung muss im Messensemble nicht-degeneriert sein. → `seed=7` fix.
  * **P2** Die protokollierte `p` muss die **ausgeführte** Politik sein (Pushforward durch die ganze Kette). → `research/policy_oracle.py::_basis_aktionen` macht das korrekt (Label-Erzwingung durch die volle Kette, GPU-Guard als reine Funktion, ~209 ms/Spot; Identitätstest `tests/test_river_br_pruefstand.py::test_oracle_identitaet_gegen_r8_stack`) — also **nicht gratis, nicht read-only**.
  * **P3** Die Mischzufälligkeit muss **am Knoten frisch** sein. → `_LINE_U` ist hand-latent (Verbotszone `pokerbot/strategy/*`).

---

## 3. Stufenleiter (Rev. 2)

> **Entscheidungsregel unverändert:** eine Maßnahme lohnt genau dann, wenn `Var_alt/Var_neu > t_neu/t_alt`. Da der Schätzer jetzt **offline** läuft, ist `t_neu/t_alt = 1` — die Regel bindet nur noch die Parallelisierung.

### S0 — MITSCHNITT (bauen, unstrittig, ~2 h)
Der Kanal persistiert heute nichts. Ohne Log ist jede Massenzahl Spekulation. Reines Anhängen, `mitschnitt=None` lässt den heutigen Pfad byte-identisch. **Ertrag: macht S1, S2 und S3 überhaupt erst messbar — und erlaubt, jede Auswertung post-hoc auf alten Läufen zu wiederholen.**

### S1 — ZENSUS (bauen, ~1 h, ENTSCHEIDET über S3)
Rein rechnerisch auf dem Log, kein Schätzer nötig:
* `m_chance` = Anteil der Quadratsumme in Decks mit `j* < 9`.
* Verteilung von `j*`; Anteil Decks mit beidseitigem All-in (`X ≡ 0` algebraisch).
* Guard-Feuerrate (`auslese_guard`), Anteil geklemmter Entscheidungen, Anteil `can_raise=False ∧ to_call>0` und deren Anteil an `ΣX²`.
* s/Deck, Plan-Aktivierungen (`_PLAN`), `river_strategy`-Aufrufe.

**Vorregistrierte Erwartung: `m_chance ≈ 0`** (A2: 0/600 Hälften mit nichtleerem Terminalkern) ⇒ **S3 wird voraussichtlich NICHT gebaut**. Das ist die Vorhersage, nicht die Hoffnung; die einzige Unsicherheit ist der v10-Plan seit `d22d400`.

### S2 — PARALLEL-IDENTITÄTSGATE (bauen, ~2 h, der eigentliche SE-Hebel)
8 Worker = 8× Decks = SE-Faktor **0,354** — mehr als jeder Schätzer hier je liefern kann. Aber: GPU-Kontention kann die Politik still ändern. Also: Runner + **hartes Identitätsgate** (G6). Der Log aus S0 liefert die Diagnose (Guard-Feuerrate je Workerzahl), die Kantenliste das Verdikt.

### S3 — DKB (Deck-Kern-Bereinigung) — **nur wenn `m_chance ≥ 0,25`**, ~3 h
`j_stern()` + exakte Enumeration der Vervollständigung + `bereinige_lauf`, offline. Werte direkt aus `parse_beobachtung`, keine Rekonstruktion. Budget `j'` per Flag.

### GESTRICHEN
TKE / Resolver-Mitschnitt / `kaggle_policy.py` / Wiederholungssonden / Rollout-Baselines / modellierte Politik / getrimmtes Mittel als „Varianzreduktion".

### AUSSERHALB DER LEITER (Diagnose, braucht expliziten Auftrag)
**Der eingefrorene Mischpfad.** Kandidat: `seed = 7 + Deckindex`, **von beiden Armen und beiden Hälften desselben Decks geteilt** — CRN bleibt erhalten, A/A bleibt exakt 0, aber `u` streut über 300 Werte statt über einen. Ändert das Schätzziel (Erwartungswert der Strategie statt eines Mischpfads) und **entwertet jede Kalibrierung** ⇒ Nutzerentscheidung, eigenes gepaartes Gate. **Macht den Aktions-Term nicht legal** (P3 bleibt verletzt).

---

## 4. Gate — Abnahmekriterien als Zahlen

**G0 (Vorbedingung, blockierend).** Zweite Sitzung geklärt; frische Referenz auf `d22d400`: `prince[final]` vs `prince[basis]`, 300 Decks, `seed0=90000`, **ein** Worker. Erst 50 Decks zur Durchsatzmessung, dann entscheiden. **Vorregistriert:** weicht `nonzero_anteil` um > 0,05 von 0,323 **oder** `SE` um > 8 von 38,0 ab, sind alle Massenzahlen der Angriffe ungültig und S1 leitet sie neu ab.

**G1 (Log-Neutralität).** (i) Kantenliste mit `--log` **elementweise identisch** zu ohne (300 Decks). (ii) `--aa --decks 8`: `bb100 == 0.0` **und** `nonzero == 0`, **vor und nach** dem Eingriff. (iii) Laufzeitaufschlag **≤ 2 %** (Median aus 3 × 50 Decks).

**G2 (Zensus).** S3 wird gebaut **gdw. `m_chance ≥ 0,25`**. Alle Zensuszahlen werden vor dem Lauf als Erwartung notiert.

**G3 (Identität, punktweise — nur bei S3).**
* `test_dkb_identitaet`: ≥ 20 Decks mit `9 − j* ≤ 2` (≤ 990 Vervollständigungen), alle Ausgänge über `state.clone()` + `apply_action` erzwingen, bis Terminal laufen (nach `j*` **keine** Entscheidung ⇒ keine RNG-Fortsetzung ⇒ der Mittelwert ist exakt). **Abnahme: `|mean_r X(r) − bereinige_deck(...)| ≤ 1e-9` Einheiten, 20/20.**
* `test_budget_monotonie`: `j' ∈ {j*, j*+1, j*+2}` — jede Stufe erfüllt ihre eigene Identität exakt, und die Reduktion sinkt monoton. **3/3.**
* `test_kein_zufall`: `random.Random.random/.sample/.choice` im Schätzerprozess durch werfende Attrappe ersetzt ⇒ `bereinige_lauf` läuft durch.
* `test_schaetzer_determinismus`: zweimal auf demselben JSONL ⇒ byte-identisch.

**G4 (Varianz, gepaart).** Auf **einem** protokollierten Lauf, beide Schätzer aus **derselben** Kantenliste, Deck-Bootstrap mit **identischen** Resample-Indizes. Bericht: `se`, `b_se`, `se_faktor`, **CI des Faktors**, `n_eff`. **Abnahme S3: obere CI-Grenze des `se_faktor` ≤ 0,85.** **Harte STOPP-Bedingung: `se_faktor > 1,0` ⇒ Implementierungsfehler** (per Konstruktion unmöglich), nicht als Statistik berichten.

**G5 (Bias-Budget — neu, aus A1 §6).** `verdikt` feuert ANWENDEN bei `bb100 − 2·se > 0` (`stats.py:93-101`). **Halbiert man `se`, verdoppelt man die Empfindlichkeit gegen jeden Rest-Bias.** Deshalb vorregistriert:
* Ein Schätzer darf nur dann in ein Verdikt eingehen, wenn sein Bias **durch Konstruktion null** ist (exakter bedingter Erwartungswert allein über Kartenzufall; kein `p`, kein `p̂`, kein Modell). DKB erfüllt das; **jeder Aktions-Term erfüllt es nicht**.
* Bis dahin bleibt der **rohe** Schätzer die primäre Zahl; `b_*`-Felder sind **Diagnostik ohne Verdikt**. Das schließt den Forking Path (zwei Verdikte auf denselben Daten) vorab.
* Formales Budget für den hypothetischen Fall eines approximativen Schätzers: `|Bias| ≤ 0,25 · SE_ziel = 1,0 bb/100`. **Kein verfügbarer Test hat diese Macht** — approximative Schätzer sind damit ausgeschlossen, nicht „später zu messen".

**G6 (Parallel-Identität, S2).** `W ∈ {1, 4, 8}` auf denselben 100 Decks: **Kantenlisten elementweise identisch UND Guard-Feuerrate identisch. 3/3.** Bei Abweichung: Workerzahl auf das größte identische `W` gedeckelt, s/Deck-Kurve berichten.

---

## 5. Datei-Spezifikation

**Grundsatz (bindend, verschärft):** der Schätzer läuft **ausschließlich post-hoc auf dem Log**. `duell` bekommt **kein** `--stufe`, rechnet **nichts**.

**Neu**
* `pokerbot/benchmark/kaggle_log.py` (~110 Z.): `karte(idx)` (`"23456789TJQKA"[idx//4] + "cdhs"[idx%4]`, gegen `observation_string` verifiziert), `class Mitschnitt` (nur Anhängen: `.chance()`, `.entscheidung()`, `.ende()`, `.als_zeile()`), `schreibe(pfad, zeilen)` (JSONL, eine Zeile je Hälfte), `referenz_deck()` (4 ms/Deck, **Diagnostik**: materialisiert das volle Board auch für früh endende Decks).
* `research/kaggle_zensus.py` (~90 Z.): **das Artefakt, das entscheidet** — `m_chance`, `j*`-Verteilung, Guard-/Klemm-/Klassenanteile, s/Deck.
* `research/kaggle_parallel.py` (~80 Z.): Worker-Runner + G6.
* `pokerbot/benchmark/kaggle_schaetzer.py` (~180 Z., **nur bei G2-Freigabe**): `j_stern(zeile_hin, zeile_rueck)`, `vervollstaendigungen(gesehene_karten, k)`, `bereinige_deck(zeile_hin, zeile_rueck, j_max=…)`, `bereinige_lauf(jsonl, j_max=…)` + eigenes CLI.
* `tests/test_kaggle_schaetzer.py` (G3).

**Zu loggen (Minimum für S1; fett = für S3 zwingend)**
*Deck:* `deck_seed`, `hand_id`, **`chance_ids[9]`**, `hole_s0`, `hole_s1`, `board5`, `stack_einheiten`, `agent_a/b`, `fp_hash`, `git_sha`, `kante_chips`, `divergenz_ply`, `divergenz_strasse`.
*Hälfte:* `haelfte`, `sitz_von_a`, `u_einheiten`, `terminal_typ`, **`letzter_entscheid_ply`**, **`karten_index_nach_letzter_entscheidung`**, **`pot_gesamt`**, **`committed_total[2]`** (beide direkt aus `parse_beobachtung`, `kaggle_arena.py:126/159/163` — **keine** Rekonstruktion).
*Entscheidung:* `ply`, `strasse`, `spieler`, `legale_aktionen`, `gewaehlt`, `betrag_einheiten`, `pot_vor`, `to_call`, `can_raise`, `wunsch_action`, `wunsch_betrag_chips` (**vor** dem Klemmen), `geklemmt`, `fallback_auf_call`, **`auslese_guard`**, `kanal`, `ms`.

**Additiv geändert:** `kaggle_arena.py` — `spiele_hand(..., mitschnitt=None)` (`:244`), `duell(..., log_pfad=None)` (`:303`), ein CLI-Flag.
**Nicht angefasst:** `pokerbot/strategy/*`, `pokerbot/autogym/improver.py`, `pokerbot/autogym/stats.py`, `pokerbot/engine/equity.py`, `knowledge_base/math/*`.
**Bauregel (aus Befund 2):** das Log-Harness importiert `pokerbot.strategy.*` **nie** vor dem Agenten (`_SIZE_INJECT` friert beim Import ein, `resolver.py:117`).

---

## 6. Ehrliche Grenzen

1. **Der Spiegel hat die Kartenvarianz bereits gelöscht.** Die „~10×"-Reduktion des GTOW-Kanals ist nicht übertragbar; wer Faktor 10 erwartet, zählt sie doppelt.
2. **Auf dem Referenzstand hat der Chance-Term NULL Masse** (0/600 Hälften mit nichtleerem Terminalkern). Der wahrscheinlichste Ausgang dieses Plans ist: **S0+S1 messen, dass nichts zu holen ist.** Das ist ein gültiges Ergebnis, kein Scheitern.
3. **Die Aktionsseite ist zu.** Drei benannte Vorbedingungen, zwei davon außerhalb der Reichweite eines Schätzers, eine davon in der Verbotszone.
4. **Die Mess-Naht bleibt unberührt.** `int(round(...))` (`:191`) erzeugt Divergenzen ohne Strategie-Signal; das Feld `geklemmt` macht sie **sichtbar**, der Schätzer behebt sie nicht.
5. **Varianz ≠ Unwissenheit.** roh +55,8 / getrimmt +6,3 / Median 0 / Vorzeichen-z −0,71 ist mit „wahrer Effekt ≈ 0" gut verträglich. Ein perfekter Schätzer macht daraus ein **enges NEUTRAL**. Wer ANWENDEN sucht, braucht einen besseren Kandidaten.
6. **Das Schätzziel ändert sich nicht** (A − B, kein GTO-Anker; auf das Kaggle-Leaderboard-Scoring gar nicht anwendbar).
7. **Parallelisierung ist der größte Hebel und vermint.** Deshalb S2 vor S3 — und deshalb war Rev. 1 mit „~0 Risiko" falsch.
8. **Jede Kostenangabe hier steht unter G0.** Der Durchsatz ist um Faktor ~25 unsicher.
9. **Alle Messungen der Angriffe beziehen sich auf einen Codestand, den HEAD verlassen hat.**

---

## 7. OFFENE FRAGEN

1. **Läuft eine zweite Sitzung?** 2 × `console_solver.exe` + 7 × `python.exe` aktiv; HEAD ist während der Angriffe gewandert. **Blockierend** — nichts starten, bis geklärt.
2. **Gilt die Referenz `+55,8 / SE 38,0 / 32,3 %` auf `d22d400` noch?** Der v10-River-Plan navigiert jetzt tatsächlich; der Kanal kann eine andere Verteilung haben.
3. **Woher der Durchsatz-Widerspruch 10,5 vs 0,41 vs 1,7–16,8 s/Deck?** Warme Memoisierung, Maschinenlast, GPU-Guard aktiv/inaktiv? Entscheidet, ob 27.000 Decks 3 h oder 79 h kosten — und damit, ob der ganze Schätzer-Gedanke überhaupt einen Gegner hat.
4. **`m_chance` auf dem aktuellen Stand** — die einzige Zahl, die über S3 entscheidet. Erzeugt der v10-Plan (`RC_STACK = "r10_stack"`, `auslese.py:35`) neue All-in-vor-River-Knoten?
5. **Will der Kanal den eingefrorenen Mischpfad?** CRN + A/A exakt 0 (heute) gegen den Erwartungswert der Strategie (`seed = 7 + i`, geteilt von beiden Armen). Nutzerentscheidung; ändert das Schätzziel und entwertet die Kalibrierung.
6. **`self.rng.`-Zählung:** A1 zählt 30, A3 exakt 21. Auflösbar als 21 direkte Aufrufe + 9 Durchreichungen `rng=self.rng` (`bot.py:335/398/430/459/566/569/1054/1081/1107`). Für den Plan irrelevant — **relevant, falls P1/P3 je wieder aufgemacht werden**, denn die Durchreich-Stellen (Equity-MC) sind die großen Verbraucher und erzeugen den datenabhängigen Stromversatz.
7. **Beißt die `_SIZE_INJECT`-Importreihenfolge im Produktionspfad?** `PrinceAgent.__init__` setzt `POKERB_PRINCE` vor dem Bot-Import (`:206-208`) — im frischen Prozess also korrekt. A2 hat den Kipp-Punkt nur im Patch-Harness gemessen. Mit einem Zwei-Zeilen-Test zu klären.
8. **Trägt der Fable-Befund „gecappte Check-Range" hier?** A1 §8 hält den eingefrorenen `u` für denselben Mechanismus wie den v8-Purify-Bruch — das betrifft die **bereits berichteten Zahlen**, nicht erst den Schätzer. Ein Zähllauf über `_line_u` (aus dem S0-Log gratis) bestätigt oder entkräftet es.

---

**Reihenfolge in einem Satz:** G0 klären → **S0 Log** bauen (G1) → **S1 Zensus** rechnen (G2) → **S2 Parallel-Identitätsgate** (G6, der eigentliche SE-Hebel) → **S3 DKB nur bei `m_chance ≥ 0,25`** (G3/G4/G5). Der Aktions-Term ist gestrichen, nicht verschoben.