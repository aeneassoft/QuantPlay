# V10 K4 — Ledger-Patch fuer den gitignorierten GTOW-Client (2026-09-07, Paket P4)

**Warum ein dokumentierter Patch statt Code im Repo:** `tools/` ist gitignored (`.gitignore:9`); die
Hand-Schleife `_play_hand` lebt NUR in `tools/gtow_client/src/main.py` (V10_FAKTEN A8: „Hook-Punkt fuer
Per-Hand-Ledger existiert nur in main.py"). Alles Fachliche ist versioniert in
`pokerbot/benchmark/gtow_ledger.py` (E8); der Client bekommt ausschliesslich zwei exception-freie Hooks.
Reproduzierbar: nach jedem frischen Clone des Clients den Diff unten anwenden (`git apply` geht nicht, weil
gitignored — Handpatch, 4 Bloecke, ~15 Zeilen).

## Was das Ledger liefert (Karte K4)
- `data/runs/v10/ledger_<prozess-start>.jsonl`, append-only, `open('a')`+`flush`+`fsync` je Ereignis.
  gtow_nacht spawnt je Chunk einen frischen Prozess → eine Datei je Chunk (`POKERB_LEDGER_PFAD` ueberschreibt).
- `prozess_start` (kompletter Fingerprint aus `pokerbot/runtime_config.fingerprint_geladen`, geschrieben in
  `PokerBotAgent.__init__`), `hand_start(hand_id, arm, fingerprint_hash)`, `hand_end(hand_id, aivat, winnings,
  status ok|unbekannt|fehler, technische_events)`. `None` wird NIE zu 0; `ok` ohne AIVAT wird `unbekannt`.
- Arm-Name: `POKERB_ARM` (gtow_nacht_v10 setzt ihn je Chunk), sonst `PokerBotAgent.stack_name`.
- Wiederanlauf: `python -m pokerbot.benchmark.gtow_ledger` listet offene Haende (start ohne end) je Datei —
  der Abgleich VOR `clear_inprogress.py` (K5: „clear_inprogress erst nach Abgleich").

## Diff `tools/gtow_client/src/main.py` (Original = Stand 2026-09-07, 390 Zeilen, CRLF)

```diff
@@ -25,6 +25,11 @@
 )
 from utils import is_engine_busy_exception

+try:                                            # K4-Ledger (versioniert in pokerbot/, docs/V10_LEDGER_PATCH.md)
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

**Begruendung je Block:** (1) Import in `try` — `pokerbot` kommt ueber `PYTHONPATH` aus `tools/gtow_run.py:20`;
fehlt er (Client direkt gestartet), laeuft der Benchmark wie zuvor, nur ohne Ledger. (2) `hand_start` sofort nach
`hand_id`-Vergabe — die Hand ist ab hier serverseitig „in progress", genau diese IDs braucht der clear_inprogress-
Abgleich. (3) `hand_end` mit dem Terminalzustand — der Agent sieht ihn nie (`while not is_hand_over`), nur die
Schleife. (4) Die beiden `except`-Zweige markieren den Ausgang als `fehler` MIT Ereignis (HTTP-Status bzw.
Exception-Klasse) statt ihn stumm zu verlieren. Alle `melde_*` schlucken jede Exception
(`gtow_ledger.py`, Fault-Injection-Test `tests/test_runtime_config.py::test_fault_injection_ledger_write_bricht_lauf_nicht`).

## Zweiter (NICHT angewandter) Patch — E5 `PokerBotMVP.act` via `asyncio.to_thread`
`PokerBotMVP` lebt in `tools/gtow_client/src/poker_agent.py:59-71` (gitignored, fuer P4 nur-lesen). Die
versionierte Seite ist fertig: `PokerBotAgent.act_async(gsr)` (`pokerbot/benchmark/gtowizard.py`) laeuft
`act_dict` in `asyncio.to_thread` und serialisiert die Entscheidungen ueber `_decide_lock` (decide mutiert
Tracker-Zustand). Der Client-Patch (2 Zeilen, vom Integrator anzuwenden):

```diff
     async def act(self, game_state: GameServiceResponse) -> ActRequest:
         gsr = game_state.model_dump()
         if game_state.game_state.is_hand_over:
             self._a.hand_end(gsr)
             return ActRequest(action="k")
-        return ActRequest(**self._a.act_dict(gsr))
+        return ActRequest(**await self._a.act_async(gsr))     # E5: Event-Loop bleibt fuer parallele Haende frei
```

Ohne diesen Patch blockiert der synchrone `act_dict` weiterhin ALLE parallelen Haende (V10_FAKTEN A8); der
Ledger funktioniert unabhaengig davon. **Status (Review-Fixrunde 2026-09-07): weiterhin NICHT angewandt**
(`grep -n act_dict tools/gtow_client/src/poker_agent.py` → `74: return ActRequest(**self._a.act_dict(gsr))`);
Karte E5 und das K5-Latenz-Gate (E10) gelten damit NICHT als erfuellt, bis der Integrator patcht.

**Nachweis der versionierten Haelfte (E5-Heartbeat, `tests/test_runtime_config.py::_e5_parallele_haende`):**
zwei Haende entscheiden gleichzeitig ueber `act_async`, decide kuenstlich auf 0,25 s verlangsamt, ein Heartbeat-Task
tickt alle 20 ms. Gemessen: `act_async` (to_thread) = **9 Ticks**; derselbe Aufbau mit dem heutigen synchronen
Pfad (`act_dict` direkt im Loop, = poker_agent.py:74) = **1 Tick** → Schwelle 5 trennt sauber; der --gtow-Smoke
druckt `E5_LOOP_FREI ticks=9`. Die Entscheidungen bleiben ueber `_decide_lock` serialisiert (Tracker-Zustand),
nur der Loop ist frei.

**Abnahme nach dem Client-Patch (Integrator):** `POKERB_K4_E5_PFLICHT=1 python -m unittest
tests.test_runtime_config.SubprozessSmokeTest.test_e5_client_patch_status` muss GRUEN sein (prueft
`await self._a.act_async(` vorhanden UND kein synchroner `act_dict`-Aufruf mehr). Ohne den Patch ist der Test
ein Skip mit Klartext „E5 NICHT LIVE"; mit `POKERB_K4_E5_PFLICHT=1` ist er ROT (gegen-geprueft 2026-09-07).
Danach ein echter 2-Haende-Lauf (`parallel_hands=2`) mit Ledger: die `hand_start`-Zeitstempel beider Haende
muessen sich ueberlappen, waehrend eine Entscheidung laeuft.

## Fingerprint-Hash: warm-up-/prozess-invariant (Review-Fix 2026-09-07)
Reviewer-Befund (HOCH, bestaetigt durch eigene Reproduktion): `advisor_pt.geladen_jetzt` — welche Netze der
Lazy-Cache IM MOMENT haelt (advisor.py:54-71) — ging in den Hash ein. Kalt `88d73d6e…` vs nach
`advisor._load(*)` `77713e6a…` im selben Prozess; im HU-Server kippte damit schon die zweite Session. Fix in
`pokerbot/runtime_config.py`: das Feld heisst jetzt Top-Level `advisor_geladen_jetzt` (bleibt als Diagnose im
Fingerprint/Ledger sichtbar) und steht in `_NICHT_IM_HASH`; `advisor_pt` traegt nur noch `sha256` + `fehlend`
(Dateiinhalt = Konfiguration). Nachweise: Reproduktion nach Fix `kalt 94281a97… == warm 94281a97… GLEICH True`;
--gtow-Smoke kalt vs. Prozess mit `K4_SMOKE_WARM_FIRST=1` (alle Netze VOR dem Agenten geladen): beide
`fp=3204ec7e2332…`; --server-Smoke Session 1 (`geladen_jetzt=[]`) vs Session 2 nach explizitem Warm-up (5 Netze):
beide `cee8c8bf801f…`. Tests dafuer: `test_hash_ist_warmup_invariant` (in-Prozess), Subprozess-Vergleich in
`test_gtow_adapter_e8_e5`, Session-Vergleich in `_server_smoke`.

## Gatter prueft den GELADENEN PRINCE-Zustand, nicht die Env-Absicht (Review-Fixrunde 2, 2026-09-07)
Reviewer-Befund (HOCH, reproduziert): `fingerprint['prince'] = gto_mode.prince_enabled()` ist die ENV-Absicht.
Wird `pokerbot.strategy.bot` VOR `POKERB_PRINCE=1` importiert, frieren `_TURN_DEFENSE/_SLOWPLAY/_LINE_U/
_RIVER_ECALL` (bot.py:84-98) auf ihren Defaults ein; `apply()` danach aendert nur noch die Env. Vorher: Fingerprint
`prince=True, turn_defense=0.0` → das v5-H-Gatter passierte (`gatter -> v5-H`, kein SystemExit). Fix in
`pokerbot/runtime_config.py`:
- `_PRINCE_IMPORTKONSTANTEN` = die sechs PRINCE-Flags, die Strategie-Module bei Import einfrieren (bot.py
  TURN_DEFENSE/SLOWPLAY/LINE_U/RIVER_ECALL, resolver.py:117 SIZE_INJECT, range_tracker.py:79 TRACKER_AGGRO_FULL);
  Sollwerte aus `gto_mode.PRINCE_PROFILE` (nie getippt, Test `test_profil_sollwerte_stammen_aus_prince_profile`).
- Neue Fingerprint-Felder (Pflicht, im Hash): `prince_importflags` (eingefrorene Werte), `prince_geladen`
  (= alle sechs stimmen UND exploit False), `prince_abweichungen` (Klartext je Abweichung).
- `ERWARTUNGSPROFILE v5-H/v10` pruefen jetzt `prince_geladen: True`, `turn_defense: 0.07`, `slowplay: 0.25`
  ZUSAETZLICH zu `prince` (die Env-Absicht bleibt relevant, weil resolver/postflop weitere Profil-Flags zur
  LAUFZEIT ueber `gto_mode.flag` lesen). Die Abbruchmeldung nennt die eingefrorene Konstante
  („prince_abweichungen (Modul VOR der Env importiert?): POKERB_TURN_DEFENSE: soll 0.07, geladen 0.0; …").
- Tests, die den Befund kuenftig rot machen: `GatterTest.test_reviewer_repro_bot_vor_env_importiert_bricht_ab`
  (in-Prozess, exakt die Reviewer-Reproduktion, Env wird restauriert) und
  `SubprozessSmokeTest.test_gtow_bot_vor_env_importiert_bricht_ab` (echter Adapter-Pfad: bot importiert, dann
  PRINCE/AUSLESE_STACK, dann `PokerBotAgent()` → Prozess endet != 0 mit `FEHLKONFIGURATION … prince_geladen`).
- Positivpfad (Env VOR Import, Server + Adapter) druckt jetzt `[K4] Fingerprint … {'prince': True,
  'prince_geladen': True, …, 'turn_defense': 0.07, 'slowplay': 0.25} == Profil v5-H: OK`.
- Hash-Konsequenz: neue gehashte Felder → `fingerprint_hash` aller frueheren Test-Ledger ist nicht vergleichbar
  (es existieren keine produktiven Ledger; `data/runs/v10` traegt 0 Ledger-Dateien).

## E5-Laufzeitnachweis im Ledger (Review-Fixrunde 2, 2026-09-07)
Der Client-Patch (oben) bleibt Integrator-Sache und ist weiterhin NICHT angewandt (`poker_agent.py:74`). Damit ein
Lauf ohne den Patch nicht stumm als E10-Latenzbeleg gilt, wird der Zustand jetzt GEMESSEN statt aus der gitignorierten
Quelle geraten: `PokerBotAgent.act_dict` zaehlt Aufrufe, die im Thread eines laufenden Event-Loops stattfinden
(`_zaehle_loop_blockade`, `asyncio.get_running_loop()`; `act_async` laeuft im Worker-Thread → zaehlt nicht), warnt
einmal auf stderr (`[K4/E5] WARNUNG: act_dict synchron im Event-Loop gerufen …`), und `gtow_ledger.melde_hand_ende`
schreibt je Hand das technische Ereignis `e5_sync_act_dict:<n>` (kumulativer Prozess-Zaehler). Regel fuer das
Gate-Protokoll: **ein Ledger mit `e5_sync_act_dict` ist KEIN E5-/E10-Beleg**; E5 und E10 sind bis zum Client-Patch
OFFEN. Nachweise: `--gtow`-Smoke druckt `E5_SYNC_ERKANNT loop_blockierende_aufrufe=1 nach act_dict im Loop, 0 nach
act_async` und `E5_LOOP_FREI ticks=9`; `LedgerTest.test_melde_hooks_lesen_aivat_aus_terminal` prueft das Ereignis
(3 → `e5_sync_act_dict:3`, 0 → keins).

## Verifikation (2026-09-07, nach Review-Fixrunde 2)
- `python -m tests.test_runtime_config` — 19 Tests, OK (skipped=1 = der E5-Client-Patch-Status): zusaetzlich
  Reviewer-Repro in-Prozess + Adapter-Subprozess (bot vor Env → Abbruch), Profil-Sollwerte aus PRINCE_PROFILE,
  E5-Zaehler im Smoke + Ledger-Ereignis.
- Golden-Set r8_stack vs basis, 40 Decks, Seed 424242: `IDENTISCH` (pre vs `golden_r8_vs_basis_post_P4fix2.json`,
  nonzero 16, Summe +11588 Chips).

## Verifikation (2026-09-07, nach der Review-Fixrunde 1)
- `python -m tests.test_runtime_config` — 16 Tests, OK (skipped=1 = der E5-Client-Patch-Status, s.o.):
  Fingerprint-Pflichtfelder + Warm-up-Invarianz, Gatter, Ledger-Abbruch/Wiederanlauf/Doppel-IDs/abgeschnittene
  Zeile, Fault-Injection, D1-Server-Smoke via TestClient (Session-1/2-Hash), GTOW-Adapter-Smoke E8/E5 mit
  `POKERB_ERWARTE_PROFIL=v5-H` (kalt + warm-first, Heartbeat) inkl. Negativfall `POKERB_RESOLVER=0` → SystemExit.
- `python -m pokerbot.benchmark.gtowizard` (Offline-Selbsttest) laeuft weiter; Achtung: er schreibt ein
  `prozess_start`-Ledger nach `data/runs/v10/` (setze `POKERB_LEDGER_PFAD`, wenn das stoert).
- Golden-Set r8_stack vs basis, 40 Decks, Seed 424242: `IDENTISCH` (pre vs post_P4 und pre vs post_P4fix,
  `data/runs/v10/golden_r8_vs_basis_post_P4fix.json`: nonzero 16, Summe +11588 Chips).
