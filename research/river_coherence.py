"""RIVER COHERENCE DIAGNOSTIC — grade our bot's river value/bluff/bluff-catch coherence vs the SOLVED
river equilibrium, per docs/doctrine/RIVER_SYSTEM.md "DER RIVER-DIAGNOSE-SCORE" (OpenAI q6_river_diagnostic,
data/research_sweep/openai_river_consult.json).

For every RIVER aggressor decision node in the logged GTOW hands (data/sessions/gtow_hands_*.jsonl):
  1. Reconstruct BOTH ranges line-aware via range_tracker (the same Bayesian walk the live resolver uses).
  2. Solve the river subgame via gto_oracle.solve — CACHE-FIRST (the 12GB warm cache hits many); live solves
     are capped by --max-solves (an export may be holding the CPU — see docs/doctrine/PRECISION_DOCTRINE.md).
  3. From sigma*, tag each hero combo at each candidate bet size s as THEORETICAL VALUE (equity vs the villain
     range >= 0.5 = it wants a call = EV_bet>=EV_check on the river) vs THEORETICAL BLUFF (equity < 0.5 but it
     still bets in sigma*). Sum to V*_s (value weight betting s) and B*_s (bluff weight).
  4. Get our bot's ACTUAL policy at the node (bot.decide on the same reconstructed state) -> observed V_s, B_s.
  5. Per-size metrics: miss_value / over_value (value-coverage error), ratio_error (|B_s/V_s - B*_s/V*_s|, the
     B/(P+B) polarization deviation).
  6. Defender side (hero FACING a river bet): overfold_rate / overcall_rate vs sigma*'s indifference threshold h*.
  7. Aggregate every node by region = board-class x line x position x bet-size, pot/initial-pot weighted.

HONESTY: the grader is TexasSolver (~90% aligned with GTOW, docs/STATE.md) -> a PROXY, not bb-truth; small-n
cells are noise -> flagged (LOW_COV). Deterministic, $0 except the (capped) CPU solves.

  python -m research.river_coherence [--limit N] [--max-solves M] [--verbose]
"""
from __future__ import annotations

import argparse
import glob
import json
from collections import defaultdict
from pathlib import Path

from treys import Card, Evaluator

from pokerbot.benchmark.slumbot import build_state
from pokerbot.strategy import gto_oracle
from pokerbot.strategy.range_tracker import RangeTracker

# ---- constants (named, not magic — the elegance rule) -------------------------------------------------
OUT = Path("data/research_sweep/river_coherence.json")
STREETS = ["preflop", "flop", "turn", "river"]

EPS = 1e-9                    # ratio-denominator floor (spec's eps)
VALUE_EQ_THRESHOLD = 0.50     # equity vs the villain range at/above which a betting combo is VALUE, else BLUFF
                              # (river: no cards to come -> raw equity == showdown equity == EV-of-being-called sign)
BET_SUPPORT = 0.02            # a sigma* action played < 2% is out of support (matches study_grade _SUPPORT_EPS)
LOW_COVERAGE_N = 20           # a region cell with fewer nodes is flagged NOISE (spec's small-n honesty)

# The solve tree the census uses (GTOW's own river arms, per postflop.ECALL_SIZES); kept small for river speed.
_RIVER_BETS = [
    "set_bet_sizes oop,river,bet,33,75", "set_bet_sizes oop,river,allin",
    "set_bet_sizes ip,river,bet,33,75", "set_bet_sizes ip,river,allin",
]
SOLVE_ACCURACY = 0.5          # river subgames converge fast; the census default
SOLVE_MAX_ITER = 120
# NOTE (units): pot AND eff_stack are passed to the solver in CHIPS (build_state uses STACK=20000, bb=100).
# The effective stack is the SMALLER remaining stack at the river; passing bb-units here collapses the tree
# to an all-in-only solve (pot 1100 chips vs "200" bb -> jam-only), which is exactly the bug that made every
# solved node emit a lone 'BET 200'. eff_stack is computed per-node from the reconstructed state.

_EV = Evaluator()


# ----------------------------------------------------------------------------------------------------------------------
# Session parsing (compact log tokens -> engine states at each river aggressor node)
# ----------------------------------------------------------------------------------------------------------------------
def _parse_cards(s: str) -> list:
    s = s or ""
    return [s[i:i + 2] for i in range(0, len(s), 2)]


def _tokens_to_prefixes(history: list, button: int):
    """Yield (acting_seat, action_string_prefix, street) for EVERY decision point in the flat token log.
    The prefix is the betting BEFORE the actor's own move — exactly what slumbot.build_state consumes.
    Play order: preflop the button (SB) acts first; each later street the non-button (BB) acts first.
    ['b225','c','_','k',...] -> the '_' ends a street and flips the first actor to the non-button."""
    seg, street_idx, actor = [[]], 0, button
    for tok in history:
        if tok == "_":
            street_idx += 1
            seg.append([])
            actor = 1 - button
            continue
        prefix = "/".join("".join(s) for s in seg)
        yield actor, prefix, STREETS[min(street_idx, 3)]
        seg[street_idx].append(tok)
        actor = 1 - actor


def _button_seat(hand: dict) -> int:
    """HU: the button is the SB seat. Session players carry a 'position' tag."""
    ps = hand.get("players", [])
    return next((i for i, p in enumerate(ps) if str(p.get("position", "")).upper() in ("SB", "BTN", "BU")), -1)


def river_aggressor_nodes(hand: dict):
    """Yield reconstructed engine states at every RIVER node where the actor can BET or CHECK (aggressor
    node = to_call==0: hero first-to-act OR facing a check). The actor is treated as 'hero' (our bot's seat)."""
    button = _button_seat(hand)
    if button < 0 or len(hand.get("players", [])) != 2:
        return
    board = _parse_cards(hand.get("board", ""))
    if len(board) != 5:                        # a full river board is required for the subgame solve
        return
    for actor, prefix, street in _tokens_to_prefixes(hand.get("history", []), button):
        if street != "river":
            continue
        hole = _parse_cards(hand["players"][actor].get("hole", ""))
        if len(hole) != 2:
            continue
        state = build_state(hole, board, prefix, client_pos=actor, button=button)
        if state is None:
            continue
        leg = state["legal"]
        if leg.get("to_call", 0) == 0 and leg.get("can_raise"):   # aggressor node: can bet/check
            yield state


# ----------------------------------------------------------------------------------------------------------------------
# Ranges + the river subgame solve (cache-first)
# ----------------------------------------------------------------------------------------------------------------------
def _hero_villain_combos(tracker: RangeTracker, state: dict) -> tuple[dict, dict]:
    """(hero_weighted_combos, villain_weighted_combos) as {(c1,c2): weight}, board-dead-card filtered.
    Hero = the acting seat (state['to_act']); villain = the other seat. The tracker's internal per-combo
    weights (not the class-aggregated emit string) are what we need to sum V*/B* over."""
    hero_seat = state["to_act"]
    board = set(state.get("board", []))
    hero_w = {c: w for c, w in tracker.range.get(hero_seat, {}).items() if not (set(c) & board)}
    vill_w = {c: w for c, w in tracker.range.get(1 - hero_seat, {}).items() if not (set(c) & board)}
    return hero_w, vill_w


def _emit_ranges(tracker: RangeTracker, state: dict) -> tuple[str, str]:
    """(oop_str, ip_str) TexasSolver class-weighted strings for the solve. OOP = non-button, IP = button."""
    board = set(state.get("board", []))
    oop_seat = 0 if state["button"] == 1 else 1
    return tracker.emit(oop_seat, board), tracker.emit(state["button"], board)


def _eff_stack_chips(state: dict) -> float:
    """Effective river stack in CHIPS = the smaller of the two players' remaining stacks (the max that can
    still go in). Same unit as pot -> the solver builds a real bet tree, not a jam-only collapse."""
    stacks = [float(p.get("stack") or 0) for p in state.get("players", [])]
    return min(stacks) if stacks else 0.0


def _solve_cached_only(oop: str, ip: str, board: list, pot: float, eff_stack: float, allow_live: bool):
    """Solve the river subgame; return the dumped root node or None. When allow_live is False we probe the
    persistent cache directly and NEVER shell out to the solver (protects a running export's CPU)."""
    if not oop or not ip or eff_stack <= 0:
        return None
    if allow_live:
        return gto_oracle.solve(board, oop, ip, pot=pot, eff_stack=eff_stack, bets=_RIVER_BETS,
                                accuracy=SOLVE_ACCURACY, max_iter=SOLVE_MAX_ITER)
    # cache-only path: reproduce the key gto_oracle.solve would compute, read the file if present
    ck = gto_oracle._cache_key(board, oop, ip, pot, eff_stack, _RIVER_BETS,
                               SOLVE_ACCURACY, SOLVE_MAX_ITER, 2, "holdem")
    cpath = gto_oracle._CACHE_DIR / f"{ck}.json"
    if cpath.exists():
        try:
            return json.loads(cpath.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 — corrupt entry -> treat as a miss
            return None
    return None


def _river_root_for_hero(node: dict, hero_is_ip: bool) -> dict | None:
    """The dumped root is the OOP first-to-act river node. If hero is IP (facing a check), navigate the
    CHECK child (where IP is the actor). Returns the node whose sigma* IS hero's betting decision, or None."""
    if node is None:
        return None
    if not hero_is_ip:
        return node
    kids = node.get("childrens") or {}
    return next((v for k, v in kids.items() if k.split()[0] == "CHECK"), None)


# ----------------------------------------------------------------------------------------------------------------------
# Equilibrium value/bluff tagging + our bot's observed policy
# ----------------------------------------------------------------------------------------------------------------------
def _combo_equity_vs_range(hole: tuple, board: list, villain_w: dict) -> float:
    """Hero combo's exact showdown equity vs the villain's weighted range (river -> no MC, pure enumeration)."""
    dead = set(hole) | set(board)
    bcards = [Card.new(x) for x in board]
    hero_sc = _EV.evaluate(bcards, [Card.new(hole[0]), Card.new(hole[1])])
    win = tie = tot = 0.0
    for c, w in villain_w.items():
        if set(c) & dead:
            continue
        vs = _EV.evaluate(bcards, [Card.new(c[0]), Card.new(c[1])])
        tot += w
        if hero_sc < vs:          # treys: LOWER = stronger
            win += w
        elif hero_sc == vs:
            tie += w
    return (win + 0.5 * tie) / tot if tot > 0 else 0.0


def _bet_actions(node: dict, pot: float) -> list[tuple[str, float]]:
    """[(action_label, size_frac_of_pot)] for the BET/ALLIN arms of the dumped node. The solver's BET label is
    the ABSOLUTE chip amount of the bet -> size fraction = label / pot (pot = the solve's set_pot, in chips)."""
    actions = (node.get("strategy") or {}).get("actions", [])
    out = []
    for a in actions:
        head = a.split()
        if head[0] in ("BET", "ALLIN"):
            amt = float(head[1]) if len(head) > 1 and head[1].replace(".", "").isdigit() else 0.0
            frac = (amt / pot) if (pot and amt) else (999.0 if head[0] == "ALLIN" else 0.0)
            out.append((a, frac))
    return out


def _size_bucket(frac: float) -> str:
    """Coarse size class for the region key (the census/GTOW river grid boundaries)."""
    if frac <= 0.0:
        return "?"
    if frac < 0.50:
        return "small(<50)"
    if frac < 0.90:
        return "mid(50-90)"
    if frac < 1.40:
        return "big(90-140)"
    return "overbet(>=140)"


def solved_value_bluff(node: dict, hero_w: dict, villain_w: dict, board: list, pot: float) -> dict:
    """{bet_label: {'V':V*_s, 'B':B*_s}} — equilibrium value/bluff weight betting each size, plus a per-combo
    equity cache. A combo counts toward size s weighted by sigma*(bet s | combo) * range_weight(combo)."""
    bets = _bet_actions(node, pot)
    if not bets:
        return {}
    out = {lab: {"V": 0.0, "B": 0.0, "frac": frac} for lab, frac in bets}
    for combo, w in hero_w.items():
        sigma = gto_oracle.strategy_for(node, combo[0], combo[1])
        if not sigma:
            continue
        eq = _combo_equity_vs_range(combo, board, villain_w)
        is_value = eq >= VALUE_EQ_THRESHOLD
        for lab, frac in bets:
            p = sigma.get(lab, 0.0)
            if p <= 0:
                continue
            out[lab]["V" if is_value else "B"] += w * p
    return out


def observed_value_bluff(state: dict, node: dict, hero_w: dict, villain_w: dict, board: list, bot) -> dict:
    """Our bot's observed value/bluff weight per solver size. We ask bot.decide once per hero combo (swapping
    the hole into the reconstructed state) and bin its bet by the NEAREST solver size label. This measures the
    bot's REALIZED policy against the same equilibrium size grid the census uses."""
    pot = float(state.get("pot") or 0)
    bets = _bet_actions(node, pot)
    out = {lab: {"V": 0.0, "B": 0.0, "frac": frac} for lab, frac in bets}
    if not bets:
        return out
    hero_seat = state["to_act"]
    for combo, w in hero_w.items():
        st = _state_with_hole(state, hero_seat, combo)
        try:
            dec = bot.decide(st)
        except Exception:  # noqa: BLE001 — one bad combo must not kill the node
            continue
        if dec.get("action") not in ("bet", "raise", "allin"):
            continue                          # a check contributes to neither V_s nor B_s (it's not a bet)
        # map the bot's chosen chip amount to a pot-fraction, then to the nearest solver size arm
        amt = dec.get("amount") or 0
        committed = st["players"][hero_seat].get("committed_street", 0) or 0
        bet_chips = max(0.0, amt - committed)
        frac = (bet_chips / pot) if pot else 0.0
        lab = min(bets, key=lambda b: abs(b[1] - frac))[0]
        eq = _combo_equity_vs_range(combo, board, villain_w)
        out[lab]["V" if eq >= VALUE_EQ_THRESHOLD else "B"] += w
    return out


def _state_with_hole(state: dict, seat: int, combo: tuple) -> dict:
    """A shallow state copy with `seat`'s hole swapped to `combo` (so bot.decide reasons about that combo)."""
    st = dict(state)
    st["players"] = [dict(p) for p in state["players"]]
    st["players"][seat] = dict(state["players"][seat])
    st["players"][seat]["hole"] = [combo[0], combo[1]]
    return st


# ----------------------------------------------------------------------------------------------------------------------
# Defender side (hero facing a river bet): overfold / overcall vs the sigma* indifference threshold
# ----------------------------------------------------------------------------------------------------------------------
def defender_scores(hand: dict, tracker_cache: dict, bot):
    """Yield (region_key, overfold, overcall, pot_weight) for each RIVER node where hero FACES a bet.
    Threshold h* = pot odds s/(1+2s) (the equilibrium indifference equity for a bluff-catch). overfold = weight
    of hero combos with equity >= h* that the bot FOLDS; overcall = weight with equity < h* that the bot CALLS."""
    button = _button_seat(hand)
    if button < 0 or len(hand.get("players", [])) != 2:
        return
    board = _parse_cards(hand.get("board", ""))
    if len(board) != 5:
        return
    for actor, prefix, street in _tokens_to_prefixes(hand.get("history", []), button):
        if street != "river":
            continue
        hole = _parse_cards(hand["players"][actor].get("hole", ""))
        if len(hole) != 2:
            continue
        state = build_state(hole, board, prefix, client_pos=actor, button=button)
        if state is None:
            continue
        leg = state["legal"]
        if leg.get("to_call", 0) <= 0:         # defender node = hero is FACING a bet
            continue
        pot = float(state.get("pot") or 0)
        to_call = float(leg["to_call"])
        s = to_call / (pot - to_call) if pot > to_call else 1.0    # bet size as a fraction of the pre-bet pot
        h_star = to_call / (pot + to_call)                          # pot-odds indifference equity
        tk = _tracker_for(state, tracker_cache)
        hero_w, vill_w = _hero_villain_combos(tk, state)
        if not hero_w or not vill_w:
            continue
        hero_seat = state["to_act"]
        of_num = of_den = oc_num = oc_den = 0.0
        for combo, w in hero_w.items():
            eq = _combo_equity_vs_range(combo, board, vill_w)
            st = _state_with_hole(state, hero_seat, combo)
            try:
                act = bot.decide(st).get("action")
            except Exception:  # noqa: BLE001
                continue
            if eq >= h_star:
                of_den += w
                if act == "fold":
                    of_num += w
            else:
                oc_den += w
                if act in ("call", "raise", "allin"):
                    oc_num += w
        overfold = of_num / of_den if of_den > 0 else None
        overcall = oc_num / oc_den if oc_den > 0 else None
        region = _region_key(board, prefix, hero_seat == state["button"], _size_bucket(s))
        yield region, overfold, overcall, pot / (2.0 * state.get("bb", 100))


# ----------------------------------------------------------------------------------------------------------------------
# Region aggregation
# ----------------------------------------------------------------------------------------------------------------------
def board_class(board: list) -> str:
    """Coarse river texture: paired / monotone(4+flush) / two-tone / rainbow, + straighty flag folded in."""
    ranks = [c[0] for c in board]
    suits = [c[1] for c in board]
    paired = len(set(ranks)) < len(ranks)
    from collections import Counter
    smax = max(Counter(suits).values())
    if smax >= 4:
        tex = "monotone4+"
    elif smax == 3:
        tex = "flush3"
    elif smax == 2:
        tex = "two-tone"
    else:
        tex = "rainbow"
    return f"{'paired-' if paired else ''}{tex}"


def _line_summary(prefix: str) -> str:
    """A compact line tag from the action string: how many streets saw a bet before the river node."""
    segs = prefix.split("/")
    tags = []
    for seg in segs[:3]:                        # preflop/flop/turn only (river action is AT the node)
        tags.append("b" if "b" in seg else "x")
    return "".join(tags) if tags else "x"


def _region_key(board: list, prefix: str, hero_is_ip: bool, size_bucket: str) -> str:
    return "|".join([board_class(board), _line_summary(prefix), "IP" if hero_is_ip else "OOP", size_bucket])


def _tracker_for(state: dict, cache: dict) -> RangeTracker:
    """Build (or reuse) the Bayesian tracker for a state. Cache by the history id to avoid rebuilding per combo."""
    key = id(state.get("history"))
    tk = cache.get(key)
    if tk is None:
        tk = RangeTracker().build(state)
        cache[key] = tk
    return tk


# ----------------------------------------------------------------------------------------------------------------------
# Driver
# ----------------------------------------------------------------------------------------------------------------------
def _accumulate_aggressor(state, node, hero_is_ip, board, tracker, bot, agg):
    """Score one aggressor node: solved V*/B* vs observed V/B per size -> region metrics."""
    hero_w, vill_w = _hero_villain_combos(tracker, state)
    if not hero_w or not vill_w:
        return 0
    star = solved_value_bluff(node, hero_w, vill_w, board, float(state.get("pot") or 0))
    if not star:
        return 0
    obs = observed_value_bluff(state, node, hero_w, vill_w, board, bot)
    prefix = _tokens_to_prefix_of(state)
    pot_w = float(state.get("pot") or 0) / (2.0 * state.get("bb", 100))
    scored = 0
    for lab, sv in star.items():
        Vs, Bs = sv["V"], sv["B"]
        if Vs + Bs < BET_SUPPORT:              # size not in sigma*'s support -> skip (noise)
            continue
        ov = obs.get(lab, {"V": 0.0, "B": 0.0})
        Vo, Bo = ov["V"], ov["B"]
        miss_value = max(0.0, (Vs - Vo) / max(Vs, EPS))
        over_value = max(0.0, (Vo - Vs) / max(Vs, EPS))
        target_ratio = Bs / max(Vs, EPS)
        actual_ratio = Bo / max(Vo, EPS)
        ratio_error = abs(actual_ratio - target_ratio) / max(target_ratio, EPS)
        region = _region_key(board, prefix, hero_is_ip, _size_bucket(sv["frac"]))
        a = agg[region]
        a["miss_value"] += miss_value * pot_w
        a["over_value"] += over_value * pot_w
        a["ratio_error"] += ratio_error * pot_w
        a["pot_weight"] += pot_w
        a["n"] += 1
        scored += 1
    return scored


def _tokens_to_prefix_of(state: dict) -> str:
    """Rebuild the action string from a reconstructed state's history (for the region line tag). Streets are
    '/'-separated (as _line_summary expects); only the per-street presence of a bet matters downstream."""
    toks, cur = [], None
    for h in state.get("history", []):
        st = h.get("street")
        if cur is not None and st != cur:
            toks.append("/")
        cur = st
        a = h.get("action")
        if a == "fold":
            toks.append("f")
        elif a == "check":
            toks.append("k")
        elif a == "call":
            toks.append("c")
        elif a in ("bet", "raise", "allin"):
            toks.append("b" + str(int(h.get("to") or 0)))
    return "".join(toks)


def run(limit: int | None, max_solves: int, verbose: bool) -> None:
    from pokerbot.strategy.bot import PokerBot
    bot = PokerBot(0, seed=7, exploit=False)      # the shipped floor, exploit OFF (the GTO-graded config)

    files = sorted(glob.glob("data/sessions/gtow_hands_*.jsonl"))
    hands = []
    for f in files:
        for line in open(f, encoding="utf-8"):
            try:
                h = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            # only full-board hands can produce a river node — the diagnostic's unit. Filtering here means a
            # small --limit still exercises the pipeline (the raw logs are mostly preflop folds).
            if len(h.get("board") or "") == 10:
                hands.append(h)
    if limit:
        hands = hands[:limit]

    agg = defaultdict(lambda: {"miss_value": 0.0, "over_value": 0.0, "ratio_error": 0.0,
                               "overfold": 0.0, "overfold_w": 0.0, "overcall": 0.0, "overcall_w": 0.0,
                               "pot_weight": 0.0, "n": 0})
    tracker_cache: dict = {}
    solves_done = 0
    nodes_seen = nodes_scored = cache_hits = cache_miss = 0

    for hand in hands:
        # ---- aggressor side (value/bluff coherence) ----
        for state in river_aggressor_nodes(hand):
            nodes_seen += 1
            board = state["board"]
            tracker = _tracker_for(state, tracker_cache)
            oop, ip = _emit_ranges(tracker, state)
            pot = float(state.get("pot") or 0)
            eff = _eff_stack_chips(state)
            allow_live = solves_done < max_solves
            # peek the cache first even when live is allowed, so a hit doesn't burn the live budget
            node_root = _solve_cached_only(oop, ip, board, pot, eff, allow_live=False)
            if node_root is None and allow_live:
                node_root = _solve_cached_only(oop, ip, board, pot, eff, allow_live=True)
                if node_root is not None:
                    solves_done += 1
                    cache_miss += 1
            elif node_root is not None:
                cache_hits += 1
            else:
                cache_miss += 1
            if node_root is None:
                continue
            hero_is_ip = (state["to_act"] == state["button"])
            node = _river_root_for_hero(node_root, hero_is_ip)
            if node is None:
                continue
            got = _accumulate_aggressor(state, node, hero_is_ip, board, tracker, bot, agg)
            nodes_scored += 1 if got else 0
            if verbose and got:
                print(f"  scored node hand {hand.get('hand_id')} board {''.join(board)} "
                      f"IP={hero_is_ip} sizes={got}")

        # ---- defender side (bluff-catch coherence) — cache/solver-free (pure equity threshold) ----
        for region, overfold, overcall, pw in defender_scores(hand, tracker_cache, bot):
            a = agg[region]
            if overfold is not None:
                a["overfold"] += overfold * pw
                a["overfold_w"] += pw
            if overcall is not None:
                a["overcall"] += overcall * pw
                a["overcall_w"] += pw

    _finalize_and_report(agg, nodes_seen, nodes_scored, cache_hits, cache_miss, solves_done, max_solves)


def _finalize_and_report(agg, nodes_seen, nodes_scored, cache_hits, cache_miss, solves_done, max_solves) -> None:
    out = {}
    for region, a in agg.items():
        n = a["n"]
        pw = a["pot_weight"] or EPS
        out[region] = {
            "miss_value": round(a["miss_value"] / pw, 4) if n else None,
            "over_value": round(a["over_value"] / pw, 4) if n else None,
            "ratio_error": round(a["ratio_error"] / pw, 4) if n else None,
            "overfold": round(a["overfold"] / a["overfold_w"], 4) if a["overfold_w"] else None,
            "overcall": round(a["overcall"] / a["overcall_w"], 4) if a["overcall_w"] else None,
            "n": n,
            "pot_weighted": round(a["pot_weight"], 2),
            "low_coverage": n < LOW_COVERAGE_N,
        }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")

    print(f"\n=== RIVER COHERENCE — {len(out)} regions, {nodes_scored}/{nodes_seen} aggressor nodes scored ===")
    print(f"solves: {cache_hits} cache-hit, {cache_miss} miss ({solves_done}/{max_solves} live budget used)")
    print("GRADER = TexasSolver (~90% GTOW-aligned) -> PROXY not bb-truth; LOW_COV cells (n<20) are NOISE.\n")

    def _top(metric: str, label: str, need_cov: bool = True):
        rows = [(r, v) for r, v in out.items() if v.get(metric) is not None]
        rows.sort(key=lambda kv: -(kv[1][metric] or 0))
        print(f"--- TOP {label} ---")
        for r, v in rows[:8]:
            flag = " [LOW_COV]" if v["low_coverage"] else ""
            cov = v["n"] if metric in ("miss_value", "over_value", "ratio_error") else "-"
            print(f"  {v[metric]:6.3f}  n={cov}  pw={v['pot_weighted']:6.1f}  {r}{flag}")
        print()

    _top("miss_value", "MISSED VALUE (bleed: not value-betting thin enough)")
    _top("ratio_error", "POLARIZATION ERROR (bleed: wrong bluff/value ratio)")
    _top("overfold", "OVER-FOLD (bleed: folding bluff-catchers we should call)")
    _top("overcall", "OVER-CALL (bleed: calling below the indifference threshold)")
    print(f"-> {OUT}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="cap hands read from the session logs")
    ap.add_argument("--max-solves", type=int, default=5, help="cap FRESH live solves (cache-first; protects a running export)")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()
    run(a.limit, a.max_solves, a.verbose)


if __name__ == "__main__":
    main()
