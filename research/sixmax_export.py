"""6-MAX GTOW-Analyzer export (user idea 2026-07-04): play our 6-max PRODUCT bot ("Hero", the tag core) vs the
league, export PokerStars 6-max hand histories, upload to GTO Wizard's ANALYZER (Chrome) -> the FIRST absolute
per-decision GTO grading of our 6-max play (by street/position). The 6-max twin of research/pokerstars_export.py.

GTOW-gradability: hero's sizes are SNAPPED to GTOW-tree conventions (preflop open 2.5bb / raise 3x, postflop
pf.snap_to_tree) — the HU study's lesson: off-tree play is UNGRADEABLE. Villains stay natural (their sizes don't
matter for hero's grade). Button rotates each hand -> hero is graded in all 6 positions.

  python -m research.sixmax_export --n 300 --out data/gtow_upload/sixmax_hands.txt
Then upload the file in GTO Wizard -> Analyze -> Upload hands (PokerStars format).
"""
from __future__ import annotations

import argparse
import datetime
import os

from pokerbot.arena.sixmax import PROFILES, SixMaxBot
from pokerbot.engine.evaluator import best_five_name
from pokerbot.engine.table import Table
from pokerbot.strategy import postflop as pf

SB, BB, STACK = 50, 100, 10000          # $0.50/$1, 100bb — the standard GTOW 6-max cash geometry
BASE_ID = 2800000000
BASE_DT = datetime.datetime(2026, 7, 1, 18, 0, 0)
HERO = 0                                 # hero seat is fixed; the BUTTON rotates -> all positions covered


def money(chips: float) -> str:
    v = chips / 100.0
    return f"${int(v)}" if v == int(v) else f"${v:.2f}"


def _snap_hero(table: Table, decision: dict) -> tuple[str, int | None]:
    """Clamp hero's chosen size onto GTOW-tree conventions (gradability): preflop open=2.5bb / reraise=3x the
    current bet; postflop bets via pf.snap_to_tree. Villain-legality is enforced by table.act anyway."""
    action, amount = decision["action"], decision.get("amount")
    if action not in ("bet", "raise") or amount is None:
        return action, amount
    la = table.legal_actions()
    lo, hi = la.get("raise_min"), la.get("raise_max")
    if table.street == "preflop":
        cur = table.current_bet
        target = round(2.5 * BB) if cur <= BB else 3 * cur       # open 2.5x / 3bet+ = 3x the last raise-to
    else:
        committed = table.seats[HERO].committed_street
        pot = table.pot()
        if la.get("to_call", 0) <= 0:                            # first-in bet: snap the pot fraction
            target = committed + pf.snap_to_tree(int(amount - committed), max(1, pot), table.street)
        else:
            target = amount                                       # postflop raise: keep (rare; census is HU-only)
    if lo is not None:
        target = max(lo, target)
    if hi is not None:
        target = min(hi, target)
    return action, int(target)


class HybridHero:
    """Das ECHTE Produkt (--hybrid): tag-Kern multiway, und sobald der Pot heads-up Hero-vs-EIN-Villain ist,
    entscheidet der validierte Prince v2.2 — exakt der Verbund, den der Trainer im GTO-Modus live spielt
    (six_server.Session._prince_seat/_prince_decide). Fail-soft: jedes Prince-Problem fällt auf den Kern."""

    def __init__(self):
        from pokerbot.coach.oracle import PrinceOracle
        self.bot = SixMaxBot(HERO, PROFILES["tag"])
        self.bot._read = lambda obs: {}          # GTO-Modus-Parität: Liga-Exploit-Reads AUS
        self.prince = PrinceOracle()
        self.table = None
        self.prince_decisions = 0

    def bind_table(self, table):
        self.table = table

    def _heads_up(self) -> bool:
        live = [i for i, s in enumerate(self.table.seats) if not s.folded]
        return len(live) == 2 and HERO in live

    def decide(self, obs):
        if self.table is not None and not self.table.hand_over and self._heads_up():
            try:
                from dataclasses import asdict
                from pokerbot.brain.format_spot import spot_from_table
                from pokerbot.coach.decision_log import spot_fingerprint
                spot = asdict(spot_from_table(self.table, HERO))
                rec = {"spot": spot, "obs": self.table.obs_for(HERO), "legal": self.table.legal_actions(),
                       "history": [dict(h) for h in self.table.history if "player" in h],
                       "street": self.table.street, "hand_id": f"exp-{self.table.hand_no}",
                       "spot_fp": spot_fingerprint(spot)}
                dec = self.prince.decide(rec)
                self.prince_decisions += 1
                return dec
            except Exception:  # noqa: BLE001
                pass
        return self.bot.decide(obs)


def play_hand(table: Table, bots: dict) -> dict:
    table.start_hand()
    holes = [list(s.hole) for s in table.seats]
    button = table.button
    guard = 0
    while not table.hand_over and table.to_act is not None:
        guard += 1
        if guard > 400:
            break
        i = table.to_act
        agent = bots[i]
        if i == HERO and hasattr(agent, "bind_table"):     # Hybrid-Held braucht den Tisch (HU-Projektion)
            agent.bind_table(table)
        d = agent.decide(table.obs_for(i))
        action, amount = d["action"], d.get("amount")
        if i == HERO:
            action, amount = _snap_hero(table, d)
        try:
            table.act(action, amount)
        except Exception:  # noqa: BLE001 — illegal -> safe fallback (engine = truth)
            la = table.legal_actions()
            table.act("check" if la.get("can_check") else ("call" if la.get("can_call") else "fold"))
    return {"holes": holes, "history": list(table.history), "result": table.result, "button": button,
            "names": [s.name for s in table.seats]}


def format_hand(hand_id, dt, h) -> str:
    names, button, holes = h["names"], h["button"], h["holes"]
    n = len(names)
    sb_i, bb_i = (button + 1) % n, (button + 2) % n
    L = [f"PokerStars Hand #{hand_id}:  Hold'em No Limit ({money(SB)}/{money(BB)} USD) - "
         f"{dt.strftime('%Y/%m/%d %H:%M:%S')} ET",
         f"Table 'PokerB6' 6-max Seat #{button + 1} is the button"]
    for k in range(n):
        L.append(f"Seat {k + 1}: {names[k]} ({money(STACK)} in chips)")
    L.append(f"{names[sb_i]}: posts small blind {money(SB)}")
    L.append(f"{names[bb_i]}: posts big blind {money(BB)}")
    L.append("*** HOLE CARDS ***")
    L.append(f"Dealt to {names[HERO]} [{holes[HERO][0]} {holes[HERO][1]}]")

    street_commit = {k: 0 for k in range(n)}
    total_commit = {k: 0 for k in range(n)}
    street_commit[sb_i] = SB; street_commit[bb_i] = BB
    total_commit[sb_i] = SB; total_commit[bb_i] = BB
    cur_bet = BB
    fold_street = {}                                       # seat -> street folded

    HEADER = {"flop": "*** FLOP ***", "turn": "*** TURN ***", "river": "*** RIVER ***"}
    for ev in h["history"]:
        act = ev.get("action")
        if act == "blinds":
            continue
        if act == "deal":
            board = ev["board"]
            st = ev["street"]
            if st == "flop":
                L.append(f"{HEADER[st]} [{' '.join(board[:3])}]")
            elif st == "turn":
                L.append(f"{HEADER[st]} [{' '.join(board[:3])}] [{board[3]}]")
            elif st == "river":
                L.append(f"{HEADER[st]} [{' '.join(board[:4])}] [{board[4]}]")
            street_commit = {k: 0 for k in range(n)}
            cur_bet = 0
            continue
        p = ev.get("player")
        if p is None:
            continue
        nm = names[p]
        if act == "fold":
            fold_street[p] = ev["street"]
            L.append(f"{nm}: folds")
        elif act == "check":
            L.append(f"{nm}: checks")
        elif act == "call":
            amt = ev.get("amount", 0)
            street_commit[p] += amt; total_commit[p] += amt
            L.append(f"{nm}: calls {money(amt)}")
        elif act in ("bet", "raise"):
            to = ev["to"]
            inc = to - cur_bet
            amt = to - street_commit[p]
            total_commit[p] += amt; street_commit[p] = to
            if act == "bet" or cur_bet == 0:
                L.append(f"{nm}: bets {money(to)}")
            else:
                L.append(f"{nm}: raises {money(inc)} to {money(to)}")
            cur_bet = to

    # uncalled-bet refund: the top committer's unmatched excess over the 2nd-highest total
    tc = sorted(total_commit.items(), key=lambda kv: -kv[1])
    uncalled = tc[0][1] - tc[1][1]
    if uncalled > 0:
        L.append(f"Uncalled bet ({money(uncalled)}) returned to {names[tc[0][0]]}")
    res = h["result"] or {}
    winners = res.get("winners", [])
    pot_paid = sum(w["amount"] for w in winners) - (uncalled if uncalled > 0 else 0)
    if res.get("reason") == "showdown":
        L.append("*** SHOW DOWN ***")
        live = [k for k in range(n) if k not in fold_street]
        for k in live:
            rank = best_five_name(board_res, holes[k]) if (board_res := res.get("board")) else None
            L.append(f"{names[k]}: shows [{holes[k][0]} {holes[k][1]}]" + (f" ({rank})" if rank else ""))
        for w in winners:
            amt = w["amount"] - (uncalled if w["seat"] == tc[0][0] and uncalled > 0 else 0)
            if amt > 0:
                L.append(f"{names[w['seat']]} collected {money(amt)} from pot")
    else:
        for w in winners:
            amt = w["amount"] - (uncalled if w["seat"] == tc[0][0] and uncalled > 0 else 0)
            L.append(f"{names[w['seat']]} collected {money(amt)} from pot")

    L.append("*** SUMMARY ***")
    L.append(f"Total pot {money(max(0, pot_paid))} | Rake $0")
    board = res.get("board") or []
    if board:
        L.append(f"Board [{' '.join(board)}]")
    for k in range(n):
        tags = ""
        if k == button:
            tags += " (button)"
        if k == sb_i:
            tags += " (small blind)"
        if k == bb_i:
            tags += " (big blind)"
        won = next((w for w in winners if w["seat"] == k), None)
        wamt = (won["amount"] - (uncalled if won and won["seat"] == tc[0][0] and uncalled > 0 else 0)) if won else 0
        if k in fold_street:
            fp = ("folded before Flop" if fold_street[k] == "preflop"
                  else f"folded on the {fold_street[k].capitalize()}")
            if fold_street[k] == "preflop" and total_commit[k] == 0:
                fp += " (didn't bet)"
            L.append(f"Seat {k + 1}: {names[k]}{tags} {fp}")
        elif won and res.get("reason") == "showdown":
            L.append(f"Seat {k + 1}: {names[k]}{tags} showed [{holes[k][0]} {holes[k][1]}] and won "
                     f"({money(wamt)}) with {won.get('rank', 'a hand')}")
        elif won:
            L.append(f"Seat {k + 1}: {names[k]}{tags} collected ({money(wamt)})")
        elif res.get("reason") == "showdown":
            L.append(f"Seat {k + 1}: {names[k]}{tags} showed [{holes[k][0]} {holes[k][1]}] and lost")
        else:
            L.append(f"Seat {k + 1}: {names[k]}{tags} mucked")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--idbase", type=int, default=BASE_ID)
    ap.add_argument("--dayoffset", type=int, default=0)
    ap.add_argument("--hero-profile", default="tag", help="hero = the PRODUCT bot core (default 'tag')")
    ap.add_argument("--hybrid", action="store_true",
                    help="Hero = das ECHTE Produkt: tag-Kern multiway + Prince v2.2 sobald der Pot heads-up "
                         "ist (derselbe Verbund wie im Trainer-GTO-Modus). Braucht POKERB_PRINCE=1.")
    ap.add_argument("--villains", default="tag,lag,nit,station,maniac")
    ap.add_argument("--out", default="data/gtow_upload/sixmax_hands.txt")
    args = ap.parse_args()

    vills = args.villains.split(",")
    names = ["Hero"] + [f"Villain{i+1}" for i in range(5)]
    table = Table(names, starting_stack=STACK, sb=SB, bb=BB, seed=args.seed, human_seat=-1)
    bots = {HERO: (HybridHero() if args.hybrid else SixMaxBot(HERO, PROFILES[args.hero_profile]))}
    for i in range(1, 6):
        bots[i] = SixMaxBot(i, PROFILES[vills[(i - 1) % len(vills)]])
    import random
    for i, b in bots.items():
        b.rng = random.Random(args.seed * 100 + i)

    blocks = []
    for i in range(args.n):
        for s in table.seats:
            s.stack = STACK                                   # cash-game reset to 100bb each hand
        h = play_hand(table, bots)
        dt = BASE_DT + datetime.timedelta(days=args.dayoffset, minutes=2 * i)
        blocks.append(format_hand(args.idbase + i, dt, h))
    text = "\n\n".join(blocks) + "\n"
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"WROTE {len(blocks)} 6-max hands -> {args.out}  ({len(text)} chars)")
    if args.hybrid:                                        # Beleg, dass der HU-Takeover wirklich gegriffen hat
        print(f"HYBRID: {bots[HERO].prince_decisions} Prince-v2.2-Entscheidungen in {len(blocks)} Händen")
    print("\n===== FIRST HAND PREVIEW =====\n")
    print(blocks[0])


if __name__ == "__main__":
    main()
