"""K4 Produktionsintegritaet — Laufzeit-Fingerprint dessen, was GELADEN wurde, + Fehlkonfig-Gatter.

Hintergrund (docs/plans/V10_BUILD_CARD.md K4, docs/reports/V10_FACTS.md A8/B12, docs/catalogs/HU_OPTIMAL_MAP.md D1): der GTOW-Harness
lief ohne jede Konfig-Pruefung (`gto_mode.fingerprint()` existierte, wurde aber nie gerufen; `POKERB_AUSLESE_STACK`
fehlte in den Fingerprint-Keys), und die HU-Web-App spielte eine nie gemessene Konfiguration. Jede bb/100-Zahl haengt
an der Frage, WELCHER Bot sie erspielt hat — dieses Modul beantwortet sie pro Prozess, aus dem laufenden Objekt
(bot.exploit / bot.use_resolver TATSAECHLICH), nicht aus der Env-Absicht.

Zwei Funktionen tragen alles:
  fingerprint_geladen(bot, stack_name) -> dict   (alle Pflichtfelder, s. PFLICHTFELDER)
  pruefe_konfiguration(erwartet, ist)            (SystemExit mit klarer Meldung bei Abweichung)
Das Gatter wird ueber die Env POKERB_ERWARTE_PROFIL=v5-H|v10 scharf geschaltet; unset = nur loggen.

Kein Strategie-Code: hier wird gelesen und gehasht, nie entschieden.
"""
from __future__ import annotations

import hashlib
import inspect
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping

from pokerbot import config
from pokerbot.strategy import gto_mode
from pokerbot.strategy.contracts import KONTRAKT_VERSION, PRIVATE_SEED_QUELLE, konfig_hash_aus

ENV_ERWARTE_PROFIL = "POKERB_ERWARTE_PROFIL"
ENV_PRIVATE_SEED_QUELLE = "POKERB_PRIVATE_SEED_QUELLE"   # K2 setzt sie live auf 'os_urandom' (Karte K2), sonst 'keine'
ENV_ARM = "POKERB_ARM"                                   # Arm-Name fuer das Ledger (gtow_nacht_v10 setzt ihn je Chunk)

# PRINCE-Flags, die die Strategie-Module bei IMPORT einfrieren (Modulkonstanten). Genau hier klafft Env-Absicht und
# geladener Zustand auseinander: wird pokerbot.strategy.bot VOR `POKERB_PRINCE=1` importiert, bleibt z.B. _TURN_DEFENSE
# fuer immer 0.0, obwohl gto_mode.prince_enabled() danach True meldet (Reviewer-Befund HOCH, 2026-09-07, reproduziert).
# (Env-Key, Modul, Konstante, Parser des Profil-Strings) — die Sollwerte kommen aus gto_mode.PRINCE_PROFILE, nie getippt.
_FLAG_AN = lambda s: s == "1"   # noqa: E731 — so lesen bot.py/resolver.py/range_tracker.py ihre "1"-Flags
_PRINCE_IMPORTKONSTANTEN: tuple[tuple[str, str, str, Any], ...] = (
    ("POKERB_TURN_DEFENSE", "pokerbot.strategy.bot", "_TURN_DEFENSE", float),                 # bot.py:95
    ("POKERB_SLOWPLAY", "pokerbot.strategy.bot", "_SLOWPLAY", float),                         # bot.py:98
    ("POKERB_LINE_U", "pokerbot.strategy.bot", "_LINE_U", _FLAG_AN),                          # bot.py:89
    ("POKERB_RIVER_ECALL", "pokerbot.strategy.bot", "_RIVER_ECALL", _FLAG_AN),                # bot.py:84
    ("POKERB_SIZE_INJECT", "pokerbot.strategy.resolver", "_SIZE_INJECT", _FLAG_AN),           # resolver.py:117
    ("POKERB_TRACKER_AGGRO_FULL", "pokerbot.strategy.range_tracker", "TRACKER_AGGRO_FULL", _FLAG_AN),  # range_tracker.py:79
)
PRINCE_SOLL_TURN_DEFENSE = float(gto_mode.PRINCE_PROFILE["POKERB_TURN_DEFENSE"])   # 0.07 (gto_mode.py:44)
PRINCE_SOLL_SLOWPLAY = float(gto_mode.PRINCE_PROFILE["POKERB_SLOWPLAY"])           # 0.25 (gto_mode.py:45)

# Erwartungsprofile = die beiden v10-Arme der Karte (Abschnitt 'Arme'): PRINCE, exploit OFF, TexasSolver ON.
# Schluessel sind Fingerprint-Felder, damit pruefe_konfiguration generisch vergleichen kann.
# `prince` (Env-Absicht) bleibt drin, weil die zur LAUFZEIT gelesenen Profil-Flags (gto_mode.flag in resolver/
# postflop) daran haengen; `prince_geladen` + die Deception-Werte pruefen den EINGEFRORENEN Zustand (Karte K4:
# 'Pruefung dessen, was GELADEN wurde').
_PRINCE_ARM = {"prince": True, "prince_geladen": True, "exploit": False, "use_resolver": True,
               "turn_defense": PRINCE_SOLL_TURN_DEFENSE, "slowplay": PRINCE_SOLL_SLOWPLAY}
ERWARTUNGSPROFILE: dict[str, dict[str, Any]] = {
    "v5-H": {**_PRINCE_ARM, "stack": "r8_stack"},
    "v10": {**_PRINCE_ARM, "stack": "r10_stack"},
}

# Alles, was ein Fingerprint tragen MUSS (Karte K4 'Fingerprint je Hand'); der Test prueft genau diese Liste.
PFLICHTFELDER = (
    "git", "advisor_pt", "prince", "prince_geladen", "prince_importflags", "gto_mode", "gto_mode_flags", "exploit",
    "use_resolver", "use_turn_resolver", "stack", "turn_defense", "slowplay", "gpu_solver", "k1_version", "river_plan",
    "private_seed_quelle", "pythonhashseed", "pid", "fingerprint_hash",
)
# Felder, die sich je Prozess/Zeitpunkt aendern, ohne die STRATEGIE zu aendern -> nicht im Hash (sonst nie zwei
# gleiche Hashes). `advisor_geladen_jetzt` ist LAUFZEIT-Zustand (welche Netze der Lazy-Cache gerade haelt, advisor.py:54-71):
# derselbe Bot traegt vor dem ersten Flop [] und danach 5 Namen — Reviewer-Befund 2026-09-07 (Hash kippte nach Warm-up,
# zweite HU-Server-Session != erste). Der Hash muss 'gleicher Hash = gleicher Arm' fuer den K5-Chunk-Vergleich tragen.
_NICHT_IM_HASH = ("pid", "zeit_utc", "fingerprint_hash", "python", "advisor_geladen_jetzt")

_GIT_TIMEOUT_S = 10
_ADVISOR_ZUSATZ_DATEIEN = ("defense_advisor.pt",)   # advisor._load_defense laedt sie ausserhalb von advisor._FILES
_DEEPCFR_DATEI = "deepcfr_hunl.pt"                   # bot.py:241, nur bei bot.use_deepcfr


# ---------------------------------------------------------------- Bausteine
def git_stand(repo: Path | None = None) -> dict[str, Any]:
    """Git-HEAD + dirty (getrennt: geaenderte vs. untracked Dateien). Robust: ohne git/Repo -> status 'unbekannt'."""
    repo = repo or config.ROOT
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True,
                              encoding="utf-8", timeout=_GIT_TIMEOUT_S, check=True).stdout.strip()
        porcelain = subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True,
                                   encoding="utf-8", timeout=_GIT_TIMEOUT_S, check=True).stdout.splitlines()
    except (OSError, subprocess.SubprocessError, ValueError) as e:
        return {"head": None, "dirty": None, "status": f"unbekannt ({type(e).__name__})"}
    untracked = [z[3:] for z in porcelain if z.startswith("??")]
    geaendert = [z[3:] for z in porcelain if z and not z.startswith("??")]
    return {"head": head, "dirty": bool(porcelain), "geaendert": sorted(geaendert), "untracked": sorted(untracked),
            "status": "ok"}


def sha256_datei(pfad: Path) -> str | None:
    """sha256 einer Datei (None, wenn sie fehlt) — die .pt-Netze sind gitignored, nur der Hash ist versionierbar."""
    try:
        h = hashlib.sha256()
        with open(pfad, "rb") as fh:
            for block in iter(lambda: fh.read(1 << 20), b""):
                h.update(block)
        return h.hexdigest()
    except OSError:
        return None


def advisor_hashes(bot: Any) -> dict[str, Any]:
    """sha256 der Advisor-Netze, die dieser Bot LAEDT (advisor._FILES + defense_advisor + deepcfr nur bei use_deepcfr).
    Reine KONFIGURATION (Dateiinhalt auf Platte) — was davon gerade im Cache liegt, liefert advisor_geladen_jetzt()."""
    from pokerbot.strategy import advisor
    dateien = sorted(set(advisor._FILES.values()) | set(_ADVISOR_ZUSATZ_DATEIEN))
    if getattr(bot, "use_deepcfr", False):
        dateien.append(_DEEPCFR_DATEI)
    hashes = {name: sha256_datei(config.POSTFLOP_DIR / name) for name in dateien}
    return {"sha256": hashes, "fehlend": sorted(n for n, h in hashes.items() if h is None)}


def advisor_geladen_jetzt() -> list[str]:
    """Welche Advisor-Netze IM MOMENT im Lazy-Cache liegen (advisor.py:54-71, 164-180) — Diagnose-Information
    (z.B. 'Prozess hat nie einen River gesehen'), KEIN Konfigurationsmerkmal: bleibt ausserhalb des Hashes."""
    from pokerbot.strategy import advisor
    geladen = sorted(advisor._FILES[s] for s, net in advisor._NETS.items() if net)
    if advisor._DEF.get("net"):
        geladen.append(_ADVISOR_ZUSATZ_DATEIEN[0])
    return geladen


def gpu_solver_version() -> dict[str, Any]:
    """torch/cuda + Quell-Hashes der GPU-Solver-Module + die r8-Chirurgie-Konstanten (river_gpu_guard-Defaults).
    Es gibt keine Versionskonstante in gpu_cfr/gpu_resolver — der Quelltext-Hash IST die Version."""
    out: dict[str, Any] = {}
    try:
        import torch
        out.update(torch=torch.__version__, cuda=torch.version.cuda, cuda_verfuegbar=bool(torch.cuda.is_available()))
    except Exception as e:  # noqa: BLE001 — torch fehlt/kaputt ist ein Befund, kein Absturz des Fingerprints
        out.update(torch=None, cuda=None, cuda_verfuegbar=False, torch_fehler=type(e).__name__)
    strat = config.ROOT / "pokerbot" / "strategy"
    out["gpu_cfr_sha256"] = sha256_datei(strat / "gpu_cfr.py")
    out["gpu_resolver_sha256"] = sha256_datei(strat / "gpu_resolver.py")
    try:
        from pokerbot.strategy import gpu_resolver
        out["default_iters"] = gpu_resolver.DEFAULT_ITERS
        out["hero_min_gewicht"] = gpu_resolver.HERO_MIN_GEWICHT
    except Exception as e:  # noqa: BLE001
        out["gpu_resolver_fehler"] = type(e).__name__
    try:
        from pokerbot.autogym.improver import river_gpu_guard
        params = inspect.signature(river_gpu_guard).parameters
        out["r8_guard"] = {k: p.default for k, p in params.items() if p.default is not inspect.Parameter.empty}
    except Exception as e:  # noqa: BLE001
        out["r8_guard_fehler"] = type(e).__name__
    return out


def k1_version() -> dict[str, Any]:
    """K1_VERSION aus pokerbot.strategy.hero_range (Paket P1) — bis es existiert ehrlich 'nicht_importierbar'."""
    try:
        from pokerbot.strategy import hero_range
        return {"version": getattr(hero_range, "K1_VERSION", None), "status": "ok"}
    except Exception as e:  # noqa: BLE001
        return {"version": None, "status": f"nicht_importierbar ({type(e).__name__})"}


def river_plan_konstanten() -> dict[str, Any]:
    """P_min/Iterationen/Praezision des River-Plans (Paket P2, pokerbot.autogym.river_plan). FALLBACK, solange das
    Modul fehlt: die eingefrorenen Vertrags-Defaults aus contracts.RiverPlan (schwelle 1500, 150 Iter, fp32) —
    als solche GEKENNZEICHNET."""
    try:
        from pokerbot.autogym import river_plan
        werte = {n: getattr(river_plan, n) for n in dir(river_plan)
                 if n.isupper() and isinstance(getattr(river_plan, n), (int, float, str))}
        return {"quelle": "river_plan", "konstanten": werte}
    except Exception as e:  # noqa: BLE001
        from pokerbot.strategy.contracts import RiverPlan
        felder = {f.name: f.default for f in RiverPlan.__dataclass_fields__.values()
                  if f.name in ("schwelle_chips", "iterationen", "praezision")}
        return {"quelle": f"fallback_contracts_default ({type(e).__name__})", "konstanten": felder}


def private_seed_quelle(bot: Any) -> str:
    """Herkunft der privaten Randomisierung (Vokabular contracts.PRIVATE_SEED_QUELLE). Der Bot darf sie selbst
    tragen (K2 setzt bot.private_seed_quelle), sonst die Env, sonst 'keine'."""
    q = getattr(bot, "private_seed_quelle", None) or os.environ.get(ENV_PRIVATE_SEED_QUELLE) or "keine"
    return q if q in PRIVATE_SEED_QUELLE else f"unbekannt:{q}"


def prince_importflags() -> dict[str, Any]:
    """Die PRINCE-Flags so, wie die Strategie-Module sie bei IMPORT eingefroren haben (_PRINCE_IMPORTKONSTANTEN) —
    nicht die Env-Absicht. None = Modul/Konstante nicht lesbar (ist ein Befund, kein Absturz). resolver/range_tracker
    importiert bot.py lazy (bot.py:1042): importiert der Fingerprint sie zuerst, frieren sie mit der JETZIGEN Env ein
    — derselbe Wert, den der Bot spaeter nutzt, weil die Env nach dem Fingerprint nicht mehr wechselt."""
    import importlib
    werte: dict[str, Any] = {}
    for env_key, modulname, konstante, _parser in _PRINCE_IMPORTKONSTANTEN:
        try:
            werte[env_key] = getattr(importlib.import_module(modulname), konstante)
        except Exception:  # noqa: BLE001
            werte[env_key] = None
    return werte


def prince_abweichungen(importflags: Mapping[str, Any], exploit: bool) -> list[str]:
    """Welche eingefrorenen Werte NICHT dem PRINCE-Profil entsprechen (leer = PRINCE ist wirklich geladen).
    exploit gehoert dazu: PRINCE impliziert GTO-Disziplin (PROFILE POKERB_EXPLOIT=0), Reviewer-Fix-Vorschlag."""
    abweichungen = []
    for env_key, _modul, _konst, parser in _PRINCE_IMPORTKONSTANTEN:
        soll = parser(gto_mode.PRINCE_PROFILE[env_key])
        ist = importflags.get(env_key)
        if ist != soll:
            abweichungen.append(f"{env_key}: soll {soll!r}, geladen {ist!r}")
    if exploit:
        abweichungen.append("exploit: soll False, geladen True")
    return abweichungen


def _bot_flag_werte(importflags: Mapping[str, Any]) -> dict[str, float | None]:
    """TURN_DEFENSE/SLOWPLAY als Top-Level-Pflichtfelder (bot.py:95,98) — der Kurzblick fuer Log und Profil."""
    td, sp = importflags.get("POKERB_TURN_DEFENSE"), importflags.get("POKERB_SLOWPLAY")
    return {"turn_defense": None if td is None else float(td), "slowplay": None if sp is None else float(sp)}


# ---------------------------------------------------------------- Fingerprint
def fingerprint_geladen(bot: Any, stack_name: str | None) -> dict[str, Any]:
    """Der Fingerprint dessen, was in DIESEM Prozess geladen ist. `stack_name` = der um decide gewickelte Auslese-
    Stack ('basis' = kein Wrapper). Der Hash ist prozess- UND warm-up-invariant: pid/zeit/advisor_geladen_jetzt
    (_NICHT_IM_HASH) werden mitgefuehrt, aber nicht gehasht — zwei Prozesse mit gleichem Code, gleicher Env und
    gleichen Bot-Flags tragen denselben fingerprint_hash, egal wie viele Haende einer schon gespielt hat."""
    exploit = bool(getattr(bot, "exploit", None))
    importflags = prince_importflags()
    abweichungen = prince_abweichungen(importflags, exploit)
    fp: dict[str, Any] = {
        "kontrakt_version": KONTRAKT_VERSION,
        "git": git_stand(),
        "advisor_pt": advisor_hashes(bot),
        "advisor_geladen_jetzt": advisor_geladen_jetzt(),
        "prince": gto_mode.prince_enabled(),                 # Env-ABSICHT (traegt die zur Laufzeit gelesenen Flags)
        "prince_geladen": not abweichungen,                  # eingefrorener ZUSTAND: Import-Konstanten == PRINCE_PROFILE
        "prince_abweichungen": abweichungen,
        "prince_importflags": importflags,
        "gto_mode": gto_mode.enabled(),
        "gto_mode_flags": gto_mode.fingerprint(),
        "exploit": exploit,
        "use_resolver": bool(getattr(bot, "use_resolver", False)),
        "use_turn_resolver": bool(getattr(bot, "use_turn_resolver", False)),
        "use_probe": bool(getattr(bot, "use_probe", False)),
        "use_deepcfr": bool(getattr(bot, "use_deepcfr", False)),
        "use_blueprint": bool(getattr(bot, "use_blueprint", False)),
        "use_range_tracker": bool(getattr(bot, "use_range_tracker", False)),
        "stack": stack_name or "basis",
        **_bot_flag_werte(importflags),
        "gpu_solver": gpu_solver_version(),
        "k1_version": k1_version(),
        "river_plan": river_plan_konstanten(),
        "private_seed_quelle": private_seed_quelle(bot),
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        "python": sys.version.split()[0],
        "pid": os.getpid(),
        "zeit_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    fp["fingerprint_hash"] = fingerprint_hash(fp)
    return fp


def fingerprint_hash(fp: Mapping[str, Any]) -> str:
    """sha256 ueber den strategie-relevanten Teil (ohne _NICHT_IM_HASH) — der Wert, den das Ledger je Hand traegt."""
    return konfig_hash_aus({k: v for k, v in fp.items() if k not in _NICHT_IM_HASH})


# ---------------------------------------------------------------- Gatter
def pruefe_konfiguration(erwartet: Mapping[str, Any], ist: Mapping[str, Any]) -> None:
    """Fehlkonfig-Gatter: jedes erwartete Feld muss im Fingerprint exakt stimmen, sonst SystemExit mit ALLEN
    Abweichungen (nicht nur der ersten) — ein Lauf mit falschem Bot ist wertlos, egal wie lang er lief."""
    abweichungen = [f"  {feld}: erwartet {soll!r}, geladen {ist.get(feld)!r}"
                    for feld, soll in erwartet.items() if ist.get(feld) != soll]
    if erwartet.get("prince_geladen") and ist.get("prince_abweichungen"):
        # WELCHE Import-Konstante eingefroren falsch ist — der Bediener sieht sofort den Import-Reihenfolge-Fehler
        abweichungen.append("  prince_abweichungen (Modul VOR der Env importiert?): " + "; ".join(ist["prince_abweichungen"]))
    if abweichungen:
        raise SystemExit("FEHLKONFIGURATION (K4-Gatter) -- Start abgebrochen:\n" + "\n".join(abweichungen)
                         + f"\n  fingerprint_hash {ist.get('fingerprint_hash')}")


def gatter_aus_env(fp: Mapping[str, Any], log=print) -> str | None:
    """Liest POKERB_ERWARTE_PROFIL; gesetzt -> pruefe_konfiguration (SystemExit bei Abweichung), unset -> nur die
    Kernfelder loggen. Gibt den geprueften Profilnamen zurueck (None = nur geloggt)."""
    kern = {k: fp.get(k) for k in ("prince", "prince_geladen", "exploit", "use_resolver", "use_turn_resolver", "stack",
                                   "turn_defense", "slowplay")}
    profil = os.environ.get(ENV_ERWARTE_PROFIL)
    if not profil:
        log(f"[K4] Fingerprint {fp.get('fingerprint_hash', '')[:12]} {kern} (no expectation profile, logged only)")
        return None
    if profil not in ERWARTUNGSPROFILE:
        raise SystemExit(f"{ENV_ERWARTE_PROFIL}={profil!r} unbekannt; bekannt: {sorted(ERWARTUNGSPROFILE)}")
    pruefe_konfiguration(ERWARTUNGSPROFILE[profil], fp)
    log(f"[K4] Fingerprint {fp.get('fingerprint_hash', '')[:12]} {kern} == Profil {profil}: OK")
    return profil
