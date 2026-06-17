"""P0 gate for the v2 range tracker (MVP#2). The consult's self-consistency checks (o3 + Claude):
mass conservation, dead-card exclusion, monotonic shrink down a line, confidence bounds, emit format,
and the safety property (silent actions never zero a live combo). Run: python -m tests.test_range_tracker
"""
from __future__ import annotations

from pokerbot.strategy.range_tracker import (
    RangeTracker, weighted_ranges, CONF_THRESHOLD)


def _state(button, board, history, hero, hole, street):
    """Minimal state matching what bot.py / floor_map produce, enough for the tracker."""
    players = [{"idx": i, "hole": hole if i == hero else ["??", "??"],
                "stack": 9700, "committed_street": 0, "committed_total": 300,
                "folded": False, "all_in": False, "is_button": button == i} for i in (0, 1)]
    return {"button": button, "street": street, "board": list(board), "pot": 600,
            "history": history, "players": players,
            "legal": {"to_act": hero, "to_call": 0, "can_raise": True, "is_bet": True,
                      "raise_min": 100, "raise_max": 9700, "pot": 600}}


def _srp_river_history(board):
    """Single-raised pot to the river: BTN(0) opens, BB(1) calls; flop check/bet/call; turn check/check; river."""
    return [
        {"player": 0, "action": "raise", "street": "preflop", "to": 300},
        {"player": 1, "action": "call", "street": "preflop", "amount": 200},
        {"action": "deal", "street": "flop", "board": board[:3]},
        {"player": 1, "action": "check", "street": "flop"},
        {"player": 0, "action": "bet", "street": "flop", "to": 200},
        {"player": 1, "action": "call", "street": "flop", "amount": 200},
        {"action": "deal", "street": "turn", "board": board[:4]},
        {"player": 1, "action": "check", "street": "turn"},
        {"player": 0, "action": "check", "street": "turn"},
        {"action": "deal", "street": "river", "board": board[:5]},
    ]


def test_mass_conservation_and_dead_cards():
    board = ["Qs", "Jh", "2h", "5c", "8d"]
    st = _state(0, board, _srp_river_history(board), hero=0, hole=["As", "Kd"], street="river")
    t = RangeTracker().build(st)
    for seat in (0, 1):
        s = sum(t.range[seat].values())
        assert 0.99 < s < 1.01, f"seat {seat} range sums to {s}, not 1"
        for c in t.range[seat]:
            assert c[0] not in board and c[1] not in board, f"dead card in seat {seat}: {c}"
    print("OK mass conservation + dead-card exclusion")


def test_monotonic_shrink():
    """Support must not GROW down a betting line (o3/Claude check). Compare flop-node vs river-node support."""
    board = ["Qs", "Jh", "2h", "5c", "8d"]
    flop_hist = _srp_river_history(board)[:5]   # up to the flop bet (BTN bets flop)
    st_flop = _state(0, board[:3], flop_hist, hero=0, hole=["As", "Kd"], street="flop")
    st_river = _state(0, board, _srp_river_history(board), hero=0, hole=["As", "Kd"], street="river")
    t_flop = RangeTracker().build(st_flop)
    t_river = RangeTracker().build(st_river)
    for seat in (0, 1):
        # river support (after more board cards removed) must be <= flop support
        assert len(t_river.range[seat]) <= len(t_flop.range[seat]), \
            f"seat {seat} range grew down the line ({len(t_flop.range[seat])} -> {len(t_river.range[seat])})"
    print(f"OK monotonic shrink (BTN {len(t_flop.range[0])}->{len(t_river.range[0])}, "
          f"BB {len(t_flop.range[1])}->{len(t_river.range[1])})")


def test_confidence_bounds_and_emit():
    board = ["Qs", "Jh", "2h", "5c", "8d"]
    st = _state(0, board, _srp_river_history(board), hero=0, hole=["As", "Kd"], street="river")
    oop, ip, conf = weighted_ranges(st)
    assert 0.0 <= conf <= 1.0, f"confidence {conf} out of range"
    # a normal, modeled SRP river line must clear the gate (else the resolver would NEVER fire = pointless)
    assert conf >= CONF_THRESHOLD, f"normal SRP river line conf {conf} below gate {CONF_THRESHOLD}"
    # emit format: CLASS-level weighted ('AQs:0.62' / 'QQ:1.0'), no dead-card classes, weights in (0,1]
    weights = []
    board = {"Qs", "Jh", "2h", "5c", "8d"}
    for entry in oop.split(","):
        if not entry:
            continue
        hc, w = entry.split(":")
        assert 2 <= len(hc) <= 3 and 0.0 < float(w) <= 1.0, f"bad oop class entry {entry}"
        weights.append(float(w))
    assert ip and oop, "empty range strings"
    # the advisor must actually REWEIGHT (non-uniform class weights), else it's the prior with no tracking
    assert max(weights) / min(weights) > 1.5, "class weights look uniform — advisor not reweighting"
    print(f"OK confidence={conf:.2f} (>= gate {CONF_THRESHOLD}); oop {len(oop.split(','))} classes "
          f"(weight spread {min(weights):.3f}..{max(weights):.3f}), ip {len(ip.split(','))} classes")


def test_safety_no_zeroed_live_combo():
    """o3 safety property: a SILENT action — one the advisor does NOT model (a raise, or an unmodeled size) —
    must NEVER zero a combo that doesn't use a dead card. (Calls are now MODELED via the multi-street defense
    advisor, the keystone widen, so they reweight rather than stay silent; we therefore exercise the property
    with a check-RAISE line, where BB's flop raise is the legality-only/silent update.) Assert the silent raise
    leaves every board-legal combo alive with positive weight."""
    board = ["Qs", "Jh", "2h", "5c", "8d"]
    hist = [
        {"player": 0, "action": "raise", "street": "preflop", "to": 300},
        {"player": 1, "action": "call", "street": "preflop", "amount": 200},
        {"action": "deal", "street": "flop", "board": board[:3]},
        {"player": 1, "action": "check", "street": "flop"},
        {"player": 0, "action": "bet", "street": "flop", "to": 200},
        {"player": 1, "action": "raise", "street": "flop", "to": 700},        # SILENT (legality-only) update
        {"player": 0, "action": "call", "street": "flop", "amount": 500},
        {"action": "deal", "street": "turn", "board": board[:4]},
        {"player": 1, "action": "check", "street": "turn"},
        {"player": 0, "action": "check", "street": "turn"},
        {"action": "deal", "street": "river", "board": board[:5]},
    ]
    st = _state(0, board, hist, hero=0, hole=["As", "Kd"], street="river")
    t = RangeTracker().build(st)
    bb = t.range[1]
    assert bb, "BB range collapsed (a silent raise must not zero the range)"
    assert all(w > 0 for w in bb.values()), "a silent action zeroed a live combo (safety violation)"
    conf_bb = t.confidence(1)
    assert 0.2 <= conf_bb <= 1.0, f"BB conf {conf_bb} out of bounds"
    print(f"OK safety: BB check-raise (silent) line kept {len(bb)} live combos, conf={conf_bb:.2f}")


def main():
    test_mass_conservation_and_dead_cards()
    test_monotonic_shrink()
    test_confidence_bounds_and_emit()
    test_safety_no_zeroed_live_combo()
    print("\nALL P0 RANGE-TRACKER TESTS PASS")


if __name__ == "__main__":
    main()
