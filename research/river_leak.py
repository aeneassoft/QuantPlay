"""Attribute the FLOOR river leak by the engine's OWN math (no GTOW needed) -> tells you which lever is warranted.
Replays PokerBot(exploit=False) vs GTOBaseline (seed 7) and logs each river decision's equity (rationale['equity'])
and, facing a bet, the required equity. Two precise questions:
  - MISSED VALUE: first-to-act with HIGH eq that still CHECKS (clear -EV on the final card; no protection concern).
  - OVER-CALL: facing a bet, CALLS with eq < required (clear -EV by pot odds). eq>=required calls are MDF-correct
    vs a balanced opponent -> NOT a leak; this separates a real leak from defensible defending.
Run:  PYTHONUTF8=1 PYTHONPATH=. python -m research.river_leak [N_HANDS]
"""
import sys
from pokerbot.engine.game import HeadsUpGame
import pokerbot.strategy.bot as bm; bm.EQUITY_ITERS = 200
from pokerbot.strategy.bot import PokerBot
from pokerbot.strategy.gto_baseline import GTOBaseline


def pct(n, d):
    return f"{100*n/d:.0f}%" if d else "n/a"


def main(n_hands: int = 800) -> None:
    first, facing = [], []                       # first: (eq, action);  facing: (eq, req, action)
    g = HeadsUpGame(names=("P0", "P1"), starting_stack=20000, sb=50, bb=100, seed=7)
    for i in range(n_hands):
        g.players[0].stack = g.players[1].stack = 20000; g.start_hand()
        pb = PokerBot(0, seed=100 + i, exploit=False); pb.value_raise_eq = 0.72
        vb = GTOBaseline(1, seed=200 + i, iters=120)
        guard = 0
        while not g.hand_over and guard < 400:
            st = g.state(); guard += 1
            if st["to_act"] == 0:
                pb.hero_idx = 0; r = pb.decide(st); act, amt = r["action"], r["amount"]
                if st["street"] == "river" and len(st["board"]) == 5:
                    rat = r["rationale"]; eq, req = rat.get("equity"), rat.get("required_equity")
                    if act in ("check", "bet"):
                        first.append((eq, act))
                    elif act in ("fold", "call", "raise"):
                        facing.append((eq, req, act))
            else:
                vb.hero = 1; act, amt = vb.decide(st)
            g.act(act, amt)

    print("=== MISSED VALUE (first-to-act, by equity vs range) ===")
    for lo, hi in [(0.80, 1.01), (0.70, 0.80), (0.58, 0.70), (0.0, 0.58)]:
        band = [a for (e, a) in first if e is not None and lo <= e < hi]
        chk = band.count("check")
        flag = "   <- HIGH eq checking = MISSED VALUE" if lo >= 0.70 and band and chk / len(band) > 0.3 else ""
        print(f"  eq [{lo:.2f},{hi:.2f}): n={len(band):3d}  check {pct(chk,len(band))}  bet {pct(len(band)-chk,len(band))}{flag}")

    called = [(e, q) for (e, q, a) in facing if a in ("call", "raise") and e is not None and q is not None]
    neg = [(e, q) for (e, q) in called if e < q]
    print("\n=== OVER-CALL test (facing a bet: called when eq < required?) ===")
    print(f"  calls/raises: {len(called)};  eq < required (clear -EV): {len(neg)} = {pct(len(neg),len(called))}")
    print(f"\n  totals: first-to-act {len(first)}, facing-bet {len(facing)}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 800)
