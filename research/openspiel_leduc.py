"""Validate vetted neural CFR: OpenSpiel Deep CFR (PyTorch) on Leduc Hold'em -> exploitability.
Runs on the RunPod GPU pod. A low nash_conv proves the neural solver converges (correct + trustworthy).
"""
import sys
import time

import torch
# Work around an OpenSpiel bug: action_probabilities uses the legacy torch.FloatTensor(x, device=)
# constructor which rejects device='cuda'. Wrap it: build on CPU, then move to the target device.
_ORIG_FT = torch.FloatTensor
def _ft(*a, **kw):
    dev = kw.pop("device", None)
    t = _ORIG_FT(*a, **kw)
    return t.to(dev) if dev is not None else t
torch.FloatTensor = _ft

import pyspiel
from open_spiel.python import policy
from open_spiel.python.algorithms import exploitability

try:
    from open_spiel.python.pytorch import deep_cfr
    BACKEND = "pytorch"
except Exception:  # noqa: BLE001
    from open_spiel.python.algorithms import deep_cfr  # TF fallback
    BACKEND = "tf"

ITERS = int(sys.argv[1]) if len(sys.argv) > 1 else 50
TRAV = int(sys.argv[2]) if len(sys.argv) > 2 else 400
DEV = "cuda" if torch.cuda.is_available() else "cpu"
print(f"OpenSpiel Deep CFR on Leduc | backend={BACKEND} | device={DEV} | iters={ITERS} trav={TRAV}",
      flush=True)
game = pyspiel.load_game("leduc_poker")
t0 = time.time()
solver = deep_cfr.DeepCFRSolver(
    game,
    policy_network_layers=(256, 256),
    advantage_network_layers=(128, 128),
    num_iterations=ITERS,
    num_traversals=TRAV,
    learning_rate=1e-3,
    batch_size_advantage=2048,
    batch_size_strategy=2048,
    memory_capacity=int(1e7),
    policy_network_train_steps=400,
    advantage_network_train_steps=750,
    reinitialize_advantage_networks=True,
    device=DEV,
    print_nash_convs=True,
)
solver.solve()
avg = policy.tabular_policy_from_callable(game, solver.action_probabilities)
conv = exploitability.nash_conv(game, avg)
print(f"RESULT nash_conv(exploitability) = {conv:.4f}  (chips/hand; lower=closer to Nash) "
      f"in {time.time()-t0:.0f}s", flush=True)
