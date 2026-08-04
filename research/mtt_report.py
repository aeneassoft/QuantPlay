"""MTT-Kampagnen-Report — poolt die Worker-JSONs und rechnet die GEPAARTEN Verdikte.

Marginal-SEs je Arm unterschaetzen die Power des gepaarten Designs massiv (beide Arme sind
byte-identisch, bis <=144 Spieler uebrig sind — Turniere mit fruehem Hero-Bust tragen exakt 0
zur Arm-Differenz bei, aber volle Varianz zum Marginal). Das Verdikt kommt deshalb aus den
PER-SEED-DIFFERENZEN (Review-Fund #11).

  python -m research.mtt_report
"""
from __future__ import annotations

import glob
import json

from research.mtt_sim import BUYIN, PAYOUTS


def _pool(pattern: str) -> dict[str, list[dict]]:
    raw: dict[str, list[dict]] = {}
    for f in sorted(glob.glob(pattern)):
        d = json.load(open(f, encoding="utf-8"))
        for arm, recs in d.items():
            raw.setdefault(arm, []).extend(recs)
    return raw


def _marginal(recs: list[dict]) -> dict:
    n = len(recs)
    nets = [r["payout"] - BUYIN for r in recs]
    m = sum(nets) / n
    se = (sum((x - m) ** 2 for x in nets) / max(1, n - 1)) ** 0.5 / n ** 0.5
    return {
        "n": n, "roi": 100 * m / BUYIN, "se": 100 * se / BUYIN,
        "p_itm": 100 * sum(r["place"] <= len(PAYOUTS) for r in recs) / n,
        "p_ft": 100 * sum(r["place"] <= 6 for r in recs) / n,
        "p_top3": 100 * sum(r["place"] <= 3 for r in recs) / n,
        "p_win": 100 * sum(r["place"] == 1 for r in recs) / n,
    }


def _paired_delta(a: list[dict], b: list[dict]) -> dict:
    """b minus a, je Seed. -> ROI-Delta (pp) + SE + Anteil identischer Ausgaenge."""
    n = min(len(a), len(b))
    diffs = [(b[i]["payout"] - a[i]["payout"]) / BUYIN * 100 for i in range(n)]
    md = sum(diffs) / n
    sd = (sum((x - md) ** 2 for x in diffs) / max(1, n - 1)) ** 0.5
    ident = sum(1 for i in range(n) if a[i]["place"] == b[i]["place"]) / n
    return {"n": n, "roi_pp": md, "se_pp": sd / n ** 0.5,
            "z": md / (sd / n ** 0.5) if sd > 0 else 0.0, "ident": 100 * ident}


def report(pattern: str, titel: str) -> None:
    raw = _pool(pattern)
    if not raw:
        print(f"[{titel}] keine Daten ({pattern})")
        return
    print(f"=== {titel} ===")
    for arm, recs in raw.items():
        s = _marginal(recs)
        print(f"  [{arm:6s}] n={s['n']:4d} ROI {s['roi']:+7.1f}% ± {s['se']:.1f} | "
              f"ITM {s['p_itm']:5.1f}% | FT {s['p_ft']:4.2f}% | Top3 {s['p_top3']:4.2f}% | "
              f"P(1.) {s['p_win']:4.2f}%")
    if "chipEV" in raw and "druck" in raw:
        d = _paired_delta(raw["chipEV"], raw["druck"])
        print(f"  [GEPAART] druck-chipEV: {d['roi_pp']:+.1f} ± {d['se_pp']:.1f} pp ROI "
              f"(z={d['z']:.2f}; n={d['n']}; {d['ident']:.0f}% identische Plaetze)")


def main() -> None:
    report("data/mtt/freq_w*.json", "Feld: $1050-frequenzkalibriert (optimistische Schranke)")
    report("data/mtt/bots_w*.json", "Feld: Bot-Kerne an Heros Tisch (konservative Schranke)")
    base = 100.0 / 600
    print(f"  (Basisraten bei 600 Spielern: P(1.) {base:.3f}% | FT {6*base:.1f}% | "
          f"ITM {90*base:.1f}%)")


if __name__ == "__main__":
    main()
