"""River-corset frontier consult (user-directed): OpenAI for the MATH/CONCEPTS -> Claude for the TECHNICAL mapping.

Grounded trigger: the re-SFT'd GLM scored -94.14 bb/100 vs GTO Wizard, but the per-hand log shows the ENTIRE loss is
~10 RIVER hands where the bot CALLS huge overbets (villain bets ~51bb into a ~20bb pot -> bot calls -> -40bb); the other
~90 hands are ~break-even. So the leak is a river over-call / mis-sized-bet spew. The user wants an engine-defined RIVER
CORSET that bounds the LLM. Run: python -m research.river_consult
"""
from __future__ import annotations

import json

from pokerbot import config
from research.llm import ask_claude, openai_json

_CONTEXT = """\
SYSTEM UNDER TEST: a heads-up No-Limit Hold'em bot at 200bb. An LLM "brain" (a fine-tuned GLM-9B) drives a deterministic
poker ENGINE via program-of-thought: it emits Python calling engine APIs (equity, required_equity, mdf, pot_odds, spr,
board_texture, hand_rank, a TexasSolver node-solve) and the engine executes an exact legal action. Measured vs GTO Wizard
(a near-optimal solver opponent, AIVAT luck-adjusted): -94.14 bb/100 over 100 hands.

GROUNDED DIAGNOSIS (per-hand log): the loss is NOT pervasive. The worst 10 hands = ~103% of the total loss; the other
~90 hands are ~break-even. ~9 of those disasters are on the RIVER and are the bot CALLING a huge bet/overbet — e.g.,
villain bets b5100 (~51bb) into a ~20bb pot and the bot CALLS and loses ~40bb. So the bot's river BLUFF-CATCHING /
over-calling vs large bets is the spew. On most hands it plays fine.

HUMAN/OPERATOR INSIGHTS to evaluate + formalize (the user is an experienced player; treat as hypotheses to make rigorous):
1. The engine still carries a 'bet enough that the opponent folds' (fold-equity-maximizing) principle. The user argues
   this is WRONG at the river: the river is where VALUE is realized, real opponents (and a GTO opponent) do not over-fold,
   so river betting should be value + balanced bluffs (EV-driven), NOT sized to generate folds.
2. The LLM is partly trained on human/Reddit data, where an ALL-IN carries emotional/dramatic weight. For a bot an all-in
   is PURELY a mathematical EV decision (no drama). The corset must strip that human bias.
3. The user proposes: at the river, maybe do NOT try to estimate the opponent's exact range; instead anchor on OUR OWN
   UNEXPLOITABILITY — the minimum-defense-frequency derived from the (fixed) card-dealing distribution — so we cannot be
   exploited by bluffs/overbets regardless of the opponent's actual holding.
4. Commitment bias (context only, NOT our leak): humans who are already big-invested call river all-ins even when -EV.
"""

_ASK = """\
Give the rigorous MATH and CONCEPTS for an ENGINE-DEFINED RIVER CORSET that bounds the LLM so it can NEVER spew (call an
overbet it cannot profitably call), while staying UNEXPLOITABLE (not over-folding). Be exact and complete — the engine
will fact-check every formula. For each field, give the precise formulas with derivations and concrete thresholds.

- river_call_discipline: the exact bluff-catcher math facing a bet of size B into pot P, INCLUDING overbets (B > P).
  Required equity to call = B/(P+2B)? derive it. The minimum-defense-frequency (MDF = P/(P+B)) and what it bounds. The
  bluff-catcher indifference. State the precise rule: GIVEN our hand's equity vs a reasonable/worst-case value-or-bluff
  range, when MUST we fold vs an overbet, and what is the unexploitable CALL frequency so we are not exploited by bluffs.
- river_bet_discipline: GTO river betting for a polarized range — value-bet + balanced-bluff sizing; the bluff-to-value
  ratio as a function of bet size (r = B/(P+B)? derive); why 'bet to make them fold' is wrong at the river; framing
  all-in as pure EV (= sum over outcomes of prob*stack-delta), with NO behavioral premium.
- unexploitability_vs_range: rigorously evaluate insight #3 (anchor on MDF / our unexploitable defense from the fixed
  card distribution vs estimating villain's exact range). When is each correct (GTO/unexploitable play vs a deliberate,
  bounded exploit)? Which should the CORSET anchor on, and why.
- corset_rules: the concrete, DETERMINISTIC rules + numeric thresholds the engine can ENFORCE on top of the LLM's
  proposed river action, so the ~10 spew hands cannot happen (a call-fold bound by required-equity, a bet-size/over-bet
  cap, a value/bluff-frequency bound). Make them implementable as guards.
- key_formulas: a compact list of the exact formulas (required_equity, MDF, bluff:value ratio, EV-of-call, EV-of-shove).
"""

RIVER_SCHEMA = {
    "type": "object",
    "properties": {
        "river_call_discipline": {"type": "string"},
        "river_bet_discipline": {"type": "string"},
        "unexploitability_vs_range": {"type": "string"},
        "corset_rules": {"type": "string"},
        "key_formulas": {"type": "string"},
    },
    "required": ["river_call_discipline", "river_bet_discipline", "unexploitability_vs_range",
                 "corset_rules", "key_formulas"],
    "additionalProperties": False,
}

OPENAI_SYS = ("You are a world-class No-Limit Hold'em game-theory mathematician (CFR / GTO / exploitability). Rigor over "
              "prose: derive formulas, state exact thresholds, no hand-waving. The engine fact-checks your math.")
CLAUDE_SYS = ("You are a senior engineer on THIS poker codebase. Turn the provided GTO math into an EXACT, minimal, "
              "deterministic implementation. Cite concrete files/functions; prefer reusing existing engine APIs.")


def main():
    print(">>> OpenAI (math/concepts) ...", flush=True)
    data, (oi, oo) = openai_json(OPENAI_SYS, _CONTEXT + "\n\n" + _ASK, RIVER_SCHEMA, "river_corset")
    print(f"  OpenAI done ({oi}+{oo} tok)\n", flush=True)
    for k, v in data.items():
        print(f"\n===== OPENAI: {k} =====\n{v}", flush=True)

    claude_user = (
        _CONTEXT
        + "\n\nA GTO mathematician produced the following river-corset math/concepts (JSON). Map it to our codebase as a "
          "DETERMINISTIC RIVER CORSET — a bounded overlay applied AFTER the LLM proposes its river action.\n\n"
        + json.dumps(data, indent=2)
        + "\n\nOUR CODE (reuse these): pokerbot/brain/api.py has `equity(hole,range,board)`, `required_equity(to_call,pot)`,"
          " `mdf(bet,pot)`, `pot_odds`, `spr`, `board_texture`, `hand_rank`, `hand_class_of`, `range_top(frac)`. The LLM's"
          " program is run by pokerbot/brain/executor.py::run_program -> a legal action. The live decision path for the"
          " GTOW bot is tools/gtow_client/src/poker_agent.py::GLMBrainAgent._decide (spot_from_slumbot -> brain.decide_spot"
          " -> action). pokerbot/strategy/bot.py already bounds JAMS via guards `bp_jam_min_pct`/`deep_jam_pct` (precedent)."
          " The spot has hole, board, pot, to_call, street.\n\n"
          "Deliver: (1) WHERE to put the corset (exact file/function) so it intercepts the LLM's river action; (2) the"
          " exact guard logic in pseudocode using the existing api.* (the call-fold bound, the bet/overbet-size cap, the"
          " all-in-as-EV handling); (3) how to keep it from OVER-folding (stay at MDF, not below); (4) a GROUNDED A/B test"
          " that verifies the ~10 disaster hands shrink (deterministic, not noisy bb/100). Be concrete + minimal."
    )
    print("\n\n>>> Claude (technical) ...", flush=True)
    ctext, (ci, co, _cc) = ask_claude(CLAUDE_SYS, claude_user, max_tokens=6000, thinking=True, temperature=1.0)
    print(f"  Claude done ({ci}+{co} tok)\n", flush=True)
    print("===== CLAUDE: technical implementation =====\n" + ctext, flush=True)

    out = config.ROOT / "docs" / "river_corset_consult.md"
    with open(out, "w", encoding="utf-8") as f:
        f.write("# River-corset consult (OpenAI math -> Claude technical)\n\n## Context\n" + _CONTEXT + "\n")
        for k, v in data.items():
            f.write(f"\n## OpenAI: {k}\n{v}\n")
        f.write("\n## Claude: technical implementation\n" + ctext + "\n")
    print(f"\nsaved -> {out}", flush=True)


if __name__ == "__main__":
    main()
