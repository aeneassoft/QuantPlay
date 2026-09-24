"""Phase B step 9: generate CFV-net training data. The net (queried at the turn->river LEAF of the flop resolve)
must map (4-card turn board + both ranges + pot) -> per-combo TURN-BOUNDARY CFVs = the value of the river subgame
BEFORE the river card is dealt = E over the river card of [river-subgame CFV]. We get each river-subgame CFV by
SOLVING that river (TexasSolver) and extracting via the B1-validated `cfv_eval`. For a turn board there are 48 unseen
cards; we solve all 48 rivers and average per combo. Each combo is valid in exactly 46 of the 48 solves (it is removed
only when the river card == one of its two cards), so n=46 is CONSTANT across combos -> the per-combo averaging
PRESERVES the river-level zero-sum (proof: sum_c [zero-sum river] = 0).

This module is range-agnostic (`turn_boundary_cfv` takes range strings) — the only thing to scale on RunPod is the
range SAMPLER (here: the SRP priors, for the $0 local pipeline test). Run: python -m extraction.cfv_data
"""
from __future__ import annotations

import random
from collections import defaultdict

from pokerbot import config
from pokerbot.benchmark.gto_benchmark import _IP, _OOP
from pokerbot.engine.evaluator import evaluate
from pokerbot.strategy import gto_oracle as O
from pokerbot.strategy.distill import CARDS, SMALL_BETS
from research import cfv_eval


def turn_boundary_cfv(board4, oop_str, ip_str, pot=20.0, eff=50.0, acc=0.5, iters=30, threads=8, timeout=30, k_rivers=48):
    """-> (turn_cfv0{combo:cfv}, turn_cfv1{combo:cfv}, cnt0, cnt1, fails). Solve k_rivers of the 48 run-outs + average
    per combo. k_rivers=48 (default) = exact (zero-sum preserved by the constant n=46 averaging); k_rivers<48 = a
    faster MC estimate for the PILOT (a sample becomes ~k/48 the cost, so it actually COMPLETES inside a short gen
    window; per-combo n varies slightly -> zero-sum only APPROXIMATE — see docs/NOTES.md, refine on the full run)."""
    unseen = [c for c in CARDS if c not in board4]
    if k_rivers < len(unseen):
        unseen = random.Random("".join(board4)).sample(unseen, k_rivers)   # deterministic per board
    acc0, acc1 = defaultdict(float), defaultdict(float)
    cnt0, cnt1 = defaultdict(int), defaultdict(int)
    fails = 0
    for c in unseen:
        board5 = list(board4) + [c]
        try:
            root = O.solve(board5, oop_str, ip_str, pot=pot, eff_stack=eff, bets=SMALL_BETS,
                           accuracy=acc, max_iter=iters, dump_rounds=1, threads=threads, timeout=timeout,
                           tag="cfv" + "".join(board5))
            cfv0, cfv1, _oop, _ip, _st = cfv_eval.compute_river_cfv(root, board5, start_pot=pot)
        except Exception:  # noqa: BLE001
            fails += 1
            continue
        for combo, v in cfv0.items():
            acc0[combo] += v
            cnt0[combo] += 1
        for combo, v in cfv1.items():
            acc1[combo] += v
            cnt1[combo] += 1
    turn0 = {k: acc0[k] / cnt0[k] for k in acc0 if cnt0[k]}
    turn1 = {k: acc1[k] / cnt1[k] for k in acc1 if cnt1[k]}
    return turn0, turn1, cnt0, cnt1, fails


def _all_classes():
    """The 169 HU hand classes (AA, AKs, AKo, ..., 22) for TexasSolver range strings."""
    ranks = "AKQJT98765432"
    cls = []
    for i, a in enumerate(ranks):
        for j, b in enumerate(ranks):
            if i == j:
                cls.append(a + b)               # pair
            elif i < j:
                cls.append(a + b + "s")          # suited (higher rank first)
            else:
                cls.append(b + a + "o")          # offsuit (higher rank first)
    return list(dict.fromkeys(cls))


def sample_range(rng, tightness=None):
    """A DIVERSE class-level weighted TexasSolver range string (DeepStack-style broad coverage so the net
    generalizes over the ranges the live range-tracker emits). `tightness` = P(include a class); random if None.
    NOTE (refinable knob): this is uniform-random coverage; biasing toward realistic prior-derived/line-narrowed
    ranges (what range_tracker actually feeds) is a sample-efficiency improvement to A/B later."""
    classes = _all_classes()
    # narrower than full-random: real turn-boundary ranges (after preflop+flop+turn narrowing) are NARROW (<~75
    # classes), and broad ranges blow up the solve tree (123-class ranges -> ~12s/solve, some hit the cap). This is
    # both more REALISTIC (matches what range_tracker emits) and far FASTER.
    t = tightness if tightness is not None else rng.uniform(0.1, 0.45)
    picked = [(c, round(rng.uniform(0.2, 1.0), 3)) for c in classes if rng.random() < t]
    if not picked:
        picked = [("AA", 1.0), ("KK", 1.0)]
    return ",".join(f"{c}:{w}" for c, w in picked)


def _gen_one(args):
    """Module-level worker (picklable for ProcessPoolExecutor): one sample -> row dict, or None on failure."""
    board4, oop_str, ip_str, pot, eff, threads, k_rivers = args
    try:
        t0, t1, _c0, _c1, fails = turn_boundary_cfv(board4, oop_str, ip_str, pot=pot, eff=eff, threads=threads,
                                                    k_rivers=k_rivers)
        return {"board": board4, "pot": pot, "eff": eff, "oop": oop_str, "ip": ip_str,
                "cfv0": t0, "cfv1": t1, "fails": fails}
    except Exception:  # noqa: BLE001
        return None


def gen(n, out, seed=0, workers=8, threads=2, k_rivers=48):
    """Generate n CFV-net training samples in PARALLEL via a PROCESS pool (NOT threads): the per-matchup CFV
    extraction (cfv_eval) is pure-Python + GIL-bound, so a ThreadPool only reached ~22% CPU (load ~7/32) — PROCESSES
    bypass the GIL -> full vCPU load. Set workers*threads ~= the box's vCPU count. `seed` SHARDS across pods. `k_rivers`
    = how many of the 48 river run-outs to solve per sample (48=exact, <48=faster pilot estimate). Writes each sample
    as it completes, so a killed run keeps its banked samples."""
    import json
    from concurrent.futures import ProcessPoolExecutor, as_completed
    rng = random.Random(seed)
    specs = [(rng.sample(CARDS, 4), sample_range(rng), sample_range(rng),
              float(rng.choice([20, 30, 40, 60])), float(rng.choice([40, 50, 80])), threads, k_rivers) for _ in range(n)]
    done = 0
    with open(out, "w", encoding="utf-8") as f, ProcessPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(_gen_one, s) for s in specs]
        for fut in as_completed(futs):
            r = fut.result()
            if r:
                f.write(json.dumps(r) + "\n")
                f.flush()
            done += 1
            print(f"  sample {done}/{n} | {('OOP ' + str(len(r['cfv0'])) + ' fails ' + str(r['fails'])) if r else 'FAILED'}", flush=True)
    print(f"wrote {done} samples (PROCESS pool workers={workers} threads={threads} seed={seed}) -> {out}", flush=True)


def main():
    import sys
    if "--sampler" in sys.argv:                          # $0 instant check: the sampler emits valid range strings
        rng = random.Random(3)
        for i in range(3):
            s = sample_range(rng)
            print(f"  sample range {i+1}: {len(s.split(','))} classes -> {s[:90]}...")
        print("  (valid class-level weighted TexasSolver strings; ready to feed gen())")
        return
    if "--gen" in sys.argv:
        def _arg(flag, d):
            return type(d)(sys.argv[sys.argv.index(flag) + 1]) if flag in sys.argv else d
        i = sys.argv.index("--gen")
        n = int(sys.argv[i + 1]) if len(sys.argv) > i + 1 and not sys.argv[i + 1].startswith("--") else 50
        out = _arg("--out", str(config.DATA_DIR / "cfv_dataset_pilot.jsonl"))
        gen(n, out, seed=_arg("--seed", 0), workers=_arg("--workers", 4), threads=_arg("--threads", 2),
            k_rivers=_arg("--k", 48))
        return
    rng = random.Random(11)
    board4 = rng.sample(CARDS, 4)
    pot, eff = 20.0, 50.0
    print(f"=== Step-9 pipeline local test: turn board {board4} | SRP ranges | pot {pot} eff {eff} ===")
    print("  solving all 48 river run-outs (this is the per-turn-board cost the RunPod job scales)...", flush=True)
    t0, t1, cnt0, cnt1, fails = turn_boundary_cfv(board4, _OOP, _IP, pot=pot, eff=eff)

    counts = sorted(set(cnt0.values()))
    s0, s1 = sum(t0.values()), sum(t1.values())
    per0 = t0                                            # reach=1 -> per-combo cfv is already comparable
    top = sorted(per0, key=lambda c: -per0[c])[:5]
    bot = sorted(per0, key=lambda c: per0[c])[:5]

    print(f"  failed solves: {fails}/48 | OOP combos {len(t0)} | IP combos {len(t1)}")
    print(f"  per-combo solve-count values (expect all 46 if 0 fails): {counts}")
    zs = abs(s0 + s1)
    print(f"  ZERO-SUM (preserved by n=46-constant averaging): sum t0 {s0:+.3f} + sum t1 {s1:+.3f} = {zs:.4f}")
    print("  NUT-SANITY (top-5 OOP turn-CFV should be strong on this board; bottom-5 weak):")
    for c in top:
        print(f"    +{per0[c]:+.2f}  {c}  (treys rank on turn {evaluate(board4, [c[:2], c[2:4]])})")
    for c in bot:
        print(f"    {per0[c]:+.2f}  {c}  (treys rank on turn {evaluate(board4, [c[:2], c[2:4]])})")
    count_ok = (fails > 0) or (counts == [46])           # all 46 iff no solve failed
    nut_ok = (sum(evaluate(board4, [c[:2], c[2:4]]) for c in top) / 5) < (sum(evaluate(board4, [c[:2], c[2:4]]) for c in bot) / 5)
    ok = zs < max(1e-3, 0.05 * abs(s0) + 0.05) and nut_ok and count_ok and len(t0) > 50
    print(f"\n  STEP-9 PIPELINE: {'PASS - turn-boundary CFV labels look correct; ready to scale (diverse ranges) on RunPod' if ok else 'FAIL - inspect before scaling'}")


if __name__ == "__main__":
    main()
