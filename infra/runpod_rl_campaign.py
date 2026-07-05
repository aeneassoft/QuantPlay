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
import base64
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
from dataset import registry  # the ONE source of the SFT gold-shard list (data discovered by ROLE, not hardcoded path)

# cp1252 Windows consoles can't encode the unicode in captured pod stdout (tqdm bars █▏▎, arrows →) -> a print() of a
# pod log raised UnicodeEncodeError and ABORTED a HEALTHY, fully-trained SFT (2026-06-20, twice: the adapter was saved
# on the pod, then the print crash killed the pod before the pull). Make ALL our stdout encode-safe so a glyph can NEVER
# kill a run again (belt-and-suspenders with a PYTHONUTF8=1 launch).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001 — older Python / a non-reconfigurable stream
        pass

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
VLLM_MEM = os.environ.get("VLLM_MEM", "0.90" if MODE == "teacher" else ("0.6" if SCALE else "0.45"))  # colocate train+vLLM:
#   0.6 leaves vRAM for the trainer — 0.85 OOM'd the H200 probe (vLLM took 119/140GB, +training → OOM, 2026-06-18 4th run).

# run_step's error-line filter: match REAL failure signatures only — a bare "Error"/"CUDA"/"FAIL" also matches SUCCESS
# lines like "...cuda 12.8 | bf16 OK | ... constructs OK" (the false-positive we hit) -> exclude any line carrying an
# `*_OK` success marker. Honest output: an "error line" should be an actual error.
_ERR_RE = re.compile(r"Traceback|No module|ModuleNotFound|TypeError|ValueError|KeyError|RuntimeError|AttributeError|"
                     r"ImportError|AssertionError|Exception:|CUDA error|out of memory|OOM|FAILED|PREFLIGHT1_FAIL",
                     re.IGNORECASE)
_OK_RE = re.compile(r"_OK\b|OK \||matmul OK|constructs OK|ev_reward OK")

# EARLY GRPO AUTO-ABORT (the flawless-unattended safeguard): if the mean frac_bad over the first ABORT_MIN_STEPS logged
# GRPO steps exceeds ABORT_FRAC_BAD, generation is broken (the 2026-06-17 frac_bad=1.0 bug) -> terminate the pod so a
# doomed multi-hour run dies for ~$3 instead of burning the whole budget — WITHOUT needing a manual pause.
# 0.75 (was 0.5): SAMPLED frac_bad ~0.5 is NORMAL exploration (the model is greedy-valid; the first run's first-5 mean
# was 0.438 — a near-miss false-abort), and with R_BAD=-3 it no longer swamps the EV reward -> only a genuine generation
# break (~0.75+) should abort.
ABORT_FRAC_BAD = float(os.environ.get("ABORT_FRAC_BAD", "0.75"))
ABORT_MIN_STEPS = int(os.environ.get("ABORT_MIN_STEPS", "5"))
R_BAD = os.environ.get("R_BAD", "-3")              # passed to the GRPO+probe reward; -3 = the flat-reward fix (see qwen_grpo.py:29)


def _nproc(ip, port) -> int:
    """Pod CPU count -> REWARD_WORKERS (the reward is CPU-bound; ~all cores minus a couple for the trainer/sshd)."""
    r = _ssh(ip, port, "nproc", timeout=30)
    try:
        return max(1, int((r.stdout or "0").strip().splitlines()[-1]))
    except Exception:  # noqa: BLE001
        return 8


def _train_env(reward_workers: int, vllm_mem: str = VLLM_MEM) -> str:
    """The common env prefix for every training step: deterministic hashing (CRN across reward workers), the parallel
    reward fan-out, the size-agnostic BASE, the vRAM-fill vLLM utilization, and the precision (nf4 vs bf16).
    GLM-Z1 (reasoning model on the 96GB RTX PRO 6000): bf16 LoRA (QLORA/QUANT4=0; no bnb-on-Blackwell-sm_120 risk) +
    BOUNDED thinking (THINK_CAP_CHARS) + reasoning-model sampling (TEMP=0.8). Qwen/pod default = nf4 (QLORA/QUANT4=1)."""
    glm = "glm" in BASE.lower()
    env = (f"PYTHONHASHSEED=0 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True REWARD_WORKERS={reward_workers} "
           f"BASE={BASE} VLLM_MEM={vllm_mem} R_BAD={R_BAD} "
           f"QUANT4={os.environ.get('QUANT4', '0' if glm else '1')} "          # qwen_sft precision (0=bf16, 1=nf4)
           f"QLORA={os.environ.get('QLORA', '0' if glm else '1')} ")          # qwen_grpo precision (0=bf16, 1=nf4)
    if glm:
        env += (f"ATTN={os.environ.get('ATTN', 'sdpa')} "          # sdpa = torch's built-in flash kernel (NO flash-attn pkg
                #                                                    needed; fast on Hopper, works on Blackwell). flash_attention_2
                #                                                    would need the pkg installed (the smoke's SFT-crash cause).
                # NB: read the sampling temp from GEN_TEMP, NOT TEMP — Windows ALWAYS sets TEMP (= the temp-dir path), so
                # os.environ.get('TEMP','0.8') returned 'C:\\Users\\...\\Temp' -> passed to the pod -> float() crash in the probe.
                f"THINK_CAP_CHARS={os.environ.get('THINK_CAP_CHARS', '1500')} TEMP={os.environ.get('GEN_TEMP', '0.8')} "
                # 9B activations OOM at batch 16 on the 96GB card WITHOUT checkpointing (~73GB of activations). Gradient
                # checkpointing (recompute in backward) cuts that ~10x -> ~28GB total. Default ON for GLM.
                f"GRAD_CKPT={os.environ.get('GRAD_CKPT', '1')} "
                # MAX_LEN must exceed the full example: SYSTEM_PROMPT alone is ~1142 tokens and every gold row is
                # 1300-1570 tokens, so the 1024 default RIGHT-truncated EVERY example mid-system-prompt -> the completion
                # was cut off -> zero trainable tokens -> SFT loss 0 (the round-4 bug). 2048 fits all (max measured 1570).
                f"MAX_LEN={os.environ.get('MAX_LEN', '2048')} ")
    return env


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


def _stream_checkpoints(ip, port, stop: threading.Event):
    """Daemon: continuously pull the LATEST GRPO checkpoint to local so an abort / crash / SSH-timeout NEVER loses the
    model (the fragility that killed 2 runs — the campaign pulled the adapter ONLY at the very end). Every CKPT_PULL_S, if
    a NEW `checkpoint-*` exists on the pod, tar it + scp -> models/qwen_poker_grpo_live.tgz. So we can kill the pod ANY
    time and the newest checkpoint is already on disk locally (lose at most CKPT_PULL_S of training)."""
    dst = str(config.ROOT / "models" / "qwen_poker_grpo_live.tgz")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    period = int(os.environ.get("CKPT_PULL_S", "120"))
    last = ""
    while not stop.is_set():
        stop.wait(period)
        try:
            r = _ssh(ip, port, "cd /root/qwen_poker_grpo 2>/dev/null && ls -dt checkpoint-* 2>/dev/null | head -1", timeout=30)
            ck = ((r.stdout or "").strip().splitlines() or [""])[-1].strip()
            if not ck or ck == last:
                continue                                          # no new checkpoint since the last pull
            t = _ssh(ip, port, f"cd /root/qwen_poker_grpo && tar czf /root/_live_ckpt.tgz {ck} 2>/dev/null && echo TARRED",
                     timeout=180)
            if "TARRED" in (t.stdout or "") and _scp_down(ip, port, "/root/_live_ckpt.tgz", dst).returncode == 0:
                last = ck
                print(f"  [ckpt-sync] {ck} -> models/qwen_poker_grpo_live.tgz (abort-safe)", flush=True)
        except Exception:  # noqa: BLE001 — pod busy / nothing checkpointed yet; retry next cycle
            pass


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


def _grpo_abort_watch(stop: threading.Event, aborted: dict):
    """Flawless-unattended safeguard: once >= ABORT_MIN_STEPS GRPO steps are logged to METRICS_LOCAL (the stream the
    _stream_metrics daemon pulls), if their mean frac_bad exceeds ABORT_FRAC_BAD the generation is broken -> set
    `aborted` + TERMINATE the pod (drops the SSH so the blocking GRPO step returns), so a doomed run dies cheap. No pause."""
    while not stop.is_set():
        stop.wait(20)
        rows = []
        try:
            for ln in open(METRICS_LOCAL, encoding="utf-8"):
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    rows.append(json.loads(ln))
                except Exception:  # noqa: BLE001 — tolerate a half-written last line mid-scp
                    pass
        except Exception:  # noqa: BLE001 — metrics file not present yet
            continue
        fb = [r["frac_bad"] for r in rows if isinstance(r.get("frac_bad"), (int, float))]
        if len(fb) >= ABORT_MIN_STEPS:
            mean_fb = sum(fb[:ABORT_MIN_STEPS]) / ABORT_MIN_STEPS
            if mean_fb > ABORT_FRAC_BAD:
                aborted["v"] = True
                stop.set()
                print(f"  !! EARLY-ABORT: mean frac_bad={mean_fb:.2f} over first {ABORT_MIN_STEPS} steps > "
                      f"{ABORT_FRAC_BAD} => generation broken; TERMINATING the pod (cheap fail, no full-budget burn).",
                      flush=True)
                try:
                    R.kill()
                except Exception as e:  # noqa: BLE001
                    print(f"  abort-kill error (run `python -m infra.runpod_run --kill`): {e}", flush=True)
                return


def _arm_watchdog(ip, port, pid, deadline_s: int) -> bool:
    """Pod-side SELF-DESTRUCT — the $65 money-safety (an overnight PC-sleep left two pods idle ~5h; a `nohup` watchdog did
    NOT survive the SSH teardown -> `setsid` does: a detached SESSION LEADER, SID==PID). It DELETEs THIS pod after
    deadline_s regardless of the PC (sleep / power-loss / campaign crash). The PC-side `_killall` stays PRIMARY and fires
    far earlier on a normal finish; this is only the backstop. Best-effort — an arm failure never blocks the run.

    deadline_s = HARD_CAP_S + margin so the watchdog fires only if the normal flow (WallClockStop + _killall) DIDN'T."""
    try:
        key = R._key()
    except Exception as e:  # noqa: BLE001 — no key -> rely on the PC-side _killall
        print(f"  watchdog NOT armed (no API key: {e}); the PC-side _killall remains the safety.", flush=True)
        return False
    wd = (f"sleep {int(deadline_s)}\n"
          f'curl -s -X DELETE {R.BASE}/pods/{pid} -H "Authorization: Bearer $(cat /root/.wd_key)" -o /tmp/wd_del.json\n'
          f'echo "watchdog DELETE fired $(date -u): $(cat /tmp/wd_del.json 2>/dev/null)" >> /tmp/wd.log\n')
    wd_b64 = base64.b64encode(wd.encode()).decode()                 # base64 the script -> no SSH-quoting hazard (the pattern)
    cmd = ("umask 077; "
           f"printf '%s' '{key}' > /root/.wd_key; "
           f"echo '{wd_b64}' | base64 -d > /root/wd.sh; "
           "setsid bash /root/wd.sh </dev/null >>/tmp/wd.log 2>&1 & "      # the '&' backgrounds ONLY the setsid line
           "sleep 1; ps -o pid,sid,cmd | grep '[w]d.sh'; echo WD_ARMED")  # SID==PID in the ps output = truly detached
    r = _ssh(ip, port, cmd, timeout=60)
    out = (r.stdout or "") + (r.stderr or "")
    armed = "WD_ARMED" in out
    tail = " | ".join(out.strip().splitlines()[-3:])[:300]
    print(f"  watchdog {'ARMED (detached, SID==PID)' if armed else 'ARM-FAILED -> _killall is the only safety'}: "
          f"pod self-deletes ~{int(deadline_s) // 60}min after arming if the PC dies. {tail}", flush=True)
    return armed


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
    r = _ssh(ip, port, f"{env}bash {REMOTE}/infra/pod_setup_rl.sh",   # 2026-06-20: a slow-network pod's pip(torch+vllm)
             timeout=int(os.environ.get("SETUP_TO_S", "2700")))      # took >25min -> clean abort; 45min default tolerates it
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
    errs = [ln.strip() for ln in (out + "\n" + err).splitlines() if _ERR_RE.search(ln) and not _OK_RE.search(ln)]
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
        if not POD_ID and not PAUSE:          # arm the pod-side self-destruct backstop ASAP (before setup can hang)
            _arm_watchdog(ip, port, pid, HARD_CAP_S + 1800)
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
        # CRITICAL: train on the reasoning-loop + read + SOLVER-mix shards (the frac_bad-fixed gold) in DSL form via
        # SKIP_PB=1, NOT raw PokerBench. The default qwen_sft path loads ~560k PokerBench rows in their ACTION:-text form
        # (NOT our DSL) then MAXN-caps the COMBINED set -> the 20.7k gold drowns to ~3% AND the model learns a non-DSL
        # output form => frac_bad re-spikes (the exact failure the reasoning-loop fix cured: the validated frac_bad=0.00
        # recipe trained on the GOLD in DSL form, never raw PokerBench). PokerBench's decisions already live in c_decide
        # in proper DSL form. SKIP_PB=1 + MAXN => MAXN now caps the GOLD itself (gold-only, DSL form) — fast smoke, full
        # gold on scale. NOT the old local_kb.jsonl (11.5k comment-only rows = the original frac_bad 0.97 cause).
        # solver*.jsonl = the local TexasSolver mixes (ship in the tarball; the pod has no solver binary — CPU mass-solve
        # is the PC-hub job per the 2-node split).
        sft_maxn = os.environ.get("SFT_MAXN", "60000" if SCALE else "1500")
        # GLM-9B is bigger + a reasoning model -> smaller batch (even if checkpointing fails to engage, batch 8 fits ~46GB).
        _glm = "glm" in BASE.lower()
        sft_batch = os.environ.get("SFT_BATCH", ("16" if SCALE else "8") if _glm else ("32" if SCALE else "16"))
        # SFT hang-guard: cap the SSH timeout so a HUNG SFT (e.g. the tokenizers fork-deadlock) dies in ~1h, not 5h.
        # SFT SSH-timeout = a GENEROUS hang-guard, NOT tied to a big budget-reserve. The old `min(cap, budget_left-2400)`
        # went NEGATIVE for a short HARD_CAP -> clamped to the 600s floor -> the SFT (~11min for MAXN=3000-4000) TIMED OUT
        # and NUKED the run (3x this session). Now: a >=15min floor, capped at SFT_TO_CAP, reserving only 600s. The SFT is
        # bounded by MAXN (finishes early regardless of this cap); GRPO's e_budget is computed AFTER, so it self-adjusts.
        _sft_cap = int(os.environ.get("SFT_TO_CAP", "3600"))
        sft_to = min(_sft_cap, max(900, int(budget_left() - 600)))
        # the frac_bad-fixed GOLD (NOT the old comment-only local_kb.jsonl): reasoning-loop selfplay (a_contract/c_decide)
        # + BOTH solver shards (the 8-board set + the local CPU mass-solve) + the distilled teacher (if a teacher run
        # produced it). .exists()-guard each so an absent/empty shard can never break the SFT mid-pod.
        gold_shards = [p.name for p in registry.sft_gold()]   # the ONE source = dataset/registry.py (.exists()-guarded)
        gold = ",".join(f"{REMOTE}/dataset/shards/{name}" for name in gold_shards)
        print(f"  SFT gold shards (registry.sft_gold): {gold_shards}", flush=True)
        try:    # tee to a pod log so a HUNG/crashed SFT is OBSERVABLE (pulled on failure), not a silent SSH timeout.
            _rs = run_step(ip, port, "DSL-SFT",   # 2026-06-20: a re-SFT hung ~2h with NO captured error -> mirror PROBE-C2's tee+pull.
                           f"{tenv}SKIP_PB=1 MAXN={sft_maxn} BATCH={sft_batch} "   # QUANT4 now from tenv (GLM=bf16 / Qwen=nf4)
                           f"DSL={gold} OUT=/root/qwen_poker_lora python3 -u -m training.qwen_sft 2>&1 | tee /root/sft.log",
                           timeout=max(600, sft_to))
            sft_ok = _grep(_rs, "SAVED LoRA")
        except Exception as _se:      # noqa: BLE001 — timeout/SSH error -> pull the pod log so the failure point is visible
            print(f"  DSL-SFT raised {type(_se).__name__}; pulling /root/sft.log for diagnosis", flush=True)
            sft_ok = False
        if not sft_ok:
            try:
                _scp_down(ip, port, "/root/sft.log", "data/_sft_hang.log")
                with open("data/_sft_hang.log", encoding="utf-8", errors="replace") as _lf:
                    print("  --- sft.log tail ---\n  " + "\n  ".join(_lf.read().splitlines()[-25:]), flush=True)
            except Exception as _le:  # noqa: BLE001
                print(f"  (sft.log pull failed: {_le})", flush=True)
            print("  SFT FAILED -> abort.", flush=True)
            return

        # C2 probe: 2-step micro-GRPO on the real adapter -> STEP_TIME_S. Uses the REAL tenv (BASE + the scale VLLM_MEM +
        # the parallel reward) so it canaries colocate-OOM AND reward-throughput at the settings the E run will use.
        # STRUCTURED=0 for GLM: the bounded-think regex [\s\S]{0,1500}</think>... is a state-explosion that makes vLLM's
        # guided decoding (xgrammar) HANG (probe timed out at both 360s AND 900s). The SFT (97.5% token-acc) emits the
        # format without the grammar. tee to a pod log so a hang is OBSERVABLE (pulled on failure), not a silent SSH timeout.
        _struct = "0" if _glm else "1"
        try:
            rp = run_step(ip, port, "PROBE-C2",
                          f"{tenv}ADAPTER=/root/qwen_poker_lora OUT=/root/_probe N_STATES=12 NUM_GEN=4 GEN_BATCH=8 K_ROLL=4 "
                          f"MAX_STEPS=2 STRUCTURED={_struct} METRICS_PATH=/root/_probe.jsonl "
                          "python3 -u -m training.qwen_grpo 2>&1 | tee /root/_probe.log", timeout=900)
        except Exception as _pe:                  # timeout/SSH error -> pull the pod log so the hang point is visible
            print(f"  PROBE-C2 raised {type(_pe).__name__}; pulling /root/_probe.log for diagnosis", flush=True)
            try:
                _scp_down(ip, port, "/root/_probe.log", "data/_probe_hang.log")
                with open("data/_probe_hang.log", encoding="utf-8", errors="replace") as _lf:
                    print("  --- probe.log tail ---\n  " + "\n  ".join(_lf.read().splitlines()[-18:]), flush=True)
            except Exception as _le:
                print(f"  (probe.log pull failed: {_le})", flush=True)
            class _Dummy:
                stdout = stderr = ""
                returncode = 124
            rp = _Dummy()
        ptxt = (rp.stdout or "") + (rp.stderr or "")
        probe_ok = _grep(rp, "SAVED GRPO adapter") and "STEP_TIME_S=" in ptxt
        step_time = _parse_float(ptxt, "STEP_TIME_S=", 25.0)

        # decide STRUCTURED + MAX_STEPS + WALLCLOCK for E from the probe + remaining budget
        e_budget = max(120, budget_left() - 1500)             # reserve 1500s for eval+pull (the LLM eval is ~10s/hand -> 600s timed out)
        feasible = int(e_budget / max(step_time, 1.0))
        structured = "0" if _glm else ("1" if feasible >= 15 else "0")   # GLM: xgrammar hangs (see probe) -> free decoding
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
        aborted = {"v": False}
        if probe_ok and wallclock > 60:
            open(METRICS_LOCAL, "w", encoding="utf-8").close()   # clear stale metrics so the abort-watch reads only THIS run
            threading.Thread(target=_stream_metrics, args=(ip, port, stop), daemon=True).start()
            threading.Thread(target=_grpo_abort_watch, args=(stop, aborted), daemon=True).start()  # flawless-unattended kill
            threading.Thread(target=_stream_checkpoints, args=(ip, port, stop), daemon=True).start()  # abort-safe model sync
            re_ = run_step(ip, port, "DAPO-GRPO",
                           f"{tenv}ADAPTER=/root/qwen_poker_lora OUT=/root/qwen_poker_grpo N_STATES={g_n} K_ROLL={g_k} "
                           f"NUM_GEN=8 GEN_BATCH={g_gb} PD_BATCH={g_pd} MAX_COMP=320 STRUCTURED={structured} "
                           f"MAX_STEPS={g_steps} WALLCLOCK_S={wallclock} SAVE_STEPS={os.environ.get('SAVE_STEPS', '50')} "
                           "METRICS_PATH=/root/grpo_metrics.jsonl "
                           "python3 -u -m training.qwen_grpo",
                           timeout=int(e_budget + 180))
            stop.set()
            if aborted["v"]:                                     # broken generation -> pod already terminated; skip eval
                print("  GRPO early-aborted (broken generation) -> skipping eval; pod already terminated.", flush=True)
                return
            _scp_down(ip, port, "/root/grpo_metrics.jsonl", METRICS_LOCAL)    # final metrics pull
            grpo_ok = _grep(re_, "SAVED GRPO adapter")
        else:
            print("  probe failed / insufficient budget -> SKIP GRPO, eval the SFT adapter alone.", flush=True)

        # G FIRST — pull the trained adapter IMMEDIATELY. The model is the valuable output; a slow/failing eval must
        # NEVER lose it (the 2026-06-18 bug: GTO-EVAL timed out at 900s BEFORE the pull -> the trained GRPO model was
        # lost with the pod). Pull, THEN eval best-effort.
        grpo_path = "/root/qwen_poker_grpo" if grpo_ok else "/root/qwen_poker_lora"
        try:    # BEST-EFFORT pull — MUST NOT crash the run before the eval. The continuous-pull daemon already saved the
            # model (models/qwen_poker_grpo_live.tgz), and a final tar of the ~40 SAVE_STEPS checkpoints exceeded 180s ->
            # the GATE-2 eval never ran (round 9/11 bug). Wrapped + 300s; --exclude the checkpoint-* dirs so the tar is the
            # FINAL adapter only (small + fast), not every intermediate checkpoint.
            _ssh(ip, port, "tar czf /root/out.tgz --exclude='checkpoint-*' -C /root qwen_poker_grpo grpo_metrics.jsonl 2>/dev/null; "
                           "[ -f /root/out.tgz ] || tar czf /root/out.tgz -C /root qwen_poker_lora", timeout=300)
            dst = str(config.ROOT / "models" / "qwen_poker_grpo.tgz")
            d = _scp_down(ip, port, "/root/out.tgz", dst)
            print(f"  pulled adapter -> {dst}" if d.returncode == 0 else f"  pull FAILED: {(d.stderr or '')[:160]}", flush=True)
        except Exception as _pe:    # noqa: BLE001 — model is safe via the live pull; the GATE-2 eval MUST still run
            print(f"  final pull raised {type(_pe).__name__} -> model is in qwen_poker_grpo_live.tgz; continuing to the eval", flush=True)

        # F eval — BEST-EFFORT (the adapter is already pulled, so an eval timeout/crash never fails the run or loses the
        # model). tenv = same BASE (size-agnostic) + PYTHONHASHSEED=0 (reproducible bb/100).
        eval_hands = os.environ.get("EVAL_HANDS", "1000" if SCALE else "200")
        try:
            run_step(ip, port, "GTO-EVAL",
                     f"{tenv}SFT=/root/qwen_poker_lora GRPO={grpo_path} EVAL_HANDS={eval_hands} "
                     "GATES_OUT=/root/eval_gates.json python3 -u -m training.qwen_eval_gto",
                     timeout=min(1500, max(120, int(budget_left() - 150))))
            _scp_down(ip, port, "/root/eval_gates.json", str(config.ROOT / "data" / "eval_gates.json"))   # -> dashboard
        except Exception as e:  # noqa: BLE001 — eval is best-effort; the adapter is already saved locally
            print(f"  GTO-EVAL failed/timed out ({type(e).__name__}) -> adapter already pulled; skipping gate-ladder", flush=True)
    finally:
        _killall()


if __name__ == "__main__":
    main()
