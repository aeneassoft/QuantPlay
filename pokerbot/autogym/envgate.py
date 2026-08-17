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

# Arm-Name -> exakte Env-Flags. 'referenz' ist der Pflicht-Nullarm.
ARME: dict[str, dict] = {
    "referenz": {},
    # Das komplette live-validierte v2.2-Profil (-19,70 AIVAT, n=2393):
    "prince": {"POKERB_PRINCE": "1"},
    # Nur die K3-Gegenmittel (transparente Check-Range / Turn-Overfold vs Stabs):
    "k3_deception": {"POKERB_TURN_DEFENSE": "0.07", "POKERB_SLOWPLAY": "0.25"},
    # Der Turn-Kopf des Defense-Advisors (v5C: Analyzer -1,87, Self-Play offen):
    "turn_def_adv": {"POKERB_TURN_DEF_ADVISOR": "1"},
    # Geminte GTOW-Raise-Range-Komposition (v3.3-Flag, hier resolver-OFF-Kanal):
    "raise_narrow_05": {"POKERB_RAISE_NARROW": "0.5"},
    "raise_narrow_10": {"POKERB_RAISE_NARROW": "1.0"},
}


def _worker(args: tuple) -> tuple:
    idx, deck_seed, n_decks, seed = args
    try:
        import torch
        torch.set_num_threads(1)
    except Exception:  # noqa: BLE001
        pass
    from pokerbot.strategy.gto_mode import apply
    apply()                                  # materialisiert PRINCE/GTO-Mode, no-op sonst
    import pokerbot.strategy.bot as botmod
    botmod.EQUITY_ITERS = 120                # in allen Armen gleich -> kuerzt sich im Delta
    from pokerbot.autogym.improver import sel_guard
    from pokerbot.benchmark.duplicate import duplicate_ab, gen_decks, gto, pokerbot

    kandidat = sel_guard(                    # der amtierende Wrapper-Stand als Traeger
        pokerbot(exploit=os.environ.get("POKERB_EXPLOIT", "1") != "0", seed=seed,
                 use_resolver=False, use_turn_resolver=False),
        margin=0.15)
    decks = gen_decks(n_decks, seed=deck_seed)
    _, _, edges = duplicate_ab(kandidat, gto(1), decks, return_edges=True)
    return idx, edges


def _arm_lauf(n_decks: int, workers: int, seed: int, out: str) -> None:
    """Kind-Prozess: geordnete per-Deck-Edges des (env-konfigurierten) Kandidaten
    vs GTOBaseline. Deck-Bloecke deterministisch aus dem Job-Index -> jede
    Arm-Instanz spielt exakt dieselben Decks in derselben Reihenfolge."""
    n_jobs = workers * 4
    chunk = max(1, n_decks // n_jobs)
    jobs = [(i, 5000 + i, chunk, seed) for i in range(n_jobs)]
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
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    if args.arm_lauf:                        # Kind-Invokation (Env steht schon)
        _arm_lauf(args.decks, args.workers, args.seed, args.out)
        return

    from pokerbot.autogym import runs
    from pokerbot.autogym.stats import robust_stats, verdikt
    arme = ["referenz"] + [a.strip() for a in args.arme.split(",") if a.strip()]
    d = runs.neuer_run("envgate", {**vars(args), "arme": arme})
    edges_je_arm: dict[str, list] = {}
    for arm in arme:
        out = d / f"edges_{arm}.json"
        env = {k: v for k, v in os.environ.items() if not k.startswith("POKERB_")}
        env.update({"PYTHONUTF8": "1", "PYTHONHASHSEED": "0"})
        env.update(ARME[arm])
        print(f"[{arm}] {args.decks} Decks vs GTOBaseline, Env={ARME[arm]} ...", flush=True)
        subprocess.run([sys.executable, "-m", "pokerbot.autogym.envgate",
                        "--arm-lauf", arm, "--decks", str(args.decks),
                        "--workers", str(args.workers), "--seed", str(args.seed),
                        "--out", str(out)], env=env, check=True)
        edges_je_arm[arm] = json.loads(out.read_text(encoding="utf-8"))["edges"]

    ref = edges_je_arm["referenz"]
    ergebnis = {}
    for arm in arme:
        if arm == "referenz":
            continue
        deltas = [a - r for a, r in zip(edges_je_arm[arm], ref)]
        rs = robust_stats(deltas)
        ergebnis[arm] = {**rs, "verdict": verdikt(rs), "env": ARME[arm]}
        print(f"{arm:16s} delta {rs['bb100_trim']:+.2f} +- {rs['se_trim']:.2f} bb/100 "
              f"(roh {rs['bb100']:+.2f} +- {rs['se']:.2f}) -> {ergebnis[arm]['verdict']}")
    runs.schliesse_run(d, {"typ": "envgate", "n_decks": args.decks, "arme": ergebnis})
    print(f"Run-Ablage: {d}")


if __name__ == "__main__":
    main()
