"""ORAKEL-DUELL — die Mathematik-Benchmark als ZWEITES Instrument im Gate.

pargate misst Chips (Instrument 2/3); dieses Werkzeug haelt dieselben Arme
gegen das Orakel (Instrument 1): Kandidat und Amtierender spielen dieselben
Decks mit Sitz-Tausch, JEDE Entscheidung wird gegradet und der jeweiligen
STRATEGIE zugebucht. Ergebnis: L/F-Klassenraten je 1000 Entscheidungen im
direkten Arm-Vergleich — z.B. muss turn_wert die W1-4-Klasse `verpasster_wert`
druecken, OHNE `bet_braucht_unplausible_folds` zu heben.

Zusaetzlich der ERSTE Konsument von runs.entscheidungs_logger (Sweep-Befund
2026-08-17: 0 Aufrufer): alle geflaggten Entscheidungen + 3%-Sample landen mit
Strategie-Label als decisions.jsonl.gz im Run-Ordner (Lead-Mining/SFT-Gold).

  python -m pokerbot.autogym.orakel_duell --kandidat turn_wert --decks 1500
"""
from __future__ import annotations

import argparse
import multiprocessing as mp
import sys
import time
from collections import Counter


def _worker(args: tuple) -> tuple:
    kandidat, incumbent, seed, deck_seed, n_decks = args
    try:
        import torch
        torch.set_num_threads(1)
    except Exception:  # noqa: BLE001
        pass
    from pokerbot.autogym import oracle as orc
    from pokerbot.autogym.pargate import _baue_fabrik
    from pokerbot.benchmark.duplicate import _setup_fixed, gen_decks
    from pokerbot.engine.game import HeadsUpGame

    decks = gen_decks(n_decks, seed=deck_seed)
    g = HeadsUpGame(names=("S0", "S1"), starting_stack=20000, sb=50, bb=100, seed=0)
    reps = {kandidat: orc.OracleReport(), incumbent: orc.OracleReport()}
    # GELEGENHEITS-Zaehler (adversarisches Review W1-4: Raten je 1000 Gesamt-
    # Entscheidungen sind arm-vergleichs-untauglich, weil ein bettender Arm die
    # Handlaengen aendert — normiert wird je ELIGIBLE Knoten, Strassen getrennt).
    geleg = {kandidat: Counter(), incumbent: Counter()}
    rows: list = []

    def spiel(fab_a, name_a, fab_b, name_b, h0, h1, board):
        _setup_fixed(g, h0, h1, board, 0, 20000)
        d = {0: (fab_a(0), name_a), 1: (fab_b(1), name_b)}
        guard = 0
        while not g.hand_over:
            st = g.state()
            seat = st["to_act"]
            dec_fn, strat = d[seat]
            a, amt = dec_fn(st)
            me, opp = st["players"][seat], st["players"][1 - seat]
            to_call = max(0, st["current_bet"] - me["committed_street"])
            rec = {"street": st["street"], "pot": st["pot"], "to_call": to_call,
                   "action": a, "amount": amt, "hero_hole": me["hole"],
                   "board": st["board"], "villain_hole": opp["hole"],
                   "call_closes_action": opp["all_in"] or to_call >= me["stack"],
                   "effective_stack": min(me["stack"], opp["stack"]), "n_opponents": 1}
            if st["street"] in ("turn", "river"):
                if to_call <= 0:
                    geleg[strat][f"check_gelegenheit_{st['street']}"] += 1
                else:
                    geleg[strat][f"facing_bet_{st['street']}"] += 1
            n_l, n_p = len(reps[strat].leads), len(reps[strat].provable)
            geflaggt = orc.grade_decision(reps[strat], rec, bb=100)
            if geflaggt:
                neu = reps[strat].leads[n_l:] + reps[strat].provable[n_p:]
                rows.append({**rec, "strategie": strat, "regeln": [v.rule for v in neu]})
            g.act(a, amt)
            guard += 1
            if guard > 500:
                break

    fk = lambda: _baue_fabrik(kandidat, seed)      # noqa: E731 — je Spiel frische Fabrik
    fi = lambda: _baue_fabrik(incumbent, seed)     # noqa: E731
    for h0, h1, board in decks:
        spiel(fk(), kandidat, fi(), incumbent, h0, h1, board)   # Kandidat Sitz 0
        spiel(fi(), incumbent, fk(), kandidat, h0, h1, board)   # Sitz-Tausch
    aus = {}
    for name, rep in reps.items():
        orc.finalize_frequencies(rep)          # F-Stufe (mdf_flop etc.) je Strategie
        aus[name] = {"decisions": rep.decisions,
                     "gelegenheiten": dict(geleg[name]),
                     "regeln": dict(Counter(v.rule for v in rep.leads + rep.provable + rep.freq)),
                     "severity": {r: round(sum(v.severity_bb for v in rep.leads if v.rule == r), 1)
                                  for r in {v.rule for v in rep.leads}}}
    return aus, rows[:400]


def duell(kandidat: str, incumbent: str, n_decks: int, workers: int,
          seed: int = 1, deck_seed0: int = 1000) -> dict:
    n_jobs = workers * 4
    chunk = max(1, n_decks // n_jobs)
    jobs = [(kandidat, incumbent, seed, deck_seed0 + i, chunk) for i in range(n_jobs)]
    t0 = time.time()
    gesamt = {kandidat: Counter(), incumbent: Counter()}
    sev = {kandidat: Counter(), incumbent: Counter()}
    dez = {kandidat: 0, incumbent: 0}
    geleg = {kandidat: Counter(), incumbent: Counter()}
    alle_rows: list = []
    with mp.Pool(workers) as pool:
        for k, (aus, rows) in enumerate(pool.imap_unordered(_worker, jobs), 1):
            for name, a in aus.items():
                gesamt[name].update(a["regeln"])
                sev[name].update(a["severity"])
                dez[name] += a["decisions"]
                geleg[name].update(a["gelegenheiten"])
            alle_rows.extend(rows)
            el = time.time() - t0
            print(f"  [{k}/{n_jobs}] {el/60:.1f} min | ETA {el/k*(n_jobs-k)/60:.1f} min",
                  flush=True)
    out = {"kandidat": kandidat, "incumbent": incumbent, "n_decks": n_decks}
    for name in (kandidat, incumbent):
        g = geleg[name]
        # Zielklassen je ELIGIBLE Gelegenheit (arm-vergleichstauglich); alles
        # andere je 1000 Entscheidungen (Nebenwirkungs-Panel).
        je_geleg = {}
        for street in ("turn", "river"):
            n_g = g.get(f"check_gelegenheit_{street}", 0)
            je_geleg[f"verpasster_wert_{street}_je100"] = round(
                gesamt[name].get(f"verpasster_wert_{street}", 0) / max(1, n_g) * 100, 2)
            n_f = g.get(f"facing_bet_{street}", 0)
            je_geleg[f"verpasster_raise_{street}_basis"] = n_f
        je_geleg["verpasster_raise_je100_facing"] = round(
            gesamt[name].get("verpasster_raise", 0)
            / max(1, g.get("facing_bet_turn", 0) + g.get("facing_bet_river", 0)) * 100, 2)
        out[name] = {"decisions": dez[name], "gelegenheiten": dict(g),
                     "zielklassen_je_gelegenheit": je_geleg,
                     "rate_je_1000": {r: round(c / max(1, dez[name]) * 1000, 2)
                                      for r, c in sorted(gesamt[name].items())},
                     "severity_bb_summe": dict(sev[name])}
    return out, alle_rows


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--kandidat", default="turn_wert")
    ap.add_argument("--incumbent", default="sel_m15")
    ap.add_argument("--decks", type=int, default=1500)
    ap.add_argument("--workers", type=int, default=max(1, mp.cpu_count() - 2))
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()

    from pokerbot.autogym import runs
    d = runs.neuer_run(f"orakel_duell_{args.kandidat}", vars(args))
    res, rows = duell(args.kandidat, args.incumbent, args.decks, args.workers, args.seed)
    log, flush = runs.entscheidungs_logger(d)
    for r in rows:
        log(r, True)
    n_rows = flush()
    runs.schliesse_run(d, {"typ": "orakel_duell", **res, "geloggte_zeilen": n_rows})
    for name in (args.kandidat, args.incumbent):
        print(f"{name}: {res[name]['decisions']} Entscheidungen, "
              f"Raten/1000: {res[name]['rate_je_1000']}")
    print(f"Run-Ablage: {d}")


if __name__ == "__main__":
    main()
