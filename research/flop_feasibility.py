"""PRINCE v2 P3 go/no-go: can we afford a FLOP->terminal re-solve? Times TexasSolver on ~50 REAL flop spots
(boards + pots from the live GTOW session logs) with a lean 3-street census tree. The number that decides:
solve-time distribution + timeout rate + achieved exploitability (via the P0-B parse). A flop subtree is ~50x
the turn tree; turn measured 5.5s at census settings -> the hypothesis is that lean flop trees are live-viable."""
from __future__ import annotations

import glob
import json
import time

from pokerbot.strategy import gto_oracle as O

N_SPOTS = 50
TIMEOUT_S = 300
ACC, ITERS = 0.5, 150
# lean 3-street tree (the go/no-go tree; the real flop_resolve would start here and only grow if converged+fast)
FLOP_BETS = [
    "set_bet_sizes oop,flop,bet,33,75", "set_bet_sizes oop,flop,raise,50", "set_bet_sizes oop,flop,allin",
    "set_bet_sizes ip,flop,bet,33,75", "set_bet_sizes ip,flop,raise,50", "set_bet_sizes ip,flop,allin",
    "set_bet_sizes oop,turn,bet,75", "set_bet_sizes oop,turn,raise,75", "set_bet_sizes oop,turn,allin",
    "set_bet_sizes ip,turn,bet,75", "set_bet_sizes ip,turn,raise,75", "set_bet_sizes ip,turn,allin",
    "set_bet_sizes oop,river,bet,65,100", "set_bet_sizes oop,river,raise,60", "set_bet_sizes oop,river,allin",
    "set_bet_sizes ip,river,bet,65,100", "set_bet_sizes ip,river,raise,60", "set_bet_sizes ip,river,allin",
]
# SRP-entry ranges: the PROVEN solver-safe strings from api.py (explicit class enumeration — TexasSolver rejects
# offsuit "+" shorthand with "format not recognize" AT SOLVE TIME, after a successful tree build; measured here).
from pokerbot.brain.api import _HU_IP as IP, _HU_OOP as OOP  # noqa: E402


def flop_spots():
    """(board3, pot_bb_chips, eff_stack) from the newest session logs — hands that reached the flop."""
    spots, seen = [], set()
    for f in sorted(glob.glob("data/sessions/gtow_hands_*.jsonl"), reverse=True):
        for line in open(f, encoding="utf-8"):
            try:
                h = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            b = h.get("board") or ""
            if len(b) < 6:
                continue
            board3 = [b[i:i + 2] for i in (0, 2, 4)]
            key = "".join(board3)
            if key in seen:
                continue
            # preflop pot from the history tokens (up to the first street marker "_")
            hist = h.get("history") or []
            if "_" not in hist:
                continue          # bug-hunt fix: a board with no round-end marker = a preflop all-in runout, never a flop decision
            level = [0.0, 100.0]        # committed per actor this street; BB posts 100 (bb=100 chips)
            level[0] = 50.0             # SB posts
            i_act = 0
            for tok in hist:
                if tok == "_":
                    break
                if tok.startswith("b"):
                    level[i_act % 2] = float(tok[1:])
                elif tok in ("c", "k"):
                    if tok == "c":
                        level[i_act % 2] = level[(i_act + 1) % 2]
                i_act += 1
            pot = sum(level)
            if pot < 150:
                continue
            seen.add(key)
            spots.append((board3, pot, 20000 - max(level)))
            if len(spots) >= N_SPOTS:
                return spots
    return spots


def main() -> None:
    spots = flop_spots()
    print(f"{len(spots)} flop spots | tree=lean census 3-street | acc={ACC} iters={ITERS} timeout={TIMEOUT_S}s")
    times, expls, fails = [], [], 0
    for i, (board, pot, eff) in enumerate(spots):
        t0 = time.time()
        try:
            r = O.solve(board, OOP, IP, pot=pot, eff_stack=eff, bets=FLOP_BETS,
                        accuracy=ACC, max_iter=ITERS, dump_rounds=1, threads=8, timeout=TIMEOUT_S,
                        tag=f"ffeas{i}")
            dt = time.time() - t0
            times.append(dt)
            e = r.get("_exploitability_pct")
            if e is not None:
                expls.append(e)
            print(f"  {''.join(board):8s} pot={pot:6.0f}  {dt:6.1f}s  expl={e}")
        except Exception as ex:  # noqa: BLE001
            fails += 1
            print(f"  {''.join(board):8s} pot={pot:6.0f}  FAILED {type(ex).__name__} after {time.time()-t0:.0f}s")
    if times:
        times.sort()
        med = times[len(times) // 2]
        p90 = times[int(len(times) * 0.9)]
        print(f"\nGO/NO-GO: n={len(times)} ok, {fails} failed | median {med:.1f}s  p90 {p90:.1f}s  max {times[-1]:.1f}s")
        if expls:
            expls.sort()
            print(f"exploitability: median {expls[len(expls)//2]:.2f}%pot  worst {expls[-1]:.2f}%pot")
        print("VERDICT:", "GO (median <= 60s, p90 <= 150s, fails <= 10%)"
              if med <= 60 and p90 <= 150 and fails <= len(spots) * 0.1 else "NO-GO -> fallback 3b")


if __name__ == "__main__":
    main()
