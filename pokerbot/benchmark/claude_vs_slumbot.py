"""Opus 4.8 as the PLAYER vs Slumbot, "perfectly prompted" with our ENTIRE bot's analysis.

Experiment: does Claude Opus 4.8, handed ALL the structured signals our solver-grounded engine computes for a spot
(preflop GTO blueprint mix, the keystone's tracked villain range + equity, board texture, the facing-bet defense
advisor's GTO frequencies, the Dirichlet exploit read of Slumbot, the engine's own recommended action + reasoning),
out-play our bot by REASONING over them? Measured vs Slumbot via its public API, with full per-decision data logging.

ClaudePlayer is a drop-in for slumbot.play_hand (exposes .decide(state)->{action,amount}, .hero_idx, .observe_hand_end):
  1. an internal PokerBot(exploit=True, Slumbot-seeded) runs its FULL pipeline on the spot -> the rich `rationale`,
  2. we format that into a prompt, 3. Opus 4.8 decides, 4. parse + legal-gate, 5. log (engine vs Claude, reasoning).
HONEST: raw bb/100 vs Slumbot is variance-dominated at small n (the point is CAPABILITY + DATA, not a precise number).
Clean-boundary: this is an LLM-as-player EVAL, never a training label for the GTO core.
Run: python -m pokerbot.benchmark.claude_vs_slumbot --hands 30 [--model claude-opus-4-8]
"""
from __future__ import annotations

import argparse
import json
import math
import time

import pokerbot.strategy.bot as botmod
from pokerbot import config
from pokerbot.benchmark.llm_opponent import _legalize, _parse
from pokerbot.benchmark.slumbot import BB, play_hand
from pokerbot.strategy import preflop_blueprint as pbp
from pokerbot.strategy.bot import PokerBot

SYS = (
    "You are a world-class heads-up No-Limit Hold'em player (200bb deep), at the level of a top solver-trained "
    "professional, playing against Slumbot (a strong near-GTO bot). You are assisted by a SOLVER-GROUNDED ENGINE "
    "that pre-analyzes each spot for you: GTO blueprint mixes, the opponent's estimated range and your equity vs it, "
    "board texture, GTO facing-bet defense frequencies, and an EXPLOIT read of the opponent's measured leaks. "
    "Use the engine's GTO analysis as your baseline, then apply expert judgment + the exploit read to choose the "
    "EV-MAXIMIZING action. You MAY follow or override the engine — state which and why in ONE short line. "
    "Bet sizes are a FRACTION OF THE POT. End your reply with EXACTLY one final line:\n"
    "ACTION: <fold|check|call|bet> [pot_fraction]   (pot_fraction only for bet, e.g. 'ACTION: bet 0.66')."
)


def _hand_class(hole):
    from pokerbot.engine.cards import hand_class
    try:
        return hand_class(hole[0], hole[1])
    except Exception:  # noqa: BLE001
        return None


def build_prompt(st: dict, seat: int, rat: dict) -> str:
    me, vil, la = st["players"][seat], st["players"][1 - seat], st["legal"]
    pot, tc = la["pot"], la["to_call"]
    podds = tc / (pot + tc) if tc > 0 else 0.0
    spr = me["stack"] / max(1, pot)
    ip = "IN POSITION" if seat == st["button"] else "OUT OF POSITION"
    legal = (["fold"] if tc > 0 else []) + (["check"] if la["can_check"] else []) \
        + (["call"] if tc > 0 else []) + (["bet/raise"] if la["can_raise"] else [])
    hist = " ".join(f"{a.get('player')}:{a.get('action')}" for a in st.get("history", []))[:240]
    lines = [
        f"HUNL 200bb vs Slumbot. You are {ip}. Street: {st['street']}.",
        f"Your hand: {' '.join(me['hole'])}. Board: {' '.join(st['board']) or '(preflop)'}.",
        f"Pot: {pot}. To call: {tc} (pot odds {podds:.0%}). Your stack: {me['stack']}, villain: {vil['stack']}. "
        f"SPR: {spr:.1f}. Blinds {st['bb']//2}/{st['bb']}.",
        f"Action history: {hist or '(none)'}.",
        f"Legal: {legal}.",
        "",
        "=== YOUR SOLVER-GROUNDED ENGINE'S ANALYSIS ===",
    ]
    # preflop: the near-Nash blueprint mix for this hand class
    if st["street"] == "preflop" and pbp.available():
        hc = _hand_class(me["hole"])
        raises = sum(1 for h in st.get("history", []) if h.get("action") in ("bet", "raise", "allin"))
        node = pbp.node_for_state(seat == st["button"], raises, la.get("can_check", False), vil.get("all_in", False))
        mix = pbp.actions(node, hc) if (node and hc) else None
        if mix:
            lines.append(f"GTO preflop blueprint mix ({hc} @ {node}): "
                         + ", ".join(f"{k} {v:.0%}" for k, v in mix.items() if v > 0.02))
    # postflop / general engine signals (from the bot's rationale dict)
    if rat.get("equity") is not None:
        lines.append(f"Made hand: {rat.get('made_hand','?')}. Equity vs the opponent's ESTIMATED range: "
                     f"{rat['equity']:.1%} ({rat.get('villain_combos','?')} combos). Texture: {rat.get('texture')}.")
    if rat.get("defense_advisor"):
        f_, c_, r_ = rat["defense_advisor"]
        lines.append(f"GTO facing-bet defense freqs (solver advisor): fold {f_:.0%} / call {c_:.0%} / raise {r_:.0%} "
                     f"vs a {rat.get('size_faced','?')}-pot bet.")
    if rat.get("opponent"):
        lines.append(f"EXPLOIT read of Slumbot (live model): {rat['opponent']}")
    lines.append(f"Engine's recommended action: {rat.get('_eng_action')} {rat.get('_eng_amount') or ''} "
                 f"-- {rat.get('reasoning','')[:200]}")
    lines.append("\nNow decide (follow or override the engine):")
    return "\n".join(lines)


class ClaudePlayer:
    """Drop-in for slumbot.play_hand: internal PokerBot analyzes -> Opus 4.8 decides. Logs every decision."""

    def __init__(self, model: str, seat: int = 0, log_path=None, exploit: bool = True):
        import anthropic
        self.model = model
        self.hero_idx = seat
        self._client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self._bot = PokerBot(seat, seed=7, exploit=exploit)
        if exploit:                                  # seed the Slumbot exploit read (our entire bot's insight)
            try:
                from pokerbot.strategy.postflop import LearnedFoldModel
                from pokerbot.strategy.opp_model import seed_from_fold_curve
                fm = LearnedFoldModel.load(config.KNOWLEDGE_DIR / "exploit" / "slumbot_fold.json")
                if fm:
                    self._bot.fold_model = fm
                seed_from_fold_curve(self._bot.opp_model)
            except Exception:  # noqa: BLE001
                pass
        self._log = open(log_path, "a", encoding="utf-8") if log_path else None
        self.stats = {"calls": 0, "parse_fail": 0, "followed": 0, "overrode": 0, "hand": 0}

    def _call(self, prompt: str) -> str:
        m = self._client.messages.create(model=self.model, max_tokens=1400, system=SYS,
                                         messages=[{"role": "user", "content": prompt}])
        return "".join(b.text for b in m.content if b.type == "text")

    def decide(self, st: dict) -> dict:
        self.stats["calls"] += 1
        self._bot.hero_idx = self.hero_idx
        try:
            eng = self._bot.decide(st)                 # our FULL engine pipeline
            rat = dict(eng.get("rationale") or {})
            rat["_eng_action"], rat["_eng_amount"] = eng.get("action"), eng.get("amount")
        except Exception:  # noqa: BLE001
            eng, rat = {"action": None, "amount": None}, {}
        prompt = build_prompt(st, self.hero_idx, rat)
        try:
            text = self._call(prompt)
            action, frac = _parse(text)
            if action is None:
                raise ValueError("no action parsed")
            a, amt = _legalize(st, self.hero_idx, action, frac)
        except Exception as ex:  # noqa: BLE001
            self.stats["parse_fail"] += 1
            text = f"(error: {type(ex).__name__})"
            la = st["legal"]
            a, amt = ("check", None) if la["can_check"] else ("call", None)
        if eng.get("action") == a:
            self.stats["followed"] += 1
        else:
            self.stats["overrode"] += 1
        if self._log:
            self._log.write(json.dumps({
                "hand": self.stats["hand"], "street": st["street"], "hole": st["players"][self.hero_idx]["hole"],
                "board": st["board"], "pot": st["legal"]["pot"], "to_call": st["legal"]["to_call"],
                "engine_action": eng.get("action"), "engine_amount": eng.get("amount"),
                "engine_equity": rat.get("equity"), "claude_action": a, "claude_amount": amt,
                "followed_engine": eng.get("action") == a, "claude_reasoning": text[-600:],
            }) + "\n")
            self._log.flush()
        return {"action": a, "amount": amt}

    def observe_hand_end(self, st):
        self.stats["hand"] += 1
        try:
            self._bot.observe_hand_end(st)
        except Exception:  # noqa: BLE001
            pass


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hands", type=int, default=30)
    ap.add_argument("--model", default=config.CLAUDE_MODEL)
    ap.add_argument("--iters", type=int, default=400, help="engine equity MC iters")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    botmod.EQUITY_ITERS = args.iters

    log_path = config.DATA_DIR / "sessions" / f"claude_slumbot_{int(time.time())}.jsonl"
    player = ClaudePlayer(args.model, seat=0, log_path=log_path)
    print(f"Opus-as-player ({args.model}) vs Slumbot, engine-assisted prompt — {args.hands} hands.", flush=True)
    print(f"per-decision data -> {log_path}", flush=True)
    token = None
    winnings = []
    t0 = time.time()
    for h in range(args.hands):
        w, token = play_hand(player, token, verbose=args.verbose and h < 3)
        winnings.append(w)
        n = len(winnings)
        if n % 5 == 0 or n == args.hands:
            total = sum(winnings)
            bb100 = total / n
            stderr = ((sum((x - bb100) ** 2 for x in winnings) / n) ** 0.5 / BB) / math.sqrt(n) * 100
            print(f"  {n:3d} hands | {bb100:+.1f} bb/100 (±{stderr:.0f}) | calls {player.stats['calls']} "
                  f"followed {player.stats['followed']}/{player.stats['followed']+player.stats['overrode']} "
                  f"parse_fail {player.stats['parse_fail']} | {(time.time()-t0)/n:.1f}s/hand", flush=True)
    total = sum(winnings)
    n = len(winnings)
    bb100 = total / n
    stderr = ((sum((x - bb100) ** 2 for x in winnings) / n) ** 0.5 / BB) / math.sqrt(n) * 100
    s = player.stats
    print(f"\n=== Opus-as-player vs Slumbot ({args.model}) ===", flush=True)
    print(f"hands={n} | {bb100:+.1f} bb/100 (±{stderr:.1f} stderr)", flush=True)
    print(f"decisions={s['calls']} | followed engine {s['followed']} / overrode {s['overrode']} "
          f"({100*s['followed']/max(1,s['calls']):.0f}% follow) | parse_fail {s['parse_fail']}", flush=True)
    print(f"data: {log_path}", flush=True)


if __name__ == "__main__":
    main()
