"""Duplicate (mirror) poker = the VERIFY GATE. Each fixed deck is played twice with the two strategies in
SWAPPED seats, so identical cards cancel out and only the SKILL difference remains. This collapses variance
~10-50x vs naive matching → a bot change's true effect becomes measurable at SMALL samples WITHOUT AIVAT.

This is the linchpin the session kept needing: raw bb/100 over 40-300 hands is noise (the thin_value & draw
fixes were 'refuted' partly by noise). With duplicate poker we can RELIABLY accept/reject a change.

Strategies are factories: make_strat(seat) -> decide(state) -> (action, amount).
Run:  python -m pokerbot.benchmark.duplicate            # self-test (variance collapse) + a real edge
"""
from __future__ import annotations

import argparse
import random

from pokerbot.engine.cards import make_deck
from pokerbot.engine.game import HeadsUpGame
from pokerbot.strategy.gto_baseline import GTOBaseline


def gen_decks(n: int, seed: int = 0):
    """n fixed deals: (hole0, hole1, board[5]) drawn without replacement from a fresh shuffle each."""
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        d = make_deck()
        rng.shuffle(d)
        out.append((d[0:2], d[2:4], d[4:9]))
    return out


def _setup_fixed(g: HeadsUpGame, h0, h1, board5, button, start):
    g.players[0].stack = g.players[1].stack = start
    if button == 0:                      # force the button via hand_no so blinds post correctly
        g.hand_no = 0
    else:
        g.hand_no, g.button = 1, 0
    g.start_hand()
    g.players[0].hole, g.players[1].hole = list(h0), list(h1)
    g.deck.cards = list(reversed(board5))   # deal() pops from the end -> board comes out in order


def _play_hand(g: HeadsUpGame, d0, d1, start) -> int:
    guard = 0
    while not g.hand_over:
        st = g.state()
        a, amt = (d0 if st["to_act"] == 0 else d1)(st)
        g.act(a, amt)
        guard += 1
        if guard > 500:
            break
    return g.players[0].stack - start       # seat-0 strategy's net (zero-sum: seat1 = -this)


def duplicate_ab(make_a, make_b, decks, start=20000, sb=50, bb=100, return_edges=False):
    """A's card-luck-cancelled edge over B (bb/100) + stderr. Each deck: A=seat0 vs B, then B=seat0 vs A.
    return_edges=True also returns the per-deck chip edges (for PAIRED deltas across configs on the same decks)."""
    g = HeadsUpGame(names=("S0", "S1"), starting_stack=start, sb=sb, bb=bb, seed=0)
    edges = []
    for h0, h1, board in decks:
        _setup_fixed(g, h0, h1, board, 0, start)
        x1 = _play_hand(g, make_a(0), make_b(1), start)      # A at seat0
        _setup_fixed(g, h0, h1, board, 0, start)
        x2 = _play_hand(g, make_b(0), make_a(1), start)      # B at seat0  (A's chips = -x2)
        edges.append(x1 - x2)                                # A's chips over the 2 mirrored hands
    n = len(edges)
    mean = sum(edges) / n
    var = sum((e - mean) ** 2 for e in edges) / max(1, n - 1)
    bb100 = mean / 2 / bb * 100                              # 2 hands per deck
    se = (var ** 0.5 / n ** 0.5) / 2 / bb * 100
    if return_edges:
        return bb100, se, edges
    return bb100, se


def naive_ab(make_a, make_b, hands, start=20000, sb=50, bb=100, seed=0):
    """Baseline (no variance reduction): A=seat0 vs B over independent random decks. For the contrast demo."""
    g = HeadsUpGame(names=("A", "B"), starting_stack=start, sb=sb, bb=bb, seed=seed)
    decks = gen_decks(hands, seed=seed + 999)
    nets = []
    for h0, h1, board in decks:
        _setup_fixed(g, h0, h1, board, 0, start)
        nets.append(_play_hand(g, make_a(0), make_b(1), start))
    n = len(nets)
    mean = sum(nets) / n
    var = sum((x - mean) ** 2 for x in nets) / max(1, n - 1)
    return mean / bb * 100, (var ** 0.5 / n ** 0.5) / bb * 100


# ---- strategy factories ----
def gto(seed=1, **params):
    def make(seat):
        b = GTOBaseline(seat, seed=seed, iters=120, params=params or None)
        def d(st):
            b.hero = seat
            return b.decide(st)
        return d
    return make


def pokerbot(exploit=False, seed=1, value_raise_eq=0.72, **flags):
    import pokerbot.strategy.bot as botmod
    botmod.EQUITY_ITERS = 120
    from pokerbot.strategy.bot import PokerBot

    def make(seat):
        pb = PokerBot(seat, seed=seed, exploit=exploit)
        pb.value_raise_eq = value_raise_eq
        for k, v in flags.items():          # floor-ablation toggles (use_turn_advisor/use_river_blocker/...)
            setattr(pb, k, v)
        def d(st):
            pb.hero_idx = seat
            r = pb.decide(st)
            return r["action"], r["amount"]
        return d
    return make


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--decks", type=int, default=400)
    args = ap.parse_args()
    decks = gen_decks(args.decks, seed=7)

    print(f"=== VARIANCE-COLLAPSE SELF-TEST ({args.decks} decks) ===")
    print("Null test (GTOBaseline vs identical GTOBaseline; true edge = 0):")
    dbb, dse = duplicate_ab(gto(1), gto(1), decks)
    nbb, nse = naive_ab(gto(1), gto(1), args.decks)
    print(f"  duplicate: {dbb:+.1f} ± {dse:.1f} bb/100   (stderr should be ~0)")
    print(f"  naive    : {nbb:+.1f} ± {nse:.1f} bb/100   (stderr large)")
    print(f"  -> duplicate cuts stderr {nse/max(0.1,dse):.0f}x\n")

    print("Real edge (PokerBot floor vs GTOBaseline), card-luck-cancelled:")
    ebb, ese = duplicate_ab(pokerbot(False), gto(1), decks)
    print(f"  PokerBot vs GTOBaseline: {ebb:+.1f} ± {ese:.1f} bb/100")


if __name__ == "__main__":
    main()
