"""The engine-as-API — the typed primitive library the LLM brain calls in a program-of-thought (docs/DATASET_SPEC.md).
THIN wrappers over existing, tested engine code (no logic duplication): equity, the Mathematics-of-Poker formulas,
board texture, hand strength, and a legal-action coercer. The brain emits Python calling THESE; `executor.py` runs it.

Design: math is done by code (no LLM-arithmetic errors), legality by the engine (truth). Everything is deterministic
given a seed. Strategy lookups (preflop blueprint / solver-freq advisor / exploit model) are exposed best-effort and
return None where 6-max coverage is not yet built — the brain must handle None.
"""
from __future__ import annotations

import os
import random
import threading
import uuid

from pokerbot.engine.equity import equity_vs_range, equity_vs_weighted_range, equity_vs_class_range
from pokerbot.engine.evaluator import evaluate, best_five_name
from pokerbot.engine.cards import hand_class
from pokerbot.strategy.postflop import classify_board
from knowledge_base.math import formulas as F
from knowledge_base.math.postflop_formulas import *  # noqa: F401,F403 — engine-verified post-flop toolkit, callable as api.<fn>
try:                                                  # engine-verified STRATEGY formulas (optional until generated)
    import knowledge_base.math.strategy_formulas as _strategy_formulas
    globals().update({_n: getattr(_strategy_formulas, _n) for _n in getattr(_strategy_formulas, "__all__", [])})
except Exception:  # noqa: BLE001
    pass

# ---------------------------------------------------------------- equity
def equity(hero: list, villain, board: list | None = None, iters: int | None = None,
           seed: int | None = 0) -> float:
    """Hero equity (0..1) vs a villain range. `villain` may be a list of class strings (['AA','AKs']), a list of
    combo tuples ([('As','Ks')]), or a weighted dict ({('As','Ks'): 0.6}). Board = community cards (or None preflop).
    `iters` defaults to the ACTIVE compute mode's equity_iters (the accuracy<->time lever; brain/modes.py)."""
    if iters is None:
        from pokerbot.brain import modes
        iters = modes.current().equity_iters
    rng = random.Random(seed)
    if isinstance(villain, dict):
        return equity_vs_weighted_range(hero, villain, board, iters=iters, rng=rng)
    if villain and isinstance(villain[0], (tuple, list)):
        return equity_vs_range(hero, [tuple(v) for v in villain], board, iters=iters, rng=rng)
    return equity_vs_class_range(hero, list(villain), board, iters=iters, rng=rng)


def range_top(frac: float) -> list:
    """Top-`frac` of starting hands as 169-class strings — a COMPACT continuing-range prior so the brain emits
    `api.range_top(0.2)` instead of a long literal list (a much shorter program = it fits the RL token budget, and the
    downstream read-branch stays salient). Wraps `preflop_strength.range_top`; safe fallback if unavailable."""
    frac = max(0.02, min(1.0, float(frac)))
    try:
        from pokerbot.strategy import preflop_strength as ps
        r = sorted(ps.range_top(frac))
        if r:
            return r
    except Exception:  # noqa: BLE001
        pass
    base = ["AA", "KK", "QQ", "JJ", "TT", "99", "88", "77", "66", "55", "44", "33", "22", "AKs", "AQs", "AJs", "ATs",
            "KQs", "KJs", "QJs", "JTs", "AKo", "AQo", "KQo"]
    return base[:max(3, round(len(base) * frac / 0.4))]


# ---------------------------------------------------------------- Mathematics of Poker (formulas.py)
def required_equity(to_call: float, pot: float) -> float:
    """Pot-odds break-even equity to call: to_call / (pot + to_call)."""
    if to_call <= 0:
        return 0.0
    return to_call / (pot + to_call)


def pot_odds(to_call: float, pot: float):
    """(ratio, required_equity) via formulas.compute_pot_odds (pot=P already in the middle, bet faced=to_call)."""
    return F.compute_pot_odds(pot, to_call, to_call)


def mdf(bet: float, pot: float) -> float:
    """Minimum defense frequency vs a bet of `bet` into `pot`."""
    return F.minimum_defense_frequency(pot, bet)


def spr(effective_stack: float, pot: float) -> float:
    return F.compute_spr(effective_stack, pot)


def outs_equity(outs: int, cards_to_come: int = 2) -> float:
    return F.outs_to_equity_rule_2_and_4(outs, cards_to_come)


# ---------------------------------------------------------------- texture + made hand
def board_texture(board: list) -> dict:
    """{'paired','monotone','twotone','connected','high','dynamic'} bools."""
    return classify_board(board) if board else {}


def hand_rank(hole: list, board: list):
    """(made_hand_name, strength) where strength in (0,1], higher=better (1 - treys/7462)."""
    if not board:
        return ("preflop", None)
    r = evaluate(board, list(hole))
    return (best_five_name(board, list(hole)), round(1.0 - r / 7462.0, 4))


def hand_class_of(hole: list) -> str:
    return hand_class(hole[0], hole[1])


# ---------------------------------------------------------------- strategy lookups (best-effort; None if uncovered)
def preflop_mix(spot) -> dict | None:
    """The solved preflop GTO action-mix for hero's class at this node, or None if outside the (200bb HU) blueprint.
    NOTE: 6-max preflop coverage is dataset-driven; this is best-effort until the 6-max ranges are wired."""
    try:
        from pokerbot.strategy import preflop_blueprint as pbp
        if not pbp.available():
            return None
        raises = sum(1 for a in spot.line if a["action"] in ("bet", "raise"))
        vill_allin = (not spot.legal.get("can_raise", True)) and (spot.to_call or 0) > 0   # facing an all-in/cap -> jam node
        node = pbp.node_for_state(spot.hero_pos in ("BTN", "SB"), raises,
                                  spot.legal.get("can_check", False), vill_allin)
        return pbp.actions(node, hand_class_of(spot.hero_hole)) if node else None
    except Exception:  # noqa: BLE001
        return None


def preflop_solve(spot) -> dict | None:
    """The PREFLOP analog of solve_node: the near-Nash HU-200bb blueprint mix as DSL VERBS + per-verb sizes —
    {verb: prob, '_sizes_bb': {'raise': bb}} (the format decide_mix + solve_node already use), or None if off-blueprint.
    So the brain plays the EXACT blueprint preflop via `m = api.preflop_solve(spot); decide_mix(m)` — a real reasoning
    loop (engine-derived), NOT the equity-logic that OVER-FOLDS preflop (the measured −41 bb/hand leak). Reuses
    preflop_mix (blueprint labels open/3bet/...) + the SIZES_BB translation; limp -> call, jam -> allin."""
    try:
        if getattr(spot, "n_active", 2) != 2:          # the blueprint is HU-200bb-only -> NEVER apply it to 6-max preflop
            return None                                # (node_for_state ignores n_active, so guard here; 6-max -> caller falls back)
        m = preflop_mix(spot)
        if not m:
            return None
        from pokerbot.strategy.preflop_blueprint import SIZES_BB
        verbs: dict = {}
        sizes: dict = {}
        for label, p in m.items():
            if not p or p <= 0:
                continue
            if label in SIZES_BB:                      # open/iso/3bet/4bet/5bet -> a sized raise; limp -> a 1bb call
                verb = "call" if label == "limp" else "raise"
                if verb == "raise":
                    sizes["raise"] = SIZES_BB[label]
            elif label == "jam":
                verb = "allin"
            elif label in ("call", "check", "fold"):
                verb = label
            else:
                continue
            verbs[verb] = verbs.get(verb, 0.0) + float(p)
        if not verbs:
            return None
        if sizes:
            verbs["_sizes_bb"] = sizes
        return verbs
    except Exception:  # noqa: BLE001
        return None


def solver_freq(hole: list, board: list, role: str, street: str) -> float | None:
    """Advisor P(bet) for this hand/board, or None if the advisor is unavailable for that street."""
    try:
        from pokerbot.strategy import advisor as A
        return A.p_bet(hole, board, role, street) if A.available(street) else None
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------- SEARCH AT INFERENCE: live TexasSolver solve
# The brain orchestrates a real solver (ReBeL/Pluribus-style): on a postflop HU spot it solves the actual board and
# returns the EXACT GTO strategy for hero's hand. The math/strategy is the solver's; the brain only navigates + acts.
# This is a v1 PORT of pokerbot/benchmark/gto_oracle_match.GTOOracleAgent (its _solve_board/_match_label/_street_actions)
# adapted from the engine state() dict to the canonical brain Spot (Spot.line, amounts in bb not chips).

# Lean bet tree (1 bet size + allin per street, NO raise) -> a small tree -> fast per-spot solves (gto_oracle_match._LEAN).
_LEAN_BETS = [f"set_bet_sizes {pos},{st},{b}" for pos in ("oop", "ip") for st in ("flop", "turn", "river")
              for b in ("bet,66", "allin")]
_SOLVE_ACC = 0.5          # solver target exploitability (% of pot) — speed<->precision lever; matches the oracle match
_SOLVE_ITERS = 40         # max CFR iterations — kept small for live-solve latency (lean tree converges fast)
_SOLVE_TIMEOUT = int(os.environ.get("SOLVE_TIMEOUT", "150"))   # per-solve wall cap (s). Measured (2026-06-18): one
                          # wide-HU flop solve is ~30s at 8 threads but ~57s at 4 and ~79s at 2 — and under a K-way
                          # PARALLEL run every solve shares the cores, so it runs SLOWER than its solo time. A timeout
                          # returns None -> a fix-defeating fall-back, so the cap must clear the worst-case loaded
                          # latency with margin: 150s (env-overridable). The solo path rarely waits this long.
_POT_BUCKET_BB = 4.0      # cache pot-bucket width in bb: same board + similar pot reuses one solve
_STACK_BUCKET_BB = 10.0   # cache stack-bucket width in bb: same board + similar effective stack reuses one solve
_SOLVE_CACHE: dict = {}   # module-level: {board+pot+stack+range-hash -> root node dict | None}; persists across a run
_SOLVE_THREADS = int(os.environ.get("SOLVE_THREADS", "8"))   # TexasSolver CPU threads PER solve. The parallel Slumbot
                          # run sets this to 2 so K games x SOLVE_THREADS <= the 24 cores (no oversubscription); the
                          # solo path keeps the original 8. Read once at import (env is fixed for a run).

# Per-key dedup so K concurrent games that hit the SAME spot solve it ONCE (the cache-hit win) while DIFFERENT spots
# solve in PARALLEL. `_CACHE_LOCK` guards BOTH `_SOLVE_CACHE` and `_SOLVE_INFLIGHT` (a {key: Event} of solves currently
# running) — it is held only for the dict ops, NEVER across the ~6s solve. The first thread for a missing key registers
# an Event + solves outside the lock; later threads for that key find the Event and WAIT on it, then read the cache.
_CACHE_LOCK = threading.Lock()
_SOLVE_INFLIGHT: dict = {}   # {key -> threading.Event}: keys with a solve in progress (signalled when the result lands)

# WIDE heads-up single-raised-pot ranges (TexasSolver explicit 169-class enumeration). The HU SB opens ~80% and the
# BB defends ~60% — far wider than the 6-max BTN-vs-BB ranges (gto_benchmark._IP/_OOP, ~20-25%), which returned None
# for almost every HU hero hand. Postflop the button is IP and the BB is OOP, so:
#   _HU_IP  = the SB-open range  (~77% / 144 classes / 1026 combos)  -> the IN-position player
#   _HU_OOP = the BB-defend range (~61% / 126 classes / 810 combos)  -> the OUT-of-position player
# HONEST/APPROXIMATE: these are FIXED full-SRP ranges at EVERY street and line. They are NOT line-aware — 3bet,
# limped, or flop-narrowed continuation ranges are inexact, and turn/river ranges should be narrower than the flop's.
# v2's goal is COVERAGE (the solver actually FIRES in HU) + approximate HU correctness, NOT exact GTO. Exact
# per-line continuation-range propagation is future work. (Verified once: O.solve accepts these strings, 7/7 coverage.)
_HU_IP = ("22,32s,33,42s,43o,43s,44,52s,53o,53s,54o,54s,55,62s,63s,64o,64s,65o,65s,66,72s,73s,74s,75o,75s,76o,76s,77,"
          "82s,83s,84s,85o,85s,86o,86s,87o,87s,88,92s,93s,94s,95s,96o,96s,97o,97s,98o,98s,99,A2o,A2s,A3o,A3s,A4o,A4s,"
          "A5o,A5s,A6o,A6s,A7o,A7s,A8o,A8s,A9o,A9s,AA,AJo,AJs,AKo,AKs,AQo,AQs,ATo,ATs,J2s,J3s,J4s,J5s,J6o,J6s,J7o,J7s,"
          "J8o,J8s,J9o,J9s,JJ,JTo,JTs,K2o,K2s,K3o,K3s,K4o,K4s,K5o,K5s,K6o,K6s,K7o,K7s,K8o,K8s,K9o,K9s,KJo,KJs,KK,KQo,"
          "KQs,KTo,KTs,Q2s,Q3s,Q4o,Q4s,Q5o,Q5s,Q6o,Q6s,Q7o,Q7s,Q8o,Q8s,Q9o,Q9s,QJo,QJs,QQ,QTo,QTs,T2s,T3s,T4s,T5s,"
          "T6o,T6s,T7o,T7s,T8o,T8s,T9o,T9s,TT")
_HU_OOP = ("22,32s,33,42s,43s,44,52s,53s,54o,54s,55,62s,63s,64s,65o,65s,66,72s,73s,74s,75s,76o,76s,77,82s,83s,84s,85s,"
           "86s,87o,87s,88,92s,93s,94s,95s,96s,97s,98o,98s,99,A2o,A2s,A3o,A3s,A4o,A4s,A5o,A5s,A6o,A6s,A7o,A7s,A8o,A8s,"
           "A9o,A9s,AA,AJo,AJs,AKo,AKs,AQo,AQs,ATo,ATs,J2s,J3s,J4s,J5s,J6s,J7s,J8o,J8s,J9o,J9s,JJ,JTo,JTs,K2s,K3s,K4s,"
           "K5o,K5s,K6o,K6s,K7o,K7s,K8o,K8s,K9o,K9s,KJo,KJs,KK,KQo,KQs,KTo,KTs,Q2s,Q3s,Q4s,Q5s,Q6s,Q7o,Q7s,Q8o,Q8s,"
           "Q9o,Q9s,QJo,QJs,QQ,QTo,QTs,T2s,T3s,T4s,T5s,T6s,T7s,T8o,T8s,T9o,T9s,TT")


def _norm_bb(spot, chips) -> float:
    """Engine chips -> big blinds (float). Spot stores raw chips; the solver scale we use IS big blinds."""
    return (chips or 0) / spot.bb


def _solver_label(action: str, amount_bb: float | None, node: dict) -> str | None:
    """Map an engine action (+ a bet-TO size in bb) to the solver child label at `node` (nearest size). Port of
    gto_oracle_match._match_label: the solver labels (BET/RAISE/ALLIN <to>) are in the SAME bb scale we solve at."""
    acts = (node.get("strategy", {}) or {}).get("actions", []) or list((node.get("childrens") or {}).keys())
    kind = {"check": "CHECK", "call": "CALL", "fold": "FOLD"}.get(action)
    if kind:
        return next((a for a in acts if a.split()[0] == kind), None)
    want = "RAISE" if action == "raise" else ("ALLIN" if action == "allin" else "BET")
    cands = [(a, float(a.split()[1])) for a in acts if a.split()[0] == want and len(a.split()) > 1]
    if not cands and want != "BET":                       # a raise with no RAISE child falls back to a BET-sized child
        cands = [(a, float(a.split()[1])) for a in acts if a.split()[0] == "BET" and len(a.split()) > 1]
    allin = next((a for a in acts if a.split()[0] == "ALLIN"), None)
    if not cands:
        return allin
    return min(cands, key=lambda c: abs(c[1] - (amount_bb or 0.0)))[0]


def _solve_key(board: list, oop_range: str, ip_range: str, pot_bb: float, stack_bb: float) -> str:
    """The cache key: board + bucketed pot + bucketed stack + RANGE signature. The range signature is REQUIRED because
    hero's own class is force-added per spot (solve_node), so the ranges are hand-dependent — keying on board+pot alone
    would hand back a stale solve built for a DIFFERENT hero hand on the same board."""
    return (f"{''.join(board)}|p{round(max(2.0, pot_bb) / _POT_BUCKET_BB)}"
            f"|s{round(max(2.0, stack_bb) / _STACK_BUCKET_BB)}|r{hash((oop_range, ip_range)) & 0xffffffff:08x}")


def _run_solve(board: list, oop_range: str, ip_range: str, pot_bb: float, stack_bb: float) -> dict | None:
    """Run ONE TexasSolver solve (no caching). UNIQUE tag per call (uuid) so concurrent solves never collide on the
    solver's `_oracle_in_<tag>.txt` / `_oracle_out_<tag>.json` temp files — the old `node{hash(key)}` tag COLLIDED for
    any two spots sharing the cache key bucket, letting parallel solves overwrite each other's input/output. None on any
    solver failure (the solver cleans its own temp files in a finally; a uuid tag means a crash leaks at most one pair)."""
    from pokerbot.strategy import gto_oracle as O
    try:
        return O.solve(board, oop_range, ip_range, pot=max(2.0, pot_bb), eff_stack=max(2.0, stack_bb),
                       accuracy=_SOLVE_ACC, max_iter=_SOLVE_ITERS, dump_rounds=1, threads=_SOLVE_THREADS,
                       tag=uuid.uuid4().hex, bets=_LEAN_BETS, timeout=_SOLVE_TIMEOUT)
    except Exception:  # noqa: BLE001
        return None


def _solve_board(board: list, oop_range: str, ip_range: str, pot_bb: float, stack_bb: float) -> dict | None:
    """Solve the board on the lean tree at the bb scale, CACHED + CONCURRENCY-SAFE. None on any solver failure.

    Thread-safe with per-key dedup: under `_CACHE_LOCK` we check the cache (hit -> return) then the in-flight map. The
    FIRST thread for a missing key registers an Event and solves it OUTSIDE the lock (so different keys solve in
    parallel); LATER threads for the SAME key find the Event, release the lock, and WAIT on it — then read the now-cached
    result. So same-key requests share ONE solve (no wasted duplicate ~6s solves, no temp-file race), different-key
    requests run concurrently."""
    key = _solve_key(board, oop_range, ip_range, pot_bb, stack_bb)
    while True:
        with _CACHE_LOCK:
            if key in _SOLVE_CACHE:                       # already solved (by us earlier or another thread) -> done
                return _SOLVE_CACHE[key]
            event = _SOLVE_INFLIGHT.get(key)
            if event is None:                             # we are the FIRST -> claim the key, solve it ourselves below
                event = threading.Event()
                _SOLVE_INFLIGHT[key] = event
                solver = True
            else:
                solver = False                            # another thread is solving this key -> wait for its result
        if solver:
            try:
                result = _run_solve(board, oop_range, ip_range, pot_bb, stack_bb)
                with _CACHE_LOCK:
                    _SOLVE_CACHE[key] = result            # publish the result (even None: cache the failure, don't retry)
                return result
            finally:
                with _CACHE_LOCK:
                    _SOLVE_INFLIGHT.pop(key, None)        # clear the in-flight slot AFTER caching ...
                event.set()                               # ... then wake the waiters (they now see the cache hit)
        else:
            event.wait(timeout=_SOLVE_TIMEOUT + 30)       # the solver thread will set() this; cap just over its timeout
            # loop: re-acquire the lock and read the cache (the solver published before set()). If the solver somehow
            # vanished without caching, `key` is back to missing + no in-flight -> we become the solver next iteration.


def _navigate(root: dict, spot) -> dict | None:
    """Walk the solver tree from the root (OOP first-to-act on the CURRENT street) along the CURRENT street's actions.
    Returns the node where hero is to act, or None if the line hits a missing/chance node (un-navigable).

    The solve roots on the CURRENT full board (`_solve_board(list(spot.board), ...)`), so the root is the current
    street's first-to-act. Walking PRIOR streets' actions would step into a `chance_node` (the board runout) and
    mis-navigate -> None: that bug made ONLY flop spots solve (turn/river NEVER did). We therefore navigate ONLY the
    current street's betting (no chance nodes occur within a single street) — mirroring gto_oracle_match._street_actions.
    """
    node = root
    current_street = [a for a in spot.line if a["street"] == spot.street]
    for a in current_street:
        lbl = _solver_label(a["action"], a.get("amount_bb"), node)
        child = (node.get("childrens") or {}).get(lbl) if lbl else None
        if not child or child.get("node_type") == "chance_node":
            return None
        node = child
    return node


def _with_class(range_str: str, hc: str) -> str:
    """`range_str` with hand-class `hc` guaranteed present (TexasSolver class notation, e.g. 'AKs'/'99'/'T9o').
    A no-op when hc is already in the range; otherwise appends it so the solver dumps a strategy for hero's EXACT
    hand. This is the RC1 force-add: the wide default ranges still miss ~20-40% of the hands the blueprint reaches,
    and on those hero's combo isn't in the acting node's range -> strategy_for None -> fall-back. Weighted-aware:
    range entries may be 'hc' OR 'hc:w' (the 2a line-aware ranges), so compare on the class token, not the raw entry."""
    classes = {p.split(":")[0] for p in range_str.split(",") if p}
    return range_str if hc in classes else f"{range_str},{hc}"


# ---- 2a: LINE-AWARE postflop starting ranges (derived from the preflop blueprint) -----------------------------------
# The fixed _HU_IP/_HU_OOP are SRP ranges applied to EVERY pot -> in a 3bet/4bet pot they are far too wide, so the solve
# optimises vs a wrong (too-loose) opponent range -> exploitable big-pot play (the measured postflop SPEW). Fix: derive
# the REACH-WEIGHTED range that actually enters the flop for the preflop line, from the blueprint. Gated behind
# POKERB_LINE_RANGES (default OFF) until the GTOW A/B confirms it beats the fixed ranges (the "never break the bot" gate).
_REACH_MIN = 0.005   # drop classes that take the line < 0.5% (negligible tail -> a leaner, correctly-weighted range)


def _all_classes() -> list:
    """All 169 hand classes in TexasSolver notation (13 pairs + 78 suited + 78 offsuit) — the reach-scan domain."""
    r = "AKQJT98765432"
    return ([a + a for a in r]
            + [r[i] + r[j] + "s" for i in range(13) for j in range(i + 1, 13)]
            + [r[i] + r[j] + "o" for i in range(13) for j in range(i + 1, 13)])


def _reach_range(steps: list) -> str:
    """A WEIGHTED TexasSolver range ('hc:w,...') = the classes reaching the flop via `steps`=[(node, action), ...], each
    weighted by the PRODUCT of its blueprint action-probabilities along the line. '' if the blueprint is unavailable.
    (Verified 2026-06-20: 3bet-pot BB(3bet) concentrates on premiums AA 1.0..22 0.03; SB(call) on mid-pairs.)"""
    from pokerbot.strategy import preflop_blueprint as pbp
    if not pbp.available():
        return ""
    out = []
    for hc in _all_classes():
        w = 1.0
        for node, action in steps:
            w *= (pbp.actions(node, hc) or {}).get(action, 0.0)
            if w <= 0.0:
                break
        if w >= _REACH_MIN:
            out.append(f"{hc}:{round(w, 4)}")
    return ",".join(out)


# preflop pot type -> (SB-side steps, BB-side steps). SB = the button = IN POSITION postflop; BB = OOP.
_LINE_STEPS = {
    "srp":  ([("ROOT", "open")],                   [("OPEN", "call")]),
    "3bet": ([("ROOT", "open"), ("3BET", "call")], [("OPEN", "3bet")]),
    "4bet": ([("ROOT", "open"), ("3BET", "4bet")], [("OPEN", "3bet"), ("4BET", "call")]),
}


def _classify_preflop(spot) -> str | None:
    """SRP / 3bet / 4bet pot from the preflop raise count. None = limped or 5bet+/jam (rare) -> use the wide defaults."""
    raises = sum(1 for a in spot.line if a.get("street") == "preflop" and a.get("action") in ("raise", "bet"))
    return {1: "srp", 2: "3bet", 3: "4bet"}.get(raises)


def _line_ranges(spot):
    """(oop_range, ip_range) for the preflop line, reach-weighted from the blueprint; None -> caller uses the wide
    defaults. SB(button)=IP, BB=OOP. Requires BOTH sides non-empty (never solve with an empty range)."""
    steps = _LINE_STEPS.get(_classify_preflop(spot) or "")
    if not steps:
        return None
    sb_steps, bb_steps = steps
    ip_r, oop_r = _reach_range(sb_steps), _reach_range(bb_steps)
    return (oop_r, ip_r) if (ip_r and oop_r) else None


def solve_node(spot) -> dict | None:
    """SEARCH AT INFERENCE: the solver's exact GTO action->prob mix for hero's hand at this spot, or None if the
    spot is UNSOLVABLE. The brain calls this to let a real solver decide postflop (it orchestrates, doesn't imitate).

    Solvable = postflop (street != preflop) AND heads-up (n_active == 2) AND a real board AND the solver is available.
    Ranges are the WIDE HU single-raised-pot defaults (_HU_IP=SB-open ~77%, _HU_OOP=BB-defend ~61%; v2 — inexact for
    3bet/limped/flop-narrowed pots, see the _HU_IP/_HU_OOP note) with hero's OWN class force-added so strategy_for no
    longer misses hero's hand. Returns {action: prob} with action in {fold,check,call,bet,raise,allin}; bet/raise carry
    a TOTAL size in bb. None on: preflop, n_active>2, an un-navigable line (off-tree/chance node), the solver
    unavailable/timed-out, or ANY exception (robust try/except -> None).
    """
    try:
        from pokerbot.strategy import gto_oracle as O
        if spot.street == "preflop" or spot.n_active != 2 or len(spot.board) < 3 or not O.available():
            return None
        # Ranges = the WIDE HU SRP defaults (button=IP, non-button=OOP) with hero's OWN class force-added to hero's
        # side. The solver only dumps a strategy for hands in the ACTING node's range, and the wide defaults still miss
        # ~20-40% of the hands the blueprint reaches -> strategy_for None -> fall-back (the #1 coverage gap). Hero's
        # IP/OOP role comes from NAVIGATION (the line); the same role here picks which side gets the force-add.
        hc = hand_class_of(spot.hero_hole)
        hero_ip = spot.hero_pos in ("BTN", "SB")             # HU: the button (SB) is in position postflop
        lr = _line_ranges(spot) if os.environ.get("POKERB_LINE_RANGES", "0") == "1" else None   # 2a (gated); None=defaults
        base_oop, base_ip = lr if lr else (_HU_OOP, _HU_IP)  # line-aware reach ranges, else the wide SRP defaults (unchanged)
        oop_range = base_oop if hero_ip else _with_class(base_oop, hc)
        ip_range = _with_class(base_ip, hc) if hero_ip else base_ip
        active = [_norm_bb(spot, s["stack"]) for s in spot.seats if not s.get("folded")]
        stack_bb = min(active) if active else 100.0          # effective = the SHORTER remaining stack -> the subgame SPR
        root = _solve_board(list(spot.board), oop_range, ip_range, _norm_bb(spot, spot.pot), stack_bb)
        if not root:
            return None
        node = _navigate(root, spot)
        if node is None:
            return None
        hole = spot.hero_hole
        strat = O.strategy_for(node, hole[0], hole[1])    # {solver_label: prob} or None if hero's combo isn't in range
        if not strat:
            return None
        # Re-key solver labels (CHECK/CALL/FOLD/BET <to>/RAISE <to>/ALLIN <to>) -> our verbs; size = TOTAL bet in bb.
        out: dict = {}
        for lbl, p in strat.items():
            parts = lbl.split()
            kind = parts[0]
            verb = {"CHECK": "check", "CALL": "call", "FOLD": "fold",
                    "BET": "bet", "RAISE": "raise", "ALLIN": "allin"}.get(kind)
            if verb is None:
                continue
            out[verb] = out.get(verb, 0.0) + max(0.0, float(p))
        total = sum(out.values())
        if total <= 0:
            return None
        norm = {a: v / total for a, v in out.items()}
        # Attach the solver's TOTAL bet/raise size (bb) per verb so the caller can legalize it. The lean tree can dump
        # SEVERAL labels for one verb (e.g. BET 66%-pot AND BET allin both serialize as "BET <to>"); pick the
        # PROBABILITY-WEIGHTED size among that verb's labels = the size the solver actually wants. ALLIN -> no size.
        size_num, size_den = {}, {}
        for lbl, p in strat.items():
            parts = lbl.split()
            if parts[0] in ("BET", "RAISE") and len(parts) > 1:
                v = parts[0].lower()
                size_num[v] = size_num.get(v, 0.0) + max(0.0, float(p)) * float(parts[1])   # solver scale == bb
                size_den[v] = size_den.get(v, 0.0) + max(0.0, float(p))
        norm["_sizes_bb"] = {v: (size_num[v] / size_den[v] if size_den[v] > 0 else max(
            float(lbl.split()[1]) for lbl in strat if lbl.split()[0] == v.upper() and len(lbl.split()) > 1))
            for v in size_num}                                     # private hint; callers read it, never normalize over it
        return norm
    except Exception:  # noqa: BLE001 — robust by contract: any failure -> unsolvable, never crash the brain
        return None


# ---------------------------------------------------------------- legality (the engine = truth)
# Brain-path GTO-tree sizing (POKERB_BRAIN_ONTREE, default OFF). The brain BYPASSES bot.py::_raise_to, so its bets are
# OFF GTOW's tree (measured 2026-06-29: ~15% on-tree, continuous ~0.60x pot, vs the engine's 100%). When ON, snap a
# first-in postflop BET to the tree {0.33,0.5,0.75,1,1.25}x pot (mirrors the engine ONTREE; never a jam/overbet) ->
# brain sizes become GTOW-tree-aligned (more gradeable + on the GTO reference tree). A/B-gated vs the −41 AIVAT.
BRAIN_ONTREE = os.environ.get("POKERB_BRAIN_ONTREE", "0") == "1"


def legalize(spot, action: str, size_bb: float | None = None):
    """Coerce (action, size_bb) to a LEGAL (action, amount_chips) for `spot`. amount = total bet in CHIPS for
    bet/raise; None for fold/check/call/all-in. Falls back safely (check>call>fold) for an illegal request."""
    a = (action or "").lower()
    L = spot.legal
    if a in ("bet", "raise", "allin", "all-in"):
        if not L.get("can_raise"):
            return ("check", None) if L.get("can_check") else (("call", None) if L.get("can_call") else ("fold", None))
        if a in ("allin", "all-in") or size_bb is None:
            return ("allin", None)
        target = int(round(size_bb * spot.bb))
        if (BRAIN_ONTREE and spot.street in ("flop", "turn", "river") and spot.to_call == 0
                and spot.pot > 0 and target <= 2.0 * spot.pot):            # first-in postflop bet, not a jam/overbet
            from pokerbot.strategy.postflop import snap_to_tree            # lazy: avoid an import cycle at module load
            target = snap_to_tree(target, spot.pot)
        target = max(L.get("raise_min") or target, min(target, L.get("raise_max") or target))
        return ("raise", target)
    if a == "fold":
        return ("fold", None) if L.get("can_fold") else ("check", None)
    if a == "call":
        return ("call", None) if L.get("can_call") else ("check", None)
    if a == "check":
        return ("check", None) if L.get("can_check") else (("call", None) if L.get("can_call") else ("fold", None))
    return ("check", None) if L.get("can_check") else (("call", None) if L.get("can_call") else ("fold", None))
