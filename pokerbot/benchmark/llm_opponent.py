"""Pit our PokerBot against a frontier-LLM poker agent — the kind of model on the GTO Wizard leaderboard
(the 'GPT-5.x' / 'Claude reproduction' entries). We can't obtain the closed individual agents (Bitcrumbs,
Gravel, ...), but we CAN reproduce an LLM agent with our own API keys and play it locally in our HU engine.

HONEST framing: this is OUR bot vs an LLM agent in OUR engine (200bb, HUNL) — NOT vs GTO Wizard AI, and NOT
AIVAT-adjusted, so the number is NOT directly comparable to the public leaderboard (which scores vs GTOW AI).
It answers: 'does our bot beat a frontier-LLM poker agent?' Raw bb/100 over a modest sample is noisy.

Run:  python -m pokerbot.benchmark.llm_opponent --model gpt-5.1 --hands 60
"""
from __future__ import annotations

import argparse
import json
import re

from pokerbot import config
from pokerbot.benchmark.beat_them_all import PokerBotHero, play

SYS = ("You are an elite heads-up No-Limit Hold'em poker agent (200bb deep). Play to maximize EV / GTO. "
       "You receive one decision node and must return ONLY a JSON object: "
       '{"action": "fold"|"check"|"call"|"bet", "size_pot": <fraction of the pot if action is bet, e.g. 0.66>}. '
       "Use bet for any raise/bet; size_pot is your TOTAL bet this street as a fraction of the current pot. "
       "No prose, JSON only.")


def _prompt(st: dict, seat: int) -> str:
    me = st["players"][seat]
    la = st["legal"]
    legal = []
    if la["to_call"] > 0:
        legal.append("fold")
    if la["can_check"]:
        legal.append("check")
    if la.get("can_call") or la["to_call"] > 0:
        legal.append("call")
    if la["can_raise"]:
        legal.append("bet")
    return (f"Street: {st['street']}. Your hand: {' '.join(me['hole'])}. "
            f"Board: {' '.join(st['board']) or '(none)'}. Pot: {la['pot']}. To call: {la['to_call']}. "
            f"Your stack: {me['stack']}. Villain stack: {st['players'][1-seat]['stack']}. "
            f"History: {' '.join(a.get('action','') for a in st.get('history', []))[:200]}. "
            f"Legal: {', '.join(legal)}. Return your action as JSON.")


def _to_amount(st, seat, frac):
    la = st["legal"]
    committed = st["players"][seat]["committed_street"]
    lo, hi = la["raise_min"], la["raise_max"]
    to = committed + int(max(0.1, frac) * max(1, la["pot"]))
    return hi if lo is None else max(lo, min(to, hi))


def _legalize(st, seat, action, frac):
    la = st["legal"]
    if action == "bet" and la["can_raise"]:
        return ("bet" if la["is_bet"] else "raise"), _to_amount(st, seat, frac or 0.66)
    if action == "fold" and la["to_call"] > 0:
        return "fold", None
    if la["can_check"]:
        return "check", None
    return "call", None


def llm_opponent(model: str, seat: int = 1):
    is_claude = model.startswith("claude")
    if is_claude:
        import anthropic
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    else:
        from openai import OpenAI
        client = OpenAI(api_key=config.OPENAI_API_KEY)
    stats = {"calls": 0, "parse_fail": 0}

    def call(prompt: str) -> str:
        if is_claude:
            m = client.messages.create(model=model, max_tokens=200, system=SYS,
                                       messages=[{"role": "user", "content": prompt}])
            return "".join(b.text for b in m.content if b.type == "text")
        r = client.chat.completions.create(model=model, max_completion_tokens=600,
                                           messages=[{"role": "system", "content": SYS},
                                                     {"role": "user", "content": prompt}])
        return r.choices[0].message.content or ""

    def d(st):
        stats["calls"] += 1
        try:
            raw = call(_prompt(st, seat))
            j = json.loads(raw[raw.index("{"):raw.rindex("}") + 1])
            return _legalize(st, seat, str(j.get("action", "")).lower(), j.get("size_pot"))
        except Exception:  # noqa: BLE001 — robust to any parse/API hiccup
            stats["parse_fail"] += 1
            la = st["legal"]
            return ("check", None) if la["can_check"] else ("call", None)

    d.stats = stats  # type: ignore[attr-defined]
    return d


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gpt-5.1")
    ap.add_argument("--hands", type=int, default=60)
    ap.add_argument("--iters", type=int, default=200)
    args = ap.parse_args()
    import pokerbot.strategy.bot as botmod
    botmod.EQUITY_ITERS = args.iters

    opp = llm_opponent(args.model)
    print(f"PokerBot(exploit) vs LLM agent [{args.model}] — {args.hands} hands, 200bb HUNL ...", flush=True)
    bb100 = play(PokerBotHero(exploit=True, seed=7), opp, args.hands, seed=7, start=20000)
    print(f"\n=== RESULT ===\nPokerBot {bb100:+.0f} bb/100 vs {args.model} "
          f"({args.hands} hands; LLM calls={opp.stats['calls']}, parse_fail={opp.stats['parse_fail']})")
    print("NOTE: vs an LLM agent in our engine, raw (noisy) bb/100 — NOT vs GTO Wizard AI, NOT AIVAT-adjusted.")


if __name__ == "__main__":
    main()
