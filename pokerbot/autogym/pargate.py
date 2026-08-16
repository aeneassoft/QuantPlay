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
KANDIDATEN = ("mdf_guard", "podds_guard", "sel_guard", "sel_all", "lizenz_guard", "auslese2", "basis")


def _baue_fabrik(name: str, seed: int):
    from pokerbot.autogym.improver import lizenz_guard, mdf_guard, podds_guard, sel_guard
    from pokerbot.benchmark.duplicate import pokerbot
    basis = pokerbot(exploit=True, seed=seed)
    if name == "basis":
        return basis
    if name == "mdf_guard":
        return mdf_guard(basis)
    if name == "podds_guard":
        return podds_guard(basis)
    if name == "sel_guard":
        return sel_guard(basis)
    if name == "lizenz_guard":
        return lizenz_guard(basis)
    if name == "sel_all":
        # B1: der bewiesene Mechanismus (+4,7 am Flop) auf Turn+River ausgeweitet.
        return sel_guard(basis, streets=("flop", "turn", "river"))
    if name == "auslese2":
        # B3: Call-Seite (alle Strassen) + Bet-Seite (Lizenz) = der v2-Kandidat.
        return lizenz_guard(sel_guard(basis, streets=("flop", "turn", "river")))
    raise ValueError(name)


def _worker(args: tuple) -> list:
    kandidat, seed, deck_seed, n_decks = args
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
    _, _, edges = duplicate_ab(_baue_fabrik(kandidat, seed), _baue_fabrik("basis", seed),
                               decks, return_edges=True)
    return edges


def par_gate(kandidat: str, n_decks: int, workers: int, seed: int = 1,
             deck_seed0: int = 1000) -> dict:
    """Gepaartes Gate, parallelisiert. Deck-Bloecke disjunkt via deck_seed0+i."""
    # Feinere Chunks (4 je Worker) + imap_unordered = laufender Fortschritt statt
    # Blackbox bis zum Ende; kostet nichts, macht ETA moeglich.
    n_jobs = workers * 4
    chunk = max(1, n_decks // n_jobs)
    jobs = [(kandidat, seed, deck_seed0 + i, chunk) for i in range(n_jobs)]
    t0 = time.time()
    edges = []
    with mp.Pool(workers) as pool:
        for k, blk in enumerate(pool.imap_unordered(_worker, jobs), 1):
            edges.extend(blk)
            el = time.time() - t0
            print(f"  [{k}/{n_jobs}] {len(edges)} Decks | {el/60:.1f} min | "
                  f"ETA {el/k*(n_jobs-k)/60:.1f} min", flush=True)
    n = len(edges)
    mean = sum(edges) / n
    var = sum((e - mean) ** 2 for e in edges) / max(1, n - 1)
    bb100 = mean / 2 / 100 * 100
    se = (var ** 0.5 / n ** 0.5) / 2 / 100 * 100
    if bb100 - 2 * se > 0:
        verdict = "ANWENDEN"
    elif bb100 + 2 * se < -1.0:
        verdict = "VERWERFEN"
    else:
        verdict = "NEUTRAL"
    return {"kandidat": kandidat, "bb100": round(bb100, 2), "se": round(se, 2),
            "n_decks": n, "workers": workers, "sekunden": round(time.time() - t0, 1),
            "decks_pro_min": round(n / max(1e-9, time.time() - t0) * 60, 1),
            "verdict": verdict}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--kandidat", choices=KANDIDATEN, default="mdf_guard")
    ap.add_argument("--decks", type=int, default=1200)
    ap.add_argument("--workers", type=int, default=max(1, mp.cpu_count() - 2))
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--deck-seed0", type=int, default=1000)
    args = ap.parse_args()

    from pokerbot.autogym import runs
    d = runs.neuer_run(f"pargate_{args.kandidat}", vars(args))
    res = par_gate(args.kandidat, args.decks, args.workers, args.seed, args.deck_seed0)
    runs.schliesse_run(d, res)
    print(res)
    print(f"Run-Ablage: {d}")


if __name__ == "__main__":
    main()
