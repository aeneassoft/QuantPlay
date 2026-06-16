"""Head-to-head bb/100: the MVP (PokerBot exploit-primary) vs a TexasSolver-driven GTO opponent -- the LOCAL
GTO Wizard substitute (GTO Wizard's key is 401-blocked). The oracle plays a GTO-grounded PREFLOP (PokerBot,
exploit off) then, on each postflop decision, SOLVES the current board (single-raised-pot ranges) and samples
the solver's GTO action; it falls back to the PokerBot floor if the spot can't be solved / the hand isn't in
range. Both players are dealt from the SRP ranges so the solve's ranges are consistent.

HONEST caveats: (1) per-decision LIVE solves -> slow -> small samples; (2) ranges are the full SRP range at every
street (no exact continuation-range propagation) -> the opponent is APPROXIMATE near-GTO, not pure GTO; (3) a
static solve has a fixed bet-size abstraction, so our off-tree edge is (as vs GTO Wizard) invisible here -> this
measures LEAST-LOSS vs GTO, the same thing the GTO Wizard benchmark measures. Pair with floor_map's GTO-gap.

Run:  python -m pokerbot.benchmark.gto_oracle_match --hands 40 [--iters 80] [--acc 0.5]
"""
from __future__ import annotations

import argparse
import random
import statistics

import pokerbot.strategy.bot as botmod
from pokerbot.benchmark.gto_benchmark import _IP, _OOP
from pokerbot.benchmark.lbr import _legalize
from pokerbot.engine.game import HeadsUpGame
from pokerbot.strategy import gto_oracle as O
from pokerbot.strategy import ranges as R
from pokerbot.strategy.bot import PokerBot

_ACC = 0.5
_ITERS = 40
# Lean bet tree (1 bet size + allin per street, NO raise) -> a small tree -> fast per-spot solves. The oracle is
# a near-GTO opponent on this abstraction; our bot's off-tree raises just drop the oracle to its floor there.
_LEAN = [f"set_bet_sizes {p},{s},{b}" for p in ("oop", "ip") for s in ("flop", "turn", "river")
         for b in ("bet,66", "allin")]


def _expand(range_str, dead):
    classes = {c.split(":")[0] for c in range_str.split(",") if c.strip()}
    return R.combos_for_classes(classes, list(dead))


def _sample_hand(range_str, dead, rng):
    combos = _expand(range_str, dead)
    return list(rng.choice(combos)) if combos else None


def _match_label(action, amount, committed, node):
    """Map an engine action to the solver child label at `node` (nearest BET/RAISE size by bet-to chips)."""
    acts = (node.get("strategy", {}) or {}).get("actions", []) or list((node.get("childrens") or {}).keys())
    kind = {"check": "CHECK", "call": "CALL", "fold": "FOLD"}.get(action)
    if kind:
        return next((a for a in acts if a.split()[0] == kind), None)
    want = "RAISE" if action == "raise" else ("ALLIN" if action == "allin" else "BET")
    cands = [(a, float(a.split()[1])) for a in acts if a.split()[0] == want and len(a.split()) > 1]
    if not cands and want != "BET":
        cands = [(a, float(a.split()[1])) for a in acts if a.split()[0] == "BET" and len(a.split()) > 1]
    allin = next((a for a in acts if a.split()[0] == "ALLIN"), None)
    if not cands:
        return allin
    return min(cands, key=lambda c: abs(c[1] - (amount or 0)))[0]


def _street_actions(st):
    cur, acts, seen = st["street"], [], False
    for h in st.get("history", []):
        if h.get("action") == "deal" and h.get("street") == cur:
            seen = True
            continue
        if seen and h.get("street") == cur and h.get("action") in ("check", "call", "bet", "raise", "allin", "fold"):
            acts.append(h)
    return acts


class GTOOracleAgent:
    """PokerBot GTO preflop + TexasSolver postflop (sampled). hero_idx set by the match loop each turn."""

    def __init__(self, seat, seed=0, acc=_ACC, iters=_ITERS):
        self.hero_idx = seat
        self.floor = PokerBot(seat, seed=seed, exploit=False)
        self.rng = random.Random(seed + 99)
        self.acc, self.iters = acc, iters
        self._cache = {}
        self.solved = self.fell_back = 0

    def _floor(self, st):
        self.floor.hero_idx = self.hero_idx
        r = self.floor.decide(st)
        return r["action"], r["amount"]

    def _solve_board(self, board, role_oop_seat, pot, stack):
        key = "".join(board)
        if key not in self._cache:
            try:
                self._cache[key] = O.solve(board, _OOP, _IP, pot=max(2.0, pot), eff_stack=max(2.0, stack),
                                            accuracy=self.acc, max_iter=self.iters, dump_rounds=1,
                                            threads=8, tag=f"m{key}", bets=_LEAN, timeout=45)
            except Exception:  # noqa: BLE001
                self._cache[key] = None
        return self._cache[key]

    def decide(self, st):
        if st["street"] == "preflop":
            return self._floor(st)
        seat = self.hero_idx
        me = st["players"][seat]
        board = st["board"]
        pot = st["legal"].get("pot") or st["pot"]
        stack = me["stack"]
        root = self._solve_board(board, 1 - st["button"], pot, stack)   # OOP = non-button
        if not root:
            self.fell_back += 1
            return self._floor(st)
        node = root                                  # root = OOP first-to-act on this street
        for h in _street_actions(st):
            lbl = _match_label(h.get("action"), h.get("to") or h.get("amount"), 0, node)
            ch = (node.get("childrens") or {}).get(lbl) if lbl else None
            if not ch or ch.get("node_type") == "chance_node":
                node = None
                break
            node = ch
        hole = me["hole"]
        strat = O.strategy_for(node, hole[0], hole[1]) if node else None
        if not strat:
            self.fell_back += 1
            return self._floor(st)
        labels, probs = list(strat.keys()), list(strat.values())
        lbl = self.rng.choices(labels, weights=[max(0.0, p) for p in probs])[0] if sum(probs) > 0 else labels[0]
        self.solved += 1
        kind = lbl.split()[0]
        if kind == "CHECK":
            return "check", None
        if kind == "CALL":
            return "call", None
        if kind == "FOLD":
            return "fold", None
        to = int(float(lbl.split()[1])) if len(lbl.split()) > 1 else st["legal"]["raise_max"]
        return ("bet" if st["legal"]["is_bet"] else "raise"), to


class _Hero:
    """The MVP as a seat-flexible agent (PokerBotHero hardcodes seat 0, which breaks paired play)."""

    def __init__(self, seed=7):
        self.pb = PokerBot(0, seed=seed, exploit=True)
        self.hero_idx = 0

    def decide(self, st):
        self.pb.hero_idx = self.hero_idx
        r = self.pb.decide(st)
        return r["action"], r["amount"]

    def observe_hand_end(self):
        self.pb.observe_hand_end()


def _play_one(hero, oracle, hero_seat, h_btn, h_bb, board, start, sb, bb):
    """One forced single-raised pot (seat0=BTN opens 2.5bb, BB calls), Hero at hero_seat. Returns Hero's net."""
    g = HeadsUpGame(names=("S0", "S1"), starting_stack=start, sb=sb, bb=bb, seed=0)
    g.players[0].stack = g.players[1].stack = start
    g.hand_no = 0                                     # seat0 = button/SB
    g.start_hand()
    g.players[0].hole, g.players[1].hole = list(h_btn), list(h_bb)
    g.deck.cards = list(reversed(board))
    guard = 0
    while not g.hand_over and guard < 400:
        guard += 1
        stt = g.state()
        la = stt["legal"]
        actor = la.get("to_act")
        if actor is None:
            break
        if stt["street"] == "preflop":                # force a single-raised pot: SB/btn opens 2.5bb, BB calls
            committed = stt["players"][actor]["committed_street"]
            if la["can_raise"] and committed < bb:
                a, amt = ("bet" if la["is_bet"] else "raise"), round(2.5 * bb)
            elif la["to_call"] > 0 and la["can_call"]:
                a, amt = "call", None
            else:
                a, amt = ("check", None) if la["can_check"] else ("call", None)
        else:
            ag = hero if actor == hero_seat else oracle
            ag.hero_idx = actor
            a, amt = ag.decide(stt)
        a, amt = _legalize(la, a, amt)
        g.act(a, amt)
    if hasattr(hero, "observe_hand_end"):
        hero.observe_hand_end()
    return g.players[hero_seat].stack - start


def run_paired(hero, oracle, decks, start=4000, sb=50, bb=100):
    """PAIRED/duplicate: each deck played twice with Hero in BOTH seats -> card luck cancels -> low-variance edge
    (the gate we trust). The oracle's per-board solves are cached, so pairing costs ~no extra solves."""
    edges = []
    for h_btn, h_bb, board, _rng in decks:
        n0 = _play_one(hero, oracle, 0, h_btn, h_bb, board, start, sb, bb)   # Hero = BTN (IP)
        n1 = _play_one(hero, oracle, 1, h_btn, h_bb, board, start, sb, bb)   # Hero = BB  (OOP)
        edges.append(n0 + n1)                                                # Hero's net over the 2 mirrored hands
    return edges


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hands", type=int, default=40)
    ap.add_argument("--iters", type=int, default=_ITERS)
    ap.add_argument("--acc", type=float, default=_ACC)
    args = ap.parse_args()
    botmod.EQUITY_ITERS = 120
    print(f"HEAD-TO-HEAD: MVP vs TexasSolver-driven GTO opponent ({args.hands} hands, solver acc={args.acc} "
          f"iters={args.iters}). Per-decision live solves -> slow; approximate near-GTO (full SRP ranges).\n", flush=True)

    rng = random.Random(7)
    decks = []
    for i in range(args.hands):
        dr = random.Random(1000 + i)
        # deal a full 5-card board + both hands from the SRP ranges (button=IP range, BB=OOP range)
        deck = [r + s for r in "23456789TJQKA" for s in "shdc"]
        dr.shuffle(deck)
        board = deck[:5]
        hb = _sample_hand(_IP, board, dr) or deck[5:7]
        ho = _sample_hand(_OOP, board + hb, dr) or deck[7:9]
        decks.append((hb, ho, board, dr))

    hero = _Hero(seed=7)
    oracle = GTOOracleAgent(1, seed=3, acc=args.acc, iters=args.iters)
    edges = run_paired(hero, oracle, decks)           # PAIRED: card luck cancels -> low-variance edge
    n = len(edges)
    emean = sum(edges) / n
    var = sum((e - emean) ** 2 for e in edges) / max(1, n - 1)
    bb100 = emean / 2                                 # 2 hands/deck; chips == bb/100 (bb=100)
    se = (var ** 0.5 / n ** 0.5) / 2
    print(f"\nMVP vs TexasSolver-oracle (PAIRED, {n} decks = {2 * n} hands): {bb100:+.1f} +/- {se:.1f} bb/100")
    print(f"oracle: solved {oracle.solved} decisions, fell back to floor {oracle.fell_back}")
    print("Caveat: paired kills CARD variance; the oracle is still APPROXIMATE GTO (full SRP ranges on turn/river "
          "+ lean tree + 40bb), so a positive number = exploiting those approximations, not beating true GTO. The "
          "deterministic GTO-gap (frequency-faithful) is the exact 'closeness to the solver' measure.")


if __name__ == "__main__":
    main()
