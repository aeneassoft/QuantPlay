"""WHY is Claude+engine (~-30 bb/100) better than the pure engine (~-47)? A paired DECISION-DIFF: run IDENTICAL spots
through (a) the full -47 engine (PokerBotAgent.act_dict, exploit-primary) and (b) the Claude brain, then show WHERE they
diverge + Claude's STATED reasoning (its program comments = its "why"). The spots are curated to probe the engine's
DOCUMENTED leaks (over-fold to 3bets, deep-jam discipline, c-bet/river decisions) — exactly where a gain would live and
what we'd port back into the engine.

Same input for both: gsr -> gtow_to_state -> state -> {engine: PokerBot.decide(state)} / {Claude:
spot_from_slumbot(state) -> ClaudeBrain.decide_spot}. Honest scope: curated spots, small n — a hypothesis generator
(the gtow_xray decomposition of the real run-log gives the authoritative WHERE). ~$1-2 Claude.

Run:  python -m research.claude_vs_engine
"""
from __future__ import annotations

from pokerbot.benchmark.gtowizard import PokerBotAgent, _gsr, gtow_to_state
from pokerbot.benchmark.slumbot_llm import spot_from_slumbot
from pokerbot.brain.claude_brain import ClaudeBrain
from pokerbot.brain.format_spot import format_spot

_CODE2WORD = {"f": "fold", "c": "call", "k": "check", "b": "bet/raise"}


def _drop_deal(state: dict) -> dict:
    state = dict(state)
    state["history"] = [h for h in state.get("history", []) if "player" in h]
    return state


# Curated HU 200bb spots (BB=100). Each: (label, gsr). Pot math: to_call = total_pot - common_pot;
# common_pot = 2*min(committed). Spots target the engine's documented leaks.
def _spots() -> list[tuple[str, dict]]:
    return [
        # 1. SB/BTN first-in: open-or-fold a speculative hand.
        ("PRE: SB first-in A5s (open/limp/fold?)",
         _gsr("preflop", common=100, total=150, board="", la=["f", "c", "b"], rr={"min": 200, "max": 20000},
              hist=[], hole="As5s", pos="SB", hstack=19950, vstack=19900)),
        # 2. BB facing a 2.5x SB open: defend / 3bet / fold.
        ("PRE: BB vs SB open-to-250, KJo (defend/3bet/fold?)",
         _gsr("preflop", common=200, total=350, board="", la=["f", "c", "b"], rr={"min": 500, "max": 20000},
              hist=["b250"], hole="KsJd", pos="BB", hstack=19900, vstack=19750)),
        # 3. THE LEAK: SB facing a BB 3bet-to-900 with AQo (engine documented to OVER-FOLD to 3bets).
        ("PRE: SB vs BB 3bet-to-900, AQo  [over-fold-to-3bet leak]",
         _gsr("preflop", common=500, total=1150, board="", la=["f", "c", "b"], rr={"min": 1550, "max": 20000},
              hist=["b250", "b900"], hole="AcQd", pos="SB", hstack=19750, vstack=19100)),
        # 4. DEEP-JAM DISCIPLINE: SB faces a full BB jam after a 4bet, holding AKs (Nash: fold AK/QQ to a 200bb jam).
        ("PRE: SB faces BB all-in (20000) after 4bet, AKs  [deep-jam discipline]",
         _gsr("preflop", common=5000, total=22500, board="", la=["f", "c"], rr=None,
              hist=["b250", "b900", "b2500", "b20000"], hole="AsKs", pos="SB", hstack=17500, vstack=0)),
        # 5. Flop c-bet: SB (PFR) on a dry K-high board, BB checked to us, overcards+backdoors.
        ("FLOP Kh7d2c: SB c-bet decision (BB checked), AQs",
         _gsr("flop", common=500, total=500, board="Kh7d2c", la=["k", "b"], rr={"min": 100, "max": 19750},
              hist=["b250", "c", "_", "k"], hole="AsQs", pos="SB", hstack=19750, vstack=19750)),
        # 6. River bluff-catch / call-down discipline: top-pair-weak-kicker facing a river bet.
        ("RIVER Kh7d2c9sAd: BB faces SB river bet-400, K5s top pair  [call-down discipline]",
         _gsr("river", common=500, total=900, board="Kh7d2c9sAd", la=["f", "c", "b"], rr={"min": 800, "max": 19600},
              hist=["b250", "c", "_", "k", "k", "_", "k", "k", "_", "b400"], hole="Kc5c", pos="BB",
              hstack=19750, vstack=19350)),
    ]


def main() -> None:
    brain = ClaudeBrain(thinking=True, strict=True)
    engine = PokerBotAgent(seed=7, exploit=True)        # the deployed -47 chassis (exploit-primary)
    agree = differ = 0
    for label, gsr in _spots():
        state = _drop_deal(gtow_to_state(gsr))
        spot = spot_from_slumbot(state)
        eng = engine.act_dict(gsr)
        e_word = _CODE2WORD.get(eng.get("action"), eng.get("action"))
        e_amt = eng.get("amount")
        res = brain.decide_spot(spot)
        same = (str(res["action"]).startswith(("bet", "raise", "all")) and e_word == "bet/raise") or \
               (res["action"] == e_word) or (res["action"] in ("call",) and e_word == "call") or \
               (res["action"] == "fold" and e_word == "fold") or (res["action"] == "check" and e_word == "check")
        agree += int(same); differ += int(not same)
        print("=" * 100)
        print(label)
        print("-" * 100)
        print(format_spot(spot))
        print(f"\nENGINE (-47): {e_word} {e_amt or ''}")
        print(f"CLAUDE      : {res['action']} {res.get('amount') or ''}  mix={res.get('mix')}")
        print(f"VERDICT     : {'AGREE' if same else '>>> DIFFER <<<'}")
        print("CLAUDE reasoning:\n" + (res.get("program") or "(none)"))
        print()
    print("=" * 100)
    print(f"SUMMARY: agree={agree}  differ={differ}  (n={agree + differ})  | tokens out={brain.report()['out_tok']}")


if __name__ == "__main__":
    main()
