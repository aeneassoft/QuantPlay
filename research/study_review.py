"""Stage E of the thought_log study: an INDEPENDENT OpenAI (gpt-5.x) 2nd-opinion on the ~36 hardest/most-disputed
decisions. The log is CLAUDE's own reasoning, so a Claude self-review is biased — OpenAI is the independent grader.

For each selected spot it asks: (1) what does GTO do, (2) is my ACTION acceptable, (3) was my stated REASONING sound
EVEN IF the action was fine (the key decoupled question), (4) the root cause + a rough bb EV cost if it's a real leak.
Resumable (research.llm.Checkpoint), parallel (openai_json opens its own request), ~$4 — PC-hub only (HARD RULE).

  python -m research.study_review [--threads 4]      # reads review_spots.json, writes review_out.jsonl + a summary
"""
from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from research import study_grade as SG
from research.llm import Checkpoint, openai_json

_REVIEW_IN = os.path.join(SG._PLAY_DIR, "review_spots.json")
_REVIEW_OUT = os.path.join(SG._PLAY_DIR, "review_out.jsonl")

SYS = (
    "You are an elite GTO + exploitative No-Limit Hold'em coach giving an INDEPENDENT review of ANOTHER strong "
    "player's heads-up decision vs GTO Wizard (200bb deep, HU). You are NOT that player — critique honestly and "
    "specifically. The engine already computed the made-hand / equity / pot-odds, so trust those. Judge FOUR things: "
    "(1) what GTO actually does here, (2) whether the player's ACTION is acceptable (a small mixed-strategy deviation "
    "is fine — only flag a REAL leak), (3) whether the player's stated REASONING is SOUND even when the action was OK "
    "(faulty logic that happened to pick a fine action still matters), (4) the root cause + a rough bb EV cost if it is "
    "a leak. Judge the DECISION, not the runout — never use hindsight about which cards came."
)

ROOT_CAUSES = ["none", "over_fold", "over_call", "mis_sized_bet", "spew_bluff", "missed_value",
               "wrong_range_read", "math_error", "thin_value_ok", "blueprint_deviation", "exploit_justified", "other"]

SCHEMA = {
    "type": "object",
    "properties": {
        "gto_action": {"type": "string", "description": "the GTO-optimal action (fold/check/call/bet X/raise X)"},
        "agrees_with_my_action": {"type": "boolean"},
        "my_reasoning_sound": {"type": "boolean", "description": "was the stated REASONING valid, regardless of the action?"},
        "root_cause": {"type": "string", "enum": ROOT_CAUSES},
        "ev_cost_bb": {"type": "number", "description": "rough EV cost of the decision vs GTO, in bb (0 if fine)"},
        "confidence": {"type": "number"},
        "why": {"type": "string", "description": "<= 2 sentences, specific"},
    },
    "required": ["gto_action", "agrees_with_my_action", "my_reasoning_sound", "root_cause",
                 "ev_cost_bb", "confidence", "why"],
    "additionalProperties": False,
}


def _user(spot: dict) -> str:
    amt = f" to {spot['my_amount_bb']}bb" if spot.get("my_amount_bb") else ""
    mix = spot.get("oracle_mix") or {}
    oracle = (f"Engine/solver oracle ({spot.get('oracle_source')}): mix={json.dumps(mix)}, "
              f"modal={spot.get('oracle_action')}, P(my action)={spot.get('gto_prob_of_mine')}.") if mix else \
        f"Engine oracle: {spot.get('oracle_source')} (no full solver mix available here)."
    return (f"{spot['spot_text']}\n\n"
            f"PLAYER'S ACTION: {spot['my_action']}{amt}.\n"
            f"PLAYER'S STATED REASONING: {spot.get('my_reasoning','')}\n\n"
            f"{oracle}\n\n"
            "Give your independent verdict per the schema.")


def run(threads: int) -> None:
    spots = json.load(open(_REVIEW_IN, encoding="utf-8"))
    ck = Checkpoint(_REVIEW_OUT)
    todo = [s for s in spots if not ck.has(str(s["seq"]))]
    print(f"reviewing {len(todo)}/{len(spots)} spots (resume: {len(spots)-len(todo)} done)")
    spend = {"in": 0, "out": 0}

    def work(s):
        try:
            verdict, (pi, co) = openai_json(SYS, _user(s), SCHEMA, "decision_review")
        except Exception as e:  # noqa: BLE001
            return s["seq"], {"error": f"{type(e).__name__}: {e}"}
        spend["in"] += pi
        spend["out"] += co
        rec = {**{k: s[k] for k in ("seq", "hand_id", "street", "my_action", "gto_prob_of_mine",
                                    "grade_bucket", "hand_aivat")}, "verdict": verdict}
        return s["seq"], rec

    with ThreadPoolExecutor(max_workers=threads) as ex:
        for seq, rec in ex.map(work, todo):
            ck.add(str(seq), rec)
            v = rec.get("verdict", {})
            print(f"  seq{seq}: agree={v.get('agrees_with_my_action')} reasoning_sound={v.get('my_reasoning_sound')} "
                  f"cause={v.get('root_cause')} ev={v.get('ev_cost_bb')} :: {v.get('why','')[:70]}")
    ck.close()
    _summary(spend)


def _summary(spend) -> None:
    rows = [r for r in SG._load_jsonl(_REVIEW_OUT) if r.get("verdict")]
    n = len(rows)
    if not n:
        print("no reviews"); return
    agree = sum(1 for r in rows if r["verdict"].get("agrees_with_my_action"))
    sound = sum(1 for r in rows if r["verdict"].get("my_reasoning_sound"))
    # the KEY decoupled finding: action OK but reasoning UNSOUND
    ok_act_bad_reason = [r for r in rows if r["verdict"].get("agrees_with_my_action")
                         and not r["verdict"].get("my_reasoning_sound")]
    causes = Counter(r["verdict"].get("root_cause") for r in rows)
    ev = sorted(rows, key=lambda r: r["verdict"].get("ev_cost_bb", 0) or 0, reverse=True)
    print(f"\n=== STAGE E — OpenAI INDEPENDENT REVIEW ({n} spots) ===")
    print(f"agrees with my action: {agree}/{n} ({agree/n:.0%}); reasoning sound: {sound}/{n} ({sound/n:.0%})")
    print(f"ACTION OK but REASONING UNSOUND (the key blind-spot signal): {len(ok_act_bad_reason)}")
    for r in ok_act_bad_reason[:6]:
        print(f"   seq{r['seq']} {r['street']}: {r['verdict'].get('why','')[:90]}")
    print(f"root causes: {dict(causes)}")
    print(f"highest EV-cost (independent estimate):")
    for r in ev[:8]:
        v = r["verdict"]
        print(f"   seq{r['seq']:>3} {r['street']:7s} ev={v.get('ev_cost_bb'):+.1f}bb cause={v.get('root_cause')} "
              f"agree={v.get('agrees_with_my_action')} :: {v.get('why','')[:70]}")
    cost = spend["in"] / 1e6 * 1.25 + spend["out"] / 1e6 * 10  # rough gpt-5.x $/Mtok
    print(f"\ntokens: in={spend['in']} out={spend['out']}  (~${cost:.2f})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--threads", type=int, default=4)
    a = ap.parse_args()
    run(a.threads)


if __name__ == "__main__":
    main()
