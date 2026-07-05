"""Grade the Claude-Code-vs-GTOW thought_log against ground truth — the core of "understanding the log".

For each of the 264 logged decisions (Claude Code itself drove the engine vs GTO Wizard, HU 200bb), we:
  1. RECONSTRUCT the exact pre-decision Spot from the SESSION history (the only place the betting LINE lives),
     reusing the battle-tested `slumbot.build_state` -> `spot_from_slumbot` seam (the same one the live bot uses).
  2. AUDIT the decision-time inputs: the live path logged `to_call`/`required_equity` from
     `gtow_to_state` (`to_call = total_pot - common_pot`), which OVER-COUNTS facing-bet spots (it logged the whole
     pot, not the call delta). We compare the LOGGED vs the TRUE (reconstructed) values -> `input_inflated`. This
     separates "the wiring fed me wrong math" from "my judgment was wrong" (a root-cause confound, not a side note).
  3. GRADE the action against the best oracle: preflop -> the stored near-Nash blueprint (free); postflop ->
     `api.solve_node` with line-aware ranges (POKERB_LINE_RANGES=1, more correct offline) + an equity-math fallback
     when the solver returns None. The EV-loss is an honest PROXY (solve_node has no per-action EV), real-bb only
     for call/fold.

Deterministic, $0 except the CPU solver. Resumable (append-only JSONL; skips seqs already graded).

  python -m research.study_grade --stage recon                 # Stage A: recon-rate + input-audit + preflop grade ($0, fast)
  python -m research.study_grade --stage grade [--threads 8] [--solve-threads 2] [--limit N]   # + postflop solving (CPU)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import threading
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

from pokerbot.benchmark.slumbot import build_state
from pokerbot.benchmark.slumbot_llm import spot_from_slumbot

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PLAY_DIR = os.path.join(_REPO, "data", "claude_play")
_THOUGHT_LOG = os.path.join(_PLAY_DIR, "thought_log.jsonl")
_SESSION = os.path.join(_REPO, "data", "sessions", "gtow_hands_1781997096.jsonl")
_ENRICHED = os.path.join(_PLAY_DIR, "enriched_decisions.jsonl")
_GRADED = os.path.join(_PLAY_DIR, "graded_decisions.jsonl")

STREETS = ["preflop", "flop", "turn", "river"]
_BOARD_LEN = {"preflop": 0, "flop": 3, "turn": 4, "river": 5}

# Grading thresholds (named, not magic — the elegance rule). A prior; tunable.
_SUPPORT_EPS = 0.02      # a GTO action played < 2% of the time is "out of support" (effectively never)
_PURE_GTO = 0.70         # >= this GTO prob = a clean, near-pure correct action
_SIZE_TOL = 0.34         # a bet/raise size within +-34% of the solver's size = "matched" (else size_mismatch)
_REQ_TOL = 0.03          # logged-vs-true required-equity gap above this = an inflated decision-time input
_MARGIN_BB_BLUNDER = 1.0 # a folded +EV call worth >= 1bb (or a call that's <= -1bb) = a quantified mistake


# ----------------------------------------------------------------------------------------------------------------------
# Loading + the session<->thought join
# ----------------------------------------------------------------------------------------------------------------------
def _load_jsonl(path: str) -> list:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(ln) for ln in fh if ln.strip()]


def _parse_cards(s: str) -> list:
    """'2c7h5hKcKs' -> ['2c','7h','5h','Kc','Ks']."""
    s = s or ""
    return [s[i:i + 2] for i in range(0, len(s), 2)]


def tokens_to_action(history: list) -> str:
    """Session token list -> a Slumbot action string. '_' (street separator) -> '/'; bet/check/call/fold tokens
    concatenate within a street. ['b225','c','_','k','k'] -> 'b225c/kk'."""
    return "".join("/" if t == "_" else t for t in history)


def hero_seat_and_button(session_hand: dict, hero_hole: list) -> tuple[int, int]:
    """(hero_seat, button_seat) in session seat-space. HU: button = the SB seat; hero = the seat holding hero_hole.
    Returns (-1,-1) if the hole can't be matched (a join failure -> recon_ok=False)."""
    players = session_hand.get("players", [])
    want = set(hero_hole)
    hero = next((i for i, p in enumerate(players) if set(_parse_cards(p.get("hole", ""))) == want), -1)
    button = next((i for i, p in enumerate(players) if str(p.get("position", "")).upper() == "SB"), -1)
    return hero, button


def hero_decision_points(history: list, button: int, hero: int) -> list:
    """[(action_string_prefix, street_name), ...] for each point where `hero` is to act, in play order. The prefix
    is the betting up to (not including) hero's own action — exactly what build_state needs to rebuild the spot.
    HU play order: preflop the button (SB) acts first; each later street the non-button (BB) acts first."""
    pts, seg, street_idx, actor = [], [[]], 0, button
    for tok in history:
        if tok == "_":
            street_idx += 1
            seg.append([])
            actor = 1 - button
            continue
        if actor == hero:
            pts.append(("/".join("".join(s) for s in seg), STREETS[street_idx]))
        seg[street_idx].append(tok)
        actor = 1 - actor
    return pts


def reconstruct_spot(session_hand: dict, hero: int, button: int, prefix: str, street: str):
    """Rebuild the canonical Spot at a hero decision point. None if build_state rejects the line."""
    players = session_hand["players"]
    hole = _parse_cards(players[hero]["hole"])
    board = _parse_cards(session_hand.get("board", ""))[:_BOARD_LEN[street]]
    st = build_state(hole, board, prefix, client_pos=hero, button=button)
    if st is None:
        return None
    return spot_from_slumbot(st)


# ----------------------------------------------------------------------------------------------------------------------
# The decision-time INPUT AUDIT (was the math I judged from even correct?)
# ----------------------------------------------------------------------------------------------------------------------
_PCT_RE = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%")
_NEED_RE = re.compile(r"(?:need|require[ds]?|pot[- ]?odds?)\D{0,12}(\d{1,3}(?:\.\d+)?)\s*%", re.IGNORECASE)


def _cited_required_pct(reasoning: str):
    """Best-effort: the required/pot-odds % I cited in my reasoning, or None. Prefer a 'need/require NN%' phrasing,
    else fall back to the first %<=60 (a plausible required-equity, not an equity claim)."""
    m = _NEED_RE.search(reasoning or "")
    if m:
        return float(m.group(1))
    for v in (float(x) for x in _PCT_RE.findall(reasoning or "")):
        if v <= 60.0:
            return v
    return None


def audit_inputs(feat: dict, spot, reasoning: str) -> dict:
    """Compare the LOGGED decision-time inputs to the TRUE (reconstructed) ones. The live `gtow_to_state` path
    logged `to_call = total_pot - common_pot`, inflating facing-bet spots -> inflated required_equity -> a possible
    over-fold CAUSE that is a WIRING bug, not a judgment leak."""
    from pokerbot.brain import api
    true_to_call_bb = spot.b(spot.to_call)
    true_req = round(api.required_equity(spot.to_call, spot.pot), 3) if spot.to_call > 0 else 0.0
    logged_to_call_bb = feat.get("to_call_bb")
    logged_req = feat.get("required_equity")
    inflated = bool(spot.to_call > 0 and logged_req is not None
                    and isinstance(logged_req, (int, float)) and (logged_req - true_req) > _REQ_TOL)
    cited = _cited_required_pct(reasoning)
    return {
        "logged_to_call_bb": logged_to_call_bb, "true_to_call_bb": true_to_call_bb,
        "logged_required": logged_req, "true_required": true_req,
        "input_inflated": inflated,
        "cited_required_pct": cited,
        # did my cited % follow the WRONG logged value rather than the truth? (I was misled by the bad input)
        "cited_followed_inflated": bool(cited is not None and logged_req is not None
                                        and isinstance(logged_req, (int, float))
                                        and abs(cited / 100.0 - logged_req) < 0.04
                                        and abs(cited / 100.0 - true_req) > 0.06),
    }


# ----------------------------------------------------------------------------------------------------------------------
# Grading — preflop (blueprint, free) and postflop (solve_node + math fallback)
# ----------------------------------------------------------------------------------------------------------------------
_PASSIVE = {"call", "check", "limp"}
_FOLD = {"fold"}


def _action_family(action: str) -> str:
    if action in _FOLD:
        return "fold"
    if action in _PASSIVE:
        return "passive"
    return "aggressive"          # bet/raise/allin


def grade_preflop(feat: dict, action: str) -> dict:
    """Grade vs the stored near-Nash blueprint {fold, call, 3bet(/open/...)}. gto_prob_of_mine = P(my family)."""
    bp = feat.get("preflop_blueprint") or {}
    if not isinstance(bp, dict) or not bp:
        return {"oracle_source": "none", "oracle_mix": {}, "oracle_action": None,
                "in_support": None, "gto_prob_of_mine": None, "prob_gap": None, "size_mismatch": None}
    fam = _action_family(action)
    fold_p = sum(v for k, v in bp.items() if k in _FOLD)
    passive_p = sum(v for k, v in bp.items() if k in _PASSIVE)
    agg_p = sum(v for k, v in bp.items() if k not in _PASSIVE and k not in _FOLD)
    mine = {"fold": fold_p, "passive": passive_p, "aggressive": agg_p}[fam]
    oracle_action = max(bp.items(), key=lambda kv: kv[1])[0]
    return {"oracle_source": "blueprint", "oracle_mix": {k: round(v, 4) for k, v in bp.items()},
            "oracle_action": oracle_action, "in_support": mine > _SUPPORT_EPS,
            "gto_prob_of_mine": round(mine, 4), "prob_gap": round(max(bp.values()) - mine, 4),
            "size_mismatch": None}


def grade_postflop(spot, feat: dict, action: str, amount_bb, solve: bool) -> dict:
    """Grade vs api.solve_node (line-aware) -> {action:prob}; equity-math fallback when None/not-solved."""
    from pokerbot.brain import api
    mix = api.solve_node(spot) if solve else None
    if mix:
        sizes = mix.get("_sizes_bb", {}) or {}
        probs = {k: v for k, v in mix.items() if k != "_sizes_bb"}
        verb = "allin" if action == "allin" else action
        mine = float(probs.get(verb, 0.0))
        oracle_action = max(probs.items(), key=lambda kv: kv[1])[0] if probs else None
        size_mismatch = None
        if verb in ("bet", "raise", "allin") and verb in sizes and amount_bb:
            ref = sizes[verb] or 0
            size_mismatch = bool(ref and abs(amount_bb - ref) / ref > _SIZE_TOL)
        return {"oracle_source": "solver", "oracle_mix": {k: round(v, 4) for k, v in probs.items()},
                "oracle_sizes_bb": {k: round(v, 2) for k, v in sizes.items()},
                "oracle_action": oracle_action, "in_support": mine > _SUPPORT_EPS,
                "gto_prob_of_mine": round(mine, 4),
                "prob_gap": round((max(probs.values()) if probs else 0) - mine, 4),
                "size_mismatch": size_mismatch}
    # ---- equity-math fallback: a call/fold sanity floor (no full mix) ----
    src = "math_fallback" if solve else "unsolved_recon"
    return {"oracle_source": src, "oracle_mix": {}, "oracle_sizes_bb": {}, "oracle_action": None,
            "in_support": None, "gto_prob_of_mine": None, "prob_gap": None, "size_mismatch": None}


def _equity_used(feat: dict) -> float | None:
    """A single equity estimate for the call/fold EV floor — vs-top30 is the middle continuing-range read."""
    for k in ("equity_vs_top30", "equity_vs_top60", "equity_vs_top10"):
        v = feat.get(k)
        if isinstance(v, (int, float)):
            return float(v)
    return None


def _bucket(g: dict, math_ok) -> str:
    """The deterministic headline grade. pure_gto / mixed_ok / minor_dev / blunder."""
    p = g.get("gto_prob_of_mine")
    if p is None:
        return "unscored"
    if p >= _PURE_GTO:
        return "pure_gto"
    if g.get("in_support"):
        return "mixed_ok"
    return "blunder" if math_ok is False else "minor_dev"


def grade_one(dec: dict, session_hand: dict, recon_pref, solve: bool) -> dict:
    """Reconstruct + audit + grade ONE decision. recon_pref = (prefix, street) or None (no recon -> degraded)."""
    from pokerbot.brain import api
    feat, action = dec["features"], dec.get("action")
    amount_bb = dec.get("amount_bb")
    hid = dec.get("hand_id")
    street = feat.get("street")
    out = {"seq": dec["seq"], "hand_id": hid, "street": street, "hero_hole": feat.get("hero_hole"),
           "board": feat.get("board"), "position": feat.get("position"),
           "my_action": action, "my_amount_bb": amount_bb,
           "hand_aivat": session_hand.get("aivat"),
           "hand_winnings_bb": round((session_hand.get("winnings") or 0) / 100.0, 2),
           "reasoning": dec.get("reasoning", "")}

    spot = None
    if recon_pref is not None:
        hero, button = hero_seat_and_button(session_hand, feat.get("hero_hole", []))
        if hero >= 0 and button >= 0:
            spot = reconstruct_spot(session_hand, hero, button, recon_pref[0], recon_pref[1])
    # checksum: street + pot match the stored features (to_call is NOT trusted — the gtow_to_state inflation)
    recon_ok = bool(spot is not None and spot.street == street
                    and abs(spot.b(spot.pot) - (feat.get("pot_bb") or -9)) <= 0.06)
    out["recon_ok"] = recon_ok
    out["pot_bb"] = spot.b(spot.pot) if spot else feat.get("pot_bb")
    out["to_call_bb"] = spot.b(spot.to_call) if spot else feat.get("to_call_bb")
    out["pot_type"] = _pot_type(spot) if spot else None

    # input audit (needs a spot for the TRUE values)
    if spot is not None:
        out.update(audit_inputs(feat, spot, dec.get("reasoning", "")))

    # oracle grade
    if street == "preflop":
        g = grade_preflop(feat, action)
    elif spot is not None:
        g = grade_postflop(spot, feat, action, amount_bb, solve=solve)
    else:
        g = {"oracle_source": "unsolved_recon", "oracle_mix": {}, "oracle_action": None,
             "in_support": None, "gto_prob_of_mine": None, "prob_gap": None, "size_mismatch": None}
    out.update(g)

    # call/fold real-bb EV margin (the one honest bb figure) + cited-math correctness
    eq = _equity_used(feat)
    true_req = out.get("true_required")
    if true_req is None and spot is not None and spot.to_call > 0:
        true_req = round(api.required_equity(spot.to_call, spot.pot), 3)
    margin_bb = None
    if eq is not None and true_req is not None and (out.get("to_call_bb") or 0) > 0 and action in ("call", "fold"):
        pot_bb, call_bb = out.get("pot_bb") or 0, out.get("to_call_bb") or 0
        edge = (eq - true_req) * (pot_bb + call_bb)            # bb won/lost by calling vs folding
        margin_bb = round(edge if action == "call" else -edge, 2)  # fold forgoes a +edge call -> -edge
    out["equity_margin_bb"] = margin_bb
    out["equity_used"] = eq

    # math_ok: TRUE if I wasn't misled by an inflated input and any folded +EV call isn't a big blunder
    math_ok = None
    if spot is not None and (out.get("to_call_bb") or 0) > 0:
        misled = out.get("cited_followed_inflated", False)
        bad_fold = bool(action == "fold" and margin_bb is not None and margin_bb <= -_MARGIN_BB_BLUNDER)
        bad_call = bool(action == "call" and margin_bb is not None and margin_bb <= -_MARGIN_BB_BLUNDER)
        math_ok = not (misled or bad_fold or bad_call)
    out["math_ok"] = math_ok
    out["grade_bucket"] = _bucket(out, math_ok)
    return out


def _pot_type(spot) -> str:
    """SRP / 3bet / 4bet / limped from the preflop raise count (the solver-range confidence tag)."""
    raises = sum(1 for a in spot.line if a.get("street") == "preflop" and a.get("action") in ("raise", "bet"))
    return {0: "limped", 1: "srp", 2: "3bet", 3: "4bet"}.get(raises, "5bet+")


# ----------------------------------------------------------------------------------------------------------------------
# Driver
# ----------------------------------------------------------------------------------------------------------------------
def _aligned_points(decisions: list, session_hand: dict) -> dict:
    """{seq: (prefix, street) | None} — per-street ordinal alignment of thought decisions to reconstructed points."""
    if not session_hand:
        return {d["seq"]: None for d in decisions}
    hero_hole = decisions[0]["features"].get("hero_hole", [])
    hero, button = hero_seat_and_button(session_hand, hero_hole)
    if hero < 0 or button < 0:
        return {d["seq"]: None for d in decisions}
    recon = hero_decision_points(session_hand.get("history", []), button, hero)
    by_street = defaultdict(list)
    for pref, stt in recon:
        by_street[stt].append((pref, stt))
    idx = defaultdict(int)
    out = {}
    for d in sorted(decisions, key=lambda d: d["seq"]):
        stt = d["features"].get("street")
        i = idx[stt]
        pts = by_street.get(stt, [])
        out[d["seq"]] = pts[i] if i < len(pts) else None
        idx[stt] += 1
    return out


def run(stage: str, threads: int, solve_threads: int, limit: int | None) -> None:
    os.environ["POKERB_LINE_RANGES"] = "1"          # offline grading: line-aware ranges are strictly more correct
    os.environ.setdefault("SOLVE_THREADS", str(solve_threads))
    tlog = _load_jsonl(_THOUGHT_LOG)
    sessions = {h["hand_id"]: h for h in _load_jsonl(_SESSION)}
    if limit:
        tlog = tlog[:limit]
    by_hand = defaultdict(list)
    for d in tlog:
        by_hand[d["hand_id"]].append(d)

    # align every decision to its reconstructed point
    aligned = {}
    for hid, decs in by_hand.items():
        aligned.update(_aligned_points(decs, sessions.get(hid)))

    solve = (stage == "grade")
    out_path = _GRADED if solve else _ENRICHED
    done = set()
    if solve and os.path.exists(out_path):                       # resume
        done = {r["seq"] for r in _load_jsonl(out_path)}
        print(f"[resume] {len(done)} decisions already graded -> skipping")
    todo = [d for d in tlog if d["seq"] not in done]

    lock = threading.Lock()
    results = []

    def work(dec):
        sh = sessions.get(dec["hand_id"], {})
        try:
            rec = grade_one(dec, sh, aligned.get(dec["seq"]), solve=solve)
        except Exception as e:  # noqa: BLE001 — one bad spot must not kill the batch
            rec = {"seq": dec["seq"], "hand_id": dec["hand_id"], "street": dec["features"].get("street"),
                   "recon_ok": False, "grade_bucket": "error", "error": f"{type(e).__name__}: {e}"}
        with lock:
            results.append(rec)
            with open(out_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n = len(results)
            if solve and n % 10 == 0:
                print(f"  graded {n}/{len(todo)} (last seq {rec['seq']}, {rec.get('oracle_source')})", flush=True)
        return rec

    if not solve and os.path.exists(out_path):
        os.remove(out_path)                                     # recon stage: always a fresh pass

    if solve and threads > 1:
        with ThreadPoolExecutor(max_workers=threads) as ex:
            list(ex.map(work, todo))
    else:
        for d in todo:
            work(d)

    all_rows = (_load_jsonl(out_path) if solve else results)
    _report(all_rows, stage)


def regrade_unscored(threads: int, solve_threads: int) -> None:
    """Re-solve ONLY the postflop rows that fell to math_fallback/unsolved (flop solves timed out under the parallel
    load at solve_threads=2 — the deep 3-street tree). A FRESH process = a fresh solve cache (the prior None is not
    reused), with more threads/solve + fewer parallel workers so the deep flop tree clears the timeout. Updates the
    existing graded_decisions.jsonl in place (scored rows preserved)."""
    os.environ["POKERB_LINE_RANGES"] = "1"
    os.environ["SOLVE_THREADS"] = str(solve_threads)
    rows = {r["seq"]: r for r in _load_jsonl(_GRADED)}
    tlog = {d["seq"]: d for d in _load_jsonl(_THOUGHT_LOG)}
    sessions = {h["hand_id"]: h for h in _load_jsonl(_SESSION)}
    by_hand = defaultdict(list)
    for d in tlog.values():
        by_hand[d["hand_id"]].append(d)
    aligned = {}
    for hid, decs in by_hand.items():
        aligned.update(_aligned_points(decs, sessions.get(hid)))

    targets = [s for s, r in rows.items()
               if r.get("street") in ("flop", "turn", "river") and r.get("oracle_source") in ("math_fallback", "unsolved_recon")]
    print(f"re-grading {len(targets)} unscored postflop rows (solve_threads={solve_threads}, workers={threads})")
    lock = threading.Lock()
    fixed = [0]

    def work(seq):
        dec = tlog[seq]
        try:
            rec = grade_one(dec, sessions.get(dec["hand_id"], {}), aligned.get(seq), solve=True)
        except Exception as e:  # noqa: BLE001 — one bad spot must NOT crash the whole batch (keep the old row)
            print(f"  seq{seq} regrade error ({type(e).__name__}: {e}) -> keeping old row", flush=True)
            return
        with lock:
            rows[seq] = rec
            if rec.get("oracle_source") == "solver":
                fixed[0] += 1
            if (fixed[0] and fixed[0] % 10 == 0):
                print(f"  recovered {fixed[0]} so far", flush=True)

    with ThreadPoolExecutor(max_workers=threads) as ex:
        list(ex.map(work, targets))
    with open(_GRADED, "w", encoding="utf-8") as fh:
        for s in sorted(rows):
            fh.write(json.dumps(rows[s], ensure_ascii=False) + "\n")
    print(f"recovered {fixed[0]}/{len(targets)} via solver; rewrote {_GRADED}")
    _report(list(rows.values()), "grade")


def _report(rows: list, stage: str) -> None:
    n = len(rows)
    recon_ok = sum(1 for r in rows if r.get("recon_ok"))
    print(f"\n=== {stage.upper()} report — {n} decisions ===")
    print(f"recon_ok: {recon_ok}/{n} ({recon_ok / max(1, n):.1%})")
    by_street = Counter(r.get("street") for r in rows)
    print(f"by street: {dict(by_street)}")
    # input audit
    facing = [r for r in rows if (r.get("to_call_bb") or 0) > 0 and r.get("true_required") is not None]
    inflated = [r for r in facing if r.get("input_inflated")]
    misled = [r for r in facing if r.get("cited_followed_inflated")]
    if facing:
        print(f"\nINPUT AUDIT (facing-bet spots, n={len(facing)}):")
        print(f"  decision-time required_equity INFLATED (logged > true + {_REQ_TOL}): "
              f"{len(inflated)}/{len(facing)} ({len(inflated)/len(facing):.1%})")
        if inflated:
            ex = inflated[0]
            print(f"    e.g. seq {ex['seq']}: logged_req {ex.get('logged_required')} vs true {ex.get('true_required')} "
                  f"(to_call logged {ex.get('logged_to_call_bb')}bb vs true {ex.get('true_to_call_bb')}bb)")
        print(f"  my cited % FOLLOWED the inflated value (misled by the wiring): {len(misled)}/{len(facing)}")
    # grade buckets
    buckets = Counter(r.get("grade_bucket") for r in rows)
    print(f"\nGRADE BUCKETS: {dict(buckets)}")
    if stage == "grade":
        src = Counter(r.get("oracle_source") for r in rows)
        print(f"oracle source: {dict(src)}")
        solved = sum(1 for r in rows if r.get("oracle_source") == "solver")
        post = sum(1 for r in rows if r.get("street") in ("flop", "turn", "river"))
        print(f"solver coverage (postflop): {solved}/{post} ({solved/max(1,post):.1%})")
    print(f"\nwrote {_GRADED if stage == 'grade' else _ENRICHED}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["recon", "grade", "regrade"], default="recon")
    ap.add_argument("--threads", type=int, default=8, help="parallel grader workers (grade stage)")
    ap.add_argument("--solve-threads", type=int, default=2, help="TexasSolver CPU threads per solve")
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    if a.stage == "regrade":
        regrade_unscored(a.threads, a.solve_threads)
    else:
        run(a.stage, a.threads, a.solve_threads, a.limit)


if __name__ == "__main__":
    main()
