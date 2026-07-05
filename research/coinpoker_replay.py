"""Replay harness: the 6-max PRODUCT bot (SixMaxBot, tag profile) plays the user's real CoinPoker hands,
decision-for-decision, and we log where it agrees/disagrees with the user's actual play.

Per hand: a FRESH SixMaxBot sits in the hero seat, every public action BEFORE each hero decision is fed
through `bot.observe(...)` (exactly the six_server wiring: allin observed as "raise", to_call/preflop_raises
captured BEFORE the action, the bot observes its own actions too), then `bot.decide(obs)` is asked at each
hero decision point and compared to what the user actually did (action-CLASS match: fold / check-call /
bet-raise buckets).

UNITS (the one conversion, documented once): CoinPoker amounts are TETHER chips with `hand.bb` the big
blind (e.g. NL200 = 1/2); our engine's obs are CHIP amounts with bb = 100 (pokerbot/engine/table.py).
All the bot's thresholds are bb- and pot-RATIO based, so we convert every chip quantity into the bot's
native scale via  chips(x) = round(x / hand.bb * 100)  and report amounts back in bb.

Output: data/coinpoker_replay/bot_vs_prince.jsonl (one record per hero decision) + a printed summary.
Run from the repo root:  python -m research.coinpoker_replay [path-to-hh.txt]
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

from pokerbot.arena.sixmax import PROFILES, SixMaxBot
from pokerbot.coach.coinpoker import hero_decisions, parse_file

DEFAULT_HH = r"C:\Users\hampe\Downloads\CoinPoker_Princedarkness_2026-02-01_to_2026-07-01_Cash.txt"
OUT_PATH = Path("data/coinpoker_replay/bot_vs_prince.jsonl")
ENGINE_BB = 100                      # our engine's big blind in chips (table.py convention)
STREETS = ("preflop", "flop", "turn", "river")

# CoinPoker parser action -> the class the observe-wiring / agreement buckets use
_PUBLIC_ACTS = ("fold", "check", "call", "bet", "raise", "allin")


def _chips(amount_t: float, hand_bb: float) -> int:
    """CoinPoker tether chips -> engine chips (bb = 100)."""
    return int(round(amount_t / hand_bb * ENGINE_BB))


def _bucket(action: str) -> str:
    """Action-CLASS for the agreement metric: fold / check-call / bet-raise."""
    if action == "fold":
        return "fold"
    if action in ("check", "call"):
        return "check-call"
    return "bet-raise"                # bet | raise | allin-as-raise


def _stake_tier(bb_t: float) -> str:
    """low: bb < 1 USDT, mid: 1 <= bb < 5, high: bb >= 5 (the 2..5 gap in the spec folded into mid)."""
    if bb_t < 1:
        return "low"
    return "mid" if bb_t < 5 else "high"


def _build_obs(spot, contrib_hero_t, stack_hero_t, cur_bet_t, min_raise_t, praises, hand_bb) -> dict:
    """The table.py::obs_for schema, built from the Decision's Spot + the tracked street state.

    raise_min/raise_max follow the ENGINE semantics (TOTAL street 'to' amounts): raise_max =
    committed_street + stack; raise_min = current_bet + min_raise (or committed + bb for an unopened bet).
    The Spot's own legal.raise_min uses a different (increment-ish) convention, so we recompute here.
    """
    can_raise = bool(spot.legal.get("can_raise"))
    raise_max_t = contrib_hero_t + stack_hero_t
    if cur_bet_t > 0:
        raise_min_t = min(cur_bet_t + min_raise_t, raise_max_t)
    else:
        raise_min_t = min(contrib_hero_t + hand_bb, raise_max_t)
    return {
        "hole": list(spot.hero_hole), "board": list(spot.board),
        "to_call": _chips(spot.to_call, hand_bb), "pot": _chips(spot.pot, hand_bb),
        "my_stack": _chips(stack_hero_t, hand_bb), "bb": ENGINE_BB, "n_active": spot.n_active,
        "position": spot.hero_pos, "preflop_raises": praises,
        "cur_bet": _chips(cur_bet_t, hand_bb), "my_committed_street": _chips(contrib_hero_t, hand_bb),
        "street": spot.street, "can_check": bool(spot.legal.get("can_check")),
        "can_call": bool(spot.legal.get("can_call")), "can_raise": can_raise,
        "raise_min": _chips(raise_min_t, hand_bb) if can_raise else None,
        "raise_max": _chips(raise_max_t, hand_bb) if can_raise else None,
    }


def _replay_hand(hand, counters) -> list[dict]:
    """Replay ONE hand through a fresh tag SixMaxBot in the hero seat; return the decision records."""
    decisions = hero_decisions(hand)
    if not decisions:
        counters["no_decision"] += 1
        return []
    if len(hand.hero_hole) != 2:
        counters["no_hole"] += 1
        return []

    bot = SixMaxBot(hand.hero_seat, PROFILES["tag"])
    bot.new_hand(sorted(hand.seats))

    # street-replay state, all in tether chips (mirrors coinpoker.hero_decisions' bookkeeping)
    contrib = {s: 0.0 for s in hand.seats}          # current-street contribution
    stack = {s: hand.seats[s]["stack"] for s in hand.seats}
    street, cur_bet, min_raise = "preflop", 0.0, hand.bb
    praises = 0                                     # engine preflop_raises: every preflop bet/raise
    di, records = 0, []

    for a in hand.actions:
        if a["street"] != street:                   # new street -> reset the betting round
            street, contrib = a["street"], {s: 0.0 for s in hand.seats}
            cur_bet, min_raise = 0.0, hand.bb
        seat, act = a["seat"], a["act"]
        to_call_actor = max(0.0, cur_bet - contrib[seat])

        # ---- hero decision point: ask the bot BEFORE the action is applied/observed
        if seat == hand.hero_seat and act in _PUBLIC_ACTS:
            if di >= len(decisions):                # replay drifted from hero_decisions -> malformed
                raise ValueError("decision misalignment")
            d = decisions[di]
            di += 1
            obs = _build_obs(d.spot, contrib[seat], stack[seat], cur_bet, min_raise, praises, hand.bb)
            bot_action = bot_amount_bb = None
            try:
                dec = bot.decide(obs)
                bot_action = dec["action"]          # fold|check|call|raise (raise covers bets)
                if dec.get("amount"):
                    bot_amount_bb = round(dec["amount"] / ENGINE_BB, 2)   # engine 'to' chips -> bb
            except Exception:  # noqa: BLE001 — count, don't crash the run
                counters["decide_errors"] += 1
            # user allin: a raise-class only if it actually exceeds the current bet, else a call/check
            user_act = act
            if act == "allin":
                user_act = "allin" if contrib[seat] + a["inc"] > cur_bet + 1e-9 else "call"
            agree = (_bucket(bot_action) == _bucket(user_act)) if bot_action else None
            records.append({
                "hid": d.hid, "street": street, "position": d.spot.hero_pos, "pot_type": praises,
                "pot_bb": round(d.spot.pot / hand.bb, 2), "to_call_bb": round(d.spot.to_call / hand.bb, 2),
                "hero_hole": list(hand.hero_hole), "board": list(d.spot.board),
                "user_action": d.action, "user_amount_bb": d.amount_bb,
                "bot_action": bot_action, "bot_amount_bb": bot_amount_bb,
                "agree": agree, "stake_tier": _stake_tier(hand.bb),
            })

        # ---- apply the action to the replay state (same arithmetic as coinpoker.hero_decisions)
        praises_before = praises                    # six_server captures preflop_raises BEFORE the action
        if act == "return":
            stack[seat] += a["inc"]
            continue
        if act in ("ante", "post"):
            stack[seat] -= a["inc"]
            if act == "post":
                contrib[seat] = a["to"]
                cur_bet = max(cur_bet, a["to"])
            continue
        if act == "call":
            contrib[seat] += a["inc"]; stack[seat] -= a["inc"]
        elif act in ("bet", "raise"):
            inc = a["to"] - contrib[seat]
            contrib[seat] = a["to"]; stack[seat] -= inc
        elif act == "allin":
            contrib[seat] += a["inc"]; stack[seat] -= a["inc"]
        new_bet = max(cur_bet, contrib[seat])
        if new_bet > cur_bet:                       # a (re)raise: track the engine min_raise
            if new_bet - cur_bet >= min_raise:
                min_raise = new_bet - cur_bet
            if street == "preflop":                 # engine counts every preflop bet/raise
                praises += 1
        cur_bet = new_bet

        # ---- feed the PUBLIC action to the bot's opponent model (the six_server wiring: allin -> "raise",
        # to_call/preflop_raises captured BEFORE the action; the bot observes its own action too)
        if act in _PUBLIC_ACTS:
            obs_act = "raise" if act == "allin" else act
            bot.observe(seat, street, obs_act, _chips(to_call_actor, hand.bb), praises_before)

    if di != len(decisions):                        # fewer hero acts seen than snapshots -> malformed
        raise ValueError("decision misalignment")
    return records


def run(hh_path: str = DEFAULT_HH, out_path: Path = OUT_PATH) -> dict:
    hands = parse_file(hh_path)
    counters = defaultdict(int)
    all_records: list[dict] = []
    for hand in hands:
        try:
            all_records.extend(_replay_hand(hand, counters))
        except Exception:  # noqa: BLE001 — malformed hand: count + skip, never crash the run
            counters["skipped_malformed"] += 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for r in all_records:
            f.write(json.dumps(r) + "\n")

    decided = [r for r in all_records if r["agree"] is not None]
    n_agree = sum(r["agree"] for r in decided)
    by_street = {}
    for st in STREETS:
        sub = [r for r in decided if r["street"] == st]
        if sub:
            by_street[st] = {"n": len(sub), "agree_pct": round(100 * sum(r["agree"] for r in sub) / len(sub), 1)}
    summary = {
        "hands_parsed": len(hands),
        "hands_with_decisions": len({r["hid"] for r in all_records}),
        "n_decisions": len(all_records),
        "n_decided": len(decided),
        "agree_pct": round(100 * n_agree / len(decided), 1) if decided else 0.0,
        "by_street": by_street,
        "skipped_malformed": counters["skipped_malformed"],
        "no_decision_hands": counters["no_decision"],
        "no_hole_hands": counters["no_hole"],
        "decide_errors": counters["decide_errors"],
        "out": str(out_path),
    }
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_HH)
