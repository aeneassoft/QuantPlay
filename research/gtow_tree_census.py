"""S0 of the ENGINE→GTOW plan (2026-07-04): extract GTO Wizard's EMPIRICAL bet-size tree from our own per-hand logs.

GTOW plays on its own solution tree, so its logged 'bX' tokens ARE the tree — 12.5k hands of ground truth nobody
extracted before. We replay every logged action_history (same token semantics as gtowizard._parse_history: 'bX' is
CUMULATIVE on the round, '_' ends a round, preflop first actor = button/SB), attribute each action hero-vs-GTOW by
matching a zero-sum replay net against the logged `winnings` (cross-checked vs `gtow_folded`), and aggregate:

  GTOW side  -> per street x (bet|raise) x pot-type: the distribution of bet-to/pot fractions (the empirical tree),
                plus preflop open sizes (bb) and 3bet/4bet multiples.
  Hero side  -> the same, PLUS distance-to-GTOW-grid = how much of OUR play is off-tree (ungradeable by the Analyzer).

$0, read-only, deterministic. Usage: python -m research.gtow_tree_census [--files glob] [--hero-files glob]
Outputs data/census/gtow_tree.json + a printed summary. bb = 100 chips throughout.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
from collections import Counter, defaultdict

from pokerbot.engine.evaluator import evaluate

BB = 100.0
SB = 50.0
_STREETS = ["preflop", "flop", "turn", "river"]


# ---------------------------------------------------------------- replay
def _parse_cards(s):
    s = (s or "").strip()
    return [s[i:i + 2] for i in range(0, len(s) - 1, 2)]


def replay(hand: dict):
    """Walk one logged hand. Yields per-action records and returns (net0, net1, folder_seat).
    Seats are LOG order (players[0], players[1]); button = the seat whose position is SB (HU)."""
    players = hand["players"]
    btn = 0 if str(players[0].get("position", "")).upper() in ("SB", "BTN", "BU", "D") else 1
    round_c = {0: 0.0, 1: 0.0}
    round_c[btn] = SB
    round_c[1 - btn] = BB
    total_c = {0: SB if btn == 0 else BB, 1: SB if btn == 1 else BB}
    carry = 0.0                                   # matched pot from completed streets
    si, actor = 0, btn
    bet_made = True                               # preflop: the BB post counts as the live bet
    n_raises = {0: 0}                             # preflop raise count -> pot type
    folder = None
    actions = []
    for tok in hand.get("history") or []:
        if tok == "_":
            carry += round_c[0] + round_c[1]
            round_c = {0: 0.0, 1: 0.0}
            si += 1
            actor = 1 - btn
            bet_made = False
            continue
        st = _STREETS[min(si, 3)]
        pot_before = carry + round_c[0] + round_c[1]
        cur = max(round_c.values())
        if tok == "f":
            folder = actor
            break
        if tok == "c":
            add = cur - round_c[actor]
            total_c[actor] += add
            round_c[actor] = cur
        elif tok == "k":
            pass
        elif tok and tok[0] == "b":
            try:
                to = float(tok[1:])
            except ValueError:
                actor = 1 - actor
                continue
            add = to - round_c[actor]
            total_c[actor] += add
            kind = "raise" if (bet_made or si == 0) else "bet"
            rec = {"street": st, "seat": actor, "kind": kind, "to": to, "pot_before": pot_before,
                   "cur_bet": cur, "prev_to": cur, "pf_raises": n_raises[0]}
            if st == "preflop":
                n_raises[0] += 1
            actions.append(rec)
            round_c[actor] = to
            bet_made = True
        actor = 1 - actor
    pot = carry + round_c[0] + round_c[1]
    if folder is not None:
        w = 1 - folder
        net = {w: pot - total_c[w], folder: -total_c[folder]}
    else:                                          # showdown (or log ended mid-hand: treat as showdown of pot)
        board = _parse_cards(hand.get("board"))
        h0, h1 = _parse_cards(players[0].get("hole")), _parse_cards(players[1].get("hole"))
        if len(board) == 5 and len(h0) == 2 and len(h1) == 2:
            s0, s1 = evaluate(board, h0), evaluate(board, h1)   # treys: lower = better
            if s0 < s1:
                net = {0: pot - total_c[0], 1: -total_c[1]}
            elif s1 < s0:
                net = {1: pot - total_c[1], 0: -total_c[0]}
            else:
                net = {0: pot / 2 - total_c[0], 1: pot / 2 - total_c[1]}
        else:
            net = {0: 0.0, 1: 0.0}                 # unresolvable — identity via gtow_folded only
    return actions, net, folder, n_raises[0]


def hero_seat_of(hand: dict, net: dict, folder) -> int | None:
    """Hero = the seat whose replay net matches logged `winnings` (±1 chip). Cross-check: gtow_folded."""
    w = hand.get("winnings")
    if w is None:
        return None
    cand = [s for s in (0, 1) if abs(net[s] - w) <= 1.0]
    if hand.get("gtow_folded") and folder is not None:
        cand = [s for s in cand if s != folder] or cand
    if len(cand) == 1:
        return cand[0]
    if len(cand) == 2 and folder is not None and hand.get("gtow_folded") is False:
        return folder                              # we folded; both nets match only if pot symmetric — rare
    return None


# ---------------------------------------------------------------- census
def pot_type_of(pf_raises: int) -> str:
    return {0: "limped", 1: "SRP", 2: "3bet"}.get(pf_raises, "4bet+")


GRID = [0.33, 0.5, 0.75, 1.0, 1.25]                # the assumed GTOW tree we snap to today (POKERB_ONTREE)


def _frac(rec) -> float:
    """Bet: to/pot. Raise: increment over the call as a fraction of the post-call pot."""
    if rec["kind"] == "bet":
        return rec["to"] / rec["pot_before"] if rec["pot_before"] else 0.0
    to_call = rec["cur_bet"]                        # simplification: actor's round commit already folded into pot_before
    pot_after_call = rec["pot_before"] + (to_call - 0)   # conservative; exact enough for a size census
    incr = rec["to"] - rec["cur_bet"]
    return incr / pot_after_call if pot_after_call else 0.0


def bucket(x: float) -> float:
    return round(x * 20) / 20                       # 0.05 buckets


def census(files: list[str], hero_files: list[str]) -> dict:
    gtow = defaultdict(Counter)                     # (street,kind,pot_type) -> Counter(frac bucket)
    hero = defaultdict(Counter)
    pf_gtow, pf_hero = defaultdict(Counter), defaultdict(Counter)   # preflop: raise # -> size
    stats = Counter()
    hero_set = {os.path.normpath(f) for f in hero_files}
    for path in files:
        is_hero_src = os.path.normpath(path) in hero_set
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
            except Exception:  # noqa: BLE001 — malformed hand: skip, count
                stats["replay_err"] += 1
                continue
            hs = hero_seat_of(hand, net, folder)
            if hs is None:
                stats["hero_unknown"] += 1
            for rec in actions:
                who = None if hs is None else ("hero" if rec["seat"] == hs else "gtow")
                if rec["street"] == "preflop":
                    # open size in bb for the 1st raise; multiple-of-previous for 3bet+
                    if rec["pf_raises"] == 0:
                        key, val = "open_bb", round(rec["to"] / BB * 4) / 4
                    else:
                        key, val = f"raise{rec['pf_raises']+1}_mult", round(rec["to"] / max(rec["prev_to"], 1) * 2) / 2
                    if who == "gtow":
                        pf_gtow[key][val] += 1
                    elif who == "hero" and is_hero_src:
                        pf_hero[key][val] += 1
                    continue
                k = (rec["street"], rec["kind"], pot_type_of(rec["pf_raises"]))
                b = bucket(_frac(rec))
                if who == "gtow":
                    gtow[k][b] += 1
                elif who == "hero" and is_hero_src:
                    hero[k][b] += 1
    return {"gtow": gtow, "hero": hero, "pf_gtow": pf_gtow, "pf_hero": pf_hero, "stats": stats}


def grid_from(counter: Counter, min_share=0.05) -> list[tuple[float, float]]:
    total = sum(counter.values()) or 1
    return sorted(((b, c / total) for b, c in counter.items() if c / total >= min_share),
                  key=lambda t: -t[1])


def off_grid_share(counter: Counter, grid: list[float], tol=0.075) -> float:
    total = sum(counter.values()) or 1
    off = sum(c for b, c in counter.items() if not any(abs(b - g) <= tol for g in grid))
    return off / total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", default="data/sessions/gtow_hands_*.jsonl")
    ap.add_argument("--hero-files", default="data/sessions/gtow_hands_1781564230.jsonl,"
                    "data/sessions/gtow_hands_1781574288.jsonl",
                    help="logs whose HERO actions feed the our-side census (default: the 2x2500 engine-era runs)")
    args = ap.parse_args()
    files = sorted(glob.glob(args.files))
    hero_files = [f for f in args.hero_files.split(",") if f and os.path.exists(f)]
    r = census(files, hero_files)
    print(f"hands={r['stats']['hands']}  replay_err={r['stats']['replay_err']}  "
          f"hero_unknown={r['stats']['hero_unknown']}")

    print("\n=== GTOW PREFLOP sizes (the tree) ===")
    for key in sorted(r["pf_gtow"]):
        print(f"  {key:14s}: {grid_from(r['pf_gtow'][key])}")
    print("=== OUR preflop sizes (engine era) ===")
    for key in sorted(r["pf_hero"]):
        print(f"  {key:14s}: {grid_from(r['pf_hero'][key])}")

    print("\n=== GTOW POSTFLOP grid (street/kind/pot-type -> top fractions w/ share) ===")
    for k in sorted(r["gtow"]):
        n = sum(r["gtow"][k].values())
        if n >= 20:
            print(f"  {k[0]:6s} {k[1]:5s} {k[2]:6s} (n={n:4d}): {grid_from(r['gtow'][k])}")

    print("\n=== OUR postflop off-GTOW-grid share (engine era) ===")
    for k in sorted(r["hero"]):
        n = sum(r["hero"][k].values())
        if n >= 10:
            gtow_grid = [b for b, _ in grid_from(r["gtow"].get(k, Counter()), 0.03)] or GRID
            print(f"  {k[0]:6s} {k[1]:5s} {k[2]:6s} (n={n:4d}): off-grid {100*off_grid_share(r['hero'][k], gtow_grid):.0f}%"
                  f"  ours={grid_from(r['hero'][k])[:4]}")

    os.makedirs("data/census", exist_ok=True)
    out = {"gtow": {f"{k[0]}|{k[1]}|{k[2]}": dict(v) for k, v in r["gtow"].items()},
           "hero": {f"{k[0]}|{k[1]}|{k[2]}": dict(v) for k, v in r["hero"].items()},
           "pf_gtow": {k: dict(v) for k, v in r["pf_gtow"].items()},
           "pf_hero": {k: dict(v) for k, v in r["pf_hero"].items()},
           "stats": dict(r["stats"]), "hero_files": hero_files}
    json.dump(out, open("data/census/gtow_tree.json", "w", encoding="utf-8"), indent=1)
    print("\nsaved data/census/gtow_tree.json")


if __name__ == "__main__":
    main()
