"""Diagnose TexasSolver solve speed on the pod (threads x tree size) to size the 30-min run."""
import time

from pokerbot.strategy import gto_oracle as O

OOP = "AA,KK,QQ,JJ,TT,AQs,AJs,KQs,QJs,JTs,T9s,98s,AQo,KQo,A5s"
IP = "AA,KK,QQ,JJ,TT,AKs,AQs,AJs,KQs,QJs,JTs,T9s,AKo,AQo"

SMALL = [  # reduced bet tree (one size + allin per street) -> much smaller game
    "set_bet_sizes oop,flop,bet,66", "set_bet_sizes oop,flop,allin",
    "set_bet_sizes ip,flop,bet,66", "set_bet_sizes ip,flop,allin",
    "set_bet_sizes oop,turn,bet,75", "set_bet_sizes oop,turn,allin",
    "set_bet_sizes ip,turn,bet,75", "set_bet_sizes ip,turn,allin",
    "set_bet_sizes oop,river,bet,75", "set_bet_sizes oop,river,allin",
    "set_bet_sizes ip,river,bet,75", "set_bet_sizes ip,river,allin",
]

for label, mi, th, bets in [("flop small-tree th48 mi40", 40, 48, SMALL),
                            ("flop small-tree th96 mi60", 60, 96, SMALL)]:
    t = time.time()
    try:
        n = O.solve(["Qs", "Jh", "2h"], OOP, IP, pot=20, eff_stack=100, max_iter=mi,
                    threads=th, bets=bets, dump_rounds=1, timeout=200)
        print(label, "->", round(time.time() - t, 1), "s", n.get("strategy", {}).get("actions"))
    except Exception as e:  # noqa: BLE001
        print(label, "-> FAIL", round(time.time() - t, 1), "s", repr(e)[:100])
