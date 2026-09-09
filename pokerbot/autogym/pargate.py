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
              "r9_play", "r9_pre", "r9_turn", "r9_v8",
              # Runde 10 (v9 ERNTE-Build, HU_OPTIMAL_KARTE A1/A2): Play tief
              # (Trigger 15bb, fp16, Solver-Sizes) + stackoff-Haertung.
              "r10_ernte",
              # v10 (docs/V10_BUILD_CARD.md, Arm B): r8_stack-Kette, aber der
              # hand-abhaengige river_gpu_guard ist durch den OEFFENTLICHEN
              # River-Plan (K2, K1-Hero-Range) ersetzt. GPU-Arm.
              "r10_stack",
              # v10.0-Patch (User 2026-09-10, "schnell v10 patchen"): H0-LITE. Identisch zu r10_stack,
              # aber der Plan sitzt auf der VOLLSTAENDIGEN v5-Kette (r8_stack) statt auf r8-ohne-Chirurgie.
              # WARUM: der dokumentierte Katastrophenherd war der Fallback in Plan-Pots — er liess
              # river_gpu_guard (feuert ab Pot 3000) weg, also genau in den grossen Poetten
              # (docs/V10_GATES_REPORT.md, Re-Release-Punkt "K2-Fallback auf r8-Chirurgie").
              "r10_h0")

# K2-Kanal (V10_BUILD_CARD E4/E5): im Gym feste Iterationen + deterministischer
# private_seed aus (hand_id, Sitz); live zusaetzlich die 7,5-s-Zeit-Deadline und
# os.urandom-Seed. Der Trace-Pfad kommt aus der Env (K5 setzt ihn je Chunk);
# im pargate-Worker ist die Env POKERB_*-frei -> kein Trace, deterministisch.
K2_LIVE_DEADLINE_S = 12.0   # G2 2026-09-08: K1-Range (bis 5,7 s) + Solve (2,5 s) sprengten 7,5 s; Harness hat keinen Timeout (V10_FAKTEN A8)
K2_TRACE_ENV = "POKERB_K2_TRACE"
K2_KANAELE = ("gym", "live")


def _k2_kanal_kw(kanal: str) -> dict:
    """Kanal-Parameter fuer river_plan_guard (nur der r10_stack-Aufbau liest sie)."""
    import os
    if kanal not in K2_KANAELE:
        raise ValueError(f"kanal muss in {K2_KANAELE} liegen: {kanal!r}")
    kw = {"modus": kanal, "trace_pfad": os.environ.get(K2_TRACE_ENV) or None}
    if kanal == "live":
        kw["deadline_s"] = K2_LIVE_DEADLINE_S
    return kw


def _wickle(name: str, basis, kanal: str = "gym"):
    """Legt den benannten Guard-Stack um eine FERTIGE Strategie-Fabrik.
    kanal ('gym' | 'live') erreicht nur K2-Arme (r10_stack): Live-Kanaele
    (auslese.wickle_decide) bekommen Deadline + os.urandom-Seed, das Gate
    bleibt deterministisch.
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
    if name == "r10_ernte":
        # v9-Kandidat (HU_OPTIMAL_KARTE): die OVERFOLD/SIZE-Ernte sitzt in
        # 8-30bb-Poetten -> Trigger 15bb; fp16 (+64%) traegt das Latenz-Budget.
        from pokerbot.autogym.improver import river_play_guard, river_wert_bremse
        from pokerbot.autogym.preflop_guards import stackoff_bremse
        kern = river_play_guard(river_wert_bremse(_wickle("r6_button", basis)),
                                min_pot_chips=1500, iters=150, half=True)
        return stackoff_bremse(kern)
    if name == "r10_stack":
        # v10 Arm B (Karte 'Arme', E1/E7): dieselbe Kette wie r8_stack darunter
        # (r6_button + wert_bremse); statt der hand-abhaengigen GPU-Chirurgie
        # spielt in Plan-Pots (pot_river >= 1500 = 15 bb, oeffentlich am
        # River-Beginn) der EINE River-Plan je Hand (RiverCFRBatch direkt, fp32,
        # 150 Iter, K1-Hero-Range; Basis wird dort NICHT gerufen). Unterhalb
        # der Schwelle bleibt alles r8-identisch bis auf den fehlenden
        # river_gpu_guard (der erst ab pot 3000 feuerte).
        from pokerbot.autogym.improver import river_wert_bremse
        from pokerbot.autogym.river_plan import river_plan_guard
        return river_plan_guard(river_wert_bremse(_wickle("r6_button", basis)),
                                min_pot_chips=1500, iters=150, **_k2_kanal_kw(kanal))
    if name == "r10_h0":
        # H0-LITE: Plan, sonst UNVERAENDERTES produktives v5 (inkl. river_gpu_guard) je Entscheidung.
        # Ein Fallback (offtree/deadline/hand_not_in_range/fehler) landet damit nie unter dem Champion.
        from pokerbot.autogym.river_plan import river_plan_guard
        return river_plan_guard(_wickle("r8_stack", basis),
                                min_pot_chips=1500, iters=150, **_k2_kanal_kw(kanal))
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
    from pokerbot.benchmark.duplicate import HAND_ID_STRIDE_JE_DECKSEED, duplicate_ab, gen_decks
    decks = gen_decks(n_decks, seed=deck_seed)
    # hand_id je Lauf eindeutig (E4): Adressraum je Deck-Block = deck_seed * Stride.
    _, _, edges = duplicate_ab(_baue_fabrik(kandidat, seed), _baue_fabrik(incumbent, seed),
                               decks, return_edges=True,
                               hand_id_basis=deck_seed * HAND_ID_STRIDE_JE_DECKSEED)
    return job_idx, edges


def _block_datei(kandidat: str, incumbent: str, seed: int, deck_seed0: int,
                 chunk: int, idx: int):
    """Ablageort eines fertigen Job-Blocks. Der Name traegt ALLE Groessen, die
    das Ergebnis bestimmen — ein Block darf nur wiederverwendet werden, wenn
    Arme, Seeds und Blockgroesse exakt uebereinstimmen."""
    from pathlib import Path
    d = Path("data/_pargate_blocks") / f"{kandidat}__vs__{incumbent}__s{seed}__b{deck_seed0}__c{chunk}"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"job{idx:03d}.json"


def par_gate(kandidat: str, n_decks: int, workers: int, seed: int = 1,
             deck_seed0: int = 1000, incumbent: str = "basis") -> dict:
    """Gepaartes Gate, parallelisiert. Deck-Bloecke disjunkt via deck_seed0+i.

    FORTSETZBAR (2026-09-01): jeder fertige Job-Block wird sofort auf Platte
    geschrieben; ein Neustart mit identischen Parametern ueberspringt bereits
    berechnete Bloecke. Die Bloecke sind deterministisch (fester seed + eigener
    deck_seed je Job), ein fortgesetzter Lauf ist deshalb byte-gleich zum
    durchgelaufenen. Grund: ein abgebrochener 30k-Lauf verlor bisher ALLES
    (18.125 Decks am 2026-08-31)."""
    import json as _json
    # Feinere Chunks (4 je Worker) + imap_unordered = laufender Fortschritt statt
    # Blackbox bis zum Ende; kostet nichts, macht ETA moeglich.
    n_jobs = workers * 4
    chunk = max(1, n_decks // n_jobs)
    t0 = time.time()
    # DECK-ORDNUNG (Niveau-Audit Rang 14): imap_unordered + extend zerstoerte das
    # Deck->Edge-Mapping — Bloecke werden per Job-Index geordnet zusammengesetzt,
    # damit edges.json lauf- und arm-uebergreifend per Deck paarbar bleibt.
    bloecke: dict[int, list] = {}
    offen = []
    for i in range(n_jobs):
        p = _block_datei(kandidat, incumbent, seed, deck_seed0, chunk, i)
        if p.exists():
            try:
                bloecke[i] = _json.loads(p.read_text(encoding="utf-8"))
                continue
            except Exception:  # noqa: BLE001
                pass            # unlesbarer Block wird neu gerechnet
        offen.append((i, kandidat, seed, deck_seed0 + i, chunk, incumbent))
    if bloecke:
        print(f"  Fortsetzung: {len(bloecke)}/{n_jobs} Bloecke aus Zwischenstand "
              f"({sum(len(b) for b in bloecke.values())} Decks), {len(offen)} offen", flush=True)
    if offen:
        with mp.Pool(workers) as pool:
            for k, (idx, blk) in enumerate(pool.imap_unordered(_worker, offen), 1):
                bloecke[idx] = blk
                _block_datei(kandidat, incumbent, seed, deck_seed0, chunk, idx).write_text(
                    _json.dumps(blk), encoding="utf-8")
                el = time.time() - t0
                n_fertig = sum(len(b) for b in bloecke.values())
                # Zwischenstand in bb/100: der laufende Lauf ist nicht mehr blind
                lauf = [e for b in bloecke.values() for e in b]
                # Skala wie stats.robust_stats: 1/2 Haende-pro-Deck / bb * 100
                zwischen = sum(lauf) / max(1, len(lauf)) * (1.0 / 2.0 / 100.0 * 100.0)
                print(f"  [{k}/{len(offen)}] {n_fertig} Decks | {el/60:.1f} min | "
                      f"ETA {el/k*(len(offen)-k)/60:.1f} min | Zwischenstand "
                      f"{zwischen:+.2f} bb/100", flush=True)
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
