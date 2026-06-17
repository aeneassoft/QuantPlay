"""Benchmark our bot vs Slumbot (a strong, near-GTO HU NLHE bot) via its public API.

Slumbot hosts the game (200bb deep, 50/100 blinds). We reconstruct each decision point
from its action string, ask our bot to decide, and translate the action back. Win-rate is
reported in bb/100 — the standard external measure of poker strength.

Run:  python -m pokerbot.benchmark.slumbot --hands 300 [--verbose]
"""
from __future__ import annotations

import argparse
import json
import math
import time
import urllib.request

import pokerbot.strategy.bot as botmod
from pokerbot import config
from pokerbot.strategy.bot import PokerBot

HOST = "https://slumbot.com"
SB, BB, STACK = 50, 100, 20000
STREETS = ["preflop", "flop", "turn", "river"]


def _post(path: str, body: dict) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(HOST + path, data=data,
                                 headers={"Content-Type": "application/json"})
    for attempt in range(4):
        try:
            return json.loads(urllib.request.urlopen(req, timeout=30).read())
        except Exception as e:  # noqa: BLE001
            if attempt == 3:
                raise
            time.sleep(1.5 * (attempt + 1))
    return {}


def parse_tokens(seg: str) -> list[str]:
    toks, i = [], 0
    while i < len(seg):
        ch = seg[i]
        if ch in "kcf":
            toks.append(ch)
            i += 1
        elif ch == "b":
            j = i + 1
            while j < len(seg) and seg[j].isdigit():
                j += 1
            toks.append(seg[i:j])
            i = j
        else:
            i += 1
    return toks


def build_state(hole: list[str], board: list[str], action: str,
                client_pos: int, button: int) -> dict | None:
    """Reconstruct a state dict (our bot's format) from Slumbot's action string.

    `button` is the seat (0/1) that is the small blind / button this hand: it posts the SB
    and acts first preflop, last postflop. Returns None if the hand is already over.
    """
    other = 1 - button
    committed = [0, 0]            # chips from completed streets
    street_contrib = [0, 0]
    current_bet = 0
    last_raise = BB
    history: list[dict] = []
    folded = None

    segs = action.split("/")
    sname = "preflop"
    actor = button
    for si, seg in enumerate(segs):
        if si == 0:
            street_contrib = [0, 0]
            street_contrib[button] = SB
            street_contrib[other] = BB
            current_bet, last_raise, actor, sname = BB, BB, button, "preflop"
        else:
            committed[0] += street_contrib[0]
            committed[1] += street_contrib[1]
            street_contrib = [0, 0]
            current_bet, last_raise, actor = 0, BB, other   # BB (non-button) first postflop
            sname = STREETS[si]
        for tok in parse_tokens(seg):
            if tok == "f":
                folded = actor
                history.append({"street": sname, "player": actor, "action": "fold"})
            elif tok == "k":
                history.append({"street": sname, "player": actor, "action": "check"})
            elif tok == "c":
                cap = STACK - committed[actor]
                street_contrib[actor] = min(current_bet, cap)
                history.append({"street": sname, "player": actor, "action": "call"})
            elif tok and tok[0] == "b":
                to = int(tok[1:])
                inc = to - current_bet
                if inc >= last_raise:
                    last_raise = inc
                street_contrib[actor] = to
                current_bet = to
                history.append({"street": sname, "player": actor, "action": "raise", "to": to})  # "to" (chips) = additive (consumers ignore extra keys); used by the LLM-adapter's spot line
            actor = 1 - actor

    if folded is not None:
        return None

    hero = client_pos
    opp = 1 - hero
    hero_stack = STACK - committed[hero] - street_contrib[hero]
    opp_stack = STACK - committed[opp] - street_contrib[opp]
    to_call = current_bet - street_contrib[hero]
    opp_all_in = opp_stack == 0
    is_bet = current_bet == 0
    raise_max = street_contrib[hero] + hero_stack
    can_raise = hero_stack > to_call and not opp_all_in
    if is_bet:
        raise_min = min(street_contrib[hero] + BB, raise_max)
    else:
        raise_min = min(current_bet + last_raise, raise_max)

    def pview(k: int) -> dict:
        return {"idx": k, "name": ("Hero" if k == hero else "Slumbot"),
                "stack": STACK - committed[k] - street_contrib[k],
                "hole": hole if k == hero else ["??", "??"],
                "folded": False, "all_in": (STACK - committed[k] - street_contrib[k]) == 0,
                "committed_street": street_contrib[k],
                "committed_total": committed[k] + street_contrib[k],
                "is_button": k == button}

    return {
        "hand_no": 0, "button": button, "street": sname, "board": board,
        "pot": committed[0] + committed[1] + street_contrib[0] + street_contrib[1],
        "current_bet": current_bet, "to_act": hero, "hand_over": False, "result": None,
        "sb": SB, "bb": BB, "history": history,
        "players": [pview(0), pview(1)],
        "legal": {"to_act": hero, "to_call": to_call, "can_fold": to_call > 0,
                  "can_check": to_call == 0, "can_call": to_call > 0,
                  "call_amount": min(to_call, hero_stack), "can_raise": can_raise,
                  "is_bet": is_bet, "raise_min": raise_min, "raise_max": raise_max,
                  "pot": committed[0] + committed[1] + street_contrib[0] + street_contrib[1]},
    }


def decision_to_incr(dec: dict, state: dict) -> str:
    a = dec["action"]
    if a == "fold":
        return "f"
    if a == "check":
        return "k"
    if a == "call":
        return "c"
    if a == "allin":
        return "b" + str(state["legal"]["raise_max"])
    if a in ("bet", "raise"):
        return "b" + str(int(dec["amount"]))
    raise ValueError(f"bad action {a}")


def play_hand(bot: PokerBot, token: str | None, verbose: bool = False) -> tuple[int, str]:
    resp = _post("/api/new_hand", {"token": token} if token else {})
    token = resp.get("token", token)
    client_pos = resp.get("client_pos", 0)
    first_action = resp.get("action", "")
    # The SB/button acts first preflop: that's us iff no action has happened yet.
    button = client_pos if first_action == "" else 1 - client_pos
    guard = 0
    last_hole, last_board, last_cpos = [], [], client_pos
    while True:
        if "error_msg" in resp and resp["error_msg"]:
            if verbose:
                print("  ERROR:", resp["error_msg"], "| action:", resp.get("action"))
            return 0, token
        if resp.get("winnings") is not None:
            try:                                       # LIVE-LEARNING: feed the completed hand to the opp model
                if hasattr(bot, "observe_hand_end"):
                    bot.observe_hand_end(build_state(last_hole, resp.get("board", last_board),
                                                     resp.get("action", ""), last_cpos, button))
            except Exception:  # noqa: BLE001
                pass
            return resp["winnings"], token
        last_hole = resp["hole_cards"]
        last_board = resp.get("board", last_board) or last_board
        last_cpos = resp["client_pos"]
        st = build_state(resp["hole_cards"], resp.get("board", []),
                         resp.get("action", ""), resp["client_pos"], button)
        if st is None:  # not our turn / hand resolving
            if resp.get("winnings") is not None:
                return resp["winnings"], token
            return 0, token
        bot.hero_idx = resp["client_pos"]
        dec = bot.decide(st)
        incr = decision_to_incr(dec, st)
        if verbose:
            print(f"  [{st['street']}] hero {resp['hole_cards']} board {resp.get('board')} "
                  f"-> {dec['action']} {dec.get('amount') or ''} (incr={incr})")
        resp = _post("/api/act", {"token": token, "incr": incr})
        token = resp.get("token", token)
        guard += 1
        if guard > 60:
            return resp.get("winnings") or 0, token


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hands", type=int, default=300)
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--iters", type=int, default=600, help="equity MC iters (speed)")
    ap.add_argument("--exploit", action="store_true", help="load the learned Slumbot fold model")
    ap.add_argument("--exploit-primary", dest="exploit_primary", action="store_true",
                    help="EXPLOIT-PRIMARY (#49): exploit=ON + seed the Dirichlet model from slumbot_fold.json")
    args = ap.parse_args()
    botmod.EQUITY_ITERS = args.iters

    bot = PokerBot(0, seed=7, exploit=bool(args.exploit_primary))   # exploit-primary turns the river EV engine ON
    if args.exploit or args.exploit_primary:
        from pokerbot.strategy.postflop import LearnedFoldModel
        fm = LearnedFoldModel.load(config.KNOWLEDGE_DIR / "exploit" / "slumbot_fold.json")
        if fm:
            bot.fold_model = fm
            print("Loaded learned Slumbot fold model -> fold-equity-optimal sizing ON")
    if args.exploit_primary:
        from pokerbot.strategy.opp_model import seed_from_fold_curve
        n = seed_from_fold_curve(bot.opp_model)
        print(f"EXPLOIT-PRIMARY: seeded {n} river buckets from slumbot_fold.json -> river EV engine ON")
    token = None
    winnings: list[int] = []
    t0 = time.time()
    for h in range(args.hands):
        w, token = play_hand(bot, token, verbose=args.verbose and h < 5)
        winnings.append(w)
        if (h + 1) % 20 == 0:
            total = sum(winnings)
            bb100 = total / len(winnings)        # see README: bb/100 == mean chips/hand here
            print(f"  {h+1:4d} hands | total {total:+d} chips | {bb100:+.1f} bb/100 "
                  f"| {(time.time()-t0)/(h+1)*1000:.0f} ms/hand", flush=True)

    total = sum(winnings)
    n = len(winnings)
    bb100 = total / n
    std = (sum((w - total / n) ** 2 for w in winnings) / n) ** 0.5 / BB
    stderr = std / math.sqrt(n) * 100
    print(f"\n=== RESULT vs Slumbot ===")
    print(f"hands={n} | total={total:+d} chips | win-rate {bb100:+.1f} bb/100 "
          f"(±{stderr:.1f} stderr)")
    if args.exploit_primary:
        obs = sum(sum(c) for c in bot.opp_model.counts.values())
        print(f"opp_model: {obs:.0f} total counts across {len(bot.opp_model.counts)} buckets "
              f"(seed ~2880; live-learning grew it by ~{obs-2880:.0f})")
        bot.opp_model.save(config.DATA_DIR / "opp_model_slumbot.json")


if __name__ == "__main__":
    main()
