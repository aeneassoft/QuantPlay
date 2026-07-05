"""Self-killing HEADS-UP Slumbot benchmark on a RunPod GPU — the bot under test = our DEPLOYED bot (the fine-tuned
Qwen brain driving our engine via program-of-thought, served by vLLM). Provisions ONE GPU (FAST chain), arms the
pod-side self-destruct watchdog, ships the code bundle + the GRPO LoRA adapter, starts a vLLM OpenAI-compatible
server (base Qwen3-8B + the LoRA), runs the extended `slumbot_llm` driver (--backend vllm --concurrency K), and
CONTINUOUSLY pulls /root/slumbot_progress.jsonl -> data/slumbot_progress.jsonl every ~60s so a crash/abort loses at
most the in-flight hand. ALWAYS terminates the pod (atexit + finally) — the user's #1 cost rule. Mirrors
infra/runpod_rl_campaign.py (same launch_gpu / _arm_watchdog / _killall structure + helpers).

Run:    python -m infra.slumbot_pod                 # default: 3000 hands, concurrency 8 (~$8, ~1-2h)
        HANDS=500 CONCURRENCY=8 python -m infra.slumbot_pod        # a cheaper sighter
Verify afterwards: python -m infra.runpod_run --status   (must show NO tracked pods)
Watch live (the continuous pull): tail -f data/slumbot_progress.jsonl

PREREQ: the GRPO adapter dir exists locally -> it's scp'd to the pod:
   models/qwen_poker_grpo   (adapter_config.json says base = Qwen/Qwen3-8B, r=64)
"""
from __future__ import annotations

import atexit
import json
import os
import threading
import time

from infra import runpod_run as R
from infra.cfv_pod_campaign import _scp_down, _scp_up, _ssh, ssh_endpoint
from infra.runpod_rl_campaign import _arm_watchdog, launch_gpu
from pipeline import orchestrate as O
from pokerbot import config

REMOTE = "/root/pokerb"
ADAPTER_LOCAL = str(config.ROOT / "models" / "qwen_poker_grpo")    # base = Qwen/Qwen3-8B, LoRA r=64 (adapter_config.json)
ADAPTER_REMOTE = "/root/qwen_poker_grpo"
PROGRESS_REMOTE = "/root/slumbot_progress.jsonl"
PROGRESS_LOCAL = str(config.ROOT / "data" / "slumbot_progress.jsonl")
FINAL_LOCAL = str(config.ROOT / "data" / "slumbot_result.json")

BASE = os.environ.get("BASE", "Qwen/Qwen3-8B")                     # the LoRA's base (must match adapter_config.json)
LORA_NAME = os.environ.get("LORA_NAME", "grpo")                   # the served --lora-modules name -> driver --model
MAX_LORA_RANK = os.environ.get("MAX_LORA_RANK", "64")            # MUST be >= the adapter's r (64) or vLLM rejects the LoRA
HANDS = int(os.environ.get("HANDS", "3000"))
CONCURRENCY = int(os.environ.get("CONCURRENCY", "8"))
GPU_COUNT = int(os.environ.get("GPU_COUNT", "1"))
VLLM_MEM = os.environ.get("VLLM_MEM", "0.90")                    # one 8B + KV cache fits easily; fill it for batch headroom
VLLM_PORT = int(os.environ.get("VLLM_PORT", "8000"))
PULL_S = int(os.environ.get("PULL_S", "60"))                    # the continuous progress-pull period
HARD_CAP_S = int(os.environ.get("HARD_CAP_S", "7200"))          # ~2h budget guard (the run is ~1-2h)
DISK = int(os.environ.get("DISK", "120"))                       # 8B download (~16GB) + cache; 120GB is ample

# Setup: vLLM + the engine/parse deps (treys/numpy = table+equity; peft = an optional adapter-merge fallback). The
# IMAGE already has a matched torch (runpod_run.IMAGE = cu1281/torch280) -> pin it so pip resolves a COMPATIBLE vLLM
# (the cu124 ABI / cu130 libnvJitLink traps from pod_setup_rl.sh). transformers pinned to vLLM's era for the tokenizer.
SETUP_SH = r"""set -e
cd /root
export PIP_BREAK_SYSTEM_PACKAGES=1
PIP="python3 -m pip"
echo "  python: $(python3 --version 2>&1) | torch: $(python3 -c 'import torch;print(torch.__version__)' 2>&1)"
TORCH_PIN=$(python3 -c "import torch; print('torch=='+torch.__version__.split('+')[0])" 2>/dev/null || echo "")
echo "  image torch pin: ${TORCH_PIN:-<none>}"
$PIP install -q ${TORCH_PIN} vllm "transformers>=4.55.2,<4.57" hf_transfer treys numpy peft >~/pip_slumbot.log 2>&1 || { echo SETUP_FAILED; tail -40 ~/pip_slumbot.log; exit 1; }
python3 -c "import torch,vllm,treys,numpy; print(f'SLUMBOT_SETUP_OK | torch {torch.__version__} | vllm {vllm.__version__}')"
"""


def setup_pod(ip, port) -> bool:
    """Upload the code bundle + the GRPO adapter, install vLLM + engine deps. Returns True iff SLUMBOT_SETUP_OK."""
    tgz = O.build_tarball()                                   # pokerbot+dataset+training+infra+research+kb subset (lean)
    print(f"  bundle {os.path.getsize(tgz) / 1e6:.1f} MB -> pod", flush=True)
    if O.push(ip, port, tgz).returncode != 0:
        print("  code upload FAILED", flush=True)
        return False
    if not os.path.isdir(ADAPTER_LOCAL):
        print(f"  ADAPTER MISSING: {ADAPTER_LOCAL} (need the trained GRPO LoRA) -> abort", flush=True)
        return False
    up = _scp_up(ip, port, [ADAPTER_LOCAL], ADAPTER_REMOTE)   # scp -r the LoRA dir -> /root/qwen_poker_grpo
    if up.returncode != 0:
        print(f"  adapter upload FAILED: {(up.stderr or '')[:200]}", flush=True)
        return False
    # _scp_up -r of dir X to /root/qwen_poker_grpo lands files at /root/qwen_poker_grpo/qwen_poker_grpo/* -> normalize.
    _ssh(ip, port, f"[ -f {ADAPTER_REMOTE}/adapter_config.json ] || (mv {ADAPTER_REMOTE}/qwen_poker_grpo/* {ADAPTER_REMOTE}/ 2>/dev/null; true)",
         timeout=30)
    chk = _ssh(ip, port, f"ls {ADAPTER_REMOTE}/adapter_config.json", timeout=30)
    if "adapter_config.json" not in (chk.stdout or ""):
        print(f"  adapter not where expected on pod: {(chk.stdout or chk.stderr or '').strip()[:160]}", flush=True)
        return False
    import base64
    sh_b64 = base64.b64encode(SETUP_SH.encode()).decode()    # base64 -> no SSH-quoting hazard (the project pattern)
    r = _ssh(ip, port, f"echo '{sh_b64}' | base64 -d > /root/slumbot_setup.sh && bash /root/slumbot_setup.sh",
             timeout=1500)
    out = ((r.stdout or "") + "\n" + (r.stderr or "")).strip()
    ok = "SLUMBOT_SETUP_OK" in out
    print(f"  setup {'OK' if ok else 'FAILED'}:", flush=True)
    print("   " + "\n   ".join(out.splitlines()[-20:]), flush=True)
    return ok


def start_vllm(ip, port) -> None:
    """Launch the vLLM OpenAI-compatible server in the BACKGROUND via setsid (survives the SSH teardown, like the
    watchdog). base Qwen3-8B + the GRPO LoRA as a named module -> the driver hits it as --model grpo. max-lora-rank
    MUST be >= the adapter's r (64) or the LoRA is rejected. Logs to /root/vllm.log for the readiness poll + debug."""
    serve = (
        f"HF_HUB_ENABLE_HF_TRANSFER=1 VLLM_ALLOW_RUNTIME_LORA_UPDATING=False "
        f"vllm serve {BASE} --port {VLLM_PORT} --enable-lora "
        f"--lora-modules {LORA_NAME}={ADAPTER_REMOTE} --max-lora-rank {MAX_LORA_RANK} "
        f"--gpu-memory-utilization {VLLM_MEM} --tensor-parallel-size {GPU_COUNT} "
        f"--max-model-len 4096 --disable-log-requests"
    )
    import base64
    launch = (f"setsid bash -c '{serve}' </dev/null >/root/vllm.log 2>&1 &\n"
              "sleep 1; echo VLLM_LAUNCHED")
    launch_b64 = base64.b64encode(launch.encode()).decode()
    r = _ssh(ip, port, f"echo '{launch_b64}' | base64 -d | bash", timeout=60)
    print(f"  vLLM launch: {'OK' if 'VLLM_LAUNCHED' in (r.stdout or '') else 'unclear'} "
          f"(base={BASE} lora={LORA_NAME} rank={MAX_LORA_RANK})", flush=True)


def wait_vllm_ready(ip, port, deadline_s: int) -> bool:
    """Poll the pod's vLLM /health until it returns 200 (8B download + load can take a few minutes). Returns True iff
    ready before the deadline; prints the vllm.log tail on failure so a model/LoRA/OOM error is visible."""
    t0 = time.time()
    probe = (f"curl -s -o /dev/null -w '%{{http_code}}' http://127.0.0.1:{VLLM_PORT}/health")
    while time.time() - t0 < deadline_s:
        r = _ssh(ip, port, probe, timeout=30)
        if "200" in (r.stdout or ""):
            # confirm the LoRA module is actually served (so --model grpo will resolve, not 404)
            mr = _ssh(ip, port, f"curl -s http://127.0.0.1:{VLLM_PORT}/v1/models", timeout=30)
            served = LORA_NAME in (mr.stdout or "")
            print(f"  vLLM READY after {time.time()-t0:.0f}s | lora '{LORA_NAME}' served={served}", flush=True)
            if not served:
                print("   /v1/models did not list the LoRA -> the driver --model must match a served id:", flush=True)
                print("   " + (mr.stdout or "")[:300], flush=True)
            return served
        time.sleep(10)
    tail = _ssh(ip, port, "tail -30 /root/vllm.log 2>/dev/null", timeout=30)
    print(f"  vLLM NOT ready within {deadline_s}s -> abort. vllm.log tail:", flush=True)
    print("   " + "\n   ".join((tail.stdout or "").splitlines()[-30:]), flush=True)
    return False


def _stream_progress(ip, port, stop: threading.Event):
    """Daemon: scp the pod's growing slumbot_progress.jsonl -> data/slumbot_progress.jsonl every PULL_S — the CONTINUOUS
    pull, so a pod death (crash / SSH-timeout / abort) loses at most one in-flight hand, never the whole run."""
    os.makedirs(os.path.dirname(PROGRESS_LOCAL), exist_ok=True)
    while not stop.is_set():
        try:
            d = _scp_down(ip, port, PROGRESS_REMOTE, PROGRESS_LOCAL)
            if d.returncode == 0:
                try:
                    n = sum(1 for ln in open(PROGRESS_LOCAL, encoding="utf-8") if ln.strip())
                    if n:
                        last = json.loads(open(PROGRESS_LOCAL, encoding="utf-8").readlines()[-1])
                        print(f"  [progress] {n} hands pulled | cum {last.get('cum_bb100')} bb/100 "
                              f"| frac_bad {last.get('frac_bad')}", flush=True)
                except Exception:  # noqa: BLE001 — tolerate a half-written tail line mid-scp
                    pass
        except Exception:  # noqa: BLE001 — file may not exist yet; retry
            pass
        stop.wait(PULL_S)


def run_benchmark(ip, port, budget_left) -> bool:
    """Run the extended slumbot_llm driver on the pod (blocking ssh) against the live vLLM server. The continuous-pull
    daemon already mirrors the progress file locally; this returns True iff the driver printed the final result line."""
    wall = max(300, int(budget_left() - 300))                # reserve ~5min for the final pull + kill
    cmd = (f"cd {REMOTE} && PYTHONPATH={REMOTE} HF_HUB_OFFLINE=1 python3 -u -m pokerbot.benchmark.slumbot_llm "
           f"--backend vllm --vllm-url http://127.0.0.1:{VLLM_PORT} --model {LORA_NAME} "
           f"--concurrency {CONCURRENCY} --hands {HANDS} --progress-out {PROGRESS_REMOTE}")
    print(f"  >>> driver: vllm | hands={HANDS} concurrency={CONCURRENCY} model={LORA_NAME} (wall {wall}s)", flush=True)
    r = _ssh(ip, port, cmd, timeout=wall)
    out = ((r.stdout or "") + "\n" + (r.stderr or "")).strip()
    print("  <<< driver tail:", flush=True)
    print("   " + "\n   ".join(out.splitlines()[-12:]), flush=True)
    return "bb/100" in out and "hands=" in out


def main():
    T0 = time.time()

    def budget_left():
        return HARD_CAP_S - (time.time() - T0)

    stop = threading.Event()
    _ended = {"done": False}

    def _killall():
        stop.set()
        if _ended["done"]:
            return
        _ended["done"] = True
        print("  >>> finally/atexit: terminating the Slumbot pod <<<", flush=True)
        try:
            R.kill()
        except Exception as e:  # noqa: BLE001
            print(f"  kill error (run `python -m infra.runpod_run --kill` MANUALLY): {e}", flush=True)
    atexit.register(_killall)

    print(f"SLUMBOT POD BENCHMARK (self-killing). hands={HANDS} concurrency={CONCURRENCY} base={BASE} lora={LORA_NAME} "
          f"HARD_CAP={HARD_CAP_S}s. Watch: tail -f {PROGRESS_LOCAL}", flush=True)
    try:
        pid, gpu = launch_gpu(disk=DISK)
        if not pid:
            print("no GPU pod launched; aborting (no cost).", flush=True)
            return
        ip, port = ssh_endpoint(pid)
        if not (ip and port):
            print("pod never exposed SSH; aborting.", flush=True)
            return
        _arm_watchdog(ip, port, pid, HARD_CAP_S + 1800)      # pod-side self-destruct backstop (money-safety) ASAP
        if not setup_pod(ip, port):
            print("  setup failed -> abort (pod will be killed).", flush=True)
            return

        start_vllm(ip, port)
        ready_deadline = min(900, max(120, int(budget_left() - 600)))   # 8B load can take minutes; cap at 15min
        if not wait_vllm_ready(ip, port, ready_deadline):
            return                                           # finally: _killall terminates the pod

        # the CONTINUOUS pull: mirror the pod's progress JSONL locally every PULL_S (crash/abort loses ~1 hand max)
        threading.Thread(target=_stream_progress, args=(ip, port, stop), daemon=True).start()

        ok = run_benchmark(ip, port, budget_left)
        stop.set()

        _scp_down(ip, port, PROGRESS_REMOTE, PROGRESS_LOCAL)                  # final progress pull
        fr = _scp_down(ip, port, PROGRESS_REMOTE + ".final.json", FINAL_LOCAL)  # the one-line summary
        if fr.returncode == 0:
            try:
                res = json.load(open(FINAL_LOCAL, encoding="utf-8"))
                print(f"\n=== SLUMBOT RESULT === hands={res['hands']} | {res['bb100']:+.1f} bb/100 "
                      f"(+/-{res['stderr']:.1f} stderr) | frac_bad={res['frac_bad']:.2f} | model={res['model']}",
                      flush=True)
            except Exception:  # noqa: BLE001
                pass
        print(f"  benchmark {'COMPLETE' if ok else 'INCOMPLETE (see tail)'}; progress -> {PROGRESS_LOCAL}", flush=True)
    finally:
        _killall()


if __name__ == "__main__":
    main()
