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

## Gate-Leiter (wie immer, vor jedem Ship)
Flag `POKERB_RSV_FLOP` default-OFF → byte-identisch OFF (Harness) → stress 70 Spots → replay_graded →
eigener Analyzer-Arm (frischer Anker!) → ggf. live tail-smoke. Ein Hebel, ein Arm.

## Synergien (mitnehmen, nicht jetzt bauen)
- **EVPA-Korpus:** jeder Bibliotheks-Solve liefert (Spot, Hand, Line)→Strategie/Wert-Labels; Dumps tragen
  `_exploitability_pct`/`_solve_iters`; CFV-Ableitung via Backward-Pass (cfv_eval-Maschinerie, B1-validiert).
- **TurboReBeL-Ideen** (verifiziert, rejected — Ledger): Iso-Augmentation nutzt denselben `isomorph.py`;
  SSMIG erst im eigenen v4-CFR-Kern (TexasSolver exponiert keine Per-Iteration-Dumps).
- **Allin-Threshold-Schuld:** `_cache_key` trägt `allin_threshold` (0.67 hardcoded) NICHT — beim nächsten
  geplanten Cache-Flush aufnehmen (NOTES/Audit), NICHT jetzt (invalidiert 12GB Warm-Cache).
