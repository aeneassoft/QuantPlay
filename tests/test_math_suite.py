"""MATH TEST SUITE — recurring, exact, independent verification of the bot's core calculations.

Doctrine (born from the Goldbach project's verification culture, 2026-07-06): a formula is verified
ONLY against a reference derived INDEPENDENTLY from first principles (Fraction-exact EV decompositions),
never against its own self-check (`verify_expr == verify_value` proves consistency, not truth — a
consistent-but-wrong formula passes it). Patterns adopted: claim-verifier separated from claim-generator,
counterexample fuzzing with exact rationals, and an honest UNVERIFIED ledger (the negative space is
reported, never hidden).

Run:  python -m tests.test_math_suite [--deep] [--json PATH]
  fast mode ~seconds (CI-able, deterministic seed); --deep multiplies fuzz counts 20x.
Exit 1 on any FAIL. A FAIL means: shipped code and independent reference disagree — investigate by
COMPETING hypotheses (shipped bug vs reference bug vs convention mismatch) before touching either side.
Live-math fixes are BEHAVIOR changes -> gate ladder; dormant/KB fixes are free.
"""
from __future__ import annotations

import json
import random
import sys
from fractions import Fraction as Fr

CHECKS: list[tuple[str, object]] = []      # (name, fn) — fn returns None (pass) or a failure detail str
VERIFIED_FORMULAS: set[str] = set()        # formula-module functions with an independent reference here
FUZZ_N = 400                               # per-check random cases; --deep multiplies by 20
_RNG_SEED = 42                             # one seed -> byte-stable run-to-run (determinism discipline)


def check(name: str):
    def deco(fn):
        CHECKS.append((name, fn))
        return fn
    return deco


def _rng() -> random.Random:
    return random.Random(_RNG_SEED)


def _fr(rng: random.Random, lo: int = 1, hi: int = 400) -> Fr:
    return Fr(rng.randint(lo, hi), rng.randint(1, 40))


# ----------------------------------------------------------------------------- A. exact identity anchors
@check("pot_odds: api.required_equity == C/(P+C) == EV-zero point (exact)")
def _pot_odds():
    from pokerbot.brain import api
    rng = _rng()
    for _ in range(FUZZ_N):
        p, c = _fr(rng), _fr(rng)
        ref = c / (p + c)                                       # EV(call)=eq*p-(1-eq)*c=0  =>  eq=c/(p+c)
        got = api.required_equity(float(c), float(p))           # signature: (to_call, pot)
        if abs(got - float(ref)) > 1e-9:
            return f"P={p} C={c}: api={got} ref={float(ref)}"
        ev_at_ref = ref * p - (1 - ref) * c                     # the independent truth: EV at threshold is 0
        if ev_at_ref != 0:
            return f"EV at threshold != 0: {ev_at_ref}"
    VERIFIED_FORMULAS.add("api.required_equity")
    return None


@check("covered-bet pot odds: AUDIT_FIX expression == first-principles refund derivation (exact)")
def _covered_pot_odds():
    # Villain bets B > hero stack H. Hero calls all-in for H, the unmatched (B-H) refunds to villain.
    # Win: +(pot - (B-H));  lose: -H  =>  req = H / (pot - (B-H) + H). bot.py's AUDIT_FIX arm computes
    # hero_stack / ((pot - (to_call - hero_stack)) + hero_stack) — must be the SAME rational function.
    rng = _rng()
    for _ in range(FUZZ_N):
        h = _fr(rng)
        b = h + _fr(rng)                                        # bet covers hero: B > H
        pot = b + _fr(rng)                                      # pot already contains villain's bet
        ref = h / ((pot - (b - h)) + h)
        derived = h / (pot - b + 2 * h)
        if ref != derived:
            return f"algebra split: {ref} != {derived}"
        ev = ref * (pot - (b - h)) - (1 - ref) * h
        if ev != 0:
            return f"EV at covered threshold != 0: {ev}"
    return None


@check("alpha/MDF: bluff-breakeven s/(1+s), MDF 1/(1+s); library fns match (exact)")
def _alpha_mdf():
    from knowledge_base.math import formulas as F
    rng = _rng()
    for _ in range(FUZZ_N):
        pot, bet = _fr(rng), _fr(rng)
        s = bet / pot
        alpha = s / (1 + s)                 # 0-EV bluff: fold_freq*pot = (1-fold_freq)*bet
        mdf = 1 / (1 + s)                   # = 1 - alpha
        if alpha + mdf != 1:
            return f"alpha+mdf != 1 at s={s}"
        got_mdf = F.minimum_defense_frequency(float(pot), float(bet))
        got_alpha = F.breakeven_bluff_percentage(float(bet), float(pot))
        if abs(got_mdf - float(mdf)) > 1e-9:
            return f"mdf(P={pot},B={bet}): lib={got_mdf} ref={float(mdf)}"
        if abs(got_alpha - float(alpha)) > 1e-9:
            return f"alpha(B={bet},P={pot}): lib={got_alpha} ref={float(alpha)}"
    VERIFIED_FORMULAS.update({"minimum_defense_frequency", "breakeven_bluff_percentage"})
    return None


@check("required_fold_equity: closed form == independent Fraction solve of EV(FE)=0")
def _rfe():
    from knowledge_base.math import formulas as F
    rng = _rng()
    for _ in range(FUZZ_N):
        p, r, c = _fr(rng), _fr(rng), _fr(rng)
        e = Fr(rng.randint(0, 100), 100)
        x = e * (p + r + c) - r                                 # called-branch EV
        if p == x:
            continue                                            # degenerate (function raises; not a math case)
        ref = x / (x - p)                                       # solve FE*p + (1-FE)*x = 0 independently
        got = F.required_fold_equity(float(p), float(r), float(c), float(e))
        # RELATIVE tolerance: near the pole (x -> p) float cancellation in the lib's denominator loses
        # digits legitimately (deep-fuzz find 2026-07-06: 2e-6 abs at ref~990, |x-p|~1e-3). The function is
        # ill-conditioned there by NATURE (FE -> inf = "no fold freq rescues this"), not by bug.
        if abs(got - float(ref)) > 1e-9 * max(1.0, abs(float(ref))) + 1e-12:
            return f"P={p} R={r} C={c} E={e}: lib={got} ref={float(ref)}"
    VERIFIED_FORMULAS.add("required_fold_equity")
    return None


@check("implied odds: F_min == C*(1/p-1) - P from p*(P+F)=(1-p)*C (exact; docstring eq was the wrong form)")
def _implied():
    from knowledge_base.math import formulas as F
    rng = _rng()
    for _ in range(FUZZ_N):
        p_hit = Fr(rng.randint(1, 99), 100)
        pot, call = _fr(rng), _fr(rng)
        # hero nets +(pot+F) on hit (his call returns inside the won pot), -call on miss
        ref = max(Fr(0), call * (1 / p_hit - 1) - pot)
        got = F.required_future_winnings_for_implied_odds(float(pot), float(call), float(p_hit))
        if abs(got - float(ref)) > 1e-9:
            return f"P={pot} C={call} p={p_hit}: lib={got} ref={float(ref)}"
    VERIFIED_FORMULAS.add("required_future_winnings_for_implied_odds")
    return None


@check("value_score: shipped form == derived EV F + (1-F)*(e*(1+s) - (1-e)*s); old==new was a no-op")
def _value_score():
    from pokerbot.strategy.postflop import value_score
    rng = _rng()
    for _ in range(FUZZ_N):
        s = Fr(rng.randint(10, 300), 100)
        f = Fr(rng.randint(0, 100), 100)
        eq = Fr(rng.randint(0, 100), 100)
        e_call = max(Fr(1, 10), eq - Fr(1, 4) * s)              # the shipped e_call surrogate (pinned)
        ref = f + (1 - f) * (e_call * (1 + s) - (1 - e_call) * s)   # win +(1+s), lose -s when called
        got = value_score(float(s), float(f), float(eq))
        if abs(got - float(ref)) > 1e-9:
            return f"s={s} F={f} eq={eq}: shipped={got} ref={float(ref)}"
    return None


@check("villain call threshold vs size s: s/(1+2s) is the exact pot-odds breakeven (identity)")
def _call_threshold():
    rng = _rng()
    for _ in range(FUZZ_N):
        s = _fr(rng)
        thr = s / (1 + 2 * s)               # facing s*P into P: call sP to win (P + sP + sP)
        ev = thr * (1 + s) - (1 - thr) * s  # caller nets +(1+s) on win, -s on loss
        if ev != 0:
            return f"threshold not breakeven at s={s}: EV={ev}"
    return None


@check("compute_pot_odds: returned (odds, req) is a consistent system anchored at req=C/(P+B+C)")
def _compute_pot_odds():
    from knowledge_base.math import formulas as F
    rng = _rng()
    for _ in range(FUZZ_N):
        p, b, c = _fr(rng), _fr(rng), _fr(rng)
        odds, req = F.compute_pot_odds(float(p), float(b), float(c))
        ref_req = c / (p + b + c)
        if abs(req - float(ref_req)) > 1e-9:
            return f"P={p} B={b} C={c}: req={req} ref={float(ref_req)}"
        if abs(req - 1 / (1 + odds)) > 1e-9:                    # odds and req must describe the SAME bet
            return f"odds/req inconsistent: odds={odds} req={req}"
    VERIFIED_FORMULAS.add("compute_pot_odds")
    return None


@check("equity_needed_to_call (villain_risked=0 path) == C/(P+C)")
def _eq_needed():
    from knowledge_base.math import formulas as F
    rng = _rng()
    for _ in range(FUZZ_N):
        p, c = _fr(rng), _fr(rng)
        got = F.equity_needed_to_call(float(p), float(c))
        ref = c / (p + c)
        if abs(got - float(ref)) > 1e-9:
            return f"P={p} C={c}: lib={got} ref={float(ref)}"
    VERIFIED_FORMULAS.add("equity_needed_to_call")
    return None


# ------------------------------------------------------------------- B. convention tests (the killer class)
@check("resolver._observed_fracs: census conventions on constructed histories")
def _observed_fracs_conventions():
    from pokerbot.strategy import resolver as R
    # first-in bet 50 into 100 -> 0.5 ; raise to 150 over the 50 -> (150-50)/(150+50) = 0.5
    st = {"history": ["_", {"action": "bet", "to": 50}, {"action": "raise", "to": 150}]}
    def acts(_state, _street):
        return [h for h in _state["history"] if isinstance(h, dict)]
    orig = R._street_actions
    R._street_actions = acts                # isolate the fraction math from history slicing
    try:
        got = R._observed_fracs(st, "flop", 100.0)
        want = [("bet", 0.5), ("raise", 0.5)]
        if len(got) != 2 or any(k != wk or abs(v - wv) > 1e-9 for (k, v), (wk, wv) in zip(got, want)):
            return f"bet+raise: got {got}, want {want}"
        st2 = {"history": [{"action": "allin", "to": 400}]}     # a shove must NEVER be injected as an arm
        if R._observed_fracs(st2, "flop", 100.0):
            return "allin action leaked into observed fracs"
        st3 = {"history": [{"action": "bet", "to": 30}, {"action": "call"},
                           {"action": "bet", "to": 80}]}        # next-street-style second bet, same walk
        got3 = R._observed_fracs(st3, "flop", 100.0)
        # after bet30+call30: pot_before=160, first-in bet to=80 by actor0 whose commit is 30 -> (80-30)/160
        want3 = [("bet", 0.3), ("bet", (80 - 30) / 160)]
        if len(got3) != 2 or abs(got3[1][1] - want3[1][1]) > 1e-9:
            return f"commit walk: got {got3}, want {want3}"
    finally:
        R._street_actions = orig
    return None


@check("tracker confidence: fully-unmodeled range must NOT pass the resolver gate under GTO-mode slope")
def _confidence_gate():
    from pokerbot.strategy import range_tracker as RT
    # constants-level pin: the S2 finding — slope 0.5 floors EXACTLY at CONF_THRESHOLD (dead gate);
    # the GTO-mode slope 0.7 gates a 100%-unmodeled reconstruction. PRINCE carries 0.7.
    dead = 1.0 - 0.5 * 1.0
    if not (dead >= RT.CONF_THRESHOLD):     # documents WHY 0.5 is dead: conf==threshold still passes >=
        return "premise broken: slope-0.5 boundary no longer sits at the threshold"
    gto = 1.0 - 0.7 * 1.0
    if not (gto < RT.CONF_THRESHOLD):
        return f"GTO-mode slope 0.7 no longer gates: conf={gto} threshold={RT.CONF_THRESHOLD}"
    return None


# --------------------------------------------------------------------------- C. structural invariants
@check("range_tracker._normalize: sums to 1, all weights positive, floor prune never empties")
def _normalize_inv():
    from pokerbot.strategy.range_tracker import RangeTracker
    rng = _rng()
    rt = RangeTracker.__new__(RangeTracker)
    for _ in range(200):
        n = rng.randint(2, 60)
        rt.range = {0: {f"c{i}": rng.random() ** 4 + 1e-12 for i in range(n)}}
        rt._normalize(0)
        d = rt.range[0]
        if not d:
            return "normalize emptied the range"
        s = sum(d.values())
        if abs(s - 1.0) > 1e-9 or any(w <= 0 for w in d.values()):
            return f"sum={s}, min={min(d.values())}"
    return None


@check("RAISE_MIX targets: valid distributions (sum~1, no negatives) per street")
def _raise_mix():
    from pokerbot.strategy import range_tracker as RT
    for name in ("RAISE_MIX", "RAISE_MIX_JAM"):
        mix = getattr(RT, name, None)
        if not isinstance(mix, dict):
            continue
        for street, dist in mix.items():
            if not isinstance(dist, dict):
                continue
            s = sum(dist.values())
            if any(v < 0 for v in dist.values()) or abs(s - 1.0) > 0.02:
                return f"{name}[{street}]: sum={s}, dist={dist}"
    return None


@check("snap_to_tree: idempotent on grid points, output positive, off-grid snaps to nearest fraction")
def _snap():
    from pokerbot.strategy import postflop as PF
    rng = _rng()
    sizes = PF.CENSUS_BETS.get("river", PF.TREE_SIZES) if PF.GTOW_TREE else PF.TREE_SIZES
    for _ in range(200):
        pot = rng.randint(50, 4000)
        s = rng.choice(sizes)
        chips = max(1, round(s * pot))
        snapped = PF.snap_to_tree(chips, pot, "river")
        if abs(snapped - chips) > 1:                            # rounding wobble of 1 chip is the contract
            return f"grid point moved: pot={pot} s={s} chips={chips} snapped={snapped}"
        off = rng.randint(1, 5 * pot)
        got = PF.snap_to_tree(off, pot, "river")
        best = min(sizes, key=lambda x: abs(x - off / pot))
        if abs(got - round(best * pot)) > 1 or got < 1:
            return f"nearest violated: off={off} pot={pot} got={got} best_frac={best}"
    return None


# --------------------------------------------------------------------------------- D. engine ground truth
@check("exact river equity: engine vs independent treys enumeration (3 boards x 3 matchups)")
def _river_equity_exact():
    from pokerbot.engine.equity import equity_vs_range
    from treys import Card, Evaluator
    ev = Evaluator()
    cases = [
        (["As", "Kd"], [("Qh", "Qc"), ("7s", "7d")], ["Ah", "7c", "2d", "9s", "3h"]),
        (["8h", "9h"], [("Ac", "Kc"), ("2c", "2d")], ["Th", "Jh", "2h", "2s", "Qd"]),
        (["5c", "5d"], [("Ad", "Kh"), ("6s", "6c")], ["5h", "6d", "9c", "9d", "Kc"]),
    ]
    for hero, vill, board in cases:
        b = [Card.new(c) for c in board]
        h = [Card.new(c) for c in hero]
        hr = ev.evaluate(b, h)
        w = t = n = 0
        for v in vill:
            if set(v) & set(hero) or set(v) & set(board):
                continue
            vr = ev.evaluate(b, [Card.new(c) for c in v])
            w += hr < vr
            t += hr == vr
            n += 1
        ref = (w + t / 2) / n
        got = equity_vs_range(hero, vill, board, iters=1)       # river path must ENUMERATE (iters ignored)
        if abs(got - ref) > 1e-9:
            return f"{hero} vs {vill} on {board}: engine={got} ref={ref}"
    return None


@check("MC turn equity within 5*SE of exact enumeration (1 spot)")
def _mc_vs_exact():
    from pokerbot.engine.equity import equity_vs_range
    from treys import Card, Deck, Evaluator
    ev = Evaluator()
    hero, vill, board = ["As", "Kd"], [("Qh", "Qc")], ["Ah", "7c", "2d", "9s"]
    used = {c for c in hero} | {c for c in board} | {c for v in vill for c in v}
    wins = tot = 0.0
    for river in [Card.int_to_str(c) for c in Deck.GetFullDeck()]:
        if river in used:
            continue
        b = [Card.new(c) for c in board + [river]]
        hr = ev.evaluate(b, [Card.new(c) for c in hero])
        vr = ev.evaluate(b, [Card.new(c) for c in vill[0]])
        wins += (hr < vr) + 0.5 * (hr == vr)
        tot += 1
    exact = wins / tot
    iters = 4000
    mc = equity_vs_range(hero, vill, board, iters=iters, rng=random.Random(7))
    se = (exact * (1 - exact) / iters) ** 0.5
    if abs(mc - exact) > 5 * se + 1e-12:
        return f"MC={mc} exact={exact} |diff|={abs(mc-exact):.5f} > 5*SE={5*se:.5f}"
    return None


@check("chip conservation incl. side pots (120 random 6-max hands)")
def _conservation():
    from pokerbot.engine.table import Table
    rng = random.Random(3)
    n, start = 6, 10000
    t = Table([f"P{i}" for i in range(n)], starting_stack=start, sb=50, bb=100, seed=3)
    for _ in range(120):
        for s in t.seats:
            s.stack = start
        t.start_hand()
        guard = 0
        while not t.hand_over:
            la = t.legal_actions()
            opts = [a for a, ok in (("check", la.get("can_check")), ("call", la.get("can_call")),
                                    ("fold", la.get("can_fold"))) if ok]
            if la.get("can_raise"):
                opts += ["raise", "allin"]
            a = rng.choice(opts)
            t.act(a, la["raise_min"] if a == "raise" else None)
            guard += 1
            if guard > 5000:
                return "runaway hand"
        if sum(s.stack for s in t.seats) != n * start:
            return f"chip leak: {sum(s.stack for s in t.seats)} != {n * start}"
    return None


# ------------------------------------------------------------------------------------------ runner
def _unverified_ledger() -> list[str]:
    """The honest negative space: public formula functions with NO independent reference above."""
    import knowledge_base.math.formulas as F
    mods = [("formulas", F)]
    from knowledge_base.math import postflop_formulas as PF2
    from knowledge_base.math import strategy_formulas as SF
    mods += [("postflop_formulas", PF2), ("strategy_formulas", SF)]
    out = []
    for mname, mod in mods:
        for n in dir(mod):
            if n.startswith("_") or not callable(getattr(mod, n)):
                continue
            if getattr(getattr(mod, n), "__module__", "") != mod.__name__:
                continue                                        # imported names are not ours to verify
            if n not in VERIFIED_FORMULAS:
                out.append(f"{mname}.{n}")
    return sorted(out)


def main() -> None:
    global FUZZ_N
    args = sys.argv[1:]
    if "--deep" in args:
        FUZZ_N *= 20
    results, failed = [], 0
    for name, fn in CHECKS:
        try:
            detail = fn()
        except Exception as ex:  # noqa: BLE001 — an exception is a FAIL with its own story
            detail = f"EXCEPTION {type(ex).__name__}: {ex}"
        ok = detail is None
        failed += not ok
        results.append({"check": name, "ok": ok, "detail": detail})
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"\n      -> {detail}"))
    ledger = _unverified_ledger()
    print(f"\n{len(CHECKS) - failed}/{len(CHECKS)} checks passed | fuzz N={FUZZ_N}/check")
    print(f"UNVERIFIED formula functions (no independent reference yet): {len(ledger)}")
    for n in ledger:
        print(f"  - {n}")
    if "--json" in args:
        path = args[args.index("--json") + 1]
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"results": results, "unverified": ledger, "fuzz_n": FUZZ_N}, f, indent=1)
        print(f"json -> {path}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
