"""Parse & catalog the 10,000 Pluribus (superhuman 6-max) hand histories from the PHH dataset.

Normalizes every hand into our schema (-> knowledge_base/hand_histories/pluribus_hands.jsonl) and
computes Pluribus's aggregate stats by position (VPIP/PFR/open-size/net), so we can study/emulate
how a superhuman bot actually plays 6-max.

Run:  python -m pokerbot.analysis.pluribus_catalog
"""
from __future__ import annotations

import json
import tomllib
from collections import defaultdict
from pathlib import Path

from pokerbot import config

SRC = config.ROOT / "data" / "_phh_repo" / "data" / "pluribus"
OUT_DIR = config.KNOWLEDGE_DIR / "hand_histories"
POS6 = ["BTN", "SB", "BB", "UTG", "MP", "CO"]


def parse_hand(path: Path) -> dict | None:
    with open(path, "rb") as f:
        d = tomllib.load(f)
    players = d.get("players", [])
    n = len(players)
    blinds = d.get("blinds_or_straddles", [])
    starting = d.get("starting_stacks", [])
    finishing = d.get("finishing_stacks", [])
    if not players or not blinds:
        return None
    sb_amt = min((b for b in blinds if b > 0), default=0)
    sb_idx = blinds.index(sb_amt) if sb_amt else 0
    button = (sb_idx - 1) % n
    bb = max(blinds) if blinds else 100

    holes: dict[int, str] = {}
    board: list[str] = []
    acts: list[dict] = []
    street = "preflop"
    for a in d.get("actions", []):
        tok = a.split()
        if tok[0] == "d":
            if tok[1] == "dh":               # deal hole
                holes[int(tok[2][1:]) - 1] = tok[3]
            elif tok[1] == "db":             # deal board
                cards = tok[2]
                board += [cards[i:i + 2] for i in range(0, len(cards), 2)]
                street = {3: "flop", 4: "turn", 5: "river"}.get(len(board), street)
            continue
        seat = int(tok[0][1:]) - 1
        verb = tok[1]
        amt = int(tok[2]) if verb == "cbr" and len(tok) > 2 else None
        if verb == "sm":
            continue
        acts.append({"seat": seat, "verb": verb, "amount": amt, "street": street})

    def pos(seat):
        return POS6[(seat - button) % n] if n == 6 else f"S{(seat - button) % n}"

    net = {i: (finishing[i] - starting[i]) if i < len(finishing) and i < len(starting) else 0
           for i in range(n)}
    return {"hand": d.get("hand"), "players": players, "bb": bb, "button": button,
            "positions": {i: pos(i) for i in range(n)}, "holes": holes, "board": board,
            "actions": acts, "net": net}


def classify_preflop(rec: dict, seat: int) -> tuple[bool, bool, int | None]:
    """(vpip, pfr, open_to) for a seat, by replaying preflop bets."""
    bb = rec["bb"]
    blinds = {}
    # reconstruct street commit from blinds via positions: SB=0.5bb, BB=1bb
    for i, p in rec["positions"].items():
        blinds[i] = (bb // 2 if p == "SB" else bb if p == "BB" else 0)
    commit = dict(blinds)
    current = bb
    vpip = pfr = False
    open_to = None
    for a in rec["actions"]:
        if a["street"] != "preflop":
            break
        s, v = a["seat"], a["verb"]
        if v == "cbr":
            if s == seat:
                vpip = pfr = True
                if open_to is None:
                    open_to = a["amount"]
            commit[s] = a["amount"]
            current = a["amount"]
        elif v == "cc":
            if commit.get(s, 0) < current:      # it's a call
                if s == seat:
                    vpip = True
                commit[s] = current
            # else it's a check (BB option) -> not VPIP
        # fold: nothing
    return vpip, pfr, open_to


def main() -> None:
    files = sorted(SRC.rglob("*.phh"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cat = OUT_DIR / "pluribus_hands.jsonl"
    by_pos = defaultdict(lambda: {"hands": 0, "vpip": 0, "pfr": 0, "opens": []})
    total_net = 0
    plur_seats = 0
    n_hands = 0
    with open(cat, "w", encoding="utf-8") as out:
        for fp in files:
            try:
                rec = parse_hand(fp)
            except Exception:  # noqa: BLE001
                continue
            if not rec:
                continue
            n_hands += 1
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            for seat, name in enumerate(rec["players"]):
                if name != "Pluribus":
                    continue
                plur_seats += 1
                p = rec["positions"][seat]
                vpip, pfr, open_to = classify_preflop(rec, seat)
                d = by_pos[p]
                d["hands"] += 1
                d["vpip"] += vpip
                d["pfr"] += pfr
                if open_to:
                    d["opens"].append(open_to / rec["bb"])
                total_net += rec["net"].get(seat, 0) / rec["bb"]

    stats = {"hands_catalogued": n_hands, "pluribus_player_instances": plur_seats,
             "pluribus_net_bb_per_100": round(total_net / max(1, plur_seats) * 100, 2),
             "by_position": {}}
    overall_v = overall_p = overall_h = 0
    for p in POS6:
        d = by_pos.get(p)
        if not d or not d["hands"]:
            continue
        stats["by_position"][p] = {
            "hands": d["hands"],
            "vpip_pct": round(100 * d["vpip"] / d["hands"], 1),
            "pfr_pct": round(100 * d["pfr"] / d["hands"], 1),
            "avg_open_bb": round(sum(d["opens"]) / len(d["opens"]), 2) if d["opens"] else None,
        }
        overall_v += d["vpip"]; overall_p += d["pfr"]; overall_h += d["hands"]
    stats["overall"] = {"vpip_pct": round(100 * overall_v / overall_h, 1),
                        "pfr_pct": round(100 * overall_p / overall_h, 1)}
    (OUT_DIR / "pluribus_stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")

    print(f"Catalogued {n_hands} hands -> {cat.name}")
    print(f"Pluribus net: {stats['pluribus_net_bb_per_100']} bb/100  "
          f"(over {plur_seats} player-instances)")
    print(f"Overall VPIP {stats['overall']['vpip_pct']}%  PFR {stats['overall']['pfr_pct']}%")
    print("By position:")
    for p in POS6:
        if p in stats["by_position"]:
            s = stats["by_position"][p]
            print(f"  {p:4s}: VPIP {s['vpip_pct']:5.1f}%  PFR {s['pfr_pct']:5.1f}%  "
                  f"open~{s['avg_open_bb']}bb  (n={s['hands']})")


if __name__ == "__main__":
    main()
