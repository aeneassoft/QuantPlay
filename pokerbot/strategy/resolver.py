"""MVP#2 P1: RIVER resolver — real-time TexasSolver re-solve of the ACTUAL river public state (tracked ranges +
board + line), sampled for our hand. This is the situation-specific GTO fix for the river facing-bet-defense /
sizing leak (the biggest bleed in the measured -160 vs the solver). Solves to TERMINAL (river = 1 betting round)
so NO value net is needed. Floor-fallback (returns None) on solve timeout / failure / hand-not-in-range. HU only.

The opponent that beat us -160 in the head-to-head did exactly this (solve the spot live); here we do it in OUR
bot with line-aware ranges (range_tracker) + a floor fallback. Gate = the GTO Wizard AIVAT (the #1 benchmark).
"""
from __future__ import annotations

from pokerbot.strategy import gto_oracle as O
from pokerbot.strategy.gto_mode import flag as _flag

# S5 (plan 2026-07-04, POKERB_RSV_CENSUS via GTOW-mode): solve on GTO WIZARD'S MEASURED tree instead of the old
# lean one. The 12.5k-hand census (research/gtow_tree_census.py): river bets 35/65/100/150 (0.65 = the DOMINANT
# size the old 33/75 tree couldn't even represent), river raises 50/100; turn bets 35/75. Deeper iters/timeouts
# too — vs GTOW there is NO latency constraint (concurrency hides wall-clock; ~6s/decision is fine).
_CENSUS = _flag("POKERB_RSV_CENSUS", "0") == "1"

if _CENSUS:
    _RIVER_BETS = [
        "set_bet_sizes oop,river,bet,35,65,100,150", "set_bet_sizes oop,river,raise,50,100",
        "set_bet_sizes oop,river,allin",
        "set_bet_sizes ip,river,bet,35,65,100,150", "set_bet_sizes ip,river,raise,50,100",
        "set_bet_sizes ip,river,allin",
    ]
    # P6/3b (papers wave #5, Supremus rich-first-action sizing): +150 turn arm — the census shows GTOW barrels
    # 1.35-1.75x on turns ~10% of the time; without the arm our own solves cannot FIND the polarized barrel line
    # (feeds the river-value/aggression leaks). Gated POKERB_TURN_OVERBET (default OFF; in NO profile — built
    # as the P6 fallback-3b arm, never promoted; audit 2026-07-05 corrected this comment).
    _TURN_OB = ",150" if _flag("POKERB_TURN_OVERBET", "0") == "1" else ""
    _TURN_BETS = [
        f"set_bet_sizes oop,turn,bet,35,75{_TURN_OB}", "set_bet_sizes oop,turn,raise,75", "set_bet_sizes oop,turn,allin",
        f"set_bet_sizes ip,turn,bet,35,75{_TURN_OB}", "set_bet_sizes ip,turn,raise,75", "set_bet_sizes ip,turn,allin",
        "set_bet_sizes oop,river,bet,65,100", "set_bet_sizes oop,river,raise,60", "set_bet_sizes oop,river,allin",
        "set_bet_sizes ip,river,bet,65,100", "set_bet_sizes ip,river,raise,60", "set_bet_sizes ip,river,allin",
    ]
    _RIVER_ACC, _RIVER_ITERS, _RIVER_TIMEOUT = 0.25, 200, 90
    _TURN_ACC, _TURN_ITERS, _TURN_TIMEOUT = 0.4, 120, 150
else:
    # Compact river bet tree (bet 33/75 + a raise + allin, both positions) -> a small terminal solve -> fast.
    _RIVER_BETS = [
        "set_bet_sizes oop,river,bet,33,75", "set_bet_sizes oop,river,raise,60", "set_bet_sizes oop,river,allin",
        "set_bet_sizes ip,river,bet,33,75", "set_bet_sizes ip,river,raise,60", "set_bet_sizes ip,river,allin",
    ]
    # Compact TURN bet tree (turn + river sizes, both positions). The solver builds+solves the whole turn->river
    # subtree (so the turn strategy is river-aware) but we dump+read only the turn round (dump_rounds=1).
    _TURN_BETS = [
        "set_bet_sizes oop,turn,bet,50,100", "set_bet_sizes oop,turn,raise,60", "set_bet_sizes oop,turn,allin",
        "set_bet_sizes ip,turn,bet,50,100", "set_bet_sizes ip,turn,raise,60", "set_bet_sizes ip,turn,allin",
        "set_bet_sizes oop,river,bet,50,100", "set_bet_sizes oop,river,raise,60", "set_bet_sizes oop,river,allin",
        "set_bet_sizes ip,river,bet,50,100", "set_bet_sizes ip,river,raise,60", "set_bet_sizes ip,river,allin",
    ]
    _RIVER_ACC, _RIVER_ITERS, _RIVER_TIMEOUT = 0.5, 80, 40
    _TURN_ACC, _TURN_ITERS, _TURN_TIMEOUT = 0.5, 60, 60

# Shared solve knobs (identical for the turn + river solves).
_SOLVE_THREADS = 8        # TexasSolver worker threads per solve
_MIN_SOLVE_CHIPS = 2.0    # degeneracy floor: never hand the solver a zero/near-zero pot or stack


# PRINCE v2 L2b (papers wave #1, Brown&Sandholm nested re-solving): insert the OBSERVED villain bet sizes into the
# solve tree instead of letting _match_label ROUND them to the nearest grid arm (the census shows GTOW barrels
# 1.35-1.75x pot on turns ~10% of the time; rounding those onto our 0.75 arm makes hero defend at wrong pot odds).
# We solve AFTER observing the size -> exact insertion is free and strictly better. Gated, default OFF.
_SIZE_INJECT = _flag("POKERB_SIZE_INJECT", "0") == "1"
_INJECT_REL_TOL = 0.10          # a size within 10% (relative) of an existing arm is "on grid" -> no arm added
_INJECT_MAX_ARMS = 6            # tree-size guard: never grow a street's bet menu beyond this many arms
_INJECT_MAX_PCT = 200           # never inject shove-scale arms (>2x pot maps to the tree's allin, bug-hunt fix)


def _grid_of(bets, street, kind):
    """The numeric pot-% values currently in `bets` for (street, kind in {'bet','raise'})."""
    vals = set()
    for line in bets:
        parts = line.split(",")
        if len(parts) > 3 and parts[1] == street and parts[2] == kind:
            vals.update(float(v) for v in parts[3:])
    return vals


def _observed_fracs(state, street, pot_entering):
    """The pot-fraction of every bet/raise ALREADY MADE this street (census convention: first-in = increment/pot;
    raise = increment-over-call / pot-after-call). HU postflop actors strictly alternate starting OOP, so the
    action index determines the actor — no per-entry seat field needed.
    BUG-HUNT FIXES: (a) `pot_entering` IS the street's entering pot (both resolver callers pass it that way) —
    the old second reconstruction subtracted street commits TWICE; (b) all-in actions update the commit walk
    (no producer emits action=='allin' — engine + gtowizard label shoves 'bet'/'raise' — but stay defensive)."""
    acts = _street_actions(state, street)
    entering = max(1.0, float(pot_entering))
    out, c = [], [0.0, 0.0]                                # [even-index actor, odd-index actor] street commits
    for i, h in enumerate(acts):
        a, me, opp = h.get("action"), i % 2, (i + 1) % 2
        if a == "call":
            c[me] = c[opp]
        elif a in ("bet", "raise", "allin"):
            to = float(h.get("to") or h.get("amount") or 0)
            pot_before = entering + c[0] + c[1]
            to_call = max(0.0, c[opp] - c[me])
            frac = ((to - c[opp]) / max(1.0, pot_before + to_call)) if to_call > 0 else \
                   ((to - c[me]) / max(1.0, pot_before))
            if a != "allin" and frac > 0.01:               # a shove maps to the tree's allin arm — never inject it
                out.append(("raise" if to_call > 0 else "bet", frac))
            c[me] = to
    return out


def _inject_observed_sizes(state, street, pot_entering, bets):
    """A NEW bets list with any off-grid observed size appended to BOTH positions' menus (the actor side is what
    matters; adding to both is harmless and robust). Cache-safe: gto_oracle._cache_key hashes the bets list.
    pot_entering = the street's START pot (what both resolver callers pass — see bot.py start_pot)."""
    if not _SIZE_INJECT:
        return bets
    add = {}                                               # (street, kind) -> set of new values
    for kind, frac in _observed_fracs(state, street, pot_entering):
        v = round(frac * 100)
        # BUG-HUNT FIX: include the already-queued values so one call can't stack near-duplicates past the cap
        grid = _grid_of(bets, street, kind) | add.get((street, kind), set())
        if (5 <= v <= _INJECT_MAX_PCT and grid
                and all(abs(v - g) / g > _INJECT_REL_TOL for g in grid) and len(grid) < _INJECT_MAX_ARMS):
            add.setdefault((street, kind), set()).add(v)
    if not add:
        return bets
    new = []
    for line in bets:
        parts = line.split(",")
        key = (parts[1], parts[2]) if len(parts) > 3 else None
        if key in add:
            vals = sorted({float(v) for v in parts[3:]} | add[key])
            line = ",".join(parts[:3] + [f"{v:g}" for v in vals])
        new.append(line)
    return new


def _street_actions(state, street):
    """Postflop actions in `street`'s betting round (both players, in order) -> navigate the solve tree to our
    node. Only collects actions tagged with this street, so it naturally stops before the next street's deal."""
    acts, seen = [], False
    for h in state.get("history", []):
        if h.get("action") == "deal" and h.get("street") == street:
            seen = True
            continue
        if seen and h.get("street") == street and h.get("action") in (
                "check", "call", "bet", "raise", "allin", "fold"):
            acts.append(h)
    return acts


def _river_actions(state):
    return _street_actions(state, "river")


def _match_label(action, amount, node):
    """Engine action -> the solver child label at `node` (nearest BET/RAISE size by chips)."""
    acts = (node.get("strategy", {}) or {}).get("actions", []) or list((node.get("childrens") or {}).keys())
    kind = {"check": "CHECK", "call": "CALL", "fold": "FOLD"}.get(action)
    if kind:
        return next((a for a in acts if a.split()[0] == kind), None)
    want = "RAISE" if action == "raise" else ("ALLIN" if action == "allin" else "BET")
    cands = [(a, float(a.split()[1])) for a in acts if a.split()[0] == want and len(a.split()) > 1]
    if not cands and want != "BET":
        cands = [(a, float(a.split()[1])) for a in acts if a.split()[0] == "BET" and len(a.split()) > 1]
    if not cands:
        return next((a for a in acts if a.split()[0] == "ALLIN"), None)
    return min(cands, key=lambda c: abs(c[1] - (amount or 0)))[0]


def _label_to_action(lbl, la):
    """Solver label -> (engine action, amount). BET/RAISE amount = the bet-to (chips), clamped to legal."""
    kind = lbl.split()[0]
    if kind == "CHECK":
        return "check", None
    if kind == "CALL":
        return "call", None
    if kind == "FOLD":
        return "fold", None
    to = int(float(lbl.split()[1])) if len(lbl.split()) > 1 else la.get("raise_max")
    return ("bet" if la.get("is_bet") else "raise"), to


def river_resolve(state, hole, board, pot, eff_stack, oop_str, ip_str, la, rng,
                  acc: float = _RIVER_ACC, iters: int = _RIVER_ITERS, timeout: int = _RIVER_TIMEOUT):
    """Solve the river public state (tracked ranges) + sample our hand's GTO action. Returns (action, amount) or
    None (-> caller plays the floor). Navigates from the OOP first-to-act root following the river line to our node."""
    if not oop_str or not ip_str:
        return None
    try:
        bets = _inject_observed_sizes(state, "river", pot, _RIVER_BETS)   # L2b: solve with the TRUE observed sizes
        root = O.solve(board, oop_str, ip_str, pot=max(_MIN_SOLVE_CHIPS, pot),
                       eff_stack=max(_MIN_SOLVE_CHIPS, eff_stack),
                       bets=bets, accuracy=acc, max_iter=iters, dump_rounds=1, threads=_SOLVE_THREADS,
                       timeout=timeout, tag="rsv" + "".join(board))
    except Exception:  # noqa: BLE001
        return None
    node = root                                       # root = OOP first-to-act on the river
    for h in _river_actions(state):
        lbl = _match_label(h.get("action"), h.get("to") or h.get("amount"), node)
        ch = (node.get("childrens") or {}).get(lbl) if lbl else None
        if not ch or ch.get("node_type") == "chance_node":
            return None
        node = ch
    strat = O.strategy_for(node, hole[0], hole[1])
    if not strat:
        return None
    labels = list(strat.keys())
    probs = [max(0.0, p) for p in strat.values()]
    if sum(probs) <= 0:
        return None
    lbl = rng.choices(labels, weights=probs)[0]
    return _label_to_action(lbl, la)


def turn_resolve(state, hole, board, pot, eff_stack, oop_str, ip_str, la, rng,
                 acc: float = _TURN_ACC, iters: int = _TURN_ITERS, timeout: int = _TURN_TIMEOUT):
    """MVP#2 P2: solve the TURN subgame (turn+river, to terminal) + sample our hand's GTO TURN action. Returns
    (action, amount) or None (-> floor). We decide on the turn; the river subtree is solved (so the turn strategy
    is river-aware) but we navigate ONLY the turn betting line + read our turn node. board = 4 cards. Bigger tree
    than the river -> lower iters + a floor-fallback on timeout/failure keeps it live-safe."""
    if not oop_str or not ip_str:
        return None
    try:
        bets = _inject_observed_sizes(state, "turn", pot, _TURN_BETS)     # L2b: solve with the TRUE observed sizes
        root = O.solve(board, oop_str, ip_str, pot=max(_MIN_SOLVE_CHIPS, pot),
                       eff_stack=max(_MIN_SOLVE_CHIPS, eff_stack),
                       bets=bets, accuracy=acc, max_iter=iters, dump_rounds=1, threads=_SOLVE_THREADS,
                       timeout=timeout, tag="tsv" + "".join(board))
    except Exception:  # noqa: BLE001
        return None
    node = root                                       # root = OOP first-to-act on the turn
    for h in _street_actions(state, "turn"):
        lbl = _match_label(h.get("action"), h.get("to") or h.get("amount"), node)
        ch = (node.get("childrens") or {}).get(lbl) if lbl else None
        if not ch or ch.get("node_type") == "chance_node":
            return None
        node = ch
    strat = O.strategy_for(node, hole[0], hole[1])
    if not strat:
        return None
    labels = list(strat.keys())
    probs = [max(0.0, p) for p in strat.values()]
    if sum(probs) <= 0:
        return None
    lbl = rng.choices(labels, weights=probs)[0]
    return _label_to_action(lbl, la)
