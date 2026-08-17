"""RUNDE 4 — die 2-Stunden-Verbesserungs-Kampagne (User-Auftrag 2026-08-17).

Ein Lauf, beide Disziplinen, seriell (eine Flotte zur Zeit), selbst-berichtend.

  PHASE A (HU, ~45 min)  Margen-Sweep: sel_m06/m10/m15 je DIREKT vs sel_guard
                         (leiser Kanal — die Arme unterscheiden sich nur im
                         Margen-Band). Snowie-Hypothese: 3pp ist zu locker.
  PHASE B (HU, ~12 min)  einmal_guard vs sel_guard: Mehrstrassen-Disziplin
                         (die groesste Snowie-Blunder-Klasse waren Call-Ketten).
  PHASE C (6max, ~35 min) AP-6MAX-Beobachtung: 12 parallele Gyms, Struktur-
                         Katalog v0 (Positions-Ledger, Orakel-Frequenzen,
                         Facing-Bet-Verteilung je Strasse) bei echtem n.
  PHASE D (HU, Rest bis 2h) der beste A/B-Kandidat DECISIVE vs die BASIS —
                         skaliert auf die verbleibende Zeit (min. 60k Decks).

Vorregistriert: ANWENDEN nur > 2*SE (pargate-Regeln); ein Kandidat, der v1
nicht schlaegt, wird ehrlich NEUTRAL gebucht; Phase D laeuft nur, wenn A/B
einen Sieger ueber v1 liefert — sonst geht die Zeit in mehr Phase-C-Haende.

  python -m pokerbot.autogym.runde4
"""
from __future__ import annotations

import json
import multiprocessing as mp
import sys
import time

ZIEL_SEKUNDEN = 2 * 3600
WORKERS = 20


def _six_worker(args: tuple) -> dict:
    seed, n_hands = args
    try:
        import torch
        torch.set_num_threads(1)
    except Exception:  # noqa: BLE001
        pass
    from pokerbot.autogym import gym_six
    r = gym_six.run(n_hands=n_hands, seed=seed)
    rep = r.pop("orakel_report")
    streets = {}
    for street, pot, bet, folded in rep.facing_bets:
        d = streets.setdefault(street, {"n": 0, "folds": 0, "bet_summe": 0.0, "pot_summe": 0.0})
        d["n"] += 1
        d["folds"] += 1 if folded else 0
        d["bet_summe"] += bet
        d["pot_summe"] += pot
    r["facing_nach_strasse"] = streets
    return r


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from pokerbot.autogym import runs
    from pokerbot.autogym.improver import _journal
    from pokerbot.autogym.pargate import par_gate

    t0 = time.time()
    d = runs.neuer_run("runde4_kampagne", {"ziel_sekunden": ZIEL_SEKUNDEN, "workers": WORKERS})
    bericht: dict = {}

    print("PHASE A — Margen-Sweep vs AUSLESE v1 (leiser Kanal)", flush=True)
    for i, arm in enumerate(("sel_m06", "sel_m10", "sel_m15")):
        res = par_gate(arm, 25000, WORKERS, deck_seed0=200000 + i * 1000)
        # vs sel_guard direkt:
        res_direkt = par_gate(arm, 25000, WORKERS, deck_seed0=210000 + i * 1000,
                              incumbent="sel_guard")
        bericht[arm] = {"vs_basis": res, "vs_v1": res_direkt}
        _journal({"typ": "RUNDE4-SWEEP", "regel": arm,
                  "vs_v1_bb100": res_direkt["bb100"], "vs_v1_se": res_direkt["se"],
                  "vs_basis_bb100": res["bb100"], "verdict": res_direkt["verdict"]})
        print(f"  {arm}: vs v1 {res_direkt['bb100']:+.2f}±{res_direkt['se']:.2f} "
              f"({res_direkt['verdict']}) | vs Basis {res['bb100']:+.2f}±{res['se']:.2f}",
              flush=True)

    print("PHASE B — Mehrstrassen-Disziplin (einmal_guard) vs v1", flush=True)
    res_b = par_gate("einmal_guard", 25000, WORKERS, deck_seed0=220000, incumbent="sel_guard")
    bericht["einmal_guard"] = {"vs_v1": res_b}
    _journal({"typ": "RUNDE4-DISZIPLIN", "regel": "einmal_guard",
              "vs_v1_bb100": res_b["bb100"], "vs_v1_se": res_b["se"],
              "verdict": res_b["verdict"]})
    print(f"  einmal_guard: vs v1 {res_b['bb100']:+.2f}±{res_b['se']:.2f} ({res_b['verdict']})",
          flush=True)

    print("PHASE C — 6-max-Beobachtung (Struktur-Katalog v0)", flush=True)
    jobs = [(500 + i, 2500) for i in range(12)]
    with mp.Pool(12) as pool:
        six = list(pool.imap_unordered(_six_worker, jobs))
    haende6 = sum(r["haende"] for r in six)
    pos: dict = {}
    for r in six:
        for k, v in r["position_bb100"].items():
            pos.setdefault(k, []).append(v)
    pos_mittel = {k: round(sum(v) / len(v), 1) for k, v in sorted(pos.items())}
    facing: dict = {}
    for r in six:
        for street, dd in r["facing_nach_strasse"].items():
            f = facing.setdefault(street, {"n": 0, "folds": 0, "bet_summe": 0.0, "pot_summe": 0.0})
            for k in f:
                f[k] += dd[k]
    katalog = {street: {"knoten": f["n"], "fold_freq": round(f["folds"] / max(1, f["n"]), 3),
                        "mittl_bet_pot": round(f["bet_summe"] / max(1e-9, f["pot_summe"]), 3)}
               for street, f in facing.items()}
    bericht["sechsmax"] = {"haende": haende6, "position_bb100": pos_mittel,
                           "facing_katalog": katalog,
                           "orakel": {k: sum(r["orakel"][k] for r in six)
                                      for k in ("decisions", "HART", "P", "L", "F")}}
    _journal({"typ": "RUNDE4-6MAX-KATALOG", "haende": haende6,
              "befund": f"Positions-bb100 {pos_mittel}; Facing-Katalog {katalog}"})
    print(f"  {haende6} Haende | Position {pos_mittel} | Facing {katalog}", flush=True)

    # PHASE D — der beste Kandidat decisive, Zeitbudget-gesteuert
    kandidaten = [(a, bericht[a]["vs_v1"]["bb100"], bericht[a]["vs_v1"]["se"])
                  for a in ("sel_m06", "sel_m10", "sel_m15", "einmal_guard")]
    sieger = max(kandidaten, key=lambda x: x[1] - 2 * x[2])
    rest = ZIEL_SEKUNDEN - (time.time() - t0)
    decks = max(60000, int(rest / 60 * 2800))
    if sieger[1] - 2 * sieger[2] > 0:
        print(f"PHASE D — {sieger[0]} DECISIVE vs Basis ({decks} Decks)", flush=True)
        res_d = par_gate(sieger[0], decks, WORKERS, deck_seed0=230000)
        bericht["decisive"] = {"kandidat": sieger[0], **res_d}
        _journal({"typ": "RUNDE4-DECISIVE", "regel": sieger[0], **res_d})
    else:
        print(f"PHASE D — kein Kandidat schlaegt v1 (bester: {sieger[0]} "
              f"{sieger[1]:+.2f}±{sieger[2]:.2f}) -> Zeit geht in 6-max-Haende", flush=True)
        with mp.Pool(12) as pool:
            six2 = list(pool.imap_unordered(_six_worker, [(700 + i, 2500) for i in range(12)]))
        bericht["sechsmax"]["haende_nachschlag"] = sum(r["haende"] for r in six2)
        _journal({"typ": "RUNDE4-DECISIVE", "regel": "keiner",
                  "befund": f"bester {sieger[0]} {sieger[1]:+.2f}+-{sieger[2]:.2f} vs v1 -> "
                            "v1 bleibt; Zeit in 6-max-Beobachtung investiert"})

    bericht["sekunden"] = round(time.time() - t0, 1)
    runs.schliesse_run(d, {"phasen": list(bericht.keys()), "sekunden": bericht["sekunden"]})
    (d / "bericht.json").write_text(json.dumps(bericht, ensure_ascii=False, indent=1),
                                    encoding="utf-8")
    print(f"RUNDE 4 KOMPLETT in {bericht['sekunden']/60:.0f} min -> {d}", flush=True)


if __name__ == "__main__":
    main()
