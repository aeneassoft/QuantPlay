"""REASONING-LOOP decision SFT examples (docs/plans/llm_curriculum.md). Each completion is a GENUINE program-of-thought where
the action is DERIVED from engine computation (equity vs the price) via CONTROL FLOW — not a hardcoded decide() with
decorative comments. (The old form computed `req` then ignored it: the reasoning was DEAD CODE, the decision memorized
— so nothing the model "reasoned" influenced the action. User directive 2026-06-17: everything the LLM emits must drive
the decision in a real reasoning loop.) The model learns the LOOP (compute -> branch -> act); RL/realized-EV then
optimizes the thresholds + ranges. No rollouts (cheap: one MC-equity per spot). Local, no HF.

Run: python -m dataset.build.from_selfplay [n=800]
"""
from __future__ import annotations

import json

from pokerbot import config
from pokerbot.brain import api as _api
from pokerbot.brain import modes
from pokerbot.brain.dsl_grammar import matches
from pokerbot.brain.format_spot import format_spot
from dataset.schema import make_example
from training.rl_env import TRAIN_LEAGUE, gen_decision_states

# villain CONTINUING-range WIDTH by preflop aggression = the LLM's READ (a prior; RL refines). Emitted COMPACTLY as
# api.range_top(frac) (NOT a long literal list) -> a short program that fits the RL token budget AND keeps the
# downstream read-branch salient (the 12-19-class literal list overflowed FAST=160 + the 1.7B dropped the read-branch).
RAISE_EDGE = 0.20      # equity margin OVER the price to raise for value (a prior; RL tunes)
BET_BAR = 0.60         # equity bar to bet when checked to (a prior; RL tunes)


def _villain_frac(spot) -> float:
    raises = sum(1 for a in spot.line if a.get("street") == "preflop" and a.get("action") in ("bet", "raise", "allin"))
    return 0.10 if raises >= 2 else (0.18 if raises == 1 else 0.40)


def _derive(spot, frac):
    """The reasoning-loop program + the action it DERIVES + a clarity score. The villain range is emitted COMPACTLY as
    `api.range_top(frac)` (a short program -> fits the RL token budget + keeps the read-branch salient)."""
    # PREFLOP (HU): emit the EXACT near-Nash HU-200bb blueprint mix as a DICT LITERAL (the grammar requires a literal,
    # not decide_mix(var); same proven form as from_solver). The equity-logic below OVER-FOLDS preflop (the −41 bb/hand
    # GTOW leak). preflop_solve is n_active==2-gated, so this only fires for HU spots that map to a blueprint node; the
    # rest fall through to equity-logic. (Spots that DON'T map at gen-time still get the blueprint at GTOW inference,
    # where spot_from_slumbot maps ~100% — but for the GOLD we need a literal, so we emit only the mapped ones.)
    if spot.street == "preflop":
        pm = _api.preflop_solve(spot)
        if pm:
            sizes = pm.get("_sizes_bb") or {}
            mix = {k: round(float(v), 3) for k, v in pm.items() if k != "_sizes_bb" and float(v) > 0.01}
            if mix:
                modal = max(mix, key=mix.get)
                size = sizes.get("raise") if any(a in mix for a in ("raise", "bet", "allin")) else None
                size_arg = f", size={size}" if size else ""
                mix_repr = "{" + ", ".join(f"'{k}': {v}" for k, v in mix.items()) + "}"
                prog = ("# preflop: the EXACT near-Nash HU-200bb blueprint mix (api.preflop_solve), not equity-logic\n"
                        f"decide_mix({mix_repr}{size_arg})")
                return prog, modal, (size if modal in ("raise", "bet", "allin") else None), max(mix.values())
    pot_bb = spot.b(spot.pot)
    vr = _api.range_top(frac)
    eq = float(_api.equity(spot.hero_hole, vr, spot.board))
    if spot.to_call <= 0:                                    # checked to us: MIX value-bet / check
        bet = round(max(1.0, 0.6 * pot_bb), 1)
        role = "ip" if spot.hero_pos in ("BTN", "CO") else "oop"
        # POSTFLOP: PREFER the TRAINED flop/turn/river GTO advisor (api.solver_freq) over raw equity — the consult+repo
        # finding: the advisors (+46% turn) were our underused gold, never wired into the emitted DSL. Wire it here.
        f_val = _api.solver_freq(spot.hero_hole, spot.board, role, spot.street) if spot.board else None
        if f_val is not None:
            prog = (f"# postflop: PREFER the trained GTO bet-frequency advisor; fall back to equity\n"
                    f"f = api.solver_freq(spot.hero_hole, spot.board, '{role}', '{spot.street}')\n"
                    f"vr = api.range_top({frac})\n"
                    f"eq = api.equity(spot.hero_hole, vr, spot.board)\n"
                    f"if f is not None and f >= 0.5:\n    decide_mix({{'bet': 0.8, 'check': 0.2}}, size={bet})\n"
                    f"elif f is not None:\n    decide_mix({{'check': 0.8, 'bet': 0.2}}, size={bet})\n"
                    f"elif eq >= {BET_BAR}:\n    decide_mix({{'bet': 0.75, 'check': 0.25}}, size={bet})\n"
                    f"else:\n    decide_mix({{'check': 0.85, 'bet': 0.15}})")
            action, size = ("bet", bet) if f_val >= 0.5 else ("check", None)
            clarity = abs(f_val - 0.5)
        else:                                                # preflop / advisor uncovered: the equity form
            prog = (f"# read: no bet to face; MIX value-bet vs check by equity (a frequency, not a pure line)\n"
                    f"vr = api.range_top({frac})\n"
                    f"eq = api.equity(spot.hero_hole, vr, spot.board)\n"
                    f"if eq >= {BET_BAR}:\n    decide_mix({{'bet': 0.8, 'check': 0.2}}, size={bet})\n"
                    f"else:\n    decide_mix({{'check': 0.85, 'bet': 0.15}}, size={bet})")
            action, size, clarity = ("bet" if eq >= BET_BAR else "check"), (bet if eq >= BET_BAR else None), abs(eq - BET_BAR)
    else:                                                    # facing a bet: MIX raise / call / fold by equity vs price
        req = float(_api.required_equity(spot.to_call, spot.pot))
        raise_to = round(pot_bb + 2.0 * spot.b(spot.to_call), 1)
        prog = (f"# read: MIX by equity vs the price, and EXPLOIT the table — a folder turns our air into a bluff-raise\n"
                f"vr = api.range_top({frac})\n"
                f"eq = api.equity(spot.hero_hole, vr, spot.board)\n"
                f"req = api.required_equity(spot.to_call, spot.pot)\n"
                f"if eq >= req + {RAISE_EDGE}:\n    decide_mix({{'raise': 0.75, 'call': 0.25}}, size={raise_to})\n"
                f"elif eq >= req:\n    decide_mix({{'call': 0.8, 'raise': 0.2}}, size={raise_to})\n"
                f"elif spot.villain_fold >= 0.6:\n    decide_mix({{'raise': 0.55, 'fold': 0.45}}, size={raise_to})\n"
                f"else:\n    decide_mix({{'fold': 0.8, 'call': 0.2}})")
        if eq >= req + RAISE_EDGE:
            action, size = "raise", raise_to
        elif eq >= req:
            action, size = "call", None
        elif spot.villain_fold >= 0.6:                       # bounded exploit: bluff-raise air vs an over-folder
            action, size = "raise", raise_to
        else:
            action, size = "fold", None
        clarity = min(abs(eq - req), abs(eq - (req + RAISE_EDGE)))
    return prog, action, size, clarity


def build(n: int = 800, seed: int = 0, hero_seat: int = 0, profiles=TRAIN_LEAGUE):
    import random
    modes.set_mode("fast")                                   # cheap MC equity for data gen
    rd = random.Random(seed + 777)
    for i, (snap, spot) in enumerate(gen_decision_states(profiles=profiles, hero_seat=hero_seat,
                                                         n_states=n, seed=seed)):
        # synthetic opponent READ (~40% non-neutral) — teaches the CONDITIONING form; live the read comes from the
        # session opp-model. Skewed to neutral so most spots stay the robust baseline ("which-GTO-here" is data-driven).
        if rd.random() < 0.4:
            spot.villain_fold = rd.choice([0.3, 0.7])
            spot.villain_aggro = rd.choice([0.3, 0.7])
        frac = _villain_frac(spot)
        prog, action, size, clarity = _derive(spot, frac)
        if not matches(prog):                               # never emit a non-grammar program into the gold
            continue
        yield make_example("selfplay", format_spot(spot), prog,
                           action={"action": action, "size_bb": size}, type_="decision",
                           meta={"derived": True, "clarity": round(clarity, 3), "villain_fold": spot.villain_fold})


def main():
    import sys
    from collections import Counter
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 800
    rows = list(build(n=n))
    out = config.ROOT / "dataset" / "shards" / "decisions.jsonl"
    with open(out, "w", encoding="utf-8") as f:
        for ex in rows:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} reasoning-loop decisions -> {out}")
    print("action mix:", dict(Counter(e["action"]["action"] for e in rows)))


if __name__ == "__main__":
    main()
