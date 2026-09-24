# Trainer wiring — as-is state after the build of 2026-09-09

Which bot plays in which mode with which chain, which exploit switch and which resolver.
Sources: `pokerbot/web/server.py` (HU app), `pokerbot/web/six_server.py` (6-max trainer), `pokerbot/coach/oracle.py`
(`PrinceOracle(stack=, kanal=)`), `pokerbot/arena/hybrid.py` (`HybridHero`), `pokerbot/strategy/auslese.py`.

| Mode / channel | Bot | Stack (AUSLESE chain) | Exploit | Resolver (river/turn) | Evidence |
|---|---|---|---|---|---|
| HU app opponent (`server.py`, `POKERB_AUSLESE=1` default) | `PokerBot` + PRINCE profile | `FINAL_STACK` = `r8_stack`, kanal `live` | OFF | ON (TexasSolver; `POKERB_RESOLVER=0` switches off) | `/api/view` → `fingerprints.bot` |
| HU app **advisor** for the human (`server.py`, NEW) | `PokerBot` (the human's seat), **identical config** | `r8_stack`, kanal `live` | OFF | ON | `fingerprints.advisor` — smoke: hash `fbb88ac7ffe4` == opponent; `GET /api/advice` |
| HU app with `POKERB_AUSLESE=0` (debug) | bare `PokerBot` | `basis` | ON (constructor) | OFF | fingerprint `stack='basis'` |
| 6-max trainer GTO mode, multiway (`six_server`) | `SixMaxBot` league, reads OFF | — | OFF | — | `Session.bots` |
| 6-max trainer GTO mode, pot heads-up hero-vs-bot (takeover) | `PrinceOracle` (Prince v2.2 + position-prior tracker) | **`FINAL_STACK` (`r8_stack`), kanal `live`** — env `POKERB_SIX_STACK` (`r10_stack` / `basis`) | OFF | OFF (response time; unchanged) | smoke: `SESSION.prince.stack == 'r8_stack'`, override `basis`→None, `r10_stack` |
| 6-max trainer exploit/arena mode | `SixMaxBot` league, reads ON | — | league reads (bounded) | — | no Prince |
| Analyzer export `research/sixmax_export.py --hybrid` | `HybridHero` (tag core + Prince, **without stack** = as before) | none (default `stack=None`) | OFF | OFF | byte-identical to the state before the move (plain 4550 B, hybrid 3550 B, n=4/3) |
| `pargate6` candidates | `tag` (reads OFF) / `tag_reads` / `hybrid` / `hybrid_r8` / `hybrid_r10` | — / — / None / `r8_stack` / `r10_stack`, kanal `gym` | OFF (reads only `tag_reads`) | OFF | `result.json` `zaehler.prince_decisions`, `aa_exakt_null` |
| `exploit_gate` HU arms | `PokerBot` **without PRINCE** (`POKERB_PRINCE=0`), projection as in the grader | `basis` | ON / OFF explicitly per arm (`POKERB_EXPLOIT`) | OFF | `fingerprints.exploit_on.exploit=True` / `exploit_off.exploit=False`, `prince=False` |

Prince takeover in the trainer: `kanal='live'` (K2 deadline/os.urandom only for `r10_stack`); for `r8_stack` the
channel has no effect. The AUSLESE import flags (`TURN_DEFENSE 0.07`, `SLOWPLAY 0.25`) are set by `server.py` via
`setze_env`; the 6-max launcher does NOT set them — `oracle.py` sets only `POKERB_PRINCE=1`. Whoever wants the takeover with the
full v5 env sets them in the launcher (`PokerB 6max spielen.bat`) — open point, deliberately not changed silently.

## Measurements (commands)

An A/A null test is mandatory BEFORE every series (smoke 24 decks ran: `bb100 0.0, se 0.0, nonzero 0, aa_exakt_null True`).

**1. 6-max candidate comparison, 3000 decks per candidate vs `tag` (one fleet at a time; ~2 s/deck/arm single-core):**
```powershell
python -m pokerbot.autogym.pargate6 --kandidat tag       --incumbent tag --decks 300  --workers 8   # A/A must be exactly 0
python -m pokerbot.autogym.pargate6 --kandidat hybrid    --incumbent tag --decks 3000 --workers 8
python -m pokerbot.autogym.pargate6 --kandidat hybrid_r8 --incumbent tag --decks 3000 --workers 8
python -m pokerbot.autogym.pargate6 --kandidat hybrid_r10 --incumbent tag --decks 3000 --workers 8
```
Result: `data/runs/<ts>_pargate6_<kand>/result.json` (bb100 = paired difference over 6 rotations per deck,
`bb100_kandidat`/`bb100_incumbent` = each arm vs league, `ci95_*`, `verdict` via `stats.verdikt`). Same `--workers`
per comparison (villain OppModels learn per job block).

**2. Exploit gate, 600 decks per profile (+ 6-max reads ON/OFF):**
```powershell
python -m pokerbot.autogym.exploit_gate --decks 600 --workers 8 --sixmax
```
Criterion pre-registered in `exploit_gate.py`: station/maniac/nit/whale diff ≥ 0 and CI lower bound > −3;
tag/shark not significantly negative. Smoke (56 decks, station/tag): station +52.1 ± 53.6 CI[−4.4, 160.7] →
at this n formally VIOLATED (CI too wide), tag +55.8 ± 53.6 correct — numbers without significance, mechanics proven.

**3. Analyzer export --hybrid n=1500 (ONLY the command; hand IDs burn on first contact — ledger
`data/runs/v10/g5_analyzer_ledger.json`, next proposal 132000 / day 91 / seed 1110 per STATE.md):**
```powershell
$env:POKERB_PRINCE="1"; python -m research.sixmax_export --hybrid --n 1500 --seed 1110 --idbase 132000 --dayoffset 91 --out data/gtow_upload/sixmax_hybrid_1500.txt
```
(CRLF mandatory before the upload; afterwards a ledger entry in STATE.md.)

## MEASUREMENT RESULTS (2026-09-09, logs data/runs/verdrahtung/, run storage data/runs/*_pargate6_*)

**6-max candidates (pargate6, hero rotates over 6 seats per deck, league tag/lag/nit/station/maniac seeded, 8 workers)**

| Candidate vs incumbent | Decks | bb/100 | CI95 | Verdict |
|---|---|---|---|---|
| tag vs tag (A/A) | 288 | 0.0 ± 0.0 | — | exactly 0 |
| hybrid (tag + Prince takeover, without chain) vs tag | 2992 | −23.56 ± 9.02 | [−40.8; −5.3] | REJECT |
| hybrid_r8 (takeover with r8_stack) vs tag | 2992 | −21.73 ± 9.01 | [−39.0; −4.4] | REJECT |
| hybrid_r10 (takeover with r10_stack) vs tag | 2992 | −26.61 ± 8.93 | [−43.9; −9.4] | REJECT |
| hybrid_r8 vs hybrid | 2992 | +1.82 ± 5.58 | — | NEUTRAL |

**Verdict:** The Prince takeover (HU projection of the PokerBot in HU-collapsed 6-max pots) hurts in the
6-max channel; the guard chain does not rescue it. Best measured 6-max bot = league core `tag`. Limitation:
self-ecology (tag plays against its own league). External anchor = Analyzer grade (tag core 85.9 % / 7.61;
hybrid never graded) → export command above. **Product decision:** `six_server` GTO mode plays the league core;
takeover only with `POKERB_SIX_TAKEOVER=1`.

**Exploit gate (HU, PokerBot without PRINCE, POKERB_EXPLOIT=1 vs 0 per arm in a fresh process, fingerprint confirmed,
600 paired decks per profile)**

| Profile | ON | OFF | Diff ON−OFF | CI95 |
|---|---|---|---|---|
| nit | +24.95 | +27.04 | −2.09 ± 9.52 | [−21.0; +15.9] |
| tag | −3.43 | +15.83 | −19.26 ± 15.35 | [−51.2; +8.2] |
| lag | −4.84 | +13.66 | −18.50 ± 12.96 | [−47.7; +3.6] |
| station | −11.62 | +5.73 | −17.35 ± 16.31 | [−51.8; +12.9] |
| maniac | −14.80 | +0.95 | −15.74 ± 9.61 | [−35.8; +2.5] |
| rock | +20.35 | +20.66 | −0.31 ± 8.97 | [−18.4; +16.9] |
| whale | −9.57 | −1.32 | −8.26 ± 17.01 | [−43.1; +23.5] |
| shark | +3.14 | +17.54 | −14.40 ± 13.67 | [−42.5; +9.6] |
| 6-max reads ON vs OFF (pargate6) | +22.77 | +19.14 | +3.64 ± 13.45 | [−22.0; +30.9] |

**Verdict:** All eight HU point estimates ≤ 0, pooled ≈ −12 bb/100 (SE ≈ 4.5): the Dirichlet river exploit
(`bot.py:_river_exploit`) loses against every league profile, even against the exploitable ones. "Exploit mode correct"
is thereby not shown but refuted for this path (consistent with PRINCE = exploit OFF and the GTOW
finding). 6-max reads are neutral (harmless). **Product decision:** exploit stays OFF in all modes; the
`six_server` mode "exploit" (reads) remains as a game-feel variant. A real exploit would need a new
mechanism (selection instead of frequency, more than river-only) with this gate as acceptance.


## Pre-fold (User, 2026-09-09) — more hands per hour

**What:** As long as the opponents act before you, the waiting bar on the left shows "Fold vorab" (key F). A click
sets `POST /api/prefold`: the server plays the hand to the end IMMEDIATELY in the background — bots act, the hero
folds at his turn regularly via `human_action("fold")` (decision capture, grading, tournament verdict like a
normal fold), the chips move correctly. The client only shows the result (board, winner, log) and
deals the next hand automatically after 1.5 s (`T.PREFOLD_NEXT`).
**Special cases:** if no bet reaches the hero (free check, e.g. BB without a raise), the pre-fold
is lifted and the hero is normally to act (`prefold: "check_frei"`) — a fold instead of a free check would be pure
EV loss; if everyone folds before him, he wins uncontested (`"kampflos"`). Double pre-fold → 400.
**Click race / layout (user QA):** the pre-fold IS the fold button (same `mk('Fold',…)`, class
`fold`, label "Fold") and sits PIXEL-IDENTICAL at the position of the real fold button. Layout of the row
(`btnRow`): two halves of 50 % each — left [Fold][Check/Call] right-aligned, right [Raise][All-in] left-aligned —
so the middle between call and raise lies EXACTLY below the middle of the hero cards (measured: both x 384);
missing buttons become invisible placeholders (`.ph`, min-width 200), the waiting bar carries the size row
as a placeholder with the waiting text (fold in both states x 161.1 / y 490.5). Additionally the action bar is locked for 350 ms on the transition waiting →
"you're up" (`.bar.lock`, `T.TURN_LOCK`) — in the first browser test a late
click otherwise landed on "Raise" (27 bb with 32s). The history ticker now sits BELOW the action bar (previously
overlapped the hero seat with 10 seats).
**"Doesn't always work" (user QA, fixed):** two causes — (1) `api()` answers `busy` while a
`/api/step` is running (every 420 ms); a click in this window fizzled silently → `prefold()` now waits for the
running request (which is still rendered regularly), only then halts the step loop; (2) the waiting bar
was rebuilt on every step, a click between mousedown/mouseup was lost → the waiting-bar DOM
stays in place (`bar.dataset.state`). Re-measurement: 6 real clicks, 4 in the waiting state → 4/4 pre-folds.
**Tests:** `python -m tests.test_prefold` (chip conservation, hero folded + hand over in one call, fold as
a graded decision, double fold rejected, tournament verdict, special cases). Applies to all modes of the 6-max
trainer (`training.html`); the HU app (`server.py`) has no pre-fold.
