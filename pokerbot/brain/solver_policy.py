"""SEARCH-AT-INFERENCE policy: the brain DRIVES a live TexasSolver solve to pick its postflop action (ReBeL/
Pluribus-style — the LLM/blueprint orchestrates, the exact solver gives the strategy). This is the highest-value
GTO move from our research and it is LOCAL + $0 (TexasSolver runs on CPU in ms).

`SolverSearchPolicy` is a `policy(table, seat) -> (action, amount_chips)` (the training/rl_env.py protocol, so it
plugs straight into evaluate_policy / the self-play eval). On each decision it builds the canonical brain Spot
(format_spot.spot_from_table), asks `api.solve_node(spot)` for the solver's GTO mix, samples an action, and legalizes
it via `api.legalize`. When the spot is UNSOLVABLE (preflop, multiway, or the solver can't navigate the line) it FALLS
BACK to a provided floor policy.

HONEST coverage limit (NOT a bug): TexasSolver is 2-player, so solve_node only fires HEADS-UP postflop. In 6-max many
spots are multiway or preflop and FALL BACK to the floor — `self.solved` / `self.fell_back` expose that rate. The HU
postflop ranges are WIDE single-raised-pot defaults PLUS hero's own class force-added (so hero's hand is always in the
acting node's range -> measured HU solve-rate ~1.0, 25/25 in the 2026-06-18 smoke), but they are still NOT line-aware
(3bet/limped/continuation ranges are inexact). Both are documented limits of search-at-inference with a HU solver, to
be lifted by multiway abstraction + line-aware ranges later.
"""
from __future__ import annotations

import random

from pokerbot.brain import api
from pokerbot.brain.format_spot import spot_from_table


def _default_fallback(seat: int, seed: int):
    """The protocol-native FLOOR for a Table: a SixMaxBot (TAG) wrapped as policy(table, seat). SixMaxBot is the
    Table's decision engine (it consumes obs_for and reuses the same postflop primitives as PokerBot), so it IS the
    6-max floor here — PokerBot.decide() needs the HU game's state() dict, which a Table does not produce."""
    from pokerbot.arena.sixmax import PROFILES, SixMaxBot
    from training.rl_env import league_policy
    bot = SixMaxBot(seat, PROFILES["tag"])
    bot.rng = random.Random(seed)
    return league_policy(bot)


class SolverSearchPolicy:
    """A `policy(table, seat)` that decides POSTFLOP via a live solver solve, else falls back to `fallback`.

    fallback: any `policy(table, seat) -> (action, amount_chips)`. Default = a SixMaxBot-TAG floor (see _default_fallback).
    seed:     RNG seed for SAMPLING the solver's mixed strategy (the solve itself is deterministic + cached by board).
    """

    def __init__(self, seat: int = 0, fallback=None, seed: int = 0):
        self.seat = seat
        self.rng = random.Random(seed)
        self.fallback = fallback if fallback is not None else _default_fallback(seat, seed + 99)
        self.solved = 0          # decisions taken from a live solve (the solver actually FIRED)
        self.fell_back = 0       # decisions taken from the floor (unsolvable spot — coverage limit)

    def __call__(self, table, seat):
        spot = spot_from_table(table, seat)
        s = api.solve_node(spot)
        if not s:
            self.fell_back += 1
            return self.fallback(table, seat)
        sizes = s.get("_sizes_bb", {})
        actions = [a for a in s if a != "_sizes_bb"]
        weights = [max(0.0, s[a]) for a in actions]
        if sum(weights) <= 0:                                # degenerate mix -> treat as unsolvable
            self.fell_back += 1
            return self.fallback(table, seat)
        action = self.rng.choices(actions, weights=weights)[0]
        size_bb = sizes.get(action) if action in ("bet", "raise") else None   # TOTAL bet in bb from the solver label
        self.solved += 1
        return api.legalize(spot, action, size_bb)           # -> (action, amount_chips); engine = legality truth
