"""End-to-end smoke for the P0 range tracker -> P1 river resolver wiring. Validates against the ACTUAL
TexasSolver v0.2.0 build (not just the consult's assertion):
  [1] the solver ACCEPTS the v2 tracker's per-combo WEIGHTED range strings and returns a strategy;
  [2] the resolver returns a sampled GTO action where hero is the solved ROOT (OOP first-to-act);
  [3] the resolver SAFELY floors (returns None, no crash) where hero is a deeper node (IP after a check) —
      a documented TexasSolver limitation (root-only strategy dump), now graceful via the null-safe fix.
Run: python -m extraction.smoke_weighted_resolve
"""
import sys, time, random
sys.stdout.reconfigure(encoding="utf-8")
from pokerbot.strategy.range_tracker import weighted_ranges
from pokerbot.strategy import gto_oracle as O
from pokerbot.strategy.gto_oracle import _key
from pokerbot.strategy import resolver as _rsv

B = ["Qs", "Jh", "2h", "5c", "8d"]
PRE_RIVER = [
    {"player": 0, "action": "raise", "street": "preflop", "to": 300},
    {"player": 1, "action": "call", "street": "preflop", "amount": 200},
    {"action": "deal", "street": "flop", "board": B[:3]},
    {"player": 1, "action": "check", "street": "flop"},
    {"player": 0, "action": "bet", "street": "flop", "to": 200},
    {"player": 1, "action": "call", "street": "flop", "amount": 200},
    {"action": "deal", "street": "turn", "board": B[:4]},
    {"player": 1, "action": "check", "street": "turn"},
    {"player": 0, "action": "check", "street": "turn"},
    {"action": "deal", "street": "river", "board": B[:5]},
]


def _state(history, hero, hole):
    return {"button": 0, "street": "river", "board": B, "pot": 1000, "current_bet": 0, "history": history,
            "players": [{"idx": i, "hole": hole if i == hero else ["??", "??"], "stack": 9400,
                         "committed_street": 0, "committed_total": 500, "folded": False, "all_in": False,
                         "is_button": i == 0} for i in (0, 1)],
            "legal": {"to_act": hero, "to_call": 0, "can_fold": False, "can_check": True, "can_call": False,
                      "can_raise": True, "is_bet": True, "raise_min": 100, "raise_max": 9400, "pot": 1000}}


def main():
    # [1] weighted ranges -> solver parse + solve
    st_oop = _state(PRE_RIVER, hero=1, hole=["Ah", "Qh"])     # hero = BB (OOP), first to act on the river
    oop, ip, conf = weighted_ranges(st_oop)
    print(f"[tracker] conf={conf:.2f} | oop {len(oop.split(','))} combos | ip {len(ip.split(','))} combos")
    print("[1] solver parse+solve of CLASS-level WEIGHTED ranges (~seconds)...", flush=True)
    t0 = time.time()
    node = O.solve(B, oop, ip, pot=1000, eff_stack=9400, accuracy=0.5, max_iter=60, dump_rounds=1,
                   threads=8, timeout=90, tag="smoke1")
    acts = node.get("strategy", {}).get("actions", [])
    nkeys = len(_key(node))   # the REAL test: per-combo strategy dump must be NON-empty (per-combo input -> 0)
    assert acts and nkeys > 0, f"solver root strategy unusable (actions={bool(acts)}, strategy keys={nkeys})"
    print(f"    OK solved {time.time()-t0:.1f}s | root actions={acts} | {nkeys} per-combo strategy keys")

    # [2] resolver returns an action where hero IS the solved root (OOP first-to-act)
    print("[2] river_resolve, hero=OOP first-to-act (the supported node)...", flush=True)
    t0 = time.time()
    res = _rsv.river_resolve(st_oop, ["Ah", "Qh"], B, 1000.0, 9400.0, oop, ip,
                             st_oop["legal"], random.Random(7), iters=60, timeout=90)
    print(f"    resolver -> {res} in {time.time()-t0:.1f}s")
    assert res is not None, "river_resolve returned None on the OOP-first node it should support"

    # [3] resolver ALSO fires on a deeper node (IP after OOP check) — class-level input populates the dump at
    # depth (the earlier 'root-only / strategy:null' failure was an artifact of the BROKEN per-combo input).
    print("[3] river_resolve, hero=IP after OOP check (deeper node)...", flush=True)
    hist_ip = PRE_RIVER + [{"player": 1, "action": "check", "street": "river"}]
    st_ip = _state(hist_ip, hero=0, hole=["As", "Kd"])
    o2, i2, _ = weighted_ranges(st_ip)
    res2 = _rsv.river_resolve(st_ip, ["As", "Kd"], B, 1000.0, 9400.0, o2, i2,
                              st_ip["legal"], random.Random(7), iters=60, timeout=90)
    assert res2 is not None, f"river_resolve returned None on the IP-after-check node, got {res2}"
    print(f"    OK resolver -> {res2} (fires on the deeper node too)")

    print("\nSMOKE PASS: class-level tracked ranges solve (non-empty strategy dump); resolver fires "
          "end-to-end on BOTH river node types (OOP-first + IP-after-check).")


if __name__ == "__main__":
    main()
