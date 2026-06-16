"""MVP#2 P1: RIVER resolver — real-time TexasSolver re-solve of the ACTUAL river public state (tracked ranges +
board + line), sampled for our hand. This is the situation-specific GTO fix for the river facing-bet-defense /
sizing leak (the biggest bleed in the measured -160 vs the solver). Solves to TERMINAL (river = 1 betting round)
so NO value net is needed. Floor-fallback (returns None) on solve timeout / failure / hand-not-in-range. HU only.

The opponent that beat us -160 in the head-to-head did exactly this (solve the spot live); here we do it in OUR
bot with line-aware ranges (range_tracker) + a floor fallback. Gate = the GTO Wizard AIVAT (the #1 benchmark).
"""
from __future__ import annotations

from pokerbot.strategy import gto_oracle as O

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
                  acc: float = 0.5, iters: int = 80, timeout: int = 40):
    """Solve the river public state (tracked ranges) + sample our hand's GTO action. Returns (action, amount) or
    None (-> caller plays the floor). Navigates from the OOP first-to-act root following the river line to our node."""
    if not oop_str or not ip_str:
        return None
    try:
        root = O.solve(board, oop_str, ip_str, pot=max(2.0, pot), eff_stack=max(2.0, eff_stack),
                       bets=_RIVER_BETS, accuracy=acc, max_iter=iters, dump_rounds=1, threads=8,
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
                 acc: float = 0.5, iters: int = 60, timeout: int = 60):
    """MVP#2 P2: solve the TURN subgame (turn+river, to terminal) + sample our hand's GTO TURN action. Returns
    (action, amount) or None (-> floor). We decide on the turn; the river subtree is solved (so the turn strategy
    is river-aware) but we navigate ONLY the turn betting line + read our turn node. board = 4 cards. Bigger tree
    than the river -> lower iters + a floor-fallback on timeout/failure keeps it live-safe."""
    if not oop_str or not ip_str:
        return None
    try:
        root = O.solve(board, oop_str, ip_str, pot=max(2.0, pot), eff_stack=max(2.0, eff_stack),
                       bets=_TURN_BETS, accuracy=acc, max_iter=iters, dump_rounds=1, threads=8,
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
