"""TURNIER-ARENA — Single-Table-SNGs des Bots gegen das sixmax-Feld, mit gepaarten Seeds.

Die Spielschleife ist die bewährte aus research/coinpoker_ecology.simulate (decide mit Fallback,
observe-Fanout), MINUS Stack-Reset, PLUS Director (Level/Antes/Eliminierung/Payouts) und der
obs['icm']-Injektion pro Entscheidung. Gepaarte Seeds = Arm A und Arm B spielen DIESELBEN Decks
gegen DIESELBEN Feld-Profile — Kartenglück kürzt sich (die Grounded-Gate-Doktrin).

  python -m pokerbot.arena.tourney --tourneys 400          # ICM-ON vs ICM-OFF, gepaart
"""
from __future__ import annotations

import argparse
import random

from pokerbot.arena.sixmax import PROFILES, SixMaxBot
from pokerbot.strategy.tournament import SNG9, Director, Structure

HERO_SEAT_NAME = "hero"
FIELD_PROFILES = ["tag", "lag", "nit", "station", "maniac", "tag", "lag", "nit"]  # 8 Gegner = 9-max


def _mk_agents(names: list[str], rng: random.Random, hero_factory, icm_on: bool):
    agents = {}
    for i, nm in enumerate(names):
        if nm == HERO_SEAT_NAME:
            agents[nm] = hero_factory(random.Random(rng.randrange(1 << 30)))
        else:
            prof = nm.rsplit("_", 1)[0]
            agents[nm] = SixMaxBot(0, PROFILES[prof])
    return agents


def run_tourney(structure: Structure, hero_factory, seed: int, icm_on: bool = True,
                field: list[str] | None = None) -> dict:
    """EIN Turnier bis zum Ende. -> {'place', 'payout', 'hands'} des Heros."""
    rng = random.Random(seed)
    profs = list(field or FIELD_PROFILES)
    names = [HERO_SEAT_NAME] + [f"{p}_{i}" for i, p in enumerate(profs)]
    rng.shuffle(names)
    d = Director(structure, names, seed=seed)
    agents = _mk_agents(names, rng, hero_factory, icm_on)
    guard_hands = 0
    while not d.over() and guard_hands < 3000:
        guard_hands += 1
        t = d.next_table()
        for a in agents.values():
            if hasattr(a, "bind_table"):
                a.bind_table(t)
        seat_agent = {i: agents[s.name] for i, s in enumerate(t.seats)}
        aggressor: int | None = None
        guard = 0
        while not t.hand_over and t.to_act is not None and guard < 300:
            guard += 1
            seat = t.to_act
            obs = t.obs_for(seat)
            if icm_on and t.seats[seat].name == HERO_SEAT_NAME:
                # NUR der Hero bekommt die ICM-Brille (der Messgegenstand); das Feld bleibt
                # Chip-EV-naiv — wie echte SNG-Felder (und wie der OFF-Arm des Experiments).
                obs["icm"] = d.icm_ctx(t, seat, aggressor)
            street, tc, pr = t.street, obs["to_call"], t.preflop_raises
            try:
                dec = seat_agent[seat].decide(obs)
                action, amount = (dec["action"], dec["amount"]) if isinstance(dec, dict) else dec
                t.act(action, amount)
            except Exception:  # noqa: BLE001 — ein Bot-Fehler killt kein Turnier
                la = t.legal_actions()
                action = "check" if la.get("can_check") else ("call" if la.get("can_call") else "fold")
                t.act(action)
                amount = None
            if action in ("bet", "raise", "allin"):
                aggressor = seat
            for a in agents.values():
                if hasattr(a, "observe"):
                    a.observe(seat, street, "raise" if action == "allin" else action, tc, pr)
        d.after_hand(t)
    res = next(r for r in d.results() if r["name"] == HERO_SEAT_NAME)
    return {"place": res["place"], "payout": res["payout"], "hands": d.hand_no}


def run_batch(n: int, hero_factory, structure: Structure = SNG9, base_seed: int = 1000) -> dict:
    """Gepaartes Experiment: ICM-ON vs ICM-OFF auf IDENTISCHEN Seeds. -> beide Arme + Deltas."""
    arms = {"icm_on": [], "icm_off": []}
    places = {"icm_on": [], "icm_off": []}
    for k in range(n):
        seed = base_seed + k
        for arm, on in (("icm_on", True), ("icm_off", False)):
            r = run_tourney(structure, hero_factory, seed, icm_on=on)
            arms[arm].append(r["payout"] - structure.buyin)
            places[arm].append(r["place"])
    out = {}
    for arm, nets in arms.items():
        m = sum(nets) / len(nets)
        var = sum((x - m) ** 2 for x in nets) / max(1, len(nets) - 1)
        se = (var ** 0.5) / (len(nets) ** 0.5)
        pl = places[arm]
        out[arm] = {"roi_pct": 100 * m / structure.buyin, "se_pct": 100 * se / structure.buyin,
                    "netto": m, "n": len(nets),
                    "platz_verteilung": {p: pl.count(p) for p in sorted(set(pl))}}
    diffs = [a - b for a, b in zip(arms["icm_on"], arms["icm_off"])]
    md = sum(diffs) / len(diffs)
    vard = sum((x - md) ** 2 for x in diffs) / max(1, len(diffs) - 1)
    out["delta"] = {"roi_pp": 100 * md / structure.buyin,
                    "se_pp": 100 * (vard ** 0.5) / (len(diffs) ** 0.5) / structure.buyin}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tourneys", type=int, default=400)
    ap.add_argument("--seed", type=int, default=1000)
    ap.add_argument("--out", type=str, default=None,
                    help="Rohdaten (JSON) fuer den Parallel-Merger schreiben")
    a = ap.parse_args()

    def hero_factory(rng):
        return SixMaxBot(0, PROFILES["tag"])

    if a.out:
        # PARALLEL-MODUS: Rohdaten je Paar schreiben, der Merger poolt exakt (kein Aggregat-Verlust)
        import json
        raw = {"icm_on": [], "icm_off": []}
        for k in range(a.tourneys):
            seed = a.seed + k
            for arm, on in (("icm_on", True), ("icm_off", False)):
                r = run_tourney(SNG9, hero_factory, seed, icm_on=on)
                raw[arm].append({"net": r["payout"] - SNG9.buyin, "place": r["place"]})
        open(a.out, "w", encoding="utf-8").write(json.dumps(raw))
        print(f"fertig: {a.tourneys} Paare -> {a.out}")
        return
    res = run_batch(a.tourneys, hero_factory, SNG9, a.seed)
    for arm in ("icm_on", "icm_off"):
        r = res[arm]
        print(f"[{arm:8s}] ROI {r['roi_pct']:+.1f}% ± {r['se_pct']:.1f} (n={r['n']}) | "
              f"Plätze {r['platz_verteilung']}")
    print(f"[GEPAART ] ICM-Effekt: {res['delta']['roi_pp']:+.2f} ± {res['delta']['se_pp']:.2f} "
          f"Prozentpunkte ROI")


if __name__ == "__main__":
    main()
