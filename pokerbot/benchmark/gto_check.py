"""Verify our analytic gto_baseline against the TexasSolver GTO oracle (postflop OOP flop decision).

For each spot we solve the true GTO strategy, then for every hand in OOP's range we compare:
  * GTO bet-frequency (sum of BET/RAISE/ALLIN probability) vs our baseline's bet/check choice,
  * per-hand agreement and the range-level bet-frequency gap.
This is the honest "how far is our baseline from GTO" measurement — the oracle we lacked without a
GTO Wizard key. Run: python -m pokerbot.benchmark.gto_check
"""
from __future__ import annotations

from pokerbot.strategy import gto_oracle as O
from pokerbot.strategy.gto_baseline import GTOBaseline

# Representative single-raised-pot flops (BB oop vs BTN ip, ~100bb), explicit solver ranges.
_OOP = "QQ,JJ,TT,99,88,77,66,55,AQs,AJs,ATs,KQs,KJs,KTs,QJs,QTs,JTs,T9s,98s,87s,76s,65s,54s,AQo,KQo,A5s,A4s,A3s"
_IP = "AA,KK,QQ,JJ,TT,99,88,77,AKs,AQs,AJs,ATs,KQs,KJs,QJs,JTs,T9s,98s,AKo,AQo,KQo,A5s,A4s"
SPOTS = [
    ("dry    K72r", ["Ks", "7h", "2d"]),
    ("wet    QJ9ss", ["Qs", "Js", "9h"]),
    ("paired 882r", ["8s", "8h", "2d"]),
    ("low    652ss", ["6s", "5s", "2h"]),
]


def _make_state(hole, board, pot=2000, stack=10000):
    return {
        "legal": {"pot": pot, "to_call": 0, "can_check": True, "can_raise": True,
                  "is_bet": True, "raise_min": 1, "raise_max": stack},
        "players": [{"hole": list(hole), "committed_street": 0}],
        "board": list(board), "street": "flop" if len(board) == 3 else "turn",
        "bb": 100, "current_bet": 0,
    }


def main() -> None:
    if not O.available():
        print(f"TexasSolver missing at {O.EXE}"); return
    hero = GTOBaseline(hero=0, seed=1, iters=200)
    tot_match = tot_n = 0
    g_sum = b_sum = 0.0
    print(f"{'spot':14} {'n':>4} {'agree':>6} {'GTO-bet%':>9} {'base-bet%':>10} {'gap':>6}")
    for name, board in SPOTS:
        node = O.solve(board, _OOP, _IP, pot=20, eff_stack=100, accuracy=0.5, max_iter=120, dump_rounds=1)
        actions = node.get("strategy", {}).get("actions", [])
        strat = node.get("strategy", {}).get("strategy", {})
        bet_idx = [i for i, a in enumerate(actions) if a.split()[0] in ("BET", "RAISE", "ALLIN")]
        n = match = 0
        gbet = bbet = 0.0
        for combo, probs in strat.items():
            c1, c2 = combo[:2], combo[2:4]
            gto_bet = sum(probs[i] for i in bet_idx)
            a, _ = hero.decide(_make_state((c1, c2), board))
            base_bet = 1.0 if a in ("bet", "raise") else 0.0
            # agreement = both bet (>=50%) or both check
            if (gto_bet >= 0.5) == (base_bet >= 0.5):
                match += 1
            n += 1
            gbet += gto_bet
            bbet += base_bet
        gbet /= max(1, n); bbet /= max(1, n)
        print(f"{name:14} {n:>4} {match/max(1,n):>6.0%} {gbet:>9.0%} {bbet:>10.0%} {abs(gbet-bbet):>6.0%}")
        tot_match += match; tot_n += n; g_sum += gbet * n; b_sum += bbet * n
    print(f"\nOVERALL  agree={tot_match/max(1,tot_n):.0%}  "
          f"GTO bet-freq={g_sum/max(1,tot_n):.0%}  baseline bet-freq={b_sum/max(1,tot_n):.0%}  "
          f"(gap {abs(g_sum-b_sum)/max(1,tot_n):.0%})")
    print("Higher agreement = baseline closer to GTO. Big bet-freq gap = a real, fixable leak.")


if __name__ == "__main__":
    main()
