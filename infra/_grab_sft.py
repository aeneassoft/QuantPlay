"""Lean 'nur Training + Test' path (plan #3, GRPO CUT): grab the SFT adapter the MOMENT it's saved, then KILL the pod.

Polls the pod for /root/qwen_poker_lora/adapter_model.safetensors. When present (SFT done), tars+pulls it to
models/sft_new.tgz and DELETES the pod (cutting the GRPO/eval detour + its cost + crash-surface). Also kills on a
sustained idle-crash (the SFT died). On exit the caller slims (sft_new.tgz already untars to qwen_poker_lora) + A/Bs.

Run: python -u -m infra._grab_sft [pod_id]
"""
from __future__ import annotations

import sys
import time

from infra import runpod_run as R
from infra.cfv_pod_campaign import _scp_down, _ssh, ssh_endpoint

POLL_S = 120
MAX_TICKS = 70                                                # ~2.3h safety


def _find_pod():
    c, r = R._req("GET", "/pods")
    ps = r if isinstance(r, list) else (r.get("pods") or r.get("data") or [])
    if c != 200 or not ps:
        return None
    pod = next((p for p in ps if "pokerb" in (p.get("name") or "").lower()), ps[0])
    return pod.get("id")


def main():
    pid = sys.argv[1] if len(sys.argv) > 1 else _find_pod()
    if not pid:
        print("GRAB: no pod -> exit", flush=True)
        return
    print(f"GRAB: watching {pid} for the SFT adapter (GRPO cut)", flush=True)
    idle = 0
    for t in range(MAX_TICKS):
        ts = time.strftime("%H:%M:%S")
        ip = port = None
        out = ""
        try:
            ip, port = ssh_endpoint(pid, wait_s=20)
            if ip and port:
                r = _ssh(ip, port,
                         "ls /root/qwen_poker_lora/adapter_model.safetensors 2>/dev/null && echo SAVED || echo NOPE; "
                         "echo GPU=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits | head -1); "
                         "echo PROC=$(ps -eo cmd | grep -E 'training.qwen_sft' | grep -v grep | wc -l)", timeout=40)
                out = r.stdout or ""
        except Exception as e:                               # noqa: BLE001
            print(f"GRAB {ts} t{t}: probe err {type(e).__name__}", flush=True)
        if not out:
            c, _ = R._req("GET", f"/pods/{pid}")
            if c == 404:
                print(f"GRAB {ts}: pod gone (404) -> exit", flush=True)
                return
            print(f"GRAB {ts} t{t}: unreachable", flush=True)
            time.sleep(POLL_S)
            continue
        saved = "SAVED" in out
        gpu = next((l.split("=", 1)[1] for l in out.splitlines() if l.startswith("GPU=")), "?")
        proc = next((l.split("=", 1)[1] for l in out.splitlines() if l.startswith("PROC=")), "?")
        print(f"GRAB {ts} t{t}: sft_saved={saved} GPU={gpu} proc={proc}", flush=True)
        if saved:
            print("GRAB: SFT adapter SAVED -> tar + pull, then KILL (cut GRPO)", flush=True)
            _ssh(ip, port, "cd /root && tar czf sft_new.tgz qwen_poker_lora", timeout=180)
            d = _scp_down(ip, port, "/root/sft_new.tgz", "models/sft_new.tgz")
            ok = d.returncode == 0
            print(f"GRAB: pulled -> models/sft_new.tgz (rc={d.returncode})", flush=True)
            if ok:
                R._req("DELETE", f"/pods/{pid}")
                print(f"GRAB: DELETE pod {pid} -> exit (SFT_GRABBED)", flush=True)
                return
            print("GRAB: pull FAILED -> NOT killing (retry next tick)", flush=True)   # never kill before the model is safe
        elif (gpu.isdigit() and int(gpu) <= 5) and proc == "0":   # SFT died without saving
            idle += 1
            print(f"GRAB: idle {idle}/2 (GPU idle, no sft proc, no adapter)", flush=True)
            if idle >= 2:
                try:
                    print("GRAB --- sft.log tail ---\n" + (_ssh(ip, port, "tail -20 /root/sft.log", timeout=30).stdout or ""),
                          flush=True)
                except Exception:                            # noqa: BLE001
                    pass
                R._req("DELETE", f"/pods/{pid}")
                print(f"GRAB: idle-crash -> DELETE pod {pid} -> exit", flush=True)
                return
        else:
            idle = 0
        time.sleep(POLL_S)
    print("GRAB: MAX_TICKS -> exit", flush=True)


if __name__ == "__main__":
    main()
