"""Monte-Carlo CFR for the Heads-Up push/fold game — true GTO short-stack ranges.

This is the core Pluribus technique (counterfactual regret minimization with chance
sampling) applied to the part of HU NLHE that is small enough to solve exactly and verify:
the open-shove / call-shove game across stack depths. It replaces the bot's ad-hoc
short-stack thresholds with a computed equilibrium.

Game at stack S (bb): SB (button) posts 0.5, BB posts 1.
  SB chooses JAM (all-in S) or FOLD.
    FOLD                 -> SB -0.5, BB +0.5
    JAM, BB FOLD         -> SB +1,   BB -1
    JAM, BB CALL         -> all-in showdown for S each (winner nets +S)

Output: knowledge_base/cfr/preflop_pushfold.json   { stack: { class: {jam, call} } }
Run:  python -m pokerbot.strategy.cfr_preflop [--iters N] [--quick]
"""
from __future__ import annotations

import argparse
import json
import random

from pokerbot import config
from pokerbot.engine.cards import all_hand_classes, expand_class, hand_class, make_deck
from pokerbot.engine.evaluator import evaluate
from pokerbot.strategy import preflop_strength as ps

CLASSES = all_hand_classes()
COMBOS = {hc: len(expand_class(hc)) for hc in CLASSES}
TOTAL_COMBOS = sum(COMBOS.values())
OUT = config.KNOWLEDGE_DIR / "cfr" / "preflop_pushfold.json"


def _regret_match(regret: dict[str, list[float]], key: str, n: int) -> list[float]:
    r = regret.setdefault(key, [0.0] * n)
    pos = [x if x > 0 else 0.0 for x in r]
    s = sum(pos)
    if s <= 0:
        return [1.0 / n] * n
    return [x / s for x in pos]


def solve_stack(stack_bb: float, iters: int, rng: random.Random) -> dict:
    """Chance-sampled CFR for one stack depth. Returns {class: {jam, call}}."""
    sb_regret: dict[str, list[float]] = {}   # actions [JAM, FOLD]
    bb_regret: dict[str, list[float]] = {}   # actions [CALL, FOLD]
    sb_strat: dict[str, list[float]] = {}
    bb_strat: dict[str, list[float]] = {}
    deck = make_deck()
    S = stack_bb

    for _ in range(iters):
        cards = rng.sample(deck, 9)
        sb_hole, bb_hole, board = cards[:2], cards[2:4], cards[4:9]
        sb_c = hand_class(*sb_hole)
        bb_c = hand_class(*bb_hole)
        sb_score = evaluate(board, sb_hole)
        bb_score = evaluate(board, bb_hole)
        w = 1.0 if sb_score < bb_score else (0.5 if sb_score == bb_score else 0.0)
        call_util_sb = (2 * w - 1) * S          # SB utility if jam+called

        sigma_sb = _regret_match(sb_regret, sb_c, 2)
        sigma_bb = _regret_match(bb_regret, bb_c, 2)

        # SB node (root, reach 1)
        v_jam = sigma_bb[1] * 1.0 + sigma_bb[0] * call_util_sb   # bb[0]=CALL, bb[1]=FOLD
        v_fold = -0.5
        node_sb = sigma_sb[0] * v_jam + sigma_sb[1] * v_fold
        sr = sb_regret[sb_c]
        sr[0] += v_jam - node_sb
        sr[1] += v_fold - node_sb
        ss = sb_strat.setdefault(sb_c, [0.0, 0.0])
        ss[0] += sigma_sb[0]
        ss[1] += sigma_sb[1]

        # BB node (reached with counterfactual reach = sigma_sb[JAM])
        reach = sigma_sb[0]
        bb_call_u = (1 - 2 * w) * S
        bb_fold_u = -1.0
        node_bb = sigma_bb[0] * bb_call_u + sigma_bb[1] * bb_fold_u
        br = bb_regret[bb_c]
        br[0] += reach * (bb_call_u - node_bb)
        br[1] += reach * (bb_fold_u - node_bb)
        bs = bb_strat.setdefault(bb_c, [0.0, 0.0])
        bs[0] += reach * sigma_bb[0]
        bs[1] += reach * sigma_bb[1]

    out = {}
    for c in CLASSES:
        js = sb_strat.get(c, [0.0, 0.0])
        bs = bb_strat.get(c, [0.0, 0.0])
        jam = js[0] / sum(js) if sum(js) > 0 else 0.0
        call = bs[0] / sum(bs) if sum(bs) > 0 else 0.0
        out[c] = {"jam": round(jam, 3), "call": round(call, 3)}
    return out


def _weighted_pct(table: dict, key: str) -> float:
    return sum(COMBOS[c] * table[c][key] for c in CLASSES) / TOTAL_COMBOS


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--iters", type=int, default=120000)
    ap.add_argument("--quick", action="store_true", help="few stacks, few iters (sanity)")
    args = ap.parse_args()
    rng = random.Random(0)

    stacks = [4, 8, 12] if args.quick else list(range(2, 21))
    iters = 8000 if args.quick else args.iters

    ps._ensure()  # warm strength table (for the printout)
    blueprint = {}
    for S in stacks:
        table = solve_stack(float(S), iters, rng)
        blueprint[str(S)] = table
        print(f"  {S:2d}bb: SB jam {100*_weighted_pct(table,'jam'):4.1f}%  |  "
              f"BB call {100*_weighted_pct(table,'call'):4.1f}%")

    if not args.quick:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(blueprint, indent=1), encoding="utf-8")
        print(f"\nsaved -> {OUT}")
        # spot-check a few hands at 10bb
        t10 = blueprint.get("10", {})
        if t10:
            print("10bb examples:", {h: t10[h] for h in ("AA", "A5s", "KQo", "22", "T8s", "72o")})


if __name__ == "__main__":
    main()
