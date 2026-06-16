"""Run 1 of the orchestration loop (docs/ORCHESTRATION_PLAN.md): the FLOOR ERROR MAP — the keep/revert
dashboard. Scores the LIVE floor (bot.py, exploit OFF) against the TexasSolver flop cache, broken down by
role (OOP-donk / IP-c-bet) x texture, so we see WHERE the floor diverges most from GTO before patching.

Cache-only (no solving) -> fast + deterministic. Metric per acting hand = GTO-gap = 1 - p_GTO(our action-kind)
(bet vs check), same as gto_benchmark, plus GTO-bet vs our-bet frequencies. Builds the FULL state bot.py needs
(history -> _has_initiative, stacks, button), unlike gto_benchmark's minimal GTOBaseline state.

Run:  python -m pokerbot.benchmark.floor_map
"""
from __future__ import annotations

import json
from collections import defaultdict

from pokerbot import config
import pokerbot.strategy.bot as botmod
botmod.EQUITY_ITERS = 120
from pokerbot.strategy.bot import PokerBot  # noqa: E402
from pokerbot.strategy.gto_baseline import GTOBaseline  # noqa: E402
from pokerbot.benchmark.gto_benchmark import _CACHE, texture  # noqa: E402


def make_flop_state(hole, board, role, pot=600, stack=9700, street="flop"):
    """A single-raised pot, hero first to act on `street` (flop/turn/river). IP = hero is the BTN aggressor
    (villain checked to us); OOP = hero is the BB caller, first to act. History drives bot.py's _has_initiative
    (preflop-only) + range estimation; board length picks the street so the right advisor fires."""
    if role == "IP":
        button = 0
        hist = [{"player": 0, "action": "raise", "street": "preflop", "to": 300},
                {"player": 1, "action": "call", "street": "preflop", "amount": 200},
                {"action": "deal", "street": "flop", "board": list(board)},
                {"player": 1, "action": "check", "street": "flop"}]
    else:  # OOP donk node
        button = 1
        hist = [{"player": 1, "action": "raise", "street": "preflop", "to": 300},
                {"player": 0, "action": "call", "street": "preflop", "amount": 200},
                {"action": "deal", "street": "flop", "board": list(board)}]
    return {"hand_no": 0, "button": button, "street": street, "board": list(board), "pot": pot,
            "current_bet": 0, "to_act": 0, "hand_over": False, "result": None, "sb": 50, "bb": 100,
            "history": hist,
            "players": [{"idx": 0, "hole": list(hole), "stack": stack, "committed_street": 0,
                         "committed_total": 300, "folded": False, "all_in": False, "is_button": button == 0},
                        {"idx": 1, "hole": ["??", "??"], "stack": stack, "committed_street": 0,
                         "committed_total": 300, "folded": False, "all_in": False, "is_button": button == 1}],
            "legal": {"to_act": 0, "to_call": 0, "can_fold": False, "can_check": True, "can_call": False,
                      "call_amount": 0, "can_raise": True, "is_bet": True, "raise_min": 100,
                      "raise_max": stack, "pot": pot}}


def _gap(node, board, role, decide, street="flop"):
    s = node.get("strategy", {})
    actions, strat = s.get("actions", []), s.get("strategy", {})
    if not actions or not strat:
        return None
    bet_idx = [i for i, a in enumerate(actions) if a.split()[0] in ("BET", "RAISE", "ALLIN")]
    check_idx = next((i for i, a in enumerate(actions) if a.split()[0] == "CHECK"), None)
    n = 0
    div = gbet = bbet = 0.0
    for combo, probs in strat.items():
        if combo[:2] in board or combo[2:4] in board:    # skip combos colliding with the board
            continue
        a = decide(make_flop_state((combo[:2], combo[2:4]), board, role, street=street))
        our_bet = a in ("bet", "raise", "allin")
        g_bet = sum(probs[i] for i in bet_idx)
        p_ourkind = g_bet if our_bet else (probs[check_idx] if check_idx is not None else 0.0)
        div += 1 - p_ourkind
        gbet += g_bet
        bbet += 1.0 if our_bet else 0.0
        n += 1
    return n, div, gbet, bbet


def _floor_decide():
    pb = PokerBot(0, seed=7, exploit=False)        # the LIVE floor, exploit OFF

    def d(st):
        pb.hero_idx = 0
        return pb.decide(st)["action"]
    return d


def _gto_decide():
    b = GTOBaseline(0, seed=1, iters=120)          # the calibrated benchmark baseline (for comparison)

    def d(st):
        b.hero = 0
        return b.decide(st)[0]
    return d


RCACHE = config.DATA_DIR / "_gto_river_cache"     # river-subgame solves (root = OOP river node, CHECK child = IP)


def run(name, decide, limit=None, street="flop", cache=None):
    """GTO-gap of `decide` vs the solver on the root (OOP first-to-act) + its CHECK child (IP) nodes. street=flop
    reads the flop cache (3-card boards); street=river reads RCACHE (5-card). Turn uses run_turn (nested walk)."""
    agg = defaultdict(lambda: [0, 0.0, 0.0, 0.0])
    cache = cache or (RCACHE if street == "river" else _CACHE)
    ncard = 5 if street == "river" else 3
    files = sorted(cache.glob("*.json"))
    if limit:
        files = files[:limit]
    for cf in files:
        try:
            node = json.loads(cf.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        st = cf.stem.split("_")[0]
        if len(st) < 2 * ncard:
            continue
        board = [st[2 * i:2 * i + 2] for i in range(ncard)]
        tex = texture(board)
        ip = next((v for k, v in (node.get("childrens") or {}).items() if k.split()[0] == "CHECK"), None)
        for role, nd in (("OOP", node), ("IP", ip)):
            if nd is None:
                continue
            r = _gap(nd, board, role, decide, street)
            if not r:
                continue
            for key in (f"{role}:{tex}", f"{role}:ALL", "ALL"):
                a = agg[key]
                for j in range(4):
                    a[j] += r[j]
    _print_agg(name, len(files), agg)
    return agg


def _print_agg(name, nfiles, agg):
    print(f"\n=== {name} ({nfiles} cached boards) ===")
    print(f"{'bucket':16}{'hands':>7}{'GTO-gap':>9}{'GTO-bet':>9}{'our-bet':>9}")
    for k in sorted(agg):
        n, div, gb, bb = agg[k]
        if n:
            print(f"{k:16}{n:>7}{div / n:>9.0%}{gb / n:>9.0%}{bb / n:>9.0%}")


def _smallest_bet(children):
    bets = [(float(k.split()[1]), k) for k in (children or {}) if k.split()[0] == "BET"]
    return min(bets)[1] if bets else None


def run_turn(name, decide, limit=None):
    """Turn GTO-gap on the classic c-bet-called line (flop OOP CHECK -> IP BET small -> OOP CALL -> turn): scores
    the OOP turn-lead + IP turn-barrel (after OOP check) nodes vs the solver, from the DUMP=2 flop cache."""
    agg = defaultdict(lambda: [0, 0.0, 0.0, 0.0])
    files = sorted(_CACHE.glob("*.json"))
    if limit:
        files = files[:limit]
    nfiles = 0
    for cf in files:
        st = cf.stem.split("_")[0]
        if len(st) != 6:
            continue
        flop = [st[0:2], st[2:4], st[4:6]]
        try:
            root = json.loads(cf.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        ipn = (root.get("childrens") or {}).get("CHECK")
        bkey = _smallest_bet(ipn.get("childrens") if ipn else None)
        oop_face = (ipn.get("childrens") or {}).get(bkey) if (ipn and bkey) else None
        chance = (oop_face.get("childrens") or {}).get("CALL") if oop_face else None
        if not chance or chance.get("node_type") != "chance_node":
            continue
        nfiles += 1
        for tcard, turn_oop in list((chance.get("dealcards") or {}).items())[:8]:   # sample turn cards (cost cap)
            if not isinstance(turn_oop, dict) or tcard in flop:
                continue
            board4 = flop + [tcard]
            tex = texture(board4)
            for role, nd in (("OOP", turn_oop), ("IP", (turn_oop.get("childrens") or {}).get("CHECK"))):
                if nd is None:
                    continue
                r = _gap(nd, board4, role, decide, "turn")
                if not r:
                    continue
                for key in (f"{role}:{tex}", f"{role}:ALL", "ALL"):
                    a = agg[key]
                    for j in range(4):
                        a[j] += r[j]
    _print_agg(name, nfiles, agg)
    return agg


def main():
    import sys
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    print("GTO-gap = mean(1 - p_GTO(our action-kind)) vs TexasSolver; 0 = GTO-plausible. OOP first-to-act, IP after-check.")
    d = _floor_decide()
    run("FLOP  - MVP floor vs TexasSolver", d, lim, street="flop")
    run_turn("TURN  - MVP floor vs TexasSolver (c-bet-called line)", d, lim)
    run("RIVER - MVP floor vs TexasSolver", d, lim, street="river")


if __name__ == "__main__":
    main()
