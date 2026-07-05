"""Step 2 of plan #3 — CLAUDE-TEACHER postflop policy distillation.

Generates HU postflop spots (`dataset/build/from_hu_postflop`), asks CLAUDE for the GTO action on each (the slow API
calls run in a thread pool), then forces every proposal through the deterministic EV-truth filter
(`pipeline/filter.EVFilter`) before APPENDING the accepted to a jsonl shard. Frontier = a GATED prior, engine = truth
(CLAUDE.md hard rule: frontier APIs feed the PC hub ONLY, never the pod). Gating runs single-threaded (EVFilter's
stats/dedup are not thread-safe) — only the I/O-bound Claude calls are parallel.

Run:  python -m pipeline.distill_run --n 300 --out dataset/shards/_teacher_pilot.jsonl   # PILOT (~$4) -> inspect
      python -m pipeline.distill_run --n 4000 --threads 8                                 # FULL -> teacher.jsonl
"""
from __future__ import annotations

import argparse
import json
import random
from concurrent.futures import ThreadPoolExecutor

from dataset.build import from_hu_postflop
from pokerbot import config
from pokerbot.brain.format_spot import format_spot
from pipeline.filter import EVFilter
from pipeline.frontier_loop import frontier_proposer, to_example


def _propose(spot, proposer):
    """One Claude proposal for a spot. Returns (spot, spot_text, proposal|None, in_tok, out_tok, err|None)."""
    spot_text = format_spot(spot)
    try:
        proposal, (it, ot) = proposer(spot_text)
        return spot, spot_text, proposal, it, ot, None
    except Exception as e:  # noqa: BLE001 — count hard failures (ask_claude already retries transient ones)
        return spot, spot_text, None, 0, 0, str(e)[:100]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300, help="number of spots to distill (the spend knob)")
    ap.add_argument("--threads", type=int, default=6, help="parallel Claude calls")
    ap.add_argument("--n-per-line", type=int, default=600, help="spot-pool size per pot type before sampling")
    ap.add_argument("--out", default=str(config.ROOT / "dataset" / "shards" / "teacher.jsonl"))
    ap.add_argument("--provider", default="claude")
    args = ap.parse_args()

    spots = list(from_hu_postflop.build(n_per_line=args.n_per_line))
    random.Random(7).shuffle(spots)                              # diversity within the --n budget
    spots = spots[: args.n]
    print(f"distilling {len(spots)} HU postflop spots via {args.provider} ({args.threads} threads) -> {args.out}",
          flush=True)

    proposer = frontier_proposer(args.provider)
    flt = EVFilter()
    accepted, tok_in, tok_out, api_err, done = [], 0, 0, 0, 0
    with ThreadPoolExecutor(max_workers=args.threads) as ex:
        for spot, spot_text, proposal, it, ot, err in ex.map(lambda s: _propose(s, proposer), spots):
            done += 1
            tok_in += it
            tok_out += ot
            if err:
                api_err += 1
            else:
                rec = to_example(spot_text, proposal)
                if flt.gate(rec, spot).ok:
                    accepted.append(rec)
            if done % 50 == 0:
                print(f"  {done}/{len(spots)} | accepted {len(accepted)} | api_err {api_err} | "
                      f"tok out={tok_out}", flush=True)

    with open(args.out, "a", encoding="utf-8") as f:
        for rec in accepted:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    keep = 100.0 * len(accepted) / max(1, len(spots) - api_err)
    print(f"\nDONE: accepted {len(accepted)}/{len(spots)} ({keep:.0f}% of non-error) -> {args.out}")
    print(f"filter stats: {dict(flt.stats)}")
    print(f"api errors: {api_err} | tokens in={tok_in:,} out={tok_out:,}")


if __name__ == "__main__":
    main()
