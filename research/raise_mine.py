"""GTOW's RAISE-range composition, split by raise-size class + pot type ($0, offline).

The freq book (freq_mine.py -> gtow_frequencies.json) shows GTOW's raise range is POLARIZED on aggregate
(flop raises 49% air) — but the v3.3 lever (raise-facing-bet range narrowing, docs/NOTES.md) needs the SIZE split:
a normal raise keeps a large bluff share, a raise-ALL-IN in a bloated pot is the nutted case that stacked us
(RANK4: K2o called a turn check-raise jam in a 4bet pot, -38bb AIVAT). Both holes are always logged -> the
composition is exact, no showdown-selection bias.

Token semantics mirror freq_mine.walk_decisions / gtow_tree_census.replay: 'bX' = street-cumulative round
level, '_' = street end, preflop first actor = button/SB (the BB post is the live preflop bet), postflop
first actor = BB. One standalone walk (no record/token dual-walk alignment risk).

Usage: python -m research.raise_mine            (mines every data/sessions/gtow_hands_*.jsonl)
Output: data/freq_targets/gtow_raise_ranges.json + a printed table.
"""
from __future__ import annotations

import glob
import json
import sys
from collections import defaultdict
from pathlib import Path

from research.freq_mine import hand_class
from research.gtow_tree_census import hero_seat_of, replay

START_STACK = 20000.0                    # 200bb at bb=100 (every logged GTOW hand)
JAM_TOL = 1.0                            # chips: commitment within this of the stack = all-in
BIG_RAISE_FRAC = 1.5                     # raise increment / post-call pot >= this = "huge" (jam-like pressure)
STREET_BOARD_LEN = {"flop": 3, "turn": 4, "river": 5}
_STREETS = ("preflop", "flop", "turn", "river")
POT_TYPES = {0: "limped", 1: "srp", 2: "3bet", 3: "4bet+"}


def _parse_cards(s) -> list[str]:
    s = s or ""
    return [s[i:i + 2] for i in range(0, len(s), 2)]


def gtow_raises(hand: dict, gtow: int) -> list[dict]:
    """Every postflop raise-facing-bet by the GTOW seat: {street, pot_type, size_cls, board}."""
    players = hand["players"]
    btn = 0 if str(players[0].get("position", "")).upper() in ("SB", "BTN", "BU", "D") else 1
    board_all = _parse_cards(hand.get("board"))
    total = {btn: 50.0, 1 - btn: 100.0}                  # blinds
    round_c = dict(total)
    si, actor, street_aggr, pf_raises = 0, btn, 1, 0
    out: list[dict] = []
    for tok in hand.get("history") or []:
        if tok == "_":
            si += 1
            actor = 1 - btn
            street_aggr = 0
            round_c = {0: 0.0, 1: 0.0}
            continue
        st = _STREETS[min(si, 3)]
        cur = max(round_c.values())
        to_call = cur - round_c[actor]
        if tok == "f":
            break
        if tok == "c":
            round_c[actor] = cur
            total[actor] = total.get(actor, 0.0) + max(0.0, to_call)
        elif tok and tok[0] == "b":
            try:
                to = float(tok[1:])
            except ValueError:
                actor = 1 - actor
                continue
            pot_before = sum(total.values()) - round_c[0] - round_c[1] + round_c[0] + round_c[1]
            total[actor] = total.get(actor, 0.0) + (to - round_c[actor])
            if st != "preflop" and to_call > 0 and actor == gtow:
                # size class: jam (all-in) > huge (>=1.5x post-call pot) > normal
                if total[actor] >= START_STACK - JAM_TOL:
                    size_cls = "jam"
                else:
                    pot_after_call = sum(total.values()) - (to - round_c[actor]) + to_call
                    frac = (to - cur) / pot_after_call if pot_after_call > 0 else 0.0
                    size_cls = "huge" if frac >= BIG_RAISE_FRAC else "normal"
                out.append({"street": st, "pot_type": POT_TYPES.get(min(pf_raises, 3), "srp"),
                            "size_cls": size_cls, "board": board_all[:STREET_BOARD_LEN[st]]})
            if st == "preflop":
                pf_raises += 1
            round_c[actor] = to
            street_aggr += 1
        actor = 1 - actor
    return out


def mine(files: list[str]) -> dict:
    comp: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    stats: defaultdict = defaultdict(int)
    for path in files:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    hand = json.loads(line)
                except json.JSONDecodeError:
                    stats["bad_json"] += 1
                    continue
                players = hand.get("players") or []
                if len(players) != 2 or not hand.get("history"):
                    stats["skipped"] += 1
                    continue
                try:
                    _actions, net, folder, _ = replay(hand)   # zero-sum replay net -> seat identity
                except Exception:  # noqa: BLE001 -- malformed hand: skip, keep mining
                    stats["replay_fail"] += 1
                    continue
                hero = hero_seat_of(hand, net, folder)
                if hero is None:
                    stats["hero_unknown"] += 1
                    continue
                gtow = 1 - hero
                gtow_hole = players[gtow].get("hole") or ""
                if len(gtow_hole) != 4:
                    stats["no_hole"] += 1
                    continue
                hole = [gtow_hole[:2], gtow_hole[2:]]
                stats["hands"] += 1
                for r in gtow_raises(hand, gtow):
                    cls = hand_class(r["board"], hole)
                    comp[f"{r['street']}|{r['pot_type']}|{r['size_cls']}"][cls] += 1
                    stats["raises_tallied"] += 1
    return {"composition": {k: dict(v) for k, v in comp.items()}, "stats": dict(stats)}


def main() -> None:
    files = sorted(glob.glob("data/sessions/gtow_hands_*.jsonl"))
    print(f"mining {len(files)} session logs ...")
    out = mine(files)
    dst = Path("data/freq_targets/gtow_raise_ranges.json")
    dst.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("stats:", out["stats"])
    strong = ("two-pair+", "monster")
    for key in sorted(out["composition"]):
        classes = out["composition"][key]
        n = sum(classes.values())
        nutted = sum(c for cls, c in classes.items() if cls in strong)
        air = classes.get("air", 0)
        print(f"{key:20s} n={n:4d}  nutted {nutted / max(1, n):5.1%}  air {air / max(1, n):5.1%}  "
              f"{dict(sorted(classes.items(), key=lambda x: -x[1]))}")
    print(f"-> {dst}")


if __name__ == "__main__":
    sys.exit(main())
