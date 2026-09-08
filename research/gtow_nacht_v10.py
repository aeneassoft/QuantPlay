"""K5 — GTOW-Nachtfahrplan v10 (Build-Karte docs/V10_BUILD_CARD.md K5 + E8/E10; Fakten docs/V10_FAKTEN.md A8/B14).

Zwei Arme auf dem Live-Fundament (PRINCE + Harness-Default-Resolver ON, OHNE RAISE_NARROW — v8-K3-Kontra-
indikation, data/runs/gtow_v8_protokoll_2026-08-31.json '1_arm_konfigurationen'):
  A = 'v5-H'  {POKERB_PRINCE=1, POKERB_AUSLESE_STACK=r8_stack}   (eingefrorene v5-Strategie, reparierter Kanal)
  B = 'v10'   {POKERB_PRINCE=1, POKERB_AUSLESE_STACK=r10_stack}  (K1-Hero-Range + K2-River-Plan)
Reihenfolge VORAB per Muenze (data/runs/v10_muenze.json 'BAAB_dann_ABBA'): Nacht 1 = B A A B, Nacht 2 = A B B A.
Benachbarte Chunks bilden Vergleichspaare (randomisiertes Blockdesign OHNE CRN). Der Code kann die Sequenz NICHT
ergebnisabhaengig veraendern — es gibt keinen Pfad, der sie liest und anders schreibt.

Mechanik je Chunk (Vorlage research/gtow_nacht.py, NICHT veraendert): frischer Subprozess `tools/gtow_run.py
--agent_type pokerbot --num_hands N` mit Env-Hygiene (alle POKERB_* gestrippt, dann Arm-Env, PYTHONUTF8=1,
GTOWIZARD_API_KEY aus derselben Key-Datei wie gtow_nacht.py), Timeout 10800 s, Retry max 3. VOR jedem Start und
vor jedem Retry: Abgleich offener Haende im Ledger (pokerbot.benchmark.gtow_ledger.offene_haende, lazy; fehlt das
Modul → Warnung + Weiterfahrt) und DANN clear_inprogress (409-Waisen-Pflicht, Protokoll '5_pflicht_schritte'[1]).

Buchfuehrung: Manifest data/runs/v10/gtow_manifest_v10.json (nach JEDEM Chunk geschrieben = Versicherung),
Journal-Eintraege V10-GTOW-VORREGISTRIERUNG (einmal, Karte-K5-Aussage woertlich) / V10-GTOW-CHUNK / V10-GTOW-
NACHT-FAZIT (gepoolt je Arm, Blockpaar-Differenzen B−A, einfache SE, technische Ausfaelle nach Klassen).
STOPP-Regeln (Karte K5): illegale Bot-Aktion ODER wiederholte Deadline-Verletzung → Kandidat B gestoppt
(weitere B-Chunks werden uebersprungen, Journal V10-GTOW-KANDIDAT-STOPP); unbekannte Ausgaenge > 0,5 % →
Fazit-Flag `kein_verdikt`. Die Zaehler laufen ueber den GESAMTEN Live-Test (Smoke + Nacht 1 + Nacht 2): jede
Fahrt liest die Kandidaten-Chunks aus dem Manifest als Vorgeschichte (Review-Fix 2026-09-07).

EREIGNIS-KANAELE (Review-Fix 2026-09-07 — vorher hatten deadline/fallback im Live-Lauf KEINEN Datenkanal):
  k2_trace   = river_plan.RiverPlanFabrik._trace schreibt je Hero-Entscheidung eine JSONL-Zeile mit den Vertrags-
               feldern fallback_status/deadline_status/offtree/latenz_ms (river_plan.py:690-715). K5 gibt je Chunk
               einen Pfad ueber die Env POKERB_K2_TRACE; der INTEGRATOR muss ihn in river_plan_guard(trace_pfad=
               os.environ.get('POKERB_K2_TRACE')) durchreichen (Fallback-Schnittstelle: solange das fehlt, steht im
               Manifest ereignis_kanal='fehlt'/'ledger' + kanal_warnung, und die Nacht endet mit kein_verdikt —
               nie eine stille 0). Klassifikation EXAKT: deadline := deadline_status=='verletzt' ODER
               fallback_status=='deadline'; fallback := fallback_status in {offtree, fehler, hand_not_in_range}.
  ledger     = gtow_ledger.hand_end (status + technische_events-Strings; heute nur in den Fehlerzweigen main.py:184/191
               belegt: 'http_<code>' / Exceptionname). http_4xx (ausser 409/429) = eigene Klasse (Verdacht auf
               abgelehnte Aktion); 409/429/5xx/Exceptions = transport.
  stdout-regex = letzter Fallback fuer 'illegal' (gtowizard.decision_to_act legalisiert heute STUMM, gtowizard.py:171
               — bis der Integrator dort ein Ereignis loggt, ist 'illegal' live nicht beobachtbar; der Kanal ist im
               Manifest als solcher ausgewiesen).
  LEGALISIERUNG (Review-Fix 2 2026-09-07): Vertrag mit dem Integrator = jeder Legalitaets-Eingriff in decision_to_act
               schreibt 'legalisiert:<von>-><nach>' in die technische_events der Hand (K5 zaehlt das als 'illegal') UND
               der prozess_start-Fingerprint traegt LEGALISIERUNG_FINGERPRINT_FELD=True. Nur so kann K5 den KANAL von
               seiner Stille unterscheiden: ohne das Feld steht am Kandidaten-Chunk illegal_kanal='fehlt' + kanal_warnung
               → kein_verdikt. Eine 0 ohne Kanal ist keine Messung.

FEHLVERSUCHE ZAEHLEN (Review-Fix 1 2026-09-07): der Harness bricht bei JEDEM nicht-busy-HTTP-Fehler den ganzen Chunk ab
(main.py:186 'if not is_engine_busy_exception(e): raise'; busy = 409/502/503/504, utils.py:6-19). Das Ledger dieses
Versuchs traegt dann hand_end der bereits gespielten Haende (AIVAT → 'geborgen', Bergungs-Lektion Nacht 1) und das
'http_<code>'-Ereignis der abgelehnten Hand. Deshalb wird JEDER Versuch ausgewertet (Ledger + K2-Trace + stdout), die
Ereignisse werden ueber die Versuche SUMMIERT (getrennte Prozesse) und je Versuch im Manifest gefuehrt. http_4xx im
Fehlversuch → KEIN blinder Retry (die API hat unsere Anfrage abgelehnt; 2×500 weitere Haende waeren verbrannt) →
Chunk FEHLGESCHLAGEN mit abbruch_grund; beim Kandidaten zusaetzlich Stopp-Regel (stopp_grund kennt http_4xx).

GESAMT-FAZIT: die vorregistrierte Aussage ('SE≈7 je Differenz') gilt fuer den GESAMTEN Test = 4 Blockpaare aus
beiden Naechten (214·√(2/500)/√4 = 6,77), nicht je Nacht (9,57). `--fazit-gesamt` poolt alle gueltigen Paare aus dem
Manifest → Journal V10-GTOW-GESAMT-FAZIT; das Nacht-Fazit bleibt ein Zwischenstand.

Staffel (Karte K5 'Smoke 20 → 100 mit v10', dann Naechte):
  python -m research.gtow_nacht_v10 --smoke 20 --arm B
  python -m research.gtow_nacht_v10 --smoke 100 --arm B
  python -m research.gtow_nacht_v10 --nacht 1
  python -m research.gtow_nacht_v10 --nacht 2
  python -m research.gtow_nacht_v10 --fazit-gesamt     (nach Nacht 2: beide Naechte gepoolt, k=4 Paare)
  python -m research.gtow_nacht_v10 --plan            (druckt Sequenz + Env, startet NICHTS)
  python -m research.gtow_nacht_v10 --nacht 1 --dry-run   (Mock-Runner, synthetische AIVAT, eigenes Journal)
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import random
import re
import subprocess
import sys
import time
import warnings
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Callable, Protocol

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
# Eingefrorener Vertrag (P0b): die Trace-Klassifikation MUSS gegen genau diese Werte laufen.
from pokerbot.strategy.contracts import DEADLINE_STATUS, FALLBACK_STATUS  # noqa: E402
# Dieselbe Key-Quelle wie research/gtow_nacht.py:26 (Key #3); gtow_run.py liest config.GTOWIZARD_API_KEY, und dort
# gewinnt die Env-Variable (pokerbot/config.py:56-59) → wir setzen GTOWIZARD_API_KEY im Subprozess-Env.
KEY_DATEI = Path(r"C:/Users/hampe/Desktop/Secret keys/Poker/GTOW API key #3.txt")
MUENZE_DATEI = REPO / "data" / "runs" / "v10_muenze.json"
MANIFEST_DATEI = REPO / "data" / "runs" / "v10" / "gtow_manifest_v10.json"
SESSIONS_DIR = REPO / "data" / "sessions"
CLEAR_CWD = REPO / "tools" / "gtow_client" / "src"          # clear_inprogress.py lebt im gitignorierten Client

# --- Arme (Karte K5 + Protokoll arm_b1_v8_resolver_on) ------------------------------------------------------------
ARME: dict[str, dict[str, str]] = {
    "A": {"POKERB_PRINCE": "1", "POKERB_AUSLESE_STACK": "r8_stack", "POKERB_ERWARTE_PROFIL": "v5-H"},
    "B": {"POKERB_PRINCE": "1", "POKERB_AUSLESE_STACK": "r10_stack", "POKERB_ERWARTE_PROFIL": "v10"},
}
ARM_NAMEN = {"A": "v5-H", "B": "v10"}
KANDIDAT = "B"
# Harness-Default ON (gtowizard.py:190-193); RAISE_NARROW + resolver-ON = v8-K3-Falle (gto_mode.py:61). Ein Arm, der
# eines davon setzt, ist ein Konfigurationsfehler → pruefe_arm_env() wirft.
VERBOTENE_ARM_ENV = ("POKERB_RESOLVER", "POKERB_TURN_RESOLVER", "POKERB_RAISE_NARROW")
# Je-Chunk-Env (additiv zum Arm-Env): Arm-Name fuers Ledger (runtime_config.ENV_ARM erwartet ihn von uns) + der
# K2-Trace-Pfad (siehe Modul-Docstring EREIGNIS-KANAELE). Nur der Kandidat traegt den K2-River-Plan (Karte K5 Arm B).
ARM_ENV_NAME = "POKERB_ARM"
K2_TRACE_ENV = "POKERB_K2_TRACE"
K2_TRACE_ARME = (KANDIDAT,)
K2_TRACE_INTEGRATION_HINWEIS = ("Integrator: river_plan_guard(trace_pfad=os.environ.get('POKERB_K2_TRACE')) im "
                                "r10_stack-Aufbau durchreichen -- sonst ereignis_kanal='fehlt' und kein_verdikt")

# --- Mess-Konstanten -----------------------------------------------------------------------------------------------
CHUNK_HAENDE = 500                  # Karte K5 'Chunks à 500'
CHUNK_TIMEOUT_S = 10800             # gtow_nacht.py:40 (3 h je Chunk; FAKTEN B14 kennt das Risiko)
MAX_VERSUCHE = 3                    # gtow_nacht.py:73 'for versuch in range(1, 4)'
RETRY_PAUSE_S = 60                  # gtow_nacht.py:83: 60 s × Versuchsnummer
CLEAR_TIMEOUT_S = 1200              # gtow_nacht.py:52
SMOKE_STAFFEL = (20, 100)           # Karte K5 'Smoke 20 → 100 mit v10'
PER_HAND_SD_BB = 214.0              # Protokoll '2_n_se_planung' per_hand_sd (v2.2-Anker n=2393) — Nominal-SE
UNBEKANNT_QUOTE_MAX = 0.005         # Karte K5: 'Unbekannte Ausgaenge > 0,5 % → kein Leistungsverdikt'
DEADLINE_WIEDERHOLT_AB = 2          # 'wiederholte Deadline-Verletzung' = ab der zweiten im Kandidaten-Arm
NICHTUNTERLEGENHEIT_MARGE_BB = -5.0 # Karte K5 vorregistrierte Aussage
Z_EINSEITIG_95 = 1.645
# http_4xx: Harness-Fehlerzweig main.py:184 'http_<code>' nach erschoepften Retries; 4xx ausser 409/429 = die API hat
# unsere Anfrage ABGELEHNT (Verdacht auf illegale Aktion / Protokollfehler) — eigene Klasse, nie in 'transport' versteckt.
EREIGNIS_KLASSEN = ("transport", "deadline", "illegal", "unbekannt", "fallback", "http_4xx")
HTTP_TRANSPORT_CODES = (409, 429)   # 409 = Waisen/Konflikt (utils.is_engine_busy_exception), 429 = Rate-Limit
# Legalisierungs-Kanal (Modul-Docstring LEGALISIERUNG) — Fallback-Schnittstelle zum Integrator, Status im Manifest:
# Ereignis-Prefix in hand_end.technische_events + Feld im prozess_start-Fingerprint (runtime_config.fingerprint_geladen).
LEGALISIERUNG_EVENT_PREFIX = "legalisiert"
LEGALISIERUNG_FINGERPRINT_FELD = "legalisierung_ledger"
LEGALISIERUNG_INTEGRATION_HINWEIS = ("Integrator: decision_to_act (gtowizard.py:171-176) soll jeden Legalitaets-Eingriff "
                                     f"als '{LEGALISIERUNG_EVENT_PREFIX}:<von>-><nach>' ins Ledger schreiben und "
                                     f"fingerprint_geladen() '{LEGALISIERUNG_FINGERPRINT_FELD}': True setzen -- bis "
                                     "dahin ist 'illegal' live nicht beobachtbar und die Nacht endet mit kein_verdikt")
ABBRUCH_API_ABLEHNUNG = "api_ablehnung"   # abbruch_grund-Kennung: http_4xx im Fehlversuch, kein blinder Retry

# Trace-Klassifikation gegen den eingefrorenen Vertrag — ein Vertragsbruch faellt hier beim Import auf, nicht in der Nacht.
TRACE_DEADLINE_VERLETZT = "verletzt"                      # DEADLINE_STATUS
TRACE_FALLBACK_DEADLINE = "deadline"                      # FALLBACK_STATUS
TRACE_FALLBACK_KLASSEN = ("offtree", "fehler", "hand_not_in_range")   # FALLBACK_STATUS, die einen Fallback bedeuten
assert TRACE_DEADLINE_VERLETZT in DEADLINE_STATUS, DEADLINE_STATUS
assert TRACE_FALLBACK_DEADLINE in FALLBACK_STATUS and set(TRACE_FALLBACK_KLASSEN) <= set(FALLBACK_STATUS), FALLBACK_STATUS
LATENZ_P99_QUANTIL = 0.99                                 # E10: Plan-Pot-Entscheidungen p99 < 8 s, kein Aufruf >= 30 s

# Karte K5, Zeilen 104-107 — WOERTLICH (die vorregistrierte Aussage geht so ins Journal).
VORREGISTRIERTE_AUSSAGE = (
    "Der Live-Test schätzt den AIVAT-Stand beider Arme und deren Differenz Δ = μ_v10 − μ_v5-H; primär "
    "explorativ (große Effekte/Regressionen). Nichtunterlegenheit mit Marge −5 bb/100 wird NUR behauptet, wenn "
    "die einseitige 95 %-Untergrenze sie trägt (bei SE≈7 je Differenz ist das bei Gleichstand NICHT der Fall → "
    "dann „nicht nachgewiesen\", nie „gleich gut\")."
)

# --- Harness-Ausgabe (tools/gtow_client/src/main.py:231-233) --------------------------------------------------------
AIVAT_RE = re.compile(r"AIVAT luck-adj : ([+-]?\d+\.\d+) \+/- ([\d.]+) bb/100  \(n=(\d+)\)")
HAENDE_RE = re.compile(r"Successful hands: (\d+)\. Failed hands: (\d+)\.")
# LETZTER Fallback aus der Prozessausgabe (Review 2026-09-07: river_plan.py schreibt KEINE stdout-Zeile, decision_to_act
# legalisiert stumm → live liefert dieser Kanal heute nur, was der Integrator zusaetzlich loggt). Die strukturierten
# Kanaele (K2-Trace, Ledger) sind massgeblich; je Klasse zaehlt das Maximum aller Kanaele.
EREIGNIS_MUSTER = {
    "illegal": re.compile(r"\billegal", re.IGNORECASE),
    "deadline": re.compile(r"\bdeadline", re.IGNORECASE),
    "fallback": re.compile(r"\bfallback\b|\bofftree\b", re.IGNORECASE),
}


def pruefe_arm_env(arm_env: dict[str, str]) -> None:
    """Wirft, wenn ein Arm die Harness-Defaults antastet (Protokoll 'explizit_NICHT_setzen')."""
    verletzt = [k for k in VERBOTENE_ARM_ENV if k in arm_env]
    if verletzt:
        raise ValueError(f"Arm-Env setzt verbotene Schluessel {verletzt} (v8-K3-Kontraindikation)")


for _env in ARME.values():
    pruefe_arm_env(_env)


# --- Sequenz aus der Muenze ----------------------------------------------------------------------------------------
def sequenzen_aus_muenze(muenze: str) -> dict[int, list[str]]:
    """'BAAB_dann_ABBA' → {1: [B,A,A,B], 2: [A,B,B,A]}. Reine Funktion der Muenze — keine andere Eingabe."""
    teile = muenze.split("_dann_")
    if len(teile) != 2 or any(set(t) - set(ARME) or len(t) != 4 for t in teile):
        raise ValueError(f"Muenze nicht lesbar: {muenze!r} (erwartet z.B. 'BAAB_dann_ABBA')")
    return {1: list(teile[0]), 2: list(teile[1])}


def lade_sequenzen(muenze_datei: Path = MUENZE_DATEI) -> dict[int, list[str]]:
    with muenze_datei.open(encoding="utf-8") as f:
        return sequenzen_aus_muenze(json.load(f)["muenze"])


def blockpaare(sequenz: list[str]) -> list[tuple[int, int]]:
    """Benachbarte Chunks (1,2),(3,4) als Vergleichspaare — Karte K5. Indizes 0-basiert."""
    return [(i, i + 1) for i in range(0, len(sequenz) - 1, 2)]


# --- Datentypen ----------------------------------------------------------------------------------------------------
@dataclass
class RohLauf:
    """Was ein Runner von EINEM Versuch zurueckgibt — Ausgabe im Harness-Format, ohne Interpretation."""
    returncode: int
    ausgabe: str
    start_epoch: float
    ende_epoch: float
    hh_datei: str | None = None      # Mock setzt sie direkt; Subprozess: None → per Sessions-Verzeichnis ermittelt
    ledger_dateien: list[str] | None = None   # dito: Mock explizit, Subprozess per Zeitfenster im Ledger-Verzeichnis
    fehlerklasse: str | None = None  # 'chunk_timeout' / 'ausnahme' — wenn der Prozess selbst nicht durchkam


@dataclass
class ChunkErgebnis:
    nacht: int | None
    chunk: int
    arm: str
    arm_name: str
    haende_geplant: int
    status: str                                       # OK / FEHLGESCHLAGEN / UEBERSPRUNGEN_KANDIDAT_GESTOPPT
    n: int = 0
    aivat: float | None = None
    se: float | None = None
    hh_datei: str | None = None
    start: str | None = None
    ende: str | None = None
    retries: int = 0
    technische_events: dict[str, int] = field(default_factory=lambda: {k: 0 for k in EREIGNIS_KLASSEN})
    # Welche STRUKTURIERTEN Kanaele diesen Chunk wirklich abgedeckt haben: 'k2_trace+ledger' / 'k2_trace' / 'ledger' /
    # 'fehlt'. stdout-regex wird nicht als Abdeckung gefuehrt (Review: er suggerierte Abdeckung, die live nicht existiert).
    ereignis_kanal: str = "fehlt"
    kanal_warnung: str | None = None                  # gesetzt, wenn dem Kandidaten der K2-Trace fehlt
    k2_trace: str | None = None                       # Pfad der Trace-Datei (None = nicht vorhanden)
    k2_entscheidungen: int = 0                        # Trace-Zeilen = Hero-Entscheidungen mit River-Plan-Wrapper
    latenz_p99_ms: float | None = None                # aus dem Trace (E10-Gate: Plan-Pot p99 < 8 s, max < 30 s)
    latenz_max_ms: float | None = None
    sonstige_events: list[str] = field(default_factory=list)   # Ledger-Strings ohne K5-Klasse (nie verschwiegen)
    # Review-Fix 1+2 (2026-09-07): Fehlversuche zaehlen, Legalisierungs-Kanal ausgewiesen.
    illegal_kanal: str = "fehlt"                      # 'ledger' nur, wenn der Fingerprint das Legalisierungs-Logging deklariert
    abbruch_grund: str | None = None                  # gesetzt, wenn die Retry-Schleife bewusst NICHT weiterlief (api_ablehnung)
    haende_geborgen: int = 0                          # hand_end MIT AIVAT aus FEHLVERSUCHEN (nicht in n; Bergung moeglich)
    haende_offen: int = 0                             # hand_start ohne hand_end ueber alle Versuche (Abbruch mitten in der Hand)
    http_codes: list[str] = field(default_factory=list)      # alle 'http_<code>'-Strings — der Stopp-Grund nennt sie
    ledger_dateien: list[str] = field(default_factory=list)  # alle Ledger-Dateien ALLER Versuche (Bergungs-Quelle)
    versuche: list[dict] = field(default_factory=list)


_CHUNK_FELDER = {f.name for f in fields(ChunkErgebnis)}
GEFAHREN_STATUS = ("OK", "FEHLGESCHLAGEN")   # Chunks, die wirklich Haende gespielt haben (Ereignisse existieren)


@dataclass
class VersuchBefund:
    """Auswertung EINES Versuchs ueber alle Kanaele (Review-Fix 1: auch fuer gescheiterte Versuche)."""
    events: dict[str, int]                 # je Klasse Maximum ueber die Kanaele DIESES Versuchs
    kanaele: list[str]                     # strukturierte Kanaele, die gelesen wurden ('k2_trace', 'ledger')
    trace: "TraceBefund | None"
    ledger: "LedgerBefund | None"
    ledger_dateien: list[str]
    hh_datei: str | None
    trace_pfad: str

    def manifest_zeile(self) -> dict:
        """Die Versuchs-Sicht fuers Manifest — Fehlversuche mit Ledger werden so zur Bergungs-Quelle."""
        return {"kanaele": self.kanaele, "events": self.events, "ledger_dateien": self.ledger_dateien,
                "haende_geborgen": self.ledger.haende_geborgen if self.ledger else None,
                "haende_offen": self.ledger.haende_offen if self.ledger else None,
                "http_codes": self.ledger.http_codes if self.ledger else []}


def _maximiere(events: dict[str, int], neue: dict[str, int]) -> None:
    """Je Klasse das Maximum zweier Kanaele desselben Versuchs (dieselbe Hand, mehrfach gesehen)."""
    for klasse, anzahl in neue.items():
        events[klasse] = max(events.get(klasse, 0), anzahl)


def chunk_aus_manifest(eintrag: dict) -> ChunkErgebnis:
    """Manifest-Zeile → ChunkErgebnis (fremde Schluessel wie 'lauf' ignoriert; aeltere Zeilen ohne neue Klassen/Felder
    werden auf die Defaults ergaenzt, damit die Zaehler ueber Manifest-Generationen hinweg addierbar bleiben)."""
    daten = {k: v for k, v in eintrag.items() if k in _CHUNK_FELDER}
    events = {k: 0 for k in EREIGNIS_KLASSEN}
    events.update(daten.get("technische_events") or {})
    daten["technische_events"] = events
    return ChunkErgebnis(**daten)


class Runner(Protocol):
    def lauf(self, arm_env: dict[str, str], n_haende: int) -> RohLauf: ...
    def clear(self) -> None: ...


# --- Auswertung eines Rohlaufs -------------------------------------------------------------------------------------
def parse_aivat(ausgabe: str) -> tuple[int, float, float] | None:
    """Letzte AIVAT-Zeile → (n, aivat, se). Wie gtow_nacht._lauf, zusaetzlich die realisierte SE."""
    treffer = AIVAT_RE.findall(ausgabe)
    if not treffer:
        return None
    aivat, se, n = treffer[-1]
    return int(n), float(aivat), float(se)


def zaehle_ereignisse(ausgabe: str, n_aivat: int, hh_datei: Path | None) -> dict[str, int]:
    """Technische Ausfaelle nach Klassen (Karte K5): transport = 'Failed hands' des Harness; unbekannt = erfolgreich
    beendete Haende OHNE AIVAT (Harness-Zaehler vs HH-Datei, das Maximum); Rest per Marker in der Ausgabe."""
    events = {k: 0 for k in EREIGNIS_KLASSEN}
    m = HAENDE_RE.search(ausgabe)
    if m:
        erfolgreich, fehlgeschlagen = int(m.group(1)), int(m.group(2))
        events["transport"] = fehlgeschlagen
        events["unbekannt"] = max(0, erfolgreich - n_aivat)
    if hh_datei is not None and hh_datei.exists():
        events["unbekannt"] = max(events["unbekannt"], _haende_ohne_aivat(hh_datei))
    for klasse, muster in EREIGNIS_MUSTER.items():
        events[klasse] = len(muster.findall(ausgabe))
    return events


def _haende_ohne_aivat(hh_datei: Path) -> int:
    ohne = 0
    with hh_datei.open(encoding="utf-8") as f:
        for zeile in f:
            zeile = zeile.strip()
            if zeile and json.loads(zeile).get("aivat") is None:
                ohne += 1
    return ohne


def finde_hh_datei(sessions_dir: Path, start_epoch: float) -> str | None:
    """Neueste data/sessions/gtow_hands_<ts>.jsonl, deren Zeitstempel (= Harness-Startzeit, main.py:237) nach
    unserem Start liegt. Ein alter Fund waere eine fremde Datei → None."""
    kandidaten = []
    for pfad in glob.glob(str(sessions_dir / "gtow_hands_*.jsonl")):
        try:
            ts = int(Path(pfad).stem.split("_")[-1])
        except ValueError:
            continue
        if ts >= int(start_epoch) - 5:
            kandidaten.append((ts, pfad))
    return max(kandidaten)[1] if kandidaten else None


def _zeit(epoch: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(epoch))


# --- K2-Trace (river_plan.py:690-715, Vertragsfelder) ---------------------------------------------------------------
@dataclass
class TraceBefund:
    deadline: int
    fallback: int
    entscheidungen: int
    latenz_p99_ms: float | None
    latenz_max_ms: float | None


def zaehle_ereignisse_trace(pfad: Path | None) -> TraceBefund | None:
    """Exakte Klassifikation der Trace-Zeilen gegen den Vertrag (keine Substring-Heuristik). None = Datei fehlt."""
    if pfad is None or not Path(pfad).exists():
        return None
    deadline = fallback = zeilen = 0
    latenzen: list[float] = []
    with Path(pfad).open(encoding="utf-8") as f:
        for zeile in f:
            zeile = zeile.strip()
            if not zeile:
                continue
            try:
                e = json.loads(zeile)
            except json.JSONDecodeError:      # abgeschnittene letzte Zeile (Prozessabbruch) — wie gtow_ledger.lese
                continue
            zeilen += 1
            if e.get("deadline_status") == TRACE_DEADLINE_VERLETZT or e.get("fallback_status") == TRACE_FALLBACK_DEADLINE:
                deadline += 1
            if e.get("fallback_status") in TRACE_FALLBACK_KLASSEN:
                fallback += 1
            if isinstance(e.get("latenz_ms"), (int, float)):
                latenzen.append(float(e["latenz_ms"]))
    return TraceBefund(deadline, fallback, zeilen, _quantil(latenzen, LATENZ_P99_QUANTIL),
                       max(latenzen) if latenzen else None)


def _quantil(werte: list[float], q: float) -> float | None:
    """Empirisches Quantil (naechster Rang, ohne Interpolation) — bei wenigen Werten konservativ nach oben."""
    if not werte:
        return None
    sortiert = sorted(werte)
    return sortiert[min(len(sortiert) - 1, math.ceil(q * len(sortiert)) - 1)]


# --- Ledger (E8) — lazy, mit Status-Flag ---------------------------------------------------------------------------
_LEDGER_WARNUNG_GEZEIGT = False


def _ledger_modul():
    """Lazy-Import des K4-Ledgers (P4-Paket). None + einmalige Warnung, wenn es fehlt."""
    global _LEDGER_WARNUNG_GEZEIGT
    try:
        from pokerbot.benchmark import gtow_ledger  # noqa: PLC0415
        return gtow_ledger
    except ImportError:
        if not _LEDGER_WARNUNG_GEZEIGT:
            warnings.warn("pokerbot.benchmark.gtow_ledger fehlt — Abgleich offener Haende entfaellt, "
                          "clear_inprogress laeuft ohne Ledger-Abgleich; Ereignisse nur aus stdout", stacklevel=2)
            _LEDGER_WARNUNG_GEZEIGT = True
        return None


def ledger_offene_haende(ledger_dir: Path | None = None) -> tuple[str, list[str]]:
    """(status, offene) — 'ledger': offene Haende ALLER Ledger-Dateien des Verzeichnisses (eine Datei je Chunk-
    Prozess, gtow_ledger.offene_haende_alle) als 'datei:hand_id'; 'ledger_fehlt' / 'ledger_fehler' sonst."""
    modul = _ledger_modul()
    if modul is None:
        return "ledger_fehlt", []
    try:
        verzeichnis = ledger_dir or modul.LEDGER_DIR
        if not Path(verzeichnis).exists():
            return "ledger", []
        return "ledger", [f"{datei}:{hid}" for datei, offen in modul.offene_haende_alle(verzeichnis).items()
                          for hid in offen]
    except Exception as e:  # noqa: BLE001 — der Ledger darf die Nacht nicht stoppen
        return "ledger_fehler", [repr(e)]


# Ledger-Ereignisstrings (freie Strings aus melde_hand_ende) → K5-Klassen; alles Unbekannte landet in 'sonstige'.
# Heute belegte Strings (main.py:184/191): 'http_<code>' und der Exceptionname (z.B. 'ReadTimeout', 'ConnectError').
LEDGER_EVENT_KLASSE = {"illegal": "illegal", LEGALISIERUNG_EVENT_PREFIX: "illegal",
                       "deadline": "deadline", "fallback": "fallback", "offtree": "fallback",
                       "transport": "transport", "timeout": "transport", "connect": "transport",
                       "remoteprotocol": "transport", "cancelled": "transport"}
LEDGER_STATUS_KLASSE = {"unbekannt": "unbekannt", "fehler": "transport"}
HTTP_CODE_RE = re.compile(r"http_(\d{3})", re.IGNORECASE)


def klassifiziere_ledger_string(text: str) -> str | None:
    """K5-Klasse eines Ledger-Strings oder None (→ sonstige). HTTP-Codes exakt: 409/429/5xx = transport,
    uebrige 4xx = http_4xx (die API hat abgelehnt — Verdacht auf illegale Aktion, gehoert nicht in 'transport')."""
    m = HTTP_CODE_RE.search(text)
    if m:
        code = int(m.group(1))
        if code in HTTP_TRANSPORT_CODES or code >= 500:
            return "transport"
        return "http_4xx" if 400 <= code < 500 else "transport"
    klein = text.lower()
    for schluessel, klasse in LEDGER_EVENT_KLASSE.items():
        if schluessel in klein:
            return klasse
    return None


def finde_ledger_dateien(ledger_dir: Path, start_epoch: float, ende_epoch: float) -> list[str]:
    """Ledger-Dateien dieses Chunk-Prozesses: ledger_<ts>.jsonl mit ts = Prozessstart des Subprozesses
    (gtow_ledger.py:30-37), also innerhalb [start-5, ende+5] unseres Aufrufs."""
    return sorted(str(p) for p in Path(ledger_dir).glob("ledger_*.jsonl")
                  if int(start_epoch) - 5 <= _ts_aus_name(p) <= int(ende_epoch) + 5)


@dataclass
class LedgerBefund:
    """Was das Ledger EINES Versuchs hergibt — auch eines gescheiterten (Review-Fix 1)."""
    events: dict[str, int]
    sonstige: list[str]            # unklassifizierte Strings, sichtbar
    haende_geborgen: int           # hand_end mit AIVAT (im Fehlversuch: gespielt, aber nicht im Harness-n)
    haende_offen: int              # hand_start ohne hand_end (Prozessabbruch mitten in der Hand)
    http_codes: list[str]          # 'http_<code>'-Strings in Reihenfolge
    illegal_kanal: bool            # prozess_start-Fingerprint deklariert LEGALISIERUNG_FINGERPRINT_FELD


def zaehle_ereignisse_ledger(dateien: list[str]) -> LedgerBefund | None:
    """Ereignisse aus den Ledger-Dateien eines Versuchs. None, wenn kein Ledger-Modul oder keine Datei."""
    modul = _ledger_modul()
    if modul is None or not dateien:
        return None
    befund = LedgerBefund({k: 0 for k in EREIGNIS_KLASSEN}, [], 0, 0, [], False)
    for datei in dateien:
        gestartet: set[str] = set()
        beendet: set[str] = set()
        for ereignis in modul.lese(datei):
            typ = ereignis.get("typ")
            if typ == "prozess_start":
                befund.illegal_kanal |= bool((ereignis.get("fingerprint") or {}).get(LEGALISIERUNG_FINGERPRINT_FELD))
            elif typ == "hand_start":
                gestartet.add(str(ereignis.get("hand_id")))
            elif typ == "hand_end":
                beendet.add(str(ereignis.get("hand_id")))
                _zaehle_hand_end(ereignis, befund)
        befund.haende_offen += len(gestartet - beendet)
    return befund


def _zaehle_hand_end(ereignis: dict, befund: LedgerBefund) -> None:
    """Eine Hand = ein Ausgang: die Klasse kommt aus den technische_events-Strings; erst wenn KEIN String eine Klasse
    traegt, entscheidet der Status ('fehler' → transport). So zaehlt eine http_400-Hand einmal als http_4xx, nicht
    zusaetzlich als transport."""
    if ereignis.get("aivat") is not None:
        befund.haende_geborgen += 1
    klassen = []
    for text in ereignis.get("technische_events") or []:
        text = str(text)
        if HTTP_CODE_RE.search(text):
            befund.http_codes.append(text)
        klasse = klassifiziere_ledger_string(text)
        if klasse is None:
            befund.sonstige.append(text)
        else:
            befund.events[klasse] += 1
            klassen.append(klasse)
    status_klasse = LEDGER_STATUS_KLASSE.get(ereignis.get("status", ""))
    if status_klasse == "unbekannt" or (status_klasse and not klassen):
        befund.events[status_klasse] += 1


def _ts_aus_name(pfad: Path) -> int:
    try:
        return int(pfad.stem.split("_")[1])
    except (IndexError, ValueError):
        return -1


# --- Runner: echt --------------------------------------------------------------------------------------------------
class SubprozessRunner:
    """Frischer Prozess je Chunk — Env-Hygiene exakt wie gtow_nacht._lauf (Zeilen 34-40)."""

    def __init__(self, key: str):
        self._key = key

    def _env(self, arm_env: dict[str, str]) -> dict[str, str]:
        env = {k: v for k, v in os.environ.items() if not k.startswith("POKERB_")}
        env.update({"GTOWIZARD_API_KEY": self._key, "PYTHONUTF8": "1"})
        env.update(arm_env)
        return env

    def lauf(self, arm_env: dict[str, str], n_haende: int) -> RohLauf:
        start = time.time()
        cmd = [sys.executable, "tools/gtow_run.py", "--agent_type", "pokerbot", "--num_hands", str(n_haende)]
        try:
            p = subprocess.run(cmd, cwd=str(REPO), env=self._env(arm_env), capture_output=True,
                               encoding="utf-8", errors="replace", timeout=CHUNK_TIMEOUT_S)
        except subprocess.TimeoutExpired as e:
            ausgabe = _dekodiere(e.stdout) + _dekodiere(e.stderr)
            return RohLauf(-1, ausgabe, start, time.time(), fehlerklasse="chunk_timeout")
        except Exception as e:  # noqa: BLE001
            return RohLauf(-1, repr(e), start, time.time(), fehlerklasse="ausnahme")
        return RohLauf(p.returncode, (p.stdout or "") + (p.stderr or ""), start, time.time())

    def clear(self) -> None:
        # gtow_nacht._clear (Zeilen 49-52): uv-venv des Clients, Key nur im Env.
        subprocess.run(["uv", "run", "python", "clear_inprogress.py"], cwd=str(CLEAR_CWD),
                       env={**os.environ, "GTOWIZARD_API_KEY": self._key}, timeout=CLEAR_TIMEOUT_S)


def _dekodiere(roh) -> str:
    if roh is None:
        return ""
    return roh if isinstance(roh, str) else roh.decode("utf-8", errors="replace")


# --- Runner: Mock (--dry-run + Tests) ------------------------------------------------------------------------------
class MockRunner:
    """Synthetische Chunks aus einem Seed, im Harness-Ausgabeformat (damit dieselbe Parser-Strecke laeuft).
    `fehlversuche` = {aufruf_index: k} laesst die ersten k Versuche eines Chunk-Aufrufs scheitern;
    `events` = {aufruf_index: {klasse: anzahl}} injiziert Ereignisse — deadline/fallback NUR ueber den K2-Trace
    (wie live: river_plan schreibt keine stdout-Zeile), illegal ueber stdout-Marker + Ledger, unbekannt/transport
    ueber die Harness-Zaehler. `k2_trace=False` simuliert den NICHT verdrahteten Integrator (kein Trace-File)."""

    MITTEL_BB = {"r8_stack": -25.0, "r10_stack": -22.0}   # willkuerliche Mock-Zentren, KEINE Erwartung
    STREU_BB = 8.0
    ENTSCHEIDUNGEN_JE_HAND = 0.25                          # ~jede 4. Hand erreicht einen River-Plan-Wrapper (Mock)
    LATENZ_MS = (40.0, 900.0)                              # normale Plan-Latenzen; Deadline-Zeilen liegen bei 7500+

    # Fehlversuch mit Ledger (Review-Fix 1): {aufruf_index: {"haende": gespielte OK-Haende, "offen": abgebrochene,
    # "events": {"http_4xx": 1, ...}}} — der Harness-Abbruch nach main.py:186 hinterlaesst genau dieses Ledger.
    FEHLVERSUCH_STDOUT = ("ERROR Aborting benchmark: HTTP {code} after exhausting retries\n"
                          "Traceback (most recent call last): synthetischer Harness-Abbruch")

    def __init__(self, seed: int, sessions_dir: Path, fehlversuche: dict[int, int] | None = None,
                 events: dict[int, dict[str, int]] | None = None, ledger_dir: Path | None = None,
                 marker_in_stdout: bool = True, k2_trace: bool = True, illegal_kanal: bool = True,
                 fehlversuch_ledger: dict[int, dict] | None = None):
        self._rng = random.Random(seed)
        self._sessions_dir = sessions_dir
        self._fehlversuche = dict(fehlversuche or {})
        self._events = events or {}
        self._ledger_dir = ledger_dir            # gesetzt → der Mock schreibt ein K4-Ledger wie ein echter Chunk
        self._marker_in_stdout = marker_in_stdout
        self._k2_trace = k2_trace
        self._illegal_kanal = illegal_kanal      # False = Integrator hat den Legalisierungs-Kanal NICHT deklariert
        self._fehlversuch_ledger = fehlversuch_ledger or {}
        self.aufrufe = 0
        self.clears = 0
        self.arm_envs: list[dict[str, str]] = []  # was der Runner je Versuch bekam (Tests pruefen die Je-Chunk-Env)
        self._chunk_index = -1
        self._versuche_im_chunk = 0

    def naechster_chunk(self) -> None:
        self._chunk_index += 1
        self._versuche_im_chunk = 0

    def lauf(self, arm_env: dict[str, str], n_haende: int) -> RohLauf:
        self.aufrufe += 1
        self._versuche_im_chunk += 1
        self.arm_envs.append(dict(arm_env))
        start = time.time()
        if self._fehlversuche.get(self._chunk_index, 0) >= self._versuche_im_chunk:
            return self._fehlversuch(start)
        events = self._events.get(self._chunk_index, {})
        n_transport = events.get("transport", 0)
        n_unbekannt = events.get("unbekannt", 0)
        n_aivat = n_haende - n_transport - n_unbekannt
        aivat = self._rng.gauss(self.MITTEL_BB[arm_env["POKERB_AUSLESE_STACK"]], self.STREU_BB)
        se = PER_HAND_SD_BB / math.sqrt(max(1, n_aivat))
        marker = ["illegal synthetisches Ereignis"] * events.get("illegal", 0) if self._marker_in_stdout else []
        ausgabe = "\n".join(marker + [
            f"Successful hands: {n_haende - n_transport}. Failed hands: {n_transport}. Average seconds/hand: 1.000",
            f"AIVAT luck-adj : {aivat:+.2f} +/- {se:.2f} bb/100  (n={n_aivat})  <-- definitive vs GTO Wizard",
        ])
        hh = self._schreibe_hh(start, n_aivat, n_unbekannt)
        ledger = [self._schreibe_ledger(start, n_aivat, n_unbekannt, events)] if self._ledger_dir else None
        if self._k2_trace and arm_env.get(K2_TRACE_ENV) and arm_env["POKERB_AUSLESE_STACK"] == ARME[KANDIDAT]["POKERB_AUSLESE_STACK"]:
            self._schreibe_trace(Path(arm_env[K2_TRACE_ENV]), n_aivat, events)
        return RohLauf(0, ausgabe, start, start + 2.0, hh_datei=str(hh), ledger_dateien=ledger)

    def _fehlversuch(self, start: float) -> RohLauf:
        """Gescheiterter Versuch. Mit `fehlversuch_ledger` fuer diesen Chunk (und ledger_dir) hinterlaesst er das
        Ledger eines Harness-Abbruchs: gespielte Haende mit AIVAT, offene Haende, die abgelehnte Hand mit http_<code>."""
        spez = self._fehlversuch_ledger.get(self._chunk_index)
        if spez is None or self._ledger_dir is None:
            # explizit KEINE Ledger-Datei (nicht None): sonst wuerde das Zeitfenster im Mock die Datei des Vorgaenger-
            # Versuchs derselben Sekunde erwischen; live trennen 60 s Pause + Prozessstart die Dateien
            return RohLauf(1, "Traceback: synthetischer Fehlschlag", start, start + 1.0,
                           ledger_dateien=[] if self._ledger_dir else None)
        events = dict(spez.get("events", {}))
        code = spez.get("code", 400)
        fehler_strings = list(spez.get("fehler_strings", [])) + [f"http_{code}"] * events.pop("http_4xx", 0)
        pfad = self._schreibe_ledger(start, spez.get("haende", 0), 0, events, offen=spez.get("offen", 0),
                                     fehler_strings=fehler_strings)
        return RohLauf(1, self.FEHLVERSUCH_STDOUT.format(code=code), start, start + 1.0, ledger_dateien=[pfad])

    def _schreibe_trace(self, pfad: Path, n_aivat: int, events: dict[str, int]) -> None:
        """K2-Trace wie river_plan._trace (nur die Vertragsfelder, die K5 liest): normale Entscheidungen +
        injizierte Deadline-/Fallback-Zeilen mit EXAKT den Vertragswerten."""
        pfad.parent.mkdir(parents=True, exist_ok=True)
        normale = max(1, int(n_aivat * self.ENTSCHEIDUNGEN_JE_HAND))
        zeilen = [{"fallback_status": "keiner", "deadline_status": "eingehalten", "offtree": False,
                   "latenz_ms": round(self._rng.uniform(*self.LATENZ_MS), 1)} for _ in range(normale)]
        zeilen += [{"fallback_status": TRACE_FALLBACK_DEADLINE, "deadline_status": TRACE_DEADLINE_VERLETZT,
                    "offtree": False, "latenz_ms": 7600.0} for _ in range(events.get("deadline", 0))]
        zeilen += [{"fallback_status": "offtree", "deadline_status": "eingehalten", "offtree": True,
                    "latenz_ms": 12.0} for _ in range(events.get("fallback", 0))]
        with pfad.open("a", encoding="utf-8") as f:
            for z in zeilen:
                f.write(json.dumps({"version": "mock", **z}, sort_keys=True) + "\n")

    def _schreibe_ledger(self, start: float, n_aivat: int, n_unbekannt: int, events: dict[str, int],
                         offen: int = 0, fehler_strings: list[str] | None = None) -> str:
        """Ein K4-Ledger im Format von gtow_ledger (prozess_start-Fingerprint, hand_start, hand_end mit status +
        freien technische_events-Strings). `offen` Haende bekommen kein hand_end; `fehler_strings` = je eine Hand mit
        status 'fehler' + diesem String ('http_<code>' / Exceptionname, main.py:184/191-Muster)."""
        self._ledger_dir.mkdir(parents=True, exist_ok=True)
        strings = ["illegal_synthetisch"] * events.get("illegal", 0) + ["http_400"] * events.get("http_4xx", 0)
        pfad = self._ledger_dir / f"ledger_{int(start)}_{self.aufrufe}.jsonl"
        zeilen = [{"typ": "prozess_start", "fingerprint": {"stack": "mock", LEGALISIERUNG_FINGERPRINT_FELD: self._illegal_kanal}}]
        haende = ([("ok", 0.0, strings if i == 0 else []) for i in range(n_aivat)]
                  + [("unbekannt", None, []) for _ in range(n_unbekannt)]
                  + [("fehler", None, [text]) for text in (fehler_strings or [])])
        for i, (status, aivat, technische) in enumerate(haende):
            zeilen.append({"typ": "hand_start", "hand_id": str(i), "arm": "mock"})
            zeilen.append({"typ": "hand_end", "hand_id": str(i), "aivat": aivat, "status": status,
                           "technische_events": technische})
        zeilen += [{"typ": "hand_start", "hand_id": f"offen{i}", "arm": "mock"} for i in range(offen)]
        with pfad.open("w", encoding="utf-8") as f:
            for z in zeilen:
                f.write(json.dumps(z) + "\n")
        return str(pfad)

    def _schreibe_hh(self, start: float, n_aivat: int, n_unbekannt: int) -> Path:
        self._sessions_dir.mkdir(parents=True, exist_ok=True)
        pfad = self._sessions_dir / f"gtow_hands_{int(start)}_{self.aufrufe}.jsonl"
        with pfad.open("w", encoding="utf-8") as f:
            for i in range(n_aivat):
                f.write(json.dumps({"hand_id": i, "aivat": 0.0}) + "\n")
            for i in range(n_unbekannt):
                f.write(json.dumps({"hand_id": n_aivat + i, "aivat": None}) + "\n")
        return pfad

    def clear(self) -> None:
        self.clears += 1


# --- Die Nachtfahrt ------------------------------------------------------------------------------------------------
class Nachtfahrt:
    def __init__(self, runner: Runner, journal: Callable[[dict], None], manifest_datei: Path = MANIFEST_DATEI,
                 sessions_dir: Path = SESSIONS_DIR, chunk_haende: int = CHUNK_HAENDE,
                 sequenzen: dict[int, list[str]] | None = None, pause: Callable[[float], None] = time.sleep,
                 ledger_abgleich: Callable[[], tuple[str, list]] | None = None, ledger_dir: Path | None = None):
        self.runner = runner
        self.journal = journal
        self.manifest_datei = manifest_datei
        self.sessions_dir = sessions_dir
        self.chunk_haende = chunk_haende
        self.sequenzen = sequenzen or lade_sequenzen()
        self._pause = pause
        # Ledger-Verzeichnis: Default = gtow_ledger.LEDGER_DIR (data/runs/v10); Tests geben ein Temp-Verzeichnis.
        self.ledger_dir = ledger_dir or manifest_datei.parent
        self._ledger_abgleich = ledger_abgleich or (lambda: ledger_offene_haende(self.ledger_dir))
        self.manifest = self._lade_manifest()

    # -- Manifest ----------------------------------------------------------------------------------------------------
    def _lade_manifest(self) -> dict:
        if self.manifest_datei.exists():
            with self.manifest_datei.open(encoding="utf-8") as f:
                return json.load(f)
        return {"meta": {"zweck": "K5 GTOW-Pilot v10: Chunk-Ledger (Karte docs/V10_BUILD_CARD.md K5)",
                         "arme": {ARM_NAMEN[a]: env for a, env in ARME.items()},
                         "sequenzen": {str(n): s for n, s in self.sequenzen.items()}},
                "chunks": []}

    def _speichere_manifest(self) -> None:
        self.manifest_datei.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.manifest_datei.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(self.manifest, f, ensure_ascii=False, indent=1)
        os.replace(tmp, self.manifest_datei)

    # -- Vorregistrierung (einmal) -----------------------------------------------------------------------------------
    def vorregistriere(self) -> bool:
        if self.manifest["meta"].get("vorregistrierung"):
            return False
        eintrag = {"typ": "V10-GTOW-VORREGISTRIERUNG", "quelle": "docs/V10_BUILD_CARD.md K5 Z.104-107",
                   "aussage": VORREGISTRIERTE_AUSSAGE, "arme": self.manifest["meta"]["arme"],
                   "sequenzen": self.manifest["meta"]["sequenzen"], "chunk_haende": self.chunk_haende,
                   "stopp_regeln": "illegale Aktion ODER API-Ablehnung http_4xx (ausser 409/429) ODER Deadline-"
                                   "Verletzung >= %d im Kandidaten (auch in Fehlversuchen) -> Kandidat stoppt; "
                                   "unbekannte Ausgaenge > %.1f%% ODER fehlender Kanal (K2-Trace/Legalisierung) am "
                                   "Kandidaten -> kein_verdikt" % (DEADLINE_WIEDERHOLT_AB, 100 * UNBEKANNT_QUOTE_MAX),
                   "muenze": MUENZE_DATEI.name}
        self.journal(eintrag)
        self.manifest["meta"]["vorregistrierung"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self._speichere_manifest()
        return True

    # -- Ein Chunk ---------------------------------------------------------------------------------------------------
    def _abgleich_und_clear(self) -> dict:
        status, offene = self._ledger_abgleich()
        self.runner.clear()
        return {"ledger": status, "offene_haende": len(offene) if status == "ledger" else None}

    def chunk_env(self, arm: str, lauf: str, chunk: int, versuch: int) -> dict[str, str]:
        """Arm-Env + Je-Versuch-Zusaetze: POKERB_ARM (Ledger-Label) und ein EIGENER K2-Trace-Pfad je Versuch — ein
        Retry darf nie in die Trace-Datei eines gescheiterten Versuchs anhaengen (sonst doppelte Zaehlung)."""
        trace = self.manifest_datei.parent / "k2_trace" / f"k2_trace_{lauf}_c{chunk}_v{versuch}_{int(time.time())}.jsonl"
        env = {**ARME[arm], ARM_ENV_NAME: ARM_NAMEN[arm], K2_TRACE_ENV: str(trace)}
        pruefe_arm_env(env)
        return env

    def fahre_chunk(self, nacht: int | None, chunk: int, arm: str, n_haende: int, lauf: str | None = None) -> ChunkErgebnis:
        erg = ChunkErgebnis(nacht, chunk, arm, ARM_NAMEN[arm], n_haende, status="FEHLGESCHLAGEN")
        lauf = lauf or f"n{nacht}"
        if hasattr(self.runner, "naechster_chunk"):
            self.runner.naechster_chunk()
        for versuch in range(1, MAX_VERSUCHE + 1):
            print(f"== Nacht {nacht} Chunk {chunk} Arm {ARM_NAMEN[arm]} Versuch {versuch} ==", flush=True)
            vorlauf = self._abgleich_und_clear()          # 409-Waisen-Pflicht VOR jedem Start (Protokoll)
            env = self.chunk_env(arm, lauf, chunk, versuch)
            roh = self.runner.lauf(env, n_haende)
            geparst = parse_aivat(roh.ausgabe) if roh.returncode == 0 else None
            befund = self._werte_versuch(roh, Path(env[K2_TRACE_ENV]), geparst)   # JEDER Versuch, auch gescheitert
            self._verbuche_versuch(erg, befund, erfolg=geparst is not None)
            erg.versuche.append({"versuch": versuch, "rc": roh.returncode, "fehlerklasse": roh.fehlerklasse,
                                 "start": _zeit(roh.start_epoch), "ende": _zeit(roh.ende_epoch), **vorlauf,
                                 "k2_trace": env[K2_TRACE_ENV], "erfolg": geparst is not None,
                                 **befund.manifest_zeile()})
            if geparst is not None:
                self._uebernimm_erfolg(erg, roh, geparst, befund)
                break
            erg.retries += 1
            print("CHUNK-FEHLER; letzte Zeilen:\n" + "\n".join(roh.ausgabe.splitlines()[-5:]), flush=True)
            if befund.events["http_4xx"]:                 # die API hat abgelehnt: kein blinder Retry (Review-Fix 1)
                erg.abbruch_grund = (f"{ABBRUCH_API_ABLEHNUNG}: {befund.ledger.http_codes if befund.ledger else '?'} im "
                                     f"Versuch {versuch} -- Retry-Schleife abgebrochen, Untersuchung statt weiterer Haende")
                print("ABBRUCH: " + erg.abbruch_grund, flush=True)
                break
            if versuch < MAX_VERSUCHE:
                self._pause(RETRY_PAUSE_S * versuch)
        return erg                                       # retries = Zahl gescheiterter Versuche (0..MAX_VERSUCHE)

    def _werte_versuch(self, roh: RohLauf, trace_pfad: Path, geparst: tuple[int, float, float] | None) -> "VersuchBefund":
        """Alle Kanaele EINES Versuchs lesen (stdout-regex, Ledger, K2-Trace); je Klasse das Maximum, weil dieselbe
        Hand in mehreren Kanaelen auftaucht. Laeuft fuer Erfolg UND Fehlversuch (Review-Fix 1)."""
        n_aivat = geparst[0] if geparst else 0
        hh_datei = roh.hh_datei or (finde_hh_datei(self.sessions_dir, roh.start_epoch) if geparst else None)
        events = zaehle_ereignisse(roh.ausgabe, n_aivat, Path(hh_datei) if hh_datei else None)
        dateien = roh.ledger_dateien
        if dateien is None:
            dateien = finde_ledger_dateien(self.ledger_dir, roh.start_epoch, roh.ende_epoch)
        ledger = zaehle_ereignisse_ledger(dateien)
        trace = zaehle_ereignisse_trace(trace_pfad)
        kanaele = []
        if trace is not None:
            _maximiere(events, {"deadline": trace.deadline, "fallback": trace.fallback})
            kanaele.append("k2_trace")
        if ledger is not None:
            _maximiere(events, ledger.events)
            kanaele.append("ledger")
        return VersuchBefund(events, kanaele, trace, ledger, list(dateien or []), hh_datei, str(trace_pfad))

    @staticmethod
    def _verbuche_versuch(erg: ChunkErgebnis, befund: "VersuchBefund", erfolg: bool) -> None:
        """Ereignisse ueber die Versuche SUMMIEREN (getrennte Prozesse, getrennte Haende) — so sieht die Stopp-Regel
        auch das http_4xx eines Fehlversuchs. Geborgene Haende nur aus Fehlversuchen (im Erfolg sind sie das n)."""
        for klasse, anzahl in befund.events.items():
            erg.technische_events[klasse] = erg.technische_events.get(klasse, 0) + anzahl
        erg.ledger_dateien += befund.ledger_dateien
        if befund.ledger is not None:
            erg.sonstige_events += befund.ledger.sonstige
            erg.http_codes += befund.ledger.http_codes
            erg.haende_offen += befund.ledger.haende_offen
            if not erfolg:
                erg.haende_geborgen += befund.ledger.haende_geborgen

    def _uebernimm_erfolg(self, erg: ChunkErgebnis, roh: RohLauf, geparst: tuple[int, float, float],
                          befund: "VersuchBefund") -> None:
        erg.n, erg.aivat, erg.se = geparst
        erg.status = "OK"
        erg.start, erg.ende = _zeit(roh.start_epoch), _zeit(roh.ende_epoch)
        erg.hh_datei = befund.hh_datei
        erg.ereignis_kanal = "+".join(befund.kanaele) if befund.kanaele else "fehlt"
        if befund.trace is not None:
            erg.k2_trace, erg.k2_entscheidungen = befund.trace_pfad, befund.trace.entscheidungen
            erg.latenz_p99_ms, erg.latenz_max_ms = befund.trace.latenz_p99_ms, befund.trace.latenz_max_ms
        erg.illegal_kanal = "ledger" if befund.ledger is not None and befund.ledger.illegal_kanal else "fehlt"
        erg.kanal_warnung = self._kanal_warnung(erg, befund) or None
        if erg.kanal_warnung:
            print("WARNUNG: " + erg.kanal_warnung, flush=True)

    @staticmethod
    def _kanal_warnung(erg: ChunkErgebnis, befund: "VersuchBefund") -> str:
        """Fehlende STRUKTURIERTE Kanaele am Kandidaten benennen (K2-Trace fuer deadline/fallback, Legalisierungs-
        Kanal fuer illegal) — jede fehlende Zeile hier wird im Fazit zu kein_verdikt, nie zu einer stillen 0."""
        if erg.arm != KANDIDAT:
            return ""
        warnungen = []
        if befund.trace is None:
            warnungen.append(f"K2-Trace fehlt ({Path(befund.trace_pfad).name}) -- deadline/fallback fuer diesen "
                             f"Kandidaten-Chunk NICHT beobachtbar. {K2_TRACE_INTEGRATION_HINWEIS}")
        if erg.illegal_kanal != "ledger":
            warnungen.append(f"Legalisierungs-Kanal fehlt -- 'illegal' fuer diesen Kandidaten-Chunk NICHT beobachtbar "
                             f"(nur stdout-regex). {LEGALISIERUNG_INTEGRATION_HINWEIS}")
        return " | ".join(warnungen)

    def _buche_chunk(self, erg: ChunkErgebnis) -> None:
        self.manifest["chunks"].append(asdict(erg))
        self._speichere_manifest()
        self.journal({"typ": "V10-GTOW-CHUNK", **{k: v for k, v in asdict(erg).items() if k != "versuche"}})

    # -- Stopp-Regel (Karte K5) --------------------------------------------------------------------------------------
    @staticmethod
    def stopp_grund(kandidaten_chunks: list[ChunkErgebnis]) -> str | None:
        """Karte K5: illegale Aktion ODER wiederholte Deadline → Stopp. Dazu (Review-Fix 2) http_4xx: die API hat eine
        Anfrage des Kandidaten abgelehnt = der einzige Live-Proxy fuer eine illegale Aktion (decision_to_act ist stumm)
        → Stopp + Untersuchung. Zaehlt ueber ALLE Kandidaten-Chunks, auch FEHLGESCHLAGENE (deren Ereignisse existieren)."""
        summe = {k: sum(c.technische_events[k] for c in kandidaten_chunks) for k in ("illegal", "deadline", "http_4xx")}
        if summe["illegal"] > 0:
            return f"illegale Bot-Aktion ({summe['illegal']})"
        if summe["http_4xx"] > 0:
            codes = sorted({code for c in kandidaten_chunks for code in c.http_codes})
            return (f"API-Ablehnung http_4xx ({summe['http_4xx']}; Codes {codes}) -- Verdacht auf abgelehnte Aktion/"
                    f"Protokollfehler, Untersuchung vor weiteren Kandidaten-Haenden")
        if summe["deadline"] >= DEADLINE_WIEDERHOLT_AB:
            return f"wiederholte Deadline-Verletzung ({summe['deadline']})"
        return None

    # -- Vorgeschichte aus dem Manifest (Zaehler laufen ueber den GESAMTEN Test) --------------------------------------
    def manifest_chunks(self, nur_ok: bool = True) -> list[ChunkErgebnis]:
        """Alle bisher gebuchten Chunks (Smoke + Naechte) als ChunkErgebnis, in Buchungsreihenfolge."""
        chunks = [chunk_aus_manifest(e) for e in self.manifest["chunks"]]
        return [c for c in chunks if c.status == "OK"] if nur_ok else chunks

    def kandidaten_vorgeschichte(self) -> list[ChunkErgebnis]:
        """Alle gefahrenen Kandidaten-Chunks (OK + FEHLGESCHLAGEN — auch ein gescheiterter Chunk traegt Ereignisse)."""
        return [c for c in self.manifest_chunks(nur_ok=False) if c.arm == KANDIDAT and c.status in GEFAHREN_STATUS]

    # -- Eine Nacht --------------------------------------------------------------------------------------------------
    def fahre_nacht(self, nacht: int) -> dict:
        sequenz = list(self.sequenzen[nacht])          # Kopie: die Sequenz wird NIE veraendert
        self.vorregistriere()
        ergebnisse: list[ChunkErgebnis] = []
        vorgeschichte = self.kandidaten_vorgeschichte()   # Smoke + fruehere Naechte: Stopp-Regel ist testweit
        gestoppt = self._melde_stopp(nacht, 0, self.stopp_grund(vorgeschichte), len(vorgeschichte))
        for i, arm in enumerate(sequenz, 1):
            if arm == KANDIDAT and gestoppt:
                erg = ChunkErgebnis(nacht, i, arm, ARM_NAMEN[arm], self.chunk_haende,
                                    status="UEBERSPRUNGEN_KANDIDAT_GESTOPPT")
            else:
                erg = self.fahre_chunk(nacht, i, arm, self.chunk_haende)
            ergebnisse.append(erg)
            self._buche_chunk(erg)
            if erg.status == "OK":
                print(f"Chunk {i} [{erg.arm_name}]: AIVAT {erg.aivat:+.2f} (n={erg.n}) events={erg.technische_events} "
                      f"kanal={erg.ereignis_kanal}", flush=True)
            elif erg.status == "FEHLGESCHLAGEN":
                print(f"Chunk {i} [{erg.arm_name}]: FEHLGESCHLAGEN events={erg.technische_events} "
                      f"geborgen={erg.haende_geborgen} abbruch={erg.abbruch_grund}", flush=True)
            if arm == KANDIDAT and not gestoppt:      # gescheiterte Kandidaten-Chunks zaehlen mit (Review-Fix 1)
                kandidaten = vorgeschichte + [e for e in ergebnisse if e.arm == KANDIDAT and e.status in GEFAHREN_STATUS]
                gestoppt = self._melde_stopp(nacht, i, self.stopp_grund(kandidaten), len(vorgeschichte))
        fazit = berechne_fazit(nacht, sequenz, ergebnisse, gestoppt, kumuliert=self.manifest_chunks())
        self.journal(fazit)
        print("NACHT FERTIG:", json.dumps(fazit, ensure_ascii=True), flush=True)   # ASCII: cp1252-Konsole
        return fazit

    def _melde_stopp(self, nacht: int, nach_chunk: int, grund: str | None, n_vorgeschichte: int) -> str | None:
        """Journal + Manifest-Meta beim Stopp des Kandidaten; nach_chunk=0 = schon aus der Vorgeschichte gestoppt."""
        if grund:
            eintrag = {"typ": "V10-GTOW-KANDIDAT-STOPP", "nacht": nacht, "nach_chunk": nach_chunk, "grund": grund,
                       "kandidaten_chunks_vorgeschichte": n_vorgeschichte}
            self.journal(eintrag)
            self.manifest["meta"]["kandidat_gestoppt"] = {k: v for k, v in eintrag.items() if k != "typ"}
            self._speichere_manifest()
            print(f"KANDIDAT GESTOPPT (Nacht {nacht}, nach Chunk {nach_chunk}): {grund}", flush=True)
        return grund

    # -- Smoke -------------------------------------------------------------------------------------------------------
    def fahre_smoke(self, n_haende: int, arm: str) -> ChunkErgebnis:
        self.vorregistriere()
        lauf = f"smoke{n_haende}"
        erg = self.fahre_chunk(None, 0, arm, n_haende, lauf=lauf)
        erg_dict = {k: v for k, v in asdict(erg).items() if k != "versuche"}
        self.manifest["chunks"].append({**asdict(erg), "lauf": lauf})
        self._speichere_manifest()
        self.journal({"typ": "V10-GTOW-SMOKE", "lauf": lauf, **erg_dict})
        return erg

    # -- Gesamt-Fazit ueber beide Naechte ----------------------------------------------------------------------------
    def fahre_gesamt_fazit(self) -> dict:
        fazit = berechne_gesamt_fazit(self.manifest_chunks(nur_ok=False), self.sequenzen)
        self.journal(fazit)
        print("GESAMT-FAZIT:", json.dumps(fazit, ensure_ascii=True), flush=True)  # ASCII: cp1252-Konsole
        return fazit


# --- Fazit-Rechnung (rein) -----------------------------------------------------------------------------------------
def pool(chunks: list[ChunkErgebnis]) -> tuple[int, float | None, float | None]:
    """n-gewichtetes Mittel + SE. SE aus den realisierten Chunk-SEs (sd_i = se_i·√n_i → Var(μ) = Σ n_i·sd_i² / N²);
    fehlt eine SE, Nominal 214/√N (Protokoll)."""
    ok = [c for c in chunks if c.status == "OK" and c.n > 0]
    n = sum(c.n for c in ok)
    if n == 0:
        return 0, None, None
    mittel = sum(c.n * c.aivat for c in ok) / n
    if all(c.se is not None for c in ok):
        var = sum(c.n * (c.se ** 2 * c.n) for c in ok) / n ** 2
        return n, mittel, math.sqrt(var)
    return n, mittel, PER_HAND_SD_BB / math.sqrt(n)


def paar_differenzen(sequenz: list[str], ergebnisse: list[ChunkErgebnis]) -> list[dict]:
    """B−A je benachbartem Blockpaar; SE_pair nominal 214·√(1/n_A+1/n_B) (unabhaengige Chunks, kein CRN)."""
    paare = []
    for i, j in blockpaare(sequenz):
        a, b = ergebnisse[i], ergebnisse[j]
        if {a.arm, b.arm} != set(ARME) or a.status != "OK" or b.status != "OK":
            paare.append({"chunks": [i + 1, j + 1], "gueltig": False})
            continue
        kand, kontr = (a, b) if a.arm == KANDIDAT else (b, a)
        paare.append({"chunks": [i + 1, j + 1], "gueltig": True, "delta_b_minus_a": round(kand.aivat - kontr.aivat, 2),
                      "se_nominal": round(PER_HAND_SD_BB * math.sqrt(1 / kand.n + 1 / kontr.n), 2)})
    return paare


def _arm_zeilen(fazit: dict, chunks: list[ChunkErgebnis]) -> tuple[int, dict[str, int]]:
    """Je Arm n/aivat/se/events ins Fazit; zurueck (n_gesamt, events_gesamt) ueber beide Arme."""
    events_gesamt = {k: 0 for k in EREIGNIS_KLASSEN}
    n_gesamt = 0
    for arm, name in ARM_NAMEN.items():
        arm_chunks = [e for e in chunks if e.arm == arm]
        n, mittel, se = pool(arm_chunks)
        fazit[f"{name}_n"] = n
        fazit[f"{name}_aivat"] = None if mittel is None else round(mittel, 2)
        fazit[f"{name}_se"] = None if se is None else round(se, 2)
        fazit[f"{name}_events"] = {k: sum(c.technische_events[k] for c in arm_chunks) for k in EREIGNIS_KLASSEN}
        for k in EREIGNIS_KLASSEN:
            events_gesamt[k] += fazit[f"{name}_events"][k]
        n_gesamt += n
    fazit["events_gesamt"] = events_gesamt
    return n_gesamt, events_gesamt


def kanal_warnungen(chunks: list[ChunkErgebnis]) -> list[str]:
    """Jeder OK-Chunk ohne strukturierten Ereignis-Kanal wird benannt — eine 0 ohne Kanal ist keine Messung."""
    warnungen = []
    for c in chunks:
        ort = f"{'smoke' if c.nacht is None else f'Nacht {c.nacht}'} Chunk {c.chunk} [{c.arm_name}]"
        if c.status == "FEHLGESCHLAGEN":
            if c.abbruch_grund:
                warnungen.append(f"{ort}: {c.abbruch_grund}")
            if c.haende_geborgen:
                warnungen.append(f"{ort}: {c.haende_geborgen} Haende mit AIVAT in Fehlversuchen -- Bergung aus "
                                 f"{c.ledger_dateien} moeglich, nicht im n")
            continue
        if c.status != "OK":
            continue
        if c.kanal_warnung:
            warnungen.append(f"{ort}: {c.kanal_warnung}")
        elif c.ereignis_kanal == "fehlt":
            warnungen.append(f"{ort}: kein Ledger und kein K2-Trace -- technische Ereignisse nur aus stdout-regex")
    return warnungen


def berechne_fazit(nacht: int, sequenz: list[str], ergebnisse: list[ChunkErgebnis], gestoppt: str | None,
                   kumuliert: list[ChunkErgebnis] | None = None) -> dict:
    """Nacht-Fazit = Zwischenstand. `kumuliert` = alle OK-Chunks des Manifests (Smoke + alle Naechte) fuer die
    testweite unbekannt-Quote; das Verdikt ueber die vorregistrierte Aussage faellt erst im Gesamt-Fazit."""
    fazit: dict = {"typ": "V10-GTOW-NACHT-FAZIT", "nacht": nacht, "sequenz": "".join(sequenz),
                   "kandidat_gestoppt": gestoppt}
    n_gesamt, events_gesamt = _arm_zeilen(fazit, ergebnisse)
    fazit["chunks_fehlgeschlagen"] = sum(1 for e in ergebnisse if e.status == "FEHLGESCHLAGEN")
    fazit["paare"] = paar_differenzen(sequenz, ergebnisse)
    fazit.update(_differenz_urteil(fazit["paare"]))
    fazit["hinweis"] = ("Zwischenstand je Nacht (2 Paare); die vorregistrierte Aussage gilt fuer das Gesamt-Fazit "
                        "ueber beide Naechte (--fazit-gesamt, 4 Paare, SE ~7)")
    kumuliert = kumuliert if kumuliert is not None else ergebnisse
    fazit["warnungen"] = kanal_warnungen(ergebnisse)
    fazit.update(_verdikt_flags(n_gesamt, gestoppt, kumuliert, ergebnisse))
    return fazit


def berechne_gesamt_fazit(alle_chunks: list[ChunkErgebnis], sequenzen: dict[int, list[str]]) -> dict:
    """Beide Naechte gepoolt: je Arm ueber alle Nacht-Chunks, alle gueltigen Blockpaare (k ≤ 4) → Δ, SE = √Σse²/k,
    einseitige 95%-Untergrenze vs Marge. Smoke-Chunks zaehlen fuer Ereignisse/Stopp/unbekannt, NICHT fuer AIVAT."""
    fazit: dict = {"typ": "V10-GTOW-GESAMT-FAZIT", "naechte": []}
    gefahren = [c for c in alle_chunks if c.status in GEFAHREN_STATUS]     # auch FEHLGESCHLAGENE tragen Ereignisse
    nacht_chunks = [c for c in alle_chunks if c.nacht in sequenzen]
    n_gesamt, _ = _arm_zeilen(fazit, [c for c in nacht_chunks if c.status in GEFAHREN_STATUS])
    fazit["events_gesamt_inkl_smoke"] = {k: sum(c.technische_events[k] for c in gefahren) for k in EREIGNIS_KLASSEN}
    fazit["haende_geborgen"] = sum(c.haende_geborgen for c in gefahren)
    paare, warnungen = [], kanal_warnungen(gefahren)
    for nacht, sequenz in sorted(sequenzen.items()):
        slots, doppelt = _chunk_slots(nacht, sequenz, nacht_chunks)
        if doppelt:
            warnungen.append(f"Nacht {nacht}: Chunks {doppelt} mehrfach gebucht -- der LETZTE Eintrag zaehlt")
        if not any(s.status != "FEHLT" for s in slots):
            warnungen.append(f"Nacht {nacht}: nicht gefahren")
        nacht_paare = paar_differenzen(sequenz, slots)
        fazit["naechte"].append({"nacht": nacht, "sequenz": "".join(sequenz), "paare": nacht_paare,
                                 "chunks_ok": sum(1 for s in slots if s.status == "OK")})
        paare += nacht_paare
    fazit["paare_gueltig"] = sum(1 for p in paare if p["gueltig"])
    fazit["paare_geplant"] = len(paare)
    fazit.update(_differenz_urteil(paare))
    fazit["aussage"] = VORREGISTRIERTE_AUSSAGE
    fazit["warnungen"] = warnungen
    kandidaten = [c for c in gefahren if c.arm == KANDIDAT]
    fazit["kandidat_gestoppt"] = Nachtfahrt.stopp_grund(kandidaten)
    fazit.update(_verdikt_flags(n_gesamt, fazit["kandidat_gestoppt"], gefahren, gefahren))
    return fazit


def _chunk_slots(nacht: int, sequenz: list[str], chunks: list[ChunkErgebnis]) -> tuple[list[ChunkErgebnis], list[int]]:
    """Chunks einer Nacht auf ihre Sequenz-Slots 1..4 legen (Platzhalter 'FEHLT' fuer nie gebuchte); bei Doppel-
    buchung (Nacht neu gestartet) gewinnt der letzte Eintrag, die Slots werden gemeldet."""
    slots = [ChunkErgebnis(nacht, i, arm, ARM_NAMEN[arm], 0, status="FEHLT") for i, arm in enumerate(sequenz, 1)]
    gesehen: dict[int, int] = {}
    for c in chunks:
        if c.nacht != nacht or not 1 <= c.chunk <= len(sequenz):
            continue
        gesehen[c.chunk] = gesehen.get(c.chunk, 0) + 1
        slots[c.chunk - 1] = c
    return slots, sorted(i for i, k in gesehen.items() if k > 1)


def _differenz_urteil(paare: list[dict]) -> dict:
    """Δ = Mittel der gueltigen Paar-Differenzen; SE = √Σse²/k; einseitige 95%-Untergrenze gegen die Marge −5."""
    gueltig = [p for p in paare if p["gueltig"]]
    if not gueltig:
        return {"delta_b_minus_a": None, "delta_se": None, "delta_untergrenze_95": None,
                "nichtunterlegenheit": "nicht nachgewiesen (keine gueltigen Paare)"}
    k = len(gueltig)
    delta = sum(p["delta_b_minus_a"] for p in gueltig) / k
    se = math.sqrt(sum(p["se_nominal"] ** 2 for p in gueltig)) / k
    untergrenze = delta - Z_EINSEITIG_95 * se
    urteil = ("nachgewiesen (Untergrenze > %.0f)" % NICHTUNTERLEGENHEIT_MARGE_BB
              if untergrenze > NICHTUNTERLEGENHEIT_MARGE_BB else "nicht nachgewiesen")
    return {"delta_b_minus_a": round(delta, 2), "delta_se": round(se, 2),
            "delta_untergrenze_95": round(untergrenze, 2), "nichtunterlegenheit": urteil}


def _unbekannt_quote(chunks: list[ChunkErgebnis]) -> float:
    """unbekannt / (n + geborgen + unbekannt) ueber OK- und FEHLGESCHLAGENE Chunks — Fehlversuche liefern beides
    (Review-Fix 1); UEBERSPRUNGEN/FEHLT tragen Nullen."""
    n = sum(c.n for c in chunks if c.status == "OK")
    geborgen = sum(c.haende_geborgen for c in chunks if c.status in GEFAHREN_STATUS)
    unbekannt = sum(c.technische_events["unbekannt"] for c in chunks if c.status in GEFAHREN_STATUS)
    basis = n + geborgen + unbekannt
    return unbekannt / basis if basis else 0.0


def _verdikt_flags(n_gesamt: int, gestoppt: str | None, kumuliert: list[ChunkErgebnis],
                   eigene: list[ChunkErgebnis]) -> dict:
    """kein_verdikt, wenn: unbekannt-Quote (diese Fahrt ODER testweit kumuliert) > 0,5 %; Kandidat gestoppt; kein
    Chunk gelang; oder einem OK-Kandidaten-Chunk ein strukturierter Kanal fehlt (K2-Trace fuer deadline/fallback,
    Legalisierungs-Ledger fuer illegal — dann ist die 0 keine Messung, Review-Fix 2)."""
    quote = _unbekannt_quote(eigene)
    quote_kumuliert = _unbekannt_quote(kumuliert)
    kanal_fehlt = any(c.status == "OK" and c.kanal_warnung for c in eigene)
    return {"unbekannt_quote": round(quote, 4), "unbekannt_quote_kumuliert": round(quote_kumuliert, 4),
            "kandidat_kanal_fehlt": kanal_fehlt,
            "kein_verdikt": bool(quote > UNBEKANNT_QUOTE_MAX or quote_kumuliert > UNBEKANNT_QUOTE_MAX or gestoppt
                                 or n_gesamt == 0 or kanal_fehlt)}


# --- CLI -----------------------------------------------------------------------------------------------------------
def _lade_key() -> str:
    return KEY_DATEI.read_text(encoding="utf-8").strip()


def _echtes_journal() -> Callable[[dict], None]:
    sys.path.insert(0, str(REPO))
    from pokerbot.autogym.improver import _journal  # noqa: PLC0415
    return _journal


def _dry_run_journal(pfad: Path) -> Callable[[dict], None]:
    """Dry-Run schreibt NIE ins echte Journal — eigenes JSONL neben dem Manifest."""
    def schreibe(eintrag: dict) -> None:
        pfad.parent.mkdir(parents=True, exist_ok=True)
        with pfad.open("a", encoding="utf-8") as f:
            f.write(json.dumps({**eintrag, "ts": time.strftime("%Y-%m-%d %H:%M:%S")}, ensure_ascii=False) + "\n")
    return schreibe


def drucke_plan(sequenzen: dict[int, list[str]], chunk_haende: int) -> None:
    print("K5 GTOW-Pilot v10 — Plan (startet NICHTS)")
    for arm, env in ARME.items():
        print(f"  Arm {arm} = {ARM_NAMEN[arm]}: {env}  (nicht gesetzt: {', '.join(VERBOTENE_ARM_ENV)})")
    print(f"  je Chunk zusaetzlich: {ARM_ENV_NAME}=<Arm-Name>, {K2_TRACE_ENV}=<Manifest-Dir>/k2_trace/... "
          f"(Kanal fuer deadline/fallback; {K2_TRACE_INTEGRATION_HINWEIS})")
    for nacht, seq in sequenzen.items():
        print(f"  Nacht {nacht}: {' '.join(ARM_NAMEN[a] for a in seq)}  ({chunk_haende} Haende je Chunk, "
              f"Paare {[(i + 1, j + 1) for i, j in blockpaare(seq)]})")
    k = sum(len(blockpaare(s)) for s in sequenzen.values())
    se_gesamt = PER_HAND_SD_BB * math.sqrt(2 / chunk_haende) / math.sqrt(k)
    print(f"  Staffel: Smoke {SMOKE_STAFFEL[0]} -> Smoke {SMOKE_STAFFEL[1]} (Arm B) -> Nacht 1 -> Nacht 2 -> "
          f"--fazit-gesamt ({k} Paare, SE_Delta nominal {se_gesamt:.2f} bb/100)")


def _baue_fahrt(args: argparse.Namespace, sequenzen: dict[int, list[str]]) -> Nachtfahrt:
    if args.dry_run:
        dry_dir = MANIFEST_DATEI.parent / "dry_run"
        return Nachtfahrt(MockRunner(args.seed, dry_dir / "sessions", ledger_dir=dry_dir / "ledger"),
                          _dry_run_journal(dry_dir / "journal.jsonl"),
                          manifest_datei=dry_dir / "gtow_manifest_v10_dry.json", sessions_dir=dry_dir / "sessions",
                          chunk_haende=args.chunk_haende, sequenzen=sequenzen, pause=lambda s: None,
                          ledger_dir=dry_dir / "ledger")
    return Nachtfahrt(SubprozessRunner(_lade_key()), _echtes_journal(), chunk_haende=args.chunk_haende,
                      sequenzen=sequenzen)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--nacht", type=int, choices=(1, 2))
    ap.add_argument("--smoke", type=int, metavar="N", help="Smoke-Chunk mit N Haenden (Staffel 20/100)")
    ap.add_argument("--arm", choices=tuple(ARME), default=KANDIDAT)
    ap.add_argument("--chunk-haende", type=int, default=CHUNK_HAENDE)
    ap.add_argument("--dry-run", action="store_true", help="Mock-Runner statt Subprozess; eigenes Journal")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--plan", action="store_true", help="Sequenz + Env drucken, nichts starten")
    ap.add_argument("--fazit-gesamt", action="store_true",
                    help="beide Naechte aus dem Manifest poolen (kein Start) -> V10-GTOW-GESAMT-FAZIT")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sequenzen = lade_sequenzen()
    if args.plan or (args.nacht is None and args.smoke is None and not args.fazit_gesamt):
        drucke_plan(sequenzen, args.chunk_haende)
        return
    if args.fazit_gesamt:
        fahrt = _baue_fahrt(args, sequenzen) if args.dry_run else Nachtfahrt(_KeinRunner(), _echtes_journal(),
                                                                              sequenzen=sequenzen)
        if not fahrt.manifest["chunks"]:
            raise SystemExit(f"Kein Chunk im Manifest {fahrt.manifest_datei} — nichts zu poolen")
        fahrt.fahre_gesamt_fazit()
        return
    fahrt = _baue_fahrt(args, sequenzen)
    if args.smoke:
        fahrt.fahre_smoke(args.smoke, args.arm)
    if args.nacht:
        fahrt.fahre_nacht(args.nacht)


class _KeinRunner:
    """Fuer --fazit-gesamt: es wird nichts gestartet — jeder Aufruf waere ein Programmierfehler."""

    def lauf(self, arm_env: dict[str, str], n_haende: int) -> RohLauf:
        raise RuntimeError("--fazit-gesamt startet keine Chunks")

    def clear(self) -> None:
        raise RuntimeError("--fazit-gesamt ruft clear_inprogress nicht")


if __name__ == "__main__":
    main()
