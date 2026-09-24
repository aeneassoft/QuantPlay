"""K4 — persistentes Hand-Ledger fuer GTOW-Laeufe (append-only JSONL, Flush nach jedem Write).

WARUM (docs/reports/V10_FACTS.md A8): der Harness schrieb die Hand-Histories erst NACH allen Haenden mit open('w') —
Chunk 4 der Nacht 2 ging komplett verloren; kein Fingerprint, kein Arm, keine Hand-Kennung je Zeile. Dieses Ledger
schreibt JEDES Ereignis sofort auf Platte (open('a') + flush + fsync), damit ein Abbruch nach hand_end nichts
verliert, und listet beim Wiederanlauf die OFFENEN Haende (start ohne end) fuer den clear_inprogress-Abgleich (K5).

Ereignisse (eine JSON-Zeile je Ereignis, Feld 'typ'):
  prozess_start(fingerprint)                     -- einmal je Prozess, der komplette Fingerprint
  hand_start(hand_id, arm, fingerprint_hash)
  hand_end(hand_id, aivat, winnings, status, technische_events)   status in STATUS; None wird NIE zu 0 imputiert

Robustheit: `melde_*` schlucken JEDE Exception (der Lauf darf nie am Ledger sterben); Schreibfehler werden gezaehlt
(`schreibfehler`) und beim naechsten erfolgreichen Write als technisches Ereignis nachgetragen.
Datei: data/runs/v10/ledger_<prozess-start>.jsonl (Env POKERB_LEDGER_PFAD ueberschreibt, z.B. fuer Tests).
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Iterable, Mapping

from pokerbot import config

STATUS = ("ok", "unbekannt", "fehler")      # Karte K4: 'unbekannte Ausgaenge markiert, nie 0 imputiert'
LEDGER_DIR = config.DATA_DIR / "runs" / "v10"
ENV_LEDGER_PFAD = "POKERB_LEDGER_PFAD"
_PROZESS_START = int(time.time())           # der Dateiname bindet das Ledger an genau diesen Prozess (Chunk)


class GtowLedger:
    """Append-only JSONL-Ledger. Alle Schreibmethoden sind exception-frei (siehe Modul-Docstring)."""

    def __init__(self, pfad: str | Path | None = None):
        self.pfad = Path(pfad or os.environ.get(ENV_LEDGER_PFAD) or LEDGER_DIR / f"ledger_{_PROZESS_START}.jsonl")
        self.schreibfehler = 0
        # Wiederanlauf: das Gedaechtnis kommt aus der DATEI, damit ein Doppelstart auch ueber Prozessgrenzen erkannt wird.
        stand = abgleich(self.pfad) if self.pfad.is_file() else {"offen": [], "abgeschlossen": []}
        self._gestartet: set[str] = set(stand["offen"]) | set(stand["abgeschlossen"])
        self._beendet: set[str] = set(stand["abgeschlossen"])

    # ---- Ereignisse -------------------------------------------------------
    def prozess_start(self, fingerprint: Mapping[str, Any]) -> bool:
        return self._schreibe({"typ": "prozess_start", "fingerprint": dict(fingerprint)})

    def hand_start(self, hand_id: Any, arm: str, fingerprint_hash: str) -> bool:
        hid = str(hand_id)
        doppelt = hid in self._gestartet          # im selben Prozess zweimal gestartet = technisches Ereignis
        self._gestartet.add(hid)
        return self._schreibe({"typ": "hand_start", "hand_id": hid, "arm": arm, "fingerprint_hash": fingerprint_hash,
                               **({"doppelt_gestartet": True} if doppelt else {})})

    def hand_end(self, hand_id: Any, aivat: float | None, winnings: float | None, status: str,
                 technische_events: Iterable[str] = ()) -> bool:
        if status not in STATUS:
            status, technische_events = "fehler", [*technische_events, f"unbekannter_status:{status}"]
        if status == "ok" and aivat is None:      # ok ohne AIVAT gibt es nicht — ehrlich als unbekannt fuehren
            status = "unbekannt"
        hid = str(hand_id)
        self._beendet.add(hid)
        return self._schreibe({"typ": "hand_end", "hand_id": hid, "aivat": aivat, "winnings": winnings,
                               "status": status, "technische_events": list(technische_events)})

    # ---- Abgleich ---------------------------------------------------------
    def offene_haende(self) -> list[str]:
        """Haende mit start ohne end — aus der DATEI gelesen (Wiederanlauf), nicht aus dem Prozessgedaechtnis."""
        return offene_haende(self.pfad)

    # ---- intern -----------------------------------------------------------
    def _schreibe(self, ereignis: dict[str, Any]) -> bool:
        ereignis = {**ereignis, "zeit": time.time(), "pid": os.getpid()}
        if self.schreibfehler:
            ereignis["schreibfehler_zuvor"] = self.schreibfehler
        try:
            self.pfad.parent.mkdir(parents=True, exist_ok=True)
            with open(self.pfad, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(ereignis, ensure_ascii=False, default=str) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            return True
        except Exception:  # noqa: BLE001 — Ledger darf den Lauf nie brechen; der Fehler wird gezaehlt
            self.schreibfehler += 1
            return False


# ---------------------------------------------------------------- Lesen / Abgleich (dateibasiert)
def lese(pfad: str | Path) -> list[dict[str, Any]]:
    """Alle Ereignisse einer Ledger-Datei; eine abgeschnittene letzte Zeile (Prozessabbruch mitten im Write) wird
    uebersprungen, nicht als Fehler geworfen."""
    ereignisse: list[dict[str, Any]] = []
    try:
        with open(pfad, encoding="utf-8") as fh:
            for zeile in fh:
                zeile = zeile.strip()
                if not zeile:
                    continue
                try:
                    ereignisse.append(json.loads(zeile))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return ereignisse


def abgleich(pfad: str | Path) -> dict[str, list[str]]:
    """{offen, abgeschlossen, doppelt_gestartet} — offen = start ohne end (fuer clear_inprogress, K5)."""
    starts: dict[str, int] = {}
    ends: set[str] = set()
    for e in lese(pfad):
        if e.get("typ") == "hand_start":
            starts[e["hand_id"]] = starts.get(e["hand_id"], 0) + 1
        elif e.get("typ") == "hand_end":
            ends.add(e["hand_id"])
    return {"offen": sorted(h for h in starts if h not in ends),
            "abgeschlossen": sorted(h for h in starts if h in ends),
            "doppelt_gestartet": sorted(h for h, n in starts.items() if n > 1)}


def offene_haende(pfad: str | Path) -> list[str]:
    return abgleich(pfad)["offen"]


def offene_haende_alle(verzeichnis: str | Path = LEDGER_DIR) -> dict[str, list[str]]:
    """Wiederanlauf-Sicht ueber ALLE Ledger-Dateien des Verzeichnisses: {datei: offene_haende}."""
    verzeichnis = Path(verzeichnis)
    return {p.name: offen for p in sorted(verzeichnis.glob("ledger_*.jsonl")) if (offen := offene_haende(p))}


# ---------------------------------------------------------------- Prozess-Singleton + exception-freie Melder
_LEDGER: GtowLedger | None = None


def standard_ledger() -> GtowLedger:
    """Das eine Ledger dieses Prozesses (gtow_nacht spawnt je Chunk einen frischen Prozess -> eine Datei je Chunk)."""
    global _LEDGER
    if _LEDGER is None:
        _LEDGER = GtowLedger()
    return _LEDGER


def _agent_kern(agent: Any) -> Any:
    """PokerBotMVP haelt den PokerBotAgent als `_a` (poker_agent.py:64-66); andere Agenten haben keinen Fingerprint."""
    return getattr(agent, "_a", agent)


def melde_hand_start(agent: Any, hand_id: Any) -> None:
    """Hook fuer main._play_hand: schreibt hand_start mit Arm + Fingerprint-Hash des Agenten. Wirft NIE."""
    try:
        kern = _agent_kern(agent)
        arm = os.environ.get("POKERB_ARM") or getattr(kern, "stack_name", None) or type(kern).__name__
        standard_ledger().hand_start(hand_id, arm, getattr(kern, "fingerprint_hash", "ohne_fingerprint"))
    except Exception:  # noqa: BLE001
        pass


def melde_hand_ende(agent: Any, hand_id: Any, terminal: Any, status: str = "ok",
                    technische_events: Iterable[str] = ()) -> None:
    """Hook fuer main._play_hand: `terminal` = GameServiceResponse (oder dict/None). Ohne Terminalzustand oder ohne
    AIVAT -> status 'unbekannt' (nie 0). Wirft NIE."""
    try:
        aivat, winnings = _aivat_winnings(terminal)
        if terminal is None and status == "ok":
            status = "unbekannt"
        events = [*technische_events, *_e5_ereignis(agent)]
        standard_ledger().hand_end(hand_id, aivat, winnings, status, events)
    except Exception:  # noqa: BLE001
        pass


E5_EREIGNIS = "e5_sync_act_dict"   # Karte E5 NICHT live: der Agent wurde synchron im Event-Loop gerufen (Latenz-Gate E10)


def _e5_ereignis(agent: Any) -> list[str]:
    """Traegt den E5-Status je Hand ins Ledger: PokerBotAgent zaehlt synchrone act_dict-Aufrufe aus dem Loop-Thread
    (gtowizard.PokerBotAgent._zaehle_loop_blockade). Kumulativer Prozess-Zaehler — >0 heisst: dieser Lauf lief OHNE
    den E5-Client-Patch, seine Latenzen sind kein E10-Beleg."""
    n = getattr(_agent_kern(agent), "loop_blockierende_aufrufe", 0)
    return [f"{E5_EREIGNIS}:{n}"] if n else []


def _aivat_winnings(terminal: Any) -> tuple[float | None, float | None]:
    if terminal is None:
        return None, None
    gs = getattr(terminal, "game_state", None)
    if gs is None and isinstance(terminal, Mapping):
        gs = terminal.get("game_state") or terminal
    if gs is None:
        return None, None
    lese_feld = (lambda k: gs.get(k)) if isinstance(gs, Mapping) else (lambda k: getattr(gs, k, None))
    return lese_feld("aivat_score"), lese_feld("winnings")


if __name__ == "__main__":
    for datei, offen in offene_haende_alle().items():
        print(f"{datei}: {len(offen)} offene Haende {offen[:10]}{' ...' if len(offen) > 10 else ''}")
