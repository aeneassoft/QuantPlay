"""Probe RunPod for CPU instance/flavor ids (read-only) so we can deploy the right CPU pod.
Run: python -m extraction.runpod_cpu_probe
"""
from __future__ import annotations

import json

from extraction.runpod_run import _graphql, _req

GQL_QUERIES = [
    "{ cpuFlavors { id displayName groupId specifics { vcpu ramGb } } }",
    "{ cpuFlavors { id displayName } }",
    "{ cpuTypes { id displayName cpuCount } }",
    "{ countryCodes }",   # sanity: confirms the endpoint responds at all
]


def main():
    for q in GQL_QUERIES:
        try:
            out = json.dumps(_graphql(q))
        except Exception as e:  # noqa: BLE001
            out = f"EXC {e}"
        print(f"GQL {q[:46]:48} -> {out[:600]}")
    print("\n-- REST attempts --")
    for path in ("/cpuFlavors", "/cpuTypes", "/cpu"):
        try:
            code, body = _req("GET", path)
            print(f"GET {path:14} -> {code} {json.dumps(body)[:300]}")
        except Exception as e:  # noqa: BLE001
            print(f"GET {path:14} -> EXC {e}")


if __name__ == "__main__":
    main()
