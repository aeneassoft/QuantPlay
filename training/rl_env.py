"""The 6-max RL REWARD ENVIRONMENT (Phase 4) — wraps pokerbot/engine/table.py (the env) + pokerbot/arena/sixmax.py
(the opponent LEAGUE) so a hero POLICY can be scored by REALIZED EV (bb/100). This is BOTH the GRPO reward signal and
the de-risk pilot's measuring stick. Deterministic given a seed.

A policy is any callable `policy(table, seat) -> (action: str, amount_chips: int | None)`:
  * the Qwen brain  -> spot_from_table -> emit a program -> executor -> (action, amount)   (Phase-4 GRPO)
  * a league bot    -> obs_for -> decide                                                    (self-play / baselines)
The hero seat is fixed (default 0) but the BUTTON rotates each hand, so the hero plays every position over a run.
Per-hand net = realized chips won − chips committed (chips are conserved within a hand -> a zero-sum invariant we test).
Per docs/plans/QWEN_6MAX_PLAN.md.
"""
from __future__ import annotations

import copy
import random
import statistics

from pokerbot.arena.sixmax import PROFILES, SixMaxBot
from pokerbot.brain import modes
from pokerbot.engine.table import Table

# Train vs HELD-OUT league split (robustness): the policy trains against TRAIN_LEAGUE; eval/robustness uses
# HELDOUT_LEAGUE — distinct opponent TYPES it never saw = the empirical surrogate for 'strong robustness to incomplete
# information' (CLAUDE.md / Einy et al.). Beating the train league but losing to a held-out type is NOT robust GTO.
TRAIN_LEAGUE = ("tag", "lag", "nit", "station", "maniac")
HELDOUT_LEAGUE = ("rock", "whale", "shark")


def league_policy(bot: SixMaxBot):
    """Wrap a SixMaxBot as a policy(table, seat). The bot is exposed as `_p.bot` so a CRN caller (rollout_action_ev) can
    reseed its mixing RNG per rollout — without that the HERO continuation is the one uncontrolled randomness source."""
    def _p(table, seat):
        d = bot.decide(table.obs_for(seat))
        return d["action"], d.get("amount")
    _p.bot = bot
    return _p


def _play_loop(table: Table, policies: dict, observers: list) -> None:
    """Drive the table from the current to_act until the hand ends. Illegal actions -> check>call>fold (engine=truth)."""
    guard = 0
    while not table.hand_over and table.to_act is not None:
        guard += 1
        if guard > 600:                                    # safety against a pathological loop
            break
        seat = table.to_act
        street, pre = table.street, table.preflop_raises
        to_call = table.legal_actions().get("to_call", 0)
        try:
            action, amount = policies[seat](table, seat)
            table.act(action, amount)
        except Exception:                                   # noqa: BLE001 — illegal/garbage -> safe fallback
            la = table.legal_actions()
            fb = "check" if la.get("can_check") else ("call" if la.get("can_call") else "fold")
            table.act(fb)
        taken = table.history[-1].get("action") if table.history else None
        if taken:
            for ob in observers:
                ob.observe(seat, street, taken, to_call, pre)


def play_hand(table: Table, policies: dict, observers: list) -> dict:
    """Play ONE hand to completion. `policies` = {seat: policy}; `observers` = league bots (opp-model upkeep).
    Returns {seat: net_chips_this_hand}."""
    table.start_hand()
    start = {i: table.seats[i].stack + table.seats[i].committed_total for i in range(table.n)}
    for ob in observers:
        ob.new_hand(list(range(table.n)))
    _play_loop(table, policies, observers)
    return {i: table.seats[i].stack - start[i] for i in range(table.n)}


def make_league(profiles: list[str], hero_seat: int = 0, seed: int | None = None) -> dict:
    """Build SixMaxBots for every seat EXCEPT hero_seat, cycling through `profiles`. Returns {seat: bot}.
    If `seed` is given, each bot's rng is seeded deterministically -> identical opponents across paired rollouts
    (Common Random Numbers: card luck AND opponent mixing cancel when comparing two candidate actions)."""
    bots = {}
    j = 0
    for seat in range(len(profiles) + 1):
        if seat == hero_seat:
            continue
        bot = SixMaxBot(seat, PROFILES[profiles[j % len(profiles)]])
        if seed is not None:
            bot.rng = random.Random(seed * 1000 + seat)
        bots[seat] = bot
        j += 1
    return bots


def evaluate_policy(hero_policy, profiles=("tag", "lag", "nit", "station", "maniac"),
                    n_hands: int = 500, seed: int = 0, hero_seat: int = 0,
                    starting_stack: int = 10000, sb: int = 50, bb: int = 100) -> dict:
    """Score `hero_policy` over `n_hands` vs a 5-bot league. Returns {bb_per_100, n, total_bb, std_bb}."""
    names = [f"seat{i}" for i in range(len(profiles) + 1)]
    table = Table(names, starting_stack=starting_stack, sb=sb, bb=bb, seed=seed, human_seat=hero_seat)
    bots = make_league(list(profiles), hero_seat=hero_seat)
    policies = {hero_seat: hero_policy}
    for seat, bot in bots.items():
        policies[seat] = league_policy(bot)
    observers = list(bots.values())
    nets_bb = []
    for _ in range(n_hands):
        nets = play_hand(table, policies, observers)
        nets_bb.append(nets[hero_seat] / bb)
    total = sum(nets_bb)
    return {"bb_per_100": round(total / n_hands * 100, 2), "n": n_hands, "total_bb": round(total, 1),
            "std_bb": round(statistics.pstdev(nets_bb), 2) if len(nets_bb) > 1 else 0.0}


def selfplay_zero_sum_check(profiles=("tag", "lag", "nit", "station", "maniac", "tag"),
                            n_hands: int = 200, seed: int = 0, bb: int = 100) -> dict:
    """Self-play sanity: ALL seats are league bots. Returns per-seat bb/100 + the max |sum-of-all-nets| (must be 0)."""
    names = [f"seat{i}" for i in range(len(profiles))]
    table = Table(names, starting_stack=10000, sb=50, bb=bb, seed=seed, human_seat=-1)
    bots = {i: SixMaxBot(i, PROFILES[p]) for i, p in enumerate(profiles)}
    policies = {i: league_policy(b) for i, b in bots.items()}
    observers = list(bots.values())
    totals = {i: 0.0 for i in range(len(profiles))}
    worst_residual = 0.0
    for _ in range(n_hands):
        nets = play_hand(table, policies, observers)
        worst_residual = max(worst_residual, abs(sum(nets.values())))   # chips conserved -> 0 every hand
        for i, v in nets.items():
            totals[i] += v / bb
    return {"per_seat_bb_per_100": {f"{i}:{profiles[i]}": round(t / n_hands * 100, 1) for i, t in totals.items()},
            "worst_hand_residual_chips": worst_residual}


# ---------------------------------------------------------------- rollout EV (de-risk pilot + GRPO reward core)
def _reseed_for_rollout(table: Table, seed: int) -> None:
    """Fresh future: re-shuffle the REMAINING (undealt) deck so each rollout draws a different run-out. Already-dealt
    cards (hole cards on seats, the current board) are preserved -> we fix the realized deal, vary only what's to come."""
    table.rng = random.Random(seed)
    if table.deck is not None:
        table.deck.rng = table.rng
        table.rng.shuffle(table.deck.cards)


def _reset_cont(cont_policy, rollout_seed: int) -> None:
    """Reset the HERO continuation bot to FRESH-construction state + a deterministic per-rollout seed. The cont bot gets
    only decide() in rollouts (never new_hand/observe), so without this its per-hand fields leak across rollouts and its
    UNSEEDED rng makes mixing non-deterministic — so the reward differed by call-history (and shared-bot vs fresh-bot).
    Resetting per rollout makes each rollout an independent fresh hand AND makes the reward identical sequential==parallel."""
    b = getattr(cont_policy, "bot", None)
    if b is None:
        return
    if hasattr(b, "opp"):
        b.opp.clear()
    if hasattr(b, "_new_hand_state"):
        b._new_hand_state([])
    if hasattr(b, "rng"):
        b.rng = random.Random(rollout_seed * 911 + 17)


def rollout_action_ev(snapshot: Table, hero_seat: int, action: str, amount, cont_policy,
                      profiles=("tag", "lag", "nit", "station", "maniac"), k: int | None = None,
                      base_seed: int = 0, bb: int = 100) -> float:
    """Mean hero net (in bb) of taking (action, amount) AT the snapshot, then playing the hand out `k` times with fresh
    run-outs (hero continues via `cont_policy`, others via a fresh league). Measured from the snapshot stack =>
    EV RELATIVE TO FOLDING NOW (fold => 0). deepcopy per rollout => the snapshot is never mutated (reusable per candidate).
    This is the de-risk pilot's candidate-ranking signal AND the GRPO realized-EV reward core. `k` defaults to the ACTIVE
    compute mode's rollout_k (brain/modes.py — the accuracy<->time lever for EV precision)."""
    if k is None:
        k = modes.current().rollout_k
    nets = []
    for r in range(k):
        rollout_seed = base_seed * 100003 + r + 1
        t = copy.deepcopy(snapshot)
        _reseed_for_rollout(t, rollout_seed)
        bots = make_league(list(profiles), hero_seat=hero_seat, seed=rollout_seed)   # CRN: same opponents per r
        _reset_cont(cont_policy, rollout_seed)        # clean + deterministically-seeded HERO continuation per rollout ->
        policies = {hero_seat: cont_policy}            # each rollout = an independent fresh hand; reward CRN-pure + parallel==seq
        for s, b in bots.items():
            policies[s] = league_policy(b)
        base = t.seats[hero_seat].stack
        try:
            t.act(action, amount)
        except Exception:                                   # noqa: BLE001 — illegal candidate -> safe fallback
            la = t.legal_actions()
            t.act("check" if la.get("can_check") else ("call" if la.get("can_call") else "fold"))
        _play_loop(t, policies, list(bots.values()))
        nets.append((t.seats[hero_seat].stack - base) / bb)
    return sum(nets) / len(nets) if nets else 0.0


def gen_decision_states(profiles=("tag", "lag", "nit", "station", "maniac"), hero_seat: int = 0,
                        n_states: int = 50, seed: int = 0):
    """Play self-play and SNAPSHOT (deepcopy) the table at each hero-seat decision. Yields (snapshot_table, spot).
    The hero seat plays a tag continuation in the main game so the game advances + states stay diverse."""
    from pokerbot.brain.format_spot import spot_from_table
    names = [f"seat{i}" for i in range(len(profiles) + 1)]
    table = Table(names, seed=seed, human_seat=hero_seat)
    pl = list(profiles)
    allbots, j = {}, 0
    for s in range(len(profiles) + 1):
        if s == hero_seat:
            allbots[s] = SixMaxBot(s, PROFILES["tag"])
        else:
            allbots[s] = SixMaxBot(s, PROFILES[pl[j % len(pl)]])
            j += 1
    policies = {s: league_policy(b) for s, b in allbots.items()}
    observers = list(allbots.values())
    out = 0
    while out < n_states:
        table.start_hand()
        for ob in observers:
            ob.new_hand(list(range(table.n)))
        guard = 0
        while not table.hand_over and table.to_act is not None:
            if out >= n_states:
                return
            guard += 1
            if guard > 600:
                break
            seat = table.to_act
            if seat == hero_seat:
                yield copy.deepcopy(table), spot_from_table(table, seat)
                out += 1
            street, pre = table.street, table.preflop_raises
            to_call = table.legal_actions().get("to_call", 0)
            try:
                a, amt = policies[seat](table, seat)
                table.act(a, amt)
            except Exception:                               # noqa: BLE001
                la = table.legal_actions()
                table.act("check" if la.get("can_check") else ("call" if la.get("can_call") else "fold"))
            taken = table.history[-1].get("action") if table.history else None
            if taken:
                for ob in observers:
                    ob.observe(seat, street, taken, to_call, pre)
