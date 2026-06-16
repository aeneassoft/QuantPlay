"""Weaponize OUR bot: battle the adaptive+gate+depth-aware exploiter against opponents CALIBRATED
to every real data source we have (Pluribus, online-cash population, WSOP pros, famous high-stakes),
plus a large random population. Each real source's hands are mined for its empirical fold-to-bet
curve / aggression / VPIP, and an opponent is built to behave like it — then our bot fights it at
scale (multiprocessing over many cores). Output: a battle report (bb/100 vs each) proving the bot
beats the field, and which sources are toughest.

Run (local smoke):  python -m pokerbot.benchmark.weaponize --hands 80 --pop 20 --workers 4
Run (pod, 64 core): python -m pokerbot.benchmark.weaponize --hands 400 --pop 200 --workers 64
"""
from __future__ import annotations

import argparse
import glob
import json
import multiprocessing as mp
import random
import statistics
from collections import defaultdict

import pokerbot.benchmark.beat_them_all as bta
from pokerbot import config
from pokerbot.benchmark.phh_leaks import REPO, bucket, parse_file, replay_hand
from pokerbot.strategy.adaptive import AdaptiveExploiter

SOURCES = {
    "Pluribus(bot)": (str(REPO / "pluribus" / "**" / "*.phh"), "Pluribus"),
    "OnlineCash1000NL": (str(REPO / "handhq" / "**" / "*.phhs"), None),
    "WSOP-pros": (str(REPO / "wsop" / "**" / "*.phh"), None),
    "Famous-highstakes": (str(REPO / "*.phh"), None),
}
OUT = config.KNOWLEDGE_DIR / "exploit" / "weaponize_report.json"


def derive_profile(glob_pat: str, target):
    """Mine a source's empirical fold-to-bet (by size), aggression and VPIP -> opponent params."""
    fold = defaultdict(lambda: [0, 0])
    could = did = pf = pf_in = 0
    for fp in glob.glob(glob_pat, recursive=True):
        try:
            for d in parse_file(fp):
                for street, to_call, pot, nact, verb, name in replay_hand(d):
                    if target and name != target:
                        continue
                    if to_call > 0 and pot > to_call:
                        b = bucket(to_call / (pot - to_call))
                        fold[b][1] += 1
                        if verb == "f":
                            fold[b][0] += 1
                    else:
                        could += 1
                        if verb == "cbr":
                            did += 1
                    if street == "preflop":
                        pf += 1
                        if verb in ("cbr",) or (verb == "cc" and to_call > 0) or verb == "cbr":
                            pf_in += 1
        except Exception:  # noqa: BLE001
            continue
    fr = {b: (f / n if n else 0.5) for b, (f, n) in fold.items()}
    return {"fold": {b: round(fr.get(b, 0.5), 3) for b in ("small", "med", "pot", "over")},
            "aggr": round(did / could, 3) if could else 0.3,
            "vpip": round(pf_in / pf, 3) if pf else 0.5,
            "n_faced": sum(n for _, n in fold.values())}


def make_calibrated_opp(prof, rng):
    """An opponent that folds-to-bet / bets / enters pots at this source's measured rates."""
    fold = prof["fold"]
    aggr = prof["aggr"]

    def d(st):
        la = st["legal"]
        if la["to_call"] > 0:
            s = la["to_call"] / max(1, la["pot"] - la["to_call"])
            if rng.random() < fold.get(bucket(s), 0.5):
                return "fold", None
            if la["can_raise"] and rng.random() < aggr * 0.4:
                return ("bet" if la["is_bet"] else "raise"), bta._aggr_amount(st, 0.7)
            return ("call", None) if la["can_call"] else ("fold", None)
        if la["can_raise"] and rng.random() < aggr:
            return ("bet" if la["is_bet"] else "raise"), bta._aggr_amount(st, 0.7)
        return "check", None
    return d


def _battle(arg):
    """One matchup: our hero vs an opponent spec. Returns (label, bb/100). hero_kind='mvp' = the unified
    PokerBot exploit-primary (the MVP we measure everywhere); 'adaptive' = the legacy AdaptiveExploiter (reference)."""
    label, kind, spec, hands, iters, hero_kind = arg
    rng = random.Random(hash(label) & 0xFFFF)
    if kind == "calibrated":
        opp = make_calibrated_opp(spec, rng)
    else:  # synthetic random
        fp, ap_, sz = spec
        opp = bta.opp_synthetic(rng, fold_p=fp, aggr_p=ap_, size=sz)
    hero = (bta.PokerBotHero(exploit=True, seed=7) if hero_kind == "mvp"
            else AdaptiveExploiter(0, seed=7, iters=iters, gate=True, depth_aware=True))
    return label, bta.play(hero, opp, hands)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hands", type=int, default=400)
    ap.add_argument("--pop", type=int, default=200, help="extra random 'unknown' opponents")
    ap.add_argument("--iters", type=int, default=120)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--hero", choices=("mvp", "adaptive"), default="mvp",
                    help="mvp = the unified PokerBot exploit-primary (default); adaptive = legacy AdaptiveExploiter")
    args = ap.parse_args()

    print("Deriving calibrated opponents from real data sources...")
    profiles = {}
    for name, (pat, tgt) in SOURCES.items():
        p = derive_profile(pat, tgt)
        profiles[name] = p
        print(f"  {name:18s}: fold={p['fold']} aggr={p['aggr']} vpip={p['vpip']} (n_faced={p['n_faced']})")

    tasks = [(name, "calibrated", profiles[name], args.hands, args.iters, args.hero)
             for name in SOURCES if profiles[name]["n_faced"] >= 30]
    rng = random.Random(123)
    for i in range(args.pop):
        tasks.append((f"unknown#{i}", "synthetic",
                      (rng.random(), rng.random() * 0.7, 0.3 + rng.random() * 1.2), args.hands, args.iters, args.hero))

    print(f"\nBattling our bot (hero={args.hero}) in {len(tasks)} matchups "
          f"({args.hands} hands each, {args.workers} workers)...")
    if args.workers > 1:
        with mp.Pool(args.workers) as pool:
            res = pool.map(_battle, tasks)
    else:
        res = [_battle(t) for t in tasks]

    real = {lbl: bb for lbl, bb in res if not lbl.startswith("unknown")}
    synth = [bb for lbl, bb in res if lbl.startswith("unknown")]
    print("\n=== BATTLE REPORT — our bot's bb/100 vs calibrated REAL-DATA opponents ===")
    for lbl, bb in real.items():
        print(f"  {lbl:18s}: {bb:+8.0f} bb/100  {'WIN' if bb > 0 else 'LOSS'}")
    if synth:
        beaten = sum(1 for b in synth if b > 0)
        print(f"\n  vs {len(synth)} random unknown opponents: beaten {beaten}/{len(synth)} "
              f"({100*beaten/len(synth):.0f}%) | mean {statistics.mean(synth):+.0f} | min {min(synth):+.0f}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"hero": args.hero, "profiles": profiles, "real_bb100": real,
                               "synth_beaten_pct": (100 * sum(1 for b in synth if b > 0) / len(synth)) if synth else None,
                               "synth_mean": statistics.mean(synth) if synth else None}, indent=2), encoding="utf-8")
    print(f"\nSaved -> {OUT}")


if __name__ == "__main__":
    main()
