"""Read the GTO solver cache built by the local mass-solve and surface what TRUE GTO does on these flops:
the OOP donk/check strategy and the IP c-bet-after-check strategy, broken down by board texture. Turns the
raw cache into immediate, actionable patterns (and flags where our analytic baseline likely deviates).

Run: python -m extraction.analyze_cache
"""
from __future__ import annotations

import collections
import json

from pokerbot import config

CACHE = config.DATA_DIR / "_gto_bench_cache"
_ORDER = "23456789TJQKA"


def texture(board: str):
    cards = [board[i:i + 2] for i in range(0, 6, 2)]
    ranks = [c[0] for c in cards]
    suits = [c[1] for c in cards]
    idx = sorted((_ORDER.index(r) for r in ranks), reverse=True)
    paired = len(set(ranks)) < 3
    tags = ["paired" if paired else {1: "monotone", 2: "two-tone", 3: "rainbow"}[len(set(suits))]]
    tags.append("high" if idx[0] >= _ORDER.index("T") else "low")
    if not paired and (idx[0] - idx[2]) <= 4:
        tags.append("connected")
    return tags


def mix(node):
    """Mean action probabilities over all combos at this node -> {action_label: freq}."""
    strat = (node or {}).get("strategy", {})
    actions = strat.get("actions", [])
    combos = strat.get("strategy", {})
    if not actions or not combos:
        return None
    agg = [0.0] * len(actions)
    n = 0
    for probs in combos.values():
        if len(probs) == len(actions):
            for i, p in enumerate(probs):
                agg[i] += p
            n += 1
    return {a: agg[i] / n for i, a in enumerate(actions)} if n else None


def child_after_check(node):
    for k, v in (node.get("childrens", {}) or {}).items():
        if k.upper().startswith("CHECK"):
            return v
    return None


def bet_freq(m):
    return sum(p for a, p in m.items() if a.split()[0].upper() in ("BET", "RAISE", "ALLIN"))


def main():
    files = list(CACHE.glob("*.json"))
    print(f"GTO cache: {len(files)} solved flops")
    oop_bet = collections.defaultdict(list)
    ip_cbet = collections.defaultdict(list)
    ip_size = collections.Counter()
    n_ok = 0
    for f in files:
        try:
            node = json.loads(f.read_text())
        except Exception:  # noqa: BLE001
            continue
        rm = mix(node)
        if not rm:
            continue
        tags = texture(f.stem)
        for t in tags + ["ALL"]:
            oop_bet[t].append(bet_freq(rm))
        cm = mix(child_after_check(node))
        if cm:
            cb = bet_freq(cm)
            for t in tags + ["ALL"]:
                ip_cbet[t].append(cb)
            for a, p in cm.items():
                if a.split()[0].upper() == "BET":
                    ip_size[a] += p
        n_ok += 1

    def line(d, t):
        v = d.get(t, [])
        return f"  {t:11} n={len(v):4}  {sum(v) / len(v) * 100:5.1f}%" if v else f"  {t:11} n=0"

    order = ["ALL", "paired", "monotone", "two-tone", "rainbow", "high", "low", "connected"]
    print(f"parsed {n_ok} boards with a readable root strategy\n")
    print("OOP donk-bet frequency (BB first to act, single-raised pot) -- GTO donks rarely:")
    for t in order:
        print(line(oop_bet, t))
    print("\nIP c-bet frequency (BTN after OOP checks):")
    for t in order:
        print(line(ip_cbet, t))
    tot = sum(ip_size.values()) or 1.0
    print("\nIP c-bet SIZE preference (share of c-bet mass):")
    for a, p in sorted(ip_size.items(), key=lambda kv: -kv[1]):
        print(f"  {a:18} {p / tot * 100:5.1f}%")


if __name__ == "__main__":
    main()
