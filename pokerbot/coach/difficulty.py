"""Adaptiver Schwierigkeitsregler: Session-Fehlerrate -> 10-20%-Band -> Liga-Komposition.

WHY: Lern-Maximierung per Fehlerraten-Band (docs/doctrine/TRAINER_DESIGN.md §5, 85%-Regel — ehrlich eine
HYPOTHESE, deshalb als adaptives Band umgesetzt, nicht als Dogma). Der Regler ist eine PURE,
deterministische Funktion ueber der PRESET_LADDER: zu viele teure Entscheidungen (> 20 %)
-> weichere Liga (mehr station/nit/whale, exploit_gain runter); zu wenige (< 10 %) -> haertere
Liga (tag/lag/shark/maniac, exploit_gain hoch — nur im Exploit-Modus). Hoechstens EIN Schritt
pro Session (Hysterese); der Modus kommt aus der Session (P0-0), nie aus Env.

Komposition = {"tier": int, "profiles": {seat: profilname}, "exploit_gain": float, "mode": str}.
Die Profilnamen sind die arena-Liga (pokerbot/arena/sixmax.py PROFILES incl. der Held-out-
Varianten rock/whale/shark); Tier 2 ist die heutige six_server-Default-Belegung.

Run: python -m pokerbot.coach.difficulty   (Selbsttest, kein Server noetig)
"""
from __future__ import annotations

import json
from pokerbot import config

TARGET_BAND = (0.10, 0.20)      # Ziel-Fehlerraten-Band (Anteil teuer+leak an allen Grades)
MIN_DECISIONS = 30              # unter n=30 ist die Rate Rauschen -> Regler ruehrt sich nicht
EXPLOIT_GAIN_BASE = 1.0         # neutraler Exploit-Hebel (Knobs-Default, byte-identisch)
EXPLOIT_GAIN_MAX = 1.5          # Feindial-Obergrenze; die READ_*-Caps deckeln die Deltas hart
EXPLOIT_GAIN_STEP = 0.5

# Leiter leichteste -> haerteste Belegung (Sitz 1-5; Sitz 0 = Mensch). Nur existierende
# arena-Profile (docs/plans/TRAINER_PLAN.md P3-D Schritt 2); Tier 2 = die heutige Default-Belegung.
PRESET_LADDER: tuple[dict[int, str], ...] = (
    {1: "whale", 2: "station", 3: "rock", 4: "nit", 5: "whale"},      # T0
    {1: "station", 2: "whale", 3: "nit", 4: "rock", 5: "maniac"},     # T1
    {1: "tag", 2: "lag", 3: "nit", 4: "station", 5: "maniac"},        # T2 (Default)
    {1: "tag", 2: "shark", 3: "lag", 4: "tag", 5: "shark"},           # T3
    {1: "shark", 2: "tag", 3: "shark", 4: "tag", 5: "shark"},         # T4
)
DEFAULT_TIER = 2

STATE_PATH = config.DATA_DIR / "trainer" / "difficulty.json"

GRADED = frozenset({"ok", "teuer", "leak"})     # der gepinnte P0-4/coach.v1-Wortschatz
COSTLY = frozenset({"teuer", "leak"})


def error_rate(decision_records) -> tuple[float, int]:
    """(Fehlerrate, n) ueber Decision-Records: Anteil teuer+leak an allen gepinnten Grades."""
    grades = [r.get("grade") for r in decision_records if r.get("grade") in GRADED]
    n = len(grades)
    return (sum(1 for g in grades if g in COSTLY) / n if n else 0.0, n)


def default_composition(mode: str = "gto") -> dict:
    return {"tier": DEFAULT_TIER, "profiles": dict(PRESET_LADDER[DEFAULT_TIER]),
            "exploit_gain": EXPLOIT_GAIN_BASE, "mode": mode}


def _composition_at(tier: int, exploit_gain: float, mode: str) -> dict:
    tier = max(0, min(len(PRESET_LADDER) - 1, tier))
    return {"tier": tier, "profiles": dict(PRESET_LADDER[tier]),
            "exploit_gain": exploit_gain, "mode": mode}


def update(session_error_rate: float, current_composition: dict, n: int | None = None) -> dict:
    """Pure Band-Steuerung: eine Session-Fehlerrate rein, die NEUE Komposition raus.

    Hoechstens ein Schritt (Hysterese). n=None heisst 'Rate ist belastbar' (der Aufrufer hat
    schon gefiltert); mit n < MIN_DECISIONS bewegt sich NIE etwas. Der exploit_gain-Feindial
    existiert nur im Exploit-Modus (im GTO-Modus ignorieren die Bots ihre Reads ohnehin)."""
    comp = current_composition or default_composition()
    tier = max(0, min(len(PRESET_LADDER) - 1, int(comp.get("tier", DEFAULT_TIER))))
    gain = float(comp.get("exploit_gain", EXPLOIT_GAIN_BASE))
    mode = comp.get("mode", "gto")
    if n is not None and n < MIN_DECISIONS:
        return _composition_at(tier, gain, mode)
    lo, hi = TARGET_BAND
    if session_error_rate > hi:                     # zu schwer -> weicher
        if mode == "exploit" and gain > EXPLOIT_GAIN_BASE:
            gain = max(EXPLOIT_GAIN_BASE, gain - EXPLOIT_GAIN_STEP)
        else:
            tier -= 1
    elif session_error_rate < lo:                   # zu leicht -> haerter
        if tier < len(PRESET_LADDER) - 1:
            tier += 1
        elif mode == "exploit":
            gain = min(EXPLOIT_GAIN_MAX, gain + EXPLOIT_GAIN_STEP)
    return _composition_at(tier, gain, mode)


# ---------------------------------------------------------------- Persistenz (Session ueberlebt)
def load_state() -> dict:
    """Komposition von Platte; Default T2, wenn Datei fehlt/kaputt (Session-Tod ist verlustfrei)."""
    try:
        raw = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return _composition_at(int(raw.get("tier", DEFAULT_TIER)),
                               float(raw.get("exploit_gain", EXPLOIT_GAIN_BASE)),
                               raw.get("mode", "gto"))
    except (OSError, ValueError, TypeError):
        return default_composition()


def save_state(composition: dict, rate: float | None = None, n: int | None = None, ts: str = "") -> None:
    """Schreibt die Komposition + append-artige History nach data/trainer/difficulty.json."""
    history = []
    try:
        history = json.loads(STATE_PATH.read_text(encoding="utf-8")).get("history", [])
    except (OSError, ValueError, TypeError):
        pass
    history.append({"ts": ts, "rate": rate, "n": n, "tier": composition.get("tier")})
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps({**composition, "history": history}, ensure_ascii=False),
                          encoding="utf-8")


def current_assignment() -> dict[int, str]:
    """Sitz->Profil der persistierten Stufe — der six_server-Kompositions-Seam (P3-D Schritt 3)."""
    return dict(load_state()["profiles"])


# ---------------------------------------------------------------- Selbsttest (pur, offline)
def _hardness(comp: dict) -> float:
    """Totale Ordnung der Schwierigkeit fuer den Monotonie-Check."""
    return comp["tier"] + comp["exploit_gain"] - EXPLOIT_GAIN_BASE


def _selftest():
    from pokerbot.arena.sixmax import PROFILES  # jede Leiter-Zelle muss ein reales Profil sein
    for tier_profiles in PRESET_LADDER:
        assert sorted(tier_profiles) == [1, 2, 3, 4, 5]
        for name in tier_profiles.values():
            assert name in PROFILES, f"unbekanntes Profil {name!r}"

    base = default_composition("gto")
    # Band-Logik: >0.20 weicher, <0.10 haerter, im Band halten, n<30 bewegt NIE etwas
    assert update(0.25, base, n=50)["tier"] == 1
    assert update(0.05, base, n=50)["tier"] == 3
    assert update(0.15, base, n=50)["tier"] == 2
    assert update(0.99, base, n=10) == base and update(0.0, base, n=10) == base

    # Clamps: T0 bleibt bei zu-schwer T0; T4 bleibt T4 (gto: kein Gain-Dial)
    t0 = _composition_at(0, EXPLOIT_GAIN_BASE, "gto")
    t4 = _composition_at(4, EXPLOIT_GAIN_BASE, "gto")
    assert update(0.9, t0, n=50)["tier"] == 0
    hard = update(0.05, t4, n=50)
    assert hard["tier"] == 4 and hard["exploit_gain"] == EXPLOIT_GAIN_BASE

    # Exploit-Feindial: T4 + zu-leicht hebt gain auf 1.5 und deckelt dort; zu-schwer senkt
    # erst den Gain zurueck auf 1.0, bevor die Stufe faellt
    t4x = _composition_at(4, EXPLOIT_GAIN_BASE, "exploit")
    up = update(0.05, t4x, n=50)
    assert up["exploit_gain"] == EXPLOIT_GAIN_MAX and up["tier"] == 4
    assert update(0.05, up, n=50)["exploit_gain"] == EXPLOIT_GAIN_MAX      # Deckel
    down = update(0.30, up, n=50)
    assert down["exploit_gain"] == EXPLOIT_GAIN_BASE and down["tier"] == 4
    assert update(0.30, down, n=50)["tier"] == 3

    # Monotonie: hoehere Fehlerrate ergibt NIE eine haertere Komposition (Task-Invariante)
    for comp in (base, t0, t4, t4x, up):
        results = [_hardness(update(r / 100, comp, n=60)) for r in range(0, 101, 5)]
        assert all(a >= b for a, b in zip(results, results[1:])), (comp, results)

    # Purity: der Input wird nie mutiert; Determinismus: gleicher Input -> gleicher Output
    frozen = json.dumps(base, sort_keys=True)
    update(0.25, base, n=50)
    assert json.dumps(base, sort_keys=True) == frozen
    assert update(0.25, base, n=50) == update(0.25, base, n=50)

    # error_rate: nur gepinnte Grades zaehlen, teuer+leak = Fehler
    recs = [{"grade": "ok"}, {"grade": "teuer"}, {"grade": "leak"}, {"grade": None}, {"x": 1}]
    rate, n = error_rate(recs)
    assert n == 3 and abs(rate - 2 / 3) < 1e-9

    # Persistenz-Roundtrip in ein Temp-File (STATE_PATH umbiegen, Platte des Users unberuehrt)
    import tempfile
    from pathlib import Path
    global STATE_PATH
    original = STATE_PATH
    with tempfile.TemporaryDirectory() as td:
        STATE_PATH = Path(td) / "difficulty.json"
        try:
            assert load_state() == default_composition()          # fehlende Datei -> Default
            save_state(update(0.05, base, n=50), rate=0.05, n=50)
            assert load_state()["tier"] == 3
            assert current_assignment() == dict(PRESET_LADDER[3])
            save_state(load_state(), rate=0.15, n=40)
            assert len(json.loads(STATE_PATH.read_text(encoding="utf-8"))["history"]) == 2
        finally:
            STATE_PATH = original

    print("OK - Band 10-20% steuert die 5-Tier-Leiter deterministisch, monoton, mit Hysterese; "
          "exploit_gain-Feindial nur im Exploit-Modus; Persistenz-Roundtrip sauber.")


if __name__ == "__main__":
    _selftest()
