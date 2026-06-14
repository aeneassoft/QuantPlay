"""Decision-alignment benchmark: how often does our 6-max bot make the SAME decision as
Pluribus (superhuman) in identical spots?

Replays the 10,000 Pluribus hand histories, reconstructs the EXACT observation at every
decision node, asks `decide_6max`, and compares the action category (aggressive / call /
check / fold) — and, for bets/raises, the sizing. The headline metric is agreement on the
Pluribus seats; we also report by street and a confusion breakdown.

Byproduct (honors "save data so we can train an AI"): writes a clean
`data/training/pluribus_decisions.jsonl` of (observation -> action) pairs for ALL seats —
directly reusable as an imitation-learning dataset. Everything stays local; no data leaves.

Run:  python -m pokerbot.benchmark.pluribus_bench [--max-hands N] [--iters N]
"""
from __future__ import annotations

import argparse
import glob
import json
import tomllib
from collections import Counter, defaultdict

from pokerbot import config
from pokerbot.arena import sixmax

SRC = config.ROOT / "data" / "_phh_repo" / "data" / "pluribus"
OUT = config.DATA_DIR / "training" / "pluribus_decisions.jsonl"
POS6 = ["BTN", "SB", "BB", "UTG", "MP", "CO"]
POSMAP = {"UTG": "EP", "MP": "MP", "CO": "CO", "BTN": "BTN", "SB": "SB", "BB": "BB"}
STREETS = {0: "preflop", 3: "flop", 4: "turn", 5: "river"}


def cat_actual(verb: str, to_call: int) -> str:
    if verb == "f":
        return "fold"
    if verb == "cbr":
        return "aggressive"
    return "call" if to_call > 0 else "check"   # cc


def cat_bot(action: str) -> str:
    if action in ("bet", "raise"):
        return "aggressive"
    if action == "call":
        return "call"
    if action == "check":
        return "check"
    return "fold"


def replay(path: str):
    """Yield (obs, verb, amount, seat, name) for every decision node in a hand."""
    with open(path, "rb") as f:
        d = tomllib.load(f)
    players = d.get("players", [])
    n = len(players)
    blinds = d.get("blinds_or_straddles", [])
    stacks0 = d.get("starting_stacks", [])
    if n != 6 or not blinds or not stacks0:
        return
    bb = max(blinds)
    sb_amt = min((b for b in blinds if b > 0), default=0)
    sb_idx = blinds.index(sb_amt) if sb_amt else 0
    button = (sb_idx - 1) % n
    pos = {i: POS6[(i - button) % n] for i in range(n)}

    holes: dict[int, str] = {}
    board: list[str] = []
    street_commit = [0] * n
    total_commit = [0] * n
    folded = [False] * n
    for i, b in enumerate(blinds):
        street_commit[i] = b
        total_commit[i] = b
    cur_street = "preflop"
    preflop_raises = 0

    for raw in d.get("actions", []):
        tok = raw.split()
        if tok[0] == "d":
            if tok[1] == "dh":
                holes[int(tok[2][1:]) - 1] = tok[3]
            elif tok[1] == "db":
                cards = tok[2]
                board += [cards[i:i + 2] for i in range(0, len(cards), 2)]
                cur_street = STREETS.get(len(board), cur_street)
                street_commit = [0] * n     # new street resets street commitments
            continue
        if tok[1] == "sm":                  # showdown reveal
            continue
        seat = int(tok[0][1:]) - 1
        verb = tok[1]
        cur_bet = max(street_commit)
        to_call = cur_bet - street_commit[seat]
        my_stack = stacks0[seat] - total_commit[seat]
        if seat not in holes or my_stack <= 0:
            # can't query the bot without cards / already all-in; still apply the action
            pass
        else:
            obs = {
                "hole": [holes[seat][0:2], holes[seat][2:4]],
                "board": list(board),
                "bb": bb,
                "to_call": to_call,
                "pot": sum(total_commit),
                "my_stack": my_stack,
                "n_active": sum(1 for i in range(n) if not folded[i]),
                "position": POSMAP.get(pos[seat], pos[seat]),
                "preflop_raises": preflop_raises,
                "can_check": to_call == 0,
                "can_call": to_call > 0 and my_stack > 0,
                "can_raise": my_stack > to_call,
                "raise_min": cur_bet + bb,
                "raise_max": street_commit[seat] + my_stack,
                "cur_bet": cur_bet,
                "street": cur_street,
                "my_committed_street": street_commit[seat],
            }
            amt = int(tok[2]) if verb == "cbr" and len(tok) > 2 else None
            yield obs, verb, amt, seat, players[seat]

        # apply action to state
        if verb == "f":
            folded[seat] = True
        elif verb == "cbr":
            amt = int(tok[2])
            total_commit[seat] += amt - street_commit[seat]
            street_commit[seat] = amt
            if cur_street == "preflop":
                preflop_raises += 1
        elif verb == "cc":
            add = cur_bet - street_commit[seat]
            if add > 0:
                total_commit[seat] += add
                street_commit[seat] = cur_bet


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-hands", type=int, default=3000, help="0 = all 10,000")
    ap.add_argument("--iters", type=int, default=160, help="equity Monte-Carlo iters (speed)")
    args = ap.parse_args()
    sixmax.EQ_ITERS = args.iters

    files = sorted(glob.glob(str(SRC / "**" / "*.phh"), recursive=True))
    if args.max_hands:
        files = files[:args.max_hands]
    OUT.parent.mkdir(parents=True, exist_ok=True)

    n_dec = 0
    plur_total = plur_match = 0
    by_street = defaultdict(lambda: [0, 0])              # street -> [match, total] (pluribus)
    confusion = defaultdict(Counter)                     # actual_cat -> Counter(bot_cat) (pluribus)
    agg_sizes = []                                       # (bot_frac, plur_frac) when both aggressive
    divergences = []

    with open(OUT, "w", encoding="utf-8") as out:
        for fp in files:
            short = fp.replace(str(SRC), "").strip("\\/").replace("\\", "/")
            try:
                gen = replay(fp)
                for obs, verb, amount, seat, name in gen:
                    dec = decide_with(obs)
                    ac = cat_actual(verb, obs["to_call"])
                    bc = cat_bot(dec["action"])
                    is_plur = (name == "Pluribus")
                    match = (ac == bc)
                    rec = {"file": short, "seat": seat, "name": name, "is_pluribus": is_plur,
                           "street": obs["street"], "pos": obs["position"],
                           "obs": obs,
                           "actual": {"cat": ac, "verb": verb, "amount": amount},
                           "bot": {"cat": bc, "action": dec["action"], "amount": dec.get("amount")},
                           "match": match}
                    out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    n_dec += 1
                    if is_plur:
                        plur_total += 1
                        plur_match += match
                        by_street[obs["street"]][1] += 1
                        by_street[obs["street"]][0] += match
                        confusion[ac][bc] += 1
                        if ac == "aggressive" and bc == "aggressive" and amount and obs["pot"]:
                            agg_sizes.append((round((dec["amount"] or 0) / obs["pot"], 2),
                                              round(amount / obs["pot"], 2)))
                        if not match and obs["street"] != "preflop":
                            divergences.append((obs["pot"], short, obs["street"], obs["position"],
                                                ac, bc, obs["hole"], obs["board"]))
            except Exception as e:  # noqa: BLE001
                continue

    print(f"Replayed {len(files)} hands | {n_dec} total decisions logged -> {OUT}")
    print(f"Pluribus decisions compared: {plur_total}")
    if not plur_total:
        return
    print(f"\n=== AGREEMENT WITH PLURIBUS ===")
    print(f"Overall: {plur_match}/{plur_total} = {100*plur_match/plur_total:.1f}%")
    print("By street:")
    for st in ("preflop", "flop", "turn", "river"):
        m, t = by_street[st]
        if t:
            print(f"  {st:8s}: {100*m/t:5.1f}%  (n={t})")
    print("\nWhen Pluribus did X, our bot did:")
    for ac in ("aggressive", "call", "check", "fold"):
        c = confusion[ac]
        tot = sum(c.values())
        if tot:
            br = ", ".join(f"{k} {100*v/tot:.0f}%" for k, v in c.most_common())
            print(f"  {ac:10s} (n={tot:5d}): {br}")
    if agg_sizes:
        bot_avg = sum(b for b, _ in agg_sizes) / len(agg_sizes)
        plur_avg = sum(p for _, p in agg_sizes) / len(agg_sizes)
        print(f"\nBet sizing when both bet/raise (n={len(agg_sizes)}): "
              f"bot ~{bot_avg:.0%} pot vs Pluribus ~{plur_avg:.0%} pot")
    divergences.sort(reverse=True)
    print("\nBiggest postflop divergences (pot, spot, Pluribus -> us):")
    for pot, sh, st, ps, ac, bc, hole, board in divergences[:12]:
        print(f"  pot {pot/100:5.0f}bb {sh:10s} {st:5s} {ps:3s} [{' '.join(hole)}] "
              f"board[{' '.join(board)}]  Pluribus={ac} us={bc}")


def decide_with(obs: dict) -> dict:
    return sixmax.decide_6max(obs)


if __name__ == "__main__":
    main()
