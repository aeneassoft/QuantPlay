"""RUNDE 5 — die Attacke-Kampagne (2026-08-17): der grosse Sweep auf dem
reparierten Messfundament (Spot-RNG-Seeding + sel_guard-streets-Fix + robuste SE).

Sequentielle Flotten (RAM-Regel: EINE Worker-Flotte zur Zeit). Phasen:
  0  A/A-Nulltest sel_m15 vs sel_m15 — die ABNAHME des Seeding-Fixes.
     Erwartung: JEDER per-Deck-Edge exakt 0; sonst Abbruch (Restquelle jagen).
  1  In-Prozess-Arme vs den Amtierenden (sel_m15), identische Decks je Arm:
     sel_all_m15, sel_turn_m15, turn_wert, wert_plus_all @ 30k Decks.
  2  Env-Arme via envgate (Subprozess-Paarung): prince, k3_deception,
     turn_def_adv, raise_narrow_05/10 @ 12k Decks.

Replikationen (3-Laeufe-Regel) und die Kombi-Montage entscheidet der Mensch
nach diesem Lauf — dieser Treiber misst, er tauft nicht.

  python -m pokerbot.autogym.runde5
"""
from __future__ import annotations

import json
import multiprocessing as mp
import subprocess
import sys
import time

# Vorregistrierte Erwartungen — geschrieben BEVOR die erste Messung laeuft.
ERWARTUNGEN = {
    "aa_nulltest": "exakt 0 auf jedem Deck (Seeding-Fix greift); sonst Abbruch",
    "sel_all_m15": ("KANALBREITE VORGEMESSEN (400 Decks, 2026-08-17): Turn-Fold-Spots 0/800"
                    " Haende (Mirror-Oekologie: die Basis bettet den Turn fast nie -- der"
                    " aelteste Leak macht den Verteidigungs-Kanal leer), River 0/15 flippt"
                    " bei m15. Erwartung: ~0 bis minimal; der Arm misst den River-Rest."),
    "turn_wert": ("KANALBREITE VORGEMESSEN: 40/800 Haende (5%) wuerden betten (208 Turn-"
                  "Checks, 60 starke Made Hands, 40 mit eq>=0,60 vs Tracker-Range). K3-Prior"
                  " +2..+4 (ungemessen); Bet-Seite historisch schwer (lizenz refutiert) --"
                  " aber WERT, kein Bluff. Der breiteste neue Kanal der Runde."),
    "wert_plus_all": "Kombi-Probe; erwartet ~Summe der Einzeleffekte falls disjunkte Knoten",
    "prince": ("UNBEKANNT in diesem Kanal: validiert vs GTOW (-19,70), nie im Self-Play/"
               "vs GTOBaseline-Delta. K3-Haertungs-These; Spew-Kanarienvogel."),
    "k3_deception": "wie prince, isoliert auf TURN_DEFENSE+SLOWPLAY",
    "turn_def_adv": "v5C-Historie: Analyzer -1,87 (resolver-OFF); dieser Kanal offen",
    "raise_narrow": "v3.3 Analyzer-refutiert; resolver-OFF-Kanal offen (Jam-Fix-These K4)",
}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    workers = max(1, mp.cpu_count() - 2)
    from pokerbot.autogym import runs
    from pokerbot.autogym.improver import _journal
    from pokerbot.autogym.pargate import par_gate

    t0 = time.time()
    d = runs.neuer_run("runde5_sweep", {"workers": workers, "phase1_decks": 30000,
                                        "phase2_decks": 12000})
    for regel, erw in ERWARTUNGEN.items():
        _journal({"typ": "R5-VORREGISTRIERUNG", "regel": regel, "erwartung": erw})
    ergebnis: dict = {}

    # ---- Phase 0: A/A-Nulltest (die Abnahme von Stufe 0) ----
    print("== Phase 0: A/A-Nulltest sel_m15 vs sel_m15 (2000 Decks) ==", flush=True)
    aa = par_gate("sel_m15", 2000, workers, incumbent="sel_m15")
    aa_edges = aa.pop("edges")
    aa["max_abs_edge"] = max(abs(e) for e in aa_edges) if aa_edges else -1
    ergebnis["aa_nulltest"] = aa
    _journal({"typ": "R5-AA-NULLTEST", **{k: aa[k] for k in
              ("bb100", "se", "n_decks", "max_abs_edge") if k in aa}})
    print(f"A/A: max |edge| = {aa['max_abs_edge']}", flush=True)
    if aa["max_abs_edge"] != 0:
        print("!! A/A NICHT exakt null — Restquelle von Nichtdeterminismus. ABBRUCH.", flush=True)
        (d / "ergebnis.json").write_text(json.dumps(ergebnis, ensure_ascii=False, indent=1),
                                         encoding="utf-8")
        runs.schliesse_run(d, {"typ": "runde5", "status": "ABBRUCH-AA",
                               "max_abs_edge": aa["max_abs_edge"]})
        return

    # ---- Phase 1: In-Prozess-Arme vs sel_m15 ----
    # sel_turn_m15 GESTRICHEN vor der Messung: Kanalbreite 0/800 Haende (s.o.).
    for arm in ("sel_all_m15", "turn_wert", "wert_plus_all"):
        print(f"== Phase 1: {arm} vs sel_m15 (30k Decks) ==", flush=True)
        r = par_gate(arm, 30000, workers, incumbent="sel_m15")
        edges = r.pop("edges")
        (d / f"edges_{arm}.json").write_text(json.dumps(edges), encoding="utf-8")
        ergebnis[arm] = r
        _journal({"typ": "R5-GATE", **r})
        print(r, flush=True)

    # ---- Phase 2: Env-Arme (eigene Run-Ablage im envgate) ----
    print("== Phase 2: envgate (prince/k3/turn_def_adv/raise_narrow) ==", flush=True)
    subprocess.run([sys.executable, "-m", "pokerbot.autogym.envgate",
                    "--decks", "12000", "--workers", str(workers)], check=True)

    (d / "ergebnis.json").write_text(json.dumps(ergebnis, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    kurz = {k: {kk: v[kk] for kk in ("bb100_trim", "se_trim", "verdict") if kk in v}
            for k, v in ergebnis.items() if k != "aa_nulltest"}
    runs.schliesse_run(d, {"typ": "runde5", "status": "FERTIG",
                           "minuten": round((time.time() - t0) / 60, 1), "arme": kurz})
    print(f"RUNDE 5 FERTIG in {(time.time()-t0)/60:.0f} min — Ablage {d}", flush=True)


if __name__ == "__main__":
    main()
