"""GTOW-ORACLE CROSS-CHECK — does OUR oracle agree with the strongest benchmark's ACTUAL play?

GTO Wizard is near-GTO, and the session logs reveal its hole cards + every action on all logged hands. So for each
GTOW decision we can ask: does OUR oracle (preflop blueprint / postflop TexasSolver `solve_node`) assign real
probability to what GTOW ACTUALLY did? Where the oracle says "never" (prob ~0) but GTOW did it = OUR ORACLE IS INEXACT.

This is the systematic ENGINE-leak source, and it tests the session's hypothesis: Claude (-28.55) and the fixed GLM
(-28.36) hit the SAME wall -> is that wall our engine/solver oracle? High agreement -> the oracle is fine (the wall is
wiring/judgment); low agreement -> the engine IS the wall (prioritise the postflop overhaul).

  python -m research.gtow_oracle_check                          # preflop (blueprint) on ALL hands, free
  python -m research.gtow_oracle_check --postflop-sample 200    # + a sampled postflop (solver) cross-check (slow)
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import threading
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

from research import study_grade as SG
from pokerbot.brain import api
from pokerbot.engine.evaluator import evaluate

_SUPPORT_EPS = 0.02     # the oracle "plays" an action if its prob exceeds this (else it effectively says "never")
_PASSIVE = {"k", "c"}


def _load_all() -> list:
    """All logged GTOW hands, deduped by hand_id (sessions can overlap)."""
    seen, out = set(), []
    for f in sorted(glob.glob(str(SG._REPO and os.path.join(SG._REPO, "data", "sessions", "gtow_hands_*.jsonl")))):
        for ln in open(f, encoding="utf-8"):
            if not ln.strip():
                continue
            r = json.loads(ln)
            hid = r.get("hand_id")
            if hid in seen:
                continue
            seen.add(hid)
            out.append(r)
    return out


def _button(hand: dict) -> int:
    """players-index of the SB (= the HU button, first to act preflop)."""
    return next((i for i, p in enumerate(hand.get("players", [])) if str(p.get("position", "")).upper() == "SB"), 1)


def _folder_seat(history: list, button: int):
    """The players-index that folded (HU: at most one), or None if the hand reached showdown. Mirrors the play order:
    preflop the button acts first, each later street the non-button first; actor alternates each action."""
    seg_first, actor = button, button
    for tok in history:
        if tok == "_":
            actor = 1 - button
            continue
        if tok == "f":
            return actor
        actor = 1 - actor
    return None


def _gtow_seat(hand: dict, button: int):
    """Which seat is GTO Wizard. Uses `gtow_folded` + the folder for fold hands (the bulk), else a showdown eval +
    the winnings sign. None if it can't be resolved cleanly (chop / odd) -> skip that hand."""
    folder = _folder_seat(hand.get("history", []), button)
    if folder is not None:
        return folder if hand.get("gtow_folded") else 1 - folder
    # showdown: winner = the better hand on the final board; hero = winner if hero won (winnings>0) else loser.
    board = SG._parse_cards(hand.get("board", ""))
    ps = hand.get("players", [])
    if len(board) < 5 or len(ps) < 2:
        return None
    try:
        r0 = evaluate(board, SG._parse_cards(ps[0]["hole"]))   # lower treys rank = stronger
        r1 = evaluate(board, SG._parse_cards(ps[1]["hole"]))
    except Exception:  # noqa: BLE001
        return None
    if r0 == r1:
        return None                                            # chop -> ambiguous, skip
    winner = 0 if r0 < r1 else 1
    w = hand.get("winnings") or 0
    if w == 0:
        return None
    hero = winner if w > 0 else 1 - winner
    return 1 - hero


def _gtow_points(history: list, button: int, gtow: int) -> list:
    """[(action_string_prefix, street, token_GTOW_played)] for each GTOW turn, in play order."""
    pts, seg, si, actor = [], [[]], 0, button
    for tok in history:
        if tok == "_":
            si += 1
            seg.append([])
            actor = 1 - button
            continue
        if actor == gtow:
            pts.append(("/".join("".join(s) for s in seg), SG.STREETS[si], tok))
        seg[si].append(tok)
        actor = 1 - actor
    return pts


def _family(token: str) -> str:
    if token == "f":
        return "fold"
    if token in _PASSIVE:
        return "passive"
    return "aggressive"                                        # 'b...' = bet/raise/allin


def _oracle_family_probs(mix: dict) -> dict:
    """Collapse an oracle mix (blueprint {fold,call,3bet,...} or solver {fold,check,call,bet,raise,allin}) to the three
    families, so a bet-vs-raise or open-vs-3bet label mismatch never trips the support test."""
    fold = sum(v for k, v in mix.items() if k == "fold")
    passive = sum(v for k, v in mix.items() if k in ("call", "check", "limp"))
    agg = sum(v for k, v in mix.items() if k not in ("fold", "call", "check", "limp", "_sizes_bb"))
    return {"fold": fold, "passive": passive, "aggressive": agg}


def _grade(spot, token: str, postflop: bool):
    """Return (in_support, oracle_prob_of_gtow_family, is_modal, source) or None if the oracle has no opinion."""
    if postflop:
        mix = api.solve_node(spot)
        src = "solver"
    else:
        mix = api.preflop_mix(spot)
        src = "blueprint"
    if not mix:
        return None
    fam = _oracle_family_probs(mix)
    g = _family(token)
    p = fam.get(g, 0.0)
    modal = max(fam, key=fam.get)
    return (p > _SUPPORT_EPS, round(p, 3), g == modal, src)


def _collect(hands: list):
    """Walk every hand -> GTOW's preflop and postflop decision points (with the spot rebuilt for GTOW's hand)."""
    pre, post, skipped = [], [], 0
    for h in hands:
        btn = _button(h)
        g = _gtow_seat(h, btn)
        if g is None:
            skipped += 1
            continue
        for prefix, street, tok in _gtow_points(h.get("history", []), btn, g):
            rec = (h, g, btn, prefix, street, tok)
            (pre if street == "preflop" else post).append(rec)
    return pre, post, skipped


def _spot_for(rec):
    h, g, btn, prefix, street, tok = rec
    return SG.reconstruct_spot(h, g, btn, prefix, street)


def _report(name: str, rows: list):
    """rows = [(in_support, prob, is_modal, family_token, street, pot_type)]."""
    n = len(rows)
    if not n:
        print(f"  {name}: no graded decisions"); return
    ins = sum(1 for r in rows if r[0])
    modal = sum(1 for r in rows if r[2])
    meanp = sum(r[1] for r in rows) / n
    print(f"\n=== {name} (n={n}) ===")
    print(f"  GTOW's action IN our oracle's support (p>{_SUPPORT_EPS}): {ins}/{n} = {ins/n:.1%}")
    print(f"  GTOW's action == our oracle's MODAL family            : {modal}/{n} = {modal/n:.1%}")
    print(f"  mean oracle prob assigned to GTOW's actual action     : {meanp:.3f}")
    print(f"  -> OUT of support (oracle says ~never, GTOW did it)   : {n-ins}/{n} = {(n-ins)/n:.1%}  (high = our oracle is INEXACT)")
    by_st = defaultdict(list)
    for r in rows:
        by_st[r[4]].append(r)
    for st in ("preflop", "flop", "turn", "river"):
        rs = by_st.get(st, [])
        if rs:
            print(f"    {st:7s}: in-support {sum(1 for x in rs if x[0])/len(rs):.0%}  modal {sum(1 for x in rs if x[2])/len(rs):.0%}  n={len(rs)}")
    fam = Counter(r[3] for r in rows)
    oos_fam = Counter(r[3] for r in rows if not r[0])
    print(f"    GTOW action mix: {dict(fam)} | OUT-of-support by family: {dict(oos_fam)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--postflop-sample", type=int, default=0, help="N postflop GTOW decisions to solve (0 = preflop only)")
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--solve-threads", type=int, default=6)
    a = ap.parse_args()
    os.environ["POKERB_LINE_RANGES"] = "1"
    os.environ.setdefault("SOLVE_THREADS", str(a.solve_threads))

    hands = _load_all()
    pre, post, skipped = _collect(hands)
    print(f"loaded {len(hands)} hands | GTOW decisions: {len(pre)} preflop, {len(post)} postflop | "
          f"{skipped} hands skipped (unresolved seat)")

    # PREFLOP — free, ALL decisions (blueprint vs GTOW's actual preflop play)
    pre_rows = []
    for rec in pre:
        spot = _spot_for(rec)
        if spot is None:
            continue
        g = _grade(spot, rec[5], postflop=False)
        if g:
            pre_rows.append((g[0], g[1], g[2], _family(rec[5]), "preflop", None))
    _report("PREFLOP: blueprint vs GTOW", pre_rows)

    # POSTFLOP — sampled (solver is slow), parallel
    if a.postflop_sample > 0 and post:
        step = max(1, len(post) // a.postflop_sample)
        sample = post[::step][:a.postflop_sample]              # stable stride sample (street-spread, deterministic)
        print(f"\nsolving {len(sample)} postflop GTOW spots (stride {step} over {len(post)}); ~slow ...", flush=True)
        rows, lock, done = [], threading.Lock(), [0]

        def work(rec):
            spot = _spot_for(rec)
            if spot is None:
                return
            try:
                g = _grade(spot, rec[5], postflop=True)
            except Exception:  # noqa: BLE001
                g = None
            with lock:
                done[0] += 1
                if done[0] % 25 == 0:
                    print(f"   solved {done[0]}/{len(sample)}", flush=True)
                if g:
                    rows.append((g[0], g[1], g[2], _family(rec[5]), rec[4], None))
        with ThreadPoolExecutor(max_workers=a.threads) as ex:
            list(ex.map(work, sample))
        _report("POSTFLOP (sampled): solver vs GTOW", rows)
        cov = len(rows)
        print(f"\n  solver coverage on the sample: {cov}/{len(sample)} ({cov/max(1,len(sample)):.0%}); the rest = off-tree/None")

    print("\nINTERPRETATION: high in-support + modal% = our oracle agrees with the benchmark (the wall is wiring/judgment,"
          " not the engine). Low (esp. postflop) = our oracle is INEXACT vs GTO -> the ENGINE is the wall (do the postflop overhaul).")


if __name__ == "__main__":
    main()
