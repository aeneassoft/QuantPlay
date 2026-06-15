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

import pokerbot.strategy.bot as botmod
botmod.EQUITY_ITERS = 120
from pokerbot.strategy.bot import PokerBot  # noqa: E402
from pokerbot.strategy.gto_baseline import GTOBaseline  # noqa: E402
from pokerbot.benchmark.gto_benchmark import _CACHE, texture  # noqa: E402


def make_flop_state(hole, board, role, pot=600, stack=9700):
    """A flop, single-raised pot. IP = hero is the BTN aggressor (villain checked to us); OOP = hero is the BB
    caller, first to act (the donk node). History drives bot.py's _has_initiative + range estimation."""
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
    return {"hand_no": 0, "button": button, "street": "flop", "board": list(board), "pot": pot,
            "current_bet": 0, "to_act": 0, "hand_over": False, "result": None, "sb": 50, "bb": 100,
            "history": hist,
            "players": [{"idx": 0, "hole": list(hole), "stack": stack, "committed_street": 0,
                         "committed_total": 300, "folded": False, "all_in": False, "is_button": button == 0},
                        {"idx": 1, "hole": ["??", "??"], "stack": stack, "committed_street": 0,
                         "committed_total": 300, "folded": False, "all_in": False, "is_button": button == 1}],
            "legal": {"to_act": 0, "to_call": 0, "can_fold": False, "can_check": True, "can_call": False,
                      "call_amount": 0, "can_raise": True, "is_bet": True, "raise_min": 100,
                      "raise_max": stack, "pot": pot}}


def _gap(node, board, role, decide):
    s = node.get("strategy", {})
    actions, strat = s.get("actions", []), s.get("strategy", {})
    if not actions or not strat:
        return None
    bet_idx = [i for i, a in enumerate(actions) if a.split()[0] in ("BET", "RAISE", "ALLIN")]
    check_idx = next((i for i, a in enumerate(actions) if a.split()[0] == "CHECK"), None)
    n = 0
    div = gbet = bbet = 0.0
    for combo, probs in strat.items():
        a = decide(make_flop_state((combo[:2], combo[2:4]), board, role))
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


def run(name, decide, limit=None):
    agg = defaultdict(lambda: [0, 0.0, 0.0, 0.0])
    files = sorted(_CACHE.glob("*.json"))
    if limit:
        files = files[:limit]
    for cf in files:
        try:
            node = json.loads(cf.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        st = cf.stem
        if len(st) < 6:
            continue
        board = [st[0:2], st[2:4], st[4:6]]
        tex = texture(board)
        ip = next((v for k, v in (node.get("childrens") or {}).items() if k.split()[0] == "CHECK"), None)
        for role, nd in (("OOP", node), ("IP", ip)):
            if nd is None:
                continue
            r = _gap(nd, board, role, decide)
            if not r:
                continue
            for key in (f"{role}:{tex}", f"{role}:ALL", "ALL"):
                a = agg[key]
                for j in range(4):
                    a[j] += r[j]
    print(f"\n=== {name} — floor error map ({len(files)} cached boards) ===")
    print(f"{'bucket':16}{'hands':>7}{'GTO-gap':>9}{'GTO-bet':>9}{'our-bet':>9}")
    for k in sorted(agg):
        n, div, gb, bb = agg[k]
        if n:
            print(f"{k:16}{n:>7}{div / n:>9.0%}{gb / n:>9.0%}{bb / n:>9.0%}")
    return agg


def main():
    import sys
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    print("GTO-gap = mean(1 - p_GTO(our action-kind)); 0 = GTO-plausible. OOP = donk node, IP = c-bet node.")
    run("LIVE FLOOR (bot.py, exploit OFF)", _floor_decide(), lim)
    run("GTOBaseline (calibrated ref)", _gto_decide(), lim)


if __name__ == "__main__":
    main()
