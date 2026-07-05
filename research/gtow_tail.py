"""Tail-robust GTOW eval + the fat-tail SPEW-vs-COOLER classifier (the (b) lever + the grounding for (a) the anti-spew gate).

★ THE FINDING (2026-06-21 #3): the model's BODY is stable at ~−17 bb/100 (5%-trimmed) across EVERY baseline session —
the raw mean swings −28↔−90 ENTIRELY in a FAT LEFT TAIL of rare catastrophic postflop stack-offs. So raw-mean AIVAT at
n≤1500 measures TAIL LUCK, not skill. This module:
  (1) TRIM-SENSITIVITY — raw vs drop-worst-k vs %-trim, so the tail's dominance is visible (--compare = the cross-session
      table that shows the body is stable + the raw swing is all tail);
  (2) the SPEW-vs-COOLER split of the catastrophic hands — but HONESTLY: the gate can only ever act on what's knowable at
      decision time = hero's equity vs a plausible committing RANGE (api.range_top), NOT villain's actual card (hindsight).
      So `eq_vs_range` is the gate-able signal; `eq_vs_actual` is shown only as context. SPEW (eq_vs_range low = hero behind
      a committing range = a disciplined fold) is gate-able; COOLER (eq_vs_range high, lost anyway) is irreducible variance.

GTOW reveals BOTH hole cards on every logged hand → hero's exact hand + equity are computable.

  python -m research.gtow_tail [log.jsonl]    # default: the most-recent n>=1000 (baseline pin) log
  python -m research.gtow_tail --compare      # the cross-session raw-vs-trimmed table (the headline finding)
"""
from __future__ import annotations

import glob
import json
import os
import sys

from pokerbot.brain import api
from research import study_grade as SG
from research import gtow_oracle_check as OC

_BB = 100.0
_CATASTROPHE_BB = 100.0      # a hand losing >100bb (>10000 chips) = a catastrophic tail hand (a near-full stack-off)
_COMMIT_RANGE = 0.40         # villain's "committing/stack-off" range ~= the top 40% of hands (a prior; the gate uses this)
_SPEW_EQ = 0.40              # hero <40% vs a committing range = behind = a disciplined fold = GATE-ABLE spew
_COOLER_EQ = 0.55           # hero >55% vs a committing range, lost anyway = COOLER / bad-beat = NOT gate-able


def _logs(min_n: int = 1) -> list:
    out = []
    for f in glob.glob(os.path.join(SG._REPO, "data", "sessions", "gtow_hands_*.jsonl")):
        rows = [json.loads(l) for l in open(f, encoding="utf-8") if l.strip()]
        av = [r["aivat"] for r in rows if r.get("aivat") is not None]
        if len(av) >= min_n:
            out.append((f, rows, av))
    return sorted(out, key=lambda t: -os.path.getmtime(t[0]))


def _trim(a: list, frac: float) -> float:
    """Mean in bb/100 after trimming `frac` from EACH tail."""
    a = sorted(a)
    n = len(a)
    k = int(n * frac)
    body = a[k:n - k] if n - 2 * k > 0 else a
    return sum(body) / len(body) / _BB * 100


def _drop_worst(a: list, k: int) -> float:
    """Mean in bb/100 after dropping only the k worst hands (asymmetric — isolates the LEFT tail)."""
    a = sorted(a)
    return sum(a[k:]) / max(1, len(a) - k) / _BB * 100


def tail_metrics(av: list) -> None:
    n = len(av)
    print(f"  n={n}  RAW={sum(av)/n/_BB*100:+.1f}   "
          f"drop-worst-1={_drop_worst(av,1):+.1f}  -5={_drop_worst(av,5):+.1f}  -10={_drop_worst(av,10):+.1f}")
    print(f"  trim:  2.5%={_trim(av,.025):+.1f}   5%={_trim(av,.05):+.1f}   10%={_trim(av,.10):+.1f}   "
          f"<- the BODY (stable ~ the true skill level)")
    cat = sum(1 for x in av if x / _BB <= -_CATASTROPHE_BB)
    worst = sorted(av)[:10]
    print(f"  catastrophes (>{_CATASTROPHE_BB:.0f}bb loss): {cat}/{n} ({cat/n*100:.1f}%) | "
          f"worst-10 = {sum(worst)/n/_BB*100:+.1f} bb/100 of the raw | worst hand {worst[0]/_BB:.0f}bb")


def _classify_one(hand: dict):
    """Returns (eq_vs_range, eq_vs_actual_flop, eq_vs_actual_turn, hero_hole, gtow_hole) or None.
    eq_vs_range = hero's showdown equity vs a top-COMMIT_RANGE range on the FULL board = the LIVE-knowable gate signal."""
    btn = OC._button(hand)
    g = OC._gtow_seat(hand, btn)
    if g is None:
        return None
    hero = 1 - g
    ps = hand.get("players", [])
    hh, gh = SG._parse_cards(ps[hero].get("hole", "")), SG._parse_cards(ps[g].get("hole", ""))
    board = SG._parse_cards(hand.get("board", ""))
    if len(hh) < 2 or len(gh) < 2 or len(board) < 3:
        return None
    vr = api.range_top(_COMMIT_RANGE)                              # the live, no-hindsight signal: hero vs a committing range
    eq_range = float(api.equity(hh, vr, board, iters=400))
    ef = float(api.equity(hh, [tuple(gh)], board[:3], iters=400))  # context: hero vs villain's ACTUAL hand (hindsight)
    et = float(api.equity(hh, [tuple(gh)], board[:4], iters=400)) if len(board) >= 4 else ef
    return eq_range, ef, et, hh, gh


def classify_tail(hands: list, k: int = 15) -> None:
    losers = sorted([h for h in hands if (h.get("aivat") or 0) < 0], key=lambda h: h["aivat"])[:k]
    spew = cooler = marginal = unresolved = 0
    print(f"\n=== FAT-TAIL CLASSIFICATION (worst {len(losers)} loss hands; eqRange = the GATE-ABLE signal) ===")
    print(f"  {'aivat':>7} {'win_bb':>6} {'eqRange':>7} {'eqActF':>6} {'eqActT':>6}  verdict   hero / villain   board")
    for h in losers:
        r = _classify_one(h)
        if r is None:
            unresolved += 1
            continue
        eqr, ef, et, hh, gh = r
        if eqr < _SPEW_EQ:
            verdict, spew = "SPEW", spew + 1                       # behind a committing range -> a disciplined fold
        elif eqr >= _COOLER_EQ:
            verdict, cooler = "COOLER", cooler + 1                 # ahead of the range, lost = variance
        else:
            verdict, marginal = "marginal", marginal + 1
        print(f"  {h['aivat']/_BB:>7.0f} {(h.get('winnings') or 0)/_BB:>6.0f} {eqr:>7.2f} {ef:>6.2f} {et:>6.2f}  "
              f"{verdict:8s}  {''.join(hh)} / {''.join(gh)}  {h.get('board','')}")
    tot = spew + cooler + marginal
    if tot:
        print(f"\n  GATE-ABLE spew (hero behind a committing range): {spew}/{tot} ({spew/tot*100:.0f}%) | "
              f"COOLER (irreducible): {cooler}/{tot} | marginal: {marginal}/{tot} | unresolved: {unresolved}")
        print(f"  => an anti-spew EV-gate can address AT MOST ~{spew/tot*100:.0f}% of the tail (the cooler/marginal rest "
              f"is variance the gate must NOT touch).")


# ----------------------------------------------------------------------------------------------------------------------
# (a) THE ANTI-SPEW GATE — a $0 COUNTERFACTUAL over the real log (no pod): fold the clear -EV big calls, measure the delta.
# A pod A/B can't see a tail effect at n<=1500 (raw is noise); replaying the gate over LOGGED hands measures it for $0.
# ----------------------------------------------------------------------------------------------------------------------
_STREETS = ["preflop", "flop", "turn", "river"]


def _hero_decisions(history: list, button: int, hero: int) -> list:
    """[(prefix, street, action_tok)] — each point hero acts, the betting before it, and the token hero played."""
    pts, seg, si, actor = [], [[]], 0, button
    for tok in history:
        if tok == "_":
            si += 1; seg.append([]); actor = 1 - button; continue
        if actor == hero:
            pts.append(("/".join("".join(s) for s in seg), _STREETS[min(si, 3)], tok))
        seg[si].append(tok); actor = 1 - actor
    return pts


def _committed_bb(spot) -> float:
    s = next((x for x in spot.seats if x.get("seat") == spot.hero_seat), None)
    return (s["committed_total"] if s else 0.0) / _BB


def counterfactual(hands: list, eq_mode: str = "range", big_bb: float = 40.0,
                   margin: float = 0.0, vill_frac: float = 0.5) -> float:
    """Replay: at hero's FIRST big CALL whose equity (vs a committing range, or vs the actual hand) is below the
    required equity, the gate FOLDS instead. delta = (fold loss = -committed) - (actual winnings). Sum/n = bb/100."""
    total = saved = cost = 0.0
    fired = n = 0
    for h in hands:
        w = h.get("winnings")
        if w is None:
            continue
        n += 1
        btn = OC._button(h)
        g = OC._gtow_seat(h, btn)
        if g is None:
            continue
        hero = 1 - g
        for prefix, street, act in _hero_decisions(h.get("history") or [], btn, hero):
            if act != "c":                                    # the gate only ever folds CALLS (bets/raises = bluffs, untouched)
                continue
            try:
                spot = SG.reconstruct_spot(h, hero, btn, prefix, street)
            except Exception:
                spot = None
            if spot is None or spot.to_call < big_bb * _BB:    # big commitments only -> the tail, not the body
                continue
            req = api.required_equity(spot.to_call, spot.pot)
            if eq_mode == "actual":
                gh = SG._parse_cards(h["players"][g].get("hole", ""))
                if len(gh) < 2:
                    continue
                eq = float(api.equity(spot.hero_hole, [tuple(gh)], spot.board, iters=400))
            else:
                eq = float(api.equity(spot.hero_hole, api.range_top(vill_frac), spot.board, iters=400))
            if eq + margin < req:                              # a clear -EV call -> fold; hand ends here
                delta = -_committed_bb(spot) - w / _BB
                total += delta; fired += 1
                saved += max(0.0, delta); cost += min(0.0, delta)
                break
    eff = total / n * 100 if n else 0.0
    print(f"  [{eq_mode:6s} vill{vill_frac:.2f} >={big_bb:.0f}bb m{margin:+.2f}] fired {fired:3d}/{n} | "
          f"NET {eff:+6.1f} bb/100  (saved {saved/max(1,n)*100:+.1f} / cost {cost/max(1,n)*100:+.1f})")
    return eff


def commitment_cap(hands: list, eq_floor: float = 0.45, pot_bb: float = 60.0,
                   vill_frac: float = 0.5, eq_mode: str = "range") -> float:
    """A FORCED bet-discipline cap (not a hint): at hero's FIRST postflop COMMITMENT (a bet, or a call facing a bet) in a
    BIG pot where hero's equity vs a committing range < eq_floor, hero GIVES UP (result = -committed_before). This is
    PESSIMISTIC on won bluffs (it forfeits them entirely) — so a net-POSITIVE here is a ROBUST signal the cap helps;
    a net-negative means the aggression is +EV in aggregate (the forfeited bluff-wins outweigh the saved spew-losses)."""
    total = saved = cost = 0.0
    fired = n = won_forfeit = 0
    for h in hands:
        w = h.get("winnings")
        if w is None:
            continue
        n += 1
        btn = OC._button(h)
        g = OC._gtow_seat(h, btn)
        if g is None:
            continue
        hero = 1 - g
        for prefix, street, act in _hero_decisions(h.get("history") or [], btn, hero):
            if street == "preflop":
                continue
            if not (act.startswith("b") or act == "c"):           # commitments only (bet/raise, or a call)
                continue
            try:
                spot = SG.reconstruct_spot(h, hero, btn, prefix, street)
            except Exception:
                spot = None
            if spot is None:
                continue
            if act == "c" and spot.to_call <= 0:                  # a check is not a commitment
                continue
            if spot.pot < pot_bb * _BB:                           # big pots only = the tail, not the body
                continue
            if eq_mode == "actual":                               # ORACLE: hero's equity vs villain's REAL hand (ceiling)
                gh = SG._parse_cards(h["players"][g].get("hole", ""))
                if len(gh) < 2:
                    continue
                eq = float(api.equity(spot.hero_hole, [tuple(gh)], spot.board, iters=400))
            else:
                eq = float(api.equity(spot.hero_hole, api.range_top(vill_frac), spot.board, iters=400))
            if eq < eq_floor:                                     # low equity into a big pot -> give up (cap the spew)
                delta = -_committed_bb(spot) - w / _BB
                total += delta; fired += 1
                if w > 0:
                    won_forfeit += 1
                saved += max(0.0, delta); cost += min(0.0, delta)
                break
    eff = total / n * 100 if n else 0.0
    print(f"  [cap eq<{eq_floor:.2f} pot>={pot_bb:.0f}bb] fired {fired:3d}/{n} (won-bluffs forfeited {won_forfeit}) | "
          f"NET(pessimistic) {eff:+6.1f} bb/100  (saved {saved/max(1,n)*100:+.1f} / cost {cost/max(1,n)*100:+.1f})")
    return eff


def cap_counterfactual(hands: list) -> None:
    print("\n=== FORCED BET-DISCIPLINE CAP — $0 counterfactual (give up low-eq big-pot commitments; PESSIMISTIC on bluffs) ===")
    print("  ORACLE (eq vs villain's ACTUAL hand) — the perfect-info ceiling; net tells us if big-pot betting-as-underdog is net -EV:")
    for floor in (0.45, 0.50):
        for pot in (40, 60):
            commitment_cap(hands, eq_floor=floor, pot_bb=pot, eq_mode="actual")
    print("  LIVE (eq vs range_top — a WEAK board-blind proxy; under-fires, shown for contrast):")
    for pot in (40, 60):
        commitment_cap(hands, eq_floor=0.45, pot_bb=pot, eq_mode="range")
    print("  => ORACLE net-POSITIVE = recoverable -EV aggression exists (RL can target it); ~0/negative = the tail is variance, accept it.")


def gate_counterfactual(hands: list) -> None:
    print("\n=== (a) ANTI-SPEW GATE — $0 COUNTERFACTUAL (fold the clear -EV big calls over the REAL log) ===")
    print("  ORACLE (eq vs villain's ACTUAL hand = the perfect-info UPPER BOUND a gate could ever reach):")
    counterfactual(hands, eq_mode="actual", big_bb=40)
    counterfactual(hands, eq_mode="actual", big_bb=60)
    print("  LIVE (eq vs a committing RANGE = what a real serve-time gate can actually compute):")
    for vf in (0.40, 0.55):
        counterfactual(hands, eq_mode="range", big_bb=40, vill_frac=vf)
    print("  => build the gate ONLY if the LIVE net is clearly positive (and cost is small); else the tail is variance.")


def _bet_amt(tok: str) -> float:
    try:
        return float(tok[1:])
    except Exception:
        return 0.0


def value_audit(hands: list) -> None:
    """Is the model VALUE-BETTING + SIZING correctly? (the user's lever: 'compute value + size right, then ride variance').
    Over bet-or-check (to_call==0) postflop spots: hero's bet-rate vs the advisor's GTO bet-rate, by made-hand strength,
    + avg bet size (% pot). Under-betting strong hands = a VALUE leak in the BODY (lost EV) — fixable, unlike the tail."""
    from collections import defaultdict
    order = ["weak <.4", "med .4-.6", "strong .6-.8", "nuts >.8"]
    B = {k: {"n": 0, "bet": 0, "adv": 0.0, "advn": 0, "size": 0.0, "sizen": 0} for k in order}
    for h in hands:
        btn = OC._button(h)
        g = OC._gtow_seat(h, btn)
        if g is None:
            continue
        hero = 1 - g
        for prefix, street, act in _hero_decisions(h.get("history") or [], btn, hero):
            if street == "preflop":
                continue
            try:
                spot = SG.reconstruct_spot(h, hero, btn, prefix, street)
            except Exception:
                spot = None
            if spot is None or spot.to_call > 0:                 # bet-or-check spots only (the value-betting decision)
                continue
            _, strg = api.hand_rank(spot.hero_hole, spot.board)
            b = order[3] if strg > 0.8 else order[2] if strg > 0.6 else order[1] if strg > 0.4 else order[0]
            d = B[b]; d["n"] += 1
            if act.startswith("b"):
                d["bet"] += 1
                amt = _bet_amt(act)
                if amt > 0 and spot.pot > 0:
                    d["size"] += amt / spot.pot; d["sizen"] += 1
            role = "IP" if spot.hero_pos in ("BTN", "SB") else "OOP"
            try:
                p = api.solver_freq(spot.hero_hole, spot.board, role, street)
            except Exception:
                p = None
            if p is not None:
                d["adv"] += p; d["advn"] += 1
    print("\n=== VALUE-BETTING + SIZING AUDIT (to_call==0 postflop spots = the fixable BODY lever) ===")
    print(f"  {'made-hand':>14} {'n':>5} {'hero bet%':>10} {'advisor bet%':>13} {'gap':>6} {'avg size %pot':>14}")
    for b in order:
        d = B[b]
        if d["n"] == 0:
            continue
        hr = d["bet"] / d["n"] * 100
        ad = d["adv"] / d["advn"] * 100 if d["advn"] else float("nan")
        sz = d["size"] / d["sizen"] * 100 if d["sizen"] else float("nan")
        print(f"  {b:>14} {d['n']:>5} {hr:>9.0f}% {ad:>12.0f}% {hr - ad:>+5.0f} {sz:>13.0f}%")
    print("  => hero bet% << advisor bet% on strong/nuts = UNDER-BETTING (lost value); avg size vs ~50-75% GTO = mis-sizing.")


def compare() -> None:
    """The headline: raw vs trimmed across every session — the body is stable, the raw swing is all tail."""
    print("=== CROSS-SESSION: raw (lies) vs 5%-trimmed BODY (the stable skill level) ===")
    print(f"  {'log':>14} {'n':>5} {'RAW':>8} {'trim5':>8} {'cat%':>6}")
    for f, rows, av in _logs(min_n=300):
        n = len(av)
        cat = sum(1 for x in av if x / _BB <= -_CATASTROPHE_BB)
        ts = f.split("_")[-1].replace(".jsonl", "")
        print(f"  {ts:>14} {n:>5} {sum(av)/n/_BB*100:>+8.1f} {_trim(av,.05):>+8.1f} {cat/n*100:>5.1f}%")
    print("\n  => the trimmed body clusters tightly (~−17) while raw swings −28↔−90 = the difference is TAIL LUCK, not skill.")


def main() -> None:
    if "--compare" in sys.argv:
        compare()
        return
    arg = next((a for a in sys.argv[1:] if not a.startswith("-")), None)
    if arg:
        rows = [json.loads(l) for l in open(arg, encoding="utf-8") if l.strip()]
    else:
        logs = _logs(min_n=1000)
        if not logs:
            print("no n>=1000 log; pass one explicitly"); return
        arg, rows, _ = logs[0]
    av = [r["aivat"] for r in rows if r.get("aivat") is not None]
    print(f"=== TAIL-ROBUST METRICS — {os.path.basename(arg)} ===")
    tail_metrics(av)
    classify_tail(rows)
    if "--gate" in sys.argv:
        gate_counterfactual(rows)
    if "--cap" in sys.argv:
        cap_counterfactual(rows)
    if "--value" in sys.argv:
        value_audit(rows)


if __name__ == "__main__":
    main()
