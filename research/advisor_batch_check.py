"""Identitaets-Wache fuer den Advisor-Batch-Pfad (2026-08-16).

p_bet_batch MUSS numerisch dasselbe liefern wie N einzelne p_bet-Aufrufe
(Toleranz 1e-6; float32-Batch-Matmul darf die Summierreihenfolge aendern,
mehr nicht). Laeuft als Gate vor jedem Refactor an advisor/range_tracker.

  python -m research.advisor_batch_check
"""
from __future__ import annotations

import random
import sys


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from pokerbot.strategy import advisor
    rng = random.Random(3)
    fails = 0
    for street, board in (("flop", ["Ah", "7d", "2c"]), ("turn", ["Ah", "7d", "2c", "Td"]),
                          ("river", ["Ah", "7d", "2c", "Td", "3s"])):
        deck = [r + s for r in "23456789TJQKA" for s in "shdc" if r + s not in board]
        combos = [tuple(rng.sample(deck, 2)) for _ in range(200)]
        for role in ("ip", "oop"):
            einzel = {tuple(c): advisor.p_bet(list(c), board, role, street) for c in combos}
            advisor._PBET_MEMO.clear()
            batch = advisor.p_bet_batch(combos, board, role, street)
            worst = max(abs((einzel[t] or 0) - (batch[t] or 0)) for t in map(tuple, combos))
            ok = worst < 1e-6
            fails += 0 if ok else 1
            print(f"{street}/{role}: max|diff| {worst:.2e} {'PASS' if ok else 'FAIL'}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
