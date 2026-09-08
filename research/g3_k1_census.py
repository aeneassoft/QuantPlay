"""G3-Zensus (Gate-Laeufer, 2026-09-07): spielt N Vorgeschichten mit research.k1_oracle.spiele_vorgeschichten
(Phase 1, ohne Orakel) und zaehlt die REAL gefeuerten Guard-Klassen, Knoten und Spielzeit — die Grundlage fuer
die Hochrechnung und die Stichproben-Planung (Karte K1: >=64 Vorgeschichten, jede Guard-Klasse >=16x).
Aendert keinen Strategie-Code; schreibt data/runs/v10/g3_census_<ts>.json.

  python -m research.g3_k1_census --n 300
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--deck-seed", type=int, default=5)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--stack", default="r6_button")
    args = ap.parse_args()
    from research import k1_oracle as ko
    ko._worker_env()
    t0 = time.time()
    vgs = ko.spiele_vorgeschichten(args.n, args.deck_seed, args.seed, args.stack)
    t_spiel = time.time() - t0
    klassen = ko._zaehle_guard_klassen(vgs)
    n_knoten = sum(len(v["knoten_states"]) for v in vgs)
    kombis: dict[str, int] = {}
    for v in vgs:
        k = "+".join(v["guards_real"]) or "keine"
        kombis[k] = kombis.get(k, 0) + 1
    max_deck = max(v["deck_idx"] for v in vgs) if vgs else -1
    rep = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "konfig": vars(args), "n_vorgeschichten": len(vgs),
           "n_knoten": n_knoten, "knoten_je_vg": n_knoten / max(1, len(vgs)), "max_deck_idx": max_deck,
           "zeit_spiel_s": round(t_spiel, 1), "guard_klassen_real": klassen, "kombinationen": kombis,
           "vg_index_je_klasse": {kl: [i for i, v in enumerate(vgs) if kl in v["guards_real"]] for kl in klassen},
           "keine_index": [i for i, v in enumerate(vgs) if not v["guards_real"]]}
    out = Path("data/runs/v10") / f"g3_census_{time.strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in rep.items() if not k.endswith("index") and k != "vg_index_je_klasse"},
                     ensure_ascii=False, indent=1))
    print("Report:", out)


if __name__ == "__main__":
    main()
