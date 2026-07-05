"""All-in-EV adjustment for a Slumbot solver run — the VARIANCE LEVER (Req C).

Reads the rich per-hand JSONL produced by `slumbot_llm.py --bot solver` (one row/hand, fields hole_cards, board,
bot_hole_cards, action, winnings, won_pot, client_pos, button) and reports TWO win-rates:

  (1) RAW       bb/100 +/- stderr  = the realized chips (the must-have number),
  (2) ADJUSTED  bb/100 +/- stderr  = for pots that went ALL-IN BEFORE THE RIVER with BOTH hands known, REPLACE the
      realized (lucky/unlucky) runout with the EQUITY-EV of hero's hand vs villain's EXACT hand on the partial board
      that was out when the chips went in:  adjusted_net = equity * final_pot - hero_invested.  Every other hand keeps
      its realized net. This cancels the all-in card luck (AIVAT-lite) -> a tighter estimate at the same sample size.

WHY all-in-BEFORE-river only: once the river is dealt the result is deterministic (no runout variance left to cancel),
so a river all-in's realized net already IS its EV — adjusting it changes nothing and only risks introducing error.

HONEST on the pot/investment extraction: chips are taken from the action string (Slumbot's `b<to>` are TOTAL street
commitments, blinds SB=50/BB=100, 200bb=20000 stacks) reconstructed exactly as slumbot.build_state does. We detect the
all-in street as the first street on which either player's cumulative commitment hits the 20000 stack. `hero_invested`
and `final_pot` come from that same reconstruction (NOT from the realized `winnings`, so the adjustment is independent
of the outcome). The equity board = the cards dealt UP TO AND INCLUDING the all-in street (flop=3, turn=4). Equity is
the EXACT 2-card-vs-2-card value (engine `equity_vs_hand`: river-complete enumerates, pre-river uses MC iters).

Run:  python -m pokerbot.benchmark.slumbot_adjust data/slumbot_solver.jsonl [--iters 20000]
"""
from __future__ import annotations

import argparse
import json
import math

from pokerbot.benchmark.slumbot import BB, SB, STACK, STREETS, parse_tokens
from pokerbot.engine.equity import equity_vs_hand

# Board-card counts revealed at the START of each postflop street's betting (the cards out when an all-in lands there).
_BOARD_AT = {"flop": 3, "turn": 4, "river": 5}


def _reconstruct(action: str, button: int) -> dict:
    """Reconstruct per-player committed chips + the all-in street from a Slumbot action string. MIRRORS the betting
    bookkeeping in slumbot.build_state (same SB/BB blinds, same 'b<to>'=total-street-commit semantics) but walks the
    WHOLE hand to the end. Returns {committed:[c0,c1], allin_street:str|None, last_street:str}.

    committed[k] = seat k's TOTAL chips in the pot at hand end. allin_street = the FIRST street where either seat's
    cumulative commitment reached the STACK (=all-in); None if no all-in. last_street = the final street reached.
    """
    other = 1 - button
    committed = [0, 0]                  # chips from COMPLETED streets
    street_contrib = [0, 0]            # chips committed on the CURRENT street
    allin_street = None
    sname = "preflop"

    segs = action.split("/")
    for si, seg in enumerate(segs):
        if si == 0:
            street_contrib = [0, 0]
            street_contrib[button] = SB
            street_contrib[other] = BB
            current_bet, actor, sname = BB, button, "preflop"
        else:
            committed[0] += street_contrib[0]
            committed[1] += street_contrib[1]
            street_contrib = [0, 0]
            current_bet, actor, sname = 0, other, STREETS[si]    # BB (non-button) acts first postflop
        for tok in parse_tokens(seg):
            if tok == "f":
                pass                                              # fold: no chips move; pot already counted
            elif tok == "k":
                pass
            elif tok == "c":
                cap = STACK - committed[actor]
                street_contrib[actor] = min(current_bet, cap)
            elif tok and tok[0] == "b":
                # Slumbot's b<to> is the TOTAL street commitment to raise TO. Cap at the actor's remaining stack so a
                # malformed/oversized 'to' can't push committed past STACK (real all-ins already sit at the stack).
                to = min(int(tok[1:]), STACK - committed[actor])
                street_contrib[actor] = to
                current_bet = to
            # all-in = this seat's cumulative commitment reaching the full stack on THIS street
            if allin_street is None and committed[actor] + street_contrib[actor] >= STACK:
                allin_street = sname
            actor = 1 - actor

    committed[0] += street_contrib[0]
    committed[1] += street_contrib[1]
    return {"committed": committed, "allin_street": allin_street, "last_street": sname}


def _adjusted_net(row: dict, iters: int) -> tuple[float, bool]:
    """(net_chips, was_adjusted). If the hand went all-in BEFORE the river with both hands known, return the equity-EV
    net; else return the realized winnings unchanged. was_adjusted flags which path was taken (for the count)."""
    realized = float(row.get("winnings", row["net_bb"] * BB))
    bot_hole = row.get("bot_hole_cards")
    action = row.get("action") or ""
    board = row.get("board") or []
    button = row.get("button")
    client_pos = row.get("client_pos")
    if not bot_hole or button is None or client_pos is None or "/" not in action:
        return realized, False                                  # no showdown reveal / pre-flop fold / no street info

    rec = _reconstruct(action, button)
    allin = rec["allin_street"]
    if allin is None or allin == "river":                       # not all-in, or all-in only ON the river (no variance)
        return realized, False

    n_board = _BOARD_AT[allin]                                  # cards out when the chips went in (flop=3, turn=4)
    if len(board) < n_board:
        return realized, False                                  # malformed board -> keep realized (honest fallback)
    partial = list(board[:n_board])
    hero = list(row["hole_cards"])
    villain = list(bot_hole)

    eq = equity_vs_hand(hero, villain, partial, iters=iters)    # hero equity vs the EXACT villain hand on the partial board
    final_pot = float(sum(rec["committed"]))
    hero_invested = float(rec["committed"][client_pos])         # client_pos is hero's seat (0/1) this hand
    return eq * final_pot - hero_invested, True


def _bb100(nets: list[float]) -> tuple[float, float]:
    """(mean bb/100, stderr_bb100) from a list of per-hand NET CHIPS. MATCHES slumbot_llm.ProgressLog.summary exactly:
    bb/100 = mean(net_chips)/BB*100 (a per-hand bb mean scaled to 100 hands; == mean chips/hand when BB=100), and
    stderr = sample-std(net_chips)/BB/sqrt(n)*100. Both in the SAME unit (bb/100) — the earlier mean/BB was bb-per-HAND
    (100x too small) while the stderr was already bb/100, a unit mismatch."""
    n = len(nets)
    if n == 0:
        return 0.0, 0.0
    mean = sum(nets) / n
    var = sum((x - mean) ** 2 for x in nets) / n
    return mean / BB * 100, (var ** 0.5 / BB) / math.sqrt(n) * 100


def analyze(path: str, iters: int = 20000) -> dict:
    """Read the rich JSONL, return {n, raw_bb100, raw_stderr, adj_bb100, adj_stderr, n_adjusted, n_showdown}."""
    raw_nets: list[float] = []
    adj_nets: list[float] = []
    n_adjusted = n_showdown = 0
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if "winnings" not in row and "net_bb" not in row:
                continue                                        # not a hand row
            realized = float(row.get("winnings", row.get("net_bb", 0) * BB))
            raw_nets.append(realized)
            if row.get("bot_hole_cards"):
                n_showdown += 1
            adj, was_adj = _adjusted_net(row, iters)
            adj_nets.append(adj)
            n_adjusted += int(was_adj)
    raw_bb100, raw_se = _bb100(raw_nets)
    adj_bb100, adj_se = _bb100(adj_nets)
    return {"n": len(raw_nets), "raw_bb100": raw_bb100, "raw_stderr": raw_se,
            "adj_bb100": adj_bb100, "adj_stderr": adj_se,
            "n_adjusted": n_adjusted, "n_showdown": n_showdown}


def main() -> None:
    ap = argparse.ArgumentParser(description="All-in-EV adjusted bb/100 from a Slumbot solver rich JSONL log.")
    ap.add_argument("path", help="the --progress-out JSONL from `slumbot_llm.py --bot solver`")
    ap.add_argument("--iters", type=int, default=20000,
                    help="equity MC iters for flop/turn all-ins (river all-ins are skipped; turn enumerates 1 card)")
    a = ap.parse_args()
    r = analyze(a.path, a.iters)
    print(f"=== Slumbot solver run: {a.path} ===")
    print(f"hands={r['n']}  showdowns(bot_hole_cards seen)={r['n_showdown']}  "
          f"all-in-pre-river adjusted={r['n_adjusted']}")
    print(f"  RAW      : {r['raw_bb100']:+.1f} bb/100 (+/-{r['raw_stderr']:.1f} stderr)")
    print(f"  ADJUSTED : {r['adj_bb100']:+.1f} bb/100 (+/-{r['adj_stderr']:.1f} stderr)   "
          f"[{r['n_adjusted']} all-in-pre-river pots replaced by equity-EV]")
    if r["n_adjusted"] == 0:
        print("  NOTE: no all-in-before-river showdowns in this log -> ADJUSTED == RAW (nothing to de-variance).")


if __name__ == "__main__":
    main()
