"""Tests K5 GTOW-Nachtfahrplan v10 (research/gtow_nacht_v10.py) — alles ueber den Mock-Runner, $0, kein API-Kontakt.

Geprueft: Muenzen-Sequenzen (BAAB/ABBA) + Unveraenderlichkeit, Arm-Env-Verbote + Je-Chunk-Env (POKERB_ARM,
POKERB_K2_TRACE eindeutig je Versuch), Harness-Parser (echte Zeile aus main.py:231-233), Ereignis-Kanaele
(K2-Trace exakt gegen contracts.FALLBACK_STATUS/DEADLINE_STATUS, Ledger inkl. http_4xx + Legalisierungs-Kanal,
stdout-regex als letzter Fallback; fehlender Kanal -> kein_verdikt statt stiller 0), HH-Datei-Zuordnung, Manifest nach
jedem Chunk, Retry-Logik (Abgleich+clear vor jedem Versuch, 3 Versuche), FEHLVERSUCHE WERDEN AUSGEWERTET (Ledger
des Harness-Abbruchs: geborgene Haende, offene Haende, http_4xx -> kein blinder Retry + Kandidaten-Stopp; Review-Fix 1),
Fazit-Rechnung (Pool, Paar-Differenzen, Untergrenze), Stopp-Regeln TESTWEIT (illegal / http_4xx / wiederholte Deadline
ueber Smoke + Naechte kumuliert / unbekannt > 0,5 % kumuliert), Vorregistrierung genau einmal, Gesamt-Fazit ueber beide
Naechte (k=4 Paare, SE_Delta 6,77 bei 500/Chunk).

Normalfall der Helfer = VOLLE Kanaele (Mock schreibt K4-Ledger mit Legalisierungs-Deklaration + K2-Trace); Tests
ueber fehlende Kanaele schalten sie explizit ab (ledger=False / k2_trace=False / illegal_kanal=False).

Lauf:  python -m tests.test_gtow_nacht_v10   (pytest-kompatibel; pytest ist lokal nicht installiert)
"""
from __future__ import annotations

import json
import math
import tempfile
import time
import warnings
from pathlib import Path

from research import gtow_nacht_v10 as k5

MUENZE = "BAAB_dann_ABBA"     # data/runs/v10_muenze.json
SEQUENZEN = k5.sequenzen_aus_muenze(MUENZE)
OHNE_LEDGER = lambda: ("ledger_fehlt", [])   # noqa: E731 — Abgleich-Stub fuer Tests ohne Ledger-Modul


def _fahrt(tmp: Path, runner: k5.MockRunner, journal: list, chunk_haende: int = 40, ledger=None) -> k5.Nachtfahrt:
    """Ohne `ledger`-Stub laeuft der ECHTE Abgleich (gtow_ledger.offene_haende_alle) ueber tmp/ledger."""
    return k5.Nachtfahrt(runner, journal.append, manifest_datei=tmp / "manifest.json", sessions_dir=tmp / "sessions",
                         chunk_haende=chunk_haende, sequenzen=SEQUENZEN, pause=lambda s: None, ledger_abgleich=ledger,
                         ledger_dir=tmp / "ledger")


def _mock(tmp: Path, seed: int = 1, ledger: bool = True, **kw) -> k5.MockRunner:
    return k5.MockRunner(seed, tmp / "sessions", ledger_dir=(tmp / "ledger") if ledger else None, **kw)


def _manifest(tmp: Path) -> dict:
    return json.loads((tmp / "manifest.json").read_text(encoding="utf-8"))


def _leise(fn, *args):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return fn(*args)


# --- Sequenz + Arme -------------------------------------------------------------------------------------------------
def test_sequenzen_aus_muenze():
    assert SEQUENZEN == {1: ["B", "A", "A", "B"], 2: ["A", "B", "B", "A"]}
    assert k5.blockpaare(SEQUENZEN[1]) == [(0, 1), (2, 3)]
    for kaputt in ("ABBA", "ABBA_dann_ABC", "ABBA_dann_ABBAA"):
        try:
            k5.sequenzen_aus_muenze(kaputt)
        except ValueError:
            continue
        raise AssertionError(f"Muenze {kaputt!r} haette abgelehnt werden muessen")


def test_muenze_datei_stimmt_mit_karte():
    assert k5.lade_sequenzen() == SEQUENZEN, "data/runs/v10_muenze.json weicht von 'BAAB_dann_ABBA' ab"


def test_arm_env_und_verbote():
    assert k5.ARME["A"] == {"POKERB_PRINCE": "1", "POKERB_AUSLESE_STACK": "r8_stack", "POKERB_ERWARTE_PROFIL": "v5-H"}
    assert k5.ARME["B"] == {"POKERB_PRINCE": "1", "POKERB_AUSLESE_STACK": "r10_stack", "POKERB_ERWARTE_PROFIL": "v10"}
    for verboten in k5.VERBOTENE_ARM_ENV:
        try:
            k5.pruefe_arm_env({**k5.ARME["B"], verboten: "0"})
        except ValueError:
            continue
        raise AssertionError(f"{verboten} im Arm-Env muss abgelehnt werden")


def test_subprozess_env_hygiene(monkeypatch=None):
    import os
    alt = dict(os.environ)
    os.environ["POKERB_RAISE_NARROW"] = "1.0"        # ein Fremd-Flag aus der Shell darf NICHT durchsickern
    try:
        env = k5.SubprozessRunner("KEY")._env(k5.ARME["B"])
    finally:
        os.environ.clear()
        os.environ.update(alt)
    assert "POKERB_RAISE_NARROW" not in env and "POKERB_RESOLVER" not in env
    assert env["GTOWIZARD_API_KEY"] == "KEY" and env["PYTHONUTF8"] == "1"
    assert env["POKERB_AUSLESE_STACK"] == "r10_stack" and env["POKERB_PRINCE"] == "1"


def test_chunk_env_arm_label_und_trace_pfad_je_versuch():
    """Review-Fix: der Runner bekommt je Versuch POKERB_ARM (Ledger-Label, runtime_config.ENV_ARM) und einen
    EIGENEN K2-Trace-Pfad unter dem Manifest-Verzeichnis; Retries teilen sich keine Trace-Datei."""
    with tempfile.TemporaryDirectory() as d:
        tmp, journal = Path(d), []
        runner = _mock(tmp, fehlversuche={0: 1})
        _leise(_fahrt(tmp, runner, journal).fahre_nacht, 1)
        envs = runner.arm_envs
        assert len(envs) == 5 and [e["POKERB_ARM"] for e in envs] == ["v10", "v10", "v5-H", "v5-H", "v10"]
        pfade = [e[k5.K2_TRACE_ENV] for e in envs]
        assert len(set(pfade)) == 5, "Trace-Pfad muss je Versuch eindeutig sein"
        assert all(Path(p).parent == tmp / "k2_trace" for p in pfade)
        assert "k2_trace_n1_c1_v2_" in Path(pfade[1]).name         # Nacht 1, Chunk 1, 2. Versuch
        for e in envs:                                              # Verbote gelten auch fuer die erweiterte Env
            k5.pruefe_arm_env(e)
            assert e["POKERB_PRINCE"] == "1" and "POKERB_RESOLVER" not in e
        c1 = _manifest(tmp)["chunks"][0]
        assert c1["k2_trace"] == pfade[1] and c1["versuche"][1]["k2_trace"] == pfade[1]


# --- Parser + Kanaele -------------------------------------------------------------------------------------------------
def test_parse_harness_zeile():
    zeile = ("Successful hands: 497. Failed hands: 3. Average seconds/hand: 12.345\n"
             "AIVAT luck-adj : -21.34 +/- 9.57 bb/100  (n=495)  <-- definitive vs GTO Wizard\n")
    assert k5.parse_aivat(zeile) == (495, -21.34, 9.57)
    assert k5.parse_aivat("kein AIVAT") is None
    events = k5.zaehle_ereignisse(zeile, 495, None)
    assert events == {"transport": 3, "deadline": 0, "illegal": 0, "unbekannt": 2, "fallback": 0, "http_4xx": 0}
    marker = "K2 plan deadline verletzt -> Fallback Basis\nILLEGAL action rejected\nofftree villain\n" + zeile
    ev2 = k5.zaehle_ereignisse(marker, 495, None)
    assert (ev2["deadline"], ev2["illegal"], ev2["fallback"]) == (1, 1, 2)


def test_trace_klassifikation_exakt_gegen_vertrag():
    """Review-Fix: deadline := deadline_status=='verletzt' ODER fallback_status=='deadline'; fallback := fallback_status
    in {offtree, fehler, hand_not_in_range}. 'nicht_aktiviert'/'iterations_deadline'/'keiner' zaehlen NICHT."""
    from pokerbot.strategy.contracts import DEADLINE_STATUS, FALLBACK_STATUS
    assert k5.TRACE_DEADLINE_VERLETZT in DEADLINE_STATUS and k5.TRACE_FALLBACK_DEADLINE in FALLBACK_STATUS
    assert set(k5.TRACE_FALLBACK_KLASSEN) <= set(FALLBACK_STATUS)
    zeilen = [
        {"fallback_status": "keiner", "deadline_status": "eingehalten", "latenz_ms": 100.0},
        {"fallback_status": "keiner", "deadline_status": "iterations_deadline"},          # Gym-Semantik, kein Ereignis
        {"fallback_status": "nicht_aktiviert", "deadline_status": "nicht_gemessen", "latenz_ms": 5.0},
        {"fallback_status": "deadline", "deadline_status": "verletzt", "latenz_ms": 7600.0},
        {"fallback_status": "keiner", "deadline_status": "verletzt", "latenz_ms": 8100.0},  # spaetes Ergebnis genommen? zaehlt
        {"fallback_status": "offtree", "deadline_status": "eingehalten", "offtree": True, "latenz_ms": 12.0},
        {"fallback_status": "hand_not_in_range", "deadline_status": "eingehalten", "latenz_ms": 30.0},
        {"fallback_status": "fehler", "deadline_status": "nicht_gemessen"},
    ]
    with tempfile.TemporaryDirectory() as d:
        pfad = Path(d) / "t.jsonl"
        pfad.write_text("\n".join(json.dumps(z) for z in zeilen) + '\n{"abgeschnitten": ', encoding="utf-8")
        b = k5.zaehle_ereignisse_trace(pfad)
        assert (b.deadline, b.fallback, b.entscheidungen) == (2, 3, 8)
        assert b.latenz_max_ms == 8100.0 and b.latenz_p99_ms == 8100.0
        assert k5.zaehle_ereignisse_trace(Path(d) / "gibt_es_nicht.jsonl") is None
    assert k5._quantil([1.0, 2.0, 3.0, 4.0], 0.5) == 2.0 and k5._quantil([], 0.99) is None


def test_ledger_string_klassen_http_4xx_und_legalisierung():
    """Review-Fix: 4xx (ausser 409/429) = eigene Klasse http_4xx (abgelehnte Anfrage), nie in transport versteckt;
    'legalisiert:<von>-><nach>' (Integrator-Vertrag fuer decision_to_act) zaehlt als illegal."""
    assert k5.klassifiziere_ledger_string("http_400") == "http_4xx"
    assert k5.klassifiziere_ledger_string("http_422") == "http_4xx"
    assert k5.klassifiziere_ledger_string("http_409") == "transport"        # Waisen/Konflikt (utils.py:13)
    assert k5.klassifiziere_ledger_string("http_429") == "transport"
    assert k5.klassifiziere_ledger_string("http_503") == "transport"
    assert k5.klassifiziere_ledger_string("ReadTimeout") == "transport"
    assert k5.klassifiziere_ledger_string("ConnectError") == "transport"
    assert k5.klassifiziere_ledger_string("illegal_action") == "illegal"
    assert k5.klassifiziere_ledger_string("legalisiert:b->c") == "illegal"
    assert k5.klassifiziere_ledger_string("KeyError") is None              # -> sonstige, sichtbar


def test_finde_hh_datei_nur_nach_start():
    with tempfile.TemporaryDirectory() as d:
        sess = Path(d)
        start = int(time.time())
        (sess / f"gtow_hands_{start - 100}.jsonl").write_text("{}\n")        # fremde alte Datei
        assert k5.finde_hh_datei(sess, start) is None
        neu = sess / f"gtow_hands_{start + 3}.jsonl"
        neu.write_text('{"hand_id": 1, "aivat": null}\n{"hand_id": 2, "aivat": 1.0}\n')
        assert k5.finde_hh_datei(sess, start) == str(neu)
        assert k5.zaehle_ereignisse("Successful hands: 2. Failed hands: 0.", 2, neu)["unbekannt"] == 1


# --- Nacht 1 komplett: Sequenz, Manifest, Journal ---------------------------------------------------------------------
def test_nacht1_sequenz_manifest_journal():
    with tempfile.TemporaryDirectory() as d:
        tmp, journal = Path(d), []
        runner = _mock(tmp)
        fazit = _leise(_fahrt(tmp, runner, journal).fahre_nacht, 1)
        manifest = _manifest(tmp)
        assert [c["arm"] for c in manifest["chunks"]] == ["B", "A", "A", "B"]
        assert manifest["meta"]["sequenzen"] == {"1": ["B", "A", "A", "B"], "2": ["A", "B", "B", "A"]}
        for c in manifest["chunks"]:
            assert c["status"] == "OK" and c["n"] == 40 and c["retries"] == 0
            for feld in ("chunk", "arm", "n", "aivat", "hh_datei", "start", "ende", "retries", "technische_events"):
                assert c[feld] is not None, feld
            assert Path(c["hh_datei"]).exists()
            assert c["versuche"][0]["ledger"] == "ledger" and c["versuche"][0]["offene_haende"] == 0
            assert c["illegal_kanal"] == "ledger" and c["kanal_warnung"] is None
            assert c["haende_geborgen"] == 0 and c["haende_offen"] == 0 and c["abbruch_grund"] is None
        # Kanal-Ehrlichkeit: B hat K2-Trace + Ledger, A (kein K2-Plan) nur das Ledger
        assert [c["ereignis_kanal"] for c in manifest["chunks"]] == ["k2_trace+ledger", "ledger", "ledger", "k2_trace+ledger"]
        assert manifest["chunks"][0]["k2_entscheidungen"] == 10 and manifest["chunks"][0]["latenz_p99_ms"] < 1000
        typen = [j["typ"] for j in journal]
        assert typen[0] == "V10-GTOW-VORREGISTRIERUNG" and typen.count("V10-GTOW-CHUNK") == 4
        assert typen[-1] == "V10-GTOW-NACHT-FAZIT"
        assert journal[0]["aussage"] == k5.VORREGISTRIERTE_AUSSAGE and "http_4xx" in journal[0]["stopp_regeln"]
        assert runner.aufrufe == 4 and runner.clears == 4          # clear VOR jedem Start
        assert fazit["sequenz"] == "BAAB" and fazit["v10_n"] == 80 and fazit["v5-H_n"] == 80
        assert fazit["kein_verdikt"] is False and fazit["kandidat_gestoppt"] is None
        assert [p["chunks"] for p in fazit["paare"]] == [[1, 2], [3, 4]] and all(p["gueltig"] for p in fazit["paare"])
        assert fazit["warnungen"] == []                              # volle Kanaele: nichts zu warnen


def test_nacht2_sequenz_und_vorregistrierung_einmal():
    with tempfile.TemporaryDirectory() as d:
        tmp, journal = Path(d), []
        _leise(_fahrt(tmp, _mock(tmp), journal).fahre_nacht, 1)
        fahrt2 = _fahrt(tmp, _mock(tmp, seed=2), journal)   # neuer Prozess, gleiches Manifest
        _leise(fahrt2.fahre_nacht, 2)
        assert [j["typ"] for j in journal].count("V10-GTOW-VORREGISTRIERUNG") == 1
        assert [c["arm"] for c in _manifest(tmp)["chunks"][4:]] == ["A", "B", "B", "A"]
        assert fahrt2.sequenzen == SEQUENZEN                     # nie veraendert


# --- Retry ------------------------------------------------------------------------------------------------------------
def test_retry_erfolg_im_dritten_versuch():
    with tempfile.TemporaryDirectory() as d:
        tmp, journal = Path(d), []
        runner = _mock(tmp, fehlversuche={0: 2})                # Chunk 1: zwei Fehlschlaege, dann Erfolg
        pausen = []
        fahrt = _fahrt(tmp, runner, journal)
        fahrt._pause = pausen.append
        _leise(fahrt.fahre_nacht, 1)
        c1 = _manifest(tmp)["chunks"][0]
        assert c1["status"] == "OK" and c1["retries"] == 2 and len(c1["versuche"]) == 3
        assert [v["erfolg"] for v in c1["versuche"]] == [False, False, True]
        assert pausen == [k5.RETRY_PAUSE_S, 2 * k5.RETRY_PAUSE_S]
        assert runner.clears == 3 + 3                            # 3 Starts in Chunk 1 + je 1 in Chunks 2-4
        assert c1["haende_geborgen"] == 0 and c1["technische_events"]["transport"] == 0   # Fehlversuche ohne Ledger


def test_retry_erschoepft_fehlgeschlagen():
    with tempfile.TemporaryDirectory() as d:
        tmp, journal = Path(d), []
        runner = _mock(tmp, fehlversuche={1: 3})                # Chunk 2 (A) faellt komplett aus
        fazit = _leise(_fahrt(tmp, runner, journal).fahre_nacht, 1)
        chunks = _manifest(tmp)["chunks"]
        assert chunks[1]["status"] == "FEHLGESCHLAGEN" and chunks[1]["retries"] == 3 and chunks[1]["aivat"] is None
        assert [c["status"] for c in chunks] == ["OK", "FEHLGESCHLAGEN", "OK", "OK"]   # Sequenz laeuft weiter
        assert fazit["chunks_fehlgeschlagen"] == 1 and fazit["v5-H_n"] == 40
        assert [p["gueltig"] for p in fazit["paare"]] == [False, True]


def test_fehlversuch_ledger_geborgen_und_abgleich():
    """Review-Fix 1: ein gescheiterter Versuch (Transport-Exception, main.py:191) hinterlaesst ein Ledger mit
    gespielten + offenen Haenden. Erwartet: Ereignis gezaehlt, Haende 'geborgen' (nicht im n), offene Hand im
    Abgleich VOR dem Retry sichtbar, Retry laeuft normal weiter (kein 4xx)."""
    with tempfile.TemporaryDirectory() as d:
        tmp, journal = Path(d), []
        runner = _mock(tmp, fehlversuche={1: 1},
                       fehlversuch_ledger={1: {"haende": 7, "offen": 1, "fehler_strings": ["ReadTimeout"]}})
        fazit = _leise(_fahrt(tmp, runner, journal).fahre_nacht, 1)
        c2 = _manifest(tmp)["chunks"][1]                          # Chunk 2 = A, 1 Fehlversuch, dann OK
        assert c2["status"] == "OK" and c2["retries"] == 1 and c2["n"] == 40
        assert c2["technische_events"]["transport"] == 1 and c2["technische_events"]["http_4xx"] == 0
        assert c2["haende_geborgen"] == 7 and c2["haende_offen"] == 1 and c2["abbruch_grund"] is None
        v1, v2 = c2["versuche"]
        assert v1["erfolg"] is False and v1["haende_geborgen"] == 7 and v1["haende_offen"] == 1
        assert v1["events"]["transport"] == 1 and v1["kanaele"] == ["ledger"] and len(v1["ledger_dateien"]) == 1
        assert v2["offene_haende"] == 1, "der echte Ledger-Abgleich muss die offene Hand des Fehlversuchs VOR dem Retry sehen"
        assert len(c2["ledger_dateien"]) == 2                     # beide Versuche = Bergungs-Quellen
        assert fazit["v5-H_events"]["transport"] == 1 and fazit["kandidat_gestoppt"] is None
        assert fazit["kein_verdikt"] is False                     # A-Transportfehler ist kein Verdikt-Killer
        assert math.isclose(fazit["unbekannt_quote"], 0.0)


def test_fehlversuch_http_4xx_kein_blinder_retry_und_kandidat_stopp():
    """Review-Fix 1+2: die API lehnt eine Anfrage des Kandidaten ab (main.py:186 -> raise -> Chunk-Abbruch). Vorher:
    rc!=0 -> Ledger verworfen -> 2x500 Haende blind nachgespielt, Stopp-Regel blind. Jetzt: Ereignis aus dem Ledger
    des Fehlversuchs, KEIN Retry, Chunk FEHLGESCHLAGEN mit abbruch_grund, Kandidat gestoppt, kein_verdikt."""
    with tempfile.TemporaryDirectory() as d:
        tmp, journal = Path(d), []
        runner = _mock(tmp, fehlversuche={0: 3},
                       fehlversuch_ledger={0: {"haende": 12, "offen": 2, "events": {"http_4xx": 1}, "code": 400}})
        pausen = []
        fahrt = _fahrt(tmp, runner, journal)
        fahrt._pause = pausen.append
        fazit = _leise(fahrt.fahre_nacht, 1)
        chunks = _manifest(tmp)["chunks"]
        assert [c["status"] for c in chunks] == ["FEHLGESCHLAGEN", "OK", "OK", "UEBERSPRUNGEN_KANDIDAT_GESTOPPT"]
        c1 = chunks[0]
        assert c1["retries"] == 1 and len(c1["versuche"]) == 1 and pausen == []      # kein blinder Retry
        assert c1["abbruch_grund"].startswith(k5.ABBRUCH_API_ABLEHNUNG) and "http_400" in c1["abbruch_grund"]
        assert c1["technische_events"]["http_4xx"] == 1 and c1["technische_events"]["transport"] == 0
        assert c1["haende_geborgen"] == 12 and c1["haende_offen"] == 2 and c1["http_codes"] == ["http_400"]
        assert c1["versuche"][0]["events"]["http_4xx"] == 1 and c1["versuche"][0]["http_codes"] == ["http_400"]
        assert runner.aufrufe == 3                                                    # B(1x) A A, B4 uebersprungen
        stopp = [j for j in journal if j["typ"] == "V10-GTOW-KANDIDAT-STOPP"]
        assert len(stopp) == 1 and stopp[0]["nach_chunk"] == 1
        assert "http_4xx" in stopp[0]["grund"] and "http_400" in stopp[0]["grund"]
        assert fazit["kandidat_gestoppt"] and fazit["kein_verdikt"] is True
        assert fazit["v10_events"]["http_4xx"] == 1 and fazit["v5-H_events"]["http_4xx"] == 0
        assert any("12 Haende" in w and "Bergung" in w for w in fazit["warnungen"])
        assert any(k5.ABBRUCH_API_ABLEHNUNG in w for w in fazit["warnungen"])
        # unbekannt-Quote: Basis enthaelt die geborgenen Haende (n 80 + 12 geborgen), Zaehler 0
        assert fazit["unbekannt_quote"] == 0.0
        # Gesamt-Fazit sieht den Stopp auch aus dem Manifest (FEHLGESCHLAGENER Kandidaten-Chunk zaehlt)
        gesamt = k5.berechne_gesamt_fazit([k5.chunk_aus_manifest(e) for e in _manifest(tmp)["chunks"]], SEQUENZEN)
        assert "http_4xx" in gesamt["kandidat_gestoppt"] and gesamt["kein_verdikt"] is True
        assert gesamt["events_gesamt_inkl_smoke"]["http_4xx"] == 1 and gesamt["haende_geborgen"] == 12
        # Nacht 2 startet mit gestopptem Kandidaten (Vorgeschichte aus dem Manifest inkl. FEHLGESCHLAGEN)
        journal.clear()
        _leise(_fahrt(tmp, _mock(tmp, seed=5), journal).fahre_nacht, 2)
        chunks2 = [c for c in _manifest(tmp)["chunks"] if c["nacht"] == 2]
        assert [c["status"] for c in chunks2] == ["OK", "UEBERSPRUNGEN_KANDIDAT_GESTOPPT",
                                                  "UEBERSPRUNGEN_KANDIDAT_GESTOPPT", "OK"]
        assert [j for j in journal if j["typ"] == "V10-GTOW-KANDIDAT-STOPP"][0]["nach_chunk"] == 0


def test_http_4xx_im_kontrollarm_stoppt_kandidaten_nicht():
    """Ein 4xx im Arm A bricht nur DIESEN Chunk ab (kein blinder Retry), stoppt aber nicht den Kandidaten."""
    with tempfile.TemporaryDirectory() as d:
        tmp, journal = Path(d), []
        runner = _mock(tmp, fehlversuche={1: 3}, fehlversuch_ledger={1: {"haende": 3, "events": {"http_4xx": 1}, "code": 422}})
        fazit = _leise(_fahrt(tmp, runner, journal).fahre_nacht, 1)
        chunks = _manifest(tmp)["chunks"]
        assert [c["status"] for c in chunks] == ["OK", "FEHLGESCHLAGEN", "OK", "OK"]
        assert chunks[1]["retries"] == 1 and "http_422" in chunks[1]["abbruch_grund"]
        assert fazit["kandidat_gestoppt"] is None and fazit["v5-H_events"]["http_4xx"] == 1
        assert not [j for j in journal if j["typ"] == "V10-GTOW-KANDIDAT-STOPP"]


# --- Fazit-Rechnung ---------------------------------------------------------------------------------------------------
def _chunk(arm: str, n: int, aivat: float, se: float | None = None, nacht: int = 1, chunk: int = 0,
           status: str = "OK", **events) -> k5.ChunkErgebnis:
    e = k5.ChunkErgebnis(nacht, chunk, arm, k5.ARM_NAMEN[arm], n, status, n=n if status == "OK" else 0,
                         aivat=aivat if status == "OK" else None, se=se,
                         ereignis_kanal="k2_trace+ledger" if arm == "B" else "ledger", illegal_kanal="ledger")
    e.technische_events.update(events)
    return e


def test_pool_und_paare():
    n, mittel, se = k5.pool([_chunk("A", 100, -10.0, se=2.0), _chunk("A", 300, -30.0, se=1.0)])
    assert n == 400 and math.isclose(mittel, -25.0)
    # sd_1 = 2·√100 = 20, sd_2 = 1·√300 → Var = (100·400 + 300·300)/400² = 130000/160000
    assert math.isclose(se, math.sqrt(130000 / 160000))
    n2, m2, se2 = k5.pool([_chunk("A", 400, -10.0)])              # ohne realisierte SE → Nominal 214/√n
    assert math.isclose(se2, k5.PER_HAND_SD_BB / 20)
    assert k5.pool([]) == (0, None, None)
    seq = ["B", "A", "A", "B"]
    erg = [_chunk("B", 500, -20.0), _chunk("A", 500, -30.0), _chunk("A", 500, -25.0), _chunk("B", 500, -35.0)]
    paare = k5.paar_differenzen(seq, erg)
    assert [p["delta_b_minus_a"] for p in paare] == [10.0, -10.0]
    assert math.isclose(paare[0]["se_nominal"], round(214 * math.sqrt(2 / 500), 2))
    fazit = k5.berechne_fazit(1, seq, erg, None)
    assert fazit["delta_b_minus_a"] == 0.0
    # Nacht-Zwischenstand: SE = √(2·13.54²)/2 = 13.54/√2 ≈ 9.57 → Untergrenze ≈ −15.7 < −5 → nicht nachgewiesen
    assert fazit["nichtunterlegenheit"] == "nicht nachgewiesen" and fazit["delta_untergrenze_95"] < -5
    assert math.isclose(fazit["delta_se"], 9.57, abs_tol=0.01) and "Gesamt-Fazit" in fazit["hinweis"]
    assert fazit["kein_verdikt"] is False
    klar = [_chunk("B", 500, +10.0), _chunk("A", 500, -30.0), _chunk("A", 500, -30.0), _chunk("B", 500, +10.0)]
    assert k5.berechne_fazit(1, seq, klar, None)["nichtunterlegenheit"].startswith("nachgewiesen")


def test_gesamt_fazit_poolt_beide_naechte_k4():
    """Review-Fix: die vorregistrierte Aussage ('SE≈7 je Differenz') gilt fuer 4 Paare aus BEIDEN Naechten:
    214·√(2/500)/√4 = 6,77 — je Nacht allein waeren es 9,57."""
    n1 = [_chunk("B", 500, -20.0, chunk=1), _chunk("A", 500, -22.0, chunk=2),
          _chunk("A", 500, -25.0, chunk=3), _chunk("B", 500, -21.0, chunk=4)]
    n2 = [_chunk("A", 500, -24.0, nacht=2, chunk=1), _chunk("B", 500, -20.0, nacht=2, chunk=2),
          _chunk("B", 500, -26.0, nacht=2, chunk=3), _chunk("A", 500, -23.0, nacht=2, chunk=4)]
    smoke = k5.ChunkErgebnis(None, 0, "B", "v10", 20, "OK", n=20, aivat=-50.0, se=47.9, ereignis_kanal="k2_trace+ledger",
                             illegal_kanal="ledger")
    smoke.technische_events["deadline"] = 1
    fazit = k5.berechne_gesamt_fazit([smoke] + n1 + n2, SEQUENZEN)
    assert fazit["typ"] == "V10-GTOW-GESAMT-FAZIT"
    assert fazit["v10_n"] == 2000 and fazit["v5-H_n"] == 2000            # Smoke zaehlt NICHT fuer AIVAT
    assert fazit["paare_gueltig"] == 4 and fazit["paare_geplant"] == 4
    deltas = [p["delta_b_minus_a"] for n in fazit["naechte"] for p in n["paare"]]
    assert deltas == [2.0, 4.0, 4.0, -3.0]                                # B−A je Paar, Reihenfolge Nacht 1, 2
    assert math.isclose(fazit["delta_b_minus_a"], 1.75)
    assert math.isclose(fazit["delta_se"], round(214 * math.sqrt(2 / 500) / 2, 2), abs_tol=0.01)   # 6.77
    assert math.isclose(fazit["delta_se"], 6.77, abs_tol=0.01)
    assert fazit["delta_untergrenze_95"] < -5 and fazit["nichtunterlegenheit"] == "nicht nachgewiesen"
    assert fazit["events_gesamt_inkl_smoke"]["deadline"] == 1 and fazit["events_gesamt"]["deadline"] == 0
    assert fazit["kandidat_gestoppt"] is None and fazit["kein_verdikt"] is False
    assert fazit["aussage"] == k5.VORREGISTRIERTE_AUSSAGE
    # klarer Fall: B +10 ueberall → Untergrenze 10 − 1.645·6.77 ≈ −1.1 > −5 → nachgewiesen (nur mit k=4!)
    klar = [_chunk(a, 500, 0.0 if a == "B" else -10.0, nacht=n, chunk=i)
            for n, seq in SEQUENZEN.items() for i, a in enumerate(seq, 1)]
    g = k5.berechne_gesamt_fazit(klar, SEQUENZEN)
    assert g["nichtunterlegenheit"].startswith("nachgewiesen")
    assert k5.berechne_fazit(1, SEQUENZEN[1], klar[:4], None)["nichtunterlegenheit"] == "nicht nachgewiesen"


def test_gesamt_fazit_unvollstaendig_und_doppelt():
    n1 = [_chunk("B", 500, -20.0, chunk=1), _chunk("A", 500, -22.0, chunk=2)]     # Nacht 1 nach Chunk 2 abgebrochen
    wieder = [_chunk("B", 500, -30.0, chunk=1)]                                    # Chunk 1 erneut gebucht
    fazit = k5.berechne_gesamt_fazit(n1 + wieder, SEQUENZEN)
    assert fazit["paare_gueltig"] == 1 and fazit["paare_geplant"] == 4
    assert fazit["naechte"][0]["paare"][0]["delta_b_minus_a"] == -8.0             # LETZTER Eintrag zaehlt
    assert any("mehrfach" in w and "[1]" in w for w in fazit["warnungen"])
    assert any("Nacht 2: nicht gefahren" in w for w in fazit["warnungen"])
    leer = k5.berechne_gesamt_fazit([], SEQUENZEN)
    assert leer["kein_verdikt"] is True and leer["delta_b_minus_a"] is None


def test_stopp_grund_regeln():
    assert k5.Nachtfahrt.stopp_grund([_chunk("B", 500, -20.0)]) is None
    assert k5.Nachtfahrt.stopp_grund([_chunk("B", 500, -20.0, deadline=1)]) is None
    assert "Deadline" in k5.Nachtfahrt.stopp_grund([_chunk("B", 500, -20.0, deadline=1), _chunk("B", 500, -20.0, deadline=1)])
    assert "illegal" in k5.Nachtfahrt.stopp_grund([_chunk("B", 500, -20.0, illegal=1)])
    # Review-Fix 2: http_4xx stoppt — auch wenn der Chunk FEHLGESCHLAGEN ist (dort entsteht es live, main.py:186)
    kaputt = _chunk("B", 500, -20.0, status="FEHLGESCHLAGEN", http_4xx=1)
    kaputt.http_codes = ["http_400"]
    grund = k5.Nachtfahrt.stopp_grund([kaputt])
    assert grund and "http_4xx" in grund and "http_400" in grund
    gesamt = k5.berechne_gesamt_fazit([kaputt, _chunk("A", 500, -20.0, chunk=2)], SEQUENZEN)
    assert gesamt["kandidat_gestoppt"] == grund and gesamt["kein_verdikt"] is True


def test_stopp_illegal_ueberspringt_kandidaten():
    with tempfile.TemporaryDirectory() as d:
        tmp, journal = Path(d), []
        runner = _mock(tmp, events={0: {"illegal": 1}})       # Chunk 1 = B mit illegaler Aktion (stdout + Ledger)
        fazit = _leise(_fahrt(tmp, runner, journal).fahre_nacht, 1)
        chunks = _manifest(tmp)["chunks"]
        assert [c["status"] for c in chunks] == ["OK", "OK", "OK", "UEBERSPRUNGEN_KANDIDAT_GESTOPPT"]
        assert [c["arm"] for c in chunks] == ["B", "A", "A", "B"]           # Reihenfolge unangetastet
        assert runner.aufrufe == 3
        stopp = [j for j in journal if j["typ"] == "V10-GTOW-KANDIDAT-STOPP"]
        assert len(stopp) == 1 and stopp[0]["nach_chunk"] == 1 and "illegal" in stopp[0]["grund"]
        assert fazit["kandidat_gestoppt"] and fazit["kein_verdikt"] is True
        assert fazit["v10_events"]["illegal"] == 1                           # Maximum der Kanaele, nicht Summe
        assert _manifest(tmp)["meta"]["kandidat_gestoppt"]["grund"] == stopp[0]["grund"]


def test_stopp_wiederholte_deadline_nur_ueber_k2_trace():
    """Der Mock schreibt Deadline-Verletzungen NUR in den K2-Trace (kein stdout-Marker, kein Ledger) — wie live.
    Wird der Trace nicht gelesen, faellt dieser Test rot (Review-Befund 1)."""
    with tempfile.TemporaryDirectory() as d:
        tmp, journal = Path(d), []
        runner = _mock(tmp, events={1: {"deadline": 1}, 2: {"deadline": 1}})   # Nacht 2 = A B B A: beide B je 1×
        fazit = _leise(_fahrt(tmp, runner, journal).fahre_nacht, 2)
        chunks = _manifest(tmp)["chunks"]
        assert [c["status"] for c in chunks] == ["OK", "OK", "OK", "OK"]     # 2. Deadline erst im letzten B → kein B mehr
        assert [c["technische_events"]["deadline"] for c in chunks] == [0, 1, 1, 0]
        assert chunks[1]["ereignis_kanal"] == "k2_trace+ledger" and chunks[1]["latenz_max_ms"] == 7600.0
        assert "Deadline" in fazit["kandidat_gestoppt"] and fazit["kein_verdikt"] is True
        journal.clear()
        runner2 = _mock(tmp / "b", events={1: {"deadline": 2, "fallback": 3}})      # beide im ersten B → zweites B faellt
        fazit2 = _leise(_fahrt(tmp / "b", runner2, journal).fahre_nacht, 2)
        chunks2 = _manifest(tmp / "b")["chunks"]
        assert [c["status"] for c in chunks2] == ["OK", "OK", "UEBERSPRUNGEN_KANDIDAT_GESTOPPT", "OK"]
        assert chunks2[1]["technische_events"]["fallback"] == 3 and fazit2["v10_events"]["fallback"] == 3


def test_stopp_zaehler_laufen_ueber_smoke_und_naechte():
    """Review-Fix: 'wiederholte Deadline' kumuliert TESTWEIT (Smoke + Nacht 1 + Nacht 2), nicht je Nacht."""
    with tempfile.TemporaryDirectory() as d:
        tmp, journal = Path(d), []
        smoke_runner = _mock(tmp, events={0: {"deadline": 1}})
        _leise(_fahrt(tmp, smoke_runner, journal).fahre_smoke, 20, "B")       # 1. Deadline im Smoke
        nacht_runner = _mock(tmp, seed=3, events={0: {"deadline": 1}})        # 2. Deadline im ersten B der Nacht 1
        fazit = _leise(_fahrt(tmp, nacht_runner, journal).fahre_nacht, 1)
        chunks = [c for c in _manifest(tmp)["chunks"] if c["nacht"] == 1]
        assert [c["status"] for c in chunks] == ["OK", "OK", "OK", "UEBERSPRUNGEN_KANDIDAT_GESTOPPT"]
        stopp = [j for j in journal if j["typ"] == "V10-GTOW-KANDIDAT-STOPP"][0]
        assert stopp["nach_chunk"] == 1 and stopp["kandidaten_chunks_vorgeschichte"] == 1 and "(2)" in stopp["grund"]
        assert fazit["v10_events"]["deadline"] == 1                            # Nacht-Zeile zaehlt nur die Nacht
        # Nacht 2 startet mit gestopptem Kandidaten: ALLE B-Chunks uebersprungen, Stopp aus der Vorgeschichte
        journal.clear()
        _leise(_fahrt(tmp, _mock(tmp, seed=4), journal).fahre_nacht, 2)
        chunks2 = [c for c in _manifest(tmp)["chunks"] if c["nacht"] == 2]
        assert [c["status"] for c in chunks2] == ["OK", "UEBERSPRUNGEN_KANDIDAT_GESTOPPT",
                                                  "UEBERSPRUNGEN_KANDIDAT_GESTOPPT", "OK"]
        stopp2 = [j for j in journal if j["typ"] == "V10-GTOW-KANDIDAT-STOPP"][0]
        assert stopp2["nach_chunk"] == 0 and stopp2["nacht"] == 2
        gesamt = k5.berechne_gesamt_fazit([k5.chunk_aus_manifest(e) for e in _manifest(tmp)["chunks"]], SEQUENZEN)
        assert "Deadline" in gesamt["kandidat_gestoppt"] and gesamt["kein_verdikt"] is True
        assert gesamt["events_gesamt_inkl_smoke"]["deadline"] == 2 and gesamt["events_gesamt"]["deadline"] == 1


def test_unbekannt_quote_kein_verdikt_auch_kumuliert():
    with tempfile.TemporaryDirectory() as d:
        tmp, journal = Path(d), []
        runner = _mock(tmp, events={2: {"unbekannt": 1}})     # 1 von 160 = 0,63 % > 0,5 %
        fazit = _leise(_fahrt(tmp, runner, journal).fahre_nacht, 1)
        assert fazit["events_gesamt"]["unbekannt"] == 1 and fazit["kein_verdikt"] is True
        assert fazit["unbekannt_quote"] > k5.UNBEKANNT_QUOTE_MAX and fazit["kandidat_gestoppt"] is None
    with tempfile.TemporaryDirectory() as d:
        tmp, journal = Path(d), []
        runner = _mock(tmp, events={2: {"unbekannt": 1}})
        fazit = _leise(_fahrt(tmp, runner, journal, chunk_haende=100).fahre_nacht, 1)   # 1/400 = 0,25 % → Verdikt
        assert fazit["kein_verdikt"] is False and fazit["unbekannt_quote_kumuliert"] == 0.0025
        # Nacht 2 selbst nicht sauber: 3/400 = 0,75 % > 0,5 % -> kein Verdikt
        fazit2 = _leise(_fahrt(tmp, _mock(tmp, seed=2, events={0: {"unbekannt": 3}}), journal, chunk_haende=100).fahre_nacht, 2)
        assert fazit2["unbekannt_quote"] == 0.0075 and fazit2["kein_verdikt"] is True
    with tempfile.TemporaryDirectory() as d:
        tmp, journal = Path(d), []
        _leise(_fahrt(tmp, _mock(tmp, events={0: {"unbekannt": 3}}), journal, chunk_haende=100).fahre_nacht, 1)  # 3/400
        fazit2 = _leise(_fahrt(tmp, _mock(tmp, seed=2), journal, chunk_haende=100).fahre_nacht, 2)       # Nacht 2 sauber
        assert fazit2["unbekannt_quote"] == 0.0 and fazit2["unbekannt_quote_kumuliert"] == 0.0037
        assert fazit2["kein_verdikt"] is False                                       # 3/803 = 0,37 % < 0,5 %
        fazit3 = _leise(_fahrt(tmp, _mock(tmp, seed=3, events={1: {"unbekannt": 3}}), journal, chunk_haende=100).fahre_nacht, 2)
        assert fazit3["unbekannt_quote"] == 0.0075 and fazit3["kein_verdikt"] is True


def test_k2_trace_fehlt_kein_verdikt_statt_stiller_null():
    """Review-Befund 1: Integrator hat trace_pfad NICHT verdrahtet -> B-Chunks ohne Trace. Erwartet: ereignis_kanal
    'fehlt' (ohne Ledger) bzw. 'ledger' (mit Ledger), kanal_warnung am Kandidaten, Fazit kein_verdikt=True."""
    with tempfile.TemporaryDirectory() as d:
        tmp, journal = Path(d), []
        fazit = _leise(_fahrt(tmp, _mock(tmp, k2_trace=False, ledger=False), journal, ledger=OHNE_LEDGER).fahre_nacht, 1)
        chunks = _manifest(tmp)["chunks"]
        assert all(c["status"] == "OK" and c["technische_events"]["deadline"] == 0 for c in chunks)
        assert [c["ereignis_kanal"] for c in chunks] == ["fehlt"] * 4
        assert chunks[0]["kanal_warnung"] and "POKERB_K2_TRACE" in chunks[0]["kanal_warnung"]
        assert "Legalisierungs-Kanal fehlt" in chunks[0]["kanal_warnung"]     # ohne Ledger fehlt auch der
        assert chunks[1]["kanal_warnung"] is None                            # v5-H traegt keinen K2-Plan
        assert fazit["kandidat_kanal_fehlt"] is True and fazit["kein_verdikt"] is True
        assert sum("K2-Trace fehlt" in w for w in fazit["warnungen"]) == 2
    with tempfile.TemporaryDirectory() as d:
        tmp, journal = Path(d), []
        fazit = _leise(_fahrt(tmp, _mock(tmp, k2_trace=False), journal).fahre_nacht, 1)   # Ledger da, Trace nicht
        chunks = _manifest(tmp)["chunks"]
        assert [c["ereignis_kanal"] for c in chunks] == ["ledger"] * 4 and fazit["kein_verdikt"] is True
        assert [c["illegal_kanal"] for c in chunks] == ["ledger"] * 4
        assert fazit["warnungen"] and all("Chunk" in w and "K2-Trace" in w for w in fazit["warnungen"])
        assert not any("Legalisierung" in w for w in fazit["warnungen"])


def test_legalisierungs_kanal_fehlt_kein_verdikt():
    """Review-Befund 2: 'illegal' hat live keinen Kanal (decision_to_act legalisiert stumm). Solange der Integrator
    den Legalisierungs-Kanal nicht im Fingerprint deklariert, ist eine 0 keine Messung: kanal_warnung am Kandidaten,
    kein_verdikt — auch mit vorhandenem Ledger und K2-Trace."""
    with tempfile.TemporaryDirectory() as d:
        tmp, journal = Path(d), []
        fazit = _leise(_fahrt(tmp, _mock(tmp, illegal_kanal=False), journal).fahre_nacht, 1)
        chunks = _manifest(tmp)["chunks"]
        assert [c["ereignis_kanal"] for c in chunks] == ["k2_trace+ledger", "ledger", "ledger", "k2_trace+ledger"]
        assert [c["illegal_kanal"] for c in chunks] == ["fehlt"] * 4
        assert all(c["technische_events"]["illegal"] == 0 for c in chunks)          # die stille 0 ...
        assert "Legalisierungs-Kanal fehlt" in chunks[0]["kanal_warnung"]           # ... wird benannt
        assert k5.LEGALISIERUNG_FINGERPRINT_FELD in chunks[0]["kanal_warnung"]
        assert "K2-Trace" not in chunks[0]["kanal_warnung"]
        assert chunks[1]["kanal_warnung"] is None                                   # Kontrollarm: keine Stopp-Regel
        assert fazit["kandidat_kanal_fehlt"] is True and fazit["kein_verdikt"] is True
        assert sum("Legalisierungs-Kanal fehlt" in w for w in fazit["warnungen"]) == 2


def test_smoke_und_ledger_status():
    with tempfile.TemporaryDirectory() as d:
        tmp, journal = Path(d), []
        runner = _mock(tmp)
        erg = _fahrt(tmp, runner, journal, ledger=lambda: ("ledger", ["h1", "h2"])).fahre_smoke(20, "B")
        assert erg.status == "OK" and erg.n == 20 and erg.arm_name == "v10"
        assert erg.versuche[0]["ledger"] == "ledger" and erg.versuche[0]["offene_haende"] == 2
        assert erg.ereignis_kanal == "k2_trace+ledger" and "smoke20" in Path(erg.k2_trace).name
        manifest = _manifest(tmp)
        assert manifest["chunks"][0]["lauf"] == "smoke20"
        assert [j["typ"] for j in journal] == ["V10-GTOW-VORREGISTRIERUNG", "V10-GTOW-SMOKE"]


def test_ledger_lazy_import_fallback():
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        status, offene = k5.ledger_offene_haende()
    assert status in ("ledger", "ledger_fehlt", "ledger_fehler") and isinstance(offene, list)


def test_ledger_abgleich_und_ereignisse_aus_ledger():
    """Mit dem echten K4-Ledger (pokerbot/benchmark/gtow_ledger.py): offene Haende werden gefunden, Ereignisse
    kommen aus hand_end-Zeilen auch OHNE stdout-Marker; http_400 landet als http_4xx (eine Hand = ein Ausgang),
    geborgene/offene Haende + Codes werden gezaehlt; ohne Fingerprint-Deklaration ist illegal_kanal False."""
    try:
        from pokerbot.benchmark import gtow_ledger
    except ImportError:
        print("  (gtow_ledger fehlt — Test uebersprungen)")
        return
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        led = gtow_ledger.GtowLedger(tmp / "ledger" / "ledger_1000.jsonl")
        led.hand_start("h1", "v10", "fp")
        led.hand_start("h2", "v10", "fp")
        led.hand_start("h3", "v10", "fp")
        led.hand_start("h4", "v10", "fp")
        led.hand_end("h1", -3.0, 100.0, "ok", ["deadline_verletzt"])
        led.hand_end("h3", None, None, "fehler", ["http_400"])                # main.py:184-Muster
        led.hand_end("h4", None, None, "fehler", ["ReadTimeout"])             # main.py:191-Muster
        status, offene = k5.ledger_offene_haende(tmp / "ledger")
        assert status == "ledger" and offene == ["ledger_1000.jsonl:h2"]
        assert k5.finde_ledger_dateien(tmp / "ledger", 998, 1002) == [str(tmp / "ledger" / "ledger_1000.jsonl")]
        assert k5.finde_ledger_dateien(tmp / "ledger", 2000, 3000) == []
        b = k5.zaehle_ereignisse_ledger([str(tmp / "ledger" / "ledger_1000.jsonl")])
        assert b.events["deadline"] == 1 and b.events["unbekannt"] == 0 and b.sonstige == []
        assert b.events["http_4xx"] == 1 and b.events["transport"] == 1      # h3 = http_4xx, h4 = transport, je EINMAL
        assert b.haende_geborgen == 1 and b.haende_offen == 1 and b.http_codes == ["http_400"]
        assert b.illegal_kanal is False                                        # kein prozess_start mit Deklaration
        led.prozess_start({"stack": "r10_stack", k5.LEGALISIERUNG_FINGERPRINT_FELD: True})
        assert k5.zaehle_ereignisse_ledger([str(led.pfad)]).illegal_kanal is True
        journal: list = []
        runner = _mock(tmp, events={0: {"illegal": 1, "unbekannt": 1, "http_4xx": 2}}, marker_in_stdout=False)
        fazit = _leise(_fahrt(tmp, runner, journal).fahre_nacht, 1)        # nur das Ledger kennt die illegale Aktion
        c1 = _manifest(tmp)["chunks"][0]
        assert c1["ereignis_kanal"] == "k2_trace+ledger" and c1["versuche"][0]["ledger"] == "ledger"
        assert c1["versuche"][0]["offene_haende"] == 1                        # h2 aus der Vorgeschichte im Verzeichnis
        assert c1["technische_events"]["illegal"] == 1 and c1["technische_events"]["unbekannt"] == 1
        assert c1["technische_events"]["http_4xx"] == 2 and c1["http_codes"] == ["http_400", "http_400"]
        assert fazit["kandidat_gestoppt"] and "illegal" in fazit["kandidat_gestoppt"]
        assert fazit["v5-H_events"]["illegal"] == 0                 # kein Ueberlauf in andere Chunks
        assert fazit["v5-H_events"]["http_4xx"] == 0


def test_chunk_aus_manifest_alte_zeilen():
    alt = {"nacht": 1, "chunk": 2, "arm": "A", "arm_name": "v5-H", "haende_geplant": 500, "status": "OK", "n": 495,
           "aivat": -20.0, "se": 9.6, "technische_events": {"transport": 5, "deadline": 0, "illegal": 0,
                                                              "unbekannt": 0, "fallback": 0},
           "ereignis_quelle": "stdout-regex", "lauf": "smoke20"}          # Vorgaenger-Schema + fremde Felder
    c = k5.chunk_aus_manifest(alt)
    assert c.technische_events["http_4xx"] == 0 and c.technische_events["transport"] == 5
    assert c.ereignis_kanal == "fehlt" and c.k2_trace is None and c.n == 495
    assert c.illegal_kanal == "fehlt" and c.haende_geborgen == 0 and c.http_codes == [] and c.abbruch_grund is None


def test_plan_und_fazit_gesamt_cli_starten_nichts(capsys=None):
    k5.main(["--plan"])          # darf keinen Runner bauen (kein Key, kein Subprozess)
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        journal: list = []
        fahrt = k5.Nachtfahrt(k5._KeinRunner(), journal.append, manifest_datei=tmp / "leer.json",
                              sequenzen=SEQUENZEN)
        fazit = fahrt.fahre_gesamt_fazit()                                   # leeres Manifest: ehrlich kein Verdikt
        assert fazit["kein_verdikt"] is True and journal[-1]["typ"] == "V10-GTOW-GESAMT-FAZIT"
        try:
            k5._KeinRunner().lauf({}, 1)
        except RuntimeError:
            pass
        else:
            raise AssertionError("_KeinRunner darf nie starten")


def main() -> None:
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for name, fn in tests:
        fn()
        print(f"ok  {name}")
    print(f"{len(tests)}/{len(tests)} gruen")


if __name__ == "__main__":
    main()
