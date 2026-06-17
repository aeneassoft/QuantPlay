"""Phase 5a: neural Deep CFR GTO core on ABSTRACTED Heads-Up NLHE (OpenSpiel universal_poker, fcpa),
on the GPU pod. Incorporates the gpt-5.1 math-check corrections:
  * device=cuda + the FloatTensor cuda-bug patch
  * sane large nets + train_steps + reservoir memory
  * EVALUATE the AVERAGE policy (solver.action_probabilities), never the last iteration
  * exact nash_conv is infeasible on full NLHE -> validate by head-to-head vs baselines in OpenSpiel
  * save a checkpoint of the policy net
Run on the pod:  python3 -u deep_cfr_nlhe.py <iters> <traversals>
"""
import os
import sys
import time

import torch
# OpenSpiel action_probabilities uses legacy torch.FloatTensor(x, device=cuda) which rejects cuda.
_ORIG_FT = torch.FloatTensor
def _ft(*a, **k):
    dev = k.pop("device", None)
    t = _ORIG_FT(*a, **k)
    return t.to(dev) if dev is not None else t
torch.FloatTensor = _ft

import numpy as np
import pyspiel
from open_spiel.python.pytorch import deep_cfr

ITERS = int(sys.argv[1]) if len(sys.argv) > 1 else 200
TRAV = int(sys.argv[2]) if len(sys.argv) > 2 else 3000
NET = tuple(int(x) for x in os.environ.get("NET", "2048,2048,1024").split(","))   # big nets -> B200
BATCH = int(os.environ.get("BATCH", "32768"))                                     # big batches -> B200
MEM = int(float(os.environ.get("MEM", "1e7")))                                    # big reservoir -> RAM
ADV_STEPS = int(os.environ.get("ADV_STEPS", "3000"))
POL_STEPS = int(os.environ.get("POL_STEPS", "2000"))
DEV = "cuda" if torch.cuda.is_available() else "cpu"

# HU NLHE, 200bb (200 chips at 1/2... we use 50/100 blinds, 20000 stacks = 200bb to match Slumbot),
# fcpa betting abstraction (fold / call / pot / all-in) — the standard tractable NLHE abstraction.
GAME = ("universal_poker(betting=nolimit,numPlayers=2,numRounds=4,blind=100 50,"
        "firstPlayer=2 1 1 1,numSuits=4,numRanks=13,numHoleCards=2,numBoardCards=0 3 1 1,"
        "stack=20000 20000,bettingAbstraction=fcpa)")

print(f"Deep CFR on HU-NLHE (fcpa) | device={DEV} | iters={ITERS} trav={TRAV}", flush=True)
game = pyspiel.load_game(GAME)
print("loaded:", game.num_distinct_actions(), "actions", flush=True)

t0 = time.time()
solver = deep_cfr.DeepCFRSolver(
    game,
    policy_network_layers=NET,
    advantage_network_layers=NET,
    num_iterations=ITERS,
    num_traversals=TRAV,
    learning_rate=1e-3,
    batch_size_advantage=BATCH,
    batch_size_strategy=BATCH,
    memory_capacity=MEM,
    policy_network_train_steps=POL_STEPS,
    advantage_network_train_steps=ADV_STEPS,
    reinitialize_advantage_networks=True,
    device=DEV,
)
print(f"config net={NET} batch={BATCH} mem={MEM} adv={ADV_STEPS} pol={POL_STEPS} | "
      f"GPU={torch.cuda.get_device_name(0) if DEV == 'cuda' else 'cpu'}", flush=True)
solver.solve()
_peak = torch.cuda.max_memory_allocated() / 1e9 if DEV == "cuda" else 0.0
print(f"trained in {time.time()-t0:.0f}s | GPU peak mem {_peak:.1f} GB", flush=True)


def rollout(p0, p1, n, seed=0):
    rng = np.random.default_rng(seed)
    tot = 0.0
    for _ in range(n):
        s = game.new_initial_state()
        while not s.is_terminal():
            if s.is_chance_node():
                acts, ps = zip(*s.chance_outcomes())
                s.apply_action(int(rng.choice(acts, p=ps)))
            else:
                pl = s.current_player()
                probs = (p0 if pl == 0 else p1)(s)
                acts = list(probs.keys())
                pr = np.array([probs[a] for a in acts], dtype=float)
                pr = pr / pr.sum()
                s.apply_action(int(rng.choice(acts, p=pr)))
        tot += s.returns()[0]
    return tot / n


def uniform(s):
    la = s.legal_actions()
    return {a: 1.0 / len(la) for a in la}


def check_call(s):                       # always check/call (action 1 in fcpa = call/check)
    la = s.legal_actions()
    return {(1 if 1 in la else la[0]): 1.0}


avg = solver.action_probabilities                       # the AVERAGE policy (correct to evaluate)
vs_uni = rollout(avg, uniform, 800)
vs_cc = rollout(avg, check_call, 800)
print(f"AVG policy chips/hand (player0): vs uniform {vs_uni:+.0f} | vs check-call {vs_cc:+.0f} "
      f"(bb/100 ~ {vs_uni/100*100:+.0f} / {vs_cc/100*100:+.0f})", flush=True)

try:
    torch.save(solver._policy_network.state_dict(), "/root/deepcfr_policy.pt")
    print("saved policy net -> /root/deepcfr_policy.pt", flush=True)
except Exception as e:  # noqa: BLE001
    print("net save skipped:", e, flush=True)
torch.save({"game": GAME, "iters": ITERS, "trav": TRAV, "net": NET}, "/root/nlhe_ckpt_meta.pt")
print("RESULT done.", flush=True)
