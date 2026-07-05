"""HU POSTFLOP spots for the Claude-teacher distillation (plan #3, Step 1) — $0, no API.

Drives an HU engine `Table` (200bb, to match GTOW) through each preflop POT-TYPE line (limp / SRP / 3bet / 4bet) to a
SETTLED flop, then WALKS the postflop with a simple realistic sampler (check / call / ~2/3-pot bet / occasional fold),
capturing every decision node as a `Spot`. The output feeds `pipeline/distill_run.py` -> `frontier_loop.run` (Claude
proposes the GTO action; the deterministic EV-truth filter gates it). Covering the 3bet/4bet pots is the point — that is
where the GLM's −43.30 postflop leak lives, and the current solver gold (SRP-only) never taught it.

Run: python -m dataset.build.from_hu_postflop [n_per_line=400]   # prints a $0 sanity sample (counts + a few spots)
"""
from __future__ import annotations

import random
import sys
from collections import Counter

from pokerbot.brain.format_spot import format_spot, spot_from_table
from pokerbot.engine.table import Table

_STACK_200BB = 20000                     # 200bb at bb=100 — the GTOW HU stack depth (Table default is 100bb)
_BET_FRAC = 0.66                         # ~2/3-pot probe size when the sampler bets/raises
_MAX_NODES = 6                           # cap decision nodes captured per hand (flop->river, both players)

# preflop verb sequences (HU: the SB/button acts first preflop) that SETTLE the betting -> the Table deals the flop.
_POT_LINES = {
    "limp": [("call", None), ("check", None)],                                    # SB limp, BB check
    "srp":  [("raise", 2.5), ("call", None)],                                     # SB open 2.5, BB call
    "3bet": [("raise", 2.5), ("raise", 10.0), ("call", None)],                    # SB open, BB 3bet, SB call
    "4bet": [("raise", 2.5), ("raise", 10.0), ("raise", 24.0), ("call", None)],   # SB open, BB 3bet, SB 4bet, BB call
}


def _act_preflop_line(t: Table, line) -> bool:
    """Act the settling preflop line; True iff it reached a postflop street with someone still to act."""
    for verb, size_bb in line:
        if t.to_act is None or t.street != "preflop" or t.hand_over:
            return False
        amt = int(size_bb * t.bb) if size_bb else None
        try:
            t.act(verb, amt)
        except (ValueError, RuntimeError):
            return False
    return t.street != "preflop" and t.to_act is not None and not t.hand_over


def _sample_action(la: dict, rd: random.Random):
    """A realistic (action, amount) from the legal-action dict — favors check/call/(2/3-pot) bet, rare fold, so hands
    stay alive AND both betting and facing-bet spots appear. Returns None if nothing is legal."""
    opts, weights = [], []
    if la.get("can_check"):
        opts.append(("check", None)); weights.append(0.45)
    if la.get("can_call"):
        opts.append(("call", None)); weights.append(0.35)
    if la.get("can_raise"):
        pot = la.get("pot", 0)
        # a clean ~2/3-pot BET (committed≈0 on a fresh street); a pot-ish RAISE when already facing a bet
        raw = int(_BET_FRAC * pot) if la.get("is_bet") else la["raise_min"] + int(_BET_FRAC * pot)
        target = min(la["raise_max"], max(la["raise_min"], raw))
        opts.append(("raise", target)); weights.append(0.30)
    if la.get("can_fold"):
        opts.append(("fold", None)); weights.append(0.08)
    return rd.choices(opts, weights=weights, k=1)[0] if opts else None


def _walk_postflop(t: Table, rd: random.Random):
    """Yield a `Spot` at each postflop decision node, then advance the hand with the sampler."""
    n = 0
    while t.to_act is not None and t.street != "preflop" and not t.hand_over and n < _MAX_NODES:
        yield spot_from_table(t, t.to_act)
        n += 1
        pick = _sample_action(t.legal_actions(), rd)
        if pick is None:
            break
        try:
            t.act(pick[0], pick[1])
        except (ValueError, RuntimeError):
            break


def build(n_per_line: int = 400, seed: int = 0):
    """Yield diverse HU 200bb postflop `Spot`s across the four pot types."""
    rd = random.Random(seed + 13)
    for pi, (pot_type, line) in enumerate(_POT_LINES.items()):
        for k in range(n_per_line):
            t = Table(["a", "b"], starting_stack=_STACK_200BB, seed=(seed + 1) * 1_000_000 + pi * 100_000 + k,
                      human_seat=-1)
            t.start_hand()
            if not _act_preflop_line(t, line):
                continue
            for spot in _walk_postflop(t, rd):
                if spot.street != "preflop" and spot.n_active == 2:
                    yield spot


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    spots = list(build(n_per_line=n))
    print(f"generated {len(spots)} HU postflop spots (n_per_line={n})")
    print("by street:", dict(Counter(s.street for s in spots)))
    print("by to_call>0 (facing a bet):", dict(Counter(s.to_call > 0 for s in spots)))
    print("n_active!=2 (should be 0):", sum(1 for s in spots if s.n_active != 2))
    print("\n--- sample format_spot (first postflop, first facing-a-bet) ---")
    for label, pred in (("first", lambda s: True), ("facing-bet", lambda s: s.to_call > 0)):
        s = next((x for x in spots if pred(x)), None)
        if s:
            print(f"[{label}] street={s.street} pos={s.hero_pos} board={s.board} hole={s.hero_hole} "
                  f"pot={s.pot} to_call={s.to_call}")


if __name__ == "__main__":
    main()
