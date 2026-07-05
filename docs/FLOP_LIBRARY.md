# FLOP-SOLVE-BIBLIOTHEK — Design (2026-07-05 Nacht; NOTES.md Queue #1, nach der v3.x-Ladder)

> Ziel: den Flop-Bleed (−6.4…−8.3 bb/100, X-Ray) angreifen, den das doppelt bestätigte Live-NO-GO
> (49/50 Timeouts @300s, `research/flop_feasibility.py`) dem Live-Resolver verwehrt — durch
> PRÄCOMPUTATION kanonischer Flops. Subsystem-Karte: 6-Agenten-Workflow 2026-07-05 (dieses Doc = Destillat).
> Status: **Design + Kalibrierungs-Pilot** (`research/flop_pilot.py` → `data/research_sweep/flop_pilot.json`).
> NICHTS hiervon ist geshippt; `POKERB_RSV_FLOP` existiert noch nicht als Code.

## Architektur-Entscheidungen (aus der Karte abgeleitet)
1. **Die Bibliothek IST der (ISO-)Solve-Cache, vorgewärmt.** `gto_oracle.solve()` prüft den Cache vor
   jedem Solve; ein Präcompute, dessen SHA1-Key byte-identisch mit dem Live-Aufruf ist, macht den
   Live-Flop-Resolve zum ~0s-Lookup. Kein neues Speichersystem, kein neuer Lookup-Pfad.
2. **DIE kritische Naht = Key-Match.** Der Key hasht board|oop|ip|pot|eff|bets|acc|iters|dump|mode.
   Das Präcompute MUSS deshalb durch den LIVE-Pfad erzeugen: Preflop-Linie durch den `RangeTracker`
   spielen → `emit()`-Strings verwenden (nicht "äquivalente" Ranges von Hand bauen). Flop-Entry-Ranges
   sind reine Funktionen der Preflop-Linie (Blueprint-Perzentilbänder: SRP=(0.66,0.84), 3bet=(0.06,0.34),
   limped=(0.85,0.85)) → endlich aufzählbar. Census-Preflop-Sizes (GTOW_SIZES) fixieren pot/eff pro Linie
   (SRP: pot=450, eff=19775).
3. **ISO-Keying an:** `isomorph.canonical_board()` (lex-min über 24 Suit-Permutationen) → 1755 kanonische
   Flops statt 22.100; Konsument remappt Hero-Hole via suit_map (Muster existiert: resolver.py:233/271).
4. **dump_rounds=1** (nur Flop-Street-Strategie im Dump): die Turn/River-Entscheidungen übernimmt der
   existierende Turn/River-Resolver; der Dump bleibt klein (~MB statt ~100MB), der SOLVE rechnet intern
   trotzdem flop→terminal.
5. **Priorisierung nach Frequenz:** freq_targets (26.8k Entscheidungen): Top-15 Buckets = 42.4%, Top-~50 =
   85% Abdeckung. Reihenfolge: SRP-Entry zuerst (dominant, 1335 obs), dann 3bet; limped/4bet+ Rest.
   Off-Library-Spots → unveränderter Floor-Fallback (heutiges Verhalten, kein Regressionsrisiko).
6. **Menü:** Census-Modal-Arme (Flop 35, sekundär 75; Turn 75; River 65) — die 1.6x+-Tails sind n<5-Rauschen
   und blähen nur den Baum (Census-Agent). Minimal- vs. Lean-Baum entscheidet der Pilot.
7. **uint8-Quantisierung (Compact CFR) = Stufe 2**, nur falls RAM-Preload nötig wird — Disk-JSON zuerst
   (Cache ist heute disk-backed und zeit-, nicht RAM-gebunden).

## Der Pilot (läuft) — die eine fehlende Zahl
`flop_pilot.py`: 4 Textur-Repräsentanten × {minimal, lean}-Baum, 30 min/Solve-Cap, acc/iters identisch
zum Feasibility-Gate. Er beantwortet: **Was kostet EIN konvergierter flop→terminal-Solve bei 200bb?**
Daraus: Bibliotheks-Budget = Kosten × Ziel-Abdeckung → lokal-über-Nächte vs. CPU-Pod ($2.24/h-Klasse).
(Der bwfga5qs2-Minimal-Menü-Retest der Alt-Session hat sein Ergebnis nie persistiert — der Pilot ersetzt ihn.)

## ★ Kritiker-Panel-Auflagen (2026-07-05 Nacht, 3-Agenten-Adversarial-Review — BINDEND fürs Design)
Rohdaten: `data/research_sweep/strategy_critic_panel.json`. Die architektur-relevanten Verdikte:
1. **Staleness-Detektion ist Pflicht (BLOCKER):** ein Miss ist sonst von "uncovered" ununterscheidbar →
   stiller Floor-Fallback → der Analyzer-Arm "widerlegt" eine Bibliothek, die nie gefeuert hat. Fix:
   (a) **Manifest** `data/flop_library/manifest.json` = Key-Set + Build-Fingerprint (Emit-Code-Version,
   Blueprint-Bänder, GTOW_SIZES-pot/eff, Menü, ISO-Status, allin_threshold, acc/iters); (b) Konsument
   validiert den Fingerprint beim Start und failt LAUT; (c) Hit/Miss-Zähler im Run-Log, erwartete Hit-Rate
   PRE-REGISTRIERT — Shortfall bricht den Arm ab als kaputte Messung, nicht als widerlegten Hebel.
2. **Reihenfolge (BLOCKER):** P1-Promotions (v3.3 ändert `range_tracker.update`, v3.5 die Advisor-Abfrage)
   ändern die emit()-Strings → invalidieren JEDEN vorberechneten Key. **Erst Profil einfrieren, DANN durch
   den eingefrorenen Emit-Pfad bauen** (Profil-Fingerprint ins Manifest). Falls früher gerechnet werden
   muss: nur Solver-Dumps (Board × Line) vorziehen, Keys nach dem Freeze billig nachberechnen.
3. **Query-seitige Kanonisierung:** der Konsument nutzt das FIXE Census-Menü und SNAPPT beobachtete
   Size/pot/eff auf die Bibliotheks-Arme VOR der Key-Berechnung (S3-Snap-Konzept) — sonst erzeugt jede
   Off-Census-Size einen unikalen SHA1 und Präcompute ist per Konstruktion unmöglich.
4. **ISO-Kopplung:** Bibliotheks-Keys sind kanonisch, live ist `POKERB_ISO_CACHE` default-OFF → ohne Fix
   treffen nur ~1/24 der Boards. Konsument erzwingt kanonisches Keying für Flop-Lookups unabhängig vom
   globalen Flag. ACHTUNG: ISO_CACHE=1 global ist selbst eine Live-Verhaltensänderung (re-keyt Turn/River →
   100% Miss auf dem Warm-Cache → Cold-Solve-Verhalten) → der Analyzer-Arm läuft mit der VOLLEN
   Konsum-Umgebung; beide Flags sind seit heute in `_FINGERPRINT_KEYS`.
5. **Lookup-only-API:** bei Miss NIE in den Solve-Pfad (das NO-GO kostet Sekunden–Minuten Wall-Clock) —
   Key-Existenz gegen das Manifest-Set im RAM (plain `set`, KEIN Bloom-Filter — Key-Zahl ≤ Zehntausende),
   Floor-Fallback in ~0ms.
6. **Versionierter Key, eigenes Verzeichnis:** `data/flop_library/` mit KEY_VERSION + allin_threshold im
   Key-Blob (der 12GB-Warm-Cache bleibt unberührt = die Stundungs-Begründung überlebt). Präcompute-Treiber:
   idempotent + checkpointed (skip-if-key-exists; das Persist-nach-jedem-Solve-Muster des Piloten).
7. **GO-Gate vor jedem Arm ($0, deterministisch):** Offline-Replay der 13.5k gelogtem GTOW-Hände durch den
   eingefrorenen Emit-Pfad → EXAKTE erwartete Hit-Rate (die 85% sind Bucket-, nicht Key-Level!) + der
   Round-Trip-Test (permutiertes Board → Cache-HIT; das ISO-Beweis-Muster).
8. **Serialisierung (BLOCKER, generalisiert):** KEIN Batch-Solve-Job während IRGENDEINER Live-Messung
   (CPU-CPU-Version der CLAUDE.md-Regel; Timeout→Floor-Fallback macht Contention zur stillen
   Policy-Änderung). Pilot/Precompute vor Smoke/Anker beenden. Anker-Arm zuerst laufen lassen (wärmt den
   geteilten Cache → Determinismus-Verbündeter für die Folge-Arme).
9. **Pilot-Selbstkontamination:** Re-Runs des Piloten nur mit `POKERB_SOLVE_CACHE=0` (sonst sind Timings
   ~0s-Cache-Hits und das Bibliotheks-Budget beruht auf Müll). Der Lauf von heute Nacht ist cold=valide.
10. **Cross-Street-Naht (dump_rounds=1) = akzeptiert, second-order:** die Naht existiert heute schon
   (Floor-Flop + Turn-Resolver); Bedingung: interne Turn/River-Menüs der Bibliothek == Live-Resolver-Menüs
   (`_TURN_BETS`/`_RIVER_BETS` vor dem Build abgleichen). Bewusst NICHT gebaut: Bloom-Filter, uint8 vor
   RAM-Not — Overengineering-Verzicht ist Teil des Designs.

## Gate-Leiter (wie immer, vor jedem Ship)
Flag `POKERB_RSV_FLOP` default-OFF → byte-identisch OFF (Harness) → stress 70 Spots → replay_graded →
Coverage-GO-Gate (#7) → eigener Analyzer-Arm mit VOLLER Konsum-Env (frischer Anker!) → ggf. live tail-smoke.
Ein Hebel, ein Arm.

## Synergien (mitnehmen, nicht jetzt bauen)
- **EVPA-Korpus:** jeder Bibliotheks-Solve liefert (Spot, Hand, Line)→Strategie/Wert-Labels; Dumps tragen
  `_exploitability_pct`/`_solve_iters`; CFV-Ableitung via Backward-Pass (cfv_eval-Maschinerie, B1-validiert).
- **TurboReBeL-Ideen** (verifiziert, rejected — Ledger): Iso-Augmentation nutzt denselben `isomorph.py`;
  SSMIG erst im eigenen v4-CFR-Kern (TexasSolver exponiert keine Per-Iteration-Dumps).
- **Allin-Threshold-Schuld:** `_cache_key` trägt `allin_threshold` (0.67 hardcoded) NICHT — beim nächsten
  geplanten Cache-Flush aufnehmen (NOTES/Audit), NICHT jetzt (invalidiert 12GB Warm-Cache).
