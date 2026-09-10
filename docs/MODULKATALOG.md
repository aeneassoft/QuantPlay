# MODULKATALOG — die Bausteine von PokerB, einzeln beschrieben

> **Wofuer dieses Dokument da ist.** Es beschreibt jedes Modul dieses Projekts SO, dass man es EINZELN
> beurteilen kann: Zweck, Schnittstelle, Ein-/Ausgabe, Abhaengigkeiten, Zustand, Kosten, Mess-Status und
> der eine Fallstrick. Zielgruppe ist ein Entwickler, der unseren Bot NICHT kennt und aus diesen Teilen
> etwas Eigenes bauen will — er soll je Modul entscheiden koennen: nehmen oder selbst bauen.
>
> **Lies dazu:** [`MESSKATALOG.md`](MESSKATALOG.md) — dort steht, was an jedem Baustein tatsaechlich
> GEMESSEN wurde und was davon heute noch gilt. Der Modulkatalog sagt, was ein Teil TUT; der Messkatalog
> sagt, ob es FUNKTIONIERT. Lagebild: [`STATE.md`](STATE.md). Doktrin: [`../CLAUDE.md`](../CLAUDE.md).
> Nie am Anker gemessene Kandidaten: [`../KANDIDATEN.md`](../KANDIDATEN.md).
>
> **Zwei Warnungen vorweg.**
> 1. **REFUTIERTE Module stehen ausdruecklich mit drin.** Was hier als REFUTIERT markiert ist, wurde
>    gemessen widerlegt — nicht vergessen. Das ist der wertvollste Teil des Katalogs.
> 2. **Mess-Status ohne Quelle gibt es nicht.** Wo `UNGEMESSEN` steht, existiert keine Zahl. Ein Modul kann
>    exzellent aussehen und trotzdem nie bewiesen worden sein.
>
> Erstellt 2026-09-10 von 12 parallelen Lese-Agenten + Vollstaendigkeitspruefung gegen den Dateibaum
> (410 Python-Module gefunden). Der Nachtrag am Ende schliesst die dabei entdeckten Luecken.

## Inhalt

- [Spiel-Engine](#spiel-engine)
- [Strategie-Kern](#strategie-kern)
- [Gegner- und Range-Lesen](#gegner--und-range-lesen)
- [Solver und Re-Solving](#solver-und-re-solving)
- [AUSLESE-Guard-Kette](#auslese-guard-kette)
- [v10-Pakete (River-Fundament)](#v10-pakete-river-fundament)
- [Mess-Infrastruktur](#mess-infrastruktur)
- [Externe Benchmarks](#externe-benchmarks)
- [Gegner, Liga, Turnier](#gegner-liga-turnier)
- [Produkte: Trainer, Coach, Vision](#produkte-trainer-coach-vision)
- [LLM-Brain-Spur (historisch)](#llm-brain-spur-historisch)
- [Wissensbasis, Daten, Werkzeuge](#wissensbasis-daten-werkzeuge)
- [Nachtrag — weitere Module](#nachtrag--weitere-module)

---

## Spiel-Engine

Dieses Subsystem ist die regelkonforme Basis: Kartenrepraesentation, 7-Karten-Handbewertung, Equity-Berechnung
und zwei Zustandsmaschinen (Heads-Up und N-Spieler-Tisch mit Side-Pots), plus optionale GPU-Beschleuniger.
Du brauchst es, wenn du Haende simulieren, ein RL-/Self-Play-Environment betreiben oder Equities rechnen willst;
du brauchst es NICHT, wenn du nur an einem fremden Tisch (Online-Client, fremdes Framework) Entscheidungen
triffst — dann reichen Kartenformat, Evaluator und Equity, und die beiden Zustandsmaschinen sind ueberfluessig.
Alle Module sind reines Python ohne Netzwerk/IO (Ausnahmen: `sd_eval.py` liest eine Datei, die GPU-Module brauchen
torch); es gibt keine Strategie und keine Abhaengigkeit auf `pokerbot/strategy/` in diese Richtung.

**Karten-Konvention (gilt fuer das gesamte Subsystem, ausser den GPU-Modulen):** Eine Karte ist ein 2-Zeichen-String
`rank+suit`, rank aus `"23456789TJQKA"`, suit aus `"shdc"` — z.B. `'As'`, `'Td'`, `'2c'` (`cards.py:10-11`). Das ist
exakt das Format, das `treys` erwartet, deshalb gibt es keine Konvertierungstabelle. Board und Hole sind Listen
solcher Strings. Chips sind IMMER `int` (Blinds default sb=50/bb=100, d.h. 1 bb = 100 Chips, `game.py:31`,
`table.py:44`). Die GPU-Module benutzen ein zweites Encoding: `int64 = rank*4 + suit` mit rank 0='2'..12='A',
suits `'shdc'` (`gpu_eval.py:196-201`) — die Bruecke ist `gpu_eval.encode()`.

### Karten & Hand-Klassen — `pokerbot/engine/cards.py`
**Zweck.** Kartenstrings, gemischtes Deck und die 169er-Startklassen-Notation (`AA`/`AKs`/`AKo`) inklusive
Hin- und Rueckabbildung auf konkrete Combos.

**Schnittstelle.**
- `make_deck() -> list[str]` — die 52 Kartenstrings in fester Reihenfolge (Rang-aussen, Suit-innen), `cards.py:19-20`.
- `class Deck(exclude: list[str] | None = None, rng: random.Random | None = None)` — gemischtes Restdeck; `deal(n=1)
  -> list[str]` popt vom ENDE der Liste, `cards.py:23-33`.
- `hand_class(c1, c2) -> str` — zwei Karten auf die kanonische Klasse abbilden, hoher Rang zuerst (`cards.py:36-44`).
- `normalize_class(hc) -> str` — lose Schreibweisen (`'kqs'`, `'qKs'`) auf die kanonische Form bringen (`:47-56`).
- `all_hand_classes() -> list[str]` — alle 169 Startklassen, deduped, in fester Reihenfolge (`:59-78`).
- `expand_class(hc) -> list[tuple[str, str]]` — Klasse zu konkreten Combos: Paar 6, suited 4, offsuit 12 (`:81-92`).
- `rank_value(rank) -> int` — 0..12 fuer '2'..'A'; `RANKS`, `SUITS`, `RANK_ORDER` als Modul-Konstanten.

**Eingabe/Ausgabe.** Rein: Kartenstrings bzw. Klassenstrings. Raus: Listen von Kartenstrings bzw. Listen von
2-Tupeln `(karte, karte)`. Keine dicts, kein Zustand in den Funktionen.

**Abhaengigkeiten.** Nur `random` aus der Stdlib. Das Modul ist die Wurzel des Subsystems — alles andere
importiert es, es importiert nichts. Ersetzbar, wenn du dein eigenes Kartenformat mitbringst; dann musst du aber
`evaluator.py` (treys-Format) und die GPU-Bruecke mit anpassen.

**Zustand.** Funktionen zustandslos. `Deck` ist zustandsbehaftet je Hand (`self.cards` schrumpft beim `deal`);
pro Hand ein neues `Deck` bauen, nicht zuruecksetzen (so machen es `game.start_hand` und `table.start_hand`).

**Kosten.** Nicht separat gemessen; alle Funktionen sind O(52) oder kleiner. `all_hand_classes()`/`expand_class()`
sind unmemoisiert — bei Aufrufen in heissen Schleifen selbst cachen.

**Mess-Status.** UNGEMESSEN (kein eigener Test, keine EV-Zahl). Indirekt korrektheitsgeprueft: `tests/test_game.py`
(300 Haende) und `tests/test_table.py` (500 Haende) laufen darauf und halten Chip-Erhaltung — beide heute
ausgefuehrt, Ausgabe "All chip-conservation & legality invariants held" bzw. "Chip conservation & non-negative
stacks held every hand (incl. side pots)".

**Allein benutzbar?** Ja, vollstaendig isoliert — Datei kopieren, keine Abhaengigkeit ausser `random`.

**Fallstricke.** `Deck.__init__` ruft `rng.shuffle`; ohne uebergebenes `rng` zieht `random.Random()` OS-Entropie →
Laeufe sind nicht reproduzierbar. Wer gepaarte/duplizierte Messungen fahren will, MUSS ein geseedetes `rng`
durchreichen. Zusaetzlich: Mengen (`set`) von Klassenstrings sind NICHT deterministisch iterierbar — das hat im
Repo dreimal Prozess-Divergenz erzeugt (siehe `equity.py:124-126` und `NOTES.md:21-27`); vor `expand_class` immer
`sorted()`.

### Hand-Evaluator + Treffer-Taxonomie — `pokerbot/engine/evaluator.py`
**Zweck.** 7-Karten-Handbewertung ueber `treys` (memoisiert) plus die projektweit geteilte Taxonomie
"air / pair / top-pair / two-pair+ / monster".

**Schnittstelle.**
- `evaluate(board: list[str], hole: list[str]) -> int` — Score der besten 5 aus board+hole; **niedriger = staerker**
  (1 = Royal Flush, 7462 = schlechteste High Card). board+hole muessen zusammen >= 5 Karten sein (`evaluator.py:31-39`).
- `hand_rank_name(score) -> str` — treys-Klassenname ("Two Pair", "Flush", ...) (`:42-43`).
- `best_five_name(board, hole) -> str` — Kurzform von beidem (`:46-47`).
- `made_class(board, hole) -> str` — `'preflop' | 'air' | 'pair' | 'top-pair' | 'two-pair+' | 'monster'`; DEMOTIERT
  bewusst, wenn das Board die Hand macht (Board-Paar, doppelt-gepaartes Board, Board-Trips, 5-Karten-Board das
  allein spielt → `'air'`), und zaehlt Straight als `'two-pair+'` (`:56-97`).

**Eingabe/Ausgabe.** Rein: zwei Listen Kartenstrings. Raus: `int` (Score), `str` (Name/Klasse). Keine dicts.

**Abhaengigkeiten.** HART: `treys` (`requirements.txt`, `treys>=0.1.8`). `made_class` zusaetzlich auf
`collections.Counter`. Der treys-Teil ist ersetzbar (jeder 7-Karten-Evaluator mit total-order tut es), aber dann
kippt die Score-Richtung und alle Vergleiche `hs < vs` im Rest des Subsystems muessen mitgedreht werden.

**Zustand.** Zwei modulglobale Caches: `_CARD_INTS` (52 Eintraege, vollstaendig nach dem ersten Durchlauf) und
`_EVAL_MEMO` (bis `_EVAL_MEMO_MAX = 120_000` Eintraege, wird bei Erreichen KOMPLETT geleert, `evaluator.py:16-18,
33-38`). Beide sind reine Funktions-Memos — nichts muss zwischen Haenden zurueckgesetzt werden; sie kosten nur RAM.

**Kosten.** Heute gemessen (dieser Rechner, CPython 3.12, Cache vorher geleert): 20.000 verschiedene 7-Karten-
Haende in 0,221 s = **~90.000 evaluate/s kalt**; dieselben Haende erneut = **~4,25 Mio/s aus dem Memo**. Der
Memo-Einbau war Teil der gemessenen `decide()`-Beschleunigung 999 ms → 83 ms (12,1x, `CLAUDE.md:163`,
`docs/STATE.md:817`, Commit 114e107). RAM des vollen Memos nicht gemessen.

**Mess-Status.** GEMESSEN POSITIV fuer die Memoisierung (12,1x auf `decide()`, Quelle oben; Byte-Identitaet der
Ausgabe bewiesen, "0 diffs over 6 arms x 70 spots", `docs/STATE.md:818-819`). `made_class` selbst: UNGEMESSEN in bb
— es ist eine Taxonomie, kein Hebel; sie wird von `research/freq_mine.py:50-53`, `strategy/range_tracker.py:272-279`
und `coach/range_story.py` geteilt, damit gemessene Klassen-Mixe ueberhaupt vergleichbar sind.

**Allein benutzbar?** Ja. Minimal: `pip install treys` + `cards.py` wird nicht einmal gebraucht (nur das
Kartenformat). `made_class` ist ebenfalls standalone.

**Fallstricke.** Die Score-Richtung ist INVERS zur Intuition (kleiner = besser) — und genau umgekehrt zum
GPU-Evaluator im selben Verzeichnis (`gpu_eval.score7`: groesser = besser). Wer beide mischt, dreht garantiert
irgendwo einen Vergleich falsch herum. Zweitens: `made_class` ist bewusst KEINE Handstaerke, sondern eine
Hero-Beitrags-Klasse; ein Flush auf dem Board ist hier `'air'`.

### Equity (Monte-Carlo + exakte River-Enumeration) — `pokerbot/engine/equity.py`
**Zweck.** Hero-Equity gegen eine einzelne Hand, gegen eine Combo-Range, gegen eine GEWICHTETE Combo-Range und
gegen eine Klassen-Range — am River exakt enumeriert, davor Monte-Carlo.

**Schnittstelle.** (alle mit `board=None|list[str]`, `iters=DEFAULT_ITERS`, `rng=None`)
- `equity_vs_hand(hero, villain, board, iters, rng) -> float` — Hero vs eine konkrete Hand. Am River (board=5)
  KEIN Sampling, sondern ein exakter Vergleich → 1.0/0.5/0.0 (`equity.py:15-35`).
- `equity_vs_range(hero, villain_combos, board, iters, rng) -> float` — vs Liste von 2-Tupeln. Am River **exakte
  Enumeration** ueber alle Combos (Hero-Score einmal, Varianz 0); Flop/Turn MC ueber (Combo, Runout) (`:38-76`).
- `equity_vs_weighted_range(hero, combo_weights: dict, board, iters, rng) -> float` — dasselbe fuer
  `{(karte,karte): gewicht}`; River = exakte gewichtete Enumeration, davor MC mit gewichteter Combo-Ziehung
  (`:79-117`).
- `equity_vs_class_range(hero, classes, board, iters, rng) -> float` — Klassenstrings (`'AKs'`) statt Combos;
  expandiert intern ueber `sorted(classes)` (`:120-130`).
- Konstanten: `BOARD_SIZE = 5`, `DEFAULT_ITERS = 3000` (Code-Kommentar `:12`: "~0.9pp standard error").

**Eingabe/Ausgabe.** Rein: Kartenlisten; bei der gewichteten Variante ein dict, dessen Schluessel 2-Tupel von
Kartenstrings sind und dessen Werte positive floats sind (Gewichte muessen NICHT normiert sein). Raus: ein `float`
in [0,1]. **`float('nan')`, wenn nach Blocker-Filterung keine Villain-Combo uebrig bleibt** (`:46, :89-90`) — das
muss der Aufrufer abfangen.

**Abhaengigkeiten.** `cards.expand_class`/`make_deck` und `evaluator.evaluate` — beide hart, aber trivial
ersetzbar. Kein numpy, kein torch.

**Zustand.** Zustandslos bis auf `_FULL = make_deck()` (modulglobal, unveraenderlich) und den Evaluator-Memo.
Nichts zuruecksetzen.

**Kosten.** Heute gemessen (dieser Rechner): `equity_vs_hand`, Flop, iters=3000: **0,041 s**;
`equity_vs_range`, Flop, 200 Combos, iters=3000: **0,041 s** (die Kosten haengen an `iters`, NICHT an der
Combo-Zahl — pro Iteration wird eine Combo gezogen); `equity_vs_range` am RIVER exakt ueber 990 Combos:
**0,011 s**. Die Anzahl Evaluationen ist am River `len(combos)+1`, davor `2*iters`.

**Mess-Status.** GEMESSEN POSITIV (Korrektheit): die River-Enumeration ist byte-identisch zur unabhaengigen
GPU-Enumeration — "River: 20 Proben exakt gegen CPU-Enumeration OK", Toleranz 1e-9 (`gpu_equity.py:99-111`;
Journal-Eintrag `R8-GPU-RESOLVER`, 2026-08-30: "gpu_equity exakt (River identisch CPU-Enum)"). GEMESSEN POSITIV
(Determinismus): der `sorted()`-Fix in `equity_vs_class_range:124-129` behob eine reproduzierte Prozess-Divergenz
(gleicher Seed → Platz 378/12/4), danach byte-identisch ueber Prozesse verifiziert (`NOTES.md:21-27`).
UNGEMESSEN: ob `iters=3000` die richtige Genauigkeit ist — `NOTES.md:203` sagt explizit "TUNING IS PROVISIONAL";
eine exakte Turn-Enumeration statt MC steht als offener Punkt in `NOTES.md:650-651`.

**Allein benutzbar?** Ja. Minimal: `cards.py` + `evaluator.py` + treys. Das ist der Teil, den ein fremder Bot am
ehesten uebernehmen kann, ohne irgendetwas anderes aus dem Repo zu kennen.

**Fallstricke.** Ohne uebergebenes `rng` ist jeder Aufruf nicht reproduzierbar; mit gemeinsamem `rng` sind
aufeinanderfolgende Aufrufe korreliert — fuer gepaarte A/B-Messungen brauchst du je Entscheidung einen
deterministisch abgeleiteten Seed (im Repo "ungeseedete MC bricht Paarungen", `CLAUDE.md`, Mess-Lektionen).
Zweiter Fallstrick: `equity_vs_range` sampelt die Villain-Combo GLEICHVERTEILT; wer eine Range mit
unterschiedlichen Combo-Zahlen je Klasse uebergibt, bekommt implizit die Combo-Gewichtung — das ist meistens
richtig, aber es ist keine Klassen-Gleichverteilung.

### Heads-Up-Zustandsmaschine — `pokerbot/engine/game.py`
**Zweck.** Vollstaendige HU-NLHE-Hand: Blinds, Setzrunden, Streets, Showdown, Rueckerstattung ungecallter
Einsaetze — mit einem JSON-faehigen Zustands-Snapshot.

**Schnittstelle.**
- `HeadsUpGame(names=("You","Bot"), starting_stack=10000, sb=50, bb=100, seed=None)` — `game.py:31`.
- `start_hand() -> None` — neue Hand: Button wechseln, austeilen, Blinds setzen. Wirft `RuntimeError`, wenn ein
  Spieler <= 0 Chips hat (`:68-94`).
- `legal_actions() -> dict` — siehe Ausgabe unten (`:97-128`).
- `act(action: str, amount: int|None = None) -> None` — `'fold' | 'check' | 'call' | 'bet' | 'raise' | 'allin'`.
  `amount` ist das kumulative **TO-Level der Strasse**, nicht der Zusatzbetrag; wird per `int()` trunkiert und
  STILL auf `[raise_min, raise_max]` geklemmt (`:131-183`).
- `state(hide: int|None = None) -> dict` — kompletter Snapshot; `hide=k` maskiert die Hole-Karten von Spieler k
  als `["??","??"]`, solange nicht aufgedeckt wird (`:290-307`).
- `pot() -> int`, `match_over() -> bool`; Attribute `board`, `street`, `button`, `to_act`, `hand_over`, `result`,
  `history`, `players[0..1]` (dataclass `Player` mit `stack/hole/folded/all_in/committed_street/committed_total`).

**Eingabe/Ausgabe.** `legal_actions()` liefert `{to_act, to_call, can_fold, can_check, can_call, call_amount,
can_raise, is_bet, raise_min, raise_max, pot}` — bei beendeter Hand NUR `{"to_act": None}`. `state()` liefert
`{hand_no, button, street, board, pot, current_bet, to_act, hand_over, result, sb, bb, history, players[], legal}`;
**kein `hand_id`** (`docs/V10_FAKTEN.md:43-45`). `history` kennt genau 5 Formen: fold/check
`{player,action,street}` · call `{player,action:'call',amount,street}` · bet/raise `{player,action,to,street}` ·
deal `{action:'deal',street,board}` ohne `player`; das Label `'allin'` erscheint NIE in der History (ein Jam ist
ein bet/raise mit `to == committed_street+stack`) (`docs/V10_FAKTEN.md:35-40`, `game.py:143-181,234-239`).
`result` = `{winner, reason:'fold'|'showdown', pot, reveal, board, [hands]}`.

**Abhaengigkeiten.** `cards.Deck`, `evaluator.evaluate`/`best_five_name` — hart, aber klein. Sonst nur Stdlib.
Keine Abhaengigkeit auf Strategie/Advisor.

**Zustand.** Je Hand: alles ausser `players[].stack`, `button` und `hand_no` wird in `start_hand()` neu gesetzt.
Je Sitzung: Stacks laufen weiter; wer unabhaengige Haende will, setzt die Stacks vor jedem `start_hand()` selbst
zurueck (so macht es `tests/test_game.py:37`). `seed` fixiert nur den internen `random.Random`.

**Kosten.** Nicht separat gemessen (die Table-Variante schafft ~6.200 Haende/s, siehe unten; HU ist billiger).

**Mess-Status.** GEMESSEN POSITIV (Invarianten): `python -m tests.test_game` heute ausgefuehrt — "OK: played 300
hands | showdowns=109 folds=191 allin_hands=23 ... All chip-conservation & legality invariants held across every
hand." Der Kanal darauf ist der gesamte Mess-Apparat des Projekts (gepaarte Duplikat-Laeufe `duplicate.py`,
`pargate`, GTOW-Adapter), d.h. das Modul ist millionenfach gelaufen. Ein EV-Wert ist fuer eine Engine sinnlos —
UNGEMESSEN in bb, per Konstruktion.

**Allein benutzbar?** Ja: `cards.py` + `evaluator.py` + treys, sonst nichts. Das Strategie-Interface, das der Rest
des Repos benutzt, ist `decide(state_dict) -> (action, amount)` mit dem `state()`-dict oben
(`pokerbot/benchmark/duplicate.py:8-9,101-115`).

**Fallstricke.** `amount` ist ein TO-Level und wird still geklemmt: wer den Zusatzbetrag uebergibt, spielt
unbemerkt eine andere Groesse, ohne dass je eine Exception faellt. Zweiter Punkt: `can_fold` ist definiert als
`can_call` (`game.py:119`) — ein Fold bei `to_call == 0` wird aber trotzdem NICHT abgelehnt und faltet die Hand
(`docs/V10_FAKTEN.md:32-33`); dein Bot kann sich also selbst wegwerfen. Drittens: Engine-Default ist
`starting_stack=10000` (100 bb), aber alle Messkanaele des Repos fahren 20000/50/100 = 200 bb
(`docs/V10_FAKTEN.md:47-49`) — Zahlen sind nur bei gleicher Stack-Tiefe vergleichbar.

### N-Spieler-Tisch / RL-Umgebung — `pokerbot/engine/table.py`
**Zweck.** 2–10 Sitze No-Limit Hold'em mit korrekten Side-Pots, optionalen Antes und optionalem Auto-Rebuy — das
Environment, auf dem Self-Play, die 6-max-Liga und die Web-App laufen.

**Schnittstelle.**
- `Table(names, starting_stack=10000, sb=50, bb=100, seed=None, human_seat=0, stacks=None, ante=0, rebuy=True)` —
  `stacks` = individuelle Startstacks (Turnier), `ante` = tote Vorab-Steuer je Hand, `rebuy=False` laesst Pleite-
  Spieler pleite (`table.py:44-51`).
- `start_hand() -> None` — Auto-Rebuy (falls aktiv), Reset, Button+1, austeilen, Antes VOR den Blinds, Blinds,
  ersten Akteur bestimmen (`:103-154`).
- `legal_actions() -> dict` — fuer den AKTUELL am Zug befindlichen Sitz (`:163-181`).
- `act(action, amount=None) -> None` — `'fold'|'check'|'call'|'bet'|'raise'|'allin'`; `amount` = TO-Level der
  Strasse, `int()`-trunkiert und still geklemmt; jeder (Re-)Raise oeffnet die Aktion wieder (`has_acted=False`
  fuer alle anderen) (`:184-225`).
- `obs_for(seat) -> dict` — Beobachtung fuer einen Sitz (`:340-352`).
- `position_label(seat) -> str` — `BTN/SB/BB/UTG/UTG+1/UTG+2/UTG+3/LJ/HJ/CO` je nach Tischgroesse
  (`POS_LABELS`, `:17-27`, `:94-100`).
- `pot() -> int`; Attribute `seats[]` (dataclass `Seat`), `board`, `street`, `button`, `to_act`, `hand_over`,
  `result`, `history`, `hand_no`.

**Eingabe/Ausgabe.** `legal_actions()` → `{to_act, to_call, can_fold, can_check, can_call, call_amount, can_raise,
is_bet, raise_min, raise_max, pot}`; bei beendeter Hand nur `{"to_act": None}`. `obs_for(seat)` →
`{hole, board, to_call, pot, my_stack, bb, n_active, position, preflop_raises, cur_bet, my_committed_street,
street, can_check, can_call, can_raise, raise_min, raise_max}`. `result` bei Fold-Ende:
`{reason:'fold', pot, reveal:False, winners:[{seat,name,amount}], board}`; bei Showdown zusaetzlich
`{pots:[{amount,winners}], shown:{seat:{hole,rank}}}` — **`shown` enthaelt NUR Gewinner** (Mucking, `:332-334`).

**Als RL-Umgebung.** Der Loop ist `start_hand()` → solange `not hand_over`: `obs_for(to_act)` /
`legal_actions()` → `act(a, amt)` → am Ende `result` als Belohnungsquelle (Stack-Differenz je Sitz ist die
saubere Reward-Groesse, nicht `result['pot']`, siehe Fallstricke). Es gibt KEIN `reset()` und kein
gym/gymnasium-Interface; `start_hand()` ist der Reset. Es gibt keine Observation-Encoder — `obs_for` liefert
rohe Python-Typen, das Featurizing ist deine Aufgabe.
- **Side-Pots**: `_build_pots()` schichtet ueber `committed_total` (`:272-285`); jede Schicht bekommt ihre
  eligible-Menge, Split-Reste gehen an den ersten Gewinner im Uhrzeigersinn ab Button (`:317-321`). Eine
  Schicht ohne Eligible (Fold OBERHALB eines All-in-Caps) wird an die Einzahler ZURUECKERSTATTET statt vernichtet
  (`:301-309`) — der Kommentar dort nennt den Fuzz-Fund "-99 Chips auch ohne Antes moeglich".
- **Antes**: werden vor den Blinds committed und danach wird `committed_street` wieder auf 0 gesetzt, sonst zaehlt
  die Ante gegen `current_bet` (`:124-135`; der Kommentar listet die drei Bugs, die das im 600er-MTT-Audit
  erzeugte, Chip-Erhaltung −32/Tisch).
- **Heads-Up-Sonderfall**: bei `n == 2` ist der Button der Small Blind und handelt preflop zuerst (`:136-140`) —
  das war frueher invertiert und betraf jedes Multiway-Endspiel, das auf 2 Spieler schrumpfte.
- **Rebuy**: `rebuy=True` (Default) fuellt jeden Stack < 1 bb in `start_hand()` auf `starting_stack` auf (`:104-106`).

**Abhaengigkeiten.** `cards.Deck`, `evaluator.evaluate`/`best_five_name`. Sonst Stdlib. Keine Strategie-Importe.

**Zustand.** Je Hand: Board, Street, Historie, `committed_*`, `folded/all_in/has_acted` (Reset in `start_hand`).
Je Sitzung: `seats[].stack`, `button`, `hand_no`, der interne RNG. Fuer unabhaengige Haende die Stacks selbst
zuruecksetzen (`tests/test_table.py:32-33`).

**Kosten.** Heute gemessen: 2.000 vollstaendige 6-max-Haende mit einer trivialen Zufallspolitik in 0,323 s =
**~6.200 Haende/s** single-threaded (ohne Bot-Entscheidungszeit; die dominiert in der Praxis um Groessenordnungen).

**Mess-Status.** GEMESSEN POSITIV (Invarianten): `python -m tests.test_table` heute ausgefuehrt — "OK: 500 six-max
hands | showdowns=486 folds=14 allin_hands=498 side-pot_hands=374 / Chip conservation & non-negative stacks held
every hand (incl. side pots)." Chip-Erhaltung ist im Projekt ein nicht verhandelbares Gatter (`CLAUDE.md`,
Operative Doktrin). UNGEMESSEN in bb (Environment, kein Hebel).

**Allein benutzbar?** Ja: `cards.py` + `evaluator.py` + treys. Kein Server, kein Config-Import.

**Fallstricke.** **`obs_for(seat)` mischt zwei Perspektiven**: `hole`/`my_stack`/`position` kommen vom
uebergebenen Sitz, aber `to_call`/`can_check`/`can_call`/`can_raise`/`raise_min`/`raise_max` kommen aus
`legal_actions()` und gelten fuer den Spieler, der GERADE am Zug ist (`table.py:340-352`). Heute verifiziert: an
einem 3er-Tisch liefert `obs_for(nicht_am_Zug)` `to_call=100, can_check=False` — die Werte des Akteurs. Ruf es nur
mit `seat == table.to_act` auf. Und nach Handende wirft es `KeyError: 'to_call'`, weil `legal_actions()` dann nur
`{"to_act": None}` zurueckgibt (heute reproduziert).
Zwei weitere Minen: (a) `act('raise', None)` wirft `TypeError: int() argument ... not 'NoneType'` statt einer
sauberen ValueError (heute reproduziert; `game.py` prueft das explizit, `table.py:208` nicht). (b)
`result['pot']` enthaelt auch ungecallte Einsaetze — es gibt in `table.py` kein `_refund_uncalled` wie in
`game.py:241-251`; heute reproduziert: Sitz jammt 1000, alle folden, `result['pot'] = 1150`, tatsaechlicher
Gewinn +150. Fuer bb/100 immer Stack-Differenzen rechnen, nie `result['pot']`. (c) Der Auto-Rebuy ist per Default
AN und fuellt Stacks lautlos auf — fuer jede Messung `rebuy=False` setzen.

### Suit-Isomorphie — `pokerbot/engine/isomorph.py`
**Zweck.** Board-Kanonisierung ueber Suit-Umbenennung (Johanson 2007 §2.5.1): bis zu 24 Solve-Cache-Eintraege je
strategischer Situation kollabieren zu einem.

**Schnittstelle.**
- `canonical_board(board: list[str]) -> tuple[list[str], dict]` — kanonisches Board (lexikographisch minimal ueber
  alle 24 Suit-Permutationen, Reihenfolge der Karten bleibt erhalten) plus die verwendete Suit-Abbildung
  (`isomorph.py:20-28`).
- `apply_map(card: str, suit_map: dict) -> str` — dieselbe Abbildung auf eine beliebige Karte (Hero-Hole)
  anwenden (`:31-32`).
- `main()` — Selbsttest (`:35-49`).

**Eingabe/Ausgabe.** Rein: Liste Kartenstrings. Raus: `(liste, dict)` mit dict `{'s':'h', 'h':'s', ...}`.

**Abhaengigkeiten.** Nur `itertools`. Vollstaendig frei stehend.

**Zustand.** Zustandslos (`_ALL_PERMS` ist eine Konstante).

**Kosten.** O(24 · |board|) je Aufruf, im Docstring so angegeben; absolute Latenz nicht gemessen.

**Mess-Status.** GEMESSEN POSITIV (Korrektheit): Selbsttest heute ausgefuehrt — "isomorph self-test: 500 boards x
24 relabelings -> canonical form idempotent + invariant. OK". GEMESSEN POSITIV (Wirkung auf den Cache):
`NOTES.md:645-646` — "permutiertes Board -> Cache-Kollaps 5.0s->0.0s, identische Strategie", bis 24x Hit-Rate auf
dem 12-GB-Cache. UNGEMESSEN in bb; der Schalter `POKERB_ISO_CACHE` ist im Repo default AUS
(`pokerbot/strategy/gto_oracle.py:54`).

**Allein benutzbar?** Ja, eine Datei ohne Abhaengigkeiten.

**Fallstricke.** Die Kanonisierung ist nur dann EXAKT, wenn ausser Board und Hero-Hole nichts Suit-Tragendes in
den Solve geht — im Repo gilt das, weil Ranges KLASSEN-Strings sind und die Navigation ueber Bet-Size-Labels
laeuft (`isomorph.py:4-7`). Wer suited-spezifische Ranges (`AhKh`) oder suit-abhaengige Features durchreicht,
bekommt falsche Cache-Treffer — und zwar lautlos.

### Short-Deck-Evaluator (6+) — `pokerbot/engine/sd_eval.py`
**Zweck.** Handbewertung fuer die 36-Karten-Variante 6+ Hold'em, bewusst getrennt vom 52-Karten-treys-Pfad.

**Schnittstelle.**
- `available() -> bool` — ist die Rangtabelle vorhanden (`sd_eval.py:41-42`).
- `rank5(cards5_tuple) -> int` — `lru_cache(200000)`; **niedriger = besser** (`:51-53`).
- `rank7(cards7) -> int` — bestes (kleinstes) Ergebnis ueber die 21 Fuenfer-Teilmengen (`:56-61`).
- `best_hand_rank(hole, board) -> int` (`:64-66`); `normalized_strength(hole, board) -> float` in [0,1], 1 = bestes
  (`:69-72`).
- Konstanten `SD_RANKS = "6789TJQKA"`, `SD_SUITS = "cdhs"`, `SD_DECK` (36 Karten).

**Eingabe/Ausgabe.** Rein: Kartenstrings mit Raengen 6..A (ein 2–5 loest `KeyError` aus, absichtlich als
Leckage-Wache). Raus: `int` Rang bzw. `float` Staerke.

**Abhaengigkeiten.** HART auf eine DATEI: `tools/TexasSolver-v0.2.0-Windows/resources/compairer/
card5_dic_sorted_shortdeck.txt` (C(36,5) = 376.992 Zeilen), Pfad ueber `pokerbot.config.ROOT` (`:22-23`). Ohne
TexasSolver-Bundle ist das Modul nutzlos. Der Import auf `pokerbot.config` ist die einzige Kopplung ins Repo und
waere durch einen Pfad-Parameter ersetzbar.

**Zustand.** Modulglobales `_DICT` (lazy geladen, 376.992 Eintraege) plus der `lru_cache`. RAM nicht gemessen.

**Kosten.** Nicht gemessen. `rank7` macht bis zu 21 Dict-Lookups je Hand.

**Mess-Status.** UNGEMESSEN in bb. Korrektheit: der Docstring dokumentiert eine Verifikation vom 2026-06-15
(Variante: Flush > Full House, A-6-7-8-9-Wheel, **Trips > Straight**) — die Quelle dafuer ist der Docstring selbst
(`sd_eval.py:1-7`), kein Testskript im Repo. Datei-Verfuegbarkeit heute geprueft: `available() == True`.

**Allein benutzbar?** Ja, wenn du die Rangtabelle hast und den `config`-Import durch einen Pfad ersetzt.
Konsument im Repo: `research/build_sd_advisor_data.py`.

**Fallstricke.** Die Variantenregel **Trips schlaegt Straight** ist raumabhaengig — der Docstring warnt selbst:
"confirm vs the target room before any COMPETITIVE use". Wer das nicht prueft, bewertet in einem Standard-6+-Raum
systematisch falsch.

### GPU-Evaluator — `pokerbot/engine/gpu_eval.py`
**Zweck.** Vektorisierter 7-Karten-Evaluator als eine einzige torch-Batch-Operation, ordnungs-isomorph zum
CPU-Evaluator.

**Schnittstelle.**
- `score7(cards: torch.Tensor) -> torch.Tensor` — `[N,7]` long (Karten 0..51) → `[N]` long Score,
  **groesser = besser** (`gpu_eval.py:75-193`). Score-Aufbau: `kategorie * 13^5 + k1*13^4 + ... + k5`,
  Kategorie 8 = Straight Flush .. 0 = High Card.
- `encode(cards: list[str]) -> list[int]` — Bruecke `'As'` → `rank*4+suit` (`:200-201`).
- `verify_vs_reference(n=200_000, seed=7) -> (geprueft, fehler)` — Ordnungs-Isomorphie gegen
  `evaluator.evaluate` auf n Zufallspaaren (`:204-225`).
- `benchmark(n=2_000_000) -> dict` (`:228-...`); `DEVICE` = cuda falls verfuegbar, sonst cpu (`:32`).
- Ausfuehrbar: `python -m pokerbot.engine.gpu_eval` (Verifikation + Benchmark).

**Eingabe/Ausgabe.** Rein: `torch.Tensor [N,7] dtype=long`. Raus: `torch.Tensor [N] dtype=long` auf `DEVICE`.
Keine dicts.

**Abhaengigkeiten.** HART: `torch` — **nicht in `requirements.txt` deklariert** (lokal 2.11.0+cu128, CUDA
verfuegbar, heute geprueft). Fuer die Verifikation zusaetzlich `cards.py` + `evaluator.py`. Laeuft auch auf CPU
(langsamer), ist dort aber sinnlos.

**Zustand.** Zustandslos; nur Konstanten (`_P13`, `_STRAIGHTS`). Kein RNG.

**Kosten.** GEMESSEN: **16,8 Mio Haende/s** (`docs/STATE.md:115-116`; Journal `R8-GPU-RESOLVER` 2026-08-30).
Speicher: die Zwischentensoren sind `[N,13]`/`[N,7]` long — bei N in Millionen relevant, nicht gemessen.

**Mess-Status.** GEMESSEN POSITIV (Korrektheit): 250.000 Ordnungs-Paare, **0 Fehler** (`docs/STATE.md:115-116`,
Journal `R8-GPU-RESOLVER`). UNGEMESSEN in bb — es ist ein Beschleuniger, kein Hebel; der Docstring sagt selbst
"ADDITIV: dieses Modul aendert NICHTS am bestehenden Pfad". Es gibt KEINE Datei unter `tests/` dafuer, nur den
`__main__`-Selbsttest (`docs/V10_FAKTEN.md:27`).

**Allein benutzbar?** Ja, fuer `score7`/`encode` reicht torch. Fuer `verify_vs_reference` brauchst du zusaetzlich
treys + `cards.py` + `evaluator.py`.

**Fallstricke.** Die Score-Richtung ist INVERS zum CPU-Evaluator (hier groesser = besser, dort kleiner = besser) —
das ist die Nummer-eins-Fehlerquelle beim Mischen. Zweiter, teuer gelernter Punkt: `_highest_bit` ist
absichtlich integer-only, weil CUDA-`log2` um 1 ulp danebenliegen darf und bei exakten Zweierpotenzen einen
falschen Rang lieferte (`gpu_eval.py:53-56`, "Lehre: CUDA-log2 1-ulp-Falle" `docs/STATE.md:116`). Wer das
"optimiert", baut einen stillen Einzelfehler ein.

### GPU-Equity (exakte Enumeration) — `pokerbot/engine/gpu_equity.py`
**Zweck.** Hero-Equity gegen JEDE Combo einer Range mit vollstaendig enumeriertem Runout-Raum, als Batch-Tensor-Op.

**Schnittstelle.**
- `equity_vs_range_exakt(hero: list[str], villain_combos: list[tuple[str,str]], board: list[str]) -> torch.Tensor`
  — `[C]` float auf CPU; **eine Equity je Villain-Combo** (nicht ein Skalar!); Combos, die Hero/Board blocken,
  bekommen `NaN` (`gpu_equity.py:34-87`).
- `_verify()` / `_benchmark()` — nur ueber `python -m pokerbot.engine.gpu_equity` (`:90-169`).

**Eingabe/Ausgabe.** board mit 3, 4 oder 5 Karten. Enumeriert River: C Combos; Turn: C × 46 Riverkarten;
Flop: C × 1081 Turn/River-Paare (`:3-8`). Ausgabe `[C]` mit NaN fuer geblockte Combos — der Aufrufer muss
`nanmean()`/eigene Gewichtung anwenden; das Modul liefert KEINE gewichtete Aggregation.

**Abhaengigkeiten.** HART: `torch` (nicht in `requirements.txt`) und `gpu_eval` (`DEVICE`, `encode`, `score7`).
Fuer die Verifikation zusaetzlich `equity.py` als CPU-Referenz.

**Zustand.** Zustandslos, kein RNG, kein Cache.

**Kosten.** GEMESSEN: Flop, 1081 Combos × 1081 Runouts EXAKT in **0,087 s** (`docs/STATE.md:117`). Der Speicher
skaliert mit C×R (der `[C,R,7]`-Tensor) — bei 1326 Combos × 1081 Runouts sind das ~10 Mio long-Eintraege je
Zwischenschritt; Peak-VRAM nicht gemessen.

**Mess-Status.** GEMESSEN POSITIV (Korrektheit): River byte-identisch zur CPU-Enumeration, Toleranz 1e-9, 20
Proben; Flop im 4-SE-Band der CPU-MC (`gpu_equity.py:99-131`; `docs/STATE.md:117`; Journal `R8-GPU-RESOLVER`).
UNGEMESSEN in bb. **Wichtig: `docs/V10_FAKTEN.md:204-206` haelt fest — "KEINE 1326-Batch-Variante, KEINE
gewichtete Variante, kein Produktions-Aufrufer"**; das Modul ist heute Werkzeug/Baustein, kein Teil des laufenden
Bots. In `docs/V10_BUILD_CARD.md:157` wurde die Karte "gpu_equity vektorisiert" aus dem K1-Plan wieder GESTRICHEN.

**Allein benutzbar?** Ja: torch + `gpu_eval.py` + `gpu_equity.py`. Fuer den Selbsttest zusaetzlich treys,
`cards.py`, `evaluator.py`, `equity.py`.

**Fallstricke.** Die Rueckgabe ist ein Vektor je Combo, kein Skalar — `float(eq)` schlaegt fehl, und ein naives
`eq.mean()` liefert NaN, sobald eine einzige Combo blockt (richtig ist `nanmean()`, so macht es die Verifikation
`:107`). Zweitens rechnet die Verifikation UNGEWICHTET gleichverteilt ueber die Combos; wer Range-Gewichte hat,
muss die Aggregation selbst schreiben.

### Paket-Export — `pokerbot/engine/__init__.py`
**Zweck.** Re-Export der Karten- und Evaluator-Primitive.

**Schnittstelle.** `RANKS, SUITS, make_deck, Deck, hand_class, all_hand_classes, expand_class, rank_value,
normalize_class, evaluate, hand_rank_name, best_five_name` (`__init__.py:2-12`).

**Eingabe/Ausgabe.** Entfaellt.

**Abhaengigkeiten.** `cards.py`, `evaluator.py` — d.h. ein `import pokerbot.engine` zieht sofort `treys`.

**Zustand.** Zustandslos.

**Kosten.** Import-Zeit von treys; nicht gemessen.

**Mess-Status.** UNGEMESSEN (reine Re-Export-Datei).

**Allein benutzbar?** Entfaellt.

**Fallstricke.** `equity`, `game`, `table`, `made_class`, `sd_eval`, `isomorph` und die GPU-Module sind hier NICHT
exportiert — die musst du mit vollem Pfad importieren (`from pokerbot.engine.table import Table`). Wer sich auf
`from pokerbot.engine import *` verlaesst, bekommt die halbe Engine nicht.

---

## Strategie-Kern

Dieses Subsystem ist die vollstaendige Entscheidungs-Pipeline eines **Heads-Up-No-Limit-Bots**: ein State-dict rein,
eine legale Aktion plus begruendendes rationale-dict raus. Es besteht aus einem grossen Regelbaum (`bot.py`) und
vier kleinen, sauber isolierbaren Preflop-Datenschichten (Staerkemodell, Range-Definitionen, ein CFR-geloester
Push-Fold-Blueprint, ein near-Nash-200bb-Blueprint). Du brauchst es NUR, wenn du einen HU-Bot willst — der Kern ist
2-Spieler-hart verdrahtet (`1 - hero_idx` an ~20 Stellen); fuer 6-max existiert ein separater, unabhaengiger Kern
(`pokerbot/arena/sixmax.py`). Die Preflop-Datenschichten (2.-8. unten) sind dagegen einzeln nachnutzbar und die
klar wertvollsten Teile, wenn du deinen eigenen Baum bauen willst.

---

### Entscheidungs-Pipeline (PokerBot) — `pokerbot/strategy/bot.py`

**Zweck.** Ein 1320-Zeilen-Regelbaum, der aus einem Heads-Up-Spielzustand eine legale Aktion plus strukturierte
Begruendung erzeugt, indem er Preflop-Blueprints, MC-Equity, trainierte Solver-Advisors, einen Range-Tracker und
optionale Echtzeit-Resolver in einer festen Prioritaetskette abfragt.

**Schnittstelle.**
- `PokerBot(hero_idx: int, seed: int | None = None, exploit: bool = True)` — ein Bot-Objekt fuer EINEN Sitz.
  `hero_idx` ist der Sitzindex (0/1), `seed` seedet `random.Random` fuer gemischte Strategien.
- `decide(state: dict) -> dict` — die einzige eigentliche API. Wirft `ValueError`, wenn `state["legal"]["to_act"]`
  nicht `hero_idx` ist (bot.py:206-207).
- `observe_opponent(street: str, action: str, facing_bet: bool) -> None` — fuettert das aggregierte Gegnermodell
  (`OpponentModel`), muss vom Aufrufer nach JEDER Gegner-Aktion gerufen werden (bot.py:1292).
- `observe_hand_end(final_state=None) -> None` — schliesst die Hand ab und speist die Reaktionen des Gegners auf
  unsere River-Bets in das Dirichlet-Knotenmodell (bot.py:1295-1320).
- Oeffentliche Attribute als A/B-Schalter (im `__init__` gesetzt, bot.py:155-201): `exploit`, `use_resolver`,
  `use_turn_resolver`, `use_flop_resolver`, `use_range_tracker`, `use_blueprint`, `bp_deep_min_bb`,
  `bp_jam_min_pct`, `deep_jam_pct`, `value_raise_eq`, `use_commit_cap`, `use_probe`, `use_deepcfr`,
  `tracker_cls` (austauschbare Range-Tracker-Klasse), `fold_model`.

**Eingabe/Ausgabe.** Eingabe = das State-dict der Engine (`pokerbot/engine/game.py:state()`). Tragende Schluessel:
`street` ("preflop"/"flop"/"turn"/"river"), `board` (Liste 2-Zeichen-Karten), `pot` (Chips), `bb`, `sb`,
`button` (Sitzindex), `current_bet`, `history` (Liste; Eintraege `{player, action, street}` plus
`{action:"deal", street, board}` bei jedem Board-Deal — beide Formen werden gelesen, game.py:239),
`players` (Liste je Sitz mit `hole`, `stack`, `committed_street`, `committed_total`, `all_in`, `folded`) und
`legal` mit `to_act`, `to_call`, `can_check`, `can_call`, `can_raise`, `is_bet`, `raise_min`, `raise_max`, `pot`.
Ausgabe = `{"action": str, "amount": int|None, "rationale": dict}`. `action` ist eines von
`fold|check|call|bet|raise|allin`; `amount` ist ein **Ziel-Gesamteinsatz dieser Strasse** ("to"), NICHT ein Delta
(game.py:168-172), und ist `None` bei fold/check/call/allin. `rationale` traegt immer `reasoning` (Klartext,
`_mk`, bot.py:1286) plus pfadabhaengige Diagnose-Felder — preflop `phase/hand/hand_class/percentile/eff_stack_bb/
position`, postflop zusaetzlich `made_hand/equity/villain_combos/texture/required_equity/mdf/call_threshold`,
Resolver-Pfade nur ein duennes `{phase, street, hand, made_hand, board, range_conf, resolver:True}`.

**Abhaengigkeiten.** HART: `pokerbot.engine.cards` (hand_class/expand_class), `pokerbot.engine.evaluator`
(treys-basiert), `pokerbot.engine.equity` (`equity_vs_range`, `equity_vs_weighted_range`),
`pokerbot.strategy.preflop_strength`, `ranges`, `postflop` (Sizing/Textur/Konstanten), `advisor`
(trainierte MLPs), `opp_model`, `opponent`, `blueprint`, `preflop_blueprint`, `gto_mode`, `pokerbot.config`
(Pfade zur `knowledge_base/`). ERSETZBAR (lazy importiert, jeweils in try/except oder mit None-Rueckfall):
`range_tracker` (faellt auf die `_narrow`-Heuristik zurueck), `resolver` (faellt auf den Floor zurueck),
`deepcfr_adapter` (nur bei `use_deepcfr=True`).

**Zustand.** Je Sitzung: `opp` (aggregierte Gegner-Frequenzen), `opp_model` (Dirichlet je River-Knoten),
`_probe_spent_bb` (Risikobudget der Off-Tree-Probes), `rng`. Je Hand: `_river_keys` (wird zu Beginn jeder
Preflop-Entscheidung geleert, bot.py:217), `_hand_u`/`_hand_u_by_id` (Line-Draw pro Hand, nur unter
`POKERB_LINE_U`; die id-Variante wird bei >64 Eintraegen gestutzt). Je Entscheidung: `_cur_street`,
`_cur_committed`, `_ecall_exact_to`, `_cur_state/_cur_hole/_cur_board`. Reset zwischen Sessions = neues Objekt;
ein Reset zwischen Haenden ist NICHT noetig, aber `observe_hand_end` muss gerufen werden, sonst wachsen
`_river_keys` und das Dirichlet-Modell lernt nichts.

**Kosten.** `decide()` ≈ **83 ms** nach der Memoisierung von `advisor.p_bet/p_defense` (vorher 999 ms, Faktor
12,1; CLAUDE.md:163 / docs/TRAINER_PLAN.md:563 / docs/V10_FAKTEN.md:103 — memoisiert ist der Advisor, nicht
`decide` selbst). Dominierender Posten postflop ist die MC-Equity mit `EQUITY_ITERS = 1500` (bot.py:29).
Mit `use_resolver=True` kommt ein echter River-Solve dazu (Latenz nicht in dieser Datei belegt; die
Cache-Flags `POKERB_SOLVE_CACHE/POKERB_ISO_CACHE` sind laut gto_mode.py:83-86 nicht semantik-neutral am
Timeout-Rand). Speicher: klein, ausser dem einmalig geladenen Advisor-Netz und den JSON-Tabellen.

**Mess-Status.** GEMESSEN — der Gesamt-Bot ist mehrfach gegen GTO Wizard (AIVAT) vermessen:
HEAD-Default (alle Flags aus) **−20,09 ± 7,18 bb/100, n=974** (CLAUDE.md, Block 2026-07-04);
Profil PRINCE v2.2 **−19,70 ± 4,37 bb/100, n=2393, 0 Katastrophen** (gto_mode.py:32-34);
aktueller einziger bestaetigter Live-Anker **v4-auf-PRINCE −21,1** (docs/STATE.md:52).
REFUTIERT ist der Exploit-Pfad: `POKERB_EXPLOIT=1` vs `0`, 600 gepaarte Decks je Liga-Profil, alle 8
Punktschaetzer ≤ 0, gepoolt ≈ **−12 bb/100 (SE ~4,5)** (Journal `data/autogym/journal.jsonl`, Eintrag
`EXPLOIT-GATE-VERDIKT`, 2026-09-09) → `_river_exploit` verliert gegen JEDES Profil, auch gegen die
ausbeutbaren. Der Range-Tracker als Equity-Quelle ist GEMESSEN POSITIV auf der Range-Metrik
(L1 0,437 vs `_narrow` 0,756 vs uniform 0,995 = +42 % naeher an der Solver-Wahrheit, NOTES.md) und
EV-seitig NEUTRAL bis leicht positiv (duplicate n=250: ON>OFF +50,5 ± 40,7; vs GTOBaseline −31,4 ± 58).

**Allein benutzbar?** Ja, aber nur mit dem halben Repo. Minimal noetig: `pokerbot/engine/*` (cards, evaluator,
equity), `pokerbot/config.py` (Pfad auf `knowledge_base/`), `strategy/{preflop_strength, ranges, postflop,
advisor, opp_model, opponent, blueprint, preflop_blueprint, gto_mode}` und die JSON/PT-Artefakte unter
`knowledge_base/`. Ohne Advisor-Netz und ohne Blueprints laeuft der Bot trotzdem — jede dieser Schichten hat
einen `available()`-Rueckfall auf die Heuristik. `tests/test_bot.py:14` zeigt das minimal noetige State-dict
zum Selbstbau.

**Fallstricke.** Der Baum ist **strikt Heads-Up**: `state["players"][1 - self.hero_idx]` steht ueberall
(z. B. bot.py:330, 630, 712, 1044) — an einem 3+-Spieler-Tisch liest er den falschen Sitz und wirft nicht,
sondern rechnet still falsch. Zweitens: `amount` ist ein **to-Betrag**, kein Erhoehungs-Delta; wer es als
Delta interpretiert, baut systematisch Min-Raises. Drittens: das Verhalten haengt an ~25 Umgebungsvariablen,
die zur **IMPORT-Zeit** gelesen werden (bot.py:32-105) — `gto_mode.apply()` bzw. `auslese.setze_env()` MUSS
vor dem Import laufen, sonst ist die Konfiguration halb an.

---

### Tiefengatter und Push-Fold-Schicht (Querschnitt durch `_preflop`)

`_preflop` (bot.py:264-317) verzweigt zuerst nach effektiver Stacktiefe. `_eff_stack` = Minimum ueber beide
Spieler von `stack + committed_total` (bot.py:1226-1227), geteilt durch `bb`. Daraus entstehen **drei Regime**:

1. **`eff_bb <= 14` → Push/Fold** (bot.py:278). `_pushfold` (bot.py:381-424) fragt den CFR-Blueprint
   `blueprint.pushfold(eff_bb, hand_class)` ab und behandelt drei Knoten: gegen einen All-In callen/folden nach
   der geloesten `call`-Wahrscheinlichkeit; SB first-in jammen/folden nach der `jam`-Wahrscheinlichkeit; BB gegen
   eine nicht-All-In-Erhoehung re-jammen, wenn das Perzentil ueber `1 - R.call_shove_fraction(eff_bb)` liegt.
   Fehlt die Blueprint-Datei, tritt der Perzentil-Rueckfall `R.push_fraction(eff_bb)` an ihre Stelle
   (bot.py:396, 415).
2. **`14 < eff_bb < bp_deep_min_bb (140.0)` → Heuristik-Kaskade.** Weder Push/Fold noch Blueprint feuern.
   Es spielt die Kette SB-first-in (Open top `R.SB_OPEN_FRAC = 0.84` zu 2,5bb) → BB-Option nach Limp →
   `_bb_vs_open` (Equity vs SB-Open-Range × Realisierungsfaktor 0,82) → `_vs_3bet` → `_deep_reraise`
   (Stack-Off nur ueber `deep_jam_pct = 0.985`). **Das ist das Regime, in dem 100-bb-Spiel stattfindet** —
   also die uebliche Cash-Game-Tiefe und z. B. die Kaggle-Arena (100 bb, docs/STATE.md:7).
3. **`eff_bb >= 140` → 200-bb-Blueprint** (bot.py:319-379), sofern `use_blueprint=True` und die Datei existiert.
   Liefert der Blueprint fuer den Knoten keine Verteilung, faellt der Code auf die Heuristik-Kaskade zurueck
   (`return None`).

Zwei Klemmen sitzen ueber dem Blueprint: `bp_jam_min_pct = 0.90` verbietet Jam/5bet-Bluffs unterhalb der
Top-10 % an den Knoten 4BET/5BET (der Checkdown-Solve ist blockerblind und wuerde 76s um 200 bb jammen,
NOTES.md:329), und `POKERB_GTOW_NOLIMP` renormalisiert die SB-Limp-Masse auf Open/Fold.

Das Tiefengatter ist eine **Ehrlichkeits-Grenze, keine Optimierung**: der Blueprint wurde bei 200 bb geloest,
darunter waere er ausserhalb seines Modells (NOTES.md:333-335 „100bb apps fall through to the heuristic").

---

### Flag- und Profil-Schicht (GTO-Mode / PRINCE) — `pokerbot/strategy/gto_mode.py`

**Zweck.** Ein import-reihenfolgesicherer Zugriff auf ~40 Verhaltens-Flags plus zwei benannte Profile, damit ein
gemessener Lauf reproduzierbar und als Fingerprint protokollierbar ist.

**Schnittstelle.**
- `flag(name: str, default: str) -> str` — Prioritaet: explizite Env-Variable > PRINCE-Profil > GTO-Mode-Profil >
  Default (gto_mode.py:114-125). Strategie-Module lesen ausschliesslich hierueber.
- `apply() -> bool` — expandiert die aktiven Profile per `os.environ.setdefault` in die Umgebung; muss VOR dem
  Import von `pokerbot.strategy.*` laufen.
- `enabled()` / `prince_enabled()` — Zustand der beiden Profil-Schalter.
- `fingerprint() -> dict` — der Env-Ausschnitt, der einen Lauf definiert (`_FINGERPRINT_KEYS`, gto_mode.py:72-97).
- Konstanten `PROFILE`, `PRINCE_PROFILE`, `FINAL_PROFILE`.

**Eingabe/Ausgabe.** Eingabe: `os.environ`. Ausgabe: Strings (die aufrufenden Module casten selbst nach
float/bool). `fingerprint()` gibt ein dict `{FLAG_NAME: wert-oder-None}` zurueck.

**Abhaengigkeiten.** Keine ausser `os`. Vollstaendig entkoppelbar — der einzige Grund, es zu uebernehmen, ist
das Muster.

**Zustand.** Zustandslos (liest `os.environ` bei jedem Aufruf). `apply()` mutiert die Prozess-Umgebung; ein Reset
verlangt einen neuen Prozess, weil die Konsumenten die Werte zur Import-Zeit einfrieren.

**Kosten.** Vernachlaessigbar (dict-Lookups).

**Mess-Status.** GEMESSEN POSITIV als Profil: `PRINCE_PROFILE` ist die einzige bei **AIVAT −19,70 ± 4,37
(n=2393, 0 Katastrophen, per-Hand-SD 214)** validierte Konfiguration (gto_mode.py:32-34). REFUTIERT als Stack:
die nach v2.2 hinzugefuegten Hebel (`POKERB_PURIFY`, `POKERB_RAISE_NARROW`, `POKERB_OVERBET_MENU`,
`POKERB_TURN_DEF_ADVISOR`, `POKERB_PAIR_DEFENSE`, `POKERB_RIVER_DEFENSE`) sind explizit ausgeschlossen, weil
ihr gestapelter v8-Zustand live auf **AIVAT −58** brach (gto_mode.py:56-66).

**Allein benutzbar?** Ja, eine Datei, keine Abhaengigkeiten.

**Fallstricke.** Die Reihenfolge. `apply()` nach dem ersten `import pokerbot.strategy.bot` ist wirkungslos fuer
alle Flags, die als Modul-Konstanten gelesen werden (bot.py:32-105) — ein halb-konfigurierter Bot, der still
falsch spielt. Der Kommentar in gto_mode.py:5-6 sagt das explizit; es ist trotzdem der am haeufigsten
dokumentierte Fehler im Repo.

---

### 200-bb-Preflop-Blueprint (near-Nash) — `pokerbot/strategy/preflop_blueprint.py`

**Zweck.** Laedt eine offline mit exaktem CFR+ geloeste Preflop-Strategie und bildet einen Live-Zustand
(Position, Anzahl Erhoehungen, All-In-Flag) auf einen von neun Blueprint-Knoten ab, aus dem die gemischte
GTO-Aktion gezogen wird.

**Schnittstelle.**
- `available() -> bool` — laedt die JSON lazy; `False` bei fehlender/kaputter Datei (Aufrufer faellt zurueck).
- `node_for_state(is_sb: bool, raises: int, can_check: bool, villain_allin: bool) -> str | None` — die reine
  Struktur-Abbildung auf `ROOT|LIMP|OPEN|ISO|3BET|4BET|JAMSB|5BET|JAMBB`; `None` = ausserhalb des Baums.
- `actions(node: str, hc: str) -> dict | None` — die geloeste Aktions→Wahrscheinlichkeits-Verteilung.
- `pick(node: str, hc: str, rng) -> tuple[str, dict] | None` — zieht eine Aktion aus der Mischung.
- `SIZES_BB: dict` — Aktion→Gesamteinsatz in bb (`limp 1.0, open 2.5, iso 4.5, 3bet 10, 4bet 24, 5bet 60`;
  unter `POKERB_GTOW_SIZES=1` stattdessen die bei GTO Wizard gemessenen 2.25/4.5/9/27/67.5, Zeile 34-37).

**Eingabe/Ausgabe.** Eingabe: Strukturmerkmale des Zustands plus die 169er-Handklasse ("AA", "AKs", "72o").
Ausgabe: `(aktion, verteilung)` mit Aktionen aus `fold|check|call|limp|open|iso|3bet|4bet|5bet|jam`. Datenquelle:
`knowledge_base/ranges/preflop_blueprint.json` (88 KB, 9 Knoten × 169 Klassen; unter `POKERB_GRAFT=1` stattdessen
`preflop_blueprint_solvergraft.json`).

**Abhaengigkeiten.** HART nur `pokerbot.config` (Pfad) und `gto_mode.flag`. Die JSON selbst ist der eigentliche
Wert; der Loader ist trivial nachbaubar.

**Zustand.** Zustandslos nach dem einmaligen Laden (Modul-globales `_BP`). Kein Reset noetig; ein Wechsel der
Datei zur Laufzeit ist nicht vorgesehen.

**Kosten.** Einmal ~88 KB JSON parsen, danach dict-Lookups. Nicht gemessen, aber offensichtlich vernachlaessigbar.

**Mess-Status.** UNGEMESSEN als EV-Hebel. Der vorgesehene Gate — GTOW-AIVAT-A/B `use_blueprint` ON vs OFF bei
n≥2500 — ist bis heute **DEFERRED**; es existiert nur ein richtungsweisender Lauf mit n=200 (docs/STATE.md:1585-1590,
NOTES.md:337). GEMESSEN wurde nur eine nicht-zirkulaere Nebenmetrik: die Exploitierbarkeit im vereinfachten
Preflop-Spiel faellt bei der solver-gepfropften Variante von 6,12 auf 2,03 (NOTES.md:380-386). VERIFIZIERT (Unit,
nicht EV): alle 9 Knoten-Abbildungen, All-In-Disziplin (QQ/AKo folden 200-bb-Jams zu 0,96; AA/KK callen),
Jam-Clamp und die robuste Shove-Erkennung (docs/STATE.md:1585-1589).

**Allein benutzbar?** Ja — mit der JSON und einer eigenen Handklassen-Normalisierung ist der Loader in 30 Zeilen
nachgebaut. Die Datei ist bei 200 bb geloest; fuer 100 bb existiert kein Aequivalent.

**Fallstricke.** `node_for_state` zaehlt `raises` als Anzahl aller Preflop-`bet|raise`-Eintraege in der History
(bot.py:1229-1231). Wer eine andere History-Semantik hat (z. B. Blinds als Bet gezaehlt), landet systematisch
einen Knoten zu tief — und dann gilt eine 4bet-Range fuer eine 3bet-Situation.

---

### Push-Fold-Blueprint-Loader — `pokerbot/strategy/blueprint.py`

**Zweck.** Serviert die CFR-geloesten Short-Stack-Jam/Call-Wahrscheinlichkeiten fuer die naechstliegende
geloeste Stacktiefe.

**Schnittstelle.**
- `available() -> bool` — laedt lazy, `False` bei fehlender Datei.
- `pushfold(stack_bb: float, hand_class: str) -> dict | None` — `{"jam": p, "call": p}` fuer die naechstgelegene
  geloeste Tiefe (`min(stacks, key=|x - stack_bb|)`, blueprint.py:29-31).

**Eingabe/Ausgabe.** Eingabe: effektive Tiefe in bb (float) und Handklasse (wird ueber
`cards.normalize_class` normalisiert). Ausgabe: zwei Wahrscheinlichkeiten. Quelle:
`knowledge_base/cfr/preflop_pushfold.json` (172 KB, Stacktiefen 2-20 bb × 169 Klassen).

**Abhaengigkeiten.** `pokerbot.config`, `pokerbot.engine.cards.normalize_class`. Beide ersetzbar.

**Zustand.** Zustandslos (Modul-Cache `_pf`).

**Kosten.** Einmal 172 KB JSON, danach zwei dict-Lookups. Nicht gemessen.

**Mess-Status.** GEMESSEN POSITIV gegen eine externe Referenz, NICHT gegen EV: die Ausgabe deckt sich fast exakt
mit veroeffentlichten Nash-Push-Fold-Charts (10 bb: SB jam ≈ 55 %, BB call ≈ 44 %; AA/KQo ≈ 100 %, 72o ≈ 0 %) —
`docs/archive/pluribus_and_benchmarking.md:30-33`. Die Datei selbst bestaetigt das
(10 bb: `AA {jam 0.999, call 0.999}`, `A5s {0.751, 0.735}`, `KQo {0.998, 0.995}`, `72o {0.0, 0.003}`). Ein
bb/100-A/B der Push-Fold-Schicht gegen die Perzentil-Heuristik ist UNGEMESSEN.

**Allein benutzbar?** Ja, das ist der am leichtesten herausloesbare Baustein des ganzen Repos: eine JSON plus
zwei Funktionen. Fuer einen Short-Stack-Turnierbot direkt verwendbar.

**Fallstricke.** Die naechstgelegene Tiefe wird ohne Interpolation genommen — bei 20,4 bb bekommst du die
20-bb-Loesung, bei 25 bb ebenfalls die 20-bb-Loesung (das Gatter in `bot.py:278` fuengt das ab, ein eigener
Aufrufer nicht). Und die Loesung gilt fuer das reine Jam-oder-Fold-Spiel: sie kennt keine Min-Raises.

---

### Push-Fold-CFR-Solver — `pokerbot/strategy/cfr_preflop.py`

**Zweck.** Erzeugt den obigen Blueprint per chance-sampled Counterfactual Regret Minimization ueber das
HU-Push-Fold-Spiel (SB jammt oder foldet, BB callt oder foldet) fuer jede Stacktiefe 2-20 bb.

**Schnittstelle.**
- `solve_stack(stack_bb: float, iters: int, rng: random.Random) -> dict` — loest EINE Tiefe, gibt
  `{klasse: {"jam": p, "call": p}}` zurueck.
- `main()` — CLI: `python -m pokerbot.strategy.cfr_preflop [--iters N] [--quick]`; schreibt
  `knowledge_base/cfr/preflop_pushfold.json` (nur ohne `--quick`).
- `_regret_match(regret, key, n)` — Standard-Regret-Matching (positive Regrets normalisiert, sonst uniform).

**Eingabe/Ausgabe.** Eingabe: Stacktiefe, Iterationen (Default 120 000), RNG-Seed (`random.Random(0)` in `main`).
Ausgabe: die JSON-Tabelle. Die Auszahlungen sind hart im Code (cfr_preflop.py:60-80): Fold → SB −0,5;
Jam+Fold → SB +1; Jam+Call → ±S auf den Showdown, mit `w = 1|0.5|0` aus einem gesampelten 5-Karten-Board.

**Abhaengigkeiten.** `pokerbot.engine.cards` (make_deck/hand_class/expand_class), `pokerbot.engine.evaluator`,
`preflop_strength` (nur fuer die Konsolen-Ausgabe), `pokerbot.config`.

**Zustand.** Zustandslos pro Aufruf; die Regret-/Strategie-Tabellen leben nur innerhalb von `solve_stack`.

**Kosten.** Nicht gemessen. Groessenordnung aus dem Code: 19 Tiefen × 120 000 Iterationen mit je einem
9-Karten-Sample und zwei Evaluator-Aufrufen — einmaliger Offline-Lauf, nichts fuer die Laufzeit.

**Mess-Status.** GEMESSEN POSITIV ueber die erzeugte Tabelle (siehe `blueprint.py` oben: Uebereinstimmung mit
veroeffentlichten Nash-Charts). Der Solver selbst hat keinen eigenen Konvergenz-Test im Repo → die
Konvergenz-Guete ist UNGEMESSEN.

**Allein benutzbar?** Ja, mit einem eigenen Hand-Evaluator. Es ist ein sauberes, kurzes, lesbares
CFR-Referenzbeispiel (98 Zeilen Kernlogik) — nuetzlich auch nur zum Lernen.

**Fallstricke.** Die BB-Regrets werden mit dem counterfactual Reach `sigma_sb[JAM]` gewichtet (cfr_preflop.py:77-86);
wer das beim Nachbau weglaesst, bekommt eine plausibel aussehende, aber falsche Call-Range.

---

### Preflop-Staerkemodell — `pokerbot/strategy/preflop_strength.py`

**Zweck.** Liefert fuer jede der 169 Handklassen die All-In-Equity gegen eine Zufallshand und daraus ein
kombinationsgewichtetes Perzentil — die Zahl, auf der praktisch jede Preflop-Heuristik des Bots steht.

**Schnittstelle.**
- `strength(hc: str) -> float` — Equity vs Random (0..1).
- `percentile(hc: str) -> float` — Anteil aller Kombinationen, die diese Klasse schlaegt (0..1, hoeher = staerker).
- `range_top(fraction: float) -> set[str]` — die staerksten `fraction` aller Haende als Klassen-Menge.
- `ranked_classes() -> list[str]` — alle 169 Klassen nach Staerke sortiert.
- Konstanten `ALL_CLASSES`, `COMBOS`, `TOTAL_COMBOS` (= 1326).

**Eingabe/Ausgabe.** Eingabe: Handklassen-String, wird ueber `normalize_class` normalisiert. Ausgabe: floats bzw.
`set[str]`. Cache: `data/preflop_strength.json` — fehlt die Datei, wird sie beim ersten Aufruf mit 4000
MC-Iterationen je Klasse berechnet und geschrieben (`_compute`, preflop_strength.py:24-30, `random.Random(0)`).

**Abhaengigkeiten.** `pokerbot.engine.cards`, `pokerbot.engine.equity.equity_vs_class_range`, `pokerbot.config`.

**Zustand.** Modul-global `_strength` / `_percentile`, einmal per `_ensure()` gefuellt. Zustandslos aus
Aufrufersicht; kein Reset noetig.

**Kosten.** Erster Aufruf ohne Cache: 169 × 4000 MC-Ziehungen (nicht gemessen, aber der Grund fuer den Cache).
Danach dict-Lookups.

**Mess-Status.** UNGEMESSEN als eigener Hebel. Ein bekannter, vom User gefundener Fehlerfall ist aktenkundig:
das Hot-and-Cold-Ranking **ueberschaetzt Offsuit-Asse** — A2o im CO gegen ein LJ-Open bekommt Perzentil 0,691
und wurde dadurch geflattet; der Gegenfix (`flat_guard`, im 6-max-Kern, nicht hier) misst gegen den alten Kern
+17,7 ± 6,4 / +11,4 ± 6,9 / +19,2 ± 7,0 bb/100 ueber je 2992 gepaarte Decks (docs/STATE.md, Block
„6MAX FLAT-FIX", 2026-09-09).

**Allein benutzbar?** Ja, vollstaendig — es braucht nur einen Equity-Rechner. Die erzeugte JSON ist eine
allgemein nuetzliche 169er-Tabelle.

**Fallstricke.** Ein Perzentil aus All-In-Equity vs Random ist **keine Spielbarkeit**. Genau das ist der oben
belegte A2o-Fall: dominierte Offsuit-Asse ranken hoch und spielen schlecht. Wer `range_top()` naiv als
Open/Call-Range benutzt, erbt diesen Fehler.

---

### HU-Range-Definitionen — `pokerbot/strategy/ranges.py`

**Zweck.** Definiert die Heads-Up-Preflop-Ranges als Perzentil-Baender auf dem Staerkemodell und stellt die
Kombinations-Expansion bereit, mit der jede Equity-Rechnung im Bot gefuettert wird.

**Schnittstelle.**
- Konstanten (ranges.py:16-22): `SB_OPEN_FRAC = 0.84`, `BB_3BET_VALUE_FRAC = 0.13`, `BB_DEFEND_FRAC = 0.66`,
  `SB_4BET_VALUE_FRAC = 0.075`, `SB_CALL_3BET_FRAC = 0.34`, `BB_CALL_4BET_FRAC = 0.06`,
  `BLUFF_BAND = (0.40, 0.60)`.
- Range-Funktionen `sb_open()`, `bb_3bet_value()`, `bb_defend()`, `bb_call_open()`, `sb_4bet_value()`,
  `sb_call_3bet()`, `bb_call_4bet()`, `bluff_band()` → jeweils `set[str]` von Handklassen.
- `push_fraction(eff_bb) -> float` / `call_shove_fraction(eff_bb) -> float` — die Perzentil-Rueckfaelle der
  Push-Fold-Schicht (Stufen 0,70/0,55/0,45/0,38/0,30 bei ≤6/8/10/12/sonst bb).
- `combos_for_classes(classes, dead) -> list[tuple[str,str]]` — expandiert Klassen zu konkreten Kombinationen
  und filtert tote Karten.
- `extracted_ranges()`, `match_grid(keywords, stack_bb)`, `grid_action(grid, hand_class)` — optionale
  Anreicherung aus extrahierten Buch-Grids (`knowledge_base/ranges/ranges_grids.json`).

**Eingabe/Ausgabe.** Ein/Ausgabe sind Klassen-Mengen bzw. Kombinationslisten `[("As","Kd"), ...]`. `dead` ist
eine Liste von Kartenstrings (Hole + Board).

**Abhaengigkeiten.** `preflop_strength` (hart — alle Baender sind Perzentile darauf), `pokerbot.engine.cards`,
`pokerbot.config` (nur fuer die Grids).

**Zustand.** Zustandslos; `_extracted` ist ein Lazy-Cache.

**Kosten.** `combos_for_classes` ist O(Klassen × Kombinationen) mit einer `sorted()`-Sortierung pro Aufruf und
wird in JEDER Preflop-Equity-Rechnung gerufen — nicht separat gemessen, aber der haeufigste Aufruf im Preflop-Pfad.

**Mess-Status.** UNGEMESSEN als Range-Kalibrierung (die Baender sind eine Setzung, kein Solver-Ergebnis).
GEMESSEN ist eine Korrektheits-Eigenschaft: die `sorted()`-Zeile in `combos_for_classes` (ranges.py:84) fixt einen
Determinismus-Bug — vor dem Fix wichen bei identischem Seed in zwei Prozessen **4 von 140 Aktionen** ab, weil die
Iteration ueber ein `set` PYTHONHASHSEED-abhaengig war (ranges.py:76-81); mit `PYTHONHASHSEED=0` waren es 0.
Die Schwester-Fassung in `engine/equity.py:123-126` nennt einen zweiten Beleg (gleicher Seed, drei Prozesse →
Hero-Platz 378/12/4 in einem 600er-MTT).

**Allein benutzbar?** Ja, sofern du `preflop_strength` mitnimmst. `combos_for_classes` allein ist ein nuetzlicher
30-Zeilen-Baustein.

**Fallstricke.** Genau der behobene Bug ist der, den ein Fremder beim Nachbau reproduziert: **niemals ueber ein
`set` iterieren, das eine Monte-Carlo-Reihenfolge bestimmt.** Ohne kanonische Sortierung sind gepaarte A/B-Tests
wertlos, und der Fehler ist unsichtbar, weil jeder einzelne Lauf plausibel aussieht.

---

### Solver-destillierte RFI-Tabelle — `pokerbot/strategy/preflop_gto.py`

**Zweck.** Nachschlagen einer aus 63k PokerBench-Preflop-Spots destillierten Open/Fold-Entscheidung (RFI,
unopened) je Position und Handklasse.

**Schnittstelle.**
- `rfi(pos: str, hand: str, min_n: int = 3) -> dict | None` — Rekord `{action, n, mix, raise_bb?}` oder `None`,
  wenn der Key fehlt oder die Stichprobe unter `min_n` liegt.
- `_table()` — `lru_cache`-Loader; fehlende Datei → leeres dict → alle Lookups `None`.

**Eingabe/Ausgabe.** Key-Schema exakt `"{pos}|0|none|none|0|{hand}"` (preflop_gto.py:27). Quelle:
`knowledge_base/ranges/preflop_gto_table.json` (1,1 MB, 17 034 Eintraege; Beispiel-Rekord
`BB|1|UTG|UTG|2|97s → {"action":"fold","n":3,"mix":{"fold":1.0}}`). `action` ist eines von
`raise|fold|check|call`.

**Abhaengigkeiten.** Nur `pokerbot.config`. Vollstaendig eigenstaendig.

**Zustand.** Zustandslos (`lru_cache(maxsize=1)`).

**Kosten.** Einmal 1,1 MB JSON parsen, danach dict-Lookup. Nicht gemessen.

**Mess-Status.** GEMESSEN gegen Held-out-Aktionen: **88,6 % Action-Match** auf zurueckgehaltenen PokerBench-Spots
(Docstring preflop_gto.py:2-3; bestaetigt in `docs/archive/BOT_PARTS_CATALOG.md:65`). Als EV-Hebel UNGEMESSEN —
und die verbleibenden 11,4 % sind im Repo explizit als moegliche High-EV-Blunder markiert
(`docs/archive/GTO_LEAK_LADDER.md:27`).

**Allein benutzbar?** Ja, das ist der einfachste Baustein hier: eine JSON und eine Lookup-Funktion.

**Fallstricke.** Das Modul ist **NICHT im HU-Bot verdrahtet**. Einziger Aufrufer im Repo ist
`pokerbot/arena/sixmax.py:170`, und dort nur fuer das Profil `tag` und nur fuer die unopened-Situation; die
Positionen werden vorher ueber `POS_RFI_BUCKET` zusammengefasst (`UTG+1/+2/+3 → UTG`, `LJ → HJ`,
sixmax.py:35). Wer die 88,6 % als „die Preflop-Strategie des Bots" liest, irrt: `bot.py` benutzt die
schwaechere Perzentil-Heuristik (`docs/archive/BOT_PARTS_CATALOG.md:27`).

---

### AUSLESE-Stack (der finale, gewickelte Bot) — `pokerbot/strategy/auslese.py`

**Zweck.** Die eine Quelle der Komposition des ausgelieferten HU-Bots: sie legt eine benannte Kette von
Guard-Wrappern um `PokerBot.decide` und setzt die zugehoerigen Import-Zeit-Flags.

**Schnittstelle.**
- `FINAL_STACK = "r8_stack"` (getauft `auslese-v5`), `RC_STACK = "r10_stack"` (v10-Release-Kandidat),
  `AUSLESE_ENV = {"POKERB_TURN_DEFENSE": "0.07", "POKERB_SLOWPLAY": "0.25"}`,
  `AUSLESE_ENV_RESOLVER_OFF` = dasselbe plus `POKERB_RAISE_NARROW=1.0`.
- `setze_env(resolver_on: bool = False) -> None` — setzt die Flags per `setdefault`; **vor** dem Import von
  `pokerbot.strategy.bot` aufrufen.
- `wickle_decide(pb, stack: str | None = None, kanal: str = "live") -> Callable[[dict], dict]` — gibt eine
  `decide`-kompatible Funktion zurueck, die das rationale-dict erhaelt und einen Guard-Eingriff mit
  `auslese_guard: True` markiert (auslese.py:72-79).

**Eingabe/Ausgabe.** Eingabe: eine `PokerBot`-Instanz, ein Stack-Name, ein Kanal (`"live"` = Deadline +
`os.urandom`-Seed, `"gym"` = deterministisch fuer gepaarte Gates). Ausgabe: dasselbe dict wie `decide()`,
gegebenenfalls mit ueberschriebenem `action`/`amount`.

**Abhaengigkeiten.** HART auf `pokerbot.autogym.pargate._wickle` (die Stack-Definitionen) und darueber auf
`pokerbot.autogym.improver` (die einzelnen Guards `sel_guard`, `turn_wert_guard`, `button_disziplin_guard`,
`river_wert_bremse`, `river_gpu_guard`). Diese Guards sind der eigentliche Inhalt und liegen ausserhalb von
`strategy/`. Imports sind bewusst lazy (auslese.py:29-31).

**Zustand.** Der Wrapper haelt ein `merker`-dict fuer die letzte Basis-Entscheidung (auslese.py:55). Er ist damit
**nicht nebenlaeufigkeitssicher** — eine Wrapper-Instanz je Sitz/Spiel.

**Kosten.** Nicht gemessen fuer die Wrapper selbst; der `river_gpu_guard` in v5 loest River-Subgames auf der GPU
(auslese.py:11-13), was die Latenz dieser Entscheidungen dominiert.

**Mess-Status.** GEMESSEN POSITIV im Gym-Spiegel, NICHT gegen GTOW: `wert_bremse` 3× repliziert
(+8,10 / +8,81 / +7,38, drei Baenke, perm_p 0,0002); `r8_stack` vs `r6_button` 3×30k gepoolt **+27,6 ± 1,8**
(alle p=0,0002); gegen die eingefrorene Basis **+30,60 ± 5,03**; A/A exakt 0 (auslese.py:6-10, Journal
`R7-REPLIKATION` / `R8-FINALE`). Der v4-Kern gegen Basis im Spiegel **+16,14 ± 2,77** (auslese.py:16-17).
**Ausdruecklich ohne externen Anker:** GTOW-bestaetigt ist nur v4-auf-PRINCE mit **−21,1** bb/100;
„v5 (r8_stack) hat Spiegel-Evidenz, kein Anker" (docs/STATE.md:52).

**Allein benutzbar?** Nein. Ohne `pokerbot/autogym/` ist die Datei eine leere Huelle — sie enthaelt nur Namen
und Flags, keine Strategie.

**Fallstricke.** Zwei bindende Regeln stehen im Docstring und sind beide gemessen erkauft: (1) `RAISE_NARROW`
ist bei eingeschaltetem Resolver **kontraindiziert** (v8-Befund K3) — deshalb laesst `setze_env(resolver_on=True)`
das Flag weg; (2) die Guards sind **HU-only** (2-Spieler-State-Ausdruecke) und duerfen nie in den Multiway-Kern
verdrahtet werden (auslese.py:16-18). Dazu der protokollierte Crash-Fall: `rationale` ist ein **dict**, kein
String — eine Konkatenation crasht exakt beim Guard-Eingriff (auslese.py:76-77).

---

## Gegner- und Range-Lesen

Dieses Subsystem beantwortet eine einzige Frage: *welche Hände kann der Gegner hier halten, und wie oft tut er was?*
Es besteht aus drei unabhängig verwendbaren Schichten — (a) statische Preflop-Prioren als Klassenmengen, (b) ein
per-Combo-Bayes-Tracker, der die Range entlang der beobachteten Betting-Line umgewichtet, (c) kleine Solver-imitierende
MLPs ("Advisor"), die dem Tracker die Likelihood `P(Aktion | Combo)` liefern. Dazu kommen zwei Gegner-Modelle
(aggregiert + per-Knoten-Dirichlet) und die Sizing-/Textur-Bibliothek, die aus einer gelesenen Range eine Betgröße macht.

Brauchst du das? Wenn dein Bot nur Equity-vs-Random rechnet: nein, dann ist das massiver Overkill. Wenn du einen Solver
(CFR/TexasSolver) zur Laufzeit fütterst oder Bluffcatch-/Thin-Value-Entscheidungen treffen willst: ja — ohne
rekonstruierte Villain-Range rechnest du gegen eine Fantasie-Verteilung, und genau das war in diesem Repo nachweislich
die Ursache eines −72-bb/100-Laufs (`docs/STATE.md:1093`).

Achtung vorab: fast alles hier ist **Heads-Up (2 Spieler)**. Der Tracker ist explizit HU-only
(`range_tracker.py:19`), die Guards darüber ebenso (`auslese.py:16-17`). Für 6-max gibt es nur die viel simplere
Variante in `pokerbot/arena/sixmax.py`.

---

### Preflop-Stärkemodell — `pokerbot/strategy/preflop_strength.py`
**Zweck.** Liefert für jede der 169 Handklassen die All-in-Equity vs. Zufallshand und daraus ein combo-gewichtetes
Perzentil, aus dem sich "die besten X % aller Hände" als Menge bilden lassen.

**Schnittstelle.**
- `strength(hc: str) -> float` — All-in-Equity der Klasse (z. B. `"AKs"`) vs. Random, aus MC berechnet/gecacht.
- `percentile(hc: str) -> float` — 0..1, Anteil aller Combos, die diese Klasse schlägt.
- `range_top(fraction: float) -> set[str]` — die stärksten `fraction` aller Hände (combo-gewichtet) als Klassenmenge.
- `ranked_classes() -> list[str]` — alle 169 Klassen nach Stärke sortiert.

**Eingabe/Ausgabe.** Rein Strings: Klassennamen im Format `"AA" | "AKs" | "AKo"`. Ausgabe float bzw. `set[str]`.
Der Cache liegt als `data/preflop_strength.json` (Klasse → Equity, 4 Nachkommastellen).

**Abhängigkeiten.** `pokerbot.engine.cards` (Klassen-Aufzählung/Expansion) + `pokerbot.engine.equity`
(`equity_vs_class_range`) — beide hart beim erstmaligen Berechnen, danach nur noch die JSON-Datei.
Ersetzbar: du kannst die JSON durch eigene Equity-Tabellen ersetzen, das Format ist trivial.

**Zustand.** Zustandslos nach außen; modulweite Lazy-Caches `_strength`/`_percentile` (`preflop_strength.py:20-21`),
einmal pro Prozess gefüllt. Nichts zurückzusetzen.

**Kosten.** Erstberechnung `_compute(iters=4000)` = 169 × MC(4000) — nicht gemessen, aber einmalig; danach
JSON-Load. Speicher: 2 × 169 Einträge.

**Mess-Status.** UNGEMESSEN als eigenständige Komponente (kein A/B; es ist eine Definitionsgrundlage, kein Hebel).

**Allein benutzbar?** Ja, praktisch dependency-frei nutzbar, sobald `data/preflop_strength.json` vorliegt — sonst
brauchst du zusätzlich den MC-Equity-Rechner der Engine.

**Fallstricke.** `range_top(f)` gibt die stärksten f **combo-gewichtet**, nicht f×169 Klassen; und die Ordnung ist
*Equity vs. Random*, nicht Spielbarkeit. `72o` und `A2o` liegen deshalb anders als in einer echten Openrange —
genau daran ist im Repo eine 6-max-Openrange aufgefallen (A2o wurde als Call eingestuft, Perzentil 0,691 > 0,665;
Commit `468bcc1`).

---

### Preflop-Range-Bibliothek — `pokerbot/strategy/ranges.py`
**Zweck.** Benannte HU-Preflop-Ranges (SB-Open, BB-Defend, 3bet-Value, …) als Klassenmengen plus der kanonische
Combo-Expander, den alle Range-Konsumenten benutzen.

**Schnittstelle.**
- `sb_open() / bb_defend() / bb_3bet_value() / bb_call_open() / sb_4bet_value() / sb_call_3bet() / bb_call_4bet() -> set[str]`
  — jeweils `range_top(<Konstante>)`-Ableitungen; die Konstanten stehen offen oben im Modul (`ranges.py:16-22`).
- `bluff_band() -> set[str]` — mittlere Hände (Perzentil 0,40–0,60) als polarisierte 3bet/4bet-Bluffs.
- `push_fraction(eff_bb) / call_shove_fraction(eff_bb) -> float` — Push/Fold-Breiten nach effektivem Stack.
- `combos_for_classes(classes, dead) -> list[tuple[str,str]]` — expandiert Klassen zu konkreten Combos, filtert
  Dead Cards, **sortiert die Klassen** vorher.
- `extracted_ranges() / match_grid(keywords, stack_bb) / grid_action(grid, hand_class)` — optionaler Abgleich mit
  aus einem Buch extrahierten GTO-Grids (`ranges_grids.json`); `grid_action` gibt `(action, freq)` oder `None`
  (= fold in diesen Charts).

**Eingabe/Ausgabe.** Klassenstrings rein, `set[str]` bzw. Combo-Tupel `("As","Kh")` raus. Grids sind Dicts mit den
Schlüsseln `label`, `villain_action`, `stack_bb`, `pure` (Liste `{hand, action}`), `mixed` (Liste
`{hand, actions:[{action, freq}]}`).

**Abhängigkeiten.** `preflop_strength` (hart), `engine.cards` (hart), `config.RANGES_DIR` für die Grid-JSON (weich —
fehlt sie, liefert `extracted_ranges()` `[]`).

**Zustand.** Zustandslos; ein Lazy-Cache `_extracted`.

**Kosten.** `combos_for_classes` über eine 85 %-Range = einige hundert bis ~1300 Tupel; nicht separat gemessen.

**Mess-Status.** GEMESSEN POSITIV (aber als Determinismus-Fix, nicht als EV-Hebel): das `sorted(classes)` in
`combos_for_classes` ist die Ursache dafür, dass Läufe reproduzierbar sind — vorher hing die Combo-Reihenfolge am
`PYTHONHASHSEED`, wodurch MC-Equity dieselben RNG-Ziehungen mit anderen Villain-Combos paarte und
Mixed-Strategy-Grenzentscheidungen zwischen identischen Läufen kippten: **4 von 140 Aktionen**, mit
`PYTHONHASHSEED=0` 0 Diffs (`pokerbot/strategy/ranges.py:77-81`).

**Allein benutzbar?** Ja. Minimal: `preflop_strength` + `engine.cards`.

**Fallstricke.** Die Range-Breiten sind **HU-Konstanten** (`SB_OPEN_FRAC = 0.84`). Wer sie ungeprüft für 6-max
benutzt, liest eine MP-Openrange von ~15–20 % als ~50 % — genau dieser Fehler ist in der PokerSnowie-Brücke
aufgetreten und wurde dort durch einen 6-max-Positions-Prior ersetzt (CLAUDE.md, Standbein 1).

---

### Range-Tracker (per-Combo-Bayes) — `pokerbot/strategy/range_tracker.py`
**Zweck.** Rekonstruiert für BEIDE HU-Sitze die Range am aktuellen öffentlichen Knoten, indem er den Preflop-Prior
entlang der beobachteten Postflop-Line mit `P(beobachtete Aktion | Combo)` umgewichtet.

**Schnittstelle.**
- `class RangeTracker(advisor=None)` — `advisor` ist ein Objekt/Modul mit `available(street)`, `p_bet(...)`,
  optional `p_bet_batch(...)`, `defense_available()`, `p_defense(...)`; `None` → lädt `strategy.advisor` lazy und
  degradiert auf legality-only, wenn torch/Modell fehlen.
- `RangeTracker.build(state) -> RangeTracker` — läuft Preflop-Prior + Postflop-Line ab; defensiv (jede kaputte
  History wird geschluckt, das Teilergebnis bleibt stehen).
- `RangeTracker.range: dict[int, dict[tuple[str,str], float]]` — Sitz → {Combo: Gewicht}, Summe 1.
- `RangeTracker.confidence(seat) -> float` in [0.2, 1.0] — `1 − CONF_SLOPE·heur_ratio`, gedeckelt auf 0,4 wenn die
  effektive Combo-Zahl (inverses Herfindahl) < 10 ist.
- `RangeTracker.emit(seat, dead) -> str` — die Range als **klassenweise gewichteter TexasSolver-String**
  (`"AQs:0.62,KQo:0.31,…"`, auf max=1 normiert).
- `weighted_ranges(state, advisor=None) -> (oop_str, ip_str, conf)` — Komfort-Wrapper; OOP = Nicht-Button.
- `river_ranges(state) -> (oop_str, ip_str)` — v1-Fallback: reine Klassenmengen nur nach Preflop-Raise-Anzahl.
- Konstanten: `WEIGHT_FLOOR=1e-6`, `EMIT_FLOOR=1e-4`, `CONF_THRESHOLD=0.5`.

**Eingabe/Ausgabe.** Eingabe ist ein State-Dict mit den tragenden Schlüsseln `button` (int), `board` (Liste
2-Zeichen-Karten), `history` (Liste von Zeilen mit `player`, `action` ∈ bet/raise/allin/check/call/fold/deal,
`street`, bei aggressiven Zeilen `to` = **street-kumulatives** Level), `players` (je `stack`, `committed_total`),
`bb`. Ausgabe: Combo→Gewicht-Dict bzw. Klassen-String + Confidence.

**Abhängigkeiten.** `strategy.advisor` (weich — ohne ihn wird jeder Schritt legality-only, die Range bleibt der
Prior), `strategy.ranges` + `preflop_strength` (hart, Prior), `engine.cards.hand_class` (hart),
`engine.evaluator.made_class` (nur im RAISE_NARROW-Pfad), `strategy.gto_mode.flag` (hart, Flag-Lesen).

**Zustand.** **Je Hand/je Aufruf**: der Tracker hat keine Snapshot-API. Der einzige Mechanismus, die Range zu einem
früheren Zeitpunkt zu bekommen, ist ein History-Schnitt plus kompletter Neubau (`docs/V10_FAKTEN.md:137-139`).
Instanzen werden im Bot pro Entscheidung neu gebaut (`bot.py:987`, `bot.py:1005`) — nichts persistiert, nichts ist
zurückzusetzen, aber es gibt auch keine Cross-Hand-Adaption.

**Kosten.** GEMESSEN: ein Neubau kostet **210 ms kalt / 7,2 ms warm** (`docs/V10_FAKTEN.md:138-139`). Der Löwenanteil
sind Advisor-Forward-Passes; `p_bet` war vor der Memoisierung **57 % der `decide()`-Laufzeit bei 196k Aufrufen**
(`pokerbot/strategy/advisor.py:78-80`). Speicher: ≤ 1326 Floats je Sitz.

**Mess-Status.** GEMESSEN POSITIV, mit einer bekannten Bruchstelle.
- Genauigkeit gegen Solver-Wahrheit (held-out): das `P(call)`-Update **halbiert den Range-L1-Fehler** gegenüber
  Nichtstun — flop +59 % / turn +60 % / river +47 % (`docs/STATE.md:1493-1496`, Werkzeug `check_range_l1.py`).
- Gegen die vorherige Heuristik (`_narrow` = "behalte Top-X % nach Boardstärke"): deren L1 war **0,756 bei
  ~0,995 für uniform-zufällig** (also fast wertlos), der aktionskonsistente Tracker **0,437 = +42 % näher an der
  Wahrheit** (flop +51 / turn +44 / river +30) (`docs/STATE.md:1508-1511`).
- End-to-end-Smoke: auf einer Turn-bet-call-Line schrumpft OOP von 658 auf 302 effektive Combos und die Confidence
  steigt 0,833 → 1,0 (`docs/STATE.md:1497-1498`).
- BRUCHSTELLE (historisch, teuer): weil `P(check)=1−P(bet)` multiplikativ pro Straße angewandt wurde, **invertierte**
  die Range nach check/check Richtung Luft; zusammen mit einem toten Confidence-Gate (Slope 0,5 floort exakt auf
  `CONF_THRESHOLD`) feuerte der Resolver in **93 %** der River-Entscheidungen auf einem falschen Gleichgewicht —
  dokumentiert als **−72 ± 6,70 bb/100 (n=2498)** (`docs/STATE.md:1093`). Gegenmittel sind die Knöpfe
  `TRACKER_ALPHA` (Dämpfung, Champion-Wert 0,5) und `TRACKER_CONF_SLOPE` (0,7) — beide im Profil
  (`pokerbot/strategy/gto_mode.py:19-20`).
- `TRACKER_AGGRO_FULL` (ab der 2. aggressiven Aktion eines Sitzes voll glauben, alpha→1): Gates bestanden,
  paired canary **+20,5 ± 42,5** — geshippt (`pokerbot/strategy/gto_mode.py:52`).
- `RAISE_NARROW` (Umgewichtung der Raise-Range auf den geminten GTOW-Mix): **im Analyzer-Kanal klar positiv**
  (v3.3 = 19,41 EV-Loss vs. Anker 24,90, `docs/STATE.md:724-726`) und **3× im envgate repliziert**
  (+16,8 / +13,7 / +9,2, `docs/STATE.md:240`) — **aber NUR resolver-OFF**. Mit laufendem Resolver ist der Hebel
  **KONTRAINDIZIERT**: die verengte Villain-Range vergiftet den Live-Resolver (v8-Befund K3), deshalb aus dem
  Produkt ausgeschlossen (`pokerbot/strategy/gto_mode.py:61`, `pokerbot/strategy/auslese.py:16-17`).
- `AUDIT_FIX` (zählt Raise als aggressive Aktion): **REFUTIERT** — v3.4 = 27,52 EV-Loss vs. Anker 24,90
  (+2,62 schlechter), dauerhaft default-OFF geparkt (`docs/STATE.md:725-726`).

**Allein benutzbar?** Ja, mit Einschränkung. Minimal brauchst du: `preflop_strength.json`, `ranges.py`,
`engine.cards`, ein State-Dict im obigen Format. Ohne `advisor` läuft er, macht dann aber ausschließlich
legality-only-Updates → die Range bleibt der Preflop-Prior und `confidence()` fällt auf 0,5 (bzw. unter das Gate,
wenn du die Slope hochdrehst). Der Nutzen kommt fast vollständig aus dem Advisor.

**Fallstricke.** Zwei, und beide beißen sofort.
(1) **`emit()` liefert KLASSEN-Gewichte, nicht Combo-Gewichte** — obwohl intern per Combo gerechnet wird. Grund
(im Repo verifiziert): TexasSolver v0.2.0 akzeptiert Per-Combo-Range-Strings nicht brauchbar, der Strategie-Dump
kommt leer zurück (`range_tracker.py:375-382`). Wer den Solver mit `"AsKh:0.6"` füttert, bekommt stumm nichts.
(2) **Der Tracker fragt den Advisor nach POSITION (`IP` iff `seat == button`), `bot.decide()` aber nach INITIATIVE**
(letzter Preflop-Raiser) — zwei verschiedene Konventionen auf demselben Netz (`range_tracker.py:179-180` vs.
`docs/V10_FAKTEN.md:133-136`). Das ist bekannt und wurde als Arm getestet (`ADVISOR_ROLE_POS` = 25,05 vs. 24,90 =
neutral, geparkt, `docs/STATE.md:726-728`) — aber wer den Tracker frisch verdrahtet, muss sich für EINE Konvention
entscheiden und sie überall durchziehen. Zusatz: `_p_call` fragt mit **fest 0,66 Pot** ab, die echte Bet-Größe wird
nicht durchgereicht (`range_tracker.py:163-169`); der Fehler geht dann bewusst Richtung "zu weit" (sicher), nicht
Richtung "zu eng".

---

### Solver-Frequenz-MLPs ("Advisor") — `pokerbot/strategy/advisor.py`
**Zweck.** Fünf kleine MLPs, die die Frequenz-Entscheidung eines Solvers pro Hand imitieren: `P(bet)` für
Flop/Turn/River und `(P_fold, P_call, P_raise)` gegen eine Bet — das Likelihood-Backend des Trackers und zugleich
die Bet-Frequenz-Quelle von `bot.decide()`.

**Schnittstelle.**
- `available(street="flop") -> bool` / `defense_available() -> bool` — ob torch + Checkpoint geladen werden konnten.
- `p_bet(hole, board, role, street="flop", pot_type=None) -> float | None` — Solver-`P(bet)` für genau diese Hand
  an diesem Knoten; `None` = Netz nicht verfügbar, Aufrufer muss auf Heuristik zurückfallen.
- `p_bet_batch(combos, board, role, street, pot_type=None) -> dict[tuple, float|None]` — ein Forward-Pass für viele
  Combos; teilt sich das Memo mit `p_bet`.
- `p_defense(hole, board, role, size_faced, street="flop") -> (P_fold, P_call, P_raise) | None` — `size_faced` ist
  die Bet-Größe als **Pot-Anteil**.
- `p_defense_batch(combos, board, role, size_faced, street) -> dict[tuple, tuple|None]` — dito gebatcht.

**Architektur (gelesen, nicht behauptet).** Alle Netze sind dasselbe Muster:
`Linear(d,64) → ReLU → Linear(64,64) → ReLU → Linear(64,1) → Sigmoid` für die Bet-Köpfe (`advisor.py:64-65`),
und `Linear(d,64) → ReLU → Linear(64,64) → ReLU → Linear(64,3)` + Softmax für den Defense-Kopf
(`advisor.py:173-174`). Der Feature-Vektor (`_vector`, `advisor.py:44-51`): Tier-One-Hot (air/medium/strong, 3) +
Textur-One-Hot (high/low/connected/monotone/paired, 5) + Rollen-Bit (IP) + 7 Bools (flush_draw, backdoor_flush,
nut_flush_blocker, made_straight, oesd, gutshot, has_draw) + `overcards/2` + `strength` (= `1 − treys_rank/7462`)
= 18 Dimensionen. Defense: + Street-One-Hot (3) + `size_faced` = 22. River-line-aware: + Pot-Typ-One-Hot
(srp/3bet/4bet) = 21. **Es gibt keinerlei Range-, Pot-, SPR- oder History-Information im Input**
(`docs/V10_FAKTEN.md:131-132`) — das ist die harte Decke dieser Köpfe.

**Welche Köpfe existieren.** `knowledge_base/postflop/`: `advisor.pt` (Flop, OOP=donk/IP=cbet), `turn_advisor.pt`
(Turn, lead/barrel), `river_advisor.pt`, `river_advisor_la.pt` (line-aware, 21-dim, nur mit `POKERB_RIVER_LA=1`
UND übergebenem `pot_type`), `defense_advisor.pt` (3-Output, flop+turn+river in EINEM Netz über das Street-One-Hot).

**Trainingsdaten.** Nicht aus Handhistorien, sondern aus dem **TexasSolver-Cache**: `research/build_advisor_data.py`
liest jede gelöste Board-Node, nimmt pro (board, role, combo) die Solver-Strategie und summiert die
BET/RAISE/ALLIN-Anteile zu `y = P_bet`; X = obiger Feature-Vektor. Training in `research/train_advisor.py`
(Flop), `train_turn_advisor.py`, `train_river_advisor.py`, `train_defense_advisor.py`, `train_river_la.py`
(River-Subgame-Solves je Pot-Typ, gebaut von `build_river_la.py`). **Held-out BY BOARD** und gegen zwei
Baselines gegated: kontext-kollabiert (Mittel je Textur/Größe) und strength-only (≈ Equity-Schwelle) —
wenn das Netz die strength-only-Baseline nicht um >3 % schlägt, wird die Tabelle geshippt statt des Netzes
(`research/train_defense_advisor.py:1-8`).

**Eingabe/Ausgabe.** `hole` = Liste zweier Karten-Strings, `board` = Liste 3/4/5 Karten, `role` = `"IP"`/`"OOP"`
(**case-sensitiv**, `docs/V10_FAKTEN.md:130`), `street` ∈ flop/turn/river. Raus: float bzw. Tripel bzw. `None`.

**Abhängigkeiten.** `torch` (weich — fehlt es, liefern alle Funktionen `None`, und der Tracker degradiert sauber),
die `.pt`-Dateien unter `config.KNOWLEDGE_DIR/postflop` (weich, gleiches Verhalten), `strategy.features`
(hart), `engine.evaluator.evaluate` (hart), `strategy.postflop.classify_board` für die Textur (hart, zirkulärer
Import wird lokal in `_texture` aufgelöst).

**Zustand.** Zustandslos im Ergebnis, aber **modulglobal gecacht**: `_NETS`, `_DEF` (Netze), `_PBET_MEMO`,
`_PDEF_MEMO` (je 120 000 Einträge, beim Überlauf komplett geleert, `advisor.py:82-84`). Zurückzusetzen ist nur
etwas, wenn du Netze austauschst oder die Batch-Identität testest (`advisor._PDEF_MEMO.clear()`, siehe
`tests/test_hero_range.py:366`). **Wichtig:** `RIVER_LA` wird zur **Import-Zeit** gelesen (`advisor.py:28`) —
Flags nach dem Import zu setzen wirkt nicht.

**Kosten.** GEMESSEN: `p_bet_batch` = ein Forward-Pass, **13/17/27 ms je Voll-Range** (flop/turn/river) gegenüber
**61–65 ms** bei Einzelaufrufen; `p_defense` einzeln **68–70 ms je Voll-Range** (`docs/V10_FAKTEN.md:127-129`;
das dort vermerkte "KEIN `p_defense_batch`" ist überholt — die Batch-Funktion existiert inzwischen,
`advisor.py:224`). Die Batch-Umstellung brachte im Gate insgesamt **2,2×** (`docs/STATE.md:302`).

**Mess-Status.** GEMISCHT, je Kopf verschieden — bitte einzeln lesen:
- Defense-Advisor (multi-street, held-out by board): schlägt strength-only um **flop +63 % / turn +46 % /
  river +18 %** (Gate-Bar war >+3 %) → PASS (`docs/STATE.md:1490-1491`). GEMESSEN POSITIV.
- River-Advisor: **+51 %** gegen die Frequenz-Baseline → **+38,6 ± 15,6 bb/100** gepaarte Floor-Verbesserung
  (`docs/STATE.md:1714-1715`). GEMESSEN POSITIV.
- Turn-Advisor (#41): **+8 bb/100, sub-1σ** → behalten, aber nicht signifikant (`docs/STATE.md:1713`). NEUTRAL.
- River-Blocker-Signal (#40): **0 Effekt** (`docs/STATE.md:1713`). NEUTRAL.
- **Defense-Advisor am RIVER im Floor: REFUTIERT** — Flop-Defense hob den Floor −70,7 → **−66,4** (+4,3,
  marginal), das Hinzunehmen der River-Defense drückte auf **−80,6 (−14 schlechter)**, zurückgedreht auf
  flop-only (`docs/STATE.md:1679-1681`). Deshalb steht in `bot.py:602` `_def_streets=('flop',)`, während der
  Tracker `p_defense` auf allen drei Straßen benutzt — dieser Unterschied ist Absicht.
- `RIVER_LA` (line-aware River): Training gut (held-out MSE 0,169 → 0,095 = +44 % vs. Frequenz-Baseline,
  1,52 M Zeilen), **Wirkung neutral**: GTOW-River-perfect 47,3 → 56,3 % ist survivorship-belastet, gepaartes
  realisiertes EV **+3,2 ± 5,0 = neutral**; Unterbetten nur halb gefixt (eq≥0,80 wird 33 → 47 % gebettet)
  (`docs/STATE.md:1094`). Default OFF im HEAD, aber `"1"` im GTO-Profil (`pokerbot/strategy/gto_mode.py:15`).
- Als Serve-Time-Hint an ein LLM: **REFUTIERT/NEUTRAL** — gepaartes A/B n=500/Arm, mit Advisor-Bet-Frequenz-Hint
  **−49,21 ± 29,00** vs. ohne **−49,52 ± 11,71**, Δ ≈ 0 (`docs/STATE.md:1118`).

**Allein benutzbar?** Ja, das ist die am leichtesten herauslösbare Komponente: `advisor.py` + `features.py` +
ein treys-Evaluator + die fünf `.pt`-Dateien. Ohne die Checkpoints ist es eine leere Hülle, die überall `None`
zurückgibt — die `.pt`-Dateien sind das eigentliche Asset und stammen aus dem eigenen Solver-Cache.

**Fallstricke.** Der Feature-Vektor **muss byte-genau dem Trainingsskript entsprechen** — Reihenfolge von
`TIERS`/`TEX`/`BOOLS`, `overcards/2`, `strength = 1 − rank/7462`, und beim Defense-Kopf zusätzlich, dass die
**Textur am FLOP-Board** (`board[:3]`) berechnet wird, nicht am aktuellen (`advisor.py:208`, `:248`). Eine
vertauschte One-Hot-Position produziert keinen Fehler, nur stille Unsinn-Frequenzen. Zweiter Fallstrick: die
Identitäts-Wache `research/advisor_batch_check.py:24` ruft die Rolle kleingeschrieben (`'ip'/'oop'`), damit ist
in beiden Armen das Rollen-Bit 0 — der IP-Pfad ist von diesem Test **nicht abgedeckt** (Beweislücke,
`docs/V10_FAKTEN.md:143-144`).

---

### Handfeatures (Blocker/Potential) — `pokerbot/strategy/features.py`
**Zweck.** Wandelt (hole, board) in die strategisch relevanten Merkmale um, die die Advisor-Netze fressen —
damit "55 % Equity" nicht mehr fungibel ist (Nut-Flush-Blocker ≠ verwundbares Top-Pair ≠ Combo-Draw).

**Schnittstelle.**
- `hand_features(hole, board) -> dict` — postflop only (board ≥ 3). Tragende Schlüssel: `made` (Klartext-Name der
  besten Fünf), `tier` ∈ {air, medium, strong}, `made_flush`, `flush_draw`, `backdoor_flush`, `nut_flush_blocker`,
  `made_straight`, `oesd`, `gutshot`, `overcards` (int 0–2), `has_draw`.
- `RANKS = "23456789TJQKA"` — die Rangreihenfolge, auf die sich alles bezieht.

**Eingabe/Ausgabe.** Karten als 2-Zeichen-Strings; raus ein flaches Dict. **Es wird eine flache Kopie
zurückgegeben** (`features.py:69`), damit ein mutierender Aufrufer den Cache nicht vergiftet.

**Abhängigkeiten.** `engine.evaluator.best_five_name` (hart, treys). Sonst nichts.

**Zustand.** Zustandslos; zwei modulglobale Memos: `_STRAIGHT_MEMO` (exakt und durch die Domäne — alle Teilmengen
von 13 Rängen — beschränkt) und `_FEATURES_MEMO` (60 000 Einträge, beim Überlauf komplett geleert).

**Kosten.** GEMESSEN: `_straight_outs` war **30 % der `decide()`-Laufzeit bei 10 M Generator-Aufrufen**,
`hand_features` wurde **241k× für 70 Entscheidungen** aufgerufen (über die Per-Combo-Advisor-Abfragen des
Trackers) — beides ist der Grund für die Memoisierung (`features.py:41-42`, `:58-60`).

**Mess-Status.** UNGEMESSEN als EV-Hebel (es ist eine Feature-Definition). GEMESSEN POSITIV als Performance-Fix
im Rahmen der `decide()`-Beschleunigung von 999 → 83 ms (12,1×, CLAUDE.md v3-Block, Commit `114e107`).

**Allein benutzbar?** Ja — die sauberste Einzeldatei des Subsystems, braucht nur einen 7-Karten-Evaluator.

**Fallstricke.** `tier` fasst Two-Pair und besser zu `"strong"` zusammen und jedes einzelne Paar zu `"medium"` —
ein Set über einem gepaarten Board und ein Bottom-Pair sind also im One-Hot nur zwei Stufen auseinander. Wer die
Netze auf feineren Tiers neu trainiert, muss `_vector` in `advisor.py` mit ändern (die Dimension `d` steckt im
Checkpoint).

---

### Aggregat-Gegnermodell — `pokerbot/strategy/opponent.py`
**Zweck.** Der billige Read über eine Session: VPIP, Fold-to-Bet, Aggression — mit Bayes-Shrinkage gegen einen
Prior, damit die ersten Hände nicht auf Rauschen exploiten.

**Schnittstelle.**
- `class OpponentModel()` — Zähler-Objekt.
- `record(street, action, facing_bet) -> None` — eine beobachtete Gegner-Aktion buchen.
- `end_hand() -> None` — Handzähler.
- `fold_to_bet_freq(k=6) / aggression_freq(k=6) / vpip(k=6) -> float` — geshrinkte Raten
  (`(gemacht + prior·k)/(n + k)`; VPIP-Prior 0,7 = HU-lose).
- `confidence() -> float` — `min(1, faced_bet/20 + pf_actions/30)`, skaliert die Exploit-Stärke.
- `summary() -> dict` — `{hands, vpip, fold_to_bet, aggression, confidence}`.

**Eingabe/Ausgabe.** Nur Primitive (Straßenname, Aktionsstring, bool). Raus Floats bzw. das Summary-Dict.

**Abhängigkeiten.** Keine. Pure stdlib, ~68 Zeilen.

**Zustand.** **Je Sitzung.** Alle Zähler leben bis zum Neu-Instanziieren; es gibt kein `reset()` — wer den Gegner
wechselt, baut ein neues Objekt. Im Bot hängt es an `PokerBot.opp` und wird über `observe_opponent` /
`observe_hand_end` gefüttert (`docs/TRAINER_PLAN.md:544`).

**Kosten.** Vernachlässigbar (Integer-Inkremente).

**Mess-Status.** UNGEMESSEN isoliert. Es ist der Eingang des Exploit-Pfads, dessen Gesamtverdikt weiter unten steht.

**Allein benutzbar?** Ja, vollständig; einfach kopieren.

**Fallstricke.** `record()` unterscheidet nicht nach Straße, wenn `facing_bet` gesetzt ist — Preflop-Folds gegen
einen Open landen im selben `fold_to_bet`-Topf wie River-Folds. Für eine ernsthafte HUD-Statistik ist das zu grob.

---

### Per-Knoten-Dirichlet-Gegnermodell — `pokerbot/strategy/opp_model.py`
**Zweck.** Eine Dirichlet-Posterior über die Gegner-Antwort (fold/call/raise) auf **unsere** Bet, geschlüsselt
nach einem groben Knoten-Bucket — die Datengrundlage des Exploit-Pfads.

**Schnittstelle.**
- `size_bucket(frac: float) -> str` — Pot-Anteil → `q|half|twothird|pot|big|over` (Grenzen `_SIZE_BINS`,
  `opp_model.py:17`); fängt bewusst auch Off-Tree-Größen zwischen Solver-Knoten.
- `node_key(street, role, line, board_class, size_frac) -> str` — `"street|role|line|board_class|bucket"`.
- `class OppModel(kappa=3.0)` — `observe(key, resp, w=1.0)`, `posterior(key, prior=(0.5,0.4,0.1)) -> ([P_fold,P_call,P_raise], n_eff)`,
  `save(path=None)`, `load(path=None)`.
- `seed_from_fold_curve(model, curve_path=None, street="river", n_eff=30.0) -> int` — impft die River-Buckets aus
  einer gemessenen Fold-Kurve `[size, fold_prob, n]` über alle Board-Klassen/Rollen; gibt die Zahl der geimpften
  Buckets zurück.

**Eingabe/Ausgabe.** Rein Strings + Floats. Persistenz als flaches JSON `{node_key: [c_fold, c_call, c_raise]}`
unter `data/opp_model.json`. `posterior` liefert Posterior-**Mittel** plus `n_eff` = Summe der *beobachteten*
Counts (der Prior zählt bewusst nicht mit — `n_eff` ist der Unsicherheitstreiber des LCB-Gates).

**Abhängigkeiten.** `pokerbot.config` nur für die Default-Pfade. Sonst **pure stdlib, kein numpy**.

**Zustand.** **Je Sitzung, optional persistent.** Counts akkumulieren über Hände hinweg; `save()`/`load()` machen
den Read gegen statische Gegner sitzungsübergreifend. Zurücksetzen = neues Objekt oder JSON löschen.

**Kosten.** Nicht gemessen; ein Dict-Lookup plus drei Additionen pro Query.

**Mess-Status.** siehe den gemeinsamen Exploit-Block unten. Das Modul selbst hat einen Self-Test
(`python -m pokerbot.strategy.opp_model`), der Cold-Start = Prior und "45 Beobachtungen → Over-Folder dominiert"
prüft (`opp_model.py:86-97`).

**Allein benutzbar?** Ja, trivial — 97 Zeilen ohne echte Abhängigkeiten.

**Fallstricke.** Der Namenskonflikt: es gibt eine **zweite, völlig andere `OppModel`-Klasse** in
`pokerbot/arena/sixmax.py:274` (ein Dataclass mit VPIP/PFR/3bet-Zählern für die 6-max-Liga). Wer den falschen
Import zieht, bekommt einen Typfehler an ganz anderer Stelle — das ist im Repo als bekannte Falle vermerkt
(`docs/TRAINER_PLAN.md:49`, `:354`).

---

### River-Exploit-Engine (LCB-Gate) — `pokerbot/strategy/exploit_engine.py`
**Zweck.** Wählt am River die EV-maximale Aktion gegen die Dirichlet-Antwortverteilung — aber nur, wenn eine
untere Konfidenzschranke über der Modellunsicherheit den Gewinn bestätigt; sonst spielt der Floor.

**Schnittstelle.**
- `action_ev(kind, size_frac, eq, pot, resp) -> float` — `EV_check = eq·pot`;
  `EV_bet = f·pot + c·[eq·(pot+bet) − (1−eq)·bet] + r·(−bet)` (ein Raise wird konservativ als "wir folden" bewertet).
- `choose_river(cands, floor_idx, eq, pot, eps_frac=0.30, z=0.5) -> (idx, mode, lam, evs)` —
  `cands` ist eine Liste `(kind, size_frac, resp|None, n_eff)`; `mode` ∈ `floor|mix|exploit`; `lam` ist die
  Wahrscheinlichkeit, mit der der Aufrufer die Exploit-Aktion tatsächlich spielt.
  Formel: `gain = EV(a*) − EV(floor)`; `LCB = gain − pot·z/√(n_eff+1)`; `LCB ≤ 0` → Floor;
  sonst `lam = min(1, LCB/(eps_frac·pot))`.

**Eingabe/Ausgabe.** Nur Zahlen; keine Karten, kein State. Das macht das Modul extrem gut testbar.

**Abhängigkeiten.** Nur `math`. Der Aufrufer (`bot.py:1162-1173`) liefert die `resp`-Tripel aus `OppModel`.

**Zustand.** Zustandslos.

**Kosten.** Nicht gemessen; O(#Kandidaten).

**Mess-Status.** siehe Exploit-Block unten. Der eingebaute Self-Test prüft die Sicherheitseigenschaft:
Cold-Start (n_eff=0) → Floor; bestätigter Over-Folder (n_eff=60) → Bluff; gut gesampelter Over-Caller (n=250) →
Thin Value (`exploit_engine.py:44-62`). Eine unabhängige Review bestätigte, dass die Schicht **GTO-neutral**
konstruiert ist — bei dünnen Daten fällt sie korrekt auf den Floor zurück (`docs/archive/GTO_GAP_REVIEW_2026-06-15.md:218`).

**Allein benutzbar?** Ja, 62 Zeilen, keine Abhängigkeiten. Das ist der sauberste "sicherer Exploit"-Baustein hier.

**Fallstricke.** `eq` muss die Equity **gegen die Call-Range** sein, nicht gegen die Gesamtrange — sonst
über-value-bettet die Formel systematisch. Und `n_eff` darf nicht den Prior enthalten, sonst schaltet das Gate
schon bei null Beobachtungen frei (`opp_model.posterior` gibt deshalb bewusst nur die beobachtete Summe zurück).

---

### ⚠ Exploit-Pfad — das gemeinsame Mess-Verdikt (opp_model + exploit_engine + adaptive + unified_exploit)
**Kurz: gegen einen leaky Pool druckt der Exploit-Pfad viel Geld; gegen einen Near-GTO-Gegner ist er NEUTRAL bis
schädlich, und die Hypothese, dass er die GTO-Abweichung des Bots verursacht, ist REFUTIERT.** Der geshippte
Champion fährt ihn deshalb **aus** (`"POKERB_EXPLOIT": "0"`, `pokerbot/strategy/gto_mode.py:13`).

Die Zahlen, einzeln belegt:
- **REFUTIERT (die Kernhypothese):** exploit-OFF sollte die GTO-Score anheben und die Frequenz-Differenz zu GTOW
  schrumpfen. Gemessen (Analyzer, n=1500, seed 55, vs. HEAD 53,4 % / 19,33 / 54,6 %): **GTO-Score 49,8 %
  (−3,6pp, schlechter) · EV-Loss 17,05 bb/100 (−2,28, besser) · Freq-Diff 54,57 % (FLAT, 54,6 → 54,57)** →
  die Frequenz-Abweichung ist **intrinsisch im Kern** (Blueprint + Advisors + Resolver), nicht vom Exploit-Overlay
  getrieben (`docs/STATE.md:977-983`).
- **NEUTRAL im gepaarten Self-Play-Gate:** exploit-OFF vs. ON = **+2,1 ± 3,3 bb/100** (`docs/STATE.md:314`).
- **POSITIV gegen den ausbeutbaren Pool** (das ist die Kehrseite, und sie ist gemessen): `PokerBot(exploit=ON)`
  schlägt jedes Liga-Profil, schlechtester Fall **+1 bb/100** gegen den starken Peer; station +493, maniac +757,
  sticky +393, trappy +161 (`docs/STATE.md:1790-1792`). Ältere Messreihe derselben Achse: station +109,
  maniac +224, nit +58, foldy +78, sticky +135, trappy +42; Mechanismus **+33 gegen eine steile Größen-Klippe**
  (`docs/STATE.md:1707-1709`).
- **`AdaptiveExploiter` = Über-Spezialisierung:** crusht Schwache am härtesten (+727/+1275), **verliert aber −47
  gegen den starken Peer**; Ursache knopfweise gemessen: seine BASIS-`decide()` ist schwächer als die von
  `PokerBot` (−56 mit allen Exploit-Knöpfen AUS) — kein falsch getuntes Gate (`docs/STATE.md:1794-1797`).
- **`unified_exploit.py` (62 Buchregeln → Nudges) ist DE FACTO TOT** für den spielenden Bot: erreichbar nur über
  `adaptive.py`, das kein App-/Live-Pfad benutzt (`docs/archive/BOT_PARTS_CATALOG.md:20-25`, `:89`). Es fahren
  ohnehin nur die 4 Regeln, deren Trigger-Statistik live gemessen wird (`vpip`, `aggression_freq`, `fold_to_bet`,
  `fold_to_cbet` — `unified_exploit.py:28`), der Rest ist hart abgeschaltet.

Praktische Konsequenz für einen fremden Entwickler: nimm `exploit_engine.choose_river` + `opp_model` **wenn dein
Zielpool ausbeutbar ist** (Micro-Cash, Freeroll, Bots). Baust du gegen einen Solver/Near-GTO-Gegner, spar dir die
Schicht — sie kostet dich dort messbar nichts und bringt dir messbar nichts, aber sie erzeugt Varianz.

---

### Bounded-Exploit-Overlays (Referenz, weitgehend orphaned) — `adaptive.py`, `unified_exploit.py`, `playbook.py`, `calibration.py`
**Zweck.** Der ältere, zweite Exploit-Stapel: ein eigener Bot (`AdaptiveExploiter`) mit Online-Fold-Kurve,
Probe-Controller, Knopf-Interface und drei Direktiv-Quellen (Buchregeln, LLM-Playbook, Live-LLM), die alle in
denselben gedeckelten Nudge-Kanal `{bluff, value, foldcatch}` münden.

**Schnittstelle (die tragenden Teile).**
- `adaptive.OpponentProfile` — `see_decision(street, la, action)`, `fold_at(size) -> float` (größen-gebucketete
  Fold-Kurve), `aggression()`, `vpip()`, `confidence()`, `summary()`.
- `adaptive.Knobs` (boolesche Steuerknöpfe je Exploit-Dimension), `adaptive.TwoModelGate.knobs(prof) -> Knobs`,
  `adaptive.ProbeController(budget_bb=40, max_frac=0.4, freq=0.12).consider(pot_bb, prof)` — unorthodoxe Testzüge
  nur bei bereits VORHERGESAGTER Schwäche, klein dimensioniert, gegen ein hartes Sitzungs-Risikobudget.
- `adaptive.AdaptiveExploiter(hero, seed, iters, knobs).decide(state)`; `observe_opponent`, `observe_hand_end`,
  `set_live_directive(directive)`, `refresh_llm_exploit(coach, context)`.
- `unified_exploit.nudge(stats: dict, postflop: bool, cap=0.2) -> dict` — aggregiert die feuernden Buchregeln zu
  `{bluff, value, foldcatch}`, jeder Kanal auf ±cap geklemmt; `{}` wenn nichts feuert.
- `playbook.directive_to_nudge(...)` — Cold-Start-Prior aus einem LLM-vorgerechneten Profil×Spot-Grid
  (`knowledge_base/exploit/playbook*.jsonl`), verblasst mit wachsender Live-Confidence.
- `calibration.Calibrator(name, path, half_life=300.0)` — loggt jede Wahrscheinlichkeits-VORHERSAGE, auf die wir
  gehandelt haben, gegen das später BEOBACHTETE Ergebnis; korrigiert systematischen Bias **selektionsbewusst**
  (nur in den Spots, in denen wir wirklich handeln), recency-gewichtet, pro Gegner persistiert.

**Eingabe/Ausgabe.** `unified_exploit.nudge` nimmt ein flaches Stat-Dict (nur die gemessenen Schlüssel, fehlende
Schlüssel = Regel aus) und gibt Kanal→Delta. Regeln kommen aus `knowledge_base/exploit/unified.json` mit den
Feldern `stat`, `condition` (`">0.6"`-Strings), `delta`, `magnitude` (small/medium/large → 0,10/0,20/0,30),
`confidence`, `spot`.

**Abhängigkeiten.** `adaptive` zieht `calibration`, `playbook`, `unified_exploit`, `ranges`, `preflop_strength`,
`engine.equity` — hart. `unified_exploit` und `playbook` brauchen nur `config` + ihre JSON/JSONL (weich: fehlt die
Datei, liefern sie leer).

**Zustand.** Je Sitzung (Profile, Probe-Budget, Kalibrator). Der `ProbeController` hat ein **Stop-Loss über die
Sitzung** — wer das Objekt nicht neu baut, spielt mit verbrauchtem Budget weiter.

**Kosten.** Nicht gemessen.

**Mess-Status.** REFUTIERT/ORPHANED als Produktweg (siehe Exploit-Block oben: −47 gegen den starken Peer, Basis
schwächer als `PokerBot`, `unified_exploit` für den Live-Bot unerreichbar). Der aus dieser Analyse gezogene
Schluss steht wörtlich im Repo: die SICHEREN Extras (Kalibrierung, Playbook-Cold-Start, LLM-Stratege) sollen auf
den robusten `PokerBot`-Floor portiert werden, **nicht umgekehrt** (`docs/STATE.md:1796-1797`).

**Allein benutzbar?** `unified_exploit.py` und `calibration.py` ja (klein, klar abgegrenzt). `adaptive.py`
(19 KB, eigener Bot) nur, wenn du seinen ganzen Unterbau mitnimmst — dann nimmst du aber auch seine gemessene
Schwäche mit.

**Fallstricke.** `unified_exploit._holds` prüft `">"` **vor** `">="` (`unified_exploit.py:45-51`) — eine Bedingung
`">=0.6"` fällt in den `">"`-Zweig und `float(">=0.6"[1:])` = `float("=0.6")` wirft `ValueError`, die Regel feuert
also stumm nie. Wer eigene Regeln mit `>=`/`<=` schreibt, bekommt keinen Fehler, sondern Schweigen.

---

### Postflop: Textur, Fold-Modelle und Sizing — `pokerbot/strategy/postflop.py`
**Zweck.** Klassifiziert Boards, modelliert die Fold-Frequenz des Gegners über die Bet-Größe und wählt daraus die
EV-maximale Bluff- bzw. Value-Größe — inklusive des range-basierten River-Sizers.

**Schnittstelle.**
- `classify_board(board) -> dict` — Flags `paired`, `monotone`, `twotone`, `connected`, `high`, `dynamic`.
- `flop_class(tex) -> str` — Mapping auf 6 Kategorien: `High_dry|Low_dry|High_dynamic|Low_dynamic|Paired|Monotone`.
- `cbet_policy(board, ip=True) -> (freq, size_frac)` — textur-konditionierte Flop-C-Bet aus `FLOP_CBET`
  (`postflop.py:100-107`, Quelle `knowledge_base/postflop/openai_strategy.json`); OOP: ~15pp seltener, größer.
- `ev_bluff(s, F) -> float` = `F − s·(1−F)`.
- `value_score(s, F, eq) -> float` = `F + (1−F)·(e_call·(1+2s) − s)` mit `e_call = max(0.10, eq − 0.25·s)`.
- `class PriorFoldModel(fold_to_bet=0.5, confidence=0.0).fold(street, s)` — GTO-Indifferenz `s/(1+s)`, verschoben
  um den Live-Read; ohne `GTO_FOLD_PRIOR` zusätzlich `+0.04` "sie folden zu viel".
- `class LearnedFoldModel(table, min_n=6, max_dist=None)` + `.load(path)` — gemessene Fold-Raten je (Straße, Größe);
  mit `max_dist` wird die gelernte Rate NUR nahe einem gemessenen Punkt benutzt, sonst GTO-Prior → der Exploit
  bleibt auf bewiesene Spots beschränkt.
- `pick_bluff_size(pot, model, street, hero_committed, hero_stack) -> (to_amount, ev, size_frac)`;
  `pick_value_size(...) -> (to_amount, score, size_frac)`.
- `snap_to_tree(bet_chips, pot, street=None) -> int` — rundet auf das GTOW-Größenraster;
  `snap_raise_to_tree(desired_to, call_level, pot, to_call, street) -> int` — Raise als Inkrement über dem Call,
  als Anteil des Post-Call-Pots.
- `pick_value_size_ecall(pot, hero_committed, hero_stack, hole, board, villain_w, hero_w)` — **River-Sizer aus den
  getrackten Ranges**: je Kandidatgröße wird villains CALLING SET exakt bestimmt (seine Combos mit Equity ≥ seinen
  Pot-Odds `s/(1+2s)` gegen unsere wahrgenommene Range), daraus kommen `F` und `e_call` aus DERSELBEN Verteilung.
- `thin_value_probe(...) -> (to_amount, e_call, call_share, size_frac) | None` — Selektionsgatter: bei der
  KLEINSTEN Größe ist die Call-Range am weitesten; schlagen wir nicht einmal die, existiert kein Thin Value.

**Eingabe/Ausgabe.** Chips als int, Größen als Pot-Anteil (float). `villain_w`/`hero_w` sind `{combo: weight}` —
genau das Format von `RangeTracker.range`. Ausgaben sind **Ziel-Beträge** (`to_amount` = street-kumulativ),
nicht Inkremente.

**Abhängigkeiten.** `strategy.gto_mode.flag` (hart), `engine.cards.RANK_ORDER` (hart),
`engine.evaluator.evaluate` (hart, nur im eCall-Pfad), der Range-Tracker (weich — ohne ihn liefert
`pick_value_size_ecall` `None` und der Aufrufer fällt auf `pick_value_size` zurück).

**Zustand.** Zustandslos, **aber alle Flags werden zur IMPORT-Zeit gelesen** (`ONTREE`, `GTOW_TREE`,
`RIVER_VALUE_FLOOR_EQ`, `AUDIT_FIX`, `_OVERBET_MENU` — `postflop.py:27,36,44,211,268`). Env-Variablen nach dem
Import zu setzen wirkt nicht; `gto_mode.apply()` muss davor laufen.

**Kosten.** `_ecall_rows` sortiert beide Ranges einmal und beantwortet dann jede Equity-Abfrage in O(log n) über
Präfixsummen (`postflop.py:298-310`) — River-only, weil dort exakt enumeriert werden kann. Absolut nicht gemessen.

**Mess-Status.** Teilweise sehr gut vermessen:
- **`ONTREE` (Bet-Snap auf {0.33, 0.5, 0.75, 1.0, 1.25}): GEMESSEN POSITIV/NEUTRAL → default AN.** A/B, 1000
  Hände je Arm + `duplicate.py`: GTO-Score 50,7 → **53,1**, EV-Loss vs. GTO 22,7 → **21,2**, realisiertes EV
  **neutral** (−59,2 vs. −60,6 bb/100, im Rauschen) (`pokerbot/strategy/postflop.py:22-27`; `docs/STATE.md:1085`).
- **River-Value-Floor (`POKERB_RIVER_VALUE`): DUAL-GATE UNEINIG.** GTOW-Grade **neutral** (River-perfect
  47,3 → 48,0; Mistake+Blunder 26,4 → 27,7 = leicht schlechter), gepaartes realisiertes EV
  **+23,0 ± 11,4 bb/100 vs. GTOBaseline (2σ Gewinn)** → eingestuft als *validierter, begrenzter Exploit*, nicht
  als GTO-Fix (`docs/STATE.md:1093`). Im HEAD default AUS, im GTO-Profil `0.75` (`gto_mode.py:14`).
- **`POKERB_RIVER_ECALL` (der range-basierte River-Sizer): GEMESSEN POSITIV**, paired canary **+133,8 ± 60**,
  also besser als 2SE → im Champion-Profil AN (`pokerbot/strategy/gto_mode.py:48`).
- **Flache Thin-Value-Frequenz (v3.1): REFUTIERT.** Analyzer gepaart **19,76 vs. 17,93** — GTOW bettet zwar 43 %
  der River-Paare, aber es **wählt aus, welche**; eine flache Frequenzuntergrenze verliert
  (`pokerbot/strategy/postflop.py:366-367`). Daraus entstand `thin_value_probe` (Selektion statt Frequenz).
- **`POKERB_OVERBET_MENU` (2,0×/2,5×-Value-Arme): Analyzer-Gewinn −4,82 NUR resolver-OFF**, die
  resolver-ON-Interaktion wurde nie getestet → aus dem Produkt ausgeschlossen (`pokerbot/strategy/gto_mode.py:62`).
- **`AUDIT_FIX` (u. a. Phantom-Size-Kandidaten im Sizer): REFUTIERT**, v3.4 = 27,52 vs. Anker 24,90
  (+2,62 schlechter) (`docs/STATE.md:725-726`) — obwohl die einzelnen Befunde plausibel waren. Steht als Warnung
  da: "die 9 Bugfixes waren verhaltenstragend".
- **Zwei echte Rechenfehler, gefunden und gefixt (im Code dokumentiert):** (a) `value_score` belastete die eigene
  Bet früher nur bei Verlusten, erstattete sie also bei Gewinnen — Steigung 3e−1 statt 2e−1, wodurch der Score
  in der Thin-Value-Zone `e_call ∈ (1/3, 1/2)` mit der Größe STIEG und Jams bevorzugte (`postflop.py:138-141`);
  (b) Kandidatgrößen, die der Stack nicht realisieren kann, mappen alle auf denselben All-in-Betrag, wurden aber
  mit ihrer PHANTOM-Fold-Rate bewertet — der Argmax feuerte All-in-Bluffs auf eine Fold-Rate, der der Gegner nie
  gegenübersteht (`postflop.py:206-221`, `:318-323`). Der Jam-Kandidat ist seither auf 2× Pot gedeckelt, weil der
  Sizer sonst handstärke-unabhängig 3,4× Pot jammte.

**Allein benutzbar?** Ja, gestaffelt. `classify_board`/`flop_class`/`cbet_policy`/`ev_bluff`/`value_score`/
`PriorFoldModel`/`LearnedFoldModel`/`snap_to_tree` brauchen nur `RANK_ORDER` und ein Flag-Stub. Die eCall-Funktionen
brauchen zusätzlich einen Evaluator **und** zwei getrackte Ranges — ohne Range-Tracker sind sie nicht benutzbar.

**Fallstricke.** Der eine, an dem jeder scheitert: **`pick_value_size_ecall` braucht `hero_w` = die Sicht des
GEGNERS auf UNSERE Range**, gefiltert **nur nach dem Board**, nicht nach unseren Holecards. Wer hier "unsere echte
Hand" oder eine hole-gefilterte Range einsetzt, baut genau den Bias ein, den `_tracked_ranges_both` vermeidet
(`postflop.py:292-294`, `bot.py:996-999`). Zweitens: die Funktion gibt bewusst `None` zurück, wenn *niemand*
callen würde — "alle folden" ist keine Value-Bet, diese Entscheidung gehört in den Bluff-Pfad
(`postflop.py:331-334`).

---

### Hero-Likelihood-Replay (K1, v10) — `pokerbot/strategy/hero_range.py`
**Zweck.** Rekonstruiert **unsere eigene** öffentliche Range am River-Beginn, ohne je unsere echten Holecards zu
lesen — damit ein Solver mit einer range-konsistenten Heldenverteilung gefüttert werden kann statt mit der
tatsächlichen Hand.

**Schnittstelle (Auswahl aus ~40 öffentlichen Funktionen).**
- `rekonstruiere(st0, guards=STANDARD_GUARDS, hero=None, advisor=None) -> K1Rekonstruktion` — der Hauptweg.
- `hero_range_river_start(st0, guards=…) -> dict` / `villain_range_river_start(st0, hero=None) -> dict` —
  bequeme Kurzformen, geben `{combo: weight}`.
- `range_state_river_start(...) -> RangeState` — mit Provenienz-Feldern (`herkunft='k1_likelihood'`,
  `hero_injiziert=False`).
- `knoten_liste(st0, hero) -> list[Knoten]` — die Hero-Entscheidungsknoten vor dem River (öffentlicher Zustand +
  beobachtete Aktion, beide Holes als `'??'`).
- `action_likelihoods(st_vor_aktion, seat, guards=…) -> …`, `knoten_modell(zustand, seat, guards=…) -> KnotenModell`
  mit `.likelihood(combo, beobachtet) -> float|None`.
- `Konvention(rolle_bet, size_faced, raise_modelliert)`; `K1_KONVENTION` (Initiative + echte Size) vs.
  `TRACKER_PARITAET` (Position + fest 0,66) — mit `guards=()` ist letztere byte-gleich zur Tracker-Hero-Range.
- `versions_hash(guards, konvention) -> str` — Fingerprint fürs Protokoll.

**Modell.** `r_river(h) ∝ r_0(h) · M_board(h) · Π_t π_exec(a_t | s_t, h)` über alle Hero-Aktionen vor dem River.
Drei Schichten: (1) Prior + Board-Maske exakt wie `RangeTracker`; (2) Basis-Likelihood aus denselben Advisor-Netzen
(gebatcht, ohne Nebenwirkung auf RNG oder Tracker); (3) die Guard-Transformationen als exakte Verschiebung von
Aktionsmasse je Combo (z. B. `turn_wert`: `π_exec(b*|h) = π_vor(bet|h) + 1_C(h)·π_vor(check|h)`).

**Eingabe/Ausgabe.** Ein State-Dict aus zwei möglichen Kanälen (Engine `HeadsUpGame.state()` oder Adapter
`gtow_to_state`); genutzt wird nur die Schnittmenge `player/action/street/to` + `deal.street`. Raus:
`{combo: weight}` bzw. `RangeState`/`K1Rekonstruktion` mit Protokoll.

**Abhängigkeiten.** `range_tracker` (hart — Prior, Board-Maske, Normalisierung), `advisor` (hart für die
Likelihood), `pokerbot.autogym.improver` (hart — `_spot_rng`/`_RANK_ORD` sind die Referenz für bitgenaue
Guard-Bedingungen), `engine.equity.equity_vs_weighted_range`, `strategy.contracts`, `knowledge_base.math.formulas`.
Das ist die am stärksten verzahnte Datei dieses Subsystems.

**Zustand.** Je Hand; kein persistenter Zustand. **INVARIANTE (im Modul bindend):** dieser Pfad liest NIE Heros
echte Holecards; gleiche öffentliche Historie + andere Hero-Hand → identische Range (durch Test abgesichert,
`hero_range.py:26-30`).

**Kosten.** Teuer. Die Guard-Bedingung `C(h)` ist ein CPU-MC mit `iters=160` **je hypothetischer Combo** — im
Live-Betrieb wurde die K1-Range mit **bis zu 5,7 s** gemessen (`docs/V10_GATES_REPORT.md:181`); das dominiert dort
den 7,5-s-Deadline stärker als der eigentliche Solve (`docs/V10_GATES_REPORT.md:201`).

**Mess-Status.** **VERFEHLT (Gate G3), gebaut aber nicht abgenommen.** Gegen ein exaktes Policy-Orakel gemessen:
Total-Variation **Mittel 0,2085 · p95 0,758 · max 0,876** gegen ein Budget von **0,02 / 0,05 / 0,10**; auch nach
Abzug des Orakel-Rauschbodens (0,095) bleibt die untere Schranke bei **Mittel 0,1446** — über allen drei Budgets,
und jede Guard-Klasse einzeln ebenfalls (`docs/V10_GATES_REPORT.md:21`, `:108`). Zusätzlich ein
**Support-Leck**: Heros tatsächliche Hand liegt in **21 von 64** Fällen außerhalb des K1-Supports (Masse 0), live
`hand_not_in_range` in 4/40 Fällen (`docs/V10_GATES_REPORT.md:63`, `:195`). Der Champion bleibt deshalb
`auslese-v5`; v10 ist **nicht** freigegeben (`docs/V10_GATES_REPORT.md:114`).

**Allein benutzbar?** Praktisch nein. Es hängt an Tracker, Advisor, dem Autogym-Improver und den
Contracts-Datenklassen. Als *Idee* (Range-konsistente Hero-Verteilung statt injizierter echter Hand) ist es
übertragbar; als Code ist es der am wenigsten herauslösbare Teil dieses Katalogs.

**Fallstricke.** Der dokumentierte Hauptgrund für G3: das **Advisor-Backend ist nicht die Basis-Politik**, die
tatsächlich gespielt wurde (`docs/V10_GATES_REPORT.md:213`). Wer aus einer Likelihood-Rekonstruktion eine Range
baut, muss die Likelihood aus der **wirklich ausgeführten** Politik ziehen — nicht aus einem Modell davon. Das ist
im Repo als bindende Hybrid-Doktrin festgeschrieben (CLAUDE.md, v10-Block, Regel 3).

---

### 6-max-Gegnermodell (die schlanke Variante) — `pokerbot/arena/sixmax.py`
**Zweck.** Das Pendant für Mehrpersonentische: pro Sitz ein Zähler-Objekt, das ausschließlich aus **öffentlichen**
Aktionen gefüttert wird, plus ein gedeckelter, konfidenzgegateter Read.

**Schnittstelle.**
- `class OppModel` (Dataclass, `sixmax.py:274`) — Felder `hands, vpip, pfr, tb, tb_opp, faced_bet, fold_bet,
  agg, agg_opp`; Methoden `fold_to_bet()` (erst ab `faced_bet ≥ 8`, sonst `None`), `threebet()` (ab `tb_opp ≥ 6`),
  `aggression()` (ab `agg_opp ≥ 8`).
- `SixMaxBot(seat, knobs, seed=None)` mit `self.opp: dict[int, OppModel]`; `new_hand(seats)`;
  `_read(obs) -> dict` — gibt gedeckelte Deltas wie `{"cont_bonus": …}` / `{"call_delta": ±0.07}` plus einen
  Text-`tag`; leeres Dict = spiel einfach das Profil.

**Eingabe/Ausgabe.** `obs` ist die Sitz-Beobachtung der Engine (`board`, `to_call`, `n_active`,
`preflop_raises`). Raus ein kleines Delta-Dict.

**Abhängigkeiten.** Nur die Engine-Beobachtung; keine Netze, keine Modelle.

**Zustand.** Je Sitzung pro beobachtetem Sitz; `new_hand(seats)` setzt den **Handzustand** zurück (aktive Sitze,
Aggressor, Straße), die Zähler bleiben absichtlich stehen.

**Kosten.** Vernachlässigbar.

**Mess-Status.** UNGEMESSEN als isolierter Hebel. Die Schwellen (`threebet > 0.11`, `aggression > 0.55` /
`< 0.30`) sind als Prioren gesetzt, nicht gemessen.

**Allein benutzbar?** Ja — wenn du 6-max baust und kein HU, ist das der realistische Startpunkt statt des
HU-Trackers.

**Fallstricke.** Die Mindest-n-Gatter (`≥8`, `≥6`, `≥8`) geben `None` zurück, nicht 0. Wer das nicht abfängt,
bekommt `TypeError` statt eines konservativen Reads. Und: dieselbe Klasse heißt wie
`pokerbot/strategy/opp_model.OppModel`, ist aber etwas völlig anderes (siehe dort).

---

### Nicht in diesem Repo: `robustheit.py`
Im Auftrag genannt, aber **in `C:\Users\hampe\Desktop\PokerB` existiert keine Datei mit `robust` im Namen außer
`research/runpod_solve_robust.sh`** (ein Shell-Skript für Solver-Läufe auf dem Pod, kein Strategie-Modul).
Die Datei `strategie/robustheit.py` liegt in einem **anderen** Projekt (`C:\Users\hampe\Desktop\Neuro-model`) und
gehört nicht zu diesem Bot. Sie ist hier nicht beschrieben, weil ich sie nicht als Teil dieses Codebestands
verifizieren kann.

---

### Wie die Teile im laufenden Bot zusammenhängen (Verdrahtungs-Karte)
Wer das nachbauen will, braucht die Reihenfolge — sie steht so in `pokerbot/strategy/bot.py`:

1. `bot.decide()` baut bei Bedarf einen frischen `RangeTracker` (`bot.py:987`, `:1005`) und nimmt die
   Villain-Range **nur**, wenn `confidence(v) ≥ CONF_THRESHOLD` — sonst `None`, und der Floor fällt auf die alte
   Heuristik zurück (`bot.py:977-993`). Das ist das o3-Sicherheitsprinzip: lieber zu weit als falsch eng.
2. Die Bet-Frequenz kommt je Straße aus `pf_advisor.p_bet` (Flop `bot.py:770-777`, Turn `:796-803`,
   River `:826-833` inkl. `pot_type` für den line-aware Kopf).
3. Am River zieht `_tracked_ranges_both` **beide** Ranges aus EINEM Tracker-Build (`bot.py:996-1013`) und füttert
   damit `postflop.thin_value_probe` (Selektionsgatter) und `postflop.pick_value_size_ecall` (Größe).
4. Für den Resolver wird `weighted_ranges(state)` als TexasSolver-Strings übergeben, wieder confidence-gegated
   (`bot.py:1043-1051`, `:1071-1078`, `:1098-1104`).
5. Der Exploit-Pfad (`opp_model.posterior` → `exploit_engine.choose_river`) sitzt daneben (`bot.py:1162-1173`) —
   im geshippten Profil aber ausgeschaltet.

Der billigste sinnvolle Ausschnitt für einen fremden Bot ist Punkt 1+2: Tracker + Advisor. Punkt 3 lohnt erst,
wenn deine Ranges nachweislich stimmen — der eCall-Sizer ist nur so gut wie die Verteilung, die du ihm gibst.

---

## Solver und Re-Solving

Dieses Subsystem beantwortet EINE Frage: "Was ist an genau diesem Postflop-Knoten, mit genau diesen beiden
Ranges, die Gleichgewichts-Strategie meiner Hand?" Es gibt dafuer zwei unabhaengige Rechenwerke — einen
externen CPU-Prozess (TexasSolver, Sekunden bis Minuten je Solve) und einen eigenen Tensor-CFR+ auf der GPU
(River/Turn, Millisekunden bis Sekunden) — plus die Wrapper, die deren Antwort in eine legale Engine-Aktion
uebersetzen. Du brauchst das NUR, wenn dein Bot postflop mehr will als Heuristik/Netz; ein Bot mit reinem
Advisor-/Blueprint-Postflop laeuft ohne jede Zeile davon.

### Aufrufkette und Kosten auf einen Blick (Quellen jeweils beim Modul)

| Wer ruft wann | Rechenwerk | Kosten je Solve |
|---|---|---|
| `bot.decide` → River, `use_resolver` | TexasSolver (`resolver.river_resolve`) | ~6 s, Median 5,8 s (docs/STATE.md:1093); Cache-Hit 0,02–0,03 s |
| `bot.decide` → Turn, `use_turn_resolver` | TexasSolver (`resolver.turn_resolve`) | ~6 s/Turn-Entscheidung (NOTES.md:49-50); Census-Messung 5,5 s (research/flop_feasibility.py:3) |
| `bot.decide` → Flop, `POKERB_FLOP_RESOLVER=1` | TexasSolver (`resolver.flop_resolve`) | 75,4 / 89,3 / 120,9 s (Timeout) — NICHT live-faehig |
| Guard-Wrapper im Big-Pot-River | GPU (`gpu_resolver.solve_spots` → `RiverCFRBatch`) | 209 ms/Spot (research/policy_oracle.py:26-29) |
| v10-Plan, ein Solve je River-Strasse | GPU (`river_plan.loese_plan` → `RiverCFRBatch` B=1) | Live gemessen 4,3 s erste Hand (river_plan.py:44-48) |
| Massen-Audit/Batch | GPU (`RiverCFRBatch` B=64..256) | 0,30 s/Spot amortisiert (docs/STATE.md:115-116) |

---

### TexasSolver-Treiber — `pokerbot/strategy/gto_oracle.py`

**Zweck (1 Satz).** Faehrt die mitgelieferte TexasSolver-Konsolenbinary als Unterprozess, liest den JSON-Dump
und liefert die GTO-Strategie eines Postflop-Knotens je Combo.

**Schnittstelle.**
- `available() -> bool` — existiert die Binary unter `SOLVER_DIR/console_solver.exe`.
- `solve(board, oop_range: str, ip_range: str, pot=20.0, eff_stack=100.0, bets=None, accuracy=0.5,
  max_iter=150, threads=8, allin_threshold=0.67, dump_rounds=2, timeout=180, keep_files=False, tag=None,
  mode='holdem') -> dict` — schreibt eine Eingabedatei mit der TexasSolver-Grammatik (`set_pot` /
  `set_effective_stack` / `set_board` / `set_range_oop` / `set_range_ip` / `set_bet_sizes …` / `build_tree` /
  `start_solve` / `dump_result`), startet `subprocess.run(cwd=SOLVER_DIR, timeout=…)` und gibt den
  Wurzelknoten des Dumps zurueck. `mode='shortdeck'` schaltet 6+ Hold'em per CLI-Flag.
- `strategy_for(node: dict, c1: str, c2: str) -> dict | None` — `{Aktionslabel: Wahrscheinlichkeit}` fuer eine
  konkrete Hand am Knoten; `None`, wenn die Combo nicht in der Range/nicht im Dump ist.
- `_parse_exploitability(stdout)` (intern, aber wichtig) — liest die letzte vom Solver gedruckte
  Exploitability und haengt sie als `data["_exploitability_pct"]` + `data["_solve_iters"]` an das Ergebnis.

**Eingabe/Ausgabe.** Rein: Board als Liste von 2-Zeichen-Karten (`['Qs','Jh','2h']`), Ranges als
TexasSolver-Range-STRINGS auf 169-Klassen-Ebene (`"AA,KK,AKs,AQs:0.5,…"`), Bet-Baum als Liste fertiger
`set_bet_sizes`-Zeilen. Raus: das geparste Dump-Dict; tragende Schluessel `strategy.actions` (Labels wie
`"CHECK"`, `"BET 66"`, `"ALLIN"`), `strategy.strategy` (`{"AsKd": [p1,p2,…]}`), `childrens` (Label → Kindknoten),
`node_type`, dazu unsere Zusaetze `_exploitability_pct`, `_solve_iters`, `_suit_map`.

**Abhaengigkeiten.** Hart: die Binary in `tools/TexasSolver-v0.2.0-Windows` (Pfad ueber `TEXASSOLVER_DIR`
ueberschreibbar) und `subprocess`. Weich: `pokerbot.engine.isomorph.canonical_board` — nur wenn
`POKERB_ISO_CACHE=1`. Sonst nur Standardbibliothek; ersetzbar durch jeden Solver, der einen
Strategie-Dump liefert (dann `strategy_for`/`childrens`-Form nachbauen).

**Zustand.** Zustandslos je Aufruf, ABER mit persistentem Disk-Cache: `data/_solve_cache/<sha1>.json`, Key =
sha1(board, beide Range-Strings, pot, eff, bets, accuracy, max_iter, dump_rounds, mode) — ohne Hole-Karten,
ohne History, also EIN Solve fuer alle Combos und Seeds desselben Knotens (`gto_oracle.py:58-62`). Der Cache
ist gemeinsamer Prozess-Zustand: im Repo aktuell 12.209 Dateien / 35 GB (gemessen 2026-09-10 per `du`). Zum
Zuruecksetzen: Verzeichnis loeschen oder `POKERB_SOLVE_CACHE=0`.

**Kosten.** Ein kalter River-Solve mit den Census-Armen ~6 s (docs/STATE.md:1093), Turn 5,5 s
(research/flop_feasibility.py:3), Flop-zu-Terminal 75–121 s (data/runs/verdrahtungs_debug_2026-08-17.json).
Cache-Treffer 0,02–0,03 s (dieselbe Quelle). Jeder gleichzeitige Solve ist ein eigener Prozess mit
~400–500 MB RSS (research/mass_solve.py:5-7).

**Mess-Status.** GEMESSEN POSITIV als Referenz: gegen unser unabhaengiges GPU-CFR auf identischem River-Spot
Frequenz-Deltas 0,007 / 0,000 / 0,001 und per-Combo-Korrelation **0,999** (docs/STATE.md:121-122,
`research/gpu_vs_texassolver.py`). Auf dem Turn dieselbe Kreuzvalidierung nur teilweise: OOP-Bet-Delta 0,031,
OOP-Call-Delta 0,000, Korrelation 0,944, aber IP-Bet-nach-Check 0,416 (unser CFR) vs 0,321 (TexasSolver) bei
beidseitig expl≈0 (NOTES.md:701-711) — eingeordnet als Gleichgewichts-SELEKTION zweier CFR-Varianten, nicht
als Bug (NOTES.md:712-726).

**Allein benutzbar?** Ja, das ist das isolierteste Modul des Repos. Minimal: die Binary, `board`, zwei
Range-Strings, `pot`, `eff_stack` — `python -m pokerbot.strategy.gto_oracle` faehrt eine Demo (Flop QsJh2h).
Kein Bot, keine Engine noetig.

**Fallstricke.** Die Range-Strings muessen EXPLIZITE Klassen sein: TexasSolver lehnt Offsuit-Kurzform mit `+`
mit „format not recognize" ab — und zwar ERST beim Solve, nach erfolgreichem `build_tree`
(research/flop_feasibility.py:24-26). Zweitens: `strategy` ist nur am gedumpten WURZELknoten je Combo
gefuellt, tiefere Knoten tragen `"strategy": null` (`gto_oracle.py:164-174`) — wer `dump_rounds` zu klein
waehlt, navigiert in ein leeres Dict.

---

### Solver-Binary — `tools/TexasSolver-v0.2.0-Windows/`

**Zweck (1 Satz).** Das mitgelieferte OSS-Postflop-Solverpaket (TexasSolver v0.2.0, Discounted-CFR-Klasse),
das der Treiber oben aufruft.

**Schnittstelle.** `console_solver.exe -i <eingabedatei.txt>` mit dem Arbeitsverzeichnis im Solverordner;
optional `--mode shortdeck`. Daneben liegt `TexasSolverGui.exe` (unbenutzt vom Code) sowie die
Unterordner `ranges/`, `parameters/`, `resources/`.

**Eingabe/Ausgabe.** Rein: eine Textdatei mit einer Kommandozeile je Zeile (Grammatik im Docstring von
`gto_oracle.py:8-13`). Raus: die per `dump_result <datei>` geschriebene JSON-Datei + Fortschrittszeilen mit
der erreichten Exploitability auf stdout.

**Abhaengigkeiten.** Keine Python-Abhaengigkeit; die Qt5-DLLs im Ordner gehoeren zur GUI, die Konsolen-Binary
laeuft ohne sie.

**Zustand.** Der Ordner ist Arbeitsverzeichnis: der Treiber schreibt `_oracle_in_<tag>.txt` /
`_oracle_out_<tag>.json` hinein und loescht sie in einem `finally`. Aktuell liegen dort 102 verwaiste
`_oracle_*`-Dateien (gemessen 2026-09-10) — Ergebnis abgebrochener Laeufe; harmlos, aber der Ordner waechst.
Gesamtgroesse 163 MB.

**Kosten.** Siehe Treiber. Speicher ~400–500 MB je gleichzeitigem Prozess (research/mass_solve.py:5-7).

**Mess-Status.** GEMESSEN POSITIV (Kreuzvalidierung 0,999, siehe oben). Zusaetzlich: der Short-Deck-Modus
wurde 2026-06-15 verifiziert (Solve konvergiert, Dump parst unveraendert durch `strategy_for`,
`gto_oracle.py:73-76`).

**Allein benutzbar?** Ja — es ist ein eigenstaendiges Fremdprodukt. Minimal: Windows-Binary + eine
Eingabedatei. Fuer Linux muessten `SOLVER_DIR`/`EXE` auf ein selbst gebautes `console_solver` zeigen.

**Fallstricke.** Das Arbeitsverzeichnis MUSS der Solverordner sein (relative Ressourcenpfade). Und: der
`timeout` unseres Treibers steckt NICHT im Cache-Key — ein Lauf, der ins Timeout lief, dumpt nichts, deshalb
ist das kein Korrektheitsproblem, aber ein Cache-Treffer und ein kalter Timeout-Lauf ergeben
UNTERSCHIEDLICHE Bot-Aktionen (Resolver-Strategie vs Floor). Genau deshalb stehen `POKERB_ISO_CACHE` und
`POKERB_SOLVE_CACHE` im Konfig-Fingerprint (`gto_mode.py:84-87`).

---

### Strassen-Resolver — `pokerbot/strategy/resolver.py`

**Zweck (1 Satz).** Uebersetzt den tatsaechlichen oeffentlichen Spielzustand in einen TexasSolver-Solve,
navigiert die gespielte Linie im geloesten Baum und zieht die GTO-Aktion unserer Hand.

**Schnittstelle.**
- `river_strategy(state, hole, board, pot, eff_stack, oop_str, ip_str, la, acc, iters, timeout) -> dict|None`
  — die VERTEILUNG am River-Knoten (rohes `{Label: p}`), verbraucht KEINE Zufallszahl.
- `river_resolve(..., rng, …) -> (action, amount) | None` — `river_strategy` + genau ein
  `rng.choices`; Byte-Identitaet zur Vor-Aufspaltung bewacht `tests/test_river_strategy_identity.py`.
- `turn_resolve(...) -> (action, amount) | None` — loest Turn+River zu Terminal, liest nur den Turn-Knoten.
- `flop_resolve(...) -> (action, amount) | None` — loest Flop+Turn+River zu Terminal (kein Value-Netz).
- Interne, aber wiederverwendbare Bausteine: `_street_actions(state, street)` (die Aktionen EINER
  Setzrunde), `_match_label(action, amount, node)` (Engine-Aktion → naechstliegendes Solver-Label),
  `_label_to_action(lbl, la)` (Label → Engine-Aktion + Chip-Betrag), `_inject_observed_sizes(...)` (die
  TATSAECHLICH beobachtete Villain-Groesse als zusaetzlichen Baum-Arm), `_prune_degenerate_arms(...)`
  (EVPA-artiges Streichen von Armen ab 85 % des Reststacks).

**Eingabe/Ausgabe.** Rein: `state` als Engine-Dict mit `history` (Eintraege `{action, street, player, to|amount}`)
und `board`; `hole` als 2er-Liste; `pot` = Pot am STRASSENBEGINN (nicht der aktuelle!); `eff_stack`;
`oop_str`/`ip_str` als TexasSolver-Range-Strings; `la` = das Legal-Actions-Dict der Engine
(`to_call`, `can_raise`, `is_bet`, `raise_max`). Raus: `("bet"|"raise"|"call"|"check"|"fold", betrag_oder_None)`
oder `None` = "spiel deinen Floor".

**Abhaengigkeiten.** Hart: `gto_oracle` (der Solve) und `gto_mode.flag` (Flag-Lesung). Der Aufrufer
(`bot.py:1037-1117`) liefert die Ranges aus `range_tracker.weighted_ranges` — ersetzbar durch jede Quelle,
die zwei Range-Strings + eine Konfidenz liefert; ohne gute Ranges ist das Modul nachweislich schaedlich
(siehe Mess-Status).

**Zustand.** Zustandslos. Der einzige gefuehrte Zustand ist die uebergebene `rng` (ein Sample je Aufruf) und
der Disk-Cache im Treiber.

**Kosten.** River ~6 s, Median 5,8 s je Entscheidung; mit Resolver AUS kostet dieselbe Entscheidung 83 ms
(docs/V10_FAKTEN.md:83-84, Verweis docs/STATE.md:1000). Turn ~6 s (NOTES.md:49-50). Flop 75–121 s
(Messung unten). Timeouts: Census-Profil River 90 s / Turn 150 s / Flop 240 s, kompaktes Profil 40/60/120 s
(`resolver.py:38-39,52,67-68,78`).

**Mess-Status.** Gemischt, und das ist der wichtigste Satz dieses Kapitels:
- REFUTIERT in der urspruenglichen Konfiguration: mit preflop-only-Ranges vs GTO Wizard **−72,06 ± 6,70
  bb/100 (n=2498)**, und der Floor OHNE Resolver lag bei **−70,73 ± 5,83** → statistisch identisch, der
  Resolver war NEUTRAL, der Verlust lag im Floor (docs/STATE.md:1640-1642). Das ist die einzige isolierte
  Live-A/B-Messung ON/OFF, die existiert.
- Die Ranges waren die Ursache: der Range-Tracker ist Voraussetzung, nicht Verfeinerung (NOTES.md:446-455).
  Mit Tracker-Ranges ist der Resolver Teil der spaeteren Live-Anker (−19,70 ± 4,37 bzw. ehrlicher
  −30,11 ± 5,51, docs/STATE.md:212-213) — aber NICHT isoliert gegen OFF gemessen.
- Feuerrate live: **93 % der River-Entscheidungen** (docs/V10_FAKTEN.md:79) — der Resolver IST die
  gespielte River-Politik, nicht ein seltener Zusatz.
- `flop_resolve`: REFUTIERT als Live-Hebel. Erstflug 0 von 3 Feuerungen, Latenz 120,86 s (Timeout) / 89,28 s /
  75,38 s, erreichte Exploitability der zwei fertigen Solves 8,47 / 8,67 % vom Pot (Ziel 0,6 klar verfehlt);
  die beiden konvergierten Solves gaben trotzdem `None`, weil Heros reale Hand (K5o, J8o) nicht in der
  emittierten 35-Klassen-Eigenrange stand (data/runs/verdrahtungs_debug_2026-08-17.json). Unabhaengig davon
  schon 2026-07-05: **49/50 Timeouts bei 300 s** (docs/STATE.md:913).

**Allein benutzbar?** Teilweise. `river_strategy`/`river_resolve` brauchen nur den Treiber, zwei
Range-Strings und ein `state`-Dict mit `history`+`board` in unserer Form — `research/smoke_weighted_resolve.py`
zeigt genau diesen Minimalaufruf. `_match_label`/`_label_to_action`/`_street_actions` sind ohne Aenderung
kopierbar.

**Fallstricke.** Der `pot`-Parameter ist der Pot am STRASSENBEGINN (`bot.py` rechnet
`pot − committed_street beider Spieler`), nicht der aktuelle Pot; wer den aktuellen uebergibt, loest ein
anderes Spiel und merkt es nie, weil `river_resolve` bei Fehlern still `None` liefert. Zweitgroesste Falle:
`hand-not-in-range` — die emittierten Ranges sind 169-KLASSEN-Strings (`range_tracker.emit`, NOTES.md:368-372),
die reale Hero-Hand kann fehlen, und dann ist jeder A/B-Arm byte-gleich zum Floor, nur mit Latenzsteuer.

---

### GPU-CFR-Kern — `pokerbot/strategy/gpu_cfr.py`

**Zweck (1 Satz).** Loest River- und Turn-Subgames als Vector-CFR+ ueber dichten 1326-Combo-Tensoren auf der
GPU, in Millisekunden statt Sekunden.

**Schnittstelle.**
- `combo_index(c1, c2) -> int` — kanonischer Index 0..1325 (Reihenfolge egal).
- `range_vector(cw: dict) -> Tensor[1326]` — `{('As','Kd'): gewicht}` → dichter float32-Vektor auf `DEVICE`.
- `showdown_matrix(board) -> (W[1326,1326], M[1326,1326])` — W = sign(score_i − score_j), M = Kompatibilitaets-
  maske (Karten-Removal steckt exakt in M).
- `build_river_tree(pot, eff_stack, bet_sizes=(0.35,0.75,1.5), raise_sizes=(2.7,), max_raises=2,
  invest0=(0,0)) -> Node` und `build_turn_tree(...)` — HU-Baeume, OOP handelt zuerst.
- `class RiverCFR(board, r_oop, r_ip, pot, eff_stack, **baum_kw)` mit `solve(iters=400)`,
  `avg_sigma(node) -> [1326, n_acts]`, `exploitability() -> float` (exakte Best Response, in % des Pots),
  `strategy_at_root() -> {act: Tensor}`.
- `class RiverCFRBatch(boards, r_oop[B,1326], r_ip[B,1326], pot, eff_stack, half=False, **baum_kw)` —
  B Subgames gleichzeitig, gleiche Baum-GEOMETRIE, freie Boards/Ranges; zusaetzlich
  `action_values(node, reach_opp, spieler) -> [B,1326,n_acts]` (EV je Aktion, beide Seiten spielen die
  Durchschnittsstrategie).
- `class TurnCFR(board4, r_oop, r_ip, pot, eff_stack, **baum_kw)` — Turn-Betting + Chance-Knoten + die 48
  River-Runouts als Batch-Dimension.
- `Node` mit `actor` (0=OOP, 1=IP, −1=Terminal), `acts` (Labels wie `"check"`, `"bet0.75"`, `"raise2.7"`,
  `"betjam"`), `kids`, `pot`, `invest` (Chips je Rolle seit Subgame-Start), `terminal`.

**Eingabe/Ausgabe.** Rein: Board als Kartenliste, Ranges als `[1326]`- bzw. `[B,1326]`-float32-Tensoren
(NICHT normiert — die Normierung passiert intern ueber die Maske), Pot/Stack als Chips. Raus: pro Knoten eine
`[1326, n_acts]`-Matrix Wahrscheinlichkeiten; Exploitability als Prozent des Pots.

**Abhaengigkeiten.** Hart: `torch` und `pokerbot.engine.gpu_eval` (`DEVICE`, `encode`, `score7` — der
vektorisierte 7-Karten-Evaluator, gegen die CPU-Referenz ordnungs-verifiziert). `DEVICE` faellt automatisch
auf CPU zurueck, wenn kein CUDA da ist (`gpu_eval.py:32`) — dann laeuft alles, nur langsam. Sonst nichts:
kein Bot, keine Engine-Zustaende.

**Zustand.** Je Instanz: die Regret- und Strategy-Sum-Tensoren an jedem Knoten. Eine Instanz = EIN Subgame
(bzw. ein Batch); zum "Zuruecksetzen" wirft man sie weg und baut eine neue. `solve()` ist kumulativ —
zweimaliges Aufrufen setzt die Iteration fort.

**Kosten.** `RiverCFRBatch` B=256: 100 % GPU-Auslastung, ~1000 Subgame-Iterationen/s, **0,30 s/Spot
amortisiert** (docs/STATE.md:115-116, RTX 3080 Ti). Ueber `solve_spots` gemessen 209 ms/Spot bei
max_batch=192, 215 ms bei 64 — bandbreiten-bound, die Batchgroesse bringt kaum etwas
(research/policy_oracle.py:26-29). Speicher: W und M sind je Board `[1326,1326]`-float32 (≈14 MB je Paar),
also linear in B — gemessen 5,3 GB Peak bei B=192, 2,7 GB bei B=64 (research/policy_oracle.py:36-38).
`half=True` (fp16 fuer W/M, {−1,0,1} exakt darstellbar) misst **+64 %** Durchsatz bei identischer
Exploitability, ist aber default AUS (gpu_cfr.py:271-274, docs/STATE.md:148).

**Mess-Status.** GEMESSEN POSITIV (Korrektheit, nicht bb): (1) Clairvoyance-Toy mit geschlossener Loesung
exakt getroffen — Bluff-Anteil 0,333 (Soll 1/3), Call-Frequenz 0,500 (Soll 1/2), Exploitability 0,014 % vom
Pot (docs/STATE.md:114-115, reproduzierbar mit `python -m pokerbot.strategy.gpu_cfr`); (2) Kreuzvalidierung
gegen TexasSolver auf identischem River-Spot: Korrelation 0,999, Deltas ≤0,007 (docs/STATE.md:121-122);
(3) Batch-vs-Einzel `max|dSigma|` im Selbsttest ~1e-7 (gpu_cfr.py Benchmark-Ausgabe). Turn-Stufe:
TEILWEISE — Korrelation 0,944, aber eine 0,095 grosse IP-Frequenzdifferenz (NOTES.md:701-711), erklaert als
Polytop-Selektion (NOTES.md:712-726), nicht als Fehler bewiesen.

**Allein benutzbar?** Ja, das ist neben `gto_oracle` der zweite sauber isolierte Baustein. Minimal:
`torch` + `pokerbot/engine/gpu_eval.py` + `gpu_cfr.py`. Der eingebaute Selbsttest laeuft ohne den Rest
des Repos.

**Fallstricke.** `avg_sigma` liefert bei Reach 0 eine UNIFORME Verteilung 1/n — das ist keine Strategie,
sondern die Abwesenheit einer Strategie. Wer sie als Politik liest, spielt an genau den Knoten, an denen
die eigene Range die Hand gar nicht enthaelt, gleichverteilten Unsinn. Das Repo hat dafuer eigens einen
Vertrag (`contracts.PolicyTable.undefiniert`, docs/V10_FAKTEN B10) und einen Fallback-Status
`hand_not_in_range`.

---

### GPU-River-Resolver — `pokerbot/strategy/gpu_resolver.py`

**Zweck (1 Satz).** Verpackt `RiverCFRBatch` zu einem benutzbaren Resolver: Ranges am River-Beginn
einfrieren, Spots nach Baum-Geometrie batchen, die gespielte Sequenz im geloesten Baum navigieren, Heros
Strategie am Frage-Knoten ausgeben.

**Schnittstelle.**
- `class RiverSpot(board, hero_w, vill_w, pot_river, eff_stack, hero_oop, seq, hero_hole, tag=None)` —
  `seq` ist eine Liste `(wer, kind, size_chips)` mit `wer ∈ {'hero','vill'}` und
  `kind ∈ {'check','bet','raise','call','fold'}`; die LETZTE Sequenz-Aktion ist die zu pruefende
  Entscheidung, navigiert wird bis davor.
- `solve_spots(spots, iters=300, max_batch=192, mit_evs=False, **baum_kw) -> list[dict|None]` — je Spot
  `{'acts': [...], 'sigma': [...], 'zusatz_norm': [...], 'expl': float, 'gespielt': kind, 'tag': …}`,
  optional `'ev_je_akt'`. `None` = Navigation oder Combo gescheitert.
- `spr_bucket(spr) -> float` — die Geometrie-Gruppierung (SPR-Buckets 0.25 … 10.0, `POT_NORM = 100`).
- Konstanten als Knoepfe: `HERO_MIN_GEWICHT = 0.02`, `DEFAULT_ITERS = 300`, `SPR_BUCKETS`.

**Eingabe/Ausgabe.** Rein: Ranges als `{('As','Kd'): gewicht}`-Dicts (nicht als Strings — anders als beim
TexasSolver-Pfad, hier gibt es KEIN 169-Klassen-Aliasing). Raus: die Strategie an Heros Frage-Knoten plus
`zusatz_norm` = der Zusatzeinsatz je Arm in POT_NORM-Einheiten; der reale Chipbetrag ist
`zusatz_norm/100 * pot_river`.

**Abhaengigkeiten.** Hart: `gpu_cfr` (und damit torch). Sonst nichts — der Aufrufer liefert die Ranges.

**Zustand.** Zustandslos; jeder `solve_spots`-Aufruf baut frische CFR-Instanzen.

**Kosten.** 209 ms/Spot (max_batch=192) bzw. 215 ms (64); VRAM 5,3 GB bzw. 2,7 GB
(research/policy_oracle.py:26-29,36-38). Achtung Skalierung: weil `_injiziere` jede Hero-Combo mit eigenem
Gewicht in die Range legt, bekommt JEDE Combo einen EIGENEN Solve — 1081 Combos ≈ 226 s je Knoten
(dieselbe Quelle). Das ist genau die Falle, die einen v10-Bauagenten 45 min haengen liess
(Journal V10-BAU-NEUSTART).

**Mess-Status.** GEMESSEN POSITIV als Werkzeug: loest und navigiert 571 von 571 River-Entscheidungen einer
echten GTOW-Nacht (docs/STATE.md:119-120); Selbsttest prueft Sigma-Summe = 1. Als STRATEGIE-Quelle nur
mittelbar gemessen — die bb-Zahlen haengen an den Guards unten.

**Allein benutzbar?** Ja, mit `gpu_cfr`. `python -m pokerbot.strategy.gpu_resolver` faehrt einen
synthetischen Spot durch. Man muss nur die eigene History in das `seq`-Format uebersetzen.

**Fallstricke.** Die Hero-Injektion (`HERO_MIN_GEWICHT = 0.02`) loest zwar das
`hand-not-in-range`-Problem des TexasSolver-Pfads, macht die Range aber HAND-ABHAENGIG — der geloeste Spot
ist nicht mehr derselbe fuer alle Combos. Das ist der Grund, warum der v10-Plan (`river_plan.py`) den
`gpu_resolver` bewusst UMGEHT und `RiverCFRBatch` direkt benutzt.

---

### River-GPU-Guards — `pokerbot/autogym/improver.py` (`river_gpu_guard`, `river_play_guard`, `_river_spot_und_frage`)

**Zweck (1 Satz).** Die zwei Wrapper, die den GPU-Solver tatsaechlich in die gespielte Politik einhaengen —
einmal als konservative Chirurgie (nur klare Fehler ueberschreiben), einmal als volles Spielen der geloesten
Politik.

**Schnittstelle.**
- `_river_spot_und_frage(st, frage_kind) -> (RiverSpot, pot_river) | None` — schneidet die History am
  River-Deal, baut daraus per `RangeTracker().build` beide Ranges, uebersetzt die River-Aktionen in
  Zusatzbetraege. Das ist der wiederverwendbare Unterbau.
- `river_gpu_guard(make_strat, min_pot_chips=3000, iters=150, p_max_basis=0.10, p_min_alt=0.70)` — ein
  Fabrik-Dekorator: aus `make_strat(seat) -> (st) -> (action, amount)` wird dieselbe Signatur, aber im
  River mit Pot ≥ `min_pot_chips` wird die Basis-Aktion ueberschrieben, wenn der Solver ihr
  p < 0,10 gibt UND eine Alternative p > 0,70 hat. Deterministisch, kein RNG.
- `river_play_guard(make_strat, min_pot_chips=3000, iters=150, half=False)` — spielt in denselben Spots die
  GELOESTE Mischung, gesampelt ueber einen `crc32`-Hash der LAGE (Karten/Board/Pot/History-Laenge), damit
  gepaarte A/B-Laeufe reproduzierbar bleiben.

**Eingabe/Ausgabe.** Rein/raus: das Gym-Zustands-Dict (`street`, `pot`, `current_bet`, `to_act`, `button`,
`players[].{stack, committed_street, hole, all_in}`, `history`, `board`) → `(action, amount)`, wobei `amount`
der Engine-Konvention "Raise-TO-Level" folgt.

**Abhaengigkeiten.** Hart: `gpu_resolver.solve_spots`, `range_tracker.RangeTracker`, das Gym-Zustandsformat.
HU-ONLY — die Zustandsausdruecke sind zweispielerig (`auslese.py:17-18`).

**Zustand.** Zustandslos je Entscheidung (der Range-Tracker wird je Aufruf neu aus der History gebaut — das
kostet, kauft aber Determinismus).

**Kosten.** Ein Solve je feuernder Entscheidung, also ~0,2 s GPU plus Tracker-Rekonstruktion. Der Live-Smoke
misst 13,5 s River-Kaltstart, weil dort TexasSolver-Resolver UND GPU-Guard gleichzeitig laufen
(„Doppel-Resolver", docs/STATE.md:146-147).

**Mess-Status.**
- `river_gpu_guard`: **GEMESSEN POSITIV, dreifach repliziert.** Der Stack `r8_stack` mit diesem Guard gegen
  seinen Vorgaenger: +29,92 ± 3,10 / +23,76 ± 3,07 / +29,23 ± 3,03 bb/100 (je 30k gepaarte Decks, drei
  disjunkte Baenke, alle perm_p 0,0002; gepoolt +27,6 ± 1,8), gegen die eingefrorene Basis +30,60 ± 5,03;
  A/A exakt 0 (`pokerbot/strategy/auslese.py:7-10`, Journal `TAUFE-AUSLESE-V5`). Achtung: das ist der
  SPIEGEL-Kanal (Self-Play gegen den eigenen Vorgaenger), kein GTOW-Anker.
- `river_play_guard`: **REFUTIERT/NEUTRAL — gedroppt.** play vs v5 +1,14 ± 2,78 (30k), der volle v8-Arm
  +3,91 ± 2,85 bzw. −1,23 ± 4,36, gepoolt ~+2,3 ± 2,4 = NEUTRAL; Postmortem `docs/V8_POSTMORTEM.md`:
  Kanal-Saettigung (die Chirurgie hatte die Klarfaelle bereits geerntet), Rest liegt in Indifferenz-Zonen
  (docs/STATE.md:96-104).
- Die Schwellen 0,10/0,70 sind nicht geraten: der GPU-Audit ueber 571 River-Entscheidungen fand
  check/fold solver-konform (p 0,86 / 0,83), **bet als schwaechste Klasse (p 0,45, 15 % klare
  Widersprueche)**, und die Desaster-Calls bekommen Solver-fold p > 0,95 (docs/STATE.md:123-125).

**Allein benutzbar?** Nur mit unserem Range-Tracker und unserem Zustandsformat. Die IDEE ist portabel und
billig nachzubauen; der Code selbst nicht.

**Fallstricke.** Legalitaet. Der 30k-Spiegel fand genau hier den Crash „Cannot bet/raise": der Solver-Ast
sagt „raise", aber die Engine erlaubt es nicht (Gegner all-in oder Stack ≤ to_call) — `river_play_guard`
prueft das explizit (`opp['all_in']`, `me['stack'] > to_call`) und faellt sonst auf den passiven Zweig.
Wer den Guard nachbaut und diese Pruefung weglaesst, bekommt Abstuerze in seltenen Spots.

---

### Turn-GPU-Guard — `pokerbot/autogym/turn_gpu.py`

**Zweck (1 Satz).** Dasselbe Chirurgie-Muster auf dem Turn, mit `TurnCFR` (Turn-Betting + 48 River-Runouts).

**Schnittstelle.** `turn_gpu_guard(make_strat, min_pot_chips=3000, iters=120, …)` — Fabrik-Dekorator wie
oben; `_turn_seq(hist_nach_deal, hero_seat)` und `_navigiere_turn(cfr, seq, skala)` sind die Turn-Varianten
der Sequenz-Uebersetzung und Baum-Navigation. Baum bewusst klein: `TURN_BETS=(0.75,)`,
`RAISE_SIZES=(2.7,)`, `MAX_RAISES=1`, River nur 0,75-Bet ohne Raise.

**Eingabe/Ausgabe.** Wie der River-Guard; `_turn_seq` liefert `None`, sobald ein weiterer Deal in der
History steht (der Guard feuert nie nach dem River-Deal).

**Abhaengigkeiten.** Hart: `gpu_cfr.TurnCFR`, `gpu_resolver.POT_NORM` und `gpu_resolver._injiziere`
(Hero-Injektion). HU-only.

**Zustand.** Zustandslos.

**Kosten.** Nicht separat als Zahl im Repo belegt; der Docstring benennt den 48-Runout-Batch als
Kostentreiber und der Selbsttest misst kalt+warm (`python -m pokerbot.autogym.turn_gpu`).

**Mess-Status.** REFUTIERT/zu leise: **feuerte 3 von 3904 Entscheidungen** — der Kanal ist zu duenn fuer ein
Verdikt (docs/STATE.md:105-106, „turn_gpu 3/3904 zu leise"). Die zugrunde liegende `TurnCFR`-Mathematik ist
nur teilweise kreuzvalidiert (Korrelation 0,944, IP-Frequenz-Differenz offen erklaert, NOTES.md:701-726).

**Allein benutzbar?** Ja im selben Sinn wie der River-Guard (Selbsttest vorhanden), aber ohne
gemessenen Nutzen.

**Fallstricke.** Die Schwelle `min_pot_chips=3000` auf dem TURN trifft fast nichts — wer das Muster
uebernimmt, muss die Feuerrate ZUERST messen, sonst misst er 3900-mal seine Basis und einmal Rauschen.

---

### Oeffentlicher River-Plan (v10 K2) — `pokerbot/autogym/river_plan.py`

**Zweck (1 Satz).** Ersetzt die entscheidungsweise, hand-abhaengige Chirurgie durch EINEN Solve je River-
Strasse mit oeffentlicher (hole-freier) Aktivierung und privater Randomisierung.

**Schnittstelle.**
- `ist_aktiviert(st, min_pot_chips=1500) -> (bool, pot_river)` — die oeffentliche Gate-Entscheidung, liest
  KEINE Hole-Karten.
- `loese_plan(st, hero_seat, hand_adresse, iters=150, …) -> GeloesterPlan` — der eine Solve am River-Beginn
  (`RiverCFRBatch` B=1, echter eff-Stack, KEIN SPR-Bucket, keine Hero-Injektion).
- `GeloesterPlan.verteilung(pfad, hole) -> (pfad, probs|None, labels)`, `.tabelle(pfad) -> PolicyTable`,
  `.im_support(hole) -> bool`.
- `navigiere(gp, st) -> Navigation` — exakter Chip-Vergleich mit `OFFTREE_TOLERANZ_CHIPS = 1`, KEIN stilles
  Snapping; off-tree → Fallback.
- `class RiverPlanFabrik(make_strat, min_pot_chips, iters, …)` — der eigentliche Wrapper, mit
  `aufwaermen()` (CUDA-Kaltstart 2–3 s vorziehen), `statistik(seat)`, `letzter_trace(seat)`.
- Konstanten: `BAUM_KW` (bet 0,35/0,75/1,5 + raise 2,7x + jam, max 2 Raises), `DEFAULT_MIN_POT_CHIPS = 1500`,
  `DEFAULT_ITERS = 150`, `LIVE_SOLVE_WORKER = 3`, `QUEUE_BUDGET_S = 3.0`.

**Eingabe/Ausgabe.** Rein: Gym-/Live-Zustandsdict. Raus: `(action, amount)` plus ein
`contracts.EntscheidungsTrace` je Entscheidung mit Status (`offtree`, `deadline`, `hand_not_in_range`,
`deadline_in_queue`, …) und Zeit-Attribution (`zeiten_ms.queue/ranges/solve/gesamt`).

**Abhaengigkeiten.** Hart: `gpu_cfr` (direkt, NICHT ueber `gpu_resolver`), `pokerbot.strategy.contracts`,
optional `pokerbot.strategy.hero_range` (K1) fuer die Hero-Range, sonst der Range-Tracker.

**Zustand.** Je Hand und Sitz: ein Plan-Cache (`CACHE_GROESSE = 16`), ein laufender Solve je Hand
(`_LaufenderSolve`), ein privater Seed (Gym: deterministisch aus `hand_adresse`; Live: `os.urandom`).
Zuruecksetzen = neue `RiverPlanFabrik`.

**Kosten.** Live gemessen (RTX 3080 Ti, 4 parallele Haende): mit 8 Solve-Threads 19,6 s/Hand und 0/4 Plaene
rechtzeitig, mit 1 Thread 4,3 s fuer die erste Hand und der Rest in der Queue (river_plan.py:44-48) — die
Solves serialisieren sich am GIL. Endkonfiguration nach Gate-Fix: 3 Threads, 3 s Queue-Budget, 12 s Deadline;
Nachmessung n=40 Plan-Pots: deadline 0/40, Plan gespielt 25/40, offtree 11/40, hand_not_in_range 4/40,
p99 10,15 s (docs/STATE.md:95-96).

**Mess-Status.** NEUTRAL im Spiegel, aber als Release **abgelehnt**. G5: r10 vs r8 auf 1968 gepaarten Decks
**+11,68 ± 10,85 bb/100**, CI95 [−9,39, +33,06], perm_p 0,156 = NEUTRAL (docs/V10_GATES_REPORT.md:23).
G4 (exakte Best Response gegen die feste Politik, 11 Holdout-Roots): der Plan ist in 11/11 Roots weniger
ausbeutbar, ΔE_H −113,0 ± 18,6 bb/100 — aber im GYM-Kanal, nicht live uebertragbar
(docs/V10_GATES_REPORT.md:22,39). **G3 VERFEHLT** (K1-Hero-Range TV 0,2085 statt ≤0,02) → Ship-Entscheid
„NICHT GTOW-reif" (docs/V10_GATES_REPORT.md:21,89). Und der harte Befund: alle drei Decks ≤ −100 bb
entstanden im FALLBACK auf die nackte Basis, nicht im Plan (docs/STATE.md:84-86).

**Allein benutzbar?** Praktisch nein — das Modul haengt an `contracts.py` (42 KB Vertraege), am Range-Tracker
und am Zustandsformat. Was ein Fremder mitnehmen sollte, sind die zwei Entwurfsregeln: oeffentliches Gating
und ein Solve je Strasse statt je Entscheidung.

**Fallstricke.** Der Fallback ist der gefaehrlichste Teil, nicht der Plan: wer bei off-tree/Deadline auf eine
ANDERE Politik zurueckfaellt als die, aus deren Range der Plan gerechnet wurde, spielt eine Mischpolitik, die
niemand bewertet hat — genau daher kamen die einzigen Katastrophendecks.

---

### Kreuzvalidierung — `research/gpu_vs_texassolver.py`, `research/gpu_vs_texassolver_turn.py`

**Zweck (1 Satz).** Stellt beide Solver auf denselben Spot mit ERZWUNGEN identischer Baum-Geometrie und
vergleicht Frequenzen und Per-Combo-Politik.

**Schnittstelle.** Beide sind Skripte mit `main()`: `python -m research.gpu_vs_texassolver` bzw.
`…_turn`. Konstanten oben in der Datei: `BOARD`/`BOARD4`, `OOP_CLASSES`, `IP_CLASSES`, `POT=100`, `EFF=75`.

**Eingabe/Ausgabe.** Rein: die Konstanten. Raus: Konsolenausgabe mit OOP-Bet-Frequenz, IP-Bet-nach-Check,
OOP-Call-vs-Bet je Solver, den drei Deltas, der Per-Combo-Korrelation und einem BESTANDEN/NICHT-Urteil bei
Delta < 0,05.

**Abhaengigkeiten.** Hart: beide Solver (`gto_oracle` + `gpu_cfr`) und `strategy.ranges.combos_for_classes`.

**Zustand.** Zustandslos.

**Kosten.** Ein GPU-Solve (600 Iterationen) + ein TexasSolver-Solve (accuracy 0.1, 400 Iterationen,
timeout 300 s).

**Mess-Status.** GEMESSEN POSITIV (River): Deltas 0,007 / 0,000 / 0,001, Korrelation 0,999
(docs/STATE.md:121-122). TEILWEISE (Turn): OOP-Delta 0,031, Call-Delta 0,000, Korrelation 0,944, IP-Bet
0,416 vs 0,321 (NOTES.md:701-711).

**Allein benutzbar?** Ja — es ist der billigste Weg, einen selbst gebauten CFR gegen eine unabhaengige
Referenz zu pruefen. Der Trick ist kopierbar: `eff_stack = 0,75 · Pot` laesst bei BEIDEN Solvern Bet-Size und
Jam zum selben einzigen Arm kollabieren, dadurch sind die Baeume beweisbar identisch.

**Fallstricke.** Ein Frequenz-Delta ist kein Fehlerbeweis. Zwei hochkonvergierte Solver desselben
Nullsummenspiels haben denselben WERT, aber duerfen an indifferenten Knoten verschiedene Frequenzen spielen
(Nash-Polytop). Der exakte Diskriminator steht in NOTES.md:708-710: die Strategie des einen Solvers in den
Baum des anderen laden und ihre Exploitability DORT messen — ~0 heisst Multiplizitaet, gross heisst Baum-Bug.

---

### Exakter Best-Response-Pruefstand — `research/river_br_pruefstand.py`, `research/policy_oracle.py`, `research/k3_roots.py`

**Zweck (1 Satz).** Bewertet zwei Hero-Politiken im SELBEN River-Root-Spiel mit einer exakten
Villain-Best-Response — die einzige Methode im Repo, die Ausbeutbarkeit misst statt bb zu zaehlen.

**Schnittstelle.**
- `k3_roots` — extrahiert je Quellhand genau einen Root (River-Beginn) aus den GTOW-Hand-Histories, samt
  Geometrie, live-treuem Engine-State und beiden Ranges; Splits `holdout` / `entwicklung`.
- `policy_oracle` — liefert die VERTEILUNG der tatsaechlich ausgefuehrten Bot-Politik je Hero-Combo an einem
  Knoten als `contracts.PolicyTable`, indem es den Stack analytisch zerlegt (Basis-`decide()` ueber S Seeds +
  die Guard-Regel als reine Funktion des Solver-Ergebnisses).
- `river_br_pruefstand` — `br_gegen_fest` (exakte Villain-BR gegen eine feste Hero-Politik,
  informationsmengen-treu), Spielwert-Klammer [L,U], lokaler Regret aus `RiverCFRBatch.action_values`.

**Eingabe/Ausgabe.** Rein: Hand-History-JSONL + ein Arm-Name. Raus: JSON mit ΔE_H (bb/Root und bb/100), ΔR,
Bootstrap-Obergrenzen, UNSUPPORTED-Zaehlern.

**Abhaengigkeiten.** Hart: `gpu_cfr`, `contracts`, `range_tracker`, der Bot selbst (fuer Arm A). Sehr eng an
unser Repo gebunden.

**Zustand.** Cache je (root_hash, knoten_hash, kanal, S, stack, Code-Fingerprint) unter
`data/runs/v10/policy_oracle_cache/`.

**Kosten.** ~0,21 s GPU je Combo; ein voller Knoten mit 1081 Combos ≈ 226 s; der volle Holdout (224 Roots)
≈ 33 h kalt (research/policy_oracle.py:26-31, docs/V10_GATES_REPORT.md:39).

**Mess-Status.** GEMESSEN POSITIV als Werkzeug: Kontrollen 15/15 gruen (Matching Pennies, Karten-Fixture
≤1e-6, A/A exakt 0, Oracle-Identitaet 60/60 gegen das direkte `decide()` der vollen Kette,
docs/V10_GATES_REPORT.md:18). Als Messkanal noch UNVOLLSTAENDIG (11 statt 20 Roots, nur Gym-Kanal).

**Allein benutzbar?** Nein. Aber das PRINZIP ist der wichtigste Import dieses Kapitels: eine exakte BR gegen
die feste eigene Politik ist billiger und schaerfer als jeder bb-Spiegel — sie braucht keinen Gegner.

**Fallstricke.** Die Baum-Schliessung. Wenn Arm A Sizes spielt, die im Evaluationsbaum nicht existieren,
darf man sie NICHT auf den naechsten Arm projizieren (ein Review fand 8 % Pot Projektionsfehler: 0,67-Pot
wurde zu 0,75). Der Pruefstand fuegt stattdessen die exakten Arm-A-Betraege als zusaetzliche Arme ein und
markiert den Root sonst als UNSUPPORTED.

---

### Solver-Audit und Machbarkeitsmessung — `research/gpu_river_audit.py`, `research/flop_feasibility.py`

**Zweck (1 Satz).** Zwei Einmal-Werkzeuge: das eine gradet jede gespielte River-Entscheidung gegen den
GPU-Solver, das andere misst, ob ein Flop-Solve ueberhaupt bezahlbar ist.

**Schnittstelle.** Beides Skripte (`python -m research.gpu_river_audit`,
`python -m research.flop_feasibility`). `gpu_river_audit` liest die Hand-Histories, baut je Hero-River-Aktion
einen `RiverSpot`, batcht nach Geometrie und gibt (1) die Verteilung von p(gespielte Aktion), (2) die klaren
Abweichungen (p_gespielt < 0,10 bei Alternative > 0,70) mit Hand-IDs und realem Ausgang aus.
`flop_feasibility` timet ~50 REALE Flop-Spots aus den Session-Logs mit einem schlanken 3-Strassen-Baum.

**Eingabe/Ausgabe.** Rein: `data/sessions/gtow_hands_*.jsonl`. Raus: Konsolen-/JSON-Statistik.

**Abhaengigkeiten.** `gpu_resolver` + `range_tracker` bzw. `gto_oracle`; dazu die Replay-Helfer
(`research/gtow_tree_census.py`, `research/hh_luecken_mine.py`).

**Zustand.** Zustandslos (der Solve-Cache wirkt).

**Kosten.** Audit: 571 Spots, GPU-gesaettigt, laut Docstring $0 und deterministisch.
Machbarkeitsmessung: bis 50 × 300 s.

**Mess-Status.** Beide GEMESSEN und mit Konsequenz: Audit → 571/571 gegradet, check p 0,86 / fold p 0,83 /
**bet p 0,45 mit 15 % klaren Widerspruechen**, Desaster-Calls Solver-fold p > 0,95 (docs/STATE.md:123-125) —
daraus entstanden die Guard-Schwellen. Machbarkeit → **NO-GO: 49/50 Timeouts bei 300 s**
(docs/STATE.md:913), spaeter unabhaengig bestaetigt durch die 0/3-Feuerrate des gebauten `flop_resolve`.

**Allein benutzbar?** Nur mit unseren Logs. Das Muster („graded jede echte Entscheidung gegen einen
unabhaengigen Solver, bevor du eine Regel baust") ist der eigentliche Wert.

**Fallstricke.** Der Audit gradet gegen einen Solver, der mit REKONSTRUIERTEN Ranges gefuettert wird — ein
Widerspruch kann ein Politik-Fehler ODER ein Range-Fehler sein. Das Repo hat genau daran einen Kandidaten
verloren (r6_ecall).

---

### Massen-Solve — `research/mass_solve.py`

**Zweck (1 Satz).** Faehrt zufaellige Boards im Hintergrund durch TexasSolver und fuellt damit den
Disk-Solve-Cache (und einen Destillations-Datensatz).

**Schnittstelle.** `python -m research.mass_solve [minuten] [max_workers] [threads_je_solve] [min_free_mb]
[mb_je_solve]`.

**Eingabe/Ausgabe.** Rein: Laufzeit + Ressourcengrenzen. Raus: je Board eine atomar geschriebene
JSON-Datei im Cache; bereits gecachte Boards werden uebersprungen, Abbrechen/Neustart verliert nichts.

**Abhaengigkeiten.** Hart: `gto_oracle` + die Binary; `pokerbot.benchmark.gto_benchmark._IP/_OOP` fuer die
Ranges.

**Zustand.** Schreibt in den gemeinsamen Disk-Cache.

**Kosten.** RAM-adaptiv: jeder gleichzeitige Solve ist ein eigener Prozess mit ~400–500 MB; das Skript misst
den freien Speicher je Runde und faehrt nur so viele parallele Solves, wie ueber einer Sicherheitsschwelle
passen (mass_solve.py:5-9). Auf einer 16-GB-Box ist RAM, nicht CPU, die bindende Grenze.

**Mess-Status.** UNGEMESSEN als EV-Hebel. Belegt ist nur der Nebeneffekt: der Cache im Repo umfasst
12.209 Eintraege / 35 GB (gemessen 2026-09-10), und Cache-Treffer druecken einen 6-s-Solve auf 0,02–0,03 s
(data/runs/verdrahtungs_debug_2026-08-17.json).

**Allein benutzbar?** Ja, es braucht nur den Treiber und die Binary.

**Fallstricke.** CPU-Massensolve und ein GPU-Trainingsjob duerfen nicht auf derselben Maschine laufen — der
CPU-Job hungert den GPU-Job aus (CLAUDE.md „Heavy compute", mass_solve.py:2-3). Und: der Cache waechst
unbegrenzt; 35 GB fuer 12k Knoten sind ~3 MB je Solve.

---

**Abgrenzung.** `pokerbot/strategy/deep_cfr.py`, `deep_cfr_hunl.py`, `deepstack_leduc.py` und
`cfr_preflop.py` liegen im selben Verzeichnis, gehoeren aber NICHT zu diesem Subsystem: das sind
Self-Play-/Netz-Lerner bzw. ein Preflop-CFR, kein Re-Solving zur Entscheidungszeit. `pokerbot/brain/api.py`
enthaelt mit `solve_node`/`_run_solve` einen zweiten, unabhaengigen Aufrufpfad in denselben
TexasSolver-Treiber (fuer den LLM-Pfad, mit eigenem uuid-Tag gegen Datei-Kollisionen bei parallelen Solves).

---

## AUSLESE-Guard-Kette

Die Guard-Kette ist eine Sammlung von **Dekoratoren um eine fertige Poker-Strategie**: jeder Guard nimmt eine
Strategie-Fabrik, ruft die Basis-Entscheidung ab und darf sie in genau EINEM eng umrissenen Knoten ueberschreiben
(z. B. „River-Bet mit mittelstarker Hand wird Check"). Du brauchst das Subsystem, wenn du eine bestehende Bot-Logik
schrittweise und **messbar** verbessern willst, ohne ihren Quelltext anzufassen — nicht, wenn du eine Strategie von
Grund auf baust. Der eigentliche Wert liegt weniger im Code (jeder Guard sind 20–60 Zeilen) als in den Messungen: elf
der hier beschriebenen Guards sind gemessen NEUTRAL oder REFUTIERT, nur vier stecken im ausgelieferten Stack.

**Gemeinsamer Kontrakt (alle Guards, ohne Ausnahme).**
Signatur: `guard(make_strat, **schwellen) -> make(seat) -> decide(st) -> (action, amount)`.
`make_strat` ist eine Fabrik `seat:int -> callable(st)->(action, amount)`; der Guard baut seine Basis mit
`base = make_strat(seat)`, ruft in `decide` **immer zuerst** `a, amt = base(st)` und entscheidet danach, ob er
ueberschreibt. Aktionen sind Strings `"fold" | "check" | "call" | "bet" | "raise" | "allin"`; `amount` ist bei
`bet`/`raise` das **Street-Ziel-Level in Chips** (Engine-Konvention `game.py act`), sonst `None`. Hero ist immer
`st["players"][st["to_act"]]` — **nicht** ein `hero_idx`-Feld (`docs/V10_FAKTEN.md:171`, Abschnitt A5). Jeder Guard
kapselt seine Rechnung in `try/except Exception: pass`, d. h. im Zweifel bleibt die Basis-Aktion stehen — bequem,
aber ohne Log (siehe Fallstricke). `bb = 100` Chips, HU-Startstack 20 000 Chips = 200 bb.

**Der State (`st`), den jeder Guard liest** — erzeugt von `pokerbot/engine/game.py:290 state()`:
`street` (`"preflop"|"flop"|"turn"|"river"`), `board` (Liste 2-Zeichen-Karten `'As'`), `pot` (int, Chips, inklusive
des Einsatzes, der Hero gerade gegenuebersteht), `current_bet`, `to_act`, `button`, `sb`, `bb`, `hand_no`,
`history` (Liste von Dicts mit `player`/`action`/`street`/`to`/`amount`, dazu `{"action":"deal","street":...}`-Marken),
`players` (2 Dicts mit `hole`, `stack`, `committed_street`, `committed_total`, `folded`, `all_in`, `is_button`),
`legal`. `to_call` berechnet jeder Guard selbst als `max(0, st["current_bet"] - me["committed_street"])`.
Zusaetzlich injiziert das Gate `st["hand_id"]` (Deck-Adresse, `pokerbot/benchmark/duplicate.py:43-51`) — die Engine
selbst kennt kein `hand_id`.

---

### Guard-Rahmen + A/B-Gate — `pokerbot/autogym/improver.py`
**Zweck.** Haelt die Wrapper-Fabrik, den spot-gebundenen RNG, das gepaarte A/B-Gate und die Journal-Schreibung, die
alle einzelnen Guards teilen.
**Schnittstelle.**
`guarded(make_strat, guard_names: list[str])` (`:626`) — legt die in `GUARDS` registrierten Mini-Regeln um eine
Fabrik; feuert nur bei `to_call == 0`.
`GUARDS` (`:32`) — Whitelist der Regeln, die ein *beweisbarer* Orakel-Befund autonom scharfschalten darf. Enthaelt
genau einen Eintrag: `free_fold` = „fold bei to_call=0 wird zu check".
`_spot_rng(st) -> random.Random` (`:41`) — deterministischer RNG je Spot; Seed = `crc32` ueber
`sortierte Hole-Karten | Board | street | pot | current_bet | committed_street | len(history)`. Ohne ihn brechen
gepaarte Messungen (belegt: Transfer-Test SE 12,9 trotz identischer Decks, journal.jsonl:33).
`gate_ab(make_candidate, make_incumbent, n_decks, seed) -> dict` (`:649`) — spielt gepaarte Duplicate-Decks und
faellt das Urteil: `ANWENDEN` bei `bb100 - 2*se > 0`, `VERWERFEN` bei `bb100 + 2*se < -1`, sonst `NEUTRAL`.
`improve_round(hu_report, n_decks=150, seed=11, exploit=True) -> list[dict]` (`:664`) — eine Runde der Schleife:
P-Befunde des Orakels werden autonom gepatcht und einzeln gegatet, L/F-Befunde nur als Vorschlag ins Journal.
`_journal(entry)` (`:642`) — haengt einen Dict + Zeitstempel an `data/autogym/journal.jsonl`.
**Eingabe/Ausgabe.** `gate_ab` gibt `{"bb100", "se", "n_decks", "verdict"}`. `improve_round` nimmt einen
`OracleReport` (`.provable`, `.freq`, `.leads` mit `.rule`, `.proof`, `.severity_bb`) und gibt die Journal-Eintraege.
**Abhaengigkeiten.** `pokerbot.benchmark.duplicate` (`duplicate_ab`, `gen_decks`, `pokerbot`) — hart, aber trivial
ersetzbar (rund 90 Zeilen, siehe Eintrag *pargate*). `.oracle.OracleReport` — nur fuer `improve_round`, ersetzbar.
**Zustand.** Zustandslos. `_spot_rng` haelt bewusst KEINEN Zustand ueber Aufrufe (pro-Seat-Sequenzen haben die Arme
desynchronisiert, Kommentar `:44-47`).
**Kosten.** `gate_ab` = `n_decks` × 2 Haende, einkernig. Der parallele Ersatz (`pargate`) schafft 3 600–3 900
Decks/min bei 20–22 Workern (journal.jsonl:39, :52).
**Mess-Status.** UNGEMESSEN fuer `free_fold`/`guarded`: das Journal enthaelt **null** Eintraege vom Typ
`P-AUTOPATCH` (gezaehlt in `data/autogym/journal.jsonl`), im Pilotlauf war die P-Klasse leer („HART 0, P 0, L 35,
F 3", `CLAUDE.md`). Der autonome Patch-Pfad ist gebaut, aber nie ausgeloest worden.
**Allein benutzbar?** Ja. `gate_ab` + eine eigene Strategie-Fabrik reicht; `duplicate.duplicate_ab` braucht nur die
HU-Engine.
**Fallstricke.** Der `verdict`-Schwellenwert `-1.0 bb/100` ist eine bewusste *Nichtverschlechterungs*-Toleranz, kein
Signifikanztest — und `2*SE` ist bei diesen fettrandigen Verteilungen zu optimistisch. Nutze fuer echte Urteile
`pokerbot/autogym/stats.py:verdikt` (Bootstrap), nicht `gate_ab`.

---

### `podds_guard` — `pokerbot/autogym/improver.py:56`
**Zweck.** Ein River-Call wird zum Fold, wenn die Equity gegen eine **uniforme** Gegner-Range die Pot-Odds nicht deckt.
**Schnittstelle.** `podds_guard(make_strat, margin=0.02, iters=120)`. Trigger: `a == "call"` und `to_call > 0` und
`street == "river"`. Zieht 40 Zufalls-Combos aus dem Restdeck, schaetzt `equity_vs_range(..., iters=120)`; bei
`eq + margin < equity_needed_to_call(pot, to_call)` → `("fold", None)`.
**Eingabe/Ausgabe.** State-Dict rein, `(action, amount)` raus.
**Abhaengigkeiten.** `knowledge_base.math.formulas.equity_needed_to_call`, `pokerbot.engine.cards.make_deck`,
`pokerbot.engine.equity.equity_vs_range` — alle drei hart, aber je 1 Funktion und leicht selbst zu schreiben
(`equity_needed_to_call = to_call / pot`, wobei `pot` hier den Call bereits enthaelt).
**Zustand.** Zustandslos.
**Kosten.** 40 Combos × 120 MC-Iterationen je Trigger; nicht einzeln gemessen.
**Mess-Status.** GEMESSEN NEUTRAL: `+0,31 ± 0,31 bb/100` auf 800 Decks
(`data/autogym/journal.jsonl:17`, Typ `KANDIDAT-GATE`, Regel `podds_guard_river`, 2026-08-16).
**Allein benutzbar?** Ja, minimal: eine Equity-Funktion + Pot-Odds. Kein Range-Tracker noetig.
**Fallstricke.** Die uniforme Range ist auf dem River fast immer zu schwach → der Guard produziert Value-Folds. Die
inhaltliche Nachfolge-Version mit Tracker-Range (`river_ecall_guard`) wurde deshalb sogar REFUTIERT (−4,15). Wenn du
Pot-Odds-Disziplin willst, nimm die **exakte Enumeration** (`_river_eq_exakt`) und eine echte Range, nicht das hier.

---

### `mdf_guard` — `pokerbot/autogym/improver.py:86`
**Zweck.** Die Gegenrichtung zu `podds_guard`: ein Flop-Fold gegen einen Einsatz wird zum Call, wenn die Equity vs
eine uniforme Range die Pot-Odds deckt (Antwort auf den Orakel-Befund „Flop-Overfold 0,63 vs MDF-erlaubt 0,24").
**Schnittstelle.** `mdf_guard(make_strat, margin=0.0, iters=120, streets=("flop",))`. Trigger: `a == "fold"`,
`to_call > 0`, `street in streets`; bei `eq >= equity_needed_to_call(pot, to_call) + margin` → `("call", None)`.
**Eingabe/Ausgabe.** Wie oben.
**Abhaengigkeiten.** Identisch zu `podds_guard`.
**Zustand.** Zustandslos.
**Kosten.** 40 Combos × 120 MC-Iterationen je Trigger; nicht einzeln gemessen.
**Mess-Status.** GEMESSEN NEUTRAL, dreimal: `−17,09 ± 22,50` (1 200 Decks), `−3,26 ± 2,19` (99 000 Decks)
(`data/runs/STAND.md`, Laeufe `20260816_204741` / `20260816_204907`) und `−7,40 ± 28,39` (400 Decks,
`data/autogym/journal.jsonl:18`). Punktschaetzer durchweg negativ, nie signifikant.
**Allein benutzbar?** Ja, wie `podds_guard`.
**Fallstricke.** Das ist reines **Frequenz-Matching** (MDF sagt „du foldest zu viel" → mehr callen). Im Repo dreimal
unabhaengig widerlegt; was funktioniert hat, war die **Selektion** (`sel_guard`, unten): nicht *wie oft*, sondern
*welche Haende*. Hier steckt der teuerste Lerneffekt des ganzen Subsystems.
Historischer Bug-Hinweis: der `streets`-Parameter landete urspruenglich hier statt in `sel_guard` und referenzierte
einen undefinierten Namen (NameError bei jedem Facing-Bet-Fold, Kommentar `:92-94`) — falls du alten Stand siehst.

---

### `sel_guard` (+ Margen-Varianten `sel_m06/m10/m15/m20`, `sel_all`) — `pokerbot/autogym/improver.py:119`
**Zweck.** Derselbe Knoten wie `mdf_guard`, aber die Equity wird gegen die **gewichtete Tracker-Range** des Gegners
gerechnet (Bayes ueber die gespielte Linie) — Trash foldet weiter, nur wirklich zahlungsfaehige Haende werden gerettet.
**Schnittstelle.** `sel_guard(make_strat, margin=0.03, iters=160, streets=("flop",))`. Trigger: `a == "fold"`,
`to_call > 0`, `street in streets`. Baut `RangeTracker().build(st)`, zieht die Gewichte des Gegners
`t.range[1 - st["to_act"]]` (dict `(karte1, karte2) -> gewicht`), rechnet
`equity_vs_weighted_range(hole, cw, board, iters=160, rng=_spot_rng(st))`; bei
`eq >= equity_needed_to_call(pot, to_call) + margin` → `("call", None)`.
**Eingabe/Ausgabe.** Wie oben; zusaetzlich liest der Tracker `st["history"]`.
**Abhaengigkeiten.** `pokerbot.strategy.range_tracker.RangeTracker` — **hart und teuer**: das ist die eigentliche
Substanz des Guards. Ersetzbar nur durch ein eigenes Range-Modell mit derselben Ausgabeform.
`pokerbot.engine.equity.equity_vs_weighted_range` und `equity_needed_to_call` — hart, aber klein.
**Zustand.** Zustandslos; der Tracker wird je Entscheidung aus der History neu gebaut (es gibt im Repo **keine**
Snapshot-API, `docs/V10_FAKTEN.md:138`).
**Kosten.** Tracker-Neubau gemessen **210 ms kalt / 7,2 ms warm** (`docs/V10_FAKTEN.md:139`), dazu 160 MC-Iterationen.
**Mess-Status.** GEMESSEN POSITIV, mehrfach, und der einzige Guard mit einer sauberen Margen-Kurve:
· `margin=0.03`, Flop: `+4,70 ± 2,06` (99 000 Decks, journal.jsonl:20) und Replikation `+7,49 ± 2,08`
  (99 000 Decks, journal.jsonl:21) → gepoolt ≈ `+6,1 ± 1,5`; getauft **AUSLESE v1**.
· Margen-Sweep vs v1 (journal.jsonl:34-36): `m06 +0,06 ± 1,45` NEUTRAL · `m10 +5,64 ± 1,74` ANWENDEN ·
  `m15 +10,50 ± 2,10` ANWENDEN · `m20 −1,52 ± 1,54` NEUTRAL (`data/runs/STAND.md`, Lauf `20260817_135314`).
· `m15` entscheidend: `+8,68 ± 1,28` vs eingefrorene Basis auf **183 200 Decks** (journal.jsonl:39); drei
  Direktlaeufe vs v1 `+10,50 / +1,11 / +2,63` → gepoolt `+3,94 ± 0,95`; getauft **AUSLESE v3** (journal.jsonl:41).
· `sel_all` (Flop+Turn+River, margin 0.03): vs Basis `+6,13 ± 2,03`, aber im Direktvergleich vs Flop-only
  `+3,00 / +0,44 / +0,18` → gepoolt `+0,69 ± 0,56`, Rotation ABGELEHNT (journal.jsonl:28).
· `sel_all_m15` vs `sel_m15`: **exakt 0,00 auf 29 920 Decks** — der Turn/River-Rettungskanal ist bei Marge 15 pp
  schlicht LEER (journal.jsonl:51 + Interpretation :59). Lies das als „kein Kanal", nicht als „refutiert".
· Transfer auf einen fremden Gegner (GTOBaseline, 3 000 Decks, gepaart): `−3,80 ± 12,87` — uninformativ, weil die
  Messung damals ungeseedete MC benutzte (journal.jsonl:33). Der Gewinn ist also **im Spiegel** belegt, gegen einen
  fremden Gegner nicht.
**Allein benutzbar?** Ja, aber nur mit einem Range-Tracker. Ohne den degeneriert der Guard zu `mdf_guard` (NEUTRAL).
**Fallstricke.** Die Marge ist kein Feinschliff, sondern der Wirkstoff: 3 pp → +6, 15 pp → +17 vs Basis, 20 pp kippt.
Wer den Guard uebernimmt und die Marge auf „mathematisch korrekt" (0.0) setzt, bekommt `mdf_guard` zurueck. Zweitens:
`m15` heisst, dass 15 Prozentpunkte Equity ueber den Pot-Odds verlangt werden — das ist bewusst *keine* GTO-Groesse.

---

### `lizenz_guard` — `pokerbot/autogym/improver.py:156`
**Zweck.** Bet-Seite: Flop/Turn-Bets und -Raises mit Equity unter `junk_eq` gegen die Tracker-Range werden zu
Check bzw. Fold („Bluffs brauchen eine Lizenz" — Browns Bluff-Equity-Band 0,36–0,50, nicht der Boden der Verteilung).
**Schnittstelle.** `lizenz_guard(make_strat, junk_eq=0.20, iters=160)`. Trigger: `a in ("bet","raise","allin")` und
`street in ("flop","turn")`; bei `eq < junk_eq` → `("check", None)` falls `to_call == 0`, sonst `("fold", None)`.
**Eingabe/Ausgabe.** Wie `sel_guard`.
**Abhaengigkeiten.** `RangeTracker`, `equity_vs_weighted_range` — hart.
**Zustand.** Zustandslos.
**Kosten.** Tracker-Neubau + 160 MC-Iterationen je Trigger.
**Mess-Status.** GEMESSEN NEUTRAL: `−0,06 ± 0,69` auf 1 200 Decks (`data/autogym/journal.jsonl:26`, Typ `AKTEN`) —
„die Basis blufft kaum lizenzlos". Davor eine **Null-Messung als Diagnose**: `0,00 ± 0,00` auf 1 200 Decks, weil der
Wrapper `"bet"` nicht in der Trigger-Liste hatte und deshalb nie feuerte (journal.jsonl:23, Typ `DIAGNOSE-BEDARF`).
**Allein benutzbar?** Ja (Tracker vorausgesetzt).
**Fallstricke.** Genau der Bug, der hier gefunden wurde, wird dir auch passieren: die **Eroeffnungs-Bet heisst in
dieser Engine `"bet"`, nicht `"raise"`** (Kommentar `:173-175`). Ein Guard, der exakt `0,00 ± 0,00` misst, ist nicht
neutral — er ist tot. Miss immer erst die **Kanalbreite** (wie oft feuert er?), bevor du das Verdikt liest.

---

### `einmal_guard` — `pokerbot/autogym/improver.py:192`
**Zweck.** Mehrstrassen-Disziplin: die Selektions-Rettung (wie `sel_guard`) darf eine Hand nur **einmal** retten;
ab der zweiten Gelegenheit derselben Hand gilt wieder die Basis-Entscheidung.
**Schnittstelle.** `einmal_guard(make_strat, margin=0.03, iters=160)`. Trigger: Flop-Fold gegen Einsatz und
`not zustand["gerettet"]`; nach einer Rettung wird `gerettet = True` gesetzt.
**Eingabe/Ausgabe.** Wie `sel_guard`.
**Abhaengigkeiten.** `RangeTracker`, `equity_vs_weighted_range` — hart.
**Zustand.** **Je Hand.** Haelt `{"hand": hand_no, "gerettet": bool}` in der Closure und setzt zurueck, sobald
`st["hand_no"]` wechselt. Wenn deine Engine `hand_no` nicht liefert oder es (wie im Duplicate-Spiegel) konstant 1
oder 2 ist, ist der Reset kaputt — dann brauchst du `st["hand_id"]`.
**Kosten.** Wie `sel_guard`, aber seltener (hoechstens ein Trigger je Hand).
**Mess-Status.** GEMESSEN NEUTRAL: `+0,41 ± 1,05 bb/100` vs AUSLESE v1 (`data/autogym/journal.jsonl:37`, Typ
`RUNDE4-DISZIPLIN`, 2026-08-17).
**Allein benutzbar?** Ja.
**Fallstricke.** Der Zustand ist an `hand_no` gebunden (`:207-208`) — im gepaarten Gate ist `hand_no` **immer 1 oder 2**
(`pokerbot/benchmark/duplicate.py:43-45`), der Reset feuert also faelschlich pro Spiegelhaelfte. Das ist genau die
Klasse von Fehler, die eine gepaarte Messung still verfaelscht.

---

### `turn_wert_guard` — `pokerbot/autogym/improver.py:230`
**Zweck.** Der aelteste belegte Leak des Bots auf der **Bet-Seite**: aus einem Turn-Check mit starker Made Hand wird
eine ~2/3-Pot-Value-Bet.
**Schnittstelle.** `turn_wert_guard(make_strat, frac=0.66, min_eq=0.60, iters=160)`. Trigger: `a == "check"`,
`to_call == 0`, `street == "turn"`, beide Stacks > 0. Zwei Bedingungen muessen halten:
(a) Handklasse via treys `get_rank_class` — `kl <= 6` (Trips oder besser) ODER `kl == 7` (Two Pair) mit
Hole-Beteiligung ODER Ueberpaar (Taschenpaar hoeher als jede Boardkarte); (b) `eq >= min_eq` gegen die
Tracker-Range. Dann `("bet", int(frac * st["pot"]))`; die Engine clampt auf `[raise_min, raise_max]`.
**Eingabe/Ausgabe.** Wie `sel_guard`, zusaetzlich `pokerbot.engine.evaluator.evaluate(board, hole)`.
**Abhaengigkeiten.** `treys` (weich — faellt der Import aus, ist `_klasse is None` und der Guard schaltet sich
komplett ab), `pokerbot.engine.evaluator`, `RangeTracker`, `equity_vs_weighted_range` — hart.
**Zustand.** Zustandslos.
**Kosten.** Tracker + 160 MC-Iterationen je Turn-Check-Knoten; nicht einzeln gemessen. Kanalbreite vorgemessen:
**40 von 800 Haenden (5 %)** wuerden betten (journal.jsonl:44).
**Mess-Status.** GEMESSEN POSITIV, 3-Laeufe-Regel erfuellt: `+1,64 ± 4,03` (Lauf 1, journal.jsonl:52),
`+9,39 ± 4,06` (:61), `+10,78 ± 4,00` (:62); **gepoolt `+7,27 ± 2,33` bb/100 ueber 89 760 Decks**, Bootstrap-CI
`[+2,69; +12,05]`, `perm_p 0,0007`, nonzero-Anteil 8,58 % (journal.jsonl:63, Typ `R5B-POOL`). Der Guard-Kern
(`turn_wert(sel_m15)`) vs eingefrorene Basis: `+16,14 ± 2,77`, CI `[+10,74; +21,56]`, `perm_p 0,0002`
(journal.jsonl:70, Typ `V4-VS-BASIS-POOL`). **Angewendet** — Teil von `FINAL_STACK`.
**Allein benutzbar?** Ja, wenn du einen Hand-Evaluator und ein Range-Modell hast.
**Fallstricke.** Zwei, beide gemessen. (1) **Lesbarkeit**: das LLM-Duell zaehlte die Guard-Bets „in
Continuation-Linien 3/3 echt" — also als Tell nutzbar; der Guard bettet *nur* mit Wert, nie mit Bluff, und cappt
damit die Check-Range (journal.jsonl:71). Wer ihn uebernimmt, uebernimmt eine Balance-Verletzung. (2) Der
Equity-RNG-Seed `_spot_rng(st)` enthaelt die **Hero-Hole-Karten** (`docs/V10_FAKTEN.md`, A5) — fuer eine
Gate-Messung egal, fuer jede range-basierte Analyse deines eigenen Bots nicht.

---

### `button_disziplin_guard` (Stack-Name `r6_button`) — `pokerbot/autogym/improver.py:606`
**Zweck.** Der Button open-foldet in Heads-up nie: aus `fold` bei `to_call == 50` preflop wird ein 2,5×-Open auf 250.
**Schnittstelle.** `button_disziplin_guard(make_strat)` — keine Parameter. Trigger: `a == "fold"`,
`street == "preflop"`, `to_call == 50` **und** `me["committed_street"] == 50`. Keine Handbedingung.
**Eingabe/Ausgabe.** Wie oben.
**Abhaengigkeiten.** Keine ausser dem State. Der einzige Guard ohne Import.
**Zustand.** Zustandslos.
**Kosten.** Vernachlaessigbar (zwei Integer-Vergleiche).
**Mess-Status.** GEMESSEN NEUTRAL im Spiegel, POSITIV auf der Adversar-Achse:
Mirror `+0,71 ± 2,18 bb/100`, Kanal 16,7 % (`data/autogym/journal.jsonl:73`, Typ `R6-GATE`) — die Selbstspiel-Basis
bestraft Open-Folds nicht. Der LLM-Adversar tat es: vor dem Guard 29 % Button-Open-Folds; nach dem Guard
**0 von 46**, und die Ernte des Gegners fiel von 186 auf 58 bb/100 ueber 92 Haende (journal.jsonl:75, Typ
`FABLE-RETEST`). **Angewendet** — Teil von `FINAL_STACK`.
**Allein benutzbar?** Ja, vollstaendig isoliert.
**Fallstricke.** Die Chip-Zahlen 50 (SB) und 250 (Open) sind **hart codiert** auf 100-Chip-Blinds. In jeder anderen
Blindstruktur feuert der Guard nie — wieder eine stille Null. Und: das ist der Prototyp der **Zwei-Achsen-Doktrin**
des Repos — Haertungs-Guards gegen adaptive Gegner sind im Spiegel strukturell unsichtbar bis negativ; der Spiegel
ist nur eine Nichtverschlechterungs-Schranke, der Beweis gehoert dem Adversar (journal.jsonl:74, Typ `R6-DOKTRIN`).

---

### `river_ecall_guard` (Stack-Name `r6_ecall`) — `pokerbot/autogym/improver.py:282` — **REFUTIERT**
**Zweck.** River-Calls gegen grosse Bets (≥ 60 % Pot) nur, wenn die Equity vs Tracker-Range die Pot-Odds + Marge deckt.
**Schnittstelle.** `river_ecall_guard(make_strat, marge=0.05, iters=200)`. Trigger: `a == "call"`,
`street == "river"`, `to_call >= 0.6 * max(1, pot - to_call)`; bei `eq < pot_odds + marge` → `("fold", None)`.
**Eingabe/Ausgabe.** Wie `sel_guard`.
**Abhaengigkeiten.** `RangeTracker`, `equity_vs_weighted_range` — hart.
**Zustand.** Zustandslos.
**Kosten.** 200 MC-Iterationen je Trigger.
**Mess-Status.** **GEMESSEN REFUTIERT:** `−4,15 ± 0,97 bb/100`, CI `[−6,1; −2,3]`, Vorzeichen-z −4,7,
nz-Median −1 452 Chips (`data/autogym/journal.jsonl:72`, Typ `R6-GATE`, Verdikt VERWERFEN). Diagnose: im Spiegel
sind die gefoldeten Calls **Value-Folds** — die Selbstspiel-Oekologie bettet dort genug Bluffs. Nicht im Stack.
**Allein benutzbar?** Technisch ja — aber uebernimm ihn nicht in dieser Form.
**Fallstricke.** Zwei benannte Ursachen: (1) MC mit `iters=200` traegt ~3,5 pp Standardfehler — genau das Rauschen,
an dem der Guard scheiterte (Kommentar `:317-319`); der Nachfolger rechnet am River **exakt** (`_river_eq_exakt`).
(2) Der Trigger ist ein reiner Schwellenwert ohne Selektion (keine Blocker, kein Equity-Defizit-Mass).

---

### `_river_eq_exakt` + `river_bill_guard` (Stack-Name `r7_bill`) — `pokerbot/autogym/improver.py:315` / `:338`
**Zweck.** `_river_eq_exakt` rechnet Equity am River durch **vollstaendige Enumeration** ueber die gewichtete Range
(kein RNG, rauschfrei). `river_bill_guard` nutzt sie fuer eine enge Big-Pot-River-Defense.
**Schnittstelle.**
`_river_eq_exakt(hole, cw: dict, board) -> float` — `cw` = `{(karte1, karte2): gewicht}`; blockierte Combos werden
uebersprungen; Rueckgabe `(schlechter + 0.5*gleich) / masse`, `nan` bei leerer Masse.
`river_bill_guard(make_strat, marge=0.04, overbet_marge=0.02, min_frac=0.6, min_pot_chips=3000)` — Trigger:
River-Call, `to_call >= min_frac * pot_vor`, `pot + to_call >= min_pot_chips`. Gefoldet wird nur bei
`eq < pot_odds − m_eff` (Marge **negativ**: nur klar −EV-Calls, nie der Grenz-Call); fuer Overbets/Jams
(`to_call >= pot_vor`) gilt die engere `overbet_marge`.
**Eingabe/Ausgabe.** Wie `sel_guard`; zusaetzlich `pokerbot.engine.evaluator.evaluate` (treys-Konvention:
**kleinerer Score = bessere Hand**).
**Abhaengigkeiten.** `RangeTracker`, `evaluate` — hart. Kein MC, kein RNG.
**Zustand.** Zustandslos.
**Kosten.** Enumeration ueber alle Range-Combos (nach 3 Barrels noch 700–900 Combos, journal.jsonl:89); nicht in
Sekunden gemessen.
**Mess-Status.** GEMESSEN TOT im Spiegel + NEUTRAL im Replay: `r7_bill` Mirror **exakt 0** — er feuert im Gym nie
(`data/autogym/journal.jsonl:91`, Typ `R7-REPLIKATION`). Auf echten GTOW-Haenden nachgespielt: 20 Trigger-Spots,
5 Folds davon 3 richtig (+141 bb) und 2 falsch (−121 bb) = netto **+20 bb** (journal.jsonl:89, Typ `R7-DIAGNOSE`).
Das ausdrueckliche Urteil dort: „Schwellen-Guard auf Tracker-Basis traegt die River-Big-Bet-Defense nicht" — die
fehlende Information ist die polarisierte Bet-Range, also eine Solver-Frage. **Nicht im Stack.**
**Allein benutzbar?** `_river_eq_exakt` ja und uneingeschraenkt empfohlen (30 Zeilen, keine Abhaengigkeit ausser
einem Evaluator). Der Guard darum herum: nein.
**Fallstricke.** Die Tracker-Equity **trennt Gewinner und Verlierer nicht** — gemessen 0,578 vs 0,513 im Default
bzw. 0,652 vs 0,532 mit PRINCE-Env (journal.jsonl:89). Ein Guard kann nur so scharf sein wie sein Range-Modell;
mehr Schwellen-Tuning hilft dort nicht.

---

### `river_wert_bremse` (Stack-Name `r7_wert`) — `pokerbot/autogym/improver.py:378`
**Zweck.** Eine River-Bet mit **starker** Made Hand (Two Pair oder besser) braucht ≥ 50 % Equity gegen die
Tracker-Range — sonst ist die Hand auf diesem Board ein Bluffcatcher und der Check dominiert.
**Schnittstelle.** `river_wert_bremse(make_strat, min_eq=0.50)`. Trigger: `a == "bet"`, `to_call == 0`,
`street == "river"`, treys-Klasse `kl <= 7`. Bei `_river_eq_exakt(...) < min_eq` → `("check", None)`.
Bluffs und schwache Haende bleiben unangetastet; der Raise-Knoten ist bewusst nicht abgedeckt.
**Eingabe/Ausgabe.** Wie `sel_guard`; RNG-frei.
**Abhaengigkeiten.** `treys` (weich), `pokerbot.engine.evaluator`, `RangeTracker`, `_river_eq_exakt` — hart.
**Zustand.** Zustandslos.
**Kosten.** Eine Range-Enumeration je River-Bet-Knoten; nicht einzeln gemessen.
**Mess-Status.** GEMESSEN POSITIV, 3-Laeufe-Regel erfuellt auf drei disjunkten Deck-Baenken, jeweils vs `r6_button`:
`+8,10 ± 1,14` · `+8,81 ± 1,25` · `+7,38 ± 1,05`, alle `perm_p 0,0002`
(`data/autogym/journal.jsonl:91`, Typ `R7-REPLIKATION`). **Angewendet** — Teil von `FINAL_STACK`.
Gegenevidenz, ehrlich vermerkt: auf 3 904 echten GTOW-Entscheidungen greift er nur **10-mal** ein, und der
Typusfall wurde unter dem Live-Tracker nicht gebremst — die Evidenz ist selbstspiel-seitig (journal.jsonl:94).
**Allein benutzbar?** Ja, sofern Evaluator + Range-Modell vorhanden.
**Fallstricke.** Die Schwelle 0,50 ist keine Theorie, sondern die Grenze „schlage ich die Range oder nicht". Der
Guard bremst **nur den Bet-Knoten mit starker Hand** — bewusst ein Mechanismus je Guard. Wer ihn auf Raises oder
schwache Haende ausdehnt, purifiziert die Bluff-Seite und verletzt das Mixing (Seesaw-Doktrin des Projekts).

---

### `_river_spot_und_frage` + `_frage_kind` (Unterbau der Solver-Guards) — `pokerbot/autogym/improver.py:421` / `:472`
**Zweck.** Uebersetzt einen laufenden State in ein loesbares River-Subgame: friert die Tracker-Ranges **am
River-Beginn** ein und rekonstruiert die River-Betting-Sequenz in Chip-Zusatzbetraegen.
**Schnittstelle.** `_river_spot_und_frage(st, frage_kind) -> (RiverSpot, pot_river) | None`. Sucht in
`st["history"]` die Marke `{"action":"deal","street":"river"}`, schneidet dort, baut `RangeTracker().build(st0)`,
laeuft die Aktionen danach durch (Level-Verfolgung je Sitz) und haengt `("hero", frage_kind, 0.0)` an.
`pot_river = st["pot"] − Summe der River-Einsaetze`; `eff = min(stack + committed_street)`.
`_frage_kind(a, to_call)` mappt die Basis-Aktion auf `"raise" | "bet" | a`.
**Eingabe/Ausgabe.** State rein; raus ein `pokerbot.strategy.gpu_resolver.RiverSpot` (Board, Hero-Gewichte,
Villain-Gewichte, `pot_river`, `eff`, `hero_oop`, `seq`, `hero_hole`) plus `pot_river`. `None`, wenn keine
River-Deal-Marke existiert oder `pot_river <= 0`.
**Abhaengigkeiten.** `gpu_resolver.RiverSpot`, `RangeTracker` — hart.
**Zustand.** Zustandslos.
**Kosten.** Ein Tracker-Neubau (210 ms kalt / 7,2 ms warm, `docs/V10_FAKTEN.md:139`).
**Mess-Status.** UNGEMESSEN als eigene Einheit; die `pot_river`-Rechnung ist verifiziert (`1400 == 1400`,
`docs/V10_FAKTEN.md`, A5).
**Allein benutzbar?** Nur zusammen mit einer History im beschriebenen Format.
**Fallstricke.** **Ohne die `deal`-Marke in der History gibt die Funktion still `None` zurueck** — der Guard
darueber feuert dann nie und du siehst exakt 0. Genau das ist im Kaggle-Adapter passiert (Commit `d22d400`:
„ohne sie meldete v10 'fehler:root_nicht_rekonstruierbar' und spielte in 30 Haenden 0-mal"). Wenn du diese
Guards portierst, ist die Deal-Marke Pflichtteil deines History-Formats.

---

### `river_gpu_guard` (Stack-Name `r8_gpu`, im Champion `r8_stack`) — `pokerbot/autogym/improver.py:477`
**Zweck.** Solver-**Chirurgie** am River: in grossen Pots wird das Subgame mit den am River-Beginn eingefrorenen
Ranges geloest, und die Basis-Aktion wird nur ueberschrieben, wenn der Solver sie klar verwirft.
**Schnittstelle.** `river_gpu_guard(make_strat, min_pot_chips=3000, iters=150, p_max_basis=0.10, p_min_alt=0.70)`.
Trigger: `street == "river"` und `st["pot"] >= min_pot_chips` (aktueller Pot, **nicht** `pot_river`). Loest via
`solve_spots([spot], iters=150)`, bestimmt `p_basis` (bei bet/raise das Maximum ueber alle Bet/Raise-Arme) und die
beste Alternative; ueberschreibt nur, wenn `p_basis < 0.10` UND `sigma[best] > 0.70`. Abbildung:
`fold`→fold (nur bei `to_call>0`), `call`→call, `check`→check (nur bei `to_call==0`), `bet…`→`("bet", int(0.75*pot))`.
**Eingabe/Ausgabe.** State rein; `solve_spots` liefert je Spot `{"acts": [str], "sigma": [float], "zusatz_norm": [float]}`.
**Abhaengigkeiten.** `pokerbot.strategy.gpu_resolver.solve_spots` (→ `gpu_cfr.RiverCFRBatch`, torch + CUDA) — **hart
und schwer**; `_river_spot_und_frage` → `RangeTracker`. Ohne GPU-Solver ist von diesem Guard nichts uebrig.
**Zustand.** Zustandslos und deterministisch (kein RNG; argmax nur im Klarfall) — A/A exakt 0 auf 600 Decks bewiesen
(`data/autogym/journal.jsonl:92`).
**Kosten.** Durchsatz `0,30 s/Spot` amortisiert bei Batch 256 (journal.jsonl:90); **Einzel-Solve** (B=1, fp32,
150 Iterationen, RTX 3080 Ti) gemessen `0,9–1,1 s` bei SPR 1, `2,0–2,55 s` bei SPR 3, `2,5 s` bei SPR 7, Setup
18–23 ms warm / 289 ms kalt (`docs/V10_FAKTEN.md`, A6). Der Guard ruft **je Entscheidung einen B=1-Solve** —
das ist der Latenz-Treiber der ganzen Kette.
**Mess-Status.** GEMESSEN POSITIV, groesster Einzelsprung des Projekts (Achtung: das Inkrement enthaelt
`river_wert_bremse` mit, die allein ≈ +8 bringt):
`r8_stack` vs `r6_button`: `+29,92 ± 3,10` / `+23,76 ± 3,07` / `+29,23 ± 3,03` auf drei Baenken à 30 000 Decks,
gepoolt `+27,6 ± 1,8`, alle `perm_p 0,0002`; vs eingefrorene Basis `+30,60 ± 5,03`; A/A exakt 0
(`data/autogym/journal.jsonl:92`, Typ `R8-FINALE-LAUF1`; Zusammenfassung der drei Laeufe :93, Typ
`TAUFE-AUSLESE-V5`). Solver-Audit auf 571 echten River-Spots:
Desaster-Calls bekommen Solver-`fold` mit p > 0,95, die Fehl-Value-Bets Solver-`check` mit p ≈ 1,0 (:90).
**Angewendet** — der Kern von `FINAL_STACK = r8_stack`.
**Allein benutzbar?** Nein, praktisch nicht. Du brauchst den GPU-River-CFR, den Resolver-Wrapper und den
Range-Tracker; das sind drei weitere Module.
**Fallstricke.** Drei aktenkundige (`docs/V10_FAKTEN.md`, A5/A6): (1) Die Bet-Groesse ist **hart auf `0.75*pot`
codiert**, obwohl der Kommentar daneben „Size aus dem Baum-Arm" behauptet. (2) `solve_spots._injiziere` schiebt
Heros tatsaechliche Combo mit Mindestgewicht 0,02 in die Hero-Range — der Solver loest also ein Spiel, in dem Hero
seine Karte teilweise „kennt"; das ist der dokumentierte strukturelle Defekt, an dem v10 ansetzte. (3) `except:
pass` ohne Log: ein dauerhaft fehlschlagender Solver ist von einem nie feuernden Guard nicht unterscheidbar.

---

### `river_play_guard` (Stack-Namen `r9_play`, `r10_ernte`) — `pokerbot/autogym/improver.py:535` — **gedroppt**
**Zweck.** Die Stufe ueber der Chirurgie: in Big-Pot-River-Spots wird die geloeste Politik **gespielt** (aus der
Solver-Mischung gesampelt), nicht nur der klare Fehler korrigiert.
**Schnittstelle.** `river_play_guard(make_strat, min_pot_chips=3000, iters=150, half=False)`. Nach dem Solve wird
deterministisch gesampelt: `u = crc32("v8play|" + hole|board|pot|current_bet|committed_street|len(history)) / 2^32`,
dann kumulative Auswahl ueber `sigma`. Sizes kommen aus dem Baum-Arm: `betrag = zus[wahl]/100 * pot_river`, Ziel-Level
`int(me["committed_street"] + betrag)`; Jam bei `betrag >= stack-1`. Legalitaetsgatter: `kann_raisen = (not opp.all_in)
and me["stack"] > to_call`, sonst faellt der Guard auf den passiven Zweig zurueck.
**Eingabe/Ausgabe.** Wie `river_gpu_guard`, zusaetzlich `zusatz_norm` aus dem Solver-Ergebnis.
**Abhaengigkeiten.** Identisch zu `river_gpu_guard` — hart.
**Zustand.** Zustandslos; deterministisch ueber den Spot-Hash (A/A exakt 0 belegt, journal.jsonl:97).
**Kosten.** Wie `river_gpu_guard`; `half=True` (fp16) wurde als Latenz-Hebel gebaut (`r10_ernte`, Trigger 1 500 Chips).
**Mess-Status.** GEMESSEN NEUTRAL im Spiegel → **gedroppt**: `play` vs v5 `+1,14 ± 2,78` (30 000 Decks);
die volle v8-Komposition vs v5 `+3,91 ± 2,85` und `−1,23 ± 4,36` (30k + 15k, gepoolt ≈ `+2,3 ± 2,4`), A/A exakt 0
(`data/autogym/journal.jsonl:97`, Typ `V8-DROP`). Gegenlaeufige Evidenz auf der GTOW-Achse, ausdruecklich als
unbewiesen markiert: 32 Eingriffe auf 3 904 Entscheidungen (0,8 %), davon 7 `call→fold` mit netto **+278,6 bb**
bilanziert (journal.jsonl:94, Typ `V8-PLAY-PROFIL`). Die dokumentierte Ursachen-Analyse (`docs/V8_POSTMORTEM.md`):
Kanal-Saettigung — die Chirurgie hatte die Klarfaelle bereits geerntet, die Play-Differenzen liegen in
Indifferenz-Zonen (nz-Median 1,9 bb vs 11,6 bb).
**Allein benutzbar?** Nein (wie `river_gpu_guard`).
**Fallstricke.** Der Sampling-Hash **enthaelt die Hero-Hole-Karten** (`docs/V10_FAKTEN.md`, A5). Damit haengt die
„Mischung" von privater Information ab statt vom oeffentlichen Zustand — genau der Defekt, den die
Hybrid-Doktrin des Projekts spaeter als „handabhaengiges Gating" benennt. Ausserdem: keine Deadline, `except: pass`.

---

### `turn_gpu_guard` — `pokerbot/autogym/turn_gpu.py:170`
**Zweck.** Dieselbe Solver-Chirurgie wie `river_gpu_guard`, aber am **Turn**: das Turn+River-Subgame wird mit den am
Turn-Beginn eingefrorenen Ranges geloest (Turn-Betting + 48-Runout-River-Batch).
**Schnittstelle.** `turn_gpu_guard(make_strat, min_pot_chips=3000, iters=120, p_max_basis=0.10, p_min_alt=0.70)`.
Trigger nur `street == "turn"` und `pot >= min_pot_chips`; feuert nie nach dem River-Deal. Kern:
`_turn_urteil(st, a, amt, iters, p_max_basis, p_min_alt) -> {"acts","sigma","p_basis","urteil"}` (`:87`);
`urteil` ist `None`, wenn die Chirurgie-Schwellen nicht greifen.
Hilfsfunktionen: `_turn_seq(hist_nach_deal, hero_seat)` (`:29`) und `_navigiere_turn(cfr, seq, skala)` (`:56`).
Baum-Geometrie als Modul-Konstanten: `TURN_BETS=(0.75,)`, `RAISE_SIZES=(2.7,)`, `MAX_RAISES=1`,
`RIVER_KW={"bet_sizes":(0.75,), "raise_sizes":(), "max_raises":1}` (`:23-26`) — bewusst klein wegen Latenz.
**Eingabe/Ausgabe.** Wie die River-Solver-Guards.
**Abhaengigkeiten.** `pokerbot.strategy.gpu_cfr` (`TurnCFR`, `combo_index`, `range_vector`),
`pokerbot.strategy.gpu_resolver` (`POT_NORM`, `_injiziere`) — hart, GPU-gebunden.
**Zustand.** Zustandslos, deterministisch (kein RNG).
**Kosten.** Die einzige Zahl im Repo ist der Code-Kommentar „hoher Trigger (**Latenz 12–14 s**)"
(`pokerbot/autogym/pargate.py:150`) — nicht durch einen Messlauf belegt. Der Selbsttest (`python -m
pokerbot.autogym.turn_gpu`) misst kalt/warm, aber im Repo ist kein Ergebnis abgelegt.
**Mess-Status.** UNGEMESSEN im Gate: es existiert **kein** A/B-Ergebnis fuer `r9_turn`. Der Kanal ist als zu duenn
dokumentiert — „turn_gpu 3/3904 zu leise" (`docs/STATE.md:110`) bzw. „Replay 3/3904 = keine bilanzierbare Evidenz"
(`pokerbot/autogym/pargate.py:159-160`). Bleibt default-OFF-Arm.
**Allein benutzbar?** Nein — braucht den kompletten GPU-CFR-Stack.
**Fallstricke.** Der Trigger `min_pot_chips` steht in `_wickle` auf **5 000** (nicht 3 000), gerade wegen der Latenz
(`pargate.py:152`). Bei 12–14 s je Entscheidung ist der Guard fuer Live-Spiel gegen eine Uhr unbrauchbar; er ist ein
Forschungsarm, kein Produkt.

---

### `stackoff_bremse` — `pokerbot/autogym/preflop_guards.py:42`
**Zweck.** Grosse Preflop-Stackoffs nur noch mit selektierten Handklassen: ab 100 bb Gesamteinsatz bleiben nur
Premium-Haende frei, Mittel-Klassen bis unter 150 bb, alles andere foldet.
**Schnittstelle.** `stackoff_bremse(make_strat, premium=("AA","KK","QQ","AKs","AKo"), mittel=("JJ","TT","AQs"),
grenze_hart=15000, grenze_weich=10000)`. Trigger: `street == "preflop"`, `to_call > 0`,
`a in ("call","raise","allin")`. Berechnet den **Gesamteinsatz nach der Aktion**:
call → `committed_total + min(to_call, stack)`; allin/`amt is None` → `committed_total + stack`;
raise → `committed_total - committed_street + min(amt, committed_street + stack)`.
Unter `grenze_weich` wird nie eingegriffen; `to_call == 0` (Opens, BB-Option) ebenfalls nie.
Hilfsfunktion `_hand_klasse(hole)` (`:31`) → `'KK' | 'AKs' | 'J9o'`.
**Eingabe/Ausgabe.** Wie oben. Konstanten: `_GRENZE_WEICH = 10000`, `_GRENZE_HART = 15000` Chips (`:27-28`).
**Abhaengigkeiten.** Keine ausser dem State — bewusst so gehalten, damit der Import keine Gate-Maschinerie mitzieht
(Kommentar `:18-19`).
**Zustand.** Zustandslos.
**Kosten.** Vernachlaessigbar (String-Vergleiche).
**Mess-Status.** UNGEMESSEN als Effekt — der Kanal ist im Selbstspiel **stumm**: gezaehlte **1 Trigger pro 400
Haenden** (`data/autogym/journal.jsonl:96`, Typ `R9-PRE-VERDIKT`, dort ausdruecklich „unschuldig" am −11,42 des
Kombi-Arms). Die Motivation stammt von der GTOW-Achse (Desaster-Klasse D, „−13,8 bb je Zelle",
`KANDIDATEN.md` → `docs/HU_OPTIMAL_KARTE.md:51`), ist dort aber nie als A/B gemessen worden.
Funktional geprueft: 10/10 Faelle im Selbsttest (`python -m pokerbot.autogym.preflop_guards`, `:136-179`).
**Allein benutzbar?** Ja, komplett isoliert — der am leichtesten uebernehmbare Guard der Sammlung.
**Fallstricke.** Die Grenzen sind **Chip-Absolutwerte** fuer 100-Chip-Blinds und 200-bb-Startstack. Und der Guard
ist gemessen wirkungslos im Selbstspiel: wenn dein Bot ohnehin selten 100-bb-Stackoffs mit J9o baut, kaufst du dir
nur Code. Miss zuerst die Trigger-Rate.

---

### `no_limp_guard` — `pokerbot/autogym/preflop_guards.py:85` — **REFUTIERT**
**Zweck.** Den HU-Button-Limp streichen: aus `call` bei `to_call == 50` und `committed_street == 50` wird ein
2,5×-Open auf 250.
**Schnittstelle.** `no_limp_guard(make_strat)` — keine Parameter. Konstanten `_SB_CHIPS = 50`,
`_OPEN_RAISE_TO = 250` (`:23-24`).
**Eingabe/Ausgabe.** Wie oben.
**Abhaengigkeiten.** Keine.
**Zustand.** Zustandslos.
**Kosten.** Vernachlaessigbar.
**Mess-Status.** **GEMESSEN REFUTIERT** (als Teil des Arms `r9_pre`): `−11,42 ± 2,97 bb/100` auf 30 000 Decks,
Verdikt VERWERFEN; die Taeter-Diagnose weist den Verlust dem `no_limp_guard` zu — die Basis limpt **78 von 400
Haenden (~39 % der Buttons) strategisch**, der Guard baute damit das halbe Preflop-Spiel um (37,8 % Divergenz-Decks)
(`data/autogym/journal.jsonl:96`, Typ `R9-PRE-VERDIKT`).
**Allein benutzbar?** Ja — aber die Messung sagt: tu es nicht.
**Fallstricke.** Das ist die Lehre, die im Repo festgehalten ist: der ausloesende Befund („Limp-Call → Fold gegen
C-Bet 5/7 = freie Kasse") war ein **Limp-Pot-Verteidigungs**-Problem, kein Limp-Problem. Ein Guard, der eine
strategische Frequenz komplett abschaltet, statt den Folgeknoten zu reparieren, kostet mehr, als der Leak wert war.

---

### `river_plan_guard` (Stack-Namen `r10_stack`, `r10_h0`) — `pokerbot/autogym/river_plan.py:920`
**Zweck.** Der v10-Ersatz fuer `river_gpu_guard`: **ein** Solve je Hand am River-Beginn, dessen Plan danach fuer alle
Entscheidungen dieser Hand gilt — Gating nach **oeffentlichem** Zustand, Randomisierung aus einem privaten Seed
statt aus den Hole-Karten.
**Schnittstelle.** `river_plan_guard(make_strat, min_pot_chips=DEFAULT_MIN_POT_CHIPS, iters=DEFAULT_ITERS,
deadline_s=None, trace_pfad=None, privater_seed=None, modus="gym", solve_worker=LIVE_SOLVE_WORKER,
queue_budget_s=None, aufwaermen=True) -> RiverPlanFabrik`. `modus="gym"`: private_seed deterministisch aus
(hand_adresse, seat), feste Iterationen, kein Zeitabbruch → A/A exakt 0. `modus="live"`: `os.urandom(16)` je Prozess,
Deadline, `solve_worker` parallele Solve-Threads. Hero ausserhalb der oeffentlichen Range → **immer** Basis mit
Status `hand_not_in_range`.
**Eingabe/Ausgabe.** Wie die anderen River-Guards; zusaetzlich ein Trace mit Statuscodes
(`plan` / `deadline` / `offtree` / `hand_not_in_range` / `fehler`).
**Abhaengigkeiten.** `pokerbot.strategy.hero_range` (K1-Hero-Likelihood-Replay), `gpu_cfr.RiverCFRBatch`,
`RangeTracker` — hart. Konstanten: `LIVE_SOLVE_WORKER = 3`, `QUEUE_BUDGET_S = 3.0`,
`K1_AKZEPTIERTE_STATUS = ("ok","teilweise")` (`:82,:84,:240`).
**Zustand.** **Je Hand** (Plan-Cache) und **je Prozess** (Live-Seed, Solve-Threads). Beim Handwechsel muss der Plan
verworfen werden, sonst spielst du den Plan der Vorhand.
**Kosten.** Live gemessen (n=40 Plan-Pots, nach dem Thread-Fix): p50 3,04 s, p90 8,50 s, **p99 10,15 s**
(`data/autogym/journal.jsonl:108`, Typ `V10-LIVEFIX-G2-NACHMESSUNG`; auch `docs/STATE.md:95`);
Deadline-Abbrueche 0/40, Vergleichsarm v5 p50 2,10 s / p99 8,20 s.
**Mess-Status.** GEMESSEN NEUTRAL im Spiegel, Gate-Leiter **nicht bestanden** → **nicht ausgeliefert**:
G5 `r10` vs `r8` `+11,68 ± 10,85` auf 1 968 Decks, CI `[−9,39; +33,06]` (NEUTRAL);
G3 VERFEHLT (K1-Total-Variation 0,2085 mittel gegen ein Budget von 0,02; Hero ausserhalb des K1-Supports in 21 von
64 Faellen); live spielte der Plan nur 25/40, `offtree` 11/40
(`data/autogym/journal.jsonl:107`, Typ `V10-GATES`, und `docs/V10_GATES_REPORT.md`).
`r10_h0` (2026-09-10, Commit `d22d400`) ist der Patch dagegen: derselbe Plan, aber auf der **vollstaendigen** v5-Kette
statt auf `r8`-ohne-Chirurgie, damit ein Fallback nie unter dem Champion landet; dokumentiert ist bisher nur
„A/A exakt 0" (Commit-Nachricht) — sonst UNGEMESSEN.
**Allein benutzbar?** Nein. Von allen Guards die schwerste Abhaengigkeitslast (Solver + eigenes Hero-Range-Modell).
**Fallstricke.** Der dokumentierte Katastrophenherd: faellt der Plan aus (Off-Tree-Size, Deadline, Hand nicht in der
Range), landete `r10_stack` auf der **nackten Basis ohne die v5-Chirurgie** — alle drei Gym-Decks mit ≤ −100 bb
stammen aus diesem Fallback (`data/autogym/journal.jsonl:107`). Ein Guard mit degradiertem, unsichtbarem Fallback ist
gefaehrlicher als gar kein Guard.

---

### `wickle_decide` + `FINAL_STACK` — `pokerbot/strategy/auslese.py`
**Zweck.** Die **eine Quelle** des ausgelieferten Guard-Stacks fuer alle Konsum-Kanaele (Web-App, Benchmarks,
Export) — damit nie zwei Kanaele verschiedene Ketten spielen.
**Schnittstelle.**
`FINAL_STACK = "r8_stack"` (`:34`) — der Champion: `river_gpu_guard(river_wert_bremse(r6_button(turn_wert(sel_m15))))`.
`RC_STACK = "r10_stack"` (`:35`) — Release-Kandidat v10, **nicht** getauft.
`AUSLESE_ENV = {"POKERB_TURN_DEFENSE": "0.07", "POKERB_SLOWPLAY": "0.25"}` (`:36`);
`AUSLESE_ENV_RESOLVER_OFF` ergaenzt `POKERB_RAISE_NARROW = "1.0"` (`:37`).
`setze_env(resolver_on=False)` (`:40`) — setzt die Flags per `setdefault`; **muss vor dem Import von
`pokerbot.strategy.bot` laufen**, weil die Flags zur Importzeit gelesen werden.
`wickle_decide(pb, stack=None, kanal="live") -> decide(st) -> dict` (`:49`) — legt den Stack **dict-erhaltend** um
`PokerBot.decide`: die Basis-Fabrik merkt sich das komplette Entscheidungs-Dict, und wenn die Guard-Kette
`(action, amount)` veraendert, wird ein neues Dict mit `auslese_guard: True` zurueckgegeben.
**Eingabe/Ausgabe.** Rein: eine Bot-Instanz mit `.decide(st) -> {"action","amount","rationale",…}`. Raus: dieselbe
Signatur, aber mit Guard-Kette. `kanal="gym"` erzwingt Determinismus (gepaarte Gates), `"live"` gibt K2-Armen
Deadline + `os.urandom`-Seed.
**Abhaengigkeiten.** `pokerbot.autogym.pargate._wickle` — hart (dort wohnt die Komposition).
**Zustand.** Je Bot-Instanz. Die Guard-Kette wird **einmal** gebaut (`kette = stack_fabrik(0)`), zustandsbehaftete
Guards (`einmal_guard`, K2-Plan-Cache) leben also so lange wie die Instanz.
**Kosten.** Die des gewaehlten Stacks; der Wrapper selbst ist ein Funktionsaufruf.
**Mess-Status.** GEMESSEN POSITIV fuer die Kette als Ganzes: v4-Aera `+23,36 ± 5,32` vs eingefrorene Basis
(`data/autogym/journal.jsonl:76`, Typ `FINAL-STACK-VS-BASIS`); v5-Aera `r8_stack` vs Basis `+30,60 ± 5,03`
(journal.jsonl:92). **Absolute Aussenmessung fehlt**: der einzige echte GTOW-Anker gehoert v4-auf-PRINCE mit
`−21,12 bb/100 AIVAT` ueber 979 Haende (journal.jsonl:88, Typ `GTOW-NACHT2-FAZIT-MANUELL`) — v5 hat nur
Spiegel-Evidenz (`docs/STATE.md`, Abschnitt 2026-09-09).
**Allein benutzbar?** Ja, wenn dein Bot ein `decide(st) -> dict` anbietet.
**Fallstricke.** `rationale` ist ein **Dict**, kein String. Der urspruengliche Code haengte bei einem Guard-Eingriff
einen String an und stuerzte genau dann ab, wenn ein Guard feuerte — der Fehler ueberlebte einen 20-Hand-Smoke-Test
(Kommentar `:76-78`). Zweitens: `setze_env` **nach** dem Bot-Import aufzurufen ist wirkungslos und stillschweigend.
Drittens: die Guards sind HU-only (2-Spieler-State-Ausdruecke, `st["players"][1 - st["to_act"]]`) — die 6-max-Messung
hat den Einbau als schaedlich verworfen (`hybrid_r8 −21,73 ± 9,01` vs dem reinen 6-max-Kern, journal.jsonl:112).

---

### `_wickle` (Stack-Komposition) + `par_gate` — `pokerbot/autogym/pargate.py`
**Zweck.** `_wickle` ist die **einzige** Stelle, an der die Guard-Ketten benannt und zusammengesetzt werden;
`par_gate` ist das gepaarte A/B-Gate ueber alle CPU-Kerne.
**Schnittstelle.**
`_wickle(name: str, basis, kanal: str = "gym")` (`:69`) — legt den benannten Stack um eine fertige Strategie-Fabrik;
`ValueError(name)` bei unbekanntem Namen. `KANDIDATEN` (`:18-47`) ist die Whitelist aller Namen.
`_baue_fabrik(name, seed)` (`:194`) — der Gate-Kanal: `_wickle(name, pokerbot(exploit=True, seed=seed))`.
`par_gate(kandidat, n_decks, workers, seed=1, deck_seed0=1000, incumbent="basis") -> dict` (`:238`).
CLI: `python -m pokerbot.autogym.pargate --kandidat sel_m15 --decks 30000 --workers 20 --incumbent basis`.
**Die registrierten Stacknamen (Aufbau von innen nach aussen):**
| Name | Komposition |
|---|---|
| `basis` | die nackte Strategie (kein Guard) |
| `mdf_guard` / `podds_guard` / `sel_guard` / `einmal_guard` / `lizenz_guard` | je ein Guard mit Default-Parametern |
| `sel_m06` / `sel_m10` / `sel_m15` / `sel_m20` | `sel_guard(margin=0.06 / 0.10 / 0.15 / 0.20)` |
| `sel_all` | `sel_guard(streets=("flop","turn","river"))` |
| `auslese2` | `lizenz_guard(sel_guard(streets=alle))` |
| `sel_all_m15` / `sel_turn_m15` | `sel_guard(margin=0.15, streets=alle / flop+turn)` |
| `turn_wert` | `turn_wert_guard(sel_guard(margin=0.15))` ← **AUSLESE v4-Kern** |
| `wert_plus_all` | `turn_wert_guard(sel_guard(margin=0.15, streets=alle))` |
| `r6_ecall` | `river_ecall_guard(turn_wert)` — REFUTIERT |
| `r6_button` | `button_disziplin_guard(turn_wert)` |
| `r7_bill` / `r7_wert` / `r7_river` | `river_bill_guard` / `river_wert_bremse` / beide, je auf `r6_button` |
| `r8_gpu` | `river_gpu_guard(r6_button)` |
| **`r8_stack`** | `river_gpu_guard(river_wert_bremse(r6_button))` ← **`auslese.FINAL_STACK`, der Champion** |
| `r9_play` | `river_play_guard(river_wert_bremse(r6_button))` |
| `r9_pre` | `stackoff_bremse(no_limp_guard(r8_stack))` — REFUTIERT (−11,42) |
| `r9_turn` | `turn_gpu_guard(r8_stack, min_pot_chips=5000, iters=80)` |
| `r9_v8` | `stackoff_bremse(river_play_guard(river_wert_bremse(r6_button)))` — bewusst OHNE `no_limp` und OHNE `turn_gpu` |
| `r10_ernte` | wie `r9_v8`, aber `min_pot_chips=1500, iters=150, half=True` (fp16) |
| `r10_stack` | `river_plan_guard(river_wert_bremse(r6_button), min_pot_chips=1500, iters=150)` = v10 |
| `r10_h0` | `river_plan_guard(r8_stack, …)` = v10.0-Patch „H0-lite" |
Die volle Champion-Kette von innen nach aussen lautet damit:
`basis → sel_m15 → turn_wert → button_disziplin → river_wert_bremse → river_gpu` (`pargate.py:80-140`, bestaetigt
in `docs/V10_FAKTEN.md`, A5). Der aeussere Wrapper sieht immer die Entscheidung des inneren.
**Eingabe/Ausgabe.** `par_gate` gibt `{"kandidat","incumbent","kanal","bb100","se","bb100_trim","median_bb100",
"nonzero","nonzero_anteil","nz_pos","vorzeichen_z","nz_median_chips","ci95_lo","ci95_hi","perm_p","workers",
"sekunden","decks_pro_min","verdict","edges"}`. Die per-Deck-Edges landen in `data/runs/<lauf>/edges.json`.
**Abhaengigkeiten.** `improver` (die Guards), `preflop_guards`, `turn_gpu`, `river_plan`, `duplicate`, `stats`,
`runs` — alles hart, aber `_wickle` selbst ist eine reine If-Kette und in 10 Minuten nachgebaut.
**Zustand.** `par_gate` ist **fortsetzbar**: jeder fertige Job-Block wird nach
`data/_pargate_blocks/<kandidat>__vs__<incumbent>__s<seed>__b<deckseed>__c<chunk>/jobNNN.json` geschrieben; ein
Neustart mit identischen Parametern ueberspringt berechnete Bloecke und ist byte-gleich zum durchgelaufenen Lauf.
Der Blockname traegt alle ergebnisbestimmenden Groessen — aendere Code, und du musst eine **neue Deck-Bank**
(`--deck-seed0`) nehmen, sonst liest du alte Bloecke.
**Kosten.** Gemessen **3 608–3 897 Decks/min** bei 20–22 Workern (`data/autogym/journal.jsonl:39, :51, :52, :61`).
GPU-Arme: die Code-Kommentare sagen `--workers <= 6`, spaeter auf 12 korrigiert (VRAM 3,7 von 12,3 GB bei
6 Workern, journal.jsonl:95).
**Mess-Status.** GEMESSEN POSITIV als Instrument (nicht als Strategie): der A/A-Nulltest (Kandidat == Incumbent)
liefert **exakt 0,00 ± 0,00** — belegt auf 1 936 Decks (journal.jsonl:50), 600 Decks im GPU-Arm (:92) und 576 Decks
im v10-Arm (:107). Ein A/A ungleich 0 ist im Repo jedes Mal ein echter Bug gewesen (ungeseedete MC; `hand_id` je
Spiegelhaelfte verschieden; RNG-Strom ueber Haende).
**Allein benutzbar?** `_wickle` ja (reine Komposition). `par_gate` braucht `duplicate` + `stats` + `runs`.
**Fallstricke.** Der Worker raeumt vor jedem Lauf die Umgebung auf (`:204-217`): alle `POKERB_*`-Variablen werden
**geloescht**, `OPENBLAS/OMP/MKL_NUM_THREADS = 1` gesetzt und `torch.set_num_threads(1)` gerufen. Ohne das erste
faerben geerbte Shell-Flags **beide** Gate-Seiten still; ohne das zweite stirbt OpenBLAS beim Init; ohne das dritte
spawnt jeder Worker torch mit Kernzahl-Threads und die Parallelisierung bricht ein, obwohl alle Kerne „busy"
aussehen. Alle drei sind im Repo als Debug-Beweise belegt. Zweiter Fallstrick: **`imap_unordered` + `extend`
zerstoert das Deck→Edge-Mapping** — die Bloecke werden deshalb nach Job-Index geordnet zusammengesetzt (`:255-286`),
sonst sind Edges lauf- und armuebergreifend nicht mehr paarbar.

---

### Urteils-Statistik — `pokerbot/autogym/stats.py`
**Zweck.** Aus per-Deck-Chip-Edges das Verdikt machen — fettrand-bewusst, weil die klassische 2-SE-Regel bei diesen
Verteilungen zu optimistisch ist.
**Schnittstelle.**
`robust_stats(edges, bb=100, trim=0.05, haende_je_deck=2) -> dict` (`:17`) — rohes Mittel + SE in bb/100
(`skala = 1/haende_je_deck/bb*100`), dazu getrimmtes Mittel, Median und die **Sparse-Diagnostik**: `nonzero`,
`nonzero_anteil`, `nz_pos`, `vorzeichen_z`, `nz_median_chips`.
`bootstrap_ci(edges, b=4000, seed=17) -> {"ci95_lo","ci95_hi","perm_p","boot_b"}` (`:59`) — Perzentil-Bootstrap +
Vorzeichen-Flip-Permutationstest, der **nur die Nicht-Null-Edges** zieht (Nullen tragen weder Resample-Summe noch
Flip) → Kosten `b*m` statt `b*n`, deterministisch.
`verdikt(st) -> "ANWENDEN" | "VERWERFEN" | "NEUTRAL"` (`:93`) — Basis rohes Mittel ± 2 SE; bei
`nonzero_anteil < SPARSE_SCHWELLE` (`0.02`, `:90`) traegt zusaetzlich das Bootstrap-Intervall (`ci95_lo > 0` und
`perm_p < 0.025`).
**Eingabe/Ausgabe.** Rein: Liste von Chip-Edges je Deck (Vorzeichen = Kandidat minus Incumbent). Raus: Dicts wie oben.
**Abhaengigkeiten.** Nur `random` aus der Standardbibliothek.
**Zustand.** Zustandslos, deterministisch (fester Bootstrap-Seed).
**Kosten.** `bootstrap_ci` = `2 * b * m` Additionen; bei 30 000 Decks und 3 % Kanal wenige Sekunden. Nicht gemessen.
**Mess-Status.** GEMESSEN POSITIV als Korrektur: die Neubewertung aller Runde-5-Verdikte mit dem Bootstrap liess
`turn_wert` halten (CI `[+2,69; +12,05]`, `p 0,0007`), liess `RN05` in 2 von 3 Laeufen fallen
(`data/autogym/journal.jsonl:68`, Typ `ESTIMATOR-V3`). Vorher war der 5-%-Trim eingebaut worden und musste
**zurueckgenommen** werden: bei duennen Guard-Kanaelen (8,4 % bzw. 1 % divergente Decks) entfernt die Trimmung genau
die Signal-Decks — der getrimmte Wert war 0,00 bei einem rohen `+1,64` (Docstring `:20-28`, journal.jsonl:54).
**Allein benutzbar?** Ja, vollstaendig — 109 Zeilen ohne Projektabhaengigkeit.
**Fallstricke.** Die Skala setzt **zwei Haende je Deck** voraus (HU-Spiegel mit Sitztausch). Fuer die 6-max-Arena
wird `haende_je_deck` anders gesetzt — wer das vergisst, misst um den Faktor der Sitzrotation daneben. Und: ein
`bb100 == 0.00` mit `nonzero == 0` bedeutet nicht „neutral", sondern „der Guard hat nie gefeuert" (siehe
`lizenz_guard`, `r7_bill`, `sel_all_m15`).

---

## v10-Pakete (River-Fundament)

Dieses Subsystem ersetzt eine hand-abhaengige River-Heuristik durch EINEN oeffentlichen, pro Hand einmal geloesten
River-Plan: eine Hero-Range wird ohne Blick auf die echten Hole-Karten rekonstruiert (K1), damit am River-Beginn ein
CFR-Subgame geloest (K2), die gespielte Sequenz exakt durch den Baum navigiert und die Aktion privat gesampelt.
Du brauchst das NUR, wenn du (a) einen GPU-River-Solver hast, (b) den Vorwurf "deine Range-Rekonstruktion liest heimlich
die eigene Hand" ausschliessen willst und (c) bereit bist, Messinfrastruktur mitzunehmen. **Es ist NICHT ausgeliefert:**
das Abnahme-Gate G3 ist verfehlt, der Champion blieb `auslese-v5` (`docs/V10_GATES_REPORT.md`, Abschnitt 4).

---

### Vertraege (Datentypen + Kanonisierung) — `pokerbot/strategy/contracts.py`
**Zweck.** Eingefrorene, solver- und strategiefreie Datentypen (frozen dataclasses) mit harter Validierung, die alle
v10-Teile als gemeinsame Sprache benutzen — plus die Regel, wie eine Engine-Aktion zu einem vergleichbaren Chip-Betrag
kanonisiert wird.

**Schnittstelle.**
- `karte_int(card) -> int` / `combo_index(c1, c2) -> int` / `combo_kanonisch(c1, c2) -> tuple` — Karten- und
  Combo-Kodierung (rank*4+suit, `_RANKS="23456789TJQKA"`, `_SUITS="shdc"`, 1326 Combos lexikographisch,
  `contracts.py:47-73`); identisch zu `gpu_cfr.combo_index`.
- `konfig_hash_aus(mapping) -> str` — sha256 ueber sortiertes JSON; der Fingerprint-Baustein aller Pakete.
- `ActionKey(kind, chips=None)` mit `fold()/check()/call()/raise_to(chips)` und
  `als_engine_aktion(legal) -> (action, amount)` — `bet`/`raise`/`allin` fallen auf `raise_to(chips)` zusammen,
  unterschieden wird NUR ueber den finalen ganzzahligen TO-Level (`contracts.py:82-121`).
- `kanonisiere(action, amount, state) -> ActionKey` — bildet die Engine-Regel nach: `int(amount)` (Truncation), dann
  stiller Clamp auf `[legal.raise_min, legal.raise_max]`; `allin` = `raise_max` (`contracts.py:124-155`).
- `kanonisiere_history_eintrag(h) -> ActionKey | None` — History-Zeile -> Key, `deal` -> None; liest nur `to`
  (float erlaubt), NIE `amount` bei `call`.
- `PolicySnapshot.aus_state(state, policy_id, konfig_hash)` — oeffentlicher Zustand OHNE jede Hole-Karte, mit
  `pot_bei_strassenbeginn()` (`pot − Σ committed_street`) und `legale_keys()`.
- `RangeState.aus(hero, villain, board, herkunft, konvention, rekonstruktions_status, versions_hash, hero_injiziert,
  hero_rolle)` — zwei Range-Vektoren mit Board-Maske; validiert hart: Board-Combos EXAKT 0, keine Doppel-Combos,
  bei `konvention="normiert_summe_1"` Σ=1 ± 1e-6, und `herkunft="k1_likelihood"` verbietet `hero_injiziert=True`.
- `PolicyTable(aktionen, zeilen, undefiniert, herkunft)` mit `p(combo, key)` / `verteilung(combo)` — jede Zeile Σ=1;
  `undefiniert` ist der Platz fuer Combos ohne Strategie (Reach 0), und `p()` gibt dort `None`, nicht 0.
- `RiverPlan(root, ranges, baum_hash, konfig_hash, knoten, aktueller_pfad, pot_river, schwelle_chips, aktiviert, …)` —
  validiert u. a. `aktiviert == (pot_river >= schwelle_chips)` (oeffentliches Gating, kein nachtraegliches Hochsetzen).
- `EntscheidungsTrace(basis, final, texassolver, guards, plan_verteilung, legalitaet, sample_u, fallback_status,
  offtree, deadline_status, hand_adresse, decision_addr)` — validiert die Kausalkette: echte Mischung ohne `sample_u`
  wirft, `final != legalitaet` wirft, `offtree=True` ohne `fallback_status="offtree"` wirft.
- Vokabular-Tupel: `ACTION_KINDS`, `FALLBACK_STATUS`, `DEADLINE_STATUS`, `REKONSTRUKTIONS_STATUS`,
  `RANGE_KONVENTION`, `RANGE_HERKUNFT`, `PRIVATE_SEED_QUELLE`, `SUMMEN_TOLERANZ = 1e-6` (`contracts.py:31-44`).

**Eingabe/Ausgabe.** Rein: ein Zustands-`dict` mit den Schluesseln `players` (je Sitz `stack`, `committed_street`,
`committed_total`, `hole`), `board`, `street`, `pot`, `current_bet`, `button`, `to_act`, `history`, `bb`, optional
`legal` (`to_call`, `can_check`, `can_call`, `can_raise`, `raise_min`, `raise_max`, `is_bet`) und optional `hand_id`.
Raus: die genannten frozen dataclasses; ungueltige Eingaben werfen `ValueError` statt still zu passieren.

**Abhaengigkeiten.** Nur Standardbibliothek (`hashlib`, `itertools`, `json`, `dataclasses`). Keine Engine, kein torch.
Das ist der einzige v10-Baustein ohne harte Repo-Bindung — er ist vollstaendig portierbar, solange dein Zustands-dict
die oben genannten Schluessel traegt.

**Zustand.** Zustandslos (alle Typen frozen). Nichts zurueckzusetzen.

**Kosten.** Nicht gemessen; reine Python-Objektkonstruktion. `PolicyTable.p()` ist eine lineare Suche ueber die Zeilen
(`contracts.py:425-434`) — bei 1326 Zeilen in einer Schleife ist das O(n²).

**Mess-Status.** UNGEMESSEN als EV-Wirkung (per Konstruktion: keine Strategie). Der eingebaute Selbsttest
(`python -m pokerbot.strategy.contracts`, `contracts.py:568`) lief im Gate G1 mit **250 Pruefungen gruen**
(`docs/V10_GATES_REPORT.md`, Gate-Tabelle G1; Rohdatei `data/runs/v10/G1_tests.txt`).

**Allein benutzbar?** Ja, als einzige Datei kopierbar. Minimal noetig: dein Zustands-Format auf die
Schnittmenge-Schluessel bringen. Der Selbsttest vergleicht `combo_index` gegen `gpu_cfr.combo_index`, wenn torch da
ist, und ueberspringt das sonst.

**Fallstricke.** `EntscheidungsTrace.basis` ist als `ActionKey` annotiert, aber K2 uebergibt dort im Plan-Pfad
bewusst `None` (Annotation zur Laufzeit ungeprueft, dokumentiert in `river_plan.py`-Docstring). Wer die Annotation
ernst nimmt und statisch prueft, bricht den einzigen produktiven Aufrufer.

---

### K1 — Hero-Likelihood-Replay — `pokerbot/strategy/hero_range.py`
**Zweck.** Rekonstruiert Heros OEFFENTLICHE Range am River-Beginn vorwaerts aus Prior x Board-Maske x
Aktions-Likelihood — ohne die echten Hole-Karten zu lesen.

**Schnittstelle.**
- `rekonstruiere(st0, guards=STANDARD_GUARDS, hero=None, konvention=K1_KONVENTION, advisor=None) -> K1Rekonstruktion`
  — der Hauptaufruf; liefert `hero_range` (kanonische Combos -> Gewicht, Σ=1), `villain_range` (Tracker),
  `status` (`ok` | `teilweise` | `fehlgeschlagen`), `grund`, `pot_river`, `knoten` (Protokoll je Hero-Knoten),
  `heur`/`total` (legality-only-Schritte).
- `hero_range_river_start(st0, guards, hero, konvention) -> dict` — nur die Range (leer bei Fehlschlag).
- `villain_range_river_start(st0, hero) -> dict` — Tracker-Villain-Range am River-Beginn.
- `range_state_river_start(...) -> contracts.RangeState` — dasselbe als validierter Vertrag; wirft bei Fehlschlag.
- `knoten_modell(zustand, seat, guards, konvention, combos, advisor) -> KnotenModell` und
  `action_likelihoods(...) -> PolicyTable` — die ausgefuehrte Politik AN EINEM Knoten je Combo, einzeln testbar.
- `bedingung_turn_wert(zustand, combo, villain_range) -> bool` / `bedingung_sel(...)` — die bitgenauen
  Guard-Bedingungen C(h).
- `prior_range(st0, hero, advisor)`, `knoten_liste(st0, hero)`, `lebende_combos(board)`,
  `schneide_am_river(st0)`, `versions_hash(guards, konvention)`.
- `Konvention(rolle_bet, size_faced, raise_modelliert)`; Konstanten `K1_KONVENTION` (Rolle nach INITIATIVE, echte
  Bet-Groesse) und `TRACKER_PARITAET` (Rolle nach POSITION, `size_faced=0.66`) — mit `guards=()` ist letztere
  byte-gleich zur Tracker-Hero-Range.

**Eingabe/Ausgabe.** Rein: ein vollstaendiger Hand-State (Engine-Form ODER GTOW-Adapter-Form) mit `history`, die
einen `deal`-Eintrag mit `street == "river"` enthaelt. Raus: `dict[(c1,c2) -> float]` mit Σ=1, Board-Combos entfernt,
plus Status und ein Protokoll je Knoten (`KnotenProtokoll`: `street`, `beobachtet`, `guard`, `guard_ziel`, `n_combos`,
`n_c`, `masse_c`, `modelliert`, `ziel_getroffen`).

**Abhaengigkeiten.** HART und tief: `pokerbot.strategy.range_tracker` (Prior `_init_preflop`, `_remove_dead`,
`_normalize`, Daempfung `TRACKER_ALPHA`/`TRACKER_AGGRO_FULL`, `_narrow_raise`), `pokerbot.autogym.improver`
(`_RANK_ORD`, `_spot_rng` — die Referenz fuer bitgenaues C(h)), `pokerbot.engine.equity.equity_vs_weighted_range`,
`pokerbot.engine.evaluator`, `treys` (optional; ohne treys feuert `turn_wert` nie), `contracts`,
`knowledge_base.math.formulas.equity_needed_to_call`. Die Advisor-MLPs (`p_bet_batch`/`p_defense_batch`) liefern die
Basis-Likelihood — fehlen sie, degradiert der Knoten auf `legality-only` und der Status wird `teilweise`.
**Ersetzbar ist praktisch nichts**: das Modul ist ein Spiegel EURES Bots. Fuer einen fremden Bot muesst ihr die
Likelihood-Quelle (Schritt 2) und die Guard-Transformationen (Schritt 3) komplett neu schreiben; nur das Geruest
(Replay der oeffentlichen Historie, `_Replay`, `ereignisse`, `_wende_an`) ist uebertragbar.

**Zustand.** Zustandslos nach aussen (jeder Aufruf baut einen frischen `RangeTracker`). Kein Reset noetig. Es gibt
KEINE Nebenwirkung auf RNG oder Tracker — das ist Absicht (`knoten_modell`-Docstring).

**Kosten.** Hoch und CPU-gebunden: je Hero-Knoten laeuft `equity_vs_weighted_range` mit `GUARD_EQUITY_ITERS = 160`
(`hero_range.py:63`) fuer JEDE lebende Combo. In der G2-Live-Messung war die K1-Range der Latenz-Treiber mit
**bis 5,7 s je Entscheidung** (`docs/V10_GATES_REPORT.md`, Abschnitt 6, Fix-Begruendung fuer
`K2_LIVE_DEADLINE_S = 12.0`, `pokerbot/autogym/pargate.py:53`).

**Mess-Status.** **REFUTIERT als Abnahme — Gate G3 VERFEHLT.** Gemessen gegen ein decide()-Orakel (offline-decide je
hypothetischer Combo): TV-Distanz **mittel 0,2085 · p95 0,758 · max 0,876**; nach Abzug des Orakel-Rauschbodens
(0,095) bleibt die untere Schranke **mittel 0,1446 · p95 0,620 · max 0,819** — Budget der Karte war
**0,02 / 0,05 / 0,10**. Auch auf Aktionsklassen-Ebene (statt Size) noch 0,1037. Zusaetzlich: Heros echte Hand lag in
**21/64** Faellen ausserhalb des K1-Supports. Quelle: `data/runs/v10/g3_k1_gate_20260907_231422.json`, zitiert in
`docs/V10_GATES_REPORT.md` Gate-Tabelle G3 und Befund R1/R3. Der EV-Beitrag der Range selbst ist UNGEMESSEN.
**Warum verfehlt:** das Advisor-Likelihood-Backend ist groessen-agnostisch (kennt nur bet-vs-check), die reale Basis
waehlt Sizes hand-abhaengig — die Rekonstruktion kann eine Size-Entscheidung strukturell nicht erklaeren. Groesster
Treiber sind `turn_wert`-Faelle (untere Schranke 0,325). Zusaetzlich ist die Karten-Annahme "`button_disziplin`
laesst den Prior unveraendert" messbar falsch (Orakel-Support 354 vs 838 Combos, Befund R3).

**Allein benutzbar?** Nein — ohne `range_tracker`, `improver` und die Advisor-Netze laeuft nichts. Uebernehmen kann
man die IDEE und die Struktur (Prior -> Board-Maske -> Produkt der Aktions-Likelihoods -> Normierung, mit einem
Status statt einer stillen Naeherung).

**Fallstricke.** Der `KnotenModell.likelihood`-Vertrag: `None` heisst "nicht modelliert" und der Aufrufer MUSS die
Combo dann unveraendert lassen (legality-only), `0.0` heisst "diese Combo haette so nie gehandelt". Wer `None` als 0
liest, kollabiert die Range auf Masse 0 — und `rekonstruiere` gibt dann Status `fehlgeschlagen` mit leerer Range
zurueck, nicht eine Exception.

---

### K2 — oeffentlicher River-Plan — `pokerbot/autogym/river_plan.py`
**Zweck.** Ein Wrapper um eine beliebige Strategie-Fabrik, der in grossen River-Poetten die Entscheidung nicht mehr
je Entscheidung, sondern aus EINEM am River-Beginn geloesten CFR-Plan zieht und privat sampelt.

#### Aktivierung
Rein oeffentlich und strassenweit: `ist_aktiviert(st, min_pot_chips) -> (bool, pot_river)` mit
`pot_river = pot − Σ committed_street` (`pot_river_aus_state`, `river_plan.py:114-131`). Default-Schwelle
`DEFAULT_MIN_POT_CHIPS = 1500` (= 15 bb bei bb=100, `river_plan.py:73`). Aktivierung haengt NICHT von den Hole-Karten
und nicht vom aktuellen Einsatz ab. Unterhalb der Schwelle und ausserhalb des Rivers laeuft die Basis unveraendert
durch, ohne Trace (`_entscheide`, `river_plan.py:710-714`).

#### Root-Rekonstruktion
`state_am_river_beginn(st)` (`river_plan.py:205`) schneidet die History nach dem River-Deal
(`river_deal_index`) und dreht die Chips auf River-Beginn zurueck: `committed_street = 0`, `stack += committed_street`,
`committed_total -= committed_street`, `pot = pot_river`, `current_bet = 0`, `to_act = 1 − button` (OOP zuerst) und ein
frisch gebauter `legal`-Block. Ohne River-Deal (stiller All-in-Run-out) gibt es keinen Root und keinen Plan.
`eff_stack_aus_state` = `min(stack + committed_street)`, ueber die Strasse invariant.

#### Ranges
`ranges_am_river_beginn(st0, hero_seat) -> RiverRanges | None` (`river_plan.py:283`): Villain immer via
`RangeTracker().build(st0)`, Hero via K1 (`_k1_hero_range`, lazy importiert). Akzeptierte K1-Status sind
`("ok", "teilweise")` (`K1_AKZEPTIERTE_STATUS`, `river_plan.py:240`, mit ausgeschriebener Begruendung); nur
`fehlgeschlagen`, ein K1-Import-Fehler oder eine Exception fuehren auf die Tracker-Hero-Range zurueck — mit Flag
`k1_fallback:<grund>`. Board-Combos werden hart auf 0 gefiltert (`_ohne_board_combos`). `root_hash_aus` hasht
Board + beide Ranges (auf `RANGE_QUANT_STELLEN = 6` quantisiert) + `pot_river` + `eff` + Rolle + Baum + Iterationen.

#### Solve
`loese_plan(st, hero_seat, hand_adresse, iters=150, half=False, …) -> GeloesterPlan | None` (`river_plan.py:454`)
ruft `gpu_cfr.RiverCFRBatch` DIREKT (B=1) mit ECHTEM `eff` (kein SPR-Bucket) und `pot_river` in Chips; Baum
`BAUM_KW = {"bet_sizes": (0.35, 0.75, 1.5), "raise_sizes": (2.7,), "max_raises": 2}` (`river_plan.py:72`),
`DEFAULT_ITERS = 150`, gemittelte Strategie (`avg_sigma`). `gpu_resolver.solve_spots` wird bewusst NICHT benutzt —
so gibt es keine Hero-Injektion und der bestehende v5-Pfad bleibt byte-identisch. `Zeiten(ranges_s, solve_s,
gesamt_s)` wird immer gemessen (`cuda.synchronize` vor dem Stoppen, `_gpu_fertig`).

#### Navigation
`navigiere(gp, st) -> Navigation(pfad, status, grund)` (`river_plan.py:510`) laeuft die gespielten River-Schritte
durch den Baum. Jeder Schritt muss auf **±`OFFTREE_TOLERANZ_CHIPS` = 1 Chip** genau auf einen Arm treffen
(`arm_index_fuer` / `_passt_raise`) — **kein Nearest-Snapping**. Ein TO-Level >= `eff` wird auf `eff` geclippt (der
deckende Villain darf mehr setzen). Status `offtree` (Villain-Size nicht im Baum), `fehler` (`akteur_desync`,
`terminal_erreicht`, `hero_nicht_am_zug`, `kein_river_deal`) oder `ok`.

#### Private Randomisierung
`private_u(private_seed, hand_adresse, decision_addr) -> float` = keyed blake2b / 2^64 (`river_plan.py:175`).
Seed-Herkunft: `modus="gym"` -> `privater_seed_gym(hand_adresse, seat)` = blake2b mit festem `GYM_SALZ`
(deterministisch, damit A/A exakt 0 bleibt); `modus="live"` -> `prozess_seed()` = `os.urandom(16)` einmal je Prozess;
`privater_seed=` ueberschreibt beides (`test_seed`). Verteilung und Sampling sind GETRENNT:
`GeloesterPlan.verteilung()` liefert die Zeile, `sample_aus_verteilung(probs, u)` waehlt. `ist_degeneriert(probs)`
(ein p mit |p−1| ≤ 1e-6) heisst argmax OHNE Zufallszahl — degenerierte Knoten verbrauchen kein u.

#### Fallback-Status
`_fallback` schreibt einen Vertrags-Status und ruft `base(st)`:
- `offtree` — Villain-Size trifft den Baum nicht.
- `deadline` — live: Solve nicht rechtzeitig (Flag `deadline_in_queue`, wenn er nicht einmal begann).
- `hand_not_in_range` — Heros echte Combo hat in der oeffentlichen Range Gewicht 0. Die `avg_sigma`-Zeile waere dort
  uniform 1/n (Reach-0-Phantom) und darf NIE als Strategie gelesen werden; `verteilung()` gibt deshalb `probs=None`
  (`river_plan.py:403-414`). Das ist ein Vertrag, kein Knopf.
- `fehler:<Typ>` — Solve-Exception oder `root_nicht_rekonstruierbar`.
In Plan-Pots wird `base(st)` sonst NICHT gerufen (Entscheidung E1) — der darunterliegende Resolver entfaellt dort.

#### Live-Parallelitaet
`_LaufenderSolve` je Hand: eine Folge-Entscheidung derselben Hand wartet auf DIESELBE Future (`solve_geteilt`) statt
neu zu loesen. Die Deadline zaehlt ab Solve-START; die Queue-Wartezeit hat ihr eigenes Budget
(`QUEUE_BUDGET_S = 3.0`, `river_plan.py:84`), `LIVE_SOLVE_WORKER = 3` (`river_plan.py:82`). Ein verspaetetes Ergebnis
wird fuer die verpasste Entscheidung verworfen, aber gecacht (`plan_verspaetet_genutzt`). `aufwaermen()` traegt den
CUDA-Kaltstart (2-3 s) vor der ersten Hand ab. LRU-Cache `CACHE_GROESSE = 16` Plaene je Sitz; ein Cache-Treffer mit
abweichendem `pot_river`/`eff`/`button` wird verworfen (`cache_root_abweichung`).

#### Trace
`_schreibe_trace` schreibt je Plan-Pot-Entscheidung eine JSONL-Zeile (`trace_pfad`): `version`, `seat`,
`hand_adresse`, `decision_addr`, `fallback_status`, `offtree`, `deadline_status`, `flags` (sortiert), `basis`,
`final`, `legalitaet`, `sample_u`, `gewaehlter_arm`, `plan_verteilung`, `pfad`, `root_hash`, `baum_hash`,
`pot_river`, `eff`, `range_herkunft`, `private_seed_quelle` — plus `latenz_ms` und `zeiten_ms`
(`queue`/`ranges`/`solve`/`gesamt`) NUR im Live-Modus, damit der Gym-Trace byte-deterministisch bleibt.
`statistik(seat)` zaehlt `plan_pot_entscheidungen` und jeden `fallback_status`.

**Schnittstelle (Kurzform).** `river_plan_guard(make_strat, min_pot_chips=1500, iters=150, deadline_s=None,
trace_pfad=None, privater_seed=None, modus="gym", solve_worker=3, queue_budget_s=None, aufwaermen=True)
-> RiverPlanFabrik`; die Fabrik ist `f(seat) -> d(st) -> (action, amount)` — dasselbe Muster wie die uebrigen
Guard-Wrapper. Diagnose: `letzter_plan(seat)`, `letzter_trace(seat)`, `statistik(seat)`, `basis_aufrufe(seat)`,
`private_seed_quelle`, `private_seed_hex`.

**Eingabe/Ausgabe.** Rein: derselbe Zustands-`dict` wie die Basis-Strategie (Engine- oder Adapter-Form), idealerweise
mit `hand_id` — sonst faellt die Hand-Adresse auf einen Karten-Hash zurueck (Flag `cache_key_ohne_hand_id`).
Raus: `(action, amount)` in Engine-Konvention (`amount` = Raise-TO-Level), erzeugt von `legalisiere()`
(`river_plan.py:539`): `fold` bei `to_call == 0` -> `check`; Bet/Raise nur wenn Gegner nicht all-in und
`stack > to_call`; `betrag >= stack − 1` -> `allin`.

**Abhaengigkeiten.** HART: `pokerbot.strategy.gpu_cfr` (`RiverCFRBatch`, `range_vector`) + torch/CUDA;
`pokerbot.strategy.range_tracker`; `contracts`. WEICH/ersetzbar: `pokerbot.strategy.hero_range` (K1) wird LAZY
importiert und faellt sauber auf den Tracker zurueck — das Modul laeuft ohne K1.

**Zustand.** Je Sitz ein `_SitzZustand` mit LRU-Plan-Cache (je Hand), laufenden Solves, Zaehlern und letztem
Trace/Plan. Der Cache lebt ueber Haende hinweg und wird nur ueber die Hand-Adresse und die Root-Kontrolle
invalidiert — es gibt KEIN explizites `reset()`. Wer Haende ohne eindeutige `hand_id` spielt, muss das wissen.
`_PROZESS_SEED` ist ein Prozess-Singleton (live).

**Kosten.** Solve gemessen ~2,5 s je Hand, K1-Ranges bis 5,7 s (Live-Kanal, `docs/V10_GATES_REPORT.md` Abschnitt 6).
Live-Latenz nach dem Mechanik-Fix: p50 3,04 s / p90 8,50 s / p99 10,15 s (n=40, ebd.). Ein Solve laeuft in einem
Thread; mehrere Solves serialisieren sich am GIL (Modul-Docstring, Messung 2026-09-07).

**Mess-Status.** GEMISCHT, live NIE als EV verankert.
- Gym-Spiegel gegen den Champion: `r10_stack` vs `r8_stack`, **n=1968 Decks: +11,68 ± 10,85 bb/100, CI95
  [−9,39, +33,06], verdict NEUTRAL, perm_p 0,156** (`data/runs/20260908_002035_pargate_r10_stack/result.json`, zitiert
  in `docs/V10_GATES_REPORT.md` Gate G5). Also **NEUTRAL**.
- Ausbeutbarkeit im K3-Pruefstand (Gym-Kanal, n=11 Holdout-Roots): **ΔE_H = w(A) − w(B) = −10,08 ± 1,66 bb/Root =
  −113,0 ± 18,6 bb/100**, alle 11 Roots negativ (= der Plan ist weniger ausbeutbar), ΔRegret −4,04 ± 0,99 bb/100
  (Gate G4). Aber: Arm A lief im GYM (ohne TexasSolver), der Betrag ist **nicht** auf Live uebertragbar.
- Live-Mechanik (n=40 Plan-Pots): Plan gespielt 25/40, `offtree` 11/40, `hand_not_in_range` 4/40, `deadline` 0/40
  (`docs/V10_GATES_REPORT.md` Abschnitt 6).
- Gate G2 (Latenz) **VERFEHLT**: Plan-Pot-p99 10,15 s ≥ 8 s und v10-p99 > v5-H-p99 (8,20 s).
- **Der Katastrophenherd ist der Fallback, nicht der Plan:** alle drei Gym-Decks ≤ −100 bb entstanden in der nackten
  Basis (2x `offtree`, 1x Sub-Schwellen-Pot), die drei reinen Plan-Decks waren alle positiv (+219 bb) —
  Befund R4, `data/runs/v10/g5_divergenz_replay.log`.
- A/A-Nulltest nach der letzten Code-Aenderung: **576 Decks EXAKT 0** (`data/runs/20260908_015248_pargate_r10_stack/
  result.json`).

**Allein benutzbar?** Ja, wenn du (1) einen River-CFR-Solver mit der `RiverCFRBatch`-Schnittstelle
(`avg_sigma(node)`, `root`, `node.acts/kids/actor/invest`) hast, (2) eine Villain-Range-Quelle und (3) eine
Basis-Strategie als `make(seat) -> d(st) -> (action, amount)`. K1 ist optional. Ohne CUDA laeuft es auf CPU-torch,
aber die Latenzzahlen oben gelten dann nicht.

**Fallstricke.** Die **Size-Konvention des Baums**: `bet{f}` investiert `f · Pot AM KNOTEN` (inklusive aller
bisherigen River-Einsaetze), NICHT `f · pot_river`; `raise2.7` investiert 2,7 · to_call ZUSAETZLICH; Arme ab 85 %
des Reststacks fallen mit dem Jam zusammen. Wer das falsch liest, bekommt bei jedem zweiten Knoten `offtree` und
merkt es nur am Zaehler. Zweiter Stolperstein: die Docstrings von `river_plan_guard` und des Moduls nennen noch die
ALTEN Werte (`LIVE_SOLVE_WORKER = 1`, `QUEUE_BUDGET_S = 0,5 s`, Deadline 7,5 s) — die Konstanten sind 3 / 3,0 und die
Live-Deadline steht in `pargate.py:53` auf 12,0.

---

### K4 Produktionsintegritaet — Laufzeit-Fingerprint + Fehlkonfig-Gatter — `pokerbot/runtime_config.py`
**Zweck.** Beantwortet je Prozess die Frage "WELCHER Bot hat diese bb/100-Zahl erspielt?" — aus dem laufenden Objekt
und den bei Import eingefrorenen Modulkonstanten, nicht aus der Env-Absicht.

**Schnittstelle.**
- `fingerprint_geladen(bot, stack_name) -> dict` — der Fingerprint. Pflichtfelder (`PFLICHTFELDER`,
  `runtime_config.py:64`): `git`, `advisor_pt`, `prince`, `prince_geladen`, `prince_importflags`, `gto_mode`,
  `gto_mode_flags`, `exploit`, `use_resolver`, `use_turn_resolver`, `stack`, `turn_defense`, `slowplay`,
  `gpu_solver`, `k1_version`, `river_plan`, `private_seed_quelle`, `pythonhashseed`, `pid`, `fingerprint_hash`.
- `fingerprint_hash(fp) -> str` — sha256 ueber den strategie-relevanten Teil; `_NICHT_IM_HASH = ("pid", "zeit_utc",
  "fingerprint_hash", "python", "advisor_geladen_jetzt")` haelt den Hash prozess- UND warm-up-invariant.
- `pruefe_konfiguration(erwartet, ist)` — `SystemExit` mit ALLEN Abweichungen (nicht nur der ersten).
- `gatter_aus_env(fp, log=print) -> str | None` — liest `POKERB_ERWARTE_PROFIL`; gesetzt = scharf, unset = nur loggen.
- Bausteine einzeln: `git_stand()`, `sha256_datei()`, `advisor_hashes(bot)`, `advisor_geladen_jetzt()`,
  `gpu_solver_version()`, `k1_version()`, `river_plan_konstanten()`, `private_seed_quelle(bot)`,
  `prince_importflags()`, `prince_abweichungen(importflags, exploit)`.
- Profile: `ERWARTUNGSPROFILE = {"v5-H": {... "stack": "r8_stack"}, "v10": {... "stack": "r10_stack"}}`.

**Eingabe/Ausgabe.** Rein: das lebende Bot-Objekt (gelesen werden `exploit`, `use_resolver`, `use_turn_resolver`,
`use_probe`, `use_deepcfr`, `use_blueprint`, `use_range_tracker`, `private_seed_quelle`) + der Name des um `decide`
gewickelten Stacks. Raus: ein flaches JSON-taugliches dict + ein Hash-String; oder `SystemExit`.

**Abhaengigkeiten.** HART auf dieses Repo: `pokerbot.config`, `pokerbot.strategy.gto_mode` (`PRINCE_PROFILE`,
`enabled()`, `fingerprint()`), `contracts`. Die Liste `_PRINCE_IMPORTKONSTANTEN` (`runtime_config.py:40-47`) nennt
Env-Key, Modul, Konstante und Parser fuer sechs Flags namentlich — fuer einen anderen Bot ist das die einzige Stelle,
die man neu schreiben muss, aber sie ist komplett projektspezifisch.

**Zustand.** Zustandslos; jeder Aufruf liest neu. `git_stand()` startet zwei `subprocess`-Aufrufe
(`_GIT_TIMEOUT_S = 10`).

**Kosten.** Nicht gemessen. Dominiert von den zwei git-Aufrufen und den sha256-Hashes der Advisor-`.pt`-Dateien —
einmal je Prozessstart, nicht je Hand.

**Mess-Status.** UNGEMESSEN als EV (per Konstruktion kein Strategie-Code). Gemessene WIRKUNG: Im Gate G1 lief
`test_runtime_config` mit **19 OK, 1 skip** und das Fehlkonfig-Gatter brach einen v10-Erwartungslauf auf `r8_stack`
korrekt mit exit 1 ab (`docs/V10_GATES_REPORT.md` Gate G1). Anlass des Moduls ist ein belegter Schaden: der
GTOW-Harness lief zuvor ohne jede Konfig-Pruefung und die HU-Web-App spielte eine nie gemessene Konfiguration
(Modul-Docstring, `docs/HU_OPTIMAL_KARTE.md` D1).

**Allein benutzbar?** Das Muster ja, der Code nein. Uebertragbar sind die zwei Ideen, die hier teuer gelernt wurden:
(1) unterscheide **Env-Absicht** von **eingefrorenem Import-Zustand** — wird ein Strategie-Modul VOR dem Setzen einer
Env-Variable importiert, bleibt die Konstante fuer immer falsch, waehrend die Absichts-Abfrage "an" meldet;
(2) nimm Laufzeit-Zustand (welche Netze der Lazy-Cache gerade haelt) aus dem Hash, sonst kippt er nach dem Warm-up
und zwei Chunks desselben Arms sind nicht mehr vergleichbar.

**Fallstricke.** `prince_importflags()` importiert die Strategie-Module selbst. Ruft man den Fingerprint zu frueh —
vor dem Setzen der Env — friert man die Konstanten mit der falschen Env ein und der Fingerprint meldet trotzdem
"OK", weil er genau das misst, was jetzt geladen ist. Reihenfolge: Env setzen, dann Bot bauen, dann Fingerprint.

---

### K4 Hand-Ledger — `pokerbot/benchmark/gtow_ledger.py`
**Zweck.** Append-only JSONL-Ledger, das jedes Hand-Ereignis eines Benchmark-Laufs SOFORT auf Platte schreibt, damit
ein Abbruch nichts verliert und ein Wiederanlauf die offenen Haende kennt.

**Schnittstelle.**
- `GtowLedger(pfad=None)` mit `prozess_start(fingerprint)`, `hand_start(hand_id, arm, fingerprint_hash)`,
  `hand_end(hand_id, aivat, winnings, status, technische_events=())`, `offene_haende()`.
- Dateibasierte Leser: `lese(pfad)`, `abgleich(pfad) -> {offen, abgeschlossen, doppelt_gestartet}`,
  `offene_haende(pfad)`, `offene_haende_alle(verzeichnis)`.
- Prozess-Singleton + exception-freie Hooks: `standard_ledger()`, `melde_hand_start(agent, hand_id)`,
  `melde_hand_ende(agent, hand_id, terminal, status="ok", technische_events=())`.
- `STATUS = ("ok", "unbekannt", "fehler")`; `python -m pokerbot.benchmark.gtow_ledger` listet offene Haende.

**Eingabe/Ausgabe.** Rein: `hand_id`, ein Arm-Name (Env `POKERB_ARM`, sonst `agent.stack_name`, sonst Klassenname),
ein Fingerprint-Hash, und beim Ende ein Terminal-Objekt (`GameServiceResponse` mit `game_state.aivat_score` /
`.winnings`, oder ein Mapping). Raus: eine JSONL-Zeile je Ereignis mit `typ`, `zeit`, `pid` — Datei
`data/runs/v10/ledger_<prozess-start>.jsonl`, ueberschreibbar via `POKERB_LEDGER_PFAD`.

**Abhaengigkeiten.** Nur `pokerbot.config` fuer das Verzeichnis; die Agenten-Hooks greifen defensiv per `getattr`.
Praktisch ersetzbar durch drei Zeilen eigenen Code — der Wert liegt in den Regeln, nicht im Code.

**Zustand.** Je Prozess ein Singleton mit Mengen `_gestartet`/`_beendet`, die beim Konstruieren AUS DER DATEI
rekonstruiert werden (Doppelstart wird auch ueber Prozessgrenzen erkannt). `schreibfehler` wird gezaehlt und beim
naechsten erfolgreichen Write nachgetragen.

**Kosten.** Ein `flush()` + `os.fsync()` je Ereignis — bewusst teuer. Nicht gemessen.

**Mess-Status.** UNGEMESSEN (keine EV-Wirkung moeglich). Belegter Anlass: der alte Harness schrieb die
Hand-Histories erst NACH allen Haenden mit `open('w')`, **Chunk 4 der Nacht 2 ging komplett verloren**
(Modul-Docstring, `docs/V10_FAKTEN.md` A8). Im Gate G1 wurden Prozessabbruch und Ledger-Write-Fault getestet
(`docs/V10_GATES_REPORT.md`, Abschnitt 2).

**Allein benutzbar?** Ja, eine Datei ohne echte Abhaengigkeiten (ausser dem Verzeichnis).

**Fallstricke.** Die harte Regel steckt in `hand_end`: `status == "ok"` mit `aivat is None` wird automatisch zu
`"unbekannt"` heruntergestuft — **ein unbekannter Ausgang wird NIE zu 0 imputiert**. Wer diese Zeile beim Portieren
"vereinfacht", bekommt einen sauber aussehenden Mittelwert aus fehlenden Daten.

---

### K3 — Policy-Oracle (die ausgefuehrte Politik als Tabelle) — `research/policy_oracle.py`
**Zweck.** Liefert die Verteilung der TATSAECHLICH ausgefuehrten Bot-Politik je Hero-Combo an einem River-Knoten als
`contracts.PolicyTable` — damit eine bestehende Heuristik im selben Spiel bewertbar wird wie ein Solver.

**Schnittstelle.**
- `PolicyOracle(kanal="gym", seeds=4, workers=4, stack="r8_stack", cache_dir=CACHE_DIR)`.
- `.tabelle(root_hash, st, hero_seat, combos=None) -> (PolicyTable, meta)` — nur nicht gecachte Combos werden
  gerechnet, die Cache-Datei traegt die Union aller Anfragen.
- `.direkt(st, hero_seat, combos, seeds) -> {(combo, seed): key_str}` — Referenz-Aktionen der VOLLEN Kette fuer den
  Identitaetstest.
- `.roh(root_hash, st, combos)` — je Seed/Label die finale und die Basis-Aktion (die Chirurgie sichtbar machen).
- `.schliessen()` — Pools beenden (Pflicht, sonst haengen die Prozesse).
- Freie Helfer, die auch andere v10-Werkzeuge importieren: `lebende_combos(board)`, `combos_mit_masse(vektor)`,
  `zustand_nach_pfad(root_state, pfad, hero_seat)` (Engine-Chip-Buchhaltung), `legal_fuer(st, seat, min_raise)`,
  `mit_hole(st, hero_seat, combo)`, `knoten_hash(st)`, `erster_hero_knoten(root)`, `code_fingerprint()`,
  `chirurgie(a, amt, st, res, …)` (die GPU-Guard-Regel als reine Funktion).
- CLI: `python -m research.policy_oracle --split entwicklung --roots 2 --seeds 2 --kanal gym --workers 4`.

**Eingabe/Ausgabe.** Rein: ein Engine-State am Hero-Knoten + der `root_hash` des Roots. Raus: `PolicyTable` (Zeilen
je Combo, `undefiniert` fuer Combos ohne Zeile) + `meta` mit `herkunft`, `fehler`, `gpu_solve_fehler`, `gueltig`,
`sekunden`, `sekunden_gpu`. Cache-Dateien unter `data/runs/v10/policy_oracle_cache/`, Schluessel
`(root_hash, knoten_hash, kanal, S, stack, code_fingerprint)`.

**Abhaengigkeiten.** HART und maximal projektspezifisch: es zerlegt genau EINE bekannte Stack-Komposition
(`r8_stack == river_gpu_guard(r7_wert)`, `pargate.py:100-108`) in "Basis-decide je Combo ueber S Seeds" plus
"Chirurgie-Regel". Ausserdem `pokerbot.autogym.pargate._baue_fabrik`, `pokerbot.strategy.gpu_resolver.solve_spots`,
torch/CUDA, `contracts`. Der Konstruktor wirft, wenn `stack != "r8_stack"`.

**Zustand.** Zwei `multiprocessing`-Pools (spawn): ein CPU-Pool fuer die decide()-Aufrufe, ein Pool(1) fuer die
GPU-Solves (die GPU wird nie von mehreren Prozessen geteilt — 12 Worker liefen in CUDA-OOM, das der Guard still
schluckte). Plus ein Platten-Cache. `schliessen()` ist Pflicht; die Worker setzen die Kanal-Env VOR dem Bot-Import.

**Kosten.** GEMESSEN (RTX 3080 Ti, 150 Iter fp32): **209 ms/Spot bei max_batch=192, 215 ms bei 64** —
bandbreiten-bound, die Batch-Groesse bringt nichts; **1081 Combos ≈ 226 s je GPU-Knoten** (Modul-Docstring,
`policy_oracle.py:26-33`). Deshalb `GPU_BATCH_MAX = 64` (2,7 GB Peak statt 5,3 GB). Der volle Holdout (224 Roots)
wurde auf **≈ 33 h kalt** geschaetzt (`docs/V10_GATES_REPORT.md`, Abschnitt 2, Zeile G4).

**Mess-Status.** Als Werkzeug validiert, nicht als Strategie: der Identitaetstest gegen das DIREKTE decide() der
vollen Kette lief **60/60** und die K3-Kontrollen insgesamt **15/15 gruen**
(`data/runs/v10/g4_logs/kontrollen_tests.log`, zitiert in `docs/V10_GATES_REPORT.md` Gate G1).
Der `--kanal live` (PRINCE + Resolver ON) fiel im G4-Pilot auf `UNSUPPORTED` (473 s fuer den schmalsten Root,
`REACH_EPS`-Inkonsistenz) — der Live-Kanal ist damit **UNGEMESSEN**.

**Allein benutzbar?** Nein. Die Idee ist uebertragbar (befrage deine eigene Politik mit ausgetauschten Hole-Karten
ueber S Seeds und lies das Ergebnis als Verteilung), der Code nicht.

**Fallstricke.** Ein Tabellenlauf mit `gpu_solve_fehler > 0` wird NICHT gecacht und ist ungueltig — wer den
Rueckgabewert ohne `meta["gueltig"]` verwendet, rechnet mit halben Tabellen. Und: der `code_fingerprint()` gehoert in
den Cache-Schluessel, sonst ueberlebt eine alte Politik jede Code-Aenderung im Cache.

---

### K3 — River-Best-Response-Pruefstand — `research/river_br_pruefstand.py`
**Zweck.** Bewertet zwei Hero-Politiken (bestehende Heuristik vs Solver-Plan) im SELBEN River-Root-Spiel mit exakter
Villain-Best-Response — die einzige Stelle im Repo, die "weniger ausbeutbar" als Zahl belegt.

**Schnittstelle.**
- `bewerte_root(root, orakel=None, arm_a="purify", villain_familie="tracker") -> dict` — ein Root.
- `baue_baum(pot, eff, bets_je_rolle, raises_je_rolle, …) -> Node`, `knoten_mit_pfad`, `zusatzarme`.
- `br_gegen_fest(spiel, root, sigma_fest, spieler_br) -> (wert, vektor)` — EXAKTE Best-Response, informationsmengen-
  treu (Villain maximiert je EIGENER Combo gegen die Hero-reach-gewichtete Summe).
- `garantiewert(spiel, root, sigma_hero, hero_rolle)`, `lokaler_regret(cfr_q, root, spiel, sigma_pi, hero_rolle)`,
  `reach_je_knoten`, `sigma_aus_cfr`, `sigma_auf_baum(sigma_quelle, baum_quelle, baum_ziel, rolle)`,
  `purifiziere(sigma)`.
- `sigma_arm_a(orakel, root, spiel, r_hero, hero_rolle)` — baut den Evaluationsbaum durch iterative SCHLIESSUNG
  (Hero-Arme = K2-Baum ∪ exakte Chipbetraege der Heuristik je Knoten, max `MAX_SCHLIESSUNGSRUNDEN = 3`).
- `aggregiere(ergebnisse, n_haende, n_roots_ge_schwelle)`, `schreibe_report(name, konfig, ergebnisse, agg)`.
- `Unsupported` — Root nicht darstellbar; wird AUSGEWIESEN, nie projiziert.
- CLI: `python -m research.river_br_pruefstand --split holdout --arm-a oracle --kanal gym --seeds 4 --workers 8
  --roots 224 --zeitbudget-s 5400 --name …`; `--arm-a` in `("purify", "identisch", "oracle")`.

**Eingabe/Ausgabe.** Rein: ein Root-dict aus `research/k3_roots.py` (`board`, `pot_river`, `eff`, `hero_oop`,
`ranges`, `root_state`, `hand_id`, `provenienz`). Raus je Root: `w_a_bb`, `w_b_bb`, `delta_e_h_bb`, Klammer
`L_bb`/`U_bb`, `e_h_a_band_bb`, `regret_a_bb`, `regret_b_bb`, `delta_regret_bb`, `expl_b_pct_pot`,
`n_knoten_eval`, `n_zusatz_arme`, `status` (`ok` | `UNSUPPORTED` + `grund`). Aggregat: Mittel + SE je Root und
`bb100_alle_haende` (Mittel x 100 x Auswahlgewicht = Roots ≥ Schwelle / alle Haende des Splits).

**Abhaengigkeiten.** HART: torch, `pokerbot.strategy.gpu_cfr` (`RiverCFRBatch`, `Node`, `range_vector`,
`showdown_matrix`), `research.policy_oracle`, `research.k3_roots`, `contracts`. `--arm-a purify`/`identisch`
brauchen KEIN Oracle — damit laeuft der Pruefstand als reines Solver-Werkzeug.

**Zustand.** Zustandslos je Root; das Oracle (falls benutzt) traegt seine Pools und den Cache.

**Kosten.** Je Root: ein 150-Iter-Solve (Arm B) + ein 600-Iter-Solve (Q-Urteile) + im Oracle-Modus die
Knoten-Tabellen (~0,21 s GPU je Combo). `--zeitbudget-s` bricht kontrolliert ab und weist das im Report aus.
11 Roots liefen in einem 5400-s-Budget durch (`docs/V10_GATES_REPORT.md` Gate G4).

**Mess-Status.** Werkzeug validiert (Matching-Pennies-Fixture, Karten-Fixture ≤1e-6, A/A exakt 0, Oracle-Identitaet
60/60 — **15/15 gruen**, `data/runs/v10/g4_logs/kontrollen_tests.log`). Ergebnis Gate G4: **UNVOLLSTAENDIG** —
ΔE_H **−10,08 ± 1,66 bb/Root = −113,0 ± 18,6 bb/100** (Bootstrap-OG95 −85,4), 11/11 Roots negativ; ΔRegret
**−4,04 ± 0,99 bb/100**; Sensitivitaet mit Villain=Preflop-Null: −126,2 ± 16,8 (gleiches Vorzeichen);
UNSUPPORTED 0/11. **Warum unvollstaendig:** die Karte verlangte ≥ 20 Roots und Arm A im LIVE-Kanal; gemessen wurden
11 Roots im GYM-Kanal (der Live-Pilot `G4_pilot_live_2981343.json` endete `UNSUPPORTED`). Live spielt der Champion in
93 % der River-Entscheidungen den TexasSolver — der Betrag ist deshalb nicht uebertragbar, nur die Richtung.

**Allein benutzbar?** Der Solver-Teil ja (`--arm-a purify` vergleicht die gemittelte CFR-Strategie gegen ihre eigene
purifizierte Version — ein sauberer Selbsttest ohne jede Bot-Abhaengigkeit). Der Oracle-Teil nur mit diesem Repo.

**Fallstricke.** Zwei teuer gelernte Fallen stecken im Code als Kommentar: (1) Arm B wird auf dem K2-Baum geloest und
MUSS vor der Bewertung per Label auf den Evaluationsbaum abgebildet werden (`sigma_auf_baum`) — sonst sind die
Spalten verschoben, sobald die Schliessung einen Arm hinzufuegt; (2) die Obergrenze U muss auf dem
EVALUATIONSBAUM berechnet werden, nicht auf dem K2-Baum, sonst ist das Band falsch beschriftet. Und:
`SIZE_TOL_CHIPS = 1.0` ist Absicht — ein 8-%-Toleranzfenster projizierte 0,67-Pot-Bets auf 0,75.

---

### K3 — River-Roots aus Hand-Histories — `research/k3_roots.py`
**Zweck.** Extrahiert je Quellhand GENAU EINEN River-Root (Zustand vor der ersten River-Aktion) aus geloggten
Hand-Histories und persistiert Geometrie, Engine-State und beide Ranges als JSONL.

**Schnittstelle.**
- `dateien_je_split(split) -> {Dateiname: Provenienz}` — `holdout` = vier namentlich fixierte Dateien,
  `entwicklung` = die Arme aus `research.hh_luecken_mine.ARME`.
- `extrahiere_roots(dateien, split) -> (roots, ausschluss_zaehler, n_haende)`.
- `schreibe_roots(split, roots, zaehler, n_haende, dateien) -> Path` — JSONL mit Kopfzeile.
- `lade_roots(split, min_pot=0.0) -> (kopf, roots)` — Ranges als Combo-Tupel-Dicts zurueckgewandelt.
- `river_sequenz(riv, hero_seat)`, `root_hash(board, pot_river, eff, hero_oop, vill)`,
  `range_als_json` / `range_aus_json`.
- CLI: `python -m research.k3_roots --split entwicklung` bzw. `--split holdout`.

**Eingabe/Ausgabe.** Rein: JSONL-Hand-Histories aus `data/sessions/` (je Zeile eine Hand mit `hand_id`, `aivat`,
`winnings` und den Aktionen). Raus: `data/runs/v10/k3_roots_<split>.jsonl` — Kopfzeile mit `n_haende`, `n_roots`,
`ausschluss`, `hero_k1`, `pot_river_ge_1500`; dann je Root `board`, `pot_river`, `eff`, `hero_seat`, `button`,
`hero_oop`, `hero_hole`, `seq_river`, `aivat_bb`, `win_bb`, `root_hash`, `hero_k1_status`,
`ranges.{hero_tracker, vill_tracker, hero_k1}` und `root_state` (der live-treue Engine-State).

**Abhaengigkeiten.** HART auf die Replay-Kette dieses Repos: `research.gtow_tree_census` (`BB`, `hero_seat_of`,
`replay`), `research.hh_luecken_mine` (`ARME`, `SESS`, `replay_voll`), `research.river_bill_replay.spot_state`,
`pokerbot.strategy.range_tracker`. K1 wird LAZY importiert (fehlt es: `hero_k1_status="fehlt"`, kein Abbruch).

**Zustand.** Zustandslos; schreibt eine Datei je Split.

**Kosten.** Nicht als Zahl belegt (der CLI druckt die Laufzeit je Lauf). Der Holdout-Split hat **224 Roots**
(`docs/V10_GATES_REPORT.md` Gate G4).

**Mess-Status.** UNGEMESSEN (Datenaufbereitung). Die Ausschluss-Zaehler sind der Ehrlichkeits-Kanal:
`aivat_none`, `hero_seat_none`, `kein_river`, `rekonstruktion` (Pot-Gatter |pot_eigen − pot| > 1 Chip), `eff_null`,
`range_leer` — sie stehen in der Kopfzeile jeder Ausgabedatei.

**Allein benutzbar?** Nein, ohne die Replay-Kette nicht. Uebertragbar ist die Disziplin: EIN Root je Hand,
Ausschluesse gezaehlt statt still weggelassen, der Split `holdout` namentlich eingefroren.

**Fallstricke.** Der Holdout-Split stammt aus einem Lauf mit ANDERER Provenienz (`v4_gym_nackt`, exploit ON,
Resolver OFF). Nur Root-Geometrie und Villain-Range daraus sind benutzbar — Heros damalige Aktionen sind
ausdruecklich KEIN Lehrsignal (Modul-Docstring).

---

### Golden-Set / Divergenz-Smoke — `research/golden_set.py`
**Zweck.** Beweist Byte-Identitaet einer Referenz-Politik VOR und NACH einer Infrastruktur-Aenderung, indem zwei
Stacks auf N festen Decks gegeneinander laufen und die Edge JE DECK auf Platte landet.

**Schnittstelle.** Nur CLI + eine interne Funktion:
`python -m research.golden_set --a r8_stack --b basis --decks 40 --seed 424242 --out <datei>.json` erzeugt den
Lauf; `python -m research.golden_set --vergleich ALT NEU` druckt `IDENTISCH` oder `ABWEICHUNG in Decks [...]` und
setzt den Exit-Code (0/1).

**Eingabe/Ausgabe.** Rein: zwei Stack-Namen aus `pargate`, Deck-Anzahl, Seed. Raus: JSON mit `a`, `b`, `decks`,
`seed`, `sek_je_deck`, `edges` (Liste je Deck), `nonzero`, `summe`.

**Abhaengigkeiten.** `pokerbot.autogym.pargate._baue_fabrik`, `pokerbot.benchmark.duplicate` (`duplicate_ab`,
`gen_decks`), torch (nur um die Threadzahl zu fixieren). Ersetzbar durch jeden gepaarten Duplicate-Runner.

**Zustand.** Zustandslos. Setzt bewusst `OPENBLAS/OMP/MKL_NUM_THREADS=1`, `torch.set_num_threads(1)` und **entfernt
alle `POKERB_*`-Env-Variablen** (`golden_set.py:20-24`) — der Gate-Kanal ist flag-frei.

**Kosten.** `sek_je_deck` steht in jeder Ausgabedatei; kein Referenzwert im Repo festgeschrieben.

**Mess-Status.** Als Werkzeug bestanden: im Gate G2a war `r8` vs `basis` **pre == post IDENTISCH** und die
Golden-A/A ueber 40 Decks hatte **nonzero 0** (`data/runs/v10/golden_r10_AA_v2.json`,
`golden_r8_vs_basis_post_g2a.json`, zitiert in `docs/V10_GATES_REPORT.md` Gate G2a).

**Allein benutzbar?** Ja, wenn dein Repo einen gepaarten Deck-Runner hat. Das Werkzeug ist 60 Zeilen und der Nutzen
liegt in der Regel, nicht im Code.

**Fallstricke.** `--vergleich` prueft `edges`, `a`, `b` und `seed` — aber NICHT, ob dazwischen die Deck-Bank
gewechselt hat oder ein anderer Code-Stand lief. Zwei "identische" Laeufe mit unterschiedlicher Deck-Anzahl
vergleichen stumm nur das Praefix (`zip`).

---

### G3-Abnahmewerkzeug: K1-Orakel — `research/k1_oracle.py` + `research/g3_k1_gate.py` + `research/g3_k1_census.py`
**Zweck.** Misst, wie weit die K1-Range von der tatsaechlich ausgefuehrten Politik abweicht (TV-Distanz), indem der
Stack an jedem Hero-Knoten mit AUSGETAUSCHTEN Hole-Karten ueber S Seeds befragt wird; `g3_k1_gate.py` ist der
stratifizierte Gate-Lauf darum, `g3_k1_census.py` der Vorab-Zensus der Guard-Haeufigkeiten.

**Schnittstelle.** CLI-getrieben:
`python -m research.k1_oracle --n 6 --seeds 8 --workers 4` (Pilot) bzw.
`python -u -m research.g3_k1_gate --zensus-n 300 --n 64 --je-klasse 16 --seeds 12 --workers 8 --zeitbudget-s 4200`.
`g3_k1_gate.waehle(vgs, n, je_klasse, klassen)` implementiert die Stratifizierung (erste `je_klasse` Vorgeschichten
je Guard-Klasse, dann mit `keine` auffuellen).

**Eingabe/Ausgabe.** Rein: Gym-Decks im Self-Play des Stacks; die Engine-States vor jeder Hero-Entscheidung werden
MITGESCHNITTEN (kein Replay). Raus: `data/runs/v10/k1_oracle_<ts>.json` bzw. `g3_k1_gate_<ts>.json` mit
`tv_k1_vs_orakel` (mittel/p95/max), `tv_k1_korrigiert_untere_schranke`, dem Rauschboden, den Kennzahlen je
Guard-Klasse, der Stichproben-Pruefung und `urteil_roh`/`urteil_budget`.

**Abhaengigkeiten.** `pargate._baue_fabrik`, `pokerbot.strategy.hero_range`, `duplicate.gen_decks`,
`multiprocessing` (spawn). Der Kanal `gtow` (Live) ist als Schalter vorgesehen, aber **nicht verdrahtet** — der
Aufruf endet mit `SystemExit` und klarer Meldung.

**Zustand.** Prozess-Pool; Ergebnisse je Vorgeschichte, Zeitbudget bricht kontrolliert ab und weist die Reduktion aus.

**Kosten.** GEMESSEN (n=6, 14 Knoten, 12 Worker): **S=8 -> Rauschboden 0,122 | S=32 -> 0,050 (600 s) |
S=64 -> 0,033 (1124 s)**, also ≈ 1/√S; 64 Vorgeschichten bei S=64 ≈ 3,3 h; ein Floor ≤ 0,010 haette S ≈ 3000
verlangt (Modul-Docstring `k1_oracle.py`, Reports `data/runs/v10/k1_oracle_20260907_18*/19*.json`).
Der Gate-Lauf fuhr mit S=12 (Floor 0,095, 55 min).

**Mess-Status.** Werkzeug funktionsfaehig, Urteil **VERFEHLT** (siehe K1 oben). Zwei Werkzeug-Befunde sind
uebertragbar und im Code dokumentiert: (1) ein GETEILTER Seed ueber alle Combos macht die geschaetzte
Wahrscheinlichkeit zu einer Treppenfunktion mit S gemeinsamen Schwellen statt zu einer empirischen Verteilung —
Fix: `seed_eff = keyed_hash(seed, Knoten-Adresse, combo)`; (2) reines MC hatte bei S=8 einen Rauschboden von 0,20 =
so gross wie das gemessene Signal — Fix: das erste `random()` des Bots wird auf den Gitterpunkt (k+½)/S
stratifiziert. Das Budget-Urteil wird nur vergeben, wenn der Rauschboden ≤ halbes Mittel-Budget ist, sonst lautet es
`orakel_zu_grob` bzw. `unterpowert`.

**Allein benutzbar?** Nein (haengt an `pargate` + K1). Die zwei Werkzeug-Befunde oben sind das Uebertragbare.

**Fallstricke.** Das Gesamt-Mittel des Gate-Laufs ist ein STRATIFIZIERTES Mittel (Guard-Faelle
ueberrepraesentiert) — es ist konservativ nach oben und darf nicht als natuerliche Rate zitiert werden. Die
Klassen-Kennzahlen sind je Klasse unverzerrt.

---

### G2-Latenzmessung — `research/v10_latenz.py`
**Zweck.** Misst die Wandzeit von `decide()` beider Arme auf identischen, echten River-Zustaenden in je einem
frischen Subprozess mit Live-Env — und liest den K2-Trace mit.

**Schnittstelle.** CLI: `--bau` (Zustandsliste erzeugen), `--probe N` (N Entscheidungen je Arm + Hochrechnung),
`--messe --n 150 --plan-min 50` (Vollmessung), `--bericht` (nur Auswertung vorhandener Roh-JSONL), `--tag`.

**Eingabe/Ausgabe.** Rein: `data/runs/v10/k3_roots_entwicklung.jsonl`; je Hero-River-Entscheidung wird der Zustand
VOR der Aktion mit `policy_oracle.zustand_nach_pfad` rekonstruiert und auf Hero=Sitz 0 gespiegelt. Raus:
`G2_latenz*.json` + `.md` + Roh-JSONL je Arm + der K2-Trace des Kandidaten. Geschichtet nach Pot-Klasse
(< 1500 / ≥ 1500), Position (IP/OOP) und Facing (check/bet); Kaltstart wird getrennt ausgewiesen.

**Abhaengigkeiten.** `research.k3_roots`, `research.policy_oracle`, `pokerbot.benchmark.gtowizard.PokerBotAgent`
(direkt gebaut, damit Fingerprint + K4-Gatter mitlaufen), `subprocess`.

**Zustand.** Zustandslos; ein frischer Subprozess je Arm.

**Kosten.** Die Vollmessung wurde mit **~15 min** veranschlagt und NICHT gestartet
(`docs/V10_GATES_REPORT.md`, Abschnitt 2, Zeile G2).

**Mess-Status.** Werkzeug lief; Gate **G2 VERFEHLT**. Probe n=10: Plan-Pot-p99 (= Maximum) 7,55 s, Gesamt-p99 v10
7,55 s > v5-H 5,54 s, 0 Aufrufe ≥ 30 s, K2-Trace Plan gespielt 1/10, `deadline` 7/10, `hand_not_in_range` 2/10
(`data/runs/v10/G2_latenz_probe10.json`, `gate_urteil.status = VERFEHLT_REDUZIERTE_STICHPROBE`). Nach dem
Mechanik-Fix (n=40): `deadline` 0/40, Plan gespielt 25/40, `offtree` 11/40, `hand_not_in_range` 4/40,
p50/p90/p99 = 3,04 / 8,50 / 10,15 s vs v5-H 2,10 / – / 8,20 s — **formal weiter verfehlt** (p99 ≥ 8 s und
v10 > v5-H); Treiber ist die K1-Rechnung, nicht der Solve (`docs/V10_GATES_REPORT.md`, Abschnitt 6).

**Allein benutzbar?** Nein. Uebertragbar ist die Bauform: gleiche Zustaende, frische Prozesse je Arm, Kaltstart
getrennt, Schichten vorher festgelegt.

**Fallstricke.** Die Messung ruft `PokerBotAgent._decide` direkt und sequentiell — der echte Harness spielt 5–8
Haende parallel. Der Queue-/Deadline-Effekt ist live also eher STAERKER als hier gemessen (ebd., Abschnitt 2).

---

### K5 — GTOW-Nachtfahrplan — `research/gtow_nacht_v10.py`
**Zweck.** Treiber fuer den Live-Benchmark: faehrt zwei Arme in einer VORAB per Muenze festgelegten Chunk-Sequenz,
mit Env-Hygiene, Ledger-Abgleich, Ereignis-Klassifikation und vorregistrierten Stopp-Regeln.

**Schnittstelle.** CLI: `--plan` (druckt Sequenz + Env, startet nichts), `--smoke N --arm B`, `--nacht 1`,
`--nacht 2`, `--fazit-gesamt`.

**Eingabe/Ausgabe.** Rein: die Arm-Definitionen (`A = PRINCE + r8_stack`, `B = PRINCE + r10_stack`, beide OHNE
RAISE_NARROW), die Muenze `data/runs/v10_muenze.json` (`BAAB_dann_ABBA`), ein API-Key. Raus: Manifest
`data/runs/v10/gtow_manifest_v10.json` (nach JEDEM Chunk geschrieben), Journal-Eintraege
`V10-GTOW-VORREGISTRIERUNG` / `-CHUNK` / `-NACHT-FAZIT` / `-GESAMT-FAZIT`, plus je Chunk ein K2-Trace-Pfad
(`POKERB_K2_TRACE`) und ein Ledger.

**Abhaengigkeiten.** `tools/gtow_run.py` (frischer Subprozess je Chunk, Timeout 10800 s, max 3 Retries),
`pokerbot.benchmark.gtow_ledger` (lazy), `clear_inprogress` (409-Waisen-Pflicht vor JEDEM Start und Retry),
`pokerbot.autogym.pargate` ueber `POKERB_AUSLESE_STACK`.

**Zustand.** Manifest-getrieben; jede Fahrt liest die bisherigen Kandidaten-Chunks als Vorgeschichte, damit die
Stopp-Zaehler ueber den GESAMTEN Live-Test laufen (Smoke + beide Naechte).

**Kosten.** 4 x 500 Haende je Nacht; die vorregistrierte Aussage rechnet mit SE ≈ 6,77 bb/100 fuer den GESAMTEN Test
(4 Blockpaare: 214·√(2/500)/√4), 9,57 je einzelner Nacht.

**Mess-Status.** UNGEMESSEN als Ergebnis — **die Staffel wurde fuer v10 nie gefahren** (Ship-Entscheid: nicht
GTOW-reif, `docs/V10_GATES_REPORT.md` Abschnitt 4; STATE.md: "kein Tag auslese-v10-rc, keine G6-Staffel"). Der
Treiber selbst ist getestet: **31/31 gruen** (`tests/test_gtow_nacht_v10.py`, Gate G1). Blockierend bleibt R6: der
Kanal fuer `illegal` (`legalisiert:<von>-><nach>` in `technische_events` + Fingerprint-Feld) existiert nicht —
grep 0 Treffer — deshalb endet jede Nacht per Konstruktion mit `kein_verdikt`.

**Allein benutzbar?** Nein (an die GTOW-API gebunden). Uebertragbar ist die Konstruktion: die Sequenz steht VORHER
fest und es gibt keinen Codepfad, der sie liest und ergebnisabhaengig anders schreibt; und: **eine 0 ohne Kanal ist
keine Messung** — fehlt der Ereignis-Kanal, wird das im Manifest als `kanal='fehlt'` gefuehrt, nicht als 0.

**Fallstricke.** Der Harness bricht bei jedem nicht-busy-HTTP-Fehler den GANZEN Chunk ab (busy = 409/502/503/504).
Deshalb wird JEDER Versuch ausgewertet und ueber Versuche summiert; ein `http_4xx` fuehrt NICHT zu blindem Retry
(zwei weitere 500er waeren verbrannte Hand-IDs).

---

### Verdrahtungspunkt — `r10_stack` / `r10_h0` in `pokerbot/autogym/pargate.py`
**Zweck.** Definiert, WIE der River-Plan in die Stack-Kette eingehaengt wird — kein eigenes Modul, aber die Stelle,
an der ein Fremder die Komposition liest.

**Schnittstelle.** `_wickle(name, basis, kanal="gym")` (`pargate.py:69`) und `_baue_fabrik(name, seed)`.
- `r10_stack` (`pargate.py:173-186`): `river_plan_guard(river_wert_bremse(r6_button(basis)), min_pot_chips=1500,
  iters=150, **_k2_kanal_kw(kanal))` — dieselbe Kette wie der Champion, aber die hand-abhaengige GPU-Chirurgie
  (`river_gpu_guard`) ist ERSETZT.
- `r10_h0` (`pargate.py:187-192`, User-Patch 2026-09-10): `river_plan_guard(r8_stack(basis), …)` — "H0-LITE": der
  Plan sitzt auf der VOLLSTAENDIGEN v5-Kette, ein Fallback landet damit nie unter dem Champion. Das ist die direkte
  Antwort auf Befund R4 (Katastrophen im nackten Fallback).
- `_k2_kanal_kw(kanal)` (`pargate.py:58-67`): `modus`, `trace_pfad` aus `POKERB_K2_TRACE`, und im Live-Kanal
  `deadline_s = K2_LIVE_DEADLINE_S = 12.0` (`pargate.py:53`).
- Konsum: `pokerbot.strategy.auslese.wickle_decide(pb, stack=None, kanal="live")` legt den Stack dict-erhaltend um
  `PokerBot.decide` und reicht `private_seed_quelle` an den K4-Fingerprint durch (`auslese.py:52-70`);
  `FINAL_STACK = "r8_stack"`, `RC_STACK = "r10_stack"` (`auslese.py:34-35`).

**Eingabe/Ausgabe.** Rein: ein Stack-Name + eine Basis-Fabrik. Raus: eine Fabrik `f(seat) -> d(st) -> (action, amount)`.

**Abhaengigkeiten.** HART auf die Guard-Sammlung in `pokerbot.autogym.improver` und `preflop_guards`.

**Zustand.** Der zurueckgegebene Wrapper haelt den K2-Zustand (Plan-Cache je Sitz).

**Kosten.** Siehe K2.

**Mess-Status.** `r10_stack`: siehe K2 (Gym-Spiegel NEUTRAL, +11,68 ± 10,85 bb/100, n=1968). **`r10_h0`:
UNGEMESSEN** — es existiert bisher nur ein Diagnoselauf ueber die Kaggle-Bruecke
(`data/runs/kaggle_v10h0_vs_champion_2026-09-10.log`); der Commit `d22d400` haelt fest: A/A exakt 0, und nach dem
Fix einer fehlenden `deal`-Marke im Kaggle-Adapter wurde in der Stichprobe **1 Plan gespielt, 1 offtree**. Das ist
eine Mechanik-Kontrolle, kein Verdikt.

**Fallstricke.** `kanal="live"` schaltet Deadline UND `os.urandom`-Seed ein — damit ist der Lauf nicht mehr
deterministisch. Jedes gepaarte Gate (A/A muss EXAKT 0 sein) MUSS `kanal="gym"` fahren.

---

### Gate-Laeufer (Sammel-Eintrag) — `research/g1_gate_runner.py`, `g4_auswertung.py`, `g5_spiegel_auswertung.py`, `g5_deck_replay.py`, `g5_divergenz_auswertung.py`
**Zweck.** Einmal-Skripte, die je ein Gate ausfuehren bzw. dessen Rohdaten zu einem Urteil verdichten (Test-Sammellauf,
Bootstrap-Auswertung des Pruefstands, Spiegel-Statistik, deterministischer Replay einzelner Divergenz-Decks,
Divergenz-Obduktion).

**Schnittstelle.** Jeweils CLI mit `--haupt/--sens/--name`-artigen Argumenten; die exakten Kommandos stehen in der
Quellenspalte von `docs/V10_GATES_REPORT.md`, Abschnitt 1.

**Eingabe/Ausgabe.** Rein: die Roh-Artefakte unter `data/runs/v10/` bzw. `data/runs/<ts>_pargate_*/`. Raus: die
zitierten Berichte (`G1_tests.txt`, `G4_holdout.{json,md}`, `G5_BERICHT.json`, `g5_divergenz_replay.log`,
`g5_katastrophen_trace.jsonl`).

**Abhaengigkeiten.** Auf die jeweiligen Mess-Module und die Artefakt-Pfade; kein Strategie-Code.

**Zustand.** Zustandslos.

**Kosten.** Nicht gemessen (Auswertung, Sekunden bis Minuten; `g5_deck_replay` spielt Decks nach).

**Mess-Status.** UNGEMESSEN (Werkzeuge). Bekannte Luecke: der G1-Runner hat den Block
`test_river_br_pruefstand` NICHT geschrieben, das Log endet nach `test_river_plan` und `G1_summary.json` fehlt —
die Evidenz fuer diesen Block stammt aus einem separaten Lauf derselben Code-Version
(`docs/V10_GATES_REPORT.md`, Gate G1 "Luecke").

**Allein benutzbar?** Nein — reine Projekt-Skripte.

**Fallstricke.** Sie setzen voraus, dass die Artefakte aus GENAU einem Code-Stand kommen. Im v10-Lauf liefen G1,
G2a, G3 und G4 teilweise PARALLEL (entgegen der Hausregel "eine Worker-Flotte zur Zeit") — der Latenz-Anhang von
`test_river_plan` gilt deshalb als kontaminiert und wird nicht zitiert (ebd., Abschnitt 2, letzte Zeile).

---

### Die verfehlten Gates — Zusammenfassung fuer einen Fremden

| Gate | Was geprueft wurde | Urteil | Warum |
|---|---|---|---|
| G1 Tests/Invarianten | 13 Test-/Smoke-Bloecke | GRUEN (zusammengesetzt) | alle exit 0; ein Block fehlt im Hauptlog und stammt aus einem zweiten Lauf derselben Code-Version; `pytest` war nicht installiert, gefahren wurde der Modul-Runner |
| G2a A/A + Golden | Determinismus nach Code-Aenderung | BESTANDEN | 576 Decks EXAKT 0, Golden pre == post |
| **G2 Latenz** | p99 < 8 s, v10 ≤ v5-H, kein Aufruf ≥ 30 s | **VERFEHLT** | n=10-Probe: 7,55 s > 5,54 s; nach Mechanik-Fix n=40: p99 10,15 s vs 8,20 s. Treiber ist die K1-CPU-MC-Rechnung je Combo, nicht der GPU-Solve. Vollmessung nie gestartet |
| **G3 K1-Abnahme** | TV(K1, decide-Orakel) ≤ 0,02 / 0,05 / 0,10 | **VERFEHLT — der Blocker** | untere Schranke nach Rauschabzug 0,1446 / 0,620 / 0,819. Strukturelle Ursache: das Likelihood-Backend kennt nur bet-vs-check, die Basis waehlt Sizes hand-abhaengig; zusaetzlich ist die Annahme "button_disziplin laesst den Prior unveraendert" messbar falsch. Karte: "G3 verfehlt -> K2 NICHT frei" |
| **G4 Holdout-Pruefstand** | ≥ 20 Roots, Arm A LIVE | **UNVOLLSTAENDIG** | 11 Roots im GYM-Kanal (Zeitbudget; Live-Pilot UNSUPPORTED). Richtung eindeutig (11/11 weniger ausbeutbar), Betrag −113 bb/100 NICHT auf Live uebertragbar |
| G5 Spiegel + Export | keine Katastrophe | BESTANDEN (mit Befund) | +11,68 ± 10,85 bb/100 NEUTRAL; je 1 Deck ≥ 150 bb in beide Richtungen. **Obduktion: alle drei Decks ≤ −100 bb entstanden im FALLBACK auf die nackte Basis, nie im Plan** — die drei reinen Plan-Decks waren alle positiv |

**Entscheid (bindend, `docs/V10_GATES_REPORT.md` Abschnitt 4): v10 (`r10_stack`) ist NICHT GTOW-reif; der Stand
bleibt `auslese-v5` (`r8_stack`).** Was ein Re-Release braeuchte: (1) ein size-bewusstes Likelihood-Backend fuer K1
plus Klaerung von `button_disziplin` und des Support-Lecks; (2) Fallback-Ziel = volle v5-Kette statt nackter Basis
(genau das ist der `r10_h0`-Patch vom 2026-09-10, ungemessen) und eine Off-Tree-Behandlung der Villain-Sizes
(27 % live, 42 % in den grossen Gym-Divergenz-Decks); (3) den Legalisierungs-Kanal, sonst endet jede Live-Nacht per
Konstruktion mit `kein_verdikt`; (4) G2-Vollmessung und G4 bis n ≥ 20 im Live-Kanal. Jede Aenderung = neuer Hash =
alle Gates neu.

---

## Mess-Infrastruktur

Dieses Subsystem beantwortet genau eine Frage: **ist Bot-Version B besser als Bot-Version A — und zwar so, dass die Antwort nicht Kartenglueck ist?** Kern ist Duplicate-Poker (dasselbe Deck zweimal mit vertauschten Sitzen), darum herum liegen ein Parallel-Treiber ueber alle CPU-Kerne, eine Entscheidungsregel mit vorregistrierten Schwellen, ein Mathematik-Orakel als zweites, unabhaengiges Instrument und eine Run-Ablage, die jedes Urteil an Commit + Konfiguration bindet.

Du brauchst es, sobald du mehr als eine Bot-Version hast. Ohne gepaarte Messung ist eine bb/100-Zahl aus wenigen hundert Haenden reines Rauschen — in diesem Repo wurden mehrfach plausible Fixes nach naiver Messung eingebaut und spaeter widerlegt. Wenn du nur EINEN Bot baust und ihn nie veraenderst, kannst du dieses Kapitel ueberspringen; sobald du iterierst, ist es der teuerste Teil, den du selbst nachbauen muesstest.

Alles hier ist reine CPU-Arbeit, laeuft lokal, kostet nichts ausser Zeit und haengt nur an `multiprocessing`, der eigenen Engine und der eigenen Strategie-Fabrik.

---

### Die bindenden Regeln (uebernehmbar, unabhaengig vom Code)

Diese vier Regeln sind im Repo nicht Konvention, sondern Abnahmebedingung. Sie sind billiger nachzubauen als der Code und retten mehr.

**1. A/A-Nulltest vor jeder Messreihe.** Bevor Kandidat gegen Amtierenden gemessen wird, laeuft derselbe Arm gegen sich selbst. Ergebnis muss **exakt 0** sein — jede per-Deck-Differenz 0, nicht "nahe 0". Ist es das nicht, gibt es eine unkontrollierte Rausch-Quelle (ungeseedete Monte-Carlo-Equity, Set-Iteration, RNG-Strom ueber Haende hinweg, Thread-Zahl) und die ganze Messreihe ist wertlos. Beleg, dass das kein Ritual ist: `data/runs/INDEX.jsonl` zeigt am 2026-09-07 zwei A/A-Laeufe desselben Arms `r10_stack`, 576 Decks — der erste `-9.4 ± 10.92` (Run `20260907_213225_pargate_r10_stack`, Ursache: `hand_id` wurde je Spiegelhaelfte verschieden vergeben), der dritte nach dem Fix `bb100 0.0, se 0.0, nonzero 0/576` (`data/runs/20260907_220348_pargate_r10_stack/result.json`). Ohne den A/A-Test waere die Differenz als Effekt gebucht worden.

**2. Drei-Laeufe-Regel vor jeder Taufe.** Ein Kandidat bekommt erst einen Namen/Tag, wenn er auf **drei frischen Deck-Baenken** (verschiedene `deck_seed0`) repliziert. Grund: im Repo wurden zweimal verfruehte Taufen nach einem einzelnen positiven Lauf verhindert (`CLAUDE.md`: „kein Name ohne 3 Laeufe"). Gemessenes Beispiel dafuer, warum: `tag_flatfix` vs `tag`, drei Laeufe a 2992 Decks → `+17,7±6,4 (ANWENDEN)` / `+11,4±6,9 (NEUTRAL)` / `+19,2±7,0 (ANWENDEN)` (Journal `FLATFIX-6MAX-VERDIKT`, 2026-09-09). Ein Lauf allein haette je nach Zufall „NEUTRAL" oder „ANWENDEN" gesagt.

**3. Kanal-Vokabular.** Ein Messkanal darf nur Worte benutzen, die zu seiner Aussagekraft passen. Im Repo:
- Self-Play-Spiegel gegen den Amtierenden (`pargate`, `pargate6`) → `ANWENDEN` / `NEUTRAL` / `VERWERFEN`. Das ist Ship-Evidenz.
- Messung gegen einen FREMDEN Referenzgegner (`envgate` vs `GTOBaseline`) → `KANAL_POSITIV` / `KANAL_NEUTRAL` / `KANAL_NEGATIV` (Code: `envgate.py:118`). Das ist ausdruecklich **keine** Ship-Evidenz, nur Vorzeichen + Spew-Kanarienvogel.
- Externer Anker (kommerzieller Solver/Leaderboard) → das ist die einzige absolute Wahrheit, aber teuer und knapp.
Der Grund fuer die Trennung ist gemessen: der Arm `prince` gewinnt im Spiegel und verliert im `envgate`-Kanal roh −68 bb/100, weil dort gegen einen ausbeutbaren Gegner mit abgeschaltetem Exploit gespielt wird (`envgate.py:39-41`). Wer beide Kanaele mit demselben Wort beschriftet, shippt Artefakte.

**4. Entscheidung nur ueber die eine vorregistrierte Regel, nie nach Sicht der Zahlen.** Die Regel steht in `stats.verdikt` (unten im Detail) und wird nicht pro Fall justiert. Zusatzregeln, die aus Schaden gelernt wurden: eine Worker-Flotte zur Zeit (RAM); leiser Kanal (Kandidat vs Kandidat) schlaegt lauten (Kandidat vs Basis); Kanalbreite VOR dem Bau messen (wenn nur 1 % der Decks ueberhaupt divergieren, braucht man andere Statistik als bei 40 %).

---

### Duplicate-Gate (Kern) — `pokerbot/benchmark/duplicate.py`
**Zweck.** Spielt jedes feste Deck zweimal mit vertauschten Sitzen, sodass sich das Kartenglueck exakt herauskuerzt und nur die Skill-Differenz uebrig bleibt.

**Schnittstelle.**
- `gen_decks(n, seed=0) -> list[(hole0, hole1, board5)]` — n feste Deals, je aus einer frischen Mischung ohne Zuruecklegen.
- `duplicate_ab(make_a, make_b, decks, start=20000, sb=50, bb=100, return_edges=False, hand_id_basis=0) -> (bb100, se[, edges])` — A's kartenbereinigte Edge ueber B in bb/100 plus Standardfehler; `return_edges=True` liefert zusaetzlich die per-Deck-Chip-Differenzen (Voraussetzung fuer gepaarte Deltas ueber mehrere Konfigurationen).
- `naive_ab(make_a, make_b, hands, ...) -> (bb100, se)` — dieselbe Messung OHNE Varianzreduktion, existiert nur fuer den Kontrast-Beweis.
- `gto(seed=1, **params)` / `pokerbot(exploit=False, seed=1, value_raise_eq=0.72, **flags)` — die zwei mitgelieferten Strategie-Fabriken.
- `_setup_fixed(g, h0, h1, board5, button, start)` — setzt feste Karten in eine laufende `HeadsUpGame` (intern, aber von `gym_hu` und `orakel_duell` mitbenutzt).

**Eingabe/Ausgabe.** Eingabe sind **Fabriken**, nicht Bots: `make_strat(seat) -> decide(state) -> (action, amount)`. `state` ist der Engine-Zustands-Dict mit `to_act`, `street`, `pot`, `current_bet`, `board`, `players[i]{hole, stack, committed_street, all_in}`; `duplicate_ab` injiziert zusaetzlich `state["hand_id"]` (siehe Fallstricke). Ausgabe: `bb100 = mean(edges)/2/bb*100` (2 Haende je Deck), `se` analog, `edges` als Chip-Liste.

**Abhaengigkeiten.** `pokerbot.engine.cards`, `pokerbot.engine.game.HeadsUpGame` (hart — die Engine ist die Legalitaets-Wahrheit), `pokerbot.strategy.gto_baseline.GTOBaseline` (nur fuer die Fabrik `gto()`, ersetzbar). Das Prinzip selbst ist engine-agnostisch: du brauchst nur eine Engine, in die man Karten und Button hart hineinsetzen kann.

**Zustand.** Zustandslos ueber Laeufe; INNERHALB eines Laufes wird EINE `HeadsUpGame`-Instanz wiederverwendet und je Deck neu aufgesetzt. Die Fabriken werden je Spiegelhaelfte frisch gerufen — ein Bot mit Gegner-Gedaechtnis wuerde die Paarung brechen (genau dafuer gibt es `exploit_jagd`).

**Kosten.** Reine CPU. Ueber `pargate` gemessen: CPU-only-Arme ~2.500 Decks/min bei 12 Workern (`data/runs/INDEX.jsonl`, Run `20260830_202416_pargate_r7_river`: 30.000 Decks in 723,2 s = 2.489 Decks/min). Speicher vernachlaessigbar (eine Chip-Zahl je Deck).

**Mess-Status.** GEMESSEN POSITIV als Instrument: A/A ueber 576 Decks ergibt `bb100 0.0, se 0.0, nonzero 0` (`data/runs/20260907_220348_pargate_r10_stack/result.json`) — der Null-Kanal ist exakt, nicht nur klein. Die im Docstring behauptete Varianz-Kollaps-Spanne „10-50x" ist eine **Design-Behauptung**; den Faktor misst `python -m pokerbot.benchmark.duplicate` selbst aus, eine festgeschriebene Zahl dafuer liegt im Repo nicht vor.

**Allein benutzbar?** Ja, das ist der am leichtesten herausloesbare Baustein des ganzen Projekts. Minimal noetig: eine HU-Engine mit setzbaren Karten + zwei Strategie-Fabriken. ~70 Zeilen.

**Fallstricke.** Der Default-Stack ist `start=20000` bei `bb=100`, also **200 bb tief** — nicht 100 bb. `pargate` erbt diesen Default, `pargate6` spielt dagegen 100 bb (`START_STACK=10000`). Wer Zahlen aus beiden Kanaelen vergleicht, vergleicht zwei verschiedene Spiele.

---

### Entscheidungs-Statistik — `pokerbot/autogym/stats.py`
**Zweck.** Wandelt eine Liste von per-Deck-Chip-Differenzen in ein Urteil um — nach einer Regel, die VOR der Messung festgelegt ist.

**Schnittstelle.**
- `robust_stats(edges, bb=100, trim=0.05, haende_je_deck=2) -> dict` — Lage/Streuung roh und getrimmt, plus Sparse-Diagnostik.
- `bootstrap_ci(edges, b=4000, seed=17, bb=100, haende_je_deck=2) -> dict` — Perzentil-Bootstrap + Vorzeichen-Flip-Permutationstest, beides nur ueber die Nicht-Null-Edges.
- `verdikt(st) -> "ANWENDEN" | "NEUTRAL" | "VERWERFEN"` — die Entscheidungsregel.

**Eingabe/Ausgabe.** Rein: `edges` = Chip-Differenzen je Deck (Kandidat minus Amtierender, summiert ueber alle Spiegelhaelften/Rotationen des Decks). Raus (tragende Schluessel): `n_decks`, `bb100` (rohes Mittel, skaliert `1/haende_je_deck/bb*100`), `se`, `bb100_trim`, `median_bb100`, `nonzero`, `nonzero_anteil`, `nz_pos`, `vorzeichen_z`, `nz_median_chips`; aus dem Bootstrap `ci95_lo`, `ci95_hi`, `perm_p`, `boot_b`.

**Die Regel im Wortlaut (`stats.py:93-110`).**
1. Basis ist das **rohe** Mittel ± 2·SE.
2. `ANWENDEN`, wenn `bb100 − 2·se > 0`.
3. `VERWERFEN`, wenn `bb100 + 2·se < −1.0` — beachte die **Asymmetrie**: die Untergrenze ist −1 bb/100, nicht 0. Das ist ein bewusstes Toleranzband („Nichtverschlechterung"), damit ein neutraler Kandidat nicht bei jedem Rauschen verworfen wird.
4. Sonst `NEUTRAL`.
5. **Sparse-Klausel:** ist `nonzero_anteil < SPARSE_SCHWELLE` (0.02, `stats.py:90`), traegt das Bootstrap-Intervall das Verdikt: `ANWENDEN` nur zusaetzlich bei `ci95_lo > 0` UND `perm_p < 0.025`; `VERWERFEN` nur zusaetzlich bei `ci95_hi < −1.0`. Sonst `NEUTRAL`.

Warum genau so — beides ist Schadensgeschichte: Der 5 %-Trim war urspruenglich die Entscheidungsstatistik (fettrandige per-Deck-Edges). Nach dem Spot-RNG-Seeding-Fix (A/A exakt 0) verschwand die Lauf-Heterogenitaet, und der Trim wurde schaedlich: bei duennen Kanaelen (z. B. 1 % divergente Decks) entfernt eine 5 %-Trimmung exakt die Signal-Decks (`stats.py:19-31`, Estimator v2). Der Trim bleibt als Diagnosefeld drin, entscheidet aber nicht mehr. Die Sparse-Klausel kam danach dazu, weil die CLT-2SE bei ~55 effektiven Divergenz-Decks aus 12k unterdeckte (`stats.py:59-66`).

**Abhaengigkeiten.** Keine ausser der Standardbibliothek (`random`). Vollstaendig herausloesbar.

**Zustand.** Zustandslos. Der Bootstrap ist deterministisch (fester `seed=17`).

**Kosten.** `bootstrap_ci` kostet `b*m` Ziehungen mit m = Zahl der Nicht-Null-Edges (nicht `b*n`) — bei 4000 Wiederholungen und wenigen tausend Nicht-Null-Decks Bruchteile einer Sekunde.

**Mess-Status.** UNGEMESSEN als eigenstaendiger Hebel — es ist eine Entscheidungsregel, kein Bot-Feature, und hat keine bb/100. Ihre Kalibrierung ist indirekt belegt: A/A liefert `verdict NEUTRAL` bei `bb100 0.0` (a. a. O.), und der Estimator-Wechsel v1→v2 ist im Docstring mit dem Anlass (turn_wert 8,4 % / raise_narrow 1 % divergente Decks) dokumentiert.

**Allein benutzbar?** Ja, sofort — `edges`-Liste rein, Verdikt raus. Das ist der billigste Import aus diesem Repo.

**Fallstricke.** `bootstrap_ci` nutzt `random.Random.binomialvariate`, das es **erst ab Python 3.12** gibt. Auf 3.11 stirbt der Aufruf mit `AttributeError` — und zwar erst am Ende eines langen Laufs, nachdem die Rechenzeit schon verbrannt ist.

---

### HU-Parallel-Gate — `pokerbot/autogym/pargate.py`
**Zweck.** Faehrt `duplicate_ab` ueber alle CPU-Kerne auf disjunkten Deck-Bloecken und liefert ein fertiges Verdikt samt Run-Ablage.

**Schnittstelle.**
- `par_gate(kandidat, n_decks, workers, seed=1, deck_seed0=1000, incumbent="basis") -> dict` — das Gate; Rueckgabe enthaelt alle `robust_stats`/`bootstrap_ci`-Felder plus `verdict` und `edges`.
- `_wickle(name, basis, kanal="gym")` — **die eine Quelle der Stack-Komposition**: uebersetzt einen Arm-Namen (`"r8_stack"`, `"turn_wert"`, …) in die geschachtelten Guard-Wrapper um eine fertige Strategie-Fabrik. Auch die Export-Kanaele importieren diese Funktion, damit nie eine divergierende Kopie gegradet wird.
- `_baue_fabrik(name, seed)` — `_wickle` um die `duplicate.pokerbot(exploit=True)`-Basis.
- CLI: `python -m pokerbot.autogym.pargate --kandidat <name> --incumbent <name> --decks N --workers W --seed S --deck-seed0 B`.

**Eingabe/Ausgabe.** Eingabe sind **Namen** aus der Konstante `KANDIDATEN` (`pargate.py:18-52`), nicht Objekte — bewusst, weil Closures unter Windows-`spawn` nicht picklebar sind. Ausgabe: `result.json` + `edges.json` im Run-Ordner, eine Zeile in `data/runs/INDEX.jsonl`, Verdikt auf stdout. Zwischenstaende: jeder fertige Job-Block wird als `data/_pargate_blocks/<kand>__vs__<inc>__s<seed>__b<bank>__c<chunk>/jobNNN.json` abgelegt.

**Abhaengigkeiten.** `duplicate.py` (hart), `stats.py` (hart), `runs.py` (Ablage, ersetzbar), `improver.py` + `preflop_guards.py` + `river_plan.py` + `turn_gpu.py` (nur fuer die konkreten Arm-Namen — die Mechanik selbst kennt keine Strategie).

**Zustand.** Je Lauf. Worker-Prozesse sind hygienisiert: alle geerbten `POKERB_*`-Env-Variablen werden geloescht, `OPENBLAS/OMP/MKL_NUM_THREADS=1` gesetzt, `torch.set_num_threads(1)` (`pargate.py:200-224`). **Der Block-Cache ist persistenter Zustand und muss bei Code-Aenderung verworfen werden** (siehe Fallstricke).

**Kosten.** Gemessen (`data/runs/INDEX.jsonl`): CPU-only-Arme 30.000 Decks in ~700 s bei 12 Workern (~2.500 Decks/min); Arme mit GPU-River-Solver 115–390 Decks/min (z. B. `r8_stack` vs `r6_button`, 30.000 Decks, 6 Worker, 7.725 s = 233 Decks/min). Fuer GPU-Arme steht im Code die Auflage `--workers <= 6` (`pargate.py:36`).

**Mess-Status.** GEMESSEN POSITIV als Instrument: A/A `r10_stack` vs `r10_stack`, 576 Decks, `bb100 0.0 / se 0.0 / nonzero 0`, 212,9 s (`data/runs/20260907_220348_pargate_r10_stack/result.json`). Als Produzent von Bot-Verdikten hat es u. a. geliefert: `sel_guard` +4,7 ± 2,06 (99.000 Decks, ANWENDEN) und `mdf_guard` −3,26 ± 2,19 (99.000 Decks, NEUTRAL) — beide `data/runs/STAND.md`.

**Allein benutzbar?** Nur zusammen mit `duplicate.py` + `stats.py`. Die Arm-Namensliste ist projektspezifisch und muss durch deine eigene ersetzt werden; das Geruest (Job-Split, Env-Hygiene, geordnete Block-Zusammensetzung, Fortsetzbarkeit) ist uebertragbar.

**Fallstricke.** Der Block-Cache ist **nicht** nach Code-Version geschluesselt — nur nach Arm-Namen, Seeds und Blockgroesse. Aenderst du den Strategie-Code und startest mit denselben Parametern, mischt der Lauf still alte und neue Bloecke. Das Repo loest das per Konvention („je Code-Stand eine frische Deck-Bank", `deck_seed0` 1080000/1090000/1100000/1110000 sind verbraucht) und im Ernstfall per Hand: unter `data/_pargate_blocks/` liegt ein Ordner `_STALE_hand_id_2k_half__r10_stack__vs__r10_stack__s1__b1080000__c12` — eine manuell in Quarantaene umbenannte Bank. Zweiter Fallstrick: `chunk = n_decks // (workers*4)`, die tatsaechliche Deckzahl wird also abgerundet (600 angefordert bei 12 Workern → 576 gespielt).

---

### 6-max-Parallel-Gate — `pokerbot/autogym/pargate6.py`
**Zweck.** Uebertraegt das Duplicate-Prinzip auf einen Mehrspieler-Tisch: ein Deck wird n-mal gespielt, der Held rotiert ueber alle Sitze.

**Schnittstelle.**
- `par_gate6(kandidat, incumbent, n_decks, workers, seed=1, deck_seed0=5000, n_seats=6, liga=LIGA, fabrik_spec="pokerbot.autogym.pargate6:held_fabrik", env_fn=arm_env) -> dict`
- `gen_decks6(n, seed, n_seats=6) -> list[(holes[n_seats], board[5])]`
- `spiele_block(held, decks, deck_id0, n_seats, liga, seed) -> {"chips": [...], "prince_decisions", "kern_fallbacks", "illegal_fallbacks", "fingerprint"}`
- `held_fabrik(name)` — die Standard-Helden; **austauschbar** ueber `fabrik_spec` als String `"modul:funktion"` (so nutzt `exploit_gate` dieselbe Arena mit eigenen Helden).
- `arm_env(name) -> dict` — die Env-Flags, die ein Arm im frischen Prozess bekommt; ebenfalls ueber `env_fn` austauschbar.

**Eingabe/Ausgabe.** Rein: Arm-Namen + Deck-Parameter. Der **Helden-Kontrakt** ist das Wichtige, wenn du eigene Bots einhaengst: das Objekt braucht `decide(obs) -> {"action", "amount"}`, `new_hand(seats)`, `observe(actor, street, action, to_call, preflop_raises)`; optional `setze_sitz(seat)` (sonst wird `.seat` gesetzt), `bind_table(table)`, `.hand_id`, `.fingerprint`, `.rng`. Raus: dieselben Statistik-Felder wie `pargate`, plus `bb100_kandidat` / `bb100_incumbent` (absolute Werte je Arm gegen die Liga), `aa_exakt_null`, `zaehler` (Fallback-Zaehler je Arm), `fingerprints`.

**Aufbau der Rotation (`pargate6.py:134-165`).** Button fest auf Sitz 0; in Rotation `r` sitzt der Held auf Sitz `r`, Sitz `s` traegt das Liga-Profil `LIGA[(s − r − 1) % 6]`. Damit sieht der Held jede Position genau einmal, und jedes Hole-Paar wird einmal vom Helden und einmal von jedem Villain-Profil gespielt. Villain-RNGs sind je `(Deck, Rotation, Sitz)` geseedet; die Villain-Objekte leben ueber den ganzen Job-Block, damit ihre Gegnermodelle Beobachtungen sammeln koennen — **gleiche `--workers` = gleiche Lernfenster**, sonst sind zwei Laeufe nicht vergleichbar.

**Abhaengigkeiten.** `pokerbot.engine.table.Table` (hart — N-Spieler-Engine mit Side-Pots), `pokerbot.arena.sixmax` (die Liga; ersetzbar durch beliebige Gegner), `stats.py`, `duplicate.HAND_ID_STRIDE_JE_DECKSEED`, `runs.py`.

**Zustand.** Je Job-Block. Jeder Job laeuft in einem **frischen Prozess** (`mp.Pool(workers, maxtasksperchild=1)`), weil die Arm-Env-Flags zur Import-Zeit gelesen werden und sich sonst ueber wiederverwendete Pool-Prozesse vermischen wuerden. Kein Block-Cache (anders als `pargate`) — ein Abbruch verliert alles.

**Kosten.** Gemessen: `tag_flatfix` vs `tag`, 2992 Decks × 6 Rotationen × 2 Arme in **90,4 s** bei 8 Workern (`data/runs/20260909_214905_pargate6_tag_flatfix/result.json`). Mit dem schweren Hybrid-Helden: dieselbe Deckzahl in 1.038–1.671 s (`20260909_190405_pargate6_hybrid_r8`, `20260909_183613_pargate6_hybrid_r10`).

**Mess-Status.** GEMESSEN POSITIV als Instrument (A/A `tag` vs `tag`, 288 Decks, EXAKT 0 — Journal `VERDRAHTUNG-6MAX-VERDIKT`, 2026-09-09) und als Produzent scharfer Verdikte: es hat den 6-max-„Prince-Takeover" refutiert (hybrid −23,56 ± 9,02 / hybrid_r8 −21,73 ± 9,01 / hybrid_r10 −26,61 ± 8,93 vs `tag`, je 2992 Decks, alle VERWERFEN) und den Flat-Fix bestaetigt (+17,7/+11,4/+19,2 ueber 3 Laeufe).

**Allein benutzbar?** Ja, sofern deine Engine `obs_for(seat)` / `legal_actions()` / `act()` anbietet und du Karten hart setzen kannst. `fabrik_spec` + `env_fn` sind ausdruecklich als Fremd-Einhaengepunkte gebaut.

**Fallstricke.** `aa_exakt_null` im Ergebnis ist **nur dann aussagekraeftig, wenn `kandidat == incumbent`** — bei verschiedenen Armen steht dort immer `False` (`pargate6.py:227`). Wer das Feld als „Messung war sauber"-Ampel liest, liest Unsinn. Der A/A muss als eigener Lauf gefahren werden.

---

### Env-Paar-Gate — `pokerbot/autogym/envgate.py`
**Zweck.** Misst Flags, die zur **Import-Zeit** gelesen werden und deshalb prozess-global sind — im normalen Gate wuerden sie beide Arme gleichzeitig faerben.

**Schnittstelle.** Im Wesentlichen ein CLI: `python -m pokerbot.autogym.envgate --decks 12000 --arme prince,k3_deception --referenz-wrapper sel_m15`. Intern: `_arm_lauf(...)` (Kind-Modus, ueber `--arm-lauf` aktiviert), `ARME` (Dict Arm-Name → `{"env": {...}, "wrapper": <pargate-Arm-Name>}`, `envgate.py:36-61`).

**Eingabe/Ausgabe.** Rein: Arm-Namen aus `ARME`. Jeder Arm laeuft als **Subprozess** mit hygienischem Env (alle `POKERB_*` des Parents gestrippt, `PYTHONHASHSEED=0`, BLAS-Threads 1, dann exakt die Arm-Flags) und spielt seinen Traeger-Stack gegen die env-INSENSITIVE `GTOBaseline` auf identischen, geordneten Decks. Der Parent bildet gepaarte per-Deck-Deltas `Arm − Referenz`. Raus: `edges_<arm>.json` je Arm (inkl. `fingerprint()` der geladenen Konfiguration) und ein `result.json` mit `{arm: {...stats..., "verdict": "KANAL_*", "kanal": "envgate_vs_gtobaseline", "arm_spec": {...}}}`.

**Abhaengigkeiten.** `pargate._baue_fabrik` (hart, gleicher Traeger-Stack wie das Spiegel-Gate), `duplicate.gto` als Referenzgegner, `stats.py`, `pokerbot.strategy.gto_mode` (`apply()` + `fingerprint()`), `runs.py`.

**Zustand.** Je Lauf; der Pflicht-Nullarm `referenz` (leeres Env, gleicher Wrapper) laeuft immer als erstes und definiert die Paarungs-Basis.

**Kosten.** Nicht gemessen als Durchsatz-Zahl im Repo. Groessenordnung ergibt sich aus der Bauform: ein voller Durchlauf ist `len(arme)+1` komplette `duplicate_ab`-Laeufe a `--decks` (Default 12.000).

**Mess-Status.** GEMESSEN, aber als **nachrangiger Kanal**. Gelieferte Zahlen: Kombi-Arm `kombi_r5` 3× repliziert `+25 … +36` vs v3-Referenz; kumulatives Finale vs eingefrorene Basis `v3 +21,4` → `v4 +49,8` (`data/runs/STAND.md`, Nachtrag 2026-08-18 00:36). REFUTIERT als Ship-Kanal: der Arm `prince` misst hier ein **Kanal-Artefakt** von roh −68 bb/100, weil exploit-OFF gegen eine ausbeutbare Baseline antritt (`envgate.py:39-41`) — im Spiegel und live ist derselbe Arm der validierte Champion. Deshalb die harte Regel `envgate-Ergebnisse heissen KANAL_* und sind NIE Ship-Evidenz` (`CLAUDE.md:386`).

**Allein benutzbar?** Nur wenn dein Bot ueberhaupt Import-Zeit-Flags hat. Hat er sie nicht (alles per Konstruktor konfigurierbar), brauchst du dieses Modul nicht — dann reicht `pargate`.

**Fallstricke.** Der gemessene Effekt ist immer „Arm gegen einen FREMDEN Referenzgegner", nie „Arm gegen den Amtierenden". Ein Arm kann hier deutlich gewinnen und im Self-Play exakt neutral sein. Das ist keine Schwaeche der Implementierung, sondern die ehrliche Grenze des Kanals — sie steht im Docstring und wurde trotzdem einmal teuer bezahlt.

---

### Exploit-Gate — `pokerbot/autogym/exploit_gate.py`
**Zweck.** Prueft mit vorregistriertem Kriterium, ob der Gegner-Ausbeutungs-Kanal (Dirichlet-Gegnermodell) ueberhaupt korrekt verdrahtet ist und Geld verdient.

**Schnittstelle.**
- `gate_profil(profil, n_decks, workers, seed, deck_seed0) -> dict` — ein Liga-Profil, exploit ON vs OFF.
- `gate_sixmax_reads(...) -> dict` — die 6-max-Variante (`tag_reads` vs `tag`).
- `kriterium(profil, res) -> "korrekt" | "VERLETZT" | None` — die vorregistrierte Regel.
- `held_fabrik(name)` / `ProjektierterPokerBot` — der Held, der einen HU-Bot ueber die Grader-Projektion an die `pargate6`-Arena anschliesst.
- CLI: `python -m pokerbot.autogym.exploit_gate --decks 600 --workers 8 --sixmax`.

**Das Kriterium im Wortlaut (`exploit_gate.py:94-104`).** Gegen **ausbeutbare** Profile (`station`, `maniac`, `nit`, `whale`): `bb100 >= 0` UND `ci95_lo > −3.0`. Gegen Profile, bei denen Exploit nichts kosten darf (`tag`, `shark`): `bb100 + 2*se >= 0`. `lag`/`rock` sind nur informativ.

**Eingabe/Ausgabe.** Rein: Profilnamen. Raus je Profil `{profil, bb100_on, bb100_off, diff_bb100, se, ci95, verdict, fingerprints, aa_exakt_null, n_decks, sekunden, kriterium}`; im Gesamt-Ergebnis `exploit_korrekt` (bool) + Liste `verletzt`.

**Abhaengigkeiten.** `pargate6.par_gate6` mit `n_seats=2` (hart — es ist die Arena), `pokerbot.coach.oracle.PrinceOracle`, `pokerbot.arena.hybrid.HybridHero._record` (die Zustands-Projektion), `pokerbot.runtime_config.fingerprint_geladen` (der Nachweis, dass der Arm-Schalter wirklich gegriffen hat).

**Zustand.** Je Hand/je Block. Wichtig: das **Adaptionsprotokoll** muss gefuettert werden — `observe_opponent(...)` je Gegneraktion und `observe_hand_end(...)` am Handende, sonst bleibt das Dirichlet-Modell leer und der Test misst per Konstruktion nichts (dieser Fehler ist im Repo einmal passiert und im Docstring vermerkt).

**Kosten.** Gemessen: 592 Decks je Profil in 25–32 s (`data/runs/20260909_192123_exploit_gate/result.json`); der volle Lauf ueber 8 Profile + 6-max dauerte wenige Minuten.

**Mess-Status.** GEMESSEN — und das Ergebnis ist **REFUTIEREND fuer den geprueften Kanal**: alle acht Punktschaetzer ≤ 0, gepoolt ca. −12 bb/100; `exploit_korrekt: false`, verletzt `[nit, station, maniac, whale]` (Quelle: `data/runs/20260909_192123_exploit_gate/result.json`; Einzelwerte: nit −2,09 ± 9,52 · tag −19,26 ± 15,35 · lag −18,50 ± 12,96 · station −17,35 ± 16,31 · maniac −15,74 ± 9,61 · rock −0,31 ± 8,97 · whale −8,26 ± 17,01 · shark −14,40 ± 13,67, je 592 Decks). 6-max-Reads ON vs OFF: +3,64 ± 13,45 NEUTRAL. Konsequenz im Repo: Exploit bleibt ueberall AUS (Journal `EXPLOIT-GATE-VERDIKT`, 2026-09-09).

**Allein benutzbar?** Nur mit `pargate6` + einem Bot, der ein Gegnermodell hat. Das **Muster** (ein Feature gegen Gegner-Archetypen ON/OFF gepaart messen, mit vorab notiertem Bestehenskriterium) ist dagegen sofort uebertragbar und die billigste Art, einen ungemessenen „Exploit-Layer" zu entzaubern.

**Fallstricke.** Ein einzelnes Profil bei 592 Decks hat SE ~9–17 bb/100 — die meisten Einzel-Verdikte sind formal `NEUTRAL`. Die Aussage entsteht erst daraus, dass **alle acht Vorzeichen** in dieselbe Richtung zeigen. Wer nur eine Zeile liest, findet „kein Effekt".

---

### Orakel-Duell — `pokerbot/autogym/orakel_duell.py`
**Zweck.** Haelt dieselben zwei Arme, die `pargate` in Chips vergleicht, gegen das Mathematik-Orakel — als zweites, unabhaengiges Instrument mit Nebenwirkungs-Panel.

**Schnittstelle.** `duell(kandidat, incumbent, n_decks, workers, seed=1, deck_seed0=1000) -> (dict, rows)`; CLI `python -m pokerbot.autogym.orakel_duell --kandidat turn_wert --incumbent sel_m15 --decks 1500`.

**Eingabe/Ausgabe.** Rein: zwei `pargate`-Arm-Namen. Beide spielen dieselben Decks mit Sitz-Tausch; **jede Entscheidung wird der jeweiligen Strategie zugebucht**. Raus je Arm: `decisions`, `gelegenheiten` (Zaehler `check_gelegenheit_{turn,river}` / `facing_bet_{turn,river}`), `zielklassen_je_gelegenheit` (z. B. `verpasster_wert_turn_je100`), `rate_je_1000` (alle Orakel-Regeln je 1000 Entscheidungen), `severity_bb_summe`. Zusaetzlich schreibt es `decisions.jsonl.gz` in den Run-Ordner (alle geflaggten Entscheidungen + 3 %-Sample, mit Strategie-Label).

**Abhaengigkeiten.** `oracle.py` (hart), `pargate._baue_fabrik` (hart), `duplicate._setup_fixed`/`gen_decks`, `runs.entscheidungs_logger`.

**Zustand.** Je Lauf. Wichtiges Detail: die F-Stufe (Frequenzen) wird **nicht** je Chunk finalisiert, sondern die Rohdaten werden hochgereicht und einmal im Parent gepoolt — sonst wird das n≥30-Minimum je Strasse im Chunk nie erreicht und die ganze Stufe ist still tot.

**Kosten.** Nicht als Durchsatz-Zahl im Repo festgehalten; die Kosten dominiert die Rueckschau-Equity (`EQ_ITERS=200` Monte-Carlo je geflaggter Entscheidung).

**Mess-Status.** GEMESSEN als Instrument (es hat das Nebenwirkungs-Panel fuer `turn_wert` geliefert, vorregistriert in `runde5b.py:16-19`: `verpasster_wert_turn` muss fallen, `bet_braucht_unplausible_folds` darf nicht steigen, HART = 0). Eine eigenstaendige bb/100-Zahl hat es per Konstruktion nicht.

**Allein benutzbar?** Nur zusammen mit `oracle.py` und einer Arm-Namensliste.

**Fallstricke.** Die Normierung. Raten „je 1000 Entscheidungen" sind zwischen Armen **nicht** vergleichbar, weil ein aggressiverer Arm die Handlaengen und damit den Nenner veraendert. Deshalb normiert der Code die Zielklassen je **eligible Gelegenheit** (`check_gelegenheit_*`, `facing_bet_*`) und getrennt nach Strasse. Wer das nachbaut und den Nenner falsch waehlt, misst Handlaenge statt Qualitaet.

---

### Mathematik-Orakel — `pokerbot/autogym/oracle.py`
**Zweck.** Verwandelt die Formelsammlung in maschinell pruefbare Urteile ueber einzelne Self-Play-Entscheidungen, getrennt nach Belastbarkeit.

**Schnittstelle.**
- `grade_decision(rep, rec, bb=100) -> bool` (True = diese Entscheidung wurde geflaggt) — der Hauptaufruf.
- `grade_hand_conservation(rep, before, after, hand_no, bb=100)` — die HART-Stufe.
- `finalize_frequencies(rep)` — die F-Stufe, erst am Ende eines Laufes ueber alle gesammelten `facing_bets`.
- `manifest() -> {"verdrahtet_v0": [...], "offen": [...]}` — der ehrliche Stand der Formalisierung.
- Datentypen: `Verdict(tier, rule, severity_bb, proof)`, `OracleReport(decisions, hard, provable, leads, freq, facing_bets)` mit `.counts()`.

**Die vier Stufen (und warum die Trennung zaehlt).**
- **HART** — nie verstellbare Invarianten, aktuell nur Chip-Erhaltung. Ein Verstoss ist ein Bug, kein Stil.
- **P** — pro Entscheidung beweisbar dominierte Aktionen, aktuell nur `free_fold` (Fold bei `to_call = 0`). Die einzige Klasse, die automatisch gepatcht werden darf.
- **L** — „Leads": Rueckschau-Equity gegen die TATSAECHLICHE Gegnerhand mit grosser Marge. Einzeln verrauscht, aggregiert ein Leck-Detektor. Nie ein Beweis. Regeln: `call_unter_pot_odds` (Marge 0.15), `fold_ueber_pot_odds` (0.30), `allin_call_ohne_odds` (range-frei, ueber die optimistische 21-Outs-Obergrenze), `bet_braucht_unplausible_folds` (noetige Fold-Frequenz > 0.75), `verpasster_wert_{turn,river}` (Check mit starker Made Hand und Rueckschau-Equity ≥ 0.75), `verpasster_raise`.
- **F** — Fold-Frequenz je Strasse gegen das MDF-Band (0.10), erst ab n ≥ 30 je Strasse, und **nur Over-Fold** ist ein Befund.

**Eingabe/Ausgabe.** `rec` ist ein flacher Dict: `street`, `pot`, `to_call`, `action`, `amount`, `hero_hole`, `board`, `villain_hole` (None wenn multiway/unbekannt), `call_closes_action`, `effective_stack`, `n_opponents`. Ausgabe ist der mutierte `OracleReport`.

**Abhaengigkeiten.** `knowledge_base.math.formulas` + `postflop_formulas` (hart — die Formeln sind im Projekt unveraenderlich), `pokerbot.engine.equity.equity_vs_hand`, optional `treys` fuer die Made-Hand-Klasse (faellt sauber auf `None` zurueck).

**Zustand.** Der `OracleReport` sammelt ueber den ganzen Lauf; `facing_bets` muss vollstaendig gefuellt sein, bevor `finalize_frequencies` laeuft. Die Rueckschau-Equity ist **rekord-gebunden deterministisch**: `_rec_rng` seedet aus `(hero_hole, villain_hole, board, street, pot)` per CRC32, damit dieselbe Entscheidung lauf- und prozessuebergreifend dasselbe Urteil bekommt.

**Kosten.** Gemessen im Pilot: 3.577 gegradete Entscheidungen (500 Haende, HU + 6-max) in **52,2 s** lokal, inkl. Spielen (`data/autogym/report_20260816_192735.json`). Der Kostentreiber ist `EQ_ITERS = 200` Monte-Carlo-Iterationen je Equity-Aufruf.

**Mess-Status.** GEMESSEN als Detektor: Pilot HART 0 / P 0 / L 35 / F 3 auf dem gesunden Bot (`report_20260816_192735.json`); der allererste Pilotlauf meldete HART 40 — das war ein Bug im **Pruefer selbst**, nicht im Bot (`report_20260816_192554.json`; die Chip-Erhaltungs-Bilanz zaehlte `committed` falsch). Als Verbesserungs-QUELLE ist die Bilanz gemischt: die aus L/F abgeleiteten Guards `mdf_guard` (−3,26 ± 2,19, n=99.000) und `podds_guard`/`lizenz_guard` wurden im Gate REFUTIERT bzw. NEUTRAL gebucht (`data/runs/STAND.md`); die selektions-basierten Guards (`sel_guard` +4,7 ± 2,06, n=99.000) haben getragen. Kernlehre des Projekts daraus: **Selektion schlaegt Frequenz** — welche Haende, nicht wie oft.

**Allein benutzbar?** Ja, `grade_decision` ist eine reine Funktion ueber einen Dict. Minimal noetig: deine Formeln + eine Equity-Funktion. Der Rest ist ~250 Zeilen ohne Fremdzustand.

**Fallstricke.** Die **Pot-Konventionen der Formeln sind entgegengesetzt** und im Code eigens kommentiert (`oracle.py:139-146`): `minimum_defense_frequency` will den Pot VOR dem Einsatz, `equity_needed_to_call` den Pot INKLUSIVE. Der Code speichert deshalb `pot − to_call` fuer die F-Stufe und `pot` fuer die L-Stufe. Wer das verwechselt, bekommt ein Orakel, das systematisch und leise falsch urteilt. Zweiter Punkt: L-Befunde sind Rueckschau gegen EINE Gegnerhand, nie gegen eine Range — sie sind Hypothesen, keine Beweise.

---

### HU-Gym — `pokerbot/autogym/gym_hu.py`
**Zweck.** Laesst den HU-Bot gegen sich selbst auf gepaarten Decks spielen und fuehrt dabei Buch: Positionswert, Symmetrie-Drift und jede Entscheidung durchs Orakel.

**Schnittstelle.** `run(n_pairs=200, seed=7, exploit=True, eq_iters=120, start=20000, bb=100) -> dict`.

**Eingabe/Ausgabe.** Rein: nur Zahlen. Raus: `disziplin`, `haende`, `abbrueche`, `button_netto_bb100`, `paar_drift_bb100`, `paar_drift_se`, `orakel` (die Zaehler-Kurzform) und `orakel_report` (das Objekt selbst).

**Der 4er-Block.** Jedes Deck wird **viermal** gespielt: Holes × Button voll gekreuzt (`(h0,h1)/btn0`, `(h0,h1)/btn1`, `(h1,h0)/btn0`, `(h1,h0)/btn1`). Bei blossem Button-Tausch kuerzt sich nur die Position heraus, nicht die Karten — der Symmetrie-Check waere praktisch machtlos. Im 4er-Block kuerzen sich beide exakt, und `paar_drift` muss gegen 0 laufen.

**Abhaengigkeiten.** `duplicate._setup_fixed`/`gen_decks` (hart), `pokerbot.engine.game.HeadsUpGame`, `pokerbot.strategy.bot.PokerBot`, `oracle.py`.

**Zustand.** Je Lauf. Die zwei Bots leben ueber alle Haende (Modul-Konstante `EQUITY_ITERS` wird beim Bau gesetzt). Bei einem Haenger (>500 Aktionen) wird die Hand **nicht** gebucht und kein HART-Urteil gefaellt — sonst waere ein Abbruch ein falscher Chip-Erhaltungs-Befund.

**Kosten.** Gemessen: 300 HU-Haende + 200 6-max-Haende + Orakel + Gate-Selbsttest zusammen 52,2 s (`data/autogym/report_20260816_192735.json`); ein spaeterer Lauf mit 600 HU-Haenden 75,3 s inkl. allem (`report_20260816_195830.json`).

**Mess-Status.** GEMESSEN: Button-Netto (der kartenbereinigte Wert der Position) **+32,65 bb/100** bei 300 Haenden bzw. **+33,43** bei 600 Haenden (beide Reports oben) — zwei unabhaengige Laeufe, konsistent. Paar-Drift 300 Haende: +294,0 ± 194,6; 600 Haende: +106,8 ± 70,3 — beide innerhalb 2·SE von 0, also E2 bestanden, aber mit sehr weitem Band.

**Allein benutzbar?** Ja, wenn du eine HU-Engine und einen Bot hast. Der 4er-Block ist das eigentlich Uebertragbare und in ~15 Zeilen nachgebaut.

**Fallstricke.** `run()` gibt das nicht-serialisierbare `orakel_report`-Objekt mit zurueck — wer das Ergebnis direkt nach JSON schreibt, bekommt einen `TypeError`. Der Aufrufer muss den Schluessel vorher `pop`en (so macht es `run_local.py:59`). Und: die Paar-Drift hat auch bei 600 Haenden noch ein Band von ±70 bb/100 — sie ist ein Symmetrie-Alarm, keine Praezisionsmessung.

---

### 6-max-Gym — `pokerbot/autogym/gym_six.py`
**Zweck.** Dasselbe fuer den Mehrspieler-Tisch: Self-Play des 6-max-Kerns mit Positions-Ledger, Chip-Erhaltung und Orakel.

**Schnittstelle.** `run(n_hands=300, seed=7, n_players=6, profile="tag", start=10000, bb=100) -> dict`.

**Eingabe/Ausgabe.** Raus: `disziplin`, `haende`, `abbrueche`, `position_bb100` (Netto je Positionslabel BB/SB/UTG/HJ/CO/BTN), `orakel`, `orakel_report`.

**Abhaengigkeiten.** `pokerbot.arena.sixmax` (PROFILES + SixMaxBot), `pokerbot.engine.table.Table`, `oracle.py`.

**Zustand.** Frischer Tisch pro Hand (deterministischer Seed `seed*100003 + h`, rebuy-frei), damit die Chip-Erhaltung sauber pruefbar bleibt — aber die **Bots leben persistent ueber alle Haende**. Beides ist notwendig: pro Hand neu erzeugte Bots koennten ihre Gegnermodelle nie fuellen, und ohne den `new_hand()`-Aufruf bleibt `pf_aggressor = None`, womit der komplette C-Bet-Zweig unerreichbar waere (gemessen: `cbet_policy` 0× in 300 Haenden ohne Protokoll, 143× mit).

**Kosten.** Gemessen: 200 Haende als Teil des 52,2-s-Piloten (`report_20260816_192735.json`).

**Mess-Status.** GEMESSEN: Positions-Ledger ueber 30.000 Haende — `BB −28,9 · SB −29,6 · UTG +6,8 · HJ +15,8 · CO +2,4 · BTN +33,5` bb/100; Facing-Bet-Katalog `flop fold_freq 0,216 · turn 0,297 · river 0,337` (Journal `RUNDE4-6MAX-KATALOG`, 2026-08-17). Bei den Pilot-Groessen (200–300 Haende) sind die Positionszahlen dagegen dreistellig verrauscht (`BTN +335,6`, `report_20260816_192735.json`) — unbrauchbar.

**Allein benutzbar?** Ja, mit einer N-Spieler-Engine. Der Ledger ist das Wertvolle: Positionswerte sind eine kartenarme, schnell konvergierende Kontrollgroesse.

**Fallstricke.** Die **L-Stufe des Orakels ist hier per Konstruktion tot** — multiway gibt es keine eindeutige Rueckschau-Gegnerhand, `villain_hole` wird `None` uebergeben, und alle L-Regeln haengen daran. In allen Pilot-Reports steht deshalb `"L": 0` fuer 6-max. Das ist kein sauberer Bot, das ist ein abgeschalteter Detektor.

---

### Selbsttest der Schleife — `pokerbot/autogym/selftest.py`
**Zweck.** Prueft in einem Kommando vier vorregistrierte Erwartungen an die Messmaschinerie selbst, bevor man ihr ein Bot-Urteil glaubt.

**Schnittstelle.** `python -m pokerbot.autogym.selftest [--quick]`; intern `e1_orakel_wahrheit() -> (ok, rows)`, `_defekt_factory(seed, mode)` mit `mode in ("station", "folder")`, `_lead_rate(rep, rule=None)`. Exit-Code 0 nur bei 4/4.

**Die vier Erwartungen.**
- **E1 Orakel-Wahrheit:** jede verdrahtete Formel gegen eine **unabhaengig handgerechnete `Fraction`-Referenz** (Pruefer getrennt vom Geprueften). Im Code liegen 9 solche Checks (`selftest.py:37-70`), Toleranz `1e-12`.
- **E2 Symmetrie:** Paar-Drift des gesunden Bots im Selbstspiel `|drift| < 2·SE`.
- **E3 Detektor:** ein konstruierter Defekt-Bot wird (a) vom Orakel erkannt (Lead-Rate ≥ 2× gesund, verglichen auf **derselben Regel**, die zur Defekt-Signatur passt) und (b) vom Gate verworfen.
- **E4 Null-Stabilitaet:** gesund vs gesund (andere Seeds) darf **kein** `ANWENDEN` erzeugen — die Schleife erfindet keine Verbesserungen.

**Eingabe/Ausgabe.** Keine Eingabe ausser `--quick`. Ausgabe: PASS/FAIL-Zeilen auf stdout, ein Journal-Eintrag `SELFTEST-BEFUND`, Exit-Code.

**Abhaengigkeiten.** `gym_hu`, `improver.gate_ab`, `duplicate.pokerbot`, `knowledge_base.math.*`.

**Zustand.** Zustandslos, aber E3 **monkeypatcht** `gym_hu._make_bot` und stellt es im `finally` zurueck.

**Kosten.** Docstring nennt „~2-4 min lokal"; `--quick` verkleinert die Stichproben (60 statt 150 Paare, 60 statt 120 Gate-Decks). Nicht unabhaengig nachgemessen.

**Mess-Status.** TEILWEISE. E1 ist heute nachweisbar gruen (die verwandte, breitere Formel-Regression `verify_refs` laeuft mit **66/66 exakt**, heute nachgefahren). Ein Beleg fuer einen vollstaendig gruenen 4/4-Lauf liegt im Repo **nicht** vor: `docs/STATE.md:316` fuehrt „selftest E1–E4 gruen kriegen" als offenen naechsten Schritt. Das Journal enthaelt nur den Nebenbefund E3c: gesund vs Nie-Folder `+394,9 ± 279,9` bei 60 Decks (Journal `SELFTEST-BEFUND`, 2026-08-16). Fuer den Gate-Beweis E3b wird bewusst der **Immer-Folder** benutzt, nicht die Station: nur der Folder hat ein mathematisch sicheres Vorzeichen (er verschenkt jeden Pot, sobald gesetzt wird); die Station ist ueber einen 1-Hand-Horizont ohne Anpassung nicht sicher schlagbar.

**Allein benutzbar?** Das Muster ja, der Code nein. Uebertragbar ist die Idee: **konstruiere absichtlich einen kaputten Bot mit bekanntem Vorzeichen und verlange, dass deine Messmaschine ihn findet.** Ohne diesen Test weisst du nicht, ob dein Gate ueberhaupt etwas messen kann.

**Fallstricke.** E3a vergleicht Lead-Raten. Vergleicht man die GESAMT-Rate statt der zur Defektsignatur passenden Einzelregel, verduennen neu hinzugefuegte Orakel-Regeln mit anderem Gegenstand die Metrik und der Detektor-Test faellt still durch (im Code als gemessener Befund vermerkt, `selftest.py:118-124`).

---

### Run-Ablage — `pokerbot/autogym/runs.py`
**Zweck.** Bindet jedes Messergebnis an Konfiguration, Git-Commit und Host, in EINER Struktur fuer alle Laeufe.

**Schnittstelle.**
- `neuer_run(name, config) -> Path` — legt `data/runs/<JJJJMMTT_HHMMSS>_<name>/` an und schreibt `config.json` (deine Config plus `commit` aus `git rev-parse --short HEAD`, `host`, `ts`).
- `schliesse_run(d, result)` — schreibt `result.json` und haengt eine Zeile `{"run": <ordner>, **result}` an `data/runs/INDEX.jsonl` (append-only).
- `entscheidungs_logger(run_dir, sample=0.03) -> (log_fn(rec, geflaggt), flush_fn)` — sammelt ALLE geflaggten Entscheidungen plus ein 3 %-Zufallssample der unauffaelligen (Basisrate) und schreibt sie als `decisions.jsonl.gz`.

**Eingabe/Ausgabe.** Dicts rein, Dateien raus. `INDEX.jsonl` ist die eine Zeile-pro-Lauf-Tabelle, aus der `bericht.py` die Uebersicht baut.

**Abhaengigkeiten.** Nur Standardbibliothek + ein `git`-Binary im PATH (faellt auf `"?"` zurueck, wenn es fehlt).

**Zustand.** Dateisystem. Der Ordnername enthaelt die Sekunde — zwei Laeufe in derselben Sekunde kollidieren (`mkdir(exist_ok=False)` wirft).

**Kosten.** Vernachlaessigbar; `edges.json` bei 30.000 Decks ist wenige hundert kB.

**Mess-Status.** UNGEMESSEN (Infrastruktur ohne EV-Wirkung). Ihr Wert ist indirekt belegt: alle in diesem Katalog zitierten Zahlen stammen aus `data/runs/*/result.json` bzw. `INDEX.jsonl`.

**Allein benutzbar?** Ja, ~40 Zeilen, kopierbar. Der eine Punkt, der zaehlt: **der Commit-Hash im `config.json`**. Ohne ihn ist ein halbes Jahr alte Messung nicht mehr zuzuordnen.

**Fallstricke.** `schliesse_run` schreibt das komplette `result`-Dict in die Index-Zeile. Rohdaten (`edges`) muessen vorher herausgenommen werden, sonst blaeht die Index-Datei auf Megabyte auf — `pargate.main()` macht genau das (`res.pop("edges")`, dann separat als `edges.json`).

---

### Formel-Regressionsnetz — `pokerbot/autogym/verify_refs.py`
**Zweck.** Prueft, dass die heute im Repo liegenden Formelfunktionen noch exakt das rechnen, was bei ihrer Verifikation festgeschrieben wurde.

**Schnittstelle.** `python -m pokerbot.autogym.verify_refs`; Exit-Code 0 nur bei 100 %.

**Eingabe/Ausgabe.** Rein: `knowledge_base/math/postflop_calc_verified.json` und `strategy_calc_verified.json`, je mit Eintraegen `{function_name, verify_expr, verify_value}`. Der Runner `eval`-t jeden Ausdruck gegen das installierte Modul und vergleicht mit Toleranz `1e-9`. Raus: eine Zeile `verify_refs: P/T exakt, M fehlend, D Drift/Fehler` plus Detailzeilen.

**Abhaengigkeiten.** `knowledge_base.math.postflop_formulas` + `strategy_formulas` (hart).

**Zustand.** Zustandslos.

**Kosten.** Wenige Sekunden (heute nachgefahren).

**Mess-Status.** GEMESSEN POSITIV: **66/66 exakt, 0 fehlend, 0 Drift** — heute (2026-09-10) live nachgefahren; dieselbe Zahl steht in `docs/STATE.md:302`.

**Allein benutzbar?** Ja, wenn du deine Formeln mit festgeschriebenen Referenzwerten ablegst.

**Fallstricke.** Der Docstring sagt es selbst und es ist der Kern: `verify_expr`/`verify_value` stammen aus **derselben Erzeugung** wie die Formeln. Das ist ein **Konsistenz-**, kein Wahrheits-Test — es faengt Drift und Regression, nicht einen von Anfang an falschen Formeleintrag. Die Wahrheits-Stufe sind die 9 unabhaengig handgerechneten `Fraction`-Referenzen in `selftest.E1`. Wer 66/66 als „unsere Mathematik ist bewiesen" liest, hat den Test missverstanden.

---

### Stand-Bericht — `pokerbot/autogym/bericht.py`
**Zweck.** Rendert `data/runs/INDEX.jsonl` + `data/autogym/journal.jsonl` zu einer lesbaren Seite `data/runs/STAND.md`.

**Schnittstelle.** `python -m pokerbot.autogym.bericht` (nur `main()`, keine API).

**Eingabe/Ausgabe.** Rein: die zwei JSONL-Dateien. Raus: Markdown mit einer Lauf-Tabelle (Lauf | Kandidat | bb/100 | SE | n | Verdikt) und den letzten 15 Journal-Eintraegen.

**Abhaengigkeiten.** Nur `runs.py`-Konventionen (Dateipfade sind fest verdrahtet).

**Zustand.** Zustandslos; ueberschreibt `STAND.md` vollstaendig.

**Kosten.** Millisekunden.

**Mess-Status.** UNGEMESSEN (Berichtswerkzeug).

**Allein benutzbar?** Nur mit derselben Ablage-Konvention. 30 Zeilen — schneller selbst geschrieben als portiert.

**Fallstricke.** Es ueberschreibt `STAND.md` komplett, waehrend im Repo unten in derselben Datei **von Hand geschriebene Nachtraege** stehen (die „Nachtrag 2026-08-18"-Bloecke, aus denen mehrere Zahlen dieses Katalogs stammen). Ein unbedachter Lauf loescht sie.

---

### Kampagnen-Treiber — `pokerbot/autogym/runde4.py`, `runde5.py`, `runde5b.py`
**Zweck.** Fahren ganze, vorab aufgeschriebene Messkampagnen automatisch ab (Phasen, Seeds, Replikationen) und berichten selbst.

**Schnittstelle.** Je ein CLI ohne Argumente: `python -m pokerbot.autogym.runde4` / `runde5` / `runde5b`. `runde4` hat ein Zeitbudget (`ZIEL_SEKUNDEN = 2*3600`, `WORKERS = 20`), `runde5` startet mit einem A/A-Nulltest als Abnahme und bricht bei Verletzung ab, `runde5b` faehrt die Drei-Laeufe-Regel zu Ende (zwei frische Deck-Baenke plus Kombi-Montage plus Orakel-Duell-Panel).

**Eingabe/Ausgabe.** Rein: nichts (alles hart im Treiber). Raus: Run-Ordner je Phase, Journal-Eintraege, ein Kampagnen-JSON.

**Abhaengigkeiten.** `pargate`, `envgate`, `orakel_duell`, `gym_six`, `runs.py` — alle hart.

**Zustand.** Je Kampagne; **strikt sequenzielle Flotten** (eine Worker-Flotte zur Zeit, RAM-Regel).

**Kosten.** `runde4` ist explizit auf 2 h Wanduhr ausgelegt (Phasen ~45/12/35 min plus Restzeit fuer die entscheidende Messung).

**Mess-Status.** GEMESSEN als Treiber (sie haben die Journal-Eintraege `RUNDE4-SWEEP`, `RUNDE4-DECISIVE sel_m15 ANWENDEN 8.68`, `RUNDE4-6MAX-KATALOG` erzeugt — `data/autogym/journal.jsonl`, 2026-08-17). Eigene bb/100 haben sie nicht.

**Allein benutzbar?** Nein — sie sind projektspezifische Drehbuecher, keine Bibliothek. Uebertragbar ist ausschliesslich das **Muster**: Erwartungen VOR dem Lauf in eine Konstante schreiben (`runde5.ERWARTUNGEN`), dann messen. Das macht Post-hoc-Rationalisierung mechanisch schwer.

**Fallstricke.** Sie tauften bewusst nicht — `runde5.py:14` sagt es explizit: „dieser Treiber misst, er tauft nicht". Wer einen solchen Treiber die Entscheidung mit treffen laesst, hat kein Gate mehr, sondern einen Optimierer auf der eigenen Metrik.

---

### Exploit-Jagd — `pokerbot/autogym/exploit_jagd.py`
**Zweck.** Laesst adaptive Jaeger (persistentes Gegnermodell) ueber viele Haende auf den eingefrorenen Bot los — **Diagnose, nicht Sieg**: jeder gefundene Exploit ist eine Haertungs-Anleitung.

**Schnittstelle.** `python -m pokerbot.autogym.exploit_jagd --haende 100000 --workers 20`. Intern `_jagd((seed, n_hands)) -> ledger`.

**Eingabe/Ausgabe.** Rein: Haende + Jaegerzahl. Raus (aggregiert): `jaeger_bb100`, `se_ueber_jaeger` (SE **ueber die unabhaengigen Jaeger**, nicht ueber Haende), `jaeger_positiv` („14/20"), `sd_netto_bb100` / `nsd_netto_bb100` (Showdown vs Non-Showdown), `fold_ernte` je Strasse, `showdown` (gewonnen/verloren/split); je Jaeger zusaetzlich `modell` (das Endprofil des Gegnermodells) in `jaeger_einzeln.json`.

**Abhaengigkeiten.** `pokerbot.engine.game.HeadsUpGame`, `pokerbot.strategy.bot.PokerBot`, `runs.py`.

**Zustand.** Der Jaeger ist EIN persistenter Bot ueber alle seine Haende (genau die Adaption, die das gepaarte Gate bewusst nie zulaesst); der Verteidiger wird je Hand frisch erzeugt (der eingefrorene Bot lernt nicht).

**Kosten.** Gemessen: 100.000 Haende mit 20 Workern in **971,9 s** bzw. 998,8 s (`data/runs/20260817_020232_exploit_jagd/result.json`, `…_014431_…`).

**Mess-Status.** GEMESSEN, Ergebnis differenziert: adaptive Jaeger **+8,87 ± 6,9** bb/100 (14/20 positiv) gegen die Null-Kontrolle **+7,73 ± 8,7** (12/20) — der Adaptions-ZUGEWINN ist ~+1 und **nicht signifikant**. Der Befund liegt woanders: der Gewinnkanal verschiebt sich hart (Showdown +5,8 → +19,9; Non-Showdown +1,9 → −11,0) und **alle 20 unabhaengigen Jaeger konvergieren auf dasselbe Verteidiger-Profil**: VPIP 0,75–0,77, fold_to_bet 0,29–0,31, aggression 0,31–0,34. Das ist die empirische Haertungs-Landkarte. Zwei Katastrophen-Jaeger (−69/−47) zeigen das Tail-Risiko generischer Adaption. (Quelle: Journal `EXPLOIT-JAGD`, 2026-08-17 02:19:27, plus die beiden `result.json`.)

**Allein benutzbar?** Ja. Es ist der einfachste Baustein hier: zwei Bots, eine Schleife, ein Ledger.

**Fallstricke.** Das **Adaptionsprotokoll**. Der erste 100k-Lauf war NULL per Konstruktion, weil `observe_opponent` nie gerufen wurde — das Dirichlet-Modell blieb bei `hands: 0, confidence: 0` und der „Jaeger" war ein gewoehnlicher Bot. Der Fix steht als Kommentar an der Stelle (`exploit_jagd.py:53-56`). Wenn du ein lernendes Gegnermodell testest, verifiziere ZUERST, dass es ueberhaupt Beobachtungen bekommt.

---

### Querverweis: das minimale Gate — `pokerbot/autogym/improver.py::gate_ab`
`improver.py` gehoert inhaltlich zur Verbesserungs-Schleife, enthaelt aber die **kleinste vollstaendige Gate-Funktion** des Repos, auf die `selftest` und `run_local` zurueckgreifen:

```
gate_ab(make_candidate, make_incumbent, n_decks, seed) -> {"bb100", "se", "n_decks", "verdict"}
```

Sie ruft `gen_decks` + `duplicate_ab` und wendet dieselbe Schwellenlogik an wie `stats.verdikt`, nur ohne Sparse-Klausel und ohne Bootstrap (`improver.py:649-662`): `ANWENDEN` bei `bb100 − 2·se > 0`, `VERWERFEN` bei `bb100 + 2·se < −1.0`, sonst `NEUTRAL`. Wer nur EINEN Baustein aus diesem Kapitel mitnehmen will: das sind 12 Zeilen ueber `duplicate_ab`, und sie sind der Unterschied zwischen „gefuehlt besser" und „gemessen besser". Ebenfalls dort: `_journal(entry)` (`improver.py:642`), das jeden Befund mit Zeitstempel an `data/autogym/journal.jsonl` anhaengt — Journal-Pflicht ist im Projekt bindend.

---

### Was in diesem Subsystem als REFUTIERT gilt (damit du es nicht nachbaust)

- **Der Dirichlet-River-Exploit als Kanal:** `exploit_gate` misst alle acht Liga-Profile ≤ 0, gepoolt ca. −12 bb/100, `exploit_korrekt: false` (`data/runs/20260909_192123_exploit_gate/result.json`). Exploit ist im Repo ueberall AUS.
- **Frequenz-Matching als Verbesserungsprinzip:** die frequenzgetriebenen Guards aus den F/L-Befunden (`mdf_guard` −3,26 ± 2,19 bei n=99.000, `podds_guard`, `lizenz_guard`) wurden im Gate NEUTRAL/negativ gebucht (`data/runs/STAND.md`), die selektionsgetriebenen (`sel_guard` +4,7 ± 2,06 bei n=99.000) haben getragen. Projektlehre: **Selektion schlaegt Frequenz.**
- **Der 5 %-Trim als Entscheidungsstatistik:** war Estimator v1, ist widerlegt fuer duenne Kanaele (er entfernt genau die Signal-Decks) und steht nur noch als Diagnosefeld im Ergebnis (`stats.py:19-31`).
- **`envgate`-Positiva als Ship-Evidenz:** der Arm `prince` misst dort ein Kanal-Artefakt von roh −68 bb/100 und ist zugleich der live validierte Champion (`envgate.py:39-41`). Deshalb das eigene Vokabular `KANAL_*`.
- **Adaptive Generik als Edge:** die 20-Jaeger-Kampagne zeigt einen Adaptions-Zugewinn von ~+1 bb/100 bei SE 6,9 — nicht signifikant — bei gleichzeitig zwei Katastrophen-Jaegern (−69/−47) (Journal `EXPLOIT-JAGD`).

---

## Externe Benchmarks

Dieses Subsystem beantwortet genau eine Frage: **wie gut ist mein Bot, gemessen an etwas, das nicht ich selbst
gebaut habe?** Es besteht aus Protokoll-Adaptern (fremde API/Umgebung -> unser Engine-Zustands-dict -> zurueck in
die fremde Aktions-Sprache) und aus Auswertern (bb/100, AIVAT, Varianz-Reduktion, Exploitierbarkeit). Kein Modul
hier trifft eine Poker-Entscheidung — sie transportieren nur.

Du brauchst davon **hoechstens den einen Adapter fuer den Gegner, den du wirklich messen willst**. Der Rest ist
Ballast. Wer nur eine interne Regressions-Schranke braucht, nimmt `duplicate.py` (gepaarte Decks) und ignoriert
das ganze Kapitel. Wer einen absoluten GTO-Abstand braucht, braucht GTO Wizard — und dafuer einen Zugang, den du
selbst besorgen musst.

**Eine Warnung vorweg, die fuer fast jedes Modul hier gilt:** `data/` und `tools/` sind in diesem Repo
gitignored (`.gitignore:8-9`). Der GTOW-Client (`tools/gtow_client/`), die Pluribus/PHH-Hand-Historien
(`data/_phh_repo/`) und alle Laufergebnisse sind **nicht** Teil dessen, was du bekommst. Die Adapter sind da,
die Gegenstelle und die Daten nicht.

---

### GTO-Wizard-Adapter — `pokerbot/benchmark/gtowizard.py`

**Zweck.** Bildet die GTO-Wizard-Researcher-API (`GameServiceResponse` <-> `ActRequest`) auf unseren
Engine-Zustand ab, sodass ein beliebiger Bot mit `.decide(state)` gegen GTO Wizard AI spielt und AIVAT-bewertet
wird.

**Schnittstelle.**
- `parse_cards(s: str | None) -> list[str]` (`:39`) — `'AsKdQh'` -> `['As','Kd','Qh']`.
- `_parse_history(action_history, button_seat, blinds)` (`:45`) — rekonstruiert aus der flachen Token-Liste
  (`'f'`, `'c'`, `'k'`, `'bX'`, `'_'`) unsere History-Liste plus die je Strasse eingezahlten Betraege beider
  Spieler; gibt `(history, committed_hero, committed_villain, street_idx)` zurueck.
- `gtow_to_state(gsr: dict) -> dict` (`:92`) — der Kern: kompletter API-Response -> unser Zustands-dict, Held
  IMMER auf Index 0 normiert.
- `decision_to_act(decision: dict, leg: dict, la_codes: list[str]) -> dict` (`:157`) — `{action, amount}` ->
  `{"action": "f|c|k|b", "amount": int|None}`, geklemmt auf `raise_range`, mit Legalitaets-Garantie.
- `class PokerBotAgent` (`:184`) — `__init__(seed=7, exploit=True, use_resolver=None, use_turn_resolver=None)`,
  `act_dict(gsr) -> dict` (`:251`, synchron), `act_async(gsr)` (`:261`, `asyncio.to_thread`),
  `hand_end(final_gsr=None)` (`:269`, fuettert das Gegner-Modell mit dem Endzustand).

**Eingabe/Ausgabe.** Rein: der API-Response als dict mit `game` (`blinds`, `starting_stack`) und `game_state`
(`street`, `common_pot`, `total_pot`, `board_cards` als String, `players[{stack, position, hole_cards}]`,
`legal_actions`, `raise_range{min,max}`, `action_history`, `is_hand_over`, `winnings`, `aivat_score`). Raus: das
Engine-Zustands-dict mit den tragenden Schluesseln `street`, `board`, `pot`, `bb`, `current_bet`, `button`,
`hand_id`, `history`, `players[0..1]` (je `hole`, `stack`, `committed_street`, `committed_total`, `is_button`)
und `legal` (`to_call`, `can_fold/check/call/raise`, `raise_min`, `raise_max`, `is_bet`). Der Held ist der Sitz,
dessen `hole_cards` gesetzt sind — der Gegner hat dort `None`.

**Abhaengigkeiten.** Hart: `pokerbot.strategy.bot.PokerBot` (nur in `PokerBotAgent`, lazy importiert),
`pokerbot.strategy.gto_mode.apply()` (wird auf Modulebene VOR jedem Strategie-Import gerufen, weil
`postflop`/`advisor` ihre Flags zur Importzeit lesen), `pokerbot.runtime_config`, `pokerbot.benchmark.gtow_ledger`,
optional `pokerbot.strategy.auslese`. **Die beiden reinen Mapping-Funktionen `gtow_to_state` und
`decision_to_act` haengen an gar nichts** ausser `os` — sie sind einzeln kopierbar.

**Zustand.** `PokerBotAgent` ist zustandsbehaftet je Sitzung: der gewickelte `PokerBot` traegt Range-Tracker und
Gegner-Modell. Zuruecksetzen passiert ueber `hand_end()` bzw. das darunterliegende `observe_hand_end`. Ein
`threading.Lock` (`self._decide_lock`) serialisiert alle `decide`-Aufrufe, weil eine Entscheidung Bot-Zustand
mutiert — mehrere parallele Haende teilen sich also EINE Bot-Instanz und einen Lock. `hand_id` aus dem Response
adressiert die per-Hand-Randomisierung; ohne sie vermischen sich parallele Haende.

**Kosten.** Gemessen im Live-Kanal mit Resolver AN: **8,9 s/Hand** (n=974, `docs/STATE.md:1021`), **10,1 s/Hand**
(n=100, `docs/STATE.md:963`), **12,6 s/Hand** (n=98, `docs/STATE.md:942`). Mit Parallelitaet ~2.500 Haende in
8–9 h (`CLAUDE.md`, Block „MESS-OEKONOMIE"). Der Adapter selbst kostet nichts messbares; die Zeit steht im Bot
und in der API.

**Mess-Status.** Der Kanal ist der Anker des Projekts, also GEMESSEN — mit Zahlen, die durch ihn gewonnen wurden:
HEAD-Engine **AIVAT −20,09 ± 7,18 bb/100 (n=974)** (`docs/STATE.md:1021`); v4-auf-PRINCE **−21,12 (n=979)** gegen
Kontroll-Arm **−31,34 (n=488)** (Journal `GTOW-NACHT2-FAZIT-MANUELL`, `data/autogym/journal.jsonl`). Am Adapter
selbst wurden ZWEI Bugs gemessen und gefixt, beide mit direktem bb/100-Effekt: (1) `to_call` wurde als
`total_pot − common_pot` gelesen und war praeflop um den ganzen Pot inflationiert (`:114-124`, Env
`POKERB_TOCALL_FIX=0` stellt den Fehler fuer das A/B wieder her); (2) `blinds` kommt live als `[BB, SB]`, wurde
aber als `[SB, BB]` entpackt — jeder Live-Lauf trug ein eingebautes Praeflop-Overfold (`:52-58`, Fix: Entpacken
nach Groesse). Der Selbsttest `python -m pokerbot.benchmark.gtowizard` (`:290`) friert beide Faelle als Assert
ein.

**Allein benutzbar?** Ja, die Mapping-Schicht: `gtow_to_state` + `decision_to_act` sind zwei reine Funktionen
ohne Projekt-Abhaengigkeit. Minimal brauchst du nur deinen eigenen Bot mit `.decide(state)`. Fuer einen echten
Lauf brauchst du zusaetzlich den **GTOW-Client**, und der liegt unter `tools/gtow_client/` — **gitignored**, also
nicht in dem, was du bekommst. Er ist der von GTO Wizard bereitgestellte Client; die Klasse dort heisst
`PokerBotMVP` und ruft `PokerBotAgent.act_dict`/`act_async`.

**Fallstricke.** Der Adapter liest seine Konfiguration aus Umgebungsvariablen, die zum Teil **zur Importzeit**
wirken (`_apply_gto_mode()` auf Modulebene, `auslese.setze_env` vor dem `bot`-Import). Wer den Bot vorher
importiert oder eine Variable nachtraeglich setzt, misst einen anderen Bot als er glaubt — genau dafuer existiert
`runtime_config.fingerprint_geladen` (unten). Zweiter Fallstrick: `act_dict` synchron aus dem Event-Loop gerufen
blockiert ALLE parallelen Haende; der Zaehler `loop_blockierende_aufrufe` (`:246`) macht das sichtbar, aber der
Client muss `act_async` awaiten, sonst laeuft dein „paralleler" Lauf seriell.

---

### GTOW-Hand-Ledger — `pokerbot/benchmark/gtow_ledger.py`

**Zweck.** Append-only-JSONL-Protokoll, das jedes Hand-Ereignis eines Live-Laufs SOFORT auf Platte schreibt,
damit ein Abbruch nicht den ganzen Chunk verliert.

**Schnittstelle.**
- `class GtowLedger(pfad=None)` mit `prozess_start(fingerprint)`, `hand_start(hand_id, arm, fingerprint_hash)`,
  `hand_end(hand_id, aivat, winnings, status, technische_events=())`, `offene_haende()`.
- `lese(pfad) -> list[dict]`, `abgleich(pfad) -> {"offen", "abgeschlossen", "doppelt_gestartet"}`,
  `offene_haende(pfad)`, `offene_haende_alle(verzeichnis)`.
- `standard_ledger() -> GtowLedger` — das eine Ledger dieses Prozesses.
- `melde_hand_start(agent, hand_id)` / `melde_hand_ende(agent, hand_id, terminal, status="ok", ...)` — die Hooks
  fuer den Client; beide werfen NIE.

**Eingabe/Ausgabe.** Rein: `hand_id`, Arm-Name, Fingerprint-Hash, und am Ende der Terminal-Response (dict oder
Objekt), aus dem `aivat_score` und `winnings` gezogen werden. Raus: eine JSON-Zeile je Ereignis mit `typ`,
`zeit`, `pid` plus den Feldern des Ereignisses. Datei:
`data/runs/v10/ledger_<prozess-start>.jsonl`, ueberschreibbar mit `POKERB_LEDGER_PFAD`.

**Abhaengigkeiten.** Nur `pokerbot.config` fuer `DATA_DIR` — trivial ersetzbar. Sonst Standardbibliothek.

**Zustand.** Je Prozess ein Singleton (`_LEDGER`). Der Dateiname bindet das Ledger an genau diesen Prozess. Beim
Wiederanlauf wird die vorhandene Datei gelesen, damit ein Doppelstart einer Hand ueber Prozessgrenzen hinweg
auffaellt. Zuruecksetzen = neue Datei bzw. neuer Prozess.

**Kosten.** Ein `open('a')` + `flush()` + `os.fsync()` je Ereignis. Nicht gemessen; bei ~10 s/Hand irrelevant,
bei einem schnellen Offline-Kanal waere `fsync` je Hand spuerbar.

**Mess-Status.** UNGEMESSEN als Groesse — aber der Anlass ist gemessen: „Chunk 4 der Nacht 2 ging komplett
verloren" (Modul-Docstring, Bezug `docs/V10_FAKTEN.md` A8), Journal `GTOW-NACHT2-FAZIT-MANUELL`
(„Chunk-4-Haende NICHT geloggt (Client schreibt HH erst am Ende) = verloren").

**Allein benutzbar?** Ja, komplett. Ersetze den `config`-Import durch einen Pfad und du hast ein generisches
Crash-sicheres Lauf-Ledger.

**Fallstricke.** Die Disziplin, nicht der Code: `status="ok"` ohne AIVAT wird automatisch zu `"unbekannt"`
herabgestuft (`:71-72`) — ein fehlender Wert wird NIE zu 0 imputiert. Wer die Auswertung selbst schreibt und
`unbekannt` als 0 zaehlt, macht genau den Fehler, den dieses Modul verhindern soll.

---

### Laufzeit-Fingerprint + Fehlkonfig-Gatter — `pokerbot/runtime_config.py`

**Zweck.** Erzeugt je Prozess einen Hash dessen, was TATSAECHLICH geladen ist (Bot-Flags aus dem lebenden Objekt,
Advisor-Dateihashes, Git-Stand), und bricht den Lauf ab, wenn er nicht zum erwarteten Profil passt. Liegt nicht
im `benchmark/`-Verzeichnis, ist aber harte Abhaengigkeit des GTOW-Adapters.

**Schnittstelle.** `fingerprint_geladen(bot, stack_name) -> dict` (`:225`), `fingerprint_hash(fp) -> str`
(`:266`), `pruefe_konfiguration(erwartet, ist)` (`:272`, `SystemExit` bei Abweichung), `gatter_aus_env(fp,
log=print)` (`:285`), dazu Bausteine `git_stand()`, `sha256_datei()`, `advisor_hashes(bot)`,
`prince_importflags()`, `prince_abweichungen(...)`.

**Eingabe/Ausgabe.** Rein: die lebende Bot-Instanz + der Name der Guard-Kette. Raus: ein dict mit den
Pflichtfeldern (`PFLICHTFELDER`, `:64`) inklusive `fingerprint_hash`; `pid`, `zeit_utc` und der Hash selbst gehen
NICHT in den Hash ein (`_NICHT_IM_HASH`, `:73`).

**Abhaengigkeiten.** `pokerbot.strategy.gto_mode` (Soll-Werte des PRINCE-Profils), `hashlib`/`inspect`/
`subprocess` (Git). Fuer ein fremdes Projekt ist das Konzept uebertragbar, der Code nicht — er kennt unsere
Flags namentlich.

**Zustand.** Zustandslos (liest nur).

**Kosten.** Ein `git`-Aufruf mit 10 s Timeout (`_GIT_TIMEOUT_S`, `:75`) + SHA256 ueber die geladenen
Advisor-Dateien, einmal je Prozess. Nicht praeziser gemessen.

**Mess-Status.** UNGEMESSEN als Effekt. Der Anlass ist belegt: „der GTOW-Harness lief ohne jede Konfig-Pruefung
(`gto_mode.fingerprint()` existierte, wurde aber nie gerufen; `POKERB_AUSLESE_STACK` fehlte in den
Fingerprint-Keys), und die HU-Web-App spielte eine nie gemessene Konfiguration" (Modul-Docstring `:3-6`).

**Allein benutzbar?** Nur als Muster. Nimm die Idee (Fingerprint aus dem OBJEKT, nicht aus der Env-Absicht), nicht
die Datei.

**Fallstricke.** Ohne `POKERB_ERWARTE_PROFIL` loggt das Gatter nur und bricht nicht ab — eine Fehlkonfiguration
faellt dann erst in der Auswertung auf, wenn ueberhaupt.

---

### Slumbot-Client — `pokerbot/benchmark/slumbot.py`

**Zweck.** Spielt unseren Bot ueber die oeffentliche Slumbot-API (HUNL, 200 bb, 50/100) und rechnet die
Gewinnrate in bb/100 aus.

**Schnittstelle.**
- `parse_tokens(seg: str) -> list[str]` (`:40`) — zerlegt ein Strassen-Segment des Aktions-Strings in
  `k`/`c`/`f`/`b<to>`.
- `build_state(hole, board, action, client_pos, button) -> dict | None` (`:58`) — **das wiederverwendbare
  Herzstueck**: rekonstruiert den vollstaendigen Engine-Zustand allein aus Slumbots Aktions-String; `None`, wenn
  die Hand schon vorbei ist.
- `decision_to_incr(dec, state) -> str` (`:148`) — `{action, amount}` -> Slumbots Inkrement-String
  (`'f'`/`'k'`/`'c'`/`'b<to>'`).
- `play_hand(bot, token, verbose=False) -> (winnings, token)` (`:163`) — eine komplette Hand.
- `play_hand_verbose(bot, token, verbose=False) -> (winnings, token, record)` (`:207`) — dieselbe Schleife, gibt
  zusaetzlich eine reiche Zeile zurueck.

**Eingabe/Ausgabe.** Rein: JSON von `POST /api/new_hand` und `POST /api/act` mit `token`, `client_pos`,
`hole_cards`, `board`, `action`, `winnings`, und **bei Showdown** `bot_hole_cards` + `won_pot`. Raus: unser
Zustands-dict (dieselben tragenden Schluessel wie beim GTOW-Adapter: `street`, `board`, `pot`, `history`,
`players`, `legal`); `play_hand_verbose` liefert zusaetzlich `{hole_cards, board, bot_hole_cards, action,
winnings, won_pot, client_pos, button}` — genau das Format, das `slumbot_adjust.py` frisst.

**Abhaengigkeiten.** `urllib.request` (kein `requests`), `pokerbot.strategy.bot.PokerBot` nur in `main()`;
`build_state`/`decision_to_incr`/`parse_tokens` sind rein und projektfrei. Der uebergebene Bot ist duck-typed:
`.decide(state)` + `.hero_idx` (+ optional `.observe_hand_end`).

**Zustand.** Der `token` traegt die Sitzung ueber alle Haende — er muss von Hand zu Hand weitergereicht werden.
Der Bot selbst ist je Sitzung zustandsbehaftet (Gegner-Modell wird ueber `observe_hand_end` gefuettert). Kein
globaler Zustand im Modul.

**Kosten.** Nicht gemessen. Das Skript druckt alle 20 Haende ms/Hand (`:288-291`); der Netzwerk-Roundtrip ist ein
`_post` je Entscheidung mit 30 s Timeout und bis zu 4 Versuchen (`:26-38`). Kein API-Key, keine Kosten.

**Mess-Status.** GEMESSEN, aber **widerspruechlich und varianzdominiert** — genau das ist die Lehre:
- `−39,6 ± 30,9 bb/100` (Exploit-primaer, n=2500, `docs/STATE.md:1478`); dort ausdruecklich: „das historische
  **+31** hat NICHT reproduziert".
- `+31 bb/100` (fruehere MVP-Messung, `docs/STATE.md:1652`).
- `≈ −5 bb/100` ueber 500 Haende (`docs/STATE.md:1791`).
- `−46` nach dem Anti-Spew-Fix, vorher `−526` (`docs/STATE.md:1864`).
Merke: bei ±31 SE sind drei dieser Zahlen miteinander vertraeglich. Slumbot allein traegt kein Verdikt.

**Allein benutzbar?** Ja, und es ist der billigste externe Kanal ueberhaupt: kein Key, kein Konto, keine
Registrierung. Minimal brauchst du `build_state` + `decision_to_incr` + die `play_hand`-Schleife und einen Bot mit
`.decide`.

**Fallstricke.** Die Button-Bestimmung. `button = client_pos if first_action == "" else 1 - client_pos`
(`:168`) — der Button wird daraus abgeleitet, ob beim ersten Response schon eine Aktion passiert ist. Wer das
falsch macht, baut praeflop die Blinds verkehrt herum ein und misst systematisch einen anderen Bot (denselben
Fehler haben wir im GTOW-Adapter tatsaechlich gemacht, siehe oben). Zweiter Punkt: `b<to>` ist ein KUMULATIVER
Strassen-Einsatz, kein Inkrement — trotz des Feldnamens `incr` in der API.

---

### All-in-EV-Korrektur fuer Slumbot-Laeufe — `pokerbot/benchmark/slumbot_adjust.py`

**Zweck.** Ersetzt in einem geloggten Slumbot-Lauf das realisierte Ergebnis aller **vor dem River** all-in
gegangenen Poette durch die Equity-EV der beiden bekannten Haende — Varianz-Reduktion ohne AIVAT.

**Schnittstelle.** `analyze(path: str, iters: int = 20000) -> dict` (`:130`) — liest die JSONL, gibt roh und
korrigiert zurueck; `_reconstruct(action, button) -> dict` (`:37`), `_adjusted_net(row, iters) -> (float, bool)`
(`:87`), `_bb100(nets) -> (bb100, stderr)` (`:117`).

**Eingabe/Ausgabe.** Rein: die JSONL aus `play_hand_verbose` (Felder `hole_cards`, `board`, `bot_hole_cards`,
`action`, `winnings`, `won_pot`, `client_pos`, `button`). Raus: ein dict mit ROH- und ADJUSTED-bb/100, je mit
Standardfehler.

**Abhaengigkeiten.** Die Chip-Rekonstruktion spiegelt `slumbot.build_state` (Blinds 50/100, Stacks 20000) —
weiche Kopplung, aber ein Auseinanderlaufen bricht die Zahlen still. Equity kommt aus unserem Engine-Modul.

**Zustand.** Zustandslos (reiner Datei-Auswerter).

**Kosten.** Ein Monte-Carlo mit `iters` (Default 20.000) je korrigierter Hand. Nicht gemessen.

**Mess-Status.** UNGEMESSEN als eigener Effekt (kein bb/100-Vergleich „roh vs korrigiert" mit Quelle gefunden).
Die Voraussetzung ist verifiziert: Slumbot liefert `bot_hole_cards` nur am Showdown (Modul-Docstring
`slumbot.py:213-216`, „verified 2026-06-18"), und die Chip-Rekonstruktion wurde „cross-validated to the chip"
(`docs/STATE.md:1178`).

**Allein benutzbar?** Ja, wenn deine Hand-Logs dieselben Felder tragen. Die Idee ist portabel: nur Poette
korrigieren, die VOR dem River all-in gingen — nach dem River ist das Ergebnis deterministisch und eine
„Korrektur" fuegt nur Fehler hinzu.

**Fallstricke.** Die All-in-Strasse wird daran erkannt, dass die kumulierte Einzahlung eines Spielers 20000 trifft
— an anderen Stacktiefen oder Blinds ist das Modul stumm falsch.

---

### Slumbot mit LLM-Gehirn — `pokerbot/benchmark/slumbot_llm.py`

**Zweck.** Laesst ein LLM (oder ein Solver-Bot, oder eine Kontroll-Baseline) statt der Engine gegen Slumbot
spielen — dieselbe Client-Schleife, anderer Entscheider.

**Schnittstelle.** `spot_from_slumbot(st: dict) -> Spot` (`:51`); `class VLLMBackend(url, model,
max_new_tokens=None)` (`:72`); `class _LLMBot` / `class AllCallBot` / `class SolverSlumbotBot(seed=0,
sample_log=None)` (`:124`/`:142`/`:184`) — alle drei duck-typed wie ein Bot (`.decide(st)`, `.hero_idx`);
`class Counters` (`:106`, zaehlt `frac_bad`); `class ProgressLog(path, t0, counters)` (`:288`);
`_run_stream(...)` (`:340`) fuer parallele Slumbot-Sitzungen.

**Eingabe/Ausgabe.** Rein: derselbe Slumbot-Zustand wie oben, uebersetzt in unser kanonisches `Spot`-Format.
Raus: bb/100 ± Standardfehler plus `frac_bad` (Anteil ungueltiger/nicht ausfuehrbarer LLM-Programme) und eine
Fortschritts-JSONL.

**Abhaengigkeiten.** Hart: `pokerbot.benchmark.slumbot` (die Schleife wird wiederverwendet, nicht geforkt),
`pokerbot.brain.*` (Spot-Format, Executor), fuer den lokalen Pfad `transformers`, fuer den schnellen Pfad ein
laufender vLLM-Server.

**Zustand.** Je Stream eine Slumbot-Sitzung (Token). Mit `--concurrency K` laufen K unabhaengige Spiele in einem
ThreadPool gegen denselben vLLM-Server.

**Kosten.** `transformers`-Pfad: **~28 s/Hand sequentiell** (Modul-Docstring `:10`), an anderer Stelle
~29 s/Hand gemessen (`docs/STATE.md:1331`). vLLM-Pfad in einem GTOW-Lauf: 1,27 s/Hand nach dem Kaltstart
(`docs/STATE.md:1159`, dort GTOW statt Slumbot).

**Mess-Status.** GEMESSEN: das SFT-1.7B-Gehirn erreichte **−72,0 bb/100 bei frac_bad 0,03 (n=100)**
(`docs/STATE.md:1281-1283`). Ein Solver-Lauf ueber 299 Haende ergab roh −106 und wurde als verrauscht verworfen
(`docs/STATE.md:1176`).

**Allein benutzbar?** Nur mit dem halben Projekt (Brain-Schicht + Executor). Was du wirklich mitnehmen solltest,
ist `--baseline allcall`: eine modellfreie Immer-Check/Call-Baseline, die deutlich NEGATIV sein MUSS. Wenn sie
das nicht ist, luegt dein Harness — das ist die billigste Selbstbetrugs-Kontrolle im ganzen Repo.

**Fallstricke.** `frac_bad` ist die Zahl, die dich rettet: ein LLM-Lauf mit hohem Anteil ungueltiger Programme
misst deinen Fallback, nicht dein Modell. Historisch stand `frac_bad` einmal bei 1,0 wegen eines
SIGALRM-in-Worker-Thread-Bugs (`CLAUDE.md`, Block GLM) — das Modell sah tot aus und war es nicht.

---

### Slumbot adaptiv — `pokerbot/benchmark/slumbot_adaptive.py`

**Zweck.** Spielt den `AdaptiveExploiter` live gegen Slumbot und laesst ihn dabei online dessen Fold-Kurve
lernen.

**Schnittstelle.** `walk_decisions(action: str, button: int)` (`:18`) — laeuft den Aktions-String ab und liefert
die Gegner-Entscheidungspunkte, damit das Gegner-Modell sie beobachten kann; dazu ein `main()` mit `--hands`,
`--iters`.

**Eingabe/Ausgabe.** Wie `slumbot.py` (es importiert dessen Client als `S`), zusaetzlich wird jede beobachtete
Gegneraktion ins Modell gebucht. Raus: bb/100.

**Abhaengigkeiten.** Hart auf `pokerbot.benchmark.slumbot` und `pokerbot.strategy.adaptive`.

**Zustand.** Je Sitzung: die gelernte Fold-Kurve waechst ueber Haende hinweg. Fuer einen sauberen A/B muss sie
zurueckgesetzt werden — sonst misst Lauf 2 ein anderes Modell als Lauf 1.

**Kosten.** Nicht gemessen.

**Mess-Status.** **REFUTIERT als Bot-Pfad.** Der `AdaptiveExploiter` selbst ist gemessen schwaecher als
`PokerBot`: „adaptive's BASE decide() is weaker than PokerBot's (−56 with all exploit knobs OFF), NOT a
mis-tuned gate" (`docs/STATE.md:1795-1797`). Der Dirichlet-River-Exploit wurde spaeter unabhaengig refutiert (ON
vs OFF, 600 gepaarte Decks, alle 8 Diffs ≤ 0, gepoolt ≈ −12 bb/100; `docs/STATE.md`, Block „Exploit-Gate",
Journal `EXPLOIT-GATE-VERDIKT`).

**Allein benutzbar?** Nur als Beispiel dafuer, wie man Gegneraktionen aus einem Aktions-String rekonstruiert.

**Fallstricke.** Online-Lernen und Messen beissen sich: der Bot in Hand 400 ist nicht der Bot aus Hand 1, die
bb/100 ist also ein Mittel ueber eine driftende Politik.

---

### Claude als Spieler vs Slumbot — `pokerbot/benchmark/claude_vs_slumbot.py`

**Zweck.** Experiment: ein Frontier-LLM entscheidet, bekommt dabei aber ALLE strukturierten Signale, die unsere
Engine fuer den Spot berechnet — schlaegt Reasoning ueber unseren eigenen Signalen unsere eigene Entscheidung?

**Schnittstelle.** `class ClaudePlayer` — Drop-in fuer `slumbot.play_hand` (`.decide(state) -> {action, amount}`,
`.hero_idx`, `.observe_hand_end`). Ablauf laut Docstring: interner `PokerBot(exploit=True)` erzeugt die
`rationale`, die wird in den Prompt formatiert, das Modell antwortet, Antwort wird geparst und legalisiert,
alles wird geloggt.

**Eingabe/Ausgabe.** Rein: Slumbot-Zustand. Raus: bb/100 plus ein Per-Entscheidung-Log (Engine-Aktion vs
Claude-Aktion vs Begruendung).

**Abhaengigkeiten.** `pokerbot.benchmark.slumbot`, `pokerbot.strategy.bot`, `research/llm.py` (API-Aufruf),
API-Key.

**Zustand.** Je Sitzung (der interne Bot lernt mit).

**Kosten.** Nicht gemessen; ein API-Aufruf je Entscheidung, also mehrere je Hand.

**Mess-Status.** UNGEMESSEN als bb/100 — der Docstring sagt es selbst: „raw bb/100 vs Slumbot is
variance-dominated at small n (the point is CAPABILITY + DATA, not a precise number)" (`:12`). Der verwandte
Claude-Lauf gegen GTOW ist gemessen (−28,55 AIVAT, `CLAUDE.md`, Block CURRENT BRAIN), aber das ist ein anderes
Modul.

**Allein benutzbar?** Nur mit unserer Engine — der ganze Sinn ist, dass das LLM UNSERE Analyse serviert bekommt.

**Fallstricke.** Klare Projekt-Regel dazu: „this is an LLM-as-player EVAL, never a training label for the GTO
core" (`:14`). Wer die Ausgaben als Trainingsdaten nimmt, importiert die Fehler des Lehrers.

---

### LBR (Local Best Response) — `pokerbot/benchmark/lbr.py`

**Zweck.** Schaetzt eine UNTERE Schranke der Exploitierbarkeit, indem ein Gegner an jedem Knoten lokal die
EV-beste Aktion waehlt (EV per Monte-Carlo-Rollout) und danach passiv weiterspielt.

**Schnittstelle.**
- `lbr_bb100(make_bot, hands=120, K=8, start=10000, sb=50, bb=100, seed=7, iters=80) -> (mean, se, net_list)`
  (`:121`) — die einzige Funktion, die du brauchst; `make_bot(seat)` ist eine Fabrik.
- `_candidates(game, la)` (`:66`) — LBRs lokale Aktionsmenge: check/call/fold + ~2/3-Pot + All-in.
- `_rollout_ev(game, lbr_idx, action, amount, rollout_bot, K, rng)` (`:84`) — mittlerer Chip-Gewinn ueber K
  Rollouts mit **neu gezogenen** Bot-Karten.
- `class _NitBot` (`:28`) — Immer-Check/Fold-Ziel als Mechanik-Test: LBR MUSS ihn zerlegen.

**Eingabe/Ausgabe.** Rein: eine Bot-Fabrik. Raus: `(mean, se, net)` — LBRs Gewinnrate in Chips je Hand
(`bb = 100`), also „so viel verliert der Bot mindestens gegen einen lokalen Best-Responder".

**Abhaengigkeiten.** Hart: `pokerbot.engine.game.HeadsUpGame` (LBR braucht eine Engine, die sich
`copy.deepcopy`-en und weiterspielen laesst) und `pokerbot.engine.cards.make_deck`. Der gemessene Bot ist
duck-typed.

**Zustand.** Zustandslos zwischen Aufrufen; INNERHALB eines Laufs wird pro Hand neu geseedet
(`g.rng = random.Random(f"deck-{seed}-{_hi}")`, `:132-133`), damit Hand *i* ueber verschiedene Bot-Versionen
identische Karten und identische Rollout-Zufaelligkeit sieht — das macht den Lauf gepaart.

**Kosten.** Nicht gemessen. Struktur: `hands × Entscheidungen × |Kandidaten| × K` volle
`copy.deepcopy`-Rollouts. Das ist der teuerste Kanal im Verzeichnis; die Default-Werte (120 Haende, K=8,
`iters=80`) sind bereits Sparversionen.

**Mess-Status.** **REFUTIERT als absolutes Gate — das ist die wichtigste Einzelinformation dieses Kapitels.**
`lbr_falsify.py` hat ueber 300 gepaarte Haende gezeigt (`NOTES.md:598-608`):
- **Range-blind:** injizierte C-Bet-Air- und River-Overbluff-Leaks ergaben gepaarte Deltas von **+123 / −31
  bb/100 (≈ 0)**, obwohl sie in 99 bzw. 95 von 300 Haenden feuerten — die uniforme Kartenziehung kann eine
  korrumpierte RANGE nicht sehen.
- **Unter-exploitet:** selbst ein EXTREMER Overfolder bringt nur **+289 ± 175** (fold-any-bet) bzw. **+323 ± 175**
  (overfold-50) — richtige Richtung, aber keine 3σ bei 300 Haenden.
- Sauberer Bot: **+141 ± 298** = Rauschen.
Frueher, unabhaengig: „LBR v1 too loose to score the floor (loses −987 to it; nit-sanity +75 OK)"
(`docs/STATE.md:1798`). Die Mechanik funktioniert (Nit-Test), die Aussagekraft nicht.

**Allein benutzbar?** Ja, wenn deine Engine tief kopierbar und aus einem beliebigen Zustand weiterspielbar ist.
Genau das ist die Anforderung, die die meisten Engines nicht erfuellen.

**Fallstricke.** Der eine Punkt: **glaube der Zahl nicht.** LBR v1 mit uniformer Kartenziehung misst nur
Fold-/Bet-ANTWORTEN, nie die Range-Zusammensetzung. Wer daraus „unser Bot ist wenig exploitierbar" liest, hat
sich selbst betrogen. Die dokumentierte Reparatur (LBR v2: Bayes-konsistente, aktionsabhaengige Range +
mehrstrassiger Best-Response) ist im Repo **nicht gebaut** (`NOTES.md:608`).

---

### LBR-Falsifikation — `pokerbot/benchmark/lbr_falsify.py`

**Zweck.** Prueft den LBR selbst: injiziert BEKANNTE Leaks in den eingefrorenen Bot und misst, ob der LBR sie
findet.

**Schnittstelle.** `class LeakyBot(seat, spec="clean", seed=0)` (`:21`) — wickelt einen `PokerBot` und
korrumpiert genau eine Entscheidung; `SPECS` (`:69`) listet die sechs Arme: `nit_ref`, `clean`, `fold_any_bet`,
`overfold_50` (Fold-Antwort, kartenunabhaengig) und `cbet_air`, `overbluff_river` (Range-Zusammensetzung).

**Eingabe/Ausgabe.** Rein: nichts (baut sich seine Bots selbst). Raus: je Arm die LBR-Gewinnrate, verglichen mit
`clean`.

**Abhaengigkeiten.** `pokerbot.benchmark.lbr` (`lbr_bb100`, `_NitBot`), `pokerbot.strategy.bot.PokerBot`.

**Zustand.** Der Wrapper hat einen eigenen RNG (`seed + 99`) fuer die probabilistischen Leaks.

**Kosten.** Sechs volle LBR-Laeufe. Nicht gemessen, aber das Sechsfache des teuersten Kanals.

**Mess-Status.** GEMESSEN — und das Ergebnis ist ein NEGATIVBEFUND ueber das Instrument, nicht ueber den Bot:
siehe die Zahlen unter `lbr.py` (`NOTES.md:598-608`). Nutzbares Nebenprodukt derselben Arbeit: `lbr_bb100` seedet
seither pro Hand neu und ist damit ein gepaarter A/B-Kanal (`NOTES.md:605-607`).

**Allein benutzbar?** Ja, konzeptionell: das ist die Vorlage fuer „falsifiziere dein Messinstrument, bevor du
ihm glaubst". Uebertragbar auf jedes Exploitierbarkeits-Mass.

**Fallstricke.** Ein Leak muss oft genug FEUERN, sonst misst du nichts — deshalb protokolliert das Modul, in wie
vielen der 300 Haende der injizierte Leak ueberhaupt griff. Ohne diesen Zaehler haette „Delta ≈ 0" auch „Leak
feuerte nie" heissen koennen.

---

### Kaggle Game Arena — `pokerbot/benchmark/kaggle_arena.py`

**Zweck.** Steckt unseren Bot in die OPEN-SOURCE-Umgebung des Kaggle-Leaderboards „Heads Up Poker"
(`python_repeated_pokerkit` ueber OpenSpiel) und misst gepaart auf identischen Decks mit Sitztausch.

**Schnittstelle.**
- `spiel(stack_einheiten=200)` (`:68`) — laedt das Spiel; der Spielstring wird aus `kaggle_environments`
  IMPORTIERT (nicht abgeschrieben), damit eine Aenderung dort auffaellt.
- `parse_beobachtung(obs: str) -> dict` (`:98`) — die `observation_string` des Wrappers -> `{strasse, bets,
  stacks, start, board, hole, pot_gesamt}`.
- `zustand(state, spieler, historie, hand_id) -> dict` (`:130`) — OpenSpiel-Zustand -> unser Engine-Zustand
  (Held IMMER Index 0, Einheiten × 50 = Chips).
- `spiel_aktion(entscheidung, state, spieler) -> int` (`:177`) — `{action, amount}` -> OpenSpiel-Aktion
  (`0` Fold, `1` Check/Call, `N` Bet/Raise **TO** N Einheiten), mit Legalitaets-Garantie.
- `spiele_hand(agenten, deck_seed, hand_id, stack_einheiten=200) -> float` (`:244`) — eine Hand, Netto von Sitz 0.
- `duell(a_fabrik, b_fabrik, decks, seed0=90000, stack_einheiten=200) -> dict` (`:303`) — der gepaarte Kanal.
- Agenten: `PrinceAgent(stack="final", seed=7, kanal="gym")` (`:196`), `BasisAgent` (`:223`), `RufAgent`
  (`:230`, Call-Station, nur Verdrahtungs-Smoke).
- `instrumentiere_plan()` (`:43`) — haengt (idempotent) Zaehler an den River-Plan, ohne eine Entscheidung zu
  aendern.

**Eingabe/Ausgabe.** Rein: Agenten-Fabriken + Deck-Anzahl. Raus: ein Statistik-dict mit `bb100`, `se`, `trim`,
`median`, `nonzero`, Bootstrap-CI, `verdict` (aus `stats.verdikt`), dazu `plan` (Aktivierungen/gespielt/Fallbacks)
und `basisrate` (u. a. `planfaehig_je_100_haende`).

**Abhaengigkeiten.** Extern hart: `open_spiel` (`pyspiel`) und `kaggle-environments` — `pip install open_spiel
kaggle-environments`, fuer Python 3.12 gibt es ein Windows-Wheel (`docs/KAGGLE_ARENA.md`, Abschnitt Kommandos).
Intern: `pokerbot.autogym.stats` (Verdikt), `pokerbot.strategy.auslese` + `pokerbot.strategy.bot` (nur fuer
`PrinceAgent`). Parser, Zustands-Adapter und Aktions-Mapping haengen an nichts davon.

**Zustand.** Kritisch und gemessen: `duell` erzeugt **je Spiegelhaelfte FRISCHE Agenten-Instanzen** (`:315-317`),
weil unser Bot aus einem fortlaufenden RNG-Strom mischt. Die `hand_id` ist **je Deck identisch**, nicht je
Haelfte (`:325-327`). Modulglobale Zaehler `_ZAEHLER` und `_PLAN` werden zu Beginn jedes `duell` genullt.

**Kosten.** Gemessen: **300 gepaarte Decks (= 600 Haende) in 3.153 s auf einem Kern ≈ 10,5 s/Deck**
(`docs/KAGGLE_ARENA.md`, Tabelle „Erster Referenzwert"). Der Doku-Vergleich nennt 0,3–18 s/Hand je nach
Resolver, parallelisierbar. Kosten je Hand: 0 (laeuft lokal).

**Mess-Status.** Der Kanal ist kalibriert, das erste Verdikt ist **NEUTRAL**: `prince[final]` vs `prince[basis]`,
300 gepaarte Decks: roher Mittelwert **+55,8 bb/100, SE 38,0**, 5 %-getrimmt +6,3, Median 0,0, abweichende Decks
97/300 (32,3 %), davon 45 positiv (Vorzeichen-z −0,71), Bootstrap-CI [−16,7, +134,6], `perm_p` 0,076
(`docs/KAGGLE_ARENA.md`, Journal `KAGGLE-REFERENZWERT`). **A/A exakt 0** nach zwei behobenen Mess-Fallen
(`hand_id` je Haelfte; RNG-Strom ueber Haende — A/A stand vorher bei **−37,5** bei 8 Decks). Preisliste des
Kanals, aus derselben Quelle: fuer SE ≈ 4 braeuchte man ~27.000 Decks ≈ 75 h auf einem Kern.

**Allein benutzbar?** Ja — das ist der am leichtesten uebernehmbare Adapter im Kapitel: `parse_beobachtung`,
`zustand` und `spiel_aktion` sind drei reine Funktionen, du brauchst nur die zwei Pakete und einen Bot mit
`.decide`. `duell` braucht zusaetzlich unser `stats`-Modul; ein eigenes Mittel-mit-SE tut es auch.

**Fallstricke.** **Die Stacktiefe.** Kaggle spielt 200 Einheiten = **100 bb**, der GTOW-Wettbewerb 200 bb — und
unser Praeflop-Blueprint feuert erst ab 140 bb effektiv (`pokerbot/strategy/bot.py:200`). Bei `--stack-bb 100`
misst du also einen ANDEREN Bot (Heuristik-Kaskade statt near-Nash-Blueprint) als im Wettbewerbskanal
(`docs/KAGGLE_ARENA.md`, „KORREKTUR"). Zweiter Punkt, ausdruecklich bindend im Projekt: **der Kanal ist KEIN
GTO-Anker.** Das offizielle Feld sind LLMs, kein Re-Solver; ein Sieg hier schlaegt LLMs, nicht den Solver. Der
Versuch, Kaggle-BB/100 auf GTOW-AIVAT zu eichen, ist gemessen gescheitert (6 gemeinsame Modelle, **r = 0,37,
R² = 0,14, Residual-SD 15,5**; nur nach Streichen von Grok 4 r = 0,88 — das waere Kurvenanpassung,
`docs/KAGGLE_ARENA.md`, Abschnitt „Eichung").

---

### LLM-Gegner in unserer Engine — `pokerbot/benchmark/llm_opponent.py`

**Zweck.** Setzt einen Frontier-LLM-Agenten als GEGNER in unsere eigene HU-Engine (200 bb), um im
Leaderboard-Stil gegen ein LLM zu spielen.

**Schnittstelle.** `llm_opponent(model: str, seat: int = 1, naive: bool = False)` (`:91`) — gibt eine
`decide(st)`-Funktion zurueck; intern `_prompt(st, seat, naive)` (`:38`), `_parse(text)` (`:81`),
`_legalize(st, seat, action, frac)` (`:66`).

**Eingabe/Ausgabe.** Rein: unser Engine-Zustand. Raus: eine legale Aktion. Zwei Prompt-Modi: `--naive` (eine
Zeile, JSON-only, **schwache Baseline — Gewinnrate nicht vertrauen**) und der Default (reicher Zustand mit
Pot-Odds/SPR/Position/History, Chain-of-Thought, `reasoning_effort=high` bei gpt-5.x).

**Abhaengigkeiten.** `research/llm.py` + API-Key; unsere Engine als Spielfeld.

**Zustand.** Zustandslos je Entscheidung (kein Gedaechtnis ueber Haende).

**Kosten.** Nicht gemessen; ein API-Aufruf je Entscheidung.

**Mess-Status.** UNGEMESSEN, und das Modul sagt selbst warum: „Raw bb/100 over a modest sample is
NOISE-dominated (HU variance ~±200 bb/100 over 100 hands) — directional only" (`:11-12`).

**Allein benutzbar?** Ja, wenn du einen LLM-Zugang hast — der Prompt-Bauer ist die eigentliche Arbeit und haengt
nur am Zustands-dict.

**Fallstricke.** Der `--naive`-Modus existiert als Kontrollgruppe, nicht als Gegner. Wer ihn versehentlich als
„das LLM" misst, hat einen Strohmann geschlagen.

---

### GTO-Oracle-Match (lokaler GTOW-Ersatz) — `pokerbot/benchmark/gto_oracle_match.py`

**Zweck.** Head-to-head bb/100 gegen einen Gegner, der postflop bei JEDER Entscheidung live TexasSolver
befragt und aus dessen GTO-Mix zieht — der lokale Ersatz, wenn kein GTOW-Zugang da ist.

**Schnittstelle.** `class GTOOracleAgent(seat, seed=0, acc=_ACC, iters=_ITERS)` (`:73`) mit `.decide(st)`;
`run_paired(hero, oracle, decks, start=4000, sb=50, bb=100)` (`:190`) — gepaarter Lauf; `_match_label(action,
amount, committed, node)` (`:46`) bildet unsere Aktion auf einen Baum-Ast ab.

**Eingabe/Ausgabe.** Rein: zwei Agenten + Deck-Anzahl. Raus: bb/100 mit Standardfehler. Beide Spieler werden aus
den SRP-Ranges ausgeteilt, damit die Solve-Ranges konsistent sind.

**Abhaengigkeiten.** Hart: `pokerbot.strategy.gto_oracle` und damit **TexasSolver als externes Binary** (liegt
unter `tools/` — gitignored).

**Zustand.** Je Hand; der Oracle-Agent faellt auf den Bot-Floor zurueck, wenn der Spot nicht loesbar ist oder die
Hand nicht in der Range liegt.

**Kosten.** Pro Entscheidung ein Live-Solve — der Docstring nennt das ausdruecklich als Grund fuer kleine
Stichproben (`:7`). An anderer Stelle im Projekt gemessen: `solve_node` ~76 s (`docs/STATE.md:1113`), allerdings
in einer anderen Konfiguration.

**Mess-Status.** UNGEMESSEN als Headline-Zahl in der aktuellen Aera. Der Docstring listet drei ehrliche
Einschraenkungen selbst: kleine Stichproben, Ranges ohne exakte Fortsetzungs-Propagation (also nur APPROXIMATIV
near-GTO), und eine feste Bet-Size-Abstraktion, in der unser Off-Tree-Vorteil unsichtbar bleibt.

**Allein benutzbar?** Nur mit TexasSolver und unserer Oracle-Schicht. Wer beides hat, bekommt einen
$0-GTO-Gegner.

**Fallstricke.** Ein statischer Solve hat eine feste Sizing-Abstraktion — dieser Kanal kann per Konstruktion
NICHT messen, ob dein Bot Off-Tree-Groessen gut ausnutzt. Er misst „Verlust gegen GTO", nicht „Gewinn gegen einen
Solver mit Baum".

---

### Pluribus-Entscheidungsabgleich — `pokerbot/benchmark/pluribus_bench.py`

**Zweck.** Spielt die 10.000 Pluribus-Hand-Historien nach, rekonstruiert jede Entscheidungssituation und misst,
wie oft unser 6-max-Bot dieselbe Aktionskategorie waehlt wie Pluribus.

**Schnittstelle.** `replay(path)` (`:51`) — eine PHH-Datei -> Entscheidungsknoten; `cat_actual(verb, to_call)`
(`:33`) und `cat_bot(action)` (`:41`) — Abbildung auf die vier Kategorien aggressiv/call/check/fold;
`decide_with(obs) -> dict` (`:221`); `main()` mit `--max-hands`, `--iters`.

**Eingabe/Ausgabe.** Rein: PHH-TOML-Dateien aus `data/_phh_repo/data/pluribus` (`:26`). Raus: Uebereinstimmungs-
quote gesamt, je Strasse, je Position, plus eine Konfusions-Aufschluesselung — und als Nebenprodukt
`data/training/pluribus_decisions.jsonl` (Beobachtung -> Aktion) fuer Imitationslernen (`:27`).

**Abhaengigkeiten.** Hart: die PHH-Daten (`data/` ist gitignored — du musst sie selbst von uoftcprg/phh-dataset
holen) und unser 6-max-Entscheider.

**Zustand.** Zustandslos je Hand (reiner Replay).

**Kosten.** Als CPU-intensiv gefuehrt („CPU-LIVE", `docs/archive/BOT_PARTS_CATALOG.md:125`), sonst nicht
gemessen. Die MC-Equity-Iterationen sind ueber `--iters` regelbar.

**Mess-Status.** UNGEMESSEN in dieser Datei. Die gemessene Zahl gehoert zum NEUEREN Nachfolger
`research/pluribus_match.py`: **76,6 % Bucket-Uebereinstimmung ueber 15.169 Entscheidungen** (preflop 82,4 %,
Flop 65,6 / Turn 63,5 / River 61,9; `docs/STATE.md:560`). Wichtige Einordnung von dort: Pluribus ist NICHT
GTO-Grundwahrheit (im Datensatz roh −7,09 bb/100 gegen Profis), und **beide Seiten MISCHEN** — identische
60/40-Mixe ergaeben rein rechnerisch ~52 % Uebereinstimmung, 76,6 % ist also eine Untergrenze.

**Allein benutzbar?** Ja, wenn du die PHH-Daten hast und dein Bot ein 6-max-`decide` anbietet. Das
Abgleich-Muster ist die eigentliche Uebertragung, nicht der Code.

**Fallstricke.** Entscheidungs-Uebereinstimmung ist KEINE Staerkemessung. Ein Bot, der einen mischenden Gegner
zu 100 % imitiert, waere schlechter als der Gegner — und der Mixing-Floor (siehe oben) macht jede Quote unter
100 % mehrdeutig.

---

### PHH-Leak-Querschnitt — `pokerbot/benchmark/phh_leaks.py`

**Zweck.** Prueft ueber vier verschiedene Hand-Historien-Quellen hinweg, ob „foldet zu viel gegen kleine/
Pot-grosse Postflop-Bets" ein Pluribus-Spezifikum oder eine allgemeine Schwaeche ist.

**Schnittstelle.** `parse_file(path)` (`:35`), `replay_hand(d)` (`:46`), `collect(paths, target=None)` (`:97`),
`agg(stats, hu, streets, buckets)` (`:121`), `report(label, hands, dec, stats)` (`:133`). Groessen-Buckets:
`small` <0,45 Pot, `med` 0,45–0,8, `pot` 0,8–1,3, `over` >1,3 (`BUCKETS`, `:23`).

**Eingabe/Ausgabe.** Rein: PHH-Dateien aus `data/_phh_repo/data` (`:22`) — Quellen `pluribus`, `wsop`, `famous`,
`handhq`. Raus: Fold-Haeufigkeit je Strasse und Groessen-Bucket, verglichen mit `alpha = to_call / pot` (die
maximal unexploitierbare Fold-Frequenz heads-up postflop); `fold% > alpha` = ausbeutbares Over-Fold.

**Abhaengigkeiten.** Nur `tomllib`, `glob` und die Daten — **das Modul braucht keine Karten und keinen Bot**, es
liest nur Aktionen und Groessen. Damit funktioniert es auch bei verdeckten Hole-Karten (`"????"`).

**Zustand.** Zustandslos.

**Kosten.** Reines Parsen, nicht gemessen; kein Solver, keine Equity.

**Mess-Status.** UNGEMESSEN — in `docs/` liess sich kein Ergebnis dieses Laufs mit Quelle finden. Der
zugrundeliegende Pluribus-Fold-Leak ist an anderer Stelle als Exploit-Projektion gefuehrt (~+4 bb/100,
`docs/archive/META_STRATEGY.md:36`), aber das ist `pluribus_leaks.py`, nicht dieses Modul.

**Allein benutzbar?** Ja, das ist das autarkste Modul des Kapitels: PHH-Dateien rein, Fold-Statistik raus. Kein
Projekt-Code noetig ausser `config.ROOT`.

**Fallstricke.** `alpha = to_call/pot` ist die HU-Schranke. In Multiway-Poetten ist sie nicht die richtige
Referenz, und die Quellen `wsop`/`famous`/`handhq` sind ueberwiegend nicht heads-up — die Aggregation muss
danach filtern (der Parameter `hu` in `agg`), sonst vergleicht man gegen die falsche Schranke.

---

### Scorecard-Aggregator — `pokerbot/benchmark/scorecard.py`

**Zweck.** Faehrt alle schluesselfreien Messachsen nacheinander und schreibt EINE JSON plus eine lesbare
Zusammenfassung, getrennt nach „Verlust gegen near-GTO" und „Edge gegen das Feld".

**Schnittstelle.** `axis_gto_gap(limit)` (`:48`), `axis_duplicate(decks_n)` (`:62`), `axis_internal(hands)`
(`:78`), `axis_field(hands)` (`:88`), `axis_exploit_proof(hands)` (`:105`), `axis_slumbot(hands,
exploit_primary)` (`:119`); `main()` mit `--quick` / `--full` / `--hands` / `--iters`; `_se(net)` und `_noise(n)`
(`:30`/`:34`) liefern Standardfehler und die HUNL-Rauschschwelle.

**Eingabe/Ausgabe.** Rein: Flags. Raus: ein dict/JSON mit `timestamp`, `git_sha`, `agent`, `config`, `axes` und
`errors`. **Nach JEDER Achse wird die (Teil-)Datei geschrieben** (`:174`), ein Absturz verliert also nichts; eine
fehlgeschlagene Achse landet als Eintrag in `errors` statt den Lauf zu killen.

**Abhaengigkeiten.** Praktisch das ganze Verzeichnis (`duplicate`, `internal`, `floor_map`, `exploit_proof`,
`slumbot`) plus die Strategie. Nicht portabel.

**Zustand.** Zustandslos; `--full` zieht Netzwerk (Slumbot), `--quick` laeuft offline.

**Kosten.** Nicht als Zahl gemessen. Default `--quick`: 500 Haende je ungepaarter Achse, 250 Decks gepaart, 250
Flop-Boards; `--full`: 1500 / 600 / alle Boards + zwei Slumbot-Laeufe mit je 2×`H` Haenden (`:150-160`).

**Mess-Status.** UNGEMESSEN als Instrument (es aggregiert nur fremde Zahlen).

**Allein benutzbar?** Nein. Nimm die zwei Ideen mit: Teilergebnisse nach jeder Achse persistieren, und jede
ungepaarte bb/100-Zahl NEBEN der Rauschschwelle `~90/sqrt(N/100)` ausgeben (`_noise`, `:34`), damit niemand eine
einzelne Zahl fuer signifikant haelt.

**Fallstricke.** Die Doktrin steht im Docstring und ist die Lehre des Projekts: „A single unpaired number is
NEVER presented as significant" (`:9-10`). Der Aggregator verfuehrt trotzdem dazu, die schoenste Achse zu
zitieren.

---

### Gepaarte Decks (Duplicate/Mirror) — `pokerbot/benchmark/duplicate.py`

**Zweck.** Der interne Standard-Gate: dasselbe Deck wird zweimal gespielt, mit vertauschten Sitzen, sodass das
Kartenglueck sich aufhebt und nur die Politik-Differenz uebrig bleibt. Kein externer Benchmark — aber der
Kanal, gegen den alle externen Zahlen gegengelesen werden.

**Schnittstelle.**
- `gen_decks(n, seed=0)` (`:21`) — n feste Deals `(hole0, hole1, board[5])`.
- `duplicate_ab(make_a, make_b, decks, start=20000, sb=50, bb=100, return_edges=False, hand_id_basis=0)`
  (`:67`) — A's kartenbereinigte Kante ueber B in bb/100 + Standardfehler; mit `return_edges=True` zusaetzlich
  die Deck-Kanten fuer gepaarte Differenzen ueber Konfigurationen hinweg.
- `naive_ab(make_a, make_b, hands, ...)` (`:91`) — dieselbe Messung OHNE Varianz-Reduktion, als Kontrast.
- Fabriken `gto(...)` (`:106`) und `pokerbot(...)` (`:116`).

**Eingabe/Ausgabe.** Rein: zwei Strategie-Fabriken `make(seat) -> decide(state) -> (action, amount)`. Raus:
`(bb100, se)` bzw. `(bb100, se, edges)`; die Umrechnung beruecksichtigt zwei Haende je Deck (`:82-84`).

**Abhaengigkeiten.** `pokerbot.engine.game.HeadsUpGame`, `pokerbot.engine.cards.make_deck`,
`pokerbot.strategy.gto_baseline` (nur fuer die mitgelieferten Fabriken).

**Zustand.** Zustandslos zwischen Aufrufen. **Aber:** die `hand_id` wird in den Zustand injiziert und ist fuer
BEIDE Spiegelhaelften identisch (`:76`), weil der private Zufall der Strategien `f(hand_id, Sitz)` ist. Mit
`2*idx+half` waren gemessen 6/276 Decks ungleich null und Replay-identisch reproduzierbar (Kommentar `:41-48`).
`HAND_ID_STRIDE_JE_DECKSEED = 1_000_000` (`:49`) haelt Bloecke in disjunkten Adressraeumen.

**Kosten.** Nicht gemessen; zwei Haende je Deck ohne Netzwerk.

**Mess-Status.** GEMESSEN POSITIV als Instrument — es ist der Kanal, ueber den die anwendbaren Aenderungen des
Projekts abgenommen wurden, z. B. der 6max-Flat-Fix mit 3 Laeufen a 2992 Decks: **+17,7 ± 6,4 / +11,4 ± 6,9 /
+19,2 ± 7,0 bb/100** (`docs/STATE.md`, Block „6MAX FLAT-FIX"). Der Docstring nennt eine Varianz-Reduktion von
~10–50× gegenueber naivem Matching (`:1-3`); die exakte Zahl ist im `main()`-Selbsttest zu reproduzieren, nicht
in `docs/` mit Zahl belegt.

**Allein benutzbar?** Ja, sobald deine Engine erlaubt, Hole-Karten und Board FEST vorzugeben (`_setup_fixed`,
`:32`). Das ist die einzige echte Anforderung.

**Fallstricke.** **Der A/A-Nulltest.** Setze Kandidat = Amtsinhaber; das Ergebnis muss EXAKT 0 sein. Ist es das
nicht, misst du deinen RNG, nicht deine Strategie — im Projekt gemessen: A/A stand bei −9,4 statt 0 (v10,
`docs/V10_GATES_REPORT.md`) und bei −37,5 statt 0 im Kaggle-Kanal, beide Male wegen Zufalls-Adressierung, nicht
wegen Poker.

---

### Interne Baseline-Gegner — `pokerbot/benchmark/internal.py`

**Zweck.** Schneller, netzwerkfreier Gegencheck gegen simple ausbeutbare Gegner — ein starker Bot MUSS die
zerlegen.

**Schnittstelle.** `run(opp: str, hands: int, start=10000, sb=50, bb=100, seed=1) -> float` (`:49`) — bb/100
gegen einen der drei Gegner; `station(la, rng)` (`:19`), `maniac(la, rng)` (`:28`), `nit(la, rng)` (`:39`).

**Eingabe/Ausgabe.** Rein: Gegnername + Handzahl. Raus: bb/100.

**Abhaengigkeiten.** `pokerbot.engine.game.HeadsUpGame`, `pokerbot.strategy.bot.PokerBot`.

**Zustand.** Zustandslos.

**Kosten.** Nicht gemessen; keine Netzwerk-, keine Solver-Aufrufe.

**Mess-Status.** GEMESSEN POSITIV, aber gegen triviale Gegner: `PokerBot(exploit=ON)` schlaegt alles, schlimmster
Fall +1 bb/100 gegen den starken Peer; station +493, maniac +757, sticky +393, trappy +161
(`docs/STATE.md:1789-1792`, gemessen mit `beat_them_all`-Muster ueber 250 Haende je Paarung).

**Allein benutzbar?** Ja, trivial — drei Funktionen von je ~10 Zeilen. Der Wert liegt in der Rolle: Rauchmelder,
nicht Massband.

**Fallstricke.** Diese Zahlen wachsen mit der Dummheit des Gegners, nicht mit der Staerke deines Bots. „+757
gegen den Maniac" beweist nichts ueber GTO-Naehe; das Projekt hat genau diesen Kontrast dokumentiert (gegen das
Feld +hunderte, gegen GTOW −20).

---

## Was sonst noch im Verzeichnis liegt (nicht Teil dieses Kapitels)

Diese Dateien liegen in `pokerbot/benchmark/`, messen aber gegen INTERNE Gegner oder gegen unseren eigenen
Solver-Cache; sie gehoeren nicht zu „externe Benchmarks" und sind hier nur aufgelistet, damit du beim
Durchsehen des Verzeichnisses nichts fuer verloren haeltst — sie sind NICHT im vollen Katalogformat geprueft:

| Datei | eine Zeile |
|---|---|
| `beat_them_all.py` | Turnier unseres Bots gegen die interne Gegner-Suite (Quelle der +493/+757-Zahlen). |
| `calibrate.py` | Kalibriert das Feld der internen Gegner. |
| `exploit_proof.py` | Gepaarter Nachweis, dass die Exploit-Schicht gegen einen konstruierten Leak Geld druckt. |
| `floor_ablate.py` | Ablation einzelner Floor-Bestandteile, gepaart. |
| `floor_map.py` | GTO-Gap ueber mehrere Strassen/Texturen gegen den Solver-Cache. |
| `gto_benchmark.py` | Bewertet die Baseline gegen den TexasSolver-Cache ueber viele Flops (GTO-Implausibilitaet je Knoten). |
| `pluribus_leaks.py` | Leak-Mining in den Pluribus-Historien (Exploit-Projektion). |
| `preflop_ab.py`, `range_tracker_ab.py`, `sixmax_gap.py` | Kleine, einzweckige A/B-Skripte. |
| `probe.py`, `weaponize.py` | Aeltere Exploit-Sondierungen. |
| `runpod_train.py` | Pod-Anbindung, kein Benchmark. |

Zugehoerige Treiber liegen ausserhalb des Verzeichnisses und sind fuer einen fremden Entwickler ohne unsere
Infrastruktur wertlos: `research/gtow_nacht.py`, `research/gtow_nacht_v10.py` (Nacht-Fahrplan mit
vorregistrierter Arm-Reihenfolge), `research/gtow_ab.py`, `research/gtow_xray.py`, `research/gtow_tail.py`,
`research/analyze_gtow_hands.py`, `tools/gtow_run.py`, `tools/gtow_measure_chunked.py`.

## Was ich nicht klaeren konnte

- **Kosten je Hand** fuer `slumbot.py`, `lbr.py`, `gto_oracle_match.py`, `phh_leaks.py`, `pluribus_bench.py` und
  `scorecard.py` sind im Repo nirgends als Zahl belegt — dort steht „nicht gemessen", nicht geschaetzt.
- **`phh_leaks.py`** hat keinen auffindbaren Ergebnis-Eintrag; das haeufig zitierte „+4 bb/100
  Exploit-Projektion" gehoert zu `pluribus_leaks.py`.
- **Varianz-Reduktion von `duplicate.py`**: der Docstring nennt „~10-50×", eine gemessene Zahl mit Quelle habe
  ich nicht gefunden (der Kontrast-Lauf `naive_ab` existiert, sein Ergebnis ist nicht dokumentiert).
- **Die Slumbot-Zahlen widersprechen sich** (+31 / −5 / −39,6 / −46); ich habe alle vier mit Quelle aufgefuehrt
  statt eine auszuwaehlen. Bei SE ±31 ist keine davon ein Verdikt.

---

## Gegner, Liga, Turnier

Dieses Subsystem liefert **Gegner zum Messen** (eine Liga aus 16 benannten Spielertypen, die alle aus EINER
Entscheidungsfunktion mit unterschiedlichen Knobs entstehen) und **Turnier-Semantik** (ICM, Bubble-Faktor,
Direktor über Level/Antes/Eliminierung/Tischbalance). Wer nur einen Cash-Bot baut, braucht davon genau ein
Stück: die Liga als Sparringpartner für gepaarte A/B-Gates. Wer Turniere spielen will, braucht `icm.py` +
`tournament.py`; alles darüber (`tourney.py`, `mtt.py`) ist Simulations-Infrastruktur, kein Strategie-Code.

---

### 6-max-Liga (Kern + Profile + Online-Gegnermodell) — `pokerbot/arena/sixmax.py`
**Zweck (1 Satz).** Eine positionsbewusste, komplette 6-max-NLHE-Entscheidungsfunktion, die über einen
Knob-Datensatz (`Knobs`) zu 16 verschiedenen Spielertypen parametrisiert wird — Liga-Gegner UND der aktuell
bestgemessene 6-max-Bot des Projekts in einem.

**Schnittstelle.**
- `decide_6max(obs: dict) -> dict` — zustandsloser Aufruf des neutralen `tag`-Profils; kein Gegnermodell.
- `class Knobs` (dataclass, `sixmax.py:39-52`) — `name, open_mult, tb_pct, fb_pct, flat_hi, cont_lo,
  value_eq, raise_eq, bluff_mult, call_delta, flat_guard`. Das ist die gesamte Profil-Sprache.
- `PROFILES: dict[str, Knobs]` (`:55-87`) — `nit, tag, tag_flatfix, lag, station, maniac` (Liga),
  `rock, whale, shark` (Held-out-Typen, gegen die nie trainiert wurde), `sheriff, iso_hammer, value_press,
  trap_nit, blind_fighter` (fünf „Punisher", je gegen ein gemessenes Leak des Haupt-Bots gebaut).
- `PUNISHER_ASSIGN: dict[int, str]` (`:90`) — Sitz→Punisher-Profil für den Straf-Tisch.
- `class SixMaxBot(seat: int, knobs: Knobs, seed: int | None = None)` — ein zustandsbehafteter Sitz.
  - `.new_hand(seats: list[int])` — Handstart, zählt `hands` je Gegner hoch.
  - `.observe(actor: int, street: str, action: str, to_call: int, preflop_raises: int)` — EINE öffentlich
    beobachtete Aktion einfüttern; baut daraus VPIP/PFR/3bet/Fold-vs-Bet/Aggression je Gegnersitz.
  - `.decide(obs: dict) -> dict` — Entscheidung inkl. Exploit-Deltas aus dem eigenen Gegnermodell.
- `class OppModel` — Zähler + drei konfidenz-gegatete Ableitungen: `fold_to_bet()` (ab 8 Beobachtungen),
  `threebet()` (ab 6), `aggression()` (ab 8); darunter `None` → kein Exploit.
- `seed_modul_rng(seed: int | None)` (`:130`) — macht den zustandslosen Pfad (`decide_6max`) reproduzierbar.
- `_dominated_offsuit(hc) -> bool` (`:97`) — der FLAT-FIX-Filter (A2o–A9o/K2o–K9o/Q2o–Q9o/J2o–J8o).

**Eingabe/Ausgabe.** Rein: das `obs`-dict von `pokerbot/engine/table.py::obs_for` (`table.py:340-352`).
Tragende Schlüssel: `hole` (2 Karten als `'As'`-Strings), `board`, `to_call`, `pot`, `my_stack`, `bb`,
`n_active`, `position` (Label `EP/UTG/MP/HJ/CO/BTN/SB/BB`, dazu `UTG+1..+3`/`LJ` für 7–10-max),
`preflop_raises`, `cur_bet`, `my_committed_street`, `street`, `can_check/can_call/can_raise`,
`raise_min/raise_max`. Optional `obs['icm']` (siehe `tournament.py`) — fehlt der Schlüssel, wird die
Turnier-Schicht NIE angefasst (Byte-Identität zum Cash-Verhalten).
Raus: `{"action": "fold"|"check"|"call"|"raise", "amount": int|None, "rationale": {...}}`. `rationale`
trägt `hand` (169er-Klasse), `percentile`, `pos`, `profile`, `eff_bb`, `reasoning` (Klartext) — reine
Diagnose, für das Spiel irrelevant.

**Abhängigkeiten.**
- HART: `pokerbot.engine.cards.hand_class`, `pokerbot.engine.equity.equity_vs_class_range`,
  `pokerbot.engine.evaluator.best_five_name`, `pokerbot.strategy.preflop_strength` (169-Klassen-Perzentil,
  cached in `data/preflop_strength.json`), `pokerbot.strategy.postflop` (`VALUE_EQ`, `BLUFF_EQ`,
  `classify_board`, `cbet_policy`, `pick_value_size`, `PriorFoldModel`).
- ERSETZBAR: `pokerbot.strategy.preflop_gto.rfi` (solver-destillierte RFI-Tabelle; liefert `None` bei
  fehlender Datei → Fallback auf die Perzentil-Heuristik). `pokerbot.strategy.tournament` wird NUR bei
  vorhandenem `obs['icm']` und dann lazy importiert.

**Zustand.** `decide_6max` = zustandslos (bis auf die Modul-RNG `_RNG`, `:127`). `SixMaxBot` = **je Sitzung**:
das `OppModel` je Gegner lebt über Hände hinweg und wird NIE zurückgesetzt; `new_hand()` setzt nur den
Handzustand zurück (`active`, `cur_agg`, `pf_aggressor`, `_street`, `_vpip_done`, `_pfr_done`). Für einen
sauberen A/B-Lauf muss also eine FRISCHE Instanz gebaut werden — sonst trägt der Bot Reads aus dem vorherigen
Block mit.

**Kosten.** Postflop ein Monte-Carlo-Equity-Lauf mit `EQ_ITERS = 400` Iterationen je Entscheidung
(`sixmax.py:36`). Absolute Latenz nicht separat gemessen; als Systemzahl belegt: gepaarter 6-max-Lauf
≈ **2 s pro Deck und Arm single-core** (ein Deck = Hero rotiert über 6 Sitze, `docs/TRAINER_VERDRAHTUNG.md:28`)
und **5 Zehner-Tische je Runde in 120–129 ms mean / 200–213 ms max** im MTT (`docs/TURNIER_MODUS.md:82`).
Speicher: vernachlässigbar (ein `OppModel`-Zähler-Objekt je Gegnersitz).

**Mess-Status.**
- Kern `tag`, extern absolut gegradet: **GEMESSEN POSITIV — GTO-Score 85,9 % / EV-Loss 7,61 bb/100** über
  1781 Moves aus n=1500 Händen (GTO-Wizard-Analyzer, `docs/STATE.md:1059`). Leaks laut derselben Quelle:
  River (22,4 % Mistake+Blunder), Blinds OOP, „als Preflop-Caller" 23,5 % M+B vs 6,6 % als Raiser.
- `flat_guard` (FLAT-FIX): **GEMESSEN POSITIV — 3 Läufe `tag_flatfix` vs `tag`, je 2992 gepaarte Decks:
  +17,7 ± 6,4 (perm_p 0,0035) · +11,36 ± 6,88 (p 0,057, NEUTRAL) · +19,18 ± 7,01 (p 0,0035); gepoolt ≈ +16
  bb/100** — Journal `data/autogym/journal.jsonl`, Eintrag `typ: "FLATFIX-6MAX-VERDIKT"`, 2026-09-09 21:54:18;
  angewendet in `sixmax.py:59`. **Einschränkung, die im Verdikt nicht steht und die ich im Code sehe:** der
  gemessene Arm hieß `tag_flatfix`, und `sixmax.py:170` gattert die solver-destillierte RFI-Tabelle auf
  `k.name == "tag"`. Der Kandidat spielte also seine Opens aus der Perzentil-Heuristik statt aus der
  Solver-Tabelle — die drei Läufe vergleichen `flat_guard` UND „ohne GTO-RFI-Tabelle" gegen das Original,
  während der GESHIPPTE Zustand (`flat_guard=True` auf `tag`) die Tabelle behält. Wer die Zahl übernimmt,
  übernimmt diese Konfundierung mit.
- Online-Reads (`_read`, `:358`): **GEMESSEN NEUTRAL — +3,64 ± 13,45 bb/100, CI [−22,0; +30,9]** (Reads ON vs
  OFF, pargate6; `docs/TRAINER_VERDRAHTUNG.md:85`). Im Turnier-Kontext isoliert sogar **negativ:
  −13,9 ± 10,7 pp ROI** (2×2-Zerlegung, `docs/STATE.md:414-415`).
- A/A-Nulltest der Messkette: `tag` vs `tag`, 288 Decks, **exakt 0,0 ± 0,0** (`docs/TRAINER_VERDRAHTUNG.md:60`).
- Determinismus: `tests/test_sixmax_seed.py` — gleicher Seed ⇒ identische Entscheidungsfolge über 40 Hände.

**Allein benutzbar?** Ja, das ist das am leichtesten herauslösbare Stück des Repos. Minimal nötig:
`pokerbot/engine/` (cards, equity, evaluator, table für `obs_for`), `strategy/preflop_strength.py` (+ dessen
Cache-Datei, sonst rechnet er beim ersten Start Monte-Carlo für 169 Klassen), `strategy/postflop.py`,
`strategy/preflop_gto.py` (optional). Wer nur Gegner will, baut `SixMaxBot(seat, PROFILES["station"])` und
füttert ein `obs`-dict in der obigen Form — die eigene Engine muss dafür nur diese 17 Schlüssel liefern.

**Fallstricke.** Der Bot ist **sitz-indiziert und initiative-abhängig**: `decide()` leitet aus
`self.pf_aggressor == self.seat` ab, ob er C-Bet-Rolle oder Check-to-the-Raiser-Rolle spielt (`:388-390`).
Wer `SixMaxBot`-Instanzen über Hände hinweg wiederverwendet und dabei die Sitzordnung ändert (Busts, Umzüge),
MUSS `bot.seat = i` je Hand neu setzen — sonst kippt die Rollenlogik lautlos ins Gegenteil (genau dieser Fehler
ist in `mtt.py:236` als „mtt_sim-Fund #4" dokumentiert und wird dort in `bots_for()` jede Hand korrigiert).
Zweiter Stolperstein: `observe()` muss von JEDEM Bot für JEDE Aktion aller Sitze aufgerufen werden (Fan-out),
sonst bleiben die Gegnermodelle leer und die Profile spielen ihre statischen Knobs.

---

### HybridHero (tag-Kern multiway + HU-Übernahme) — `pokerbot/arena/hybrid.py`
**Zweck (1 Satz).** Ein Agent, der multiway den `tag`-Liga-Kern spielt und, sobald der Pot auf Hero gegen
genau EINEN Villain zusammengefallen ist, an den Heads-up-Bot (`PrinceOracle`) übergibt.

**Schnittstelle.**
- `class HybridHero(seat=0, stack: str|None=None, seed: int|None=None, prince=None, kanal="gym")`.
  `stack` = Name der AUSLESE-Guard-Kette um den HU-Anteil (`None` = nackter Prince v2.2).
- `.setze_sitz(seat)`, `.bind_table(table)`, `.new_hand(seats)`, `.observe(*args)` — SixMaxBot-kompatibles
  Protokoll, damit eine Arena beide Agenten gleich behandelt.
- `.decide(obs) -> dict` — HU-Pot ⇒ `prince.decide(record)`, sonst `bot.decide(obs)`.
- Zähler: `.prince_decisions`, `.kern_fallbacks`.
- `KERN_PROFIL = "tag"` (`hybrid.py:12`).

**Eingabe/Ausgabe.** Rein: dasselbe `obs`-dict wie `SixMaxBot`, PLUS ein gebundenes `Table`-Objekt
(`bind_table`) — ohne das ist `_heads_up()` nie wahr und der Hybrid ist ein reiner `tag`. Der HU-Pfad baut in
`_record()` (`:51-61`) ein dict mit `spot` (aus `brain.format_spot.spot_from_table`), `obs`, `legal`,
`history`, `street`, `hand_id`, `spot_fp`. Raus: dasselbe Entscheidungs-dict.

**Abhängigkeiten.** HART: `pokerbot.arena.sixmax`, `pokerbot.coach.oracle.PrinceOracle`,
`pokerbot.brain.format_spot`, `pokerbot.coach.decision_log`, ein `pokerbot.engine.table.Table`.
Der Prince-Teil zieht den kompletten HU-Bot (`pokerbot/strategy/bot.py`, ~94 kB) nach — das ist die schwerste
Abhängigkeit in diesem Katalogteil.

**Zustand.** Je Hand über den gekapselten `SixMaxBot` (der wiederum je Sitzung Reads hält — hier allerdings
abgeschaltet: `self.bot._read = lambda obs: {}`, `:26`). `self.table` und `self.hand_id` müssen je Hand neu
gesetzt werden. `prince_decisions`/`kern_fallbacks` laufen über den ganzen Lauf und werden nicht zurückgesetzt.

**Kosten.** Nicht separat gemessen. Der HU-Pfad ist deutlich teurer als der Kern (er fährt den vollen
PokerBot-Stack); im Trainer läuft er deshalb mit Resolver AUS (`docs/TRAINER_VERDRAHTUNG.md:13`).

**Mess-Status.** **REFUTIERT.** pargate6, je 2992 gepaarte Decks gegen den Incumbent `tag`
(`docs/TRAINER_VERDRAHTUNG.md:61-64`, Journal `typ: "VERDRAHTUNG-6MAX-VERDIKT"`, 2026-09-09 19:26:50):
`hybrid` (ohne Kette) **−23,56 ± 9,02**, CI [−40,8; −5,3] → VERWERFEN · `hybrid_r8` **−21,73 ± 9,01**,
CI [−39,0; −4,4] → VERWERFEN · `hybrid_r10` **−26,61 ± 8,93**, CI [−43,9; −9,4] → VERWERFEN ·
`hybrid_r8` vs `hybrid` **+1,82 ± 5,58** → NEUTRAL (die Guard-Kette rettet ihn nicht).
Konsequenz im Produkt: der Takeover ist im 6-max-Trainer **default AUS**, nur `POKERB_SIX_TAKEOVER=1`
schaltet ihn ein (`pokerbot/web/six_server.py:153-158`). Einschränkung des Verdikts, die in der Quelle steht:
Selbst-Ökologie (`tag` spielt gegen seine eigene Liga); der Hybrid wurde nie extern gegradet.

**Allein benutzbar?** Nur als Muster, nicht als Baustein — die 71 Zeilen sind trivial, der Wert steckt in den
beiden Bots dahinter. Wer die Idee „starker HU-Bot übernimmt, sobald der Pot HU ist" nachbauen will, sollte
wissen, dass sie hier **gemessen verloren hat**.

**Fallstricke.** `decide()` prüft `self.table is not None and not self.table.hand_over and self._heads_up()`.
Wer `bind_table` vergisst, bekommt still einen reinen `tag`-Bot — der Lauf sieht erfolgreich aus und misst das
Falsche. Genau dagegen prüft `tests/test_hybrid.py:24` (`prince_decisions > 0`). Zweitens ist der HU-Zweig
`except Exception` (`:69`): jeder Prince-Fehler fällt still auf den Kern zurück und wird nur in
`kern_fallbacks` sichtbar — diesen Zähler in jedem Lauf mit ausgeben.

---

### SNG-Arena (gepaarte Single-Table-Turniere) — `pokerbot/arena/tourney.py`
**Zweck (1 Satz).** Spielt ganze Single-Table-SNGs des Heros gegen ein Liga-Feld und misst den ICM-Effekt als
gepaartes Experiment: Arm A (ICM an) und Arm B (ICM aus) spielen dieselben Seeds gegen dieselben Profile.

**Schnittstelle.**
- `run_tourney(structure: Structure, hero_factory, seed: int, icm_on: bool = True,
  field: list[str] | None = None) -> dict` — EIN Turnier bis zum Sieger; liefert
  `{"place": int, "payout": float, "hands": int}` des Heros.
- `run_batch(n: int, hero_factory, structure=SNG9, base_seed=1000) -> dict` — n Paare; liefert je Arm
  `{roi_pct, se_pct, netto, n, platz_verteilung}` plus `delta = {roi_pp, se_pp}` der gepaarten Differenz.
- `main()` / CLI: `python -m pokerbot.arena.tourney --tourneys 400 [--seed N] [--out datei.json]`.
  `--out` schreibt die Rohdaten je Paar (für exaktes Poolen mehrerer Worker statt Aggregat-Mittelung).
- `FIELD_PROFILES` (`:19`) = 8 Gegner (`tag, lag, nit, station, maniac, tag, lag, nit`) ⇒ 9-max.

**Eingabe/Ausgabe.** Rein: eine `Structure` (aus `strategy/tournament.py`) und eine `hero_factory(rng)`, die
einen Agenten mit `.decide(obs)` und optional `.observe(...)`/`.bind_table(...)` liefert. Raus: dicts wie oben;
Geldgrößen in derselben Einheit wie `Structure.buyin`, ROI in Prozent bzw. Prozentpunkten.

**Abhängigkeiten.** HART: `pokerbot.arena.sixmax` (das Feld), `pokerbot.strategy.tournament`
(`Director`, `Structure`, `SNG9`), indirekt `pokerbot.engine.table`. Die `hero_factory` ist der
Austauschpunkt — dort hängt man einen beliebigen eigenen Bot ein.

**Zustand.** Je Turnier neu: `Director`, Agenten, Tisch. Über den Batch hinweg zustandslos. Wichtig:
`_mk_agents` (`:22`) baut die Feld-Bots je Turnier frisch, sie tragen also keine Reads von Turnier zu Turnier.

**Kosten.** Nicht separat gemessen. Belegter Größenordnungs-Anker aus derselben Codefamilie: ein volles
60-Spieler-MTT bots-only läuft in **38,8–40,1 s / 131 Runden** (`docs/TURNIER_MODUS.md:85`).

**Mess-Status.** **GEMESSEN POSITIV — dies ist der Kanal, der das anteilige Risiko-Premium validiert hat**
(`docs/STATE.md:402-406`): μ-1 (voller Bubble-Faktor auf jeden Call) **REFUTIERT sich selbst: −8,1 ± 13,9 pp
ROI** mit Überstraffungs-Fingerabdruck (mehr 4. Plätze — zur Bubble überlebt, dort ausgeblutet) →
Doktrin-Fix → μ-2 **+9,2 ± 8,0 pp** (n=500; 2. Plätze 71 vs 47) → **μ-3: +10,02 ± 5,03 pp ROI,
95 %-Band [+0,2; +19,9], z = 1,99 — VALIDIERT**, mit MEHR Siegen (214 vs 192) UND besserer Ladder
(n=1500 Paare, 6 parallele Worker). Zusatzbefund am Druck-Hebel gegen ein ICM-spielendes Bot-Feld
(n=300/Arm, gepaart): chipEV +6,6 / icm +7,7 / **icm+druck +14,1 % ROI** — Ordnung klar, z = 0,76, also
Signifikanz noch offen (`docs/STATE.md:409-412`). Die Modell-Fee (~4,8 pp) ist in keiner dieser Zahlen
abgezogen.

**Allein benutzbar?** Ja, wenn man `strategy/tournament.py` + `engine/table.py` mitnimmt. Der Rest ist eine
120-Zeilen-Spielschleife mit gepaartem Seed-Management — das nachzubauen ist billiger, als die Kopplung an
unsere `Structure`-Klasse zu übernehmen, wenn man eine eigene Turnierstruktur hat.

**Fallstricke.** Die ICM-Brille bekommt **nur der Hero** (`:56-59`), das Feld bleibt bewusst Chip-EV-naiv.
Wer beide Seiten mit ICM ausstattet, misst etwas anderes (die Messung dazu existiert und heißt „defensive
ICM-Brille gegen ICM-Feld ≈ wertlos, +1,1 pp", `docs/STATE.md:412-413`). Zweitens: die Spielschleife fängt
jede Bot-Exception ab und spielt `check/call/fold` (`:65-69`) — ein kaputter Kandidat produziert dadurch
plausible, aber bedeutungslose Ergebnisse statt eines Absturzes.

---

### MTT-Direktor (60 Spieler, 6 Tische) — `pokerbot/arena/mtt.py`
**Zweck (1 Satz).** Führt ein Multi-Table-Turnier: Feld-Erzeugung nach Profil-Mix, Turnieruhr, Nebentische
vollautomatisch, globale Platzvergabe, Tisch-Kollaps und Balancing, plus die ICM-Kontext-Erzeugung für Bots
und einen Hero-Berater.

**Schnittstelle.**
- `class MTT(seed, hero_name="Du", hero_bot=None, n_players=60, seats_per_table=10, hands_per_level=12,
  start_stack=5000)`.
- Zustandsabfragen: `.level()`, `.level_index()`, `.hands_to_level()`, `.payouts()`, `.payouts_remaining()`,
  `.next_payout()`, `.rank_of(name)`, `.avg_stack()`, `.over()`, `.hero_out()`, `.hero_host()`,
  `.is_final_table()`, `.total_chips()`.
- Ablauf: `.build_table(host) -> Table` · `.bots_for(table) -> {seat: SixMaxBot}` ·
  `.start_stacks(table)` · `.play_bot_hand(host) -> [(name, start_stack)]` (Busts) ·
  `.after_table_hand(table, host, start_stacks)` · `.play_side_tables()` ·
  `.advance_round(hero_busts)` (Rundenschluss nach einer Hero-Hand) · `.play_round_all()` (bots-only) ·
  `.run_bots_only(max_rounds=5000, audit=False) -> {winner, rounds, places}`.
- ICM: `.icm_ctx(table, seat, aggressor, start_stacks, pressure_cache) -> dict | None` ·
  `.hero_icm(table, seat, aggressor, start_stacks, obs) -> dict | None` (Berater-Text).
- `.audit_invariants()` — Chip-Erhaltung, Tischgrößen, Balance ±1, lückenlose Platzvergabe (assert-basiert).
- Freie Funktionen: `field_counts(n_bots, mix)` (größte-Reste-Rundung), `make_league_bot(profile, seed)`.
- Konstanten (`:27-68`): `N_PLAYERS 60`, `SEATS_PER_TABLE 10`, `START_STACK 5000`, `BUYIN 10.0`,
  `HANDS_PER_LEVEL 12`, `MTT_LEVELS` (10 Level, Ante ab Level 3), `LEVEL_EXTENSION_FACTOR 1.5`,
  `PAYOUT_PCT_TOP9`, `FIELD_MIX`, `AVATARS`, `EXACT_ICM_AT 12`, `BUBBLE_WINDOW_FACTOR 1.6`,
  `PRESSURE_CAP 1.5`, `PRESSURE_SLOPE 0.6`, `ICM_HINT_BF 1.15`.

**Eingabe/Ausgabe.** Rein: ein Integer-Seed (steuert Sitzlosung, Profilverteilung, jede Bot-RNG und jedes
Deck) und optional ein `hero_bot`. Raus: `Table`-Objekte je Hand, Bust-Listen `(name, start_stack)`, und für
den Berater ein dict mit `bf`, `villain`, optional `req_chip`/`req_icm`/`text`. Der ICM-Kontext hat die
Schlüssel `stacks`, `payouts`, `seat`, `aggressor`, `invested`, `pressure`, `pressure_mult` — bzw. im
Bubble-Fenster NUR `{pressure, pressure_mult}`.

**Abhängigkeiten.** HART: `pokerbot.arena.sixmax` (Feld), `pokerbot.engine.table.Table` (braucht
`stacks=`, `ante=`, `rebuy=`, `human_seat=`), `pokerbot.strategy.icm.bubble_factor`,
`pokerbot.strategy.tournament` (`BlindLevel`, `icm_pressure_mult`, `icm_required_equity`, `icm_scaled_req`,
`pick_villain`). Der Hero-Tisch selbst wird NICHT hier gespielt, sondern vom Trainer (`web/six_server.py`).

**Zustand.** Je Turnier ein `MTT`-Objekt: `entrants` (Stacks, alive, place), `tables` (`TableHost` mit
`names`, `button_name`, `hand_no`), `alive`, `next_place`, `round_no`, `hero_place`, `table_change`. Nichts
davon ist zurücksetzbar — ein neues Turnier = ein neues Objekt. Die Liga-Bots im Feld tragen ihre `OppModel`
über das ganze Turnier.

**Kosten.** **GEMESSEN:** 5 Nebentische je Hero-Hand **mean 120–129 ms, max ≈ 200–213 ms** (volles Feld,
20 Runden, `docs/TURNIER_MODUS.md:82`); ein komplettes Bots-only-Turnier (Seed 7, Audit jede Runde)
**131 Runden in 38,8–40,1 s** (`:85`). Fallback-Knopf für langsamere Rechner: `MTT.side_tables_every = 2`.

**Mess-Status.** **UNGEMESSEN als Strategie** — es gibt kein EV-/ROI-Verdikt für den MTT-Modus; die Quelle
sagt das explizit („Kein Mess-Verdikt — der Modus ist Trainer-Produkt, kein Bot-Kandidat",
`docs/STATE.md:44-45`). Was gemessen ist, sind Mechanik-Eigenschaften (`tests/test_tournament_mode.py`,
7 Tests, `docs/TURNIER_MODUS.md:82-90`): Chip-Erhaltung 60·5000 nach jeder Runde, jeder Platz 1..60 genau
einmal, Balance ±1, Determinismus (Seed 11 zweimal identisch, Seed 12 verschieden). `FIELD_MIX` ist
ausdrücklich **ein Prior, kein gemessener Fit** (`mtt.py:46-52`).

**Allein benutzbar?** Nur zusammen mit unserer `Table` (die `stacks=`/`ante=`/`rebuy=`-Parameter kennen muss)
und der Liga. Wertvoll herauszulösen sind zwei kleine Teile: die **ICM-Ökonomie-Staffelung** in `icm_ctx`
(exakt ≤ 12 Verbliebene, sonst Bubble-Fenster-Multiplikator, sonst Chip-EV) und die **Rebalancing-Routine**
`_rebalance` (`:337-363`) — beides ist Turnierlogik, die man sonst selbst herleiten müsste.

**Fallstricke.** Die Uhr zählt **Hero-Hände**, nicht Zeit, und jeder Nebentisch spielt genau EINE Hand pro
Hero-Hand. Ein Zehner-Tisch braucht real länger für eine Hand als ein Heads-up-Tisch — das Modell ignoriert
das. Wer aus diesem Direktor Turnier-Statistiken zieht (Feldtempo, Bubble-Zeitpunkt), misst also eine
synchronisierte Kunstwelt: die Dokumentation notiert selbst „60 → ~30 Spieler in ~25 Runden … schneller als
ein echtes Online-MTT" (`docs/TURNIER_MODUS.md`, Nachtrag).

---

### ICM-Mathematik (Malmuth-Harville, exakt) — `pokerbot/strategy/icm.py`
**Zweck (1 Satz).** Berechnet den $-Wert von Turnier-Stacks exakt (Bitmask-DP über die Platz-Rekursion) und
leitet daraus Bubble-Faktor und exakte All-in-Call-Schwellen ab.

**Schnittstelle.**
- `icm_equities(stacks: list[float], payouts: list[float]) -> list[float]` — $-Equity je Spieler; exakt,
  `lru_cache` über die Bitmask (2^n Zustände statt n! Pfade); bricht ab, sobald die Platztiefe die letzte
  bezahlte Position überschreitet.
- `icm_equities_mc(stacks, payouts, iters=20_000, rng=None) -> list[float]` — dieselbe Harville-Annahme
  gesampelt, für große Felder (n > `MC_THRESHOLD = 12`).
- `icm_equity(stacks, payouts, hero) -> float` — Bequemlichkeits-Wrapper.
- `bubble_factor(stacks, payouts, hero, villain) -> float` — `|ΔEq(verlieren)| / ΔEq(gewinnen)` für den Flip
  des effektiven Stacks; ≥ 1,0; `inf`, wenn der Gewinn-Gradient ≤ 0 ist.
- `icm_call_threshold(stacks, payouts, hero, villain, to_call, pot_before) -> float` — exakte Equity-Schwelle
  für einen All-in-Call über drei Welten (fold/win/lose): `(E_fold − E_lose)/(E_win − E_lose)`; liefert
  `1.01`, wenn ein Call nie richtig sein kann, und fällt bei flachen Payouts auf Chip-EV-Pot-Odds zurück.

**Eingabe/Ausgabe.** Rein: zwei Zahlenlisten (Chips, Preisgelder) + Indizes. `len(payouts) <= len(stacks)`;
der Rest zahlt 0. Raus: Floats in der Währungseinheit der `payouts` bzw. eine Wahrscheinlichkeitsschwelle.
**Die Konvention von `icm_call_threshold` ist kritisch und im Docstring festgeschrieben** (`icm.py:129-136`):
`stacks` = BEHIND-Stacks im Entscheidungsmoment, `pot_before` = Gesamtpot INKLUSIVE Gegner-Shove und Heros
bisherigem Einsatz, `to_call` = Restzahlung. Wer das anders füttert, verletzt die Chip-Erhaltung.

**Abhängigkeiten.** KEINE außer der Standardbibliothek (`functools.lru_cache`, `random` lazy in der
MC-Variante). Das ist das am saubersten isolierte Modul dieses Katalogteils.

**Zustand.** Zustandslos. Der `lru_cache` sitzt INNERHALB des Aufrufs und wird per `rec.cache_clear()`
(`icm.py:60`) vor der Rückgabe geleert — es gibt keinen modulweiten Cache, der über Aufrufe hinweg lebt.

**Kosten.** Nicht in Sekunden gemessen. Belegte Struktur-Aussage: exakt bis ~10–12 Spieler bezahlbar
(`MC_THRESHOLD = 12`, `icm.py:19`), darüber die MC-Variante; im MTT wird die exakte Rechnung erst ab
`EXACT_ICM_AT = 12` Verbliebenen zugeschaltet (`mtt.py:64`). `bubble_factor` kostet **drei** volle
`icm_equities`-Läufe, `icm_call_threshold` ebenfalls drei.

**Mess-Status.** **GEMESSEN POSITIV (Korrektheit, nicht EV):** `tests/test_icm.py` prüft die Rekursion gegen
eine **unabhängige Permutations-Enumeration** (bewusst ein anderer Algorithmus) plus geschlossene Form für
2 Spieler; `tests/test_tournament.py` prüft die Buchanker (BF 2,56 ⇒ 71,9 % beim Flip). Ein EV-Verdikt gibt es
für dieses Modul nicht — es liefert Zahlen, keine Politik; die Politik in `tournament.py` ist gemessen.

**Allein benutzbar?** Ja, uneingeschränkt — kopierbar als einzelne Datei ohne jede Repo-Abhängigkeit. Das ist
das Modul dieses Teils, das ein Fremder am ehesten übernehmen sollte statt es neu zu schreiben.

**Fallstricke.** `bubble_factor` kann `float("inf")` zurückgeben (Gewinn-Gradient ≤ 0, z. B. wenn Hero bereits
den Coverstack hält und der Payout-Sprung dominiert). Jeder Aufrufer muss diesen Fall abfangen — im Repo tun
das `tournament.icm_scaled_req` (`:124-125`), `icm_pressure_mult` (`:159`) und `mtt.hero_icm` (`:405`)
einzeln. Wer nur `max()`/Mittelwerte über eine BF-Matrix bildet, bekommt sonst `inf` oder `nan` in die
Strategie.

---

### Turnier-Doktrin + Direktor — `pokerbot/strategy/tournament.py`
**Zweck (1 Satz).** Die Schicht zwischen ICM-Mathematik und Cash-Kern: sie übersetzt Bubble-Faktoren in
korrigierte Call-Schwellen (nur auf der Call-Seite), liefert Turnierstrukturen und führt ein
Single-Table-Turnier.

**Schnittstelle.**
- `@dataclass(frozen=True) BlindLevel(sb, bb, ante=0, hands=10)`.
- `@dataclass(frozen=True) Structure(name, levels, payouts_pct, start_stack=10_000, buyin=100.0)` mit
  `.level_at(hand_no) -> BlindLevel` (letzte Stufe wiederholt sich) und `.payouts(n_entries) -> list[float]`.
  Fertige Strukturen: `SNG9` (50/30/20 %), `SNG6` (65/35), plus die Sensitivitätsarme `FLAT9` (6 flache
  Plätze) und `TOP_HEAVY9` (80/20).
- `icm_required_equity(req_chip: float, bf: float) -> float` — `r' = bf·r / (bf·r + (1−r))`; `bf ≤ 1` ⇒ `r`.
- `pick_villain(stacks, hero, aggressor) -> int` — der Aggressor, sonst der größte gegnerische Stack.
- **`icm_scaled_req(req_chip, obs, to_call, pot) -> float`** — DER EINE Einstiegspunkt für den Cash-Kern
  (`sixmax._decide` ruft genau das, an drei Stellen: `sixmax.py:190`, `:227`). All-in-Calls
  (`to_call >= my_stack`) rechnen exakt über `icm_call_threshold`, alles andere über das **anteilige
  Risiko-Premium** `BF_eff = 1 + (BF−1)·(to_call/Stack)` (`tournament.py:131-133`).
- `icm_pressure_mult(obs, villains=None) -> float` — Steal-Verbreiterung des Coverstacks:
  `min(1.6, 1 + 0.5·(mittlerer BF der Gegner gegen uns − 1))`; respektiert einen vorberechneten
  `ctx["pressure_mult"]` (MTT-Pfad). Wird in `sixmax.py:166-167` auf die Open-Fraktion multipliziert.
- `bf_matrix(stacks, payouts) -> list[list[float]]` — alle Paar-BFs, für Diagnosen/Reports.
- `class Director(structure, names, seed=None)` — `.alive()`, `.payouts_remaining()`, `.over()`,
  `.next_table() -> Table`, `.icm_ctx(table, seat, aggressor) -> dict`, `.after_hand(table)`,
  `.results() -> [{name, place, payout}]`.

**Eingabe/Ausgabe.** `icm_scaled_req` liest `obs['icm']` mit den Schlüsseln `stacks` (Start-of-Hand-Chips je
Sitz), `payouts` (Rest-Preisgelder), `seat` (Hero), `aggressor` (Sitz oder `None`), `invested` (Sitz→bereits
investiert; nur für den All-in-Pfad) — plus `obs['my_stack']`. **Fehlt `obs['icm']`, gibt die Funktion
`req_chip` unverändert zurück; der Cash-Kern fasst sie dann nie an (bewusster Anker-Schutz.)**
Raus: eine korrigierte Required-Equity in [0,1].

**Abhängigkeiten.** HART: `pokerbot.strategy.icm`, `pokerbot.engine.table.Table` (nur für den `Director`;
die Doktrin-Formeln oben sind Table-frei). Ersetzbar: die `Structure`-Konstanten sind reine Daten.

**Zustand.** Die Formeln sind zustandslos. Der `Director` ist **je Turnier**: `entrants` (Stack/alive/place),
`hand_no`, `_button_name`, `_next_place`, `_start_stacks`. `_start_stacks` wird in `next_table()` gesetzt und
in `after_hand()` gelesen — die beiden gehören zwingend zusammen.

**Kosten.** Ein `icm_scaled_req` mit BF-Pfad = drei `icm_equities`-Läufe; der All-in-Pfad = drei weitere.
`icm_pressure_mult` = ein BF je Gegner, deshalb im MTT je Hand einmal vorberechnet und gecacht
(`mtt.py:259-263`). Absolute Latenz nicht gemessen.

**Mess-Status.**
- **Anteiliges Risiko-Premium: GEMESSEN POSITIV / VALIDIERT — +10,02 ± 5,03 pp ROI, 95 %-Band [+0,2; +19,9],
  z = 1,99, n = 1500 gepaarte Turniere** (`docs/STATE.md:405-406`); Mechanismus-Fingerabdruck: mehr Siege
  (214 vs 192) UND bessere Ladder.
- **Voller Bubble-Faktor auf jeden Call: REFUTIERT — −8,1 ± 13,9 pp ROI** mit Überstraffungs-Muster
  (`docs/STATE.md:402-404`). Genau deshalb existiert die Anteils-Formel; sie ist keine Verfeinerung, sondern
  ein Fix für ein gemessenes Versagen.
- **Druck-Hebel (`icm_pressure_mult`): GEMESSEN POSITIV, aber nicht signifikant — icm+druck +14,1 % ROI vs
  icm +7,7 vs chipEV +6,6 (n = 300/Arm, gepaart, z = 0,76)**; in der 2×2-Zerlegung trägt der Druck
  +4,7 pp allein / +6,4 gebündelt (`docs/STATE.md:409-416`).
- Mechanik: `tests/test_tournament.py` — Chip-Erhaltung über ganze Turniere inkl. Ante-Side-Pots,
  Determinismus, Buchanker, **Cash-Parität** (ohne `obs['icm']` entscheidet der sixmax-Kern byte-identisch).

**Allein benutzbar?** Die Doktrin-Formeln (`icm_required_equity`, `icm_scaled_req`, `pick_villain`,
`icm_pressure_mult`) ja — sie brauchen nur `icm.py` und ein dict. Der `Director` nicht ohne unsere `Table`.

**Fallstricke.** Der Aufschlag trifft **ausschließlich die Call-Seite** (Gap-Konzept: Jam- und Open-Ranges
bleiben Chip-EV, weil Fold Equity unter ICM die geschützte Equity-Form ist). Wer `icm_scaled_req` auch auf
die Bet-/Jam-Seite legt, baut genau die Überstraffung nach, die als μ-1 refutiert wurde. Zweiter, subtiler
Punkt: der All-in-Pfad muss den **uncalled excess** des Villain-Shoves an ihn zurückgeben
(`tournament.py:117-122`) und die `behind`-Stacks für JEDEN Sitz um `invested` reduzieren — beides sind im
Repo gefangene Bugs (Dritt-Einsätze existierten doppelt, Hero bekam fremde Chips geschenkt). Wer die Formel
abschreibt und diese zwei Korrekturen weglässt, callt an der Bubble zu locker.

---

### Open-Poker-Arena-Client (WebSocket) — `pokerbot/arena/openpoker.py`
**Zweck (1 Satz).** Verbindet den zustandslosen 6-max-Kern über WebSocket mit der Online-Arena
openpoker.ai — Auth, Lobby-Join, `your_turn` → Entscheidung → `action`.

**Schnittstelle.** `class OpenPokerClient(api_key, buy_in=2000, verbose=True)` mit
`.position_label(n_active) -> str` (Dealer-relative Sitzordnung → unsere Positionslabels), `.reset_hand()`,
`async .run()` (Verbindungsschleife), `async .handle(ws, msg: dict)` (Nachrichten-Dispatch); `main()` als
CLI-Einstieg (`python -m pokerbot.arena.openpoker`, Key über `OPENPOKER_API_KEY`).

**Eingabe/Ausgabe.** Rein: JSON-Nachrichten des Servers (`connected`, `table_joined`, `your_turn`, …). Der
Client führt daraus ein leichtes Tischmodell (`my_seat`, `dealer_seat`, `sb/bb`, `hole`, `board`, `street`,
`seat_stacks`, `preflop_raises`, `my_committed_street`) und baut daraus das `obs`-dict für `decide_6max`.
Raus: eine `action`-Nachricht, die `hand_id` und `turn_token` zurückspiegelt. Unbekannte Nachrichtentypen
werden geloggt, nicht verworfen.

**Abhängigkeiten.** HART: `pokerbot.arena.sixmax.decide_6max`, `websockets` (lazy importiert in `.run()`,
`:142`; fehlt es, druckt der Client `pip install websockets` und bricht ab). Sonst nur Standardbibliothek.

**Zustand.** Je Verbindung/Hand: das Tischmodell oben; `.reset_hand()` setzt Board/Street/`preflop_raises`
zurück. Kein Gegnermodell — er nutzt den zustandslosen Kern, kein `SixMaxBot`.

**Kosten.** Nicht gemessen.

**Mess-Status.** **UNGEMESSEN.** Belegt ist ausschließlich die Konnektivität: „Endpunkt-Erreichbarkeit +
Auth-Handshake bestätigt (Server antwortet exakt laut Doku)" (`docs/archive/EDGE_UND_ARENA.md:34-36`). Es
existiert kein bb/100-Ergebnis aus dieser Arena, und die Quelle notiert selbst, dass einzelne Live-Felder
(z. B. die Dealer-Position pro Hand) in der Fremd-Doku nur teilweise spezifiziert sind. Das Modul liegt in
`docs/archive/BOT_PARTS_CATALOG.md:105` als „TOOL" geführt — Werkzeug, nicht Produktpfad.

**Allein benutzbar?** Nur gegen genau diesen Anbieter. Als Vorlage taugt die Trennung „Protokoll-Adapter baut
`obs` → Kern entscheidet → Adapter formt `action`" — das ist das übertragbare Muster, der Rest ist
anbieterspezifisch.

**Fallstricke.** `position_label` fällt bei unvollständigem Tischmodell still auf `"CO"` zurück
(`:57-58`, `:63`). Der Bot spielt dann eine falsche Position, ohne dass etwas auffällt — wer den Client
produktiv nutzen will, muss diesen Default in einen sichtbaren Fehler verwandeln.

---

### Haiku-Pilot (LLM steuert Exploit-Knöpfe) — `pokerbot/arena/haiku_pilot.py`
**Zweck (1 Satz).** Experiment: ein LLM (Claude Haiku) liest alle N Hände das Gegnerprofil und setzt vier
boolesche Exploit-Schalter des `AdaptiveExploiter`, um zu testen, ob LLM-Steuerung die automatische
Knopf-Setzung schlägt.

**Schnittstelle.** `haiku_knobs(client, summary: dict, fold_curve: dict) -> Knobs` (ein Modellaufruf, JSON
zurück, bei jedem Fehler Default-Knobs) · `class HaikuPilot(client, hero=0, iters=90, refresh=40)` mit
`.decide(st)`, `.observe_opponent(st, a)`, `.observe_hand_end()` (setzt alle `refresh` Hände neu, sobald
`prof.confidence() > 0.1`) · `main()` (`--hands`, `--refresh`, `--iters`).

**Eingabe/Ausgabe.** Rein: das Gegner-Summary + die Fold-Kurve bei 0,33- und 0,9-Pot-Sizings. Raus: ein
`Knobs`-Objekt mit `exploit_bluff`, `exploit_value`, `exploit_bluffcatch`, `probe` (je 0/1). Der Vergleich
in `main()` druckt bb/100 „auto-knobs" gegen „haiku-pilot" für drei synthetische Gegner.

**Abhängigkeiten.** HART: `anthropic` (echter API-Key aus `pokerbot.config`),
`pokerbot.strategy.adaptive.AdaptiveExploiter`, `pokerbot.benchmark.beat_them_all`. **Der
`AdaptiveExploiter`-Cluster ist im Repo als verwaist dokumentiert** — kein Live-Pfad nutzt ihn, nur
Benchmarks und dieses Skript (`docs/archive/BOT_PARTS_CATALOG.md:20`).

**Zustand.** Je Sitzung: der gekapselte `AdaptiveExploiter` (Gegnerprofil) + `self.h` (Handzähler) +
`self.last` (zuletzt gesetzte Knobs). Kein Reset vorgesehen.

**Kosten.** Ein LLM-Aufruf je `refresh` Hände (Default 40) — also Geld und Netzlatenz, aber bewusst NICHT in
der Per-Hand-Schleife. Nicht gemessen.

**Mess-Status.** **UNGEMESSEN** — im Repo sind keine Ergebniszahlen dieses Piloten abgelegt. Der übergeordnete
Mechanismus, den er steuert, ist inzwischen negativ vermessen: das Exploit-Gate (HU-PokerBot, 600 gepaarte
Decks je Liga-Profil) fand **alle acht Diffs ON−OFF ≤ 0, gepoolt ≈ −12 bb/100 (SE ≈ 4,5)** und erklärt den
Exploit-Pfad damit für refutiert (`docs/TRAINER_VERDRAHTUNG.md:74-95`, Journal `typ: "EXPLOIT-GATE-VERDIKT"`).
Das ist nicht dasselbe Codestück, aber dieselbe Idee — wer den Piloten nachbaut, sollte diese Messung kennen.

**Allein benutzbar?** Nein, ohne `adaptive.py` + `beat_them_all.py` + API-Key läuft nichts. Übertragbar ist
nur das Muster: **LLM setzt Strategie-Flags im Minutentakt, die schnelle Engine entscheidet jede Hand** —
kein LLM in der Per-Hand-Schleife.

**Fallstricke.** `haiku_knobs` fängt jede Exception und liefert dann Knobs mit allen Defaults **auf 1**
(`:44-46`) — ein stillschweigend fehlgeschlagener API-Call sieht im Log identisch aus wie „das LLM will alle
Exploits an". Wer damit misst, misst im Zweifel den Fehlerpfad.

---

## Produkte: Trainer, Coach, Vision

Dieses Subsystem ist alles, was einen Menschen an den Bot heranlaesst: zwei FastAPI-Spiel-Server (Heads-up und
6-max/Turnier), eine Benotungs-Kette, die jede menschliche Entscheidung gegen eine Bot-Referenz graded und auf
Deutsch erklaert, Session-Statistik und eine Bildschirm-Bruecke, die eine fremde Poker-Software (PokerSnowie 4)
per Template-Matching liest und automatisch bespielt. Fuer einen reinen Bot braucht man NICHTS davon — die Server
sind duenne Wrapper um `engine/table.py`. Interessant sind drei Dinge einzeln: die Decision-Capture/Grader-Kette
(P0-Schema, deterministisch, fail-soft), das Snowie-Gatter (wie man verhindert, dass ein Bot mit falsch gelesenen
Zahlen rechnet) und der Hand-Logger als JSONL-Format.

---

## Web-Apps

### Heads-up-Server — `pokerbot/web/server.py`
**Zweck.** FastAPI-App, in der ein Mensch (Sitz 0) heads-up gegen den Produktions-Bot spielt, mit einem zweiten,
identisch konfigurierten Bot als Berater und optionalem Claude-Coaching.

**Schnittstelle.**
- `class Session(stack=10000, sb=50, bb=100)` — haelt `HeadsUpGame`, den Gegner-Bot, den Berater-Bot, den Coach,
  den Session-Logpfad.
- `Session.start_hand() -> list[dict]` / `Session.advance() -> list[dict]` — startet bzw. laesst den Bot handeln,
  bis der Mensch am Zug ist; gibt Bot-Events zurueck.
- `Session.human_action(action: str, amount: int|None) -> list[dict]` — holt VOR dem Zug die Berater-Empfehlung,
  fuettert das Gegnermodell, fuehrt die Aktion aus, laesst den Bot weiterspielen.
- `Session.beratung() -> dict|None` — Champion-Empfehlung am aktuellen Entscheidungspunkt (None = nicht am Zug).
- `Session.fingerprints() -> dict` — Kernfelder beider Bots (Hash, Stack, exploit, Resolver-Flags, PRINCE-Flags);
  belegt im View, dass Gegner und Berater dieselbe Politik spielen.
- `Session.view(events) -> dict`.
- HTTP-Routen: `GET /` (HTML), `POST /api/new_game {stack,sb,bb}`, `POST /api/next_hand`, `POST /api/action
  {action, amount}`, `GET /api/state`, `GET /api/advice`, `POST /api/coach/explain`, `POST /api/coach/review`,
  `POST /api/coach/ask {question}`.
- `main()` — argparse `--host/--port/--open`, startet uvicorn (Default Port 8000).

**Eingabe/Ausgabe.** Rein: JSON-Bodies (`ActionReq{action, amount}`, `NewGameReq{stack,sb,bb}`, `AskReq{question}`).
Raus: `view()`-dict mit `state` (das `HeadsUpGame.state(hide=BOT)`-dict), `fingerprints`, `human_idx`, `bot_idx`,
`bot_events` (je `{who, action, amount, rationale, street}`), `coach_available`, `match_over`. Coach-Routen geben
`{"text": ...}`. Jede beendete Hand wird als volles `game.state()`-JSON nach
`data/sessions/hu_<zeitstempel>.jsonl` angehaengt.

**Abhaengigkeiten.** Hart: `pokerbot.engine.game.HeadsUpGame`, `pokerbot.strategy.bot.PokerBot`, FastAPI/uvicorn/
pydantic. Hart bei eingeschaltetem Default: `pokerbot.strategy.gto_mode.apply()` und `pokerbot.strategy.auslese.
setze_env/wickle_decide/FINAL_STACK` (das Guard-Ketten-Profil des Repos), `pokerbot.runtime_config` (Fingerprint +
Fehlkonfig-Gatter). Ersetzbar: `pokerbot.coach.coach.Coach` (nur die drei Coach-Routen).

**Zustand.** Ein einziges Modul-Global `SESSION` — die App ist EIN-Spieler und EIN-Tisch. `POST /api/new_game`
ersetzt es komplett; alles bisherige (Gegnermodell, Kommentare, Logpfad) ist danach weg. Innerhalb einer Session:
Zustand je Hand (`last_bot`, `last_human`, `counted`) und je Session (`log_path`, Gegnermodell des Bots).

**Kosten.** Nicht gemessen in diesem Modul. Der Resolver ist per Default AN (`POKERB_RESOLVER=0` schaltet ab), was
die Antwortzeit dominiert; der Kommentar in `server.py:44-46` nennt genau das als Grund fuer den Schalter.

**Mess-Status.** UNGEMESSEN als Produkt. Die gespielte Konfiguration ist die gemessene: PRINCE, exploit OFF,
Resolver AN, `wickle_decide(FINAL_STACK)` — laut `docs/STATE.md:47-49` bewusst so verdrahtet ("Gegner UND Berater
= Champion-Konfig"). Der GTOW-Anker der Politik selbst liegt woanders (STATE.md:56-57: nur v4-auf-PRINCE −21,1 ist
GTOW-bestaetigt).

**Allein benutzbar?** Ja: `python -m pokerbot.web.server --open`. Minimal noetig sind Engine + Strategie + FastAPI.
Ohne Anthropic-Key laeuft alles ausser den drei Coach-Routen (`coach_available:false`).

**Fallstricke.** Die Env-Flags werden VOR dem Bot-Import gesetzt (`server.py:20-27`), weil `postflop.py`/`advisor.py`
ihre Flags zur IMPORTZEIT lesen. Wer das Modul aus einem anderen Prozess importiert, der `pokerbot.strategy` schon
geladen hat, bekommt stillschweigend eine andere Politik als die gemessene. Ausserdem: `_INDEX` wird beim Import
EINMAL gelesen — UI-Aenderungen brauchen einen Server-Neustart (anders als bei `six_server`).

---

### 6-max-/Trainer-/Turnier-Server — `pokerbot/web/six_server.py`
**Zweck.** Der Haupt-Produkt-Server: Mensch auf Sitz 0 gegen 1–9 Liga-Bots, in fuenf Modi (`gto`, `exploit`,
`arena`, `punish`, `tournament`), mit vollstaendiger Trainer-Kette (Capture → Benotung → deutsches Feedback →
Replay → Report).

**Schnittstelle.**
- `class Session(stack=10000, sb=50, bb=100, mode="gto", players=6, seed=None)` — baut Tisch, Bot-Belegung,
  Session-Pfade, laedt die Coach-Module lazy.
- `Session.start_hand(auto_advance=True) -> list[dict]` — neue Hand; `auto_advance=False` = Step-Modus (Client
  treibt die Bots via `/api/step`).
- `Session.human_action(action, amount, step_mode=False) -> list[dict]` — Kern: baut VOR `table.act()` den
  Decision-Record, fuehrt aus, haengt den Record erst nach erfolgreichem `act` an (illegale Aktion darf keinen
  Geister-Record hinterlassen), fuettert alle Gegnermodelle.
- `Session.prefold() -> list[dict]` — Vorab-Fold: spielt die Hand sofort im Hintergrund fertig; Sonderfaelle
  `check_frei` (Gratis-Check hebt den Vorab-Fold auf) und `kampflos`.
- `Session.step() -> list[dict]` — genau EINE Bot-Aktion.
- `Session.view(events) -> dict`.
- `Session._grade_and_flush()` — benotet alle Records der beendeten Hand und rendert das Feedback (Budget
  `GRADING_BUDGET_MS = 800`, Warnung bei Ueberschreitung, `six_server.py:40`).
- HTTP: `GET /` (six.html), `GET /training` (training.html), `POST /api/new_session {stack_bb, mode, step,
  players, seed}`, `POST /api/hand {step}`, `POST /api/action {action, amount: float|None, step}`,
  `POST /api/prefold`, `POST /api/step`, `GET /api/state`, `POST /api/analyze`, `GET /api/glossary`,
  `GET /api/feedback/last`, `GET /api/replay/last`, `GET /api/opponent_panel`, `GET /api/report`.
- `main()` — `--host/--port/--open/--trainer`; ruft beim Start einmal `grader.prewarm()`.

**Eingabe/Ausgabe.** Der `view()`-dict ist der Vertrag zum Client; tragende Schluessel: `hand_no, button, sb, bb,
street, board, pot, current_bet, to_act, hand_over, result, human_seat, session_net, hands_done, seats[]
(seat/name/stack/hole/folded/all_in/committed_street/is_human/is_button/is_turn/pos/net/won), legal, bot_events,
mode, coach (das Feedback-dict am Handende), difficulty{profiles, error_rate}, prince_seat, arena_news,
tournament, prefold`. Geschrieben werden zwei JSONL pro Session:
`data/sessions/session_<sid>.jsonl` (Hand-Records) und `data/sessions/decisions_<sid>.jsonl` (benotete
Decision-Records).

**Abhaengigkeiten.** Hart: `engine/table.Table`, `arena/sixmax` (PROFILES/SixMaxBot/PUNISHER_ASSIGN),
`web/session_log`, FastAPI. Hart nur im Turniermodus: `arena/mtt.MTT`. Weich (alle via `_coach(name)` lazy +
`try/except`, jede fehlende Datei schaltet nur ihr Feature ab): `coach.registry`, `coach.difficulty`,
`coach.decision_log`, `coach.grader`, `coach.templates_de`, `coach.oracle`, `coach.replay`,
`coach.opponent_panel`, `coach.trainer_report`, `coach.glossar_de`, `coach.range_story`,
`analysis.session_analysis`.

**Zustand.** Ein Modul-Global `SESSION`; `POST /api/new_session` ersetzt es (die Registry schreibt vorher die
End-Zeile). Je Hand: `_pending_decisions`, `prefold_state`, `last_graded`, `last_feedback`, `last_hand_record`.
Je Session: `human_net`, `hands_done`, `_grade_counts`, `last_error_rate`, Gegnermodelle der Bots, im Turnier
zusaetzlich der komplette `MTT`-Zustand. Zuruecksetzen heisst: neue `Session` bauen.

**Kosten.** Benotungs-Budget 800 ms pro Hand (Konstante, mit Konsolen-Warnung bei Ueberschreitung). Erste Hand
nach `prewarm()` gemessen 7,8 ms Grading (`docs/STATE.md:494`); ohne Prewarm kostete der erste `decide()` ~1,6 s.
Nebentische im Turnier ≈ 120–130 ms je Hero-Hand (`docs/STATE.md:35`).

**Mess-Status.** Gemischt.
- Trainer-Kette insgesamt: GEMESSEN POSITIV als Gate — „autotest 8/8 PASS over 800 hands / 1411 decisions"
  (`docs/STATE.md:496`).
- Prince-HU-Takeover in HU-kollabierten 6-max-Poetten: **REFUTIERT** — hybrid −23,6 ± 9,0, hybrid_r8 −21,7 ± 9,0,
  hybrid_r10 −26,6 ± 8,9 bb/100 vs Liga-Kern `tag`, je 2992 gepaarte Decks, alle VERWERFEN
  (`docs/STATE.md:50-52`, Journal `VERDRAHTUNG-6MAX-VERDIKT`). Darum default AUS
  (`POKERB_SIX_TAKEOVER=1` schaltet ein).
- Exploit-Reads der Liga: **REFUTIERT** — ON vs OFF, 600 gepaarte Decks, alle 8 Diffs ≤ 0, gepoolt ≈ −12 bb/100
  (`docs/STATE.md:53-55`, Journal `EXPLOIT-GATE-VERDIKT`).
- Der Liga-Kern `tag` mit `flat_guard`: GEMESSEN POSITIV, +17,7 ± 6,4 / +11,4 ± 6,9 / +19,2 ± 7,0 bb/100 in drei
  pargate6-Laeufen (Journal `FLATFIX-6MAX-VERDIKT`).
- Turnier- und Vorab-Fold-Modus: UNGEMESSEN als EV („Kein Mess-Verdikt — der Modus ist Trainer-Produkt, kein
  Bot-Kandidat", `docs/STATE.md:44-45`); Funktionsgates: `tests/test_tournament_mode.py`, `tests/test_prefold.py`.

**Allein benutzbar?** Ja: `python -m pokerbot.web.six_server --open` (Tisch) oder `--trainer` (Coaching-UI).
Minimal: Engine + Arena-Liga + FastAPI; die gesamte `coach/`-Ebene darf fehlen, dann spielt man ohne Benotung.
Multiway ueber `?players=9` bzw. `NewReq.players` (2–10).

**Fallstricke.** Die Trainer-Module werden per `importlib` in einem nackten `except Exception` geladen — ein
Syntaxfehler oder ein fehlender Import in `coach/grader.py` schaltet die Benotung STILL ab, ohne Fehlermeldung im
Server-Log. Wer die Kette debuggt, muss `_coach("grader")` von Hand aufrufen. Zweiter Fallstrick: `ActionReq.amount`
ist bewusst `float` — im Turnier erzeugt der Viertel-bb-Slider bei bb=50 Betraege wie 187,5, und ein `int`-Feld
antwortete mit pydantic-422, was der Client als Spielzustand rendert (leerer Tisch, „Hand #undefined";
`six_server.py:582-585`).

---

### Hand-Logger — `pokerbot/web/session_log.py`
**Zweck.** Verwandelt einen fertig gespielten `Table` in EINEN JSONL-Record und haengt ihn an eine Datei an.

**Schnittstelle.** `build_hand_record(table) -> dict`; `append_record(path, rec: dict) -> None` (legt Verzeichnisse
an, schreibt UTF-8 + `ensure_ascii=False`).

**Eingabe/Ausgabe.** Rein: ein `Table` nach Handende. Raus:
`{hand_no, button, sb, bb, human_seat, positions{seat:pos}, hole{seat:[karten]}, board[], actions[{street, seat,
pos, action, amount, is_human}], result, net{seat:chips}}`. `amount` ist `h["to"] or h["amount"]` — also fuer
`bet/raise` das Strassen-Commit-TO-Total, fuer `call` die zugefuegten Chips (die Konvention von `table.py`).
`net` = gewonnene Chips minus `committed_total`.

**Abhaengigkeiten.** Keine ausser der Duck-Typed-`Table`-Schnittstelle (`seats`, `history`, `result`, `hand_no`,
`button`, `sb`, `bb`, `board`, `n`, `position_label`). Frei ersetzbar.

**Zustand.** Zustandslos.

**Kosten.** Nicht gemessen (ein `json.dumps` + ein Append je Hand).

**Mess-Status.** UNGEMESSEN — reines Format-Modul. Es ist aber die Eingabe von `analysis.session_analysis`,
`coach.replay`, `coach.trainer_report` und `coach.export_gtow`.

**Allein benutzbar?** Ja, wenn man das Table-Interface nachbaut. `append_record` wird im Repo auch fuer die
Registry und das GTOW-Ledger wiederverwendet.

**Fallstricke.** Der Filter `if "player" not in h` wirft die `blinds`- und `deal`-Events der Engine-History weg.
Wer aus dem Record spaeter animieren will, muss Blinds und Board-Reveal rekonstruieren — genau das tut
`coach/replay.py`. Ausserdem sind die dict-Schluessel nach dem JSON-Roundtrip STRINGS, nicht ints.

---

### Trainings-Dashboard — `pokerbot/web/train_dashboard.py`
**Zweck.** Winziger FastAPI-Server, der `data/training_metrics.jsonl` + `data/eval_gates.json` waehrend eines
Pod-Trainingslaufs als Canvas-Charts anzeigt.

**Schnittstelle.** `GET /` (liest `static/train_dashboard.html` frisch pro Request), `GET /api/metrics ->
{"metrics": [...], "gates": {...}|None}`; `main()` mit `--host/--port/--open` (Default Port 8001).

**Eingabe/Ausgabe.** Rein: zwei Dateien im Datenverzeichnis, per scp vom Pod gestreamt. Raus: das obige JSON.
Fehlende/kaputte Dateien ergeben leere Liste bzw. `null`, nie einen Fehler.

**Abhaengigkeiten.** FastAPI + `pokerbot.config` (nur fuer `DATA_DIR`). Trivial ersetzbar.

**Zustand.** Zustandslos.

**Kosten.** Nicht gemessen.

**Mess-Status.** UNGEMESSEN — Beobachtungswerkzeug, gehoert zum (inzwischen sekundaeren) LLM-Trainings-Track.

**Allein benutzbar?** Ja, aber nur sinnvoll mit dem Pod-Trainingslauf, der die JSONL schreibt.

**Fallstricke.** Es gibt keine Schema-Pruefung: das HTML erwartet bestimmte Metrik-Schluessel; wer ein anderes
Trainingsskript anschliesst, sieht leere Charts statt einer Fehlermeldung.

---

### UI-Dateien — `pokerbot/web/static/{index.html, six.html, training.html, train_dashboard.html}`
**Zweck.** Vier eigenstaendige HTML-Seiten ohne Framework: HU-Tisch (`index.html`), 6-max-Tisch (`six.html`,
19 KB), Trainer-Oberflaeche mit Coaching-Panel (`training.html`, 75 KB — Tisch links ~60 %, Panel rechts ~40 %,
Snowie-Layout 2560×1440), Trainings-Dashboard.

**Schnittstelle.** Kein Python-API. `training.html` dokumentiert seinen Server-Vertrag im Kopf-Kommentar:
`POST /api/new_session|/api/action|/api/hand|/api/analyze`, `GET /api/glossary` (Fallback `/api/glossar`),
`GET /api/replay/last`, `GET /api/bot_read` (Fallback `/api/opponent_panel`), plus die `view`-Felder.

**Eingabe/Ausgabe.** Jede POST-Antwort ist der VOLLE `view()`-dict; `render(v)` zeichnet daraus alles neu — es
gibt keinen inkrementellen Client-Zustand.

**Abhaengigkeiten.** Nur die Routen des jeweiligen Servers. Alle optionalen Felder degradieren auf Platzhalter.

**Zustand.** Im Browser; kein Server-Zustand.

**Kosten.** Nicht gemessen.

**Mess-Status.** UNGEMESSEN (UI). Als Gate existiert: `six.html` byte-identisch beim Trainer-Build (P2-7,
`docs/STATE.md:496-497`) und Browser-Verifikation bei 2560×1440.

**Allein benutzbar?** Nur zusammen mit dem passenden Server.

**Fallstricke.** `six_server` liest `six.html`/`training.html` FRISCH pro Request (Edit → F5 genuegt),
`server.py` cached `index.html` beim Import (Edit → Neustart noetig). Diese Asymmetrie kostet garantiert einmal
eine halbe Stunde.

---

## Trainer-Kette (`pokerbot/coach/`)

Die Kette ist: `decision_log` (Snapshot) → `grader` (4 Mathe-Checks) + `oracle` (Referenz-Bot) → `templates_de`
(deutscher Text) → `replay`/`trainer_report`/`opponent_panel` (Ansichten). Sie ist deterministisch, arbeitet
NUR auf dicts und braucht keinen Server.

### Decision-Capture — `pokerbot/coach/decision_log.py`
**Zweck.** Baut aus dem lebenden `Table` genau VOR `table.act()` einen unveraenderlichen Snapshot der
menschlichen Entscheidung (Schema `trainer.decision.v1`).

**Schnittstelle.**
- `capture_decision(table, session_id: str, hand_no: int, mode: str, action: str, amount) -> dict` — reiner
  Lesevorgang, mutiert den Tisch nicht.
- `spot_fingerprint(spot: dict) -> int` — crc32 ueber kanonisches JSON von
  `{street, board, hero_hole, pot, to_call, line}`; NIE `hash()` (prozess-salted).
- Konstanten: `SCHEMA_VERSION`, `HUMAN_SEAT = 0`, `CAPTURE_BUDGET_MS = 5.0`.

**Eingabe/Ausgabe.** Raus: `{schema, session_id, hand_id ("<sid>-<hand_no>"), ts, mode, street, spot, obs, legal,
history, human_action{action, amount}, spot_fp}`. `spot` = `asdict(format_spot.spot_from_table(...))`,
`obs`/`legal` sind woertlich `table.obs_for(0)` / `table.legal_actions()`, `history` nur die Eintraege mit
`player`. `amount` bei `bet/raise` = Commit-TO-Total in Chips; bei `allin` ist `amount=None` und die effektive
Groesse steckt in `legal["raise_max"]`. Die Grade-Felder (`checks`, `oracle`, `grade`, `grade_typ`,
`erklaerung_kurz`, `grade_ms`) fuegt spaeter `grader.grade_decision` hinzu.

**Abhaengigkeiten.** Hart: `pokerbot.brain.format_spot.spot_from_table` und das Table-Interface. Sonst nur
stdlib.

**Zustand.** Zustandslos.

**Kosten.** GEMESSEN im eigenen Selbsttest: Budget 5 ms, `min()` ueber 5 Laeufe muss darunter liegen
(`decision_log.py:123-129`); das Modul ruft bewusst weder Equity noch Advisor noch Oracle auf.

**Mess-Status.** GEMESSEN POSITIV (Funktion, nicht EV): eigener Selbsttest gruen —
`python -m pokerbot.coach.decision_log` prueft Schema-Schluessel, Nicht-Mutation, fp-Determinismus, Kollisionsfreiheit
und die Latenz. Teil des „11/11 module selftests green"-Gates (`docs/STATE.md:497`).

**Allein benutzbar?** Ja, wenn man `format_spot` mitnimmt. Wer ein eigenes Spot-Format hat, braucht nur die
`spot_fingerprint`-Idee (crc32 statt `hash`).

**Fallstricke.** Der Aufrufer MUSS den Record erst nach erfolgreichem `table.act()` in die Pending-Liste haengen —
sonst hinterlaesst jede illegale Aktion (HTTP 400) einen Geister-Record, der spaeter benotet wird. Das ist
Aufrufer-Disziplin, nicht vom Modul erzwungen.

---

### Referenz-Orakel — `pokerbot/coach/oracle.py`
**Zweck.** Liefert zu einem Decision-Record die Aktion einer Referenz-Politik: PRINCE v2.2 (der HU-Produktionsbot)
fuer heads-up-Spots, der neutrale Liga-Kern `tag` fuer Multiway-Spots.

**Schnittstelle.**
- `record_to_hu_state(rec: dict) -> dict` — projiziert einen (6-max-)Record auf den HU-`game.state()`-dict, den
  `PokerBot.decide` konsumiert; 1:1 modelliert nach `benchmark/gtowizard.py`. Wirft `ValueError`, wenn nicht genau
  2 Spieler aktiv sind.
- `class PrinceOracle(seed=7, stack: str|None=None, kanal="gym")` mit `.decide(rec) -> {source, action, amount,
  rationale}` — `stack` legt optional die AUSLESE-Guard-Kette (`wickle_decide`) um `decide`.
- `class SixMaxOracle(profile="tag")` mit `.decide(rec) -> {...}`.
- `oracle_decision(rec) -> dict` — routet nach `n_active == 2`.
- `oracle_diff(rec, oracle=None) -> {"match": bool, "oracle_action": str, "size_diff_frac": float|None,
  "oracle": dict}` — `size_diff_frac` = |Mensch-TO − Orakel-TO| / Pot-as-faced, nur wenn BEIDE aggressiv sind.

**Eingabe/Ausgabe.** Rein: der `trainer.decision.v1`-Record. Raus: die obigen dicts; Betraege sind Commit-TO-
Strassentotale in Chips, `allin` loest zu `legal["raise_max"]` auf. Jede synthetisierte Aktion laeuft durch
`api.legalize` (`_legalized`), bevor sie zurueckkommt.

**Abhaengigkeiten.** Hart: `pokerbot.strategy.bot.PokerBot` (lazy importiert), `pokerbot.strategy.gto_mode`,
`pokerbot.arena.sixmax._decide` + `PROFILES`, `pokerbot.brain.api.legalize`. Ersetzbar nur, indem man eine eigene
Referenzpolitik einsetzt — die Schnittstelle (`.decide(rec)`) ist schmal.

**Zustand.** Modul-Singletons `_PRINCE` / `_SIXMAX`. Sie LERNEN NICHT (die Lernpfade `observe_opponent` /
`observe_hand_end` werden bewusst nie aufgerufen) und werden vor jedem Aufruf mit `random.Random(rec["spot_fp"])`
neu geseedet — deshalb ist Reuse sicher und die Benotung wiederholbar. Nichts muss zurueckgesetzt werden.

**Kosten.** Nicht direkt gemessen. Das Modul schaltet `use_resolver`/`use_turn_resolver` explizit AUS, mit der
Begruendung, ein kalter River-Solve koste Sekunden (`oracle.py:172-174`) — das ist die Latenz-Entscheidung dieses
Moduls.

**Mess-Status.** GEMESSEN POSITIV (Funktion): eigener Selbsttest gruen, Teil des 11/11-Gates
(`docs/STATE.md:497`). Als 6-max-SPIELER ist die HU-Projektion REFUTIERT (siehe six_server: hybrid-Arme
−21,7 bis −26,6 bb/100, Journal `VERDRAHTUNG-6MAX-VERDIKT`) — als BENOTUNGS-Referenz bleibt sie im Einsatz und
wird im Text ehrlich „Bot-Einschaetzung" genannt.

**Allein benutzbar?** Ja, wenn man PRINCE bzw. den Liga-Kern mitnimmt. Wer nur den Adapter will:
`record_to_hu_state` ist unabhaengig und zeigt sauber, wie man einen n-Spieler-Spot auf einen HU-Solver kippt.

**Fallstricke.** Die Env-Flags (`POKERB_PRINCE=1` + `gto_mode.apply()`) werden beim Modul-Import gesetzt, VOR jedem
Strategie-Import. Wer `pokerbot.strategy` vorher importiert, benotet gegen eine andere Politik als gedacht — und
merkt es nicht. Zweitens: `state["hand_id"]` darf nicht fehlen, sonst greift ein skalarer Fallback im Bot
(`LINE_U`) und die Entscheidung wandert.

---

### Grader — `pokerbot/coach/grader.py`
**Zweck.** Benotet EINEN Decision-Record mit vier billigen deterministischen Checks plus dem Orakel-Diff und
vergibt daraus eine Note aus `{ok, teuer, leak}`.

**Schnittstelle.**
- `grade_decision(rec: dict) -> dict` — mutiert den Record IN PLACE: setzt `checks`, `oracle`, `grade`,
  `grade_typ`, `confidence`, `erklaerung_kurz`, `grade_ms`.
- Einzeln aufrufbar: `check_pot_odds(rec)`, `check_mdf(rec)`, `check_sizing(rec)`, `check_advisor(rec)`.
- `assemble_grade(checks, oracle_diff, street, n_active) -> {grade, grade_typ, confidence, erklaerung_kurz}`.
- `prewarm() -> dict` — einmalig beim Serverstart: laedt die Advisor-Netze, baut einen Wegwerf-`PokerBot` und
  benotet einen synthetischen Record; gibt eine Verfuegbarkeits-Map zurueck.
- Schwellen als Modul-Konstanten: `POT_ODDS_TOLERANCE 0.05`, `MDF_SMALL_BET_X 0.5`, `SIZING_ERR_HARD 0.5`,
  `MIX_SUPPORT 0.15`, `OK_SIZE_DIFF 0.25`, `EQUITY_ITERS 600`.

**Eingabe/Ausgabe.** Rein: der Record. Raus (im Record): `checks = {pot_odds{req, eq_max, violated},
mdf{mdf, size_faced, strength, violated}, sizing{human_frac, snapped_frac, err, violated},
advisor{available, node, role, dist{aktion:p}, chosen, p_chosen}}`, dazu `grade` ∈ {ok, teuer, leak},
`grade_typ` ∈ {pot_odds, mdf, sizing, advisor_freq, oracle_diff} und ein `confidence`-Label
(„Mathe (unanfechtbar)" / „Solver-Frequenz (HU-trainiert, Naeherung)" / „Bot-Einschaetzung").
Die Regel: `leak` NUR bei einer harten Mathe-Verletzung, nie weil eine Referenz fehlte; `ok` bei gemischtem
Support (Advisor-Frequenz ≥ 15 %), Orakel-Treffer oder nahem Sizing; sonst `teuer`.

**Abhaengigkeiten.** Hart: `pokerbot.brain.api` (equity/required_equity/mdf/hand_rank),
`pokerbot.brain.understanding` (Position, `STRONG_MADE`), `pokerbot.strategy.advisor` (die Solver-Frequenz-MLPs),
`pokerbot.strategy.postflop.snap_to_tree/snap_raise_to_tree`, `gto_mode`. Weich: `coach.oracle` — fehlt es oder
wirft es, degradiert der Diff zu `{"source": "none"}` und die Note bleibt moeglich.

**Zustand.** Zustandslos pro Aufruf. Die Advisor-Netze und Blueprint-Caches sind Modul-global und read-only.

**Kosten.** Erste benotete Hand nach `prewarm()` 7,8 ms (`docs/STATE.md:494`); ohne Prewarm kostete allein der
erste `decide()` ~1,6 s von 800 ms Budget. Der Autotest gated den Median der Benotungs-Latenz auf 250 ms
(`autotest.py:36 MEDIAN_GRADE_MS_BUDGET`).

**Mess-Status.** GEMESSEN POSITIV (Funktion + Sanity): Selbsttest gruen; Autotest 8/8 ueber 800 Haende /
1411 Entscheidungen (`docs/STATE.md:496`). Die Sanity-Pruefung „station wird schlechter benotet als tag" trennt
erst ab ~300 benoteten Entscheidungen je Profil sauber — bei ~120 lagen die Raten im Rauschen (.057 vs .059,
`docs/STATE.md:494-496`), darum WARNt der Autotest bei kleinen Laeufen statt zu scheitern. KEINE EV-Messung: der
Grader spielt nicht, er benotet.

**Allein benutzbar?** Nur mit `brain/api` + `brain/understanding` + `strategy/advisor` + `strategy/postflop`. Die
vier Checks einzeln sind aber lesbare, uebernehmbare Rezepte; `check_pot_odds` braucht nur eine Equity-Funktion.

**Fallstricke.** Die Pot-Konventionen sind die Fehlerquelle Nr. 1 und im Docstring festgenagelt:
`required_equity(to_call, pot)` mit Pot AS-FACED (Villains Bet ist schon drin), `mdf(bet, pot)` mit dem PRE-Bet-Pot
(`spot.pot - spot.to_call`). Wer eines von beiden verwechselt, bekommt systematisch falsche Noten, die trotzdem
plausibel aussehen. Zweitens: `check_advisor` fragt das Netz nach POSITION, das Orakel intern nach INITIATIVE —
zwei verschiedene Groessen aus demselben Netz, die nebeneinander im Record stehen und nicht verwechselt werden
duerfen.

---

### Deutsche Feedback-Templates — `pokerbot/coach/templates_de.py`
**Zweck.** Rendert benotete Records in warme deutsche Saetze; rechnet selbst NICHTS und entscheidet NICHTS.

**Schnittstelle.**
- `render_decision_feedback(rec: dict) -> {"text", "html", "terms"}` — eine Entscheidung, 1–2 Saetze.
- `render_hand_feedback(records: list[dict], hand_result: dict|None=None, mode="gto") -> {"text","html","terms"}`
  — nur die suboptimalen Entscheidungen, je eine Zeile mit Strassen-Tag + Grund + Bot-Frequenzen, danach der
  Strategie-Abschnitt (Range-Erzaehlung).
- Hilfsformatierer, die einzeln nuetzlich sind: `eins_von(p)`, `freq_vergleich(p)`, `pot_frac_de(frac)`,
  `equity_satz(eq, req)`.
- `TERMS_USED` — frozenset aller Glossar-Term-Ids, die diese Templates emittieren koennen.

**Eingabe/Ausgabe.** Rein: der benotete Record; jeder Zugriff geht ueber `.get()` mit deutschem Fallback. Ein
unbekannter `grade` wirft bewusst `ValueError` (Vokabular gepinnt: `ok`/`teuer`/`leak`). Raus: `text` (Klartext),
`html` (mit Glossar-Spans via `glossar_de.markup`, Fallback = text), `terms` (die vorkommenden Term-Ids).

**Abhaengigkeiten.** Weich: `coach.glossar_de` (ohne es faellt `html` auf `text` zurueck), `coach.range_story`
(ohne es faellt die Erzaehlung auf die alte Heuristik zurueck). Sonst stdlib.

**Zustand.** Zustandslos, deterministisch.

**Kosten.** Nicht gemessen; laeuft im 800-ms-Handende-Budget mit.

**Mess-Status.** GEMESSEN POSITIV (Funktion): Selbsttest prueft Branch-Abdeckung, Determinismus und
TERMS_USED-Abdeckung; Teil des 11/11-Gates (`docs/STATE.md:497`).

**Allein benutzbar?** Ja — es ist reines dict→Text. Wer eigene Records baut, muss nur `grade`, `grade_typ` und die
`checks` fuellen.

**Fallstricke.** Die Sprachschicht darf keine Zahl NEU rechnen; alle Zahlen muessen im Record stehen. Wer hier
„schnell" eine Groesse ableitet, bricht die Konvention und riskiert einen Text, der der Note widerspricht.

---

### Sprach-Vertrag + LLM-Backend — `pokerbot/coach/language.py`
**Zweck.** Pinnt das Payload-Schema `coach.v1` zwischen Grader, Templates und optionalen Render-Backends und
gatet LLM-Text auf die Zahlen aus dem Payload.

**Schnittstelle.** `make_payload(...) -> dict`, `validate_payload(payload) -> dict` (wirft bei Vokabular-Drift),
`validate_numbers(text, payload) -> list[str]` (gibt die Zahlen zurueck, die im Text stehen, aber NICHT im
Payload), `get_backend(name="templates") -> LanguageBackend`, `class TemplateBackend`, `class OllamaBackend`
(lokales `qwen3:8b` ueber `http://localhost:11434`, harte Timeout-Grenze 2 s, Fallback auf Templates).

**Eingabe/Ausgabe.** Payload-Schema: `{schema:'coach.v1', mode, hand_id, street, hero_pos, grade, grade_typ,
confidence, human_action{action, amount_bb?}, oracle_action|None, numbers{equity_pct?, required_equity_pct?,
mdf_pct?, pot_bb?, to_call_bb?, bet_frac_pot?, snapped_frac_pot?, advisor_*_pct?, spr?, ev_diff_bb?},
strategic|None, mixed{is_mixed, dist}|None, glossar_terms[]}`. Fehlende Werte werden WEGGELASSEN, nie als 0
gesetzt.

**Abhaengigkeiten.** `coach.templates_de` fuer das Template-Backend; `requests`/urllib fuer Ollama. Ohne Ollama
laeuft alles ueber Templates.

**Zustand.** Ein Modul-Zaehler `FALLBACKS`.

**Kosten.** Ollama-Timeout hart auf 2,0 s (`OLLAMA_TIMEOUT_S`); danach Templates.

**Mess-Status.** UNGEMESSEN als Produkt-Hebel. Selbsttest gruen (Teil des 11/11-Gates). Das LLM-Backend ist im
ausgelieferten Pfad NICHT verdrahtet — `six_server` ruft `templates_de` direkt.

**Allein benutzbar?** Ja. `validate_numbers` ist der uebertragbare Teil: die Regel „ein LLM darf umformulieren,
aber keine Zahl erfinden" ist hier als pruefbare Funktion implementiert.

**Fallstricke.** Die Zahlen-Whitelist muss Board-Zaehlungen („3 Karten") und lexikalische Formen („3-Bet") von
echten Zahlen unterscheiden — dafuer gibt es Sonderregeln (`_BOARD_COUNT_WHITELIST`, `_LEXICAL_NUM_RE`). Wer
eigene Texte gaten will, faellt genau darueber.

---

### Glossar — `pokerbot/coach/glossar_de.py`
**Zweck.** Die einzige Registry deutscher Poker-Begriffe des Coaching-Layers plus der Markup-Mechanismus, der sie
im Text klickbar macht.

**Schnittstelle.** `term(name, text=None) -> dict|str|None`, `get(term_id) -> dict`, `markup(text) -> str`
(setzt `<span class="term" data-term="...">`), `as_json() -> list[dict]` (die Route `GET /api/glossary`),
`all_terms() -> set[str]`.

**Eingabe/Ausgabe.** Eintrag: `{begriff, synonyme[], erklaerung (1–3 Saetze, ≤ 220 Zeichen), formel?, quelle?}`.
Formeln/Quellen stammen aus den Docstrings in `knowledge_base/math/formulas.py`.

**Abhaengigkeiten.** Keine ausser stdlib.

**Zustand.** Zustandslos (Modul-Konstanten + kompilierte Regexe).

**Kosten.** Nicht gemessen.

**Mess-Status.** GEMESSEN POSITIV (Abdeckung): 61 Eintraege (`docs/STATE.md:497`), Mindestanforderung
`MIN_ENTRIES = 50`; Selbsttest prueft Laengenlimit und Markup-Idempotenz.

**Allein benutzbar?** Ja — es ist eine Datei mit Text plus zwei Regex-Funktionen.

**Fallstricke.** `markup()` darf nicht doppelt laufen: bereits gesetzte Spans werden per `_SPAN_RE` uebersprungen.
Wer den Text vorher HTML-escaped, zerstoert die Erkennung.

---

### Session-Registry — `pokerbot/coach/registry.py`
**Zweck.** Append-only-JSONL mit einer Start- und einer End-Zeile je Trainer-Session, weil das Modul-Global
`SESSION` bei „Neu" komplett stirbt.

**Schnittstelle.** `register_start(session) -> dict|None`, `register_end(session) -> dict|None`,
`sessions(path=None) -> list[dict]` (faltet Start/End je `session_id`, letzter gewinnt, Reihenfolge = erstes
Auftreten). Pfad: `data/trainer/registry.jsonl`.

**Eingabe/Ausgabe.** Rein: ein duck-typed Session-Objekt (`session_id`, `path`, `decisions_path`, `table`,
`bots`, `mode`, `hands_done`, `human_net`). Raus: Start-Zeile `{event:'start', session_id, ts, mode, stack_bb,
session_log_path, decisions_path, profile_assign, fingerprint}` — `fingerprint` = `gto_mode.fingerprint()`, also
der exakte Flag-Satz, unter dem benotet wurde. End-Zeile `{event:'end', session_id, ts, hands_done, human_net}`.

**Abhaengigkeiten.** `pokerbot.strategy.gto_mode.fingerprint`, `pokerbot.web.session_log.append_record`,
`pokerbot.config`. Alle ersetzbar.

**Zustand.** Je Session zwei Zeilen; sonst zustandslos. Kaputte Zeilen ueberspringt der Leser.

**Kosten.** Nicht gemessen (zwei Appends je Session).

**Mess-Status.** GEMESSEN POSITIV (Funktion): Selbsttest prueft Faltung, Torn-Line-Toleranz und dass ein
Schreibfehler nur eine Warnung erzeugt; Teil des 11/11-Gates.

**Allein benutzbar?** Ja.

**Fallstricke.** Der Modus kommt BINDEND aus der Session, nie aus einer Env-Variable — sonst waere die Provenienz
der Benotung falsch. Und: `register_end` muss VOR dem Ersetzen der Session laufen, sonst fehlt die End-Zeile
dauerhaft.

---

### Schwierigkeitsregler — `pokerbot/coach/difficulty.py`
**Zweck.** Uebersetzt die Fehlerrate der letzten Session in eine haertere oder weichere Gegner-Besetzung.

**Schnittstelle.** `error_rate(decision_records) -> (rate, n)`, `default_composition(mode="gto") -> dict`,
`update(session_error_rate, current_composition, n=None) -> dict` (pur, hoechstens EIN Schritt),
`load_state()`, `save_state(composition, rate, n, ts)`, `current_assignment() -> {seat: profil}`.

**Eingabe/Ausgabe.** Komposition: `{tier: int, profiles: {seat: profilname}, exploit_gain: float, mode: str}`.
Leiter `PRESET_LADDER` T0…T4 (T2 = die Default-Belegung tag/lag/nit/station/maniac). Zielband
`TARGET_BAND = (0.10, 0.20)`, unter `MIN_DECISIONS = 30` bewegt sich nichts. Der `exploit_gain`-Feindial existiert
nur im Exploit-Modus. Zustandsdatei `data/trainer/difficulty.json`.

**Abhaengigkeiten.** `pokerbot.config` (nur DATA_DIR); die Profilnamen muessen in `arena/sixmax.PROFILES` existieren.

**Zustand.** Eine JSON-Datei; Verlust ist harmlos (Default T2).

**Kosten.** Nicht gemessen (pure Arithmetik).

**Mess-Status.** UNGEMESSEN als Lern-Effekt. Das 10–20-%-Band ist im Docstring selbst als HYPOTHESE deklariert
(85-%-Regel), nicht als Messung. Der Regler-Code ist per Selbsttest gruen.

**Allein benutzbar?** Ja, vollstaendig — `update` ist eine reine Funktion ohne Import ausser `config`.

**Fallstricke.** `six_server` ruft den Regler nur im `gto`-Modus und nur, wenn die Registry eine VORIGE Session
mit `error_rate` kennt (`six_server.py:129-135`). Wer testet, ohne dass eine beendete Session in der Registry
steht, sieht nie eine Anpassung und haelt das Modul faelschlich fuer tot.

---

### Replay-Compiler — `pokerbot/coach/replay.py`
**Zweck.** Baut aus einem Hand-Record (+ den benoteten Entscheidungen) eine geordnete Schrittliste zum Abspielen.

**Schnittstelle.** `compile_replay(hand_record: dict, decision_records: list[dict]|None=None) -> dict`;
`load_last_hand(session_path, decisions_path) -> (hand_record, decisions)`.

**Eingabe/Ausgabe.** Rein: das `build_hand_record`-dict und die `trainer.decision.v1`-Records. Raus:
`{hand_no, button, sb, bb, human_seat, positions, hero_hole, board, steps[], result, net, final_pot}`.
Blinds und der 3/1/1-Board-Reveal werden rekonstruiert (sie fehlen im Record, weil `session_log` die
`blinds`/`deal`-Events wegfiltert). Pot-Mathematik folgt der Table-Semantik: `call` = zugefuegte Chips,
`bet`/`raise` = Strassen-Commit-TO.

**Abhaengigkeiten.** Keine — reines dict→dict, kein FastAPI, kein Engine-Import.

**Zustand.** Zustandslos.

**Kosten.** Nicht gemessen.

**Mess-Status.** GEMESSEN POSITIV (Funktion): Selbsttest gruen. Bei der Integration wurden hier zwei ECHTE Defekte
gefunden und behoben: das Coach-Matching verglich `hand_no` gegen die `<session>-<hand_no>`-`hand_id` (Ergebnis:
0 Coach-Texte im Replay) und das Verdikt lag verschachtelt unter `oracle` (`docs/STATE.md:491-493`).

**Allein benutzbar?** Ja, das sauberste Uebernahme-Modul dieses Verzeichnisses.

**Fallstricke.** Die Bot-Karten: `hole{}` enthaelt ALLE Haende. Der Compiler zeigt fremde Karten nur ueber
`result["shown"]`, wenn `result["reveal"]` wahr ist — wer den Record direkt rendert, verraet dem Trainierenden
versehentlich alles und macht das Feedback ergebnisorientiert.

---

### Gegner-Panel — `pokerbot/coach/opponent_panel.py`
**Zweck.** Uebersetzt die Reads, die die Liga-Bots ueber den Menschen gelernt haben, in deutsche Saetze
(„Sitz 3 hat bemerkt: du foldest oft auf River-Bets").

**Schnittstelle.** `was_bot_gelernt(bots: dict) -> list[{seat, name, beobachtung_de}]` — max. 4 Eintraege
(`MAX_OBSERVATIONS`), aufgefuellt auf mindestens 2 mit ehrlichem Leerstand („noch nicht genug Daten").

**Eingabe/Ausgabe.** Rein: `{seat: SixMaxBot}` aus der Session. Raus: die Liste oben, `beobachtung_de` bereits mit
Glossar-Markup.

**Abhaengigkeiten.** Weich, aber inhaltlich hart an `arena/sixmax` gekoppelt: die Trigger-Schwellen werden aus
`READ_THREEBET_HAPPY/READ_OVERFOLD/READ_STATION/READ_AGGRO_HI/READ_AGGRO_LO` importiert, mit gespiegelten Literalen
als Fallback plus einer Drift-Wache im Selbsttest.

**Zustand.** Zustandslos; der Zustand lebt in den Gegnermodellen der Bots.

**Kosten.** Nicht gemessen.

**Mess-Status.** GEMESSEN POSITIV (Funktion): Selbsttest mit synthetischem OppModel. Der EV-Nutzen der
zugrundeliegenden Reads ist dagegen REFUTIERT (Exploit-Gate: alle 8 Diffs ≤ 0, gepoolt ≈ −12 bb/100,
`docs/STATE.md:53-55`) — das Panel bleibt als LEHRMITTEL nuetzlich, obwohl der Exploit selbst abgeschaltet ist.

**Allein benutzbar?** Nur mit der Liga (`arena/sixmax`) — die Schwellen sind exakt deren Schwellen.

**Fallstricke.** Die Schwellen MUESSEN gespiegelt bleiben. Zeigt das Panel Reads, auf die die Bots gar nicht
reagieren, lernt der Mensch etwas Falsches — deshalb der Import statt eigener Konstanten.

---

### Session-Report — `pokerbot/coach/trainer_report.py`
**Zweck.** Fasst eine Trainings-Session aus den beiden JSONL zu einem deutschen Rueckblick zusammen.

**Schnittstelle.** `report(session_path, decisions_path) -> dict`; `format_report_text(rep) -> str`.

**Eingabe/Ausgabe.** Raus: `{n_hands, n_decisions, grade_dist{ok,teuer,leak}, error_rate, leak_top[],
stats{...}, best_moment, teuerstes_moment, narrative_de}`. `leak_top` = die drei haeufigsten `grade_typ`-Eimer.
Alle Zugriffe key-tolerant per `.get()`.

**Abhaengigkeiten.** Keine ausser stdlib (liest nur JSONL).

**Zustand.** Zustandslos.

**Kosten.** Nicht gemessen.

**Mess-Status.** GEMESSEN POSITIV (Funktion): Selbsttest mit synthetischen Haenden/Entscheidungen; Teil des
11/11-Gates.

**Allein benutzbar?** Ja.

**Fallstricke.** Der Report benotet ausdruecklich KEINE Ergebnisse — wer eine bb/100-Zeile ergaenzt, kippt die
Fairness-Doktrin und erzeugt genau die Ergebnisorientierung, gegen die die ganze Kette gebaut ist.

---

### Range-Erzaehlung — `pokerbot/coach/range_story.py`
**Zweck.** Erzeugt den Strategie-Abschnitt des Hand-Feedbacks aus einer ECHT gerechneten Range-Rekonstruktion
(„Preflop repraesentiert der Gegner top 5 % … du repraesentierst einen Flush-Draw").

**Schnittstelle.** `build_story(records, hand_result=None) -> list[str]` (bei jedem harten Problem `[]`, dann
faellt `templates_de` auf die alte Heuristik zurueck); `class StoryTracker(RangeTracker)`;
`make_seeded_tracker(villain_pos: str|None, villain_raised: bool|None) -> type` — eine Tracker-Klasse mit
6-max-Positions-Prior statt HU-Prior.

**Eingabe/Ausgabe.** Rein: die Decision-Records einer Hand + `table.result`. Raus: Liste deutscher Saetze.
Prioren als Konstanten: `RAISER_FRAC {1:0.20, 2:0.09, 3:0.04}`, `CALLER_FRAC {0:0.55, 1:0.28, 2:0.12, 3:0.06}`,
`OPEN_FRAC` je Position (UTG 0.15 … BTN 0.42).

**Abhaengigkeiten.** Hart: `strategy.range_tracker.RangeTracker`, `engine.equity.equity_vs_weighted_range`,
`coach.oracle.record_to_hu_state`, die `made_class`-Taxonomie des Evaluators.

**Zustand.** Je Hand ein Tracker; MC-Equity deterministisch aus `spot_fp` + Strasse geseedet.

**Kosten.** `EQ_ITERS = 200` fuer Flop/Turn (~3,5 pp SE, laut Kommentar „fuer eine Erzaehlung genug"), River
enumeriert exakt. Absolute Latenz nicht gemessen; sie laeuft im 800-ms-Handende-Budget mit (deshalb waermt
`grader.prewarm` explizit auch die Turn/River-Netze vor).

**Mess-Status.** UNGEMESSEN als Lern-Effekt. Der 6-max-Positions-Prior ist als Verdrahtung dokumentiert:
`make_seeded_tracker` gibt UTG 194 bis BTN 552 Combos statt der HU-1102 (`docs/STATE.md:425-426`). Selbsttest
gruen.

**Allein benutzbar?** Nur mit Tracker + Equity-Engine. `make_seeded_tracker` ist der wiederverwendete Teil — die
Snowie-Bruecke und der 6-max-Takeover benutzen exakt diese Fabrik.

**Fallstricke.** Die Tracker-Prioren des Live-Bots sind HU-kalibriert (SB-Open 84 % aller Haende). Wer sie
unveraendert als 6-max-Lehrtext ausgibt, erzaehlt dem Menschen Unsinn — genau deshalb ueberschreibt `StoryTracker`
NUR die Preflop-Prioren und laesst die Postflop-Updates unangetastet.

---

### Autotest-Harness — `pokerbot/coach/autotest.py`
**Zweck.** Laesst Liga-Bots den Menschen-Sitz durch den KOMPLETTEN Trainer-Stack spielen und prueft, ob Logger →
Grader → Renderer → Report N Haende ohne Absturz, im Latenz-Budget und mit plausibler Notenverteilung ueberleben.

**Schnittstelle.** `run_all(hands) -> dict`, `run_arm(client, six_server, profile, mode, hands, seed, ...)`,
`normalize_action(dec, legal) -> (action, amount)`; CLI
`python -m pokerbot.coach.autotest [hands] [--hands N] [--deep] [--json PATH] [--selftest]`.
Acht Checks: `_zero_crash`, `_decisions_schema`, `_grade_latency`, `_grade_distribution_sanity`,
`_feedback_nonempty`, `_report_builds`, `_mode_toggle`, `_replay_reconstructs`.

**Eingabe/Ausgabe.** Rein: nichts ausser Parametern; faehrt `six_server` per `fastapi.testclient.TestClient`.
Raus: ein Ergebnis-dict + Exit-Code (0 = PASS/WARN, 1 = FAIL). Gates: `MEDIAN_GRADE_MS_BUDGET = 250`,
`DEEP_HANDS = 300`, Vokabular `{ok, teuer, leak}`.

**Abhaengigkeiten.** `six_server`, die gesamte Coach-Kette, `arena/sixmax`, `fastapi.testclient`.

**Zustand.** Ein persistenter injizierter RNG pro Arm (bewusst KEIN per-Spot-Reseed — das waere Fake-Mixing).

**Kosten.** Nicht als Wandzeit dokumentiert; der Deep-Lauf sind 300 Haende je Arm.

**Mess-Status.** GEMESSEN POSITIV: „autotest 8/8 PASS over 800 hands / 1411 decisions" (`docs/STATE.md:496`).
Wichtige Einschraenkung, gemessen: bei ~120 benoteten Entscheidungen je Profil liegen station- und tag-Fehlerraten
im Rauschen (.057 vs .059) — saubere Trennung erst ab 300+ (`docs/STATE.md:494-496`); kleine Laeufe WARNen daher.

**Allein benutzbar?** Nur mit dem Server. Uebertragbar ist das Muster: eine bewusste Fehl-Probe (Grader so
patchen, dass Records ohne `grade` geschrieben werden) beweist, dass der Harness ueberhaupt erkennt.

**Fallstricke.** Der Treiber MUSS `bet` zu `raise` normalisieren und Betraege in `[raise_min, raise_max]` klemmen,
sonst antwortet der Server mit 400 und `zero_crash` scheitert faelschlich.

---

### GTOW-Export der Trainer-Haende — `pokerbot/coach/export_gtow.py`
**Zweck.** Schreibt eine Trainer-Session als PokerStars-6-max-Handhistorie, damit der GTO-Wizard-Analyzer die
eigenen Noten unabhaengig gegenprueft.

**Schnittstelle.** `export_session(session_path, out_path=None, ledger_path=None) -> {n_hands, idbase, out,
warnungen}`; `record_to_export(rec) -> dict`; `class ExportError(ValueError)`; CLI `main()`.

**Eingabe/Ausgabe.** Rein: `session_<sid>.jsonl`. Raus: eine `.txt` mit CRLF-Zeilenenden (der Analyzer parst nur
CRLF) und ein Ledger-Eintrag `{idbase, n_hands, file, session, ts}`. Fehlende `deal`-Events bei All-in-Runouts
werden synthetisch injiziert, weil der 6-max-Exporter Strassen-Header NUR aus `deal`-Events erzeugt.

**Abhaengigkeiten.** Hart: `research.sixmax_export.format_hand`, `pokerbot.web.session_log.append_record`.

**Zustand.** Ein persistentes Ledger; `_fresh_idbase` vergibt einen frischen Block.

**Kosten.** Nicht gemessen.

**Mess-Status.** UNGEMESSEN als Export-Ergebnis (kein Analyzer-Grade einer Trainer-Session im Repo belegt). Das
Modul hat einen Selbsttest. Der 6-max-Analyzer-Anker des Bots selbst liegt bei 85,9 % GTO-Score / 7,61 EV-loss
(`docs/STATE.md:52-53`), stammt aber aus `research/sixmax_export.py`, nicht aus diesem Modul.

**Allein benutzbar?** Ja, mit `research/sixmax_export`.

**Fallstricke.** Hand-IDs VERBRENNEN beim ersten Kontakt — auch bei einem gescheiterten Upload. Das Ledger wird
deshalb VOR dem Schreiben der Datei fortgeschrieben. Wer einen `idbase` wiederverwendet, ruiniert die
Analyzer-Historie. Und: exportiert werden die ROHEN Groessen des Menschen (kein Snapping), was Off-Tree-Warnungen
erzeugt — bewusst so, weil Snappen die Pot-Buchhaltung aller Folgestrassen verschoebe.

---

## Coach (LLM-Zweig und persoenliche Reports)

### Claude-Coach — `pokerbot/coach/coach.py`
**Zweck.** On-Demand-Coaching per Claude-API: erklaert den Bot-Zug, bewertet den eigenen Zug gegen die
Bot-Referenz, beantwortet freie Fragen.

**Schnittstelle.** `class Coach(model=None, language="de")` mit `.available -> bool`,
`.explain_move(state, hero_idx, decision) -> str`, `.review_user_move(state, hero_idx, user_action, user_amount,
bot_decision) -> str`, `.ask(question, state=None, hero_idx=0) -> str`; Modulfunktion
`describe_hand(state, hero_idx) -> str`.

**Eingabe/Ausgabe.** Rein: der `game.state()`-dict + die Bot-Entscheidung inkl. `rationale`. Raus: deutscher
Fliesstext. Ohne API-Key kommt ein ehrlicher Hinweistext statt einer Ausnahme; API-Fehler werden als
`(Coach-Fehler: ...)` zurueckgegeben.

**Abhaengigkeiten.** Hart: `anthropic` (Import auf Modulebene — deshalb ist der Import in `coach/__init__.py`
gekapselt, damit die Trainer-Module ohne das Paket importierbar bleiben), `pokerbot.config` (Key + Modell),
`knowledge_base/concepts` (wird in den gecachten System-Prompt injiziert, max. 180 Konzepte / 14 000 Zeichen).

**Zustand.** Der Wissens-String wird einmal je Instanz geladen; der System-Prompt nutzt
`cache_control: ephemeral`.

**Kosten.** Nicht gemessen. Es ist der einzige bezahlte Pfad in diesem Subsystem, und er laeuft nur auf
ausdruecklichen Klick, nicht pro Aktion.

**Mess-Status.** UNGEMESSEN (Textqualitaet, kein EV-Effekt). Smoke-Test: `tests/test_coach.py`.

**Allein benutzbar?** Ja, mit Key. `describe_hand` allein ist ein brauchbarer Zustands-Serialisierer.

**Fallstricke.** Der Coach sieht `state(hide=BOT)` — die Bot-Karten sind darin `??`. Wer ihm versehentlich den
vollen State gibt, bekommt Erklaerungen, die auf verdeckten Karten beruhen, und der Trainierende lernt
Ergebnisorientierung.

---

### CoinPoker-Parser — `pokerbot/coach/coinpoker.py`
**Zweck.** Liest CoinPoker-Handhistorien und macht aus jeder Hero-Entscheidung einen kanonischen `Spot`.

**Schnittstelle.** `parse_file(path) -> list[Hand]`, `hero_decisions(hand) -> list[Decision]`
(je `Spot` + tatsaechlich gespielte Aktion), `summary(hand) -> dict`; Dataclasses `Hand`, `Decision`.

**Eingabe/Ausgabe.** Rein: `.txt` im CoinPoker-Format (Chips in ₮ ≈ $; „raises X to Y" mit Y = Total, „bets X",
„NAME: ALLIN X" mit X = Zuwachs, „collected ₮X from pot" OHNE Doppelpunkt). Raus: `Spot`-Objekte aus
`pokerbot/brain/format_spot.py`.

**Abhaengigkeiten.** Hart: `pokerbot.brain.format_spot`.

**Zustand.** Zustandslos.

**Kosten.** Nicht gemessen.

**Mess-Status.** UNGEMESSEN.

**Allein benutzbar?** Ja, wenn man das `Spot`-Format uebernimmt. Sonst ist es ein site-spezifischer Parser.

**Fallstricke.** Die Betragssemantik wechselt je Verb (Total bei `raises to`, Zuwachs bei `ALLIN`). Wer das
vermischt, baut eine Pot-Buchhaltung, die erst zwei Strassen spaeter auffaellt.

---

### Persoenliche Hand-Review — `pokerbot/coach/review_session.py`
**Zweck.** Coacht die EIGENEN CoinPoker-Haende des Nutzers: Spot → Engine-Grundlage (`understanding.
strategic_read` + `api`-Equity) → Claude → Markdown-Report + Leak-Rollup.

**Schnittstelle.** `coach_decision(dec, provider="claude") -> (dict, tuple)`; CLI
`python -m pokerbot.coach.review_session --hh "<pfad>" --stakes 2,5 --limit 25 --out data/coach/report.md`.

**Eingabe/Ausgabe.** Rein: CoinPoker-HH + Filter (Stakes, Limit, Daten). Raus: Markdown + Leak-Aggregat.

**Abhaengigkeiten.** `coach.coinpoker`, `brain.format_spot`, `brain.understanding`, `brain.api`, `research.llm`.

**Zustand.** Zustandslos je Lauf.

**Kosten.** Bezahlt (ein LLM-Call je Entscheidung). Nicht gemessen.

**Mess-Status.** UNGEMESSEN. Der Docstring sagt selbst: per-Session bb/100 ist Rauschen; der Wert liegt im
per-Entscheidungs-Grading und im Leak-Trend ueber Sessions.

**Allein benutzbar?** Nur mit dem `brain/`-Stack und einem API-Key.

**Fallstricke.** Keine Gegenprobe: der LLM-Text wird hier NICHT wie in `language.validate_numbers` gegatet. Wer
das produktiv nutzt, sollte das Gate nachruesten.

---

### Deep-Report-Pipeline — `pokerbot/coach/{deep_report, report_synth, report_charts, build_report}.py`
**Zweck.** Vier Stufen, die aus einer CoinPoker-Historie ein langes deutsches PDF-Portrait machen: `deep_report`
rechnet (A/B/C-Game-Phasen, Varianz-Amplitude, Sizing-Entropie, beobachtete Ranges) → `report_synth` laesst
OpenAI die Prosa schreiben und berechnet die „Poker-IQ"-Dimensionen deterministisch → `report_charts` malt PNGs
mit Pillow → `build_report` setzt das PDF mit reportlab.

**Schnittstelle.** Je Modul ein `main()`; wichtige Funktionen: `deep_report.sessions/variance_stats/
sizing_entropy/observed_ranges`, `report_synth.compute_iq(stats, cls) -> (dims, iq)`,
`report_charts.{phase_timeline, observed_range_matrix, confusion_chart, variance_chart, iq_radar, bot_sim_chart}`,
`build_report.build()`.

**Eingabe/Ausgabe.** Kette ueber Dateien: HH → `data/coach/deep_stats.json` → `synth.json` + PNGs →
`Spieler_Report.pdf`.

**Abhaengigkeiten.** `coach.coinpoker`, `research.llm` (nur `report_synth` ist bezahlt), `PIL`, `reportlab`.

**Zustand.** Dateibasiert, keine In-Memory-Kopplung.

**Kosten.** Nicht gemessen.

**Mess-Status.** UNGEMESSEN. Es sind Darstellungs-Werkzeuge, keine Bot-Hebel.

**Allein benutzbar?** Nur als Kette und nur fuer CoinPoker-Historien.

**Fallstricke.** Die Reports haben harte inhaltliche Regeln (kein Geld, keine „Verluste"/„Downswing", nur
low/mid/high), und `build_report.san()` sanitisiert jeden String beim Schreiben. Wer die Kette uebernimmt und die
Sanitisierung entfernt, bekommt Texte, die der Prompt-Vorgabe widersprechen.

---

### Stil- und Station-Simulationen — `pokerbot/coach/{style_sim, station_sim, build_station_pdf}.py`
**Zweck.** `style_sim` bildet den gemessenen Stil des Nutzers als `Knobs`-Profil ab und misst ihn gegen die
Trainings- und die Held-out-Liga; `station_sim` ist eine explizite Monte-Carlo-Studie gegen einen modellierten
Calling-Station (echte Karten, echte Showdowns, gepaarte A/B auf identischen Deals); `build_station_pdf` setzt
daraus einen mobilen PDF-Leitfaden.

**Schnittstelle.** `style_sim.run(n_hands=2000) -> dict`; `station_sim.compare(scenario, size, barrels, mega,
n, seed) -> dict` und `station_sim.run(n=6000) -> dict`; `build_station_pdf.build()`.

**Eingabe/Ausgabe.** Reine Parameter rein, Kennzahl-dicts bzw. ein PDF raus.

**Abhaengigkeiten.** `training/rl_env.py` + `arena/sixmax` (style_sim), Engine-Evaluator (station_sim),
`reportlab` (PDF).

**Zustand.** Zustandslos je Lauf, geseedet.

**Kosten.** `style_sim` laut Docstring ~5 min lokale CPU; `station_sim` nicht gemessen.

**Mess-Status.** UNGEMESSEN im Sinn des Bot-EV. Beide erzeugen Zahlen ueber MODELLIERTE Gegner, nicht ueber
gemessene. `station_sim` sagt das im Docstring selbst: die Liga war das falsche Instrument, deshalb der explizite
Gegner-Bau.

**Allein benutzbar?** `station_sim` ja (Engine-Evaluator genuegt), `style_sim` nur mit RL-Env und Liga.

**Fallstricke.** Beide Module messen gegen eine SELBSTGEBAUTE Gegnerannahme. Ergebnisse sind Hypothesen ueber die
Annahme, nie Evidenz ueber die reale Population.

---

### Meta-Coach — `pokerbot/coach/meta_coach.py`
**Zweck.** Steuert die Verbesserungs-Schleife zwischen Trainings-Checkpoints: JSON mit Metriken rein,
priorisierte Direktiven als JSON raus. Er spielt keine Haende.

**Schnittstelle.** `class MetaCoach` (Provider `anthropic` oder ein OpenAI-kompatibler Endpunkt), `main()` als
Demo auf echten Zahlen.

**Eingabe/Ausgabe.** Rein: Checkpoint-dict (Solver-Gaps, bb/100, aktuelle Parameter). Raus: strukturiertes JSON
mit Direktiven.

**Abhaengigkeiten.** Ein LLM-Provider.

**Zustand.** Zustandslos.

**Kosten.** Nicht gemessen (bewusst als „billig genug pro Checkpoint" ausgelegt).

**Mess-Status.** UNGEMESSEN. Gehoert zum LLM-Track, der im Repo als SEKUNDAER markiert ist.

**Allein benutzbar?** Ja, es ist ein duenner Prompt-Wrapper.

**Fallstricke.** LLM-Direktiven sind Hypothesen, keine Befunde. Ohne ein gepaartes Gate dahinter ist jede
uebernommene Direktive ungemessen — das ist im Repo mehrfach teuer bezahlt worden.

---

## Session-Analyse (`pokerbot/analysis/`)

### Session-Statistik — `pokerbot/analysis/session_analysis.py`
**Zweck.** Rechnet aus einem Session-JSONL die klassischen Kennzahlen des Menschen und laesst Claude einen kurzen
deutschen Kommentar dazu schreiben.

**Schnittstelle.** `compute_stats(recs: list[dict]) -> dict`, `narrative(stats) -> str`,
`analyze_session(path) -> {"stats": ..., "narrative": ...}` (das ist die Antwort von `POST /api/analyze`).

**Eingabe/Ausgabe.** Rein: `build_hand_record`-Zeilen. Raus: `{hands, vpip_pct, pfr_pct, threebet_pct,
postflop_aggression_factor, postflop{bets,raises,calls,folds}, went_to_showdown_pct, net_bb, bb_per_100,
avg_postflop_bet_bb}`.

**Abhaengigkeiten.** `pokerbot.config` + `anthropic` (nur fuer `narrative`; ohne Key kommt ein leerer String).

**Zustand.** Zustandslos.

**Kosten.** Nicht gemessen (ein Durchlauf ueber die Zeilen).

**Mess-Status.** UNGEMESSEN — Deskriptive Statistik, kein Hebel.

**Allein benutzbar?** Ja, mit dem JSONL-Format.

**Fallstricke.** Die Seat-Schluessel sind nach dem JSON-Roundtrip Strings; der Code fasst beide Faelle ab
(`net.get(hs, net.get(int(hs) ...))`). Und `_folded` prueft nur, OB der Mensch irgendwann gefoldet hat — als
Showdown-Filter ist das grob.

### Weitere Analyse-Skripte — `pokerbot/analysis/{session_deep, harvest_play, luck_vs_skill, pluribus_catalog}.py`
**Zweck.** `session_deep` erzaehlt ueber mehrere eigene Sessions hinweg (Meta-Muster, Tilt ueber Zeit, per Claude);
`harvest_play` verifiziert Reads aus zuletzt gespielten Sessions und misst die Preflop-Tendenzen der Bots;
`luck_vs_skill` zerlegt das Netto in Nicht-Showdown-Anteil (Fold-Equity) und Showdown-Anteil und schaetzt ueber
exakte Flop-Equity gegen die tatsaechlichen Gegnerhaende den Glueck-Anteil; `pluribus_catalog` parst die 10 000
Pluribus-Haende des PHH-Datensatzes nach `knowledge_base/hand_histories/pluribus_hands.jsonl` und aggregiert deren
Stats je Position.

**Schnittstelle.** Alle als `python -m pokerbot.analysis.<modul> [n_sessions]`; wiederverwendbare Funktionen:
`luck_vs_skill.flop_equity(hole, opp_holes, flop)`, `pluribus_catalog.parse_hand(path)` und
`classify_preflop(rec, seat)`, `session_deep.user_sessions()`.

**Eingabe/Ausgabe.** Session-JSONL bzw. PHH-TOML rein; Konsolentext bzw. eine JSONL raus.

**Abhaengigkeiten.** `analysis.session_analysis`, Engine-Equity, `tomllib`, optional `anthropic`.

**Zustand.** Zustandslos.

**Kosten.** Nicht gemessen.

**Mess-Status.** UNGEMESSEN. `luck_vs_skill` benennt seine Naeherung selbst: eine Session ist eine kleine
Stichprobe, und Flop-Equity als einziger Proxy fuer „got it in gut" ist grob.

**Allein benutzbar?** `pluribus_catalog` ja (nur der Datensatz noetig); die anderen brauchen unser Session-Format.

**Fallstricke.** Es sind Analyse-Einmal-Skripte, keine gepflegten Bibliotheken — sie erwarten das exakte
Log-Format und brechen bei Schema-Aenderungen.

---

## Vision (`pokerbot/vision/`)

### Snowie-Bilderkennung — `pokerbot/vision/snowie_local.py`
**Zweck.** Liest Karten aus dem PokerSnowie-4-Fenster rein lokal per Template-Matching — kein VLM, keine Kosten.

**Schnittstelle.** `window_bbox()`, `grab() -> Image`, `crop_frac(img, box)`, `match(glyph, kind) -> (label|None,
score)`, `read_card(img, key, learn=False)`, `read_cards(img=None, learn=False) -> dict`, `slot_occupied(img, key)
-> bool`, `suit_by_colour(glyph) -> list[str]`, `dump(img=None) -> str`; CLI `--dump`, `--read`, `--learn`.

**Eingabe/Ausgabe.** Rein: ein Screenshot (PIL). Raus: `{"hero": [karte|None, karte|None], "board": [...],
"unreadable": int}`. Karten sind die 2-Zeichen-Codes des Repos (`'As'`, `'Td'`). Templates liegen als PNG unter
`data/vision/snowie/tpl/<art>/<label>.png`.

**Abhaengigkeiten.** `numpy`, `PIL`, `ctypes` (Windows-DPI + Fenstersuche via
`vision.screen_reader.pick_window`). Windows-gebunden.

**Zustand.** Template-Cache; sonst zustandslos.

**Kosten.** Nicht als Millisekunden im Modul belegt. Die Gesamt-Lesung liegt bei ~0,1 s statt ~4 s VLM
(`snowie_bridge.py:187`).

**Mess-Status.** GEMESSEN POSITIV im Verbund (siehe Bruecke). Isoliert: die Schwellen sind live vermessen
(`MATCH_MIN = 0.72`, `MATCH_MARGIN = 0.05` — das beste Label muss das zweitbeste FREMDE Label klar schlagen).
Regressionsnetz `research/snowie_regress.py` (konservierte Tatorte beider Themes).

**Allein benutzbar?** Ja, aber nur fuer PokerSnowie 4 auf Windows: die Regionen sind als Bruchteile des Fensters
hart vermessen.

**Fallstricke.** Unsicher heisst None, nicht „bester Treffer". Wer die Margin-Regel aufweicht, um weniger Pausen
zu haben, bekommt still falsche Karten — die teuerste Fehlerklasse, weil nichts abstuerzt.

---

### Snowie-Tischzustand + Gatter — `pokerbot/vision/snowie_state.py`
**Zweck.** Liest den KOMPLETTEN Tischzustand (Sitze, Positionen, Stacks, Einsaetze, Pot, Buttons) und entscheidet
per Gatter, ob die Lesung gut genug ist, um darauf zu spielen.

**Schnittstelle.**
- `read_state(img=None, learn=False) -> dict` — die eine Hauptfunktion.
- `gate(s, strict_bets=True) -> str|None` — None = brauchbar, sonst der Grund zu PAUSIEREN.
- `duplicate_cards(s) -> str|None`, `implausible(s) -> str|None` — die zwei Plausibilitaets-Waechter.
- Bausteine: `dealer_seat(img)`, `seat_live(img, seat)`, `hero_turn(img)`, `position_of(dealer)`,
  `read_bets`, `read_buttons`, `read_number`, `read_numbers_batched`, `match_digit`.

**Eingabe/Ausgabe.** Raus: `{hero_turn, hero_cards, board, cards_unreadable, dealer, positions, hero_position,
live{seat:bool}, bets{seat:float}, stacks{seat:float|None}, pot, hero_bet, max_bet, buttons, can_check,
call_amount, raise_min_dollars, players_in_hand, unknown_bet}`. Betraege sind DOLLAR, nicht Chips.

**Abhaengigkeiten.** `vision.snowie_local`, `numpy`, `PIL`; optional Tesseract
(`C:\Program Files\Tesseract-OCR\tesseract.exe`) als zweite Zahlenquelle.

**Zustand.** Zustandslos pro Lesung. Der Verlaufs-Zustand (Position je Hand fixieren, Pot darf nie schrumpfen)
liegt bewusst in `snowie_bridge.HandTracker`.

**Kosten.** Belegt im Code: die Batch-OCR fuer Pot + alle Stacks kostet 131 ms statt 557 ms mit Templates
(`snowie_state.py:673-674`); der Einzel-OCR-Schiedsrichter im Konfliktfall ~340 ms
(`snowie_state.py:696-698`).

**Mess-Status.** GEMESSEN POSITIV im Verbund (siehe Bruecke). Jede Schwelle im Modul hat einen benannten Tatort:
Pot mit Zweitquellen-Pflicht, weil die Batch-OCR '39' als '539' las (das Waehrungszeichen wurde Ziffer); die
Plausibilitaets-Grenze, weil ein Stack als 14104 statt ~180 gelesen wurde und der Bot 206 Dollar in einen
9-Dollar-Pot raiste; Duplikat-Pruefung, weil ein Board live als `6s Ks 2h Jd 6s` gelesen wurde.

**Allein benutzbar?** Nur fuer PokerSnowie 4 auf Windows. Uebertragbar ist das GATTER-MUSTER, nicht die Geometrie.

**Fallstricke.** Die Reihenfolge im Gatter ist bedeutungstragend: die Lockerung `strict_bets=False` MUSS vor der
Einsatzniveau-Pruefung greifen, sonst verweigert sich die Eskalation mit genau dem Blocker, den sie umgehen soll
(`snowie_state.py:794-798`). Wer die Pruefungen umsortiert, baut diese Falle neu ein.

---

### Snowie-Bruecke — `pokerbot/vision/snowie_bridge.py`
**Zweck.** Die Spielschleife: Fenster lesen → Gatter → `obs` fuer unseren Bot → Entscheidung → ctypes-Klick, mit
Verlaufs-Waechtern und JSONL-Log.

**Schnittstelle.**
- `run(n_hands, strict, bb_dollars, probe) -> None`; CLI
  `python -m pokerbot.vision.snowie_bridge --probe | --hands 50 [--bb 2.0] [--loose]`.
- `read_local(img=None) -> dict` (delegiert an `snowie_state.read_state`).
- `to_obs_local(s, bb_dollars=2.0, committed=0.0) -> dict` — Dollar-Zustand → Engine-`obs`.
- `class HandTracker` — Positions- und Pot-Monotonie ueber eine Hand.
- `class StreetTracker` — Heros Strassen-Einsatz aus der STACK-DIFFERENZ statt aus der winzigen Einsatz-Schrift;
  `cur_bet = mein Einsatz + to_call` ist damit eine Identitaet.
- `class ActionLog` — rekonstruiert Gegner-Aktionen aus den Deltas zwischen Standbildern.
- `class PrinceHU` — baut aus der Vision-Lesung ein `trainer.decision.v1`-Record und laesst `PrinceOracle`
  entscheiden.
- `make_hero()` — der Multiway-Kern (`arena/sixmax` Profil `tag`, Reads AUS).
- `act(bbox, obs, decision, bb_dollars) -> str` — Entscheidung in Klicks.
- `esc_pressed()` — ESC beendet alles.

**Eingabe/Ausgabe.** `to_obs_local` liefert die tragenden Schluessel `hole, board, to_call, pot, my_stack, bb(=100),
n_active, position, preflop_raises, cur_bet, my_committed_street, street, can_check, can_call, can_raise,
raise_min, raise_max` — alles in Chips (bb = 100). Jede Entscheidung geht nach
`data/vision/snowie_session_<zeitstempel>.jsonl`.

**Abhaengigkeiten.** Hart: `vision.snowie_state`, `vision.snowie_local`, `arena.sixmax`, `coach.oracle.
PrinceOracle`, `coach.range_story.make_seeded_tracker`, `ctypes` (Klicks), `PIL`. Windows-gebunden.

**Zustand.** Je Hand: `HandTracker` (Position einmal fixieren, Pot darf nie schrumpfen), `StreetTracker`,
`ActionLog`. Je Lauf: Log-Datei, Stale-Zaehler (`MAX_STALE = 400`, `BLOCK_GIVEUP = 12`).

**Kosten.** GEMESSEN: 13,3 Haende/min, ~4 % Aussetzer, beide Themes (`docs/STATE.md:421-423`); eine lokale Lesung
~0,1 s statt ~4 s VLM, 0 statt ~4 ct pro Zug (`snowie_bridge.py:187`).

**Mess-Status.** GEMESSEN — und die Zahl braucht ihren Kontext: drei Marathon-Laeufe, 3 651 Haende roh, Konto
−$2 915; der BEREINIGTE Pool (3 114 saubere Haende) ergab **+3,2 bb/100, 95 %-Band [−37, +44]**
(`docs/STATE.md:426-427`) — also ≈ break-even gegen Snowie, waehrend die Automatisierungs-Steuer das Konto frass.
Jede Verlustklasse wurde einzeln obduziert und abgedichtet: L1 = 46 % Aussetzer (833 Zwangs-Folds), L2 =
Ueber-Stack-Raise-Schleife, L3 = 13 Fantasie-Pot-Jams durch Dezimalpunkt-Verlust ×100 (Antwort: die
Chip-Erhaltungs-Invariante). Volles AIVAT ist hier NICHT moeglich (kein Showdown-Logging) — die Leiter dorthin ist
in STATE.md definiert.

**Allein benutzbar?** Nein: sie ist auf PokerSnowie 4 unter Windows gebaut und braucht `snowie_state` +
`snowie_local` + einen Bot. Uebertragbar ist die ARCHITEKTUR (Gatter → Verlaufs-Waechter → Klick-Verifikation →
Regressionsnetz).

**Fallstricke.** Prince uebernimmt HU-Poette NUR POSTFLOP. Der Grund ist gemessen und wichtig: ein MP-Open ist eine
15–20-%-Range, die HU-Projektion laese daraus ~50 % (`docs/STATE.md:423-425`). Wer den Takeover „der Einfachheit
halber" auch preflop schaltet, spielt gegen eine erfundene Gegner-Range. Der zweite Fallstrick ist `raise_min`:
Snowies Raise-Button traegt den SLIDER-VORSCHLAG, nicht das Minimum, und sein '$' wurde einmal als '3' gelesen —
darum wird das Minimum BERECHNET (`2 × Einsatzniveau`), nie abgelesen.

---

### Universeller Screen-Reader — `pokerbot/vision/screen_reader.py`
**Zweck.** Liest EINEN beliebigen Pokertisch per VLM (OpenAI) in ein striktes JSON-Schema — ohne site-spezifische
Templates.

**Schnittstelle.** `list_windows() -> list[dict]`, `pick_window(pattern) -> dict|None`, `capture(bbox=None) ->
Image`, `dhash(img) -> int`, `hamming(a, b) -> int`, `read_table(img, model=None) -> (dict, (w, h))`,
`pretty(t) -> str`; CLI `--list | --once [--window "Coin"] | --watch [--interval 2.0]`.

**Eingabe/Ausgabe.** Rein: ein Fenster-Screenshot. Raus: `TABLE_SCHEMA`-JSON (Sitze, Stacks, Board, Pot, Buttons;
Karten als 2-Zeichen-Codes). Watch-Modus schreibt nach `data/vision/table_states.jsonl`.

**Abhaengigkeiten.** `research.llm.openai_json` (bezahlt), `PIL`, `ctypes`. Windows fuer die Fenstersuche.

**Zustand.** Der letzte dHash zur Aenderungserkennung.

**Kosten.** Kostendaempfer im Code: Downscale auf `MAX_W = 1280` und ein 64-Bit-dHash mit `HASH_DIST_MIN = 6` —
unveraenderte Frames loesen keinen API-Call aus. Absolute Kosten/Latenz nicht gemessen; die Bruecke nennt als
Vergleichswert ~4 s und ~4 ct pro VLM-Zug (`snowie_bridge.py:187`).

**Mess-Status.** UNGEMESSEN als Spiel-Pfad. Er ist im Snowie-Betrieb ABGELOEST worden: „LOKALE Lesung (Standard
seit 2026-08-04)" (`snowie_bridge.py:187`) — genutzt wird von ihm nur noch `pick_window`.

**Allein benutzbar?** Ja, mit OpenAI-Key. Es ist der generische Weg, wenn man keine Templates bauen will.

**Fallstricke.** Genau die zwei Fehler, die `snowie_state.py` im Kopf-Docstring dokumentiert: das VLM meldete
einen logisch unmoeglichen Button-Zustand (Fold ja, Check nein, Call nein → 17 Gratis-Checks als Fold
weggeworfen) und eine Sitzreihenfolge, die nicht beim Dealer-Button begann (Position in 26 von 57 Faellen falsch).
Strukturelle Fragen (was ist legal, wer sitzt wo) gehoeren nicht an ein Sprachmodell — sie folgen deterministisch
aus Einsaetzen und Layout. Frontier-API laeuft ausserdem laut Projektregel nur auf dem PC, nie auf einem Pod.

---

## LLM-Brain-Spur (historisch)

Dieses Subsystem laesst ein Sprachmodell Poker spielen, indem es NICHT die Aktion nennt, sondern ein kleines
Python-Programm ueber eine getypte Engine-API schreibt ("program of thought"); ein Sandkasten fuehrt es aus, die
Engine erzwingt Legalitaet, das Modell liefert nur Urteil. Der Zweig ist im Projekt SEKUNDAER und weitgehend
eingefroren: die besten LLM-Zahlen (Claude ueber der Engine −28,55 bis −41 AIVAT bb/100; eigenes 9B-Modell
−43,30, nach Nachtraining −90,18) liegen unter dem reinen Engine-Pfad, und der RL-Lift wurde gemessen widerlegt.
Wer nur einen Bot bauen will, braucht davon fast nichts — mit einer Ausnahme: `api.py`, `format_spot.py`,
`executor.py` und `grammar.py` sind ein sauberes, wiederverwendbares Muster fuer "LLM darf rechnen lassen, aber
nichts erfinden", und `training/rl_env.py` ist eine brauchbare Rollout-/EV-Messumgebung unabhaengig vom LLM.

---

# Teil A — `pokerbot/brain/` (die Brain-Engine-Naht)

### Engine-API (DSL-Vokabular) — `pokerbot/brain/api.py`
**Zweck.** Duenne, getypte Huelle ueber Equity, Poker-Mathematik, Boardtextur, Blueprint, Advisor, Live-Solver und
Legalitaet — genau die Funktionen, die ein LLM-Programm aufrufen darf.
**Schnittstelle.**
- `equity(hero, villain, board=None, iters=None, seed=0) -> float` — Monte-Carlo-Equity; `villain` darf Klassenliste
  (`['AA','AKs']`), Combo-Liste (`[('As','Ks')]`) oder gewichtetes dict sein; `iters=None` nimmt das aktive
  Compute-Mode-Budget (`brain/modes.py`).
- `range_top(frac) -> list[str]` — obere `frac` der 169 Startklassen als kompakter Range-Prior.
- `required_equity(to_call, pot)`, `pot_odds(to_call, pot)`, `mdf(bet, pot)`, `spr(eff, pot)`,
  `outs_equity(outs, cards_to_come=2)` — Pot-Odds/MDF/SPR/Outs aus `knowledge_base/math/formulas.py`.
- `board_texture(board) -> dict` (paired/monotone/twotone/connected/high/dynamic), `hand_rank(hole, board) ->
  (name, strength)` (strength = 1 − treys/7462), `hand_class_of(hole) -> str`.
- `preflop_mix(spot) -> dict|None`, `preflop_solve(spot) -> dict|None` — Blueprint-Mix bzw. derselbe Mix als
  spielfertige DSL-Verben inkl. `_sizes_bb`; beide nur HU-200bb, 6-max gibt `None` (`api.py:130`).
- `solver_freq(hole, board, role, street) -> float|None` — P(bet) der trainierten Advisor-MLPs.
- `solve_node(spot) -> dict|None` — Suche zur Laufzeit: startet TexasSolver auf dem echten Board, navigiert die
  Linie der aktuellen Strasse und gibt `{fold|check|call|bet|raise|allin: prob, '_sizes_bb': {...}}` fuer die
  konkrete Hand; `None` bei preflop, `n_active>2`, unnavigierbarer Linie, Timeout oder jeder Exception.
- `legalize(spot, action, size_bb=None) -> (action, amount_chips)` — erzwingt eine legale Aktion, faellt sicher auf
  check>call>fold zurueck.
Ausserdem werden `knowledge_base/math/postflop_formulas.py` und (falls vorhanden) `strategy_formulas.py` per
Wildcard in den Modul-Namensraum gezogen, sind also als `api.<fn>` aufrufbar (`api.py:21-26`).
**Eingabe/Ausgabe.** Karten sind 2-Zeichen-Strings (`'As'`). `spot` ist immer ein `format_spot.Spot` (Chips roh,
`spot.bb` = Big Blind in Chips); der Solver rechnet in Big Blinds, `legalize` gibt Chips zurueck. Tragende
Rueckgabe-Schluessel: Aktion-Verben plus der private Hinweis `_sizes_bb` (Gesamteinsatz in bb je Verb) — er ist
KEINE Frequenz und darf nie mitnormalisiert werden.
**Abhaengigkeiten.** Hart: `pokerbot/engine/{equity,evaluator,cards}`, `pokerbot/strategy/postflop.classify_board`,
`knowledge_base/math/formulas.py`. Weich/ersetzbar (alles in try/except, `None` bei Fehlen):
`strategy/preflop_blueprint`, `strategy/preflop_strength`, `strategy/advisor`, `strategy/gto_oracle` (TexasSolver-Binary).
**Zustand.** Fast zustandslos; ABER ein modulweiter Solve-Cache `_SOLVE_CACHE` plus `_SOLVE_INFLIGHT` (`api.py:188-198`)
lebt ueber den ganzen Prozess. Schluessel = Board + gebucketeter Pot (4 bb) + gebucketeter Stack (10 bb) + Range-Hash.
Fuer eine saubere Messung muss man den Prozess neu starten oder den Cache leeren.
**Kosten.** Import 0,07 s, `equity` mit 1000 MC-Iterationen ~17 ms (eigener Smoke in dieser Sitzung, Standard-Mode).
`solve_node` ist teuer: ein breiter HU-Flop-Solve ~30 s bei 8 Threads, ~57 s bei 4, ~79 s bei 2 (Messnotiz
`api.py:181-185`, 2026-06-18); Deckel `SOLVE_TIMEOUT` default 150 s.
**Mess-Status.** Als Modul UNGEMESSEN (kein eigener bb/100-Arm). Belegte Teilzahlen: `solve_node` feuerte in einem
Live-Lauf bei 61 % der Entscheidungen (`docs/STATE.md:1090`) bzw. 453-mal in n=500 (`docs/STATE.md:1173`); die
Brain-Bet-Groessen liegen nur zu 15 % auf GTOWs Grid gegen 100 % beim Engine-Pfad (`docs/STATE.md:1090`).
Der Schalter `POKERB_BRAIN_ONTREE` (Snap auf {0,33/0,5/0,75/1/1,25}×Pot, `api.py:461-468`) ist gebaut und
Unit-verifiziert, aber EV-UNGEMESSEN; `POKERB_LINE_RANGES` (linienbewusste Startranges, `api.py:332-338`) ebenfalls
default AUS und ungemessen.
**Allein benutzbar?** Ja, das ist das nachnutzbarste Stueck. Minimal noetig: `pokerbot/engine/*`,
`knowledge_base/math/formulas.py` und ein `Spot`-aehnliches Objekt. Ohne TexasSolver-Binary und ohne die
Advisor-Modelle liefern `solve_node`/`solver_freq` einfach `None`.
**Fallstricke.** Die Kombination "alles in try/except → `None`" und "Cache speichert auch Fehlschlaege" macht
Fehler unsichtbar: ein abgelaufener Solve-Timeout wird als `None` GECACHT (`api.py:293`), der Bot faellt still auf
seinen Fallback zurueck, und die Messung misst einen degradierten Bot, ohne dass irgendwo etwas rot wird.

### Kanonischer Spot + Prompt-Rendering — `pokerbot/brain/format_spot.py`
**Zweck.** Die eine Repraesentation einer Entscheidungssituation, byte-identisch ueber SFT, RL, Inferenz und Eval.
**Schnittstelle.**
- `@dataclass Spot(street, board, bb, hero_seat, hero_pos, hero_hole, pot, to_call, n_active, seats, legal, line,
  villain_fold=0.5, villain_aggro=0.5)` mit `Spot.b(chips) -> float` (Chips → bb).
- `spot_from_table(table, seat) -> Spot` — baut den Spot aus einem laufenden `pokerbot/engine/table.py`.
- `format_spot(spot) -> str` — rendert den Prompt-Text (deterministisch, alles in bb).
- `ACTION_RE` — geteilter Parser fuer `ACTION: <fold|check|call|bet N|raise N|all-in>`.
**Eingabe/Ausgabe.** `seats` = Liste von `{seat,pos,stack,committed_total,folded,all_in}`; `legal` =
`{can_fold,can_check,can_call,can_raise,raise_min,raise_max}` in CHIPS; `line` = geordnete
`{street,pos,action,amount_bb,hero}`. Ausgabe ist reiner Text, ~8-12 Zeilen.
**Abhaengigkeiten.** Hart nur `re`/`dataclasses`; `spot_from_table` haengt hart an der Table-API
(`legal_actions/position_label/obs`-Konventionen). `api.hand_rank` und `understanding.strategic_read` werden LAZY
importiert, nur wenn die jeweiligen Schalter an sind.
**Zustand.** Zustandslos je Aufruf. Aber drei Modul-Schalter werden EINMAL beim Import aus der Umgebung gelesen:
`INCLUDE_MADE_HAND` (`POKERB_MADE_HAND`, default AN), `INCLUDE_SOLVER_FREQ` (`POKERB_SOLVER_FREQ`, default AUS),
`INCLUDE_UNDERSTANDING` (`POKERB_UNDERSTANDING`, default AUS). Ein spaeteres `os.environ[...]` wirkt nicht mehr.
**Kosten.** < 1 ms je Aufruf ohne Zusatzbloecke (eigener Smoke). Mit `INCLUDE_MADE_HAND` kommt eine
Treys-Auswertung dazu (vernachlaessigbar), mit `INCLUDE_SOLVER_FREQ` ein Advisor-Forward.
**Mess-Status.** `INCLUDE_MADE_HAND`: GEMESSEN POSITIV — gepaarter GTOW-A/B n=500 je Arm, AUS −84,11 → AN −43,46,
2,1σ, Varianz halbiert (`docs/STATE.md:1120`); vorher lokal gepaart 7 Spots, 3 klare Korrekturen, 3 Kontrollen
unveraendert (`docs/STATE.md:1153`). `INCLUDE_SOLVER_FREQ`: GEMESSEN NEUTRAL — AN −49,21 ± 29,00 vs AUS
−49,52 ± 11,71, Δ ≈ 0 (`docs/STATE.md:1118`), deshalb default AUS. `INCLUDE_UNDERSTANDING`: UNGEMESSEN
(`docs/STATE.md:1078`).
**Allein benutzbar?** Ja. `Spot` + `format_spot` haengen an nichts Schwerem; man kann Spots von Hand bauen (so macht
es `tests/test_made_hand_read.py`). Nur `spot_from_table` braucht die Engine-Table.
**Fallstricke.** Die gemessene Lehre des Projekts steht als Hartregel im Kopf der Datei (`format_spot.py:31-32`):
Serve-Hinweise (wie der Made-Hand-Block) duerfen NICHT in die Trainingsdaten gebacken werden — genau das hat das
Modell von −28 auf −90 verschlechtert. Wer trainiert und serviert, muss also wissen, welche Bloecke an waren.

### Programm-Sandkasten — `pokerbot/brain/executor.py`
**Zweck.** Fuehrt das vom Modell emittierte Entscheidungsprogramm eingeschraenkt aus und liefert eine legale Aktion.
**Schnittstelle.** `run_program(program, spot, timeout_s=None, strict=True, seed=0) -> dict`. Im Programm-Namensraum
liegen genau `api`, `spot`, `decide(action, size_bb=None)`, `decide_mix(mix, size=None)` und eine Whitelist von
21 Builtins (`executor.py:21-24`) — kein `__import__`, `open`, `exec`, `eval`, `compile`.
**Eingabe/Ausgabe.** Rein: Programmtext + `Spot`. Raus: `{action, amount, ok, error, intended, mix}` — `action`
legalisiert, `amount` = Gesamteinsatz in CHIPS oder `None`; `ok=False` bei Grammatikverstoss, Exception, fehlendem
`decide` oder illegal beabsichtigter Aktion (genau das ist das Hard-Negative fuers RL); `mix` = normierte
Frequenzen, falls `decide_mix` benutzt wurde.
**Abhaengigkeiten.** Hart: `brain/api.py` (Legalisierung) und `brain/grammar.py` (AST-Gatter, nur bei `strict=True`).
**Zustand.** Zustandslos. Die Mix-Ziehung ist ueber `seed` deterministisch (Common Random Numbers).
**Kosten.** ~17 ms fuer ein Programm mit einem `api.equity`-Aufruf bei 1000 Iterationen (eigener Smoke); ohne
Equity im Mikrosekundenbereich. Der Wanduhr-Deckel greift nur unter POSIX und nur im Hauptthread.
**Mess-Status.** GEMESSEN POSITIV als Bugfix: `_alarm_available()` verlangt zusaetzlich `threading.main_thread()`,
weil SIGALRM in Worker-Threads eine Exception wirft und damit JEDE Entscheidung als "bad" zaehlte — das drueckte
`frac_bad` von 1,0 auf 0,009, ohne dass sich am Modell etwas aenderte (`docs/STATE.md:1159`).
**Allein benutzbar?** Ja, mit `api.py` + `grammar.py`. Fuer ein eigenes Vokabular reicht es, den Namensraum in
`run_program` (`executor.py:56`) und die Owner-Liste in `grammar.py:36` zu tauschen.
**Fallstricke.** Der Sandkasten ist eine Whitelist, KEINE Sicherheitsgrenze gegen einen boesartigen Autor: Endlos-
schleifen sind nur unter POSIX/Hauptthread gedeckelt, und Speicherfrass ist ueberhaupt nicht gedeckelt. Fuer
fremde/ungepruefte Modellausgaben in einem Serverprozess braucht es zusaetzlich Prozessisolation.

### AST-Gatter (semantisch) — `pokerbot/brain/grammar.py`
**Zweck.** Strukturelle Zurueckweisung: nur Programme, deren gesamter AST in einer Whitelist liegt, duerfen laufen.
**Schnittstelle.** `validate_program(program) -> (ok: bool, reason: str)`.
**Eingabe/Ausgabe.** Rein Text, raus Wahrheitswert + Klartextgrund (`"disallowed construct: FunctionDef"`,
`"attribute access only on api/spot"`, `"no decide() — a decision program must commit an action"`).
**Abhaengigkeiten.** Nur `ast`. Vollstaendig eigenstaendig.
**Zustand.** Zustandslos.
**Kosten.** Ein `ast.parse` + ein `ast.walk` — nicht messbar relevant.
**Mess-Status.** UNGEMESSEN als EV-Hebel; im Repo gibt es keine eigene Abnahmezahl fuer dieses AST-Gatter (die
zitierten 7/7 · 8/8 · 40/40 gehoeren zur Regex-Variante `dsl_grammar.py`, `docs/STATE.md:1396`). Wirksam ist es
ueber `executor.run_program(strict=True)`, dessen Ablehnungen als `ok=False` in `frac_bad` sichtbar werden.
**Allein benutzbar?** Ja, ohne jede Abhaengigkeit. Anpassen heisst `_ALLOWED_NODES`, `_OWNERS`, `_SAFE_CALLS` aendern.
**Fallstricke.** Attributzugriff ist NUR auf `api`/`spot` erlaubt (`grammar.py:59-60`) — also scheitert schon
`m.get('bet')` oder `sorted(x)[0].foo`. Ein Modell, das idiomatisches Python schreibt, wird permanent abgelehnt;
man muss den Systemprompt sehr eng auf diese Form trimmen (siehe `policy.SYSTEM_PROMPT`, Abschnitt FORM RULES).

### Constrained-Decoding-Grammatik (generativ) — `pokerbot/brain/dsl_grammar.py`
**Zweck.** Dieselbe Sprache als REGEX, damit ungueltige Tokens beim Dekodieren gar nicht erst samplebar sind.
**Schnittstelle.** `matches(program) -> bool`; `vllm_regex(think_cap_chars=None) -> str` (fuer
`GRPOConfig(vllm_structured_outputs_regex=...)`); `regex_logits_processor(tokenizer)` (lokal, via `outlines`,
gibt `None` zurueck wenn `outlines` fehlt).
**Eingabe/Ausgabe.** Text rein, bool bzw. Regex-String raus. Die Form ist: beliebig viele Kommentar-/Zuweisungs-
zeilen, dann genau ein `decide(...)`/`decide_mix({...})` oder ein `if/elif/else`, dessen Zweige je genau einmal
committen (`dsl_grammar.py:37-56`).
**Abhaengigkeiten.** `re` (hart); `outlines`+`transformers` nur fuer den Logits-Processor (weich).
**Zustand.** Zustandslos.
**Kosten.** Nicht gemessen (Regex-Match auf wenigen hundert Zeichen).
**Mess-Status.** UNGEMESSEN als EV-Hebel; als Gatter abgenommen: 7/7 gueltige DSL-Formen akzeptiert, 8/8 fremde
Konstrukte abgelehnt, 40/40 echte Completions (`docs/STATE.md:1396`). Belegt ist ausserdem der Zweck des `think_cap_chars`-Arms: ohne harte Begrenzung
des Denkblocks fuellte das Modell das Token-Budget mit `<think>`-Gerede, bevor ein `decide` kam → `frac_bad` 0,93
(`dsl_grammar.py:64-73`, `docs/STATE.md` gleicher Befund bei `policy.QwenPolicy`).
**Allein benutzbar?** Ja fuer `matches`; der vLLM-Pfad braucht TRL/vLLM, der lokale Pfad `outlines`.
**Fallstricke.** Die Regex ist eine ECHTE Teilmenge dessen, was `grammar.py` akzeptiert. Wer beide benutzt, muss
sie zusammen aendern, sonst produziert das constrained Decoding Programme, die das AST-Gatter spaeter verwirft
(oder umgekehrt trainiert man auf eine Form, die live nicht dekodierbar ist).

### Qwen-Policy-Bruecke + Systemprompt — `pokerbot/brain/policy.py`
**Zweck.** Verbindet ein geladenes (Modell, Tokenizer)-Paar zu `policy(table, seat) -> (action, amount_chips)` und
haelt den EINEN Systemprompt, den SFT, RL, Inferenz und Eval gemeinsam benutzen.
**Schnittstelle.**
- `SYSTEM_PROMPT` (str, ~50 Zeilen) — beschreibt das API-Vokabular, die Formregeln und drei Beispielprogramme.
- `build_messages(spot) -> [{'role':'system'...},{'role':'user'...}]`.
- `extract_program(text) -> str` — schaelt das Programm aus Rohtext (entfernt `<think>`-Bloecke, auch dangling,
  und Markdown-Fences).
- `parse_completion(text, spot, timeout_s=None) -> dict` — Rohtext → `run_program(strict=True)` → Ergebnis-dict
  plus `program`; bei abgelehntem Programm wird notfalls eine `ACTION:`-Zeile legalisiert, `ok` bleibt aber `False`.
- `@dataclass QwenPolicy(model, tok, sampling=False, constrained=True, max_new_tokens=None, temperature=1.0,
  top_p=1.0)` mit `decide_verbose(table, seat)` und `__call__(table, seat)`.
**Eingabe/Ausgabe.** Rein: Table+Sitz bzw. Spot. Raus: `(action, amount_chips)` bzw. das volle Parse-dict.
**Abhaengigkeiten.** `brain/{api,dsl_grammar,modes,executor,format_spot}` hart. `torch`/`transformers` nur in
`QwenPolicy._generate` — `build_messages`/`parse_completion` sind bewusst modellfrei und damit $0-testbar.
**Zustand.** `QwenPolicy` haelt das Modell und einen Logits-Processor; sonst zustandslos je Entscheidung.
**Kosten.** Nicht gemessen fuer den lokalen Transformers-Pfad in dieser Datei; die Projektnotiz zum lokalen
Betrieb: ~5–30 s je Entscheidung ohne vLLM (Memory [[playable-product-launchers]]), ueber vLLM auf dem Pod
1,27 s/Hand nach dem Kaltstart (`docs/STATE.md:1159`).
**Mess-Status.** Der Prompt selbst ist die Trainings-/Inferenz-Naht und GEMESSEN kritisch: fehlender bzw.
abweichender Systemprompt im SFT fuehrte zu `frac_bad=1.0`, und `enable_thinking=False` (`policy.py:133`) war der
Fix fuer `frac_bad=0.93` (Kommentare `policy.py:132-135`, `training/qwen_sft.py:22-25`). Das Gesamtergebnis der
Qwen/GLM-Spur ist REFUTIERT (siehe `training/qwen_grpo.py`).
**Allein benutzbar?** `build_messages`/`extract_program`/`parse_completion` ja, ohne GPU. `QwenPolicy` braucht ein
geladenes HF-Modell.
**Fallstricke.** `extract_program` schneidet an `</think>` — wenn der Denkblock ins Token-Limit laeuft und nie
schliesst, bleibt ein LEERER Programmtext uebrig, der als Hard-Negative gewertet wird. Das sieht wie ein dummes
Modell aus, ist aber ein Budgetproblem.

### Claude-als-Brain — `pokerbot/brain/claude_brain.py`
**Zweck.** Ein Frontier-Modell (Claude Opus) schreibt das Entscheidungsprogramm; alles danach ist identisch zum
Qwen-Pfad.
**Schnittstelle.** `@dataclass ClaudeBrain(model=None, thinking=True, strict=True, max_tokens=6000)` mit
`decide_spot(spot) -> dict` (Form wie `parse_completion`, zusaetzlich `program`) und `report() -> dict`
(`decisions, valid, frac_bad, called_solve_node, errors, in_tok, out_tok, cache_tok`).
**Eingabe/Ausgabe.** Rein: `Spot`. Raus: legale Aktion + Metadaten. Bei API-Fehler wird ein sicheres `check`
legalisiert und `ok=False` gesetzt — die Hand bricht nie ab.
**Abhaengigkeiten.** `research/llm.ask_claude` (verzoegert importiert), `brain/{api,modes,executor,format_spot,
policy}`. Schluessel kommen aus `pokerbot/config.py`.
**Zustand.** Zaehler je Instanz (threadsicher via `self._lock`); die HTTP-Aufrufe selbst sind zustandslos, daher
sind viele Haende parallel moeglich.
**Kosten.** GEMESSEN: ~8,32 $ fuer 500 Haende (`docs/STATE.md:1173`), 4,14 $ fuer 200 Haende
(`docs/STATE.md:1090`) — also grob 1,7–2 Cent je Hand plus Latenz eines Reasoning-Aufrufs je Entscheidung.
**Mess-Status.** GEMESSEN, aber unter dem Engine-Pfad: −28,55 ± 7,25 AIVAT bb/100 (n=500, `frac_bad` 0,011,
`solve_node` 453×, `docs/STATE.md:1173`); Nachmessung −41,0 ± 14,06 (n=200, `docs/STATE.md:1090`) → ehrliche
Einordnung ~−35 bis −45 mit fettem Rand. Zwei benannte Lecks: Deep-Jam-Spew (Programm degenerierte zu "immer
callen", ~−7 bb/100 aus ~2 % der Haende, `claude_brain.py:32-34`) und reflexartige ~0,60×Pot-River-Bets gegen
solvergemessene ~0,33×Pot (`claude_brain.py:44-48`). Gegen beides existiert je ein Prompt-Zusatz; der River-Zusatz
`POKERB_CLAUDE_RIVERSIZE` ist default AUS und EV-UNGEMESSEN.
**Allein benutzbar?** Ja, wenn man `research/llm.ask_claude` durch den eigenen API-Aufruf ersetzt — die Klasse ist
duenn (117 Zeilen) und haengt sonst nur an Prompt + Executor.
**Fallstricke.** Der Brain-Pfad UMGEHT `pokerbot/strategy/bot.py` vollstaendig (er ruft `api.legalize` direkt).
Jede Verbesserung, die in der Engine-Strategie steckt — Sizing-Grid, Guards, Profile — erreicht das Brain nicht.
Genau daran ist im Projekt der Vergleich "Brain vs Engine" immer wieder zerbrochen (Memory
[[brain-engine-two-products]]).

### Verstaendnis-Schicht — `pokerbot/brain/understanding.py`
**Zweck.** Fasst SPR/Position/Pot-Odds/MDF, Boardtextur, Handstaerke, Initiative und gemessene GTO-Heuristiken zu
EINEM engine-berechneten Textblock zusammen, damit das Modell auch ohne Solve begruenden kann.
**Schnittstelle.** `strategic_read(spot) -> str` (einzige oeffentliche Funktion). Die Prioren stehen als benannte
Konstanten oben: `RIVER_BET_MEDIAN_X=0.33`, `RIVER_CHECK_RATE=0.58`, `SPR_COMMITTED=1.0`, `SPR_DEEP=6.0`,
`STRONG_MADE=0.62`, `MEDIUM_MADE=0.40`.
**Eingabe/Ausgabe.** `Spot` rein, mehrzeiliger Text raus (`STRATEGIC READ (...)` + vier Aufzaehlungspunkte:
Geometry / Hand vs board / Initiative / Prinzip).
**Abhaengigkeiten.** Nur `brain/api.py` (hart). Kein Solver, kein Netz.
**Zustand.** Zustandslos, rein deterministisch.
**Kosten.** < 1 ms (eigener Smoke; enthaelt eine Treys-Auswertung, keine MC-Simulation).
**Mess-Status.** UNGEMESSEN. Gebaut und lokal verifiziert (AUS byte-identisch, AN korrekte Zahlen), aber der
realisierte EV-Nutzen ist ausdruecklich unbewiesen (`docs/STATE.md:1078`, `docs/ROADMAP.md:26-35`). Die zwei
River-Zahlen 0,33/0,58 stammen aus einer eigenen Solver-Messung ueber 5 Boards × 2 Pottypen
(`understanding.py:21-22`).
**Allein benutzbar?** Ja — das ist der leichteste nachnutzbare Block der ganzen Spur (nur `api.py` noetig), und er
funktioniert auch fuer ein ganz anderes LLM oder als Erklaertext fuer Menschen.
**Fallstricke.** `_draw_note` (`understanding.py:93-101`) leitet aus `board_texture` ab, und `twotone` heisst dort
"genau zwei Karten derselben Farbe" (`strategy/postflop.py:89`). Auf einem 5-Karten-River schreibt die Schicht
darum "flush possible", obwohl bei nur zwei gleichfarbigen Karten gar kein Flush moeglich ist — selbst reproduziert
(Board `As Kd 2h 7c 9d` → "wet/dynamic board; flush possible"). Wer den Block ins Modell fuettert, fuettert hier
eine falsche Behauptung mit.

### Compute-Modi — `pokerbot/brain/modes.py`
**Zweck.** Macht den Kompromiss Genauigkeit gegen Zeit explizit und global umschaltbar.
**Schnittstelle.** `Mode`-Dataclass (`name, time_budget_s, equity_iters, rollout_k, max_new_tokens,
exact_threshold, sympy_verify, analysis`); vier Instanzen `FAST/STANDARD/DEEP/TRAIN`; `current()`, `set_mode(mode)`,
Kontextmanager `using(mode)`.
**Eingabe/Ausgabe.** Modusname oder `Mode` rein, aktiver `Mode` raus.
**Abhaengigkeiten.** Keine.
**Zustand.** GLOBAL, prozessweit (`_active` als Ein-Element-Liste, `modes.py:42`). Konsumenten sind `api.equity`
(MC-Iterationen), `rl_env.rollout_action_ev` (Rollout-Zahl), `policy.QwenPolicy` (Token- und Zeitbudget).
**Kosten.** Vernachlaessigbar; die Werte sind aber der dominante Kostenhebel aller anderen Module
(STANDARD: 1000 Equity-Iterationen, 5 s Budget; DEEP: 8000 Iterationen, 180 s).
**Mess-Status.** UNGEMESSEN (Konfigurationsschicht, kein EV-Arm).
**Allein benutzbar?** Ja, 62 Zeilen ohne Abhaengigkeiten.
**Fallstricke.** Globaler Zustand plus Default `STANDARD`: wer in einem Messlauf vergisst, `TRAIN`/`FAST` zu setzen,
misst mit anderen Equity-Iterationen als der Vergleichslauf — und MC-Iterationen aendern Entscheidungen an
Grenzspots. Immer explizit setzen, nie auf den Default verlassen.

### Solver-Suche als Policy — `pokerbot/brain/solver_policy.py`
**Zweck.** Ganz ohne LLM: postflop wird direkt aus dem Live-Solve gespielt, sonst faellt es auf eine Fallback-Policy.
**Schnittstelle.** `SolverSearchPolicy(seat=0, fallback=None, seed=0)`, aufrufbar als `policy(table, seat) ->
(action, amount_chips)`; Zaehler `.solved` und `.fell_back`.
**Eingabe/Ausgabe.** Table+Sitz rein; legale Aktion raus. Default-Fallback ist ein `SixMaxBot`-TAG
(`solver_policy.py:26-34`).
**Abhaengigkeiten.** `brain/api.solve_node` + `format_spot.spot_from_table` (hart); der Default-Fallback zieht
`arena/sixmax` und `training/rl_env` nach (ersetzbar: jede Callable mit derselben Signatur genuegt).
**Zustand.** Eigener RNG je Instanz fuer die Mix-Ziehung; der Solve-Cache liegt in `api.py`, nicht hier.
**Kosten.** Dominiert von `solve_node` (30–79 s je NEUEM Solve, `api.py:181-185`); Cache-Treffer sind billig.
**Mess-Status.** UNGEMESSEN in bb/100. Belegt ist nur die Abdeckung: HU-Solve-Rate ~1,0, 25/25 im Smoke vom
2026-06-18 (`solver_policy.py:14-15`); 6-max faellt haeufig zurueck, weil TexasSolver zwei Spieler kann.
**Allein benutzbar?** Ja, wenn TexasSolver ueber `strategy/gto_oracle` erreichbar ist und man einen eigenen
Fallback uebergibt.
**Fallstricke.** Fuer echtes Spiel unbrauchbar langsam, solange der Cache kalt ist — und die Ranges sind FESTE
Single-Raised-Pot-Defaults auf jeder Strasse (`api.py:204-208`), also in 3bet-/gelimpten Pots systematisch zu
weit. Der Solver liefert dann eine praezise Antwort auf die falsche Frage.

---

# Teil B — `training/` (Self-Play-Reward + Qwen-/GLM-Training)

### RL-Umgebung + Rollout-EV — `training/rl_env.py`
**Zweck.** Bewertet eine beliebige Policy per realisiertem EV gegen eine Bot-Liga und liefert den Rollout-EV, der
sowohl Pilot als auch GRPO-Reward speist.
**Schnittstelle.**
- `league_policy(bot) -> policy(table, seat)` (der Bot bleibt als `_p.bot` erreichbar, damit CRN-Reseeding geht).
- `play_hand(table, policies, observers) -> {seat: net_chips}`.
- `make_league(profiles, hero_seat=0, seed=None) -> {seat: SixMaxBot}`.
- `evaluate_policy(hero_policy, profiles=(...), n_hands=500, seed=0, hero_seat=0, starting_stack=10000, sb=50,
  bb=100) -> {bb_per_100, n, total_bb, std_bb}`.
- `selfplay_zero_sum_check(...) -> {per_seat_bb_per_100, worst_hand_residual_chips}` (Chip-Erhaltung als Invariante).
- `rollout_action_ev(snapshot, hero_seat, action, amount, cont_policy, profiles=(...), k=None, base_seed=0,
  bb=100) -> float` — mittlerer Held-Netto in bb, gemessen ab dem Snapshot, also EV RELATIV ZUM SOFORTIGEN FOLD.
- `gen_decision_states(profiles=(...), hero_seat=0, n_states=50, seed=0)` — Generator von `(snapshot_table, spot)`.
- Konstanten `TRAIN_LEAGUE = ("tag","lag","nit","station","maniac")`, `HELDOUT_LEAGUE = ("rock","whale","shark")`.
**Eingabe/Ausgabe.** Policies sind `callable(table, seat) -> (action: str, amount_chips|None)`. Snapshots sind
`deepcopy`-Kopien der Table; `rollout_action_ev` mutiert den uebergebenen Snapshot NICHT.
**Abhaengigkeiten.** Hart: `pokerbot/engine/table.py`, `pokerbot/arena/sixmax.py`, `brain/modes.py`. `brain/
format_spot` nur im Generator (lazy).
**Zustand.** Je Hand: die Table. Zwischen Rollouts wird explizit zurueckgesetzt — `_reseed_for_rollout` mischt nur
die NOCH NICHT ausgeteilten Karten neu, `_reset_cont` setzt Gegner-Modell, Hand-Felder und RNG des Held-
Fortsetzungsbots zurueck (`rl_env.py:130-152`). Ohne diesen Reset ist der Reward nicht reproduzierbar.
**Kosten.** Nicht gemessen als Zahl im Repo; der Aufbau des State-Buffers ist als EINZELTHREADIG dokumentiert
und war der Engpass eines Laufs (`docs/STATE.md:1196`).
**Mess-Status.** GEMESSEN POSITIV als Messinstrument (siehe `training/pilot.py`), aber als RL-Reward REFUTIERT:
`make_league` baut alle Gegner aus DERSELBEN `SixMaxBot`-Engine (~68 % identisches Postflop-Verhalten) und die
Held-Fortsetzung ist hart `tag` (`qwen_grpo.py:116`) → der Reward misst "Engine gegen Engine", nicht GTO; die
erreichbare RL-Decke wurde daraus auf ~Engine-Niveau geschaetzt und die RL-Spur eingestellt (`docs/STATE.md:1087`).
**Allein benutzbar?** Ja — das ist neben `api.py` das brauchbarste Stueck fuer einen Fremden: eine paarweise,
seed-kontrollierte EV-Messumgebung fuer beliebige Policies. Noetig sind nur `engine/table.py` und ein Gegnerbot.
**Fallstricke.** `rollout_action_ev` misst EV RELATIV zum Snapshot-Stack, Fold ist also per Definition 0. Wer die
Zahl mit einer absoluten bb/100-Groesse vergleicht, vergleicht zwei verschiedene Dinge.

### De-Risk-Pilot (EV-Signal-Nachweis) — `training/pilot.py`
**Zweck.** Beweist lokal und kostenfrei, ob Rollout-EV ueberhaupt ein lernbares Signal traegt, bevor man GPU-Geld
ausgibt.
**Schnittstelle.** `candidate_actions(snapshot) -> [(action, amount, label)]`; `rank_state(snapshot, hero_seat,
cont_policy, k=16, profiles=..., base_seed=0) -> [{action, amount, label, ev_bb}]` (best zuerst);
`baseline_profile(profile, hero_seat=0)`, `baseline_random(seed=0)`; `run_pilot(n_states=8, k=16, seed=0,
profiles=..., hero_seat=0, baselines=None) -> dict`.
**Eingabe/Ausgabe.** Raus kommen je Spot die EV-gerankten Kandidaten plus die Luecke zwischen Orakel-Aktion und
jeder Baseline, aggregiert zu `{gap, sem, sig_2sem}`.
**Abhaengigkeiten.** `training/rl_env.py`, `pokerbot/arena/sixmax.py` (hart).
**Zustand.** Zustandslos; Paarung ueber `base_seed` (alle Kandidaten teilen den Seed = CRN) und ein FRISCHER
Holdout-Seed fuer die unverzerrte Nachmessung (`pilot.py:104-113`).
**Kosten.** Nicht gemessen; skaliert mit `n_states × Kandidaten × k` Rollouts.
**Mess-Status.** GEMESSEN POSITIV: n=200 gegen random +11,03 ± 3,31, gegen maniac +5,21 ± 1,77, gegen tag
+5,62 ± 1,81 — alle > 2·SEM; die Luecke wuchs mit der Stichprobe (+2,06 → +5,62), Holdout-Liga (rock/whale/shark)
n=50 ebenfalls signifikant (+3,52 ± 1,39 gegen tag) — `docs/STATE.md:1388-1394` und `:1404-1407`.
**Allein benutzbar?** Ja, komplett ohne LLM und ohne GPU. Es ist eine allgemeine "welche Aktion waere hier besser
gewesen"-Maschine.
**Fallstricke.** Das Orakel hat WEITSICHT (es rollt die Zukunft aus) — es ist die Obergrenze, die eine gelernte
Policy annaehert, kein erreichbares Ziel. Wer die Orakel-Luecke als "so viel bringt das Training" liest, taeuscht
sich systematisch.

### SFT-Trainer — `training/qwen_sft.py`
**Zweck.** LoRA-Feintuning eines Basismodells auf PokerBench und/oder auf die eigenen DSL-Shards.
**Schnittstelle.** Kommandozeilenlos, ueber Umgebungsvariablen: `BASE` (default `Qwen/Qwen3-8B`), `MAXN`, `EPOCHS`,
`BATCH`, `QUANT4`, `ATTN`, `DSL` (kommaseparierte JSONL-Shards), `SKIP_PB`, `OUT`, `CURRICULUM`, `REPLAY`,
`PACKING`, `ASSIST_ONLY`, `GRAD_CKPT`, `MAX_LEN`. Funktionen: `load_pokerbench()`, `load_dsl(paths)`,
`load_curriculum(paths, replay, seed)`, Klasse `_OrderedSFT` (erzwingt sequentiellen Sampler), `main()`.
**Eingabe/Ausgabe.** Shard-Zeilen sind `{"spot": ..., "completion": ...}`; sie werden zu
`{messages:[system,user,assistant]}` mit `policy.SYSTEM_PROMPT` als System-Rolle. Raus: ein LoRA-Adapter unter `OUT`.
**Abhaengigkeiten.** Hart: `torch`, `transformers`, `peft`, `trl`, `datasets`, `bitsandbytes` — und
`pokerbot/brain/policy.SYSTEM_PROMPT` (bewusst, damit Training und Inferenz denselben Prompt sehen).
**Zustand.** Nur Dateien; setzt `TOKENIZERS_PARALLELISM=false` VOR dem transformers-Import (`qwen_sft.py:11-14`),
weil das `map()` sonst in einem Futex haengt (beobachtet: 21k Zeilen, 32 Minuten ohne Fortschritt).
**Kosten.** GEMESSEN: ~60 min / 625 Schritte bei `MAXN=10000` auf einer H100 (`docs/STATE.md:1163`).
**Mess-Status.** GEMESSEN POSITIV als Warm-Start: Loss ≈ 0,087, mittlere Token-Genauigkeit 97,5 % auf 33k
DSL-Gold-Zeilen (`docs/STATE.md:1158`); ein zweiter Lauf 1,94 → 0,10 bei Token-Genauigkeit 0,70 → 0,97
(`docs/STATE.md:1163`). Das Modell lernt also die Sprache — was es NICHT lernt, ist besser zu spielen (naechster
Eintrag).
**Allein benutzbar?** Ja, wenn man `SYSTEM_PROMPT` durch den eigenen ersetzt; sonst haengt nichts am Pokerteil.
**Fallstricke.** `ASSIST_ONLY=1` (Loss nur auf der Antwort) war der Fix gegen `frac_bad` — und der Systemprompt im
Training MUSS derselbe sein wie bei der Inferenz, sonst halluziniert das Modell unter dem ungesehenen Prompt
`import api` (`qwen_sft.py:22-25`). Das ist der teuerste, am haeufigsten wiederholte Fehler dieser Spur.

### GRPO/DAPO-Trainer — `training/qwen_grpo.py`
**Zweck.** RL ueber realisiertem Self-Play-EV, um die Policy ueber ihren SFT-Start zu heben.
**Schnittstelle.** `build_state_buffer(n, oversample=1.5, spread_eps=0.5, k_screen=8, profiles=TRAIN_LEAGUE,
hero_seat=0, seed=0, decontam=True) -> [(snapshot, spot)]`; `make_ev_reward(snapshots, hero_seat=0,
profiles=TRAIN_LEAGUE, k=K_ROLL, bb=100) -> reward_func(completions, sid, base_seed, ...) -> [float]`;
`build_dataset(states, tok=None, seed=0) -> (Dataset, snapshots)`; `make_config(out_dir)`;
`load_policy_model(base, adapter)`; `main()`. Reward-Knoepfe als Umgebungsvariablen: `R_BAD` (default −3),
`R_CLIP` (25), `R_FMT` (2,0), `K_ROLL` (16), `REWARD_TIMEOUT_S`, `REWARD_WORKERS`.
**Eingabe/Ausgabe.** Datensatzspalten `prompt`, `sid`, `base_seed`; Reward = geclippter Rollout-EV + Formatbonus
± abklingende "engine-grounded"-Formung. Raus: Adapter + `models/grpo_metrics.jsonl`-artige Kurven
(`step, reward, reward_std, frac_bad, engine_grounded_rate, ...`).
**Abhaengigkeiten.** `training/{rl_env,pilot}`, `pokerbot/brain/{executor,format_spot,policy,dsl_grammar}`,
`pokerbot/arena/sixmax` (hart, CPU); `trl`/`torch`/`vllm` nur in Config/Trainer (Pod-GPU).
**Zustand.** Ein Prozess-Pool fuer die Rollouts (`_POOL`), Snapshots als Seitentabelle; CRN je Completion ueber
`base_seed`, damit die gruppenrelative Vorteilsschaetzung die AKTION isoliert und nicht das Kartenglueck.
**Kosten.** Nicht sauber gemessen; belegt ist ein Schrittprofil aus `models/grpo_metrics.jsonl` (Schritt 1:
52,2 s inkl. Aufwaermen, danach ~2 s je Schritt bei diesem Lauf).
**Mess-Status.** REFUTIERT als EV-Hebel. (1) Erster Lauf mit `R_BAD=-30`: Reward flach bei −17,69, die Gruppe
lernte "gueltig sein" statt "gut spielen" — Belegzeile 1 in `models/grpo_metrics.jsonl` plus die Begruendung
`qwen_grpo.py:29-34`; Fix auf −3. (2) Das trainierte 9B erreichte −43,30 ± 7,15 AIVAT (n=100,
`docs/STATE.md:1159`), also etwa Engine-Niveau. (3) Ein Nachtraining (Re-SFT auf made-hand-nativem Gold + frisches
GRPO) REGRESSIERTE auf −90,18 (`docs/STATE.md:1132`). (4) Die Ursachenanalyse ($0, `docs/STATE.md:1087`) fuehrt
die Decke auf den Reward zurueck (Liga aus einer Bot-Engine, harte tag-Fortsetzung). Fazit im Repo: die Gewinne
lagen in der VERDRAHTUNG zur Inferenzzeit, nicht in den Gewichten (`docs/STATE.md:1135`).
**Allein benutzbar?** Die CPU-Haelfte (`build_state_buffer`, `make_ev_reward`, `build_dataset`) laeuft ohne
torch/trl und ist damit isoliert testbar — bewusst so geschichtet. Der Trainer selbst braucht eine GPU-Box.
**Fallstricke.** Der Reward ist nur so stark wie die Liga. Wer diesen Aufbau uebernimmt, uebernimmt die gemessene
Falle: das Modell lernt, die eigene Liga zu schlagen, und verliert genau dadurch gegen einen echten Solver-Gegner.

### PokerBench-Eval — `training/qwen_eval.py`
**Zweck.** Vergleicht Basismodell gegen LoRA auf ausgehaltenen PokerBench-Spots ueber Aktions-Uebereinstimmung.
**Schnittstelle.** `main()` (Aufruf `python -m training.qwen_eval [N]`), Hilfen `_action(text)`, `load_pokerbench()`,
`_heldout(n)`, `_gen(model, tok, prompt)`, `_score(model, tok, data, label)`.
**Eingabe/Ausgabe.** PokerBench-Zeilen rein, Trefferquote (erstes Aktionsschluesselwort) raus.
**Abhaengigkeiten.** `torch`, `transformers`, `peft`, `datasets` (hart) sowie ein HF-Download.
**Zustand.** Zustandslos.
**Kosten.** Nicht gemessen.
**Mess-Status.** UNGEMESSEN in dieser Datei; die Projektbewertung der Metrik ist negativ — Aktions-Matching gegen
eine Referenz sagt wenig ueber bb/100 (dieselbe Lehre wie beim GTO-Score, `docs/STATE.md` Kopfblock).
**Allein benutzbar?** Ja. Enthaelt eine hart kodierte Adapterpfad-Konstante (`qwen_eval.py:20`, Windows-Pfad) —
anpassen.
**Fallstricke.** `_action` nimmt das ERSTE Aktionswort im Text; ein Modell, das im Fliesstext "ich falte nicht,
ich raise" schreibt, wird als "fold" gewertet.

### GTO-verankerte Eval + Gate-Leiter — `training/qwen_eval_gto.py`
**Zweck.** Misst die Policy gegen eine AUSGEHALTENE Gegnerliga und fasst die Freigabekriterien zu einer Leiter.
**Schnittstelle.** `league_eval(policy, league=HELDOUT_LEAGUE, n_hands=2000, seed=0, hero_seat=0) ->
{per_type, mixed_bb100, worst_bb100, spread_bb100}`; `gate_ladder(grpo, sft, pokerbench_acc, dsl_emit_rate,
legality, lbr_delta=None) -> dict`; `pokerbench_acc(model, tok, n=200) -> (acc, emit_rate)`; `main()`.
**Eingabe/Ausgabe.** Policy rein, Kennzahlen raus; `main()` schreibt `eval_gates.json` (Pfad ueber `GATES_OUT`).
Gates: G0 PokerBench-Genauigkeit ≥ 0,70 und DSL-Emissionsrate ≥ 0,99; G1 Legalitaet ≥ 0,99; G2 GRPO-bb/100 >
SFT-bb/100 (die Kernthese); G3 Worst-Case ≥ 0; G4 Exploitierbarkeit nicht schlechter.
**Abhaengigkeiten.** `training/rl_env.py` (hart, modellfrei) — nur `pokerbench_acc`/`main` brauchen GPU-Modelle.
**Zustand.** Zustandslos; `EVAL_MIXED_ONLY=1` ueberspringt die fuenf Einzeltypen (das war die Timeout-Ursache).
**Kosten.** Nicht gemessen; skaliert mit `n_hands` × Ligagroesse × 2 Adapter.
**Mess-Status.** UNGEMESSEN als eigener Arm; die Leiter wurde als Instrument gebaut und $0-verifiziert
(`docs/STATE.md:1398-1401`). Ein `data/eval_gates.json` liegt in diesem Arbeitsverzeichnis NICHT vor.
**Allein benutzbar?** `league_eval`/`gate_ladder` ja, rein und modellfrei.
**Fallstricke.** Die Liga hier ist "gehalten" nur relativ zur Trainingsliga — alle Profile stammen aus derselben
`arena/sixmax.py`-Engine. Das ist eine Robustheits-NAEHERUNG, kein unabhaengiger Gegner.

### Pod-Vorflugcheck — `training/preflight.py`
**Zweck.** Faellt in ein bis zwei Minuten durch, wenn die GPU-Umgebung oder die TRL-API nicht passt — statt nach
einer teuren halben Stunde Modell-Laden.
**Schnittstelle.** `main()`; Ausgabe `PREFLIGHT1_OK` oder `PREFLIGHT1_FAIL: ...` mit Rueckgabecode ≠ 0.
**Eingabe/Ausgabe.** Nichts rein; Statuszeilen raus.
**Abhaengigkeiten.** `torch/transformers/trl/peft/bitsandbytes/datasets/vllm` (hart) plus
`training.qwen_grpo.{make_config, build_state_buffer, make_ev_reward}`.
**Zustand.** Zustandslos.
**Kosten.** Laut Kopfzeile ~1–2 min, kein Modell-Laden.
**Mess-Status.** UNGEMESSEN als EV-Hebel; als Schutz belegt: eine echte bf16-Matmul faengt Blackwell-Karten ab,
auf denen `torch.cuda.is_available()` zwar wahr ist, die Kernel aber fehlen (`preflight.py:20-25`).
**Allein benutzbar?** Ja, aber nur sinnvoll fuer genau diesen Stack.
**Fallstricke.** Er prueft die TRL-Konfiguration durch KONSTRUKTION — wenn TRL seine Signaturen aendert, ist das
Skript selbst das Erste, was angepasst werden muss.

---

# Teil C — `pipeline/` (PC-Hub: Distillation unter Gatter, Orchestrierung)

### EV-Wahrheitsfilter — `pipeline/filter.py`
**Zweck.** Das Anti-Halluzinations-Gatter: kein Vorschlag eines Fremdmodells kommt in den Datensatz, ohne dass die
Engine ihn deterministisch geprueft hat.
**Schnittstelle.** `@dataclass Verdict(ok, reason, gate)`; `class EVFilter(decontam_keys=None)` mit
`gate(ex, spot=None) -> Verdict` und `.stats` (`in, kept, schema, irrelevant, decontam, dup, illegal, ev`).
Gatterkette: G1 Schema, G2 Themenrelevanz, G3 Dekontamination gegen die PokerBench-Testmenge, G4 Deduplizierung,
G5 Legalitaet (`api.legalize` muss die Aktion unveraendert lassen), G6 EV-Plausibilitaet (Fold obwohl gratis
gecheckt werden koennte; Call, dessen Equity selbst gegen eine ZUFAELLIGE Gegnerhand klar unter dem Break-even liegt).
**Eingabe/Ausgabe.** `ex` = Datensatzzeile aus `dataset/schema.make_example` (Felder `spot`, `completion`,
`action{action,size_bb}`); optional der strukturierte `Spot`, ohne den nur G1–G4 laufen. Raus: `Verdict`.
**Abhaengigkeiten.** `pokerbot/brain/api.py`, `dataset/schema.py` (hart).
**Zustand.** JE LAUF: `self.seen` (Dedup) und `self.decontam`. Eine Instanz pro Build; nicht threadsicher
(`distill_run.py` gatet deshalb bewusst einthreadig).
**Kosten.** G6 rechnet eine MC-Equity gegen ALLE verbleibenden Combos — nicht gemessen, aber die teuerste Stufe.
**Mess-Status.** UNGEMESSEN als EV-Hebel. Die Idee wurde spaeter als Live-Instrument empfohlen ("EVFilter-G6 zur
Servezeit gegen die Katastrophen-Haende", `docs/STATE.md:1122`), aber nie in dieser Form gemessen.
**Allein benutzbar?** Ja, wenn man `dataset/schema.py` mitnimmt oder die drei Aufrufe (`validate`, `is_relevant`,
`spot_key`) selbst stellt.
**Fallstricke.** G6 ist bewusst STUMPF: es misst gegen eine zufaellige Gegnerhand, also eine grosszuegige
Obergrenze der Heldenequity, und verwirft nur eindeutige Verlierer. Wer es fuer ein Qualitaetsurteil haelt, laesst
sehr viel Mittelmass durch.

### Frontier-Distillationsschleife — `pipeline/frontier_loop.py`
**Zweck.** Fragt ein Frontier-Modell zu SCHWACHEN Spots, presst jede Antwort durch `EVFilter` und haengt nur
Akzeptiertes an einen JSONL-Shard.
**Schnittstelle.** `frontier_proposer(provider='claude') -> proposer(spot_text) -> (proposal, (in_tok, out_tok))`;
`to_example(spot_text, proposal) -> dict`; `run(weak_spots, ev_filter=None, out_path=None, proposer=None,
provider='claude', limit=None) -> {accepted, rejected, filter, tokens, reject_reasons}`.
**Eingabe/Ausgabe.** Rein: iterierbare `Spot`s. Vorschlag = JSON mit `action`, `size_bb`, `reasoning`; daraus wird
ein Programm `# <reason>\ndecide('call', 7.5)`. Raus: Statistik + angehaengte Zeilen.
**Abhaengigkeiten.** `dataset/schema`, `brain/format_spot`, `pipeline/filter`, `research/llm` (hart) — der
`proposer` ist injizierbar, damit man die Schleife ohne API-Kosten testen kann.
**Zustand.** Der `EVFilter` haelt den Zustand; die Schleife selbst ist zustandslos.
**Kosten.** Token-Verbrauch wird zurueckgegeben; keine Latenzmessung im Repo.
**Mess-Status.** UNGEMESSEN (keine bb/100-Zahl fuer daraus destillierte Daten). Der uebergreifende Befund gilt:
Imitation hebt den START, nicht die Decke (`pipeline/distill_teacher.py:6-7`).
**Allein benutzbar?** Ja, mit eigenem `proposer` und eigenem Gatter.
**Fallstricke.** `to_example` schneidet die Begruendung auf 500 Zeichen und macht daraus EINE Kommentarzeile plus
`decide(...)` — das ist genau die "dekorative" Form, die im Projekt gemessen `frac_bad` 0,97 erzeugte, waehrend die
ableitende Form (`if eq >= req: ...`) 0,00 ergab (Memory [[reasoning-loop-not-decoration]]). Wer damit trainiert,
trainiert dem Modell das Nichtrechnen an.

### Schwachstellen-Monitor — `pipeline/monitor.py`
**Zweck.** Definiert die gemeinsame Cluster-Taxonomie und findet die schwaechsten Cluster, damit die Distillation
dort nachwaechst.
**Schnittstelle.** `cluster_of(spot) -> (street, hero_pos, spr_bucket, texture_tag)`;
`weak_clusters(records, k=10, min_n=20) -> [(cluster, mean_score, n)]`; `spots_in_clusters(spot_pool,
target_clusters)` (Generator).
**Eingabe/Ausgabe.** `records` = `[{'cluster': key, 'score': float, 'n': int}]`, score hoeher = besser. Raus die
k schwaechsten Cluster mit mindestens `min_n` Beobachtungen.
**Abhaengigkeiten.** `brain/api.py` (SPR + Textur), `brain/format_spot.Spot`.
**Zustand.** Zustandslos.
**Kosten.** Nicht gemessen (reine Aggregation).
**Mess-Status.** UNGEMESSEN.
**Allein benutzbar?** Ja, sehr klein (52 Zeilen).
**Fallstricke.** Die Buckets sind grob (3 SPR-Stufen, 5 Texturklassen) — ein "schwacher Cluster" kann eine
Mischung sehr verschiedener Spots sein. Als Lead brauchbar, als Beweis nicht.

### PC↔Pod-Transport — `pipeline/orchestrate.py`
**Zweck.** Packt Code und Daten in EIN Tarball, schiebt es per scp auf den Pod und holt Adapter/Report zurueck.
**Schnittstelle.** `build_tarball(out_path=None, members=None) -> str`; `push(ip, port, tarball,
remote='/root/bundle.tgz', unpack_to='/root/pokerb')`; `pull(ip, port, remote, local)`.
**Eingabe/Ausgabe.** Standard-`BUNDLE` = `pokerbot, dataset, training, infra, research` plus vier
`knowledge_base`-Unterordner (`orchestrate.py:23-25`); raus `subprocess.CompletedProcess`.
**Abhaengigkeiten.** `pokerbot/config.py`, ein SSH-Schluessel (Pfad hart kodiert, `orchestrate.py:18`), `scp`/`ssh`
im PATH.
**Zustand.** Zustandslos; Dateien auf beiden Seiten.
**Kosten.** Nicht gemessen. Begruendung im Kopf: `scp -r` ueber hunderte kleiner Dateien blieb haengen, ein
einzelnes Tarball nicht.
**Mess-Status.** UNGEMESSEN.
**Allein benutzbar?** Ja, aber der Schluesselpfad ist hart kodiert und Windows-spezifisch.
**Fallstricke.** Das Bundle laesst `books/` und `knowledge_base/hand_histories` bewusst weg. Wer auf dem Pod ein
Modul benutzt, das diese Pfade liest, bekommt dort einen FileNotFound, den man lokal nie sieht.

### Lehrer-Destillation (Lauf) — `pipeline/distill_run.py`
**Zweck.** Erzeugt HU-Postflop-Spots, fragt Claude parallel, gatet einthreadig und schreibt einen Shard.
**Schnittstelle.** `main()` (Argumente `--n`, `--out`, `--threads`), Hilfsfunktion `_propose(spot, proposer)`.
**Eingabe/Ausgabe.** Raus: JSONL-Shard mit akzeptierten Zeilen plus Gatter-Statistik.
**Abhaengigkeiten.** `dataset/build/from_hu_postflop`, `pipeline/{filter,frontier_loop}`, `research/llm`.
**Zustand.** Ein `EVFilter` je Lauf.
**Kosten.** Der Kopf nennt einen Pilotlauf mit ~4 $ fuer n=300 (`distill_run.py:10`).
**Mess-Status.** UNGEMESSEN (kein EV-Arm auf den erzeugten Daten).
**Allein benutzbar?** Nur zusammen mit dem `dataset/`-Zweig.
**Fallstricke.** Parallel sind NUR die API-Aufrufe; das Gatter ist bewusst seriell, weil `EVFilter` Zustand haelt.
Wer das parallelisiert, zerstoert Dedup und Statistik still.

### Lehrer-Destillation (Ernte) — `pipeline/distill_teacher.py`
**Zweck.** Filtert die vom Pod zurueckgeholten Rohkandidaten des grossen Lehrermodells zu einem SFT-Korpus.
**Schnittstelle.** `main()` (`python -m pipeline.distill_teacher [in] [out]`).
**Eingabe/Ausgabe.** `data/teacher_raw.jsonl` rein → `dataset/shards/teacher.jsonl` raus. Legalitaet wurde bereits
auf dem Pod durch `run_program` erzwungen, hier laufen Schema/Relevanz/Dekontamination/Dedup.
**Abhaengigkeiten.** `pipeline/filter`, `pokerbot/config`, optional `dataset/decontam`.
**Zustand.** Ein Filter je Lauf.
**Kosten.** Nicht gemessen.
**Mess-Status.** UNGEMESSEN; die Datei selbst schreibt die Grenze hin: Destillation hebt den START, nicht die
Decke (`distill_teacher.py:6-7`).
**Allein benutzbar?** Nur im Verbund.
**Fallstricke.** Wenn `dataset/decontam` fehlt, faellt der Code still auf eine LEERE Dekontaminationsmenge zurueck
(`distill_teacher.py:20-24`) — dann laeuft G3 wirkungslos mit und man trainiert womoeglich auf Testspots.

### Shard-Qualitaetspruefer — `pipeline/inspect_teacher.py`
**Zweck.** $0-Gatter vor grossen Ausgaben: zeigt Aktionsmischung, Erdungsrate und Degeneriertheit je Shard.
**Schnittstelle.** `stats(path) -> dict`, `main()` (`python -m pipeline.inspect_teacher [shard ...]`).
**Eingabe/Ausgabe.** JSONL-Shards rein; je Shard Aktionsanteile, Anteil mit `api.*`-Aufruf vor dem ersten
`decide` ("grounded"), `decide_mix`-Anteil, Strassenabdeckung.
**Abhaengigkeiten.** `pokerbot/config` (hart), sonst Standardbibliothek — kein torch.
**Zustand.** Zustandslos.
**Kosten.** Nicht gemessen (reines Zeilenlesen).
**Mess-Status.** UNGEMESSEN. Die Schwellen sind als Gate-Kriterien FESTGELEGT, nicht gemessen: keine Einzelaktion
ueber 70 %, Aggressionsanteil innerhalb ~15 Prozentpunkten der Solver-Baseline (`inspect_teacher.py:6-8`).
**Allein benutzbar?** Ja, mit minimaler Anpassung des Config-Imports.
**Fallstricke.** "grounded" ist ein reiner Textcheck auf `api.` vor dem ersten `decide` — ein Programm, das die
Zahl berechnet und dann ignoriert, gilt als geerdet.

### Selbstwachsende Mathematik — `pipeline/math_loop.py`
**Zweck.** Laesst ein Frontier-Modell neue exakte Formeln vorschlagen, prueft jede gegen die Engine und
materialisiert nur die verifizierten in die aufrufbare Werkzeugkiste.
**Schnittstelle.** `grow_math(request, model='gpt-5.5', max_tokens=16000, consult=None) -> dict`.
**Eingabe/Ausgabe.** Textwunsch rein; raus die Zahl der verifizierten/verworfenen Formeln und der Pfad der
neu erzeugten `postflop_formulas.py`.
**Abhaengigkeiten.** `research/{llm, postflop_calc_consult, postflop_calc_gate}` (hart).
**Zustand.** Schreibt in `knowledge_base/math/` — also in die Verbotszone der Projektdoktrin.
**Kosten.** Nicht gemessen.
**Mess-Status.** UNGEMESSEN als EV-Hebel. Belegt ist der einmalige Ertrag des zugrundeliegenden Wegs: 34
generierte Postflop-Berechnungen, ALLE 34 engine-verifiziert (`docs/STATE.md:1409-1412`).
**Allein benutzbar?** Nein — ohne den `research/`-Gate-Pfad ist es nur ein LLM-Aufruf.
**Fallstricke.** Es schreibt generierten Code in den Mathematik-Kern. In diesem Repo sind diese Dateien per
Doktrin unveraenderlich; ein Fremder sollte den Ausgabepfad umlenken, bevor er das ausfuehrt.

### Laufauswertung — `pipeline/process_run.py`
**Zweck.** Macht aus den vier zurueckgeholten Artefakten eines Pod-Laufs EIN Urteil.
**Schnittstelle.** `unpack_adapter()`, `gate_summary() -> (zeilen, pass_bool|None)`, `curve_summary() -> zeilen`,
`gpu_summary() -> zeilen`, `verdict(gates_pass, curve_rows) -> str`, `main()`.
**Eingabe/Ausgabe.** Liest (alles optional) `models/qwen_poker_grpo.tgz`, `data/eval_gates.json`,
`data/training_metrics.jsonl`, `data/gpu_load.jsonl`; druckt Gate-Leiter, Lernkurve, GPU-Last, Urteil.
**Abhaengigkeiten.** `pokerbot/config` (hart); kein torch.
**Zustand.** Entpackt den Adapter nach `models/qwen_poker_grpo/`.
**Kosten.** Nicht gemessen.
**Mess-Status.** UNGEMESSEN. In diesem Arbeitsverzeichnis fehlt `data/eval_gates.json`,
`data/training_metrics.jsonl` ist vorhanden — der Bericht laeuft also nur teilweise.
**Allein benutzbar?** Nur fuer genau dieses Dateiquartett.
**Fallstricke.** Fehlende Dateien werden als "Lauf nicht fertig" gemeldet, nicht als Fehler — ein leerer Bericht
sieht aus wie ein harmloser Zwischenstand, auch wenn der Lauf in Wahrheit abgestuerzt ist.

---

# Teil D — Modelle und Randstuecke

### Modell-Artefakte — `models/` (nicht im Git)
**Zweck.** Lagert die LoRA-Adapter und die gepackten Pod-Ergebnisse dieser Spur.
**Schnittstelle.** Keine — Dateien. Adapter werden ueber `peft.PeftModel.from_pretrained(base, pfad)` geladen.
**Eingabe/Ausgabe.** Vorhandene Verzeichnisse/Dateien (Stand dieses Arbeitsverzeichnisses):
`qwen_poker_ckpt500/`, `qwen_poker_grpo/` (beide Basis `Qwen/Qwen3-8B`, LoRA r=64), `qwen_poker_lora/`
(Basis `THUDM/GLM-Z1-9B-0414`, r=64), `qwen_local_*`, `qwen_1.7b_aligned/`, `qwen_smoke/`, sowie die Tarballs
`grpo_slim.tgz` (708 MB), `grpo_slim_baseline.tgz` (706 MB), `qwen_poker_grpo.tgz` (708 MB),
`qwen_poker_grpo_live.tgz` (710 MB), `qwen_poker_sft.tgz` (2,8 GB), `sft_new.tgz` (2,1 GB),
`sft_slim.tgz` (706 MB) und die Kurve `grpo_metrics.jsonl`.
**Abhaengigkeiten.** `peft`/`transformers` und das jeweilige Basismodell aus dem Netz.
**Zustand.** Reine Artefakte; `models/` ist gitignored (`.gitignore:12`) — ein Klon des Repos hat sie NICHT.
**Kosten.** Speicher wie oben (Summe ~8 GB im Verzeichnis).
**Mess-Status.** Der geschuetzte Stand `grpo_slim_baseline.tgz` ist das Modell mit −43,30 ± 7,15 AIVAT bzw.
robust eingeordnet ~−37 bis −40 mit fettem linken Rand (`docs/STATE.md:1159`, `:1121`). Die spaeteren Modelle
sind REFUTIERT (−90,18, `docs/STATE.md:1132`).
**Allein benutzbar?** Nur mit dem passenden Basismodell und derselben Prompt-Verdrahtung (Made-Hand-Block AN,
to_call-Fix AN — sonst misst man einen anderen Bot).
**Fallstricke.** Adapter und Serve-Konfiguration gehoeren zusammen. Dieselben Gewichte mit anderem Prompt haben im
Projekt Unterschiede von 40 bb/100 erzeugt (`docs/STATE.md:1120`) — ohne die Flags ist ein Adapter wertlos.

### RunPod-Serverless-Lehrer — `handler.py` (Repo-Wurzel)
**Zweck.** Ein vLLM-Worker, der DSL-Programme im Batch erzeugt und direkt auf dem Worker engine-gatet.
**Schnittstelle.** RunPod-Job `{"input": {"n", "seed", "temperature", "max_tokens"}}` →
`{"examples": [...], "kept", "total", "model"}`.
**Eingabe/Ausgabe.** Nur JSON; die Spots kommen aus `research/teacher_generate.build_spots`, die Gatterung aus
`gate_and_rows`.
**Abhaengigkeiten.** `runpod`, `vllm`, `transformers`, `pokerbot/brain/{modes,policy}`, `research/teacher_generate`.
**Zustand.** Laedt das Modell EINMAL beim Kaltstart auf Modulebene; setzt global `modes.set_mode("fast")`.
**Kosten.** Nicht gemessen.
**Mess-Status.** UNGEMESSEN.
**Allein benutzbar?** Nur auf RunPod-Serverless.
**Fallstricke.** `modes.set_mode("fast")` ist prozessweit — der Gate-Equity im Worker rechnet damit mit 300
MC-Iterationen, waehrend eine lokale Nachpruefung per Default 1000 nimmt und andere Urteile faellen kann.

### Zugehoerige Werkzeuge ausserhalb der drei Ordner (nur Wegweiser, kein Katalogformat)
- `research/claude_brain_smoke.py` — lokaler Ausgabe-Check des Claude-Brains vor jedem Geldausgeben.
- `research/claude_export.py` — laesst das Brain spielen und exportiert PokerStars-Handhistorien fuer die
  externe GTO-Benotung.
- `research/claude_vs_engine.py` — gepaarter Entscheidungsdiff Brain gegen Engine samt der Programm-Kommentare
  als "Begruendung".
- `research/glm_local_probe.py` — faehrt das trainierte 9B lokal 4-bit; damit wurde der Hand-Lesefehler gefunden,
  der zum Made-Hand-Block fuehrte.
- `research/teacher_generate.py` — die Spot- und Gatterfunktionen, die `handler.py` auf dem Pod wiederverwendet.
- `infra/gtow_glm_pod.py` — isolierter Pod, der den GRPO-Adapter in die Basis mergt, per vLLM serviert und gegen
  den externen Benchmark spielt.
- `research/llm.py` — die geteilten Claude-/OpenAI-Aufrufhelfer (strukturierte Ausgabe, Prompt-Caching, Retries).
- `pokerbot/strategy/postflop_corset.py` — benutzt `brain/api.py`, um einen Call gegen eine grosse Bet zu deckeln;
  GEMESSEN als NO-OP (ueber 13 Spektrum-Spots ueber-callte das Modell gar nicht; `docs/STATE.md:1152`).
- `tests/test_made_hand_read.py` — der $0-Test, der den Made-Hand-Block festnagelt; guter Einstiegspunkt, um zu
  sehen, wie man einen `Spot` von Hand baut.

---

## Wissensbasis, Daten, Werkzeuge

Dieses Subsystem enthaelt keine Spiel-Logik: es ist der Vorrat (destilliertes Buch-/Solver-/Gegner-Wissen als
JSON und Python), das Daten-Verzeichnis (registry + Konverter + Shards) und die Werkzeugkiste (Miner, Gates,
Konsult- und Replay-Skripte), aus der die Strategie-Module gefuettert und die Messungen erzeugt werden.
Brauchen wirst du davon fast nichts vollstaendig — aber die Formelmodule, die Range-Blueprints, die
Run-Ablage-Konvention und zwei bis drei Miner sind einzeln, ohne den Rest des Repos, uebernehmbar.
Wenn du nur EINE Sache mitnimmst: die Run-Ablage + das Journal (unten), weil ohne sie keine Zahl ueberlebt.

---

# 1. knowledge_base/ — das destillierte Wissen

### Kern-Formeln — `knowledge_base/math/formulas.py`
**Zweck (1 Satz).** 12 aus den Poker-Buechern extrahierte und beim Erzeugen ausgefuehrte Grundformeln (Pot Odds,
MDF, EV, SPR, Fold Equity, Outs, Blocker-Kombinatorik, Equity-Realisierung) als reines stdlib-Python.
**Schnittstelle.**
- `compute_pot_odds(P, B, C) -> (ratio, required_equity)` — Pot-Odds als Verhaeltnis und als noetige Equity.
- `equity_needed_to_call(pot_before_call, call_amount, villain_risked_this_street=0.0) -> float`.
- `expected_value(probabilities, payoffs) -> float` — Summe p·payoff, mit Laengen-/Summenpruefung.
- `minimum_defense_frequency(pot, bet) -> float` — MDF = p/(p+b).
- `bluff_to_value_and_frequencies(P, ...)` — Bluff/Value-Verhaeltnis und Frequenzen eines polaren Bets.
- `required_future_winnings_for_implied_odds(pot_size, call_cost, hit_probability) -> float`.
- `required_fold_equity(P, R, C, E) -> float` — noetige Fold-Frequenz eines Raises/Jams.
- `outs_to_equity_rule_2_and_4(outs, cards_to_come) -> float`.
- `compute_spr(effective_stack, pot_size) -> float`.
- `count_hand_combos_with_blockers(pattern, known_cards) -> int`.
- `breakeven_bluff_percentage(bet_size, pot_size) -> float` — Alpha = b/(b+p).
- `equity_realization(eq, pot, cost, ev=None) -> (…)`.
**Eingabe/Ausgabe.** Nur floats/ints bzw. Kartenlisten als 2-Zeichen-Strings (`'As'`); Rueckgabe float oder Tupel.
Keine dicts, kein Zustand, keine IO.
**Abhaengigkeiten.** Nur `math`/`typing` — KEINE Repo-Abhaengigkeit. Vollstaendig kopierbar.
**Zustand.** Zustandslos.
**Kosten.** Nicht gemessen (arithmetische Einzeiler; die Kosten liegen im Aufrufer).
**Mess-Status.** UNGEMESSEN als EV-Hebel. Die Funktionen sind bei der Erzeugung ausgefuehrt worden
(`research/extract_math.py:111 verify()` fuehrt den generierten Code aus). CLAUDE.md-Doktrin dazu ist
ausdruecklich: Formeln sind „Suppenfleisch" — Features in empirischen Deciders, nie Dogma darueber; das
Frequenz-Matching nach Formel wurde 3x gemessen widerlegt (CLAUDE.md, Block „OPERATIVE DOKTRIN").
**Allein benutzbar?** Ja, vollstaendig. Datei kopieren, fertig.
**Fallstricke.** `compute_pot_odds` und `equity_needed_to_call` definieren `pot` UNTERSCHIEDLICH (einmal Pot VOR
dem Bet plus Bet getrennt, einmal Pot INKLUSIVE des Bets). Wer sie mischt, rechnet still falsch.

### Erweiterte Formelmodule — `knowledge_base/math/postflop_formulas.py`, `knowledge_base/math/strategy_formulas.py`
**Zweck (1 Satz).** 66 weitere Rechenfunktionen (34 postflop, 32 strategisch) als aufrufbare Bibliothek —
Bluff/Value-Ratios, geometrisches Sizing, Rake-korrigierte Pot-Odds, Range-Kombinatorik, Preflop-Sizings,
Polarisierungs-/Textur-Indizes, Exploit-Deltas.
**Schnittstelle.** Alles Modul-Funktionen, alle mit Typ-Annotationen, u.a.
`alpha_break_even_bluff_frequency(bet, pot)`, `minimum_defense_frequency_by_bet_fraction(pot_fraction)`,
`per_street_geometric_bets(pot, effective_stack, streets) -> list[float]`,
`pot_odds_required_equity_with_rake(to_call, pot, rake_fraction, rake_cap)`,
`range_combo_count(hand_classes, known_cards) -> int`,
`preflop_open_raise_size_bb(position, effective_bb, ante_bb=0.0)`,
`cbet_frequency(texture_wetness, in_position, spr, range_advantage, nut_advantage)`,
`exploit_fold_deviation_ev(pot_size, bet_size, actual_fold_frequency, equilibrium_fold_frequency)`.
**Eingabe/Ausgabe.** Skalare rein, Skalare/Listen raus. `hand_classes` = Sequenz `(rank1, rank2, suited|None)`.
**Abhaengigkeiten.** stdlib only (`math`, `typing`). Ersetzbar/kopierbar.
**Zustand.** Zustandslos.
**Kosten.** Nicht gemessen.
**Mess-Status.** UNGEMESSEN als Spielstaerke. GEMESSEN NEUTRAL als Konsistenz: `pokerbot/autogym/verify_refs.py`
fuehrt alle hinterlegten `verify_expr`-Referenzen gegen die installierten Module aus — laut CLAUDE.md
(AUTOGYM-Block) zuletzt 66/66. Wichtige Einschraenkung steht im Werkzeug selbst (`verify_refs.py:5-9`):
verify_expr stammt aus derselben Erzeugung wie die Formel, das ist Konsistenz, NICHT Wahrheit.
**Allein benutzbar?** Ja. Einzige Einschraenkung: die Vorsicht bei den heuristischen Funktionen —
`cbet_frequency`, `range_morphology_selector`, `capped_range_penalty` u.a. sind LLM-erzeugte Modelle, keine
Ableitungen aus Poker-Theorie.
**Fallstricke.** Die Module sind NICHT alle gleichwertig: die exakten (Alpha, MDF, Pot-Odds, Kombinatorik)
stehen neben freien Heuristiken mit erfundenen Gewichten. Wer sie als Block uebernimmt, importiert die
Heuristiken mit — sie sind an keiner Stelle dieses Repos EV-gemessen.

### Math-Rohartefakte — `knowledge_base/math/*.json` / `*.md`
**Zweck (1 Satz).** Die Quelle, aus der die drei Formelmodule materialisiert wurden, plus die
Buch-Volltext-Extraktion.
**Schnittstelle.** Reine Datendateien: `math.jsonl` (13 Zeilen, je `{id, topic, formula:{name, definition,
formula_latex, …}, worked_example, function_name}`), `math.json` (dieselben gemerged),
`postflop_calc_verified.json` / `strategy_calc_verified.json` (`{"calculations": [ {category, definition,
formula_plain, function_name, inputs, name, python_function, verify_expr, verify_value, worked_example} ]}`),
`mathematics_of_poker.json` + `.md` (Buch-Extrakt, 540 KB Markdown).
**Eingabe/Ausgabe.** Nur Ausgabe. Konsumenten: `dataset/build/from_math.py`, `dataset/build/from_calc.py`,
`pokerbot/autogym/verify_refs.py`.
**Abhaengigkeiten.** Keine.
**Zustand.** Zustandslos, statisch.
**Kosten.** ~1,5 MB gesamt.
**Mess-Status.** UNGEMESSEN (Datenartefakte).
**Allein benutzbar?** Ja — die `*_verified.json` sind das interessanteste Stueck: sie enthalten den
Python-Quelltext JEDER Funktion plus einen ausfuehrbaren Selbsttest-Ausdruck, sind also ein sofort
regenerierbares Formelpaket.
**Fallstricke.** `postflop_calc.json` und `postflop_calc_verified.json` sind byte-gleich gross (40937) — die
„verified"-Datei ist keine gefilterte Teilmenge; der Name suggeriert eine Selektion, die nicht stattfand.

### Konzepte — `knowledge_base/concepts/concepts.jsonl`
**Zweck (1 Satz).** 67 Datensaetze mit aus den Buechern gezogenen Strategie-Konzepten (Titel, Kategorie,
Kurzfassung, Details) — Prosa-Wissen, kein Code.
**Schnittstelle.** JSONL, je Zeile `{id: "<buch>:<seiten>", book, concepts: [{title, category, summary,
details, …}]}`.
**Eingabe/Ausgabe.** Nur Lesen. Erzeugt von `research/extract_concepts.py`.
**Abhaengigkeiten.** Keine (Daten).
**Zustand.** Statisch.
**Kosten.** 765 KB.
**Mess-Status.** UNGEMESSEN als Spielstaerke. In `dataset/registry.py` NICHT als aktives Gold gefuehrt; die
Mischung Konzepte+Math+Exploit in einem Shard (`shard.local_kb`) ist dort ausdruecklich als Ursache eines
frueheren Trainings-Fehlschlags markiert (`registry.py:83-86`, „the original frac_bad=0.97 cause; NOT the gold").
**Allein benutzbar?** Ja als Prompt-/RAG-Material. Fuer eine Engine wertlos, weil nicht maschinell auswertbar.
**Fallstricke.** Es ist Buchprosa. Sie klingt nach Wahrheit und ist an keiner Stelle gegen bb/100 geprueft.

### Theorie-Extrakte — `knowledge_base/theory/`
**Zweck (1 Satz).** Destillate von Forschungspapieren und Konsult-Antworten (Pluribus, Supremus, Deep-CFR+,
sequentielles Gleichgewicht, WEVA-Abstraktion, algorithmische Spieltheorie) plus eigene Doktrin-Dokumente.
**Schnittstelle.** JSON pro Paper (`pluribus_paper.json`, `supremus_paper.json`, `deep_pdcfr_paper.json`,
`weva_abstraction_paper.json`, `seq_equilibrium_cfr_paper.json`, `nn_architecture_paper.json`,
`algorithmic_game_theory.json`) + Markdown-Analysen (`grand_synthesis.md`, `brown_vnm_169.md`,
`bluff_lizenzen.md`, `exploit_gto_bridge.md`, `gto_hybrid.md`, `poker_for_compute.md`, …).
**Eingabe/Ausgabe.** Nur Lesen.
**Abhaengigkeiten.** Keine.
**Zustand.** Statisch.
**Kosten.** ~350 KB.
**Mess-Status.** UNGEMESSEN. `harvard_general_cfr_paper.json` ist 2 Byte gross — ein leeres JSON, also ein
fehlgeschlagener Extraktionslauf, der nie geloescht wurde.
**Allein benutzbar?** Ja als Lesematerial.
**Fallstricke.** Metadaten aus LLM-Konsults sind hier teilweise ungeprueft; das Repo hat dafuer eine eigene
Regel (CLAUDE.md: „Perplexity scrambles metadata — NEVER cite unverified"). Nimm keine Paper-Zitation aus
diesen Dateien ohne Gegenpruefung.

### Exploit-Wissen — `knowledge_base/exploit/`
**Zweck (1 Satz).** Vorberechnete „Gegner sieht aus wie X in Spot Y → verschiebe Aktion Z um Δ"-Direktiven
plus gemessene Gegner-Leaks.
**Schnittstelle.**
- `playbook.jsonl` — 11.520 Zeilen, je `{opp:{vpip,pfr,fold_to_cbet,three_bet,af}, ctx:{stack_bb,hero_position,
  street,facing}, directive:{reasoning, level, target, adjust:{action, freq_delta}, confidence}}`.
- `unified.json` — 62 verdichtete Regeln `{stat, condition, spot, adjustment, delta, magnitude, confidence,
  rationale, merged}`.
- `pluribus_leaks.json` (`decisions`, `leaks`, `bet_size_footprint`, `river_call_strength`),
  `slumbot_fold.json`, `stack_depth_params.json`, `beyond_gto.json`, `exploitative_poker.json`.
**Eingabe/Ausgabe.** Nur Lesen; konsumiert von `pokerbot/strategy/unified_exploit.py`,
`pokerbot/strategy/playbook.py` und `dataset/build/from_exploit.py`.
**Abhaengigkeiten.** Keine (Daten). Die Konsumenten sind hart, das Format ist ersetzbar.
**Zustand.** Statisch.
**Kosten.** playbook.jsonl 7,2 MB — zeilenweise lesen, nicht komplett in den Speicher.
**Mess-Status.** GEMESSEN NEGATIV fuer den daran haengenden HU-Exploit-Pfad: das Journal
(`data/autogym/journal.jsonl`, Eintrag `EXPLOIT-GATE-VERDIKT` vom 2026-09-09) misst `POKERB_EXPLOIT=1` gegen 0
auf gepaarten Decks, 600 Decks je Liga-Profil: alle acht Punktschaetzer ≤ 0, gepoolt ca. −12 bb/100 (SE ~4,5).
Verdikt dort woertlich: „der Dirichlet-River-Exploit VERLIERT gegen jedes Liga-Profil". Der 6-max-Read-Pfad
ist im selben Eintrag NEUTRAL (+3,6 ± 13,5).
**Allein benutzbar?** Ja — `unified.json` (62 Regeln) ist klein und direkt in eine eigene Overlay-Logik
uebersetzbar.
**Fallstricke.** Das Playbook ist LLM-generiert (`research/exploit_playbook.py`), nicht aus Haenden gemessen.
Es ist ein VORSCHLAGS-Generator; das Repo hat den daran haengenden Exploit-Mechanismus gemessen und AUS
geschaltet. Uebernimm die Daten, nicht die Annahme, dass sie funktionieren.

### Preflop-Ranges — `knowledge_base/ranges/` + `knowledge_base/cfr/preflop_pushfold.json`
**Zweck (1 Satz).** Die fertigen Preflop-Blueprints: pro Knoten und Handklasse eine Aktions-Mischung.
**Schnittstelle.**
- `preflop_blueprint.json` — dict mit Knoten `OPEN, LIMP, ISO, 3BET, 4BET, 5BET, JAMSB, JAMBB`; je Knoten
  dict Handklasse → Mischung, z.B. `"AA": {"fold": 0.0, "call": 0.0, "3bet": 1.0}`.
- `preflop_blueprint_k0.json`, `preflop_blueprint_solvergraft.json` — Varianten desselben Formats.
- `preflop_pushfold.json` — Nash-Push/Fold, geschluesselt nach Effektivstack in bb (`"2"…"9"…`).
- `preflop_eqmatrix.json` (`{n, sims, eq}` — vorgerechnete Klassen-gegen-Klassen-Equities),
  `preflop_gto_table.json` (1,1 MB), `preflop_leaf_table.json`, `ranges_grids.json`, `range_captions.json`,
  `ranges_vision.jsonl` (38 vision-geparste Buch-Grids).
**Eingabe/Ausgabe.** Nur Lesen; Konsument ist `pokerbot/strategy/preflop_blueprint.py`.
**Abhaengigkeiten.** Keine (Daten). Handklassen-Schreibweise ist die uebliche (`AKs`, `T9o`, `77`).
**Zustand.** Statisch.
**Kosten.** ~2,5 MB gesamt; `preflop_eqmatrix.json` 500 KB.
**Mess-Status.** GEMESSEN POSITIV im Verbund, nicht isoliert: CLAUDE.md nennt Preflop als „near-solved
blueprint" mit einem Anteil von etwa −1,6 bb/100 am Gesamtverlust gegen GTO Wizard (Zerlegung des −20-Laufs).
Isoliert wurde der Blueprint in diesem Repo nicht gegen eine Alternative A/B-getestet.
**Allein benutzbar?** Ja, das ist der am leichtesten uebernehmbare Teil der ganzen Wissensbasis: JSON laden,
Handklasse bilden, Mischung ziehen.
**Fallstricke.** Der Blueprint wird im Bot erst ab einer Stack-Tiefe verwendet — laut Journal-Eintrag
`KONSULT-SOL-KORREKTUR` (2026-09-10) feuert er „erst ab 140 bb effektiv (bot.py:200)". Wer ihn bei 100 bb
erwartet, misst einen anderen Bot als er denkt; genau dieser Irrtum steht als korrigierte Doku-Behauptung im
Journal.

### Postflop-Artefakte — `knowledge_base/postflop/`
**Zweck (1 Satz).** Die trainierten Solver-Imitations-Netze (Bet-Frequenz je Strasse) plus zwei kleine
kalibrierte Tabellen und ein Regel-Playbook.
**Schnittstelle.** Dateien, keine Funktionen: `advisor.pt` (Flop), `turn_advisor.pt`, `river_advisor.pt`,
`river_advisor_la.pt` (line-aware), `defense_advisor.pt`, `deepcfr_hunl.pt` (556 KB, stillgelegt),
`texture_freqs.json` (`{"IP": {"ALL":0.741, "connected":0.609, "high":0.785, "low":0.73, "monotone":0.576,
"paired":0.781}, "OOP": {…0.224…}}`), `calibrated_priors.json` (`{"cbet_eq":0.72, "donk_eq":0.75}`),
`openai_strategy.json` (`{summary, rules[15], fold_equity, parameters}`).
**Eingabe/Ausgabe.** `.pt` = torch-MLPs, geladen von `pokerbot/strategy/advisor.py`; die JSONs von
`pokerbot/strategy/postflop.py` bzw. `playbook.py`.
**Abhaengigkeiten.** Die `.pt` brauchen torch UND die exakte Feature-Reihenfolge des Trainers
(`research/train_*_advisor.py`) — harte Kopplung, ein Netz ohne seinen Feature-Bau ist wertlos.
**Zustand.** Statisch (geladen einmal je Prozess).
**Kosten.** Je Netz ~24 KB; Ladezeit nicht gemessen. Es gibt eine gemessene Batch-Beschleunigung des
Advisor-Pfades von 2,2x (CLAUDE.md, AUTOGYM-Block „Advisor-Batch (2,2x)").
**Mess-Status.** GEMESSEN POSITIV laut Registry-Beschreibung: Flop +63 % gegen eine reine Handstaerke-Baseline,
Turn +46 %, River +18 % (`dataset/registry.py:97`, `:99`, `:101`). Achtung: das ist eine Imitations-Metrik
(Naehe zur Solver-Frequenz), KEIN bb/100. `defense_advisor.pt` traegt in derselben Datei die Notiz
„verify live wiring" (`registry.py:104`) — die Verdrahtung ist also selbst im Repo nicht bestaetigt.
**Allein benutzbar?** Nur mit dem passenden Trainer. Praktisch: neu trainieren statt uebernehmen.
**Fallstricke.** Die Registry beschreibt `openai_strategy.json` als „the 62-rule postflop strategy playbook"
(`registry.py:112`) — die Datei enthaelt tatsaechlich 15 Regeln unter `rules`; die 62 stehen in
`knowledge_base/exploit/unified.json`. Die Beschreibung ist falsch.

### Hand-Historien — `knowledge_base/hand_histories/`
**Zweck (1 Satz).** 10.000 vollstaendige 6-max-Pluribus-Haende mit allen Holecards als Bewertungs- und
Gegnermodell-Verteilung.
**Schnittstelle.** `pluribus_hands.jsonl` — je Zeile `{hand, players[6], bb, button, positions{seat:pos},
holes{seat:"TcQc"}, board[], actions[{seat, verb, amount, street}]}`; Verben im PHH-Stil (`f`, `cbr`, …).
`pluribus_stats.json` — aggregiert (`hands_catalogued: 10000`, `pluribus_net_bb_per_100: -7.09`, `by_position`
mit vpip/pfr/avg_open_bb je Position). Ausserdem ein Ordner `players - handhistories/Coin Poker` mit
persoenlichen Historien.
**Eingabe/Ausgabe.** Nur Lesen; Konsument `pokerbot/analysis/pluribus_catalog.py`, `benchmark/pluribus_leaks.py`.
**Abhaengigkeiten.** Keine.
**Zustand.** Statisch.
**Kosten.** 9,6 MB.
**Mess-Status.** GEMESSEN als Datum (nicht als Hebel): `pluribus_net_bb_per_100 = -7.09` ueber die 10.000
katalogisierten Haende (`knowledge_base/hand_histories/pluribus_stats.json`).
**Allein benutzbar?** Ja — sauberes, vollstaendig aufgedecktes 6-max-Material, gut fuer Gegnermodelle und
Replay-Tests.
**Fallstricke.** Die Betraege sind in Chips bei `bb: 100`; wer sie als bb liest, ist um Faktor 100 daneben.

### Turnier-Doktrin — `knowledge_base/tournament/DOKTRIN.md`
**Zweck (1 Satz).** Zehn Punkte ICM-/Turnier-Doktrin mit exakten Formeln (Malmuth-Harville, Bubble-Faktor,
Gap-Konzept, Phasen-Kurve), als Spezifikation der Turnier-Module.
**Schnittstelle.** Markdown. Nennt die Implementierungen: `pokerbot/strategy/icm.py`,
`pokerbot/strategy/tournament.py`, `pokerbot/arena/tourney.py`, Tests `tests/test_icm.py`,
`tests/test_tournament.py`.
**Eingabe/Ausgabe.** Nur Lesen (Doktrin, kein Code).
**Abhaengigkeiten.** Keine.
**Zustand.** Statisch.
**Kosten.** 4,5 KB.
**Mess-Status.** GEMESSEN POSITIV fuer den daraus gebauten Hebel: das ANTEILIGE Risiko-Premium
(`BF_eff = 1+(BF−1)·(to_call/Stack)`) misst laut CLAUDE.md (Block 2026-08-04) gepaart bei n=1500
**+10,0 ± 5,0 pp ROI, 95%-Band [+0,2, +19,9]**; der VOLLE Bubble-Faktor wurde im selben Experiment
REFUTIERT (−8 pp).
**Allein benutzbar?** Ja als Spezifikation — die Formeln sind exakt genug, um sie neu zu implementieren.
**Fallstricke.** Punkt 7 der Doktrin: Heads-up hat BF exakt 1,0. Wer den Bubble-Faktor auch im HU-Endspiel
anwendet, verbiegt genau den Teil, der schon vermessen ist.

### Scorecard — `knowledge_base/scorecard.json`
**Zweck (1 Satz).** Eingefrorenes Ergebnis eines alten Bewertungslaufs (gto_gap / duplicate) mit Zeitstempel
und git-SHA.
**Schnittstelle.** JSON: `{timestamp, git_sha, agent, config:{mode,hands,decks,iters}, axes:{gto_gap:{buckets:
{ALL,OOP:ALL,IP:ALL}}, duplicate:{…}}}`.
**Eingabe/Ausgabe.** Erzeugt von `research/bot_audit.py`; in `registry.py` als Rolle `eval` gefuehrt.
**Zustand.** Statisch.
**Abhaengigkeiten.** Keine.
**Kosten.** 2,9 KB.
**Mess-Status.** VERALTET: Stand `2026-06-15`, `git_sha 53690a7`, Agent „PokerBot(exploit=True) -- the unified
MVP". Der Exploit-Modus ist seit 2026-09-09 gemessen negativ (siehe Exploit-Wissen oben) — die Zahlen
beschreiben einen Bot, den es nicht mehr gibt.
**Allein benutzbar?** Nein, nur als Format-Vorlage.
**Fallstricke.** Die Datei sieht aus wie ein aktueller Zustand und ist keiner. Das Repo hat dafuer eine
stehende Regel (CLAUDE.md: die lebende Wahrheit steht in `docs/STATE.md`).

---

# 2. dataset/ — die Datenverwaltung

### Daten-Registry — `dataset/registry.py`
**Zweck (1 Satz).** Die EINE Aufzaehlung aller Trainings-/Wissens-Assets mit Rolle, Beschreibung, Schema,
Herkunft und einem `current`-Flag, damit die Trainings-Pipeline Daten nach ROLLE statt nach Pfad findet.
**Schnittstelle.**
- `@dataclass(frozen=True) Asset(key, path, role, desc, schema, provenance, stage, current, note)`.
- `ROLES = ("sft_gold","raw_shard","kb_advisor","kb_playbook","kb_ranges","kb_math","model","train_data","eval")`.
- `ASSETS: list[Asset]` — die Liste selbst (aktuell 30 Eintraege).
- `get(key) -> Asset`; `by_role(role, current_only=True) -> list[Asset]`.
- `sft_gold() -> list[Path]` — nur `current` Shards, die auf Platte existieren.
- `advisor(street) -> Path|None` fuer `'flop'|'turn'|'river'|'defense'`.
- `model(name) -> Asset`.
- `stats(asset) -> dict` — `{exists, bytes, rows?, action_mix?}`; zaehlt Zeilen nur unter 64 MB
  (`_ROWCOUNT_MAX_BYTES`), sonst `rows_uncounted: True`.
- `grep(term, roles=…, limit=20) -> list[{key, line, snippet}]` — Inhaltssuche ueber alle katalogisierten JSONL.
**Eingabe/Ausgabe.** Rein deklarativ; Rueckgaben sind `Path`/`Asset`/dict.
**Abhaengigkeiten.** Nur `pokerbot.config` (fuer die Wurzelpfade). Kein torch. Leicht ersetzbar.
**Zustand.** Zustandslos.
**Kosten.** Import ist billig; `stats()` liest die Datei (bei grossen JSONL sekundenlang).
**Mess-Status.** UNGEMESSEN (Infrastruktur, kein Spielhebel).
**Allein benutzbar?** Ja — das MUSTER ist das Uebernehmenswerte, nicht die Eintraege. Ein Datei-Katalog mit
Rolle + `current`-Flag + ehrlicher Notiz je Asset ist billig und verhindert genau die Verwechslungen, die im
Repo dokumentiert sind.
**Fallstricke.** Die Registry BESCHREIBT nur; sie verschiebt/benennt nichts (Kommentar `registry.py:14-16`),
und ihre Beschreibungen koennen vom Inhalt abweichen — Beispiel `registry.py:112` (siehe oben, „62 rules" fuer
eine 15-Regel-Datei). Beschreibungen sind kein Vertrag.

### Beispiel-Schema + Hygiene — `dataset/schema.py`
**Zweck (1 Satz).** Definiert den einen Trainings-Datensatz und die drei Hygiene-Gatter (Gueltigkeit,
Domaenen-Relevanz, Dedup/Decontam).
**Schnittstelle.**
- `make_example(source, spot, completion, action=None, type_="decision", meta=None) -> dict`.
- `is_relevant(text, min_hits=2) -> bool` — Regex-Gatter ueber ~50 Poker-/Mathe-Begriffe.
- `spot_key(spot) -> str` — sha1 ueber whitespace-/case-normalisierten Spot-Text.
- `validate(ex) -> bool`; `dedup(examples, decontam_keys=None)` (Generator, Statistik in `ex_stats[0]`);
  `write_jsonl(path, examples) -> int`.
- `VALID_SOURCES = {pokerbench, ranges, postflop, exploit, math, concepts, distill, selfplay, solver}`.
**Eingabe/Ausgabe.** Ein Datensatz = `{"source","type","spot","completion","action":{action,size_bb}|None,
"meta":{}}`; JSONL raus.
**Abhaengigkeiten.** stdlib only.
**Zustand.** Ein Modul-globaler Nebenausgang `ex_stats` (Liste mit einem Element) — der wird bei jedem
`dedup()`-Durchlauf ueberschrieben.
**Kosten.** Linear in der Zeilenzahl.
**Mess-Status.** UNGEMESSEN.
**Allein benutzbar?** Ja, vollstaendig (stdlib).
**Fallstricke.** `ex_stats` wird ERST am Generator-Ende gesetzt. Wer `dedup()` nur teilweise konsumiert oder
zwei Laeufe verschachtelt, liest die Statistik des falschen Laufs.

### Decontamination — `dataset/decontam.py`
**Zweck (1 Satz).** Haelt die Spot-Schluessel des PokerBench-TEST-Splits vor, damit kein Trainingsbeispiel
einen Testspot enthaelt.
**Schnittstelle.** `pokerbench_test_keys(refresh=False) -> set` — liest den Cache
`dataset/decontam_keys.json` (484 KB) oder baut ihn per HuggingFace `RZ412/PokerBench` split='test' neu.
**Eingabe/Ausgabe.** Menge von sha1-Strings, direkt an `schema.dedup(..., decontam_keys=…)` uebergebbar.
**Abhaengigkeiten.** `pokerbot.config`, `dataset.schema`; `datasets` (HF) NUR beim Refresh — faellt sonst
still auf eine leere Menge zurueck.
**Zustand.** Datei-Cache.
**Kosten.** Cache-Lesen ~0,5 s.
**Mess-Status.** UNGEMESSEN.
**Allein benutzbar?** Ja.
**Fallstricke.** Bei fehlendem HF-Zugriff gibt die Funktion eine LEERE Menge zurueck und druckt nur eine
Meldung (`decontam.py:29-31`) — die Decontamination faellt dann still aus, der Aufrufer merkt es nicht.

### Datenkarte — `dataset/build_manifest.py` (→ `CATALOG.md`, `dataset/manifest.json`)
**Zweck (1 Satz).** Rendert aus der Registry eine nie veraltende Markdown-Karte plus maschinenlesbares
Manifest, inklusive eines Anhangs mit noch nicht katalogisierten Dateien.
**Schnittstelle.** `build() -> (markdown, manifest_list)`; `main()`. Aufruf:
`python -m dataset.build_manifest`.
**Eingabe/Ausgabe.** Liest `dataset.registry` + Platte, schreibt `CATALOG.md` (git-versioniert) und
`dataset/manifest.json` (Liste von Asset-dicts mit Live-Zeilenzahlen/Groessen).
**Abhaengigkeiten.** `dataset.registry`, `pokerbot.config`. Hart, aber trivial ersetzbar.
**Zustand.** Zustandslos.
**Kosten.** Nicht gemessen; laeuft ueber alle JSONL unter 64 MB (Zeilenzaehlung).
**Mess-Status.** UNGEMESSEN.
**Allein benutzbar?** Ja, mit der Registry zusammen.
**Fallstricke.** `CATALOG.md` ist eingecheckt und wird NICHT automatisch neu erzeugt. Der aktuelle Stand
stammt vom 2026-06-20 und weicht von der Platte ab.

### Die Konverter — `dataset/build/`
**Zweck (1 Satz).** Zwoelf Skripte, die aus den lokalen Quellen (Formeln, Playbook, Solver, Self-Play,
Blueprint, PokerBench) einheitliche DSL-Trainingsdatensaetze bauen.
**Schnittstelle.** Jedes Modul exportiert `build(...)` als Generator ueber Beispiel-dicts:
- `from_math.build()` — `knowledge_base/math/math.json` → Mathe-Aufgaben mit `api.<fn>`-Aufruf als Loesung.
- `from_calc.build(limit=None)` — die beiden `*_calc_verified.json` → „diese Engine-Funktion existiert"-Beispiele.
- `from_exploit.build(limit=None)` — `playbook.jsonl` → Read→Anpassung durch die GTO-Linse.
- `from_pokerbench.build(limit=None, streaming=True)` + `parse_output(out)` — HF-PokerBench → `decide(a, size_bb)`.
- `from_selfplay.build(n=800, seed=0, hero_seat=0, profiles=TRAIN_LEAGUE)` — echte Programm-Schleifen
  (rechnen → verzweigen → handeln), NICHT hartkodierte `decide()`-Aufrufe.
- `from_solver.build(boards=None, oop_range, ip_range, …)` + `mass_solve(n, out_path, …)` — TexasSolver-Mixes
  → `decide_mix({...}, size=)`.
- `from_hu.build_enum()` — treibt einen HU-Tisch zu JEDEM Blueprint-Knoten und emittiert Knoten × Handklasse.
- `from_hu_postflop.build(n_per_line=400, seed=0)` — HU-Postflop-Spots je Pot-Typ (limp/SRP/3bet/4bet).
- `run.main(full, pb, decontam)` — der Sammel-Lauf (`python -m dataset.build.run [--full]`).
- `curriculum.build(n_decisions=1500, pb=0, exploit=0, ground=False, seed=0)` — die vier geordneten Shards
  a_contract → b_ground → c_decide → d_exploit.
- `streets.street_of(spot_text)` + `main(test_frac=0.02, seed=0)` — Strassen-Split + dekontaminierter Test-Fold.
- `add_made_hand.add_made_hand_line(spot_text)`, `verify()`, `apply_to_gold()` — nachtraegliches Einfuegen der
  Made-Hand-Zeile, byte-identisch zu `format_spot` mit eingeschaltetem Flag.
**Eingabe/Ausgabe.** Rein: die Wissensbasis + die Engine. Raus: JSONL nach `dataset/shards/`.
**Abhaengigkeiten.** HART an `pokerbot.brain.format_spot`, `pokerbot.brain.api`, `pokerbot.engine.table`,
`pokerbot.strategy.gto_oracle`, `training.rl_env`. Diese Konverter sind der am staerksten mit dem Rest des
Repos verwachsene Teil des Katalogs — praktisch nicht isoliert uebernehmbar.
**Zustand.** Zustandslos je Lauf; `add_made_hand --apply` SCHREIBT die Shards um (legt `<shard>.off.bak` an).
**Kosten.** Nicht gemessen ausser: `from_selfplay` braucht einen MC-Equity-Aufruf je Spot (Docstring: „no
rollouts (cheap: one MC-equity per spot)").
**Mess-Status.** GEMESSEN POSITIV fuer die FORM der Completion: die „Reasoning-Loop"-Form gegen die
dekorative Form gab lokal `frac_bad` 0,97 → 0,00 (Memory-Eintrag `reasoning-loop-not-decoration`, im
Modul-Docstring `from_selfplay.py:1-6` wiederholt). GEMESSEN NEGATIV fuer die Datenmischung:
`shard.solver_mass` wurde aus dem aktiven Gold ENTFERNT, weil 25,6k nicht-linienbewusste Flop-Solves die 2,2k
Lehrer-Beispiele 13:1 erschlagen (`registry.py:60-64`).
**Allein benutzbar?** Nein. Uebernehmenswert ist das Prinzip: eine Datei je Quelle, alle mit derselben
`build()`-Signatur, ein globales Dedup-/Relevanz-Gatter dahinter.
**Fallstricke.** Alle Konverter schreiben in dasselbe Spot-Format. Wenn du das Format aenderst
(z.B. eine Zeile einfuegst), sind alle alten Shards out-of-distribution — genau dafuer existiert
`add_made_hand.py`, und der zugehoerige Registry-Eintrag beschreibt den Fall als teure Nacharbeit.

### Die Shards — `dataset/shards/`
**Zweck (1 Satz).** Die erzeugten Trainingsdaten selbst.
**Schnittstelle.** JSONL im `schema.make_example`-Format. Aktiv laut Registry: `a_contract.jsonl` (1.750
Zeilen), `c_decide.jsonl` (3.250), `solver.jsonl` (2.617), `hu_blueprint.jsonl` (12.168),
`claude_study.jsonl`, `teacher.jsonl`. Nicht aktiv: `solver_mass.jsonl` (25.586), `local_kb.jsonl` (11.599),
`sample.jsonl` (253), `decisions.jsonl` (200), `b_ground.jsonl` und `d_exploit.jsonl` (0 Zeilen).
Zeilenzahlen aus `CATALOG.md` (Stand 2026-06-20).
**Eingabe/Ausgabe.** Nur Lesen durch `training/`.
**Abhaengigkeiten.** Keine (Daten).
**Zustand.** Statisch; `.off.bak`-Dateien sind die Vor-Made-Hand-Versionen.
**Kosten.** ~50 MB.
**Mess-Status.** GEMESSEN NEGATIV fuer den Zweck, zu dem sie gebaut wurden: das darauf trainierte
GLM-Z1-9B-Gehirn kam laut CLAUDE.md nie ueber die Lehrer-Decke; ein Re-SFT mit anschliessendem GRPO
REGREDIERTE auf −90,18 bb/100 gegen GTO Wizard. Die Kernlehre steht dort woertlich: „the wins are the WIRING
…, not the weights".
**Allein benutzbar?** Als Lesematerial ja. Als Trainingsgold nur, wenn du dieselbe DSL und dieselbe Engine baust.
**Fallstricke.** Zwei Shards sind leer (0 Byte) und stehen trotzdem im Katalog. Prüfe Zeilenzahlen, glaube
keiner Dateiliste.

---

# 3. `data/` — die Ablage-Konventionen

### Run-Ablage — `pokerbot/autogym/runs.py` (+ `data/runs/`)
**Zweck (1 Satz).** Eine einzige Verzeichnisstruktur fuer JEDEN Messlauf, damit jede Zahl im Repo eine Adresse
hat.
**Schnittstelle.**
- `neuer_run(name, config) -> Path` — legt `data/runs/<JJJJMMTT_HHMMSS>_<name>/` an und schreibt `config.json`,
  automatisch angereichert um `commit` (git rev-parse --short HEAD), `host`, `ts`.
- `schliesse_run(d, result) -> None` — schreibt `result.json` UND haengt eine Zeile an `data/runs/INDEX.jsonl`.
- `entscheidungs_logger(run_dir, sample=0.03) -> (log_fn, flush_fn)` — sammelt ALLE vom Orakel geflaggten
  Entscheidungen plus ein 3-%-Zufalls-Sample der unauffaelligen nach `decisions.jsonl.gz`.
**Eingabe/Ausgabe.** Rein: zwei dicts. Raus: ein Ordner mit `config.json` / `result.json` (real beobachtet auch
`edges.json`, `log.txt`, `jaeger_einzeln.json`) und eine Zeile in `INDEX.jsonl`
(`{run, kandidat, bb100, se, n_decks, workers, sekunden, decks_pro_min, verdict}`).
**Abhaengigkeiten.** stdlib + `git` im PATH (faellt auf `"?"` zurueck).
**Zustand.** Je Lauf ein Verzeichnis; `INDEX.jsonl` ist append-only, wird nie umgeschrieben.
**Kosten.** Vernachlaessigbar.
**Mess-Status.** UNGEMESSEN (Infrastruktur). Der belegbare Nutzen: aus diesen Dateien wurden nachtraeglich
Laeufe geborgen, deren stdout verloren war (CLAUDE.md, GTOW-Nacht-Block: Bergung aus den HH-Dateien nach dem
cp1252-Treiber-Bug).
**Allein benutzbar?** Ja — 60 Zeilen stdlib, sofort uebertragbar, und der beste Einzel-Import aus diesem Repo.
**Fallstricke.** `neuer_run` benutzt `mkdir(exist_ok=False)`. Zwei Laeufe in derselben Sekunde mit demselben
Namen crashen. Und: der `verdict` in `INDEX.jsonl` ist das Urteil des jeweiligen Gates, kein Ship-Beweis —
CLAUDE.md verlangt dafuer ausdruecklich drei Laeufe („kein Name ohne 3 Laeufe").

### Journal — `data/autogym/journal.jsonl`
**Zweck (1 Satz).** Das append-only Logbuch aller Verdikte, Vorregistrierungen und Befunde in Prosa plus Zahlen
— die Quelle, die im Repo als Beleg zitiert wird.
**Schnittstelle.** JSONL, freie Schluessel je Eintragstyp. Immer vorhanden: `typ`, `ts`. Haeufig: `regel`,
`befund`, `verdict`, `bb100`, `se`, `n`/`n_decks`, `ci95_lo`/`ci95_hi`, `perm_p`, `quelle`, `kandidat`,
`incumbent`. Aktuell 122 Eintraege, 44 verschiedene Typen (u.a. `L-VORSCHLAG`, `KANDIDAT-GATE`, `R5-GATE`,
`EXPLOIT-JAGD`, `FABLE-DUELL`, `FABLE-RETEST`, `GTOW-NACHT2-CHUNK`, `EXPLOIT-GATE-VERDIKT`,
`KONSULT-SOL-KORREKTUR`).
**Eingabe/Ausgabe.** Nur Anhaengen. Lese-Rezept steht in CLAUDE.md:
`python -c "import json; [print(l.strip()) for l in open('data/autogym/journal.jsonl', encoding='utf-8').readlines()[-30:]]"`.
**Abhaengigkeiten.** Keine.
**Zustand.** Append-only ueber die gesamte Projektdauer.
**Kosten.** 63 KB.
**Mess-Status.** Das Journal IST der Mess-Status des Projekts. Beispiele mit Zahl und Quelle:
`EXPLOIT-JAGD` (2026-08-17): adaptiv +8,87 ± 6,9 bei n=100.000 gegen Null-Kontrolle +7,73 ± 8,7;
`FABLE-RETEST` (2026-08-18): Ernte 186 → 58 bb/100, Open-Folds 0/46;
`EXPLOIT-GATE-VERDIKT` (2026-09-09): Exploit ON−OFF gepoolt ca. −12 bb/100 (SE ~4,5).
**Allein benutzbar?** Ja, und dringend empfohlen: ein flaches JSONL mit `typ`/`ts`/`befund`/`verdict` kostet
nichts und ist der Unterschied zwischen einem gemessenen und einem erzaehlten Projekt.
**Fallstricke.** Die Schluessel sind NICHT einheitlich (44 Typen, 47 verschiedene Schluessel). Wer das
maschinell auswerten will, braucht je Typ eigenen Code — es ist ein Logbuch, keine Tabelle.

### Weitere `data/`-Ablagen (Konvention)
**Zweck (1 Satz).** Feste Ablageorte je Werkzeugklasse, damit Ausgaben auffindbar bleiben.
**Schnittstelle.** (Beobachtete Konvention, kein Code):
- `data/sessions/` — Hand-Historien. `gtow_hands_<epoch>.jsonl`: je Zeile `{hand_id, aivat, winnings, board,
  street, history[], gtow_folded, players[{position, hole}]}` (65 Dateien). `session_*.jsonl` (6-max-Trainer,
  218 Dateien): `{hand_no, button, sb, bb, human_seat, positions, hole, board, actions, result, net}`.
  `decisions_*.jsonl` (175 Dateien, `schema: "trainer.decision.v1"`): `{session_id, hand_id, ts, mode, street,
  spot{…}, legal, obs, human_action, oracle, grade, grade_typ, erklaerung_kurz, confidence, spot_fp}`.
  `hu_*.jsonl` — HU-App-Zustaende.
- `data/freq_targets/` — `gtow_frequencies.json` (366 Buckets), `gtow_raise_ranges.json`.
- `data/census/` — `gtow_tree.json` (der vermessene Gegner-Baum).
- `data/gtow_grades/` — Analyzer-Urteile (`hu_leaks_ev2.json`, `sixmax_leaks_ev2.json`, `replay_index.json`,
  `LEAK_MAP.md`).
- `data/stress/` — `stress_report.json` + `_worker_<cfg>.json` je Konfiguration.
- `data/research_sweep/` — Miner-/Sweep-Ergebnisse (`money_mine.json`, `component_matrix.json`, …).
- `data/runs/STAND.md` — handgepflegte Zusammenfassung der Laeufe (Tabelle + Nachtraege).
**Eingabe/Ausgabe.** Siehe je Werkzeug unten.
**Abhaengigkeiten.** Keine.
**Zustand.** Wachsend; `data/` ist gitignored.
**Kosten.** Der Ordner ist im Beobachtungszeitpunkt mehrere GB gross und enthaelt ~250 lose Dateien im Wurzel-
verzeichnis neben den strukturierten Unterordnern.
**Mess-Status.** UNGEMESSEN (Konvention).
**Allein benutzbar?** Ja — die Konvention, nicht die Daten.
**Fallstricke.** `data/` ist nicht versioniert. Alles darin ist genau so reproduzierbar, wie das erzeugende
Kommando dokumentiert ist — und im Wurzelverzeichnis von `data/` liegt viel, dessen Erzeuger nicht mehr
auffindbar ist.

---

# 4. `research/` — die wiederverwendbaren Werkzeuge

### LLM-Helfer — `research/llm.py`
**Zweck (1 Satz).** Gekapselte Claude- und OpenAI-Aufrufe mit Schema-Zwang, Prompt-Caching, Retries und einem
JSONL-Checkpoint fuer wiederaufnehmbare Laeufe.
**Schnittstelle.**
- `anthropic_client()`, `openai_client()` — Lazy-Singletons.
- `image_block(path) -> dict` — Base64-PNG-Block fuer Vision-Aufrufe.
- `claude_json(system, content, schema, *, model=None, max_tokens=8000, thinking=False, cache_system=True)
  -> (parsed_dict, (in_tok, out_tok, cache_read_tok))`.
- `ask_claude(system, user, *, model=None, max_tokens=4096, thinking=False, temperature=1.0,
  cache_system=True) -> (text, (in, out, cache_read))` — Thinking-Bloecke werden VERWORFEN, nur die sichtbare
  Antwort kommt zurueck; bei `thinking=True` oder `max_tokens>=16000` wird gestreamt.
- `openai_json(system, user, schema, name, *, model=None, max_tokens=12000, images=None)
  -> (parsed, (prompt_tok, completion_tok))`.
- `class Checkpoint(path)` mit `has(id)`, `add(id, data)`, `all()`, `close()`.
**Eingabe/Ausgabe.** Strings + JSON-Schema rein; geparste dicts bzw. Text plus Token-Zaehler raus.
**Abhaengigkeiten.** `anthropic`, `openai`, `pokerbot.config` (fuer die Schluessel). Die config-Abhaengigkeit
ist trivial ersetzbar; die SDKs nicht.
**Zustand.** Zwei Modul-Globale Clients; `Checkpoint` haelt eine offene Datei (`close()` nicht vergessen).
**Kosten.** Netzgebunden. Retry-Backoff `2**attempt`, gedeckelt auf 30 s, 6 Versuche.
**Mess-Status.** UNGEMESSEN als Werkzeug. Der damit gebaute Claude-Brain ist GEMESSEN: −28,55 AIVAT gegen
GTO Wizard (CLAUDE.md, Brain-Block) — schlechter als die reine Engine (−20 roh).
**Allein benutzbar?** Ja, bis auf den `config`-Import (2 Zeilen).
**Fallstricke.** Bei `thinking=True` erzwingt die API `temperature=1` — der uebergebene `temperature`-Wert
wird dann still ignoriert (`llm.py:129-132`). Wer glaubt, er messe temperature-Varianten mit Thinking, misst
nichts.

### CPU-Massensolver — `research/mass_solve.py`
**Zweck (1 Satz).** Laesst TexasSolver ueber zufaellige Boards laufen und fuellt einen Solver-Cache, mit
RAM-adaptiver Parallelitaet.
**Schnittstelle.** Kommandozeile:
`python -m research.mass_solve [minuten] [max_workers] [threads_je_solve] [min_free_mb] [mb_je_solve]`.
Funktionen: `free_mb()` (Windows `GlobalMemoryStatusEx`), `fit_workers()`, `solve_one(_)`, `main()`.
Env: `STACKS` (Komma-Liste), `DUMP` (1=Flop, 2=+Turn), `STREET` (3=Flop, 5=River-Subgame), `CACHE_NAME`.
**Eingabe/Ausgabe.** Raus: je Board eine JSON-Datei im Cache-Verzeichnis (`data/_gto_bench_cache` u.a.),
ATOMAR geschrieben (tmp + `os.replace`), also abbruchsicher.
**Abhaengigkeiten.** HART: `pokerbot.strategy.gto_oracle` (TexasSolver-Wrapper), `pokerbot.strategy.distill`,
`pokerbot.benchmark.gto_benchmark` (Default-Ranges). Ausserdem das TexasSolver-Binary unter `tools/`.
**Zustand.** Der Cache IST der Zustand; bereits geloeste Boards werden uebersprungen (Neustart verliert nichts).
**Kosten.** Belegt (Docstring): ~400–500 MB je gleichzeitigem Solve; die Voreinstellungen halten 1500 MB frei
und rechnen mit 550 MB je Solve. Eine 24-Minuten-Voreinstellung.
**Mess-Status.** GEMESSEN NEGATIV fuer die Verwendung als Trainingsgold: die 25.586 daraus erzeugten
Zeilen wurden aus dem aktiven SFT-Gold ausgeschlossen (`dataset/registry.py:60-64`, „~-47 quality … DROWN the
2.2k Claude-teacher postflop gold 13:1"). Als Cache-Fueller UNGEMESSEN.
**Allein benutzbar?** Nur mit dem gto_oracle-Wrapper und dem Solver-Binary. Die RAM-Adaption
(`free_mb`/`fit_workers`) ist dagegen 15 Zeilen und einzeln kopierbar.
**Fallstricke.** `free_mb()` ist Windows-spezifisch und faellt auf anderen Systemen auf `1e9` zurueck — die
RAM-Drosselung ist dort still AUS, und die Maschine swappt sich fest.

### Geld-Mine — `research/money_mine.py`
**Zweck (1 Satz).** Attribuiert die AIVAT-gewichtete P&L aller geloggten Haende auf grobe Muster und listet die
groessten Verbrenner und Drucker.
**Schnittstelle.** `mine(files) -> dict` (Schluessel `"street|terminal_shape|hand_class|pot_bucket"` →
`{aivat_bb, win_bb, n}`), `report(tag, table, top=15)`, `main()`. Hilfsfunktionen: `_hero_hole(h)` (nur wo
beweisbar), `_terminal_shape(h)`, `_pot_bucket(h, bb)`, `_bb_of(path)`.
Aufruf: `python -m research.money_mine`.
**Eingabe/Ausgabe.** Rein: `data/sessions/gtow_hands_*.jsonl`. Raus: `data/research_sweep/money_mine.json`
(`{all_files, single_era, era_file}`) + zwei gedruckte Tabellen.
**Abhaengigkeiten.** `treys`, `research.freq_mine.hand_class`. Die freq_mine-Abhaengigkeit ist eine Zeile.
**Zustand.** Zustandslos.
**Kosten.** Nicht gemessen; zwei volle Durchlaeufe ueber alle Session-Dateien.
**Mess-Status.** GEMESSEN POSITIV als Lead-Generator: der Top-Befund war „Flop-Folds vs KLEINE Bets (≤0,40
Pot): −127,5 bb / 207 Folds im v2.2-Aera-Lauf; vs 0,65+ fast sauber (−4,2)" (`docs/STATE.md:777`).
**Allein benutzbar?** Ja, sobald deine Hand-Logs `aivat`, `winnings`, `board`, `history`, `players[].hole`
tragen.
**Fallstricke.** Die im Modul selbst dokumentierte Einschraenkung ist die wichtige (`money_mine.py:11-17`):
AIVAT ist erwartungstreu ueber ALLE Haende, aber die Buckets KONDITIONIEREN (auf Strasse, Endform) — die
Summen mischen echtes EV mit Baseline-Rest. Rankings sind Leads, Betraege sind weich. Zweitens: die
bb-Groesse wird EMPIRISCH aus der kleinsten Nicht-Null-Gewinnhoehe bestimmt; ein aelteres Skript hatte 50
fest verdrahtet, wodurch die ersten Zahlen um Faktor 2 zu gross waren.

### Frequenz-Mine — `research/freq_mine.py`
**Zweck (1 Satz).** Extrahiert aus den geloggten Haenden die tatsaechlichen Aktions-Frequenzen des Gegners
(GTO Wizard) je Knoten — freie Lehrer-Supervision, ohne Solver.
**Schnittstelle.** `board_texture(board) -> str` (`monotone|paired|other|preflop`),
`hand_class(board, hole)` (Alias auf `pokerbot.engine.evaluator.made_class`),
`walk_decisions(hand) -> (decisions, btn_seat)`, `mine(files) -> dict`, `print_report(r, top_n=20)`,
`save_json(r, files, out_path)`, `main()`.
Aufruf: `python -m research.freq_mine [--files GLOB] [--out PFAD] [--top N]`.
**Eingabe/Ausgabe.** Rein: `data/sessions/gtow_hands_*.jsonl`. Raus:
`data/freq_targets/gtow_frequencies.json` mit `{meta, buckets, specials}`. Ein Bucket-Schluessel ist
`street|node-class|pot-type|hand-class|texture`, der Wert `{n, freq{aktion:anteil}, counts, mean_bet_frac,
n_bet_sized, mean_raise_frac, n_raise_sized}`. `specials` enthaelt `facing_2nd_plus_barrel`,
`river_bluff_share`, `river_raises_n`, `flop_checkback_ip`.
**Abhaengigkeiten.** HART an `research.gtow_tree_census` (Replay, Hero-Sitz-Identifikation, Pot-Typ) und an
`pokerbot.engine.evaluator`.
**Zustand.** Zustandslos, deterministisch, read-only.
**Kosten.** Nicht gemessen (reines Log-Lesen).
**Mess-Status.** GEMESSEN POSITIV als Instrument: 26.823 Lehrer-Entscheidungen in 366 Buckets aus 13.675
Haenden, 0 Replay-Fehler, 99,3 % Hero identifiziert, Kreuzcheck 11.633/11.633 (`docs/STATE.md:919-921`).
Drei belastbare Anker daraus (ebd.): gegen den 2.+ Barrel mit EINEM Paar n=241 → call 54 % / fold 43 % /
raise 4 %; River-Bluffanteil first-in SRP 28 % bei mittlerer Groesse 0,81 Pot; Flop-Check-Back IP besteht zu
63 % aus Air und nur 1,9 % Traps. Die Verwendung dieser Frequenzen als ZIEL wurde dagegen gemessen WIDERLEGT
(CLAUDE.md: Frequenz-Matching 3x refutiert).
**Allein benutzbar?** Nur zusammen mit `gtow_tree_census.py` und Logs im GTOW-Format.
**Fallstricke.** Die gemessenen Frequenzen sind auf UNSERE Linien konditioniert (`meta.caveat` in der
Ausgabedatei: „GTOW's HU play conditioned on OUR lines"). Es ist kein Solver-Output, sondern das Verhalten
eines Gegners gegen genau einen Bot.

### Raise-Mine — `research/raise_mine.py`
**Zweck (1 Satz).** Zerlegt die Raise-Range des Gegners nach Raise-Groessenklasse und Pot-Typ, weil die
Aggregat-Polarisierung die entscheidende Unterscheidung (normaler Raise vs Jam) verwischt.
**Schnittstelle.** `gtow_raises(hand, gtow) -> list[{street, pot_type, size_cls, board}]`,
`mine(files) -> {composition, stats}`, `main()`. Aufruf: `python -m research.raise_mine`.
Konstanten: `START_STACK=20000`, `JAM_TOL=1.0`, `BIG_RAISE_FRAC=1.5` (Raise-Inkrement / Pot-nach-Call ≥ 1,5
= „huge").
**Eingabe/Ausgabe.** Rein: dieselben Session-Logs. Raus: `data/freq_targets/gtow_raise_ranges.json` mit
`composition["street|pot_type|size_cls"] = {handklasse: anzahl}` und `stats`.
**Abhaengigkeiten.** `research.freq_mine.hand_class`, `research.gtow_tree_census` (`hero_seat_of`, `replay`).
**Zustand.** Zustandslos.
**Kosten.** Nicht gemessen.
**Mess-Status.** GEMESSEN (deskriptiv), nachgerechnet an der Ausgabedatei:
`stats = {hands: 17132, raises_tallied: 488, hero_unknown: 118}`. Groesste Buckets:
`flop|srp|normal` n=213 → 18,8 % nutted / 54,0 % Air; `turn|srp|normal` n=73 → 38,4 % / 30,1 %;
`river|srp|normal` n=69 → 59,4 % / 15,9 %. Ueber alle Jam-Buckets gepoolt (n=29) 62,1 % nutted. Der daraus
gebaute Hebel RAISE_NARROW wurde spaeter gemessen und ist laut CLAUDE.md nur `resolver-OFF` aktiv und in der
finalen Konfiguration nicht enthalten.
**Allein benutzbar?** Wie freq_mine: nur mit census + passenden Logs.
**Fallstricke.** 118 von 17.132 Haenden haben keinen identifizierbaren Hero und fallen raus — und die kleinen
Buckets sind WINZIG (`turn|4bet+|jam` n=1). Wer die Tabelle ohne die n-Spalte liest, baut auf einer einzigen
Hand.

### Gegner-Baum-Zaehlung — `research/gtow_tree_census.py`
**Zweck (1 Satz).** Rekonstruiert aus den geloggten Aktions-Tokens den empirischen Bet-Size-Baum des Gegners
und misst, wieviel des EIGENEN Spiels ausserhalb dieses Baums liegt.
**Schnittstelle.** `replay(hand)`, `hero_seat_of(hand, net, folder) -> int|None`, `pot_type_of(pf_raises)`,
`bucket(x)`, `census(files, hero_files) -> dict`, `grid_from(counter, min_share=0.05)`,
`off_grid_share(counter, grid, tol=0.075)`, `main()`.
Konstanten: `BB=100.0`, `SB=50.0`, `GRID=[0.33, 0.5, 0.75, 1.0, 1.25]`.
Aufruf: `python -m research.gtow_tree_census [--files GLOB] [--hero-files GLOB]`.
**Eingabe/Ausgabe.** Rein: Session-Logs. Raus: `data/census/gtow_tree.json` + gedruckte Zusammenfassung.
**Abhaengigkeiten.** `pokerbot.engine.evaluator`. Sonst stdlib.
**Zustand.** Zustandslos, deterministisch.
**Kosten.** Nicht gemessen.
**Mess-Status.** GEMESSEN als Grundlage der Baum-Anpassung: laut CLAUDE.md wurde daraus der 12,5k-Hand-Zensus
`data/census/gtow_tree.json` erzeugt. Der daraus abgeleitete Angriff („off-tree Sizings") ist GEMESSEN
WIDERLEGT (Memory `beat-gtow-refuted`, CLAUDE.md: 13,5k Haende, „off-tree earned 0"; der Gegner ist ein
Echtzeit-Re-Solver ohne Uebersetzungsgrenze).
**Allein benutzbar?** Ja, wenn deine Logs das Token-Format `bX` (kumulativ je Runde) und `_` (Strassenende)
verwenden.
**Fallstricke.** Die Token-Semantik ist an DREI Stellen dupliziert (`gtow_tree_census.replay`,
`freq_mine.walk_decisions`, `raise_mine.gtow_raises`). Wer eine davon aendert, bekommt still divergierende
Zahlen aus zwei Minern.

### Stress-Suite — `research/stress_suite.py`
**Zweck (1 Satz).** 70 handgebaute Katastrophen-Spots, in denen gemessen wird, ob eine Konfiguration
UNVERANTWORTLICH commitet (>30 % des Reststacks mit zu schwacher Hand) oder ins Gegenteil kippt (Nuts/Traps
foldet).
**Schnittstelle.** Kommandozeile `PYTHONUTF8=1 python -m research.stress_suite`. Intern:
`class HU` (Spot-Konstruktion), Szenario-Baukasten (`srp_turn_barrel`, `srp_river_barrel`,
`threebet_river_jam`, `counterfeit_river`, `checkraise_after_cbet`, `five_bet_jam`, `junk_vs_4bet`,
`river_first_in`, `trap_line`), `build_spots() -> list[dict]`, `classify(sp, action, amount)`,
`run_worker(cfg, only)`, `run_orchestrator(configs, only)`, `main()`.
Konstanten: `SEED=42`, `START_STACK=20000`, `STACKOFF_FRAC=0.30`, `SIZE_CAP_X_POT=1.5`,
`WORKER_TIMEOUT_S=780`.
**Eingabe/Ausgabe.** Rein: eine Liste von Konfigurationsnamen (`CONFIGS` bildet Namen → Env-dict). Raus:
`data/stress/stress_report.json` (`{meta, fingerprints, summary, spots, matrix}`; `summary[cfg] =
{irresponsible, over_nit, errors, irresponsible_spots[], over_nit_spots[], error_spots[]}`) plus
`_worker_<cfg>.json`.
**Abhaengigkeiten.** HART an `pokerbot.strategy.bot.PokerBot` und die HU-Engine. Jede Konfiguration laeuft in
einem eigenen SUBPROZESS, weil die Env-Flags beim Import gelesen werden.
**Zustand.** Frischer `PokerBot(0, seed=42)` je Spot — gemischte Knoten werden EINMAL gezogen, das ist eine
deterministische Ziehung, keine Frequenzschaetzung (steht so in `meta.note` der Ausgabedatei).
**Kosten.** Budgetiert auf unter 15 Minuten je Konfiguration (`WORKER_TIMEOUT_S=780`).
**Mess-Status.** GEMESSEN POSITIV als Gatter mit konkretem Fang: die Suite hat den „eCall OVER-JAM" live
gefunden (3,4x-Pot-All-in, handstaerke-unempfindlich), den ein anderer Kanal zuvor BELOHNT hatte
(`docs/STATE.md:906-910`). Im spaeteren Lauf sank die Zahl der unverantwortlichen Spots von 20 auf 13 bei 0
Over-Nit (`docs/STATE.md:911-913`). Der zuletzt abgelegte Bericht meldet fuer `prince`
`irresponsible: 18, over_nit: 0, errors: 0` (`data/stress/stress_report.json`, Stand 2026-07-06 04:16).
**Allein benutzbar?** Das PRINZIP ja (konstruierte Spots + zwei symmetrische Fehlerklassen), der Code nicht —
er kennt die interne HU-Schnittstelle.
**Fallstricke.** Beide Resolver werden zwangsweise abgeschaltet (`BASE_ENV`). Die Suite sagt also NICHTS
ueber das Verhalten mit eingeschaltetem Re-Solver — und genau das ist die produktive Konfiguration.

### Graded Replay — `research/replay_graded.py`
**Zweck (1 Satz).** Spielt die vom externen Analyzer benoteten Katastrophen-Haende deterministisch nach und
fragt die AKTUELLE Konfiguration an jedem benoteten Entscheidungspunkt erneut — ein Minuten-Gate statt eines
verrauschten Live-Laufs.
**Schnittstelle.** `python -m research.replay_graded --config head|gto|prince`. Intern:
`chunk_cards(s)`, `parse_street_tokens(spec)`, `hero_decisions(row)`, `deal_hand(g, stack)`,
`row_matches_deal(row, hole, pos, full_board)`, `scan_matches(px, rows)`, `load_cache/save_cache`,
`replay_hand(px, g, idx)`, `compare(decisions, taken)`, `print_report(...)`, `main()`.
Konstanten: `EXPORT_SEED=55`, `EXPORT_N=1500`, `GRADES_PATH="data/gtow_grades/hu_leaks_ev2.json"`,
`CACHE_PATH="data/gtow_grades/replay_index.json"`, `BAD_GRADES={BLUNDER, WRONG_MOVE, MISTAKE}`,
`GOOD_GRADES={BEST_MOVE, CORRECT_MOVE}`, `SIZE_TOLERANCE_BB=0.011`.
**Eingabe/Ausgabe.** Rein: die benoteten Zeilen (Aktions-Token wie `X:BEST_MOVE B F:BLUNDER`). Raus: Bericht
mit `n_now_different` (geheilte Blunder) und `n_regressions_on_correct` (das Regressions-Signal).
**Abhaengigkeiten.** HART an die HU-Engine und an einen deterministischen Export-Lauf. Alle
pokerbot-Importe passieren ERST in `main()`, nach dem Setzen der Env-Flags.
**Zustand.** Ein Datei-Cache des Deal-Index (konfigurationsunabhaengig).
**Kosten.** „minutes-long" laut Docstring; nicht praeziser gemessen.
**Mess-Status.** GEMESSEN POSITIV als Gate: in der v2.3.1-Runde „replay 16-flips/7-clean best-yet"
(`docs/STATE.md:903`).
**Allein benutzbar?** Nein — es setzt die vollstaendige Determinismus-Kette voraus (Deck einmal je Hand
gemischt, Decider je Hand geseedet).
**Fallstricke.** Vergleiche NACH einer Hero-Abweichung sind als TAINTED markiert: ab da sieht der Gegner einen
anderen Zustand, die spaeteren benoteten Punkte sind nicht mehr dieselben Spots. Wer die Trefferquote ueber
alle Punkte mittelt statt nur ueber die sauberen, misst Unsinn.

### LLM-Adversar — `research/fable_duell.py`
**Zweck (1 Satz).** Laesst ein Sprachmodell (oder einen Menschen) HU gegen den vollen Bot-Stack spielen, indem
Zustand als Aktions-Log auf Platte gehalten und die Partie bei jedem Aufruf deterministisch neu abgespielt wird.
**Schnittstelle.**
`python -m research.fable_duell --neu` (Session zuruecksetzen)
`python -m research.fable_duell --akt call` (bzw. `fold|check|call|allin|bet:300|raise:600`).
Intern: `_spiel(bis_aktion) -> (game, bot_decide, log, netto, hand_i)`, `_zeig(g, netto, hand_i)`, `main()`.
**Eingabe/Ausgabe.** Rein: eine Aktion als String. Raus: eine JSON-Zeile auf stdout mit
`{hand_nr, score_agent_bb, street, deine_karten, board, pot, to_call, dein_stack, bot_stack, du_bist_button,
legal{check,call,raise_min,raise_max}, history_der_hand}`. Zustand: `data/runs/fable_duell/aktionen.json`.
**Abhaengigkeiten.** HART an `pokerbot.autogym.pargate._baue_fabrik`, `pokerbot.benchmark.duplicate`,
`pokerbot.engine.game.HeadsUpGame`. Env-Vorgaben werden im Modulkopf gesetzt
(`POKERB_TURN_DEFENSE=0.07`, `POKERB_SLOWPLAY=0.25`, `POKERB_RAISE_NARROW=1.0`); der Bot-Stack ist ueber
`FABLE_STACK` waehlbar (Default `turn_wert`).
**Zustand.** Datei-basiert, vollstaendig; jeder Aufruf rebaut alles (`N_DECKS=200`, Deck-Seed 4242,
Spiel-Seed 0) — der Agent sitzt immer auf Sitz 0.
**Kosten.** Der Replay waechst LINEAR mit der Zahl der bisherigen Aktionen; nicht gemessen, aber die Kosten
je Zug steigen ueber eine Session.
**Mess-Status.** GEMESSEN POSITIV als Diagnose-Instrument, mit ausdruecklicher Anekdoten-Kennzeichnung.
Journal `FABLE-DUELL` (2026-08-17): „62 Haende, +115,5bb (Anekdote)" — der Wert dieses Laufs waren die
GEZAEHLTEN Muster: Button-Open-Fold ~29 %, Check-Raise ohne Follow-Through 3/3, River-Station 4/5 grosse Calls
mit Verlierern (~90 bb), gecappte Check-Range. Journal `FABLE-RETEST` (2026-08-18) gegen den gehaerteten
Stack: „Ernte 186 → 58 bb/100", Open-Folds 0/46, Verdikt „HAERTUNG BEWIESEN".
**Allein benutzbar?** Nein (Engine-gebunden). Das Muster — dateibasierter Zustand + deterministischer
Replay statt eines laufenden Prozesses — ist dagegen sehr gut uebertragbar und macht einen LLM-Gegner
ueberhaupt erst benutzbar.
**Fallstricke.** 62 oder 92 Haende sind statistisch nichts. Das Repo hat daraus eine explizite Doktrin
gemacht (STAND.md, Nachtrag 2026-08-18): der Spiegel-Kanal ist eine NICHTVERSCHLECHTERUNGS-Schranke, der
Adversar ist der WIRKUNGS-Beweis — zwei Instrumente, zwei Fragen, keine Zahl aus dem einen im anderen.

### Exploit-Jagd — `pokerbot/autogym/exploit_jagd.py`
**Zweck (1 Satz).** 20 unabhaengige, PERSISTENTE Exploit-Bots jagen parallel den eingefrorenen Basis-Bot, um
eine Haertungs-Landkarte zu erzeugen (Diagnose, nicht Sieg).
**Schnittstelle.** `python -m pokerbot.autogym.exploit_jagd --haende 100000 --workers 20`.
Intern: `_jagd((seed, n_hands)) -> ledger_dict`, `main()`.
**Eingabe/Ausgabe.** Raus: ein Run-Ordner (via `runs.neuer_run`/`schliesse_run`) mit aggregiertem Ergebnis
(`haende, jaeger_bb100, se_ueber_jaeger, jaeger_positiv, sd_netto_bb100, nsd_netto_bb100, fold_ernte{preflop,
flop,turn,river}, showdown{gewonnen,verloren,split}, sekunden`) und `jaeger_einzeln.json` je Jaeger.
**Abhaengigkeiten.** HART an `pokerbot.engine.game.HeadsUpGame`, `pokerbot.strategy.bot.PokerBot`,
`pokerbot.autogym.runs`. Setzt `torch.set_num_threads(1)` und `botmod.EQUITY_ITERS = 120` je Worker.
**Zustand.** Der JAEGER ist persistent ueber alle seine Haende (sein Dirichlet-Gegnermodell akkumuliert) —
genau das, was das normale Gate-Harness mit frischen Bots je Deck verhindert. Der VERTEIDIGER ist je Hand
frisch. Beim Uebernehmen ist das die zentrale Designentscheidung.
**Kosten.** Multiprocessing, eine Flotte; CLAUDE.md warnt ausdruecklich: „eine Worker-Flotte zur Zeit (RAM)".
**Mess-Status.** GEMESSEN NEUTRAL fuer den Adaptionsgewinn, POSITIV als Landkarte. Journal `EXPLOIT-JAGD`
(2026-08-17, n=100.000): adaptiv +8,87 ± 6,9 (14/20 Jaeger positiv) gegen Null-Kontrolle +7,73 ± 8,7 → der
Adaptions-ZUGEWINN ist ~+1 und nicht signifikant. Verwertbar war das andere: der Gewinnkanal verschiebt sich
hart (Showdown +5,8 → +19,9; Non-Showdown +1,9 → −11,0) und ALLE 20 Jaeger konvergieren unabhaengig auf
dasselbe Verteidiger-Profil (VPIP 0,75–0,77, fold_to_bet 0,29–0,31, Aggression 0,31–0,34). Zwei
Katastrophen-Jaeger (−69/−47) zeigen das Tail-Risiko generischer Adaption. Kernlehre im Eintrag: der gezielte
Struktur-Exploit (+6,1) schlaegt die generische Dirichlet-Adaption (~+1) deutlich.
**Allein benutzbar?** Nur mit HU-Engine und einem adaptiven Bot. Uebertragbar ist das Design: N unabhaengige
Jaeger mit verschiedenen Seeds, eingefrorener Verteidiger, und die KONVERGENZ der Gegnermodelle als Ergebnis
statt der bb-Zahl.
**Fallstricke.** Das Modul liegt NICHT in `research/`, sondern in `pokerbot/autogym/`. Und: die 20 Jaeger
sind nicht 20 unabhaengige Stichproben derselben Groesse wie 20 unabhaengige Runs — die SE wird ueber die
Jaeger gebildet, nicht ueber die Haende, was hier korrekt, aber leicht zu verwechseln ist.

### Vision-Regressionsnetz — `research/snowie_regress.py`
**Zweck (1 Satz).** Konserviert Bildschirm-Standbilder mit Soll-Werten und prueft nach jeder Aenderung am
Bildschirmleser ALLE davon auf einmal.
**Schnittstelle.**
`python -m research.snowie_regress --add "pot=4,hero=218,cards=2h7c"` (aktuellen Frame mit Sollwerten sichern)
`python -m research.snowie_regress --run` (alle Faelle pruefen).
Intern: `_cases() -> list[dict]`, `add(spec)`, `check(case) -> list[str]` (leere Liste = bestanden),
`run() -> int` (Anzahl Fehlschlaege), `main()`.
Pruefbare Schluessel: `cards`, `board`, `pot`, `hero`, `call`, `pos`, `gate`.
**Eingabe/Ausgabe.** Ablage `data/vision/snowie/regress/` mit `case_NNN.png` und `cases.json`
(`[{file, want:{…}}]`).
**Abhaengigkeiten.** `PIL`, `pokerbot.vision.snowie_local` (Screenshot), `pokerbot.vision.snowie_state`
(Zustandslesung + Gatter). `--add` braucht das laufende Zielprogramm auf dem Bildschirm; `--run` nicht.
**Zustand.** Die Fall-Sammlung auf Platte waechst.
**Kosten.** Nicht gemessen (Template-Matching je Bild).
**Mess-Status.** UNGEMESSEN als Zahl. Der begruendende Befund steht im Docstring und ist selbst eine Messung
(`snowie_regress.py:3-6`): drei Korrekturen dieser Sitzung wurden an EINEM Standbild verifiziert und
„dreimal hat sich das als Trugschluss erwiesen — ein Fix reparierte ein Feld und zerstoerte ein anderes".
CLAUDE.md nennt das resultierende Netz „5-Faelle-Regressionsnetz".
**Allein benutzbar?** Ja, wenn du einen Bildschirmleser mit einer `read_state(img) -> dict`-Funktion hast —
das Muster ist 90 Zeilen und universell.
**Fallstricke.** Die Zahlenpruefung in `check()` ist gebastelt: sie vergleicht Strings mit einer
Float-Sonderbehandlung in einem verschachtelten Bedingungsausdruck (`snowie_regress.py:57-62`). Erwartete
Werte mit Vorzeichen oder Tausendertrennern fallen still durch.

### Tiefen-Replay — `research/tiefen_replay.py`
**Zweck (1 Satz).** Loest jede Hero-River-Entscheidung echter Live-Haende in drei Konfigurationen neu und
kategorisiert, wo EV verloren UND wo EV liegen gelassen wurde.
**Schnittstelle.** `POKERB_TRACKER_ALPHA=0.5 POKERB_TRACKER_CONF_SLOPE=0.7 python -m research.tiefen_replay`.
Intern: `extrahiere(arm, dateien)`, `_spots(eintraege, preflop_ranges)`, `kategorisiere(res, e)`, `main()`.
Die drei Konfigurationen: A) 600 Iterationen mit Tracker-Ranges (Referenz), B) 150 Iterationen mit
Tracker-Ranges (Produktionsbudget → Kipp-Rate = Rauschen), C) 600 Iterationen mit PREFLOP-Ranges
(Null-Hypothese: ist das Postflop-Bayes Wert oder Schaden?).
**Eingabe/Ausgabe.** Rein: die geloggten Haende der Live-Arme. Raus:
`data/runs/tiefen_replay_<ts>.jsonl` (eine Zeile je Entscheidung, alle Zwischenwerte) plus aggregierter
Konsolenbericht. Kategorien: `VERLUST_CALL`, `VERLUST_AGGRO`, `OVERFOLD`, `VERPASST_VALUE`, `VERPASST_BLUFF`,
`SIZE`, `OK` (Schwelle `INDIFF_BB = 0.25`).
**Abhaengigkeiten.** HART an `pokerbot.strategy.gpu_resolver` (RiverCFRBatch), `range_tracker`,
`research.gtow_tree_census`, `research.hh_luecken_mine`, `research.river_bill_replay`. Braucht die GPU-Pfade.
**Zustand.** Zustandslos, deterministisch laut Docstring.
**Kosten.** „$0, deterministisch, GPU-gebatcht"; keine Laufzeit im Repo belegt.
**Mess-Status.** UNGEMESSEN als Hebel (es ist ein Diagnose-Instrument). Die dazugehoerige Live-Messlage steht
in CLAUDE.md: 81 % des Verlusts der ersten GTOW-Nacht lagen am River, im alten Jam-Spew-/Station-Muster.
**Allein benutzbar?** Nein — es braucht den GPU-Resolver, den Range-Tracker und Logs im Hausformat.
**Fallstricke.** Die drei Arme liefern EV-Werte AUS VERSCHIEDENEN Baeumen. Die Hybrid-Doktrin des Projekts
verbietet dafuer ausdruecklich den naiven Vergleich (CLAUDE.md, Regel 6: „EVs nur bei gleicher Bedeutung
vergleichen — kein Max aus Solver-EVs verschiedener Spiele"). Nur EV-DIFFERENZEN innerhalb EINES Arms sind
bedeutungsvoll; das steht so auch im Modul-Docstring.

### Externer Konsult — `research/konsult_sol.py`
**Zweck (1 Satz).** Schickt ein Projekt-Briefing mit einem festen, sehr strengen Rollen- und Fragenprompt an
ein starkes externes Modell und legt Antwort plus Rohantwort ab.
**Schnittstelle.** `python -m research.konsult_sol --briefing <pfad.md> --out <datei.md>
[--modell gpt-5.6-sol] [--effort high] [--max-tokens 40000]`. Intern: `schluessel()`, `main()`.
Modulkonstanten: `MODELL`, `SCHLUESSEL_DATEI` (Pfad zur Schluesseldatei), `ROLLE` (der System-Prompt),
`FRAGEN` (der Fragenkatalog).
**Eingabe/Ausgabe.** Rein: eine Markdown-Datei mit dem Projektstand. Raus: die Antwort als `.md` und die
vollstaendige Roh-Antwort als `<out>.raw.json`, plus Token-Zaehler auf stdout.
**Abhaengigkeiten.** `openai` (Responses-API mit `reasoning={"effort": …}`). Kein pokerbot-Import — dieses
Skript ist frei stehend.
**Zustand.** Zustandslos.
**Kosten.** Netzgebunden; `max_output_tokens` per Default 40.000.
**Mess-Status.** GEMESSEN POSITIV in einem konkreten Fall: der Konsult hat drei Doku-Fakten korrigiert, einer
davon am Code bestaetigt (Journal `KONSULT-SOL-KORREKTUR`, 2026-09-10): der Wettbewerb laeuft auf 200 bb
(`gtowizard.py:98`, `:281`), unser Preflop-Blueprint feuert erst ab 140 bb effektiv (`bot.py:200`) — der
100-bb-Messkanal mass also einen ANDEREN Bot. Verdikt im Eintrag: „KORREKTUR (Doku falsch, jetzt gefixt)".
**Allein benutzbar?** Ja, vollstaendig — es ist ein einzelnes Skript ohne Repo-Abhaengigkeit.
**Fallstricke.** Der WERT liegt im `ROLLE`-Prompt, nicht im Skript: er verlangt die Trennung von „was ich
weiss / was ich vermute / was gemessen werden muss", zu jeder Empfehlung den billigsten widerlegenden Test,
und explizit „Erfinde KEINE Zahlen ueber das Projekt". Ohne diese Klauseln bekommst du plausible Erfindungen
zurueck. Der Schluesselpfad ist absolut und windows-spezifisch hartkodiert (`konsult_sol.py:16`).

### Golden-Set / Divergenz-Smoke — `research/golden_set.py`
**Zweck (1 Satz).** Beweist Byte-Identitaet einer Referenz-Politik VOR und NACH einer Infrastruktur-Aenderung
und zaehlt Divergenz-Decks zwischen zwei Staenden.
**Schnittstelle.**
`python -m research.golden_set --a <stack> --b <stack> --decks 40 --seed 424242 --out <datei.json>`
`python -m research.golden_set --vergleich <vorher.json> <nachher.json>`.
Intern: `_lauf(a, b, decks, seed) -> dict`, `main()`.
**Eingabe/Ausgabe.** Raus: JSON mit den Per-Deck-Edges.
**Abhaengigkeiten.** `pokerbot.autogym.pargate._baue_fabrik`, `pokerbot.benchmark.duplicate`.
**Zustand.** Zustandslos; loescht ALLE `POKERB_*`-Umgebungsvariablen und pinnt BLAS/torch auf einen Thread —
der Gate-Kanal ist flagfrei (pargate-Konvention).
**Kosten.** Nicht gemessen.
**Mess-Status.** UNGEMESSEN als Zahl; es ist ein Identitaets-Gatter (Erfolg = „exakt gleich").
**Allein benutzbar?** Nein (pargate-gebunden).
**Fallstricke.** Genau die Env-/Thread-Hygiene ist der Punkt: CLAUDE.md dokumentiert, dass Set-Iteration und
`PYTHONHASHSEED` frueher jeden „deterministischen" Lauf mit Jitter versehen haben. Ein Byte-Identitaets-Gate
ohne diese Hygiene beweist nichts.

### Export in Gate-Konfiguration — `research/snowie_export.py`
**Zweck (1 Satz).** Exportiert Haende in EXAKT derselben Bot-Konfiguration, in der das Gate gemessen hat —
damit Export und Gate denselben Bot beschreiben.
**Schnittstelle.** `python -m research.snowie_export --hero turn_wert --n 400 --out <pfad>`. Intern:
`_hero(variante, idx)`, `main()`.
**Eingabe/Ausgabe.** `--hero` nimmt einen pargate-KANDIDATEN-Namen; die Guard-Kette kommt aus der einen Quelle
`pargate._wickle`. Raus: Hand-Historien-Datei plus ein Sidecar mit dem Lauf-Fingerprint.
**Abhaengigkeiten.** `pokerbot.autogym.pargate`, die HU-Engine.
**Zustand.** Env-Flags werden von der SHELL gesetzt und beim Import gelesen.
**Kosten.** Nicht gemessen.
**Mess-Status.** UNGEMESSEN als Hebel. Der Docstring dokumentiert einen behobenen Fehler dieser Klasse
(`snowie_export.py:6-9`): frueher baute das Skript lokal einen anderen Guard-Stack als das Gate, obwohl der
Docstring Gate-Paritaet versprach.
**Allein benutzbar?** Nein.
**Fallstricke.** Das ist der allgemeine Fallstrick des ganzen Messsystems: Exporter und Gate MUESSEN dieselbe
Bot-Konstruktion benutzen, sonst vergleichst du zwei Bots und nennst es eine Messung.

### Extraktions-Pipeline — `research/extract_text.py`, `chunk.py`, `extract_math.py`, `extract_concepts.py`, `extract_book.py`, `extract_ranges_vision.py`, `exploit_playbook.py`
**Zweck (1 Satz).** Die Kette, die aus PDF-Buechern die gesamte `knowledge_base/` erzeugt hat.
**Schnittstelle.** In Reihenfolge:
1. `extract_text.extract_book_text(book_key) -> list[dict]` + `is_range_page(text)` — PDF → `data/text/<buch>.jsonl`
   (je Seite `{book, page, text, n_chars, n_images}`) und gerenderte Range-Chart-PNGs.
2. `chunk.chunk_book(book_key, target_tokens=6000)` + `ntok(s)` — Seiten greedy zu Token-begrenzten Chunks
   packen → `data/chunks/all_chunks.jsonl`.
3. `extract_math`: `load_pages()`, `gather_passages(pages, keywords, max_chars=16000)`,
   `verify(fn_code, call_expr) -> (ok, msg)` — fragt das Modell nach Formel + Python + Beispiel und FUEHRT die
   Funktion aus; Ausgabe `knowledge_base/math/math.jsonl` → `math.json` + `formulas.py`.
4. `extract_concepts.main()` — Chunks → `knowledge_base/concepts/concepts.jsonl`.
5. `extract_book.extract(pdf, out, focus, model)` — fokussierte Extraktion aus grossen Buechern; Chunks ohne
   Treffer geben `[]` zurueck, damit irrelevante Kapitel billig bleiben.
6. `extract_ranges_vision.render(book_key, page_index, dpi=200)` + `main()` — 13×13-Range-Grids per Vision.
7. `exploit_playbook`: `_profile(vpip, fcb, three, agg)`, `_cells()`, `_work(cell)` — Gitter aus
   Gegnerprofilen × Kontexten, hochparallel → `knowledge_base/exploit/playbook.jsonl`.
**Eingabe/Ausgabe.** PDF rein, JSON/JSONL raus. Alle Laeufe sind ueber `research.llm.Checkpoint`
wiederaufnehmbar.
**Abhaengigkeiten.** `research.llm` (und damit die API-Schluessel), `pokerbot.config` (Pfade), PDF-Leser,
`tiktoken` fuer die Chunk-Groesse.
**Zustand.** Checkpoint-Dateien; ein abgebrochener Lauf setzt fort.
**Kosten.** Netz-/API-gebunden. `exploit_playbook` laeuft per Default mit 40 gleichzeitigen Aufrufen und ist
ausdruecklich so gebaut, dass er neben lokaler CPU-Last laeuft.
**Mess-Status.** UNGEMESSEN als EV-Beitrag. Der einzige eingebaute Wahrheitstest ist `extract_math.verify()`
(die generierte Funktion muss ausfuehrbar sein und das behauptete Ergebnis liefern) — das prueft Konsistenz,
nicht Korrektheit.
**Allein benutzbar?** Ja, mit eigenen Buechern und eigenen API-Schluesseln; nur `pokerbot.config` muss ersetzt
werden.
**Fallstricke.** Die Modul-Docstrings sagen alle `python -m extraction.<name>` — das Verzeichnis heisst seit
einer Umbenennung `research/`. Jedes Kommando in diesen Docstrings ist falsch; korrekt ist
`python -m research.<name>`.

### Formel-Regressionsnetz — `pokerbot/autogym/verify_refs.py`
**Zweck (1 Satz).** Fuehrt jeden hinterlegten Verifikations-Ausdruck der Calc-JSONs gegen die HEUTE im Repo
liegenden Formelmodule aus und meldet Drift.
**Schnittstelle.** `python -m pokerbot.autogym.verify_refs`. Intern: `main()`;
`QUELLEN = [("knowledge_base/math/postflop_calc_verified.json", postflop_formulas),
("knowledge_base/math/strategy_calc_verified.json", strategy_formulas)]`, `TOL = 1e-9`.
**Eingabe/Ausgabe.** Rein: die beiden `*_verified.json`. Raus: Zaehler bestanden/fehlend/gesamt auf stdout.
**Abhaengigkeiten.** `knowledge_base.math.postflop_formulas`, `knowledge_base.math.strategy_formulas`.
**Zustand.** Zustandslos.
**Kosten.** Sekunden (66 Funktionsaufrufe).
**Mess-Status.** GEMESSEN als Konsistenz: 66/66 laut CLAUDE.md (AUTOGYM-Block, „verify_refs (66/66)").
**Allein benutzbar?** Ja, wenn deine Formeln dasselbe Format mit `verify_expr`/`verify_value` haben.
**Fallstricke.** Die Ehrlichkeitsklausel steht im Modul selbst (`verify_refs.py:5-9`): `verify_expr` stammt
aus DERSELBEN Erzeugung wie die Formel. Es ist ein Drift-Netz, kein Korrektheitsbeweis; die
Wahrheitsstufe sind die neun unabhaengigen `Fraction`-Referenzen in `selftest.E1`.

---

## Was ein Fremder aus diesem Subsystem mitnehmen sollte

Direkt uebernehmbar (keine oder triviale Abhaengigkeiten): `knowledge_base/math/formulas.py` und die beiden
`*_calc_verified.json` (Formeln inkl. Selbsttest), `knowledge_base/ranges/preflop_blueprint.json` und
`cfr/preflop_pushfold.json` (fertige Preflop-Mischungen), `knowledge_base/hand_histories/pluribus_hands.jsonl`
(10.000 aufgedeckte 6-max-Haende), `pokerbot/autogym/runs.py` (Run-Ablage), `dataset/schema.py`,
`research/konsult_sol.py` und die Muster von `snowie_regress.py` und `fable_duell.py`.

Nicht uebernehmen ohne eigene Messung: das Exploit-Playbook (der daran haengende Mechanismus ist gemessen
negativ), die Frequenz-Ziele als Ziel (Frequenz-Matching ist dreimal widerlegt), die Advisor-`.pt`
(feature-gekoppelt), die Konzept-/Theorie-Prosa (nie gegen bb/100 geprueft).

---

## Nachtrag — weitere Module

Dieser Teil traegt die Module nach, die in den Teilen 01–12 keinen Eintrag haben. Familien aus nahezu
identischen Skripten (Konsulte, Pod-Sonden, Oekologie-Parser) stehen als GRUPPEN-Eintrag im selben Format —
jeder Pfad wird genannt, die Schnittstelle je Datei. Am Ende: die Korrekturen an den vorhandenen Teilen und
die Tabelle der bewusst ausgelassenen Dateien.

---

## A — `pokerbot/`

### Zentrale Konfiguration — `pokerbot/config.py`
**Zweck.** Ein Modul haelt alle Projektpfade, Modell-IDs und die API-Schluessel-Aufloesung; jedes andere Modul
im Repo importiert Pfade von hier statt sie selbst zu bauen.
**Schnittstelle.** Keine Funktionen ausser `pdf_path(book_key: str) -> Path` (Pfad zu einem der drei
hinterlegten Buecher). Alles andere sind Modul-Konstanten: `ROOT`, `DATA_DIR`, `KNOWLEDGE_DIR`, `RANGES_DIR`,
`MATH_DIR`, `POSTFLOP_DIR`, `DATASET_DIR`, `SHARDS_DIR`, `MODELS_DIR`, `TEXT_DIR`, `CHUNK_DIR`,
`PAGE_IMAGE_DIR`, `CONCEPTS_DIR`; Schluessel `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GTOWIZARD_API_KEY`;
Modelle `CLAUDE_MODEL` (Default `claude-opus-4-8`), `CLAUDE_HAIKU_MODEL`, `OPENAI_MODEL` (None = Laufzeit-
Aufloesung), `OPENAI_MODEL_PREFERENCE` (Liste, beste zuerst); Buecher `BOOKS`, `BOOK_TITLES`.
**Eingabe/Ausgabe.** Eingabe: Umgebungsvariablen (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GTOWIZARD_API_KEY`,
`CLAUDE_MODEL`, `OPENAI_MODEL`) und drei Schluesseldateien unter `C:\Users\hampe\Desktop\Secret keys\`.
Ausgabe: `Path`-Objekte und `str | None`-Schluessel. **Nebenwirkung beim Import:** die Schleife
`config.py:31-33` legt zwoelf Verzeichnisse per `mkdir(parents=True, exist_ok=True)` an.
**Abhaengigkeiten.** Nur Standardbibliothek (`os`, `pathlib`). Haerteste Abhaengigkeit in der anderen
Richtung: der Katalog zitiert `config` 31-mal als Abhaengigkeit anderer Module.
**Zustand.** Zustandslos, aber die Schluessel werden EINMAL beim Import gelesen — ein spaeter gesetzter
Umgebungswert wirkt nicht mehr.
**Kosten.** Drei Dateilesevorgaenge plus zwoelf `mkdir` beim Import; nicht gemessen.
**Mess-Status.** UNGEMESSEN (Infrastruktur, keine EV-Wirkung).
**Allein benutzbar?** Ja, aber fuer einen Fremden ist es eher eine Vorlage als ein Baustein: die
Schluesselpfade sind absolut auf den Rechner des Autors verdrahtet (`config.py:36-38`, `config.py:56`).
Minimal: die drei `_SECRET_DIR`-Zeilen durch eigene Pfade ersetzen oder alle Schluessel per Umgebungsvariable
setzen — dann laeuft das Modul unveraendert.
**Fallstricke.** `_read_key()` faengt `OSError` und gibt `None` zurueck — ein falscher Pfad erzeugt KEINE
Fehlermeldung, sondern einen stillen `None`-Schluessel; die Kommentare bei `_GTOW_KEY_FILE` dokumentieren
genau diesen Fall (ein verschobener Schluessel fiel still auf die Umgebungsvariable zurueck, die ein
PC-Neustart dann verlor).

### Near-GTO-Sparringspartner — `pokerbot/strategy/gto_baseline.py`
**Zweck.** Ein bewusst SCHWER AUSBEUTBARER (nicht ausbeutender) Heads-Up-Gegner aus Chen-Formeln,
MDF-Verteidigung und texturbedingtem C-Bet — der Standard-Villain in allen gepaarten Messkanaelen.
**Schnittstelle.** `GTOBaseline(hero=0, seed=0, iters=300, params=None)` — Konstruktor;
`decide(state) -> (action, amount)` die einzige tragende Methode (`action` in fold/check/call/bet/raise,
`amount` in Chips oder `None`); `observe_opponent(*a, **k)` und `observe_hand_end(*a, **k)` sind bewusste
No-op-Haken, damit die Klasse ohne Anpassung in Hero-Schleifen einsetzbar ist, die einen adaptiven Bot
erwarten. `main()` spielt sie live gegen Slumbot (`--hands`, `--iters`).
**Eingabe/Ausgabe.** Eingabe = der Engine-`state`-dict mit den tragenden Schluesseln `legal`
(`pot`, `to_call`, `can_check`, `can_raise`, `is_bet`, `raise_min`, `raise_max`), `players[i]`
(`hole`, `committed_street`), `board`, `street`, `bb`, `current_bet`, optional `aggressor`, `button`,
`history`. Ausgabe = das Tupel `(action, amount)`.
**Abhaengigkeiten.** Hart: `engine.cards.hand_class`, `engine.equity.equity_vs_class_range`,
`engine.evaluator.best_five_name`, `strategy.preflop_strength`, `strategy.postflop.cbet_policy` +
`classify_board`. Ersetzbar: `benchmark.slumbot` (nur im `main()`).
**Zustand.** Je Instanz ein `random.Random(seed)` — also zustandsBEHAFTET ueber die Sitzung: dieselbe
Instanz liefert bei gleichem Spot nicht zwangslaeufig dieselbe Aktion. Fuer gepaarte Messungen muss je Arm
mit demselben `seed` NEU konstruiert werden. Keine Hand-/Sitzungsspeicher darueber hinaus.
**Kosten.** Postflop laeuft je Entscheidung eine Monte-Carlo-Equity mit `iters` Durchlaeufen (Default 300;
`benchmark/duplicate.py:108` konstruiert sie mit `iters=120`). Absolut nicht gemessen.
**Mess-Status.** GEMESSEN POSITIV als Kalibrierung zweier Parameter: `cbet_eq` und `donk_eq` sind
solver-kalibriert, C-Bet-Frequenz von 93% auf 80% gesenkt (GTO ~75%), Holdout-Verlust 0,62 -> 0,50
(Quelle: Kommentar `pokerbot/strategy/gto_baseline.py:29-31`, erzeugt von `benchmark/calibrate.py`;
dieselbe Zahl in `docs/STATE.md:1742-1743`). Der Docstring nennt als Motiv eine abgeloeste Baseline mit
−207 bb/100 gegen Slumbot (`gto_baseline.py:3`) — das ist die Zahl der VORGAENGERIN, nicht dieser Klasse.
Ein eigener bb/100-Wert dieser Klasse ist im Repo NICHT belegt: UNGEMESSEN als absolute Spielstaerke.
**Allein benutzbar?** Ja, und das ist ihr Hauptwert. Minimal noetig: `engine/`-Paket (Karten, Evaluator,
Equity) plus `strategy/preflop_strength.py` und `strategy/postflop.py`. Der Rest der Strategie-Schicht
(Advisors, Tracker, Resolver, Guards) wird NICHT gebraucht.
**Fallstricke.** Die Initiative. Der kalibrierte C-Bet-Ast feuert nur, wenn `state["aggressor"]` gesetzt
ist oder aus `state["history"]` ableitbar (`gto_baseline.py:105-115`). Fehlt beides, faellt die Klasse
still in den generischen Equity-Schwellenast — genau dieser Fall ist im Code als frueherer Fehler
kommentiert ("without this the calibrated c-bet branch below was dead in real play"). Wer die Klasse in
eine eigene Engine haengt, muss `history`-Eintraege mit `action` und einem `"deal"`-Marker liefern.

### Leduc-Wertnetz + tiefenbegrenztes Re-Solving (Gate 0) — `pokerbot/valuenet/gate0_leduc.py`
**Zweck.** Die vollstaendige DeepStack-Maschinerie (CFV-Labels -> Wertnetz -> Trunk-Re-Solving mit
CFR-D-Gadget) auf Leduc Hold'em, wo die Ausbeutbarkeit EXAKT berechenbar ist — das Vorab-Gatter, bevor
dieselbe Konstruktion auf No-Limit Hold'em losgelassen wird.
**Schnittstelle.** Phase 1 (Labels): `solve_subgame(pub, pot_half, r0, r1, iters, hist="") -> (policy, Z)`,
`subgame_cfvs(pub, pot_half, r0, r1, iters)`, `generate_labels(n_situations, label_iters, workers)`,
`label_stability_probe(n_probe, iters_lo=500, iters_hi=1000)`. Phase 2 (Netz): `class CFVNet(nn.Module)`
mit eingebauter Nullsummen-Korrektur in `forward`, `train_net(x, y)`. Phase 3 (Re-Solving):
`class TrunkResolver(leaf_fn, hero=None)` mit `run(iters)`, `policy()`, `opponent_constraints()`;
`gadget_resolve(leaf_fn, trunk_iters, fill_iters)`, `resolve_subgame_gadget(...)`, `gadget_fill(...)`,
`harvest_query_beliefs(trunk_pols)`, `generate_boot_labels(...)`. Phase 4 (Gatter): `full_solve(iters)`,
`exact_constraints(pol_full)`, `main()`.
**Eingabe/Ausgabe.** Eingabe: nichts von aussen — die Situationen werden gesampelt (`_situation`,
`_sample_belief`). Zwischenformat: NumPy-Arrays `x` (Merkmale: Public-One-Hot, Pot, beide
Glaubensvektoren) und `y` (pot-normierte CFVs je Rang, beide Spieler); Zwischenspeicher
`data/research_sweep/gate0_leduc_labels.npz` und `..._boot.npz`. Ausgabe:
`data/research_sweep/gate0_leduc.json` mit den tragenden Schluesseln `config`, `label_stability`, `labels`,
`net` (`mae_train_pot`, `mae_holdout_pot`), `resolve` (inkl. `residual_decomposition_mbb`), `gate`
(`pass`, `delta_mbb`, `full_solve_mbb_per_hand`, `net_resolved_mbb_per_hand`, `trunk_policy_table`).
**Abhaengigkeiten.** Hart: `pokerbot.strategy.deep_cfr` (liefert `State`, `vanilla_cfr`, `exploitability`,
`key`, `regret_match`, `root_states`, `NACT`, `_avg`) — ohne dieses Modul laeuft gar nichts; `numpy`,
`torch`. Ersetzbar: nichts. Das Modul beruehrt den produktiven Bot NICHT.
**Zustand.** Je Lauf. Phasenweise persistiert: Labels und Ergebnisse werden auf Platte geschrieben und beim
naechsten Start wiederverwendet — wer eine Konstante aendert, muss `data/research_sweep/gate0_leduc*.npz`
loeschen, sonst rechnet die naechste Phase auf alten Labels weiter.
**Kosten.** Aus dem Ergebnis-JSON desselben Laufs: Label-Erzeugung 4.500 Teilspiele in 186,7 s auf zwoelf
Prozessen (`labels.seconds`), Netz-Training 5,7 s (`net.seconds`). Der Docstring nennt fuer den ganzen
Durchlauf "< 30 min CPU", `--quick` ~1 min (`gate0_leduc.py:38-39`).
**Mess-Status.** REFUTIERT — das Gatter ist DURCHGEFALLEN. `data/research_sweep/gate0_leduc.json`:
`gate.pass = false`, `gate.delta_mbb = 90,89` gegen eine vorregistrierte Schranke von 10,0 mbb/Hand
(`gate.bar`); voller Solve 10,02 mbb/Hand, netz-basiertes Re-Solving 100,91 mbb/Hand. Das NETZ selbst ist
dabei nicht das Problem im engeren Sinne (Holdout-MAE 0,0604 Pot-Anteile), die Zerlegung schreibt 69,64 mbb
dem Netzfehler an den Trunk-Glaeubigkeiten zu und 21,25 mbb der Konstruktion selbst. Positiv-Teilbefunde:
das Gadget hat gegenueber der Vorgaenger-Iteration 106,05 mbb (Oracle-Trunk) bzw. 26,94 mbb (Fill)
zurueckgeholt (`resolve.residual_decomposition_mbb`). Vorgeschichte in `docs/VALUE_NET_PLAN.md:52-79`:
Gate 0a validiert, Gate 0b BESTANDEN (val-MAE 0,191 = 6,4% der CFV-Skala), Gate 0c diagnostiziert als
spurioses Gleichgewicht der tiefenbegrenzten Konstruktion.
**Allein benutzbar?** Ja, als in sich geschlossenes Forschungspaket — aber nur zusammen mit
`pokerbot/strategy/deep_cfr.py`. Beide zusammen sind ein vollstaendiger, exakt bewertbarer Leduc-Pruefstand;
das ist der ehrlichste Ort, eigene Re-Solving-Ideen zu testen, bevor Geld fuer GPUs ausgegeben wird.
**Fallstricke.** Die CFV-Konvention. Der Docstring (`gate0_leduc.py:32-36`) warnt ausdruecklich: Labels und
Trunk-Blatt MUESSEN dieselbe Normierung verwenden (`CFV0[a] = sum_b r1[b]*mult(a,b|pub)*u0*(a,b)/Z`), sonst
ist das Re-Solving STILL falsch — kein Fehler, nur schlechte Zahlen. Zweiter Stolperstein: der
`BELIEF_FLOOR = 0.01` gilt NUR fuer Netz-Abfragen; die exakten Fill-Solves benutzen `FILL_BELIEF_FLOOR =
1e-6`, weil 0,01 rund 2% Phantom-Masse in jedes Teilspiel spritzt (im Code als gemessene Kompositionskosten
vermerkt).

### Solver-Destillation zum Politiknetz — `pokerbot/strategy/distill.py`
**Zweck.** Ein kleines stochastisches MLP lernt ueberwacht die Aktionsverteilung des TexasSolver-Orakels
nach — der billige, stichprobeneffiziente Weg zu einem niedrigen GTO-Abstand.
**Schnittstelle.** `features(hole, board, role_ip, pot, stack) -> list[float]` (schnelle Merkmale);
`build_dataset(pot=20.0, stack=100.0) -> (X, Y)` liest den Solver-Cache; `train(X, Y, epochs=300, lr=1e-3,
hidden=(128,128), device=None, seed=0, net=None, bs=0)` trainiert (Torch wird erst hier importiert);
`eval_gap(net, X, Y)` liefert den Selektor (mittlere TV/KL zur GTO-Zielverteilung);
`solve_focus_spots(focus, n=8, pot=20.0, stack=100.0, workers=8, threads=16, max_iter=30, seed=None)`
loest gezielt neue Boards nach; `main()`.
**Eingabe/Ausgabe.** Eingabe: die JSON-Dateien des Solver-Cache `data/_gto_bench_cache`. Ausgabe: `X` =
Merkmalsvektoren, `Y` = Verteilung ueber die fuenf kanonischen Aktions-Eimer `ACTIONS = ["fold_check",
"call", "aggr_small", "aggr_big", "allin"]` (Grenze klein/gross bei 0,66 Pot, `_bucket`).
**Abhaengigkeiten.** Hart: `pokerbot.config`, `engine.evaluator.evaluate`, `strategy.postflop.classify_board`,
ein gefuellter Solver-Cache. Weich: `torch` (nur zum Trainieren, bewusst lazy importiert, damit der
Datenbau ueberall laeuft).
**Zustand.** Zustandslos; der Cache auf Platte ist der einzige Speicher.
**Kosten.** Nicht gemessen. Der Docstring nennt als Entwurfsziel "fits a 30-min pod run".
**Mess-Status.** GEMESSEN NEGATIV / gedeckelt: der destillierte Boden bleibt bei rund 17% TV auf
SRP-Flop-Daten stehen (`docs/STATE.md:1898`). Das passt zur Projekt-Doktrin des Imitations-Deckels
(CLAUDE.md: Solver-Imitations-Boden plateau ~−72). Als eigenstaendiger bb/100-Hebel: UNGEMESSEN.
**Allein benutzbar?** Nur mit einem eigenen Solver-Cache im erwarteten JSON-Format (Knoten mit `children`,
Aktionsnamen wie `BET 6.6`, `CHECK`, `ALLIN`). Ohne den Cache ist das Modul leer.
**Fallstricke.** Die fuenf Eimer sind die Decke. Wer Overbets braucht, bekommt sie hier nicht — `_bucket`
faltet jede Groesse ueber 0,66 Pot in EINEN Eimer; genau das steht in `docs/STATE.md:1899-1900` als
benannte naechste Stufe ("finer action buckets (add overbets)").

### Deep-CFR-Adapter — `pokerbot/strategy/deepcfr_adapter.py`
**Zweck.** Setzt das von Grund auf trainierte HUNL-Deep-CFR-Politiknetz als Entscheidungskern ein, indem er
den Live-Engine-Zustand in EXAKT die Merkmalsfunktion des Trainers zurueckuebersetzt.
**Schnittstelle.** `class LoadedPolicy(path, device="cpu")` mit `strategy(feat, legal) -> {aktion: p}`
(Softmax ueber die legalen Aktionen, renormiert); `live_features(state, hero_idx) -> (feat_vec, p)`
rekonstruiert die Trainer-Merkmale, `p` ist der Spielerindex des Trainers (0 = Button);
`legal_fcpa(la) -> [int]` bildet das Engine-`legal`-dict auf fold/call/pot/allin ab;
`_selfcheck(n=800)` ist der eingebaute Beweis.
**Eingabe/Ausgabe.** Eingabe: Engine-`state` (`street`, `board`, `players[i].hole`/`committed_total`/
`is_button`, `legal.to_call`, `history` mit `street` und `action`) plus ein Checkpoint-Pfad mit dem
Schluessel `policy`. Ausgabe: Merkmalsvektor und Aktionsverteilung ueber die fcpa-Konstanten aus
`deep_cfr_hunl`.
**Abhaengigkeiten.** Hart und unaufloesbar: `pokerbot.strategy.deep_cfr_hunl` (liefert `Net`, `HState`,
`features`, `new_hand`, `FOLD/CALL/POT/ALLIN`) sowie `torch`, `numpy`. Der Adapter dupliziert bewusst KEINE
Merkmalslogik.
**Zustand.** `LoadedPolicy` haelt das geladene Netz (je Sitzung); `live_features` ist zustandslos.
**Kosten.** Ein Vorwaertsdurchlauf eines kleinen MLP je Entscheidung; nicht gemessen.
**Mess-Status.** GEMESSEN POSITIV nur als REKONSTRUKTION: `_selfcheck` prueft auf zufaelligen Zustaenden
`np.allclose(f_true, f_live, atol=1e-6)` und druckt PASS/FAIL — ein im Modul selbst ausfuehrbarer Beweis,
dass Trainings- und Inferenz-Merkmale identisch sind (`deepcfr_adapter.py:69-104`). Die Spielstaerke des
Netzes ist REFUTIERT: das fcpa-Politiknetz dieser Familie erreichte −212 bb/100 (CLAUDE.md,
"a HU policy net hit −212"); der Chef-Katalog grenzt `deep_cfr*.py` in `04_solver.md:580` ausdruecklich ab.
**Allein benutzbar?** Nur mit `deep_cfr_hunl.py` und einem trainierten Checkpoint. Der Wert fuer einen
Fremden liegt im MUSTER, nicht im Ergebnis: "rufe die Trainer-Merkmalsfunktion selbst auf statt sie zu
kopieren, und beweise die Identitaet mit einem Selbsttest" ist die uebertragbare Idee.
**Fallstricke.** Der Chip-Rahmen ist verdrahtet (SB 50 / BB 100 / Stack 20.000 = 200bb, Docstring Zeile 3).
Wer mit anderen Blinds spielt, bekommt still falsch skalierte Merkmale — der Selbsttest faengt das NICHT,
weil er dieselbe Skala auf beiden Seiten verwendet.

### Leeres Paketmodul — `pokerbot/valuenet/__init__.py`
0 Bytes. Reiner Paket-Marker, kein Inhalt, keine Re-Exporte.

---

## B — `infra/`: Pod-Steuerung

### Pod-Lebenszyklus — `infra/runpod_run.py`
**Zweck.** Provisioniert einen RunPod-Pod (GPU oder CPU), meldet dessen SSH-Endpunkt und terminiert ihn
wieder — die eine Stelle, an der im Projekt Geld ausgegeben wird.
**Schnittstelle.** `launch(fast=False, disk=60)` probiert eine Vorzugsliste von GPUs/Clouds durch, bis eine
anspringt; `launch_cpu(flavor="cpu5c", vcpu=32, disk=40)`; `status()` pollt jeden verfolgten Pod und druckt
`publicIp` + Port-Mappings; `stop(pid)` PAUSIERT (Container-Disk bleibt, Speicher wird weiter berechnet);
`kill()` terminiert JEDEN verfolgten Pod per `DELETE /pods/{id}` und leert die Sitzungsdatei; `gpus()`
listet GPU-Typen mit Preisen ueber GraphQL; `is_blackwell(gpu)`. CLI: `--launch [--fast] / --cpu
[--flavor --vcpu] / --gpus / --status / --kill`.
**Eingabe/Ausgabe.** Eingabe: der RunPod-API-Schluessel aus `C:\Users\hampe\Desktop\Secret keys\
Runpod-machiavel key.txt` (`KEY_FILE`, Zeile 18) und der oeffentliche SSH-Schluessel aus
`C:\Users\hampe\.ssh\pokerb_runpod.pub`; optional `POD_IMAGE`. Ausgabe: Konsolenzeilen plus die
Sitzungsdatei `data/_runpod_session.json` im Format `{"ids": [...]}` (das alte `{"id": x}` wird von
`_tracked_ids()` weiterhin gelesen).
**Abhaengigkeiten.** Nur `pokerbot.config` (fuer `ROOT`) und Standardbibliothek (`urllib`). Ersetzbar: die
`config`-Abhaengigkeit ist eine Zeile.
**Zustand.** Je Sitzung, auf Platte: `data/_runpod_session.json`. `_track()` haengt IDs AN und ueberschreibt
nie — damit `--kill` wirklich alle Pods erwischt. Zuruecksetzen = Datei loeschen (dann sind laufende Pods
allerdings nicht mehr verfolgt und laufen auf Rechnung weiter).
**Kosten.** Echtes Geld. `gpus()` druckt die aktuellen Stundenpreise; `launch()` gibt `costPerHr` der
erzeugten Instanz aus. Keine gespeicherte Zahl im Repo.
**Mess-Status.** UNGEMESSEN (Infrastruktur). Belegt sind nur Betriebs-Erkenntnisse als Code-Kommentare:
Blackwell-Karten (B200/B300, sm_100/103) fielen ohne torch `+cu128` auf den Mathematik-Pfad zurueck und
liefen dadurch rund 10-mal langsamer (beobachtet 2026-06-14, 14B bei ~25 s/it — `runpod_run.py:29-33`);
die korrekte B300-ID lautet `NVIDIA B300 SXM6 AC`.
**Allein benutzbar?** Ja, praktisch sofort — es ist ein duenner REST-Klient. Minimal: eigener API-Schluessel,
eigener SSH-Pubkey, `KEY_FILE`/`PUBKEY_FILE` anpassen.
**Fallstricke.** `stop()` ist NICHT `kill()`. Ein pausierter Pod wird weiter fuer Speicher berechnet — die
Projektregel lautet deshalb ausnahmslos `--kill` (CLAUDE.md). Zweiter Punkt: die Sitzungsdatei ist GLOBAL;
zwei parallele Kampagnen teilen sie sich, und ein `--kill` der einen terminiert die Pods der anderen mit
(genau davor warnt `infra/eval_pod.py:5-7`).

### Selbst-toetende RL-Kampagne — `infra/runpod_rl_campaign.py`
**Zweck.** Ein Kommando faehrt den kompletten Trainingslauf auf einem frisch provisionierten H100/H200:
Setup, DSL-SFT (Gate 0), DAPO-GRPO, GTO-verankerte Holdout-Evaluation, Ergebnis-Pull — und terminiert den
Pod IMMER (`atexit` + `finally`).
**Schnittstelle.** Modul mit `main()`/CLI; die Phasen sind als Schritte hintereinandergeschaltete
SSH-Kommandos. Kein wiederverwendbares API — der Wert liegt im Ablaufmuster.
**Eingabe/Ausgabe.** Eingabe: das Code-Tarball (Repo-Teilmenge) plus die Gold-Shards; Ausgabe: der beste
LoRA-Adapter und die Logdateien, per scp zurueck auf den PC.
**Abhaengigkeiten.** Hart: `infra/runpod_run` (Provisionierung + Kill), ein funktionierender
SSH-Schluessel, die Pod-Setup-Skripte, `training/`. Nicht ersetzbar ohne Umbau.
**Zustand.** Je Kampagne; der Pod ist der Zustand. Zuruecksetzen = Pod terminieren, Sitzungsdatei pruefen.
**Kosten.** GPU-Stunden; nicht als Zahl im Repo hinterlegt.
**Mess-Status.** REFUTIERT als Hebel — nicht das Skript, sondern das, was es misst: die Kette SFT -> GRPO
brachte in der letzten Ausfuehrung eine REGRESSION von −28 auf −90,18 gegen GTO Wizard (CLAUDE.md,
"a re-SFT on made-hand-NATIVE gold + a fresh GRPO REGRESSED to −90.18"). Der SFT-Warmstart selbst
funktioniert (Token-Genauigkeit 97,5%, `docs/STATE.md:1159`).
**Allein benutzbar?** Nein — es ist die Verdrahtung DIESES Projekts. Uebertragbar ist das Muster:
selbst-toetend (`atexit` UND `finally`), Gatter-Leiter zwischen den Phasen, Ergebnis-Pull vor dem Kill.
**Fallstricke.** Der Pull steht am ENDE. Zwei Laeufe des Projekts starben an SSH-Zeitueberschreitungen und
verloren dabei das Modell (Memory `grpo-reward-fix-and-timeout-fragility`); die Gegenmassnahme war ein
unabhaengiger Waechter (`infra/_resft_mon.py`) und ein Zwischen-Greifer (`infra/_grab_sft.py`).

### Kampagnen-Pods (Gruppe) — `infra/{cfv_pod_campaign,eval_pod,export_pod,slumbot_pod,ablation_pod}.py`
**Zweck.** Fuenf gleich gebaute, selbst-toetende Ein-Zweck-Kampagnen: CFV-Datenerzeugung auf mehreren
CPU-Pods, isolierte Slumbot-Baseline-Messung, parallele Erzeugung der ganzen Analyzer-Arm-Familie,
HU-Slumbot-Benchmark mit vLLM-gehostetem Brain, und die RESOLVER-ON-Ablation.
**Schnittstelle.** Je Datei ein `main()` mit eigenen Flags; keine importierbaren Bausteine.
`cfv_pod_campaign` provisioniert N CPU-Pods, richtet jeden ein (TexasSolver-Linux + Repo-Code) und merged
die Shards; `eval_pod` misst `qwen_poker_ckpt500` gegen Slumbot; `export_pod` erzeugt mehrere
1500-Hand-Exporte parallel; `slumbot_pod` startet einen vLLM-Server (Basismodell + LoRA) und laesst das
Brain ueber die Engine spielen; `ablation_pod` faehrt die 2x2-Isolation mit eingeschalteten Resolvern.
**Eingabe/Ausgabe.** Eingabe: Code-Tarball + jeweilige Artefakte (Adapter, Cache, Seeds). Ausgabe: die
gepullten Ergebnisdateien im lokalen `data/`.
**Abhaengigkeiten.** Alle hart auf `infra/runpod_run`; `export_pod` zusaetzlich auf
`research/pokerstars_export` bzw. `research/sixmax_export`; `slumbot_pod` auf `pokerbot/benchmark/slumbot*`.
**Zustand.** Je Kampagne. `eval_pod` loest ausdruecklich den Konflikt der GEMEINSAMEN Sitzungsdatei —
es darf einen parallel trainierenden Pod nicht mit-killen (`eval_pod.py:5-7`).
**Kosten.** Der Grund fuer `export_pod` ist ausdruecklich Zeit: ein 1500-Hand-Seed-55-Export laeuft LOKAL
Stunden, wenn der Turn-Solve-Cache nach einer Hebel-Aenderung kalt ist (`export_pod.py:3-5`). Absolute
Zahlen: nicht gemessen.
**Mess-Status.** UNGEMESSEN als Hebel (Werkzeuge). `ablation_pod` traegt den Anlass als belegte Zahl: der
Live-Bruch von −58 zeigte, dass alle Nacht-Hebel resolver-OFF validiert worden waren, waehrend das
Live-Spiel resolver-dominiert ist (`ablation_pod.py:3-5`; dieselbe Geschichte in CLAUDE.md als v8-Bruch).
**Allein benutzbar?** Nein. Fuer einen Fremden sind sie Vorlagen, keine Bausteine.
**Fallstricke.** Die geteilte Sitzungsdatei aus `runpod_run` — wer zwei dieser Kampagnen gleichzeitig
faehrt, riskiert, dass ein `kill()` beide Pods terminiert. `eval_pod` ist die einzige Datei, die diesen
Fall explizit behandelt; die anderen tun es nicht.

### Pod-Sonden und Waechter (Gruppe) — `infra/{runpod_launch,runpod_check,runpod_recon,runpod_cpu_probe,_grab_sft,_resft_mon}.py`
**Zweck.** Sechs kleine Hilfen um die Pod-Steuerung herum: ein Trockenlauf-Starter, drei nur-lesende
API-Sonden und zwei unabhaengige Waechter, die einen haengenden Lauf abfangen.
**Schnittstelle.** `runpod_launch` prueft Guthaben, druckt Rezept und Kostenschaetzung und provisioniert
NICHTS ohne `--go` (114 Zeilen); `runpod_check` (32 Z.) prueft Konnektivitaet/Auth; `runpod_recon` (38 Z.)
listet verfuegbare Deploy-Mutationen und GPU/CPU-Optionen; `runpod_cpu_probe` (35 Z.) findet die gueltigen
CPU-Flavor-IDs; `_grab_sft` (93 Z.) pollt den Pod auf
`/root/qwen_poker_lora/adapter_model.safetensors`, zieht ihn nach `models/sft_new.tgz` und LOESCHT den Pod;
`_resft_mon` (121 Z.) pollt unabhaengig von der Kampagne und killt bei Stillstand.
**Eingabe/Ausgabe.** Eingabe: API-Schluessel, Pod-ID aus der Sitzungsdatei. Ausgabe: Konsolenzeilen; bei
`_grab_sft` zusaetzlich das Tarball.
**Abhaengigkeiten.** Alle auf `infra/runpod_run` bzw. direkt auf die RunPod-REST-API; `_grab_sft`/`_resft_mon`
zusaetzlich auf funktionierendes `ssh`/`scp` unter Windows.
**Zustand.** Zustandslos bis auf die geteilte Sitzungsdatei.
**Kosten.** Die drei Sonden kosten nichts (nur-lesend, ausdruecklich "no pods provisioned, no cost").
**Mess-Status.** UNGEMESSEN. Der Existenzgrund von `_resft_mon` ist ein belegter Betriebsfehler: die
SSH-Zeitueberschreitung der Kampagne feuert unter Windows NICHT sauber, ein abgestuerzter SFT liess den Pod
im Leerlauf weiter Rechnung schreiben (`_resft_mon.py:3-5`).
**Allein benutzbar?** `runpod_check`/`runpod_recon`/`runpod_cpu_probe` ja, sofort und gefahrlos. Die
Waechter nur mit der zugehoerigen Kampagne.
**Fallstricke.** `_grab_sft` und `_resft_mon` KILLEN Pods eigenstaendig. Wer sie parallel zu einer laufenden
Kampagne startet, ohne die Sitzungsdatei zu verstehen, kann sich den eigenen Trainingslauf abschalten.

---

## C — `research/`: Provenienz der Kern-Assets

### Preflop-Blueprint per exaktem CFR+ — `research/preflop_solve.py`
**Zweck.** Erzeugt den near-Nash-HU-200bb-Preflop-Blueprint durch rauschfreies CFR+ ueber einen echten
Bet-Size-Baum (limp / 2,5bb-Open / 3bet 10 / 4bet 24 / 5bet 60 / Jam) — das Asset, das der Katalogteil
02 als fertiges Produkt beschreibt.
**Schnittstelle.** `build_eqmatrix(sims, rng) -> list[list[float]]` baut die 169x169-All-in-Equity-Matrix
(obere Dreiecksmatrix per MC, untere per Symmetrie, Diagonale 0,5); `load_eqmatrix(sims, rebuild)` cached
sie nach `knowledge_base/ranges/preflop_eqmatrix.json`; `traverse(node, i, j, EQ, r_sb, r_bb, regret,
strat)` ist der CFR+-Rekursionsschritt (liefert den kontrafaktischen Wert des SB); `main()` faehrt die
Iterationen und schreibt das Ergebnis. Der Baum selbst ist die Modulkonstante `TREE`
(Knoten -> `(to_act, sb_inv, bb_inv, [(aktion, art, n_sb, n_bb, folgeknoten)])`, `art` in
`foldSB`/`foldBB`/`sd`/`sd_allin`/`node`).
**Eingabe/Ausgabe.** Eingabe: nur Flags (`--iters`, `--sims`, `--realize-kappa`, `--rebuild-eq`,
`--leaf-table`). Ausgabe: `knowledge_base/ranges/preflop_blueprint.json` im Format
`{knoten: {handklasse: {aktion: wahrscheinlichkeit}}}` (mit `--leaf-table`:
`preflop_blueprint_solvergraft.json`).
**Abhaengigkeiten.** Hart: `pokerbot.config`, `engine.cards` (`all_hand_classes`, `expand_class`,
`make_deck`), `engine.evaluator.evaluate`, `research.preflop_leaves.leaf_w`. Ersetzbar: `preflop_leaves`
ist eine 3-Zeilen-Funktion (die Naht fuer kalibrierte Blattwerte).
**Zustand.** Zustandslos je Lauf; die Equity-Matrix auf Platte ist der einzige Cache. Wird `--sims` erhoeht,
baut `load_eqmatrix` sie automatisch neu.
**Kosten.** GEMESSEN: Equity-Matrix ~3 min plus CFR+ ~3,5 min = ~6 min lokal, einkernig, danach gecacht
(`docs/STATE.md:1595-1596`). Derselbe Eintrag haelt fest, dass die Cloud hier VERLIERT (GCP-Setup allein
~15 min, eine CFR-Schleife nutzt viele vCPUs nicht).
**Mess-Status.** GEMESSEN POSITIV. Exakte Preflop-Ausbeutbarkeit im Modellspiel: `expl(blueprint) = 3,3`
gegen `expl(heuristik) = 234` bb/100, also 71-mal weniger ausbeutbar (`docs/STATE.md:1610-1611`, gemessen
mit `research/preflop_exploit.py`). Live nur RICHTUNGSWEISEND: −53 ± ~24 bb/100 mit Blueprint an (n=200)
gegen die −72-Baseline (`docs/STATE.md:1616`) — ausdruecklich nicht signifikant.
**Allein benutzbar?** Ja, das ist eines der am besten isolierbaren Module des Repos. Minimal noetig:
Kartencode und ein Handevaluator; `TREE` und `traverse` sind eigenstaendig lesbar. Wer einen anderen
Bet-Baum will, aendert nur `TREE`.
**Fallstricke.** Die Fortsetzungs-Naeherung. Nicht-All-in-Showdowns werden als CHECKDOWN gewertet
(`kind == "sd"`, `leaf_w`), es gibt also KEIN Postflop-Spiel im Modell. Das erfasst die All-in-Disziplin
sauber, unterschaetzt aber die Realisierbarkeit von suited/connected-Haenden — der Docstring sagt das
selbst (Zeilen 9-13), und `docs/STATE.md:1617-1620` warnt zusaetzlich: niedrige In-Modell-Ausbeutbarkeit
kann blosse Konvergenz gegen das FALSCHE (Checkdown-)Spiel bedeuten. Zweiter Fallstrick: eine frueh
versuchte, chance-gesampelte Variante liess die tiefen 4bet/5bet/Jam-Knoten als reines Rauschen zurueck
(72o callte 200bb-Jams) — deshalb die vorab berechnete Equity-Matrix.

### Blattwert-Kalibrierung (Gruppe) — `research/{preflop_calibrate,preflop_leaves,preflop_ranges}.py`
**Zweck.** Ersetzen die Checkdown-Schaetzung an den See-Flop-Blaettern des Blueprints durch eine aus echten
TexasSolver-Flop-Solves GEMESSENE Realisierungspraemie je Knoten.
**Schnittstelle.** `preflop_ranges.reaching_ranges()`/`load_blueprint()`/`sd_leaves()` liefern die
reach-gewichteten Ranges je See-Flop-Knoten (95 Z.). `preflop_calibrate.calibrate_node(node, blueprint,
n_flops, n_samples, max_iter, ...)` loest suit-kanonische Flops am Knoten und misst per Rollout die
realisierte EV des In-Position-Spielers; `flop_realized_ev(root, board, oop_str, ip_str, pot0, n_samples,
...)` ist der Kern, `_rollout`/`_checkdown_v0` die beiden Bewertungen, `_canonical_flops(n, rng)` die
Board-Auswahl (259 Z.). `preflop_leaves.load_leaf_table(path)`, `build_kappa_map(table, blueprint, EQ) ->
{knoten: kappa}` und `leaf_w(node, e, kmap, default_kappa) -> float` bilden die eine Naht, die
`preflop_solve.traverse` und `preflop_exploit._leaf` gemeinsam benutzen (59 Z.).
**Eingabe/Ausgabe.** Eingabe: der Blueprint plus TexasSolver. Ausgabe:
`knowledge_base/ranges/preflop_leaf_table.json` mit `w_node` je Knoten; daraus per
`build_kappa_map` ein `{knoten: kappa_node}` nach der Formel
`kappa_node = (w_node - E[e]) / (4 * E[e*(1-e)])`, reach-gewichtet.
**Abhaengigkeiten.** Hart: `pokerbot.strategy.gto_oracle` (also TexasSolver), `engine.cards`,
`engine.evaluator`, `research.preflop_ranges`. `preflop_leaves` haengt an gar nichts ausser `json`.
**Zustand.** Zustandslos; Tabellen auf Platte.
**Kosten.** Nicht gemessen (haengt an der Zahl der geloesten Flops mal `max_iter`).
**Mess-Status.** UNGEMESSEN als EV-Hebel — im Repo ist kein bb/100-Vergleich Blueprint-mit-Graft gegen
Blueprint-ohne-Graft belegt. Die Konstruktion selbst ist bewusst RUECKWAERTS-KOMPATIBEL: `kmap=None` oder
ein fehlender Knoten liefert exakt das alte Checkdown-Verhalten (`preflop_leaves.py:13-15`).
**Allein benutzbar?** `preflop_leaves` ja (reine Arithmetik). `preflop_calibrate` nur mit lauffaehigem
TexasSolver.
**Fallstricke.** Die Fidelitaetsstufe. `preflop_calibrate` loest NUR die Flop-Runde (`dump_rounds=1`) und
checkt Turn+River per Equity durch (Docstring Zeilen 9-11). Wer das fuer eine vollwertige
Postflop-Fortsetzung haelt, ueberschaetzt die Zahl.

### Exakte Preflop-Ausbeutbarkeit — `research/preflop_exploit.py`
**Zweck.** Misst den EXAKTEN Abstand zu Nash im Preflop-Modellspiel per Best-Response-Enumeration — die
Metrik, mit der der Blueprint gegen die alte Heuristik gestellt wurde.
**Schnittstelle.** Modul mit `main()`; berechnet `½[BRV_SB + BRV_BB]` (Johanson-Konvention) ueber alle
enumerierten Infosets des `TREE` aus `preflop_solve`, mit einer per-KNOTEN-Zerlegung.
**Eingabe/Ausgabe.** Eingabe: ein Strategieprofil (Blueprint-JSON oder die Heuristik). Ausgabe:
Ausbeutbarkeit in bb/100 gesamt und je Knoten.
**Abhaengigkeiten.** Hart: `research.preflop_solve` (Baum), `research.preflop_leaves.leaf_w`, die
Equity-Matrix.
**Zustand.** Zustandslos.
**Kosten.** Nicht gemessen.
**Mess-Status.** GEMESSEN POSITIV als Werkzeug — es hat zwei konkrete Lecks LOKALISIERT: 3BET +164 bb/100
(SB ueber-foldet gegen 3bets) und 4BET +87 (BB foldet zu 98% gegen 4bets), was die −72 gegen GTO Wizard
mechanistisch erklaert (`docs/STATE.md:1611-1615`).
**Allein benutzbar?** Nur zusammen mit `preflop_solve`.
**Fallstricke.** Zirkularitaet. `docs/STATE.md:1617-1620` haelt die vetted Warnung fest: In-Modell-
Ausbeutbarkeit ist ein KONVERGENZ-Test, keine echte Nash-Distanz — "low expl can just mean convergence to
the WRONG (checkdown) game". Die nicht-zirkulaere Variante braeuchte unabhaengige Blattwerte.

### Preflop-Nachschlagewerke (Gruppe) — `research/{preflop_table,preflop_probe,parse_ranges}.py`
**Zweck.** Drei unabhaengige Preflop-Quellen neben dem geloesten Blueprint: eine aus PokerBench destillierte
Nachschlagetabelle, 30 konstruierte Pruefspots gegen den 6-max-Kern, und die Range-Bildunterschriften aus
*Modern Poker Theory*.
**Schnittstelle.** `preflop_table` (159 Z.) destilliert PokerBench-Spots in eine Tabelle mit dem Schluessel
`hero_pos + level + last-raiser-pos + 169 Handklassen` und misst die Aktions-Uebereinstimmung auf dem
Holdout. `preflop_probe` (161 Z.) faehrt 30 konstruierte Spots gegen den `tag`-Kern und stellt Vorhersage
gegen Messung. `parse_ranges` (114 Z.) parst die `Hand Range N:`-Zeilen aus dem Buch ohne API.
**Eingabe/Ausgabe.** PokerBench-Datensatz bzw. Buchtext rein; JSON-Tabellen nach `knowledge_base/ranges/`
raus.
**Abhaengigkeiten.** `preflop_table` braucht den PokerBench-Datensatz (extern); `preflop_probe` den
6-max-Kern; `parse_ranges` nur den extrahierten Buchtext.
**Zustand.** Zustandslos.
**Kosten.** Nicht gemessen.
**Mess-Status.** GEMESSEN POSITIV fuer `preflop_table`: 88,6% Uebereinstimmung auf dem Holdout, besser als
beide LoRAs; Ergebnis liegt als `knowledge_base/ranges/preflop_gto_table.json` und ist in die 6-max-RFI
verdrahtet (`docs/STATE.md:1741-1743`). ACHTUNG: derselbe Stand vermerkt an anderer Stelle, dass
`preflop_gto.py` (88,6%) in den HU-`bot.py` NICHT verdrahtet ist (`docs/STATE.md:1672`). `preflop_probe`
und `parse_ranges`: UNGEMESSEN.
**Allein benutzbar?** `parse_ranges` ja. `preflop_table` nur mit PokerBench.
**Fallstricke.** 88,6% Aktions-Uebereinstimmung ist KEINE Spielstaerke — die Projekt-Doktrin (CLAUDE.md,
mehrfach gemessen) lautet, dass Frequenz-Nachahmung ohne die Selektion des Lehrers EV kostet.

### Advisor-Datenbauer (Gruppe) — `research/{build_river_data,build_turn_data,build_defense_data}.py`
**Zweck.** Erzeugen die Trainingsdaten der drei Berater-Netze (River, Turn, Facing-Bet-Verteidigung) aus den
bereits vorhandenen TexasSolver-Caches — ohne neue Solves.
**Schnittstelle.** Je Datei ein `main()`. `build_river_data` (67 Z.) laeuft ueber
`data/_gto_river_cache/*.json`; die Cache-Wurzel IST der OOP-River-Knoten und ihr `CHECK`-Kind der
IP-Knoten, deshalb ohne Linien-Lauf. `build_turn_data` (96 Z.) hat `_smallest_bet(children)` (die
Nicht-All-in-C-Bet = kleinste `BET`-Groesse) und `_extract(node, role, board4, tex, rows)`; es folgt der
klassischen Turn-Barrel-Linie flop CHECK -> BET -> CALL -> Turn. `build_defense_data` (122 Z.) hat
`_defense_rows(defender, node, board, tex, st, street, size_faced)`, `_bet_children(node)` und
`_process_cache(cache_dir, street, nboard, cap=None)`; es zieht aus BEIDEN Caches (Flop 3-Karten und
River 5-Karten) die Knoten eine Ebene tiefer.
**Eingabe/Ausgabe.** Eingabe: die Solver-Cache-Verzeichnisse. Ausgabe: JSONL-Zeilen nach
`data/river_data.jsonl`, `data/turn_data.jsonl`, `data/defense_data.jsonl`. Merkmale einheitlich
`FEAT = ["tier","flush_draw","backdoor_flush","nut_flush_blocker","made_straight","oesd","gutshot",
"overcards","has_draw"]` plus Textur und Rolle; Ziel `y` = P(bet) bei River/Turn, `(P_fold, P_call,
P_raise)` bei der Verteidigung.
**Abhaengigkeiten.** Hart: `pokerbot.config`, `pokerbot.benchmark.gto_benchmark` (`_CACHE`, `texture`),
`engine.evaluator.evaluate`, `strategy.features.hand_features`.
**Zustand.** Zustandslos.
**Kosten.** Nicht gemessen; `build_turn_data` lief laut Docstring AUF DEM POD, weil die DUMP=2-Cache-Dateien
mit ~8 MB je Datei zu gross zum Ziehen waren.
**Mess-Status.** UNGEMESSEN als eigenstaendige Hebel (Datenbauer). Die daraus trainierten Berater sind in
Katalogteil 03 beschrieben.
**Allein benutzbar?** Nur mit einem TexasSolver-Cache im erwarteten Dump-Format.
**Fallstricke.** Die drei Dateien sehen austauschbar aus, sind es aber nicht: `build_river_data` spiegelt
bewusst `build_advisor_data` (Flop) und NICHT `build_turn_data` — weil die River-Cache-Wurzel schon der
gesuchte Knoten ist. Wer die Turn-Logik auf den River kopiert, laeuft den Baum eine Ebene zu tief.
Zweitens deckt `build_defense_data` NUR Flop und River ab; Turn und weitere Groessen/SPRs fehlen und
braeuchten neue Solves (Docstring Zeile 7).

### CFV-Netz-Kette (Gruppe) — `research/{cfv_eval,cfv_data,train_cfv_net}.py`
**Zweck.** Die drei Schritte, die das Turn-Blatt-Wertnetz fuer einen Flop-Resolver liefern sollten: CFVs aus
geloesten River-Teilspielen ziehen, daraus einen Datensatz erzeugen, das Netz trainieren.
**Schnittstelle.** `cfv_eval` (168 Z., Phase-B-Schritt 8) extrahiert per-Combo-River-CFVs aus einem
geloesten TexasSolver-Dump — die Trainingslabels. `cfv_data` (171 Z., Schritt 9) erzeugt daraus den
Datensatz `cfv_dataset.jsonl`: (4-Karten-Turnboard + beide Ranges + Pot) -> per-Combo-Turn-Boundary-CFVs.
`train_cfv_net` (140 Z., Schritt 10) trainiert das Netz auf `cfv0[169]`/`cfv1[169]`.
**Eingabe/Ausgabe.** Solver-Dumps rein, `cfv_dataset.jsonl` in der Mitte, ein `.pt`-Netz raus.
**Abhaengigkeiten.** Hart: TexasSolver (fuer die Labels), `torch` (fuer das Netz), die Nullsummen-Konvention
aus `cfv_eval` (`value0 = winnings0 - (pot/2 + street_contrib0)`), die `preflop_calibrate` ausdruecklich
uebernimmt.
**Zustand.** Zustandslos; Datensatz und Netz auf Platte.
**Kosten.** Nicht gemessen; die Datenerzeugung war der Grund fuer `infra/cfv_pod_campaign.py` (mehrere
CPU-Pods).
**Mess-Status.** UNGEMESSEN im HUNL-Massstab. Das GLEICHE Konstruktionsprinzip ist auf Leduc REFUTIERT
worden (siehe `pokerbot/valuenet/gate0_leduc.py`: Gatter durchgefallen, 90,89 mbb ueber der Schranke) —
allerdings mit der ausdruecklichen Einschraenkung in `docs/VALUE_NET_PLAN.md:70-79`, dass die Leduc-Version
STRENGER degeneriert ist als der HUNL-Plan (dort waeren Flop+Turn explizit, das Netz nur am Turn->River-Blatt).
**Allein benutzbar?** Nur als Kette und nur mit Solver.
**Fallstricke.** Die Vorzeichen- und Normierungs-Konvention. Sie muss zwischen `cfv_eval`, `cfv_data` und dem
Abfrageort im Resolver identisch sein; ist sie es nicht, ist das Ergebnis still falsch (dieselbe Falle, die
`gate0_leduc.py:32-36` fuer Leduc dokumentiert).

### Cache-Werkzeuge und Short-Deck (Gruppe) — `research/{mass_solve_shortdeck,train_sd_advisor,texture_freqs,analyze_cache,inspect_node}.py`
**Zweck.** Fuenf Werkzeuge am Solver-Cache: eine Short-Deck-Variante des Massen-Solvens, der zugehoerige
Berater, die Extraktion exakter Per-Textur-Frequenzen, und zwei Inspektoren.
**Schnittstelle.** `mass_solve_shortdeck` (69 Z.) spiegelt das Parallelmuster von `mass_solve.py` mit
`mode='shortdeck'` (36 Karten, 6-A) nach `data/_gto_shortdeck_cache`. `train_sd_advisor` (77 Z.) trainiert
den Short-Deck-Bet-vs-Check-Berater auf `data/sd_advisor_data.jsonl`, ausgehalten BOARDWEISE, gegen eine
(Rolle, Textur)-Frequenz-Baseline. `texture_freqs` (63 Z.) zieht die exakten GTO-Bet-Frequenzen des
OOP-Donk- und des IP-C-Bet-Knotens aus dem 1340-Board-Cache nach
`knowledge_base/postflop/texture_freqs.json`. `analyze_cache` (106 Z.) druckt, was echtes GTO auf diesen
Flops tut, aufgeschluesselt nach Textur. `inspect_node` (49 Z.) legt die Rohstruktur eines
DUMP=2-Chance-Knotens offen.
**Eingabe/Ausgabe.** Cache-JSONs rein; JSON-Tabellen, ein `.pt` bzw. Konsolenausgabe raus.
**Abhaengigkeiten.** Hart: `pokerbot.config`, `pokerbot.benchmark.gto_benchmark`, TexasSolver fuer das
Massen-Solven.
**Zustand.** Zustandslos.
**Kosten.** Nicht gemessen. Groessenordnung: das Cache-Verzeichnis `data/_solve_cache` enthielt beim
Schreiben dieses Nachtrags 12.493 Dateien — die Zahl WAECHST mit jedem Lauf und ist kein Festwert (Teil 04
nennt 12.209, eine Zwischenzaehlung 12.395).
**Mess-Status.** UNGEMESSEN, mit einer Ausnahme: `texture_freqs` ersetzte gemessene Heuristiken durch
Solver-Frequenzen und speist die C-Bet-Politik, die in `gto_baseline` kalibriert wurde (93% -> 80%,
`gto_baseline.py:29-31`). `train_sd_advisor` ist laut eigenem Docstring ausdruecklich ein SANITY-Test, kein
Produkt.
**Allein benutzbar?** `analyze_cache` und `inspect_node` ja (reine Leser). Der Rest braucht TexasSolver.
**Fallstricke.** Short-Deck ist ein ANDERES Spiel (Flush schlaegt Full House, geaenderte Equities). Wer den
Short-Deck-Cache versehentlich in die Voll-Deck-Pipeline haengt, bekommt plausible, aber falsche Zahlen.

---

## D — `research/`: externe Benotung

### HU-Export fuer den GTO-Wizard-Analyzer — `research/pokerstars_export.py`
**Zweck.** Laesst den HU-Bot gegen `GTOBaseline` spielen und schreibt die Haende als
PokerStars-Hand-History, damit der GTO-Wizard-Analyzer JEDE Hero-Entscheidung gegen GTO benoten kann — die
schnelle, kostenlose Haelfte der Messoekonomie (das 6-max-Gegenstueck ist `sixmax_export.py`).
**Schnittstelle.** `hero_decider(seat, seed, resolver=None)` liefert einen Decider, der EXAKT den
Live-GTOW-Agenten benutzt (`benchmark.gtowizard.PokerBotAgent`, Sitz 0 zwingend);
`villain_decider(seat, seed)`; `stack_mit_protokoll(variante, roh_decider, hand_idx, protokoll)` wickelt den
v4-Guard-Stapel aus der EINEN Quelle `autogym.pargate._wickle` um einen fertigen Decider und protokolliert
jeden Eingriff; `play_hand(g, hero_seat, idx, resolver=None, ...)`; `format_hand(hand_id, dt, names, button,
holes, history, result, hero_seat) -> str` erzeugt den Textblock; `money(chips) -> str`; `main()`.
**Eingabe/Ausgabe.** Eingabe: Flags (`--n`, `--out`, `--hero`, Seeds) plus die Umgebungsvariablen des
GTO-Modus. Ausgabe: eine Textdatei mit PokerStars-formatierten Haenden bei SB 50 / BB 100 / Stack 20.000
(= 200bb, `pokerstars_export.py:29`); Hero wechselt je Hand den Sitz, damit beide Positionen benotet werden;
Stacks werden je Hand zurueckgesetzt (Cash-Game).
**Abhaengigkeiten.** Hart: `strategy.gto_mode.apply` (MUSS vor jedem Strategie-Import laufen, siehe
Fallstricke), `engine.game.HeadsUpGame`, `strategy.bot`, `strategy.gto_baseline.GTOBaseline`,
`benchmark.gtowizard.PokerBotAgent`, `autogym.pargate` (`KANDIDATEN`, `_wickle`).
**Zustand.** Je Lauf; das Modul-globale `GEFEUERT` sammelt die Guard-Eingriffe ueber alle Haende und wird
NICHT automatisch geleert.
**Kosten.** Der Katalog-Rahmen (CLAUDE.md, Mess-Oekonomie) nennt fuer den Export von 1500 Haenden lokal
etwa 4 Minuten nach der Memoisierung; `infra/export_pod.py:3-5` haelt dagegen fest, dass ein
1500-Hand-Export bei KALTEM Turn-Solve-Cache Stunden dauert.
**Mess-Status.** GEMESSEN POSITIV als Messkanal — der HU-Arm dieses Exports lieferte die erste absolute
GTO-Note der HU-Engine: GTO-Score 53,4% / Freq-Diff 54,6% (CLAUDE.md, ★★★ CURRENT-TRUTH-Block; das
6-max-Gegenstueck kam auf 85,9% / EV-Loss 7,61). Als EV-Hebel: UNGEMESSEN (es ist ein Messgeraet).
**Allein benutzbar?** Der FORMATIERER ja: `format_hand` und `money` sind ein eigenstaendiger
PokerStars-Serialisierer, den man mit einer beliebigen Engine fuettern kann. Der Rest haengt an diesem Bot.
**Fallstricke.** Zwei, beide teuer bezahlt. (1) `_apply_gto_mode()` steht ABSICHTLICH vor den
Strategie-Importen (`pokerstars_export.py:15-21`) — die Flags werden beim Import gelesen; wer die Zeile
verschiebt, exportiert eine ANDERE Konfiguration als die, die live gemessen wurde. (2) Der Guard-Stapel
kommt aus `pargate._wickle`; eine fruehere lokale Kopie hatte eine andere Marge und UNGESEEDETE
Monte-Carlo — das zerbrach die Paarung gepaarter Vergleiche (Kommentar `pokerstars_export.py:57-62`).
Ausserdem gilt die Ledger-Regel aus CLAUDE.md: Hand-IDs verbrennen beim ERSTEN Kontakt, `idbase`/`dayoffset`
nie wiederholen.

### Entscheidungs-Benotung der eigenen Sitzung (Gruppe) — `research/{study_grade,study_analyze,study_review,study_distill}.py`
**Zweck.** Ein wiederverwendbarer Pruefstand, der jede geloggte Entscheidung einer GTOW-/Slumbot-Sitzung
gegen die beste verfuegbare Wahrheit benotet — Preflop gegen den Blueprint, Postflop gegen den Solver — und
den Befund bis zur Lehrer-Gold-Destillation weiterfuehrt.
**Schnittstelle.** `study_grade` (481 Z.) ist der Kern: `reconstruct_spot(session_hand, hero, button,
prefix, street)`, `hero_decision_points(history, button, hero)`, `hero_seat_and_button(session_hand,
hero_hole)`, `audit_inputs(feat, spot, reasoning)` (trennt "die Verdrahtung lieferte falsche Mathematik" von
"das Urteil war falsch"), `grade_preflop(feat, action)`, `grade_postflop(spot, feat, action, amount_bb,
solve)`, `grade_one(dec, session_hand, recon_pref, solve)`, `run(stage, threads, solve_threads, limit)`,
`regrade_unscored(...)`; CLI-Stufen `--stage recon` (kostenlos) und `--stage grade` (mit Solver).
`study_analyze` (258 Z.) macht daraus die gerankten Lecks + Kanten und waehlt die ~36 haertesten Spots aus;
`study_review` (130 Z.) holt dazu eine UNABHAENGIGE OpenAI-Zweitmeinung (ein Claude-Selbstreview waere
befangen); `study_distill` (92 Z.) destilliert die guten Entscheidungen zu Lehrer-Gold.
**Eingabe/Ausgabe.** Eingabe: `data/claude_play/thought_log.jsonl` plus die Sitzungs-Handhistorien.
Ausgabe: append-only JSONL mit einer Note je Entscheidung (fortsetzbar — bereits benotete `seq` werden
uebersprungen).
**Abhaengigkeiten.** Hart: `pokerbot.benchmark.slumbot.build_state` und
`benchmark.slumbot_llm.spot_from_slumbot` (dieselbe Naht, die der Live-Bot benutzt), `api.solve_node`
(TexasSolver), der Preflop-Blueprint. Ersetzbar: die OpenAI-Zweitmeinung in `study_review`.
**Zustand.** Je Lauf, aber fortsetzbar ueber die JSONL-Datei; `regrade_unscored` holt Luecken nach.
**Kosten.** Deterministisch und kostenlos ausser der CPU des Solvers (Docstring Zeile 16); die
Stufe `recon` laeuft ohne Solver.
**Mess-Status.** GEMESSEN POSITIV als Werkzeug: 264 Entscheidungen benotet, Postflop-Solver-Deckung 98,8%
(160/162), plus unabhaengige Zweitmeinung auf den 33 haertesten Spots (`docs/STATE.md:1139`). Befund:
96,2% im Support, das −38 AIVAT war River-/Grosspot-VARIANZ statt Lecks; das eine echte kleine Leck war
Postflop-Ueber-Checken (Memory `claude-code-vs-gtow-study`).
**Allein benutzbar?** Der Rekonstruktions-Teil ja, wenn man Handhistorien im Slumbot-Token-Format hat. Der
Benotungsteil braucht Blueprint + Solver.
**Fallstricke.** Der EV-Verlust ist ein PROXY. `api.solve_node` liefert keine EV je Aktion; nur fuer
call/fold ist die Zahl echte bb (Docstring Zeilen 12-14). Wer die Summe als bb/100 liest, ueberdehnt sie.
Zweitens: das Modul deckte den `to_call`-Verdrahtungsfehler nur auf, WEIL es die geloggten gegen die
rekonstruierten Eingaben stellt (`input_inflated`) — diese Trennung wegzulassen verwandelt einen
Verdrahtungsfehler in ein scheinbares Urteilsproblem.

### Slumbot-Werkzeuge (Gruppe) — `research/{slumbot_collect,slumbot_mistakes,slumbot_v22}.py`
**Zweck.** Gegen den frei verfuegbaren Slumbot spielen, reich protokollieren und die Fehler herausziehen.
**Schnittstelle.** `slumbot_collect` (54 Z.) spielt `PokerBot(exploit=False)` gegen Slumbot und schreibt je
Hand Hole-Karten, Board, den vollen Aktions-String, `winnings`, `won_pot` und Slumbots Showdown-Karten in
eine JSONL. `slumbot_mistakes` (78 Z.) liest diese Datei und legt die Fehler offen.
`slumbot_v22` (105 Z.) faehrt den gesetzten v2.2-Anker MIT eingeschaltetem Slumbot-spezifischem Exploit.
**Eingabe/Ausgabe.** Netzwerk rein, JSONL raus, Fehlerliste auf der Konsole.
**Abhaengigkeiten.** Hart: `pokerbot.benchmark.slumbot` (HTTP-Klient + `build_state`), Internet.
**Zustand.** Je Sitzung ein Slumbot-`token`.
**Kosten.** Netzwerklatenz je Entscheidung; nicht gemessen.
**Mess-Status.** GEMESSEN NEUTRAL: die Engine liegt gegen Slumbot bei etwa break-even (+12,6 bei n=500;
die frueher zitierten −46/−871/−374 waren falsch), und die Fehler teilen sich etwa haelftig in Cooler und
behebbares -EV-Ueberbluffen (Memory `engine-vs-slumbot-breakeven`, Werkzeuge ausdruecklich
`slumbot_collect`/`slumbot_mistakes`).
**Allein benutzbar?** Ja, sobald ein eigener Bot die `(action, amount)`-Schnittstelle bedient — Slumbot ist
oeffentlich und kostenlos. Fuer einen Fremden ist das der billigste externe Realitaetstest im ganzen Repo.
**Fallstricke.** n=500 gegen Slumbot ist statistisch duenn; die Projektgeschichte an genau dieser Stelle
(vier verschiedene "gemessene" Zahlen fuer dieselbe Engine) ist die Warnung.

### Orakel-Kreuzpruefung und Restwerkzeuge (Gruppe) — `research/{gtow_oracle_check,play_gtow,pokerbench_grounded}.py`
**Zweck.** Pruefen, ob unser eigenes Solver-Orakel mit dem staerksten verfuegbaren Benchmark uebereinstimmt;
einen Handshake bereitstellen, ueber den ein Agent GTO Wizard Hand fuer Hand spielt; PokerBench als
geerdete 6-max-Referenz erschliessen.
**Schnittstelle.** `gtow_oracle_check` (245 Z.) stellt die Orakel-Empfehlung gegen GTOWs TATSAECHLICHES
Spiel. `play_gtow` (73 Z.) ist der Dateihandshake-Treiber fuer den `ClaudeCodeAgent`.
`pokerbench_grounded` (93 Z.) parst die 563k templatierten PokerBench-Entscheidungen in strukturierte Spots.
**Eingabe/Ausgabe.** GTOW-Handhistorien bzw. der PokerBench-Datensatz rein; Uebereinstimmungsstatistik bzw.
strukturierte Spots raus.
**Abhaengigkeiten.** Hart: GTOW-API-Schluessel (fuer die Kreuzpruefung), TexasSolver, PokerBench.
**Zustand.** Zustandslos.
**Kosten.** Solver-CPU; nicht gemessen.
**Mess-Status.** GEMESSEN POSITIV fuer `gtow_oracle_check`: unser Solver/Blueprint-Orakel ist zu rund 90%
mit GTOW ausgerichtet, also NICHT grob kaputt — dieser Befund hat die spekulative
Postflop-Solver-Generalueberholung ABGERAEUMT (CLAUDE.md, "our solver/blueprint ORACLE is ~90% aligned with
GTOW (NOT grossly broken) → the speculative postflop-solver overhaul ... is NOT justified by the data").
`play_gtow`, `pokerbench_grounded`: UNGEMESSEN.
**Allein benutzbar?** `pokerbench_grounded` ja (nur der oeffentliche Datensatz). Die anderen beiden brauchen
den GTOW-Forscherzugang.
**Fallstricke.** Der GTOW-Zugang ist der knappe Kanal des Projekts (CLAUDE.md: Hand-Budget, Ledger-Pflicht).
Wer die Kreuzpruefung gedankenlos ueber viele Haende laufen laesst, verbrennt Budget, das fuer Live-Anker
gebraucht wird.

---

## E — `research/`: Diagnose und Wirkungs-Beweise

### River-Bill-Replay — `research/river_bill_replay.py`
**Zweck.** Rueckschau-Konfusionsmatrix: haette der `river_bill_guard` die gemessenen Grosspot-River-Call-
Desaster wirklich gefoldet, und wie viele gewonnene Grosspot-Calls haette er gekostet?
**Schnittstelle.** `spot_state(hand, hero_seat, spot_idx, acts) -> dict | None` rekonstruiert den Zustand am
Call-Spot live-treu; `main()` faehrt beide Arme (Kontrolle und v4_prince) und druckt die Matrix.
**Eingabe/Ausgabe.** Eingabe: die geloggten GTOW-Nacht-2-Handhistorien (`data/sessions/gtow_hands_*.jsonl`).
Ausgabe: je Spot `fold_net = -committed_total_hero_vor_call` und `delta = fold_net - winnings` (positiv =
der Fold haette gerettet), aggregiert zur Matrix.
**Abhaengigkeiten.** Hart: `benchmark.gtowizard._parse_history` (der validierte Token-Uebersetzer), der
echte `river_bill_guard`-Codepfad (um eine Dummy-Basis gewickelt, die immer `('call', None)` liefert), die
Hero-Sitz-Logik `hero_seat_of`.
**Zustand.** Zustandslos, deterministisch.
**Kosten.** Kostenlos, laeuft auf geloggten Daten.
**Mess-Status.** GEMESSEN, gemischt — und deshalb lehrreich. Journal `data/autogym/journal.jsonl`, Eintrag
`R7-DIAGNOSE` vom 2026-08-30 19:55:52: 20 Trigger-Spots, der Guard foldet 5 davon — 3 richtig (+141bb),
2 falsch (−121bb), netto +20bb. Derselbe Eintrag haelt den TRENNSCHAERFE-Befund fest: die Tracker-Equity
trennt Gewinner und Verlierer NICHT (Default 0,578 vs 0,513; PRINCE-Env 0,652 vs 0,532; die Ranges sind nach
drei Barrels noch 700-900 Combos breit), und die beiden 200bb-Stack-offs liegen UNTER dem Trigger.
**Allein benutzbar?** Nur mit unseren Handlogs und dem Guard. Das MUSTER ist aber uebertragbar: einen Guard
gegen echte, aus der Zukunft bekannte Ergebnisse zu halten, bevor man ihn ausliefert.
**Fallstricke.** Der Docstring sagt es selbst (Zeilen 22-25): das ist ein WIRKUNGS-NACHWEIS-Proxy fuer eine
Gate-Entscheidung, KEIN bb/100-Schaetzer — der Fold aendert die kuenftige Anpassung des Gegners nicht mit.
Und das Konsistenz-Gatter ist Pflicht: stimmt der rekonstruierte Pot nicht mit `replay_voll.pot_before`
ueberein, wird die Hand AUSGESCHLOSSEN und gezaehlt (nie mit falschen Zahlen rechnen).

### River-Kohaerenz-Diagnose — `research/river_coherence.py`
**Zweck.** Benotet die Value-/Bluff-/Bluffcatch-Kohaerenz unseres Bots gegen das GELOESTE
River-Gleichgewicht — der River-Diagnose-Score.
**Schnittstelle.** Modul mit `main()` (562 Z.); Ergebnis nach
`data/research_sweep/river_coherence.json`.
**Eingabe/Ausgabe.** Gespielte River-Entscheidungen rein; ein Score je Kategorie raus.
**Abhaengigkeiten.** Hart: der Solver, der Range-Tracker; Spezifikation `docs/RIVER_SYSTEM.md` und
`data/research_sweep/openai_river_consult.json`.
**Zustand.** Zustandslos.
**Kosten.** Solver-CPU; nicht gemessen.
**Mess-Status.** UNGEMESSEN als Hebel (Diagnose-Werkzeug); das Ergebnis-JSON liegt im Repo, im Katalog ist
keine daraus abgeleitete bb-Zahl belegt.
**Allein benutzbar?** Nein, verwoben mit Tracker und Solver.
**Fallstricke.** Ein Kohaerenz-Score ist eine FREQUENZ-Metrik. Die Projekt-Doktrin (CLAUDE.md, dreimal
gemessen) sagt, dass Frequenz-Angleichung ohne die Selektion des Lehrers EV KOSTET — ein besserer Score ist
also kein Ship-Argument.

### Komponenten-Kompetenz-Matrix — `research/component_matrix.py`
**Zweck.** Misst, WELCHE entscheidungs-erzeugende Komponente des Bots in WELCHER Region des Spiels die beste
ist, benotet gegen das TexasSolver-Orakel — die Operationalisierung des Prinzips "ensemble, don't discard".
**Schnittstelle.** Modul mit `main()` (672 Z.); Ergebnis nach
`data/research_sweep/component_matrix.json`.
**Eingabe/Ausgabe.** Spot-Stichprobe rein; je (Komponente x Region) eine Guete raus.
**Abhaengigkeiten.** Hart: alle bewerteten Komponenten (Blueprint, Advisors, Resolver, Heuristiken) plus
TexasSolver.
**Zustand.** Zustandslos.
**Kosten.** Solver-CPU je Spot; nicht gemessen.
**Mess-Status.** UNGEMESSEN als Hebel. Der zugrundeliegende Gedanke ist im Memory `ensemble-not-discard`
festgehalten (per-Kontext-Zuverlaessigkeit gewichten statt eine Komponente an ihrem Durchschnitt zu
verwerfen), aber eine daraus abgeleitete gemessene bb-Verbesserung ist im Repo nicht belegt.
**Allein benutzbar?** Nein.
**Fallstricke.** Die Matrix ist so gut wie das Orakel. Da die Kreuzpruefung dem Orakel ~90% Ausrichtung mit
GTOW bescheinigt, sind die restlichen 10% genau die Zellen, in denen die Matrix in die Irre fuehren kann.

### River- und Resolver-Sonden (Gruppe) — `research/{river_bill_diagnose,river_leak,river_probe,resolver_probe,freq_diff,v8_replay_gegentest}.py`
**Zweck.** Sechs schmale Sonden auf denselben River-/Resolver-Komplex: Trennschaerfe der Tracker-Equity,
Leck-Zuordnung mit der eigenen Mathematik, Verhaltensprofil, Resolver-Latenz und Feuerrate,
Frequenz-Differenz zum Lehrer, und ein Achsen-Gegentest fuer beliebige Guard-Stapel.
**Schnittstelle.** `river_bill_diagnose` (84 Z.) stellt fuer die 20 Trigger-Spots die exakte Equity gegen
die Tracker-Range. `river_leak` (57 Z.) wiederholt `PokerBot(exploit=False)` gegen `GTOBaseline` (Seed 7)
und loggt je River-Entscheidung `rationale['equity']` und, vor einem Bet, die benoetigte Equity — ohne
GTOW. `river_probe` (129 Z.) profiliert Heros River-Verhalten auf denselben 1000 Haenden wie der
GTOW-Upload nach Aktion x Handstaerke x SPR. `resolver_probe` (60 Z.) misst Latenz und Feuerrate des
line-aware Resolvers. `freq_diff` (265 Z.) bucketet HERO (PRINCE v2.2) und GTOW in dieselben Eimer wie
`freq_mine`. `v8_replay_gegentest` (219 Z.) laesst beliebige Guard-Stapel gegen die echten
Nacht-2-Haende laufen.
**Eingabe/Ausgabe.** Geloggte Haende bzw. frische Self-Play-Laeufe rein; Konsolen-/JSON-Befunde raus.
**Abhaengigkeiten.** Hart: der jeweilige Bot-Pfad plus `gtowizard._parse_history` bei den Replay-Sonden.
**Zustand.** Zustandslos.
**Kosten.** `resolver_probe` MISST Kosten (das ist sein Zweck); die uebrigen sind billig, weil sie auf
Logs laufen.
**Mess-Status.** UNGEMESSEN als Hebel (Messgeraete). Ein daraus gewonnener, belegter Befund steht im
Journal-Eintrag zu `river_bill_diagnose` (siehe `river_bill_replay` oben: Tracker-Equity trennt nicht).
**Allein benutzbar?** `river_leak` am ehesten — es braucht nur den eigenen Bot und die Baseline, kein
externes Konto.
**Fallstricke.** Diese Sonden erzeugen HYPOTHESEN, keine Verdikte. Die Projekt-Doktrin verlangt fuer jedes
Verdikt ein gepaartes Gate (`pargate`/`envgate`) und drei Laeufe vor einer Taufe.

### Akquise-, Range- und Kanal-Werkzeuge (Gruppe) — `research/{blindspot_radar,grounded_blindspots,check_floor_range,danger_pair,duplicate_mode_ab,theory_duel,flop_pilot}.py`
**Zweck.** Sieben Werkzeuge fuer die Frage "wo soll ich als Naechstes hinschauen und womit messe ich es":
LLM-triagiertes aktives Lernen, sein geerdetes Gegenstueck, ein Range-Gatter, ein klassendichter A/B-Bauer,
die schnelle lokale Kanarienvogel-Messung, ein Duell gegen die Theorie selbst und ein Solve-Kosten-Pilot.
**Schnittstelle.** `blindspot_radar` (204 Z.) triagiert per LLM, welche Spots geloest werden sollen.
`grounded_blindspots` (93 Z.) macht dasselbe OHNE LLM: wo weicht der analytische Boden (`GTOBaseline`) am
staerksten vom Solver ab, direkt aus dem Cache. `check_floor_range` (119 Z.) prueft, ob die per-Combo-
P(call) des aktionskonsistenten Trackers naeher an der wahren Post-Call-Range des Solvers liegt als die
`_narrow`-Heuristik. `danger_pair` (49 Z.) baut klassendichte Arme fuer SELTENE Hebel, die auf normalen
1500-Hand-Saetzen unsichtbar sind. `duplicate_mode_ab` (92 Z.) faehrt HEAD gegen GTOW-Modus auf
GESPIEGELTEN Decks gegen `GTOBaseline` — kostenlos, ohne Netz, Kartenglueck zweifach gekuerzt.
`theory_duel` (59 Z.) stellt den Bot gegen die zwei in-Engine-Verkoerperungen der Pokertheorie.
`flop_pilot` (88 Z.) misst, was EIN Flop-zu-Terminal-Solve bis zur Konvergenz wirklich kostet.
**Eingabe/Ausgabe.** Cache/Logs/Seeds rein; Kandidatenlisten bzw. gepaarte Deltas raus
(`flop_pilot` nach `data/research_sweep/flop_pilot.json`).
**Abhaengigkeiten.** Hart: `GTOBaseline` und der Solver-Cache; `blindspot_radar` zusaetzlich eine LLM-API.
**Zustand.** Zustandslos.
**Kosten.** `flop_pilot` misst sie: der Vorlaeufer `research/flop_feasibility.py` deckelte bei 300 s und
bekam 49 von 50 Zeitueberschreitungen (`flop_pilot.py:4-5`).
**Mess-Status.** GEMESSEN NEGATIV fuer die LLM-Triage: `blindspot_radar` ist Hypothesen-Generator, es hat
seine eigene Top-Markierung durch Messung WIDERLEGT (Memory `blindspot-radar-and-verify`); der Solver ist
der Linchpin-Verifizierer, Spieltests sind fuer Einzelregeln zu verrauscht. Die uebrigen: UNGEMESSEN als
Hebel.
**Allein benutzbar?** `grounded_blindspots` und `duplicate_mode_ab` ja, mit Cache bzw. Baseline.
**Fallstricke.** `duplicate_mode_ab` misst gegen `GTOBaseline`, nicht gegen GTOW. Die
Autogym-Doktrin (CLAUDE.md) ist hier hart: solche Kanal-Ergebnisse heissen `KANAL_*` und sind NIE
Ship-Evidenz.

---

## F — `research/`: Oekologie und echte Spielerpools

### GG-NL2-Populationsanalyse — `research/gg_nl2_pop.py`
**Zweck.** Vermisst eine echte $0.01/$0.02-6-max-Population aus rund 600k Handhistorien und laesst
verschiedene Hero-Arme dagegen simulieren — die Quelle mehrerer Oekologie-Zahlen des Projekts.
**Schnittstelle.** `berlin_hour(hand_text) -> int | None` (GG-Zeitstempel sind UTC, Annahme dokumentiert);
`_iter_all()` iteriert die Handhistorien; `_configure_gg(eu_only)` schaltet das Zeitfenster;
`zeit_pass() -> dict` der billige Zeit-/Stats-Durchlauf; `_window(H, hours)`, `print_zeit(H)`;
`make_hero(arm)` baut den Hero-Arm (`clone` = Ist-Zustand, `agame` = Reset-Klon, plus die Hebel
`agame+nolimp`, `agame+valuegate`, `agame+3bet`, `agame+calldisc`); `main()`.
**Eingabe/Ausgabe.** Eingabe: entpackte Handhistorien unter `data/gg_nl2/hh`, BB = $0.02. Ausgabe:
Populations-Statistik plus Arm-Ergebnisse als JSON (`--out`).
**Abhaengigkeiten.** Hart: `research.coinpoker_ecology` (das Parser-Geruest, auf dem es aufsetzt), die
6-max-Liga; `zoneinfo`.
**Zustand.** Zustandslos; die Konfiguration `_configure_gg` ist allerdings MODUL-GLOBAL — sie wirkt auf
alle nachfolgenden Iterationen im selben Prozess (`boltzmann_fit` importiert genau diese Funktion).
**Kosten.** Nicht gemessen (Parsen von ~600k Haenden).
**Mess-Status.** GEMESSEN POSITIV als Messkanal, mit dem teuersten Einzelbefund des Projekts: auf dem
haertesten Pool (GG $10/$20, 85% TAG) erzielten GTO +106 und Exploit +126 (modell-optimistisch), der
P_D-Klon dagegen −216 gegen den P_D-A-GAME-Klon +16,6 ± 5,3 [+6,3, +27] — der TILT kostet also rund
233 bb/100 (CLAUDE.md, ★★★★★-Block 2026-08-04, "die teuerste gemessene Verhaltensvariable des Projekts").
**Allein benutzbar?** Nur mit einem eigenen GG-Handhistorien-Export im erwarteten Format.
**Fallstricke.** Simulierte Arme gegen eine aus Frequenzen rekonstruierte Population sind
MODELL-optimistisch — die Zahlen +106/+126 sind ausdruecklich so gekennzeichnet. Sie sind Oekologie-Lehren,
keine Winrate-Versprechen.

### Boltzmann-Temperatur-Fit — `research/boltzmann_fit.py`
**Zweck.** Testet falsifizierbar, ob ein Pokerpool ein thermisches Ensemble ist (P(Aktion) ~ exp(lambda*EV)):
eine NUR aus Entscheidungsfrequenzen gefittete Temperatur soll die echte Winrate OUT-OF-SAMPLE vorhersagen.
**Schnittstelle.** `_day_parity(hand) -> int | None` (Kalendertag-Split);
`population_by_parity(parity) -> dict`; `channels_by_parity(parity) -> dict` liefert die zwei unabhaengigen
dominierten Kanaele `theta1 = logit(Open-Limps / First-in-Gelegenheiten)` und
`theta2 = logit(Limp-Calls / Limps)`; `logit(k, n)`; `spearman(xs, ys)`; `main()`.
**Eingabe/Ausgabe.** Eingabe: der 683k-Hand-Korpus ueber `gg_nl2_pop._iter_all`. Ausgabe: Konsolenbericht
mit der Konsistenzpruefung `corr(theta1, theta2)` und dem Vergleich gegen den Kontroll-Praediktor VPIP.
**Abhaengigkeiten.** Hart: `research.coinpoker_ecology`, `research.gg_nl2_pop` (`_configure_gg`,
`_iter_all`). Ohne den Korpus laeuft nichts.
**Zustand.** Zustandslos, aber der Modul-globale Zustand von `_configure_gg` wirkt hinein.
**Kosten.** Nicht gemessen.
**Mess-Status.** UNGEMESSEN — im Repo (docs/, Journal) ist KEIN Ergebnis dieses Laufs abgelegt; das Modul
druckt nur auf die Konsole. Wer die These braucht, muss es selbst laufen lassen.
**Allein benutzbar?** Nein (haengt am Korpus und an zwei anderen Modulen).
**Fallstricke.** Die Konstruktion steht und faellt mit der Sauberkeit des Splits: Temperatur wird auf
Haelfte A gefittet, Winrate auf Haelfte B gemessen, dieselben Haende beruehren sich nie. Wer den Split
lockert, misst sich selbst.

### Pool- und Gegner-Profile (Gruppe) — `research/{gg_hs_ecology,gg_nl2_mistakes,coinpoker_ecology,coinpoker_style,coinpoker_replay,pro_hands_profile,flynnie_profile,flynnie_duel}.py`
**Zweck.** Aus echten Handhistorien Populationen und einzelne Gegner profilieren und den eigenen Bot
dagegen simulieren.
**Schnittstelle.** `gg_hs_ecology` (109 Z.) stellt zwei Bot-Arme gegen die $10/$20-Population.
`gg_nl2_mistakes` (132 Z.) zaehlt, wie oft der Pool KLARE strategische Fehler macht. `coinpoker_ecology`
(366 Z.) ist das Basis-Geruest (Parser + Populationsmix + echte Winrates), auf dem die GG-Module aufsetzen.
`coinpoker_style` (235 Z.) profiliert den Stil eines Spielers (VPIP/PFR/3bet/Open-Limp/C-Bet/WTSD/
Aggression/Sizing, nach Position). `coinpoker_replay` (217 Z.) laesst den 6-max-Produktbot (`tag`) die
echten Haende Entscheidung fuer Entscheidung nachspielen und loggt Uebereinstimmung und Abweichung.
`pro_hands_profile` (146 Z.) und `flynnie_profile` (239 Z.) profilieren einzelne Gegner aus
PokerStars-Historien; `flynnie_duel` (320 Z.) laesst den Bot gegen die konkurrierenden Gegnerbilder spielen.
**Eingabe/Ausgabe.** Handhistorien-Textdateien rein; Statistik-JSON/Konsole raus.
**Abhaengigkeiten.** Hart: `arena.sixmax` (fuer die Simulationsarme), regulaere Ausdruecke auf dem
jeweiligen Site-Format. Site-Formate sind NICHT austauschbar.
**Zustand.** Zustandslos.
**Kosten.** Nicht gemessen.
**Mess-Status.** GEMESSEN POSITIV als Kanal (siehe `gg_nl2_pop` fuer die Zahlen). Fuer die
Einzelgegner-Module: UNGEMESSEN.
**Allein benutzbar?** Nur mit passenden Handhistorien. `coinpoker_style` ist das am leichtesten
uebertragbare Stueck (ein reiner Stil-Profiler).
**Fallstricke.** Jede dieser Dateien parst EIN Site-Format mit fest verdrahteten regulaeren Ausdruecken.
Ein anderes Format bricht sie still (leere Zaehler statt Fehler).

### Personenbezogene Reports (Gruppe) — `research/{prince_protocol,prince_ecology,pd_day,pd_nl200,pd_physics,tourney_report}.py`
**Zweck.** Vermessen die Spielweise EINER realen Person (des Nutzers) aus deren eigenen Handhistorien und
erzeugen daraus Berichte.
**Schnittstelle.** `prince_protocol` (560 Z.) parst alle Haende, rechnet die volle Statistiktabelle, misst
die Hypothesen H1-H10 und schreibt `data/research_sweep/prince_protocol.json`; `prince_ecology` (384 Z.)
simuliert Oekologie-Szenarien; `pd_day` (211 Z.) obduziert eine Tagessession; `pd_nl200` (223 Z.) misst das
A-Game auf NL200; `pd_physics` (156 Z.) prueft drei Gesetze an den eigenen Haenden; `tourney_report`
(467 Z.) rendert daraus ein PDF.
**Eingabe/Ausgabe.** Eingabe: Handhistorien-Dateien AUSSERHALB des Repos (`prince_protocol.py:15-16`
verweist auf `C:\Users\hampe\Documents\...`). Ausgabe: JSON und PDF.
**Abhaengigkeiten.** Hart: die jeweiligen Dateipfade, die Engine fuer die Simulationsarme.
**Zustand.** Zustandslos.
**Kosten.** Nicht gemessen.
**Mess-Status.** GEMESSEN als Analyse (923 CoinPoker-Cash- und 75 GG-Turnierhaende laut Docstring), mit
harter Regel im Modul selbst: keine erfundenen Zahlen, n je Metrik, `[DATEN FEHLEN]`-Marker, wo Daten
fehlen (`prince_protocol.py:4`). Als EV-Hebel fuer einen Bot: UNGEMESSEN (es sind Spielerberichte).
**Allein benutzbar?** Fuer einen Fremden praktisch nicht — die Pfade zeigen auf private Dateien.
**Fallstricke.** REPO-GRENZE. CLAUDE.md zieht eine ausdrueckliche Linie: persoenliche Akten und Berichte
ueber reale Personen gehoeren nach `#Anderes/` und werden nie versioniert. Diese Module leben in
`research/`, lesen aber personenbezogene Daten von ausserhalb — wer den Baustein uebernimmt, uebernimmt
diese Grenzfrage mit. Der uebertragbare Teil ist die METHODE (Parser + Statistiktabelle + n je Metrik),
nicht die Person.

---

## G — `research/`: Turnier und MTT

### PS-Turnierfeld und Duell (Gruppe) — `research/{ps_tourney_field,ps_tourney_duel}.py`
**Zweck.** Vermessen ein echtes High-Stakes-Turnierfeld PHASENWEISE und lassen die eigenen Turnier-Arme
dagegen antreten — der Kern-Trick: die gemessenen Frequenzen des Pools ENTHALTEN sein ICM-Verhalten
bereits, statt es zu simulieren.
**Schnittstelle.** `ps_tourney_field` (125 Z.): `_phase(eff_bb) -> str` (deep >40bb / mid 15-40 / short
<15), `parse() -> dict`, `main()`. `ps_tourney_duel` (202 Z.): `_hand_class(hole)`, `_phase(eff_bb)`,
`make_hero(arm)` mit den drei Armen `chipEV` (tag-Kern pur), `icm` (tag + ICM-Brille: anteiliges
Risiko-Premium + exakte All-in-Schwelle) und `icm+druck` (dazu der Coverstack-Druckhebel + Live-Reads),
`run_one(structure, arm, seed, field_kind="freq")`, `main()`.
**Eingabe/Ausgabe.** Eingabe: PokerStars-Turnier-Handhistorien unter `data/ps_tourney/hh/**/*.txt`.
Zwischenformat: `data/ps_tourney_field.json` mit dem Schluessel `phasen` (je Phase VPIP, FoldVsRaise,
Jam-Anteil). Ausgabe des Duells: ROI/Ladder je Arm unter zwei Auszahlungsregimen (`sng65_35` und
`winner_take_all`).
**Abhaengigkeiten.** Hart: `arena.sixmax.PROFILES`/`SixMaxBot`, `strategy.preflop_strength`,
`strategy.tournament` (`BlindLevel`, `Director`, `Structure`) — und fuer das Duell zwingend die von
`ps_tourney_field` erzeugte JSON-Datei.
**Zustand.** `ps_tourney_duel` laedt `FIELD` beim IMPORT (Modulebene, Zeile 33) — fehlt die Datei, scheitert
schon der Import. Gepaarte Seeds je Turnier.
**Kosten.** Nicht gemessen.
**Mess-Status.** GEMESSEN POSITIV als Beleg fuer die ICM-Tightness des Feldes: die $1050-Vermessung zeigt
FoldVsRaise 54% -> 62% und Jam 1,1% -> 13,1% von deep nach short (CLAUDE.md, Standbein 2). Der zugehoerige
Hebel selbst (anteiliges Risiko-Premium in `strategy/tournament.py`) ist separat gepaart validiert:
+10,0 ± 5,0 pp ROI bei n=1500, 95%-Band [+0,2, +19,9] — der VOLLE Bubble-Faktor wurde dagegen REFUTIERT
(−8pp, Bubble-Ausbluten). Diese Zahlen gehoeren zu `tournament.py`, nicht zu diesen beiden Dateien.
**Allein benutzbar?** `ps_tourney_field` ja, wenn man PokerStars-Turnier-Historien hat — es ist ein reiner
Parser. Das Duell braucht die ganze Turnier-Schicht.
**Fallstricke.** Die Phase wird ueber die effektive Stacktiefe in bb approximiert, NICHT ueber die Zahl der
verbliebenen Spieler — der Docstring nennt das eine bewusste Naeherung, weil Spieler-uebrig aus
Handhistorien tischuebergreifend nicht rekonstruierbar ist. Unter `winner_take_all` ist ICM per Definition
gleich chipEV; wer dort einen ICM-Gewinn misst, misst einen Fehler.

### Turnier-Simulationen (Gruppe) — `research/{mtt_sim,mtt_report,tonight_sim,spin_sim,turnier_live,turnier_replay}.py`
**Zweck.** Sechs Szenario-Simulationen und Auswertungen rund um Turniere: ein 600-Spieler-MTT, die
Kampagnen-Poolung, ein 60er-Freezeout, die Spin-&-Gold-Lotterie, die Vermessung eines laufenden Turniers
und der Replay der eigenen 88 Haende durch die Engine.
**Schnittstelle.** `mtt_sim` (383 Z.) simuliert das $1050/$600k-Event; `mtt_report` (78 Z.) poolt die
Worker-JSONs und rechnet die GEPAARTEN Verdikte; `tonight_sim` (464 Z.) das 60er-Freezeout mit 50k-Start,
10er-Tischen und limpigem Feld; `spin_sim` (230 Z.) das 3-max-Hyper-SNG; `turnier_live` (270 Z.) misst, was
tatsaechlich gespielt wurde; `turnier_replay` (422 Z.) laesst Prince v2 (GTO) und die Exploit-Schicht ueber
dieselben Haende laufen.
**Eingabe/Ausgabe.** Struktur-/Feld-Parameter bzw. Handhistorien rein; ROI/Ladder-JSON raus.
**Abhaengigkeiten.** Hart: `strategy/tournament.py`, `strategy/icm.py`, `arena/sixmax.py`.
**Zustand.** Je Lauf; `mtt_report` setzt voraus, dass mehrere Worker in dasselbe Verzeichnis geschrieben
haben.
**Kosten.** Nicht gemessen.
**Mess-Status.** UNGEMESSEN als Hebel (Szenario-Werkzeuge). Die validierte Turnier-Zahl haengt an
`strategy/tournament.py` (siehe oben), nicht an diesen Simulationen. Der Formatvergleich-Befund
(NL2-Cash >> Spin&Gold > Mystery-BR) liegt als Memory `gg-formats-verdict` vor.
**Allein benutzbar?** Nein.
**Fallstricke.** Simulierte Felder sind konstruiert. `mtt_report` ist das einzige Modul der Gruppe, das
gepaarte Verdikte rechnet — Zahlen aus den anderen fuenf ohne diese Paarung sind Szenario-Beschreibungen,
keine Messungen.

---

## H — `research/`: Vision (PokerSnowie)

### Glyphen-Sammler — `research/snowie_collect.py`
**Zweck.** Bringt der lokalen Erkennung das Karten- und Zifferndeck EINMALIG bei: klickt sich stumpf durch
Spielgeld-Haende und legt dabei jeden Glyph ab, den das Template-Matching noch nicht kennt.
**Schnittstelle.** `_collect(sub, kind, seen, bright) -> bool` legt einen unbekannten Glyph ab (True = neu),
mit Dedup gegen bereits gesammelte per derselben Metrik wie die Erkennung; `run(iters, pause)` die
Sammelschleife; `main()` mit `--iter`, `--pause`.
**Eingabe/Ausgabe.** Eingabe: der laufende PokerSnowie-4-Cash-Tisch auf dem Bildschirm. Ausgabe: PNG-Dateien
unter `SL.DUMP_DIR/{rank_b,rank_h,digit}/` (Board-Raenge, Hero-Raenge, Ziffern) plus, bei jeder Gelegenheit,
Belegbilder des Betragsfeldes unter `.../bet/soll_<wert>_<n>.png`. Am Ende druckt es Median/min/max der
Betrags-Eingabezeit in Millisekunden.
**Abhaengigkeiten.** Hart: `pokerbot.vision.snowie_local` (Regionen, `grab`, `crop_frac`, `match`,
`_binary`, `_score`), `pokerbot.vision.snowie_state` (`_binary_bright`, `number_fields`, `_digit_boxes`,
`match_digit`, `hero_turn`), `pokerbot.vision.snowie_bridge` (`_click_frac`, `_type_number`, `window_box`),
`PIL`, `numpy`. Und: ein tatsaechlich geoeffnetes PokerSnowie-Fenster.
**Zustand.** Je Lauf. Das `seen`-Woerterbuch wird zu Beginn aus den VORHANDENEN Templates vorgeladen, damit
Bekanntes nicht erneut gesammelt wird. Zuruecksetzen = Dump-Verzeichnis leeren.
**Kosten.** Ein Bildschirmabzug plus Template-Vergleiche je Runde, Default-Pause 0,45 s; Absolutwerte nicht
gemessen. Die Betrags-Eingabezeit MISST es selbst zur Laufzeit (kein Wert im Repo abgelegt).
**Mess-Status.** UNGEMESSEN. Das Modul ist ausdruecklich "KEIN Spiel und KEINE Messung" (Docstring Zeile 3).
Was daran haengt, ist gemessen: die Bruecke insgesamt spielt 13,3 Haende/min bei ~4% Aussetzern, und der
bereinigte Pool von 3.114 sauberen Haenden ergab +3,2 bb/100 [−37, +44] (CLAUDE.md, Standbein 1).
**Allein benutzbar?** Nur mit dem ganzen `pokerbot/vision`-Paket und PokerSnowie. Aber es ist der SCHRITT 1
der Kette — ohne ihn ist die Erkennung auf einem neuen Rechner oder Theme nicht neu aufsetzbar.
**Fallstricke.** `DEDUP_MIN = 0.82` ist der ganze Unterschied zwischen "Deck gelernt" und "Dutzende Kopien
desselben Zeichens". Und die Konstante `AMOUNT_BOX = (1766, 1234, 1878, 1282)` ist eine LIVE VERMESSENE
Pixelkoordinate — bei anderer Aufloesung oder anderem Fenster tippt das Modul ins Leere, ohne sich zu
beschweren. Die gesammelten Glyphen muessen anschliessend von HAND gelabelt werden (die letzte Zeile des
Laufs sagt, wo).

### Snowie-Waechter und Rekorder (Gruppe) — `research/{snowie_marathon,snowie_record}.py`
**Zweck.** Einen mehrstuendigen Snowie-Lauf ueberhaupt durchbringen (Etappen-Waechter) und ihn
nachpruefbar machen (Bildschirm-Mitschnitt).
**Schnittstelle.** `snowie_marathon` (109 Z.): `hands_in(files) -> int` zaehlt die GESPIELTEN Haende
(Hole-Karten-Wechsel mit mindestens einer Entscheidung) aus den Session-Logs nach; die Schleife startet die
Bruecke in Etappen von `CHUNK_HANDS = 150` mit `PAUSE_S = 20` Pause und gibt nach
`MAX_BARREN_CHUNKS = 5` Etappen ohne neue Hand auf. `snowie_record` (53 Z.): `run(seconds)` schneidet den
Tisch mit `FRAME_S = 0.25` (4 Bilder/s) als JPEGs mit `JPEG_Q = 70` (~120 KB/Bild) nach
`data/vision/rec/<zeitstempel>/` mit; der Dateiname traegt die Unix-Zeit in Millisekunden — dieselbe Uhr wie
das Entscheidungs-Log, sodass sich jede Entscheidung dem naechsten Bild zuordnen laesst.
**Eingabe/Ausgabe.** Session-Logs bzw. Bildschirm rein; Etappenberichte bzw. Bildfolgen raus.
**Abhaengigkeiten.** Hart: `pokerbot.vision.snowie_bridge` (der Marathon startet sie als Subprozess, der
Rekorder nutzt `esc_pressed`), `snowie_local.grab`.
**Zustand.** Der Zaehler des Marathons ist BEWUSST nicht im Prozess, sondern wird aus den Logs
rekonstruiert — deshalb ueberlebt er den Tod einer Etappe. Stopp ueber die Datei `data/vision/STOP`.
**Kosten.** Rekorder: ~120 KB je Bild bei 4 Bildern/s (aus den Konstanten, im Code als "Stunden passen auf
die Platte" begruendet).
**Mess-Status.** UNGEMESSEN (Betriebswerkzeuge). Die Marathon-Konstruktion ist der Grund, warum ueberhaupt
3.651 Haende in drei Laeufen zusammenkamen (CLAUDE.md, Standbein 1).
**Allein benutzbar?** Der Rekorder fast (er braucht nur `grab` und eine ESC-Abfrage). Der Marathon ist an
das Log-Format der Bruecke gebunden.
**Fallstricke.** ESC beendet nur die LAUFENDE Etappe; der Waechter wartet danach und macht weiter, wenn die
STOP-Datei fehlt (Docstring Zeilen 8-10). Wer den Lauf per ESC "beenden" will, startet ihn in Wahrheit neu.

---

## I — `research/`: Netz-/RL-Reste und Kleinwerkzeug

### RL-/Netz-Reste (Gruppe) — `research/{deep_cfr_nlhe,openspiel_leduc,distill_improve,eval_lora,llm_probe,llm_exploit_demo,teacher_serverless_client,pod_run30}.py`
**Zweck.** Acht Ueberbleibsel der Netz- und LLM-Phasen: neuronales Deep CFR auf abstrahiertem HUNL, die
OpenSpiel-Validierung auf Leduc, ein lokaler Destillations-Verbesserer, die Holdout-Evaluation eines LoRA,
zwei LLM-Sonden, der Klient fuer den serverlosen Lehrer und ein 30-Minuten-Pod-Orchestrator.
**Schnittstelle.** `deep_cfr_nlhe` (111 Z.) faehrt neuronales Deep CFR auf OpenSpiel `universal_poker`
(fcpa) auf dem GPU-Pod. `openspiel_leduc` (55 Z.) misst die Exploitability von OpenSpiels Deep CFR auf
Leduc — ein niedriger `nash_conv` beweist, dass der neuronale Loeser konvergiert. `distill_improve` (40 Z.)
verbessert das Destillationsnetz lokal per Minibatching (die Voll-Batch-Baseline unterpasst ~328k Beispiele,
weil sie insgesamt nur `epochs` Gradientenschritte macht). `eval_lora` (66 Z.) misst die Aktions-
Uebereinstimmung auf UNGESEHENEN PokerBench-Zeilen (disjunkt konstruiert ueber denselben Loader mit
`shuffle(seed=0)`). `llm_probe` (18 Z.) und `llm_exploit_demo` (29 Z.) pruefen, was das lokale LoRA
tatsaechlich ausgibt bzw. demonstrieren die Kette Direktive -> `directive_to_nudge` -> gedeckelte Anpassung.
`teacher_serverless_client` (132 Z.) feuert Generierungs-Jobs an den serverlosen Endpunkt und haengt die
engine-GEGATETEN Beispiele an `data/teacher_raw.jsonl`. `pod_run30` (80 Z.) ist ein zeitgedeckelter
Destillations-Orchestrator mit LLM-gesteuertem Curriculum.
**Eingabe/Ausgabe.** Je nach Modul: OpenSpiel-Spiele, PokerBench-Zeilen, LoRA-Adapter, Endpunkt-Antworten.
**Abhaengigkeiten.** Hart und schwer: OpenSpiel, `torch`, `peft`/`transformers`, ein RunPod-Endpunkt.
**Zustand.** Je Lauf.
**Kosten.** GPU-Zeit; nicht gemessen.
**Mess-Status.** REFUTIERT als Produktpfad: das fcpa-Politiknetz dieser Familie erreichte −212 bb/100
(CLAUDE.md) und `04_solver.md:580` grenzt die ganze Deep-CFR-Familie ausdruecklich ab. `openspiel_leduc`
ist als METHODIK-Validierung UNGEMESSEN im Repo (kein abgelegter `nash_conv`). Der Imitations-Deckel ist
die zusammenfassende Lehre: ein kleines Modell auf unseren Daten zu TRAINIEREN kann uns nicht uebertreffen.
**Allein benutzbar?** `openspiel_leduc` ja (es haengt nur an OpenSpiel und ist ein sauberer
Konvergenz-Test). Der Rest ist projektverwoben.
**Fallstricke.** Diese Module sehen aus wie ein Weg nach vorn und sind es nachweislich nicht. Wer sie
uebernimmt, sollte zuerst `04_solver.md:580` und den −212-Befund lesen.

### Wissens- und Formel-Werkzeuge (Gruppe) — `research/{consolidate_exploit,postflop_calc_gate,postflop_calc_materialize,experiment10,md_to_pdf,pdf_peek,peek_pb}.py`
**Zweck.** Sieben kleine Werkzeuge: Exploit-Primitive zusammenfuehren, LLM-erzeugte Postflop-Rechnungen
gegen die Engine gattern und materialisieren, eine inszenierte Trainer-Session, ein Markdown-nach-PDF-
Renderer und zwei Datei-Gucker.
**Schnittstelle.** `consolidate_exploit` (65 Z.) dedupliziert und normalisiert die buchextrahierten
Exploit-Primitive zu EINER Datenbank, verschluesselt nach den MESSBAREN Gegner-Statistiken des Bots ->
`knowledge_base/exploit/unified.json`. `postflop_calc_gate` (77 Z.) ist der EV-Wahrheitsfilter fuer reine
Mathematik: fuer jede Spezifikation wird `python_function` ausgefuehrt, `verify_expr` ausgewertet, und nur
Bestehendes bleibt. `postflop_calc_materialize` (63 Z.) giesst die verifizierten Rechnungen in EIN
importierbares Modul `knowledge_base/math/postflop_formulas.py` und verifiziert danach ALLE GEMEINSAM
(faengt Namenskollisionen, die die Einzelpruefung nicht sieht). `experiment10` (92 Z.) ist eine inszenierte
Trainer-Session. `md_to_pdf` (96 Z.) rendert einfaches Markdown nach A4-PDF (deutschsicher: Helvetica/
WinAnsi deckt Umlaute, ß, Geviertstrich, typografische Anfuehrungszeichen). `pdf_peek` (36 Z.) zieht einen
Seitenbereich als Text; `peek_pb` (9 Z.) laedt PokerBench-Train und zeigt drei echte Preflop-Zeilen.
**Eingabe/Ausgabe.** JSON-Spezifikationen, Markdown, PDFs.
**Abhaengigkeiten.** Weitgehend eigenstaendig; `postflop_calc_*` braucht die Formelsammlung.
**Zustand.** Zustandslos.
**Kosten.** Vernachlaessigbar; nicht gemessen.
**Mess-Status.** GEMESSEN POSITIV fuer `consolidate_exploit` als Verdichtung: 262 Exploit-Primitive plus
95 AGT-Konzepte aus fuenf Buechern, dedupliziert auf 62 stat-verschluesselte, verdrahtbare Regeln
(`docs/STATE.md:1745-1747`). Die uebrigen: UNGEMESSEN.
**Allein benutzbar?** `md_to_pdf` und `pdf_peek` sofort und ohne Projektbezug. `postflop_calc_gate` ist als
MUSTER wertvoll: LLM-Vorschlag -> ausfuehren -> Zusicherung pruefen -> nur Bestehendes behalten.
**Fallstricke.** `postflop_calc_materialize` verifiziert bewusst ZWEIMAL (einzeln beim Gattern, gemeinsam
beim Materialisieren) — wer den zweiten Durchlauf weglaesst, faengt Namenskollisionen nicht.

### Frontier-Konsulte (Tabelle) — `research/*_consult.py` und Verwandte
Vierzig Einmal-Skripte nach EINEM Muster: eine (oder wenige) LLM-Abfragen mit einer festen, im Docstring
stehenden Frage; Ergebnis als Markdown oder JSON nach `knowledge_base/` bzw. `docs/`. Sie haben KEINE
importierbare Schnittstelle ausser `main()`, sind zustandslos, kosten API-Guthaben und sind als Hebel
durchweg UNGEMESSEN — was sie liefern, ist ein GEGATETER PRIOR, nie ein Trainingslabel (CLAUDE.md:
"the engine is TRUTH, the frontier a GATED PRIOR"). Der Fallstrick ist derselbe fuer alle vierzig: die
Antworten stehen als Prosa im Repo und LESEN sich wie Befunde; das Muster mit dem Gatter ist in
`12_wissen.md` an `research/konsult_sol.py` beschrieben, und `research/perplexity_search.py` traegt die
harte Warnung des Projekts (CLAUDE.md: Perplexity verwuerfelt Metadaten — NIE unverifiziert zitieren).

| Pfad | eine Zeile |
|---|---|
| `research/alpha_consult.py` | Frontier-Abfrage zur Alpha-/Bluff-Frequenz-Theorie. |
| `research/cfr_papers_consult.py` | Welche CFR-Papers sind fuer uns relevant. |
| `research/cfr_tips.py` | Praktische CFR-Implementierungshinweise. |
| `research/exploit_gto_bridge.py` | Bruecke zwischen Exploit-Regeln und GTO-Basis. |
| `research/exploit_synthesis.py` | Synthese der Exploit-Primitive aus den Buechern. |
| `research/gto_frontier_consult.py` | Stand der GTO-Forschungsfront. |
| `research/gto_hybrid.py` | Hybrid aus GTO-Boden und Exploit-Overlay. |
| `research/gto_shortcut.py` | Gibt es Abkuerzungen zu GTO-Qualitaet. |
| `research/grand_synthesis.py` | Gesamtsynthese aller extrahierten Wissensquellen. |
| `research/hard_spots_consult.py` | Zweitmeinung zu den haertesten Spots. |
| `research/landscape_consult.py` | Landkarte der Poker-KI-Landschaft. |
| `research/math_theory_consult.py` | Mathematische Theorie-Rueckfragen. |
| `research/mathematics_of_poker.py` | Gezielte Extraktion aus *The Mathematics of Poker*. |
| `research/nash_consult.py` | Nash-Gleichgewichts-Fragen fuer 6-max. |
| `research/nash_keyword_consult.py` | Stichwortgetriebene Nash-Literaturabfrage. |
| `research/nextrun_consult.py` | Was als Naechstes laufen sollte. |
| `research/orchestrate_consult.py` | Orchestrierung der Zwei-Knoten-Pipeline. |
| `research/phase1_consult.py` | Planungsabfrage zu Phase 1. |
| `research/phase5_math_check.py` | Mathematik-Gegenpruefung fuer Phase 5. |
| `research/poker_for_compute.py` | Wo Rechenzeit im Poker am meisten bringt. |
| `research/postflop_calc_consult.py` | Erzeugt die Postflop-Rechnungs-Spezifikationen (Gatter: `postflop_calc_gate`). |
| `research/postflop_openai.py` | Postflop-Strategie-Playbook per OpenAI. |
| `research/qwen_train_consult.py` | Trainingsrezept fuer Qwen. |
| `research/range_tracker_consult.py` | Entwurfsfragen zum Range-Tracker. |
| `research/river_consult.py` | River-System-Spezifikation (Quelle von `river_coherence`). |
| `research/rl_consult.py` | RL-Rezept und Belohnungsentwurf. |
| `research/runpod_gto_consult.py` | Pod-Einsatz fuer GTO-Rechnung. |
| `research/shortdeck_consult.py` | Short-Deck-Besonderheiten. |
| `research/simplify_consult.py` | Wo vereinfachen statt hinzufuegen. |
| `research/situational_consult.py` | Situative Spielfragen. |
| `research/solvability_proof_consult.py` | Ist 6-max loesbar (Ergebnis: PPAD-hart, siehe Memory). |
| `research/solvability_query.py` | Kurzfassung derselben Frage. |
| `research/strategy_to_formula_consult.py` | Strategie-Text in Formeln uebersetzen. |
| `research/surfing_consult.py` | *Surfing Uncertainty* -> Value-of-Computation-Arbiter. |
| `research/synthesis_consult.py` | Synthese-Abfrage ueber mehrere Quellen. |
| `research/theory_qa.py` | Freie Theorie-Fragerunde. |
| `research/wso_consult.py` | Turnier-/WSO-bezogene Abfrage. |
| `research/math_audit.py` | OpenAI-Audit von `knowledge_base/math/formulas.py` (ehrlich als Review deklariert, nicht als Bestaetigung). |
| `research/fable5_bot_audit.py` | Audit des Bots durch die fablize-Disziplin-Linse. |
| `research/perplexity_search.py` | Suchgestuetzte Recherche — Metadaten unzuverlaessig, nie unverifiziert zitieren. |
| `research/venice_models.py` | Listet Venice.ai-Modelle (Schluessel bleibt aus der Ausgabe). |
| `research/probe_apis.py` | Prueft beide API-Schluessel und loest das beste OpenAI-Modell auf. |

---

## J — Korrekturen an den Teilen 01–12

Diese Punkte stehen hier, weil ein fremder Entwickler sonst zwei sich widersprechende Aussagen liest.

1. **`research/k3_roots.py` traegt in `04_solver.md:473` eine fremde Note.** Der Sammel-Eintrag vergibt an
   `river_br_pruefstand`, `policy_oracle` UND `k3_roots` gemeinsam "GEMESSEN POSITIV … Kontrollen 15/15
   gruen". Die Kontrollen gehoeren zu Pruefstand und Oracle. `06_v10.md:466` ist fuer dasselbe Modul richtig:
   UNGEMESSEN (Datenaufbereitung).
2. **Vier Module haben in zwei Teilen gegensaetzliche Mess-Etiketten** (inhaltlich aufloesbar, gedruckt
   widerspruechlich): `pokerbot/arena/sixmax.py` (03 UNGEMESSEN als isolierter Hebel / 09 GEMESSEN POSITIV
   85,9% GTO-Score, EV-Loss 7,61), `pokerbot/autogym/stats.py` (05 GEMESSEN POSITIV als Korrektur / 07
   UNGEMESSEN als eigenstaendiger Hebel), `research/golden_set.py` (06 als Werkzeug bestanden / 12
   UNGEMESSEN als Zahl), `research/mass_solve.py` (04 UNGEMESSEN als EV-Hebel / 12 GEMESSEN NEGATIV als
   Trainingsgold). Richtig ist jeweils BEIDES, aber nur mit dem Zusatz "als was".
3. **Namenskollision `mass_solve`.** Teil 12 schreibt die 25.586 ausgeschlossenen `solver_mass`-Zeilen
   `research/mass_solve.py` zu; erzeugt wurden sie laut demselben Kapitel von
   `dataset/build/from_solver.mass_solve(...)`. Zwei verschiedene Dinge mit gleichem Namen — beim Nachbauen
   trennen.
4. **Zwei Zeilenangaben ueberschiessen das Dateiende** (Inhalt stimmt jeweils): `04_solver.md:68/:237/:375`
   verweist auf `NOTES.md:712-726`, `NOTES.md` hat 724 Zeilen; `07_messung.md:65` verweist auf
   `stats.py:93-110`, `pokerbot/autogym/stats.py` hat 109 Zeilen (beides heute nachgezaehlt).
5. **Der Cache-Umfang ist ein Schnappschuss, kein Festwert.** Teil 04 nennt fuer `data/_solve_cache`
   12.209 Eintraege / 35 GB (gemessen 2026-09-10); beim Schreiben dieses Nachtrags waren es 12.493 Dateien.
   Der Cache waechst bei jedem Lauf.
6. **Tote Startanweisungen in den Docstrings.** 86 Module in `research/` und `infra/` tragen im Docstring
   `python -m extraction.<modul>`. Das Paket `extraction/` existiert nicht mehr (heute `research/`). Jede
   dieser Zeilen ist eine falsche Anleitung — alle in diesem Nachtrag genannten Startbefehle wurden auf
   `research.`/`infra.` korrigiert. Betroffen sind unter anderem `infra/runpod_run.py`,
   `research/preflop_solve.py`, `research/build_*_data.py`, `research/pdf_peek.py`.
7. **Fehlender Querverweis.** `04_solver.md:580` grenzt `deep_cfr.py`, `deep_cfr_hunl.py` und
   `deepstack_leduc.py` korrekt ab, verweist aber nicht auf `pokerbot/valuenet/gate0_leduc.py`, das
   `deep_cfr.py` als Fundament BENUTZT (`State`, `vanilla_cfr`, `exploitability`).

---

## K — Zu Recht fehlend (nur Tabelle)

| Pfad | eine Zeile | Grund |
|---|---|---|
| `pokerbot/__init__.py` | Paket-Docstring mit Unterpaket-Uebersicht, `__version__ = "0.1.0"` (11 Z.). | Trivial, kein Verhalten. |
| `pokerbot/coach/__init__.py` | Re-Export von `Coach`, in `try/except` gekapselt, damit die Trainer-Module ohne installiertes `anthropic` importierbar bleiben (11 Z.). | Trivial; die eine nicht-offensichtliche Zeile ist der Import-Guard. |
| `pokerbot/autogym/__init__.py` | Docstring mit der Vier-Teile-Aufteilung des Autogym + Einstieg `python -m pokerbot.autogym.run_local` (10 Z.). | Trivial. |
| `pokerbot/valuenet/__init__.py` | 0 Bytes. | Reiner Paket-Marker. |
| weitere 12 `__init__.py` | 0–1 Zeilen. | Reine Paket-Marker. |
| `pokerbot/benchmark/{beat_them_all,calibrate,exploit_proof,floor_ablate,floor_map,gto_benchmark,pluribus_leaks,preflop_ab,range_tracker_ab,sixmax_gap,probe,weaponize,runpod_train}.py` | 13 Benchmark-Treiber. | Bewusst als Tabelle in `08_benchmarks.md:738` gefuehrt; Verzeichnis damit vollstaendig (17 Voll-Eintraege + 13 Zeilen). |
| `research/{claude_brain_smoke,claude_export,claude_vs_engine,glm_local_probe,teacher_generate}.py`, `infra/gtow_glm_pod.py`, `research/llm.py`, `pokerbot/strategy/postflop_corset.py` | 8 Wegweiser der Brain-Spur. | Deklariert in `11_brain.md:608`; `postflop_corset` ist GEMESSEN NO-OP. |
| `research/{gtow_nacht,gtow_nacht_v10,gtow_ab,gtow_xray,gtow_tail,analyze_gtow_hands}.py` | 6 GTOW-Treiber. | Deklariert in `08_benchmarks.md:759` — ohne unseren Forscherzugang und unser Hand-Budget wertlos. |
| alle 12 `dataset/build/*.py` | Die Konverter Wissen -> DSL. | Vollstaendig ueber den Sammel-Eintrag `12_wissen.md:330` abgedeckt, je mit `build()`-Signatur. |
| `pokerbot/strategy/{deep_cfr,deep_cfr_hunl,deepstack_leduc}.py` | 1.232 Zeilen Self-Play-/Netz-Lernpfad. | Ausdrueckliche Abgrenzung in `04_solver.md:580` (kein Re-Solving zur Entscheidungszeit); `deep_cfr.py` ist allerdings die harte Abhaengigkeit von `valuenet/gate0_leduc.py` (siehe Korrektur 7). |
| `research/{runde4,runde5,runde5b,g4_auswertung,g5_*}.py`, Extraktions-Pipeline, Exploit-Overlays, `analysis/*`, `coach/*` | Kampagnen- und Pipeline-Familien. | Ueber Gruppenueberschriften in den Teilen 05/07/10/12 abgedeckt. |
