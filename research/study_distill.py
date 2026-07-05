"""Stage F (close the loop) of the thought_log study: distill the GOOD decisions into teacher gold.

Take every decision that graded clean (recon_ok + GTO-supported + math-OK), rebuild its exact Spot, and emit it in the
SAME program-of-thought shape the frontier teacher pipeline uses (pipeline.frontier_loop.to_example -> "# <reasoning>\n
decide(...)"), forcing each through the deterministic EV-TRUTH gate (pipeline.filter.EVFilter G1-G6). The accepted rows
become dataset/shards/claude_study.jsonl, registered as sft_gold so registry.sft_gold() (the re-SFT input) picks it up.

HONEST CAP (CLAUDE.md boundary): this is a WARM-START shard (reasoning-bearing + EV-gated), NOT a lift above my own
play. It is built with INCLUDE_MADE_HAND ON so train == serve.

  python -m research.study_distill [--limit N]      # writes the shard + prints inspect_teacher stats
"""
from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict

os.environ.setdefault("POKERB_MADE_HAND", "1")          # train == serve (the +40.65 wiring is ON)

from pipeline.filter import EVFilter
from pipeline.frontier_loop import to_example
from pokerbot.brain.format_spot import format_spot
from research import study_grade as SG

_SHARD = os.path.join(SG._REPO, "dataset", "shards", "claude_study.jsonl")

# A decision is teacher-gold only if it graded clean against the TRUE oracle.
_GOOD_BUCKETS = {"pure_gto", "mixed_ok"}


def _is_good(r: dict) -> bool:
    return bool(r.get("recon_ok") and r.get("grade_bucket") in _GOOD_BUCKETS
               and r.get("in_support") is not False and r.get("math_ok") is not False)


def run(limit: int | None) -> None:
    graded = SG._load_jsonl(SG._GRADED)
    feats = {d["seq"]: d for d in SG._load_jsonl(SG._THOUGHT_LOG)}
    sessions = {h["hand_id"]: h for h in SG._load_jsonl(SG._SESSION)}
    tlog_by_hand = defaultdict(list)
    for d in feats.values():
        tlog_by_hand[d["hand_id"]].append(d)

    good = [r for r in graded if _is_good(r)]
    if limit:
        good = good[:limit]
    print(f"candidates: {len(good)}/{len(graded)} graded-clean decisions")

    ev = EVFilter()
    kept = []
    open(_SHARD, "w").close()                            # fresh shard
    for r in good:
        decs = tlog_by_hand.get(r["hand_id"], [])
        aligned = SG._aligned_points(decs, sessions.get(r["hand_id"], {}))
        pref = aligned.get(r["seq"])
        feat = feats.get(r["seq"], {}).get("features", {})
        hero, button = SG.hero_seat_and_button(sessions.get(r["hand_id"], {}), feat.get("hero_hole", []))
        if not pref or hero < 0:
            continue
        spot = SG.reconstruct_spot(sessions[r["hand_id"]], hero, button, pref[0], pref[1])
        if spot is None:
            continue
        action = (r.get("my_action") or "").lower()
        proposal = {"action": action, "size_bb": r.get("my_amount_bb"), "reasoning": r.get("reasoning", "")}
        ex = to_example(format_spot(spot), proposal)
        v = ev.gate(ex, spot)
        if v.ok:
            kept.append(ex)
            with open(_SHARD, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(ex, ensure_ascii=False) + "\n")

    print(f"\nEVFilter: {dict(ev.stats)}")
    print(f"kept {len(kept)} -> {_SHARD}")
    try:
        from pipeline.inspect_teacher import stats, _fmt
        print("\n=== inspect_teacher (claude_study) ===")
        print("   " + _fmt(stats(_SHARD)))
    except Exception as e:  # noqa: BLE001
        print(f"(inspect_teacher skipped: {e})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    run(a.limit)


if __name__ == "__main__":
    main()
