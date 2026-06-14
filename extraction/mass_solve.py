"""Hammer the spare CPU cores: mass-solve random boards with TexasSolver into the GTO cache. Builds a big
distillation dataset (solver imitation) for free. Designed to run on the LOCAL machine ALONGSIDE the GPU
fine-tune on the pod (CPU+GPU must live on separate boxes — a heavy CPU job starves a GPU-training box).

RAM-ADAPTIVE: each concurrent solve is a separate console_solver process (~400-500 MB). On a RAM-limited
box (e.g. 16 GB) RAM, not CPU, is the binding constraint. Each round we measure free physical RAM and run
only as many parallel solves as fit above a safety floor — so it auto-scales up when you free RAM and backs
off when you don't, and never swaps the machine to a freeze. Progress is per-board JSON in the cache, written
atomically; stopping/restarting loses nothing (cached boards are skipped).

Run: python -m extraction.mass_solve [minutes] [max_workers] [threads_per_solve] [min_free_mb] [mb_per_solve]
"""
from __future__ import annotations

import ctypes
import json
import os
import random
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from pokerbot import config
from pokerbot.benchmark.gto_benchmark import _IP, _OOP
from pokerbot.strategy import gto_oracle as O
from pokerbot.strategy.distill import CARDS, SMALL_BETS

MINUTES = float(sys.argv[1]) if len(sys.argv) > 1 else 24.0
CEILING = int(sys.argv[2]) if len(sys.argv) > 2 else 10       # max parallel solves (RAM permitting)
THREADS = int(sys.argv[3]) if len(sys.argv) > 3 else 3        # cpu threads per solve
MIN_FREE = float(sys.argv[4]) if len(sys.argv) > 4 else 1500  # keep this many MB free for the OS/user
PER_SOLVE = float(sys.argv[5]) if len(sys.argv) > 5 else 550  # est. peak MB per concurrent solve
STACKS = [int(x) for x in os.environ.get("STACKS", "100").split(",")]   # stack depths -> SPR coverage
DUMP = int(os.environ.get("DUMP", "1"))                                 # 1=flop only, 2=+turn (broader coverage)
CACHE = config.DATA_DIR / "_gto_bench_cache"
CACHE.mkdir(parents=True, exist_ok=True)


class _MEMSTATUS(ctypes.Structure):
    _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


def free_mb() -> float:
    """Available physical RAM in MB (Windows GlobalMemoryStatusEx, no deps). Non-Windows -> no throttle."""
    try:
        m = _MEMSTATUS()
        m.dwLength = ctypes.sizeof(m)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))  # type: ignore[attr-defined]
        return m.ullAvailPhys / (1024 * 1024)
    except Exception:  # noqa: BLE001
        return 1e9


def fit_workers() -> int:
    """How many parallel solves fit right now, above the safety floor (1..CEILING)."""
    return max(1, min(CEILING, int((free_mb() - MIN_FREE) / PER_SOLVE)))


def solve_one(_):
    b = random.sample(CARDS, 3)
    stack = random.choice(STACKS)
    name = "".join(b) + (f"_{stack}" if len(STACKS) > 1 else "") + ".json"
    cf = CACHE / name
    if cf.exists():
        return 0
    try:
        node = O.solve(b, _OOP, _IP, pot=20, eff_stack=stack, accuracy=0.5, max_iter=30,
                       threads=THREADS, bets=SMALL_BETS, dump_rounds=DUMP, timeout=400,
                       tag="ms" + uuid.uuid4().hex[:8])
        tmp = cf.with_name(cf.name + f".{uuid.uuid4().hex[:6]}.tmp")
        tmp.write_text(json.dumps(node))
        os.replace(tmp, cf)            # atomic: a kill mid-write never leaves a corrupt cache file
        return 1
    except Exception:  # noqa: BLE001
        return 0


def main():
    t0, solved = time.time(), 0
    print(f"mass-solve RAM-adaptive: ceiling={CEILING} threads={THREADS} keep_free={MIN_FREE:.0f}MB "
          f"per_solve~{PER_SOLVE:.0f}MB | free now {free_mb():.0f}MB", flush=True)
    with ThreadPoolExecutor(max_workers=CEILING) as ex:
        while (time.time() - t0) / 60 < MINUTES:
            n = fit_workers()
            solved += sum(ex.map(solve_one, range(n)))
            print(f"mass-solve: +{solved} new | cache={len(list(CACHE.glob('*.json')))} | "
                  f"free={free_mb():.0f}MB n={n} | {(time.time()-t0)/60:.1f} min", flush=True)
    print(f"DONE mass-solve: {solved} new boards, cache total {len(list(CACHE.glob('*.json')))}", flush=True)


if __name__ == "__main__":
    main()
