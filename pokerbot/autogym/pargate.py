"""G5 — das parallele Gate: gepaarte A/B-Messung ueber alle CPU-Kerne.

Derselbe Code laeuft lokal (G5-Beweis) und auf dem Pod (R1/R2). Windows-spawn-
fest: Worker bauen ihre Strategie-Fabriken selbst aus einem NAMEN-Spec (Closures
sind nicht picklebar). Jeder Worker spielt einen disjunkten Deck-Block; die
per-Deck-Edges werden zusammengefuehrt -> bb100, SE wie in duplicate_ab.

  python -m pokerbot.autogym.pargate --kandidat mdf_guard --decks 1200 --workers 12
"""
from __future__ import annotations

import argparse
import multiprocessing as mp
import sys
import time

# Spec-Namen -> Fabrik-Bauer. Worker-seitig aufgeloest (picklefrei).
KANDIDATEN = ("mdf_guard", "podds_guard", "sel_guard", "sel_m06", "sel_m10", "sel_m15", "sel_m20",
              "einmal_guard", "sel_all", "lizenz_guard", "auslese2", "basis",
              # Runde 5 (2026-08-17): margen-gematchte streets-Arme (nach dem
              # sel_guard-streets-Fix ERSTMALS echt messbar) + Turn-Wert-Bet-Seite.
              "sel_all_m15", "sel_turn_m15", "turn_wert", "wert_plus_all",
              "r6_ecall", "r6_button",
              # Runde 7 (2026-08-30, GTOW-Nacht-2-Mine): Big-Pot-River-Defense +
              # Wert-Bremse, exakte Enumeration (RNG-frei), Inkremente auf r6_button.
              "r7_bill", "r7_wert", "r7_river",
              # Runde 8: GPU-Solver-Chirurgie (RiverCFRBatch; nur klare
              # Solver-Widersprueche in Big Pots). GPU-Arme: --workers <= 6!
              # r8_stack = der Versions-Kandidat: wert_bremse + GPU-Chirurgie.
              "r8_gpu", "r8_stack",
              # Runde 9 (v8-Bau): Solver-PLAY statt Chirurgie (deterministisch
              # spot-gehasht gesampelt, Mixing bleibt); GTOW-Replay netto
              # +278,6bb vs +66,9bb der Chirurgie. GPU-Arme: --workers <= 6!
              "r9_play", "r9_pre", "r9_turn", "r9_v8")


def _wickle(name: str, basis):
    """Legt den benannten Guard-Stack um eine FERTIGE Strategie-Fabrik.
    DIE EINE QUELLE der Stack-Komposition — Gate (unten) UND die Export-Kanaele
    (research/snowie_export + research/pokerstars_export) beziehen sie hier,
    damit nie wieder eine divergierende Kopie graded wird (der m0.03-Fork
    in pokerstars_export._auslese_um, behoben 2026-08-17)."""
    from pokerbot.autogym.improver import (einmal_guard, lizenz_guard, mdf_guard,
                                       podds_guard, sel_guard, turn_wert_guard)
    if name == "basis":
        return basis
    if name == "mdf_guard":
        return mdf_guard(basis)
    if name == "podds_guard":
        return podds_guard(basis)
    if name == "sel_guard":
        return sel_guard(basis)
    if name == "sel_m06":
        return sel_guard(basis, margin=0.06)   # Margen-Sweep (Snowie: 3pp zu locker)
    if name == "sel_m10":
        return sel_guard(basis, margin=0.10)
    if name == "sel_m15":
        return sel_guard(basis, margin=0.15)
    if name == "sel_m20":
        return sel_guard(basis, margin=0.20)   # Gradienten-Probe jenseits des Sweep-Rands
    if name == "einmal_guard":
        return einmal_guard(basis)
    if name == "lizenz_guard":
        return lizenz_guard(basis)
    if name == "sel_all":
        # B1: der bewiesene Mechanismus (+4,7 am Flop) auf Turn+River ausgeweitet.
        return sel_guard(basis, streets=("flop", "turn", "river"))
    if name == "auslese2":
        # B3: Call-Seite (alle Strassen) + Bet-Seite (Lizenz) = der v2-Kandidat.
        return lizenz_guard(sel_guard(basis, streets=("flop", "turn", "river")))
    # ---- Runde 5: alle Arme als INKREMENT auf dem Amtierenden (sel_m15) gebaut,
    # damit das Gate vs sel_m15 exakt den Zusatz-Effekt misst.
    if name == "sel_all_m15":
        return sel_guard(basis, margin=0.15, streets=("flop", "turn", "river"))
    if name == "sel_turn_m15":
        return sel_guard(basis, margin=0.15, streets=("flop", "turn"))
    if name == "turn_wert":
        return turn_wert_guard(sel_guard(basis, margin=0.15))
    if name == "r6_ecall":
        # Runde 6 (Fable): River-Station-Haertung AUF dem v4-Kern.
        from pokerbot.autogym.improver import river_ecall_guard
        return river_ecall_guard(_wickle("turn_wert", basis))
    if name == "r6_button":
        from pokerbot.autogym.improver import button_disziplin_guard
        return button_disziplin_guard(_wickle("turn_wert", basis))
    if name == "wert_plus_all":
        # Kombi-Probe: Call-Selektion alle Strassen + Turn-Wert-Bet-Seite.
        return turn_wert_guard(sel_guard(basis, margin=0.15, streets=("flop", "turn", "river")))
    if name == "r7_bill":
        from pokerbot.autogym.improver import river_bill_guard
        return river_bill_guard(_wickle("r6_button", basis))
    if name == "r7_wert":
        from pokerbot.autogym.improver import river_wert_bremse
        return river_wert_bremse(_wickle("r6_button", basis))
    if name == "r7_river":
        from pokerbot.autogym.improver import river_bill_guard, river_wert_bremse
        return river_wert_bremse(river_bill_guard(_wickle("r6_button", basis)))
    if name == "r8_gpu":
        from pokerbot.autogym.improver import river_gpu_guard
        return river_gpu_guard(_wickle("r6_button", basis))
    if name == "r8_stack":
        # Der Versions-Kandidat: GPU-Chirurgie ZULETZT (sie prueft auch die
        # wert_bremse-Checks), wert_bremse darunter, r6_button-Kette als Kern.
        from pokerbot.autogym.improver import river_gpu_guard, river_wert_bremse
        return river_gpu_guard(river_wert_bremse(_wickle("r6_button", basis)))
    if name == "r9_play":
        # Play statt Chirurgie: ersetzt river_gpu_guard im v5-Stack.
        from pokerbot.autogym.improver import river_play_guard, river_wert_bremse
        return river_play_guard(river_wert_bremse(_wickle("r6_button", basis)))
    if name == "r9_pre":
        # Preflop-Disziplin-Inkrement AUF dem Amtierenden (r8_stack).
        from pokerbot.autogym.preflop_guards import no_limp_guard, stackoff_bremse
        return stackoff_bremse(no_limp_guard(_wickle("r8_stack", basis)))
    if name == "r9_turn":
        # Turn-Chirurgie-Inkrement auf r8_stack; hoher Trigger (Latenz 12-14s).
        from pokerbot.autogym.turn_gpu import turn_gpu_guard
        return turn_gpu_guard(_wickle("r8_stack", basis), min_pot_chips=5000, iters=80)
    if name == "r9_v8":
        # Die v8-Komposition: stackoff_bremse aussen (Selfplay-stumm, 1
        # Trigger/400 Haende — reiner GTOW-Klasse-D-Guard), River-Play/
        # wert_bremse auf der r6_button-Kette. OHNE no_limp_guard (Mirror
        # -11,42 VERWERFEN: die Basis limpt ~39% der Buttons strategisch;
        # Limp-Streichung baut das Preflop-Spiel um) und OHNE turn_gpu_guard
        # (Replay 3/3904 = keine bilanzierbare Evidenz; beide bleiben
        # default-OFF-Arme fuer spaetere Runden).
        from pokerbot.autogym.improver import river_play_guard, river_wert_bremse
        from pokerbot.autogym.preflop_guards import stackoff_bremse
        kern = river_play_guard(river_wert_bremse(_wickle("r6_button", basis)))
        return stackoff_bremse(kern)
    raise ValueError(name)


def _baue_fabrik(name: str, seed: int):
    """Gate-Kanal: der benannte Stack um die duplicate-PokerBot-Basis (exploit=ON)."""
    from pokerbot.benchmark.duplicate import pokerbot
    return _wickle(name, pokerbot(exploit=True, seed=seed))


def _worker(args: tuple) -> tuple:
    job_idx, kandidat, seed, deck_seed, n_decks, incumbent = args
    # ENV-HYGIENE (Armee-Befund bestaetigt): geerbte Shell-POKERB_*-Flags wuerden
    # BEIDE Gate-Seiten still faerben — der sel-Kanal ist per Definition flag-frei.
    import os

    for v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ[v] = "1"     # OpenBLAS-Init-Tod bei Default-Threads (Debug-Beweis 2026-08-17)
    for k in [k for k in os.environ if k.startswith("POKERB_")]:
        os.environ.pop(k, None)
    # KRITISCH (gemessen 2026-08-16): ohne das spawnt JEDER Worker torch mit
    # Default-Intra-Op-Threads (= Kernzahl). 20 Worker x 24 Threads auf 24 Kernen
    # = Thrashing; die Skalierung bricht ein, obwohl alle Kerne 'busy' aussehen.
    try:
        import torch
        torch.set_num_threads(1)
    except Exception:  # noqa: BLE001
        pass
    from pokerbot.benchmark.duplicate import duplicate_ab, gen_decks
    decks = gen_decks(n_decks, seed=deck_seed)
    _, _, edges = duplicate_ab(_baue_fabrik(kandidat, seed), _baue_fabrik(incumbent, seed),
                               decks, return_edges=True)
    return job_idx, edges


def par_gate(kandidat: str, n_decks: int, workers: int, seed: int = 1,
             deck_seed0: int = 1000, incumbent: str = "basis") -> dict:
    """Gepaartes Gate, parallelisiert. Deck-Bloecke disjunkt via deck_seed0+i."""
    # Feinere Chunks (4 je Worker) + imap_unordered = laufender Fortschritt statt
    # Blackbox bis zum Ende; kostet nichts, macht ETA moeglich.
    n_jobs = workers * 4
    chunk = max(1, n_decks // n_jobs)
    jobs = [(i, kandidat, seed, deck_seed0 + i, chunk, incumbent) for i in range(n_jobs)]
    t0 = time.time()
    # DECK-ORDNUNG (Niveau-Audit Rang 14): imap_unordered + extend zerstoerte das
    # Deck->Edge-Mapping — Bloecke werden per Job-Index geordnet zusammengesetzt,
    # damit edges.json lauf- und arm-uebergreifend per Deck paarbar bleibt.
    bloecke: dict[int, list] = {}
    with mp.Pool(workers) as pool:
        for k, (idx, blk) in enumerate(pool.imap_unordered(_worker, jobs), 1):
            bloecke[idx] = blk
            el = time.time() - t0
            print(f"  [{k}/{n_jobs}] {sum(len(b) for b in bloecke.values())} Decks | {el/60:.1f} min | "
                  f"ETA {el/k*(n_jobs-k)/60:.1f} min", flush=True)
    edges = [e for i in range(n_jobs) for e in bloecke[i]]
    from pokerbot.autogym.stats import bootstrap_ci, robust_stats, verdikt
    rs = robust_stats(edges)
    rs.update(bootstrap_ci(edges))     # Verdikt v3: Bootstrap traegt bei duennen Kanaelen
    return {"kandidat": kandidat, "incumbent": incumbent, "kanal": "pargate_mirror", **rs,
            "workers": workers, "sekunden": round(time.time() - t0, 1),
            "decks_pro_min": round(len(edges) / max(1e-9, time.time() - t0) * 60, 1),
            "verdict": verdikt(rs), "edges": edges}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--kandidat", choices=KANDIDATEN, default="mdf_guard")
    ap.add_argument("--decks", type=int, default=1200)
    ap.add_argument("--workers", type=int, default=max(1, mp.cpu_count() - 2))
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--deck-seed0", type=int, default=1000)
    ap.add_argument("--incumbent", choices=KANDIDATEN, default="basis",
                    help="Gegenseite des Gates (Default: die eingefrorene Basis)")
    args = ap.parse_args()

    from pokerbot.autogym import runs
    d = runs.neuer_run(f"pargate_{args.kandidat}", vars(args))
    res = par_gate(args.kandidat, args.decks, args.workers, args.seed,
                   args.deck_seed0, args.incumbent)
    edges = res.pop("edges")                 # Rohdaten in den Run-Ordner, nie in die INDEX-Zeile
    import json as _json
    (d / "edges.json").write_text(_json.dumps(edges), encoding="utf-8")
    runs.schliesse_run(d, res)
    print(res)
    print(f"Run-Ablage: {d}")


if __name__ == "__main__":
    main()
