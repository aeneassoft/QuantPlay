"""Probe Slumbot to learn its fold-frequency-vs-bet-size curve F(s) per street.

We lead with RANDOM bet sizes (postflop, when first to act) and record how often Slumbot
folds to each size. Aggregated, this is the empirical F(s) we exploit — our data source in
place of pro hand histories. The probing itself loses chips (random bets); that's the cost of
exploration, separate from the benchmark.

Output: knowledge_base/exploit/slumbot_fold.json   { street: [[size, fold_rate, n], ...] }
Run:    python -m pokerbot.benchmark.probe --hands 300
"""
from __future__ import annotations

import argparse
import json
import random
import time
from collections import defaultdict

import pokerbot.strategy.bot as botmod
from pokerbot import config
from pokerbot.benchmark import slumbot as S
from pokerbot.strategy.bot import PokerBot
from pokerbot.strategy.postflop import CANDIDATE_SIZES


def bucket(s: float) -> float:
    return min(CANDIDATE_SIZES, key=lambda c: abs(c - s))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hands", type=int, default=300)
    ap.add_argument("--iters", type=int, default=250)
    args = ap.parse_args()
    botmod.EQUITY_ITERS = args.iters
    rng = random.Random(5)
    bot = PokerBot(0, seed=5, exploit=False)

    # street -> size bucket -> [folds, total]
    rec: dict = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    token = None
    t0 = time.time()

    for h in range(args.hands):
        resp = S._post("/api/new_hand", {"token": token} if token else {})
        token = resp.get("token", token)
        client_pos = resp.get("client_pos", 0)
        first = resp.get("action", "")
        button = client_pos if first == "" else 1 - client_pos
        guard = 0
        while True:
            if resp.get("error_msg") or resp.get("winnings") is not None:
                break
            st = S.build_state(resp["hole_cards"], resp.get("board", []),
                               resp.get("action", ""), resp["client_pos"], button)
            if st is None:
                break
            bot.hero_idx = resp["client_pos"]
            la = st["legal"]
            street = st["street"]
            pot = st["pot"]
            old_action = resp.get("action", "")
            committed = st["players"][resp["client_pos"]]["committed_street"]

            probe_size = None
            if street != "preflop" and la["to_call"] == 0 and la["can_raise"] and rng.random() < 0.85:
                s = rng.choice(CANDIDATE_SIZES)
                to = max(la["raise_min"], min(committed + round(s * pot), la["raise_max"]))
                incr = "b" + str(to)
                probe_size = (to - committed) / max(pot, 1)
            else:
                incr = S.decision_to_incr(bot.decide(st), st)

            new = S._post("/api/act", {"token": token, "incr": incr})
            token = new.get("token", token)
            if probe_size is not None and not new.get("error_msg"):
                rest = new.get("action", "")[len(old_action) + len(incr):].lstrip("/")
                resp_char = rest[0] if rest else "c"
                b = bucket(probe_size)
                rec[street][b][1] += 1
                if resp_char == "f":
                    rec[street][b][0] += 1
            resp = new
            guard += 1
            if guard > 60:
                break
        if (h + 1) % 20 == 0:
            n = sum(t for s in rec.values() for _, t in s.values())
            print(f"  probed {h+1} hands | {n} probe-bets recorded | "
                  f"{(time.time()-t0)/(h+1)*1000:.0f} ms/hand", flush=True)

    table = {}
    for street, sizes in rec.items():
        table[street] = [[b, round(f / t, 3), t] for b, (f, t) in sorted(sizes.items()) if t > 0]
    out = config.KNOWLEDGE_DIR / "exploit" / "slumbot_fold.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(table, indent=2), encoding="utf-8")
    print(f"\nsaved -> {out}")
    for street, rows in table.items():
        print(f"  {street}:")
        for size, fr, n in rows:
            alpha = size / (1 + size)
            tag = "OVERFOLD" if fr > alpha + 0.05 else ("underfold" if fr < alpha - 0.05 else "")
            print(f"    {size:>4}x pot: fold {fr:.0%} (breakeven {alpha:.0%}, n={n}) {tag}")


if __name__ == "__main__":
    main()
