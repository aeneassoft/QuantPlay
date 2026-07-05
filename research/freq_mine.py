"""Mine PER-NODE ACTION-FREQUENCY TARGETS from GTO Wizard's revealed play in our ~13.5k logged hands.

GTOW (the near-GTO teacher) sits on one side of every logged hand and BOTH hole cards are logged, so its
per-node action mix is free near-solver supervision. We reuse research.gtow_tree_census's VALIDATED replay
+ hero-seat identification (a zero-sum replay net matched against the logged `winnings`, cross-checked vs
`gtow_folded`), then bucket every GTOW decision:

  (street, node-class, pot-type, hand-strength class, board texture) -> action mix + mean size + n

Node classes: first-in-after-check (no live bet) | facing-bet (one aggression level) | facing-raise (2+).
Preflop legend (the BB post counts as the live bet): (preflop|facing-bet|limped) = the SB RFI node,
(preflop|facing-raise|SRP) = BB defending vs an open, (preflop|facing-raise|3bet) = facing a 3bet.

$0, read-only, deterministic. Usage: python -m research.freq_mine [--files glob]
Outputs data/freq_targets/gtow_frequencies.json + a printed report (top buckets + three live design
questions: barrel defense with one pair, river bluff share, flop check-back traps). bb = 100 chips.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import time
from collections import Counter, defaultdict

from pokerbot.engine.evaluator import best_five_name, evaluate, made_class
from research.gtow_tree_census import BB, SB, _STREETS, _parse_cards, hero_seat_of, pot_type_of, replay

RANK_ORDER = "23456789TJQKA"
STREET_BOARD_LEN = {"preflop": 0, "flop": 3, "turn": 4, "river": 5}
ONE_PAIR_CLASSES = ("pair", "top-pair")
TRAP_CLASSES = ("two-pair+", "monster")
NET_MATCH_TOL = 1.0                      # chips; same tolerance as the census hero-seat match


# ---------------------------------------------------------------- hand class / texture
def board_texture(board: list[str]) -> str:
    """monotone (3+ of one suit) > paired (any board rank twice) > other. Preflop = its own bucket."""
    if not board:
        return "preflop"
    if max(Counter(c[1] for c in board).values()) >= 3:
        return "monotone"
    if max(Counter(c[0] for c in board).values()) >= 2:
        return "paired"
    return "other"


def hand_class(board: list[str], hole: list[str]) -> str:
    """Alias: the taxonomy moved to pokerbot.engine.evaluator.made_class (2026-07-05) so the range
    tracker's raise narrowing and this mining classify IDENTICALLY (the mined mixes calibrate that
    lever). Semantics verified byte-identical on relocation."""
    return made_class(board, hole)


# ---------------------------------------------------------------- decision walk
def walk_decisions(hand: dict) -> tuple[list[dict], int]:
    """Every decision point of a logged hand, in order. Token semantics mirror gtow_tree_census.replay
    ('bX' = cumulative round level, '_' = street end, preflop first actor = button/SB, the BB post is
    the live preflop bet). Returns (decisions, btn_seat)."""
    players = hand["players"]
    btn = 0 if str(players[0].get("position", "")).upper() in ("SB", "BTN", "BU", "D") else 1
    board_all = _parse_cards(hand.get("board"))
    round_c = {0: 0.0, 1: 0.0}
    round_c[btn] = SB
    round_c[1 - btn] = BB
    carry = 0.0                                   # matched pot from completed streets
    si, actor = 0, btn
    street_aggr = 1                               # the BB post counts as the live preflop bet
    pf_raises = 0
    last_aggr: dict[int, int | None] = {}         # street idx -> seat of the street's last aggressor
    cur_last_aggr = None
    out: list[dict] = []
    for tok in hand.get("history") or []:
        if tok == "_":
            last_aggr[si] = cur_last_aggr
            carry += round_c[0] + round_c[1]
            round_c = {0: 0.0, 1: 0.0}
            si += 1
            actor = 1 - btn
            street_aggr = 0
            cur_last_aggr = None
            continue
        st = _STREETS[min(si, 3)]
        pot_before = carry + round_c[0] + round_c[1]
        cur = max(round_c.values())
        to_call = cur - round_c[actor]
        node = ("first-in-after-check" if to_call <= 0
                else "facing-bet" if street_aggr <= 1 else "facing-raise")
        rec = {"street": st, "seat": actor, "node": node, "pf_raises": pf_raises,
               "board": board_all[:STREET_BOARD_LEN[st]], "pot_before": pot_before,
               "prev_last_aggr": last_aggr.get(si - 1), "frac": None}
        if tok == "f":
            rec["action"] = "fold"
            out.append(rec)
            break
        if tok == "c":
            rec["action"] = "call" if to_call > 0 else "check"   # 'c' at to_call 0 = the BB option
            out.append(rec)
            round_c[actor] = cur
        elif tok == "k":
            rec["action"] = "check"
            out.append(rec)
        elif tok and tok[0] == "b":
            try:
                to = float(tok[1:])
            except ValueError:                    # malformed token: skip it, keep census parity
                actor = 1 - actor
                continue
            if node == "first-in-after-check":
                rec["action"] = "bet"
                rec["frac"] = to / pot_before if pot_before else None
            else:                                 # raise size = increment over the call / post-call pot
                rec["action"] = "raise"
                pot_after_call = pot_before + to_call
                rec["frac"] = (to - cur) / pot_after_call if pot_after_call else None
            out.append(rec)
            if st == "preflop":
                pf_raises += 1
            round_c[actor] = to
            street_aggr += 1
            cur_last_aggr = actor
        actor = 1 - actor
    return out, btn


# ---------------------------------------------------------------- mining
def _new_bucket() -> dict:
    return {"acts": Counter(), "bet_sum": 0.0, "bet_n": 0, "raise_sum": 0.0, "raise_n": 0}


def mine(files: list[str]) -> dict:
    buckets: dict[tuple, dict] = defaultdict(_new_bucket)
    barrel = defaultdict(Counter)                 # (street, hand class) -> action mix vs a 2nd+ barrel
    river_bets = defaultdict(Counter)             # pot-type -> hand-class mix of GTOW's river BETS
    river_bet_frac = defaultdict(lambda: [0.0, 0])
    river_raises = Counter()                      # pot-type -> n (footnote only)
    cb_node, cb_checks, cb_bets = Counter(), Counter(), Counter()   # GTOW IP flop, checked to
    stats = Counter()
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
            except Exception:  # noqa: BLE001 — malformed hand: skip, count
                stats["replay_err"] += 1
                continue
            _cross_check_identity(hand, net, folder, stats)
            hero = hero_seat_of(hand, net, folder)
            if hero is None:
                stats["hero_unknown"] += 1
                continue
            stats["hero_seat0" if hero == 0 else "hero_seat1"] += 1
            gtow = 1 - hero
            try:
                decisions, btn = walk_decisions(hand)
            except Exception:  # noqa: BLE001
                stats["walk_err"] += 1
                continue
            # parity check: our walk must see exactly the aggressive actions the census replay saw
            stats["aggr_walk"] += sum(1 for d in decisions if d["action"] in ("bet", "raise"))
            stats["aggr_census"] += len(actions)
            gtow_hole = _parse_cards(hand["players"][gtow].get("hole"))
            for d in decisions:
                if d["seat"] != gtow:
                    continue
                stats["gtow_decisions"] += 1
                try:
                    cls = hand_class(d["board"], gtow_hole)
                except Exception:  # noqa: BLE001 — bad cards
                    cls = "unknown"
                    stats["class_err"] += 1
                _tally(d, cls, pot_type_of(d["pf_raises"]), gtow, btn, buckets,
                       barrel, river_bets, river_bet_frac, river_raises, cb_node, cb_checks, cb_bets)
    return {"buckets": buckets, "barrel": barrel, "river_bets": river_bets,
            "river_bet_frac": river_bet_frac, "river_raises": river_raises,
            "cb_node": cb_node, "cb_checks": cb_checks, "cb_bets": cb_bets, "stats": stats}


def _tally(d, cls, pot, gtow, btn, buckets, barrel, river_bets, river_bet_frac, river_raises,
           cb_node, cb_checks, cb_bets):
    act = d["action"]
    b = buckets[(d["street"], d["node"], pot, cls, board_texture(d["board"]))]
    b["acts"][act] += 1
    if d["frac"] is not None:
        kind = "bet" if act == "bet" else "raise"
        b[f"{kind}_sum"] += d["frac"]
        b[f"{kind}_n"] += 1
    # (1) facing a 2nd+ barrel: turn/river facing-bet where the bettor also last-aggressed the prior street
    if (d["street"] in ("turn", "river") and d["node"] == "facing-bet"
            and d["prev_last_aggr"] == 1 - gtow):
        barrel[(d["street"], cls)][act] += 1
    # (2) river first-in bets: bluff share = air share
    if d["street"] == "river" and act == "bet":
        river_bets[pot][cls] += 1
        if d["frac"] is not None:
            river_bet_frac[pot][0] += d["frac"]
            river_bet_frac[pot][1] += 1
    if d["street"] == "river" and act == "raise":
        river_raises[pot] += 1
    # (3) flop check-back: GTOW in position (btn), checked to
    if d["street"] == "flop" and d["node"] == "first-in-after-check" and gtow == btn:
        cb_node[act] += 1
        (cb_checks if act == "check" else cb_bets)[cls] += 1


def _cross_check_identity(hand, net, folder, stats):
    """Independent of hero_seat_of: when the net match alone is unique AND a fold happened, the
    prediction 'GTOW folded iff the folder is not hero' must agree with the logged gtow_folded flag."""
    w = hand.get("winnings")
    if w is None or folder is None or not isinstance(hand.get("gtow_folded"), bool):
        return
    cand = [s for s in (0, 1) if abs(net[s] - w) <= NET_MATCH_TOL]
    if len(cand) == 1:
        predicted_gtow_folded = folder != cand[0]
        stats["xcheck_agree" if predicted_gtow_folded == hand["gtow_folded"] else "xcheck_disagree"] += 1


# ---------------------------------------------------------------- report / output
def _mix(counter: Counter) -> str:
    n = sum(counter.values())
    return " ".join(f"{a[:2]}={100 * c / n:.0f}%" for a, c in counter.most_common()) if n else "-"


def _share(counter: Counter, keys) -> float:
    n = sum(counter.values())
    return sum(counter[k] for k in keys) / n if n else 0.0


def print_report(r: dict, top_n: int = 20):
    s = r["stats"]
    ided = s["hero_seat0"] + s["hero_seat1"]
    print(f"hands={s['hands']}  replay_err={s['replay_err']}  hero_unknown={s['hero_unknown']} "
          f"({100 * s['hero_unknown'] / max(s['hands'], 1):.1f}%)  identified={ided}")
    print(f"identity cross-check (net-unique fold hands): agree={s['xcheck_agree']} "
          f"disagree={s['xcheck_disagree']}  |  hero seat0/seat1 = {s['hero_seat0']}/{s['hero_seat1']}")
    print(f"walk parity: aggressive actions walk={s['aggr_walk']} census={s['aggr_census']}"
          f"  |  GTOW decisions bucketed={s['gtow_decisions']}  class_err={s['class_err']}")

    print(f"\n=== TOP {top_n} GTOW buckets by n  (street|node|pot|class|texture -> mix, mean size) ===")
    ranked = sorted(r["buckets"].items(), key=lambda kv: -sum(kv[1]["acts"].values()))
    for key, b in ranked[:top_n]:
        n = sum(b["acts"].values())
        sizes = []
        if b["bet_n"]:
            sizes.append(f"bet~{b['bet_sum'] / b['bet_n']:.2f}pot")
        if b["raise_n"]:
            sizes.append(f"raise~{b['raise_sum'] / b['raise_n']:.2f}pot")
        print(f"  {'|'.join(key):58s} n={n:5d}  {_mix(b['acts'])}  {' '.join(sizes)}")

    print("\n=== (1) GTOW FACING a 2nd+ barrel (turn/river facing-bet, same opponent barreled prior street) ===")
    combined = Counter()
    for (street, cls), mix in sorted(r["barrel"].items()):
        if cls in ONE_PAIR_CLASSES:
            combined += mix
        print(f"  {street:5s} {cls:9s} n={sum(mix.values()):4d}  {_mix(mix)}")
    print(f"  >> ONE PAIR combined (pair+top-pair): n={sum(combined.values())}  {_mix(combined)}")

    print("\n=== (2) GTOW river BLUFF share (air% of its river first-in bets) per pot-type ===")
    for pot, mix in sorted(r["river_bets"].items(), key=lambda kv: -sum(kv[1].values())):
        n = sum(mix.values())
        fsum, fn = r["river_bet_frac"][pot]
        size = f" mean size {fsum / fn:.2f}pot" if fn else ""
        print(f"  {pot:6s} n={n:4d}  air={100 * _share(mix, ['air']):.0f}%  "
              f"one-pair={100 * _share(mix, ONE_PAIR_CLASSES):.0f}%  "
              f"2p+={100 * _share(mix, ['two-pair+']):.0f}%  monster={100 * _share(mix, ['monster']):.0f}%{size}")
    print(f"  (river raises, not counted above: {dict(r['river_raises']) or 0})")

    print("\n=== (3) GTOW flop CHECK-BACK (in position, checked to) ===")
    node_n = sum(r["cb_node"].values())
    print(f"  node n={node_n}  {_mix(r['cb_node'])}")
    ck = r["cb_checks"]
    print(f"  check-back composition (n={sum(ck.values())}): {_mix(ck)}")
    print(f"  trap share (two-pair+/monster among checks) = {100 * _share(ck, TRAP_CLASSES):.1f}%")
    print(f"  bet range for contrast (n={sum(r['cb_bets'].values())}): {_mix(r['cb_bets'])}")


def save_json(r: dict, files: list[str], out_path: str):
    def freq(counter: Counter) -> dict:
        n = sum(counter.values())
        return {a: round(c / n, 4) for a, c in counter.most_common()}

    buckets = {}
    for key, b in r["buckets"].items():
        n = sum(b["acts"].values())
        buckets["|".join(key)] = {
            "n": n, "freq": freq(b["acts"]), "counts": dict(b["acts"]),
            "mean_bet_frac": round(b["bet_sum"] / b["bet_n"], 4) if b["bet_n"] else None,
            "n_bet_sized": b["bet_n"],
            "mean_raise_frac": round(b["raise_sum"] / b["raise_n"], 4) if b["raise_n"] else None,
            "n_raise_sized": b["raise_n"],
        }
    out = {
        "meta": {
            "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "files": files, "stats": dict(r["stats"]),
            "key": "street|node-class|pot-type|hand-class|board-texture",
            "node_classes": "first-in-after-check (no live bet) / facing-bet (1 aggression level; the "
                            "BB post counts preflop, so preflop|facing-bet|limped = the SB RFI node) / "
                            "facing-raise (2+ levels; preflop|facing-raise|SRP = BB vs an open)",
            "hand_classes": "air/pair/top-pair(incl. overpair)/two-pair+(thru straight)/monster(flush+); "
                            "board-made hands demoted (board pair->air, board plays->air)",
            "sizes": "bet = to/pot; raise = increment over the call / post-call pot",
            "hero_id": "gtow_tree_census net-match vs logged winnings, cross-checked vs gtow_folded; "
                       "GTOW = the other seat",
            "caveat": "GTOW's HU play conditioned on OUR lines (spot distribution shaped by our hero eras)",
        },
        "buckets": buckets,
        "specials": {
            "facing_2nd_plus_barrel": {f"{st}|{cls}": {"n": sum(m.values()), "freq": freq(m)}
                                       for (st, cls), m in sorted(r["barrel"].items())},
            "river_bluff_share": {pot: {"n_bets": sum(m.values()), "class_mix": freq(m),
                                        "air_share": round(_share(m, ["air"]), 4),
                                        "mean_bet_frac": (round(r["river_bet_frac"][pot][0]
                                                                / r["river_bet_frac"][pot][1], 4)
                                                          if r["river_bet_frac"][pot][1] else None)}
                                  for pot, m in r["river_bets"].items()},
            "river_raises_n": dict(r["river_raises"]),
            "flop_checkback_ip": {"node_actions": dict(r["cb_node"]),
                                  "check_composition": freq(r["cb_checks"]),
                                  "trap_share": round(_share(r["cb_checks"], TRAP_CLASSES), 4),
                                  "n_checks": sum(r["cb_checks"].values()),
                                  "bet_composition": freq(r["cb_bets"])},
        },
    }
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    json.dump(out, open(out_path, "w", encoding="utf-8"), indent=1)
    print(f"\nsaved {out_path}  ({len(buckets)} buckets)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", default="data/sessions/gtow_hands_*.jsonl")
    ap.add_argument("--out", default="data/freq_targets/gtow_frequencies.json")
    ap.add_argument("--top", type=int, default=20)
    args = ap.parse_args()
    files = sorted(glob.glob(args.files))
    r = mine(files)
    print_report(r, args.top)
    save_json(r, files, args.out)


if __name__ == "__main__":
    main()
