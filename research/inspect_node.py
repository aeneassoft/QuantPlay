"""Inspect a DUMP=2 cache file: reveal the chance_node (turn-deal) raw structure for the #41 turn extractor."""
from __future__ import annotations

import json

from pokerbot import config

CACHE = config.DATA_DIR / "_gto_bench_cache"
files = sorted(CACHE.glob("*.json"), key=lambda p: p.stat().st_size, reverse=True)
f = files[0]
node = json.loads(f.read_text(encoding="utf-8"))
print(f"FILE {f.name}  size={f.stat().st_size}")
print("ROOT keys:", list(node.keys()))


def find_chance(n, depth=0):
    if not isinstance(n, dict):
        return None
    if n.get("node_type") == "chance_node" and depth > 0:
        return n
    for c in (n.get("childrens") or {}).values():
        r = find_chance(c, depth + 1)
        if r:
            return r
    return None


cn = find_chance(node)
if not cn:
    print("NO chance node found")
else:
    print("\nCHANCE node keys:", list(cn.keys()))
    for k, v in cn.items():
        if isinstance(v, dict):
            print(f"  {k}: dict[{len(v)}] sample_keys={list(v.keys())[:4]}")
        elif isinstance(v, list):
            print(f"  {k}: list[{len(v)}] sample={v[:4]}")
        else:
            print(f"  {k}: {v}")
    dc = cn.get("dealcards") or cn.get("deal_cards") or {}
    if isinstance(dc, dict) and dc:
        ck = list(dc.keys())[0]
        sub = dc[ck]
        print(f"\nTURN subtree under card '{ck}':")
        if isinstance(sub, dict):
            print("  keys:", list(sub.keys()))
            s = sub.get("strategy", {}) or {}
            print(f"  node_type={sub.get('node_type')} actions={s.get('actions')} "
                  f"combos={len(s.get('strategy', {}) or {})} children={list((sub.get('childrens') or {}).keys())[:6]}")
