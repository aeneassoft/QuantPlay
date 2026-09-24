"""K4 Produktionsintegritaet — Tests fuer runtime_config (Fingerprint + Gatter) und gtow_ledger (append-only Ledger).

    python -m tests.test_runtime_config            # alle Tests (unittest; kein pytest im Repo-Interpreter)
    python -m tests.test_runtime_config --server   # nur der D1-Server-Smoke (eigener Prozess: PRINCE-Env vor bot-Import)
    python -m tests.test_runtime_config --gtow     # nur der GTOW-Adapter-Smoke (E8 setze_env vor Import, E5 act_async)
    python -m tests.test_runtime_config --gtow-bot-vor-env   # Negativfall: bot VOR der Env importiert -> Gatter muss abbrechen

Die beiden Smokes laufen als SUBPROZESS, weil server.py/gtowizard.py ihre Env VOR dem Import von
pokerbot.strategy.bot setzen (Import-Zeit-Konstanten) — im Testprozess ist bot.py bereits importiert.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from pokerbot import runtime_config as rc
from pokerbot.benchmark import gtow_ledger as gl

# KEIN Modul-Import von pokerbot.strategy.bot: die Smoke-Modi (--server/--gtow) muessen ihre Env VOR dem ersten
# bot-Import setzen (Import-Zeit-Konstanten TURN_DEFENSE/SLOWPLAY, bot.py:95-98) — genau der Fehler, den K4 jagt.

SCRATCH = Path(tempfile.mkdtemp(prefix="k4_test_"))
_SMOKE_TIMEOUT_S = 600            # Bot-Import + TexasSolver-faehiger Bot: kalt ~10-30 s, grosszuegig
ENV_SMOKE_WARM_FIRST = "K4_SMOKE_WARM_FIRST"   # --gtow: alle Advisor-Netze VOR dem Agenten laden (Warm-up-Invarianz)
ENV_E5_PFLICHT = "POKERB_K4_E5_PFLICHT"        # =1 sobald der Integrator den Client-Patch angewandt hat -> Test wird scharf
_CLIENT_AGENT_DATEI = Path(__file__).resolve().parents[1] / "tools" / "gtow_client" / "src" / "poker_agent.py"
_E5_CLIENT_PATCH = "await self._a.act_async("   # docs/reports/V10_LEDGER_PATCH.md 'Zweiter Patch'
_E5_SIMULIERTE_LATENZ_S = 0.25                  # kuenstliche decide-Dauer, damit der Heartbeat-Test deterministisch ist
_E5_HEARTBEAT_S = 0.02
_E5_MIN_TICKS = 5                               # blockierte der Loop, saehe der Heartbeat waehrend decide 0 Ticks


def _bot(exploit: bool = False, resolver: bool = True):
    from pokerbot.strategy.bot import PokerBot
    b = PokerBot(0, seed=1, exploit=exploit)
    b.use_resolver = resolver
    b.use_turn_resolver = resolver
    return b


def _advisor_warmup() -> None:
    """Alle Advisor-Netze in den Lazy-Cache laden (advisor.py:54-71, 164-180) — der Zustand nach dem ersten River."""
    from pokerbot.strategy import advisor
    for street in advisor._FILES:
        advisor._load(street)
    advisor._load_defense()


# ================================================================ Fingerprint
class FingerprintTest(unittest.TestCase):
    def test_pflichtfelder_und_stabiler_hash(self):
        fp = rc.fingerprint_geladen(_bot(), "r8_stack")
        fehlend = [k for k in rc.PFLICHTFELDER if k not in fp]
        self.assertEqual(fehlend, [], f"Pflichtfelder fehlen: {fehlend}")
        self.assertEqual(fp["stack"], "r8_stack")
        self.assertEqual(set(fp["prince_importflags"]), {k for k, *_ in rc._PRINCE_IMPORTKONSTANTEN})
        self.assertEqual(fp["prince_geladen"], fp["prince_abweichungen"] == [])
        self.assertIs(fp["exploit"], False)
        self.assertIs(fp["use_resolver"], True)
        self.assertIn("POKERB_AUSLESE_STACK", fp["gto_mode_flags"], "E8: Stack-Key gehoert in die Fingerprint-Keys")
        self.assertEqual(fp["git"]["status"], "ok")
        self.assertRegex(fp["git"]["head"], r"^[0-9a-f]{40}$")
        # Hash: prozess-invariant (pid/zeit ausgeschlossen), aber sensitiv auf jede Strategie-Achse
        fp2 = rc.fingerprint_geladen(_bot(), "r8_stack")
        self.assertEqual(fp["fingerprint_hash"], fp2["fingerprint_hash"])
        self.assertNotEqual(fp["fingerprint_hash"], rc.fingerprint_geladen(_bot(exploit=True), "r8_stack")["fingerprint_hash"])
        self.assertNotEqual(fp["fingerprint_hash"], rc.fingerprint_geladen(_bot(), "r10_stack")["fingerprint_hash"])
        self.assertEqual(rc.fingerprint_hash({**fp, "pid": 1, "zeit_utc": "x"}), fp["fingerprint_hash"])

    def test_hash_ist_warmup_invariant(self):
        """Reviewer-Befund 2026-09-07: der Lazy-Cache-Zustand kippte den Hash (kalt [] != warm 5 Netze). Das Feld
        bleibt als Diagnose sichtbar (advisor_geladen_jetzt), darf den Hash aber nicht beruehren."""
        from pokerbot.strategy import advisor
        b = _bot()
        kalt = rc.fingerprint_geladen(b, "r8_stack")
        _advisor_warmup()
        warm = rc.fingerprint_geladen(b, "r8_stack")
        erwartet_geladen = sorted(advisor._FILES.values()) + ["defense_advisor.pt"]
        self.assertEqual(sorted(warm["advisor_geladen_jetzt"]), sorted(erwartet_geladen))
        self.assertNotEqual(kalt["advisor_geladen_jetzt"], warm["advisor_geladen_jetzt"],
                            "Testvoraussetzung: der Cache muss sich zwischen den Fingerprints geaendert haben")
        self.assertEqual(kalt["fingerprint_hash"], warm["fingerprint_hash"], "Hash darf Laufzeit-Zustand nicht tragen")
        self.assertNotIn("geladen_jetzt", kalt["advisor_pt"], "geladen_jetzt gehoert nicht in den gehashten advisor_pt-Block")
        self.assertIn("advisor_geladen_jetzt", rc._NICHT_IM_HASH)

    def test_advisor_hashes_und_gpu_version(self):
        fp = rc.fingerprint_geladen(_bot(), "basis")
        pt = fp["advisor_pt"]["sha256"]
        self.assertEqual(set(pt), {"advisor.pt", "turn_advisor.pt", "river_advisor.pt", "river_advisor_la.pt",
                                   "defense_advisor.pt"})
        for name, h in pt.items():
            if h is not None:
                self.assertRegex(h, r"^[0-9a-f]{64}$", name)
        self.assertNotIn("deepcfr_hunl.pt", pt, "deepcfr nur bei bot.use_deepcfr")
        gpu = fp["gpu_solver"]
        self.assertIn("gpu_cfr_sha256", gpu)
        self.assertEqual(gpu.get("r8_guard", {}).get("min_pot_chips"), 3000, "river_gpu_guard-Default (improver.py)")
        self.assertIn("quelle", fp["river_plan"])          # entweder river_plan oder gekennzeichneter Fallback
        self.assertIn("status", fp["k1_version"])


# ================================================================ Gatter
class GatterTest(unittest.TestCase):
    def setUp(self):
        # Im Testprozess ist bot.py OHNE PRINCE-Env importiert -> ein echter Fingerprint traegt prince_geladen False.
        # Der POSITIVE Pfad (Env vor Import) wird in den Subprozess-Smokes echt geprueft; hier wird er SIMULIERT,
        # damit die Gatter-Logik isoliert testbar bleibt.
        self.fp_ok = {**rc.fingerprint_geladen(_bot(), "r8_stack"), "prince": True, "prince_geladen": True,
                      "prince_abweichungen": [], "turn_defense": rc.PRINCE_SOLL_TURN_DEFENSE,
                      "slowplay": rc.PRINCE_SOLL_SLOWPLAY}
        os.environ.pop(rc.ENV_ERWARTE_PROFIL, None)

    def tearDown(self):
        os.environ.pop(rc.ENV_ERWARTE_PROFIL, None)

    def test_korrekte_konfig_passiert(self):
        rc.pruefe_konfiguration(rc.ERWARTUNGSPROFILE["v5-H"], self.fp_ok)

    def test_profil_sollwerte_stammen_aus_prince_profile(self):
        """Nicht getippt: die Deception-Sollwerte des Profils SIND gto_mode.PRINCE_PROFILE (Reviewer-Fix-Vorschlag)."""
        from pokerbot.strategy import gto_mode
        v5h = rc.ERWARTUNGSPROFILE["v5-H"]
        self.assertEqual(v5h["turn_defense"], float(gto_mode.PRINCE_PROFILE["POKERB_TURN_DEFENSE"]))
        self.assertEqual(v5h["slowplay"], float(gto_mode.PRINCE_PROFILE["POKERB_SLOWPLAY"]))
        self.assertIs(v5h["prince_geladen"], True)
        for env_key, *_ in rc._PRINCE_IMPORTKONSTANTEN:
            self.assertIn(env_key, gto_mode.PRINCE_PROFILE, f"{env_key} ist keine PRINCE-Profil-Zeile mehr")

    def test_reviewer_repro_bot_vor_env_importiert_bricht_ab(self):
        """Reviewer-Befund HOCH 2026-09-07: bot.py VOR POKERB_PRINCE=1 importiert -> Env sagt prince=True, der Bot
        spielt aber TURN_DEFENSE/SLOWPLAY 0.0. Vorher passierte das v5-H-Gatter (nur Env geprueft); jetzt muss es
        abbrechen und die eingefrorene Konstante benennen. Die Env wird danach vollstaendig zurueckgesetzt."""
        from pokerbot.strategy import gto_mode
        import pokerbot.strategy.bot as botmod
        if float(botmod._TURN_DEFENSE) == rc.PRINCE_SOLL_TURN_DEFENSE:
            self.skipTest("Testprozess laeuft selbst mit PRINCE-Env vor dem bot-Import -> Fall nicht darstellbar")
        env_vorher = dict(os.environ)
        try:
            os.environ["POKERB_PRINCE"] = "1"
            gto_mode.apply()                                    # Env-ABSICHT nachtraeglich: zu spaet fuer die Konstanten
            fp = rc.fingerprint_geladen(_bot(), "r8_stack")
            self.assertIs(fp["prince"], True)
            self.assertIs(fp["prince_geladen"], False)
            self.assertEqual((fp["turn_defense"], fp["slowplay"]), (0.0, 0.0))
            os.environ[rc.ENV_ERWARTE_PROFIL] = "v5-H"
            with self.assertRaises(SystemExit) as cm:
                rc.gatter_aus_env(fp, log=lambda *_: None)
            meldung = str(cm.exception)
            self.assertIn("prince_geladen: erwartet True, geladen False", meldung)
            self.assertIn("turn_defense: erwartet 0.07, geladen 0.0", meldung)
            self.assertIn("POKERB_TURN_DEFENSE: soll 0.07, geladen 0.0", meldung)
            self.assertIn("POKERB_SLOWPLAY: soll 0.25, geladen 0.0", meldung)
        finally:
            os.environ.clear()
            os.environ.update(env_vorher)

    def test_fehlkonfig_bricht_ab_und_nennt_alle_abweichungen(self):
        falsch = {**self.fp_ok, "exploit": True, "stack": "basis"}
        with self.assertRaises(SystemExit) as cm:
            rc.pruefe_konfiguration(rc.ERWARTUNGSPROFILE["v5-H"], falsch)
        meldung = str(cm.exception)
        self.assertIn("exploit: erwartet False, geladen True", meldung)
        self.assertIn("stack: erwartet 'r8_stack', geladen 'basis'", meldung)

    def test_env_unset_loggt_nur(self):
        protokoll: list[str] = []
        self.assertIsNone(rc.gatter_aus_env({**self.fp_ok, "exploit": True}, log=protokoll.append))
        self.assertTrue(protokoll and "nur geloggt" in protokoll[0])

    def test_env_gesetzt_gattert(self):
        os.environ[rc.ENV_ERWARTE_PROFIL] = "v5-H"
        self.assertEqual(rc.gatter_aus_env(self.fp_ok, log=lambda *_: None), "v5-H")
        with self.assertRaises(SystemExit):
            rc.gatter_aus_env({**self.fp_ok, "use_resolver": False}, log=lambda *_: None)
        os.environ[rc.ENV_ERWARTE_PROFIL] = "v10"
        with self.assertRaises(SystemExit):                       # r8_stack != r10_stack
            rc.gatter_aus_env(self.fp_ok, log=lambda *_: None)
        os.environ[rc.ENV_ERWARTE_PROFIL] = "gibt_es_nicht"
        with self.assertRaises(SystemExit):
            rc.gatter_aus_env(self.fp_ok, log=lambda *_: None)


# ================================================================ Ledger
class LedgerTest(unittest.TestCase):
    def setUp(self):
        self.pfad = SCRATCH / f"ledger_{self._testMethodName}.jsonl"

    def test_abbruch_nach_hand_end_verliert_nichts(self):
        led = gl.GtowLedger(self.pfad)
        self.assertTrue(led.prozess_start({"fingerprint_hash": "abc", "stack": "r8_stack"}))
        led.hand_start(1001, "v5-H", "abc")
        led.hand_end(1001, aivat=-12.5, winnings=100.0, status="ok")
        led.hand_start(1002, "v5-H", "abc")
        del led                                                  # 'Prozessabbruch' — nichts wird mehr geflusht
        zeilen = self.pfad.read_text(encoding="utf-8").splitlines()
        self.assertEqual([json.loads(z)["typ"] for z in zeilen], ["prozess_start", "hand_start", "hand_end", "hand_start"])
        ende = json.loads(zeilen[2])
        self.assertEqual((ende["hand_id"], ende["aivat"], ende["winnings"], ende["status"]), ("1001", -12.5, 100.0, "ok"))
        self.assertEqual(gl.abgleich(self.pfad), {"offen": ["1002"], "abgeschlossen": ["1001"], "doppelt_gestartet": []})

    def test_wiederanlauf_listet_offene_und_keine_doppel_ids(self):
        alt = gl.GtowLedger(self.pfad)
        for hid in (1, 2, 3):
            alt.hand_start(hid, "v10", "h")
        alt.hand_end(1, -3.0, 0.0, "ok")
        neu = gl.GtowLedger(self.pfad)                          # Wiederanlauf: liest die DATEI, kein Prozessgedaechtnis
        self.assertEqual(neu.offene_haende(), ["2", "3"])
        neu.hand_end(2, None, None, "unbekannt", ["clear_inprogress"])
        neu.hand_end(3, -1.0, 50.0, "ok")
        self.assertEqual(neu.offene_haende(), [])
        self.assertEqual(gl.abgleich(self.pfad)["doppelt_gestartet"], [])
        neu.hand_start(3, "v10", "h")                            # Doppelstart wird MARKIERT, nicht verschwiegen
        self.assertEqual(gl.abgleich(self.pfad)["doppelt_gestartet"], ["3"])
        self.assertTrue(json.loads(self.pfad.read_text(encoding="utf-8").splitlines()[-1]).get("doppelt_gestartet"))

    def test_unbekannt_wird_nie_null(self):
        led = gl.GtowLedger(self.pfad)
        led.hand_start(7, "v5-H", "h")
        led.hand_end(7, None, None, "ok")                        # 'ok' ohne AIVAT gibt es nicht
        e = json.loads(self.pfad.read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual((e["status"], e["aivat"]), ("unbekannt", None))
        led.hand_end(8, None, None, "quatsch")
        e = json.loads(self.pfad.read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual(e["status"], "fehler")
        self.assertIn("unbekannter_status:quatsch", e["technische_events"])

    def test_abgeschnittene_zeile_wird_uebersprungen(self):
        led = gl.GtowLedger(self.pfad)
        led.hand_start(5, "v5-H", "h")
        with open(self.pfad, "a", encoding="utf-8") as fh:
            fh.write('{"typ": "hand_end", "hand_id": "5", "aiv')   # Prozess starb mitten im Write
        self.assertEqual(len(gl.lese(self.pfad)), 1)
        self.assertEqual(gl.offene_haende(self.pfad), ["5"])

    def test_fault_injection_ledger_write_bricht_lauf_nicht(self):
        kaputt = SCRATCH / "ist_ein_verzeichnis"
        kaputt.mkdir(exist_ok=True)
        led = gl.GtowLedger(kaputt)                              # open('a') auf ein Verzeichnis -> OSError
        self.assertFalse(led.hand_start(1, "v5-H", "h"))
        self.assertFalse(led.hand_end(1, -1.0, 0.0, "ok"))
        self.assertEqual(led.schreibfehler, 2)
        # die main.py-Hooks: nie eine Exception, egal was Agent/Terminal sind
        os.environ[gl.ENV_LEDGER_PFAD] = str(kaputt)
        gl._LEDGER = None
        try:
            gl.melde_hand_start(object(), 42)
            gl.melde_hand_ende(object(), 42, None)
            gl.melde_hand_ende(None, 42, {"game_state": {"aivat_score": 1.0, "winnings": 2.0}}, "ok")
            self.assertEqual(gl.standard_ledger().schreibfehler, 3)
        finally:
            os.environ.pop(gl.ENV_LEDGER_PFAD, None)
            gl._LEDGER = None

    def test_melde_hooks_lesen_aivat_aus_terminal(self):
        os.environ[gl.ENV_LEDGER_PFAD] = str(self.pfad)
        gl._LEDGER = None
        try:
            class Kern:                                          # Stand-in fuer PokerBotAgent
                fingerprint_hash, stack_name = "fp123", "r8_stack"
                loop_blockierende_aufrufe = 0                    # E5 live: nie synchron im Loop gerufen

            class Agent:                                         # Stand-in fuer PokerBotMVP (haelt _a)
                _a = Kern()

            class GS:
                aivat_score, winnings = -7.25, -300.0

            class Terminal:
                game_state = GS()
            gl.melde_hand_start(Agent(), 99)
            gl.melde_hand_ende(Agent(), 99, Terminal())
            gl.melde_hand_start(Agent(), 100)
            gl.melde_hand_ende(Agent(), 100, None)               # kein Terminalzustand -> unbekannt
            Kern.loop_blockierende_aufrufe = 3                   # E5 NICHT live (poker_agent.py:74 ungepatcht)
            gl.melde_hand_start(Agent(), 101)
            gl.melde_hand_ende(Agent(), 101, Terminal())
            ev = gl.lese(self.pfad)
            self.assertEqual((ev[0]["arm"], ev[0]["fingerprint_hash"]), ("r8_stack", "fp123"))
            self.assertEqual((ev[1]["aivat"], ev[1]["winnings"], ev[1]["status"]), (-7.25, -300.0, "ok"))
            self.assertEqual(ev[1]["technische_events"], [], "E5 live -> kein e5-Ereignis")
            self.assertEqual((ev[3]["aivat"], ev[3]["status"]), (None, "unbekannt"))
            self.assertEqual(ev[5]["technische_events"], [f"{gl.E5_EREIGNIS}:3"], "E5 nicht live muss im Ledger stehen")
        finally:
            os.environ.pop(gl.ENV_LEDGER_PFAD, None)
            gl._LEDGER = None


# ================================================================ Subprozess-Smokes (D1-Server, GTOW-Adapter)
def _subprozess(modus: str, env_extra: dict[str, str]) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if not k.startswith("POKERB_")}
    env.update(env_extra)
    return subprocess.run([sys.executable, "-m", "tests.test_runtime_config", modus], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=_SMOKE_TIMEOUT_S, env=env,
                          cwd=Path(__file__).resolve().parents[1])


class SubprozessSmokeTest(unittest.TestCase):
    def test_server_d1_spielt_v5H_und_gatter_greift(self):
        led = SCRATCH / "ledger_server.jsonl"
        ok = _subprozess("--server", {rc.ENV_ERWARTE_PROFIL: "v5-H", gl.ENV_LEDGER_PFAD: str(led)})
        self.assertEqual(ok.returncode, 0, ok.stdout[-2000:] + ok.stderr[-2000:])
        self.assertIn("SERVER_OK", ok.stdout)
        falsch = _subprozess("--server", {rc.ENV_ERWARTE_PROFIL: "v10", gl.ENV_LEDGER_PFAD: str(led)})
        self.assertNotEqual(falsch.returncode, 0, "v10 erwartet r10_stack -> der Server (r8_stack) muss abbrechen")
        self.assertIn("FEHLKONFIGURATION", falsch.stdout + falsch.stderr)

    def test_gtow_adapter_e8_e5(self):
        led = SCRATCH / "ledger_gtow.jsonl"
        env = {"POKERB_PRINCE": "1", "POKERB_AUSLESE_STACK": "r8_stack", rc.ENV_ERWARTE_PROFIL: "v5-H",
               gl.ENV_LEDGER_PFAD: str(led)}
        ok = _subprozess("--gtow", env)
        self.assertEqual(ok.returncode, 0, ok.stdout[-2000:] + ok.stderr[-2000:])
        self.assertIn("GTOW_OK", ok.stdout)
        self.assertIn("E5_LOOP_FREI", ok.stdout, "act_async muss den Event-Loop waehrend decide freigeben")
        ev = gl.lese(led)
        self.assertEqual(ev[0]["typ"], "prozess_start")
        self.assertEqual(ev[0]["fingerprint"]["stack"], "r8_stack")
        self.assertIsNone(ev[0]["fingerprint"]["gto_mode_flags"]["POKERB_RAISE_NARROW"], "resolver-ON: kein RAISE_NARROW")
        # Prozess-Invarianz: ein ZWEITER Prozess, der alle Netze schon VOR dem Agenten laedt, muss denselben Hash tragen
        warm = _subprozess("--gtow", {**env, ENV_SMOKE_WARM_FIRST: "1", gl.ENV_LEDGER_PFAD: str(led) + ".warm"})
        self.assertEqual(warm.returncode, 0, warm.stdout[-2000:] + warm.stderr[-2000:])
        self.assertEqual(_smoke_hash(ok.stdout), _smoke_hash(warm.stdout),
                         "fingerprint_hash ist nicht prozess-/warm-up-invariant (Reviewer-Befund 2026-09-07)")
        falsch = _subprozess("--gtow", {**env, "POKERB_RESOLVER": "0"})   # Resolver aus != v5-H -> Abbruch
        self.assertNotEqual(falsch.returncode, 0)
        self.assertIn("use_resolver: erwartet True, geladen False", falsch.stdout + falsch.stderr)
        self.assertIn("E5_SYNC_ERKANNT", ok.stdout, "synchroner act_dict im Loop muss gezaehlt werden (E5-Laufzeitnachweis)")

    def test_gtow_bot_vor_env_importiert_bricht_ab(self):
        """Reviewer-Befund HOCH 2026-09-07 auf dem ECHTEN Adapter-Pfad: pokerbot.strategy.bot ist schon importiert,
        bevor gtowizard.py PRINCE/AUSLESE_ENV setzt -> Env-Absicht PRINCE, eingefroren 0.0. Das Gatter muss den
        PokerBotAgent-Start abbrechen (vorher: passierte, weil nur die Env geprueft wurde)."""
        env = {"POKERB_PRINCE": "1", "POKERB_AUSLESE_STACK": "r8_stack", rc.ENV_ERWARTE_PROFIL: "v5-H",
               gl.ENV_LEDGER_PFAD: str(SCRATCH / "ledger_bot_vor_env.jsonl")}
        falsch = _subprozess("--gtow-bot-vor-env", env)
        ausgabe = falsch.stdout + falsch.stderr
        self.assertNotEqual(falsch.returncode, 0, "bot vor Env importiert muss am K4-Gatter scheitern:\n" + ausgabe[-2000:])
        self.assertIn("FEHLKONFIGURATION", ausgabe)
        self.assertIn("prince_geladen: erwartet True, geladen False", ausgabe)
        self.assertIn("POKERB_TURN_DEFENSE: soll 0.07, geladen 0.0", ausgabe)
        self.assertIn("BOT_VOR_ENV_IMPORTIERT prince_env=True", falsch.stdout, "Testvoraussetzung: Env-Absicht war PRINCE")

    def test_e5_client_patch_status(self):
        """E5 ist erst LIVE, wenn PokerBotMVP.act (gitignored, poker_agent.py:74) act_async awaitet. Der Patch ist
        Integrator-Sache (docs/reports/V10_LEDGER_PATCH.md); bis dahin meldet der Test den Stand als Skip mit Klartext.
        POKERB_K4_E5_PFLICHT=1 macht ihn scharf (rot, sobald der Patch fehlt oder verloren geht)."""
        if not _CLIENT_AGENT_DATEI.exists():
            self.skipTest(f"GTOW-Client nicht vorhanden: {_CLIENT_AGENT_DATEI}")
        quelle = _CLIENT_AGENT_DATEI.read_text(encoding="utf-8")
        gepatcht = _E5_CLIENT_PATCH in quelle
        if not gepatcht and os.environ.get(ENV_E5_PFLICHT) != "1":
            self.skipTest("E5 NICHT LIVE: poker_agent.py ruft act_dict synchron (Event-Loop blockiert, V10_FAKTEN A8)"
                          " -- Integrator-Patch aus docs/reports/V10_LEDGER_PATCH.md ausstehend")
        self.assertTrue(gepatcht, f"E5-Client-Patch fehlt in {_CLIENT_AGENT_DATEI}: erwartet '{_E5_CLIENT_PATCH}'")
        self.assertNotIn("return ActRequest(**self._a.act_dict(gsr))", quelle, "synchroner act_dict-Aufruf noch vorhanden")


def _smoke_hash(stdout: str) -> str:
    """Den fingerprint_hash aus der GTOW_OK-Zeile eines Smoke-Subprozesses lesen."""
    for zeile in stdout.splitlines():
        if zeile.startswith("GTOW_OK"):
            return zeile.split("fp=")[1].split()[0]
    raise AssertionError("keine GTOW_OK-Zeile in: " + stdout[-1500:])


def _server_smoke() -> None:
    """D1: der Web-Bot spielt PRINCE + exploit OFF + FINAL_STACK + Resolver AN; eine Hand starten, Bot muss handeln."""
    from fastapi.testclient import TestClient
    from pokerbot.web import server
    client = TestClient(server.app)
    view = client.post("/api/new_game", json={"stack": 20000, "sb": 50, "bb": 100}).json()
    fp = server.SESSION.fingerprint
    kern = {k: fp[k] for k in ("prince", "exploit", "use_resolver", "use_turn_resolver", "stack")}
    assert kern == {"prince": True, "exploit": False, "use_resolver": True, "use_turn_resolver": True,
                    "stack": "r8_stack"}, kern
    assert fp["gto_mode_flags"]["POKERB_RAISE_NARROW"] is None, "resolver-ON-Kanal darf kein RAISE_NARROW tragen"
    assert (fp["turn_defense"], fp["slowplay"]) == (0.07, 0.25), (fp["turn_defense"], fp["slowplay"])
    bot_aktionen = list(view["bot_events"])
    for _ in range(12):                                          # Mensch checkt/callt, bis der Bot gehandelt hat
        if bot_aktionen:
            break
        legal = view["state"]["legal"]
        aktion = "check" if legal.get("can_check") else "call"
        view = client.post("/api/action", json={"action": aktion}).json()
        assert "error" not in view, view
        bot_aktionen += view.get("bot_events", [])
        if view["state"].get("hand_over"):
            view = client.post("/api/next_hand").json()
            bot_aktionen += view.get("bot_events", [])
    assert bot_aktionen, "der Bot hat nicht gehandelt"
    # Reviewer-Fall 2026-09-07: die ZWEITE Session (nach gespielten Aktionen, Advisor-Cache warm) trug einen anderen
    # Hash als die erste -> beide muessen identisch sein (gleicher Bot, gleicher Prozess). Der Cache wird explizit
    # gefuellt, weil eine Preflop-Hand allein kein Netz laedt (sonst testete der Vergleich nur den Zufall der Hand).
    _advisor_warmup()
    client.post("/api/new_game", json={"stack": 20000, "sb": 50, "bb": 100})
    fp2 = server.SESSION.fingerprint
    assert fp2["fingerprint_hash"] == fp["fingerprint_hash"], (
        f"Session-Hash kippt: {fp['fingerprint_hash'][:12]} -> {fp2['fingerprint_hash'][:12]}; "
        f"geladen_jetzt {fp['advisor_geladen_jetzt']} -> {fp2['advisor_geladen_jetzt']}")
    print(f"SERVER_OK {kern} bot_events={[(e['action'], e['amount']) for e in bot_aktionen[:3]]} "
          f"fp={fp['fingerprint_hash']} session2_gleich=True geladen_jetzt_s1={fp['advisor_geladen_jetzt']} "
          f"s2={fp2['advisor_geladen_jetzt']}")


def _gtow_smoke() -> None:
    """E8: setze_env VOR dem bot-Import (Modulanfang gtowizard.py), Fingerprint + prozess_start + Gatter in
    PokerBotAgent.__init__; E5: act_async liefert eine legale ActRequest aus dem Worker-Thread."""
    import asyncio
    import time
    from pokerbot.benchmark import gtowizard as gw
    import pokerbot.strategy.bot as botmod
    botmod.EQUITY_ITERS = 60
    if os.environ.get(ENV_SMOKE_WARM_FIRST) == "1":
        _advisor_warmup()                                        # Prozess-Invarianz: warm gestartet == kalt gestartet
    agent = gw.PokerBotAgent(seed=7, exploit=True)              # exploit=True wird vom PRINCE-Profil (EXPLOIT=0) ueberstimmt
    assert agent.bot.exploit is False and agent.stack_name == "r8_stack", (agent.bot.exploit, agent.stack_name)
    assert agent.fingerprint["prince"] is True and agent.fingerprint_hash == agent.fingerprint["fingerprint_hash"]
    fp = agent.fingerprint
    assert (fp["turn_defense"], fp["slowplay"]) == (0.07, 0.25), "PRINCE-Werte muessen bei IMPORT gelesen worden sein"
    gsr = gw._gsr("preflop", 150, 150, "", ["f", "c", "b"], {"min": 300, "max": 19950}, [], hole="AsKd", pos="SB",
                  hstack=19950, vstack=19900)
    ar = asyncio.run(agent.act_async(gsr))
    assert ar["action"] in ("f", "c", "b"), ar
    assert agent.loop_blockierende_aufrufe == 0, "act_async (Worker-Thread) darf nicht als Loop-Blockade zaehlen"
    asyncio.run(_e5_synchroner_aufruf_im_loop(agent, gsr))
    assert agent.loop_blockierende_aufrufe == 1, agent.loop_blockierende_aufrufe
    print("E5_SYNC_ERKANNT loop_blockierende_aufrufe=1 nach act_dict im Loop, 0 nach act_async")
    ticks = asyncio.run(_e5_parallele_haende(agent, gsr, time))
    assert ticks >= _E5_MIN_TICKS, f"Event-Loop war waehrend decide blockiert: nur {ticks} Heartbeat-Ticks"
    assert agent.loop_blockierende_aufrufe == 1, "parallele act_async-Haende duerfen den Zaehler nicht erhoehen"
    # Warm-up-Invarianz IM Prozess: nach echten Entscheidungen (Advisor-Cache warm) derselbe Hash wie im Konstruktor
    _advisor_warmup()
    warm = rc.fingerprint_geladen(agent.bot, agent.stack_name)
    assert warm["fingerprint_hash"] == agent.fingerprint_hash, (
        f"Hash kippt nach Warm-up: {agent.fingerprint_hash[:12]} -> {warm['fingerprint_hash'][:12]}")
    print(f"E5_LOOP_FREI ticks={ticks} waehrend 2 parallelen act_async (je {_E5_SIMULIERTE_LATENZ_S}s decide)")
    print(f"GTOW_OK stack={agent.stack_name} fp={agent.fingerprint_hash} act_async={ar} warm_gleich=True "
          f"geladen_jetzt_start={agent.fingerprint['advisor_geladen_jetzt']}")


async def _e5_synchroner_aufruf_im_loop(agent, gsr: dict) -> None:
    """Der UNGEPATCHTE Client-Pfad (poker_agent.py:74): act_dict direkt in einer Coroutine -> ein Loop laeuft im
    aufrufenden Thread -> der Agent muss die Blockade zaehlen (wird als 'e5_sync_act_dict:n' ins Ledger geschrieben)."""
    antwort = agent.act_dict(gsr)
    assert antwort["action"] in ("f", "c", "b"), antwort


def _gtow_bot_vor_env_smoke() -> None:
    """Der Import-Reihenfolge-Fehler auf dem echten Adapter-Pfad: bot.py wird OHNE PRINCE importiert (Konstanten
    frieren auf 0.0), DANACH bekommt die Env PRINCE/AUSLESE_STACK zurueck und gtowizard.py + PokerBotAgent starten
    wie im Harness. Erwartet: SystemExit FEHLKONFIGURATION (prince_geladen False) — der Prozess endet != 0."""
    prince_env = os.environ.pop("POKERB_PRINCE")
    import pokerbot.strategy.bot as botmod                        # zu frueh: liest TURN_DEFENSE/SLOWPLAY als 0
    os.environ["POKERB_PRINCE"] = prince_env
    from pokerbot.strategy import gto_mode
    print(f"BOT_VOR_ENV_IMPORTIERT prince_env={gto_mode.prince_enabled()} turn_defense_eingefroren={botmod._TURN_DEFENSE}")
    from pokerbot.benchmark import gtowizard as gw
    gw.PokerBotAgent(seed=7)                                      # muss am K4-Gatter sterben
    print("GATTER_HAT_NICHT_GEGRIFFEN")                           # nie erreichen


async def _e5_parallele_haende(agent, gsr: dict, time_mod) -> int:
    """E5-Nachweis fuer die versionierte Haelfte: zwei Haende entscheiden GLEICHZEITIG ueber act_async, waehrend ein
    Heartbeat-Task tickt. decide wird kuenstlich verlangsamt (time.sleep im Worker-Thread) — blockierte act_async den
    Loop wie der synchrone act_dict, bekaeme der Heartbeat waehrend der ~0,5 s keine Gelegenheit zu ticken."""
    import asyncio
    echtes_act_dict = agent.act_dict

    def langsames_act_dict(g: dict) -> dict:
        time_mod.sleep(_E5_SIMULIERTE_LATENZ_S)
        return echtes_act_dict(g)

    agent.act_dict = langsames_act_dict
    ticks = 0
    haende = asyncio.gather(agent.act_async(gsr), agent.act_async(dict(gsr)))
    try:
        while not haende.done():
            await asyncio.sleep(_E5_HEARTBEAT_S)
            ticks += 1
        for antwort in haende.result():
            assert antwort["action"] in ("f", "c", "b"), antwort
    finally:
        agent.act_dict = echtes_act_dict
    return ticks


if __name__ == "__main__":
    if "--server" in sys.argv:
        _server_smoke()
    elif "--gtow-bot-vor-env" in sys.argv:
        _gtow_bot_vor_env_smoke()
    elif "--gtow" in sys.argv:
        _gtow_smoke()
    else:
        unittest.main(verbosity=2)
