"""Process a finished RL pod run into ONE verdict.

The moment `infra.runpod_rl_campaign` self-kills, run:  python -m pipeline.process_run
and you immediately KNOW: did it train, did GRPO beat its SFT init, is the DSL legal, what's the bb/100, and what to do
next — without hand-reading four files.

Reads whatever the campaign pulled back (all optional — missing = "run not finished / stage skipped"):
  models/qwen_poker_grpo.tgz   -> unpacked to models/qwen_poker_grpo (the trained adapter, ready for eval/the live bot)
  data/eval_gates.json         -> the GATE ladder (PokerBench-acc, legality, delta-vs-SFT bb/100, held-out, LBR)
  data/training_metrics.jsonl  -> the GRPO learning curve (frac_bad, reward, reward_std, engine_grounded_rate)
  data/gpu_load.jsonl          -> the empirical full-load proof (util/mem) — filtered to THIS run

$0, no torch — pure read + summarize.
"""
from __future__ import annotations

import json
import tarfile

from pokerbot import config

_ADAPTER_TGZ = config.MODELS_DIR / "qwen_poker_grpo.tgz"
_ADAPTER_DIR = config.MODELS_DIR / "qwen_poker_grpo"
_GATES = config.DATA_DIR / "eval_gates.json"
_METRICS = config.DATA_DIR / "training_metrics.jsonl"
_GPULOAD = config.DATA_DIR / "gpu_load.jsonl"
_RUN_GAP_S = 300   # a >5min gap in gpu_load = a run boundary -> keep only the most recent contiguous block


def _rows(path):
    if not path.exists():
        return []
    out = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def _current_run_start() -> float | None:
    """The start-time of the MOST RECENT contiguous gpu_load block (samples split on a >_RUN_GAP_S gap = a run boundary).
    Used to drop STALE metric rows left from a prior run (training_metrics.jsonl is only truncated at THIS run's GRPO
    start, so before GRPO it still holds the previous run's rows)."""
    rows = _rows(_GPULOAD)
    if not rows:
        return None
    start = rows[-1]["t"]
    for r in reversed(rows[:-1]):
        if start - r["t"] > _RUN_GAP_S:
            break
        start = r["t"]
    return start


def _fresh_metrics() -> list:
    """GRPO metric rows from THIS run only (t >= the current gpu_load run start). Stale rows (older t, or no t when a
    run-start is known) are dropped — so the verdict never fires on a prior run's frac_bad."""
    rows = [r for r in _rows(_METRICS) if "frac_bad" in r or "reward" in r]
    start = _current_run_start()
    if start is None:
        return rows
    return [r for r in rows if isinstance(r.get("t"), (int, float)) and r["t"] >= start]


def unpack_adapter() -> str:
    if _ADAPTER_DIR.exists() and any(_ADAPTER_DIR.iterdir()):
        return f"adapter already unpacked -> {_ADAPTER_DIR.relative_to(config.ROOT)}"
    if not _ADAPTER_TGZ.exists():
        return "no adapter tgz pulled yet (run not finished, or pull failed)"
    with tarfile.open(_ADAPTER_TGZ) as t:
        t.extractall(config.MODELS_DIR)
    return f"unpacked {_ADAPTER_TGZ.name} -> {config.MODELS_DIR.relative_to(config.ROOT)}/ (qwen_poker_grpo or qwen_poker_lora)"


def gate_summary() -> tuple[list[str], bool | None]:
    if not _GATES.exists():
        return ["  (no eval_gates.json yet — eval stage not reached)"], None
    g = json.loads(_GATES.read_text(encoding="utf-8"))
    lines = [f"  {json.dumps(g, indent=2)}"]
    gates = g.get("gates", g)
    passed = gates.get("PASS") if isinstance(gates, dict) else None
    return lines, passed


def curve_summary() -> list[str]:
    rows = _fresh_metrics()
    if not rows:
        return ["  (no FRESH GRPO metrics this run — GRPO not started yet, or early-aborted before logging)"]
    first, last = rows[0], rows[-1]

    def fmt(r, k):
        return f"{r[k]:.3f}" if isinstance(r.get(k), (int, float)) else "—"
    out = [f"  steps logged: {len(rows)}"]
    for k in ("frac_bad", "reward", "reward_std", "engine_grounded_rate", "completions/clipped_ratio"):
        if k in first or k in last:
            out.append(f"  {k:28} first={fmt(first, k)}  ->  last={fmt(last, k)}")
    return out


def gpu_summary() -> list[str]:
    rows = _rows(_GPULOAD)
    if not rows:
        return ["  (no gpu_load samples)"]
    # keep only the most recent contiguous run (split on a >_RUN_GAP_S gap)
    run = [rows[-1]]
    for r in reversed(rows[:-1]):
        if run[0]["t"] - r["t"] > _RUN_GAP_S:
            break
        run.insert(0, r)
    utils = [r["util"] for r in run]
    mems = [r.get("mem_used", 0) for r in run]
    span_min = (run[-1]["t"] - run[0]["t"]) / 60 if len(run) > 1 else 0
    return [f"  this run: {len(run)} samples over ~{span_min:.0f} min | "
            f"avg util {sum(utils) / len(utils):.0f}% (peak {max(utils)}%) | peak mem {max(mems) // 1024} GB"]


def verdict(gates_pass, curve_rows) -> str:
    if not _GATES.exists() and not curve_rows:
        return "RUN NOT FINISHED — no eval + no GRPO metrics yet. Re-run when the campaign self-kills."
    fb = next((r["frac_bad"] for r in reversed(curve_rows) if isinstance(r.get("frac_bad"), (int, float))), None)
    if fb is not None and fb > 0.5:
        return (f"BROKEN GENERATION — last frac_bad={fb:.2f} (>0.5). The DSL isn't being emitted; do NOT measure/ship. "
                "Inspect a sample completion (the prompt/grammar path) before the next run.")
    if gates_pass is True:
        return ("GATES PASS — GRPO beat its SFT init with legal DSL. NEXT: measure vs Slumbot (headline bb/100 vs -72, "
                "needs a GPU for the 8B) + wire the adapter into the live 6-max bot; then scale (32B / more GRPO).")
    if gates_pass is False:
        return ("GATES did NOT all pass — read eval_gates.json above (likely G2 delta-vs-SFT ~0 on a short run). The "
                "pipeline is proven; decide: longer GRPO, more/again data, or 32B. frac_bad low = the model is healthy.")
    return ("PARTIAL — adapter + metrics present but no PASS verdict. Read the gates above; if frac_bad low + reward_std>0 "
            "the run is healthy → measure vs Slumbot next.")


def main() -> None:
    print("=" * 78)
    print("PROCESS RUN — verdict for the last RL pod run")
    print("=" * 78)
    print("\n[1] ADAPTER")
    print("  " + unpack_adapter())
    print("\n[2] GATE LADDER (data/eval_gates.json)")
    glines, gates_pass = gate_summary()
    print("\n".join(glines))
    print("\n[3] GRPO LEARNING CURVE (data/training_metrics.jsonl)")
    print("\n".join(curve_summary()))
    print("\n[4] FULL-LOAD PROOF (data/gpu_load.jsonl)")
    print("\n".join(gpu_summary()))
    print("\n[VERDICT]")
    print("  " + verdict(gates_pass, _fresh_metrics()))
    print("=" * 78)


if __name__ == "__main__":
    main()
