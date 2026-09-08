# V10 FAKTEN — konsolidierte Scout-Befunde (Integrator, 2026-09-07)

Reine Faktensicherung zur Build-Karte `docs/V10_BUILD_CARD.md`. Fuenf Scouts (bot / engine / harness /
tracker / gpu / pargate), vom Integrator gegen den Quelltext nachgeprueft (Stichproben: `game.py:97-181,
290-307`, `gtowizard.py:36-82,126-148`, `pargate.py:18-37`, `gpu_cfr.py:37-53`, `gpu_resolver.py:26-36`,
`bot.py:545-556`, `auslese.py:20-62`, Existenzpruefung aller Zieldateien). Jede Aussage traegt `file:line`.
**Wichtigster Output = Abschnitt B (Widersprueche) und C (Entscheidungsbedarf).** Keine Zahl ohne Quelle.

Stand des Repos: Branch `poker-core`, HEAD `eabcef3`; Working Tree sauber bis auf die zwei ungetrackten
Karten-Dokumente (`docs/TOP5_KONSULT_GPT6_2026-09-07.md`, `docs/V10_BUILD_CARD.md`). Muenzwurf K5 liegt vor:
`data/runs/v10_muenze.json` = `BAAB_dann_ABBA` (2026-09-07 16:47:57). `data/runs/v10/` existiert leer.

---

## A. FAKTEN NACH THEMA

### A0. Existenz der Zieldateien / Registrierung
| Karte nennt | Befund | Quelle |
|---|---|---|
| `pokerbot/strategy/contracts.py` | FEHLTE — wird mit diesem Auftrag (P0b) angelegt | `test -e` 2026-09-07 |
| `pokerbot/strategy/hero_range.py` (K1) | FEHLT | dito |
| `pokerbot/autogym/river_plan.py` (K2) | FEHLT | dito |
| `research/policy_oracle.py`, `research/river_br_pruefstand.py` (K3) | FEHLEN | dito |
| `pokerbot/runtime_config.py` (K4) | FEHLT | dito |
| `research/gtow_nacht_v10.py` (K5) | FEHLT | dito |
| Stack `r10_stack` | NICHT registriert; vorhanden: `r8_stack`, `r9_play`, `r9_pre`, `r9_turn`, `r9_v8`, `r10_ernte` | `pokerbot/autogym/pargate.py:18-37` (KANDIDATEN), `:40-141` (`_wickle`) |
| `tests/` GPU-/CFR-/Resolver-Tests | KEINE; nur `__main__`-Selbsttests | `gpu_cfr.py:667-676`, `gpu_resolver.py:218-244`, `gpu_equity.py:161-169` |
| 40-Deck-Divergenz-Smoke / „Golden-Set" | KEIN Skript, KEIN Artefakt; nur Journal-Satz „0,88s/Deck, 4/40 Divergenzen" | `data/autogym/journal.jsonl` V9-VORREGISTRIERUNG 2026-09-01; `git show --stat a84473a` (nur 2 Dateien) |

### A1. Engine-Zustand (HeadsUpGame) — das Gym-/pargate-Format
- `act()`: Betrag = **Raise-TO-Level der Strasse** (kumulativ), `int(amount)` trunkiert, dann **stiller Clamp**
  `max(raise_min, min(target, raise_max))`; Exceptions nur bei check/call/bet ohne Erlaubnis, bet/raise ohne
  amount, unbekannter Aktion. **Fold bei to_call==0 ist erlaubt** (nicht geprueft). `game.py:141-181`
- Label `'bet'` iff `prev_bet==0`, sonst `'raise'`; **`'allin'` erscheint nie als History-Label** (Jam = bet/raise
  mit `to == committed_street+stack`). `game.py:178-181`
- History-Formen (5): fold/check `{player,action,street}`; call `{player,action:'call',amount:<gezahlt>,street}`;
  bet/raise `{player,action,to:<Level>,street}`; deal `{action:'deal',street,board:[gesamt]}` OHNE player.
  Kein preflop-deal, keine Blinds-Eintraege. Bei All-in-Run-out: **KEIN deal-Event** (silent). `game.py:143,151,
  158-159,179-181,217-221,239`
- `legal_actions()`: `to_act,to_call,can_fold(=can_call),can_check,can_call,call_amount,can_raise,is_bet,
  raise_min,raise_max,pot`; `can_raise = stack > to_call and not opp.all_in`; `raise_min` = bet: `committed+bb`,
  raise: `current_bet+min_raise` (min_raise NICHT im State). `game.py:97-128`
- `state()`: `hand_no,button,street,board,pot(=Σcommitted_total),current_bet,to_act,hand_over,result,sb,bb,
  history,players[{idx,name,stack,hole,folded,all_in,committed_street,committed_total,is_button}],legal`.
  **KEIN `hand_id`.** Ohne `hide=` sind BEIDE Hole-Karten sichtbar (Gym/duplicate rufen ohne hide). `game.py:
  290-307`; `gym_hu.py:35`; `duplicate.py:47`
- `hand_no` im Spiegel ist NICHT eindeutig: `_setup_fixed` setzt 0 bzw. 1 vor `start_hand` → immer 1 (Button 0)
  oder 2 (Button 1), fuer jedes Deck gleich. `duplicate.py:32-40`; `game.py:68-72`
- Engine-Default `starting_stack=10000` (`game.py:31`), aber ALLE Messkanaele 20000/50/100: `gym_hu.py:69-72`,
  `duplicate.py:55-58,76-78`, `pargate.py:168-171`, `orakel_duell.py:41`, GTOW `gtowizard.py:89-91,232-235`.

### A2. Adapter-Zustand (gtow_to_state) — der Live-Kanal
- History aus `_parse_history`: call OHNE `amount`; deal OHNE `board`; bet/raise mit `to` als **FLOAT**; preflop-
  Aggression immer `'raise'`; deal-Events auch bei All-in-Run-outs. `gtowizard.py:38-82`
- Top-Level: `street,board,pot(=total_pot),bb,current_bet,button,hand_id(GTOW),hand_no:0,history,to_act:0,
  hand_over,players[hole Villain '??',stack,committed_street,committed_total=start-stack,folded,all_in,
  is_button],legal(raise_range-Clamp separat)`. Kein `sb`, kein `result`. `gtowizard.py:126-148,150-174`
- **Schnittmenge beider Kanaele** (nur darauf duerfen K1/K2 bauen): `player, action, street, to` (bet/raise) +
  `deal.street`; Board aus `state['board']`; Call-Increment aus Level-Differenz. Konsumenten pruefen heute nur
  `action=='deal'`/`street`: `bot.py:500-519`, `range_tracker.py:314`, `resolver.py:191`.

### A3. Bot — RNG, Gatter, Resolver-Vorrang, versteckter Zustand
- EIN Instanz-RNG `self.rng = random.Random(seed)`; kein globales `random`. Seeds: GTOW `seed=7` (EINE Instanz
  fuer 5-8 parallele Haende → Ziehungsreihenfolge interleaving-abhaengig, nicht reproduzierbar); HU-App
  `seed=None`; gym `seed/seed+1`; duplicate/pargate beide Sitze `seed`. `bot.py:139-141`; `gtowizard.py:183-194`;
  `server.py:37,44`; `gym_hu.py:22-26,73`; `duplicate.py:101-110`; `pargate.py:144-147`
- Praezedenz Per-Spot-Reseeding ohne globale Nebenwirkung: `coach/oracle.py:185-188` (`bot.rng = Random(spot_fp)`).
- Zufallsverbrauch: Flop/Turn MC-Equity 1500 Iter (`bot.py:33,566,569`; `equity.py:65-68,107-110`); **River
  exakt (kein RNG)** (`equity.py:52-61,92-101`). Gatter mit `rng.random()/choices`: preflop `bot.py:216-231,303,
  335-342,356,391,410,446,466,486-491`; postflop `621,753,783,812,851,870,897,909,921,927,1174,1195`.
- **LINE_U (PRINCE=1): EINE Ziehung pro Hand im Preflop-Aufruf** → `_hand_u` / `_hand_u_by_id[hand_id]`; die
  Advisor-Gatter Flop/Turn/River nutzen diesen Wert (`bot.py:216-231,486-491,783,812,851`). Ein isolierter
  River-decide ohne Preflop-Aufruf spielt mit `u=0.5` (Default = faktisch Purify) oder fremdem u. `bot.py:144-149`
- Weitere Instanz-Attribute (nicht reentrant): `_cur_street/_cur_committed/_cur_state/_cur_hole/_cur_board/
  _ecall_exact_to`, `self.opp`, `_probe_spent_bb`, `_river_keys`. `bot.py:210-212,534-536,1265-1266`
- **Resolver-Vorrang:** `street=='river' and self.use_resolver` → `_river_resolve`; bei Ergebnis `return` VOR
  allen Gattern/Levern/Slowplay/eCall — er ERSETZT die Basis, ist kein Eingriff. Fallback (None) nur bei: kein
  Raise/Call moeglich, Tracker-Konfidenz `<0.5`, leere Range-Strings, Exception/Timeout, Baum-Navigation
  scheitert, **Hero-Hand nicht in Range** (`strategy_for` None), Σprobs<=0. Feuerte 93 % der River-Entscheidungen.
  `bot.py:545-556,1037-1062`; `resolver.py:232-266`; `range_tracker.py:59`; `docs/STATE.md:1000`
- Resolver sampelt `rng.choices(labels, weights=probs)`; die exakte Verteilung `strat` (`resolver.py:257`) wird
  NICHT zurueckgegeben. TexasSolver-Timeouts: Census (PRINCE) River 90 s/Turn 150 s/Flop 240 s; kompakt 40/60/120 s;
  `subprocess.run(timeout)` → `TimeoutExpired` von `except Exception` gefangen → None → Floor **nach** Ablauf.
  `resolver.py:18-38,81-82,117,238-246`; `gto_oracle.py:126-127`. Latenz ~6 s/River-Entscheidung (Median 5,8 s);
  resolver-OFF 83 ms (`docs/STATE.md:1000`; Commit 57b9807).
- Disk-Solve-Cache (default AN): Key = sha1(board, ranges, pot, eff, bets, acc, iters, dump, mode) — OHNE Hole,
  OHNE History direkt → ein Solve je Knoten fuer alle Combos/Seeds. `gto_oracle.py:44-62,92-101,148-158`
- **`POKERB_RESOLVER` wird von bot.py NICHT gelesen**; Attribute `use_resolver=False`, `use_turn_resolver=False`
  default; nur `gtowizard.py:187-196` liest die Env (default AN, **Turn-Resolver ebenfalls AN**). HU-App/gym/
  duplicate/pargate: AUS. `bot.py:185-190`; `server.py:37`; `replay_graded.py:323-324`; `stress_suite.py:81`
- Mischverteilung exponiert? NEIN (keine Funktion). Teil-Exposition im rationale: `advisor_pbet*`,
  `defense_advisor:[p_fold,p_call,p_raise]`, `blueprint.dist`, deepcfr `probs`. Nicht: Resolver-`strat`,
  Heuristik-Frequenzen (f_cbet/bf/donk nur als Text), LINE_U-u. `bot.py:249-250,361-362,614-615,781,809,848,1060-1062`
- `exploit=False` (PRINCE→GTO_MODE→`POKERB_EXPLOIT=0`): conf=0 → MDF-Shade 0, Exploit-Term 0, `_river_exploit/
  _river_probe` uebersprungen, Bluff-Raise-Zweig tot; bot.py kann exploit nur AUS-schalten. `bot.py:151-155,436,
  573-576,583,655-657,721-729,761-764`; `gto_mode.py:14,19`; `postflop.py:151-161`
- PRINCE-Flags sind **Import-Zeit-Konstanten** (`bot.py:36-108`; `postflop.py:27,35,44,148`; `advisor.py:28`;
  `resolver.py:18,31,117`; `range_tracker.py:71,79`) → Env MUSS vor dem ersten `pokerbot.strategy.*`-Import stehen;
  `gtowizard.py:23-27` ruft `apply()` vor dem lazy Bot-Import. Prioritaet: Env > PRINCE_PROFILE > PROFILE > Default
  (`gto_mode.py:12-31,44-54,102-137`).
- Hero-Hole als Dead Cards: `_tracked_villain_range` filtert Villain um Hero-Hole+Board; `_tracked_ranges_both`
  filtert Hero NUR um das Board (bereits oeffentlich). `bot.py:967-969,989-990,1010-1012`
- `decide()` ist NICHT memoisiert; der 12,1x-Speedup memoisiert `advisor.p_bet/p_defense` (Key hole/board/role/
  street/pot_type bzw. size_faced), `features._FEATURES_MEMO`, `evaluator._EVAL_MEMO`; Wholesale-Clear bei
  120k/60k (kein LRU). `advisor.py:82-97,185-199`; `features.py:36-68`; `evaluator.py:17-38`
- RangeTracker wird bis zu 3x pro River-decide neu gebaut (`bot.py:987,1003,1050`); `build()` liest nur history/
  board/button/bb/stacks+committed_total — **keine Hole Cards** (`range_tracker.py:294-350,397-409`).
- Auslese-Wrapper: `wickle_decide(pb, stack)` legt `_wickle`-Kette um `pb.decide`; Guards sehen die Basis NUR als
  `(action, amount)`; bei Abweichung `auslese_guard: True` ins rationale — kein Stufen-Trace. `auslese.py:39-62`;
  `pargate.py:40-47`. Wenn der TexasSolver feuert, ist die „Basis" fuer alle Guards die Resolver-Aktion.

### A4. RangeTracker + Advisor (K1-Backend)
- Preflop-Prior = KLASSEN-Menge nach Raise-ANZAHL (0/1/2+) und Button: `>=2` → `range_top(0.18)` beide; `==1` →
  Button `sb_open()`, Nicht-Button `bb_defend()`; `0` → `range_top(0.85)`; Combos ohne Dead-Cards, Gewicht 1.0.
  Preflop-Zeilen werden im Walk UEBERSPRUNGEN → Preflop-Aktionen (auch Hero) veraendern die Range nicht.
  `range_tracker.py:32-42,131-138,337-338`
- Walk: deal setzt `cur_street`, `_remove_dead(board[:3/4/5])`; Commitment-Buchhaltung fuer Jam-Read (`jam` wenn
  `committed+inc >= start_stack-1`); `facing = street_bet>0`; Rolle = POSITION (`'IP'` iff seat==button);
  fold kein Update; ganzer Walk in try/except (Teilergebnis bleibt). `range_tracker.py:105-107,179-180,294-352`
- `_update_action`: bet&!facing → `d[c] *= p_bet**alpha` (alpha 1.0 bei AGGRO_FULL und aggro>=1, sonst
  TRACKER_ALPHA), gebatcht; check&!facing → `(1-p)**alpha`, Einzelaufrufe; call&facing → `P_call**alpha` mit
  **FESTEM size_faced=0.66**; raise/allin&facing → nur mit RAISE_NARROW modelliert, sonst `heur+=1` (legality-
  only). `_normalize` loescht `< 1e-6`. `range_tracker.py:163-177,182-197,208-267,269-292`
- Effektiv unter PRINCE (Sonde): ALPHA 0.5, AGGRO_FULL True, AUDIT_FIX False, RN 0.0, CONF_SLOPE 0.7 → erste Bet
  eines Sitzes ^0.5, ab der 2. ^1.0; Check/Call ^0.5; Raise zaehlt NICHT als aggro. `range_tracker.py:71-90,218,
  255-263`; `gto_mode.py:19-20,43,52,61`; `auslese.py:25-36`
- Advisor-API: `p_bet(hole,board,role,street,pot_type)->float|None` (memo 120k); `p_bet_batch(combos,...)->dict`
  (ein Forward-Pass; 13/17/27 ms je Voll-Range flop/turn/river vs 61-65 ms einzeln); `p_defense(hole,board,role,
  size_faced,street)->(P_fold,P_call,P_raise)`; **KEIN `p_defense_batch`** (68-70 ms je Voll-Range einzeln).
  Rolle `'IP'` case-sensitiv. `advisor.py:18-20,44-51,54-75,82-157,160-221`
- Feature-Vektor: tier(3)+Textur(5)+role-Bit+7 Bools+overcards/2+strength; p_defense + Street-One-Hot + size;
  **KEINE Range-/Pot-/SPR-/History-Information** (Karte korrekt). `advisor.py:44-51,101-114,203-221`; `features.py:57-106`
- Rollen-Konflikt: Tracker fragt POSITION; `decide()` fragt `p_bet` nach INITIATIVE (`_ADVISOR_ROLE_POS` default
  '0'; `_has_initiative` = letzter Preflop-Raiser) und `p_defense` nach Position. `range_tracker.py:179-180`;
  `bot.py:65-70,604,771-776,801-802,831-832,934-943`; Training: Baum-Position `research/build_advisor_data.py:33`
- Defense-Advisor in `decide()` NUR am Flop (`_def_streets=('flop',)` ohne TURN_DEF_ADVISOR) mit echter size und
  `self.rng`; Turn-/River-Calls aus MDF/Schwellen-Logik. `bot.py:600-603,622,636ff`
- Snapshot-API: KEINE. Einziger Mechanismus = History-Schnitt + Neubau (`improver.py:420-440` am River-Deal;
  `turn_gpu.py:100-110` am Turn-Deal). Kosten: 210 ms kalt / 7,2 ms warm (Sonde). Ein Schnitt `hist[:i]` liefert
  die Range VOR Aktion i nur, wenn die Deal-Zeile der Strasse enthalten ist.
- Modelle vorhanden: `knowledge_base/postflop/{advisor,turn_advisor,river_advisor,defense_advisor,river_advisor_la}.pt`.
- Postflop-Haeufigkeiten (65 HH-Dateien, 24.050 Haende, beide Sitze): bet 27,5 %, check 56,3 %, call 13,3 %,
  raise-facing-bet 2,9 % (→ heur-Anteil im Live-Stack); `tests/test_range_tracker.py:89-116` gruen.
- Identitaets-Wache `research/advisor_batch_check.py:24` ruft Rollen kleingeschrieben (`'ip'/'oop'`) → Rollen-Bit
  in beiden Armen 0; IP-Pfad NICHT abgedeckt (Beweis-Luecke, kein Produktfehler).

### A5. Bestehende Guards (Vorlage fuer K1-Transformationen und K2)
- `turn_wert_guard(frac=0.66,min_eq=0.60,iters=160)`: Trigger check & to_call==0 & turn & Stacks>0; Klasse via
  treys (`kl<=6` oder `kl==7 & beteiligt` oder Ueberpaar); Tracker auf VOLLEM State (kein Schnitt);
  **MC-Equity iters=160 mit `_spot_rng(st)`, dessen Seed die HERO-HOLE enthaelt** → `('bet', int(0.66*pot))`.
  `improver.py:38,41-53,230-278`; `equity.py:79-117`
- `sel_guard(margin=0.15)` = `sel_m15`: fold & to_call>0 & flop; MC-Equity iters=160 `>= equity_needed_to_call +
  0.15` → call. `improver.py:119-153`; `pargate.py:60-61`
- `button_disziplin_guard`: fold & preflop & to_call==50 & committed==50 → `('raise',250)`; keine Handbedingung.
  `improver.py:600-616`
- `river_wert_bremse`: bet & to_call==0 & river & kl<=7 & exakte Equity `<0.50` → check (RNG-frei). `improver.py:
  318-333,377-410`
- `river_gpu_guard(min_pot_chips=3000,iters=150,p_max_basis=0.10,p_min_alt=0.70)`: gated `st['pot']>=3000` JE
  ENTSCHEIDUNG (aktueller Pot, nicht pot_river); `solve_spots([spot])` B=1 je Entscheidung; Override nur bei
  `p_basis<0.10 & p_alt>0.70`; **Bet-Size hardcodet `int(0.75*pot)`** trotz Kommentar; `except: pass` ohne Log.
  `improver.py:477-533`
- `river_play_guard(min_pot_chips=3000,iters=150,half=False)`: sampelt deterministisch `crc32('v8play|'+sorted
  (hole)|board|pot|current_bet|committed_street|len(history))/2^32` — **Hash ENTHAELT Hero-Hole**, kein
  private_seed/hand_id; Size `zus[wahl]/100*pot_river`, `int()`-Truncation, Jam bei `>= stack-1`, Legalitaets-
  gatter; keine Deadline; `except: pass`. `improver.py:535-604`. Registriert als `r9_play`; `r10_ernte` = mit
  `min_pot=1500, half=True` + `stackoff_bremse`. `pargate.py:109-112,133-140`
- `_river_spot_und_frage`: Schnitt am River-`deal`, `pot_river = st['pot'] − River-Einsaetze` (verifiziert 1400==
  1400; aequivalent exakt: `st['pot'] − Σ committed_street`), float; None ohne River-deal (silent runout).
  `improver.py:421-470`
- Kette (Wrapper-Reihenfolge, aeusserer sieht inneren): basis → sel_m15 → turn_wert → button → wert_bremse →
  river_gpu (`pargate.py:80-108`). Guards lesen Hero via `st['players'][st['to_act']]`, nicht `hero_idx`.

### A6. GPU-Solver (gpu_cfr / gpu_resolver)
- Combo-Index kanonisch: `itertools.combinations(range(52),2)` lexikographisch, Karte `rank*4+suit`, rank 0='2'..
  12='A', Suits `'shdc'`; `combo_index` sortiert. `gpu_cfr.py:37-44,441`; `gpu_eval.py:9,200-201`
- `range_vector({('As','Kd'):w})` → dichter float32 [1326]; **KEINE Normierung** (Docstring `gpu_cfr.py:167-168`
  behauptet es; Code `175-176,293-294` maskiert nur; skaleninvariant harmlos).
- `RiverCFRBatch(boards, r_oop, r_ip, pot, eff_stack, half=False, **baum_kw)`: Spieler 0 = OOP handelt zuerst;
  CFR+ (RM+, lineares Averaging, alternierend, KEIN RNG); `avg_sigma(node)` = Durchschnittsstrategie, **Combos mit
  Reach 0 erhalten UNIFORM 1/n** (Phantom-Falle). `gpu_cfr.py:276-343`
- Keine oeffentliche Dump-API; Weg: `node.acts/node.kids` rekursiv + `cfr.avg_sigma(node)[b]`; `_alle_knoten`
  privat; `strategy_at_root` nur auf `RiverCFR`. `gpu_cfr.py:157-163,263-265`
- `_br`: exakte BR je (Knoten, eigene Combo); Villain-Strategie nur ueber Villain-Combo indiziert → sieht Heros
  Hand nicht (korrekt). `gpu_cfr.py:345-360`. Terminals um `−pot0/2` zentriert, nullsummig. `gpu_cfr.py:309-316`
- `exploitability()` = `100*(BR_0+BR_1)/pot0` [B]; **KEIN Spielwert v\*, KEINE Klammer [L,U]** (ableitbar aus
  beiden `_br`). `gpu_cfr.py:362-372`. `action_values` = Q je Combo je Aktion (POT_NORM-Skala, nur Differenzen);
  **KEINE Indifferenz-Validierung im Repo** (`INDIFF_BB` in `tiefen_replay.py:47` ist nur Kategorienschwelle).
- `solve_spots(spots,iters=300,max_batch=192,mit_evs=False)`: **`_injiziere` IMMER auf der Hero-Seite** (kein
  Schalter; `HERO_MIN_GEWICHT=0.02`); Gruppierung nach SPR-Bucket (`spr<=1.25*b`), pot normiert 100, **eff_stack =
  Bucket, nicht echter Stack**. `gpu_resolver.py:26-36,64-70,148-215`; zweiter Aufrufer `turn_gpu.py:20,131`
- `_navigiere/_navigiere_mit_reach`: bet/raise-Sizes werden **STUMM auf den naechsten Arm gesnappt** (kein
  Toleranzfenster, kein Log); fehlender check/call-Arm, fold, Terminal → None. `gpu_resolver.py:73-145`
- `build_river_tree(pot,eff,bet_sizes=(0.35,0.75,1.5),raise_sizes=(2.7,),max_raises=2)`: Bets = Fraktion des
  AKTUELLEN Pots; **Raise-Zusatz = 2,7 x to_call** (nicht „raise to 2,7x"); Arme >=85 % rest kollabieren in Jam.
  `gpu_cfr.py:96-153`. Baumgroesse 9-99 Knoten je SPR-Bucket (Messung Scout).
- Latenz: Repo dokumentiert nur Durchsatz 0,30 s/Spot bei B=256 (`docs/STATE.md:26`); „~1-3 s" im Konsult ist
  Annahme (`TOP5_KONSULT…:2406-2407`). Scout-Messung heute (RTX 3080 Ti, B=1, fp32, 150 Iter, 400x400 Combos):
  SPR 1: 0,9-1,1 s; SPR 3: 2,0-2,55 s; SPR 7: 2,5 s reiner Solve; Setup 18-23 ms warm / 289 ms kalt. p99/Kaltstart
  end-to-end NICHT gemessen.
- Kein Cache, keine Deadline in gpu_cfr/gpu_resolver/improver. Determinismus: kein RNG; A/A exakt 0 bewiesen
  (r8_stack fp32 600 Decks, Journal R8-FINALE-LAUF1; r10_ernte fp16 576 Decks, `data/runs/20260901_114509_pargate_
  r10_ernte/result.json`), Bedingungen: OPENBLAS/OMP/MKL=1, `torch.set_num_threads(1)`, POKERB_*-Strip
  (`pargate.py:150-165`); `use_deterministic_algorithms/cudnn/TF32` nirgends gesetzt (Hardware-/Versions-gebunden).
- `gpu_equity.equity_vs_range_exakt(hero, villain_combos, board)` = EINE Hand vs Range [C], NaN fuer Blocker;
  KEINE 1326-Batch-Variante, KEINE gewichtete Variante, **kein Produktions-Aufrufer**; Verifikation mittelt
  ungewichtet. `gpu_equity.py:34-87,90-131`

### A7. pargate / duplicate — der Spiegel-Kanal
- `par_gate(kandidat,n_decks,workers,seed=1,deck_seed0=1000,incumbent)`: `n_jobs=workers*4`, `chunk=n_decks//
  n_jobs` → **600 Decks / 12 Worker = 576 Decks** (result.json n_decks 576). `pargate.py:186-215`
- Paarung = `duplicate_ab`: jedes Deck ZWEIMAL, **Button IMMER 0**, die Strategie wechselt den Sitz; `edge = x1−x2`;
  `bb100 = mean/2/bb*100`. `duplicate.py:32-73`. gym_hu (4er-Block Holes x Button) wird von pargate NICHT benutzt.
- Fabrik-Vertrag: `make_strat(seat) -> decide(st) -> (action, amount)`; `d(st)` nur bei `st['to_act']==seat`.
  `duplicate.py:8-9,46,101-115`
- **Gate-Kanal = exploit=ON, alle POKERB_*-Env gestrippt (kein PRINCE), Resolver AUS.** `pargate.py:144-147,
  152-159`; `bot.py:185`. Beide Instanzen im SELBEN Worker-Prozess mit demselben `--seed`; PYTHONHASHSEED wird von
  pargate NICHT gesetzt (nur envgate `envgate.py:145`). Env-Kanal = envgate (vs GTOBaseline, KANAL_*-Evidenz).
- A/A-Kommando (v9-Kette): `python -m pokerbot.autogym.pargate --kandidat X --incumbent X --decks 600 --workers 12
  --seed 1 --deck-seed0 960000`; Abnahme an `result.json`: `bb100==0.0 AND se==0.0 AND nonzero==0` (verdict ist
  NEUTRAL). Bank-Ledger vergeben bis 1050000 (v9), 720000-930000 (v8). `research/v9_kette.sh:15-24`; `v8_kette.sh:15-28`
- Fortsetzbar seit `eabcef3`: Bloecke `data/_pargate_blocks/{k}__vs__{i}__s{seed}__b{bank}__c{chunk}/job{idx:03d}.json`;
  Verzeichnis existiert derzeit nicht. `pargate.py:175-183,205-233`
- Output: `data/runs/<ts>_pargate_<k>/{config,result,edges}.json` + `INDEX.jsonl`; Verdikt v3 (`stats.py:90-108`).
- Deck-Seed erreicht die Strategie NICHT (nur `_worker`); einziger deterministischer Schluessel heute = Karten-/
  Lage-Hash (`improver.py:41-57,569-578`, enthaelt Hero-Hole). `pargate.py:168-171`

### A8. GTOW-Harness (Live-Kanal)
- KEINE per-Entscheidung-Timeout-Klasse: `PokerBotMVP.act` ruft `act_dict` SYNCHRON im Event-Loop (blockiert alle
  parallelen Haende); nur httpx 180 s je Request, tenacity 32 Versuche (409/502/503/504), Chunk-Subprozess 10800 s.
  `tools/gtow_client/src/poker_agent.py:69-74`; `main.py:95-116`; `utils.py:86-97`; `research/gtow_nacht.py:64-66`.
  Server-seitige Act-Deadline **nirgends belegt** (STATE zeigt stundenlang haengende Haende `docs/STATE.md:1478-1480`).
- HH-Logging: `data/sessions/gtow_hands_<ts>.jsonl` erst NACH allen Haenden mit `open('w')` (Chunk-4-Verlust);
  8 Felder `hand_id,aivat,winnings,board,street,history(Tokens),gtow_folded,players[{position,hole}]`; **keine Hero-
  Kennung, kein Fingerprint, kein Arm.** `main.py:234-250`. `main.py`/`gtow_run.py` sind **GITIGNORED** (`.gitignore:9`).
- Hook-Punkt fuer Per-Hand-Ledger existiert nur in `main.py` `_play_hand` (`main.py:159-168,194-204`); der Agent
  sieht den Terminalzustand NIE (`while not is_hand_over`); `observe_hand_end` = toter Code (`poker_agent.py:71-73,88-90`).
- Konfig: `PokerBotAgent(seed=7, exploit=True)`; Flags `POKERB_EXPLOIT/RESOLVER/TURN_RESOLVER(default ON)/GTO_MODE/
  DEEPCFR/BLUEPRINT/RANGE_TRACKER/AUSLESE_STACK`; **keine Fehlkonfig-Pruefung**; `fingerprint()` existiert
  (`gto_mode.py:138`) wird aber nirgends aufgerufen; `POKERB_AUSLESE_STACK` fehlt in `_FINGERPRINT_KEYS` (`gto_mode.py:
  72-94`). `gtowizard.py:116,183-213`
- `auslese.setze_env` wird im GTOW-Pfad NICHT gerufen (nur `server.py:20-21`, `six_server.py:22-23`); mit
  `POKERB_PRINCE=1` sind TURN_DEFENSE/SLOWPLAY 0.07/0.25 = AUSLESE_ENV-aequivalent. `auslese.py:26-36`; `gto_mode.py:42-53`
- Key: `gtow_nacht.py:52` hart Key #3 (`Secret keys/Poker/GTOW API key #3.txt`); `config.py:53-59` andere Datei;
  `gtow_run.py:19` uebergibt `--key` auf der Kommandozeile (widerspricht `main.py:254`). `_clear()` nur NACH
  Fehlversuch (`gtow_nacht.py:106-109`), nicht vor dem Start. Concurrency default 5 (`main.py:33`).
- AIVAT-Regex `gtow_nacht.py:66-72,99-109` auf `main.py:220` (bb=100). **`research/analyze_gtow_hands.py:141` BB=50
  → alle bb/100 dort um Faktor 2 ueberhoeht** (API blinds [100,50]).
- Bestand: Nacht-1 `1787012286(A,500)/1787014241(B,500)/1787016046(C,497)/1787017672(D,500)` = Arm `v4_gym_nackt`
  (exploit-ON, resolver-OFF, r6_button); Nacht-2 `1787019130(kontrolle,488)/1787027076(v4_prince,490)/1787033025
  (489)`; Chunk 4 fehlt. `data/sessions/gtow_manifest_2026-08-18.json`. `hh_luecken_mine.ARME` laedt Nacht-1 NICHT
  (`research/hh_luecken_mine.py:1-6,23-27`); Trackliste `tiefen_replay_20260901_112429.jsonl` (571 Zeilen) traegt
  KEINE Roots (gestrippt `tiefen_replay.py:218`).

---

## B. WIDERSPRUECHE ZUR BUILD-KARTE (das Wichtigste)

**B1. Arm-Definition A „PRINCE, exploit OFF, TexasSolver ON" existiert nur im GTOW-Kanal.** Der pargate-Spiegel
(G2 A/A, G5 2000 Decks) spielt `exploit=True`, POKERB_* gestrippt, `use_resolver=False` (`pargate.py:144-159`,
`bot.py:185`). Zusaetzlich ist im GTOW-Kanal der **TURN-Resolver default AN** (`gtowizard.py:192-193`) — die
Karte nennt nur den River. AUSLESE_ENV enthaelt kein `POKERB_PRINCE` (`auslese.py:26`).

**B2. Der TexasSolver ist kein „Eingriff", er ERSETZT die Basis** (`bot.py:545-547` returnt vor allen Gattern);
in 93 % der River-Entscheidungen ist die live gespielte Politik die Resolver-Stichprobe, nicht der Advisor
(`docs/STATE.md:1000`). Die K1-„Basis-Likelihood = Advisor" modelliert am River eine Politik, die live nicht
gespielt wird; die exakte `strat` (`resolver.py:257`) wird nicht exponiert. Der K2-Trace „basis →
texassolver_eingriff" braucht einen Fallback-Begriff: eine Basis existiert nur, wenn der Resolver None liefert.

**B3. Deadline 7,5 s hat KEIN Gegenstueck.** Weder Harness (synchroner `act`, `poker_agent.py:69-74`) noch
gpu-Pfad (kein Timeout, `improver.py:502,563`) noch TexasSolver (90 s Census-Timeout, greift NACH Ablauf,
`resolver.py:38`, `gto_oracle.py:126-127`). Als Wrapper um `decide()` kann K2 die ~6 s TexasSolver-Latenz nicht
unterschreiten; „p99 < 8 s" ist mit TexasSolver ON + GPU-Solve + 3 Tracker-Builds nur erreichbar, wenn der Plan
VOR `bot.py:545` greift oder der TexasSolver in Plan-Pots deaktiviert wird (Karte: „TexasSolver bleibt AN").

**B4. Gating-Zeitpunkt + Schwelle:** r8_stack (Arm A) gated `st['pot'] >= 3000` JE ENTSCHEIDUNG (`improver.py:
497`); K2 will `pot_river >= 1500` am River-Beginn. Die Arme unterscheiden sich also in Mechanismus, Schwelle UND
Zeitpunkt — G5 misst drei Dinge zugleich.

**B5. „Keine Hero-Hand-Injektion":** `solve_spots` injiziert IMMER (`gpu_resolver.py:64-70,162-169`, kein
Schalter); die Tracker-Hero-Range ist HEUTE bereits hole-invariant (`range_tracker.py:294-350`). Der TexasSolver
faellt bei hand-not-in-range still auf den Floor (`resolver.py:257-259`) → die Aktivierung im Resolver-Teil bleibt
hand-abhaengig, solange TexasSolver AN ist.

**B6. hand_id / private_seed im Gym:** Engine-State hat kein `hand_id`, `hand_no` ist im Spiegel immer 1 oder 2
(`game.py:301`; `duplicate.py:32-40`); der Deck-Seed erreicht die Strategie nicht (`pargate.py:168-171`).
`keyed_hash(private_seed, hand_id, decision_addr)` braucht eine neu gebaute Adresse; der existierende
deterministische Schluessel enthaelt die Hero-Hole (`improver.py:569-578`).

**B7. K1-Oracle „offline decide() je Combo ueber Seeds":** funktioniert nur mit `bot.rng` UND `_hand_u`/
`_hand_u_by_id` je Seed (`bot.py:216-231,486-491`), Instanz nicht reentrant (`_cur_*`), `decide()` mutiert den
RNG. Am River ist die Ueber-Seeds-Verteilung exakt die Gatter-Mischung (kein MC) → >=4 Seeds schaetzen eine
Bernoulli grob (SE ~0,25). Kanal-Konfig muss den Arm spiegeln (GTOW: Turn+River-Resolver ON; Gym: OFF).

**B8. K1-Transformationen exakt nachbilden:** `turn_wert` nutzt MC iters=160 mit hole-abhaengigem `_spot_rng`
(`improver.py:41-53,270-271`) auf dem VOLLEN State (kein Snapshot „vor der Turn-Aktion", `improver.py:267`);
eine exakte/GPU-Equity reproduziert `1_C(h)` nicht bitgenau (Grenzfaelle um 0,60). `gpu_equity` hat keine
1326-Batch- und keine gewichtete Variante (`gpu_equity.py:34-38`). Tracker verwertet Sizes gar nicht (nur jam/
normal fuer RN=0) → „Groessenvergleich" hat im Basis-Backend keine Zielgroesse.

**B9. K1-Rollen/Streets:** Tracker=Position vs `decide()`=Initiative (`range_tracker.py:179-180` vs `bot.py:65-70,
775-776`); Defense-Advisor in `decide()` nur am Flop mit echter Size, im Tracker fuer alle Calls mit 0.66
(`bot.py:600-603`; `range_tracker.py:163-177`). Preflop-Prior ohne Sitz-Aktions-Likelihood (`range_tracker.py:
37-42,337-338`). Kein `p_defense_batch` (Karte schliesst Advisor-Umbau aus).

**B10. Solver-Vertraege:** `avg_sigma` liefert uniform fuer Reach-0-Combos (`gpu_cfr.py:342-343`) → K3-Combo-
Matrix muss auf Support maskiert werden; kein `v*`/[L,U] (`gpu_cfr.py:362-372`); keine Indifferenz-Validierung;
`_navigiere` snappt Off-Tree stumm (`gpu_resolver.py:93-101`); eff_stack = SPR-Bucket, nicht echter Stack
(`gpu_resolver.py:170-171`); `river_gpu_guard` hardcodet `int(0.75*pot)` (`improver.py:527`); Raise = Zusatz 2,7x
to_call (`gpu_cfr.py:118`). Kein Cache je Hand (B=1 je Entscheidung, `improver.py:505,564`).

**B11. Latenz-Belege:** keine Einzel-Spot-Messung im Repo; 0,30 s/Spot ist Durchsatz; „~1-3 s" Annahme;
Scout-Messung 0,9-2,5 s reiner Solve (B=1, fp32, 150 Iter), p99/Kaltstart offen.

**B12. K4:** kein Startabbruch, kein Fingerprint-Aufruf, `POKERB_AUSLESE_STACK` nicht im Fingerprint
(`gto_mode.py:72-94`); Ledger-Hook nur in gitignorierter `main.py`; `POKERB_RESOLVER`-Pruefung muss ueber
`bot.use_resolver` laufen (Env wird von bot.py nicht gelesen). „Golden-Set byte-identisch" ist nur im
sequentiellen Gym-Kanal definiert (GTOW seed=7 ueber parallele Haende nicht reproduzierbar; HU-App seed=None).

**B13. K3 Holdout:** Muster `17870122xx` trifft nur Chunk A; B-D = `1787014241/1787016046/1787017672`; Arm
`v4_gym_nackt` (anderer Kanal als v10-Arme); `hh_luecken_mine.ARME` laedt sie nicht; Hero-Sitz fehlt in allen HH
(Rekonstruktion ueber winnings-Vorzeichen, `tiefen_replay.py:57-67`).

**B14. K5:** Chunk-Timeout 10800 s + synchroner act + heutiger End-of-Run-Writer → K2-Latenzen koennen den
ganzen Chunk verlieren; `_clear()` nicht vor dem Start; Key auf argv; `analyze_gtow_hands.py` BB=50 falsch.

**B15. Zahlen in der Karte:** „A/A 600 Decks" = effektiv 576 (12 Worker); „stack 10000?" — Default ungenutzt,
alle Kanaele 20000/50/100; `'allin'`-Label existiert in keiner History (Jam-Erkennung via to vs Stack).

**B16. History-Vertrag:** deal.board und call.amount fehlen im Live-Kanal (`gtowizard.py:55,66`); deal-Events bei
Run-outs nur im Adapter; `to` ist dort float. K1/K2 duerfen nur die Schnittmenge nutzen (A2).

---

## C. ENTSCHEIDUNGSBEDARF (Integrator/User) — mit Empfehlung

**E1. Wo greift K2 in der Kette — Wrapper um decide() oder VOR dem TexasSolver?** (B2, B3)
Optionen: (a) Wrapper (wie alle Guards; Basis = Resolver-Aktion; Latenz >= 6 s + GPU; p99<8 s unrealistisch);
(b) Plan-Pots deaktivieren den TexasSolver am River (`use_resolver`-Bypass nur wenn `aktiviert`; Karte sagt
„TexasSolver bleibt AN" — er bliebe AN in Nicht-Plan-Pots und am Turn); (c) Hook in `bot._postflop` vor `:545`
(Eingriff in Strategie-Code, Byte-Identitaets-Gate noetig).
**Empfehlung: (b)** — sauberste Trennung, Latenz-Ziel erreichbar, TexasSolver-Timeouts bleiben ausserhalb des
Plan-Pfads; in der Karte als bewusste Praezisierung „TexasSolver bleibt AN ausser in Plan-Pots (River)" festhalten.

**E2. Auf welchem Kanal laufen G2/G5?** (B1) pargate = exploit ON/PRINCE aus/Resolver aus. Optionen: (a) so
lassen und als „Gym-Kanal" kennzeichnen (Nichtverschlechterungs-Schranke, wie bisher); (b) `_baue_fabrik` um
`exploit=False`/PRINCE-Env fuer v10 erweitern (Mess-Fundament-Eingriff, eigener A/A-Beweis, Env muss vor Bot-
Import im Worker stehen). **Empfehlung: (a) fuer G2 (A/A ist ein Determinismus-Test, kanal-unabhaengig) + (b) als
ZUSAETZLICHER envgate-Arm fuer G5**, nicht als Ersatz — die Karte muss dann sagen, dass G5 zwei Kanaele hat.

**E3. K1-Basis-Likelihood: Advisor-only oder zweiteilig (Resolver-`strat` + Advisor-Floor)?** (B2)
**Empfehlung: zweiteilig** — `resolver.river_resolve` um eine Schwesterfunktion `river_strategy(...)` (Verteilung,
ohne `rng.choices`) erweitern; am River-Beginn spielt aber die Vorgeschichte (Flop/Turn) — dort ist Advisor
korrekt der Floor, weil Turn-Resolver im Gym AUS ist. Fuer den GTOW-Kanal (Turn-Resolver AN) TV-Abnahme
getrennt nach Kanal ausweisen.

**E4. Hand-Adresse fuer private Randomisierung im Gym.** (B6) Optionen: (a) Karten-Hash `sorted(h0|h1|board)` +
Sitz (Deck-Identitaet = Kartentupel; enthaelt beide Hole-Karten des DECKS, aber nicht als Funktion von Heros
Entscheidung — im Spiegel unproblematisch, live nicht verwendbar); (b) `hand_id` in `duplicate._setup_fixed`
injizieren (Mess-Fundament-Eingriff; bot.py toleriert `state.get('hand_id')` bereits, `bot.py:488-493`).
**Empfehlung: (b) mit A/A + Fortsetzungs-Identitaetstest als Abnahme**, weil nur (b) den Karten-Vertrag
„Aktivierung UND Sampling-Key ohne Hole Cards" erfuellt; `game.py` selbst nicht anfassen.

**E5. Deadline-Semantik im Gym vs Live.** (B3) Zeit-Deadline bricht A/A-Determinismus. **Empfehlung:** im Gym
feste ITERATIONS-Deadline (150 Iter, kein Zeitabbruch); live zusaetzlich Zeit-Deadline 7,5 s im Guard (Solve in
Thread/Future, verspaetetes Ergebnis verwerfen, `deadline`-Status im Trace); `PokerBotMVP.act` auf
`asyncio.to_thread` (Vorbild `poker_agent.py:208/285`).

**E6. K1-Transformation turn_wert: bitgenau (CPU-MC, `_spot_rng` je Combo) oder exakt (GPU) mit Kennzeichnung?**
(B8) **Empfehlung: bitgenau nachbilden** (derselbe MC-Pfad, iters=160, `_spot_rng` mit hypothetischer Combo) —
sonst misst G3 die Approximation, nicht K1; die Karte „Equity vektorisiert (gpu_equity)" ist zu streichen oder als
Approximation zu markieren. Kosten: 1326 x MC(160) je Turn-Knoten ≈ tragbar (Scout: ~50-80 ms/Combo-decide;
reine Equity deutlich billiger).

**E7. Injektions-Schalter in `solve_spots`/`RiverSpot` (Default unveraendert) vs K2 nutzt `RiverCFRBatch` direkt.**
(B5) **Empfehlung: K2 nutzt `RiverCFRBatch` direkt** (kein Eingriff in `gpu_resolver.py` → r8_stack/r10_ernte
bleiben byte-identisch, kein A/A-Neubeweis fuer Legacy-Arme); Support-Maske + Off-Tree-Toleranz + Cache in
`river_plan.py`.

**E8. Wo lebt der Per-Hand-Ledger, wenn `main.py` gitignored ist?** (B12) **Empfehlung:** versioniertes Modul
`pokerbot/benchmark/gtow_ledger.py` + minimaler, in `docs/` dokumentierter Patch in `main.py._play_hand`
(Hand-Start + Hand-Ende, `open('a')`+flush); Fingerprint einmal je Prozess in `PokerBotAgent.__init__`
(`gtowizard.py:183`) inkl. `POKERB_AUSLESE_STACK`, Git-HEAD/dirty, .pt-Hashes, `bot.use_resolver/
use_turn_resolver/exploit`; Fehlkonfig-Gatter dort (SystemExit vor Bot-Import).

**E9. Holdout-Definition K3.** (B13) **Empfehlung:** Holdout = die vier Nacht-1-Dateien namentlich (A-D), Arm
`v4_gym_nackt` als Provenienz ausweisen; nur Villain-Range/Root-Geometrie daraus nutzen; `hh_luecken_mine.ARME`
parametrisieren statt aendern; Hero-Sitz-Rekonstruktion + Ausschluss-Zaehler in den Report.

**E10. Zahlen der Karte anpassen:** A/A 576 Decks (oder Worker fixieren); Bank-Ledger neue Bank (z.B. 1080000);
Latenz-Gate end-to-end im frischen Prozess, geschichtet nach SPR-Bucket; „stack 20000/50/100" als Einheit
festschreiben; `analyze_gtow_hands.py` vor jedem K3/K5-Report auf BB=100 korrigieren (oder nicht zitieren).

**E11. K1-Rollenkonvention** (B9): **Empfehlung:** Hero = INITIATIVE-Rolle (wie `decide()`), Villain = Position
(wie Tracker); Abweichung in G3 nach Pot-Typ (SRP/3bet) getrennt messen. `p_defense_batch` als additive Funktion
mit Identitaets-Wache (korrekte Gross-Schreibung `'IP'/'OOP'`) zulassen — die Karte muesste den Ausschluss
„Advisor-Umbau" auf „keine Gewichts-/Feature-Aenderung" praezisieren.

---

## D. WAS DER VERTRAG (contracts.py, P0b) DARAUS FESTSCHREIBT
- Oeffentlicher Zustand OHNE Hole Cards (`PolicySnapshot`); Aktionshistorie als `(street, spieler, ActionKey)`
  auf der Kanal-Schnittmenge (A2), deal-Events werden NICHT als Aktionen gefuehrt, Board aus `state['board']`.
- `ActionKey`: `fold|check|call|raise_to(chips:int)`; Kanonisierung = Engine-Regel `int()`-Truncation + Clamp auf
  `legal.raise_min/raise_max` (`game.py:170`), `bet/raise/allin` → `raise_to`.
- `RangeState`: Combo-Konvention = `gpu_cfr.combo_index` (rank*4+suit, 'shdc', lexikographische Paare); Gewichte
  unnormiert-skaleninvariant ODER normiert; Board-Combos exakt 0 (hart); `hero_injiziert` muss im K1/K2-Pfad False sein.
- `PolicyTable`: Zeilen Σ=1±1e-6; `undefiniert`-Menge fuer Reach-0-Combos (nie uniform interpretieren, B10).
- `RiverPlan`: Aktivierung nur aus `pot_river` (oeffentlich); Status-Vokabular `offtree|deadline|fehler|
  hand_not_in_range|keiner`; `private_seed_quelle` explizit.
- `EntscheidungsTrace`: `basis → texassolver → guards → plan_verteilung → legalitaet → sample_u → final`, wobei
  `texassolver` als ERSATZ (nicht Eingriff) gefuehrt wird (B2).
