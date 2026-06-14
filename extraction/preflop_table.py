"""SYNTHESIS_PLAN Step 2: distill PokerBench preflop spots into a GTO lookup table that GENERALIZES
(key = hero_pos + level + last-raiser-pos + 169 hand-class), then measure action-match on the held-out TEST
split (the grounded gate, target >95%). This is the exact-data preflop floor -- no LLM. Saves the table for
wiring into the bot.  Run: python -m extraction.preflop_table
"""
from __future__ import annotations

import json
import re
import statistics
from collections import Counter, defaultdict

from datasets import load_dataset

from pokerbot import config

RANKS = "23456789TJQKA"
_RANKW = {"two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8",
          "nine": "9", "ten": "T", "jack": "J", "queen": "Q", "king": "K", "ace": "A"}
_SUITW = {"spade": "s", "heart": "h", "diamond": "d", "club": "c"}
_CARD = re.compile(r"([A-Za-z]+)\s+of\s+([A-Za-z]+)", re.I)


def _cards(text):
    out = []
    for r, s in _CARD.findall(text):
        rr, ss = _RANKW.get(r.lower()), _SUITW.get(s.lower())
        if rr and ss:
            out.append(rr + ss)
    return out


def hand_class(cs):
    if len(cs) != 2:
        return None
    r1, s1 = cs[0][0], cs[0][1]
    r2, s2 = cs[1][0], cs[1][1]
    if RANKS.index(r1) < RANKS.index(r2):
        r1, s1, r2, s2 = r2, s2, r1, s1
    if r1 == r2:
        return r1 + r2
    return r1 + r2 + ("s" if s1 == s2 else "o")


def parse_seq(instr):
    m = re.search(r"Before the flop,\s*(.+?)\.\s*(?:Assume|Now)", instr, re.S)
    txt = m.group(1) if m else ""
    if "no action" in txt:
        return []
    seq = []
    for part in re.split(r",|\band\b", txt):
        pm = re.search(r"(UTG|HJ|CO|BTN|SB|BB)\s+(raise|call|fold|check|all\s*in|bet)", part)
        if pm:
            act = pm.group(2).replace(" ", "")
            seq.append((pm.group(1), "allin" if "allin" in act else act))
    return seq


def act_type(s):
    w = s.strip().lower().split()
    if not w:
        return ""
    return "allin" if w[0] == "all" else w[0]


def key_of(instr):
    pos = re.search(r"your position is (\w+)", instr)
    hold = re.search(r"holding is \[([^\]]+)\]", instr)
    if not (pos and hold):
        return None
    hc = hand_class(_cards(hold.group(1)))
    if not hc:
        return None
    seq = parse_seq(instr)
    raisers = [p for p, a in seq if a in ("raise", "allin")]
    level = len(raisers)
    first_r = raisers[0] if raisers else "none"
    last_r = raisers[-1] if raisers else "none"
    ncall = min(2, sum(1 for _, a in seq if a == "call"))
    # full key (precise) -> backoff keys derived in build/predict
    return (pos.group(1), level, first_r, last_r, ncall, hc)


def _backoffs(k):
    """full -> drop ncall -> drop first-raiser -> pos+level+hand."""
    pos, lvl, first_r, last_r, ncall, hc = k
    return [k,
            (pos, lvl, first_r, last_r, hc),
            (pos, lvl, last_r, hc),
            (pos, lvl, hc)]


def main():
    tr = load_dataset("RZ412/PokerBench", "default", split="train")
    te = load_dataset("RZ412/PokerBench", "default", split="test")
    tabs = [defaultdict(Counter) for _ in range(4)]   # one table per backoff granularity
    amts = defaultdict(list)
    npre = 0
    for r in tr:
        if "flop comes" in r["instruction"].lower():
            continue
        k = key_of(r["instruction"])
        at = act_type(r["output"])
        if not k or not at:
            continue
        for t, bk in zip(tabs, _backoffs(k)):
            t[bk][at] += 1
        npre += 1
        if at == "raise":
            mm = re.search(r"([\d.]+)", r["output"])
            if mm:
                amts[k].append(float(mm.group(1)))
    print(f"preflop train rows: {npre} | full keys: {len(tabs[0])} (backoff {[len(t) for t in tabs]})", flush=True)

    def predict(k):
        for depth, (t, bk) in enumerate(zip(tabs, _backoffs(k))):
            if bk in t:
                return t[bk].most_common(1)[0][0], depth
        return "fold", 9

    hit = tot = 0
    by_lvl = defaultdict(lambda: [0, 0])
    depths = Counter()
    for r in te:
        if "flop comes" in r["instruction"].lower():
            continue
        k = key_of(r["instruction"])
        gold = act_type(r["output"])
        if not k or not gold:
            continue
        pred, depth = predict(k)
        tot += 1
        hit += (pred == gold)
        depths[depth] += 1
        by_lvl[k[1]][1] += 1
        by_lvl[k[1]][0] += (pred == gold)
    print(f"TEST preflop: action-match {100*hit/tot:.1f}% ({hit}/{tot}) | full-key hits {100*depths[0]/tot:.0f}%",
          flush=True)
    for lvl in sorted(by_lvl):
        h, n = by_lvl[lvl]
        name = {0: "RFI/limp", 1: "vs-raise", 2: "vs-3bet", 3: "vs-4bet"}.get(lvl, f"lvl{lvl}")
        print(f"   {name:10}: {100*h/n:.1f}% ({h}/{n})", flush=True)

    out = {}
    for k, c in tabs[0].items():
        tot_k = sum(c.values())
        kk = f"{k[0]}|{k[1]}|{k[2]}|{k[3]}|{k[4]}|{k[5]}"
        rec = {"action": c.most_common(1)[0][0], "n": tot_k,
               "mix": {a: round(n / tot_k, 3) for a, n in c.items()}}   # full distribution for mixed play
        if amts.get(k):
            rec["raise_bb"] = round(statistics.median(amts[k]), 1)
        out[kk] = rec
    p = config.KNOWLEDGE_DIR / "ranges" / "preflop_gto_table.json"
    p.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(f"saved {len(out)} keys -> {p}", flush=True)


if __name__ == "__main__":
    main()
