"""GTO oracle: harvest TexasSolver (open-source SOTA NLHE solver) as a local GTO reference.

We do NOT brute-force this on a GPU — TexasSolver runs a direct (Discounted-CFR-class) solve of a
postflop spot in milliseconds on CPU and dumps the exact GTO strategy as JSON. We use it to
  (1) VERIFY our analytic `gto_baseline` against true GTO (the oracle we lacked without a GTO Wizard key),
  (2) generate SUPERVISED distillation targets to train/upgrade the baseline cheaply.

Driving the bundled console binary:  console_solver.exe -i <input.txt>  (cwd must be the solver dir).
Input grammar (verified against the shipped sample_parameters): set_pot / set_effective_stack /
set_board / set_range_oop / set_range_ip / set_bet_sizes <pos>,<street>,<bet|raise|donk|allin>[,sizes]
/ set_allin_threshold / build_tree / set_thread_num / set_accuracy / set_max_iteration /
set_use_isomorphism / start_solve / set_dump_rounds / dump_result <file>.

Cards are 2-char ('As','Td','2h') — same as our engine. Combo keys in the dump are concatenated
('AsKd'); lookup here is order-insensitive.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

# Bundled OSS solver (TexasSolver v0.2.0). Path is the tool location, not a secret.
SOLVER_DIR = Path(os.environ.get("TEXASSOLVER_DIR",
                                 r"C:\Users\hampe\Desktop\PokerB\tools\TexasSolver-v0.2.0-Windows"))
EXE = SOLVER_DIR / ("console_solver.exe" if os.name == "nt" else "console_solver")

# Reasonable default bet trees (kept small for speed; solver only uses streets it reaches).
_DEFAULT_BETS = [
    "set_bet_sizes oop,flop,bet,33,75", "set_bet_sizes oop,flop,raise,60", "set_bet_sizes oop,flop,allin",
    "set_bet_sizes ip,flop,bet,33,75", "set_bet_sizes ip,flop,raise,60", "set_bet_sizes ip,flop,allin",
    "set_bet_sizes oop,turn,bet,50,100", "set_bet_sizes oop,turn,raise,60", "set_bet_sizes oop,turn,allin",
    "set_bet_sizes ip,turn,bet,50,100", "set_bet_sizes ip,turn,raise,60", "set_bet_sizes ip,turn,allin",
    "set_bet_sizes oop,river,bet,50,100", "set_bet_sizes oop,river,raise,60", "set_bet_sizes oop,river,allin",
    "set_bet_sizes ip,river,bet,50,100", "set_bet_sizes ip,river,raise,60", "set_bet_sizes ip,river,allin",
]


def available() -> bool:
    return EXE.exists()


# S5 (plan 2026-07-04): persistent DISK cache for solves. Semantics-neutral (the key covers every input that
# shapes the solve), so it defaults ON; POKERB_SOLVE_CACHE=0 disables. Biggest payoff in the $0 loops
# (duplicate.py mirrored decks hit the same boards twice; repeated grading runs re-hit spots).
_CACHE_ON = os.environ.get("POKERB_SOLVE_CACHE", "1") == "1"
_CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "_solve_cache"


def _cache_key(board, oop, ip, pot, eff, bets, accuracy, max_iter, dump_rounds, mode) -> str:
    import hashlib
    blob = "|".join([",".join(board), oop, ip, f"{pot:.1f}", f"{eff:.1f}",
                     ";".join(bets), f"{accuracy}", f"{max_iter}", f"{dump_rounds}", mode])
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()


def solve(board, oop_range: str, ip_range: str, pot: float = 20.0, eff_stack: float = 100.0,
          bets=None, accuracy: float = 0.5, max_iter: int = 150, threads: int = 8,
          allin_threshold: float = 0.67, dump_rounds: int = 2, timeout: int = 180,
          keep_files: bool = False, tag=None, mode: str = "holdem") -> dict:
    """Solve one postflop spot; return the root (first-to-act) node dict from the dumped JSON.

    board: list like ['Qs','Jh','2h'] (flop) up to 5 cards (river).
    oop_range / ip_range: TexasSolver range strings (e.g. 'AA,KK,AKs,AQs:0.5,...').
    mode: 'holdem' (52-card, default) or 'shortdeck' (36-card 6+ Hold'em). TexasSolver v0.2.0 ships short-deck
        natively (correct rankings: flush > full house, A-6-7-8-9 wheel; dict card5_dic_sorted_shortdeck.txt =
        C(36,5)). For short-deck pass mode='shortdeck' AND short-deck range strings (6-A ranks only). Verified
        2026-06-15 (movie-factory run): solve converges + the dump parses through strategy_for unchanged.
    """
    if not EXE.exists():
        raise FileNotFoundError(f"TexasSolver console binary not found at {EXE}")
    if mode not in ("holdem", "shortdeck"):
        raise ValueError(f"mode must be 'holdem' or 'shortdeck', got {mode!r}")
    ck = None
    if _CACHE_ON:
        ck = _cache_key(board, oop_range, ip_range, pot, eff_stack, bets or _DEFAULT_BETS,
                        accuracy, max_iter, dump_rounds, mode)
        cpath = _CACHE_DIR / f"{ck}.json"
        if cpath.exists():
            try:
                return json.loads(cpath.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001 — corrupt cache entry: fall through to a fresh solve
                pass
    file_tag = tag if tag is not None else os.getpid()
    inp = SOLVER_DIR / f"_oracle_in_{file_tag}.txt"
    out = SOLVER_DIR / f"_oracle_out_{file_tag}.json"
    lines = [
        f"set_pot {pot}", f"set_effective_stack {eff_stack}",
        "set_board " + ",".join(board),
        "set_range_oop " + oop_range,
        "set_range_ip " + ip_range,
        *(bets or _DEFAULT_BETS),
        f"set_allin_threshold {allin_threshold}",
        "build_tree",
        f"set_thread_num {threads}", f"set_accuracy {accuracy}",
        # BUG-HUNT FIX: interval was hardcoded 100 -> solves with max_iter<=100 recorded the ITER-0 (pre-solve)
        # exploitability and bigger solves a mid-run value. Prints land at 0, k*I+1, ... — I=(max_iter-2)//2
        # guarantees the last print sits near the END, so _exploitability_pct reflects achieved convergence.
        f"set_max_iteration {max_iter}", f"set_print_interval {max(1, (max_iter - 2) // 2)}",
        "set_use_isomorphism 1", "start_solve",
        f"set_dump_rounds {dump_rounds}", f"dump_result {out.name}",
    ]
    inp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    cmd = [str(EXE), "-i", inp.name]
    if mode != "holdem":                      # short-deck (6+) is a CLI flag; the input grammar is identical
        cmd += ["--mode", mode]
    try:
        proc = subprocess.run(cmd, cwd=str(SOLVER_DIR),
                              capture_output=True, text=True, timeout=timeout)
        data = json.loads(out.read_text(encoding="utf-8"))
        # P0-B convergence audit (plan 2026-07-04 #2): TexasSolver prints its achieved exploitability per
        # print_interval; we previously DISCARDED it — so solve quality was never observed (Supremus's central
        # lesson: unconverged solves are where re-solvers silently bleed). Parse the LAST reported value and
        # attach it to the result (and thus the persistent cache). Consumers read data["_exploitability_pct"].
        expl = _parse_exploitability(proc.stdout or "")
        if expl is not None:
            data["_exploitability_pct"] = expl
            data["_solve_iters"] = max_iter
    finally:
        if not keep_files:
            for f in (inp, out):
                try:
                    f.unlink()
                except OSError:
                    pass
    if _CACHE_ON and ck is not None:
        try:
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            tmp = _CACHE_DIR / f"_{ck}.{os.getpid()}.tmp"      # atomic-ish write (concurrent hands share the dir)
            tmp.write_text(json.dumps(data), encoding="utf-8")
            tmp.replace(_CACHE_DIR / f"{ck}.json")
        except Exception:  # noqa: BLE001 — cache write failures never break a solve
            pass
    return data


def _parse_exploitability(stdout: str):
    """Last exploitability the solver reported (percent-of-pot units as printed), or None.
    TexasSolver prints progress lines per print_interval; the final one = the achieved convergence."""
    last = None
    for m in re.finditer(r"exploitability[^0-9\-]*([0-9]*\.?[0-9]+)", stdout, re.IGNORECASE):
        last = float(m.group(1))
    return last


def _key(node: dict) -> dict:
    """{frozenset({c1,c2}): [probs]} for order-insensitive combo lookup.
    NULL-SAFE: TexasSolver dumps the per-combo `strategy` ONLY for the dumped ROOT node; deeper nodes
    (e.g. IP after an OOP check) carry `"strategy": null`. `(x or {})` guards both a missing key and an
    explicit null so a caller navigating to such a node gets {} (-> strategy_for None -> floor) instead of
    an AttributeError crash. (Bug found via the P0 end-to-end smoke, 2026-06-15.)"""
    strat = (node.get("strategy") or {}).get("strategy") or {}
    out = {}
    for combo, probs in strat.items():
        out[frozenset((combo[:2], combo[2:4]))] = probs
    return out


def strategy_for(node: dict, c1: str, c2: str) -> dict | None:
    """GTO action->probability for a specific hand at this node, or None if not in range / not dumped."""
    actions = (node.get("strategy") or {}).get("actions", [])
    probs = _key(node).get(frozenset((c1, c2)))
    if probs is None:
        return None
    return {a: p for a, p in zip(actions, probs)}


def main() -> None:
    if not available():
        print(f"solver missing at {EXE}")
        return
    # Demo: single-raised-pot flop, BTN(ip) vs BB(oop), 100bb, pot 5.5bb-ish scaled to 20/200.
    board = ["Qs", "Jh", "2h"]
    oop = "QQ,JJ,TT,99,88,AQs,AJs,KQs,KJs,QJs,JTs,T9s,98s,AQo,KQo,A5s,A4s,76s,65s"
    ip = "AA,KK,QQ,AKs,AQs,AJs,ATs,KQs,KJs,QJs,JTs,T9s,99,88,77,A5s,A4s,KQo,AQo"
    print(f"Solving flop {board} (pot 20, stack 100)...")
    node = solve(board, oop, ip, pot=20, eff_stack=100, accuracy=0.5, max_iter=120, dump_rounds=1)
    actions = node.get("strategy", {}).get("actions", [])
    print(f"root player={node.get('player')} actions={actions}")
    for hand in [("As", "Ks"), ("Ah", "Qh"), ("7s", "6s"), ("Jc", "Ts")]:
        s = strategy_for(node, *hand)
        if s:
            print(f"  {hand[0]}{hand[1]}: " + ", ".join(f"{a.split()[0]} {p:.0%}" for a, p in s.items()))


if __name__ == "__main__":
    main()
