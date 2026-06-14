"""Blindspot Radar — AI-triaged active learning (2026 way: don't brute-force-solve everything).

Flow:
  1. CAPTURE: play PokerBot(exploit) vs a diverse mix, log every hero decision with full context.
  2. TRIAGE (massive, concurrent Claude Haiku): for each decision, "is this theoretically sound? if not,
     error type + severity + confidence". Haiku = cheap/broad/fallible recall.
  3. RANK + CLUSTER: the suspected blindspots, ranked by severity*confidence, grouped by street/texture/error.
  4. (next step) VERIFY: solve ONLY the top clusters with TexasSolver (the truth) -> filters Haiku's
     hallucinations and quantifies the real leak. This is the compute saving: solve a triaged subset, not
     the whole tree.

Run:  python -m extraction.blindspot_radar --capture-hands 150 --cap 300 --workers 8
"""
from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

import anthropic

from pokerbot import config
from pokerbot.benchmark.beat_them_all import (opp_maniac, opp_pokerbot, opp_station, opp_synthetic)
from pokerbot.engine.game import HeadsUpGame
from pokerbot.strategy import postflop as pf
from pokerbot.strategy.bot import PokerBot

TRIAGE_SYS = (
    "You are a world-class heads-up No-Limit Hold'em GTO + exploitation expert auditing a bot's individual "
    "decisions to find BLINDSPOTS (systematic, theoretically-wrong plays). For each decision judge whether it "
    "is defensible. Be rigorous and SKEPTICAL of the bot, but do NOT invent problems: every flag is verified "
    "by a solver downstream, and false positives waste that compute. Justify each flag with concrete poker "
    "theory (range vs range, MDF, pot odds, polarization, blockers, SPR/commitment, reverse implied odds). "
    "Rate your confidence honestly; a decision that is fine should be marked sound."
)

TRIAGE_INSTR = (
    "For EACH numbered decision below, return a JSON array element:\n"
    '{"i": <index>, "sound": true|false, "error_type": '
    '"overfold|overcall|calldown_too_light|thin_value_too_big|missed_value|spew_bluff|under_bluff|'
    'wrong_size|bad_preflop|fine|other", "severity": "low|med|high", "ev_leak_bb100": <number>, '
    '"confidence": 0.0-1.0, "why": "<one concrete sentence>"}\n'
    "Return ONLY a JSON array, nothing else. Mark defensible decisions sound=true, error_type=fine."
)


def capture(hands: int, iters: int, seed: int = 7) -> list[dict]:
    """Play PokerBot(exploit) vs a diverse mix; log every hero decision + context."""
    import pokerbot.strategy.bot as botmod
    botmod.EQUITY_ITERS = iters
    R = random.Random
    opps = {"station": opp_station(R(1)), "maniac": opp_maniac(R(2)),
            "sticky": opp_synthetic(R(5), 0.12, 0.25, 0.7),
            "trappy": opp_synthetic(R(6), 0.40, 0.55, 1.1), "strong": opp_pokerbot(99)}
    spots: list[dict] = []
    for oname, odec in opps.items():
        g = HeadsUpGame(names=("Bot", oname), starting_stack=20000, sb=50, bb=100, seed=seed)
        bot = PokerBot(0, seed=seed, exploit=True)
        for _ in range(hands):
            g.players[0].stack = g.players[1].stack = 20000
            g.start_hand()
            guard = 0
            while not g.hand_over:
                st = g.state()
                if st["to_act"] == 0:
                    bot.hero_idx = 0
                    d = bot.decide(st)
                    rat = d.get("rationale", {})
                    la = st["legal"]
                    spots.append({
                        "vs": oname, "street": st["street"], "board": " ".join(st["board"]),
                        "hand": " ".join(st["players"][0]["hole"]),
                        "pos": "IP" if st["players"][0] is st["players"][st["button"]] else "OOP",
                        "pot": la["pot"], "to_call": la["to_call"],
                        "facing": "facing_bet" if la["to_call"] > 0 else "first_to_act",
                        "action": d["action"], "amount": d["amount"],
                        "made": rat.get("made_hand"), "equity": rat.get("equity"),
                        "reasoning": rat.get("reasoning"),
                    })
                    a, amt = d["action"], d["amount"]
                else:
                    a, amt = odec(st)
                    bot.observe_opponent(st["street"], a, st["legal"]["to_call"] > 0)
                g.act(a, amt)
                guard += 1
                if guard > 200:
                    break
            bot.observe_hand_end()
    return spots


def sample(spots: list[dict], cap: int, seed: int = 0) -> list[dict]:
    """Diverse subset: bucket by (street, texture, action), round-robin up to cap. Postflop-weighted."""
    rng = random.Random(seed)
    def texkey(s):
        b = s["board"].split()
        if len(b) < 3:
            return "preflop"
        t = pf.classify_board(b)
        return pf.flop_class(t)
    buckets = defaultdict(list)
    for s in spots:
        buckets[(s["street"], texkey(s), s["action"])].append(s)
    for v in buckets.values():
        rng.shuffle(v)
    # round-robin across buckets, de-prioritising preflop folds (least interesting)
    order = sorted(buckets, key=lambda k: (k[0] == "preflop", -len(buckets[k])))
    out, i = [], 0
    while len(out) < cap and any(buckets[k] for k in order):
        k = order[i % len(order)]
        if buckets[k]:
            out.append(buckets[k].pop())
        i += 1
    return out


def _fmt(i: int, s: dict) -> str:
    return (f'#{i} [{s["street"]}|{s["board"] or "preflop"}] {s["pos"]} hand={s["hand"]} '
            f'made={s["made"]} eq={s["equity"]} {s["facing"]} pot={s["pot"]} to_call={s["to_call"]} '
            f'-> {s["action"]} {s["amount"]} | bot_reasoning: {s["reasoning"]}')


def triage(spots: list[dict], batch: int, workers: int) -> list[dict]:
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    batches = [list(range(i, min(i + batch, len(spots)))) for i in range(0, len(spots), batch)]

    def run_batch(idxs):
        body = "\n".join(_fmt(j, spots[j]) for j in idxs)
        try:
            m = client.messages.create(
                model=config.CLAUDE_HAIKU_MODEL, max_tokens=2200, system=TRIAGE_SYS,
                messages=[{"role": "user", "content": TRIAGE_INSTR + "\n\nDECISIONS:\n" + body}])
            raw = "".join(b.text for b in m.content if b.type == "text").strip()
            arr = json.loads(raw[raw.index("["):raw.rindex("]") + 1])
            return arr
        except Exception as e:  # noqa: BLE001
            return [{"i": j, "sound": True, "error_type": "parse_error", "severity": "low",
                     "confidence": 0.0, "why": str(e)[:80]} for j in idxs]

    out = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for arr in ex.map(run_batch, batches):
            out.extend(arr)
    # attach the spot back
    by_i = {a.get("i"): a for a in out if isinstance(a, dict)}
    merged = []
    for j, s in enumerate(spots):
        a = by_i.get(j, {})
        merged.append({**s, **{k: a.get(k) for k in
                       ("sound", "error_type", "severity", "ev_leak_bb100", "confidence", "why")}})
    return merged


def report(rows: list[dict]) -> None:
    SEV = {"high": 3, "med": 2, "low": 1, None: 0}
    flagged = [r for r in rows if r.get("sound") is False and r.get("error_type") not in ("fine", "parse_error")]
    for r in flagged:
        r["_score"] = SEV.get(r.get("severity"), 0) * (r.get("confidence") or 0.0)
    flagged.sort(key=lambda r: -r["_score"])

    out = config.DATA_DIR / "sessions" / "blindspot_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"n_spots": len(rows), "n_flagged": len(flagged), "flagged": flagged},
                              indent=2), encoding="utf-8")

    print(f"\n=== BLINDSPOT RADAR: {len(flagged)}/{len(rows)} decisions flagged ===")
    clusters = defaultdict(lambda: [0, 0.0])
    for r in flagged:
        key = (r["street"], r.get("error_type"))
        clusters[key][0] += 1
        clusters[key][1] += r["_score"]
    print("\nTop blindspot CLUSTERS (street, error_type) by count x severity:")
    for (street, err), (n, sc) in sorted(clusters.items(), key=lambda kv: -kv[1][1])[:12]:
        print(f"  {street:7s} {str(err):20s} n={n:3d}  score={sc:.1f}")
    print("\nTop individual flags (to verify with the solver):")
    for r in flagged[:10]:
        print(f"  [{r['severity']}|c={r.get('confidence')}] {r['street']}|{r['board'] or 'pf'} "
              f"{r['pos']} {r['hand']} {r['facing']} -> {r['action']} {r['amount']}: {r.get('why')}")
    print(f"\nFull report -> {out}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--capture-hands", type=int, default=150)
    ap.add_argument("--iters", type=int, default=80)
    ap.add_argument("--cap", type=int, default=300)
    ap.add_argument("--batch", type=int, default=6)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    print(f"CAPTURE: PokerBot(exploit) vs 5 opponents, {args.capture_hands} hands each ...", flush=True)
    spots = capture(args.capture_hands, args.iters)
    print(f"  captured {len(spots)} decisions", flush=True)
    chosen = sample(spots, args.cap)
    print(f"TRIAGE: {len(chosen)} diverse spots via {config.CLAUDE_HAIKU_MODEL} "
          f"({args.workers} workers, batch {args.batch}) ...", flush=True)
    rows = triage(chosen, args.batch, args.workers)
    report(rows)


if __name__ == "__main__":
    main()
