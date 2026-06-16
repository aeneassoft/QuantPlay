"""Adapter: use the from-scratch HUNL Deep CFR policy net (deep_cfr_hunl) as the bot's decision core.

The GTOW/engine chip frame is identical to the trainer's (SB 50 / BB 100 / 20000 = 200bb), so we reconstruct a
minimal HState from the live engine state and call the EXACT training feature function `deep_cfr_hunl.features` —
zero feature duplication => no train/inference mismatch. Maps the net's fcpa choice (fold/call/pot/all-in) onto the
engine's (action, amount). Self-check (`python -m pokerbot.strategy.deepcfr_adapter`) proves the reconstruction
reproduces the trainer's features on random states.
"""
from __future__ import annotations

import numpy as np
import torch

from pokerbot.strategy import deep_cfr_hunl as dc

_STREET_IDX = {"preflop": 0, "flop": 1, "turn": 2, "river": 3}


class LoadedPolicy:
    def __init__(self, path, device="cpu"):
        ck = torch.load(path, map_location=device)
        self.net = dc.Net().to(device)
        self.net.load_state_dict(ck["policy"])
        self.net.eval()
        self.dev = device

    def strategy(self, feat, legal):
        with torch.no_grad():
            x = torch.tensor(feat, device=self.dev).unsqueeze(0)
            pr = torch.softmax(self.net(x), dim=1).cpu().numpy()[0]
        z = {a: max(float(pr[a]), 1e-9) for a in legal}
        tot = sum(z.values())
        return {a: z[a] / tot for a in legal}


def _raises_this_street(state) -> int:
    st = state.get("street")
    return sum(1 for h in state.get("history", []) if h.get("street") == st and h.get("action") in ("bet", "raise"))


def live_features(state: dict, hero_idx: int):
    """Reconstruct the trainer's infoset features from the live engine state. Returns (feat_vec, p) where p is the
    trainer's player index (0 = button)."""
    hero = state["players"][hero_idx]
    vill = state["players"][1 - hero_idx]
    s = dc.HState()
    s.street = _STREET_IDX.get(state["street"], 0)
    p = 0 if hero.get("is_button") else 1
    s.hole = [["2c", "2d"], ["2c", "2d"]]          # placeholder; features() only reads hole[p]
    s.hole[p] = list(hero["hole"])
    s.board = list(state["board"])
    s.committed = [0, 0]
    s.committed[p] = int(hero.get("committed_total", 0))
    s.committed[1 - p] = int(vill.get("committed_total", 0))
    s.to_match = s.committed[p] + int(state["legal"].get("to_call", 0))
    s.raises = _raises_this_street(state)
    return dc.features(s, p), p


def legal_fcpa(la: dict):
    acts = []
    if la.get("can_fold") or la.get("to_call", 0) > 0:
        acts.append(dc.FOLD)
    acts.append(dc.CALL)
    if la.get("can_raise"):
        acts.append(dc.POT)
        acts.append(dc.ALLIN)
    return acts


def _selfcheck(n=800):
    """Verify the live HState reconstruction reproduces the trainer's features EXACTLY (the only mismatch risk)."""
    import random
    rng = random.Random(0)
    bad = 0
    checked = 0
    for _ in range(n):
        s = dc.new_hand(rng)
        for _ in range(rng.randint(0, 6)):
            if s.done:
                break
            s = s.apply(rng.choice(s.legal()))
        if s.done:
            continue
        p = s.to_act
        f_true = dc.features(s, p)
        # build a fake live-state mirroring s (hero = the to-act player p; button iff p==0)
        owe = s.to_match - s.committed[p]
        fake = {
            "street": dc._RANKS and ["preflop", "flop", "turn", "river"][s.street],
            "board": list(s.board),
            "players": [None, None],
            "legal": {"to_call": owe},
            "history": [{"action": "bet", "street": ["preflop", "flop", "turn", "river"][s.street]}] * s.raises,
        }
        hero = {"hole": s.hole[p], "committed_total": s.committed[p], "is_button": (p == 0)}
        vill = {"committed_total": s.committed[1 - p], "is_button": (p != 0)}
        fake["players"][0] = hero            # hero_idx = 0 in the fake
        fake["players"][1] = vill
        f_live, _ = live_features(fake, 0)
        checked += 1
        if not np.allclose(f_true, f_live, atol=1e-6):
            bad += 1
            if bad <= 3:
                print(f"  MISMATCH at {s.hist}: \n   true={f_true}\n   live={f_live}")
    print(f"feature reconstruction self-check: {checked} states, {bad} mismatches "
          f"-> {'PASS' if bad == 0 else 'FAIL'}")


if __name__ == "__main__":
    _selfcheck()
