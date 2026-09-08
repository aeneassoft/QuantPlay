"""Golden-Set / Divergenz-Smoke: zwei Stacks auf N festen Decks (duplicate_ab), Edges je Deck
auf Platte. Zweck (V10_BUILD_CARD E4/K4): Byte-Identitaet einer Referenz-Politik VOR und NACH
Infrastruktur-Aenderungen (hand_id-Injektion, K4-Hygiene) beweisen, und Divergenz-Decks
zwischen Kandidat und Amtierendem zaehlen.

    python -m research.golden_set --a r8_stack --b basis --decks 40 --seed 424242 --out data/runs/v10/golden_r8_vs_basis_pre.json
    python -m research.golden_set --vergleich data/runs/v10/golden_r8_vs_basis_pre.json data/runs/v10/golden_r8_vs_basis_post.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time


def _lauf(a: str, b: str, decks: int, seed: int) -> dict:
    for v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ.setdefault(v, "1")
    for k in [k for k in os.environ if k.startswith("POKERB_")]:
        os.environ.pop(k, None)           # Gate-Kanal ist flag-frei (pargate-Konvention)
    import torch
    torch.set_num_threads(1)
    from pokerbot.autogym.pargate import _baue_fabrik
    from pokerbot.benchmark.duplicate import duplicate_ab, gen_decks
    t0 = time.time()
    deck_liste = gen_decks(decks, seed=seed)
    res = duplicate_ab(_baue_fabrik(a, seed), _baue_fabrik(b, seed), deck_liste, return_edges=True)
    edges = list(res[-1]) if isinstance(res, tuple) else list(res["edges"])
    return {"a": a, "b": b, "decks": decks, "seed": seed, "sek_je_deck": round((time.time() - t0) / decks, 3),
            "edges": [float(e) for e in edges], "nonzero": int(sum(1 for e in edges if e != 0)),
            "summe": float(sum(edges))}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", default="r8_stack")
    ap.add_argument("--b", default="basis")
    ap.add_argument("--decks", type=int, default=40)
    ap.add_argument("--seed", type=int, default=424242)
    ap.add_argument("--out", default="")
    ap.add_argument("--vergleich", nargs=2, metavar=("ALT", "NEU"))
    args = ap.parse_args()
    if args.vergleich:
        alt, neu = (json.load(open(p, encoding="utf-8")) for p in args.vergleich)
        gleich = alt["edges"] == neu["edges"] and (alt["a"], alt["b"], alt["seed"]) == (neu["a"], neu["b"], neu["seed"])
        diff = [i for i, (x, y) in enumerate(zip(alt["edges"], neu["edges"])) if x != y]
        print("IDENTISCH" if gleich else f"ABWEICHUNG in Decks {diff}")
        sys.exit(0 if gleich else 1)
    r = _lauf(args.a, args.b, args.decks, args.seed)
    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        json.dump(r, open(args.out, "w", encoding="utf-8"), indent=1)
    print(f"{r['a']} vs {r['b']}: {r['decks']} Decks, nonzero {r['nonzero']}, Summe {r['summe']:+.0f} Chips, "
          f"{r['sek_je_deck']} s/Deck" + (f" -> {args.out}" if args.out else ""))


if __name__ == "__main__":
    main()
