"""research/slumbot_mistakes.py — surface the GAME engine's MISTAKES vs Slumbot from a logged run.

Input: a `slumbot_collect` jsonl (fields: hole_cards, board, bot_hole_cards [showdown only], action, winnings,
won_pot, button, client_pos). Using Slumbot's REVEALED cards, it classifies the biggest realized losses:

  COOLER     hero committed a STRONG made hand and was beaten  -> irreducible variance (unfoldable),
  THIN/-EV   hero committed a WEAK/medium hand and was behind   -> the FIXABLE / RL-targetable slice,
  FOLD/other no showdown (villain hand unknown -> uncategorizable here).

This is the per-hand "where do WE lose, and is it fixable or just variance" answer (the gtow_tail logic on Slumbot).
For the variance-adjusted bb/100, run `slumbot_adjust` on the same jsonl (cancels all-in card luck).

Run:  python -m research.slumbot_mistakes [path=data/slumbot_pokerbot.jsonl] [topN=20]
"""
from __future__ import annotations

import json
import math
import sys

from pokerbot.benchmark.slumbot import BB
from pokerbot.brain import api

_STRONG = 0.45            # hero made-hand strength >= this when committing + losing = COOLER; below = THIN/-EV
                          # (matches the gtow_tail observation: the cooler tail sits at made-hand strength ~0.48-0.76)


def _aggressor_lost_betting(action: str, hero_is_button: bool) -> bool:
    """Heuristic: did hero put the last big money in as the AGGRESSOR (a bet/raise that then lost)? A losing bet is a
    candidate -EV BET (the spew slice); a losing call is a bad call. Coarse — for flavor only."""
    last_street = action.split("/")[-1]
    return "b" in last_street            # a bet/raise token exists on the final street


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "data/slumbot_pokerbot.jsonl"
    topn = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    if not rows:
        print("no rows"); return

    wins = [r["winnings"] for r in rows]
    n, tot = len(wins), sum(wins)
    bb100 = tot / n
    std = (sum((w - bb100) ** 2 for w in wins) / n) ** 0.5 / BB
    print(f"n={n} | RAW {bb100:+.1f} bb/100 (±{std / math.sqrt(n) * 100:.1f} stderr)")

    won = sum(w for w in wins if w > 0)
    sd_loss = sum(r["winnings"] for r in rows if r["winnings"] < 0 and r.get("bot_hole_cards"))
    fold_loss = sum(r["winnings"] for r in rows if r["winnings"] < 0 and not r.get("bot_hole_cards"))
    print(f"won {won:+d} | lost-at-showdown {sd_loss:+d} | lost-by-folding {fold_loss:+d}  (chips)")

    worst = sorted(rows, key=lambda r: r["winnings"])[:topn]
    cooler = thin = other = 0
    thin_chips = cooler_chips = 0
    print(f"\n=== worst {topn} losses ===")
    for r in worst:
        w, hole, board = r["winnings"], r["hole_cards"], (r.get("board") or [])
        villain = r.get("bot_hole_cards")
        if villain and len(board) >= 3:
            ch, sh = api.hand_rank(hole, board)
            cv, sv = api.hand_rank(villain, board)
            if sh >= _STRONG:
                kind, cooler, cooler_chips = "COOLER", cooler + 1, cooler_chips + w
            else:
                bet = _aggressor_lost_betting(r.get("action", ""), r.get("button") == r.get("client_pos"))
                kind, thin, thin_chips = ("THIN/-EV BET" if bet else "THIN/-EV CALL"), thin + 1, thin_chips + w
            print(f"  {w:+6d} | hero {hole} {ch}({sh:.2f})  vs  {villain} {cv}({sv:.2f}) | {board} | {kind}")
        else:
            other += 1
            print(f"  {w:+6d} | hero {hole} | {board} | NO SHOWDOWN (folded) | act={r.get('action','')[:44]}")

    print(f"\nworst-{topn}: COOLER {cooler} ({cooler_chips:+d}) | THIN/-EV {thin} ({thin_chips:+d}) | fold/other {other}")
    print(f"=> the THIN/-EV chips are the FIXABLE slice; COOLER chips are irreducible variance.")


if __name__ == "__main__":
    main()
