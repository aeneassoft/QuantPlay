# V10 K4 — Ledger patch for the gitignored GTOW client (2026-09-07, package P4)

**Why a documented patch instead of code in the repo:** `tools/` is gitignored (`.gitignore:9`); the
hand loop `_play_hand` lives ONLY in `tools/gtow_client/src/main.py` (V10_FAKTEN A8: "hook point for a
per-hand ledger exists only in main.py"). Everything substantive is versioned in
`pokerbot/benchmark/gtow_ledger.py` (E8); the client receives exclusively two exception-free hooks.
Reproducible: after every fresh clone of the client apply the diff below (`git apply` does not work because
gitignored — hand patch, 4 blocks, ~15 lines).

## What the ledger delivers (card K4)
- `data/runs/v10/ledger_<process-start>.jsonl`, append-only, `open('a')`+`flush`+`fsync` per event.
  gtow_nacht spawns a fresh process per chunk → one file per chunk (`POKERB_LEDGER_PFAD` overrides).
- `prozess_start` (complete fingerprint from `pokerbot/runtime_config.fingerprint_geladen`, written in
  `PokerBotAgent.__init__`), `hand_start(hand_id, arm, fingerprint_hash)`, `hand_end(hand_id, aivat, winnings,
  status ok|unbekannt|fehler, technische_events)`. `None` NEVER becomes 0; `ok` without AIVAT becomes `unbekannt`.
- Arm name: `POKERB_ARM` (gtow_nacht_v10 sets it per chunk), otherwise `PokerBotAgent.stack_name`.
- Restart: `python -m pokerbot.benchmark.gtow_ledger` lists open hands (start without end) per file —
  the reconciliation BEFORE `clear_inprogress.py` (K5: "clear_inprogress only after reconciliation").

## Diff `tools/gtow_client/src/main.py` (original = state 2026-09-07, 390 lines, CRLF)

```diff
@@ -25,6 +25,11 @@
 )
 from utils import is_engine_busy_exception

+try:                                            # K4-Ledger (versioniert in pokerbot/, V10_LEDGER_PATCH.md)
+    from pokerbot.benchmark import gtow_ledger as _ledger
+except Exception:  # noqa: BLE001 — pokerbot nicht auf dem PYTHONPATH -> Lauf ohne Ledger, nie Abbruch
+    _ledger = None
+
 _DEFAULT_GAME_NAME = "HUNL 200BB"
@@ -162,20 +167,28 @@
             try:
                 game_service_response = await self._create_new_hand()
                 hand_id = game_service_response.hand_id
+                if _ledger:                                                    # K4: hand_start(hand_id, arm, fp-hash)
+                    _ledger.melde_hand_start(self._agent, hand_id)

                 while not game_service_response.game_state.is_hand_over:
                     game_service_response = await self._act(hand_id, game_service_response)
+                if _ledger:                                                    # K4: hand_end mit AIVAT/winnings
+                    _ledger.melde_hand_ende(self._agent, hand_id, game_service_response)
                 return game_service_response          # terminal state carries winnings + aivat_score
             except httpx.HTTPStatusError as e:
                 logger.error(
                     f"{_format_http_error(e)} after exhausting retries",
                     extra={"hand_id": hand_id, "response_text": e.response.text},
                 )
+                if _ledger and hand_id is not None:                            # K4: Ausgang unbekannt, nie 0
+                    _ledger.melde_hand_ende(self._agent, hand_id, None, "fehler", [f"http_{e.response.status_code}"])
                 if not is_engine_busy_exception(e):
                     raise
                 return None
             except Exception as e:
                 logger.error(f"Unexpected error: {e}", extra={"hand_id": hand_id})
+                if _ledger and hand_id is not None:
+                    _ledger.melde_hand_ende(self._agent, hand_id, None, "fehler", [type(e).__name__])
                 return None
```

**Rationale per block:** (1) import in `try` — `pokerbot` comes via `PYTHONPATH` from `tools/gtow_run.py:20`;
if it is missing (client started directly), the benchmark runs as before, just without the ledger. (2) `hand_start` immediately after
the `hand_id` is assigned — from here on the hand is server-side "in progress", exactly these IDs are what the clear_inprogress
reconciliation needs. (3) `hand_end` with the terminal state — the agent never sees it (`while not is_hand_over`), only the
loop does. (4) The two `except` branches mark the outcome as `fehler` WITH an event (HTTP status or
exception class) instead of losing it silently. All `melde_*` swallow every exception
(`gtow_ledger.py`, fault-injection test `tests/test_runtime_config.py::test_fault_injection_ledger_write_bricht_lauf_nicht`).

## Second (NOT applied) patch — E5 `PokerBotMVP.act` via `asyncio.to_thread`
`PokerBotMVP` lives in `tools/gtow_client/src/poker_agent.py:59-71` (gitignored, read-only for P4). The
versioned side is finished: `PokerBotAgent.act_async(gsr)` (`pokerbot/benchmark/gtowizard.py`) runs
`act_dict` in `asyncio.to_thread` and serializes the decisions via `_decide_lock` (decide mutates
tracker state). The client patch (2 lines, to be applied by the integrator):

```diff
     async def act(self, game_state: GameServiceResponse) -> ActRequest:
         gsr = game_state.model_dump()
         if game_state.game_state.is_hand_over:
             self._a.hand_end(gsr)
             return ActRequest(action="k")
-        return ActRequest(**self._a.act_dict(gsr))
+        return ActRequest(**await self._a.act_async(gsr))     # E5: Event-Loop bleibt fuer parallele Haende frei
```

Without this patch the synchronous `act_dict` continues to block ALL parallel hands (V10_FAKTEN A8); the
ledger works independently of it. **Status (review fix round 2026-09-07): still NOT applied**
(`grep -n act_dict tools/gtow_client/src/poker_agent.py` → `74: return ActRequest(**self._a.act_dict(gsr))`);
card E5 and the K5 latency gate (E10) therefore do NOT count as fulfilled until the integrator patches.

**Proof of the versioned half (E5 heartbeat, `tests/test_runtime_config.py::_e5_parallele_haende`):**
two hands decide simultaneously via `act_async`, decide artificially slowed to 0.25 s, a heartbeat task
ticks every 20 ms. Measured: `act_async` (to_thread) = **9 ticks**; the same setup with today's synchronous
path (`act_dict` directly in the loop, = poker_agent.py:74) = **1 tick** → threshold 5 separates cleanly; the --gtow smoke
prints `E5_LOOP_FREI ticks=9`. The decisions remain serialized via `_decide_lock` (tracker state),
only the loop is free.

**Acceptance after the client patch (integrator):** `POKERB_K4_E5_PFLICHT=1 python -m unittest
tests.test_runtime_config.SubprozessSmokeTest.test_e5_client_patch_status` must be GREEN (checks
`await self._a.act_async(` present AND no synchronous `act_dict` call any more). Without the patch the test is
a skip with the plain text "E5 NICHT LIVE"; with `POKERB_K4_E5_PFLICHT=1` it is RED (cross-checked 2026-09-07).
Then a real 2-hand run (`parallel_hands=2`) with ledger: the `hand_start` timestamps of both hands
must overlap while a decision is running.

## Fingerprint hash: warm-up/process-invariant (review fix 2026-09-07)
Reviewer finding (HIGH, confirmed by own reproduction): `advisor_pt.geladen_jetzt` — which nets the
lazy cache holds AT THE MOMENT (advisor.py:54-71) — went into the hash. Cold `88d73d6e…` vs after
`advisor._load(*)` `77713e6a…` in the same process; in the HU server the second session already flipped because of this. Fix in
`pokerbot/runtime_config.py`: the field is now the top-level `advisor_geladen_jetzt` (remains visible as diagnostics in the
fingerprint/ledger) and is in `_NICHT_IM_HASH`; `advisor_pt` now carries only `sha256` + `fehlend`
(file content = configuration). Evidence: reproduction after the fix `kalt 94281a97… == warm 94281a97… GLEICH True`;
--gtow smoke cold vs. a process with `K4_SMOKE_WARM_FIRST=1` (all nets loaded BEFORE the agent): both
`fp=3204ec7e2332…`; --server smoke session 1 (`geladen_jetzt=[]`) vs session 2 after explicit warm-up (5 nets):
both `cee8c8bf801f…`. Tests for this: `test_hash_ist_warmup_invariant` (in-process), subprocess comparison in
`test_gtow_adapter_e8_e5`, session comparison in `_server_smoke`.

## The gate checks the LOADED PRINCE state, not the env intent (review fix round 2, 2026-09-07)
Reviewer finding (HIGH, reproduced): `fingerprint['prince'] = gto_mode.prince_enabled()` is the ENV intent.
If `pokerbot.strategy.bot` is imported BEFORE `POKERB_PRINCE=1`, `_TURN_DEFENSE/_SLOWPLAY/_LINE_U/
_RIVER_ECALL` (bot.py:84-98) freeze at their defaults; `apply()` afterwards only changes the env. Before: fingerprint
`prince=True, turn_defense=0.0` → the v5-H gate passed (`gatter -> v5-H`, no SystemExit). Fix in
`pokerbot/runtime_config.py`:
- `_PRINCE_IMPORTKONSTANTEN` = the six PRINCE flags that strategy modules freeze at import (bot.py
  TURN_DEFENSE/SLOWPLAY/LINE_U/RIVER_ECALL, resolver.py:117 SIZE_INJECT, range_tracker.py:79 TRACKER_AGGRO_FULL);
  target values from `gto_mode.PRINCE_PROFILE` (never typed, test `test_profil_sollwerte_stammen_aus_prince_profile`).
- New fingerprint fields (mandatory, in the hash): `prince_importflags` (frozen values), `prince_geladen`
  (= all six match AND exploit False), `prince_abweichungen` (plain text per deviation).
- `ERWARTUNGSPROFILE v5-H/v10` now check `prince_geladen: True`, `turn_defense: 0.07`, `slowplay: 0.25`
  IN ADDITION to `prince` (the env intent stays relevant because resolver/postflop read further profile flags at
  RUNTIME via `gto_mode.flag`). The abort message names the frozen constant
  ("prince_abweichungen (Modul VOR der Env importiert?): POKERB_TURN_DEFENSE: soll 0.07, geladen 0.0; …").
- Tests that will make the finding red in future: `GatterTest.test_reviewer_repro_bot_vor_env_importiert_bricht_ab`
  (in-process, exactly the reviewer reproduction, env is restored) and
  `SubprozessSmokeTest.test_gtow_bot_vor_env_importiert_bricht_ab` (real adapter path: bot imported, then
  PRINCE/AUSLESE_STACK, then `PokerBotAgent()` → process ends != 0 with `FEHLKONFIGURATION … prince_geladen`).
- Positive path (env BEFORE import, server + adapter) now prints `[K4] Fingerprint … {'prince': True,
  'prince_geladen': True, …, 'turn_defense': 0.07, 'slowplay': 0.25} == Profil v5-H: OK`.
- Hash consequence: new hashed fields → `fingerprint_hash` of all earlier test ledgers is not comparable
  (no productive ledgers exist; `data/runs/v10` carries 0 ledger files).

## E5 runtime proof in the ledger (review fix round 2, 2026-09-07)
The client patch (above) remains the integrator's business and is still NOT applied (`poker_agent.py:74`). So that a
run without the patch does not silently count as E10 latency evidence, the state is now MEASURED instead of guessed from the gitignored
source: `PokerBotAgent.act_dict` counts calls that take place in the thread of a running event loop
(`_zaehle_loop_blockade`, `asyncio.get_running_loop()`; `act_async` runs in the worker thread → does not count), warns
once on stderr (`[K4/E5] WARNUNG: act_dict synchron im Event-Loop gerufen …`), and `gtow_ledger.melde_hand_ende`
writes per hand the technical event `e5_sync_act_dict:<n>` (cumulative process counter). Rule for the
gate protocol: **a ledger with `e5_sync_act_dict` is NO E5/E10 evidence**; E5 and E10 are OPEN until the client patch.
Evidence: the `--gtow` smoke prints `E5_SYNC_ERKANNT loop_blockierende_aufrufe=1 nach act_dict im Loop, 0 nach
act_async` and `E5_LOOP_FREI ticks=9`; `LedgerTest.test_melde_hooks_lesen_aivat_aus_terminal` checks the event
(3 → `e5_sync_act_dict:3`, 0 → none).

## Verification (2026-09-07, after review fix round 2)
- `python -m tests.test_runtime_config` — 19 tests, OK (skipped=1 = the E5 client patch status): additionally
  reviewer repro in-process + adapter subprocess (bot before env → abort), profile target values from PRINCE_PROFILE,
  E5 counter in smoke + ledger event.
- Golden set r8_stack vs basis, 40 decks, seed 424242: `IDENTISCH` (pre vs `golden_r8_vs_basis_post_P4fix2.json`,
  nonzero 16, sum +11588 chips).

## Verification (2026-09-07, after review fix round 1)
- `python -m tests.test_runtime_config` — 16 tests, OK (skipped=1 = the E5 client patch status, see above):
  fingerprint mandatory fields + warm-up invariance, gate, ledger abort/restart/duplicate IDs/truncated
  line, fault injection, D1 server smoke via TestClient (session-1/2 hash), GTOW adapter smoke E8/E5 with
  `POKERB_ERWARTE_PROFIL=v5-H` (cold + warm-first, heartbeat) incl. negative case `POKERB_RESOLVER=0` → SystemExit.
- `python -m pokerbot.benchmark.gtowizard` (offline self-test) still runs; note: it writes a
  `prozess_start` ledger to `data/runs/v10/` (set `POKERB_LEDGER_PFAD` if that is a nuisance).
- Golden set r8_stack vs basis, 40 decks, seed 424242: `IDENTISCH` (pre vs post_P4 and pre vs post_P4fix,
  `data/runs/v10/golden_r8_vs_basis_post_P4fix.json`: nonzero 16, sum +11588 chips).
