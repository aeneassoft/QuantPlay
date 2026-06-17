"""Step 2-3 of the solver-grafted-preflop plan: calibrate the see-flop REALIZATION premium per node from real
TexasSolver flop solves, replacing the blueprint's pure-equity "checkdown" guess.

For each see-flop node we (a) get the reach-weighted ranges (extraction.preflop_ranges), (b) solve a modest
suit-canonical set of flops at the node's (pot, eff) with a LEAN bet tree, and (c) measure the IN-POSITION
(SB) player's REALIZED EV from the solved flop play via an MC rollout of the solved strategies. The realized
fraction w_node = ip_ev/pot + 0.5 replaces the checkdown's `w = e + kappa*4*e*(1-e)`.

Fidelity L1 (this file): dump_rounds=1, solved flop betting + a CHECKDOWN of turn+river (real flop fold/bet
EV; turn+river approximated by equity). It already captures the flop fold-equity the pure-equity checkdown
omits. L2 (flop+turn betting) is a later deepen if the metric demands it.

Convention matches extraction.cfv_eval (zero-sum): value0 (OOP) = winnings0 - (pot/2 + street_contrib0); the
flop-start pot is "neutral" (both invested pot/2). ip_ev = -oop_ev. Output: knowledge_base/ranges/preflop_leaf_table.json.
Run: python -m extraction.preflop_calibrate [--node OPEN] [--flops 16] [--samples 80000] [--selftest]
"""
from __future__ import annotations

import argparse
import json
import random
import time

from pokerbot import config
from pokerbot.engine.cards import expand_class, make_deck
from pokerbot.engine.evaluator import evaluate
from pokerbot.strategy import gto_oracle as O
from research.preflop_ranges import reaching_ranges, load_blueprint, sd_leaves

_FULL = make_deck()

# Lean bet tree: one 75%-pot bet + all-in, NO intermediate raise -> bounded depth even at 200bb (verified ~100-160s/solve).
LEAN_BETS = []
for _pos in ("oop", "ip"):
    for _st in ("flop", "turn", "river"):
        LEAN_BETS += [f"set_bet_sizes {_pos},{_st},bet,75", f"set_bet_sizes {_pos},{_st},allin"]
# Rich tree (robustness check for the lean-tree under-realization caveat): two bet sizes + a raise + all-in.
RICH_BETS = []
for _pos in ("oop", "ip"):
    for _st in ("flop", "turn", "river"):
        RICH_BETS += [f"set_bet_sizes {_pos},{_st},bet,33,75", f"set_bet_sizes {_pos},{_st},raise,60",
                      f"set_bet_sizes {_pos},{_st},allin"]
# Middle tree: two bet sizes (33/75) + all-in, NO raise (the raise sub-tree is the 200bb branching killer that made
# RICH intractable). Tests whether the lean 1-size tree materially under-realizes, while staying solvable.
MID_BETS = []
for _pos in ("oop", "ip"):
    for _st in ("flop", "turn", "river"):
        MID_BETS += [f"set_bet_sizes {_pos},{_st},bet,33,75", f"set_bet_sizes {_pos},{_st},allin"]
BETS = LEAN_BETS                                # module-level, swapped to RICH_BETS / MID_BETS by --rich / --mid


def _weighted_combos(range_str: str, dead: set) -> tuple[list, list]:
    """'AA:1.0,76s:0.3,...' -> (combos, weights), board-removed, class weight applied per combo (TexasSolver style)."""
    combos, weights = [], []
    for entry in range_str.split(","):
        if not entry:
            continue
        cls, _, w = entry.partition(":")
        wt = float(w) if w else 1.0
        for a, b in expand_class(cls):
            if a in dead or b in dead:
                continue
            combos.append((a, b))
            weights.append(wt)
    return combos, weights


def _player_oop(root, oop_combos: list) -> int:
    """Which dump player index (0/1) is OOP — match the root's range against our known OOP combos (robust to
    TexasSolver's player numbering, which puts the first-to-act at the root)."""
    from research.cfv_eval import _combos_at
    p0 = set(_combos_at(root, 0) or [])
    oop_keys = {a + b for a, b in oop_combos}
    # the player whose dumped range overlaps our OOP range is OOP
    return 0 if len(p0 & oop_keys) >= len(p0) / 2 else 1


def flop_realized_ev(root, board: list, oop_str: str, ip_str: str, pot0: float, n_samples: int,
                     rng: random.Random) -> tuple[float, float, dict]:
    """MC rollout of the solved flop subgame -> (oop_ev, ip_ev) chips + per-IP-equity-bucket realized w.
    Samples (c_oop, c_ip) ~ ranges, walks the dumped strategies, checks down turn+river at betting close."""
    dead0 = set(board)
    oop_c, oop_w = _weighted_combos(oop_str, dead0)
    ip_c, ip_w = _weighted_combos(ip_str, dead0)
    if not oop_c or not ip_c:
        return 0.0, 0.0, {}
    p_oop = _player_oop(root, oop_c)
    acc0 = 0.0
    n = 0
    bucket = {}        # ip-equity-bucket -> [sum_w, count]  (w = ip realized fraction for that sample)
    base_deck = _FULL
    for _ in range(n_samples):
        c0 = rng.choices(oop_c, weights=oop_w, k=1)[0]
        c1 = rng.choices(ip_c, weights=ip_w, k=1)[0]
        if c0[0] in c1 or c0[1] in c1:                 # card overlap -> impossible matchup
            continue
        v0 = _rollout(root, c0, c1, p_oop, 0.0, 0.0, board, pot0, base_deck, rng)
        acc0 += v0
        n += 1
        w_ip = (-v0) / pot0 + 0.5                       # ip realized fraction this sample
        b = int(min(9, max(0, w_ip * 10)))              # coarse 10-bucket by realized fraction
        s = bucket.setdefault(b, [0.0, 0])
        s[0] += w_ip
        s[1] += 1
    oop_ev = acc0 / n if n else 0.0
    return oop_ev, -oop_ev, bucket


def _rollout(node, c0, c1, p_oop, sc0, sc1, board, pot0, base_deck, rng) -> float:
    """One sampled playout from `node` -> value0 (OOP net, cfv_eval convention). c0=OOP hand, c1=IP hand."""
    p = node.get("player")
    actor_is_oop = (p == p_oop)
    hand = c0 if actor_is_oop else c1
    pr = O.strategy_for(node, hand[0], hand[1])
    if not pr:                                          # combo not in this node's range -> checkdown defensively
        return _checkdown_v0(c0, c1, sc0, sc1, board, pot0, base_deck, rng)
    acts = list(pr)
    a = rng.choices(acts, weights=[max(0.0, pr[x]) for x in acts], k=1)[0]
    parts = a.split()
    kind = parts[0]
    amt = float(parts[1]) if len(parts) > 1 else None
    if kind == "FOLD":
        tc0 = pot0 / 2 + sc0
        return (0.0 - tc0) if actor_is_oop else (pot0 + sc0 + sc1 - tc0)
    if kind in ("BET", "RAISE", "ALLIN"):
        if actor_is_oop:
            sc0 = amt
        else:
            sc1 = amt
    elif kind == "CALL":
        if actor_is_oop:
            sc0 = sc1
        else:
            sc1 = sc0
    child = (node.get("childrens") or {}).get(a)
    if child is None or child.get("node_type") == "chance_node":   # betting closed / turn not dumped -> checkdown
        return _checkdown_v0(c0, c1, sc0, sc1, board, pot0, base_deck, rng)
    return _rollout(child, c0, c1, p_oop, sc0, sc1, board, pot0, base_deck, rng)


def _checkdown_v0(c0, c1, sc0, sc1, board, pot0, base_deck, rng) -> float:
    """Deal turn+river (one sampled runout) and score the showdown -> value0 (OOP net)."""
    dead = {c0[0], c0[1], c1[0], c1[1], *board}
    avail = [c for c in base_deck if c not in dead]
    t, r = rng.sample(avail, 2)
    full = board + [t, r]
    tc0 = pot0 / 2 + sc0
    pot = pot0 + sc0 + sc1
    r0, r1 = evaluate(full, [c0[0], c0[1]]), evaluate(full, [c1[0], c1[1]])
    w0 = pot if r0 < r1 else (0.0 if r0 > r1 else pot / 2)
    return w0 - tc0


def _canonical_flops(n: int, rng: random.Random) -> list:
    """A modest suit-canonical-ish flop sample spanning textures (dealt random, dedup by sorted ranks+suit-pattern)."""
    seen, out = set(), []
    deck = list(_FULL)
    while len(out) < n and len(seen) < 1500:
        b = rng.sample(deck, 3)
        ranks = "".join(sorted(c[0] for c in b))
        suits = b[0][1], b[1][1], b[2][1]
        pat = "m" if len(set(suits)) == 1 else ("r" if len(set(suits)) == 3 else "2")  # mono / rainbow / two-tone
        key = (ranks, pat)
        if key in seen:
            continue
        seen.add(key)
        out.append(b)
    return out


def _solve_and_roll(node, b, oop_str, ip_str, pot0, eff, n_samples, max_iter, seed) -> dict | None:
    """One flop: solve + MC rollout -> {board, w, ip_ev, secs}. Own seeded RNG (thread-safe + deterministic)."""
    t0 = time.time()
    try:
        root = O.solve(b, oop_str, ip_str, pot=pot0, eff_stack=eff, bets=BETS,
                       accuracy=0.5, max_iter=max_iter, dump_rounds=1, timeout=600,
                       tag=f"cal_{node}_{''.join(b)}")
    except Exception as ex:  # noqa: BLE001
        print(f"    {''.join(b)} solve FAILED: {ex}", flush=True)
        return None
    oop_ev, ip_ev, _bkt = flop_realized_ev(root, b, oop_str, ip_str, pot0, n_samples, random.Random(seed))
    w = max(0.0, min(1.0, ip_ev / pot0 + 0.5))
    print(f"    {''.join(b)}  w={w:.3f}  ip_ev={ip_ev:+.2f}bb  ({time.time()-t0:.0f}s)", flush=True)
    return {"board": "".join(b), "w": round(w, 4), "ip_ev": round(ip_ev, 3)}


def calibrate_node(node: str, blueprint: dict, n_flops: int, n_samples: int, max_iter: int,
                   rng: random.Random, workers: int = 3) -> dict:
    """Solve n_flops at `node` (concurrently) and return {w_node, n_flops, per_flop:[...]}."""
    from concurrent.futures import ThreadPoolExecutor
    oop_str, ip_str, pot0, eff = reaching_ranges(node, blueprint)
    flops = _canonical_flops(n_flops, rng)
    rows = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(_solve_and_roll, node, b, oop_str, ip_str, pot0, eff, n_samples, max_iter, 1000 + i)
                for i, b in enumerate(flops)]
        for f in futs:
            r = f.result()
            if r is not None:
                rows.append(r)
    ws = [r["w"] for r in rows]
    w_node = sum(ws) / len(ws) if ws else 0.5
    spread = (min(ws), max(ws)) if ws else (0.0, 0.0)
    return {"node": node, "pot": pot0, "eff": eff, "w_node": round(w_node, 4),
            "w_spread": [round(spread[0], 3), round(spread[1], 3)], "n_flops": len(ws), "per_flop": rows}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--node", default="OPEN", help="see-flop node to calibrate (or 'all')")
    ap.add_argument("--flops", type=int, default=16)
    ap.add_argument("--samples", type=int, default=80000)
    ap.add_argument("--iter", type=int, default=80)
    ap.add_argument("--workers", type=int, default=3, help="concurrent flop solves (each uses 8 solver threads)")
    ap.add_argument("--rich", action="store_true", help="use the RICH bet tree (33/75 + raise + allin) to check the lean-tree under-realization caveat")
    ap.add_argument("--mid", action="store_true", help="use the MIDDLE bet tree (33/75 + allin, NO raise) - tractable richness check")
    ap.add_argument("--selftest", action="store_true", help="solve ONE flop + print the realized-EV sanity, then stop")
    args = ap.parse_args()
    global BETS
    if args.rich:
        BETS = RICH_BETS
        print("  (rich bet tree: 33/75 + raise60 + allin)", flush=True)
    elif args.mid:
        BETS = MID_BETS
        print("  (middle bet tree: 33/75 + allin, no raise)", flush=True)
    rng = random.Random(7)
    bp = load_blueprint()

    if args.selftest:
        node = args.node if args.node != "all" else "OPEN"
        oop_str, ip_str, pot0, eff = reaching_ranges(node, bp)
        b = ["Ks", "7h", "2c"]
        print(f"SELFTEST {node} flop {b} pot={pot0} eff={eff}", flush=True)
        t0 = time.time()
        root = O.solve(b, oop_str, ip_str, pot=pot0, eff_stack=eff, bets=BETS, accuracy=0.5,
                       max_iter=args.iter, dump_rounds=1, timeout=600, tag="selftest")
        oop_ev, ip_ev, bkt = flop_realized_ev(root, b, oop_str, ip_str, pot0, args.samples, rng)
        w = ip_ev / pot0 + 0.5
        print(f"  solved+rolled in {time.time()-t0:.0f}s", flush=True)
        print(f"  oop_ev={oop_ev:+.3f}  ip_ev={ip_ev:+.3f}  (zero-sum: {oop_ev+ip_ev:+.4f})", flush=True)
        print(f"  w_node(IP realized) = {w:.3f}   (0.5 = break-even; >0.5 = IP realization premium)", flush=True)
        print(f"  implied kappa (vs checkdown e+k*4e(1-e)): see full run; per-bucket counts: "
              f"{ {k: v[1] for k, v in sorted(bkt.items())} }", flush=True)
        return

    nodes = list(sd_leaves()) if args.node == "all" else [args.node]
    table = {}
    for node in nodes:
        print(f"=== calibrating {node} ({args.flops} flops, {args.samples} samples/flop) ===", flush=True)
        res = calibrate_node(node, bp, args.flops, args.samples, args.iter, rng, workers=args.workers)
        table[node] = res
        print(f"  -> w_node({node}) = {res['w_node']}  over {res['n_flops']} flops", flush=True)
    out = config.KNOWLEDGE_DIR / "ranges" / "preflop_leaf_table.json"
    out.write_text(json.dumps(table, indent=1), encoding="utf-8")
    print(f"\nDONE -> {out}", flush=True)


if __name__ == "__main__":
    main()
