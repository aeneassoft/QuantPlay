"""Grounded blindspot finder: where our analytic floor (GTOBaseline) most DISAGREES with the solver,
per-spot, straight from the TexasSolver cache. This is the GROUNDED acquisition signal for active learning
(which spots to solve more / fix) — no LLM opinion, no play-noise. The thin_value episode showed LLM triage
is a fallible hypothesis; this is truth. Reuses the gto_benchmark cache (no new solving).

Run:  python -m extraction.grounded_blindspots --boards 14 --top 25
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict

import json

from pokerbot import config
from pokerbot.benchmark.gto_benchmark import _CACHE, boards, make_state, texture
from pokerbot.strategy.gto_baseline import GTOBaseline


def _score_node(nd: dict, board, role: str, tex: str, hero, rows: list[dict]) -> None:
    s = nd.get("strategy", {})
    actions, strat = s.get("actions", []), s.get("strategy", {})
    if not actions or not strat:
        return
    bet_idx = [i for i, a in enumerate(actions) if a.split()[0] in ("BET", "RAISE", "ALLIN")]
    check_idx = next((i for i, a in enumerate(actions) if a.split()[0] == "CHECK"), None)
    hero.hero = 0
    for combo, probs in strat.items():
        a, _ = hero.decide(make_state((combo[:2], combo[2:4]), board, role))
        our_bet = a in ("bet", "raise")
        g_bet = sum(probs[i] for i in bet_idx)
        p_ourkind = g_bet if our_bet else (probs[check_idx] if check_idx is not None else 0.0)
        rows.append({"board": "".join(board), "tex": tex, "role": role, "combo": combo,
                     "bot": "bet" if our_bet else "check", "gto_bet": round(g_bet, 2),
                     "div": round(1 - p_ourkind, 3)})


def divergences(nb: int) -> list[dict]:
    """Score per-combo divergence vs the cache, matching gto_benchmark's node mapping:
    OOP = the root node (OOP acts first); IP = the child AFTER OOP checks."""
    hero = GTOBaseline(0, seed=1, iters=200)
    rows: list[dict] = []
    for board in boards(nb):
        cf = _CACHE / ("".join(board) + ".json")
        if not cf.exists():
            continue
        node = json.loads(cf.read_text(encoding="utf-8"))
        ip = next((v for k, v in (node.get("childrens") or {}).items() if k.split()[0] == "CHECK"), None)
        tex = texture(board)
        _score_node(node, board, "OOP", tex, hero, rows)
        if ip is not None:
            _score_node(ip, board, "IP", tex, hero, rows)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--boards", type=int, default=14)
    ap.add_argument("--top", type=int, default=25)
    args = ap.parse_args()

    rows = divergences(args.boards)
    if not rows:
        print("no cached nodes scored (cache empty or solver missing)")
        return
    rows.sort(key=lambda r: -r["div"])
    clu = defaultdict(lambda: [0, 0.0])
    for r in rows:
        c = clu[(r["tex"], r["role"])]
        c[0] += 1
        c[1] += r["div"]

    out = config.DATA_DIR / "sessions" / "grounded_blindspots.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"n": len(rows), "top": rows[:200]}, indent=2), encoding="utf-8")

    print(f"=== GROUNDED blindspots (GTOBaseline vs solver cache, {len(rows)} spots) ===")
    print("Worst (role, texture) clusters by MEAN divergence (how far our floor is from GTO):")
    for (tex, role), (n, sc) in sorted(clu.items(), key=lambda kv: -kv[1][1] / max(1, kv[1][0]))[:10]:
        print(f"  {role} {tex:10s} mean_div={sc/n:.0%}  (n={n})")
    print("\nTop individual disagreements (GROUNDED — these are what to solve/fix, not LLM guesses):")
    shown = 0
    for r in rows:
        if r["div"] > 0.55 and shown < args.top:
            print(f"  {r['role']} {r['board']} ({r['tex']:9s}) {r['combo']}: "
                  f"bot={r['bot']:5s} but GTO bets {r['gto_bet']:.0%}  -> div {r['div']:.0%}")
            shown += 1
    print(f"\nFull report -> {out}")


if __name__ == "__main__":
    main()
