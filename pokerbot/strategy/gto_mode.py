"""GTOW mode (S1 of the ENGINE->GTOW plan, 2026-07-04): ONE switch that configures the engine for MINIMAL
EXPLOITABILITY vs a near-GTO opponent (GTO Wizard) instead of exploit-primary vs a leaky field.

POKERB_GTO_MODE=1 expands into individually-overridable sub-flags (os.environ.setdefault -> any explicitly-set
sub-flag wins, so single-flag ablation arms stay possible). Call apply() BEFORE importing pokerbot.strategy
modules — postflop.py/advisor.py read their flags at IMPORT time. Default OFF = the product is byte-identical.
"""
from __future__ import annotations

import os

PROFILE = {
    "POKERB_EXPLOIT": "0",         # no exploit-primary deviations vs near-GTO (also starves the river probe path)
    "POKERB_RIVER_VALUE": "0.75",  # river value-bet floor (measured +23.0 +/- 11.4 vs GTOBaseline, GTOW-grade-neutral)
    "POKERB_RIVER_LA": "1",        # line-aware river advisor (borderline; kept as its own ablation arm)
    "POKERB_ONTREE": "1",          # postflop bet snap (already the default; explicit for the run fingerprint)
    "POKERB_GTO_FOLD_PRIOR": "1",  # drop PriorFoldModel's +0.04 "they over-fold" assumption (an exploit prior)
    # S2 — the weighted_ranges fix (the resolver's input; the documented "fires 93% on a WRONG equilibrium"):
    "POKERB_TRACKER_ALPHA": "0.5",       # damp the marginal-frequency Bayes updates (kills the check/check inversion)
    "POKERB_TRACKER_CONF_SLOPE": "0.7",  # revive the confidence gate (100%-unmodeled reconstructions now gate)
    # S3 — off-tree fixes, calibrated by the 12.5k-hand GTOW tree census (research/gtow_tree_census.py):
    "POKERB_GTOW_TREE": "1",       # street-specific census BET grid (adds GTOW's dominant river 0.65 + the 1.5x)
    "POKERB_ONTREE_RAISES": "1",   # snap postflop RAISES to the census raise grid (the 64-85% off-tree slice)
    "POKERB_GTOW_SIZES": "1",      # census preflop sizes (open 2.25 / 3bet 9 / 4bet 27 / 5bet 67.5)
    "POKERB_GTOW_NOLIMP": "1",     # SB root: renormalize limp->open/fold (GTOW's tree has no limp)
    # S5 — resolver on GTOW's measured tree (adds the dominant river 0.65 + 1.5x) + deeper iters (no latency
    # constraint vs GTOW); the persistent solve cache is independently ON by default (semantics-neutral).
    "POKERB_RSV_CENSUS": "1",
}

# VERSION "PRINCE" (docs/VERSION_PRINCE.md): the GTO-mode base + the deception layer (the user-found leak fixes,
# 2026-07-04: turn over-fold 44% vs 33% MDF; transparent check range P(K|check)=9%). POKERB_PRINCE=1 expands to
# GTO_MODE + these. Gated: canary PASSED (paired +39.1 +/- 19.9); enters the product only after the mechanics probe.
PRINCE_PROFILE = {
    "POKERB_GTO_MODE": "1",
    "POKERB_TURN_DEFENSE": "0.07",  # MDF-calibrated turn defense (canary+mechanics PASSED 2026-07-04)
    "POKERB_SLOWPLAY": "0.25",      # trap 25% of strong flop hands (canary+mechanics PASSED 2026-07-04)
    # PRINCE v2 levers (2026-07-05, post bug-hunt: 23 confirmed fixes; gates on the FIXED code):
    "POKERB_LINE_U": "1",           # per-hand line-draw -> coherent barrel/give-up lines (canary passes; replay ok)
    "POKERB_RIVER_ECALL": "1",      # river value size from tracked-range e_call/F (canary BETTER >=2SE: +133.8+/-60)
    "POKERB_SIZE_INJECT": "1",      # solve with the TRUE observed villain sizes (unit-gated; floor-0 correctness fix)
    # The Kc3h 200bb-stack-off fix (2026-07-05; the fat-tail/leaderboard-std lever). Gates: disaster-hand probe
    # (river call->FOLD), replay (no regression), paired canary (+20.5 +/- 42.5, passes):
    "POKERB_TRACKER_AGGRO_FULL": "1",   # believe the narrowing fully (alpha->1) from a seat's 2nd barrel on
    # v3 (2026-07-05): the top-2 over-fold classes. Gates: stress 20/20 · replay flips 8/9 graded flop-fold
    # blunders · paired Analyzer 17.93 vs v2.2's 20.66 (-2.73 on identical deals) · tail-smoke 0 catastrophes:
    "POKERB_PAIR_DEFENSE": "0.10",      # flop: advisor-fold cap 0.30 + MDF discount for hole-pairs vs single c-bet
    "POKERB_RIVER_DEFENSE": "0.06",     # river: defend bluffcatchers vs <=0.6-pot bets (23% of folds were ahead)
}

# every flag that defines a run — logged as the config fingerprint next to any measured number.
# AUDIT FIX (2026-07-05, confirmed 3x): gate/lever flags OUTSIDE the profiles were invisible here, so a
# lever arm's export printed a fingerprint byte-identical to plain v3 — the graded artifact carried no
# record of the lever under test. Every behavior-changing flag must be listed, profile-carried or not.
_FINGERPRINT_KEYS = sorted(set(PROFILE) | set(PRINCE_PROFILE) | {
    "POKERB_GTO_MODE", "POKERB_PRINCE", "POKERB_TOCALL_FIX", "POKERB_RESOLVER", "POKERB_TURN_RESOLVER",
    "POKERB_BLUEPRINT", "POKERB_RANGE_TRACKER", "POKERB_COMMIT_CAP", "POKERB_ONTREE_RAISES",
    # gate/lever flags (default OFF, tested as their own arms):
    "POKERB_RIVER_THIN_SEL", "POKERB_RAISE_NARROW", "POKERB_BARREL_DISCIPLINE", "POKERB_TURN_PROBE",
    "POKERB_CBET_DAMP", "POKERB_TURN_DEF_ADVISOR", "POKERB_TURN_OVERBET", "POKERB_AUDIT_FIX",
    "POKERB_ADVISOR_ROLE_POS",
    # run-defining strategy swaps:
    "POKERB_DEEPCFR", "POKERB_GRAFT", "POKERB_RIVER_VALUE_FREQ", "POKERB_COMMIT_EQ",
})


def enabled() -> bool:
    # BUG-HUNT FIX: an EXPLICIT POKERB_GTO_MODE (e.g. "0" in an ablation arm) must win over PRINCE's implication —
    # the old unconditional OR silently kept the base profile on while direct env readers honored the "0".
    v = os.environ.get("POKERB_GTO_MODE")
    if v is not None:
        return v == "1"
    return prince_enabled()


def prince_enabled() -> bool:
    return os.environ.get("POKERB_PRINCE", "0") == "1"


def flag(name: str, default: str) -> str:
    """Import-order-safe flag read: explicit env wins, else PRINCE (if on), else the mode profile (if on),
    else the default. Strategy modules read via this instead of os.environ.get so the profile applies no
    matter which module got imported first (the import-order trap that silently dropped sub-flags)."""
    v = os.environ.get(name)
    if v is not None:
        return v
    if prince_enabled() and name in PRINCE_PROFILE:
        return PRINCE_PROFILE[name]
    if enabled() and name in PROFILE:
        return PROFILE[name]
    return default


def apply() -> bool:
    """Expand the profile(s) (no-op unless POKERB_GTO_MODE=1 or POKERB_PRINCE=1). Returns whether a mode is on.
    PRINCE expands first (it sets POKERB_GTO_MODE=1 itself), then the GTO-mode base fills the rest."""
    if prince_enabled():
        for k, v in PRINCE_PROFILE.items():
            os.environ.setdefault(k, v)
    if not enabled():
        return False
    for k, v in PROFILE.items():
        os.environ.setdefault(k, v)
    return True


def fingerprint() -> dict:
    """The env slice that defines a measured run — print/log this next to every AIVAT / grading number."""
    return {k: os.environ.get(k) for k in _FINGERPRINT_KEYS}
