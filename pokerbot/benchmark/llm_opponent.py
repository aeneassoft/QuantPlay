"""Pit our PokerBot against a frontier-LLM poker agent (GTO-Wizard-leaderboard style).

Two prompt modes:
  --naive  : minimal one-line spot, JSON-only (a WEAK baseline — DON'T trust its win rate).
  (default): a STRONG, PokerSkill-inspired prompt — rich state (pot odds, SPR, position, history) + explicit
             reasoning (CoT) + expert strategy guidance, then a final ACTION line. reasoning_effort=high for
             gpt-5.x. Reproduces the kind of agent that scores well on the public leaderboard.

HONEST framing: OUR bot vs an LLM agent in OUR engine (200bb HUNL) — NOT vs GTO Wizard AI, NOT AIVAT-adjusted.
Raw bb/100 over a modest sample is NOISE-dominated (HU variance ~±200 bb/100 over 100 hands) — directional only.
GPT-5.5 is not in our API; gpt-5.2 is the strongest available proxy. The reliable number needs AIVAT (GTOW key).

Run:  python -m pokerbot.benchmark.llm_opponent --model gpt-5.2 --hands 40
"""
from __future__ import annotations

import argparse
import re

from pokerbot import config
from pokerbot.benchmark.beat_them_all import PokerBotHero, play

SYS_STRONG = (
    "You are a world-class heads-up No-Limit Hold'em player (200bb deep), at the level of a top solver-trained "
    "professional. For EACH decision reason briefly through: (a) your made-hand strength + draws/equity, (b) "
    "range vs range given position and the action so far, (c) pot odds / SPR / stack commitment, (d) balance "
    "(value vs bluffs) and the EV-maximizing bet size. Then commit. Bet sizes are a FRACTION OF THE POT. "
    "End your reply with EXACTLY one final line:\n"
    "ACTION: <fold|check|call|bet> [pot_fraction]\n"
    "where pot_fraction is given only for bet (e.g. 'ACTION: bet 0.66'). Keep reasoning concise."
)
SYS_NAIVE = (
    "You are a heads-up No-Limit Hold'em agent. Return ONLY JSON "
    '{"action":"fold|check|call|bet","size_pot":<frac if bet>}. No prose.'
)


def _prompt(st: dict, seat: int, naive: bool) -> str:
    me, vil, la = st["players"][seat], st["players"][1 - seat], st["legal"]
    legal = ([("fold")] if la["to_call"] > 0 else []) + (["check"] if la["can_check"] else []) \
        + (["call"] if la["to_call"] > 0 else []) + (["bet"] if la["can_raise"] else [])
    hist = " ".join(a.get("action", "") for a in st.get("history", []))[:200]
    if naive:
        return (f"Street {st['street']}. Hand {' '.join(me['hole'])}. Board {' '.join(st['board']) or '-'}. "
                f"Pot {la['pot']}. To call {la['to_call']}. Legal {legal}. JSON action.")
    pot, tc = la["pot"], la["to_call"]
    podds = tc / (pot + tc) if tc > 0 else 0.0
    spr = me["stack"] / max(1, pot)
    ip = "IN POSITION" if seat == st["button"] else "OUT OF POSITION"
    return (f"HUNL, 200bb start. You are {ip}. Street: {st['street']}.\n"
            f"Your hand: {' '.join(me['hole'])}. Board: {' '.join(st['board']) or '(preflop)'}.\n"
            f"Pot: {pot}. To call: {tc} (pot odds {podds:.0%}). Your stack: {me['stack']}, "
            f"villain stack: {vil['stack']}. SPR: {spr:.1f}. Blinds {st['bb']//2}/{st['bb']}.\n"
            f"Action history this hand: {hist or '(none)'}.\n"
            f"Legal actions: {legal}. What is your action?")


def _to_amount(st, seat, frac):
    la = st["legal"]
    committed = st["players"][seat]["committed_street"]
    lo, hi = la["raise_min"], la["raise_max"]
    to = committed + int(max(0.1, frac) * max(1, la["pot"]))
    return hi if lo is None else max(lo, min(to, hi))


def _legalize(st, seat, action, frac):
    la = st["legal"]
    if action in ("bet", "raise", "allin") and la["can_raise"]:
        return ("bet" if la["is_bet"] else "raise"), _to_amount(st, seat, frac if frac else 0.66)
    if action == "fold" and la["to_call"] > 0:
        return "fold", None
    if la["can_check"]:
        return "check", None
    return "call", None


_ACT = re.compile(r"ACTION:\s*(fold|check|call|bet|raise|allin)\s*([0-9]*\.?[0-9]+)?", re.I)
_JSON = re.compile(r'"action"\s*:\s*"(\w+)"(?:.*?"size_pot"\s*:\s*([0-9]*\.?[0-9]+))?', re.S)


def _parse(text: str):
    m = _ACT.search(text) or None
    if m:
        return m.group(1).lower(), float(m.group(2)) if m.group(2) else None
    j = _JSON.search(text)
    if j:
        return j.group(1).lower(), float(j.group(2)) if j.group(2) else None
    return None, None


def llm_opponent(model: str, seat: int = 1, naive: bool = False):
    is_claude = model.startswith("claude")
    sysmsg = SYS_NAIVE if naive else SYS_STRONG
    if is_claude:
        import anthropic
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    else:
        from openai import OpenAI
        client = OpenAI(api_key=config.OPENAI_API_KEY)
    stats = {"calls": 0, "parse_fail": 0}

    def call(prompt: str) -> str:
        if is_claude:
            m = client.messages.create(model=model, max_tokens=1200, system=sysmsg,
                                       messages=[{"role": "user", "content": prompt}])
            return "".join(b.text for b in m.content if b.type == "text")
        kw = {"model": model, "max_completion_tokens": 6000,
              "messages": [{"role": "system", "content": sysmsg}, {"role": "user", "content": prompt}]}
        try:
            return client.chat.completions.create(reasoning_effort="high", **kw).choices[0].message.content or ""
        except Exception:  # noqa: BLE001 — model may reject reasoning_effort
            return client.chat.completions.create(**kw).choices[0].message.content or ""

    def d(st):
        stats["calls"] += 1
        try:
            action, frac = _parse(call(_prompt(st, seat, naive)))
            if action is None:
                raise ValueError("no action parsed")
            return _legalize(st, seat, action, frac)
        except Exception:  # noqa: BLE001
            stats["parse_fail"] += 1
            la = st["legal"]
            return ("check", None) if la["can_check"] else ("call", None)

    d.stats = stats  # type: ignore[attr-defined]
    return d


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gpt-5.2")
    ap.add_argument("--hands", type=int, default=40)
    ap.add_argument("--iters", type=int, default=200)
    ap.add_argument("--naive", action="store_true")
    args = ap.parse_args()
    import pokerbot.strategy.bot as botmod
    botmod.EQUITY_ITERS = args.iters

    opp = llm_opponent(args.model, naive=args.naive)
    tag = "naive" if args.naive else "STRONG/PokerSkill-style"
    print(f"PokerBot(exploit) vs {args.model} [{tag} prompt] — {args.hands} hands, 200bb HUNL ...", flush=True)
    bb100 = play(PokerBotHero(exploit=True, seed=7), opp, args.hands, seed=7, start=20000)
    print(f"\n=== RESULT ===\nPokerBot {bb100:+.0f} bb/100 vs {args.model} ({tag}; {args.hands} hands; "
          f"LLM calls={opp.stats['calls']}, parse_fail={opp.stats['parse_fail']})")
    print("NOTE: noise-dominated at this sample size; NOT vs GTO Wizard AI; NOT AIVAT. Directional only.")


if __name__ == "__main__":
    main()
