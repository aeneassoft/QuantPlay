"""Stage C/D of the thought_log study: turn the per-decision GRADES (research/study_grade.py) into UNDERSTANDING —
the ranked LEAKS + the EDGES + the decision-time input audit + AIVAT corroboration — and SELECT the ~36 spots that
deserve an independent OpenAI 2nd-opinion (Stage E).

Deterministic, $0. Reads data/claude_play/graded_decisions.jsonl (+ thought_log + the session log for the join).

  python -m research.study_analyze                       # print the leak/edge report (Stage C) + AIVAT (Stage D)
  python -m research.study_analyze --select-review 36    # also write data/claude_play/review_spots.json for Stage E
"""
from __future__ import annotations

import argparse
import json
import os
from collections import Counter, defaultdict

from research import study_grade as SG

_PLAY = SG._PLAY_DIR
_GRADED = SG._GRADED
_REVIEW = os.path.join(_PLAY, "review_spots.json")

_OVERRIDE_RE = ("override", "size-blind", "deviat", "exploit", "vs blueprint", "judgment")


# ----------------------------------------------------------------------------------------------------------------------
# Join + classification
# ----------------------------------------------------------------------------------------------------------------------
def _load():
    graded = SG._load_jsonl(_GRADED)
    feats = {d["seq"]: d for d in SG._load_jsonl(SG._THOUGHT_LOG)}
    return graded, feats


def hand_strength_bucket(feat: dict) -> str:
    """A coarse made-hand bucket from the engine strength (postflop) or 'preflop'."""
    mh = feat.get("features", {}).get("made_hand")
    if not mh or not isinstance(mh, list) or mh[1] is None:
        return "preflop"
    s = mh[1]
    if s < 0.10:
        return "air"
    if s < 0.40:
        return "weak"
    if s < 0.70:
        return "medium"
    if s < 0.92:
        return "strong"
    return "monster"


def spot_type(rec: dict, feat: dict) -> str:
    """A coarse strategic role for the decision (the leak-clustering dimension)."""
    street = rec.get("street")
    action = rec.get("my_action")
    facing = (rec.get("to_call_bb") or 0) > 0
    if street == "preflop":
        pt = rec.get("pot_type") or "srp"
        if action == "fold":
            return f"pf_fold_{pt}"
        if action in ("bet", "raise", "allin"):
            return f"pf_aggress_{pt}"
        return f"pf_call_{pt}"
    strong = hand_strength_bucket(feat) in ("strong", "monster")
    if action in ("bet", "raise", "allin"):
        if facing:
            return "raise" + ("_value" if strong else "_bluff")
        return "bet" + ("_value" if strong else "_bluff")
    if action == "check":
        return "check"
    if action == "call":
        return "bluffcatch" if not strong else "value_call"
    if action == "fold":
        return "fold_vs_bet"
    return "other"


def _dev(rec: dict):
    """Deviation from GTO in [0,1] for a scored decision (1 - P(my action)), or None if unscored."""
    p = rec.get("gto_prob_of_mine")
    return None if p is None else round(1.0 - p, 4)


# ----------------------------------------------------------------------------------------------------------------------
# Stage C — leak / edge aggregation
# ----------------------------------------------------------------------------------------------------------------------
def _agg(rows, keyfn, feats):
    """Per-bucket: n, scored, mean P(gto), sum deviation, out-of-support count, sum equity_margin_bb, mean aivat."""
    d = defaultdict(list)
    for r in rows:
        d[keyfn(r, feats.get(r["seq"], {}))].append(r)
    out = []
    for k, rs in d.items():
        scored = [r for r in rs if r.get("gto_prob_of_mine") is not None]
        devs = [_dev(r) for r in scored]
        oos = sum(1 for r in scored if r.get("in_support") is False)
        margin = sum(r["equity_margin_bb"] for r in rs if isinstance(r.get("equity_margin_bb"), (int, float)))
        aiv = [r["hand_aivat"] for r in rs if isinstance(r.get("hand_aivat"), (int, float))]
        out.append({
            "bucket": k, "n": len(rs), "scored": len(scored),
            "mean_gto_p": round(sum(p for p in (r.get("gto_prob_of_mine") for r in scored) if p is not None) / len(scored), 3) if scored else None,
            "sum_dev": round(sum(devs), 2) if devs else 0.0,
            "out_of_support": oos,
            "sum_margin_bb": round(margin, 1),
            "mean_aivat_bb100": round(sum(aiv) / len(aiv), 1) if aiv else None,
        })
    return out


def _print_table(title, aggs, sort_key="sum_dev"):
    print(f"\n### {title}")
    print(f"  {'bucket':22s}{'n':>4s}{'scored':>7s}{'meanP(gto)':>11s}{'sumDev':>8s}{'OOS':>5s}{'margBB':>8s}{'aivat':>8s}")
    for a in sorted(aggs, key=lambda x: -(x[sort_key] or 0)):
        mp = f"{a['mean_gto_p']:.2f}" if a["mean_gto_p"] is not None else "  -"
        av = f"{a['mean_aivat_bb100']:+.0f}" if a["mean_aivat_bb100"] is not None else "  -"
        print(f"  {str(a['bucket']):22s}{a['n']:>4d}{a['scored']:>7d}{mp:>11s}"
              f"{a['sum_dev']:>8.1f}{a['out_of_support']:>5d}{a['sum_margin_bb']:>+8.1f}{av:>8s}")


def report(graded, feats):
    n = len(graded)
    scored = [r for r in graded if r.get("gto_prob_of_mine") is not None]
    print(f"=== STAGE C — LEAK / EDGE REPORT ({n} decisions, {len(scored)} scored) ===")
    buckets = Counter(r.get("grade_bucket") for r in graded)
    print(f"grade buckets: {dict(buckets)}")
    src = Counter(r.get("oracle_source") for r in graded)
    print(f"oracle source: {dict(src)}")

    # input audit
    facing = [r for r in graded if (r.get("to_call_bb") or 0) > 0 and r.get("true_required") is not None]
    inflated = [r for r in facing if r.get("input_inflated")]
    misled = [r for r in facing if r.get("cited_followed_inflated")]
    print(f"\n--- DECISION-TIME INPUT AUDIT ---")
    print(f"facing-bet spots: {len(facing)}; required_equity INFLATED at decision time: "
          f"{len(inflated)} ({len(inflated)/max(1,len(facing)):.0%}); my reasoning followed the inflated value: {len(misled)}")

    _print_table("by STREET", _agg(graded, lambda r, f: r.get("street"), feats))
    _print_table("by ACTION", _agg(graded, lambda r, f: r.get("my_action"), feats))
    _print_table("by SPOT-TYPE (sorted by total deviation = LEAKS at top)", _agg(graded, spot_type, feats))
    _print_table("by POT-TYPE", _agg(graded, lambda r, f: r.get("pot_type") or "n/a", feats))
    _print_table("by HAND-STRENGTH", _agg(graded, lambda r, f: hand_strength_bucket(f), feats))

    # the single worst decisions (highest deviation, scored) = the concrete leaks
    worst = sorted([r for r in scored if r.get("in_support") is False],
                   key=lambda r: -(_dev(r) or 0))
    print(f"\n--- WORST DECISIONS (out of GTO support, n={len(worst)}; top 12) ---")
    for r in worst[:12]:
        print(f"  seq{r['seq']:>3} {r['street']:7s} {str(r.get('my_action')):5s} "
              f"P(gto)={r.get('gto_prob_of_mine'):.2f} oracle={str(r.get('oracle_action')):6s} "
              f"aivat={_fmt(r.get('hand_aivat'))} :: {r.get('reasoning','')[:80]}")

    # edges: pure-GTO buckets we nail
    pure = [r for r in scored if r.get("gto_prob_of_mine", 0) >= SG._PURE_GTO]
    print(f"\n--- EDGES: {len(pure)}/{len(scored)} scored decisions are pure-GTO (P>= {SG._PURE_GTO}) ---")


def _fmt(x):
    return f"{x:+.0f}" if isinstance(x, (int, float)) else " -"


# ----------------------------------------------------------------------------------------------------------------------
# Stage D — AIVAT corroboration (hand-level, n=100, caveated)
# ----------------------------------------------------------------------------------------------------------------------
def aivat_corroboration(graded, feats):
    """Cross-check: do the deterministic-leak streets/buckets also carry the most-negative AIVAT? (n=100, ±22 noisy.)"""
    print("\n=== STAGE D — AIVAT CORROBORATION (hand-level, n=100, ±22 bb/100 — corroboration only) ===")
    # AIVAT is per-hand; attribute each hand once to the FINAL street it reached (mirrors gtow_xray).
    sessions = {h["hand_id"]: h for h in SG._load_jsonl(SG._SESSION)}
    by_final = defaultdict(list)
    for hid, h in sessions.items():
        if h.get("aivat") is not None:
            by_final[h.get("street") or "?"].append(h["aivat"] / 100.0 * 100)  # bb/100 (bb=100)
    N = sum(len(v) for v in by_final.values())
    overall = sum(sum(v) for v in by_final.values()) / max(1, N)
    print(f"overall AIVAT {overall:+.1f} bb/100 (n={N} hands)")
    for stt, xs in sorted(by_final.items(), key=lambda kv: sum(kv[1]) / len(kv[1])):
        print(f"  final-street {stt:8s}: mean {sum(xs)/len(xs):+7.1f} bb/100  n={len(xs):3d}  contribution {sum(xs)/N:+.1f}")
    print("NOTE: run `python -m research.gtow_xray` for the full bet-size/outcome breakdown.")


# ----------------------------------------------------------------------------------------------------------------------
# Stage E selection — the ~36 spots worth an independent OpenAI grade
# ----------------------------------------------------------------------------------------------------------------------
def select_review(graded, feats, k: int) -> list:
    """Top leak severity + disputed (grade vs aivat) + self-flagged overrides. Returns spot dicts with the rebuilt
    format_spot text + the oracle + my reasoning, deduped, capped at k."""
    from pokerbot.brain.format_spot import format_spot
    sessions = {h["hand_id"]: h for h in SG._load_jsonl(SG._SESSION)}
    tlog_by_hand = defaultdict(list)
    for d in SG._load_jsonl(SG._THOUGHT_LOG):
        tlog_by_hand[d["hand_id"]].append(d)

    def severity(r):
        sev = 0.0
        if r.get("in_support") is False and r.get("gto_prob_of_mine") is not None:
            sev += 2.0 + (_dev(r) or 0)
        if r.get("grade_bucket") == "blunder":
            sev += 2.0
        if isinstance(r.get("equity_margin_bb"), (int, float)) and r["equity_margin_bb"] < -0.5:
            sev += min(2.0, -r["equity_margin_bb"] / 5.0)
        # disputed: good grade but a very negative hand, or bad grade in a won hand
        aiv = r.get("hand_aivat")
        if isinstance(aiv, (int, float)):
            if r.get("gto_prob_of_mine", 0) and r["gto_prob_of_mine"] >= SG._PURE_GTO and aiv < -50:
                sev += 1.0
            if r.get("in_support") is False and aiv > 20:
                sev += 1.0
        if any(t in (r.get("reasoning") or "").lower() for t in _OVERRIDE_RE):
            sev += 1.0
        return sev

    ranked = sorted(graded, key=lambda r: -severity(r))
    chosen, out = set(), []
    for r in ranked:
        if severity(r) <= 0 or len(out) >= k:
            continue
        # rebuild the spot for the prompt
        decs = tlog_by_hand.get(r["hand_id"], [])
        aligned = SG._aligned_points(decs, sessions.get(r["hand_id"], {}))
        pref = aligned.get(r["seq"])
        feat = feats.get(r["seq"], {}).get("features", {})
        hero, button = SG.hero_seat_and_button(sessions.get(r["hand_id"], {}), feat.get("hero_hole", []))
        spot_text = None
        if pref and hero >= 0:
            spot = SG.reconstruct_spot(sessions[r["hand_id"]], hero, button, pref[0], pref[1])
            if spot is not None:
                spot_text = format_spot(spot)
        if not spot_text:
            continue
        out.append({
            "seq": r["seq"], "hand_id": r["hand_id"], "street": r["street"],
            "spot_text": spot_text, "my_action": r["my_action"], "my_amount_bb": r.get("my_amount_bb"),
            "my_reasoning": r.get("reasoning", ""),
            "oracle_source": r.get("oracle_source"), "oracle_mix": r.get("oracle_mix"),
            "oracle_action": r.get("oracle_action"), "gto_prob_of_mine": r.get("gto_prob_of_mine"),
            "grade_bucket": r.get("grade_bucket"), "hand_aivat": r.get("hand_aivat"),
            "severity": round(severity(r), 2),
        })
        chosen.add(r["seq"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--select-review", type=int, default=0, help="also write N review spots for Stage E")
    a = ap.parse_args()
    graded, feats = _load()
    report(graded, feats)
    aivat_corroboration(graded, feats)
    if a.select_review:
        spots = select_review(graded, feats, a.select_review)
        with open(_REVIEW, "w", encoding="utf-8") as fh:
            json.dump(spots, fh, ensure_ascii=False, indent=2)
        print(f"\nwrote {len(spots)} review spots -> {_REVIEW}")


if __name__ == "__main__":
    main()
