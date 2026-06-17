"""Short-deck (6+) GTO cache — the foundation for a HU-postflop near-GTO short-deck bot. Mass-solves 36-card
(6-A) flops with TexasSolver mode='shortdeck' -> data/_gto_shortdeck_cache. Mirrors mass_solve.py's parallel
structure; short-deck is a SMALLER game (630 combos, ~5s solves) so this is fast + scales to the parallel-CPU run.
Run: python -m extraction.mass_solve_shortdeck [minutes] [workers] [threads_per_solve]

⚠ RULE-LOCK (verify before a PRODUCTION cache): TexasSolver's bundled short-deck dict ranks flush>full house +
A-6-7-8-9 wheel (verified). Confirm the trips-vs-straight order matches the TARGET room (Triton/modern: straight
beats trips) before trusting the cache competitively. The ranges below are a reasonable SRP placeholder (refine
with a short-deck range model later)."""
from __future__ import annotations

import json
import os
import random
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from pokerbot import config
from pokerbot.strategy import gto_oracle as O
from pokerbot.strategy.distill import SMALL_BETS

SD_RANKS = "6789TJQKA"
SD_CARDS = [r + s for r in SD_RANKS for s in "cdhs"]          # 36-card short deck
# Reasonable short-deck SRP range (6-A only — no 2-5). Placeholder for the pilot; refine with a SD range model.
SD_RANGE = ("AA,KK,QQ,JJ,TT,99,88,77,66,AKs,AQs,AJs,ATs,A9s,A8s,A7s,A6s,KQs,KJs,KTs,K9s,K8s,QJs,QTs,Q9s,"
            "JTs,J9s,T9s,T8s,98s,97s,87s,86s,76s,AKo,AQo,AJo,ATo,KQo,KJo,KTo,QJo,QTo,JTo")  # 6-A ONLY (no 65s: 5 not in short-deck)
assert not (set(SD_RANGE) & set("2345")), "SD_RANGE must be 6-A only (no 2-5 ranks) — short-deck has no 2-5"

MINUTES = float(sys.argv[1]) if len(sys.argv) > 1 else 10.0
WORKERS = int(sys.argv[2]) if len(sys.argv) > 2 else 4
THREADS = int(sys.argv[3]) if len(sys.argv) > 3 else 2
CACHE = config.DATA_DIR / "_gto_shortdeck_cache"
CACHE.mkdir(parents=True, exist_ok=True)


def solve_one(_):
    b = random.sample(SD_CARDS, 3)
    cf = CACHE / ("".join(b) + ".json")
    if cf.exists():
        return 0
    try:
        node = O.solve(b, SD_RANGE, SD_RANGE, pot=20, eff_stack=100, accuracy=0.5, max_iter=60,
                       threads=THREADS, bets=SMALL_BETS, dump_rounds=1, timeout=120, mode="shortdeck",
                       tag="sd" + uuid.uuid4().hex[:8])
        keys = len((node.get("strategy") or {}).get("strategy") or {})
        if keys == 0:
            return 0
        tmp = cf.with_name(cf.name + f".{uuid.uuid4().hex[:6]}.tmp")
        tmp.write_text(json.dumps(node))
        os.replace(tmp, cf)
        return 1
    except Exception:  # noqa: BLE001
        return 0


def main():
    t0, solved = time.time(), 0
    print(f"short-deck mass-solve: workers={WORKERS} threads={THREADS} minutes={MINUTES} -> {CACHE.name}", flush=True)
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        while (time.time() - t0) / 60 < MINUTES:
            solved += sum(ex.map(solve_one, range(WORKERS)))
            print(f"  +{solved} new | cache={len(list(CACHE.glob('*.json')))} | {(time.time()-t0)/60:.1f} min", flush=True)
    print(f"DONE short-deck: {solved} new, cache total {len(list(CACHE.glob('*.json')))}", flush=True)


if __name__ == "__main__":
    main()
