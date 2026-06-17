"""scp-ORCHESTRATION — moves data PC<->pod for the 2-node system (Phase 3). Bundles the code+dataset into ONE tarball
(one fast scp, per the cfv_pod_campaign lesson: scp -r of hundreds of small files stalls), pushes it to the RunPod
trainer, and pulls the best adapter + eval report back. Reuses the SSH key + scp pattern from
infra/cfv_pod_campaign.py; pod lifecycle = infra/runpod_run.py. Per docs/QWEN_6MAX_PLAN.md.

HARD RULE (CLAUDE.md): this moves the DATASET + CODE to the pod; frontier APIs NEVER touch the pod (PC hub only).
The lean bundle deliberately EXCLUDES knowledge_base/hand_histories + books/ (huge, not needed by the trainer/RL env).
"""
from __future__ import annotations

import subprocess
import tarfile
from pathlib import Path

from pokerbot import config

KEY = r"C:\Users\hampe\.ssh\pokerb_runpod"
SSH = ["-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null"]

# What the pod's SFT/GRPO trainer + RL env (table.py) + brain api + the TEACHER generator actually need — lean on purpose.
BUNDLE = ["pokerbot", "dataset", "training", "infra", "research",
          "knowledge_base/math", "knowledge_base/ranges", "knowledge_base/exploit", "knowledge_base/postflop"]


def build_tarball(out_path=None, members=None) -> str:
    """Bundle code+dataset into ONE .tgz for a single fast scp. Returns the tarball path. Skips missing members."""
    out_path = str(out_path or (config.DATA_DIR / "podbundle.tgz"))
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    members = members or BUNDLE
    with tarfile.open(out_path, "w:gz") as t:
        for m in members:
            p = config.ROOT / m
            if p.exists():
                t.add(p, arcname=m)
    return out_path


def push(ip, port, tarball, remote="/root/bundle.tgz", unpack_to="/root/pokerb") -> subprocess.CompletedProcess:
    """scp the tarball UP, then unpack it on the pod."""
    up = subprocess.run(["scp", "-i", KEY, "-P", str(port), *SSH, tarball, f"root@{ip}:{remote}"],
                        capture_output=True, text=True)
    if up.returncode != 0:
        return up
    return subprocess.run(["ssh", "-i", KEY, "-p", str(port), *SSH, f"root@{ip}",
                           f"mkdir -p {unpack_to} && tar xzf {remote} -C {unpack_to}"],
                          capture_output=True, text=True)


def pull(ip, port, remote, local) -> subprocess.CompletedProcess:
    """scp a result (best adapter / eval report) DOWN from the pod."""
    Path(local).parent.mkdir(parents=True, exist_ok=True)
    return subprocess.run(["scp", "-i", KEY, "-P", str(port), *SSH, f"root@{ip}:{remote}", str(local)],
                          capture_output=True, text=True)
