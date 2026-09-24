# V10 FACTS — consolidated scout findings (Integrator, 2026-09-07)

Pure fact-securing for the build card `../plans/V10_BUILD_CARD.md`. Five scouts (bot / engine / harness /
tracker / gpu / pargate), re-checked by the integrator against the source (spot checks: `game.py:97-181,
290-307`, `gtowizard.py:36-82,126-148`, `pargate.py:18-37`, `gpu_cfr.py:37-53`, `gpu_resolver.py:26-36`,
`bot.py:545-556`, `auslese.py:20-62`, existence check of all target files). Every statement carries `file:line`.
**Most important output = section B (contradictions) and C (decisions needed).** No number without a source.

Repo state: branch `poker-core`, HEAD `eabcef3`; working tree clean except for the two untracked
card documents (`../consults/TOP5_CONSULT_GPT6_2026-09-07.md`, `../plans/V10_BUILD_CARD.md`). Coin flip K5 is on record:
`data/runs/v10_muenze.json` = `BAAB_dann_ABBA` (2026-09-07 16:47:57). `data/runs/v10/` exists, empty.

---

## A. FACTS BY TOPIC

### A0. Existence of the target files / registration
| Card names | Finding | Source |
|---|---|---|
| `pokerbot/strategy/contracts.py` | WAS MISSING — created with this assignment (P0b) | `test -e` 2026-09-07 |
| `pokerbot/strategy/hero_range.py` (K1) | MISSING | ditto |
| `pokerbot/autogym/river_plan.py` (K2) | MISSING | ditto |
| `research/policy_oracle.py`, `research/river_br_pruefstand.py` (K3) | MISSING | ditto |
| `pokerbot/runtime_config.py` (K4) | MISSING | ditto |
| `research/gtow_nacht_v10.py` (K5) | MISSING | ditto |
| Stack `r10_stack` | NOT registered; present: `r8_stack`, `r9_play`, `r9_pre`, `r9_turn`, `r9_v8`, `r10_ernte` | `pokerbot/autogym/pargate.py:18-37` (KANDIDATEN), `:40-141` (`_wickle`) |
| `tests/` GPU/CFR/resolver tests | NONE; only `__main__` self-tests | `gpu_cfr.py:667-676`, `gpu_resolver.py:218-244`, `gpu_equity.py:161-169` |
| 40-deck divergence smoke / "golden set" | NO script, NO artifact; only the journal sentence "0.88 s/deck, 4/40 divergences" | `data/autogym/journal.jsonl` V9-VORREGISTRIERUNG 2026-09-01; `git show --stat a84473a` (only 2 files) |

### A1. Engine state (HeadsUpGame) — the gym/pargate format
- `act()`: amount = **raise-TO level of the street** (cumulative), `int(amount)` truncates, then **silent clamp**
  `max(raise_min, min(target, raise_max))`; exceptions only for check/call/bet without permission, bet/raise without
  amount, unknown action. **Fold at to_call==0 is allowed** (not checked). `game.py:141-181`
- Label `'bet'` iff `prev_bet==0`, else `'raise'`; **`'allin'` never appears as a history label** (jam = bet/raise
  with `to == committed_street+stack`). `game.py:178-181`
- History shapes (5): fold/check `{player,action,street}`; call `{player,action:'call',amount:<paid>,street}`;
  bet/raise `{player,action,to:<level>,street}`; deal `{action:'deal',street,board:[full]}` WITHOUT player.
  No preflop deal, no blind entries. On an all-in run-out: **NO deal event** (silent). `game.py:143,151,
  158-159,179-181,217-221,239`
- `legal_actions()`: `to_act,to_call,can_fold(=can_call),can_check,can_call,call_amount,can_raise,is_bet,
  raise_min,raise_max,pot`; `can_raise = stack > to_call and not opp.all_in`; `raise_min` = bet: `committed+bb`,
  raise: `current_bet+min_raise` (min_raise NOT in the state). `game.py:97-128`
- `state()`: `hand_no,button,street,board,pot(=Σcommitted_total),current_bet,to_act,hand_over,result,sb,bb,
  history,players[{idx,name,stack,hole,folded,all_in,committed_street,committed_total,is_button}],legal`.
  **NO `hand_id`.** Without `hide=` BOTH hole cards are visible (gym/duplicate call without hide). `game.py:
  290-307`; `gym_hu.py:35`; `duplicate.py:47`
- `hand_no` in the mirror is NOT unique: `_setup_fixed` sets 0 or 1 before `start_hand` → always 1 (button 0)
  or 2 (button 1), the same for every deck. `duplicate.py:32-40`; `game.py:68-72`
- Engine default `starting_stack=10000` (`game.py:31`), but ALL measurement channels 20000/50/100: `gym_hu.py:69-72`,
  `duplicate.py:55-58,76-78`, `pargate.py:168-171`, `orakel_duell.py:41`, GTOW `gtowizard.py:89-91,232-235`.

### A2. Adapter state (gtow_to_state) — the live channel
- History from `_parse_history`: call WITHOUT `amount`; deal WITHOUT `board`; bet/raise with `to` as **FLOAT**; preflop
  aggression always `'raise'`; deal events also on all-in run-outs. `gtowizard.py:38-82`
- Top level: `street,board,pot(=total_pot),bb,current_bet,button,hand_id(GTOW),hand_no:0,history,to_act:0,
  hand_over,players[hole villain '??',stack,committed_street,committed_total=start-stack,folded,all_in,
  is_button],legal(raise_range clamp separate)`. No `sb`, no `result`. `gtowizard.py:126-148,150-174`
- **Intersection of both channels** (the only thing K1/K2 may build on): `player, action, street, to` (bet/raise) +
  `deal.street`; board from `state['board']`; call increment from the level difference. Consumers today only check
  `action=='deal'`/`street`: `bot.py:500-519`, `range_tracker.py:314`, `resolver.py:191`.

### A3. Bot — RNG, gates, resolver precedence, hidden state
- ONE instance RNG `self.rng = random.Random(seed)`; no global `random`. Seeds: GTOW `seed=7` (ONE instance
  for 5-8 parallel hands → draw order depends on interleaving, not reproducible); HU app
  `seed=None`; gym `seed/seed+1`; duplicate/pargate both seats `seed`. `bot.py:139-141`; `gtowizard.py:183-194`;
  `server.py:37,44`; `gym_hu.py:22-26,73`; `duplicate.py:101-110`; `pargate.py:144-147`
- Precedent for per-spot reseeding without global side effect: `coach/oracle.py:185-188` (`bot.rng = Random(spot_fp)`).
- Randomness consumption: flop/turn MC equity 1500 iters (`bot.py:33,566,569`; `equity.py:65-68,107-110`); **river
  exact (no RNG)** (`equity.py:52-61,92-101`). Gates with `rng.random()/choices`: preflop `bot.py:216-231,303,
  335-342,356,391,410,446,466,486-491`; postflop `621,753,783,812,851,870,897,909,921,927,1174,1195`.
- **LINE_U (PRINCE=1): ONE draw per hand in the preflop call** → `_hand_u` / `_hand_u_by_id[hand_id]`; the
  advisor gates flop/turn/river use this value (`bot.py:216-231,486-491,783,812,851`). An isolated
  river decide without a preflop call plays with `u=0.5` (default = effectively purify) or a foreign u. `bot.py:144-149`
- Further instance attributes (not reentrant): `_cur_street/_cur_committed/_cur_state/_cur_hole/_cur_board/
  _ecall_exact_to`, `self.opp`, `_probe_spent_bb`, `_river_keys`. `bot.py:210-212,534-536,1265-1266`
- **Resolver precedence:** `street=='river' and self.use_resolver` → `_river_resolve`; on a result `return` BEFORE
  all gates/levers/slowplay/eCall — it REPLACES the base, it is not an intervention. Fallback (None) only on: no
  raise/call possible, tracker confidence `<0.5`, empty range strings, exception/timeout, tree navigation
  fails, **hero hand not in range** (`strategy_for` None), Σprobs<=0. Fired on 93 % of river decisions.
  `bot.py:545-556,1037-1062`; `resolver.py:232-266`; `range_tracker.py:59`; `docs/STATE.md:1000`
- Resolver samples `rng.choices(labels, weights=probs)`; the exact distribution `strat` (`resolver.py:257`) is
  NOT returned. TexasSolver timeouts: census (PRINCE) river 90 s/turn 150 s/flop 240 s; compact 40/60/120 s;
  `subprocess.run(timeout)` → `TimeoutExpired` caught by `except Exception` → None → floor **after** expiry.
  `resolver.py:18-38,81-82,117,238-246`; `gto_oracle.py:126-127`. Latency ~6 s/river decision (median 5.8 s);
  resolver-OFF 83 ms (`docs/STATE.md:1000`; commit 57b9807).
- Disk solve cache (default ON): key = sha1(board, ranges, pot, eff, bets, acc, iters, dump, mode) — WITHOUT hole,
  WITHOUT history directly → one solve per node for all combos/seeds. `gto_oracle.py:44-62,92-101,148-158`
- **`POKERB_RESOLVER` is NOT read by bot.py**; attributes `use_resolver=False`, `use_turn_resolver=False`
  default; only `gtowizard.py:187-196` reads the env (default ON, **turn resolver ON as well**). HU app/gym/
  duplicate/pargate: OFF. `bot.py:185-190`; `server.py:37`; `replay_graded.py:323-324`; `stress_suite.py:81`
- Mixed distribution exposed? NO (no function). Partial exposure in the rationale: `advisor_pbet*`,
  `defense_advisor:[p_fold,p_call,p_raise]`, `blueprint.dist`, deepcfr `probs`. Not: resolver `strat`,
  heuristic frequencies (f_cbet/bf/donk only as text), LINE_U-u. `bot.py:249-250,361-362,614-615,781,809,848,1060-1062`
- `exploit=False` (PRINCE→GTO_MODE→`POKERB_EXPLOIT=0`): conf=0 → MDF shade 0, exploit term 0, `_river_exploit/
  _river_probe` skipped, bluff-raise branch dead; bot.py can only switch exploit OFF. `bot.py:151-155,436,
  573-576,583,655-657,721-729,761-764`; `gto_mode.py:14,19`; `postflop.py:151-161`
- PRINCE flags are **import-time constants** (`bot.py:36-108`; `postflop.py:27,35,44,148`; `advisor.py:28`;
  `resolver.py:18,31,117`; `range_tracker.py:71,79`) → the env MUST be set before the first `pokerbot.strategy.*` import;
  `gtowizard.py:23-27` calls `apply()` before the lazy bot import. Priority: env > PRINCE_PROFILE > PROFILE > default
  (`gto_mode.py:12-31,44-54,102-137`).
- Hero hole as dead cards: `_tracked_villain_range` filters villain by hero hole+board; `_tracked_ranges_both`
  filters hero ONLY by the board (already public). `bot.py:967-969,989-990,1010-1012`
- `decide()` is NOT memoized; the 12.1x speedup memoizes `advisor.p_bet/p_defense` (key hole/board/role/
  street/pot_type or size_faced), `features._FEATURES_MEMO`, `evaluator._EVAL_MEMO`; wholesale clear at
  120k/60k (no LRU). `advisor.py:82-97,185-199`; `features.py:36-68`; `evaluator.py:17-38`
- RangeTracker is rebuilt up to 3x per river decide (`bot.py:987,1003,1050`); `build()` reads only history/
  board/button/bb/stacks+committed_total — **no hole cards** (`range_tracker.py:294-350,397-409`).
- Auslese wrapper: `wickle_decide(pb, stack)` wraps the `_wickle` chain around `pb.decide`; guards see the base ONLY as
  `(action, amount)`; on deviation `auslese_guard: True` goes into the rationale — no stage trace. `auslese.py:39-62`;
  `pargate.py:40-47`. When the TexasSolver fires, the "base" for all guards is the resolver action.

### A4. RangeTracker + Advisor (K1 backend)
- Preflop prior = CLASS set by NUMBER of raises (0/1/2+) and button: `>=2` → `range_top(0.18)` both; `==1` →
  button `sb_open()`, non-button `bb_defend()`; `0` → `range_top(0.85)`; combos without dead cards, weight 1.0.
  Preflop rows are SKIPPED in the walk → preflop actions (hero's too) do not change the range.
  `range_tracker.py:32-42,131-138,337-338`
- Walk: deal sets `cur_street`, `_remove_dead(board[:3/4/5])`; commitment bookkeeping for the jam read (`jam` if
  `committed+inc >= start_stack-1`); `facing = street_bet>0`; role = POSITION (`'IP'` iff seat==button);
  fold no update; whole walk in try/except (partial result remains). `range_tracker.py:105-107,179-180,294-352`
- `_update_action`: bet&!facing → `d[c] *= p_bet**alpha` (alpha 1.0 with AGGRO_FULL and aggro>=1, else
  TRACKER_ALPHA), batched; check&!facing → `(1-p)**alpha`, single calls; call&facing → `P_call**alpha` with
  **FIXED size_faced=0.66**; raise/allin&facing → modeled only with RAISE_NARROW, else `heur+=1` (legality
  only). `_normalize` deletes `< 1e-6`. `range_tracker.py:163-177,182-197,208-267,269-292`
- Effective under PRINCE (probe): ALPHA 0.5, AGGRO_FULL True, AUDIT_FIX False, RN 0.0, CONF_SLOPE 0.7 → first bet
  of a seat ^0.5, from the 2nd ^1.0; check/call ^0.5; raise does NOT count as aggro. `range_tracker.py:71-90,218,
  255-263`; `gto_mode.py:19-20,43,52,61`; `auslese.py:25-36`
- Advisor API: `p_bet(hole,board,role,street,pot_type)->float|None` (memo 120k); `p_bet_batch(combos,...)->dict`
  (one forward pass; 13/17/27 ms per full range flop/turn/river vs 61-65 ms individually); `p_defense(hole,board,role,
  size_faced,street)->(P_fold,P_call,P_raise)`; **NO `p_defense_batch`** (68-70 ms per full range individually).
  Role `'IP'` case-sensitive. `advisor.py:18-20,44-51,54-75,82-157,160-221`
- Feature vector: tier(3)+texture(5)+role bit+7 bools+overcards/2+strength; p_defense + street one-hot + size;
  **NO range/pot/SPR/history information** (card correct). `advisor.py:44-51,101-114,203-221`; `features.py:57-106`
- Role conflict: tracker asks POSITION; `decide()` asks `p_bet` by INITIATIVE (`_ADVISOR_ROLE_POS` default
  '0'; `_has_initiative` = last preflop raiser) and `p_defense` by position. `range_tracker.py:179-180`;
  `bot.py:65-70,604,771-776,801-802,831-832,934-943`; training: tree position `research/build_advisor_data.py:33`
- Defense advisor in `decide()` ONLY on the flop (`_def_streets=('flop',)` without TURN_DEF_ADVISOR) with real size
  and `self.rng`; turn/river calls from MDF/threshold logic. `bot.py:600-603,622,636ff`
- Snapshot API: NONE. Only mechanism = history cut + rebuild (`improver.py:420-440` at the river deal;
  `turn_gpu.py:100-110` at the turn deal). Cost: 210 ms cold / 7.2 ms warm (probe). A cut `hist[:i]` yields
  the range BEFORE action i only if the street's deal row is included.
- Models present: `knowledge_base/postflop/{advisor,turn_advisor,river_advisor,defense_advisor,river_advisor_la}.pt`.
- Postflop frequencies (65 HH files, 24,050 hands, both seats): bet 27.5 %, check 56.3 %, call 13.3 %,
  raise-facing-bet 2.9 % (→ heur share in the live stack); `tests/test_range_tracker.py:89-116` green.
- Identity guard `research/advisor_batch_check.py:24` calls roles in lower case (`'ip'/'oop'`) → role bit
  0 in both arms; IP path NOT covered (evidence gap, not a product bug).

### A5. Existing guards (template for K1 transformations and K2)
- `turn_wert_guard(frac=0.66,min_eq=0.60,iters=160)`: trigger check & to_call==0 & turn & stacks>0; class via
  treys (`kl<=6` or `kl==7 & involved` or overpair); tracker on the FULL state (no cut);
  **MC equity iters=160 with `_spot_rng(st)`, whose seed contains the HERO HOLE** → `('bet', int(0.66*pot))`.
  `improver.py:38,41-53,230-278`; `equity.py:79-117`
- `sel_guard(margin=0.15)` = `sel_m15`: fold & to_call>0 & flop; MC equity iters=160 `>= equity_needed_to_call +
  0.15` → call. `improver.py:119-153`; `pargate.py:60-61`
- `button_disziplin_guard`: fold & preflop & to_call==50 & committed==50 → `('raise',250)`; no hand condition.
  `improver.py:600-616`
- `river_wert_bremse`: bet & to_call==0 & river & kl<=7 & exact equity `<0.50` → check (RNG-free). `improver.py:
  318-333,377-410`
- `river_gpu_guard(min_pot_chips=3000,iters=150,p_max_basis=0.10,p_min_alt=0.70)`: gated `st['pot']>=3000` PER
  DECISION (current pot, not pot_river); `solve_spots([spot])` B=1 per decision; override only at
  `p_basis<0.10 & p_alt>0.70`; **bet size hardcoded `int(0.75*pot)`** despite the comment; `except: pass` without log.
  `improver.py:477-533`
- `river_play_guard(min_pot_chips=3000,iters=150,half=False)`: samples deterministically `crc32('v8play|'+sorted
  (hole)|board|pot|current_bet|committed_street|len(history))/2^32` — **hash CONTAINS hero hole**, no
  private_seed/hand_id; size `zus[wahl]/100*pot_river`, `int()` truncation, jam at `>= stack-1`, legality
  gate; no deadline; `except: pass`. `improver.py:535-604`. Registered as `r9_play`; `r10_ernte` = with
  `min_pot=1500, half=True` + `stackoff_bremse`. `pargate.py:109-112,133-140`
- `_river_spot_und_frage`: cut at the river `deal`, `pot_river = st['pot'] − river bets` (verified 1400==
  1400; equivalent exactly: `st['pot'] − Σ committed_street`), float; None without a river deal (silent runout).
  `improver.py:421-470`
- Chain (wrapper order, outer sees inner): basis → sel_m15 → turn_wert → button → wert_bremse →
  river_gpu (`pargate.py:80-108`). Guards read hero via `st['players'][st['to_act']]`, not `hero_idx`.

### A6. GPU solver (gpu_cfr / gpu_resolver)
- Canonical combo index: `itertools.combinations(range(52),2)` lexicographic, card `rank*4+suit`, rank 0='2'..
  12='A', suits `'shdc'`; `combo_index` sorted. `gpu_cfr.py:37-44,441`; `gpu_eval.py:9,200-201`
- `range_vector({('As','Kd'):w})` → dense float32 [1326]; **NO normalization** (docstring `gpu_cfr.py:167-168`
  claims it; code `175-176,293-294` only masks; scale-invariant, harmless).
- `RiverCFRBatch(boards, r_oop, r_ip, pot, eff_stack, half=False, **baum_kw)`: player 0 = OOP acts first;
  CFR+ (RM+, linear averaging, alternating, NO RNG); `avg_sigma(node)` = average strategy, **combos with
  reach 0 receive UNIFORM 1/n** (phantom trap). `gpu_cfr.py:276-343`
- No public dump API; route: `node.acts/node.kids` recursively + `cfr.avg_sigma(node)[b]`; `_alle_knoten`
  private; `strategy_at_root` only on `RiverCFR`. `gpu_cfr.py:157-163,263-265`
- `_br`: exact BR per (node, own combo); villain strategy indexed only by villain combo → does not see hero's
  hand (correct). `gpu_cfr.py:345-360`. Terminals centered around `−pot0/2`, zero-sum. `gpu_cfr.py:309-316`
- `exploitability()` = `100*(BR_0+BR_1)/pot0` [B]; **NO game value v\*, NO bracket [L,U]** (derivable from
  both `_br`). `gpu_cfr.py:362-372`. `action_values` = Q per combo per action (POT_NORM scale, differences only);
  **NO indifference validation in the repo** (`INDIFF_BB` in `tiefen_replay.py:47` is only a category threshold).
- `solve_spots(spots,iters=300,max_batch=192,mit_evs=False)`: **`_injiziere` ALWAYS on the hero side** (no
  switch; `HERO_MIN_GEWICHT=0.02`); grouping by SPR bucket (`spr<=1.25*b`), pot normalized 100, **eff_stack =
  bucket, not the real stack**. `gpu_resolver.py:26-36,64-70,148-215`; second caller `turn_gpu.py:20,131`
- `_navigiere/_navigiere_mit_reach`: bet/raise sizes are **SILENTLY snapped to the nearest arm** (no
  tolerance window, no log); missing check/call arm, fold, terminal → None. `gpu_resolver.py:73-145`
- `build_river_tree(pot,eff,bet_sizes=(0.35,0.75,1.5),raise_sizes=(2.7,),max_raises=2)`: bets = fraction of the
  CURRENT pot; **raise increment = 2.7 x to_call** (not "raise to 2.7x"); arms >=85 % of the remainder collapse into jam.
  `gpu_cfr.py:96-153`. Tree size 9-99 nodes per SPR bucket (scout measurement).
- Latency: repo documents only throughput 0.30 s/spot at B=256 (`docs/STATE.md:26`); "~1-3 s" in the consult is
  an assumption (`TOP5_KONSULT…:2406-2407`). Scout measurement today (RTX 3080 Ti, B=1, fp32, 150 iters, 400x400 combos):
  SPR 1: 0.9-1.1 s; SPR 3: 2.0-2.55 s; SPR 7: 2.5 s pure solve; setup 18-23 ms warm / 289 ms cold. p99/cold start
  end-to-end NOT measured.
- No cache, no deadline in gpu_cfr/gpu_resolver/improver. Determinism: no RNG; A/A exactly 0 proven
  (r8_stack fp32 600 decks, journal R8-FINALE-LAUF1; r10_ernte fp16 576 decks, `data/runs/20260901_114509_pargate_
  r10_ernte/result.json`), conditions: OPENBLAS/OMP/MKL=1, `torch.set_num_threads(1)`, POKERB_* strip
  (`pargate.py:150-165`); `use_deterministic_algorithms/cudnn/TF32` set nowhere (hardware/version-bound).
- `gpu_equity.equity_vs_range_exakt(hero, villain_combos, board)` = ONE hand vs range [C], NaN for blockers;
  NO 1326-batch variant, NO weighted variant, **no production caller**; verification averages
  unweighted. `gpu_equity.py:34-87,90-131`

### A7. pargate / duplicate — the mirror channel
- `par_gate(kandidat,n_decks,workers,seed=1,deck_seed0=1000,incumbent)`: `n_jobs=workers*4`, `chunk=n_decks//
  n_jobs` → **600 decks / 12 workers = 576 decks** (result.json n_decks 576). `pargate.py:186-215`
- Pairing = `duplicate_ab`: every deck TWICE, **button ALWAYS 0**, the strategy switches seats; `edge = x1−x2`;
  `bb100 = mean/2/bb*100`. `duplicate.py:32-73`. gym_hu (4-block holes x button) is NOT used by pargate.
- Factory contract: `make_strat(seat) -> decide(st) -> (action, amount)`; `d(st)` only at `st['to_act']==seat`.
  `duplicate.py:8-9,46,101-115`
- **Gate channel = exploit=ON, all POKERB_* env stripped (no PRINCE), resolver OFF.** `pargate.py:144-147,
  152-159`; `bot.py:185`. Both instances in the SAME worker process with the same `--seed`; PYTHONHASHSEED is
  NOT set by pargate (only envgate `envgate.py:145`). Env channel = envgate (vs GTOBaseline, KANAL_* evidence).
- A/A command (v9 chain): `python -m pokerbot.autogym.pargate --kandidat X --incumbent X --decks 600 --workers 12
  --seed 1 --deck-seed0 960000`; acceptance on `result.json`: `bb100==0.0 AND se==0.0 AND nonzero==0` (verdict is
  NEUTRAL). Bank ledger assigned up to 1050000 (v9), 720000-930000 (v8). `research/v9_kette.sh:15-24`; `v8_kette.sh:15-28`
- Resumable since `eabcef3`: blocks `data/_pargate_blocks/{k}__vs__{i}__s{seed}__b{bank}__c{chunk}/job{idx:03d}.json`;
  directory does not currently exist. `pargate.py:175-183,205-233`
- Output: `data/runs/<ts>_pargate_<k>/{config,result,edges}.json` + `INDEX.jsonl`; verdict v3 (`stats.py:90-108`).
- The deck seed does NOT reach the strategy (only `_worker`); the only deterministic key today = card/
  situation hash (`improver.py:41-57,569-578`, contains hero hole). `pargate.py:168-171`

### A8. GTOW harness (live channel)
- NO per-decision timeout class: `PokerBotMVP.act` calls `act_dict` SYNCHRONOUSLY in the event loop (blocks all
  parallel hands); only httpx 180 s per request, tenacity 32 attempts (409/502/503/504), chunk subprocess 10800 s.
  `tools/gtow_client/src/poker_agent.py:69-74`; `main.py:95-116`; `utils.py:86-97`; `research/gtow_nacht.py:64-66`.
  Server-side act deadline **documented nowhere** (STATE shows hands hanging for hours `docs/STATE.md:1478-1480`).
- HH logging: `data/sessions/gtow_hands_<ts>.jsonl` only AFTER all hands with `open('w')` (chunk-4 loss);
  8 fields `hand_id,aivat,winnings,board,street,history(tokens),gtow_folded,players[{position,hole}]`; **no hero
  marker, no fingerprint, no arm.** `main.py:234-250`. `main.py`/`gtow_run.py` are **GITIGNORED** (`.gitignore:9`).
- Hook point for a per-hand ledger exists only in `main.py` `_play_hand` (`main.py:159-168,194-204`); the agent
  NEVER sees the terminal state (`while not is_hand_over`); `observe_hand_end` = dead code (`poker_agent.py:71-73,88-90`).
- Config: `PokerBotAgent(seed=7, exploit=True)`; flags `POKERB_EXPLOIT/RESOLVER/TURN_RESOLVER(default ON)/GTO_MODE/
  DEEPCFR/BLUEPRINT/RANGE_TRACKER/AUSLESE_STACK`; **no misconfiguration check**; `fingerprint()` exists
  (`gto_mode.py:138`) but is called nowhere; `POKERB_AUSLESE_STACK` is missing from `_FINGERPRINT_KEYS` (`gto_mode.py:
  72-94`). `gtowizard.py:116,183-213`
- `auslese.setze_env` is NOT called in the GTOW path (only `server.py:20-21`, `six_server.py:22-23`); with
  `POKERB_PRINCE=1` TURN_DEFENSE/SLOWPLAY 0.07/0.25 = AUSLESE_ENV-equivalent. `auslese.py:26-36`; `gto_mode.py:42-53`
- Key: `gtow_nacht.py:52` hard-codes key #3 (`Secret keys/Poker/GTOW API key #3.txt`); `config.py:53-59` a different file;
  `gtow_run.py:19` passes `--key` on the command line (contradicts `main.py:254`). `_clear()` only AFTER a
  failed attempt (`gtow_nacht.py:106-109`), not before the start. Concurrency default 5 (`main.py:33`).
- AIVAT regex `gtow_nacht.py:66-72,99-109` on `main.py:220` (bb=100). **`research/analyze_gtow_hands.py:141` BB=50
  → all bb/100 there inflated by a factor of 2** (API blinds [100,50]).
- Inventory: night 1 `1787012286(A,500)/1787014241(B,500)/1787016046(C,497)/1787017672(D,500)` = arm `v4_gym_nackt`
  (exploit-ON, resolver-OFF, r6_button); night 2 `1787019130(kontrolle,488)/1787027076(v4_prince,490)/1787033025
  (489)`; chunk 4 missing. `data/sessions/gtow_manifest_2026-08-18.json`. `hh_luecken_mine.ARME` does NOT load night 1
  (`research/hh_luecken_mine.py:1-6,23-27`); track list `tiefen_replay_20260901_112429.jsonl` (571 rows) carries
  NO roots (stripped `tiefen_replay.py:218`).

---

## B. CONTRADICTIONS WITH THE BUILD CARD (the most important part)

**B1. Arm definition A "PRINCE, exploit OFF, TexasSolver ON" exists only in the GTOW channel.** The pargate mirror
(G2 A/A, G5 2000 decks) plays `exploit=True`, POKERB_* stripped, `use_resolver=False` (`pargate.py:144-159`,
`bot.py:185`). Additionally, in the GTOW channel the **TURN resolver is ON by default** (`gtowizard.py:192-193`) — the
card names only the river. AUSLESE_ENV does not contain `POKERB_PRINCE` (`auslese.py:26`).

**B2. The TexasSolver is not an "intervention", it REPLACES the base** (`bot.py:545-547` returns before all gates);
in 93 % of river decisions the policy played live is the resolver sample, not the advisor
(`docs/STATE.md:1000`). The K1 "base likelihood = advisor" models, on the river, a policy that is not
played live; the exact `strat` (`resolver.py:257`) is not exposed. The K2 trace "basis →
texassolver_eingriff" needs a fallback notion: a base exists only when the resolver returns None.

**B3. Deadline 7.5 s has NO counterpart.** Neither harness (synchronous `act`, `poker_agent.py:69-74`) nor
gpu path (no timeout, `improver.py:502,563`) nor TexasSolver (90 s census timeout, applies AFTER expiry,
`resolver.py:38`, `gto_oracle.py:126-127`). As a wrapper around `decide()`, K2 cannot get under the ~6 s TexasSolver
latency; "p99 < 8 s" with TexasSolver ON + GPU solve + 3 tracker builds is only reachable if the plan
kicks in BEFORE `bot.py:545` or the TexasSolver is deactivated in plan pots (card: "TexasSolver stays ON").

**B4. Gating time + threshold:** r8_stack (arm A) gates `st['pot'] >= 3000` PER DECISION (`improver.py:
497`); K2 wants `pot_river >= 1500` at the start of the river. So the arms differ in mechanism, threshold AND
timing — G5 measures three things at once.

**B5. "No hero-hand injection":** `solve_spots` ALWAYS injects (`gpu_resolver.py:64-70,162-169`, no
switch); the tracker hero range is ALREADY hole-invariant today (`range_tracker.py:294-350`). The TexasSolver
silently falls to the floor on hand-not-in-range (`resolver.py:257-259`) → activation in the resolver part stays
hand-dependent as long as TexasSolver is ON.

**B6. hand_id / private_seed in the gym:** the engine state has no `hand_id`, `hand_no` in the mirror is always 1 or 2
(`game.py:301`; `duplicate.py:32-40`); the deck seed does not reach the strategy (`pargate.py:168-171`).
`keyed_hash(private_seed, hand_id, decision_addr)` needs a newly built address; the existing
deterministic key contains the hero hole (`improver.py:569-578`).

**B7. K1 oracle "offline decide() per combo over seeds":** works only with `bot.rng` AND `_hand_u`/
`_hand_u_by_id` per seed (`bot.py:216-231,486-491`), instance not reentrant (`_cur_*`), `decide()` mutates the
RNG. On the river the over-seeds distribution is exactly the gate mix (no MC) → >=4 seeds estimate a
Bernoulli coarsely (SE ~0.25). Channel config must mirror the arm (GTOW: turn+river resolver ON; gym: OFF).

**B8. Reproducing K1 transformations exactly:** `turn_wert` uses MC iters=160 with hole-dependent `_spot_rng`
(`improver.py:41-53,270-271`) on the FULL state (no snapshot "before the turn action", `improver.py:267`);
an exact/GPU equity does not reproduce `1_C(h)` bit-exactly (edge cases around 0.60). `gpu_equity` has no
1326-batch and no weighted variant (`gpu_equity.py:34-38`). The tracker does not use sizes at all (only jam/
normal for RN=0) → "size comparison" has no target quantity in the base backend.

**B9. K1 roles/streets:** tracker=position vs `decide()`=initiative (`range_tracker.py:179-180` vs `bot.py:65-70,
775-776`); defense advisor in `decide()` only on the flop with real size, in the tracker for all calls with 0.66
(`bot.py:600-603`; `range_tracker.py:163-177`). Preflop prior without seat-action likelihood (`range_tracker.py:
37-42,337-338`). No `p_defense_batch` (card excludes an advisor rebuild).

**B10. Solver contracts:** `avg_sigma` returns uniform for reach-0 combos (`gpu_cfr.py:342-343`) → K3 combo
matrix must be masked to the support; no `v*`/[L,U] (`gpu_cfr.py:362-372`); no indifference validation;
`_navigiere` snaps off-tree silently (`gpu_resolver.py:93-101`); eff_stack = SPR bucket, not the real stack
(`gpu_resolver.py:170-171`); `river_gpu_guard` hardcodes `int(0.75*pot)` (`improver.py:527`); raise = increment 2.7x
to_call (`gpu_cfr.py:118`). No cache per hand (B=1 per decision, `improver.py:505,564`).

**B11. Latency evidence:** no single-spot measurement in the repo; 0.30 s/spot is throughput; "~1-3 s" an assumption;
scout measurement 0.9-2.5 s pure solve (B=1, fp32, 150 iters), p99/cold start open.

**B12. K4:** no start abort, no fingerprint call, `POKERB_AUSLESE_STACK` not in the fingerprint
(`gto_mode.py:72-94`); ledger hook only in the gitignored `main.py`; the `POKERB_RESOLVER` check must go through
`bot.use_resolver` (the env is not read by bot.py). "Golden set byte-identical" is defined only in the
sequential gym channel (GTOW seed=7 over parallel hands not reproducible; HU app seed=None).

**B13. K3 holdout:** pattern `17870122xx` matches only chunk A; B-D = `1787014241/1787016046/1787017672`; arm
`v4_gym_nackt` (a different channel than the v10 arms); `hh_luecken_mine.ARME` does not load them; hero seat missing in all HH
(reconstruction via the sign of winnings, `tiefen_replay.py:57-67`).

**B14. K5:** chunk timeout 10800 s + synchronous act + today's end-of-run writer → K2 latencies can lose the
whole chunk; `_clear()` not before the start; key on argv; `analyze_gtow_hands.py` BB=50 wrong.

**B15. Numbers in the card:** "A/A 600 decks" = effectively 576 (12 workers); "stack 10000?" — default unused,
all channels 20000/50/100; the `'allin'` label exists in no history (jam detection via to vs stack).

**B16. History contract:** deal.board and call.amount are missing in the live channel (`gtowizard.py:55,66`); deal events on
run-outs only in the adapter; `to` is float there. K1/K2 may only use the intersection (A2).

---

## C. DECISIONS NEEDED (Integrator/User) — with recommendation

**E1. Where does K2 enter the chain — wrapper around decide() or BEFORE the TexasSolver?** (B2, B3)
Options: (a) wrapper (like all guards; base = resolver action; latency >= 6 s + GPU; p99<8 s unrealistic);
(b) plan pots deactivate the TexasSolver on the river (`use_resolver` bypass only when `aktiviert`; card says
"TexasSolver stays ON" — it would stay ON in non-plan pots and on the turn); (c) hook in `bot._postflop` before `:545`
(intervention in strategy code, byte-identity gate needed).
**Recommendation: (b)** — cleanest separation, latency target reachable, TexasSolver timeouts stay outside the
plan path; record it in the card as a deliberate clarification "TexasSolver stays ON except in plan pots (river)".

**E2. On which channel do G2/G5 run?** (B1) pargate = exploit ON/PRINCE off/resolver off. Options: (a) leave as is
and label it "gym channel" (non-regression bound, as before); (b) extend `_baue_fabrik` with
`exploit=False`/PRINCE env for v10 (intervention in the measurement foundation, separate A/A proof, env must be set before the bot
import in the worker). **Recommendation: (a) for G2 (A/A is a determinism test, channel-independent) + (b) as an
ADDITIONAL envgate arm for G5**, not as a replacement — the card must then say that G5 has two channels.

**E3. K1 base likelihood: advisor-only or two-part (resolver `strat` + advisor floor)?** (B2)
**Recommendation: two-part** — extend `resolver.river_resolve` with a sister function `river_strategy(...)` (distribution,
without `rng.choices`); but at the start of the river the prior history (flop/turn) is what plays — there the advisor is
correctly the floor, because the turn resolver is OFF in the gym. For the GTOW channel (turn resolver ON) report the TV acceptance
separately per channel.

**E4. Hand address for private randomization in the gym.** (B6) Options: (a) card hash `sorted(h0|h1|board)` +
seat (deck identity = card tuple; contains both hole cards of the DECK, but not as a function of hero's
decision — unproblematic in the mirror, not usable live); (b) inject `hand_id` in `duplicate._setup_fixed`
(intervention in the measurement foundation; bot.py already tolerates `state.get('hand_id')`, `bot.py:488-493`).
**Recommendation: (b) with A/A + resume identity test as acceptance**, because only (b) fulfils the card contract
"activation AND sampling key without hole cards"; do not touch `game.py` itself.

**E5. Deadline semantics in gym vs live.** (B3) A time deadline breaks A/A determinism. **Recommendation:** in the gym a
fixed ITERATION deadline (150 iters, no time abort); live additionally a 7.5 s time deadline in the guard (solve in a
thread/future, late result discarded, `deadline` status in the trace); `PokerBotMVP.act` on
`asyncio.to_thread` (model `poker_agent.py:208/285`).

**E6. K1 transformation turn_wert: bit-exact (CPU MC, `_spot_rng` per combo) or exact (GPU) with labeling?**
(B8) **Recommendation: reproduce bit-exactly** (the same MC path, iters=160, `_spot_rng` with hypothetical combo) —
otherwise G3 measures the approximation, not K1; the card's "equity vectorized (gpu_equity)" is to be struck or marked as an
approximation. Cost: 1326 x MC(160) per turn node ≈ tolerable (scout: ~50-80 ms/combo decide;
pure equity considerably cheaper).

**E7. Injection switch in `solve_spots`/`RiverSpot` (default unchanged) vs K2 uses `RiverCFRBatch` directly.**
(B5) **Recommendation: K2 uses `RiverCFRBatch` directly** (no intervention in `gpu_resolver.py` → r8_stack/r10_ernte
stay byte-identical, no new A/A proof for legacy arms); support mask + off-tree tolerance + cache in
`river_plan.py`.

**E8. Where does the per-hand ledger live if `main.py` is gitignored?** (B12) **Recommendation:** versioned module
`pokerbot/benchmark/gtow_ledger.py` + a minimal patch to `main.py._play_hand` documented in `docs/`
(hand start + hand end, `open('a')`+flush); fingerprint once per process in `PokerBotAgent.__init__`
(`gtowizard.py:183`) incl. `POKERB_AUSLESE_STACK`, git HEAD/dirty, .pt hashes, `bot.use_resolver/
use_turn_resolver/exploit`; misconfiguration gate there (SystemExit before the bot import).

**E9. Holdout definition K3.** (B13) **Recommendation:** holdout = the four night-1 files by name (A-D), arm
`v4_gym_nackt` reported as provenance; use only villain range/root geometry from them; parameterize `hh_luecken_mine.ARME`
instead of changing it; hero-seat reconstruction + exclusion counters in the report.

**E10. Adjust the card's numbers:** A/A 576 decks (or pin the workers); bank ledger new bank (e.g. 1080000);
latency gate end-to-end in a fresh process, stratified by SPR bucket; fix "stack 20000/50/100" as the unit;
correct `analyze_gtow_hands.py` to BB=100 before every K3/K5 report (or do not cite it).

**E11. K1 role convention** (B9): **Recommendation:** hero = INITIATIVE role (like `decide()`), villain = position
(like the tracker); measure the deviation in G3 separately by pot type (SRP/3bet). Allow `p_defense_batch` as an additive function
with an identity guard (correct capitalization `'IP'/'OOP'`) — the card would have to sharpen the exclusion
"advisor rebuild" to "no weight/feature change".

---

## D. WHAT THE CONTRACT (contracts.py, P0b) FIXES FROM THIS
- Public state WITHOUT hole cards (`PolicySnapshot`); action history as `(street, player, ActionKey)`
  on the channel intersection (A2), deal events are NOT kept as actions, board from `state['board']`.
- `ActionKey`: `fold|check|call|raise_to(chips:int)`; canonicalization = engine rule `int()` truncation + clamp to
  `legal.raise_min/raise_max` (`game.py:170`), `bet/raise/allin` → `raise_to`.
- `RangeState`: combo convention = `gpu_cfr.combo_index` (rank*4+suit, 'shdc', lexicographic pairs); weights
  unnormalized-scale-invariant OR normalized; board combos exactly 0 (hard); `hero_injiziert` must be False in the K1/K2 path.
- `PolicyTable`: rows Σ=1±1e-6; `undefiniert` set for reach-0 combos (never interpret as uniform, B10).
- `RiverPlan`: activation only from `pot_river` (public); status vocabulary `offtree|deadline|fehler|
  hand_not_in_range|keiner`; `private_seed_quelle` explicit.
- `EntscheidungsTrace`: `basis → texassolver → guards → plan_verteilung → legalitaet → sample_u → final`, where
  `texassolver` is kept as a REPLACEMENT (not an intervention) (B2).
