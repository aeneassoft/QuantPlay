"""Simulate OUR engine playing the USER's measured style (report plan 2026-07-01, stage 7).

We map the user's observed tendencies (loose, opens wide, over-bets, sticky bluff-catcher) onto a custom `Knobs`
profile — 'princedarkness' — hand it to a `SixMaxBot`, and score it with the RL environment vs the training league AND
the held-out league. A neutral 'tag' hero is the reference. The point is NOT a bb/100 headline (framing rule: no
losses); it is WHAT WE LEARN — where a loose-aggressive style dominates (loose-passive opponents) and where it gets
punished (the disciplined/held-out types) — which independently corroborates the user's own read about "frantic" tables.

Pure-local, ~5 min CPU, NO pod. Reuses training/rl_env.py + pokerbot/arena/sixmax.py.
"""
from __future__ import annotations

import json
import random

from pokerbot.arena.sixmax import PROFILES, Knobs, SixMaxBot
from pokerbot.brain import modes  # noqa: F401  (rl_env imports it; keep the import graph explicit)
from training import rl_env

# The user's style as engine knobs — calibrated to the MEASURED stats (deep_stats.json): high VPIP (~55%), opens wide,
# 3-bets often, flats very wide (the loose-call tendency), overbets/bluffs a lot, sticky bluff-catcher. A prior; the
# calibration gate below checks the resulting VPIP lands near the measured value.
PRINCEDARKNESS = Knobs(
    name="princedarkness",
    open_mult=3.0,      # opens far wider than a TAG core (loose, aggressive first-in) — tuned to ~45% VPIP
    tb_pct=0.75,        # 3-bets at a lower percentile threshold = more 3-bets
    fb_pct=0.92,
    flat_hi=0.92,       # flats a very wide share of opens (the loose multiway-call tendency)
    cont_lo=0.36,       # almost never over-folds vs a 3-bet
    raise_eq=0.70,      # raises for value a touch lighter
    bluff_mult=2.0,     # the over-bet / high-aggression signature
    call_delta=-0.10,   # calls down wider than GTO (sticky bluff-catcher)
)

_TRAIN = rl_env.TRAIN_LEAGUE          # ("tag","lag","nit","station","maniac")
_HELD = rl_env.HELDOUT_LEAGUE         # ("rock","whale","shark") — types the profile is not tuned against


def _measure_vpip(knobs: Knobs, n_hands: int = 400, seed: int = 7) -> float:
    """Play the profile vs the train league and count the fraction of hands it VOLUNTARILY put money in preflop
    (call/raise/all-in that is not the free BB check). The calibration gate: this should land near the user's ~55%."""
    hero_seat = 0
    from pokerbot.engine.table import Table
    table = Table([f"s{i}" for i in range(len(_TRAIN) + 1)], starting_stack=10000, sb=50, bb=100,
                  seed=seed, human_seat=hero_seat)
    hero_bot = SixMaxBot(hero_seat, knobs)
    league = rl_env.make_league(list(_TRAIN), hero_seat=hero_seat)
    voluntary = {"hand": -1, "did": False}
    counts = {"hands": 0, "vpip": 0}

    def hero(tbl, seat):
        d = hero_bot.decide(tbl.obs_for(seat))
        if tbl.street == "preflop" and voluntary["hand"] != tbl.hand_no:
            voluntary["hand"], voluntary["did"] = tbl.hand_no, False
        if (tbl.street == "preflop" and not voluntary["did"]
                and d["action"] in ("call", "raise", "bet", "all-in")):
            voluntary["did"] = True
        return d["action"], d.get("amount")

    policies = {hero_seat: hero}
    observers = list(league.values())
    for seat, bot in league.items():
        policies[seat] = rl_env.league_policy(bot)
    for _ in range(n_hands):
        rl_env.play_hand(table, policies, observers)
        counts["hands"] += 1
        if voluntary["did"]:
            counts["vpip"] += 1
        voluntary["did"] = False
    return round(100 * counts["vpip"] / counts["hands"], 1)


def _score(knobs: Knobs, league, n_hands: int, seed: int) -> dict:
    bot = SixMaxBot(0, knobs)
    return rl_env.evaluate_policy(rl_env.league_policy(bot), profiles=league, n_hands=n_hands, seed=seed)


def _per_opponent(knobs: Knobs, n_hands: int = 600, seed: int = 11) -> dict:
    """Heads-up-ish read: score the style against EACH opponent type alone (a 5-seat table all of one type) so we can
    see which tables it dominates and which punish it — the 'when dangerous' cross-check."""
    out = {}
    for opp in ("station", "whale", "nit", "rock", "maniac", "lag", "tag", "shark"):
        out[opp] = _score(knobs, (opp,) * 5, n_hands, seed)
    return out


def run(n_hands: int = 2000) -> dict:
    random.seed(0)
    calib_vpip = _measure_vpip(PRINCEDARKNESS)
    result = {
        "profile": PRINCEDARKNESS.__dict__,
        "calibration": {"measured_vpip_pct": calib_vpip, "user_target_vpip_pct": 55.0,
                        "gate_ok": abs(calib_vpip - 55.0) <= 15.0},
        "style_vs_train": _score(PRINCEDARKNESS, _TRAIN, n_hands, seed=0),
        "style_vs_heldout": _score(PRINCEDARKNESS, _HELD, n_hands, seed=0),
        "tag_vs_train": _score(PROFILES["tag"], _TRAIN, n_hands, seed=0),
        "tag_vs_heldout": _score(PROFILES["tag"], _HELD, n_hands, seed=0),
        "style_per_opponent": _per_opponent(PRINCEDARKNESS),
    }
    json.dump(result, open("data/coach/style_sim.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return result


if __name__ == "__main__":
    r = run()
    print(f"calibration VPIP: {r['calibration']['measured_vpip_pct']}%  (gate_ok={r['calibration']['gate_ok']})")
    print(f"style vs TRAIN   : {r['style_vs_train']}")
    print(f"style vs HELDOUT : {r['style_vs_heldout']}")
    print(f"tag   vs TRAIN   : {r['tag_vs_train']}")
    print(f"tag   vs HELDOUT : {r['tag_vs_heldout']}")
    print("per-opponent (style):")
    for opp, s in r["style_per_opponent"].items():
        print(f"  {opp:>8}: {s['bb_per_100']:>7} bb/100  (std {s['std_bb']})")
    print("saved data/coach/style_sim.json")
