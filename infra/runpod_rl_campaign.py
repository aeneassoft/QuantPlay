"""Self-killing RL pod run — the real GATE 2 (smoke->scale). Provisions ONE H100/H200, sets up the RL stack, runs
DSL-SFT (GATE 0) -> DAPO-GRPO -> the GTO-anchored held-out eval (GATE ladder), pulls the best adapter + logs, and
ALWAYS terminates the pod (atexit + finally) — the user's #1 cost rule. Mirrors infra/cfv_pod_campaign.py.

Run:   python -m infra.runpod_rl_campaign            # smoke: short SFT + ~50 GRPO steps + eval (~$15-30)
       python -m infra.runpod_rl_campaign --scale    # the full run (only after a green smoke delta vs SFT-init)
Verify afterwards: python -m infra.runpod_run --status   (must show NO tracked pods)

PREREQ ($0, run first): the full DSL dataset must exist locally -> it ships in the tarball:
   python -m dataset.build.run --full --pb -1     # -> dataset/shards/local_kb.jsonl
"""
from __future__ import annotations

import atexit
import json
import os
import re
import sys
import threading
import time

from infra import runpod_run as R
from pipeline import orchestrate as O
from infra.cfv_pod_campaign import _scp_down, _ssh, ssh_endpoint
from pokerbot import config

REMOTE = "/root/pokerb"
ENV = f"cd {REMOTE} && PYTHONPATH={REMOTE} HF_HUB_ENABLE_HF_TRANSFER=1 "
METRICS_LOCAL = str(config.ROOT / "data" / "training_metrics.jsonl")   # the dashboard reads this
GPULOAD_LOCAL = str(config.ROOT / "data" / "gpu_load.jsonl")           # nvidia-smi util/mem samples (full-load proof)

# SCALE = the full-mega-GPU-load run (vs the default 40-60min smoke). The user's directive: fully load BOTH the compute
# AND the vRAM, with SIZE-AGNOSTIC training (BASE = 8B preferred, 32B/70B to fill a bigger card). The three full-load
# levers (docs/full_gpu_load.md): (1) REWARD_WORKERS parallelizes the CPU reward so the GPU isn't starved [the real
# bottleneck], (2) VLLM_MEM high fills vRAM with vLLM KV cache (more concurrent gen), (3) BASE↑ + bigger G/batch fill
# compute. All env-driven so one file serves smoke + scale.
# MODE = "train" (the SFT->GRPO deployment-model run) OR "teacher" (a frontier-scale Qwen GENERATES gated DSL data on the
# B300 to DISTIL into the 8B — the user's "deep research with the biggest model" plan; the 235B is a TEACHER, not deployed).
MODE = os.environ.get("MODE", "train")
SCALE = os.environ.get("SCALE", "0") == "1"
BASE = os.environ.get("BASE", "Qwen/Qwen3-8B")                   # size-agnostic (QLoRA nf4 + all-linear); 8B/32B/70B
TEACHER_BASE = os.environ.get("TEACHER_BASE", "Qwen/Qwen3-235B-A22B-Instruct-2507-FP8")   # fp8 235B fits ONE B300 (288GB)
TEACHER_FALLBACK = os.environ.get("TEACHER_FALLBACK", "Qwen/Qwen3-32B")   # if the 235B won't load -> still produce data
GPU = os.environ.get("GPU", "")                                  # force ONE gpuTypeId (e.g. "NVIDIA H200"); "" = the FAST chain
POD_ID = os.environ.get("POD_ID", "")                           # use an EXISTING (e.g. manually-launched B300) pod; do NOT kill it
PAUSE = os.environ.get("PAUSE", "0") == "1"                     # at the end STOP (pause) the auto-provisioned pod, don't terminate
#                                                                 -> the container disk (235GB model cache) persists -> resume skips re-download
GPU_COUNT = int(os.environ.get("GPU_COUNT", "1"))               # multi-GPU pod (e.g. 2 -> 2x H200 = 282GB, fits 235B fp8)
TP = int(os.environ.get("TP", str(GPU_COUNT)))                  # vLLM tensor-parallel size (= GPU_COUNT for a big model)
_BIG = SCALE or MODE == "teacher"                               # teacher always loads a HUGE model (235B fp8 ~235GB)
DISK = int(os.environ.get("DISK", "400" if _BIG else "200"))   # container disk GB — 32B/70B/235B downloads + ckpts need room
HARD_CAP_S = int(os.environ.get("HARD_CAP_S", "21600" if SCALE else ("6000" if MODE == "teacher" else "3600")))  # teacher ~100min
VLLM_MEM = os.environ.get("VLLM_MEM", "0.90" if MODE == "teacher" else ("0.85" if SCALE else "0.45"))  # fill the B300 vRAM


def _nproc(ip, port) -> int:
    """Pod CPU count -> REWARD_WORKERS (the reward is CPU-bound; ~all cores minus a couple for the trainer/sshd)."""
    r = _ssh(ip, port, "nproc", timeout=30)
    try:
        return max(1, int((r.stdout or "0").strip().splitlines()[-1]))
    except Exception:  # noqa: BLE001
        return 8


def _train_env(reward_workers: int, vllm_mem: str = VLLM_MEM) -> str:
    """The common env prefix for every training step: deterministic hashing (CRN across reward workers), the parallel
    reward fan-out, the size-agnostic BASE, and the vRAM-fill vLLM utilization."""
    return (f"PYTHONHASHSEED=0 REWARD_WORKERS={reward_workers} BASE={BASE} VLLM_MEM={vllm_mem} ")


def _grep(r, marker: str) -> bool:
    return marker in ((r.stdout or "") + (r.stderr or ""))


def _parse_float(text: str, key: str, default: float) -> float:
    m = re.search(re.escape(key) + r"([0-9.]+)", text or "")
    return float(m.group(1)) if m else default


def _stream_metrics(ip, port, stop: threading.Event):
    """Daemon: scp the pod's growing GRPO metrics JSONL -> data/training_metrics.jsonl every ~15s (the dashboard feed)."""
    os.makedirs(os.path.dirname(METRICS_LOCAL), exist_ok=True)
    while not stop.is_set():
        try:
            _scp_down(ip, port, "/root/grpo_metrics.jsonl", METRICS_LOCAL)
        except Exception:  # noqa: BLE001 — file may not exist yet; retry
            pass
        stop.wait(15)


def _sample_gpu_load(ip, port, stop: threading.Event):
    """Daemon: poll nvidia-smi every ~10s -> data/gpu_load.jsonl = the EMPIRICAL full-load proof (util% + vRAM used/total).
    The whole point of parallelizing the reward is that these stay HIGH during GRPO instead of sawtoothing to 0 while the
    CPU computes rewards."""
    os.makedirs(os.path.dirname(GPULOAD_LOCAL), exist_ok=True)
    q = ("nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total "
         "--format=csv,noheader,nounits")
    while not stop.is_set():
        try:
            r = _ssh(ip, port, q, timeout=20)
            for ln in (r.stdout or "").strip().splitlines():
                parts = [p.strip() for p in ln.split(",")]
                if len(parts) == 3 and parts[0].isdigit():
                    util, used, total = int(parts[0]), int(parts[1]), int(parts[2])
                    with open(GPULOAD_LOCAL, "a", encoding="utf-8") as f:
                        f.write(json.dumps({"t": time.time(), "util": util, "mem_used": used,
                                            "mem_total": total, "mem_frac": round(used / max(1, total), 3)}) + "\n")
        except Exception:  # noqa: BLE001
            pass
        stop.wait(10)


def launch_gpu(disk: int = None):
    """Provision ONE GPU pod, SECURE then COMMUNITY. GPU env forces a single gpuTypeId (e.g. the B300); else the R.FAST
    chain. Returns (pid, gpu) or (None, None)."""
    disk = DISK if disk is None else disk
    pub = open(R.PUBKEY_FILE, encoding="utf-8").read().strip()
    gpu_list = [GPU] if GPU else R.FAST
    for cloud in ("SECURE", "COMMUNITY"):
        for gpu in gpu_list:
            body = {"name": "pokerb-rl", "imageName": R.IMAGE, "cloudType": cloud, "computeType": "GPU",
                    "gpuTypeIds": [gpu], "gpuCount": GPU_COUNT, "containerDiskInGb": disk, "volumeInGb": 0,
                    "ports": ["22/tcp"], "env": {"PUBLIC_KEY": pub}}
            code, resp = R._req("POST", "/pods", body)
            if code in (200, 201):
                pid = resp.get("id")
                R._track(pid)
                print(f"  launched RL pod {pid} on {GPU_COUNT}x {gpu} [{cloud}] (${resp.get('costPerHr')}/hr, disk {disk}GB)",
                      flush=True)
                return pid, gpu
            print(f"  {cloud:9} {gpu:22}: {code} {json.dumps(resp)[:140]}", flush=True)
    return None, None


def setup_rl_pod(ip, port, blackwell: bool = False) -> bool:
    """Upload the code+data bundle, install the RL stack. Returns True iff RL_SETUP_OK. `blackwell` (B200/B300/GB200) ->
    force torch +cu128 so sm_100/103 gets real kernels (else the math-fallback path is ~10x slower / can break)."""
    tgz = O.build_tarball()                                          # pokerbot+dataset+training+infra+knowledge_base subset
    print(f"  bundle {os.path.getsize(tgz) / 1e6:.1f} MB -> pod", flush=True)
    up = O.push(ip, port, tgz)                                       # scp + unpack to /root/pokerb
    if up.returncode != 0:
        print(f"  upload FAILED: {(up.stderr or '')[:200]}", flush=True)
        return False
    env = ("B200=1 " if blackwell else "") + ("TEACHER=1 " if MODE == "teacher" else "")   # lean teacher stack / Blackwell switch
    r = _ssh(ip, port, f"{env}bash {REMOTE}/infra/pod_setup_rl.sh", timeout=1500)
    ok = "RL_SETUP_OK" in (r.stdout or "")
    out = ((r.stdout or "") + "\n" + (r.stderr or "")).strip()
    print(f"  RL setup {'OK' if ok else 'FAILED'} (TEACHER={MODE=='teacher'}):", flush=True)
    print("   " + "\n   ".join(out.splitlines()[-45:]), flush=True)   # show the tail incl. the ERR-trap's pip-log dump
    return ok


def run_step(ip, port, name: str, cmd: str, timeout: int):
    """ssh a training/eval step (blocking). Print the STDOUT tail (our markers) + any ERROR lines separately, so a real
    failure is never buried under stderr warnings (the C1 diagnosis gap). Returns the CompletedProcess."""
    print(f"  >>> {name} ...", flush=True)
    r = _ssh(ip, port, ENV + cmd, timeout=timeout)
    out, err = (r.stdout or ""), (r.stderr or "")
    tail = out.strip().splitlines()[-6:]
    print(f"  <<< {name}: " + " | ".join(tail)[:500], flush=True)
    errs = [ln.strip() for ln in (out + "\n" + err).splitlines()
            if re.search(r"Traceback|TypeError|ValueError|KeyError|Error|FAIL|assert|Exception|No module|CUDA|OOM",
                         ln, re.IGNORECASE)]
    if errs:
        print(f"  !! {name} error lines: " + " | ".join(errs[-8:])[:900], flush=True)
    return r


def run_teacher(ip, port, budget_left, reward_workers: int) -> bool:
    """TEACHER mode: a frontier-scale Qwen GENERATES engine-gated DSL data on the B300 (-> distil into the 8B on the PC).
    Tries the 235B (fp8, fills the 288GB B300); if it won't load, falls back to a 32B so the run STILL produces data
    (the user's dual goal: biggest model AND runs-through). Pulls teacher_raw.jsonl. Returns True iff data was produced."""
    gen_n = os.environ.get("TEACHER_N", "200000")            # a high cap; the wall-clock is the real stop
    out_remote = "/root/teacher_raw.jsonl"
    dst = str(config.ROOT / "data" / "teacher_raw.jsonl")

    # periodic pull: teacher_generate appends chunks incrementally -> scp every ~5min so data/teacher_raw.jsonl is always
    # fresh (the user's "pull + analyze at the halfway mark" while the run keeps generating).
    _pstop = threading.Event()

    def _periodic_pull():
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        while not _pstop.is_set():
            _pstop.wait(300)
            try:
                _scp_down(ip, port, out_remote, dst)
            except Exception:  # noqa: BLE001 — file may not exist yet
                pass
    threading.Thread(target=_periodic_pull, daemon=True).start()

    def _gen(model: str, secs: float) -> bool:
        wall = int(max(300, secs - 240))                     # reserve ~4min for the pull+kill
        cmd = (f"PYTHONHASHSEED=0 BASE={model} N={gen_n} CHUNK=1500 VLLM_MEM={VLLM_MEM} TP={TP} "
               f"WALLCLOCK_S={wall} OUT={out_remote} python3 -u -m research.teacher_generate")
        r = run_step(ip, port, f"TEACHER-GEN[{model.split('/')[-1]}]", cmd, timeout=int(secs + 120))
        txt = (r.stdout or "") + (r.stderr or "")
        if "TEACHER_GEN_OK" in txt:
            return True
        if "TEACHER_MODEL_LOADED" not in txt:                # never even loaded -> a model/vram/Blackwell problem
            print(f"  {model} did not load -> fallback", flush=True)
        return False

    ok = _gen(TEACHER_BASE, budget_left())
    if not ok and TEACHER_FALLBACK != TEACHER_BASE and budget_left() > 600:   # primary failed -> smaller fallback (always fits)
        print(f"  TEACHER {TEACHER_BASE} failed -> fallback {TEACHER_FALLBACK}", flush=True)
        ok = _gen(TEACHER_FALLBACK, budget_left())
    d = _scp_down(ip, port, out_remote, dst)                 # pull whatever was generated (incremental = partial-safe)
    got = d.returncode == 0
    print(f"  pulled teacher data -> {dst}" if got else f"  teacher pull FAILED: {(d.stderr or '')[:160]}", flush=True)
    return ok and got


def main():
    T0 = time.time()

    def budget_left():
        return HARD_CAP_S - (time.time() - T0)

    stop = threading.Event()

    _ended = {"done": False}                                    # guard so atexit doesn't re-stop/-kill after the normal end

    def _killall():
        stop.set()
        if _ended["done"]:
            return
        _ended["done"] = True
        if POD_ID:                                             # the user owns this pod (manually launched) -> NEVER touch it
            print(f"  >>> done. LEAVING your pod {POD_ID} running — manage it yourself (console / --kill) <<<", flush=True)
            return
        if PAUSE:                                              # PAUSE: stop (keep the disk + model cache), don't terminate
            for pid in R._tracked_ids():
                try:
                    code, _ = R.stop(pid)
                    print(f"  >>> PAUSED pod {pid} (stop {code}) — model cached on disk; resume to skip re-download. "
                          f"Storage still bills; `python -m infra.runpod_run --kill` to fully terminate. <<<", flush=True)
                except Exception as e:  # noqa: BLE001
                    print(f"  pause error for {pid} ({e}) — `python -m infra.runpod_run --kill` MANUALLY if needed", flush=True)
            return
        print("  >>> finally/atexit: terminating the RL pod <<<", flush=True)
        try:
            R.kill()
        except Exception as e:  # noqa: BLE001
            print(f"  kill error (run `python -m infra.runpod_run --kill` MANUALLY): {e}", flush=True)
    atexit.register(_killall)

    print("RL CAMPAIGN (first run, ~40-60min, self-killing). "
          "Watch live: python -m pokerbot.web.train_dashboard --open", flush=True)
    try:
        if POD_ID:                                             # use the user's EXISTING pod (e.g. a manually-launched B300)
            pid, gpu = POD_ID, GPU
            print(f"  using EXISTING pod {pid} (GPU={GPU or 'unknown'}, blackwell={R.is_blackwell(gpu)}) — will NOT kill it",
                  flush=True)
        else:
            pid, gpu = launch_gpu()
        if not pid:
            print("no GPU pod launched; aborting (no cost).", flush=True)
            return
        ip, port = ssh_endpoint(pid)
        if not (ip and port):
            print("pod never exposed SSH; aborting.", flush=True)
            return
        if not setup_rl_pod(ip, port, blackwell=R.is_blackwell(gpu)):
            return

        ncpu = _nproc(ip, port)
        reward_workers = max(1, ncpu - 2)                          # leave ~2 cores for the trainer/vLLM/sshd
        tenv = _train_env(reward_workers)
        print(f"  pod has {ncpu} CPUs -> REWARD_WORKERS={reward_workers} | BASE={BASE} VLLM_MEM={VLLM_MEM} "
              f"SCALE={SCALE} HARD_CAP={HARD_CAP_S}s", flush=True)
        threading.Thread(target=_sample_gpu_load, args=(ip, port, stop), daemon=True).start()   # full-load proof

        if MODE == "teacher":                                  # the deep-research run: a big Qwen generates gated DSL -> distil into 8B.
            run_teacher(ip, port, budget_left, reward_workers) # the LEAN setup's verify (vllm import + bf16 matmul) IS the teacher
            return                                             # preflight (training.preflight needs trl/bnb, not installed in lean). finally: _killall

        # C1 preflight (TRAIN mode, pre-SFT, fail-fast: imports/CUDA/GRPOConfig-constructs/1-state-reward)
        if not _grep(run_step(ip, port, "PREFLIGHT-C1", "python3 -u -m training.preflight", timeout=300),
                     "PREFLIGHT1_OK"):
            print("  PREFLIGHT C1 FAILED -> abort (kill).", flush=True)
            return

        # D DSL-SFT on the CORRECTED GOLD (size-agnostic BASE; scale -> more data + bigger batch to saturate a mega GPU).
        # CRITICAL: train on the reasoning-loop + read + SOLVER-mix shards (the frac_bad-fixed gold), NOT the old
        # local_kb.jsonl (11.5k comment-only exploit/math rows = the original frac_bad 0.97 cause). PokerBench (the spine)
        # is auto-loaded by qwen_sft and capped by MAXN. solver.jsonl = the local TexasSolver mixes (ships in the tarball;
        # the pod has no solver binary — CPU mass-solve is the PC-hub job per the 2-node split).
        sft_maxn = os.environ.get("SFT_MAXN", "60000" if SCALE else "1500")
        sft_batch = os.environ.get("SFT_BATCH", "32" if SCALE else "16")
        sft_to = (int(budget_left() - 2400) if SCALE else min(900, int(budget_left() - 1200)))
        gold_shards = ["a_contract.jsonl", "c_decide.jsonl", "solver.jsonl"]
        if (config.ROOT / "dataset" / "shards" / "teacher.jsonl").exists():    # the distilled B300-235B teacher gold,
            gold_shards.append("teacher.jsonl")                                # if a MODE=teacher run + distill produced it
        gold = ",".join(f"/root/pokerb/dataset/shards/{s}" for s in gold_shards)
        if not _grep(run_step(ip, port, "DSL-SFT",
                              f"{tenv}QUANT4=1 MAXN={sft_maxn} BATCH={sft_batch} "
                              f"DSL={gold} OUT=/root/qwen_poker_lora python3 -u -m training.qwen_sft",
                              timeout=max(600, sft_to)), "SAVED LoRA"):
            print("  SFT FAILED -> abort.", flush=True)
            return

        # C2 probe: 2-step micro-GRPO on the real adapter -> STEP_TIME_S. Uses the REAL tenv (BASE + the scale VLLM_MEM +
        # the parallel reward) so it canaries colocate-OOM AND reward-throughput at the settings the E run will use.
        rp = run_step(ip, port, "PROBE-C2",
                      f"{tenv}ADAPTER=/root/qwen_poker_lora OUT=/root/_probe N_STATES=12 NUM_GEN=4 GEN_BATCH=8 K_ROLL=4 "
                      "MAX_STEPS=2 STRUCTURED=1 METRICS_PATH=/root/_probe.jsonl "
                      "python3 -u -m training.qwen_grpo", timeout=360)
        ptxt = (rp.stdout or "") + (rp.stderr or "")
        probe_ok = _grep(rp, "SAVED GRPO adapter") and "STEP_TIME_S=" in ptxt
        step_time = _parse_float(ptxt, "STEP_TIME_S=", 25.0)

        # decide STRUCTURED + MAX_STEPS + WALLCLOCK for E from the probe + remaining budget
        e_budget = max(120, budget_left() - 600)              # reserve 600s for eval + pull
        feasible = int(e_budget / max(step_time, 1.0))
        structured = "1" if feasible >= 15 else "0"           # structured-probe too slow -> free decoding (more steps)
        max_steps = max(8, min(400, feasible if structured == "1" else feasible * 2))
        wallclock = int(e_budget - 90)
        print(f"  probe ok={probe_ok} step_time={step_time:.1f}s e_budget={e_budget:.0f}s -> "
              f"STRUCTURED={structured} MAX_STEPS={max_steps} WALLCLOCK_S={wallclock}", flush=True)

        # E GRPO (stream metrics to the dashboard during the blocking run). Scale -> big G/batch fill vLLM + the now-parallel
        # reward affords K_ROLL=16 (sharper EV) without starving the GPU; MAX_STEPS uncapped, WallClockStop is the guard.
        g_n = os.environ.get("N_STATES", "2000" if SCALE else "120")
        g_k = os.environ.get("K_ROLL", "16" if SCALE else "6")
        g_gb = os.environ.get("GEN_BATCH", "256" if SCALE else "32")
        g_pd = os.environ.get("PD_BATCH", "16" if SCALE else "8")
        g_steps = "-1" if SCALE else str(max_steps)               # scale: run to the wall-clock budget, not a step cap
        grpo_ok = False
        if probe_ok and wallclock > 60:
            threading.Thread(target=_stream_metrics, args=(ip, port, stop), daemon=True).start()
            re_ = run_step(ip, port, "DAPO-GRPO",
                           f"{tenv}ADAPTER=/root/qwen_poker_lora OUT=/root/qwen_poker_grpo N_STATES={g_n} K_ROLL={g_k} "
                           f"NUM_GEN=8 GEN_BATCH={g_gb} PD_BATCH={g_pd} MAX_COMP=320 STRUCTURED={structured} "
                           f"MAX_STEPS={g_steps} WALLCLOCK_S={wallclock} METRICS_PATH=/root/grpo_metrics.jsonl "
                           "python3 -u -m training.qwen_grpo",
                           timeout=int(e_budget + 180))
            stop.set()
            _scp_down(ip, port, "/root/grpo_metrics.jsonl", METRICS_LOCAL)    # final metrics pull
            grpo_ok = _grep(re_, "SAVED GRPO adapter")
        else:
            print("  probe failed / insufficient budget -> SKIP GRPO, eval the SFT adapter alone.", flush=True)

        # F eval (GRPO if trained, else the SFT-alone fallback) -> the GATE-ladder JSON. tenv = same BASE (size-agnostic)
        # + PYTHONHASHSEED=0 (reproducible bb/100).
        grpo_path = "/root/qwen_poker_grpo" if grpo_ok else "/root/qwen_poker_lora"
        eval_hands = os.environ.get("EVAL_HANDS", "1000" if SCALE else "300")
        run_step(ip, port, "GTO-EVAL",
                 f"{tenv}SFT=/root/qwen_poker_lora GRPO={grpo_path} EVAL_HANDS={eval_hands} "
                 "GATES_OUT=/root/eval_gates.json python3 -u -m training.qwen_eval_gto",
                 timeout=min(900, max(120, int(budget_left() - 150))))
        _scp_down(ip, port, "/root/eval_gates.json", str(config.ROOT / "data" / "eval_gates.json"))   # -> dashboard
        # (data/gpu_load.jsonl is written live by the _sample_gpu_load daemon — the empirical full-load record)

        # G pull adapter + metrics
        _ssh(ip, port, "tar czf /root/out.tgz -C /root qwen_poker_grpo grpo_metrics.jsonl 2>/dev/null; "
                       "[ -f /root/out.tgz ] || tar czf /root/out.tgz -C /root qwen_poker_lora", timeout=120)
        dst = str(config.ROOT / "models" / "qwen_poker_grpo.tgz")
        d = _scp_down(ip, port, "/root/out.tgz", dst)
        print(f"  pulled -> {dst}" if d.returncode == 0 else f"  pull FAILED: {(d.stderr or '')[:160]}", flush=True)
    finally:
        _killall()


if __name__ == "__main__":
    main()
