"""Smoke-test the sixmax leak fixes: import + scenario behaviour."""
from pokerbot.arena.sixmax import decide_6max
from pokerbot.engine.cards import hand_class
from pokerbot.strategy import preflop_strength as ps


def obs(hole, board=None, to_call=0, pot=150, my_stack=10000, n_active=2, position="BTN",
        preflop_raises=0, cur_bet=0, street="preflop", committed=0):
    board = board or []
    return {"hole": hole, "board": board, "to_call": to_call, "pot": pot, "my_stack": my_stack,
            "bb": 100, "n_active": n_active, "position": position, "preflop_raises": preflop_raises,
            "cur_bet": cur_bet, "my_committed_street": committed, "street": street,
            "can_check": to_call == 0, "can_call": to_call > 0, "can_raise": True,
            "raise_min": (cur_bet or 100) + (to_call or 100), "raise_max": my_stack}


def show(label, o):
    d = decide_6max(o)
    pct = ps.percentile(hand_class(*o["hole"]))
    print(f"{label:42} -> {d['action']:5} {d['amount'] or '':>6}  (pct {pct:.2f}) | {d['rationale']['reasoning']}")


print("# Read #3 fix — facing a BIG 3bet (was: fold all but top ~4%):")
show("AJo vs big 3bet (should CONTINUE)", obs(["Ah", "Js"], to_call=4000, pot=5000, cur_bet=4286,
                                              position="HJ", preflop_raises=2))
show("KQs vs big 3bet (should CONTINUE)", obs(["Kh", "Qh"], to_call=4000, pot=5000, cur_bet=4286,
                                              position="CO", preflop_raises=2))
show("72o vs big 3bet (should FOLD)", obs(["7d", "2c"], to_call=4000, pot=5000, cur_bet=4286,
                                          position="HJ", preflop_raises=2))

print("\n# Read #1 fix — underpair shouldn't call down:")
show("44 on K92-8 turn vs barrel (FOLD)", obs(["4d", "4s"], board=["Kh", "9c", "2d", "8s"],
                                              to_call=2000, pot=3000, street="turn", position="BB"))
show("AK top pair on K72 flop vs bet (CALL/RAISE)", obs(["Ah", "Kd"], board=["Ks", "7c", "2d"],
                                                        to_call=300, pot=600, street="flop", position="BB"))

print("\n# Read #2 fix — flatting capped vs an open:")
show("KJo CO vs UTG open (tighter flat)", obs(["Kh", "Jd"], to_call=250, pot=400, cur_bet=250,
                                              position="CO", preflop_raises=1, n_active=3))
show("AQs unopened BTN (OPEN)", obs(["As", "Qs"], position="BTN"))
