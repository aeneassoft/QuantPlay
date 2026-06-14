"""Claude Haiku as PILOT of the adaptive bot.

The engine exposes boolean control knobs (the "Steuerknöpfe", 0/1). Here Claude Haiku reads the live
opponent profile every N hands and flips those flags to steer the bot — testing whether bot + AI
co-pilot beats the bot's own automatic knob-setting. Haiku decides STRATEGY (which exploits to arm);
the fast engine executes every hand (no LLM in the per-hand loop, so it stays cheap & quick).

Run: python -m pokerbot.arena.haiku_pilot [--hands N] [--refresh N]
"""
from __future__ import annotations

import argparse
import json
import random
import re

import anthropic

import pokerbot.benchmark.beat_them_all as bta
from pokerbot import config
from pokerbot.strategy.adaptive import AdaptiveExploiter, Knobs

HAIKU = "claude-haiku-4-5-20251001"
SYS = (
    "You are the co-pilot of a heads-up No-Limit Hold'em exploitation bot. Given the live read on the "
    "opponent, set 4 boolean control knobs (0 or 1) to maximise profit. Reply ONLY with compact JSON: "
    '{"exploit_bluff":0|1,"exploit_value":0|1,"exploit_bluffcatch":0|1,"probe":0|1}. '
    "Heuristics: exploit_bluff=1 iff the opponent OVER-folds to bets; exploit_value=1 iff the opponent "
    "is sticky / calls too much; exploit_bluffcatch=1 iff the opponent is over-aggressive / bluffs a "
    "lot; probe=1 while the read is still thin (low confidence) to learn faster, else 0."
)


def haiku_knobs(client, summary: dict, fold_curve: dict) -> Knobs:
    try:
        msg = client.messages.create(
            model=HAIKU, max_tokens=200, system=SYS,
            messages=[{"role": "user", "content": f"read={json.dumps(summary)} fold_by_size={json.dumps(fold_curve)}"}])
        txt = "".join(b.text for b in msg.content if b.type == "text")
        m = re.search(r"\{.*\}", txt, re.S)
        d = json.loads(m.group(0)) if m else {}
    except Exception as e:  # noqa: BLE001
        print("  (haiku error, default knobs):", type(e).__name__, str(e)[:80])
        d = {}
    return Knobs(bool(d.get("exploit_bluff", 1)), bool(d.get("exploit_value", 1)),
                 bool(d.get("exploit_bluffcatch", 1)), bool(d.get("probe", 1)))


class HaikuPilot:
    def __init__(self, client, hero: int = 0, iters: int = 90, refresh: int = 40) -> None:
        self.ex = AdaptiveExploiter(hero, seed=7, iters=iters)
        self.client, self.refresh = client, refresh
        self.h = 0
        self.last = None

    def decide(self, st):
        return self.ex.decide(st)

    def observe_opponent(self, st, a):
        self.ex.observe_opponent(st, a)

    def observe_hand_end(self):
        self.ex.observe_hand_end()
        self.h += 1
        if self.h % self.refresh == 0 and self.ex.prof.confidence() > 0.1:
            fc = {"small": round(self.ex.prof.fold_at(0.33), 2), "pot": round(self.ex.prof.fold_at(0.9), 2)}
            self.last = haiku_knobs(self.client, self.ex.prof.summary(), fc)
            self.ex.knobs = self.last


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hands", type=int, default=140)
    ap.add_argument("--refresh", type=int, default=40)
    ap.add_argument("--iters", type=int, default=90)
    args = ap.parse_args()
    bta.botmod.EQUITY_ITERS = args.iters
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    R = random.Random
    opps = {
        "nit(foldy)": lambda: bta.opp_nit(R(3)),
        "station(sticky)": lambda: bta.opp_station(R(1)),
        "unknown-C(trappy)": lambda: bta.opp_synthetic(R(6), 0.40, 0.55, 1.1),
    }
    print(f"HAIKU PILOT vs AUTO ({args.hands} hands, Haiku refresh every {args.refresh}) — bb/100\n")
    print(f"{'opponent':18s} {'auto-knobs':>11s} {'haiku-pilot':>12s} {'final knobs (b,v,bc,p)':>24s}")
    for oname, ofac in opps.items():
        auto = bta.play(AdaptiveExploiter(0, seed=7, iters=args.iters), ofac(), args.hands)
        pilot = HaikuPilot(client, 0, iters=args.iters, refresh=args.refresh)
        ph = bta.play(pilot, ofac(), args.hands)
        k = pilot.last
        kn = f"{int(k.exploit_bluff)},{int(k.exploit_value)},{int(k.exploit_bluffcatch)},{int(k.probe)}" if k else "n/a"
        print(f"{oname:18s} {auto:>11.0f} {ph:>12.0f} {kn:>24s}")


if __name__ == "__main__":
    main()
