"""PC-side driver for the RunPod SERVERLESS teacher worker (infra/serverless_handler.py). Fires generation jobs at the
endpoint, accumulates the engine-GATED examples it returns, and appends them to data/teacher_raw.jsonl (then
`python -m pipeline.distill_teacher` applies the EV-truth gate -> dataset/shards/teacher.jsonl for the 8B SFT).

No SSH / scp / pod setup — just HTTPS to the managed endpoint (the env hell that broke 5 pod runs is RunPod's problem
now). The worker generates + light-gates (grammar+executes); the PC accumulates + EV-gates (CLAUDE.md: engine is truth,
frontier feeds the PC's dataset).

Run: ENDPOINT_ID=<your endpoint> TARGET=20000 N_PER_JOB=500 python -m research.teacher_serverless_client
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

from infra.runpod_run import _key
from pokerbot import config

ENDPOINT_ID = os.environ.get("ENDPOINT_ID", "")
TARGET = int(os.environ.get("TARGET", "20000"))        # total GATED examples to collect
N_PER_JOB = int(os.environ.get("N_PER_JOB", "500"))    # spots generated per job
TEMP = float(os.environ.get("GEN_TEMP", "0.7"))
MAXTOK = int(os.environ.get("MAXTOK", "320"))
WALLCLOCK_S = float(os.environ.get("WALLCLOCK_S", "9000"))   # 2.5h budget
OUT = os.environ.get("OUT", str(config.ROOT / "data" / "teacher_raw.jsonl"))
BASE = f"https://api.runpod.ai/v2/{ENDPOINT_ID}"


def _post(path: str, body: dict, timeout: int = 60) -> dict:
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": "Bearer " + _key(), "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode() or "{}")


def _get(path: str, timeout: int = 60) -> dict:
    req = urllib.request.Request(BASE + path, headers={"Authorization": "Bearer " + _key()})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode() or "{}")


def run_job(seed: int, cold: bool) -> list:
    """Fire one async job, poll until COMPLETED, return its gated examples. Patient on the first (cold-start) job."""
    job = _post("/run", {"input": {"n": N_PER_JOB, "seed": seed, "temperature": TEMP, "max_tokens": MAXTOK}})
    jid = job.get("id")
    if not jid:
        print(f"  job submit failed: {json.dumps(job)[:200]}", flush=True)
        return []
    deadline = time.time() + (1500 if cold else 600)   # cold start = model download+load (~10-20min); warm = fast
    while time.time() < deadline:
        st = _get(f"/status/{jid}")
        status = st.get("status")
        if status == "COMPLETED":
            out = st.get("output") or {}
            print(f"  job {jid[:8]} seed={seed}: kept {out.get('kept')}/{out.get('total')} "
                  f"(gate_pass {out.get('gate_pass')}) model={out.get('model')}", flush=True)
            return out.get("examples") or []
        if status in ("FAILED", "CANCELLED", "TIMED_OUT"):
            print(f"  job {jid[:8]} {status}: {json.dumps(st)[:200]}", flush=True)
            return []
        time.sleep(5)
    print(f"  job {jid[:8]} poll timeout (status={status})", flush=True)
    return []


def main():
    if not ENDPOINT_ID:
        print("set ENDPOINT_ID to your RunPod serverless endpoint id"); return
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w", encoding="utf-8").close()                # truncate
    t0 = time.time()
    kept = seed = 0
    print(f"TEACHER-SERVERLESS endpoint={ENDPOINT_ID} target={TARGET} | first job = cold start (model download)...", flush=True)
    while kept < TARGET and (time.time() - t0) < WALLCLOCK_S:
        rows = run_job(seed, cold=(seed == 0))
        with open(OUT, "a", encoding="utf-8") as f:
            for ex in rows:
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")
        kept += len(rows)
        seed += 1
        print(f"  >> total kept {kept}/{TARGET} | {time.time()-t0:.0f}s elapsed", flush=True)
    print(f"DONE: {kept} gated teacher rows -> {OUT} | next: python -m pipeline.distill_teacher", flush=True)


if __name__ == "__main__":
    main()
