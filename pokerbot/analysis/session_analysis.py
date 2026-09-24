"""Compute the human's poker stats from a session log and produce an LLM narrative."""
from __future__ import annotations

import json

from pokerbot import config


def _load(path) -> list[dict]:
    recs = []
    try:
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    except OSError:
        pass
    return recs


def compute_stats(recs: list[dict]) -> dict:
    hands = len(recs)
    if not hands:
        return {"hands": 0}
    vpip = pfr = threebet = 0
    pf_bets = pf_calls = 0
    pf_raises_total = 0
    po_bets = po_raises = po_calls = po_folds = 0
    net_bb = 0.0
    showdowns = 0
    bet_sizes: list[float] = []
    for rec in recs:
        hs = str(rec.get("human_seat"))
        bb = rec.get("bb", 100)
        net = rec.get("net", {})
        net_bb += float(net.get(hs, net.get(int(hs) if hs.isdigit() else hs, 0))) / bb
        acts = rec.get("actions", [])
        h_pf = [a for a in acts if a["is_human"] and a["street"] == "preflop"]
        if any(a["action"] in ("call", "bet", "raise") for a in h_pf):
            vpip += 1
        if any(a["action"] in ("bet", "raise") for a in h_pf):
            pfr += 1
        pf_all_raises = [a for a in acts if a["street"] == "preflop" and a["action"] in ("bet", "raise")]
        if any(a["is_human"] for a in pf_all_raises) and len(pf_all_raises) >= 2:
            threebet += 1
        for a in acts:
            if not a["is_human"]:
                continue
            if a["street"] == "preflop":
                pf_bets += a["action"] in ("bet", "raise")
                pf_calls += a["action"] == "call"
            else:
                po_bets += a["action"] == "bet"
                po_raises += a["action"] == "raise"
                po_calls += a["action"] == "call"
                po_folds += a["action"] == "fold"
                if a["action"] in ("bet", "raise") and a.get("amount"):
                    bet_sizes.append(a["amount"] / bb)
        if rec.get("result", {}).get("reason") == "showdown" \
                and not _folded(rec, hs):
            showdowns += 1
    return {
        "hands": hands,
        "vpip_pct": round(100 * vpip / hands, 1),
        "pfr_pct": round(100 * pfr / hands, 1),
        "threebet_pct": round(100 * threebet / hands, 1),
        "postflop_aggression_factor": round((po_bets + po_raises) / max(1, po_calls), 2),
        "postflop": {"bets": po_bets, "raises": po_raises, "calls": po_calls, "folds": po_folds},
        "went_to_showdown_pct": round(100 * showdowns / hands, 1),
        "net_bb": round(net_bb, 1),
        "bb_per_100": round(net_bb / hands * 100, 1),
        "avg_postflop_bet_bb": round(sum(bet_sizes) / len(bet_sizes), 1) if bet_sizes else None,
    }


def _folded(rec: dict, hs: str) -> bool:
    return any(a["is_human"] and a["action"] == "fold" for a in rec.get("actions", []))


def narrative(stats: dict) -> str:
    if not config.ANTHROPIC_API_KEY or stats.get("hands", 0) == 0:
        return ""
    import anthropic
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    sys = ("You are a heads-up/6-max poker coach. Analyze a player's session stats honestly and "
           "concretely: style classification (tight/loose, passive/aggressive), the biggest leaks, "
           "and 3 concrete improvements. Refer to the numbers (VPIP, PFR, aggression, bb/100). "
           "Answer in English, concise (max ~180 words).")
    try:
        msg = client.messages.create(
            model=config.CLAUDE_MODEL, max_tokens=600,
            system=sys,
            messages=[{"role": "user", "content":
                       f"Session stats (6-max, {stats['hands']} hands):\n{json.dumps(stats, ensure_ascii=False, indent=2)}"}])
        return "".join(b.text for b in msg.content if b.type == "text").strip()
    except Exception as e:  # noqa: BLE001
        return f"(Analysis text unavailable: {type(e).__name__})"


def analyze_session(path) -> dict:
    recs = _load(path)
    stats = compute_stats(recs)
    return {"stats": stats, "narrative": narrative(stats)}
