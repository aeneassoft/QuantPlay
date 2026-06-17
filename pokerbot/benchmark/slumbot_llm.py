"""Measure the FULL LLM brain (QwenPolicy) vs Slumbot — a real external HU near-GTO reference (bb/100).

The brain DRIVES via program-of-thought: each Slumbot decision point -> our `Spot` -> QwenPolicy emits + executes a
DSL program -> a legal action -> translated back to Slumbot. Reuses `slumbot.play_hand` (duck-typed bot: `.decide(st)`
+ `.hero_idx`).

HONEST framing: the local 1.7B is a BASELINE (SFT only, no RL) and Slumbot is HU (our target is 6-max) — so expect a
strongly NEGATIVE bb/100. This is a GROUNDED BASELINE to track progress against (RL + the 8B lift it), and it proves
the brain plays a full external game end-to-end (the "brain in the driver's seat").

Run: python -m pokerbot.benchmark.slumbot_llm --hands 100 [--adapter models/qwen_local_sft] [--base Qwen/Qwen3-1.7B]
"""
from __future__ import annotations

import argparse
import math
import os
import time

from pokerbot.benchmark.slumbot import BB, play_hand
from pokerbot.brain import modes
from pokerbot.brain.format_spot import Spot
from pokerbot.brain.policy import QwenPolicy, build_messages, parse_completion


def _pos(k: int, button: int) -> str:
    return "SB" if k == button else "BB"          # HU: the button posts the small blind


def spot_from_slumbot(st: dict) -> Spot:
    """Slumbot/HU state dict (slumbot.build_state) -> our canonical Spot (so QwenPolicy can decide on it)."""
    hero, button, bb = st["to_act"], st["button"], st["bb"]
    players, L = st["players"], st["legal"]
    seats = [{"seat": k, "pos": _pos(k, button), "stack": p["stack"],
              "committed_total": p["committed_total"], "folded": p.get("folded", False),
              "all_in": p.get("all_in", False)} for k, p in enumerate(players)]
    line = [{"street": h["street"], "pos": _pos(h["player"], button), "action": h["action"],
             "amount_bb": (round(h["to"] / bb, 1) if "to" in h else None),
             "hero": h["player"] == hero} for h in st.get("history", [])]
    return Spot(street=st["street"], board=list(st["board"]), bb=bb, hero_seat=hero,
                hero_pos=_pos(hero, button), hero_hole=list(players[hero]["hole"]),
                pot=st["pot"], to_call=L["to_call"], n_active=2, seats=seats,
                legal={k: L.get(k) for k in ("can_fold", "can_check", "can_call", "can_raise",
                                             "raise_min", "raise_max")},
                line=line)


class QwenSlumbotBot:
    """Duck-typed for slumbot.play_hand. `.decide(st)` runs the LLM program-of-thought; tracks frac_bad."""

    def __init__(self, policy: QwenPolicy):
        self.policy = policy
        self.hero_idx = 0
        self.bad = self.n = 0

    def decide(self, st: dict) -> dict:
        spot = spot_from_slumbot(st)
        res = parse_completion(self.policy._generate(build_messages(spot)), spot,
                               timeout_s=modes.current().time_budget_s)
        self.n += 1
        self.bad += int(not res["ok"])
        return {"action": res["action"], "amount": res["amount"]}


def _load(base: str, adapter: str) -> QwenPolicy:
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    tok = AutoTokenizer.from_pretrained(base)
    qc = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.bfloat16)
    bm = AutoModelForCausalLM.from_pretrained(base, quantization_config=qc, device_map="cuda")
    m = PeftModel.from_pretrained(bm, adapter)
    m.eval()
    return QwenPolicy(m, tok, sampling=False)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hands", type=int, default=100)
    ap.add_argument("--base", default="Qwen/Qwen3-1.7B")
    ap.add_argument("--adapter", default="models/qwen_local_sft")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    modes.set_mode("fast")
    bot = QwenSlumbotBot(_load(a.base, a.adapter))
    token, winnings, t0 = None, [], time.time()
    for h in range(a.hands):
        w, token = play_hand(bot, token, verbose=a.verbose and h < 3)
        winnings.append(w)
        if (h + 1) % 10 == 0:
            tot = sum(winnings)
            print(f"  {h+1:4d} hands | {tot/len(winnings):+.1f} bb/100 | frac_bad {bot.bad/max(1,bot.n):.2f} "
                  f"| {(time.time()-t0)/(h+1):.1f}s/hand", flush=True)
    tot, n = sum(winnings), len(winnings)
    bb100 = tot / n
    stderr = ((sum((w - bb100) ** 2 for w in winnings) / n) ** 0.5 / BB) / math.sqrt(n) * 100
    print(f"\n=== LLM (QwenPolicy {a.adapter}) vs Slumbot ===")
    print(f"hands={n} | {bb100:+.1f} bb/100 (+/-{stderr:.1f} stderr) | "
          f"decisions={bot.n} frac_bad={bot.bad/max(1,bot.n):.2f}", flush=True)


if __name__ == "__main__":
    main()
