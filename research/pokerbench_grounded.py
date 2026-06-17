"""Use the PokerBench DB (563k 6-max GTO decisions, RZ412/PokerBench) as a GROUNDED reference for our 6-max
bot. PokerBench is templated NL -> GTO action; we parse it into a structured spot so we can (next step) put
our SixMaxBot in the same spot and compare its action to GTO = grounded blindspots for the MAIN-APP 6-max bot.
This is the free 'bigger database' we already have (used only for Qwen training so far).

Step 1 (this file): a robust PARSER + a parseability self-test on a streamed sample.

Run:  python -m extraction.pokerbench_grounded --n 200
"""
from __future__ import annotations

import argparse
import itertools
import re

_RANK = {"two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8",
         "nine": "9", "ten": "T", "jack": "J", "queen": "Q", "king": "K", "ace": "A"}
_SUIT = {"spade": "s", "heart": "h", "diamond": "d", "club": "c"}
_CARD = re.compile(r"([A-Za-z]+)\s+[Oo]f\s+([A-Za-z]+)")
_POS = ("UTG", "HJ", "CO", "BTN", "SB", "BB")


def _cards(text: str) -> list[str]:
    out = []
    for rank, suit in _CARD.findall(text):
        r, s = _RANK.get(rank.lower()), _SUIT.get(suit.lower())
        if r and s:
            out.append(r + s)
    return out


def parse_spot(instruction: str, output: str) -> dict | None:
    try:
        hero = re.search(r"your position is (\w+)", instruction)
        hole_m = re.search(r"holding is \[([^\]]+)\]", instruction)
        pot_m = re.search(r"current pot size is ([\d.]+)", instruction)
        if not (hero and hole_m and pot_m):
            return None
        hole = _cards(hole_m.group(1))
        # board: collect cards mentioned on flop/turn/river "comes ..." lines
        board = []
        for st, pat in (("flop", r"flop comes ([^\.]+)\."), ("turn", r"turn comes ([^\.,]+)"),
                        ("river", r"river comes ([^\.,]+)")):
            m = re.search(pat, instruction)
            if m:
                board += _cards(m.group(1))
        street = "river" if "river comes" in instruction else \
                 "turn" if "turn comes" in instruction else \
                 "flop" if "flop comes" in instruction else "preflop"
        # the last action the hero faces (to infer to_call): look at the tail before "Now it is your turn"
        head = instruction.split("Now it is your turn")[0]
        last = re.findall(r"(raise|bet|call|check|fold)\s*([\d.]*)", head.lower())
        facing = "check"
        if last:
            facing = last[-1][0]
        act = output.strip().split()
        gto_action = act[0].lower() if act else None
        gto_amt = float(act[1]) if len(act) > 1 and re.match(r"^[\d.]+$", act[1]) else None
        if len(hole) != 2 or (street != "preflop" and len(board) < 3):
            return None
        return {"hero_pos": hero.group(1), "hole": hole, "board": board, "street": street,
                "pot": float(pot_m.group(1)), "facing": facing,
                "gto_action": gto_action, "gto_amount": gto_amt}
    except Exception:  # noqa: BLE001
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    args = ap.parse_args()
    from datasets import load_dataset
    ds = load_dataset("RZ412/PokerBench", "default", split="train", streaming=True)
    ok, fail, by_street, by_action = 0, 0, {}, {}
    sample = None
    for r in itertools.islice(ds, args.n):
        s = parse_spot(r["instruction"], r["output"])
        if s is None:
            fail += 1
            continue
        ok += 1
        by_street[s["street"]] = by_street.get(s["street"], 0) + 1
        by_action[s["gto_action"]] = by_action.get(s["gto_action"], 0) + 1
        if sample is None and s["street"] in ("turn", "river"):
            sample = s
    print(f"PARSEABILITY: {ok}/{ok+fail} parsed ({100*ok/max(1,ok+fail):.0f}%)")
    print(f"by street: {by_street}")
    print(f"GTO action distribution: {by_action}")
    print(f"sample parsed spot: {sample}")


if __name__ == "__main__":
    main()
