"""Independent safety-net monitor for the re-SFT campaign pod (scratch).

The campaign's run_step SSH-timeout does NOT fire cleanly on Windows -> a crashed/hung SFT leaves the pod idle-billing
until the watchdog (~hours). This polls the pod directly every POLL_S and, INDEPENDENT of the campaign, KILLS it on
EITHER failure mode: (a) idle-crash = GPU 0% + no train process + no adapter saved (the SFT died), or (b) SSH/probe
UNREACHABLE while the pod is API-alive for ~16 min (a hung run_step). Survives transient SSH errors (the whole loop body
is guarded — an earlier version died on an uncaught ssh_endpoint exception and went blind). Exits on DONE (out.tgz) /
pod-gone / kill / MAX_TICKS. Read data/_resft_mon.log for the live trace.

Run: python -u -m infra._resft_mon
"""
from __future__ import annotations

import time

from infra import runpod_run as R
from infra.cfv_pod_campaign import _ssh, ssh_endpoint

POLL_S = 240
MAX_TICKS = 50
UNREACHABLE_KILL = 4                                          # ~16 min SSH-unreachable while API-alive -> hang -> kill


def _find_pod():
    c, r = R._req("GET", "/pods")
    ps = r if isinstance(r, list) else (r.get("pods") or r.get("data") or [])
    if c != 200 or not ps:
        return None
    pod = next((p for p in ps if "pokerb" in (p.get("name") or "").lower()), ps[0])
    return pod.get("id")


def _probe(ip, port):
    """One SSH snapshot -> dict(GPU, PROC, ADAPTER, GRPO, SFTKB, DONE). Empty dict on failure."""
    cmd = ("echo GPU=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits | head -1); "
           "echo PROC=$(ps -eo cmd | grep -E 'training.qwen_(sft|grpo)' | grep -v grep | wc -l); "
           "echo ADAPTER=$([ -f /root/qwen_poker_lora/adapter_model.safetensors ] && echo 1 || echo 0); "
           "echo GRPO=$([ -f /root/qwen_poker_grpo/adapter_model.safetensors ] && echo 1 || echo 0); "
           "echo SFTKB=$(du -k /root/sft.log 2>/dev/null | cut -f1); "
           "echo DONE=$([ -f /root/out.tgz ] && echo 1 || echo 0)")
    r = _ssh(ip, port, cmd, timeout=40)
    d = {}
    for ln in (r.stdout or "").splitlines():
        if "=" in ln and ln.split("=")[0] in ("GPU", "PROC", "ADAPTER", "GRPO", "SFTKB", "DONE"):
            k, v = ln.split("=", 1)
            d[k] = v.strip()
    return d


def _alive(pid) -> bool:
    c, _ = R._req("GET", f"/pods/{pid}")
    return c != 404


def main():
    pid = None
    for _ in range(10):
        pid = _find_pod()
        if pid:
            break
        time.sleep(30)
    if not pid:
        print("MON: no pod appeared in 5 min -> exit", flush=True)
        return
    print(f"MON: watching pod {pid}", flush=True)
    idle_streak = unreachable = 0
    for tick in range(MAX_TICKS):
        ts = time.strftime("%H:%M:%S")
        try:                                                 # GUARD the whole probe — never die blind
            ip, port = ssh_endpoint(pid, wait_s=20)
            d = _probe(ip, port) if (ip and port) else {}
        except Exception as e:                               # noqa: BLE001
            d = {}
            print(f"MON {ts} t{tick}: probe raised {type(e).__name__}", flush=True)

        if not d:                                            # unreachable: pod gone, or a hung run_step
            if not _alive(pid):
                print(f"MON {ts}: pod gone (404) -> exit", flush=True)
                return
            unreachable += 1
            print(f"MON {ts} t{tick}: pod ALIVE but SSH/probe unreachable ({unreachable}/{UNREACHABLE_KILL})", flush=True)
            if unreachable >= UNREACHABLE_KILL:
                print(f"MON {ts}: unreachable ~{UNREACHABLE_KILL*POLL_S//60}min while alive -> HANG. KILLING pod {pid}.",
                      flush=True)
                R._req("DELETE", f"/pods/{pid}")
                return
            time.sleep(POLL_S)
            continue
        unreachable = 0

        gpu = d.get("GPU", "?"); proc = d.get("PROC", "0")
        adapter = d.get("ADAPTER", "0"); grpo = d.get("GRPO", "0")
        sftkb = d.get("SFTKB", "0"); done = d.get("DONE", "0")
        print(f"MON {ts} t{tick}: GPU={gpu}% proc={proc} sft.log={sftkb}KB adapter={adapter} grpo={grpo} done={done}",
              flush=True)
        if done == "1":
            print("MON: out.tgz present -> DONE, exit", flush=True)
            return
        training = (proc != "0") or (gpu.isdigit() and int(gpu) > 5)
        sft_started = sftkb.isdigit() and int(sftkb) > 0
        if sft_started and (not training) and adapter == "0" and grpo == "0":   # the SFT died without saving
            idle_streak += 1
            print(f"MON: IDLE streak {idle_streak}/2 (no train proc, GPU idle, no adapter)", flush=True)
            if idle_streak >= 2:
                print("MON: sustained idle -> CRASH. grabbing sft.log tail + KILLING pod.", flush=True)
                try:
                    rr = _ssh(ip, port, "tail -25 /root/sft.log 2>/dev/null", timeout=30)
                    print("MON --- sft.log tail ---\n" + (rr.stdout or "(empty)"), flush=True)
                except Exception:                            # noqa: BLE001
                    pass
                R._req("DELETE", f"/pods/{pid}")
                print(f"MON: DELETE pod {pid} -> exit (CRASH)", flush=True)
                return
        else:
            idle_streak = 0
        time.sleep(POLL_S)
    print("MON: MAX_TICKS reached -> exit", flush=True)


if __name__ == "__main__":
    main()
