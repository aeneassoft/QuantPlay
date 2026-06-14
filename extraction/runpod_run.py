"""Provision a RunPod GPU pod (sshd image), expose its SSH endpoint so we can drive it, and tear it
down. Pod time is cheap; ALWAYS --kill when done.

  python -m extraction.runpod_run --launch        # create GPU pod (runpod/pytorch image, has sshd)
  python -m extraction.runpod_run --status         # poll status + print SSH ip:port when ready
  python -m extraction.runpod_run --kill            # terminate (do this when finished!)
"""
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request

from pokerbot import config

KEY_FILE = r"C:\Users\hampe\Desktop\Secret keys\Runpod-machiavel key.txt"
PUBKEY_FILE = r"C:\Users\hampe\.ssh\pokerb_runpod.pub"
SESSION = config.ROOT / "data" / "_runpod_session.json"
BASE = "https://rest.runpod.io/v1"
GQL = "https://api.runpod.io/graphql"
IMAGE = "runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04"   # has sshd + python + pip
GPUS = ["NVIDIA GeForce RTX 3090", "NVIDIA GeForce RTX 4090", "NVIDIA RTX A5000",
        "NVIDIA A100 80GB PCIe"]   # try cheap community GPUs in order
# Hopper/Ampere FIRST (mature, fast attention kernels). Blackwell B200/B300 LAST: their training
# kernels are immature -- torch 2.11 SDPA fell back to the math path on sm_100 => ~10x slow (observed
# 2026-06-14, 14B ran at ~25 s/it). Consumer 5090/4090 dropped (too little VRAM for 32B). Used by --fast.
FAST = ["NVIDIA H200", "NVIDIA H100 NVL", "NVIDIA H100 80GB HBM3", "NVIDIA H100 PCIe",
        "NVIDIA A100 80GB PCIe", "NVIDIA B200", "NVIDIA B300"]


def _key() -> str:
    return open(KEY_FILE, encoding="utf-8").read().strip().splitlines()[0].strip()


def _req(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Authorization": "Bearer " + _key(),
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def _graphql(query: str) -> dict:
    req = urllib.request.Request(GQL, data=json.dumps({"query": query}).encode(), method="POST",
                                 headers={"Authorization": "Bearer " + _key(),
                                          "Content-Type": "application/json",
                                          "User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode() or "{}")


def gpus() -> None:
    """List GPU types + price + cloud availability (fastest first)."""
    q = ("{ gpuTypes { id displayName memoryInGb secureCloud communityCloud "
         "lowestPrice(input:{gpuCount:1}){ uninterruptablePrice minimumBidPrice } } }")
    data = _graphql(q).get("data", {}).get("gpuTypes", [])
    want = ("B200", "B300", "GB200", "H200", "H100", "A100", "5090", "4090", "A6000", "L40")
    rows = [g for g in data if any(w in (g.get("id") or "") for w in want)]
    rows.sort(key=lambda g: ((g.get("lowestPrice") or {}).get("uninterruptablePrice") or 999))
    print(f"{'id':40} {'mem':>5} {'sec':>4} {'comm':>5} {'$/hr-onDemand':>14} {'$/hr-spot':>10}")
    for g in rows:
        lp = g.get("lowestPrice") or {}
        print(f"{g.get('id',''):40} {g.get('memoryInGb',''):>5} "
              f"{str(g.get('secureCloud')):>4} {str(g.get('communityCloud')):>5} "
              f"{str(lp.get('uninterruptablePrice')):>14} {str(lp.get('minimumBidPrice')):>10}")


def launch(fast: bool = False, disk: int = 60) -> None:
    pub = open(PUBKEY_FILE, encoding="utf-8").read().strip()
    if fast:
        combos = [("SECURE", g) for g in FAST] + [("COMMUNITY", g) for g in FAST]
    else:
        combos = [("COMMUNITY", g) for g in GPUS]
    for cloud, gpu in combos:
        body = {"name": "pokerb-deepcfr", "imageName": IMAGE, "cloudType": cloud,
                "computeType": "GPU", "gpuTypeIds": [gpu], "gpuCount": 1,
                "containerDiskInGb": disk, "volumeInGb": 0, "ports": ["22/tcp"],
                "env": {"PUBLIC_KEY": pub}}
        code, resp = _req("POST", "/pods", body)
        if code in (200, 201):
            pid = resp.get("id")
            SESSION.parent.mkdir(parents=True, exist_ok=True)
            SESSION.write_text(json.dumps({"id": pid}), encoding="utf-8")
            print(f"CREATED pod {pid} on {gpu} [{cloud}] (${resp.get('costPerHr')}/hr). Polling...")
            status()
            return
        print(f"  {cloud:9} {gpu:32}: {code} {json.dumps(resp)[:130]}")
    print("All GPU options failed — see errors above (no pod created, no cost).")


def launch_cpu(flavor: str = "cpu5c", vcpu: int = 32, disk: int = 40) -> None:
    """Launch a CPU pod (for the TexasSolver coverage campaign). cpu5c = high-freq Compute-Optimized."""
    pub = open(PUBKEY_FILE, encoding="utf-8").read().strip()
    body = {"name": "pokerb-cpu-solve", "imageName": IMAGE, "computeType": "CPU",
            "cpuFlavorIds": [flavor], "vcpuCount": vcpu,
            "containerDiskInGb": disk, "volumeInGb": 0, "ports": ["22/tcp"],
            "env": {"PUBLIC_KEY": pub}}
    code, resp = _req("POST", "/pods", body)
    if code in (200, 201):
        pid = resp.get("id")
        SESSION.parent.mkdir(parents=True, exist_ok=True)
        SESSION.write_text(json.dumps({"id": pid}), encoding="utf-8")
        print(f"CREATED CPU pod {pid} [{flavor} x{vcpu}vCPU] (${resp.get('costPerHr')}/hr). Polling...")
        status()
        return
    print(f"CPU launch failed: {code} {json.dumps(resp)[:500]}")


def status() -> None:
    pid = json.loads(SESSION.read_text())["id"]
    code, resp = _req("GET", f"/pods/{pid}")
    ds = resp.get("desiredStatus")
    ip = resp.get("publicIp")
    ports = resp.get("portMappings") or resp.get("ports")
    rt = resp.get("runtime")
    print(f"STATUS {code} | desired={ds} | publicIp={ip!r} | ports={ports} | runtime={json.dumps(rt)[:300] if rt else None}")
    print("  (full):", json.dumps(resp)[:500])


def kill() -> None:
    try:
        pid = json.loads(SESSION.read_text())["id"]
    except Exception:  # noqa: BLE001
        print("no session; nothing to kill")
        return
    code, resp = _req("DELETE", f"/pods/{pid}")
    print(f"TERMINATE {code} -> pod {pid} stopped (no more billing).")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--launch", action="store_true")
    ap.add_argument("--fast", action="store_true", help="prefer strongest GPUs (B200/H200/H100) on SECURE")
    ap.add_argument("--gpus", action="store_true", help="list GPU types + prices")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--kill", action="store_true")
    ap.add_argument("--cpu", action="store_true", help="launch a CPU pod (solver coverage campaign)")
    ap.add_argument("--flavor", default="cpu5c", help="CPU flavor (cpu5c=high-freq compute-optimized)")
    ap.add_argument("--vcpu", type=int, default=32)
    ap.add_argument("--disk", type=int, default=60, help="container disk GB (bump for big models, e.g. 200 for 32B)")
    args = ap.parse_args()
    if args.kill:
        kill()
    elif args.status:
        status()
    elif args.gpus:
        gpus()
    elif args.cpu:
        launch_cpu(args.flavor, args.vcpu)
    elif args.launch:
        launch(fast=args.fast, disk=args.disk)
    else:
        print("use --launch [--fast] / --cpu [--flavor --vcpu] / --gpus / --status / --kill")


if __name__ == "__main__":
    main()
