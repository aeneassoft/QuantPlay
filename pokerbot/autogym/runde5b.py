"""RUNDE 5b — Replikationen + Kombi (2026-08-17 abend), auf Estimator v2.

Befund-Lage aus Runde 5 (Journal): turn_wert 8,4% Kanal, Vorzeichen-z ~7,7,
nz-Median +132; k3_deception 60% positiv; raise_narrow_10 1% Kanal, 73% positiv,
nz-Median +2160 (Grosspott-Knoten); sel_all_m15 Kanal LEER (0 divergente Decks
auf 30k -> Journal-Korrektur: nicht 'abgelehnt', sondern 'kein Kanal bei m15');
prince = Kanal-Artefakt (exploit-OFF vs exploitbare GTOBaseline).

Dieser Treiber fahrt die 3-Laeufe-Regel zu Ende:
  1  pargate turn_wert vs sel_m15 @30k, ZWEI frische Deck-Baenke (40000/80000).
  2  envgate Runde 2+3 @12k (Deck-Baenke 25000/45000): k3_deception,
     turn_def_adv, raise_narrow_05/10 + KOMBI (turn_wert-Wrapper + K3 + RN10).
  3  orakel_duell turn_wert vs sel_m15 (Nebenwirkungs-Panel, vorregistriert:
     verpasster_wert_turn faellt im mechanischen Kanal, bet_braucht_unplausible_
     folds steigt NICHT, HART=0; Klasse->0 waere ROTES TUCH).
  4  Gepoolte Auswertung ueber alle Laeufe (Chips-Mittel +- 2SE gepoolt).

  python -m pokerbot.autogym.runde5b
"""
from __future__ import annotations

import json
import multiprocessing as mp
import subprocess
import sys
import time
from pathlib import Path

ERWARTUNGEN = {
    "estimator_v2": ("VORREGISTRIERT: Entscheidung auf rohem Mittel +- 2SE "
                     "(Trim war fuer duenne Kanaele blind, s. stats.py-Docstring); "
                     "Vorzeichen-Test als Stuetz-Evidenz."),
    "turn_wert_repl": ("Replikation haelt: gepoolt ueber 3x30k bleibt das Mittel "
                       "positiv; Vorzeichen-z bleibt > 3. Ehrlich: 3x30k ergibt "
                       "SE ~2,3 — Signifikanz des MITTELS nicht garantiert."),
    "k3_deception_repl": "haelt Richtung (+, vz-z > 2) auf frischen Deck-Baenken",
    "raise_narrow_repl": "haelt Richtung; Dosis 1.0 >= 0.5; Kanal bleibt ~1%",
    "kombi_r5": ("~Summe der Einzeleffekte (disjunkte Knoten: Turn-Bet-Seite / "
                 "Turn-Defense+Slowplay / Raise-Facing); Interaktions-Verlust "
                 "moeglich (Slowplay unterdrueckt turn_wert-Bets: BEOBACHTEN)."),
}


def _journal_all() -> None:
    from pokerbot.autogym.improver import _journal
    for regel, erw in ERWARTUNGEN.items():
        _journal({"typ": "R5B-VORREGISTRIERUNG", "regel": regel, "erwartung": erw})
    _journal({"typ": "R5-INTERPRETATION", "regel": "sel_all_m15",
              "befund": "0 divergente Decks auf 29.920 — Turn/River-Rettungskanal bei "
                        "m15 LEER; das alte Verdikt 'v2/sel_all abgelehnt' wird zu "
                        "'kein Kanal', nicht 'refutiert'."})
    _journal({"typ": "R5-INTERPRETATION", "regel": "prince",
              "befund": "delta -68 roh vs GTOBaseline = exploit-OFF-Kanal-Artefakt "
                        "(Referenz exploitet den schwachen Gegner, der Arm nicht); "
                        "KEIN Urteil ueber PRINCE vs GTOW."})


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    workers = max(1, mp.cpu_count() - 2)
    from pokerbot.autogym import runs
    from pokerbot.autogym.improver import _journal
    from pokerbot.autogym.pargate import par_gate
    from pokerbot.autogym.stats import robust_stats, verdikt

    t0 = time.time()
    d = runs.neuer_run("runde5b_replikation", {"workers": workers})
    _journal_all()
    ergebnis: dict = {}

    # ---- 1: turn_wert-Replikationen (frische Deck-Baenke) ----
    for lauf, ds0 in (("r2", 40000), ("r3", 80000)):
        print(f"== turn_wert {lauf} vs sel_m15 (30k, Deck-Bank {ds0}) ==", flush=True)
        r = par_gate("turn_wert", 30000, workers, deck_seed0=ds0, incumbent="sel_m15")
        edges = r.pop("edges")
        (d / f"edges_turn_wert_{lauf}.json").write_text(json.dumps(edges), encoding="utf-8")
        ergebnis[f"turn_wert_{lauf}"] = r
        _journal({"typ": "R5B-GATE", "lauf": lauf, **r})
        print(r, flush=True)

    # ---- 2: envgate Runde 2+3 (frische Deck-Baenke, inkl. Kombi) ----
    arme = "k3_deception,turn_def_adv,raise_narrow_05,raise_narrow_10,kombi_r5"
    for ds0 in (25000, 45000):
        print(f"== envgate @12k, Deck-Bank {ds0} ==", flush=True)
        subprocess.run([sys.executable, "-m", "pokerbot.autogym.envgate",
                        "--decks", "12000", "--workers", str(workers),
                        "--arme", arme, "--deck-seed0", str(ds0)], check=True)

    # ---- 3: Orakel-Duell (Nebenwirkungs-Panel) ----
    print("== orakel_duell turn_wert vs sel_m15 (1500 Decks) ==", flush=True)
    subprocess.run([sys.executable, "-m", "pokerbot.autogym.orakel_duell",
                    "--kandidat", "turn_wert", "--decks", "1500",
                    "--workers", str(workers)], check=True)

    # ---- 4: Pooling turn_wert ueber die 3 Laeufe ----
    r5 = sorted(Path("data/runs").glob("*runde5_sweep"))[-1]
    alle = json.loads((r5 / "edges_turn_wert.json").read_text())
    for lauf in ("r2", "r3"):
        alle += json.loads((d / f"edges_turn_wert_{lauf}.json").read_text())
    rs = robust_stats(alle)
    ergebnis["turn_wert_gepoolt"] = {**rs, "verdict": verdikt(rs)}
    _journal({"typ": "R5B-POOL", "regel": "turn_wert_3x30k", **rs,
              "verdict": verdikt(rs)})
    print(f"turn_wert GEPOOLT (3x30k): {rs['bb100']:+.2f} +- {rs['se']:.2f} | "
          f"nz {rs['nonzero']} ({rs['nonzero_anteil']*100:.1f}%) "
          f"vz-z {rs['vorzeichen_z']:+.1f} -> {verdikt(rs)}", flush=True)

    (d / "ergebnis.json").write_text(json.dumps(ergebnis, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    runs.schliesse_run(d, {"typ": "runde5b", "status": "FERTIG",
                           "minuten": round((time.time() - t0) / 60, 1),
                           "turn_wert_gepoolt": {k: rs[k] for k in
                                                 ("bb100", "se", "vorzeichen_z", "nonzero")}})
    print(f"RUNDE 5b FERTIG in {(time.time()-t0)/60:.0f} min — Ablage {d}", flush=True)


if __name__ == "__main__":
    main()
