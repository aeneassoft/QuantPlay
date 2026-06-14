"""Translation layer between our poker ENGINE (numbers) and the LANGUAGE model in the loop.

Two directions:
  * describe_spot(state, opp_stats) -> str : engine facts -> the poker NATURAL-LANGUAGE a coach would
    use (texture, hand class, position/initiative, SPR, pot-odds/MDF, opponent stats). LLMs reason well
    over THIS, not over raw card bits — so we hand them the computed picture, never ask them to do math.
  * directive_to_change(directive) -> dict : the LLM's JSON exploit directive (from
    meta_coach.propose_exploit) -> a concrete, machine-checkable param/node-lock change the benchmark
    can GROUND. The LLM proposes in language; the engine verifies in numbers.

Pipeline: describe_spot --(prose)--> propose_exploit --(JSON)--> directive_to_change --(param)--> benchmark.
"""
from __future__ import annotations

from pokerbot.engine.cards import hand_class
from pokerbot.engine.evaluator import best_five_name
from pokerbot.strategy import preflop_strength as ps
from pokerbot.strategy.postflop import classify_board


def describe_spot(state: dict, opp_stats: dict | None = None) -> str:
    hero = state.get("hero", 0)
    hole = state["players"][hero]["hole"]
    board = state.get("board", [])
    la = state.get("legal", {})
    pot, to_call = la.get("pot", 0), la.get("to_call", 0)
    out = []

    if board:
        tex = classify_board(board)
        tags = [k for k in ("paired", "monotone", "two_tone", "connected") if tex.get(k)]
        out.append(f"Flop/board {''.join(board)} ({', '.join(tags) or 'dry, rainbow'}).")
        out.append(f"Our hand {hole[0]}{hole[1]} = {best_five_name(board, hole)}.")
    else:
        hc = hand_class(*hole)
        out.append(f"Preflop. Our hand {hc} (~top {100 * (1 - ps.percentile(hc)):.0f}%).")

    aggr = state.get("aggressor")
    out.append("We have the initiative (preflop aggressor)." if aggr
               else ("We are the caller, no initiative." if aggr is False else ""))
    out.append(f"Pot {pot}" + (f", {to_call} to call." if to_call else ", checked to us — we can bet."))
    if to_call:
        req = to_call / (pot + to_call)
        out.append(f"We need {req:.0%} equity to call; MDF vs this bet = {pot / (pot + to_call):.0%}.")

    if opp_stats:
        labels = {"vpip": "VPIP", "pfr": "PFR", "threebet": "3bet%", "fold_to_bet": "fold-to-bet",
                  "fold_to_cbet": "fold-to-cbet", "aggression": "aggression", "wtsd": "WTSD"}
        bits = [f"{labels[k]} {v:.0%}" if isinstance(v, float) else f"{labels[k]} {v}"
                for k, v in opp_stats.items() if k in labels and v is not None]
        if bits:
            out.append("Villain (from public actions only): " + ", ".join(bits) + ".")
    return " ".join(p for p in out if p)


# LLM strategic verb -> concrete baseline param + sign of the freq_delta (the v1 compiler target).
# (With a node-lock-capable solver, the same directive also maps to a locked-node freq shift.)
_VERB = {
    "bluff_more":        ("cbet_bluff", +1),
    "value_bet_thinner": ("cbet_eq", -1),    # lower the value threshold -> bet thinner
    "raise_more":        ("cbet_eq", -1),
    "fold_more":         ("call_delta", +1),
    "call_wider":        ("call_delta", -1),
}


def directive_to_change(directive: dict) -> dict:
    """Compile the LLM directive into a bounded, machine-checkable change. The benchmark grounds it."""
    adj = directive.get("adjust", {})
    verb = adj.get("action")
    delta = abs(float(adj.get("freq_delta", 0) or 0))
    delta = min(delta, 0.3)                                   # hard clamp — bounded exploitation
    m = _VERB.get(verb)
    if not m:
        return {"ok": False, "note": f"unknown action '{verb}'"}
    param, sign = m
    return {"ok": True, "param_delta": {param: round(sign * delta, 3)}, "target": directive.get("target"),
            "confidence": directive.get("confidence"), "note": f"{verb} -> {param} {sign * delta:+.2f}"}


def main() -> None:
    # demo the full bridge on one spot (IP aggressor on a dry K72 vs a station)
    state = {"hero": 0, "board": ["Ks", "7h", "2d"], "aggressor": True,
             "players": [{"hole": ["As", "Qd"], "committed_street": 0}],
             "legal": {"pot": 600, "to_call": 0, "can_check": True, "can_raise": True}}
    opp = {"vpip": 0.42, "pfr": 0.12, "fold_to_cbet": 0.66, "aggression": 0.18, "wtsd": 0.41}
    prose = describe_spot(state, opp)
    print("ENGINE -> LANGUAGE:\n  " + prose + "\n")
    sample_directive = {"reasoning": "fold-to-cbet 66% + low aggression = level-0 over-folder; attack.",
                        "level": 0, "target": {"street": "flop", "facing": "check"},
                        "adjust": {"action": "bluff_more", "freq_delta": 0.15}, "confidence": 0.6}
    print("LANGUAGE -> ENGINE (directive_to_change):\n  " + str(directive_to_change(sample_directive)))


if __name__ == "__main__":
    main()
