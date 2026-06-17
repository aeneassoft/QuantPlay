"""C1 PREFLIGHT (pod, pre-SFT, ~1-2 min, no model load) — fail-fast so an integration bug surfaces in minutes, not after
the expensive SFT. Checks: the RL stack imports + CUDA; the DAPO `GRPOConfig` actually CONSTRUCTS with our knobs (catches
trl API-drift on the unpinned-ish version); a 1-state `ev_reward` returns a finite float (the reward path works on the
pod). Prints `PREFLIGHT1_OK` on success, else exits non-zero with `PREFLIGHT1_FAIL: ...`. Run: python -u -m training.preflight
"""
from __future__ import annotations

import sys


def main():
    import torch  # noqa: F401
    import transformers  # noqa: F401
    import trl
    import peft  # noqa: F401
    import bitsandbytes  # noqa: F401
    import datasets  # noqa: F401
    import vllm  # noqa: F401
    assert torch.cuda.is_available(), "no CUDA device"
    cap = torch.cuda.get_device_capability(0)
    # a REAL bf16 GPU op — on Blackwell (sm_100/103) `is_available()` passes even when the kernels are missing; a matmul
    # is the canary that the cu128 build actually runs on THIS card (else it would crash/fall back mid-training).
    _x = torch.randn(4096, 4096, device="cuda", dtype=torch.bfloat16)
    _y = float((_x @ _x).float().sum())
    assert _y == _y, "GPU bf16 matmul produced NaN"   # NaN != NaN
    print(f"PRE imports OK | torch {torch.__version__} | cuda {torch.version.cuda} | sm_{cap[0]}{cap[1]} | "
          f"trl {trl.__version__} | GPU {torch.cuda.get_device_name(0)} | bf16 matmul OK", flush=True)

    from training.qwen_grpo import build_state_buffer, make_config, make_ev_reward
    make_config("/tmp/_pf")                                   # constructs GRPOConfig(loss_type=dapo, epsilon_high, ...)
    print("PRE GRPOConfig(loss_type=dapo, epsilon_high, scale_rewards, vllm_structured_outputs_regex) constructs OK",
          flush=True)

    from pokerbot.brain.format_spot import spot_from_table
    states = build_state_buffer(1, oversample=3.0, k_screen=4, spread_eps=0.0, seed=0)
    assert states, "state buffer empty"
    snaps = [s for s, _ in states]
    legal = spot_from_table(snaps[0], 0).legal
    act = "check" if legal.get("can_check") else ("call" if legal.get("can_call") else "fold")
    r = make_ev_reward(snaps, k=4)(completions=[f"x = api.required_equity(spot.to_call, spot.pot)\ndecide('{act}')"],
                                   sid=[0], base_seed=[0])
    assert len(r) == 1 and isinstance(r[0], float), f"reward not a finite float: {r}"
    print(f"PRE 1-state ev_reward OK -> {r[0]:.2f}", flush=True)
    print("PREFLIGHT1_OK", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        print(f"PREFLIGHT1_FAIL: {type(e).__name__}: {e}", flush=True)
        sys.exit(1)
