"""OUR-vs-TEACHER frequency diff: HERO (PRINCE v2.2) vs GTO Wizard, same buckets as freq_mine.

Both players live in the same logs. We bucket HERO's decisions in the target log with the exact
freq_mine machinery (walk_decisions / hand_class / board_texture / census hero-ID), then DIFF each
bucket's action mix against GTOW's saved mix (data/freq_targets/gtow_frequencies.json, mined from
all ~13.5k logged hands). Gap metric = total-variation distance (TVD); ranking = TVD x avg-pot(bb)
x n_hero. Custom nodes not in the saved JSON (c-bet as pf-aggressor, turn lead after a flop
check-through) are mined for GTOW's side directly from all logs.

$0, read-only, deterministic (bootstrap seeded). Usage:
  python -m research.freq_diff [--hero-files data/sessions/gtow_hands_1783226155.jsonl]
"""
from __future__ import annotations

import argparse
import glob
import json
import random
from collections import Counter, defaultdict

from research.freq_mine import ONE_PAIR_CLASSES, board_texture, hand_class, walk_decisions
from research.gtow_tree_census import _parse_cards, hero_seat_of, pot_type_of, replay

GTOW_JSON = "data/freq_targets/gtow_frequencies.json"
MIN_N = 30
BOOT = 1000
ACTIONS = ("fold", "check", "call", "bet", "raise")


# ---------------------------------------------------------------- decision collection
def collect(files: list[str], side: str) -> tuple[list[dict], Counter]:
    """Flat per-decision records for one side ('hero' or 'gtow'), tagged for hand-level bootstrap."""
    recs: list[dict] = []
    stats = Counter()
    hand_idx = 0
    for path in files:
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                hand = json.loads(line)
            except json.JSONDecodeError:
                continue
            stats["hands"] += 1
            try:
                actions, net, folder, _ = replay(hand)
            except Exception:  # noqa: BLE001
                stats["replay_err"] += 1
                continue
            hero = hero_seat_of(hand, net, folder)
            if hero is None:
                stats["hero_unknown"] += 1
                continue
            seat = hero if side == "hero" else 1 - hero
            try:
                decisions, btn = walk_decisions(hand)
            except Exception:  # noqa: BLE001
                stats["walk_err"] += 1
                continue
            hole = _parse_cards(hand["players"][seat].get("hole"))
            hand_idx += 1
            for d in decisions:
                if d["seat"] != seat:
                    continue
                stats["decisions"] += 1
                try:
                    cls = hand_class(d["board"], hole)
                except Exception:  # noqa: BLE001
                    cls = "unknown"
                recs.append({
                    "hand": hand_idx, "street": d["street"], "node": d["node"],
                    "pot_type": pot_type_of(d["pf_raises"]), "cls": cls,
                    "tex": board_texture(d["board"]), "action": d["action"],
                    "frac": d["frac"], "pot_bb": d["pot_before"] / 100.0,
                    # flags for the custom nodes
                    "is_pf_aggr": d["prev_last_aggr"] == seat if d["street"] == "flop" else None,
                    "flop_checked_through": (d["street"] == "turn" and d["prev_last_aggr"] is None),
                    "oop": seat != btn,
                    "vs_barrel": (d["street"] in ("turn", "river") and d["node"] == "facing-bet"
                                  and d["prev_last_aggr"] == 1 - seat),
                })
    return recs, stats


# ---------------------------------------------------------------- mix / gap helpers
def mix_of(recs: list[dict]) -> dict[str, float]:
    c = Counter(r["action"] for r in recs)
    n = sum(c.values())
    return {a: c[a] / n for a in c} if n else {}


def tvd(p: dict[str, float], q: dict[str, float]) -> float:
    return 0.5 * sum(abs(p.get(a, 0.0) - q.get(a, 0.0)) for a in set(p) | set(q))


def boot_ci(recs: list[dict], stat_fn, n_boot: int = BOOT, seed: int = 7) -> tuple[float, float]:
    """Hand-level bootstrap 95% CI of stat_fn(list-of-recs)."""
    rng = random.Random(seed)
    by_hand = defaultdict(list)
    for r in recs:
        by_hand[r["hand"]].append(r)
    hands = list(by_hand.values())
    vals = []
    for _ in range(n_boot):
        sample = [r for _ in range(len(hands)) for r in hands[rng.randrange(len(hands))]]
        vals.append(stat_fn(sample))
    vals.sort()
    return vals[int(0.025 * n_boot)], vals[int(0.975 * n_boot)]


def fmt_mix(m: dict[str, float]) -> str:
    return " ".join(f"{a[:2]}={100 * v:.0f}%" for a, v in sorted(m.items(), key=lambda kv: -kv[1]))


# ---------------------------------------------------------------- main report
def bucket_key(r: dict) -> str:
    return "|".join((r["street"], r["node"], r["pot_type"], r["cls"], r["tex"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hero-files", default="data/sessions/gtow_hands_1783226155.jsonl")
    ap.add_argument("--all-files", default="data/sessions/gtow_hands_*.jsonl")
    ap.add_argument("--top", type=int, default=25)
    args = ap.parse_args()

    hero_recs, hstats = collect(sorted(glob.glob(args.hero_files)), "hero")
    print(f"HERO side: {dict(hstats)}")
    gtow_all, gstats = collect(sorted(glob.glob(args.all_files)), "gtow")
    print(f"GTOW side (all logs, custom nodes): hands={gstats['hands']} decisions={gstats['decisions']}")
    gtow_json = json.load(open(GTOW_JSON, encoding="utf-8"))

    # ---- main bucket diff vs the saved GTOW mixes
    ours = defaultdict(list)
    for r in hero_recs:
        ours[bucket_key(r)].append(r)
    rows = []
    for key, recs in ours.items():
        g = gtow_json["buckets"].get(key)
        if g is None or len(recs) < MIN_N or g["n"] < MIN_N:
            continue
        p, q = mix_of(recs), g["freq"]
        gap = tvd(p, q)
        pot = sum(r["pot_bb"] for r in recs) / len(recs)
        rows.append({"key": key, "n_ours": len(recs), "n_gtow": g["n"], "tvd": gap,
                     "pot_bb": pot, "score": gap * pot * len(recs), "ours": p, "gtow": q,
                     "recs": recs,
                     "ours_bet_frac": (sum(r["frac"] for r in recs if r["frac"] is not None and r["action"] == "bet")
                                       / max(1, sum(1 for r in recs if r["frac"] is not None and r["action"] == "bet"))),
                     "gtow_bet_frac": g.get("mean_bet_frac")})
    rows.sort(key=lambda r: -r["score"])
    print(f"\n=== BUCKET DIFF ranked by TVD x avg-pot(bb) x n_ours  (n>={MIN_N} both sides; {len(rows)} buckets) ===")
    for r in rows[:args.top]:
        lo, hi = boot_ci(r["recs"], lambda s, q=r["gtow"]: tvd(mix_of(s), q), n_boot=300)
        sz = ""
        if r["gtow_bet_frac"] and any(x["action"] == "bet" and x["frac"] is not None for x in r["recs"]):
            sz = f"  size ours {r['ours_bet_frac']:.2f} vs gtow {r['gtow_bet_frac']:.2f}pot"
        print(f"  {r['key']:56s} n={r['n_ours']:4d}/{r['n_gtow']:5d} pot={r['pot_bb']:5.1f}bb "
              f"TVD={r['tvd']:.3f} [{lo:.3f},{hi:.3f}] score={r['score']:6.0f}\n"
              f"     ours {fmt_mix(r['ours'])}   |   gtow {fmt_mix(r['gtow'])}{sz}")

    # ---- (A) river first-in bets: bluff (air) share + size, per pot-type
    print("\n=== (A) RIVER FIRST-IN: ours vs GTOW ===")
    riv_fi = [r for r in hero_recs if r["street"] == "river" and r["node"] == "first-in-after-check"]
    bets = [r for r in riv_fi if r["action"] == "bet"]
    if riv_fi:
        bfreq = len(bets) / len(riv_fi)
        lo, hi = boot_ci(riv_fi, lambda s: (sum(1 for r in s if r["action"] == "bet") / len(s)) if s else 0.0)
        print(f"  ours river first-in bet-freq {100 * bfreq:.1f}% [{100 * lo:.1f},{100 * hi:.1f}] (n={len(riv_fi)})")
    for pot in ("SRP", "limped", "3bet", "4bet+"):
        sub = [r for r in bets if r["pot_type"] == pot]
        gj = gtow_json["specials"]["river_bluff_share"].get(pot, {})
        if not sub:
            continue
        air = sum(1 for r in sub if r["cls"] == "air") / len(sub)
        fr = [r["frac"] for r in sub if r["frac"] is not None]
        mfrac = sum(fr) / len(fr) if fr else float("nan")
        lo, hi = boot_ci(sub, lambda s: (sum(1 for r in s if r["cls"] == "air") / len(s)) if s else 0.0)
        print(f"  {pot:6s} ours n={len(sub):3d} air={100 * air:.0f}% [{100 * lo:.0f},{100 * hi:.0f}] "
              f"@{mfrac:.2f}pot   |   gtow n={gj.get('n_bets')} air={100 * gj.get('air_share', 0):.0f}% "
              f"@{gj.get('mean_bet_frac')}pot")
        print(f"         ours class mix: {fmt_mix(mix_class(sub))}")

    # ---- (B) facing 2nd+ barrels
    print("\n=== (B) FACING 2nd+ BARREL (turn/river facing-bet, same opp barreled prior street) ===")
    barrels = [r for r in hero_recs if r["vs_barrel"]]
    gbar = gtow_json["specials"]["facing_2nd_plus_barrel"]
    for st in ("turn", "river"):
        sub = [r for r in barrels if r["street"] == st]
        gmix = combine_special(gbar, st)
        print(f"  {st:5s} ALL      ours n={len(sub):3d} {fmt_mix(mix_of(sub))}   |   "
              f"gtow n={gmix[1]} {fmt_mix(gmix[0])}")
        op = [r for r in sub if r["cls"] in ONE_PAIR_CLASSES]
        gop = combine_special(gbar, st, ONE_PAIR_CLASSES)
        if op:
            lo, hi = boot_ci(op, lambda s: (sum(1 for r in s if r["action"] == "fold") / len(s)) if s else 0.0)
            print(f"  {st:5s} ONE-PAIR ours n={len(op):3d} {fmt_mix(mix_of(op))} "
                  f"(fold CI [{100 * lo:.0f},{100 * hi:.0f}])   |   gtow n={gop[1]} {fmt_mix(gop[0])}")

    # ---- (C) flop c-bet (pf aggressor, first-in)
    print("\n=== (C) FLOP C-BET (pf aggressor, no bet yet this street) ===")
    for oop in (False, True):
        h = [r for r in hero_recs if r["street"] == "flop" and r["node"] == "first-in-after-check"
             and r["is_pf_aggr"] and r["oop"] == oop]
        g = [r for r in gtow_all if r["street"] == "flop" and r["node"] == "first-in-after-check"
             and r["is_pf_aggr"] and r["oop"] == oop]
        pos = "OOP" if oop else "IP "
        if not h:
            continue
        lo, hi = boot_ci(h, lambda s: (sum(1 for r in s if r["action"] == "bet") / len(s)) if s else 0.0)
        hf = [r["frac"] for r in h if r["action"] == "bet" and r["frac"] is not None]
        gf = [r["frac"] for r in g if r["action"] == "bet" and r["frac"] is not None]
        print(f"  {pos} ours n={len(h):4d} {fmt_mix(mix_of(h))} (bet CI [{100 * lo:.0f},{100 * hi:.0f}]) "
              f"size {avg(hf):.2f}pot   |   gtow n={len(g):4d} {fmt_mix(mix_of(g))} size {avg(gf):.2f}pot")

    # ---- (D) turn lead after flop check-through (the v2.4 probe target)
    print("\n=== (D) TURN AFTER FLOP CHECK-THROUGH, first-in (v2.4 probe baseline) ===")
    for oop in (True, False):
        h = [r for r in hero_recs if r["flop_checked_through"] and r["node"] == "first-in-after-check"
             and r["oop"] == oop]
        g = [r for r in gtow_all if r["flop_checked_through"] and r["node"] == "first-in-after-check"
             and r["oop"] == oop]
        pos = "OOP lead" if oop else "IP stab "
        if not h and not g:
            continue
        hb = fmt_mix(mix_of(h)) if h else "-"
        ci = ""
        if h:
            lo, hi = boot_ci(h, lambda s: (sum(1 for r in s if r["action"] == "bet") / len(s)) if s else 0.0)
            ci = f" (bet CI [{100 * lo:.0f},{100 * hi:.0f}])"
        hf = [r["frac"] for r in h if r["action"] == "bet" and r["frac"] is not None]
        gf = [r["frac"] for r in g if r["action"] == "bet" and r["frac"] is not None]
        print(f"  {pos} ours n={len(h):4d} {hb}{ci} size {avg(hf):.2f}pot   |   "
              f"gtow n={len(g):4d} {fmt_mix(mix_of(g))} size {avg(gf):.2f}pot")
        if h:
            print(f"           ours bet composition: {fmt_mix(mix_class([r for r in h if r['action'] == 'bet']))}")
            print(f"           gtow bet composition: {fmt_mix(mix_class([r for r in g if r['action'] == 'bet']))}")


def avg(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else float("nan")


def mix_class(recs: list[dict]) -> dict[str, float]:
    c = Counter(r["cls"] for r in recs)
    n = sum(c.values())
    return {k: v / n for k, v in c.items()} if n else {}


def combine_special(gbar: dict, street: str, classes=None) -> tuple[dict[str, float], int]:
    """Aggregate the saved facing_2nd_plus_barrel special over hand classes (counts-weighted)."""
    tot = Counter()
    for key, entry in gbar.items():
        st, cls = key.split("|")
        if st != street or (classes is not None and cls not in classes):
            continue
        for a, f in entry["freq"].items():
            tot[a] += f * entry["n"]
    n = int(round(sum(tot.values())))
    return ({a: v / sum(tot.values()) for a, v in tot.items()} if tot else {}, n)


if __name__ == "__main__":
    main()
