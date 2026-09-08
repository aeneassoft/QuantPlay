# -*- coding: utf-8 -*-
"""G5-Katastrophen-Obduktion: einzelne Decks eines pargate-Spiegels EXAKT nachspielen.

Rekonstruiert aus dem globalen Deck-Index (Position in edges.json) den pargate-Job
(deck_seed = deck_seed0 + job, Deck idx im Block, hand_id = deck_seed*Stride + idx),
spielt beide Spiegelhaelften mit denselben Fabriken wie pargate._worker (POKERB_*
gestrippt, 1 Thread, exploit ON, Resolver AUS = Gym-Kanal) und druckt Holes, Board,
Aktionsfolge und Ergebnis je Haelfte. Der Replay-Edge MUSS dem Eintrag in edges.json
gleichen (Determinismus-Kontrolle); bei Abweichung wird das ausgewiesen.

  python -m research.g5_deck_replay data/runs/<ts>_pargate_r10_stack 1226 336 1308
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")
for _k in [k for k in os.environ if k.startswith("POKERB_")]:
    os.environ.pop(_k, None)

BB_CHIPS = 100


def _aktionen(history: list) -> str:
    teile = []
    for ev in history:
        if ev.get("action") == "deal":
            teile.append(f"| {ev['street']} {' '.join(ev['board'])} |")
        elif ev["action"] in ("bet", "raise"):
            teile.append(f"P{ev['player']} {ev['action']}->{ev['to']}")
        elif ev["action"] == "call":
            teile.append(f"P{ev['player']} call {ev.get('amount', '')}")
        else:
            teile.append(f"P{ev['player']} {ev['action']}")
    return "  ".join(teile)


def replay(run_dir: Path, deck_global: int) -> dict:
    import torch
    torch.set_num_threads(1)
    from pokerbot.autogym.pargate import _baue_fabrik
    from pokerbot.benchmark.duplicate import (HAND_ID_STRIDE_JE_DECKSEED, _play_hand, _setup_fixed,
                                              gen_decks)
    from pokerbot.engine.game import HeadsUpGame

    cfg = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    edges = json.loads((run_dir / "edges.json").read_text(encoding="utf-8"))
    n_jobs = cfg["workers"] * 4
    chunk = max(1, cfg["decks"] // n_jobs)
    job, idx = divmod(deck_global, chunk)
    deck_seed = cfg["deck_seed0"] + job
    h0, h1, board = gen_decks(chunk, seed=deck_seed)[idx]
    hand_id = deck_seed * HAND_ID_STRIDE_JE_DECKSEED + idx
    make_a = _baue_fabrik(cfg["kandidat"], cfg["seed"])
    make_b = _baue_fabrik(cfg["incumbent"], cfg["seed"])
    start = 20000
    g = HeadsUpGame(names=("S0", "S1"), starting_stack=start, sb=50, bb=100, seed=0)
    t0 = time.time()
    haelften = []
    for (d0, d1, wer0) in ((make_a(0), make_b(1), cfg["kandidat"]), (make_b(0), make_a(1), cfg["incumbent"])):
        _setup_fixed(g, h0, h1, board, 0, start)
        x = _play_hand(g, d0, d1, start, hand_id)
        haelften.append({"seat0": wer0, "seat0_netto_chips": x, "aktionen": _aktionen(list(g.history)),
                         "board_gespielt": list(g.result.get("board", [])) if g.result else None})
    replay_edge = haelften[0]["seat0_netto_chips"] - haelften[1]["seat0_netto_chips"]
    return {"deck_global": deck_global, "job": job, "idx": idx, "deck_seed": deck_seed, "hand_id": hand_id,
            "holes": {"S0": h0, "S1": h1}, "board": board,
            "edge_edges_json": edges[deck_global], "edge_replay": replay_edge,
            "identisch": replay_edge == edges[deck_global], "sekunden": round(time.time() - t0, 1),
            "haelften": haelften}


def _trace_zeilen(pfad: str, ab: int) -> list:
    if not pfad or not os.path.exists(pfad):
        return []
    return [json.loads(l) for l in open(pfad, encoding="utf-8")][ab:]


def main() -> None:
    args = list(sys.argv[1:])
    trace = None
    if "--trace" in args:                       # K2-Trace der Plan-Entscheidungen (Verteilung, sample_u, final)
        i = args.index("--trace")
        trace = args[i + 1]
        del args[i:i + 2]
        os.environ["POKERB_K2_TRACE"] = trace   # nach dem POKERB_*-Strip gesetzt, wie scratchpad/aa_replay_deck.py
    run_dir = Path(args[0])
    decks = [int(x) for x in args[1:]]
    out = []
    for d in decks:
        n0 = len(_trace_zeilen(trace, 0))
        r = replay(run_dir, d)
        r["k2_trace"] = [{k: z.get(k) for k in ("seat", "hand_adresse", "decision_addr", "fallback_status", "flags",
                                                  "plan_verteilung", "sample_u", "final", "range_herkunft")}
                         for z in _trace_zeilen(trace, n0)]
        out.append(r)
        print(f"Deck {d} (job {r['job']} idx {r['idx']} deck_seed {r['deck_seed']} hand_id {r['hand_id']}): "
              f"edges.json {r['edge_edges_json']} | replay {r['edge_replay']} | identisch={r['identisch']} "
              f"({r['sekunden']} s)", flush=True)
        print(f"   Holes S0 {r['holes']['S0']} S1 {r['holes']['S1']}  Board {r['board']}")
        for h in r["haelften"]:
            print(f"   seat0={h['seat0']:<9} netto {h['seat0_netto_chips']:+6d} Chips ({h['seat0_netto_chips']/BB_CHIPS:+.0f} bb): "
                  f"{h['aktionen']}", flush=True)
        for z in r["k2_trace"]:
            print(f"   [K2] seat{z['seat']} {z['decision_addr']} status={z['fallback_status']} "
                  f"verteilung={z['plan_verteilung']} u={z['sample_u']} final={z['final']} flags={z['flags']}", flush=True)
    ziel = run_dir / "g5_deck_replay.json"
    ziel.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"-> {ziel}")


if __name__ == "__main__":
    main()
