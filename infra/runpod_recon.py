"""Read-only RunPod API recon: which deploy mutations exist, GPU/CPU options, ssh-key setting.
Run: python -m extraction.runpod_recon
"""
import json

from infra.runpod_launch import _gql


def q(label, query, path=None):
    try:
        r = _gql(query)
        if r.get("errors"):
            print(f"{label}: ERR {json.dumps(r['errors'])[:200]}")
            return None
        data = r.get("data")
        print(f"{label}: {json.dumps(data)[:1500]}")
        return data
    except Exception as e:  # noqa: BLE001
        print(f"{label}: EXC {type(e).__name__} {str(e)[:150]}")
        return None


# 1) all mutation names -> find deploy/pod/cpu ones
m = q("mutations", "query { __schema { mutationType { fields { name } } } }")
if m:
    names = [f["name"] for f in m["__schema"]["mutationType"]["fields"]]
    hits = [n for n in names if any(k in n.lower() for k in ("deploy", "pod", "cpu", "terminate", "rent"))]
    print("DEPLOY/POD MUTATIONS:", hits)

# 2) GPU types (cheap ones double as many-vCPU CPU hosts)
q("gpuTypes", "query { gpuTypes { id displayName memoryInGb communityCloud secureCloud "
  "lowestPrice(input:{gpuCount:1}) { minimumBidPrice uninterruptablePrice } } }")

# 3) CPU options (may not exist on this schema)
q("cpuFlavors", "query { cpuFlavors { id displayName minVcpu maxVcpu } }")

# 4) my ssh key setting
q("myself.pubKey", "query { myself { pubKey } }")
