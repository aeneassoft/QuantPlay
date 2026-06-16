"""WS4: the DEFINITIVE multi-opponent scorecard. Runs the unified MVP (PokerBot exploit-primary) across every
axis we can measure KEY-FREE and emits one JSON + a readable summary, organized by the two targets:

  * LEAST-LOSS (vs near-GTO): how close to GTO the FLOOR plays. GTO Wizard is the true opponent but its key is
    assumed unavailable, so the stand-ins are the TexasSolver GTO-gap (deterministic) + GTOBaseline (paired).
  * EXPLOIT EDGE (vs the field): where the real +bb/100 lives -- the exploitable suite + the calibrated field.

Honest variance: paired/deterministic axes are DECISION-GRADE; unpaired bb/100 carry +/- stderr AND the
rule-of-thumb HUNL noise floor (~90/sqrt(N/100) bb/100). A single unpaired number is NEVER presented as
significant. Every axis is wrapped so one failure writes a partial scorecard with an `errors` entry.

Run:  python -m pokerbot.benchmark.scorecard [--quick | --full] [--hands N]
      --quick : offline, small N (smoke; ~minutes)   --full : large N + Slumbot (network)
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import subprocess
import time

import pokerbot.strategy.bot as botmod
from pokerbot import config

OUT = config.KNOWLEDGE_DIR / "scorecard.json"


def _se(net):
    return statistics.pstdev(net) / (len(net) ** 0.5) if len(net) > 1 else 0.0   # bb/100 units (bb=100)


def _noise(n):
    """Rule-of-thumb HUNL unpaired stderr at N hands (~90/sqrt(N/100) bb/100) -- the reader's reality check."""
    return round(90.0 / ((n / 100.0) ** 0.5), 1) if n > 0 else None


def _git_sha():
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                       cwd=str(config.ROOT), stderr=subprocess.DEVNULL).decode().strip()
    except Exception:  # noqa: BLE001
        return "unknown"


# ----------------------------------------------------------------- LEAST-LOSS (near-GTO)
def axis_gto_gap(limit):
    """Deterministic flop GTO-gap of the MVP floor vs the TexasSolver cache (lower = closer to GTO)."""
    from pokerbot.benchmark import floor_map
    agg = floor_map.run("MVP floor (exploit OFF)", floor_map._floor_decide(), limit)
    out = {}
    for k in ("ALL", "OOP:ALL", "IP:ALL"):
        if k in agg:
            n, div, gb, bb = agg[k]
            if n:
                out[k] = {"gto_gap": round(div / n, 3), "gto_bet": round(gb / n, 3),
                          "our_bet": round(bb / n, 3), "n": n}
    return {"target": "least-loss", "grade": "decision (deterministic, flop-only)", "buckets": out}


def axis_duplicate(decks_n):
    """Paired (card-luck-cancelled) bb/100 vs GTOBaseline, deterministic -> decision-grade least-loss signal.
    NOTE: the duplicate factory builds a FRESH bot per deck (no cross-deck learning), so exploit~=floor here;
    this measures FLOOR quality vs near-GTO (the exploit's learning-driven edge shows in the EXPLOIT axes)."""
    from pokerbot.benchmark.duplicate import duplicate_ab, gen_decks, gto, pokerbot
    decks = gen_decks(decks_n, seed=7)
    null_bb, null_se = duplicate_ab(pokerbot(False), pokerbot(False), decks)
    floor_bb, floor_se = duplicate_ab(pokerbot(False), gto(1), decks)
    mvp_bb, mvp_se = duplicate_ab(pokerbot(True), gto(1), decks)
    return {"target": "least-loss", "grade": "decision (paired, deterministic)", "decks": decks_n,
            "null_floor_vs_floor": {"bb100": round(null_bb, 1), "se": round(null_se, 1)},
            "floor_vs_gtobaseline": {"bb100": round(floor_bb, 1), "se": round(floor_se, 1)},
            "mvp_vs_gtobaseline": {"bb100": round(mvp_bb, 1), "se": round(mvp_se, 1)}}


# ----------------------------------------------------------------- EXPLOIT EDGE (the field)
def axis_internal(hands):
    """MVP (exploit ON, persistent -> learns) vs the exploitable baselines. Unpaired -> wide; should CRUSH."""
    from pokerbot.benchmark import internal
    out = {}
    for opp in ("station", "maniac", "nit"):
        bb100, se, net = internal.run(opp, hands)
        out[opp] = {"bb100": round(bb100, 1), "se": round(se, 1), "n": len(net)}
    return {"target": "exploit-edge", "grade": f"directional (unpaired, noise~{_noise(hands)})", "vs": out}


def axis_field(hands):
    """MVP (exploit ON) vs the diverse 'beat-them-all' suite (named + synthetic-unknown + a strong PokerBot)."""
    import random
    from pokerbot.benchmark import beat_them_all as bta
    R = random.Random
    opps = {"station": bta.opp_station(R(1)), "maniac": bta.opp_maniac(R(2)), "nit": bta.opp_nit(R(3)),
            "foldy": bta.opp_synthetic(R(4), 0.75, 0.15, 0.6), "sticky": bta.opp_synthetic(R(5), 0.12, 0.25, 0.7),
            "trappy": bta.opp_synthetic(R(6), 0.40, 0.55, 1.1), "pokerbot": bta.opp_pokerbot(99)}
    out = {}
    for name, od in opps.items():
        net = bta.play(bta.PokerBotHero(exploit=True, seed=7), od, hands, return_net=True)
        out[name] = {"bb100": round(sum(net) / len(net), 1), "se": round(_se(net), 1), "n": len(net)}
    worst = min(v["bb100"] for v in out.values())
    return {"target": "exploit-edge", "grade": f"directional (unpaired, noise~{_noise(hands)})",
            "worst": round(worst, 1), "beats_all": worst > 0, "vs": out}


def axis_exploit_proof(hands):
    """The MECHANISM proof: exploit-primary vs the floor, vs the size-cliff over-folder (fold_p=0.82), PAIRED decks.
    Synthetic adversary -> diagnostic of the engine's per-size capability, not a population result."""
    from pokerbot.benchmark.exploit_proof import run as ep_run
    from pokerbot.strategy.bot import PokerBot
    mf, sf, nf = ep_run(lambda s: PokerBot(s, seed=7, exploit=False), hands=hands, fold_p=0.82)
    me, se2, ne = ep_run(lambda s: PokerBot(s, seed=7, exploit=True), hands=hands, fold_p=0.82)
    d = [ne[i] - nf[i] for i in range(len(nf))]
    return {"target": "exploit-edge", "grade": "paired, synthetic size-cliff adversary",
            "floor_bb100": round(mf, 1), "exploit_bb100": round(me, 1),
            "paired_delta": round(sum(d) / len(d), 1), "delta_se": round(_se(d), 1), "n": len(nf)}


# ----------------------------------------------------------------- EXTERNAL near-GTO (--full)
def axis_slumbot(hands, exploit_primary):
    """Slumbot (free API): an external near-GTO peer, now RE-ROLED as exploitable (GTOW beats it +19.4 bb/100).
    Network + wide variance -> --full only. Subprocess + parse the printed win-rate line."""
    cmd = ["python", "-m", "pokerbot.benchmark.slumbot", "--hands", str(hands)]
    if exploit_primary:
        cmd.append("--exploit-primary")
    p = subprocess.run(cmd, cwd=str(config.ROOT), capture_output=True, text=True, timeout=3600)
    tail = (p.stdout or "")[-1500:]
    m = re.search(r"win-rate\s*(-?[\d.]+)\s*bb/100.*?([\d.]+)\s*stderr", tail, re.S)
    res = {"target": "external-near-GTO (exploitable)", "grade": f"directional (network, noise~{_noise(hands)})",
           "exploit_primary": exploit_primary, "n": hands}
    if m:
        res["bb100"], res["se"] = float(m.group(1)), float(m.group(2))
    else:
        res["raw_tail"] = tail
    return res


# ----------------------------------------------------------------- runner
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="offline smoke (small N)")
    ap.add_argument("--full", action="store_true", help="large N + Slumbot (network)")
    ap.add_argument("--hands", type=int, default=0, help="override per-axis hand count")
    ap.add_argument("--iters", type=int, default=80, help="equity MC iters (lower=faster, directional)")
    args = ap.parse_args()
    botmod.EQUITY_ITERS = args.iters

    full = args.full
    H = args.hands or (1500 if full else 500)        # unpaired-axis hands
    DECKS = 600 if full else 250                     # paired-axis decks
    GLIM = None if full else 250                     # floor_map flop boards

    sc = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "git_sha": _git_sha(),
          "agent": "PokerBot(exploit=True) -- the unified MVP",
          "config": {"mode": "full" if full else "quick", "hands": H, "decks": DECKS, "iters": args.iters},
          "axes": {}, "errors": {}}

    axes = [("gto_gap", lambda: axis_gto_gap(GLIM)),
            ("duplicate", lambda: axis_duplicate(DECKS)),
            ("exploit_proof", lambda: axis_exploit_proof(H)),
            ("internal", lambda: axis_internal(H)),
            ("field", lambda: axis_field(min(H, 250)))]
    if full:
        axes.append(("slumbot_floor", lambda: axis_slumbot(H * 2, False)))
        axes.append(("slumbot_exploit", lambda: axis_slumbot(H * 2, True)))

    for name, fn in axes:
        print(f"\n########## axis: {name} ##########", flush=True)
        t0 = time.time()
        try:
            sc["axes"][name] = fn()
            sc["axes"][name]["seconds"] = round(time.time() - t0, 1)
        except Exception as e:  # noqa: BLE001
            sc["errors"][name] = f"{type(e).__name__}: {e}"
            print(f"  !! {name} failed: {e}")
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(sc, indent=2), encoding="utf-8")   # write partial after each axis

    _summary(sc)
    print(f"\nSaved -> {OUT}")


def _verdict(label, ok, watch):
    return "PASS" if ok else ("WATCH" if watch else "FAIL")


def _summary(sc):
    a = sc["axes"]
    print("\n" + "=" * 72)
    print("DEFINITIVE SCORECARD -- unified MVP (PokerBot exploit-primary)")
    print(f"  {sc['config']['mode']} mode | {sc['git_sha']} | {sc['timestamp']}")
    print("=" * 72)
    print("\n--- TARGET 1: LEAST-LOSS vs near-GTO (decision-grade; ceiling ~break-even) ---")
    if "gto_gap" in a and "ALL" in a["gto_gap"].get("buckets", {}):
        g = a["gto_gap"]["buckets"]["ALL"]["gto_gap"]
        print(f"  flop GTO-gap (vs TexasSolver) : {g:.0%}   [{_verdict('', g < 0.25, g < 0.35)}]  (0=GTO-plausible, flop-only)")
    if "duplicate" in a:
        d = a["duplicate"]
        fb = d["floor_vs_gtobaseline"]
        print(f"  floor vs GTOBaseline (paired) : {fb['bb100']:+.1f} +/- {fb['se']:.1f} bb/100   "
              f"[{_verdict('', fb['bb100'] > -10, fb['bb100'] > -30)}]  (null={d['null_floor_vs_floor']['bb100']:+.1f})")
    print("\n--- TARGET 2: EXPLOIT EDGE vs the field (directional unless paired) ---")
    if "internal" in a:
        for opp, v in a["internal"]["vs"].items():
            print(f"  vs {opp:8s} : {v['bb100']:+8.1f} +/- {v['se']:.0f} bb/100   [{_verdict('', v['bb100'] > 50, v['bb100'] > 0)}]")
    if "field" in a:
        f = a["field"]
        print(f"  beat-them-all WORST          : {f['worst']:+.1f} bb/100   "
              f"[{'PASS (beats all)' if f['beats_all'] else 'WATCH'}]")
    if "exploit_proof" in a:
        v = a["exploit_proof"]
        print(f"  exploit_proof (size-cliff)   : delta {v['paired_delta']:+.1f} +/- {v['delta_se']:.1f} bb/100 "
              f"(floor {v['floor_bb100']:+.0f} -> exploit {v['exploit_bb100']:+.0f})")
    if "slumbot_floor" in a or "slumbot_exploit" in a:
        print("\n--- EXTERNAL near-GTO (Slumbot, re-roled exploitable; wide) ---")
        for k in ("slumbot_floor", "slumbot_exploit"):
            if k in a and "bb100" in a[k]:
                print(f"  {k:16s} : {a[k]['bb100']:+.1f} +/- {a[k]['se']:.1f} bb/100  (n={a[k]['n']})")
    if sc["errors"]:
        print("\n  ERRORS:", sc["errors"])
    print("\nNOTE: paired/deterministic axes are decision-grade; unpaired bb/100 are directional "
          "(see each axis's noise floor). The exploit edge is learning-driven -> shown vs the field, not the duplicate.")


if __name__ == "__main__":
    main()
