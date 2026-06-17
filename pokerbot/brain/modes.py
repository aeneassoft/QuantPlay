"""Compute MODES — the accuracy <-> time trade-off, made explicit (user directive, 2026-06-17).

The paradox the modes resolve: a live poker decision must land within the rules' time frame (seconds); if we try to
compute "too exactly", the mathematical reasoning over-runs that frame and the DECISION suffers. So accuracy is
BUDGETED per mode, not maximized. Conversely R&D may think LONG about a single decision and let us analyse the LLM's
behaviour — the framework must do both.

Modes (every accuracy<->time knob set by the ACTIVE one):
  FAST     ~1-2s  — snap live play (low MC iters, short reasoning).
  STANDARD ~1-5s  — the default live mode (the user's target window).
  DEEP     long   — R&D: think long about ONE decision, exact + sympy + full trace, for analysis.
  TRAIN    —       — RL self-play: throughput-tuned (many decisions/s; exactness off in the hot path).

Consumers read `current()`: `brain/api.equity` (MC iters), `training/rl_env.rollout_action_ev` (EV rollout k),
`brain/policy.QwenPolicy` (generation tokens + the executor wall-clock). Switch globally with `set_mode('deep')`, or
scope an analysis with `with modes.using('deep'): ...`.
"""
from __future__ import annotations

import contextlib
from dataclasses import dataclass


@dataclass(frozen=True)
class Mode:
    name: str
    time_budget_s: float     # soft wall-clock for ONE decision (executor enforces where SIGALRM exists)
    equity_iters: int        # MC equity samples — the dominant accuracy<->time lever
    rollout_k: int           # EV rollouts (RL reward / analysis)
    max_new_tokens: int      # brain reasoning/generation budget
    exact_threshold: bool    # exact Fraction for decision-threshold formula math (cheap; on except in the RL hot path)
    sympy_verify: bool       # symbolic verification (R&D only; slow)
    analysis: bool           # emit the full decision trace / diagnostics


FAST     = Mode("fast",     1.5,   300,   8,   160,  True,  False, False)
STANDARD = Mode("standard", 5.0,   1000,  16,  320,  True,  False, False)
DEEP     = Mode("deep",     180.0, 8000,  96,  2048, True,  True,  True)
TRAIN    = Mode("train",    20.0,  400,   16,  384,  False, False, False)

MODES = {m.name: m for m in (FAST, STANDARD, DEEP, TRAIN)}
_active = [STANDARD]


def current() -> Mode:
    return _active[0]


def set_mode(mode) -> Mode:
    m = mode if isinstance(mode, Mode) else MODES[str(mode).lower()]
    _active[0] = m
    return m


@contextlib.contextmanager
def using(mode):
    """Temporarily switch mode (e.g. `with modes.using('deep'):` for a one-off R&D analysis), then restore."""
    prev = _active[0]
    try:
        yield set_mode(mode)
    finally:
        _active[0] = prev
