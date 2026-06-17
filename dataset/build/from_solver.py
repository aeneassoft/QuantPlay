"""Solver-grounded MIXED-strategy SFT data (Pillar 2, docs/full_gpu_load.md / the GTO plan). TexasSolver (OSS,
Discounted-CFR-class, CPU, $0) solves a postflop spot exactly and dumps the GTO action FREQUENCIES — exactly the
mixed, multi-size targets representation-v2 needs (hand-written formulas can't express a 60/40 check-bet split). Each
solved hand -> a canonical Spot -> a `decide_mix({...}, size=)` program whose mix IS the solver's ground truth.

This is WARM-START distillation from the gold-standard teacher (CLAUDE.md CLEAN BOUNDARY: SFT/distillation = warm-start;
the solver is the best possible teacher). The program stays ENGINE-GROUNDED (an `api.equity` call before the commit) so
the grounded-rate metric + the program-of-thought contract hold; the mix VARIES with the spot (board/hand) so it is a
learnable spot->mix mapping, not a constant. Multi-size bets are aggregated to our 6-action DSL vocab with a
prob-weighted representative size (per-action-size mixes = a noted follow-up once decide_mix carries sizes per key).

Run: python -m dataset.build.from_solver            # solve the built-in board set -> dataset/shards/solver.jsonl
"""
from __future__ import annotations

import json

from pokerbot import config
from pokerbot.brain import api as _api
from pokerbot.brain.dsl_grammar import matches
from pokerbot.brain.format_spot import Spot, format_spot
from pokerbot.strategy import gto_oracle as O
from dataset.schema import make_example

BB = 100                       # chips per bb (engine convention)
POT_BB = 20.0                  # single-raised-pot-ish flop pot (bb)
EFF_BB = 100.0                 # effective stack (bb)
MIN_PROB = 0.02                # drop solver actions below 2% (noise floor)

# Representative single-raised-pot flops (dry / wet / paired / monotone / high / low) with standard BTN(ip)-vs-BB(oop)
# 100bb ranges. The OOP first-to-act ROOT node = a check/bet mixed decision = the cleanest solver-mix to distil.
# Ranges are ENUMERATED (TexasSolver v0.2.0 rejects the '22+'/'A2s+' shorthand -> "format not recognize"; verified).
_BB_DEF = ("22,33,44,55,66,77,88,99,TT,JJ,QQ,KK,AA,"
           "A2s,A3s,A4s,A5s,A6s,A7s,A8s,A9s,ATs,AJs,AQs,AKs,K5s,K6s,K7s,K8s,K9s,KTs,KJs,KQs,"
           "Q8s,Q9s,QTs,QJs,J8s,J9s,JTs,T8s,T9s,97s,98s,86s,87s,75s,76s,65s,54s,"
           "A8o,A9o,ATo,AJo,AQo,AKo,KTo,KJo,KQo,QTo,QJo,JTo")             # BB defend range
_BTN_OR = ("22,33,44,55,66,77,88,99,TT,JJ,QQ,KK,AA,"
           "A2s,A3s,A4s,A5s,A6s,A7s,A8s,A9s,ATs,AJs,AQs,AKs,K7s,K8s,K9s,KTs,KJs,KQs,"
           "Q9s,QTs,QJs,J9s,JTs,T8s,T9s,98s,87s,76s,65s,54s,"
           "A7o,A8o,A9o,ATo,AJo,AQo,AKo,K9o,KTo,KJo,KQo,Q9o,QTo,QJo,J9o,JTo,T9o")   # BTN open range
_BOARDS = [
    ["Ah", "7d", "2c"],   # dry, ace-high
    ["Ks", "Qd", "5h"],   # two broadway
    ["9h", "8d", "7c"],   # wet, connected
    ["Jc", "Jd", "4s"],   # paired
    ["Qh", "9h", "4h"],   # monotone
    ["5s", "4d", "2h"],   # low, dynamic
    ["Td", "6s", "2c"],   # dry, ten-high
    ["As", "Ks", "Qh"],   # high, connected broadway
]


def _frac_of_range(range_str: str) -> float:
    """Rough fraction-of-all-hands of a TexasSolver range string -> the api.range_top(frac) prior used as the equity
    context in the emitted program (the mix itself is the solver target; eq is grounding context)."""
    n_combos = 0.0
    for tok in range_str.split(","):
        tok = tok.strip()
        if not tok:
            continue
        if tok.endswith("+") or "s" in tok or "o" in tok:
            n_combos += 8        # rough avg combos per class token
        else:
            n_combos += 6
    return max(0.05, min(0.9, round(n_combos / 1326.0 * 4, 2)))   # scaled heuristic; bucketed by round()


def _map_mix(strat: dict, eff_bb: float) -> tuple[dict, float | None]:
    """Solver {action_str: prob} -> (our-6-action mix dict, representative bet/raise size in bb). Aggregates multi-size
    bets; classifies a near-stack bet as all-in. Drops sub-MIN_PROB noise, renormalizes."""
    mix: dict[str, float] = {}
    sized: list[tuple[float, float]] = []                  # (size_bb, prob) for bet/raise -> weighted representative size
    for a, p in strat.items():
        if p < MIN_PROB:
            continue
        parts = a.split()
        verb = parts[0].upper()
        size = float(parts[1]) if len(parts) > 1 else None
        if verb == "CHECK":
            mix["check"] = mix.get("check", 0.0) + p
        elif verb == "FOLD":
            mix["fold"] = mix.get("fold", 0.0) + p
        elif verb == "CALL":
            mix["call"] = mix.get("call", 0.0) + p
        elif verb in ("BET", "RAISE"):
            if size is not None and size >= 0.95 * eff_bb:           # a near-stack sizing = all-in
                mix["allin"] = mix.get("allin", 0.0) + p
            else:
                key = "bet" if verb == "BET" else "raise"
                mix[key] = mix.get(key, 0.0) + p
                if size is not None:
                    sized.append((size, p))
        elif verb in ("ALLIN", "ALL-IN", "ALL_IN"):
            mix["allin"] = mix.get("allin", 0.0) + p
    tot = sum(mix.values())
    if tot <= 0:
        return {}, None
    mix = {k: round(v / tot, 3) for k, v in mix.items() if v / tot >= MIN_PROB}
    tot2 = sum(mix.values())
    mix = {k: round(v / tot2, 3) for k, v in mix.items()}          # renormalize after the floor drop
    size_bb = round(sum(s * p for s, p in sized) / sum(p for _, p in sized), 1) if sized else None
    return mix, size_bb


def _spot(board: list, hole: list, pot_bb: float, eff_bb: float, hero_pos: str = "BB") -> Spot:
    """A canonical OOP first-to-act postflop Spot (to_call=0 -> check/bet legal) for the solved node."""
    pot = int(round(pot_bb * BB))
    eff = int(round(eff_bb * BB))
    street = {3: "flop", 4: "turn", 5: "river"}[len(board)]
    villain_pos = "BTN" if hero_pos != "BTN" else "CO"
    seats = [{"seat": 0, "pos": hero_pos, "stack": eff, "committed_total": 0, "folded": False, "all_in": False},
             {"seat": 1, "pos": villain_pos, "stack": eff, "committed_total": 0, "folded": False, "all_in": False}]
    legal = {"can_fold": False, "can_check": True, "can_call": False, "can_raise": True,
             "raise_min": BB, "raise_max": eff}
    return Spot(street=street, board=list(board), bb=BB, hero_seat=0, hero_pos=hero_pos, hero_hole=list(hole),
                pot=pot, to_call=0, n_active=2, seats=seats, legal=legal, line=[])


def _program(mix: dict, size_bb: float | None, frac: float) -> str:
    """Engine-grounded program whose committed mix IS the solver target (equity computed as grounding context)."""
    mix_repr = "{" + ", ".join(f"'{k}': {v}" for k, v in mix.items()) + "}"
    size_arg = f", size={size_bb}" if (size_bb is not None and ("bet" in mix or "raise" in mix)) else ""
    return ("# GTO solver target mix (TexasSolver, range vs range) — distil the exact frequencies\n"
            f"vr = api.range_top({frac})\n"
            "eq = api.equity(spot.hero_hole, vr, spot.board)\n"
            f"decide_mix({mix_repr}{size_arg})")


def build(boards=None, oop_range: str = _BB_DEF, ip_range: str = _BTN_OR, pot_bb: float = POT_BB,
          eff_bb: float = EFF_BB, accuracy: float = 0.3, max_iter: int = 120, timeout: int = 200):
    """Solve each board, distil the OOP root-node mixed strategy for every hand in range -> grammar-valid examples."""
    if not O.available():
        raise FileNotFoundError("TexasSolver console binary not found (pokerbot/strategy/gto_oracle.py)")
    boards = boards or _BOARDS
    frac = _frac_of_range(ip_range)                               # opponent (IP) continuing range as the equity prior
    for board in boards:
        try:
            node = O.solve(board, oop_range, ip_range, pot=pot_bb, eff_stack=eff_bb,
                           accuracy=accuracy, max_iter=max_iter, dump_rounds=1, timeout=timeout)
        except Exception as e:  # noqa: BLE001 — a single board failing must not kill the shard
            print(f"  board {board} solve FAILED: {type(e).__name__}: {e}", flush=True)
            continue
        keyed = O._key(node)                                      # {frozenset(combo): probs}
        actions = (node.get("strategy") or {}).get("actions", [])
        if not keyed or not actions:
            print(f"  board {board}: empty dump (player={node.get('player')}) — skip", flush=True)
            continue
        for combo in keyed:
            c1, c2 = tuple(combo)
            strat = O.strategy_for(node, c1, c2)
            if not strat:
                continue
            mix, size_bb = _map_mix(strat, eff_bb)
            if len(mix) < 1:
                continue
            spot = _spot(board, [c1, c2], pot_bb, eff_bb)
            prog = _program(mix, size_bb, frac)
            if not matches(prog):                                # never emit a non-grammar program into the gold
                continue
            top = max(mix, key=mix.get)
            yield make_example("solver", format_spot(spot), prog,
                               action={"action": top, "size_bb": size_bb if top in ("bet", "raise") else None},
                               type_="decision",
                               meta={"solver": True, "board": "".join(board), "mix": mix, "n_actions": len(mix)})


def main():
    import sys
    from collections import Counter
    rows = list(build())
    out = config.ROOT / "dataset" / "shards" / "solver.jsonl"
    with open(out, "w", encoding="utf-8") as f:
        for ex in rows:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} solver-mixed decisions -> {out}")
    mixed = sum(1 for e in rows if e["meta"]["n_actions"] >= 2)
    print(f"  genuinely MIXED (>=2 actions): {mixed}/{len(rows)} ({mixed / max(1, len(rows)):.0%})")
    print("  top-action mix:", dict(Counter(e["action"]["action"] for e in rows)))


if __name__ == "__main__":
    main()
