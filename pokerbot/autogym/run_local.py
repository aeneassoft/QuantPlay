"""AUTOGYM lokal — der PC-Pilot vor jeder Pod-Skalierung.

  python -m pokerbot.autogym.run_local                     # Standard-Pilot
  python -m pokerbot.autogym.run_local --hu-pairs 300 --six-hands 400

Ablauf: (1) HU-Gym auf gepaarten Decks, (2) 6-max-Gym, (3) beide durchs Orakel,
(4) eine Improver-Runde (P-Patches durchs A/B-Gate, L/F als Vorschlaege),
(5) Report nach data/autogym/. Erst wenn dieser Lauf traegt, lohnt ein Pod.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from . import gym_hu, gym_six, improver
from .oracle import manifest


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--hu-pairs", type=int, default=150)
    ap.add_argument("--six-hands", type=int, default=200)
    ap.add_argument("--gate-decks", type=int, default=100)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--eq-iters", type=int, default=120)
    args = ap.parse_args()

    t0 = time.time()
    print("AUTOGYM v0 — lokaler Pilot\n")
    print("1) HU-Gym laeuft ...")
    hu = gym_hu.run(n_pairs=args.hu_pairs, seed=args.seed, eq_iters=args.eq_iters)
    print(f"   {hu['haende']} Haende | Button-Netto {hu['button_netto_bb100']:+.1f} bb/100 | "
          f"Paar-Drift {hu['paar_drift_bb100']:+.2f} ± {hu['paar_drift_se']:.2f} (Soll ~0) | "
          f"Orakel {hu['orakel']}")

    print("2) 6-max-Gym laeuft ...")
    six = gym_six.run(n_hands=args.six_hands, seed=args.seed)
    pos = ", ".join(f"{k} {v:+.0f}" for k, v in six["position_bb100"].items())
    print(f"   {six['haende']} Haende | Position bb/100: {pos} | Orakel {six['orakel']}")

    print("3) Gate-Selbsttest (exploit OFF vs ON, gepaarte Decks) ...")
    from pokerbot.benchmark.duplicate import pokerbot as pb_factory
    gate = improver.gate_ab(pb_factory(exploit=False), pb_factory(exploit=True),
                            args.gate_decks, args.seed + 3)
    print(f"   Kandidat exploit-OFF: {gate['bb100']:+.1f} ± {gate['se']:.1f} bb/100 "
          f"-> {gate['verdict']}")

    print("4) Improver-Runde ...")
    entries = improver.improve_round(hu["orakel_report"], n_decks=args.gate_decks,
                                     seed=args.seed + 1)
    for e in entries:
        kern = e.get("bb100", e.get("severity_bb", ""))
        print(f"   [{e['typ']}] {e['regel']}: {e['verdict']} {kern}")
    if not entries:
        print("   keine Befunde -> keine Patches, kein Vorschlag (sauberer Lauf)")

    out = Path("data/autogym") / f"report_{time.strftime('%Y%m%d_%H%M%S')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    hu.pop("orakel_report"); six.pop("orakel_report")
    out.write_text(json.dumps({
        "hu": hu, "six": six, "gate_selbsttest": gate, "improver": entries,
        "manifest": manifest(),
        "sekunden": round(time.time() - t0, 1),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nReport: {out}  ({time.time() - t0:.0f}s)")
    print("\nFormalisierungs-Stand (Orakel-Manifest):")
    m = manifest()
    for z in m["verdrahtet_v0"]:
        print("   [x] " + z)
    for z in m["offen"][:4]:
        print("   [ ] " + z)
    print(f"   ... plus {len(m['offen']) - 4} weitere offen")


if __name__ == "__main__":
    main()
