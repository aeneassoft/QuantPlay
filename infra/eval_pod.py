"""ISOLATED Slumbot-baseline eval pod — measure the existing 8B (`qwen_poker_ckpt500`) vs Slumbot WITHOUT touching a
concurrently-training pod. The "before −72" reference to quantify the GRPO lift.

CRITICAL ISOLATION (CLAUDE.md cross-kill hazard): `runpod_run` tracks ALL pods in ONE session file and `kill()`
terminates EVERY tracked pod. So this script launches via `R._req("POST","/pods")` WITHOUT `R._track`, and kills ONLY
its own id via `R._req("DELETE", ...)` — it NEVER calls `R.kill()`. → a concurrently-training pod is never touched.

Run:  python -m infra.eval_pod [--hands 500]
Verify after:  python -m infra.runpod_run --status   (must STILL show only the training pod)
"""
from __future__ import annotations

import argparse
import atexit
import json
import os
import time

from infra import runpod_run as R
from infra.cfv_pod_campaign import _scp_up, _scp_down, _ssh, ssh_endpoint
from pipeline import orchestrate as O
from pokerbot import config

REMOTE = "/root/pokerb"
HARD_CAP_S = int(os.environ.get("EVAL_HARD_CAP", "5400"))    # 90-min wall budget (eval ~15-25 min; margin for setup)
EVAL_GPU = os.environ.get("EVAL_GPU", "")                    # "" = the R.FAST chain (H100/H200); else force one gpuTypeId
EVAL_BASE = os.environ.get("EVAL_BASE", "Qwen/Qwen3-8B")
ADAPTER_LOCAL = config.MODELS_DIR / "qwen_poker_ckpt500"     # the existing 8B baseline (base = Qwen3-8B)


def _launch_isolated(disk: int = 80):
    """Launch ONE GPU via the raw API — deliberately NO `R._track`, so the training pod's session + `--kill` never see
    this pod (the cross-kill guard). Returns (pid, gpu) or (None, None)."""
    pub = open(R.PUBKEY_FILE, encoding="utf-8").read().strip()
    gpus = [EVAL_GPU] if EVAL_GPU else R.FAST
    for cloud in ("SECURE", "COMMUNITY"):
        for gpu in gpus:
            body = {"name": "pokerb-evalbase", "imageName": R.IMAGE, "cloudType": cloud, "computeType": "GPU",
                    "gpuTypeIds": [gpu], "gpuCount": 1, "containerDiskInGb": disk, "volumeInGb": 0,
                    "ports": ["22/tcp"], "env": {"PUBLIC_KEY": pub}}
            code, resp = R._req("POST", "/pods", body)
            if code in (200, 201):
                pid = resp.get("id")
                print(f"  launched ISOLATED eval pod {pid} on {gpu} [{cloud}] (${resp.get('costPerHr')}/hr) — NOT tracked",
                      flush=True)
                return pid, gpu
            print(f"  {cloud:9} {gpu:22}: {code} {json.dumps(resp)[:120]}", flush=True)
    return None, None


_state = {"killed": False}


def _kill_by_id(pid: str | None) -> None:
    """Terminate ONLY this pod (NEVER `R.kill()` — that would also kill the training pod). Idempotent."""
    if not pid or _state["killed"]:
        return
    _state["killed"] = True
    try:
        code, _ = R._req("DELETE", f"/pods/{pid}")
        print(f"  >>> eval pod {pid} TERMINATED (DELETE {code}). Training pod untouched. <<<", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"  !! eval-pod kill error for {pid} ({e}) — MANUALLY DELETE /pods/{pid} in the RunPod console", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hands", type=int, default=int(os.environ.get("EVAL_HANDS", "500")))
    ap.add_argument("--gate2", action="store_true",
                    help="eval the SAVED SFT+GRPO adapters (RL vs SFT mixed bb/100), no re-train")
    a = ap.parse_args()
    t0 = time.time()
    if not a.gate2 and not ADAPTER_LOCAL.exists():
        print(f"adapter {ADAPTER_LOCAL} missing; aborting (no cost).", flush=True)
        return

    pid = {"id": None}
    atexit.register(lambda: _kill_by_id(pid["id"]))
    print(f"ISOLATED EVAL-BASELINE POD — {EVAL_BASE} + {ADAPTER_LOCAL.name} vs Slumbot ({a.hands} hands). "
          "Never touches the training pod.", flush=True)
    try:
        pid["id"], _gpu = _launch_isolated()
        if not pid["id"]:
            print("no eval pod launched (no cost).", flush=True)
            return
        ip, port = ssh_endpoint(pid["id"])
        if not (ip and port):
            print("eval pod never exposed SSH; aborting.", flush=True)
            return

        # light INFERENCE setup (the image already has torch+cu128; no trl/vllm needed). Pin transformers to dodge the
        # known tokenizer bug; bitsandbytes for the nf4 load (slumbot_llm._load uses 4-bit).
        print("  >>> installing inference deps ...", flush=True)
        r = _ssh(ip, port, "export PIP_BREAK_SYSTEM_PACKAGES=1 && python3 -m pip install -q -U "
                 "'transformers>=4.55.2,<4.57' peft bitsandbytes treys numpy accelerate hf_transfer requests "
                 "2>&1 | tail -3; python3 -c 'import torch,transformers,peft,bitsandbytes; "
                 "print(\"DEPS_OK\", torch.__version__, transformers.__version__)'", timeout=900)
        if "DEPS_OK" not in (r.stdout or ""):
            print(f"  setup FAILED: {((r.stdout or '') + (r.stderr or ''))[-400:]}", flush=True)
            return
        print("  " + [ln for ln in (r.stdout or "").splitlines() if "DEPS_OK" in ln][-1], flush=True)

        if a.gate2:    # GATE-2: eval the SAVED SFT + GRPO adapters (NO re-training) -> qwen_eval_gto mixed-only -> RL vs SFT
            up = O.push(ip, port, O.build_tarball())
            if up.returncode != 0:
                print(f"  bundle push FAILED: {(up.stderr or '')[:200]}", flush=True); return
            sft_tgz, grpo_tgz = config.MODELS_DIR / "sft_slim.tgz", config.MODELS_DIR / "grpo_slim.tgz"   # adapter-only (no optimizer) -> fits the scp timeout
            if not (sft_tgz.exists() and grpo_tgz.exists()):
                print(f"  missing slim adapter tgz ({sft_tgz.name} / {grpo_tgz.name}); aborting.", flush=True); return
            sc = _scp_up(ip, port, [str(sft_tgz), str(grpo_tgz)], "/root/")
            if sc.returncode != 0:
                print(f"  adapter scp FAILED: {(sc.stderr or '')[:200]}", flush=True); return
            _ssh(ip, port, "cd /root && tar xzf sft_slim.tgz && tar xzf grpo_slim.tgz && "
                           "ls -d qwen_poker_lora checkpoint-* 2>/dev/null", timeout=300)
            print("  uploaded + untarred both adapters (SFT + GRPO)", flush=True)
            budget = max(300, int(HARD_CAP_S - (time.time() - t0) - 120))
            cmd = (f"cd {REMOTE} && PYTHONPATH={REMOTE} HF_HUB_OFFLINE=0 HF_HUB_ENABLE_HF_TRANSFER=1 "
                   f"BASE={EVAL_BASE} SFT=/root/qwen_poker_lora GRPO=$(ls -d /root/checkpoint-* | tail -1) "
                   f"EVAL_HANDS={a.hands} EVAL_MIXED_ONLY=1 GATES_OUT=/root/eval_gates.json "
                   f"python3 -u -m training.qwen_eval_gto")
            print(f"  >>> GATE-2 EVAL (mixed-only, {a.hands} hands) — RL vs SFT bb/100 ...", flush=True)
            r = _ssh(ip, port, cmd, timeout=budget)
            out = (r.stdout or "") + "\n" + (r.stderr or "")
            for ln in out.splitlines():
                if any(k in ln for k in ("GATE", "mixed", "bb_per", "G2", "RL", "SFT", "Traceback", "Error")):
                    print("   " + ln.strip(), flush=True)
            _scp_down(ip, port, "/root/eval_gates.json", str(config.DATA_DIR / "eval_gates.json"))
            print("  pulled eval_gates.json -> data/eval_gates.json", flush=True)
            return

        # upload the code bundle + the baseline adapter (models/ is NOT in the bundle)
        up = O.push(ip, port, O.build_tarball())
        if up.returncode != 0:
            print(f"  bundle push FAILED: {(up.stderr or '')[:200]}", flush=True)
            return
        _ssh(ip, port, f"mkdir -p {REMOTE}/models", timeout=60)
        sc = _scp_up(ip, port, [str(ADAPTER_LOCAL)], f"{REMOTE}/models/")
        if sc.returncode != 0:
            print(f"  adapter scp FAILED: {(sc.stderr or '')[:200]}", flush=True)
            return
        print(f"  uploaded bundle + adapter ({ADAPTER_LOCAL.name})", flush=True)

        # run the Slumbot eval. HF_HUB_OFFLINE=0 is ESSENTIAL: slumbot_llm setdefaults it to "1", which would block the
        # fresh-pod download of the Qwen3-8B base.
        budget = max(300, int(HARD_CAP_S - (time.time() - t0) - 120))
        cmd = (f"cd {REMOTE} && PYTHONPATH={REMOTE} HF_HUB_OFFLINE=0 HF_HUB_ENABLE_HF_TRANSFER=1 "
               f"python3 -u -m pokerbot.benchmark.slumbot_llm --hands {a.hands} --base {EVAL_BASE} "
               f"--adapter {REMOTE}/models/{ADAPTER_LOCAL.name}")
        print(f"  >>> SLUMBOT EVAL ({a.hands} hands) — this is the baseline number ...", flush=True)
        r = _ssh(ip, port, cmd, timeout=budget)
        out = (r.stdout or "") + "\n" + (r.stderr or "")
        for ln in out.splitlines():
            if any(k in ln for k in ("bb/100", "vs Slumbot", "Traceback", "Error", "frac_bad")):
                print("   " + ln.strip(), flush=True)
        res_path = config.DATA_DIR / "slumbot_baseline.txt"
        res_path.write_text(out, encoding="utf-8")
        print(f"  full output -> {res_path.relative_to(config.ROOT)}", flush=True)
    finally:
        _kill_by_id(pid["id"])
        # belt-and-suspenders: confirm via the API the eval pod is gone (best-effort)
        try:
            code, resp = R._req("GET", "/pods")
            pods = resp if isinstance(resp, list) else (resp.get("pods") or resp.get("data") or [])
            ids = [p.get("id") for p in pods] if code == 200 else []
            gone = pid["id"] not in ids
            print(f"  API check: eval pod gone={gone} | pods now={ids}", flush=True)
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    main()
