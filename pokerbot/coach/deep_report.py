"""The DEEP player-report analytics (docs plan 2026-07-01). Turns a CoinPoker history into a rich PORTRAIT: temporal
A/B/C-game phases, variance magnitude, bet-sizing entropy ("confusion"), and the player's ACTUAL observed ranges.

Pure-local + $0 (the LLM interpretation, bot-sim, charts, and PDF are separate steps). Reuses pokerbot/coach/
coinpoker.py (parse + hero_decisions). HARD RULE for the eventual report: no money/losses — only low/mid/high tiers.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict

from pokerbot.coach import coinpoker

_RANKS = "23456789TJQKA"          # low -> high
_SESSION_GAP_MIN = 45             # a gap > this (minutes) starts a new session


def tier(bb: float) -> str:
    """Stake tier WITHOUT money: BB<1 = low (NL2-50), BB in {1,2} = mid (NL100/200), BB>=5 = high (NL500+)."""
    return "low" if bb < 1 else ("mid" if bb <= 2 else "high")


def hand_class(hole: list) -> str:
    """['As','Kd'] -> 'AKo' / ['As','Ks'] -> 'AKs' / ['As','Ah'] -> 'AA' (higher card first)."""
    (r1, s1), (r2, s2) = hole[0], hole[1]
    hi, lo = sorted([r1, r2], key=_RANKS.index, reverse=True)
    if hi == lo:
        return hi + lo
    return hi + lo + ("s" if s1 == s2 else "o")


def _timestamps(path: str) -> dict:
    """hid -> minutes-since-epoch-ish (a monotone integer for gap detection), parsed from the raw headers."""
    out = {}
    for m in re.finditer(r"Hand #(\d+): NLH \([^)]*\)\s+(\d{4})/(\d{2})/(\d{2})\s+(\d{2}):(\d{2}):(\d{2})",
                         open(path, encoding="utf-8", errors="replace").read()):
        hid, y, mo, da, hh, mm, ss = m.groups()
        # a simple monotone minute counter (days*1440 + h*60 + m); good enough for ordering + gaps within the file
        minutes = ((int(y) * 372 + int(mo) * 31 + int(da)) * 1440) + int(hh) * 60 + int(mm)
        out[hid] = minutes
    return out


def _preflop_role(hand) -> str | None:
    """Hero's first voluntary preflop action: 'open'|'3bet'|'call'|'limp'|'fold'|None (checked BB / not dealt in)."""
    hero, raises = hand.hero_seat, 0
    for a in hand.actions:
        if a["street"] != "preflop":
            break
        if a["seat"] == hero and a["act"] in ("fold", "check", "call", "raise", "allin", "bet"):
            if a["act"] == "fold":
                return "fold"
            if a["act"] == "check":
                return None
            if a["act"] == "call":
                return "limp" if raises == 0 else "call"
            return "open" if raises == 0 else "3bet"          # raise / allin / bet
        if a["act"] in ("raise", "allin") and a["seat"] != hero:
            raises += 1
    return None


def _hand_row(hand) -> dict:
    """Per-hand extraction: tier, net in bb, position, preflop role, all-in, + postflop aggression counts + bet sizes."""
    s = coinpoker.summary(hand)
    aggr = calls = 0                                          # postflop aggression (bet/raise/all-in) vs calls
    sizes = []                                                # bet/raise size as fraction of pot (postflop)
    for d in coinpoker.hero_decisions(hand):
        if d.street == "preflop":
            continue
        if d.action in ("bet", "raise", "all-in"):
            aggr += 1
            if d.amount_bb and d.spot.pot > 0 and d.action != "all-in":
                sizes.append(round(d.amount_bb * d.spot.bb / d.spot.pot, 2))
        elif d.action == "call":
            calls += 1
    af = aggr / calls if calls else float(aggr)
    return {"hid": hand.hid, "bb": hand.bb, "tier": tier(hand.bb), "date": hand.date,
            "net_bb": round(s["net"] / hand.bb, 3), "pos": hand.pos.get(hand.hero_seat, "?"),
            "role": _preflop_role(hand), "vpip": s["vpip"], "pfr": s["pfr"], "wtsd": s["wtsd"],
            "allin": s["allin"], "pf_aggr": aggr, "pf_calls": calls, "af": round(af, 2),
            "sizes": sizes, "hole": hand.hole if hasattr(hand, "hole") else hand.hero_hole,
            "hc": hand_class(hand.hero_hole) if len(hand.hero_hole) == 2 else None}


def sessions(rows: list, ts: dict) -> list:
    """Cluster hands into sessions: contiguous blocks with < 45-min gaps. Each session = dict of aggregate metrics."""
    ordered = sorted(rows, key=lambda r: (ts.get(r["hid"], 0)))
    blocks, cur, last = [], [], None
    for r in ordered:
        t = ts.get(r["hid"], 0)
        if last is not None and t - last > _SESSION_GAP_MIN:
            blocks.append(cur); cur = []
        cur.append(r); last = t
    if cur:
        blocks.append(cur)
    return [_session_metrics(b) for b in blocks]


def _session_metrics(block: list) -> dict:
    n = len(block)
    tc = Counter(r["tier"] for r in block)
    vpip = 100 * sum(r["vpip"] for r in block) / n
    pfr = 100 * sum(r["pfr"] for r in block) / n
    allin = 100 * sum(r["allin"] for r in block) / n
    afs = [r["af"] for r in block if r["pf_calls"] + r["pf_aggr"] > 0]
    af = sum(afs) / len(afs) if afs else 0.0
    m = {"n": n, "date": block[0]["date"], "tier": tc.most_common(1)[0][0], "tiers": dict(tc),
         "vpip": round(vpip, 1), "pfr": round(pfr, 1), "allin_rate": round(allin, 1), "af": round(af, 2),
         "vpip_pfr_gap": round(vpip - pfr, 1)}
    m["game_level"] = _game_level(m)
    return m


def _game_level(m: dict) -> str:
    """CONSTRUCTED index (honest label: an engineered proxy, not canonical) — calibrated to a LOOSE-AGGRESSIVE player,
    so 'A' is NOT about playing few hands. A = focused + controlled-aggressive on serious stakes; C = the 'playful',
    experimental, high-variance end (mostly the micro warm-up). Stakes-seriousness is the dominant signal (the user's
    own framing), modified by aggression-discipline + variance-control."""
    score = {"high": 3, "mid": 2, "low": 0}[m["tier"]]        # serious stakes = the A-game arena
    score += 1 if m["vpip_pfr_gap"] <= 25 else 0             # raising, not passively limping (the real leak)
    score += 1 if m["allin_rate"] <= 15 else 0               # variance under control
    score += 1 if 1.3 <= m["af"] <= 6 else 0                 # controlled aggression (not passive, not pure spew)
    return "A" if score >= 5 else ("B" if score >= 3 else "C")


def variance_stats(rows: list) -> dict:
    """Quantify SWING MAGNITUDE (no money, no 'losses'): std-dev of per-hand result in bb, and the peak-to-valley
    swing amplitude of the running sum in bb. Reported as volatility, framed positively later."""
    nets = [r["net_bb"] for r in rows]
    n = len(nets)
    mean = sum(nets) / n
    std = math.sqrt(sum((x - mean) ** 2 for x in nets) / n)
    run, peak, valley, amp = 0.0, 0.0, 0.0, 0.0               # running sum extremes -> swing amplitude
    for x in nets:
        run += x
        peak = max(peak, run); valley = min(valley, run)
        amp = max(amp, peak - run, run - valley)
    return {"n": n, "std_per_hand_bb": round(std, 2), "swing_amplitude_bb": round(amp, 1),
            "std_per_100_bb": round(std * 10, 1)}            # per-100 std ~ per-hand std * sqrt(100)


def sizing_entropy(rows: list) -> dict:
    """'Confusion' proxy: Shannon entropy (bits) of the postflop bet-size distribution (bucketed by pot-fraction).
    Higher entropy = more varied/unpredictable sizing. Also the raw distribution for a chart."""
    buckets = {"<=0.4x": 0, "0.4-0.7x": 0, "0.7-1.1x": 0, ">1.1x (overbet)": 0}
    for r in rows:
        for s in r["sizes"]:
            k = "<=0.4x" if s <= 0.4 else ("0.4-0.7x" if s <= 0.7 else ("0.7-1.1x" if s <= 1.1 else ">1.1x (overbet)"))
            buckets[k] += 1
    total = sum(buckets.values()) or 1
    probs = [v / total for v in buckets.values() if v]
    ent = -sum(p * math.log2(p) for p in probs)
    return {"entropy_bits": round(ent, 2), "max_bits": 2.0, "distribution": buckets, "n_bets": total}


def observed_ranges(rows: list, tiers: set) -> dict:
    """The player's ACTUAL played hands (hero cards are always known): {pos: {role: Counter(hand_class)}}. Filtered
    to the given stake tiers. Roles: open / 3bet / call / limp."""
    out = defaultdict(lambda: defaultdict(Counter))
    for r in rows:
        if r["tier"] not in tiers or not r["hc"] or r["role"] not in ("open", "3bet", "call", "limp"):
            continue
        out[r["pos"]][r["role"]][r["hc"]] += 1
    return {p: {role: dict(c) for role, c in d.items()} for p, d in out.items()}


def main():
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\hampe\Desktop\CoinPoker_Princedarkness_2026-02-01_to_2026-07-01_Cash.txt"
    hands = [h for h in coinpoker.parse_file(path) if h.hero_seat is not None]
    ts = _timestamps(path)
    rows = [_hand_row(h) for h in hands]
    sess = sessions(rows, ts)
    mid_high = {"mid", "high"}
    out = {
        "n_hands": len(rows),
        "n_sessions": len(sess),
        "by_tier": {t: sum(1 for r in rows if r["tier"] == t) for t in ("low", "mid", "high")},
        "sessions": sess,
        "game_level_dist": dict(Counter(s["game_level"] for s in sess)),
        "hands_by_level": {L: sum(s["n"] for s in sess if s["game_level"] == L) for L in "ABC"},
        "variance": variance_stats(rows),
        "variance_serious": variance_stats([r for r in rows if r["tier"] in mid_high]),
        "entropy": sizing_entropy([r for r in rows if r["tier"] in mid_high]),
        "ranges": observed_ranges(rows, mid_high),
    }
    json.dump(out, open("data/coach/deep_stats.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # per-hand result spread for the (symmetric, direction-free) variance chart — mid+high only
    nets = [r["net_bb"] for r in rows if r["tier"] in mid_high]
    json.dump(nets, open("data/coach/_hand_nets.json", "w", encoding="utf-8"))
    print(f"hands {out['n_hands']} | sessions {out['n_sessions']} | by_tier {out['by_tier']}")
    print(f"game-level sessions {out['game_level_dist']} | hands {out['hands_by_level']}")
    print(f"variance ALL: {out['variance']}")
    print(f"variance mid+high: {out['variance_serious']}")
    print(f"sizing entropy mid+high: {out['entropy']['entropy_bits']}/2.0 bits  dist {out['entropy']['distribution']}")
    print(f"positions with observed ranges: {list(out['ranges'].keys())}")
    print("saved data/coach/deep_stats.json")


if __name__ == "__main__":
    main()
