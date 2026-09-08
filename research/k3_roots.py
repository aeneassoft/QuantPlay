"""K3-ROOTS — River-Roots aus den GTOW-Hand-Histories fuer den River-Pruefstand (v10 K3, E9).

Je Quellhand GENAU EIN Root = der River-BEGINN (Zustand vor der ersten River-Aktion, riv[0]); persistiert werden
Root-Geometrie (board, pot_river, eff, hero_oop, River-Sequenz, hero_hole), der live-treue Engine-State am Root
(fuer decide()-Abfragen des Policy-Oracles) und BEIDE Ranges am River-Beginn:
  * Villain: Tracker (RangeTracker().build auf dem am River-Deal geschnittenen State — research/tiefen_replay.py),
  * Hero: Tracker UND, falls pokerbot/strategy/hero_range.py (K1) existiert, hero_range_river_start(...);
    sonst Flag hero_k1_status='fehlt' (Karte K3: 'K1-Range falls vorhanden sonst Tracker (Flag)').

SPLITS (Build-Karte E9, V10_FAKTEN B13):
  holdout     = die vier Nacht-1-Dateien namentlich (Provenienz 'v4_gym_nackt': exploit ON, resolver OFF) — nur
                Root-Geometrie + Villain-Range werden daraus genutzt; Heros DAMALIGE Aktionen sind kein Lehrsignal.
  entwicklung = Nacht-2-Dateien laut data/sessions/gtow_manifest_2026-08-18.json bzw. hh_luecken_mine.ARME
                (kontrolle + v4_prince).
Die Originale (tiefen_replay.extrahiere ist auf hh_luecken_mine.ARME verdrahtet) werden NICHT geaendert; die
Dateiliste wird hier ueber eine EIGENE Ladefunktion parametrisiert; spot_state/replay/hero_seat_of/replay_voll
werden importiert (validierte Semantik: BB=100 reproduziert die Journal-AIVATs, hh_luecken_mine Docstring).

Ausschluss-Zaehler (Kopfzeile der JSONL): aivat_none, hero_seat_none, kein_river, rekonstruktion (spot_state None =
Board/Hole-Laenge oder Pot-Gatter |pot_eigen - pot| > 1 Chip), eff_null, range_leer.

Run: python -m research.k3_roots --split entwicklung   (-> data/runs/v10/k3_roots_entwicklung.jsonl)
     python -m research.k3_roots --split holdout
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

from pokerbot.strategy.range_tracker import RangeTracker
from research.gtow_tree_census import BB, hero_seat_of, replay
from research.hh_luecken_mine import ARME, SESS, replay_voll
from research.river_bill_replay import spot_state

AUSGABE_DIR = Path("data/runs/v10")
MANIFEST = SESS / "gtow_manifest_2026-08-18.json"

# E9: die vier Nacht-1-Dateien NAMENTLICH (Chunks A-D), Provenienz aus dem Manifest ('v4_gym_nackt').
HOLDOUT_DATEIEN = ("gtow_hands_1787012286.jsonl", "gtow_hands_1787014241.jsonl",
                   "gtow_hands_1787016046.jsonl", "gtow_hands_1787017672.jsonl")
HOLDOUT_PROVENIENZ = "v4_gym_nackt"

AUSSCHLUSS_KLASSEN = ("aivat_none", "hero_seat_none", "kein_river", "rekonstruktion", "eff_null", "range_leer")


def dateien_je_split(split: str) -> dict[str, str]:
    """{Dateiname: Provenienz/Arm} je Split. Entwicklung = hh_luecken_mine.ARME (Nacht 2), Holdout = E9-Liste."""
    if split == "holdout":
        prov = {}
        if MANIFEST.exists():
            mani = json.loads(MANIFEST.read_text(encoding="utf-8"))
            for name in HOLDOUT_DATEIEN:
                prov[name] = mani.get("dateien", {}).get(name, {}).get("arm", HOLDOUT_PROVENIENZ)
        return {name: prov.get(name, HOLDOUT_PROVENIENZ) for name in HOLDOUT_DATEIEN}
    if split == "entwicklung":
        return {name: arm for arm, namen in ARME.items() for name in namen}
    raise ValueError(f"split muss holdout|entwicklung sein: {split!r}")


def combo_str(c: tuple[str, str]) -> str:
    return c[0] + c[1]


def range_als_json(cw: dict) -> dict[str, float]:
    return {combo_str(c): float(w) for c, w in cw.items() if w > 0}


def range_aus_json(d: dict[str, float]) -> dict[tuple[str, str], float]:
    return {(k[:2], k[2:4]): float(w) for k, w in d.items()}


def _k1_hero_range(st0: dict, hero_seat: int):
    """Lazy K1-Import (pokerbot/strategy/hero_range.py, Paket P1). (range|None, status)."""
    try:
        from pokerbot.strategy import hero_range as hr  # noqa: PLC0415
    except Exception:  # noqa: BLE001
        return None, "fehlt"
    fn = getattr(hr, "hero_range_river_start", None)
    if fn is None:
        return None, "fehlt_funktion"
    try:
        r = fn(st0, hero=hero_seat)                # Signatur K1: (st0, guards=..., hero=None, konvention=...)
        if isinstance(r, dict) and r:
            return r, "ok"
        return None, "leer"
    except Exception as e:  # noqa: BLE001
        return None, f"fehler:{type(e).__name__}"


def river_sequenz(riv: list[tuple[int, dict]], hero_seat: int) -> list[tuple[str, str, float]]:
    """(wer, kind, zusatz_chips) je River-Aktion — dieselbe Uebersetzung wie tiefen_replay.extrahiere
    (Runden-Level je Sitz, Zusatz = Level-Differenz; call = noch zu zahlender Betrag)."""
    lvl = {0: 0.0, 1: 0.0}
    seq = []
    for _i, a in riv:
        s = a["seat"]
        wer = "hero" if s == hero_seat else "vill"
        if a["kind"] in ("bet", "raise"):
            zusatz = a["to"] - lvl[s]
            lvl[s] = a["to"]
            seq.append((wer, a["kind"], float(zusatz)))
        elif a["kind"] == "call":
            need = max(lvl.values()) - lvl[s]
            lvl[s] = max(lvl.values())
            seq.append((wer, "call", float(need)))
        else:
            seq.append((wer, a["kind"], 0.0))
    return seq


def root_hash(board: list[str], pot_river: float, eff: float, hero_oop: bool, vill: dict) -> str:
    """Stabiler Schluessel der Root-Geometrie + Villain-Range (Cache-Key des Policy-Oracles)."""
    blob = json.dumps([board, round(pot_river, 1), round(eff, 1), hero_oop,
                       sorted((combo_str(c), round(w, 6)) for c, w in vill.items())], sort_keys=True)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]


def extrahiere_roots(dateien: dict[str, str], split: str) -> tuple[list[dict], dict, int]:
    """Alle River-Roots der Dateien + Ausschluss-Zaehler + Gesamtzahl gelesener Haende (Nenner)."""
    zaehler = {k: 0 for k in AUSSCHLUSS_KLASSEN}
    roots, n_haende = [], 0
    for name, prov in dateien.items():
        for line in open(SESS / name, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            hand = json.loads(line)
            n_haende += 1
            root = _root_einer_hand(hand, name, prov, split, zaehler)
            if root is not None:
                roots.append(root)
    return roots, zaehler, n_haende


def _root_einer_hand(hand: dict, name: str, prov: str, split: str, zaehler: dict) -> dict | None:
    if hand.get("aivat") is None:
        zaehler["aivat_none"] += 1
        return None
    _, net, folder, _ = replay(hand)
    hs = hero_seat_of(hand, net, folder)
    if hs is None:
        zaehler["hero_seat_none"] += 1
        return None
    acts, _ = replay_voll(hand)
    riv = [(i, a) for i, a in enumerate(acts) if a["street"] == "river"]
    if not riv:
        zaehler["kein_river"] += 1
        return None
    st0 = spot_state(hand, hs, riv[0][0], acts)
    if st0 is None:
        zaehler["rekonstruktion"] += 1
        return None
    st0["to_act"] = 1 - st0["button"]           # River-Beginn: OOP (Nicht-Button) handelt zuerst
    eff = min(p["stack"] for p in st0["players"])
    if eff <= 0:
        zaehler["eff_null"] += 1
        return None
    t = RangeTracker().build(st0)
    hero_w = t.range.get(hs, {})
    vill_w = t.range.get(1 - hs, {})
    if not hero_w or not vill_w:
        zaehler["range_leer"] += 1
        return None
    k1, k1_status = _k1_hero_range(st0, hs)
    pot_river = float(st0["pot"])
    return {
        "split": split, "provenienz": prov, "datei": name, "hand_id": hand["hand_id"],
        "hero_seat": hs, "button": st0["button"], "hero_oop": hs != st0["button"],
        "board": list(st0["board"]), "pot_river": pot_river, "eff": float(eff),
        "hero_hole": list(st0["players"][hs]["hole"]),
        "seq_river": river_sequenz(riv, hs),
        "aivat_bb": hand["aivat"] / BB, "win_bb": float(hand.get("winnings") or 0) / BB,
        "root_hash": root_hash(st0["board"], pot_river, eff, hs != st0["button"], vill_w),
        "hero_k1_status": k1_status,
        "ranges": {"hero_tracker": range_als_json(hero_w), "vill_tracker": range_als_json(vill_w),
                   "hero_k1": range_als_json(k1) if k1 else None},
        "root_state": {k: v for k, v in st0.items() if not k.startswith("_")},
    }


def ausgabe_pfad(split: str) -> Path:
    return AUSGABE_DIR / f"k3_roots_{split}.jsonl"


def schreibe_roots(split: str, roots: list[dict], zaehler: dict, n_haende: int, dateien: dict) -> Path:
    AUSGABE_DIR.mkdir(parents=True, exist_ok=True)
    pfad = ausgabe_pfad(split)
    kopf = {"kopf": True, "split": split, "dateien": dateien, "n_haende": n_haende, "n_roots": len(roots),
            "ausschluss": zaehler, "erzeugt": time.strftime("%Y-%m-%d %H:%M:%S"),
            "hero_k1": {s: sum(1 for r in roots if r["hero_k1_status"] == s)
                        for s in sorted({r["hero_k1_status"] for r in roots})},
            "pot_river_ge_1500": sum(1 for r in roots if r["pot_river"] >= 1500)}
    with pfad.open("w", encoding="utf-8") as f:
        f.write(json.dumps(kopf, ensure_ascii=False) + "\n")
        for r in roots:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return pfad


def lade_roots(split: str, min_pot: float = 0.0) -> tuple[dict, list[dict]]:
    """(Kopfzeile, Roots) aus der persistierten Datei; Ranges als Combo-Tupel-Dicts."""
    pfad = ausgabe_pfad(split)
    zeilen = [json.loads(l) for l in pfad.read_text(encoding="utf-8").splitlines() if l.strip()]
    kopf, roots = zeilen[0], zeilen[1:]
    for r in roots:
        rg = r["ranges"]
        rg["hero_tracker"] = range_aus_json(rg["hero_tracker"])
        rg["vill_tracker"] = range_aus_json(rg["vill_tracker"])
        rg["hero_k1"] = range_aus_json(rg["hero_k1"]) if rg.get("hero_k1") else None
        r["seq_river"] = [tuple(x) for x in r["seq_river"]]
    return kopf, [r for r in roots if r["pot_river"] >= min_pot]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=("holdout", "entwicklung"), required=True)
    args = ap.parse_args()
    t0 = time.perf_counter()
    dateien = dateien_je_split(args.split)
    roots, zaehler, n = extrahiere_roots(dateien, args.split)
    pfad = schreibe_roots(args.split, roots, zaehler, n, dateien)
    ge = sum(1 for r in roots if r["pot_river"] >= 1500)
    print(f"[{args.split}] {n} Haende -> {len(roots)} River-Roots ({ge} mit pot_river>=1500) in "
          f"{time.perf_counter()-t0:.1f}s; Ausschluss {zaehler}; K1-Status "
          f"{ {r['hero_k1_status'] for r in roots} } -> {pfad}")


if __name__ == "__main__":
    main()
