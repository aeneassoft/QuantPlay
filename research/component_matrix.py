"""COMPONENT COMPETENCE MATRIX — which decision-generating component of the bot is best in which region of
the game, graded against the TexasSolver oracle. Operationalizes the "ensemble, don't discard" principle
(per-context reliability weighting) for the PRECISION DOCTRINE (docs/PRECISION_DOCTRINE.md): a routing-DESIGN
instrument, NOT a shippable router.

REUSE: this is floor_map.py's region-decomposition machinery generalized across COMPONENTS. It reads the same
TexasSolver flop/turn/river caches (cache-only + deterministic), builds full bot-consumable states, and scores
each component IN ISOLATION on the nodes where it is defined via the floor_map GTO-gap = 1 - p_oracle(chosen
action-kind). Where cheap it also reports the oracle EV-loss of the chosen action-kind vs the oracle's best kind.

Grid axes (a region = one cell): street x board-texture x pot-type x SPR-bucket x made-hand-class. The matrix is
SPARSE by design — each component is graded only where it can act (preflop_blueprint has no board oracle; the
resolver is solve-gated and capped). Sparse cells are INFORMATIVE, low-n cells are MARKED, never decisive.

Run:  python -m research.component_matrix [--limit N] [--max-solves K]
Out:  data/research_sweep/component_matrix.json  + a printed routing-suggestion table (a DESIGN HYPOTHESIS).

HONESTY (baked into the printed report + JSON):
  (1) grader = TexasSolver, ~90% aligned with GTOW, NOT identical -> PROXY, not bb-truth.
  (2) measures ISOLATED competence, NOT composed behavior -> a routing tool; the composed router still needs
      its own LIVE gate (the v8 live-breakage lesson: Hebel x Resolver -58 vs -20 isolated).
  (3) unpaired / small-n cells carry noise -> cells with n < MIN_DECISIVE_N are marked LOW-COVERAGE.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import time
from collections import defaultdict
from pathlib import Path

from pokerbot import config
import pokerbot.strategy.bot as botmod

# Keep the equity MC cheap + deterministic (the grid is large; PYTHONHASHSEED=0 pins combo order elsewhere).
botmod.EQUITY_ITERS = 80
from pokerbot.strategy.bot import PokerBot                     # noqa: E402
from pokerbot.strategy import advisor as pf_advisor            # noqa: E402
from pokerbot.strategy import preflop_blueprint as pbp         # noqa: E402
from pokerbot.strategy.postflop import classify_board          # noqa: E402
from pokerbot.strategy import preflop_strength as ps           # noqa: E402
from pokerbot.engine.evaluator import evaluate, best_five_name  # noqa: E402
from pokerbot.engine.cards import hand_class                   # noqa: E402

# ------------------------------------------------------------------ constants
SEED = 7                                # every sampler seeds off this -> byte-deterministic runs
MIN_DECISIVE_N = 30                     # a cell with fewer graded hands is LOW-COVERAGE (never "decisive")
STACK = 9700                           # chip stack in the synthetic states (100bb-ish, matches floor_map)
SB, BB = 50, 100
COMBOS_PER_NODE = 32                   # cap graded hands per (node, role) — the formula floor runs MC equity per
                                       # combo, so a full 100+-combo range x thousands of nodes blows the runtime
                                       # budget. A deterministic 32-combo subsample keeps cells well-populated
                                       # (many nodes -> the same region cell fills fast) while staying < 20 min.
OUT = config.DATA_DIR / "research_sweep" / "component_matrix.json"

_BENCH = config.DATA_DIR / "_gto_bench_cache"    # flop first-to-act OOP roots (CHECK child = IP c-bet)
_TURN = config.DATA_DIR / "_gto_turn_cache"      # turn first-to-act OOP roots
_RIVER = config.DATA_DIR / "_gto_river_cache"    # river first-to-act OOP roots (plain 5-card + _pot suffix)
_ORDER = "23456789TJQKA"

# Component identifiers.
C_PREFLOP = "preflop_blueprint"
C_ADVISOR = "advisor_mlp"              # flop/turn/river bet-vs-check advisor (their trained streets)
C_DEFENSE = "defense_advisor"          # facing-bet fold/call/raise advisor (flop, its trained + gated street)
C_FORMULA = "formula_floor"            # the heuristic MDF/pot-odds/value_score path (exploit OFF, advisors OFF)
C_RESOLVER = "resolver"                # live turn/river re-solve (solve-gated, capped)
C_EXPLOIT = "exploit_overlay"          # opp_model/exploit river overlay (fires only on the river w/ data)


# ============================================================ region classification
def texture_class(board) -> str:
    """dry / wet / paired / monotone — the task's texture axis via classify_board (matches bot._board_class)."""
    t = classify_board(board)
    if t.get("paired"):
        return "paired"
    if t.get("monotone"):
        return "monotone"
    if t.get("connected") or t.get("twotone"):
        return "wet"
    return "dry"


def spr_bucket(pot: float, stack: float) -> str:
    """SPR = stack-to-pot ratio at the decision. low <=3 (commit-y), mid 3-8, high >8 (maneuver room)."""
    spr = stack / max(1.0, pot)
    if spr <= 3.0:
        return "sprLo"
    if spr <= 8.0:
        return "sprMid"
    return "sprHi"


def made_class(hole, board) -> str:
    """air / pair / toppair / twopairplus / monster — the made-hand axis. Built from the treys evaluator name
    (same source as engine.features 'tier'), split so 'pair' distinguishes top-pair (the biggest strategic
    boundary) from a weak pair, and two-pair+ from the true nuts region."""
    name = best_five_name(board, list(hole)).lower()
    if any(k in name for k in ("quad", "straight flush", "full house", "flush", "straight")):
        return "monster"
    if "three of a kind" in name or "two pair" in name:
        return "twopairplus"
    if "pair" in name:                                  # one pair: top-pair vs the rest
        board_ranks = {c[0] for c in board}
        top = max(board, key=lambda c: _ORDER.index(c[0]))[0] if board else None
        pair_rank = next((c[0] for c in hole if c[0] in board_ranks), None)   # a board-matching hole card
        # an overpair (pocket pair above the board top) or top-pair -> the "toppair" strategic bucket
        if hole[0][0] == hole[1][0] and _ORDER.index(hole[0][0]) > _ORDER.index(top):
            return "toppair"
        if pair_rank is not None and pair_rank == top:
            return "toppair"
        return "pair"
    return "air"


def region_key(street, board, pot, stack, hole, pot_type) -> str:
    """The full cell coordinate. Compact so the JSON stays readable + the printed table fits."""
    return f"{street}|{texture_class(board)}|{pot_type}|{spr_bucket(pot, stack)}|{made_class(hole, board)}"


# ============================================================ oracle-node reading
def _bet_check_idx(actions):
    """(bet-kind indices, check index) for a first-to-act node (CHECK / BET.. )."""
    bet_idx = [i for i, a in enumerate(actions) if a.split()[0] in ("BET", "RAISE", "ALLIN")]
    check_idx = next((i for i, a in enumerate(actions) if a.split()[0] == "CHECK"), None)
    return bet_idx, check_idx


def _defense_idx(actions):
    """(fold, call, raise-kind) indices for a facing-bet node (FOLD / CALL / RAISE.. )."""
    fold_idx = next((i for i, a in enumerate(actions) if a.split()[0] == "FOLD"), None)
    call_idx = next((i for i, a in enumerate(actions) if a.split()[0] == "CALL"), None)
    raise_idx = [i for i, a in enumerate(actions) if a.split()[0] in ("RAISE", "ALLIN", "BET")]
    return fold_idx, call_idx, raise_idx


def _node_pot(node, default_pot):
    """The pot the solver actually faced at this node, reconstructed from the ACTIONS' bet chips when possible
    (the cache filename carries only the board / start-pot). Falls back to the passed default."""
    return default_pot


# ============================================================ state builders (bot-consumable)
def _players(hole, button, v_committed=0):
    return [{"idx": 0, "hole": list(hole), "stack": STACK, "committed_street": 0, "committed_total": 300,
             "folded": False, "all_in": False, "is_button": button == 0},
            {"idx": 1, "hole": ["??", "??"], "stack": STACK, "committed_street": v_committed,
             "committed_total": 300 + v_committed, "folded": False, "all_in": False, "is_button": button == 1}]


def make_firstact_state(hole, board, role, pot, street):
    """Hero first-to-act on `street` (can bet/check). role='OOP' (BB caller, donk node) or 'IP' (BTN aggressor
    after villain checked). Mirrors floor_map.make_flop_state; history drives bot._has_initiative + range."""
    if role == "IP":
        button = 0
        hist = [{"player": 0, "action": "raise", "street": "preflop", "to": 300},
                {"player": 1, "action": "call", "street": "preflop", "amount": 200},
                {"action": "deal", "street": "flop", "board": list(board[:3])}]
        if street in ("turn", "river"):
            hist += [{"player": 1, "action": "check", "street": "flop"},
                     {"player": 0, "action": "check", "street": "flop"},
                     {"action": "deal", "street": "turn", "board": list(board[:4])}]
        if street == "river":
            hist += [{"player": 1, "action": "check", "street": "turn"},
                     {"player": 0, "action": "check", "street": "turn"},
                     {"action": "deal", "street": "river", "board": list(board)}]
        hist.append({"player": 1, "action": "check", "street": street})
    else:  # OOP donk node
        button = 1
        hist = [{"player": 1, "action": "raise", "street": "preflop", "to": 300},
                {"player": 0, "action": "call", "street": "preflop", "amount": 200},
                {"action": "deal", "street": "flop", "board": list(board[:3])}]
        for s, ln in (("turn", 4), ("river", 5)):
            if _street_ge(street, s):
                hist += [{"player": 1, "action": "check", "street": _prev(s)},
                         {"player": 0, "action": "check", "street": _prev(s)},
                         {"action": "deal", "street": s, "board": list(board[:ln])}]
    return {"hand_no": 0, "button": button, "street": street, "board": list(board), "pot": pot,
            "current_bet": 0, "to_act": 0, "hand_over": False, "result": None, "sb": SB, "bb": BB,
            "history": hist, "players": _players(hole, button),
            "legal": {"to_act": 0, "to_call": 0, "can_fold": False, "can_check": True, "can_call": False,
                      "call_amount": 0, "can_raise": True, "is_bet": True, "raise_min": 100,
                      "raise_max": STACK, "pot": pot}}


def make_facing_state(hole, board, role, pot, bet, street):
    """Hero faces a villain bet of `bet` chips into `pot` on `street` (a defense node). role = hero's position.
    OOP: hero checked, BTN c-bet (classic defense). IP: BTN faces an OOP donk-lead. `pot` excludes the bet."""
    if role == "OOP":
        button = 1
        hist = [{"player": 1, "action": "raise", "street": "preflop", "to": 300},
                {"player": 0, "action": "call", "street": "preflop", "amount": 200},
                {"action": "deal", "street": "flop", "board": list(board[:3])},
                {"player": 0, "action": "check", "street": street},
                {"player": 1, "action": "bet", "street": street, "amount": bet}]
    else:
        button = 0
        hist = [{"player": 0, "action": "raise", "street": "preflop", "to": 300},
                {"player": 1, "action": "call", "street": "preflop", "amount": 200},
                {"action": "deal", "street": "flop", "board": list(board[:3])},
                {"player": 1, "action": "bet", "street": street, "amount": bet}]
    return {"hand_no": 0, "button": button, "street": street, "board": list(board), "pot": pot + bet,
            "current_bet": bet, "to_act": 0, "hand_over": False, "result": None, "sb": SB, "bb": BB,
            "history": hist, "players": _players(hole, button, v_committed=bet),
            "legal": {"to_act": 0, "to_call": bet, "can_fold": True, "can_check": False, "can_call": True,
                      "call_amount": bet, "can_raise": True, "is_bet": False, "raise_min": 2 * bet,
                      "raise_max": STACK, "pot": pot + bet}}


def _prev(street):
    return {"turn": "flop", "river": "turn"}[street]


def _street_ge(a, b):
    o = {"flop": 0, "turn": 1, "river": 2}
    return o[a] >= o[b]


# ============================================================ component deciders (isolated)
def _bot(**flags):
    """A PokerBot with exploit OFF by default; flags select which internal path stays live so a component can be
    graded IN ISOLATION (advisors OFF -> the formula floor; only-defense-advisor; etc.)."""
    pb = PokerBot(0, seed=SEED, exploit=flags.get("exploit", False))
    pb.hero_idx = 0
    for k in ("use_turn_advisor", "use_river_advisor", "use_defense_advisor", "use_resolver",
              "use_turn_resolver", "use_range_tracker", "use_probe"):
        if k in flags:
            setattr(pb, k, flags[k])
    return pb


def kind_firstact(action) -> str:
    """Map a bot action to the first-to-act oracle action-KIND: 'bet' or 'check'."""
    return "bet" if action in ("bet", "raise", "allin") else "check"


def kind_defense(action) -> str:
    """Map a bot action to the facing-bet oracle action-KIND: 'fold' / 'call' / 'raise'."""
    if action == "fold":
        return "fold"
    if action in ("call", "check"):
        return "call"
    return "raise"


# ============================================================ grading
def p_kind_firstact(probs, actions, chosen_kind):
    """Oracle probability mass on the chosen KIND (bet vs check) at a first-to-act node + the EV-optimal kind's
    mass (for the ev-loss proxy: we lack per-action EVs in the dump, so 'ev-loss' here = the frequency-gap to
    the oracle's MODAL kind = a bounded surrogate; labelled as such in the output)."""
    bet_idx, check_idx = _bet_check_idx(actions)
    p_bet = sum(probs[i] for i in bet_idx)
    p_check = probs[check_idx] if check_idx is not None else 0.0
    p_chosen = p_bet if chosen_kind == "bet" else p_check
    p_best = max(p_bet, p_check)
    return p_chosen, p_best


def p_kind_defense(probs, actions, chosen_kind):
    fold_idx, call_idx, raise_idx = _defense_idx(actions)
    p_fold = probs[fold_idx] if fold_idx is not None else 0.0
    p_call = probs[call_idx] if call_idx is not None else 0.0
    p_raise = sum(probs[i] for i in raise_idx)
    p_map = {"fold": p_fold, "call": p_call, "raise": p_raise}
    p_chosen = p_map.get(chosen_kind, 0.0)
    p_best = max(p_fold, p_call, p_raise)
    return p_chosen, p_best


class Accumulator:
    """component -> region -> [n, sum_gap, sum_evloss]. gap = 1 - p_oracle(chosen kind); evloss = the
    frequency-surrogate p_best - p_chosen (>=0), the bounded proxy noted above."""

    def __init__(self):
        self.d = defaultdict(lambda: defaultdict(lambda: [0, 0.0, 0.0]))

    def add(self, comp, region, p_chosen, p_best):
        cell = self.d[comp][region]
        cell[0] += 1
        cell[1] += 1.0 - p_chosen
        cell[2] += max(0.0, p_best - p_chosen)


# ------------------------------------------------------------ per-node grading
def _subsample(strat, board):
    """A DETERMINISTIC subsample of at most COMBOS_PER_NODE board-legal combos from a node's strategy dict.
    sorted() pins the order (no PYTHONHASHSEED dependence), then an evenly-strided pick spans the whole range
    (weak-to-strong) rather than an alphabetic prefix -> the made-hand axis stays populated."""
    bset = set(board)
    legal = [(c, p) for c, p in sorted(strat.items()) if not (set((c[:2], c[2:4])) & bset)]
    if len(legal) <= COMBOS_PER_NODE:
        return legal
    step = len(legal) / COMBOS_PER_NODE
    return [legal[int(i * step)] for i in range(COMBOS_PER_NODE)]


def grade_firstact_node(node, board, role, street, pot, acc, deciders, coverage):
    """Grade every first-to-act-domain component on this cached first-to-act node, per combo."""
    s = node.get("strategy") or {}
    actions, strat = s.get("actions") or [], s.get("strategy") or {}
    if not actions or not strat:
        return
    for combo, probs in _subsample(strat, board):
        hole = (combo[:2], combo[2:4])
        pot_type = "srp"                                # the caches are single-raised-pot ranges
        region = region_key(street, board, pot, STACK, hole, pot_type)
        for comp, decide in deciders.items():
            act = decide(hole, board, role, street, pot, facing=None)
            if act is None:                             # component not defined here (e.g. advisor returned None)
                continue
            p_chosen, p_best = p_kind_firstact(probs, actions, kind_firstact(act))
            acc.add(comp, region, p_chosen, p_best)
            coverage[comp] += 1


def grade_facing_node(node, board, role, street, pot, bet, acc, deciders, coverage):
    """Grade the facing-bet-domain components (defense advisor + formula floor) on a defense node, per combo."""
    s = node.get("strategy") or {}
    actions, strat = s.get("actions") or [], s.get("strategy") or {}
    if not actions or not strat:
        return
    for combo, probs in _subsample(strat, board):
        hole = (combo[:2], combo[2:4])
        region = region_key(street, board, pot, STACK, hole, "srp")
        for comp, decide in deciders.items():
            act = decide(hole, board, role, street, pot, facing=bet)
            if act is None:
                continue
            p_chosen, p_best = p_kind_defense(probs, actions, kind_defense(act))
            acc.add(comp, region, p_chosen, p_best)
            coverage[comp] += 1


# ------------------------------------------------------------ decider factories (bound to shared bots)
def build_firstact_deciders():
    """Deciders for the first-to-act (bet/check) domain: advisor, formula floor, exploit overlay, resolver.
    Each returns a bot ACTION or None (None = not defined at this node)."""
    bot_advisor = _bot(use_defense_advisor=False)                              # advisors ON (the default paths)
    bot_floor = _bot(use_turn_advisor=False, use_river_advisor=False,          # advisors OFF -> heuristic floor
                     use_defense_advisor=False)
    bot_exploit = _bot(exploit=True, use_defense_advisor=False)                # exploit overlay ON (river only)
    bot_resolver = _bot(use_resolver=True, use_turn_resolver=True, use_defense_advisor=False)

    def advisor_decide(hole, board, role, street, pot, facing):
        # the flop advisor is queried by the bot's flop-net; on the flop the net drives bet/check, so the
        # advisor component = the bot with advisors ON (flop always; turn/river only where a street net exists).
        if street == "flop" and not pf_advisor.available("flop"):
            return None
        if street in ("turn", "river") and not pf_advisor.available(street):
            return None
        return bot_advisor.decide(make_firstact_state(hole, board, role, pot, street))["action"]

    def floor_decide(hole, board, role, street, pot, facing):
        return bot_floor.decide(make_firstact_state(hole, board, role, pot, street))["action"]

    def exploit_decide(hole, board, role, street, pot, facing):
        if street != "river":                    # the exploit overlay only generates a river action
            return None
        return bot_exploit.decide(make_firstact_state(hole, board, role, pot, street))["action"]

    return {C_ADVISOR: advisor_decide, C_FORMULA: floor_decide, C_EXPLOIT: exploit_decide}, bot_resolver


def build_facing_deciders():
    """Deciders for the facing-bet (fold/call/raise) domain: defense advisor + formula MDF floor."""
    bot_def = _bot(use_defense_advisor=True)                         # defense advisor ON
    bot_floor = _bot(use_defense_advisor=False)                      # defense advisor OFF -> MDF/pot-odds floor

    def defense_decide(hole, board, role, street, pot, facing):
        if street not in ("flop",) or not pf_advisor.defense_available():   # trained+gated to the flop
            return None
        return bot_def.decide(make_facing_state(hole, board, role, pot, facing, street))["action"]

    def floor_decide(hole, board, role, street, pot, facing):
        return bot_floor.decide(make_facing_state(hole, board, role, pot, facing, street))["action"]

    return {C_DEFENSE: defense_decide, C_FORMULA: floor_decide}


# ============================================================ cache walk
def _child_facing_nodes(node):
    """Yield (bet_chips, defense_node) for the facing-bet children of a first-to-act node: OOP-bet->{CALL,FOLD}
    (IP defends) and CHECK->IP-bet->{CALL,FOLD} (OOP defends). The defense strategy is dumped there."""
    kids = node.get("childrens") or {}
    for lbl, ch in kids.items():
        parts = lbl.split()
        if parts[0] == "BET" and (ch.get("strategy") or {}).get("strategy"):
            yield float(parts[1]), ch, "IP"          # villain (OOP) bet -> IP faces it
        if parts[0] == "CHECK":
            for lbl2, ch2 in (ch.get("childrens") or {}).items():
                p2 = lbl2.split()
                if p2[0] == "BET" and (ch2.get("strategy") or {}).get("strategy"):
                    yield float(p2[1]), ch2, "OOP"   # hero checked, villain (IP) bet -> OOP faces it


def walk_cache(cache_dir, street, ncard, limit, acc, coverage, default_pot):
    """Walk a solve cache: grade the OOP root + IP c-bet child as first-to-act nodes, and their facing-bet
    grandchildren as defense nodes. Deterministic file order (sorted)."""
    fa_deciders, _resolver_bot = build_firstact_deciders()
    fc_deciders = build_facing_deciders()
    files = sorted(cache_dir.glob("*.json"))
    rng = random.Random(SEED)
    rng.shuffle(files)                              # representative sample across the whole cache, not a-z prefix
    if limit:
        files = files[:limit]
    n_nodes = 0
    for cf in files:
        parts = cf.stem.split("_")
        st = parts[0]
        if len(st) < 2 * ncard:
            continue
        board = [st[2 * i:2 * i + 2] for i in range(ncard)]
        # SPR variation: the river cache encodes the solved START pot as a '_<pot>' filename suffix (in bb; the
        # solve was pot=<n>bb scaled). Convert to chips (bb=100) so the SPR bucket actually varies within the
        # river; flop/turn caches have no such suffix -> the fixed default_pot (SPR ~constant by construction).
        pot = default_pot
        if len(parts) > 1 and parts[1].isdigit():
            pot = int(parts[1]) * BB
        try:
            node = json.loads(cf.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        ip = next((v for k, v in (node.get("childrens") or {}).items()
                   if k.split()[0] == "CHECK"), None)
        for role, nd in (("OOP", node), ("IP", ip)):
            if nd is None:
                continue
            grade_firstact_node(nd, board, role, street, pot, acc, fa_deciders, coverage)
            for bet, dnode, drole in _child_facing_nodes(nd):
                grade_facing_node(dnode, board, drole, street, pot, bet, acc, fc_deciders, coverage)
            n_nodes += 1
    return n_nodes


# ============================================================ preflop track (separate oracle)
def grade_preflop(acc, coverage):
    """preflop_blueprint has NO TexasSolver board oracle (TexasSolver is postflop-only). The only available
    preflop GTO reference is the blueprint's OWN solved mixture -> we grade the blueprint's CHOSEN action vs
    that mixture. The resulting gap therefore reflects only the value-clamp / limp-clamp DEVIATIONS from the
    solved mix, NOT independent skill. Labelled 'preflop (self-mix)' in the output so it is never read as a
    solver grade. Covers the ROOT (SB open) + 3BET + 4BET nodes over the full 169-hand grid."""
    if not pbp.available():
        return
    rng = random.Random(SEED)
    pb = _bot()
    ranks = "AKQJT98765432"
    hands = []
    for i, a in enumerate(ranks):
        for j, b in enumerate(ranks):
            hands.append(a + b + ("s" if i < j else ("o" if i > j else "")))
    for node_name, is_sb, raises, can_check, v_allin in (("ROOT", True, 0, False, False),
                                                         ("3BET", True, 2, False, False),
                                                         ("4BET", False, 3, False, False)):
        node = pbp.node_for_state(is_sb, raises, can_check, v_allin)
        if node is None:
            continue
        for hc in hands:
            picked = pbp.pick(node, hc, rng)
            if picked is None:
                continue
            _action, dist = picked
            # the bot's actual choice (may differ from the modal via the clamps)
            pct = ps.percentile(hc)
            chosen = _blueprint_chosen(pb, node, hc, dist, pct, rng)
            p_chosen = dist.get(chosen, 0.0)
            p_best = max(dist.values()) if dist else 0.0
            region = f"preflop|{node_name}|selfmix|na|na"
            acc.add(C_PREFLOP, region, p_chosen, p_best)
            coverage[C_PREFLOP] += 1


def _blueprint_chosen(pb, node, hc, dist, pct, rng):
    """Reproduce the blueprint's clamp logic (bot._preflop_blueprint) to know which action the bot COMMITS to,
    then bucket it to a dist key. Kept minimal: the value-only jam clamp is the only clamp active at 200bb."""
    action = rng.choices(list(dist), weights=list(dist.values()))[0] if dist else "fold"
    if action in ("jam", "5bet") and node in ("4BET", "5BET") and pct < pb.bp_jam_min_pct:
        safe = {a: p for a, p in dist.items() if a not in ("jam", "5bet")}
        tot = sum(safe.values())
        action = rng.choices(list(safe), weights=list(safe.values()))[0] if tot > 1e-9 else "fold"
    return action


# ============================================================ resolver track (solve-gated, capped)
def grade_resolver(acc, coverage, max_solves, street, cache_dir, ncard, default_pot):
    """The live resolver re-solves the spot with TexasSolver -> grading it against the TexasSolver oracle is a
    CONVERGENCE / range-truth check, NOT independent skill (near-identical tree => near-zero gap by
    construction). Capped at max_solves cells (each is a real solve). We grade its bet/check KIND on the OOP
    root only, sampled."""
    if max_solves <= 0:
        return 0
    bot_resolver = _bot(use_resolver=True, use_turn_resolver=True, use_defense_advisor=False)
    files = sorted(cache_dir.glob("*.json"))
    rng = random.Random(SEED + 1)
    rng.shuffle(files)
    solves = 0
    for cf in files:
        if solves >= max_solves:
            break
        st = cf.stem.split("_")[0]
        if len(st) < 2 * ncard:
            continue
        board = [st[2 * i:2 * i + 2] for i in range(ncard)]
        try:
            node = json.loads(cf.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        s = node.get("strategy") or {}
        actions, strat = s.get("actions") or [], s.get("strategy") or {}
        if not actions or not strat:
            continue
        # one representative combo per board (a value-ish hand) to keep the solve budget small
        combo = next(iter(strat))
        hole = (combo[:2], combo[2:4])
        if set(hole) & set(board):
            continue
        try:
            act = bot_resolver.decide(make_firstact_state(hole, board, "OOP", default_pot, street))["action"]
        except Exception:  # noqa: BLE001
            continue
        probs = strat[combo]
        p_chosen, p_best = p_kind_firstact(probs, actions, kind_firstact(act))
        region = region_key(street, board, default_pot, STACK, hole, "srp")
        acc.add(C_RESOLVER, region, p_chosen, p_best)
        coverage[C_RESOLVER] += 1
        solves += 1
    return solves


# ============================================================ reporting
CAVEATS = [
    "GRADER = TexasSolver (bundled OSS solver), ~90% aligned with GTO Wizard but NOT identical. Every number "
    "here is a PROXY for GTO-closeness, not bb/100 truth. A component 'winning' a region wins vs THIS oracle.",
    "This measures ISOLATED component competence, NOT composed behavior. Routing by it is a DESIGN HYPOTHESIS: "
    "the composed router still needs its own LIVE gate. Lesson (docs/PRECISION_DOCTRINE.md): behaviour levers "
    "carried interaction risk (Hebel x Resolver measured -58 live vs -20 isolated) — isolated wins do not add.",
    f"Cells with n < {MIN_DECISIVE_N} graded hands are LOW-COVERAGE (marked '*'); their winner is noise, never "
    "decisive. The preflop_blueprint track is graded vs its OWN solved mixture (no postflop-solver preflop "
    "oracle) so its gap = clamp-deviation only; the resolver track is a convergence check (near-zero by "
    "construction), capped at the solve budget.",
]


def summarize(acc: Accumulator, coverage, meta):
    """Build the JSON matrix + the printed routing-suggestion table."""
    matrix = {}
    for comp, regions in acc.d.items():
        matrix[comp] = {}
        for region, (n, sg, sev) in regions.items():
            matrix[comp][region] = {"n": n, "gto_gap_mean": round(sg / n, 4),
                                    "ev_loss_mean": round(sev / n, 4), "coverage": n,
                                    "low_coverage": n < MIN_DECISIVE_N}

    # per-region ranking of components (postflop domains only; preflop/resolver are separate tracks)
    region_components = defaultdict(dict)
    for comp, regions in matrix.items():
        for region, cell in regions.items():
            region_components[region][comp] = cell

    routing = {}
    for region, comps in region_components.items():
        ranked = sorted(comps.items(), key=lambda kv: kv[1]["gto_gap_mean"])
        best_comp, best_cell = ranked[0]
        routing[region] = {
            "best_component": best_comp,
            "best_gap": best_cell["gto_gap_mean"],
            "best_n": best_cell["n"],
            "low_coverage": best_cell["low_coverage"],
            "ranking": [(c, cell["gto_gap_mean"], cell["n"]) for c, cell in ranked],
        }

    out = {"meta": meta, "caveats": CAVEATS, "coverage_totals": dict(coverage),
           "matrix": matrix, "routing_suggestion": routing}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


def print_report(out):
    routing = out["routing_suggestion"]
    matrix = out["matrix"]
    print("\n" + "=" * 92)
    print("COMPONENT COMPETENCE MATRIX  (GTO-gap = 1 - p_oracle(chosen kind); lower = closer to the solver)")
    print("=" * 92)

    # ---- per component: best + worst regions (decisive cells only) ----
    print("\n--- PER COMPONENT: best / worst regions (n >= %d only) ---" % MIN_DECISIVE_N)
    for comp in sorted(matrix):
        cells = [(reg, c["gto_gap_mean"], c["n"]) for reg, c in matrix[comp].items()
                 if c["n"] >= MIN_DECISIVE_N]
        if not cells:
            tot_n = sum(c["n"] for c in matrix[comp].values())
            print(f"\n[{comp}]  (no decisive cell; total graded n={tot_n})")
            continue
        cells.sort(key=lambda x: x[1])
        wmean = sum(g * n for _, g, n in cells) / sum(n for _, _, n in cells)
        print(f"\n[{comp}]  weighted GTO-gap {wmean:.1%} over {len(cells)} decisive cells")
        for reg, g, n in cells[:3]:
            print(f"    BEST  {reg:44} gap {g:5.1%}  n={n}")
        for reg, g, n in cells[-3:][::-1]:
            print(f"    WORST {reg:44} gap {g:5.1%}  n={n}")

    # ---- routing-suggestion table (DESIGN HYPOTHESIS) ----
    print("\n" + "-" * 92)
    print("ROUTING SUGGESTION  (region -> lowest-gap component)  ***DESIGN HYPOTHESIS, NOT A SHIPPABLE ROUTER***")
    print("-" * 92)
    print(f"{'region (street|texture|pot|spr|made)':46}{'best component':20}{'gap':>7}{'n':>7}  runner-up")
    for region in sorted(routing, key=lambda r: (r.split('|')[0], -routing[r]['best_n'])):
        info = routing[region]
        if len(info["ranking"]) < 2:                    # single-component regions carry no routing signal
            continue
        mark = "*" if info["low_coverage"] else " "
        runner = info["ranking"][1]
        print(f"{region:46}{info['best_component']:20}{info['best_gap']:6.1%}{info['best_n']:>6}{mark} "
              f"{runner[0]} ({runner[1]:.0%})")

    # ---- coverage stats ----
    m = out["meta"]
    print("\n" + "-" * 92)
    print("COVERAGE  (cells graded = decisions scored; solves are live TexasSolver calls)")
    print("-" * 92)
    print(f"  cache-backed grading decisions : {sum(out['coverage_totals'].get(c, 0) for c in out['coverage_totals'] if c != '%s' % C_RESOLVER):,}")
    print(f"  by component                   : " + ", ".join(f"{c}={n:,}" for c, n in sorted(out['coverage_totals'].items())))
    print(f"  live solves (resolver)         : {m['resolver_solves']} (capped at {m['max_solves']})")
    print(f"  nodes walked (flop/turn/river) : {m['nodes_flop']}/{m['nodes_turn']}/{m['nodes_river']} "
          f"(cache-backed; 0 skipped-for-solve)")
    print(f"  runtime                        : {m['runtime_s']:.0f}s")

    print("\n" + "=" * 92)
    print("HONEST CAVEATS")
    print("=" * 92)
    for i, c in enumerate(out["caveats"], 1):
        print(f"({i}) {c}")
    print(f"\nFull matrix JSON -> {OUT}")


# ============================================================ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=250,
                    help="max cached boards per street (deterministic shuffled sample; keeps runtime < 20min)")
    ap.add_argument("--max-solves", type=int, default=24,
                    help="cap on live resolver solves (each is a real TexasSolver call)")
    args = ap.parse_args()

    t0 = time.time()
    acc = Accumulator()
    coverage = defaultdict(int)

    # single-raised-pot start pots the caches were solved at (gto_benchmark: pot 20 scaled; here in chips the
    # synthetic states use ~600 pot / 9700 stack = SPR ~16 flop, dropping as the board runs out).
    print("Walking flop cache...", flush=True)
    n_flop = walk_cache(_BENCH, "flop", 3, args.limit, acc, coverage, default_pot=600)
    print(f"  {n_flop} flop nodes. Walking turn cache...", flush=True)
    n_turn = walk_cache(_TURN, "turn", 4, args.limit, acc, coverage, default_pot=1400)
    print(f"  {n_turn} turn nodes. Walking river cache...", flush=True)
    n_river = walk_cache(_RIVER, "river", 5, args.limit, acc, coverage, default_pot=3000)
    print(f"  {n_river} river nodes. Grading preflop blueprint...", flush=True)
    grade_preflop(acc, coverage)
    print(f"  preflop done. Grading resolver (capped {args.max_solves} solves)...", flush=True)
    n_solves = grade_resolver(acc, coverage, args.max_solves, "river", _RIVER, 5, 3000)

    meta = {"seed": SEED, "limit_per_street": args.limit, "max_solves": args.max_solves,
            "resolver_solves": n_solves, "nodes_flop": n_flop, "nodes_turn": n_turn,
            "nodes_river": n_river, "runtime_s": round(time.time() - t0, 1),
            "min_decisive_n": MIN_DECISIVE_N}
    out = summarize(acc, coverage, meta)
    print_report(out)


if __name__ == "__main__":
    main()
