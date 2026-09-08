# -*- coding: utf-8 -*-
"""G5-Auswertung eines pargate-Spiegels (docs/V10_BUILD_CARD.md, Gate G5).

Liest result.json + edges.json eines pargate-Run-Ordners und weist die Gate-
Kennzahlen aus: bb/100 +- SE, Bootstrap-CI, Verdikt, Divergenz-Decks, nz_median,
groesste Einzel-Deck-Verluste/-Gewinne und den KATASTROPHEN-CHECK (Decks mit
|Edge| > 150 bb = 15000 Chips; ein Deck = 2 gespiegelte Haende, Einsatz 200 bb).
Reine Messung — aendert nichts, rechnet nichts nach, was pargate schon liefert.

  python -m research.g5_spiegel_auswertung data/runs/<ts>_pargate_r10_stack [--out pfad.json]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

BB_CHIPS = 100
KATASTROPHE_BB = 150                      # Karte G5: Katastrophen-Deck-Muster
KATASTROPHE_CHIPS = KATASTROPHE_BB * BB_CHIPS
TOP_N = 10                                 # groesste Einzel-Decks je Richtung


def auswerten(run_dir: Path) -> dict:
    res = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    edges = json.loads((run_dir / "edges.json").read_text(encoding="utf-8"))
    cfg = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    nz = [(i, e) for i, e in enumerate(edges) if e != 0]
    verluste = sorted(nz, key=lambda t: t[1])[:TOP_N]
    gewinne = sorted(nz, key=lambda t: -t[1])[:TOP_N]
    kata = [(i, e) for i, e in nz if abs(e) >= KATASTROPHE_CHIPS]
    kata_neg = [t for t in kata if t[1] < 0]
    summe = sum(edges)
    summe_kata = sum(e for _, e in kata)
    return {
        "run_dir": str(run_dir), "config": cfg,
        "kandidat": res["kandidat"], "incumbent": res["incumbent"], "kanal": res["kanal"],
        "n_decks": res["n_decks"], "bb100": res["bb100"], "se": res["se"],
        "ci95": [res["ci95_lo"], res["ci95_hi"]], "verdict": res["verdict"],
        "bb100_trim": res["bb100_trim"], "median_bb100": res["median_bb100"],
        "perm_p": res.get("perm_p"), "vorzeichen_z": res.get("vorzeichen_z"),
        "divergenz_decks": res["nonzero"], "divergenz_anteil": res["nonzero_anteil"],
        "nz_pos": res["nz_pos"], "nz_median_chips": res["nz_median_chips"],
        "summe_chips": summe, "summe_bb": summe / BB_CHIPS,
        "groesste_verluste_chips": [{"deck": i, "chips": e, "bb": e / BB_CHIPS} for i, e in verluste],
        "groesste_gewinne_chips": [{"deck": i, "chips": e, "bb": e / BB_CHIPS} for i, e in gewinne],
        "katastrophen_schwelle_chips": KATASTROPHE_CHIPS,
        "katastrophen_decks": [{"deck": i, "chips": e, "bb": e / BB_CHIPS} for i, e in kata],
        "n_katastrophen": len(kata), "n_katastrophen_negativ": len(kata_neg),
        "anteil_summe_aus_katastrophen": (summe_kata / summe) if summe else None,
        "sekunden": res["sekunden"], "decks_pro_min": res["decks_pro_min"],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    a = auswerten(Path(args.run_dir))
    out = Path(args.out) if args.out else Path(args.run_dir) / "g5_auswertung.json"
    out.write_text(json.dumps(a, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{a['kandidat']} vs {a['incumbent']} [{a['kanal']}] n={a['n_decks']} Decks")
    print(f"  bb/100 {a['bb100']:+.2f} +- {a['se']:.2f}  CI95 [{a['ci95'][0]:+.2f}, {a['ci95'][1]:+.2f}]  "
          f"verdict {a['verdict']}  trim {a['bb100_trim']:+.2f}  perm_p {a['perm_p']}")
    print(f"  Divergenz-Decks {a['divergenz_decks']} ({100*a['divergenz_anteil']:.1f} %), nz_pos {a['nz_pos']}, "
          f"nz_median {a['nz_median_chips']} Chips, Summe {a['summe_bb']:+.0f} bb")
    print(f"  Katastrophen (|Edge| >= {KATASTROPHE_BB} bb): {a['n_katastrophen']} "
          f"(negativ {a['n_katastrophen_negativ']}), Anteil an Summe: {a['anteil_summe_aus_katastrophen']}")
    print("  groesste Verluste (Deck, bb):", [(d["deck"], round(d["bb"], 1)) for d in a["groesste_verluste_chips"]])
    print("  groesste Gewinne  (Deck, bb):", [(d["deck"], round(d["bb"], 1)) for d in a["groesste_gewinne_chips"]])
    print(f"  Auswertung -> {out}")


if __name__ == "__main__":
    main()
