"""ENV-PAAR-GATE — gepaarte Zwei-Lauf-Messung fuer IMPORT-Zeit-/Env-Flags.

Die PRINCE-/Profil-Flags sind Modul-Level-Konstanten (bot.py liest bei IMPORT)
und Env ist prozess-global — im pargate-Prozess bekaemen BEIDE Gate-Seiten das
Flag. Bauform hier (Muster research/duplicate_mode_ab.py, verallgemeinert):

  * Jeder ARM laeuft als SUBPROZESS mit hygienischem Env (alle POKERB_* des
    Parents gestrippt, dann exakt die Arm-Flags gesetzt) und spielt den
    Kandidaten-Stack [Arm-Flags + sel_guard(m15)-Wrapper = der amtierende
    AUSLESE-Stand] gegen die env-INSENSITIVE GTOBaseline auf IDENTISCHEN,
    GEORDNETEN Decks.
  * Der Parent bildet gepaarte per-Deck-Deltas Arm - Referenz (Referenz = leeres
    Env, derselbe Wrapper) mit robuster Statistik (stats.robust_stats).

EHRLICHE GRENZE (duplicate_mode_ab-Lektion, vorregistriert): gemessen wird vs
GTOBaseline, nicht vs den Amtierenden — ein Arm kann hier gewinnen und im
Self-Play neutral sein. Dieses Gate liefert Vorzeichen + Spew-Kanarienvogel;
die Self-Play-Wahrheit bleibt pargate, die externe Wahrheit der GTOW-Anker.

  python -m pokerbot.autogym.envgate --decks 12000                (alle Arme)
  python -m pokerbot.autogym.envgate --arme prince,k3_deception   (Auswahl)
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import subprocess
import sys
import time
from pathlib import Path

# Arm-Name -> {"env": Flags, "wrapper": pargate-KANDIDATEN-Name des Traeger-Stacks}.
# 'referenz' ist der Pflicht-Nullarm (leeres Env, amtierender Wrapper sel_m15).
ARME: dict[str, dict] = {
    "referenz": {"env": {}, "wrapper": "sel_m15"},
    # Das komplette live-validierte v2.2-Profil (-19,70 AIVAT, n=2393). ACHTUNG
    # Kanal-Artefakt gemessen (R5): exploit-OFF vs die exploitbare GTOBaseline
    # kostet -68 roh — der Arm sagt in DIESEM Kanal nichts ueber PRINCE vs GTOW.
    "prince": {"env": {"POKERB_PRINCE": "1"}, "wrapper": "sel_m15"},
    # Nur die K3-Gegenmittel (transparente Check-Range / Turn-Overfold vs Stabs):
    "k3_deception": {"env": {"POKERB_TURN_DEFENSE": "0.07", "POKERB_SLOWPLAY": "0.25"},
                     "wrapper": "sel_m15"},
    # Der Turn-Kopf des Defense-Advisors (v5C: Analyzer -1,87, Self-Play offen):
    "turn_def_adv": {"env": {"POKERB_TURN_DEF_ADVISOR": "1"}, "wrapper": "sel_m15"},
    # Geminte GTOW-Raise-Range-Komposition (v3.3-Flag, hier resolver-OFF-Kanal):
    "raise_narrow_05": {"env": {"POKERB_RAISE_NARROW": "0.5"}, "wrapper": "sel_m15"},
    "raise_narrow_10": {"env": {"POKERB_RAISE_NARROW": "1.0"}, "wrapper": "sel_m15"},
    # KOMBI-Kandidat Runde 5b: die drei positiven Kanaele gestapelt —
    # turn_wert-Wrapper + K3-Deception + Raise-Narrow 1.0.
    "kombi_r5": {"env": {"POKERB_TURN_DEFENSE": "0.07", "POKERB_SLOWPLAY": "0.25",
                         "POKERB_RAISE_NARROW": "1.0"}, "wrapper": "turn_wert"},
    # Attribution Runde 5c: NUR die zwei Einzel-Gate-Passierer (turn_wert 3x
    # Mirror-repliziert + RN10 3x envgate-repliziert), OHNE das nicht
    # replizierende K3 — klaert, ob K3 in der Kombi traegt oder schleppt.
    "kombi_schlank": {"env": {"POKERB_RAISE_NARROW": "1.0"}, "wrapper": "turn_wert"},
    # Der amtierende AUSLESE-v3-Stand als ARM (fuers kumulative Finale vs basis):
    "auslese_v3": {"env": {}, "wrapper": "sel_m15"},
}


def _worker(args: tuple) -> tuple:
    idx, deck_seed, n_decks, seed, wrapper = args
    import os
    for v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ[v] = "1"     # OpenBLAS-Init-Tod bei Default-Threads (Debug-Beweis 2026-08-17)
    try:
        import torch
        torch.set_num_threads(1)
    except Exception:  # noqa: BLE001
        pass
    from pokerbot.strategy.gto_mode import apply
    apply()                                  # materialisiert PRINCE/GTO-Mode, no-op sonst
    import pokerbot.strategy.bot as botmod
    botmod.EQUITY_ITERS = 120                # in allen Armen gleich -> kuerzt sich im Delta
    from pokerbot.autogym.pargate import _baue_fabrik
    from pokerbot.benchmark.duplicate import duplicate_ab, gen_decks, gto

    # Traeger-Stack identisch zum pargate-Kanal (gleicher Fabrik-Bauer). Hinweis:
    # ein exploit-OFF-Profil (PRINCE) greift hier NICHT auf den ctor-Param durch —
    # der prince-Arm traegt sein gemessenes Kanal-Artefakt ohnehin (s. ARME).
    kandidat = _baue_fabrik(wrapper, seed)
    decks = gen_decks(n_decks, seed=deck_seed)
    _, _, edges = duplicate_ab(kandidat, gto(1), decks, return_edges=True)
    return idx, edges


def _arm_lauf(n_decks: int, workers: int, seed: int, out: str, wrapper: str,
              deck_seed0: int) -> None:
    """Kind-Prozess: geordnete per-Deck-Edges des (env-konfigurierten) Kandidaten
    vs GTOBaseline. Deck-Bloecke deterministisch aus dem Job-Index -> jede
    Arm-Instanz spielt exakt dieselben Decks in derselben Reihenfolge."""
    n_jobs = workers * 4
    chunk = max(1, n_decks // n_jobs)
    jobs = [(i, deck_seed0 + i, chunk, seed, wrapper) for i in range(n_jobs)]
    t0 = time.time()
    bloecke: dict[int, list] = {}
    with mp.Pool(workers) as pool:
        for k, (idx, blk) in enumerate(pool.imap_unordered(_worker, jobs), 1):
            bloecke[idx] = blk
            el = time.time() - t0
            print(f"  [{k}/{n_jobs}] {sum(len(b) for b in bloecke.values())} Decks | "
                  f"{el/60:.1f} min | ETA {el/k*(n_jobs-k)/60:.1f} min", flush=True)
    edges = [e for i in range(n_jobs) for e in bloecke[i]]      # Ordnung wiederherstellen
    from pokerbot.strategy.gto_mode import fingerprint
    Path(out).write_text(json.dumps({"edges": edges, "fingerprint": fingerprint()}),
                         encoding="utf-8")
    print(f"Arm fertig: {len(edges)} Decks -> {out}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--decks", type=int, default=12000)
    ap.add_argument("--workers", type=int, default=max(1, mp.cpu_count() - 2))
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--arme", default=",".join(a for a in ARME if a != "referenz"))
    ap.add_argument("--arm-lauf", default="", help="intern: Kind-Modus, Arm-Name")
    ap.add_argument("--wrapper", default="sel_m15")
    ap.add_argument("--deck-seed0", type=int, default=5000)
    ap.add_argument("--referenz-wrapper", default="sel_m15",
                    help="Traeger-Stack des Nullarms (z.B. 'basis' fuers kumulative Finale)")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    if args.arm_lauf:                        # Kind-Invokation (Env steht schon)
        _arm_lauf(args.decks, args.workers, args.seed, args.out, args.wrapper,
                  args.deck_seed0)
        return

    from pokerbot.autogym import runs
    from pokerbot.autogym.stats import bootstrap_ci, robust_stats, verdikt
    # KANAL-VOKABULAR (Niveau-Audit Rang 5, v8-Praezedenz): dieser Kanal misst vs
    # GTOBaseline — sein Positiv ist SHIP-Evidenz-VORSTUFE, nie 'ANWENDEN'.
    KANAL_WORT = {"ANWENDEN": "KANAL_POSITIV", "VERWERFEN": "KANAL_NEGATIV",
                  "NEUTRAL": "KANAL_NEUTRAL"}
    arme = ["referenz"] + [a.strip() for a in args.arme.split(",") if a.strip()]
    ARME["referenz"] = {"env": {}, "wrapper": args.referenz_wrapper}
    d = runs.neuer_run("envgate", {**vars(args), "arme": arme})
    edges_je_arm: dict[str, list] = {}
    for arm in arme:
        out = d / f"edges_{arm}.json"
        env = {k: v for k, v in os.environ.items() if not k.startswith("POKERB_")}
        env.update({"PYTHONUTF8": "1", "PYTHONHASHSEED": "0", "OPENBLAS_NUM_THREADS": "1",
                    "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"})
        env.update(ARME[arm]["env"])
        print(f"[{arm}] {args.decks} Decks vs GTOBaseline, Env={ARME[arm]['env']}, "
              f"Wrapper={ARME[arm]['wrapper']} ...", flush=True)
        subprocess.run([sys.executable, "-m", "pokerbot.autogym.envgate",
                        "--arm-lauf", arm, "--decks", str(args.decks),
                        "--workers", str(args.workers), "--seed", str(args.seed),
                        "--wrapper", ARME[arm]["wrapper"],
                        "--deck-seed0", str(args.deck_seed0),
                        "--out", str(out)], env=env, check=True)
        edges_je_arm[arm] = json.loads(out.read_text(encoding="utf-8"))["edges"]

    ref = edges_je_arm["referenz"]
    ergebnis = {}
    for arm in arme:
        if arm == "referenz":
            continue
        deltas = [a - r for a, r in zip(edges_je_arm[arm], ref)]
        rs = robust_stats(deltas)
        rs.update(bootstrap_ci(deltas))
        ergebnis[arm] = {**rs, "verdict": KANAL_WORT[verdikt(rs)],
                         "kanal": "envgate_vs_gtobaseline", "arm_spec": ARME[arm]}
        print(f"{arm:16s} delta {rs['bb100']:+.2f} +- {rs['se']:.2f} bb/100 | "
              f"CI95 [{rs['ci95_lo']:+.2f},{rs['ci95_hi']:+.2f}] p={rs['perm_p']} | "
              f"nz {rs['nonzero']} ({rs['nonzero_anteil']*100:.1f}%) "
              f"vz-z {rs['vorzeichen_z']:+.1f} -> {ergebnis[arm]['verdict']}")
    runs.schliesse_run(d, {"typ": "envgate", "kanal": "envgate_vs_gtobaseline",
                           "n_decks": args.decks, "arme": ergebnis})
    print(f"Run-Ablage: {d}")


if __name__ == "__main__":
    main()
