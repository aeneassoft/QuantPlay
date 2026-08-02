"""Pluribus-Match: unseren 6-max-Kern in PLURIBUS' Spots setzen und die Abweichung quantifizieren.

WHY (User, 2026-08-02): Der GTOW-Analyzer graded unser 6-max-Spiel absolut (85.9% / 7.61 bb/100, n=1500),
aber die Spot-Verteilung ist Self-Play. Die 10.000 Pluribus-Hände (knowledge_base/hand_histories/
pluribus_hands.jsonl, alle Hole Cards offen) sind eine ZWEITE, unabhängige Referenz: wir replayen jede
Hand, und an JEDEM Entscheidungspunkt von Pluribus fragen wir unseren `tag`-Produktkern (sixmax._decide,
read={}, aggressor-aware) mit identischer Information — gleiche Hole Cards, gleiches Board, gleiche
Action-History. Verglichen wird der Aktions-BUCKET (fold / check-call / bet-raise) + das Sizing.

EHRLICH: Pluribus ist NICHT GTO-Ground-Truth (superhuman, aber selbst gemischt & imperfekt; im Datensatz
−7.09 bb/100 vs Profis). Übereinstimmung ≠ Korrektheit; Abweichung ≠ Fehler. Systematische Divergenzen
sind LEADS (money_mine-Doktrin: Buckets sind Leads, keine Beweise), keine Verdikte. Da beide Seiten
MISCHEN, ist der Einzelspot-Vergleich verrauscht — erst das Aggregat über ~20k Entscheidungen trägt.

Amount-Semantik der Quelle (an Hand 0 verifiziert, Pot-Arithmetik schließt): 'cbr' = commit-TO des
Straßen-Levels; 'cc' = check (to_call=0) oder call; 'f' = fold. Stacks: 10.000 Chips frisch pro Hand
(Pluribus-Experiment-Setup, Science 2019). Blinds 50/100, SB=button+1, BB=button+2.

Run: python -m research.pluribus_match [--n 10000] [--json data/pluribus_match.json]
"""
from __future__ import annotations

import argparse
import json
import random
import zlib
from collections import Counter, defaultdict
from pathlib import Path

from pokerbot.arena.sixmax import PROFILES, _decide

HH_PATH = Path("knowledge_base/hand_histories/pluribus_hands.jsonl")
START_STACK = 10_000            # Pluribus-Experiment: jede Hand frische 100bb (Science-Paper-Setup)
SB_CHIPS, BB_CHIPS = 50, 100
HERO_NAME = "Pluribus"
STREETS = ("preflop", "flop", "turn", "river")
BOARD_LEN = {"preflop": 0, "flop": 3, "turn": 4, "river": 5}
# Sizing zählt nur, wenn BEIDE aggressiv sind; Verhältnis unser-TO / Pluribus-TO
SIZE_LOG_CAP = 4.0              # Verhältnisse jenseits 4x als 4x zählen (Jam-vs-Minraise-Ausreißer)


def _bucket(verb: str, to_call: int) -> str:
    if verb == "f":
        return "fold"
    if verb == "cc":
        return "check" if to_call == 0 else "call"
    return "raise"               # 'cbr'


def _our_bucket(action: str) -> str:
    return {"fold": "fold", "check": "check", "call": "call", "bet": "raise",
            "raise": "raise", "allin": "raise"}.get(action, action)


class HandSim:
    """Minimaler Replay-Simulator: hält Pot/Committed/Folded/Stacks exakt in table.py-Konventionen,
    damit obs_for-förmige Spots für sixmax._decide entstehen (Amounts = Straßen-commit-TO)."""

    def __init__(self, hand: dict):
        self.hand = hand
        self.n = len(hand["players"])
        self.button = hand["button"]
        self.stacks = {s: float(START_STACK) for s in range(self.n)}
        self.street_committed = {s: 0.0 for s in range(self.n)}
        self.total_committed = {s: 0.0 for s in range(self.n)}
        self.folded: set[int] = set()
        self.street = "preflop"
        self.current_bet = float(BB_CHIPS)
        self.min_raise = float(BB_CHIPS)
        self.preflop_raises = 0
        self.pf_aggressor: int | None = None
        sb, bbs = (self.button + 1) % self.n, (self.button + 2) % self.n
        self._commit(sb, SB_CHIPS)
        self._commit(bbs, BB_CHIPS)

    def _commit(self, seat: int, to_level: float) -> None:
        add = max(0.0, to_level - self.street_committed[seat])
        add = min(add, self.stacks[seat])
        self.stacks[seat] -= add
        self.street_committed[seat] += add
        self.total_committed[seat] += add

    def pot(self) -> float:
        return sum(self.total_committed.values())

    def new_street(self, street: str) -> None:
        self.street = street
        self.street_committed = {s: 0.0 for s in range(self.n)}
        self.current_bet = 0.0
        self.min_raise = float(BB_CHIPS)

    def to_call(self, seat: int) -> float:
        return max(0.0, self.current_bet - self.street_committed[seat])

    def obs_for(self, seat: int, board_now: list[str], hole: list[str]) -> dict:
        tc = self.to_call(seat)
        can_check = tc <= 0
        raise_min = self.current_bet + self.min_raise
        raise_max = self.street_committed[seat] + self.stacks[seat]     # commit-TO all-in
        can_raise = self.stacks[seat] > tc
        pos = self.hand["positions"][str(seat)]
        return {"hole": hole, "board": board_now, "to_call": int(tc), "pot": int(self.pot()),
                "my_stack": int(self.stacks[seat]), "bb": BB_CHIPS,
                "n_active": self.n - len(self.folded), "position": pos,
                "preflop_raises": self.preflop_raises, "cur_bet": int(self.current_bet),
                "my_committed_street": int(self.street_committed[seat]), "street": self.street,
                "can_check": can_check, "can_call": tc > 0,
                "can_raise": can_raise,
                "raise_min": int(min(raise_min, raise_max)), "raise_max": int(raise_max)}

    def apply(self, seat: int, verb: str, amount) -> None:
        if verb == "f":
            self.folded.add(seat)
            return
        if verb == "cc":
            self._commit(seat, self.current_bet)
            return
        to = float(amount or 0)                                        # 'cbr': commit-TO des Levels
        self.min_raise = max(self.min_raise, to - self.current_bet)
        self.current_bet = max(self.current_bet, to)
        self._commit(seat, to)
        if self.street == "preflop":
            self.preflop_raises += 1
            self.pf_aggressor = seat


def match_hand(hand: dict, knobs, stats: dict) -> None:
    """Replay eine Hand; an jedem Pluribus-Entscheidungspunkt unseren Kern fragen und vergleichen."""
    sim = HandSim(hand)
    hero = hand["players"].index(HERO_NAME)
    hero_hole = [hand["holes"][str(hero)][:2], hand["holes"][str(hero)][2:]]
    board = hand["board"]
    for act in hand["actions"]:
        if act["street"] != sim.street:
            sim.new_street(act["street"])
        seat, verb = act["seat"], act["verb"]
        if seat == hero and seat not in sim.folded:
            board_now = board[:BOARD_LEN[sim.street]]
            obs = sim.obs_for(seat, board_now, hero_hole)
            p_bucket = _bucket(verb, obs["to_call"])
            # deterministisch pro Spot (Mixing-Draw reproduzierbar): rng aus Hand+Aktionsindex
            rng = random.Random(zlib.crc32(f"{hand['hand']}:{len(stats['rows'])}".encode()))
            aggr = (sim.pf_aggressor == hero) if board_now else None
            try:
                ours = _decide(obs, knobs, {}, aggressor=aggr, rng=rng)
            except Exception as e:  # noqa: BLE001 — ein kaputter Spot bricht nie den Lauf
                stats["errors"] += 1
                sim.apply(seat, verb, act["amount"])
                continue
            o_bucket = _our_bucket(ours["action"])
            # check und call nie verwechselbar (to_call trennt sie) -> 3er-Vergleichsraum pro Spot
            agree = (p_bucket == o_bucket)
            # Situations-Taxonomie: preflop trennt un-eröffnet vs. vs-Raise (to_call ist preflop fast immer
            # >0 wegen der Blinds — ein 'bet'-Label wäre irreführend); postflop bet vs. checked-to.
            if sim.street == "preflop":
                facing = "pf_unopened" if sim.preflop_raises == 0 else "pf_vs_raise"
            else:
                facing = "bet" if obs["to_call"] > 0 else "checked"
            row = {"street": sim.street, "pos": obs["position"], "facing": facing,
                   "pluribus": p_bucket, "ours": o_bucket, "agree": agree}
            if p_bucket == "raise" and o_bucket == "raise" and act["amount"] and ours.get("amount"):
                ratio = min(SIZE_LOG_CAP, max(1 / SIZE_LOG_CAP, ours["amount"] / float(act["amount"])))
                row["size_ratio"] = round(ratio, 3)
            stats["rows"].append(row)
        sim.apply(seat, verb, act["amount"])


def run(n_hands: int, json_out: Path | None) -> dict:
    knobs = PROFILES["tag"]
    stats = {"rows": [], "errors": 0}
    lines = HH_PATH.read_text(encoding="utf-8").splitlines()
    for ln in lines[:n_hands]:
        hand = json.loads(ln)
        if HERO_NAME in hand["players"]:
            match_hand(hand, knobs, stats)
    rows = stats["rows"]
    n = len(rows)
    agree = sum(r["agree"] for r in rows)

    def rate(sub):
        m = [r for r in rows if sub(r)]
        return (sum(r["agree"] for r in m), len(m))

    per_street = {st: rate(lambda r, s=st: r["street"] == s) for st in STREETS}
    per_pos = {p: rate(lambda r, q=p: r["pos"] == q) for p in ("UTG", "MP", "CO", "BTN", "SB", "BB")}
    per_facing = {f: rate(lambda r, q=f: r["facing"] == q)
                  for f in ("pf_unopened", "pf_vs_raise", "checked", "bet")}
    conf = Counter((r["pluribus"], r["ours"]) for r in rows)
    ratios = [r["size_ratio"] for r in rows if "size_ratio" in r]
    ratios.sort()
    med_ratio = ratios[len(ratios) // 2] if ratios else None
    out = {
        "hands": n_hands, "decisions": n, "errors": stats["errors"],
        "agree": agree, "agree_pct": round(100 * agree / n, 2) if n else None,
        "per_street": {k: {"agree": a, "n": m, "pct": round(100 * a / m, 1) if m else None}
                       for k, (a, m) in per_street.items()},
        "per_position": {k: {"agree": a, "n": m, "pct": round(100 * a / m, 1) if m else None}
                         for k, (a, m) in per_pos.items()},
        "per_facing": {k: {"agree": a, "n": m, "pct": round(100 * a / m, 1) if m else None}
                       for k, (a, m) in per_facing.items()},
        "confusion": {f"{p}->{o}": c for (p, o), c in conf.most_common()},
        "sizing": {"n_both_raise": len(ratios), "median_ours_over_pluribus": med_ratio,
                   "p25": ratios[len(ratios) // 4] if ratios else None,
                   "p75": ratios[3 * len(ratios) // 4] if ratios else None},
    }
    if json_out:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def _report(out: dict) -> None:
    print(f"PLURIBUS-MATCH  ·  {out['hands']} Hände  ·  {out['decisions']} Pluribus-Entscheidungen  "
          f"·  Fehler {out['errors']}")
    print(f"ÜBEREINSTIMMUNG GESAMT: {out['agree_pct']}%   (fold / check / call / raise-Bucket)")
    print("  je Straße: ", {k: f"{v['pct']}% (n={v['n']})" for k, v in out["per_street"].items()})
    print("  je Position:", {k: f"{v['pct']}%" for k, v in out["per_position"].items()})
    print("  je Situation:", {k: f"{v['pct']}% (n={v['n']})" for k, v in out["per_facing"].items()})
    top = list(out["confusion"].items())[:8]
    print("  Konfusion (Pluribus->wir):", top)
    s = out["sizing"]
    print(f"  Sizing (beide raisen, n={s['n_both_raise']}): Median wir/Pluribus = "
          f"{s['median_ours_over_pluribus']}  [p25 {s['p25']} · p75 {s['p75']}]")


def _selftest() -> None:
    """Hand 0 (bekannt): Pluribus (BTN, 6c7s) foldet preflop auf das MP-Open -> genau 1 Entscheidung."""
    hand = json.loads(HH_PATH.read_text(encoding="utf-8").splitlines()[0])
    stats = {"rows": [], "errors": 0}
    match_hand(hand, PROFILES["tag"], stats)
    assert len(stats["rows"]) == 1 and stats["errors"] == 0, stats
    r = stats["rows"][0]
    assert r["pluribus"] == "fold" and r["street"] == "preflop" and r["pos"] == "BTN", r
    sim = HandSim(hand)
    for a in hand["actions"]:
        if a["street"] != sim.street:
            sim.new_street(a["street"])
        sim.apply(a["seat"], a["verb"], a["amount"])
    # 210(MP)+100(BB)+210+230(SB) = 750; SB committed 440, gewinnt 750 -> net +310 = Quelle exakt
    assert sim.pot() == 750 and sim.pot() - sim.total_committed[0] == 310, sim.pot()
    print("selftest OK: 1 BTN-Preflop-Entscheidung, Pot 750 / Net +310 schließen exakt.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10_000)
    ap.add_argument("--json", default="data/pluribus_match.json")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        _selftest()
        return
    out = run(args.n, Path(args.json))
    _report(out)


if __name__ == "__main__":
    main()
