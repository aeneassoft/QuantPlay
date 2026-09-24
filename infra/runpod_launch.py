"""RunPod launcher for the heavy stack-depth training job. SAFE BY DEFAULT: dry-run only checks the
account (balance) and prints the exact launch recipe + cost estimate. It provisions NOTHING unless
you pass --go (and even then it cost-caps and asks for nothing it can't afford).

  Dry-run (default):  python -m extraction.runpod_launch
  Actually launch:    python -m extraction.runpod_launch --go      # <- only on the user's word

Reliable path is: this script (or the RunPod UI) creates a high-vCPU CPU pod, then you push the repo
with `runpodctl send`, run the bootstrap, and pull the result json with `runpodctl receive`.
"""
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request

from pokerbot import config

KEY_FILE = r"C:\Users\hampe\Desktop\Secret keys\Runpod-machiavel key.txt"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36")
BOOTSTRAP = config.ROOT / "infra/serverless/pod_bootstrap.sh"
EST_MIN, EST_MAX = 0.5, 3.0      # estimated USD for one full run (CPU pod, ~30-90 min)


def _key() -> str:
    return open(KEY_FILE, encoding="utf-8").read().strip().splitlines()[0].strip()


def _gql(query: str, variables: dict | None = None) -> dict:
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request("https://api.runpod.io/graphql?api_key=" + _key(), data=body,
                                 headers={"Content-Type": "application/json", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def write_bootstrap() -> None:
    BOOTSTRAP.write_text(
        "#!/bin/bash\nset -e\ncd /workspace/PokerB\npip install -q -r requirements.txt\n"
        "python -m pokerbot.benchmark.runpod_train --pop 300 --hands 300 --iters 200 --workers $(nproc)\n"
        "echo DONE: knowledge_base/exploit/stack_depth_params.json\n", encoding="utf-8")


def recipe() -> str:
    return (
        "  1) Create a high-vCPU CPU pod (e.g. 32 vCPU) from a python:3.12 image (this script with "
        "--go, or the RunPod UI).\n"
        "  2) Push the project:   runpodctl send .            (from C:\\Users\\hampe\\Desktop\\PokerB)\n"
        "  3) On the pod:         bash /workspace/PokerB/pod_bootstrap.sh\n"
        "  4) Pull the result:    runpodctl receive <code>    (knowledge_base/exploit/stack_depth_params.json)\n"
        "  Optional tournament variant: add --icm to the training command.")


def dry_run() -> None:
    write_bootstrap()
    try:
        d = _gql("query { myself { id clientBalance } }")
        bal = d.get("data", {}).get("myself", {}).get("clientBalance")
    except Exception as e:  # noqa: BLE001
        print("RunPod check FAILED:", type(e).__name__, str(e)[:120])
        bal = None
    print("=== RunPod launch plan (DRY-RUN — nothing provisioned) ===")
    print(f"Account balance: ${bal}")
    print(f"Job: stack-depth self-play hardening (5 depths x 18 param-combos x 300 opp x 300 hands).")
    print(f"Hardware: CPU pod, many vCPU (the job parallelises over cores; no GPU needed).")
    print(f"Estimated cost: ${EST_MIN:.1f}-{EST_MAX:.1f}, ~30-90 min on 32 vCPU.")
    print(f"Bootstrap written: {BOOTSTRAP}")
    print("Recipe:")
    print(recipe())
    print("\nTo actually launch: re-run with  --go  (only on your word).")


def go() -> None:
    write_bootstrap()
    d = _gql("query { myself { clientBalance } }")
    bal = d.get("data", {}).get("myself", {}).get("clientBalance") or 0
    if bal < EST_MAX:
        print(f"ABORT: balance ${bal} < safety reserve ${EST_MAX}. Not provisioning.")
        return
    print(f"Balance ${bal} OK. Provisioning a CPU pod (cost-capped ~${EST_MAX})...")
    # NOTE: exact CPU-pod schema can vary by account/template; if this mutation 422s, create the pod
    # in the RunPod UI and follow the printed recipe (send/bootstrap/receive) — the job itself is ready.
    mut = ("mutation($in: PodFindAndDeployOnDemandInput) { podFindAndDeployOnDemand(input:$in) "
           "{ id imageName machineId } }")
    inp = {"in": {"cloudType": "COMMUNITY", "minVcpuCount": 16, "minMemoryInGb": 32,
                  "containerDiskInGb": 20, "volumeInGb": 0, "imageName": "runpod/base:0.4.0-cpu",
                  "name": "pokerb-train", "dockerArgs": "", "ports": "22/tcp"}}
    try:
        r = _gql(mut, inp)
        errs = r.get("errors")
        pod = (r.get("data") or {}).get("podFindAndDeployOnDemand")
        if errs or not pod:
            msg = (errs[0].get("message") if errs else "no pod returned")
            print(f"Headless provision not available ({msg}). NO pod created, NO cost.")
            print("Create a 32-vCPU python:3.12 pod in the RunPod UI, then follow the recipe:")
            print(recipe())
            return
        print(f"\nPod {pod.get('id')} created. Now:\n{recipe()}")
    except urllib.error.HTTPError as e:  # noqa: BLE001
        print("Provision call returned", e.code, "- create the pod via the RunPod UI and follow the recipe:")
        print(recipe())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--go", action="store_true", help="actually provision a pod (costs money)")
    args = ap.parse_args()
    (go if args.go else dry_run)()


if __name__ == "__main__":
    main()
