"""End-to-end sim: wire the SixMaxBot agents through a real Session, play passive hands, confirm no
crash + that a bot accumulates an opponent model of the human from public actions only."""
from pokerbot.web.six_server import HUMAN, Session

s = Session()
for _ in range(25):
    try:
        s.start_hand()
    except (RuntimeError, ValueError):
        break                       # a player busted; table can't deal another hand
    guard = 0
    while not s.table.hand_over and guard < 60:
        if s.table.to_act == HUMAN:
            la = s.table.legal_actions()
            a = "check" if la.get("can_check") else ("call" if la.get("can_call") else "fold")
            s.human_action(a, None)
        else:
            s.advance()
        guard += 1

print(f"played {s.hands_done} hands, human_net {s.human_net}")
for seat in (1, 2, 3, 4, 5):
    b = s.bots[seat]
    m = b.opp[HUMAN]
    print(f"  {b.k.name:8} (seat {seat}) model of human: hands={m.hands} vpip={m.vpip} pfr={m.pfr} "
          f"faced_bet={m.faced_bet} fold_to_bet={m.fold_to_bet()} aggr={m.aggression()}")
